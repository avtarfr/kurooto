"""Deadlines: one list of what's due, and a chase that doesn't let things slip: a message with Done buttons a day
before, an urgent one six hours before (a call, once Calls is on).

Where deadlines come from: what you add (/due fri 17:00 essay draft, or "add a deadline: essay draft due friday
5pm"), and, if you like, unticked dated tasks in your notes, written like:  - [ ] Essay draft (2026-11-02 17:00)
Quizzes and exams aren't "done"; for those you get a reminder and, with Quiz on, a practice offer.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults("deadlines", {"scan_notes": True, "ping_h": 24, "urgent_h": 6, "max_files": 3000})
EXAMISH = re.compile(r"\b(quiz|exam|midterm|mid-term|finals|midsem|mid-sem|endsem|end-sem|viva|oral|test)\b", re.I)
NOT_EXAM = re.compile(r"\b(view|viewing|graded|results?|solutions?|marks|papers? shown)\b", re.I)
TASK = re.compile(r"^\s*- \[ \] (.*?\((\d{4}-\d{2}-\d{2})(?:[ ,T]+(\d{1,2}:\d{2}))?[^)]*\).*)$")
ADD = re.compile(
    r"^\s*(?:add (?:a )?(?:deadline|assignment|due date)[:\s]+|i have (?:an? )?)"
    r"(?P<what>.+?)\s+due\s+(?P<when>.+)$",
    re.I,
)


def did(title: str, due: str) -> str:
    norm = re.sub(r"\W+", " ", title.lower()).strip()
    return "d" + hashlib.sha1(f"{norm}|{due[:10]}".encode(), usedforsecurity=False).hexdigest()[:8]


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


class Deadlines(Module):
    id = "deadlines"
    title = "Deadlines"
    description = (
        "What's due, from what you add and dated tasks in your notes; a nudge a day before, an urgent one six "
        "hours before."
    )
    requires = ("telegram",)

    @property
    def file(self):
        return self.app.paths.state / "deadlines.json"

    def items(self) -> dict:
        return jload(self.file, {}) or {}

    def start(self):
        self.every("tick", "hourly", self._tick)

    # ------------------------------------------------------------------------------------- sources
    def add(self, title: str, due: dt.datetime, source: str = "manual") -> str:
        iso = due.replace(second=0, microsecond=0).isoformat()
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            i = did(title, iso)
            items.setdefault(
                i,
                {
                    "title": title.strip(),
                    "due": iso,
                    "source": source,
                    "status": "open",
                    "kind": "exam" if EXAMISH.search(title) and not NOT_EXAM.search(title) else "task",
                    "told": [],
                },
            )
            jsave(self.file, items)
        self.app.events.emit("deadline_added", source=source)
        return f"Added: {title.strip()}, due {due:%a %d %b %H:%M} ({human(hours_left(iso))})."

    def mark_done(self, title: str, due: dt.datetime) -> bool:
        """Mark the deadline with this title and due time done (e.g. handed in on Classroom). True if it changed."""
        i = did(title, due.replace(second=0, microsecond=0).isoformat())
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            if items.get(i, {}).get("status") != "open":
                return False
            items[i]["status"] = "done"
            jsave(self.file, items)
        self.app.events.emit("deadline_done", source="sync")
        return True

    def scan_notes(self) -> int:
        """Pick up unticked dated tasks from the notes folder."""
        if not self.setting("scan_notes"):
            return 0
        n = 0
        found = {}
        root = self.app.workspace
        for i, p in enumerate(root.rglob("*.md")):
            if i > (self.setting("max_files") or 3000):
                break
            if any(part.startswith(".") for part in p.relative_to(root).parts) or p.stat().st_size > 1_000_000:
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                m = TASK.match(line)
                if m:
                    title = re.sub(r"\s*\([^)]*\d{4}-\d{2}-\d{2}[^)]*\)", "", m[1]).strip()
                    due = f"{m[2]}T{(m[3] or '23:59').zfill(5)}"
                    found[did(title, due)] = (title, due, p.relative_to(root).as_posix())
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            for i, (title, due, where) in found.items():
                if i not in items:
                    items[i] = {
                        "title": title,
                        "due": due,
                        "source": f"notes:{where}",
                        "status": "open",
                        "kind": "exam" if EXAMISH.search(title) and not NOT_EXAM.search(title) else "task",
                        "told": [],
                    }
                    n += 1
            for i, it in items.items():  # ticked or deleted in the notes: done
                if it["source"].startswith("notes:") and i not in found and it["status"] == "open":
                    it["status"] = "done"
            jsave(self.file, items)
        return n

    # ------------------------------------------------------------------------------------- the chase
    def _tick(self, p: dict | None = None) -> None:
        self.scan_notes()
        t = now()
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            changed = False
            for i, it in items.items():
                if it["status"] != "open":
                    continue
                if it.get("snooze_until") and dt.datetime.fromisoformat(it["snooze_until"]) > t:
                    continue
                h = hours_left(it["due"], t)
                if h < -24:
                    continue
                for mark, limit in (("urgent", self.setting("urgent_h")), ("ping", self.setting("ping_h"))):
                    if h <= limit and mark not in it["told"]:
                        it["told"] += ["ping", "urgent"] if mark == "urgent" else ["ping"]
                        self._tell(i, it, h, urgent=mark == "urgent")
                        changed = True
                        break
            if changed:
                jsave(self.file, items)

    def _tell(self, i: str, it: dict, h: float, urgent: bool) -> None:
        if it["kind"] == "exam":
            text = f"{it['title']}: {human(h)} ({dt.datetime.fromisoformat(it['due']):%a %H:%M})."
            buttons = [[("Practice now", f"dl:{i}:quiz")]] if self.app.is_on("quiz") else None
        else:
            text = f"Due {human(h)}: {it['title']} ({dt.datetime.fromisoformat(it['due']):%a %d %b %H:%M})"
            buttons = [[("Done", f"dl:{i}:done"), ("Not mine", f"dl:{i}:ignore"), ("Snooze 3 h", f"dl:{i}:snooze")]]
        self.app.notify(text, kind="deadline", urgent=urgent, buttons=buttons)
        self.app.events.emit("deadline_told", urgent=urgent)

    def callbacks(self):
        return {"dl": self._button}

    def _button(self, i: str, act: str) -> str:
        if act == "quiz":
            quiz = self.app.modules.get("quiz")
            return quiz.ask_next(None) if quiz else "Quiz is off."
        with Lock(self.app.paths.state, "deadlines"):
            items = self.items()
            it = items.get(i)
            if not it:
                return "That one is gone."
            if act == "snooze":
                it["snooze_until"] = (now() + dt.timedelta(hours=3)).isoformat()
                it["told"] = [x for x in it["told"] if x != "urgent"]
            else:
                it["status"] = "done" if act == "done" else "ignored"
            jsave(self.file, items)
        self.app.events.emit("deadline_" + ("done" if act == "done" else act))
        return {"done": "Marked done.", "ignore": "Removed.", "snooze": "I'll ask again in 3 hours."}[act]

    # ------------------------------------------------------------------------------------ commands
    def upcoming(self, hours: float = 336) -> list[tuple[str, dict, float]]:
        out = []
        for i, it in self.items().items():
            h = hours_left(it["due"])
            if it["status"] == "open" and -24 < h <= hours:
                out.append((i, it, h))
        return sorted(out, key=lambda x: x[2])

    def commands(self):
        return [
            Command("deadlines", "what's due in the next two weeks", self._list),
            Command("due", "add one: /due fri 17:00 essay draft", self._due),
        ]

    def _list(self, msg: Incoming, arg: str) -> str | None:
        self.scan_notes()
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
                return self.add(" ".join(parts[n:]), when)
        return "Usage: /due fri 17:00 essay draft   (or: /due 2026-11-02 lab report)"

    def intents(self):
        def show(text: str):
            if re.search(r"\b(what'?s|what is|anything|show)\b.*\b(due|deadlines?)\b", text, re.I):
                return {"hours": 168 if "week" in text.lower() else 72 if "soon" in text.lower() else 336}
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

        return [
            Intent("show_due", "what's due", show, run_show, questions=True),
            Intent("add_deadline", "add a deadline", add, lambda m, s: self.add(s["what"], s["when"])),
        ]

    # -------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        due = [
            {"id": i, "what": it["title"], "due": human(h), "kind": it["kind"]} for i, it, h in self.upcoming(72)[:10]
        ]
        return {"due_soon": due} if due else {}

    def call_tools(self):
        return [
            Tool(
                "mark_deadline_done",
                "Mark a deadline done (its id is in pending_items).",
                lambda a: self._button(str(a.get("id", "")), "done"),
                {"id": arg()},
                ("id",),
                offline="queue",
                hint="mark_deadline_done when they say something is submitted or finished; add_deadline adds one.",
            ),
            Tool(
                "add_deadline",
                'Add a deadline: what, and when it is due ("fri 23:59", "2026-11-02 17:00").',
                self._tool_add,
                {"title": arg(), "due": arg()},
                ("title", "due"),
                offline="queue",
            ),
        ]

    def _tool_add(self, a: dict) -> str:
        try:
            due = parse_when(str(a.get("due", "")))
        except ValueError:
            return f"I couldn't read the date {a.get('due')!r}."
        return self.add(str(a.get("title") or "untitled"), due.replace(tzinfo=None), source="call")
