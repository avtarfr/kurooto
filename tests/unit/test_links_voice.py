"""0.9.0 links, batch 2: desk Voice, Brain sleep, the presence forecast, breaks, the alarm, owner_here, Chat.

Each section names its link. Made-up times and words; nothing here opens a camera or a microphone."""

# ruff: noqa: F811 (the fixtures imported from the other tests are taken as arguments)

import datetime as dt
import time
from types import SimpleNamespace

import pytest

from kurooto import mind
from kurooto.core import calm, clock, here, nearby
from kurooto.mind import breaks, presence_forecast, signals, sleep
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.modules import voice as voice_mod
from kurooto.modules.face import greet as greet_mod
from kurooto.modules.face.watch import Watcher
from kurooto.modules.voice.gate import Gate, Heard
from tests.unit.test_voice import Speakers, Tts, voice  # noqa: F401 (a pytest fixture)

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
    sleep._cache.clear()
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def at(monkeypatch, hh: int, mm: int = 0, day: dt.date = DAY) -> dt.datetime:
    t = dt.datetime.combine(day, dt.time(hh, mm))
    monkeypatch.setattr(sleep, "now", lambda: t)
    monkeypatch.setattr(clock, "now", lambda: t)
    monkeypatch.setattr(calm, "now", lambda: t)
    return t


def kinds(app, kind: str) -> list[dict]:
    return [r for r in app.events.tail(500) if r.get("kind") == kind]


# ------------------------------------------------------------------------------------------- L8: owner_here
def test_owner_here_is_words_free_once_per_gap_and_switched(app):
    assert here.owner_here(app, "voice", at=1000.0)
    assert here.owner_here(app, "voice", at=1010.0)  # kept in memory, not logged again
    rows = kinds(app, "owner_here")
    assert len(rows) == 1 and set(rows[0]) <= {"ts", "kind", "via"} and rows[0]["via"] == "voice"
    assert here.last(app, desk=True) == 1010.0
    here.owner_here(app, "voice", at=1010.0 + here.EVENT_GAP_S)
    assert len(kinds(app, "owner_here")) == 2
    app.settings.set("presence.owner_here.phone", False)  # the switch
    assert not here.owner_here(app, "phone") and here.last(app) == 1010.0 + here.EVENT_GAP_S
    assert not here.owner_here(app, "elsewhere")
    assert "owner_here" in signals.ACTIVE


def test_desk_vias_count_at_the_desk_the_phone_doesnt(app):
    t = time.time()
    here.owner_here(app, "phone", at=t)
    assert presence_forecast.at_desk(app, t) is None  # nothing at the desk can tell
    here.owner_here(app, "dashboard", at=t)
    assert presence_forecast.at_desk(app, t) is True
    assert presence_forecast.at_desk(app, t + presence_forecast.DESK_S + 5) is None


def test_the_dashboard_or_the_phone_wakes_it_your_face_doesnt(app, monkeypatch):
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    m = app.modules["mind"]
    m._mirror({"kind": "owner_here", "via": "face"})
    assert sleep.state(app) == "asleep"
    m._mirror({"kind": "owner_here", "via": "dashboard"})
    assert sleep.state(app) == "awake"


def test_the_phone_apps_events_are_owner_here(app):
    app.modules["mind"]._mirror({"kind": "phone_today_act"})
    assert [r["via"] for r in kinds(app, "owner_here")] == ["phone"]


def test_a_voice_sign_ends_away_without_an_arrival(app):
    got = []
    clk = [100.0]
    w = Watcher(
        camera=None, detector=None, embedder=None, frames=None, classify=lambda e: ("you", 1.0), paused=lambda: "",
        cfg=lambda: {}, idle=lambda: None, locked=lambda: False, emit=lambda k, **f: got.append(k),
        clock=lambda: clk[0],
    )  # fmt: skip
    w.away, w.camera_open = True, True
    assert w.here() and not w.away and got == ["back"]
    clk[0] += 60
    w._check_away(clk[0], False, {"away_on": True, "away_after_min": 5})
    assert not w.away  # counted again from the voice, not from the last face
    clk[0] += 5 * 60
    w._check_away(clk[0], False, {"away_on": True, "away_after_min": 5})
    assert w.away and "arrived" not in got


