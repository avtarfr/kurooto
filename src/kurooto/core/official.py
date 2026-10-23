"""Official add-ons: the add-ons published from addons/ in Kurooto's own repository, each a public repository of its
own, offered with one Add on the dashboard (Features → Add-ons), on Telegram (/addons official) and in a terminal
(`kurooto addons official`, `kurooto addons add <name>`).

The list is data/official_addons.json, shipped inside Kurooto, so a release's signature covers it: each one's name,
title, one line, what it needs, its repository, tag and pinned commit. "Official" means exactly: in this list and at
that commit. One added from the list, or by hand from the same address at that commit, is marked official; another
commit, another address (a fork) or a changed folder isn't.

Adding one is still core/addons.py's card and yes: fetch(..., pin=<the commit>) clones it at the pinned commit (the
tag is only its label), you read the card, and only your yes adds it (a guarded tap: core/tap.py's addon.install).

Updates come with Kurooto: when a newer Kurooto pins a newer commit, the commit you have goes into the entry's
"earlier" list. One you have at an earlier official commit is then offered the update, once, in a message through
Calm (addons.official_updates; why: addons.official_update), and with an Update button on the dashboard and under
/addons. The update is core/addons.py's: what changes, the card again, and your yes. Nothing updates by itself.

    catalog()                  the list (each entry a dict), as shipped
    find(word)                 the entry by its name or its repository's ("restic-backups", "command-words")
    match(url, commit, name)   the entry when this is an official add-on at its pinned commit, else None
    update_for(rec)            the entry when the add-on you have (its record) has a newer official commit
    rows(paths)                each entry with what you have of it: "", "official", "update" or "other"
    fetch(paths, word)         the card of an official one, at its pinned commit (core/addons.py's fetch)
    button(app, ref, act)      the "oad:" buttons: look (its card), check (an update's), yes / no (your answer)
"""

from __future__ import annotations

import functools
import json
import re
import threading
import time
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.paths import Paths

FILE = "official_addons.json"  # in kurooto/data
OFFERED = "official-addons.json"  # in the state folder: the update offers already made, {name: commit}
OFFER_ACTION = "addons.official_offer"
TOKEN = re.compile(r"[0-9a-f]{12}")


@functools.cache
def _load() -> tuple[dict, ...]:
    with resources.files("kurooto.data").joinpath(FILE).open("rb") as f:
        raw = json.load(f)
    out = []
    for e in raw.get("addons") or []:
        out.append(
            {
                "name": str(e["name"]),
                "title": str(e["title"]),
                "line": str(e.get("line") or ""),
                "needs": str(e.get("needs") or ""),
                "url": str(e["url"]),
                "tag": str(e.get("tag") or ""),
                "commit": str(e["commit"]).lower(),
                "earlier": [str(x).lower() for x in e.get("earlier") or []],
                "source": str(e.get("source") or ""),
            }
        )
    return tuple(out)


def catalog() -> list[dict]:
    return [dict(e) for e in _load()]


def _repo(url: str) -> str:
    """One spelling per repository: github.com/<owner>/<repo> for its https and ssh addresses (with or without .git),
    else the address itself, without a trailing / or .git."""
    u = (url or "").strip().lower().rstrip("/")
    m = re.fullmatch(r"(?:https://(?:www\.)?|ssh://git@|git@)github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?", u)
    return f"github.com/{m[1]}" if m else u.removesuffix(".git")


def same_repo(a: str, b: str) -> bool:
    return bool(a and b) and _repo(a) == _repo(b)


def find(word: str) -> dict | None:
    """The entry by its name ("habits") or its repository's name ("command-words", "kurooto-command-words")."""
    w = (word or "").strip().lower()
    for e in _load():
        slug = _repo(e["url"]).rsplit("/", 1)[-1]
        if w in (e["name"], slug, slug.removeprefix("kurooto-")):
            return dict(e)
    return None


def entry_for(url: str) -> dict | None:
    """The entry whose repository this address is (any commit)."""
    return next((dict(e) for e in _load() if same_repo(e["url"], url)), None)


def match(url: str, commit: str, name: str = "") -> dict | None:
    """The entry when (url, commit) is an official add-on at its pinned commit: the same repository, that commit."""
    e = entry_for(url)
    if e is None or (commit or "").lower() != e["commit"] or (name and name != e["name"]):
        return None
    return e


def update_for(rec: dict | None) -> dict | None:
    """The entry when the add-on you have is at an earlier official commit and this Kurooto pins a newer one."""
    if not rec:
        return None
    e = entry_for(str(rec.get("url") or ""))
    commit = str(rec.get("commit") or "").lower()
    if e is None or rec.get("name") != e["name"] or commit == e["commit"] or commit not in e["earlier"]:
        return None
    return e


def rows(p: Paths) -> list[dict]:
    """Each official add-on with what you have of it. have: "" (not added), "official" (at its pinned commit),
    "update" (an earlier official commit: the newer one waits for your yes), "other" (one of that name from another
    address or commit: not marked official)."""
    from kurooto.core import addons

    have = addons.installed(p)
    out = []
    for e in _load():
        rec = have.get(e["name"])
        state = ""
        if rec:
            state = "official" if match(rec.get("url", ""), rec.get("commit", ""), e["name"]) else ""
            state = state or ("update" if update_for(rec) else "other")
        out.append({**e, "earlier": list(e["earlier"]), "have": state, "commit_have": (rec or {}).get("commit", "")})
    return out


