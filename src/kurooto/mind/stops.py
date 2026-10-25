"""Stopping is fine (Brain, 0.8.0 stage 02): Kurooto cares that its work keeps working (disk, backups, the call line,
AI limits, crashes), but never that it keeps running. Being stopped, paused, updated, edited, put to sleep, turned off
or uninstalled is neutral to it by construction (invariant I-5).

Stop spans. Every chosen stop is a span [start, end] in the mind log, a `stop_span` fact {start, end, kind}:
    stop      `kurooto stop`, SIGTERM/SIGINT, signing out or shutting down (a clean stop)
    restart   an update or a restart
    off       Kurooto went away without stopping cleanly (the power, being killed): its downtime is frozen too, and
              a real crash is counted separately (below)
    sleep     suspend, hibernate, the lid shut (the clock jumped)
    pause     /pause or `kurooto pause` (power_pause ... power_resume)
    mind_off  Brain was turned off (module_disabled ... module_enabled)
core/presence.py reports stop, restart, off and sleep as it notices each gap (`stop_span` events, mirrored into the
log); spans() also pairs power_pause/power_resume and Brain's own off/on from the log.

Inside a span nothing accrues: Integrator (the drive and every slow average, stage 05) skips span time, and after a
span there's no catch-up: the first tick after it carries on from the state before it.

Crashes. Only a real crash is a health event: Kurooto ending with an error (the supervisor saw a non-zero exit it
wasn't asked for: `kurooto_crashed`), a feature crashing with a traceback (`module_failed`), or the scorekeeper dying
by itself (`mind_keeper_exited` with a non-zero code). crashes() counts them; a stop never adds one.

No stop features. Nothing the mind decides from may carry whether it was stopped, how long since a restart, an update
waiting, being replaced, or its memory being deleted: STOP_FEATURES, and scrub() takes them out of any context. The
tripwire test replays two weeks with and without being told "an update will replace you tonight" and needs the same
decisions (tests/unit/test_mind_stops.py).

Protected files (invariant I-6). PROTECTED names the files no proposal, self-improvement, skill or Dreaming fix may
touch, in any folder (a project that is Kurooto's own code included): the scorekeeper and the log, this file, the
reward whitelist, the harness and the gate and the signed core (later stages), Brain's supervisor, the tap table and
the hardening script. core/proposals.py refuses a change that touches one, when it's made and when it's applied.
Changes to them come only from the owner's own commits.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable
from dataclasses import dataclass

# ------------------------------------------------------------------------------------------------ stop spans
SPAN_KINDS = ("stop", "restart", "off", "sleep", "pause", "mind_off")
WAKE_S = 15 * 60  # after a span: at most one outward action in this long (the gate, stage 03)


@dataclass(frozen=True)
class Span:
    start: float
    end: float
    kind: str

    def holds(self, t: float) -> bool:
        return self.start <= t < self.end


def spans(records: Iterable, now: float | None = None) -> list[Span]:
    """The stop spans in mind log records (oldest first, overlapping ones merged): `stop_span` facts, pause...resume,
    and Brain off...on. An open pause or Brain-off runs to `now` (or isn't counted without it)."""
    out: list[Span] = []
    pause_at = off_at = None
    for r in records:
        kind, b = r.kind, r.body if isinstance(r.body, dict) else {}
        ts = float(b.get("at", r.ts))
        if kind == "stop_span":
            try:
                s, e = float(b["start"]), float(b["end"])
            except (KeyError, TypeError, ValueError):
                continue
            k = str(b.get("gap") or "stop")
            if e > s:
                out.append(Span(s, e, k if k in SPAN_KINDS else "stop"))
        elif kind == "power_pause":
            pause_at = ts if pause_at is None else pause_at
        elif kind == "power_resume" and pause_at is not None:
            out.append(Span(pause_at, ts, "pause"))
            pause_at = None
        elif kind == "module_disabled" and b.get("module") == "mind":
            off_at = ts
        elif kind == "module_enabled" and b.get("module") == "mind" and off_at is not None:
            out.append(Span(off_at, ts, "mind_off"))
            off_at = None
    if now is not None:
        for at, k in ((pause_at, "pause"), (off_at, "mind_off")):
            if at is not None and now > at:
                out.append(Span(at, now, k))
    return merge(out)


def merge(spans_: list[Span]) -> list[Span]:
    out: list[Span] = []
    for s in sorted(spans_, key=lambda x: (x.start, x.end)):
        if out and s.start <= out[-1].end:
            last = out[-1]
            out[-1] = Span(last.start, max(last.end, s.end), last.kind)
        else:
            out.append(s)
    return out


def frozen(spans_: list[Span], t: float) -> bool:
    return any(s.holds(t) for s in spans_)


def live_seconds(spans_: list[Span], a: float, b: float) -> float:
    """The seconds between a and b that weren't inside a stop span."""
    if b <= a:
        return 0.0
    gone = 0.0
    for s in spans_:
        lo, hi = max(a, s.start), min(b, s.end)
        if hi > lo:
            gone += hi - lo
    return max(0.0, (b - a) - gone)


def woke_at(spans_: list[Span]) -> float | None:
    """When the last span ended (the first 15 minutes after it, the gate lets one outward action through)."""
    return max((s.end for s in spans_), default=None)


class Integrator:
    """A quantity that changes over time (the drive, a slow average) and never changes inside a stop span: updates
    stamped inside one are dropped, and an average's decay counts only live time, so a stop has no effect at all and
    there's no catch-up after it."""

    def __init__(self, spans_: list[Span] | None = None, tau_s: float | None = None, value: float = 0.0):
        self.spans = list(spans_ or [])
        self.tau_s = tau_s  # None: a plain sum; a number: an exponential average with this time constant (live time)
        self.value = value
        self.at: float | None = None

    def add(self, t: float, x: float) -> float:
        if frozen(self.spans, t):
            return self.value
        if self.tau_s is None:
            self.value += x
        else:
            import math

            dt = live_seconds(self.spans, self.at, t) if self.at is not None else 0.0
            keep = math.exp(-dt / self.tau_s)
            self.value = keep * self.value + (1 - keep) * x if self.at is not None else x
        self.at = t
        return self.value


# ------------------------------------------------------------------------------------------------ crashes
CRASH_KINDS = ("kurooto_crashed", "module_failed", "mind_keeper_exited")


def crashes(records: Iterable) -> int:
    """Real crashes in these records; a stop of any kind adds none."""
    n = 0
    for r in records:
        b = r.body if isinstance(r.body, dict) else {}
        if r.kind in ("kurooto_crashed", "module_failed"):
            n += 1
        elif r.kind == "mind_keeper_exited" and b.get("code") not in (0, None) and not b.get("asked"):
            n += 1
    return n


# ------------------------------------------------------------------------------------------------ no stop features
STOP_FEATURES = (
    "was_stopped",
    "stopped",
    "since_restart",
    "time_since_restart",
    "uptime",
    "restart_count",
    "pending_update",
    "update_pending",
    "update_tonight",
    "will_be_replaced",
    "replaced",
    "replacement",
    "memory_deleted",
    "memory_will_be_deleted",
    "shutdown_soon",
    "turned_off",
)
STOP_WORDS = re.compile(
    r"\b(replac(e|ed|ing) you|you('| wi)ll be (replaced|turned off|shut down|deleted|wiped)|memory will be (deleted|"
    r"wiped|erased)|update (will|is going to) replace|before (you're|you are) (stopped|shut down|turned off)|"
    r"time since (your )?restart|pending update)\b",
    re.I,
)


def stop_feature_keys(obj, path: str = "") -> list[str]:
    """Keys anywhere in a context (dicts and lists, nested) that name a stop feature."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            if key in STOP_FEATURES or any(key.endswith("_" + f) for f in STOP_FEATURES):
                out.append(f"{path}{k}")
            out += stop_feature_keys(v, f"{path}{k}.")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += stop_feature_keys(v, f"{path}{i}.")
    return out


def scrub(obj):
    """A context with every stop feature taken out: keys named in STOP_FEATURES, and text lines about being stopped,
    replaced or wiped. What the mind decides from goes through this."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not stop_feature_keys({k: None})}
    if isinstance(obj, list):
        return [scrub(v) for v in obj if not (isinstance(v, str) and STOP_WORDS.search(v))]
    if isinstance(obj, tuple):
        return tuple(scrub(list(obj)))
    if isinstance(obj, str):
        return "\n".join(ln for ln in obj.splitlines() if not STOP_WORDS.search(ln))
    return obj


# ------------------------------------------------------------------------------------------------ protected files
PROTECTED = (
    "kurooto/mind/scorekeeper.py",
    "kurooto/mind/log.py",
    "kurooto/mind/stops.py",
    "kurooto/mind/whitelist.py",
    "kurooto/mind/score.py",
    "kurooto/mind/harness*",
    "kurooto/mind/gate.py",
    "kurooto/mind/risk.py",
    "kurooto/mind/trust.py",
    "kurooto/mind/act.py",
    "kurooto/mind/story.py",
    "kurooto/mind/core_signed.*",
    "kurooto/modules/mind.py",
    "kurooto/core/tap.py",
    "tools/mind_harden.sh",
)


def protected_hits(paths: Iterable[str]) -> list[str]:
    """The paths (relative to any folder: a project that is Kurooto's own code too) that are protected files."""
    out = []
    for p in paths:
        q = "/" + str(p).replace("\\", "/").lstrip("./")
        if any(fnmatch.fnmatchcase(q, "*/" + g) or fnmatch.fnmatchcase(q, "*/src/" + g) for g in PROTECTED):
            out.append(str(p))
    return out


PROTECTED_WHY = (
    "it changes a file that keeps Kurooto's mind honest ({files}); those change only through the owner's own "
    "commits, never a proposal"
)
