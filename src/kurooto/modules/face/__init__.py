"""Face presence (0.8.10, off by default): Kurooto knows your face, on this computer only, and greets you by voice
when you sit down at your desk after a while, then opens Voice's conversation so you can answer straight away.

Set up (Features → Face presence → Set up, or `kurooto face install-from FOLDER`) fetches OpenCV's headless package and
two models from OpenCV's model zoo (about 0.18 GB, parts.py). Nothing watches until you enrol on the dashboard's Face
page (Start: the guarded action camera.open). Enrolment, training, the test and what "training" honestly means:
enrol.py and model.py. Watching, arrival and away: watch.py. The greeting: greet.py.

What's kept: your template only (numbers that describe your face, never a picture), sealed with AES-GCM under the
secret face.key (core/biometric.py), in <state>/face/template.bin, and its status (counts and dates) in
<state>/face/face.json. Frames, crops and strangers' numbers live in memory and go with each frame. Forget (`/face
forget`, `kurooto face forget`, the Face page, /forget all) deletes the key first, then the template and its status.

A face match never authorises anything: it isn't one of core/tap.py's ways, never answers an approval or unlocks
anything (tests/unit/test_face.py checks no such path reads this module). The one narrow use (0.8.13,
voice.speaker_id.face_assist): a voice Voice ID already scored inside its "not sure" margin counts as the owner while
only his face is in view (each frame's "view" -> core/nearby.py). A face alone never makes Kurooto act.

The dashboard: GET /api/face (status and stage), POST /api/face/<action> (web/api.py), GET /api/face/frame?s=<session>
(a JPEG made in memory, Cache-Control: no-store) and the live stream's {"t": "face"} messages (to the Face page only,
and {kind: "camera", on} to every page). Events carry no scores, embeddings or image data.

Hooks for add-ons (0.8.12): watch_people(cb) hands an add-on every face in each frame the watcher looks at (box, place,
yaw, identity, score and its numbers, in memory only), hold_watch(reason) / release_watch(reason) keep the camera
looking while you type (never past a pause reason), owner_desk_height() says how big your face usually is at the desk.
Switches face.addons.watch and face.addons.hold; with no add-on using them, nothing changes and nothing runs.

Who's talking (0.8.13, voice.listen.need_face): each frame's faces are counted as close (at least
voice.listen.face_near of owner_desk_height()) and facing the camera (yaw within voice.listen.face_yaw_deg) or not;
only the time and the counts go to core/nearby.py, so Voice answers only someone in front of it. While Voice listens it
holds the camera with hold_watch(..., core=True): a hold of Kurooto's own, not an add-on's, so face.addons.hold doesn't
turn it off; every pause reason still applies first.

Look at it to talk (0.8.17, voice.listen.look_to_talk): each frame, whether the owner's face is close and turned to the
camera within the tight look angles (looking()) goes to core/nearby.py as a time, and Voice is told at once
(Voice.look_tick), so a steady look opens its conversation as if its name was said.

By the eyes (0.8.17, voice.listen.look_gaze): with the eye model here (Get the eye model on the Face page: MediaPipe
Iris, 2.6 MB) and your eyes calibrated (Calibrate my eyes: three seconds looking at the lens; four numbers kept in the
sealed template, never a picture), looking() goes by where your eyes point (gaze.py: the head's turn and the irises'
place together), so eyes on the screen below the camera don't count and a head a little turned with the eyes on the lens
does. Without either, the head's turn as before; status()["gaze"] and /voice say which. While Voice listens for a look
the watcher looks at face.watch.look_fps frames a second (at most 5).

Camera resolution (0.8.17): sizes are shares of the frame (close_facing, owner_desk_height, enrolment's front face) or
pixels of a 480-high frame scaled to the camera's (vision.px_scale), so a camera switched from 480x640 to 1080x1440
changes nothing but sharper eyes. YuNet always looks at a 320-wide copy.

Add this look (0.9.0, face.looks.on): a look your template doesn't know (hair up, a new beard) scores "unsure", and
learning never learns from unsure frames. The Face page's Add this look, `/face add-look [label]` or `kurooto face
add-look [label]` (only you start it: camera.open, typed or the button) opens the camera for about 10 seconds, takes up
to 10 samples through enrolment's checks (enrol.py's Look), and adds them as enrolled samples of their own look after
model.look_check() says they're safe; a look that isn't is refused with the reason, never added with a looser
threshold. Each look is listed on the Face page with Remove; at most model.LOOKS_MAX.

Tracking (0.8.12, face.track.on): while the camera is open and a dashboard is in sight or an add-on holds the camera,
every face in view goes out as {"t": "face", "kind": "faces", "faces": [{id, x, y, h, owner, m}]} (at most 10 a
second; watch.py's tracking), so the being's eye can follow anyone; watch_faces(cb) hands the same to an add-on. A
dashboard in sight, or a hold whose reason says "track", detects at face.track.fps between the recognition frames.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
import re
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

from kurooto.core import here, nearby, persona
from kurooto.core.biometric import Locked, TemplateStore, load_impostors
from kurooto.core.config import register_defaults
from kurooto.core.state import jsave
from kurooto.modules.base import Answer, Command, Incoming, Intent, Module
from kurooto.modules.face import gaze as gaze_mod
from kurooto.modules.face import parts as face_parts
from kurooto.modules.face.enrol import (
    LOOK_S,
    LOOK_TARGET,
    MINIMUM,
    PLAN,
    TARGET,
    TARGETS,
    Enrolment,
    Look,
    Session,
    Vision,
)
from kurooto.modules.face.model import (
    FLOOR,
    LOOK_MIN,
    LOOKS_MAX,
    MODEL,
    STRICTNESS,
    Template,
    centroids,
    is_look,
    look_check,
    score,
)
from kurooto.modules.face.vision import YAW_K, pitch_degrees, px_scale, yaw_degrees
from kurooto.modules.face.watch import PAUSES, TRACK_FAST, TRACK_OFF, TRACK_SLOW, Watcher

if TYPE_CHECKING:
    from kurooto.app import App

# (0.9.0) kurooto_now (core/tools.py): every AI can ask whether you're at the desk and since when, on a call, the
# channel, Voice ID's last word, Brain's plan line and the camera's state: words only, never pictures or senses
register_defaults("face", {"tools": True})
# (0.9.0) the being's eye looks at whoever is talking: your face when Voice ID says it's you, else the face moving
# most; only "someone is talking" and Voice ID's word reach the page, never sound
register_defaults("face", {"track": {"speaker": True}})
# (0.9.0) your time at the desk, from Face presence's arrivals and departures (times only): a line in the evening
# check-in and the weekly summary ("6 h at the desk, longest 2 h 40 unbroken"); off by default
register_defaults("face", {"desk_time": False})
register_defaults(
    "face",
    {
        "camera": {
            "device": "",  # the camera: empty = the first ordinary one (infrared skipped); a number or part of its name
            "width": 640,  # capture size asked of the camera (it may give another)
            "height": 480,  # capture height asked of the camera
            # (0.9.0) degrees the spot you look at sits beside the lens (+: to your right as you face it; -30 to 30):
            # look to talk centres on it, head and eyes alike; 0 = the lens itself (an add-on's camera may set it)
            "yaw_offset_deg": 0.0,
        },
        "watch": {
            "fps": 1.0,  # frames a second it looks at while watching for you (0.2 to 2)
            "fps_battery": 0.33,  # frames a second on battery
            "look_fps": 5.0,  # while Voice listens for a look: at least this many frames a second (0: as usual; max 5)
            "idle_s": 60,  # seconds with no keyboard or mouse before the camera looks (while you type, it doesn't)
            "when_locked": False,  # also look while the screen is locked (off: paused while locked)
            # (0.9.0) keep looking during focus and a study timer: look to talk, the desk keeping it awake and an
            # add-on's eye go on while you study (off: paused in focus, as before)
            "in_focus": True,
            "night": False,  # also look during the night hours (availability.night); off: paused at night
        },
        "recognise": {
            "strictness": "normal",  # false accepts per frame: loose 1 in 100, normal 1 in 1,000, strict 1 in 10,000
            "threshold": 0.0,  # 0 = the calibrated one; else this cosine score (0 to 1) overrides it, never below 0.363
            "min_face_px": 60,  # faces smaller than this (pixels, at the capture size) are ignored: too far to judge
            "frames": 3,  # recognised in this many of the last 4 frames = you're here
        },
        "greet": {
            "on": True,  # greet you by voice when you arrive (needs Voice speaking)
            "after_absent_min": 20,  # only after you've been away at least this long (minutes)
            "gap_min": 60,  # at most one greeting in this many minutes
            "per_day": 3,  # at most this many greetings a day
            # what it says: next (today), waiting, deadline (24 h), held, answers (0.9.0: not read while you were away)
            "say": ["next", "waiting", "deadline", "answers"],
            "with_others": "skip",  # someone else in view too: skip (no greeting), short ("Welcome back." only) or full
            "talk": True,  # then open the conversation: answer without saying its name (needs Voice listening)
            "listen_s": 12,  # how long that conversation stays open with nothing said (seconds)
            # (0.9.0) each greeting is a Brain decision record (the parts said, never the words) closed by whether you
            # answered it, and the nightly look back may propose a different gap_min from them (your tap applies it)
            "records": True,
            # (0.9.0) when you answer the greeting, your AI is told what it had just said (rule-made words: counts, a
            # class's or a deadline's title), so "yes" continues it
            "tell_ai": True,
            # (0.9.0) an add-on may add one short line of its own to the greeting (said last, alone in view only)
            "addons": False,
        },
        "away": {
            "on": False,  # notice when you leave the desk (events "left" and "back")
            "after_min": 5,  # no sign of you (face or keyboard) this long = you've left (minutes)
            "hold_desktop": False,  # while you're away, desktop pop-ups wait and answers aren't read aloud
            "hold_calls": False,  # while you're away, calls Kurooto starts itself wait (at most hold_max_min)
            "hold_max_min": 60,  # the longest a call waits while you're away (minutes)
            # (0.9.0) while you're away, note the times someone else's face was in view (times and counts only, in
            # memory, never a picture or who) and tell you once you're back
            "report_others": False,
            # (0.9.0) with Brain's phone places sensor: your phone leaving a place you saved marks you away at once
            "use_places": False,
            # (0.9.0) and while your phone is out, the camera stays closed (a look, an arrival: none till it's back)
            "places_close_camera": False,
        },
        "track": {
            "on": True,  # while the camera is open, follow every face in view (places only) for the being's eye
            "fps": 10,  # detection frames a second while a dashboard is in sight or an add-on tracks (1 to 15)
        },
        # (0.9.0) the room's light from the camera's frames, a smoothed number only (never a frame), for Brain's body
        # and add-ons (light_level()); only while the camera looks anyway
        "light_sense": False,
        "addons": {
            "watch": True,  # an add-on may see who's in view (faces' places and numbers, in memory; never pictures)
            "hold": True,  # an add-on may keep the camera looking while you type (never past a pause or a switch)
            # (0.9.0) an add-on may say "everyone else in view is someone I know" (a yes or no, never who): with
            # face.greet.with_others skip, they get the short greeting instead of none
            "known_guests": True,
        },
        # (0.9.0) natural breaks for Brain's door (mind/breaks.py): you leaving (with away on), looking up at the
        # camera, standing up (your face well below its usual desk size); kinds and times only
        "breaks": True,
        "learn": {
            "on": False,  # refine your template slowly from confident recognitions (never unsure ones), with Undo
            "every_h": 6,  # at most one new sample this often (hours)
            "max": 30,  # at most this many learned samples (the oldest goes first); enrolled samples are never replaced
            "margin": 0.08,  # a frame must beat your threshold by this much to be learned from
            # (0.9.0) Voice ID sure a turn was your voice, with only your face in view: a sample may be learned from
            # that frame too, not only after an arrival and typing (the same caps, spacing and Undo)
            "from_voice": False,
        },
        "looks": {
            # (0.9.0) Add this look: you may add a short capture of how you look now (hair up, a new beard) to your
            # face model, only when you start it; off: no new looks, and the ones you added stop counting
            "on": True,
        },
    },
)

TICK_S = 0.25  # the watcher's thread looks this often (frames are taken at the watcher's own rate)
FACES_EVERY_S = 0.09  # "faces" to the pages at most about 10 a second
HOLD_MAX_S = 600.0  # an add-on's hold lasts at most this long unless renewed: a crashed add-on can't keep the camera
DESK_EVERY_S = 5.0  # your face's size at the desk is noted at most this often (a running median, in memory)
DESK_MIN = 10  # sightings before the running median is trusted over the enrolment's front step
LOOK_BREAK_S = 1.0  # (face.breaks) a look at the camera this long is "you looked up", a natural break
STOOD_RATIO = 0.6  # (face.breaks) your face under this share of its usual desk height: you stood up
STOOD_BACK = 0.8  # and back over this share: sitting again (the next stand counts)
BLINK_HOLD_S = 1.0  # (look by the eyes) a frame whose eyes can't be read keeps the last verdict this long
EYE_MB = 2.64  # the eye model (parts.py's iris)
CONFIRM_FORGET_S = 7 * 86400  # Delete my face data, offered when Face presence is turned off, works this long
IMPOSTORS = "face-impostors.npz"
GREET_EXPECT_H = 0.05  # (greet.records) a greeting that opened the conversation expects an answer within 3 minutes
ADDON_LINE_MAX = 120  # (greet.addons) an add-on's greeting line is cut to this many characters
LIGHT_ALPHA = 0.2  # (light_sense) each frame moves the smoothed level this share of the way
LIGHT_STALE_S = 120.0  # ...and a level older than this isn't the room's any more (the camera closed)
OTHERS_MAX = 120  # (away.report_others) at most this many minutes with someone else in view are noted while away
OTHERS_SAID = 6  # ...and the message names at most this many of them
SIZE_GB = 0.18
LICENCES = [
    {"what": "YuNet face detection (face_detection_yunet_2023mar)", "licence": "MIT (Shiqi Yu)", "mb": 0.23},
    {"what": "SFace face recognition (face_recognition_sface_2021dec)", "licence": "Apache-2.0", "mb": 38.7},
    {
        "what": "opencv-python-headless and numpy",
        "licence": "Apache-2.0 and BSD-3; the wheel bundles FFmpeg's libraries (LGPL-2.1+) and the GCC runtime "
        "(GPL-3.0 with the runtime exception)",
        "mb": 140,
    },
]
EARLY = PAUSES[:3] + ("template locked",)  # no watcher is built for these
# a session's kind -> the page's stage
STAGES = {"enrol": "capturing", "test": "testing", "gaze": "calibrating", "look": "looking"}
SAY_PARTS = ("next", "waiting", "deadline", "held", "answers")
TOGGLES = {
    "greet.on": "Greet me when I sit down",
    "greet.talk": "Then listen for my answer",
    "away.on": "Notice when I leave",
    "learn.on": "Learn slowly from confident sightings",
}
PAUSE = re.compile(
    r"^(?:please\s+)?(?:stop watching(?: me)?|pause (?:the |my )?(?:camera|webcam|face presence)|don'?t watch me)"
    r"(?:\s+for\s+(?:an?\s+|one\s+)?(?P<n>\d+)?\s*(?P<u>hours?|h|minutes?|mins?|m)\b)?[\s.!]*$",
    re.I,
)
STATUS = re.compile(
    r"^(?:are you|is (?:kurooto|it)) (?:watching|looking at|seeing) me\b|^is (?:the|my) (?:camera|webcam) on\b"
    r"|^(?:is )?face presence (?:on|watching)\b",
    re.I,
)
LABEL_MAX = 40  # (looks) a look's label, in characters
FORGET = re.compile(r"^(?:please\s+)?(?:forget|delete|erase) my face(?: data| model| template)?[\s.!]*$", re.I)


def _sleeping(app) -> bool:
    """(0.8.18) Kurooto asleep with mind.sleep.senses_off on: the camera stays shut until it's woken."""
    try:
        from kurooto.mind import sleep

        return sleep.senses_off(app)
    except Exception:
        return False


