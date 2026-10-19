"""Agent plan: a calendar of its own, "Agent plan", that Kurooto makes in your Google Calendar for the time blocks it
plans with you (the morning plan, "block 2 to 4 for the problem set" on a call). Kurooto writes only to that calendar:
Google's permission for it ("calendars this app creates") doesn't let it see or change any other calendar. Hide or
delete the calendar in Google Calendar any time; Kurooto makes a new one the next time it plans something.

    /blocks                          today's blocks
    /blocks add 14:00-15:30 problem set 4
    /blocks clear                    remove today's blocks (only Kurooto's own)
"""

from __future__ import annotations

import datetime as dt
import re
import urllib.parse

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.google import GoogleError, GooglePart, NeedsSignIn

register_defaults("agent_plan", {"name": "Agent plan", "remind_min": 5})
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
        """Kurooto's own calendar (made on first use, and again if you deleted it)."""
        st = jload(self.file, {}) or {}
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
        st["id"] = cal["id"]
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
            )
        ]

    def call_brief(self) -> dict:
        day = (jload(self.file, {}) or {}).get("days", {}).get(now().date().isoformat()) or []
        return {"plan_today": [f"{b['start'][11:16]}–{b['end'][11:16]} {b['title']}" for b in day]} if day else {}

    # ----------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "blocks",
                "your Agent plan blocks today (/blocks add 14:00-15:30 what, /blocks clear)",
                self._cmd,
                usage="/blocks [add <from>-<to> <what> | clear]",
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
            if word.lower() == "clear":
                n = self.clear_plan(now().date())
                return f"Removed {n} block(s) from today's Agent plan." if n else "No blocks today."
            blocks = self.plan_blocks(now().date())
        except (NeedsSignIn, GoogleError) as e:
            return f"Google Calendar: {e}"[:300]
        if not blocks:
            return "No blocks planned today."
        return "Today's plan:\n" + "\n".join(f"{b['start']:%H:%M}–{b['end']:%H:%M}  {b['title']}" for b in blocks)
