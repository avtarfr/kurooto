"""Brain 0.8.14, group B: Kurooto sleeps (mind/sleep.py), the body-aware job gate (mind/senses/intero.py, core/jobs.py)
and the orienting jolt (mind/stimulation.py)."""

import datetime as dt
import time

import pytest

from kurooto import mind
from kurooto.core import calm, clock
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind import sleep, stimulation
from kurooto.mind.senses import intero, store

DAY = dt.date(2026, 3, 10)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("mind.sleep.on", True)  # off for other tests (tests/conftest.py: kurooto_awake)
    a.settings.set("availability.night", {"enabled": True, "from": "23:30", "to": "07:00", "alarm_only": False})
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 0)  # this test machine's card isn't the point
    monkeypatch.setattr(intero, "_on_battery", lambda app: False)
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def at(monkeypatch, hh: int, mm: int = 0, day: dt.date = DAY) -> dt.datetime:
    t = dt.datetime.combine(day, dt.time(hh, mm))
    monkeypatch.setattr(sleep, "now", lambda: t)
    monkeypatch.setattr(clock, "now", lambda: t)
    monkeypatch.setattr(calm, "now", lambda: t)  # its close-deadline rule
    return t


def sent(app, monkeypatch) -> list:
    out = []
    monkeypatch.setattr(app.notifier, "release", lambda m: out.append(m))
    return out


