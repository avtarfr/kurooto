"""Antigravity (`agy`), Google's agent CLI: free with a Google account. It runs in your notes folder and can read
and write notes there.

Two ways to read its answer, picked at setup by a quick test: through pipes ("pipe"), or through a pseudo-terminal
("pty") for builds that print nothing when their output isn't a terminal.

Kurooto's tools reach agy as an MCP server, added once when agy is set up (`agy mcp add kurooto ...`, plus
"mcp(kurooto/*)" in agy's own allow-list so unattended runs may use them; its settings file is backed up first).
To undo: `agy mcp remove kurooto`, and take that line out of ~/.gemini/antigravity-cli/settings.json.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import proc
from kurooto.core.state import jload, jsave
from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, TEXT_ONLY, Brain, Result, Task, Verdict

if TYPE_CHECKING:
    from kurooto.app import App

LEVELS = {
    "low": ("gemini-3.8-flash-low", "low"),
    "medium": ("gemini-3.8-flash-medium", "medium"),
    "high": ("gemini-3.8-flash-high", "high"),
}
ARG_LIMIT = 20_000 if sys.platform == "win32" else 100_000  # longer prompts go through a file (handover)
ALLOW = "mcp(kurooto/*)"  # agy's allow-list entry for every Kurooto tool
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
        if task.text_only:  # unattended runs may not use tools; text-only work says so plainly
            prompt = f"{TEXT_ONLY}\n\n{prompt}"
        long = handover(prompt, task.cwd, task.text_only)
        args = self._args(long[1] if long else prompt, task.effort, minutes)
        env = {**os.environ, **task.mcp_env} if task.mcp_env else None  # agy hands it on to `kurooto mcp`
        t0 = time.monotonic()
        try:
            if self.io_mode == "pty":
                code, out, err = run_pty(args, task.cwd, task.timeout_s + self.grace_s, env)
            else:
                r = proc.run(args, cwd=task.cwd, timeout=task.timeout_s + self.grace_s, env=env)
                code, out, err = r.code, r.out, r.err
        finally:
            if long:
                long[0].unlink(missing_ok=True)
        return verdict(code, out, err, time.monotonic() - t0, minutes)

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 120) -> Result:
        return self.run(Task(prompt=prompt, context=system, effort=effort, timeout_s=timeout, text_only=True))


def handover(prompt: str, cwd: Path | None, text_only: bool = False) -> tuple[Path, str] | None:
    """agy takes its request on the command line, which has a size limit (about 32,000 characters in all on
    Windows, 128 KB per argument on Linux). A longer request goes in a file in a hidden folder of the notes, which
    git (Notes sync) ignores, and agy is told to read it. Returns (the file, the short prompt), or None."""
    if len(prompt) <= ARG_LIMIT or cwd is None:
        return None
    d = Path(cwd) / ".kurooto" / "requests"
    d.mkdir(parents=True, exist_ok=True)
    if not (d / ".gitignore").exists():
        (d / ".gitignore").write_text("*\n", encoding="utf-8")
    f = d / f"{uuid.uuid4().hex[:12]}.md"
    f.write_text(prompt, encoding="utf-8")
    rel = f.relative_to(cwd).as_posix()
    if text_only:
        return f, (
            f"Your full request is in the file {rel} (in this folder). Read that one file, then answer with text "
            "only: don't read anything else, and don't write or run anything."
        )
    return f, f"Your full request is in the file {rel} (in this folder). Read all of it, then do what it says."


def worked_file(state: Path) -> Path:
    return Path(state) / "agy-worked.json"


def has_worked(state: Path) -> bool:
    """Has agy answered on this computer before (a request, or the setup page's test)? Then it may stand in for
    the Gemini key."""
    return worked_file(state).exists()


def mark_worked(state: Path) -> None:
    f = worked_file(state)
    if not f.exists():
        f.write_text(json.dumps({"at": time.time()}), encoding="utf-8")


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


def run_pty(args: list[str], cwd: Path | None, timeout: float, env: dict | None = None) -> tuple[int | None, str, str]:
    """Run under a pseudo-terminal (ConPTY on Windows) and return (exit code, cleaned output, "")."""
    deadline = time.monotonic() + timeout
    chunks: list[str] = []
    if sys.platform == "win32":
        from winpty import PtyProcess  # pywinpty

        p = PtyProcess.spawn(args, cwd=str(cwd) if cwd else None, env=env, dimensions=(50, 400))
    else:
        from ptyprocess import PtyProcessUnicode as PtyProcess

        p = PtyProcess.spawn(args, cwd=str(cwd) if cwd else None, env=env, dimensions=(50, 400))
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


# ------------------------------------------------------------------------------------------ Kurooto's tools
def settings_file() -> Path:
    return Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def allow_tools(backups: Path) -> tuple[bool, str]:
    """Add "mcp(kurooto/*)" to agy's permissions.allow, backing its settings file up first. Changes nothing else."""
    f = settings_file()
    data = jload(f, None) if f.exists() else {}
    perms = data.setdefault("permissions", {}) if isinstance(data, dict) else None
    allow = perms.setdefault("allow", []) if isinstance(perms, dict) else None
    if not isinstance(allow, list):
        return False, f"agy's settings ({f}) aren't in the shape Kurooto expects; add {ALLOW} to permissions.allow"
    if ALLOW in allow:
        return True, "agy may already use Kurooto's tools"
    if f.exists():
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, backups / f"agy-settings-{time.strftime('%Y%m%d-%H%M%S')}.json")
    allow.append(ALLOW)
    jsave(f, data)
    return True, "agy may use Kurooto's tools"


