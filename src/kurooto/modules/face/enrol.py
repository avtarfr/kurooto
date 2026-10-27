"""Enrolment: the guided capture on the dashboard's Face page, and the live test. Only you start one (Start or Test on
the page, the guarded action camera.open); the camera opens for it and closes when it ends.

The plan (PLAN): nine steps, 52 samples. Front to down (26 samples) are needed before Finish and train; near, far,
glasses and light raise the grade and can be skipped (Add samples resumes at the steps that are short). Every frame is
checked (judge(): the first failing check is the reason shown); accepted samples are at least half a second apart.

    check       rejected when                                                    reason shown
    camera      no frame for 2 s                                                 The camera stopped sending pictures.
    covered     the frame's mean light < 8 for 10 frames                         The camera sees nothing: ...
    no face     no face found with a score >= 0.9                                No face found: look at the camera.
    two faces   more than one face with a score >= 0.6                           Two faces: only you should be ...
    too far     the face is shorter than face.recognise.min_face_px              Too far: come a little closer.
    too close   taller than 0.7 of the frame                                     Too close: move back a little.
    out of view touching the frame's edge (near step: eyes, nose, mouth only)       Partly out of view at the bottom.
    tilted      the eyes' line more than 25 degrees off level                    Keep your head level.
    step pose   the step's own rule                                              the step's nudge
    blur        variance of the Laplacian on the aligned crop < BLUR_MIN         Blurry: hold still for a moment.
    dark        the crop's mean < 50 (< 30 in the light step)                    Too dark: more light on your face.
    bright      mean > 210, or more than 8 % of it blown out                     Too bright: ...
    repeat      the same as the step's last sample (cosine > 0.97, moved < 3 px)  Move a little: ...
    not you     5 samples or more, and this one unlike them (cosine < 0.25)      That doesn't look like the earlier ...

Samples live in memory only, in the Session, until training seals them into the template; Discard, a stop, turning
the feature off, or 30 minutes without training drops them. Preview frames are JPEGs made in memory for the page
(GET /api/face/frame), never written anywhere. What's pushed to the page is rounded numbers, never an embedding.
"""

from __future__ import annotations

import secrets
import statistics
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kurooto.core.biometric import dot, mean_unit
from kurooto.modules.face.model import Sample
from kurooto.modules.face.vision import SCORE_ENROL, SCORE_OTHER, Face, Pose, Stats, moved, pose

# quality limits (§4.3); BLUR_MIN is a first guess, to be tuned on the first real run
BLUR_MIN = 60.0
DARK, DARK_LIGHT, BRIGHT, BLOWN = 50.0, 30.0, 210.0, 0.08
COVERED, COVERED_FRAMES = 8.0, 10
TILT_MAX = 25.0
SPACING_S = 0.5  # at most 2 accepted a second
REPEAT_COS, REPEAT_PX = 0.97, 3.0
NOT_YOU_COS, NOT_YOU_AFTER = 0.25, 5
LIGHT_DIFF = 25.0
# the session (§4.5)
CAPTURE_FPS = 5.0
PAGE_GONE_S = 15  # no preview fetched this long: the page closed or the tab hid, the camera closes
CAPTURE_MAX_S = 600  # ten minutes of capturing in all
KEEP_S = 1800  # samples not trained within 30 minutes are dropped
TEST_S = 60
MARK_S = 10  # "I'm testing as me" / "Someone else" each look this long
NO_FRAME_S = 2.0

R_CAMERA = "The camera stopped sending pictures."
R_COVERED = "The camera sees nothing: is it covered, or the lid closed?"
R_NO_FACE = "No face found: look at the camera."
R_TWO = "Two faces: only you should be in view while enrolling."
R_FAR = "Too far: come a little closer."
R_CLOSE = "Too close: move back a little."
R_EDGE = "Partly out of view at the {side}: {fix}"
EDGE_FIX = {
    "top": "move down a little, or tilt the screen back.",
    "bottom": "move up a little, or tilt the screen forward.",
    "left": "move to your right a little.",
    "right": "move to your left a little.",
}
NEAR_RATIO = 1.25  # the near step: this much taller than the front steps' face, or as near as the frame allows
R_TILT = "Keep your head level."
R_BLUR = "Blurry: hold still for a moment."
R_DARK = "Too dark: more light on your face."
R_BRIGHT = "Too bright: is a light shining at the camera or behind you?"
R_REPEAT = "Move a little: that's the same as the last one."
R_NOT_YOU = "That doesn't look like the earlier samples. Is someone else in view?"
R_LIGHT = "Change the light a little more: a lamp, the room light, the window."


