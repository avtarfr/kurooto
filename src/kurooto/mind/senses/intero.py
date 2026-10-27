"""Interoception (Brain, 0.8.0 stage 13): Kurooto's sense of its own machine, on by default with Brain.

Every minute (the scheduler's finest step): CPU and GPU temperature, graphics memory used, memory and swap, battery and
charging, free disk, how much of the cloud AI limits is left, whether an AI provider is at its limit, whether the call
line is connected, and how many AI requests wait. They go to the workspace as bids when something is off (a hot
computer, a low battery, a limit reached) and the share that is fine is the `health` variable's input (mind/measure.py).

The learned sensorimotor model: which of *its own* actions move *its own* body (running the lab raises the temperature,
a training run fills graphics memory). `observe(action, before, after)` keeps a running mean change per action and body
variable; `expected(action, var)` is what scheduling asks ("would this heat it up?"). Its targets are body variables
only (I-14): `learn` refuses anything else, and nothing about you (phone sensors, the activity stream) is a target.

The job gate (0.8.14, `mind.yield.on`, on with Brain): before the Brain's own heavy work starts (the lab, play, plans,
the model of your mind's sync, Dreaming, the fine-tune), `ok(app, cost)` asks the body. Cost "gpu" or "cpu" waits while
your own work holds the graphics card (a process on it that isn't Kurooto's, from nvidia-smi), during a call, on
battery, or when the work would heat the computer past HOT_C (`would_overheat`); "light" waits only while it's hot.
`gated()` runs the work or keeps it, and `retry()` (every 5 minutes) starts it once the body allows, for up to
PENDING_H hours. With `mind.yield.prefer_sleep` (on) the nightly work also waits for Kurooto's sleep (mind/sleep.py)
until that night's window ends. What you ask for yourself is never deferred: it doesn't come through here. The
measure: contention minutes, a minute in which the Brain's heavy work ran while your own work held the card, kept per
day for 30 days and shown on /mind with the deferrals.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-intero.json"
BODY_VARS = (
    "cpu_temp_c",
    "gpu_temp_c",
    "vram_used_gb",
    "ram_pct",
    "swap_pct",
    "battery_pct",
    "disk_free_gb",
    "queue_depth",
)
HISTORY = 120
HOT_C = 85.0

register_defaults("mind", {"senses": {"intero": True}})  # its own machine's state, every minute (on with Brain)
register_defaults(
    "mind",
    {
        "yield": {
            "on": True,  # the Brain's own heavy work waits for the computer: your GPU jobs, calls, battery, heat
            "prefer_sleep": True,  # its nightly work also waits for Kurooto's sleep (until that night's window ends)
        }
    },
)
COSTS = ("gpu", "cpu", "light")
SHARED_GPU = ("ollama",)  # a model server Kurooto shares: what it holds on the card isn't your own job
FOREIGN_MB = 256  # a process holding less of the card than this doesn't count
PENDING_H = 12  # deferred work is given up after this long (it comes again at its next time)
KEEP_DAYS = 30


def on(app: App) -> bool:
    return mind.on(app) and bool(app.settings.get("mind.senses.intero"))


def _num(x) -> float | None:
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _gpu() -> dict:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {}
    try:
        r = subprocess.run(  # noqa: S603
            [exe, "--query-gpu=temperature.gpu,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        t, m = r.stdout.strip().splitlines()[0].split(",")
        return {"gpu_temp_c": _num(t), "vram_used_gb": round((_num(m) or 0) / 1024, 2)}
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return {}


def sample(app: App) -> dict:
    """The body now: {variable: number}, plus `at`. Only what this computer can say; a missing sensor is absent."""
    import psutil

    out: dict = {"at": time.time()}
    try:
        temps = [
            t.current
            for ts in (getattr(psutil, "sensors_temperatures", lambda: {})() or {}).values()
            for t in ts
            if t.current
        ]
        if temps:
            out["cpu_temp_c"] = round(max(temps), 1)
    except Exception:  # noqa: S110 (a sensor that fails is simply not there)
        pass
    out.update({k: v for k, v in _gpu().items() if v is not None})
    out["ram_pct"] = psutil.virtual_memory().percent
    try:
        out["cpu_pct"] = psutil.cpu_percent(
            interval=None
        )  # since the last call: the minute's load (0.8.8, stimulation)
    except Exception:  # noqa: S110
        pass
    out["swap_pct"] = psutil.swap_memory().percent
    b = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if b is not None:
        out["battery_pct"], out["charging"] = round(b.percent), bool(b.power_plugged)
    try:
        du = shutil.disk_usage(app.paths.state)
        out["disk_free_gb"] = round(du.free / 2**30, 1)
        out["disk_free_pct"] = round(100.0 * du.free / du.total, 1) if du.total else 100.0
    except OSError:
        pass
    try:
        out["queue_depth"] = len(app.jobs.active())
    except Exception:
        out["queue_depth"] = 0
    try:
        calls = app.modules.get("calls")
        if calls is not None and app.is_on("calls"):
            out["line_connected"] = bool(calls.connector.connected)
    except Exception:  # noqa: S110
        pass
    try:
        rows = app.quota.report()
        out["quota_used_pct"] = max((r.get("pct") or 0 for r in rows), default=0)
        out["limit_hit"] = any(r.get("until") for r in rows)
    except Exception:  # noqa: S110
        pass
    return out


def tick(app: App) -> dict | None:
    """One sampling: kept in the state file (a short history), and the change an action caused is learned."""
    if not on(app):
        return None
    s = sample(app)
    st = jload(app.paths.state / FILE, {}) or {}
    hist = [*(st.get("history") or []), s][-HISTORY:]
    st["history"] = hist
    st.setdefault("model", {})
    if len(hist) >= 2:
        for action in current_actions(app):
            observe(st, action, hist[-2], hist[-1])
    jsave(app.paths.state / FILE, st)
    return s


def current_actions(app: App) -> list[str]:
    """Which of its own big actions is running now (for the model): the lab's batch, an AI request, a training run."""
    out = []
    try:
        if (app.paths.state / "lab").is_dir() and any((app.paths.state / "lab").glob("*/queue.json")):
            out.append("lab")
        if any(j.status == "running" for j in app.jobs.active()):
            out.append("ai_request")
    except Exception:  # noqa: S110
        pass
    return out


