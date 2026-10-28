"""Look at it to talk (0.8.17, voice.listen.look_to_talk): the owner's face, close and turned to the camera within the
tight look angles for look_dwell_s, opens the conversation as its name alone would; looking away before anything was
said closes it. Fakes only: no camera or microphone is opened, nothing reads the real install."""

# ruff: noqa: F811 (the fixtures imported from the other tests are taken as arguments)

import time
from types import SimpleNamespace

import pytest

from kurooto.core import nearby
from kurooto.modules import voice as voice_mod
from kurooto.modules.face.vision import pitch_degrees
from tests.unit.test_face import W, face, frame, rvec, you
from tests.unit.test_voice import Judge, hear, vid, voice  # noqa: F401 (pytest fixtures)
from tests.unit.test_voice_face_gate import Listener, events, fv, turn  # noqa: F401

DESK = (140.0, 0.0, 0.5)  # the owner at the desk, looking straight at the camera: height (px), yaw, pitch


@pytest.fixture
def lv(fv, monkeypatch):
    """Voice listening, Face presence on and enrolled, awake (Brain's sleep can't depend on when the tests run)."""
    fv.listener = Listener()
    asleep = [False]
    monkeypatch.setattr(voice_mod, "_asleep", lambda app: asleep[0])
    fv.asleep = asleep
    return fv


def looks(v, *ago, on=True):
    """Frames looked at `ago` seconds back (oldest first), the owner looking at it (on) or not."""
    now = time.monotonic()
    for a in ago:
        nearby.set_look(v.app, on, at=now - a)


def opened(v):
    v.look_tick()
    return v.portal.open and v.portal.looked


# ------------------------------------------------------------------------------------------- what counts as a look
def test_a_look_is_the_owner_close_and_turned_to_it_within_the_tight_angles(lv):
    f = lv.f
    assert f.looking(DESK)
    assert not f.looking(None)  # nobody, or not the owner: the watcher hands no pose
    assert not f.looking((60.0, 0.0, 0.5))  # across the room
    assert not f.looking((140.0, 0.25, 0.5))  # about 21 degrees: facing it for need_face (35), not looking at it
    assert f.looking((140.0, 0.15, 0.5))  # about 11 degrees
    assert not f.looking((140.0, None, 0.5))  # no landmarks
    lv.app.settings.set("voice.listen.look_yaw_deg", 25)
    assert f.looking((140.0, 0.25, 0.5))
    lv.app.settings.set("voice.listen.look_to_talk", False)
    assert not f.looking(DESK)


def test_pitch_is_judged_against_the_enrolment_s_front_face(lv, monkeypatch):
    f = lv.f
    assert f.looking((140.0, 0.0, 0.9))  # no front step on record: the yaw alone
    monkeypatch.setattr(f, "_template_or_none", lambda: SimpleNamespace(baseline={"pitch": 0.5}))
    assert pitch_degrees(0.56, 0.5) == pytest.approx(13.0, abs=0.5)
    assert f.looking((140.0, 0.0, 0.56)) and f.looking((140.0, 0.0, 0.44))
    assert not f.looking((140.0, 0.0, 0.62))  # chin up about 25 degrees: looking over it
    assert not f.looking((140.0, 0.0, None))


def test_the_watcher_hands_the_owner_s_pose_with_the_view_and_nobody_else_s():
    t = W([frame([face(yaw=0.1, pitch=0.55)], [you()])] * 3)
    t.run(2)
    views = [f for k, f in t.got if k == "view"]
    assert views
    h, yaw, pitch = views[0]["owner"]
    assert h == 140.0 and yaw == pytest.approx(0.1, abs=0.01) and pitch == pytest.approx(0.55, abs=0.01)
    t = W([frame([face(yaw=0.0)], [rvec()])] * 3)  # someone else, looking straight at it
    t.run(2)
    assert all(f["owner"] is None for k, f in t.got if k == "view")


# ------------------------------------------------------------------------------------------- opening and closing
def test_a_steady_look_opens_the_conversation_silently(lv):
    looks(lv, 1.2, 0.0)
    assert opened(lv)
    p = lv.portal
    assert p.opened_why == "looked at" and not p.awaiting and lv.look_count == 1
    assert lv.spoken == [] and lv.brain.got == []  # nothing said, nothing sent
    assert lv.last_state["state"] == "addressed" and lv.last_state["why"] == "looked at"  # the being shows it listens
    assert [e["why"] for e in events(lv, "voice_portal")] == ["looked at"]
    assert lv.status()["look_to_talk"]["state"] == "open"


def test_face_presence_tells_voice_at_once(lv):
    looks(lv, 1.5)
    lv.f._on_watch("view", faces=1, owner_alone=True, sizes=[(140.0, 0.0)], owner=DESK)
    assert lv.portal.open and lv.portal.looked


