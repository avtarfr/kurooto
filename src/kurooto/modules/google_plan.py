"""Agent plan: a calendar of its own, "Agent plan", that Kurooto makes in your Google Calendar for the time blocks it
plans with you (the morning plan, "block 2 to 4 for the problem set" on a call). Kurooto writes only to that calendar:
Google's permission for it ("calendars this app creates") doesn't let it see or change any other calendar. Hide or
delete the calendar in Google Calendar any time; Kurooto makes a new one the next time it plans something.
With several Google accounts, it lives on the one you choose on its card (or /google use plan personal).

    /blocks                          today's blocks
    /blocks add 14:00-15:30 problem set 4
    /blocks clear                    remove today's blocks (only Kurooto's own)
    /blocks shift [19:00 | in 2 hours]   reschedule the day: today's blocks still to do, from then (default now)
    /blocks undo                     put the blocks back where they were before the last reschedule

Rescheduling the day ("reschedule my day", "push my day by 2 hours", "I just woke up, reschedule my day from 7", or
on a call): the blocks you haven't done (still to come, and with a late start the ones you slept through) move to
start then, in their order, each as long as it was, the breaks between them kept (at most GAP_MAX); pushing "by" some
time moves only the ones not over yet. A block planned twice keeps its first. One that would end after LATEST_H past
midnight is left out and named. The new plan goes in the daily note too.
"""

from __future__ import annotations

import datetime as dt
import re
import urllib.parse

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.google import GoogleError, GooglePart, NeedsSignIn

register_defaults("agent_plan", {"name": "Agent plan", "remind_min": 5})
GAP_MAX = dt.timedelta(minutes=45)  # a reschedule keeps the breaks between blocks, up to this long
LATEST_H = 3  # ... and fits blocks up to this hour after midnight
SHIFT = re.compile(
    r"^(?:please |can you |could you )?(?:(?:i (?:just )?(?:woke up|got up)|i'?m (?:up|awake))[,.;:!]* "
    r"(?:so |and |now )?"
    r"(?:please |can you )?)?(?:re-?schedule|re-?plan|shift|push|move)(?: (?:my|the|today'?s))? (?:day|plan|schedule|"
    r"blocks?)(?: for today| accordingly)*(?:(?:(?: to start| starting)(?: from| at)?|(?: from| at)) "
    r"(?P<from>(?:in )?[\w: ]+?))?"
    r"(?: by (?P<by>[\w ]+?))?[.!?]*$",
    re.I,
)
TIME = re.compile(r"^(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|–|to)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(.+)$", re.I)


def when(text: str, base: dt.datetime | None = None) -> dt.datetime:
    """'14:00', '2pm', 'tomorrow 9am', '2026-10-20 14:00', or an ISO time -> a naive local datetime."""
    t = str(text or "").strip()
    try:
        d = dt.datetime.fromisoformat(t.replace(" ", "T") if re.match(r"\d{4}-\d\d-\d\d \d", t) else t)
        if d.tzinfo:
            d = d.astimezone().replace(tzinfo=None)
        if len(t) > 10 or "T" in t:
            return d.replace(second=0, microsecond=0)
    except ValueError:
        pass
    return parse_when(t, base)


