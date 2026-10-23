"""Where you are in setup: each step of the setup page finished, skipped for now, or not yet (state/setup.json).

The setup page (web/static/setup.js) says when you leave a step (Next, Back, Skip for now, a step in the list, or
closing the page) and how long you were on it. Reopening /setup, or `kurooto setup`, lands on the first step that isn't
finished, with the others marked and open to visit again. The first step (You) and the AI have no Skip for now: setup
can't finish without them, and `kurooto doctor` already counts a missing AI as a problem. The other steps can be
skipped; a skipped step is listed on the dashboard (Features: Finish setting up) and in `kurooto doctor` as a note,
each with the way back to it, until it's finished (Telegram paired later on the dashboard takes the Chat step off).

What's recorded, per step: finished / skipped / open, the seconds spent on it, how many times it was opened, and when
it was last left. Never what you typed. It stays on this computer; `kurooto doctor --bundle` puts it in the zip
(setup.json), which is only ever saved here for you to look at and send yourself.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

STEPS = ("you", "computer", "brain", "about", "features", "telegram", "finish")
TITLES = {  # as the setup page's list says them (setup.js LABELS)
    "you": "You",
    "computer": "Computer",
    "brain": "AI",
    "about": "About you",
    "features": "Features",
    "telegram": "Chat",
    "finish": "Done",
}
# what's left to do when a step was skipped, in words (the dashboard and doctor)
WHAT = {
    "computer": "what this computer suits, its colours and what to do on battery",
    "about": "teach it what your other AI accounts know about you",
    "features": "pick what it does for you (what was ticked is on)",
    "telegram": "connect Telegram, or pair the phone app",
}
REQUIRED = ("you", "brain", "finish")  # no Skip for now
MAX_VISIT = 3600  # seconds counted for one visit at most: a page left open overnight isn't stalling
_lock = threading.Lock()


def _file(app: App):
    return app.paths.state / "setup.json"


def load(app: App) -> dict:
    data = jload(_file(app), {}) or {}
    steps = data.get("steps") if isinstance(data.get("steps"), dict) else {}
    return {**data, "steps": {k: v for k, v in steps.items() if k in STEPS and isinstance(v, dict)}}


def finished(app: App, step: str) -> bool | None:
    """Whether a step's work is done, from what's known now; None for steps that have nothing to check."""
    if step == "brain":
        from kurooto import providers

        main = app.settings.get("brain.main")
        b = providers.build(app, main) if main else None
        return bool(b and b.available()[0])
    if step == "about":
        return bool(app.about.profile_file.exists() or app.about.reports())
    if step == "telegram":
        tg, calls = app.modules.get("telegram"), app.modules.get("calls")
        if tg is not None and tg.ready()[0]:
            return True
        return app.settings.get("setup.channel") == "app" and calls is not None and calls.ready()[0]
    return None


def record(app: App, step: str, how: str, seconds: float = 0, chosen: list | None = None) -> dict:
    """Leaving a step. how: "next" (finished, or skipped/open if its work isn't done), "skip", or "leave" (Back, the
    list, closing the page: what it was stays). Raises ValueError for an unknown step, or skipping a required one."""
    if step not in STEPS:
        raise ValueError(f"not a setup step: {step}")
    if how not in ("next", "skip", "leave"):
        raise ValueError("how: next, skip or leave")
    if how == "skip" and step in REQUIRED:
        raise ValueError(f"{TITLES[step]} can't be skipped: setup can't finish without it")
    with _lock:
        data = load(app)
        row = dict(data["steps"].get(step) or {})
        if how == "leave":
            row.setdefault("status", "open")
        else:
            done = finished(app, step)
            if done is not False and (how == "next" or done):
                row["status"] = "done"
            else:
                row["status"] = "open" if step in REQUIRED else "skipped"
        try:
            secs = max(0.0, min(float(seconds or 0), MAX_VISIT))
        except (TypeError, ValueError):
            secs = 0.0
        row["seconds"] = round(float(row.get("seconds") or 0) + secs, 1)
        row["visits"] = int(row.get("visits") or 0) + 1
        row["left_at"] = int(time.time())
        data["steps"][step] = row
        if isinstance(chosen, list):
            data["chosen"] = [str(x) for x in chosen if str(x) in app.modules][:100]
        jsave(_file(app), data)
    return view(app)


def finish(app: App) -> None:
    """Finish setup was pressed (POST setup/done). A step that can be skipped and wasn't finished counts as skipped
    now (never opened, or Telegram left unconnected); one opened with nothing to check (Features: its ticks went on
    with Finish) counts as done. The AI isn't touched: doctor says when it doesn't work."""
    with _lock:
        data = load(app)
        for s in STEPS:
            row = dict(data["steps"].get(s) or {})
            if s == "finish":
                row["status"], row["left_at"] = "done", int(time.time())
            elif s not in REQUIRED and row.get("status") not in ("done", "skipped"):
                done = finished(app, s)
                row["status"] = "done" if done or (done is None and row.get("status") == "open") else "skipped"
            else:
                continue
            data["steps"][s] = row
        jsave(_file(app), data)


def status(app: App, data: dict | None = None) -> dict[str, str]:
    """Each step's state now: done, skipped, open or "" (not reached). A skipped step whose work got done since
    (Telegram paired on the dashboard) counts as done."""
    data = data if data is not None else load(app)
    out = {}
    for s in STEPS:
        st = (data["steps"].get(s) or {}).get("status") or ""
        if st == "skipped" and finished(app, s):
            st = "done"
        out[s] = st
    return out


def resume(app: App, data: dict | None = None) -> str:
    """Where reopening the setup page lands: the first step not finished (nor skipped), else the first skipped one,
    else the start (setup done: you're revisiting)."""
    st = status(app, data)
    return (
        next((s for s in STEPS if st[s] not in ("done", "skipped")), None)
        or next((s for s in STEPS if st[s] == "skipped"), None)
        or STEPS[0]
    )


def left(app: App, data: dict | None = None) -> list[dict]:
    """The steps skipped for now and not done since: the dashboard's Finish setting up, and doctor's notes."""
    st = status(app, data)
    skipped = [s for s in STEPS if st[s] == "skipped"]
    return [{"id": s, "title": TITLES[s], "what": WHAT.get(s, ""), "link": f"/setup#{s}"} for s in skipped]


def view(app: App) -> dict:
    """For the setup page and the dashboard (GET /api/setup, and in /api/state)."""
    data = load(app)
    st = status(app, data)
    return {
        "steps": {s: {**(data["steps"].get(s) or {}), "status": st[s]} for s in STEPS},
        "resume": resume(app, data),
        "left": left(app, data),
        "required": list(REQUIRED),
        "chosen": data.get("chosen"),
    }


def doctor_rows(app: App) -> list[tuple[str, bool | None, str]]:
    """`kurooto doctor`: a note (never a problem) for each skipped step, with the way back to it."""
    return [
        (f"setup: {x['title']}"[:60], None, f"skipped for now: {x['what']}. Finish it: kurooto setup {x['id']}")
        for x in left(app)
    ]


def timings(app: App) -> dict:
    """For `kurooto doctor --bundle`: where setup went quickly and where it stalled. Steps and seconds only."""
    data = load(app)
    return {
        "setup_done": bool(app.settings.get("setup.done")),
        "steps": [
            {
                "step": s,
                "status": (data["steps"].get(s) or {}).get("status") or "",
                "seconds": (data["steps"].get(s) or {}).get("seconds") or 0,
                "visits": (data["steps"].get(s) or {}).get("visits") or 0,
            }
            for s in STEPS
        ],
    }
