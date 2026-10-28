"""Zotero, for Research (modules/research.py): a paper from the digest goes into your Zotero library with one tap (the
Zotero button under it), and your reading notes that link the paper get a link to its Zotero item.

Two ways in (research.zotero):
    app   the Zotero app on this computer, through its connector at 127.0.0.1:23119 (what the browser extension
          uses), when Zotero is running. Nothing leaves this computer from Kurooto.
    web   Zotero's web API (api.zotero.org) with a key you make at zotero.org/settings/keys (allow library access
          and write access), kept with your other secrets: `/zotero key <key>`, or Research's setup form.
    auto  (the default) the app when it's running, else the web API when there's a key.
    off   no Zotero buttons.

What goes to Zotero is the paper's public details: title, authors (the first four the source gives), abstract,
date, link, arXiv id or DOI. Kurooto remembers each paper's Zotero item (<state>/research/zotero.json), so a second
tap doesn't add it twice.

Reading notes: a note of yours that links a paper you put in Zotero (its arXiv, bioRxiv, medRxiv, PubMed or feed
link) gets a Kurooto block with `zotero://select/library/items/<key>` (it opens the item in Zotero), right after the
add and in a nightly pass (research.zotero_links). Through the app, the item's key is found with Zotero's local API
(Zotero 7: Settings → Advanced → "Allow other applications on this computer to communicate with Zotero"); without
it the paper is in Zotero but notes get no link.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import egress, graphwrite
from kurooto.core.clock import now
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.modules.research import Research

WEB = "https://api.zotero.org"
LOCAL = "http://127.0.0.1:23119"
KEY_NAME = "research.zotero_key"  # where the web API key is kept (app.secrets)
MODES = ("auto", "app", "web", "off")
MAX_NOTES = 4000  # notes read looking for paper links
MAX_NOTE = 400 * 1024


def select_link(key: str) -> str:
    """Opens the item in Zotero (your own library)."""
    return f"zotero://select/library/items/{key}"


def ref_of(pid: str) -> str:
    """A paper's short reference for buttons ("zot:<ref>:add", under Telegram's 64 bytes)."""
    return hashlib.sha1(pid.encode("utf-8")).hexdigest()[:10]  # noqa: S324 (a name, not security)


def _creators(paper: dict) -> list[dict]:
    pubmed = str(paper.get("id", "")).startswith("pubmed:")
    out = []
    for a in paper.get("authors") or []:
        a = re.sub(r"\s+", " ", str(a)).strip()
        if not a:
            continue
        parts = a.split(" ")
        if len(parts) == 1:
            out.append({"creatorType": "author", "name": a})
        elif pubmed:  # PubMed: "Doe JQ"
            out.append({"creatorType": "author", "lastName": parts[0], "firstName": " ".join(parts[1:])})
        else:
            out.append({"creatorType": "author", "lastName": parts[-1], "firstName": " ".join(parts[:-1])})
    return out


def item(paper: dict) -> dict:
    """A digest paper as a Zotero item (the same JSON for the web API and the connector)."""
    pid = str(paper.get("id", ""))
    kind, _, ident = pid.partition(":")
    out = {
        "title": paper.get("title", ""),
        "creators": _creators(paper),
        "abstractNote": paper.get("summary", "") if kind != "pubmed" else "",
        "date": paper.get("date", ""),
        "url": paper.get("link", ""),
        "accessDate": now().date().isoformat(),
        "tags": [],
    }
    source = str(paper.get("source", ""))
    if kind == "arxiv":
        out.update(itemType="preprint", repository="arXiv", archiveID=f"arXiv:{ident}", libraryCatalog="arXiv.org")
    elif kind == "doi":
        server = "medRxiv" if "medrxiv" in (paper.get("link") or "").lower() else "bioRxiv"
        out.update(itemType="preprint", repository=server, DOI=ident, libraryCatalog=server)
    elif kind == "pubmed":
        out.update(itemType="journalArticle", extra=f"PMID: {ident}", libraryCatalog="PubMed")
        journal = paper.get("summary", "")
        if journal:
            out["publicationTitle"] = journal
    else:
        out.update(itemType="journalArticle", libraryCatalog=source[:80])
    return {k: v for k, v in out.items() if v != ""}


class Zotero:
    def __init__(self, research: Research):
        self.r = research
        self.app = research.app
        self.file = self.app.paths.state / "research" / "zotero.json"

    # ------------------------------------------------------------------------------------------- state
    def _state(self) -> dict:
        d = jload(self.file, {}) or {}
        d.setdefault("items", {})
        return d

    def items(self) -> dict:
        return self._state()["items"]

    def _keep(self, pid: str, rec: dict) -> None:
        with Lock(self.app.paths.state, "research-zotero"):
            d = self._state()
            d["items"][pid] = rec
            jsave(self.file, d)

    # ------------------------------------------------------------------------------------------- which way
    def mode(self) -> str:
        m = str(self.r.setting("zotero") or "auto").strip().lower()
        return m if m in MODES else "auto"

    def key(self) -> str:
        return (self.app.secrets.get(KEY_NAME) or "").strip()

    def app_running(self) -> bool:
        try:
            with egress.urlopen(f"{LOCAL}/connector/ping", "Research: Zotero", timeout=1.5) as r:
                return r.status == 200
        except (OSError, ValueError):
            return False

    def way(self) -> str:
        """How a paper would go in now: "app", "web" or "" (off, or neither is there)."""
        m = self.mode()
        if m == "off":
            return ""
        if m in ("auto", "app") and self.app_running():
            return "app"
        if m in ("auto", "web") and self.key():
            return "web"
        return ""

    # ------------------------------------------------------------------------------------------- the web API
    def _web(self, path: str, data=None, key: str | None = None, method: str | None = None, headers=None):
        key = key if key is not None else self.key()
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(  # noqa: S310 (https, a fixed host)
            f"{WEB}{path}",
            data=body,
            method=method or ("POST" if body is not None else "GET"),
            headers={
                "Zotero-API-Key": key,
                "Zotero-API-Version": "3",
                "Content-Type": "application/json",
                "User-Agent": "kurooto (research digest)",
                **(headers or {}),
            },
        )
        with egress.urlopen(req, "Research: Zotero", timeout=30) as r:
            return json.loads(r.read(2 * 1024 * 1024) or b"null")

    def check_key(self, key: str) -> tuple[bool, str, str]:
        """(ok, what to say, the library's user id) for a web API key: it must allow writing to your library."""
        try:
            info = self._web("/keys/current", key=key)
        except urllib.error.HTTPError as e:
            return False, "Zotero didn't take that key" + (" (it isn't a key)" if e.code in (403, 404) else ""), ""
        except (OSError, ValueError) as e:
            return False, f"Couldn't reach Zotero ({type(e).__name__})", ""
        user = str((info or {}).get("userID") or "")
        lib = ((info or {}).get("access") or {}).get("user") or {}
        if not user or not lib.get("write"):
            return False, "That key can't add to your library: make one with library and write access", ""
        return True, f"Zotero key kept ({info.get('username') or 'your library'}).", user

    def set_key(self, key: str) -> str:
        key = key.strip()
        if key.lower() in ("off", "remove", "clear", "none"):
            self.app.secrets.delete(KEY_NAME)
            with Lock(self.app.paths.state, "research-zotero"):
                d = self._state()
                d.pop("user", None)
                jsave(self.file, d)
            return "Zotero key removed."
        if not re.fullmatch(r"[A-Za-z0-9]{16,40}", key):
            return "That doesn't look like a Zotero key (24 letters and digits, from zotero.org/settings/keys)."
        ok, said, user = self.check_key(key)
        if not ok:
            return said + "."
        self.app.secrets.set(KEY_NAME, key)
        with Lock(self.app.paths.state, "research-zotero"):
            d = self._state()
            d["user"] = user
            jsave(self.file, d)
        self.app.events.emit("zotero_key_set")
        return said + " Papers in the digest now come with a Zotero button."

    def _user(self) -> str:
        user = str(self._state().get("user") or "")
        if user:
            return user
        ok, _, user = self.check_key(self.key())
        if ok:
            with Lock(self.app.paths.state, "research-zotero"):
                d = self._state()
                d["user"] = user
                jsave(self.file, d)
        return user if ok else ""

    def _web_add(self, paper: dict) -> str:
        user = self._user()
        if not user:
            raise ValueError("the Zotero key doesn't work (/zotero key <key> sets a new one)")
        res = self._web(
            f"/users/{urllib.parse.quote(user)}/items",
            [item(paper)],
            headers={"Zotero-Write-Token": uuid.uuid4().hex},
        )
        ok = (res or {}).get("successful") or {}
        if "0" in ok:
            return str(ok["0"].get("key") or (res.get("success") or {}).get("0") or "")
        failed = ((res or {}).get("failed") or {}).get("0") or {}
        raise ValueError(f"Zotero said no: {failed.get('message') or 'unknown reason'}")

    # -------------------------------------------------------------------------------------- the Zotero app
    def _local_add(self, paper: dict) -> str:
        it = {**item(paper), "id": ref_of(paper["id"]), "attachments": [], "notes": []}
        body = json.dumps({"items": [it], "uri": paper.get("link") or "", "sessionID": uuid.uuid4().hex}).encode()
        req = urllib.request.Request(  # noqa: S310 (this computer)
            f"{LOCAL}/connector/saveItems",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "X-Zotero-Connector-API-Version": "3"},
        )
        with egress.urlopen(req, "Research: Zotero", timeout=20) as r:
            if r.status not in (200, 201):
                raise ValueError(f"the Zotero app said {r.status}")
        return self._local_key(paper)

    def _local_key(self, paper: dict) -> str:
        """The new item's key, from Zotero's local API (Zotero 7, when other programs may talk to it); "" without."""
        title = str(paper.get("title") or "")
        q = urllib.parse.urlencode({"q": title[:200], "limit": 10, "format": "json", "sort": "dateAdded"})
        for _ in range(3):  # the save lands a moment after the connector answers
            try:
                with egress.urlopen(f"{LOCAL}/api/users/0/items?{q}", "Research: Zotero", timeout=5) as r:
                    rows = json.loads(r.read(2 * 1024 * 1024) or b"[]")
            except (OSError, ValueError):
                return ""
            for row in rows if isinstance(rows, list) else []:
                data = row.get("data") or {}
                if str(data.get("title", "")).strip().lower() == title.strip().lower():
                    return str(row.get("key") or data.get("key") or "")
            time.sleep(0.5)
        return ""

    # ------------------------------------------------------------------------------------------- adding
    def add(self, paper: dict) -> tuple[bool, str]:
        """Put one paper into Zotero; (ok, what to say)."""
        pid = str(paper.get("id") or "")
        have = self.items().get(pid)
        if have:
            return True, f"{paper.get('title', 'That paper')[:80]} is already in your Zotero."
        way = self.way()
        if not way:
            if self.mode() == "off":
                return False, "Zotero is off (research.zotero)."
            return False, (
                "Zotero isn't reachable: open the Zotero app on this computer, or add a web API key "
                "(/zotero key <key>, from zotero.org/settings/keys)."
            )
        try:
            key = self._local_add(paper) if way == "app" else self._web_add(paper)
        except (OSError, ValueError) as e:
            self.app.events.emit("zotero_failed", via=way, error=type(e).__name__)
            return False, f"Couldn't add it to Zotero: {e}"[:300]
        rec = {
            "key": key,
            "via": way,
            "title": paper.get("title", "")[:300],
            "link": paper.get("link", ""),
            "at": now().isoformat(timespec="seconds"),
        }
        self._keep(pid, rec)
        self.app.events.emit("zotero_added", via=way, linked=bool(key))
        ig = self.app.modules.get("integrate")
        if ig is not None:  # integrate.sources with "papers" (0.9.0, not there by default): the concept graph reads it
            try:
                ig.take_paper(paper)
            except Exception as e:
                self.app.events.emit("integrate_failed", error=f"paper: {type(e).__name__}"[:60])
        title = paper.get("title", "It")[:80]
        linked = self.link_notes() if key and self.r.setting("zotero_links") else 0
        where = "your Zotero library" if way == "web" else "Zotero (the app)"
        out = f"{title}: added to {where}."
        if linked:
            out += f" {linked} reading note{'s' if linked > 1 else ''} now link{'' if linked > 1 else 's'} to it."
        elif not key:
            out += (
                " Notes can't link to it: turn on Zotero's local API (Settings → Advanced → Allow other "
                "applications on this computer to communicate with Zotero)."
            )
        return True, out

    def add_later(self, paper: dict) -> None:
        """A tap: added in a thread (the network can take a while), and the outcome told."""

        def go():
            ok, said = self.add(paper)
            self.app.notify(said, kind="result" if ok else "info", why="asked")

        threading.Thread(target=go, name="zotero", daemon=True).start()

    # ------------------------------------------------------------------------------------- reading notes
    def link_notes(self) -> int:
        """Notes that link a paper you put in Zotero get (or update) a Kurooto block linking its Zotero item. Returns
        how many notes changed."""
        known = [(r, _needles(r.get("link", ""), pid)) for pid, r in self.items().items() if r.get("key")]
        known = [(r, n) for r, n in known if n]
        if not known:
            return 0
        root = self.app.workspace
        changed, seen = 0, 0
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if not name.endswith(".md"):
                    continue
                seen += 1
                if seen > MAX_NOTES:
                    return changed
                changed += self._link_one(Path(dirpath) / name, known)
        return changed

    def _link_one(self, f: Path, known: list) -> int:
        try:
            if f.stat().st_size > MAX_NOTE:
                return 0
            old = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return 0
        mine = graphwrite.BLOCK_ANY.sub("", old)
        hits = [r for r, needles in known if any(n in mine for n in needles)]
        if not hits:
            return 0
        rows = [f"- [{r['title'][:120] or 'In Zotero'}]({select_link(r['key'])}) (in Zotero)" for r in hits]
        new = graphwrite.put_block(old, "zotero", "## In Zotero\n\n" + "\n".join(rows))
        if new == old or not graphwrite.guarded(old, new).ok:
            return 0
        from kurooto.core.tools import write_note_file

        write_note_file(f, new)
        return 1


def _needles(link: str, pid: str) -> list[str]:
    """What in a note means it links this paper: its link without the scheme, and its arXiv id or DOI."""
    out = []
    bare = re.sub(r"^https?://(?:www\.)?", "", link or "").rstrip("/")
    if len(bare) > 12:
        out.append(bare)
    kind, _, ident = pid.partition(":")
    if kind == "arxiv" and ident:
        out += [f"arxiv.org/abs/{ident}", f"arxiv.org/pdf/{ident}", f"arXiv:{ident}"]
    elif kind == "doi" and ident:
        out.append(ident)
    return list(dict.fromkeys(out))
