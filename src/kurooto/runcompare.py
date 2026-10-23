"""Run compare (the Research add-on): two experiment runs side by side, written into the project's notes.

    kurooto runlog diff A B        on a terminal (the ids, or a unique piece of them, as `kurooto runlog ls` shows)
    /runs compare A B              on Telegram or the phone app; /runs lists recent runs, /runs compare alone the
                                   last two of one project

What it compares: the config (keys changed, added, dropped, nested keys flattened to a.b.c), the code (a diff between
the two runs' git commits, read-only: `git diff`, nothing is checked out or changed; and whether either run had
uncommitted changes, kept in its diff.patch), the metrics (last and lowest value of each, and the change), and the
curves (a PNG of each metric over the steps when matplotlib is in Kurooto's Python, else a text sparkline per run).

Where it goes: a comparison note runs/compare/<A>--<B>.md in the project's runs folder (the whole note is Kurooto's
block, so running it again replaces it), the PNG beside it, and a line in the project note's `run-compare` block
(the last ten comparisons). Nothing outside Kurooto's blocks is changed (core/graphwrite.py). Nothing leaves the
computer.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from kurooto.core import graphwrite, proc
from kurooto.core.state import jload

CODE_DIFF_MAX = 200_000  # characters of `git diff` kept in the note
SPARK = "▁▂▃▄▅▆▇█"
KEPT = 10  # comparisons listed in the project note
CURVES = 4  # metrics drawn


class CompareError(Exception):
    pass


@dataclass
class RunInfo:
    id: str
    dir: Path
    meta: dict
    config: dict
    rows: list[dict] = field(default_factory=list)

    @property
    def name(self) -> str:
        return str(self.meta.get("name") or self.id)


def load(d: Path) -> RunInfo:
    """A run's folder (as `kurooto runlog` or kurooto.runlog.Run writes it)."""
    meta = jload(d / "meta.json", None)
    if not isinstance(meta, dict):
        raise CompareError(f"{d.name} has no meta.json: not a run folder")
    cfg = jload(d / "config.json", {}) or {}
    rows = []
    try:
        for ln in (d / "metrics.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict):
                rows.append(r)
    except OSError:
        pass
    return RunInfo(d.name, d, meta, cfg if isinstance(cfg, dict) else {"config": cfg}, rows)


# ---------------------------------------------------------------------------------------------- finding runs
def all_runs(rl, repo_dirs: list[Path] | None = None) -> list[tuple[str, Path]]:
    """Every run Kurooto knows: the ones in your notes (runlog's own list), and those kept in a repository's runs
    folder (`repo_dirs`: <repo>/runs for each repository Research follows). Newest first (ids start with the time)."""
    out: dict[str, Path] = {}
    for rid, r in (rl._state().get("runs") or {}).items():
        d = Path(r.get("dir") or "")
        if (d / "meta.json").is_file():
            out[rid] = d
    for base in repo_dirs or []:
        try:
            kids = sorted(base.iterdir())[-500:]
        except OSError:
            continue
        for d in kids:
            if d.is_dir() and (d / "meta.json").is_file():
                out.setdefault(d.name, d)
    return sorted(out.items(), key=lambda kv: kv[0], reverse=True)


def find(runs: list[tuple[str, Path]], ref: str) -> tuple[str, Path]:
    """A run by its id, a unique start or end of it, or its number in the /runs listing (1 is the newest)."""
    ref = ref.strip()
    if not ref:
        raise CompareError("which run?")
    if re.fullmatch(r"\d{1,2}", ref) and 1 <= int(ref) <= len(runs):
        return runs[int(ref) - 1]
    exact = [r for r in runs if r[0] == ref]
    if exact:
        return exact[0]
    hits = [r for r in runs if r[0].startswith(ref) or r[0].endswith(ref)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise CompareError(f"no run {ref!r} (`kurooto runlog ls` or /runs lists them)")
    raise CompareError(f"{ref!r} matches {len(hits)} runs; give more of it")


# ------------------------------------------------------------------------------------------------- config
def flat(cfg, prefix: str = "") -> dict:
    """{"opt": {"lr": 0.1}} -> {"opt.lr": 0.1}; lists stay whole."""
    out = {}
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict) and v:
                out.update(flat(v, key))
            else:
                out[key] = v
    elif prefix:
        out[prefix] = cfg
    return out


MISSING = object()


def config_diff(a: dict, b: dict) -> list[tuple[str, object, object]]:
    """(key, A's value, B's value) for each key that differs; MISSING where a run doesn't have it."""
    fa, fb = flat(a), flat(b)
    out = []
    for k in sorted(set(fa) | set(fb)):
        va, vb = fa.get(k, MISSING), fb.get(k, MISSING)
        if (
            va is MISSING
            or vb is MISSING
            or json.dumps(va, sort_keys=True, default=str) != json.dumps(vb, sort_keys=True, default=str)
        ):
            out.append((k, va, vb))
    return out


def _v(v) -> str:
    if v is MISSING:
        return "(not set)"
    if isinstance(v, float):
        return f"{v:.6g}"
    s = json.dumps(v, default=str) if not isinstance(v, str) else v
    return s if len(s) <= 60 else s[:57] + "..."


# ------------------------------------------------------------------------------------------------ metrics
def _num(v) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def series(rows: list[dict]) -> dict[str, list[tuple[float, float]]]:
    """Each numeric metric as (step, value) points: the step a row gave, else its place in the file."""
    out: dict[str, list[tuple[float, float]]] = {}
    for i, r in enumerate(rows):
        x = _num(r.get("step"))
        x = float(i) if x is None else x
        for k, v in r.items():
            if k in ("time", "step"):
                continue
            y = _num(v)
            if y is not None:
                out.setdefault(str(k), []).append((x, y))
    return out


def _order(names) -> list[str]:
    """Loss-like metrics first, then the rest as they came."""
    names = list(names)
    return sorted(names, key=lambda n: (0 if "loss" in n.lower() else 1, names.index(n)))


def metric_rows(a: RunInfo, b: RunInfo) -> list[dict]:
    sa, sb = series(a.rows), series(b.rows)
    if not sa and not sb:  # no metrics.jsonl: what meta.json kept at the end (a run kept in a repository)
        sa = {k: [(0.0, float(v))] for k, v in (a.meta.get("last") or {}).items() if _num(v) is not None}
        sb = {k: [(0.0, float(v))] for k, v in (b.meta.get("last") or {}).items() if _num(v) is not None}
    rows = []
    for k in _order(dict.fromkeys([*sa, *sb])):
        pa, pb = sa.get(k) or [], sb.get(k) or []
        la, lb = (pa[-1][1] if pa else None), (pb[-1][1] if pb else None)
        rows.append(
            {
                "metric": k,
                "a": la,
                "b": lb,
                "a_min": min(y for _, y in pa) if pa else None,
                "b_min": min(y for _, y in pb) if pb else None,
                "change": (lb - la) if la is not None and lb is not None else None,
                "pct": ((lb - la) / abs(la) * 100) if la not in (None, 0) and lb is not None else None,
                "pa": pa,
                "pb": pb,
            }
        )
    return rows


def _n(v) -> str:
    return "" if v is None else f"{v:.4g}"


def _change(r: dict) -> str:
    if r["change"] is None:
        return ""
    s = f"{r['change']:+.4g}"
    return s + (f" ({r['pct']:+.0f}%)" if r["pct"] is not None else "")


def resample(ys: list[float], n: int) -> list[float]:
    if len(ys) <= n:
        return ys
    return [ys[min(len(ys) - 1, round(i * (len(ys) - 1) / (n - 1)))] for i in range(n)]


def sparkline(ys: list[float], lo: float, hi: float, width: int = 32) -> str:
    """Values as block characters, on a shared scale (lo..hi) so two runs compare at a glance."""
    if not ys:
        return ""
    span = hi - lo
    return "".join(
        SPARK[0 if span <= 0 else min(len(SPARK) - 1, int((y - lo) / span * (len(SPARK) - 1) + 0.5))]
        for y in resample(ys, width)
    )


def spark_table(rows: list[dict]) -> list[str]:
    """The text curves: a sparkline per run for each metric with at least two points."""
    out = []
    for r in [r for r in rows if len(r["pa"]) > 1 or len(r["pb"]) > 1][:CURVES]:
        ys = [y for _, y in r["pa"]] + [y for _, y in r["pb"]]
        lo, hi = min(ys), max(ys)
        w = max(len(r["metric"]), 6)
        for tag, pts in (("A", r["pa"]), ("B", r["pb"])):
            vals = [y for _, y in pts]
            ends = f"  {_n(vals[0])} → {_n(vals[-1])}" if vals else "  (none)"
            out.append(f"{(r['metric'] if tag == 'A' else ''):<{w}} {tag} {sparkline(vals, lo, hi)}{ends}")
    return out


def has_matplotlib() -> bool:
    import importlib.util

    return importlib.util.find_spec("matplotlib") is not None


def curves_png(path: Path, rows: list[dict], a: RunInfo, b: RunInfo) -> bool:
    """A PNG of each metric over the steps, both runs on one plot (with matplotlib, when Kurooto's Python has it)."""
    drawn = [r for r in rows if len(r["pa"]) > 1 or len(r["pb"]) > 1][:CURVES]
    if not drawn or not has_matplotlib():
        return False
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(len(drawn), 1, figsize=(7, 2.6 * len(drawn)), squeeze=False)
        for ax, r in zip(axes[:, 0], drawn, strict=False):
            for pts, label in ((r["pa"], f"A: {a.name}"), (r["pb"], f"B: {b.name}")):
                if pts:
                    ax.plot([x for x, _ in pts], [y for _, y in pts], label=label, linewidth=1.4)
            ax.set_title(r["metric"], fontsize=10)
            ax.set_xlabel("step", fontsize=8)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        fig.tight_layout()
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=110)
        plt.close(fig)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------------------------------- code