@dataclass(frozen=True)
class Step:
    key: str
    prompt: str
    target: int
    skippable: bool


PLAN = (
    Step("front", "Look straight at the camera, at your usual distance.", 8, False),
    Step("left", "Turn your head a little to your left.", 5, False),
    Step("right", "Now a little to your right.", 5, False),
    Step("up", "Tilt your chin up a little.", 4, False),
    Step("down", "And down a little.", 4, False),
    Step("near", "Lean in closer.", 5, True),
    Step("far", "Sit back.", 5, True),
    Step("glasses", "If you wear glasses, put them on (or take them off) now.", 8, True),
    Step(
        "light",
        "Change the light: room light off, a desk lamp, or the window behind you. You can do this later with Add "
        "samples.",
        8,
        True,
    ),
)
STEPS = {s.key: s for s in PLAN}
NEEDED = ("front", "left", "right", "up", "down")
TARGET = sum(s.target for s in PLAN)  # 52
MINIMUM = sum(STEPS[k].target for k in NEEDED)  # 26
TARGETS = {s.key: s.target for s in PLAN}


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    step: str = ""
    face: Face | None = None
    pose: Pose | None = None
    stats: Stats | None = None
    sample: Sample | None = None
    quiet: bool = False  # a frame skipped for spacing: nothing new to show


def edge(face: Face, w: int, h: int, near: bool = False) -> str:
    """The side of the frame the face touches ("" when it's in view). Near the camera (the near step) only the eyes,
    nose and mouth must stay clear of the edge: leaning in on a laptop's camera, the forehead or chin leaves the frame
    long before they do (the box touched the bottom edge while the step still asked to come closer)."""
    x, y, bw, bh = face.box
    if near and face.landmarks:
        m = 0.08 * bh
        xs, ys = [q[0] for q in face.landmarks], [q[1] for q in face.landmarks]
        lo_x, hi_x, lo_y, hi_y = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
    else:
        lo_x, hi_x, lo_y, hi_y = x - 1, x + bw + 1, y - 1, y + bh + 1
    # named as on the page's mirrored picture (your own right and left): the camera's left edge is on your right
    for side, out in (("top", lo_y <= 0), ("bottom", hi_y >= h), ("right", lo_x <= 0), ("left", hi_x >= w)):
        if out:
            return side
    return ""


def near_target(base: float, frame_h: float) -> float:
    """The near step's face height: NEAR_RATIO times the front steps', but never more than 60 % of the way to the
    too-close limit, so it can always be reached in the frame (sitting close already, 1.35 times could not)."""
    return min(NEAR_RATIO * base, base + 0.6 * (0.7 * frame_h - base))


