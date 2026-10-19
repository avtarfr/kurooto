"""Check-ins: at times you choose, Kurooto asks how things are going. Reply to the message and your answer goes
into your journal (notes folder: journal/YYYY-MM-DD.md). Move or skip one in plain English: "move tonight's
check-in to 9:30", "skip the midday check-in", "push the check-in by 30 min", "skip Friday's check-in" (other days
work too: tomorrow, or a weekday). /checkins lists today's, with +30 min and Skip buttons.

Once Calls is on, a check-in can be a phone call instead (Settings → Check-ins → by call). The evening one is a
debrief: how the day went, what each class covered, what slipped, open questions, a quiz if an exam is near, then
tomorrow's priority and when to wake you (it sets the alarm). After the call, with Chat on, the AI writes your
journal and a study log for the classes you talked about, from what you said; without Chat your words go into the
journal as they are.
"""

from __future__ import annotations

import datetime as dt
import re
import time

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day, a_minutes, a_time

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
        "ai_notes": True,  # with Chat on: after a check-in call, the AI writes your journal and study logs
    },
)
NAMES = ("evening", "midday")
CALL_REASON = {"evening": "Evening debrief", "midday": "Midday check-in"}
WORDS = re.compile(
    r"\b(evening|midday|tonight'?s?|today'?s?|tomorrow'?s?|night|afternoon|lunch|(?:mon|tues|wednes|thurs|fri|satur|"
    r"sun)day'?s?)?\s*(check-?in|debrief|call)\b",
    re.I,
)
MOVE = re.compile(r"\b(move|push|postpone|shift|change|make|put|set|reschedule|instead|delay|later)\b", re.I)
SKIP = re.compile(r"\b(skip|cancel|drop|no (?:\w+ )?(?:check-?in|debrief))\b", re.I)


def _label(day: dt.date) -> str:
    today = now().date()
    return "today" if day == today else "tomorrow" if day == today + dt.timedelta(days=1) else f"on {day:%a %d %b}"


