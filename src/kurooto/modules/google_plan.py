"""Agent plan: a calendar of its own, "Agent plan", that Kurooto makes in your Google Calendar for the time blocks it
plans with you (the morning plan, "block 2 to 4 for the problem set" on a call). Kurooto writes only to that calendar:
Google's permission for it ("calendars this app creates") doesn't let it see or change any other calendar. Hide or
delete the calendar in Google Calendar any time; Kurooto makes a new one the next time it plans something.
With several Google accounts, it lives on the one you choose on its card (or /google use plan personal).

    /blocks                          today's blocks
    /blocks add 14:00-15:30 problem set 4
    /blocks clear                    remove today's blocks (only Kurooto's own)
    /blocks shift [19:00 | in 2 hours]   reschedule the day: today's blocks still to do, from then (default now)
    /blocks remove <what> | after 22:00   take blocks out (a title or subject, all, or from a time on)
    /blocks undo                     put the blocks back where they were before the last reschedule or removal

Each block is tied to the deadline, quiz or exam it's for (the one its title names, from Deadlines), and to its due
date then. A block for something done, dropped or over (a quiz this morning) isn't planned.

Rescheduling the day ("reschedule my day", "push my day by 2 hours", "I just woke up, reschedule my day from 7", or
on a call): the blocks you haven't done (still to come, and with a late start the ones you slept through) move to
start then, each as long as it was, the breaks between them kept (at most GAP_MAX), and around your classes,
commitments and calendar events (a block that would overlap one goes after it); pushing "by" some time moves only
the ones not over yet, in their order. Starting over, what's due soonest goes first (blocks tied to nothing keep their
places), and an order you give ("homework first, then quiz prep") comes before that. Blocks whose thing is done, over
or moved past "due soon" (deadlines.plan_h) since they were planned are dropped and named. A block planned twice keeps
its first. One that would end after LATEST_H past midnight is left out and named, and so is what's due within a day
with no block. The new plan goes in the daily note too.

A block planned on a call or with /blocks add that overlaps one already there goes in the first free time after it
(said), or isn't planned when there's none before LATEST_H.
"""

from __future__ import annotations

import datetime as dt
import re
import time
import urllib.parse
import uuid

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.deadlines import STOP, similar, when_text
from kurooto.modules.google import GoogleError, GooglePart, NeedsSignIn

register_defaults(
    "agent_plan",
    {
        "name": "Agent plan",
        "remind_min": 5,
        # (0.9.0) a call Kurooto places by itself (a check-in, a nudge; never one you asked for, never an alarm) waits
        # for the end of a block of yours that's running (modules/calls)
        "holds_calls": False,
        # (0.9.0) when a block of yours starts and you're at your desk (Face presence or the computer in use), one
        # message offers a Study mode focus for what it's for; the focus starts only on your tap
        "start_focus": True,
        # (0.9.1) something you said you'd do by today ("I'll send the draft by 6") gets a half-hour block in your
        # free time before it's due, never over anything already there; one line says so, with Remove
        "thread_slot": False,
    },
)
THREAD_MIN, THREAD_MAX = 30, 3  # (thread_slot) a block's minutes; blocks a day, at most
FOCUS_EVERY = "every 5m"  # (start_focus) how often it looks for a block that just started
BUSY_KEEP_S = 120  # (0.9.0) the blocks Start-by and Revision count as busy are fetched at most this often
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
ORDER = re.compile(r"\s*(?:[,;>\n]|\band then\b|\bthen\b|\bafter that\b)\s*", re.I)  # "homework first, then quiz"
SAME = {"hw": "homework", "homeworks": "homework", "preparation": "prep", "preparing": "prep", "revise": "revision",
        "revising": "revision", "quizzes": "quiz", "problems": "problem"}  # fmt: skip
FILL = {"first", "then", "next", "last", "after", "that", "before", "do", "start", "with", "finally", "block", "blocks",
        "session", "sessions", "those", "these", "this", "them", "it", "all"}  # fmt: skip


