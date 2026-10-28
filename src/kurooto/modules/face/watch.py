"""The watcher: when the camera is open, what it decides from each frame, and when you've arrived or left. Pure logic:
the clock, the idle probe, the camera, the models, the template and the pause reasons are all passed in, so every rule
is tested with fakes.

States: off, paused (why), resting (camera closed: you're here by keyboard and mouse), watching (camera open), away.

The camera is open only when the feature is on, you're enrolled, nothing in the pause list applies (Face.pause_reason),
and one of: no keyboard or mouse for face.watch.idle_s; the screen just unlocked or the computer just woke (10 s); an
arrival is being confirmed. While you type, input is the presence signal and the camera stays closed (on Linux one
program can stream from a camera at a time, so a video call you start gets it). Once input is active again, recognition
gets up to 6 s to confirm you, then the camera closes, confirmed or not. When this computer can't say how long it's
been idle, only a wake, an unlock or a confirmation opens it, and it closes when that window ends. With
face.watch.when_locked on, a locked screen counts as idle.

Rate: face.watch.fps (fps_battery on battery); 2 a second for up to 5 s after the first frame it recognises you in;
halved (down to 0.2) when one frame takes more than 150 ms on a slow machine. (0.8.17) While Voice listens for a look
(cfg "look_fps", face.watch.look_fps), at least that many a second (at most LOOK_MAX_FPS, halved the same way).

Sizes (0.8.17): face.recognise.min_face_px and the still-picture check are pixels of a frame whose shorter side is 480
(vision.px_scale), so a camera switched from 480x640 to 1080x1440 judges the same faces; "view" carries the frame's
size (frame) so Face.close_facing compares shares of it.

Arrival: 3 (face.recognise.frames) of the last 4 frames are you, within 6 s, after at least face.greet.after_absent_min
with no sign of you (no face of yours, no input while unlocked; a locked screen isn't presence), and the frames aren't
a still picture (every pair alike to 0.995 with landmarks moved under half a pixel: it waits for movement). Unsure and
stranger frames count for nothing and reset nothing.

Away (face.away.on): no sign of you for away.after_min while unlocked and watching, or locked that long. "left" once;
it ends with an arrival or with input ("back": somebody is using the computer, though it never greets for that).

Strangers: their numbers are dropped with the frame; only counts since start are kept (you, unsure, not you).

Hooks for add-ons (0.8.12): `held()` true (an add-on asked the camera to keep looking: Face.hold_watch) opens it
whatever the input says, but only after every pause reason above has passed, so it never overrides a switch, the
night, a call, a lock or /face pause. `people()` true (an add-on watches who's in view: Face.watch_people): each frame
looked at also emits "people" with every face's box, place, yaw, identity, score and numbers, handed over in memory
on this thread and dropped with the frame here.

Tracking (0.8.12, face.track.on): while `tracking()` asks for it, every face in view gets a track id (nearest centre,
frame to frame) and a micro-movement number, emitted as "faces" (positions, the owner flag, m; never numbers that
describe a face). TRACK_FAST (a dashboard in sight, or an add-on holding the camera "to track") adds detection-only
frames between the recognition frames at face.track.fps: YuNet only, never SFace, so recognition keeps its own rate.
Tracking never opens the camera: it only looks faster while the rules above have it open.

Eyes (0.8.17, voice.listen.look_gaze): while `gaze()` hands a gazer (look to talk on, the eye model here, your eyes
calibrated), the owner's best face in each recognition frame gets its iris offsets read from the full frame
(gaze.py), handed with "view" as eyes=(h, v): two numbers, never the eyes' pictures, dropped with the frame.

Anyone's look (0.8.18, voice.listen.look_anyone; cfg "look_anyone"): the other faces big enough to judge, the
LOOK_OTHERS biggest, go with "view" as looks=[(height, yaw, pitch, eyes)], the same numbers as the owner's: where a
face looks, never who it is.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kurooto.core.biometric import dot
from kurooto.modules.face.enrol import BLOWN, BLUR_MIN, BRIGHT, COVERED, COVERED_FRAMES, DARK
from kurooto.modules.face.vision import SCORE_OTHER, SCORE_WATCH, moved, pose, px_scale

WAKE_S = 10  # after an unlock or a wake the camera may look this long
INPUT_GRACE_S = 6  # input active again: recognition gets this long before the camera closes
CONFIRM_S = 5  # after the first frame of you: 2 frames a second for this long
CONFIRM_FPS = 2.0
WINDOW_S = 6  # the frames of an arrival fall within this
RETURN_S = 30  # a return (presence after an absence) waits this long for your face, then it was someone else
SLOW_MS = 0.150
MIN_FPS = 0.2
LOOK_OTHERS = 3  # (0.8.18, look_anyone) at most this many other faces' looks are read per frame
LOOK_MAX_FPS = 5.0  # (0.8.17) face.watch.look_fps, while Voice listens for a look, never above this
BUSY_RECHECK_S = 60
COVERED_RECHECK_S = 300
BLOCKED_RECHECK_S = 300
JUMP_S = 30  # the clock moved this far between two ticks: the computer slept
STILL_COS, STILL_PX = 0.995, 0.5
LEARN_INPUT_S = 60  # learning needs input within this after the arrival (someone who sits down and types)
TRACK_OFF, TRACK_SLOW, TRACK_FAST = 0, 1, 2  # tracking(): no faces; faces at the recognition rate; at face.track.fps
TRACK_MAX_FPS = 15.0
TRACK_SLOW_S = 0.06  # a detection-only frame taking longer than this halves the tracking rate (down to 8 times)
TRACK_RECOVER = 30  # this many quick detection-only frames in a row undo one halving
TRACK_MATCH = 1.0  # the same face as last frame: its centre within this many face heights of the old one
TRACK_MISS = 3  # missing from this many frames in a row: gone, its id with it
MICRO_WINDOW_S = 0.4  # movement is measured against the face this long ago (jitter doesn't add up, motion does)
MICRO_JITTER = 0.03  # face heights: YuNet's own jitter between two frames of a still face, ignored (an estimate)
MICRO_FULL = 0.3  # face heights a second beyond the jitter that make m = 1 (a small nod: about 0.2-0.4)
MICRO_RISE = 0.6  # m rises this share of the way to a new reading at once (a spike shows in one frame)
MICRO_TAU = 0.5  # seconds: m fades with this time constant once the face is still
WAIT_MIN_S = 0.02  # the thread never waits less than this between looks: it can't spin


@dataclass
class Seen:
    t: float
    owner: bool
    e: list[float] | None = None  # only an owner frame's numbers, kept for the still-picture check and learning
    face: Any = None
    others: bool = False


@dataclass
class Track:
    """One face followed frame to frame: its place in pixels, its landmarks relative to its centre in face heights."""

    id: int
    cx: float
    cy: float
    h: float
    rel: tuple
    t: float
    m: float = 0.0
    owner: bool = False
    miss: int = 0
    past: deque = field(default_factory=lambda: deque(maxlen=12))  # (t, cx, cy, h, rel) of the last frames


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
    held: Callable[[], bool] = lambda: False  # an add-on keeps the camera looking (after every pause reason)
    people: Callable[[], bool] = lambda: False  # an add-on watches who's in view: "people" each frame
    tracking: Callable[[], int] = lambda: TRACK_OFF  # who wants every face's place (TRACK_*; face.track.on checked)
    gaze: Callable[[], Any] = lambda: None  # (0.8.17) a gaze.Gazer when the owner's eyes are wanted now, else None
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
        self.here_at = -1e9  # (0.9.0, core/here.py) your voice or the dashboard said you're here: away waits again
        self.locked_since: float | None = None
        self._was_locked = False
        self._last_tick = now
        self.problem: tuple[str, float] | None = None  # (pause reason, until): busy, no camera, blocked, covered
        self._dark = 0
        self.others = False
        self.arrived_at: float | None = None
        self.candidate: tuple[list[float], float] | None = None  # a frame to learn from, if input follows
        self.tracks: dict[int, Track] = {}  # positions only, in memory, dropped when the camera closes
        self._next_id = 1
        self._track = TRACK_OFF  # tracking() as of the last full tick (track_tick runs between them)
        self._track_fps = 0.0
        self.last_track_at = -1e9
        self.track_slow = 1.0
        self._quick = 0
        self._faces_shown = False  # the last "faces" had someone in it (an empty one is sent once, on the change)
        self._scale = 1.0  # (0.8.17) vision.px_scale of the last frame looked at

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
        look = float(c.get("look_fps") or 0)  # (0.8.17) set only while Voice listens for a look (Face._watch_cfg)
        if look > 0:
            fps = max(fps, min(LOOK_MAX_FPS, look) / self.slow)
        if self.clock() < self.confirm_until:
            fps = max(fps, CONFIRM_FPS)
        return max(MIN_FPS, fps)

    def track_rate(self) -> float:
        """Detection frames a second while tracking fast: face.track.fps (at most 15), never under the recognition
        rate, halved when one is slow."""
        return max(self.rate(), min(TRACK_MAX_FPS, self._track_fps) / self.track_slow)

    def wait_s(self, cap: float) -> float:
        """How long the module's thread may sleep: `cap` (until its next full tick), or less when a detection-only
        frame is due sooner; never under WAIT_MIN_S."""
        if self.camera_open and self._track == TRACK_FAST:
            cap = min(cap, self.last_track_at + 1.0 / self.track_rate() - self.clock())
        return max(WAIT_MIN_S, cap)

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
        self._track = int(self.tracking() or TRACK_OFF) if c.get("track_on") else TRACK_OFF
        self._track_fps = float(c.get("track_fps") or 10)
        if self._track == TRACK_OFF and self.tracks:
            self._drop_tracks()
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
        # an open camera stays open only while idle time can be measured (input then closes it after the grace);
        # when it can't (None), only a wake, an unlock or a confirmation keeps it open, never "it was open already"
        keep = self.camera_open and idle is not None
        looking = (idle is not None and idle >= idle_s) or (locked and bool(c.get("when_locked")))
        want = looking or ((woke or confirming or keep) and grace) or self.held()
        if not want:
            self._close("resting")
            self._set("away" if self.away else "resting", "")
            return
        if not self.camera_open and not self._open():
            return
        self._set("away" if self.away else "watching", "")
        if now - self.last_frame_at >= 1.0 / self.rate():
            self.last_frame_at = self.last_track_at = now
            self._frame(now, c)
        else:
            self.track_tick()

    def track_tick(self) -> None:
        """A detection-only frame, if tracking fast and one is due (the module's thread calls it between full ticks;
        the camera's open/close rules are only ever decided in tick())."""
        now = self.clock()
        if not (self.camera_open and self._track == TRACK_FAST and now - self.last_track_at >= 1.0 / self.track_rate()):
            return
        self.last_track_at = now
        frame = self.camera.read()
        if frame is None:
            if not self.camera.is_open():
                self.camera_open = False
                self._drop_tracks()
                self.emit("watch", on=False, why="camera stopped")
            return
        t0 = self.clock()
        try:
            faces = self.detector.detect(frame, SCORE_OTHER)
            size = self.frames.size(frame)
        finally:
            del frame
        self._update_tracks(now, faces, size, {})
        if self.clock() - t0 > TRACK_SLOW_S:
            self._quick = 0
            self.track_slow = min(8.0, self.track_slow * 2)
        else:  # quick again for a while (a busy minute is over): back up a step
            self._quick += 1
            if self._quick >= TRACK_RECOVER and self.track_slow > 1:
                self._quick, self.track_slow = 0, self.track_slow / 2

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
            self._drop_tracks()
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

    def here(self, at: float | None = None) -> bool:
        """(0.9.0, core/here.py) Another sign you're here (Voice ID heard you, you used the dashboard): away ends
        ("back", never "arrived": no greeting) and starts counting again from now. True when it ended away."""
        self.here_at = max(self.here_at, self.clock() if at is None else at)
        if not self.away:
            return False
        self.away = False
        self.left_at = None
        self.emit("back")
        return True

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
        seen = max(self.present_at, self.here_at)
        gone = (not locked and self.camera_open and now - seen >= after) or (
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
                self._drop_tracks()
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
        full = self.frames.size(frame)
        self._scale = px_scale(*full)  # (0.8.17) min_face_px and the still check are pixels of a 480-high frame
        min_px = float(c.get("min_face_px") or 60) * self._scale
        faces = self.detector.detect(frame, SCORE_OTHER)
        best: tuple[float, list[float], Any, dict] | None = None
        judged: dict[int, bool] = {}  # index in faces -> recognised as you (for the tracks' owner flag)
        best_i = -1
        n_other = 0
        seen: list[dict] | None = [] if self.people() else None
        size = full if seen is not None else (0, 0)
        for i, f in enumerate(faces):
            p = _person(f, size) if seen is not None and f.score >= SCORE_WATCH else None
            if p is not None:
                seen.append(p)  # type: ignore[union-attr]
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
            if klass == "stranger":
                judged[i] = False  # unsure keeps the track's flag: one poor frame doesn't make you someone else
            if p is not None:
                p.update(who=klass, score=round(float(s), 3), e=list(e))  # a copy for the add-on, in memory only
            if klass == "owner":
                self.counts.you += 1
                good = st.blur >= BLUR_MIN and DARK <= st.mean <= BRIGHT and st.bright <= BLOWN
                if best is None or s > best[0]:
                    if best is not None:
                        n_other += 1
                    best = (s, e, f, {"good": good})
                    best_i = i
                else:
                    n_other += 1
            else:
                if klass == "unsure":
                    self.counts.unsure += 1
                else:
                    self.counts.not_you += 1
                n_other += 1
            del e  # a stranger's or an unsure face's numbers go with the frame
        if seen is not None:
            self.emit("people", faces=seen)  # every frame looked at, empty too: nobody in view is news as well
            del seen
        if self._track != TRACK_OFF:
            if best_i >= 0:
                judged[best_i] = True
            self._update_tracks(now, faces, full, judged)
        n_faces = sum(1 for f in faces if f.score >= SCORE_OTHER)
        # (0.8.13) for Voice ID's face assist: how many faces, and whether the only one is the owner's; and for
        # voice.listen.need_face each face's height (pixels) and yaw, numbers that say how close it is and where it
        # looks, never who (Face.close_facing counts the close and facing ones and drops these with the frame)
        sizes = [(float(f.height), _yaw(f)) for f in faces if f.score >= SCORE_OTHER]
        # (0.8.17, voice.listen.look_to_talk) the owner's face: height, yaw and pitch, for Face.looking (never who else)
        mine = (float(best[2].height), _yaw(best[2]), _pitch(best[2])) if best is not None else None
        # (0.8.17, voice.listen.look_gaze) and where his eyes sit in them: two numbers (gaze.py), only while wanted;
        # frame: its (width, height), so "close" is a share of the frame at any camera resolution
        eyes = self._eyes(frame, best[2]) if best is not None else None
        # (0.8.18, voice.listen.look_anyone) the other faces close enough to judge, the LOOK_OTHERS biggest: the same
        # numbers and eyes, so anyone's look opens the talk; never who they are, dropped with the frame
        looks = None
        if c.get("look_anyone"):
            rest = [f for i, f in enumerate(faces) if i != best_i and f.score >= SCORE_WATCH and f.height >= min_px]
            rest = sorted(rest, key=lambda f: -float(f.height))[:LOOK_OTHERS]
            looks = [(float(f.height), _yaw(f), _pitch(f), self._eyes(frame, f)) for f in rest]
        self.emit(
            "view", faces=n_faces, owner_alone=best is not None and n_other == 0, sizes=sizes, owner=mine, eyes=eyes,
            frame=full, looks=looks,
        )  # fmt: skip
        others = n_faces >= 2
        if others != self.others or others:  # while it lasts, every frame refreshes it (core/nearby.py's STALE_S)
            self.others = others
            self.emit("others", on=others)
        if best is None:
            self.recent.append(Seen(now, False))
            return
        _s, e, f, q = best
        self.recent.append(Seen(now, True, e, f, n_other > 0))
        # where your face is in the frame (its box's centre, -1..1, and width 0..1), for the being's eyes to find you:
        # the box only, never the picture or the numbers
        fw, fh = full
        if fw and fh:
            x, y, w, h = f.box
            self.emit(
                "seen",
                x=round((x + w / 2) / fw * 2 - 1, 3),
                y=round((y + h / 2) / fh * 2 - 1, 3),
                w=round(w / fw, 3),
                h=round(h / fh, 4),
                px=round(float(h), 1),
            )
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
        if self.still(mine, STILL_PX * self._scale):
            return  # a picture propped up in front of the camera: wait for movement
        gap = self.returning["gap"]
        self.returning = None
        self.arrived_at = now
        if self.away:
            self.away = False
            self.left_at = None
        self.emit("arrived", away_min=round(gap / 60), others=any(x.others for x in win))

    # ---------------------------------------------------------------------------------------------- tracking
    def _update_tracks(self, now: float, faces: list, size: tuple[int, int], judged: dict[int, bool]) -> None:
        """Match this frame's faces to the tracks (greedy, nearest centre first, within TRACK_MATCH face heights),
        update each one's micro-movement, start new ids, drop the long-missing, and emit "faces"."""
        fw, fh = size
        if not fw or not fh:
            return
        dets = []
        for i, f in enumerate(faces):
            x, y, w, h = f.box
            cx, cy, hh = x + w / 2, y + h / 2, max(1.0, float(h))
            dets.append((i, cx, cy, hh, tuple(((lx - cx) / hh, (ly - cy) / hh) for lx, ly in f.landmarks[:5])))
        pairs = sorted(
            (math.hypot(cx - tr.cx, cy - tr.cy) / max(hh, tr.h), tid, i)
            for i, cx, cy, hh, _ in dets
            for tid, tr in self.tracks.items()
        )
        got: dict[int, int] = {}  # det index -> track id
        for d, tid, i in pairs:
            if d <= TRACK_MATCH and i not in got and tid not in got.values():
                got[i] = tid
        for i, cx, cy, hh, rel in dets:
            tid = got.get(i)
            if tid is None:
                tid, self._next_id = self._next_id, self._next_id + 1
                self.tracks[tid] = Track(tid, cx, cy, hh, rel, now)
                got[i] = tid
            else:
                self._move(self.tracks[tid], now, cx, cy, hh, rel)
            if i in judged:
                if judged[i]:  # you: only one track is yours at a time
                    for tr in self.tracks.values():
                        tr.owner = False
                self.tracks[tid].owner = judged[i]
        mine = set(got.values())
        for tid in [t for t in self.tracks if t not in mine]:
            self.tracks[tid].miss += 1
            if self.tracks[tid].miss >= TRACK_MISS:
                del self.tracks[tid]
        out = [_shown(tr, fw, fh) for tr in sorted(self.tracks.values(), key=lambda t: t.id) if tr.miss == 0]
        if out or self._faces_shown:
            self._faces_shown = bool(out)
            self.emit("faces", faces=out)

    @staticmethod
    def _move(tr: Track, now: float, cx: float, cy: float, hh: float, rel: tuple) -> None:
        """Micro-movement: how far the centre, the size and the landmarks (relative to the face: a nod, a turn, the
        mouth's corners) moved since MICRO_WINDOW_S ago (the last frame, when frames are further apart), in face
        heights, less the detector's jitter, per second, scaled to 0..1; it rises at once and fades with MICRO_TAU."""
        tr.past.append((tr.t, tr.cx, tr.cy, tr.h, tr.rel))
        ref = next((x for x in tr.past if now - x[0] <= MICRO_WINDOW_S), tr.past[-1])
        t0, cx0, cy0, h0, rel0 = ref
        span, step = max(0.05, now - t0), max(0.05, now - tr.t)
        scale = max(hh, h0)
        moved_by = (
            math.hypot(cx - cx0, cy - cy0) / scale
            + abs(hh - h0) / scale
            + max((math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(rel, rel0, strict=False)), default=0.0)
        )
        raw = min(1.0, max(0.0, moved_by - MICRO_JITTER) / span / MICRO_FULL)
        tr.m = max(tr.m * math.exp(-step / MICRO_TAU), tr.m + (raw - tr.m) * MICRO_RISE)
        tr.cx, tr.cy, tr.h, tr.rel, tr.t, tr.miss = cx, cy, hh, rel, now, 0

    def _drop_tracks(self) -> None:
        self.tracks.clear()
        if self._faces_shown:
            self._faces_shown = False
            self.emit("faces", faces=[])

    def _eyes(self, frame, face) -> tuple[float, float] | None:
        """(0.8.17) The owner's iris offsets (gaze.Eyes' h and v), when a gazer is wanted now; None otherwise or
        when the eyes can't be read (a blink, glare, too small)."""
        try:
            g = self.gaze()
            e = g.eyes(frame, face) if g is not None else None
        except Exception as ex:
            self.emit("failed", part="reading the eyes", error=type(ex).__name__)
            return None
        return (round(e.h, 4), round(e.v, 4)) if e is not None else None

    @staticmethod
    def still(mine: list[Seen], px: float = STILL_PX) -> bool:
        if len(mine) < 2:
            return False
        for i in range(len(mine)):
            for j in range(i + 1, len(mine)):
                a, b = mine[i], mine[j]
                if a.e is None or b.e is None:
                    return False
                if not (dot(a.e, b.e) > STILL_COS and moved(a.face, b.face) < px):
                    return False
        return True


def _shown(tr: Track, fw: int, fh: int) -> dict:
    """One face in "faces": its track id, centre (-1..1, the camera's own picture), height's share, owner flag, m."""
    x, y = round(tr.cx / fw * 2 - 1, 3), round(tr.cy / fh * 2 - 1, 3)
    return {"id": tr.id, "x": x, "y": y, "h": round(tr.h / fh, 4), "owner": tr.owner, "m": round(tr.m, 3)}


def _yaw(f) -> float | None:
    """vision.pose's yaw, or None when the landmarks can't give one (then the face doesn't count as facing it)."""
    try:
        return round(pose(f).yaw, 3)
    except Exception:
        return None


def _pitch(f) -> float | None:
    """vision.pose's pitch, or None (then the owner doesn't count as looking at it)."""
    try:
        return round(pose(f).pitch, 3)
    except Exception:
        return None


def _person(f, size: tuple[int, int]) -> dict:
    """One face for Face.watch_people: its box's height (pixels and share of the frame), centre (-1..1, the camera's
    own picture, not mirrored), width share, yaw (vision.pose, mirrored: negative = turned to their left) and the
    detector's score. who/score/e are filled in when the face was big and clear enough to be judged, else None."""
    fw, fh = size
    x, y, w, h = f.box
    try:
        yaw = round(pose(f).yaw, 3)
    except Exception:
        yaw = None
    return {
        "h_px": round(float(h), 1),
        "h": round(h / fh, 4) if fh else None,
        "w": round(w / fw, 4) if fw else None,
        "x": round((x + w / 2) / fw * 2 - 1, 3) if fw else None,
        "y": round((y + h / 2) / fh * 2 - 1, 3) if fh else None,
        "yaw": yaw,
        "det": round(float(f.score), 3),
        "who": None,
        "score": None,
        "e": None,
    }


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
    "Kurooto is asleep",  # (0.8.18, mind.sleep.senses_off)
    "enrolling",
    "camera in use by another program",
    "no camera",
    "camera blocked by the system",
    "camera covered",
    "template locked",
)
