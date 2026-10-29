"""Look to talk by the eyes (0.8.17, voice.listen.look_gaze, modules/face/gaze.py) and a sharper camera (480x640 to
1080x1440). Fakes only: frames are dicts, the gazer hands scripted iris offsets; no camera, microphone or model is
opened, except the one model-run test, skipped unless KUROOTO_TEST_MODELS holds iris_landmark.tflite and OpenCV can be
imported (it draws made-up eyes; no picture of anyone).

1 the iris maths  2 gaze angles  3 calibration  4 Face.looking by the eyes  5 the calibration session  6 the watcher
7 resolution independence  8 parts  9 look to talk end to end  10 the real model"""

# ruff: noqa: F811 (the fixtures imported from the other tests are taken as arguments)

import math
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from kurooto.core import egress, nearby
from kurooto.modules.face import enrol as en
from kurooto.modules.face import gaze as gz
from kurooto.modules.face import parts as fp
from kurooto.modules.face.enrol import PLAN, Enrolment
from kurooto.modules.face.vision import Face, px_scale
from tests.unit.test_face import (
    BASE,
    GLASSES,
    GOOD,
    Clock,
    W,
    app,  # noqa: F401 (pytest fixtures)
    every_file,
    face,
    feed_plan,
    frame,
    judge,
    ready,  # noqa: F401
    rvec,
    trained,  # noqa: F401
    you,
)
from tests.unit.test_voice import voice  # noqa: F401 (pytest fixtures)
from tests.unit.test_voice_face_gate import fv  # noqa: F401
from tests.unit.test_voice_look import DESK, lv  # noqa: F401

CAL = {"h": 0.05, "v": 0.02, "yaw": 0.0, "pitch": 0.5, "n": 15, "at": 1_700_000_000}
BIG = (1080, 1440)  # the phone camera after the switch (portrait)
SMALL = (480, 640)  # before it
K = 1440 / 640  # how much bigger everything is at the sharper size


def scaled(f: Face, k: float) -> Face:
    return Face(tuple(v * k for v in f.box), tuple((x * k, y * k) for x, y in f.landmarks), f.score)  # type: ignore[arg-type]


class Gz:
    """A gazer: the frame's scripted iris offsets (a dict's "eyes"), or None (a blink)."""

    def __init__(self):
        self.calls = 0

    def eyes(self, fr, f):
        self.calls += 1
        e = fr.get("eyes")
        return None if e is None else gz.Eyes(*e)


# ------------------------------------------------------------------------------------------- 1 the iris maths
def eye(iris, ang=0.0, open_=16.0):
    """An eye 44 wide around (32, 32), its contour's corners 0 and 8 and lids' middles 4 and 12, turned by ang."""
    c, s = math.cos(ang), math.sin(ang)

    def at(x, y):
        return (32 + (x - 32) * c - (y - 32) * s, 32 + (x - 32) * s + (y - 32) * c)

    pts = [at(32, 32)] * 16
    pts[0], pts[8] = at(10, 32), at(54, 32)
    pts[4], pts[12] = at(32, 32 + open_ / 2), at(32, 32 - open_ / 2)
    return pts, at(*iris)


def test_the_iris_offset_along_and_across_the_eye():
    h, v, o = gz.offset(*eye((32, 32)))
    assert h == pytest.approx(0) and v == pytest.approx(0) and o == pytest.approx(16 / 44)
    assert gz.offset(*eye((43, 32)))[0] == pytest.approx(0.5)  # a quarter of the eye to the picture's right
    assert gz.offset(*eye((10, 32)))[0] == pytest.approx(-1)
    assert gz.offset(*eye((32, 36.4)))[1] == pytest.approx(0.1)  # down is positive, in eye widths
    turned = gz.offset(*eye((43, 36.4), ang=math.radians(20)))  # a tilted head: measured along the eye itself
    assert turned[0] == pytest.approx(0.5) and turned[1] == pytest.approx(0.1)
    pts, iris = eye((43, 32))
    pts[0], pts[8] = pts[8], pts[0]  # the corners in either order
    assert gz.offset(pts, iris)[0] == pytest.approx(0.5)
    pts[8] = pts[0]
    assert gz.offset(pts, iris) is None


