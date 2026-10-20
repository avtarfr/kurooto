"""The AI job queue: requests that may take minutes run in the background and the answer comes back to you.

CLI brains (agy) run one job at a time; API brains may run a few at once. If the main brain can't do a request
(rate-limited, signed out, refused, failed, or no answer) and a fallback brain is set, the job is retried on the
fallback. As a last resort, an agent program (agy, Codex, Claude Code) hands over to your Gemini key when one is
saved, and the Gemini key hands over to agy when agy has worked here before; the answer then says so in one line.

Free limits (core/quota.py): background work skips a limit that's kept for you (past quota.background_pct of the day,
or used up) and waits in the queue for its reset (not_before) instead of being dropped; your own requests try a
used-up limit last, and a used-up limit is told in one plain line.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from kurooto import providers
from kurooto.core.mcp import command, run_env
from kurooto.core.state import owner_only
from kurooto.core.tools import agent_tools, run_tool
from kurooto.providers import effort as effort_mod
from kurooto.providers.base import Result, Task, Verdict
from kurooto.providers.context import headless_context

if TYPE_CHECKING:
    from kurooto.app import App

SCHEMA = """
create table if not exists jobs (
    id text primary key, title text, prompt text, effort_req text, effort text, status text, verdict text,
    brain text, reply_to text, quiet integer, created real, started real, finished real, seconds real,
    result text, detail text, then_action text, then_payload text
);
create index if not exists jobs_status on jobs(status, created);
create table if not exists attempts (job text, brain text, verdict text, at real, seconds real, tool_calls integer);
create index if not exists attempts_at on attempts(at);
"""
LONG = 7000  # longer answers are also sent as a document
RETRY = (Verdict.RATE_LIMITED, Verdict.AUTH, Verdict.ERROR, Verdict.DENIED, Verdict.EMPTY)  # the next brain tries
GEMINI_KEY = "gemini.api_key"  # also what calls and voice notes use
DENIED_HELP = (
    "agy refused to run this without you watching. Add a free Gemini key in Settings → AI "
    "(aistudio.google.com/apikey), then try again."
)
SHORT = {"agy": "agy", "gemini": "your Gemini key", "codex": "Codex", "claude": "Claude Code"}

FRIENDLY = {
    Verdict.DENIED: "The AI stopped without an answer: it tried something unattended runs aren't allowed to do. "
    "Rephrase it, or do that part yourself.",
    Verdict.EMPTY: "The AI gave no answer this time. Try rephrasing.",
    Verdict.TIMEOUT: "No answer in time; the request was stopped.",
    Verdict.AUTH: "{brain} isn't signed in any more (or its key stopped working). Open the setup page "
    "(kurooto open) → AI → Sign in again.",
    Verdict.RATE_LIMITED: "{brain} has hit its usage limit for now.",
    Verdict.ERROR: "Something went wrong talking to {brain}.",
}


@dataclass
class Job:
    id: str
    title: str
    prompt: str
    effort_req: str
    effort: str | None
    status: str  # queued | running | ok | failed
    verdict: str | None
    brain: str | None
    reply_to: str | None
    quiet: bool
    created: float
    seconds: float | None
    result: str | None


def _process(pid: int) -> str:
    """A process's pid and start time: a pid alone can belong to another program after a reboot."""
    return f"{pid}:{psutil.Process(pid).create_time():.2f}"


RUNNER = _process(os.getpid())


def _alive(runner: str | None) -> bool:
    try:
        pid = int(str(runner).split(":")[0])
        return _process(pid) == runner
    except (psutil.Error, ValueError):
        return False


