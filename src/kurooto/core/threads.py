"""Open threads: a small list of what you're in the middle of, so "did I finish that thing?" has an answer.

Opens (rules, no AI; memory.threads):
    said      a sentence of yours saying you'll do something ("I'll send the draft tonight", "I need to reply to Lena's
              email", "I'm going to finish the problem set"), in a message (Telegram, the app, the terminal) or on a
              call (your lines, when its transcript is kept: a call's gist records what its tools did, not your words)
    started   a task you started: a study session (/study), a deadline you gave progress on ("ps3 4/7")
Closes:
    done      you say it's done ("I sent the draft", "that thing is done"), the study session ends, the deadline is
              done or dropped
    dropped   /threads drop 2, or its Drop button
    expired   nobody touched it for memory.thread_days (7), nightly
A sentence with a health, money or password detail never opens one (modules/remember.py's rules). Nothing is sent
when a thread opens or closes: /threads shows them, with Done and Drop, and Undo on what closed in the last 48 hours.

"That thing": "did I finish that thing?", "what was that thing?", "that thing is done" look at threads opened or
changed in the last 48 hours, narrowed by any other words you used ("did you finish that thing?" also looks at your
AI requests). One answers; two or more ask once, with a button each. A thread found that way is only read or asked
about: Kurooto never sends, moves or deletes anything for it without asking you first (the AI is told the same,
core/assembler.py).

Kept in the memory ledger (core/ledger.py), encrypted, as rows of kind "thread" (sub: open, done, dropped, expired).
"""

from __future__ import annotations

import datetime as dt
import re
import time
from typing import TYPE_CHECKING

from kurooto.core import ledger
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "memory",
    {
        "threads": True,  # what you say you'll do (in chats and on calls) and tasks you start become open threads
        "thread_days": 7,  # an open thread nobody touched closes by itself after this many days
    },
)

RECENT_S = 48 * 3600  # "that thing" looks this far back; Undo on a closed thread works this long
SHOWN = 8
INTENT = re.compile(
    r"(?i)(?:^|\b(?:ok|okay|so|and|then|but|yeah|yes)[,\s]+)(?:i'll|i will|i'm going to|im going to|i am going to|"
    r"i'm gonna|i need to|i have to|i've got to|i gotta|i must|i still (?:need|have) to|i meant to|i plan to|"
    r"i'm planning to|i want to get|let me)\s+(?P<what>[^.!?\n]{4,140})"
)
NOT_TASK = re.compile(
    r"(?i)^(?:be|being|think|see|sleep|go to (?:bed|sleep)|let you know|know|try|wait|remember|never|not|check if|"
    r"ask you|tell you|say|like|love|hate|guess|need|have|probably|maybe)\b"
)
DONE = re.compile(
    r"(?i)\b(?:i(?:'ve| have)?\s+(?:just\s+|already\s+|finally\s+)?(?:sent|submitted|finished|done|did|replied to|"
    r"answered|handed in|completed|emailed|mailed|wrote|written|booked|paid|fixed|uploaded|pushed|returned|called)|"
    r"(?:is|it's|its|that's)\s+(?:done|sent|finished|submitted|handed in)|done with|finished with)\b"
)
THING = re.compile(r"(?i)\b(?:that|the|this)(?:\s+[\w'-]+){0,3}?\s+(?:thing|stuff)\b")  # "that (wind tunnel) thing"
THING_DONE = re.compile(
    r"(?i)\b(?:is|it's|'s|was)\s+(?:done|finished|sent)\b|^(?:i(?:'ve| have)?\s+)?(?:did|done|finished|sent|"
    r"completed|submitted)\b"
)
ASK = re.compile(r"(?i)^(?:did|have|has|had) (?P<who>i|you|we)\b")
WHAT = re.compile(r"(?i)^(?:what(?:'s| is| was)|remind me what|which was)\b")
STATES = {"done": "done", "dropped": "dropped", "expired": "closed by itself (nobody touched it)"}


def on(app: App) -> bool:
    return bool(app.settings.get("memory.threads"))


def _clean(what: str) -> str:
    what = re.sub(r"\s+", " ", what).strip(" ,;:-")
    return re.sub(r"(?i)\s*(?:,\s*)?(?:ok|okay|alright|then)$", "", what)[:140]


def _all(app: App, sub: str | None = None) -> list[dict]:
    return ledger.of(app).rows(("thread",), sub=sub)


