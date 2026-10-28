"""Study tracker: how long you spend on each subject, counted from the window you're working in. A window whose title
names one of your subjects (its name or a short name you gave it in Subjects, e.g. a PDF called "linear-algebra-
week3.pdf", or a note in that subject's folder) counts for that subject, while you're at the computer: not idle for 5
minutes (study.idle_min) and the screen not locked. Only the minutes per subject are kept, never window titles.
Research: a window naming one of study.research_paths (a word, or a folder whose name is matched), or a project or
repository of Research when that's on, counts as "Research".

Time away from the computer (library, paper): start a session with "/study linear algebra 50" (or "starting
linear algebra for 50 min") and end it with "/study stop" ("done studying"); or log it afterwards: "/studied 2h
linear algebra", "studied stats for an hour", or tell it on a call. /study shows today, /study week the last 7 days
("how much did I study today?" works too). At 23:45 the day's hours go into your daily note ("## Study hours").
The dashboard's Study mode (/study mode on|off, core/actions.py) has a timer: a focus session for a subject (focus
time, so calls and messages wait, and the minutes logged here), then a break; pause and reset.
Works on Windows, macOS (it asks once for permission to see window titles) and Linux on X11, Hyprland or Sway;
other Linux desktops can only log by hand. How it tells you're away: core/idle.py (on Wayland desktops without an idle
API, your idle tool can tell it: `kurooto idle away` / `kurooto idle back`).

Seen minutes (0.9.0, study.seen): another feature (an add-on) may add minutes it saw you on a subject's topic where the
window doesn't name the subject itself (add_seen: a subject and seconds, never a title). They're kept apart
("<subject>|seen"), count in the totals, and /study says how much of the day was seen that way; never while a session
or Study mode's focus runs (that time is the session's).
"""

from __future__ import annotations

import asyncio
import ctypes
import datetime as dt
import json
import re
import shutil
import subprocess
import sys

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.idle import IdleProbe
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_minutes, another_day

register_defaults(
    "study",
    {
        "sample_s": 30,
        "idle_min": 5,
        "keywords": {},  # {subject slug: [words]}
        "daily_note": "23:45",  # the day's hours go into your daily note at this time; None = don't
        "research_paths": [],  # words or folders: a window naming one counts as Research
        "focus_min": 25,  # Study mode's timer: minutes of focus (calls and messages wait; the time is logged)
        "break_min": 5,  # Study mode's timer: minutes of break after each focus
        "timer_ends_mode": False,  # when a focus ends, Study mode ends too (look.study_mode), instead of a break
        # (0.9.0) another feature (an add-on) may add minutes it saw you on a subject's topic, kept apart as "seen"
        # and never while a session runs; nothing is counted until one does
        "seen": True,
    },
)
# "turn on study mode", "leave study mode", "study mode off": the dashboard's Study mode (core/actions.py)
MODE_ON = ("turn on", "switch on", "switch to", "go into", "start", "enter", "open")
MODE_OFF = ("turn off", "switch off", "leave", "exit", "end", "stop", "close", "quit")
RESEARCH = "research"  # the key research time is kept under (a subject called "research" shares it)
HOW = {  # how the tracker tells you're away (core/idle.py), for the health line
    "windows": "Windows' last input",
    "ioreg": "macOS's last input",
    "hook": "your idle tool (kurooto idle away/back)",
    "x11": "xprintidle",
    "gnome": "GNOME's idle monitor",
    "screensaver": "the screensaver's idle time",
    "logind": "logind's idle hint",
    "watch": "input and window changes",
}


