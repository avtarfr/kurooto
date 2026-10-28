"""The dense dashboard and the btop-like `kurooto top`: the shared vitals sampler (core/vitals.py), the dashboard's new
status fields (web/live.py: processes, features' own programs, today, what's due, the AI's corner, study, projects,
events today), GET /api/board, look.layout, and the terminal board's drawing."""

import datetime as dt
import json
import os
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import pytest

from kurooto.core import vitals
from kurooto.core.vitals import Sampler, own_pids

Nic = namedtuple("Nic", "bytes_sent bytes_recv packets_sent packets_recv errin errout dropin dropout")
Stat = namedtuple("Stat", "isup duplex speed mtu")
Battery = namedtuple("Battery", "percent secsleft power_plugged")


# ================================================================================================ the sampler
def test_a_reading_has_every_part_and_keeps_history(tmp_path):
    s = Sampler(tmp_path / "hardware.json", history=5)
    for _ in range(7):
        r = s.sample()
    assert 0 <= r["cpu"] <= 1 and r["threads"] == len(r["cores"]) >= 1
    assert len(r["hist"]["cpu"]) == 5 and len(r["core_hist"]) == r["threads"] and len(r["core_hist"][0]) == 5
    m = r["mem"]
    assert m["total"] > 0 and 0 < m["used"] <= m["total"] and m["available"] <= m["total"] and 0 <= m["pct"] <= 1
    for key in ("freq", "load", "temps", "fans", "swap", "gpu", "net", "disks", "io", "battery", "uptime"):
        assert key in r, key
    json.dumps(r)  # all of it goes over the page's stream as it is


def test_what_a_mac_or_windows_computer_cant_tell_is_left_out(tmp_path, monkeypatch):
    monkeypatch.delattr(vitals.psutil, "sensors_temperatures", raising=False)
    monkeypatch.delattr(vitals.psutil, "sensors_fans", raising=False)
    monkeypatch.setattr(vitals.psutil, "sensors_battery", lambda: None)
    monkeypatch.setattr(vitals.psutil, "cpu_freq", lambda: None, raising=False)  # macOS on Apple chips has none
    monkeypatch.setattr(vitals.proc, "which", lambda name, *a: None)  # no nvidia-smi
    monkeypatch.setattr(vitals, "amdgpu", lambda: None)
    r = Sampler(tmp_path / "hw.json").sample(force=True)
    assert r["temps"] == {} and r["fans"] == [] and r["battery"] is None and r["freq"] is None and r["gpu"] is None