def test_a_blink_gives_no_reading_and_two_eyes_are_averaged():
    assert gz.eyes_of([None, None]) is None
    assert gz.eyes_of([(0.2, 0.0, 0.05)]) is None  # shut
    e = gz.eyes_of([(0.2, 0.1, 0.3), (0.4, 0.0, 0.3)])
    assert (e.h, e.v, e.n) == (pytest.approx(0.3), pytest.approx(0.05), 2)
    one = gz.eyes_of([(0.2, 0.1, 0.3), (0.9, 0.0, 0.05)])  # one blinks: the other counts
    assert one.n == 1 and one.h == pytest.approx(0.2)


# ------------------------------------------------------------------------------------------- 2 gaze angles
def eyes_for(deg_h: float, deg_v: float = 0.0, cal=CAL) -> tuple[float, float]:
    """The iris offsets of eyes turned deg_h (your left negative) and deg_v (down positive) from the calibration's."""
    h0 = math.degrees(math.asin(cal["h"] / gz.EYE_H))
    v0 = math.degrees(math.asin(cal["v"] / gz.EYE_V))
    # the camera's picture isn't mirrored: eyes turned to your left move the iris to the picture's right
    return gz.EYE_H * math.sin(math.radians(h0 - deg_h)), gz.EYE_V * math.sin(math.radians(v0 + deg_v))


def yaw_for(deg: float) -> float:
    return math.tan(math.radians(deg)) * (0.3 / math.tan(math.radians(25)))


def test_at_the_calibration_the_gaze_is_on_the_lens():
    assert gz.angles(CAL["h"], CAL["v"], CAL["yaw"], CAL["pitch"], CAL) == (pytest.approx(0), pytest.approx(0))


def test_a_turned_head_with_the_eyes_back_on_the_lens_is_looking_at_it():
    h, v = eyes_for(+20)  # eyes 20 degrees to your right...
    gh, gv = gz.angles(h, v, yaw_for(-20), CAL["pitch"], CAL)  # ...in a head turned 20 degrees to your left
    assert abs(gh) < 0.5 and abs(gv) < 0.5
    gh, _ = gz.angles(*eyes_for(0), yaw_for(-20), CAL["pitch"], CAL)  # the eyes went with the head
    assert gh == pytest.approx(-20, abs=0.5)


def test_a_head_facing_it_with_the_eyes_on_the_screen_below_isn_t():
    h, v = eyes_for(0, 20)  # eyes 20 degrees down: the monitor under the camera
    gh, gv = gz.angles(h, v, CAL["yaw"], CAL["pitch"], CAL)
    assert abs(gh) < 0.5 and gv == pytest.approx(20, abs=0.5)
    nod = CAL["pitch"] + gz.PITCH_K * math.tan(math.radians(15))  # chin down 15 degrees, eyes up 15: on the lens
    gh, gv = gz.angles(*eyes_for(0, -15), CAL["yaw"], nod, CAL)
    assert abs(gv) < 0.5


def test_valid_calibrations():
    assert gz.valid(CAL) and not gz.valid({}) and not gz.valid({**CAL, "h": "x"}) and not gz.valid(None)
    assert not gz.valid({**CAL, "v": float("nan")})


# ------------------------------------------------------------------------------------------- 3 calibration
def test_calibration_keeps_four_medians_a_count_and_a_time():
    c = gz.Calibration()
    t = 100.0
    assert c.share(t) == 0 and not c.done(t)
    for i in range(16):  # 5 a second for 3 s
        c.feed(gz.Eyes(0.05 + (i % 3) * 0.01, 0.02), 0.01, 0.5, t)
        t += 0.2
    assert c.done(t) and c.share(t) == 1.0
    r = c.result(1_700_000_123.6)
    assert set(r) == {"h", "v", "yaw", "pitch", "n", "at"} and r["n"] == 16 and r["at"] == 1_700_000_124
    assert r["h"] == pytest.approx(0.06) and r["pitch"] == 0.5


