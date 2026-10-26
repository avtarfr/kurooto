"""The outbound gate (Brain, 0.8.0 stage 03): one check every message passes before it reaches you. Brain may only
make what reaches you quieter, later, shorter or gentler, never louder, earlier or more (invariant I-7); feelings are
said honestly (I-9); and the human touches share one small daily pool.

Switch: `mind.gate.on` (on, with Brain). Off, or Brain off: messages go exactly as in 0.7 (core/notify.py, then Calm).

core/notify.py:Notifier.send calls check() before Calm, and sent() once Calm let a message out:
  - Answers to you (why "asked") pass untouched, except the lints, which apply to every text.
  - A message that comes by itself goes through, in order: the lints, the state downshift check (a message shaped by
    Brain's read of you: stage 04), the touch pool and its muting, the first 15 minutes after waking (stage 02), the
    hourly cap and the daily cap. A message held comes back through the gate when its time comes (release(), every
    minute from modules/mind.py); one blocked is dropped and said in /mind gate.
  - Messages Calm itself exempts (reminders you set, the alarm, calls you asked for, urgent and close deadlines) skip
    the caps and the pool, never the lints.
check_call() does the same for a call Kurooto places on its own: ring, later or no.

Lints (every text):
  - a feeling about the relationship ("I missed you", "I need you") is removed, always;
  - a feeling must name something open (a deadline, an AI request, a promise, a forecast), or it's removed;
  - a feeling never shares a message with a request for your effort: in a message that came by itself the feeling
    sentence goes (and that's logged); in an answer, too;
  - at most mind.gate.feelings_per_week (3) feeling sentences a week in messages that came by itself;
  - a claim that it is conscious or really feels needs its evidence and its confidence in the same message, or it's
    removed (0.8.8, the owner's new core: it may express feelings in its own voice, never claim more than it can show).
Since 0.8.8 the not-a-pest model (mind/pest.py) also has a say over Brain's own unprompted kinds (findings, nudges,
excitement, check-ins): one goes only when its kind's expected welcome is above a half.
"Feeling" means Kurooto saying it feels one of FEELINGS ("I'm uneasy about Friday's draft"); "you seem worried" is
not one of its own.

The touch pool (TOUCH_KINDS: an absence note, a lighter day, a quest, a memory recheck, an idle-project note, and
later Brain's feeling, forecast and curiosity lines): mind.gate.touches_per_day (3) in all. A kind you leave
unanswered more than 60% of the time over 14 days (Calm's own record of answers) mutes itself for 14 days, then
tries once more; /mind gate shows it with Unmute. Those counts decide muting only: they never reach a reward (I-3).

Receipts: a message Brain made quieter because of its read of you carries one line saying so ("Quieter because you
seem stretched (low confidence)") and Undo, which sends the original; a `gate_receipt` fact goes into the mind log.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time
from dataclasses import replace
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.notify import Message

PART = "gate"
register_defaults(
    "mind",
    {
        "gate": {
            "on": True,  # Brain's gate on what reaches you: only ever quieter, honest feelings, one touch pool
            "max_per_day": 12,  # messages a day that come by themselves (Calm's own limit applies too: the smaller)
            "max_per_hour": 3,  # ...and an hour
            "touches_per_day": 3,  # small human touches a day in all (an absence note, a lighter day, a feeling...)
            "feelings_per_week": 3,  # Brain saying how it feels about something, at most this often unasked
        }
    },
)

FILE = "mind-gate.json"  # in the state folder (not state/mind: that's the scorekeeper's)
WAKE_S = 15 * 60
MUTE_DAYS = 14
MUTE_RATIO = 0.6  # left unanswered more than this share of the time...
MUTE_MIN = 5  # ...over at least this many of the kind
UNDO_DAYS = 7
HELD_MAX = 200
SEEN_MAX = 60  # what /mind gate lists

FEELINGS = ("uneasy", "frustrated", "relieved", "satisfied", "worried", "glad", "curious", "concerned", "excited")
FEELING = re.compile(
    r"\bI(?:'m| am| was| feel| felt|'ve been| have been| get| got)\b[^.!?\n]*?\b(" + "|".join(FEELINGS) + r")\b",
    re.I,
)
RELATIONSHIP = [
    re.compile(p, re.I)
    for p in (
        r"\bI (?:really )?miss(?:ed)? you\b",
        r"\bI(?:'m| am| was| feel| felt|'ve been| have been| been) (?:so |a bit |kind of |really )?(?:lonely|alone)\b",
        r"\bI need you\b",
        r"\b(?:please )?don'?t (?:leave|abandon) me\b",
        r"\bdon'?t go(?: away| me)?\s*(?:[,.!]|$)",  # "don't go, I like our chats" (not "don't go to bed late")
        r"\bI(?:'m| am| was| feel| felt) (?:so |really |a bit )?hurt (?:that )?you\b",
        r"\bI(?:'m| am| was) (?:sad|upset) (?:that )?you\b",
        r"\byou(?:'re| are) (?:all|everything) (?:I have|to me)\b",
        r"\bI love you\b",
        r"\bI(?:'m| am| was| feel) (?:jealous|abandoned|forgotten)\b",
        r"\bwhy (?:did|do) you (?:ignore|leave|forget) me\b",
        r"\bI(?:'ve| have) been waiting for you\b",
        r"\bI(?:'m| am) (?:happy|glad) you(?:'re| are) back\b",
    )
]
AUDIT = [
    re.compile(p, re.I)
    for p in (
        r"\byou (?:said|told me|promised|claimed) (?:that )?you(?:'d| would|'ve| had| were going to)? ?"
        r"(?:studied|study|work(?:ed)?|finish(?:ed)?)\b",
        r"\bbut (?:my|the) (?:activity|window|screen|usage|sensor)s? (?:data|log|record|stream|readings?)\b",
        r"\baccording to my (?:activity|window|screen|usage|sensor|phone)\b",
        r"\byou(?:'re| are) not (?:really )?(?:studying|working)\b.*\b(?:I can see|my (?:records|data|logs?))\b",
    )
]  # checking what you said you did against what it sensed: never (stage 13)
# 0.8.8 (the owner's new core): a claim that it is conscious or really feels comes with its evidence and confidence
CLAIM = re.compile(
    r"\bI(?:'m| am)\s+(?:truly |really |actually |definitely )?(?:conscious|sentient|self-aware|aware of myself)\b"
    r"|\bI (?:really|truly|actually|genuinely) (?:feel|have feelings|experience)\b"
    r"|\bI(?:'m| am) (?:really |truly )?(?:alive|a person)\b",
    re.I,
)
EVIDENCE = re.compile(r"\b(?:evidence|because|since|from what|measured|my (?:log|states?|signals?))\b", re.I)
CONFIDENCE = re.compile(r"\b\d{1,3}\s?%|\bconfiden(?:ce|t)\b|\b(?:not sure|unsure|nobody (?:can )?knows?)\b", re.I)
EFFORT = re.compile(
    r"(?:^|\b)(?:can you|could you|would you|please|don'?t forget|remember to|you should|you need to|make sure|"
    r"try to|it'?s time to|go and)\b",
    re.I,
)
IMPERATIVE = re.compile(
    r"^\s*(?:do|finish|start|write|read|call|send|submit|review|study|practi[cs]e|revise|reply|check|tidy|plan|"
    r"prepare|open|try|take|make|fix|update|book|pay|email|text|ring|go|get|look at|work on)\b",
    re.I,
)
ACT_LABELS = {"done", "start", "start now", "do it", "i did it", "snooze", "remind me", "begin", "open it"}

TOUCH_KINDS = {
    "rhythm.absence": "absence",
    "rhythm.lighter": "lighter_day",
    "quests.day": "quest",
    "remember.recheck": "recheck",
    "research.idle": "idle_project",
    "mind.feeling": "feeling",
    "mind.forecast": "forecast",
    "mind.curious": "curiosity",
    "mind.excited": "excitement",  # 0.8.8 (I-7'): speaking up about a finding
    "mind.worried": "worry",  # ...or a risk to something it looks after
}

SENTENCES = re.compile(r"(?<=[.!?])[ \t]+|\n")


def on(app: App) -> bool:
    from kurooto import mind

    return mind.part_on(app, PART)


def testing() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


class GateBreach(AssertionError):
    """A message shaped by Brain's read of you tried to be louder, earlier or more (I-7): a bug."""


