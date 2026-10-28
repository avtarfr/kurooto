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
