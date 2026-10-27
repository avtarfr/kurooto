"""Reminders: "remind me at 9 to call mum", "remind me in 20 minutes to take the tea off", /remind tomorrow 7am gym.
They arrive on Telegram. If the computer was asleep at the time, the reminder still comes when it wakes, marked
late; with Reminders with the lid shut on, your phone gets it at its time instead (lidsafe.py).

Location reminders (0.6.0, reminders.places, off by default): "remind me when I reach the library to return the
book", "remind me whenever I'm at the gym to stretch". The place's name and the text go to the Android app (a "place"
message through your call line), which keeps them and reminds you when you arrive at a place you saved there under
that name (android/.../Places.java: Android's proximity alerts, no Google services). Where your places are never
leaves the phone; this computer only knows their names."""

from __future__ import annotations

import datetime as dt
import re
import time
import uuid

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.notify import Message
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import NEG, WHEN_DAY, stale_time, when_from

REMIND = re.compile(r"^\s*remind me\s+(?P<rest>.+)$", re.I)
WHEN_WORDS = re.compile(
    r"\b(?:in\s+\d+(?:\.\d+)?\s*[a-z]+|in\s+(?:an?|half an?)\s+[a-z]+|(?:at|by)\s+\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?"
    r"|\d{1,2}(?:[:.]\d{2})\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)|(?:the\s+)?day after tomorrow|tomorrow|tonight|today)\b",
    re.I,
)
register_defaults(
    "reminders",
    {
        # sent to the Android app, which reminds you on arrival at a place saved there (turn on Places in the app too)
        "places": False,  # location reminders: "remind me when I reach the library to …" (needs the Android app)
    },
)
PLACE = re.compile(
    r"^\s*remind me\s+(?P<when>whenever|every time|when|once|as soon as|(?:the )?next time)\s+"
    r"(?:i|i'm|i am)\s+(?P<verb>reach|arrive at|arrive in|get back to|get to|am at|at|get back(?=\s+home\b)"
    r"|get(?=\s+home\b))\s+(?P<place>.+?)\s*(?:[,:;]+|\s+-\s+|\s+(?:to|that|about)\s+)\s*(?P<what>\S.*)$",
    re.I,
)
JOIN = re.compile(r"^(?:\s*(?:[:;,.\-–—]+|(?:to|that|about)\b))+\s*", re.I)


def tidy_what(text: str) -> str:
    """What to be reminded of, without the joins left at its start once the time is taken out: "at 6 pm: call mum",
    "- call mum", "to call mum", "about the exam" all give "call mum" / "the exam"."""
    what = JOIN.sub("", re.sub(r"\s+", " ", text).strip())
    return what.strip(" ,.;:-–—")


