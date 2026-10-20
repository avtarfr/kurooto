"""Coming from an older version: what changes once, at the first start of a new version (state/upgrades.json keeps
it to once).

0.2.0, for installs that were set up with 0.1: where 0.2.0 would start something new on its own (a browser tab at
the alarm, an AI plan before it, a call six hours before a deadline, deadlines taken from the calendar, more rings
for an unanswered call, AI study logs after class, your journal and call transcripts read by the nightly look back),
those settings are set to off, unless you had set them yourself. Deadlines already overdue and research projects
already quiet aren't asked about all at once on the first day, and a short "What's new" message comes once.
New installs keep 0.2.0's defaults.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

MARKER = "upgrades.json"
MANUAL = "https://github.com/avtarfr/kurooto/blob/main/docs/MANUAL.md"
KEEP_0_1 = {  # 0.1's behaviour for those who had it
    "alarm.open_page": False,
    "alarm.prep_min": None,
    "capture.study_log": False,
    "retro.transcripts": False,
    "retro.journal": False,
    "deadlines.call": False,
    "deadlines.from_calendar": False,
    "calls.realert_min": [3],
}
WHATS_NEW = (
    "Kurooto 0.2.0: what's new\n"
    "- Your AI can act for you: reminders, notes, calls and questions, from any chat.\n"
    "- Skills: ready-made routines like a morning plan or a study log (/skills).\n"
    "- Questions and approvals reach your phone; answer there or here.\n"
    "- Check-ins: an evening debrief, and a night call if you want one.\n"
    "- Google add-ons (Classroom notes, a mail digest), backups and profile sync.\n"
    "- Your About-you profile is editable, and the pages have a new green look.\n"
    f"New features stay off until you turn them on in Settings. The manual: {MANUAL}"
)


def _has(raw: dict, dotted: str) -> bool:
    """You set this yourself (it's in your settings.json, not only a default)."""
    cur = raw
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    return True


def run(app: App) -> str:
    """At start, before the features start. "upgraded" (from 0.1, once), "fresh" (a new install), or ""."""
    app.scheduler.action("upgrade.whats_new", lambda p: whats_new(app))
    f = app.paths.state / MARKER
    done = jload(f, {}) or {}
    if "0.2.0" in done:
        return ""
    raw = app.settings.user()
    setup = raw.get("setup") if isinstance(raw.get("setup"), dict) else {}
    mods = raw.get("modules") if isinstance(raw.get("modules"), dict) else {}
    if not (setup.get("done") or mods.get("enabled")):  # a new install: 0.2.0's defaults stay
        jsave(f, {**done, "0.2.0": {"at": time.time(), "fresh": True}})
        return "fresh"
    changed = [k for k in KEEP_0_1 if not _has(raw, k)]
    for k in changed:
        app.settings.set(k, KEEP_0_1[k])
    overdue = app.modules["deadlines"].quiet_overdue() if "deadlines" in app.modules else 0
    if "research" in app.modules:
        app.modules["research"].quiet_idle_once()
    app.scheduler.at(time.time() + 90, "upgrade.whats_new", key="upgrade:whats_new", grace_s=7 * 86400)
    jsave(f, {**done, "0.2.0": {"at": time.time(), "set": changed, "overdue_quiet": overdue}})
    app.events.emit("upgraded", to="0.2.0", settings=len(changed), overdue_quiet=overdue)
    return "upgraded"


def whats_new(app: App) -> None:
    app.notify(WHATS_NEW, kind="update", why="updates.whats_new")
