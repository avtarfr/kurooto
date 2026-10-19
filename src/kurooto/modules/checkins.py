"""Check-ins: at times you choose, Kurooto asks how things are going. Reply to the message and your answer goes
into your journal (notes folder: journal/YYYY-MM-DD.md). Move or skip one in plain English: "move tonight's
check-in to 9:30", "skip the midday check-in", "push the check-in by 30 min".

Once Calls is on, a check-in can be a phone call instead (Settings → Check-ins → by call).
"""

from __future__ import annotations

import datetime as dt
import re
import time

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_minutes, a_time

register_defaults(
    "checkins",
    {
        "times": {"evening": "22:00", "midday": None},  # None = off
        "questions": {
            "evening": "How did today go? What got done, what slipped, and what's first tomorrow?",
            "midday": "How's the morning been? Anything to re-plan for the afternoon?",
        },
        "journal": True,
        "by_call": False,  # with Phone calls on: the check-in is a call (a missed call falls back to Telegram)
    },
)
NAMES = ("evening", "midday")
WORDS = re.compile(
    r"\b(evening|midday|tonight'?s?|today'?s?|night|afternoon|lunch)?\s*(check-?in|debrief|call)\b", re.I
)
MOVE = re.compile(r"\b(move|push|postpone|shift|change|make|put|set|reschedule|instead|delay|later)\b", re.I)
SKIP = re.compile(r"\b(skip|cancel|drop|no (?:\w+ )?(?:check-?in|debrief))\b", re.I)


