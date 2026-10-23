"""Claude Code as an AI brain (Advanced), with the same reach agy has in Kurooto.

Each run gets its permissions from Kurooto, the same folders and harmless commands as agy's allow-list
(providers/agy.py, core/places.py): read your notes, course files and Documents/Downloads; write in the notes folder,
the course files folder and your add-ons' skills; harmless commands; the web; Kurooto's tools, and your own GBrain's
when gbrain.agy_mcp is on. Nothing else is allowed (`--permission-mode dontAsk`), and `kurooto` itself never runs
from inside a request. Nothing is saved in Claude Code's own settings, nor are its user, project or local settings,
hooks or session history used: all of it is given for the run only, so there's nothing to undo.

Settings: brain.models.claude {"low": "haiku", "medium": "sonnet", "high": "sonnet"} (any model name Claude Code
takes), and your Claude sign-in (`claude` once, or Settings → AI → Test). An extra Claude account ("claude:work",
providers/claude_accounts.py) is the same brain run with CLAUDE_CONFIG_DIR set to its own folder of Kurooto's.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import egress, proc
from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict

if TYPE_CHECKING:
    from kurooto.app import App

MODELS = {"low": "haiku", "medium": "sonnet", "high": "sonnet"}  # names Claude Code keeps pointed at the latest
LIMIT_RESET = re.compile(r"usage limit reached\|(\d{9,11})", re.I)  # "Claude AI usage limit reached|<epoch>"
# Claude Code's own words for its plan limits: "5-hour limit reached ∙ resets 3pm", "You've hit your limit · resets
# 3pm (Europe/Berlin)", "Weekly limit reached ∙ resets Oct 27, 9am", "Opus weekly limit reached ∙ resets Mon 9am"
PLAN_LIMIT = re.compile(
    r"\b(?:5-hour|weekly|session|opus|sonnet) limit\b|hit your (?:usage )?limit|limit reached", re.I
)
RESETS = re.compile(
    r"reset(?:s|ting)?(?:\s+at|\s+on)?\s+"
    r"(?:(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?P<day>\d{1,2}),?\s+(?:at\s+)?)?"
    r"(?:(?P<wd>Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:at\s+)?)?"
    r"(?P<h>\d{1,2})(?::(?P<mi>\d{2}))?\s*(?P<ap>[ap]\.?m\.?)?"
    r"(?:\s*\((?P<tz>[A-Za-z_]+(?:/[A-Za-z_+-]+)+|UTC|GMT)\))?",
    re.I,
)
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DENIAL_NAMES = 5  # how many refused tools the log line names


def reset_at(text: str, now: float | None = None) -> float | None:
    """When a Claude plan limit comes back, from Claude Code's own message: "...|<epoch>", "resets 3pm",
    "resets 3:30pm (Asia/Kolkata)", "resets Oct 27, 9am", "resets Mon 9am". A timestamp, or None when it doesn't say."""
    import datetime as dt
    from zoneinfo import ZoneInfo

    text = str(text or "")
    now = time.time() if now is None else now
    m = LIMIT_RESET.search(text)
    if m:
        return float(m.group(1))
    for m in RESETS.finditer(text):
        if not (m["ap"] or m["mi"]):  # a bare number isn't a time ("resets in 5 hours" is quota.hints's)
            continue
        try:
            tz = ZoneInfo("UTC" if (m["tz"] or "").upper() == "GMT" else m["tz"]) if m["tz"] else None
        except Exception:
            tz = None
        h, mi = int(m["h"]), int(m["mi"] or 0)
        ap = (m["ap"] or "").lower()[:1]
        if h > 23 or mi > 59 or (ap and not 1 <= h <= 12):
            continue
        h = h % 12 + (12 if ap == "p" else 0) if ap else h
        base = dt.datetime.fromtimestamp(now, tz) if tz else dt.datetime.fromtimestamp(now)
        when = base.replace(hour=h, minute=mi, second=0, microsecond=0)
        if m["mon"]:
            try:
                when = when.replace(month=MONTHS.index(m["mon"][:3].lower()) + 1, day=int(m["day"]))
            except ValueError:
                continue
            if when <= base:
                when = when.replace(year=when.year + 1)
        elif m["wd"]:
            ahead = (DAYS.index(m["wd"][:3].lower()) - when.weekday()) % 7
            when += dt.timedelta(days=ahead)
            if when <= base:
                when += dt.timedelta(days=7)
        elif when <= base:
            when += dt.timedelta(days=1)
        return when.timestamp()
    return None


def used_model(data: dict) -> str:
    """The model that did the work, from `--output-format json`'s modelUsage (the one that cost the most, else wrote
    the most) or its model field; "" when it doesn't say."""
    usage = data.get("modelUsage") if isinstance(data.get("modelUsage"), dict) else {}
    best, score = "", (-1.0, -1.0)
    for name, u in usage.items():
        u = u if isinstance(u, dict) else {}
        try:
            s = (float(u.get("costUSD") or 0), float(u.get("outputTokens") or 0))
        except (TypeError, ValueError):
            s = (0.0, 0.0)
        if s > score:
            best, score = str(name), s
    return best or str(data.get("model") or "")