def test_owner_here_back_is_a_break(app):
    app.settings.set("mind.workspace.on", True)
    app.settings.set("mind.workspace.breaks", True)
    breaks.on_event(app, {"kind": "owner_here", "via": "voice"})
    assert not breaks.last(app)
    breaks.on_event(app, {"kind": "owner_here", "via": "voice", "back": True})
    assert breaks.last(app)["kind"] == "back"


# ------------------------------------------------------------------------------------- L9: the desk and sleep
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


@pytest.mark.parametrize(
    "rec",
    [
        {"kind": "voice_portal", "open": True, "why": "looked at"},
        {"kind": "voice_barge", "how": "voice", "outcome": "turn"},
        {"kind": "voice_live", "stage": "answered"},
    ],
)
def test_a_look_a_barge_in_or_a_live_turn_wakes_it(app, monkeypatch, rec):
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    app.settings.set("mind.sleep.follow_desk", False)  # the switch: as 0.8.18
    app.modules["mind"]._mirror(rec)
    assert sleep.state(app) == "asleep"
    app.settings.set("mind.sleep.follow_desk", True)
    app.modules["mind"]._mirror({**rec, "outcome": "listen", "stage": "fallback", "why": "silence"})
    assert sleep.state(app) == "asleep"  # not a turn of yours
    app.modules["mind"]._mirror(rec)
    assert sleep.state(app) == "awake"


def test_at_the_desk_near_the_end_it_is_up(app, monkeypatch):
    app.settings.set("mind.sleep.desk_holds", False)  # the hold alone would already let things go; this is the end
    d = desk(app, monkeypatch)
    t = at(monkeypatch, 6, 0, DAY + dt.timedelta(days=1))
    d.at = t.timestamp()
    assert not sleep.desk_up(app)  # asleep: the desk can't undo it (the latch)
    sleep.wake(app, "you said /wake", 20)
    assert sleep.desk_up(app) and sleep._load(app)["up_why"] == "you're at the desk"
    assert sleep.state(app) == "awake" and not sleep.resting(app)
    t = at(monkeypatch, 3, 0, DAY + dt.timedelta(days=2))
    sleep.wake(app, "you said /wake", 20)
    d.at = t.timestamp()
    assert not sleep.desk_up(app)  # 3:00 is not the night's last 90 minutes
    t = at(monkeypatch, 6, 0, DAY + dt.timedelta(days=2))
    sleep.wake(app, "you said /wake", 20)
    d.at = t.timestamp()
    app.settings.set("mind.sleep.follow_desk", False)
    assert not sleep.desk_up(app)


# ---------------------------------------------------------------------------- L10: an add-on's sleep reading
def test_an_addons_sleep_reading_is_noted_and_moves_the_night_only_when_switched_on(app, monkeypatch):
    t = at(monkeypatch, 22, 40)
    sleep.body_asleep(app, True)  # the name the Body add-on probes
    assert sleep._load(app)["external"]["body"]["asleep"] is True
    assert [r["state"] for r in kinds(app, "body_sleep")] == ["asleep"]  # the reading it wrote before, kept
    at(monkeypatch, 23, 0)
    assert sleep.window(app)[0] == dt.datetime(2026, 3, 10, 23, 30)  # off by default: as 0.8.18
    app.settings.set("mind.sleep.follow_external", True)
    assert sleep.window(app)[0] == t and sleep.state(app) == "asleep"
    sleep.external_asleep(app, False, "body")
    assert sleep.window(app)[0] == dt.datetime(2026, 3, 10, 23, 30)
    sleep.external_asleep(app, True, "some odd/name!")
    assert "someoddname" in sleep._load(app)["external"]


