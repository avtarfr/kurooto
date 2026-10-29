"""Room modes (0.9.2, voice.room_modes.on): alone, company, night and silent. A mode is a table over Voice's own
saved settings, read through Voice.setting(), and it only ever tightens them: a switch is only turned off (never on),
a choice only narrowed (speak.what "all" -> "voice", the "heard you" word -> the tone). It never turns on anything
(Gemini Live for everyone, a feature you switched off) and never touches Voice ID, Face presence or approvals, so a
feature's own switch always wins. Each mode ends by itself (its hours, night at the end of your night hours) and goes
back to alone, which is your settings as they are.

    alone    as you set it (the default; ending a mode comes back here)
    company  others are here: nothing of yours is said aloud by itself (answers you asked for elsewhere, reminders,
             questions), only your own look opens a talk, and nobody else's turns go to Gemini Live
    night    the same quiet about your things, every sound voice.room_modes.night_db quieter (the output stage,
             outstage.py), the tone in place of the "Hmm." word; the dashboard and the Body face show it
    silent   nothing aloud at all: the answers are on screen only (the captions: the dashboard's and the app's text),
             and Gemini Live (speech to speech) isn't used

Set by: /room <mode> typed (Telegram, the phone app's chat, the dashboard's talk box), the dashboard (the Voice panel
and its quick toggle: POST /api/voice/room), the phone app (Today's Room card: the being op voice.room), a phrase said
aloud ("night mode", "go silent", "I'm alone"), on your own verified turn only (Voice ID's verdict "owner";
voice.room_modes.spoken), and add-ons through Voice.set_room_mode(mode, source) and Voice.room_mode() (the Body
face: it shows the mode, and its long-press sets it while Face presence sees the owner). Kept in
state/voice/room.json (the mode, until when, who set it: no words), so it lasts a restart until it ends."""

from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.modules.voice import Voice

register_defaults(
    "voice",
    {
        "room_modes": {
            # (0.9.2) room modes: alone, company, night and silent (/room, the dashboard, the phone app, Body); each
            # only tightens Voice's own settings and ends by itself
            "on": True,
            "spoken": True,  # a mode can be set by saying it ("night mode", "go silent"), in your own voice only
            "company_h": 3,  # company ends by itself after this many hours
            "silent_h": 2,  # silent ends by itself after this many hours
            "night_h": 10,  # night ends at the end of your night hours, or after this many hours without them
            "night_db": -12,  # at night every sound is this much quieter (decibels, -30 to 0)
        },
    },
)

MODES = ("alone", "company", "night", "silent")
LABELS = {"alone": "Alone", "company": "Company", "night": "Night", "silent": "Silent"}
WHAT = {
    "alone": "as you set it",
    "company": "nothing of yours said aloud by itself, only your look opens a talk",
    "night": "quieter, and nothing of yours said aloud by itself",
    "silent": "nothing aloud: answers on screen only",
}
SAME = {"off": "alone", "normal": "alone", "end": "alone", "none": "alone", "guests": "company", "people": "company"}
MAX_H = 24.0
NIGHT_MAX_H = 16.0  # night hours ending later than this from now aren't tonight's


def _off(v):
    """A switch: only ever turned off."""
    return False if v else v


def _what(v):
    """voice.speak.what: every answer read aloud narrows to the ones you asked for aloud."""
    return "voice" if str(v or "").strip().lower() == "all" else v


def _tone(v):
    """voice.speak.ack: the spoken "Hmm." narrows to the soft tone (off stays off)."""
    return "tone" if str(v or "").strip().lower() == "word" else v


QUIET_ABOUT_YOU = {
    "speak.what": _what,
    "speak.messages": _off,
    "listen.live_everyone": _off,
}
TABLE: dict[str, dict] = {
    "alone": {},
    "company": {**QUIET_ABOUT_YOU, "answers_questions": _off, "listen.look_anyone": _off},
    "night": {**QUIET_ABOUT_YOU, "speak.ack": _tone},
    "silent": {**QUIET_ABOUT_YOU, "speak.on": _off, "listen.live": _off, "answers_questions": _off},
}

