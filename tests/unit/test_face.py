"""Face presence (modules/face, 0.8.10), all with fakes: frames are plain dicts, the detector returns scripted faces,
the embedder made-up unit vectors (you = a base plus noise; someone else = random; you with glasses = the base plus an
offset). No camera is opened, no model is loaded, no picture is looked at; cv2 isn't imported.

1 quality  2 the plan  3 calibration  4 the watcher  5 the greeting  6 Portal.invite  7 sessions  8 learning
9 privacy  10 parts  11 the API  12 a face never authorises anything."""

import datetime as dt
import hashlib
import json
import math
import random
from pathlib import Path

import pytest

import kurooto
from kurooto.core.biometric import Locked, npz_write, unit
from kurooto.modules.face import enrol as en
from kurooto.modules.face import greet as gr
from kurooto.modules.face import model as mo
from kurooto.modules.face import parts as fp
from kurooto.modules.face.enrol import PLAN, Enrolment, Session
from kurooto.modules.face.vision import Face, Stats, pose
from kurooto.modules.face.watch import PAUSES, Watcher

SRC = Path(kurooto.__file__).parent
R = random.Random(42)  # noqa: S311 (made-up test data, not secrets)


# ------------------------------------------------------------------------------------------------------ fakes
def rvec(r=R):
    return unit([r.gauss(0, 1) for _ in range(128)])


BASE = rvec()
GLASSES = unit([b + 0.9 * o for b, o in zip(BASE, rvec(), strict=True)])


def you(base=BASE, noise=0.6, r=R):
    n = rvec(r)
    return unit([b + noise * x for b, x in zip(base, n, strict=True)])


def face(x=260.0, y=150.0, h=140.0, yaw=0.0, pitch=0.5, roll=0.0, score=0.95, dx=0.0):
    """A face whose landmarks give this pose (mirrored preview: yaw < 0 is turned to your left)."""
    d = 0.4 * h
    mx, ey = x + h / 2 + dx, y + 0.38 * h
    dy = math.tan(math.radians(roll)) * d
    re, le = (mx - d / 2, ey - dy / 2), (mx + d / 2, ey + dy / 2)
    my = ey + 0.4 * h
    nose = (mx - yaw * d, ey + pitch * (my - ey))
    return Face((x, y, h, h), (re, le, nose, (mx - d / 3, my), (mx + d / 3, my)), score)


GOOD = {"blur": 150.0, "mean": 120.0, "bright": 0.0}


def frame(faces=(), embs=(), stats=None, mean=110.0, size=(640, 480)):
    return {"faces": list(faces), "embs": list(embs), "stats": stats or [GOOD] * len(faces), "mean": mean, "size": size}


class Det:
    def detect(self, fr, min_score):
        return [f for f in fr["faces"] if f.score >= min_score]


class Emb:
    def __init__(self, clock=None, slow=0.0):
        self.clock, self.slow = clock, slow

    def align(self, fr, f):
        return (fr, fr["faces"].index(f))

    def stats(self, crop):
        fr, i = crop
        return Stats(**fr["stats"][i])

    def feature(self, crop):
        fr, i = crop
        if self.clock is not None and self.slow:
            self.clock.t += self.slow
        return list(fr["embs"][i])


class Frames:
    def size(self, fr):
        return fr["size"]

    def mean(self, fr):
        return fr["mean"]

    def jpeg(self, fr):
        return b"\xff\xd8 not a real picture"


class Cam:
    def __init__(self, frames=None, busy=False, fail=None):
        self.frames, self.is_busy, self.fail = list(frames or []), busy, fail
        self.opened = self.closed = 0
        self.open_now = False
        self.last = None

    def busy(self):
        return self.is_busy

    def open(self):
        if self.fail:
            from kurooto.modules.face.camera import CameraError

            raise CameraError(self.fail)
        self.opened += 1
        self.open_now = True

    def read(self):
        if not self.open_now:
            return None
        if self.frames:
            self.last = self.frames.pop(0)
        return self.last

    def is_open(self):
        return self.open_now

    def close(self):
        self.closed += 1
        self.open_now = False


class Clock:
    def __init__(self, t=10_000.0):
        self.t = t

    def __call__(self):
        return self.t


def stats_of(fr):
    return lambda f: Stats(**fr["stats"][fr["faces"].index(f)])


def embs_of(fr):
    return lambda f: list(fr["embs"][fr["faces"].index(f)])


def judge(p, fr, now):
    return p.judge(fr["faces"], fr["size"], fr["mean"], stats_of(fr), embs_of(fr), now)


def enrolled_plan(skip_extra=False):
    """A plan walked through every step with made-up faces that pass."""
    p = Enrolment(60)
    t = 0.0
    poses = {"front": {}, "left": {"yaw": -0.3}, "right": {"yaw": 0.3}, "up": {"pitch": 0.38}, "down": {"pitch": 0.62},
             "near": {"h": 200.0, "x": 200.0}, "far": {"h": 95.0}, "glasses": {}, "light": {}}  # fmt: skip
    for st in PLAN:
        if skip_extra and st.skippable:
            p.act("skip")
            continue
        for i in range(st.target):
            t += 1.0
            kw = dict(poses[st.key])
            e = GLASSES if st.key == "glasses" else BASE
            stats = {**GOOD, "mean": 70.0} if st.key == "light" else GOOD
            fr = frame([face(dx=i * 5.0, **kw)], [you(e)], [stats])
            v = judge(p, fr, t)
            assert v.ok, (st.key, i, v.reason)
    return p


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    f = a.modules["face"]
    monkeypatch.setattr(f.parts, "missing", lambda keys: [])
    monkeypatch.setattr(f, "_on_call", lambda: False)
    monkeypatch.setattr(f, "_idle_now", lambda: (0.0, False))
    yield a
    a.close()


def events(app, prefix="face_"):
    return [e for e in app.events.tail(500) if e["kind"].startswith(prefix)]


# ------------------------------------------------------------------------------------------------ 1 quality
def test_pose_from_the_landmarks_with_and_without_the_mirror():
    f = face(yaw=-0.3, pitch=0.4, roll=10)
    p = pose(f)
    assert math.isclose(p.yaw, -0.3 * math.cos(math.radians(10)), abs_tol=1e-9) and math.isclose(
        p.roll, 10, abs_tol=1e-6
    )
    assert math.isclose(p.pitch, 0.4, abs_tol=1e-9)
    assert math.isclose(pose(f, mirror=False).yaw, -p.yaw, abs_tol=1e-9)  # the camera's own picture: the other way


@pytest.mark.parametrize(
    "fr,reason",
    [
        (frame([], mean=110), en.R_NO_FACE),
        (frame([face(score=0.85)]), en.R_NO_FACE),
        (frame([face(), face(x=20, score=0.7)], [BASE, BASE]), en.R_TWO),
        (frame([face(h=50)]), en.R_FAR),
        (frame([face(h=400, x=100, y=20)]), en.R_CLOSE),
        (frame([face(x=0)]), "Partly out of view at the right: move to your left a little."),
        (frame([face(y=340)]), "Partly out of view at the bottom: move up a little, or tilt the screen forward."),
        (frame([face(roll=30)]), en.R_TILT),
        (frame([face(yaw=0.3)]), "Look straight at the camera."),
        (frame([face()], [BASE], [{**GOOD, "blur": 20}]), en.R_BLUR),
        (frame([face()], [BASE], [{**GOOD, "mean": 40}]), en.R_DARK),
        (frame([face()], [BASE], [{**GOOD, "mean": 230}]), en.R_BRIGHT),
        (frame([face()], [BASE], [{**GOOD, "bright": 0.2}]), en.R_BRIGHT),
    ],
)
def test_every_check_gives_its_reason(fr, reason):
    v = judge(Enrolment(60), fr, 1.0)
    assert not v.ok and v.reason == reason


def at_near_step(base_h):
    """A plan at its near step, its front steps' faces base_h tall."""
    p = Enrolment(60)
    t = 0.0
    poses = {"front": {"h": base_h, "y": 60.0}, "left": {"yaw": -0.3}, "right": {"yaw": 0.3}, "up": {"pitch": 0.38},
             "down": {"pitch": 0.62}}  # fmt: skip
    while p.current().key != "near":
        key = p.current().key
        t += 1.0
        assert judge(p, frame([face(dx=(t % 7) * 5.0, **poses[key])], [you()]), t).ok, key
    return p, t


def test_the_near_step_can_be_reached_sitting_close():
    """Reported: leaning in kept saying "closer", then "partly out of view": the chin left the frame at the bottom
    before the face was 1.35 times its front height. Now the target leaves room, and only the eyes, nose and mouth must
    stay in view."""
    p, t = at_near_step(250.0)  # sitting close: over half the frame's height already
    want = en.near_target(250.0, 480)
    assert 250.0 < want < 0.7 * 480
    v = judge(p, frame([face(h=280.0, y=150.0)], [you()]), t + 1)
    assert not v.ok and v.reason.startswith("Lean in a little closer (") and "% of the way" in v.reason
    # near enough, its chin past the bottom edge, the eyes, nose and mouth well inside: a sample
    v = judge(p, frame([face(h=want + 2, y=480 - want + 30)], [you()]), t + 2)
    assert v.ok, v.reason


def test_the_near_step_still_needs_the_eyes_and_mouth_in_view():
    p, t = at_near_step(200.0)
    v = judge(p, frame([face(h=260.0, y=330.0)], [you()]), t + 1)  # the mouth at the bottom edge
    assert not v.ok and v.reason.startswith("Partly out of view at the bottom")


def test_the_edge_is_named_as_the_page_shows_it():
    f = face(x=0)
    assert en.edge(f, 640, 480) == "right"  # your right: the camera's left edge
    v = Enrolment(60, mirror=False).judge([f], (640, 480), 110.0, lambda f: Stats(**GOOD), lambda f: BASE, 1.0)
    assert v.reason == "Partly out of view at the left: move to your left a little."


def test_covered_after_ten_dark_frames():
    p = Enrolment(60)
    for i in range(9):
        assert judge(p, frame([], mean=3), i).reason == en.R_NO_FACE
    assert judge(p, frame([], mean=3), 10).reason == en.R_COVERED