def _run(args: list[str], timeout: float = 5) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def active_title() -> str | None:
    """The focused window's title, or None if this desktop doesn't say."""
    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        h = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, buf, n + 1)
        return buf.value
    if sys.platform == "darwin":
        script = (
            'tell application "System Events" to tell (first process whose frontmost is true) to '
            'return (name as text) & " — " & (name of front window as text)'
        )
        return _run(["osascript", "-e", script]) or None
    if shutil.which("hyprctl"):
        try:
            return json.loads(_run(["hyprctl", "activewindow", "-j"]) or "{}").get("title")
        except ValueError:
            return None
    if shutil.which("swaymsg"):
        try:
            tree = json.loads(_run(["swaymsg", "-t", "get_tree"]) or "{}")
        except ValueError:
            return None
        stack = [tree]
        while stack:
            n = stack.pop()
            if n.get("focused"):
                return n.get("name")
            stack += n.get("nodes", []) + n.get("floating_nodes", [])
        return None
    if shutil.which("xdotool"):
        return _run(["xdotool", "getactivewindow", "getwindowname"]) or None
    return None


class Study(Module):
    id = "study"
    title = "Study tracker"
    description = "Minutes per subject from the window you're working in, plus what you log by hand; /study."
    requires = ("subjects",)
    privacy = "Window titles are read on this computer and thrown away; only minutes per subject are kept."

    def __init__(self, app):
        super().__init__(app)
        self.probe = IdleProbe(app.paths.state)

    def health(self):
        ok, why = self.ready()
        if not ok or not self.probe.how:
            return ok, why
        return True, f"away time from: {HOW.get(self.probe.how, self.probe.how)}"

    def start(self):
        self.action("session_end", self._session_end)
        self.action("timer_end", self._timer_end)
        at = self.setting("daily_note")
        if at:
            self.every("write", f"daily {at}", self.write_day)
        else:
            self.app.scheduler.cancel(f"{self.id}:write")

    def _file(self, day: dt.date):
        return self.app.paths.state / "study" / f"{day.isoformat()}.json"

    def day(self, day: dt.date | None = None) -> dict:
        return jload(self._file(day or now().date()), {}) or {}

    def add(self, slug: str, seconds: float, day: dt.date | None = None, manual: bool = False) -> None:
        day = day or now().date()
        with Lock(self.app.paths.state, "study"):
            d = self.day(day)
            key = f"{slug}|manual" if manual else slug
            d[key] = round(d.get(key, 0) + seconds)
            jsave(self._file(day), d)

    def add_seen(self, slug: str, seconds: float) -> bool:
        """(0.9.0, study.seen) Seconds another feature saw you on this subject's topic (a subject's slug and a number,
        nothing else), kept as "<slug>|seen" beside the tracker's own. Not while a session or Study mode's focus runs,
        not for a subject that isn't yours, at most 10 minutes a call. True when counted."""
        if self.setting("seen") is False or not seconds or seconds <= 0 or self.session().get("subject"):
            return False
        subj = self.app.modules.get("subjects")
        known = {s["slug"] for s in subj.subjects()} if subj is not None else set()
        if slug not in known and slug != RESEARCH:
            return False
        self.add(f"{slug}|seen", min(float(seconds), 600.0))
        return True

    def seen_seconds(self, days: int = 1) -> float:
        """(study.seen) The seen seconds over the last `days` days."""
        return sum(
            v
            for i in range(days)
            for k, v in self.day(now().date() - dt.timedelta(days=i)).items()
            if k.endswith("|seen")
        )

    def name_of(self, slug: str) -> str:
        if slug == RESEARCH and not any(s["slug"] == RESEARCH for s in self.app.modules["subjects"].subjects()):
            return "Research"
        return self.app.modules["subjects"].name_of(slug)

    def research_words(self) -> list[str]:
        """What marks a window as research: study.research_paths (a folder counts by its name), and Research's
        projects and repository folders when it's on."""
        words = []
        for w in self.setting("research_paths") or []:
            words.append(re.split(r"[/\\]", str(w).strip().rstrip("/\\"))[-1])
        r = self.app.modules.get("research")
        if r is not None and self.app.is_on("research"):
            try:
                for project, repos in r.projects().items():
                    words += [project, *(re.split(r"[/\\]", x.rstrip("/\\"))[-1] for x in repos)]
            except Exception:
                pass
        return sorted({w for w in words if len(w) >= 3}, key=len, reverse=True)

    def subject_of(self, title: str) -> str | None:
        subj = self.app.modules["subjects"]
        low = title.lower()
        for slug, words in (self.setting("keywords") or {}).items():
            if any(w.lower() in low for w in words):
                return slug
        hits = subj.find_in(re.sub(r"[-_./\\]+", " ", title))
        if hits:
            return hits[0]
        for s in subj.subjects():  # a note or file inside that subject's folder
            if f"{s['slug']}/" in title.replace("\\", "/") or f"/{s['slug']}" in title.replace("\\", "/"):
                return s["slug"]
        for w in self.research_words():
            if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", low):
                return RESEARCH
        return None

    async def background(self, stop: asyncio.Event) -> None:
        step = self.setting("sample_s") or 30
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.sample, step)
            except Exception as e:
                self.app.events.emit("study_failed", error=str(e)[:200])
            try:
                await asyncio.wait_for(stop.wait(), timeout=step)
            except TimeoutError:
                pass

    def sample(self, seconds: float) -> str | None:
        if self.session().get("subject"):  # a session away from the computer is running: it counts, not the window
            return None
        if self.probe.locked():  # the lock screen: you're away
            return None
        title = active_title()
        idle = self.probe.idle_seconds(title)
        if idle is not None and idle > (self.setting("idle_min") or 5) * 60:
            return None
        slug = self.subject_of(title) if title else None
        if slug:
            self.add(slug, seconds)
        return slug

    # ------------------------------------------------------------------------------------- telling you
    def totals(self, days: int = 1, last: dt.date | None = None) -> dict[str, float]:
        """Seconds per subject over `days` days ending with `last` (today unless given)."""
        out: dict[str, float] = {}
        for i in range(days):
            for k, v in self.day((last or now().date()) - dt.timedelta(days=i)).items():
                slug = k.split("|")[0]
                out[slug] = out.get(slug, 0) + v
        return out

    def report(self, days: int = 1) -> str:
        t = self.totals(days)
        if not t:
            return "No study time counted yet." if days == 1 else "No study time counted this week."
        name = self.name_of
        rows = [f"{name(k)}: {v / 3600:.1f} h" for k, v in sorted(t.items(), key=lambda kv: -kv[1])]
        head = "Today" if days == 1 else f"Last {days} days"
        seen = self.seen_seconds(days)
        if seen >= 360:  # (study.seen) how much of it another feature saw, from a tenth of an hour
            rows.append(f"(of which {seen / 3600:.1f} h seen on screen, not timed)")
        return f"{head} ({sum(t.values()) / 3600:.1f} h):\n" + "\n".join(rows)

    def log(self, text: str) -> str:
        m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hours?|m|min|mins|minutes?)\s+(.+)", text, re.I)
        if not m:
            return "Say how long and what: /studied 90m linear algebra"
        amount = float(m.group(1)) * (3600 if m.group(2).lower().startswith("h") else 60)
        slug = self.app.modules["subjects"].resolve(m.group(3).strip())
        if not slug:
            return f"I don't know the subject {m.group(3).strip()!r} (Subjects lists them)."
        self.add(slug, amount, manual=True)
        self.app.events.emit("study_logged", subject=slug, minutes=round(amount / 60))
        return f"Logged {amount / 3600:.1f} h of {self.app.modules['subjects'].name_of(slug)}."

    # --------------------------------------------------------------------------------- paper sessions
    @property
    def session_file(self):
        return self.app.paths.state / "study" / "session.json"

    def session(self) -> dict:
        return jload(self.session_file, {}) or {}

    def start_session(self, subject: str, minutes: int | None = None) -> str:
        """A study session away from the computer (paper, library): timed until you stop it, or for `minutes`."""
        subj = self.app.modules["subjects"]
        slug = subj.resolve(subject) or (subj.find_in(subject) or [None])[0]
        if not slug:
            return f"I don't know the subject {subject!r} (Subjects lists them)."
        prev = self.stop_session() if self.session().get("subject") else ""
        jsave(self.session_file, {"subject": slug, "start": now().isoformat(), "minutes": minutes})
        self.app.scheduler.cancel(f"{self.id}:session-end")
        if minutes:
            self.app.scheduler.at(
                now() + dt.timedelta(minutes=minutes), "study.session_end", key=f"{self.id}:session-end", module=self.id
            )
        self.app.events.emit("study_session_start", subject=slug, planned=minutes)
        name = subj.name_of(slug)
        from kurooto.core import threads  # something you're in the middle of (core/threads.py)

        threads.started(self.app, f"studying {name}", key=f"study:{slug}", via="study")
        until = f" for {minutes} min (until {now() + dt.timedelta(minutes=minutes):%H:%M})" if minutes else ""
        return (f"{prev} " if prev else "") + f"{name}: session started{until}. /study stop when you're done."

    def stop_session(self, timer: bool = False) -> str:
        """End the session and log it. timer: the scheduled end or Study mode's timer stops it; a timer's session
        ended any other way (/study stop, "done studying", a new session) ends the timer too."""
        s = self.session()
        if not s.get("subject"):
            return "No study session is running."
        if s.get("timer") and not timer:
            return self.timer_reset()
        try:
            start = dt.datetime.fromisoformat(s["start"])
        except (KeyError, ValueError):
            start = now()
        secs = max(0, (now() - start).total_seconds())
        if s.get("minutes"):
            secs = min(secs, s["minutes"] * 60)  # a timed session counts at most what was planned
        self.session_file.unlink(missing_ok=True)
        if not timer:
            self.app.scheduler.cancel(f"{self.id}:session-end")
        if start.date() != now().date():  # ran past midnight: the time goes to the day it started
            self.add(s["subject"], secs, day=start.date(), manual=True)
        else:
            self.add(s["subject"], secs, manual=True)
        mins = round(secs / 60)
        self.app.events.emit("study_session_end", subject=s["subject"], minutes=mins)
        from kurooto.core import threads

        threads.finish(self.app, f"study:{s['subject']}")
        return f"{self.app.modules['subjects'].name_of(s['subject'])}: {mins} min logged."

    def _session_end(self, p: dict) -> None:
        if self.session().get("subject"):
            self.app.notify(
                f"Session done. {self.stop_session(timer=True)} Take a break.", kind="reminder", why="study.timer"
            )

    # ------------------------------------------------------------------------------- Study mode's timer
    # A focus is a session for the subject (logged when it ends, at most its length) with focus time until it ends,
    # so calls and messages wait; then a break, then the next focus waits for you. Paused, it keeps what's left. Its
    # end is scheduled (study.timer_end), so it keeps time with the dashboard closed. State: study/timer.json.
    @property
    def timer_file(self):
        return self.app.paths.state / "study" / "timer.json"

    def timer(self) -> dict:
        return jload(self.timer_file, {}) or {}

    def _length(self, key: str, default: int) -> float:
        """study.focus_min or study.break_min, in seconds (1 to 240 minutes)."""
        try:
            return max(1.0, min(240.0, float(self.setting(key) or default))) * 60
        except (TypeError, ValueError):
            return default * 60.0

    def _then(self) -> str:
        return "end" if self.setting("timer_ends_mode") else "break"

    def timer_view(self) -> dict:
        """For the page: phase ("focus", "break", or "" before a start), subject, ends (epoch seconds, while it runs)
        or left (seconds, paused), total, round, then ("break", or "end": Study mode ends with the focus)."""
        t = self.timer()
        ends, slug = t.get("ends"), t.get("subject") or ""
        return {
            "phase": t.get("phase", ""),
            "subject": slug,
            "name": self.name_of(slug) if slug else "",
            "running": bool(ends),
            "ends": dt.datetime.fromisoformat(ends).timestamp() if ends else None,
            "left": t.get("left"),
            "total": t.get("total") or self._length("focus_min", 25),
            "round": t.get("round", 0),
            "then": t.get("then") or self._then(),
        }

    def timer_start(self, subject: str | None = None) -> str:
        """Start, or go on after a pause: a focus for `subject` (or the one it had), or what's left of a break."""
        t = self.timer()
        if t.get("ends"):
            return "The timer is already running."
        subj = self.app.modules["subjects"]
        slug = (subj.resolve(subject) or (subj.find_in(subject) or [None])[0]) if subject else t.get("subject")
        if not slug:
            return f"I don't know the subject {subject!r} (Subjects lists them)." if subject else "Pick a subject."
        phase = t.get("phase") or "focus"
        total = t.get("total") or self._length("focus_min", 25)
        left = t.get("left") or total
        ends = now() + dt.timedelta(seconds=left)
        jsave(
            self.timer_file,
            {
                "phase": phase,
                "subject": slug,
                "ends": ends.isoformat(),
                "left": None,
                "total": total,
                "round": t.get("round") or 1,
                "then": t.get("then") or self._then(),
                "focus_set": self._focus_begin(slug, ends, left) if phase == "focus" else None,
            },
        )
        self.app.scheduler.at(ends, "study.timer_end", key=f"{self.id}:timer", module=self.id)
        self.app.events.emit("study_timer", act="start", phase=phase, subject=slug, minutes=round(left / 60))
        if phase == "break":
            return f"Break until {ends:%H:%M}."
        return f"{self.name_of(slug)}: focus until {ends:%H:%M}. Calls and messages wait till then."

    def _focus_begin(self, slug: str, ends: dt.datetime, seconds: float) -> str | None:
        """The focus's session (one of yours that's running ends here, logged) and focus time until it ends, unless
        something holds it longer already. Returns the focus end it set, or None."""
        s = self.session()
        if s.get("subject"):
            self.stop_session(timer=bool(s.get("timer")))
        jsave(self.session_file, {"subject": slug, "start": now().isoformat(), "minutes": seconds / 60, "timer": True})
        self.app.events.emit("study_session_start", subject=slug, planned=round(seconds / 60))
        av = self.app.availability
        held = av.focus_until()
        if held is not None and held >= ends:
            return None
        av.set_focus(ends)
        return ends.isoformat()

    def _focus_end(self, t: dict) -> str:
        """A focus is over, paused or reset: its session is logged, and the focus time it set ends (the messages that
        waited come) unless a /focus or a #focus event of yours holds longer. Returns what was logged."""
        said = self.stop_session(timer=True) if self.session().get("timer") else ""
        mine, av = t.get("focus_set"), self.app.availability
        held = av.focus_until()
        if mine and held is not None and held <= dt.datetime.fromisoformat(mine) + dt.timedelta(seconds=1):
            av.set_focus(None)
            if av.focus_until() is None:
                self.app.notifier.flush_queue()
        return said

    def timer_pause(self) -> str:
        t = self.timer()
        if not t.get("ends"):
            return "The timer isn't running."
        left = max(1, round((dt.datetime.fromisoformat(t["ends"]) - now()).total_seconds()))
        self.app.scheduler.cancel(f"{self.id}:timer")
        said = self._focus_end(t) if t.get("phase") == "focus" else ""
        jsave(self.timer_file, {**t, "ends": None, "left": left, "focus_set": None})
        self.app.events.emit("study_timer", act="pause", phase=t.get("phase"))
        return "Paused." + (f" {said}" if said else "")

    def timer_reset(self) -> str:
        t = self.timer()
        self.app.scheduler.cancel(f"{self.id}:timer")
        said = self._focus_end(t) if t.get("phase") == "focus" and t.get("ends") else ""
        self.timer_file.unlink(missing_ok=True)
        if t:
            self.app.events.emit("study_timer", act="reset", phase=t.get("phase"))
        return "Timer reset." + (f" {said}" if said else "")

    def _timer_end(self, p: dict | None = None) -> None:
        t = self.timer()
        if not t.get("ends"):
            return
        self.app.events.emit("study_timer", act="end", phase=t.get("phase"))
        if t.get("phase") == "break":  # the next focus waits for you
            total = self._length("focus_min", 25)
            nxt = {
                **t,
                "phase": "focus",
                "ends": None,
                "left": total,
                "total": total,
                "round": (t.get("round") or 1) + 1,
            }
            jsave(self.timer_file, nxt)
            self.app.notify(
                "Break's over: the next focus starts when you press start.", kind="reminder", why="study.timer"
            )
            return
        said = self._focus_end(t)
        if t.get("then") == "end":
            from kurooto.core.actions import study_mode

            self.timer_file.unlink(missing_ok=True)
            self.app.notify(f"Focus done. {said} {study_mode(self.app, False)}", kind="reminder", why="study.timer")
            return
        total = self._length("break_min", 5)
        ends = now() + dt.timedelta(seconds=total)
        jsave(self.timer_file, {**t, "phase": "break", "ends": ends.isoformat(), "total": total, "focus_set": None})
        self.app.scheduler.at(ends, "study.timer_end", key=f"{self.id}:timer", module=self.id)
        self.app.notify(f"Focus done. {said} Break until {ends:%H:%M}.", kind="reminder", why="study.timer")

    # -------------------------------------------------------------------------------- the daily note
    def write_day(self, p: dict | None = None) -> bool:
        """Put the day's hours into its daily note, once ("## Study hours"). Run late (the computer was asleep at the
        time), it writes the day it was due."""
        at = self.setting("daily_note")
        day = now().date()
        try:
            if at and now().time() < dt.time.fromisoformat(at):
                day -= dt.timedelta(days=1)
        except ValueError:
            pass
        t = self.totals(1, last=day)
        if not t or daily.has_section(self.app, "Study hours", day):
            return False
        name = self.name_of
        manual = self.day(day)
        rows = []
        for k, v in sorted(t.items(), key=lambda kv: -kv[1]):
            paper = manual.get(f"{k}|manual", 0)
            rows.append(
                f"- {name(k)}: {v / 3600:.1f} h" + (f" (away from the computer {paper / 3600:.1f} h)" if paper else "")
            )
        total = sum(t.values()) / 3600
        daily.append(self.app, "Study hours", f"{total:.1f} h in all\n\n" + "\n".join(rows), day)
        self.app.events.emit("study_day", hours=round(total, 2))
        return True

    # ------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "study",
                "study time today (/study week); /study <subject> [minutes] starts a session, /study stop ends it; "
                "/study mode on|off: the dashboard's Study mode",
                self._cmd,
            ),
            Command(
                "studied", "log study time away from the computer: /studied 2h linear algebra", lambda m, a: self.log(a)
            ),
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        a = arg.strip()
        low = a.lower()
        if not a or low in ("today", "day"):
            return self.report(1) + self._running()
        if low in ("week", "w", "7", "7d", "this week"):
            return self.report(7)
        if low in ("stop", "done", "end", "off", "finish", "finished"):
            return self.stop_session()
        mode = re.fullmatch(r"mode(?:\s+(on|off))?", low)
        if mode:  # the dashboard's Study mode (core/actions.py); "/study mode" on its own turns it on
            return self._mode(mode.group(1) != "off")
        m = re.match(r"(.+?)\s+(\d+)\s*(?:m|min|mins|minutes)?$", a)
        if m:
            return self.start_session(m.group(1), int(m.group(2)))
        mins = a_minutes(a)
        subject = re.sub(r"\bfor\b.*$", "", a).strip() if mins else a
        return self.start_session(subject, mins)

    def _mode(self, on: bool) -> str:
        from kurooto.core.actions import study_mode

        return study_mode(self.app, on)

    def _running(self) -> str:
        s = self.session()
        if not s.get("subject"):
            return ""
        return f"\nSession running: {self.app.modules['subjects'].name_of(s['subject'])} since {s['start'][11:16]}."

    def intents(self):
        subj = self.app.modules["subjects"]

        def one_subject(text: str) -> str | None:
            found = subj.find_in(text)
            return found[0] if len(found) == 1 else None

        def start(text: str):
            if another_day(text) or not re.search(
                r"^(?:i'?m |i am |ok,? |now )?(?:starting|start|beginning|begin|going to study|gonna study|studying)\b",
                text,
                re.I,
            ):
                return None
            if re.search(r"\b(?:studied|did|spent|was|were|earlier|this morning|yesterday)\b", text, re.I):
                return None
            slug = one_subject(text)
            return {"slug": slug, "mins": a_minutes(text)} if slug else None

        def stop(text: str):
            pat = (
                r"^(?:i'?m |i am )?(?:done|finished|through|stopp?(?:ed|ing)?|end(?:ed|ing)?) (?:with )?(?:the )?"
                r"(?:study(?:ing)?|session|study session)\b|^(?:study )?session (?:over|done|finished)$"
            )
            return {} if re.search(pat, text, re.I) else None

        def log(text: str):
            if another_day(text) or not re.search(r"\b(?:studied|did|spent|revised|worked on)\b", text, re.I):
                return None
            mins, slug = a_minutes(text), one_subject(text)
            return {"slug": slug, "mins": mins} if mins and slug else None

        def show(text: str):
            if not re.search(r"\bhow (?:much|long|many hours)\b.*\bstud(?:y|ied|ying)\b", text, re.I):
                return None
            return {"days": 7 if re.search(r"\b(?:this|last|the) week\b|\bweek\b", text, re.I) else 1}

        def mode(text: str):
            m = re.fullmatch(
                rf"(?:({'|'.join(MODE_ON + MODE_OFF)}) |(?:turn|switch) (?=(?:the )?study mode (?:on|off)$))?"
                r"(?:the )?study mode(?: (on|off))?",
                text.strip().lower().rstrip(".!"),
            )
            return {"on": m.group(2) != "off" and m.group(1) not in MODE_OFF} if m else None

        return [
            Intent(
                "study_mode",
                "Study mode on or off (the dashboard shows notes, the study timer and what's due)",
                mode,
                lambda m, s: self._mode(s["on"]),
                examples=("study mode on", "study mode off"),
            ),
            Intent(
                "study_start",
                "starting to study a subject (a session away from the computer)",
                start,
                lambda m, s: self.start_session(s["slug"], s["mins"]),
                examples=("starting to study la",),
            ),
            Intent(
                "study_stop",
                "done studying: end the session",
                stop,
                lambda m, s: self.stop_session(),
                examples=("done studying",),
            ),
            Intent(
                "study_log",
                "studied a subject for some time (logs it)",
                log,
                lambda m, s: self.log(f"{s['mins']}m {s['slug']}"),
                examples=("studied la for 2 hours",),
            ),
            Intent(
                "show_study",
                "how much did I study",
                show,
                lambda m, s: self.report(s["days"]) + (self._running() if s["days"] == 1 else ""),
                questions=True,
                examples=("how much did I study this week?",),
            ),
        ]

    def call_brief(self) -> dict:
        t = self.totals(1)
        return {"study_today_h": round(sum(t.values()) / 3600, 1)} if t else {}

    def call_tools(self):
        return [
            Tool(
                "log_study",
                "Log study time away from the computer (paper, library), e.g. 120 minutes of a subject.",
                lambda a: self.log(f"{a.get('minutes', 0)}m {a.get('subject', '')}"),
                {"subject": arg(), "minutes": {"type": "number"}},
                ("subject", "minutes"),
                offline="queue",
            ),
            Tool(
                "study_summary",
                "Study hours per subject today and this week.",
                lambda a: self.report(1) + "\n\n" + self.report(7),
            ),
        ]

    def weekly_lines(self) -> list[str]:
        t = self.totals(7)
        return [f"Study: {sum(t.values()) / 3600:.1f} h ({len(t)} subjects)"] if t else []