# what's said aloud: the whole turn (its name already taken off), lower case, punctuation and "please" dropped
_M = r"(alone|company|night|silent)"
SET = (
    re.compile(rf"^(?:room\s+)?{_M}\s+mode(?:\s+(?:on|now))?$"),
    re.compile(
        rf"^(?:go|switch\s+to|change\s+to|turn\s+on|put\s+(?:it|yourself)\s+in(?:to)?)\s+(?:the\s+)?{_M}(?:\s+mode)?$"
    ),
    re.compile(rf"^room\s+{_M}$"),
)
END = re.compile(
    r"^(?:(?:end|stop|turn\s+off|cancel|leave)\s+(?:the\s+)?(?:room|alone|company|night|silent)\s+mode"
    r"|(?:room|company|night|silent)\s+mode\s+off|normal\s+mode|i'?m\s+alone(?:\s+now)?|it'?s\s+just\s+me(?:\s+now)?)$"
)
NOT_YOU = "Only your own voice can change the room mode, and Voice ID has to know it's you. You can type /room instead."
NO_ID = "Room modes by voice need Voice ID, so only you can change them. You can type /room instead."


def phrase(text: str) -> str | None:
    """A room mode said aloud: its mode ("alone" to end one), or None when the turn isn't one (whole turn only)."""
    t = re.sub(r"[^\w\s']", " ", str(text or "").lower())
    t = re.sub(r"\bplease\b", " ", t)
    t = " ".join(t.split())
    if not t or len(t) > 60:
        return None
    if END.match(t):
        return "alone"
    for rx in SET:
        m = rx.match(t)
        if m:
            return m.group(1)
    return None


def mode_of(word: str) -> str | None:
    w = str(word or "").strip().lower()
    w = SAME.get(w, w)
    return w if w in MODES else None


