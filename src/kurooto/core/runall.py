"""Run all (0.8.8): every process that otherwise waits for the night, now, one after another: /run all on Telegram (and
the phone app's chat), `kurooto run all` in a terminal (it prints the progress line live).

    1 Books           read new books (Books: its own reading thread, on the charger; waits until it ends)
    2 Inbox           file the inbox: the Notes sorter's pass, with the inbox reader when sorter.read_files is on
    3 Concept graph   the queue: batch after batch until nothing is ready, tonight's budget stops it, or /graph stop
                      holds it (respected: the batch already asked for finishes)
    4 Look-alikes     the duplicates pass: clear pairs merged (integrate.auto_merge, with Undo), the unsure ones asked
    5 Garden          the daily linking pass, then waits for its linking requests to come back

A step runs only when its feature (and the switch for that part) is on; one that's off is listed as skipped. Each step
waits for the one before, on a thread of its own (the call line and Telegram never wait on it), with a tqdm-style line:

    [3/5] Concept graph |########------------| 40% 4/10 batches, 2:05 elapsed, ETA 3:08

Only one run at a time (a second /run all says what's running). /run all status: that line. /run all stop: the step
running stops at its next safe point (a book after its page, the graph after the batch in flight, the garden before
its next note) and the rest don't start. It ends with one summary. Off: runall.on = false.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming

register_defaults(
    "runall",
    {
        "on": True,  # /run all and `kurooto run all`: every nightly process that's on, now, one after another
    },
)
POLL = 2.0  # seconds between looks at a step that runs elsewhere (a book's reading thread, the AI's requests)
EDIT_EVERY = 5.0  # seconds between edits of the Telegram message (Telegram limits how often a message may change)
WIDTH = 20  # the bar's width
_start = threading.Lock()  # two /run all at once: one starts


class Skip(Exception):
    """A step that doesn't run: its feature is off, or there's nothing it can do now (the reason)."""


# ------------------------------------------------------------------------------------------------ the line
def clock(s: float | None) -> str:
    """Seconds as m:ss (h:mm:ss from an hour); "?" when not known."""
    if s is None or s < 0:
        return "?"
    s = int(round(s))
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def line(i: int, n: int, name: str, done: int, total: int | None, unit: str, elapsed: float) -> str:
    """The tqdm-style progress line of step i of n."""
    if total:
        frac = min(1.0, max(0.0, done / total))
        fill = int(round(frac * WIDTH))
        eta = elapsed / done * (total - done) if done else None
        return (
            f"[{i}/{n}] {name} |{'#' * fill}{'-' * (WIDTH - fill)}| {frac:.0%} {done}/{total} {unit}, "
            f"{clock(elapsed)} elapsed, ETA {clock(0 if done >= total else eta)}"
        )
    return f"[{i}/{n}] {name} |{'-' * WIDTH}| {done} {unit}, {clock(elapsed)} elapsed, ETA ?"


# ------------------------------------------------------------------------------------------------ a run
@dataclass
class Step:
    key: str
    name: str
    unit: str
    fn: Callable[[Run], str]


@dataclass
class Run:
    app: App
    steps: list[Step]
    stop: threading.Event = field(default_factory=threading.Event)
    i: int = 0  # the step running (0-based)
    done: int = 0
    total: int | None = None
    started: float = field(default_factory=time.monotonic)
    step_started: float = field(default_factory=time.monotonic)
    results: list[tuple[str, str]] = field(default_factory=list)  # (step name, what it did or why it was skipped)
    finished: bool = False
    buttons: list = field(default_factory=list)  # Undo buttons for the summary (merges made by themselves)
    watch: Callable[[Run, bool], None] | None = None  # told of progress (Telegram's message); True: a step ended
    thread: threading.Thread | None = None

    def progress(self, done: int, total: int | None) -> None:
        self.done, self.total = int(done), (int(total) if total else None)
        if self.watch:
            self.watch(self, False)

    def line(self) -> str:
        if self.finished or self.i >= len(self.steps):
            return "Finished."
        st = self.steps[self.i]
        return line(
            self.i + 1, len(self.steps), st.name, self.done, self.total, st.unit, time.monotonic() - self.step_started
        )

    def text(self) -> str:
        """What's done, and the line of the step running."""
        rows = [f"{name}: {what}" for name, what in self.results]
        if not self.finished:
            rows.append(self.line())
        return "\n".join(rows)

    def wait(self, s: float = POLL) -> bool:
        """Sleep a moment; True when /run all stop came."""
        return self.stop.wait(s)

    def go(self) -> None:
        for k, st in enumerate(self.steps):
            if self.stop.is_set():
                self.results.append((st.name, "not started (stopped)"))
                continue
            self.i, self.done, self.total, self.step_started = k, 0, None, time.monotonic()
            if self.watch:
                self.watch(self, False)
            try:
                said = st.fn(self)
            except Skip as e:
                said = f"skipped ({e})"
            except Exception as e:  # one step's mistake never stops the next
                said = f"failed: {type(e).__name__}: {e}"[:300]
                self.app.events.emit("runall_failed", step=st.key, error=said)
            took = time.monotonic() - self.step_started
            self.results.append((st.name, f"{said} ({clock(took)})" if not said.startswith("skipped") else said))
            if self.watch:
                self.watch(self, True)
        self.finished = True

    def summary(self) -> str:
        head = "Run all stopped" if self.stop.is_set() else "Run all finished"
        rows = "\n".join(f"- {name}: {what}" for name, what in self.results)
        return f"{head} in {clock(time.monotonic() - self.started)}:\n{rows}"