def open_threads(app: App) -> list[dict]:
    """The open threads, newest first. [] while the ledger's key can't be read."""
    try:
        return sorted(_all(app, "open"), key=lambda r: r["at"], reverse=True)
    except ledger.Locked:
        return []


def closed_between(app: App, lo: float, hi: float, how: str = "done") -> list[dict]:
    """Threads closed this way in [lo, hi), oldest first (the evening check-in's "what you did today")."""
    try:
        rows = _all(app, how)
    except ledger.Locked:
        return []
    return sorted([r for r in rows if lo <= float(r.get("closed_at") or 0) < hi], key=lambda r: r["closed_at"])


def recent(app: App, since: float | None = None) -> list[dict]:
    """Threads opened or changed in the last 48 hours (any state), newest first."""
    edge = since if since is not None else time.time() - RECENT_S
    try:
        rows = _all(app)
    except ledger.Locked:
        return []
    return sorted([r for r in rows if max(r["at"], r["upd"]) >= edge], key=lambda r: r["upd"], reverse=True)


# -------------------------------------------------------------------------------------------- opening
def add(app: App, text: str, via: str, key: str = "", due: str = "") -> int | None:
    """Open a thread (the same words already open: that one is touched instead). Its row id, or None."""
    from kurooto.modules.remember import sensitive

    text = _clean(text)
    if not text or sensitive(text):
        return None
    led = ledger.of(app)
    want = ledger.words(text)
    for r in open_threads(app):
        if (key and r.get("key") == key) or (want and ledger.words(r["text"]) == want):
            led.update(r["id"], text=text if key else r["text"])
            return r["id"]
    rid = led.add("thread", text, sub="open", via=via, key=key, due=due)
    app.events.emit("thread_opened", via=via)
    return rid


def started(app: App, text: str, key: str, via: str) -> None:
    """A task you started (a study session, progress on a deadline): one open thread per key, its words kept new."""
    if not on(app):
        return
    try:
        add(app, text, via, key=key)
    except ledger.Locked:
        pass


def finish(app: App, key: str, how: str = "done") -> int:
    """The task behind a key ended: its open thread closes. How many."""
    try:
        rows = [r for r in open_threads(app) if r.get("key") == key]
        for r in rows:
            close(app, r, how)
    except ledger.Locked:
        return 0
    return len(rows)


def close(app: App, r: dict, how: str = "done") -> None:
    ledger.of(app).update(r["id"], sub=how, closed_at=time.time(), was=r.get("sub") or "open")
    app.events.emit("thread_closed", how=how)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def _closes(app: App, sentence: str) -> dict | None:
    """ "I sent the draft": the one open thread it's about (most shared words, at least two, or all of a short one)."""
    if not DONE.search(sentence) or THING.search(sentence) or sentence.rstrip().endswith("?"):
        return None
    said = ledger.words(sentence)
    scored = []
    for r in open_threads(app):
        want = ledger.words(r["text"])
        hit = len(said & want)
        if want and hit >= min(2, len(want)):
            scored.append((hit, r))
    scored.sort(key=lambda x: -x[0])
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None  # none, or two equally: left alone
    return scored[0][1]


def observe(app: App, text: str, via: str = "chat") -> list[str]:
    """Look at what you said (a message, your lines on a call): what it says you'll do opens a thread, what it says
    you did closes one. Nothing is sent. The threads opened."""
    if not text or not on(app) or text.lstrip().startswith("/"):
        return []
    opened = []
    try:
        for s in _sentences(text):
            hit = _closes(app, s)
            if hit is not None:
                close(app, hit, "done")
                continue
            if s.endswith("?"):
                continue
            m = INTENT.search(s)
            if not m or NOT_TASK.match(m["what"]) or re.match(r"(?i)remind me\b|call me\b", s):
                continue
            from kurooto.modules.text import when_from

            when = when_from(s)
            if add(app, m["what"], via, due=when.isoformat() if when else "") is not None:
                opened.append(_clean(m["what"]))
    except ledger.Locked:
        return []
    except Exception as e:  # never in the way of the message it came with
        app.events.emit("threads_failed", error=f"{type(e).__name__}: {e}"[:200])
    return opened


