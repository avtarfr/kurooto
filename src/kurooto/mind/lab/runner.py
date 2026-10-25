"""The lab's runner: a pre-registered batch of experiments on one project, in a sandbox, when the computer can spare it.

    projects(app)          the projects with a lab: `mind.lab.projects` (folders, or names of repository projects)
    status / approve       a protocol is a draft until you approve it; changing the file asks again
    ready(app)             on AC, lid open, not hot, the sandbox exists: else the batch waits (never a failure)
    run_batch(...)         baseline, register (the hash goes to the log first), run, replicate the winners, analyse,
                           propose; a suspend or a lost charger puts the rest back in the queue, uncounted
    nightly(app)           the night's batches, within `mind.lab.gpu_hours_per_night`

Nothing here changes your files: a winner arrives as a proposal (core/proposals.py) that only you apply.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core import power, scratch
from kurooto.core.state import jload, jsave
from kurooto.mind.lab import prereg, protocol, sandbox, scoring

if TYPE_CHECKING:
    from kurooto.app import App

COPY_MAX = 200 * 1024 * 1024  # bytes: a bigger folder that isn't a git repository isn't copied
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", ".kurooto"}
HOT_C = 85.0
RUN_MIN_S = 5.0
CONFIG_NAME = ".kurooto-config.json"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:40] or "project"


def folder(app: App, slug_: str) -> Path:
    return prereg.folder(app, slug_)


def projects(app: App) -> dict[str, Path]:
    """slug -> folder, from `mind.lab.projects` (full folder paths, or the names of repository projects)."""
    out: dict[str, Path] = {}
    named = None
    for item in app.settings.get("mind.lab.projects") or []:
        p = Path(os.path.expanduser(str(item)))
        if not p.is_dir():
            if named is None:
                from kurooto.core import repoproject

                named = {slug(Path(r.get("path") or r["key"]).name): r for r in repoproject.records(app).values()} | {
                    slug(r.get("name") or ""): r for r in repoproject.records(app).values() if r.get("name")
                }
            rec = named.get(slug(str(item)))
            p = Path(rec.get("path") or "") if rec else p
        if p.is_dir():
            out[slug(p.name)] = p
    return out


# ------------------------------------------------------------------------------------------------ the protocol
def protocol_file(app: App, slug_: str, root: Path) -> Path:
    if app.settings.get("mind.lab.in_repo"):
        return root / ".kurooto" / "lab.toml"
    return folder(app, slug_) / "lab.toml"


def draft(app: App, slug_: str, root: Path) -> tuple[str, list[str]]:
    """The protocol's text and notes: the file if there is one, else a draft inferred from the folder (and saved)."""
    f = protocol_file(app, slug_, root)
    if f.exists():
        return f.read_text(), []
    inferred = protocol.infer(root)
    p, bad = protocol.validate(inferred)
    notes = list(inferred.get("notes") or []) + bad
    if p is None:
        return "", notes
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(protocol.dumps(p))
    return f.read_text(), notes


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


def status(app: App, slug_: str, root: Path) -> tuple[str, protocol.Protocol | None, list[str]]:
    """("none" | "draft" | "approved" | "changed" | "invalid", protocol, problems)."""
    f = protocol_file(app, slug_, root)
    if not f.exists():
        return "none", None, []
    text = f.read_text()
    p, bad = protocol.loads(text)
    if p is None:
        return "invalid", None, bad
    ok = jload(folder(app, slug_) / "approved.json", {}) or {}
    if not ok.get("sha"):
        return "draft", p, []
    return ("approved" if ok["sha"] == _sha(text) else "changed"), p, []


def approve(app: App, slug_: str, root: Path) -> str:
    st, p, bad = status(app, slug_, root)
    if st in ("none", "invalid"):
        return "There's no valid protocol to approve: " + (
            "; ".join(bad) if bad else "write one first (/lab protocol)."
        )
    text = protocol_file(app, slug_, root).read_text()
    folder(app, slug_).mkdir(parents=True, exist_ok=True)
    jsave(folder(app, slug_) / "approved.json", {"sha": _sha(text), "at": time.time()})
    return f"Approved: {p.objective} on {slug_}. Changing the file asks again."


# ----------------------------------------------------------------------------------------------- scheduling
def lid_open() -> bool:
    for f in Path("/proc/acpi/button").glob("lid/*/state"):
        try:
            return "closed" not in f.read_text()
        except OSError:
            continue
    return True  # no lid (or none we can read)


