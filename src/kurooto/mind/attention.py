"""The attention schema (Brain, 0.8.0 stage 10): a small model of Kurooto's own attention.

It holds what is in the workspace, why each item won (its salience terms), how long it has stayed, and which items it
expects to win next. "What are you thinking about?" and `/thinking` are answered from this model and the log; an AI
only phrases the result, it never narrates its insides.

    model(app)       {winners: [{item_id, kind, text, terms, since_s}], next: [item_id], capacity}
    predict(app)     the items expected to win the next cycle: those now winning that aren't worn out (persistence)
    check(...)       each cycle: the last prediction against what won; (hit share, chance share) go to the scorekeeper
    accuracy(app)    (n, hit share, chance share) over all checks; the indicators page uses it
    report(app)      the /thinking text: from the model, the log's last records and the accuracy line

If its predictions of its own attention don't beat chance, `report` and the indicators page say so.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.mind import workspace

if TYPE_CHECKING:
    from kurooto.app import App

PART = "attention"  # its switch: mind.attention.on (with the workspace)
MIN_CHECKS = 10  # before this many, it says "too few to tell"


def on(app: App) -> bool:
    return mind.part_on(app, "attention") and workspace.on(app)


def terms(w: dict) -> str:
    return (
        f"stake {w.get('stake', 0):.2f}, urgency {w.get('urgency', 0):.2f}, surprise {w.get('surprise', 0):.2f} "
        f"-> salience {w.get('salience', 0):.2f}"
    )


def predict(app: App) -> list[str]:
    """Persistence, minus what is worn out: the winners now that you haven't heard about three times today."""
    st = workspace._state(app)  # noqa: SLF001
    now = time.time()
    return [w["item_id"] for w in st["winners"] if workspace.fatigue(st, w["item_id"], now) < 1.0]


def model(app: App) -> dict:
    now = time.time()
    ws = workspace.current(app)
    return {
        "capacity": workspace.capacity(app),
        "winners": [
            {
                "item_id": w["item_id"],
                "kind": w["kind"],
                "text": w.get("text", ""),
                "terms": terms(w),
                "since_s": max(0.0, now - float(w.get("since", now))),
                "pinned": bool(w.get("pinned")),
            }
            for w in ws
        ],
        "next": predict(app),
    }


def check(app: App, predicted: list[str], actual: list[str], n_bids: int, cap: int) -> None:
    """Did the schema's prediction of its next winners come true? Chance is picking `cap` of `n_bids` at random."""
    if not predicted or not actual or n_bids <= 0:
        return
    hit = len(set(predicted) & set(actual)) / max(1, min(cap, len(actual)))
    chance = min(1.0, cap / n_bids)
    mind.connect(app).report("attention_check", {"hit": hit, "chance": chance})


def accuracy(app: App) -> tuple[int, float, float]:
    """(checks, hit share, chance share), from the scorekeeper's running sums; zeros before any."""
    row = next(iter(mind.connect(app).mood_rows("attention:total")), None)
    if not row:
        return 0, 0.0, 0.0
    n = int((row.get("meta") or {}).get("n") or 0)
    if n <= 0:
        return 0, 0.0, 0.0
    return n, float(row["value"]) / n, float((row.get("meta") or {}).get("chance") or 0.0) / n


def accuracy_line(app: App) -> str:
    n, hit, chance = accuracy(app)
    if n < MIN_CHECKS:
        return f"Its guesses about its own next focus: {n} checked so far, too few to tell."
    verdict = "better than chance" if hit > chance + 0.05 else "no better than chance"
    return (
        f"Its guesses about its own next focus: right {hit:.0%} of the time over {n} checks; "
        f"chance is {chance:.0%}, so {verdict}."
    )


def report(app: App) -> str:
    """What /thinking says. Facts only: the model, the log, the accuracy."""
    if not on(app):
        return "The workspace is off (mind.workspace.on), so there's no 'now' to report."
    if time.time() - float(workspace._state(app)["cycle_at"]) > 120:  # noqa: SLF001  (the job runs each minute)
        workspace.cycle(app)
    m = model(app)
    if not m["winners"]:
        out = ["Nothing is competing for its attention right now."]
    else:
        out = ["On its mind right now:"]
        for i, w in enumerate(m["winners"], 1):
            mins = int(w["since_s"] // 60)
            stay = f"{mins // 60}h {mins % 60}m" if mins >= 60 else f"{mins}m"
            pin = ", pinned by you" if w["pinned"] else ""
            out.append(f"{i}. {w['text'] or w['kind']} ({w['kind']}): {w['terms']}; there {stay}{pin}")
        if m["next"]:
            out.append("It expects the same to stay on top next: " + ", ".join(m["next"]) + ".")
    out.append(accuracy_line(app))
    return "\n".join(out)
