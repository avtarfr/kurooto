"""What every AI brain offers, whichever service or program is behind it."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Verdict(StrEnum):
    OK = "ok"
    EMPTY = "empty"  # it ran but gave no answer
    DENIED = "denied"  # it tried something unattended runs may not do
    RATE_LIMITED = "rate_limited"  # a usage limit or quota; try later or use the fallback
    AUTH = "auth"  # signed out, or the key is wrong
    TIMEOUT = "timeout"
    ERROR = "error"


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


@dataclass
class Result:
    verdict: Verdict
    text: str = ""
    seconds: float = 0.0
    detail: str = ""  # what went wrong, for the log (never shown raw to the user)
    retry_after_s: int | None = None
    usage: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.verdict == Verdict.OK


RATE_LIMIT = re.compile(r"RESOURCE_EXHAUSTED|quota exceeded|rate.?limit|429|too many requests|usage limit", re.I)
AUTH_FAIL = re.compile(
    r"\b(401|403)\b|unauthori[sz]ed|invalid api key|not logged in|please (log|sign) ?in|login required"
    r"|authentication required|visit the url to log in",  # the last two: agy when signed out (seen on all OSes)
    re.I,
)


class Brain:
    id = ""
    label = ""
    kind = "api"  # api: quick to call; cli: a program with a slow start, one job at a time

    def available(self) -> tuple[bool, str]:
        return True, ""

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 60) -> Result:
        """A short answer: classify something, grade a quiz answer, summarise a paragraph."""
        raise NotImplementedError

    def run(self, task: Task) -> Result:
        """A full request: may take minutes, may read your notes."""
        raise NotImplementedError