def hot() -> bool:
    try:
        import psutil

        temps = getattr(psutil, "sensors_temperatures", lambda: {})()
        cur = [t.current for ts in temps.values() for t in ts if t.current]
        return bool(cur) and max(cur) >= HOT_C
    except Exception:
        return False


def ready(app: App) -> tuple[bool, str]:
    """May a run start now? (True, "") or (False, why). The lab never keeps the computer awake."""
    if not mind.part_on(app, "lab"):
        return False, "the lab is off (mind.lab.on)"
    why = sandbox.unavailable(app)
    if why:
        return False, why
    if not power.on_ac():
        return False, "it isn't on the charger"
    if not lid_open():
        return False, "the lid is closed"
    if hot():
        return False, "the computer is hot"
    return True, ""


# ------------------------------------------------------------------------------------------------- sampling
def sample(space: dict, n: int, seed: int) -> list[dict]:
    """n configurations by seeded random search (the same seed gives the same list)."""
    import math

    rng = random.Random(seed)  # noqa: S311
    out: list[dict] = []
    for _ in range(n):
        cfg: dict = {}
        for k, v in space.items():
            if protocol._range(v):  # noqa: SLF001
                lo, hi, how = v
                if how == "log":
                    cfg[k] = round(math.exp(rng.uniform(math.log(lo), math.log(hi))), 8)
                elif how == "int":
                    cfg[k] = rng.randint(int(lo), int(hi))
                else:
                    cfg[k] = round(rng.uniform(lo, hi), 8)
            else:
                cfg[k] = rng.choice(v)
        out.append(cfg)
    return out


# ------------------------------------------------------------------------------------------------ one run
def prepare(app: App, root: Path, dest: Path) -> tuple[Path, scratch.Scratch | None]:
    """A private copy of the project to run in (and the scratch folder to remove after, if it's a worktree): its
    committed files for a git repository, else a filtered copy."""
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    if (root / ".git").exists():
        sc = scratch.create(app, root, label="lab", project="lab")
        return sc.work, sc
    total = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if scratch.secret(f):
                continue
            try:
                total += (Path(dp) / f).stat().st_size
            except OSError:
                continue
    if total > COPY_MAX:
        raise RuntimeError(
            "the folder is too big to copy for a run; put the project in git so the lab can use a worktree"
        )

    def ignore(d, names):
        return [n for n in names if n in SKIP_DIRS or scratch.secret(n)]

    shutil.copytree(root, dest, ignore=ignore)
    return dest, None


def read_config(root: Path, proto: protocol.Protocol) -> dict:
    f = root / proto.config_file if proto.config_file else None
    if not f or not f.is_file():
        return {}
    try:
        if f.suffix == ".json":
            return json.loads(f.read_text())
        import tomllib

        return tomllib.loads(f.read_text())
    except (OSError, ValueError):
        return {}


