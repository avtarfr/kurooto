"""Reminders: "remind me at 9 to call mum", "remind me in 20 minutes to take the tea off", /remind tomorrow 7am gym.
They arrive on Telegram. If the computer was asleep at the time, the reminder still comes when it wakes, marked
late; with Reminders with the lid shut on, your phone gets it at its time instead (lidsafe.py).

Location reminders (0.6.0, reminders.places, off by default): "remind me when I reach the library to return the
book", "remind me whenever I'm at the gym to stretch". The place's name and the text go to the Android app (a "place"
message through your call line), which keeps them and reminds you when you arrive at a place you saved there under
that name (android/.../Places.java: Android's proximity alerts, no Google services). Where your places are never
leaves the phone; this computer only knows their names.

An add-on's buttons (0.9.0, reminders.addon_buttons): a feature's reminder_buttons(what) -> [(label, callback data)]
adds a row of its own under +10 min / +1 h when a reminder fires (at most 2 buttons, each answered by that feature's
own callbacks); the snooze row is always there and first. A tap is the user's; nothing starts by itself.

The phone's place names (0.9.1, reminders.place_names, off): the Android app sends the names of the places saved on
it (names only, sealed, never where they are; modules/calls/chat.py's "place_names" op, kept in
calls/place-names.json), and a place you name is matched to one of them before it goes to the phone: "the lib" ->
"Library", "chem lab" -> "Chemistry lab". One clear match only; otherwise your words go as before. The names are used
here only, never told to an AI.

Repeating reminders (0.9.2, reminders.repeat, on): "remind me every day at 22:15 to call home", "every weekday at 7",
"on Mondays and Thursdays at 9", with an optional "until <date>". One scheduler job per series (its key never
changes): each time it fires it books its own next time (_rearm), so a series is listed, cancelled and skipped as one
(/reminders: Cancel, Skip next). Each time gets its own "ref" (the series' ref and the date) so Reminders with the lid
shut says each one once. Turned off: a series comes once more at its next time and isn't booked again.

Changing one (0.9.2): change_reminder (calls and AI requests) moves a reminder's time or its repeat, found by key or
by words of its text (the most recently set first), so "make it 10:15" right after setting 22:00 moves that one
instead of adding a second. A bare time keeps the reminder's day and takes the reading nearest the old time ("10:15"
after 22:00 is 22:15). add_reminder from a call or AI request with the same words as one set in the last 15 minutes
moves that one too, unless `another` says they want both."""

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
        # (0.9.0) a feature (an add-on) may add its own buttons to a reminder as it fires, in a row under +10 min and
        # +1 h (for example "Order on Zepto" under "buy milk"); a tap starts it, nothing starts by itself
        "addon_buttons": True,
        # (0.9.0) during a Study mode focus, your reminders wait for its break (a reset or pause brings them at once)
        "wait_for_break": False,
        # (0.9.1) the phone app shares the names of the places you saved (names only, sealed, never where they are),
        # so "the lib" finds "Library"; used here for matching only, never told to an AI
        "place_names": False,
        # (0.9.2) repeating reminders: "every day at 22:15", "on weekdays", "every Monday and Thursday", "until <date>";
        # off: a series comes once more at its next time and isn't booked again
        "repeat": True,
    },
)
PLACE_NAMES_MAX = 50  # (place_names) names kept from the phone, at most
PLACE = re.compile(
    r"^\s*remind me\s+(?P<when>whenever|every time|when|once|as soon as|(?:the )?next time)\s+"
    r"(?:i|i'm|i am)\s+(?P<verb>reach|arrive at|arrive in|get back to|get to|am at|at|get back(?=\s+home\b)"
    r"|get(?=\s+home\b))\s+(?P<place>.+?)\s*(?:[,:;]+|\s+-\s+|\s+(?:to|that|about)\s+)\s*(?P<what>\S.*)$",
    re.I,
)
ADDON_BUTTONS = 2  # (reminders.addon_buttons) at most this many buttons features add to a reminder
RECENT_S = 15 * 60  # (0.9.2) a reminder set this recently with the same words is the one a correction means
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_FULL = r"(?:mon|tues|wednes|thurs|fri|satur|sun)day"
_SHORT = r"(?:mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)"
_ONE = rf"(?:{_FULL}|{_SHORT})\b"
_AND = r"\s*(?:,|/|&|\band\b)\s*"
# (0.9.2, reminders.repeat) the words that make a reminder repeat, and the filler around them ("from today onwards")
REPEAT_WORDS = re.compile(
    r"\b(?:every\s*day\b(?!'s)|(?:daily|nightly)(?=\s*(?:$|[,.;]|(?:at|from|until|till|to|starting|onwards?)\b))"
    r"|each\s+day|(?:every|each)\s+(?:morning|evening|night)\b|(?:every|each|on)\s+weekdays?"
    r"|(?:every|on|at)\s+(?:the\s+)?weekends?"
    rf"|(?:every|each)\s+{_ONE}(?:{_AND}{_ONE})*|(?:every|on)\s+{_FULL}s\b(?:{_AND}{_FULL}s?\b)*)",
    re.I,
)
REPEAT_FILLER = re.compile(
    r"\b(?:(?:from|starting)\s+(?:today|tonight|now|tomorrow)(?:\s+(?:on(?:wards?)?))?|from\s+now\s+on|onwards?"
    r"|going\s+forward)\b",
    re.I,
)
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_DATE = r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+[a-z]{3,9}|[a-z]{3,9}\s+\d{1,2}(?![:.\d])|tomorrow|" + _FULL
UNTIL = re.compile(rf"\b(?:until|till|through|up\s+to)\s+(?:the\s+)?(?P<u>{_DATE})\b", re.I)
ONCE = re.compile(r"^\s*(?:once|no|none|never|off|stop|not?\s+repeat\w*|just\s+once|one-?off)\s*$", re.I)
TIME_ONLY = re.compile(r"^\s*(?:at\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s*$", re.I)
STOP = {"the", "my", "a", "an", "to", "for", "and", "of", "on", "at", "me", "remind", "reminder", "about"}