def test_repeat_and_not_you():
    p = Enrolment(60)
    fr = frame([face()], [BASE])
    assert judge(p, fr, 1.0).ok
    assert judge(p, frame([face(dx=1)], [BASE]), 2.0).reason == en.R_REPEAT  # the same, barely moved
    for i in range(4):
        assert judge(p, frame([face(dx=10.0 * (i + 1))], [you()]), 3.0 + i).ok
    stranger = [-x for x in BASE]
    assert judge(p, frame([face(dx=80)], [stranger]), 10.0).reason == en.R_NOT_YOU


def test_the_steps_own_rules_and_the_light_step():
    p = Enrolment(60)
    p.baseline = {"pitch": 0.5, "height": 140.0, "light": 120.0}
    p.at = 1  # left
    assert judge(p, frame([face(yaw=-0.05)]), 1).reason == "Turn a bit more to your left."
    assert judge(p, frame([face(yaw=-0.6)]), 1).reason == "Not so far: turn back a little."
    p.at = 2
    assert judge(p, frame([face(yaw=0.05)]), 1).reason == "Turn a bit more to your right."
    p.at = 3
    assert judge(p, frame([face(pitch=0.47)]), 1).reason == "Tilt your chin up a little more."
    p.at = 5
    assert judge(p, frame([face(h=150)]), 1).reason == "Lean in a little closer (29% of the way)."
    p.at = 6
    assert judge(p, frame([face(h=75)]), 1).reason == en.R_FAR  # under min_face_px + 20
    p.at = 8
    assert judge(p, frame([face()], [BASE], [{**GOOD, "mean": 110}]), 1).reason == en.R_LIGHT
    assert judge(p, frame([face()], [BASE], [{**GOOD, "mean": 40}]), 1).ok  # 40 is fine in the light step (>= 30)


# --------------------------------------------------------------------------------------------------- 2 the plan
def test_the_plan_progress_skips_and_the_minimum():
    assert en.TARGET == 52 and en.MINIMUM == 26
    p = Enrolment(60)
    assert p.act("skip") == "This step can't be skipped." and p.current().key == "front"
    assert not p.ready()
    q = enrolled_plan(skip_extra=True)
    assert q.ready() and q.total() == 26 and q.current() is None
    assert {s["key"] for s in q.progress()["steps"] if s["skipped"]} == {"near", "far", "glasses", "light"}
    full = enrolled_plan()
    assert full.total() == 52 and full.progress()["ready"]


def test_add_samples_resumes_at_the_short_steps():
    have = {s.key: s.target for s in PLAN if not s.skippable} | {"near": 2}
    p = Enrolment(60, have, {"pitch": 0.5, "height": 140.0, "light": 120.0}, [BASE])
    assert p.current().key == "near" and p.ready()
    assert p.progress()["total"] == 28


def test_samples_are_spaced():
    p = Enrolment(60)
    assert judge(p, frame([face()], [you()]), 1.0).ok
    v = judge(p, frame([face(dx=20)], [you()]), 1.2)
    assert not v.ok and v.quiet and v.reason == ""
    assert judge(p, frame([face(dx=20)], [you()]), 1.6).ok


def test_back_and_no_glasses():
    p = enrolled_plan(skip_extra=True)
    assert p.act("back").startswith("Back to light")
    assert p.current().key == "light"
    p.act("no_glasses")
    assert "glasses" in p.skipped


# ----------------------------------------------------------------------------------------------- 3 calibration
def samples(n_per=None, glasses=0):
    out, t = [], 0.0
    for st in PLAN:
        if st.key == "glasses":
            for _ in range(glasses):
                out.append(mo.Sample(you(GLASSES), "glasses", t))
            continue
        for _ in range((n_per or {}).get(st.key, st.target)):
            t += 1
            out.append(mo.Sample(you(), st.key, t))
    return out


def test_folds_are_stratified_by_step():
    s = samples()
    f = mo.folds(s)
    for st in PLAN:
        got = [g for x, g in zip(s, f, strict=True) if x.step == st.key]
        assert len(set(got)) == min(len(got), 5)


def test_training_meets_the_false_accept_target_on_the_impostors():
    r = random.Random(5)  # noqa: S311 (made-up test data, not secrets)
    imp = [unit([0.55 * b + x for b, x in zip(BASE, rvec(r), strict=True)]) for _ in range(3000)]  # look-alikes
    out = mo.train(samples(glasses=8), [], imp, "normal", 0, en.TARGETS)
    th = out["thresholds"]
    j = [mo.score(i, out["centroids"]) for i in imp]
    assert th.method == "impostors" and th.hi > mo.FLOOR
    assert sum(x >= th.hi for x in j) / len(j) <= 1e-3
    assert {g for g, _ in out["centroids"]} == {"base", "glasses", "light"}
    strict = mo.train(samples(glasses=8), [], imp, "strict", 0, en.TARGETS)["thresholds"]
    assert strict.hi >= th.hi


def test_the_floor_and_the_grade_and_advice():
    imp = [rvec() for _ in range(500)]  # unrelated faces: the floor holds
    out = mo.train(samples(glasses=8), [], imp, "normal", 0, en.TARGETS)
    assert out["thresholds"].hi == mo.FLOOR and out["grade"] == "good", out["report"]
    poor = mo.train(samples({"near": 0, "far": 0, "light": 0}), [], imp, "normal", 0, en.TARGETS)
    assert poor["grade"] in ("fair", "weak") and any("raise the grade" in a for a in poor["report"]["advice"])
    noisy = [mo.Sample(you(noise=3.0), st, i) for i, st in enumerate(["front"] * 10 + ["left"] * 10)]
    weak = mo.train(noisy, [], imp, "normal", 0, en.TARGETS)
    assert weak["grade"] == "weak" and any("held-out samples" in a for a in weak["report"]["advice"])


def test_no_impostor_set_falls_back_to_the_floor(tmp_path):
    out = mo.train(samples(), [], None, "normal", 0, en.TARGETS)
    assert math.isclose(out["thresholds"].hi, mo.FLOOR + 0.05) and out["thresholds"].method == "floor"
    assert any("someone else" in a for a in out["report"]["advice"])
    from kurooto.core.biometric import load_impostors

    npz_write(tmp_path / "i.npz", emb=[rvec() for _ in range(30)], model_sha256="another", source="x")
    assert load_impostors(tmp_path / "i.npz", fp.SFACE_SHA) is None


def test_the_template_round_trips_and_classifies():
    t = mo.Template(fp.SFACE_SHA)
    t.samples = samples(glasses=8)
    t.retrain([rvec() for _ in range(300)], fp.SFACE_SHA, "normal", 0, en.TARGETS)
    back = mo.Template.from_payload(json.loads(json.dumps(t.to_payload())))
    assert back.hi == t.hi and len(back.samples) == len(t.samples)
    assert back.classify(you())[0] == "owner" and back.classify(you(GLASSES))[0] == "owner"
    assert back.classify(rvec())[0] == "stranger"


# ------------------------------------------------------------------------------------------------- 4 the watcher
class W:
    """A watcher with fakes, and the knobs a test turns."""

    def __init__(self, frames=(), idle=600.0, locked=False, cfg=None, why="", slow=0.0):
        self.clock = Clock()
        self.cam = Cam(frames)
        self.idle, self.locked, self.why = idle, locked, why
        self.got = []
        self.cfg = {"fps": 1.0, "fps_battery": 0.33, "idle_s": 60, "after_absent_min": 20, "frames": 3,
                    "min_face_px": 60, "away_on": False, "away_after_min": 5} | (cfg or {})  # fmt: skip
        self.tpl = mo.Template(fp.SFACE_SHA)
        self.tpl.samples = samples()
        self.tpl.retrain([rvec() for _ in range(200)], fp.SFACE_SHA, "normal", 0, en.TARGETS)
        self.battery = False
        self.w = Watcher(
            camera=self.cam, detector=Det(), embedder=Emb(self.clock, slow), frames=Frames(),
            classify=self.tpl.classify, paused=lambda: self.why, cfg=lambda: self.cfg, idle=lambda: self.idle,
            locked=lambda: self.locked, on_battery=lambda: self.battery,
            emit=lambda kind, **f: self.got.append((kind, f)), clock=self.clock,
            learnable=lambda e: self.tpl.learnable(e, 0.0),
        )  # fmt: skip

    def run(self, seconds, step=0.25):
        end = self.clock.t + seconds
        while self.clock.t < end:
            self.w.tick()
            self.clock.t += step

    def kinds(self):
        return [k for k, _ in self.got]


def mine(n, moving=True):
    return [frame([face(dx=(i * 3.0 if moving else 0.0))], [you()]) for i in range(n)]


def test_an_arrival_needs_three_of_four_frames_and_an_absence():
    t = W(mine(10))
    t.w.present_at -= 25 * 60  # away for 25 minutes
    t.run(6)
    arr = [f for k, f in t.got if k == "arrived"]
    assert len(arr) == 1 and arr[0]["away_min"] >= 25 and not arr[0]["others"]
    assert t.w.counts.you >= 3
    fresh = W(mine(10))  # just started: no absence, no greeting
    fresh.run(6)
    assert "arrived" not in fresh.kinds()


def test_unsure_and_stranger_frames_never_trigger():
    stranger = [frame([face(dx=i * 3.0)], [rvec()]) for i in range(10)]
    t = W(stranger)
    t.w.present_at -= 3600
    t.run(10)
    assert "arrived" not in t.kinds() and t.w.counts.not_you >= 3 and t.w.counts.you == 0
    mixed = [mine(1)[0], frame([face()], [rvec()]), mine(1)[0], frame([face()], [rvec()])] * 2
    t2 = W(mixed)
    t2.w.present_at -= 3600
    t2.run(3.5, step=0.5)  # 2 of 4 are you within the window: not enough
    assert "arrived" not in t2.kinds()