class Checkins(Module):
    id = "checkins"
    title = "Check-ins"
    description = "Kurooto asks how your day is going at times you choose; your replies go into your journal."
    requires = ("telegram",)

    def start(self):
        self.action("fire", self._fire)
        self.every("plan", "daily 00:05", self._plan)
        self._plan({})

    def _file(self, day: dt.date) -> str:
        return str(self.app.paths.state / "checkins" / f"{day.isoformat()}.json")

    def today(self, day: dt.date | None = None) -> dict:
        return jload(self._file(day or now().date()), {}) or {}

    def _save(self, plan: dict, day: dt.date | None = None) -> None:
        jsave(self._file(day or now().date()), plan)

    def _plan(self, p: dict) -> None:
        """Each day (and at startup): schedule today's check-ins from the settings, unless already planned."""
        day = now().date()
        plan = self.today(day)
        for name in NAMES:
            t = (self.setting("times") or {}).get(name)
            if t and name not in plan:
                plan[name] = {"time": t, "status": "planned"}
        self._save(plan, day)
        for name, c in plan.items():
            if c["status"] == "planned":
                self._schedule(name, c["time"], day)

    def _schedule(self, name: str, hhmm: str, day: dt.date) -> dt.datetime:
        at = dt.datetime.combine(day, dt.time.fromisoformat(hhmm))
        self.app.scheduler.action("checkins.fire", self._fire)
        self.app.scheduler.at(
            at,
            "checkins.fire",
            {"name": name, "day": day.isoformat()},
            key=f"checkins:{name}",
            module=self.id,
            grace_s=2 * 3600,
            respect="quiet",
        )
        return at

    def _fire(self, p: dict) -> None:
        name, day = p["name"], p.get("day") or now().date().isoformat()
        plan = self.today(dt.date.fromisoformat(day))
        if plan.get(name, {}).get("status") != "planned":
            return
        if p.get("missed"):
            self.app.notify(
                f"I missed your {name} check-in (the computer was off). Reply here any time and I'll "
                "put it in your journal.",
                map_kind="checkin",
                map_ref=f"{name}:{day}",
            )
        elif self._by_call() and (held := self._held(name, day)) != "message":
            if held == "later":
                return
            q = (self.setting("questions") or {}).get(name) or "How's it going?"
            self.app.modules["calls"].ring(f"{name.title()} check-in: {q}", key=f"checkins:{name}:{day}")
            plan[name]["status"] = "calling"
            self._save(plan, dt.date.fromisoformat(day))
            self.app.events.emit("checkin_called", name=name)
            return
        else:
            q = (self.setting("questions") or {}).get(name) or "How's it going?"
            self.app.notify(
                f"{name.title()} check-in: {q}\n\n(Reply to this message.)",
                kind="question",
                map_kind="checkin",
                map_ref=f"{name}:{day}",
                buttons=[[("In 30 min", f"chk:{name}:p30"), ("Skip today", f"chk:{name}:skip")]],
            )
        plan[name]["status"] = "asked"
        self._save(plan, dt.date.fromisoformat(day))
        self.app.events.emit("checkin_asked", name=name)

    def _held(self, name: str, day: str) -> str | None:
        """A check-in call during a no-call time (a class, /hold, focus, a calendar event, night) waits until the
        block ends if that's still today ("later"), or comes as a message instead ("message"). None: call now."""
        av = self.app.availability
        reason, _ = av.call_block()
        if not reason:
            return None
        when, _ = av.next_callable()
        if when.date() != now().date() or av.night(when):
            return "message"  # too late for a call today
        self.app.scheduler.at(
            when,
            "checkins.fire",
            {"name": name, "day": day},
            key=f"checkins:{name}",
            module=self.id,
            grace_s=2 * 3600,
            respect="quiet",
        )
        self.app.notify(f"Your {name} check-in call waits until {when:%H:%M} ({reason}).", kind="info")
        self.app.events.emit("checkin_held", name=name)
        return "later"

    def replies(self):
        return {"checkin": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str:
        name, _, day = ref.partition(":")
        day = day or now().date().isoformat()
        plan = self.today(dt.date.fromisoformat(day))
        if name in plan:
            plan[name]["status"] = "answered"
            self._save(plan, dt.date.fromisoformat(day))
        self.app.events.emit("checkin_answered", name=name, chars=len(msg.text))
        if not self.setting("journal"):
            return "Thanks."
        j = self.app.workspace / "journal" / f"{day}.md"
        j.parent.mkdir(parents=True, exist_ok=True)
        new = not j.exists()
        with open(j, "a", encoding="utf-8") as f:
            if new:
                f.write(f"# {day}\n")
            f.write(f"\n## {name.title()} check-in ({now():%H:%M})\n\n{msg.text.strip()}\n")
        return f"Saved to your journal ({j.parent.name}/{j.name})."

    # ------------------------------------------------------------------------- moving and skipping
    def move(self, name: str, hhmm: str) -> str:
        plan = self.today()
        plan[name] = {"time": hhmm, "status": "planned"}
        self._save(plan)
        at = self._schedule(name, hhmm, now().date())
        return f"{name.title()} check-in at {at:%H:%M}."

    def postpone(self, name: str, minutes: int) -> str:
        c = self.today().get(name)
        base = max(now(), dt.datetime.combine(now().date(), dt.time.fromisoformat(c["time"]))) if c else now()
        t = base + dt.timedelta(minutes=minutes)
        return self.move(name, f"{t:%H:%M}")

    def skip(self, name: str) -> str:
        plan = self.today()
        plan[name] = {**plan.get(name, {"time": None}), "status": "skipped"}
        self._save(plan)
        self.app.scheduler.cancel(f"checkins:{name}")
        return f"No {name} check-in today."

    def callbacks(self):
        def btn(name: str, act: str) -> str:
            return self.postpone(name, 30) if act == "p30" else self.skip(name)

        return {"chk": btn}

    def commands(self):
        return [
            Command("checkins", "today's check-ins", self._list),
            Command("checkin", "move or skip one: /checkin evening 21:30 (or: skip)", self._cmd),
        ]

    def _list(self, msg: Incoming, arg: str) -> str:
        plan = self.today()
        rows = [f"{n}: {c.get('time') or '-'} ({c['status']})" for n, c in plan.items()]
        return "\n".join(rows) or "No check-ins today. /checkin evening 22:00 sets one."

    def _cmd(self, msg: Incoming, arg: str) -> str:
        m = re.match(r"(\w+)\s+(.+)", arg)
        if not m or m[1].lower() not in NAMES:
            return "Usage: /checkin evening 21:30   (or midday 13:30; 'skip' drops it for today)"
        name, what = m[1].lower(), m[2].strip().lower()
        if what == "skip":
            return self.skip(name)
        tm = a_time(f"at {what}")
        return self.move(name, tm) if tm else "What time? e.g. /checkin evening 21:30"

    def intents(self):
        def match(text: str):
            if not WORDS.search(text) or re.search(r"\b(?:call|ring) me\b", text, re.I):
                return None
            low = text.lower()
            name = "midday" if re.search(r"midday|afternoon|lunch|noon", low) else "evening"
            if re.search(r"\b(?:don'?t|do not|never)\s+(?:skip|cancel)\b", low):
                return None
            if SKIP.search(text):
                return {"name": name, "act": "skip"}
            mins, tm = a_minutes(text), a_time(text)
            if mins and re.search(r"\b(?:push|postpone|later|delay|by|after)\b", low):
                return {"name": name, "act": "postpone", "mins": mins}
            if tm and (MOVE.search(text) or re.search(r"\bat\b", low)):
                return {"name": name, "act": "move", "time": tm}
            return None

        def run(msg, s):
            if s["act"] == "skip":
                return self.skip(s["name"])
            if s["act"] == "postpone":
                return self.postpone(s["name"], s["mins"])
            return self.move(s["name"], s["time"])

        return [Intent("move_checkin", "move, postpone or skip a check-in", match, run)]

    # -------------------------------------------------------------------------------------- by call
    def _by_call(self) -> bool:
        calls = self.app.modules.get("calls")
        return bool(self.setting("by_call") and calls and self.app.is_on("calls") and calls.ready()[0])

    def call_schedule(self) -> list[dict]:
        """Today's check-in calls, so the call line can ring them if this computer is off then."""
        if not self._by_call():
            return []
        day, out = now().date(), []
        for name, c in self.today(day).items():
            if c.get("status") == "planned" and c.get("time"):
                at = dt.datetime.combine(day, dt.time.fromisoformat(c["time"]))
                q = (self.setting("questions") or {}).get(name) or "How's it going?"
                if at.timestamp() > time.time() - 120:
                    out.append(
                        {
                            "at": int(at.timestamp()),
                            "reason": f"{name.title()} check-in: {q}",
                            "alarm": False,
                            "key": f"checkins:{name}:{day.isoformat()}",
                        }
                    )
        return out

    def call_outcome(self, key: str, outcome: str) -> bool:
        _, name, day = (key.split(":") + ["", ""])[:3]
        plan = self.today(dt.date.fromisoformat(day)) if day else {}
        if name not in plan:
            return False
        if outcome == "answered":
            plan[name]["status"] = "answered"
        elif outcome in ("missed", "decline", "skip"):
            plan[name]["status"] = "asked"
            q = (self.setting("questions") or {}).get(name) or "How's it going?"
            self.app.notify(
                f"{name.title()} check-in (missed call): {q}\n\n(Reply to this message.)",
                kind="question",
                map_kind="checkin",
                map_ref=f"{name}:{day}",
            )
        self._save(plan, dt.date.fromisoformat(day))
        return False

    def call_transcript(self, key: str, lines: list[dict]) -> None:
        """What you said on a check-in call goes into your journal (your side only)."""
        _, name, day = (key.split(":") + ["", ""])[:3]
        if not self.setting("journal") or not day:
            return
        ai = self.app.name
        said = " ".join(x.get("text", "").strip() for x in lines if x.get("who") != ai).strip()
        if not said:
            return
        j = self.app.workspace / "journal" / f"{day}.md"
        j.parent.mkdir(parents=True, exist_ok=True)
        new = not j.exists()
        with open(j, "a", encoding="utf-8") as f:
            if new:
                f.write(f"# {day}\n")
            f.write(f"\n## {name.title()} check-in, by call ({now():%H:%M})\n\n{said}\n")
        self.app.events.emit("checkin_answered", name=name, chars=len(said), via="call")

    def call_brief(self) -> dict:
        plan = self.today()
        rows = [f"{n} {c.get('time') or '-'} ({c['status']})" for n, c in plan.items()]
        return {"checkins_today": rows} if rows else {}

    def call_tools(self):
        return [
            Tool(
                "change_checkin",
                "Move, postpone or skip today's check-in (names: evening, midday).",
                self._tool_change,
                {
                    "name": arg(),
                    "action": {"type": "string", "enum": ["move", "postpone", "skip"]},
                    "when": arg('for move: "21:30"; for postpone: minutes, e.g. "30"'),
                },
                ("name", "action"),
                offline="queue",
                hint="change_checkin moves, postpones or skips today's check-ins.",
            )
        ]

    def _tool_change(self, a: dict) -> str:
        name = str(a.get("name", "evening")).lower()
        if name not in NAMES:
            return f"There's no {name} check-in (evening or midday)."
        act, when = a.get("action"), str(a.get("when", "")).strip()
        if act == "skip":
            return self.skip(name)
        if act == "postpone":
            return self.postpone(name, int(re.sub(r"\D", "", when) or 30))
        tm = a_time(f"at {when}")
        return self.move(name, tm) if tm else f"I couldn't read the time {when!r}."
