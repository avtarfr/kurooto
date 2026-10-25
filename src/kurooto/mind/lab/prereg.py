"""Pre-registration: the batch's question, configurations, metric, stopping rule and analysis are written down, and
their sha256 is appended to the mind log (`lab_prereg`), before the first run. Afterwards a batch is judged only under
that analysis. The file is read-only; `verify` recomputes the hash and compares it with the log's.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

ANALYSIS = (
    "a win beats the baseline by at least min_effect of it in the objective's direction; it counts only when every "
    "second-seed run also beats the baseline and the mean of its runs still clears min_effect; the score is the "
    "replication rate; parameters whose halves differ by less than min_effect are reported as null"
)


def make(project: str, proto, hypothesis: str, experiments: list[dict], baseline: float, stopping: str = "") -> dict:
    """The record to register: {project, hypothesis, experiments, metric, direction, stopping, analysis, ...}."""
    return {
        "project": project,
        "hypothesis": hypothesis[:300],
        "experiments": experiments,
        "metric": proto.metric,
        "direction": proto.direction,
        "min_effect": proto.min_effect,
        "seeds": proto.seeds,
        "space": proto.space,
        "baseline": baseline,
        "stopping": stopping or f"stop after {len(experiments)} configurations, the GPU-hour budget, or a suspend",
        "analysis": ANALYSIS,
        "weak": proto.weak,
    }


def digest(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def folder(app: App, slug: str) -> Path:
    return app.paths.state / "lab" / slug


def register(app: App, slug: str, rec: dict) -> str:
    """Write the record (read-only) and hand its hash to the scorekeeper; call this before the first run."""
    from kurooto import mind

    d = folder(app, slug)
    d.mkdir(parents=True, exist_ok=True)
    sha = digest(rec)
    n = len(list(d.glob("prereg-*.json"))) + 1
    f = d / f"prereg-{n:04d}.json"
    f.write_text(json.dumps({**rec, "registered": round(time.time(), 3), "sha256": sha}, indent=1, sort_keys=True))
    os.chmod(f, 0o444)
    mind.connect(app).report("lab_prereg", {"project": slug, "sha": sha, "n": len(rec["experiments"]), "batch": n})
    return sha


def load(app: App, slug: str, batch: int) -> dict | None:
    f = folder(app, slug) / f"prereg-{batch:04d}.json"
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return None


def verify(app: App, slug: str, batch: int) -> bool:
    """The file still hashes to what it did, and the log holds that hash from before the batch ran."""
    from kurooto import mind

    saved = load(app, slug, batch)
    if not saved:
        return False
    sha = saved.pop("sha256", "")
    saved.pop("registered", None)
    if digest(saved) != sha:
        return False
    return any(sha in str(r.body) for r in mind.connect(app).log(kinds=["lab_prereg"], limit=1000))