def from_call(app: App, lines: list[dict]) -> list[str]:
    """A call's transcript as it's kept (modules/calls:Calls.save_transcript): your lines are read like messages,
    so "I'll send the draft tonight" said on a call opens a thread."""
    ai = app.name
    yours = [str(x.get("text") or "") for x in lines if x.get("who") not in (ai, "(note)")]
    return observe(app, "\n".join(yours), via="call")


# -------------------------------------------------------------------------------------------- closing
def expire(app: App, t: float | None = None) -> int:
    """(nightly) Open threads nobody touched for memory.thread_days close by themselves. How many."""
    try:
        days = max(0.0, float(app.settings.get("memory.thread_days") or 0))
    except (TypeError, ValueError):
        days = 0.0
    if not days:
        return 0
    edge = (t or time.time()) - days * 86400
    old = [r for r in open_threads(app) if r["upd"] < edge]
    for r in old:
        close(app, r, "expired")
    return len(old)


def forget(app: App, lo: float, hi: float) -> int:
    """(core/retention.py) Threads opened in [lo, hi) go."""
    return ledger.of(app).drop("thread", lo, hi)


# ---------------------------------------------------------------------------------------- "that thing"
def _when(r: dict) -> str:
    return ledger.when_text(float(r.get("closed_at") or r["at"]))


def _state(r: dict) -> str:
    if r.get("job"):
        return r["state"]
    if r["sub"] == "open":
        return "It's still open."
    return f"It's {STATES.get(r['sub'], r['sub'])} ({_when(r)})."


def _requests(app: App, since: float) -> list[dict]:
    """Your own AI requests of the last 48 hours, as candidates for "did you finish that thing?"."""
    out = []
    for j in app.jobs.recent(20):
        if j.lane != "you" or j.created < since or not j.title or j.title == "(forgotten)":
            continue
        state = {
            "ok": f"Answered ({ledger.when_text(j.created)}).",
            "failed": "It didn't get an answer; send it again if you still want it.",
            "queued": "It's waiting its turn (/jobs).",
            "running": "I'm on it now (/jobs).",
        }.get(j.status, j.status)
        out.append({"job": j.id, "text": j.title, "at": j.created, "upd": j.created, "state": state})
    return out


def resolve(app: App, text: str) -> list[dict]:
    """What "that thing" in this message can mean: threads (and, for "did you ...", your AI requests) from the last
    48 hours, the ones sharing the most of its other words first, else the newest first."""
    since = time.time() - RECENT_S
    found = recent(app, since)
    m = ASK.match(text.strip())
    if m and m["who"].lower() == "you":
        found += _requests(app, since)
    rest = ledger.words(text) - {"finish", "finished", "did", "done", "sent", "send", "mean"}
    if rest:
        scored = [(len(rest & ledger.words(r["text"])), r) for r in found]
        best = max((s for s, _ in scored), default=0)
        if best:
            found = [r for s, r in scored if s == best]
    return sorted(found, key=lambda r: r["upd"], reverse=True)


def _said_of(r: dict) -> str:
    return "your AI request" if r.get("job") else ledger.said(r)


def _answer(r: dict) -> tuple[str, list | None]:
    """One thing, read only: what it is, where it came from and how it stands; buttons only change the thread."""
    text = f'That\'s "{r["text"]}" ({_said_of(r)}). {_state(r)}'
    if r.get("job") or r["sub"] != "open":
        return text, None
    return text, [[("Done", f"thr:{r['id']}:done"), ("Drop", f"thr:{r['id']}:drop")]]


def _which(found: list[dict], act: str = "show") -> list:
    rows = []
    for r in found[:4]:
        ref = r["job"] if r.get("job") else r["id"]
        rows.append([(r["text"][:40], f"thr:{ref}:{act}")])
    return rows


def intent(app: App, text: str) -> tuple[str, list | None] | None:
    """ "did I finish that thing?", "what was that thing?", "that thing is done": answered from the threads of the last
    48 hours; two or more ask once which. None when it isn't one."""
    t = text.strip()
    if not THING.search(t):
        return None
    done = bool(THING_DONE.search(t)) and not t.endswith("?")
    if not (done or ASK.match(t) or WHAT.match(t)):
        return None
    if ledger.locked(app):
        return ledger.LOCKED, None
    found = resolve(app, t)
    if done:
        found = [r for r in found if not r.get("job") and r["sub"] == "open"]
    if not found:
        return "Nothing open from the last 48 hours that fits. /threads lists what you're in the middle of.", None
    if len(found) > 1:
        what = "Which one is done?" if done else "Which one do you mean? These are from the last 48 hours:"
        return what, _which(found, "done" if done else "show")
    r = found[0]
    if done:
        close(app, r, "done")
        return f'Closed "{r["text"]}" ({_said_of(r)}).', [[("Undo", f"thr:{r['id']}:undo")]]
    return _answer(r)