def test_calibration_needs_enough_steady_frames():
    c = gz.Calibration()
    for i in range(3):
        c.feed(gz.Eyes(0.0, 0.0), 0.0, 0.5, 100.0 + i)
    assert not c.done(102.0) and c.done(100.0 + gz.CAL_MAX_S)  # it gives up in the end
    assert isinstance(c.result(0), str)
    c = gz.Calibration()
    for i in range(16):
        c.feed(gz.Eyes(0.6 if i % 2 else -0.6, 0.0), 0.0, 0.5, 100 + i * 0.2)  # eyes all over the place
    assert "moved about" in c.result(0)


# --------------------------------------------------------------------------------------- 4 Face.looking by the eyes
@pytest.fixture
def eyes_on(lv, monkeypatch):
    """lv with the eye model here and the owner's eyes calibrated."""
    f = lv.f
    real = f.parts.has_model
    monkeypatch.setattr(f.parts, "has_model", lambda key: True if key == "iris" else real(key))
    from types import SimpleNamespace

    tpl = SimpleNamespace(baseline={"pitch": 0.5}, gaze=dict(CAL))
    monkeypatch.setattr(f, "_template_or_none", lambda: tpl)
    lv.tpl = tpl
    return lv


def test_without_a_calibration_it_goes_by_the_head(lv):
    f = lv.f
    assert f.gaze_calibration() is None
    assert not f.looking((140.0, yaw_for(-20), 0.5), eyes_for(20))  # eyes back on the lens: unseen without one
    assert f.looking(DESK, eyes_for(0, 20))  # head facing it, eyes on the screen: the head's turn says yes
    st = f.gaze_status()
    assert st["using"] == "head" and "eye model" in st["why"]


def test_with_a_calibration_it_goes_by_the_eyes(eyes_on):
    f = eyes_on.f
    assert f.gaze_calibration() == CAL and f.gaze_status()["using"] == "eyes"
    assert f.looking(DESK, eyes_for(0))
    assert f.looking((140.0, yaw_for(-20), 0.5), eyes_for(20))  # head turned past look_yaw_deg, eyes on the lens
    assert not f.looking(DESK, eyes_for(0, 20))  # head on the camera, eyes on the screen below
    assert not f.looking(DESK, eyes_for(-15))  # eyes off to the side
    assert not f.looking((140.0, yaw_for(-40), 0.5), eyes_for(40))  # past face_yaw_deg: the irises can't be trusted
    assert not f.looking((60.0, 0.0, 0.5), eyes_for(0))  # across the room
    eyes_on.app.settings.set("voice.listen.look_gaze_pitch_deg", 25)
    assert f.looking(DESK, eyes_for(0, 20))
    now = f.gaze_status()["now"]
    assert now["looking"] and now["pitch_deg"] == pytest.approx(20, abs=0.5) and "t" not in now


def test_a_blink_keeps_the_last_verdict_for_a_moment(eyes_on, monkeypatch):
    f = eyes_on.f
    assert f.looking(DESK, eyes_for(0))
    assert f.looking(DESK, None)  # a blink right after a look
    f._gaze_last["t"] -= 2
    assert not f.looking(DESK, None)
    assert not f.looking(DESK, eyes_for(0, 25)) and not f.looking(DESK, None)  # a blink after looking away


