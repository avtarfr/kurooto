"""Antigravity (`agy`), Google's agent CLI: free with a Google account. It runs in your notes folder and can read
and write notes there.

Two ways to read its answer, picked at setup by a quick test: through pipes ("pipe"), or through a pseudo-terminal
("pty") for builds that print nothing when their output isn't a terminal.

Kurooto's tools reach agy as an MCP server, added once when agy is set up (`agy mcp add kurooto ...`). Unattended
runs may only do what agy's own allow-list says, so Kurooto adds what it needs to work for you (its settings file is
backed up first; your own rules are never removed): "mcp(kurooto/*)" for Kurooto's tools; reading your notes, your
Documents, Downloads and Screenshots, and Kurooto's copies of Classroom and mail (core/places.py); writing in your
notes folder, course files and add-ons' skills; reading web pages; harmless commands (ls, cat, grep, find, git, latexmk
...), never `kurooto` itself.
Outside the notes folder agy needs non-workspace access turned on, so that's set too unless you set it yourself.
The setup page's agy test says so and does it; someone who set agy up before (or before these permissions) is asked
once (Approve / Deny; Deny holds for 30 days) instead of having agy's settings changed by itself.
To undo: `agy mcp remove kurooto`, and take those lines out of ~/.gemini/antigravity-cli/settings.json (or put back
the backup from Kurooto's state folder, backups/).

With your own GBrain (gbrain.managed = false) and gbrain.agy_mcp on, the same approval also gives agy that brain's own
MCP server, registered as "gbrain" (unless agy has one by that name already, which is kept), and "mcp(gbrain/*)" in
its allow-list (unless you listed gbrain's tools there yourself, which are kept as they are). Undo: `agy mcp remove
gbrain` and that line.
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
GBRAIN_ALLOW = "mcp(gbrain/*)"  # every tool of your own GBrain's MCP server (gbrain.agy_mcp)
# shell commands that only read or are harmless (agy's rules name a program, not its arguments, so sed is left out:
# `sed -i` writes; and never `kurooto`, whose off/uninstall/restore must not run unattended)
# commands an unattended AI may run: none of them can start another program, whatever its arguments (find -exec,
# git -c or aliases, latexmk -e or a latexmkrc, rg --pre and sort --compress-program can, so they're not here: a
# prompt hidden in a mail or a web page must not get a way to run code). Searching is the AI programs' own tools'
# job, and Kurooto compiles LaTeX itself (skills.compile_tex).
COMMANDS = (
    "cat", "cd", "date", "echo", "file", "grep", "head", "jq", "ls", "mkdir", "pdftotext",
    "pwd", "stat", "tail", "tree", "uniq", "wc", "which",
)  # fmt: skip
# programs that run whatever they're given: never allowed as "a script" (agents.scripts)
INTERPRETERS = {
    "sh", "bash", "zsh", "fish", "dash", "ksh", "csh", "tcsh", "python", "python2", "python3", "pypy", "node", "deno",
    "bun", "perl", "ruby", "php", "lua", "tclsh", "env", "sudo", "su", "doas", "pkexec", "xargs", "nohup", "timeout",
    "nice", "exec", "pwsh", "powershell", "cmd", "osascript", "awk", "gawk", "mawk", "sed", "find", "git", "make",
    "npm", "npx", "uv", "uvx", "pip", "pip3", "docker", "podman", "ssh", "kurooto",
}  # fmt: skip
NON_WORKSPACE = {"allowNonWorkspaceAccess": True, "nonWorkspaceFileAccess": "allow"}  # set only when absent
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

    denied_help = (
        "agy refused to run this without you watching. Add a free Gemini key in Settings → AI "
        "(aistudio.google.com/apikey), then try again."
    )

    def available(self):
        return (True, "") if self.exe else (False, "agy isn't installed")

    def prepare(self, app):
        tools_once(app, self)

    def after_test(self, app) -> str:
        """Setting agy up: give it Kurooto's tools (`kurooto mcp`) now."""
        self.mark_worked(app)
        ok, why = connect_tools(app, self.exe)
        if ok:
            return (
                " It can now use Kurooto's tools, read your notes, Documents and Downloads, and write in your notes "
                "folder."
            )
        return f" (It can't use Kurooto's tools yet: {why}.)"

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
                code, out, err = run_pty(args, task.cwd, task.timeout_s + self.grace_s, env, task.on_process)
            else:
                r = proc.run(
                    args, cwd=task.cwd, timeout=task.timeout_s + self.grace_s, env=env, on_start=task.on_process
                )
                code, out, err = r.code, r.out, r.err
        finally:
            if long:
                long[0].unlink(missing_ok=True)
        result = verdict(code, out, err, time.monotonic() - t0, minutes)
        self.metered(None, result)  # agy's day's limit (core/quota.py); its own logs count the model requests
        return result

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
        from kurooto.core.quota import hints

        return Result(Verdict.RATE_LIMITED, "", secs, both[-500:], usage={"limit": hints(both)})
    if AUTH_FAIL.search(both) and (code != 0 or not out):
        return Result(Verdict.AUTH, "", secs, both[-500:])
    if code != 0:
        return Result(Verdict.ERROR, out, secs, (err or out)[-800:] or f"exit {code}")
    return Result(Verdict.OK if out else Verdict.EMPTY, out, secs, "" if out else (err[-500:] or "no output"))


