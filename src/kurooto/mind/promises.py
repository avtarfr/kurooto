"""The commitments ledger (Brain, 0.8.0 stage 05): what Kurooto itself said it would do, and whether it did.

Detecting a promise. When a message Kurooto starts by itself says it will do something at a time ("I'll check back at
6",
"I'll remind you Friday"), it becomes a promise: rules first (an "I'll" or "I will", a verb of doing, a time that
core/clock.py's parser reads). The deadline is frozen when the promise is made.

    {id, text (cut), due, made_at, source (the message's reason), state: open | kept | broken | renegotiated}

Kept: the promised action's event happens before it's due. Silent. Broken: it's due and nothing happened. Kurooto says
so first, in one line, before you notice, with the fix and nothing grovelling ("I said I'd check back at 6 and didn't:
the laptop was off. Checking now."). Renegotiating writes `broken` first, then a new promise. The log gets
`promise_made`,
`promise_kept`, `promise_broken` with ids and numbers only; the words stay in `mind-promises.json` in the state folder
(deleted with Brain's data).

    seen(app, text, why)    a message Kurooto sent: any promise in it is recorded
    said(app, text, where)  (0.9.0, mind.promises.answers) its own words elsewhere: an answer, a call, the desk
    review(app)             every 5 minutes: kept ones close silently, broken ones are said and recorded
    slack(app)              the body budget's promise_slack variable, in [-1, 1] (1: nothing open)
    listing(app)            /promises
    outage_line(app)        the heartbeat: what the next 12 hours don't have a guarantee for while the computer is down
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.mind import budget

if TYPE_CHECKING:
    from kurooto.app import App

PART = "promises"  # its switch: mind.promises.on

register_defaults(
    "mind",
    {
        # its own promises: noticed, kept or owned up to first; answers (0.9.0): also in its answers to you, its side
        # of a call and what it says at the desk (read here with the same rules, never sent anywhere)
        "promises": {"on": True, "answers": True},
        "heartbeat": {"on": True},  # when this computer is down, what the next 12 hours don't have a guarantee for
    },
)

FILE = "mind-promises.json"
KEEP_DAYS = 30
TEXT_MAX = 140
WORK_H = 0.5  # hours of work a promise needs, until something knows better
_WHEN = (
    r"(?:at|by|before|in|on|tonight|tomorrow|this (?:morning|afternoon|evening)|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b[^.!?\n]{0,30}"
)
SAID = re.compile(rf"(?i)\bI(?:'ll| will)\s+(?P<act>[a-z][a-z' -]{{2,60}}?)\s+(?P<when>{_WHEN})")
VERB = re.compile(
    r"(?i)^(?:also |then |just )?(check|read|remind|call|look|send|follow|prepare|finish|come|get|ping|review|draft)"
)
KEPT_BY = {
    "remind": {"reminder_fired", "call_rang"},
    "call": {"call_rang", "call_answered", "call_rang_offline"},
}
KEPT_ANY = {
    "job_ended",
    "reminder_fired",
    "call_rang",
    "checkin_asked",
    "deadline_told",
}  # a doing verb with no event of its own
LOOSE = {"tonight": "21:00", "this morning": "09:00", "this afternoon": "15:00", "this evening": "18:30"}


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("rows", [])
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def _when(text: str, base: dt.datetime) -> dt.datetime | None:
    s = text.strip().lower().rstrip(" ,;")
    for k, v in LOOSE.items():
        if s.startswith(k):
            s = v
            break
    s = re.sub(r"^(?:on|by|before)\s+", "", s)
    s = re.sub(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lambda m: m[1][:3] + " 09:00", s)
    s = re.sub(r"^tomorrow(?: morning)?$", "tomorrow 09:00", s)
    s = re.sub(r"^tomorrow afternoon$", "tomorrow 15:00", s)
    s = re.sub(r"^tomorrow (?:evening|night)$", "tomorrow 18:30", s)
    words = s.split()
    for start in range(len(words)):  # "at it tomorrow morning": drop words from the front until the rest reads
        for end in range(len(words), start, -1):
            try:
                return parse_when(" ".join(words[start:end]), base)
            except ValueError:
                continue
    return None


def detect(text: str, base: dt.datetime | None = None) -> list[dict]:
    """The promises in a piece of text: [{act, when_text, due}]. Rules only."""
    base = base or now()
    out = []
    for m in SAID.finditer(text or ""):
        act = " ".join(m["act"].split())
        if not VERB.match(act):
            continue
        due = _when(m["when"], base)
        if due is not None and due > base:
            out.append({"act": act, "when_text": m["when"].strip(), "due": due})
    return out


def seen(app: App, text: str, why: str = "") -> int:
    """A message Kurooto sent by itself: record any promise in it. How many."""
    if not mind.part_on(app, "promises") or not why or why == "asked":
        return 0
    found = detect(text)
    if not found:
        return 0
    t = now()
    with Lock(app.paths.state, "mind-promises"):
        st = _state(app)
        for f in found:
            for r in st["rows"]:  # a new promise to do the same thing renegotiates the old one: broken first
                if r["state"] == "open" and r["act"] == f["act"]:
                    r["state"] = "renegotiated"
                    _log(app, "promise_broken", r, renegotiated=True)
            row = {
                "id": uuid.uuid4().hex[:12], "act": f["act"], "text": f"I'll {f['act']} {f['when_text']}"[:TEXT_MAX],
                "due": f["due"].timestamp(), "made_at": t.timestamp(), "source": str(why)[:40], "state": "open",
            }  # fmt: skip
            st["rows"].append(row)
            _log(app, "promise_made", row)
        st["rows"] = st["rows"][-200:]
        _save(app, st)
    return len(found)


def said(app: App, text: str, where: str) -> int:
    """(0.9.0, mind.promises.answers) Kurooto's own words outside the messages it starts: an answer to you ("answer"),
    its side of a call ("call"), what it said at the desk ("desk"). The same local rules; the source is "said.<where>".
    Never raises."""
    try:
        if not app.settings.get("mind.promises.answers") or not text:
            return 0
        return seen(app, str(text)[:4000], f"said.{where}")
    except Exception:
        return 0


def _log(app: App, kind: str, row: dict, **extra) -> None:
    app.events.emit(kind, id=row["id"], due_s=int(row["due"]), made_s=int(row["made_at"]), **extra)


def _events_since(app: App, kinds: set[str], since: float) -> list[float]:
    out = []
    for rec in app.events.tail(2000, kinds):
        try:
            t = dt.datetime.fromisoformat(str(rec.get("ts"))).timestamp()
        except ValueError:
            continue
        if t >= since:
            out.append(t)
    return out


def review(app: App, payload: dict | None = None) -> dict:
    """Close what was kept (silently) and own up to what wasn't (once, first). {kept, broken}."""
    if not mind.part_on(app, "promises"):
        return {}
    t = now().timestamp()
    kept = broken = 0
    said: list[tuple[dict, str]] = []
    with Lock(app.paths.state, "mind-promises"):
        st = _state(app)
        for r in st["rows"]:
            if r["state"] != "open":
                continue
            verb = (VERB.match(r["act"]) or [None, "check"])[1].lower()
            kinds = KEPT_BY.get(verb, KEPT_ANY)
            if any(x <= r["due"] + 60 for x in _events_since(app, kinds, r["made_at"])):
                r["state"] = "kept"
                kept += 1
                _log(app, "promise_kept", r)
            elif t > r["due"]:
                r["state"] = "broken"
                broken += 1
                _log(app, "promise_broken", r)
                said.append((r, _why_not(app, r)))
        st["rows"] = [r for r in st["rows"] if t - r["made_at"] < KEEP_DAYS * 86400]
        _save(app, st)
    for r, why in said:  # before you notice, one line, with the fix
        app.notify(
            f"{r['text'].replace('I\'ll', 'I said I\'d', 1)} and didn't{': ' + why if why else ''}. Checking now.",
            kind="info", why="mind.promise_broken",
        )  # fmt: skip
    return {"kept": kept, "broken": broken}


