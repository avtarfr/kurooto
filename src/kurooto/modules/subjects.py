"""Subjects: the courses or topics you work on, with short names ("LA", "stats"), and an optional weekly timetable.
With a timetable, Kurooto won't call you during a class you attend; tell it when you skip one ("skipping LA
today", "not going to stats on Friday").

    /subject add Linear Algebra (la, linalg)
    /class mon 09:00-09:55 la        /classes        /skip la   /attend la
    /term ends 2026-12-04            /term exams 2026-12-07 to 2026-12-18
    /term note terms/2026-autumn     read the timetable and key dates from a note, live (/term note off)

Holidays, exam periods and the days after the term's last day have no classes: no after-class questions, and the
timetable doesn't hold calls then. Events in calendars you mark as classes (Calendar: /cal classes Timetable) are
classes too.

The term note (subjects.term_note): a note with a "## Weekly timetable" and a "## Key dates" table (the format is in
kurooto/modules/termnote.py; /term-setup writes one). Kurooto re-reads it whenever it changes: its classes, subjects,
holidays, exam periods and last day of classes join the ones you set here (yours win where both say something), and
its dated quizzes, exams and deadlines reach Deadlines. "maps/semester-*" picks the newest matching note; "auto" is
terms/* (or maps/semester-* in the zettelkasten layout).

Missed-class catch-up (subjects.catch_up, on): a class you skipped, or one that was over before you were up (the
alarm answered, "I'm awake", or your first message of the day), gets a catch-up task in Deadlines, due before that
course's next class (else in 3 days), and a note for that lecture: the one you have for that day, else a short stub
("## What was covered") to fill in. One message lists them, with a **Went to ...** button on each (it takes the task
back, and the stub if you haven't written in it). Rules only; nothing leaves the computer.
"""

from __future__ import annotations

import datetime as dt
import glob
import re
import time
from pathlib import Path

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import termnote
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day