# ------------------------------------------------------------------------------------------- /threads
def command(app: App, arg: str) -> tuple[str, list | None]:
    """/threads: what's open, newest first and numbered, with Done and Drop; what closed in the last 48 hours, with
    Undo. /threads done 2, /threads drop 2, /threads all (closed ones too)."""
    arg = (arg or "").strip().lower()
    if ledger.locked(app):
        return ledger.LOCKED, None
    items = open_threads(app)
    m = re.fullmatch(r"(done|drop|close)\s+(\d{1,3})", arg)
    if m:
        n = int(m.group(2))
        if not 1 <= n <= len(items):
            return f"There's no open thread {n}; /threads shows them with their numbers.", None
        r = items[n - 1]
        how = "done" if m.group(1) == "done" else "dropped"
        close(app, r, how)
        return f'{"Done" if how == "done" else "Dropped"}: "{r["text"]}".', [[("Undo", f"thr:{r['id']}:undo")]]
    since = 0 if arg == "all" else time.time() - RECENT_S
    shut = [r for r in recent(app, since) if r["sub"] != "open"][:SHOWN]
    if not items and not shut:
        why = "" if on(app) else " (memory.threads is off)"
        return (
            f"Nothing open{why}. When you say you'll do something (\"I'll send the draft tonight\"), in a chat or on a "
            "call, or start a task, it shows up here until it's done.",
            None,
        )
    lines, buttons = [], []
    if items:
        lines.append("What you're in the middle of:")
        for i, r in enumerate(items[:SHOWN], 1):
            due = f", by {dt.datetime.fromisoformat(r['due']):%a %H:%M}" if r.get("due") else ""
            lines.append(f"{i}. {r['text']} ({ledger.said(r)}{due})")
            buttons.append([(f"Done {i}", f"thr:{r['id']}:done"), (f"Drop {i}", f"thr:{r['id']}:drop")])
        if len(items) > SHOWN:
            lines.append(f"…and {len(items) - SHOWN} more (/threads done 9 works on them too)")
    if shut:
        lines.append("\nClosed" + (":" if arg == "all" else " in the last 48 hours:"))
        for r in shut:
            lines.append(f"- {r['text']}: {STATES.get(r['sub'], r['sub'])}, {_when(r)}")
            if time.time() - float(r.get("closed_at") or 0) < RECENT_S and len(buttons) < SHOWN + 3:
                buttons.append([(f"Undo: {r['text'][:30]}", f"thr:{r['id']}:undo")])
    return "\n".join(lines)[:3800], buttons or None


def button(app: App, ref: str, act: str) -> str:
    """thr:<row>:done|drop|undo|show, thr:<job>:show. They change the thread itself, never anything outside it."""
    if ref.startswith("j"):
        j = next((x for x in _requests(app, 0) if x["job"] == ref), None)
        text = f'Your request "{j["text"]}": {j["state"]}' if j else "That request isn't remembered any more."
        app.notify(text, why="asked")
        return text[:190]
    try:
        r = ledger.of(app).get(int(ref))
    except (ValueError, ledger.Locked):
        r = None
    if r is None or r["kind"] != "thread":
        return "That thread isn't remembered any more."
    if act == "show":
        text, buttons = _answer(r)
        app.notify(text, why="asked", buttons=buttons)
        return text[:190]
    if act == "undo":
        if r["sub"] == "open":
            return "It's open already."
        ledger.of(app).update(r["id"], sub="open", closed_at=None)
        app.events.emit("thread_reopened")
        return f'Open again: "{r["text"]}".'[:190]
    if act in ("done", "drop"):
        if r["sub"] != "open":
            return f"It's {STATES.get(r['sub'], r['sub'])} already."
        close(app, r, "done" if act == "done" else "dropped")
        return f'{"Done" if act == "done" else "Dropped"}: "{r["text"]}". /threads has Undo.'[:190]
    return "unknown button"


__all__ = ["on", "observe", "from_call", "started", "finish", "expire", "forget", "resolve", "intent", "command"]