# ------------------------------------------------------------------------ L16: reachable, beside at the desk
MON10 = dt.datetime(2026, 11, 2, 10, 0)  # a Monday


def test_reachable_keeps_a_message_where_the_desk_estimate_would_move_it(app, monkeypatch):
    monkeypatch.setattr(presence_forecast, "_in_class", lambda a, t: False)
    monkeypatch.setattr(presence_forecast, "_asleep", lambda a, t: False)
    st = presence_forecast._load(app)
    st["cells"]["0-10"] = [0.0, 4]  # never at the desk at 10 on Mondays
    st["cells"]["0-11"] = [4.0, 4]  # always at 11
    st["rcells"]["0-10"] = [2.0, 2]  # but on your phone at 10
    presence_forecast._save(app, st)
    assert presence_forecast.p_reach(app, MON10) > presence_forecast.FREE_P > presence_forecast.p_free(app, MON10)
    assert presence_forecast.prefer(app, MON10, earliest=MON10) == dt.datetime(2026, 11, 2, 11, 0)  # as 0.8.18
    assert presence_forecast.prefer(app, MON10, earliest=MON10, reach=True) == MON10
    app.settings.set("mind.presence_forecast.reachable", False)  # the switch: exactly as before
    assert presence_forecast.p_reach(app, MON10) == presence_forecast.p_free(app, MON10)
    assert presence_forecast.prefer(app, MON10, earliest=MON10, reach=True) == dt.datetime(2026, 11, 2, 11, 0)


def test_the_phone_app_makes_reachable_looks_and_now(app, monkeypatch):
    c = {"t": MON10.replace(hour=9)}
    monkeypatch.setattr(presence_forecast, "now", lambda: c["t"])
    monkeypatch.setattr(presence_forecast, "sensing", lambda a: False)  # nothing sees the desk
    monkeypatch.setattr(presence_forecast, "_asleep", lambda a, t: False)
    assert not presence_forecast.reachable_now(app)
    for m in (0, 15, 30):
        c["t"] = MON10.replace(hour=9, minute=m)
        here.owner_here(app, "phone", at=c["t"].timestamp())
        presence_forecast.tick(app)
    assert presence_forecast.reachable_now(app)
    c["t"] = MON10
    assert presence_forecast.tick(app) == []  # nothing scored: reachable is never paid for
    st = presence_forecast._load(app)
    assert st["rcells"]["0-9"] == [1.0, 1] and not st["cells"]


# ---------------------------------------------------------------------- L17: an add-on's busy times, a hint
def test_busy_times_are_a_hint_and_a_soft_cut_only_when_switched_on(app, monkeypatch):
    monkeypatch.setattr(presence_forecast, "_in_class", lambda a, t: False)
    monkeypatch.setattr(presence_forecast, "_asleep", lambda a, t: False)
    tue7 = dt.datetime(2026, 11, 3, 19, 0)
    before = presence_forecast.p_free(app, tue7)
    assert presence_forecast.busy_hint(app) == ""
    presence_forecast.busy_from(app, "visits", lambda a: [(1, 19), (3, 19), (3, 20), (9, 99)])
    assert presence_forecast.busy_hint(app) == "Tue and Thu evenings are usually busy."
    assert "usually busy" in presence_forecast.line(app)
    assert presence_forecast.p_free(app, tue7) == before  # visitors off: a hint only
    app.settings.set("mind.presence_forecast.visitors", True)
    assert presence_forecast.BLOCKED_P < presence_forecast.p_free(app, tue7) < before
    app.settings.set("mind.presence_forecast.busy_hint", False)
    assert presence_forecast.busy_hint(app) == ""
    presence_forecast.busy_from(app, "visits", lambda a: 1 / 0)  # an add-on's trouble: no busy times
    assert not presence_forecast.busy(app, tue7)