def hours_of(word: str) -> float | None:
    """ "2h", "90m", "1.5" (hours) -> hours; None when it isn't a length."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|m|min|mins|minutes?)?", str(word or "").strip().lower())
    if not m:
        return None
    n = float(m.group(1))
    return n / 60 if (m.group(2) or "h").startswith("m") else n


class Room:
    def __init__(self, v: Voice, file, clock=time.time):
        self.v = v
        self.file = file
        self.clock = clock
        self._lock = threading.Lock()
        self._state: dict = jload(file, {}) or {}

    # ------------------------------------------------------------------------------------------- reading
    def _base(self, key: str, default=None):
        """A saved setting as it is (the table never applies to its own switches)."""
        return self.v.app.settings.get(f"voice.{key}", default)

    def on(self) -> bool:
        return bool(self._base("room_modes.on"))

    def mode(self) -> str:
        """The mode now: "alone" while off, after its time, or never set."""
        if not self.on():
            return "alone"
        m = self._state.get("mode")
        if m not in MODES or m == "alone":
            return "alone"
        until = self._state.get("until")
        if until and self.clock() >= float(until):
            self._end(m)
            return "alone"
        return m

    def tighten(self, key: str, value):
        """Voice.setting(): the saved value, tightened by the mode's table (never loosened)."""
        m = self.mode()
        if m == "alone":
            return value
        f = TABLE[m].get(key)
        return f(value) if f is not None else value

    def gain_db(self) -> float:
        """(outstage.py) Night's quieter output, in dB (0 otherwise)."""
        if self.mode() != "night":
            return 0.0
        try:
            db = float(self._base("room_modes.night_db", -12))
        except (TypeError, ValueError):
            db = -12.0
        return max(-30.0, min(0.0, db))

    def silent(self) -> bool:
        return self.mode() == "silent"

    def status(self) -> dict:
        """What the dashboard, the phone and add-ons show: words and times, never what was said."""
        m = self.mode()
        until = self._state.get("until") if m != "alone" else None
        return {
            "on": self.on(),
            "mode": m,
            "label": LABELS[m],
            "what": WHAT[m],
            "until": until,
            "until_hm": time.strftime("%H:%M", time.localtime(float(until))) if until else "",
            "by": self._state.get("by", "") if m != "alone" else "",
            "modes": list(MODES),
            "spoken": bool(self._base("room_modes.spoken")),
        }

    def line(self) -> str:
        st = self.status()
        if st["mode"] == "alone":
            return ""
        return f"room: {st['label'].lower()} until {st['until_hm']}" if st["until_hm"] else f"room: {st['mode']}"

    # ------------------------------------------------------------------------------------------- setting
    def _until(self, mode: str, hours: float | None) -> float | None:
        now = self.clock()
        if mode == "alone":
            return None
        if hours is not None:
            return now + max(0.05, min(MAX_H, float(hours))) * 3600
        if mode == "night":
            end = self._night_end()
            if end is not None and now < end <= now + NIGHT_MAX_H * 3600:
                return end
        key = {"company": "company_h", "silent": "silent_h", "night": "night_h"}[mode]
        try:
            h = float(self._base(f"room_modes.{key}") or 0)
        except (TypeError, ValueError):
            h = 0.0
        return now + max(0.05, min(MAX_H, h or 2.0)) * 3600

    def _night_end(self) -> float | None:
        """When tonight's night hours end (availability), as a time; None outside them or without them."""
        try:
            from kurooto.core.clock import now

            got = self.v.app.availability.night(now())
            return got[1].timestamp() if got else None
        except Exception:
            return None

    def set(self, mode: str, by: str = "", hours: float | None = None) -> tuple[bool, str]:
        """Set a mode (alone ends one). (ok, a sentence to show or say)."""
        m = mode_of(mode)
        if m is None:
            return False, "Room modes: alone, company, night or silent."
        if not self.on():
            return False, "Room modes are off (voice.room_modes.on)."
        until = self._until(m, hours)
        with self._lock:
            was = self._state.get("mode") or "alone"
            self._state = {"mode": m, "since": self.clock(), "until": until, "by": str(by or "")[:20]}
            jsave(self.file, self._state)
        self._changed(m, str(by or ""), was)
        if m == "alone":
            return True, "Room mode: alone (as you set it)."
        hm = time.strftime("%H:%M", time.localtime(until)) if until else ""
        return True, f"{LABELS[m]} mode until {hm}: {WHAT[m]}."

    def _end(self, was: str) -> None:
        with self._lock:
            if self._state.get("mode") != was:
                return
            self._state = {"mode": "alone", "since": self.clock(), "until": None, "by": "time"}
            try:
                jsave(self.file, self._state)
            except OSError:
                pass
        self._changed("alone", "time", was)

    def _changed(self, mode: str, by: str, was: str) -> None:
        """The event log (the mode and who set it, never words), the open pages, and the Body face's hook."""
        try:
            self.v.app.events.emit("voice_room", mode=mode, by=by, was=was)
        except Exception:
            pass
        try:
            self.v.publish("voice_room", **self.status())
        except Exception:
            pass

    # --------------------------------------------------------------------------------------- said aloud
    def heard(self, text: str, who) -> str | None:
        """A room-mode phrase in a turn said to it: the answer to say ("" never), or None when it isn't one (or the
        spoken switch is off): then the turn goes on as usual. Only his verified turn sets it."""
        if not self.on() or not self._base("room_modes.spoken"):
            return None
        m = phrase(text)
        if m is None:
            return None
        if not self.v.voiceid.on():
            return NO_ID
        if who is None or getattr(who, "decision", "") != "owner":
            return NOT_YOU
        return self.set(m, by="voice")[1]
