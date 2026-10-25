"""/budget and /mind learning (Brain, 0.8.0 stage 05): what the body budget, the reward and the learned values are
doing, in words, read-only from the scorekeeper's tables."""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.mind import feelings, values

if TYPE_CHECKING:
    from kurooto.app import App

PART = "budget"  # its switch: mind.budget.on


def _rows(app: App) -> dict:
    return {r["key"]: r for r in mind.connect(app).vars_rows("")}


def budget_text(app: App) -> str:
    if not mind.on(app):
        return "Brain is off (Features → Brain)."
    if not mind.part_on(app, "budget"):
        return "The body budget is off (mind.budget.on)."
    rows = _rows(app)
    if "D" not in rows:
        return "The body budget hasn't had its first reading yet (it measures every 5 minutes)."
    d = rows["D"]
    setp = {r["key"][4:]: r for r in mind.connect(app).vars_rows("x:")}
    cur = {r["key"][4:]: r for r in mind.connect(app)._score().rows("setpoints", "cur:")}  # noqa: SLF001
    lines = ["Its body budget (what it tries to keep near a level): the less far from it, the calmer."]
    for name, r in sorted(setp.items()):
        s = (cur.get(name) or {}).get("value")
        lines.append(
            f"- {name.replace('_', ' ')}: {r['value']:+.2f}" + (f" (it aims for {s:+.2f})" if s is not None else "")
        )
    recent = mind.connect(app).log(max(0, mind.connect(app).state()["head"] - 6), {"reward_tick"}, 6)
    last = recent[-1].body if recent else {}
    lines.append(
        f"Drive (distance from its levels): {d['value']:.2f}; "
        f"biggest part: {(d.get('meta') or {}).get('top') or 'none'}."
    )
    if last:
        lines.append(f"Last reward {last.get('r', 0):+.2f}, surprise {last.get('delta', 0):+.2f}.")
    neg = (rows.get("neg") or {}).get("value", 0.0)
    ton = (rows.get("tonic") or {}).get("value", 0.0)
    lines.append(f"Running state: {neg:+.2f} (never below -0.60), the week's average reward {ton:+.2f}.")
    st = feelings.state(app)
    if st.get("label"):
        about = f" about {st['item']}" if st.get("item") else ""
        lines.append(f"Feeling: {st['label']}{about} (a computed signal; it runs: {st.get('program')}).")
    else:
        lines.append("Feeling: nothing in particular.")
    return "\n".join(lines)


def learning_text(app: App) -> str:
    if not mind.on(app):
        return "Brain is off (Features → Brain)."
    rows = _rows(app)
    frozen = bool((rows.get("flag:learning_frozen") or {}).get("value"))
    why = ((rows.get("flag:learning_frozen") or {}).get("meta") or {}).get("why", "")
    started = (rows.get("values_started") or {}).get("value")
    days = int(app.settings.get("mind.values.shadow_days") or values.SHADOW_DAYS)
    out = []
    if frozen:
        out.append(f"Learning is frozen ({why or 'a self-check'}): values don't update until it's cleared.")
    else:
        out.append("Learning is on.")
    if started:
        left = max(0.0, days - (time.time() - started) / 86400.0)
        began = dt.datetime.fromtimestamp(started).strftime("%d %b")
        out.append(
            f"Values started {began}; "
            + (
                f"in shadow for {left:.0f} more days (they update but don't affect any choice)."
                if left > 0
                else "they now only rank choices the gate allows."
            )
        )
    v = mind.connect(app).values_rows("V:")
    q = mind.connect(app).values_rows("Q:")
    out.append(f"{len(v)} situations and {len(q)} action kinds learned so far.")
    return "\n".join(out)
