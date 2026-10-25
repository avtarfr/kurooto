"""Week-scale plans (Brain, 0.8.0 stage 15): goal trees, simulated rollouts of the coming weeks and dated plans, scored
against
what happens. Plans shape only Kurooto's own preparation and quieter timing; they never steer you.

    tree.py      goal trees: deadlines (with Start-by sizes), repository milestones, stated goals
    pace.py      your real hours a day by weekday, as a distribution
    rollout.py   Monte Carlo (1000 rollouts, 6 weeks): p50/p90 finish dates, the risk of missing a due date, the
    week's allocation
    score.py     calibration against what finished, never compliance

    run(app)        make the plan now: the results, the allocation, what the workspace is told
    view(app)       /plan: this week's suggested hours and each milestone's risk
    weekly(app)     Sunday: one line, at most one plan message a week, through the gate
"""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.state import jsave
from kurooto.mind import workspace
from kurooto.mind.plans import pace, rollout, score, tree

if TYPE_CHECKING:
    from kurooto.app import App

PART = "plans"  # its switch: mind.plans.on
RISK_BID = 0.2  # a milestone at least this likely to be missed gets a standing bid
SEND_GAP_S = 6.5 * 86400  # at most one plan message a week


def on(app: App) -> bool:
    return mind.part_on(app, "plans")


def free_hours(app: App, today: dt.date, days: int):
    """Free hours per day from Start-by's free slots (the calendar's gaps), or None when it isn't on."""
    sb = app.modules.get("startby")
    if sb is None or not app.is_on("startby"):
        return None
    try:
        t0 = dt.datetime.combine(today, dt.time(0))
        slots = sb.slots(t0, t0 + dt.timedelta(days=days))
    except Exception:
        return None
    per = [0.0] * days
    for a, b in slots:
        for d in range(days):
            lo, hi = t0 + dt.timedelta(days=d), t0 + dt.timedelta(days=d + 1)
            per[d] += max(0.0, (min(b, hi) - max(a, lo)).total_seconds() / 3600)
    return lambda d: per[d] if 0 <= d < days else 0.0


def run(app: App, seed: int | None = None, today: dt.date | None = None) -> dict | None:
    if not on(app):
        return None
    today = today or dt.date.today()
    weeks = int(app.settings.get("mind.plans.weeks") or 6)
    nodes = tree.build(app, weeks)
    if not nodes:
        return {"nodes": [], "results": {}, "alloc": {}}
    days = weeks * 7
    results, alloc = rollout.simulate(
        nodes,
        pace.samples(app, today),
        today,
        days,
        int(app.settings.get("mind.plans.rollouts") or 1000),
        seed if seed is not None else int(time.time() // 3600),
        free_hours(app, today, days),
    )
    score.record(app, results, today)
    for r in results.values():  # inward: a milestone that may be missed raises its standing bid in the workspace
        if r.risk >= RISK_BID:
            workspace.set_standing(app, f"plan-{r.id}", r.title, r.risk)
        else:
            workspace.clear_standing(app, f"plan-{r.id}")
    jsave(
        app.paths.state / "mind-plan-last.json",
        {"on": today.isoformat(), "risks": {i: r.risk for i, r in results.items()}},
    )
    return {"nodes": nodes, "results": results, "alloc": alloc}


def view(app: App) -> str:
    if not on(app):
        return "Plans are off (mind.plans.on, with Brain)."
    plan = run(app)
    if not plan or not plan["nodes"]:
        return "Nothing to plan: no open deadlines or milestones in the next weeks."
    today = dt.date.today()
    names = "Mon Tue Wed Thu Fri Sat Sun".split()
    lines = ["A suggestion for this week, hours a day (your pace: " + pace.describe(pace.samples(app)) + "):"]
    head = "  " + " ".join(f"{names[(today + dt.timedelta(days=d)).weekday()]:>4}" for d in range(7))
    lines.append(head)
    for n in plan["nodes"]:
        a = plan["alloc"][n.id]
        if sum(a) >= 0.05:
            lines.append("  " + " ".join(f"{h:4.1f}" for h in a) + f"  {n.title[:36]}")
    lines.append("")
    lines.append("Milestones (likely finish, and the chance of missing the due date at your current pace):")
    for n in sorted(plan["nodes"], key=lambda n: -plan["results"][n.id].risk)[:10]:
        r = plan["results"][n.id]
        fin = f"{r.p50:%a %d %b} (p90 {r.p90:%d %b})" if r.p50 and r.p90 else "not within the horizon"
        guess = " ~" if n.guessed else ""
        lines.append(
            f"- {n.title[:40]}: due {n.due:%a %d %b}; {fin}; {round(r.risk * 100)}% late; "
            f"effort {n.effort_h:g} h{guess} [{n.id}]"
        )
    n, frac, skill = score.calibration(app)
    lines.append(
        f"\nHow well past plans held: {n} milestone(s) scored, too few to say."
        if skill is None
        else f"\nHow well past plans held: {round(frac * 100)}% finished by their p50 (about 50% is calibrated)."
    )
    lines.append("~ = a guess; /plan effort <id> <hours> sets your own. This is a suggestion, not a to-do.")
    return "\n".join(lines)


def digest_line(app: App) -> str:
    plan = run(app)
    if not plan or not plan["nodes"]:
        return ""
    worst = max(plan["nodes"], key=lambda n: plan["results"][n.id].risk)
    r = plan["results"][worst.id]
    if r.risk < 0.1:
        return ""
    week = {n.id: sum(plan["alloc"][n.id]) for n in plan["nodes"]}
    big = max(plan["nodes"], key=lambda n: week[n.id])
    line = f"{worst.title}: {round((1 - r.risk) * 100)}% on time at your current pace"
    return line + (
        f"; this week most of the time goes to {big.title}." if big.id != worst.id and week[big.id] > 0 else "."
    )


def weekly(app: App, payload: dict | None = None, now: float | None = None) -> bool:
    """Sunday: at most one plan line a week, and only when something is at risk. Through the gate (reason mind.plan)."""
    if not on(app):
        return False
    st = tree._state(app)  # noqa: SLF001
    t = now or time.time()
    if t - float(st.get("last_sent") or 0) < SEND_GAP_S:
        return False
    line = digest_line(app)
    if not line:
        return False
    st["last_sent"] = t
    jsave(app.paths.state / tree.FILE, st)
    app.notify("Plan for the week: " + line, kind="info", why="mind.plan")
    return True
