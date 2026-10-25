"""The context assembler: what one AI reply (or one call) is told of what Kurooto remembers, within a budget.

For your own AI requests (lane "you": chat, the terminal, the dashboard, a task from a call), core/jobs.py adds what
this builds to the request's context (providers/context.py), and the run receipt says "used 2 remembered items". It
holds, in this order and at most memory.budget_tokens (600, about 4 characters a token):

    open threads           what you're in the middle of (core/threads.py) that the message is about
    remembered items       gists (of faded conversations, and of what's still kept from the last 3 days), meetings and
                           daily notes from the memory ledger (core/ledger.py) that share its words

Only when the message refers to past things ("last time", "on the call", "yesterday", "that thing", "did I ...",
"as we said", a weekday) or shares at least two words with an open thread; otherwise nothing goes. Picked by rules:
shared words count most, then the subject (a course the message names), then a day it names, then how recent. Gists
only, never transcripts; each item says where it's from ("call at 07:56 today"), so a reply can say "as we said on
the call at 07:56". A "that thing" the message points at is named, with the rule that it's only read or asked about,
never acted on (sent, moved, deleted) without asking first.

A call's brief (modules/calls:Calls.pending) gets the open threads and the gists of the last day the same way.
memory.recall off: nothing is added anywhere.
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
        "recall": True,  # AI replies and calls are told the few remembered items your message refers to
        "budget_tokens": 600,  # at most about this much of what's remembered goes with one AI reply or call
    },
)

CHARS_PER_TOKEN = 4
ITEM_MAX = 240  # one remembered item, at most
LOOK_DAYS = 60  # remembered items older than this aren't offered (open threads always are)
PAST = re.compile(
    r"(?i)\b(?:last time|earlier|again|yesterday|last (?:week|night|month|\w+day)|on (?:the|our|that) call|the call|"
    r"we (?:said|talked|discussed|agreed|decided|spoke|planned)|as (?:i|we|you) said|you said|i said|i told you|"
    r"remember|recall|that thing|the thing|where (?:was|were) (?:i|we)|pick up where|carry on|continue|follow(?:ing)? "
    r"up|did i|have i|when did|what did|what was|the draft|that (?:email|draft|plan|idea|task|meeting)|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day)\b"
)
HEAD = (
    "What {name} remembers that may bear on this (one-line gists from its memory, never transcripts; use only what "
    'helps, and say where it\'s from when you use it, e.g. "as we said on the call at 07:56"):'
)
THAT = re.compile(r"(?i)\b(?:that|this)(?:\s+[\w'-]+){0,2}?\s+(?:thing|stuff)\b")  # "that thing", "that draft thing"
GUARD = (
    '"That thing" most likely means: {what}. Read it or ask about it only: never send, move or delete anything for it '
    "without asking them first."
)


def _subject_words(app: App, text: str) -> set[str]:
    """The words of the courses the message names (Subjects), so rows about that course rank higher."""
    s = app.modules.get("subjects")
    if s is None or not app.is_on("subjects"):
        return set()
    try:
        return set().union(*(ledger.words(s.name_of(slug)) for slug in s.find_in(text)))
    except Exception:
        return set()


def pick(app: App, text: str, call: bool = False) -> list[tuple[str, dict]]:
    """The remembered items for this message, best first: (line, row). call=True: a call's brief (the open threads,
    and the gists of the last day)."""
    t = time.time()
    said = ledger.words(text)
    cue = bool(PAST.search(text or ""))
    from kurooto.core import threads

    thing = bool(THAT.search(text or ""))
    day = ledger.a_past_day(text) if cue and not call else None
    subj = _subject_words(app, text) if text else set()
    out = []
    for r in threads.open_threads(app):
        hit = len(said & ledger.words(r["text"]))
        if call or hit >= 2 or (cue and hit) or thing:
            out.append((3 * hit + 2 + 1 / (1 + (t - r["upd"]) / 86400), r))
    if call or cue:
        lo = t - (86400 if call else LOOK_DAYS * 86400)
        rows = [
            r
            for r in ledger.everything(app, live_days=1 if call else ledger.LIVE_DAYS)
            if r["kind"] in ("gist", "meeting", "day") and r["at"] >= lo
        ]
        for r in rows:
            mine = ledger.words(r["text"])
            hit = len(said & mine)
            on_day = day is not None and dt.datetime.fromtimestamp(r["at"]).date() == day
            if not (call or hit or on_day):
                continue
            if call and r["kind"] != "gist":
                continue
            score = 3 * hit + 2 * len(subj & mine) + 2 * on_day + 1 / (1 + (t - r["at"]) / (7 * 86400))
            out.append((score, r))
    out.sort(key=lambda x: -x[0])
    return [(f"- {ledger.label(r)}: {_one(r['text'])}", r) for _, r in out]


def _one(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= ITEM_MAX else text[: ITEM_MAX - 1].rstrip() + "…"


def budget(app: App) -> int:
    """The budget, in characters."""
    try:
        return max(0, int(app.settings.get("memory.budget_tokens") or 0)) * CHARS_PER_TOKEN
    except (TypeError, ValueError):
        return 600 * CHARS_PER_TOKEN


def build(app: App, text: str) -> tuple[str, int]:
    """What an AI reply to this message is told: (the block, how many remembered items it holds). ("", 0) when the
    message doesn't refer to anything remembered."""
    if not app.settings.get("memory.recall"):
        return "", 0
    left = budget(app)
    parts: list[str] = []
    # the persona card goes into every AI request already (providers/context.py, core/persona.py), not here
    picked = pick(app, text)
    lines: list[str] = []
    if picked:
        head = HEAD.format(name=app.name)
        left -= len(head) + 1
        thing = THAT.search(text or "")
        open_ = [r for _, r in picked if r["kind"] == "thread" and r["sub"] == "open"]
        guard = GUARD.format(what=f'"{open_[0]["text"]}"') if thing and len(open_) == 1 else ""
        if thing and len(open_) > 1:
            guard = GUARD.format(what="one of the open threads below; ask them which before anything else")
        left -= len(guard) + 1 if guard else 0
        for line, _r in picked:
            if len(line) + 1 > left:
                continue  # a shorter one further down may still fit
            lines.append(line)
            left -= len(line) + 1
        if lines:
            parts += [head, *lines] + ([guard] if guard else [])
    return "\n".join(parts), len(lines)


