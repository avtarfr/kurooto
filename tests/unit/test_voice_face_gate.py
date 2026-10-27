"""Only someone in front of it (0.8.13, voice.listen.need_face): a turn is addressed only when Face presence saw a
face close to the camera and facing it around the stretch; the camera is held while Voice listens; when it can't see,
need_face_fallback decides. Fakes only: no microphone or camera is opened, nothing reads the real install."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import time

import pytest

from kurooto.core import nearby
from kurooto.modules import voice as voice_mod
from kurooto.modules.face.vision import yaw_degrees
from kurooto.modules.voice.gate import Heard
from tests.unit.test_face import W, face, frame, you
from tests.unit.test_voice import Judge, everything_kept, voice  # noqa: F401 (pytest fixtures)

AGO = 4.0  # the stretch ended this long ago: past its whole window (FACE_AFTER_S + FACE_SLOW_S), so nothing waits
SECONDS = 2.0


class Listener:
    def __init__(self):
        self.on = True
        self.error = ""

    def running(self):
        return self.on

    def stop(self):
        self.on = False


@pytest.fixture
def fv(voice, monkeypatch):
    """Voice listening with Face presence on and enrolled (its pause reason in fv.paused)."""
    app = voice.app
    f = app.modules["face"]
    real = app.is_on
    on = {"face": True}
    monkeypatch.setattr(app, "is_on", lambda mid: on["face"] if mid == "face" else real(mid))
    monkeypatch.setattr(f, "enrolled", lambda: True)
    monkeypatch.setattr(f, "reenrol_needed", lambda: False)
    paused = [""]
    monkeypatch.setattr(f, "pause_reason", lambda: paused[0])
    monkeypatch.setattr(f, "owner_desk_height", lambda: {"px": 140.0, "h": 0.29, "n": 20, "from": "seen"})
    voice.blocked_why = ""
    voice.paused, voice.face_on, voice.f = paused, on, f
    return voice


def look(app, at, faces=1, facing=1):
    nearby.set_facing(app, faces, facing, at=at)


def turn(v, text, ago=AGO, seconds=SECONDS, wake=False, sight=None):
    """One stretch that ended `ago` seconds ago. sight: (faces, facing) for a frame looked at in the middle of it."""
    end = time.monotonic() - ago
    if sight is not None:
        look(v.app, end - seconds / 2, *sight)
    return v.hear(Heard(speech=True, text=text, seconds=seconds, wake=wake, ended_at=end))


def events(v, kind):
    return [e for e in v.app.events.tail(100) if e["kind"] == kind]


# ------------------------------------------------------------------------------------------ the record (nearby)
def test_nearby_keeps_frames_as_times_and_counts_only(voice):
    app = voice.app
    now = time.monotonic()
    look(app, now - 10, 1, 1)
    look(app, now - 3, 2, 0)
    look(app, now - 2, 1, 1)
    assert nearby.facing(app, now - 4, now) == (2, 1)
    assert nearby.facing(app, now - 4, now - 2.5) == (1, 0)
    assert nearby.facing(app, now - 1, now) == (0, 0)
    assert nearby.last_facing(app) == pytest.approx(now - 2)
    look(app, now - 30, 1, 1)  # an older frame doesn't move the last sighting back
    assert nearby.last_facing(app) == pytest.approx(now - 2)
    assert all(len(r) == 3 and all(isinstance(x, (int, float)) for x in r) for r in app._nearby_looks)


# ----------------------------------------------------------------------------------- close and facing (Face)
def test_yaw_degrees_follows_the_pose_scale():
    assert yaw_degrees(0) == 0
    assert yaw_degrees(0.3) == pytest.approx(25, abs=0.01) and yaw_degrees(-0.3) == pytest.approx(25, abs=0.01)
    assert 30 < yaw_degrees(0.4) < 35 < yaw_degrees(0.5)


def test_face_counts_close_and_facing_faces(fv):
    f, app = fv.f, fv.app
    assert f.close_facing([(140.0, 0.0)]) == 1  # at the desk, looking at it
    assert f.close_facing([(150.0, -0.2)]) == 1  # a little turned
    assert f.close_facing([(60.0, 0.0)]) == 0  # across the room: under half the desk height
    assert f.close_facing([(140.0, 0.6)]) == 0  # side-on (about 43 degrees)
    assert f.close_facing([(140.0, None)]) == 0  # no landmarks: not facing
    assert f.close_facing([(140.0, 0.0), (60.0, 0.0), (140.0, 0.7)]) == 1
    assert f.close_facing([]) == 0
    app.settings.set("voice.listen.face_yaw_deg", 50)
    assert f.close_facing([(140.0, 0.6)]) == 1
    app.settings.set("voice.listen.face_near", 0.4)
    assert f.close_facing([(60.0, 0.0)]) == 1


def test_without_a_desk_height_the_smallest_judged_face_stands_in(fv, monkeypatch):
    f = fv.f
    monkeypatch.setattr(f, "owner_desk_height", lambda: None)
    assert f.close_facing([(61.0, 0.0)]) == 1 and f.close_facing([(50.0, 0.0)]) == 0


def test_each_frame_s_faces_reach_nearby_as_counts(fv):
    f, app = fv.f, fv.app
    f._on_watch("view", faces=2, owner_alone=False, sizes=[(140.0, 0.0), (55.0, 0.1)])
    f._on_watch("view", faces=1, owner_alone=False, sizes=[(55.0, 0.1)])
    assert nearby.facing(app, time.monotonic() - 5) == (2, 1)
    f._on_watch("view", faces=1, owner_alone=True)  # an older watcher without sizes: a frame with nobody facing
    assert nearby.facing(app, time.monotonic() - 5) == (3, 1)


def test_the_watcher_hands_each_face_s_height_and_yaw_with_the_view():
    t = W([frame([face(yaw=0.3), face(x=500, h=70, yaw=0.0, score=0.7)], [you(), you()])] * 3)
    t.run(2)
    views = [f for k, f in t.got if k == "view"]
    assert views
    sizes = views[0]["sizes"]
    assert len(sizes) == 2 and sizes[0][0] == 140.0 and sizes[0][1] == pytest.approx(0.3, abs=0.01)
    assert sizes[1] == (70.0, pytest.approx(0.0, abs=0.01))
    assert all(len(s) == 2 for s in sizes)  # height and yaw: never numbers that say who


# -------------------------------------------------------------------------------------------- the voice gate
def test_a_face_close_and_facing_lets_the_turn_through(fv):
    assert turn(fv, "Kurooto, what's due this week?", sight=(1, 1)) == "It's due Friday."
    assert fv.brain.got == ["what's due this week?"]
    assert fv.face_counts == {"no_face": 0, "blind": 0}


def test_a_face_just_after_the_stretch_counts(fv):
    end = time.monotonic() - AGO
    look(fv.app, end + 1.0)
    assert fv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=SECONDS, ended_at=end))
    fv.portal.close("test")
    end -= 10
    look(fv.app, end + 2.5, 1, 1)  # too late for this stretch
    look(fv.app, end - SECONDS / 2, 1, 0)  # the camera looked during it: nobody facing it
    assert fv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=SECONDS, ended_at=end)) is None


@pytest.mark.parametrize(
    "sight,why",
    [((1, 0), "far or side-on"), ((0, 0), "nobody in view"), ((2, 0), "two people, neither facing it")],
)
def test_no_face_close_and_facing_is_chatter(fv, sight, why):
    assert turn(fv, "Kurooto, what's due this week?", sight=sight) is None, why
    assert fv.brain.got == [] and not fv.portal.open
    assert fv.heard["chatter"] == 1 and fv.heard["addressed"] == 0 and fv.face_counts["no_face"] == 1
    portal = events(fv, "voice_portal")
    assert not portal or all(e.get("open") is not True for e in portal)


def test_far_and_side_on_faces_from_the_frames_themselves(fv):
    end = time.monotonic() - AGO
    f = fv.f
    f._on_watch("view", faces=1, owner_alone=False, sizes=[(55.0, 0.0)])  # now, not in the window: no frame there
    nearby.set_facing(fv.app, 1, f.close_facing([(55.0, 0.0)]), at=end - 1)  # across the room
    nearby.set_facing(fv.app, 1, f.close_facing([(150.0, 0.65)]), at=end - 0.5)  # at the desk, turned away
    assert fv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=SECONDS, ended_at=end)) is None
    nearby.set_facing(fv.app, 1, f.close_facing([(150.0, 0.1)]), at=end - 0.2)
    assert fv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=SECONDS, ended_at=end)) is not None


def test_a_phone_call_across_the_room_is_never_sent_or_kept(fv):
    fv.judge.answers = ['{"class": "addressed", "confidence": 0.95}'] * 3
    secret = "yeah I'll send you the locker code later, it's four four seven one"
    assert turn(fv, f"Kurooto, {secret}", sight=(1, 0)) is None  # its name in a call, the caller across the room
    assert turn(fv, "can you hear me now?", sight=(0, 0)) is None  # a question the model would take
    assert fv.brain.got == [] and fv.judge.prompts != []
    assert "four four seven" not in everything_kept(fv) and "locker" not in everything_kept(fv)
    assert "locker" not in str(fv.app.events.tail(200))


def test_the_conversation_going_on_needs_a_face_too(fv):
    assert turn(fv, "Kurooto, what's due this week?", ago=12, sight=(1, 1))
    assert fv.portal.open
    assert turn(fv, "and the one after that", sight=(1, 0)) is None  # he turned away: someone else's words
    assert fv.brain.got == ["what's due this week?"] and not fv.portal.open


def test_the_wake_word_and_the_request_after_it_need_no_face(fv):
    assert turn(fv, "", wake=True, sight=(0, 0)) is None and fv.portal.open and fv.portal.awaiting
    assert fv.spoken == ["Yes?"]
    assert turn(fv, "what's due this week", sight=(0, 0)) == "It's due Friday."
    assert fv.brain.got == ["what's due this week"]


def test_after_its_name_alone_the_request_still_needs_a_face(fv):
    assert turn(fv, "Kurooto", ago=12, sight=(1, 1)) is None and fv.portal.awaiting
    assert turn(fv, "what's due this week", sight=(1, 0)) is None and fv.brain.got == []


def test_told_off_works_without_a_face(fv):
    stopped = []
    fv.speaker.stop = lambda: stopped.append(1)
    assert turn(fv, "Kurooto, what's due this week?", sight=(1, 1))
    assert turn(fv, "stop", sight=(0, 0)) is None
    assert stopped and not fv.portal.open and len(events(fv, "voice_misfire")) == 1


def test_a_face_that_turns_up_while_it_waits_counts(fv):
    end = time.monotonic()  # just ended: the window runs FACE_AFTER_S on
    waits = []

    def sleep(s):
        waits.append(s)
        if len(waits) == 3:
            look(fv.app, time.monotonic())

    fv._face_sleep = sleep
    assert fv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=SECONDS, ended_at=end))
    assert len(waits) == 3 and all(0 < s <= 0.1 for s in waits)


# -------------------------------------------------------------------------------------- the switches, fallback
def test_the_switch_off_or_face_presence_off_is_the_voice_rules_as_before(fv):
    fv.app.settings.set("voice.listen.need_face", False)
    assert turn(fv, "Kurooto, what's due this week?", sight=(0, 0))
    assert fv.face_gate() == ("off", "") and fv.face_line() == ""
    fv.portal.close("test")
    fv.app.settings.set("voice.listen.need_face", True)
    fv.face_on["face"] = False
    assert turn(fv, "Kurooto, what's due this week?", sight=(0, 0))
    assert fv.status()["need_face"]["state"] == "off" and len(fv.brain.got) == 2


def test_not_enrolled_it_does_nothing(fv, monkeypatch):
    monkeypatch.setattr(fv.f, "enrolled", lambda: False)
    assert fv.face_gate() == ("off", "")
    assert turn(fv, "Kurooto, what's due this week?", sight=(0, 0))


def test_camera_paused_falls_back_to_voice_rules_by_default(fv):
    fv.paused[0] = "screen locked"
    assert fv.face_gate() == ("blind", "screen locked")
    assert turn(fv, "Kurooto, what's due this week?") == "It's due Friday."
    assert "needs a face: camera paused (screen locked), using voice rules" in fv.line()
    assert fv.status()["need_face"] | {"seen_s": None} == {
        "on": True,
        "state": "blind",
        "why": "screen locked",
        "fallback": "voice",
        "held": False,
        "seen_s": None,
        "no_face": 0,
        "blind": 0,
    }


def test_fallback_none_answers_nothing_by_voice_until_the_camera_is_back(fv):
    fv.app.settings.set("voice.listen.need_face_fallback", "none")
    for why in ("you're on a call", "camera covered", "camera in use by another program", "night hours"):
        fv.paused[0] = why
        assert turn(fv, "Kurooto, what's due this week?") is None, why
        assert f"needs a face: camera paused ({why}), not answering by voice" in fv.line()
    assert fv.brain.got == [] and fv.face_counts["blind"] == 4
    assert turn(fv, "", wake=True) is None and fv.portal.awaiting  # the wake word still works
    fv.portal.close("test")
    fv.paused[0] = ""
    assert turn(fv, "Kurooto, what's due this week?", sight=(1, 1)) == "It's due Friday."
    assert "answers only someone facing it" in fv.line()


def test_no_frame_at_all_is_the_fallback_not_chatter(fv):
    assert turn(fv, "Kurooto, what's due this week?") == "It's due Friday."  # camera not looking yet: voice rules
    fv.portal.close("test")
    fv.app.settings.set("voice.listen.need_face_fallback", "none")
    assert turn(fv, "Kurooto, what's due this week?") is None and fv.face_counts == {"no_face": 0, "blind": 1}


def test_typed_voice_commands_are_untouched(fv):
    fv.app.settings.set("voice.listen.need_face_fallback", "none")
    fv.paused[0] = "camera covered"
    from kurooto.modules.base import Incoming

    msg = Incoming(text="/voice status", via="test")
    assert "needs a face: camera paused (camera covered), not answering by voice" in fv._cmd(msg, "status")
    assert fv._cmd(Incoming(text="/voice stop", via="test"), "stop") == "Stopped speaking."


# ----------------------------------------------------------------------------------------------- the hold
def test_the_camera_is_held_while_listening_and_released(fv):
    f = fv.f
    fv.listener = Listener()
    fv._face_hold()
    assert f.holds() == [voice_mod.FACE_HOLD] and fv.status()["need_face"]["held"]
    assert f._holds[voice_mod.FACE_HOLD] - time.monotonic() <= voice_mod.FACE_HOLD_S + 0.5
    fv.app.settings.set("face.addons.hold", False)  # the add-on switch isn't this one
    assert f.holds() == [voice_mod.FACE_HOLD]
    fv._face_hold_at -= voice_mod.FACE_RENEW_S + 1
    fv._face_hold()  # renewed
    assert f.holds() == [voice_mod.FACE_HOLD] and time.monotonic() - fv._face_hold_at < 1
    fv._stop_listening("muted")
    assert f.holds() == [] and not fv._face_hold_at
    fv.listener = Listener()
    fv._face_hold()
    assert f.holds() == [voice_mod.FACE_HOLD]
    fv.app.settings.set("voice.listen.need_face", False)
    fv._face_hold()
    assert f.holds() == []
    fv.app.settings.set("voice.listen.need_face", True)
    fv._face_hold()
    fv.face_on["face"] = False  # Face presence off: nothing held
    fv._face_hold()
    assert f.holds() == []
    fv.face_on["face"] = True
    fv.blocked_why = "you're on a call"  # not listening: released
    fv._face_hold()
    assert f.holds() == []
    fv.listener.on = False


def test_face_presence_names_voice_s_hold_on_its_card(fv):
    f = fv.f
    assert f.hold_watch(voice_mod.FACE_HOLD, 30, core=True)
    f.watcher = type("Wt", (), {"state": "watching", "camera_open": True})()
    assert f.line() == f"camera on: {voice_mod.FACE_HOLD}"
    f.hold_watch("meeting people")
    assert f.line() == f"camera on: an add-on is looking (meeting people); {voice_mod.FACE_HOLD}"
    fv.app.settings.set("face.addons.hold", False)
    assert f.holds() == [voice_mod.FACE_HOLD] and not f.hold_watch("meeting people")
    f.release_watch(voice_mod.FACE_HOLD)
    assert f.holds() == [] and f._core_holds == set()
    f.watcher = None


# ----------------------------------------------------------------------------------------------- barge-in
def test_a_barged_in_question_needs_a_face(fv):
    from kurooto.modules.voice import barge as barge_mod

    stt = type("Stt", (), {"text": lambda self, pcm: "what time is it?"})()
    fv.stt = lambda: stt
    end = time.monotonic() - AGO
    pcm = b"\x00\x00" * 16000
    look(fv.app, end - 0.5, 1, 0)
    assert fv.barge_turn(pcm, b"", {"how": barge_mod.LOUD}, end) is None
    assert fv.brain.got == [] and events(fv, "voice_barge")[-1]["outcome"] == "no face"
    look(fv.app, end - 0.4, 1, 1)
    assert fv.barge_turn(pcm, b"", {"how": barge_mod.LOUD}, end) == "It's due Friday."
    assert events(fv, "voice_barge")[-1]["outcome"] == "turn"
