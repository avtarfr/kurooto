"""Subjects: the courses or topics you work on, with short names ("LA", "stats"), and an optional weekly timetable.
With a timetable, Kurooto won't call you during a class you attend; tell it when you skip one.

    /subject add Linear Algebra (la, linalg)
    /class mon 09:00-09:55 la        /classes        /skip la   /attend la
"""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults("subjects", {"list": [], "timetable": [], "holidays": [], "no_calls_in_class": True, "margin_min": 5})
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class Subjects(Module):
    id = "subjects"
    title = "Subjects and timetable"
    description = "Your courses with short names, and an optional timetable so calls never interrupt a class."

    def start(self):
        self.app.availability.blockers["subjects:class"] = self._block

    def stop(self):
        super().stop()
        self.app.availability.blockers.pop("subjects:class", None)

    # ---------------------------------------------------------------------------------------- data
    def subjects(self) -> list[dict]:
        return self.setting("list") or []

    def resolve(self, text: str) -> str | None:
        """'LA', 'linalg', 'Linear Algebra' -> the subject's slug."""
        t = (text or "").lower().strip()
        if not t:
            return None
        for s in self.subjects():
            if t == s["slug"] or t == s["name"].lower() or t in [a.lower() for a in s.get("aliases", [])]:
                return s["slug"]
        for s in self.subjects():
            if len(t) >= 4 and (t in s["name"].lower() or t in s["slug"]):
                return s["slug"]
        return None

    def name_of(self, slug: str) -> str:
        return next((s["name"] for s in self.subjects() if s["slug"] == slug), slug)

    def find_in(self, text: str) -> list[str]:
        """Every subject named in a sentence, in order."""
        found = []
        low = f" {text.lower()} "
        for s in self.subjects():
            for n in [s["name"], s["slug"], *s.get("aliases", [])]:
                if n and re.search(r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])", low):
                    if s["slug"] not in found:
                        found.append(s["slug"])
                    break
        return found

    def skipped(self, day: dt.date | None = None) -> set[str]:
        day = day or now().date()
        return set(jload(self.app.paths.state / "subjects" / f"skip-{day.isoformat()}.json", []) or [])

    def set_skip(self, slugs: list[str], add: bool = True, day: dt.date | None = None) -> set[str]:
        day = day or now().date()
        cur = self.skipped(day)
        cur = cur | set(slugs) if add else cur - set(slugs)
        jsave(self.app.paths.state / "subjects" / f"skip-{day.isoformat()}.json", sorted(cur))
        return cur

    def classes_on(self, day: dt.date | None = None, include_skipped: bool = False) -> list[dict]:
        day = day or now().date()
        if day.isoformat() in (self.setting("holidays") or []):
            return []
        skip = set() if include_skipped else self.skipped(day)
        out = []
        for c in self.setting("timetable") or []:
            if DAYS.index(c["day"]) != day.weekday() or c["subject"] in skip:
                continue
            s = dt.datetime.combine(day, dt.time.fromisoformat(c["start"]))
            e = dt.datetime.combine(day, dt.time.fromisoformat(c["end"]))
            out.append({**c, "name": self.name_of(c["subject"]), "start_dt": s, "end_dt": e})
        return sorted(out, key=lambda c: c["start_dt"])

    def _block(self, t: dt.datetime):
        if not self.setting("no_calls_in_class"):
            return None
        margin = dt.timedelta(minutes=self.setting("margin_min") or 0)
        for c in self.classes_on(t.date()):
            if c["start_dt"] - margin <= t < c["end_dt"]:
                return f"class: {c['name']}", c["end_dt"]
        return None

    # ------------------------------------------------------------------------------------ commands
    def commands(self):
        return [
            Command("subject", "add a subject: /subject add Linear Algebra (la, linalg)", self._subject),
            Command("class", "add a class to your timetable: /class mon 09:00-09:55 la", self._class),
            Command("classes", "your timetable (today: /classes today)", self._classes),
            Command("skip", "you're not attending a class today: /skip la", lambda m, a: self._skip(a, True)),
            Command("attend", "undo /skip", lambda m, a: self._skip(a, False)),
        ]

    def _subject(self, msg: Incoming, arg: str) -> str:
        m = re.match(r"(?:add\s+)?(?P<name>[^()]+?)\s*(?:\((?P<aliases>[^)]*)\))?\s*$", arg)
        if not arg or not m:
            names = ", ".join(f"{s['name']} ({', '.join(s.get('aliases', []))})" for s in self.subjects())
            return names or "No subjects yet. /subject add Linear Algebra (la, linalg)"
        if arg.lower().startswith("remove "):
            slug = self.resolve(arg[7:])
            self.app.settings.set("subjects.list", [s for s in self.subjects() if s["slug"] != slug])
            return f"Removed {arg[7:]}." if slug else "No such subject."
        name = m["name"].strip()
        aliases = [a.strip().lower() for a in (m["aliases"] or "").split(",") if a.strip()]
        items = [s for s in self.subjects() if s["slug"] != slugify(name)]
        items.append({"name": name, "slug": slugify(name), "aliases": aliases})
        self.app.settings.set("subjects.list", items)
        return f"Added {name}" + (f" (also: {', '.join(aliases)})" if aliases else "") + "."

    def _class(self, msg: Incoming, arg: str) -> str:
        m = re.match(
            r"(?P<day>[a-z]{3})[a-z]*\s+(?P<s>\d{1,2}:\d{2})\s*[-–]\s*(?P<e>\d{1,2}:\d{2})\s+(?P<subj>.+)$", arg, re.I
        )
        if not m or m["day"].lower() not in DAYS:
            return "Usage: /class mon 09:00-09:55 la   (/class remove mon 09:00 removes one)"
        slug = self.resolve(m["subj"])
        if not slug:
            return f"Add the subject first: /subject add {m['subj']}"
        row = {
            "day": m["day"].lower(),
            "start": f"{int(m['s'][:-3]):02d}{m['s'][-3:]}",
            "end": f"{int(m['e'][:-3]):02d}{m['e'][-3:]}",
            "subject": slug,
        }
        tt = [c for c in self.setting("timetable") or [] if not (c["day"] == row["day"] and c["start"] == row["start"])]
        self.app.settings.set("subjects.timetable", [*tt, row])
        return f"{self.name_of(slug)} on {row['day'].title()} {row['start']}–{row['end']} added."

    def _classes(self, msg: Incoming, arg: str) -> str:
        if arg.strip() == "today":
            cs = self.classes_on(include_skipped=True)
            skip = self.skipped()
            return (
                "\n".join(
                    f"{c['start']}–{c['end']} {c['name']}{' (skipping)' if c['subject'] in skip else ''}" for c in cs
                )
                or "No classes today."
            )
        rows = sorted(self.setting("timetable") or [], key=lambda c: (DAYS.index(c["day"]), c["start"]))
        return "\n".join(f"{c['day'].title()} {c['start']}–{c['end']} {self.name_of(c['subject'])}" for c in rows) or (
            "No timetable yet. /class mon 09:00-09:55 la"
        )

    def _skip(self, arg: str, add: bool) -> str:
        slugs = [s for s in (self.resolve(x) for x in re.split(r"[,\s]+and\s+|,\s*", arg) if x.strip()) if s]
        if not slugs:
            slugs = self.find_in(arg)
        if not slugs:
            return "Which subject? e.g. /skip la"
        cur = self.set_skip(slugs, add=add)
        self.app.events.emit("class_skip" if add else "class_attend", subjects=slugs)
        names = ", ".join(self.name_of(s) for s in sorted(cur)) or "nothing"
        return f"Today you're skipping: {names}. Calls are allowed during skipped classes."

    def intents(self):
        def match(text: str):
            if not re.search(r"\b(skip(?:ping)?|not (?:going|attending)|missing|bunking)\b", text, re.I):
                return None
            found = self.find_in(text)
            return {"slugs": found} if len(found) == 1 else None

        return [Intent("skip_class", "skipping a class today", match, lambda m, s: self._skip(s["slugs"][0], True))]

    # -------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        cls = self.classes_on()
        return {"classes_today": [f"{c['start']}-{c['end']} {c['name']}" for c in cls]} if cls else {}

    def call_tools(self):
        return [
            Tool(
                "skip_class",
                "They're not going to this class today (no after-class question; calls are allowed during it).",
                self._tool_skip,
                {"subject": arg("e.g. Linear Algebra")},
                ("subject",),
                offline="queue",
            )
        ]

    def _tool_skip(self, a: dict) -> str:
        slug = self.resolve(str(a.get("subject", "")))
        if not slug:
            return "I don't know that subject."
        self.set_skip([slug])
        return f"Skipping {self.name_of(slug)} today."
