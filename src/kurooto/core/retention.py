"""Retention: what Kurooto keeps of your conversations is forgotten after privacy.keep_days, when you set it (0, the
default, keeps it), and /forget forgets a stretch of it now.

What it covers, all in Kurooto's own folders (your notes folder is never touched):

    calls       call transcripts (state/calls/transcripts/), calls that went on as text (calls/textcalls.json) and
                what calls searched your notes for (calls/searches.json, 8 days at most: modules/curious.py)
    requests    what was asked and answered in finished AI requests (jobs.db: the row stays, without its words, for
                /usage and the Space keeper) and long answers kept as files (jobs/<id>-result.md)
    chats       Chat's recent turns (chat/history.json)
    questions   answered and expired questions (ask/; ask.keep_days when you set it)
    cases       Wrong-button cases you didn't make test cases (cases/; cases.keep_days when you set it)
    messages    the words of messages that came by themselves (calm.db keeps when and why for 45 days)
    index       the search index of past requests, calls and chats (Learns from its own work)
    threads     what you were in the middle of (core/threads.py), by when each opened
    logs        log lines (logs/), by their time; a log file with no times goes by when it was last written

Voice notes keep nothing here: the recording is saved in your notes' inbox (yours, so never removed) and what was
heard becomes your message. The event log (events.jsonl) is left alone: it holds counts and names, never what you
typed or what was answered, and other features learn from it over weeks. The call line's queue (what it holds while
the computer is off) is handed over and emptied each time the computer connects, so nothing waits there to expire.

Every day at 04:15 (or on waking, if the computer slept through it) what's older than keep_days goes. /forget 7d
(2w, 12h) forgets the last stretch now; /forget all forgets everything, after a confirm button. Each says how many of
each kind went. keep_days 0 keeps everything until you forget it.

Nothing is simply dropped: like memory, a call, a request or a chat settles into a one-line gist of what it decided
or did (core/gists.py, privacy.keep_gist), and the daily job lets its words fade only once that gist exists (a gist
that couldn't be made keeps the words until the next night). /forget 7d still removes the words now and keeps the
gists; /forget all asks whether the gists go too.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import gists, threads
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.config import Settings

register_defaults(
    "privacy",
    {
        "keep_days": 0,  # transcripts, AI requests and answers, chats and logs go after this many days (0: kept)
    },
)

WHEN = "daily 04:15"
END = 1e18  # "until now and later": the end of a stretch that runs to the present
CONFIRM_S = 600  # the Forget everything button works this long
KINDS = {  # kind -> (one, many)
    "calls": ("call transcript", "call transcripts"),
    "requests": ("AI request", "AI requests"),
    "chats": ("chat turn", "chat turns"),
    "questions": ("question", "questions"),
    "cases": ("case", "cases"),
    "messages": ("message I sent", "messages I sent"),
    "index": ("search index item", "search index items"),
    "threads": ("thread", "threads"),
    "logs": ("log file", "log files"),
    "mind": ("thing Brain kept", "things Brain kept"),
}
SPAN = re.compile(r"^(\d{1,5})\s*(h|hours?|d|days?|w|weeks?)$")
STAMP = re.compile(rb"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")  # a log line's time (daemon.py:setup_logging)
TRANSCRIPT = re.compile(r"^(\d{4}-\d{2}-\d{2}-\d{6})")


TIDY = {"ask": 30, "cases": 30}  # settled questions and Wrong cases were always tidied after 30 days; they still are


def days(settings: Settings, section: str = "") -> float:
    """How many days to keep: the section's own keep_days when you set one (ask, cases), else privacy.keep_days, else
    the section's old tidy-up (TIDY). 0: keep."""
    own = settings.get(f"{section}.keep_days") if section else None
    try:
        return max(0.0, float(own or settings.get("privacy.keep_days") or TIDY.get(section, 0)))
    except (TypeError, ValueError):
        return float(TIDY.get(section, 0))


def _in(t: float | None, lo: float, hi: float) -> bool:
    return t is not None and lo <= t < hi


def _mtime(p: Path) -> float | None:
    try:
        return p.stat().st_mtime
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------- each kind
def _calls(app: App, lo: float, hi: float) -> int:
    d = Path(app.paths.state) / "calls"
    n = 0
    for f in sorted((d / "transcripts").glob("*.txt")) if (d / "transcripts").is_dir() else []:
        m = TRANSCRIPT.match(f.stem)
        try:
            t = dt.datetime.strptime(m.group(1), "%Y-%m-%d-%H%M%S").timestamp() if m else _mtime(f)
        except ValueError:
            t = _mtime(f)
        if _in(t, lo, hi):
            f.unlink(missing_ok=True)
            gists.drop_did(f)
            n += 1
    tc = d / "textcalls.json"
    if tc.exists():
        with Lock(app.paths.state, "calls-textcall"):  # modules/calls/fallback.py:TextCall
            convs = jload(tc, {}) or {}
            gone = [
                k
                for k, c in convs.items()
                if isinstance(c, dict) and c.get("state") != "open" and _in(float(c.get("last") or 0), lo, hi)
            ]
            if gone:
                jsave(tc, {k: c for k, c in convs.items() if k not in gone})
        n += len(gone)
    sf = d / "searches.json"
    if sf.exists():
        rows = jload(sf, []) or []
        keep = [r for r in rows if not (isinstance(r, dict) and _in(float(r.get("at") or 0), lo, hi))]
        if len(keep) != len(rows):
            jsave(sf, keep)
    return n


