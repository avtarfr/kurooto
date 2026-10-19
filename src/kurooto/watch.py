"""`kurooto watch -- <command...>`: run a long job, and get a message when it ends (exit code, how long it took, its
last lines). Its output still shows in your terminal as it runs.

    kurooto watch -- python train.py --epochs 50
    kurooto watch --lines 0 -- make all          no output lines in the message
    kurooto watch --log my-model -- python fit.py also log it as a run of the project my-model (`kurooto runlog`)

The message goes through Kurooto (Telegram, the phone app, the desktop); if Kurooto isn't running, it shows on this
computer only. Every watched run is also listed in watch.log in Kurooto's state folder.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from kurooto.core import proc

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")
WRAPPERS = ("python", "python3", "py", "uv", "bash", "sh", "node", "Rscript", "julia", "pwsh", "powershell")


def label(cmd: list[str]) -> str:
    """A short name for the job: the program, or for `python train.py` the script."""
    first = Path(cmd[0]).name
    stem = first.rsplit(".", 1)[0] if first.lower().endswith(".exe") else first
    if stem in WRAPPERS:
        rest = [a for a in cmd[1:] if not a.startswith("-")]
        if rest:
            return f"{stem} {Path(rest[0]).name}"
    return first


def took(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{secs % 3600 // 60:02d}m"


def last_lines(tail: bytes, n: int, max_chars: int = 1500) -> list[str]:
    """The last n readable lines of output: colours removed, progress-bar rewrites (\\r) reduced to their last state."""
    if n <= 0:
        return []
    text = ANSI.sub("", tail.decode("utf-8", "replace"))
    lines = [ln.rsplit("\r", 1)[-1].rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    lines = [ln for ln in lines if ln.strip()][-n:]
    while lines and sum(len(x) + 1 for x in lines) > max_chars:
        lines.pop(0)
    return [ln[:300] for ln in lines]


def run(cmd: list[str], lines: int = 10, project: str | None = None, out=None) -> tuple[int, str]:
    """Run it (output passed through), then send the message. Returns (exit code, the message)."""
    out = out or sys.stdout.buffer
    exe = shutil.which(cmd[0]) or cmd[0]
    argv = proc.resolve_cmd_shim(exe) + list(cmd[1:])
    rl = rid = None
    if project:
        from kurooto.runlog import RunError, for_this_install

        rl = for_this_install()
        try:
            rid = rl.start(project, name=label(cmd).split()[-1], config={"command": cmd})
        except RunError as e:
            print(f"watch: couldn't start the run log ({e}); watching anyway", file=sys.stderr)
            rl = None
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if rid:
        env["KUROOTO_RUN"] = rid  # the job can add metrics with `kurooto runlog metric ...`
    t0 = time.monotonic()
    tail: deque[bytes] = deque()
    size = 0
    interrupted = False
    try:
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    except OSError as e:
        print(f"watch: couldn't start {cmd[0]}: {e}", file=sys.stderr)
        return 127, ""
    fd = p.stdout.fileno()
    while True:
        try:
            chunk = os.read(fd, 65536)
        except KeyboardInterrupt:  # Ctrl+C reaches the job too; wait for it to stop
            interrupted = True
            continue
        except OSError:
            chunk = b""
        if not chunk:
            break
        try:
            out.write(chunk)
            out.flush()
        except (OSError, ValueError):
            pass
        tail.append(chunk)
        size += len(chunk)
        while size > 32768 and len(tail) > 1:
            size -= len(tail.popleft())
    while True:
        try:
            code = p.wait()
            break
        except KeyboardInterrupt:
            interrupted = True
    secs = time.monotonic() - t0
    name = label(cmd)
    if interrupted or code in (-2, 130, 0xC000013A):
        head, status = f"Stopped: {name} after {took(secs)} (interrupted)", "interrupted"
    elif code == 0:
        head, status = f"Done: {name} in {took(secs)}", "ok"
    else:
        head, status = f"Failed: {name} (exit {code}) after {took(secs)}", "failed"
    shown = last_lines(b"".join(tail), lines)
    text = head + (("\n\nLast lines:\n" + "\n".join(shown)) if shown else "")
    if rl and rid:
        try:
            rl.end(status, rid)
            text += f"\n\nLogged as run {rid}."
        except Exception as e:
            print(f"watch: couldn't finish the run log: {e}", file=sys.stderr)
    _record(code, secs, cmd)
    return code, text


def _record(code: int, secs: float, cmd: list[str]) -> None:
    from kurooto.core.paths import paths

    try:
        log = paths().ensure().state / "watch.log"
        line = "\t".join([time.strftime("%Y-%m-%dT%H:%M:%S"), str(code), took(secs), str(Path.cwd()), " ".join(cmd)])
        with open(log, "a", encoding="utf-8") as f:
            f.write(line[:2000] + "\n")
    except OSError:
        pass


def main(cmd: list[str], lines: int = 10, project: str | None = None) -> int:
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("usage: kurooto watch [--lines N] [--log PROJECT] -- <command> [args...]", file=sys.stderr)
        return 2
    code, text = run(cmd, lines, project)
    if not text:
        return code
    from kurooto.cli import ask_running

    r = ask_running("notify", {"text": text, "title": "Job finished", "kind": "result", "urgent": code != 0})
    if not (r and r.get("ok")):
        from kurooto.core import desktop

        desktop.notify("Job finished", text.split("\n", 1)[0], urgent=code != 0)
        print("watch: Kurooto isn't running, so this was only shown on this computer.", file=sys.stderr)
    return code if code >= 0 else 128 - code


def follow_log(path: Path, n: int = 60, follow: bool = True, out=None, stop=None) -> int:
    """`kurooto logs [-f]`: the end of Kurooto's log, then new lines as they come (log rotation handled)."""
    out = out or sys.stdout
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    for ln in lines[-n:]:
        out.write(ln + "\n")
    out.flush()
    if not follow:
        return 0
    pos = path.stat().st_size if path.exists() else 0
    try:
        while not (stop and stop()):
            time.sleep(0.5)
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size < pos:  # rotated: start the new file from the top
                pos = 0
            if size > pos:
                with open(path, "rb") as f:
                    f.seek(pos)
                    data = f.read(size - pos)
                pos = size
                out.write(data.decode("utf-8", "replace"))
                out.flush()
    except KeyboardInterrupt:
        pass
    return 0
