"""Deadlines: one list of what's due, and a chase that doesn't let things slip.

Where deadlines come from (the same thing from two places is kept once):
- what you add: /due fri 17:00 essay draft, or "add a deadline: essay draft due friday 5pm";
- unticked dated tasks in your notes, written like:  - [ ] Essay draft (2026-11-02 17:00)
- Google Classroom coursework (with Google on);
- calendar events that look like deadlines or exams ("Problem set 3 due", "Midterm"; with Calendar on);
- recurring quizzes and tests, from the table in your notes at kurooto/recurring.md (/recurring);
- the key dates in your term note (Subjects: /term note), read again whenever the note changes: its quizzes and
  exams, and deadlines that name one of your subjects.
Topics on your not-interested list (/ignore) are left out.

The chase, for things you hand in: a message with Done / Snooze / Not mine a day before; six hours before, a call
(with Phone calls on; it waits out classes and other no-call times) or else an urgent message; after the due time, an
"Overdue?" check (Done / New date / Drop). Done ticks the "- [ ]" line in your notes when it came from one.
Quizzes and exams aren't "done": you get a reminder or, with Quiz on, a practice offer the evening before, and exam
mode starts two weeks before (/exam).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re

from kurooto.core import layout
from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.notinterested import add_topic, ignored_topics, is_ignored, matcher, remove_topic
from kurooto.core.state import jload, jsave
from kurooto.modules import recurring
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg, note_files

register_defaults(
    "deadlines",
    {
        "scan_notes": True,
        "plan_h": 72,  # "due soon": what's due this many hours ahead goes into the morning plan, /status and calls
        "ping_h": 24,
        "urgent_h": 6,
        "max_files": 3000,
        "call": True,  # with Phone calls on, the six-hour nudge is a call (a message when no call fits before it)
        "overdue_check": True,  # after the due time: "Overdue?" with Done / New date / Drop
        "tick_notes": True,  # Done ticks the "- [ ]" line in your notes when the deadline came from one
        "from_calendar": True,  # calendar events that look like deadlines or exams (with Calendar on)
        "recurring": True,  # recurring quizzes from kurooto/recurring.md
        "from_term_note": True,  # quizzes, exams and deadlines from the term note's key dates (Subjects: /term note)
        "horizon_days": 30,  # recurring quizzes become dated deadlines this far ahead
        "exam_mode_days": 14,  # exam mode starts this many days before a quiz or exam (0: never)
    },
)
EXAMISH = re.compile(
    r"\b(quiz|exam|exams|midterm|mid-term|finals|midsem|mid-sem|endsem|end-sem|viva|oral|test|assessment)\b", re.I
)
NOT_EXAM = re.compile(r"\b(view|viewing|graded|results?|solutions?|marks|papers? shown)\b", re.I)
DUEISH = re.compile(
    r"\b(due|deadline|submit|submission|hand[- ]?in|assignment|homework|hw|problem set|coursework|report|"
    r"presentation)\b",
    re.I,
)
TASK = re.compile(r"^\s*[-*] \[( |x|X)\] (.*?\((\d{4}-\d{2}-\d{2})([^)]*)\).*)$")
ADD = re.compile(
    r"^\s*(?:add (?:a )?(?:deadline|assignment|due date)[:\s]+|i have (?:an? )?)"
    r"(?P<what>.+?)\s+due\s+(?P<when>.+)$",
    re.I,
)
IGNORE = re.compile(
    r"^(?:please\s+)?(?:i\s+(?:really\s+)?)?(?:don'?t|do not)\s+care\s+about\s+(?:the\s+|any\s+)?(?P<t>.+?)"
    r"(?:\s+(?:any ?more|from now on|stuff|things))?$"
    r"|^(?:i'?m|i am)\s+not\s+interested\s+in\s+(?:the\s+|any\s+)?(?P<u>.+?)(?:\s+(?:any ?more|from now on))?$"
    r"|^(?:please\s+)?ignore\s+(?:anything\s+(?:about|on)\s+|all\s+|any\s+|the\s+)?(?P<v>.+?)"
    r"\s+(?:from now on|any ?more|stuff|things|events|emails|posts|deadlines)$"
    r"|^(?:please\s+)?stop\s+telling\s+me\s+about\s+(?:the\s+|any\s+)?(?P<w>.+)$",
    re.I,
)
STOP_WHAT = re.compile(
    r"\s+(?:every|weekly|fortnightly|bi-?weekly|each|on|at|from)\b|\s+(?=\d)|\s+(?=(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b)",
    re.I,
)  # where "<what>" ends in "/recurring add la quiz every 2 weeks thu 10:00"
NEXT_EXAM = re.compile(r"\bexam mode\b|\bwhen(?:'?s| is) my next (?:quiz|exam|test)\b", re.I)
VAGUE = {"that", "this", "it", "them", "those", "these", "him", "her", "me", "you"}
NUM = re.compile(r"(?<![\d:./-])\d{1,3}(?![\d:./-])")
STOP = {
    "the", "a", "an", "due", "deadline", "submit", "submission", "for", "of", "on", "in", "to", "and", "by", "at",
    "is", "my", "your", "assignment", "hand", "turn", "no",
}  # fmt: skip


def did(title: str, due: str) -> str:
    norm = re.sub(r"\W+", " ", title.lower()).strip()
    return "d" + hashlib.sha1(f"{norm}|{due[:10]}".encode(), usedforsecurity=False).hexdigest()[:8]


def iso(t: dt.datetime) -> str:
    return t.replace(second=0, microsecond=0).isoformat()


def kind_of(title: str) -> str:
    return "exam" if EXAMISH.search(title) and not NOT_EXAM.search(title) else "task"


def hours_left(due: str, t: dt.datetime | None = None) -> float:
    return (dt.datetime.fromisoformat(due) - (t or now())).total_seconds() / 3600


def human(h: float) -> str:
    if h < 0:
        return "overdue"
    if h < 1:
        return f"in {int(h * 60)} min"
    if h < 48:
        return f"in {h:.0f} h"
    return f"in {h / 24:.0f} days"


def span(h: float) -> str:
    """72 -> "3 days", 36 -> "36 hours", 24 -> "day" (for "in the next ...")."""
    if h % 24 == 0:
        return "day" if h == 24 else f"{h / 24:.0f} days"
    return f"{h:g} hours"


def when_text(due: str) -> str:
    d = dt.datetime.fromisoformat(due)
    return f"{d:%a %d %b}" + ("" if d.strftime("%H:%M") == "23:59" else f" {d:%H:%M}")


def due_from(date: str, rest: str) -> str:
    """The date, at the first time written after it in the brackets ("17:00", "5:00 PM"), else the end of the day."""
    tm = re.search(r"(\d{1,2})[:.](\d{2})\s*(am|pm)?", rest or "", re.I)
    if not tm:
        return f"{date}T23:59:00"
    h = int(tm[1]) % 24
    if tm[3] and tm[3].lower() == "pm" and h < 12:
        h += 12
    elif tm[3] and tm[3].lower() == "am" and h == 12:
        h = 0
    return f"{date}T{h:02d}:{min(int(tm[2]), 59):02d}:00"


def similar(a: str, b: str, drop: set[str] | frozenset = frozenset()) -> bool:
    """Do two titles name the same thing? ("Linear Algebra: Problem set 3" and "Problem set 3": yes; "Quiz 2" and
    "Quiz 3": no.) `drop` holds words that don't count, like the subject's name."""
    na, nb = set(NUM.findall(a)), set(NUM.findall(b))
    if na and nb and not na & nb:
        return False
    wa = {w for w in re.findall(r"[a-z]+", a.lower()) if w not in STOP and w not in drop}
    wb = {w for w in re.findall(r"[a-z]+", b.lower()) if w not in STOP and w not in drop}
    if not wa or not wb:
        return bool(na & nb) or (not wa and not wb)
    return wa <= wb or wb <= wa or len(wa & wb) / len(wa | wb) >= 0.5


class Deadlines(Module):
    id = "deadlines"
    title = "Deadlines"
    description = (
        "What's due, from what you add, your notes, Classroom, your calendar and recurring quizzes; a nudge a day "
        "before, a call six hours before, an overdue check; exam mode before quizzes and exams."
    )
    requires = ("telegram",)

    @property
    def file(self):
        return self.app.paths.state / "deadlines.json"

    def items(self) -> dict:
        return jload(self.file, {}) or {}

    def quiet_overdue(self) -> int:
        """Updating from 0.1 (core/upgrade.py): what's overdue already isn't asked about ("Overdue?") all at once on
        the first tick; it stays on /deadlines. The number of deadlines marked."""
        t, n = now(), 0
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            for it in items.values():
                told = it.setdefault("told", [])
                if it.get("status") == "open" and hours_left(it["due"], t) < 0 and "overdue" not in told:
                    told.append("overdue")
                    n += 1
            if n:
                jsave(self.file, items)
        return n

    def start(self):
        self.every("tick", "hourly", self._tick)
        self.app.ask.hooks["deadlines.recurring"] = lambda q, a: self._recurring_answer(q.get("hook_payload") or {}, a)
        self.app.ask.hooks["deadlines.new_date"] = lambda q, a: self._new_date(
            str((q.get("hook_payload") or {}).get("id", "")), a
        )

    # ------------------------------------------------------------------------------------ subjects
    def _subjects(self):
        return self.app.modules.get("subjects") if self.app.is_on("subjects") else None

    def subject_of(self, title: str, path: str | None = None) -> str | None:
        """The subject a deadline belongs to: its notes folder, or the one subject its title names."""
        s = self._subjects()
        if not s:
            return None
        if path and "/" in path:
            folder = path.split("/")[0]
            slug = s.resolve(folder) or s.resolve(folder.replace("-", " "))
            if slug:
                return slug
        found = s.find_in(title)
        return found[0] if len(found) == 1 else None

    def subject_name(self, slug: str | None) -> str:
        s = self._subjects()
        return (s.name_of(slug) if s else slug) if slug else ""

    def _slug(self, text: str) -> str:
        s = self._subjects()
        return (s.resolve(text) if s else None) or re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

    def _subject_words(self, slug: str | None) -> set[str]:
        if not slug:
            return set()
        words = set(slug.split("-"))
        s = self._subjects()
        for x in s.subjects() if s else []:
            if x["slug"] == slug:
                for n in [x["name"], *x.get("aliases", [])]:
                    words |= set(re.findall(r"[a-z]+", n.lower()))
        return words

    def _slots(self, slug: str) -> list[tuple[str, str]]:
        """(day, start) of the subject's classes in your timetable."""
        s = self._subjects()
        if not s:
            return []
        rows = s.timetable()
        return sorted(
            {(c["day"], c["start"]) for c in rows if c.get("subject") == slug},
            key=lambda x: (recurring.DAYS.index(x[0]), x[1]),
        )

    # ------------------------------------------------------------------------------- one list
    def _resolve(self, items: dict, i: str) -> str | None:
        """The id a deadline is kept under (it may have been merged into the same thing from another source)."""
        if i in items:
            return i
        return next((j for j, it in items.items() if i in it.get("aliases", [])), None)

    def _twin(self, items: dict, title: str, due: str, kind: str, subject: str | None) -> str | None:
        for j, it in items.items():
            if it["due"][:10] != due[:10] or it["kind"] != kind:
                continue
            if subject and it.get("subject") and subject != it["subject"]:
                continue
            if similar(title, it["title"], self._subject_words(subject or it.get("subject"))):
                return j
        return None

    def _put(
        self, items: dict, title: str, due: str, source: str, kind: str | None = None, **extra
    ) -> tuple[str, bool]:
        """Add one deadline to `items` (call it under the lock), or merge it into the same thing from another place.
        Returns (its id, True if it's new)."""
        title = re.sub(r"\s+", " ", title).strip()
        kind = kind or kind_of(title)
        subject = extra.pop("subject", None) or self.subject_of(title, extra.get("note"))
        i = did(title, due)
        j = self._resolve(items, i) or self._twin(items, title, due, kind, subject)
        if j is None:
            items[i] = {
                "title": title,
                "due": due,
                "source": source,
                "sources": [source],
                "status": "open",
                "kind": kind,
                "subject": subject,
                "told": [],
                **{k: v for k, v in extra.items() if v},
            }
            return i, True
        it = items[j]
        if i != j and i not in it.setdefault("aliases", []):
            it["aliases"].append(i)
        if due[:10] == it["due"][:10] and due[11:16] != "23:59" and it["due"][11:16] == "23:59":
            it["due"] = due  # a known time beats "end of the day"
        if source not in it.setdefault("sources", [it["source"]]):
            it["sources"].append(source)
        if subject and not it.get("subject"):
            it["subject"] = subject
        for k, v in extra.items():
            if v and not it.get(k):
                it[k] = v
        if it["status"] == "gone":
            it["status"] = "open"
        return j, False

    def add(self, title: str, due: dt.datetime, source: str = "manual", **extra) -> str:
        """Add a deadline (from you, Classroom, a call...). extra: kind ("exam" | "task"), subject, link."""
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            i, new = self._put(items, title, iso(due), source, **extra)
            if not new and source in ("manual", "call") and items[i]["status"] == "ignored":
                items[i]["status"] = "open"  # you added it yourself after all
            jsave(self.file, items)
        self.app.events.emit("deadline_added" if new else "deadline_merged", source=source)
        it = items[i]
        due_s = f"{dt.datetime.fromisoformat(it['due']):%a %d %b %H:%M}"
        return (
            f"{'Added' if new else 'Already on the list'}: {it['title']}, due {due_s} ({human(hours_left(it['due']))})."
        )

    def mark_done(self, title: str, due: dt.datetime) -> bool:
        """Mark the deadline with this title and due time done (e.g. handed in on Classroom). True if it changed."""
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            j = self._resolve(items, did(title, iso(due)))
            if not j or items[j]["status"] != "open":
                return False
            items[j]["status"] = "done"
            jsave(self.file, items)
        self._after_status(j, items[j], "done")
        self.app.events.emit("deadline_done", source="sync")
        return True

    def ignored(self, text: str) -> str | None:
        """The not-interested topic this text is about, or None (see kurooto.core.notinterested)."""
        return is_ignored(self.app, text)

    # ------------------------------------------------------------------------------------ sources
    def refresh(self) -> int:
        """Bring the list up to date from your notes, calendar and recurring quizzes. Returns how many are new."""
        n = 0
        for scan in (self.scan_notes, self.scan_calendar, self.scan_recurring, self.scan_term):
            try:
                n += scan()
            except Exception as e:  # one broken source never stops the others
                self.app.events.emit("deadlines_source_failed", source=scan.__name__, error=str(e)[:200])
        return n

    def scan_notes(self) -> int:
        """Pick up dated tasks from the notes folder: unticked ones are open, ticked ones are done."""
        if not self.setting("scan_notes"):
            return 0
        found, ticked = {}, set()
        root = self.app.workspace
        for p in note_files(root, limit=self.setting("max_files") or 3000):
            try:
                if p.stat().st_size > 1_000_000:
                    continue
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = p.relative_to(root).as_posix()
            for line in lines:
                m = TASK.match(line)
                if not m:
                    continue
                title = re.sub(r"\s*\([^)]*\d{4}-\d{2}-\d{2}[^)]*\)", "", m[2])
                title = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]|\[([^\]]+)\]\([^)]*\)", lambda x: x[1] or x[2], title)
                title = title.strip()
                if not title:
                    continue
                due = due_from(m[3], m[4])
                nid = did(title, due)
                if m[1] == " ":
                    found[nid] = (title, due, rel, line)
                else:
                    ticked.add(nid)
        n = 0
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            for nid, (title, due, rel, line) in found.items():
                j = next((k for k, it in items.items() if it.get("note_id") == nid), None)
                if j:
                    items[j].update(note=rel, line=line)
                    continue
                j, new = self._put(items, title, due, f"notes:{rel}", note=rel, line=line, note_id=nid)
                items[j].update(note=rel, line=line, note_id=nid)
                n += new
            old = iso(now() - dt.timedelta(days=90))
            for j in [j for j, it in items.items() if it["status"] != "open" and it["due"] < old]:
                del items[j]  # long settled: forgotten
            for j, it in items.items():
                if str(it.get("source", "")).startswith("notes:") and "note_id" not in it and "line" not in it:
                    it["note_id"] = j  # kept by an older version: its id is the task's
                nid = it.get("note_id")
                if not nid or nid in found:
                    continue
                if it["status"] == "open" and (nid in ticked or len(it.get("sources", [it["source"]])) == 1):
                    it["status"] = "done"  # ticked (or deleted) in the notes
                for k in ("note", "line", "note_id"):
                    it.pop(k, None)
            jsave(self.file, items)
        return n

    def scan_calendar(self) -> int:
        """Calendar events that look like deadlines or exams ("Assignment: Problem set 3", "Midterm")."""
        cal = self.app.modules.get("calendar")
        if not (self.setting("from_calendar") and cal and self.app.is_on("calendar")):
            return 0
        t0 = cal.now()
        end = t0 + dt.timedelta(days=cal.setting("days") or 14)
        rows = []
        for e in cal.events(t0 - dt.timedelta(days=1), end):
            title = re.sub(r"^(?:assignment|due|deadline)\s*:\s*", "", (e.get("title") or "").strip(), flags=re.I)
            if not title or not (EXAMISH.search(title) or DUEISH.search(title)):
                continue
            if e["all_day"]:
                due = f"{e['start_dt'].date().isoformat()}T23:59:00"
            else:
                due = iso(e["start_dt"].astimezone().replace(tzinfo=None))
            rows.append((title, due, {}))
        return self._sync_source("calendar", rows, iso(end.astimezone().replace(tzinfo=None)))

    def _sync_source(self, source: str, rows: list[tuple[str, str, dict]], until: str) -> int:
        """Put a source's current rows in the list; what came only from it and has vanished since is "gone"."""
        n, seen = 0, set()
        t = iso(now())
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            for title, due, extra in rows:
                j, new = self._put(items, title, due, source, **extra)
                seen.add(j)
                n += new
            for j, it in items.items():
                only_here = it.get("sources", [it["source"]]) == [source]
                if j not in seen and only_here and it["status"] == "open" and t < it["due"] <= until:
                    it["status"] = "gone"
            jsave(self.file, items)
        return n

    def scan_term(self) -> int:
        """The term note's key dates (Subjects: /term note): its quizzes and exams, and deadlines that name one of
        your subjects (or that its Kind column calls due). A date taken out of the note goes from the list."""
        s = self._subjects()
        if not (self.setting("from_term_note") and s and hasattr(s, "key_dates")):
            return 0
        raw = str(s.setting("term_note") or "").strip()
        if raw and raw.lower() not in ("off", "none") and s.term_path() is None:
            return 0  # set but not there right now (a sync in progress, a folder not mounted): keep what we have
        rows = []
        for d in s.key_dates():
            if d["kind"] == "exam":
                kind = "exam"
            elif d["kind"] == "due" and (d["subject"] or d.get("explicit")):
                kind = "task"
            else:
                continue
            due = f"{d['from']}T{d['time'] or ('09:00' if kind == 'exam' else '23:59')}:00"
            rows.append((d["what"], due, {"subject": d["subject"], "kind": kind}))
        until = iso(now() + dt.timedelta(days=400))
        return self._sync_source("term-note", rows, until)

    # ----------------------------------------------------------------------------- recurring quizzes
    @property
    def recurring_note(self):
        return recurring.note_file(self.app)

    @property
    def _over_file(self):
        return self.app.paths.state / "deadlines-recurring.json"

    def recurring_rows(self) -> list[dict]:
        """The table's rows, with what you told Kurooto about rows that left the day or week open; then an imported
        class pack's quizzes (from_pack, Class packs) that the table doesn't have."""
        try:
            rows = recurring.parse(self.recurring_note.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            rows = []
        packs = self.app.modules.get("classpacks")
        if packs is not None and self.app.is_on("classpacks"):
            rows += packs.quiz_rows()
        over = jload(self._over_file, {}) or {}
        for r in rows:
            r["slug"] = self._slug(r["subject"])
            r["key"] = f"{r['slug']}|{r['what'].lower()}"
            for k, v in (over.get(r["key"]) or {}).items():
                if not r.get(k):
                    r[k] = v
        mine = {r["key"] for r in rows if not r.get("from_pack")}
        return [r for r in rows if not (r.get("from_pack") and r["key"] in mine)]

    def scan_recurring(self) -> int:
        if not self.setting("recurring"):
            return 0
        today = now().date()
        horizon = self.setting("horizon_days") or 30
        holidays = self._subjects().holidays() if self._subjects() else []
        asked = (jload(self._over_file, {}) or {}).get("_asked", [])
        rows = []
        for r in self.recurring_rows():
            slots = self._slots(r["slug"])
            if not r["day"] and len(slots) == 1:  # the subject's one class
                r["day"], r["time"] = slots[0][0], r["time"] or slots[0][1]
            if not r["time"] and r["day"]:
                r["time"] = next((s for d, s in slots if d == r["day"]), "")
            if not r["day"] or (r["every"] > 1 and not r["next"]):
                if r["key"] not in asked:
                    self._complete_rule({**r, "new": False}, rescan=False)  # asks you, once
                continue
            name = self.subject_name(r["slug"]) or r["subject"]
            for d in recurring.dates(r, today, horizon, holidays):
                due = f"{d.isoformat()}T{r['time'] or '09:00'}:00"
                rows.append((f"{name}: {r['what']}", due, {"subject": r["slug"], "kind": kind_of(r["what"])}))
        until = iso(dt.datetime.combine(today + dt.timedelta(days=horizon), dt.time(23, 59)))
        return self._sync_source("recurring", rows, until)

    def _complete_rule(self, rule: dict, rescan: bool = True) -> str:
        """Fill in a rule's day, time and next date from your timetable, or ask you what's missing. Saves it when
        it's complete (a new row in the table; for a row you wrote, what you answered). Returns what to tell you."""
        slug, name = rule["slug"], self.subject_name(rule["slug"]) or rule["subject"]
        what = rule["what"].lower()
        slots = self._slots(slug)
        question = None
        if not rule.get("day"):
            if len(slots) == 1:
                rule["day"], rule["time"] = slots[0][0], rule.get("time") or slots[0][1]
            else:
                question = (f"Which day (and time) is the {name} {what}?", [f"{d.title()} {s}" for d, s in slots][:6])
        if not question and not rule.get("time"):
            same = [s for d, s in slots if d == rule["day"]]
            rule["time"] = same[0] if same else "09:00"
        if not question and rule["every"] > 1 and not rule.get("next"):
            first = recurring.first_on(rule["day"], now().date())
            rule["options"] = {
                f"{first + dt.timedelta(weeks=k):%a %d %b}": (first + dt.timedelta(weeks=k)).isoformat()
                for k in range(rule["every"])
            }
            question = (
                f"The {name} {what} is every {rule['every']} weeks: when is the next one?",
                list(rule["options"]),
            )
        if question:
            if not rule.get("new"):
                over = jload(self._over_file, {}) or {}
                over["_asked"] = [*over.get("_asked", []), rule["key"]][-200:]
                jsave(self._over_file, over)
            self.app.ask.ask(
                question[0],
                choices=question[1] or None,
                hook="deadlines.recurring",
                hook_payload=rule,
                source=self.id,
                title="Recurring quiz",
                expires="3d",
                why="asked",
            )
            return f"One question first: {question[0]}"
        rule.pop("options", None)
        if rule.get("new"):
            row = {k: rule.get(k, "") for k in ("what", "every", "day", "time", "next", "until")}
            row["subject"] = slug
            f = self.recurring_note
            f.parent.mkdir(parents=True, exist_ok=True)
            old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
            head = layout.frontmatter(self.app, "recurring", f, title="Recurring quizzes and tests")
            old = old if old.strip() else recurring.new_note(self.app.name, now().date(), head)
            f.write_text(recurring.insert(old, recurring.line(row)), encoding="utf-8")
        else:
            over = jload(self._over_file, {}) or {}
            over[rule["key"]] = {k: rule.get(k, "") for k in ("day", "time", "next")}
            jsave(self._over_file, over)
        self.app.events.emit("recurring_set", every=rule["every"])
        if rescan:
            self.scan_recurring()
        future = [
            it
            for it in self.items().values()
            if it.get("subject") == slug and "recurring" in it.get("sources", []) and it["status"] == "open"
        ]
        nxt = min((it["due"] for it in future if hours_left(it["due"]) > 0), default=None)
        every = "every week" if rule["every"] == 1 else f"every {rule['every']} weeks"
        tail = f"; next {when_text(nxt)}" if nxt else ""
        return f"{name}: {rule['what']} {every}, {rule['day'].title()} {rule['time']}{tail}."

    def _recurring_answer(self, rule: dict, answer: str) -> str:
        if not rule.get("day"):
            day = recurring.day_of(answer)
            if not day:
                return "I couldn't find a day in that. /recurring add sets it: /recurring add la quiz weekly thu 10:00"
            rule["day"] = day
            rule["time"] = (recurring.read_rule(f"every {answer}") or {}).get("time", "")
        elif rule.get("every", 1) > 1 and not rule.get("next"):
            opts = rule.get("options") or {}
            vals = list(opts.values())
            pick = next((v for k, v in opts.items() if k.lower() == answer.strip().lower()), None)
            m = re.search(r"\d{4}-\d{2}-\d{2}", answer)
            low = answer.lower()
            pick = pick or (
                m[0] if m else vals[0] if "this" in low and vals else vals[1] if "next" in low and vals[1:] else ""
            )
            if not pick:
                return (
                    "I couldn't tell which week. /recurring add <subject> <what> every 2 weeks <day> <time> YYYY-MM-DD"
                )
            rule["next"] = pick
        return self._complete_rule(rule)

    def add_recurring(self, subject: str, what: str = "Quiz", every: int = 1, day: str = "", time: str = "",
                      next_date: str = "", until: str = "") -> str:  # fmt: skip
        """Add a row to the recurring table (asking you for the day or week when it isn't known)."""
        slug = self._slug(subject)
        what = (what or "Quiz").strip()[:60]
        rule = {
            "subject": subject,
            "slug": slug,
            "key": f"{slug}|{what.lower()}",
            "what": what,
            "every": max(1, min(8, int(every or 1))),
            "day": recurring.day_of(day) if day else "",
            "time": recurring.hhmm(time) if time else "",
            "next": next_date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", next_date or "") else "",
            "until": until if re.fullmatch(r"\d{4}-\d{2}-\d{2}", until or "") else "",
            "new": True,
        }
        if rule["next"] and not rule["day"]:
            rule["day"] = recurring.DAYS[dt.date.fromisoformat(rule["next"]).weekday()]
        if any(r["key"] == rule["key"] and not r.get("from_pack") for r in self.recurring_rows()):
            where = recurring.note_rel(self.app)
            return f"{self.subject_name(slug) or subject}: {what} is already in {where}; edit it there."
        return self._complete_rule(rule)

    def remove_recurring(self, subject: str, what: str) -> bool:
        slug = self._slug(subject)
        for r in self.recurring_rows():
            if r["slug"] == slug and r["what"].lower() == what.strip().lower() and r["line"]:  # not a pack's
                f = self.recurring_note
                f.write_text(recurring.remove(f.read_text(encoding="utf-8"), r["line"]), encoding="utf-8")
                self.scan_recurring()
                return True
        return False

    # ------------------------------------------------------------------------------------- the chase
    def _calls_ok(self) -> bool:
        c = self.app.modules.get("calls")
        return bool(self.setting("call") and c and self.app.is_on("calls") and c.ready()[0])

    def _quiz_offers(self) -> bool:
        return self.app.is_on("quiz") and bool(self.app.settings.get("quiz.offer_at"))

    def _tick(self, p: dict | None = None) -> None:
        self.refresh()
        t = now()
        skip = matcher(self.app)
        ping_h, urgent_h = self.setting("ping_h") or 24, self.setting("urgent_h") or 6
        todo = []
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            for i, it in items.items():
                if it["status"] != "open" or skip(it["title"]):
                    continue
                if it.get("snooze_until") and dt.datetime.fromisoformat(it["snooze_until"]) > t:
                    continue
                h = hours_left(it["due"], t)
                told = it.setdefault("told", [])
                if it["kind"] == "exam":  # not "done": a reminder, or (Quiz) the practice offer the evening before
                    if 0 < h <= ping_h and "ping" not in told and not self._quiz_offers():
                        told.append("ping")
                        todo.append(("exam", i, h))
                elif h < 0:
                    if self.setting("overdue_check") and "overdue" not in told and h > -72:
                        told.append("overdue")
                        todo.append(("overdue", i, h))
                elif h <= urgent_h and "urgent" not in told:
                    told += [x for x in ("ping", "urgent") if x not in told]
                    todo.append(("urgent", i, h))
                elif h <= ping_h and "ping" not in told:
                    told.append("ping")
                    todo.append(("ping", i, h))
            if todo:
                jsave(self.file, items)
        for what, i, h in todo:
            self._chase(what, i, items[i], h)
        self._exam_mode_news()

    def _chase(self, what: str, i: str, it: dict, h: float) -> None:
        if what == "urgent" and self._calls_ok() and self._call(i, it, h):
            return
        if what == "overdue":
            self.app.notify(
                f"{it['title']} was due {when_text(it['due'])}.",  # the title asks "Overdue?"
                kind="deadline",
                title="Overdue?",
                buttons=[[("Done", f"dl:{i}:done"), ("New date", f"dl:{i}:date"), ("Drop", f"dl:{i}:drop")]],
                why="deadlines.overdue",
                about=it["title"],
                item=i,
            )
            self.app.events.emit("deadline_overdue_asked")
            return
        self._tell(i, it, h, urgent=what == "urgent")

    def _tell(self, i: str, it: dict, h: float, urgent: bool, prefix: str = "") -> None:
        if it["kind"] == "exam":
            text = f"{prefix}{it['title']}: {human(h)} ({dt.datetime.fromisoformat(it['due']):%a %H:%M})."
            buttons = [[("Practice now", f"dl:{i}:quiz")]] if self.app.is_on("quiz") else None
        else:
            text = f"{prefix}Due {human(h)}: {it['title']} ({dt.datetime.fromisoformat(it['due']):%a %d %b %H:%M})"
            buttons = [[("Done", f"dl:{i}:done"), ("Not mine", f"dl:{i}:ignore"), ("Snooze 3 h", f"dl:{i}:snooze")]]
        self.app.notify(
            text,
            kind="deadline",
            urgent=urgent,
            buttons=buttons,
            why="deadlines.reminder",
            about=it["title"],
            item=i,
            due=it["due"],
        )
        self.app.events.emit("deadline_told", urgent=urgent)

    def _call(self, i: str, it: dict, h: float) -> bool:
        """The six-hour call. It waits out classes, /hold, focus and the night; if that would take it too close to
        the deadline, False (you get a message instead)."""
        due = dt.datetime.fromisoformat(it["due"])
        when, _ = self.app.availability.next_callable(now())
        if when > due - dt.timedelta(minutes=30):
            return False
        reason = f"{it['title']} is due {when_text(it['due'])}. Is it done, or how will you finish it in time?"
        calls = self.app.modules["calls"]
        place = getattr(calls, "place", None)  # rings now, or waits out a block and says so
        if place is not None:
            place(reason, key=f"deadlines:{i}", why="deadlines.call", due=it["due"])
        else:
            calls.schedule(max(when, now()), reason, key=f"deadlines:{i}", why="deadlines.call", due=it["due"])
        self.app.events.emit("deadline_call", hours_left=round(h, 1))
        return True

    def call_outcome(self, key: str, outcome: str) -> bool:
        """The deadline call was answered, missed or turned down: when it didn't happen, a message instead."""
        i = key.partition(":")[2]
        it = self.items().get(i)
        if not it or it["status"] != "open":
            return False
        if outcome in ("missed", "decline", "skip"):
            self._tell(i, it, hours_left(it["due"]), urgent=True, prefix="Missed call. ")
        self.app.events.emit("deadline_call_" + (outcome or "reply"))
        return False

    def _exam_mode_news(self) -> None:
        """Say once when exam mode starts for a quiz or exam."""
        items = self.items()
        news = [e for e in self.exam_mode() if "exam_mode" not in (items.get(e["id"], {}).get("told") or [])]
        if not news:
            return
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            for e in news:
                if e["id"] in items:
                    items[e["id"]].setdefault("told", []).append("exam_mode")
            jsave(self.file, items)
        for e in news:
            more = " Quizzes come more often until then." if self.app.is_on("quiz") else ""
            whose = f" for {e['name']}" if e["name"] else ""
            self.app.notify(
                f"Exam mode{whose}: {e['title']}, {when_text(e['due'])} ({e['when']}).{more} /exam shows it.",
                kind="info",
                why="deadlines.exam_mode",
                about=e["title"],
            )
            self.app.events.emit("exam_mode_on", days=e["days"])

    # ------------------------------------------------------------------------------- your answers
    def _status(self, i: str, status: str) -> tuple[str | None, dict | None]:
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            j = self._resolve(items, i)
            if not j:
                return None, None
            items[j]["status"] = status
            jsave(self.file, items)
        return j, self._after_status(j, items[j], status)

    def _after_status(self, j: str, it: dict, status: str) -> dict:
        self.app.scheduler.cancel(f"calls:ring:deadlines:{j}")
        if status == "done":
            it["ticked"] = self._tick_note(it)
        return it

    def _tick_note(self, it: dict) -> bool:
        """Done: tick its "- [ ]" line in your notes (only that box changes)."""
        if not (self.setting("tick_notes") and it.get("note") and it.get("line")):
            return False
        f = self.app.workspace / it["note"]
        try:
            with open(f, encoding="utf-8", newline="") as fh:
                text = fh.read()
        except OSError:
            return False
        lines = text.split("\n")
        for k, ln in enumerate(lines):
            if ln.rstrip("\r") == it["line"] and re.match(r"^\s*[-*] \[ \]", ln):
                lines[k] = ln.replace("[ ]", "[x]", 1)
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write("\n".join(lines))
                self.app.events.emit("deadline_ticked")
                return True
        return False

    def move(self, i: str, when: dt.datetime) -> str:
        """A new due date for a deadline (the chase starts over)."""
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            j = self._resolve(items, i)
            if not j:
                return "That one is gone."
            it = items[j]
            it.update(due=iso(when), status="open", told=[x for x in it.get("told", []) if x == "exam_mode"])
            it.pop("snooze_until", None)
            jsave(self.file, items)
        self.app.scheduler.cancel(f"calls:ring:deadlines:{j}")
        self.app.events.emit("deadline_moved")
        return f"Moved: {it['title']}, now due {when_text(it['due'])} ({human(hours_left(it['due']))})."

    def _new_date(self, i: str, answer: str) -> str:
        try:
            when = parse_when(answer.strip())
        except ValueError:
            return f"I couldn't read {answer.strip()!r} as a date. Try e.g. fri 17:00 or 2026-11-02 17:00."
        return self.move(i, when)

    def callbacks(self):
        return {"dl": self._button}

    def _button(self, i: str, act: str) -> str:
        items = self.items()
        j = self._resolve(items, i)
        if act == "quiz":
            quiz = self.app.modules.get("quiz")
            if not quiz or not self.app.is_on("quiz"):
                return "Quiz is off."
            return quiz.start_session(items.get(j or "", {}).get("subject"))
        if not j:
            return "That one is gone."
        if act == "date":
            self.app.ask.ask(
                f"New date for {items[j]['title']}? (e.g. fri 17:00 or 2026-11-02 17:00)",
                hook="deadlines.new_date",
                hook_payload={"id": j},
                source=self.id,
                title="Deadline",
                why="asked",
            )
            return "When is it due now? Answer the question."
        if act == "snooze":
            with Lock(self.app.paths.state, "deadlines"):
                items = self.items()
                if j not in items:
                    return "That one is gone."
                it = items[j]
                it["snooze_until"] = (now() + dt.timedelta(hours=3)).isoformat()
                it["told"] = [x for x in it["told"] if x != "urgent"]
                jsave(self.file, items)
            self.app.scheduler.cancel(f"calls:ring:deadlines:{j}")
            self.app.events.emit("deadline_snooze")
            return "I'll ask again in 3 hours."
        j, it = self._status(j, "done" if act == "done" else "ignored")
        if not j:
            return "That one is gone."
        self.app.events.emit("deadline_" + ("done" if act == "done" else "ignore"))
        if act == "done":
            return "Marked done" + (f" (ticked in {it['note']})." if it.get("ticked") else ".")
        return "Dropped." if act == "drop" else "Removed."

    # ------------------------------------------------------------------------------------- the list
    def upcoming(self, hours: float = 336) -> list[tuple[str, dict, float]]:
        out = []
        skip = matcher(self.app)
        for i, it in self.items().items():
            h = hours_left(it["due"])
            if it["status"] == "open" and -24 < h <= hours and not skip(it["title"]):
                out.append((i, it, h))
        return sorted(out, key=lambda x: x[2])

    @staticmethod
    def _row(i: str, it: dict, h: float) -> dict:
        return {
            "id": i,
            "title": it["title"],
            "subject": it.get("subject"),
            "due": it["due"][:16],
            "kind": it["kind"],
            "when": human(h),
            "hours": round(h, 1),
        }

    def plan_hours(self) -> float:
        """How far ahead "due soon" looks (deadlines.plan_h, 72): the morning plan and page, /status, calls."""
        try:
            return max(1.0, float(self.setting("plan_h") or 72))
        except (TypeError, ValueError):
            return 72.0

    def deadlines_soon(self, hours: float | None = None) -> list[dict]:
        """Open deadlines, quizzes and exams in the next `hours` (default: plan_h), soonest first (for briefs and the
        morning page)."""
        hours = self.plan_hours() if hours is None else hours
        return [self._row(i, it, h) for i, it, h in self.upcoming(hours) if h > 0]

    def exams_soon(self, days: float = 14) -> list[dict]:
        """Quizzes and exams in the next `days`, soonest first."""
        return [r for r in self.deadlines_soon(days * 24) if r["kind"] == "exam"]

    def exam_mode(self) -> list[dict]:
        """Exam mode: for each subject, its nearest quiz or exam within exam_mode_days (nearest first), with the
        subject's name and the days left."""
        days = self.setting("exam_mode_days") or 0
        if days <= 0:
            return []
        best: dict = {}
        for r in self.exams_soon(days):
            best.setdefault(r["subject"] or "", r)
        return [
            {**r, "name": self.subject_name(r["subject"]), "days": round(r["hours"] / 24, 1)} for r in best.values()
        ]

    def commands(self):
        return [
            Command("deadlines", "what's due in the next two weeks", self._list),
            Command("due", "add one: /due fri 17:00 essay draft", self._due),
            Command("exam", "exam mode: quizzes and exams in the next two weeks", lambda m, a: self._exam()),
            Command("recurring", "repeating quizzes: /recurring add la quiz every 2 weeks thu 10:00", self._recurring),
            Command("ignore", "a topic you don't care about: /ignore drama club", lambda m, a: self._ignore(a)),
            Command("ignored", "your not-interested list", lambda m, a: self._ignored()),
            Command("unignore", "take a topic off that list: /unignore drama club", lambda m, a: self._unignore(a)),
        ]

    def _list(self, msg: Incoming, arg: str) -> str | None:
        self.refresh()
        up = self.upcoming()
        if not up:
            return "Nothing due in the next two weeks that I know of."
        for i, it, h in up[:12]:
            buttons = None if it["kind"] == "exam" else [[("Done", f"dl:{i}:done"), ("Not mine", f"dl:{i}:ignore")]]
            msg.reply(f"{human(h)} · {it['title']}", buttons=buttons)
        return None

    def _due(self, msg: Incoming, arg: str) -> str:
        parts = arg.split()
        for n in (3, 2, 1):
            if len(parts) > n:
                try:
                    when = parse_when(" ".join(parts[:n]))
                except ValueError:
                    continue
                title = re.sub(r"^(?:00\s+|-\s+|:\s+)", "", " ".join(parts[n:])).strip()
                return self.add(title, when)
        return (
            "Usage: /due fri 17:00 essay draft   (or: /due 2026-11-02 lab report; a bare number is the hour: 5 is the "
            "next 5:00)"
        )

    def _exam(self) -> str:
        days = self.setting("exam_mode_days") or 0
        if not days:
            return "Exam mode is turned off (Settings → Deadlines → exam mode days)."
        modes = self.exam_mode()
        if not modes:
            return f"Exam mode is off: no quiz or exam in the next {days} days that I know of."
        quiz = self.app.modules.get("quiz") if self.app.is_on("quiz") else None
        rows = []
        for e in modes:
            count = f", {quiz.due_count(e['subject'])} questions to practise" if quiz and e["subject"] else ""
            label = f"{e['name']}: " if e["name"] and not e["title"].lower().startswith(e["name"].lower()) else ""
            rows.append(f"{label}{e['title']}, {when_text(e['due'])} ({e['when']}){count}")
        return "Exam mode:\n" + "\n".join(rows) + ("\n\n/quiz to practise." if quiz else "")

    def _recurring(self, msg: Incoming, arg: str) -> str | None:
        a = arg.strip()
        if not a or a == "list":
            rows = self.recurring_rows()
            if not rows:
                return (
                    "No recurring quizzes yet. /recurring add la quiz every 2 weeks thu 10:00, or say "
                    '"linear algebra has a quiz every thursday". They live in your notes: '
                    f"{recurring.note_rel(self.app)}."
                )
            out = []
            for r in rows:
                every = "every week" if r["every"] == 1 else f"every {r['every']} weeks"
                when = f"{r['day'].title()} {r['time']}".strip() or "day not known yet"
                pack = " (class pack: /classpack set to change it)" if r.get("from_pack") else ""
                out.append(f"{self.subject_name(r['slug']) or r['subject']}: {r['what']}, {every}, {when}{pack}")
            return "\n".join(out) + f"\n\n(Edit them in {recurring.note_rel(self.app)}.)"
        m = re.match(r"(add|remove)\s+(\S+)\s*(.*)$", a, re.I)
        if not m:
            return "Usage: /recurring add la quiz every 2 weeks thu 10:00   ·   /recurring remove la quiz"
        subj, rest = m[2], m[3].strip()
        if m[1].lower() == "remove":
            return "Removed." if self.remove_recurring(subj, rest or "Quiz") else "No such row (see /recurring)."
        rule = recurring.read_rule(
            rest if recurring.ONE.search(rest) or recurring.TWO.search(rest) else rest + " every"
        )
        what = re.split(STOP_WHAT, " " + rest, maxsplit=1)[0].strip() or "Quiz"
        out = self.add_recurring(
            subj, what[:1].upper() + what[1:], rule["every"], rule["day"], rule["time"], rule["next"]
        )
        return None if out.startswith("One question first") else out  # the question itself is the reply

    def _ignore(self, topic: str) -> str:
        topic = topic.strip()
        if not topic:
            return "Usage: /ignore drama club   (/ignored lists them, /unignore takes one off)"
        if not add_topic(self.app, topic):
            return f"'{topic}' is already on your not-interested list."
        hidden = sum(1 for it in self.items().values() if it["status"] == "open" and is_ignored(self.app, it["title"]))
        tail = f" ({hidden} hidden now)" if hidden else ""
        return (
            f"Ignoring '{topic}' from now on: deadlines about it are left out{tail}, and mail and Classroom digests "
            f"only count it. /unignore {topic} undoes it."
        )

    def _ignored(self) -> str:
        t = ignored_topics(self.app)
        return ("Not interested in:\n" + "\n".join(f"- {x}" for x in t)) if t else "Your not-interested list is empty."

    def _unignore(self, topic: str) -> str:
        if not topic.strip():
            return "Usage: /unignore drama club"
        return f"'{topic.strip()}' is off the list." if remove_topic(self.app, topic) else "That isn't on the list."

    def intents(self):
        def show(text: str):
            if re.search(r"\b(what'?s|what is|anything|show)\b.*\b(due|deadlines?)\b", text, re.I):
                return {
                    "hours": 168 if "week" in text.lower() else self.plan_hours() if "soon" in text.lower() else 336
                }
            return None

        def add(text: str):
            m = ADD.match(text)
            if not m:
                return None
            try:
                return {"what": m["what"], "when": parse_when(m["when"])}
            except ValueError:
                return None

        def run_show(msg, s):
            up = self.upcoming(s["hours"])
            return "\n".join(f"{human(h)} · {it['title']}" for _, it, h in up[:15]) or "Nothing due in that time."

        def ignore(text: str):
            m = IGNORE.match(text.strip().rstrip(".!"))
            if not m:
                return None
            topic = next(g for g in (m["t"], m["u"], m["v"], m["w"]) if g).strip()
            if len(topic) < 3 or topic.lower() in VAGUE or len(topic.split()) > 6:
                return None
            return {"topic": topic}

        def recur(text: str):
            s = self._subjects()
            if not s or not re.search(r"\b(quiz|test|assessment|viva|worksheet)", text, re.I):
                return None
            rule = recurring.read_rule(text)
            found = s.find_in(text)
            if not rule or len(found) != 1 or re.search(r"\b(remind|call|skip)\b", text, re.I):
                return None
            return {**rule, "subject": found[0]}

        def run_recur(msg, s):
            out = self.add_recurring(s["subject"], s["what"], s["every"], s["day"], s["time"], s["next"])
            return "OK. " + out if out.startswith("One question first") else out

        return [
            Intent("show_due", "what's due", show, run_show, questions=True),
            Intent("add_deadline", "add a deadline", add, lambda m, s: self.add(s["what"], s["when"])),
            Intent("ignore_topic", "I don't care about X", ignore, lambda m, s: self._ignore(s["topic"])),
            Intent(
                "exam_mode",
                "exam mode, when's my next quiz",
                lambda t: (
                    {} if NEXT_EXAM.search(t) and not re.search(r"\b(off|stop|disable|turn|set)\b", t, re.I) else None
                ),
                lambda m, s: self._exam(),
                questions=True,
            ),
            Intent("add_recurring", "<subject> has a quiz every <day>", recur, run_recur),
        ]

    # -------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        due = [
            {"id": i, "what": it["title"], "due": human(h), "kind": it["kind"]}
            for i, it, h in self.upcoming(self.plan_hours())[:10]
        ]
        out: dict = {"due_soon": due} if due else {}
        modes = self.exam_mode()
        if modes:
            out["exam_mode"] = [
                f"{(e['name'] + ': ') if e['name'] else ''}{e['title']}, {when_text(e['due'])} ({e['when']})"
                for e in modes
            ]
        return out

    def call_tools(self):
        return [
            Tool(
                "mark_deadline_done",
                "Mark a deadline done (its id is in pending_items).",
                lambda a: self._button(str(a.get("id", "")), "done"),
                {"id": arg()},
                ("id",),
                offline="queue",
                hint="mark_deadline_done when they say something is submitted or finished; add_deadline adds one; "
                "move_deadline when it got a new date; ignore_topic when they don't care about something.",
            ),
            Tool(
                "add_deadline",
                'Add a deadline: what, and when it is due ("fri 23:59", "2026-11-02 17:00").',
                self._tool_add,
                {"title": arg(), "due": arg()},
                ("title", "due"),
                offline="queue",
            ),
            Tool(
                "move_deadline",
                'Give a deadline a new due date (its id is in pending_items; due like "fri 17:00").',
                lambda a: self._new_date(str(a.get("id", "")), str(a.get("due", ""))),
                {"id": arg(), "due": arg()},
                ("id", "due"),
                offline="queue",
            ),
            Tool(
                "ignore_topic",
                "Put a topic on their not-interested list (deadlines about it are left out, digests only count it).",
                lambda a: self._ignore(str(a.get("topic", ""))),
                {"topic": arg("e.g. drama club")},
                ("topic",),
                offline="queue",
            ),
            Tool(
                "add_recurring_quiz",
                "A quiz or test that repeats every week or every few weeks. Day like thu, time like 10:00, next as "
                "YYYY-MM-DD (any date it happens on; needed for every 2 weeks). Leave out what you don't know.",
                lambda a: self.add_recurring(
                    str(a.get("subject", "")),
                    str(a.get("what") or "Quiz"),
                    int(a.get("every_weeks") or 1),
                    str(a.get("day") or ""),
                    str(a.get("time") or ""),
                    str(a.get("next") or ""),
                ),
                {
                    "subject": arg(),
                    "what": arg("e.g. Quiz"),
                    "every_weeks": {"type": "integer"},
                    "day": arg(),
                    "time": arg(),
                    "next": arg(),
                },
                ("subject",),
                offline="queue",
            ),
        ]

    def _tool_add(self, a: dict) -> str:
        try:
            due = parse_when(str(a.get("due", "")))
        except ValueError:
            return f"I couldn't read the date {a.get('due')!r}."
        return self.add(str(a.get("title") or "untitled"), due.replace(tzinfo=None), source="call")
