"""What 0.6.1 keeps or skips to make the dashboard and setup page quick, and that each kept thing is made again when
what it came from changes: settings' copies, the notes map's scan, the Notes step's scan, quiz notes, the process
list, the job list's index, static files' ETags, and the live stream pausing while every page is out of sight."""

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from collections import namedtuple
from pathlib import Path

import pytest

from kurooto.core import config, notesfit, vitals
from kurooto.modules.quiz import md_files
from kurooto.web import live as live_mod


# ------------------------------------------------------------------------------------------------- settings
def test_settings_copies_are_equal_and_separate(tmp_path):
    config.register_defaults("speedtest", {"list": [{"a": [1, 2]}], "n": 3, "t": (1, [2])})
    s = config.Settings(tmp_path / "settings.json")
    got = s.get("speedtest.list")
    assert got == [{"a": [1, 2]}]
    got[0]["a"].append(3)  # the caller may change what it gets
    assert s.get("speedtest.list") == [{"a": [1, 2]}]
    whole = s.all()
    whole["speedtest"]["list"].clear()
    assert s.get("speedtest.list") == [{"a": [1, 2]}] and s.get("speedtest.n") == 3
    t = s.get("speedtest")["t"]  # anything that isn't a dict or list goes through copy.deepcopy
    t[1].append(9)
    assert s.get("speedtest")["t"] == (1, [2])
    s.set("speedtest.n", 4)
    assert s.get("speedtest.n") == 4


# ------------------------------------------------------------------------------------------ the notes map
def test_the_notes_map_scan_names_notes_as_before_and_sees_changes(tmp_path):
    root = tmp_path / "notes"
    (root / "a" / "b").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "node_modules").mkdir()
    (root / "top.md").write_text("# Top\n[[a/b/deep]]\n", encoding="utf-8")
    (root / "a" / "b" / "deep.md").write_text("# Deep\n", encoding="utf-8")
    (root / "a" / "x.y.md").write_text("# Dotted\n", encoding="utf-8")
    (root / ".git" / "skip.md").write_text("# no\n", encoding="utf-8")
    (root / "node_modules" / "skip.md").write_text("# no\n", encoding="utf-8")
    g = live_mod.Graph(root)
    assert g.scan() is True
    assert sorted(n["id"] for n in g.payload["nodes"]) == ["a/b/deep", "a/x.y", "top"]  # as Path.with_suffix("")
    assert g.payload["links"] == [("top", "a/b/deep")]
    assert g.scan() is False  # nothing changed
    f = root / "a" / "b" / "deep.md"
    f.write_text("# Deep, edited\n", encoding="utf-8")
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert g.scan() is True and g.payload["changed"] == ["a/b/deep"]
    assert next(n for n in g.payload["nodes"] if n["id"] == "a/b/deep")["title"] == "Deep, edited"
    (root / "top.md").unlink()
    assert g.scan() is True and sorted(n["id"] for n in g.payload["nodes"]) == ["a/b/deep", "a/x.y"]


# ------------------------------------------------------------------------------------------------- quiz notes
def test_quiz_note_files_come_as_rglob_had_them_without_hidden_folders(tmp_path):
    root = tmp_path / "notes"
    for d in ("b/c", "a/z", ".obsidian", "a/.trash", "dir.md"):
        (root / d).mkdir(parents=True)
    for f in ("x.md", "b/c/la-quiz.md", "a/z/exam-prep.md", "a/notes.txt", ".obsidian/quiz.md", "a/.trash/quiz.md",
              "a/one.md", "b/two.md", ".hidden.md"):  # fmt: skip
        (root / f).write_text("x", encoding="utf-8")
    want = [p for p in root.rglob("*.md") if not any(x.startswith(".") for x in p.relative_to(root).parts[:-1])]
    assert md_files(root) == want  # the same files (and the folder called dir.md), in the same order
    assert md_files(root, lambda n: "quiz" in n) == [p for p in want if "quiz" in p.name]


# ------------------------------------------------------------------------------------------ the Notes step
def test_the_notes_step_keeps_its_scan_until_a_note_changes(tmp_path, monkeypatch):
    root = tmp_path / "notes"
    (root / "Daily").mkdir(parents=True)
    (root / "Daily" / "2026-10-20.md").write_text("[[a]] and [[b]]\n", encoding="utf-8")
    (root / "a.md").write_text("---\ntags: [x]\n---\n# A\n", encoding="utf-8")
    reads = []
    real = notesfit.scan
    monkeypatch.setattr(notesfit, "scan", lambda r, *a, **k: reads.append(1) or real(r, *a, **k))
    sc, fx = notesfit.scanned(root)
    assert fx == notesfit.facts(real(root)) and fx["links"]["wikilinks"] == 2 and fx["notes"] == 2
    assert notesfit.propose(root, None, sc, fx) == notesfit.propose(root)
    reads.clear()
    reads.append(1)  # the first scanned()
    fx["links"]["wikilinks"] = 99  # a copy each time
    assert notesfit.scanned(root)[1]["links"]["wikilinks"] == 2 and len(reads) == 1  # kept
    (root / "a.md").write_text("---\ntags: [x]\n---\n# A\n[[c]]\n", encoding="utf-8")
    assert notesfit.scanned(root)[1]["links"]["wikilinks"] == 3 and len(reads) == 2  # a note changed: read again
    (root / "b.md").write_text("# B\n", encoding="utf-8")
    assert notesfit.scanned(root)[1]["notes"] == 3 and len(reads) == 3  # a note added
    (root / "b.md").unlink()
    assert notesfit.scanned(root)[1]["notes"] == 2 and len(reads) == 4  # and removed
    other = tmp_path / "other"
    other.mkdir()
    assert notesfit.scanned(other)[1]["notes"] == 0 and len(reads) == 5  # another folder