def run_pty(
    args: list[str], cwd: Path | None, timeout: float, env: dict | None = None, on_start=None
) -> tuple[int | None, str, str]:
    """Run under a pseudo-terminal (ConPTY on Windows) and return (exit code, cleaned output, ""). `on_start(pid)`:
    as in proc.run."""
    deadline = time.monotonic() + timeout
    chunks: list[str] = []
    if sys.platform == "win32":
        from winpty import PtyProcess  # pywinpty

        p = PtyProcess.spawn(args, cwd=str(cwd) if cwd else None, env=env, dimensions=(50, 400))
    else:
        from ptyprocess import PtyProcessUnicode as PtyProcess

        p = PtyProcess.spawn(args, cwd=str(cwd) if cwd else None, env=env, dimensions=(50, 400))
    if getattr(p, "pid", None):
        from kurooto.core import children

        children.session(p.pid)  # a pty's program leads its own session (core/children.py)
        if on_start is not None:
            try:
                on_start(p.pid)
            except Exception:
                pass
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


def runnable(f: Path) -> bool:
    """Can this file be run as a program? On Windows every file passes os.access(X_OK), so there it's the extension
    (PATHEXT: .exe, .bat, .cmd...); elsewhere the execute bit."""
    if os.name == "nt":
        exts = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").lower().split(";")
        return f.suffix.lower() in {e for e in exts if e}
    return os.access(f, os.X_OK)


def safe_scripts(app) -> list[tuple[Path, str | None]]:
    """Your own scripts your AI programs may run (agents.scripts): (full path, the bare name when it's on PATH as
    that same file). Left out: a path that isn't absolute, not an executable file, or a shell or interpreter."""
    import shutil

    out = []
    for raw in (app.settings.get("agents.scripts") if app is not None else None) or []:
        f = Path(os.path.expanduser(str(raw)))
        if not f.is_absolute() or not f.is_file() or not runnable(f):
            continue
        if f.name.lower() in INTERPRETERS or f.stem.lower() in INTERPRETERS:
            continue
        on_path = shutil.which(f.name)
        same = on_path and Path(on_path).resolve() == f.resolve()
        out.append((f, f.name if same else None))
    return out


def wanted_rules(app: App) -> list[str]:
    """agy's allow-list entries Kurooto adds: its tools, harmless commands, what it may read (core/places.py: the same
    folders Kurooto's own read_file tool may), writing in the notes folder, and the web."""
    from kurooto.core.places import read_roots, write_roots

    rules = [ALLOW, *(f"command({c})" for c in COMMANDS)]
    for f, name in safe_scripts(app):  # your own scripts (agents.scripts), by full path and by name
        rules += [f"command({f})", *([f"command({name})"] if name else [])]
    rules += [f"read_file({p})" for p in read_roots(app)]
    rules += [f"write_file({p})" for p in write_roots(app)]
    if gbrain_mcp(app):
        rules.append(GBRAIN_ALLOW)
    return [*rules, "read_url(*)"]


def gbrain_mcp(app: App):
    """The GBrain module when agy should get your own brain's MCP server (your own GBrain, gbrain.agy_mcp on, the
    Notes brain on), else None. Kurooto's own brain is never handed to agy this way: agy searches it through Kurooto's
    tools."""
    gb = app.modules.get("gbrain") if hasattr(app, "modules") else None
    if gb is None or not app.is_on("gbrain") or not getattr(gb, "external", lambda: False)():
        return None
    return gb if gb.setting("agy_mcp") and gb.exe() else None


def connect_gbrain(app: App, base: list[str]) -> tuple[bool, str]:
    """Register your own brain's MCP server with agy as "gbrain" (`gbrain serve`), unless agy has a "gbrain" already."""
    gb = gbrain_mcp(app)
    if gb is None:
        return True, ""
    have = proc.run([*base, "mcp", "list"], timeout=60)
    if have.code == 0 and re.search(r"(?mi)^\W*gbrain\b", have.out or ""):
        return True, "agy has your GBrain already"
    home = gb.brain_home()
    flags = ["--env", f"GBRAIN_HOME={home}"] if home is not None else []
    surface = str(gb.setting("mcp_surface") or "full")
    surface = surface if surface in ("full", "starter", "verbs") else "full"
    from kurooto.modules.gbrain import serve_command

    cmd = [*serve_command(gb.exe()), "--surface", surface]
    r = proc.run([*base, "mcp", "add", *flags, "gbrain", "--", *cmd], timeout=60)
    if r.code != 0:
        return False, f"agy didn't take your GBrain: {(r.err or r.out).strip()[-200:] or f'exit {r.code}'}"
    return True, "agy has your GBrain's tools"