def test_the_graphics_card_from_nvidia_smi_and_never_woken(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(vitals.proc, "which", lambda name, *a: "/usr/bin/nvidia-smi")

    def run(args, **kw):
        calls.append(args)
        return vitals.proc.Result(0, "NVIDIA GeForce RTX 4060 Laptop GPU, 12, 800, 8188, 48, 4.20, 80.00\n", "")

    monkeypatch.setattr(vitals.proc, "run", run)
    monkeypatch.setattr(vitals, "nvidia_asleep", lambda: False)
    g = vitals.nvidia()
    assert g["util"] == 0.12 and g["mem_total"] == 8188 * 1024**2 and g["temp"] == 48 and g["watts_max"] == 80
    monkeypatch.setattr(vitals, "nvidia_asleep", lambda: True)  # a laptop's sleeping card: nvidia-smi isn't run
    assert vitals.nvidia() == {"asleep": True} and len(calls) == 1
    s = Sampler(tmp_path / "hw.json")
    r = s.sample(force=True)
    assert r["gpu"] == {"asleep": True} and r["hist"]["gpu"] == [0.0]


def test_the_charger_from_the_power_supply_when_psutil_cant_tell(tmp_path, monkeypatch):
    monkeypatch.setattr(vitals.psutil, "sensors_battery", lambda: Battery(81.4, -1, None))
    monkeypatch.setattr(vitals, "mains_online", lambda: True)
    b = Sampler(tmp_path / "hw.json").sample()["battery"]
    assert b["ac"] is True and b["pct"] == 81.4 and b["secs"] is None


def test_the_main_connection_is_the_busy_one_not_loopback_or_a_bridge(tmp_path, monkeypatch):
    counters = {
        "lo": Nic(10**9, 10**9, 0, 0, 0, 0, 0, 0),
        "docker0": Nic(5, 5, 0, 0, 0, 0, 0, 0),
        "wlan0": Nic(2_000, 50_000, 0, 0, 0, 0, 0, 0),
        "eth0": Nic(100, 1_000, 0, 0, 0, 0, 0, 0),
    }
    monkeypatch.setattr(vitals.psutil, "net_io_counters", lambda pernic=False: dict(counters))
    monkeypatch.setattr(vitals.psutil, "net_if_stats", lambda: {k: Stat(True, 2, 0, 1500) for k in counters})
    s = Sampler(tmp_path / "hw.json")
    assert s.sample()["net"]["dev"] == "wlan0"
    counters["eth0"] = Nic(100 + 10**6, 1_000 + 10**7, 0, 0, 0, 0, 0, 0)  # a cable now carries the traffic
    time.sleep(0.2)
    n = s.sample()["net"]
    assert n["dev"] == "eth0" and n["rx"] > 10**6 and n["rx_total"] == 1_000 + 10**7 and n["all_rx"] >= n["rx"]


def test_processes_busiest_and_biggest_with_kuroots_own_marked(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        s = Sampler(tmp_path / "hw.json")
        s.processes()
        own = own_pids(os.getpid())
        assert own[os.getpid()] == "kurooto" and child.pid in own
        rows = s.processes(own=own.get, n=5)
        assert len({r["pid"] for r in rows}) == len(rows) <= 10 and all(r["pid"] != 0 for r in rows)
        big = max(rows, key=lambda r: r["mem"])
        assert {"pid", "name", "cpu", "mem", "mem_pct", "threads", "own"} <= set(big)
        everyone = s.processes(own=own.get, n=100000)
        assert next(r for r in everyone if r["pid"] == os.getpid())["own"] == "kurooto"
        assert next(r for r in everyone if r["pid"] == child.pid)["own"]
    finally:
        child.kill()
        child.wait()
    assert own_pids(None) == {} and own_pids(2**31 - 7) == {}


# ======================================================================================= the dashboard's fields
@pytest.fixture
def repo(tmp_path):
    """A git project with one commit pushed and two not."""
    if not __import__("shutil").which("git"):
        pytest.skip("git isn't installed")
    env = {**os.environ, "GIT_AUTHOR_NAME": "Sam", "GIT_AUTHOR_EMAIL": "s@example.com",
           "GIT_COMMITTER_NAME": "Sam", "GIT_COMMITTER_EMAIL": "s@example.com"}  # fmt: skip
    bare, work = tmp_path / "origin.git", tmp_path / "denoise-mini"

    def git(*a, cwd=work):
        subprocess.run(["git", *a], cwd=cwd, env=env, check=True, capture_output=True)

    git("init", "-q", "--bare", str(bare), cwd=tmp_path)
    work.mkdir()
    git("init", "-q", "-b", "main")
    (work / "a.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-qm", "one")
    git("remote", "add", "origin", str(bare))
    git("push", "-qu", "origin", "main")
    for i in range(2):
        (work / f"b{i}.py").write_text("y = 2\n")
        git("add", ".")
        git("commit", "-qm", f"more {i}")
    (work / "a.py").write_text("x = 3\n")
    return work


def test_the_status_stream_carries_the_dense_boards_fields(env, repo, monkeypatch):
    from kurooto.core.clock import now
    from kurooto.web.live import Vitals

    app = env.app
    env.on("reminders", "deadlines", "subjects", "study")
    app.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": []}])
    day = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[now().weekday()]
    app.settings.set(
        "subjects.timetable", [{"day": day, "start": "00:00", "end": "23:59", "subject": "linear-algebra"}]
    )
    app.modules["study"].add("linear-algebra", 3600)
    app.modules["deadlines"].add("Problem set 5", now() + dt.timedelta(hours=30))
    app.modules["deadlines"].add("Lab report", now() - dt.timedelta(hours=2))
    tomorrow = dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(0)).timestamp()
    soon = min(time.time() + 120, tomorrow - 1)
    app.scheduler.at(soon, "reminders.fire", {"what": "stretch"}, key="reminders:test")
    app.settings.set("look.projects", [str(repo), str(repo.parent / "missing")])
    app.events.emit("reminder_fired", n=1)
    v = Vitals(app)
    v.snapshot()
    snap = v.snapshot()
    json.dumps(snap, default=str)
    sys_ = snap["sys"]
    assert {"hist", "memx", "net", "disks", "threads", "load", "power"} <= set(sys_) and sys_["hist"]["cores"]
    assert 0 <= sys_["mem"] <= 1 and sys_["cores"]  # the roomy layout's fields are still there
    assert any(p["own"] == "kurooto" and p["pid"] == os.getpid() for p in snap["procs"])
    assert snap["core"]["mem"] > 0 and snap["events_today"] >= 1
    rem = next(f for f in snap["features"] if f["id"] == "reminders")
    assert rem["events"] == 1 and rem["last"] is not None and rem["next"] and not rem["down"]
    items = snap["today"]["items"]
    assert any(x["kind"] == "class" and x["what"] == "Linear Algebra" and x["state"] == "now" for x in items)
    assert any(x["what"] == "stretch" for x in items) and not any("refresh" in x["what"] for x in items)
    due = {d["title"]: d["hours"] for d in snap["deadlines"]}
    assert due["Lab report"] < 0 < due["Problem set 5"] and snap["deadlines_open"] == 2
    assert snap["study"] == [{"name": "Linear Algebra", "seconds": 3600}]
    p = snap["projects"][0]
    assert p["name"] == "denoise-mini" and p["ahead"] == 2 and p["dirty"] == 1 and p["last"] and p["week"] == 3
    assert snap["projects"][1] == {"name": "missing", "last": None, "ahead": None, "dirty": None, "week": None}
    assert snap["link"] is None and snap["agent"]["models"] is None and snap["agent"]["scheduled"] >= 1


def test_a_feature_names_its_programs_and_its_cell_shows_them_or_that_none_runs(env):
    from kurooto.web.live import Vitals

    app = env.app
    env.on("reminders", "deadlines")
    app.modules["reminders"].processes = (Path(sys.executable).name[:12],)  # this test's own python
    app.modules["deadlines"].processes = ("no-such-program-xyz", "bots/never.js")
    try:
        feats = {f["id"]: f for f in Vitals(app).board()["features"]}
    finally:
        del app.modules["reminders"].processes, app.modules["deadlines"].processes
    assert (
        feats["reminders"]["proc"]["mem"] > 0
        and feats["reminders"]["proc"]["n"] >= 1
        and not feats["reminders"]["down"]
    )
    assert feats["deadlines"]["down"] is True and feats["deadlines"]["proc"] is None
    assert feats["telegram"]["down"] is False  # it names no programs: never "down"


def test_board_api_and_the_layout_setting(env):
    from kurooto.web.server import start
    from tests.unit.test_dashboard import call

    app = env.app
    srv = start(app, port=18960)
    try:
        code, b = call(srv, "/api/board")
        assert code == 200 and {"features", "today", "deadlines", "projects", "events_today", "core"} <= set(b)
        assert call(srv, "/api/board", token=False)[0] == 401
        app.settings.set("setup.done", True)

        def page():
            import urllib.request

            with urllib.request.urlopen(srv.url) as r:
                return r.read().decode()

        assert 'data-layout="dense"' in page()  # the default
        assert call(srv, "/api/settings", {"key": "look.layout", "value": "roomy"})[1] == {"ok": True}
        assert 'data-layout="roomy"' in page()
        app.settings.set("look.layout", '"><script>')  # anything else is the default, never written into the page
        assert 'data-layout="dense"' in page() and '<script>"' not in page()
    finally:
        srv.stop()


def test_the_page_has_both_layouts_and_keeps_the_tabs(env):
    from importlib import resources

    static = resources.files("kurooto.web") / "static"
    js = (static / "home.js").read_text(encoding="utf-8")
    css = (static / "home.css").read_text(encoding="utf-8")
    assert "window.innerWidth >= 1280" in js and "function renderBoard" in js and "function showDense" in js
    for tab in ("activity", "jobs", "schedule", "features", "phone", "research", "about", "settings"):
        assert f"{tab}:" in js.split("const DLABEL")[1].split("\n")[0], tab  # every page is in the terminal's border
    assert 'api("say", { text })' in js and "kurooto:palette" in js
    assert "body.dense" in css and "#" not in "".join(
        ln for ln in css.splitlines() if "body.dense" in ln and "color:" in ln
    )


def test_roomy_places_every_pane_by_name_so_none_collapses(env):
    """0.8.16: under 1280 px (half a 1920 screen) roomy's old three-column grid pushed NOTES and the tabs to extra rows
    and left STATUS, SYSTEMS and BRAIN no height. Every pane now has a named area, the areas have as many rows as the
    grid has, and the being board shows the being in roomy too, where SYSTEMS and BRAIN were."""
    import re
    from importlib import resources

    static = resources.files("kurooto.web") / "static"
    css = (static / "home.css").read_text(encoding="utf-8")
    js = (static / "home.js").read_text(encoding="utf-8")
    roomy = css.split("roomy's board (0.8.16)")[1]
    for pane, area in (("status", "status"), ("systems", "systems"), ("brain", "brain"), ("vault", "notes"),
                       ("tabs", "tabs"), ("being", "being"), ("study", "study")):  # fmt: skip
        assert f"body.home:not(.dense) #pane-{pane} {{ grid-area: {area}; }}" in roomy, pane

    def rule(sel, text):
        return text.split(sel + " {", 1)[1].split("}", 1)[0]

    for sel, names in (("body.home:not(.dense) .grid", {"status", "notes", "systems", "brain", "tabs"}),
                       ("body.home.being-board:not(.dense) .grid", {"being", "notes", "status", "tabs"})):  # fmt: skip
        for text in (roomy, roomy.split("@media (max-width: 900px)")[1]):  # wide and phone-narrow
            r = rule(sel, text)
            rows = re.findall(r'"([^"]+)"', r.split("grid-template-areas:")[1].split(";")[0])
            assert {n for row in rows for n in row.split()} == names, (sel, rows)
            if "grid-template-rows:" in r:  # no pane spills into an implicit row
                tracks = re.sub(r"\([^)]*\)", "x", r.split("grid-template-rows:")[1].split(";")[0]).split()
                assert len(tracks) == len(rows), (sel, tracks, rows)
    hid = "body.home.being-board:not(.dense) #pane-systems, body.home.being-board:not(.dense) #pane-brain"
    assert hid + " { display: none; }" in roomy
    assert "body.home.being-board:not(.dense) #pane-being { display: block;" in roomy
    # the being board is no longer dense-only, and roomy mounts it
    assert 'const beingBoard = () => BOARD === "being" && !STUDY && !(DENSE && MAX);' in js
    roomy_js = js.split("if (!DENSE) { // roomy:")[1].split("talkShow(); return;")[0]
    for part in ("mountBeing()", "stopBeing()", 'classList.toggle("being-board", being)'):
        assert part in roomy_js, part


def test_a_narrow_window_and_back_shows_what_the_board_showed():
    """0.8.17: making the window narrow (roomy) and wide again (dense) opened the tab roomy last had, often Features,
    over a board that had no page open, and dropped a page roomy has but the old list didn't (Chat, AI jobs...). The
    dense board's page (or none) is kept when the window goes narrow and comes back; a tab picked while it was narrow
    forgets it, and then a roomier one still opens over the board."""
    from importlib import resources

    js = (resources.files("kurooto.web") / "static" / "home.js").read_text(encoding="utf-8")
    assert "let LEFT = null;" in js
    show = js.split("function showTab(name) {")[1].split("\n}")[0]
    assert "tab = name; LEFT = null;" in show  # a tab picked in roomy
    lay = js.split("function applyLayout(force = false) {")[1].split("\n}")[0]
    assert 'const keep = force ? null : DENSE ? PAGE : LEFT ? LEFT.page : ["features",' in lay
    # set after roomy's showTab (which clears it), before the dense board opens the page again
    assert (
        lay.index("showTab(tab")
        < lay.index("LEFT = !force && !DENSE ? { page: keep } : null;")
        < lay.index("if (DENSE && keep) openPage(keep);")
    )


# ================================================================================================= kurooto top
def board_data(tmp_path):
    from kurooto import top

    b = top.Board(SimpleNamespace(state=tmp_path, config=tmp_path))
    data = b.collect(force=True)
    data["kurooto"].update(
        running=True,
        pid=4242,
        url="http://127.0.0.1:8770/",
        on=["Reminders", "Deadlines", "Local AI models"],
        board={
            "features": [
                {"id": "local_models", "title": "Local AI models",
                 "proc": {"cpu": 0.12, "mem": 4 * 1024**3, "threads": 21, "up": 4000}},
                {"id": "persona", "title": "Persona bot", "proc": None, "down": True},
                {"id": "telegram", "title": "Telegram", "proc": None, "down": False},
            ],
            "core": {"cpu": 0.01, "mem": 60 * 1024**2, "threads": 13, "up": 7200},
            "link": {"connected": True, "beat": 12},
            "today": {"items": [{"at": "09:00", "end": "09:50", "what": "Linear Algebra", "kind": "class",
                                 "state": "now"},
                                {"at": "21:00", "what": "evening check-in", "kind": "job", "state": "next"}],
                      "focus": None, "quiet": "18:00"},
            "deadlines": [{"title": "Lab report", "hours": -2.0}, {"title": "Problem set 5", "hours": 30.0}],
            "deadlines_open": 2,
            "agent": {"models": [{"name": "small-model", "vram": 2 * 1024**3}]},
            "calls": [],
            "study": [{"name": "Linear Algebra", "seconds": 3600}, {"name": "Signals", "seconds": 1800}],
            "projects": [{"name": "denoise-mini", "last": time.time() - 600, "ahead": 2, "dirty": 1, "week": 3}],
            "events_today": 9,
        },
        events_today=9,
        beats=[time.time() - 30, time.time() - 5],
    )  # fmt: skip
    return data


def test_top_draws_the_machine_like_btop_and_kurooto_beside_it(tmp_path):
    from kurooto import top

    data = board_data(tmp_path)
    for w, h in ((200, 60), (150, 50), (100, 80), (60, 40), (30, 10)):
        lines = top.render(data, w, h)
        assert lines and all(top.vlen(ln) == max(30, w) for ln in lines) and len(lines) <= max(10, h), (w, h)
    flat = "\n".join(top.ANSI.sub("", ln) for ln in top.render(data, 200, 70, colour=False))
    for part in (
        "┤CPU├", "┤MEM├", "┤NET├", "┤DISKS├", "┤PROCESSES├", "┤KUROOTO├", "┤TODAY├", "┤DUE├", "┤STUDY TODAY├",
        "┤PROJECTS├", "EVENTS TODAY 9", "● call line", "heartbeat 12s", "Local AI models", "Persona bot",
        "not running", "overdue 2h", "Linear Algebra", "now", "no calls until 18:00", "small-model", "↑2 to push",
        "+3 this week", "✦ kurooto", "threads",
    ):  # fmt: skip
        assert part in flat, part
    ascii_only = "\n".join(top.render(data, 200, 70, colour=False, unicode=False))
    assert ascii_only.isascii() and "\x1b[" not in ascii_only and "[CPU]" in ascii_only
    by_mem = top.ANSI.sub("", "\n".join(top.render(data, 200, 70, colour=False, sort="mem")))
    assert "by mem" in by_mem


def test_top_colours_are_the_palettes_at_the_terminals_depth(tmp_path, monkeypatch):
    from kurooto import top

    data = board_data(tmp_path)
    true = "\n".join(top.render(data, 150, 40, depth=24))
    assert "\x1b[38;2;" in true and "\x1b[38;5;" not in true
    assert "\x1b[38;5;" in "\n".join(top.render(data, 150, 40, depth=256))
    eight = "\n".join(top.render(data, 150, 40, depth=8))
    assert "\x1b[38;" not in eight and "\x1b[3" in eight
    for envs, want in (({"COLORTERM": "truecolor"}, 24), ({"TERM": "xterm-256color"}, 256), ({"TERM": "linux"}, 8)):
        for k in ("COLORTERM", "WT_SESSION", "TERM_PROGRAM", "TERM"):
            monkeypatch.delenv(k, raising=False)
        for k, v in envs.items():
            monkeypatch.setenv(k, v)
        if sys.platform != "win32":
            assert top.colour_depth() == want, envs
    pal = top.colours(None)
    assert pal["bg"].startswith("#") and len(pal) >= 15


def test_braille_graphs_rise_with_the_value(tmp_path):
    from kurooto import top

    st = top.Style(False, True)
    full, empty = top.braille(st, [1.0] * 20, 10, 2), top.braille(st, [0.0] * 20, 10, 2)
    assert all(set(r) == {"⣿"} for r in full) and all(set(r) == {" "} for r in empty)
    half = top.braille(st, [0.5] * 20, 10, 2)
    assert set(half[0]) == {" "} and set(half[1]) == {"⣿"}
    assert set(top.braille(st, [1.0] * 4, 2, 1, down=True)[0]) == {"⣿"}
    assert top.trace(st, [time.time() - 1], 10, time.time()) != top.trace(st, [], 10, time.time())
