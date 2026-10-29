"""Quiz: spaced-repetition questions from your own notes, on Telegram or on a call.

Questions come from notes files whose name includes "exam-prep" or "quiz": every bullet under a heading like
"Must know", "Typical questions", "Key results", "Definitions", "Theorems" or "Formulas" is one item. Reply to a
question with your answer: with Chat on, the AI gives the key idea and a grade; otherwise you grade yourself.
Items you know come back less often (SM-2-lite). A session is a few questions in a row.

With Deadlines on, quizzes follow your quizzes and exams: the evening before one you're offered practice (here, or
by call with Phone calls on); in exam mode (two weeks before) sessions are longer, items come back before the exam,
and a short practice check-in comes every day.

    /quiz [subject]            practise now (with Phone calls on it asks: here or by call?; with quiz.by_call on
                               too, it calls straight away: "/quiz [subject] here" keeps it on Telegram)
    /quiz [subject] call       a quiz call          /quiz at 21:00 [subject]   a quiz check-in later
    /quizstatus

Link recall cards (modules/quiz_links.py): the concept graph's links between notes as review cards, answered in your
own words and graded by you, up to five a day with quiz.links on.

    /card                      a link card now            /cards [on|off]    how they're going (or turn them on, off)

Cards Kurooto wrote (0.8.14, add_card): Brain's dream cards (mind/dream.py) that you kept, in the concept's subject
(or "kurooto-cards"), marked with who wrote them and the answer it wrote for grading; /quiz asks them like your own.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from kurooto import providers
from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.quiz_links import LinkCards
from kurooto.modules.text import when_from


def md_files(root: Path, keep=None) -> list[Path]:
    """root.rglob("*.md") in the same order, without going into hidden folders (.git, .obsidian, .trash): nothing in
    one is quiz material, and a notes folder's .git alone can hold tens of thousands of files (0.6.1: Study mode's
    pane asks for this twice a request). keep(name): only the names it says yes to."""
    match = re.compile(fnmatch.translate(os.path.normcase("*.md"))).match
    entries: dict[str, list[os.DirEntry]] = {}
    order = [str(root)]

    def visit(d: str) -> None:  # Path.walk's top-down order: a folder, then its folders, then each one's own
        try:
            with os.scandir(d) as it:
                entries[d] = list(it)
        except OSError:
            entries[d] = []
            return
        subs = []
        for e in entries[d]:
            try:
                if e.is_dir(follow_symlinks=False) and not e.name.startswith("."):
                    subs.append(e.path)
            except OSError:
                continue
        order.extend(subs)
        for sub in subs:
            visit(sub)

    visit(str(root))
    return [
        Path(d) / e.name
        for d in order
        for e in entries.get(d, [])
        if match(os.path.normcase(e.name)) and (keep is None or keep(e.name))
    ]


register_defaults(
    "quiz",
    {
        "per_session": 3,
        # (0.9.0) a session ends with one extra card on a concept another feature marked "learning now" (Brain's
        # frontier), after the usual ones; nothing changes until something marks one
        "learning_now": True,
        "exam_per_session": 6,  # in exam mode
        "offer_at": "19:00",  # the evening before a quiz or exam: offer practice from this time (empty: never)
        "exam_daily": "",  # in exam mode: a practice check-in every day at this time, e.g. "18:00" (empty: never)
        "by_call": False,  # /quiz, "quiz me" and quiz check-ins ring you (with Phone calls on); "here" keeps text
        "call_min": 10,  # how long a quiz call is meant to take
        "links": False,  # link recall cards from the concept graph's links come by themselves (/card works anyway)
        "links_per_day": 3,  # the most link cards a day (at most 5)
        "links_at": "daily 11:00,16:00,20:00",  # when one may come (never in a class, focus time or the night)
        "links_check": False,  # a local model (Local AI models) says how close your answer came; never a cloud AI
        "links_frontier": False,  # of the link cards due the same day, those on concepts you're ready for come first
        "to_doubts": True,  # after a call, questions you got wrong on it (graded below 3) are offered as doubts, once
        "call_frontier": False,  # on a call, the due questions on concepts you are ready for come first (none added)
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


CARDS_FILE = "cards.json"  # subject -> how many cards Kurooto wrote there (Brain's dream cards), so /quiz finds them
CARD_SECTION = "Kurooto's cards"
CARD_FALLBACK = "kurooto-cards"  # the subject of a card whose concept belongs to none of yours
WEAK_FILE = "call-weak.json"  # questions graded below 3 on a call, offered as doubts once it ends (quiz.to_doubts)
WEAK_CHECK_MIN = 3  # how often to look whether the call they were missed on has ended


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Quiz(Module):
    id = "quiz"
    title = "Quiz"
    description = (
        "Spaced-repetition questions from your notes, on Telegram or by call; offered the evening before quizzes and "
        "exams, and more often in exam mode. Link recall cards turn the concept graph's links into questions too."
    )
    requires = ("telegram",)

    def __init__(self, app):
        super().__init__(app)
        self.links = LinkCards(self)  # link recall cards (modules/quiz_links.py)

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
        self.action("links_later", self.links.tick)
        self.action("weak_offer", self._weak_offer)
        if not self.setting("links"):
            self.app.scheduler.cancel("quiz:links")
        else:
            try:
                self.every("links", self.setting("links_at") or "daily 11:00,16:00,20:00", self.links.tick)
            except ValueError:
                self.app.events.emit("quiz_bad_setting", key="links_at")

    # ---------------------------------------------------------------------------------------- items
    def sources(self) -> dict[str, list]:
        """subject -> note files with quiz material."""
        out: dict[str, list] = {}
        root = self.app.workspace
        for p in md_files(root, lambda n: "exam-prep" in n.lower() or "quiz" in n.lower()):  # as below
            name = p.stem.lower()
            if ("exam-prep" in name or "quiz" in name) and not any(
                x.startswith(".") for x in p.relative_to(root).parts
            ):
                subj = p.parent.name if p.parent != root else p.stem
                out.setdefault(slugify(subj), []).append(p)
        return out

    def load(self, subject: str) -> dict:
        """A subject's quiz state with every part there: a file from an import or an older version may lack some."""
        st = jload(self._dir() / f"{subject}.json", {}) or {}
        st = st if isinstance(st, dict) else {}
        for key in ("items", "seeded"):
            if not isinstance(st.get(key), dict):
                st[key] = {}
        today = dt.date.today().isoformat()
        for iid, it in list(st["items"].items()):
            if not isinstance(it, dict) or not it.get("text"):
                del st["items"][iid]
                continue
            for k, v in (("section", ""), ("ef", 2.5), ("interval", 0), ("reps", 0), ("due", today), ("history", [])):
                it.setdefault(k, v)
        return st

    def state(self, subject: str) -> dict:
        st = self.load(subject)
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

    # ------------------------------------------------------------------------ cards Kurooto wrote (0.8.14)
    def card_subjects(self) -> list[str]:
        """Subjects with cards Kurooto added (add_card), with or without a quiz note of their own."""
        idx = jload(self._dir() / CARDS_FILE, {}) or {}
        return [s for s, n in idx.items() if isinstance(n, int) and n > 0] if isinstance(idx, dict) else []

    def _count_cards(self, subject: str, delta: int) -> None:
        idx = jload(self._dir() / CARDS_FILE, {}) or {}
        idx = idx if isinstance(idx, dict) else {}
        idx[subject] = max(0, int(idx.get(subject) or 0) + delta)
        jsave(self._dir() / CARDS_FILE, {k: v for k, v in idx.items() if v})

    def add_card(
        self,
        subject: str | None,
        text: str,
        by: str = "kurooto",
        concept: str = "",
        due: dt.date | None = None,
        answer: str = "",
    ) -> str | None:
        """A card that isn't from a quiz note: Brain's dream cards (mind/dream.py), added only after a tap. It's marked
        with who wrote it (`by`), so its recall can be told apart from your own cards'. Returns its id (the same text
        twice is one card), or None for a text too short to ask."""
        text = re.sub(r"\s+", " ", text or "").strip()
        if len(text) < 12:
            return None
        subject = slugify(subject or "") or CARD_FALLBACK
        iid = "k" + hashlib.sha1(f"{by}|{text}".encode(), usedforsecurity=False).hexdigest()[:7]
        st = self.load(subject)
        if iid in st["items"]:
            return iid
        today = dt.date.today()
        st["items"][iid] = {
            "text": text,
            "section": CARD_SECTION,
            "ef": 2.5,
            "interval": 0,
            "reps": 0,
            "due": (due or today + dt.timedelta(days=1)).isoformat(),
            "history": [],
            "by": by,
            "concept": concept,
            "made": today.isoformat(),
            **({"answer": re.sub(r"\s+", " ", answer).strip()[:300]} if answer else {}),
        }
        jsave(self._dir() / f"{subject}.json", st)
        self._count_cards(subject, 1)
        self.app.events.emit("quiz_card_added", by=by)
        return iid

    def remove_card(self, subject: str, iid: str) -> bool:
        """Take out a card add_card made (an Undo); a card from your own notes is never removed here."""
        st = self.load(subject)
        it = st["items"].get(iid)
        if not it or not it.get("by"):
            return False
        del st["items"][iid]
        jsave(self._dir() / f"{subject}.json", st)
        self._count_cards(subject, -1)
        return True

    def due(self, subject: str | None) -> tuple[str | None, list]:
        subjects = [subject] if subject else list(dict.fromkeys([*self.sources(), *self.card_subjects()]))
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
        if (s["left"] <= 0 or not items) and not s.get("extra"):  # (quiz.learning_now) one more, after the usual
            extra = self._learning_extra()
            if extra is not None:
                s["extra"], s["left"] = True, 0
                jsave(self._session_file(), s)
                self._ask_item(*extra, note="learning now")
                return None
        if s["left"] <= 0 or not items:
            self._session_file().unlink(missing_ok=True)
            return "That's the session. /quiz for more." if items else "That's everything due for now."
        jsave(self._session_file(), s)
        self.ask_next(subj)
        return None

    def _learning_extra(self) -> tuple[str, str, dict] | None:
        """(quiz.learning_now) A card on a concept marked "learning now" (mind/frontier.py learning_now): its text or
        section names the concept, and it wasn't answered today. (subject, id, item) or None."""
        if self.setting("learning_now") is False:
            return None
        try:
            from kurooto.mind import frontier
            from kurooto.mind.tom import knowledge

            marked = frontier.learning_now(self.app)
            if not marked:
                return None
            notes = knowledge.concepts(self.app)
            want = {s: notes[s] for s in marked if s in notes}
            if not want:
                return None
            today = dt.date.today().isoformat()
            for subj in dict.fromkeys([*self.sources(), *self.card_subjects()]):
                for iid, it in self.state(subj)["items"].items():
                    if any(h.get("date") == today for h in it.get("history") or []):
                        continue
                    if knowledge.mentions(f"{it.get('section') or ''} {it.get('text') or ''}", want):
                        return subj, iid, it
        except Exception:
            return None
        return None

    def _ask_item(self, subj: str, iid: str, it: dict, note: str = "") -> None:
        self.app.notify(
            f"Quiz ({subj}, {it['section']}{', ' + note if note else ''}):\n{it['text']}\n\nReply with your answer.",
            kind="question",
            map_kind="quiz",
            map_ref=f"{subj}|{iid}",
            why="asked",
        )

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
            why="asked",
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

    def restore(self, subject: str, before: dict) -> None:
        """Items back as they were before grades given elsewhere (Undo of the revision plan's evening answers)."""
        st = self.load(subject)
        st["items"].update(before)
        jsave(self._dir() / f"{subject}.json", st)

    def replies(self):
        return {"quiz": self._answer, "qlink": self.links.answer}

    def _answer(self, msg: Incoming, ref: str) -> str | None:
        subj, _, iid = ref.partition("|")
        it = self.state(subj)["items"].get(iid)
        if not it:
            return "That question is gone."
        brain = providers.build(self.app, self.app.settings.get("brain.main") or "") if self.app.is_on("chat") else None
        if brain and brain.available()[0]:
            r = brain.complete(
                f"{GRADE}Question / note: {it['text']}\n"
                + (f"The expected answer: {it['answer']}\n" if it.get("answer") else "")
                + f"Their answer: {msg.text}",
                effort="low",
                timeout=90,
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
            f"The note says: {it.get('answer') or it['text']}\nHow did you do?",
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

        return {"qz": btn, "qo": self._offer_button, "ql": self.links.button, "qd": self._weak_button}

    # ---------------------------------------------------------------------------------------- by call
    def _calls_ok(self) -> bool:
        c = self.app.modules.get("calls")
        return bool(c and self.app.is_on("calls") and c.ready()[0])

    def call_quiz(self, subject: str | None = None, at: dt.datetime | None = None, why: str = "calls.own") -> str:
        """A quiz call: now (it waits out classes and other no-call times), or at a time. why: "quiz.call" when it
        calls by itself (exam mode, exam season), else it's one you asked for (core/calm.py)."""
        if not self._calls_ok():
            return "Phone calls aren't on, so the quiz is here: /quiz"
        subject = subject or self.exam_subject()
        name = self.name_of(subject)
        reason = f"Quiz call, about {self.setting('call_min') or 10} minutes{' on ' + name if name else ''}."
        key = f"quiz:{subject or 'any'}"
        calls = self.app.modules["calls"]
        self.app.events.emit("quiz_call", later=at is not None)
        if at is not None:
            return calls.schedule(at, reason, key=f"{key}:{at:%Y%m%d%H%M}", why=why)
        place = getattr(calls, "place", None)
        if place is not None:
            return place(reason, key=key, why=why) or "Calling you."
        when, _ = self.app.availability.next_callable(now())
        reason_now, _ = self.app.availability.call_block(now())
        calls.schedule(max(when, now()), reason, key=key, why=why)
        return "Calling you now." if not reason_now else f"I'll call you at {when:%H:%M} ({reason_now})."

    def call_outcome(self, key: str, outcome: str) -> bool:
        if outcome in ("missed", "decline", "skip"):
            subject = (key.split(":") + [""])[1]
            cmd = "/quiz" if subject in ("", "any") else f"/quiz {subject}"
            self.app.notify(f"Missed the quiz call. {cmd} practises here instead.", kind="info", why="quiz.call")
        return False

    def call_transcript(self, key: str, lines: list[dict]) -> None:
        """A quiz call ended (modules/calls): what was missed on it is offered as doubts now."""
        self._weak_offer({})

    # ------------------------------------------------------- missed on a call -> doubts (0.9.0, quiz.to_doubts)
    def _weak_note(self, subject: str, iid: str, q: int) -> None:
        """A question graded below 3 on a call: kept, and offered as a doubt once the call is over (one message for
        the whole call). Nothing is written to your notes until you tap Add."""
        if q >= 3 or not self.setting("to_doubts") or not self.app.is_on("doubts"):
            return
        it = self.load(subject)["items"].get(iid)
        if not it:
            return
        f = self._dir() / WEAK_FILE
        weak = jload(f, {}) or {}
        weak = weak if isinstance(weak, dict) else {}
        weak[f"{subject}|{iid}"] = {"subject": subject, "text": it["text"]}
        jsave(f, dict(list(weak.items())[-12:]))
        self._weak_later()

    def _weak_later(self) -> None:
        later = now() + dt.timedelta(minutes=WEAK_CHECK_MIN)
        self.app.scheduler.at(later, "quiz.weak_offer", {}, key="quiz:weak_offer", module=self.id)

    def _weak_offer(self, p: dict | None = None) -> None:
        """Once the call is over: "Add these as doubts?" with Add and Not now. Still on the call: look again later."""
        f = self._dir() / WEAK_FILE
        weak = jload(f, {}) or {}
        if not isinstance(weak, dict) or not weak:
            return
        if not self.setting("to_doubts") or not self.app.is_on("doubts"):
            f.unlink(missing_ok=True)
            return
        until = self.app.availability.on_call_until(now())
        if until is not None and until > now():
            self._weak_later()
            return
        rid = uuid.uuid4().hex[:8]
        offers = jload(self._dir() / "weak-offers.json", {}) or {}
        offers = {**(offers if isinstance(offers, dict) else {}), rid: list(weak.values())}
        jsave(self._dir() / "weak-offers.json", dict(list(offers.items())[-10:]))
        f.unlink(missing_ok=True)
        lines = [f"{i}. {w['text']}" for i, w in enumerate(weak.values(), 1)]
        one = len(lines) == 1
        self.app.notify(
            f"On the call you missed {'this' if one else 'these'}:\n"
            + "\n".join(lines)
            + f"\n\nAdd {'it' if one else 'them'} to your doubts, to ask in the next class?",
            kind="question",
            buttons=[[("Add to doubts", f"qd:{rid}:add"), ("Not now", f"qd:{rid}:no")]],
            why="quiz.to_doubts",
        )
        self.app.events.emit("quiz_doubts_offered", n=len(lines))

    def _weak_button(self, ref: str, act: str) -> str:
        offers = jload(self._dir() / "weak-offers.json", {}) or {}
        items = offers.pop(ref, None) if isinstance(offers, dict) else None
        if items is None:
            return "That offer is gone."
        jsave(self._dir() / "weak-offers.json", offers)
        if act != "add":
            return "Left out of your doubts."
        doubts, sub = self.app.modules.get("doubts"), self.app.modules.get("subjects")
        if doubts is None or not self.app.is_on("doubts"):
            return "The doubt queue is off (Features → Doubt queue)."
        known = {s["slug"] for s in sub.subjects()} if sub is not None else set()
        added = 0
        for w in items:
            slug = w.get("subject") if w.get("subject") in known else None
            slug = slug or (sub.resolve(str(w.get("subject") or "")) if sub is not None else None)
            if slug:
                doubts.add(slug, w["text"])  # Kurooto's own line, in the subject's doubts note (modules/doubts.py)
                added += 1
        self.app.events.emit("quiz_doubts_added", n=added)
        return f"Added {added} to your doubts." if added else "None of them belongs to one of your subjects."

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
            if e["id"] in offered or not (tomorrow or today) or self._season_call(e["id"]):
                continue  # (a quiz call you picked in Exam season takes the offer's place)
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
            self.app.notify(
                f"{text} Nothing to practise yet: a '## Must know' list in {where} works.",
                kind="info",
                why="quiz.offer",
                about=e["title"],
            )
            return
        row = [("Quiz me now", f"qo:{e['id']}:now")]
        if self._calls_ok():
            row.append(("Call me for a quiz", f"qo:{e['id']}:call"))
        row.append(("Not tonight" if day == "tomorrow" else "No thanks", f"qo:{e['id']}:no"))
        self.app.notify(
            f"{text} Practise? {count} questions are due.",
            kind="question",
            buttons=[row],
            why="quiz.offer",
            about=e["title"],
        )
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
        if not count or self._folded(subject):
            return
        if self.setting("by_call") and self._calls_ok() and self._season_call(e["id"]) is not False:
            self.call_quiz(subject, why="quiz.call")
            return
        row = [("Quiz me now", f"qo:{e['id']}:now")]
        if self._calls_ok():
            row.append(("Call me", f"qo:{e['id']}:call"))
        row.append(("Skip today", f"qo:{e['id']}:skip"))
        self.app.notify(
            f"Exam mode: {e['title']} {e['when']}. {count} questions to practise. Now?",
            kind="question",
            buttons=[row],
            why="quiz.exam_daily",
            about=e["title"],
        )
        self.app.events.emit("quiz_checkin", via="message", exam=True)

    def _folded(self, subject: str | None) -> bool:
        """Brain's morning line about the subject it's most uneasy about (its cards due included) took this check-in's
        place today (0.8.14, mind/study_push.py; mind.study_push.on)."""
        try:
            from kurooto.mind import study_push

            return study_push.folded(self.app, subject, "quiz")
        except Exception:
            return False

    def _season_call(self, exam_id: str) -> bool | None:
        """Exam season (modules/exam_season.py) on: True when you picked the quiz call for this exam, False for its
        other exams (no quiz call rings for them by itself); None when it's off or the exam isn't one of its."""
        s = self.app.modules.get("exam_season")
        return s.quiz_call(exam_id) if s is not None and self.app.is_on("exam_season") else None

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
            self.app.notify("Quiz time, but nothing is due to practise right now.", kind="info", why="quiz.checkin")
            return
        self.app.events.emit("quiz_checkin", via="message", exam=False)
        self.app.notify("Quiz time.", kind="info", why="quiz.checkin")
        self.start_session(subject)

    # ------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command("quiz", "practise questions from your notes (/quiz subject, /quiz subject call)", self._cmd),
            Command("quizstatus", "what's due to practise", self._status),
            Command("card", "a link recall card now: how two of your concepts relate", self.links.cmd_card),
            Command("cards", "link recall cards: due, done, how you did (/cards on, /cards off)", self.links.cmd_cards),
        ]

    def _by_call(self, p: dict) -> bool:
        """quiz.by_call on, Phone calls ready, and they didn't say "here": a quiz request rings rather than texts."""
        return bool(self.setting("by_call")) and not p.get("here") and self._calls_ok()

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
        if p["call"] or self._by_call(p):
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
            if p["call"] or self._by_call(p):
                return self.call_quiz(p["subject"])
            out = self.start_session(p["subject"])
            return out + (' (Say "quiz me by call" for a call.)' if self._calls_ok() else "")

        return [
            Intent(
                "quiz_me",
                "quiz me [on X] [by call] [at 9]",
                match,
                run,
                examples=("quiz me", "quiz me on la by call at 9"),
                guarded="call.place",  # "by call" rings
            )
        ]

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
                self._tool_grade,
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
                guarded="call.place",
                guard_if=lambda a: (
                    bool(self.setting("by_call") if a.get("by_call") is None else a.get("by_call")) and self._calls_ok()
                ),
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
        items, focus = self._frontier_first(items[:10])
        return {
            "subject": subj,
            **({"exam_in_days": days} if days is not None else {}),
            **({"focus": focus} if focus else {}),
            "items": [{"item": k, "section": v["section"], "question": v["text"]} for k, v in items],
        }

    def _frontier_first(self, items: list) -> tuple[list, list[str]]:
        """quiz.call_frontier (0.9.0): the same due questions a call gets, with those on concepts at your frontier or
        partly known (mind/frontier.py) first, then their neighbours, then the rest, each group in due order; and the
        names of those concepts as the call's focus. Never a question that isn't due, never one fewer. Only concept
        names reach the call's AI."""
        if not self.setting("call_frontier") or not items:
            return items, []
        try:
            from kurooto.mind import frontier
            from kurooto.mind.tom import knowledge

            grades = frontier.grades(self.app)
            if not grades:
                return items, []
            notes = knowledge.concepts(self.app)
            ready, focus = (frontier.FRONTIER, frontier.STARTED), {}

            def rank(kv) -> int:
                slugs = knowledge.item_slugs(kv[1], notes)
                for s in slugs:
                    if grades.get(s) in ready and s in notes:
                        focus.setdefault(s, notes[s].title)
                best = max((grades.get(s, 0.0) for s in slugs), default=0.0)
                return 0 if best in ready else 1 if best == frontier.NEAR else 2

            return sorted(items, key=rank), list(focus.values())[:5]
        except Exception as e:
            self.app.events.emit("quiz_failed", error=f"frontier order: {e}"[:200])
            return items, []

    def _tool_grade(self, a: dict) -> str:
        subject, iid, q = str(a.get("subject", "")), str(a.get("item", "")), int(a.get("grade", 3))
        out = self.grade(subject, iid, q)
        try:  # a question missed on the call: offered as a doubt once it's over (quiz.to_doubts)
            self._weak_note(subject, iid, max(0, min(5, q)))
        except Exception as e:
            self.app.events.emit("quiz_failed", error=f"doubt offer: {e}"[:200])
        return out

    def _tool_schedule(self, a: dict) -> str:
        try:
            when = parse_when(str(a.get("when", "")))
        except ValueError:
            return f"I couldn't read the time {a.get('when')!r}."
        return self.schedule_checkin(when, self.resolve(str(a.get("subject") or "")), by_call=a.get("by_call"))
