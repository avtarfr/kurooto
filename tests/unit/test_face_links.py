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