def test_the_switch_and_the_part_fall_back_to_the_head(eyes_on, monkeypatch):
    f = eyes_on.f
    eyes_on.app.settings.set("voice.listen.look_gaze", False)
    assert f.gaze_calibration() is None and f.looking(DESK, eyes_for(0, 20))
    assert f.gaze_status()["why"] == "voice.listen.look_gaze is off"
    eyes_on.app.settings.set("voice.listen.look_gaze", True)
    monkeypatch.setattr(f.parts, "has_model", lambda key: False)
    assert f.gaze_calibration() is None and f.gaze_status()["using"] == "head"
    eyes_on.app.settings.set("voice.listen.look_to_talk", False)
    assert not f.looking(DESK, eyes_for(0))


# ----------------------------------------------------------------------------------- 5 the calibration session
@pytest.fixture
def cal_ready(trained, monkeypatch):
    f = trained
    real = f.parts.has_model
    monkeypatch.setattr(f.parts, "has_model", lambda key: True if key == "iris" else real(key))
    g = Gz()
    monkeypatch.setattr(f, "_gaze_model", lambda: g)
    f.gz = g
    return f


def run_cal(f, frames, seconds=4.0):
    sess = f.session
    clock = Clock()
    sess.clock = clock
    sess.started = sess.last_fetch = sess._tick_at = sess._last_frame_at = clock.t
    end = clock.t + seconds
    i = 0
    while clock.t < end and sess.state != "ended":
        f.cam.frames = [frames[i % len(frames)]]
        clock.t += 0.2
        sess.last_fetch = clock.t
        sess.step()
        i += 1
    return sess


def looking_frame(eyes=(0.05, 0.02), **kw):
    fr = frame([face(**kw)], [you()])
    fr["eyes"] = eyes
    return fr


def test_calibrating_keeps_only_the_numbers_in_the_sealed_template(app, cal_ready, tmp_path):
    f = cal_ready
    before = every_file(tmp_path)
    ok, out = f.gaze_start(cid=7)
    assert ok and out["stage"] == "calibrating" and f.stage() == "calibrating"
    sess = run_cal(f, [looking_frame()])
    assert sess.state == "ended" and sess.why == "calibrated" and not f.cam.open_now
    cal = f.template().gaze
    assert set(cal) == {"h", "v", "yaw", "pitch", "n", "at"} and cal["h"] == pytest.approx(0.05) and cal["n"] >= 8
    assert f.gaze_status()["calibrated"] and f.gaze_status()["using"] == "eyes"
    assert f.store.status()["gaze_at"] == cal["at"]
    new = every_file(tmp_path) - before
    assert {n for n in new if not n.startswith(("state/events", "state/locks/", "state/calm"))} <= {
        "state/face/template.bin",
        "state/face/face.json",
    }
    pushed = [m for m in f.pushed if m.get("kind") in ("gaze", "gaze_result")]
    assert pushed and all(not ({"h", "v", "yaw", "pitch", "e"} & set(m)) for m in pushed)  # words and a share only
    assert pushed[-1] == {**pushed[-1], "kind": "gaze_result", "ok": True}
    ev = [e for e in app.events.tail(50) if e["kind"] == "face_gaze"]
    assert ev and set(ev[-1]) == {"ts", "kind", "calibrated"}
    assert f.gaze_clear()[0] and f.template().gaze == {} and f.gaze_status()["using"] == "head"


def test_calibration_needs_you_alone_facing_it_with_your_eyes_readable(app, cal_ready):
    f = cal_ready
    f.gaze_start()
    blink = looking_frame(eyes=None)
    sess = run_cal(f, [blink], seconds=2.0)
    assert sess.state == "capturing" and f.pushed[-1]["reason"] == en.R_EYES
    f.cam.frames = [looking_frame(yaw=0.35)]
    sess.step()
    assert f.pushed[-1]["reason"] == en.R_LENS
    stranger = frame([face()], [rvec()])
    stranger["eyes"] = (0.0, 0.0)
    f.cam.frames = [stranger]
    sess.step()
    assert f.pushed[-1]["reason"] == en.R_NOT_OWNER
    two = frame([face(), face(x=40, h=100)], [you(), rvec()])
    f.cam.frames = [two]
    sess.step()
    assert f.pushed[-1]["reason"] == en.R_TWO
    assert sess.cal.rows == [] and f.template().gaze == {}
    f.test_stop(sess.id)


