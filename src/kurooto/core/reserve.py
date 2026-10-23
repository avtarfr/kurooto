"""The reserve: Kurooto's own state as plain Markdown files an AI program can simply open and read, because a request
that has to run a command or call a tool to learn something small (is an alarm set? what's due?) can fail on a
permission it doesn't have, and one that reads a file can't.

Files, in <state>/reserve/ (one more folder an AI may read: core/places.py):

    alarm.md        the next alarm and the daily one (written by the alarm feature as it changes)
    deadlines.md    what's due, nearest first
    calendar.md     the next two weeks of events
    settings.md     every setting that differs from its default, and which features are on (never a secret)
    addons.md       your add-ons and whether each loaded
    agent-guide.md  what an AI program may read, write and run here, the tools it has, and the chat commands
    ai-manual.md    how Kurooto works, for its AI (a copy of the shipped data/ai-manual.md)
    self.md         what Kurooto is running here: version, AIs and models, features and their health, the last day's
                    failures (core/selfdoc.py; written when it's out of date, not counted as a change here)

They're rewritten when something changes and every 10 minutes (`kurooto reserve` does it now); a file is only
written when its text changed, so nothing churns. Nothing here is ever read back by Kurooto.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

SECRET = re.compile(r"(?i)(token|secret|password|passphrase|api[_-]?key|\bkey\b|credential|cookie)")


def folder(app: App) -> Path:
    return Path(app.paths.state) / "reserve"


def stamp() -> str:
    return f"(Updated {now():%Y-%m-%d %H:%M}.)"


def deadlines_md(app: App) -> str:
    mod = app.modules.get("deadlines")
    if mod is None or not app.is_on("deadlines"):
        return "# Deadlines\n\nThe Deadlines feature is off.\n"
    rows = mod.upcoming(24 * 60)
    lines = ["# Deadlines", ""]
    if not rows:
        lines.append("Nothing is due in the next 60 days.")
    for _id, it, hours in rows:
        subj = f" ({it['subject']})" if it.get("subject") else ""
        lines.append(
            f"- {it['due'][:16]}: {it['title']}{subj}: {it.get('kind', 'task')}, in {mod._row(_id, it, hours)['when']}"
        )
    return "\n".join(lines) + "\n"


def calendar_md(app: App) -> str:
    mod = app.modules.get("calendar")
    if mod is None or not app.is_on("calendar"):
        return "# Calendar\n\nThe Calendar feature is off.\n"
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        events = mod.events(start, start + dt.timedelta(days=14))
    except (OSError, ValueError, KeyError):
        events = []
    lines = ["# Calendar", "", "The next two weeks."]
    day = None
    for e in events:
        s = e.get("start")
        s = s if isinstance(s, dt.datetime) else dt.datetime.fromisoformat(str(s))
        if s.date() != day:
            day = s.date()
            lines += ["", f"## {day:%A %d %b}"]
        lines.append(f"- {s:%H:%M} {e.get('title') or e.get('summary') or 'event'}")
    if not events:
        lines.append("\nNo events.")
    return "\n".join(lines) + "\n"


def flat(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict) and v:
            out.update(flat(v, key))
        else:
            out[key] = v
    return out


def settings_md(app: App) -> str:
    user = flat(app.settings.user())
    lines = ["# Settings", "", "What differs from the defaults (secrets are never in here).", ""]
    for k in sorted(user):
        if SECRET.search(k):
            continue
        v = json.dumps(user[k], ensure_ascii=False)
        lines.append(f"- {k} = {v[:160]}")
    on = sorted(m.id for m in app.enabled())
    lines += ["", "## Features that are on", "", ", ".join(on) or "none"]
    return "\n".join(lines) + "\n"


def addons_md(app: App) -> str:
    from kurooto.core import overlay

    st = overlay.status(app)
    lines = ["# Add-ons", ""]
    if not st.get("path"):
        lines.append("No add-ons folder is set.")
    else:
        lines.append(f"Folder: {st['path']}")
        mods = st.get("modules") or []
        lines += ["", *(f"- {m}" for m in mods)] if mods else ["", "No add-on features loaded."]
    linked = st.get("linked") or {}
    if linked:  # added by link (core/addons.py)
        lines += ["", "## Added by link", ""]
        for name, row in sorted(linked.items()):
            what = row.get("problem") or (", ".join(row.get("modules") or []) or "no features")
            lines.append(f"- {name} at {str(row.get('commit', ''))[:12]}: {what}")
    if st.get("path") or linked:
        for e in st.get("errors") or []:
            lines.append(f"- failed: {e.get('where')}: {e.get('error')}")
    return "\n".join(lines) + "\n"


def guide_md(app: App) -> str:
    from kurooto.core.places import read_roots, write_roots
    from kurooto.core.tools import agent_tools
    from kurooto.providers.agy import COMMANDS, safe_scripts

    reads = "\n".join(f"- {p}" for p in read_roots(app))
    writes = "\n".join(f"- {p}" for p in write_roots(app))
    tools = []
    for t in agent_tools(app):
        first = re.split(r"(?<=[.!?])\s", (t.description or "").strip(), maxsplit=1)[0]
        tools.append(f"- `{t.name}`: {first[:160]}")
    cmds = app.help().splitlines() if hasattr(app, "help") else []
    return "\n".join(
        [
            "# What an AI program can do here",
            "",
            "Read this instead of exploring: it is the whole answer.",
            "",
            "## It may read",
            reads,
            "",
            "## It may write",
            writes,
            "",
            "## Commands it may run",
            ", ".join(COMMANDS) + ". Never `kurooto` itself, and no inline scripts.",
            *(
                [f"Your own scripts (full path): {', '.join(str(f) for f, _ in safe_scripts(app))}."]
                if safe_scripts(app)
                else []
            ),
            "",
            "## Kurooto's tools (already connected; call them, don't look for them)",
            *tools,
            "",
            "## Files that already hold the state (open them; no command needed)",
            f"- {folder(app) / 'alarm.md'}: alarms",
            f"- {folder(app) / 'deadlines.md'}: what's due",
            f"- {folder(app) / 'calendar.md'}: the next two weeks",
            f"- {folder(app) / 'settings.md'}: settings and which features are on",
            f"- {folder(app) / 'addons.md'}: your add-ons",
            f"- {folder(app) / 'self.md'}: what Kurooto is running (version, AIs and models, features and their "
            "health, the last day's failures): read it for any question about Kurooto itself",
            f"- {folder(app) / 'ai-manual.md'}: how Kurooto works and what you may and may not do",
            "",
            "## Chat commands",
            *[f"    {ln}" for ln in cmds[:80]],
            "",
        ]
    )


BUILDERS = {
    "deadlines.md": deadlines_md,
    "calendar.md": calendar_md,
    "settings.md": settings_md,
    "addons.md": addons_md,
    "agent-guide.md": guide_md,
    "ai-manual.md": lambda app: _manual(),
}


def _manual() -> str:
    from kurooto.core.selfdoc import manual_text

    return manual_text()


def start(app: App) -> None:
    """At start, and then every 10 minutes: bring the reserve files up to date (in the background)."""
    import threading

    app.scheduler.action("reserve.refresh", lambda p: refresh(app))
    app.scheduler.every("reserve:refresh", "every 10m", "reserve.refresh", misfire="coalesce")
    threading.Thread(target=refresh, args=(app,), name="reserve", daemon=True).start()


def write_if_changed(path: Path, text: str) -> bool:
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return True
    except OSError:
        return False


def refresh(app: App) -> list[str]:
    """Write every reserve file whose text changed; returns their names. One failing builder never stops the rest."""
    changed = []
    for name, build in BUILDERS.items():
        try:
            text = build(app)
        except Exception as e:  # a feature in a bad state mustn't stop the others being written
            text = f"# {name}\n\nCouldn't be written: {type(e).__name__}.\n"
        if write_if_changed(folder(app) / name, text):
            changed.append(name)
    from kurooto.core import selfdoc  # self.md: written when out of date (it carries its own time)

    selfdoc.refresh(app)
    return changed