def test_unsure_frames_count_as_not_you_and_never_trigger():
    t = W(mine(20))
    t.w.classify = lambda e: ("unsure", t.tpl.hi - 0.01)  # just under the cut-off: unsure is never you
    t.w.present_at -= 3600
    t.run(10)
    assert "arrived" not in t.kinds() and t.w.counts.unsure >= 3 and t.w.counts.you == 0
    assert t.w.last_seen_owner is None and t.w.candidate is None


def test_with_no_idle_time_the_camera_closes_after_the_wake_look():
    t = W(mine(10_000), idle=None, locked=True)  # this computer can't say how long it's been idle
    t.run(2)
    assert not t.w.camera_open
    t.locked = False  # an unlock: a look of WAKE_S seconds, then closed (never left open for good)
    t.run(1)
    assert t.w.camera_open
    t.run(600, step=1.0)
    assert not t.w.camera_open and t.w.state == "resting" and t.cam.closed >= 1


def test_when_locked_looks_while_the_screen_is_locked():
    t = W(mine(100), idle=None, locked=True)
    t.run(3)
    assert not t.w.camera_open  # off by default: locked means no look
    t.cfg["when_locked"] = True
    t.run(2)
    assert t.w.camera_open and t.w.state == "watching"


def test_turning_it_off_closes_the_camera_at_once(app, trained, monkeypatch):
    from kurooto.core import desktop

    f = trained
    shown = []
    monkeypatch.setattr(desktop, "notify", lambda title, text, urgent=False: shown.append(text))
    monkeypatch.setattr(app, "notify", lambda text, **kw: None)
    t = W(mine(100))
    t.run(1)
    assert t.w.camera_open
    f.watcher = t.w
    f.hold_desktop("Kurooto", "Held while you were away.")
    app.disable("face")
    assert not t.w.camera_open and t.cam.closed == 1 and f._halt.is_set()
    assert f.pause_reason() == "feature off"
    assert shown == ["Held while you were away."] and not f.held  # nothing held is lost when it goes off


def test_a_learn_racing_forget_never_brings_the_template_back(app, trained):
    f = trained
    f._tpl = None
    stale = f.template()  # what a learn or a retrain was holding
    f.forget()
    f._retrain(stale)
    assert not f.store.exists() and not app.secrets.get("face.key")


def test_a_threshold_setting_never_goes_under_the_floor(app, trained):
    f = trained
    t = f.template()
    e = you(noise=4.0, r=random.Random(7))  # noqa: S311 (made-up test data) someone a little like you
    s = t.score(e)
    assert 0.1 < s < mo.FLOOR
    app.settings.set("face.recognise.threshold", s - 0.05)  # would take them for you
    assert f._classify(e)[0] != "owner"


def test_a_still_picture_waits_for_movement():
    still = [frame([face()], [BASE]) for _ in range(6)]
    t = W(still)
    t.w.present_at -= 3600
    t.run(5)
    assert "arrived" not in t.kinds()
    t.cam.frames = mine(6)
    t.run(4)
    assert "arrived" in t.kinds()


def test_someone_else_in_view_is_said_on_the_arrival():
    two = [frame([face(dx=i * 3.0), face(x=40, h=100, score=0.9)], [you(), rvec()]) for i in range(8)]
    t = W(two)
    t.w.present_at -= 3600
    t.run(5)
    arr = [f for k, f in t.got if k == "arrived"]
    assert arr and arr[0]["others"] and ("others", {"on": True}) in t.got


def test_typing_closes_the_camera_after_six_seconds():
    t = W(mine(100), idle=600)
    t.run(2)
    assert t.w.camera_open and t.w.state == "watching"
    t.idle = 0.5  # typing again
    t.run(5)
    assert t.w.camera_open  # recognition's grace
    t.run(2)
    assert not t.w.camera_open and t.w.state == "resting"
    assert ("watch", {"on": False, "why": "resting"}) in t.got


def test_an_unlock_opens_it_for_a_look():
    t = W(mine(100), idle=0.5, locked=True)
    t.run(2)
    assert not t.w.camera_open
    t.locked = False
    t.run(1)
    assert t.w.camera_open


def test_paused_closes_the_camera_and_problems_back_off():
    t = W(mine(10))
    t.run(1)
    assert t.w.camera_open
    t.why = "focus"
    t.run(1)
    assert not t.w.camera_open and t.w.state == "paused" and t.w.why == "focus"
    busy = W(mine(10))
    busy.cam.is_busy = True
    busy.run(1)
    assert busy.w.why == "camera in use by another program" and busy.cam.opened == 0
    busy.cam.is_busy = False
    busy.run(30)
    assert busy.cam.opened == 0  # re-checked only after 60 s
    busy.run(40)
    assert busy.cam.opened == 1
    blocked = W(mine(10))
    blocked.cam.fail = "blocked"
    blocked.run(1)
    assert blocked.w.why == "camera blocked by the system"


def test_a_covered_camera_pauses():
    t = W([frame([], mean=2) for _ in range(20)])
    t.run(12)
    assert t.w.why == "camera covered" and not t.w.camera_open


def test_the_battery_rate_and_the_adaptive_rate():
    t = W(mine(100))
    assert t.w.rate() == 1.0
    t.battery = True
    assert math.isclose(t.w.rate(), 0.33)
    slow = W([frame([face(dx=i * 3.0)], [rvec()]) for i in range(100)], slow=0.2)
    slow.run(4)
    assert slow.w.slow >= 2 and ("slow", {"factor": 2.0}) in slow.got
    assert slow.w.rate() <= 0.5


def test_away_and_back():
    t = W([frame([], mean=100) for _ in range(1000)], cfg={"away_on": True, "away_after_min": 5})
    t.w.present_at -= 4 * 60
    t.run(70, step=1.0)
    assert "left" in t.kinds() and t.w.away and t.w.state == "away"
    t.idle = 0.5  # someone typed: back (never a greeting for that)
    t.run(1)
    assert "back" in t.kinds() and not t.w.away and "arrived" not in t.kinds()
    locked = W([], cfg={"away_on": True, "away_after_min": 5}, locked=True, why="screen locked")
    locked.run(6 * 60, step=5.0)
    assert "left" in locked.kinds()


def test_every_pause_reason_in_order(app, monkeypatch):
    f = app.modules["face"]
    names = [n for n, _ in f.pause_checks()]
    assert names == list(PAUSES) and len(PAUSES) == 17
    assert f.pause_reason() == "feature off"
    app.settings.set("modules.enabled", ["face"])
    assert f.pause_reason() == "not enrolled"
    monkeypatch.setattr(f, "enrolled", lambda: True)
    monkeypatch.setattr(f.parts, "missing", lambda keys: ["model:sface"])
    assert f.pause_reason() == "not set up yet"
    monkeypatch.setattr(f.parts, "missing", lambda keys: [])
    f.pause("1h")
    assert f.pause_reason() == "paused by you"
    f.pause("off")
    monkeypatch.setattr(f, "_idle_now", lambda: (5.0, True))
    assert f.pause_reason() == "screen locked"
    app.settings.set("face.watch.when_locked", True)
    monkeypatch.setattr(f, "_on_call", lambda: True)
    assert f.pause_reason() == "you're on a call"
    monkeypatch.setattr(f, "_on_call", lambda: False)
    app.availability.set_focus(dt.datetime.now() + dt.timedelta(hours=1))
    assert f.pause_reason() == "focus"
    app.availability.set_focus(None)
    app.power.pause(30)
    assert f.pause_reason() == "Kurooto is paused"
    app.power.resume()
    assert f.pause_reason() in ("", "night hours", "template locked")


# ----------------------------------------------------------------------------------------------- 5 the greeting
NOW = dt.datetime(2026, 11, 3, 13, 20)
ITEMS = [
    {"at": "09:00", "what": "Calculus", "state": "done"},
    {"at": "14:00", "what": "Linear Algebra", "state": "next"},
]


def test_compose_each_part_in_order():
    text, parts = gr.compose(["next", "waiting", "deadline", "held"], ITEMS, (2, 1),
                             ("Problem set 3", NOW.replace(hour=23, minute=59)), 3, False, NOW)  # fmt: skip
    assert text == (
        "Welcome back. Next: Linear Algebra at 14:00, in 40 minutes. Two questions and one approval wait for you. "
        "Problem set 3 is due at 23:59. Three messages wait for this evening. Want to go through them?"
    )
    assert parts == ["next", "waiting", "deadline", "held"] and len(text) <= gr.MAX_CHARS
    t2, p2 = gr.compose(["waiting"], [], (1, 0), None, 0, False, NOW.replace(hour=9), first_today=True)
    assert t2 == "Morning. One question waits for you. Want to go through them?" and p2 == ["waiting"]
    t3, p3 = gr.compose(["next", "waiting"], [], (0, 0), None, 0, False, NOW, talk=False)
    assert t3 == "Welcome back." and p3 == []


def test_the_length_limit_drops_the_last_parts():
    long = "A very long deadline title that goes on and on " * 3
    text, parts = gr.compose(["next", "waiting", "deadline", "held"], ITEMS, (2, 2), (long, NOW), 4, False, NOW)
    assert len(text) <= gr.MAX_CHARS and "held" not in parts


def test_others_in_view():
    t, p = gr.compose(["next", "waiting"], ITEMS, (2, 0), None, 0, True, NOW, with_others="short")
    assert t == "Welcome back." and p == []
    t, p = gr.compose(["next"], ITEMS, (0, 0), None, 0, True, NOW, with_others="full")
    assert "Linear Algebra" in t


class FakeVoice:
    def __init__(self):
        self.said, self.mute = [], False

    def muted(self):
        return self.mute

    def tts(self):
        return object(), ""

    def greet(self, text, listen_s, talk=True):
        self.said.append((text, talk))
        return True, "talk" if talk else "spoken"


@pytest.fixture
def greeter(app, monkeypatch):
    v = FakeVoice()
    monkeypatch.setitem(app.modules, "voice", v)
    app.settings.set("modules.enabled", ["face", "voice"])
    app.settings.set("face.watch.night", True)  # whatever the hour the test runs at
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00", "alarm_only": False})
    return app.modules["face"], v


