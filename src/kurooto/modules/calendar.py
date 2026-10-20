"""Calendar: your calendar's events in Kurooto, from its private iCal link (Google Calendar: Settings → your calendar →
"Secret address in iCal format"; Outlook and Apple Calendar have one too). Read-only; nothing is ever changed there.

What you get: /today and /week, "what's on tomorrow?", today's events in calls and check-ins, no calls during an
event (on by default; or only during events with #nocall in the title or description, or in a calendar whose name
contains "no call"), focus time during events with #focus (calls held, messages wait until it ends), and optionally a
reminder a few minutes before each event. Refreshed every 15 minutes.
The link is kept in your keychain: anyone with it can read that calendar, so don't share it.

Google calendars can also come through Google's Calendar API instead (the Google Calendar feature: no iCal link, and
several accounts at once).

Events marked private (Google's "Private" visibility, CLASS:PRIVATE in iCal, or #private in the title or description)
show as "Busy (private)" wherever Kurooto shows or tells them: /today, the dashboard, calls, reminders, the AI. Their
title, place and description aren't kept (calendar.mask_private).

Class calendars (calendar.class_calendars, or /cal classes Timetable): events in calendars with those names count as
classes: no calls during them, they're in your day's classes, and one whose title names a subject gets the
after-class question.
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

register_defaults(
    "calendar",
    {
        "refresh": "every 15m",
        "no_calls_in_events": True,
        "nocall_events": "all",  # "all": every timed event holds calls; "tagged": #nocall ones, "no call" calendars
        "remind_min": 0,
        "days": 14,
        "mask_private": True,  # private events: "Busy (private)", nothing else kept
        "private_keyword": "#private",  # in a title or description: private too
        "class_calendars": [],  # names (any part, any case) of calendars whose events are classes, e.g. ["Timetable"]
    },
)
BUSY = "Busy (private)"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
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
    """VEVENTs as dicts: uid, title, location, description, calendar (its name), start, end (aware), all_day, rrule,
    exdates, recurrence_id, cancelled."""
    events, cur, depth, calname = [], None, 0, ""
    for ln in unfold(text):
        if ln == "BEGIN:VEVENT":
            cur, depth = {"exdates": [], "calendar": calname}, 0
            continue
        if cur is None:
            if ln.upper().startswith("X-WR-CALNAME"):
                calname = unescape(ln.partition(":")[2])[:200]
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
            elif name == "DESCRIPTION":
                cur["description"] = unescape(value)[:2000]
            elif name == "STATUS":
                cur["cancelled"] = value.upper() == "CANCELLED"
            elif name == "CLASS":
                cur["private"] = value.strip().upper() in ("PRIVATE", "CONFIDENTIAL")
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
    description = (
        "Your calendar's events (from its private iCal link, or Google Calendar): /today, no calls during events, "
        "reminders, class calendars."
    )
    privacy = (
        "Kurooto reads your calendar (its private iCal link, or Google Calendar); nothing is changed. Events marked "
        "private show only as Busy (private)."
    )

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

    def google_source(self):
        """The Google Calendar feature, when it's on and signed in; else None."""
        gc = self.app.modules.get("google_calendar")
        return gc if gc is not None and self.app.is_on("google_calendar") and gc.ready()[0] else None

    def ready(self):
        if self.links() or self.google_source():
            return True, ""
        return False, "paste your calendar's private iCal link (see the help), or set up Google Calendar"

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
        found, failed, names = [], 0, []
        for url in self.links():
            try:
                evs = self._fetch(url)
                names += [e["calendar"] for e in evs[:1] if e.get("calendar")]
                found += expand(evs, start, end)
            except Exception as e:
                failed += 1
                self.app.events.emit("calendar_failed", error=str(e)[:200])
        gc = self.google_source()
        if gc is not None:
            evs, cals, bad = gc.fetch(start, end, self.tz())
            found += [e for e in evs if e["start"] < end and e["end"] > start]
            names += cals
            failed += bad
        elif self.app.is_on("google_calendar"):
            failed += 1  # on, but its sign-in is missing: keep what was read last
        if failed and not found:
            return 0  # keep the last good copy
        rows = sorted((self._row(e) for e in found), key=lambda r: r["start"])
        with Lock(self.app.paths.state, "calendar"):
            jsave(
                self.file,
                {"events": rows, "at": self.now().isoformat(), "calendars": list(dict.fromkeys(names))[:50]},
            )
        self._plan_reminders(rows)
        self._plan_focus_ends(rows)
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
        self.action("focus_end", self._focus_end)
        self.app.availability.blockers["calendar:event"] = self._block
        self.app.availability.blockers["focus:calendar"] = self._focus
        if not self.file.exists():
            self.refresh()

    def stop(self):
        super().stop()
        self.app.availability.blockers.pop("calendar:event", None)
        self.app.availability.blockers.pop("focus:calendar", None)

    def _row(self, e: dict) -> dict:
        """What's kept of an event. A private one keeps only its time and flags: "Busy (private)"."""
        tags = self._tags(e)
        hide = tags.get("private") and self.setting("mask_private")
        return {
            "title": BUSY if hide else e.get("title") or "(no title)",
            "start": e["start"].isoformat(),
            "end": e["end"].isoformat(),
            "all_day": bool(e.get("all_day")),
            "location": "" if hide else e.get("location", ""),
            **tags,
        }

    def _tags(self, e: dict) -> dict:
        """What an event's title, description and calendar say: {"nocall", "focus", "private", "class": True}. Only
        these flags are kept, never the description."""
        av = self.app.settings.get("availability") or {}
        text = f"{e.get('title', '')} {e.get('description', '')}".lower()
        kw, fk = (av.get("nocall_keyword") or "").lower(), (av.get("focus_keyword") or "").lower()
        cal = (av.get("nocall_calendar") or "").lower()
        calname = str(e.get("calendar", "")).lower()
        pk = str(self.setting("private_keyword") or "").lower()
        out = {}
        if (kw and kw in text) or (cal and cal in calname):
            out["nocall"] = True
        if fk and fk in text:
            out["focus"] = True
        if e.get("private") or (pk and pk in text):
            out["private"] = True
        if calname and any(c and c in calname for c in self.class_calendars()):
            out["class"] = True
        return out

    def class_calendars(self) -> list[str]:
        return [str(c).strip().lower() for c in self.setting("class_calendars") or [] if str(c).strip()]

    def classes(self, day: dt.date) -> list[dict]:
        """A day's events from your class calendars, shaped like timetable classes (Subjects counts them as
        classes). One whose title names a subject is that subject's class; else its subject is ""."""
        if not self.class_calendars():
            return []
        subj = self.app.modules.get("subjects")
        out = []
        for e in self.day(day):
            if not e.get("class") or e["all_day"]:
                continue
            s, f = (x.astimezone().replace(tzinfo=None) for x in (e["start_dt"], e["end_dt"]))
            slug = ""
            if subj is not None and not e.get("private"):
                slug = subj.resolve(e["title"]) or next(iter(subj.find_in(e["title"])), "")
            out.append(
                {
                    "day": DAYS[s.weekday()],
                    "start": f"{s:%H:%M}",
                    "end": f"{f:%H:%M}",
                    "subject": slug,
                    "name": subj.name_of(slug) if slug else e["title"],
                    "start_dt": s,
                    "end_dt": f,
                    "source": "calendar",
                }
            )
        return out

    def _block(self, t: dt.datetime):
        if not self.setting("no_calls_in_events"):
            return None
        tagged_only = self.setting("nocall_events") == "tagged"
        t = t if t.tzinfo else t.astimezone()
        for e in self.events(t, t + dt.timedelta(seconds=1)):
            until = e["end_dt"].astimezone().replace(tzinfo=None)  # naive local time, like the rest of availability
            if e.get("nocall"):  # all-day ones too: "Exam day #nocall"
                return f"no-call event: {e['title']}", until
            if e.get("class") and not e["all_day"]:
                if self.app.is_on("subjects"):
                    continue  # a class: Subjects holds calls then (with its margin, and knows what you skip)
                return f"class: {e['title']}", until
            if not tagged_only and not e["all_day"]:
                return f"in {e['title']}", until
        return None

    def _focus(self, t: dt.datetime):
        """A #focus event is focus time while it runs (the "focus:" blocker: calls held, messages wait)."""
        t = t if t.tzinfo else t.astimezone()
        ends = [e["end_dt"] for e in self.events(t, t + dt.timedelta(seconds=1)) if e.get("focus")]
        return ("focus", max(ends).astimezone().replace(tzinfo=None)) if ends else None

    def _plan_focus_ends(self, rows: list[dict]) -> None:
        """When a #focus event ends, what waited for you is delivered (unless focus goes on)."""
        self.app.scheduler.cancel_prefix("calendar:focus:")
        for e in rows:
            end = dt.datetime.fromisoformat(e["end"])
            if e.get("focus") and end > self.now():
                self.app.scheduler.at(
                    end + dt.timedelta(seconds=30),
                    "calendar.focus_end",
                    key=f"calendar:focus:{e['end']}",
                    module=self.id,
                    grace_s=12 * 3600,
                )

    def _focus_end(self, p: dict) -> None:
        if not self.app.availability.focus_until():
            n = self.app.notifier.flush_queue()
            if n:
                self.app.events.emit("focus_ended", via="calendar", delivered=n)

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
            Command(
                "cal",
                "the next 7 days of your calendar; /cal classes Timetable: events in that calendar are classes",
                self._week,
                usage="/cal [classes <calendar names, comma-separated> | classes none]",
            ),
        ]

    def _classes_cmd(self, arg: str) -> str:
        names = (jload(self.file, {}) or {}).get("calendars") or []
        known = f"\nYour calendars: {', '.join(names)}." if names else ""
        if not arg:
            now_ = ", ".join(self.setting("class_calendars") or []) or "none"
            return f"Class calendars: {now_}. Set them: /cal classes Timetable, Seminars (or /cal classes none).{known}"
        chosen = [] if arg.lower() in ("none", "off", "-") else [x.strip() for x in arg.split(",") if x.strip()][:10]
        self.app.settings.set("calendar.class_calendars", chosen)
        self.app.events.emit("class_calendars_set", n=len(chosen))
        self.refresh()
        if not chosen:
            return "No calendar counts as classes now."
        return f"Events in {', '.join(chosen)} count as classes now (no calls then; in your day's classes).{known}"

    def _week(self, msg: Incoming, arg: str) -> str:
        word, _, rest = arg.strip().partition(" ")
        if word.lower() == "classes":
            return self._classes_cmd(rest.strip())
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
            "the same way. No such link (some school accounts), or two Google accounts? Set up the Google Calendar "
            "feature instead: it reads them through Google and turns this on.",
            "links": [["Google Calendar settings", "https://calendar.google.com/calendar/r/settings"]],
            "fields": [
                {"name": "link", "label": "Private iCal link", "type": "password", "placeholder": "https://…/basic.ics"}
            ],
        }

    def configure(self, values: dict) -> dict:
        ok, msg = self.add_link(str(values.get("link", "")))
        return {"ok": ok, "message": msg}