class Reminders(Module):
    id = "reminders"
    title = "Reminders"
    description = (
        'Plain English: "remind me at 9 to call mum". They arrive on Telegram (or the phone app), even after the '
        "laptop slept."
    )
    requires = ("telegram",)

    def __init__(self, app):
        super().__init__(app)
        # registered at once: a reminder set in the setup page's try-it box (web/tryit.py), before this feature is
        # on, still fires after a restart
        app.scheduler.action("reminders.fire", self._fire)

    def start(self):
        self.action("fire", self._fire)
        self._unpark()

    @property
    def parked_file(self):
        return self.app.paths.state / "reminders-parked.json"

    def stop(self) -> None:
        """Turned off: the reminders you set are kept (not cancelled) and set again when it's turned back on; any
        whose time passed meanwhile come then, marked late."""
        rows = jload(self.parked_file, []) or []
        for j in self.app.scheduler.jobs(f"{self.id}:"):
            if j.action == "reminders.fire":
                rows.append({"key": j.key, "at": j.next_run, "payload": j.payload})
        if rows:
            jsave(self.parked_file, rows)
        super().stop()
        self._lidsafe_poke()

    def _unpark(self) -> None:
        rows = jload(self.parked_file, []) or []
        for r in rows:
            payload = dict(r.get("payload") or {})
            if r["at"] <= time.time():
                payload["while_off"] = True
            self.app.scheduler.at(
                max(r["at"], time.time()), "reminders.fire", payload, key=r["key"], module=self.id, replace=False
            )
        self.parked_file.unlink(missing_ok=True)
        if rows:
            self._lidsafe_poke()

    def add(self, when: dt.datetime, what: str, key: str | None = None) -> str:
        # key: a caller that may take the reminder back (Brain's Undo, mind/study_push.py) names it "reminders:<ref>"
        key = key if key and key.startswith("reminders:") else f"reminders:{uuid.uuid4().hex[:8]}"
        self.app.scheduler.action("reminders.fire", self._fire)
        self.app.scheduler.at(
            when, "reminders.fire", {"what": what, "ref": key.split(":", 1)[1]}, key=key, module=self.id
        )
        self.app.events.emit("reminder_set", at=when.isoformat())
        self._lidsafe_poke()
        return f"I'll remind you {when:%a %d %b at %H:%M}: {what}"

    def _lidsafe(self):
        """Reminders with the lid shut (lidsafe.py), when it's on: your call line holds the next day's reminders."""
        m = self.app.modules.get("lidsafe")
        return m if m is not None and self.app.is_on("lidsafe") else None

    def _lidsafe_poke(self) -> None:
        m = self._lidsafe()
        if m is not None:
            m.poke()

    def _fire(self, p: dict):
        ls = self._lidsafe()
        if ls is not None and ls.handed_over("reminders.fire", p):
            return  # your call line has a sealed copy: whichever side is awake now says it, once (lidsafe.py)
        what = p.get("what", "")
        late = (
            " (late: Reminders was off)"
            if p.get("while_off")
            else " (late: the computer was asleep)"
            if p.get("late_s") or p.get("missed")
            else ""
        )
        ref = uuid.uuid4().hex[:8]
        self._snoozable(ref, what)
        self.app.notify(
            f"Reminder{late}: {what}",
            kind="reminder",
            buttons=[[("+10 min", f"rem:{ref}:10"), ("+1 h", f"rem:{ref}:60")]],
            why="reminders.own",
            about=what,
        )
        self.app.events.emit("reminder_fired", late=bool(late))

    def _snoozable(self, ref: str, what: str) -> None:
        from kurooto.core.state import jload, jsave

        f = self.app.paths.state / "reminders-snooze.json"
        d = jload(f, {}) or {}
        d[ref] = what
        jsave(f, dict(list(d.items())[-200:]))

    def callbacks(self):
        return {"rem": self._snooze, "remx": self._cancel}

    def _snooze(self, ref: str, act: str) -> str:
        from kurooto.core.state import jload

        what = (jload(self.app.paths.state / "reminders-snooze.json", {}) or {}).get(ref)
        if not what:
            return "That reminder is gone."
        when = now() + dt.timedelta(minutes=int(act or 10))
        self.add(when, what)
        return f"Again at {when:%H:%M}"

    def _cancel(self, ref: str, act: str) -> str:
        gone = self.app.scheduler.cancel(f"reminders:{ref}")
        self._lidsafe_poke()
        return "Cancelled." if gone else "Already gone."

    # ---------------------------------------------------------------------------------- at a place
    def at_place(self, place: str, what: str, every: bool = False) -> str:
        """A location reminder: the place's name and the text go to the phone app, which says it on arrival."""
        place = re.sub(r"^(?:the|my|our)\s+", "", " ".join(place.split()), flags=re.I).strip(" .,!?")
        what = tidy_what(what)
        if not self.setting("places"):
            return (
                "Location reminders are off. Turn them on in Settings → Reminders (places), and Places in the phone "
                "app."
            )
        calls = self.app.modules.get("calls")
        if calls is None or not self.app.is_on("calls") or not calls.ready()[0]:
            return "Location reminders work through the Android app: set up Phone calls and pair the phone first."
        sent = calls.phone.send(Message(what, title=place, kind="place_every" if every else "place"))
        if not sent:
            return "That didn't reach the phone app. Try again in a moment."
        self.app.events.emit("reminder_place", every=every)
        how = "every time you reach" if every else "when you reach"
        return (
            f"Sent to your phone: {how} {place}, it reminds you: {what}. If {place} isn't saved in the app yet, "
            "save it there once you're at it (Places → Save where you are now)."
        )

    # ------------------------------------------------------------------------------- plain English
    def intents(self):
        def match_place(text: str):
            m = PLACE.match(text)
            if not m or NEG.search(text):
                return None
            place = m["place"].strip()
            if len(place) > 40 or len(place.split()) > 5 or not tidy_what(m["what"]):
                return None
            return {"place": place, "what": m["what"], "every": m["when"].lower() in ("whenever", "every time")}

        def match(text: str):
            m = REMIND.match(text)
            if not m or NEG.search(text):
                return None
            rest = m["rest"]
            when = when_from(rest)
            if not when:
                said = stale_time(rest)  # "remind me, I didn't do it at 3": that time didn't happen, so ask
                return {"ask": said} if said else None
            what = tidy_what(WHEN_WORDS.sub("", WHEN_DAY.sub(" ", rest)))
            return {"when": when, "what": what or "you asked me to remind you"}

        def run(msg, s):
            if s.get("ask"):
                return (
                    f"When should I remind you? I didn't set one: the {s['ask']} in that is about what didn't happen "
                    'or what was planned. Say "remind me at 4:30 to …" or "remind me in 20 minutes to …".'
                )
            return self.add(s["when"], s["what"])

        return [
            Intent(
                "remind_place",
                "a reminder for when you reach a place (the phone app)",
                match_place,
                lambda msg, s: self.at_place(s["place"], s["what"], s["every"]),
                examples=("remind me when I reach the library to return the book",),
            ),
            Intent(
                "remind",
                "set a reminder",
                match,
                run,
                examples=("remind me at 9 to call mum", "remind me in 20 minutes to take the tea off"),
            ),
        ]

    def commands(self):
        return [
            Command(
                "remind",
                "a reminder (/remind 21:30 call mum, /remind tomorrow 7am gym; /remind 20 tea: in 20 min)",
                self._cmd,
            ),
            Command("reminders", "your upcoming reminders", self._list),
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        parts = arg.split()
        for n in (3, 2, 1):  # "tomorrow 7am gym", "in 20m tea", "21:30 call mum"
            if len(parts) >= n:
                try:
                    when = parse_when(" ".join(parts[:n]))
                except ValueError:
                    continue
                return self.add(when, tidy_what(" ".join(parts[n:])) or "you asked me to remind you")
        return (
            "Usage: /remind 21:30 call mum   (or: tomorrow 7am gym, in 20m tea; a bare number is the hour: 9 gym is "
            "the next 9:00)"
        )

    def _list(self, msg: Incoming, arg: str) -> str | None:
        jobs = self.app.scheduler.jobs("reminders:")
        if not jobs:
            return "No reminders set."
        for j in jobs[:15]:
            msg.reply(
                f"{j.when.astimezone():%a %d %b %H:%M}  {j.payload.get('what')}",
                buttons=[[("Cancel", f"remx:{j.key.split(':', 1)[1]}:x")]],
            )
        return None

    def help(self):
        return ['"remind me at 9 to …", /remind, /reminders']

    # -------------------------------------------------------------------------------------- on calls
    def call_tools(self):
        return [
            Tool(
                "add_reminder",
                'A reminder message at a time, e.g. when "18:30", "in 2 hours", "tomorrow 9am".',
                self._tool_add,
                {"when": arg(), "what": arg("what to remind them of")},
                ("when", "what"),
                offline="queue",
                hint="add_reminder sets a reminder message; schedule_call is for a reminder call instead.",
            )
        ]

    def _tool_add(self, a: dict) -> str:
        try:
            when = parse_when(str(a.get("when", "")))
        except ValueError:
            return f"I couldn't read the time {a.get('when')!r}."
        return self.add(when, str(a.get("what") or "a reminder"))

    def call_brief(self) -> dict:
        soon = [j for j in self.app.scheduler.jobs("reminders:") if j.next_run < time.time() + 86400]
        if not soon:
            return {}
        return {
            "reminders_next_24h": [
                f"{dt.datetime.fromtimestamp(j.next_run):%a %H:%M} {j.payload.get('what', '')}" for j in soon[:8]
            ]
        }