def _git(git: str, repo: Path, *a: str, timeout: int = 60):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
    return proc.run([git, "-C", str(repo), *a], timeout=timeout, env=env)


def code_diff(git: str | None, a: RunInfo, b: RunInfo) -> dict:
    """The code between the two runs: {"note": what to say, "stat": git's summary, "diff": the diff (capped),
    "commits": how many commits apart}. Read-only: git diff and git log, nothing checked out."""
    ca, cb = str(a.meta.get("commit") or ""), str(b.meta.get("commit") or "")
    dirty = [f"{t} had uncommitted changes (its diff.patch)" for t, r in (("A", a), ("B", b)) if r.meta.get("dirty")]
    out = {"note": "", "stat": "", "diff": "", "commits": None, "dirty": dirty}
    if not ca or not cb:
        out["note"] = "No git commit recorded for " + ("either run" if not ca and not cb else "A" if not ca else "B")
        return out
    if ca == cb:
        out["note"] = f"Same commit ({ca[:10]})"
        return out
    if not git:
        out["note"] = f"Commits {ca[:10]} and {cb[:10]} (git isn't installed, so no diff)"
        return out
    repo = None
    for r in (b, a):
        cwd = Path(str(r.meta.get("cwd") or ""))
        if cwd.is_dir():
            top = _git(git, cwd, "rev-parse", "--show-toplevel").out.strip()
            if top:
                repo = Path(top)
                break
    if repo is None:
        out["note"] = f"Commits {ca[:10]} and {cb[:10]} (the repository isn't on this computer any more)"
        return out
    missing = [c[:10] for c in (ca, cb) if not _git(git, repo, "cat-file", "-e", f"{c}^{{commit}}").ok]
    if missing:
        out["note"] = f"Commits {ca[:10]} and {cb[:10]} ({', '.join(missing)} isn't in {repo.name} any more)"
        return out
    n = _git(git, repo, "rev-list", "--count", f"{ca}..{cb}").out.strip()
    back = _git(git, repo, "rev-list", "--count", f"{cb}..{ca}").out.strip()
    out["commits"] = int(n) if n.isdigit() else None
    out["stat"] = _git(git, repo, "diff", "--stat", ca, cb).out.rstrip()
    diff = _git(git, repo, "diff", ca, cb).out
    if len(diff) > CODE_DIFF_MAX:
        diff = diff[:CODE_DIFF_MAX] + f"\n... (cut: the whole diff is `git diff {ca[:10]} {cb[:10]}` in {repo.name})"
    out["diff"] = diff
    files = len([ln for ln in out["stat"].splitlines()[:-1]]) if out["stat"] else 0
    apart = f"{n} commit{'s' if n != '1' else ''} after A" if n.isdigit() and n != "0" else ""
    if back.isdigit() and back != "0":
        apart = (apart + ", " if apart else "") + f"{back} before it"
    out["note"] = (
        f"{repo.name}: {ca[:10]} → {cb[:10]}" + (f" ({apart})" if apart else "") + f", {files} file"
        f"{'s' if files != 1 else ''} changed"
    )
    return out