register_defaults(
    "subjects",
    {
        "list": [],
        "timetable": [],
        "holidays": [],  # ["2026-12-25", ...]: no classes those days
        "exam_periods": [],  # [["2026-12-07", "2026-12-18"], ...]: no classes then (exams instead)
        "term_ends": "",  # "2026-12-04": the last day of classes; none after it
        "no_calls_in_class": True,
        "margin_min": 5,
        # a note with your timetable and key dates, read live: "terms/2026-autumn", "maps/semester-*" (the newest
        # matching note), "auto" (terms/*, or maps/semester-* in the zettelkasten layout); empty: off
        "term_note": "",
        "catch_up": True,  # a class you missed gets a catch-up task and a lecture note (see the notes above)
    },
)
CATCH_UP_EVERY = "every 30m"  # classes that ended are looked at this often
CATCH_UP_DAYS = 3  # with no next class in two weeks, the catch-up is due this many days on
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
AUTO_NOTE = {"kurooto": "terms/*.md", "zettelkasten": "maps/semester-*.md"}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class Subjects(Module):
    id = "subjects"
    title = "Subjects and timetable"
    description = "Your courses with short names, and an optional timetable so calls never interrupt a class."

    def __init__(self, app):
        super().__init__(app)
        self._term_cache: dict[str, tuple] = {}  # path -> ((mtime, size), what the note says)
        self._glob_cache: tuple | None = None  # (pattern, when, the note it picked)

    def start(self):
        self.app.availability.blockers["subjects:class"] = self._block
        self.every("term_note", "every 10m", self._term_watch)
        self.every("catch_up", CATCH_UP_EVERY, lambda p: self.catch_up())

    def stop(self):
        super().stop()
        self.app.availability.blockers.pop("subjects:class", None)

    # -------------------------------------------------------------------------------- the term note
    def term_path(self) -> Path | None:
        """The term note to read (subjects.term_note), or None (not set, or not there)."""
        raw = str(self.setting("term_note") or "").strip()
        raw = re.sub(r"^\[\[|\]\]$", "", raw).split("|")[0].strip()
        if not raw or raw.lower() in ("off", "none"):
            return None
        if raw.lower() == "auto":
            raw = AUTO_NOTE.get(layout.of(self.app).preset, AUTO_NOTE["kurooto"])
        raw = raw if raw.lower().endswith(".md") else raw + ".md"
        p = Path(raw).expanduser()
        p = p if p.is_absolute() else self.app.workspace / raw
        if not any(ch in raw for ch in "*?["):
            return p if p.is_file() else None
        hit = self._glob_cache
        if hit and hit[0] == str(p) and time.monotonic() - hit[1] < 60:
            return hit[2]
        found = [Path(f) for f in glob.glob(str(p)) if Path(f).is_file() and not Path(f).stem.endswith("-plan")]
        name = termnote.pick([(str(f), self._read(f)) for f in found], now().date())
        pick = Path(name) if name else None
        self._glob_cache = (str(p), time.monotonic(), pick)
        return pick

    def _read(self, f: Path) -> dict:
        try:
            st = f.stat()
            sig = (st.st_mtime_ns, st.st_size)
            hit = self._term_cache.get(str(f))
            if hit and hit[0] == sig:
                return hit[1]
            data = termnote.parse(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return termnote.empty()
        self._term_cache[str(f)] = (sig, data)
        return data

    def term(self) -> dict:
        """What the term note says (termnote.parse), read again whenever the note changes, over an imported class
        pack's term (Class packs, modules/classpacks.py: the note wins where both say something)."""
        p = self.term_path()
        data = self._read(p) if p else termnote.empty()
        packs = self.app.modules.get("classpacks")
        return packs.under(data) if packs is not None and self.app.is_on("classpacks") else data

    @staticmethod
    def _match(items: list[dict], n: dict) -> dict | None:
        names = {n["slug"], n["name"].lower(), *n.get("aliases", [])}
        for s in items:
            if s["slug"] in names or s["name"].lower() in names or names & {a.lower() for a in s.get("aliases", [])}:
                return s
        return None

    def _term_slugs(self) -> dict[str, str]:
        """The term note's subject slugs -> yours, where a note subject is one you added."""
        own = self.setting("list") or []
        return {n["slug"]: (self._match(own, n) or n)["slug"] for n in self.term()["subjects"]}

    def _term_watch(self, p: dict | None = None) -> bool:
        """Every few minutes: when the term note changed (or another one is picked), Deadlines reads its key dates
        now rather than at its next hourly pass. True if it changed."""
        path = self.term_path()
        sig = None
        if path is not None:
            try:
                st = path.stat()
                sig = [str(path), st.st_mtime_ns, st.st_size]
            except OSError:
                sig = None
        f = self.app.paths.state / "subjects" / "term-note.json"
        if (jload(f, {}) or {}).get("sig") == sig:
            return False
        jsave(f, {"sig": sig})
        data = self.term()
        self.app.events.emit(
            "term_note_read", found=path is not None, classes=len(data["classes"]), dates=len(data["dates"])
        )
        dl = self.app.modules.get("deadlines")
        if dl is not None and self.app.is_on("deadlines") and hasattr(dl, "scan_term"):
            try:
                dl.scan_term()
            except Exception as e:  # the next hourly pass tries again
                self.app.events.emit("deadlines_source_failed", source="scan_term", error=str(e)[:200])
        return True

    def health(self) -> tuple[bool, str]:
        raw = str(self.setting("term_note") or "").strip()
        if raw and raw.lower() not in ("off", "none") and self.term_path() is None:
            return False, f"the term note {raw} isn't in your notes (/term note <note>, or /term note off)"
        return True, ""

    # ---------------------------------------------------------------------------------------- data
    def subjects(self) -> list[dict]:
        """Your subjects, then the term note's (a note subject that's one of yours adds its code as a short name)."""
        out = [dict(s, aliases=list(s.get("aliases", []))) for s in self.setting("list") or []]
        for n in self.term()["subjects"]:
            mine = self._match(out, n)
            if mine is not None:
                mine["aliases"] += [a for a in n["aliases"] if a not in mine["aliases"]]
            else:
                out.append({**n, "aliases": list(n["aliases"]), "from_note": True})
        return out

    def timetable(self) -> list[dict]:
        """Your classes (/class), then the term note's; yours win where both have a class at the same time."""
        rows = list(self.setting("timetable") or [])
        have = {(c["day"], c["start"]) for c in rows}
        slugs = self._term_slugs()
        for c in self.term()["classes"]:
            if (c["day"], c["start"]) in have:
                continue
            have.add((c["day"], c["start"]))
            rows.append(
                {"day": c["day"], "start": c["start"], "end": c["end"], "subject": slugs.get(c["slug"], c["slug"])}
            )
        return rows

    def holidays(self) -> list[str]:
        """Yours (subjects.holidays), the term note's, and your holiday calendars' (Calendar: /cal holidays)."""
        cal = self.app.modules.get("calendar")
        from_cal = cal.holiday_dates() if cal is not None and self.app.is_on("calendar") else set()
        return sorted({*(self.setting("holidays") or []), *self.term()["holidays"], *from_cal})

    def exam_periods(self) -> list[list[str]]:
        out = [list(p) for p in self.setting("exam_periods") or [] if isinstance(p, (list, tuple)) and len(p) == 2]
        return out + [p for p in self.term()["exam_periods"] if p not in out]

    def term_ends(self) -> str:
        """The last day of classes: yours (/term ends), else the term note's."""
        return str(self.setting("term_ends") or "") or self.term()["term_ends"]

    def key_dates(self) -> list[dict]:
        """The term note's key dates, each with the subject it names (or None)."""
        items = self.subjects()
        out = []
        for d in self.term()["dates"]:
            found = self._find(d["text"], items)
            out.append({**d, "subject": found[0] if len(found) == 1 else None})
        return out

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
        return self._find(text, self.subjects())

    @staticmethod
    def _find(text: str, items: list[dict]) -> list[str]:
        found = []
        low = f" {text.lower()} "
        for s in items:
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

    def no_classes(self, day: dt.date | None = None) -> str | None:
        """Why there are no classes on a day at all: "holiday", "exams" (an exam period), "term over" (after the
        term's last day), or None on a normal day."""
        d = (day or now().date()).isoformat()
        if d in self.holidays():
            return "holiday"
        for period in self.exam_periods():
            if str(period[0]) <= d <= str(period[1]):
                return "exams"
        end = self.term_ends()
        if end and d > end:
            return "term over"
        return None

    def classes_on(self, day: dt.date | None = None, include_skipped: bool = False) -> list[dict]:
        day = day or now().date()
        if self.no_classes(day):
            return []
        skip = set() if include_skipped else self.skipped(day)
        out = []
        for c in self.timetable():
            if DAYS.index(c["day"]) != day.weekday() or c["subject"] in skip:
                continue
            s = dt.datetime.combine(day, dt.time.fromisoformat(c["start"]))
            e = dt.datetime.combine(day, dt.time.fromisoformat(c["end"]))
            out.append({**c, "name": self.name_of(c["subject"]), "start_dt": s, "end_dt": e})
        out += self._calendar_classes(day, skip, out)
        return sorted(out, key=lambda c: c["start_dt"])

    # ------------------------------------------------------------------------------ missed-class catch-up
    def woke_at(self, day: dt.date) -> dt.datetime | None:
        """When you were first up that day: the alarm answered, "I'm awake", or your first message after the day
        turned (checkins.day_starts, 05:00). None: no sign yet."""
        try:
            turn = dt.time.fromisoformat(self.app.settings.get("checkins.day_starts") or "05:00")
        except ValueError:
            turn = dt.time(5, 0)
        start = dt.datetime.combine(day, turn)
        for e in self.app.events.tail(20000):
            kind = e.get("kind")
            if kind not in ("message_in", "alarm_up_now", "call_answered"):
                continue
            try:
                t = dt.datetime.fromisoformat(e["ts"])
            except (KeyError, ValueError):
                continue
            if start <= t < start + dt.timedelta(days=1):
                return t
        return None

    def _catch_file(self, day: dt.date) -> Path:
        return self.app.paths.state / "subjects" / f"catchup-{day.isoformat()}.json"

    def catch_up(self, day: dt.date | None = None) -> list[str]:
        """Catch-ups for the classes of that day (today) that are over and that you missed. Returns their lines."""
        if not self.setting("catch_up"):
            return []
        t = now()
        day = day or t.date()
        done = jload(self._catch_file(day), {}) or {}
        skipped, woke, looked = self.skipped(day), None, False
        lines, buttons = [], []
        for c in self.classes_on(day, include_skipped=True):
            slug = c.get("subject") or slugify(c["name"])
            if c["end_dt"] > t or slug in done:
                continue
            if slug not in skipped and not looked:  # the event log is read only when it can matter
                woke, looked = self.woke_at(day), True
            why = "skipped" if slug in skipped else "before you were up" if woke and woke > c["end_dt"] else ""
            if not why:
                continue
            done[slug] = self._make_catch_up(c, slug, day, why)
            lines.append(f"{c['name']} ({c['start']}, {why}): {done[slug]['line']}")
            buttons.append([(f"Went to {c['name'][:24]}", f"cup:{day.isoformat()}|{slug}:went")])
        if lines:
            jsave(self._catch_file(day), done)
            self.app.notify(
                "Catch up on what you missed today:\n" + "\n".join(f"- {x}" for x in lines),
                kind="info",
                why="subjects.catch_up",
                buttons=buttons[:6],
            )
            self.app.events.emit("class_catch_up", n=len(lines))
        return lines

    def _next_class(self, slug: str, after: dt.datetime) -> dt.datetime | None:
        for add in range(1, 15):
            for c in self.classes_on(after.date() + dt.timedelta(days=add), include_skipped=True):
                if (c.get("subject") or slugify(c["name"])) == slug:
                    return c["start_dt"]
        return None

    def _make_catch_up(self, c: dict, slug: str, day: dt.date, why: str) -> dict:
        root = Path(self.app.workspace)
        lecture = layout.path(self.app, "lecture", subject=slug, date=day.isoformat(), slug="missed-class")
        have = sorted(p for p in lecture.parent.glob(f"{day.isoformat()}-*.md") if p != lecture)
        made = False
        if have:
            note = have[0]
        else:
            note = lecture
            if not note.exists():
                note.parent.mkdir(parents=True, exist_ok=True)
                head = layout.frontmatter(
                    self.app, "lecture", note, title=f"{c['name']}: {day:%d %b} (missed)", subject=slug
                )
                note.write_text(
                    f"{head}# {c['name']}: {day:%a %d %b} (missed)\n\nYou missed this class ({why}). Fill this in "
                    "from the slides, a friend's notes or the Classroom posts.\n\n## What was covered\n\n",
                    encoding="utf-8",
                )
                made = True
        rel = note.relative_to(root).with_suffix("").as_posix() if note.is_relative_to(root) else str(note)
        due = self._next_class(slug, c["end_dt"]) or dt.datetime.combine(
            day + dt.timedelta(days=CATCH_UP_DAYS), dt.time(18, 0)
        )
        dl, did = self.app.modules.get("deadlines"), ""
        if dl is not None and self.app.is_on("deadlines"):
            title = f"Catch up: {c['name']} ({day:%a %d %b} class)"
            dl.add(title, due, source="catch_up", kind="task", subject=slug, note=rel)
            from kurooto.modules import deadlines

            did = deadlines.did(title, deadlines.iso(due))
        return {
            "note": rel,
            "made": made,
            "size": note.stat().st_size if made else 0,
            "deadline": did,
            "line": f"catch-up due {due:%a %H:%M}, notes in [[{rel}]]",
        }

    def _went(self, ref: str, act: str) -> str:
        """ "Went after all": the catch-up task goes, and the stub if it's as it was made."""
        day, _, slug = ref.partition("|")
        f = self._catch_file(dt.date.fromisoformat(day))
        done = jload(f, {}) or {}
        it = done.pop(slug, None)
        if not it:
            return "That's gone already."
        dl = self.app.modules.get("deadlines")
        if it.get("deadline") and dl is not None:
            dl._status(it["deadline"], "ignored")
        note = Path(self.app.workspace) / f"{it['note']}.md"
        if it.get("made") and note.is_file() and note.stat().st_size == it.get("size"):
            note.unlink()
        done[slug] = {"went": True}
        jsave(f, done)
        self.app.events.emit("class_catch_up_undone")
        return "OK, you went: no catch-up for it."

    def callbacks(self):
        return {"cup": self._went}

    def _calendar_classes(self, day: dt.date, skip: set[str], have: list[dict]) -> list[dict]:
        """Events in your class calendars (Calendar: calendar.class_calendars) are classes too, unless the timetable
        already has a class then."""
        cal = self.app.modules.get("calendar")
        if cal is None or not self.app.is_on("calendar") or not hasattr(cal, "classes"):
            return []
        out = []
        for c in cal.classes(day):
            if c["subject"] and c["subject"] in skip:
                continue
            if any(h["start_dt"] < c["end_dt"] and c["start_dt"] < h["end_dt"] for h in have):
                continue
            out.append(c)
        return out

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
            Command("term", "the term's dates, or a note to read them from: /term ends 2026-12-04", self._term),
        ]

    def _term(self, msg: Incoming, arg: str) -> str:
        if arg.strip().lower().startswith("note"):
            return self._term_note(arg.strip()[4:].strip())
        a = arg.strip().lower()
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", a)
        try:
            for d in dates:
                dt.date.fromisoformat(d)
        except ValueError:
            return "Dates look like 2026-12-04."
        if a.startswith("ends") and len(dates) == 1:
            self.app.settings.set("subjects.term_ends", dates[0])
            return f"Classes end on {dates[0]}; no after-class questions after that."
        if a.startswith("exams") and len(dates) == 2:
            periods = [p for p in self.setting("exam_periods") or [] if list(p) != sorted(dates)]
            self.app.settings.set("subjects.exam_periods", [*periods, sorted(dates)])
            return f"Exams from {min(dates)} to {max(dates)}: no classes then."
        if a in ("clear", "reset"):
            self.app.settings.set("subjects.term_ends", "")
            self.app.settings.set("subjects.exam_periods", [])
            return "Term dates cleared."
        if a:
            return (
                "Usage: /term ends 2026-12-04, /term exams 2026-12-07 to 2026-12-18, /term clear, "
                "/term note terms/2026-autumn (or off)"
            )
        end = self.term_ends() or "not set"
        exams = ", ".join(f"{p[0]} to {p[1]}" for p in self.exam_periods()) or "none"
        out = [f"Last day of classes: {end}. Exam periods: {exams}."]
        out += self._term_summary()
        return "\n".join(out)

    def _term_summary(self) -> list[str]:
        raw = str(self.setting("term_note") or "").strip()
        if not raw or raw.lower() in ("off", "none"):
            return []
        p = self.term_path()
        if p is None:
            return [f"Term note {raw}: not found."]
        t = self._read(p)  # the note's own (not a class pack's)

        def n(k: int, word: str) -> str:
            return f"{k} {word}" + ("" if k == 1 else "es" if word.endswith("s") else "s")

        out = [
            f"Term note {layout.shown(self.app, p)}: {n(len(t['classes']), 'class')}, "
            f"{n(len(t['holidays']), 'holiday')}, {n(len(t['exam_periods']), 'exam period')}, "
            f"{n(len(t['dates']), 'key date')}."
        ]
        today = now().date().isoformat()
        soon = [d for d in t["dates"] if d["to"] >= today][:3]
        if soon:
            out.append("Next: " + "; ".join(f"{d['from']} {d['what']}" for d in soon))
        return out

    def _term_note(self, arg: str) -> str:
        """/term note <note> | off: read the timetable and key dates from that note from now on."""
        if not arg:
            return "\n".join(self._term_summary()) or "No term note. /term note terms/2026-autumn reads one."
        if arg.lower() in ("off", "none", "clear"):
            self.app.settings.set("subjects.term_note", "")
            self._term_watch()
            return "Term note off: only the dates and classes you set here count now."
        old = self.setting("term_note")
        self.app.settings.set("subjects.term_note", arg)
        self._glob_cache = None
        if self.term_path() is None:
            self.app.settings.set("subjects.term_note", old)
            return f"I can't find {arg} in your notes (a path like terms/2026-autumn, or maps/semester-*)."
        self._term_watch()
        self.app.events.emit("term_note_set")
        return "\n".join(self._term_summary()) + "\nI'll read it again whenever it changes."

    def _subject(self, msg: Incoming, arg: str) -> str:
        m = re.match(r"(?:add\s+)?(?P<name>[^()]+?)\s*(?:\((?P<aliases>[^)]*)\))?\s*$", arg)
        if not arg or not m:
            names = ", ".join(f"{s['name']} ({', '.join(s.get('aliases', []))})" for s in self.subjects())
            return names or "No subjects yet. /subject add Linear Algebra (la, linalg)"
        if arg.lower().startswith("remove "):
            slug = self.resolve(arg[7:])
            self.app.settings.set("subjects.list", [s for s in self.setting("list") or [] if s["slug"] != slug])
            return f"Removed {arg[7:]}." if slug else "No such subject."
        name = m["name"].strip()
        aliases = [a.strip().lower() for a in (m["aliases"] or "").split(",") if a.strip()]
        items = [s for s in self.setting("list") or [] if s["slug"] != slugify(name)]
        items.append({"name": name, "slug": slugify(name), "aliases": aliases})
        self.app.settings.set("subjects.list", items)
        return f"Added {name}" + (f" (also: {', '.join(aliases)})" if aliases else "") + "."

    def _class(self, msg: Incoming, arg: str) -> str:
        rm = re.fullmatch(r"\s*(?:remove|delete|rm)\s+(?P<day>[a-z]{3})[a-z]*\s+(?P<s>\d{1,2}:\d{2})\s*", arg, re.I)
        if rm and rm["day"].lower() in DAYS:
            return self._remove_class(rm["day"].lower(), f"{int(rm['s'][:-3]):02d}{rm['s'][-3:]}")
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

    def _remove_class(self, day: str, start: str) -> str:
        mine = self.setting("timetable") or []
        tt = [c for c in mine if not (c["day"] == day and c["start"] == start)]
        if len(tt) == len(mine):
            if any(c["day"] == day and c["start"] == start for c in self.timetable()):
                return f"The class on {day.title()} {start} comes from your term note or a class pack: change it there."
            return f"No class on {day.title()} at {start} (/classes lists them)."
        self.app.settings.set("subjects.timetable", tt)
        return f"Removed the class on {day.title()} {start}."

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
        rows = sorted(self.timetable(), key=lambda c: (DAYS.index(c["day"]), c["start"]))
        return "\n".join(f"{c['day'].title()} {c['start']}–{c['end']} {self.name_of(c['subject'])}" for c in rows) or (
            "No timetable yet. /class mon 09:00-09:55 la"
        )

    def _skip(self, arg: str, add: bool, day: dt.date | None = None) -> str:
        slugs = [s for s in (self.resolve(x) for x in re.split(r"[,\s]+and\s+|,\s*", arg) if x.strip()) if s]
        if not slugs:
            slugs = self.find_in(arg)
        if not slugs:
            return "Which subject? e.g. /skip la"
        cur = self.set_skip(slugs, add=add, day=day)
        self.app.events.emit("class_skip" if add else "class_attend", subjects=slugs)
        names = ", ".join(self.name_of(s) for s in sorted(cur)) or "nothing"
        if day and day != now().date():
            return f"On {day:%a %d %b} you're skipping: {names}."
        return f"Today you're skipping: {names}. Calls are allowed during skipped classes."

    def intents(self):
        def match(text: str):
            if not re.search(r"\b(skip(?:ping)?|not (?:going|attending)|missing|bunking)\b", text, re.I):
                return None
            if re.match(r"\s*(?:can|could|should|may|shall)\s+i\b", text, re.I):  # a question, not a skip
                return None
            found, day = self.find_in(text), a_day(text)
            if day is None:  # a day it can't pin down: the AI works it out
                return None
            return {"slugs": found, "day": day} if len(found) == 1 else None

        return [
            Intent(
                "skip_class",
                "skipping a class (today, tomorrow or on a weekday)",
                match,
                lambda m, s: self._skip(s["slugs"][0], True, s["day"]),
            )
        ]

    # -------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        cls, t = self.classes_on(), f"{now():%H:%M}"
        over = lambda c: " (over)" if str(c["end"]) <= t else ""  # noqa: E731 (a late wake-up isn't asked about them)
        return {"classes_today": [f"{c['start']}-{c['end']} {c['name']}{over(c)}" for c in cls]} if cls else {}

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
