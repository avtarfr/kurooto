"""Systems and the Notes map on the Android app (calls/views.py, 0.7.0), without a call line: what each copy holds (the
notes map's titles and links, cut to size, never what a note says; SYSTEMS' features and health, today as times only),
sealed once and its key for each Android phone alone (line.py v1), handed over in parts and only when the notes
changed, Systems only while a phone watches, and calls.views off by default and dropping the line's copies. Also: the
shared drawing code stays within what Android 6's WebView can run. The Worker's side is in
tests/integration/test_phone_views_line.py; the phone's opening of a copy in android/test/ViewsTest.java."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import kurooto
from kurooto.modules.calls import line, views
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)

VECTORS = Path(__file__).parent.parent / "fixtures" / "call-vectors.json"
STATIC = Path(kurooto.__file__).parent / "web" / "static"
BODY_TEXT = "the-quiet-eigenvalue-sentence"


class Line:
    """The call line's admin side, as views.py sees it: it puts the parts back together."""

    def __init__(self, devices):
        self.devices, self.ops, self.kept = devices, [], {}

    async def admin(self, op, **kw):
        self.ops.append((op, kw))
        if op == "devices":
            return {"devices": self.devices}
        if op == "view-put" and not kw.get("off"):
            k = self.kept.setdefault((kw["view"], kw["rev"]), {"parts": [], "keys": kw.get("keys")})
            k["parts"].append(kw["data"])
        return {"ok": True}

    def puts(self, kind=None):
        return [kw for op, kw in self.ops if op == "view-put" and (kind is None or kw.get("view") == kind)]

    def opened(self, phone_key, kind):
        (kind_, rev), k = [(key, v) for key, v in self.kept.items() if key[0] == kind][-1]
        import base64

        blob = b"".join(base64.b64decode(p) for p in k["parts"])
        got = line.open_v1(phone_key, k["keys"]["abcd1234"], blob)
        assert got and got[0] == kind and got[1] == rev
        return json.loads(got[2]), k


def notes(root: Path, n: int = 30) -> None:
    for i in range(n):
        p = root / "zettel" / f"c{i}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# Concept {i}\n\n{BODY_TEXT}\n\n[[zettel/c{(i + 1) % n}]] [[maps/index]]\n", encoding="utf-8")
    (root / "maps").mkdir(parents=True, exist_ok=True)
    (root / "maps" / "index.md").write_text(
        "# Home\n\n" + " ".join(f"[[zettel/c{i}]]" for i in range(n)), encoding="utf-8"
    )