class Enrolment:
    """The plan's bookkeeping and the checks: pure, so every rule is tested with made-up faces and numbers."""

    def __init__(
        self,
        min_face_px: int = 60,
        have: dict[str, int] | None = None,
        baseline: dict | None = None,
        prior: list[list[float]] | None = None,
        mirror: bool = True,
    ):
        self.min_face_px = int(min_face_px)
        self.have = dict(have or {})  # Add samples: what the template already holds per step
        self.baseline = dict(baseline or {})  # the front step's medians: pitch, height, light
        self.prior = list(prior or [])  # Add samples: the template's centroids, for the "not you" check
        self.mirror = mirror
        self.samples: list[Sample] = []
        self.skipped: set[str] = set()
        self.at = 0
        self._dark = 0
        self._last_ok = -1e9
        self._last: dict[str, tuple[list[float], Face]] = {}
        self._front: dict[str, list[float]] = {"pitch": [], "height": [], "light": []}
        self._advance()

    # ------------------------------------------------------------------------------------------ progress
    def got(self, key: str) -> int:
        return self.have.get(key, 0) + sum(1 for s in self.samples if s.step == key)

    def done(self, key: str) -> bool:
        return key in self.skipped or self.got(key) >= STEPS[key].target

    def _advance(self) -> None:
        while self.at < len(PLAN) and self.done(PLAN[self.at].key):
            self.at += 1

    def current(self) -> Step | None:
        return PLAN[self.at] if self.at < len(PLAN) else None

    def ready(self) -> bool:
        """Finish and train: steps front to down are complete."""
        return all(self.got(k) >= STEPS[k].target for k in NEEDED)

    def total(self) -> int:
        return sum(min(self.got(s.key), s.target) for s in PLAN)

    def progress(self) -> dict:
        cur = self.current()
        return {
            "steps": [
                {
                    "key": s.key,
                    "prompt": s.prompt,
                    "got": min(self.got(s.key), s.target),
                    "need": s.target,
                    "done": self.got(s.key) >= s.target,
                    "skipped": s.key in self.skipped,
                    "skippable": s.skippable,
                }
                for s in PLAN
            ],
            "step": cur.key if cur else "",
            "step_no": (self.at + 1) if cur else len(PLAN),
            "steps_n": len(PLAN),
            "total": self.total(),
            "target": TARGET,
            "minimum": MINIMUM,
            "ready": self.ready(),
            "new": len(self.samples),
        }

    def act(self, action: str) -> str:
        """skip (a skippable step), back (the previous step), no_glasses (skips the glasses step)."""
        cur = self.current()
        if action == "no_glasses":
            self.skipped.add("glasses")
            self._advance()
            return "Glasses skipped."
        if action == "skip":
            if cur is None or not cur.skippable:
                return "This step can't be skipped."
            self.skipped.add(cur.key)
            self._advance()
            return f"Skipped {cur.key}."
        if action == "back":
            if self.at == 0:
                return "This is the first step."
            self.at -= 1
            self.skipped.discard(PLAN[self.at].key)
            return f"Back to {PLAN[self.at].key}."
        return "There's no such action."

    # --------------------------------------------------------------------------------------------- judging
    def _step_rule(self, key: str, p: Pose, face: Face, frame_h: float = 480.0) -> str:
        b = self.baseline
        if key == "front":
            return "" if abs(p.yaw) < 0.12 and abs(p.roll) < 12 else "Look straight at the camera."
        if key == "left":
            if p.yaw > -0.15:
                return "Turn a bit more to your left."
            return "" if p.yaw >= -0.45 else "Not so far: turn back a little."
        if key == "right":
            if p.yaw < 0.15:
                return "Turn a bit more to your right."
            return "" if p.yaw <= 0.45 else "Not so far: turn back a little."
        if key in ("up", "down"):
            base = b.get("pitch")
            if base is None:
                return "Look straight at the camera first."
            if key == "up":
                return "" if p.pitch < base - 0.06 else "Tilt your chin up a little more."
            return "" if p.pitch > base + 0.06 else "Tilt your chin down a little more."
        if key == "near":
            hb = b.get("height")
            if not hb:
                return "Look straight at the camera first."
            want = near_target(hb, frame_h)
            if face.height >= want:
                return ""
            way = max(0, min(99, round(100 * (face.height - hb) / max(1.0, want - hb))))
            return f"Lean in a little closer ({way}% of the way)."
        if key == "far":
            hb = b.get("height")
            if face.height < self.min_face_px + 20:
                return R_FAR
            return "" if hb and face.height <= 0.75 * hb else "Sit back a little more."
        if key == "glasses":
            return "" if abs(p.yaw) < 0.2 else "Look towards the camera."
        return ""

    def judge(
        self,
        faces: list[Face],
        size: tuple[int, int],
        frame_mean: float,
        measure: Callable[[Face], Stats],
        embed: Callable[[Face], list[float]],
        now: float,
    ) -> Verdict:
        cur = self.current()
        key = cur.key if cur else ""
        w, h = size
        self._dark = self._dark + 1 if frame_mean < COVERED else 0
        if self._dark >= COVERED_FRAMES:
            return Verdict(False, R_COVERED, key)
        if cur is None:
            return Verdict(False, "All steps are done: Finish and train.", key, quiet=True)
        sure = [f for f in faces if f.score >= SCORE_ENROL]
        if not sure:
            return Verdict(False, R_NO_FACE, key)
        if sum(1 for f in faces if f.score >= SCORE_OTHER) > 1:
            return Verdict(False, R_TWO, key)
        f = sure[0]
        if f.height < self.min_face_px:
            return Verdict(False, R_FAR, key, f)
        if f.height > 0.7 * h:
            return Verdict(False, R_CLOSE, key, f)
        side = edge(f, w, h, near=key == "near")
        if side:
            # the camera's own picture (not mirrored) shows your right on its left
            shown = side if self.mirror else {"right": "left", "left": "right"}.get(side, side)
            return Verdict(False, R_EDGE.format(side=shown, fix=EDGE_FIX[side]), key, f)
        p = pose(f, self.mirror)
        if abs(p.roll) > TILT_MAX:
            return Verdict(False, R_TILT, key, f, p)
        nudge = self._step_rule(key, p, f, h)
        if nudge:
            return Verdict(False, nudge, key, f, p)
        st = measure(f)
        if st.blur < BLUR_MIN:
            return Verdict(False, R_BLUR, key, f, p, st)
        if st.mean < (DARK_LIGHT if key == "light" else DARK):
            return Verdict(False, R_DARK, key, f, p, st)
        if st.mean > BRIGHT or st.bright > BLOWN:
            return Verdict(False, R_BRIGHT, key, f, p, st)
        if key == "light":
            lb = self.baseline.get("light")
            if lb is not None and abs(st.mean - lb) < LIGHT_DIFF:
                return Verdict(False, R_LIGHT, key, f, p, st)
        if now - self._last_ok < SPACING_S:
            return Verdict(False, "", key, f, p, st, quiet=True)
        e = embed(f)
        last = self._last.get(key)
        if last is not None and dot(e, last[0]) > REPEAT_COS and moved(last[1], f) < REPEAT_PX:
            return Verdict(False, R_REPEAT, key, f, p, st)
        known = [s.e for s in self.samples] + self.prior
        if len(self.samples) + sum(self.have.values()) >= NOT_YOU_AFTER and known:
            if dot(e, mean_unit(known)) < NOT_YOU_COS:
                return Verdict(False, R_NOT_YOU, key, f, p, st)
        s = Sample(e, key, now, {"blur": round(st.blur), "light": round(st.mean)})
        self.samples.append(s)
        self._last[key] = (e, f)
        self._last_ok = now
        if key == "front":
            self._front["pitch"].append(p.pitch)
            self._front["height"].append(f.height)
            self._front["light"].append(st.mean)
            self.baseline.update({k: round(statistics.median(v), 4) for k, v in self._front.items() if v})
        self._advance()
        return Verdict(True, "", key, f, p, st, s)