def find_metric(text: str, name: str) -> float | None:
    """The metric from a command's output: the last JSON object holding `name` (at any depth), or `name: number`."""

    def dig(o):
        if isinstance(o, dict):
            if name in o and isinstance(o[name], (int, float)) and not isinstance(o[name], bool):
                return float(o[name])
            for v in o.values():
                r = dig(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = dig(v)
                if r is not None:
                    return r
        return None

    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith(("{", "[")):
            try:
                r = dig(json.loads(line))
                if r is not None:
                    return r
            except ValueError:
                continue
    try:
        r = dig(json.loads(text.strip()))
        if r is not None:
            return r
    except ValueError:
        pass
    m = re.findall(re.escape(name) + r"\s*[:=]\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", text)
    return float(m[-1]) if m else None


def pytest_passed(text: str) -> float | None:
    m = re.findall(r"(\d+) passed", text)
    return float(m[-1]) if m else None


def execute(app: App, proto: protocol.Protocol, root: Path, slug_: str, exp: dict, wall_s: float) -> dict:
    """Run one experiment {id, config, seed, files?} and read its metric: {id, config, seed, value, ok, seconds, why,
    requeue}. A failed run is a result with ok False; a suspend is `requeue` (not counted)."""
    base = {"id": exp["id"], "config": exp.get("config", {}), "seed": exp.get("seed", 0), "value": None, "ok": False}
    if exp.get("files"):
        base["files"] = exp["files"]
    dest = folder(app, slug_) / "runs" / f"{exp['id']}-s{exp.get('seed', 0)}"
    try:
        work, sc = prepare(app, root, dest)
    except Exception as e:
        return {**base, "seconds": 0.0, "why": f"couldn't prepare: {e}"[:200], "requeue": False}
    try:
        cfg = exp.get("config") or {}
        (work / CONFIG_NAME).write_text(json.dumps(cfg))
        if proto.config_file and (work / proto.config_file).suffix == ".json":
            merged = {**read_config(work, proto), **cfg}
            (work / proto.config_file).write_text(json.dumps(merged))
        for rel, text in (exp.get("files") or {}).items():
            if scratch.clean_rel(rel) and not scratch.secret(rel):
                (work / rel).parent.mkdir(parents=True, exist_ok=True)
                (work / rel).write_text(text)
        cmd = proto.run_cmd.replace("{config}", CONFIG_NAME).replace("{seed}", str(exp.get("seed", 0)))
        r = sandbox.run(app, work, cmd, wall_s, gpu=bool(app.settings.get("mind.lab.gpu")))
        if r["suspended"]:
            return {**base, "seconds": r["seconds"], "why": "the computer slept", "requeue": True}
        if not r["ran"] or not r["ok"]:
            return {
                **base,
                "seconds": r["seconds"],
                "why": (r["why"] or r["out"][-200:] or "failed")[:200],
                "requeue": False,
            }
        text = r["out"]
        if proto.metric_cmd and not proto.metric_cmd.startswith("builtin:"):
            m = sandbox.run(app, work, proto.metric_cmd, min(wall_s, 300))
            if m["suspended"]:
                return {**base, "seconds": r["seconds"], "why": "the computer slept", "requeue": True}
            text = m["out"] if m["ok"] else ""
        value = pytest_passed(text) if proto.metric_cmd == "builtin:pytest" else find_metric(text, proto.metric)
        if value is None:
            return {**base, "seconds": r["seconds"], "why": f"no {proto.metric} in the output", "requeue": False}
        return {**base, "value": value, "ok": True, "seconds": r["seconds"], "why": "", "requeue": False}
    finally:
        if sc is not None:
            scratch.remove(app, sc)
        shutil.rmtree(dest, ignore_errors=True)


def baseline_value(app: App, proto: protocol.Protocol, root: Path, slug_: str, executor, wall_s: float) -> float | None:
    """The best metric so far: the baseline file, a number, or a run of the project as it is."""
    b = proto.baseline.strip()
    if b:
        try:
            return float(b)
        except ValueError:
            f = root / b
            if f.is_file():
                v = find_metric(f.read_text(), proto.metric)
                if v is not None:
                    return v
    r = executor(app, proto, root, slug_, {"id": "baseline", "config": read_config(root, proto), "seed": 0}, wall_s)
    return r["value"] if r.get("ok") else None


# ------------------------------------------------------------------------------------------------ the batch
def _queue_file(app: App, slug_: str) -> Path:
    return folder(app, slug_) / "queue.json"


def plan(app: App, proto: protocol.Protocol, root: Path, slug_: str, proposer=None) -> list[dict]:
    """The batch's experiments {id, config, seed, files?}: sampled from the space, or proposed small diffs (free)."""
    n = min(proto.max_runs, int(app.settings.get("mind.lab.max_per_night") or 40))
    if isinstance(proto.space, dict) and proto.space:
        seed = int(app.settings.get("mind.lab.seed") or time.time() // 86400)
        return [{"id": f"c{i:03d}", "config": c, "seed": 0} for i, c in enumerate(sample(proto.space, n, seed))]
    if proposer is None:
        return []
    return [
        {"id": f"d{i:03d}", "config": {}, "seed": 0, "files": files}
        for i, files in enumerate(proposer(app, proto, root, min(n, 10)))
    ]


def ask_json(app: App, prompt: str, title: str):
    """One AI request whose answer is JSON, waited for (a background job, low effort); None when it isn't."""
    jid = app.jobs.submit(prompt, title=title, effort="low", background=True, text_only=True, quiet=True, lane="bg")
    for _ in range(300):
        job = app.jobs.get(jid)
        if job and job.status in ("ok", "failed", "cancelled"):
            try:
                return json.loads(str(getattr(job, "text", "") or getattr(job, "result", "") or ""))
            except ValueError:
                return None
        time.sleep(1)
    return None


def ai_proposer(app: App, proto: protocol.Protocol, root: Path, n: int) -> list[dict]:
    """Free experiments: ask your AI for up to n small independent code changes as {path: new full text} (JSON)."""
    files = {
        str(p.relative_to(root)): p.read_text(errors="replace")[:4000]
        for p in sorted(root.glob("*.py"))[:6]
        if not scratch.secret(p.name)
    }
    prompt = (
        f"Goal: {proto.objective}. Propose up to {n} small, independent code changes that might improve it. "
        "Answer with "
        'JSON only: a list of objects {"path": "relative/file.py", "text": "the whole new file"}.\nFiles: '
        + json.dumps(files)
    )
    got = ask_json(app, prompt, "Lab: propose changes")
    out = []
    for it in got if isinstance(got, list) else []:
        if isinstance(it, dict) and isinstance(it.get("path"), str) and isinstance(it.get("text"), str):
            out.append({it["path"]: it["text"][:60000]})
    return out[:n]


def run_batch(
    app: App,
    slug_: str,
    root: Path,
    *,
    executor=None,
    ready_fn=None,
    proposer=None,
    hypothesis: str = "",
    budget_s: float | None = None,
) -> dict:
    """One pre-registered batch. Returns {"ran", "why", "batch", "analysis", ...}. Never raises."""
    executor = executor or execute
    ready_fn = ready_fn or ready
    st, proto, bad = status(app, slug_, root)
    if st != "approved" or proto is None:
        return {
            "ran": False,
            "why": {
                "none": "no protocol yet",
                "draft": "the protocol isn't approved",
                "changed": "the protocol changed since you approved it",
                "invalid": "; ".join(bad),
            }.get(st, st),
        }
    ok, why = ready_fn(app)
    if not ok:
        return {"ran": False, "why": why}
    budget = float(budget_s if budget_s is not None else proto.budget_gpu_hours * 3600)
    wall_s = float(min(max(budget, RUN_MIN_S), float(app.settings.get("mind.lab.run_wall_s") or 1800)))
    qf = _queue_file(app, slug_)
    q = jload(qf, {}) or {}
    t_start = time.monotonic()
    if not q.get("pending") and not q.get("batch"):
        base = baseline_value(app, proto, root, slug_, executor, wall_s)
        if base is None:
            return {"ran": False, "why": "couldn't measure the baseline (the project's own run or metric failed)"}
        exps = plan(app, proto, root, slug_, proposer or (ai_proposer if proto.free else None))
        if not exps:
            return {"ran": False, "why": "nothing to try (empty space, and no AI to propose changes)"}
        batch = len(list(folder(app, slug_).glob("prereg-*.json"))) + 1
        what = ", ".join(proto.space) if isinstance(proto.space, dict) else "the code"
        rec = prereg.make(
            slug_,
            proto,
            hypothesis or f"some settings of {what} improve {proto.metric}",
            [
                {k: e[k] for k in ("id", "config") if k in e}
                | ({"files": sorted(e["files"])} if e.get("files") else {})
                for e in exps
            ],
            base,
        )
        prereg.register(app, slug_, rec)  # the hash is in the log before the first experiment runs
        q = {"batch": batch, "baseline": base, "pending": exps, "firsts": [], "repeats": {}, "phase": 1, "fails": 0}
        jsave(qf, q)
    batch, base = int(q["batch"]), float(q["baseline"])
    # phase 1 (first seeds) then phase 2 (replicate the winners); each run re-checks that the computer can spare it
    interrupted = ""
    while q["pending"]:
        if time.monotonic() - t_start > budget:
            interrupted = "the night's GPU-hour budget was used"
            break
        ok, why = ready_fn(app)
        if not ok:
            interrupted = why
            break
        exp = q["pending"][0]
        res = executor(app, proto, root, slug_, exp, wall_s)
        if res.get("requeue"):
            interrupted = "the computer slept (the run is queued again, not counted)"
            break
        q["pending"].pop(0)
        if q["phase"] == 1:
            q["firsts"].append(res)
            if not res["ok"]:
                q["fails"] += 1
        else:
            q["repeats"].setdefault(exp["id"], []).append(res)
        jsave(qf, q)
        if not q["pending"] and q["phase"] == 1:
            q["phase"] = 2
            for w in scoring.wins(q["firsts"], base, proto.direction, proto.min_effect):
                src = next(e for e in plan_cache(q, w["id"]))
                for k in range(1, proto.seeds + 1):
                    q["pending"].append({**src, "seed": k})
            jsave(qf, q)
    if q["pending"]:
        return {
            "ran": True,
            "finished": False,
            "why": interrupted,
            "batch": batch,
            "done": len(q["firsts"]),
            "left": len(q["pending"]),
        }
    rec = prereg.load(app, slug_, batch) or {}
    analysis = scoring.analyse(rec, q["firsts"], q["repeats"], base)
    jsave(
        folder(app, slug_) / f"results-{batch:04d}.json",
        {"analysis": analysis, "firsts": q["firsts"], "repeats": q["repeats"], "baseline": base},
    )
    qf.unlink(missing_ok=True)
    mind.connect(app).report(
        "lab_result",
        {
            "project": slug_,
            "batch": batch,
            "ok": analysis["n_ok"],
            "failed": analysis["n_failed"],
            "wins": len(analysis["wins"]),
            "replicated": len(analysis["replicated"]),
            "rate": analysis["rate"] if analysis["rate"] is not None else -1.0,
            "nulls": len(analysis["nulls"]),
        },
    )
    prop = propose(app, slug_, root, proto, analysis, q, rec) if analysis["best"] else None
    return {"ran": True, "finished": True, "batch": batch, "analysis": analysis, "proposal": prop, "baseline": base}


def plan_cache(q: dict, exp_id: str):
    """The experiment dict of a first-seed result (its config and files), to run again with another seed."""
    for r in q["firsts"]:
        if r["id"] == exp_id:
            yield {"id": r["id"], "config": r["config"], **({"files": r["files"]} if r.get("files") else {})}
            return


# ------------------------------------------------------------------------------------------------ the winner
def propose(
    app: App, slug_: str, root: Path, proto: protocol.Protocol, analysis: dict, q: dict, rec: dict
) -> str | None:
    """The best replicated winner as a proposal (a change to the config file, or the proposed files). You apply it."""
    from kurooto.core import proposals

    best = analysis["best"]
    if proto.weak or proto.kind in ("tests", "writing"):
        return None  # weak evidence or no change to make: the digest says it, no proposal
    try:
        sc = scratch.create(app, root, label=f"lab: {slug_}", project=slug_)
    except Exception:
        return None
    changed = False
    if best.get("files"):
        for rel, text in best["files"].items():
            if scratch.clean_rel(rel) and not scratch.secret(rel):
                scratch.write(sc, rel, text)
                changed = True
    elif proto.config_file and best.get("config"):
        cur = scratch.read(sc, proto.config_file)
        if cur is not None and proto.config_file.endswith(".json"):
            try:
                cfg = json.loads(cur)
            except ValueError:
                cfg = None
            if isinstance(cfg, dict):
                cfg.update(best["config"])
                scratch.write(sc, proto.config_file, json.dumps(cfg, indent=2) + "\n")
                changed = True
    if not changed:
        scratch.remove(app, sc)
        return None
    pct = round((analysis["best_gain"] or 0.0) * 100, 1)
    reps = len(q["repeats"].get(best["id"], []))
    what = ", ".join(f"{k} = {v}" for k, v in (best.get("config") or {}).items()) or "a code change"
    p, why = proposals.make(
        app,
        sc,
        f"Lab: {proto.metric} {pct}% better on {slug_}",
        f"{what}: {best['value']} against "
        f"{q['baseline']} ({pct}% better), replicated in {reps} more run(s). Pre-registered batch {q['batch']}.",
        request=rec.get("hypothesis", ""),
        source="lab",
        night=True,
        meta={"lab_batch": q["batch"], "project": slug_},
    )
    return p["id"] if p else None


# ------------------------------------------------------------------------------------------------ the night
def nightly(app: App, payload: dict | None = None) -> dict:
    """Each approved project's batch, within `mind.lab.gpu_hours_per_night`; the digest is sent in the morning."""
    if not mind.part_on(app, "lab"):
        return {}
    budget = float(app.settings.get("mind.lab.gpu_hours_per_night") or 2) * 3600
    t0 = time.monotonic()
    out = {}
    for slug_, root in projects(app).items():
        left = budget - (time.monotonic() - t0)
        if left < RUN_MIN_S:
            break
        res = run_batch(app, slug_, root, budget_s=left)
        out[slug_] = res
    jsave(
        app.paths.state / "lab" / "last-night.json",
        {
            "at": time.time(),
            "projects": {
                k: {x: v[x] for x in v if x in ("ran", "why", "finished", "batch", "done", "left")}
                | (
                    {
                        "rate": v["analysis"]["rate"],
                        "wins": len(v["analysis"]["wins"]),
                        "replicated": len(v["analysis"]["replicated"]),
                        "nulls": v["analysis"]["nulls"],
                        "n": v["analysis"]["n_ok"] + v["analysis"]["n_failed"],
                    }
                    if v.get("analysis")
                    else {}
                )
                for k, v in out.items()
            },
        },
    )
    return out
