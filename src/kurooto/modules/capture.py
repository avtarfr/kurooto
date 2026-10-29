"""After class: a couple of minutes after each class in your timetable ends, Kurooto asks what was worth keeping.
Reply on Telegram (a line or two, photos of the board or slides, files, a voice note) and it goes into that subject's
class log in your notes (<subject>/class-log.md, or where your notes layout keeps it), with the photos and files moved
to the subject's files folder (<subject>/files/, or under files.folder outside your notes) and linked. With Chat on,
the AI also writes a proper study log for the class (the study-log skill).

"Nothing new" ends it; "Later" keeps the question for your evening check-in call. No questions for classes you skip
(/skip), on holidays, in exam periods or after the term's last day (Subjects: /term).

Only some subjects: capture.subjects lists the ones to ask about (empty: every subject), capture.skip_subjects the
ones never to ask about (a subject's short name, full name or alias works in both).

On a call (0.9.2): a question about a class that had a quiz or test today (a Deadlines exam item of that subject due
that day) says so in the call's brief (same_as), so the call asks about both once, or not at all once they've said
how it went. After the call, a question still open for a class the call talked about (Kurooto named the subject and
they answered) is answered with what they said, as a reply would be; one they only said "I already answered that" to
is closed as not needed. It's never asked again.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Incoming, Module

register_defaults(
    "capture",
    {
        "delay_min": 2,
        "study_log": True,  # with Chat on, the AI writes one
        "subjects": [],  # ask only after these subjects' classes; empty: every subject
        "skip_subjects": [],  # never ask after these
    },
)

IMAGES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")
# (0.9.1) an answer that says they weren't there: "I did not attend lab", "skipped it", "didn't go"
_CLASS = r"(?:it|that|the\s+(?:class|lecture|lab|tutorial)|class|lecture|lab|tutorial)"
NOT_THERE = re.compile(
    rf"\b(?:did(?:n['’]?t| not)\s+(?:go|attend|make it)|not\s+attend(?:ed|ing)?|never\s+went|bunked|"
    rf"(?:was|were)(?:n['’]?t| not)\s+there|(?:skipped|missed)\s+{_CLASS})\b|^\W*(?:i\s+)?(?:skipped|missed)\W*$",
    re.I,
)
NOT_THERE_MAX = 160  # longer answers are about the class itself, even when they mention skipping something
# (0.9.2) after a call: "I already answered that", and replies too short to be about the class
ALREADY = re.compile(
    r"\b(?:already\s+(?:answered|told|said|covered|went\s+over)|(?:i\s+)?(?:just\s+)?(?:told|said)\s+(?:you|that)"
    r"|answered\s+(?:that|it|this)\s+already)\b",
    re.I,
)
NOT_AN_ANSWER = re.compile(
    r"^\W*(?:yes|yeah|yep|no|nope|ok(?:ay)?|sure|hmm+|right|all right|fine|later|not now|ask me later)\W*$", re.I
)
# words of a subject's name too general to say which class a sentence is about
GENERIC = {
    "theory", "practice", "introduction", "advanced", "methods", "principles", "applied", "topics", "special",
    "basic", "general", "elementary", "laboratory", "course", "class", "studies", "fundamentals", "seminar",
    "project", "modern", "and", "with",
}  # fmt: skip


def not_there(text: str) -> bool:
    """(0.9.1) A short answer to "How was <class>?" that says they didn't go to it."""
    t = re.sub(r"\s+", " ", text or "").strip()
    return bool(t) and len(t) <= NOT_THERE_MAX and bool(NOT_THERE.search(t))


