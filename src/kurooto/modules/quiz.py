"""Quiz: spaced-repetition questions from your own notes, on Telegram or on a call.

Questions come from notes files whose name includes "exam-prep" or "quiz": every bullet under a heading like
"Must know", "Typical questions", "Key results", "Definitions", "Theorems" or "Formulas" is one item. Reply to a
question with your answer: with Chat on, the AI gives the key idea and a grade; otherwise you grade yourself.
Items you know come back less often (SM-2-lite). A session is a few questions in a row.

With Deadlines on, quizzes follow your quizzes and exams: the evening before one you're offered practice (here, or
by call with Phone calls on); in exam mode (two weeks before) sessions are longer, items come back before the exam,
and a short practice check-in comes every day.

    /quiz [subject]            practise now (with Phone calls on it asks: here or by call?)
    /quiz [subject] call       a quiz call          /quiz at 21:00 [subject]   a quiz check-in later
    /quizstatus
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re

from kurooto import providers
from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import when_from

register_defaults(
    "quiz",
    {
        "per_session": 3,
        "exam_per_session": 6,  # in exam mode
        "offer_at": "19:00",  # the evening before a quiz or exam: offer practice from this time (empty: never)
        "exam_daily": "",  # in exam mode: a practice check-in every day at this time, e.g. "18:00" (empty: never)
        "by_call": False,  # quiz check-ins ring you (with Phone calls on) instead of sending the first question
        "call_min": 10,  # how long a quiz call is meant to take
    },
)
SECTIONS = re.compile(
    r"^##\s+(must know|typical questions|key (results|theorems|definitions)|definitions|theorems|formulas)", re.I
)
GRADE = (
    "You are grading a student's answer to a revision question from their own notes. Reply with JSON only: "
    '{"grade": <0-5, 5 = complete and correct>, "key_idea": "<the one or two sentences they should remember>"}.\n'
)
QUIZ_ME = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?(?:quiz me|test me|give me a quiz|call me for a quiz|do a quiz|"
    r"start a quiz)\b(?P<rest>.*)$",
    re.I,
)
TIME_PART = re.compile(
    r"\b(?:at\s+\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?|\d{1,2}:\d{2}(?:\s*[ap]m)?|\d{1,2}\s*[ap]m)\b", re.I
)
DAY_PART = re.compile(r"\b(?:tonight|tomorrow|in \d+\s*(?:min|mins|minutes|h|hours?))\b", re.I)
BY_CALL = re.compile(r"\b(?:by|on a|over the|with a)\s+(?:call|phone)\b|\bcall me\b|^\s*call\b|\bcall\s*$", re.I)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Quiz(Module):
    id = "quiz"
    title = "Quiz"
    description = (
        "Spaced-repetition questions from your notes, on Telegram or by call; offered the evening before quizzes and "
        "exams, and more often in exam mode."
    )
    requires = ("telegram",)

    def _dir(self):
        return self.app.paths.state / "quiz"

    def start(self):
        self.every("offers", "hourly", self._offers)
        self.action("checkin", self._checkin)
        self.action("exam_daily", self._exam_daily)
        daily = self.setting("exam_daily")
        if not daily:
            self.app.scheduler.cancel("quiz:exam_daily")
        else:
            try:
                self.every("exam_daily", f"daily {daily}", self._exam_daily)
            except ValueError:
                self.app.events.emit("quiz_bad_setting", key="exam_daily")

    # ---------------------------------------------------------------------------------------- items
    def sources(self) -> dict[str, list]:
        """subject -> note files with quiz material."""
        out: dict[str, list] = {}
        root = self.app.workspace
        for p in root.rglob("*.md"):
            name = p.stem.lower()
            if ("exam-prep" in name or "quiz" in name) and not any(
                x.startswith(".") for x in p.relative_to(root).parts
            ):
                subj = p.parent.name if p.parent != root else p.stem
                out.setdefault(slugify(subj), []).append(p)
        return out

    def state(self, subject: str) -> dict:
        st = jload(self._dir() / f"{subject}.json", {"items": {}, "seeded": {}}) or {"items": {}, "seeded": {}}
        for p in self.sources().get(subject, []):
            mtime = str(p.stat().st_mtime)
            if st["seeded"].get(str(p)) == mtime:
                continue
            section = None
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("## "):
                    section = line[3:].strip() if SECTIONS.match(line) else None
                    continue
                m = re.match(r"^\s*[-*]\s+(.{12,})$", line)
                if section and m:
                    text = re.sub(r"\s+", " ", m[1]).strip()
                    iid = hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()[:8]
                    st["items"].setdefault(
                        iid,
                        {
                            "text": text,
                            "section": section,
                            "ef": 2.5,
                            "interval": 0,
                            "reps": 0,
                            "due": dt.date.today().isoformat(),
                            "history": [],
                        },
                    )
            st["seeded"][str(p)] = mtime
        jsave(self._dir() / f"{subject}.json", st)
        return st

    def due(self, subject: str | None) -> tuple[str | None, list]:
        subjects = [subject] if subject else list(self.sources())
        today = dt.date.today().isoformat()
        best = (None, [])
        for s in subjects:
            items = [(k, v) for k, v in self.state(s)["items"].items() if v["due"] <= today]
            items.sort(key=lambda kv: (kv[1]["due"], kv[1]["reps"]))
            if len(items) > len(best[1]):
                best = (s, items)
        return best

    def due_count(self, subject: str | None) -> int:
        return len(self.due(subject)[1])

    def resolve(self, text: str) -> str | None:
        """'LA', 'linear algebra', 'topology' -> the subject's slug (None for nothing)."""
        text = (text or "").strip()
        if not text:
            return None
        sub = self.app.modules.get("subjects")
        return (sub.resolve(text) if sub and self.app.is_on("subjects") else None) or slugify(text)

    def name_of(self, slug: str | None) -> str:
        sub = self.app.modules.get("subjects")
        return (sub.name_of(slug) if sub and self.app.is_on("subjects") else slug) if slug else ""

    # ------------------------------------------------------------------------------------ exam mode
    def _deadlines(self):
        return self.app.modules.get("deadlines") if self.app.is_on("deadlines") else None

    def exams(self) -> list[dict]:
        dl = self._deadlines()
        return dl.exam_mode() if dl else []

    def exam_days(self, subject: str | None) -> float | None:
        """Days until this subject's quiz or exam, when it's in exam mode."""
        return next((e["days"] for e in self.exams() if subject and e["subject"] == subject), None)

    def exam_subject(self) -> str | None:
        """The subject of the nearest quiz or exam in exam mode that has something to practise."""
        modes = [e["subject"] for e in self.exams() if e["subject"]]
        return next((s for s in modes if self.due_count(s)), modes[0] if modes else None)

    # -------------------------------------------------------------------------------------- sessions
    def _session_file(self):
        return self._dir() / "session.json"

    def start_session(self, subject: str | None = None, n: int | None = None) -> str:
        """Practise now: the first of a few questions on Telegram (None: the exam subject, else the most due)."""
        subject = subject or self.exam_subject()
        n = n or (self.setting("exam_per_session") if self.exam_days(subject) else self.setting("per_session")) or 3
        out = self.ask_next(subject)
        subj, items = self.due(subject)
        if items:
            jsave(self._session_file(), {"subject": subj, "left": int(n), "day": dt.date.today().isoformat()})
            self.app.events.emit("quiz_session", subject=subj, n=n, exam=bool(self.exam_days(subj)))
        return out

    def _continue(self) -> str | None:
        """After a graded answer: the next question of the session, or the end of it."""
        s = jload(self._session_file(), None)
        if not s or s.get("day") != dt.date.today().isoformat():
            return None
        s["left"] = int(s.get("left", 1)) - 1
        subj, items = self.due(s.get("subject"))
        if s["left"] <= 0 or not items:
            self._session_file().unlink(missing_ok=True)
            return "That's the session. /quiz for more." if items else "That's everything due for now."
        jsave(self._session_file(), s)
        self.ask_next(subj)
        return None

    def ask_next(self, subject: str | None) -> str:
        subj, items = self.due(subject)
        if not subj or not items:
            if self.sources():
                return "Nothing to practise right now."
            return "I didn't find quiz material: add a note named like 'exam-prep.md' with a '## Must know' list."
        iid, it = items[0]
        self.app.notify(
            f"Quiz ({subj}, {it['section']}):\n{it['text']}\n\nReply with your answer.",
            kind="question",
            map_kind="quiz",
            map_ref=f"{subj}|{iid}",
        )
        return f"{len(items)} due in {subj}."

    def grade(self, subject: str, iid: str, q: int) -> str:
        st = self.state(subject)
        it = st["items"].get(iid)
        if not it:
            return "That question is gone."
        q = max(0, min(5, int(q)))
        if q < 3:
            it["reps"], it["interval"] = 0, 1
        else:
            it["reps"] += 1
            it["interval"] = 1 if it["reps"] == 1 else 3 if it["reps"] == 2 else round(it["interval"] * it["ef"])
        it["ef"] = max(1.3, it["ef"] + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        days = self.exam_days(subject)
        if days is not None:  # exam mode: it comes back at least once more before the exam
            it["interval"] = max(1, min(it["interval"], int(days // 2)))
        it["due"] = (dt.date.today() + dt.timedelta(days=it["interval"])).isoformat()
        it["history"].append({"date": dt.date.today().isoformat(), "q": q})
        jsave(self._dir() / f"{subject}.json", st)
        self.app.events.emit("quiz_graded", subject=subject, q=q)
        return f"Grade {q}/5. Next time: {it['due']}."

    def replies(self):
        return {"quiz": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str | None:
        subj, _, iid = ref.partition("|")
        it = self.state(subj)["items"].get(iid)
        if not it:
            return "That question is gone."
        brain = providers.build(self.app, self.app.settings.get("brain.main") or "") if self.app.is_on("chat") else None
        if brain and brain.available()[0]:
            r = brain.complete(
                f"{GRADE}Question / note: {it['text']}\nTheir answer: {msg.text}", effort="low", timeout=90
            )
            m = re.search(r"\{.*\}", r.text, re.S)
            try:
                data = json.loads(m[0]) if m else {}
                note = self.grade(subj, iid, int(data.get("grade", 0)))
            except (ValueError, TypeError):
                pass
            else:
                text = f"{data.get('key_idea', '').strip()}\n\n{note}".strip()
                if not jload(self._session_file(), None):
                    return text + "\n\n/quiz for the next one."
                msg.reply(text)
                return self._continue()
        msg.reply(
            f"The note says: {it['text']}\nHow did you do?",
            buttons=[
                [
                    ("Forgot", f"qz:{subj}|{iid}:0"),
                    ("Hard", f"qz:{subj}|{iid}:3"),
                    ("Good", f"qz:{subj}|{iid}:4"),
                    ("Easy", f"qz:{subj}|{iid}:5"),
                ]
            ],
        )
        return None

    def callbacks(self):
        def btn(ref: str, act: str) -> str:
            subj, _, iid = ref.partition("|")
            out = self.grade(subj, iid, int(act or 0))
            end = self._continue()
            return f"{out} {end}" if end else out

        return {"qz": btn, "qo": self._offer_button}

    # ---------------------------------------------------------------------------------------- by call
    def _calls_ok(self) -> bool:
        c = self.app.modules.get("calls")
        return bool(c and self.app.is_on("calls") and c.ready()[0])

    def call_quiz(self, subject: str | None = None, at: dt.datetime | None = None) -> str:
        """A quiz call: now (it waits out classes and other no-call times), or at a time."""
        if not self._calls_ok():
            return "Phone calls aren't on, so the quiz is here: /quiz"
        subject = subject or self.exam_subject()
        name = self.name_of(subject)
        reason = f"Quiz call, about {self.setting('call_min') or 10} minutes{' on ' + name if name else ''}."
        key = f"quiz:{subject or 'any'}"
        calls = self.app.modules["calls"]
        self.app.events.emit("quiz_call", later=at is not None)
        if at is not None:
            return calls.schedule(at, reason, key=f"{key}:{at:%Y%m%d%H%M}")
        place = getattr(calls, "place", None)
        if place is not None:
            return place(reason, key=key) or "Calling you."
        when, _ = self.app.availability.next_callable(now())
        reason_now, _ = self.app.availability.call_block(now())
        calls.schedule(max(when, now()), reason, key=key)
        return "Calling you now." if not reason_now else f"I'll call you at {when:%H:%M} ({reason_now})."

    def call_outcome(self, key: str, outcome: str) -> bool:
        if outcome in ("missed", "decline", "skip"):
            subject = (key.split(":") + [""])[1]
            cmd = "/quiz" if subject in ("", "any") else f"/quiz {subject}"
            self.app.notify(f"Missed the quiz call. {cmd} practises here instead.", kind="info")
        return False

    # ------------------------------------------------------------------------- offers and check-ins
    def _offers(self, p: dict | None = None) -> int:
        """The evening before a quiz or exam (from Deadlines): offer practice."""
        dl, at = self._deadlines(), self.setting("offer_at")
        if not dl or not at:
            return 0
        t = now()
        if self.app.availability.night(t):
            return 0
        f = self._dir() / "offered.json"
        offered = jload(f, {}) or {}
        n = 0
        for e in dl.exams_soon(2):
            due = dt.datetime.fromisoformat(e["due"])
            tomorrow = due.date() == t.date() + dt.timedelta(days=1) and t.time() >= dt.time.fromisoformat(at)
            today = due.date() == t.date() and e["hours"] >= 2
            if e["id"] in offered or not (tomorrow or today):
                continue
            offered[e["id"]] = t.isoformat()
            self._offer(e, "tomorrow" if tomorrow else "today")
            n += 1
        if n:
            cutoff = (t - dt.timedelta(days=30)).isoformat()
            jsave(f, {k: v for k, v in offered.items() if v >= cutoff})
        return n

    def _offer(self, e: dict, day: str) -> None:
        subject = e["subject"]
        count = self.due_count(subject) if subject else len(self.due(None)[1])
        text = f"{e['title']} is {day} at {dt.datetime.fromisoformat(e['due']):%H:%M}."
        if not count:
            where = f"{subject}/exam-prep.md" if subject else "an exam-prep note"
            self.app.notify(f"{text} Nothing to practise yet: a '## Must know' list in {where} works.", kind="info")
            return
        row = [("Quiz me now", f"qo:{e['id']}:now")]
        if self._calls_ok():
            row.append(("Call me for a quiz", f"qo:{e['id']}:call"))
        row.append(("Not tonight" if day == "tomorrow" else "No thanks", f"qo:{e['id']}:no"))
        self.app.notify(f"{text} Practise? {count} questions are due.", kind="question", buttons=[row])
        self.app.events.emit("quiz_offered", day=day)

    def _exam_daily(self, p: dict | None = None) -> None:
        """Exam mode's daily practice check-in (the evening before the exam, the offer takes its place)."""
        modes = self.exams()
        if not modes or (p or {}).get("missed"):
            return
        e = modes[0]
        if dt.datetime.fromisoformat(e["due"]).date() <= now().date() + dt.timedelta(days=1):
            return
        subject = e["subject"] or self.exam_subject()
        count = self.due_count(subject) if subject else len(self.due(None)[1])
        if not count:
            return
        if self.setting("by_call") and self._calls_ok():
            self.call_quiz(subject)
            return
        row = [("Quiz me now", f"qo:{e['id']}:now")]
        if self._calls_ok():
            row.append(("Call me", f"qo:{e['id']}:call"))
        row.append(("Skip today", f"qo:{e['id']}:skip"))
        self.app.notify(
            f"Exam mode: {e['title']} {e['when']}. {count} questions to practise. Now?", kind="question", buttons=[row]
        )
        self.app.events.emit("quiz_checkin", via="message", exam=True)

    def _offer_button(self, ref: str, act: str) -> str:
        if ref.startswith("s-"):
            subject = ref[2:] or None
        elif ref.startswith("d") and self._deadlines():
            subject = (self._deadlines().items().get(ref) or {}).get("subject")
        else:
            subject = None
        if act in ("now", "here"):
            return self.start_session(subject)
        if act == "call":
            return self.call_quiz(subject)
        self.app.events.emit("quiz_offer_declined", act=act)
        return "OK, not tonight." if act == "no" else "Skipped for today."

    def schedule_checkin(self, when: dt.datetime, subject: str | None = None, by_call: bool | None = None) -> str:
        """A quiz check-in later: a call (Phone calls on and by call) or the first question on Telegram."""
        by_call = self.setting("by_call") if by_call is None else by_call
        if by_call and self._calls_ok():
            return self.call_quiz(subject, at=when)
        self.app.scheduler.at(
            when,
            "quiz.checkin",
            {"subject": subject},
            key=f"quiz:checkin:{when:%Y%m%d%H%M}",
            module=self.id,
            grace_s=3 * 3600,
            respect="quiet",
        )
        on = f" on {self.name_of(subject)}" if subject else ""
        return f"Quiz{on} at {when:%a %H:%M}: I'll send the first question then."

    def _checkin(self, p: dict) -> None:
        if p.get("missed"):
            return
        subject = p.get("subject")
        if not self.due(subject or self.exam_subject())[1]:
            self.app.notify("Quiz time, but nothing is due to practise right now.", kind="info")
            return
        self.app.events.emit("quiz_checkin", via="message", exam=False)
        self.app.notify("Quiz time.", kind="info")
        self.start_session(subject)

    # ------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command("quiz", "practise questions from your notes (/quiz subject, /quiz subject call)", self._cmd),
            Command("quizstatus", "what's due to practise", self._status),
        ]

    def _parse(self, text: str) -> dict:
        """'linear algebra by call at 21:00' -> {subject, call, when}."""
        call = bool(BY_CALL.search(text))
        here = bool(re.search(r"\bhere\b|\bby (?:text|message)\b", text, re.I))
        parts = [m[0] for m in TIME_PART.finditer(text)] + [m[0] for m in DAY_PART.finditer(text)]
        when = when_from(" ".join(parts)) if parts else None
        rest = BY_CALL.sub(" ", DAY_PART.sub(" ", TIME_PART.sub(" ", text)))
        rest = re.sub(r"\b(?:here|by (?:text|message)|now|please)\b", " ", rest, flags=re.I)
        rest = re.sub(r"\s+", " ", rest).strip(" .,!?")
        rest = re.sub(r"^(?:on|in|about|for)\s+(?:the\s+|my\s+)?", "", rest, flags=re.I)
        return {"subject": self.resolve(rest), "call": call, "here": here, "when": when}

    def _cmd(self, msg: Incoming, arg: str) -> str | None:
        p = self._parse(arg)
        if p["when"]:
            return self.schedule_checkin(p["when"], p["subject"], by_call=p["call"] or None)
        if p["call"]:
            return self.call_quiz(p["subject"])
        if self._calls_ok() and not p["here"]:
            ref = f"s-{(p['subject'] or '')[:50]}"
            msg.reply("Here or by call?", buttons=[[("Here", f"qo:{ref}:here"), ("By call", f"qo:{ref}:call")]])
            return None
        return self.start_session(p["subject"])

    def _status(self, msg: Incoming, arg: str) -> str:
        today = dt.date.today().isoformat()
        rows = []
        for s in self.sources():
            items = self.state(s)["items"]
            rows.append(f"{s}: {len(items)} items, {sum(1 for v in items.values() if v['due'] <= today)} due")
        exam = [f"Exam mode: {e['title']} ({e['when']})" for e in self.exams()]
        out = "\n".join(exam + rows)
        return out or "No quiz material yet: a note named 'exam-prep.md' with a '## Must know' list works."

    def intents(self):
        def match(text: str):
            m = QUIZ_ME.match(text.strip().rstrip(".!"))
            if not m:
                return None
            p = self._parse(m["rest"])
            p["call"] = p["call"] or text.lower().startswith("call me")
            return p

        def run(msg, p):
            if p["when"]:
                return self.schedule_checkin(p["when"], p["subject"], by_call=p["call"] or None)
            if p["call"]:
                return self.call_quiz(p["subject"])
            out = self.start_session(p["subject"])
            return out + (' (Say "quiz me by call" for a call.)' if self._calls_ok() else "")

        return [Intent("quiz_me", "quiz me [on X] [by call] [at 9]", match, run)]

    # -------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        subject = self.exam_subject()
        n = self.due_count(subject) if subject else 0
        return {"quiz_due": f"{n} questions due in {subject} (exam mode)"} if n else {}

    def call_tools(self):
        return [
            Tool(
                "quiz_next",
                "The next practice questions (subject optional: defaults to the exam-mode subject, else the one with "
                "most due).",
                self._tool_next,
                {"subject": arg()},
                offline="brief",
                hint="quiz_next and quiz_grade run a spoken quiz: ask one question, listen, grade it 0-5, move on.",
            ),
            Tool(
                "quiz_grade",
                "Grade their answer to a quiz item: 0 (blank) to 5 (perfect).",
                lambda a: self.grade(str(a.get("subject", "")), str(a.get("item", "")), int(a.get("grade", 3))),
                {"subject": arg(), "item": arg(), "grade": {"type": "integer"}},
                ("subject", "item", "grade"),
                offline="queue",
            ),
            Tool(
                "schedule_quiz",
                'A quiz later: when ("21:00", "tomorrow 8pm"), subject optional, by_call true for a quiz call.',
                self._tool_schedule,
                {"when": arg(), "subject": arg(), "by_call": {"type": "boolean"}},
                ("when",),
                offline="queue",
            ),
        ]

    def _tool_next(self, a: dict):
        subject = self.resolve(str(a.get("subject") or "")) or self.exam_subject()
        subj, items = self.due(subject)
        if (not subj or not items) and subject and not a.get("subject"):
            subj, items = self.due(None)  # the exam subject has nothing due: any subject
        if not subj or not items:
            return "Nothing due to practise."
        days = self.exam_days(subj)
        return {
            "subject": subj,
            **({"exam_in_days": days} if days is not None else {}),
            "items": [{"item": k, "section": v["section"], "question": v["text"]} for k, v in items[:10]],
        }

    def _tool_schedule(self, a: dict) -> str:
        try:
            when = parse_when(str(a.get("when", "")))
        except ValueError:
            return f"I couldn't read the time {a.get('when')!r}."
        return self.schedule_checkin(when, self.resolve(str(a.get("subject") or "")), by_call=a.get("by_call"))