def observe(st: dict, action: str, before: dict, after: dict) -> None:
    """Fold one observed change into the model: a running mean per (action, body variable)."""
    m = st.setdefault("model", {}).setdefault(action, {})
    for v in BODY_VARS:
        a, b = _num(before.get(v)), _num(after.get(v))
        if a is None or b is None:
            continue
        e = m.setdefault(v, {"n": 0, "mean": 0.0})
        e["n"] += 1
        e["mean"] += ((b - a) - e["mean"]) / e["n"]


def learn(st: dict, action: str, var: str, delta: float) -> bool:
    """Teach the model one effect directly. Only a body variable can be a target (I-14)."""
    if var not in BODY_VARS:
        return False
    m = st.setdefault("model", {}).setdefault(action, {})
    e = m.setdefault(var, {"n": 0, "mean": 0.0})
    e["n"] += 1
    e["mean"] += (float(delta) - e["mean"]) / e["n"]
    return True


def expected(app: App, action: str, var: str) -> float | None:
    """The change this action usually makes to this body variable, if it has been seen enough (3 times)."""
    e = ((jload(app.paths.state / FILE, {}) or {}).get("model", {}).get(action) or {}).get(var)
    return round(e["mean"], 3) if e and e["n"] >= 3 else None


def would_overheat(app: App, action: str, s: dict | None = None) -> bool:
    """Would this action take the computer past HOT_C, from now (`s`, else a fresh sample) and what it usually adds?"""
    s = s or sample(app)
    d = expected(app, action, "cpu_temp_c") or 0.0
    return (s.get("cpu_temp_c") or 0) + max(d, 0) >= HOT_C