def for_request(app: App, job) -> tuple[str, int]:
    """(core/jobs.py) The block for one AI request: your own requests only, from the words you wrote (a chat's
    history around them isn't what you asked now). Never stands in the way of the request."""
    if getattr(job, "lane", "you") != "you":
        return "", 0
    text = (job.prompt or "").split("Current request:\n", 1)[-1]
    try:
        block, n = build(app, text)
        from kurooto.mind.tom import knowledge

        hint = knowledge.hint(app, text)  # how well they know what this names (Brain's model of their mind)
        return (block + "\n" + hint).strip() if hint else block, n
    except ledger.Locked:
        return "", 0
    except Exception as e:
        app.events.emit("recall_failed", error=f"{type(e).__name__}: {e}"[:200])
        return "", 0


def call_brief(app: App) -> dict:
    """(modules/calls:Calls.pending) The open threads and the gists of the last day, within the budget, so a call can
    pick up what was said in a chat or on the call before."""
    if not app.settings.get("memory.recall"):
        return {}
    left, out = budget(app), {"open_threads": [], "earlier": []}
    for line, r in pick(app, "", call=True):
        if len(line) > left:
            continue
        key = "open_threads" if r["kind"] == "thread" else "earlier"
        out[key].append(line[2:])
        left -= len(line)
    return {k: v for k, v in out.items() if v}


__all__ = ["build", "pick", "for_request", "call_brief", "budget"]