def allow_tools(backups: Path, rules: list[str] | None = None, extra: dict | None = None) -> tuple[bool, str]:
    """Add Kurooto's entries to agy's permissions.allow (and `extra` settings that aren't set yet), backing its
    settings file up first. Your own rules and settings stay as they are; nothing is removed."""
    rules, extra = rules or [ALLOW], extra or {}
    f = settings_file()
    data = jload(f, None) if f.exists() else {}
    perms = data.setdefault("permissions", {}) if isinstance(data, dict) else None
    allow = perms.setdefault("allow", []) if isinstance(perms, dict) else None
    if not isinstance(allow, list):
        return False, f"agy's settings ({f}) aren't in the shape Kurooto expects; add {ALLOW} to permissions.allow"
    own_gbrain = any(str(a).startswith("mcp(gbrain/") for a in allow)  # your own picks of gbrain's tools stay
    add = [r for r in rules if r not in allow and not (r == GBRAIN_ALLOW and own_gbrain)]
    keys = {k: v for k, v in extra.items() if k not in data}
    if not add and not keys:
        return True, "agy may already use Kurooto's tools"
    if f.exists():
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, backups / f"agy-settings-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}.json")
    allow.extend(add)
    data.update(keys)
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
        ok, msg = allow_tools(app.paths.state / "backups", wanted_rules(app), NON_WORKSPACE)
        if ok:
            ok, extra = connect_gbrain(app, base)
            msg = f"{msg}; {extra}" if extra and ok else (extra or msg)
    jsave(
        app.paths.state / "agy-tools.json",
        {"command": cmd, "ok": ok, "message": msg, "version": __version__, "granted": wanted_rules(app)},
    )
    app.events.emit("agy_tools", ok=ok)
    return ok, msg


def tools_once(app: App, brain: Agy) -> None:
    """Before an agy run: if agy was set up before it could have Kurooto's tools, ask once whether it may (agy's
    settings are yours); if they were connected before and Kurooto's command changed since (an update), connect them
    again. A failure isn't retried here; the setup page's test tries again."""
    from kurooto.core.mcp import command

    if not isinstance(brain.exe, str):  # a test's fake agy
        return
    if os.environ.get("KUROOTO_HOME") and os.environ.get("KUROOTO_AGY_TOOLS") != "1":
        return  # a portable or test copy leaves agy's own settings alone unless set up through the setup page
    before = jload(app.paths.state / "agy-tools.json", {}) or {}
    covered = set(wanted_rules(app)) <= set(before.get("granted") or [])
    if before.get("command") == command(persistent=True) and covered:
        return
    if not covered:  # never connected, or more is wanted than was agreed (e.g. add-ons turned on): yours to decide
        ask_consent(app, brain.exe)
        return
    try:
        connect_tools(app, brain.exe)
    except Exception as e:
        app.events.emit("agy_tools", ok=False, error=f"{type(e).__name__}: {e}"[:200])


CONSENT = (
    "Let agy work for you unattended? Kurooto adds these to agy's settings (a backup is kept; nothing of yours is "
    "removed):\n"
    "- Kurooto's tools: reminders, notes, calls, deadlines and the rest you have on\n"
    "- read your notes, your Documents, Downloads and Screenshots, and Kurooto's copies of Classroom and mail\n"
    "- write in your notes folder, your course files folder and, with add-ons on, your add-ons' skills (Documents and "
    "Downloads stay read-only)\n"
    "- read web pages\n"
    "- run harmless commands such as ls, cat, grep, find and git, and latexmk to build PDFs (never Kurooto's own "
    "command)"
)
CONSENT_GBRAIN = (
    '\n- your own GBrain\'s tools (its MCP server, as "gbrain"): all of them, also the ones that change or remove '
    "pages in that brain"
)
DENY_DAYS = 30


def consent_file(state: Path) -> Path:
    return state / "agy-tools-consent.json"


