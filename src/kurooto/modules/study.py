"""Study tracker: how long you spend on each subject, counted from the window you're working in. A window whose title
names one of your subjects (its name or a short name you gave it in Subjects, e.g. a PDF called "linear-algebra-
week3.pdf", or a note in that subject's folder) counts for that subject, while you're active (not idle for 5
minutes). Only the minutes per subject are kept, never window titles.

Time away from the computer (library, paper): "/studied 2h linear algebra", or tell it on a call. /study shows today
and this week. Works on Windows, macOS (it asks once for permission to see window titles) and Linux on X11,
Hyprland or Sway; other Linux desktops can only log by hand.
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
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults("study", {"sample_s": 30, "idle_min": 5, "keywords": {}})  # keywords: {subject slug: [words]}


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


def idle_seconds() -> float | None:
    if sys.platform == "win32":

        class LastInput(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        li = LastInput()
        li.cbSize = ctypes.sizeof(li)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000
        return None
    if sys.platform == "darwin":
        m = re.search(r'"HIDIdleTime" = (\d+)', _run(["ioreg", "-c", "IOHIDSystem"]))
        return int(m.group(1)) / 1e9 if m else None
    if shutil.which("xprintidle"):
        v = _run(["xprintidle"])
        return int(v) / 1000 if v.isdigit() else None
    return None


class Study(Module):
    id = "study"
    title = "Study tracker"
    description = "Minutes per subject from the window you're working in, plus what you log by hand; /study."
    requires = ("subjects",)
    privacy = "Window titles are read on this computer and thrown away; only minutes per subject are kept."

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
        idle = idle_seconds()
        if idle is not None and idle > (self.setting("idle_min") or 5) * 60:
            return None
        title = active_title()
        slug = self.subject_of(title) if title else None
        if slug:
            self.add(slug, seconds)
        return slug

    # ------------------------------------------------------------------------------------- telling you
    def totals(self, days: int = 1) -> dict[str, float]:
        out: dict[str, float] = {}
        for i in range(days):
            for k, v in self.day(now().date() - dt.timedelta(days=i)).items():
                slug = k.split("|")[0]
                out[slug] = out.get(slug, 0) + v
        return out

    def report(self, days: int = 1) -> str:
        t = self.totals(days)
        if not t:
            return "No study time counted yet." if days == 1 else "No study time counted this week."
        name = self.app.modules["subjects"].name_of
        rows = [f"{name(k)}: {v / 3600:.1f} h" for k, v in sorted(t.items(), key=lambda kv: -kv[1])]
        head = "Today" if days == 1 else f"Last {days} days"
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
        self.app.events.emit("study_logged", minutes=round(amount / 60))
        return f"Logged {amount / 3600:.1f} h of {self.app.modules['subjects'].name_of(slug)}."

    def commands(self):
        return [
            Command(
                "study",
                "study time today (/study week for 7 days)",
                lambda m, a: self.report(7 if a.strip().lower().startswith("w") else 1),
            ),
            Command(
                "studied", "log study time away from the computer: /studied 2h linear algebra", lambda m, a: self.log(a)
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
