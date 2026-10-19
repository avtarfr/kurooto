"""Calendar: your calendar's events in Kurooto, from its private iCal link (Google Calendar: Settings → your calendar →
"Secret address in iCal format"; Outlook and Apple Calendar have one too). Read-only; nothing is ever changed there.

What you get: /today and /week, "what's on tomorrow?", today's events in calls and check-ins, no calls during an
event (on by default), and optionally a reminder a few minutes before each event. Refreshed every 15 minutes.
The link is kept in your keychain: anyone with it can read that calendar, so don't share it.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module

register_defaults("calendar", {"refresh": "every 15m", "no_calls_in_events": True, "remind_min": 0, "days": 14})
SECRET = "calendar.ics"  # noqa: S105 (the secret's name): a JSON list of iCal links


# --------------------------------------------------------------------------------------------- iCal
def unfold(text: str) -> list[str]:
    out: list[str] = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ln[:1] in (" ", "\t") and out:
            out[-1] += ln[1:]
        elif ln:
            out.append(ln)
    return out


def unescape(v: str) -> str:
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m[1] in "nN" else m[1], v)


def parse_dt(value: str, params: dict, local: dt.tzinfo) -> tuple[dt.datetime, bool]:
    """(an aware datetime, all-day?)"""
    v = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", v):
        d = dt.datetime.strptime(v[:8], "%Y%m%d")
        return d.replace(tzinfo=local), True
    base = dt.datetime.strptime(v.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if v.endswith("Z"):
        return base.replace(tzinfo=dt.UTC), False
    tz = local
    if params.get("TZID"):
        try:
            tz = ZoneInfo(params["TZID"].strip('"'))
        except (ZoneInfoNotFoundError, ValueError):
            tz = local  # e.g. Outlook's Windows zone names: assume your own
    return base.replace(tzinfo=tz), False


def parse_ics(text: str, local: dt.tzinfo) -> list[dict]:
    """VEVENTs as dicts: uid, title, location, start, end (aware), all_day, rrule, exdates, recurrence_id, cancelled."""
    events, cur, depth = [], None, 0
    for ln in unfold(text):
        if ln == "BEGIN:VEVENT":
            cur, depth = {"exdates": []}, 0
            continue
        if cur is None:
            continue
        if ln.startswith("BEGIN:"):  # VALARM inside an event
            depth += 1
            continue
        if ln.startswith("END:") and depth:
            depth -= 1
            continue
        if ln == "END:VEVENT":
            if "start" in cur:
                cur.setdefault(
                    "end", cur["start"] + (dt.timedelta(days=1) if cur.get("all_day") else dt.timedelta(hours=1))
                )
                events.append(cur)
            cur = None
            continue
        if depth:
            continue
        head, _, value = ln.partition(":")
        name, *ps = head.split(";")
        params = dict(p.split("=", 1) for p in ps if "=" in p)
        name = name.upper()
        try:
            if name == "UID":
                cur["uid"] = value
            elif name == "SUMMARY":
                cur["title"] = unescape(value)[:200]
            elif name == "LOCATION":
                cur["location"] = unescape(value)[:200]
            elif name == "STATUS":
                cur["cancelled"] = value.upper() == "CANCELLED"
            elif name == "DTSTART":
                cur["start"], cur["all_day"] = parse_dt(value, params, local)
            elif name == "DTEND":
                cur["end"], _ = parse_dt(value, params, local)
            elif name == "DURATION":
                m = re.fullmatch(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value)
                if m and "start" in cur:
                    w, d, h, mi, s = (int(x or 0) for x in m.groups())
                    cur["end"] = cur["start"] + dt.timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)
            elif name == "RRULE":
                cur["rrule"] = value
            elif name == "EXDATE":
                cur["exdates"] += [parse_dt(x, params, local)[0] for x in value.split(",") if x.strip()]
            elif name == "RECURRENCE-ID":
                cur["recurrence_id"], _ = parse_dt(value, params, local)
        except ValueError:
            continue
    return events


def fix_until(rule: str) -> str:
    """dateutil wants UNTIL in UTC when the start has a time zone; calendars also write plain dates and local times."""

    def utc(m):
        v = m.group(1)
        if v.endswith("Z"):
            return m.group(0)
        if len(v) == 8:
            return f"UNTIL={v}T235959Z"
        return f"UNTIL={v}Z"

    return re.sub(r"UNTIL=([0-9TZ]+)", utc, rule)


def local_zone(name: str | None) -> dt.tzinfo:
    try:
        return ZoneInfo(name) if name else dt.datetime.now().astimezone().tzinfo
    except (ZoneInfoNotFoundError, ValueError):
        return dt.datetime.now().astimezone().tzinfo


def expand(events: list[dict], start: dt.datetime, end: dt.datetime) -> list[dict]:
    """Every occurrence between start and end, with moved or cancelled ones applied."""
    overrides = {(e.get("uid"), e["recurrence_id"]): e for e in events if e.get("recurrence_id")}
    out = []
    for e in events:
        if e.get("recurrence_id"):
            continue
        length = e["end"] - e["start"]
        if e.get("rrule"):
            try:
                rule = rrulestr(fix_until(e["rrule"]), dtstart=e["start"], forceset=True)
            except (ValueError, TypeError):
                continue
            for x in e["exdates"]:
                rule.exdate(x)
            starts = rule.between(start - length, end, inc=True)
        else:
            starts = [e["start"]]
        for s in starts:
            occ = overrides.get((e.get("uid"), s)) or {**e, "start": s, "end": s + length}
            if occ.get("cancelled") or not (occ["start"] < end and occ["end"] > start):
                continue
            out.append(occ)
    for o in overrides.values():  # a moved occurrence whose original falls outside the window
        if not o.get("cancelled") and o["start"] < end and o["end"] > start and o not in out:
            out.append(o)
    return sorted(out, key=lambda e: e["start"])


# ------------------------------------------------------------------------------------------- feature
class Calendar(Module):
    id = "calendar"
    title = "Calendar"
    description = "Your calendar's events (from its private iCal link): /today, no calls during events, reminders."
    privacy = "Kurooto reads your calendar's private iCal link from Google (or wherever it lives); nothing is changed."

    @property
    def file(self):
        return self.app.paths.state / "calendar.json"

    def tz(self) -> dt.tzinfo:
        return local_zone(self.app.settings.get("you.timezone"))

    def now(self) -> dt.datetime:
        return dt.datetime.now(self.tz()).replace(microsecond=0)

    def links(self) -> list[str]:
        try:
            return json.loads(self.app.secrets.get(SECRET) or "[]")
        except ValueError:
            return []

    def ready(self):
        return (True, "") if self.links() else (False, "paste your calendar's private iCal link (see the help)")

    def add_link(self, url: str) -> tuple[bool, str]:
        url = url.strip().replace("webcal://", "https://", 1)
        if not url.startswith(("https://", "http://127.0.0.1")):
            return False, "That isn't an https:// iCal link."
        try:
            n = len(self._fetch(url))
        except Exception as e:
            return False, f"Couldn't read that link: {e}"[:200]
        links = [x for x in self.links() if x != url] + [url]
        self.app.secrets.set(SECRET, json.dumps(links))
        self.refresh()
        return True, f"Added: {n} events found."

    def _fetch(self, url: str) -> list[dict]:
        req = urllib.request.Request(url, headers={"User-Agent": "kurooto"})  # noqa: S310 (your calendar's link)
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            text = r.read(20 * 1024 * 1024).decode("utf-8", "replace")
        if "BEGIN:VCALENDAR" not in text:
            raise ValueError("not an iCal calendar")
        return parse_ics(text, self.tz())

    def refresh(self, p: dict | None = None) -> int:
        start = self.now() - dt.timedelta(days=1)
        end = self.now() + dt.timedelta(days=self.setting("days") or 14)
        found, failed = [], 0
        for url in self.links():
            try:
                found += expand(self._fetch(url), start, end)
            except Exception as e:
                failed += 1
                self.app.events.emit("calendar_failed", error=str(e)[:200])
        if failed and not found:
            return 0  # keep the last good copy
        rows = [
            {
                "title": e.get("title") or "(no title)",
                "start": e["start"].isoformat(),
                "end": e["end"].isoformat(),
                "all_day": bool(e.get("all_day")),
                "location": e.get("location", ""),
            }
            for e in found
        ]
        with Lock(self.app.paths.state, "calendar"):
            jsave(self.file, {"events": rows, "at": self.now().isoformat()})
        self._plan_reminders(rows)
        self.app.events.emit("calendar_synced", events=len(rows))
        return len(rows)

    def events(self, start: dt.datetime, end: dt.datetime) -> list[dict]:
        out, tz = [], self.tz()
        for e in (jload(self.file, {}) or {}).get("events", []):
            s = dt.datetime.fromisoformat(e["start"]).astimezone(tz)
            f = dt.datetime.fromisoformat(e["end"]).astimezone(tz)
            if s < end and f > start:
                out.append({**e, "start_dt": s, "end_dt": f})
        return out

    def day(self, d: dt.date) -> list[dict]:
        a = dt.datetime.combine(d, dt.time(0), self.tz())
        return self.events(a, a + dt.timedelta(days=1))

    # ------------------------------------------------------------------------------- availability
    def start(self):
        self.every("refresh", self.setting("refresh") or "every 15m", self.refresh)
        self.action("remind", self._remind)
        self.app.availability.blockers["calendar:event"] = self._block
        if not self.file.exists():
            self.refresh()

    def stop(self):
        super().stop()
        self.app.availability.blockers.pop("calendar:event", None)

    def _block(self, t: dt.datetime):
        if not self.setting("no_calls_in_events"):
            return None
        t = t if t.tzinfo else t.astimezone()
        for e in self.events(t, t + dt.timedelta(seconds=1)):
            if not e["all_day"]:  # naive local time, like the rest of availability
                return f"in {e['title']}", e["end_dt"].astimezone().replace(tzinfo=None)
        return None

    def _plan_reminders(self, rows: list[dict]) -> None:
        mins = self.setting("remind_min") or 0
        self.app.scheduler.cancel_prefix("calendar:remind:")
        if not mins:
            return
        for e in rows:
            if e["all_day"]:
                continue
            at = dt.datetime.fromisoformat(e["start"]) - dt.timedelta(minutes=mins)
            if at > self.now():
                key = f"calendar:remind:{e['start']}:{abs(hash(e['title'])) % 10**8}"
                self.app.scheduler.at(
                    at,
                    "calendar.remind",
                    {"title": e["title"], "start": e["start"], "location": e["location"]},
                    key=key,
                    module=self.id,
                    grace_s=600,
                )

    def _remind(self, p: dict) -> None:
        if p.get("missed"):
            return
        s = dt.datetime.fromisoformat(p["start"]).astimezone(self.tz())
        where = f" ({p['location']})" if p.get("location") else ""
        self.app.notify(f"{p['title']} at {s:%H:%M}{where}.", kind="reminder")

    # -------------------------------------------------------------------------------- telling you
    @staticmethod
    def line(e: dict) -> str:
        if e["all_day"]:
            return f"all day  {e['title']}"
        loc = f" ({e['location']})" if e.get("location") else ""
        return f"{e['start_dt']:%H:%M}–{e['end_dt']:%H:%M}  {e['title']}{loc}"

    def agenda(self, d: dt.date) -> str:
        evs, today = self.day(d), self.now().date()
        label = "Today" if d == today else "Tomorrow" if d == today + dt.timedelta(days=1) else f"{d:%a %d %b}"
        return f"{label}:\n" + "\n".join(self.line(e) for e in evs) if evs else f"{label}: nothing in your calendar."

    def commands(self):
        return [
            Command("today", "today's calendar", lambda m, a: self.agenda(self.now().date())),
            Command("cal", "the next 7 days of your calendar", self._week),
        ]

    def _week(self, msg: Incoming, arg: str) -> str:
        days = [self.now().date() + dt.timedelta(days=i) for i in range(7)]
        return "\n\n".join(self.agenda(d) for d in days if self.day(d)) or "Nothing in the next 7 days."

    def intents(self):
        pat = re.compile(
            r"\b(?:what'?s|what is|anything|whats)\b.*\b(on|planned|happening|in my calendar|scheduled)\b.*"
            r"\b(today|tomorrow)\b|\b(today|tomorrow)'?s? (?:schedule|plan|calendar|agenda)\b",
            re.I,
        )

        def match(text: str):
            m = pat.search(text)
            if not m:
                return None
            return {"tomorrow": "tomorrow" in text.lower()}

        return [
            Intent(
                "calendar_day",
                "what's on today/tomorrow",
                match,
                lambda msg, s: self.agenda(self.now().date() + dt.timedelta(days=1 if s["tomorrow"] else 0)),
                questions=True,
            )
        ]

    def call_brief(self) -> dict:
        evs = self.day(self.now().date())
        return {"calendar_today": [self.line(e) for e in evs]} if evs else {}

    # ------------------------------------------------------------------------------------- setup
    def setup_form(self) -> dict:
        return {
            "intro": "Paste your calendar's private iCal link. Google Calendar (on a computer): Settings → your "
            "calendar on the left → Integrate calendar → Secret address in iCal format → copy. Add more calendars "
            "the same way.",
            "links": [["Google Calendar settings", "https://calendar.google.com/calendar/r/settings"]],
            "fields": [
                {"name": "link", "label": "Private iCal link", "type": "password", "placeholder": "https://…/basic.ics"}
            ],
        }

    def configure(self, values: dict) -> dict:
        ok, msg = self.add_link(str(values.get("link", "")))
        return {"ok": ok, "message": msg}
