"""`kurooto runlog`: a small, file-based log of experiment runs, written into your notes. No server, no account.

    kurooto runlog start <project> [--name N] [--config JSON] [--repo DIR]   prints the run's id
    kurooto runlog metric [--run ID] [--step N] loss=0.31 acc=0.88           one row of numbers
    kurooto runlog note [--run ID] TEXT                                      a line in the run's notes
    kurooto runlog end [--run ID] [--status ok|failed|interrupted]          finish it
    kurooto runlog ls [project]                                              the runs so far
    kurooto runlog diff A B                                                  two runs side by side (Research add-on)

Each run is a folder research/<project>/runs/<YYYYmmdd-HHMMSS>-<name>/ in your notes (where your notes layout keeps a
project's runs):
    run.md         what it was (command folder, git commit, config) and, at the end, how it went
    config.json    the config you gave
    meta.json      git commit, branch, uncommitted changes, start, end, duration, status
    diff.patch     the uncommitted changes at the start, so the exact code can be recovered
    metrics.jsonl  one JSON object per `metric` call
and one line in research/<project>/runs/index.csv, and one in the project's Log when it ends.
Without --run, the commands use $KUROOTO_RUN, else the run you started last on this computer.

From Python, a run is a `with` block (`Run` below): the same folder in your notes with a project, or, without one, a
runs/ folder in your repository that Research reads into the project's Log each night.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import platform
import re
import sys
import time
import traceback
from pathlib import Path

from kurooto.core import layout, proc
from kurooto.core.state import jload, jsave

DIFF_MAX = 2 * 1024 * 1024
STATUSES = ("ok", "failed", "interrupted")


class RunError(Exception):
    pass


def _git_exe(p) -> str | None:
    exe = proc.which("git")
    if exe:
        return exe
    try:
        from kurooto.core.prereqs import Prereqs

        return Prereqs(p.app, p.cache).items["git"].find()
    except Exception:
        return None


def git_state(repo: Path, git: str | None) -> dict:
    """The code's exact state: commit, branch, whether there are uncommitted changes (and the diff)."""
    if not git:
        return {"commit": "", "branch": "", "dirty": False, "diff": "", "repo": ""}
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}

    def g(*a):
        r = proc.run([git, "-C", str(repo), *a], timeout=30, env=env)
        return r.out if r.ok else ""

    top = g("rev-parse", "--show-toplevel").strip()
    if not top:
        return {"commit": "", "branch": "", "dirty": False, "diff": "", "repo": ""}
    dirty = bool(g("status", "--porcelain").strip())
    return {
        "commit": g("rev-parse", "HEAD").strip(),
        "branch": g("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "dirty": dirty,
        "diff": g("diff", "HEAD") if dirty else "",
        "repo": Path(top).name,
    }


class Runlog:
    """Runs for one installation: `p` its paths, `workspace` the notes folder (or its layout.Layout)."""

    def __init__(self, p, workspace, assistant: str = "Kurooto"):
        self.p = p
        self.notes = layout.of(workspace)
        self.workspace = self.notes.root
        self.assistant = assistant
        self.state_file = p.state / "runlog.json"

    def _state(self) -> dict:
        return jload(self.state_file, {"runs": {}, "current": None}) or {"runs": {}, "current": None}

    def runs_dir(self, project: str) -> Path:
        from kurooto.modules.research import slug

        return self.notes.path("runs", project=slug(project))

    # --------------------------------------------------------------------------------------------- start
    def start(self, project: str, name: str = "", config: dict | None = None, repo: Path | None = None) -> str:
        from kurooto.modules.research import ensure_project

        if not project.strip():
            raise RunError("which project? kurooto runlog start <project>")
        repo = Path(repo or Path.cwd())
        gs = git_state(repo, _git_exe(self.p))
        name = name or gs["repo"] or "run"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")[:60] or "run"
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        ensure_project(self.notes, project, self.assistant)
        base = self.runs_dir(project)
        d = base / f"{stamp}-{safe}"
        n = 2
        while d.exists():
            d = base / f"{stamp}-{safe}-{n}"
            n += 1
        d.mkdir(parents=True)
        cfg = dict(config or {})
        (d / "config.json").write_text(json.dumps(cfg, indent=2, default=str), encoding="utf-8")
        if gs["diff"]:
            (d / "diff.patch").write_text(gs["diff"][:DIFF_MAX], encoding="utf-8")
        meta = {
            "name": name,
            "project": project,
            "start": dt.datetime.now().isoformat(timespec="seconds"),
            "t0": time.time(),
            "cwd": str(repo),
            "commit": gs["commit"],
            "branch": gs["branch"],
            "dirty": gs["dirty"],
            "status": "running",
        }
        jsave(d / "meta.json", meta, mode=0o644)
        run = d / "run.md"  # its links are written from here (notes.links)
        lines = [
            f"# Run: {name}",
            "",
            f"Project: {self.notes.note_link(self.notes.link('project', project=_slug(project)), project, run)}. "
            f"Started {meta['start'].replace('T', ' ')}"
            f" in {repo.name or repo}.",
        ]
        if gs["commit"]:
            lines.append(
                f"Code: {gs['repo']} at {gs['commit'][:10]} ({gs['branch']})"
                + (", with uncommitted changes (diff.patch)" if gs["dirty"] else "")
                + "."
            )
        if cfg:
            lines += ["", "Config:", "", "```json", json.dumps(cfg, indent=2, default=str), "```"]
        (d / "run.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rid = d.name
        st = self._state()
        st["runs"][rid] = {"dir": str(d), "project": project, "started": time.time(), "status": "running"}
        st["runs"] = dict(list(st["runs"].items())[-200:])
        st["current"] = rid
        jsave(self.state_file, st)
        return rid

    # ------------------------------------------------------------------------------------------- finding
    def find(self, rid: str | None = None) -> tuple[str, Path]:
        st = self._state()
        rid = rid or os.environ.get("KUROOTO_RUN") or st.get("current")
        if not rid:
            raise RunError("no run going: start one with `kurooto runlog start <project>`")
        runs = st.get("runs") or {}
        if rid not in runs:
            hits = [k for k in runs if k.startswith(rid) or k.endswith(rid)]
            if len(hits) != 1:
                raise RunError(f"no run {rid!r}" if not hits else f"{rid!r} matches several runs; give more of it")
            rid = hits[0]
        d = Path(runs[rid]["dir"])
        if not (d / "meta.json").exists():
            raise RunError(f"the run's folder is gone ({d})")
        return rid, d

    # -------------------------------------------------------------------------------------- during a run
    def metric(self, values: dict, step: int | None = None, rid: str | None = None) -> str:
        rid, d = self.find(rid)
        meta = jload(d / "meta.json", {}) or {}
        row = {"time": round(time.time() - float(meta.get("t0") or time.time()), 3)}
        if step is not None:
            row["step"] = step
        row.update(values)
        with open(d / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return rid

    def note(self, text: str, rid: str | None = None) -> str:
        rid, d = self.find(rid)
        with open(d / "notes.md", "a", encoding="utf-8") as f:
            f.write(f"- {dt.datetime.now():%Y-%m-%d %H:%M} {text.strip()}\n")
        return rid

    # ----------------------------------------------------------------------------------------------- end
    def end(self, status: str = "ok", rid: str | None = None, error: str = "") -> dict:
        from kurooto.modules.research import log_lines

        if status not in STATUSES:
            raise RunError(f"status is one of {', '.join(STATUSES)}")
        rid, d = self.find(rid)
        meta = jload(d / "meta.json", {}) or {}
        if meta.get("status") != "running":
            raise RunError(f"that run already ended ({meta.get('status')})")
        last: dict = {}
        try:
            for ln in (d / "metrics.jsonl").read_text(encoding="utf-8").splitlines():
                try:
                    last.update({k: v for k, v in json.loads(ln).items() if k != "time"})
                except ValueError:
                    continue
        except OSError:
            pass
        secs = round(time.time() - float(meta.get("t0") or time.time()), 1)
        meta.update(status=status, end=dt.datetime.now().isoformat(timespec="seconds"), duration_s=secs, last=last)
        if error:
            meta["error"] = error[-4000:]
        jsave(d / "meta.json", meta, mode=0o644)
        index = d.parent / "index.csv"
        new = not index.exists()
        with open(index, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["run", "start", "duration_s", "status", "commit", "dirty", "last_metrics"])
            w.writerow(
                [
                    rid,
                    meta.get("start"),
                    secs,
                    status,
                    (meta.get("commit") or "")[:10],
                    meta.get("dirty"),
                    json.dumps(last),
                ]
            )
        shown = ", ".join(f"{k}={_short(v)}" for k, v in list(last.items())[:4])
        with open(d / "run.md", "a", encoding="utf-8") as f:
            f.write(f"\n## Result\n\n{status} after {_took(secs)}" + (f"; last: {shown}" if shown else "") + ".\n")
        project = meta.get("project") or ""
        line = (
            f"- **{dt.date.today().isoformat()}** | run:{meta.get('name', rid)} — {status} after {_took(secs)}"
            + (f" ({shown})" if shown else "")
            + " "
            + self.notes.note_link(
                f"{self.notes.link('runs', project=_slug(project))}/{rid}/run",
                "details",
                self.notes.path("project", project=_slug(project)),
            )
        )
        log_lines(self.notes, project, [line], self.assistant)
        st = self._state()
        if rid in st["runs"]:
            st["runs"][rid]["status"] = status
        if st.get("current") == rid:
            st["current"] = None
        jsave(self.state_file, st)
        return {"run": rid, "status": status, "seconds": secs, "last": last, "dir": str(d)}

    def ls(self, project: str | None = None) -> list[dict]:
        out = []
        for rid, r in (self._state().get("runs") or {}).items():
            if project and r.get("project") != project:
                continue
            meta = jload(Path(r["dir"]) / "meta.json", {}) or {}
            out.append(
                {
                    "run": rid,
                    "project": r.get("project"),
                    "status": meta.get("status", r.get("status")),
                    "seconds": meta.get("duration_s"),
                    "last": meta.get("last") or {},
                }
            )
        return out


def _slug(project: str) -> str:
    from kurooto.modules.research import slug

    return slug(project)


class Run:
    """An experiment run as a `with` block, for Python scripts:

        from kurooto.runlog import Run

        with Run("lr-sweep", config={"lr": 1e-3}, project="my-model") as run:
            for step in range(n_steps):
                ...
                run.log(step=step, loss=loss)
            run.note("diverged after step 800")

    With a project (or $KUROOTO_PROJECT), the run goes into your notes exactly like `kurooto runlog` (and a line in
    the project's Log). Without one, it goes to a runs/ folder where the script starts ($RUNLOG_DIR, or `root`):
    <YYYYmmdd-HHMMSS>-<name>/ with config.json, meta.json (git commit, uncommitted changes, host, argv, start, end,
    status, error), diff.patch, metrics.jsonl and notes.md, and a row in runs/index.csv, which Research reads into the
    project's Log each night. It ends as ok, failed (an exception; its traceback is kept) or interrupted (Ctrl+C), and
    never hides the exception."""

    def __init__(self, name: str, config: dict | None = None, project: str | None = None, root=None):
        self.name = str(name or "run")
        self.config = dict(config or {})
        self.project = project if project is not None else os.environ.get("KUROOTO_PROJECT") or None
        self.root = None if self.project else Path(root or os.environ.get("RUNLOG_DIR") or "runs")
        self.dir: Path | None = None
        self.id = ""
        self._rl: Runlog | None = None
        self._metrics = None
        self._last: dict = {}
        self._t0 = time.time()

    def __enter__(self) -> Run:
        self._t0 = time.time()
        if self.project:
            self._rl = for_this_install()
            self.id = self._rl.start(self.project, self.name, self.config, Path.cwd())
            self.dir = self._rl.find(self.id)[1]
        else:
            self._start_here()
        self._metrics = open(self.dir / "metrics.jsonl", "a", encoding="utf-8")  # noqa: SIM115 (closed in __exit__)
        return self

    def _start_here(self) -> None:
        gs = git_state(Path.cwd(), proc.which("git"))
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", self.name).strip("-")[:60] or "run"
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        d = self.root / f"{stamp}-{safe}"
        n = 2
        while d.exists():
            d = self.root / f"{stamp}-{safe}-{n}"
            n += 1
        d.mkdir(parents=True)
        (d / "config.json").write_text(json.dumps(self.config, indent=2, default=str), encoding="utf-8")
        if gs["diff"]:
            (d / "diff.patch").write_text(gs["diff"][:DIFF_MAX], encoding="utf-8")
        self.meta = {
            "name": self.name,
            "start": dt.datetime.now().isoformat(timespec="seconds"),
            "commit": gs["commit"],
            "branch": gs["branch"],
            "dirty": gs["dirty"],
            "host": platform.node(),
            "python": sys.version.split()[0],
            "argv": list(sys.argv),
            "cwd": os.getcwd(),
            "status": "running",
        }
        jsave(d / "meta.json", self.meta, mode=0o644)
        self.dir, self.id = d, d.name

    def log(self, step: int | None = None, **values) -> None:
        """One row of numbers: run.log(step=10, loss=0.3)."""
        row = {"time": round(time.time() - self._t0, 3)}
        if step is not None:
            row["step"] = step
        row.update(values)
        self._metrics.write(json.dumps(row, default=float) + "\n")
        self._metrics.flush()
        self._last.update({k: v for k, v in row.items() if k != "time"})

    def note(self, text: str) -> None:
        """A line in the run's notes.md."""
        with open(self.dir / "notes.md", "a", encoding="utf-8") as f:
            f.write(f"- {dt.datetime.now():%Y-%m-%d %H:%M:%S} {str(text).strip()}\n")

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._metrics is not None:
            self._metrics.close()
        if exc_type is None:
            status, error = "ok", ""
        else:
            status = "interrupted" if issubclass(exc_type, KeyboardInterrupt) else "failed"
            error = "".join(traceback.format_exception(exc_type, exc, tb))[-4000:]
            self.note(f"{status}: {exc_type.__name__}: {exc}"[:500])
        if self._rl is not None:
            self._rl.end(status, self.id, error=error)
            return False
        secs = round(time.time() - self._t0, 1)
        self.meta.update(
            status=status, end=dt.datetime.now().isoformat(timespec="seconds"), duration_s=secs, last=self._last
        )
        if error:
            self.meta["error"] = error
        jsave(self.dir / "meta.json", self.meta, mode=0o644)
        index = self.dir.parent / "index.csv"
        new = not index.exists()
        with open(index, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["run", "start", "duration_s", "status", "commit", "dirty", "last_metrics"])
            w.writerow(
                [
                    self.id,
                    self.meta["start"],
                    secs,
                    status,
                    (self.meta.get("commit") or "")[:10],
                    self.meta.get("dirty"),
                    json.dumps(self._last, default=float),
                ]
            )
        return False  # never hide the exception


def parse_values(pairs: list[str]) -> dict:
    """key=value words -> {key: number or text}."""
    out = {}
    for p in pairs:
        k, eq, v = p.partition("=")
        if not eq or not k.strip():
            raise RunError(f"{p!r}: write metrics as name=value")
        v = v.strip()
        try:
            out[k.strip()] = int(v) if re.fullmatch(r"-?\d+", v) else float(v)
        except ValueError:
            out[k.strip()] = v
    return out


def _short(v) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)[:30]


def _took(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{secs % 3600 // 60:02d}m"


def for_this_install() -> Runlog:
    """The Runlog for this computer's Kurooto (its notes folder), without starting Kurooto."""
    from kurooto.app import default_workspace
    from kurooto.core.config import Settings
    from kurooto.core.paths import paths

    p = paths().ensure()
    s = Settings(p.config / "settings.json")
    ws = s.get("you.workspace")
    notes = layout.Layout(Path(ws) if ws else default_workspace(), s, s.get("you.assistant_name") or "Kurooto", p.data)
    return Runlog(p, notes, notes.assistant)


def main(args) -> int:
    """`kurooto runlog ...` (args from argparse)."""
    rl = for_this_install()
    try:
        if args.action == "start":
            cfg = json.loads(args.config) if args.config else {}
            if not isinstance(cfg, dict):
                raise RunError("--config takes a JSON object, e.g. '{\"lr\": 0.001}'")
            rid = rl.start(args.project, args.name or "", cfg, Path(args.repo) if args.repo else None)
            print(rid)
            return 0
        if args.action == "metric":
            rl.metric(parse_values(args.values), args.step, args.run)
            return 0
        if args.action == "note":
            rl.note(" ".join(args.text), args.run)
            return 0
        if args.action == "end":
            r = rl.end(args.status, args.run)
            print(f"{r['run']}: {r['status']} after {_took(r['seconds'])}. Notes: {r['dir']}")
            return 0
        if args.action == "diff":
            from kurooto import runcompare

            s = rl.notes.settings
            off = runcompare.on(s)
            if off:
                print(off)
                return 2
            r = runcompare.compare(rl, args.a, args.b, runcompare.repo_dirs(s), runcompare.project_for(s))
            print(r["summary"])
            print(f"In your notes: {r['note']}" + (f" (curves: {Path(r['png']).name})" if r["png"] else ""))
            return 0
        if args.action == "ls":
            rows = rl.ls(args.project)
            for r in rows:
                took = _took(r["seconds"]) if r["seconds"] is not None else "running"
                last = ", ".join(f"{k}={_short(v)}" for k, v in list(r["last"].items())[:3])
                print(f"{r['run']:<40} {r['project'] or '':<16} {r['status']:<11} {took:>9}  {last}")
            if not rows:
                print("No runs yet.")
            return 0
    except (RunError, ValueError) as e:
        print(f"runlog: {e}")
        return 2
    except Exception as e:
        from kurooto.runcompare import CompareError

        if not isinstance(e, CompareError):
            raise
        print(f"runlog: {e}")
        return 2
    return 2