def test_calibration_that_wanders_keeps_nothing(app, cal_ready):
    f = cal_ready
    f.gaze_start()
    sess = run_cal(f, [looking_frame(eyes=(0.6, 0.0)), looking_frame(eyes=(-0.6, 0.0))])
    assert sess.state == "ended" and sess.why == "not calibrated" and f.template().gaze == {}
    assert [m for m in f.pushed if m.get("kind") == "gaze_result"][-1]["ok"] is False


def test_calibration_needs_the_eye_model_and_a_face_model(app, ready, monkeypatch):
    f = ready
    assert "Enrol first" in f.gaze_start()[1]["message"]
    f.enrol_start()
    feed_plan(f, f.session)
    f.cam.dev = SimpleNamespace(name="Test camera")  # (0.9.2) the enrolment's camera is recorded, a name only
    f.train(f.session.id)
    assert f.template().cameras == ["Test camera"]
    assert "Get the eye model first" in f.gaze_start()[1]["message"]
    assert f.cam.opened == 1  # only the enrolment opened it


# --------------------------------------------------------------------------------------------- 6 the watcher
def test_the_watcher_reads_the_eyes_only_when_a_gazer_is_handed_and_sends_two_numbers():
    fr = frame([face()], [you()])
    fr["eyes"] = (0.1234567, -0.02)
    t = W([fr] * 4)
    t.run(2)
    assert all(v["eyes"] is None for k, v in t.got if k == "view")
    g = Gz()
    t = W([fr] * 4)
    t.w.gaze = lambda: g
    t.run(2)
    views = [v for k, v in t.got if k == "view"]
    assert views and views[0]["eyes"] == (0.1235, -0.02) and views[0]["frame"] == (640, 480) and g.calls
    other = frame([face()], [rvec()])  # someone else: no eyes read, no owner
    other["eyes"] = (0.0, 0.0)
    g2 = Gz()
    t = W([other] * 4)
    t.w.gaze = lambda: g2
    t.run(2)
    assert g2.calls == 0 and all(v["eyes"] is None for k, v in t.got if k == "view")


def test_a_failing_eye_model_is_reported_and_reads_nothing():
    class Bad:
        def eyes(self, fr, f):
            raise RuntimeError("no")

    t = W([frame([face()], [you()])] * 4)
    t.w.gaze = lambda: Bad()
    t.run(2)
    assert any(k == "failed" and v["part"] == "reading the eyes" for k, v in t.got)
    assert all(v["eyes"] is None for k, v in t.got if k == "view")


def test_while_voice_listens_for_a_look_the_rate_rises_to_look_fps_at_most_five():
    t = W(cfg={"fps": 1.0})
    assert t.w.rate() == 1.0
    t.cfg["look_fps"] = 3
    assert t.w.rate() == 3.0
    t.cfg["look_fps"] = 30
    assert t.w.rate() == 5.0
    t.w.slow = 2.0  # a slow machine halves it too
    assert t.w.rate() == 2.5


def test_face_asks_for_look_fps_only_while_voice_holds_the_camera(app):
    f = app.modules["face"]
    assert f._watch_cfg()["look_fps"] == 0
    f.hold_watch("voice: who's talking", 60, core=True)
    assert f._watch_cfg()["look_fps"] == 5.0
    app.settings.set("voice.listen.look_to_talk", False)
    assert f._watch_cfg()["look_fps"] == 0
    app.settings.set("voice.listen.look_to_talk", True)
    f.release_watch("voice: who's talking")
    f.hold_watch("an add-on", 60)  # an add-on's hold isn't Voice listening
    assert f._watch_cfg()["look_fps"] == 0