def connect_tools(app: App, exe: str | list[str] | None = None) -> tuple[bool, str]:
    """Give agy Kurooto's tools for every run: register `kurooto mcp` as its MCP server "kurooto" and allow its
    tools. Done when agy is set up (and once after an update to a version that has tools)."""
    from kurooto import __version__
    from kurooto.core.mcp import command

    exe = exe or proc.which("agy", install_dirs())
    if not exe:
        return False, "agy isn't installed"
    cmd = command(persistent=True)
    # saved for good, so only what a portable copy needs; the system's own folders (XDG_*, LOCALAPPDATA) come from
    # agy's environment at each run, which stays right if they change
    home = os.environ.get("KUROOTO_HOME")
    flags = ["--env", f"KUROOTO_HOME={home}"] if home else []
    base = list(exe) if isinstance(exe, list) else [exe]
    r = proc.run([*base, "mcp", "add", *flags, "kurooto", "--", *cmd], timeout=60)
    if r.code != 0:
        ok, msg = False, f"agy didn't take Kurooto's tools: {(r.err or r.out).strip()[-200:] or f'exit {r.code}'}"
    else:
        ok, msg = allow_tools(app.paths.state / "backups")
    jsave(app.paths.state / "agy-tools.json", {"command": cmd, "ok": ok, "message": msg, "version": __version__})
    app.events.emit("agy_tools", ok=ok)
    return ok, msg


def tools_once(app: App, brain: Agy) -> None:
    """Before agy's first run with this install: connect the tools if that was never tried (a failure isn't
    retried here; the setup page's test tries again)."""
    from kurooto.core.mcp import command

    if not isinstance(brain.exe, str):  # a test's fake agy
        return
    if os.environ.get("KUROOTO_HOME") and os.environ.get("KUROOTO_AGY_TOOLS") != "1":
        return  # a portable or test copy leaves agy's own settings alone unless set up through the setup page
    if (jload(app.paths.state / "agy-tools.json", {}) or {}).get("command") == command(persistent=True):
        return
    try:
        connect_tools(app, brain.exe)
    except Exception as e:
        app.events.emit("agy_tools", ok=False, error=f"{type(e).__name__}: {e}"[:200])
