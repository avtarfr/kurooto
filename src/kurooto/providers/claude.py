"""Claude Code as an AI brain (Advanced), with the same reach agy has in Kurooto.

Each run gets its permissions from Kurooto, the same folders and harmless commands as agy's allow-list
(providers/agy.py, core/places.py): read your notes, course files and Documents/Downloads; write in the notes folder,
the course files folder and your add-ons' skills; harmless commands; the web; Kurooto's tools, and your own GBrain's
when gbrain.agy_mcp is on. A change request (core/scratch.py) runs in its scratch folder and may edit only there;
the real folders are denied for editing, and files of keys or passwords for reading. Nothing else is allowed
(`--permission-mode dontAsk`), and `kurooto` itself never runs from inside a request. Nothing is saved in Claude Code's
own settings, nor are its user, project or local settings, hooks or session history used: all of it is given for the run
only, so there's nothing to undo.

Settings: brain.models.claude {"low": "haiku", "medium": "sonnet", "high": "sonnet"} (any model name Claude Code
takes), and your Claude sign-in (`claude` once, or Settings → AI → Test). An extra Claude account ("claude:work",
providers/claude_accounts.py) is the same brain run with CLAUDE_CONFIG_DIR set to its own folder of Kurooto's.

(0.8.17, brain.claude.session) A conversation's requests (Task.session: a chat's, spoken ones too) go to one Claude
Code kept running for it (Session, `--input-format stream-json`), one message a turn, instead of a new program each
time: the same command, permissions, tools and folders as a run of its own, so it may do nothing more. It closes after
brain.claude.session_idle_min, when its AI or the switch changes, and with Kurooto; a failed one hands the turn to a
run of its own.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import tempfile
import threading
import time
from dataclasses import replace
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
SCRATCH_NO = {"mkdir", "echo"}  # commands a change request doesn't get: they could write outside its scratch folder
SESSIONS_MAX = 2  # (brain.claude.session) Claude Code programs kept at once; the longest idle goes first
IDLE_MIN = 10  # brain.claude.session_idle_min's default
REAP_S = 15  # how often kept programs are looked at
FIRST_S = 45  # a new one silent this long after its first message: it isn't answering that way (a run of its own)
SAID_KEEP = 40  # messages and answers a session remembers it saw (to leave out chat's history it already has)
HISTORY, CURRENT = "Previous conversation:\n", "\nCurrent request:\n"  # chat's request with history (modules/chat.py)
NEWS = "[New since this conversation began; where it differs from your instructions, this wins:]"


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
    """The run's permissions ({"permissions": ...} for `--settings`) and the folders outside the notes it reads.

    A change request (task.scratch, core/scratch.py) may edit its scratch folder and nothing else: Edit is allowed
    there only, editing the original and every usual write folder is denied outright, commands that write (mkdir,
    echo) aren't allowed, and files of keys or passwords (.env, *.pem, id_rsa ...) are denied for reading and editing
    in every folder it can see."""
    from kurooto.providers.agy import COMMANDS, gbrain_mcp, safe_scripts

    allow: list[str] = []
    deny: list[str] = ["Bash(kurooto)", "Bash(kurooto *)"]  # off, uninstall and restore never run unattended
    dirs: list[Path] = []
    scratch = Path(task.scratch) if task.scratch else None
    if app is not None:
        from kurooto.core.places import read_roots, write_roots

        write = write_roots(app, scratch=scratch)
        read = read_roots(app, extra=[*task.reads, *([scratch] if scratch else [])])
        allow += [f"Edit({rule_path(p)}/**)" for p in write]
        allow += [f"Read({rule_path(p)}/**)" for p in read]
        dirs = [p for p in read if p.is_dir()]
        if scratch is not None:
            inside = scratch.resolve()
            for p in [*write_roots(app), *task.reads]:  # never the real folders, even if a rule above were wider
                rp = Path(p).resolve()
                if rp != inside and rp not in inside.parents:
                    deny.append(f"Edit({rule_path(p)}/**)")
            from kurooto.core.scratch import SECRETS

            for p in read:
                deny += [f"Read({rule_path(p)}/**/{pat})" for pat in SECRETS]
            deny += [f"Edit({rule_path(scratch)}/**/{pat})" for pat in SECRETS]
    elif task.cwd:  # no app (tests): the folder it runs in
        allow += [f"Read({rule_path(task.cwd)}/**)"]
    # (0.8.17) the pictures the job is about (Task.images: a screenshot Interest asked about, a photo from the phone):
    # those files exactly, and their folder so Claude Code can reach them. They were only named in the prompt, so
    # reading them was denied in every unattended run
    pics = [Path(i) for i in task.images or [] if Path(i).is_file()]
    allow += [f"Read({rule_path(i)})" for i in pics]
    dirs += [d for d in dict.fromkeys(i.parent for i in pics) if d not in dirs]
    for c in COMMANDS if scratch is None else [c for c in COMMANDS if c not in SCRATCH_NO]:
        allow += [f"Bash({c})", f"Bash({c} *)"]
    for f, name in safe_scripts(app) if app is not None and scratch is None else []:  # your scripts (agents.scripts)
        allow += [f"Bash({f})", f"Bash({f} *)", *([f"Bash({name})", f"Bash({name} *)"] if name else [])]
    allow += ["WebFetch", "WebSearch"]
    if task.mcp:  # Kurooto's tools, and its resources (kurooto://self: what it's running)
        allow += ["mcp__kurooto", "ListMcpResourcesTool", "ReadMcpResourceTool"]
    if app is not None and gbrain_mcp(app) and scratch is None:
        allow.append("mcp__gbrain")
    cfg = {
        "permissions": {
            "defaultMode": "dontAsk",
            "allow": list(dict.fromkeys(allow)),
            "deny": list(dict.fromkeys(deny)),
        }
    }
    return cfg, [str(p) for p in dirs]


def mcp_servers(app: App | None, task: Task) -> dict:
    servers: dict = {}
    if task.mcp:
        servers["kurooto"] = {"command": task.mcp[0], "args": task.mcp[1:], "env": task.mcp_env}
    if app is not None and not task.scratch:  # a change request gets Kurooto's tools only (they write in its folder)
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


class Lines:
    """(voice.speak.stream) Claude Code's stream-json, a line at a time, as on_text(key, text so far): the text deltas
    of each message (--include-partial-messages), else each whole assistant message. `key` is the message's id, so the
    words it wrote before a tool call are a message of their own and the answer the last one. A subagent's messages
    (parent_tool_use_id) are left out. A line that isn't JSON, or a mistake in on_text, never stops the run."""

    def __init__(self, on_text):
        self.on_text = on_text
        self.key: str | None = None
        self.text = ""
        self.n = 0
        self.deltas: set[str] = set()  # messages whose text came in deltas: their whole message adds nothing

    def _new(self, key: str) -> None:
        self.key, self.text, self.n = key or f"m{self.n}", "", self.n + 1

    def _tell(self) -> None:
        try:
            self.on_text(self.key, self.text)
        except Exception:
            pass

    def line(self, line: str) -> None:
        try:
            d = json.loads(line)
        except ValueError:
            return
        if not isinstance(d, dict) or d.get("parent_tool_use_id"):
            return
        kind = d.get("type")
        if kind == "stream_event":
            ev = d.get("event") if isinstance(d.get("event"), dict) else {}
            if ev.get("type") == "message_start":
                self._new(str((ev.get("message") or {}).get("id") or ""))
            elif ev.get("type") == "content_block_delta":
                delta = ev.get("delta") if isinstance(ev.get("delta"), dict) else {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    if self.key is None:
                        self._new("")
                    self.deltas.add(self.key)
                    self.text += str(delta["text"])
                    self._tell()
        elif kind == "assistant":
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            key = str(msg.get("id") or "")
            if key and key in self.deltas:
                return
            text = "".join(
                str(b.get("text") or "")
                for b in msg.get("content") or []
                if isinstance(b, dict) and b.get("type") == "text"
            )
            if not text:
                return
            if not key or key != self.key:
                self._new(key)
                self.text = text
            elif text.startswith(self.text):  # the whole message so far
                self.text = text
            else:  # one block of it
                self.text += "\n" + text
            self._tell()


def stream_run(
    args: list[str],
    *,
    input: str,
    timeout: float,
    cwd: Path | None = None,
    env: dict | None = None,
    on_start=None,
    on_line=None,
) -> proc.Result:
    """proc.run, with stdout read a line at a time as it comes (on_line(line)) instead of all at the end. The same
    process handling: its own session, ended with Kurooto (core/children.py), the whole tree killed at the timeout."""
    import subprocess
    import threading

    args = proc.resolve_cmd_shim(args[0]) + list(args[1:])
    p = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if proc.WINDOWS else 0,
        start_new_session=not proc.WINDOWS,
    )
    if not proc.WINDOWS:
        from kurooto.core import children

        children.session(p.pid)
    if on_start is not None:
        try:
            on_start(p.pid)
        except Exception:
            pass
    err: list[bytes] = []
    reader = threading.Thread(target=lambda: err.append(p.stderr.read() or b""), name="claude-err", daemon=True)
    reader.start()

    def feed() -> None:
        try:
            p.stdin.write(input.encode("utf-8"))
            p.stdin.close()
        except OSError:
            pass

    threading.Thread(target=feed, name="claude-in", daemon=True).start()
    late = threading.Event()

    def kill() -> None:
        late.set()
        proc.kill_tree(p.pid)

    timer = threading.Timer(timeout, kill)
    timer.daemon = True
    timer.start()
    out: list[str] = []
    try:
        for raw in p.stdout:
            line = raw.decode("utf-8", "replace")
            out.append(line)
            if on_line is not None:
                try:
                    on_line(line)
                except Exception:
                    pass
    finally:
        timer.cancel()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill_tree(p.pid)
    reader.join(timeout=10)
    code = None if late.is_set() else p.returncode
    return proc.Result(code, "".join(out), b"".join(err).decode("utf-8", "replace"))