def test_a_glance_shorter_than_the_dwell_doesn_t(lv):
    looks(lv, 0.5, 0.0)
    assert not opened(lv)
    looks(lv, 0.0, on=False)  # looked away: the next look starts again
    looks(lv, 0.0)
    assert not opened(lv)
    assert lv.portal.session == 0


def test_someone_else_s_face_doesn_t_open_it(lv):
    looks(lv, 1.5)
    lv.f._on_watch("view", faces=1, owner_alone=False, sizes=[(140.0, 0.0)], owner=None)
    assert not lv.portal.open


def test_the_next_words_count_without_its_name(lv):
    looks(lv, 1.2, 0.0)
    assert opened(lv)
    assert turn(lv, "I need the report done by six", sight=(1, 1)) == "It's due Friday."  # a statement, no name
    assert lv.brain.got == ["I need the report done by six"]
    assert lv.portal.open and not lv.portal.looked  # a conversation now: follow_s and close_s as usual


def test_without_a_look_the_same_words_are_not_to_it(lv):
    lv.judge.answers = ['{"class": "chatter", "confidence": 0.9}']
    assert turn(lv, "I need the report done by six", sight=(1, 1)) is None and lv.brain.got == []


def test_looking_keeps_it_open_and_looking_away_closes_it_when_nothing_was_said(lv):
    looks(lv, 2.2, 1.0)
    assert opened(lv)
    lv.portal.last -= 60  # long past close_s: still looking keeps it open
    looks(lv, 0.0)
    lv.look_tick()
    lv.portal.tick()
    assert lv.portal.open
    looks(lv, 0.0, on=False)
    lv.look_tick()
    assert lv.portal.open  # a moment away isn't enough (look_away_s, 3 s)
    lv.app.settings.set("voice.listen.look_away_s", 0.5)
    nearby.set_look(lv.app, True, at=time.monotonic() - 1.0)  # the last look a second ago...
    looks(lv, 0.0, on=False)  # ...and away since
    lv.look_tick()
    assert not lv.portal.open
    assert events(lv, "voice_portal")[-1]["why"] == "looked away"


def test_looking_away_leaves_a_conversation_going(lv):
    looks(lv, 1.2, 0.0)
    assert opened(lv)
    assert turn(lv, "what's due this week", sight=(1, 1))
    lv.app.settings.set("voice.listen.look_away_s", 0)
    looks(lv, 0.0, on=False)
    lv.look_tick()
    assert lv.portal.open  # closes by follow_s / close_s as any conversation


def test_one_look_opens_it_once(lv):
    looks(lv, 1.2, 0.0)
    assert opened(lv)
    lv.portal.close("not addressed")
    looks(lv, 0.0)
    assert not opened(lv)  # still the same look: told off or not to it, it doesn't spring open again
    looks(lv, 0.0, on=False)
    looks(lv, 1.1, 0.0)
    assert opened(lv) and lv.look_count == 2


def test_a_look_while_it_s_open_already_is_spent(lv):
    assert turn(lv, "Kurooto, what's due?", ago=0.5, sight=(1, 1))
    looks(lv, 1.2, 0.0)
    lv.look_tick()
    assert not lv.portal.looked
    lv.portal.close("silence")
    assert not opened(lv)


NEVER = ["switch off", "muted", "asleep", "voice off", "on a call", "face off", "not listening"]


@pytest.mark.parametrize("why", NEVER)
def test_it_never_fires_when_it_mustn_t(lv, monkeypatch, why):
    if why == "switch off":
        lv.app.settings.set("voice.listen.look_to_talk", False)
    elif why == "muted":
        lv.mute(True)
    elif why == "asleep":
        lv.asleep[0] = True
    elif why == "voice off":
        real = lv.app.is_on
        monkeypatch.setattr(lv.app, "is_on", lambda mid: False if mid == "voice" else real(mid))
    elif why == "on a call":
        lv.app.settings.set("voice.listen.calls", True)  # listening through calls: still no look opens a talk
        monkeypatch.setattr(lv, "_on_call", lambda: True)
    elif why == "face off":
        lv.face_on["face"] = False
    else:
        lv.listener = None
    looks(lv, 1.5, 0.0)
    assert not opened(lv) and not lv.portal.open
    assert lv.status()["look_to_talk"]["state"] == "off" and lv.status()["look_to_talk"]["why"]


def test_status_and_line_say_it_watches(lv):
    st = lv.status()["look_to_talk"]
    assert st["on"] and st["state"] == "watching" and st["why"] == "" and st["dwell_s"] == 1.0
    assert {"yaw_deg", "pitch_deg", "away_s", "opened"} <= set(st)
    assert "looking at it opens a conversation" in lv.line()


def test_the_camera_is_held_for_looks_with_need_face_off(lv):
    held = []
    lv.f.hold_watch = lambda reason, seconds, core=False: held.append(core) or True
    lv.app.settings.set("voice.listen.need_face", False)
    lv._face_hold()
    assert held == [True]
    lv._face_hold_at = 0.0
    lv.app.settings.set("voice.listen.look_to_talk", False)
    lv._face_hold()
    assert held == [True]