# ------------------------------------------------------------------------------------------- L18: Face breaks
def test_face_left_looked_and_stood_are_breaks(app):
    app.settings.set("mind.workspace.on", True)
    app.settings.set("mind.workspace.breaks", True)
    app.settings.set("face.breaks", False)  # the switch: as 0.8.18
    breaks.on_event(app, {"kind": "face_stood"})
    assert not breaks.last(app)
    app.settings.set("face.breaks", True)
    for kind, b in (("face_left", "left"), ("face_looked", "looked"), ("face_stood", "stood")):
        breaks.on_event(app, {"kind": kind})
        assert breaks._load(app)["counts"].get(b) == 1  # (last() keeps the latest by its rounded time)


def test_face_sees_a_look_and_standing_up(app, monkeypatch):
    from kurooto.core import nearby

    face = app.modules["face"]
    monkeypatch.setattr(face, "owner_desk_height", lambda: {"px": 200.0, "h": 0.4, "measured": True})
    nearby.set_look(app, True, at=10.0)
    nearby.set_look(app, True, at=11.2)
    face._break_signs((190.0, 0.0, 0.0), (640, 480))
    face._break_signs((190.0, 0.0, 0.0), (640, 480))  # the same run of looks: once
    assert len(kinds(app, "face_looked")) == 1 and not kinds(app, "face_stood")
    face._break_signs((100.0, 0.0, 0.0), (640, 480))  # 0.21 of the frame, under 0.6 x 0.4
    face._break_signs((100.0, 0.0, 0.0), (640, 480))
    assert len(kinds(app, "face_stood")) == 1
    face._break_signs((180.0, 0.0, 0.0), (640, 480))  # sitting again
    face._break_signs((90.0, 0.0, 0.0), (640, 480))
    assert len(kinds(app, "face_stood")) == 2
    app.settings.set("face.breaks", False)
    face._break_signs((180.0, 0.0, 0.0), (640, 480))
    face._break_signs((90.0, 0.0, 0.0), (640, 480))
    assert len(kinds(app, "face_stood")) == 2


# ----------------------------------------------------------------------------- L15: up before the alarm
@pytest.fixture
def alarm_world(env, monkeypatch):
    from kurooto.modules.calls import deploy
    from tests.unit.test_alarmfix import WED, World
    from tests.unit.test_alarmfix import at as day_at

    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls")
    w = World(env.app, monkeypatch, day_at(WED, 6, 0))
    env.app.settings.set("alarm.daily", "07:00")
    env.on("alarm")
    return env, env.app.modules["alarm"], w, WED, day_at


def test_up_before_the_alarm_asks_and_only_a_tap_skips(alarm_world):
    env, a, w, wed, day_at = alarm_world
    assert a.ask_skip() == ""  # no sign of you
    w.t = day_at(wed, 6, 20)
    here.owner_here(env.app, "dashboard", at=w.t.timestamp())
    assert "skip the 07:00 alarm" in a.ask_skip()
    assert a.ask_skip() == ""  # once per alarm
    w.tick(day_at(wed, 7, 0))
    assert w.rang == [("alarm:next", True)]  # no answer: it rings as set


def test_skip_it_clears_that_alarm(alarm_world):
    env, a, w, wed, day_at = alarm_world
    w.t = day_at(wed, 6, 30)
    here.owner_here(env.app, "phone", at=w.t.timestamp())
    assert a.ask_skip()
    assert env.press(f"alm:{day_at(wed, 7, 0):%Y%m%d%H%M}:skipup") == "OK, the 07:00 alarm won't ring."
    assert a.next() == day_at(wed, 7, 0) + dt.timedelta(days=1)
    w.tick(day_at(wed, 7, 0))
    assert w.rang == []
    assert env.press("alm:up:keep") == "OK, the alarm stays."


def test_skip_if_up_off_asks_nothing(alarm_world):
    env, a, w, wed, day_at = alarm_world
    env.app.settings.set("alarm.skip_if_up", False)
    w.t = day_at(wed, 6, 30)
    here.owner_here(env.app, "dashboard", at=w.t.timestamp())
    assert a.ask_skip() == ""