def test_greeting_gates(app, greeter, monkeypatch):
    f, v = greeter
    assert f.greet() and v.said[-1][1] is True
    ev = [e for e in events(app) if e["kind"] == "face_greeted"][-1]
    assert set(ev) <= {"ts", "kind", "parts", "talk"} and ev["talk"] is True
    assert not f.greet()  # within gap_min
    assert events(app)[-1] == {**events(app)[-1], "kind": "face_greet_skipped", "why": "greeted a little while ago"}
    f._greets = {}
    v.mute = True
    assert not f.greet() and events(app)[-1]["why"] == "Voice is muted"
    v.mute = False
    app.availability.set_on_call(dt.datetime.now() + dt.timedelta(minutes=5))
    assert not f.greet() and events(app)[-1]["why"] == "you're on a call"
    app.availability.set_on_call(None)
    assert not f.greet(others=True) and events(app)[-1]["why"] == "someone else is here"
    app.settings.set("face.greet.on", False)
    assert not f.greet() and events(app)[-1]["why"] == "greetings are off"
    app.settings.set("face.greet.on", True)
    f._greets = {"day": dt.date.today().isoformat(), "n": 3, "last": 0}
    assert not f.greet() and events(app)[-1]["why"] == "enough greetings today"


def test_calm_speak_ok_stopped_exam_keep_and_quiet_week(app, greeter, monkeypatch):
    f, _v = greeter
    c = app.calm
    assert c.speak_ok("face.greet")
    app.settings.set("notify.calm.stopped", ["face.greet"])
    assert not c.speak_ok("face.greet")
    app.settings.set("notify.calm.stopped", [])
    monkeypatch.setattr(c, "exam_keep", lambda: ("deadlines",))
    assert not c.speak_ok("face.greet")
    monkeypatch.setattr(c, "exam_keep", lambda: None)
    monkeypatch.setattr(app.rhythm, "quiet_week", lambda t: True)
    assert not c.speak_ok("face.greet")
    with c._db() as db:
        rows = db.execute("select kind, state, held, text from sent where why='face.greet'").fetchall()
    assert [tuple(r) for r in rows] == [
        ("spoken", "spoken", None, ""), ("spoken", "skipped", "stopped", ""), ("spoken", "skipped", "exams", ""),
        ("spoken", "skipped", "quiet", ""),
    ]  # fmt: skip
    assert c._count(dt.date.today().isoformat()) == 0  # never counted against the day's messages
    r = c.reason("face.greet")
    assert r.setting == "face.greet.on" and not r.counted and r.feature == "face"


# ---------------------------------------------------------------------------------------------- 6 Portal.invite
def test_portal_invite_opens_without_awaiting():
    from kurooto.modules.voice.gate import ADDRESSED, CHATTER, Context, Decision, Gate, Heard
    from kurooto.modules.voice.portal import Portal

    sent, clock = [], Clock(100.0)
    p = Portal(send=lambda t: sent.append(t) or "Linear Algebra at 14:00.", speak=lambda t: None,
               publish=lambda k, **f: None, clock=clock, close_s=8)  # fmt: skip
    p.invite("Welcome back. Two questions wait for you. Want to go through them?", 12)
    ctx = p.context()
    assert p.open and not ctx.awaiting and p.close_s == 12
    g = Gate(["Kurooto"], judge=lambda prompt: None)
    clock.t += 2
    d = g.decide(Heard(speech=True, text="yes"), p.context())  # a yes after a question: addressed (rule 8)
    assert d.addressed
    d2 = g.decide(Heard(speech=True, text="what's on today?"), p.context())
    assert d2.addressed
    p.take(Heard(speech=True, text="what's on today?"), d2)
    assert sent == ["what's on today?"]
    chatter = g.decide(Heard(speech=True, text="anyway I told her the bus was late", voices=2), p.context())
    assert chatter.klass == CHATTER
    p.take(Heard(speech=True, text="x"), chatter)
    assert not p.open and len(sent) == 1 and p.close_s == 8  # closed at once, nothing sent, its hold put back
    p.invite("Welcome back.", 12)
    clock.t += 13
    p.tick()
    assert not p.open
    assert Decision(ADDRESSED, 1, "x").addressed and isinstance(ctx, Context)