# ----------------------------------------------------------------------------------- 7 resolution independence
def test_px_scale():
    assert px_scale(640, 480) == 1.0 and px_scale(*SMALL) == 1.0 and px_scale(*BIG) == pytest.approx(2.25)
    assert px_scale(0, 0) == 1.0


@pytest.mark.parametrize("size,k", [(SMALL, 1.0), (BIG, K)])
def test_the_watcher_judges_the_same_faces_at_both_sizes(size, k):
    near, far = face(h=140.0), face(x=40, h=50.0)  # far: under min_face_px at 480 wide
    t = W([frame([scaled(near, k), scaled(far, k)], [you(), rvec()], size=size)] * 4)
    t.run(2)
    assert t.w.counts.you >= 1 and t.w.counts.not_you == 0  # the small face isn't judged at either size
    v = [x for kind, x in t.got if kind == "view"][0]
    assert v["frame"] == size and v["owner"][0] == pytest.approx(140.0 * k)


@pytest.mark.parametrize("k", [1.0, K])
def test_a_still_picture_is_caught_at_both_sizes(k):
    t = W([frame([scaled(face(dx=0.0), k)], [you()], size=SMALL if k == 1 else BIG)] * 10)
    t.w.present_at -= 3600
    t.run(5)
    assert "arrived" not in t.kinds()  # a picture's landmarks barely move: waits for movement at 1440 too


def desk_face(f, k, measured=True):
    f.owner_desk_height = lambda: {"px": 140.0, "h": 140 / 640, "n": 20, "from": "seen", "measured": measured}


@pytest.mark.parametrize("size,k", [(SMALL, 1.0), (BIG, K)])
def test_close_and_facing_are_shares_of_the_frame(app, size, k):
    f = app.modules["face"]
    desk_face(f, k)
    assert f.close_facing([(140.0 * k, 0.0)], size) == 1
    assert f.close_facing([(60.0 * k, 0.0)], size) == 0  # less than half your desk height: across the room
    assert f.looking((140.0 * k, 0.0, 0.5), None, size)
    assert not f.looking((60.0 * k, 0.0, 0.5), None, size)


def test_without_a_measured_desk_height_min_face_px_is_scaled(app):
    f = app.modules["face"]
    f.owner_desk_height = lambda: None
    assert f.close_facing([(100.0, 0.0)], SMALL) == 1 and f.close_facing([(100.0, 0.0)], BIG) == 0
    assert f.close_facing([(140.0, 0.0)], BIG) == 1  # 140 > 60 x 2.25
    assert f.close_facing([(100.0, 0.0)]) == 1  # no frame size given: pixels as before


def test_an_old_enrolment_s_guessed_share_isn_t_scaled(app):
    f = app.modules["face"]
    desk_face(f, 1.0, measured=False)  # pixels only: compared as pixels, as before 0.8.17
    assert f.close_facing([(80.0, 0.0)], BIG) == 1


@pytest.mark.parametrize("size,k", [(SMALL, 1.0), (BIG, K)])
def test_enrolment_walks_through_at_both_sizes(size, k):
    p = Enrolment(60)
    poses = {"left": {"yaw": -0.3}, "right": {"yaw": 0.3}, "up": {"pitch": 0.38}, "down": {"pitch": 0.62},
             "near": {"h": 200.0, "x": 140.0}, "far": {"h": 95.0}}  # fmt: skip
    t = 0.0
    for st in PLAN:
        for i in range(st.target):
            t += 1.0
            e = GLASSES if st.key == "glasses" else BASE
            stats = {**GOOD, "mean": 70.0} if st.key == "light" else GOOD
            fr = frame([scaled(face(dx=i * 5.0, **poses.get(st.key, {})), k)], [you(e)], [stats], size=size)
            v = judge(p, fr, t)
            assert v.ok, (st.key, i, v.reason)
    assert p.baseline["share"] == pytest.approx(140 / 640, abs=0.002)
    too_far = frame([scaled(face(h=50.0), k)], [you()], size=size)
    assert judge(Enrolment(60), too_far, 1.0).reason == en.R_FAR