# ------------------------------------------------------------------------ L14: a short night and the alarm
def test_up_late_offers_a_later_ring_only_set_on_a_tap(alarm_world, monkeypatch):
    env, a, w, wed, day_at = alarm_world
    monkeypatch.setattr(a, "_first_class", lambda day: day_at(day, 11, 0))
    w.t = day_at(wed, 2, 0)  # up at 02:00 with the 07:00 alarm
    assert a.suggest_later() == ""  # no sign of you up
    here.owner_here(env.app, "dashboard", at=w.t.timestamp())
    text = a.suggest_later()
    assert "short night" in text and "first class is at 11:00" in text and "Ring at 09:30 instead?" in text
    assert a.suggest_later() == "" and a.next() == day_at(wed, 7, 0)  # once, and nothing moved by itself
    out = env.press(f"alm:{day_at(wed, 7, 0):%Y%m%d%H%M}-{day_at(wed, 9, 30):%Y%m%d%H%M}:later")
    assert "09:30" in out and a.next() == day_at(wed, 9, 30)


def test_no_offer_when_the_morning_isnt_known_free_or_switched_off(alarm_world, monkeypatch):
    env, a, w, wed, day_at = alarm_world
    w.t = day_at(wed, 2, 0)
    here.owner_here(env.app, "dashboard", at=w.t.timestamp())
    assert a.suggest_later() == ""  # no timetable: nothing says the morning is free
    monkeypatch.setattr(a, "_first_class", lambda day: day_at(day, 8, 0))
    assert a.suggest_later() == ""  # an 08:00 class: no later ring worth offering
    monkeypatch.setattr(a, "_first_class", lambda day: day_at(day, 12, 0))
    env.app.settings.set("alarm.sleep_aware", False)
    assert a.suggest_later() == ""


def test_a_short_night_is_said_coarsely_in_the_wake_up_script(alarm_world, monkeypatch):
    env, a, w, wed, day_at = alarm_world
    monkeypatch.setattr(sleep, "last_night", lambda app, t=None: (day_at(wed, 3, 30), day_at(wed, 7, 0)))
    monkeypatch.setattr(sleep, "on", lambda app: True)
    w.t = day_at(wed, 7, 0)
    script = a.script()
    assert "short night" in script and "03:30" not in script
    env.app.settings.set("alarm.sleep_aware", False)
    assert "short night" not in a.script()


def test_last_night_keeps_the_onset_it_fell_asleep_at(app, monkeypatch):
    at(monkeypatch, 2, 0, DAY + dt.timedelta(days=1))
    assert sleep.state(app) == "asleep"
    got = sleep.last_night(app)
    assert got == (dt.datetime(2026, 3, 10, 23, 30), dt.datetime(2026, 3, 11, 7, 0))


# =========================================================================================== desk Voice
@pytest.fixture
def spk(voice, monkeypatch):
    monkeypatch.setattr(voice, "tts", lambda: (Tts(), ""))
    voice.app.settings.set("voice.speak.join_sentences", False)  # one sound per sentence
    voice.speaker.player = Speakers()
    return voice.speaker.player


def answer(text="The library closes at nine.", quiet=False):
    job = SimpleNamespace(id="j1", lane="you", quiet=quiet, background=False)
    return job, SimpleNamespace(ok=True, text=text)


def read_all(voice, monkeypatch) -> list:
    said = []
    monkeypatch.setattr(voice.speaker, "say", lambda text, wait=True, rate=None: said.append(text) or (True, ""))
    voice.app.settings.set("voice.speak.what", "all")
    return said


# ------------------------------------------------------------------------------------- L138: read-all and Calm
def test_read_all_answers_follow_calms_spoken_rules(voice, monkeypatch):
    said = read_all(voice, monkeypatch)
    voice._job_done(*answer(), None)
    assert said == ["The library closes at nine."] and voice.spoken_why == "voice.read_all"
    voice.app.settings.set("notify.calm.stopped", ["voice.read_all"])  # Less of this -> Stop
    voice._job_done(*answer(), None)
    assert len(said) == 1
    voice._job_done(*answer(quiet=True), None)  # a quiet request (the talk box, a spoken one): never this path
    assert len(said) == 1
    r = voice.app.calm.reason("voice.read_all")
    assert r is not None and not r.counted


