"""First-week quests: for your first seven days, one short message a day with one thing to try, each leaving something
real behind: tomorrow's classes in your timetable, a deadline, a reminder, a doubt for the next class.

Only features that are on and pass their checks (what `kurooto doctor` looks at) get a quest, and one you've already
done (there's a timetable, you set a reminder this week) is left out. A quest is done when what it suggests happens
(the event log says so); replying to the message with it works too. Tap Skip this one and tomorrow brings another.
Tap Stop these, or leave a day's quest alone (not done, not skipped, not answered), and they stop for good. No AI;
nothing leaves the computer.

    quests.when   when the day's quest comes (daily 18:00)
    /quests       how far they got; /quests stop ends them

State: state/quests.json (when they started, what was sent and how it went, and why they stopped). Events:
quest_sent, quest_done, quest_skipped, quests_stopped.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "quests",
    {
        "when": "daily 18:00",  # the day's quest
        "days": 7,  # how long the first week lasts
    },
)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass
class Quest:
    id: str
    module: str  # the feature it's for: only when that's on and passes its checks
    text: str  # {subject} (one of yours, by its short name) and {day} (tomorrow: "tue") are filled in
    events: tuple[str, ...]  # any of these after it was sent means it's done
    test: Callable[[dict], bool] | None = None  # ...when the event says so
    have: str = ""  # what already counts as done: "timetable" (there is one), "recent" (one of the events lately)


QUESTS = [
    Quest(
        "timetable",
        "subjects",
        "add tomorrow's classes, so calls and reminders keep out of them. One line each: "
        "/class {day} 09:00-09:55 {subject}",
        (),
        have="timetable",
    ),
    Quest(
        "deadline",
        "deadlines",
        'send me one real deadline, like "I have problem set 3 due fri 17:00" (or /due fri 17:00 essay draft). '
        "I'll remind you before it.",
        ("deadline_added",),
        have="recent",
    ),
    Quest(
        "reminder",
        "reminders",
        'set a reminder for something real: "remind me at 21:00 to pack my bag".',
        ("reminder_set",),
        have="recent",
    ),
    Quest(
        "doubt",
        "doubts",
        'a doubt from class? "I have a doubt about {subject}: <your doubt>". It comes back before the next class.',
        ("doubt_added",),
        have="recent",
    ),
    Quest(
        "quiz",
        "quiz",
        '"quiz me on {subject}": a few questions from your notes, on what you had this week.',
        ("quiz_session",),
        have="recent",
    ),
    Quest(
        "study",
        "study",
        "about to study? /study {subject} 25 times a 25-minute session and counts it in today's study hours.",
        ("study_session_start",),
        have="recent",
    ),
    Quest(
        "checkin",
        "checkins",
        "answer tonight's check-in in a line or two; it goes into your journal.",
        ("checkin_answered",),
        have="recent",
    ),
    Quest(
        "remember",
        "remember",
        'tell me one way you like to be helped: "remember that I prefer short answers".',
        ("remembered",),
        have="recent",
    ),
    Quest(
        "journal",
        "skills",
        "/journal what I did today: a few words, and today's journal entry is written for you.",
        ("skill_run",),
        lambda e: e.get("name") == "journal",
        have="recent",
    ),
]


class Quests(Module):
    id = "quests"
    title = "First-week quests"
    description = "For your first week: one short message a day with one thing to try, each leaving something real."

    def __init__(self, app):
        super().__init__(app)
        self.file = app.paths.state / "quests.json"

    # ----------------------------------------------------------------------------------------- state
    def state(self) -> dict:
        return jload(self.file, {}) or {}

    def _save(self, st: dict) -> None:
        jsave(self.file, st)

    def start(self):
        st = self.state()
        if not st.get("started"):
            st["started"] = now().date().isoformat()
            self._save(st)
        if st.get("stopped"):
            return  # for good
        self.every("daily", self.setting("when") or "daily 18:00", self.daily, respect="quiet")

    # ------------------------------------------------------------------------------------- the checks
    def passes(self, mid: str) -> bool:
        """Is this feature on and working (its own check, and its health check if it has one)?"""
        m = self.app.modules.get(mid)
        if m is None or not self.app.is_on(mid):
            return False
        try:
            ok, _ = m.health()
        except Exception:
            return False
        if ok is False:
            return False
        try:
            owner = {c.id: c.module or c.id for c in self.app.health.checks()}
            return all(owner.get(r.id, r.id) != mid for r in self.app.health.problems())
        except Exception:
            return True  # the registry's own trouble isn't this feature's

    def _events_since(self, mark: int) -> list[dict]:
        """The events logged after byte `mark` of the event log (a quest's own window: a day)."""
        f = self.app.events.file
        try:
            size = f.stat().st_size
            with open(f, "rb") as fh:
                fh.seek(mark if mark <= size else 0)
                data = fh.read()
        except OSError:
            return []
        out = []
        for ln in data.decode("utf-8", "replace").splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out

    def _mark(self) -> int:
        try:
            return self.app.events.file.stat().st_size
        except OSError:
            return 0

    def _done_after(self, q: Quest, mark: int) -> bool:
        if q.have == "timetable":
            sub = self.app.modules.get("subjects")
            return bool(sub is not None and sub.timetable())
        return any(e.get("kind") in q.events and (q.test is None or q.test(e)) for e in self._events_since(mark))

    def _had(self, q: Quest) -> bool:
        """Already done before any quest asked (so it's left out)."""
        if q.have == "timetable":
            return self._done_after(q, 0)
        if q.have == "recent":
            since = (now() - dt.timedelta(days=7)).isoformat()
            for kind in q.events:
                hit = self.app.health.last_event(kind, q.test, key=f"quests:{q.id}:{kind}")
                if hit and str(hit[1].get("ts", "")) >= since:
                    return True
        return False

    def pick(self, st: dict) -> Quest | None:
        """The next quest: in order, for a feature that's on and working, not sent before and not done already."""
        sent = {s["id"] for s in st.get("sent", [])}
        for q in QUESTS:
            if q.id in sent or not self.passes(q.module) or self._had(q):
                continue
            return q
        return None

    # ---------------------------------------------------------------------------------------- the day
    def daily(self, payload: dict | None = None) -> str:
        """Once a day: settle yesterday's quest (done, or ignored: then they stop), then send today's."""
        st = self.state()
        if st.get("stopped"):
            return f"stopped ({st['stopped']})"
        today = now().date()
        last = (st.get("sent") or [None])[-1]
        if last and last.get("date") == today.isoformat():
            return "already sent today"
        if last and last.get("status") == "open":
            q = next((x for x in QUESTS if x.id == last["id"]), None)
            if q is not None and self._done_after(q, int(last.get("mark", 0))):
                self._settle(st, last, "done")
            else:
                return self._stop(st, "ignored")
        started = dt.date.fromisoformat(st.get("started") or today.isoformat())
        days = int(self.setting("days") or 7)
        if (today - started).days >= days or len(st.get("sent", [])) >= days:
            return self._stop(st, "finished")
        q = self.pick(st)
        if q is None:
            return "nothing to suggest today"
        return self._send(st, q, (today - started).days + 1, days)

    def _fill(self, text: str) -> str:
        sub = self.app.modules.get("subjects")
        names = []
        if sub is not None and self.app.is_on("subjects"):
            names = [(s.get("aliases") or [s["slug"]])[0] for s in sub.subjects()]
        tomorrow = DAYS[(now().date() + dt.timedelta(days=1)).weekday()]
        return text.replace("{subject}", names[0] if names else "<subject>").replace("{day}", tomorrow)

    def _send(self, st: dict, q: Quest, day: int, days: int) -> str:
        ref = uuid.uuid4().hex[:8]
        rec = {"id": q.id, "ref": ref, "date": now().date().isoformat(), "mark": self._mark(), "status": "open"}
        st.setdefault("sent", []).append(rec)
        self._save(st)
        self.app.notify(
            f"First week, day {day} of {days}: {self._fill(q.text)}",
            kind="info",
            buttons=[[("Skip this one", f"quest:{ref}:skip"), ("Stop these", f"quest:{ref}:stop")]],
            map_kind="quest",
            map_ref=ref,
        )
        self.app.events.emit("quest_sent", quest=q.id, day=day)
        return f"sent {q.id}"

    def _settle(self, st: dict, rec: dict, status: str) -> None:
        rec["status"] = status
        self._save(st)
        self.app.events.emit("quest_done" if status == "done" else f"quest_{status}", quest=rec["id"])

    def _stop(self, st: dict, why: str) -> str:
        st["stopped"] = why
        st["stopped_at"] = now().isoformat()
        self._save(st)
        self.app.scheduler.cancel_prefix(f"{self.id}:")
        self.app.events.emit("quests_stopped", why=why, sent=len(st.get("sent", [])))
        return f"stopped ({why})"

    # ---------------------------------------------------------------------------------- your answers
    def callbacks(self):
        return {"quest": self._button}

    def _button(self, ref: str, act: str) -> str:
        st = self.state()
        rec = next((s for s in st.get("sent", []) if s.get("ref") == ref), None)
        if act == "stop":
            if not st.get("stopped"):
                self._stop(st, "stop")
            return "OK, no more of these."
        if rec is None or st.get("stopped"):
            return "These have ended."
        if act == "skip":
            if rec["status"] == "open":
                self._settle(st, rec, "skipped")
            return "Skipped. Another one tomorrow."
        return "unknown button"

    def replies(self):
        return {"quest": self._reply}

    def _reply(self, msg: Incoming, ref: str) -> str | None:
        """A reply to a quest: "stop" ends them; anything else counts as an answer and goes on as a message (so
        replying with "remind me at 9 to ..." does it)."""
        st = self.state()
        if msg.text.strip().lower() in ("stop", "stop these", "no more", "no"):
            if not st.get("stopped"):
                self._stop(st, "stop")
            return "OK, no more of these."
        rec = next((s for s in st.get("sent", []) if s.get("ref") == ref), None)
        if rec is not None and rec.get("status") == "open":
            self._settle(st, rec, "answered")
        self.app.handle(
            Incoming(text=msg.text, via=msg.via, message_id=msg.message_id, files=msg.files, respond=msg.respond)
        )
        return None

    def commands(self):
        return [Command("quests", "your first-week quests (/quests stop ends them)", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        st = self.state()
        if arg.strip().lower() in ("stop", "off", "end"):
            if not st.get("stopped"):
                self._stop(st, "stop")
            return "First-week quests stopped for good."
        sent = st.get("sent", [])
        done = [s["id"] for s in sent if s.get("status") in ("done", "answered")]
        if st.get("stopped"):
            why = {"stop": "you stopped them", "ignored": "a day's quest was left alone", "finished": "the week ended"}
            head = f"First-week quests are over ({why.get(st['stopped'], st['stopped'])})."
        else:
            days = int(self.setting("days") or 7)
            head = f"First-week quests: {len(sent)} of {days} sent; the next one comes {self._next_text()}."
        return head + (f" Done: {', '.join(done)}." if done else "")

    def _next_text(self) -> str:
        j = self.app.scheduler.get(f"{self.id}:daily")
        return f"at {j.when.astimezone():%a %H:%M}" if j else "at the next run"