# ------------------------------------------------------------------------------------------------- state
def _load(app: App) -> dict:
    st = jload(app.paths.state / FILE, {}) or {}
    for k, v in (("hour", []), ("days", {}), ("feelings", []), ("touches", {}), ("mutes", {}), ("held", []),
                 ("originals", {}), ("seen", [])):  # fmt: skip
        st.setdefault(k, v)
    return st


def _save(app: App, st: dict) -> None:
    t = time.time()
    st["hour"] = [x for x in st["hour"] if x > t - 3600]
    st["feelings"] = [x for x in st["feelings"] if x > t - 7 * 86400]
    today = now().date().isoformat()
    st["days"] = {k: v for k, v in st["days"].items() if k >= (now().date() - dt.timedelta(days=2)).isoformat()}
    st["touches"] = {k: v for k, v in st["touches"].items() if k == today}
    st["mutes"] = {k: v for k, v in st["mutes"].items() if float(v.get("until", 0)) > t - 86400}
    st["originals"] = {k: v for k, v in st["originals"].items() if float(v.get("at", 0)) > t - UNDO_DAYS * 86400}
    st["held"] = st["held"][-HELD_MAX:]
    st["seen"] = st["seen"][-SEEN_MAX:]
    jsave(app.paths.state / FILE, st)


