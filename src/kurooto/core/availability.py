"""When may Kurooto interrupt you? Quiet hours you set ("no calls till 6"), focus time (do-not-disturb), the
night, and blockers that modules add (a class you attend, a calendar event marked #nocall).

    call_block(t)   -> (reason, until) or (None, None)
    next_callable(t)-> the earliest time a call is allowed
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

from kurooto.core.clock import now
from kurooto.core.config import Settings, register_defaults
from kurooto.core.state import jload, jsave

register_defaults(
    "availability",
    {
        "night": {"enabled": True, "from": "23:30", "to": "07:00"},  # no calls overnight unless it's an alarm
        "nocall_keyword": "#nocall",
    },
)

# a blocker returns (reason, until) for time t, or None
Blocker = Callable[[dt.datetime], "tuple[str, dt.datetime] | None"]


class Availability:
    def __init__(self, state_dir: Path, settings: Settings):
        self.dir = Path(state_dir)
        self.settings = settings
        self.blockers: dict[str, Blocker] = {}

    # quiet: "no calls until X" (messages still come)
    def quiet_until(self, t: dt.datetime | None = None) -> dt.datetime | None:
        return self._until("quiet.json", t)

    def set_quiet(self, until: dt.datetime | None, reason: str = "you asked") -> None:
        self._set("quiet.json", until, reason=reason)

    # focus: do-not-disturb; non-urgent messages wait in a queue until it ends
    def focus_until(self, t: dt.datetime | None = None) -> dt.datetime | None:
        ends = [u for u in [self._until("focus.json", t)] if u]
        for name, b in self.blockers.items():
            if name.startswith("focus:"):
                r = b(t or now())
                if r:
                    ends.append(r[1])
        return max(ends) if ends else None

    def set_focus(self, until: dt.datetime | None) -> None:
        self._set("focus.json", until)

    def night(self, t: dt.datetime) -> tuple[str, dt.datetime] | None:
        n = self.settings.get("availability.night") or {}
        if not n.get("enabled"):
            return None
        start, end = dt.time.fromisoformat(n["from"]), dt.time.fromisoformat(n["to"])
        tt = t.time()
        inside = (start <= tt or tt < end) if start > end else (start <= tt < end)
        if not inside:
            return None
        day = t.date() if tt < end else t.date() + dt.timedelta(days=1)
        return "it's night", dt.datetime.combine(day, end)

    def call_block(self, t: dt.datetime | None = None) -> tuple[str | None, dt.datetime | None]:
        t = t or now()
        q = self.quiet_until(t)
        if q:
            return "you asked for no calls", q
        f = self.focus_until(t)
        if f:
            return "focus", f
        n = self.night(t)
        if n:
            return n
        for name, b in sorted(self.blockers.items()):
            if name.startswith("focus:"):
                continue
            r = b(t)
            if r:
                return r
        return None, None

    def next_callable(self, t: dt.datetime | None = None, limit: int = 24) -> tuple[dt.datetime, str | None]:
        """The earliest time at or after t when a call is allowed (follows chained blocks)."""
        t = t or now()
        for _ in range(limit):
            reason, until = self.call_block(t)
            if not reason:
                return t, None
            t = until + dt.timedelta(minutes=1)
        return t, "too many blocks in a row"

    # gates for the scheduler: when to postpone a job to
    def quiet_gate(self, at_utc: dt.datetime) -> dt.datetime | None:
        t = at_utc.astimezone().replace(tzinfo=None)
        f = self.focus_until(t)
        return f.astimezone() if f else None

    def call_gate(self, at_utc: dt.datetime) -> dt.datetime | None:
        t = at_utc.astimezone().replace(tzinfo=None)
        when, _ = self.next_callable(t)
        return None if when <= t else when.astimezone()

    def _until(self, name: str, t: dt.datetime | None) -> dt.datetime | None:
        t = t or now()
        try:
            u = dt.datetime.fromisoformat((jload(self.dir / name, {}) or {})["until"])
        except (KeyError, ValueError, TypeError):
            return None
        return u if u > t else None

    def _set(self, name: str, until: dt.datetime | None, **extra) -> None:
        if until is None:
            (self.dir / name).unlink(missing_ok=True)
        else:
            jsave(self.dir / name, {"until": until.replace(microsecond=0).isoformat(), **extra})