# ------------------------------------------------------------------------------------------ the process list
class _P:
    def __init__(self, pid, cpu_s, threads=3):
        self.pid = pid
        self.info = {"memory_info": namedtuple("MI", "rss")(1000 * pid), "create_time": 1.0,
                     "cpu_times": namedtuple("CT", "user system")(cpu_s, 0.0)}  # fmt: skip
        self.threads = threads
        self.asked: list = []

    def as_dict(self, attrs):
        self.asked.append(tuple(attrs))
        return {"name": f"prog{self.pid}", "num_threads": self.threads}


def test_the_process_list_asks_names_and_threads_only_of_the_processes_it_lists(monkeypatch):
    procs = [_P(i, float(i)) for i in range(1, 9)]
    seen_attrs = []

    def it(attrs=None):
        seen_attrs.append(tuple(attrs or ()))
        return list(procs)

    monkeypatch.setattr(vitals.psutil, "process_iter", it)
    s = vitals.Sampler.__new__(vitals.Sampler)
    s._procs, s._share = None, {}
    rows = s.processes(own=lambda pid: "kurooto" if pid == 1 else None, n=2)
    assert seen_attrs == [("memory_info", "cpu_times", "create_time")]
    listed = {r["pid"] for r in rows}
    assert listed == {8, 7, 1}  # the two biggest, and Kurooto's own
    assert all(r["name"] == f"prog{r['pid']}" and r["threads"] == 3 for r in rows)
    assert [p.pid for p in procs if p.asked] == sorted(listed)


# ------------------------------------------------------------------------------------------ the job list
def test_the_job_list_has_an_index_on_when_jobs_came(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        for i in range(3):
            app.jobs.submit(f"question {i}", title=f"q{i}")
        assert [j.title for j in app.jobs.recent(2)] == ["q2", "q1"]
        db = sqlite3.connect(app.paths.state / "jobs.db")
        plan = " ".join(
            r[-1] for r in db.execute("explain query plan select id from jobs order by created desc limit 8")
        )
        db.close()
        assert "jobs_created" in plan and "TEMP B-TREE" not in plan
    finally:
        app.close()


# ------------------------------------------------------------------------------------------ live stream
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def test_the_stream_reads_nothing_while_every_page_is_out_of_sight(app, monkeypatch):
    lv = live_mod.Live(app)
    readings = []
    monkeypatch.setattr(lv.vitals, "snapshot", lambda: readings.append(1) or {"t": "body"})
    try:
        cid, q = lv.add()  # a new page gets a reading at once
        assert readings == [1] and lv.watched()
        assert lv.seen(cid, False) and not lv.watched()
        time.sleep(0.2)
        n = len(readings)
        lv._wake.set()  # a turn of the loop: nothing read for a page out of sight
        time.sleep(0.4)
        assert len(readings) == n
        assert lv.seen(cid, True) and lv.watched()  # back in sight: a reading now, not in up to 2 s
        deadline = time.time() + 1.5
        while len(readings) == n and time.time() < deadline:
            time.sleep(0.05)
        assert len(readings) > n
        assert lv.seen(12345, False) is False  # no such page
        lv.seen(cid, False)
        lv.drop(cid)
        assert cid not in lv.hidden and not lv.watched()
    finally:
        lv.stop()


def test_the_page_says_whether_its_in_sight(app):
    from kurooto.web.api import Api

    api = Api(app)
    assert api.post("stream/seen", {"cid": 1, "visible": False}) == (200, {"ok": False})  # no live stream yet
    app.live = live_mod.Live(app)
    try:
        cid, _ = app.live.add()
        assert api.post("stream/seen", {"cid": cid, "visible": False}) == (200, {"ok": True})
        assert cid in app.live.hidden
        assert api.post("stream/seen", {"cid": cid, "visible": True}) == (200, {"ok": True})
        assert cid not in app.live.hidden
        assert api.post("stream/seen", {"cid": "x"})[0] == 400
    finally:
        app.live.stop()


# ------------------------------------------------------------------------------------------ static files
def test_static_files_carry_an_etag_and_pages_are_never_kept(app):
    from kurooto.web.server import start

    srv = start(app, port=18790)
    try:
        url = srv.url.rstrip("/")
        with urllib.request.urlopen(url + "/static/home.js", timeout=10) as r:
            tag, body = r.headers["ETag"], r.read()
            assert r.headers["Cache-Control"] == "no-cache" and tag and len(body) > 1000
        req = urllib.request.Request(url + "/static/home.js", headers={"If-None-Match": tag})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code == 304
        req = urllib.request.Request(url + "/static/home.js", headers={"If-None-Match": '"other"'})
        with urllib.request.urlopen(req, timeout=10) as r:
            assert r.status == 200 and r.read() == body
        with urllib.request.urlopen(url + "/static/style.css", timeout=10) as r:
            assert r.headers["ETag"] != tag
        with urllib.request.urlopen(url + "/setup", timeout=10) as r:  # the page holds the key
            assert r.headers["Cache-Control"] == "no-store" and "ETag" not in r.headers
        req = urllib.request.Request(url + "/api/look", headers={"X-Kurooto": srv.token})
        with urllib.request.urlopen(req, timeout=10) as r:
            assert r.headers["Cache-Control"] == "no-store" and json.loads(r.read())
    finally:
        srv.stop()


def test_the_dashboard_tells_the_stream_when_it_is_out_of_sight():
    js = (Path(live_mod.__file__).parent / "static" / "home.js").read_text(encoding="utf-8")
    assert 'addEventListener("visibilitychange", saySeen)' in js and 'api("stream/seen"' in js