class AgentPlan(GooglePart):
    id = "agent_plan"
    part = "agent_calendar"
    title = "Agent plan calendar"
    description = (
        'Time blocks Kurooto plans with you (morning plan, calls) go into its own "Agent plan" calendar in your '
        "Google Calendar."
    )
    privacy = (
        "Kurooto makes one calendar of its own in your Google Calendar and writes only there (Google's permission for "
        "calendars an app creates); it can't see or change your other calendars."
    )
    permission = (
        "Google will ask you to allow Kurooto to make secondary calendars and manage the events on them. That covers "
        'only calendars Kurooto itself makes ("Agent plan"): it can\'t see or change any other calendar.'
    )
    api_link = (
        "Turn on the Google Calendar API",
        "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
    )

    @property
    def file(self):
        return self.app.paths.state / "agent-plan.json"

    def plan_ready(self) -> bool:
        return self.app.is_on(self.id) and self.ready()[0]

    # -------------------------------------------------------------------------------------- the calendar
    def calendar_id(self, create: bool = True) -> str | None:
        """Kurooto's own calendar (made on first use, again if you deleted it, and on another account if you moved
        it there)."""
        st = jload(self.file, {}) or {}
        if st.get("id") and st.get("account", "main") != self.account:
            st.pop("id")  # it's on the account you used before
        if st.get("id") or not create:
            return st.get("id")
        body = {
            "summary": self.setting("name") or "Agent plan",
            "description": f"Time blocks planned with {self.app.name}. Hide or delete this calendar any time.",
        }
        tzname = self.app.settings.get("you.timezone")
        if tzname:
            body["timeZone"] = tzname
        cal = self.google.api("calendar", "/calendars", body)
        st["id"], st["account"] = cal["id"], self.account
        jsave(self.file, st)
        self.app.events.emit("agent_calendar_made")
        return st["id"]

    def _events_path(self, cid: str) -> str:
        return f"/calendars/{urllib.parse.quote(cid, safe='')}/events"

    def _forget_calendar(self) -> None:
        st = jload(self.file, {}) or {}
        st.pop("id", None)
        jsave(self.file, st)

    def plan_blocks(self, day: dt.date) -> list[dict]:
        """That day's blocks in Kurooto's calendar: [{"title", "start", "end", "id"}] (naive local times)."""
        cid = self.calendar_id(create=False)
        if not cid:
            return []
        a = dt.datetime.combine(day, dt.time(0)).astimezone()  # local time, like the rest of Kurooto
        q = {
            "timeMin": a.isoformat(),
            "timeMax": (a + dt.timedelta(days=1)).isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 100,
        }
        try:
            items = self.google.api("calendar", f"{self._events_path(cid)}?{urllib.parse.urlencode(q)}").get(
                "items", []
            )
        except GoogleError as e:
            if e.code == 404:  # you deleted the calendar
                self._forget_calendar()
                return []
            raise
        out = []
        for e in items:
            s, f = (e.get("start") or {}).get("dateTime"), (e.get("end") or {}).get("dateTime")
            if not s or not f or e.get("status") == "cancelled":
                continue
            out.append(
                {
                    "id": e.get("id"),
                    "title": e.get("summary") or "(no title)",
                    "start": dt.datetime.fromisoformat(s).astimezone().replace(tzinfo=None),
                    "end": dt.datetime.fromisoformat(f).astimezone().replace(tzinfo=None),
                }
            )
        self._remember(day, out)
        return out

    def _remember(self, day: dt.date, blocks: list[dict]) -> None:
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            days = {
                k: v
                for k, v in (st.get("days") or {}).items()
                if k >= (now().date() - dt.timedelta(days=1)).isoformat()
            }
            days[day.isoformat()] = [
                {"title": b["title"], "start": b["start"].isoformat(), "end": b["end"].isoformat()} for b in blocks
            ]
            st["days"] = days
            jsave(self.file, st)

    def plan_block(self, start: dt.datetime, end: dt.datetime, title: str) -> str:
        """Put one time block into Kurooto's own calendar. Never touches another calendar."""
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:200] or "Focus"
        start, end = start.replace(second=0, microsecond=0), end.replace(second=0, microsecond=0)
        if end <= start:
            return "The block has to end after it starts."
        if end - start > dt.timedelta(hours=12):
            return "That's longer than 12 hours; plan it in smaller blocks."
        t = now()
        if end < t or start > t + dt.timedelta(days=31):
            return "Blocks go between now and a month ahead."
        existing = self.plan_blocks(start.date())
        if any(b["title"].lower() == title.lower() and b["start"] == start for b in existing):
            return f"Already planned: {start:%a %H:%M} {title}."
        mins = int(self.setting("remind_min") or 0)
        body = {
            "summary": title,
            "description": f"Planned with {self.app.name}.",
            "start": {"dateTime": start.astimezone().isoformat()},
            "end": {"dateTime": end.astimezone().isoformat()},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": mins}] if mins else []},
            "extendedProperties": {"private": {"kurooto": "1"}},
        }
        cid = self.calendar_id()
        try:
            self.google.api("calendar", self._events_path(cid), body)
        except GoogleError as e:
            if e.code != 404:
                raise
            self._forget_calendar()  # deleted in Google Calendar: make a new one
            self.google.api("calendar", self._events_path(self.calendar_id()), body)
        self._remember(start.date(), [*existing, {"title": title, "start": start, "end": end, "id": ""}])
        self.app.events.emit("plan_block_added", minutes=int((end - start).total_seconds() // 60))
        return f"Planned {start:%a %H:%M}–{end:%H:%M}: {title}."

    def clear_plan(self, day: dt.date) -> int:
        """Remove that day's blocks from Kurooto's own calendar (you asked; nothing else is touched)."""
        cid = self.calendar_id(create=False)
        n = 0
        for b in self.plan_blocks(day) if cid else []:
            try:
                self.google.api(
                    "calendar", f"{self._events_path(cid)}/{urllib.parse.quote(b['id'], safe='')}", method="DELETE"
                )
                n += 1
            except GoogleError as e:
                if e.code not in (404, 410):
                    raise
        self._remember(day, [])
        self.app.events.emit("plan_cleared", blocks=n)
        return n

    # -------------------------------------------------------------------------------------- reschedule
    def _delete(self, cid: str, eid: str) -> None:
        try:
            self.google.api("calendar", f"{self._events_path(cid)}/{urllib.parse.quote(eid, safe='')}", method="DELETE")
        except GoogleError as e:
            if e.code not in (404, 410):
                raise

    def reschedule(self, start: dt.datetime | None = None, by: dt.timedelta | None = None) -> str:
        """Move today's blocks still to do so they start at `start` (default: now, at the next quarter hour), or later
        by `by`. Starting over (no `by`) takes the blocks that are past too (a late start: you slept through them);
        pushing `by` some time moves only what isn't over. See the module's notes."""
        t, missed = now(), by is None
        blocks = sorted(self.plan_blocks(t.date()), key=lambda b: b["start"])
        todo, dupes, seen = [], [], set()
        for b in blocks:
            if b["end"] <= t and not missed:
                continue
            key = b["title"].strip().lower()
            (dupes if key in seen else todo).append(b)
            seen.add(key)
        if not todo:
            return "No blocks planned today to move." if not blocks else "Every block today is done already."
        soon = (t + dt.timedelta(minutes=14)).replace(second=0, microsecond=0)
        soon -= dt.timedelta(minutes=soon.minute % 15)
        if start is None:
            start = todo[0]["start"] + by if by else soon  # pushed: each block that much later
        latest = dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(LATEST_H))
        new, left, cur, prev = [], [], start, None
        for b in todo:
            if prev is not None:
                cur += min(GAP_MAX, max(dt.timedelta(0), b["start"] - prev))
            end = cur + (b["end"] - b["start"])
            if end > latest:
                left.append(b)
            else:
                new.append({"title": b["title"], "start": cur, "end": end})
                cur = end
            prev = b["end"]
        cid = self.calendar_id()
        for b in todo + dupes:
            self._delete(cid, b["id"])
        for b in new:
            self.plan_block(b["start"], b["end"], b["title"])
        old = [
            {"title": b["title"], "start": b["start"].isoformat(), "end": b["end"].isoformat()} for b in todo + dupes
        ]
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st["undo"] = {
                "old": old,
                "new": [{**b, "start": b["start"].isoformat(), "end": b["end"].isoformat()} for b in new],
            }
            jsave(self.file, st)
        lines = [f"{b['start']:%H:%M}–{b['end']:%H:%M}  {b['title']}" for b in new]
        if left:
            lines.append("Didn't fit before " + f"{latest:%H:%M}: " + "; ".join(b["title"] for b in left))
        from kurooto.modules import daily

        try:
            daily.append(self.app, f"Plan rescheduled ({t:%H:%M})", "\n".join(f"- {x}" for x in lines), t.date())
        except OSError:
            pass
        self.app.events.emit("plan_rescheduled", moved=len(new), dropped=len(dupes), left=len(left))
        return "Your day, from now:\n" + "\n".join(lines) + "\n(/blocks undo puts it back.)"

    def undo_reschedule(self) -> str:
        st = jload(self.file, {}) or {}
        u = st.get("undo")
        if not u:
            return "There's no reschedule to undo."
        cid = self.calendar_id()
        days = {dt.datetime.fromisoformat(b["start"]).date() for b in u["new"]}
        for day in days:
            for b in self.plan_blocks(day):
                if any(
                    b["title"] == n["title"] and f"{b['start']:%Y-%m-%dT%H:%M}" == n["start"][:16] for n in u["new"]
                ):
                    self._delete(cid, b["id"])
        back = 0
        for b in u["old"]:
            s, e = dt.datetime.fromisoformat(b["start"]), dt.datetime.fromisoformat(b["end"])
            if e > now():
                self.plan_block(s, e, b["title"])
                back += 1
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st.pop("undo", None)
            jsave(self.file, st)
        self.app.events.emit("plan_reschedule_undone", back=back)
        return f"Put {back} block{'s' if back != 1 else ''} back where they were (the ones already past stay gone)."

    def _shift_args(self, frm: str, by: str) -> tuple[dt.datetime | None, dt.timedelta | None]:
        """("19:00" or "in 2 hours", "2 hours") -> (start, by)."""
        frm, by = (frm or "").strip(), (by or "").strip()
        if by:
            m = re.fullmatch(r"(?i)(?:an?|one|(\d+(?:\.\d+)?)) ?(hours?|hrs?|h|minutes?|mins?|m)", by)
            if not m:
                raise ValueError(f"I couldn't read {by!r}")
            n = float(m.group(1) or 1)
            return None, dt.timedelta(hours=n) if m.group(2).lower().startswith("h") else dt.timedelta(minutes=n)
        if frm and not re.fullmatch(r"(?i)now|today", frm):
            return when(frm, base=now()), None
        return None, None

    def _tool_reschedule(self, a: dict) -> str:
        if not self.ready()[0]:
            return f"The Agent plan calendar isn't ready: {self.ready()[1]}."
        try:
            start, by = self._shift_args(str(a.get("start") or ""), str(a.get("by") or ""))
            return self.reschedule(start, by)
        except ValueError as err:
            return f"I couldn't read that time: {err}"
        except (NeedsSignIn, GoogleError) as err:
            return f"Google Calendar didn't take it: {err}"[:300]

    # -------------------------------------------------------------------------------------------- tools
    def _tool_block(self, a: dict) -> str:
        if not self.ready()[0]:
            return f"The Agent plan calendar isn't ready: {self.ready()[1]}."
        try:
            s = when(a.get("start", ""))
            e = when(a.get("end", ""), base=s)
        except ValueError as err:
            return f"I couldn't read that time: {err}"
        try:
            return self.plan_block(s, e, str(a.get("title") or ""))
        except (NeedsSignIn, GoogleError) as err:
            return f"Google Calendar didn't take it: {err}"[:300]

    def call_tools(self):
        return [
            Tool(
                "plan_block",
                'Put a time block (study, a task, a break) into Kurooto\'s own "Agent plan" calendar in their Google '
                'Calendar. start and end like "2026-10-20 14:00", "14:00" or "tomorrow 9am"; end may be "15:30".',
                self._tool_block,
                {"start": arg(), "end": arg(), "title": arg("what the block is for")},
                ("start", "end", "title"),
                offline="queue",
                hint="plan_block when they agree to a time for something (a study block, a task) today or later.",
            ),
            Tool(
                "reschedule_day",
                "Move today's blocks still to do (and ones they slept through) to start later, keeping their order, "
                'lengths and the breaks between them; drops a block planned twice. start: "19:00", "in 2 hours" or '
                'empty for now; or by: "2 hours" to push everything that much later.',
                self._tool_reschedule,
                {"start": arg(), "by": arg()},
                (),
                offline="queue",
                hint='When they want the day rescheduled or pushed ("I just woke up", "push my day"), call '
                "reschedule_day once instead of plan_block for each block.",
            ),
        ]

    def intents(self):
        def match(text: str):
            m = SHIFT.match(text.strip())
            return {"from": m.group("from") or "", "by": m.group("by") or ""} if m else None

        def run(msg, sl):
            return self._tool_reschedule({"start": sl["from"], "by": sl["by"]})

        return [Intent("reschedule_day", "reschedule my day, push my day by 2 hours, replan from 19:00", match, run)]

    def call_brief(self) -> dict:
        day = (jload(self.file, {}) or {}).get("days", {}).get(now().date().isoformat()) or []
        return {"plan_today": [f"{b['start'][11:16]}–{b['end'][11:16]} {b['title']}" for b in day]} if day else {}

    # ----------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "blocks",
                "your Agent plan blocks today (/blocks add 14:00-15:30 what, /blocks shift [19:00 | by 2 hours] "
                "reschedules the day, /blocks undo, /blocks clear)",
                self._cmd,
                usage="/blocks [add <from>-<to> <what> | shift [<time> | by <hours>] | undo | clear]",
            )
        ]

    def _cmd(self, msg: Incoming, arg_text: str) -> str:
        if not self.ready()[0]:
            return f"Not yet: {self.ready()[1]}."
        word, _, rest = arg_text.strip().partition(" ")
        try:
            if word.lower() == "add":
                m = TIME.match(rest.strip())
                if not m:
                    return "Usage: /blocks add 14:00-15:30 problem set 4"
                return self._tool_block({"start": m[1], "end": m[2], "title": m[3]})
            if word.lower() in ("shift", "reschedule", "move", "push"):
                frm, _, by = rest.strip().partition("by ")
                start, delta = self._shift_args(frm.strip(), by.strip())
                return self.reschedule(start, delta)
            if word.lower() == "undo":
                return self.undo_reschedule()
            if word.lower() == "clear":
                n = self.clear_plan(now().date())
                return f"Removed {n} block(s) from today's Agent plan." if n else "No blocks today."
            blocks = self.plan_blocks(now().date())
        except ValueError as e:
            return f"I couldn't read that time: {e}"
        except (NeedsSignIn, GoogleError) as e:
            return f"Google Calendar: {e}"[:300]
        if not blocks:
            return "No blocks planned today."
        return "Today's plan:\n" + "\n".join(f"{b['start']:%H:%M}–{b['end']:%H:%M}  {b['title']}" for b in blocks)