def fine(s: dict) -> float:
    """The share of the checks that are fine (for `health`)."""
    checks = []
    if "cpu_temp_c" in s:
        checks.append(s["cpu_temp_c"] < HOT_C)
    if "battery_pct" in s:
        checks.append(s["battery_pct"] > 15 or bool(s.get("charging")))
    if "disk_free_gb" in s:
        checks.append(s["disk_free_gb"] > 2)
    checks.append(s.get("swap_pct", 0) < 80)
    if "line_connected" in s:
        checks.append(bool(s["line_connected"]))
    if "limit_hit" in s:
        checks.append(not s["limit_hit"])
    return sum(checks) / len(checks) if checks else 1.0


def bids(app: App, now: float) -> list:
    """Workspace bids for a body that needs attention: not about you, so they may be shown to an AI."""
    from kurooto.mind.workspace import Bid

    if not on(app):
        return []
    hist = (jload(app.paths.state / FILE, {}) or {}).get("history") or []
    if not hist:
        return []
    s, out = hist[-1], []
    if s.get("cpu_temp_c", 0) >= HOT_C:
        out.append(
            Bid(
                "body:hot",
                "body",
                "this computer is running hot",
                stake=0.6,
                urgency=0.9,
                module="intero",
                source="saw",
            )
        )
    if "battery_pct" in s and s["battery_pct"] <= 15 and not s.get("charging"):
        out.append(
            Bid("body:battery", "body", "the battery is low", stake=0.6, urgency=0.8, module="intero", source="saw")
        )
    if s.get("disk_free_gb", 99) <= 2:
        out.append(
            Bid("body:disk", "body", "the disk is nearly full", stake=0.7, urgency=0.7, module="intero", source="saw")
        )
    if s.get("limit_hit"):
        out.append(
            Bid(
                "body:limit",
                "body",
                "an AI provider is at its limit",
                stake=0.5,
                urgency=0.6,
                module="intero",
                source="saw",
            )
        )
    return out


def report(app: App) -> str:
    st = jload(app.paths.state / FILE, {}) or {}
    hist = st.get("history") or []
    if not hist:
        return "No body readings yet (they start with Brain, every minute)."
    s = hist[-1]
    names = {
        "cpu_temp_c": "CPU temperature",
        "gpu_temp_c": "GPU temperature",
        "vram_used_gb": "graphics memory in use (GB)",
        "ram_pct": "memory used (%)",
        "swap_pct": "swap used (%)",
        "battery_pct": "battery (%)",
        "disk_free_gb": "free disk (GB)",
        "queue_depth": "AI requests waiting",
        "quota_used_pct": "most-used AI limit (%)",
    }
    lines = [f"- {n}: {s[k]}" for k, n in names.items() if k in s]
    if "line_connected" in s:
        lines.append(f"- call line: {'connected' if s['line_connected'] else 'not connected'}")
    learned = [
        f"- {a} changes {v} by {e['mean']:+.1f} (seen {e['n']} times)"
        for a, vs in (st.get("model") or {}).items()
        for v, e in vs.items()
        if e["n"] >= 3 and abs(e["mean"]) >= 0.5
    ]
    return (
        "Its own machine, a minute ago:\n"
        + "\n".join(lines)
        + ("\nWhat it has learned about its own actions:\n" + "\n".join(learned) if learned else "")
    )


def last_fine(app: App) -> float | None:
    """The share of fine checks at the latest reading (None before any)."""
    hist = (jload(app.paths.state / FILE, {}) or {}).get("history") or []
    return fine(hist[-1]) if hist else None


# ------------------------------------------------------------------------------------------------- the job gate
_pending: dict[tuple[int, str], tuple[str, Callable, bool]] = {}  # (app, name) -> (cost, the work, nightly)
_running: dict[int, set[str]] = {}  # app -> the gated work running now (for contention)
_glock = threading.Lock()
_retrying = threading.Lock()


def yield_on(app: App) -> bool:
    return mind.on(app) and bool(app.settings.get("mind.yield.on"))