def repeat_days(text: str) -> list[int] | None:
    """(0.9.2) The weekdays (0 = Monday) a reminder repeats on, from words ("every day", "daily", "on weekdays",
    "weekends", "every Monday and Thursday", "on Tuesdays", "mon,thu" as a tool's argument), or None (no repeat)."""
    t = " ".join(str(text or "").lower().split())
    if not t:
        return None
    if re.fullmatch(r"(?:every\s*day|daily|each day|all days|every night|nightly|every (?:morning|evening))", t):
        return list(range(7))
    if re.fullmatch(r"(?:every |on )?weekdays?", t):
        return [0, 1, 2, 3, 4]
    if re.fullmatch(r"(?:every |on |at )?(?:the )?weekends?", t):
        return [5, 6]
    m = REPEAT_WORDS.search(t)
    if m is None:  # a tool's list: "mon,thu", "monday thursday"
        names = re.findall(_ONE, t)
        if names and not re.sub(rf"{_ONE}|[\s,/&]|\band\b|\bevery\b|\bon\b|s\b", "", t):
            return sorted({DAY_NAMES.index(n[:3]) for n in names})
        return None
    w = m[0]
    if re.search(r"day|daily|night|morning|evening", w) and not re.search(_FULL, w) and "week" not in w:
        return list(range(7))
    if "weekday" in w:
        return [0, 1, 2, 3, 4]
    if "weekend" in w:
        return [5, 6]
    return sorted({DAY_NAMES.index(n[:3]) for n in re.findall(rf"(?:{_FULL}|{_SHORT})(?=s?\b)", w)}) or None


def strip_repeat(text: str) -> str:
    """The text without its repeat words, their filler ("from today onwards") and an "until <date>"."""
    return REPEAT_FILLER.sub(" ", REPEAT_WORDS.sub(" ", UNTIL.sub(" ", text)))


def until_date(text: str, base: dt.datetime | None = None) -> dt.date | None:
    """(0.9.2) The last day of a series: "2026-12-01", "friday", "tomorrow", "30 nov", "november 30". Raises
    ValueError when it can't read it."""
    base = base or now()
    t = " ".join(str(text or "").lower().split())
    t = re.sub(r"^(?:until|till|through|up to)\s+(?:the\s+)?", "", t)
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})|([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?", t)
    if m:
        day, mon = (int(m[1]), m[2]) if m[1] else (int(m[4]), m[3])
        if mon[:3] in _MONTHS:
            d = dt.date(base.year, _MONTHS.index(mon[:3]) + 1, day)
            return d if d >= base.date() else d.replace(year=base.year + 1)
    return parse_when(t, base).date()


def repeat_label(rep: dict) -> str:
    """ "every day", "on weekdays", "at weekends", "every Mon and Thu", with "until Fri 04 Dec" when it ends."""
    days = sorted(set(rep.get("days") or []))
    if days == list(range(7)):
        out = "every day"
    elif days == [0, 1, 2, 3, 4]:
        out = "on weekdays"
    elif days == [5, 6]:
        out = "at weekends"
    else:
        names = [DAY_NAMES[d].title() for d in days]
        out = "every " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1])
    if rep.get("until"):
        out += f" until {dt.date.fromisoformat(rep['until']):%a %d %b}"
    return out


