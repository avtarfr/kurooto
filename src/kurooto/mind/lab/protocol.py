"""The lab protocol of a project: what to improve, how to run it, how to measure it, and what may change.

    [lab]
    objective = "minimise val_rmse"        # a direction and a metric name
    metric_cmd = "python eval.py"          # prints JSON holding the metric ("builtin:pytest" counts passing tests)
    run_cmd = "python train.py --config {config}"
    space = { lr = [1e-4, 1e-2, "log"], width = [32, 256, "int"] }    # or space = "free": the AI proposes small diffs
    budget_gpu_hours = 2
    max_runs = 200
    baseline = "results/best.json"         # a file holding the best metric so far, or a number

infer() drafts one from a folder (README, scripts, configs, tests, LaTeX); you approve or edit it once. It lives in
`<project>/.kurooto/lab.toml` when `mind.lab.in_repo` is on, else in Kurooto's own state (the repo is not touched).
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("search", "free", "tests", "writing")
DIRECTIONS = {"minimise": "min", "minimize": "min", "min": "min", "maximise": "max", "maximize": "max", "max": "max"}
RANGE_KINDS = ("log", "lin", "int")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOSSY = re.compile(r"\b(loss|rmse|mse|mae|error|perplexity)\b", re.I)


@dataclass
class Protocol:
    objective: str
    metric: str
    direction: str  # "min" | "max"
    run_cmd: str
    metric_cmd: str = ""
    space: dict | str = field(default_factory=dict)  # name -> [lo, hi, "log"|"lin"|"int"] | [choices...], or "free"
    kind: str = "search"
    budget_gpu_hours: float = 2.0
    max_runs: int = 200
    baseline: str = ""
    config_file: str = ""  # the file whose values the space sets (a winner is proposed as a change to it)
    min_effect: float = 0.01  # a win beats the baseline by at least this share of it
    seeds: int = 2  # runs a winner is replicated with, besides its first
    weak: bool = False  # a blind-judge rubric score: weak evidence, marked so
    inferred_from: list = field(default_factory=list)

    @property
    def free(self) -> bool:
        return self.space == "free"


def parse_objective(text: str) -> tuple[str, str] | None:
    m = re.match(r"^\s*([A-Za-z]+)\s+([A-Za-z_][\w.\-]*)\s*$", text or "")
    if not m or m[1].lower() not in DIRECTIONS:
        return None
    return DIRECTIONS[m[1].lower()], m[2]


def _range(v) -> bool:
    return (
        isinstance(v, list) and len(v) == 3 and v[2] in RANGE_KINDS and all(isinstance(x, (int, float)) for x in v[:2])
    )


def validate(raw: dict) -> tuple[Protocol | None, list[str]]:
    """(protocol, []) or (None, what is wrong), in words."""
    lab = raw.get("lab", raw) if isinstance(raw, dict) else {}
    bad: list[str] = []
    obj = parse_objective(str(lab.get("objective") or ""))
    if obj is None:
        bad.append('objective must be a direction and a metric, like "minimise val_rmse"')
    run = str(lab.get("run_cmd") or "").strip()
    if not run:
        bad.append("run_cmd is missing")
    metric_cmd = str(lab.get("metric_cmd") or "").strip()
    kind = str(lab.get("kind") or "")
    space = lab.get("space", {})
    if not kind:
        kind = "free" if space == "free" else "search"
    if kind not in KINDS:
        bad.append(f"kind must be one of {', '.join(KINDS)}")
    if kind in ("search", "free", "tests") and not metric_cmd and kind != "tests":
        bad.append("metric_cmd is missing (a command that prints JSON with the metric, or a file to read)")
    if space != "free":
        if not isinstance(space, dict):
            bad.append('space must be a table of parameters, or "free"')
            space = {}
        for k, v in space.items():
            if not NAME.match(str(k)):
                bad.append(f"parameter {k!r} isn't a plain name")
            elif not (_range(v) or (isinstance(v, list) and len(v) >= 2 and not _range(v))):
                bad.append(f"parameter {k}: use [low, high, 'log'|'lin'|'int'] or a list of choices")
        if kind == "search" and not space:
            bad.append('space is empty (name the parameters, or write space = "free")')
    try:
        budget = float(lab.get("budget_gpu_hours", 2))
        runs = int(lab.get("max_runs", 200))
        eff = float(lab.get("min_effect", 0.01))
        seeds = int(lab.get("seeds", 2))
    except (TypeError, ValueError):
        bad.append("budget_gpu_hours, max_runs, min_effect and seeds must be numbers")
        budget, runs, eff, seeds = 2.0, 200, 0.01, 2
    if budget <= 0 or runs <= 0 or not (0 < eff < 1) or seeds < 1:
        bad.append("budget_gpu_hours and max_runs must be above 0, min_effect between 0 and 1, seeds at least 1")
    if bad or obj is None:
        return None, bad
    return (
        Protocol(
            objective=str(lab["objective"]),
            metric=obj[1],
            direction=obj[0],
            run_cmd=run,
            metric_cmd=metric_cmd,
            space=space,
            kind=kind,
            budget_gpu_hours=budget,
            max_runs=min(runs, 2000),
            baseline=str(lab.get("baseline") or ""),
            config_file=str(lab.get("config_file") or ""),
            min_effect=eff,
            seeds=seeds,
            weak=bool(lab.get("weak", kind == "writing")),
            inferred_from=list(lab.get("inferred_from") or []),
        ),
        [],
    )


# ----------------------------------------------------------------------------------------------- reading and writing
def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_toml_value(x)}" for k, x in v.items()) + " }"
    return json.dumps(str(v))


def dumps(p: Protocol) -> str:
    rows = [
        ("objective", p.objective),
        ("kind", p.kind),
        ("run_cmd", p.run_cmd),
        ("metric_cmd", p.metric_cmd),
        ("space", p.space),
        ("budget_gpu_hours", p.budget_gpu_hours),
        ("max_runs", p.max_runs),
        ("baseline", p.baseline),
        ("config_file", p.config_file),
        ("min_effect", p.min_effect),
        ("seeds", p.seeds),
        ("weak", p.weak),
        ("inferred_from", p.inferred_from),
    ]
    return "[lab]\n" + "\n".join(f"{k} = {_toml_value(v)}" for k, v in rows) + "\n"


def loads(text: str) -> tuple[Protocol | None, list[str]]:
    try:
        return validate(tomllib.loads(text))
    except tomllib.TOMLDecodeError as e:
        return None, [f"the file isn't valid TOML ({e})"]


# ------------------------------------------------------------------------------------------------------ inference
def _read(p: Path, n: int = 20000) -> str:
    try:
        return p.read_text(errors="replace")[:n]
    except OSError:
        return ""


def _numeric_space(cfg: dict) -> dict:
    out: dict = {}
    for k, v in cfg.items():
        if not NAME.match(str(k)) or isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            continue
        if isinstance(v, int):
            out[k] = [max(1, v // 2), v * 4, "int"]
        elif re.search(r"lr|rate|decay|eps|tol", str(k), re.I) or v < 0.1:
            out[k] = [v / 10, v * 10, "log"]
        else:
            out[k] = [v / 2, v * 2, "lin"]
    return out


def infer(folder: Path) -> dict:
    """A draft protocol from a folder, as the dict `validate` takes plus `notes` (what it found and what it guessed)."""
    folder = Path(folder)
    top = {p.name: p for p in folder.iterdir() if p.is_file()} if folder.is_dir() else {}
    readme = next((_read(top[n]) for n in ("README.md", "README.rst", "README.txt", "README") if n in top), "")
    notes: list[str] = []
    seen: list[str] = [n for n in ("README.md", "pyproject.toml", "Makefile", "setup.cfg") if n in top]
    tex = [p for n, p in top.items() if n.endswith(".tex") and "\\documentclass" in _read(p, 4000)]
    train = next((n for n in top if re.match(r"^(train|run|main|fit)\w*\.py$", n)), "")
    evalf = next((n for n in top if re.match(r"^(eval|evaluate|score|metrics?)\w*\.py$", n)), "")
    cfgs = [n for n in top if re.match(r"^(config|params|settings|hparams)\w*\.(json|toml)$", n)]
    tests = (folder / "tests").is_dir() or any(n.startswith("test_") for n in top)
    if tex and not train:
        main = tex[0].name
        notes.append("a LaTeX document: the score is a blind-judge rubric, which is weak evidence")
        return {
            "lab": {
                "objective": "maximise rubric_score",
                "kind": "writing",
                "run_cmd": f"latexmk -pdf -interaction=nonstopmode {main}",
                "metric_cmd": "builtin:rubric",
                "space": "free",
                "max_runs": 20,
                "weak": True,
                "inferred_from": [*seen, main],
            },
            "notes": notes,
        }
    if train:
        seen.append(train)
        cfgfile = cfgs[0] if cfgs else ""
        cmd = f"python {train}"
        m = re.search(r"python3?\s+" + re.escape(train) + r"([^\n`]*)", readme)
        if m:
            cmd = "python " + train + m[1].rstrip()
        if cfgfile:
            cmd = re.sub(re.escape(cfgfile), "{config}", cmd) if cfgfile in cmd else f"{cmd} --config {{config}}"
        metric_name = "val_loss"
        if "rmse" in readme.lower():
            metric_name = "val_rmse"
        elif LOSSY.search(readme):
            metric_name = (LOSSY.search(readme) or [""])[0].lower()
        direction = "minimise" if LOSSY.search(readme) or "rmse" in metric_name or "loss" in metric_name else "maximise"
        if direction == "maximise" and "accuracy" in readme.lower():
            metric_name = "accuracy"
        metric_cmd = f"python {evalf}" if evalf else ""
        if evalf:
            seen.append(evalf)
        else:
            notes.append("no evaluation script found: set metric_cmd to a command that prints the metric as JSON")
        space: dict | str = "free"
        if cfgfile:
            seen.append(cfgfile)
            try:
                cfg = (
                    json.loads(_read(top[cfgfile])) if cfgfile.endswith(".json") else tomllib.loads(_read(top[cfgfile]))
                )
                space = _numeric_space(cfg) or "free"
            except (ValueError, tomllib.TOMLDecodeError):
                notes.append(f"couldn't read {cfgfile}")
        notes.append("the search ranges are guesses around the current values; check them")
        return {
            "lab": {
                "objective": f"{direction} {metric_name}",
                "kind": "search" if isinstance(space, dict) else "free",
                "run_cmd": cmd,
                "metric_cmd": metric_cmd,
                "space": space,
                "config_file": cfgfile,
                "inferred_from": seen,
            },
            "notes": notes,
        }
    if tests:
        notes.append("tests only: the objective is the number of passing tests (a test-driven project)")
        return {
            "lab": {
                "objective": "maximise tests_passed",
                "kind": "tests",
                "run_cmd": "python -m pytest -q",
                "metric_cmd": "builtin:pytest",
                "space": "free",
                "max_runs": 30,
                "inferred_from": [*seen, "tests"],
            },
            "notes": notes,
        }
    return {"lab": {}, "notes": ["nothing measurable found: write a lab.toml by hand (objective, run_cmd, metric_cmd)"]}