def test_voice_greet_speaks_then_invites(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        v = app.modules["voice"]
        monkeypatch.setattr(v.parts, "missing", lambda keys: [])
        app.settings.set("modules.enabled", ["voice"])
        monkeypatch.setattr(v, "tts", lambda: (object(), ""))
        spoken = []
        monkeypatch.setattr(v.speaker, "say", lambda text, **_kw: spoken.append(text) or (True, "Spoken."))
        assert v.greet("Welcome back.", 12, talk=True) == (True, "spoken; not listening: listening is off")
        app.settings.set("voice.listen.on", True)
        monkeypatch.setattr(v, "blocked", lambda: "")
        assert v.greet("Welcome back.", 12, talk=True) == (True, "talk") and v.portal.open
        assert not v.portal.awaiting and spoken == ["Welcome back.", "Welcome back."]
        v.mute(True)
        assert v.greet("Welcome back.", 12)[0] is False
    finally:
        app.close()


# ----------------------------------------------------------------------------------------------- 7 sessions
@pytest.fixture
def ready(app, monkeypatch):
    """Face presence on, set up, with a fake camera and fake models."""
    f = app.modules["face"]
    app.settings.set("modules.enabled", ["face"])
    cam = Cam()
    monkeypatch.setattr(f, "make_camera", lambda: cam)
    monkeypatch.setattr(f, "_vision_objects", lambda threads=1: (Det(), Emb(), Frames()))
    monkeypatch.setattr(Session, "start_thread", lambda self, before=None: before() if before else None)
    pushed = []
    monkeypatch.setattr(f, "_push", lambda m, cid=None: pushed.append(m))
    f.cam, f.pushed = cam, pushed
    return f


def feed_plan(f, sess):
    """Walk the session's plan with frames that pass every check."""
    poses = {"left": {"yaw": -0.3}, "right": {"yaw": 0.3}, "up": {"pitch": 0.38}, "down": {"pitch": 0.62},
             "near": {"h": 200.0, "x": 200.0}, "far": {"h": 95.0}}  # fmt: skip
    clock = Clock()
    sess.clock = clock
    sess.started = sess.last_fetch = sess._tick_at = sess._last_frame_at = clock.t
    i = 0
    while sess.plan.current() is not None and i < 500:
        st = sess.plan.current().key
        e = GLASSES if st == "glasses" else BASE
        stats = {**GOOD, "mean": 70.0} if st == "light" else GOOD
        f.cam.frames = [frame([face(dx=(i % 40) * 4.0, **poses.get(st, {}))], [you(e)], [stats])]
        clock.t += 0.6
        sess.last_fetch = clock.t
        sess.step()
        i += 1


def test_a_session_is_refused_when_it_cant_run(app, ready, monkeypatch):
    f = ready
    app.settings.set("modules.enabled", [])
    assert f.enrol_start()[1]["message"].startswith("Face presence is off")
    app.settings.set("modules.enabled", ["face"])
    monkeypatch.setattr(f.parts, "missing", lambda keys: ["pkg:vision"])
    assert "Set Face presence up" in f.enrol_start()[1]["message"]
    monkeypatch.setattr(f.parts, "missing", lambda keys: [])
    monkeypatch.setattr(f, "_on_call", lambda: True)
    assert "call" in f.enrol_start()[1]["message"]
    monkeypatch.setattr(f, "_on_call", lambda: False)
    f.cam.is_busy = True
    assert "in use" in f.enrol_start()[1]["message"]
    f.cam.is_busy = False
    ok, out = f.enrol_start(cid=7)
    assert ok and out["session"] and f.cam.opened == 1
    assert "Another" in f.enrol_start()[1]["message"]
    assert f.stage() == "capturing"  # (the watcher's pause says "not enrolled" first: that comes earlier in PAUSES)


def test_enrol_train_and_the_report(app, ready):
    f = ready
    ok, out = f.enrol_start(cid=7)
    sess = f.session
    feed_plan(f, sess)
    assert sess.plan.total() == 52
    assert any(m.get("kind") == "enrol" and m.get("ok") for m in f.pushed)
    ok, res = f.train(out["session"])
    assert ok and res["report"]["samples"] == 52 and res["report"]["grade"] in ("good", "fair", "weak")
    assert f.session is None and sess.state == "ended" and sess.plan.samples == [] and not f.cam.open_now
    assert f.enrolled() and f.store.status()["samples"] == 52
    ev = [e for e in events(app) if e["kind"] == "face_enrolled"]
    assert ev and set(ev[0]) == {"ts", "kind", "samples", "grade"}
    assert f.stage() == "manage"


def test_timeouts_close_the_camera_and_discard_drops_the_samples(app, ready):
    f = ready
    _ok, out = f.enrol_start()
    s = f.session
    clock = Clock()
    s.clock = clock
    s.started = s.last_fetch = s._tick_at = s._last_frame_at = clock.t
    f.cam.frames = [frame([face()], [BASE])]
    s.step()
    assert s.plan.samples
    clock.t += en.PAGE_GONE_S + 1  # the page went away
    s.step()
    assert s.state == "paused" and not f.cam.open_now and s.plan.samples  # kept a while
    s.resume()
    assert f.cam.open_now and s.state == "capturing"
    f.discard(out["session"])
    assert s.plan.samples == [] and not f.cam.open_now and f.session is None
    _ok, out = f.enrol_start()
    s2 = f.session
    s2.clock = clock
    s2.started = clock.t - en.KEEP_S - 1
    s2.step()
    assert s2.state == "ended" and s2.plan.samples == []


def test_the_live_test_keeps_only_results(app, ready):
    f = ready
    f.enrol_start()
    feed_plan(f, f.session)
    f.train(f.session.id)
    ok, out = f.test_start(cid=3)
    s = f.session
    assert ok and s.kind == "test"
    clock = Clock()
    s.clock = clock
    s.started = s.last_fetch = s._tick_at = s._last_frame_at = clock.t
    s.mark("other")
    for i in range(12):
        f.cam.frames = [frame([face(dx=i * 3.0)], [rvec()])]
        clock.t += 1
        s.last_fetch = clock.t
        s.step()
    s.mark("me")
    for i in range(12):
        f.cam.frames = [frame([face(dx=i * 3.0)], [you()])]
        clock.t += 1
        s.last_fetch = clock.t
        s.step()
    res = [m for m in f.pushed if m.get("kind") == "test_result"]
    assert [r["who"] for r in res] == ["other", "me"]
    assert res[0]["any_accepted"] is False and res[1]["recognised"] >= 8 and res[1]["decided"]
    lt = f.template().last_test
    assert set(lt) == {"at", "me", "other"} and set(lt["other"]) == {"frames", "best", "any_accepted"}
    tests = [m for m in f.pushed if m.get("kind") == "test"]
    assert tests and all(set(x) <= {"box", "score", "class"} for m in tests for x in m["faces"])


# ---------------------------------------------------------------------------------------------- 8 learning
@pytest.fixture
def trained(app, ready):
    f = ready
    f.enrol_start()
    feed_plan(f, f.session)
    f.train(f.session.id)
    return f


def test_learning_only_when_on_spaced_capped_and_undoable(app, trained, monkeypatch):
    f = trained
    t = f.template()
    x = you(noise=0.3)
    assert not f.learn(x)  # the switch is off
    app.settings.set("face.learn.on", True)
    app.settings.set("face.learn.margin", 0.0)
    assert not f.learn(rvec())  # not confident
    assert f.learn(x) and len(t.learned) == 1
    assert not f.learn(you(noise=0.3))  # within every_h
    enrolled_hi = t.hi
    assert all(s.step != "learned" for s in t.samples)  # enrolled samples untouched
    t.learned[-1].at -= 7 * 3600
    assert f.learn(you(noise=0.3)) and len(t.learned) == 2
    app.settings.set("face.learn.max", 2)
    t.learned[-1].at -= 7 * 3600
    assert f.learn(you(noise=0.3)) and len(t.learned) == 2  # the oldest went
    assert "1 learned sample left" in f.learn_undo()
    assert "Forgot 1 learned sample" in f.learn_forget() and t.learned == []
    assert f.learn_undo() == "Nothing learned to undo."
    assert abs(t.hi - enrolled_hi) < 0.2
    ev = [e for e in events(app) if e["kind"] == "face_learned"]
    assert ev and set(ev[0]) == {"ts", "kind", "count"}


def test_held_out_scores_never_include_learned_samples():
    s = samples()
    learned = [mo.Sample(rvec(), "learned", 0) for _ in range(30)]  # junk: if it were graded, TAR would move
    a = mo.train(s, [], None, "normal", 0, en.TARGETS)["report"]
    assert mo.held_out(s) and all(st != "learned" for st, _ in mo.held_out(s))
    b = mo.train(s, learned, None, "normal", 0, en.TARGETS)["report"]
    assert b["samples"] == a["samples"] and b["learned"] == 30


def test_the_watcher_learns_only_after_an_arrival_and_typing():
    t = W(mine(10))
    t.w.present_at -= 3600
    t.run(5)
    assert "arrived" in t.kinds() and t.w.candidate is not None
    assert "learn" not in t.kinds()
    t.idle = 0.5
    t.run(1)
    assert "learn" in t.kinds()


def test_a_new_recognition_model_needs_a_re_enrol(app, trained):
    f = trained
    st = f.store.status()
    from kurooto.core.state import jsave

    jsave(f.store.status_file, {**st, "model_sha": "000000000000"})
    assert f.reenrol_needed() and f.stage() == "enrol"
    assert f.pause_reason() == "re-enrol needed (the recognition model changed)"


# ------------------------------------------------------------------------------------------------ 9 privacy
def every_file(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_the_only_files_kept_are_the_template_and_its_status(app, ready, tmp_path):
    before = every_file(tmp_path)
    f = ready
    f.enrol_start()
    feed_plan(f, f.session)
    f.train(f.session.id)
    t = W(mine(10))  # watching too, with the template's classify
    t.w.classify = f._classify
    t.w.present_at -= 3600
    t.run(5)
    new = every_file(tmp_path) - before
    ignore = ("state/events", "state/locks/", "config/secrets.json", "config/settings.json", "state/calm")
    kept = {n for n in new if not n.startswith(ignore)}
    assert kept == {"state/face/template.bin", "state/face/face.json"}, kept
    raw = (tmp_path / "state/face/template.bin").read_bytes()
    assert not raw.startswith(b"{") and b"samples" not in raw and b"front" not in raw
    from kurooto.core.biometric import pack

    assert pack(f.template().samples[0].e).encode()[:16] not in raw
    st = json.loads((tmp_path / "state/face/face.json").read_text())
    assert not any(k in json.dumps(st) for k in ('"e"', "centroid", "embedding"))


def test_a_wrong_key_locks_and_forget_removes_everything(app, trained):
    f = trained
    good = app.secrets.get("face.key")
    app.secrets.delete("face.key")
    f._tpl = None
    f.store._key = None
    with pytest.raises(Locked):
        f.template()
    assert app.secrets.get("face.key") is None and f.status()["locked"]
    app.settings.set("face.watch.night", True)
    assert f.pause_reason() == "template locked"
    app.secrets.set("face.key", good)
    f.store._key = None
    assert f.template() is not None
    said = f.forget()
    assert said.startswith("Forgot your face model") and app.secrets.get("face.key") is None
    assert not f.store.file.exists() and not f.store.status_file.exists()
    assert events(app)[-1]["kind"] == "face_forgotten"
    assert f.forget() == "There was no face model to forget."


def test_the_key_never_travels():
    from kurooto import diagnostics
    from kurooto.core import profile
    from kurooto.core.biometric import BIOMETRIC_SECRETS
    from kurooto.modules import backups

    class S:
        def names(self):
            return ["face.key", "telegram.token"]

    assert "face.key" in BIOMETRIC_SECRETS and "face.key" in profile.NEVER
    assert "face.key" in diagnostics.KNOWN_SECRETS
    assert "face.key" not in backups.backup_secret_names(S()) and "telegram.token" in backups.backup_secret_names(S())
    assert "face" in backups.SKIP_STATE_DIRS


def test_forget_all_takes_the_face_model_too(app, trained):
    import time

    from kurooto.core import retention

    text, _b = retention.command(app, "all")
    assert "face model" in text
    out = retention.button(app, str(time.time()), "all")
    assert "face model" in out and not trained.store.exists()


def test_events_carry_no_scores_or_pictures(app, trained):
    t = W(mine(10))
    f = trained
    t.w.emit = f._on_watch
    t.w.present_at -= 3600
    t.run(5)
    f.pause("1h")
    f.forget()
    allowed = {"ts", "kind", "on", "why", "away_min", "parts", "talk", "samples", "grade", "count", "part", "error"}
    for e in events(app):
        assert set(e) <= allowed, e
        assert not any(k in e for k in ("score", "emb", "img", "frame"))


def test_the_diagnostics_bundle_says_counts_only(app, trained, tmp_path):
    from kurooto import diagnostics

    dest, names = diagnostics.bundle(app, tmp_path / "d.zip")
    import zipfile

    with zipfile.ZipFile(dest) as z:
        assert not any(n.startswith(("state/face", "face/")) for n in z.namelist())
        d = json.loads(z.read("face.json"))
    assert d == {"on": True, "enrolled": True, "samples": 52, "set_up": True}


# ------------------------------------------------------------------------------------------------- 10 parts
def test_what_it_needs_and_where(app):
    f = app.modules["face"]
    assert f.wants() == ["pkg:vision", "model:yunet", "model:sface"]
    p = fp.parts(app)
    assert p.py == (app.paths.app / "voice" / p.py.name)  # shared with Voice: one numpy
    assert p.models_dir == app.paths.app / "face" / "models" and p.feature == "Face presence"
    assert all(
        m.sha256 and m.url.startswith("https://media.githubusercontent.com/")
        for k, ms in p.table.items()
        for m in ms
        if k != "iris"  # (0.8.17) the optional eye model comes from MediaPipe's store: test_face_gaze.py
    )
    from kurooto.core import egress

    assert "media.githubusercontent.com" in egress.HOSTS


class Resp:
    def __init__(self, data):
        self.data, self.headers = data, {"Content-Length": str(len(data))}

    def read(self, n=-1):
        out, self.data = self.data, b""
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_checksum_mismatch_deletes_the_file(app, monkeypatch):
    from kurooto.core import egress

    p = fp.parts(app)
    monkeypatch.setattr(egress, "urlopen", lambda url, feature, timeout=60: Resp(b"something else"))
    ok, msg = p.download_model("yunet", lambda s: None)
    assert not ok and "didn't match its checksum" in msg
    assert not list(p.models_dir.glob("*")) if p.models_dir.exists() else True
    good = b"made-up model bytes"
    p.table = {"yunet": [fp.ModelFile(fp.YUNET, "https://media.githubusercontent.com/x", 0.1,
                                      hashlib.sha256(good).hexdigest())]}  # fmt: skip
    monkeypatch.setattr(egress, "urlopen", lambda url, feature, timeout=60: Resp(good))
    assert p.download_model("yunet", lambda s: None)[0] and (p.models_dir / fp.YUNET).read_bytes() == good


def test_install_from_a_folder(app, tmp_path, monkeypatch):
    from kurooto.core import proc

    p = fp.parts(app)
    good = b"the detector"
    p.table = {
        "yunet": [fp.ModelFile(fp.YUNET, "u", 0.1, hashlib.sha256(good).hexdigest())],
        "sface": [fp.ModelFile(fp.SFACE, "u", 0.1, "0" * 64)],
    }
    folder = tmp_path / "offline"
    folder.mkdir()
    (folder / fp.YUNET).write_bytes(good)
    (folder / fp.SFACE).write_bytes(b"wrong bytes")
    ran = []

    def run(cmd, timeout=0):
        ran.append(cmd)
        (p.py / "cv2").mkdir(parents=True, exist_ok=True)
        return (
            proc.Result(0, "", "") if hasattr(proc, "Result") else type("R", (), {"ok": True, "out": "", "err": ""})()
        )

    monkeypatch.setattr(proc, "run", run)
    monkeypatch.setattr(p, "installer", lambda: ["uv", "pip", "install", "--python", "py"])
    said = []
    ok, msg = p.install_from(folder, fp.WANTS, said.append)
    assert not ok and msg == "Still missing: model:sface."
    assert (p.models_dir / fp.YUNET).read_bytes() == good and not (p.models_dir / fp.SFACE).exists()
    assert ran and "--no-index" in ran[0] and "--find-links" in ran[0] and str(folder) in ran[0]
    assert any("didn't match its checksum" in s for s in said)
    assert p.install_from(tmp_path / "nope", fp.WANTS, said.append) == (
        False,
        f"There's no folder at {tmp_path / 'nope'}.",
    )


def test_voices_parts_are_unchanged(app):
    from kurooto.modules.voice.parts import PACKAGES, Parts, models

    v = Parts(app.paths.app / "voice", app.paths.app)
    assert v.packages is PACKAGES and v.feature == "Voice" and v.models_dir == app.paths.app / "voice" / "models"
    assert set(v.table) == set(models())


# ---------------------------------------------------------------------------------------------------- 11 the API
def test_the_api_stages_and_routes(app, ready):
    from kurooto.web.api import Api

    api = Api(app)
    f = ready
    code, st = api.get("face")
    assert code == 200 and st["stage"] == "enrol" and st["plan"][0]["key"] == "front" and st["target"] == 52
    assert api.face_frame({"s": "nothing"}) is None
    code, out = api.post("face/enrol/start", {"cid": "7"})
    assert out["ok"] and api.get("face")[1]["stage"] == "capturing"
    sid = out["session"]
    f.cam.frames = [frame([face()], [BASE])]
    f.session.step()
    assert api.face_frame({"s": sid}) == b"\xff\xd8 not a real picture"
    assert (
        api.post("face/enrol/step", {"session": sid, "action": "skip"})[1]["message"] == "This step can't be skipped."
    )
    assert api.post("face/train", {"session": sid})[1]["ok"] is False
    assert api.post("face/enrol/discard", {"session": sid})[1]["ok"]
    assert api.face_frame({"s": sid}) is None
    assert api.post("face/pause", {"arg": "1h"})[1]["message"].startswith("Face presence paused")
    assert api.post("face/strictness", {"level": "bogus"})[1]["ok"] is False
    assert api.post("face/nothing", {})[0] == 404
    app.settings.set("modules.enabled", [])
    assert api.get("face")[1]["stage"] == "off"


def test_the_frame_route_is_never_kept():
    src = (SRC / "web" / "server.py").read_text(encoding="utf-8")
    i = src.index('if path == "/api/face/frame"')
    block = src[i : i + 400]
    assert 'self._send(200, jpg, "image/jpeg")' in block and "etag" not in block  # no-store, nosniff (_send)
    assert '"Cache-Control", "no-store"' in src and '"X-Content-Type-Options", "nosniff"' in src
    js = (SRC / "web" / "static" / "face.js").read_text(encoding="utf-8")
    assert 'cache: "no-store"' in js and "getUserMedia" not in js and 'localStorage.setItem("kurooto.face.say"' in js


def test_the_card_and_switches(app, ready):
    f = ready
    c = f.card()
    assert {t["id"] for t in c["toggles"]} == {"greet.on", "greet.talk", "away.on", "learn.on"}
    assert f.card_action("learn.on", True) == "Learn slowly from confident sightings: on."
    assert app.settings.get("face.learn.on") is True
    from kurooto.core.config import Settings

    d = Settings(Path("/nonexistent/x.json"))
    assert (
        d.get("face.learn.on") is False and d.get("face.away.on") is False and d.get("face.greet.with_others") == "skip"
    )


def test_the_command_and_plain_words(app, trained):
    f = trained
    from kurooto.modules.base import Incoming

    m = Incoming(text="/face")
    assert f._cmd(m, "").startswith("Face presence:") and "Faces since start" in f._cmd(m, "")
    a = f._cmd(m, "forget")
    assert a.buttons[0][0][1].startswith("fce:") and a.buttons[0][1] == ("Keep it", "fce:0:keep")
    assert f.store.exists()  # asking never deletes
    ints = {i.name: i for i in f.intents()}
    assert ints["face_status"].match("is the camera on?") == {} and ints["face_status"].match("is it raining") is None
    assert ints["face_pause"].match("pause the camera for an hour") == {"arg": "1h"}
    assert ints["face_pause"].match("stop watching") == {"arg": ""}
    assert ints["face_pause"].match("stop watching the pot") is None
    assert ints["face_forget"].match("forget my face") == {}
    assert ints["face_forget"].run(m, {}).buttons and f.store.exists()
    assert app.callback("fce:0:keep") == "Kept." and f.store.exists()
    assert app.callback("fce:1:forget").startswith("That button has expired")
    import time

    assert app.callback(f"fce:{int(time.time())}:forget").startswith("Forgot your face model")


def test_turning_it_off_offers_to_delete(app, trained, monkeypatch):
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    app.disable("face")
    assert sent and sent[0][1]["why"] == "face.off"
    assert sent[0][1]["buttons"][0][0][0] == "Delete my face data" and trained.store.exists()


# -------------------------------------------------------------------------------- 12 a face never authorises
def test_a_face_never_authorises_anything():
    for rel in ("core/tap.py", "core/ask.py", "core/tools.py"):
        src = (SRC / rel).read_text(encoding="utf-8")
        assert "modules.face" not in src and 'modules.get("face")' not in src and "modules['face']" not in src, rel
        assert "face_arrived" not in src and "biometric" not in src, rel
    from kurooto.core import tap

    assert "face" not in " ".join(tap.WAYS)
    assert tap.GUARDED["camera.open"].ways == ("button",)
    assert tap.BUTTONS["fce"] == "data.delete"


# ------------------------------------------------------------------------------------- the impostor-set tool
def test_the_impostor_tool_keeps_one_clear_face_per_image(tmp_path):
    import sys

    sys.path.insert(0, str(SRC.parents[1] / "tools"))
    try:
        import face_impostors as tool
    finally:
        sys.path.pop(0)
    imgs = {
        "a": frame([face()], [rvec()]),
        "b": frame([face(), face(x=10, score=0.95)], [rvec(), rvec()]),
        "c": frame([face(score=0.5)], [rvec()]),
        "d": None,
        "e": frame([face()], [rvec()]),
    }
    rows, seen = tool.build(
        [Path(k) for k in imgs],
        lambda img: Det().detect(img, 0.6),
        lambda img, f: Emb().feature(Emb().align(img, f)),
        lambda p: imgs[str(p)],
        limit=10,
    )
    assert len(rows) == 2 and seen == {"read": 4, "unreadable": 1, "no face": 1, "several faces": 1, "used": 2}
    out = tmp_path / "imp.npz"
    from kurooto.core.biometric import load_impostors

    npz_write(out, emb=rows, model_sha256=fp.SFACE_SHA, source="made up for a test")
    assert len(load_impostors(out, fp.SFACE_SHA)) == 2
    spread = tool.spread([rvec() for _ in range(40)])
    assert spread["n"] == 20 and -1 <= spread["median"] <= spread["max"] <= 1


def test_away_holds_desktop_popups_and_calls_until_back(app, trained, monkeypatch):
    from kurooto.core import desktop
    from kurooto.core.notify import Message

    f = trained
    for k in ("face.away.on", "face.away.hold_desktop", "face.away.hold_calls"):
        app.settings.set(k, True)
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00", "alarm_only": False})
    t = W()
    t.w.away, t.w.left_at = True, t.clock.t
    f.watcher = t.w
    shown = []
    monkeypatch.setattr(desktop, "notify", lambda title, text, urgent=False: shown.append(text))
    f.start()
    assert app.away_from_desk()
    app.notifier._desktop(Message("Your build finished."))
    assert shown == [] and len(f.held) == 1
    assert app.availability.call_block()[0] == "you've stepped away from your desk"
    t.w.away = False
    f._on_watch("back")
    assert shown == ["Your build finished."] and not f.held
    assert app.availability.call_block() == (None, None) and not app.away_from_desk()
    app.settings.set("face.away.hold_desktop", False)
    t.w.away = True
    app.notifier._desktop(Message("Shown at once."))
    assert shown[-1] == "Shown at once."
    f.stop()
    assert "face:away" not in app.availability.blockers


def test_others_nearby_is_a_shared_signal_with_no_details(app):
    from kurooto.core import nearby

    f = app.modules["face"]
    assert not nearby.others(app)
    f._on_watch("others", on=True)
    assert nearby.others(app) and nearby.sources(app) == ["face"]
    f._on_watch("others", on=False)
    assert not nearby.others(app)
    ev = [e for e in app.events.tail(20) if e["kind"] == "nearby_others"]
    assert [e["on"] for e in ev] == [True, False] and all(set(e) == {"ts", "kind", "on", "source"} for e in ev)


def test_a_second_face_that_stays_keeps_others_nearby_on(app, monkeypatch):
    """nearby.py drops a signal not refreshed for STALE_S: a second face in view for longer must keep it on (it
    once said "others" only when it changed, so after two minutes Kurooto thought you were alone again)."""
    from kurooto.core import nearby

    f = app.modules["face"]
    two = [frame([face(dx=i * 3.0), face(x=40, h=100, score=0.9)], [you(), rvec()]) for i in range(400)]
    t = W(two)
    t.w.emit = lambda kind, **kw: (t.got.append((kind, kw)), f._on_watch(kind, **kw))
    now = [1000.0]
    monkeypatch.setattr(nearby.time, "monotonic", lambda: now[0])
    t.run(3)
    assert nearby.others(app)
    for _ in range(4):  # 4 x 60 s of frames, past STALE_S
        now[0] += 60
        t.run(1)
    assert nearby.others(app)
    assert [e["on"] for e in app.events.tail(50) if e["kind"] == "nearby_others"] == [True]  # one event, not per frame
    t.cam.frames = mine(5)
    t.run(2)
    assert not nearby.others(app)


def test_start_over_and_undo_the_last_training(app, trained):
    f = trained
    old = f.template()
    old_cents = [c for _, c in old.cents]
    ok, out = f.enrol_start(mode="new")  # Start over: a whole new plan
    assert ok and not f.session.plan.have
    assert f.template() is old  # the old model is still the one in use
    feed_plan(f, f.session)
    ok, out = f.train(f.session.id)
    assert ok and out["can_undo"] and f.status()["can_undo"]
    assert [c for _, c in f.template().cents] != old_cents
    from kurooto.web.api import Api

    code, r = Api(app).post("face/undo", {})
    assert r["ok"] and "previous face model" in r["message"]
    f._tpl = None  # read back from the sealed file (float16 inside it)
    back = [c for _, c in f.template().cents]
    assert len(back) == len(old_cents) and all(
        abs(a - b) < 2e-3 for x, y in zip(back, old_cents, strict=True) for a, b in zip(x, y, strict=True)
    )
    assert len(f.template().samples) == len(old.samples)
    assert Api(app).post("face/undo", {})[1]["ok"] is False  # once
    f.enrol_start(mode="add")
    feed_plan(f, f.session)
    f.train(f.session.id)
    f.forget()
    assert not f.status()["can_undo"] and not f.store.exists()  # forget drops the undo too


def test_start_over_never_overwrites_a_model_whose_key_cant_be_read(app, trained):
    f = trained
    f.enrol_start(mode="new")
    feed_plan(f, f.session)
    app.secrets.delete("face.key")
    f._tpl = None
    f.store._key = None
    ok, out = f.train(f.session.id)
    assert not ok and "key can't be read" in out["message"] and f.store.exists()


# ------------------------------------------------------------------------------- 13 hooks for add-ons (0.8.12)
def test_nobody_watching_people_costs_nothing():
    t = W(mine(10) + [frame([face(), face(x=40, h=100)], [you(), rvec()])])
    t.run(12)
    assert "people" not in t.kinds()  # off: no list built, nothing handed over


def test_each_frame_hands_every_face_with_its_place_identity_and_numbers():
    small = face(x=500, y=40, h=40.0, score=0.9)  # too small to judge: its place only
    stranger = face(x=40, y=200, h=100.0, score=0.92, yaw=0.3)
    fr = frame([face(), stranger, small], [you(), rvec(), rvec()])
    t = W([fr] * 5 + [frame()])
    t.w.people = lambda: True
    t.run(6)
    lists = [f["faces"] for k, f in t.got if k == "people"]
    assert lists and lists[-1] == []  # an empty frame is handed over too
    one = lists[0]
    assert len(one) == 3
    me, other, far = one
    assert me["who"] == "owner" and me["score"] > 0.5 and len(me["e"]) == 128
    assert other["who"] == "stranger" and len(other["e"]) == 128
    assert other["yaw"] == pytest.approx(0.3, abs=0.01)  # as pose() gives it
    assert far["who"] is None and far["e"] is None and far["score"] is None
    assert me["h_px"] == 140.0 and me["h"] == pytest.approx(140 / 480, abs=1e-3)
    assert me["w"] == pytest.approx(140 / 640, abs=1e-3)
    assert -1 <= me["x"] <= 1 and -1 <= me["y"] <= 1 and far["x"] > 0.5 and far["y"] < 0
    assert set(me) == {"h_px", "h", "w", "x", "y", "yaw", "det", "who", "score", "e"}
    assert t.w.counts.you >= 1 and t.w.counts.not_you >= 1  # the usual bookkeeping still runs


def test_a_hold_keeps_the_camera_open_while_you_type_but_never_past_a_pause():
    t = W(mine(100), idle=0.0)  # typing: input is the presence signal
    t.run(10)
    assert not t.w.camera_open and t.w.state == "resting"
    held = [True]
    t.w.held = lambda: held[0]
    t.run(2)
    assert t.w.camera_open and t.w.state == "watching"
    for why in ("night hours", "you're on a call", "paused by you", "screen locked"):
        t.why = why
        t.run(1)
        assert not t.w.camera_open and (t.w.state, t.w.why) == ("paused", why)
    t.why = ""
    t.run(1)
    assert t.w.camera_open
    held[0] = False  # released: the input grace has long passed, so it closes
    t.run(1)
    assert not t.w.camera_open


def test_face_hands_people_to_each_add_on_and_unsubscribes(app):
    f = app.modules["face"]
    got_a, got_b = [], []

    def a(faces):
        got_a.append(faces)
        faces[0]["who"] = "changed by a"
        raise RuntimeError("an add-on's mistake")

    off_a = f.watch_people(a)
    f.watch_people(got_b.append)
    assert f._people_on()
    faces = [{"h_px": 140.0, "who": "stranger", "e": [0.1] * 4}]
    f._on_watch("people", faces=faces)
    assert got_a and got_b[0][0]["who"] == "stranger"  # each its own copy; one add-on's mistake stops nothing
    assert [e["kind"] for e in events(app)][-1] == "face_failed" and "e" not in events(app)[-1]
    off_a()
    off_a()  # twice is fine
    app.settings.set("face.addons.watch", False)
    assert not f._people_on()
    f._on_watch("people", faces=faces)
    assert len(got_a) == 1 and len(got_b) == 1
    app.settings.set("face.addons.watch", True)
    f._on_watch("people", faces=faces)
    assert len(got_a) == 1 and len(got_b) == 2
    assert f.build_watcher(camera=Cam(), detector=Det(), embedder=Emb(), frames=Frames()).people() is True


def test_holds_are_capped_named_on_the_card_and_switchable(app, trained):
    import time

    f = trained
    app.settings.set("face.watch.night", True)  # whatever the hour the test runs at
    assert f.hold_watch("meeting people", 3600) and f.holds() == ["meeting people"]
    assert f._holds["meeting people"] - time.monotonic() <= 600.5  # capped: renew it to keep it
    w = f.build_watcher(camera=Cam(), detector=Det(), embedder=Emb(), frames=Frames())
    assert w.held()
    f.watcher = w
    w.state = "watching"
    assert "an add-on is looking (meeting people)" in f.line() and f.status()["holds"] == ["meeting people"]
    f._holds["meeting people"] = time.monotonic() - 1  # expired: gone
    assert f.holds() == [] and not w.held()
    f.hold_watch("meeting people")
    f.release_watch("meeting people")
    assert f.holds() == []
    app.settings.set("face.addons.hold", False)
    assert not f.hold_watch("meeting people") and f.holds() == []


def test_your_desk_height_from_enrolment_then_from_sightings(app, trained):
    f = trained
    app.modules["face"]._desk.clear()
    d = f.owner_desk_height()
    assert d["from"] == "enrolment" and d["px"] == pytest.approx(140.0, abs=1)
    assert d["h"] == pytest.approx(140 / 480, abs=0.01)
    for i in range(12):
        f._desk_at = 0.0
        f._on_watch("seen", x=0.0, y=0.0, w=0.2, h=0.25 + i * 0.001, px=120.0 + i)
    d = f.owner_desk_height()
    assert d["from"] == "seen" and d["n"] == 12 and 120 <= d["px"] <= 131 and 0.25 <= d["h"] <= 0.262
    f.forget()
    assert f.owner_desk_height() is None  # sizes go with your face model


def test_people_events_never_reach_the_event_log_or_the_pages(app, trained):
    t = W([frame([face(), face(x=40, h=100)], [you(), rvec()])] * 6)
    f = trained
    pushed = f.pushed
    f.watch_people(lambda faces: None)
    t.w.emit, t.w.people = f._on_watch, f._people_on
    t.w.present_at -= 3600
    t.run(5)
    for e in events(app):
        assert not any(k in e for k in ("score", "e", "emb", "faces", "h_px"))
    assert all(m.get("kind") != "people" and "e" not in m and "h" not in m for m in pushed)


# ------------------------------------------------------------------------------------- 14 tracking (0.8.12)
from kurooto.modules.face import watch as wa  # noqa: E402


def tracked(frames, mode=wa.TRACK_FAST, cfg=None):
    t = W(frames, idle=600.0, cfg={"track_on": True, "track_fps": 10} | (cfg or {}))
    t.w.tracking = lambda: mode
    return t


def loop(t, seconds):
    """Face._run with the fake clock: a full tick every 0.25 s, track_tick between, sleeping wait_s. Returns the loop's
    passes (each one a sleep of at least wait_s's floor)."""
    end, nxt, n = t.clock.t + seconds, t.clock.t, 0
    while t.clock.t < end:
        if t.clock.t >= nxt:
            nxt = t.clock.t + 0.25
            t.w.tick()
        else:
            t.w.track_tick()
        w = t.w.wait_s(nxt - t.clock.t)
        assert w >= wa.WAIT_MIN_S
        t.clock.t += w
        n += 1
    return n


def faces_msgs(t):
    return [f["faces"] for k, f in t.got if k == "faces"]


class Count(Det):
    def __init__(self, clock=None, cost=0.0):
        self.n, self.clock, self.cost = 0, clock, cost

    def detect(self, fr, min_score):
        self.n += 1
        if self.clock is not None:
            self.clock.t += self.cost
        return super().detect(fr, min_score)


def test_track_ids_stay_with_each_face_as_they_move_and_swap_places_in_the_list():
    frs = []
    for i in range(80):
        a, b = face(x=100 + i * 2.0, h=120.0), face(x=420 - i * 1.0, y=180, h=100.0, score=0.9)
        frs.append(frame([a, b] if i % 2 else [b, a], [you(), rvec()] if i % 2 else [rvec(), you()]))
    t = tracked(frs)
    loop(t, 6)
    msgs = [m for m in faces_msgs(t) if len(m) == 2]
    assert len(msgs) > 40  # about 10 a second
    ids = {(f["id"], f["x"] < 0) for m in msgs for f in m}
    assert len({i for i, _ in ids}) == 2 and len(ids) == 2  # the left face keeps its id, the right one its own
    assert all(f["owner"] for m in msgs[3:] for f in m if f["x"] < 0)
    assert not any(f["owner"] for m in msgs for f in m if f["x"] > 0)
    assert set(msgs[-1][0]) == {"id", "x", "y", "h", "owner", "m"}  # places only: no numbers, no scores
    assert "seen" in t.kinds()  # face_seen's source still runs
    t.cam.frames = [frame([face(x=560, y=10, h=60.0)], [rvec()])] * 50  # both gone, someone else elsewhere
    loop(t, 2)
    last = faces_msgs(t)[-1]
    assert len(last) == 1 and last[0]["id"] not in {i for i, _ in ids} and not last[0]["owner"]
    t.w.release()
    assert faces_msgs(t)[-1] == [] and not t.w.tracks  # the camera closed: nobody, and nothing kept


def test_micro_movement_is_zero_when_still_and_rises_with_a_small_nod():
    still = tracked([frame([face()], [you()])] * 200)
    loop(still, 4)
    assert max(f["m"] for m in faces_msgs(still) for f in m) == 0.0
    nod = tracked([frame([face(pitch=0.5 + 0.1 * math.sin(i / 2))], [you()]) for i in range(200)])
    loop(nod, 4)
    ms = [m[0]["m"] for m in faces_msgs(nod)]
    assert 0.2 < max(ms) <= 1.0
    big = tracked([frame([face(x=100 + 25 * (i % 8))], [you()]) for i in range(200)])
    loop(big, 4)
    assert max(m[0]["m"] for m in faces_msgs(big)) > max(ms)
    nod.cam.frames = [frame([face(pitch=0.5)], [you()])] * 100  # still again: it fades
    loop(nod, 3)
    assert faces_msgs(nod)[-1][0]["m"] < 0.05


def test_tracking_fast_detects_at_its_own_rate_recognition_stays_slow_and_the_loop_never_spins():
    t = tracked([frame([face()], [you()])] * 400)
    det = t.w.detector = Count()
    feats = []
    real = t.w.embedder.feature
    t.w.embedder.feature = lambda crop: feats.append(1) or real(crop)
    passes = loop(t, 10)
    assert 90 <= det.n <= 115  # face.track.fps 10
    assert len(feats) <= 16  # SFace at the watcher's own rate (1 a second; 2 for the first 5 s after you)
    assert passes <= 10 * (10 + 4) + 5  # sleeping until the next frame or tick, never a busy loop
    det.n = 0
    t.w.tracking = lambda: wa.TRACK_SLOW  # an add-on's ordinary hold: faces at the recognition rate only
    passes = loop(t, 10)
    assert det.n <= 11 and passes <= 41 and faces_msgs(t)[-1]
    t.cfg["track_on"] = False  # the switch: nothing tracked, the old rate
    det.n, n_faces = 0, len(faces_msgs(t))
    loop(t, 10)
    assert det.n <= 11 and len(faces_msgs(t)) == n_faces + 1 and faces_msgs(t)[-1] == []  # one "nobody" on the way out


def test_switch_off_means_face_seen_only_as_before():
    t = tracked([frame([face(), face(x=40, h=100)], [you(), rvec()])] * 100, cfg={"track_on": False})
    det = t.w.detector = Count()
    loop(t, 5)
    assert "faces" not in t.kinds() and "seen" in t.kinds() and not t.w.tracks
    assert det.n <= 10  # the watcher's own rate (2 a second while it confirms you)


def test_a_slow_machine_halves_the_tracking_rate_and_recovers():
    t = tracked([frame([face()], [you()])] * 300)
    loop(t, 1)
    t.w.detector = Count(t.clock, 0.08)
    loop(t, 3)
    assert t.w.track_slow >= 2 and t.w.track_rate() <= 5
    t.w.detector = Det()
    loop(t, 60)
    assert t.w.track_slow < 2


def test_who_wants_every_face_and_the_switch(app, trained):
    f = trained
    assert f._track_mode() == wa.TRACK_OFF  # no page in sight, no hold, no add-on: nothing is worked out
    f.hold_watch("reading the room")
    assert f._track_mode() == wa.TRACK_SLOW
    f.hold_watch("Eye tracking")
    assert f._track_mode() == wa.TRACK_FAST
    f.release_watch("Eye tracking")
    f.release_watch("reading the room")
    off = f.watch_faces(lambda faces: None)
    assert f._track_mode() == wa.TRACK_SLOW
    off()
    f._page_in_sight = lambda: True  # a dashboard in sight
    w = f.build_watcher(camera=Cam(), detector=Det(), embedder=Emb(), frames=Frames())
    assert f._track_mode() == wa.TRACK_FAST and w.tracking() == wa.TRACK_FAST and w.cfg()["track_fps"] == 10
    app.settings.set("face.track.on", False)
    assert f._track_mode() == wa.TRACK_OFF


def test_faces_reach_open_pages_at_most_ten_a_second_and_add_ons_each_their_own_copy(app, trained):
    f = trained
    pushed = f.pushed
    f._page_in_sight = lambda: True
    one = [{"id": 1, "x": 0.1, "y": -0.2, "h": 0.3, "owner": True, "m": 0.4}]
    got, bad = [], []

    def broken(faces):
        bad.append(faces)
        faces[0]["x"] = 9
        raise RuntimeError("an add-on's mistake")

    f.watch_faces(broken)
    off = f.watch_faces(got.append)
    for _ in range(50):
        f._on_watch("faces", faces=one)
    msgs = [m for m in pushed if m.get("kind") == "faces"]
    assert len(msgs) == 1 and msgs[0] == {"t": "face", "kind": "faces", "faces": one}
    assert len(got) == 50 and got[-1][0]["x"] == 0.1  # one add-on's change never reaches the next
    f._on_watch("faces", faces=[])  # the last face gone: always said
    assert pushed[-1]["faces"] == [] and got[-1] == []
    f._page_in_sight = lambda: False  # no page in sight: nothing pushed
    f._faces_at = 0.0
    f._on_watch("faces", faces=one)
    assert pushed[-1]["faces"] == []
    off()
    app.settings.set("face.addons.watch", False)
    f._on_watch("faces", faces=one)
    assert len(got) == 52 and len(bad) == 52
    for e in events(app):
        assert not any(k in e for k in ("faces", "x", "m", "e"))


def test_the_watch_thread_sleeps_between_frames_while_tracking(app, trained, monkeypatch):
    """The real loop (Face._run) for a second with fakes: about 10 detections, a few dozen passes, little CPU."""
    import threading
    import time

    f = trained
    app.settings.set("face.watch.night", True)  # whatever the hour the test runs at
    f.cam.frames = [frame([face()], [you()])] * 200
    det = Count()
    monkeypatch.setattr(f, "_vision_objects", lambda threads=1: (det, Emb(), Frames()))
    f.hold_watch("eye tracking")  # you're typing (the fixture's idle is 0): the hold opens the camera
    f.watcher = f.build_watcher()
    passes = [0]
    real = f.watcher.track_tick
    f.watcher.track_tick = lambda: passes.__setitem__(0, passes[0] + 1) or real()
    cpu = []

    def run():
        t0 = time.thread_time()
        f._run()
        cpu.append(time.thread_time() - t0)

    th = threading.Thread(target=run, daemon=True)
    th.start()
    time.sleep(1.2)
    f._halt.set()
    th.join(5)
    assert f.watcher.camera_open is False and f.cam.closed >= 1  # stopping closes it
    assert 7 <= det.n <= 16 and passes[0] <= 1.2 * (10 + 4) + 6
    assert cpu[0] < 0.3  # the loop's own cost with free fakes (the real cost is YuNet's: docs/wiki/dev/face.md)


def _cams(tmp_path, holders_of: dict[str, list[int]], loopback=("video42",)):
    """A fake /sys/class/video4linux and /proc: cameras by name, which processes hold which node."""
    sysfs, proc = tmp_path / "sys", tmp_path / "proc"
    for node, name in (("video0", "Integrated Camera"), ("video42", "Kurooto body cam")):
        (sysfs / node).mkdir(parents=True)
        (sysfs / node / "name").write_text(name)
        if node in loopback:
            (sysfs / node / "max_openers").write_text("10")
    for node, pids in holders_of.items():
        for pid in pids:
            fd = proc / str(pid) / "fd"
            fd.mkdir(parents=True, exist_ok=True)
            (fd / "3").symlink_to(f"/dev/{node}")
    return sysfs, proc


def test_a_virtual_camera_another_program_feeds_isnt_busy(tmp_path):
    """The body phone's camera (v4l2loopback) is open in scrcpy, which writes it: Face presence may still read it, and
    with no camera chosen, the laptop's camera isn't held up by it either."""
    from kurooto.modules.face import camera as cam

    sysfs, proc = _cams(tmp_path, {"video42": [999001]})
    devs = cam.devices("linux", sysfs)
    assert cam.holders("/dev/video42", proc, me=1) == [999001]  # someone has it open...
    assert [d.node for d in cam.free(devs, sysfs, proc)] == ["/dev/video0", "/dev/video42"]  # ...and it's shared
    sysfs2, proc2 = _cams(tmp_path / "b", {"video0": [999002]}, loopback=())
    devs2 = cam.devices("linux", sysfs2)
    assert [d.node for d in cam.free(devs2, sysfs2, proc2)] == ["/dev/video42"]  # one in use leaves the other
    assert cam.free(cam.pick(devs2, "Integrated"), sysfs2, proc2) == []  # the one you chose is busy


def test_kurootos_own_processes_never_make_a_camera_busy(tmp_path):
    from kurooto.modules.face import camera as cam

    _, proc = _cams(tmp_path, {"video0": [999003]}, loopback=())
    assert cam.holders("/dev/video0", proc, me=999003) == []


def test_a_new_camera_setting_takes_effect_without_a_restart(app):
    from kurooto.modules.face.camera import Camera

    face = app.modules["face"]

    class W:
        problem = ("camera in use by another program", 1e18)
        released = False

        def release(self):
            self.released = True

    w = W()
    w.camera = Camera("Kurooto body cam", 640, 480, platform="linux")
    face.watcher = w
    app.settings.set("face.camera.device", "Kurooto body cam")
    assert not face._camera_changed()
    app.settings.set("face.camera.device", "Integrated Camera")
    assert face._camera_changed()
    face.watcher = None