def _which(name: str, app_dir: Path | None = None) -> str | None:
    dirs = [Path.home() / ".local" / "bin"]
    if app_dir:
        dirs += [app_dir / "npm", app_dir / "npm" / "bin"]
    return proc.which(name, dirs)


def _fail(code: int | None, text: str, secs: float, minutes: int) -> Result | None:
    if code is None:
        return Result(Verdict.TIMEOUT, "", secs, f"timed out after {minutes} min")
    if RATE_LIMIT.search(text) or PLAN_LIMIT.search(text):
        return Result(Verdict.RATE_LIMITED, "", secs, text[-500:])
    if AUTH_FAIL.search(text) or "/login" in text:
        return Result(Verdict.AUTH, "", secs, text[-500:])
    return None


def limited(res: Result, text: str) -> None:
    """A plan limit: when it resets (when Claude Code says), as retry_after_s and as a hint the free-limit count reads
    (core/quota.py), so it's known as used up until then."""
    at = reset_at(text)
    if at is None:
        return
    res.retry_after_s = max(0, int(at - time.time()))
    res.usage = {**res.usage, "limit": {"per": None, "limit": None, "retry_s": None, "reset_at": at, "model": None}}


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
    if task.mcp:  # Kurooto's tools, and its resources (kurooto://self: what it's running)
        allow += ["mcp__kurooto", "ListMcpResourcesTool", "ReadMcpResourceTool"]
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
    label = "Claude Code"  # the brain's name everywhere; "Advanced" is only the setup page's grouping (web/api.py)
    kind = "cli"
    grace_s = 120

    def __init__(
        self,
        models: dict | None = None,
        exe: str | list[str] | None = None,
        app: App | None = None,
        account: str = "",
        name: str = "",
        config_dir: Path | None = None,
    ):
        self.exe = exe or _which("claude", None)
        self.models = {**MODELS, **{k: v for k, v in (models or {}).items() if v}}
        self.app = app
        self.config_dir = config_dir  # an extra account's own folder (CLAUDE_CONFIG_DIR); None: your usual sign-in
        if account:  # an extra account: its own id, so its own limit, receipt line and "has worked"
            self.id = f"claude:{account}"
            self.label = f"Claude Code ({name or account})"

    def available(self):
        if not self.exe:
            return False, "Claude Code isn't installed"
        if self.config_dir is not None and not Path(self.config_dir).is_dir():
            return False, f"{self.label} isn't signed in on this computer (Settings → Claude accounts → Sign in)"
        return True, ""

    def env(self) -> dict | None:
        """The environment of a run: an extra account's folder as CLAUDE_CONFIG_DIR (where its sign-in lives); None
        for your usual sign-in, which runs exactly as before."""
        if self.config_dir is None:
            return None
        return {**os.environ, "CLAUDE_CONFIG_DIR": str(self.config_dir)}

    def sees(self):
        return True, ""  # Claude Code reads a picture with its Read tool, where the request says it is

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
            egress.handed("Claude Code", "AI requests")  # what it sends to Anthropic, it sends itself
            t0 = time.monotonic()
            r = proc.run(
                args,
                input=task.prompt,
                timeout=task.timeout_s + self.grace_s,
                cwd=task.cwd,
                env=self.env(),
                on_start=task.on_process,
            )
            secs = time.monotonic() - t0
        result = self.verdict(r, secs, minutes)
        result.model = result.model or self.models.get(task.effort) or ""  # what it said it used, else what was asked
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
            model = used_model(data)
            if denied:
                usage["denied"] = denied[:DENIAL_NAMES]
            if data.get("is_error"):
                bad = _fail(r.code if r.code is not None else 1, text + "\n" + (r.err or ""), secs, minutes)
                if bad is not None:
                    bad.model = model
                    if bad.verdict == Verdict.RATE_LIMITED:
                        limited(bad, text)
                    return bad
                return Result(Verdict.ERROR, "", secs, text[-800:], model=model)
            if text:
                return Result(Verdict.OK, text, secs, usage=usage, model=model)
            if denied:  # it stopped at something unattended runs may not do
                what = ", ".join(sorted(set(denied)))
                return Result(
                    Verdict.DENIED, "", secs, f"Claude Code stopped: it tried {what}, which isn't allowed", model=model
                )
            return Result(Verdict.EMPTY, "", secs, usage=usage, model=model)
        bad = _fail(r.code, f"{r.out}\n{r.err}", secs, minutes)
        if bad is not None and bad.verdict == Verdict.RATE_LIMITED:
            limited(bad, f"{r.out}\n{r.err}")
        return bad or Result(Verdict.ERROR, "", secs, (r.err or r.out)[-800:] or f"exit {r.code}")

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 120) -> Result:
        return self.run(Task(prompt=prompt, context=system, effort=effort, timeout_s=timeout, text_only=True))
