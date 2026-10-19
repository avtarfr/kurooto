"""Antigravity (`agy`), Google's agent CLI: free with a Google account. It runs in your notes folder and can read
and write notes there.

Two ways to read its answer, picked at setup by a quick test: through pipes ("pipe"), or through a pseudo-terminal
("pty") for builds that print nothing when their output isn't a terminal.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from kurooto.core import proc
from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict

LEVELS = {
    "low": ("gemini-3.8-flash-low", "low"),
    "medium": ("gemini-3.8-flash-medium", "medium"),
    "high": ("gemini-3.8-flash-high", "high"),
}
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Z0-9]|\r")


def install_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform == "win32":
        return [Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "agy" / "bin"]
    return [home / ".local" / "bin"]


class Agy(Brain):
    id = "agy"
    label = "Antigravity (agy)"
    kind = "cli"
    grace_s = 180  # agy gets this long past its own --print-timeout before it is killed

    def __init__(self, io_mode: str = "pipe", models: dict | None = None, exe: str | list[str] | None = None):
        self.io_mode = io_mode
        self.levels = {**LEVELS, **(models or {})}
        self.exe = exe or proc.which("agy", install_dirs())

    def available(self):
        return (True, "") if self.exe else (False, "agy isn't installed")

    def _args(self, prompt: str, effort: str, minutes: int) -> list[str]:
        model, eff = self.levels.get(effort, self.levels["medium"])
        base = list(self.exe) if isinstance(self.exe, list) else [self.exe]  # a list: tests run a fake agy
        return [*base, "--model", model, "--effort", eff, "--print-timeout", f"{minutes}m", "-p", prompt]

    def run(self, task: Task) -> Result:
        if not self.exe:
            return Result(Verdict.ERROR, detail="agy isn't installed")
        minutes = max(1, task.timeout_s // 60)
        prompt = (task.context + "\n\n" + task.prompt).strip() if task.context else task.prompt
        args = self._args(prompt, task.effort, minutes)
        t0 = time.monotonic()
        if self.io_mode == "pty":
            code, out, err = run_pty(args, task.cwd, task.timeout_s + self.grace_s)
        else:
            r = proc.run(args, cwd=task.cwd, timeout=task.timeout_s + self.grace_s)
            code, out, err = r.code, r.out, r.err
        return verdict(code, out, err, time.monotonic() - t0, minutes)

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 120) -> Result:
        return self.run(Task(prompt=prompt, context=system, effort=effort, timeout_s=timeout))


def verdict(code: int | None, out: str, err: str, secs: float, minutes: int) -> Result:
    """agy's own way of failing: it exits 0 and prints "no output produced" when a step was denied."""
    out, err = (out or "").strip(), (err or "").strip()
    both = f"{out}\n{err}"
    if code is None:
        return Result(Verdict.TIMEOUT, out, secs, f"timed out after {minutes} min")
    if "no output produced" in both:
        return Result(Verdict.DENIED, "", secs, "agy stopped: it tried something unattended runs aren't allowed to do")
    if RATE_LIMIT.search(both) and (code != 0 or not out):
        return Result(Verdict.RATE_LIMITED, "", secs, both[-500:])
    if AUTH_FAIL.search(both) and (code != 0 or not out):
        return Result(Verdict.AUTH, "", secs, both[-500:])
    if code != 0:
        return Result(Verdict.ERROR, out, secs, (err or out)[-800:] or f"exit {code}")
    return Result(Verdict.OK if out else Verdict.EMPTY, out, secs, "" if out else (err[-500:] or "no output"))


def run_pty(args: list[str], cwd: Path | None, timeout: float) -> tuple[int | None, str, str]:
    """Run under a pseudo-terminal (ConPTY on Windows) and return (exit code, cleaned output, "")."""
    deadline = time.monotonic() + timeout
    chunks: list[str] = []
    if sys.platform == "win32":
        from winpty import PtyProcess  # pywinpty

        p = PtyProcess.spawn(args, cwd=str(cwd) if cwd else None, dimensions=(50, 400))
    else:
        from ptyprocess import PtyProcessUnicode as PtyProcess

        p = PtyProcess.spawn(args, cwd=str(cwd) if cwd else None, dimensions=(50, 400))
    code: int | None = None
    try:
        while time.monotonic() < deadline:
            try:
                data = p.read(65536)
            except EOFError:
                break
            if data:
                chunks.append(data)
            elif not p.isalive():
                break
        else:
            p.terminate(force=True)
            return None, clean("".join(chunks)), ""
        while p.isalive() and time.monotonic() < deadline:
            time.sleep(0.05)
        code = p.exitstatus if getattr(p, "exitstatus", None) is not None else 0
    finally:
        if p.isalive():
            p.terminate(force=True)
    return code, clean("".join(chunks)), ""


def clean(text: str) -> str:
    return ANSI.sub("", text).replace("\r\n", "\n").strip()