def test_a_look_only_remembers_two_times():
    app = SimpleNamespace()
    nearby.set_look(app, True, at=10.0)
    nearby.set_look(app, True, at=11.0)
    assert nearby.look(app) == (10.0, 11.0)
    nearby.set_look(app, False, at=12.0)
    assert nearby.look(app) == (None, 11.0)
    nearby.set_look(app, True, at=13.0)
    nearby.clear_view(app)  # the camera closed: the run of looks is broken
    assert nearby.look(app) == (None, 13.0)


# ---------------------------------------------------------------------------------------------- with Voice ID
@pytest.fixture
def lvid(vid, lv):
    lv.app.settings.set("voice.listen.need_face", False)  # these are about the voice; the face gate has its own tests
    return vid


def test_speech_while_looked_at_still_goes_through_voice_id(lvid):
    v = lvid.v
    v.app.settings.set("voice.listen.look_anyone", False)  # (0.8.18) the owner's look only: as 0.8.17
    stt = lvid.stt_fake
    looks(v, 1.2, 0.0)
    assert opened(v)
    hear(v, "did you see the match last night, it was something", who_voice=55, seconds=8.0)  # someone else
    assert v.portal.send.got == [] and not v.portal.open
    assert stt.calls and max(stt.calls) < 8 * 16000 * 2  # only the edges were written out, as with it closed
    looks(v, 0.0, on=False)
    looks(v, 1.2, 0.0)
    assert opened(v)
    hear(v, "what's due tomorrow", utt=2)
    assert v.portal.send.got == [("what's due tomorrow", "owner")]


def test_a_guest_voice_with_voice_id_s_gate_off_isn_t_taken_by_the_look(lvid):
    v = lvid.v
    v.app.settings.set("voice.speaker_id.gate", False)
    v.judge = Judge('{"class": "chatter", "confidence": 0.9}')
    looks(v, 1.2, 0.0)
    assert opened(v)
    hear(v, "I'll grab the snacks later", who_voice=55)
    assert v.portal.send.got == []


# ------------------------------------------------------------------------------------------- 0.8.18: anyone's look
def test_anyone_s_look_opens_it(lv):
    f = lv.f
    other = (140.0, 0.0, 0.5, None)  # a guest close and turned to it; the owner not looking
    assert f.looking(None, None, None, [other]) and f.looking((140.0, 0.6, 0.5), None, None, [other])
    assert not f.looking(None, None, None, [(60.0, 0.0, 0.5, None)])  # across the room
    assert not f.looking(None, None, None, [(140.0, 0.3, 0.5, None)])  # turned away
    lv.app.settings.set("voice.listen.look_anyone", False)  # the switch: the owner's look only
    assert not f.looking(None, None, None, [other]) and f.looking(DESK)
    lv.app.settings.set("voice.listen.look_anyone", True)
    looks(lv, 1.5)
    lv.f._on_watch("view", faces=2, owner_alone=False, sizes=[(140.0, 0.0)] * 2, owner=None, looks=[other])
    assert lv.portal.open and lv.portal.looked


def test_the_watcher_hands_other_faces_looks_only_when_asked():
    frames = [frame([face(yaw=0.0), face(x=420.0, h=120.0, yaw=0.1)], [rvec(), rvec()])] * 3
    t = W(frames, cfg={"look_anyone": True})
    t.run(2)
    views = [f for k, f in t.got if k == "view"]
    assert views and len(views[0]["looks"]) == 2 and views[0]["owner"] is None
    h, yaw, _pitch, eyes = views[0]["looks"][0]
    assert h == 140.0 and yaw == pytest.approx(0.0, abs=0.01) and eyes is None  # biggest first; no gazer, no eyes
    t = W(frames)
    t.run(2)
    assert all(f["looks"] is None for k, f in t.got if k == "view")


def test_a_guest_looked_at_it_is_heard_as_a_guest(lvid):
    v = lvid.v
    looks(v, 1.2, 0.0)
    assert opened(v)
    hear(v, "what's the weather like tomorrow", who_voice=55)
    assert [w for _t, w in v.portal.send.got] == ["guest"]  # chat only: the guest path


def test_with_company_a_look_and_a_misheard_name_count(lvid):
    from kurooto.modules.voice.gate import ADDRESSED, LOOKED, Context, Heard

    g = lvid.v.gate()
    ctx = Context(portal_open=True, looked=True, faces=2, careful=True, look_company=True)
    h = Heard(text="Kurooti close your eyes for a bit", speech=True, voices=1)
    d = g.decide(h, ctx)
    assert d.klass == ADDRESSED and d.why == LOOKED
    ctx.look_company = False  # the switch: in company only a question or a request after a look
    assert g.decide(h, ctx).why != LOOKED