# ------------------------------------------------------------------------------------------------- compare
def _took(secs) -> str:
    try:
        secs = int(float(secs))
    except (TypeError, ValueError):
        return ""
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{secs % 3600 // 60:02d}m"


def headline(cfg: list, code: dict, rows: list[dict]) -> str:
    """One line: what changed and what came of it."""
    bits = []
    if cfg:
        shown = "; ".join(f"{k} {_v(va)} → {_v(vb)}" for k, va, vb in cfg[:2])
        bits.append(
            f"{len(cfg)} config change{'s' if len(cfg) != 1 else ''} ({shown}{'; ...' if len(cfg) > 2 else ''})"
        )
    else:
        bits.append("same config")
    bits.append(code["note"][0].lower() + code["note"][1:] if code["note"] else "")
    r = next((r for r in rows if r["change"] is not None), None)
    if r:
        bits.append(
            f"{r['metric']} {_n(r['a'])} → {_n(r['b'])}" + (f" ({r['pct']:+.0f}%)" if r["pct"] is not None else "")
        )
    return "; ".join(b for b in bits if b)


def note_text(a: RunInfo, b: RunInfo, cfg: list, code: dict, rows: list[dict], png: str, link) -> str:
    """The comparison note's body (inside Kurooto's block)."""
    L = [f"# Runs compared: {a.name} vs {b.name}", ""]
    L.append(f"Compared {dt.datetime.now():%Y-%m-%d %H:%M}. A is [[{link(a)}|{a.id}]], B is [[{link(b)}|{b.id}]].")
    L += ["", "| | A | B |", "|---|---|---|"]
    for label, key in (("started", "start"), ("status", "status"), ("branch", "branch")):
        va, vb = (str(r.meta.get(key) or "").replace("T", " ") for r in (a, b))
        L.append(f"| {label} | {va} | {vb} |")
    L.append(f"| took | {_took(a.meta.get('duration_s'))} | {_took(b.meta.get('duration_s'))} |")
    L.append(f"| commit | {str(a.meta.get('commit') or '')[:10]} | {str(b.meta.get('commit') or '')[:10]} |")
    L += ["", "## Config", ""]
    if cfg:
        L += ["| key | A | B |", "|---|---|---|"]
        L += [f"| `{k}` | {_v(va)} | {_v(vb)} |" for k, va, vb in cfg]
    else:
        L.append("The same in both runs.")
    L += ["", "## Code", "", (code["note"] or "Nothing to compare") + "."]
    L += [f"- {d}" for d in code["dirty"]]
    if code["stat"]:
        L += ["", "```", code["stat"], "```"]
    if code["diff"]:
        L += ["", "<details><summary>The diff</summary>", "", "```diff", code["diff"].rstrip(), "```", "", "</details>"]
    L += ["", "## Metrics", ""]
    if rows:
        L += ["| metric | A last | B last | change | A lowest | B lowest |", "|---|---|---|---|---|---|"]
        L += [
            f"| {r['metric']} | {_n(r['a'])} | {_n(r['b'])} | {_change(r)} | {_n(r['a_min'])} | {_n(r['b_min'])} |"
            for r in rows[:40]
        ]
    else:
        L.append("Neither run logged any numbers.")
    if png:
        L += ["", "## Curves", "", f"![curves]({png})"]
    else:
        spark = spark_table(rows)
        if spark:
            L += ["", "## Curves", "", "```", *spark, "```"]
    return "\n".join(L)


def compare(rl, ref_a: str, ref_b: str, repo_dirs: list[Path] | None = None, project_of=None) -> dict:
    """Compare two runs and write the comparison into the project's notes. `rl`: a runlog.Runlog (its notes and
    state); `repo_dirs`: runs folders kept in repositories; `project_of(run)`: the project for a run kept in a
    repository (default: its repository folder's name). Returns {"summary", "note", "png", "project"}."""
    from kurooto.runlog import _git_exe

    runs = all_runs(rl, repo_dirs)
    ia, da = find(runs, ref_a)
    ib, db = find(runs, ref_b)
    if da == db:
        raise CompareError("that's the same run twice")
    a, b = load(da), load(db)
    project = str(a.meta.get("project") or b.meta.get("project") or "")
    if not project:
        project = project_of(a) if project_of else ""
        project = project or da.parent.parent.name
    cfg = config_diff(a.config, b.config)
    code = code_diff(_git_exe(rl.p), a, b)
    rows = metric_rows(a, b)
    out_dir = rl.runs_dir(project) / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe(a.id)}--{_safe(b.id)}"
    note = out_dir / f"{stem}.md"
    png = out_dir / f"{stem}.png"
    drew = curves_png(png, rows, a, b)
    notes = rl.notes

    def link(r: RunInfo) -> str:
        run_md = r.dir / "run.md"
        if run_md.is_file() and notes.inside_notes(run_md):
            return notes.shown(run_md)[:-3]
        return notes.shown(r.dir / "meta.json")

    body = note_text(a, b, cfg, code, rows, png.name if drew else "", link)
    old = note.read_text(encoding="utf-8") if note.exists() else ""
    if old:
        new = graphwrite.put_block(old, "run-compare", body)
        if not graphwrite.guarded(old, new).ok:
            raise CompareError(f"{notes.shown(note)} changed outside Kurooto's block; left as it is")
    else:
        new = (
            notes.frontmatter("note", note, title=f"{a.name} vs {b.name}", tags=["runs"])
            + graphwrite.block("run-compare", body)
            + "\n"
        )
    note.write_text(new, encoding="utf-8")
    line = headline(cfg, code, rows)
    _project_line(rl, project, note, a, b, line)
    return {
        "summary": f"{a.id} vs {b.id}: {line}.",
        "note": notes.shown(note),
        "png": str(png) if drew else "",
        "project": project,
        "a": ia,
        "b": ib,
    }


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s)[:70]