def fetch(p: Paths, word: str) -> dict:
    """An official add-on's card at its pinned commit (nothing is added: core/addons.py's install with your yes)."""
    from kurooto.core import addons

    e = find(word)
    if e is None:
        raise addons.AddonError(f"there's no official add-on called {word!r} (kurooto addons official lists them)")
    return addons.fetch(p, e["url"], e["tag"], pin=e["commit"])


def lines(p: Paths) -> list[str]:
    """The official add-ons in words, for /addons and `kurooto addons official`."""
    out = []
    for r in rows(p):
        said = {
            "official": f"added ({r['tag']})",
            "update": f"added; {r['tag']} is ready to update to",
            "other": "added from another address or commit, so not marked official",
        }.get(r["have"], "not added")
        out.append(f"• {r['title']} ({r['name']}): {r['line']} Needs: {r['needs']}. {said}.")
    return out


def buttons(p: Paths) -> list[list[tuple[str, str]]]:
    """Add under each one not added, Update under each with a newer official commit (one row each)."""
    out = []
    for r in rows(p):
        if r["have"] == "":
            out.append([(f"Add {r['title']}"[:40], f"oad:{r['name']}:look")])
        elif r["have"] == "update":
            out.append([(f"Update {r['title']}"[:40], f"oad:{r['name']}:check")])
    return out


# ------------------------------------------------------------------------------------ the buttons ("oad:")
def button(app: App, ref: str, act: str) -> str:
    """oad:<name>:look (its card, with Add / Don't), oad:<name>:check (an update's), oad:<token>:yes|no (your answer
    to that card). Fetching clones, so it runs aside and the card comes as a message."""
    from kurooto.core import addons

    p = app.paths
    if act in ("look", "check"):
        e = find(ref)
        if e is None:
            return "That add-on isn't in this Kurooto's official list any more."
        _aside(_card, app, e["name"], act)
        return "Fetching its card…" if act == "look" else "Looking at what the update changes…"
    if not TOKEN.fullmatch(ref or ""):
        return "That card isn't waiting any more: look again."
    if act != "yes":
        addons.drop(p, ref)
        return "Not added; nothing was kept."
    ok, msg = addons.install(p, ref, True, via="button")
    if ok:
        from kurooto.core import overlay

        try:
            overlay.reload_linked(app)
        except Exception as e:  # added all the same: it loads at the next start
            app.events.emit("module_failed", module="addons", error=f"{type(e).__name__}: {e}"[:300])
    app.notify(msg, kind="result", why="asked")
    return msg[:190]


def _aside(fn, *args) -> None:
    threading.Thread(target=fn, args=args, name="official-addon", daemon=True).start()


def _card(app: App, name: str, act: str) -> None:
    from kurooto.core import addons

    try:
        out = fetch(app.paths, name) if act == "look" else addons.check_update(app.paths, name)
    except addons.AddonError as e:
        said = str(e)
        app.notify(f"{name}: {said[:1].upper() + said[1:]}.", kind="result", why="asked")
        return
    if out.get("same"):
        app.notify(f"{name} is at the newest commit already ({out['commit'][:12]}).", kind="result", why="asked")
        return
    code = bool(out["card"].get("code"))
    verb = "Update" if act == "check" else "Add"
    head = "What this update brings:\n" + out["changes_text"] + "\n\n" if out.get("changes_text") else ""
    text = f"{head}{out['text']}\n\n{verb} it? Nothing is {'updated' if act == 'check' else 'added'} until you tap."
    yes = f"{verb}, I trust its code" if code else verb
    app.notify(text, kind="result", why="asked",
               buttons=[[(yes, f"oad:{out['token']}:yes"), ("Don't", f"oad:{out['token']}:no")]])  # fmt: skip


# ----------------------------------------------------------------------------- update offers, once each
def offers(app: App) -> list[dict]:
    """The official add-ons you have with a newer official commit that you weren't told about yet."""
    from kurooto.core import addons

    told = jload(Path(app.paths.state) / OFFERED, {}) or {}
    out = []
    for name, rec in sorted(addons.installed(app.paths).items()):
        e = update_for(rec)
        if e is not None and told.get(name) != e["commit"]:
            out.append(e)
    return out


def start(app: App) -> None:
    """At start: when this Kurooto brought a newer official commit of one you have, a message says so (in 2 minutes,
    once per commit), with a button that shows what changes. addons.official_updates off: no message (the dashboard
    and /addons still show Update)."""
    app.scheduler.action(OFFER_ACTION, lambda payload=None: offer(app))
    if app.settings.get("addons.official_updates", True) is False or not offers(app):
        return
    app.scheduler.at(time.time() + 120, OFFER_ACTION, key="addons:official_offer", grace_s=7 * 86400)


def offer(app: App) -> int:
    """The message itself (through Calm). Returns how many it named."""
    if app.settings.get("addons.official_updates", True) is False:
        return 0
    todo = offers(app)
    if not todo:
        return 0
    names = ", ".join(f"{e['title']} ({e['tag']})" for e in todo)
    one = len(todo) == 1
    text = (
        f"This Kurooto brings a newer official version of {names}. "
        f"{'It' if one else 'Each'} stays as it is until you've seen what changes and said yes."
    )
    app.notify(text, kind="info", why="addons.official_update", about=", ".join(e["name"] for e in todo),
               buttons=[[(f"Look: {e['title']}"[:40], f"oad:{e['name']}:check")] for e in todo])  # fmt: skip
    f = Path(app.paths.state) / OFFERED
    told = jload(f, {}) or {}
    jsave(f, {**told, **{e["name"]: e["commit"] for e in todo}})
    return len(todo)