def next_time(rep: dict, after: dt.datetime) -> dt.datetime | None:
    """(0.9.2) A series' first time strictly after `after` (local, naive): its time of day on one of its days, on or
    before its last day. None when it's over."""
    h, mi = (int(x) for x in str(rep.get("at") or "09:00").split(":"))
    until = dt.date.fromisoformat(rep["until"]) if rep.get("until") else None
    days = set(rep.get("days") or [])
    for add in range(8):
        day = after.date() + dt.timedelta(days=add)
        if until and day > until:
            return None
        cand = dt.datetime.combine(day, dt.time(h, mi))
        if day.weekday() in days and cand > after:
            return cand
    return None


def occurrence(ref: str, when: dt.datetime) -> str:
    """One time of a series, as Reminders with the lid shut tells them apart (each said once)."""
    return f"{ref}-{when:%y%m%d}"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(w) > 1 and w not in STOP}


def moved_time(old: dt.datetime, text: str, base: dt.datetime | None = None) -> dt.datetime:
    """(0.9.2) A reminder's new time from a correction: a bare time ("10:15", "10.15 pm", "11") keeps its day and, with
    no am/pm, takes the reading nearest the old time ("10:15" after 22:00 is 22:15); anything else is read as
    usual ("tomorrow 9am"). A time already past moves to the next day. Raises ValueError."""
    base = base or now()
    m = TIME_ONLY.match(str(text or ""))
    if not m:
        return parse_when(str(text or ""), base)
    h, mi, ap = int(m[1]), int(m[2] or 0), (m[3] or "").lower().replace(".", "")
    if mi > 59 or h > 23:
        raise ValueError("no such time")
    if ap:
        if h > 12:
            raise ValueError("no such time")
        hours = [h % 12 + (12 if ap == "pm" else 0)]
    else:
        hours = [h % 12, h % 12 + 12] if 1 <= h <= 12 else [h]
    opts = [dt.datetime.combine(old.date(), dt.time(x, mi)) for x in hours]
    best = min(opts, key=lambda t: abs((t - old).total_seconds()))
    while best <= base:
        best += dt.timedelta(days=1)
    return best


JOIN = re.compile(r"^(?:\s*(?:[:;,.\-–—]+|(?:to|that|about)\b))+\s*", re.I)


def tidy_what(text: str) -> str:
    """What to be reminded of, without the joins left at its start once the time is taken out: "at 6 pm: call mum",
    "- call mum", "to call mum", "about the exam" all give "call mum" / "the exam"."""
    what = JOIN.sub("", re.sub(r"\s+", " ", text).strip())
    return what.strip(" ,.;:-–—")


def place_key(name: str) -> str:
    """A place's name as it's matched (the phone's PlaceRules.key): "The Library " and "library" are the same."""
    s = re.sub(r"\s+", " ", str(name or "").strip().lower())
    s = re.sub(r"^(?:the|my|our) ", "", s)
    return re.sub(r"[.!?,;:]+$", "", s).strip()