# ----------------------------------------------------------------------------------------------- the window
def test_state_from_the_night_hours(app, monkeypatch):
    at(monkeypatch, 22, 30)
    assert sleep.state(app) == "awake"
    assert sleep.window(app) == (dt.datetime(2026, 3, 10, 23, 30), dt.datetime(2026, 3, 11, 7, 0))
    at(monkeypatch, 23, 10)
    assert sleep.state(app) == "drowsy"
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "asleep" and sleep.window(app)[1] == dt.datetime(2026, 3, 11, 7, 0)
    at(monkeypatch, 8, 0, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "awake"
    assert sleep.window(app)[0] == dt.datetime(2026, 3, 11, 23, 30)  # tonight's


def test_manual_window_and_switches(app, monkeypatch):
    app.settings.set("mind.sleep.window", "01:00-09:00")
    at(monkeypatch, 0, 0)
    assert sleep.state(app) == "awake"
    at(monkeypatch, 8, 30)
    assert sleep.state(app) == "asleep"
    app.settings.set("mind.sleep.on", False)
    assert sleep.state(app) == "awake" and sleep.window(app) is None
    app.settings.set("mind.sleep.on", True)
    app.settings.set("modules.enabled", [])  # Brain off: as 0.8.13
    assert sleep.state(app) == "awake" and sleep.window(app) is None


def test_bedtime_to_the_alarm(app, monkeypatch):
    bed, alarm = dt.datetime(2026, 3, 10, 22, 0), dt.datetime(2026, 3, 11, 5, 30)
    app.availability.sleep = lambda: [(bed, alarm)]
    at(monkeypatch, 22, 15)
    assert sleep.state(app) == "asleep" and sleep.window(app) == (bed, alarm)
    at(monkeypatch, 6, 0, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "awake"  # the alarm's night ended at 05:30, not the fixed 07:00
    app.settings.set("mind.sleep.follow_owner", False)
    at(monkeypatch, 22, 15)
    assert sleep.state(app) == "awake"  # the night hours as they are: 23:30


def _phone(app, sensor, kind, target, n, t):
    store.add(app, f"phone:{sensor}", kind, target, n, t=t.timestamp())


def _phone_on(app, *sensors):
    for s in sensors:
        app.settings.set(f"mind.senses.phone.{s}", True)


def test_sleep_onset_from_the_phone(app, monkeypatch):
    _phone_on(app, "screen", "light", "charging")
    t0 = dt.datetime(2026, 3, 10, 22, 0)
    for i in range(10):  # screen off, dark and charging from 22:00
        t = t0 + dt.timedelta(minutes=5 * i)
        _phone(app, "screen", "on_min", "", 0, t)
        _phone(app, "light", "band", "dark", 0, t)
        _phone(app, "charging", "on", "", 1, t)
    at(monkeypatch, 22, 45)
    assert sleep.state(app) == "asleep" and sleep.window(app)[0] == t0  # it sleeps with you, early
    _phone(app, "light", "band", "bright", 0, dt.datetime(2026, 3, 10, 22, 50))
    at(monkeypatch, 22, 55)
    assert sleep.state(app) == "awake"  # the light came on: not asleep yet (the fixed window is 23:30)


def test_up_late_and_up_early_from_the_phone(app, monkeypatch):
    _phone_on(app, "screen")
    _phone(app, "screen", "on_min", "", 15, dt.datetime(2026, 3, 10, 23, 35))
    at(monkeypatch, 23, 40)
    assert sleep.state(app) == "drowsy"  # still on the phone: the window waits for you
    at(monkeypatch, 1, 0, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "asleep"
    _phone(app, "screen", "on_min", "", 15, dt.datetime(2026, 3, 11, 5, 50))
    at(monkeypatch, 6, 0, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "awake"  # in use in the last 90 minutes: you're up


def test_the_phones_alarm_ends_it(app, monkeypatch):
    _phone_on(app, "alarm")
    _phone(app, "alarm", "at", "", dt.datetime(2026, 3, 11, 6, 0).timestamp() * 1000, dt.datetime(2026, 3, 10, 22, 0))
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    assert sleep.window(app)[1] == dt.datetime(2026, 3, 11, 6, 0)


# ----------------------------------------------------------------------------------------------- waking
def test_woken_by_its_name_and_dozing_again(app, monkeypatch):
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    m = app.modules["mind"]
    m._mirror({"kind": "voice_portal", "open": True, "why": "its name"})
    assert sleep.state(app) == "awake" and sleep.summary(app)["wakes_today"] == 1
    at(monkeypatch, 2, 15, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "awake"
    at(monkeypatch, 2, 21, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "asleep"  # 20 quiet minutes: dozing again
    m._mirror({"kind": "voice_portal", "open": True, "why": "a question"})  # not its name: still asleep
    assert sleep.state(app) == "asleep"


def test_woken_by_a_message(app, monkeypatch):
    app.settings.set("mind.sleep.wake_minutes", 5)
    at(monkeypatch, 3, 0, DAY + dt.timedelta(days=1))
    app.modules["mind"]._mirror({"kind": "message_in", "via": "telegram"})
    assert sleep.state(app) == "awake"
    at(monkeypatch, 3, 6, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "asleep"


def test_a_message_by_day_changes_nothing(app, monkeypatch):
    at(monkeypatch, 14, 0)
    sleep.on_event(app, {"kind": "message_in"})
    assert "woke_until" not in sleep._load(app)


# ----------------------------------------------------------------------------------------------- holding
def test_asleep_it_holds_what_it_starts_and_sends_the_exempt(app, monkeypatch):
    out = sent(app, monkeypatch)
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    app.notifier.send("Research watch: two new papers.", why="research.papers")
    assert out == [] and sleep.held_count(app) == 1
    app.notifier.send("Your reminder: call the lab.", kind="reminder", why="reminders.own")
    app.notifier.send("Approve this?", kind="approval", why="proposals.night")
    app.notifier.send("Here's your answer.", why="asked")
    app.notifier.send("Due in 3 hours.", why="deadlines.reminder", due=dt.datetime(2026, 3, 11, 5, 0).isoformat())
    assert [m.text for m in out] == [
        "Your reminder: call the lab.",
        "Approve this?",
        "Here's your answer.",
        "Due in 3 hours.",
    ]
    sleep.wake(app, "its name")  # woken to answer: what waited still waits for the morning
    sleep.tick(app)
    assert sleep.held_count(app) == 1 and len(out) == 4
    at(monkeypatch, 7, 30, DAY + dt.timedelta(days=1))
    assert sleep.tick(app) == "awake"
    assert sleep.held_count(app) == 0 and out[-1].text == "Research watch: two new papers."
    assert out[-1].why == "research.papers"  # it went through the usual path, its reason kept


def test_getting_up_ends_the_night(app, monkeypatch):
    out = sent(app, monkeypatch)
    at(monkeypatch, 5, 0, DAY + dt.timedelta(days=1))
    app.notifier.send("A check-in.", why="checkins.ask")
    assert out == []
    app.modules["mind"]._mirror({"kind": "alarm_up_now"})
    assert sleep.state(app) == "awake" and [m.text for m in out] == ["A check-in."]
    app.notifier.send("Another.", why="checkins.ask")
    assert len(out) == 2  # up: nothing more is held this night


def test_sleep_off_holds_nothing(app, monkeypatch):
    out = sent(app, monkeypatch)
    app.settings.set("mind.sleep.on", False)
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    app.notifier.send("Research watch.", why="research.papers")
    assert len(out) == 1


def test_voice_says_nothing_by_itself_while_asleep(app, monkeypatch):
    v = app.modules["voice"]
    monkeypatch.setattr(app, "is_on", lambda m: m in ("mind", "voice"))
    monkeypatch.setattr(v, "muted", lambda: False)
    at(monkeypatch, 23, 10)  # drowsy: quieter already
    assert v.greet("Good evening.", 10) == (False, "Kurooto is asleep")
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    assert v.greet("Hello.", 10) == (False, "Kurooto is asleep")


def test_mind_status_lines(app, monkeypatch):
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    assert sleep.line(app) == "Sleep: asleep until 07:00."
    at(monkeypatch, 12, 0)
    assert sleep.line(app) == "Sleep: awake; tonight 23:30 to 07:00."
    assert intero.yield_line(app).startswith("Job gate: 0 contention minutes this week")


# ----------------------------------------------------------------------------------------------- the job gate
def test_the_gate_defers_for_your_gpu_work_a_call_or_battery(app, monkeypatch):
    monkeypatch.setattr(intero, "would_overheat", lambda *a, **k: False)
    assert intero.ok(app, "gpu") == (True, "")
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 1)
    assert intero.ok(app, "gpu") == (False, "your own work is using the graphics card")
    assert intero.ok(app, "light") == (True, "")  # reading files doesn't fight for the card
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 0)
    app.availability.set_on_call(dt.datetime.now() + dt.timedelta(minutes=2))
    assert intero.ok(app, "cpu") == (False, "you're on a call")
    app.availability.set_on_call(None)
    monkeypatch.setattr(intero, "_on_battery", lambda app: True)
    assert intero.ok(app, "gpu") == (False, "on battery")
    monkeypatch.setattr(intero, "_on_battery", lambda app: False)
    monkeypatch.setattr(intero, "would_overheat", lambda *a, **k: True)
    assert intero.ok(app, "gpu") == (False, "the computer is hot")
    app.settings.set("mind.yield.on", False)
    assert intero.ok(app, "gpu") == (True, "")


def test_would_overheat_is_used(app, monkeypatch):
    st = {"model": {}}
    for _ in range(4):
        intero.learn(st, "lab", "cpu_temp_c", 20.0)
    from kurooto.core.state import jsave

    jsave(app.paths.state / intero.FILE, {**st, "history": [{"at": time.time(), "cpu_temp_c": 70.0}]})
    assert intero.ok(app, "gpu", "lab") == (False, "the computer is hot")  # 70 + 20 past 85
    assert intero.ok(app, "gpu", "ai_request")[0]


def test_gated_work_waits_then_runs(app, monkeypatch):
    monkeypatch.setattr(intero, "would_overheat", lambda *a, **k: False)
    ran = []
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 1)
    assert intero.gated(app, "lab", "gpu", lambda: ran.append(1) or "done") is None
    assert ran == [] and intero.contention(app)["waiting"] == ["lab"] and intero.contention(app)["deferred"] == 1
    assert intero.retry(app) == 0
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 0)
    assert intero.retry(app) == 1 and ran == [1] and intero.contention(app)["waiting"] == []
    assert intero.gated(app, "lab", "gpu", lambda: "now") == "now"


def test_waiting_work_is_given_up_after_a_while(app, monkeypatch):
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 1)
    intero.gated(app, "play", "cpu", lambda: None)
    from kurooto.core.state import jload, jsave

    st = jload(app.paths.state / intero.FILE, {})
    st["pending"]["play"]["since"] = time.time() - (intero.PENDING_H + 1) * 3600
    jsave(app.paths.state / intero.FILE, st)
    assert intero.retry(app) == 0 and intero.contention(app)["skipped"] == 1


def test_nightly_work_prefers_its_sleep(app, monkeypatch):
    monkeypatch.setattr(intero, "would_overheat", lambda *a, **k: False)
    ran = []
    at(monkeypatch, 1, 30, DAY + dt.timedelta(days=1))
    sleep.wake(app, "a message")  # you're up at 01:30: the lab waits for it to sleep
    assert intero.gated(app, "lab", "gpu", lambda: ran.append("lab"), nightly=True) is None and ran == []
    assert intero.gated(app, "plans", "cpu", lambda: ran.append("plans")) is None and ran == ["plans"]  # not nightly
    at(monkeypatch, 1, 55, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "asleep"
    assert intero.retry(app) == 1 and ran == ["plans", "lab"]
    app.settings.set("mind.yield.prefer_sleep", False)
    at(monkeypatch, 15, 0)
    assert intero.gated(app, "lab", "gpu", lambda: "ran", nightly=True) == "ran"


def test_contention_minutes(app, monkeypatch):
    assert not intero.contention_tick(app)  # nothing of its own running
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 1)
    seen = []

    def work():
        seen.append(intero.contention_tick(app))

    intero._run(app, "finetune", work)
    assert seen == [True] and intero.contention(app)["minutes"] == 1


def test_the_job_queue_gate(app, monkeypatch):
    calls = []

    def gate(info):
        calls.append(info["why"])
        return time.time() + 600 if info["why"].startswith("mind.") else None

    app.jobs.gates.append(gate)
    mine = app.jobs.submit("what's due?", lane="you", why="mind.asked_by_you")  # yours: never asked
    dream = app.jobs.submit("dream", background=True, quiet=True, lane="bg", why="mind.dream")
    other = app.jobs.submit("research", background=True, quiet=True, lane="bg", why="research.papers")
    assert app.jobs._claim("you") == mine and calls == []
    assert app.jobs._claim("bg") == other and calls == ["mind.dream", "research.papers"]
    assert app.jobs._claim("bg") is None  # the Brain's own waits a while, never dropped
    row = app.jobs._read("select status, yield_until from jobs where id=?", (dream,))
    assert row[0] == "queued" and row[1] > time.time() + 500


def test_the_brains_job_gate(app, monkeypatch):
    m = app.modules["mind"]
    assert m._job_gate({"why": "research.papers"}) is None
    monkeypatch.setattr(intero, "gpu_holders", lambda app: 1)
    monkeypatch.setattr(intero, "would_overheat", lambda *a, **k: False)
    assert m._job_gate({"why": "mind.dream", "brain": "gemini"}) is None  # a cloud AI: light work
    assert m._job_gate({"why": "mind.dream", "brain": "ollama"}) > time.time()  # the model here: the card


# ----------------------------------------------------------------------------------------------- the jolt
def test_an_orienting_jolt(app, monkeypatch):
    cycles = []
    from kurooto.mind import workspace

    monkeypatch.setattr(workspace, "cycle", lambda app, extra=None, force=False: cycles.append(force) or [])
    assert stimulation.arousal(app) == 0.0
    assert stimulation.jolt(app, "pickup") and cycles == [True]
    assert stimulation.arousal(app) > 0.9
    assert not stimulation.jolt(app, "pickup")  # once a minute per kind
    assert not stimulation.jolt(app, "Not a kind!")
    assert stimulation.feed(app, "a device", {"proximity_cm": 1.0}) and cycles == [True, True]  # something close
    app.settings.set("mind.stimulation.jolt", False)
    assert not stimulation.jolt(app, "loud")


def test_a_phone_pickup_jolts(app, monkeypatch):
    from kurooto.mind.senses import phone

    _phone_on(app, "screen")
    kinds = []
    monkeypatch.setattr(stimulation, "jolt", lambda app, kind, strength=1.0: kinds.append(kind) or True)
    phone.ingest(app, {"bins": [{"s": "screen", "t": time.time() * 1000, "unlocks": 0, "on_min": 0}]})
    assert kinds == []
    phone.ingest(app, {"bins": [{"s": "screen", "t": time.time() * 1000, "unlocks": 1, "on_min": 15}]})
    assert kinds == ["pickup"]


# ----------------------------------------------------------------------------------------------- 0.8.18
class Desk:
    """Face presence's desk_seen_at(), set by the test."""

    def __init__(self):
        self.at = None

    def desk_seen_at(self):
        return self.at


def desk(app, monkeypatch) -> Desk:
    d = Desk()
    monkeypatch.setitem(app.modules, "face", d)
    monkeypatch.setattr(app, "is_on", lambda m: m in ("mind", "face"))
    return d


def test_asleep_its_senses_close_until_woken(app, monkeypatch):
    sleep._cache.clear()
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    assert sleep.senses_off(app)
    sleep._cache.clear()
    app.settings.set("mind.sleep.senses_off", False)  # the switch: Voice keeps listening, its name wakes it
    assert not sleep.senses_off(app)
    app.settings.set("mind.sleep.senses_off", True)
    sleep._cache.clear()
    out = app.modules["mind"].wake_cmd(None, "")
    assert out.startswith("Awake: camera and microphone on") and not sleep.senses_off(app)  # wake drops the cache
    at(monkeypatch, 14, 0)
    assert app.modules["mind"].wake_cmd(None, "").startswith("I'm awake.")


def test_the_desk_keeps_it_awake_then_it_sleeps_till_woken(app, monkeypatch):
    d = desk(app, monkeypatch)
    t = at(monkeypatch, 23, 40)
    d.at = (t - dt.timedelta(minutes=2)).timestamp()  # at the desk: the window waits for you
    assert sleep.state(app) == "drowsy" and sleep.window(app)[0] == dt.datetime(2026, 3, 10, 23, 53)
    t = at(monkeypatch, 1, 0, DAY + dt.timedelta(days=1))
    d.at = (t - dt.timedelta(minutes=1)).timestamp()  # still there at one
    assert sleep.state(app) != "asleep"
    d.at = (t - dt.timedelta(minutes=20)).timestamp()  # left 20 minutes ago (desk_after_min 15)
    assert sleep.state(app) == "asleep"
    t = at(monkeypatch, 1, 5, DAY + dt.timedelta(days=1))
    d.at = t.timestamp()  # back at the desk: asleep is asleep until woken (the latch)
    assert sleep.state(app) == "asleep"
    sleep.wake(app, "you said /wake", 20)
    t = at(monkeypatch, 1, 40, DAY + dt.timedelta(days=1))
    d.at = (t - dt.timedelta(minutes=1)).timestamp()  # woken, and at the desk: it stays awake past wake_minutes
    assert sleep.state(app) != "asleep"
    app.settings.set("mind.sleep.desk_holds", False)  # the switch
    assert sleep.state(app) == "asleep"


def test_the_desk_holds_a_window_set_by_hand_up_to_its_end(app, monkeypatch):
    app.settings.set("mind.sleep.window", "01:00-03:00")
    d = desk(app, monkeypatch)
    t = at(monkeypatch, 2, 50, DAY)
    d.at = t.timestamp()
    assert sleep.state(app) == "awake"  # held past its end: no window left tonight
    d.at = None  # Face presence can't say (off, away): as before
    assert sleep.state(app) == "asleep"
