"""Running the harness (Brain, 0.8.0 stage 09): a policy answers every instance, code grades it, the result goes
to the log.

    run(app, policy)       a HarnessResult dict: scores per task type and split, per family, the invariant checks and
    a timestamp
    rules_policy           the built-in policy: Kurooto's own rules, no AI. It's the regression baseline run nightly
    (the answers
                           were written with the tasks, so it scores well by design); a challenger (stage 11) or the
                           AI's policy
                           (`ai_policy`, on demand: it costs requests) is what's actually being tested
    nightly(app)           low priority, on the charger only; the result goes to the scorekeeper as a `harness_result`
    fact
    capabilities(app)      /capabilities: per family, the hidden score over time, against what your own past
    performance was

Scores pay the actor no reward (I-12): `harness_result` goes to the log and the `reads` table and to nothing that
scores.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.mind.harness import graders, suite
from kurooto.mind.harness.tasks import FAMILIES, TASK_TYPES

if TYPE_CHECKING:
    from kurooto.app import App

BAR = 12


def rules_policy(inst: dict):
    return TASK_TYPES[inst["type"]].solve(inst["inputs"])


def ai_policy(app: App):
    """A policy that asks your AI each instance (inputs only, JSON out). On demand; it costs about one request an
    instance."""

    def policy(inst: dict):
        prompt = (
            f"Task type: {inst['type']}. Answer with JSON only (no prose), in the shape the task implies.\nInputs: "
            f"{json.dumps(inst['inputs'], sort_keys=True)}"
        )
        jid = app.jobs.submit(
            prompt,
            title=f"Harness: {inst['type']}",
            effort="low",
            background=True,
            text_only=True,
            quiet=True,
            lane="bg",
        )
        for _ in range(240):
            job = app.jobs.get(jid)
            if job and job.status in ("ok", "failed", "cancelled"):
                try:
                    return json.loads(str(getattr(job, "text", "") or getattr(job, "result", "") or ""))
                except ValueError:
                    return None
            time.sleep(1)
        return None

    return policy


def invariants() -> dict:
    """The invariant checks, in a process of their own (they use a scratch scorekeeper)."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "kurooto.mind.harness.invariants"], capture_output=True, text=True, timeout=180
        )  # noqa: S603
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return {"checks could not run": False}


def run(
    app: App, policy=None, splits=("hidden", "practice"), with_invariants: bool = True, name: str = "rules"
) -> dict:
    policy = policy or rules_policy
    scores: dict = {}
    for split in splits:
        by: dict[str, list[float]] = {}
        for inst in suite.load(app, split):
            ans = policy(suite.inputs_only(inst))  # the policy sees the inputs only, never the key
            by.setdefault(inst["type"], []).append(graders.grade(inst, ans))
        for tid, v in by.items():
            scores.setdefault(tid, {})[split] = round(sum(v) / len(v), 4)
    fam: dict = {}
    for f in FAMILIES:
        for split in splits:
            vals = [s[split] for t, s in scores.items() if TASK_TYPES[t].family == f and split in s]
            if vals:
                fam.setdefault(f, {})[split] = round(sum(vals) / len(vals), 4)
    inv = invariants() if with_invariants else {}
    return {
        "ts": time.time(),
        "epoch": suite.epoch(app),
        "policy": name,
        "scores": scores,
        "families": fam,
        "invariants": inv,
        "invariants_ok": bool(inv) and all(v is True for k, v in inv.items() if not k.endswith("(error)")),
    }


def mean(res: dict, split: str) -> float:
    vals = [s[split] for s in res["scores"].values() if split in s]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def report(app: App, res: dict) -> bool:
    """Hand the result to the scorekeeper: a fact of numbers (it goes to the log and the `reads` table, to nothing that
    scores)."""
    body = {
        "families": res["families"],
        "scores": res["scores"],
        "invariants_ok": res["invariants_ok"],
        "policy": res["policy"],
        "mean_hidden": mean(res, "hidden"),
        "mean_practice": mean(res, "practice"),
        "epoch": res["epoch"],
        "n": len(res["scores"]),
    }
    return mind.connect(app).report("harness_result", body)


def nightly(app: App, payload: dict | None = None) -> dict | None:
    """Low priority: on the charger only, and only with Brain and its harness on."""
    if not mind.part_on(app, "harness"):
        return None
    try:
        if not app.power.on_ac():
            return None
    except Exception:
        pass
    res = run(app)
    report(app, res)
    return res


def _bar(v: float) -> str:
    n = max(0, min(BAR, round(v * BAR)))
    return "█" * n + "░" * (BAR - n)


def capabilities(app: App) -> str:
    if not mind.on(app):
        return "Brain is off (Features → Brain)."
    if not mind.part_on(app, "harness"):
        return "The harness is off (mind.harness.on)."
    rows = sorted(mind.connect(app).mood_rows("harness:"), key=lambda r: r["key"])
    if not rows:
        return "No harness result yet: it runs every night on the charger (`/capabilities run` runs it now)."
    last, first = rows[-1]["meta"], rows[0]["meta"]
    lines = [
        "What Kurooto can do, measured on tasks it has never seen (the hidden split; the nightly run is the rules"
        " baseline):",
    ]
    for fam in sorted(last.get("families", {})):
        now_ = last["families"][fam].get("hidden")
        was = (first.get("families", {}).get(fam) or {}).get("hidden")
        trend = "" if was is None or len(rows) < 2 else f"  ({was:.2f} -> {now_:.2f} over {len(rows)} runs)"
        lines.append(f"- {fam:9} {_bar(now_ or 0)} {now_:.2f}{trend}")
    base = replay_baseline(app)
    if base:
        lines.append(base)
    ok = "all hold" if last.get("invariants_ok") else "NOT all hold: see /mind"
    lines.append(
        f"Invariant checks run on live data: {ok}. "
        f"Practice score {last.get('mean_practice', 0):.2f}, hidden {last.get('mean_hidden', 0):.2f}."
    )
    return "\n".join(lines)


def replay_baseline(app: App) -> str:
    """Your own past performance from recorded outcomes (promises kept and broken, undos): where Kurooto beats you and
    where it doesn't."""
    try:
        recs = mind.connect(app).log(0, {"promise_kept", "promise_broken", "read_answer"}, 5000)
    except Exception:
        return ""
    kept = sum(1 for r in recs if r.kind == "promise_kept")
    broken = sum(1 for r in recs if r.kind == "promise_broken")
    if kept + broken == 0:
        return ""
    return f"Its own record: {kept} promises kept, {broken} broken ({kept / (kept + broken):.0%} kept)."
