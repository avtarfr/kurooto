"""The activity stream (Brain, 0.8.0 stage 13, opt-in: `mind.senses.activity`): what you are working on, as shapes.

Every minute: the active window's application class (when it changes), the window title only as a salted hash, the
terminal's folder (relative to a known project, else a hash), files saved in known project folders and git commits there
(a path relative to the project; the commit message as a hash). A browser in front is reduced to a category (docs,
video, social, web) from a small local list and the title is dropped.

Never collected: keystrokes, screen contents, URLs. Raw events live 7 days (senses/store.py); after that only daily
totals ("2 h on glacier-flow, 40 min reading"). It is never used to audit you: the gate removes any sentence that checks
what you said you did against it (mind/gate.py AUDIT). The salt is a random file of its own (0600); a hash can't be
turned back into a title.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.mind.senses import store

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-activity.json"
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", "build", "dist"}
WALK_MAX = 4000
BROWSERS = {
    "firefox",
    "chromium",
    "google-chrome",
    "chrome",
    "brave-browser",
    "brave",
    "safari",
    "msedge",
    "zen",
    "librewolf",
}
CATEGORIES = {
    "docs": ("docs", "documentation", "wikipedia", "stack overflow", "stackexchange", "arxiv", "manual", "reference"),
    "video": ("youtube", "netflix", "twitch", "prime video", "vimeo", "hotstar"),
    "social": ("reddit", "twitter", "instagram", "facebook", "whatsapp", "linkedin", "discord", "telegram", "x.com"),
}

register_defaults(
    "mind", {"senses": {"activity": False}}
)  # opt-in: window classes, hashed titles, saves and commits in projects


def on(app: App) -> bool:
    return mind.on(app) and bool(app.settings.get("mind.senses.activity"))


def salt(app: App) -> bytes:
    f = app.paths.state / "mind-senses" / "salt"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(os.urandom(32))
        f.chmod(0o600)
    return f.read_bytes()


def hashed(app: App, text: str) -> str:
    return hmac.new(salt(app), text.encode(), hashlib.sha256).hexdigest()[:10]


def browser_category(title: str) -> str:
    t = title.lower()
    return next((c for c, ws in CATEGORIES.items() if any(w in t for w in ws)), "web")


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=3, check=False).stdout.strip()  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        return ""


def active_window() -> tuple[str, str, int | None] | None:
    """(application class, title, pid) of the window in front, or None where this system can't say."""
    import json
    import sys

    if sys.platform == "darwin":
        name = _run(
            ["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true']
        )
        return (name.lower(), "", None) if name else None
    if os.name == "nt":
        try:
            import ctypes

            u = ctypes.windll.user32
            h = u.GetForegroundWindow()
            n = u.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, buf, n + 1)
            pid = ctypes.c_ulong()
            u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            import psutil

            return psutil.Process(pid.value).name().lower().removesuffix(".exe"), buf.value, pid.value
        except Exception:
            return None
    if shutil.which("hyprctl"):
        try:
            w = json.loads(_run(["hyprctl", "activewindow", "-j"]) or "{}")
            if w.get("class"):
                return str(w["class"]).lower(), str(w.get("title") or ""), w.get("pid")
        except ValueError:
            return None
    if shutil.which("xdotool"):
        cls = _run(["xdotool", "getactivewindow", "getwindowclassname"])
        if cls:
            pid = _run(["xdotool", "getactivewindow", "getwindowpid"])
            return (
                cls.lower(),
                _run(["xdotool", "getactivewindow", "getwindowname"]),
                int(pid) if pid.isdigit() else None,
            )
    return None


def roots(app: App) -> dict[str, Path]:
    """Known project folders: the lab's, and repositories added as projects."""
    out: dict[str, Path] = {}
    try:
        from kurooto.mind.lab import runner

        out.update(runner.projects(app))
        from kurooto.core import repoproject

        for r in repoproject.records(app).values():
            p = Path(r.get("path") or "")
            if p.is_dir():
                out.setdefault(runner.slug(p.name), p)
    except Exception:  # noqa: S110 (no projects known is fine)
        pass
    return out


