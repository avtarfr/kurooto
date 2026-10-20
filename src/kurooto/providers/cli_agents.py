"""Two more agent CLIs as AI brains: OpenAI's Codex (with a ChatGPT plan) and Anthropic's Claude Code (Advanced).
Both read the prompt from stdin, run in your notes folder, and are only allowed to read files there. Kurooto's tools
(reminders, calls, adding to notes, ...) reach them as the MCP server "kurooto" (`kurooto mcp`), given for each run
only: nothing is saved in their own settings.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from kurooto.core import proc
from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict


def _which(name: str, app_dir: Path | None) -> str | None:
    dirs = [Path.home() / ".local" / "bin"]
    if app_dir:
        dirs += [app_dir / "npm", app_dir / "npm" / "bin"]
    return proc.which(name, dirs)


def codex_mcp(task: Task) -> list[str]:
    """`codex exec -c` overrides that give this run Kurooto's tools (the value after `=` is TOML; JSON strings and
    arrays are valid TOML). Its tool calls are approved up front: nobody is there to approve them."""
    if not task.mcp:
        return []
    out = [
        f"mcp_servers.kurooto.command={json.dumps(task.mcp[0])}",
        f"mcp_servers.kurooto.args={json.dumps(task.mcp[1:])}",
        'mcp_servers.kurooto.default_tools_approval_mode="approve"',
    ]
    if task.mcp_env:  # Codex gives MCP servers a short environment: name what to pass on
        out.append(f"mcp_servers.kurooto.env_vars={json.dumps(sorted(task.mcp_env))}")
    return [x for o in out for x in ("-c", o)]


def _fail(code: int | None, text: str, secs: float, minutes: int) -> Result | None:
    if code is None:
        return Result(Verdict.TIMEOUT, "", secs, f"timed out after {minutes} min")
    if RATE_LIMIT.search(text):
        return Result(Verdict.RATE_LIMITED, "", secs, text[-500:])
    if AUTH_FAIL.search(text) or "/login" in text or "codex login" in text:
        return Result(Verdict.AUTH, "", secs, text[-500:])
    return None


class Codex(Brain):
    id = "codex"
    label = "ChatGPT / Codex"
    kind = "cli"
    grace_s = 120

    def __init__(self, app_dir: Path | None = None, models: dict | None = None, exe: str | list[str] | None = None):
        self.exe = exe or _which("codex", app_dir)
        self.models = models or {}

    def available(self):
        return (True, "") if self.exe else (False, "Codex isn't installed")

    def run(self, task: Task) -> Result:
        if not self.exe:
            return Result(Verdict.ERROR, detail="Codex isn't installed")
        base = list(self.exe) if isinstance(self.exe, list) else [self.exe]
        minutes = max(1, task.timeout_s // 60)
        with tempfile.TemporaryDirectory() as tmp:
            last = Path(tmp) / "answer.txt"
            args = [
                *base,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--color",
                "never",
                "--output-last-message",
                str(last),
                "-c",
                f"model_reasoning_effort={task.effort}",
            ]
            if task.cwd:
                args += ["-C", str(task.cwd)]
            if self.models.get(task.effort):
                args += ["-m", self.models[task.effort]]
            args += codex_mcp(task)
            env = {**os.environ, **task.mcp_env} if task.mcp_env else None
            prompt = (task.context + "\n\n" + task.prompt).strip() if task.context else task.prompt
            t0 = time.monotonic()
            r = proc.run(
                [*args, "-"],
                input=prompt,
                timeout=task.timeout_s + self.grace_s,
                cwd=task.cwd,
                env=env,
                on_start=task.on_process,
            )
            secs = time.monotonic() - t0
            text = last.read_text(encoding="utf-8", errors="replace").strip() if last.exists() else ""
        bad = _fail(r.code, f"{r.out}\n{r.err}", secs, minutes)
        if bad and not text:
            return bad
        if r.code != 0 and not text:
            return Result(Verdict.ERROR, "", secs, (r.err or r.out)[-800:] or f"exit {r.code}")
        return Result(Verdict.OK if text else Verdict.EMPTY, text, secs)

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 120) -> Result:
        return self.run(Task(prompt=prompt, context=system, effort=effort, timeout_s=timeout))


class ClaudeCode(Brain):
    id = "claude"
    label = "Claude Code (Advanced)"
    kind = "cli"
    grace_s = 120

    def __init__(self, models: dict | None = None, exe: str | list[str] | None = None):
        self.exe = exe or _which("claude", None)
        self.models = models or {}

    def available(self):
        return (True, "") if self.exe else (False, "Claude Code isn't installed")

    def run(self, task: Task) -> Result:
        if not self.exe:
            return Result(Verdict.ERROR, detail="Claude Code isn't installed")
        base = list(self.exe) if isinstance(self.exe, list) else [self.exe]
        minutes = max(1, task.timeout_s // 60)
        with tempfile.TemporaryDirectory() as tmp:
            args = [*base, "-p", "--output-format", "json", "--allowedTools", "Read,Grep,Glob"]
            if task.mcp:  # this run only: Kurooto's tools, and no other MCP servers
                cfg = Path(tmp) / "mcp.json"
                server = {"command": task.mcp[0], "args": task.mcp[1:], "env": task.mcp_env}
                cfg.write_text(json.dumps({"mcpServers": {"kurooto": server}}), encoding="utf-8")
                args[-1] += ",mcp__kurooto"
                args += ["--mcp-config", str(cfg), "--strict-mcp-config"]
            if task.context:
                args += ["--append-system-prompt", task.context]
            if self.models.get(task.effort):
                args += ["--model", self.models[task.effort]]
            t0 = time.monotonic()
            r = proc.run(
                args, input=task.prompt, timeout=task.timeout_s + self.grace_s, cwd=task.cwd, on_start=task.on_process
            )
            secs = time.monotonic() - t0
        data = None
        for line in reversed((r.out or "").strip().splitlines()):
            try:
                data = json.loads(line)
                break
            except ValueError:
                continue
        if isinstance(data, dict) and data.get("type") == "result":
            text = str(data.get("result") or "").strip()
            if data.get("is_error"):
                bad = _fail(r.code if r.code is not None else 1, text + "\n" + (r.err or ""), secs, minutes)
                return bad or Result(Verdict.ERROR, "", secs, text[-800:])
            return Result(Verdict.OK if text else Verdict.EMPTY, text, secs, usage={"cost": data.get("total_cost_usd")})
        return _fail(r.code, f"{r.out}\n{r.err}", secs, minutes) or Result(
            Verdict.ERROR, "", secs, (r.err or r.out)[-800:] or f"exit {r.code}"
        )

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 120) -> Result:
        return self.run(Task(prompt=prompt, context=system, effort=effort, timeout_s=timeout))
