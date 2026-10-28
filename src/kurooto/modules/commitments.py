"""Commitments: the regular things in your week that aren't classes (the gym, a shift, a standup, tuition you
teach), each on its days and hours. Like a class, one holds calls while it's on (commitments.no_calls), and you can
skip one for a day. They also come from what you say: "every Tuesday and Thursday at 7pm I go to the gym" adds one,
with Undo (core/infer.py). (Not the same as Skills' routines: /every runs a skill on a schedule.)

    /busy                                     your commitments, and today's
    /busy add gym mon,wed,fri 18:00-19:00     days: mon,wed / weekdays / weekends / daily / mon-fri
    /busy remove gym
    /busy skip gym                            not today (calls are allowed then); /busy unskip gym
    /busy calls gym off                       it doesn't hold calls (on to undo)

Hooks: a word of yours that starts a hold. "when I say gym, hold calls 90 min" (or "when I say lab, hold everything
2 h") keeps the word; later, "gym" on its own holds calls for 90 minutes (as /hold does; "everything" is focus, as
/focus does: calls and messages that aren't urgent wait). Only the word alone does it: "I'm off to the gym" is an
ordinary message. Each step has Undo. A hook never sets or moves an alarm and never sends anything to anyone.

    /hooks                                    your hooks
    /hooks drop gym                           forget one (with Undo)
"""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Answer, Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day, a_minutes

register_defaults(
    "commitments",
    {
        "items": [],  # {"name": "gym", "days": ["mon", "wed"], "start": "18:00", "end": "19:00", "calls": true}
        "no_calls": True,  # no calls during a commitment (each one can opt out: /busy calls gym off)
        "hooks": [],  # {"word": "gym", "hold": "calls" or "all", "minutes": 90}: "gym" alone starts that hold
    },
)
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GROUPS = {
    "daily": DAYS, "everyday": DAYS, "every day": DAYS, "day": DAYS, "days": DAYS,
    "weekday": DAYS[:5], "weekdays": DAYS[:5],
    "weekend": DAYS[5:], "weekends": DAYS[5:],
}  # fmt: skip
HM = re.compile(r"(\d{1,2}):(\d{2})")
# "when I say gym, hold calls 90 min", "whenever I say 'lab' hold everything for 2 hours"
HOOK = re.compile(
    r"^\s*(?:when(?:ever)?|if)\s+i\s+(?:say|type|send|write)\s+[\"'‘“]?(?P<word>[a-z][a-z0-9-]*(?:\s+[a-z0-9-]+){0,2}?)"
    r"[\"'’”]?\s*[,:;–-]?\s*(?:then\s+)?(?P<what>(?:please\s+)?(?:hold|no|mute|silence|block|focus|do not disturb|dnd|"
    r"don'?t)\b.*)$",
    re.I,
)
HOLD_ALL = re.compile(r"\b(?:everything|all of it|messages|notifications|focus|do not disturb|dnd)\b", re.I)
HOLD_CALLS = re.compile(r"\b(?:calls?|ringing|ring)\b", re.I)
NOT_HOOK = {"yes", "no", "ok", "okay", "done", "stop", "help", "thanks", "hi", "hello", "undo", "skip", "later"}
HOLDS = {"calls": "calls", "all": "everything (focus)"}


def parse_days(text: str) -> list[str]:
    """ "mon,wed,fri" / "Tuesday and Thursday" / "weekdays" / "mon-fri" -> ["mon", ...] in week order; [] if unsure."""
    low = " ".join(text.lower().replace("&", " and ").split())
    if low in GROUPS:
        return list(GROUPS[low])
    r = re.fullmatch(r"([a-z]{3})[a-z]*\s*(?:-|–|to)\s*([a-z]{3})[a-z]*", low)
    if r and r[1] in DAYS and r[2] in DAYS:
        a, b = DAYS.index(r[1]), DAYS.index(r[2])
        return sorted({DAYS[i % 7] for i in range(a, a + (b - a) % 7 + 1)}, key=DAYS.index)
    out = []
    for w in re.split(r"\s*(?:,|\band\b|\s)\s*", low):
        w = w.strip()
        if not w:
            continue
        if w[:3] not in DAYS:
            return []
        out.append(w[:3])
    return sorted(set(out), key=DAYS.index)


