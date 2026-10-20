"""0.5.1: a stuck AI request never holds up the queue. Two lanes (yours and background work), a watchdog that ends a
stuck request with a plain message, cancelling (/jobs, the dashboard, `kurooto jobs --cancel`) that stops the
request's program and everything it started; Google turning on with its sign-in, and /commands of features that are
off saying how to turn them on instead of going to the AI."""

from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from kurooto import providers
from kurooto.app import App
from kurooto.core import proc
from kurooto.core.clock import now
from kurooto.modules.base import Incoming
from kurooto.modules.calls.tools import Tool
from kurooto.providers.agy import Agy
from kurooto.providers.base import Result, Task, Verdict
from kurooto.providers.openai_compat import OpenAICompat
from tests.fakes.google import FakeGoogle
from tests.fakes.openai import FakeOpenAI

TOOL = Tool("noop", "does nothing", lambda a: "ok")
CLIENT = json.dumps({"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "csec"}})


class Gate:
    """A brain that holds a request until it's let go (a dropped connection, a request that never comes back)."""

    id, label, kind = "gate", "Gate", "api"

    def __init__(self):
        self.go, self.entered, self.where = threading.Event(), threading.Event(), "run"

    def available(self):
        if self.where == "available":  # stuck before any AI ran
            self.entered.set()
            self.go.wait(30)
        return True, ""

    def run(self, task):
        if task.prompt.startswith("quick"):
            return Result(Verdict.OK, f"done: {task.prompt}")
        self.entered.set()
        self.go.wait(30)
        return Result(Verdict.OK, "late answer")


@pytest.fixture
def q(env, monkeypatch):
    """The paired assistant with the Gate brain as its AI."""
    gate = Gate()
    monkeypatch.setattr(providers, "build", lambda a, w: gate if w == "gate" else None)
    env.app.settings.set("brain.main", "gate")
    env.app.power.current = "normal"
    yield env, gate
    gate.go.set()


def until(cond, secs: float = 10.0) -> bool:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def thread_of(app, lane):
    return app.jobs._lanes[lane][1]


# ------------------------------------------------------------------------------------------------ the lanes
def test_your_request_never_waits_behind_a_stuck_background_job(q):
    env, gate = q
    app = env.app
    seen = []
    app.jobs.then_actions["t.seen"] = lambda job, result, payload: seen.append((job.id, result.verdict))
    bg = app.jobs.submit("Revision pack: Lab", quiet=True, lane="bg", then="t.seen")
    assert (
        app.jobs.get(bg).lane == "bg" and app.jobs.submit("x", background=True) and app.jobs.active()[-1].lane == "bg"
    )
    app.jobs._tick()  # the background lane takes the pack, which hangs
    assert gate.entered.wait(5) and app.jobs.get(bg).status == "running"
    assert app.jobs.get(bg).brain == "gate"  # which AI is at work shows while it runs, not only at the end
    mine = app.jobs.submit("quick: what's due?", reply_to=1)
    assert app.jobs.get(mine).lane == "you"
    app.jobs._tick()
    thread_of(app, "you").join(5)
    assert app.jobs.get(mine).status == "ok" and env.fake.texts()[-1].endswith("done: quick: what's due?")
    gate.go.set()
    thread_of(app, "bg").join(5)
    assert app.jobs.get(bg).status == "ok" and seen == [(bg, Verdict.OK)]


def test_your_request_jumps_ahead_of_older_background_work(q):
    env, _ = q
    app = env.app
    old = app.jobs.submit("digest", quiet=True, background=True)
    mine = app.jobs.submit("quick one", reply_to=2)
    assert app.jobs._claim("you") == mine and app.jobs._claim("you") is None
    assert app.jobs._claim("bg") == old


def test_automatic_packs_are_background_work_and_your_pack_is_yours(env):
    from kurooto.modules import skills as smod

    env.on("deadlines")
    dl, sk = env.app.modules["deadlines"], env.app.modules["skills"]
    env.app.settings.set("skills.auto_pack", "auto")
    dl.add("Lab exam", now() + dt.timedelta(hours=20), kind="exam", subject="physics-lab")
    evening = dt.datetime.combine(now().date(), dt.time(18, 0))
    smod.now, real = (lambda: evening), smod.now
    try:
        assert sk.auto_packs() == 1
    finally:
        smod.now = real
    job = env.app.jobs.recent(1)[0]
    assert job.title.startswith("Before your exam: Revision pack:") and job.lane == "bg"
    sk.pack_for("physics lab midterm", reply_to=5)
    assert env.app.jobs.recent(1)[0].lane == "you"


# --------------------------------------------------------------------------------------------- the watchdog
def test_a_job_stuck_before_any_ai_ran_is_ended_and_the_lane_goes_on(q):
    env, gate = q
    app = env.app
    gate.where = "available"
    seen = []
    app.jobs.then_actions["t.seen"] = lambda job, result, payload: seen.append(result.verdict)
    jid = app.jobs.submit("Before your exam: Revision pack: Lab", then="t.seen")
    app.jobs._tick()
    assert gate.entered.wait(5)
    job = app.jobs.get(jid)
    assert job.status == "running" and job.brain is None
    assert app.jobs.watchdog() == []  # only 10 minutes without a sign of life count
    app.jobs._db.execute("update jobs set activity=? where id=?", (time.time() - 11 * 60, jid))
    assert app.jobs.watchdog() == [jid]
    job = app.jobs.get(jid)
    assert job.status == "failed" and job.verdict == "stuck" and seen == [Verdict.STUCK]
    assert "It got stuck (nothing was happening), so I stopped it." in env.fake.texts()[-1]
    assert not app.jobs._busy("you")  # its thread is still stuck, but the lane is free
    gate.where = "run"
    nxt = app.jobs.submit("quick: next", reply_to=3)
    app.jobs._tick()
    assert until(lambda: app.jobs.get(nxt).status == "ok")
    n = len(env.fake.texts())
    gate.go.set()  # the stuck one comes back late: nothing more is said, nothing changes
    gate.entered.clear()
    app.jobs._stops.get(jid) is None or app.jobs._stops[jid].wait(1)
    time.sleep(0.3)
    assert app.jobs.get(jid).verdict == "stuck" and len(env.fake.texts()) == n and seen == [Verdict.STUCK]


def test_a_job_past_its_time_limit_is_ended(q):
    env, gate = q
    app = env.app
    jid = app.jobs.submit("a long one", reply_to=4)
    app.jobs._tick()
    assert gate.entered.wait(5)
    assert until(lambda: app.jobs._read("select deadline from jobs where id=?", (jid,))[0] is not None)
    deadline = app.jobs._read("select deadline from jobs where id=?", (jid,))[0]
    assert deadline > time.time() + 15 * 60  # medium: 15 min, plus grace
    app.jobs._db.execute("update jobs set activity=?, deadline=? where id=?", (0, time.time() - 1, jid))
    assert app.jobs.watchdog() == [jid]
    assert app.jobs.get(jid).verdict == "timeout" and "No answer in time" in env.fake.texts()[-1]
    gate.go.set()
    thread_of(app, "you").join(5)
    assert app.jobs.get(jid).status == "failed"  # the late answer is dropped


def test_a_running_program_is_not_stuck(q):
    env, _ = q
    app = env.app
    jid = app.jobs.submit("x")
    assert app.jobs._claim() == jid
    from kurooto.core.jobs import RUNNER

    app.jobs._db.execute("update jobs set activity=0, proc=? where id=?", (RUNNER, jid))  # a live process
    assert app.jobs.watchdog() == [] and app.jobs.get(jid).status == "running"


def test_a_mistake_in_a_job_fails_it_instead_of_stopping_the_queue(q):
    env, gate = q
    app = env.app
    real = gate.run
    gate.run = lambda task: (_ for _ in ()).throw(http.client.IncompleteRead(b""))
    jid = app.jobs.submit("hello", reply_to=6)
    assert app.jobs.run_next() == jid
    job = app.jobs.get(jid)
    assert job.status == "failed" and job.verdict == "error" and "failed" in env.fake.texts()[-1]
    gate.run = real
    assert app.jobs.submit("quick: again") and app.jobs.run_next() and app.jobs.recent(1)[0].status == "ok"


# ------------------------------------------------------------------------------------------- cancelling
TREE = """import subprocess, sys, time
kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open(sys.argv[1], "w").write(f"{kid.pid}")
time.sleep(60)
"""


def test_cancelling_a_running_job_stops_its_program_and_what_it_started(env, monkeypatch, tmp_path):
    script, pids = tmp_path / "agent.py", tmp_path / "kid.pid"
    script.write_text(TREE)
    agent = Agy(exe=[sys.executable, str(script), str(pids)])
    monkeypatch.setattr(providers, "build", lambda a, w: agent if w == "agy" else None)
    app = env.app
    app.settings.set("brain.main", "agy")
    seen = []
    app.jobs.then_actions["t.seen"] = lambda job, result, payload: seen.append(result.verdict)
    jid = app.jobs.submit("a pack", then="t.seen", reply_to=9)
    app.jobs._tick()
    assert until(lambda: pids.exists() and pids.read_text().strip())
    assert until(lambda: app.jobs._read("select proc from jobs where id=?", (jid,))[0])
    parent = int(app.jobs._read("select proc from jobs where id=?", (jid,))[0].split(":")[0])
    kid = int(pids.read_text())
    n = len(env.fake.texts())
    assert app.jobs.cancel(jid).verdict == "cancelled"
    assert until(lambda: not psutil.pid_exists(kid) or psutil.Process(kid).status() == psutil.STATUS_ZOMBIE)
    assert not psutil.pid_exists(parent) or psutil.Process(parent).status() == psutil.STATUS_ZOMBIE
    thread_of(app, "you").join(10)
    assert not thread_of(app, "you").is_alive()
    job = app.jobs.get(jid)
    assert job.status == "failed" and job.verdict == "cancelled" and seen == [Verdict.CANCELLED]
    assert len(env.fake.texts()) == n  # no "failed" answer after you cancelled it
    assert app.jobs.cancel(jid) is None  # once


def test_jobs_on_telegram_lists_with_cancel_buttons(q):
    env, gate = q
    app = env.app
    a = app.jobs.submit("Revision pack: Lab", quiet=True, lane="bg")
    app.jobs._tick()
    assert gate.entered.wait(5)
    b = app.jobs.submit("/google forget school", reply_to=7)
    c = app.jobs.submit("/google forget main", reply_to=8)
    text = env.say("/jobs")
    assert "Running:\n- Revision pack: Lab · gate · under a minute · background" in text
    assert "Waiting:\n- /google forget school · waiting" in text and f"({c})" in text
    kb = [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"]
    datas = [btn["callback_data"] for row in kb for btn in row]
    assert datas == [f"job:{a}:cancel", f"job:{b}:cancel", f"job:{c}:cancel", "job:all:cancel"]
    assert env.press(f"job:{b}:cancel") == "Cancelled: /google forget school."
    assert env.press(f"job:{b}:cancel").startswith("No running or waiting request")
    assert env.say(f"/jobs cancel {c[:5]}") == "Cancelled: /google forget main."
    assert env.say("/jobs cancel all") == "Cancelled 1: Revision pack: Lab."
    assert env.say("/jobs").startswith("Nothing running or waiting.")
    assert app.jobs.get(a).verdict == "cancelled" and not app.jobs._busy("bg")


def test_jobs_cancel_from_the_dashboard_and_the_terminal(env, capsys):
    from kurooto import cli
    from kurooto.web.api import Api

    app = env.app
    a, b = app.jobs.submit("one"), app.jobs.submit("two")
    code, out = Api(app).get("jobs", {})
    assert code == 200 and [r["id"] for r in out["active"]] == [a, b] and "prompt" not in out["active"][0]
    assert Api(app).post("jobs/cancel", {"id": a})[1] == {"ok": True, "message": "Cancelled: one."}
    assert Api(app).post("jobs/cancel", {"id": a})[1]["ok"] is False
    assert cli.main(["jobs"]) == 0 and "two · waiting" in capsys.readouterr().out
    assert cli.main(["jobs", "--cancel", b]) == 0 and capsys.readouterr().out.strip() == "Cancelled: two."
    assert cli.main(["jobs", "--cancel", b]) == 1
    from kurooto.web import live

    js = (Path(live.__file__).parent / "static" / "home.js").read_text(encoding="utf-8")
    assert 'data-cancel="${esc(j.id)}"' in js and 'api("jobs/cancel"' in js


def test_the_dashboard_lists_waiting_jobs_however_old(env):
    from kurooto.web.live import Vitals

    app = env.app
    old = app.jobs.submit("old waiting one")
    for i in range(10):
        jid = app.jobs.submit(f"done {i}")
        app.jobs._db.execute("update jobs set status='ok' where id=?", (jid,))
    rows = Vitals(app).snapshot()["jobs"]
    assert old in [r["id"] for r in rows] and len(rows) == 9


# ----------------------------------------------------------------------------- an API brain on the internet
def test_one_internet_request_waits_minutes_not_the_whole_job(monkeypatch):
    seen = []

    def post(self, path, body, timeout):
        seen.append(timeout)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(OpenAICompat, "_post", post)
    far = OpenAICompat("gemini", "k")
    here = OpenAICompat("ollama", "", models={"medium": "m", "high": "m"})
    for b in (far, here):
        assert b.run(Task(prompt="x", effort="high", timeout_s=1800)).ok
    assert seen == [600, 1800]


def test_a_connection_cut_mid_answer_is_a_failure_not_a_crash(monkeypatch):
    def post(self, path, body, timeout):
        raise http.client.IncompleteRead(b"partial")

    monkeypatch.setattr(OpenAICompat, "_post", post)
    r = OpenAICompat("gemini", "k").run(Task(prompt="x", tools=[TOOL], run_tool=lambda n, a: ""))
    assert r.verdict == Verdict.ERROR and "IncompleteRead" in r.detail


def test_a_stopped_request_makes_no_more_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(OpenAICompat, "_post", lambda *a: calls.append(1) or {})
    stop = threading.Event()
    stop.set()
    t = Task(prompt="x", tools=[TOOL], run_tool=lambda n, a: calls.append(n), stop=stop)
    assert OpenAICompat("gemini", "k").run(t).verdict == Verdict.CANCELLED and calls == []


# ------------------------------------------------------------------------------------------- programs
def test_a_program_is_reported_when_it_starts():
    got = []
    r = proc.run([sys.executable, "-c", "print('hi')"], on_start=got.append)
    assert r.ok and r.out.strip() == "hi" and len(got) == 1 and got[0] > 0


@pytest.mark.skipif(sys.platform == "win32", reason="a double fork is POSIX")
def test_a_timed_out_program_whose_helper_escaped_doesnt_hang(tmp_path):
    pid = tmp_path / "escaped.pid"
    script = (
        "import os, sys, time\n"
        "if os.fork() == 0:\n"
        "    os.setsid()\n"
        "    if os.fork() == 0:\n"
        f"        open({str(pid)!r}, 'w').write(str(os.getpid())); time.sleep(40); os._exit(0)\n"
        "    os._exit(0)\n"
        "time.sleep(60)\n"
    )
    t0 = time.monotonic()
    r = proc.run([sys.executable, "-c", script], timeout=1)
    try:
        assert r.code is None and time.monotonic() - t0 < 20  # not the escaped helper's 40 s
    finally:
        if pid.exists():
            try:
                os.kill(int(pid.read_text()), 9)
            except (OSError, ValueError):
                pass


# ----------------------------------------------------------------------------------------------- Google
def test_signing_in_turns_google_on_with_the_parts_that_are_ready(env):
    from kurooto.modules.google_mail import MailDigest

    app = env.app
    app.modules.setdefault(MailDigest.id, MailDigest(app))
    g = FakeGoogle()
    try:
        app.settings.set("google.endpoints", g.endpoints())
        app.settings.set("google.mail_digest", True)  # set up before (an import), but Google itself is off
        gm = app.modules["google"]
        gm.set_client(CLIENT)
        assert not app.is_on("google")
        code, state = g.issue_code(gm.start_signin())
        ok, msg = gm.finish_signin(code, state)
        assert ok and app.is_on("google") and app.is_on("mail_digest")
        assert "Turned on: Google (Classroom, Gmail drafts), Mail digest." in msg
        assert "google" in [c["command"] for c in env.tg.menu()]
    finally:
        g.close()


# ------------------------------------------------------------------------------- commands of features that are off
def test_commands_of_features_that_are_off_say_how_to_turn_them_on(env, monkeypatch):
    ai = FakeOpenAI()
    try:
        app = env.app
        app.secrets.set("custom.api_key", ai.key)
        app.settings.set("brain.base_urls", {"custom": ai.base})
        app.settings.set("brain.models", {"custom": {"medium": "smart"}})
        app.settings.set("brain.main", "custom")
        env.on("chat")
        n = len(app.jobs.recent(50))
        assert env.say("/google forget school") == "Google is off: Features → Google → Turn on."
        assert env.say("/classroom") == "Google is off: Features → Google → Turn on."
        app.disable("skills") if app.is_on("skills") else None
        assert env.say("/journal my day") == "Skills is off: Features → Skills → Turn on."
        assert len(app.jobs.recent(50)) == n  # none of them went to the AI
        assert env.say("/jobs").startswith("Nothing running or waiting.")
        app.disable("chat")
        assert env.say("/jobs").startswith("Nothing running or waiting.")  # Kurooto's own: always answers
        assert env.say("/help").startswith(app.name)
        assert "/jobs  what the AI is working on" in env.say("/help")
    finally:
        ai.close()


def test_status_answers_with_telegram_off(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        out = []
        app.handle(Incoming(text="/status", via="terminal", respond=lambda t, buttons=None: out.append(t)))
        assert out and out[0].startswith("Calls:")
        out.clear()
        app.handle(Incoming(text="/hold 18:00", via="terminal", respond=lambda t, buttons=None: out.append(t)))
        assert out == ["Telegram is off: Features → Telegram → Turn on."]
        out.clear()
        app.handle(Incoming(text="/sync", via="terminal", respond=lambda t, buttons=None: out.append(t)))
        assert out and "is off" not in out[0]  # /sync syncs everything while Notes sync is off
    finally:
        app.close()