# ------------------------------------------------------------------------------------------------ the steps
def _module(app: App, mid: str, title: str):
    m = app.modules.get(mid)
    if m is None or not app.is_on(mid):
        raise Skip(f"{title} is off")
    return m


def books_step(run: Run) -> str:
    app = run.app
    bk = _module(app, "books", "Books")
    lib = bk.library()
    if not lib:
        raise Skip("no books")

    def left() -> int:
        n = 0
        for b in bk.library():
            m = bk.meta(b)  # a book not opened yet counts as one page until its pages are known
            n += max(0, int(m["pages"]) - int(m.get("done") or 0)) if m.get("pages") else 1
        return n

    start = left()
    if not start:
        return "every book is read already"
    if not app.power.may_run(bk):
        raise Skip("on battery: books are read on the charger, /books read force reads now")
    bk.spawn(bk._until())  # noqa: SLF001 (or the reading already going: waited for the same)
    run.progress(0, start)
    t = getattr(bk, "_thread", None)
    while t is not None and t.is_alive():
        if run.wait():
            bk._halt.set()  # noqa: SLF001 (/books stop: after this page)
            t.join(timeout=120)
            break
        run.progress(max(0, start - left()), start)
    read = max(0, start - left())
    run.progress(read, start)
    return f"{read} page{'s' if read != 1 else ''} read" + (f", {start - read} left" if read < start else "")


def inbox_step(run: Run) -> str:
    so = _module(run.app, "sorter", "Notes sorter")
    run.progress(0, 1)
    out = so.run(force=True)
    run.progress(1, 1)
    read = len(out.get("read") or [])
    parts = [f"{len(out.get('moved') or [])} filed"]
    if run.app.settings.get("sorter.read_files"):
        parts.append(f"{read} file{'s' if read != 1 else ''} read into notes")
    parts.append(f"{out.get('asked', 0)} asked your AI about, {out.get('waiting', 0)} waiting for you")
    return ", ".join(parts)


def graph_step(run: Run) -> str:
    ig = _module(run.app, "integrate", "Concept graph")
    until = ig.stopped_until()
    if until:
        raise Skip(f"held by /graph stop until {until:%a %H:%M}; /graph now lifts it")
    c0 = ig.counts()
    done0, total = c0["done"], c0["todo"] + sum(ig.inflight())
    run.progress(0, total)
    why = ""
    while True:
        r = ig.tick()
        bulk, chk = ig.inflight()
        c = ig.counts()
        done = max(0, c["done"] - done0)
        total = max(total, done + c["todo"] + bulk + chk)
        run.progress(done, total)
        if r.get("stopped"):
            why = "held by /graph stop"
        elif r.get("limit"):
            why = "tonight's reading budget is used up"
        if not bulk and not chk and not r.get("submitted"):
            break
        if run.wait():
            why = "stopped: the request in flight still finishes"
            break
    done = max(0, ig.counts()["done"] - done0)
    said = f"{done} batch{'es' if done != 1 else ''} read into your notes"
    return f"{said} ({why})" if why else said


def same_step(run: Run) -> str:
    ig = _module(run.app, "integrate", "Concept graph")
    if not ig.setting("duplicates"):
        raise Skip("integrate.duplicates is off")
    from kurooto.core import graphmerge

    run.progress(0, 2)
    merged = graphmerge.auto(ig)
    run.progress(1, 2)
    said, undo = graphmerge.merged_section(ig)
    run.buttons += undo
    pairs, index = graphmerge.find(ig, again=True)
    if pairs:
        text, buttons = graphmerge.message(ig, pairs, index)
        run.app.notify(text, kind="question", buttons=buttons, why="asked", about=f"{len(pairs)} pairs")
    run.progress(2, 2)
    n = len(merged)
    return (
        f"{n} look-alike pair{'s' if n != 1 else ''} merged by themselves (Undo below), "
        f"{len(pairs)} unsure pair{'s' if len(pairs) != 1 else ''} asked"
    )


