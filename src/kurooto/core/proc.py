"""Running other programs safely on every OS.

- Prompts and other long text go through stdin, never the command line (Windows caps it at 32 KB and cmd.exe
  mangles characters like " & ^ %).
- An npm `.cmd` shim on Windows is run through node directly instead of cmd.exe.
- Output is decoded as UTF-8; no console window pops up on Windows.
- On a timeout the whole process tree is killed, not just the first process.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psutil

WINDOWS = sys.platform == "win32"


@dataclass
class Result:
    code: int | None  # None: killed after the timeout
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


USER_BIN = (".local/bin", ".cargo/bin")
SYSTEM_BIN = ("/usr/local/bin", "/opt/homebrew/bin", "/opt/homebrew/sbin")


def ensure_user_path(home: Path | None = None) -> list[str]:
    """Put the folders programs are usually installed to on PATH when they aren't: a service started at boot has a
    short PATH (no ~/.local/bin, no Homebrew), so tools you installed yourself (restic, rclone, git, an AI program)
    were "not found" until the desktop session handed its own PATH over. Only folders that exist are added, at the
    end, so nothing already on PATH is shadowed. Returns what it added."""
    if WINDOWS:
        return []
    home = Path(home) if home else Path.home()
    have = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    added = []
    for d in [str(home / x) for x in USER_BIN] + list(SYSTEM_BIN):
        if d not in have and Path(d).is_dir():
            have.append(d)
            added.append(d)
    if added:
        os.environ["PATH"] = os.pathsep.join(have)
    return added


def which(name: str, extra_dirs: list[Path] | None = None) -> str | None:
    """Find a program on PATH (with Windows' PATHEXT) or in extra folders such as an installer's default."""
    found = shutil.which(name)
    if found:
        return found
    for d in extra_dirs or []:
        for ext in os.environ.get("PATHEXT", ".EXE;.CMD;.BAT").split(";") if WINDOWS else [""]:
            p = Path(d) / f"{name}{ext.lower()}"
            if p.is_file():
                return str(p)
    return None


def resolve_cmd_shim(exe: str) -> list[str]:
    """npm puts `foo.cmd` wrappers on PATH on Windows. Running them goes through cmd.exe, which re-parses the
    arguments; run the JavaScript entry point with node instead when we can find it."""
    if not (WINDOWS and exe.lower().endswith(".cmd")):
        return [exe]
    try:
        text = Path(exe).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [exe]
    m = re.search(r'"%(?:~dp0|dp0%)\\?([^"%]+\.(?:c?js|mjs))"', text)
    node = shutil.which("node")
    if m and node:
        script = Path(exe).parent / m.group(1)
        if script.is_file():
            return [node, str(script)]
    return [exe]


def kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = parent.children(recursive=True) + [parent]
    for p in procs:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=5)


def run(
    args: list[str],
    *,
    input: str | None = None,
    timeout: float = 60,
    cwd: Path | None = None,
    env: dict | None = None,
    on_start: Callable[[int], None] | None = None,
) -> Result:
    """Run a program and wait for it. `input` is written to its stdin. `on_start(pid)` is told the program's pid as
    soon as it runs (the AI queue keeps it, so a cancel can stop the program and everything it started)."""
    args = resolve_cmd_shim(args[0]) + list(args[1:])
    flags = subprocess.CREATE_NO_WINDOW if WINDOWS else 0
    p = subprocess.Popen(
        args,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        creationflags=flags,
        start_new_session=not WINDOWS,
    )
    if not WINDOWS:  # what it leaves behind in its session ends with Kurooto (core/children.py)
        from kurooto.core import children

        children.session(p.pid)
    if on_start is not None:
        try:
            on_start(p.pid)
        except Exception:
            pass
    try:
        out, err = p.communicate(input=input.encode("utf-8") if input is not None else None, timeout=timeout)
        code = p.returncode
    except subprocess.TimeoutExpired:
        kill_tree(p.pid)
        try:  # a process that slipped out of the tree can hold the pipes open: never wait for it for ever
            out, err = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
            for f in (p.stdout, p.stderr):
                try:
                    f.close()
                except OSError:
                    pass
        code = None
    return Result(code, (out or b"").decode("utf-8", "replace"), (err or b"").decode("utf-8", "replace"))


BACKGROUND_NICE = 10  # (0.9.2, a fix) automatic work's programs run this much nicer: a spoken turn never waits


def run_nicer(pid: int, by: int = BACKGROUND_NICE) -> bool:
    """(0.9.2) Run a program Kurooto started for automatic work (not your own request) at a lower CPU priority: what it
    starts afterwards inherits it. Never raises; False where it can't (Windows, gone, not ours)."""
    try:
        p = psutil.Process(int(pid))
        if WINDOWS:
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(min(19, max(p.nice(), 0) + int(by)))
        return True
    except (psutil.Error, ValueError, OSError, AttributeError):
        return False


def pid_alive(pid: int, must_contain: str = "") -> bool:
    """Is this process still running (and, if given, is `must_contain` in its command line)?"""
    try:
        p = psutil.Process(int(pid))
        return p.is_running() and (not must_contain or must_contain in " ".join(p.cmdline()))
    except (psutil.Error, ValueError):
        return False