def words(text: str) -> set[str]:
    """The words that name a block ("Bayesian: HW08" -> bayesian, homework, 8), for an order or a removal."""
    got = re.findall(r"[a-z]+|\d+", str(text or "").lower())
    return {str(int(w)) if w.isdigit() else SAME.get(w, w) for w in got if w not in STOP and w not in FILL}


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

    def start(self):
        self.every("block_start", FOCUS_EVERY, lambda p: self.block_start())
        self.every("thread_slots", "every 30m", lambda p: self.thread_slots())

    # ------------------------------------------------------------------ (0.9.1) a slot for what you said you'd do
    def thread_slots(self, t: dt.datetime | None = None) -> int:
        """(agent_plan.thread_slot, off) Open threads due later today (core/threads.py) with no block yet: a
        THREAD_MIN-minute block in the first free time before each is due, around your blocks, classes, commitments
        and calendar events (never moving or covering one), at most THREAD_MAX a day. One line says each, with
        Remove. How many were planned."""
        if not self.setting("thread_slot") or not self.plan_ready():
            return 0
        from kurooto.core import threads

        t = t or now()
        edge = dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(0))
        rows = [r for r in threads.due_by(self.app, edge, 10) if r["due_dt"] > t]
        if not rows:
            return 0
        st = jload(self.file, {}) or {}
        day = t.date().isoformat()
        done = [k for k in st.get("thread_slots") or [] if k.startswith(day)]
        n = 0
        for r in rows:
            key = f"{day}|{r['id']}"
            if key in done or len(done) >= THREAD_MAX:
                continue
            at = self._free_before(t, r["due_dt"], dt.timedelta(minutes=THREAD_MIN))
            done.append(key)  # tried once a day: no fit now is no fit
            if at is None:
                continue
            title = str(r["text"]).strip()[:80]
            said = self.plan_block(at, at + dt.timedelta(minutes=THREAD_MIN), title, check=False)
            if not said.startswith("Planned"):
                continue
            n += 1
            self.app.notify(
                f"You said you'd {title.rstrip('.')} by {r['due_dt']:%H:%M}: {THREAD_MIN} minutes for it at "
                f"{at:%H:%M} in your Agent plan.",
                kind="info",
                why="agent_plan.thread_slot",
                buttons=[[("Remove", f"apl:thread:{at:%H%M}")]],
                about=title,
            )
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st["thread_slots"] = done[-20:]
            jsave(self.file, st)
        self.app.events.emit("plan_thread_slots", planned=n)
        return n

    def _free_before(self, t: dt.datetime, due: dt.datetime, length: dt.timedelta) -> dt.datetime | None:
        """The first start from t (to the next quarter hour) with `length` free before `due`: none of your blocks,
        classes, commitments or calendar events in it. None when there's no such time."""
        start = t.replace(second=0, microsecond=0) + dt.timedelta(minutes=(-t.minute) % 15 or 15)
        busy = [(b["start"], b["end"]) for b in self.plan_blocks(t.date())] + self._busy_else(t, due)
        while start + length <= due:
            hit = [e for s, e in busy if s < start + length and e > start]
            if not hit:
                return start
            start = max(hit)
            start += dt.timedelta(minutes=(-start.minute) % 15)
        return None

    def _remove_thread_block(self, hhmm: str) -> str:
        """Remove under a thread's block: that block only, if it's still Kurooto's and still there."""
        t = now()
        try:
            at = t.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:4]), second=0, microsecond=0)
        except ValueError:
            return "That block is gone."
        cid = self.calendar_id(create=False)
        b = next((b for b in self.plan_blocks(at.date()) if b["start"] == at and b.get("id")), None)
        if not cid or b is None:
            return "That block is gone already."
        self._delete(cid, b["id"])
        self.plan_blocks(at.date())
        return f"Removed {b['title']} at {at:%H:%M}."

    def block_start(self, t: dt.datetime | None = None) -> bool:
        """(0.9.0, agent_plan.start_focus) A block that started in the last five minutes, you at your desk: one offer
        of a Study mode focus for its subject (modules/study.py), tied to the deadline it's for. Away from the desk:
        nothing, and nothing is noted. True when it offered."""
        if not self.setting("start_focus"):
            return False
        study = self.app.modules.get("study")
        if study is None or not self.app.is_on("study"):
            return False
        t = t or now()
        st = jload(self.file, {}) or {}
        b = next(
            (
                b
                for b in (st.get("days") or {}).get(t.date().isoformat()) or []
                if t - dt.timedelta(minutes=5) <= dt.datetime.fromisoformat(b["start"]) <= t
            ),
            None,
        )
        key = f"{b['start'][:16]}|{b['title']}" if b else ""
        if b is None or key in (st.get("focus_offered") or []) or study.timer().get("ends"):
            return False
        try:
            from kurooto.mind import presence_forecast as pf

            if not pf.at_desk(self.app):
                return False
        except Exception:
            return False
        src = self.source(b["title"], t.date())
        it = src[1] if src else {}
        slug = it.get("subject") or (self._deadlines().subject_of(b["title"]) if self._deadlines() else None)
        if not slug:
            return False
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st["focus_offered"] = [*(st.get("focus_offered") or [])[-20:], key]
            st["focus_pending"] = {"subject": slug, "item": src[0] if src else ""}
            jsave(self.file, st)
        mins = int(float(self.app.settings.get("study.focus_min") or 25))
        self.app.notify(
            f"Your block {b['title']} starts now. Start a {mins}-minute focus for it? Calls and messages wait till "
            "it ends.",
            kind="info",
            why="agent_plan.start_focus",
            buttons=[[(f"Start {mins} min", "apl:focus:start")]],
            about=b["title"],
        )
        self.app.events.emit("plan_focus_offered")
        return True

    def _focus_answer(self) -> str:
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            p = st.pop("focus_pending", None)
            jsave(self.file, st)
        study = self.app.modules.get("study")
        if not p:
            return "That offer is over."
        if study is None or not self.app.is_on("study"):
            return "The Study tracker is off."
        return study.timer_start(p["subject"], deadline=p.get("item") or None)

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
            mine = (e.get("extendedProperties") or {}).get("private") or {}
            out.append(
                {
                    "id": e.get("id"),
                    "title": e.get("summary") or "(no title)",
                    "start": dt.datetime.fromisoformat(s).astimezone().replace(tzinfo=None),
                    "end": dt.datetime.fromisoformat(f).astimezone().replace(tzinfo=None),
                    "item": mine.get("item") or "",  # the deadline it's for, and its due date when it was planned
                    "due": mine.get("due") or "",
                }
            )
        self._remember(day, out)
        return out

    def busy(self, t0: dt.datetime, until: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """(0.9.0) Kurooto's own blocks between t0 and `until` as busy times, the one ledger Start-by's free time and
        Revision read (modules/startby.py, modules/revision.py): time you've planned is not free for something else.
        One request, kept BUSY_KEEP_S seconds (a block planned, moved or removed here clears it). Not set up, signed
        out or Google unreachable: no busy time, the way it was before."""
        if not self.plan_ready():
            return []
        key = (t0.replace(second=0, microsecond=0), until.replace(second=0, microsecond=0))
        memo = getattr(self, "_busy_memo", None)
        if memo and memo[0] == key and time.monotonic() - memo[1] < BUSY_KEEP_S:
            return list(memo[2])
        try:
            cid = self.calendar_id(create=False)
            if not cid:
                return []
            q = {
                "timeMin": t0.astimezone().isoformat(),
                "timeMax": until.astimezone().isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 250,
            }
            items = self.google.api("calendar", f"{self._events_path(cid)}?{urllib.parse.urlencode(q)}").get(
                "items", []
            )
        except Exception as e:  # signed out, offline, the calendar deleted: plan as if there were no blocks
            self.app.events.emit("agent_plan_failed", error=f"busy: {type(e).__name__}"[:120])
            return []
        out = []
        for e in items:
            s, f = (e.get("start") or {}).get("dateTime"), (e.get("end") or {}).get("dateTime")
            if not s or not f or e.get("status") == "cancelled":
                continue
            a, b = (dt.datetime.fromisoformat(x).astimezone().replace(tzinfo=None) for x in (s, f))
            if b > a:
                out.append((a, b))
        self._busy_memo = (key, time.monotonic(), out)
        return list(out)

    def running_block(self, t: dt.datetime | None = None) -> dict | None:
        """(0.9.0) The block of yours running at t (default now), from the blocks remembered for today; None."""
        t = t or now()
        st = jload(self.file, {}) or {}
        for b in (st.get("days") or {}).get(t.date().isoformat()) or []:
            try:
                a, f = dt.datetime.fromisoformat(b["start"]), dt.datetime.fromisoformat(b["end"])
            except (KeyError, ValueError):
                continue
            if a <= t < f:
                return {"title": b.get("title") or "", "start": a, "end": f}
        return None

    def _remember(self, day: dt.date, blocks: list[dict]) -> None:
        self._busy_memo = None  # a change here: Start-by asks Google again
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

    def plan_block(
        self,
        start: dt.datetime,
        end: dt.datetime,
        title: str,
        item: str | None = None,
        *,
        due: str = "",
        shift: bool = False,
        check: bool = True,
    ) -> str:
        """Put one time block into Kurooto's own calendar. Never touches another calendar. It's tied to the deadline,
        quiz or exam it's for (`item`, else the one its title names) and that one's due date (`due`, else the one it
        has now), so a reschedule knows when it has no point any more. `check`: one for something done or over isn't
        planned. `shift`: one that overlaps a block already there goes in the first free time after it, said (or
        isn't planned when there's none before LATEST_H past midnight)."""
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:200] or "Focus"
        start, end = start.replace(second=0, microsecond=0), end.replace(second=0, microsecond=0)
        if end <= start:
            return "The block has to end after it starts."
        if end - start > dt.timedelta(hours=12):
            return "That's longer than 12 hours; plan it in smaller blocks."
        t = now()
        if end < t or start > t + dt.timedelta(days=31):
            return "Blocks go between now and a month ahead."
        src = self.source(title, start.date(), item or "") if check or item else None
        why = self._over(src[1]) if src and check else ""
        if why:
            return f"Not planned: {self._name(src[1])} is {why}."
        existing = self.plan_blocks(start.date())
        if any(b["title"].lower() == title.lower() and b["start"] == start for b in existing):
            return f"Already planned: {start:%a %H:%M} {title}."
        said = ""
        if shift:
            near = existing + self.plan_blocks(start.date() + dt.timedelta(days=1))
            hit = [b for b in near if b["start"] < end and b["end"] > start]
            if hit:
                length, s = end - start, start
                for b in sorted(near, key=lambda b: b["start"]):
                    if b["start"] < s + length and b["end"] > s:
                        s = max(s, b["end"])
                names = "; ".join(f"{b['title']} ({b['start']:%H:%M}–{b['end']:%H:%M})" for b in hit)
                latest = dt.datetime.combine(start.date() + dt.timedelta(days=1), dt.time(LATEST_H))
                if s + length > latest:
                    return (
                        f"Not planned: {start:%H:%M}–{end:%H:%M} overlaps {names}, and there's no free time after it "
                        f"before {latest:%H:%M}. Remove those first (remove_blocks) or pick another time."
                    )
                said = f"{start:%H:%M}–{end:%H:%M} overlapped {names}, so it went in the first free time after: "
                start, end = s, s + length
                existing = [b for b in near if b["start"].date() == start.date()]
        mins = int(self.setting("remind_min") or 0)
        link = {"item": src[0], "due": due or src[1]["due"]} if src else {}
        body = {
            "summary": title,
            "description": f"Planned with {self.app.name}.",
            "start": {"dateTime": start.astimezone().isoformat()},
            "end": {"dateTime": end.astimezone().isoformat()},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": mins}] if mins else []},
            "extendedProperties": {"private": {"kurooto": "1", **link}},
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
        return f"{said}Planned {start:%a %H:%M}–{end:%H:%M}: {title}."

    # ----------------------------------------------------------------------------- what a block is for
    def _deadlines(self):
        dl = self.app.modules.get("deadlines")
        return dl if dl is not None and self.app.is_on("deadlines") else None

    def _name(self, it: dict) -> str:
        dl = self._deadlines()
        return dl.full_title(it) if dl is not None else it["title"]

    def source(self, title: str, day: dt.date, item: str = "") -> tuple[str, dict] | None:
        """(id, deadline) a block is for: the one it was planned for, else the one its title names (due from the day
        before its day on; one still to do before one that's over, the soonest due). None: it's for nothing known."""
        dl = self._deadlines()
        if dl is None:
            return None
        items = dl.items()
        if item:
            j = dl._resolve(items, item)
            return (j, items[j]) if j else None
        lo, subj, found = (day - dt.timedelta(days=1)).isoformat(), dl.subject_of(title), []
        for i, it in items.items():
            if it["due"] < lo or (subj and it.get("subject") and it["subject"] != subj):
                continue
            full = dl.full_title(it)
            if len(re.findall(r"[a-z]+|\d+", full.lower())) < 2:
                continue  # a bare "Quiz" names nothing in particular
            if similar(title, full, dl._subject_words(subj or it.get("subject"))):
                found.append((i, it))
        live = [x for x in found if not self._over(x[1])]
        return min(live or found, key=lambda x: x[1]["due"], default=None)

    def _soon_h(self) -> float:
        dl = self._deadlines()
        return dl.plan_hours() if dl is not None else 72.0

    def _over(self, it: dict, due_then: str = "") -> str:
        """Why a block for this deadline has no point any more ("" while it has): done, dropped, a quiz or exam
        that's over, or (given the due date it was planned for) moved past "due soon" since."""
        status = it.get("status") or "open"
        if status != "open":
            return "done" if status == "done" else "dropped"
        due, t = dt.datetime.fromisoformat(it["due"]), now()
        if it.get("kind") == "exam" and due <= t:
            return f"over ({when_text(it['due'])})"
        if due_then and due_then[:16] != it["due"][:16] and due > t + dt.timedelta(hours=self._soon_h()):
            return f"moved to {when_text(it['due'])}"
        return ""

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
        self._busy_memo = None
        try:
            self.google.api("calendar", f"{self._events_path(cid)}/{urllib.parse.quote(eid, safe='')}", method="DELETE")
        except GoogleError as e:
            if e.code not in (404, 410):
                raise

    def _tonight(self, t: dt.datetime) -> list[dict]:
        """Today's blocks, and the ones past midnight up to LATEST_H (where a late reschedule puts them)."""
        latest = dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(LATEST_H))
        late = [b for b in self.plan_blocks(latest.date()) if b["start"] < latest]
        return sorted(self.plan_blocks(t.date()) + late, key=lambda b: b["start"])

    def _tied(self, b: dict) -> dict:
        """The block with what it's for: _item and _due (that deadline's id and due date, "" for nothing), _over (why
        it has no point any more, else "") and _words (its title's and that deadline's, for an order or a removal)."""
        src = self.source(b["title"], b["start"].date(), b.get("item") or "")
        it = src[1] if src else {}
        return {
            **b,
            "_item": src[0] if src else "",
            "_due": it.get("due", ""),
            "_over": self._over(it, b.get("due") or "") if src else "",
            "_words": words(f"{b['title']} {self._name(it) if src else ''}"),
        }

    @staticmethod
    def _arrange(todo: list[dict], order: str) -> tuple[list[dict], list[str]]:
        """The blocks in the order they go: the ones `order` names first, in its order; then the rest, those for a
        deadline soonest due first in the places they held, the others where they were. Plus the parts of `order`
        that named no block."""
        named, missing, rest = [], [], list(todo)
        for part in (p.strip() for p in ORDER.split(order or "")):
            want = words(part)
            got = [b for b in rest if want and want <= b["_words"]]
            if not got:
                missing += [part] if part and want else []
                continue
            named += sorted(got, key=lambda b: b["_due"] or "~")
            rest = [b for b in rest if all(b is not g for g in got)]
        dated = iter(sorted((b for b in rest if b["_due"]), key=lambda b: b["_due"]))
        return named + [next(dated) if b["_due"] else b for b in rest], missing

    @staticmethod
    def _undo_rows(blocks: list[dict]) -> list[dict]:
        return [
            {
                "title": b["title"],
                "start": b["start"].isoformat(),
                "end": b["end"].isoformat(),
                "item": b.get("item") or "",
                "due": b.get("due") or "",
            }
            for b in blocks
        ]

    def _keep_undo(self, old: list[dict], new: list[dict]) -> str:
        uid = uuid.uuid4().hex[:8]
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st["undo"] = {"uid": uid, "old": self._undo_rows(old), "new": self._undo_rows(new)}
            jsave(self.file, st)
        return uid

    def reschedule(self, start: dt.datetime | None = None, by: dt.timedelta | None = None, order: str = "") -> str:
        """Move today's blocks still to do so they start at `start` (default: now, at the next quarter hour), or later
        by `by`. Starting over (no `by`) takes the blocks that are past too (a late start: you slept through them) and
        puts what's due soonest first; `order` ("homework, then quiz prep") goes before that. Blocks for something
        done, over or moved away are dropped. See the module's notes."""
        t, missed = now(), by is None
        latest = dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(LATEST_H))
        blocks = self._tonight(t)
        todo, gone, seen = [], [], set()
        for b in blocks:
            if b["end"] <= t and not missed:
                continue
            key = b["title"].strip().lower()
            (gone if key in seen else todo).append(b)
            seen.add(key)
        if not todo:
            return "No blocks planned today to move." if not blocks else "Every block today is done already."
        todo = [self._tied(b) for b in todo]
        stale = [b for b in todo if b["_over"]]
        todo = [b for b in todo if not b["_over"]]
        gaps = [dt.timedelta(0)] + [
            min(GAP_MAX, max(dt.timedelta(0), b["start"] - a["end"])) for a, b in zip(todo, todo[1:], strict=False)
        ]
        soon = (t + dt.timedelta(minutes=14)).replace(second=0, microsecond=0)
        soon -= dt.timedelta(minutes=soon.minute % 15)
        if start is None and todo:
            start = todo[0]["start"] + by if by else soon  # pushed: each block that much later
        todo, unnamed = self._arrange(todo, order) if missed or order else (todo, [])
        busy = self._busy_else(min(start, t), latest)
        new, left, cur = [], [], start
        for gap, b in zip(gaps, todo, strict=False):
            cur += gap
            end = cur + (b["end"] - b["start"])
            for s, f in busy:  # 0.9.0: a class, a commitment or an event in the way: the block goes after it
                if s < end and f > cur:
                    cur = max(cur, f)
                    end = cur + (b["end"] - b["start"])
            if end > latest:
                left.append(b)
            else:
                new.append({"title": b["title"], "start": cur, "end": end, "item": b["_item"], "due": b["_due"]})
                cur = end
        cid = self.calendar_id()
        for b in todo + stale + gone:
            self._delete(cid, b["id"])
        for b in new:
            self.plan_block(b["start"], b["end"], b["title"], b["item"] or None, check=False)
        self._keep_undo(todo + stale + gone, new)
        lines = [f"{b['start']:%H:%M}–{b['end']:%H:%M}  {b['title']}" for b in new]
        if stale:
            lines.append(
                "Dropped, nothing left to do for them: " + "; ".join(f"{b['title']} ({b['_over']})" for b in stale)
            )
        if left:
            lines.append(
                f"Didn't fit before {latest:%H:%M}, taken off the plan: " + "; ".join(b["title"] for b in left)
            )
        if unnamed:
            lines.append("No block for: " + "; ".join(unnamed))
        due = self._unplanned((start or t) + dt.timedelta(days=1), {b["_item"] for b in todo})
        if due:
            lines.append("Due within a day with no block yet: " + "; ".join(due))
        from kurooto.modules import daily

        try:
            daily.append(self.app, f"Plan rescheduled ({t:%H:%M})", "\n".join(f"- {x}" for x in lines), t.date())
        except OSError:
            pass
        self.app.events.emit("plan_rescheduled", moved=len(new), dropped=len(gone), left=len(left), stale=len(stale))
        return "Your day, from now:\n" + "\n".join(lines) + "\n(/blocks undo puts it back.)"

    def _busy_else(self, a: dt.datetime, b: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """What a reschedule keeps clear between a and b, soonest first: classes you go to (Subjects, skips left
        out), commitments (Commitments) and your calendar's timed events (Calendar), as naive local times. A feature
        that's off or fails adds nothing."""
        out = []
        day = a.date() - dt.timedelta(days=1)
        for mid, get in (("subjects", "classes_on"), ("commitments", "on")):
            m = self.app.modules.get(mid)
            if m is None or not self.app.is_on(mid):
                continue
            d = day
            while d <= b.date():
                try:
                    out += [(c["start_dt"], c["end_dt"]) for c in getattr(m, get)(d)]
                except Exception:
                    break
                d += dt.timedelta(days=1)
        cal = self.app.modules.get("calendar")
        if cal is not None and self.app.is_on("calendar"):
            try:
                for e in cal.events(a.astimezone(), b.astimezone()):
                    if not e.get("all_day"):
                        out.append(tuple(x.astimezone().replace(tzinfo=None) for x in (e["start_dt"], e["end_dt"])))
            except Exception:
                pass
        return sorted((s, f) for s, f in out if f > a and s < b and f > s)

    def _unplanned(self, until: dt.datetime, tied: set[str]) -> list[str]:
        """What's due between now and `until` that no block is for: "Bayesian: Quiz (Thu 29 Oct 10:00)"."""
        dl, t = self._deadlines(), now()
        if dl is None:
            return []
        out = []
        for i, it, _h in dl.upcoming(24 * 40):
            if i not in tied and t < dt.datetime.fromisoformat(it["due"]) <= until and not self._over(it):
                out.append(f"{dl.full_title(it)} ({when_text(it['due'])})")
        return out

    def remove_blocks(self, what: str = "", after: dt.datetime | None = None) -> str:
        """Take blocks out of the plan (today's, and tonight's past midnight up to LATEST_H; not ones already over):
        the ones `what` names (words of their title or of the deadline they're for; "all": every one), every one from
        `after` on, or the named ones from then on. Only Kurooto's own calendar; /blocks undo puts them back."""
        t, w = now(), re.sub(r"\s+", " ", str(what or "")).strip()
        every = bool(re.fullmatch(r"(?i)(?:all|everything)(?: (?:the )?(?:blocks?|sessions?|of them))?", w))
        want = set() if every else words(w)
        if (w and not every and not want) or (not w and after is None):
            return "Which blocks? Name them (a title or subject), say all, or give a time to remove from."
        here = [b for b in self._tonight(t) if b["end"] > t]
        out = [
            b for b in (self._tied(b) for b in here) if (after is None or b["start"] >= after) and want <= b["_words"]
        ]
        if not out:
            have = "; ".join(f"{b['start']:%H:%M}–{b['end']:%H:%M} {b['title']}" for b in here) or "nothing"
            return f"No planned block matches that, so nothing was removed. Planned now: {have}."
        cid = self.calendar_id()
        for b in out:
            self._delete(cid, b["id"])
        self._keep_undo(out, [])
        self.app.events.emit("plan_blocks_removed", blocks=len(out))
        gone = "; ".join(f"{b['title']} ({b['start']:%H:%M}–{b['end']:%H:%M})" for b in out)
        n = f"{len(out)} block{'s' if len(out) != 1 else ''}"
        return f"Removed {n} from the plan: {gone}. (/blocks undo puts them back.)"

    def undo_reschedule(self) -> str:
        st = jload(self.file, {}) or {}
        u = st.get("undo")
        if not u:
            return "There's no reschedule or removal to undo."
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
                self.plan_block(s, e, b["title"], b.get("item") or None, due=b.get("due") or "", check=False)
                back += 1
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st.pop("undo", None)
            jsave(self.file, st)
        self.app.events.emit("plan_reschedule_undone", back=back)
        return f"Put {back} block{'s' if back != 1 else ''} back where they were (the ones already past stay gone)."

    # ---------------------------------------------------------------------------- a deadline that moved
    def deadline_changed(self, j: str, what: str) -> None:
        """(0.9.0) A deadline moved (modules/deadlines.py): its blocks still ahead in Kurooto's calendar get "(moved to
        ...)" in their titles and one message asks Remove or Keep. Nothing is removed without that tap."""
        if what != "moved" or not self.plan_ready():
            return
        dl = self._deadlines()
        it = (dl.items() if dl is not None else {}).get(j)
        cid = self.calendar_id(create=False)
        if not it or not cid:
            return
        t = now()
        q = {
            "timeMin": t.astimezone().isoformat(),
            "timeMax": (t + dt.timedelta(days=31)).astimezone().isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 250,
        }
        items = self.google.api("calendar", f"{self._events_path(cid)}?{urllib.parse.urlencode(q)}").get("items", [])
        mine = [e for e in items if ((e.get("extendedProperties") or {}).get("private") or {}).get("item") == j]
        mark = f" (moved to {when_text(it['due'])})"
        rows = []
        for e in mine:
            s_, f_ = (e.get("start") or {}).get("dateTime"), (e.get("end") or {}).get("dateTime")
            if not s_ or not f_ or e.get("status") == "cancelled":
                continue
            a, b = (dt.datetime.fromisoformat(x).astimezone().replace(tzinfo=None) for x in (s_, f_))
            old = re.sub(r" \(moved to [^)]*\)$", "", e.get("summary") or "")
            due = ((e.get("extendedProperties") or {}).get("private") or {}).get("due") or ""
            self._delete(cid, e["id"])
            self.plan_block(a, b, old + mark, j, due=due, check=False)
            rows.append({"title": old, "start": a.isoformat(), "end": b.isoformat(), "item": j, "due": due})
        if not rows:
            return
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            st.setdefault("moved", {})[j] = {"blocks": rows, "mark": mark}
            jsave(self.file, st)
        n = f"{len(rows)} plan block{'s' if len(rows) != 1 else ''}"
        name = dl.full_title(it) if dl is not None else it["title"]
        self.app.notify(
            f"{name} moved to {when_text(it['due'])}: remove its {n} from your Agent plan calendar?",
            kind="info",
            title="Plan blocks",
            why="agent_plan.moved",
            buttons=[[("Remove", f"apl:mv{j}:remove"), ("Keep", f"apl:mv{j}:keep")]],
            about=name,
            item=j,
        )
        self.app.events.emit("plan_moved_offered", blocks=len(rows))

    def _moved_answer(self, j: str, remove: bool) -> str:
        """Remove: the blocks go (/blocks undo puts them back). Keep: their titles go back to what they were."""
        with Lock(self.app.paths.state, "agent-plan"):
            st = jload(self.file, {}) or {}
            rec = (st.get("moved") or {}).pop(j, None)
            jsave(self.file, st)
        if not rec:
            return "Already answered."
        cid = self.calendar_id(create=False)
        if not cid:
            return "The Agent plan calendar is gone, so there's nothing to change."
        old = []
        for r in rec["blocks"]:
            a, b = dt.datetime.fromisoformat(r["start"]), dt.datetime.fromisoformat(r["end"])
            hit = next(
                (x for x in self.plan_blocks(a.date()) if x["start"] == a and x["title"] == r["title"] + rec["mark"]),
                None,
            )
            if hit is None:
                continue  # moved or removed since
            self._delete(cid, hit["id"])
            old.append({**hit, "title": r["title"], "item": r["item"], "due": r["due"]})
            if not remove:
                self.plan_block(a, b, r["title"], r["item"] or None, due=r["due"], check=False)
        self.app.events.emit("plan_moved_answered", removed=bool(remove), blocks=len(old))
        if not remove:
            return "Kept: the blocks stay where they are."
        self._keep_undo(old, [])
        return f"Removed {len(old)} block{'s' if len(old) != 1 else ''}. (/blocks undo puts them back.)"

    def _button(self, ref: str, act: str) -> str:
        """Undo under a removal: only while it's still the last change to the plan. Remove / Keep under a deadline
        that moved (0.9.0)."""
        if ref == "focus" and act == "start":
            return self._focus_answer()
        if ref == "thread":  # (0.9.1) Remove under a thread's block
            try:
                return self._remove_thread_block(act)
            except (NeedsSignIn, GoogleError) as err:
                return f"Google Calendar didn't take it: {err}"[:300]
        if ref.startswith("mv") and act in ("remove", "keep"):
            try:
                return self._moved_answer(ref[2:], act == "remove")
            except (NeedsSignIn, GoogleError) as err:
                return f"Google Calendar didn't take it: {err}"[:300]
        if act != "undo":
            return "That button is out of date."
        if ((jload(self.file, {}) or {}).get("undo") or {}).get("uid") != ref:
            return "The plan changed again since; /blocks undo takes back the latest change."
        return self.undo_reschedule()

    def callbacks(self):
        return {"apl": self._button}

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
            return self.reschedule(start, by, str(a.get("order") or ""))
        except ValueError as err:
            return f"I couldn't read that time: {err}"
        except (NeedsSignIn, GoogleError) as err:
            return f"Google Calendar didn't take it: {err}"[:300]

    def _tool_remove(self, a: dict) -> str:
        if not self.ready()[0]:
            return f"The Agent plan calendar isn't ready: {self.ready()[1]}."
        try:
            said = self.remove_blocks(str(a.get("what") or ""), self._after(str(a.get("after") or "")))
        except ValueError as err:
            return f"I couldn't read that time: {err}"
        except (NeedsSignIn, GoogleError) as err:
            return f"Google Calendar didn't take it: {err}"[:300]
        uid = ((jload(self.file, {}) or {}).get("undo") or {}).get("uid")
        if said.startswith("Removed") and uid:
            self.app.notify(said, kind="info", why="asked", buttons=[[("Undo", f"apl:{uid}:undo")]])
        return said

    @staticmethod
    def _after(text: str) -> dt.datetime | None:
        """ "22:00" for a removal: tonight's, even once it's past ("after 10" at 21:00 is 22:00)."""
        if not str(text or "").strip():
            return None
        t = now()
        a = when(str(text).strip(), base=t)
        return a - dt.timedelta(days=1) if a - t > dt.timedelta(hours=20) else a

    def _tool_undo(self, a: dict) -> str:
        if not self.ready()[0]:
            return f"The Agent plan calendar isn't ready: {self.ready()[1]}."
        try:
            return self.undo_reschedule()
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
            return self.plan_block(s, e, str(a.get("title") or ""), shift=True)
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
                hint="plan_block when they agree to a time for something (a study block, a task) today or later. It "
                "never overlaps another block: it moves to the first free time after it, or refuses; tell them the "
                "time its result gives, not the one you asked for.",
            ),
            Tool(
                "reschedule_day",
                "Move today's blocks still to do (and ones they slept through) to start later, keeping their lengths "
                "and the breaks between them; what's due soonest goes first, and blocks for something done, over or "
                'moved away are dropped. start: "19:00", "in 2 hours" or empty for now; or by: "2 hours" to push '
                "everything that much later, in its order. order: what goes first when they say so, in their order, "
                'e.g. "homework; Bayesian quiz prep; Real Analysis".',
                self._tool_reschedule,
                {"start": arg(), "by": arg(), "order": arg("optional: what goes first, in their order")},
                (),
                offline="queue",
                hint='When they want the day rescheduled or pushed ("I just woke up", "push my day"), call '
                'reschedule_day once instead of plan_block for each block; when they say an order ("homework first, '
                'then quiz prep"), pass it as order. Tell them what its result says was dropped or is due with no '
                "block.",
            ),
            Tool(
                "remove_blocks",
                "Take planned blocks out of Kurooto's own \"Agent plan\" calendar (today's and tonight's, not ones "
                'already over): what names them (a title or subject, or "all"); after (like "22:00") takes every one '
                "from then on, or with what only the named ones from then on.",
                self._tool_remove,
                {"what": arg("a title or subject, or all"), "after": arg('optional: a time like "22:00"')},
                (),
                offline="queue",
                hint="remove_blocks when they want planned blocks gone; undo_plan puts back the last reschedule or "
                "removal.",
            ),
            Tool(
                "undo_plan",
                "Put the Agent plan back as it was before the last reschedule_day or remove_blocks.",
                self._tool_undo,
                {},
                (),
                offline="queue",
            ),
        ]

    def intents(self):
        def match(text: str):
            m = SHIFT.match(text.strip())
            return {"from": m.group("from") or "", "by": m.group("by") or ""} if m else None

        def run(msg, sl):
            return self._tool_reschedule({"start": sl["from"], "by": sl["by"]})

        return [
            Intent(
                "reschedule_day",
                "reschedule my day, push my day by 2 hours, replan from 19:00",
                match,
                run,
                examples=("push my day by 2 hours", "reschedule my day"),
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
                "your Agent plan blocks today (/blocks add 14:00-15:30 what, /blocks shift [19:00 | by 2 hours] "
                "reschedules the day, /blocks remove <what> | after 22:00, /blocks undo, /blocks clear)",
                self._cmd,
                usage="/blocks [add <from>-<to> <what> | shift [<time> | by <hours>] | remove <what> [after <time>] | "
                "undo | clear]",
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
            if word.lower() == "remove":
                what, _, after = rest.strip().partition("after ")
                return self.remove_blocks(what.strip(), self._after(after))
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
