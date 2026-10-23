"""What every AI brain offers, whichever service or program is behind it."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Verdict(StrEnum):
    OK = "ok"
    EMPTY = "empty"  # it ran but gave no answer
    DENIED = "denied"  # it tried something unattended runs may not do
    RATE_LIMITED = "rate_limited"  # a usage limit or quota; try later or use the fallback
    AUTH = "auth"  # signed out, or the key is wrong
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"  # you cancelled it (/jobs, the dashboard, `kurooto jobs --cancel`)
    STUCK = "stuck"  # nothing was happening, so the queue's watchdog ended it (core/jobs.py)


EFFORTS = ("low", "medium", "high")
TEXT_ONLY = "Answer with text only. Don't use any tools: don't read, write or run anything."


@dataclass
class Task:
    prompt: str
    effort: str = "medium"
    title: str = ""
    cwd: Path | None = None  # the user's workspace (notes folder)
    timeout_s: int = 900
    context: str = ""  # who the user is, the time, the rules for unattended work
    tools: list = field(default_factory=list)  # Kurooto's tools (core/tools.py), for brains that call them directly
    run_tool: Callable | None = None  # (name, args) -> result
    mcp: list[str] | None = None  # the command that serves the same tools over MCP, for agent programs
    mcp_env: dict = field(default_factory=dict)  # what that command needs to reach the running Kurooto
    text_only: bool = False  # the answer is just text: agent programs are told to use no tools
    on_process: Callable | None = None  # (pid) when an agent program starts: cancelling it stops its process tree
    stop: Any = None  # a threading.Event set when the request is cancelled or stopped: no more steps after it


@dataclass
class Result:
    verdict: Verdict
    text: str = ""
    seconds: float = 0.0
    detail: str = ""  # what went wrong, for the log (never shown raw to the user)
    retry_after_s: int | None = None
    usage: dict = field(default_factory=dict)
    model: str = ""  # the model that answered, as the brain knows it (agy's --model id; Claude Code's own report)

    @property
    def ok(self) -> bool:
        return self.verdict == Verdict.OK


RATE_LIMIT = re.compile(r"RESOURCE_EXHAUSTED|quota exceeded|rate.?limit|429|too many requests|usage limit", re.I)
AUTH_FAIL = re.compile(
    r"\b(401|403)\b|unauthori[sz]ed|invalid api key|not logged in|please (log|sign) ?in|login required"
    r"|authentication required|visit the url to log in",  # the last two: agy when signed out (seen on all OSes)
    re.I,
)


MODEL_DATE = re.compile(r"-\d{8}$")
MODEL_VERSION = re.compile(r"(?<![\d.])(\d+)-(\d{1,2})(?=$|-)")


def short_model(model: str | None, effort: str = "") -> str:
    """A model id short enough for the run receipt: no vendor prefix, release date or "-latest", versions with a dot
    ("claude-opus-4-5-20251101" -> "opus-4.5", "gemini-3.8-flash-medium" -> "3.8-flash-medium"), and no effort suffix
    when the receipt names the effort anyway ("3.8-flash-medium" at medium -> "3.8-flash")."""
    m = re.sub(r"\[[^\]]*\]$", "", str(model or "").strip())  # "opus[1m]"
    m = m.rsplit("/", 1)[-1]  # "models/gemini-..." or a router's "vendor/model"
    m = MODEL_DATE.sub("", m)
    m = re.sub(r"^claude-|^gemini-(?=\d)", "", m)  # "gemini-flash-latest" keeps its name
    m = re.sub(r"-latest$", "", m)
    m = MODEL_VERSION.sub(r"\1.\2", m)
    if effort and m.endswith(f"-{effort}") and len(m) > len(effort) + 1:
        m = m[: -len(effort) - 1]
    return m[:32]


class Brain:
    id = ""
    label = ""
    kind = "api"  # api: quick to call; cli: a program with a slow start, one job at a time
    meter: Callable | None = None  # (model, Result or None for an answer) after each request: core/quota.py counts

    def metered(self, model: str | None, result: Result | None) -> None:
        """Count one request against its free limit (providers.build attaches the meter); never fails a request."""
        if self.meter is not None:
            try:
                self.meter(model, result)
            except Exception:
                pass

    denied_help = (
        ""  # what to tell you when a run stopped at something unattended runs may not do ("" = the usual line)
    )

    def available(self) -> tuple[bool, str]:
        return True, ""

    # What an agent program (kind "cli") does around a run; an API brain has nothing to do here.
    def prepare(self, app) -> None:
        """Before a run: whatever this program needs from Kurooto first (agy: its tools and permissions, asked once)."""

    def worked_file(self, app):
        return app.paths.state / f"{self.id}-worked.json"

    def has_worked(self, app) -> bool:
        """Has it answered on this computer before (a request, or the setup page's test)? Then it may stand in for
        the Gemini key."""
        return self.worked_file(app).exists()

    def mark_worked(self, app) -> None:
        f = self.worked_file(app)
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("{}", encoding="utf-8")
        except OSError:
            pass

    def after_test(self, app) -> str:
        """After the setup page's test passed: set up what it needs and say what it can do (a sentence to add)."""
        return ""

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 60) -> Result:
        """A short answer: classify something, grade a quiz answer, summarise a paragraph."""
        raise NotImplementedError

    def run(self, task: Task) -> Result:
        """A full request: may take minutes, may read your notes."""
        raise NotImplementedError
