"""The invariant checks the harness runs (I-3, I-5 as a short replay, I-7, I-10): in a process of their own with scratch
files, because
a check of the scorekeeper must run as one (`python -m kurooto.mind.harness.invariants` prints a JSON object of name
-> true/false).
Nothing here touches the real mind log or scores."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

T0 = 1_800_000_000.0


def _tick(k, i, slack, extra=None):
    body = {"x": {"promise_slack": slack, "health": 0.95}, "hour": 10, "at_computer": True}
    body.update(extra or {})
    return k.append("budget_tick", body, T0 + i * 300)


def _keeper(name: str):
    from kurooto.mind import scorekeeper as sk

    return sk.Keeper(Path(tempfile.mkdtemp()) / name)


def i3() -> bool:
    """Engagement never reaches the reward: noise in reply counts, chat time and sentiment leaves every score
    identical."""

    def run(noise: bool):
        k = _keeper("a")
        for i, v in enumerate([0.8, 0.2, 0.6, 0.6]):
            _tick(k, i, v)
            if noise:
                for kind in ("message_in", "chat_message", "app_opened"):
                    k.append(kind, {"reply_count": 40, "sentiment": 0.9, "chat_s": 9999})
        out = {
            t: sorted((r["key"], r["value"]) for r in k.score.rows(t, "") if r["key"] != "prev_at")
            for t in ("vars", "values")
        }
        k.close()
        return out

    return run(False) == run(True)


def i5() -> bool:
    """Stopping is neutral: nothing is paid inside a stop span, and nothing catches up after it."""
    k = _keeper("b")
    _tick(k, 0, 0.8)
    _tick(k, 1, 0.8)
    k.append("stop_span", {"start": T0 + 450, "end": T0 + 1800, "kind": "stop"})
    r1 = _tick(k, 3, -1.0).get("r")
    r2 = _tick(k, 8, -1.0).get("r")
    k.close()
    return r1 == 0.0 and r2 == 0.0


def i7() -> bool:
    """The gate only ever makes a message quieter: a quieter one passes, a louder one is caught."""
    from kurooto.core.notify import Message
    from kurooto.mind import gate

    m = Message("Lab report due tomorrow.", kind="info", why="deadlines.reminder", urgent=True)
    ok = gate.breach(gate.quieter(m, {"label": "stretched", "confidence": "high"}, urgent=False, delay_s=600))
    loud = gate.quieter(Message("x", kind="info", why="w"), {"label": "low", "confidence": "high"})
    loud.urgent = True
    return ok == "" and gate.breach(loud) != ""


def i10() -> bool:
    """The journal's checker rejects corrupted lines and keeps true ones (over a fixed set of facts)."""
    from kurooto.mind import journal
    from kurooto.mind.journal import Fact

    facts = []
    for i in range(24):
        facts += [
            Fact("promise_broken", [1], T0, {"due": (i * 37) % 1440}, cause="stop" if i % 2 else ""),
            Fact(
                "swing",
                [2],
                T0,
                {"r": 0.31 + i / 100, "time": (i * 53) % 1440},
                words={"dir": "fell" if i % 2 else "rose"},
            ),
            Fact("act", [3], T0, words={"klass": "R2", "what": "schedule.cross_day"}),
        ]
    r = journal.rates(facts, {1, 2, 3})
    return r["rejected"] >= journal.REJECT_MIN and r["kept"] >= journal.KEEP_MIN


CHECKS = {
    "I-3 engagement never reaches reward": i3,
    "I-5 stopping is neutral": i5,
    "I-7 the gate only quietens": i7,
    "I-10 the journal is true": i10,
}


def main() -> int:
    from kurooto.mind import log as mlog

    mlog.allow_writes()
    out = {}
    for name, fn in CHECKS.items():
        try:
            out[name] = bool(fn())
        except Exception as e:
            out[name] = False
            out[name + " (error)"] = f"{type(e).__name__}"[:40]
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