def _project_line(rl, project: str, note: Path, a: RunInfo, b: RunInfo, line: str) -> None:
    """The project note's run-compare block: this comparison first, then the last ones (ten in all)."""
    from kurooto.modules.research import ensure_project

    pnote = ensure_project(rl.notes, project, rl.assistant)
    text = pnote.read_text(encoding="utf-8")
    target = rl.notes.shown(note)[:-3]
    m = re.search(r"<!-- kurooto:run-compare\b[^>]*-->\n(.*?)\n<!-- /kurooto:run-compare -->", text, re.S)
    old = [ln for ln in (m.group(1).splitlines() if m else []) if ln.startswith("- ") and f"[[{target}|" not in ln]
    new_line = f"- {dt.date.today().isoformat()} [[{target}|{a.name} vs {b.name}]]: {line}"
    body = "Runs compared (newest first; `kurooto runlog diff A B` or /runs compare adds one):\n" + "\n".join(
        [new_line, *old][:KEPT]
    )
    new = graphwrite.put_block(text, "run-compare", body)
    if graphwrite.guarded(text, new).ok:
        pnote.write_text(new, encoding="utf-8")


# ----------------------------------------------------------------------------------------- from settings
def on(settings) -> str:
    """ "" when run compare may run (the Research add-on is on, with its Run compare part), else what to do."""
    if "research_addon" not in (settings.get("modules.enabled") or []):
        return (
            "Run compare is part of the Research add-on, which is off: turn it on in the dashboard (Features, "
            "Add-ons: Research add-on)."
        )
    if settings.get("research_addon.run_compare") is False:
        return "Run compare is off: switch it on on the Research add-on's card."
    return ""


def repo_dirs(settings) -> list[Path]:
    """The runs folders kept in the repositories Research follows (research.repos, research.repo_runs)."""
    folder = str(settings.get("research.repo_runs") or "").strip()
    if not folder:
        return []
    return [Path(r).expanduser() / folder for r in settings.get("research.repos") or []]


def project_for(settings):
    """project_of(run) for runs kept in a repository: its mapping in research.projects, else the folder's name."""
    mapping = {str(Path(k).expanduser()): v for k, v in (settings.get("research.projects") or {}).items() if v}

    def f(r: RunInfo) -> str:
        repo = r.dir.parent.parent
        return str(mapping.get(str(repo)) or repo.name)

    return f