def saved_place(said: str, names: list[str]) -> str | None:
    """(0.9.1, reminders.place_names) The one saved place `said` means, or None: the same name, else the only one
    whose words start with the words said ("lib" -> "Library", "chem lab" -> "Chemistry lab"), else the only close
    spelling. Two that fit equally: None (your words go as they are)."""
    import difflib

    k = place_key(said)
    if not k:
        return None
    keyed = {}
    for n in names:
        if place_key(n):
            keyed.setdefault(place_key(n), n)
    if k in keyed:
        return keyed[k]
    words = k.split()

    def starts(key: str) -> bool:
        kw = key.split()
        return len(kw) >= len(words) and all(a.startswith(b) for a, b in zip(kw, words, strict=False))

    hits = [n for key, n in keyed.items() if len(k) >= 2 and starts(key)]
    if len(hits) == 1:
        return hits[0]
    if hits:
        return None
    close = difflib.get_close_matches(k, list(keyed), n=2, cutoff=0.8)
    return keyed[close[0]] if len(close) == 1 else None


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

    def add(
        self,
        when: dt.datetime,
        what: str,
        key: str | None = None,
        buttons: list | None = None,
        repeat: list[int] | None = None,
        until: dt.date | None = None,
    ) -> str:
        # key: a caller that may take the reminder back (Brain's Undo, mind/study_push.py) names it "reminders:<ref>"
        # buttons: rows of (label, data) shown under it besides the snoozes (0.9.0: Study push's "Start 25 min")
        # repeat: (0.9.2, reminders.repeat) the weekdays it comes back on (0 = Monday), at when's time; until: its last
        key = key if key and key.startswith("reminders:") else f"reminders:{uuid.uuid4().hex[:8]}"
        self.app.scheduler.action("reminders.fire", self._fire)
        ref = key.split(":", 1)[1]
        p = {"what": what, "ref": ref, "set_at": round(time.time())}
        if buttons:
            p["buttons"] = [[list(b) for b in row] for row in buttons]
        off = ""
        if repeat and self.setting("repeat") is False:
            off = " (Repeating reminders are off, so this one comes once: Settings, Reminders, repeat.)"
        elif repeat:
            rep = {"days": sorted(set(repeat)), "at": f"{when:%H:%M}"}
            if until:
                rep["until"] = until.isoformat()
            first = next_time(rep, when - dt.timedelta(seconds=1))
            if first is None:
                return f"I didn't set it: no {repeat_label(rep)} is left after {when:%a %d %b}."
            when = first
            p.update(repeat=rep, series=ref, ref=occurrence(ref, when))
        self.app.scheduler.at(when, "reminders.fire", p, key=key, module=self.id)
        self.app.events.emit("reminder_set", at=when.isoformat(), **({"repeat": True} if p.get("repeat") else {}))
        self._lidsafe_poke()
        return self._said(when, what, p.get("repeat")) + off

    @staticmethod
    def _said(when: dt.datetime, what: str, rep: dict | None) -> str:
        if rep:
            return f"I'll remind you {repeat_label(rep)} at {when:%H:%M}, starting {when:%a %d %b}: {what}"
        return f"I'll remind you {when:%a %d %b at %H:%M}: {what}"

    # ------------------------------------------------------------------------- repeating, changing (0.9.2)
    def _rearm(self, p: dict) -> None:
        """A series just came due: book its next time under the same key (the scheduler drops only the row it ran,
        and this one has a later time). Off (reminders.repeat) or past its last day: it ends here."""
        series, rep = str(p.get("series") or ""), p.get("repeat") or {}
        if not series:
            return
        if self.setting("repeat") is False:
            self.app.events.emit("reminder_series_ended", why="off")
            return
        nxt = next_time(rep, now())
        if nxt is None:
            self.app.events.emit("reminder_series_ended", why="until")
            return
        keep = {k: v for k, v in p.items() if k not in ("late_s", "missed", "while_off", "released", "lidsafe")}
        keep["ref"] = occurrence(series, nxt)
        self.app.scheduler.at(nxt, "reminders.fire", keep, key=f"reminders:{series}", module=self.id)
        self._lidsafe_poke()

    def _jobs(self) -> list:
        """The reminders you set (not the ones waiting for a study break)."""
        return [
            j
            for j in self.app.scheduler.jobs("reminders:")
            if j.action == "reminders.fire" and not j.key.startswith("reminders:wait")
        ]

    def skip_next(self, ref: str) -> str:
        """A series' next time is skipped: it comes back at the one after (or ends, if that was its last)."""
        j = self.app.scheduler.get(f"reminders:{ref}")
        if j is None:
            return "That reminder is gone."
        rep = (j.payload or {}).get("repeat")
        if not rep:
            return "That reminder doesn't repeat; Cancel takes it off."
        cur = j.when.astimezone().replace(tzinfo=None)
        nxt = next_time(rep, cur)
        if nxt is None:
            self.app.scheduler.cancel(j.key)
            self._lidsafe_poke()
            return "That was its last time, so it's over."
        self.app.scheduler.at(
            nxt, "reminders.fire", {**j.payload, "ref": occurrence(ref, nxt)}, key=j.key, module=self.id
        )
        self._lidsafe_poke()
        self.app.events.emit("reminder_skipped")
        return f"Skipped {cur:%a %d %b}; next {nxt:%a %d %b at %H:%M}."

    def find(self, key: str = "", words: str = "", recent_s: float | None = None) -> list:
        """The reminders a correction may mean, the most recently set first: by key; else by the words of its text
        (all of them, else the most of them); else the ones set in the last `recent_s` seconds."""
        jobs = self._jobs()
        key = str(key or "").strip()
        if key:
            k = key if key.startswith("reminders:") else f"reminders:{key}"
            return [j for j in jobs if j.key == k]
        newest = sorted(jobs, key=lambda j: -float((j.payload or {}).get("set_at") or 0))
        want = _words(words)
        if want:
            have = [(len(want & _words((j.payload or {}).get("what"))), j) for j in newest]
            full = [j for n, j in have if n == len(want)]
            if full:
                return full
            best = max((n for n, _ in have), default=0)
            return [j for n, j in have if best and n == best]
        if recent_s is None:
            return newest
        return [j for j in newest if float((j.payload or {}).get("set_at") or 0) >= time.time() - recent_s]

    def change(self, job, when: str = "", repeat: str = "", until: str = "") -> str:
        """Move a reminder (and its series) to a new time, make it repeat or stop repeating, or give it an end."""
        p = dict(job.payload or {})
        what = p.get("what") or "a reminder"
        old = job.when.astimezone().replace(tzinfo=None)
        rep = dict(p.get("repeat") or {}) or None
        was = self._said(old, what, rep).removeprefix("I'll remind you ").rsplit(f": {what}", 1)[0]
        try:
            new = moved_time(old, when) if str(when or "").strip() else old
        except ValueError:
            return f"I couldn't read the time {when!r}; nothing changed."
        if str(repeat or "").strip():
            if ONCE.match(repeat):
                rep = None
            else:
                days = repeat_days(repeat)
                if days is None:
                    return f"I couldn't read how often {repeat!r} is (daily, weekdays, weekends or days like mon,thu)."
                if self.setting("repeat") is False:
                    return "Repeating reminders are off (Settings, Reminders, repeat); nothing changed."
                rep = {"days": days, **({"until": rep["until"]} if rep and rep.get("until") else {})}
        if str(until or "").strip():
            if not rep:
                return "Only a repeating reminder has an end date; nothing changed."
            try:
                rep["until"] = until_date(until).isoformat()
            except ValueError:
                return f"I couldn't read the end date {until!r}; nothing changed."
        ref = job.key.split(":", 1)[1]
        p.pop("repeat", None)
        p.pop("series", None)
        if rep:
            rep["at"] = f"{new:%H:%M}"
            first = next_time(rep, max(new, now()) - dt.timedelta(seconds=1))
            if first is None:
                return f"Nothing changed: no {repeat_label(rep)} is left."
            new = first
            p.update(repeat=rep, series=ref, ref=occurrence(ref, new))
        else:
            p["ref"] = ref
        p["set_at"] = round(time.time())
        self.app.scheduler.at(new, "reminders.fire", p, key=job.key, module=self.id)
        self._lidsafe_poke()
        self.app.events.emit("reminder_changed", repeat=bool(rep))
        return "Changed: " + self._said(new, what, rep).replace("I'll remind you", "now", 1) + f" (was {was})."

    def _lidsafe(self):
        """Reminders with the lid shut (lidsafe.py), when it's on: your call line holds the next day's reminders."""
        m = self.app.modules.get("lidsafe")
        return m if m is not None and self.app.is_on("lidsafe") else None

    def _lidsafe_poke(self) -> None:
        m = self._lidsafe()
        if m is not None:
            m.poke()

    def _fire(self, p: dict):
        if p.get("series") and not p.get("released") and p.get("lidsafe") != "here":
            self._rearm(p)  # (0.9.2) a series books its next time first, whichever side says this one
        ls = self._lidsafe()
        if ls is not None and ls.handed_over("reminders.fire", p):
            return  # your call line has a sealed copy: whichever side is awake now says it, once (lidsafe.py)
        if self._wait(p):
            return
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
        rows = [[("+10 min", f"rem:{ref}:10"), ("+1 h", f"rem:{ref}:60")]]
        extra = self._addon_buttons(what)
        if extra:
            rows.append(extra)
        self.app.notify(
            f"Reminder{late}: {what}",
            kind="reminder",
            buttons=rows + [[(str(a), str(b)) for a, b in row] for row in p.get("buttons") or []],
            why="reminders.own",
            about=what,
        )
        self.app.events.emit("reminder_fired", late=bool(late))

    def _addon_buttons(self, what: str) -> list[tuple[str, str]]:
        """(reminders.addon_buttons) The buttons features add to this reminder (reminder_buttons(what)): at most
        ADDON_BUTTONS, each a short label and callback data Telegram takes (64 bytes); a feature that fails is
        skipped."""
        if self.setting("addon_buttons") is False:
            return []
        out: list[tuple[str, str]] = []
        for m in self.app.enabled():
            fn = getattr(m, "reminder_buttons", None)
            if m is self or not callable(fn):
                continue
            try:
                got = list(fn(what) or [])
            except Exception as e:
                self.app.events.emit("reminder_buttons_failed", module=m.id, error=type(e).__name__)
                continue
            for b in got:
                if isinstance(b, (tuple, list)) and len(b) == 2 and all(isinstance(x, str) and x for x in b):
                    label, data = b[0][:30], b[1]
                    if len(data.encode("utf-8")) <= 64 and ":" in data:
                        out.append((label, data))
        return out[:ADDON_BUTTONS]

    def _wait(self, p: dict) -> bool:
        """(0.9.0, reminders.wait_for_break) In a Study mode focus (modules/study.py), the reminder waits for its break:
        booked again for when the focus ends. True when it waits."""
        if not self.setting("wait_for_break") or p.get("released"):
            return False
        study = self.app.modules.get("study")
        t = study.timer() if study is not None and self.app.is_on("study") else {}
        if t.get("phase") != "focus" or not t.get("ends"):
            return False
        try:
            ends = dt.datetime.fromisoformat(t["ends"])
        except ValueError:
            return False
        if ends <= now():
            return False
        ref = str(p.get("ref") or uuid.uuid4().hex[:8])
        self.app.scheduler.at(
            ends, "reminders.fire", {**p, "released": True}, key=f"reminders:wait{ref}", module=self.id
        )
        self.app.events.emit("reminder_waits", until=ends.isoformat(timespec="minutes"))
        return True

    def release_waiting(self) -> int:
        """The reminders waiting for a focus's break, now (Study mode's timer was paused, reset or ended)."""
        n = 0
        for j in self.app.scheduler.jobs("reminders:wait"):
            if j.action == "reminders.fire" and self.app.scheduler.cancel(j.key):
                self._fire({**(j.payload or {}), "released": True})
                n += 1
        return n

    def _snoozable(self, ref: str, what: str) -> None:
        from kurooto.core.state import jload, jsave

        f = self.app.paths.state / "reminders-snooze.json"
        d = jload(f, {}) or {}
        d[ref] = what
        jsave(f, dict(list(d.items())[-200:]))

    def callbacks(self):
        return {"rem": self._snooze, "remx": self._cancel, "remk": lambda ref, act: self.skip_next(ref)}

    def _snooze(self, ref: str, act: str) -> str:
        from kurooto.core.state import jload

        what = (jload(self.app.paths.state / "reminders-snooze.json", {}) or {}).get(ref)
        if not what:
            return "That reminder is gone."
        when = now() + dt.timedelta(minutes=int(act or 10))
        self.add(when, what)
        return f"Again at {when:%H:%M}"

    def _cancel(self, ref: str, act: str) -> str:
        j = self.app.scheduler.get(f"reminders:{ref}")
        gone = self.app.scheduler.cancel(f"reminders:{ref}")
        self._lidsafe_poke()
        if gone and j is not None and (j.payload or {}).get("repeat"):
            return "Cancelled, every time of it."
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
        names = self.place_names()
        saved = saved_place(place, names) if names else None  # (0.9.1, place_names) "the lib" -> "Library"
        place = saved or place
        sent = calls.phone.send(Message(what, title=place, kind="place_every" if every else "place"))
        if not sent:
            return "That didn't reach the phone app. Try again in a moment."
        self.app.events.emit("reminder_place", every=every)
        how = "every time you reach" if every else "when you reach"
        if saved:
            return f"Sent to your phone: {how} {place} (saved there), it reminds you: {what}."
        return (
            f"Sent to your phone: {how} {place}, it reminds you: {what}. If {place} isn't saved in the app yet, "
            "save it there once you're at it (Places → Save where you are now)."
        )

    def place_names(self) -> list[str]:
        """(0.9.1, reminders.place_names) The names of the places saved on the phone, as it last sent them; [] while
        the switch is off or none came. Never told to an AI."""
        f = self.app.paths.state / "calls" / "place-names.json"
        if not self.setting("places") or not self.setting("place_names"):
            f.unlink(missing_ok=True)  # turned off: the names the phone sent go too
            return []
        got = jload(f, {}) or {}
        names = got.get("names") if isinstance(got, dict) else None
        return [str(n) for n in names if isinstance(n, str)][:PLACE_NAMES_MAX] if isinstance(names, list) else []

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
            days = repeat_days(rest)  # (0.9.2) "every day at 22:15", "on weekdays", "until friday"
            until = None
            u = UNTIL.search(rest) if days else None
            if u:
                try:
                    until = until_date(u["u"])
                except ValueError:
                    until = None
            if days:
                rest = strip_repeat(rest)
            what = tidy_what(WHEN_WORDS.sub("", WHEN_DAY.sub(" ", rest)))
            return {"when": when, "what": what or "you asked me to remind you", "repeat": days, "until": until}

        def run(msg, s):
            if s.get("ask"):
                return (
                    f"When should I remind you? I didn't set one: the {s['ask']} in that is about what didn't happen "
                    'or what was planned. Say "remind me at 4:30 to …" or "remind me in 20 minutes to …".'
                )
            return self.add(s["when"], s["what"], repeat=s.get("repeat"), until=s.get("until"))

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
                examples=(
                    "remind me at 9 to call mum",
                    "remind me in 20 minutes to take the tea off",
                    "remind me every day at 22:15 to call home",
                ),
            ),
        ]

    def commands(self):
        return [
            Command(
                "remind",
                "a reminder (/remind 21:30 call mum, /remind tomorrow 7am gym; /remind 20 tea: in 20 min; "
                "/remind 22:15 call home every day)",
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
                rest = " ".join(parts[n:])
                days = repeat_days(rest)  # (0.9.2) "/remind 22:15 call home every day"
                what = tidy_what(strip_repeat(rest) if days else rest)
                return self.add(when, what or "you asked me to remind you", repeat=days)
        return (
            "Usage: /remind 21:30 call mum   (or: tomorrow 7am gym, in 20m tea; a bare number is the hour: 9 gym is "
            "the next 9:00)"
        )

    def _list(self, msg: Incoming, arg: str) -> str | None:
        jobs = self.app.scheduler.jobs("reminders:")
        if not jobs:
            return "No reminders set."
        for j in jobs[:15]:
            ref, rep = j.key.split(":", 1)[1], j.payload.get("repeat")
            if rep:  # (0.9.2) a series: listed once, with its next time; Cancel ends it, Skip next skips one
                msg.reply(
                    f"{repeat_label(rep).capitalize()} at {rep.get('at')}  {j.payload.get('what')}  "
                    f"(next {j.when.astimezone():%a %d %b})",
                    buttons=[[("Cancel", f"remx:{ref}:x"), ("Skip next", f"remk:{ref}:x")]],
                )
                continue
            msg.reply(
                f"{j.when.astimezone():%a %d %b %H:%M}  {j.payload.get('what')}",
                buttons=[[("Cancel", f"remx:{ref}:x")]],
            )
        return None

    def help(self):
        return ['"remind me at 9 to …", "remind me every day at 22:15 to …", /remind, /reminders']

    # -------------------------------------------------------------------------------------- on calls
    def call_tools(self):
        repeats = self.setting("repeat") is not False
        params = {"when": arg(), "what": arg("what to remind them of")}
        if repeats:
            params.update(
                repeat=arg('optional, to make it repeat: "daily", "weekdays", "weekends" or days like "mon,thu"'),
                until=arg('optional, the last day of a repeating one: "2026-12-04", "friday", "4 dec"'),
            )
        params["another"] = arg('"yes" only when they want a second reminder with the same words as one just set')
        hint = (
            "add_reminder sets a reminder message; schedule_call is for a reminder call instead. When they correct a "
            'reminder just set ("make it 10:15", "change it to tomorrow"), call change_reminder on it, never '
            "add_reminder again (that leaves two)."
        )
        if repeats:
            hint += (
                ' For "every day", "every weekday", "on Mondays", "from today onwards", give add_reminder repeat (or '
                'change_reminder repeat for one just set: "can you do that every day?"). Never say a reminder repeats '
                'unless the tool\'s result says so ("every day", "on weekdays", "every Mon").'
            )
        change = {
            "key": arg("optional: the reminder's key, when you know it (pending_items, /api today)"),
            "what": arg("optional: words of the reminder's text; leave both out for the one just set"),
            "when": arg(
                'optional: its new time, e.g. "22:15", "10:15" (kept on its day, the reading nearest the old '
                'time), "tomorrow 9am"'
            ),  # fmt: skip
        }
        if repeats:
            change.update(
                repeat=arg('optional: "daily", "weekdays", "weekends", days like "mon,thu", or "once" to stop it'),
                until=arg("optional: the last day of a repeating one"),
            )
        return [
            Tool(
                "add_reminder",
                'A reminder message at a time, e.g. when "18:30", "in 2 hours", "tomorrow 9am"'
                + (", once or repeating (repeat)." if repeats else "."),
                self._tool_add,
                params,
                ("when", "what"),
                offline="queue",
                hint=hint,
            ),
            Tool(
                "change_reminder",
                "Change a reminder already set: its time"
                + (", or make it repeat or stop repeating" if repeats else "")
                + ". Finds it by key or by words of its text (the most recently set first); with neither, the one "
                "set most recently.",
                self._tool_change,
                change,
                (),
                offline="queue",
            ),
        ]

    def _tool_add(self, a: dict) -> str:
        try:
            when = parse_when(str(a.get("when", "")))
        except ValueError:
            return f"I couldn't read the time {a.get('when')!r}."
        what = str(a.get("what") or "a reminder")
        days, until = None, None
        if str(a.get("repeat") or "").strip() and not ONCE.match(str(a["repeat"])):
            days = repeat_days(str(a["repeat"]))
            if days is None:
                return f"I couldn't read how often {a['repeat']!r} is (daily, weekdays, weekends or days like mon,thu)."
        if str(a.get("until") or "").strip() and days:
            try:
                until = until_date(str(a["until"]))
            except ValueError:
                return f"I couldn't read the end date {a['until']!r}."
        if str(a.get("another") or "").strip().lower() not in ("yes", "true", "1"):
            same = [j for j in self.find(recent_s=RECENT_S) if _words(j.payload.get("what")) == _words(what)]
            if same and _words(what):  # (0.9.2) "make it 10:15" sent as a second add_reminder: move the first
                out = self.change(
                    same[0],
                    when=f"{when:%Y-%m-%d %H:%M}",
                    repeat=str(a.get("repeat") or ""),
                    until=str(a.get("until") or "") if days else "",
                )
                return f"{out} That reminder was set a moment ago, so I moved it instead of adding a second."
        return self.add(when, what, repeat=days, until=until)

    def _tool_change(self, a: dict) -> str:
        if not any(str(a.get(k) or "").strip() for k in ("when", "repeat", "until")):
            return "Say what to change: its time (when), how often (repeat) or its last day (until)."
        hits = self.find(str(a.get("key") or ""), str(a.get("what") or ""))
        if not hits:
            left = "; ".join(f"{j.when.astimezone():%a %H:%M} {j.payload.get('what')}" for j in self._jobs()[:6])
            return "I couldn't find that reminder; nothing changed." + (f" Set now: {left}." if left else "")
        return self.change(hits[0], str(a.get("when") or ""), str(a.get("repeat") or ""), str(a.get("until") or ""))

    def call_brief(self) -> dict:
        soon = [j for j in self.app.scheduler.jobs("reminders:") if j.next_run < time.time() + 86400]
        if not soon:
            return {}
        return {
            "reminders_next_24h": [
                f"{dt.datetime.fromtimestamp(j.next_run):%a %H:%M} {j.payload.get('what', '')}"
                + (f" ({repeat_label(j.payload['repeat'])})" if j.payload.get("repeat") else "")
                for j in soon[:8]
            ]
        }