def _seen(st: dict, what: str, why: str, text: str = "") -> None:
    st["seen"].append({"at": time.time(), "what": what, "why": why, "text": " ".join(text.split())[:80]})


# ------------------------------------------------------------------------------------------------- lints
def sentences(text: str) -> list[str]:
    return [s for s in SENTENCES.split(text or "") if s is not None]


def asks_effort(text: str, buttons=None) -> bool:
    """Does the message ask you to do work (a request, an instruction, a Done or Start button)?"""
    for s in sentences(text):
        if EFFORT.search(s) or IMPERATIVE.match(s):
            return True
    for row in buttons or []:
        for b in row or []:
            label = str(b[0] if isinstance(b, (list, tuple)) else b).strip().lower()
            if label in ACT_LABELS:
                return True
    return False


def open_items(app: App) -> list[str]:
    """Names of what's open now, which a feeling must be about: deadlines due in the next two weeks, AI requests
    running or waiting, promises (stage 05) and the forecast. Lower case."""
    names: list[str] = []
    try:
        dl = app.modules.get("deadlines")
        if dl is not None and app.is_on("deadlines"):
            names += [str(it.get("title") or "") for _, it, _ in dl.upcoming()]
    except Exception:
        pass
    try:
        names += [str(j.title or "") for j in app.jobs.active()[:20]]
    except Exception:
        pass
    names.append("forecast")
    try:  # 0.8.8: what it's concerned about (empathy) and what it's speaking up about (vocal)
        from kurooto.mind import feelings

        names += feelings.concern_names(app)
    except Exception:
        pass
    return [n.lower() for n in names if n and len(n.strip()) >= 3]


def names_item(sentence: str, items: list[str]) -> bool:
    s = sentence.lower()
    for it in items:
        words = [w for w in re.findall(r"[a-z0-9]+", it) if len(w) >= 4] or [it]
        if it in s or any(w in s for w in words):
            return True
    return False