@pytest.fixture
def v(phone):  # noqa: F811
    key = ec.generate_private_key(ec.SECP256R1())
    pub = line.b64url(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
    phone.key, phone.views = key, phone.calls.views
    phone.line = Line([{"id": "abcd1234", "kind": "android", "seal": pub}, {"id": "0000beef", "kind": "web"}])
    notes(phone.app.workspace)
    return phone


def test_off_by_default_and_documented(v):
    assert v.app.settings.get("calls.views") is False and not v.views.on()
    asyncio.run(v.views.push(v.line))
    assert v.line.ops == []  # never on: nothing said to the line
    guide = (Path(__file__).parents[2] / "docs" / "SETTINGS_GUIDE.md").read_text(encoding="utf-8")
    assert "calls.views" in guide


def test_the_notes_map_goes_sealed_for_each_android_phone_without_what_notes_say(v):
    v.app.settings.set("calls.views", True)
    asyncio.run(v.views.push(v.line))
    (put,) = v.line.puts("notes")
    assert list(put["keys"]) == ["abcd1234"]  # the web app has no key of its own
    assert BODY_TEXT not in json.dumps(v.line.ops)  # sealed: the line sees nothing
    snap, _ = v.line.opened(v.key, "notes")
    ids = [n[0] for n in snap["nodes"]]
    assert (
        "maps/index" in ids
        and "zettel/c3" in ids
        and [n[1] for n in snap["nodes"] if n[0] == "zettel/c3"] == ["Concept 3"]
    )
    assert BODY_TEXT not in json.dumps(snap)  # titles and links, never what a note says
    assert len(snap["links"]) == 90 and all(isinstance(a, int) for a, b in snap["links"])
    assert snap["cut"] == {"notes": 0, "links": 0} and snap["made"] >= int(time.time()) - 5
    asyncio.run(v.views.push(v.line))
    assert len(v.line.puts("notes")) == 1  # unchanged: not sent again


def test_changed_notes_go_again_but_not_more_often_than_every_few_minutes(v, monkeypatch):
    v.app.settings.set("calls.views", True)
    asyncio.run(v.views.push(v.line))
    (v.app.workspace / "zettel" / "new.md").write_text("# Brand new\n\n[[maps/index]]\n", encoding="utf-8")
    asyncio.run(v.views.push(v.line))
    assert len(v.line.puts("notes")) == 1  # changed, but it just went: the next state push takes it
    monkeypatch.setattr(views, "NOTES_MIN_S", 0)
    asyncio.run(v.views.push(v.line))
    assert len(v.line.puts("notes")) == 2
    snap, _ = v.line.opened(v.key, "notes")
    assert "zettel/new" in [n[0] for n in snap["nodes"]]


def test_a_big_folder_is_cut_to_size_best_linked_first():
    nodes = [{"id": f"n{i:04d}", "title": f"Note {i}", "mtime": i, "words": 1} for i in range(40)]
    links = [["n0000", f"n{i:04d}"] for i in range(1, 40)] + [[f"n{i:04d}", f"n{i + 1:04d}"] for i in range(1, 20)]
    research = {"p": {"name": "A project", "topics": ["n0001", "gone"]}}
    snap = views.trim_notes(
        {"nodes": nodes, "links": links, "research": research, "layout": {"research": "maps/r"}}, 10, 12
    )
    ids = [n[0] for n in snap["nodes"]]
    assert len(ids) == 10 and "n0000" in ids and ids == sorted(ids)  # the hub stays; in path order
    assert len(snap["links"]) == 12 and snap["cut"] == {"notes": 30, "links": len(links) - 12}
    assert all(0 <= a < 10 and 0 <= b < 10 for a, b in snap["links"])
    assert snap["research"]["p"]["topics"] == (["n0001"] if "n0001" in ids else [])
    assert snap["total"] == {"notes": 40, "links": len(links)}


def test_a_copy_too_big_for_one_part_goes_in_parts(v, monkeypatch):
    monkeypatch.setattr(views, "PART", 1000)
    v.app.settings.set("calls.views", True)
    notes(v.app.workspace, 200)
    asyncio.run(v.views.push(v.line))
    puts = v.line.puts("notes")
    assert len(puts) > 2 and [p["part"] for p in puts] == list(range(len(puts)))
    assert "keys" in puts[0] and "keys" not in puts[1] and all(p["parts"] == len(puts) for p in puts)
    snap, _ = v.line.opened(v.key, "notes")
    assert len(snap["nodes"]) == 201


def test_turned_off_the_line_drops_its_copies_once(v):
    v.app.settings.set("calls.views", True)
    asyncio.run(v.views.push(v.line))
    v.app.settings.set("calls.views", False)
    asyncio.run(v.views.push(v.line))
    asyncio.run(v.views.push(v.line))
    offs = [kw for op, kw in v.line.ops if op == "view-put" and kw.get("off")]
    assert len(offs) == 1
    v.app.settings.set("calls.views", True)  # on again: the map goes at once
    asyncio.run(v.views.push(v.line))
    assert len(v.line.puts("notes")) == 2


def test_systems_holds_what_systems_draws_and_what_needs_a_look(v, monkeypatch):
    v.on("deadlines")
    snap = v.views.systems_snapshot()
    ids = [c["id"] for c in snap["cells"]]
    assert "calls" in ids and "deadlines" in ids and {"act", "events", "title"} <= set(snap["cells"][0])
    f = {x["id"]: x for x in snap["features"]}
    assert f["calls"]["title"] == "Phone calls" and {"down", "idle", "last", "next", "proc"} <= set(f["calls"])
    assert all(set(i) <= {"at", "end", "kind", "state"} for i in snap["today"]["items"])  # no names on the clock
    assert 0 <= snap["sys"]["cpu"] <= 1 and snap["name"]
    monkeypatch.setattr(
        v.app.health,
        "board",
        lambda: [{"id": "calls", "title": "Phone calls", "detail": "the call line isn't connected"}],
    )
    v.views.vitals = None
    snap = v.views.systems_snapshot()
    f = {x["id"]: x for x in snap["features"]}
    assert f["calls"]["health"] == "Phone calls: the call line isn't connected"
    assert snap["health"] == [{"id": "calls", "title": "Phone calls", "detail": "the call line isn't connected"}]


class Connector:
    """The connector as views.py's watching uses it: a running loop, a socket, admin()."""

    def __init__(self, ln):
        self.ln, self.ws, self.pokes = ln, object(), 0
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()

    async def admin(self, op, **kw):
        return await self.ln.admin(op, **kw)

    def poke(self):
        self.pokes += 1


def test_systems_goes_live_only_while_a_phone_watches(v, monkeypatch):
    monkeypatch.setattr(views, "WATCH_S", 1.2)
    monkeypatch.setattr(views, "SYSTEMS_S", 0.3)  # (a copy every 0.5 s at the quickest)
    c = Connector(v.line)
    v.calls.connector = c
    try:
        assert v.views.watch() is False  # off: nothing
        v.app.settings.set("calls.views", True)
        v.calls.on_event({"name": "views_watch", "device": "abcd1234", "kind": "systems"})  # from the call line
        time.sleep(0.3)
        assert v.views.looping and len(v.line.puts("systems")) == 1
        snap, _ = v.line.opened(v.key, "systems")
        assert snap["kind"] == "systems" and snap["cells"]
        deadline = time.time() + 6
        while v.views.looping and time.time() < deadline:
            time.sleep(0.1)
        assert not v.views.looping  # no word for WATCH_S: it stops
        n = len(v.line.puts("systems"))
        assert 2 <= n <= 5
        time.sleep(0.8)
        assert len(v.line.puts("systems")) == n
        assert any(e["kind"] == "phone_views_watching" for e in v.app.events.tail(20))
    finally:
        c.loop.call_soon_threadsafe(c.loop.stop)


def test_turning_it_on_or_off_reaches_the_line_soon(v):
    c = Connector(v.line)
    v.calls.connector = c
    try:
        v.views.on_event({"kind": "setting_changed", "key": "calls.views"})
        v.views.on_event({"kind": "setting_changed", "key": "calls.today"})
        assert c.pokes == 1
    finally:
        c.loop.call_soon_threadsafe(c.loop.stop)


def test_v1_matches_the_shared_vectors():
    d = json.loads(VECTORS.read_text(encoding="utf-8"))
    s1, v1 = d["s1"], d["v1"]
    mine = ec.derive_private_key(int(s1["phone_priv_hex"], 16), ec.SECP256R1())
    blob = line.unb64url(v1["blob"])
    assert line.open_v1(mine, v1["head_sealed"], blob) == ("notes", v1["rev"], v1["plain"])
    assert line.open_s1(mine, v1["head_sealed"]) == v1["head"]
    assert line.open_v1(mine, v1["head_sealed"], blob[:-1] + bytes([blob[-1] ^ 1])) is None  # changed
    assert line.open_v1(ec.generate_private_key(ec.SECP256R1()), v1["head_sealed"], blob) is None  # another phone
    key, packed = line.pack_v1(v1["plain"], bytes.fromhex(v1["key_hex"]), bytes.fromhex(v1["blob_nonce_hex"]))
    assert line.open_f1(key, packed) is not None and line.head_v1("notes", 1, key, packed).startswith("v1 notes 1 ")


# ------------------------------------------------------------------------------------------- the drawing code
def test_the_dashboard_loads_the_shared_drawing_code_before_its_own():
    html = (STATIC / "home.html").read_text(encoding="utf-8")
    order = [
        html.index(f"/static/{f}") for f in ("views/common.js", "views/systems.js", "views/notesmap.js", "home.js")
    ]
    assert order == sorted(order)
    page = (STATIC / "views" / "phone.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in page and "script-src 'self'" in page
    home = (STATIC / "home.js").read_text(encoding="utf-8")
    assert "class Board extends Body" in home and "class Notes extends Mind" in home
    assert "class Body" not in home.replace("class Board extends Body", "")  # one copy of the drawing


def test_the_phone_page_has_no_colours_of_its_own():
    css = (STATIC / "views" / "phone.css").read_text(encoding="utf-8")
    js = (STATIC / "views" / "phone.js").read_text(encoding="utf-8")
    import re

    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", css) and "color-mix(" not in css
    assert not re.search(r"[\"']#[0-9a-fA-F]{6}[\"']", js)


@pytest.mark.skipif(
    not (STATIC.parents[1] / "data" / "worker" / "node_modules" / "esbuild").is_dir() or not shutil.which("node"),
    reason="needs the Worker's packages (npm ci in src/kurooto/data/worker), for esbuild",
)
@pytest.mark.parametrize("name", ["common.js", "systems.js", "notesmap.js", "phone.js"])
def test_the_drawing_code_runs_in_android_6s_webview(name):
    """The phone app's WebView can be as old as Chrome 58 (ViewsActivity.MIN_CHROME): esbuild's output for that
    target is the same as for the newest only if the file needs nothing newer (?., ??, object spread, catch without a
    binding, class fields...)."""
    esbuild = STATIC.parents[1] / "data" / "worker" / "node_modules" / ".bin" / "esbuild"
    src = (STATIC / "views" / name).read_text(encoding="utf-8")

    def build(target):
        # (esbuild counts template literals as Chrome 62's, for a bug in tagged ones, which these files don't use)
        args = ["--loader=js", f"--target={target}", "--supported:template-literal=true", "--log-level=error"]
        r = subprocess.run([str(esbuild), *args], input=src, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return r.stdout

    assert build("chrome58") == build("esnext")