def days_text(days: list[str]) -> str:
    for word, group in (("daily", DAYS), ("weekdays", DAYS[:5]), ("weekends", DAYS[5:])):
        if tuple(days) == group:
            return word
    return ", ".join(d.title() for d in days)


def _mins(m: int) -> str:
    return f"{m // 60} h" if m % 60 == 0 else f"{m} min" if m < 120 else f"{m // 60} h {m % 60} min"


def _hm(s: str) -> str | None:
    m = HM.fullmatch(s.strip())
    return f"{int(m[1]):02d}:{m[2]}" if m and int(m[1]) < 24 and int(m[2]) < 60 else None


class Commitments(Module):
    id = "commitments"
    title = "Commitments"
    description = (
        "The regular things in your week that aren't classes (gym, shifts, standups, tuition), so calls wait for "
        "them; you can skip one for a day."
    )

    def start(self):
        self.app.availability.blockers["commitments"] = self._block

    def stop(self):
        super().stop()
        self.app.availability.blockers.pop("commitments", None)

    # ------------------------------------------------------------------------------------------ data
    def items(self) -> list[dict]:
        return [r for r in self.setting("items") or [] if r.get("name") and r.get("days")]

    def find(self, name: str) -> dict | None:
        n = " ".join(name.lower().split())
        return next((r for r in self.items() if r["name"].lower() == n), None) or next(
            (r for r in self.items() if n and (n in r["name"].lower() or r["name"].lower() in n)), None
        )

    def add(self, name: str, days: list[str], start: str, end: str, calls: bool = True) -> dict:
        row = {"name": name, "days": days, "start": start, "end": end, "calls": calls}
        keep = [r for r in self.setting("items") or [] if r.get("name", "").lower() != name.lower()]
        self.app.settings.set("commitments.items", [*keep, row])
        return row

    def remove(self, name: str) -> dict | None:
        r = self.find(name)
        if r:
            self.app.settings.set("commitments.items", [x for x in self.setting("items") or [] if x != r])
        return r

    def _skip_file(self, day: dt.date):
        return self.app.paths.state / "commitments" / f"skip-{day.isoformat()}.json"

    def skipped(self, day: dt.date | None = None) -> set[str]:
        return set(jload(self._skip_file(day or now().date()), []) or [])

    def set_skip(self, name: str, add: bool = True, day: dt.date | None = None) -> set[str]:
        day = day or now().date()
        cur = self.skipped(day)
        cur = cur | {name} if add else cur - {name}
        jsave(self._skip_file(day), sorted(cur))
        return cur

    def on(self, day: dt.date | None = None, include_skipped: bool = False) -> list[dict]:
        """A day's commitments, in time order, with start_dt and end_dt (an end before the start runs past midnight)."""
        day = day or now().date()
        skip = set() if include_skipped else self.skipped(day)
        out = []
        for r in self.items():
            if DAYS[day.weekday()] not in r["days"] or r["name"] in skip:
                continue
            s = dt.datetime.combine(day, dt.time.fromisoformat(r["start"]))
            e = dt.datetime.combine(day, dt.time.fromisoformat(r["end"]))
            out.append({**r, "start_dt": s, "end_dt": e if e > s else e + dt.timedelta(days=1)})
        return sorted(out, key=lambda r: r["start_dt"])

    def _block(self, t: dt.datetime):
        if not self.setting("no_calls"):
            return None
        for day in (t.date() - dt.timedelta(days=1), t.date()):  # yesterday's night shift may still be on
            for r in self.on(day):
                if r.get("calls", True) and r["start_dt"] <= t < r["end_dt"]:
                    return f"commitment: {r['name']}", r["end_dt"]
        return None

    # -------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "busy",
                "your gym, shifts, standups (they hold calls): /busy add gym mon,wed,fri 18:00-19:00 (skip, remove)",
                self._cmd,
            ),
            Command("hooks", 'your hook words ("when I say gym, hold calls 90 min"); /hooks drop gym', self._hooks_cmd),
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        a = arg.strip()
        m = re.fullmatch(r"(?i)add\s+(?P<rest>.+?)\s+(?P<s>\d{1,2}:\d{2})\s*[-–]\s*(?P<e>\d{1,2}:\d{2})", a)
        if m:
            words, start, end = m["rest"].split(), _hm(m["s"]), _hm(m["e"])
            # the first split whose remaining words are all days: "night shift daily" -> "night shift", daily
            name, days = next(
                ((" ".join(words[:i]), d) for i in range(1, len(words)) if (d := parse_days(" ".join(words[i:])))),
                ("", []),
            )
            if not name or not start or not end:
                return "Usage: /busy add gym mon,wed,fri 18:00-19:00   (days: weekdays, weekends, daily, mon-fri)"
            r = self.add(name, days, start, end)
            return f"Added {r['name']}: {days_text(days)} {start}–{end}. Calls wait while it's on."
        m = re.fullmatch(r"(?i)(?P<verb>remove|delete|rm|skip|unskip)\s+(?P<name>.+)", a)
        if m:
            verb, r = m["verb"].lower(), self.find(m["name"])
            if not r:
                return f"Nothing called {m['name']} (/busy lists them)."
            if verb in ("remove", "delete", "rm"):
                self.remove(r["name"])
                return f"Removed {r['name']}."
            return self._skip(r, verb == "skip", now().date())
        m = re.fullmatch(r"(?i)calls\s+(?P<name>.+?)\s+(?P<v>on|off)", a)
        if m:
            r = self.find(m["name"])
            if not r:
                return f"Nothing called {m['name']}."
            self.add(r["name"], r["days"], r["start"], r["end"], calls=m["v"].lower() == "on")
            return f"{r['name']} {'holds' if m['v'].lower() == 'on' else 'no longer holds'} calls."
        if a:
            return "Usage: /busy add gym mon,wed,fri 18:00-19:00 | remove gym | skip gym | calls gym off"
        return self.listing()

    def listing(self) -> str:
        items = self.items()
        if not items:
            return (
                "No commitments yet. /busy add gym mon,wed,fri 18:00-19:00, or say "
                '"every Monday at 6pm I go to the gym".'
            )
        skip = self.skipped()
        rows = [
            f"{r['name']}: {days_text(r['days'])} {r['start']}–{r['end']}"
            + ("" if r.get("calls", True) else " (calls allowed)")
            + (" (skipping today)" if r["name"] in skip else "")
            for r in sorted(items, key=lambda r: (DAYS.index(r["days"][0]), r["start"]))
        ]
        return "Your commitments:\n" + "\n".join(rows)

    def _skip(self, r: dict, add: bool, day: dt.date) -> str:
        self.set_skip(r["name"], add, day)
        self.app.events.emit("commitment_skip" if add else "commitment_unskip", name=r["name"])
        when = "today" if day == now().date() else f"on {day:%a %d %b}"
        return f"Skipping {r['name']} {when}; calls are allowed then." if add else f"{r['name']} is back on {when}."

    def intents(self):
        def match(text: str):
            if not re.search(r"\b(skip(?:ping)?|not going to|missing|bunking)\b", text, re.I):
                return None
            if re.match(r"\s*(?:can|could|should|may|shall)\s+i\b", text, re.I):
                return None
            found = [r for r in self.items() if re.search(rf"(?i)\b{re.escape(r['name'])}\b", text)]
            day = a_day(text)
            return {"name": found[0]["name"], "day": day} if len(found) == 1 and day else None

        return [
            Intent(
                "skip_commitment",
                "skipping a commitment (the gym today, tomorrow's shift)",
                match,
                lambda m, s: self._skip(self.find(s["name"]), True, s["day"]),
                examples=("skipping the gym today",),
            ),
            Intent(
                "hook",
                'a hook: a word that starts a hold ("gym" alone, once set)',
                self._hook_match,
                self._hook_run,
                questions=True,  # "when I say ..." reads like a question to the rules; "gym?" never matches
                examples=("when I say gym, hold calls 90 min", "when I say lab, hold everything 2 h"),
            ),
        ]

    # ------------------------------------------------------------------------------------------ hooks
    def hooks(self) -> list[dict]:
        return [h for h in self.setting("hooks") or [] if h.get("word") and h.get("minutes")]

    def _hook(self, word: str) -> dict | None:
        return next((h for h in self.hooks() if h["word"] == word), None)

    def _put_hook(self, word: str, row: dict | None) -> None:
        """Set (or, with None, remove) the hook for a word, keeping the others in their order."""
        keep = [h for h in self.setting("hooks") or [] if h.get("word") != word]
        self.app.settings.set("commitments.hooks", keep + ([row] if row else []))

    @property
    def _undo_file(self):
        return self.app.paths.state / "commitments" / "hooks-undo.json"

    def _remember(self, word: str, act: str, data) -> None:
        """What Undo puts back, per word and step (add: the hook it replaced; drop: the hook; hold: the hold before)."""
        undo = jload(self._undo_file, {}) or {}
        undo.setdefault(word, {})[act] = data
        jsave(self._undo_file, undo)

    def _hook_match(self, text: str):
        m = HOOK.match(text)
        if m:
            word = " ".join(m["word"].lower().strip("'\"‘’“” -").split())
            what, mins = m["what"], a_minutes(m["what"])
            kind = "all" if HOLD_ALL.search(what) else "calls" if HOLD_CALLS.search(what) else ""
            usage = 'Say it like "when I say gym, hold calls 90 min" (or "hold everything 2 h").'
            if not word or word in NOT_HOOK or len(word) > 30:
                return {"bad": f'"{word}" is too common a word for a hook. {usage}'}
            if not kind:
                return {"bad": f"Hold calls, or everything? {usage}"}
            if not mins:
                return {"bad": f"For how long? {usage}"}
            return {"word": word, "hold": kind, "minutes": max(1, min(24 * 60, mins))}
        said = " ".join(text.strip().rstrip(".!").lower().split())  # the word on its own, nothing more
        return {"fire": said} if said and self._hook(said) else None

    def _hook_run(self, msg: Incoming | None, s: dict) -> str:
        if s.get("bad"):
            return s["bad"]
        if s.get("fire"):
            return self.fire_hook(s["fire"])
        return self.add_hook(s["word"], s["hold"], s["minutes"])

    def add_hook(self, word: str, hold: str, minutes: int) -> Answer:
        before = self._hook(word)
        self._put_hook(word, {"word": word, "hold": hold, "minutes": minutes})
        self._remember(word, "add", before)
        self.app.events.emit("hook_added", hold=hold, minutes=minutes, replaced=bool(before))
        return Answer(
            f'Hook set: "{word}" on its own holds {HOLDS[hold]} for {_mins(minutes)}. /hooks lists them.',
            [[("Undo", f"hook:{word}:unadd")]],
        )

    def drop_hook(self, word: str) -> Answer | str:
        h = self._hook(" ".join(word.lower().split()))
        if not h:
            return f'No hook "{word}". /hooks lists them.'
        self._put_hook(h["word"], None)
        self._remember(h["word"], "drop", h)
        self.app.events.emit("hook_dropped")
        return Answer(f'Hook "{h["word"]}" dropped.', [[("Undo", f"hook:{h['word']}:undrop")]])

    def fire_hook(self, word: str) -> Answer | str:
        """The word said on its own: the hold starts now (a longer hold already on is kept). Undo puts back what was
        there before."""
        h = self._hook(word)
        if not h:
            return f'No hook "{word}".'
        a, until = self.app.availability, now() + dt.timedelta(minutes=h["minutes"])
        file = "focus.json" if h["hold"] == "all" else "quiet.json"
        before = a._until(file, None)
        until = max(until, before) if before else until
        if h["hold"] == "all":
            a.set_focus(until)
            if self.app.is_on("telegram"):  # what waited comes when it ends, as after /focus
                self.app.scheduler.at(until, "telegram.focus_end", key="telegram:focus-end", module="telegram")
            text = f"{word}: focus until {until:%H:%M}; calls and messages that aren't urgent wait. /focus off ends it."
        else:
            a.set_quiet(until, reason=f"hook: {word}")
            text = f"{word}: no calls until {until:%H:%M}. Messages still come. /calls lifts it."
        self._remember(
            word, "hold", {"file": file, "until": until.isoformat(), "before": before.isoformat() if before else None}
        )
        self.app.events.emit("hook_fired", hold=h["hold"], minutes=h["minutes"])
        return Answer(text, [[("Undo", f"hook:{word}:unhold")]])

    def _hook_button(self, word: str, act: str) -> str:
        last = (jload(self._undo_file, {}) or {}).get(word) or {}
        if act == "unadd" and "add" in last:
            self._put_hook(word, last.pop("add"))
            out = "Hook undone." if not self._hook(word) else f'"{word}" is back to what it was.'
        elif act == "undrop" and last.get("drop"):
            self._put_hook(word, last.pop("drop"))
            out = f'Hook "{word}" is back.'
        elif act == "unhold" and last.get("hold"):
            out = self._unhold(last.pop("hold"))
        else:
            return "Nothing to undo."
        undo = jload(self._undo_file, {}) or {}
        undo[word] = last
        jsave(self._undo_file, undo)
        self.app.events.emit("hook_undone", step=act)
        return out

    def _unhold(self, h: dict) -> str:
        a = self.app.availability
        now_until = a._until(h["file"], None)
        if now_until is None or now_until.isoformat() != h["until"]:
            return "That hold has already changed or ended."
        before = dt.datetime.fromisoformat(h["before"]) if h.get("before") else None
        if h["file"] == "focus.json":
            a.set_focus(before)
            if before is None:
                self.app.notifier.flush_queue()
            elif self.app.is_on("telegram"):
                self.app.scheduler.at(before, "telegram.focus_end", key="telegram:focus-end", module="telegram")
            return "Focus is back to what it was." if before else "Focus off."
        a.set_quiet(before)
        return f"Calls held until {before:%H:%M} again." if before else "Calls are allowed again."

    def _hooks_cmd(self, msg: Incoming, arg: str) -> str:
        m = re.fullmatch(r"(?i)(?:drop|remove|delete|rm|forget)\s+(.+)", arg.strip())
        if m:
            return self.drop_hook(m[1].strip().strip("\"'"))  # an Answer: its Undo goes with it
        if arg.strip():
            return 'Usage: /hooks, /hooks drop gym. To add one, say "when I say gym, hold calls 90 min".'
        hooks = self.hooks()
        if not hooks:
            return 'No hooks yet. Say "when I say gym, hold calls 90 min" and "gym" alone will hold calls.'
        rows = [f'"{h["word"]}": holds {HOLDS.get(h.get("hold"), "calls")} for {_mins(h["minutes"])}' for h in hooks]
        return "Your hooks (say the word on its own):\n" + "\n".join(rows) + "\n/hooks drop <word> forgets one."

    def callbacks(self):
        return {"hook": self._hook_button}

    # ------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        rs = self.on()
        return {"commitments_today": [f"{r['start']}-{r['end']} {r['name']}" for r in rs]} if rs else {}

    def call_tools(self):
        return [
            Tool(
                "skip_commitment",
                "They're skipping these commitments today (the gym, a shift; never classes); calls are allowed during "
                'them. One call for any number: names lists them, ["all"] is every commitment today.',
                self._tool_skip,
                {
                    "name": arg("one, e.g. gym"),
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'several at once, or ["all"] for all of today\'s',
                    },
                },
                offline="queue",
            )
        ]

    def _tool_skip(self, a: dict) -> str:
        """One commitment (name, as before 0.8.17), several (names) or all of today's, in one call."""
        want = a.get("names")
        want = [str(x) for x in want] if isinstance(want, list) else [str(want)] if want else []
        if a.get("name"):
            want.append(str(a["name"]))
        today = now().date()
        if any(x.strip().lower() in ("all", "everything", "today") for x in want):
            rows = self.on(today, include_skipped=True)
            if not rows:
                return "There are no commitments today."
        else:
            rows = list({r["name"]: r for r in (self.find(x) for x in want) if r}.values())
        if not rows:
            return "I don't know that one."
        if len(rows) == 1:
            return self._skip(rows[0], True, today)
        for r in rows:
            self._skip(r, True, today)
        return f"Skipping {', '.join(r['name'] for r in rows)} today; calls are allowed then."