def _event_safe(**fields) -> dict:
    """What a face event may carry: never a score, an embedding or image data."""
    return {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}


ALLOWED_FIELDS = {"on", "why", "away_min", "parts", "talk", "samples", "grade", "count", "part", "error", "result"}


class Face(Module):
    id = "face"
    title = "Face presence: greet you at your desk"
    description = (
        "Knows your face, on this computer only, and greets you by voice when you sit down after a while: what's "
        "next today and what's waiting, then it listens for your answer. Strangers do nothing and are never kept."
    )
    privacy = (
        "Runs on this computer only, on the CPU. Frames are looked at in memory and dropped; only your template "
        "(numbers that describe your face, never a picture) is kept, encrypted. Nothing is sent anywhere. It's never a "
        "lock: a face match never approves or unlocks anything."
    )
    heavy = False
    setup_notes = (
        (
            "A webcam on this computer, and its light on while Face presence looks",
            "Features → Face presence → Set up, then the Face page (Start); face.camera.device picks another camera",
            "turn Face presence off; /face forget deletes your face model",
        ),
        (
            "On macOS and Windows, the system's camera permission for the program that runs Kurooto",
            "macOS: System Settings → Privacy & Security → Camera; Windows: Settings → Privacy & security → Camera → "
            '"Let desktop apps access your camera"; `kurooto face test-camera` checks it',
            "the same switch, off",
        ),
    )

    def __init__(self, app: App):
        super().__init__(app)
        self.parts = face_parts.parts(app)
        self.store = TemplateStore(app, "face")
        self.session: Session | None = None
        self.watcher: Watcher | None = None
        self.why = "feature off"
        self.paused_until: float | None = None  # /face pause: a time.time() end, inf = until /face pause off
        self.held: deque = deque(maxlen=20)  # desktop pop-ups held while you're away (title, text, urgent)
        self._tpl: Template | None = None
        self._tpl_lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._halt = threading.Event()
        self._vision: tuple | None = None
        self._idle = None
        self._idle_at = (0.0, None, False)
        self._battery_at = (0.0, False)
        self._greets: dict = {}
        self._break_look: float | None = None  # (face.breaks) the run of looks already called a break
        self._stood = False  # (face.breaks) your face is under STOOD_RATIO of its desk size: stood up, said once
        self.slow = 1.0
        self._previous: dict | None = None  # the template before the last training, sealed nowhere: Undo, this run only
        self._people: list = []  # add-ons watching who's in view (watch_people)
        self._faces: list = []  # add-ons following every face's place (watch_faces)
        self._faces_at = 0.0
        self._holds: dict[str, float] = {}  # an add-on's reason -> until (monotonic): hold_watch
        self._core_holds: set[str] = set()  # the reasons among them that are Kurooto's own (Voice): hold_watch(core)
        self._hooks_lock = threading.Lock()
        self._desk: deque = deque(maxlen=240)  # (pixels, share) of your face's height, sightings 5 s apart
        self._desk_at = 0.0
        self._gazer: object | None = None  # (0.8.17) the eye model, loaded once it's wanted (gaze.CvGazer)
        self._gazer_failed = -1e9  # when loading it last failed (monotonic): not tried again for a minute
        self._gaze_last: dict = {}  # the last frame's gaze: degrees and the verdict, numbers only, in memory
        self._greet_parts: dict[str, object] = {}  # (0.9.0, greet.addons) an add-on's name -> its line's callable
        self._carried: dict[str, float] = {}  # ...and when the greeting last said its line (time.time())
        self._known: list = []  # (0.9.0, addons.known_guests) add-ons' "everyone else here is known" callables
        self._light: tuple[float, float] | None = None  # (0.9.0, light_sense) (level 0..1, monotonic time)
        self._greet_rec = ""  # (0.9.0, greet.records) the open greeting's decision record id, until its talk closes
        self._others_away: dict[int, int] = {}  # (0.9.0, away.report_others) minute (epoch // 60) -> most faces seen
        self._look_last: dict = {}  # (0.9.0, looks) the last look's result: {at, ok, message}, for the terminal

    # ------------------------------------------------------------------------------------------- the parts
    def wants(self) -> list[str]:
        return list(face_parts.WANTS)

    def ready(self) -> tuple[bool, str]:
        missing = self.parts.missing(self.wants())
        if missing:
            return False, f"needs setting up (downloads about {self.parts.size_gb(missing):g} GB)"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        from kurooto.core.prereqs import Prereqs

        free = lambda: Prereqs.free_gb(self.parts.models_dir.parent)  # noqa: E731
        return self.parts.install(self.wants(), progress, free_gb=free)

    def install_from(self, folder: str, progress=print) -> tuple[bool, str]:
        from pathlib import Path

        out = self.parts.install_from(folder, self.wants(), progress)
        if (Path(folder).expanduser() / face_parts.IRIS).is_file():  # (0.8.17) the optional eye model, when it's there
            self.parts.install_from(folder, face_parts.EYES, progress)
        return out

    def health(self) -> tuple[bool, str]:
        ok, why = self.ready()
        if not ok:
            return ok, why
        return True, self.line()

    def health_check(self):
        from kurooto.core.health import Check

        return Check(
            "face",
            "Face presence",
            module="face",
            probe=lambda net: self.health(),
            help="Features → Face presence → Set up",
        )

    # ------------------------------------------------------------------------------------------ the template
    def template(self) -> Template | None:
        """Your template, unsealed once and kept in memory while Kurooto runs. Raises Locked."""
        with self._tpl_lock:
            if self._tpl is None:
                d = self.store.load()
                self._tpl = Template.from_payload(d) if d else None
                if self._tpl is not None:
                    self._tpl.from_store = True
            return self._tpl

    def _template_or_none(self) -> Template | None:
        try:
            return self.template()
        except Locked:
            return None

    def _save(self, t: Template) -> None:
        with self._tpl_lock:
            if t.from_store and t is not self._tpl:
                return  # forgotten (or replaced) meanwhile: a learn or a retrain never brings an old template back
            t.updated = t.updated or time.time()
            status = {**t.status(), "model_sha": face_parts.SFACE_SHA[:12], "greets": self._greets}
            self.store.save(t.to_payload(), status)
            self._tpl = t

    def enrolled(self) -> bool:
        return bool(self.store.status().get("enrolled")) and self.store.exists()

    def reenrol_needed(self) -> bool:
        st = self.store.status()
        return bool(st.get("enrolled")) and str(st.get("model_sha") or "") != face_parts.SFACE_SHA[:12]

    def impostors(self) -> list[list[float]] | None:
        from importlib import resources

        try:
            path = resources.files("kurooto").joinpath("data", IMPOSTORS)
            return load_impostors(path, face_parts.SFACE_SHA)  # type: ignore[arg-type]
        except Exception:
            return None

    def greets(self) -> dict:
        if not self._greets:
            self._greets = dict(self.store.status().get("greets") or {})
        return self._greets

    # --------------------------------------------------------------------------------------------- pausing
    def _idle_now(self) -> tuple[float | None, bool]:
        at, idle, locked = self._idle_at
        if time.monotonic() - at > 1.0:
            from kurooto.core.idle import IdleProbe

            if self._idle is None:
                self._idle = IdleProbe(self.app.paths.state)
            try:
                locked = bool(self._idle.locked())
                idle = self._idle.idle_seconds()
            except Exception:
                idle, locked = None, False
            self._idle_at = (time.monotonic(), idle, locked)
        return idle, locked

    def on_battery(self) -> bool:
        at, val = self._battery_at
        if time.monotonic() - at > 30:
            from kurooto.core.power import on_ac

            try:
                val = not on_ac()
            except Exception:
                val = False
            self._battery_at = (time.monotonic(), val)
        return val

    def _on_call(self) -> bool:
        from kurooto.web.tools_api import live_call

        try:
            return live_call(self.app)
        except Exception:
            return False

    def pause_checks(self) -> list[tuple[str, object]]:
        """Each pause reason with its check, in PAUSES order; checked lazily (the later ones read the system)."""
        from kurooto.core.clock import now

        app, s = self.app, self.setting

        def problem(name: str):
            return lambda: self.watcher is not None and self.watcher.problem_now() == name

        def focus() -> bool:
            if s("watch.in_focus") is not False:  # (0.9.0) study mode doesn't close the camera
                return False
            try:
                return app.availability.focus_until(now()) is not None
            except Exception:
                return False

        def night() -> bool:
            try:
                return not s("watch.night") and app.availability.night(now()) is not None
            except Exception:
                return False

        return [
            ("feature off", lambda: not app.is_on(self.id)),
            ("not enrolled", lambda: not self.enrolled() or self.reenrol_needed()),
            ("not set up yet", lambda: bool(self.parts.missing(self.wants()))),
            ("paused by you", lambda: self.paused_until is not None and time.time() < self.paused_until),
            ("Kurooto is paused", lambda: app.power.current == "paused" and app.power.paused_until() is not None),
            ("on battery (pause mode)", lambda: app.power.current == "paused"),
            ("screen locked", lambda: not s("watch.when_locked") and self._idle_now()[1]),
            ("you're on a call", self._on_call),
            ("focus", focus),
            ("night hours", night),
            ("Kurooto is asleep", lambda: _sleeping(app)),  # (0.8.18, mind.sleep.senses_off): /wake wakes it
            ("your phone is out", self._phone_out),  # (0.9.0, face.away.places_close_camera)
            ("enrolling", lambda: self.session is not None and self.session.state != "ended"),
            ("camera in use by another program", problem("camera in use by another program")),
            ("no camera", problem("no camera")),
            ("camera blocked by the system", problem("camera blocked by the system")),
            ("camera covered", problem("camera covered")),
            ("template locked", lambda: self.store.exists() and not self.store.readable()),
        ]

    def pause_reason(self) -> str:
        for name, check in self.pause_checks():
            if check():  # type: ignore[operator]
                if name == "not enrolled" and self.reenrol_needed():
                    return "re-enrol needed (the recognition model changed)"
                return name
        return ""

    def pause(self, arg: str = "") -> str:
        """/face pause [1h|30m|off]: no camera until then (or until /face pause off)."""
        a = (arg or "").strip().lower()
        if a in ("off", "resume", "on", "end"):
            self.paused_until = None
            self.app.events.emit("face_watch", on=False, why="resumed")
            return "Face presence: watching again (when you're idle)."
        m = re.fullmatch(r"(\d+)\s*(h|hours?|m|mins?|minutes?)?", a)
        if m:
            secs = int(m[1]) * (60 if (m[2] or "h").startswith("m") else 3600)
            self.paused_until = time.time() + secs
            until = dt.datetime.fromtimestamp(self.paused_until)
            said = f"until {until:%H:%M}"
        else:
            self.paused_until = float("inf")
            said = "until /face pause off"
        if self.watcher is not None:
            self.watcher.release()
        self.app.events.emit("face_watch", on=False, why="paused by you")
        return f"Face presence paused {said}: the camera stays off."

    # ------------------------------------------------------------------------------------------ watching
    def _vision_objects(self, threads: int = 1):
        self.parts.importable()
        from kurooto.modules.face import vision

        det = vision.opencv_detector(self.parts.path(face_parts.YUNET), threads)
        emb = vision.opencv_embedder(self.parts.path(face_parts.SFACE))
        return det, emb, vision.opencv_frames()

    def make_camera(self):
        from kurooto.modules.face.camera import Camera

        s = self.setting
        return Camera(str(s("camera.device") or ""), int(s("camera.width") or 640), int(s("camera.height") or 480))

    def _watch_cfg(self) -> dict:
        s = self.setting
        return {
            "fps": s("watch.fps"),
            "fps_battery": s("watch.fps_battery"),
            "idle_s": s("watch.idle_s"),
            "when_locked": s("watch.when_locked"),
            "after_absent_min": s("greet.after_absent_min"),
            "frames": s("recognise.frames"),
            "min_face_px": s("recognise.min_face_px"),
            "away_on": s("away.on"),
            "away_after_min": s("away.after_min"),
            "track_on": s("track.on"),
            "track_fps": s("track.fps"),
            "look_fps": s("watch.look_fps") if self._look_listening() else 0,
            # (0.8.18) every close face's look, not only yours, while Voice listens for one
            "look_anyone": bool(self.app.settings.get("voice.listen.look_anyone", True)) and self._look_listening(),
            "light": bool(self.setting("light_sense")),  # (0.9.0) each frame's mean brightness, a number only
        }

    def _tpl_live(self) -> Template | None:
        """The template as recognition uses it now: with face.looks.on off, the looks' centroids don't count."""
        t = self._template_or_none()
        if t is not None:
            t.use_looks = bool(self.setting("looks.on"))
        return t

    def _classify(self, e) -> tuple[str, float]:
        t = self._tpl_live()
        if t is None:
            return "stranger", 0.0
        over = float(self.setting("recognise.threshold") or 0)
        if over > 0:
            over = max(FLOOR, over)  # an override never goes under OpenCV's published floor: unsure is never you
            s = t.score(e)
            return ("owner" if s >= over else "unsure" if s >= max(0.2, over - 0.1) else "stranger"), s
        return t.classify(e)

    def _learnable(self, e) -> bool:
        t = self._tpl_live()
        return bool(t and self.setting("learn.on") and t.learnable(e, float(self.setting("learn.margin") or 0.08)))

    def build_watcher(self, camera=None, detector=None, embedder=None, frames=None, clock=time.monotonic) -> Watcher:
        if detector is None:
            detector, embedder, frames = self._vision_objects(1)
        return Watcher(
            camera=camera or self.make_camera(),
            detector=detector,
            embedder=embedder,
            frames=frames,
            classify=self._classify,
            paused=self.pause_reason,
            cfg=self._watch_cfg,
            idle=lambda: self._idle_now()[0],
            locked=lambda: self._idle_now()[1],
            on_battery=self.on_battery,
            emit=self._on_watch,
            learnable=self._learnable,
            clock=clock,
            held=self._held_now,
            people=self._people_on,
            tracking=self._track_mode,
            gaze=self._gaze_now,
        )

    def tick(self) -> None:
        """One look (the watcher's thread calls it every TICK_S)."""
        why = self.pause_reason()
        if why in EARLY or why.startswith("re-enrol"):
            if self.watcher is not None:
                self.watcher.release()
                self.watcher.state, self.watcher.why = "paused", why
            self.why = why
            return
        if self.watcher is None:
            try:
                self.watcher = self.build_watcher()
            except Exception as e:
                self.why = "not set up yet"
                self._failed("loading the models", e)
                self._halt.wait(30)
                return
        elif self._camera_changed():  # face.camera.* changed: the new camera from the next look, no restart
            self.watcher.release()
            self.watcher.camera, self.watcher.problem = self.make_camera(), None
        self.watcher.tick()
        self.why = self.watcher.why

    def _camera_changed(self) -> bool:
        cam = getattr(self.watcher, "camera", None)
        if not hasattr(cam, "want"):  # not a real camera (tests)
            return False
        s = self.setting
        want = (str(s("camera.device") or ""), int(s("camera.width") or 640), int(s("camera.height") or 480))
        return (cam.want, cam.width, cam.height) != want

    def _run(self) -> None:
        # a full tick (pause reasons, input, the camera's rules) every TICK_S; between them, while tracking fast, only
        # the detection-only frames (Watcher.track_tick), and the sleep is Watcher.wait_s: never under 20 ms
        next_full = 0.0
        try:
            while not self._halt.is_set():
                try:
                    if time.monotonic() >= next_full:
                        next_full = time.monotonic() + TICK_S
                        self.tick()
                    elif self.watcher is not None:
                        self.watcher.track_tick()
                except Exception as e:
                    self._failed("watching", e)
                    if self.watcher is not None:
                        self.watcher.release()
                    self._halt.wait(5)
                gap = next_full - time.monotonic()
                self._halt.wait(self.watcher.wait_s(gap) if self.watcher is not None else max(0.02, gap))
        finally:
            if self.watcher is not None:
                self.watcher.release()

    async def background(self, stop: asyncio.Event) -> None:
        self._halt.clear()
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="face-watch", daemon=True)
            self._thread.start()
        try:
            while not stop.is_set() and not self._halt.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    pass
        finally:
            self._halt.set()

    def _tell_study(self, kind: str) -> None:
        """(0.9.0, study.face) The Study tracker offers a pause or a resume in a focus (modules/study.py)."""
        study = self.app.modules.get("study")
        if study is None or not self.app.is_on("study") or not hasattr(study, "face_event"):
            return
        try:
            study.face_event(kind)
        except Exception as e:
            self._failed("telling the Study tracker", e)

    def _failed(self, part: str, e: BaseException) -> None:
        self.app.events.emit("face_failed", **_event_safe(part=part, error=f"{type(e).__name__}"[:80]))

    def _push(self, msg: dict, cid: int | None = None) -> None:
        live = getattr(self.app, "live", None)
        if live is None:
            return
        try:
            live.push(msg, only=None if cid is None else {cid})
        except Exception:
            pass

    def _on_watch(self, kind: str, **f) -> None:
        if kind == "watch":
            self.app.events.emit("face_watch", **_event_safe(on=bool(f.get("on")), why=str(f.get("why") or "")))
            if not f.get("on"):
                nearby.clear_view(self.app)
            self._push({"t": "face", "kind": "camera", "on": bool(f.get("on"))})
        elif kind == "arrived":
            self._arrived(int(f.get("away_min") or 0), bool(f.get("others")))
        elif kind == "left":
            self.app.events.emit("face_left")  # (0.9.0) a "left" break too, with face.breaks (mind/breaks.py)
            self._tell_study("left")
        elif kind == "back":
            nearby.set_phone_out(self.app, False)  # (0.9.0) somebody's at the desk: the phone's "out" is over
            self.app.events.emit("face_back")
            self.flush_desktop()
            self.report_others()
            self._tell_study("back")
        elif kind == "strangers":  # (0.9.0) someone else's face while you're away: the time and how many, nothing more
            self._stranger_seen(int(f.get("n") or 0))
        elif kind == "others":
            nearby.set_others(self.app, "face", bool(f.get("on")))
        elif kind == "view":  # (0.8.13) how many faces, and whether the only one is yours: memory only, never an event
            nearby.set_view(self.app, int(f.get("faces") or 0), bool(f.get("owner_alone")))
            size = f.get("frame")  # (0.8.17) the frame's (width, height): sizes as shares of it
            nearby.set_facing(self.app, int(f.get("faces") or 0), self.close_facing(f.get("sizes") or [], size))
            looks = f.get("looks")  # (0.8.18) anyone's look, voice.listen.look_anyone
            nearby.set_look(self.app, self.looking(f.get("owner"), f.get("eyes"), size, looks))  # (0.8.17) look to talk
            if f.get("owner") is not None:  # (0.9.0) your face in view: you're here (core/here.py, words-free)
                here.owner_here(self.app, "face")
            self._break_signs(f.get("owner"), size)  # (0.9.0, face.breaks) looked up, stood up
            voice = self.app.modules.get("voice")
            if voice is not None and self.app.is_on("voice"):
                try:
                    voice.look_tick()  # at once, not at Voice's next second: a look should feel instant
                except Exception as e:
                    self._failed("telling Voice it's looked at", e)
        elif kind == "light":  # (0.9.0, face.light_sense) a frame's mean brightness: smoothed, in memory only
            self._light_seen(float(f.get("mean") or 0.0))
        elif kind == "learn":
            self.learn(f.get("e"))
        elif kind == "failed":
            self.app.events.emit("face_failed", **_event_safe(part=f.get("part"), error=f.get("error")))
        elif kind == "slow":
            self.slow = float(f.get("factor") or 1)
        elif kind == "people":
            self._hand_people(f.get("faces") or [])
        elif kind == "faces":  # every face's place and micro-movement: to open dashboards (the eye) and add-ons
            faces = [dict(x) for x in f.get("faces") or []]
            now = time.monotonic()
            if (not faces or now - self._faces_at >= FACES_EVERY_S) and self._page_in_sight():
                self._faces_at = now
                spk = {"speaker": True} if self.setting("track.speaker") else {}  # (0.9.0) the eye: who's talking
                self._push({"t": "face", "kind": "faces", "faces": faces, **spk})
            self._hand_faces(faces)
        elif kind == "seen":  # your face's place in the frame: to open dashboards only (the being's eyes), never kept
            now = time.monotonic()
            if f.get("px") and now - self._desk_at >= DESK_EVERY_S:  # its size only, for owner_desk_height
                self._desk_at = now
                self._desk.append((float(f["px"]), float(f.get("h") or 0)))
            if now - getattr(self, "_seen_at", 0.0) >= 0.2:  # at most 5 a second
                self._seen_at = now
                self._push(
                    {"t": "face", "kind": "face_seen", "x": f.get("x"), "y": f.get("y"), "w": f.get("w"), "owner": True}
                )

    # -------------------------------------------------------------------------------------- hooks for add-ons
    def watch_people(self, cb) -> object:
        """cb(faces) on the watcher's thread for each frame it looks at, while face.addons.watch is on: a list (empty
        when nobody's in view) of dicts with h_px, h (share of the frame's height), w, x, y (-1..1), yaw, det, and,
        when the face was big and clear enough to judge, who (owner, unsure, stranger), score and e (its numbers, a
        copy in memory: never keep them unasked). Keep it quick: it runs between frames. Returns the unsubscribe."""
        with self._hooks_lock:
            self._people.append(cb)

        def unsubscribe() -> None:
            with self._hooks_lock:
                if cb in self._people:
                    self._people.remove(cb)

        return unsubscribe

    def watch_faces(self, cb) -> object:
        """cb(faces) on the watcher's thread with every face in view while face.track.on and face.addons.watch are
        on and the camera is open: [{id, x, y, h, owner, m}] (watch.py's tracking: a track id, the centre -1..1, the
        height's share, the owner flag, micro-movement 0..1), an empty list once when the last one goes. No identity
        beyond the owner flag, no numbers. Faster with a hold whose reason says "track". Returns the unsubscribe."""
        with self._hooks_lock:
            self._faces.append(cb)

        def unsubscribe() -> None:
            with self._hooks_lock:
                if cb in self._faces:
                    self._faces.remove(cb)

        return unsubscribe

    def _faces_on(self) -> bool:
        return bool(self._faces) and bool(self.setting("addons.watch"))

    def _hand_faces(self, faces: list) -> None:
        if not self._faces_on():
            return
        with self._hooks_lock:
            cbs = list(self._faces)
        for cb in cbs:
            try:
                cb([dict(x) for x in faces])
            except Exception as e:
                self._failed("an add-on following faces", e)

    def _page_in_sight(self) -> bool:
        live = getattr(self.app, "live", None)
        try:
            return bool(live is not None and live.watched())
        except Exception:
            return False

    def _track_mode(self) -> int:
        """Who wants every face's place: TRACK_FAST for a dashboard in sight or a hold "to track", TRACK_SLOW for any
        other hold or an add-on following faces (at the recognition rate), else TRACK_OFF (nothing is worked out)."""
        if not self.setting("track.on"):
            return TRACK_OFF
        holds = self.holds()
        if self._page_in_sight() or any("track" in h.lower() for h in holds):
            return TRACK_FAST
        return TRACK_SLOW if holds or self._faces_on() else TRACK_OFF

    def _people_on(self) -> bool:
        return bool(self._people) and bool(self.setting("addons.watch"))

    def _hand_people(self, faces: list) -> None:
        if not self._people_on():
            return
        with self._hooks_lock:
            cbs = list(self._people)
        for cb in cbs:
            try:
                cb([dict(x) for x in faces])  # each its own copy: one add-on can't change what the next sees
            except Exception as e:
                self._failed("an add-on watching", e)

    def hold_watch(self, reason: str, seconds: float = HOLD_MAX_S, core: bool = False) -> bool:
        """Keep the camera looking (while you type too) for `seconds` (at most HOLD_MAX_S; call again to renew),
        until release_watch(reason). Every pause reason still applies first: off, not enrolled, /face pause, Kurooto
        paused, battery, a locked screen, a call, focus, night, an enrolment, a camera problem. False when
        face.addons.hold is off (nothing held). core=True: Kurooto's own hold (Voice's need_face), which that add-on
        switch doesn't cover; its own switch does."""
        if not core and not self.setting("addons.hold"):
            return False
        why = (str(reason or "").strip() or "an add-on")[:60]
        with self._hooks_lock:
            self._holds[why] = time.monotonic() + max(1.0, min(float(seconds or HOLD_MAX_S), HOLD_MAX_S))
            if core:
                self._core_holds.add(why)
            else:
                self._core_holds.discard(why)
        return True

    def release_watch(self, reason: str) -> None:
        why = (str(reason or "").strip() or "an add-on")[:60]
        with self._hooks_lock:
            self._holds.pop(why, None)
            self._core_holds.discard(why)

    def holds(self) -> list[str]:
        """The reasons the camera is held for now, add-ons' and Kurooto's own (shown on the card and in /face)."""
        on = bool(self.setting("addons.hold"))
        now = time.monotonic()
        with self._hooks_lock:
            for k in [k for k, until in self._holds.items() if until <= now]:
                del self._holds[k]
                self._core_holds.discard(k)
            return sorted(k for k in self._holds if on or k in self._core_holds)

    def close_facing(self, sizes: list, frame: tuple | None = None) -> int:
        """(voice.listen.need_face) How many of a frame's faces, given as (height in pixels, pose yaw), are close (at
        least voice.listen.face_near of your usual desk face height, the same idea as Curiosity's distance) and facing
        the camera (|yaw| within voice.listen.face_yaw_deg). Without a desk height yet, face.recognise.min_face_px
        stands in. A face without a yaw doesn't count. frame (0.8.17): the frame's (width, height); with it, heights are
        compared as shares of the frame (a sharper camera's pixels change nothing) and min_face_px is scaled."""
        if not sizes:
            return 0
        get = self.app.settings.get
        try:
            near = float(get("voice.listen.face_near", 0.5))
            limit = float(get("voice.listen.face_yaw_deg", 35))
        except (TypeError, ValueError):
            near, limit = 0.5, 35.0
        desk = self.owner_desk_height()
        fw, fh = (float(x or 0) for x in (frame or (0, 0)))
        if fh > 0 and desk and desk.get("h") and desk.get("measured"):  # an older enrolment's "h" is a guess
            base = float(desk["h"]) * fh * near
        elif desk and desk.get("px"):
            base = float(desk["px"]) * near
        else:
            base = float(self.setting("recognise.min_face_px") or 60) * (px_scale(fw, fh) if fw and fh else 1.0)
        n = 0
        for h_px, yaw in sizes:
            if yaw is not None and float(h_px) >= base and yaw_degrees(yaw) <= limit:
                n += 1
        return n

    def looking(self, owner, eyes=None, frame=None, looks=None) -> bool:
        """(voice.listen.look_to_talk, 0.8.17) Whether the owner's face in a frame, given as (height in pixels, pose
        yaw, pose pitch) or None, is looking at the camera. It must be close (as close_facing; frame: the frame's
        (width, height)). Then, with your eyes calibrated (gaze_calibration()), by the eyes: `eyes` (the irises'
        (h, v), gaze.py) and the head together within look_gaze_yaw_deg and look_gaze_pitch_deg of the lens, the head
        within face_yaw_deg (beyond it the irises can't be read well); a frame without eyes (a blink) keeps the last
        verdict for BLINK_HOLD_S. Otherwise by the head: turned at most look_yaw_deg from the camera and nodded at
        most look_pitch_deg from your enrolment's front step (none on record: the yaw alone), the nearest honest
        stand-in for eye contact YuNet's five points give, hence angles tighter than face_yaw_deg.
        (0.8.18, voice.listen.look_anyone) Or any other close face in `looks`, [(height, yaw, pitch, eyes)], judged the
        same way against your calibration and enrolment (theirs isn't known); a blink of theirs is no look."""
        if not self.app.settings.get("voice.listen.look_to_talk", True):
            return False
        if owner and self._looks_at(owner, eyes, frame, own=True):
            return True
        if looks and self.app.settings.get("voice.listen.look_anyone", True):
            return any(self._looks_at(lk[:3], lk[3] if len(lk) > 3 else None, frame, own=False) for lk in looks)
        return False

    def _looks_at(self, face, eyes, frame, own: bool) -> bool:
        """One face, (height, yaw, pitch), looking at the camera (looking()); own: the owner's (the blink hold and
        /voice's gaze line are his)."""
        h_px, yaw, pitch = (list(face) + [None, None])[:3]
        get = self.app.settings.get
        try:
            yaw_max = float(get("voice.listen.look_yaw_deg", 15))
            pitch_max = float(get("voice.listen.look_pitch_deg", 15))
        except (TypeError, ValueError):
            yaw_max = pitch_max = 15.0
        if yaw is None or h_px is None or not self.close_facing([(h_px, 0.0)], frame):
            return False
        cal = self.gaze_calibration()
        if cal is not None:
            return self._looking_by_eyes(yaw, pitch, eyes, cal, own)
        if abs(math.degrees(math.atan(float(yaw) / YAW_K)) - self.yaw_offset()) > yaw_max:  # 0 offset: yaw_degrees
            return False
        t = self._template_or_none()
        front = (t.baseline or {}).get("pitch") if t is not None else None
        if front is None:
            return True
        return pitch is not None and pitch_degrees(pitch, front) <= pitch_max

    def _looking_by_eyes(self, yaw: float, pitch, eyes, cal: dict, own: bool = True) -> bool:
        get = self.app.settings.get
        try:
            head_max = float(get("voice.listen.face_yaw_deg", 35))
            h_max = float(get("voice.listen.look_gaze_yaw_deg", 10))
            v_max = float(get("voice.listen.look_gaze_pitch_deg", 10))
        except (TypeError, ValueError):
            head_max, h_max, v_max = 35.0, 10.0, 10.0
        now = time.monotonic()
        if yaw_degrees(yaw) > head_max:
            if own:
                self._gaze_last = {"t": now, "looking": False, "why": "head turned away"}
            return False
        if not eyes or pitch is None:  # a blink, glare: the last verdict holds for a moment (the owner's only)
            if not own:
                return False
            last = self._gaze_last
            return bool(last.get("looking")) and now - float(last.get("t") or 0) <= BLINK_HOLD_S
        gh, gv = gaze_mod.angles(float(eyes[0]), float(eyes[1]), float(yaw), float(pitch), cal)
        gh -= self.yaw_offset()  # (0.9.0) the spot to look at, beside the lens the calibration looked into
        ok = abs(gh) <= h_max and abs(gv) <= v_max
        if not own:
            return ok
        self._gaze_last = {"t": now, "looking": ok, "yaw_deg": round(gh, 1), "pitch_deg": round(gv, 1)}
        return ok

    def yaw_offset(self) -> float:
        """(0.9.0, face.camera.yaw_offset_deg) How far beside the lens the spot to look at sits, in degrees (+: to your
        right), at most 30 either way: a camera whose lens is off the place you look at (a drawn eye beside a phone's
        punch hole) moves look to talk's centre there. An add-on with such a camera sets it while that camera is in
        use and clears it after."""
        try:
            off = float(self.setting("camera.yaw_offset_deg") or 0)
        except (TypeError, ValueError):
            return 0.0
        return max(-30.0, min(30.0, off)) if math.isfinite(off) else 0.0

    # ------------------------------------------------------------------------------- your eyes (0.8.17, gaze.py)
    def gaze_calibration(self) -> dict | None:
        """Your eyes' calibration when look to talk goes by the eyes: voice.listen.look_gaze on, the eye model here
        and a calibration in your template. Else None (the head's turn)."""
        if not self.app.settings.get("voice.listen.look_gaze", True) or not self.parts.has_model("iris"):
            return None
        t = self._template_or_none()
        cal = dict(t.gaze or {}) if t is not None else {}
        return cal if gaze_mod.valid(cal) else None

    def _look_listening(self) -> bool:
        """Voice listens for a look now: look_to_talk on and Voice's own hold on the camera."""
        if not self.app.settings.get("voice.listen.look_to_talk", True):
            return False
        return any(h in self._core_holds for h in self.holds())

    def _gaze_model(self):
        """The eye model, loaded once (a failure is retried after a minute); None when it can't be."""
        if self._gazer is None:
            if time.monotonic() - self._gazer_failed < 60:
                return None
            try:
                self.parts.importable()
                self._gazer = gaze_mod.opencv_gazer(self.parts.path(face_parts.IRIS))
            except Exception as e:
                self._gazer_failed = time.monotonic()
                self._failed("loading the eye model", e)
                return None
        return self._gazer

    def _gaze_now(self):
        """For the watcher: the eye model while Voice listens for a look and your eyes are calibrated, else None (no
        eyes are read: nothing runs that nobody uses)."""
        if not self._look_listening() or self.gaze_calibration() is None:
            return None
        return self._gaze_model()

    def gaze_status(self) -> dict:
        """What look to talk goes by, words and rounded degrees only: the switch, the model, the calibration's date,
        "eyes" or "head" and why, and the last frame's gaze (5 s fresh) for tuning look_gaze_*_deg."""
        on = bool(self.app.settings.get("voice.listen.look_gaze", True))
        model = self.parts.has_model("iris")
        t = self._template_or_none()
        cal = dict(t.gaze or {}) if t is not None else {}
        calibrated = gaze_mod.valid(cal)
        using = "eyes" if on and model and calibrated else "head"
        if using == "eyes":
            why = ""
        elif not on:
            why = "voice.listen.look_gaze is off"
        elif not model:
            why = "the eye model isn't here (Get the eye model on the Face page)"
        else:
            why = "your eyes aren't calibrated (Calibrate my eyes on the Face page)"
        last = self._gaze_last
        fresh = bool(last) and time.monotonic() - float(last.get("t") or 0) <= 5
        return {"on": on, "model": model, "calibrated": calibrated, "at": cal.get("at") if calibrated else None,
                "using": using, "why": why, "now": {k: v for k, v in last.items() if k != "t"} if fresh else None,
                "mb": EYE_MB}  # fmt: skip

    def gaze_start(self, cid=None) -> tuple[bool, dict]:
        """Calibrate my eyes: the camera opens (the guarded action camera.open, the Face page's button only) for
        about three seconds of you looking at its lens."""
        return self._start("gaze", cid)

    def _gaze_done(self, numbers: dict) -> None:
        t = self._template_or_none()
        if t is None:
            return
        t.gaze = {k: numbers[k] for k in (*gaze_mod.NUMBERS, "n", "at") if k in numbers}
        self._save(t)
        self._gaze_last = {}
        self.app.events.emit("face_gaze", calibrated=True)

    def gaze_clear(self) -> tuple[bool, str]:
        t = self._template_or_none()
        if t is None or not t.gaze:
            return False, "Your eyes aren't calibrated."
        t.gaze = {}
        self._save(t)
        self._gaze_last = {}
        self.app.events.emit("face_gaze", calibrated=False)
        return True, "Eye calibration cleared: look to talk goes by your head's turn."

    def gaze_setup(self, progress=print) -> tuple[bool, str]:
        """Get the eye model (MediaPipe Iris, 2.6 MB, pinned by sha256) into the face models' folder."""
        from kurooto.core.prereqs import Prereqs

        free = lambda: Prereqs.free_gb(self.parts.models_dir.parent)  # noqa: E731
        ok, msg = self.parts.install(face_parts.EYES, progress, free_gb=free)
        return ok, ("The eye model is here: now Calibrate my eyes." if ok else msg)

    def _held_now(self) -> bool:
        return bool(self.holds())

    def owner_desk_height(self) -> dict | None:
        """How tall your face usually is at the desk: {"px", "h" (share of the frame's height), "n", "from"}: the
        running median of your recent sightings ("seen", from DESK_MIN of them), else the enrolment's front step
        ("enrolment": its share of the frame, measured since 0.8.17; an older one's pixels over face.camera.height),
        else None. "px" is in the pixels of the frames it was seen in: after the camera's resolution changes, "h"
        is the one to compare (close_facing does). Sizes only, in memory."""
        if len(self._desk) >= DESK_MIN:
            import statistics

            px = statistics.median(p for p, _ in self._desk)
            hs = [h for _, h in self._desk if h]
            return {"px": round(px, 1), "h": round(statistics.median(hs), 4) if hs else None, "n": len(self._desk),
                    "from": "seen", "measured": bool(hs)}  # fmt: skip
        t = self._template_or_none()
        b = (t.baseline or {}) if t is not None else {}
        base = float(b.get("height") or 0)
        if base <= 0:
            return None
        if b.get("share"):
            return {"px": round(base, 1), "h": round(float(b["share"]), 4), "n": 0, "from": "enrolment",
                    "measured": True}  # fmt: skip
        fh = float(self.setting("camera.height") or 480)
        return {"px": round(base, 1), "h": round(base / fh, 4) if fh else None, "n": 0, "from": "enrolment"}

    # ------------------------------------------------------------------------------------------- arriving
    def away_now(self) -> bool:
        return bool(self.setting("away.on") and self.watcher is not None and self.watcher.away)

    def _break_signs(self, owner, frame) -> None:
        """(0.9.0, face.breaks) Natural breaks for Brain's door, from what this frame shows of you: you looked at the
        camera for LOOK_BREAK_S (one per run of looks, core/nearby.py's look times) -> face_looked; your face under
        STOOD_RATIO of its usual desk height (owner_desk_height, measured shares only) -> face_stood, once until it's
        back over STOOD_BACK. Kinds only into the event log; nothing about the face."""
        if not self.setting("breaks"):
            return
        try:
            since, last = nearby.look(self.app)
            if since is not None and last is not None and last - since >= LOOK_BREAK_S and since != self._break_look:
                self._break_look = since
                self.app.events.emit("face_looked")
            desk = self.owner_desk_height()
            fh = float((frame or (0, 0))[1] or 0)
            if owner is None or fh <= 0 or not desk or not desk.get("h") or not desk.get("measured"):
                return
            share = float(owner[0]) / fh
            if not self._stood and share < STOOD_RATIO * float(desk["h"]):
                self._stood = True
                self.app.events.emit("face_stood")
            elif self._stood and share >= STOOD_BACK * float(desk["h"]):
                self._stood = False
        except Exception as e:
            self._failed("break signs", e)

    def here(self) -> bool:
        """(0.9.0, core/here.py) Your voice or the dashboard says you're here: Face presence's away ends without a
        greeting. True when it was away."""
        w = self.watcher
        return bool(w is not None and self.setting("away.on") and w.here())

    def desk_seen_at(self) -> float | None:
        """(0.8.18, mind.sleep.desk_holds) When you were last at this computer by Face presence (your face, or your
        keyboard and mouse while it watches) as time.time(); None when it isn't watching or you've stepped away."""
        w = self.watcher
        if w is None or w.away or not self.app.is_on(self.id):
            return None
        return time.time() - max(0.0, w.clock() - w.present_at)

    # --------------------------------------------------------------------- your phone's places (0.9.0)
    def phone_place(self, event: str) -> bool:
        """(face.away.use_places) Brain's phone senses: the phone left a place you saved ("leave": you're away at once,
        as if no sign of you for face.away.after_min, so face.away.hold_* apply) or arrived at one (nothing more: your
        face or your keyboard says you're back). True when it marked you away."""
        if event != "leave" or not self.setting("away.on") or not self.setting("away.use_places"):
            return False
        w = self.watcher
        if w is None or w.away:
            return False
        w.mark_away()
        return True

    def _phone_out(self) -> bool:
        """(face.away.places_close_camera) The camera stays closed while the phone is out (core/nearby.py)."""
        if not self.setting("away.use_places") or not self.setting("away.places_close_camera"):
            return False
        return nearby.phone_out(self.app) is not None

    def left_at(self) -> dt.datetime | None:
        """(0.9.0) When you stepped away from the desk, while you're away (face.away.on); else None."""
        w = self.watcher
        if not self.away_now() or w is None or w.left_at is None:
            return None
        return dt.datetime.fromtimestamp(time.time() - max(0.0, w.clock() - w.left_at))

    def _away_block(self, t: dt.datetime):
        if not self.setting("away.hold_calls") or not self.away_now():
            return None
        w = self.watcher
        ago = (w.clock() - w.left_at) if w is not None and w.left_at is not None else 0.0
        left = dt.datetime.fromtimestamp(time.time() - ago)
        until = left + dt.timedelta(minutes=float(self.setting("away.hold_max_min") or 60))
        return ("you've stepped away from your desk", until) if t < until else None

    def hold_desktop(self, title: str, text: str, urgent: bool = False, key: tuple | None = None) -> None:
        """key: (map_kind, map_ref, button data) of what it's about, so drop_held can take it back once that's dealt
        with elsewhere (0.9.0, notify.desktop_retract)."""
        self.held.append((title, text, urgent, key))

    def drop_held(self, gone) -> int:
        """Pop-ups held while you're away whose question was dealt with meanwhile (gone(key) is True) don't show."""
        keep = [h for h in self.held if not (h[3] is not None and gone(h[3]))]
        n = len(self.held) - len(keep)
        if n:
            self.held.clear()
            self.held.extend(keep)
        return n

    def flush_desktop(self) -> int:
        from kurooto.core import desktop

        n = 0
        while self.held:
            title, text, urgent = self.held.popleft()[:3]
            try:
                desktop.notify(title, text, urgent=urgent)
                n += 1
            except Exception:
                pass
        return n

    # ---------------------------------------------------------------- add-ons and the greeting (0.9.0)
    def greet_part(self, name: str, line) -> object:
        """(face.greet.addons) line(): one short sentence the add-on wants said in the next greeting, or None. Called
        on the greeting's thread, only with nobody else in view; at most ADDON_LINE_MAX characters are said, after
        every built-in part, so it's the first to go at the length limit. greet_carried(name, since) says whether it
        was said. Returns the unsubscribe."""
        key = re.sub(r"[^a-z0-9_-]", "", str(name or "").lower())[:30] or "addon"
        with self._hooks_lock:
            self._greet_parts[key] = line

        def unsubscribe() -> None:
            with self._hooks_lock:
                if self._greet_parts.get(key) is line:
                    del self._greet_parts[key]

        return unsubscribe

    def greet_carried(self, name: str, since: float = 0.0) -> bool:
        """Whether a greeting said this add-on's line at or after `since` (time.time()): if not, the add-on says it
        its own way, as before."""
        key = re.sub(r"[^a-z0-9_-]", "", str(name or "").lower())[:30] or "addon"
        return self._carried.get(key, -1.0) >= since

    def _addon_lines(self) -> list[tuple[str, str]]:
        if not self.setting("greet.addons"):
            return []
        with self._hooks_lock:
            parts = list(self._greet_parts.items())
        out = []
        for key, line in parts:
            try:
                text = " ".join(str(line() or "").split())[:ADDON_LINE_MAX]  # type: ignore[operator]
            except Exception as e:
                self._failed("an add-on's greeting line", e)
                continue
            if text:
                out.append((f"addon:{key}", text if text[-1] in ".?!" else text + "."))
        return out

    def known_guests(self, check) -> object:
        """(face.addons.known_guests) check() -> True when everyone in view besides you is someone the add-on knows. A
        yes or no only: Face presence never learns who, and nothing of it is kept. Returns the unsubscribe."""
        with self._hooks_lock:
            self._known.append(check)

        def unsubscribe() -> None:
            with self._hooks_lock:
                if check in self._known:
                    self._known.remove(check)

        return unsubscribe

    def known_guest(self) -> bool:
        """An add-on says everyone else in view is known (face.addons.known_guests); False with none."""
        if not self.setting("addons.known_guests"):
            return False
        with self._hooks_lock:
            checks = list(self._known)
        for check in checks:
            try:
                if check() is True:
                    return True
            except Exception as e:
                self._failed("an add-on's known guests", e)
        return False

    # ------------------------------------------------------------------- the room's light (0.9.0)
    def _light_seen(self, mean: float) -> None:
        """(face.light_sense) One frame's mean brightness (0..255) into a smoothed level (0..1, LIGHT_ALPHA)."""
        if not self.setting("light_sense"):
            self._light = None
            return
        x = max(0.0, min(1.0, mean / 255.0))
        old = self._light[0] if self._light is not None and time.monotonic() - self._light[1] <= LIGHT_STALE_S else x
        self._light = (old + LIGHT_ALPHA * (x - old), time.monotonic())

    def light_level(self) -> float | None:
        """(face.light_sense) The room's light as the camera saw it lately: 0 (dark) to 1 (blown out), smoothed, or
        None (off, or the camera hasn't looked for LIGHT_STALE_S). A webcam adjusts its exposure, so this is a rough
        dark-to-lit signal, not lux: whoever uses it maps it onto its own scale. A number only, never kept or sent."""
        if self._light is None or not self.setting("light_sense") or not self.app.is_on(self.id):
            return None
        level, at = self._light
        return round(level, 3) if time.monotonic() - at <= LIGHT_STALE_S else None

    # ------------------------------------------------------------- someone else while you're away (0.9.0)
    def _stranger_seen(self, n: int) -> None:
        """(face.away.report_others) A frame with n faces judged not yours while you were away: the minute and the
        most faces in it, in memory only (OTHERS_MAX minutes, the oldest go first). Never a picture, numbers or who."""
        if n <= 0 or not self.setting("away.report_others"):
            return
        minute = int(time.time() // 60)
        self._others_away[minute] = max(n, self._others_away.get(minute, 0))
        while len(self._others_away) > OTHERS_MAX:
            del self._others_away[min(self._others_away)]

    def report_others(self) -> bool:
        """You're back (or arrived): one message with the times someone else was in view while you were away, then
        they're forgotten. Nothing when the switch is off (what was noted goes too) or nobody was seen."""
        seen, self._others_away = self._others_away, {}
        if not seen or not self.setting("away.report_others"):
            return False
        times = []
        for minute in sorted(seen)[:OTHERS_SAID]:
            n = seen[minute]
            times.append(f"{dt.datetime.fromtimestamp(minute * 60):%H:%M}" + (f" ({n} faces)" if n > 1 else ""))
        more = len(seen) - len(times)
        said = ", ".join(times[:-1]) + (" and " if len(times) > 1 else "") + times[-1]
        said += f", and {more} more minute{'s' if more != 1 else ''}" if more > 0 else ""
        self.app.notify(
            f"While you were away, Face presence saw someone else at your desk at {said}. It keeps only these times: "
            "no picture, and it doesn't know who.",
            kind="info",
            why="face.away.others",
            setting="face.away.report_others",
            about="someone at your desk",
        )
        self.app.events.emit("face_away_others", **_event_safe(count=len(seen)))
        return True

    def _arrived(self, away_min: int, others: bool) -> None:
        nearby.set_phone_out(self.app, False)  # (0.9.0) your face is here: the phone's "out" is over
        self.app.events.emit("face_arrived", **_event_safe(away_min=away_min))
        self.flush_desktop()
        self.report_others()
        threading.Thread(target=self.greet, args=(others,), name="face-greet", daemon=True).start()

    def greet(self, others: bool = False) -> bool:
        from kurooto.core.clock import now
        from kurooto.modules.face import greet as g

        t = now()
        ok, why = g.may_greet(self.app, self, others, t)
        if not ok:
            self.app.events.emit("face_greet_skipped", **_event_safe(why=why))
            return False
        talk = bool(self.setting("greet.talk")) and not others
        with_others = str(self.setting("greet.with_others") or "skip")
        if others and with_others == "skip":  # (0.9.0) may_greet let it through: everyone else here is known
            with_others = "short"
        extra = self._addon_lines() if not others and not nearby.others(self.app) else []
        text, parts = g.compose(
            [p for p in (self.setting("greet.say") or []) if p in SAY_PARTS],
            self._today(),
            self._waiting(),
            self._deadline(t),
            self._held(),
            others,
            t,
            first_today=self.greets().get("day") != t.date().isoformat(),
            with_others=with_others,
            talk=talk,
            extra=extra,
            name="" if others or nearby.others(self.app) else persona.address(self.app),  # (0.9.0) alone in view only
            answers=self._held_answers(),
        )
        text = persona.template(self.app, text)  # (0.9.0, persona.templates) the avoid line, as punctuation
        v = self.app.modules["voice"]
        spoken, opened = v.greet(text, float(self.setting("greet.listen_s") or 12), talk=talk)
        if not spoken:
            self.app.events.emit("face_greet_skipped", **_event_safe(why=str(opened)))
            return False
        day = t.date().isoformat()
        gr = self.greets()
        gr.update({"day": day, "n": (int(gr.get("n") or 0) if gr.get("day") == day else 0) + 1, "last": t.timestamp()})
        self._write_status()
        for p in parts:  # (0.9.0, greet.addons) which add-ons' lines went out, for greet_carried()
            if p.startswith("addon:"):
                self._carried[p[6:]] = time.time()
        self.app.events.emit("face_greeted", **_event_safe(parts=parts, talk=opened == "talk"))
        self._record_greeting(parts, opened == "talk")
        if opened == "talk" and text.endswith("Want to go through them?"):  # (0.9.0) a yes starts it (walkthrough.py)
            from kurooto.core import walkthrough

            walkthrough.offered(self.app)
        return True

    # ----------------------------------------------------------------------- the greeting's records (0.9.0)
    @property
    def tunable(self) -> dict:
        """(face.greet.records) What the nightly look back (modules/retro.py) may propose from the greetings' outcomes:
        the gap between greetings only, and only with a tap."""
        if not self.setting("greet.records"):
            return {}
        return {"face.greet.gap_min": "minutes at least between two desk greetings (number)"}

    def _record_greeting(self, parts: list[str], talk: bool) -> None:
        """A decision record for a greeting said (mind/records.py; nothing with Brain off): the parts' names, never
        the words or the frame. With the conversation open it expects an answer within GREET_EXPECT_H, closed by
        greet_closed() when the conversation does (or as missed by records.sweep)."""
        if not self.setting("greet.records"):
            return
        from types import SimpleNamespace

        from kurooto.mind import records

        try:
            expect = {"what": "reply", "within_h": GREET_EXPECT_H} if talk else None
            said = ", ".join(parts) or "the opening only"
            rid = records.decide(self.app, "speak:face.greet", scored_reason=f"a greeting at the desk: {said}",
                                 source="rules", expect=expect)  # fmt: skip
            if not rid:
                return
            msg = SimpleNamespace(rid=rid, why="face.greet", kind="spoken", buttons=[], map_kind="", tail="")
            records.track(self.app, rid, msg, expect)
            self._greet_rec = rid if talk else ""
        except Exception as e:
            self._failed("recording the greeting", e)

    def greet_closed(self, answered: bool) -> None:
        """(face.greet.records) Voice: the greeting's conversation closed, answered (a turn in it) or not."""
        rid, self._greet_rec = self._greet_rec, ""
        if not rid:
            return
        from kurooto.mind import records

        result = "replied" if answered else "missed"
        records.outcome(self.app, rid, result, 1.0 if answered else 0.0)
        self.app.events.emit("face_greet_outcome", **_event_safe(result=result))

    def _held_answers(self) -> int:
        """(0.9.0) How many answers Voice didn't read while you were away (a count only)."""
        v = self.app.modules.get("voice")
        try:
            return len(v.held_answers) if v is not None and self.app.is_on("voice") else 0
        except Exception:
            return 0

    def _write_status(self) -> None:
        st = self.store.status()
        if st:
            jsave(self.store.status_file, {**st, "greets": self._greets})

    def _today(self) -> list[dict]:
        from kurooto.web.live import today_items

        try:
            return today_items(self.app).get("items") or []
        except Exception:
            return []

    def _waiting(self) -> tuple[int, int]:
        try:
            return len(self.app.ask.pending(kind="question")), len(self.app.ask.pending(kind="approval"))
        except Exception:
            return 0, 0

    def _deadline(self, t: dt.datetime):
        d = self.app.modules.get("deadlines")
        if d is None or not self.app.is_on("deadlines"):
            return None
        try:
            for _i, it, h in d.upcoming(24):
                if h >= 0:
                    return str(it.get("title") or ""), dt.datetime.fromisoformat(it["due"])
        except Exception:
            return None
        return None

    def _held(self) -> int:
        try:
            return len(self.app.calm.held())
        except Exception:
            return 0

    # -------------------------------------------------------------------------------------------- learning
    def learn(self, e) -> bool:
        if not e or not self.setting("learn.on"):
            return False
        t = self._tpl_live()
        if t is None or not t.learnable(e, float(self.setting("learn.margin") or 0.08)):
            return False
        every = float(self.setting("learn.every_h") or 6) * 3600
        if t.learned and time.time() - t.learned[-1].at < every:
            return False
        n = t.learn(e, time.time(), int(self.setting("learn.max") or 30))
        self._retrain(t)
        self.app.events.emit("face_learned", **_event_safe(count=n))
        return True

    def learn_from_voice(self) -> bool:
        """(face.learn.from_voice, under face.learn.on) Voice ID was sure a turn was yours: with exactly one face in
        view, yours, nobody else nearby and a confident clear frame of it from the last few seconds, learn() from it
        (its spacing, cap and Undo apply). The voice confirms the face, as typing after an arrival does."""
        if not self.setting("learn.on") or not self.setting("learn.from_voice") or nearby.others(self.app):
            return False
        if nearby.view(self.app) != (1, True):
            return False
        w = self.watcher
        e = w.voice_candidate() if w is not None else None
        return self.learn(e) if e else False

    def learn_undo(self) -> str:
        t = self._template_or_none()
        if t is None or not t.undo_learn():
            return "Nothing learned to undo."
        self._retrain(t)
        return f"Undone: {len(t.learned)} learned sample{'s' if len(t.learned) != 1 else ''} left."

    def learn_forget(self) -> str:
        t = self._template_or_none()
        if t is None:
            return "There's no face model."
        n = t.forget_learned()
        self._retrain(t)
        return f"Forgot {n} learned sample{'s' if n != 1 else ''}; your enrolled samples stay."

    def _retrain(self, t: Template) -> dict:
        imp = self.impostors()
        rep = t.retrain(
            imp,
            face_parts.SFACE_SHA if imp else "",
            str(self.setting("recognise.strictness") or "normal"),
            float(self.setting("recognise.threshold") or 0),
            TARGETS,
        )
        self._save(t)
        return rep

    def retrain(self) -> tuple[bool, dict | str]:
        t = self._template_or_none()
        if t is None:
            return False, "There's no face model to retrain (or its key can't be read)."
        rep = self._retrain(t)
        self.app.events.emit("face_trained", **_event_safe(samples=len(t.samples), grade=t.grade))
        return True, rep

    def set_strictness(self, level: str) -> tuple[bool, dict | str]:
        if level not in STRICTNESS:
            return False, "Strictness is loose, normal or strict."
        self.app.settings.set("face.recognise.strictness", level)
        return self.retrain() if self.enrolled() else (True, "Saved.")

    # ----------------------------------------------------------------------------------------- the sessions
    def _refuse(self) -> str:
        if not self.app.is_on(self.id):
            return "Face presence is off: turn it on first (Features)."
        if self.parts.missing(self.wants()):
            return "Set Face presence up first (it downloads about 0.18 GB)."
        if self._on_call():
            return "Not while you're on a call."
        if self.session is not None and self.session.state != "ended":
            return "Another enrolment or test is open: finish or discard it first."
        return ""

    def _start(self, kind: str, cid, mode: str = "new", label: str = "", via: str = "page") -> tuple[bool, dict]:
        why = self._refuse()
        if why:
            return False, {"message": why}
        camera = self.make_camera()
        try:
            if camera.busy():
                return False, {"message": "The camera is in use by another program: close it, then try again."}
        except Exception:
            pass
        plan = None
        t = None
        if kind == "enrol":
            if mode == "add":
                t = self._template_or_none()
                if t is None:
                    return False, {"message": "There's no face model to add to: Start enrolling first."}
                have: dict[str, int] = {}
                for s in t.samples:
                    have[s.step] = have.get(s.step, 0) + 1
                px = int(self.setting("recognise.min_face_px") or 60)
                plan = Enrolment(px, have, t.baseline, [c for _, c in t.cents])
            else:
                plan = Enrolment(int(self.setting("recognise.min_face_px") or 60))
        elif kind == "look":
            t = self._template_or_none()
            if t is None:
                return False, {"message": "Your face model's key can't be read just now: nothing was started."}
            mine = centroids([x for x in t.samples if not is_look(x.step)])  # your enrolment's, never another look's
            px = int(self.setting("recognise.min_face_px") or 60)
            plan = Look(px, t.baseline, lambda e: score(e, mine), t.lo, label)
        else:
            t = self._template_or_none()
            if t is None:
                return False, {"message": "Enrol first: there's nothing to test yet."}
            if kind == "gaze" and not self.parts.has_model("iris"):
                return False, {"message": f"Get the eye model first ({EYE_MB:g} MB)."}
        try:
            det, emb, frames = self._vision_objects(4 if kind in ("enrol", "look") else 1)
        except Exception as e:
            self._failed("loading the models", e)
            return False, {"message": f"The models didn't load: {type(e).__name__}."}
        gazer = self._gaze_model() if kind == "gaze" else None
        if kind == "gaze" and gazer is None:
            return False, {"message": "The eye model didn't load: try again in a minute."}
        cid_i = int(cid) if str(cid or "").isdigit() else None
        sess = Session(
            kind,
            cid_i,
            camera,
            Vision(det, emb, frames, gazer),
            push=lambda m: self._push(m, cid_i),
            plan=plan,
            classify=self._classify if kind in ("test", "gaze") else None,
            thresholds=(t.hi, t.lo) if (t is not None and kind == "test") else (0.0, 0.0),
            on_mark=self._test_result if kind == "test" else None,
            on_gaze=self._gaze_done if kind == "gaze" else None,
            on_look=(lambda got, why: self._look_done(got, why, label, via)) if kind == "look" else None,
            keep=self._look_keep if kind == "look" else None,
            preview=kind != "look" or via == "page",
        )
        self.session = sess
        if self.watcher is not None:
            self.watcher.release()

        def before():
            end = time.monotonic() + 3
            while self.watcher is not None and self.watcher.camera_open and time.monotonic() < end:
                time.sleep(0.05)
            try:
                sess.open_camera()
            except Exception as e:
                from kurooto.modules.face.camera import CameraError

                why = e.why if isinstance(e, CameraError) else type(e).__name__
                sess.end(f"the camera didn't open ({why})")

        sess.start_thread(before)
        out = {"session": sess.id, "stage": STAGES[kind]}
        if plan is not None:
            out["plan"] = plan.progress()
        return True, out

    def enrol_start(self, cid=None, mode: str = "new") -> tuple[bool, dict]:
        return self._start("enrol", cid, "add" if mode == "add" else "new")

    def test_start(self, cid=None) -> tuple[bool, dict]:
        return self._start("test", cid)

    # ------------------------------------------------------------------------------------------- looks (0.9.0)
    def looks(self) -> list[dict]:
        """Your looks: {id, label, at, n}; [] when there's no model or its key can't be read."""
        t = self._template_or_none()
        return [dict(x) for x in t.looks] if t is not None else []

    def look_start(self, label: str = "", cid=None, via: str = "page") -> tuple[bool, dict]:
        """Add this look: the Face page's button (via "page"), /face add-look ("chat": the result comes as a message)
        or `kurooto face add-look` ("terminal": it asks look_status()). Only ever started by you."""
        if not self.setting("looks.on"):
            return False, {"message": "Add this look is off (face.looks.on in Settings)."}
        why = self._refuse()
        if why:
            return False, {"message": why}
        if not self.enrolled() or self.reenrol_needed():
            return False, {"message": "Enrol first on the Face page: a look is added to your face model."}
        t = self._template_or_none()
        if t is None:
            return False, {"message": "Your face model's key can't be read just now: nothing was started."}
        if len(t.looks) >= LOOKS_MAX:
            return False, {"message": f"You have {LOOKS_MAX} looks, the most it keeps: remove one on the Face page."}
        shown = "".join(c if c.isprintable() else " " for c in str(label or ""))  # a newline is a space
        label = re.sub(r"\s+", " ", shown).strip()[:LABEL_MAX]
        label = label or f"Look {len(t.looks) + 1}"
        self._look_last = {}
        return self._start("look", cid, label=label, via=via)

    def _look_keep(self) -> str:
        return "" if self.setting("looks.on") else "face.looks.on was turned off"

    def _look_done(self, got: list, why: str, label: str, via: str) -> dict:
        """The look's end (on its session's thread): checked by model.look_check, then added and retrained, or not."""
        ok, n = False, len(got)
        if why:
            msg = "Add this look stopped" + (f": {why}" if why != "stopped" else "") + ". Nothing was added."
            result = "stopped"
        elif n < LOOK_MIN:
            msg = (
                f"Only {n} clear frame{'s' if n != 1 else ''} of you in {LOOK_S:g} seconds (a look needs {LOOK_MIN}): "
                "nothing was added. Try again alone, facing the camera, in steady light."
            )
            result = "too few"
        else:
            with self._tpl_lock:
                t = self._template_or_none()
                if t is None or not self.enrolled():
                    msg, result = "Your face model isn't there any more: nothing was added.", "stopped"
                elif len(t.looks) >= LOOKS_MAX:
                    msg, result = f"You have {LOOKS_MAX} looks already: nothing was added.", "refused"
                else:
                    imp = self.impostors()
                    reason = look_check(
                        t.samples,
                        t.learned,
                        got,
                        imp,
                        str(self.setting("recognise.strictness") or "normal"),
                        float(self.setting("recognise.threshold") or 0),
                    )
                    if reason:
                        msg, result = f'"{label}" wasn\'t added: {reason}.', "refused"
                    else:
                        self._previous = t.to_payload()  # Undo the last training puts it back (this run only)
                        t.add_look(label, got, time.time())
                        rep = self._retrain(t)
                        ok, result = True, "added"
                        msg = (
                            f'Added "{label}" ({n} samples) to your face model: recognised in '
                            f"{round(float(rep.get('tar') or 0) * 100)}% of held-out samples, grade {t.grade}. Remove "
                            "it on the Face page any time."
                        )
        got.clear()  # the numbers live only in the sealed template now (or nowhere)
        self.app.events.emit("face_look", **_event_safe(result=result, count=len(self.looks())))
        self._look_last = {"at": time.time(), "ok": ok, "message": msg}
        if via == "chat":
            try:
                self.app.notify(msg, kind="result", why="face.look")
            except Exception as e:
                self._failed("telling you about the look", e)
        return {"ok": ok, "message": msg}

    def look_remove(self, lid: str) -> tuple[bool, str]:
        """Takes a look and its samples out of your template, then retrains (Undo the last training puts it back)."""
        with self._tpl_lock:
            t = self._template_or_none()
            if t is None:
                return False, "Your face model's key can't be read just now."
            before = t.to_payload()
            look = t.remove_look(str(lid or ""))
            if look is None:
                return False, "There's no such look."
            self._previous = before
            self._retrain(t)
        self.app.events.emit("face_look", **_event_safe(result="removed", count=len(t.looks)))
        return True, f'Removed "{look.get("label") or "the look"}": its {look.get("n", 0)} samples are gone.'

    def look_status(self) -> dict:
        """For `kurooto face add-look`: the look being taken (counts) and the last one's result."""
        s = self.session
        live = None
        if s is not None and s.kind == "look" and s.state != "ended" and s.plan is not None:
            live = {"state": s.state, "got": s.plan.total(), "need": LOOK_TARGET}
        return {"session": live, "last": dict(self._look_last)}

    def _session(self, sid: str) -> Session | None:
        s = self.session
        return s if s is not None and s.id == str(sid or "") and s.state != "ended" else None

    def enrol_step(self, sid: str, action: str) -> tuple[bool, dict]:
        s = self._session(sid)
        if s is None or s.plan is None:
            return False, {"message": "That enrolment has ended."}
        return True, {"message": s.plan.act(action), "plan": s.plan.progress()}

    def session_pause(self, sid: str, on: bool) -> tuple[bool, dict]:
        s = self._session(sid)
        if s is None:
            return False, {"message": "That session has ended."}
        if on:
            s.pause("paused by you")
        else:
            try:
                s.resume()
            except Exception as e:
                return False, {"message": f"The camera didn't open: {type(e).__name__}."}
        return True, {"state": s.state}

    def discard(self, sid: str) -> tuple[bool, dict]:
        s = self._session(sid)
        if s is None:
            return False, {"message": "That session has ended."}
        s.end("discarded")
        self.session = None
        return True, {"message": "Discarded: nothing was kept."}

    def train(self, sid: str) -> tuple[bool, dict]:
        s = self._session(sid)
        if s is None or s.plan is None or s.kind != "enrol":
            return False, {"message": "That enrolment has ended (samples are kept for 30 minutes)."}
        plan = s.plan
        add = bool(plan.have)
        if not add and not plan.ready():
            return False, {"message": f"Finish the first five steps first ({MINIMUM} samples)."}
        if add and not plan.samples:
            return False, {"message": "No new samples yet."}
        new = list(plan.samples)
        before = self._template_or_none()
        if add:
            t = before
            if t is None:
                return False, {"message": "The face model's key can't be read just now."}
        else:
            if before is None and not self.store.readable():  # never a new model over one whose key can't be read
                return False, {"message": "The face model's key can't be read just now."}
            t = Template(face_parts.SFACE_SHA)
        self._previous = before.to_payload() if before is not None else None  # Undo (in memory, this run only)
        t.samples += new
        if plan.baseline:
            t.baseline = {**t.baseline, **plan.baseline}
        rep = self._retrain(t)
        s.end("trained")  # the in-memory samples go; they live only in the sealed template now
        self.session = None
        del new
        kind = "face_trained" if add else "face_enrolled"
        self.app.events.emit(kind, **_event_safe(samples=len(t.samples), grade=t.grade))
        return True, {"report": rep, "stage": "manage", "can_undo": self._previous is not None}

    def undo_train(self) -> tuple[bool, str]:
        """Back to the face model before the last training (Add samples or Start over), within this run of Kurooto."""
        with self._tpl_lock:
            prev, self._previous = self._previous, None
            if prev is None:
                return False, "Nothing to undo."
            t = Template.from_payload(prev)
            self._save(t)
        self.app.events.emit("face_trained", **_event_safe(samples=len(t.samples), grade=t.grade))
        return True, f"Back to your previous face model ({len(t.samples)} samples, {t.grade or '?'})."

    def test_mark(self, sid: str, who: str) -> tuple[bool, dict]:
        s = self._session(sid)
        if s is None or s.kind != "test":
            return False, {"message": "That test has ended."}
        return True, {"message": s.mark(who)}

    def test_stop(self, sid: str) -> tuple[bool, dict]:
        s = self._session(sid)
        if s is None:
            return True, {"message": "Ended."}
        s.end("stopped")
        self.session = None
        return True, {"message": "Test ended; the camera is off."}

    def _test_result(self, who: str, res: dict) -> None:
        t = self._template_or_none()
        if t is None:
            return
        last = dict(t.last_test or {})
        last["at"] = round(time.time())
        last["me" if who == "me" else "other"] = res
        t.last_test = last
        self._save(t)

    def frame(self, sid: str) -> bytes | None:
        s = self._session(sid)
        return s.jpeg() if s is not None else None

    def end_session(self, why: str) -> None:
        s, self.session = self.session, None
        if s is not None:
            s.end(why)

    # --------------------------------------------------------------------------------------------- forgetting
    def forget(self) -> str:
        """Every way to forget comes here: the session closes, the camera closes, then the key, the template and its
        status go (TemplateStore.forget: the key first)."""
        self.end_session("forgotten")
        if self.watcher is not None:
            self.watcher.release()
        with self._tpl_lock:
            self._tpl = None
            self._previous = None
            self._desk.clear()
            self._gaze_last = {}
            self._others_away = {}
            gone = self.store.forget()
        self._greets = {}
        self.app.events.emit("face_forgotten")
        if not gone:
            return "There was no face model to forget."
        return "Forgot your face model: the key, the template and its status. Nothing of it remains on this computer."

    def turned_off(self) -> None:
        """Turned off: what's kept stays; one message offers to delete it."""
        if not self.store.exists():
            return
        asked = int(time.time())
        self.app.notify(
            "Face presence is off. Your face model (numbers that describe your face, encrypted, never a picture) stays "
            "on this computer until you delete it; turning it on again uses it.",
            kind="result",
            why="face.off",
            buttons=[[("Delete my face data", f"fce:{asked}:forget"), ("Keep it", "fce:0:keep")]],
        )

    # ------------------------------------------------------------------------------------------------ running
    def start(self) -> None:
        self.app.availability.blockers["face:away"] = self._away_block

    def shutdown(self) -> None:
        """Kurooto stopping: any enrolment or test ends (its samples dropped) and the camera closes."""
        self.end_session("stopped")
        self._halt.set()
        if self.watcher is not None:
            self.watcher.release()

    def stop(self) -> None:
        super().stop()
        self.app.availability.blockers.pop("face:away", None)
        self.flush_desktop()  # pop-ups held while you were away show now: no "back" will come to show them
        self.end_session("turned off")
        self._halt.set()
        if self.watcher is not None:
            self.watcher.release()
        nearby.set_others(self.app, "face", False)

    # -------------------------------------------------------------------------------------------- showing it
    # --------------------------------------------------------------------------------- time at the desk
    DESK_KINDS = {"face_arrived": True, "face_back": True, "face_left": False}

    def desk_spans(self, lo: dt.datetime, hi: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """(0.9.0) Your stretches at the desk in [lo, hi), from Face presence's arrivals and departures (times only;
        a stretch still going ends now). Never what it saw, only when you came and went."""
        from kurooto.core.clock import now

        end = min(hi, now())
        marks = []
        for e in self.app.events.tail(5000, kinds=set(self.DESK_KINDS)):
            try:
                t = dt.datetime.fromisoformat(e["ts"]).replace(tzinfo=None)
            except (KeyError, ValueError):
                continue
            if t < end:
                marks.append((t, self.DESK_KINDS[e["kind"]]))
        spans, start, here = [], None, False
        for t, came in marks:
            if t < lo:
                here = came  # where you were when the window opened
                continue
            if here and start is None:
                start = lo
            if came and start is None:
                start = t
            elif not came and start is not None:
                spans.append((start, t))
                start = None
            here = came
        if here and start is None and marks and marks[-1][0] < lo:
            start = lo
        if start is not None and end > start:
            spans.append((start, end))
        return [(a, b) for a, b in spans if b > a]

    def desk_line(self, lo: dt.datetime, hi: dt.datetime, when: str = "today") -> str:
        """(face.desk_time) "6 h at the desk today, longest 2 h 40 unbroken", or "" (off, or nothing seen)."""
        if not self.setting("desk_time") or not self.app.is_on(self.id):
            return ""
        spans = self.desk_spans(lo, hi)
        total = sum((b - a).total_seconds() for a, b in spans)
        if total < 15 * 60:
            return ""
        longest = max((b - a).total_seconds() for a, b in spans)

        def hm(s: float) -> str:
            h, m = int(s // 3600), int(s % 3600 // 60)
            return f"{h} h {m:02d}" if h and m else f"{h} h" if h else f"{m} min"

        return f"{hm(total)} at the desk {when}, longest {hm(longest)} unbroken."

    def weekly_lines(self) -> list[str]:
        from kurooto.core.clock import now

        t = now()
        line = self.desk_line(t - dt.timedelta(days=7), t, "this week")
        return [line[0].upper() + line[1:]] if line else []

    def line(self) -> str:
        w = self.watcher
        if not self.app.is_on(self.id):
            return "off"
        why = self.pause_reason()
        if why:
            return f"paused: {why}"
        if w is None:
            return "starting"
        if w.state == "watching":
            held = self.holds()
            if not held:
                return "camera on: looking for you"
            addon = [h for h in held if h not in self._core_holds]
            own = [h for h in held if h in self._core_holds]
            parts = ([f"an add-on is looking ({', '.join(addon)})"] if addon else []) + own
            return "camera on: " + "; ".join(parts)
        if w.state == "away":
            return "you've stepped away" + (" (camera on)" if w.camera_open else "")
        return "resting: camera off while you use the computer"

    def counts(self) -> dict:
        c = self.watcher.counts if self.watcher is not None else None
        return {"you": c.you if c else 0, "unsure": c.unsure if c else 0, "not_you": c.not_you if c else 0}

    def stage(self) -> str:
        if not self.app.is_on(self.id):
            return "off"
        if self.parts.missing(self.wants()):
            return "setup"
        s = self.session
        if s is not None and s.state != "ended":
            return STAGES.get(s.kind, "testing")
        if not self.enrolled() or self.reenrol_needed():
            return "enrol"
        return "manage"

    def status(self) -> dict:
        st = self.store.status()
        locked = False
        model = None
        if self.store.exists():
            try:
                t = self.template()
            except Locked:
                t, locked = None, True
            if t is not None:
                model = {
                    "samples": len(t.samples),
                    "per_step": st.get("per_step") or {},
                    "learned": len(t.learned),
                    "learned_at": [round(x.at) for x in t.learned],
                    "grade": t.grade,
                    "report": t.report,
                    "t_hi": round(t.hi, 3),
                    "t_lo": round(t.lo, 3),
                    "impostors": t.thresholds.get("method") == "impostors",
                    "model": MODEL,
                    "created": round(t.created),
                    "trained": round(t.updated),
                    "last_test": t.last_test,
                    "looks": [dict(x) for x in t.looks],  # (0.9.0) id, label, at, n: never the samples
                }
        s = self.session
        missing = self.parts.missing(self.wants())
        vo = self.app.modules.get("voice")
        return {
            "on": self.app.is_on(self.id),
            "stage": self.stage(),
            "line": self.line(),
            "why": self.pause_reason() if self.app.is_on(self.id) else "feature off",
            "enrolled": self.enrolled(),
            "kept": self.store.exists(),
            "locked": locked,
            "reenrol": self.reenrol_needed(),
            "missing": missing,
            "missing_gb": self.parts.size_gb(missing) if missing else 0,
            "size_gb": SIZE_GB,
            "licences": LICENCES,
            "camera": bool(self.watcher and self.watcher.camera_open) or bool(s and s.camera_open),
            "counts": self.counts(),
            "slow": self.slow,
            "model": model,
            "status": {k: st.get(k) for k in ("samples", "grade", "learned", "created", "trained", "last_test_at")},
            "session": (
                {"id": s.id, "kind": s.kind, "state": s.state, "why": s.why} if s and s.state != "ended" else None
            ),
            "plan": [{"key": p.key, "prompt": p.prompt, "need": p.target, "skippable": p.skippable} for p in PLAN],
            "target": TARGET,
            "minimum": MINIMUM,
            "strictness": self.setting("recognise.strictness") or "normal",
            "can_undo": self._previous is not None,
            "switches": {k: bool(self.setting(k)) for k in TOGGLES},
            "holds": self.holds(),
            "voice_speaks": bool(vo is not None and self.app.is_on("voice") and not vo.muted()),
            "gaze": self.gaze_status(),  # (0.8.17) look to talk by the eyes or the head; never the numbers
            "looks": {"on": bool(self.setting("looks.on")), "max": LOOKS_MAX, "samples": LOOK_TARGET, "s": LOOK_S},
        }

    def card(self) -> dict:
        st = self.store.status()
        lines = [f"Face presence: {self.line()}."]
        if st.get("enrolled"):
            grade = st.get("grade") or "?"
            lines.append(
                f"Model: {st.get('samples', 0)} samples, grade {grade}"
                + (f", {st.get('learned')} learned" if st.get("learned") else "")
                + "."
            )
            if grade == "weak":
                lines.append("Weak model: greetings may miss you; add samples on the Face page.")
        else:
            lines.append("Not enrolled yet: open the Face page and press Start.")
        c = self.counts()
        lines.append(f"Faces since start: you {c['you']}, unsure {c['unsure']}, not you {c['not_you']} (counts only).")
        lines.append("Open the Face page (the dashboard's face tab) to enrol, test or forget.")
        return {
            "lines": lines,
            "toggles": [{"id": k, "label": v, "on": bool(self.setting(k))} for k, v in TOGGLES.items()],
        }

    def card_action(self, act: str, value) -> str:
        if act not in TOGGLES:
            return "There's no such switch."
        self.app.settings.set(f"face.{act}", bool(value))
        return f"{TOGGLES[act]}: {'on' if value else 'off'}."

    # ------------------------------------------------------------------------------------------- commands
    def commands(self) -> list[Command]:
        return [
            Command(
                "face",
                "Face presence: what it's doing; pause [1h|off], forget, add-look [label] (about 10 s at the camera)",
                self._cmd,
                usage="/face [pause [1h|off]|forget|add-look [label]]",
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        word, _, rest = (arg or "").strip().partition(" ")
        word = word.lower()
        if word == "pause":
            return self.pause(rest)
        if word in ("forget", "delete"):
            return self.forget_question()
        if word in ("add-look", "addlook"):  # typed by you: camera.open (core/tap.py), never by voice
            if msg.via == "voice" or msg.voice:
                return "Adding a look is typed only: type /face add-look, or use Add this look on the Face page."
            via = "terminal" if msg.via == "terminal" else "chat"
            ok, out = self.look_start(rest, None, via)
            if not ok:
                return str(out.get("message") or "That didn't start.")
            then = "" if via == "terminal" else " I'll say how it went."
            return (
                f"Look at this computer's camera now, alone, as you are (its light is on), for about {LOOK_S / 2:g} "
                f"seconds; move your head a little.{then}"
            )
        return self.describe()

    def forget_question(self) -> Answer:
        if not self.store.exists():
            return Answer("There's no face model to forget.")
        asked = int(time.time())
        return Answer(
            "Forget your face model? Kurooto will stop recognising you until you enrol again.",
            [[("Forget", f"fce:{asked}:forget"), ("Keep it", "fce:0:keep")]],
        )

    def describe(self) -> str:
        st = self.store.status()
        out = [f"Face presence: {self.line()}."]
        if st.get("enrolled"):
            tar = st.get("tar")
            out.append(
                f"Model: {st.get('samples', 0)} samples, grade {st.get('grade') or '?'}"
                + (f", recognised {round(float(tar) * 100)}% of held-out samples" if tar is not None else "")
                + (f"; {st.get('learned')} learned" if st.get("learned") else "")
                + (f"; {st.get('looks')} added look{'s' if st.get('looks') != 1 else ''}" if st.get("looks") else "")
                + "."
            )
        else:
            out.append("Not enrolled: the dashboard's Face page has Start.")
        c = self.counts()
        out.append(f"Faces since start: you {c['you']}, unsure {c['unsure']}, not you {c['not_you']} (only counts).")
        out.append("/face pause [1h|off], /face forget, /face add-look [label]")
        return "\n".join(out)

    def intents(self) -> list[Intent]:
        def pause_match(t: str):
            m = PAUSE.match(t.strip())
            if not m:
                return None
            n, u = m["n"], (m["u"] or "").lower()
            if not u:
                return {"arg": ""}
            return {"arg": f"{n or 1}{'m' if u.startswith('m') else 'h'}"}

        return [
            Intent(
                "face_status",
                "is the camera on / are you watching me: what Face presence is doing",
                lambda t: {} if STATUS.match(t.strip()) else None,
                lambda msg, slots: self.describe(),
                questions=True,
                examples=("is the camera on?", "are you watching me?"),
            ),
            Intent(
                "face_pause",
                "stop watching / pause the camera for an hour",
                pause_match,
                lambda msg, slots: self.pause(slots.get("arg", "")),
                examples=("stop watching", "pause the camera for an hour"),
            ),
            Intent(
                "face_forget",
                "forget my face: asks first (Forget / Keep it)",
                lambda t: {} if FORGET.match(t.strip()) else None,
                lambda msg, slots: self.forget_question(),
                examples=("forget my face",),
            ),
        ]


def button(app: App, ref: str, act: str) -> str:
    """Forget / Keep it under /face forget and "forget my face", and Delete my face data / Keep it after Face presence
    was turned off (a core button: the feature may be off by then)."""
    if act != "forget":
        return "Kept."
    try:
        asked = int(ref)
    except ValueError:
        return "That button has expired."
    if time.time() - asked > CONFIRM_FORGET_S:
        return "That button has expired; send /face forget again."
    m = app.modules.get("face")
    if m is None:
        return "There's no Face presence here."
    return m.forget()[:190]


__all__ = ["Face", "button"]
