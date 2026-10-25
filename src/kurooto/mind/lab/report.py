"""What the lab says: the morning digest, `/lab`, and the page. Null results are as prominent as wins."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.state import jload
from kurooto.mind.lab import prereg, runner

if TYPE_CHECKING:
    from kurooto.app import App


def pct(x: float | None) -> str:
    return "none yet" if x is None else f"{round(x * 100)}%"


def batch_line(slug: str, a: dict, baseline: float, metric: str = "the metric") -> str:
    n = a["n_ok"] + a["n_failed"]
    out = [f"Ran {n} configuration{'s' if n != 1 else ''} for {slug}."]
    if a["wins"]:
        out.append(
            f"{len(a['wins'])} beat your best on {metric} (replicated: {len(a['replicated'])})."
            + (
                f" Best: {a['best']['value']} against {baseline} ({round((a['best_gain'] or 0) * 100, 1)}% better)."
                if a["best"]
                else ""
            )
        )
    else:
        out.append(f"None beat your best ({baseline}) by enough: a null result, and a real one.")
    if a["nulls"]:
        out.append("Null on " + ", ".join(a["nulls"]) + " (changing it didn't move the metric).")
    if a["n_failed"]:
        out.append(f"{a['n_failed']} run(s) failed.")
    out.append(f"Replication rate: {pct(a['rate'])}.")
    return " ".join(out)


def digest(app: App) -> str:
    """The morning lines for last night's batches ("" when the lab did nothing)."""
    last = jload(app.paths.state / "lab" / "last-night.json", {}) or {}
    lines = []
    for slug, r in (last.get("projects") or {}).items():
        if r.get("finished") and r.get("batch"):
            res = jload(runner.folder(app, slug) / f"results-{int(r['batch']):04d}.json", {}) or {}
            if res.get("analysis"):
                rec = prereg.load(app, slug, int(r["batch"])) or {}
                lines.append(batch_line(slug, res["analysis"], res.get("baseline", 0), rec.get("metric", "the metric")))
        elif r.get("ran") and not r.get("finished"):
            lines.append(
                f"{slug}: {r.get('done', 0)} run(s) done, {r.get('left', 0)} waiting ({r.get('why', 'paused')}); "
                "it picks up tonight."
            )
        elif r.get("why"):
            lines.append(f"{slug}: didn't run: {r['why']}.")
    return "\n".join(lines)


def listing(app: App) -> str:
    if not mind.part_on(app, "lab"):
        return "The lab is off (mind.lab.on, with Brain)."
    ps = runner.projects(app)
    if not ps:
        return "No projects in the lab yet. Add a folder to mind.lab.projects, then /lab protocol <project>."
    out = ["Lab projects:"]
    for slug, root in ps.items():
        st, p, bad = runner.status(app, slug, root)
        q = jload(runner._queue_file(app, slug), {}) or {}  # noqa: SLF001
        line = f"- {slug} ({root}): protocol {st}" + (f", {p.objective}" if p else "")
        if q.get("pending"):
            line += f"; batch {q.get('batch')} has {len(q['pending'])} runs waiting"
        out.append(line)
    return "\n".join(out)


def results(app: App) -> str:
    out = []
    for slug in runner.projects(app):
        files = sorted(runner.folder(app, slug).glob("results-*.json"))
        regs = len(list(runner.folder(app, slug).glob("prereg-*.json")))
        reps, wins = 0, 0
        for f in files:
            a = (json.loads(f.read_text()) or {}).get("analysis", {})
            reps += len(a.get("replicated", []))
            wins += len(a.get("wins", []))
        out.append(
            f"- {slug}: {regs} pre-registered batch(es), {len(files)} finished; {wins} wins, {reps} replicated "
            f"(rate {pct(reps / wins if wins else None)})"
        )
    return "Lab results:\n" + "\n".join(out) if out else "No lab results yet."


def bid(app: App, now: float) -> list:
    """The workspace's bid for a replicated win from the last night (surprise: how much it gained)."""
    from kurooto.mind.workspace import Bid, clip01

    last = jload(app.paths.state / "lab" / "last-night.json", {}) or {}
    if not mind.part_on(app, "lab") or now - float(last.get("at") or 0) > 86400:
        return []
    out = []
    for slug, r in (last.get("projects") or {}).items():
        if r.get("replicated"):
            out.append(
                Bid(
                    f"lab:{slug}",
                    "lab",
                    f"the lab found a better setting for {slug}",
                    stake=0.6,
                    urgency=0.5,
                    surprise=clip01(0.3 + 0.1 * int(r["replicated"])),
                    module="lab",
                    source="saw",
                )
            )
    return out
