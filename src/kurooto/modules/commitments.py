"""Commitments: the regular things in your week that aren't classes (the gym, a shift, a standup, tuition you
teach), each on its days and hours. Like a class, one holds calls while it's on (commitments.no_calls), and you can
skip one for a day. They also come from what you say: "every Tuesday and Thursday at 7pm I go to the gym" adds one,
with Undo (core/infer.py). (Not the same as Skills' routines: /every runs a skill on a schedule.)

    /busy                                     your commitments, and today's
    /busy add gym mon,wed,fri 18:00-19:00     days: mon,wed / weekdays / weekends / daily / mon-fri
    /busy remove gym
    /busy skip gym                            not today (calls are allowed then); /busy unskip gym
    /busy calls gym off                       it doesn't hold calls (on to undo)
"""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day

register_defaults(
    "commitments",
    {
        "items": [],  # {"name": "gym", "days": ["mon", "wed"], "start": "18:00", "end": "19:00", "calls": true}
        "no_calls": True,  # no calls during a commitment (each one can opt out: /busy calls gym off)
    },
)
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GROUPS = {
    "daily": DAYS, "everyday": DAYS, "every day": DAYS, "day": DAYS, "days": DAYS,
    "weekday": DAYS[:5], "weekdays": DAYS[:5],
    "weekend": DAYS[5:], "weekends": DAYS[5:],
}  # fmt: skip
HM = re.compile(r"(\d{1,2}):(\d{2})")


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
            )
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
            )
        ]

    # ------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        rs = self.on()
        return {"commitments_today": [f"{r['start']}-{r['end']} {r['name']}" for r in rs]} if rs else {}

    def call_tools(self):
        return [
            Tool(
                "skip_commitment",
                "They're skipping this commitment today (the gym, a shift); calls are allowed during it.",
                self._tool_skip,
                {"name": arg("e.g. gym")},
                ("name",),
                offline="queue",
            )
        ]

    def _tool_skip(self, a: dict) -> str:
        r = self.find(str(a.get("name", "")))
        return self._skip(r, True, now().date()) if r else "I don't know that one."