def _requests(app: App, lo: float, hi: float) -> int:
    n = app.jobs.forget(lo, hi)
    d = Path(app.paths.state) / "jobs"
    for f in d.glob("*-result.md") if d.is_dir() else []:
        if _in(_mtime(f), lo, hi):
            f.unlink(missing_ok=True)
    return n


def _chats(app: App, lo: float, hi: float) -> int:
    f = Path(app.paths.state) / "chat" / "history.json"
    turns = (jload(f, []) or []) if f.exists() else []
    keep = [t for t in turns if not (isinstance(t, dict) and _in(float(t.get("at") or 0), lo, hi))]
    if len(keep) != len(turns):
        jsave(f, keep)
    return len(turns) - len(keep)


def _cases(app: App, lo: float, hi: float) -> int:
    from kurooto.modules.cases import Store

    return Store(app.paths.state).forget(lo, hi)


def _index(app: App, lo: float, hi: float) -> int:
    from kurooto.modules import learning

    return learning.forget(app, lo, hi) if learning.index_file(app).exists() else 0


def _logs(app: App, lo: float, hi: float) -> int:
    d = Path(app.paths.logs)
    n = 0
    for f in sorted(d.iterdir()) if d.is_dir() else []:
        if f.is_file() and not f.is_symlink() and trim_log(f, lo, hi):
            n += 1
    return n


