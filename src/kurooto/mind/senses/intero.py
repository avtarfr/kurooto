"""Interoception (Brain, 0.8.0 stage 13): Kurooto's sense of its own machine, on by default with Brain.

Every minute (the scheduler's finest step): CPU and GPU temperature, graphics memory used, memory and swap, battery and
charging, free disk, how much of the cloud AI limits is left, whether an AI provider is at its limit, whether the call
line is connected, and how many AI requests wait. They go to the workspace as bids when something is off (a hot
computer, a low battery, a limit reached) and the share that is fine is the `health` variable's input (mind/measure.py).

The learned sensorimotor model: which of *its own* actions move *its own* body (running the lab raises the temperature,
a training run fills graphics memory). `observe(action, before, after)` keeps a running mean change per action and body
variable; `expected(action, var)` is what scheduling asks ("would this heat it up?"). Its targets are body variables
only (I-14): `learn` refuses anything else, and nothing about you (phone sensors, the activity stream) is a target.
"""

from __future__ import annotations

import shutil
import subprocess
import time
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


def would_overheat(app: App, action: str) -> bool:
    s = sample(app)
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
