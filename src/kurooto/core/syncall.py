"""Sync everything: every sync that's on, in one go, with one line each when it's done.

/sync all (or "sync everything") on Telegram, `kurooto sync` in a terminal. In order: your notes with your repository
(to take in what changed elsewhere), Google Classroom, your calendars, research project logs, your notes again (to
send up what the others just wrote), then the notes brain's index. A feature that's off is left out. It runs in the
background; the summary comes as a message.

A feature joins in by having a `sync_now() -> (ok, detail)` method; the ones below that don't are called the way their
own timers call them.
"""

from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING

from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

ORDER = [  # (module id, what to call it)
    ("notes_sync", "Notes"),
    ("google", "Classroom"),
    ("calendar", "Calendar"),
    ("research", "Research"),
    ("gbrain", "Notes brain"),
]
ASK = re.compile(
    r"^(?:please\s+)?(?:/sync\s+(?:all|everything)|sync\s+(?:everything|all(?:\s+the\s+things)?|it\s+all)"
    r"(?:\s+now)?)\s*[.!]*$",
    re.I,
)
_lock = threading.Lock()


def wanted(text: str) -> bool:
    """Is this message asking to sync everything?"""
    return bool(ASK.match(text.strip()))


def _one(app: App, mid: str) -> tuple[bool | None, str]:
    m = app.modules.get(mid)
    own = getattr(m, "sync_now", None)
    if own:
        return own()
    if mid == "notes_sync":
        return m.sync()
    if mid == "google":
        r = m.classroom_sync()
        if r.get("skipped"):
            return None, "Classroom isn't on"
        if r.get("error"):
            return False, str(r["error"])
        return True, f"{r.get('deadlines', 0)} assignments, {r.get('posts', 0)} new posts"
    if mid == "calendar":
        n = m.refresh()
        return True, f"{n} events"
    if mid == "gbrain":
        return m.sync()
    return None, "nothing to do"


def steps(app: App) -> list[tuple[str, str]]:
    """What a sync would run now: the features in ORDER that are on, then any other feature that's on and has
    sync_now()."""
    known = {mid for mid, _ in ORDER}
    out = [(mid, label) for mid, label in ORDER if app.is_on(mid)]
    for m in app.enabled():
        if m.id not in known and hasattr(m, "sync_now"):
            out.append((m.id, m.title))
    return out


def run(app: App) -> list[tuple[str, bool | None, str]]:
    """Run every sync that's on, one after another. Returns (label, ok, detail) per feature; ok None = skipped."""
    todo = steps(app)
    results: dict[str, tuple[str, bool | None, str]] = {}
    for mid, label in todo:
        results[mid] = (label, *_safe(app, mid))
    if "notes_sync" in results and results["notes_sync"][1] and len(todo) > 1:
        results["notes_sync"] = ("Notes", *_safe(app, "notes_sync"))  # send up what the others wrote
    out = [results[mid] for mid, _ in todo]
    app.events.emit("sync_all", ok=sum(1 for _, ok, _ in out if ok), failed=sum(1 for _, ok, _ in out if ok is False))
    return out


def _safe(app: App, mid: str) -> tuple[bool | None, str]:
    try:
        ok, detail = _one(app, mid)
        return ok, (detail or ("done" if ok else "failed")).strip()[:200]
    except Exception as e:  # one failing sync never stops the others
        return False, f"{type(e).__name__}: {e}"[:200]


def summary(results: list[tuple[str, bool | None, str]]) -> str:
    if not results:
        return "Nothing to sync: notes sync, Classroom, calendar, research and the notes brain are all off."
    good = sum(1 for _, ok, _ in results if ok)
    bad = sum(1 for _, ok, _ in results if ok is False)
    head = "Synced everything that's on" + (f" ({good} ok, {bad} failed):" if bad else ":")
    word = {True: "ok", False: "failed", None: "skipped"}
    return head + "\n" + "\n".join(f"{label}: {word[ok]}, {detail}" for label, ok, detail in results)


def status(app: App) -> dict:
    return jload(app.paths.state / "sync-all.json", {}) or {}


def start(app: App, notify: bool = True) -> tuple[bool, str]:
    """Start a sync in the background. (False, why) if one is already running or there's nothing to sync."""
    todo = steps(app)
    if not todo:
        return False, summary([])
    if not _lock.acquire(blocking=False):
        return False, "A sync is already running; you'll get its summary."
    f = app.paths.state / "sync-all.json"
    jsave(f, {"running": True, "started": time.time(), "lines": []})

    def work():
        try:
            res = run(app)
            text = summary(res)
            jsave(f, {"running": False, "started": status(app).get("started"), "finished": time.time(), "text": text})
            if notify:
                app.notify(text, kind="result")
        except Exception as e:
            jsave(f, {"running": False, "finished": time.time(), "text": f"The sync stopped: {e}"[:300]})
        finally:
            _lock.release()

    threading.Thread(target=work, name="sync-all", daemon=True).start()
    names = ", ".join(label for _, label in todo)
    return True, f"Syncing {names}. I'll send one line each when it's done."
