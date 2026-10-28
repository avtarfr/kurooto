"""Face presence's links (0.9.0): the look's centre beside the lens, the greeting's name, strangers while you're away,
phone places, learning from a Voice ID turn, greeting records, the room's light, and the greeting's add-on hooks.
Fakes only: no camera or microphone is opened, nothing reads the real install, no AI is asked."""

# ruff: noqa: F811 (the fixtures imported from the other tests are taken as arguments)

import math

from kurooto.modules.face.vision import YAW_K
from tests.unit.test_face import app  # noqa: F401 (pytest fixtures)


def yaw_for(deg: float) -> float:
    """pose()'s yaw for a head turned this many degrees (+: to your right)."""
    return YAW_K * math.tan(math.radians(deg))


# ------------------------------------------------------------------------- L102 the look's centre beside the lens
def test_the_look_centres_on_the_yaw_offset(app):
    f = app.modules["face"]
    app.settings.set("voice.listen.look_to_talk", True)
    assert f.yaw_offset() == 0.0
    assert f.looking((140.0, yaw_for(0), 0.5)) and not f.looking((140.0, yaw_for(20), 0.5))
    app.settings.set("face.camera.yaw_offset_deg", 20)  # the spot to look at sits 20 degrees to your right
    assert f.looking((140.0, yaw_for(20), 0.5)) and f.looking((140.0, yaw_for(28), 0.5))
    assert not f.looking((140.0, yaw_for(0), 0.5))  # straight at the lens is beside the spot now
    app.settings.set("face.camera.yaw_offset_deg", 90)  # clamped
    assert f.yaw_offset() == 30.0
    app.settings.set("face.camera.yaw_offset_deg", "x")
    assert f.yaw_offset() == 0.0


def test_the_eyes_path_centres_on_the_offset_too(app):
    f = app.modules["face"]
    cal = {"h": 0.05, "v": 0.02, "yaw": 0.0, "pitch": 0.5, "n": 15, "at": 1}
    eyes = (cal["h"], cal["v"])  # the eyes where they were when calibrated, on the lens
    assert f._looking_by_eyes(0.0, 0.5, eyes, cal)
    app.settings.set("face.camera.yaw_offset_deg", -20)
    assert not f._looking_by_eyes(0.0, 0.5, eyes, cal)
    assert f._looking_by_eyes(yaw_for(-20), 0.5, eyes, cal)  # the head turned 20 degrees to the left: on the spot


# --------------------------------------------------------------------------------- L6 your card's name and avoid line
def test_the_greeting_says_your_name_alone_and_never_loses_a_part_for_it():
    from kurooto.modules.face import greet as gr
    from tests.unit.test_face import ITEMS, NOW

    t, p = gr.compose(["next"], ITEMS, (0, 0), None, 0, False, NOW, name="Sam")
    assert t.startswith("Welcome back, Sam. Next: Linear Algebra") and p == ["next"]
    t, _ = gr.compose(["waiting"], [], (1, 0), None, 0, False, NOW.replace(hour=9), first_today=True, name="Sam")
    assert t.startswith("Morning, Sam. One question")
    assert gr.compose(["next"], ITEMS, (0, 0), None, 0, True, NOW, with_others="full", name="Sam")[0].startswith(
        "Welcome back. Next"
    )  # someone else in view: no name, even with full
    assert gr.compose(["next"], ITEMS, (0, 0), None, 0, True, NOW, with_others="short", name="Sam")[0] == (
        "Welcome back."
    )
    # a greeting at exactly 220 characters: the name doesn't count, so no part goes for it
    args = (["next", "waiting", "deadline", "held"], ITEMS, (2, 1), ("x" * 35, NOW.replace(hour=23)), 3, False, NOW)
    plain, parts = gr.compose(*args)
    named, parts2 = gr.compose(*args, name="Alexandra")
    assert len(plain) == gr.MAX_CHARS and parts == parts2 == ["next", "waiting", "deadline", "held"]
    assert named == plain.replace("Welcome back.", "Welcome back, Alexandra.", 1)