def garden_step(run: Run) -> str:
    ig = _module(run.app, "integrate", "Concept graph")
    if not ig.setting("garden"):
        raise Skip("integrate.garden is off")
    ig.garden_halt = run.stop
    ig.garden_last = {}
    try:
        ig.garden_start()
        t = getattr(ig, "_garden_t", None)
        while t is not None and t.is_alive():
            if run.wait(0.5):
                t.join(timeout=60)
                break
    finally:
        ig.garden_halt = None  # tomorrow's garden isn't stopped by this run's stop
    out = getattr(ig, "garden_last", None) or {}
    ids = list(out.get("jobs") or [])
    run.progress(0, len(ids))
    while ids and not run.stop.is_set():
        open_ = [j for j in ids if (job := run.app.jobs.get(j)) is not None and job.status in ("queued", "running")]
        run.progress(len(ids) - len(open_), len(ids))
        if not open_ or run.wait():
            break
    n = len(ids)
    said = f"{n} note{'s' if n != 1 else ''} sent to be linked"
    if run.stop.is_set():
        said += " (stopped; requests already asked for still finish, /jobs cancels them)"
    return said


STEPS: tuple[Step, ...] = (
    Step("books", "Books", "pages", books_step),
    Step("inbox", "Inbox", "pass", inbox_step),
    Step("graph", "Concept graph", "batches", graph_step),
    Step("same", "Look-alike notes", "parts", same_step),
    Step("garden", "Garden", "notes", garden_step),
)


# ------------------------------------------------------------------------------------------------ starting it
def current(app: App) -> Run | None:
    r = getattr(app, "_runall", None)
    return r if r is not None and not r.finished else None


def start(
    app: App, watch: Callable[[Run, bool], None] | None = None, steps: tuple[Step, ...] | None = None
) -> Run | None:
    """Start a run on a thread of its own; None when one is running already."""
    with _start:
        if current(app) is not None:
            return None
        run = Run(app, list(steps if steps is not None else STEPS), watch=watch)
        app._runall = run  # noqa: SLF001

    def go():
        try:
            run.go()
        finally:
            run.finished = True
            app.events.emit("runall_done", stopped=run.stop.is_set(), steps=len(run.results))
            if watch:
                watch(run, True)

    run.thread = threading.Thread(target=go, name="runall", daemon=True)
    run.thread.start()
    return run


def _telegram(app: App, msg: Incoming, first) -> Callable[[Run, bool], None]:
    """Progress for the message's own chat: Telegram edits the first reply (at most every EDIT_EVERY seconds, and at
    each step's end); where it can't (the phone app's chat, an edit refused), one message per step. The summary comes
    as its own message, with the Undo buttons of what merged by itself."""
    from kurooto.core.notify import Message

    state = {"at": 0.0, "edit": msg.via == "telegram" and first is not None, "told": 0}

    def watch(run: Run, step_end: bool) -> None:
        if run.finished:
            if state.get("summary"):
                return
            state["summary"] = True
            msg.reply(run.summary(), buttons=run.buttons or None)
            return
        t = time.monotonic()
        if state["edit"] and (step_end or t - state["at"] >= EDIT_EVERY):
            state["at"] = t
            if app.notifier.edit(first, Message(text="Run all:\n" + run.text(), kind="result")):
                return
            state["edit"] = False
        if step_end and not state["edit"] and len(run.results) > state["told"]:
            state["told"] = len(run.results)
            name, what = run.results[-1]
            msg.reply(f"Run all, {name}: {what}")

    return watch


def command(app: App, msg: Incoming, arg: str) -> str | None:
    """/run all, /run all status, /run all stop."""
    words = (arg or "").strip().lower().split()
    if not words or words[0] != "all":
        return "Usage: /run all (every nightly process that's on, now), /run all status, /run all stop."
    sub = words[1] if len(words) > 1 else ""
    run = current(app)
    if sub == "status":
        if run is not None:
            return "Running:\n" + run.text()
        last = getattr(app, "_runall", None)
        return ("Nothing running. Last run: " + last.summary()) if last is not None else "Nothing running."
    if sub == "stop":
        if run is None:
            return "Nothing running."
        run.stop.set()
        return "Stopping: " + run.line() + "\nThe step running stops at its next safe point; the rest don't start."
    if sub:
        return "Usage: /run all, /run all status, /run all stop."
    if app.settings.get("runall.on") is False:
        return "Run all is off (runall.on)."
    if run is not None:
        return "Already running:\n" + run.text() + "\n/run all stop stops it."
    names = ", ".join(s.name for s in STEPS)
    head = f"Running everything that's on, in order: {names}. /run all status shows where it is, /run all stop stops."
    first = msg.reply(head) if msg.via != "terminal" else None
    watch = None if msg.via == "terminal" else _telegram(app, msg, first)
    if start(app, watch) is None:
        return "Already running."
    return head if msg.via == "terminal" else None