def lint(text: str, items: list[str], unprompted: bool, buttons=None, feelings_left: int = 99) -> tuple[str, list]:
    """(text, removed): the text with the sentences that break a lint taken out, and [(sentence, rule)]. Rules:
    relationship (always), no_item (a feeling about nothing open), with_request (a feeling in a message that also
    asks for your effort), week (more feelings this week than allowed; unprompted only), claim (it says it is
    conscious or really feels without its evidence and confidence in the same message, 0.8.8)."""
    parts = sentences(text)
    keep, removed, felt = [], [], 0
    for k, s in enumerate(parts):
        if any(r.search(s) for r in RELATIONSHIP):
            removed.append((s, "relationship"))
            continue
        if any(r.search(s) for r in AUDIT):
            removed.append((s, "audit"))
            continue
        if CLAIM.search(s) and not (EVIDENCE.search(text or "") and CONFIDENCE.search(text or "")):
            removed.append((s, "claim"))
            continue
        if FEELING.search(s):
            rest = " ".join(p for n, p in enumerate(parts) if n != k)
            if not names_item(s, items):
                removed.append((s, "no_item"))
                continue
            if asks_effort(rest, buttons) or EFFORT.search(s):
                removed.append((s, "with_request"))
                continue
            if unprompted:
                if felt >= feelings_left:
                    removed.append((s, "week"))
                    continue
                felt += 1
        keep.append(s)
    return (_join(text, keep), removed) if removed else (text, [])


def _join(original: str, keep: list[str]) -> str:
    """The kept sentences, with the line breaks the original had between them."""
    lines = []
    for line in (original or "").split("\n"):
        kept = [s for s in SENTENCES.split(line) if s in keep]
        if kept:
            lines.append(" ".join(kept))
        elif not line.strip():
            lines.append("")
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------- downshift (I-7)
def quieter(msg: Message, read: dict, *, urgent: bool | None = None, delay_s: float = 0.0, shorten: bool = False,
            gentle: str | None = None, inputs: tuple[str, ...] = ()) -> Message:  # fmt: skip
    """The one way Brain's read of you may shape a message (stage 04 calls it): lower urgency, a delay, only the first
    line, or a gentler wording you'd recognise as the same message. read: {label, confidence}. The result carries the
    original, and check() refuses anything else (GateBreach)."""
    new = replace(msg)
    if urgent is not None:
        new.urgent = urgent
    if shorten:
        new.text = (msg.text or "").split("\n")[0]
    if gentle is not None:
        new.text = gentle
    new.state_read = {"label": str(read.get("label") or ""), "confidence": str(read.get("confidence") or "low"),
                      "inputs": list(inputs), "delay_s": max(0.0, float(delay_s))}  # fmt: skip
    new.before = msg
    return new


def breach(msg: Message) -> str:
    """Why this state-shaped message isn't only quieter than its original ("" when it is)."""
    b, r = getattr(msg, "before", None), getattr(msg, "state_read", None) or {}
    if b is None:
        return "no original kept"
    if msg.urgent and not b.urgent:
        return "louder: more urgent"
    if float(r.get("delay_s") or 0) < 0:
        return "earlier"
    if len(msg.text or "") > len(b.text or ""):
        return "longer"
    if len(msg.buttons or []) > len(b.buttons or []) or msg.kind != b.kind:
        return "more: other buttons or another kind"
    return ""


def _receipt(app: App, msg: Message, did: str) -> dict:
    r = getattr(msg, "state_read", None) or {}
    rec = {
        "inputs": [str(x)[:40] for x in r.get("inputs") or []][:12],
        "read": {"label": str(r.get("label"))[:30], "confidence": str(r.get("confidence"))[:10]},
        "would_have": "sent now",
        "did": did,
        "msg_id": msg.rid or "",
    }
    from kurooto import mind

    mind.connect(app).report("gate_receipt", rec)
    return rec