def shape(v: Verdict, size: tuple[int, int]) -> dict:
    """What the page draws for one frame: a box and five points as shares of the frame, rounded quality numbers."""
    w, h = size
    out: dict[str, Any] = {"ok": v.ok, "reason": v.reason, "step": v.step}
    if v.face is not None:
        x, y, bw, bh = v.face.box
        out["box"] = [round(x / w, 3), round(y / h, 3), round(bw / w, 3), round(bh / h, 3)]
        out["landmarks"] = [[round(px / w, 3), round(py / h, 3)] for px, py in v.face.landmarks]
    q: dict[str, float] = {}
    if v.stats is not None:
        q.update(blur=round(v.stats.blur), light=round(v.stats.mean))
    if v.pose is not None:
        q.update(yaw=round(v.pose.yaw, 2), pitch=round(v.pose.pitch, 2), roll=round(v.pose.roll))
    out["quality"] = q
    return out


# --------------------------------------------------------------------------------------------- the session
@dataclass
class Vision:
    detector: Any
    embedder: Any
    frames: Any


@dataclass
class Session:
    """One enrolment or test: the camera, the preview, and (enrolment) the samples in memory.

    kind "enrol": every frame goes through Enrolment.judge. kind "test": every face is scored against the template
    (classify) and the decision shown; mark("me" | "other") looks for MARK_S seconds and keeps only the result."""

    kind: str
    cid: int | None
    camera: Any
    vision: Vision
    push: Callable[[dict], None]
    plan: Enrolment | None = None
    classify: Callable[[list[float]], tuple[str, float]] | None = None
    thresholds: tuple[float, float] = (0.0, 0.0)
    clock: Callable[[], float] = time.monotonic
    on_mark: Callable[[str, dict], None] | None = None
    id: str = field(default_factory=lambda: secrets.token_urlsafe(12))
    state: str = "capturing"  # capturing, paused (why), ended
    why: str = ""

    def __post_init__(self):
        now = self.clock()
        self.started = now
        self.last_fetch = now
        self.captured_s = 0.0
        self._tick_at = now
        self._last_frame_at = now
        self._jpeg: bytes | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.recent: deque[bool] = deque(maxlen=4)  # test: owner or not, the last four frames
        self.marking: dict | None = None
        self.camera_open = False

    # ------------------------------------------------------------------------------------------- the camera
    def open_camera(self) -> None:
        self.camera.open()
        self.camera_open = True
        self._last_frame_at = self.clock()

    def close_camera(self) -> None:
        """Closed by the session's own thread when it runs (never from under a read), else here and now."""
        with self._lock:
            self._jpeg = None
        t = self._thread
        if t is not None and t.is_alive() and threading.current_thread() is not t:
            return  # the loop sees the state and closes it within a frame
        if self.camera_open:
            self.camera_open = False
            self.camera.close()

    def jpeg(self) -> bytes | None:
        """The latest preview frame (the page's GET /api/face/frame): fetching it keeps the session alive."""
        self.last_fetch = self.clock()
        with self._lock:
            return self._jpeg

    # -------------------------------------------------------------------------------------------- one frame
    def step(self) -> dict | None:
        """Read one frame and judge it; returns what was pushed to the page (or None)."""
        now = self.clock()
        if self.state == "capturing":
            self.captured_s += max(0.0, now - self._tick_at)
        self._tick_at = now
        if self.state == "ended":
            if self.camera_open:
                self.close_camera()
            return None
        if now - self.started > (KEEP_S if self.kind == "enrol" else TEST_S):
            self.end("time up")
            return None
        if self.state != "capturing":
            if self.camera_open:
                self.close_camera()
            return None
        if now - self.last_fetch > PAGE_GONE_S:
            self.pause("page gone")
            return None
        if self.kind == "enrol" and self.captured_s > CAPTURE_MAX_S:
            self.pause("ten minutes of capturing")
            return None
        frame = self.camera.read() if self.camera_open else None
        if frame is None:
            if now - self._last_frame_at > NO_FRAME_S:
                return self._push({"ok": False, "reason": R_CAMERA, "step": self._step_key()})
            return None
        self._last_frame_at = now
        try:
            v = self.vision
            size = v.frames.size(frame)
            jpg = v.frames.jpeg(frame)
            with self._lock:
                self._jpeg = jpg
            faces = v.detector.detect(frame, SCORE_OTHER)
            if self.kind == "enrol":
                out = self._enrol(frame, faces, size, now)
            else:
                out = self._test(frame, faces, size, now)
        finally:
            del frame
        return out

    def _step_key(self) -> str:
        cur = self.plan.current() if self.plan else None
        return cur.key if cur else ""

    def _enrol(self, frame, faces, size, now) -> dict | None:
        v = self.vision
        crops: dict[int, Any] = {}

        def measure(f: Face) -> Stats:
            crops[id(f)] = v.embedder.align(frame, f)
            return v.embedder.stats(crops[id(f)])

        def embed(f: Face) -> list[float]:
            c = crops.get(id(f))
            if c is None:
                c = v.embedder.align(frame, f)
            return v.embedder.feature(c)

        assert self.plan is not None
        verdict = self.plan.judge(faces, size, v.frames.mean(frame), measure, embed, now)
        crops.clear()
        if verdict.quiet and not verdict.reason:
            return None
        return self._push(shape(verdict, size))

    def _test(self, frame, faces, size, now) -> dict:
        v = self.vision
        w, h = size
        rows, owner = [], False
        for f in faces:
            if f.score < SCORE_ENROL:
                continue
            crop = v.embedder.align(frame, f)
            e = v.embedder.feature(crop)
            del crop
            klass, s = self.classify(e) if self.classify else ("stranger", 0.0)
            del e  # someone else's numbers are never kept: only the score, for this frame
            owner = owner or klass == "owner"
            x, y, bw, bh = f.box
            rows.append(
                {"box": [round(x / w, 3), round(y / h, 3), round(bw / w, 3), round(bh / h, 3)], "score": round(s, 3),
                 "class": {"owner": "you", "unsure": "unsure", "stranger": "not you"}[klass]}
            )  # fmt: skip
        self.recent.append(owner)
        decision = "no face" if not rows else max(rows, key=lambda r: r["score"])["class"]
        frames_ok = f"{sum(self.recent)} of {len(self.recent)}"
        m = self.marking
        if m is not None:
            m["frames"] += 1
            m["recognised"] += 1 if owner else 0
            if rows:
                m["best"] = max(m["best"], max(r["score"] for r in rows))
            m["window"].append(owner)
            if sum(m["window"]) >= 3:
                m["decided"] = True
            if now - m["at"] >= MARK_S:
                self._mark_done()
        hi, lo = self.thresholds
        return self._push(
            {"faces": rows, "decision": decision, "frames_ok": frames_ok, "t_hi": round(hi, 3), "t_lo": round(lo, 3),
             "marking": (self.marking or {}).get("who", "")}
        )  # fmt: skip

    def mark(self, who: str) -> str:
        if self.kind != "test" or who not in ("me", "other"):
            return "That's for the test."
        self.marking = {
            "who": who, "at": self.clock(), "frames": 0, "recognised": 0, "best": 0.0, "decided": False,
            "window": deque(maxlen=4),
        }  # fmt: skip
        return "Looking for ten seconds."

    def _mark_done(self) -> None:
        m, self.marking = self.marking, None
        if m is None:
            return
        if m["who"] == "me":
            res = {"frames": m["frames"], "recognised": m["recognised"], "decided": m["decided"]}
        else:
            res = {"frames": m["frames"], "best": round(m["best"], 3), "any_accepted": m["recognised"] > 0}
        self._push({"kind": "test_result", "who": m["who"], **res})
        if self.on_mark:
            self.on_mark(m["who"], res)

    def _push(self, fields: dict) -> dict:
        msg = {"t": "face", "kind": self.kind if "kind" not in fields else fields.pop("kind"), "session": self.id}
        msg.update(fields)
        if self.plan is not None and msg["kind"] == "enrol":
            msg.update(self.plan.progress())
        try:
            self.push(msg)
        except Exception:
            pass
        return msg

    # ------------------------------------------------------------------------------------------ the session
    def pause(self, why: str) -> None:
        self.state, self.why = "paused", why
        self.close_camera()
        self._push({"kind": "session", "state": "paused", "why": why})

    def resume(self) -> None:
        if self.state != "paused":
            return
        self.open_camera()
        self.state, self.why = "capturing", ""
        self.last_fetch = self._tick_at = self.clock()
        self._push({"kind": "session", "state": "capturing", "why": ""})

    def end(self, why: str) -> None:
        """Closes the camera and drops what's in memory."""
        if self.state == "ended":
            return
        self.state, self.why = "ended", why
        self._stop.set()
        self.close_camera()
        if self.plan is not None:
            self.plan.samples.clear()
        self.marking = None
        self._push({"kind": "session", "state": "ended", "why": why})

    def start_thread(self, before: Callable[[], None] | None = None) -> None:
        def run():
            try:
                if before:
                    before()
                while not self._stop.is_set():
                    t0 = time.monotonic()
                    try:
                        self.step()
                    except Exception as e:
                        self._push({"kind": "session", "state": self.state, "why": f"error: {type(e).__name__}"})
                        self.pause("an error")
                    self._stop.wait(max(0.02, 1 / CAPTURE_FPS - (time.monotonic() - t0)))
            finally:
                self.close_camera()

        self._thread = threading.Thread(target=run, name=f"face-{self.kind}", daemon=True)
        self._thread.start()
