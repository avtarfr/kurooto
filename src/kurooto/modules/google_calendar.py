"""Google Calendar: the Calendar feature reads your Google calendars through Google's Calendar API instead of (or as
well as) private iCal links. Useful when a school or work account has no "secret address in iCal format", and for
reading two accounts at once (say main and school). Read-only: nothing is ever changed in your calendars.

It reads your own calendars and the ones you subscribed to (a class calendar, holidays); calendars other people share
with you (a classmate's or a teacher's own calendar) are their data and are left out. Kurooto's own Agent plan
calendar is left out too (/blocks shows it). Events marked private come through as "Busy (private)" (Calendar).
Leave a calendar out by name: google_calendar.skip = ["Birthdays"].
"""

from __future__ import annotations

import datetime as dt
import urllib.parse

from kurooto.core.config import register_defaults
from kurooto.core.state import jload
from kurooto.modules.google import GoogleError, GooglePart

register_defaults("google_calendar", {"skip": []})  # calendar names (any part of them, any case) to leave out


def theirs(cal: dict) -> bool:
    """Someone else's calendar shared with you (its id is that person's address), not one of yours or one you
    subscribed to (group calendars, holidays)."""
    cid = str(cal.get("id", ""))
    if cal.get("primary") or cal.get("accessRole") == "owner":
        return False
    return "@" in cid and not cid.endswith("calendar.google.com")


def as_event(e: dict, calendar: str, tz: dt.tzinfo) -> dict | None:
    """A Calendar API event in the shape the iCal reader gives (title, location, description, calendar, start, end,
    all_day, private); None for a cancelled one."""
    if e.get("status") == "cancelled":
        return None
    s, f = e.get("start") or {}, e.get("end") or {}
    try:
        if s.get("date"):
            start = dt.datetime.fromisoformat(s["date"]).replace(tzinfo=tz)
            end = dt.datetime.fromisoformat(f.get("date") or s["date"]).replace(tzinfo=tz)
            end = max(end, start + dt.timedelta(days=1))
            all_day = True
        else:
            start = dt.datetime.fromisoformat(s["dateTime"])
            end = dt.datetime.fromisoformat(f.get("dateTime") or s["dateTime"])
            start = start if start.tzinfo else start.replace(tzinfo=tz)
            end = end if end.tzinfo else end.replace(tzinfo=tz)
            all_day = False
    except (KeyError, ValueError, TypeError):
        return None
    return {
        "uid": e.get("id", ""),
        "title": str(e.get("summary") or "(no title)")[:200],
        "location": str(e.get("location") or "")[:200],
        "description": str(e.get("description") or "")[:2000],
        "calendar": calendar,
        "start": start,
        "end": end,
        "all_day": all_day,
        "private": e.get("visibility") in ("private", "confidential"),
    }


class GoogleCalendar(GooglePart):
    id = "google_calendar"
    part = "calendar_read"
    title = "Google Calendar"
    description = (
        "Calendar reads your Google calendars through Google's API (no iCal link needed), from one account or several."
    )
    privacy = (
        "Reads your own Google calendars, the next two weeks (read-only: nothing is changed). Calendars other people "
        "share with you are left out; events marked private show only as Busy (private)."
    )
    permission = (
        "Google will ask you to allow Kurooto to see your calendars (read-only: it can't change anything). Kurooto "
        "reads only your own calendars and the ones you subscribed to; calendars other people share with you are left "
        "out, and events marked private come through only as Busy (private)."
    )
    api_link = (
        "Turn on the Google Calendar API",
        "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
    )
    with_modules = ("calendar",)

    def start(self):
        if self.app.is_on("calendar"):  # Calendar was on already (iCal links): read Google's calendars soon
            self.app.scheduler.at(
                dt.datetime.now() + dt.timedelta(seconds=5),
                "calendar.refresh",
                key=f"{self.id}:refresh",
                module=self.id,
                grace_s=3600,
            )

    def fetch(self, start: dt.datetime, end: dt.datetime, tz: dt.tzinfo) -> tuple[list[dict], list[str], int]:
        """(events between start and end from every account it reads, the calendars' names, accounts that failed)."""
        g = self.app.modules["google"]
        skip = [str(x).lower() for x in self.setting("skip") or [] if str(x).strip()]
        own = (jload(self.app.paths.state / "agent-plan.json", {}) or {}).get("id")
        events, names, failed = [], [], 0
        for name in g.accounts_for(self.part):
            acct = g.as_account(name)
            try:
                cals = list(acct.pages("calendar", "/users/me/calendarList", "items", {"maxResults": 250}, limit=4))
                for cal in cals:
                    cname = str(cal.get("summaryOverride") or cal.get("summary") or "")[:200]
                    if cal.get("hidden") or cal.get("deleted") or theirs(cal) or cal.get("id") == own:
                        continue
                    if any(s in cname.lower() for s in skip):
                        continue
                    names.append(cname)
                    q = {
                        "timeMin": start.isoformat(),
                        "timeMax": end.isoformat(),
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 250,
                    }
                    path = f"/calendars/{urllib.parse.quote(str(cal['id']), safe='')}/events"
                    try:
                        found = list(acct.pages("calendar", path, "items", q, limit=8))
                    except GoogleError as e:  # one calendar Google won't list: the others still come
                        self.app.events.emit("calendar_failed", error=str(e)[:200], source="google")
                        continue
                    events += [ev for ev in (as_event(e, cname, tz) for e in found) if ev]
            except Exception as e:
                failed += 1
                self.app.events.emit("calendar_failed", error=str(e)[:200], source="google")
        return events, list(dict.fromkeys(names)), failed