def _why_not(app: App, r: dict) -> str:
    """The honest reason it can say: it was stopped or asleep then (stage 02's spans), else none."""
    try:
        from kurooto.mind import stops

        recs = mind.connect(app).log(0, stops.STOP_KINDS if hasattr(stops, "STOP_KINDS") else None, 2000)
        sp = stops.spans(recs, now=r["due"] + 60)
        if stops.frozen(sp, r["due"]):
            return "the computer was off or asleep"
    except Exception:
        pass
    return ""


def slack(app: App) -> float:
    """promise_slack: the least slack over open promises (hours to due minus WORK_H), in [-1, 1]; 1 when none are
    open."""
    t = now().timestamp()
    opens = [r for r in _state(app)["rows"] if r["state"] == "open"]
    if not opens:
        return 1.0
    return min(budget.slack((r["due"] - t) / 3600.0, WORK_H) for r in opens)


def listing(app: App) -> str:
    st = _state(app)
    rows = sorted(st["rows"], key=lambda r: r["due"])
    if not rows:
        return "No promises yet: nothing it said it would do at a time."
    n = {s: sum(1 for r in rows if r["state"] == s) for s in ("open", "kept", "broken", "renegotiated")}
    lines = [f"Promises: {n['open']} open, {n['kept']} kept, {n['broken']} broken, {n['renegotiated']} renegotiated."]
    for r in rows[-12:]:
        lines.append(f"- {dt.datetime.fromtimestamp(r['due']):%a %H:%M} [{r['state']}] {r['text']}")
    return "\n".join(lines)


def outage_line(app: App) -> str:
    """The heartbeat: while this computer is down, which reminders in the next 12 hours aren't guaranteed (the call line
    holds some of them, and scheduled calls). "" when Brain's heartbeat is off or there's nothing to say."""
    if not mind.part_on(app, "heartbeat"):
        return ""
    t = now()
    horizon = t + dt.timedelta(hours=12)
    try:
        n = sum(1 for j in app.scheduler.jobs("reminders:") if j.when.timestamp() <= horizon.timestamp())
    except Exception:
        n = 0
    held = 0
    try:
        held = int(((app.modules.get("lidsafe") or object())._held() or {}).get("held") or 0)  # noqa: SLF001
    except Exception:
        held = 0
    open_n = sum(1 for r in _state(app)["rows"] if r["state"] == "open" and r["due"] <= horizon.timestamp())
    waiting = max(0, n - held) + open_n
    if not waiting:
        return ""
    many = waiting != 1
    return (
        f" {waiting} thing{'s' if many else ''} in the next 12 hours (reminders, its own promises) "
        f"{'have' if many else 'has'} no guarantee until it's back."
    )
