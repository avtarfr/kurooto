"""Claude Code as an AI brain (Advanced), with the same reach agy has in Kurooto.

Each run gets its permissions from Kurooto, the same folders and harmless commands as agy's allow-list
(providers/agy.py, core/places.py): read your notes, course files and Documents/Downloads; write in the notes folder,
the course files folder and your add-ons' skills; harmless commands; the web; Kurooto's tools, and your own GBrain's
when gbrain.agy_mcp is on. Nothing else is allowed (`--permission-mode dontAsk`), and `kurooto` itself never runs
from inside a request. Nothing is saved in Claude Code's own settings, nor are its user, project or local settings,
hooks or session history used: all of it is given for the run only, so there's nothing to undo.

Settings: brain.models.claude {"low": "haiku", "medium": "sonnet", "high": "sonnet"} (any model name Claude Code
takes), and your Claude sign-in (`claude` once, or Settings → AI → Test).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import proc
from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict

if TYPE_CHECKING:
    from kurooto.app import App

MODELS = {"low": "haiku", "medium": "sonnet", "high": "sonnet"}  # names Claude Code keeps pointed at the latest
LIMIT_RESET = re.compile(r"usage limit reached\|(\d{9,11})", re.I)  # "Claude AI usage limit reached|<epoch>"
DENIAL_NAMES = 5  # how many refused tools the log line names


def _which(name: str, app_dir: Path | None = None) -> str | None:
    dirs = [Path.home() / ".local" / "bin"]
    if app_dir:
        dirs += [app_dir / "npm", app_dir / "npm" / "bin"]
    return proc.which(name, dirs)


def _fail(code: int | None, text: str, secs: float, minutes: int) -> Result | None:
    if code is None:
        return Result(Verdict.TIMEOUT, "", secs, f"timed out after {minutes} min")
    if RATE_LIMIT.search(text):
        return Result(Verdict.RATE_LIMITED, "", secs, text[-500:])
    if AUTH_FAIL.search(text) or "/login" in text:
        return Result(Verdict.AUTH, "", secs, text[-500:])
    return None


def rule_path(p: Path | str) -> str:
    """A folder as Claude Code's permission rules name it: `//` and the path from the root; on Windows the drive is
    the first part (C:\\Users\\me -> //c/Users/me)."""
    s = os.path.abspath(str(p)).replace("\\", "/").rstrip("/")
    m = re.match(r"^([A-Za-z]):(/.*)?$", s)
    if m:
        return f"//{m.group(1).lower()}{m.group(2) or ''}"
    return "/" + s


def permissions(app: App | None, task: Task) -> tuple[dict, list[str]]:
    """The run's permissions ({"permissions": ...} for `--settings`) and the folders outside the notes it reads."""
    from kurooto.providers.agy import COMMANDS, gbrain_mcp, safe_scripts

    allow: list[str] = []
    dirs: list[Path] = []
    if app is not None:
        from kurooto.core.places import read_roots, write_roots

        write = write_roots(app)
        read = read_roots(app)
        allow += [f"Edit({rule_path(p)}/**)" for p in write]
        allow += [f"Read({rule_path(p)}/**)" for p in read]
        dirs = [p for p in read if p.is_dir()]
    elif task.cwd:  # no app (tests): the folder it runs in
        allow += [f"Read({rule_path(task.cwd)}/**)"]
    for c in COMMANDS:
        allow += [f"Bash({c})", f"Bash({c} *)"]
    for f, name in safe_scripts(app) if app is not None else []:  # your own scripts (agents.scripts)
        allow += [f"Bash({f})", f"Bash({f} *)", *([f"Bash({name})", f"Bash({name} *)"] if name else [])]
    allow += ["WebFetch", "WebSearch"]
    if task.mcp:
        allow.append("mcp__kurooto")
    if app is not None and gbrain_mcp(app):
        allow.append("mcp__gbrain")
    cfg = {
        "permissions": {
            "defaultMode": "dontAsk",
            "allow": list(dict.fromkeys(allow)),
            "deny": ["Bash(kurooto)", "Bash(kurooto *)"],  # off, uninstall and restore never run unattended
        }
    }
    return cfg, [str(p) for p in dirs]


def mcp_servers(app: App | None, task: Task) -> dict:
    servers: dict = {}
    if task.mcp:
        servers["kurooto"] = {"command": task.mcp[0], "args": task.mcp[1:], "env": task.mcp_env}
    if app is not None:
        from kurooto.modules.gbrain import serve_command
        from kurooto.providers.agy import gbrain_mcp

        gb = gbrain_mcp(app)
        if gb is not None:
            surface = str(gb.setting("mcp_surface") or "full")
            surface = surface if surface in ("full", "starter", "verbs") else "full"
            cmd = [*serve_command(gb.exe()), "--surface", surface]
            home = gb.brain_home()
            servers["gbrain"] = {
                "command": cmd[0],
                "args": cmd[1:],
                "env": {"GBRAIN_HOME": str(home)} if home is not None else {},
            }
    return servers


class ClaudeCode(Brain):
    id = "claude"
    label = "Claude Code (Advanced)"
    kind = "cli"
    grace_s = 120

    def __init__(self, models: dict | None = None, exe: str | list[str] | None = None, app: App | None = None):
        self.exe = exe or _which("claude", None)
        self.models = {**MODELS, **{k: v for k, v in (models or {}).items() if v}}
        self.app = app

    def available(self):
        return (True, "") if self.exe else (False, "Claude Code isn't installed")

    def after_test(self, app) -> str:
        """Nothing to set up: everything is given for each request. Say what it can do."""
        return (
            " It can use Kurooto's tools, read your notes, Documents and Downloads, and write in your notes folder, "
            "for each request."
        )

    def args(self, task: Task, tmp: Path) -> list[str]:
        """The command for one run: its permissions, tools and prompt are files in `tmp`, gone after the run."""
        base = list(self.exe) if isinstance(self.exe, list) else [self.exe]
        args = [
            *base,
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--setting-sources",
            "",  # none of your own Claude Code settings, hooks or project files: what Kurooto gives is all there is
            "--permission-mode",
            "dontAsk",
        ]
        if task.text_only:
            args += ["--tools", ""]
        else:
            cfg, dirs = permissions(self.app, task)
            f = tmp / "settings.json"
            f.write_text(json.dumps(cfg), encoding="utf-8")
            args += ["--settings", str(f)]
            if dirs:
                args += ["--add-dir", *dirs]
            servers = {} if task.text_only else mcp_servers(self.app, task)
            if servers:
                m = tmp / "mcp.json"
                m.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
                args += ["--mcp-config", str(m), "--strict-mcp-config"]
        if task.context:  # in a file: a command line has a length limit (Windows' is short)
            c = tmp / "context.md"
            c.write_text(task.context, encoding="utf-8")
            args += ["--append-system-prompt-file", str(c)]
        if task.effort in ("low", "medium", "high"):
            args += ["--effort", task.effort]
        if self.models.get(task.effort):
            args += ["--model", self.models[task.effort]]
        return args

    def run(self, task: Task) -> Result:
        if not self.exe:
            return Result(Verdict.ERROR, detail="Claude Code isn't installed")
        minutes = max(1, task.timeout_s // 60)
        with tempfile.TemporaryDirectory() as tmp:
            args = self.args(task, Path(tmp))
            t0 = time.monotonic()
            r = proc.run(
                args, input=task.prompt, timeout=task.timeout_s + self.grace_s, cwd=task.cwd, on_start=task.on_process
            )
            secs = time.monotonic() - t0
        result = self.verdict(r, secs, minutes)
        self.metered(None, result)  # counted against its own limit (core/quota.py)
        return result

    def verdict(self, r, secs: float, minutes: int) -> Result:
        data = None
        for line in reversed((r.out or "").strip().splitlines()):
            try:
                data = json.loads(line)
                break
            except ValueError:
                continue
        if isinstance(data, dict) and data.get("type") == "result":
            text = str(data.get("result") or "").strip()
            denied = [
                str(d.get("tool_name") or "") for d in data.get("permission_denials") or [] if isinstance(d, dict)
            ]
            usage = {"cost": data.get("total_cost_usd")}
            if denied:
                usage["denied"] = denied[:DENIAL_NAMES]
            if data.get("is_error"):
                bad = _fail(r.code if r.code is not None else 1, text + "\n" + (r.err or ""), secs, minutes)
                if bad is not None:
                    m = LIMIT_RESET.search(text)
                    if bad.verdict == Verdict.RATE_LIMITED and m:
                        bad.retry_after_s = max(0, int(m.group(1)) - int(time.time()))
                    return bad
                return Result(Verdict.ERROR, "", secs, text[-800:])
            if text:
                return Result(Verdict.OK, text, secs, usage=usage)
            if denied:  # it stopped at something unattended runs may not do
                what = ", ".join(sorted(set(denied)))
                return Result(Verdict.DENIED, "", secs, f"Claude Code stopped: it tried {what}, which isn't allowed")
            return Result(Verdict.EMPTY, "", secs, usage=usage)
        return _fail(r.code, f"{r.out}\n{r.err}", secs, minutes) or Result(
            Verdict.ERROR, "", secs, (r.err or r.out)[-800:] or f"exit {r.code}"
        )

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 120) -> Result:
        return self.run(Task(prompt=prompt, context=system, effort=effort, timeout_s=timeout, text_only=True))