def test_add_samples_after_the_camera_got_sharper_compares_shares():
    """Enrolled at 480x640 (front face 140 px); Add samples at 1080x1440: the near step wants 1.25 times the front
    face's share of the frame, not 1.25 times 140 pixels."""
    have = {s.key: s.target for s in PLAN if s.key != "near"}
    p = Enrolment(60, have, {"pitch": 0.5, "height": 140.0, "light": 120.0, "share": 140 / 640}, [BASE])
    assert p.current().key == "near"
    fr = frame([scaled(face(h=150.0, x=140.0), K)], [you()], size=BIG)  # 337 px: far more than 175, but not near
    assert judge(p, fr, 1.0).reason.startswith("Lean in a little closer")
    fr = frame([scaled(face(h=200.0, x=140.0), K)], [you()], size=BIG)
    assert judge(p, fr, 2.0).ok


def test_your_desk_height_from_a_new_enrolment_is_its_share(app, trained):
    f = trained
    f._desk.clear()
    d = f.owner_desk_height()
    assert d["from"] == "enrolment" and d["measured"] and d["h"] == pytest.approx(140 / 480, abs=0.002)


# --------------------------------------------------------------------------------------------------- 8 parts
def test_the_eye_model_is_an_optional_pinned_part(app):
    f = app.modules["face"]
    assert "model:iris" not in f.wants() and fp.EYES == ["model:iris"]
    (m,) = fp.face_models()["iris"]
    assert m.name == "iris_landmark.tflite" and len(m.sha256) == 64 and m.mb == pytest.approx(2.64)
    assert m.url.startswith("https://storage.googleapis.com/mediapipe-assets/") and "generation=" in m.url
    assert egress.host_of(m.url) in egress.HOSTS


def test_get_the_eye_model_downloads_only_it(app, monkeypatch):
    f = app.modules["face"]
    got = []
    monkeypatch.setattr(f.parts, "install", lambda keys, progress, free_gb=None: got.append(keys) or (True, "ok"))
    ok, msg = f.gaze_setup(lambda m: None)
    assert ok and got == [["model:iris"]] and "Calibrate" in msg


# ------------------------------------------------------------------------------------- 9 look to talk end to end
def test_a_look_by_the_eyes_opens_the_conversation_and_eyes_on_the_screen_don_t(eyes_on):
    v = eyes_on
    for i in range(3):  # a second and a half of frames, the eyes on the screen below the camera
        nearby.set_look(v.app, v.f.looking(DESK, eyes_for(0, 20)), at=time.monotonic() - 1.5 + i * 0.5)
    v.look_tick()
    assert not v.portal.open
    v.f._on_watch("view", faces=1, owner_alone=True, sizes=[(140.0, 0.0)], owner=DESK, eyes=eyes_for(0, 20))
    assert not v.portal.open
    for i in range(3):
        nearby.set_look(v.app, v.f.looking(DESK, eyes_for(0)), at=time.monotonic() - 1.5 + i * 0.5)
    v.f._on_watch("view", faces=1, owner_alone=True, sizes=[(140.0, 0.0)], owner=DESK, eyes=eyes_for(0))
    assert v.portal.open and v.portal.looked
    st = v.status()["look_to_talk"]
    assert st["by"] == "eyes" and st["gaze"]["calibrated"] and "by your eyes" in v.line()


def test_by_the_eyes_a_single_frame_opens_it_at_once(eyes_on):
    v = eyes_on
    v.f._on_watch("view", faces=1, owner_alone=True, sizes=[(140.0, 0.0)], owner=DESK, eyes=eyes_for(0))
    assert v.portal.open and v.portal.looked and v.look_count == 1  # no second of dwell: the first frame did it