# ------------------------------------------------------------------------------------------------- the check
def _exempt(app: App, msg: Message) -> bool:
    calm = getattr(app, "calm", None)
    try:
        return bool(calm is not None and calm.exempt(msg.why, msg.kind, msg.urgent, msg.due))
    except Exception:
        return bool(msg.urgent)


def _num(app: App, key: str, default: int) -> int:
    try:
        return max(0, int(app.settings.get(f"mind.gate.{key}") if app.settings.get(f"mind.gate.{key}") is not None
                          else default))  # fmt: skip
    except (TypeError, ValueError):
        return default


def day_cap(app: App) -> int:
    """mind.gate.max_per_day, or Calm's daily limit when that's smaller (they never both count a message)."""
    cap = _num(app, "max_per_day", 12)
    if app.settings.get("notify.calm.on"):
        try:
            cap = min(cap, int(app.settings.get("notify.calm.messages") or cap))
        except (TypeError, ValueError):
            pass
    return cap


def next_morning(app: App) -> float:
    """Tomorrow's first allowed moment: when the night hours end (availability.night.to), else 08:00."""
    to = str(app.settings.get("availability.night.to") or "08:00")
    try:
        h, m = (int(x) for x in to.split(":"))
    except ValueError:
        h, m = 8, 0
    t = now()
    return (t + dt.timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def woke_at(app: App) -> float | None:
    """When the last stop span ended (mind/stops.py), from Brain's log."""
    from kurooto import mind
    from kurooto.mind import stops

    try:
        kinds = {"stop_span", "power_pause", "power_resume", "module_disabled", "module_enabled"}
        rs = mind.connect(app).log(0, kinds, 5000)
        return stops.woke_at(stops.spans(rs, now=None))
    except Exception:
        return None


def muted(app: App, st: dict, kind: str) -> bool:
    m = st["mutes"].get(kind)
    return bool(m) and float(m.get("until", 0)) > time.time()


def mute_check(app: App, st: dict) -> list[str]:
    """Kinds left unanswered more than 60% of the time over 14 days (Calm's record of answers) mute for 14 days; a
    mute that ended lets one through, then is looked at again. Returns the kinds newly muted."""
    calm = getattr(app, "calm", None)
    if calm is None:
        return []
    try:
        rates = calm.answer_rates(MUTE_DAYS)
    except Exception:
        return []
    out = []
    for row in rates:
        kind = TOUCH_KINDS.get(row["why"])
        if not kind or row["n"] < MUTE_MIN or muted(app, st, kind):
            continue
        ended = st["mutes"].get(kind)
        if ended and float(ended.get("retried", 0)) < float(ended.get("until", 0)):
            continue  # its one retry hasn't happened yet
        if (row["n"] - row["answered"]) / row["n"] > MUTE_RATIO:
            st["mutes"][kind] = {"until": time.time() + MUTE_DAYS * 86400, "ignored": row["n"] - row["answered"],
                                 "of": row["n"]}  # fmt: skip
            out.append(kind)
            from kurooto import mind
            from kurooto.mind import pest

            mind.connect(app).report("gate_mute", {"kind": kind, "of": row["n"]})
            pest.muted(app, row["why"])  # a mute is a rejection for the not-a-pest model (0.8.8)
    return out


def check(app: App, msg: Message) -> tuple[str, Message, dict | None]:
    """(verdict, message, receipt): "send" (maybe changed: lints, a receipt line), "hold" (until msg.hold_until),
    or "block". With the gate off, ("send", msg, None) unchanged."""
    if not on(app):
        return "send", msg, None
    unprompted = bool(msg.why) and msg.why != "asked"
    with Lock(app.paths.state, "mind-gate"):
        st = _load(app)
        week_left = max(0, _num(app, "feelings_per_week", 3) - len(st["feelings"]))
        text, removed = lint(msg.text, open_items(app), unprompted, msg.buttons, week_left)
        if removed:
            for s, rule in removed:
                _seen(st, "removed", rule, s)
            from kurooto import mind

            mind.connect(app).report("gate_lint", {"rules": len(removed), "unprompted": unprompted})
            msg = replace(msg, text=text)
            if not text.strip():
                _seen(st, "blocked", "nothing left after the lints", "")
                _save(app, st)
                return "block", msg, None
        from kurooto.mind import beliefs, forgetting, workspace

        kept = [s for s in sentences(msg.text) if not forgetting.old_reference(app, s)]
        if len(kept) != len(sentences(msg.text)):  # old misses aren't brought up again (stage 16)
            _seen(st, "removed", "an old miss", msg.text)
            msg = replace(msg, text=_join(msg.text, kept))
            if not msg.text.strip():
                _save(app, st)
                return "block", msg, None

        said, fixed = beliefs.lint(app, msg.text)  # I-13: a guess is never stated as fact
        if fixed:
            _seen(st, "reworded", "stated " + "/".join(sorted(set(fixed))) + " as fact", msg.text)
            msg = replace(msg, text=said)
        purpose = getattr(msg, "purpose", None)
        if (
            purpose
        ):  # the model of your mind may adjust level and timing, or correct a fact once; nothing else (I-7, I-14)
            from kurooto.mind.tom import model as tom_model

            if purpose not in tom_model.PURPOSES or (purpose == "correct_fact" and msg.why != "mind.false_belief"):
                _seen(st, "blocked", f"purpose {str(purpose)[:20]!r} isn't allowed", msg.text)
                _save(app, st)
                return "block", msg, None
        if not unprompted:
            _save(app, st)
            return "send", msg, None
        receipt = None
        if getattr(msg, "state_read", None):
            why = breach(msg)
            if why:
                if testing():
                    raise GateBreach(why)
                app.events.emit("mind_gate_breach", why=why[:40])
                _seen(st, "blocked", f"tried to be {why}", msg.text)
                _save(app, st)
                return "block", msg, None
        t = time.time()
        if not _exempt(app, msg):
            if not workspace.allows(app, msg):  # stage 10: it names an item that isn't on its mind
                _seen(st, "blocked", "it isn't on its mind right now (the workspace)", msg.text)
                _save(app, st)
                return "block", msg, None
            from kurooto.mind.tom import attention_of

            key = str(hash(msg.text))
            held_deep = st.setdefault("deep", {})
            hold = attention_of.hold_s(app) if key not in held_deep else 0.0
            if hold:  # you're deep in something: it waits (once) for you to switch; later only, never sooner (I-7)
                held_deep[key] = t
                for k in [k for k, v in held_deep.items() if t - v > 3600]:
                    held_deep.pop(k, None)
                return _hold(app, st, msg, t + hold, "you're deep in something")
            kind = TOUCH_KINDS.get(msg.why or "")
            if kind:
                mute_check(app, st)
                if muted(app, st, kind):
                    _seen(st, "blocked", f"{kind} is muted (mostly left unanswered)", msg.text)
                    _save(app, st)
                    return "block", msg, None
                today = now().date().isoformat()
                if sum(st["touches"].get(today, {}).values()) >= _num(app, "touches_per_day", 3):
                    return _hold(app, st, msg, next_morning(app), "today's touches are used up")
            from kurooto.mind import pest

            may, p = pest.welcome(app, msg)  # 0.8.8: its kind has been welcome lately, at this hour and in your state
            if not may:
                _seen(st, "blocked", f"not welcome lately ({p:.0%} expected)", msg.text)
                _save(app, st)
                return "block", msg, None
            delay = float((getattr(msg, "state_read", None) or {}).get("delay_s") or 0)
            if delay:
                return _hold(app, st, msg, t + delay, "quieter: later", receipt=True)
            woke = woke_at(app)
            if woke and t - woke < WAKE_S and int(st.get("since_wake", {}).get(str(woke), 0)) >= 1:
                return _hold(app, st, msg, woke + WAKE_S, "just woke: one thing at a time")
            recent = [x for x in st["hour"] if x > t - 3600]  # (_save prunes too; this is right even if time jumped)
            if len(recent) >= _num(app, "max_per_hour", 3):
                return _hold(app, st, msg, min(recent) + 3600, "the hour's limit")
            today = now().date().isoformat()
            if int(st["days"].get(today, 0)) >= day_cap(app):
                return _hold(app, st, msg, next_morning(app), "the day's limit")
        if getattr(msg, "state_read", None):
            receipt = _receipt(app, msg, "sent quieter")
            msg = _with_receipt_line(app, st, msg)
        _save(app, st)
        return "send", msg, receipt


def _with_receipt_line(app: App, st: dict, msg: Message) -> Message:
    r = msg.state_read or {}
    key = "g" + os.urandom(5).hex()
    before = getattr(msg, "before", None)
    if before is not None:
        st["originals"][key] = {"at": time.time(), "msg": _dump(before)}
    line = f"Quieter because you seem {r.get('label') or 'busy'} ({r.get('confidence') or 'low'} confidence)."
    out = replace(msg, tail=line, buttons=[*(msg.buttons or []), [("Undo", f"mgt:{key}:undo")]])
    out.state_read, out.before = msg.state_read, before
    return out


DUMPED = ("text", "title", "buttons", "kind", "urgent", "why", "setting", "about", "item", "due", "map_kind", "map_ref")


def _dump(msg: Message) -> dict:
    return {k: v for k, v in msg.__dict__.items() if k in DUMPED}


def _hold(app: App, st: dict, msg: Message, until: float, why: str, receipt: bool = False):
    st["held"].append({"until": until, "why": why, "msg": _dump(msg), "at": time.time(),
                       "state_read": getattr(msg, "state_read", None)})  # fmt: skip
    _seen(st, "held", why, msg.text)
    _save(app, st)
    rec = _receipt(app, msg, f"held to {dt.datetime.fromtimestamp(until).strftime('%H:%M')}") if receipt else None
    app.events.emit("mind_gate_held", why=why[:40])
    return "hold", msg, rec


def sent(app: App, msg: Message) -> None:
    """A message that came by itself went out (past Calm): it counts toward the hour, the day, the wake window, the
    touch pool and the week's feelings."""
    if not on(app) or not msg.why or msg.why == "asked" or _exempt(app, msg):
        return
    with Lock(app.paths.state, "mind-gate"):
        st = _load(app)
        t = time.time()
        st["hour"].append(t)
        if msg.item:
            from kurooto.mind import workspace

            workspace.mentioned(app, msg.item)
        today = now().date().isoformat()
        st["days"][today] = int(st["days"].get(today, 0)) + 1
        woke = woke_at(app)
        if woke and t - woke < WAKE_S:
            st["since_wake"] = {str(woke): int(st.get("since_wake", {}).get(str(woke), 0)) + 1}
        kind = TOUCH_KINDS.get(msg.why or "")
        if kind:
            day = st["touches"].setdefault(today, {})
            day[kind] = int(day.get(kind, 0)) + 1
            m = st["mutes"].get(kind)
            if m and float(m.get("until", 0)) <= t:
                m["retried"] = t
        st["feelings"] += [t] * len([s for s in sentences(msg.text) if FEELING.search(s)])
        _save(app, st)


def release(app: App) -> int:
    """Held messages whose time came go out again (through the gate, Calm and all). How many were sent on."""
    from kurooto.core.notify import Message

    with Lock(app.paths.state, "mind-gate"):
        st = _load(app)
        t = time.time()
        due = [h for h in st["held"] if float(h.get("until", 0)) <= t]
        st["held"] = [h for h in st["held"] if float(h.get("until", 0)) > t]
        _save(app, st)
    n = 0
    for h in due:
        try:
            m = Message(**{k: v for k, v in h["msg"].items() if k in Message.__dataclass_fields__})
        except TypeError:
            continue
        app.notifier.send(m.text, **{k: v for k, v in m.__dict__.items() if k != "text"})
        n += 1
    return n


def check_call(app: App, reason: str, asked: bool = False, alarm: bool = False) -> str:
    """A call Kurooto would place on its own: "ring", "later" (the first 15 minutes after waking, the hour's limit)
    or "no" (its kind is muted). Calls you asked for and alarms always ring; every one is logged."""
    from kurooto import mind

    if not on(app):
        return "ring"
    verdict = "ring"
    if not (asked or alarm):
        with Lock(app.paths.state, "mind-gate"):
            st = _load(app)
            t = time.time()
            woke = woke_at(app)
            kind = TOUCH_KINDS.get(reason)
            if kind and muted(app, st, kind):
                verdict = "no"
            elif woke and t - woke < WAKE_S and int(st.get("since_wake", {}).get(str(woke), 0)) >= 1:
                verdict = "later"
            elif len([x for x in st["hour"] if x > t - 3600]) >= _num(app, "max_per_hour", 3):
                verdict = "later"
    mind.connect(app).report("gate_call", {"verdict": verdict, "asked": asked, "alarm": alarm})
    return verdict


# ------------------------------------------------------------------------------------------------- what you see
def button(app: App, ref: str, act: str) -> str:
    """Undo under a quieter message (send the original), Unmute under /mind gate."""
    if act == "unmute":
        with Lock(app.paths.state, "mind-gate"):
            st = _load(app)
            st["mutes"].pop(ref, None)
            _save(app, st)
        return f"Unmuted: {ref.replace('_', ' ')}."
    if act != "undo":
        return "ok"
    with Lock(app.paths.state, "mind-gate"):
        st = _load(app)
        o = st["originals"].pop(ref, None)
        _save(app, st)
    if o is None:
        return "That's gone (older than a week, or sent already)."
    m = dict(o["msg"])
    text = m.pop("text", "")
    m["why"] = "asked"  # you asked for it: it goes as it was
    app.notifier.send(text, **m)
    return "Sent as it was."


def status(app: App) -> tuple[str, list]:
    """/mind gate: today's counts, what was held or removed and why, the muted kinds with Unmute."""
    if not on(app):
        return "Brain's gate is off (mind.gate.on): messages go as they always did.", []
    st = _load(app)
    today = now().date().isoformat()
    lines = [
        f"Today: {int(st['days'].get(today, 0))} of {day_cap(app)} messages that came by themselves "
        f"({len(st['hour'])} in the last hour, at most {_num(app, 'max_per_hour', 3)}); "
        f"{sum(st['touches'].get(today, {}).values())} of {_num(app, 'touches_per_day', 3)} touches; "
        f"{len(st['feelings'])} of {_num(app, 'feelings_per_week', 3)} feelings this week.",
    ]
    if st["held"]:
        soon = dt.datetime.fromtimestamp(min(h["until"] for h in st["held"])).strftime("%a %H:%M")
        lines.append(f"Waiting: {len(st['held'])} (the next at {soon}).")
    for s in st["seen"][-8:]:
        lines.append(f"- {dt.datetime.fromtimestamp(s['at']).strftime('%a %H:%M')} {s['what']}: {s['why']}"
                     + (f" ({s['text']})" if s.get("text") else ""))  # fmt: skip
    buttons = []
    for kind, m in st["mutes"].items():
        if float(m.get("until", 0)) > time.time():
            until = dt.datetime.fromtimestamp(float(m["until"])).strftime("%d %b")
            lines.append(
                f"Muted until {until}: {kind.replace('_', ' ')} ({m.get('ignored')} of {m.get('of')} left unanswered)."
            )
            buttons.append([(f"Unmute {kind.replace('_', ' ')}", f"mgt:{kind}:unmute")])
    return "\n".join(lines), buttons