class Checkins(Module):
    id = "checkins"
    title = "Check-ins"
    description = "Kurooto asks how your day is going at times you choose; your replies go into your journal."
    requires = ("telegram",)

    def start(self):
        self.action("fire", self._fire)
        self.every("plan", "daily 00:05", self._plan)
        self.app.jobs.then_actions["checkins.notes_done"] = self._notes_done
        self._plan({})

    def _file(self, day: dt.date) -> str:
        return str(self.app.paths.state / "checkins" / f"{day.isoformat()}.json")

    def today(self, day: dt.date | None = None) -> dict:
        return jload(self._file(day or now().date()), {}) or {}

    def _save(self, plan: dict, day: dt.date | None = None) -> None:
        jsave(self._file(day or now().date()), plan)

    def _plan(self, p: dict) -> None:
        """Each day (and at startup): schedule today's check-ins from the settings, unless already planned (one moved
        or skipped ahead of time, e.g. "skip Friday's check-in", is already in that day's plan)."""
        day = now().date()
        plan = self.today(day)
        for name in NAMES:
            t = (self.setting("times") or {}).get(name)
            if t and name not in plan:
                plan[name] = {"time": t, "status": "planned"}
        self._save(plan, day)
        for name, c in plan.items():
            if c["status"] == "planned" and c.get("time"):
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
            self.app.modules["calls"].ring(self._reason(name), key=f"checkins:{name}:{day}")
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

    @staticmethod
    def _reason(name: str) -> str:
        return CALL_REASON.get(name) or f"{name.title()} check-in"

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
        self.app.events.emit("checkin_held", name=name, reason=reason, to_time=f"{when:%H:%M}")
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
        self.app.events.emit("checkin_answered", name=name, chars=len(msg.text), via="telegram")
        if not self.setting("journal"):
            return "Thanks."
        j = daily.append(self.app, f"{name.title()} check-in ({now():%H:%M})", msg.text, dt.date.fromisoformat(day))
        return f"Saved to your journal ({j.parent.name}/{j.name})."

    # ------------------------------------------------------------------------- moving and skipping
    def move(self, name: str, hhmm: str, day: dt.date | None = None, via: str = "telegram") -> str:
        """Set a check-in's time on a day (today unless given). Another day's goes into that day's plan and is
        scheduled when the day comes."""
        day = day or now().date()
        plan = self.today(day)
        before = (plan.get(name) or {}).get("time") or (self.setting("times") or {}).get(name)
        plan[name] = {"time": hhmm, "status": "planned"}
        self._save(plan, day)
        self.app.events.emit("checkin_moved", name=name, from_time=before, to_time=hhmm, day=day.isoformat(), via=via)
        if day != now().date():
            return f"{name.title()} check-in {_label(day)} at {hhmm}."
        at = self._schedule(name, hhmm, day)
        return f"{name.title()} check-in at {at:%H:%M}."

    def postpone(self, name: str, minutes: int, day: dt.date | None = None, via: str = "telegram") -> str:
        day = day or now().date()
        t0 = (self.today(day).get(name) or {}).get("time") or (self.setting("times") or {}).get(name)
        planned = dt.datetime.combine(day, dt.time.fromisoformat(t0)) if t0 else None
        if day == now().date():
            base = max(now(), planned) if planned else now()
        elif planned:
            base = planned
        else:
            return f"There's no {name} check-in {_label(day)} to push back; give a time instead."
        t = base + dt.timedelta(minutes=minutes)
        if t.date() != day:
            return f"That would push the {name} check-in past midnight; skip it instead?"
        return self.move(name, f"{t:%H:%M}", day, via)

    def skip(self, name: str, day: dt.date | None = None, via: str = "telegram") -> str:
        day = day or now().date()
        plan = self.today(day)
        plan[name] = {**plan.get(name, {"time": (self.setting("times") or {}).get(name)}), "status": "skipped"}
        self._save(plan, day)
        if day == now().date():
            self.app.scheduler.cancel(f"checkins:{name}")
        self.app.events.emit("checkin_skipped", name=name, day=day.isoformat(), via=via)
        return f"No {name} check-in {_label(day)}."

    def callbacks(self):
        def btn(name: str, act: str) -> str:
            return self.postpone(name, 30, via="button") if act == "p30" else self.skip(name, via="button")

        return {"chk": btn}

    def commands(self):
        return [
            Command("checkins", "today's check-ins (with +30 min and Skip buttons)", self._list),
            Command("checkin", "move or skip one: /checkin evening 21:30 (or: skip)", self._cmd),
        ]

    def _list(self, msg: Incoming, arg: str) -> str | None:
        plan = self.today()
        rows = [f"{n}: {c.get('time') or '-'} ({c['status']})" for n, c in plan.items()]
        if not rows:
            return "No check-ins today. /checkin evening 22:00 sets one."
        buttons = [
            [(f"{n.title()} +30 min", f"chk:{n}:p30"), (f"Skip {n}", f"chk:{n}:skip")]
            for n, c in plan.items()
            if c["status"] == "planned"
        ]
        if not buttons or not msg.respond:
            return "\n".join(rows)
        msg.reply("\n".join(rows), buttons=buttons)
        return None

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
            day = a_day(text)
            if day is None:  # a day it can't pin down ("yesterday", "next week"): the AI works it out
                return None
            name = "midday" if re.search(r"midday|afternoon|lunch|noon", low) else "evening"
            if re.search(r"\b(?:don'?t|do not|never)\s+(?:skip|cancel)\b", low):
                return None
            if SKIP.search(text):
                return {"name": name, "act": "skip", "day": day}
            mins, tm = a_minutes(text), a_time(text)
            if mins and re.search(r"\b(?:push|postpone|later|delay|by|after)\b", low):
                return {"name": name, "act": "postpone", "mins": mins, "day": day}
            if tm and (MOVE.search(text) or re.search(r"\bat\b", low)):
                return {"name": name, "act": "move", "time": tm, "day": day}
            return None

        def run(msg, s):
            if s["act"] == "skip":
                return self.skip(s["name"], s["day"], via="intent")
            if s["act"] == "postpone":
                return self.postpone(s["name"], s["mins"], s["day"], via="intent")
            return self.move(s["name"], s["time"], s["day"], via="intent")

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
                if at.timestamp() > time.time() - 120:
                    out.append(
                        {
                            "at": int(at.timestamp()),
                            "reason": self._reason(name),
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
        """After a check-in call: with Chat on, the AI writes your journal (and, after the evening debrief, a study log
        for the classes you talked about) from what you said; otherwise your side goes into the journal as it is."""
        _, name, day = (key.split(":") + ["", ""])[:3]
        if not self.setting("journal") or not day:
            return
        said = daily.their_words(self.app, lines)
        if not said:
            return
        self.app.events.emit("checkin_answered", name=name, chars=len(said), via="call")
        payload = {"name": name, "day": day, "said": said}
        if self.setting("ai_notes") and daily.ai_on(self.app):
            jid = daily.run_skill(
                self.app,
                "journal",
                f"From my {name} check-in call on {day}, in my words:\n{said}",
                title=f"Journal from your {name} call",
                then="checkins.notes_done",
                then_payload=payload,
            )
            if jid:
                classes = [c for c in self._classes(dt.date.fromisoformat(day)) if c["status"] in ("", "later")]
                if name == "evening" and classes:
                    daily.run_skill(
                        self.app,
                        "study-log",
                        f"Classes on {day}: {', '.join(c['name'] for c in classes)}. What I said about them on my "
                        "evening debrief call (log only what I said; leave out a class I didn't talk about):\n\n"
                        f"{daily.transcript(self.app, lines)}",
                        title="Study logs from your evening call",
                    )
                self.app.events.emit("checkin_notes_started", name=name, study_logs=len(classes))
                return
        self._journal_raw(payload)

    def _journal_raw(self, p: dict) -> None:
        heading = f"{p['name'].title()} check-in, by call ({now():%H:%M})"
        daily.append(self.app, heading, p["said"], dt.date.fromisoformat(p["day"]))

    def _notes_done(self, job, result, payload: dict) -> None:
        """The AI couldn't write the journal: keep your words anyway."""
        if not result.ok:
            self._journal_raw(payload)

    def call_brief(self) -> dict:
        plan = self.today()
        rows = [f"{n} {c.get('time') or '-'} ({c['status']})" for n, c in plan.items()]
        return {"checkins_today": rows} if rows else {}

    def call_tools(self):
        return [
            Tool(
                "change_checkin",
                "Plan, move, postpone or skip a check-in (names: evening, midday); today unless a day is given.",
                self._tool_change,
                {
                    "name": arg(),
                    "action": {"type": "string", "enum": ["move", "postpone", "skip"]},
                    "when": arg('for move: "21:30"; for postpone: minutes, e.g. "30"'),
                    "day": arg('optional: "tomorrow" or a weekday, e.g. "friday"'),
                },
                ("name", "action"),
                offline="queue",
                hint="change_checkin plans, moves, postpones or skips check-ins (also another day's).",
            ),
            Tool(
                "checkin_script",
                "The steps for a check-in call (evening debrief or midday check-in), with today's details.",
                self._tool_script,
                {"name": arg("evening or midday")},
                offline="brief",
                hint="On a check-in call (the reason is Evening debrief or Midday check-in), first call "
                "checkin_script with that name and follow it.",
            ),
        ]

    def _tool_change(self, a: dict) -> str:
        name = str(a.get("name", "evening")).lower()
        if name not in NAMES:
            return f"There's no {name} check-in (evening or midday)."
        day = a_day(str(a.get("day") or ""))
        if day is None:
            return f"I couldn't tell which day {a.get('day')!r} is; say tomorrow or a weekday."
        act, when = a.get("action"), str(a.get("when", "")).strip()
        if act == "skip":
            return self.skip(name, day, via="call")
        if act == "postpone":
            return self.postpone(name, int(re.sub(r"\D", "", when) or 30), day, via="call")
        tm = a_time(f"at {when}")
        return self.move(name, tm, day, via="call") if tm else f"I couldn't read the time {when!r}."

    def _tool_script(self, a: dict):
        name = str(a.get("name") or "").lower()
        if name in NAMES:
            return self.script(name)
        return {n: self.script(n) for n in NAMES}  # the call line keeps both for when this computer is off

    # ------------------------------------------------------------------------------------- the scripts
    def _classes(self, day: dt.date) -> list[dict]:
        """The day's classes and what became of each one's after-class question: "" (not asked or no answer yet),
        "later", "answered", "nothing", or "skipped"."""
        if not self.app.is_on("subjects"):
            return []
        subj = self.app.modules["subjects"]
        skip = subj.skipped(day)
        cap = self.app.modules.get("capture")
        status = cap.statuses(day) if cap is not None and self.app.is_on("capture") else {}
        return [
            {
                "name": c["name"],
                "start": c["start"],
                "slug": c["subject"],
                "status": "skipped" if c["subject"] in skip else status.get(c["subject"], ""),
            }
            for c in subj.classes_on(day, include_skipped=True)
        ]

    def script(self, name: str) -> str:
        """What the call goes through, step by step, with today's details filled in."""
        app, today = self.app, now().date()
        plan = daily.plan(app, today, 1200)
        if name == "midday":
            return "\n".join(
                [
                    "Midday check-in, about 5 minutes.",
                    *([f"Today's plan:\n{plan}"] if plan else []),
                    "Ask how the morning went against today's plan.",
                    "Re-plan the afternoon with them in two or three blocks.",
                    "Confirm the evening check-in time, or move or skip it (change_checkin).",
                ]
            )
        steps = ["Ask how today went."]
        classes = [c for c in self._classes(today) if c["status"] != "skipped"]
        if classes:
            names = ", ".join(f"{c['name']} ({c['start']})" for c in classes)
            steps.append(f"Today's classes: {names}. For each, ask what it covered and anything unclear.")
            kept = [c["name"] for c in classes if c["status"] == "later"]
            if kept:
                steps.append(
                    f"They kept the after-class question for this call: {', '.join(kept)}. Once they've said what "
                    "was covered, answer it with answer_question."
                )
        steps.append(
            f"Today's plan said:\n{plan}\nAsk what got done and what slipped." if plan else "Ask what slipped."
        )
        steps.append("If pending_items lists open questions, ask them (answer_question).")
        study = app.modules.get("study")
        if study is not None and app.is_on("study"):
            name_of = app.modules["subjects"].name_of
            counted = ", ".join(f"{name_of(k)} {v / 3600:.1f} h" for k, v in study.totals(1).items())
            steps.append(
                (f"Study counted today: {counted}. " if counted else "No study counted on the computer today. ")
                + "Ask about study on paper or away from the computer and log it with log_study."
            )
        exams = self._exams()
        if exams:
            e = exams[0]
            quiz = " (quiz_next, quiz_grade)" if app.is_on("quiz") else ""
            steps.append(
                f"Coming up: {e.get('title')}, {e.get('when') or e.get('due', '')}. Offer a 10-minute quiz now{quiz} "
                "or tomorrow."
            )
        alarm = " and set it with set_alarm" if app.is_on("alarm") else ""
        steps.append(f"Ask tomorrow's top priority and when they want to wake up{alarm}.")
        notes = "journal" + (" and study logs" if classes else "")
        steps.append(
            f"Say goodnight. Don't write notes yourself: their {notes} are written from this call afterwards."
            if self.setting("ai_notes") and daily.ai_on(app)
            else "Say goodnight. What they said goes into their journal after the call."
        )
        head = "Evening debrief, about 5 to 8 minutes. One question at a time; let them talk and keep yours short."
        return "\n".join([head] + [f"{i}. {s}" for i, s in enumerate(steps, 1)])

    def _exams(self) -> list[dict]:
        """Exams and quizzes in the next two weeks (from Deadlines, when it's on), soonest first."""
        dl = self.app.modules.get("deadlines")
        soon = getattr(dl, "exams_soon", None) if dl is not None and self.app.is_on("deadlines") else None
        if not soon:
            return []
        try:
            return list(soon(days=14) or [])
        except Exception as e:
            self.app.events.emit("checkin_script_failed", part="exams", error=str(e)[:200])
            return []