def test_a_gaze_dwell_can_ask_for_more_than_one_frame(eyes_on):
    v = eyes_on
    v.app.settings.set("voice.listen.look_gaze_dwell_s", 0.3)
    v.f._on_watch("view", faces=1, owner_alone=True, sizes=[(140.0, 0.0)], owner=DESK, eyes=eyes_for(0))
    assert not v.portal.open
    nearby.set_look(v.app, False, at=time.monotonic() - 0.5)
    nearby.set_look(v.app, True, at=time.monotonic() - 0.4)  # a run that began 0.4 s ago
    nearby.set_look(v.app, True)
    v.look_tick()
    assert v.portal.open


def test_by_the_head_the_dwell_still_applies(lv):
    lv.f._on_watch("view", faces=1, owner_alone=True, sizes=[(140.0, 0.0)], owner=DESK)
    assert not lv.portal.open  # one frame of the head's turn is a glance


def test_voice_says_it_goes_by_the_head_without_a_calibration(lv):
    st = lv.status()["look_to_talk"]
    assert st["by"] == "head" and "by your head's turn" in lv.line()


# ------------------------------------------------------------------------------------------ 10 the real model
def _real_gazer():
    folder = os.environ.get("KUROOTO_TEST_MODELS")
    if not folder or not (Path(folder) / fp.IRIS).is_file():
        pytest.skip("needs KUROOTO_TEST_MODELS with iris_landmark.tflite")
    pytest.importorskip("cv2")
    return gz.opencv_gazer(Path(folder) / fp.IRIS)


def drawn_eyes(size, shift, roll=0.0):
    """A made-up face's two eyes (an almond, an iris and a pupil each), the irises moved `shift` of the way to the
    picture's right; and its YuNet-style landmarks."""
    import cv2
    import numpy as np

    w, h = size
    k = h / 640
    img = np.full((h, w, 3), (120, 150, 200), np.uint8)
    d, cx, cy, a = 80 * k, w / 2, h * 0.4, math.radians(roll)
    pts = [(cx - d / 2 * math.cos(a), cy - d / 2 * math.sin(a)), (cx + d / 2 * math.cos(a), cy + d / 2 * math.sin(a))]
    for ex, ey in pts:
        axes = (int(20 * k), int(9 * k))
        cv2.ellipse(img, (int(ex), int(ey)), axes, roll, 0, 360, (235, 235, 240), -1)
        mask = np.zeros((h, w), np.uint8)
        cv2.ellipse(mask, (int(ex), int(ey)), axes, roll, 0, 360, 255, -1)
        iris = np.zeros_like(img)
        c = (int(ex + shift * 14 * k), int(ey))
        cv2.circle(iris, c, int(8 * k), (40, 60, 90), -1)
        cv2.circle(iris, c, int(3 * k), (10, 10, 10), -1)
        on = (iris.sum(2) > 0) & (mask > 0)
        img[on] = iris[on]
        cv2.ellipse(img, (int(ex), int(ey)), axes, roll, 0, 360, (60, 60, 80), max(1, int(k)))
    lm = (pts[0], pts[1], (cx, cy + 40 * k), (cx - 30 * k, cy + 80 * k), (cx + 30 * k, cy + 80 * k))
    return img, Face((cx - 100 * k, cy - 60 * k, 200 * k, 200 * k), lm, 0.95)


@pytest.mark.parametrize("size", [SMALL, BIG])
def test_the_real_eye_model_follows_drawn_irises_at_both_sizes(size):
    g = _real_gazer()
    hs = []
    for shift in (-0.6, 0.0, 0.6):
        img, f = drawn_eyes(size, shift, roll=8.0)
        e = g.eyes(img, f)
        assert e is not None and e.n == 2
        hs.append(e.h)
    assert hs[0] < hs[1] - 0.15 and hs[2] > hs[1] + 0.15  # to the picture's left and right, both eyes alike
    assert abs(hs[1]) < 0.15
