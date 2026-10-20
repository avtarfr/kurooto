"""Attendance and standing: how many classes you've been to in each course, checked against its rule (75% unless you
say otherwise), and how many more you can miss. It's an estimate, and off until you turn it on.

Every class on your timetable (/class, and the term note's) counts as attended unless you /skip it; holidays, exam
periods and the days after the last day of classes don't count, and neither do calendar events. Labs are counted on
their own, with their own rule: a subject whose name says lab or practical is one, and so is a timetable slot you mark.

    /attendance                    each course: "Linear Algebra 82% (23/28), you can miss 3 more this term"
    /attendance la                 one course, in more detail
    /attendance set la 23/30       the official count as of now (classes from now on count on top of it)
    /attendance rule la 80         a course's rule (/attendance rule labs 100, /attendance rule 75 for every course)
    /attendance lab thu 14:00      that slot is the lab of its subject (/attendance lab thu 14:00 off undoes it)
    /attendance since 2026-08-03   count from the term's first day (by default, from the day you turned this on)
    /standing                      attendance and, once you've set them up, marks
    /marks la weights midsem 30, quizzes 20, endsem 50     /marks la midsem 21/30     /marks grades A 85, B 70

"You can miss" counts the rest of the term when the last day of classes is known (/term ends): miss that many and go
to every other class, and the term ends on the line. Without it, it's how many you can miss in a row from now. /skip
asks before a skip would take a course under its line (Skip anyway / Don't skip; "/skip la anyway" doesn't ask), and
the Sunday summary carries one line. Marks come second: what you'd need on what's left (usually the end-sem) for each
grade line, also an estimate.

The count drifts from the official register (a cancelled class, an extra one, a skip you didn't tell Kurooto about):
/attendance set puts it right. Nothing leaves this computer; corrections and marks are in the state folder
(attendance/), and turning the feature off keeps them.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import uuid
from dataclasses import dataclass
from fractions import Fraction

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day

register_defaults(
    "attendance",
    {
        "min_pct": 75,  # a course's rule: the share of its classes you must attend, unless `rules` says otherwise
        "lab_min_pct": 75,  # the rule for labs, which are counted on their own
        "rules": {},  # a course's own rule: {"la": 80, "la:lab": 100}
        "lab_slots": [],  # timetable slots that are the lab of their subject: ["thu 14:00"]
        "since": "",  # count classes from this day ("2026-08-03"); filled in with the day you turn it on
        "weekly": True,  # one line in the Sunday summary
        "grades": {},  # grade lines for /standing, % of a course's total: {"A": 85, "B": 70, "C": 55, "D": 40}
    },
)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LAB = re.compile(r"\b(?:labs?|laborator(?:y|ies)|practicals?)\b", re.I)
AHEAD_DAYS = 14  # without a last day of classes, skips you've already planned this far ahead count
FRACTION = r"(?P<a>\d+(?:\.\d+)?)\s*(?:/|of|out of)\s*(?P<b>\d+(?:\.\d+)?)"
CLEAR = ("clear", "off", "reset", "none", "default")
HOW_MARKS = """Marks, an estimate from what you type in:
1. Each course's weightage: /marks la weights midsem 30, quizzes 20, endsem 50
2. Scores as they come: /marks la midsem 21/30
3. Grade lines, once for every course: /marks grades A 85, B 70, C 55, D 40 (or one course's own: /marks la grades \
A 80, B 65)
/standing then shows what you'd need on what's left (usually the end-sem) for each grade. /marks la shows one course,
/marks la clear forgets it."""


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "es" if word.endswith("s") else "s")


def number(x: float) -> str:
    """21.0 -> "21", 21.25 -> "21.2"."""
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


@dataclass
class Course:
    """One course's count: a subject, or the lab part of one."""

    key: str  # the subject's slug, or "<slug>:lab"
    slug: str
    name: str
    short: str  # "LA", or the name when there's no short name
    lab: bool
    rule: int  # its rule, in percent (0: none)
    held: int = 0  # classes so far (with your correction, if you set one)
    attended: int = 0
    left: int | None = None  # classes still to come this term; None: the last day of classes isn't known
    planned: int = 0  # classes to come that you've already said you'll skip
    ended: bool = False  # the term's classes are over
    set_at: str = ""  # when /attendance set last corrected it

    @property
    def pct(self) -> int | None:
        return self.attended * 100 // self.held if self.held else None

    def spare(self) -> int | None:
        """How many more classes you can miss and still end on the line (negative: you're under it; None: no rule)."""
        if self.rule <= 0:
            return None
        r = Fraction(self.rule, 100)
        if self.left is not None:
            return math.floor(self.attended + self.left - self.planned - r * (self.held + self.left))
        return math.floor(Fraction(self.attended) / r - self.held - self.planned)

    def state(self) -> tuple:
        return self.held, self.attended, self.left, self.planned

    def line(self) -> str:
        """ "Linear Algebra 82% (23/28), you can miss 3 more this term", or where it's short of its rule."""
        head = f"{self.name} {self.pct}% ({self.attended}/{self.held})" if self.held else f"{self.name}: no classes yet"
        k = self.spare()
        if k is None:
            return f"{head}, no rule set"
        if self.ended:
            return f"{head}, the term's classes are over" + (f" (under {self.rule}%)" if k < 0 else "")
        plan = f" (besides the {self.planned} you've said you'll skip)" if self.planned else ""
        if not self.held and self.left is None:
            return head
        if k >= 0:
            if not self.held:
                return f"{head}; you can miss {k} of the {self.left} this term{plan}" if self.left else head
            if self.left is not None and (self.pct or 0) < self.rule:
                return f"{head}, under {self.rule}% for now; you can still miss {k} more this term{plan}"
            return f"{head}, you can miss {k} more" + (" this term" if self.left is not None else "") + plan
        if self.left is not None:
            best = (self.attended + self.left) * 100 // (self.held + self.left)
            if self.planned and best >= self.rule:
                return f"{head}: the {plural(self.planned, 'class')} you've said you'll skip take it under {self.rule}%"
            return f"{head}: under {self.rule}% at the end of term even going to every class left (at most {best}%)"
        if self.rule >= 100:
            return f"{head}: under {self.rule}%, which it can't get back to"
        r = Fraction(self.rule, 100)
        need = math.ceil((r * (self.held + self.planned) - self.attended) / (1 - r))
        return f"{head}: under {self.rule}%; go to the next {need} to get back" + (
            f" (with the {self.planned} you've said you'll skip)" if self.planned else ""
        )

    def brief(self) -> str:
        """For the Sunday summary: "LA 82%, 3 to spare"."""
        k = self.spare()
        if k is None or self.ended:
            return f"{self.short} {self.pct}%"
        return f"{self.short} {self.pct}%, " + (f"{k} to spare" if k >= 0 else f"under {self.rule}%")


def grade_ranges(earned: float, left: float, total: float, grades: dict) -> list[str]:
    """What you'd need on what's left for each grade line, best grade first: ["A out of reach", "B 77%+",
    "C 47-76%", "D 17-46%", "under 17%: below D"]. Lines are % of the total."""
    out: list[str] = []
    upper = None  # the better grade's need (a whole percent of what's left), when it's within reach
    last = None
    for g, line in sorted(grades.items(), key=lambda kv: -float(kv[1])):
        need = math.ceil((float(line) * total / 100 - earned) / left * 100 - 1e-9)
        if need > 100:
            out.append(f"{g} out of reach")
            continue
        if need <= 0:
            out.append(f"{g} whatever you get" if upper is None else f"{g} under {upper}%")
            return out
        out.append(f"{g} {need}%+" if upper is None else f"{g} {need}-{upper - 1}%")
        upper, last = need, g
    if last is not None:
        out.append(f"under {upper}%: below {last}")
    return out


class Attendance(Module):
    id = "attendance"
    title = "Attendance and standing"
    description = "Classes attended per course against its rule, how many more you can miss, and marks (an estimate)."
    requires = ("subjects",)
    privacy = "Stays on this computer: counted from your timetable and skips; corrections and marks are kept here."

    def start(self):
        if not self.setting("since"):  # count from the day it was turned on, unless you say otherwise
            self.app.settings.set("attendance.since", now().date().isoformat())

    def _subjects(self):
        return self.app.modules["subjects"]

    @property
    def _dir(self):
        return self.app.paths.state / "attendance"

    def health(self) -> tuple[bool, str]:
        if not self._subjects().timetable():
            return False, "no classes on your timetable, so nothing is counted (/class mon 09:00-09:55 la)"
        return True, ""

    def health_check(self):
        from kurooto.core.health import Check

        def probe(net: bool):
            ok, why = self.health()
            return ok, why

        return Check(
            "attendance",
            "Attendance",
            probe=probe,
            kind="setup",
            help="Add your classes (/class mon 09:00-09:55 la), or read them from a note (/term note <note>).",
        )

    # ---------------------------------------------------------------------------------------- counting
    def since(self) -> dt.date:
        try:
            return dt.date.fromisoformat(str(self.setting("since") or ""))
        except ValueError:
            return now().date()

    def _fixes(self) -> dict:
        return jload(self._dir / "counts.json", {}) or {}

    def _rule(self, key: str, lab: bool) -> int:
        rules = self.setting("rules") or {}
        try:
            return int(rules[key]) if key in rules else int(self.setting("lab_min_pct" if lab else "min_pct") or 0)
        except (TypeError, ValueError):
            return 75

    def courses(self, extra: frozenset | set = frozenset()) -> dict[str, Course]:
        """Every course with classes on the timetable (or a correction), counted up to now. `extra`: (day, subject)
        pairs to count as skipped as well, for "what if I skip it"."""
        subj = self._subjects()
        t = now()
        today = t.date()
        rows = [r for r in subj.timetable() if r.get("day") in DAYS]
        holidays = set(subj.holidays())
        periods = [(str(p[0]), str(p[1])) for p in subj.exam_periods()]
        try:
            ends = subj.term_ends()
            last = dt.date.fromisoformat(ends) if ends else None
        except ValueError:
            last = None
        info = {s["slug"]: s for s in subj.subjects()}
        labs = {" ".join(str(x).lower().split()) for x in self.setting("lab_slots") or []}
        fixes = self._fixes()
        out: dict[str, Course] = {}

        def course(slug: str, slot_lab: bool) -> Course:
            s = info.get(slug) or {"name": slug, "aliases": []}
            own = bool(LAB.search(s["name"]) or LAB.search(slug.replace("-", " ")))
            key = f"{slug}:lab" if slot_lab and not own else slug
            if key not in out:
                short = next((a.upper() for a in s.get("aliases", []) if len(a) <= 4), s["name"])
                part = " lab" if key.endswith(":lab") else ""
                out[key] = Course(
                    key, slug, s["name"] + part, short + part, own or bool(part), self._rule(key, own or bool(part))
                )
                out[key].left = 0 if last is not None else None
                out[key].ended = last is not None and today > last
            return out[key]

        cut = {}
        for key, f in fixes.items():
            slug, _, part = key.partition(":")
            c = course(slug, part == "lab")
            try:
                cut[c.key] = dt.datetime.fromisoformat(f["at"])
                c.held, c.attended, c.set_at = int(f["held"]), int(f["attended"]), f["at"]
            except (KeyError, TypeError, ValueError):
                continue
        days_extra = [dt.date.fromisoformat(d) for d, _ in extra]
        horizon = last if last is not None else max([today + dt.timedelta(days=AHEAD_DAYS), *days_extra])
        d = self.since()
        while d <= horizon and rows:
            iso = d.isoformat()
            todays = [r for r in rows if DAYS.index(r["day"]) == d.weekday()]
            if todays and iso not in holidays and not any(a <= iso <= b for a, b in periods):
                skipped = subj.skipped(d) | {s for day, s in extra if day == iso}
                for r in todays:
                    try:
                        end = dt.datetime.combine(d, dt.time.fromisoformat(r["end"]))
                    except (KeyError, ValueError):
                        continue
                    c = course(r["subject"], f"{r['day']} {r['start']}" in labs)
                    if c.key in cut and end <= cut[c.key]:
                        continue  # in the official count you set
                    missed = r["subject"] in skipped
                    if end <= t:
                        c.held += 1
                        c.attended += 0 if missed else 1
                    else:
                        if c.left is not None:
                            c.left += 1
                        c.planned += 1 if missed else 0
            d += dt.timedelta(days=1)
        return out

    @staticmethod
    def ordered(cs: dict[str, Course]) -> list[Course]:
        """Closest to its line first."""
        return sorted(cs.values(), key=lambda c: (c.spare() is None, c.spare() or 0, c.name.lower()))

    def _key(self, text: str) -> str | None:
        """'la', 'Linear Algebra', 'la lab' -> the course's key."""
        t = " ".join(text.lower().replace(":", " ").split())
        subj = self._subjects()
        slug = subj.resolve(t)
        if slug:
            return slug
        m = re.fullmatch(r"(.+?) (?:labs?|practicals?)", t)
        slug = subj.resolve(m[1]) if m else None
        if not slug:
            return None
        own = LAB.search(subj.name_of(slug)) or LAB.search(slug.replace("-", " "))
        return slug if own else f"{slug}:lab"

    def typed(self, key: str) -> str:
        """How you'd type a course in a command: its first short name ("la", "la lab"), else its slug."""
        slug, _, part = key.partition(":")
        s = next((x for x in self._subjects().subjects() if x["slug"] == slug), None)
        return next(iter((s or {}).get("aliases") or []), slug) + (" lab" if part else "")

    def _split(self, text: str) -> tuple[str | None, str]:
        """'linear algebra midsem 21/30' -> ("linear-algebra", "midsem 21/30"): the longest start that's a subject."""
        words = text.split()
        for n in range(min(4, len(words)), 0, -1):
            slug = self._subjects().resolve(" ".join(words[:n]))
            if slug:
                return slug, " ".join(words[n:])
        return None, text

    # ----------------------------------------------------------------------------------------- /skip
    def if_skipped(self, slugs: list[str], day: dt.date) -> tuple[list[Course], list[Course]]:
        """The courses a skip of these subjects on that day changes, as they'd be after it, and the ones of them it
        leaves under their rule. Subjects already skipped that day change nothing."""
        new = [s for s in slugs if s not in self._subjects().skipped(day)]
        if not new:
            return [], []
        before = self.courses()
        after = self.courses(frozenset((day.isoformat(), s) for s in new))
        hit = [c for k, c in after.items() if k not in before or before[k].state() != c.state()]
        bad = [c for c in hit if (c.spare() if c.spare() is not None else 0) < 0 and not c.ended]
        return hit, bad

    def check_skip(self, slugs: list[str], day: dt.date) -> tuple[str | None, str]:
        """For /skip, before it marks a day: (a warning when the skip takes a course under its rule, else None; the
        changed courses' lines after it, for the reply)."""
        hit, bad = self.if_skipped(slugs, day)
        if not hit:
            return None, ""
        note = "Attendance (an estimate): " + "; ".join(c.line() for c in hit) + "."
        if not bad:
            return None, note
        when = "today" if day == now().date() else f"on {day:%a %d %b}"
        names = ", ".join(dict.fromkeys(self._subjects().name_of(s) for s in slugs))
        lines = [f"Skipping {names} {when} would leave you under the line (an estimate):"]
        lines += [f"- {c.line()}" for c in bad]
        self.app.events.emit("attendance_warned", courses=[c.key for c in bad])
        return "\n".join(lines), note

    def skip_buttons(self, slugs: list[str], day: dt.date) -> list:
        """Skip anyway / Don't skip, for a skip that waits for your OK."""
        f = self._dir / "held.json"
        week = (now().date() - dt.timedelta(days=7)).isoformat()
        held = {k: v for k, v in (jload(f, {}) or {}).items() if str(v.get("day", "")) >= week}
        ref = uuid.uuid4().hex[:8]
        held[ref] = {"day": day.isoformat(), "slugs": list(slugs)}
        jsave(f, held)
        return [[("Skip anyway", f"att:{ref}:skip"), ("Don't skip", f"att:{ref}:keep")]]

    def callbacks(self):
        return {"att": self._button}

    def _button(self, ref: str, act: str) -> str:
        if ref == "marks":
            self.app.events.emit("marks_offer", answer=act)
            if act == "yes":
                self.app.notify(HOW_MARKS, kind="result", title="Marks", why="asked")
                return "How to set up marks is below."
            jsave(self._dir / "marks-offer.json", {"declined": now().isoformat()})
            return "No marks, then. /marks sets them up whenever you like."
        f = self._dir / "held.json"
        held = jload(f, {}) or {}
        h = held.pop(ref, None)
        jsave(f, held)
        if not h:
            return "That's settled already."
        subj = self._subjects()
        day = dt.date.fromisoformat(h["day"])
        when = "today" if day == now().date() else f"on {day:%a %d %b}"
        names = ", ".join(subj.name_of(s) for s in h["slugs"])
        if act == "skip":
            subj.set_skip(h["slugs"], add=True, day=day)
            self.app.events.emit("class_skip", subjects=h["slugs"], anyway=True)
            return f"Marked: you're skipping {names} {when}."
        self.app.events.emit("class_skip_kept", subjects=h["slugs"])
        return f"Not marked: you're going to {names} {when}."

    # -------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "attendance",
                "classes attended per course, an estimate (/attendance set la 23/30 corrects it)",
                self._attendance,
            ),
            Command("standing", "attendance and marks per course, an estimate", self._standing),
            Command("marks", "marks so far and what's left: /marks la midsem 21/30", self._marks),
        ]

    def report(self) -> str:
        cs = self.ordered(self.courses())
        if not cs:
            return "No classes to count yet: add your timetable (/class mon 09:00-09:55 la, or /term note <note>)."
        lines = [f"Attendance since {self.since():%d %b}, an estimate (your timetable, minus the classes you skipped):"]
        lines += [c.line() for c in cs]
        if not self._subjects().term_ends():
            lines.append(
                "No last day of classes is set, so this is about classes so far: /term ends 2026-12-04 counts the "
                "rest of the term."
            )
        lines.append("Off from the official count? /attendance set la 23/30")
        return "\n".join(lines)

    def _attendance(self, msg: Incoming, arg: str) -> str:
        word, _, rest = arg.strip().partition(" ")
        w = word.lower()
        if w == "set":
            return self._set(rest)
        if w == "rule":
            return self._set_rule(rest)
        if w in ("lab", "labs"):
            return self._lab(rest)
        if w == "since":
            return self._since(rest)
        if arg.strip():
            return self._one(arg.strip())
        return self.report()

    def _one(self, text: str) -> str:
        key = self._key(text)
        if not key:
            return f"I don't know a course called {text}. /attendance lists them."
        cs = self.courses()
        mine = [c for c in self.ordered(cs) if c.key == key or (":" not in key and c.slug == key)]
        if not mine:
            return f"{self._subjects().name_of(key.partition(':')[0])} has no classes on your timetable."
        lines = [f"{c.line()}." for c in mine]
        for c in mine:
            if c.set_at:
                lines.append(
                    f"{c.name}: from your count of {c.set_at[:10]} on (/attendance set {self.typed(c.key)} clear)."
                )
            rule = f"{c.name}'s rule: {c.rule}%" if c.rule else f"{c.name}: no rule"
            lines.append(f"{rule} (/attendance rule {self.typed(c.key)} 80 changes it).")
            if c.left:
                lines.append(f"{c.name}: {plural(c.left, 'class')} left this term.")
        lines.append(f"Counted since {self.since():%d %b}; an estimate from your timetable and skips.")
        return "\n".join(lines)

    def _set(self, rest: str) -> str:
        m = re.fullmatch(rf"(?P<who>.+?)\s+(?:{FRACTION}|(?P<clear>{'|'.join(CLEAR)}))\s*", rest.strip(), re.I)
        if not m:
            return "Usage: /attendance set la 23/30 (attended/held, as of now), or /attendance set la clear"
        key = self._key(m["who"])
        if not key:
            return f"I don't know a course called {m['who']}."
        f = self._dir / "counts.json"
        fixes = jload(f, {}) or {}
        name = self._subjects().name_of(key.partition(":")[0]) + (" lab" if key.endswith(":lab") else "")
        if m["clear"]:
            fixes.pop(key, None)
            jsave(f, fixes)
            self.app.events.emit("attendance_set", course=key, cleared=True)
            return f"{name}: your correction is gone; it's counted from your timetable again."
        a, h = float(m["a"]), float(m["b"])
        if not (a.is_integer() and h.is_integer()) or a > h:
            return "That's attended/held in whole classes, e.g. 23/30."
        fixes[key] = {"attended": int(a), "held": int(h), "at": now().isoformat()}
        jsave(f, fixes)
        self.app.events.emit("attendance_set", course=key)
        c = self.courses().get(key)
        return f"{name}: {int(a)}/{int(h)} as of now; classes from now on count on top of it." + (
            f"\n{c.line()} (an estimate)." if c else ""
        )

    def _set_rule(self, rest: str) -> str:
        t = rest.strip()
        m = re.fullmatch(r"(?:(?P<who>.+?)\s+)?(?:(?P<pct>\d{1,3})\s*%?|(?P<clear>" + "|".join(CLEAR) + "))", t, re.I)
        if not m or (m["clear"] and not m["who"]):
            return "Usage: /attendance rule la 80, /attendance rule labs 100, /attendance rule 75 (every course)"
        pct = int(m["pct"]) if m["pct"] else None
        if pct is not None and pct > 100:
            return "A rule is a percentage, 0 to 100."
        who = (m["who"] or "").lower().strip()
        for words, setting, what in (
            (("", "all", "every course", "courses"), "min_pct", "Every course's rule"),
            (("lab", "labs", "all labs", "practicals"), "lab_min_pct", "Every lab's rule"),
        ):
            if who in words:
                if pct is None:
                    self.app.settings.reset(f"attendance.{setting}")
                else:
                    self.app.settings.set(f"attendance.{setting}", pct)
                self.app.events.emit("attendance_rule", course=setting, pct=pct)
                return f"{what} is {self.setting(setting)}% now" + (
                    " (labs have their own: /attendance rule labs 100)." if setting == "min_pct" else "."
                )
        key = self._key(who)
        if not key:
            return f"I don't know a course called {m['who']}."
        rules = dict(self.setting("rules") or {})
        name = self._subjects().name_of(key.partition(":")[0]) + (" lab" if key.endswith(":lab") else "")
        if pct is None:
            rules.pop(key, None)
            self.app.settings.set("attendance.rules", rules)
            return f"{name} follows the usual rule again."
        rules[key] = pct
        self.app.settings.set("attendance.rules", rules)
        self.app.events.emit("attendance_rule", course=key, pct=pct)
        return f"{name}'s rule is {pct}% now."

    def _lab(self, rest: str) -> str:
        slots = [" ".join(str(x).lower().split()) for x in self.setting("lab_slots") or []]
        t = rest.strip().lower()
        if not t:
            return (
                "Lab slots: " + ", ".join(slots) + "."
                if slots
                else "No lab slots. /attendance lab thu 14:00 marks one."
            ) + " Subjects named like a lab (Physics Lab) count as labs anyway."
        m = re.fullmatch(
            r"(?P<day>[a-z]{3})[a-z]*\s+(?P<h>\d{1,2})[:.](?P<m>\d{2})(?:\s+(?P<off>off|no|remove|clear))?", t
        )
        if not m or m["day"] not in DAYS:
            return "Usage: /attendance lab thu 14:00 (the slot's start), or /attendance lab thu 14:00 off"
        slot = f"{m['day']} {int(m['h']):02d}:{m['m']}"
        if m["off"]:
            self.app.settings.set("attendance.lab_slots", [s for s in slots if s != slot])
            return f"{slot.title()} counts as a class again."
        row = next((r for r in self._subjects().timetable() if f"{r['day']} {r['start']}" == slot), None)
        if row is None:
            return f"There's no class starting {slot.title()} on your timetable (/classes lists them)."
        self.app.settings.set("attendance.lab_slots", sorted({*slots, slot}))
        name, rule = self._subjects().name_of(row["subject"]), self._rule(f"{row['subject']}:lab", True)
        return f"{slot.title()} is the {name} lab now, counted on its own (rule {rule}%)."

    def _since(self, rest: str) -> str:
        try:
            d = dt.date.fromisoformat(rest.strip())
        except ValueError:
            return f"Usage: /attendance since 2026-08-03 (now counting since {self.since().isoformat()})"
        self.app.settings.set("attendance.since", d.isoformat())
        return (
            f"Counting from {d:%a %d %b}: every class on your timetable since then, minus the days you said you "
            "skipped. Earlier skips Kurooto didn't hear about need /attendance set la 23/30."
        )

    # ---------------------------------------------------------------------------------------- marks
    def _marks_data(self) -> dict:
        return jload(self._dir / "marks.json", {}) or {}

    def _marks_save(self, data: dict) -> None:
        jsave(self._dir / "marks.json", data)

    def marks_line(self, slug: str) -> str | None:
        """ "31.5 of the 50 so far; on what's left (endsem, worth 50): A out of reach, B 77%+, C 47-76%, ..." (an
        estimate), or None without marks."""
        d = self._marks_data().get(slug)
        parts = (d or {}).get("parts") or []
        if not parts:
            return None
        total = sum(float(p["weight"]) for p in parts)
        scored = [p for p in parts if p.get("of")]
        earned = sum(float(p["weight"]) * float(p["got"]) / float(p["of"]) for p in scored)
        rest = [p for p in parts if not p.get("of")]
        left = sum(float(p["weight"]) for p in rest)
        grades = d.get("grades") or self.setting("grades") or {}
        if not rest or left <= 0:
            pct = earned / total * 100 if total else 0
            best = sorted(grades.items(), key=lambda kv: -float(kv[1]))
            got = next((g for g, line in best if pct >= float(line)), "")
            return f"{number(earned)} of {number(total)}, all in" + (
                f"; that's {got} on your grade lines." if got else "."
            )
        names = [p["name"] for p in rest]
        what = (", ".join(names[:-1]) + " and " if len(names) > 1 else "") + f"{names[-1]}, worth {number(left)}"
        out = f"{number(earned)} of the {number(total - left)} so far"
        if not grades:
            return f"{out}; {what} still to come. Grade lines (/marks grades A 85, B 70) show what you'd need."
        return f"{out}; on what's left ({what}): " + ", ".join(grade_ranges(earned, left, total, grades)) + "."

    def _marks(self, msg: Incoming, arg: str) -> str:
        a = arg.strip()
        if not a:
            data = self._marks_data()
            lines = [f"{self._subjects().name_of(s)}: {self.marks_line(s)}" for s in data if self.marks_line(s)]
            return "\n".join(["Marks (an estimate):", *lines]) if lines else HOW_MARKS
        if a.lower().startswith("grades"):
            return self._grades(None, a[6:])
        slug, rest = self._split(a)
        if not slug:
            return "Which course? e.g. /marks la midsem 21/30 (/marks alone says how to set them up)"
        name, short = self._subjects().name_of(slug), self.typed(slug)
        r = rest.strip()
        data = self._marks_data()
        cur = data.get(slug) or {"parts": []}
        if not r:
            line = self.marks_line(slug)
            if not line:
                return f"No marks for {name} yet. /marks {short} weights midsem 30, endsem 70 starts them."
            parts = "; ".join(
                f"{p['name']} {number(p['weight'])}"
                + (f": {number(p['got'])}/{number(p['of'])}" if p.get("of") else "")
                for p in cur["parts"]
            )
            return f"{name} marks (an estimate): {line}\nParts (weight: score): {parts}"
        low = r.lower()
        if low in CLEAR:
            data.pop(slug, None)
            self._marks_save(data)
            return f"{name}'s marks are forgotten."
        if low.startswith("grades"):
            return self._grades(slug, r[6:])
        if re.match(r"weigh(?:ts?|tage)\b", low):
            return self._weights(slug, re.sub(r"^weigh(?:ts?|tage)\s*:?\s*", "", r, flags=re.I), data)
        m = re.fullmatch(rf"(?P<part>.+?)\s+(?:{FRACTION}|(?P<clear>{'|'.join(CLEAR)}))", r, re.I)
        if not m:
            return f"Usage: /marks {short} midsem 21/30, /marks {short} weights midsem 30, endsem 70"
        if not cur["parts"]:
            return f"Set {name}'s weightage first: /marks {short} weights midsem 30, quizzes 20, endsem 50"
        want = re.sub(r"[^a-z0-9]", "", m["part"].lower())
        part = next((p for p in cur["parts"] if re.sub(r"[^a-z0-9]", "", p["name"].lower()) == want), None)
        if part is None:
            names = ", ".join(p["name"] for p in cur["parts"])
            return (
                f"{name} has no part called {m['part']}. Its parts: {names} (/marks {short} weights ... changes them)."
            )
        if m["clear"]:
            part.pop("got", None)
            part.pop("of", None)
        else:
            got, of = float(m["a"]), float(m["b"])
            if of <= 0 or got > of:
                return "That's a score out of a total, e.g. 21/30."
            part["got"], part["of"] = got, of
        data[slug] = cur
        self._marks_save(data)
        self.app.events.emit("marks_set", course=slug)
        return f"{name} marks (an estimate): {self.marks_line(slug)}"

    def _weights(self, slug: str, text: str, data: dict) -> str:
        pieces = [x.strip() for x in re.split(r"[,;]|\band\b", text) if x.strip()]
        parts = []
        for x in pieces:
            m = re.fullmatch(r"(.+?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?", x)
            if not m:
                return f"I can't read '{x}'. Usage: /marks {self.typed(slug)} weights midsem 30, quizzes 20, endsem 50"
            parts.append({"name": m[1].strip(), "weight": float(m[2])})
        if not parts:
            return f"Usage: /marks {self.typed(slug)} weights midsem 30, quizzes 20, endsem 50"
        old = {re.sub(r"[^a-z0-9]", "", p["name"].lower()): p for p in (data.get(slug) or {}).get("parts", [])}
        for p in parts:
            was = old.get(re.sub(r"[^a-z0-9]", "", p["name"].lower()))
            if was and was.get("of"):
                p["got"], p["of"] = was["got"], was["of"]
        cur = data.get(slug) or {}
        data[slug] = {**cur, "parts": parts}
        self._marks_save(data)
        self.app.events.emit("marks_set", course=slug, weights=True)
        total = sum(p["weight"] for p in parts)
        name = self._subjects().name_of(slug)
        note = "" if abs(total - 100) < 1e-9 else f" They add up to {number(total)}, so grade lines are of that."
        return f"{name}: " + ", ".join(f"{p['name']} {number(p['weight'])}" for p in parts) + "." + note

    def _grades(self, slug: str | None, text: str) -> str:
        t = text.strip()
        data = self._marks_data()
        if t.lower() in CLEAR:
            if slug:
                data.setdefault(slug, {"parts": []}).pop("grades", None)
                self._marks_save(data)
                return "That course follows the usual grade lines again."
            self.app.settings.set("attendance.grades", {})
            return "Grade lines cleared."
        if not t:
            g = (data.get(slug) or {}).get("grades") if slug else None
            g = g or self.setting("grades") or {}
            return "Grade lines: " + ", ".join(f"{k} {number(float(v))}" for k, v in g.items()) if g else HOW_MARKS
        grades = {}
        for x in [x.strip() for x in re.split(r"[,;]", t) if x.strip()]:
            m = re.fullmatch(r"(\S+?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?", x)
            if not m or float(m[2]) > 100:
                return "Usage: /marks grades A 85, B 70, C 55, D 40 (% of the course's total)"
            grades[m[1]] = float(m[2])
        if slug:
            data.setdefault(slug, {"parts": []})["grades"] = grades
            self._marks_save(data)
        else:
            self.app.settings.set("attendance.grades", grades)
        return "Grade lines: " + ", ".join(f"{k} {number(v)}" for k, v in grades.items()) + "."

    def _standing(self, msg: Incoming, arg: str) -> str | None:
        cs = self.ordered(self.courses())
        marks = self._marks_data()
        lines = ["Where you stand (an estimate):"]
        seen = set()
        for c in cs:
            lines.append(c.line())
            m = self.marks_line(c.slug) if c.slug not in seen else None
            seen.add(c.slug)
            if m:
                lines.append(f"  Marks: {m}")
        for slug in marks:
            if slug not in seen and self.marks_line(slug):
                lines.append(f"{self._subjects().name_of(slug)} marks: {self.marks_line(slug)}")
        if len(lines) == 1:
            lines.append("Nothing to count yet: add your timetable (/class mon 09:00-09:55 la).")
        offered = (jload(self._dir / "marks-offer.json", {}) or {}).get("declined")
        if not any(self.marks_line(s) for s in marks) and not offered:
            msg.reply(
                "\n".join(lines)
                + "\n\nSet up marks too? Then this shows what you'd need in the end-sem for each grade "
                "(an estimate; /marks says how).",
                buttons=[[("Set up marks", "att:marks:yes"), ("Not now", "att:marks:no")]],
            )
            return None
        return "\n".join(lines)

    # --------------------------------------------------------------------------------- the rest of it
    def weekly_lines(self) -> list[str]:
        if not self.setting("weekly"):
            return []
        cs = [c for c in self.ordered(self.courses()) if c.held]
        return ["Attendance (an estimate): " + "; ".join(c.brief() for c in cs)] if cs else []

    def intents(self):
        def match(text: str):
            low = text.lower()
            if not (
                re.search(r"\battendance\b", low)
                or re.search(r"\b(?:can|could|should|may) i (?:still )?(?:skip|miss|bunk)\b", low)
                or re.search(
                    r"\bhow many (?:more )?(?:classes |lectures |labs )?(?:can|could) i (?:skip|miss|bunk)\b", low
                )
            ):
                return None
            if re.search(r"\b(?:check-?ins?|alarm|call|quiz|reminder)\b", low):
                return None
            return {"slugs": self._subjects().find_in(text), "day": a_day(text), "skip": "attendance" not in low}

        return [
            Intent(
                "attendance",
                "how your attendance stands, or whether you can skip a class",
                match,
                lambda m, s: self._answer(s),
                questions=True,
            )
        ]

    def _answer(self, s: dict) -> str:
        """ "can I skip LA tomorrow?": what the skip would do; "how's my attendance (in LA)?": the count."""
        slugs, day = s.get("slugs") or [], s.get("day")
        if len(slugs) != 1:
            return self.report()
        if not (s.get("skip") and day is not None):
            return self._one(slugs[0])
        name = self._subjects().name_of(slugs[0])
        when = "today" if day == now().date() else f"on {day:%a %d %b}"
        if slugs[0] in self._subjects().skipped(day):
            return f"You've already said you're skipping {name} {when}.\n{self._one(slugs[0])}"
        hit, bad = self.if_skipped(slugs, day)
        if not hit:
            return f"{name} has no class {when} on your timetable."
        lines = "\n".join(f"- {c.line()}" for c in hit)
        if bad:
            return f"Better not: skipping {name} {when} would leave you under the line (an estimate):\n{lines}"
        return f"Yes. After skipping {name} {when} (an estimate):\n{lines}"

    def call_tools(self):
        return [
            Tool(
                "attendance",
                "Their class attendance per course (an estimate: the timetable minus classes they skipped), and how "
                "many more classes each course can miss. Check it before they skip a class.",
                self._tool,
                {"subject": arg("optional: one course, e.g. Linear Algebra")},
                writes=False,
            )
        ]

    def _tool(self, a: dict) -> str:
        subject = str(a.get("subject") or "").strip()
        return self._one(subject) if subject else self.report()