def test_persona_templates_name_and_avoid_line(app):
    from kurooto.core import persona

    assert persona.address(app) == "" and persona.template(app, "Welcome back!") == "Welcome back!"
    persona.save(app, {"call_me": "Sam", "avoid": "exclamation marks, emojis"})
    assert persona.address(app) == "Sam"
    assert persona.template(app, "Welcome back! \u2600\ufe0f Next: maths.") == "Welcome back. Next: maths."
    persona.save(app, {"avoid": "pep talk"})  # nothing a template can honour: unchanged, nothing dropped
    assert persona.template(app, "Two questions wait for you!") == "Two questions wait for you!"
    app.settings.set("persona.templates", False)
    assert persona.address(app) == "" and persona.template(app, "a!") == "a!"


def test_the_spoken_greeting_uses_the_card(app, monkeypatch):
    from kurooto.core import nearby, persona
    from tests.unit.test_face import FakeVoice

    v = FakeVoice()
    monkeypatch.setitem(app.modules, "voice", v)
    app.settings.set("modules.enabled", ["face", "voice"])
    app.settings.set("face.watch.night", True)
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00", "alarm_only": False})
    persona.save(app, {"call_me": "Sam"})
    f = app.modules["face"]
    assert f.greet() and ", Sam." in v.said[-1][0]
    f._greets = {}
    nearby.set_others(app, "test", True)  # someone else in view now: no name
    app.settings.set("face.greet.with_others", "full")
    assert f.greet() and "Sam" not in v.said[-1][0]
    nearby.set_others(app, "test", False)
    f._greets = {}
    app.settings.set("persona.templates", False)
    assert f.greet() and "Sam" not in v.said[-1][0]


def test_check_in_openers_keep_their_start_for_the_phone_card(app):
    from kurooto.core import persona

    ck = app.modules["checkins"]
    persona.save(app, {"call_me": "Sam", "avoid": "exclamation marks"})
    assert ck._worded("Evening check-in: How was it!") == "Evening check-in: How was it."


def test_i_m_awake_says_your_name(app, monkeypatch):
    from types import SimpleNamespace

    from kurooto.core import persona

    al = app.modules["alarm"]
    monkeypatch.setitem(app.modules, "calls", SimpleNamespace(place=lambda *a, **k: None))
    monkeypatch.setattr(al, "open_morning_page", lambda: False)
    monkeypatch.setattr(al, "next", lambda: None)
    assert al.up("I'm up").startswith("Good morning. Calling you")
    persona.save(app, {"call_me": "Sam"})
    assert al.up("I'm up").startswith("Good morning, Sam. Calling you")


# ------------------------------------------------------------------------ L21 someone else while you're away
def test_the_watcher_says_how_many_strangers_only_while_you_re_away():
    from tests.unit.test_face import W, face, frame, rvec

    strangers = [frame([face(dx=i * 3.0), face(x=40.0, dx=i * 3.0)], [rvec(), rvec()]) for i in range(20)]
    t = W(strangers)
    t.run(3)
    assert "strangers" not in t.kinds()  # here: nothing noted
    t.w.away = True
    t.run(3)
    got = [f for k, f in t.got if k == "strangers"]
    assert got and all(f == {"n": 2} for f in got)  # a count, nothing about the faces