def trim_log(f: Path, lo: float, hi: float) -> bool:
    """Take the lines from [lo, hi) out of a log, in place (the program writing it keeps appending); a line without a
    time of its own (a traceback) goes with the line before it. A log with no times at all goes by when it was last
    written. Rotated copies (kurooto.log.1) that end up empty are removed. True if it changed."""
    data = f.read_bytes()
    lines = data.splitlines(keepends=True)
    keep, t, stamped = [], None, False
    for ln in lines:
        m = STAMP.match(ln)
        if m:
            stamped = True
            try:
                t = time.mktime(time.strptime(m.group(1).decode(), "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                t = None
        if not _in(t, lo, hi):
            keep.append(ln)
    if not stamped:
        keep = [] if _in(_mtime(f), lo, hi) and data else lines
    if len(keep) == len(lines):
        return False
    if not keep and f.suffix != ".log":
        f.unlink(missing_ok=True)
    else:
        f.write_bytes(b"".join(keep))
    return True


def _mind(app: App, lo: float, hi: float) -> int:
    """What Brain kept from the span, in every one of its stores (mind/forgetting.py)."""
    from kurooto.mind import forgetting

    return forgetting.forget_span(app, lo, hi)


STEPS = {
    "calls": _calls,
    "requests": _requests,
    "chats": _chats,
    "questions": lambda app, lo, hi: app.ask.forget(lo, hi),
    "cases": _cases,
    "messages": lambda app, lo, hi: app.calm.forget(lo, hi),
    "index": _index,
    "threads": lambda app, lo, hi: threads.forget(app, lo, hi),
    "logs": _logs,
    "mind": lambda app, lo, hi: _mind(app, lo, hi),
}


def forget(
    app: App,
    lo: float,
    hi: float = END,
    kinds: tuple[str, ...] = tuple(KINDS),
    gist: bool = True,
    settle: bool = False,
) -> dict[str, int]:
    """Forget what was kept from [lo, hi) (times in seconds), kind by kind; one kind failing never stops the rest.
    gist: calls, requests and chats leave their gists first (core/gists.py; privacy.keep_gist). settle (the daily
    job): a kind whose gists couldn't be made keeps its words until next time. {kind: how many}."""
    out: dict[str, int] = {}
    for kind in kinds:
        if gist:
            try:
                gists.keep(app, kind, lo, hi)
            except Exception as e:
                app.events.emit("gist_failed", what=kind, error=f"{type(e).__name__}: {e}"[:300])
                if settle:  # the words fade only once their gist exists
                    continue
        try:
            out[kind] = int(STEPS[kind](app, lo, hi) or 0)
        except Exception as e:
            app.events.emit("retention_failed", what=kind, error=f"{type(e).__name__}: {e}"[:300])
    return out


def expire(app: App, now: float | None = None) -> dict[str, int]:
    """The daily job: what's older than privacy.keep_days goes (questions and cases by their own keep_days if set).
    Counts only in the event log."""
    now = now or time.time()
    out: dict[str, int] = {}
    keep = days(app.settings)
    if keep:
        out = forget(
            app, 0, now - keep * 86400, tuple(k for k in KINDS if k not in ("questions", "cases")), settle=True
        )
    for kind in ("questions", "cases"):
        own = days(app.settings, "ask" if kind == "questions" else kind)
        if own:
            out.update(forget(app, 0, now - own * 86400, (kind,)))
    app.events.emit("retention_expired", **{k: v for k, v in out.items() if v})
    try:
        gists.expire(app, now)  # gists are kept for good unless you give them a time (privacy.gist_days)
    except Exception as e:
        app.events.emit("retention_failed", what="gists", error=f"{type(e).__name__}: {e}"[:300])
    return out


def summary(counts: dict[str, int]) -> str:
    parts = [f"{n} {KINDS[k][0 if n == 1 else 1]}" for k, n in counts.items() if n]
    if not parts:
        return "Nothing was kept from then."
    return "Forgot " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."


def span(arg: str) -> float | None:
    """ "7d", "2w", "12h", "3 days": seconds; None if it isn't one."""
    m = SPAN.match(arg.strip().lower())
    if not m or not int(m.group(1)):
        return None
    return int(m.group(1)) * {"h": 3600, "d": 86400, "w": 7 * 86400}[m.group(2)[0]]


# ----------------------------------------------------------------------------------------------- /forget
def gists_kept(app: App) -> str:
    g = app.settings.get("privacy.gist_days")
    return (
        " As their words fade, calls, requests and chats settle into a one-line gist of what they decided, kept "
        + (f"{g} days" if g else "until /forget all")
        + " (/gists)."
    )


def command(app: App, arg: str) -> tuple[str, list | None]:
    """/forget 7d (2w, 12h): forget that much now. /forget all: everything, after a confirm button. /forget alone:
    what's kept and for how long."""
    arg = (arg or "").strip().lower()
    if arg in ("all", "everything"):
        text = (
            "Forget everything I've kept of our conversations: call transcripts, AI requests and answers, chats, "
            "answered questions, cases, the words of messages I sent, the search index, your open threads and the "
            "logs? Your notes stay. This can't be undone."
        )
        asked = int(time.time())
        if gists.on(app) or gists.load(app):  # one line of what each decided (core/gists.py): keep those?
            text += " The gists (one line of what each call or request decided, /gists) can stay or go too."
            return text, [
                [("Forget all, keep gists", f"fgt:{asked}:all"), ("Forget gists too", f"fgt:{asked}:gists")],
                [("Keep it", "fgt:0:no")],
            ]
        return text, [[("Forget everything", f"fgt:{asked}:all"), ("Keep it", "fgt:0:no")]]
    secs = span(arg) if arg else None
    if secs is None:
        keep = days(app.settings)
        kept = f"for {keep:g} days (privacy.keep_days)" if keep else "until you forget it (privacy.keep_days is 0)"
        return (
            f"I keep call transcripts, AI requests and answers, chats, answered questions, cases and logs {kept}. "
            "/forget 7d forgets the last 7 days now (also 12h, 2w); /forget all forgets everything (it asks first). "
            "Your notes are never touched." + (gists_kept(app) if gists.on(app) else ""),
            None,
        )
    out = summary(forget(app, time.time() - secs))
    app.events.emit("retention_forgot", span=arg)
    return out, None


def button(app: App, ref: str, act: str) -> str:
    """The confirm buttons under /forget all ("fgt:<when asked>:all", "fgt:<when asked>:gists" (the gists go too),
    "fgt:0:no")."""
    if act not in ("all", "gists"):
        return "Kept."
    try:
        asked = float(ref)
    except ValueError:
        asked = 0
    if time.time() - asked > CONFIRM_S:
        return "That button has run out; send /forget all again."
    out = summary(forget(app, 0, gist=act == "all"))
    if act == "gists":
        n = gists.clear(app)
        if n:
            gone = f"{n} gist{'s' if n != 1 else ''}"
            out = f"{out[:-1]} and {gone}." if out.startswith("Forgot") else f"Forgot {gone}."
    app.events.emit("retention_forgot", span="all" if act == "all" else "all+gists")
    app.notify(out, why="asked")
    return out[:190]


def start(app: App) -> None:
    async def daily(payload: dict | None = None) -> dict:
        return await asyncio.to_thread(expire, app)

    app.scheduler.action("retention.expire", daily)
    app.scheduler.every("retention:expire", WHEN, "retention.expire", module="retention", misfire="coalesce")


__all__ = ["days", "forget", "expire", "summary", "span", "command", "button", "start"]