class Jobs:
    def __init__(self, app: App):
        self.app = app
        self.dir = app.paths.state / "jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(app.paths.state / "jobs.db", check_same_thread=False, isolation_level=None)
        owner_only(app.paths.state / "jobs.db")
        self._db.execute("pragma journal_mode=wal")
        had_attempts = self._db.execute("select 1 from sqlite_master where name='attempts'").fetchone()
        self._db.executescript(SCHEMA)
        if not had_attempts:  # /usage counts every try at a brain; older databases start from their jobs
            self._db.execute(
                "insert into attempts(job, brain, verdict, at, seconds, tool_calls) select id, brain, verdict, "
                "coalesce(finished, created), seconds, 0 from jobs where brain is not null and verdict is not null"
            )
        self._lock = threading.Lock()
        self._cli_lock = threading.Lock()  # CLI brains: one job at a time
        self._wake: asyncio.Event | None = None
        self._loop = None
        self.then_actions: dict = {}  # name -> fn(job, result)
        if "background" not in [r[1] for r in self._db.execute("pragma table_info(jobs)")]:  # older databases
            self._db.execute("alter table jobs add column background integer default 0")
        if "runner" not in [r[1] for r in self._db.execute("pragma table_info(jobs)")]:  # which process runs it
            self._db.execute("alter table jobs add column runner text")
        if "text_only" not in [r[1] for r in self._db.execute("pragma table_info(jobs)")]:
            self._db.execute("alter table jobs add column text_only integer default 0")
        if "not_before" not in [r[1] for r in self._db.execute("pragma table_info(jobs)")]:  # waits for a reset
            self._db.execute("alter table jobs add column not_before real")
        if "why" not in [r[1] for r in self._db.execute("pragma table_info(jobs)")]:  # (calm) the answer's reason
            self._db.execute("alter table jobs add column why text")

    # ------------------------------------------------------------------------------------- the queue
    def submit(
        self,
        prompt: str,
        title: str | None = None,
        effort: str = "auto",
        reply_to=None,
        quiet: bool = False,
        then: str | None = None,
        then_payload: dict | None = None,
        background: bool = False,
        text_only: bool = False,
        why: str | None = None,
    ) -> str:
        """Queue an AI request. background=True: work nobody is waiting for, which waits for the charger when the
        laptop is on battery. text_only=True: the answer is just text (agent programs are told to use no tools).
        why: the answer's reason when it comes by itself (core/calm.py, e.g. "research.papers"); otherwise it's an
        answer to something asked, never held."""
        forced, prompt_clean = effort_mod.strip_forced(prompt)
        jid = "j" + uuid.uuid4().hex[:8]
        with self._lock:
            self._db.execute(
                "insert into jobs(id,title,prompt,effort_req,status,reply_to,quiet,created,then_action,then_payload,"
                "background,text_only,why) values(?,?,?,?, 'queued',?,?,?,?,?,?,?,?)",
                (
                    jid,
                    (title or prompt_clean.split("\n")[0])[:80],
                    prompt_clean,
                    forced or effort,
                    None if reply_to is None else str(reply_to),
                    int(quiet),
                    time.time(),
                    then,
                    json.dumps(then_payload or {}),
                    int(background),
                    int(text_only),
                    why,
                ),
            )
        self.app.events.emit("job_queued", job=jid, chars=len(prompt_clean))
        if self._wake is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._wake.set)
        return jid

    def recover(self) -> int:
        """Jobs cut off by a crash or a restart run again. Only the daemon's worker does this, and only for jobs whose
        process is gone: anything else that opens the queue (`kurooto doctor`, the CLI) leaves running jobs alone."""
        with self._lock:
            rows = self._db.execute("select id, runner from jobs where status='running'").fetchall()
            gone = [jid for jid, runner in rows if not _alive(runner)]
            for jid in gone:
                self._db.execute("update jobs set status='queued' where id=? and status='running'", (jid,))
        return len(gone)

    def poke(self) -> None:
        """Look at the queue now (e.g. a pause just ended)."""
        if self._wake is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    def _read(self, sql: str, args: tuple = (), one: bool = True):
        """A read under the queue's lock: the web page, the worker and tests share one connection, and two threads
        stepping the same cached statement at once can lose a row (seen on Windows)."""
        with self._lock:
            cur = self._db.execute(sql, args)
            return cur.fetchone() if one else cur.fetchall()

    def get(self, jid: str) -> Job | None:
        row = self._read(f"select {self._cols} from jobs where id=?", (jid,))
        return Job(*row[:9], bool(row[9]), *row[10:]) if row else None

    def recent(self, n: int = 10) -> list[Job]:
        rows = self._read(f"select {self._cols} from jobs order by created desc limit ?", (n,), one=False)
        return [Job(*r[:9], bool(r[9]), *r[10:]) for r in rows]

    _cols = "id,title,prompt,effort_req,effort,status,verdict,brain,reply_to,quiet,created,seconds,result"

    # queued, allowed on this power, and not waiting for a free limit's reset (core/quota.py)
    _READY = "status='queued' and (background=0 or ?) and coalesce(not_before, 0) <= ?"

    def _ready_args(self) -> tuple:
        q = self.app.quota  # with the reserve turned off (quota.on = false), work that waited goes at once
        return int(self.app.power.current == "normal"), q.clock() if q.on() else 1e18

    def _claim(self) -> str | None:
        with self._lock:
            row = self._db.execute(
                f"select id from jobs where {self._READY} order by created limit 1", self._ready_args()
            ).fetchone()
            if not row:
                return None
            self._db.execute(
                "update jobs set status='running', started=?, runner=? where id=?", (time.time(), RUNNER, row[0])
            )
            return row[0]

    def run_next(self) -> str | None:
        """Run the oldest queued job to completion. Returns its id, or None if the queue is empty."""
        jid = self._claim()
        if jid:
            self._run(jid)
        return jid

    async def worker(self, stop: asyncio.Event) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self.recover()
        while not stop.is_set():
            if self.app.power.current != "paused" and self._read(
                f"select 1 from jobs where {self._READY} limit 1", self._ready_args()
            ):
                await asyncio.to_thread(self.run_next)
                continue
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=5)
            except TimeoutError:
                pass

    # ------------------------------------------------------------------------------------- running
    def _classifier(self, main):
        how = self.app.settings.get("brain.classify") or "rules"
        if how == "rules" or main is None:
            return None
        brain = main if how == "main" else providers.build(self.app, how)
        quota = self.app.quota
        if brain is not None and quota.wait_until(quota.pool(brain, "low")) is not None:  # its limit is kept for you
            brain = providers.local(self.app) if quota.setting("local") != "off" else None  # else the rules
        if brain is None or not brain.available()[0]:
            return None
        return lambda q: brain.complete(q, effort="low", timeout=30).text

    def _run(self, jid: str) -> None:
        job = self.get(jid)
        s = self.app.settings
        main = providers.build(self.app, s.get("brain.main") or "")
        fallback = providers.build(self.app, s.get("brain.fallback") or "")
        level = (
            job.effort_req
            if job.effort_req in ("low", "medium", "high")
            else effort_mod.pick(job.prompt, self._classifier(main))
        )
        minutes = (s.get("brain.timeout_min") or {}).get(level, 15)
        tools = agent_tools(self.app)
        text_only = bool(self._read("select text_only from jobs where id=?", (jid,))[0])
        task = Task(
            prompt=job.prompt,
            effort=level,
            title=job.title,
            cwd=self.app.workspace,
            timeout_s=minutes * 60,
            context=headless_context(self.app),
            tools=[] if text_only else tools,  # text-only work gets no tools (and agent programs no MCP)
            run_tool=lambda name, args: run_tool(self.app, name, args, tools),
            mcp=None if text_only else mcp_command(),
            mcp_env=run_env(self.app.paths),
            text_only=text_only,
        )
        chain = [b for b in (main, fallback) if b is not None]
        last = self._last_resort(main)
        if last is not None and last.id not in {b.id for b in chain}:
            chain.append(last)
        background = bool(self._read("select background from jobs where id=?", (jid,))[0])
        chain, wait = self.app.quota.arrange(chain, level, background)  # free limits kept for you (core/quota.py)
        if wait is not None and not chain:
            self._defer(jid, wait)
            return
        used, result, first = None, Result(Verdict.ERROR, detail="no AI brain is set up"), None
        for i, brain in enumerate(chain):
            ok, why = brain.available()
            if not ok:
                result, used = Result(Verdict.ERROR, detail=why), brain
                first = first or (brain, result)
                continue
            used = brain
            if brain.id == "agy":
                from kurooto.providers.agy import tools_once

                tools_once(self.app, brain)
            if brain.kind == "cli":
                with self._cli_lock:
                    result = brain.run(task)
            else:
                result = brain.run(task)
            self._attempt(jid, brain.id, result)
            if brain.id == "agy" and result.ok:
                from kurooto.providers.agy import mark_worked

                mark_worked(self.app.paths.state)
            if result.verdict not in RETRY:
                break
            first = first or (brain, result)
            self._problem(brain, result, chain[i + 1] if i + 1 < len(chain) else None, level)
        if wait is not None and not result.ok:  # moved to the model here, which couldn't: it waits for the reset
            self._defer(jid, wait)
            return
        if last is not None and used is last and result.ok and first:
            note = f"(Answered with {SHORT.get(last.id, last.label)}: {_why(*first)}.)"
            result.usage = {**result.usage, "note": note}
        if result.verdict == Verdict.DENIED and used.id == "agy" and not self.app.secrets.get(GEMINI_KEY):
            result.detail = DENIED_HELP
        ok = result.ok
        with self._lock:
            self._db.execute(
                "update jobs set status=?, verdict=?, brain=?, effort=?, finished=?, seconds=?, result=?, detail=? "
                "where id=?",
                (
                    "ok" if ok else "failed",
                    result.verdict.value,
                    used.id if used else None,
                    level,
                    time.time(),
                    round(result.seconds, 1),
                    result.text,
                    result.detail[:2000],
                    jid,
                ),
            )
        self.app.events.emit(
            "job_done",
            job=jid,
            ok=ok,
            verdict=result.verdict.value,
            effort=level,
            brain=used.id if used else None,
            seconds=round(result.seconds),
        )
        job = self.get(jid)
        if not job.quiet:
            self._deliver(job, result, used)
        then = self._read("select then_action, then_payload from jobs where id=?", (jid,))
        if then and then[0] and then[0] in self.then_actions:
            try:
                self.then_actions[then[0]](job, result, json.loads(then[1] or "{}"))
            except Exception as e:
                self.app.events.emit("job_then_failed", job=jid, error=str(e)[:300])

    def _attempt(self, jid: str, brain: str, result: Result) -> None:
        tools = result.usage.get("tool_calls") if isinstance(result.usage, dict) else 0
        with self._lock:
            self._db.execute(
                "insert into attempts(job, brain, verdict, at, seconds, tool_calls) values(?,?,?,?,?,?)",
                (jid, brain, result.verdict.value, time.time(), round(result.seconds, 1), int(tools or 0)),
            )

    def usage(self, days: int = 7) -> list[dict]:
        """AI requests per day (local time) per brain over the last `days` days, with usage-limit hits."""
        start = datetime.datetime.combine(
            datetime.date.today() - datetime.timedelta(days=days - 1), datetime.time()
        ).timestamp()
        rows = self._read(
            "select date(at, 'unixepoch', 'localtime'), brain, count(*), sum(verdict = 'rate_limited'), "
            "sum(coalesce(tool_calls, 0)) from attempts where at >= ? group by 1, 2 order by 1, 2",
            (start,),
            one=False,
        )
        return [
            {"day": d, "brain": b, "requests": n, "limited": lim or 0, "tool_calls": tc or 0}
            for d, b, n, lim, tc in rows
        ]

    def _last_resort(self, main):
        """When the main AI can't do a request: an agent program (agy, Codex, Claude Code) hands over to your Gemini
        key if one is saved; the Gemini key hands over to agy if agy is installed and has worked here before."""
        if main is None:
            return None
        if main.kind == "cli" and self.app.secrets.get(GEMINI_KEY):
            return providers.build(self.app, "gemini")
        if main.id == "gemini":
            from kurooto.providers.agy import has_worked

            agy = providers.build(self.app, "agy")
            if agy is not None and agy.available()[0] and has_worked(self.app.paths.state):
                return agy
        return None

    def _problem(self, brain, result: Result, nxt=None, level: str = "medium") -> None:
        """Tell the user about a usage limit or a sign-out, at most once an hour per brain."""
        if result.verdict not in (Verdict.RATE_LIMITED, Verdict.AUTH):
            return
        flag = self.dir / f"told-{brain.id}-{result.verdict.value}"
        if flag.exists() and time.time() - flag.stat().st_mtime < 3600:
            return
        flag.touch()
        text = FRIENDLY[result.verdict].format(brain=brain.label)
        pool = self.app.quota.pool(brain, level)
        if result.verdict == Verdict.RATE_LIMITED and self.app.quota.used_up(pool):  # the day's limit: one plain line
            text = self.app.quota.line(pool, brain.label) + (
                f" Requests go to the fallback ({nxt.label}) meanwhile." if nxt is not None else ""
            )
        elif result.verdict == Verdict.RATE_LIMITED:
            text += (
                f" Requests go to the fallback ({nxt.label}) meanwhile."
                if nxt is not None
                else (" Requests will fail until it resets. You can set a fallback brain in Settings.")
            )
        self.app.notify(
            text,
            title=f"{brain.label}: action needed" if result.verdict == Verdict.AUTH else None,
            kind="info",
            urgent=True,
            why="ai.limit",
        )

    def _deliver(self, job: Job, result: Result, used) -> None:
        label = used.label if used else "AI"
        why = (self._read("select why from jobs where id=?", (job.id,)) or [None])[0] or "asked"  # core/calm.py
        pool = self.app.quota.pool(used, job.effort or "medium")
        head = f"[{label} · {job.effort or '?'}{'' if result.ok else ' · failed'}] {job.title}"
        if result.ok:
            note = (result.usage or {}).get("note")
            body = f"{result.text}\n\n{note}" if note else result.text
        elif result.detail == DENIED_HELP:
            body = DENIED_HELP
        elif result.verdict == Verdict.RATE_LIMITED and self.app.quota.used_up(pool):
            body = self.app.quota.line(pool, label)  # "Google's free limit for today is used up, resets at 12:30; ..."
        else:
            body = FRIENDLY.get(result.verdict, "It failed.").format(brain=label)
        reply_to = int(job.reply_to) if job.reply_to and job.reply_to.isdigit() else job.reply_to
        cases = self.app.modules.get("cases") if self.app.is_on("cases") else None  # (wrong) a Wrong button on it
        buttons = cases.answer_buttons(job.id) if cases is not None else None
        if len(body) > LONG:
            md = self.dir / f"{job.id}-result.md"
            md.write_text(body, encoding="utf-8")
            self.app.notify(
                f"{head}\n\n{body[:1500]}\n\n[…the full answer is attached]",
                kind="result",
                reply_to=reply_to,
                buttons=buttons,
                why=why,
            )
            self.app.notify(job.title, kind="result", file=str(md), why=why)
        else:
            self.app.notify(f"{head}\n\n{body}", kind="result", reply_to=reply_to, buttons=buttons, why=why)

    def _defer(self, jid: str, until: float) -> None:
        """Background work whose free limits are kept for you: back in the queue until the reset, never dropped."""
        until = max(float(until), self.app.quota.clock() + 60)
        with self._lock:
            self._db.execute(
                "update jobs set status='queued', not_before=?, runner=null, started=null where id=?", (until, jid)
            )
        self.app.events.emit("job_deferred", job=jid, until=datetime.datetime.fromtimestamp(until).isoformat())

    def resume(self) -> int:
        """A free limit answers again before its reset: waiting work gets another look now (core/quota.py)."""
        with self._lock:
            n = self._db.execute(
                "update jobs set not_before=null where status='queued' and not_before is not null"
            ).rowcount
        if n:
            self.poke()
        return n

    def waiting(self) -> int:
        """Background requests waiting for a free limit's reset."""
        row = self._read(
            "select count(*) from jobs where status='queued' and not_before > ?", (self.app.quota.clock(),)
        )
        return int(row[0]) if row else 0

    def close(self) -> None:
        self._db.close()


def mcp_command() -> list[str]:
    """How an agent program starts Kurooto's tool server (`kurooto mcp`), with this version's own Python."""
    return command()


def _why(brain, result: Result) -> str:
    """Why the main AI didn't answer, for the line under an answer from the last-resort one."""
    who = SHORT.get(brain.id, brain.label)
    return {
        Verdict.DENIED: f"{who} couldn't do this unattended",
        Verdict.RATE_LIMITED: f"{who} hit its limit",
        Verdict.AUTH: f"{who} isn't signed in" if brain.kind == "cli" else f"{who} stopped working",
        Verdict.EMPTY: f"{who} gave no answer",
    }.get(result.verdict, f"{who} failed")


def result_path(app: App, jid: str) -> Path:
    return app.paths.state / "jobs" / f"{jid}-result.md"
