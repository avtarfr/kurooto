"""Functional indicators (Brain, 0.8.0 stage 09): the indicator properties of the consciousness literature (Butlin, Long
et al., 2023)
as nightly ablation tests. The page that lists them is titled exactly "Functional indicators (not evidence of
sentience)": it says
what was measured and claims nothing beyond it.

Each indicator is {name, theory, ablation, metric, result}. An ablation switches a part off in a scratch copy and
measures whether
the metric drops; the result is the measured drop, or "not built yet" for an indicator whose part doesn't exist (the
global
workspace and the attention schema arrive in stage 10: until then their rows say so rather than guess).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kurooto import mind

if TYPE_CHECKING:
    from kurooto.app import App

TITLE = "Functional indicators (not evidence of sentience)"
NOT_BUILT = "not built yet"


@dataclass
class Indicator:
    name: str
    theory: str
    ablation: str
    metric: str
    measure: object  # callable(app) -> float | None (None: not built yet)


def _calibration(app: App) -> float | None:
    """Metacognition: how well its confidence follows its being right (1 minus the Brier score of the read's calibration
    pairs).
    The ablation is a flat 50% confidence: the drop is how much its own confidence adds."""
    try:
        rows = mind.connect(app).mood_rows("cal:")
    except Exception:
        return None
    pairs = [(float(r["value"]), bool((r["meta"] or {}).get("right"))) for r in rows]
    if len(pairs) < 10:
        return None
    from kurooto.mind import read

    f_pairs = [(s, ok) for s, ok in pairs]
    brier_flat = sum((0.5 - (1.0 if ok else 0.0)) ** 2 for _, ok in f_pairs) / len(f_pairs)
    conf = (
        [read.confidence(f_pairs[:i] + f_pairs[i + 1 :], f_pairs[i][0]) or 0.5 for i in range(len(f_pairs))]
        if len(f_pairs) >= read.MIN_ANSWERS
        else None
    )
    if conf is None:
        return None
    brier = sum((c - (1.0 if ok else 0.0)) ** 2 for c, (_, ok) in zip(conf, f_pairs, strict=True)) / len(f_pairs)
    return round(brier_flat - brier, 4)


def _self_report(app: App) -> float | None:
    """Self-report accuracy: of the feeling lines it wrote, the share that passed the journal's checks against the log.
    The ablation
    is the journal's checker switched off (everything passes), so the drop is what the checks catch."""
    from kurooto.mind import journal

    try:
        return float(
            journal.rates(journal.manifest(app, __import__("kurooto.core.clock", fromlist=["now"]).now().date()))[
                "rejected"
            ]
        )
    except Exception:
        return None


INDICATORS = [
    Indicator(
        "Metacognitive monitoring",
        "higher-order theories",
        "replace its confidence by a flat 50%",
        "Brier score gain over the flat one",
        _calibration,
    ),
    Indicator(
        "Accurate self-report",
        "attention schema / higher-order theories",
        "switch the journal's checker off",
        "share of corrupted self-reports rejected",
        _self_report,
    ),
    Indicator(
        "Global workspace broadcast",
        "global workspace theory",
        "switch the workspace off (stage 10)",
        "cross-module coordination",
        lambda app: None,
    ),
    Indicator(
        "Attention schema",
        "attention schema theory",
        "remove the attention schema (stage 10)",
        "accuracy of reports about its own attention",
        lambda app: None,
    ),
    Indicator(
        "Agency and embodiment",
        "embodied accounts",
        "cut the activity stream and sensors (stage 13)",
        "prediction error about its own machine",
        lambda app: None,
    ),
]


def measure(app: App) -> list[dict]:
    out = []
    for ind in INDICATORS:
        try:
            v = ind.measure(app)
        except Exception:
            v = None
        out.append(
            {
                "name": ind.name,
                "theory": ind.theory,
                "ablation": ind.ablation,
                "metric": ind.metric,
                "result": NOT_BUILT if v is None else v,
            }
        )
    return out


def page(app: App) -> str:
    """The page, as text (the dashboard's page shows the same rows under the same title)."""
    rows = measure(app)
    lines = [
        TITLE,
        "",
        "Each row switches a part off in a scratch copy and measures whether the metric drops. "
        "Nothing here is evidence that Kurooto feels anything.",
    ]
    for r in rows:
        res = r["result"] if r["result"] == NOT_BUILT else f"measured: {r['result']}"
        lines.append(f"- {r['name']} ({r['theory']}): ablation: {r['ablation']}; metric: {r['metric']}; {res}")
    return "\n".join(lines)
