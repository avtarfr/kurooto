"""Where a lab run happens: a copy of the project, read-only system, no network, limits on time, CPU and memory.

Linux: bubblewrap (`bwrap`), as core/scratch.py uses for checks, plus the GPU's device files when the run may use the
GPU. macOS: a `sandbox-exec` profile (core/scratch.py's). Windows: the lab is unavailable, and says so. Without a
sandbox the lab does not run at all (it never runs a project's code outside one).
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import proc, scratch

if TYPE_CHECKING:
    from kurooto.app import App

OUT_KEEP = 6000  # characters of a run's output kept


def unavailable(app: App | None = None) -> str:
    """Why the lab can't run here, or "" when it can."""
    if os.name == "nt":
        return "the lab isn't available on Windows yet (it needs a sandbox: bubblewrap on Linux, macOS's own)"
    if sys.platform.startswith("linux"):
        return "" if shutil.which("bwrap") else "this computer has no bubblewrap (install the bubblewrap package)"
    if sys.platform == "darwin":
        return "" if shutil.which("sandbox-exec") else "this Mac has no sandbox-exec"
    return "this system has no sandbox the lab knows"


def prefix(work: Path, hide: list[Path], gpu: bool = False) -> list[str] | None:
    pre = scratch.sandbox(work, hide)
    if pre is None or not gpu or not sys.platform.startswith("linux"):
        return pre
    devs: list[str] = []
    for pat in ("/dev/nvidia*", "/dev/dri/*", "/dev/kfd"):
        for p in glob.glob(pat):
            devs += ["--dev-bind", p, p]
    i = pre.index("--bind")
    return pre[:i] + devs + pre[i:]


def limits(cmd: str, cpu_s: int, mem_mb: int) -> str:
    """The command with ulimits in front (CPU seconds and address space); the wall limit is the caller's."""
    return f"ulimit -t {int(cpu_s)}; ulimit -v {int(mem_mb) * 1024} 2>/dev/null; {cmd}"


def run(app: App, work: Path, cmd: str, wall_s: float, *, gpu: bool = False, mem_mb: int = 8192) -> dict:
    """Run `cmd` in `work` inside the sandbox: {"ran", "ok", "code", "out", "seconds", "suspended", "why"}."""
    why = unavailable(app)
    if why:
        return {"ran": False, "ok": False, "why": why, "out": "", "seconds": 0.0, "suspended": False, "code": None}
    home_dir = Path.home()
    hide = [
        app.paths.config,
        app.paths.state,
        *(home_dir / x for x in (".ssh", ".gnupg", ".aws", ".gemini", ".claude", ".config/gcloud", ".docker", ".kube")),
    ]
    pre = prefix(work, hide, gpu)
    if pre is None:
        return {
            "ran": False,
            "ok": False,
            "why": "no sandbox",
            "out": "",
            "seconds": 0.0,
            "suspended": False,
            "code": None,
        }
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "HOME", "USER", "TERM") if k in os.environ}
    env["TMPDIR"] = "/tmp"  # noqa: S108 (inside the sandbox: a fresh one of its own)
    w0, m0 = time.time(), time.monotonic()
    r = proc.run([*pre, "sh", "-c", limits(cmd, wall_s * 2, mem_mb)], cwd=work, env=env, timeout=wall_s)
    secs = round(time.monotonic() - m0, 2)
    asleep = (time.time() - w0) - (time.monotonic() - m0) > 60  # the computer slept in the middle (monotonic stops)
    out = ((r.out or "") + ("\n" + r.err if r.err else "")).strip()
    return {
        "ran": True,
        "ok": r.code == 0,
        "code": r.code,
        "out": out[-OUT_KEEP:],
        "seconds": secs,
        "suspended": asleep,
        "why": f"stopped after {int(wall_s)} s" if r.code is None else "",
    }