class Capture(Module):
    id = "capture"
    title = "After-class notes"
    description = (
        "A couple of minutes after each class ends, you're asked what was worth keeping; replies go to its log."
    )
    requires = ("telegram", "subjects")
    privacy = (
        "Your replies, photos and files go into the subject's class log in your notes, on this computer. With Chat on, "
        "your reply and the files you sent go to the AI you picked, to write a study log (capture.study_log)."
    )

    def start(self):
        self.action("ask", self._ask)
        self.app.ask.hooks["capture.answer"] = self._hook
        self.every("plan", "daily 00:10", lambda p: self._plan())
        self._plan()

    def stop(self):
        super().stop()
        self.app.ask.hooks.pop("capture.answer", None)

    # ------------------------------------------------------------------------------------- state
    def _state_file(self, day: dt.date) -> Path:
        return self.app.paths.state / "capture" / f"{day.isoformat()}.json"

    def _set(self, day: str, slug: str, **kw) -> None:
        d = dt.date.fromisoformat(day)
        st = jload(self._state_file(d), {}) or {}
        st[slug] = {**st.get(slug, {}), **kw}
        jsave(self._state_file(d), st)

    def statuses(self, day: dt.date | None = None) -> dict[str, str]:
        """{subject: "asked" | "answered" | "nothing" | "later" | "skipped"} for a day's classes."""
        out = {}
        for slug, s in (jload(self._state_file(day or now().date()), {}) or {}).items():
            status = s.get("status", "")
            if status == "asked" and s.get("qid"):
                q = self.app.ask.get(s["qid"]) or {}
                status = "later" if q.get("status") == "later" else status
            out[slug] = status
        return out

    # ------------------------------------------------------------------------------------ asking
    def _chosen(self, key: str) -> set[str]:
        """The subjects in capture.subjects or capture.skip_subjects, as slugs ("all" or nothing: none)."""
        v = self.setting(key) or []
        if isinstance(v, str):
            v = [] if v.strip().lower() in ("", "all") else v.split(",")
        subjects = self.app.modules["subjects"]
        return {subjects.resolve(str(x)) or str(x).strip().lower() for x in v if str(x).strip()}

    def wanted(self, slug: str) -> bool:
        """Is the after-class question on for this subject? capture.subjects (if any) and not capture.skip_subjects."""
        only = self._chosen("subjects")
        return slug not in self._chosen("skip_subjects") and (not only or slug in only)

    def _plan(self) -> None:
        subjects = self.app.modules["subjects"]
        delay = dt.timedelta(minutes=self.setting("delay_min") or 2)
        for c in subjects.classes_on():
            if not c.get("subject"):
                continue  # a class-calendar event that doesn't name one of your subjects: no log to write it into
            if not self.wanted(c["subject"]):
                continue
            at = c["end_dt"] + delay
            if at > now():
                self.app.scheduler.at(
                    at,
                    "capture.ask",
                    {"subject": c["subject"], "name": c["name"], "day": at.date().isoformat(), "start": c["start"]},
                    key=f"capture:{c['subject']}:{c['end']}",
                    module=self.id,
                    grace_s=3 * 3600,
                )

    def _ask(self, p: dict) -> None:
        subjects = self.app.modules["subjects"]
        day = dt.date.fromisoformat(p["day"])
        if not self.wanted(p["subject"]):  # taken off after the day was planned
            self.app.events.emit("capture_skipped", subject=p["subject"], why="not_chosen")
            return
        if p["subject"] in subjects.skipped(day):
            self._set(p["day"], p["subject"], status="skipped")
            self.app.events.emit("capture_skipped", subject=p["subject"], why="skipped")
            return
        why = subjects.no_classes(day)  # an exam period or the term's end, set after the day was planned
        if why:
            self.app.events.emit("capture_skipped", subject=p["subject"], why=why.replace(" ", "_"))
            return
        qid = self.app.ask.ask(
            f"How was {p['name']}? Anything worth keeping (a definition, a doubt, homework)? Reply here: a line or "
            "two, or photos of the board or slides.",
            choices=["Nothing new"],
            hook="capture.answer",
            hook_payload={"subject": p["subject"], "name": p["name"], "day": p["day"], "start": p.get("start", "")},
            expires=dt.timedelta(hours=20),
            source=self.id,
            title="After class",
            why="capture.after_class",
            about=p["name"],
            item=p["subject"],
            ws_item=f"class:{p['subject']}",
        )
        self._set(p["day"], p["subject"], status="asked", qid=qid)
        self.app.events.emit("capture_asked", subject=p["subject"])

    # ----------------------------------------------------------------------------------- answers
    def _hook(self, q: dict, answer: str) -> str | None:
        """Your answer (from Telegram, the app or a call): into the class log, and a study log by the AI."""
        p = q.get("hook_payload") or {}
        slug, day = p.get("subject", ""), p.get("day") or now().date().isoformat()
        if not slug:
            return None
        if q.get("nothing"):
            self._set(day, slug, status="nothing")
            self.app.events.emit("capture_nothing", subject=slug)
            return f"OK, nothing new from {p.get('name') or slug}."
        files = [self.app.workspace / f for f in q.get("files") or []]
        text = "" if answer == "(files)" else answer
        if not files and not_there(text):
            return self.missed(slug, day, p.get("name"))
        return self.save(slug, day, text, files, name=p.get("name"), start=p.get("start", ""))

    def missed(self, slug: str, day: str, name: str | None = None) -> str:
        """(0.9.1) "I didn't go": the class is marked missed for that day (skipped, as /skip would; a catch-up follows
        when subjects.catch_up is on), and nothing goes into its class log and no study log is started."""
        subjects = self.app.modules["subjects"]
        name = name or subjects.name_of(slug)
        d = dt.date.fromisoformat(day)
        subjects.set_skip([slug], day=d)
        self._set(day, slug, status="skipped")
        self.app.events.emit("capture_missed", subject=slug)
        try:
            subjects.catch_up(d)
        except Exception as e:  # the mark is what matters; a catch-up that fails is tried again by its timer
            self.app.events.emit("capture_failed", subject=slug, error=f"{type(e).__name__}: {e}"[:200])
        when = "today" if d == now().date() else f"on {d:%A}"
        return f"OK, marked {name} as missed {when}; no study log for it."

    def save(self, slug: str, day: str, text: str, files: list[Path], name: str | None = None, start: str = "") -> str:
        """Add what you said, and the files (moved to the subject's files folder and linked), to its class log."""
        name = name or self.app.modules["subjects"].name_of(slug)
        f = layout.path(self.app, "class_log", subject=slug)
        f.parent.mkdir(parents=True, exist_ok=True)
        kept = [
            self._file_away(x, layout.file_dir(self.app, "subject", subject=slug), day) for x in files if x.is_file()
        ]
        links = [layout.file_link(self.app, p, f) for p in kept]
        new = not f.exists()
        with open(f, "a", encoding="utf-8") as out:
            if new:
                head = layout.frontmatter(self.app, "class_log", f, title=f"{name}: class log", bare=True, subject=slug)
                out.write(f"{head}# {name}: class log\n")
            body = "\n\n".join(x for x in [text.strip(), "\n".join(links)] if x)
            out.write(f"\n## {day}\n\n{body}\n")
        self._set(day, slug, status="answered")
        self.app.events.emit("capture_answered", subject=slug, files=len(kept))
        note = f"Saved to {layout.shown(self.app, f)}" + (f" with {len(kept)} file(s)" if kept else "") + "."
        if self.setting("study_log"):
            when = f" at {start}" if start else ""
            jid = daily.run_skill(
                self.app,
                "study-log",
                f"{name}, class on {day}{when}. What I said about it: {text.strip() or '(only the files)'}",
                files=kept or None,
                title=f"Study log: {name}",
            )
            if jid:
                note += " The AI is writing a study log for it."
        return note

    def _file_away(self, src: Path, folder: Path, day: str) -> Path:
        """Move a file you sent (it arrived in the inbox) to the subject's files; leave it where it is if that fails."""
        stem = src.name if src.name.startswith(day) else f"{day}-{src.name}"
        dest, n = folder / stem, 1
        try:
            folder.mkdir(parents=True, exist_ok=True)
            while dest.exists():
                dest = folder / f"{Path(stem).stem}-{n}{Path(stem).suffix}"
                n += 1
            shutil.move(str(src), str(dest))
            return dest
        except OSError:
            return src

    def replies(self):
        return {"capture": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str:
        """A reply to an after-class question sent before questions went through app.ask (an older message)."""
        slug, _, day = ref.partition("|")
        return self.save(slug, day or now().date().isoformat(), msg.text, list(msg.files))

    def callbacks(self):
        return {"cap": lambda ref, act: "OK."}

    # ------------------------------------------------------------------------------------- on calls (0.9.2)
    def call_question(self, q: dict) -> dict:
        """For the call's brief (core/ask.py): an after-class question about a class that had a quiz or test that day
        says so, so the call asks about both at once, or not at all once they've said how it went."""
        p = q.get("hook_payload") or {}
        slug, day = p.get("subject"), str(p.get("day") or "")
        dl = self.app.modules.get("deadlines")
        if not slug or not day or dl is None or not self.app.is_on("deadlines"):
            return {}
        same = [
            str(it.get("title") or "")
            for it in dl.items().values()
            if it.get("subject") == slug
            and it.get("kind") == "exam"
            and str(it.get("due") or "")[:10] == day
            and it.get("status") not in ("removed", "dropped", "cancelled")
        ]
        if not same or not same[0]:
            return {}
        return {
            "same_as": f"{same[0]} was in this class that day: one question covers both. If they've already said "
            "how it went on this call, don't ask this: save what they said with answer_question. Otherwise ask once "
            f'about both ("How did {same[0]} and the class go?").'
        }

    def named(self, slug: str, text: str) -> bool:
        """Does a sentence name this subject: its name, short name or an alias, or a word of its name no other subject
        has ("Bayesian" for "Bayesian Statistics" when no other subject's name has it)."""
        subjects = self.app.modules["subjects"]
        if slug in subjects.find_in(text):
            return True
        rows = subjects.subjects()
        mine = next((s for s in rows if s["slug"] == slug), None)
        if mine is None:
            return False
        others = " ".join(s["name"].lower() for s in rows if s["slug"] != slug)
        low = text.lower()
        for w in re.findall(r"[a-z]{5,}", mine["name"].lower()):
            if w in GENERIC or re.search(rf"\b{w}\b", others):
                continue
            if re.search(rf"\b{w}\b", low):
                return True
        return False

    def covered_by_call(self, lines: list[dict]) -> int:
        """(0.9.2) After a call: each after-class question still open for a class the call talked about (Kurooto named
        the subject and they answered) is answered with what they said, as a reply would be (the class log; a study
        log with Chat on). One they only answered "I already answered that", with nothing said about it before, is
        closed as not needed. One they said "later" to stays. How many were closed."""
        mine = {self.app.name.lower(), "kurooto", "assistant", "ai"}
        rows = [
            (str(x.get("who") or "").lower() in mine, str(x.get("text") or "").strip())
            for x in lines
            if x.get("who") != "(note)"
        ]
        rows = [r for r in rows if r[1]]
        n = 0
        for q in self.app.ask.pending(kind="question", source=self.id):
            slug = (q.get("hook_payload") or {}).get("subject")
            if not slug:
                continue
            said, already, later = [], False, False
            for i, (ours, text) in enumerate(rows):
                if not ours or not self.named(slug, text) or i + 1 >= len(rows) or rows[i + 1][0]:
                    continue
                reply = rows[i + 1][1]
                if ALREADY.search(reply):
                    already = True
                elif re.search(r"\b(?:later|not now)\b", reply, re.I) and len(reply) < 40:
                    later = True
                elif len(reply) >= 12 and not NOT_AN_ANSWER.match(reply):
                    said.append(reply)
            if later:
                continue
            if said:
                self.app.ask.answer(q["id"], " ".join(dict.fromkeys(said))[:2000], "call")
            elif already:
                self.app.ask.expire(q["id"])
            else:
                continue
            self.app.events.emit("capture_covered_by_call", subject=slug, answered=bool(said))
            n += 1
        return n