def project_of(app: App, path: str) -> tuple[str, str] | None:
    """(project, path relative to it) when `path` is inside a known project."""
    for slug, root in roots(app).items():
        try:
            return slug, str(Path(path).resolve().relative_to(root.resolve()))
        except ValueError:
            continue
    return None


def terminal_cwd(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        import psutil

        p = psutil.Process(pid)
        kids = p.children(recursive=True)
        return (kids[-1] if kids else p).cwd()
    except Exception:
        return None


def _st(app: App) -> dict:
    return jload(app.paths.state / FILE, {}) or {}


def tick(app: App) -> dict | None:
    """The minute's sample: the window (an event when it changes, a minute either way) and the terminal's folder."""
    if not on(app):
        return None
    w = active_window()
    if not w:
        return None
    cls, title, pid = w
    st, now = _st(app), time.time()
    day = time.strftime("%Y-%m-%d")
    target = cls
    if cls in BROWSERS:
        target = f"browser:{browser_category(title)}"  # the title is dropped
    elif title:
        store.add(app, "activity", "title", hashed(app, title), t=now)
    if st.get("last") != target:
        store.add(app, "activity", "window", target, t=now)
        st["last"] = target
    store.bump(app, day, "activity", f"min:{target}", 1)
    cwd = (
        terminal_cwd(pid)
        if any(t in cls for t in ("kitty", "alacritty", "terminal", "wezterm", "foot", "konsole", "iterm"))
        else None
    )
    if cwd:
        pr = project_of(app, cwd)
        label = f"{pr[0]}/{pr[1]}" if pr else hashed(app, cwd)
        if st.get("cwd") != label:
            store.add(app, "activity", "cwd", label, t=now)
            st["cwd"] = label
        if pr:
            store.bump(app, day, "activity", f"project:{pr[0]}", 1)
    jsave(app.paths.state / FILE, st)
    return {"window": target}


def poll(app: App) -> int:
    """Files saved and commits made in known projects since the last poll (every few minutes)."""
    if not on(app):
        return 0
    st, now, n = _st(app), time.time(), 0
    since = float(st.get("polled") or now - 300)
    day = time.strftime("%Y-%m-%d")
    for slug, root in roots(app).items():
        seen = 0
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP]
            for f in fn:
                seen += 1
                if seen > WALK_MAX:
                    break
                try:
                    if (Path(dp) / f).stat().st_mtime >= since:
                        store.add(app, "activity", "save", f"{slug}/{Path(dp, f).relative_to(root)}", t=now)
                        store.bump(app, day, "activity", f"saves:{slug}", 1)
                        n += 1
                except OSError:
                    continue
        if (root / ".git").exists() and shutil.which("git"):
            out = _run(["git", "-C", str(root), "log", f"--since=@{int(since)}", "--format=%s"])
            for msg in filter(None, out.splitlines()):
                store.add(app, "activity", "commit", f"{slug}:{hashed(app, msg)}", t=now)
                store.bump(app, day, "activity", f"commits:{slug}", 1)
                n += 1
    st["polled"] = now
    jsave(app.paths.state / FILE, st)
    return n


def today(app: App) -> str:
    t = store.totals(app, "activity", time.strftime("%Y-%m-%d"))
    if not t:
        return "nothing yet today"
    mins = sorted(((v, k[4:]) for k, v in t.items() if k.startswith("min:")), reverse=True)[:5]
    proj = sorted(((v, k[8:]) for k, v in t.items() if k.startswith("project:")), reverse=True)[:3]
    parts = [f"{int(v)} min in {k}" for v, k in mins] + [f"{int(v)} min on {k}" for v, k in proj]
    parts += [
        f"{int(v)} {k.split(':')[0]} in {k.split(':', 1)[1]}"
        for k, v in t.items()
        if k.startswith(("saves:", "commits:"))
    ]
    return "; ".join(parts)


TITLE_AUDIT = re.compile(r"\byou (said|told me|promised) you (studied|worked|would|were going to)\b", re.I)