def _own_pids() -> set[int]:
    import psutil

    try:
        me = psutil.Process(os.getpid())
        return {me.pid, *(c.pid for c in me.children(recursive=True))}
    except Exception:
        return {os.getpid()}


def _compute_apps() -> list[tuple[int, float]]:
    """(pid, MB) of every compute process on the graphics card, from nvidia-smi; [] without one."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        r = subprocess.run(  # noqa: S603
            [exe, "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for ln in r.stdout.strip().splitlines():
        try:
            pid, mb = ln.split(",")[:2]
            out.append((int(pid), float(_num(mb) or 0)))
        except ValueError:
            continue
    return out


def gpu_holders(app: App) -> int:
    """How many processes that aren't Kurooto's (nor a model server it shares) hold the graphics card."""
    import psutil

    own = _own_pids()
    n = 0
    for pid, mb in _compute_apps():
        if pid in own or mb < FOREIGN_MB:
            continue
        try:
            name = psutil.Process(pid).name().lower()
        except Exception:
            name = ""
        if any(name.startswith(s) for s in SHARED_GPU):
            continue
        n += 1
    return n


def _on_call(app: App) -> bool:
    try:
        return bool(app.availability.on_call_until())
    except Exception:
        return False


def _on_battery(app: App) -> bool:
    try:
        p = getattr(app, "power", None)
        if p is not None:
            return not p.on_ac()
        from kurooto.core.power import on_ac

        return not on_ac()
    except Exception:
        return False


def ok(app: App, cost: str = "gpu", action: str = "") -> tuple[bool, str]:
    """May the Brain's own work of this cost start now? (True, "") or (False, why). `action` names it, for what the
    body has learned it does (would_overheat). With mind.yield.on off, or Brain off: always yes."""
    if not yield_on(app):
        return True, ""
    cost = cost if cost in COSTS else "gpu"
    hist = (jload(app.paths.state / FILE, {}) or {}).get("history") or []
    last = hist[-1] if hist and time.time() - float(hist[-1].get("at") or 0) < 180 else None  # the minute's reading
    if cost == "light":
        hot = (last or {}).get("cpu_temp_c", 0) >= HOT_C
        return (False, "the computer is hot") if hot else (True, "")
    if _on_call(app):
        return False, "you're on a call"
    if _on_battery(app):
        return False, "on battery"
    if gpu_holders(app):
        return False, "your own work is using the graphics card"
    try:
        if would_overheat(app, action or ("lab" if cost == "gpu" else "ai_request"), last):
            return False, "the computer is hot"
        if cost == "gpu" and ((last or {}).get("gpu_temp_c") or 0) >= HOT_C:
            return False, "the graphics card is hot"
    except Exception:  # noqa: S110 (a sensor that fails doesn't hold the work)
        pass
    return True, ""


def _sleep_wait(app: App) -> str:
    """Nightly work, with prefer_sleep: "" when it may go, else why it waits for Kurooto's sleep."""
    if not app.settings.get("mind.yield.prefer_sleep"):
        return ""
    try:
        from kurooto.mind import sleep
    except ImportError:
        return ""
    try:
        if not sleep.on(app) or sleep.state(app) == "asleep":
            return ""
        from kurooto.core.clock import now

        w, t = sleep.window(app), now()
        if w and w[0] - dt.timedelta(hours=PENDING_H) <= t < w[1]:
            return "waiting for its sleep"
    except Exception:  # noqa: S110
        pass
    return ""


def _day() -> str:
    return dt.date.today().isoformat()


def _count(app: App, key: str, n: int = 1) -> None:
    with _glock:
        st = jload(app.paths.state / FILE, {}) or {}
        days = st.setdefault(key, {})
        days[_day()] = int(days.get(_day(), 0)) + n
        cut = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
        st[key] = {d: v for d, v in days.items() if d >= cut}
        jsave(app.paths.state / FILE, st)


def _run(app: App, name: str, fn: Callable):
    with _glock:
        _running.setdefault(id(app), set()).add(name)
    try:
        return fn()
    finally:
        with _glock:
            _running.get(id(app), set()).discard(name)