# ------------------------------------------------------------------------- L47 / L48: answers while you're away
def test_an_answer_held_while_away_is_offered_by_the_greeting_and_read_on_yes(voice, monkeypatch):
    said = read_all(voice, monkeypatch)
    voice.app.settings.set("face.away.hold_desktop", True)
    monkeypatch.setattr(voice.app, "away_from_desk", lambda: True)
    voice._job_done(*answer(), None)
    assert said == [] and list(voice.held_answers) == ["The library closes at nine."]
    t = dt.datetime(2026, 3, 10, 15, 0)
    text, parts = greet_mod.compose(["waiting", "answers"], [], (1, 0), None, 0, False, t, answers=1)
    assert parts == ["waiting", "answers"] and "One answer came while you were away; say yes to hear it." in text
    assert "Want to go through them?" not in text  # one yes, for the answers
    assert greet_mod.compose(["answers"], [], (0, 0), None, 0, False, t, answers=0)[1] == []
    voice.portal.invite(text, 12)
    assert voice.read_held("what's on today") is None
    assert voice.read_held("yes please") == "Here it is. The library closes at nine."
    assert not voice.held_answers and voice.read_held("yes") is None


def test_leaving_mid_answer_stops_it_only_when_switched_on(voice, spk, monkeypatch):
    monkeypatch.setattr(voice.app, "away_from_desk", lambda: True)
    voice.say("One. Two. Three.", wait=True)
    assert len(spk.got) == 3 and not voice.held_answers  # off by default: read to the end
    voice.app.settings.set("voice.speak.stop_when_gone", True)
    voice.say("Four. Five. Six.", wait=True)
    assert len(spk.got) == 4 and list(voice.held_answers) == ["Five. Six."]


# ---------------------------------------------------------------------------------------- L80: told off
def test_three_stops_over_its_greetings_offer_to_stop_them(voice, monkeypatch):
    sent = []
    monkeypatch.setattr(voice.app, "notify", lambda text, **kw: sent.append((text, kw)) or "m")
    calm_ = voice.app.calm
    assert not calm_.voice_stop("face.greet") and not calm_.voice_stop("face.greet")
    assert calm_.voice_stop("face.greet")
    text, kw = sent[-1]
    assert "told me to stop 3 times" in text and kw["why"] == "calm.voice_stops"
    assert kw["buttons"] == [[("Stop these", "calm:face.greet:apply"), ("Keep them", "calm:face.greet:no")]]
    assert voice.app.settings.get("face.greet.on") is True  # nothing applied by itself
    assert not calm_.voice_stop("face.greet")  # offered once in a while
    voice.app.settings.set("notify.calm.voice_stops", False)
    assert not calm_.voice_stop("face.greet")


def test_told_off_over_its_own_line_marks_it_not_over_an_answer(voice, monkeypatch):
    marks = []
    monkeypatch.setattr(voice.app.calm, "voice_stop", lambda why: marks.append(why) or False)
    voice.spoken_why = "face.greet"
    voice.speaker.until = time.monotonic()
    voice._told_off(Heard(speech=True), None)
    assert marks == ["face.greet"] and voice.spoken_why == ""
    voice.speaker.until = time.monotonic()  # it just answered you: spoken_why is ""
    voice._told_off(Heard(speech=True), None)
    assert marks == ["face.greet"]


# -------------------------------------------------------------------------------------- L139: two voices
def test_two_close_faces_and_a_guests_voice_are_two_voices(voice):
    now = time.monotonic()
    nearby.set_facing(voice.app, 2, 2, at=now - 0.5)
    guest, owner = SimpleNamespace(decision="guest"), SimpleNamespace(decision="owner")
    h = Heard(speech=True, seconds=2.0, ended_at=now)
    voice._count_voices(h, guest)
    assert h.voices is None  # off by default: as before
    voice.app.settings.set("voice.listen.count_voices", True)
    voice._count_voices(h, owner)
    assert h.voices is None  # your own voice never makes it two
    voice._count_voices(h, guest)
    assert h.voices == 2
    lone = Heard(speech=True, seconds=2.0, ended_at=now + 30)
    voice._count_voices(lone, guest)
    assert lone.voices is None  # no two faces in that stretch


