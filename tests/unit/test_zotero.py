"""Zotero for Research (modules/zotero.py): a digest paper into Zotero with one tap, through the Zotero app's connector
or the web API with a key; a second tap doesn't add it twice; reading notes that link the paper get a Kurooto block
with its zotero://select link, and nothing of the note's own text changes."""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kurooto.core import egress
from kurooto.modules import zotero as zmod
from tests.unit.test_research import FakeSources

KEY = "abcdefghijklmnopqrstuvwx"
PAPER = {
    "id": "arxiv:2610.00001",
    "title": "Graph networks for molecules",
    "authors": ["Ada Q. Lovelace", "Plato"],
    "summary": "message passing",
    "link": "https://arxiv.org/abs/2610.00001",
    "date": "2026-10-20",
    "source": "arXiv",
}


class FakeZotero:
    """The web API (/keys/current, /users/<id>/items) and the app's connector (/connector/ping, /connector/saveItems,
    the local API's /api/users/0/items) on one local server."""

    def __init__(self, write=True, local_api=True):
        self.posted: list[dict] = []
        self.saved: list[dict] = []
        self.headers: list[dict] = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, ctype="application/json"):
                body = json.dumps(obj).encode() if obj is not None else b""
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = urllib.parse.urlsplit(self.path)
                fake.headers.append({k.lower(): v for k, v in self.headers.items()})
                if u.path == "/keys/current":
                    if self.headers.get("Zotero-API-Key") != KEY:
                        return self._send(403, {"error": "forbidden"})
                    return self._send(
                        200, {"userID": 4242, "username": "ada", "access": {"user": {"library": True, "write": write}}}
                    )
                if u.path == "/connector/ping":
                    return self._send(200, None, "text/html")
                if u.path == "/api/users/0/items":
                    if not local_api:
                        return self._send(403, {"error": "local API off"})
                    rows = [{"key": "LOCAL123", "data": {"key": "LOCAL123", "title": s["title"]}} for s in fake.saved]
                    return self._send(200, rows)
                return self._send(404, {})

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"null")
                fake.headers.append({k.lower(): v for k, v in self.headers.items()})
                if self.path == "/users/4242/items":
                    fake.posted += body
                    return self._send(200, {"successful": {"0": {"key": "WEBKEY12"}}, "success": {"0": "WEBKEY12"}})
                if self.path == "/connector/saveItems":
                    fake.saved += body["items"]
                    return self._send(201)
                return self._send(404, {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"


@pytest.fixture
def zot(env, monkeypatch):
    fake = FakeZotero()
    monkeypatch.setattr(zmod, "WEB", fake.base)
    yield env, fake, env.app.modules["research"]
    fake.server.shutdown()


def on(env):
    env.app.settings.set("research.feeds", [{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}])
    env.on("research")


def wait_for(cond, secs=5.0):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_items_carry_the_papers_public_details():
    it = zmod.item(PAPER)
    assert it["itemType"] == "preprint" and it["archiveID"] == "arXiv:2610.00001" and it["repository"] == "arXiv"
    assert it["creators"] == [
        {"creatorType": "author", "lastName": "Lovelace", "firstName": "Ada Q."},
        {"creatorType": "author", "name": "Plato"},
    ]
    pm = zmod.item({**PAPER, "id": "pubmed:123", "authors": ["Doe JQ"], "summary": "The Lancet"})
    assert pm["itemType"] == "journalArticle" and pm["extra"] == "PMID: 123" and pm["publicationTitle"] == "The Lancet"
    assert pm["creators"] == [{"creatorType": "author", "lastName": "Doe", "firstName": "JQ"}]
    assert zmod.select_link("AB12") == "zotero://select/library/items/AB12"


def test_the_web_api_with_a_key(zot):
    env, fake, r = zot
    on(env)
    assert r.zotero.way() == ""  # no app running, no key: no buttons
    assert r.zotero_buttons([PAPER]) is None
    assert env.say("/zotero key nonsense!").startswith("That doesn't look like a Zotero key")
    assert env.say(f"/zotero key {KEY}").startswith("Zotero key kept (ada).")
    assert env.app.secrets.get(zmod.KEY_NAME) == KEY and KEY not in json.dumps(env.app.settings.all())
    assert r.zotero.way() == "web"
    ok, said = r.zotero.add(PAPER)
    assert ok and said.startswith("Graph networks for molecules: added to your Zotero library.")
    sent = fake.posted[-1]
    assert sent["title"] == PAPER["title"] and sent["url"] == PAPER["link"] and sent["itemType"] == "preprint"
    assert any(h.get("zotero-api-key") == KEY and h.get("zotero-write-token") for h in fake.headers)
    assert r.zotero.items()["arxiv:2610.00001"]["key"] == "WEBKEY12"
    assert r.zotero.add(PAPER)[1].endswith("is already in your Zotero.") and len(fake.posted) == 1
    assert env.say("/zotero").startswith("Zotero: through Zotero's web API with your key. 1 paper")
    assert env.say("/zotero key off") == "Zotero key removed." and r.zotero.way() == ""


def test_a_key_that_cant_write_is_refused(env, monkeypatch):
    fake = FakeZotero(write=False)
    monkeypatch.setattr(zmod, "WEB", fake.base)
    on(env)
    assert "can't add to your library" in env.say(f"/zotero key {KEY}")
    assert env.app.secrets.get(zmod.KEY_NAME) is None
    fake.server.shutdown()


def test_the_zotero_app_through_its_connector(env, monkeypatch):
    fake = FakeZotero()
    monkeypatch.setattr(zmod, "LOCAL", fake.base)
    on(env)
    r = env.app.modules["research"]
    assert r.zotero.way() == "app"  # running: the app comes first, even with no key
    ok, said = r.zotero.add(PAPER)
    assert ok and "added to Zotero (the app)" in said
    assert fake.saved[0]["title"] == PAPER["title"] and fake.saved[0]["id"] == zmod.ref_of(PAPER["id"])
    assert r.zotero.items()[PAPER["id"]]["key"] == "LOCAL123"
    env.app.settings.set("research.zotero", "off")
    assert r.zotero.way() == "" and r.zotero_buttons([PAPER]) is None
    fake.server.shutdown()


def test_without_the_local_api_it_says_notes_cant_link(env, monkeypatch):
    fake = FakeZotero(local_api=False)
    monkeypatch.setattr(zmod, "LOCAL", fake.base)
    monkeypatch.setattr(zmod.time, "sleep", lambda s: None)
    on(env)
    ok, said = env.app.modules["research"].zotero.add(PAPER)
    assert ok and "Notes can't link to it" in said
    assert env.app.modules["research"].zotero.items()[PAPER["id"]]["key"] == ""
    fake.server.shutdown()


def test_reading_notes_get_the_zotero_link_and_nothing_else_changes(zot):
    env, fake, r = zot
    on(env)
    env.app.secrets.set(zmod.KEY_NAME, KEY)
    note = env.app.workspace / "research" / "reading" / "graph-nets.md"
    note.parent.mkdir(parents=True)
    mine = "# Graph nets\n\nRead [the paper](https://arxiv.org/abs/2610.00001): message passing is neat.\n"
    note.write_text(mine)
    other = env.app.workspace / "inbox" / "unrelated.md"
    other.parent.mkdir(parents=True)
    other.write_text("# Unrelated\n\nNothing about it.\n")
    ok, said = r.zotero.add(PAPER)
    assert ok and said.endswith("1 reading note now links to it.")
    text = note.read_text()
    assert text.startswith(mine.rstrip("\n")) and "zotero://select/library/items/WEBKEY12" in text
    assert "<!-- kurooto:zotero -->" in text and other.read_text() == "# Unrelated\n\nNothing about it.\n"
    assert r.zotero.link_notes() == 0  # again: nothing new
    assert env.say("/zotero links").startswith("0 notes")


def test_digest_buttons_add_with_one_tap(zot, monkeypatch):
    env, fake, r = zot
    src = FakeSources()
    env.app.settings.set("research.endpoints", {"arxiv": f"{src.base}/arxiv", "biorxiv": "x", "pubmed": "x"})
    env.app.settings.set("research.feeds", [{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}])
    env.app.secrets.set(zmod.KEY_NAME, KEY)
    env.on("research")
    r.papers()
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    rows = [b for row in sent["reply_markup"]["inline_keyboard"] for b in row if b["callback_data"].startswith("zot:")]
    assert [b["text"] for b in rows] == ["Zotero 1: Graph networks for molecules", "Zotero 2: Galaxy rotation curves"]
    assert all(len(b["callback_data"].encode()) <= 64 for b in rows)
    assert sent["text"].startswith("New papers (2):\n1. Graph networks for molecules")
    assert env.press(rows[1]["callback_data"]) == "Adding it to Zotero…"
    assert wait_for(lambda: any("added to your Zotero library" in (t or "") for t in env.fake.texts()))
    assert fake.posted[-1]["title"] == "Galaxy rotation curves"
    assert env.say("/zotero 1").startswith("Graph networks for molecules: added")
    assert egress.listed("api.zotero.org")
    src.server.shutdown()


def test_the_ai_digest_gets_buttons_for_the_papers_it_names(zot):
    env, fake, r = zot
    from kurooto.providers.base import Result, Verdict

    src = FakeSources()
    env.app.settings.set("research.endpoints", {"arxiv": f"{src.base}/arxiv", "biorxiv": "x", "pubmed": "x"})
    env.app.settings.set("research.feeds", [{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}])
    env.app.settings.set("research.max_papers", 1)
    env.app.settings.set("brain.main", "gemini")
    env.app.secrets.set("gemini.api_key", "k")
    env.app.secrets.set(zmod.KEY_NAME, KEY)
    env.on("chat", "research")
    r.papers()
    job = env.app.jobs.recent(1)[0]
    row = env.app.jobs._db.execute("select quiet, then_payload from jobs where id=?", (job.id,)).fetchone()
    assert row[0] == 1  # it comes back to Research, which sends it with the buttons
    payload = json.loads(row[1])
    then = env.app.jobs.then_actions["research.digest"]
    then(job, Result(Verdict.OK, "1. Galaxy rotation curves https://arxiv.org/abs/2610.00002 — why"), payload)
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    names = [
        b["text"] for row in sent["reply_markup"]["inline_keyboard"] for b in row if b["callback_data"][:4] == "zot:"
    ]
    assert sent["text"].startswith("1. Galaxy rotation curves") and names == ["Zotero 1: Galaxy rotation curves"]
    then(job, Result(Verdict.ERROR, "", detail="down"), payload)
    assert env.fake.texts()[-1].startswith("New papers:") and "come again next time" in env.fake.texts()[-1]
    src.server.shutdown()