def test_strangers_while_away_are_told_once_on_your_return_as_times_only(app, monkeypatch):
    import time

    f = app.modules["face"]
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    f._on_watch("strangers", n=2)
    assert f._others_away == {}  # off by default: nothing is kept
    app.settings.set("face.away.report_others", True)
    now = [1_800_000_000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    f._on_watch("strangers", n=1)
    f._on_watch("strangers", n=2)  # the same minute: one time, the most faces
    now[0] += 900
    f._on_watch("strangers", n=1)
    f._on_watch("back")
    assert len(sent) == 1
    text, kw = sent[0]
    assert kw["why"] == "face.away.others" and "(2 faces)" in text and " and " in text and "doesn't know who" in text
    ev = [e for e in app.events.tail(50) if e["kind"] == "face_away_others"][-1]
    assert set(ev) <= {"ts", "kind", "count"} and ev["count"] == 2
    f._on_watch("back")
    assert len(sent) == 1  # told once, then forgotten
    f._on_watch("strangers", n=1)
    app.settings.set("face.away.report_others", False)
    assert not f.report_others() and f._others_away == {}  # turned off meanwhile: dropped, not told


def test_an_arrival_also_tells_and_forget_drops_them(app, monkeypatch):
    f = app.modules["face"]
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append(text))
    monkeypatch.setattr(f, "greet", lambda others=False: False)
    app.settings.set("face.away.report_others", True)
    f._on_watch("strangers", n=1)
    f._arrived(30, False)
    assert len(sent) == 1
    f._on_watch("strangers", n=1)
    f.forget()
    assert f._others_away == {}
    import time

    now = [1_800_000_000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    for _ in range(200):
        now[0] += 60
        f._stranger_seen(1)
    assert len(f._others_away) == 120 and min(f._others_away) == int(now[0] // 60) - 119  # the oldest went first


def test_the_message_has_a_calm_reason():
    from kurooto.core import calm

    r = calm.REASONS["face.away.others"]
    assert r.setting == "face.away.report_others" and r.feature == "face"


# ------------------------------------------------------------------------------ L20 your phone's saved places
def test_the_phone_out_signal_is_a_time_only_and_runs_out():
    import time
    from types import SimpleNamespace

    from kurooto.core import nearby

    a = SimpleNamespace()
    assert nearby.phone_out(a) is None
    nearby.set_phone_out(a, True)
    assert nearby.phone_out(a) is not None
    nearby.set_phone_out(a, False)
    assert nearby.phone_out(a) is None
    nearby.set_phone_out(a, True, at=time.time() - nearby.PHONE_OUT_MAX_S - 1)
    assert nearby.phone_out(a) is None  # never heard back from: it stops counting


def test_the_phone_leaving_a_place_marks_you_away_at_once_only_with_its_switches(app):
    from kurooto.core import nearby
    from tests.unit.test_face import W, mine

    f = app.modules["face"]
    t = W(mine(10))
    t.w.emit = f._on_watch
    f.watcher = t.w
    assert not f.phone_place("leave")  # off by default
    app.settings.set("face.away.use_places", True)
    assert not f.phone_place("leave")  # needs noticing when you leave (face.away.on)
    app.settings.set("face.away.on", True)
    assert not f.phone_place("arrive") and not t.w.away  # arriving says nothing about the desk
    assert f.phone_place("leave") and t.w.away and f.away_now()
    assert [e["kind"] for e in app.events.tail(20)].count("face_left") == 1
    assert not f.phone_place("leave")  # away already
    nearby.set_phone_out(app, True)
    t.w._input(t.clock(), t.cfg)  # someone types at the desk: back, and the phone's "out" is over
    assert not t.w.away and nearby.phone_out(app) is None


def test_closing_the_camera_while_the_phone_is_out_is_its_own_switch(app):
    from kurooto.core import nearby

    f = app.modules["face"]
    nearby.set_phone_out(app, True)
    assert not f._phone_out()
    app.settings.set("face.away.use_places", True)
    assert not f._phone_out()  # marking away doesn't close the camera by itself
    app.settings.set("face.away.places_close_camera", True)
    assert f._phone_out()
    names = [n for n, check in f.pause_checks()]
    assert "your phone is out" in names
    nearby.set_phone_out(app, False)
    assert not f._phone_out()


def test_the_senses_hand_a_fresh_place_event_on_and_never_its_label(app, monkeypatch):
    import time

    from kurooto import mind
    from kurooto.core import nearby
    from kurooto.mind.senses import phone

    monkeypatch.setattr(mind, "on", lambda a: True)
    app.settings.set("mind.senses.phone.places", True)
    app.settings.set("modules.enabled", ["face"])
    told = []
    monkeypatch.setattr(app.modules["face"], "phone_place", lambda event: told.append(event))
    now_ms = int(time.time() * 1000)
    phone.ingest(app, {"bins": [{"s": "places", "t": now_ms - 3600_000, "event": "leave", "label": "home"}]})
    assert told == [] and nearby.phone_out(app) is None  # an hour old: history, not news
    phone.ingest(app, {"bins": [{"s": "places", "t": now_ms, "event": "leave", "label": "home"}]})
    assert told == ["leave"] and nearby.phone_out(app) is not None
    assert "home" not in repr(getattr(app, "_nearby_phone", None))
    phone.ingest(app, {"bins": [{"s": "places", "t": now_ms, "event": "arrive", "label": "home"}]})
    assert told == ["leave", "arrive"] and nearby.phone_out(app) is None


def test_voice_stops_listening_while_the_phone_is_out_only_when_asked(tmp_path, monkeypatch):
    from kurooto.core import nearby
    from tests.unit.test_voice import Live

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    v = a.modules["voice"]
    monkeypatch.setattr(v.parts, "missing", lambda keys: [])
    monkeypatch.setattr(v, "_on_call", lambda: False)
    monkeypatch.setattr(v, "_night", lambda: False)
    a.live = Live()
    a.settings.set("voice.listen.on", True)
    try:
        nearby.set_phone_out(a, True)
        assert v.blocked() != "your phone is out"
        a.settings.set("voice.listen.phone_away", True)
        assert v.blocked() == "your phone is out"
        nearby.set_phone_out(a, False)
        assert v.blocked() != "your phone is out"
    finally:
        a.close()


# ------------------------------------------------------------------------- L23 learning from a Voice ID turn
def test_the_watcher_hands_a_recent_clear_frame_of_you_alone_only():
    from tests.unit.test_face import W, face, frame, mine, rvec, you

    t = W(mine(10))
    t.run(2)
    assert t.w.voice_candidate() is not None
    t.clock.t += 4  # too old
    assert t.w.voice_candidate() is None
    two = [frame([face(dx=i * 3.0), face(x=40.0, dx=i * 3.0)], [you(), rvec()]) for i in range(10)]
    t2 = W(two)
    t2.run(2)
    assert t2.w.voice_candidate() is None  # someone else in view
    t3 = W(mine(10))
    t3.w.learnable = lambda e: False  # not confident enough
    t3.run(2)
    assert t3.w.voice_candidate() is None


def test_a_voice_id_turn_learns_only_under_its_switches_with_only_you_in_view(app, monkeypatch):
    from types import SimpleNamespace

    from kurooto.core import nearby

    f = app.modules["face"]
    learned = []
    monkeypatch.setattr(f, "learn", lambda e: learned.append(e) or True)
    f.watcher = SimpleNamespace(voice_candidate=lambda: [0.1, 0.2])
    nearby.set_view(app, 1, True)
    assert not f.learn_from_voice()  # learn.on off
    app.settings.set("face.learn.on", True)
    assert not f.learn_from_voice()  # from_voice off
    app.settings.set("face.learn.from_voice", True)
    assert f.learn_from_voice() and learned == [[0.1, 0.2]]
    nearby.set_view(app, 2, False)
    assert not f.learn_from_voice()
    nearby.set_view(app, 1, True)
    nearby.set_others(app, "voice", True)
    assert not f.learn_from_voice()
    nearby.set_others(app, "voice", False)
    f.watcher = SimpleNamespace(voice_candidate=lambda: None)
    assert not f.learn_from_voice() and len(learned) == 1


def test_voice_asks_face_to_learn_only_for_a_sure_owner_voice(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    try:
        v = a.modules["voice"]
        asked = []
        monkeypatch.setitem(a.modules, "face", SimpleNamespace(learn_from_voice=lambda: asked.append(1)))
        v._face_learn()
        assert asked == []  # Face presence off
        a.settings.set("modules.enabled", ["face"])
        v._face_learn()
        assert asked == [1]
    finally:
        a.close()
    import inspect

    from kurooto.modules import voice as voice_mod

    src = inspect.getsource(voice_mod.Voice)
    assert 'who.decision == "owner" and not who.assisted' in src  # a face-assisted verdict never teaches the face


# ------------------------------------------------------------------------------ L100 the greeting's records
def brain_on(app, monkeypatch):
    """Brain on, its scorekeeper replaced by a list of what it was handed."""
    from kurooto import mind

    got = []
    monkeypatch.setattr(mind, "on", lambda a: True)
    monkeypatch.setattr(mind.connect(app), "report", lambda kind, body: got.append((kind, body)) or True)
    return got


def greeting_app(app, monkeypatch):
    from tests.unit.test_face import FakeVoice

    v = FakeVoice()
    monkeypatch.setitem(app.modules, "voice", v)
    app.settings.set("modules.enabled", ["face", "voice"])
    app.settings.set("face.watch.night", True)
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00", "alarm_only": False})
    return app.modules["face"], v


def test_a_greeting_is_a_decision_closed_by_whether_you_answered(app, monkeypatch):
    from kurooto.mind import records

    got = brain_on(app, monkeypatch)
    f, _v = greeting_app(app, monkeypatch)
    assert f.greet()
    kind, rec = got[0]
    assert kind == "decision" and rec["action"] == "speak:face.greet" and rec["source"] == "rules"
    assert rec["scored_reason"].startswith("a greeting at the desk") and rec["expect"]["what"] == "reply"
    rows = records._load(app)["rows"]
    assert rows[-1]["id"] == rec["id"] and rows[-1]["why"] == "face.greet" and f._greet_rec == rec["id"]
    f.greet_closed(True)
    assert got[-1] == ("decision_outcome", {"decision": rec["id"], "result": "replied", "value": 1.0})
    ev = [e for e in app.events.tail(30) if e["kind"] == "face_greet_outcome"][-1]
    assert ev["result"] == "replied" and f._greet_rec == ""
    f.greet_closed(False)  # nothing open: nothing more
    assert len(got) == 2


def test_an_unanswered_greeting_is_missed_and_the_switch_stops_it(app, monkeypatch):
    got = brain_on(app, monkeypatch)
    f, _v = greeting_app(app, monkeypatch)
    assert f.greet()
    f.greet_closed(False)
    assert got[-1][1]["result"] == "missed"
    f._greets = {}
    app.settings.set("face.greet.records", False)
    n = len(got)
    assert f.greet() and len(got) == n and f._greet_rec == ""
    assert f.tunable == {}
    app.settings.set("face.greet.records", True)
    assert list(f.tunable) == ["face.greet.gap_min"]


def test_with_brain_off_nothing_is_recorded(app, monkeypatch):
    from kurooto.mind import records

    f, _v = greeting_app(app, monkeypatch)
    assert f.greet() and f._greet_rec == "" and records._load(app)["rows"] == []


def test_the_look_back_sees_greetings_and_may_tune_only_the_gap(app):
    import datetime as dt

    retro = app.modules["retro"]
    app.events.emit("face_greeted", parts=["next"], talk=True)
    app.events.emit("face_greet_outcome", result="missed")
    since = dt.datetime.now() - dt.timedelta(hours=1)
    ev = retro.evidence(since)
    assert "face_greet_outcome result=missed" in ev and "face_greeted parts=['next']" in ev
    app.settings.set("modules.enabled", ["face"])
    assert retro.tunable()["face.greet.gap_min"].endswith("(number)") and "face.greet.say" not in retro.tunable()
    app.settings.set("face.greet.records", False)
    assert "face_greet_outcome result=" not in retro.evidence(since)  # only counted, as every event is
    assert "face.greet.gap_min" not in retro.tunable()


def test_the_portal_counts_turns_per_conversation():
    from kurooto.modules.voice.gate import ADDRESSED, Decision, Heard
    from kurooto.modules.voice.portal import Portal

    closed = []

    def changed(is_open, why):
        if not is_open:
            closed.append((is_open, p.opened_why, p.turns))

    p = Portal(send=lambda t: "ok", speak=lambda t: None, publish=lambda *a, **k: None, clock=lambda: 0.0)
    p.on_change = changed
    p.invite("Welcome back.", 12)
    assert p.open and p.turns == 0 and p.opened_why == "greeting"
    p.take(Heard(True, "what's next"), Decision(ADDRESSED, 0.9, "a question"))
    assert p.turns == 1
    p.close("silence")
    assert closed == [(False, "greeting", 1)]  # on_change still sees the closing conversation's turns


# ------------------------------------------------------------------------------------- L120 the room's light
def test_the_watcher_hands_the_frame_s_brightness_only_when_asked():
    from tests.unit.test_face import W, mine

    t = W(mine(10))
    t.run(2)
    assert "light" not in t.kinds()
    t.cfg["light"] = True
    t.run(2)
    got = [f for k, f in t.got if k == "light"]
    assert got and all(set(f) == {"mean"} and f["mean"] == 110.0 for f in got)  # a number, nothing else


def test_the_light_level_is_smoothed_switchable_and_goes_stale(app, monkeypatch):
    import time

    f = app.modules["face"]
    app.settings.set("modules.enabled", ["face"])
    f._on_watch("light", mean=255.0)
    assert f.light_level() is None  # off by default: nothing kept
    app.settings.set("face.light_sense", True)
    assert f._watch_cfg()["light"] is True
    f._on_watch("light", mean=0.0)
    assert f.light_level() == 0.0
    f._on_watch("light", mean=255.0)
    assert 0.0 < f.light_level() < 0.5  # smoothed: one bright frame moves it a fifth of the way
    real = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real() + 1000)
    assert f.light_level() is None  # the camera stopped looking: not the room's any more
    monkeypatch.setattr(time, "monotonic", real)
    app.settings.set("face.light_sense", False)
    assert f.light_level() is None


def test_brain_s_body_takes_the_camera_s_light_only_without_a_device_s(app, monkeypatch):
    from types import SimpleNamespace

    from kurooto.mind import stimulation

    monkeypatch.setitem(app.modules, "face", SimpleNamespace(light_level=lambda: 0.4))
    x = {}
    stimulation._webcam(app, x)
    assert x["brightness"] == stimulation.WEBCAM_SCALE * 0.4
    x = {"brightness": 2.0}  # an add-on's lux was fed in: it wins
    stimulation._webcam(app, x)
    assert x["brightness"] == 2.0
    monkeypatch.setitem(app.modules, "face", SimpleNamespace(light_level=lambda: None))
    x = {}
    stimulation._webcam(app, x)
    assert x == {}


# ------------------------------------------------------------------------- L105 an add-on's line in the greeting
def test_compose_says_add_on_lines_last_and_drops_them_first():
    from kurooto.modules.face import greet as gr
    from tests.unit.test_face import ITEMS, NOW

    t, p = gr.compose(["next"], ITEMS, (0, 0), None, 0, False, NOW, extra=[("addon:interest", "The run stalled.")])
    assert t.endswith("Next: Linear Algebra at 14:00, in 40 minutes. The run stalled.")
    assert p == ["next", "addon:interest"]
    args = (["next", "waiting", "deadline", "held"], ITEMS, (2, 1), ("x" * 35, NOW.replace(hour=23)), 3, False, NOW)
    plain, parts = gr.compose(*args)  # exactly at the limit
    t2, p2 = gr.compose(*args, extra=[("addon:interest", "Something long enough to go over.")])
    assert t2 == plain and p2 == parts  # the add-on's line went; nothing of the built-in parts did


def test_an_add_on_line_needs_its_switch_and_says_whether_it_was_carried(app, monkeypatch):
    import time

    from kurooto.core import nearby

    f, v = greeting_app(app, monkeypatch)
    unsub = f.greet_part("Interest", lambda: "the training run stalled at 03:10")
    start = time.time()
    assert f.greet() and "stalled" not in v.said[-1][0]  # face.greet.addons is off
    assert not f.greet_carried("interest", start)
    app.settings.set("face.greet.addons", True)
    f._greets = {}
    assert f.greet() and v.said[-1][0].endswith("the training run stalled at 03:10.")
    assert f.greet_carried("interest", start)
    ev = [e for e in app.events.tail(20) if e["kind"] == "face_greeted"][-1]
    assert "addon:interest" in ev["parts"] and "stalled" not in str(ev)
    f._greets = {}
    nearby.set_others(app, "test", True)
    app.settings.set("face.greet.with_others", "full")
    later = time.time() + 1
    f._carried.clear()
    assert f.greet() and "stalled" not in v.said[-1][0] and not f.greet_carried("interest", later)
    nearby.set_others(app, "test", False)
    unsub()
    f._greets = {}
    assert f.greet() and "stalled" not in v.said[-1][0]
    f.greet_part("broken", lambda: 1 / 0)
    f._greets = {}
    assert f.greet()  # a failing add-on doesn't stop the greeting


# ----------------------------------------------------------------------------------- L108 known guests
def test_a_known_guest_gets_the_short_greeting_instead_of_none(app, monkeypatch):
    f, v = greeting_app(app, monkeypatch)
    assert not f.greet(others=True)  # skip, as before
    known = [True]
    unsub = f.known_guests(lambda: known[0])
    assert f.greet(others=True) and v.said[-1] == ("Welcome back.", False)  # short: no details, no talk
    f._greets = {}
    known[0] = False
    assert not f.greet(others=True)
    known[0] = True
    app.settings.set("face.addons.known_guests", False)
    assert not f.greet(others=True)
    app.settings.set("face.addons.known_guests", True)
    unsub()
    assert not f.greet(others=True)
    f.known_guests(lambda: 1 / 0)
    assert not f.known_guest()  # a failing add-on counts as nobody known