# -------------------------------------------------------------------------------------------- L103: a tap
def test_a_tap_opens_the_portal_and_the_next_words_count(voice):
    p = voice.portal
    assert p.tapped() and not p.tapped()
    ctx = p.context()
    assert ctx.tapped and p.opened_why == "tapped"
    d = Gate(["Kurooto"], judge=lambda prompt: None).decide(
        Heard(speech=True, text="what's left on my list today"), ctx
    )
    assert d.addressed and d.why == "tapped"
    p.close("silence")
    assert not p.context().tapped
    voice.app.settings.set("voice.listen.tap_to_talk", False)
    assert voice.tapped() == (False, "off")


# --------------------------------------------------------------------------------------- N1: lines in Chat
def test_unasked_lines_go_to_chat_once_and_answers_dont(voice, spk, monkeypatch):
    chat = []
    monkeypatch.setitem(
        voice.app.modules, "calls", SimpleNamespace(chat=SimpleNamespace(say=lambda t, **kw: chat.append((t, kw))))
    )
    real = voice.app.is_on
    monkeypatch.setattr(voice.app, "is_on", lambda m: True if m == "calls" else real(m))
    voice.say("Ready when you are.", wait=True)  # said back to you: not mirrored
    assert chat == []
    voice.say("Your tea is probably cold.", wait=True, unprompted=True)
    assert chat == [("Your tea is probably cold.", {"title": "Said aloud at your desk"})]
    line = voice.unasked_line()
    assert "Your tea is probably cold." in line and voice.unasked_line() == ""  # once
    voice.app.settings.set("voice.mirror_to_chat", False)
    voice.say("Another line.", wait=True, unprompted=True)
    assert len(chat) == 1 and voice.unasked_line() == ""


# --------------------------------------------------------------------------- L37: a desk talk's after-pipeline
def test_a_desk_talk_leaves_threads_and_a_daily_line_when_it_closes(voice, monkeypatch):
    from kurooto.core import threads
    from kurooto.modules import daily

    seen = []
    monkeypatch.setattr(threads, "from_call", lambda app, lines: seen.append(lines) or [])
    p = voice.portal
    p.tapped()
    voice._talk_line("you", "I'll send the draft to Mira tonight")
    voice._talk_line(voice.app.name, "Noted.")
    voice.after_talk(list(voice._talk))
    assert seen and seen[0][0]["text"].startswith("I'll send the draft")
    note = daily.note_path(voice.app).read_text(encoding="utf-8")
    assert "## Desk talks" in note and "a talk at the desk (1 turn of yours)" in note and "Mira" not in note
    seen.clear()
    voice.after_talk([{"who": voice.app.name, "text": "Welcome back."}])  # nothing of yours: nothing kept
    assert seen == []


def test_after_talk_runs_on_close_only_when_switched_on(voice, monkeypatch):
    got = []
    monkeypatch.setattr(voice, "after_talk", lambda lines: got.append(lines))
    monkeypatch.setattr(voice_mod, "threading", SimpleNamespace(Thread=Inline))  # only the close runs here
    voice.portal.tapped()
    voice._talk_line("you", "what's left today")
    voice.portal.close("silence")
    assert got == [[{"who": "you", "text": "what's left today"}]] and voice._talk == []
    voice.app.settings.set("voice.listen.after_talk", False)
    voice.portal.tapped()
    voice._talk_line("you", "anything else")
    voice.portal.close("silence")
    assert len(got) == 1


class Inline:
    """threading.Thread, run at once (the after-talk work in these tests)."""

    def __init__(self, target, args=(), **kw):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)
