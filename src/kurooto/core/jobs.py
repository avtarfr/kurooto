"""The AI job queue: requests that may take minutes run in the background and the answer comes back to you.

CLI brains (agy) run one job at a time; API brains may run a few at once. If the main brain is rate-limited or
signed out and a fallback brain is set, the job is retried once on the fallback.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import providers
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
"""
LONG = 7000  # longer answers are also sent as a document

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


class Jobs:
    def __init__(self, app: App):
        self.app = app
        self.dir = app.paths.state / "jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(app.paths.state / "jobs.db", check_same_thread=False, isolation_level=None)
        self._db.execute("pragma journal_mode=wal")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()
        self._cli_lock = threading.Lock()  # CLI brains: one job at a time
        self._wake: asyncio.Event | None = None
        self._loop = None
        self.then_actions: dict = {}  # name -> fn(job, result)
        if "background" not in [r[1] for r in self._db.execute("pragma table_info(jobs)")]:  # older databases
            self._db.execute("alter table jobs add column background integer default 0")
        with self._lock:  # jobs cut off by a restart run again
            self._db.execute("update jobs set status='queued' where status='running'")

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
    ) -> str:
        """Queue an AI request. background=True: work nobody is waiting for, which waits for the charger when the
        laptop is on battery."""
        forced, prompt_clean = effort_mod.strip_forced(prompt)
        jid = "j" + uuid.uuid4().hex[:8]
        with self._lock:
            self._db.execute(
                "insert into jobs(id,title,prompt,effort_req,status,reply_to,quiet,created,then_action,then_payload,"
                "background) values(?,?,?,?, 'queued',?,?,?,?,?,?)",
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
                ),
            )
        self.app.events.emit("job_queued", job=jid, chars=len(prompt_clean))
        if self._wake is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._wake.set)
        return jid

    def poke(self) -> None:
        """Look at the queue now (e.g. a pause just ended)."""
        if self._wake is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    def get(self, jid: str) -> Job | None:
        row = self._db.execute(f"select {self._cols} from jobs where id=?", (jid,)).fetchone()
        return Job(*row[:9], bool(row[9]), *row[10:]) if row else None

    def recent(self, n: int = 10) -> list[Job]:
        rows = self._db.execute(f"select {self._cols} from jobs order by created desc limit ?", (n,)).fetchall()
        return [Job(*r[:9], bool(r[9]), *r[10:]) for r in rows]

    _cols = "id,title,prompt,effort_req,effort,status,verdict,brain,reply_to,quiet,created,seconds,result"

    def _claim(self) -> str | None:
        with self._lock:
            row = self._db.execute(
                "select id from jobs where status='queued' and (background=0 or ?) order by created limit 1",
                (int(self.app.power.current == "normal"),),
            ).fetchone()
            if not row:
                return None
            self._db.execute("update jobs set status='running', started=? where id=?", (time.time(), row[0]))
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
        while not stop.is_set():
            if (
                self.app.power.current != "paused"
                and self._db.execute(
                    "select 1 from jobs where status='queued' and (background=0 or ?) limit 1",
                    (int(self.app.power.current == "normal"),),
                ).fetchone()
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
        task = Task(
            prompt=job.prompt,
            effort=level,
            title=job.title,
            cwd=self.app.workspace,
            timeout_s=minutes * 60,
            context=headless_context(self.app),
            tools=tools,
            run_tool=lambda name, args: run_tool(self.app, name, args, tools),
            mcp=mcp_command(),
        )
        used, result = None, Result(Verdict.ERROR, detail="no AI brain is set up")
        for brain in [b for b in (main, fallback) if b is not None]:
            ok, why = brain.available()
            if not ok:
                result, used = Result(Verdict.ERROR, detail=why), brain
                continue
            used = brain
            if brain.kind == "cli":
                with self._cli_lock:
                    result = brain.run(task)
            else:
                result = brain.run(task)
            if result.verdict not in (Verdict.RATE_LIMITED, Verdict.AUTH, Verdict.ERROR):
                break
            self._problem(brain, result)
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
        then = self._db.execute("select then_action, then_payload from jobs where id=?", (jid,)).fetchone()
        if then and then[0] and then[0] in self.then_actions:
            try:
                self.then_actions[then[0]](job, result, json.loads(then[1] or "{}"))
            except Exception as e:
                self.app.events.emit("job_then_failed", job=jid, error=str(e)[:300])

    def _problem(self, brain, result: Result) -> None:
        """Tell the user about a usage limit or a sign-out, at most once an hour per brain."""
        if result.verdict not in (Verdict.RATE_LIMITED, Verdict.AUTH):
            return
        flag = self.dir / f"told-{brain.id}-{result.verdict.value}"
        if flag.exists() and time.time() - flag.stat().st_mtime < 3600:
            return
        flag.touch()
        text = FRIENDLY[result.verdict].format(brain=brain.label)
        if result.verdict == Verdict.RATE_LIMITED:
            fb = self.app.settings.get("brain.fallback")
            text += (
                f" Requests go to the fallback ({providers.CHOICES.get(fb, fb)}) meanwhile."
                if fb
                else (" Requests will fail until it resets. You can set a fallback brain in Settings.")
            )
        self.app.notify(
            text,
            title=f"{brain.label}: action needed" if result.verdict == Verdict.AUTH else None,
            kind="info",
            urgent=True,
        )

    def _deliver(self, job: Job, result: Result, used) -> None:
        label = used.label if used else "AI"
        head = f"[{label} · {job.effort or '?'}{'' if result.ok else ' · failed'}] {job.title}"
        if result.ok:
            body = result.text
        else:
            body = FRIENDLY.get(result.verdict, "It failed.").format(brain=label)
        reply_to = int(job.reply_to) if job.reply_to and job.reply_to.isdigit() else job.reply_to
        if len(body) > LONG:
            md = self.dir / f"{job.id}-result.md"
            md.write_text(body, encoding="utf-8")
            self.app.notify(
                f"{head}\n\n{body[:1500]}\n\n[…the full answer is attached]", kind="result", reply_to=reply_to
            )
            self.app.notify(job.title, kind="result", file=str(md))
        else:
            self.app.notify(f"{head}\n\n{body}", kind="result", reply_to=reply_to)

    def close(self) -> None:
        self._db.close()


def mcp_command() -> list[str]:
    """How an agent program starts Kurooto's tool server (`kurooto mcp`), with this version's own Python."""
    return [sys.executable, "-m", "kurooto", "mcp"]


def result_path(app: App, jid: str) -> Path:
    return app.paths.state / "jobs" / f"{jid}-result.md"