def _bare(line: str) -> str:
    line = line.strip()
    for head in ("User: ", "Assistant: "):
        if line.startswith(head):
            return line[len(head) :].strip()
    return line


class Session:
    """(0.8.17, brain.claude.session) One Claude Code kept running for a conversation: its stream-json input gets one
    message a turn and its output is read as a run of its own is, up to the turn's result line. Its files (settings,
    tools, the first turn's context) live in `tmp` until it closes; the request a turn belongs to is in tmp/job, which
    Kurooto's tools read (core/mcp.py ENV_JOB_FILE), so tool uses count for the right request. One turn at a time
    (`lock`). It ends by its own pid only: stdin closed, then its tree killed if it's still there."""

    def __init__(self, args: list[str], tmp: Path, *, cwd=None, env=None, context: str = "", app=None, idle_s=600):
        import subprocess

        self.tmp, self.app, self.idle_s = tmp, app, idle_s
        self.main = str(app.settings.get("brain.main") or "") if app is not None else ""
        self.p = subprocess.Popen(
            proc.resolve_cmd_shim(args[0]) + list(args[1:]),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if proc.WINDOWS else 0,
            start_new_session=not proc.WINDOWS,
        )
        if not proc.WINDOWS:
            from kurooto.core import children

            children.session(self.p.pid)
        self.lock = threading.Lock()
        self.used = time.monotonic()
        self.turns = 0
        self.known = set(context.splitlines())  # the context lines it was started with, or told since
        self.said: list[str] = []
        self.lines: queue.Queue = queue.Queue()
        self.err: list[str] = []
        threading.Thread(target=self._read, name="claude-session", daemon=True).start()
        threading.Thread(target=self._read_err, name="claude-session-err", daemon=True).start()

    def _read(self) -> None:
        try:
            for raw in self.p.stdout:
                self.lines.put(raw.decode("utf-8", "replace"))
        except (OSError, ValueError):
            pass
        self.lines.put(None)  # it ended

    def _read_err(self) -> None:
        try:
            for raw in self.p.stderr:
                self.err = [*self.err[-50:], raw.decode("utf-8", "replace")]
        except (OSError, ValueError):
            pass

    def alive(self) -> bool:
        return self.p.poll() is None

    def message(self, prompt: str, context: str) -> str:
        """What this turn sends: chat's "Previous conversation" left out when it saw all of it already (it's in its
        own context), and the context's lines it wasn't given yet (the time, what's remembered for this request)."""
        body = prompt
        if self.turns and prompt.startswith(HISTORY) and CURRENT in prompt:
            hist, cur = prompt[len(HISTORY) :].split(CURRENT, 1)
            seen = "\n".join(self.said)
            if all(_bare(x) in seen for x in hist.splitlines() if _bare(x)):
                body = cur
        new = [x for x in context.splitlines() if x.strip() and x not in self.known]
        self.known.update(new)
        if new:
            body = NEWS + "\n" + "\n".join(new) + "\n\n" + body
        return body

    def turn(self, text: str, job: str, timeout: float, on_line=None) -> proc.Result | None:
        """One message, read up to its result line. None when it failed (gone, ended without one, or a new one said
        nothing for FIRST_S): the caller runs the request on its own. Past the timeout it's closed, and the result
        says so (code None)."""
        while not self.lines.empty():  # nothing of an earlier turn is read as this one's
            if self.lines.get_nowait() is None:
                return None
        self.err = []
        try:
            (self.tmp / "job").write_text(job, encoding="utf-8")
            msg = {"type": "user", "session_id": "", "message": {"role": "user", "content": text}}
            self.p.stdin.write((json.dumps({**msg, "parent_tool_use_id": None}) + "\n").encode("utf-8"))
            self.p.stdin.flush()
        except (OSError, ValueError):
            return None
        self.said = [*self.said[-SAID_KEEP:], text]
        end = time.monotonic() + timeout
        quiet = time.monotonic() + FIRST_S if not self.turns else None
        out: list[str] = []
        while True:
            left = end - time.monotonic()
            if quiet is not None and not out and time.monotonic() > quiet:
                return None
            if left <= 0:  # as a run of its own: its whole tree killed at the timeout
                proc.kill_tree(self.p.pid)
                self.close()
                return proc.Result(None, "".join(out), "".join(self.err))
            try:
                line = self.lines.get(timeout=min(left, 1.0))
            except queue.Empty:
                continue
            if line is None:
                return None
            out.append(line)
            if on_line is not None:
                try:
                    on_line(line)
                except Exception:
                    pass
            if '"result"' in line:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("type") == "result":
                    self.said = [*self.said[-SAID_KEEP:], str(d.get("result") or "")]
                    break
        self.turns += 1
        self.used = time.monotonic()
        return proc.Result(0, "".join(out), "".join(self.err))

    def close(self) -> None:
        """Its stdin closed (it ends by itself), and a few seconds later its tree killed by its pid if it's still
        there; its files go."""
        try:
            self.p.stdin.close()
        except (OSError, ValueError):
            pass

        def end() -> None:
            try:
                self.p.wait(timeout=5)
            except Exception:
                proc.kill_tree(self.p.pid)
            shutil.rmtree(self.tmp, ignore_errors=True)

        threading.Thread(target=end, name="claude-session-end", daemon=True).start()

    def stale(self, now: float) -> bool:
        """Idle too long, gone, or its AI or the switch changed meanwhile."""
        if not self.alive() or now - self.used > self.idle_s:
            return True
        if self.app is None:
            return False
        s = self.app.settings
        return not s.get("brain.claude.session", True) or str(s.get("brain.main") or "") != self.main