def ask_consent(app: App, exe: str | None = None) -> str | None:
    """Ask (an approval) whether agy may use Kurooto's tools, unless that's waiting for an answer already or was
    denied in the last 30 days. The question's id, or None."""
    from kurooto.core.ask import OPEN

    f = consent_file(app.paths.state)
    c = jload(f, {}) or {}
    q = app.ask.get(c["qid"]) if c.get("qid") else None
    if q and q.get("status") in OPEN:
        return None
    if c.get("denied") and time.time() - float(c["denied"]) < DENY_DAYS * 86400:
        return None
    text = CONSENT + (CONSENT_GBRAIN if gbrain_mcp(app) else "")
    qid = app.ask.ask(
        text,
        kind="approval",
        hook="agy.tools",
        hook_payload={"exe": exe or ""},
        source="agy",
        title="agy",
        why="agy.consent",
    )
    jsave(f, {"qid": qid, "asked": time.time()})
    return qid


def consent_answer(app: App, q: dict, answer: str) -> str:
    """The answer to ask_consent's question (app.ask.hooks["agy.tools"])."""
    from kurooto.core.ask import APPROVE

    f = consent_file(app.paths.state)
    if str(answer).strip().lower() == APPROVE.lower():
        ok, msg = connect_tools(app, (q.get("hook_payload") or {}).get("exe") or None)
        jsave(f, {"approved": time.time(), "ok": ok})
        return f"{msg[:1].upper()}{msg[1:]}." if ok else f"That didn't work: {msg}."
    jsave(f, {"denied": time.time()})
    app.events.emit("agy_tools", ok=False, error="denied")
    return (
        f"OK, agy works without Kurooto's tools; I won't ask again for {DENY_DAYS} days. "
        "(The agy test on the setup page connects them any time.)"
    )


# ------------------------------------------------------------------------------- (ws5) agy's own count, for /usage
LIMIT_HIT = re.compile(rb"RESOURCE_EXHAUSTED|quota exceeded|rate limit exceeded|429 Too Many", re.I)
LOG_MAX = 64 * 1024 * 1024  # a log bigger than this is only read this far


def log_dir() -> Path:
    return settings_file().parent / "log"


def log_usage(days: int = 7, folder: Path | None = None) -> list[dict]:
    """agy's own count, from its logs: every agy run on this computer (the ones you typed too, not only Kurooto's),
    its model requests and usage-limit hits, per day. [] when agy has no logs here. Only counted: nothing in the
    logs is read out or kept."""
    import datetime as dt

    folder = folder or log_dir()
    if not folder.is_dir():
        return []
    out = []
    for i in range(days - 1, -1, -1):
        d = dt.date.today() - dt.timedelta(days=i)
        runs = reqs = limited = 0
        for f in folder.glob(f"cli-{d:%Y%m%d}_*.log"):
            try:
                with open(f, "rb") as fh:
                    data = fh.read(LOG_MAX)
            except OSError:
                continue
            runs += 1
            reqs += data.count(b"streamGenerateContent")
            limited += len(LIMIT_HIT.findall(data))
        out.append({"day": d.isoformat(), "runs": runs, "requests": reqs, "limited": limited})
    return out if any(r["runs"] for r in out) else []


_counted: dict = {}  # (log file, size, mtime) -> model requests: a log is read again only when it changed


def log_requests_since(since: float, folder: Path | None = None) -> int | None:
    """Model requests in agy's logs written since `since` (a timestamp): every agy run on this computer, the ones you
    typed too, for the free-tier reserve (core/quota.py). None when agy has no logs here. Only counted."""
    folder = folder or log_dir()
    if not folder.is_dir():
        return None
    n, seen = 0, {}
    for f in folder.glob("cli-*.log"):
        try:
            st = f.stat()
        except OSError:
            continue
        if st.st_mtime < since:
            continue
        key = (str(f), st.st_size, st.st_mtime)
        if key not in _counted:
            try:
                with open(f, "rb") as fh:
                    _counted[key] = fh.read(LOG_MAX).count(b"streamGenerateContent")
            except OSError:
                continue
        seen[key] = _counted[key]
        n += seen[key]
    _counted.clear()
    _counted.update(seen)
    return n


def log_usage_text(rows: list[dict]) -> str:
    """The lines /usage adds for agy's own count."""
    if not rows:
        return ""
    lines = ["\nagy itself (every run on this computer, also the ones you typed), from its logs:"]
    for r in rows:
        d = time.strptime(r["day"], "%Y-%m-%d")
        hit = f", limit hit {r['limited']}" if r["limited"] else ""
        lines.append(f"{time.strftime('%a %d %b', d)}  {r['runs']} runs, {r['requests']} model requests{hit}")
    reqs = sum(r["requests"] for r in rows)
    lines.append(f"{len(rows)}-day total: {reqs} model requests, {sum(r['runs'] for r in rows)} runs.")
    if any(r["limited"] for r in rows):
        lines.append("agy hit its usage limit on those days (Google doesn't publish the exact limits).")
    return "\n".join(lines)
