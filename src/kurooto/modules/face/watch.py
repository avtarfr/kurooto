"""The watcher: when the camera is open, what it decides from each frame, and when you've arrived or left. Pure logic:
the clock, the idle probe, the camera, the models, the template and the pause reasons are all passed in, so every rule
is tested with fakes.

States: off, paused (why), resting (camera closed: you're here by keyboard and mouse), watching (camera open), away.

The camera is open only when the feature is on, you're enrolled, nothing in the pause list applies (Face.pause_reason),
and one of: no keyboard or mouse for face.watch.idle_s; the screen just unlocked or the computer just woke (10 s); an
arrival is being confirmed. While you type, input is the presence signal and the camera stays closed (on Linux one
program can stream from a camera at a time, so a video call you start gets it). Once input is active again, recognition
gets up to 6 s to confirm you, then the camera closes, confirmed or not.

Rate: face.watch.fps (fps_battery on battery); 2 a second for up to 5 s after the first frame it recognises you in;
halved (down to 0.2) when one frame takes more than 150 ms on a slow machine.

Arrival: 3 (face.recognise.frames) of the last 4 frames are you, within 6 s, after at least face.greet.after_absent_min
with no sign of you (no face of yours, no input while unlocked; a locked screen isn't presence), and the frames aren't
a still picture (every pair alike to 0.995 with landmarks moved under half a pixel: it waits for movement). Unsure and
stranger frames count for nothing and reset nothing.

Away (face.away.on): no sign of you for away.after_min while unlocked and watching, or locked that long. "left" once;
it ends with an arrival or with input ("back": somebody is using the computer, though it never greets for that).

Strangers: their numbers are dropped with the frame; only counts since start are kept (you, unsure, not you).
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kurooto.core.biometric import dot
from kurooto.modules.face.enrol import BLOWN, BLUR_MIN, BRIGHT, COVERED, COVERED_FRAMES, DARK
from kurooto.modules.face.vision import SCORE_OTHER, SCORE_WATCH, moved

WAKE_S = 10  # after an unlock or a wake the camera may look this long
INPUT_GRACE_S = 6  # input active again: recognition gets this long before the camera closes
CONFIRM_S = 5  # after the first frame of you: 2 frames a second for this long
CONFIRM_FPS = 2.0
WINDOW_S = 6  # the frames of an arrival fall within this
RETURN_S = 30  # a return (presence after an absence) waits this long for your face, then it was someone else
SLOW_MS = 0.150
MIN_FPS = 0.2
BUSY_RECHECK_S = 60
COVERED_RECHECK_S = 300
BLOCKED_RECHECK_S = 300
JUMP_S = 30  # the clock moved this far between two ticks: the computer slept
STILL_COS, STILL_PX = 0.995, 0.5
LEARN_INPUT_S = 60  # learning needs input within this after the arrival (someone who sits down and types)


@dataclass
class Seen:
    t: float
    owner: bool
    e: list[float] | None = None  # only an owner frame's numbers, kept for the still-picture check and learning
    face: Any = None
    others: bool = False


@dataclass
class Counts:
    you: int = 0
    unsure: int = 0
    not_you: int = 0


@dataclass
class Watcher:
    camera: Any
    detector: Any
    embedder: Any
    frames: Any
    classify: Callable[[list[float]], tuple[str, float]]
    paused: Callable[[], str]  # the first pause reason that applies, or ""
    cfg: Callable[[], dict]  # the settings now (fps, fps_battery, idle_s, ...)
    idle: Callable[[], float | None]  # seconds since the last input, or None (this computer can't say)
    locked: Callable[[], bool]
    on_battery: Callable[[], bool] = lambda: False
    emit: Callable[..., None] = lambda kind, **f: None
    learnable: Callable[[list[float]], bool] = lambda e: False
    clock: Callable[[], float] = time.monotonic
    counts: Counts = field(default_factory=Counts)

    def __post_init__(self):
        now = self.clock()
        self.state = "off"
        self.why = ""
        self.camera_open = False
        self.present_at = now  # starting is presence enough: no greeting right after Kurooto starts
        self.last_seen_owner: float | None = None
        self.last_input: float | None = None
        self.returning: dict | None = None  # {"since", "gap"}: presence after an absence, waiting for your face
        self.recent: deque[Seen] = deque(maxlen=4)
        self.confirm_until = 0.0
        self.wake_until = 0.0
        self.input_since: float | None = None
        self.last_frame_at = -1e9
        self.slow = 1.0
        self.away = False
        self.left_at: float | None = None
        self.locked_since: float | None = None
        self._was_locked = False
        self._last_tick = now
        self.problem: tuple[str, float] | None = None  # (pause reason, until): busy, no camera, blocked, covered
        self._dark = 0
        self.others = False
        self.arrived_at: float | None = None
        self.candidate: tuple[list[float], float] | None = None  # a frame to learn from, if input follows

    # --------------------------------------------------------------------------------------------- reading
    def problem_now(self) -> str:
        if self.problem and self.clock() < self.problem[1]:
            return self.problem[0]
        self.problem = None
        return ""

    def rate(self) -> float:
        c = self.cfg()
        fps = float(c.get("fps_battery" if self.on_battery() else "fps") or 1.0)
        fps = max(MIN_FPS, min(2.0, fps)) / self.slow
        if self.clock() < self.confirm_until:
            fps = max(fps, CONFIRM_FPS)
        return max(MIN_FPS, fps)

    # ------------------------------------------------------------------------------------------- one tick
    def tick(self) -> None:
        now = self.clock()
        if now - self._last_tick > JUMP_S:  # the computer slept: look when it wakes
            self.wake_until = now + WAKE_S
        self._last_tick = now
        c = self.cfg()
        locked = bool(self.locked())
        if locked and not self._was_locked:
            self.locked_since = now
        if not locked and self._was_locked:
            self.locked_since = None
            self.wake_until = now + WAKE_S
        self._was_locked = locked
        idle = None if locked else self.idle()
        idle_s = float(c.get("idle_s") or 60)
        active = idle is not None and idle < idle_s
        if idle is not None and idle < 2:
            self._input(now - idle, c)
        if active:
            if self.input_since is None:
                self.input_since = now
        else:
            self.input_since = None
        self._check_away(now, locked, c)
        why = self.paused()
        if why:
            self._close(why)
            self._set("paused", why)
            return
        problem = self.problem_now()
        if problem:
            self._close(problem)
            self._set("paused", problem)
            return
        woke = now < self.wake_until
        confirming = (self.returning is not None and now - self.returning["since"] < WAKE_S) or now < self.confirm_until
        grace = self.input_since is None or now - self.input_since < INPUT_GRACE_S
        want = (idle is not None and idle >= idle_s) or ((woke or confirming or self.camera_open) and grace)
        if not want:
            self._close("resting")
            self._set("away" if self.away else "resting", "")
            return
        if not self.camera_open and not self._open():
            return
        self._set("away" if self.away else "watching", "")
        if now - self.last_frame_at >= 1.0 / self.rate():
            self.last_frame_at = now
            self._frame(now, c)

    def _set(self, state: str, why: str) -> None:
        self.state, self.why = state, why

    def _open(self) -> bool:
        from kurooto.modules.face.camera import CameraError

        try:
            if self.camera.busy():
                raise CameraError("busy")
            self.camera.open()
        except CameraError as e:
            what = {
                "busy": ("camera in use by another program", BUSY_RECHECK_S),
                "no camera": ("no camera", BUSY_RECHECK_S),
                "blocked": ("camera blocked by the system", BLOCKED_RECHECK_S),
            }.get(e.why, ("no camera", BUSY_RECHECK_S))
            self.problem = (what[0], self.clock() + what[1])
            self._set("paused", what[0])
            return False
        except Exception as e:
            self.problem = ("no camera", self.clock() + BUSY_RECHECK_S)
            self._set("paused", "no camera")
            self.emit("failed", part="camera", error=f"{type(e).__name__}"[:100])
            return False
        self.camera_open = True
        self._dark = 0
        self.emit("watch", on=True, why="")
        return True

    def _close(self, why: str) -> None:
        if self.camera_open:
            self.camera_open = False
            try:
                self.camera.close()
            finally:
                self.emit("watch", on=False, why=why)
                if self.others:
                    self.others = False
                    self.emit("others", on=False)

    def release(self) -> None:
        """Close the camera now (an enrolment starting, the feature going off, a stop)."""
        self._close("stopped")

    # ------------------------------------------------------------------------------------------- presence
    def _input(self, at: float, c: dict) -> None:
        """Keyboard or mouse input (while unlocked) at `at`."""
        before = self.present_at
        self.last_input = max(self.last_input or at, at)
        self._presence(at, before, c)
        if self.away:
            self.away = False
            self.left_at = None
            self.emit("back")
        if self.candidate and self.arrived_at is not None and at - self.arrived_at <= LEARN_INPUT_S:
            e, _t = self.candidate
            self.candidate = None
            self.emit("learn", e=e)

    def _presence(self, at: float, before: float, c: dict) -> None:
        gap = at - before
        if gap >= float(c.get("after_absent_min") or 20) * 60 and self.returning is None:
            self.returning = {"since": at, "gap": gap}
        self.present_at = max(self.present_at, at)

    def _check_away(self, now: float, locked: bool, c: dict) -> None:
        if self.returning is not None and now - self.returning["since"] > RETURN_S:
            self.returning = None  # presence came back without your face: someone else, or bad light
            self.candidate = None
        if self.candidate is not None and self.arrived_at is not None and now - self.arrived_at > LEARN_INPUT_S:
            self.candidate = None
        if not c.get("away_on") or self.away:
            return
        after = float(c.get("away_after_min") or 5) * 60
        gone = (not locked and self.camera_open and now - self.present_at >= after) or (
            locked and self.locked_since is not None and now - self.locked_since >= after
        )
        if gone:
            self.away = True
            self.left_at = now
            self.emit("left")

    # ---------------------------------------------------------------------------------------------- a frame
    def _frame(self, now: float, c: dict) -> None:
        frame = self.camera.read()
        if frame is None:
            if not self.camera.is_open():  # a read error closed it (a stale handle after a sleep): reopened later
                self.camera_open = False
                self.emit("watch", on=False, why="camera stopped")
            return
        t0 = self.clock()
        try:
            self._look(frame, now, c)
        finally:
            del frame
        took = self.clock() - t0
        if took > SLOW_MS and self.slow < 8:
            self.slow *= 2
            self.emit("slow", factor=self.slow)

    def _look(self, frame, now: float, c: dict) -> None:
        if self.frames.mean(frame) < COVERED:
            self._dark += 1
            if self._dark >= COVERED_FRAMES:
                self.problem = ("camera covered", self.clock() + COVERED_RECHECK_S)
                self._close("camera covered")
            return
        self._dark = 0
        min_px = float(c.get("min_face_px") or 60)
        faces = self.detector.detect(frame, SCORE_OTHER)
        best: tuple[float, list[float], Any, dict] | None = None
        n_other = 0
        for f in faces:
            if f.score < SCORE_WATCH or f.height < min_px:
                n_other += 1 if f.score >= SCORE_OTHER else 0
                continue
            crop = self.embedder.align(frame, f)
            st = self.embedder.stats(crop)
            if st.blur < BLUR_MIN / 2 or not (30 <= st.mean <= 225):
                del crop
                n_other += 1
                continue  # too poor to judge: counts for nothing
            e = self.embedder.feature(crop)
            del crop
            klass, s = self.classify(e)
            if klass == "owner":
                self.counts.you += 1
                good = st.blur >= BLUR_MIN and DARK <= st.mean <= BRIGHT and st.bright <= BLOWN
                if best is None or s > best[0]:
                    if best is not None:
                        n_other += 1
                    best = (s, e, f, {"good": good})
                else:
                    n_other += 1
            else:
                if klass == "unsure":
                    self.counts.unsure += 1
                else:
                    self.counts.not_you += 1
                n_other += 1
            del e  # a stranger's or an unsure face's numbers go with the frame
        others = sum(1 for f in faces if f.score >= SCORE_OTHER) >= 2
        if others != self.others:
            self.others = others
            self.emit("others", on=others)
        if best is None:
            self.recent.append(Seen(now, False))
            return
        _s, e, f, q = best
        self.recent.append(Seen(now, True, e, f, n_other > 0))
        first = self.last_seen_owner is None or now - self.last_seen_owner > WINDOW_S
        before = self.present_at
        self.last_seen_owner = now
        if first:
            self.confirm_until = now + CONFIRM_S
        self._presence(now, before, c)
        if q["good"] and n_other == 0 and self.returning is not None and self.learnable(e):
            self.candidate = (e, now)
        self._arrival(now, c)

    def _arrival(self, now: float, c: dict) -> None:
        if self.returning is None:
            return
        need = int(c.get("frames") or 3)
        win = [x for x in self.recent if now - x.t <= WINDOW_S]
        mine = [x for x in win if x.owner]
        if len(mine) < need:
            return
        if self.still(mine):
            return  # a picture propped up in front of the camera: wait for movement
        gap = self.returning["gap"]
        self.returning = None
        self.arrived_at = now
        if self.away:
            self.away = False
            self.left_at = None
        self.emit("arrived", away_min=round(gap / 60), others=any(x.others for x in win))

    @staticmethod
    def still(mine: list[Seen]) -> bool:
        if len(mine) < 2:
            return False
        for i in range(len(mine)):
            for j in range(i + 1, len(mine)):
                a, b = mine[i], mine[j]
                if a.e is None or b.e is None:
                    return False
                if not (dot(a.e, b.e) > STILL_COS and moved(a.face, b.face) < STILL_PX):
                    return False
        return True


# the pause reasons, in order: the first that applies is the one shown (on the card and in /face)
PAUSES = (
    "feature off",
    "not enrolled",
    "not set up yet",
    "paused by you",
    "Kurooto is paused",
    "on battery (pause mode)",
    "screen locked",
    "you're on a call",
    "focus",
    "night hours",
    "enrolling",
    "camera in use by another program",
    "no camera",
    "camera blocked by the system",
    "camera covered",
    "template locked",
)