def gated(app: App, name: str, cost: str, fn: Callable, nightly: bool = False):
    """Run the Brain's own heavy work `fn()` now if the body allows (and, nightly, Kurooto is asleep), else keep it
    for retry(). Returns fn's result, or None when it waits. Never for what you asked for."""
    if not yield_on(app):
        return fn()
    go, why = ok(app, cost, name)
    if go and nightly:
        why = _sleep_wait(app)
        go = not why
    if not go:
        _defer(app, name, cost, fn, nightly, why)
        return None
    _drop(app, name)
    return _run(app, name, fn)


def _defer(app: App, name: str, cost: str, fn: Callable, nightly: bool, why: str) -> None:
    key = (id(app), name)
    first = key not in _pending
    _pending[key] = (cost, fn, nightly)
    with _glock:
        st = jload(app.paths.state / FILE, {}) or {}
        p = st.setdefault("pending", {})
        p[name] = {"since": (p.get(name) or {}).get("since") or time.time(), "cost": cost, "why": why}
        jsave(app.paths.state / FILE, st)
    if first:
        _count(app, "deferred")
        app.events.emit("mind_yield", work=name, why=why[:40])


def _drop(app: App, name: str) -> None:
    _pending.pop((id(app), name), None)
    with _glock:
        st = jload(app.paths.state / FILE, {}) or {}
        if name in (st.get("pending") or {}):
            st["pending"].pop(name, None)
            jsave(app.paths.state / FILE, st)


def retry(app: App, payload: dict | None = None) -> int:
    """Every 5 minutes: deferred work that the body now allows starts (one at a time); work waiting longer than
    PENDING_H hours is given up until its next time. How many started."""
    if not _retrying.acquire(blocking=False):
        return 0
    try:
        st = jload(app.paths.state / FILE, {}) or {}
        pending = st.get("pending") or {}
        n = 0
        for name, p in list(pending.items()):
            got = _pending.get((id(app), name))
            if got is None or not yield_on(app):  # a restart lost the work, or the gate was turned off
                _drop(app, name)
                if got is not None:
                    _run(app, name, got[1])
                    n += 1
                continue
            if time.time() - float(p.get("since") or 0) > PENDING_H * 3600:
                _drop(app, name)
                _count(app, "skipped")
                app.events.emit("mind_yield_skipped", work=name)
                continue
            cost, fn, nightly = got
            go, why = ok(app, cost, name)
            if go and nightly:
                why = _sleep_wait(app)
                go = not why
            if go:
                _drop(app, name)
                _run(app, name, fn)
                n += 1
        return n
    finally:
        _retrying.release()


def contention_tick(app: App) -> bool:
    """Every minute: a minute in which the Brain's heavy work ran while your own work held the card counts."""
    if not yield_on(app):
        return False
    with _glock:
        busy = bool(_running.get(id(app)))
    if not busy or not gpu_holders(app):
        return False
    _count(app, "contention")
    return True


def contention(app: App, days: int = 7) -> dict:
    """The last `days` days: contention minutes, how often work was deferred, and given up; what waits now."""
    st = jload(app.paths.state / FILE, {}) or {}
    cut = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()

    def total(key: str) -> int:
        return sum(int(v) for d, v in (st.get(key) or {}).items() if d >= cut)

    return {
        "minutes": total("contention"),
        "deferred": total("deferred"),
        "skipped": total("skipped"),
        "waiting": sorted((st.get("pending") or {}).keys()),
    }


def yield_line(app: App) -> str:
    """One plain line for /mind."""
    if not yield_on(app):
        return "Job gate: off."
    c = contention(app)
    out = (
        f"Job gate: {c['minutes']} contention minute{'s' if c['minutes'] != 1 else ''} this week, "
        f"{c['deferred']} deferred, {c['skipped']} given up"
    )
    return out + (f"; waiting: {', '.join(c['waiting'])}." if c["waiting"] else ".")