_SESSIONS: dict[tuple[str, str], Session] = {}  # (conversation, what its command is) -> its program
_POOL = threading.Lock()
_REAPER: list[threading.Thread] = []


def reap(now: float | None = None) -> int:
    """Close the kept programs that are idle too long, gone, or out of date (not one at work). How many closed."""
    now = time.monotonic() if now is None else now
    gone = []
    with _POOL:
        for k, s in list(_SESSIONS.items()):
            if s.stale(now) and s.lock.acquire(blocking=False):
                gone.append(_SESSIONS.pop(k))
    for s in gone:
        s.close()
    return len(gone)


def _reaper() -> None:
    while True:
        time.sleep(REAP_S)
        reap()
        with _POOL:
            if not _SESSIONS:
                _REAPER.clear()
                return


def close_sessions() -> None:
    """Every kept Claude Code closed now (Kurooto is stopping): killed by its pid, its files gone."""
    with _POOL:
        gone = list(_SESSIONS.values())
        _SESSIONS.clear()
    for s in gone:
        try:
            s.p.stdin.close()
        except (OSError, ValueError):
            pass
        proc.kill_tree(s.p.pid)
        shutil.rmtree(s.tmp, ignore_errors=True)


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
        stream = task.on_text is not None  # (voice.speak.stream) the answer as it's written, line by line
        args = [
            *base,
            "-p",
            "--output-format",
            "stream-json" if stream else "json",
            *(["--verbose", "--include-partial-messages"] if stream else []),  # stream-json needs --verbose with -p
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

    def keeps(self) -> bool:
        """(brain.claude.session) Are a conversation's requests sent to a Claude Code kept running for it?"""
        return self.app is None or bool(self.app.settings.get("brain.claude.session", True))

    def _session_run(self, task: Task):
        """(brain.claude.session) The request as a turn of its conversation's kept Claude Code: (result, seconds), or
        None for a run of its own (that one busy, or it failed before answering; a stopped request isn't run again).
        Its command is a run of its own's, made the same way, with its stream-json input; a different command (other
        settings, model, effort or permissions) is another program."""
        from kurooto.core.mcp import ENV_JOB, ENV_JOB_FILE

        tmp = Path(tempfile.mkdtemp(prefix="kurooto-claude-"))
        env = {k: v for k, v in task.mcp_env.items() if k != ENV_JOB}
        env[ENV_JOB_FILE] = str(tmp / "job")
        args = self.args(replace(task, context="", mcp_env=env, on_text=lambda k, t: None), tmp)
        args += ["--input-format", "stream-json"]
        shape = [a.replace(str(tmp), "<tmp>") for a in args]
        for name in ("settings.json", "mcp.json"):
            f = tmp / name
            if f.exists():
                text = f.read_text(encoding="utf-8")
                shape.append(text.replace(json.dumps(str(tmp))[1:-1], "<tmp>"))
        shape += [str(task.cwd), str(self.config_dir)]
        key = (task.session, hashlib.sha256(json.dumps(shape).encode("utf-8")).hexdigest())
        afresh = not task.prompt.startswith(HISTORY)  # chat sent no history: the conversation began again
        own = None
        with _POOL:
            s = _SESSIONS.get(key)
            if s is not None:
                if not s.lock.acquire(blocking=False):  # at work on another request: this one runs on its own
                    shutil.rmtree(tmp, ignore_errors=True)
                    return None
                if not s.alive() or (afresh and s.turns):
                    _SESSIONS.pop(key)
                    own, s = s, None
        if own is not None:
            own.close()
        if s is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            if task.context:
                c = tmp / "context.md"
                c.write_text(task.context, encoding="utf-8")
                args += ["--append-system-prompt-file", str(c)]
            idle = (self.app.settings.get("brain.claude.session_idle_min") if self.app is not None else None) or 0
            try:
                s = Session(
                    args, tmp, cwd=task.cwd, env=self.env(), context=task.context, app=self.app,
                    idle_s=60 * (float(idle) if float(idle) > 0 else IDLE_MIN),
                )  # fmt: skip
            except OSError:
                shutil.rmtree(tmp, ignore_errors=True)
                return None
            s.lock.acquire()
            evict = []
            with _POOL:
                pooled = key not in _SESSIONS
                if pooled:
                    _SESSIONS[key] = s
                    for k, o in sorted(_SESSIONS.items(), key=lambda kv: kv[1].used):
                        if len(_SESSIONS) <= SESSIONS_MAX:
                            break
                        if o is not s and o.lock.acquire(blocking=False):
                            evict.append(_SESSIONS.pop(k))
                    if not _REAPER:
                        _REAPER.append(threading.Thread(target=_reaper, name="claude-sessions", daemon=True))
                        _REAPER[0].start()
            for o in evict:
                o.close()
            if not pooled:  # another request opened one for it meanwhile: this one is for this turn only
                s.idle_s = 0
        try:
            if task.on_process is not None:
                try:
                    task.on_process(s.p.pid)  # cancelling the request stops the program (the next turn opens one)
                except Exception:
                    pass
            text = s.message(task.prompt, task.context)
            egress.handed("Claude Code", "AI requests")
            t0 = time.monotonic()
            r = s.turn(
                text,
                str(task.mcp_env.get(ENV_JOB) or ""),
                task.timeout_s + self.grace_s,
                on_line=Lines(task.on_text).line if task.on_text is not None else None,
            )
            secs = time.monotonic() - t0
        finally:
            s.lock.release()
        if r is None or r.code is None or s.idle_s == 0:  # failed, timed out (closed), or for this turn only
            with _POOL:
                if _SESSIONS.get(key) is s:
                    _SESSIONS.pop(key)
            s.close()
        if r is None:
            if task.stop is not None and task.stop.is_set():
                return proc.Result(-9, "", "stopped"), secs
            return None
        return r, secs

    def run(self, task: Task) -> Result:
        if not self.exe:
            return Result(Verdict.ERROR, detail="Claude Code isn't installed")
        minutes = max(1, task.timeout_s // 60)
        got = None
        if task.session and self.keeps():
            try:
                got = self._session_run(task)
            except Exception:  # a kept program's mistake never costs the request: it runs on its own
                got = None
        if got is not None:
            r, secs = got
            result = self.verdict(r, secs, minutes)
            result.model = result.model or self.models.get(task.effort) or ""
            self.metered(None, result)
            return result
        with tempfile.TemporaryDirectory() as tmp:
            args = self.args(task, Path(tmp))
            egress.handed("Claude Code", "AI requests")  # what it sends to Anthropic, it sends itself
            t0 = time.monotonic()
            if task.on_text is not None:
                r = stream_run(
                    args,
                    input=task.prompt,
                    timeout=task.timeout_s + self.grace_s,
                    cwd=task.cwd,
                    env=self.env(),
                    on_start=task.on_process,
                    on_line=Lines(task.on_text).line,
                )
            else:
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
