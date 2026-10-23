"""The AI job queue: requests that may take minutes run in the background and the answer comes back to you.

CLI brains (agy, Claude Code) run one job at a time; API brains may run a few at once. If the main brain can't do a
request (rate-limited, signed out, refused, failed, or no answer) and a fallback brain is set, the job is retried on
the fallback. As a last resort the Gemini key hands over to an agent program that has worked here before; an agent
program doesn't roll over to the Gemini key (its free limit is small). The answer then says so in one line.

Free limits (core/quota.py): background work skips a limit that's kept for you (past quota.background_pct of the day,
or used up) and waits in the queue for its reset (not_before) instead of being dropped; your own requests try a
used-up limit last, and a used-up limit is told in one plain line.

No internet (core/helper.py): a request that needs it waits in the queue (held_until) instead of failing, you're told
once, and it runs when the connection is back, its answer saying it waited; one that waited local_helper.hold_h ends
with a message. A request that failed because the connection went during it waits the same way.

Three lanes, each running one request at a time: yours ("you": what you asked on Telegram, a call, the terminal or
the dashboard), work nobody is waiting for ("bg": background=True, automatic revision packs, routines, the morning
plan), and a second lane of that work ("chk": the concept graph's second looks and linking, so its checking AI runs
beside the first). Your request never waits behind a background one.

A watchdog ends a request that is stuck: no AI at work on it and no program running for jobs.stuck_min minutes
(10), or still going past its time limit plus a grace. It ends as failed with a plain message. You can cancel what's
running or waiting (/jobs, the dashboard's AI jobs page, `kurooto jobs --cancel ID`); a running agent program is
stopped with everything it started.

The plan line (jobs.plan_line, 0.5.22): when one of your text requests is likely to take more than PLAN_S seconds
(the median of your last requests on that AI and effort, from at least 3), one short line comes first ("Searching your
notes, then answering (about 40 s with agy)."), from what's known before it runs: a file you sent, a link, remembered
items, words about your notes. Never on a call (calls' requests are quiet, and none while you're on one), never for
background work.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from kurooto import providers
from kurooto.core import proc
from kurooto.core.config import register_defaults
from kurooto.core.mcp import ENV_JOB, command, run_env
from kurooto.core.state import owner_only
from kurooto.core.tools import agent_tools, run_tool
from kurooto.providers import effort as effort_mod
from kurooto.providers.agy import Agy
from kurooto.providers.base import Result, Task, Verdict, short_model
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
register_defaults(
    "jobs",
    {
        "stuck_min": 10,  # the watchdog: minutes with no AI at work and no program running
        "receipt": True,  # a quiet last line under each answer: which AI, effort, time, limit used, what it did
        "plan_line": True,  # a short "Searching your notes, then answering" first, when a text answer will take 20 s+
    },
)

LONG = 7000  # longer answers are also sent as a document
PLAN_S = 20  # a request expected to take longer than this gets the plan line first
PLAN_SAMPLES = 3  # past requests on that AI and effort needed before guessing
NOTES_CUE = re.compile(r"(?i)\b(?:my|the|in|from|of)\s+(?:own\s+)?notes?\b|\bnotes?\s+(?:on|about)\b|\bvault\b")
URL = re.compile(r"https?://\S+")
LANES = ("you", "bg", "chk")  # your own requests; work nobody is waiting for; a second kind of that work, so two
# AI programs (agy and Claude Code) can each have a job running at once
GRACE_S = 120  # the watchdog's grace past a try's time limit (and the brain's own grace)
ACTIVE = ("queued", "running")
RETRY = (Verdict.RATE_LIMITED, Verdict.AUTH, Verdict.ERROR, Verdict.DENIED, Verdict.EMPTY)  # the next brain tries
GEMINI_KEY = "gemini.api_key"  # also what calls and voice notes use
MAX_STEPS = 200  # tool uses kept per running request (its tool log)
DENIED_HELP = Agy.denied_help  # what an AI that was refused says (providers/agy.py); a brain's own is `denied_help`
SHORT = {"agy": "agy", "gemini": "your Gemini key", "claude": "Claude Code"}
NAMES = {**SHORT, "gemini": "Gemini", "ollama": "Ollama", "custom": "your AI service", "freellmapi": "your AI service"}
GAVE_UP = "It waited for the internet connection"  # the start of the message when a request waited too long
RECEIPT_MAX = 160  # the run receipt is one line, at most this long (who decided and answered, with models)
# the run receipt's "what it did", from its tool log: a tool -> (what it did, the thing it counts; "" = said once)
ACTS = {
    "search_notes": ("searched notes", ""),
    "list_notes": ("searched notes", ""),
    "note_timeline": ("searched notes", ""),
    "search_history": ("searched past answers", ""),
    "read_note": ("read", "note"),
    "write_note": ("wrote", "note"),
    "add_to_note": ("added to", "note"),
    "edit_note": ("edited", "note"),
    "tick_task": ("ticked", "task"),
    "list_files": ("looked through files", ""),
    "read_file": ("read", "file"),
    "read_course_file": ("read", "file"),
    "read_book": ("read books", ""),
    "fetch_url": ("read", "web page"),
    "add_reminder": ("set", "reminder"),
    "set_alarm": ("set", "alarm"),
    "add_deadline": ("added", "deadline"),
    "move_deadline": ("moved", "deadline"),
    "mark_deadline_done": ("ticked off", "deadline"),
    "remove_deadline": ("removed", "deadline"),
    "schedule_call": ("set up", "call"),
    "call_now": ("rang", "call"),
    "remember": ("remembered", "preference"),
    "send_message": ("sent", "message"),
    "send_file": ("sent", "file"),
    "send_files": ("sent", "file"),
    "ask_user": ("asked", "question"),
    "draft_reply": ("drafted", "reply"),
}

FRIENDLY = {
    Verdict.DENIED: "The AI stopped without an answer: it tried something unattended runs aren't allowed to do. "
    "Rephrase it, or do that part yourself.",
    Verdict.EMPTY: "The AI gave no answer this time. Try rephrasing.",
    Verdict.TIMEOUT: "No answer in time; the request was stopped.",
    Verdict.AUTH: "{brain} isn't signed in any more (or its key stopped working). Open the setup page "
    "(kurooto open) → AI → Sign in again.",
    Verdict.RATE_LIMITED: "{brain} has hit its usage limit for now.",
    Verdict.ERROR: "Something went wrong talking to {brain}.",
    Verdict.CANCELLED: "Cancelled.",
    Verdict.STUCK: "It got stuck (nothing was happening), so I stopped it. Send it again to try once more.",
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
    started: float | None = None
    lane: str = "you"
    not_before: float | None = None
    background: bool = False
    model: str | None = None  # the model that answered (agy's --model, Claude Code's own report)
    receipt: str | None = None  # the run receipt


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
        self._wake: asyncio.Event | None = None
        self._loop = None
        self.then_actions: dict = {}  # name -> fn(job, result)
        # fn(job, result, info) after every finished request, its then-action included; info: "steps" (its tool log:
        # [{"name", "args"}]), "then", "payload". Learns from its own work (modules/learning.py) watches here
        self.watchers: list = []
        self.steps: dict[str, list[dict]] = {}  # a running request's tool log (note_step), dropped when it ends
        self.recalled: dict[str, int] = {}  # a running request's remembered items (core/assembler.py), for its receipt
        self.decided: dict[str, dict] = {}  # a running request's quick decision (its effort): who made it, its model
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
        have = [r[1] for r in self._db.execute("pragma table_info(jobs)")]
        for col, kind in (
            ("lane", "text default 'you'"),
            ("proc", "text"),
            ("activity", "real"),
            ("deadline", "real"),
            ("brain_req", "text"),
            ("receipt", "text"),
            ("effort_from", "text"),
            ("corrected", "text"),
            ("held", "real"),
            ("held_until", "real"),
            ("model", "text"),
        ):
            if col not in have:  # the lane; the agent program running it; the last sign of life; a try's deadline;
                # the AI it was pinned to; the run receipt; what picked its effort and your words when you said its
                # answer missed (both for Dream RSI part three, core/tuning.py); when it first waited for the
                # internet, and until when (core/helper.py); the model that answered
                self._db.execute(f"alter table jobs add column {col} {kind}")
        self._stops: dict[str, threading.Event] = {}  # job -> set when it's cancelled or ended by the watchdog
        self._lanes: dict[str, tuple[str, threading.Thread]] = {}  # lane -> (job, the thread running it)

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
        lane: str | None = None,
        brain: str | None = None,
        offline: bool = False,
    ) -> str:
        """Queue an AI request. background=True: work nobody is waiting for, which waits for the charger when the
        laptop is on battery. text_only=True: the answer is just text (agent programs are told to use no tools).
        why: the answer's reason when it comes by itself (core/calm.py, e.g. "research.papers"); otherwise it's an
        answer to something asked, never held.
        lane: "you" (your own request) or "bg" / "chk" (automatic work); unset, background work goes in "bg".
        brain: run it on this AI (agy, claude, gemini, ...) instead of the main one; another AI program takes over if
        it can't.
        offline: the internet is down and the caller told you it waits (modules/chat.py): it waits from now."""
        forced, prompt_clean = effort_mod.strip_forced(prompt)
        jid = "j" + uuid.uuid4().hex[:8]
        lane = lane if lane in LANES else ("bg" if background else "you")
        with self._lock:
            self._db.execute(
                "insert into jobs(id,title,prompt,effort_req,status,reply_to,quiet,created,then_action,then_payload,"
                "background,text_only,why,lane,brain_req,held,held_until) "
                "values(?,?,?,?, 'queued',?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    lane,
                    brain,
                    time.time() if offline else None,
                    time.time() + 120 if offline else None,  # core/helper.py:RETRY_S
                ),
            )
        self.app.events.emit("job_queued", job=jid, chars=len(prompt_clean), lane=lane)
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
                self._db.execute(
                    "update jobs set status='queued', proc=null, deadline=null where id=? and status='running'", (jid,)
                )
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

    @staticmethod
    def _job(r) -> Job:
        return Job(*r[:9], bool(r[9]), *r[10:14], r[14] or "you", r[15], bool(r[16]), r[17], r[18])

    def get(self, jid: str) -> Job | None:
        row = self._read(f"select {self._cols} from jobs where id=?", (jid,))
        return self._job(row) if row else None

    def recent(self, n: int = 10) -> list[Job]:
        rows = self._read(f"select {self._cols} from jobs order by created desc limit ?", (n,), one=False)
        return [self._job(r) for r in rows]

    def finished_since(self, t: float, limit: int = 500) -> list[tuple]:
        """Requests that ended well after time t, oldest first, for the search index (modules/learning.py):
        (id, title, prompt, result, finished, lane, then_action)."""
        return self._read(
            "select id, title, prompt, result, finished, coalesce(lane, 'you'), coalesce(then_action, '') from jobs "
            "where status='ok' and finished > ? and prompt != '' order by finished limit ?",  # not forgotten ones
            (t, limit),
            one=False,
        )

    def ending(self, lo: float, hi: float) -> list[tuple]:
        """(gists) Your own requests forget() would blank in [lo, hi), before it does, oldest first: (title, status,
        verdict, receipt, when). core/gists.py."""
        return self._read(
            "select title, status, coalesce(verdict, ''), coalesce(receipt, ''), coalesce(finished, created) from jobs "
            "where status not in ('queued','running') and prompt != '' and coalesce(lane, 'you') = 'you' "
            "and coalesce(finished, created) >= ? and coalesce(finished, created) < ? order by 5",
            (lo, hi),
            one=False,
        )

    def forget(self, lo: float, hi: float) -> int:
        """(retention) Blank what was asked and answered in finished requests that ended in [lo, hi): the row stays,
        without its words, for /usage and the Space keeper. How many were forgotten (core/retention.py)."""
        with self._lock:
            n = self._db.execute(
                "update jobs set title='(forgotten)', prompt='', result=null, detail=null, then_payload=null, "
                "corrected=case when coalesce(corrected,'')='' then corrected else '-' end "
                "where status not in ('queued','running') and prompt != '' and coalesce(finished, created) >= ? "
                "and coalesce(finished, created) < ?",
                (lo, hi),
            ).rowcount
            if n:  # the old words don't linger in the write-ahead log
                self._db.execute("pragma wal_checkpoint(truncate)")
        return n

    def active(self) -> list[Job]:
        """What's running, then what's waiting, oldest first."""
        rows = self._read(
            f"select {self._cols} from jobs where status in ('running','queued') order by status='queued', created",
            one=False,
        )
        return [self._job(r) for r in rows]

    _cols = (
        "id,title,prompt,effort_req,effort,status,verdict,brain,reply_to,quiet,created,seconds,result,started,lane,"
        "not_before,background,model,receipt"
    )

    # queued, allowed on this power, not waiting for a free limit's reset (core/quota.py) nor for the internet
    _READY = "status='queued' and (background=0 or ?) and coalesce(not_before, 0) <= ? and coalesce(held_until, 0) <= ?"

    def _ready_args(self) -> tuple:
        q = self.app.quota  # with the reserve turned off (quota.on = false), work that waited goes at once
        return int(self.app.power.current == "normal"), q.clock() if q.on() else 1e18, time.time()

    def _claim(self, lane: str | None = None) -> str | None:
        """Mark the oldest ready job (of one lane, or of any) as running; its id, or None."""
        with self._lock:
            which = " and coalesce(lane, 'you')=?" if lane else ""
            row = self._db.execute(
                f"select id from jobs where {self._READY}{which} order by created limit 1",
                (*self._ready_args(), *((lane,) if lane else ())),
            ).fetchone()
            if not row:
                return None
            t = time.time()
            self._db.execute(
                "update jobs set status='running', started=?, runner=?, activity=?, proc=null, deadline=null "
                "where id=?",
                (t, RUNNER, t, row[0]),
            )
            self._stops[row[0]] = threading.Event()
            return row[0]

    def run_next(self, lane: str | None = None) -> str | None:
        """Run the oldest queued job (of a lane, or of any) to completion here. Its id, or None if none is ready."""
        jid = self._claim(lane)
        if jid:
            self._run_safe(jid)
        return jid

    def _busy(self, lane: str) -> bool:
        """Is a job of this lane running? One ended by a cancel or the watchdog doesn't count, even while its thread
        is still finishing (stuck in a request): the lane goes on without it."""
        cur = self._lanes.get(lane)
        if cur is None or not cur[1].is_alive():
            return False
        row = self._read("select status from jobs where id=?", (cur[0],))
        return bool(row and row[0] == "running")

    def _start(self, lane: str, jid: str) -> None:
        t = threading.Thread(target=self._run_safe, args=(jid,), name=f"job-{lane}", daemon=True)
        self._lanes[lane] = (jid, t)
        t.start()

    def _tick(self) -> None:
        """One look at the queue: the watchdog, then a job for each lane that's free."""
        self.watchdog()
        if self.app.power.current == "paused":
            return
        for lane in LANES:
            if not self._busy(lane):
                jid = self._claim(lane)
                if jid:
                    self._start(lane, jid)

    async def worker(self, stop: asyncio.Event) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self.recover()
        while not stop.is_set():
            self._wake.clear()
            try:
                await asyncio.to_thread(self._tick)
            except Exception as e:  # the queue never stops over one mistake
                self.app.events.emit("jobs_failed", error=f"{type(e).__name__}: {e}"[:300])
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=5)
            except TimeoutError:
                pass

    # ------------------------------------------------------------------------------------- running
    def _classifier(self, main, jid: str | None = None):
        """Who answers "how hard is this": brain.classify's choice; the offline helper (core/helper.py) where the
        rules would otherwise decide alone (rules, its limit kept for you or reached, the internet down); else the
        rules (None). The run receipt names the model that decided (self.decided)."""
        helper = getattr(self.app, "helper", None)
        quick = self._helper_classifier(helper, jid)
        how = self.app.settings.get("brain.classify") or "rules"
        if how == "rules" or main is None or (helper is not None and helper.holds()):
            return quick
        brain = main if how == "main" else providers.build(self.app, how)
        quota = self.app.quota
        if brain is not None and quota.wait_until(quota.pool(brain, "low")) is not None:  # its limit is kept for you
            brain = providers.local(self.app) if quota.setting("local") != "off" else None  # else the helper or rules
        if brain is not None and providers.fallback.cooling(self.app, brain.id):  # at its limit: the helper or rules
            return quick
        if brain is None or not brain.available()[0]:
            return quick

        def ask(q: str) -> str:
            r = brain.complete(q, effort="low", timeout=30)
            if jid and r.ok and r.text:
                self.decided[jid] = {"brain": brain.id, "model": r.model, "who": who(brain, r.model, "low")}
            return r.text

        return ask

    def _helper_classifier(self, helper, jid: str | None):
        """The offline helper's "how hard is this" (None when it isn't ready), noting it as the one that decided."""
        ask = helper.classifier() if helper is not None else None
        if ask is None or not jid:
            return ask

        def decide(q: str) -> str:
            word = ask(q)
            if word:
                tag = str(helper.model().get("tag") or "")
                self.decided[jid] = {"brain": "helper", "model": tag, "who": who(None, tag, "low")}
            return word

        return decide

    def _run_safe(self, jid: str) -> None:
        """Run a job; a mistake anywhere ends it as failed (and tells you) instead of leaving it "running"."""
        try:
            self._run(jid)
        except Exception as e:
            self.app.events.emit("job_crashed", job=jid, error=f"{type(e).__name__}: {e}"[:300])
            self._end(jid, Verdict.ERROR, f"{type(e).__name__}: {e}")
        finally:
            self._stops.pop(jid, None)
            self.steps.pop(jid, None)
            self.recalled.pop(jid, None)
            self.decided.pop(jid, None)
            self.poke()

    def _run(self, jid: str) -> None:
        job = self.get(jid)
        stop = self._stops.get(jid) or threading.Event()
        s = self.app.settings
        main = providers.build(self.app, s.get("brain.main") or "")
        chosen = providers.fallback.chosen(self.app)  # brain.fallback: one AI, or a list of them (yours, in order)
        fallbacks = [b for k in chosen if (b := providers.build(self.app, k)) is not None]
        fallback = fallbacks[0] if fallbacks else None
        want = (self._read("select brain_req from jobs where id=?", (jid,)) or [None])[0]
        if want:  # pinned to an AI (a role in the concept graph): another AI program stands in if it can't
            pinned = providers.build(self.app, want)
            if pinned is not None:
                other = next(
                    (
                        b
                        for k in providers.AGENT_PROGRAMS
                        if k != want and (b := providers.build(self.app, k)) is not None and b.available()[0]
                    ),
                    None,
                )
                main, fallback = pinned, other or fallback
                fallbacks = [other] if other is not None else fallbacks
        origin = None  # what picked the effort (providers/effort.py); none when it was asked for
        if job.effort_req in ("low", "medium", "high"):
            level = job.effort_req
        else:
            level, origin = effort_mod.pick_with_origin(job.prompt, self._classifier(main, jid))
            if job.lane == "you":  # tuned while dreaming, for your own requests only (core/tuning.py)
                level = effort_mod.tuned(level, origin, s.get("brain.effort_map"))
        self._mark(jid, effort_from=origin or "")
        minutes = (s.get("brain.timeout_min") or {}).get(level, 15)
        tools = agent_tools(self.app)
        text_only = bool(self._read("select text_only from jobs where id=?", (jid,))[0])
        from kurooto.core import assembler, selfdoc  # what's remembered that your message refers to, within its budget

        memory, self.recalled[jid] = assembler.for_request(self.app, job)
        extra = "\n\n".join(x for x in (memory, selfdoc.for_request(self.app, job.prompt)) if x)
        task = Task(
            prompt=job.prompt,
            effort=level,
            title=job.title,
            cwd=self.app.workspace,
            timeout_s=minutes * 60,
            context=headless_context(self.app, extra),
            tools=[] if text_only else tools,  # text-only work gets no tools (and agent programs no MCP)
            run_tool=lambda name, args: run_tool(self.app, name, args, tools, job=jid),
            mcp=None if text_only else mcp_command(),
            mcp_env={**run_env(self.app.paths), ENV_JOB: jid},  # its tool uses come back marked as its steps
            text_only=text_only,
            on_process=lambda pid: self._mark(jid, proc=_process(pid)),
            stop=stop,
        )
        chain = []
        for b in (main, *fallbacks):  # the AIs you picked take over on any failure, as before
            if b is not None and b.id not in {c.id for c in chain}:
                chain.append(b)
        if not want and fallback is not None and level in (s.get("brain.fallback_first") or []):
            chain = [fallback, *[b for b in chain if b is not fallback]]  # tuned while dreaming (core/tuning.py)
        last = self._last_resort(main)
        if last is not None and last.id not in {b.id for b in chain}:
            chain.append(last)
        # none picked: at a limit (brain.fallback_on) the automatic order takes over (providers/fallback.py)
        auto = [] if chosen else providers.fallback.candidates(self.app, {b.id for b in chain})
        chain += auto
        auto_ids = {b.id for b in auto}
        on = providers.fallback.triggers(self.app)
        kept, skipped = providers.fallback.skip_cooling(self.app, chain)  # still at a limit: straight to the next
        if any(b.id not in auto_ids or "rate_limited" in on for b in kept):  # ...when one that will run is left
            chain = kept
        else:
            skipped = []
        chain, wait = self.app.quota.arrange(chain, level, job.background)  # free limits kept for you (core/quota.py)
        if wait is not None and not chain:
            self._defer(jid, wait)
            return
        helper = getattr(self.app, "helper", None)
        if helper is not None and chain and helper.holds():  # no internet: only an AI on this computer can run it
            here = [b for b in chain if helper.here(b)]
            waited = (self._read("select held from jobs where id=?", (jid,)) or [None])[0]
            if here:
                chain = here
            elif not waited or helper.sure():  # one that waited already tries, unless it's down for certain
                self._hold(jid, job)
                return
        if chain:
            self.plan_line(job, chain[0], level, self.recalled.get(jid, 0))
        tried = time.time()
        used, result, first = None, Result(Verdict.ERROR, detail="no AI brain is set up"), None
        limits: list[dict] = []  # every limit hit on the way, also one a stand-in then answered for
        moved = bool(skipped) and "rate_limited" in on  # a limit already moves this request on
        for i, brain in enumerate(chain):
            if stop.is_set():  # cancelled, or ended by the watchdog: it was told already
                return
            if brain.id in auto_ids and not moved:  # the automatic order: only at a limit (or what fallback_on says)
                continue
            ok, why = brain.available()
            if not ok:
                result, used = Result(Verdict.ERROR, detail=why), brain
                first = first or (brain, result)
                continue
            used = brain
            if brain.kind == "cli":
                brain.prepare(self.app)
            # which AI is at work, and until when (the watchdog's limit: its time plus the brain's grace and ours)
            limit = task.timeout_s + getattr(brain, "grace_s", 0) + GRACE_S
            self._mark(jid, brain=brain.id, deadline=time.time() + limit)
            try:
                result = brain.run(task)
            finally:
                self._mark(jid, proc=None, deadline=None)
            if stop.is_set():
                return
            steps = len(self.steps.get(jid, ()))  # agent programs' tool uses arrive through `kurooto mcp`
            if steps and isinstance(result.usage, dict) and not result.usage.get("tool_calls"):
                result.usage = {**result.usage, "tool_calls": steps}
            self._attempt(jid, brain.id, result)
            if result.verdict == Verdict.RATE_LIMITED:
                limits.append(
                    {"brain": brain.id, "retry_after_s": result.retry_after_s, "detail": result.detail[-500:]}
                )
                providers.fallback.cool(self.app, brain.id, result)  # skipped until its reset (or a back-off)
            elif result.ok and providers.fallback.cooling(self.app, brain.id):
                providers.fallback.clear(self.app, brain.id)  # it answered before the reset we thought
            if brain.kind == "cli" and result.ok:
                brain.mark_worked(self.app)
            if (
                result.verdict in (Verdict.ERROR, Verdict.TIMEOUT)
                and helper is not None
                and not helper.here(brain)
                and helper.lost(tried)
            ):
                break  # the connection went: the request waits for it (below); that's no fallback case
            hand_on = result.verdict.value in on
            moved = moved or hand_on
            if result.verdict not in RETRY and not hand_on:
                break
            first = first or (brain, result)
            nxt = next((b for b in chain[i + 1 :] if b.id not in auto_ids or moved), None)
            self._problem(brain, result, nxt, level)
        if limits:  # the follow-up sees them (the concept graph's reading budget: core/readbudget.py)
            result.usage = {**result.usage, "limits": limits}
        if wait is not None and not result.ok:  # moved to the model here, which couldn't: it waits for the reset
            self._defer(jid, wait)
            return
        if (
            not result.ok
            and result.verdict in (Verdict.ERROR, Verdict.TIMEOUT)
            and helper is not None
            and not (used is not None and helper.here(used))
            and helper.lost(tried)
        ):  # the connection went while it tried: it waits for it to come back (not another AI's turn)
            self._hold(jid, job)
            return
        fell = ""  # who couldn't and who answered instead, for the run receipt
        before = first[0] if first else skipped[0][0] if skipped else None
        if used is not None and result.ok and before is not None and before is not used:
            fell = handed(first, None if first else skipped[0], used)
        if last is not None and used is last and result.ok and first:
            note = f"(Answered with {SHORT.get(last.id, last.label)}: {_why(*first)}.)"
            result.usage = {**result.usage, "note": note}
        waited = (self._read("select held from jobs where id=?", (jid,)) or [None])[0]
        if waited and result.ok:
            line = f"(It waited for the internet connection from {_clock(waited)}.)"
            note = (result.usage or {}).get("note")
            result.usage = {**result.usage, "note": f"{note}\n{line}" if note else line}
        if (
            result.verdict == Verdict.DENIED
            and getattr(used, "denied_help", "")
            and not self.app.secrets.get(GEMINI_KEY)
        ):
            result.detail = used.denied_help
        ok = result.ok
        took = time.time() - (job.started or time.time())
        receipt = self._receipt(jid, used, level, took, result.model, fell) if used else None
        with self._lock:
            done = self._db.execute(
                "update jobs set status=?, verdict=?, brain=?, effort=?, finished=?, seconds=?, result=?, detail=?, "
                "receipt=?, model=?, proc=null, deadline=null where id=? and status='running'",
                (
                    "ok" if ok else "failed",
                    result.verdict.value,
                    used.id if used else None,
                    level,
                    time.time(),
                    round(result.seconds, 1),
                    result.text,
                    result.detail[:2000],
                    receipt,
                    result.model or None,
                    jid,
                ),
            ).rowcount
        if not done:  # cancelled or ended by the watchdog while it ran: that was told already
            return
        self.app.events.emit(
            "job_done",
            job=jid,
            ok=ok,
            verdict=result.verdict.value,
            effort=level,
            brain=used.id if used else None,
            model=result.model or None,
            seconds=round(result.seconds),
            **({"fallback": True} if fell else {}),
        )
        self._after(self.get(jid), result, used)

    def _after(self, job: Job, result: Result, used=None, tell: bool = True) -> None:
        """A finished job: the answer to you (unless it's quiet), then its follow-up (then_action)."""
        if tell and not job.quiet:
            self._deliver(job, result, used)
        then = self._read("select then_action, then_payload from jobs where id=?", (job.id,))
        if then and then[0] and then[0] in self.then_actions:
            try:
                self.then_actions[then[0]](job, result, json.loads(then[1] or "{}"))
            except Exception as e:
                self.app.events.emit("job_then_failed", job=job.id, error=str(e)[:300])
        with self._lock:
            steps = self.steps.pop(job.id, [])
        if self.watchers:
            try:
                payload = json.loads((then[1] if then else None) or "{}")
            except ValueError:
                payload = {}
            info = {"steps": steps, "then": (then[0] if then else None) or "", "payload": payload}
            for fn in list(self.watchers):
                try:
                    fn(job, result, info)
                except Exception as e:  # a watcher's mistake never touches the answer, which is delivered already
                    self.app.events.emit("job_watcher_failed", job=job.id, error=f"{type(e).__name__}: {e}"[:300])

    def expected(self, brain: str, level: str) -> float | None:
        """How long a request of yours on this AI and effort usually takes: the median of the last 9 that answered,
        or None with fewer than PLAN_SAMPLES."""
        rows = self._read(
            "select seconds from jobs where lane='you' and status='ok' and brain=? and effort=? "
            "and seconds is not null order by finished desc limit 9",
            (brain, level),
            one=False,
        )
        secs = sorted(float(r[0]) for r in rows or [])
        return secs[len(secs) // 2] if len(secs) >= PLAN_SAMPLES else None

    def plan_line(self, job: Job, brain, level: str, recalled: int = 0) -> str:
        """The plan line before a long text answer of yours (jobs.plan_line); "" when there's none. Never for quiet or
        background work (a call's requests are quiet) or while you're on a call."""
        if not self.app.settings.get("jobs.plan_line") or job.quiet or job.background or job.lane != "you":
            return ""
        try:
            if self.app.availability.on_call_until():
                return ""
        except Exception:  # no availability: no reason to hold it
            pass
        est = self.expected(brain.id, level)
        if est is None or est <= PLAN_S:
            return ""
        prompt = job.prompt.split("Current request:\n", 1)[-1]
        steps = []
        if "Files they sent with it" in prompt:
            steps.append("Opening the file you sent")
        if URL.search(prompt):
            steps.append("Reading the link")
        if NOTES_CUE.search(prompt):
            steps.append("Searching your notes")
        if recalled:
            steps.append(f"going over {recalled} remembered {_plural('item', recalled)}")
        first = (", ".join(steps[:2]) or "Thinking it through").capitalize()
        line = f"{first}, then answering (about {_took(est)} with {SHORT.get(brain.id, brain.label)})."
        reply_to = int(job.reply_to) if job.reply_to and job.reply_to.isdigit() else job.reply_to
        self.app.notify(line, kind="info", reply_to=reply_to, why="asked")
        self.app.events.emit("job_plan_line", job=job.id, expected=round(est))
        return line

    def note_step(self, jid: str, name: str, args: dict | None = None) -> None:
        """One tool use by a request that is running in this process (from core/tools.py:run_tool): its tool log."""
        with self._lock:
            if jid not in self._stops:  # not one of ours, or over already
                return
            log = self.steps.setdefault(jid, [])
            if len(log) < MAX_STEPS:
                log.append(
                    {"name": str(name)[:60], "args": json.dumps(args or {}, ensure_ascii=False, default=str)[:300]}
                )

    def _receipt(self, jid: str, used, level: str, seconds: float, model: str = "", fell: str = "") -> str:
        """The run receipt of a request that just ran: who decided and who answered (with their models; a fallback
        says why), effort, time, the share of today's limit (when core/quota.py knows the limit) and what it did from
        its tool log."""
        with self._lock:
            steps = list(self.steps.get(jid, ()))
        pct = None
        try:
            pool = self.app.quota.pool(used, level)
            pct = self.app.quota.status(pool)["pct"] if pool else None
        except Exception:  # a broken count never stops the answer
            pass
        d = self.decided.get(jid) or {}
        same = d.get("brain") == used.id and (d.get("model") or "") == (model or "")
        decided = "" if same else d.get("who", "")  # the same model decided and answered: nothing to tell apart
        return receipt(used, level, seconds, pct, steps, self.recalled.get(jid, 0), model, decided, fell)

    def receipt(self, jid: str) -> str:
        """A finished request's run receipt, to show under its answer ("" when jobs.receipt is off or no AI ran)."""
        if not self.app.settings.get("jobs.receipt"):
            return ""
        return (self._read("select receipt from jobs where id=?", (jid,)) or [None])[0] or ""

    def _mark(self, jid: str, **cols) -> None:
        """Note how a running job is doing (which AI, its program, its deadline); each note is a sign of life."""
        cols["activity"] = time.time()
        sets = ", ".join(f"{k}=?" for k in cols)  # constant column names only
        with self._lock:
            self._db.execute(f"update jobs set {sets} where id=? and status='running'", (*cols.values(), jid))

    # ------------------------------------------------------------------------------------- ending early
    def _end(self, jid: str, verdict: Verdict, detail: str, tell: bool = True) -> bool:
        """End a queued or running job as failed now: its program (and what that started) is stopped, the thread
        running it stops at its next step and its late answer is dropped. You're told unless tell=False or it's
        quiet; its follow-up runs with the failure. False if it wasn't queued or running."""
        t = time.time()
        with self._lock:
            row = self._db.execute("select status, proc from jobs where id=?", (jid,)).fetchone()
            if not row or row[0] not in ACTIVE:
                return False
            self._db.execute(
                "update jobs set status='failed', verdict=?, finished=?, detail=?, proc=null, deadline=null, "
                "seconds=case when started is null then 0 else round(? - started, 1) end where id=?",
                (verdict.value, t, detail[:2000], t, jid),
            )
        ev = self._stops.get(jid)
        if ev is not None:
            ev.set()
        if row[1] and _alive(row[1]):
            proc.kill_tree(int(str(row[1]).split(":")[0]))
        self.app.events.emit("job_ended", job=jid, verdict=verdict.value, was=row[0])
        self._after(self.get(jid), Result(verdict, detail=detail), tell=tell)
        self.poke()
        return True

    def cancel(self, jid: str) -> Job | None:
        """Cancel a queued or running request (a running agent program is stopped with everything it started). The
        job, or None if it wasn't waiting or running."""
        if not self._end(jid, Verdict.CANCELLED, "cancelled by you", tell=False):
            return None
        self.app.events.emit("job_cancelled", job=jid)
        return self.get(jid)

    def find(self, ref: str) -> Job | None:
        """A running or waiting job by its id, or by the start of it when only one matches."""
        ref = str(ref or "").strip().lower()
        act = self.active()
        hit = [j for j in act if j.id == ref] or [j for j in act if ref and j.id.startswith(ref)]
        return hit[0] if len(hit) == 1 else None

    def halt(self) -> None:
        """Kurooto is stopping: running jobs take no more steps and give no answer. They stay "running" with this
        process gone, so the next start runs them again (recover)."""
        for ev in list(self._stops.values()):
            ev.set()

    def watchdog(self) -> list[str]:
        """End this process's stuck jobs as failed: no AI at work on it and no program running for jobs.stuck_min
        minutes, or a try still going past its time limit plus grace. Returns their ids."""
        try:
            stuck = max(1.0, float(self.app.settings.get("jobs.stuck_min") or 10)) * 60
        except (TypeError, ValueError):
            stuck = 600.0
        t, out = time.time(), []
        rows = self._read(
            "select id, proc, activity, started, deadline from jobs where status='running' and runner=?",
            (RUNNER,),
            one=False,
        )
        for jid, pr, act, started, deadline in rows:
            if deadline is not None:
                if t > deadline and self._end(jid, Verdict.TIMEOUT, "still going past its time limit; stopped"):
                    out.append(jid)
                continue
            if pr and _alive(pr):
                continue
            if t - float(act or started or t) > stuck:
                why = f"nothing happened for {round(stuck / 60)} min, with no AI at work on it; stopped"
                if self._end(jid, Verdict.STUCK, why):
                    out.append(jid)
        return out

    def corrected(self, said: str, within_s: float = 600) -> str | None:
        """You said "that's not what I asked" (core/tuning.py:heard): your last request answered in the last
        `within_s` seconds keeps your words (300 characters; forgotten with the request), once. Its id, or None."""
        with self._lock:
            row = self._db.execute(
                "select id from jobs where status in ('ok','failed') and coalesce(lane,'you')='you' and finished >= ? "
                "and coalesce(corrected,'')='' order by finished desc limit 1",
                (time.time() - within_s,),
            ).fetchone()
            if row:
                self._db.execute("update jobs set corrected=? where id=?", ((said or "").strip()[:300] or "-", row[0]))
        return row[0] if row else None

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
        """When the main AI can't do a request: Gemini hands over to an agent program (agy, Claude Code) that is
        installed and has worked here before. Agent programs do NOT roll over to the free Gemini key (its limit)."""
        if main is None:
            return None
        if main.id == "gemini":
            for key in providers.AGENT_PROGRAMS:
                brain = providers.build(self.app, key)
                if (
                    brain is not None
                    and brain.available()[0]
                    and getattr(brain, "has_worked", lambda a: False)(self.app)
                ):
                    return brain
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
        elif result.detail.startswith(GAVE_UP):  # it waited local_helper.hold_h for the internet
            body = result.detail
        else:
            body = FRIENDLY.get(result.verdict, "It failed.").format(brain=label)
        reply_to = int(job.reply_to) if job.reply_to and job.reply_to.isdigit() else job.reply_to
        cases = self.app.modules.get("cases") if self.app.is_on("cases") else None  # (wrong) a Wrong button on it
        buttons = cases.answer_buttons(job.id) if cases is not None else None
        tail = self.receipt(job.id) or None  # the run receipt, last (Telegram shows it in italics)
        end = f"\n\n{tail}" if tail else ""
        if len(body) > LONG:
            md = self.dir / f"{job.id}-result.md"
            md.write_text(body, encoding="utf-8")
            self.app.notify(
                f"{head}\n\n{body[:1500]}\n\n[…the full answer is attached]{end}",
                kind="result",
                reply_to=reply_to,
                buttons=buttons,
                why=why,
                tail=tail,
            )
            # the file follows the answer (the phone app's chat gets a link: calls/chat.py:send_file)
            self.app.notify(job.title, kind="result", file=str(md), reply_to=reply_to, why=why)
        else:
            self.app.notify(
                f"{head}\n\n{body}{end}", kind="result", reply_to=reply_to, buttons=buttons, why=why, tail=tail
            )
        chat = self.app.modules.get("chat")
        if chat is not None and result.ok and result.text and getattr(chat, "owns", lambda _j: True)(job.id):
            try:  # only chat's own requests: a digest's or a research run's prompt isn't something you said
                chat.record_turn(job.prompt, result.text)
            except Exception:
                pass

    def _defer(self, jid: str, until: float) -> None:
        """Background work whose free limits are kept for you: back in the queue until the reset, never dropped."""
        until = max(float(until), self.app.quota.clock() + 60)
        with self._lock:
            self._db.execute(
                "update jobs set status='queued', not_before=?, runner=null, started=null, proc=null, deadline=null "
                "where id=? and status='running'",
                (until, jid),
            )
        self.app.events.emit("job_deferred", job=jid, until=datetime.datetime.fromtimestamp(until).isoformat())

    def _hold(self, jid: str, job: Job) -> None:
        """No internet (core/helper.py): back in the queue, looked at again every RETRY_S and at once when the
        connection is back (unhold). You're told the first time it waits (your own requests); one that waited
        local_helper.hold_h ends with a message. Never dropped silently."""
        from kurooto.core import helper as helper_mod

        t = time.time()
        first = (self._read("select held from jobs where id=?", (jid,)) or [None])[0]
        hold_s = self.app.helper.hold_s()
        if first and t - float(first) > hold_s:
            h = round(hold_s / 3600)
            self._end(
                jid,
                Verdict.TIMEOUT,
                f"{GAVE_UP} for {h} h and didn't run, as the internet stayed down. Send it again once you're online.",
            )
            return
        with self._lock:
            self._db.execute(
                "update jobs set status='queued', held=coalesce(held, ?), held_until=?, runner=null, started=null, "
                "proc=null, deadline=null where id=? and status='running'",
                (t, t + helper_mod.RETRY_S, jid),
            )
        self.app.events.emit("job_held", job=jid, lane=job.lane, first=not first)
        if not first and job.lane == "you" and not job.quiet:
            from kurooto.core.calm import ASKED

            reply_to = int(job.reply_to) if job.reply_to and job.reply_to.isdigit() else job.reply_to
            self.app.notify(self.app.helper.waiting_line(job.title), kind="info", reply_to=reply_to, why=ASKED)

    def unhold(self) -> list[str]:
        """The internet is back: what waited for it runs now. The titles of your own requests among them."""
        with self._lock:
            rows = self._db.execute(
                "select title, coalesce(lane, 'you'), quiet from jobs where status='queued' and held_until is not null"
            ).fetchall()
            self._db.execute("update jobs set held_until=null where status='queued' and held_until is not null")
        if rows:
            self.poke()
        return [title for title, lane, quiet in rows if lane == "you" and not quiet]

    def held(self) -> int:
        """Requests waiting for the internet connection."""
        row = self._read("select count(*) from jobs where status='queued' and held_until is not null")
        return int(row[0]) if row else 0

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

    # ------------------------------------------------------------------------------------- /jobs
    def line(self, j: Job) -> str:
        """One running or waiting job, for /jobs and `kurooto jobs`."""
        t = time.time()
        if j.status == "running":
            who = providers.CHOICES.get(j.brain or "", j.brain or "")
            what = f"{SHORT.get(j.brain or '', who) or 'starting'} · {_mins(t - (j.started or t))}"
        else:
            what = f"waiting {_mins(t - j.created)}"
            if j.not_before and j.not_before > t:
                what += f", until a free limit resets ({datetime.datetime.fromtimestamp(j.not_before):%H:%M})"
            elif (self._read("select held_until from jobs where id=?", (j.id,)) or [None])[0]:
                what += ", for the internet connection"
            elif j.background and self.app.power.current != "normal":
                what += ", for the charger"
        lane = "" if j.lane == "you" else " · background"
        return f"- {j.title} · {what}{lane} ({j.id})"

    def command(self, arg: str = "") -> tuple[str, list | None]:
        """/jobs: what's running and waiting, each with a Cancel button, then the last few that finished.
        /jobs cancel <id|all> does it from the keyboard."""
        words = arg.split()
        if words and words[0].lower() in ("cancel", "stop"):
            return self.cancel_text(words[1] if len(words) > 1 else ""), None
        act = self.active()
        run = [self.line(j) for j in act if j.status == "running"]
        wait = [self.line(j) for j in act if j.status == "queued"]
        lines = (["Running:", *run] if run else []) + (["Waiting:", *wait] if wait else [])
        if not act:
            lines.append("Nothing running or waiting.")
        done = [j for j in self.recent(12) if j.status not in ACTIVE][:5]
        if done:
            lines += ["", "Last finished:"] + [
                f"{j.status:7} {j.effort or '-':6} {f'{j.seconds:.0f}s' if j.seconds else '':>5}  {j.title}"
                + (f" · {NAMES.get(j.brain, j.brain)}" if j.brain else "")
                + (f" {short_model(j.model, j.effort or '')}" if j.brain and j.model else "")
                + (f" ({j.verdict})" if j.status == "failed" and j.verdict else "")
                for j in done
            ]
        if len(act) > 1:
            lines.append("\n/jobs cancel <id> (or all) cancels from here too.")
        buttons = [[(f"Cancel: {j.title[:40]}", f"job:{j.id}:cancel")] for j in act[:8]]
        if len(act) > 1:
            buttons.append([("Cancel all", "job:all:cancel")])
        return "\n".join(lines), buttons or None

    def cancel_text(self, ref: str) -> str:
        """/jobs cancel <id|all>, a Cancel button, `kurooto jobs --cancel`: what happened, in one line."""
        ref = str(ref or "").strip()
        if not ref:
            return "Which one? /jobs lists them with their ids: /jobs cancel <id>, or /jobs cancel all."
        if ref.lower() == "all":
            gone = [j for j in self.active() if self.cancel(j.id)]
            if not gone:
                return "Nothing was running or waiting."
            return f"Cancelled {len(gone)}: " + "; ".join(j.title for j in gone)[:600] + "."
        j = self.find(ref)
        if j is None:
            return f"No running or waiting request {ref} (it may have finished: /jobs)."
        return f"Cancelled: {j.title}." if self.cancel(j.id) else f"{j.title} had finished already."

    def button(self, ref: str, act: str) -> str:
        """The Cancel buttons under /jobs ("job:<id>:cancel", "job:all:cancel")."""
        if act != "cancel":
            return "unknown button"
        return self.cancel_text(ref)[:190]

    def close(self) -> None:
        self._db.close()


def public(j: Job) -> dict:
    """A job for the dashboard and `kurooto jobs`: what it is and how it's going (not what was asked or answered)."""
    keys = ("id", "title", "status", "verdict", "effort", "seconds", "created", "started", "brain", "lane", "model")
    return {k: getattr(j, k) for k in keys} | {"receipt": j.receipt or ""}


def _clock(ts: float) -> str:
    """14:02, or Mon 14:02 on another day."""
    d = datetime.datetime.fromtimestamp(float(ts))
    return f"{d:%H:%M}" if d.date() == datetime.date.today() else f"{d:%a %H:%M}"


def _mins(secs: float) -> str:
    m = int(max(0, secs) // 60)
    return "under a minute" if m < 1 else f"{m} min" if m < 120 else f"{m // 60} h"


def mcp_command() -> list[str]:
    """How an agent program starts Kurooto's tool server (`kurooto mcp`), with this version's own Python."""
    return command()


def who(brain, model: str = "", effort: str = "") -> str:
    """An AI and its model, short: "Claude Code opus-4.5", "agy 3.8-flash"; a model on this computer or behind an API
    key by its model alone ("gemma4:e4b")."""
    if brain is None:
        return short_model(model, effort)
    m = short_model(model, effort)
    if brain.kind != "cli" and m:
        return m
    name = NAMES.get(brain.id, brain.label)
    return f"{name} {m}" if m else name


def handed(first: tuple | None, skipped: tuple | None, used) -> str:
    """Why another AI answered, for the run receipt: "Claude Code hit its limit; agy answered", "Claude Code is at its
    limit until 15:00; agy answered"."""
    them = SHORT.get(used.id, NAMES.get(used.id, used.label))
    if first is not None:
        return f"{_why(*first)}; {them} answered"
    brain, until = skipped
    name = SHORT.get(brain.id, NAMES.get(brain.id, brain.label))
    return f"{name} is at its limit until {_clock(until)}; {them} answered"


def _clock(ts: float) -> str:
    d = datetime.datetime.fromtimestamp(ts)
    return f"{d:%H:%M}" if d.date() == datetime.date.today() else f"{d:%a %H:%M}"


def receipt(
    brain,
    effort: str,
    seconds: float,
    pct: int | None,
    steps: list[dict],
    recalled: int = 0,
    model: str = "",
    decided: str = "",
    fell: str = "",
) -> str:
    """The run receipt: one line built from the run's own record, never from the answer's words, e.g.
    "agy · 3.8-flash · medium · 42 s · 12% of today's limit · searched notes, wrote 1 note · used 2 remembered items".
    The model is the one it ran with (agy's --model, the one Claude Code says it used), shortened. decided: the model
    that made the quick decision (the effort), when it isn't the one that answered ("decided by gemma4:e4b, answered
    by Claude Code · opus-4.5 · ..."). fell: why another AI answered ("Claude Code hit its limit; agy answered"). An
    agent program may also work with tools of its own, which Kurooto doesn't see: with none of Kurooto's, it "did
    nothing through Kurooto". recalled: how many remembered items it was told (core/assembler.py)."""
    name = NAMES.get(brain.id, brain.label)
    lead = fell or name
    if decided:
        lead = f"decided by {decided}; {fell}" if fell else f"decided by {decided}, answered by {name}"
    m = short_model(model, effort)
    head = [lead, *([m] if m else []), effort, _took(seconds)]
    if pct is not None:
        head.append(f"{pct}% of today's limit")
    did = _did(steps) or ["did nothing" if brain.kind != "cli" else "did nothing through Kurooto"]
    tail = f" · used {recalled} remembered item{'s' if recalled != 1 else ''}" if recalled else ""
    line = " · ".join(head) + " · " + ", ".join(did) + tail
    while len(line) > RECEIPT_MAX and len(did) > 1:
        did = did[:-1]
        line = " · ".join(head) + " · " + ", ".join(did) + " and more" + tail
    if len(line) > RECEIPT_MAX:  # long model names: what it did goes first, never half a word
        line = " · ".join(head) + tail
    return line if len(line) <= RECEIPT_MAX else line[: RECEIPT_MAX - 1] + "…"


def _did(steps: list[dict]) -> list[str]:
    """What a run did, from its tool log, in the order it first did each: ["searched notes", "wrote 2 notes"]."""
    counts: dict[tuple[str, str], int] = {}
    other = 0
    for s in steps:
        act = ACTS.get(str(s.get("name") or ""))
        if act is None:
            other += 1
        else:
            counts[act] = counts.get(act, 0) + 1
    out = [f"{verb} {n} {_plural(noun, n)}" if noun else verb for (verb, noun), n in counts.items()]
    if other:
        out.append(f"used {other} other tool{'s' if other > 1 else ''}")
    return out


def _plural(noun: str, n: int) -> str:
    if n == 1:
        return noun
    return noun[:-1] + "ies" if noun.endswith("y") else noun + "s"


def _took(secs: float) -> str:
    s = max(1, round(secs))
    if s < 60:
        return f"{s} s"
    return f"{round(s / 60)} min" if s < 3600 else f"{s // 3600} h {round(s % 3600 / 60)} min"


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
