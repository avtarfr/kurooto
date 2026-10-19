"""Quiz: spaced-repetition questions from your own notes, on Telegram.

Questions come from notes files whose name includes "exam-prep" or "quiz": every bullet under a heading like
"Must know", "Typical questions", "Key results", "Definitions", "Theorems" or "Formulas" is one item. Reply to a
question with your answer: with Chat on, the AI gives the key idea and a grade; otherwise you grade yourself.
Items you know come back less often (SM-2-lite).

    /quiz [subject]     /quizstatus
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re

from kurooto import providers
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults("quiz", {"per_session": 3})
SECTIONS = re.compile(
    r"^##\s+(must know|typical questions|key (results|theorems|definitions)|definitions|theorems|formulas)", re.I
)
GRADE = (
    "You are grading a student's answer to a revision question from their own notes. Reply with JSON only: "
    '{"grade": <0-5, 5 = complete and correct>, "key_idea": "<the one or two sentences they should remember>"}.\n'
)


class Quiz(Module):
    id = "quiz"
    title = "Quiz"
    description = "Spaced-repetition questions from your notes, answered on Telegram."
    requires = ("telegram",)

    def _dir(self):
        return self.app.paths.state / "quiz"

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
                out.setdefault(re.sub(r"[^a-z0-9]+", "-", subj.lower()).strip("-"), []).append(p)
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
        it["due"] = (dt.date.today() + dt.timedelta(days=it["interval"])).isoformat()
        it["history"].append({"date": dt.date.today().isoformat(), "q": q})
        jsave(self._dir() / f"{subject}.json", st)
        self.app.events.emit("quiz_graded", subject=subject, q=q)
        return f"Grade {q}/5. Next time: {it['due']}."

    def replies(self):
        return {"quiz": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str:
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
                return f"{data.get('key_idea', '').strip()}\n\n{note}".strip() + "\n\n/quiz for the next one."
            except (ValueError, TypeError):
                pass
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
            return self.grade(subj, iid, int(act or 0))

        return {"qz": btn}

    def commands(self):
        return [
            Command("quiz", "practise questions from your notes (/quiz subject)", self._cmd),
            Command("quizstatus", "what's due to practise", self._status),
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        subj = None
        if arg:
            sub = self.app.modules.get("subjects")
            subj = (sub.resolve(arg) if sub and self.app.is_on("subjects") else None) or re.sub(
                r"[^a-z0-9]+", "-", arg.lower()
            )
        return self.ask_next(subj)

    def _status(self, msg: Incoming, arg: str) -> str:
        today = dt.date.today().isoformat()
        rows = []
        for s in self.sources():
            items = self.state(s)["items"]
            rows.append(f"{s}: {len(items)} items, {sum(1 for v in items.values() if v['due'] <= today)} due")
        return "\n".join(rows) or "No quiz material yet: a note named 'exam-prep.md' with a '## Must know' list works."

    # -------------------------------------------------------------------------------------- on calls
    def call_tools(self):
        return [
            Tool(
                "quiz_next",
                "The next practice questions (subject optional: defaults to the one with most due).",
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
        ]

    def _tool_next(self, a: dict):
        subj, items = self.due(a.get("subject") or None)
        if not subj or not items:
            return "Nothing due to practise."
        return {
            "subject": subj,
            "items": [{"item": k, "section": v["section"], "question": v["text"]} for k, v in items[:10]],
        }
