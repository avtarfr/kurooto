"""The global workspace (Brain, 0.8.0 stage 10): a small "now" stage that parts of Kurooto compete to enter.

What wins is broadcast to everything, and only what wins may drive an unprompted outward action or a new autonomous
act, enter the journal and the story, and be foregrounded in an AI's context. It coordinates parallel work; it is
**never a queue or a bottleneck**: jobs, Dreaming, reading and the lab keep running, and an answer to a direct request
needs no winner.

    Bid                  one thing asking for attention: item_id, kind, text, stake, urgency, surprise, source
    register_bidder      a part adds `bid(app, now) -> [Bid]` (deadlines, promises, the read, the forecast are built in)
    cycle(app)           run every minute (the scheduler's finest step), at least `mind.workspace.cycle_s` apart, and
                         on any high-priority event (`poke`). Salience = stake x urgency x (1 + surprise)
                         x (1 - fatigue);
                         the top `capacity` (1 to 3) win, and a `workspace_cycle` record (ids and numbers) is logged
    current / won        the winners, and "did this item win lately" (the gate's rule for unprompted messages)
    mentioned            an item was said to you: it tires (fatigue is its mentions in 24 hours over 3, at most 1)
    pin / mute / veto    you decide: pin keeps an item in, mute keeps it out, veto silences a whole bidder
    standing             long-horizon goals hold bids that grow with plan slip, so week-long goals aren't starved
    context              the winners that aren't about you, for "on my mind" in an AI request (a reading of you stays
                         on this computer: invariant I-11)

The door (0.8.14, `mind.workspace.arbiter`): every message Kurooto starts by itself (check-ins, Calm's touches,
research watch, Dreaming's results, a feeling said aloud) and every add-on bid goes through here, and only winners
are sent.
    door(app, msg)       core/notify.py asks it after Brain's gate: go now, or wait here. A message gets a default bid
                         from its Calm reason (DEFAULT_BIDS), its due time, how long it has waited, and the not-a-pest
                         model's welcome (it scales the stake); one about something on its mind counts double
    add_bidder           an add-on adds `fn(app, now) -> [{"kind", "id", "stake", "urgency", "surprise", "send"}]`:
                         numbers and ids only (text never enters), and `send()` is called when it wins
    release(app)         every minute and at each natural break (mind/breaks.py): the top `capacity` waiting win; a
                         winner goes at a break, when it's urgent, or after `max_hold_min`; never while it's asleep.
                         Losers stay and bid again; one that kept losing `fold_h` hours goes into the evening bundle
    held_count           how many wait at the door (the status stream shows it)
Exempt, they go straight past: alarms, your own reminders, calls, approvals, close deadlines (Calm's exemptions) and
answers to you. With the arbiter off, or Brain off, messages go as in 0.8.13.

Words (an item's text) stay in `<state>/mind-workspace.json`, and a waiting message in `<state>/mind-door.json`; the
log gets ids and numbers.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "workspace"  # its switch: mind.workspace.on

register_defaults(
    "mind",
    {
        "workspace": {
            "on": True,  # a small "now" stage parts compete to enter; only what wins may drive an unprompted action
            "capacity": 3,  # how many items win a cycle (1 to 3)
            "cycle_s": 30,  # the least gap in seconds between two cycles (the job runs every minute; events poke it)
            "arbiter": True,  # 0.8.14: every message that comes by itself bids at the door; only winners are sent
            "breaks": True,  # 0.8.14: a winner that isn't urgent waits for a natural break (a window switch, a pickup)
            "max_hold_min": 90,  # ...but never longer than this many minutes (unless Kurooto is asleep)
            # (0.9.0) an add-on may say you're deep in one thing (mind/breaks.py deep): a winner that isn't urgent
            # then waits even at a break, still at most max_hold_min; what goes past the door is never held
            "deep_hold": True,
            "break_after_min": 25,  # a window switch is a break after this many minutes in one window
            "fold_h": 6,  # a message that kept losing this many hours goes into the next evening bundle instead
        },
        "attention": {"on": True},  # a model of its own attention; "what are you thinking about?" is answered from it
        # 0.8.14 (mind/records.py; registered here, as records.py is also the scorekeeper's and stays lean):
        "expect": {"on": True},  # what it expects of each message it starts (a reply, done in 2 h), and what came
        # "Why this?" under its own messages says what the gate and the door did with it; to_ai (0.9.0): a turn that
        # asks you why also gives your AI the plain reasons for its last few messages (never a sense, mood or tone)
        "why": {"on": True, "to_ai": True},
        "beliefs": {"on": True},  # every belief keeps its source (said, saw, inferred, imagined) and a confidence
    },
)

FILE = "mind-workspace.json"
HISTORY = 60  # cycles kept
DAY_S = 86400
FATIGUE_AT = 3  # mentions in 24 hours that tire an item out completely
SOURCES = ("said", "saw", "inferred", "imagined")


@dataclass
class Bid:
    item_id: str
    kind: str
    text: str = ""
    stake: float = 0.5  # 0-1: how much it matters
    urgency: float = 0.5  # 0-1: how soon
    surprise: float = 0.0  # 0-1: how unexpected
    source: str = "saw"
    module: str = ""
    private: bool = False  # about you: it can win, but never goes into an AI's context
    standing: bool = False
    extra: dict = field(default_factory=dict)


def clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def salience(b: Bid, fatigue: float) -> float:
    """stake x urgency x (1 + surprise) x (1 - fatigue); each term a number from 0 to 1."""
    return round(clip01(b.stake) * clip01(b.urgency) * (1.0 + clip01(b.surprise)) * (1.0 - clip01(fatigue)), 6)


BIDDERS: dict[str, Callable[[App, float], list[Bid]]] = {}


def register_bidder(name: str, fn: Callable[[App, float], list[Bid]]) -> None:
    BIDDERS[name] = fn


# ----------------------------------------------------------------------------------------------------- state
def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k, v in (
        ("winners", []),
        ("history", []),
        ("mentions", {}),
        ("pins", []),
        ("mutes", []),
        ("vetoes", []),
        ("standing", {}),
    ):
        d.setdefault(k, v)
    d.setdefault("cycle_at", 0.0)
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def capacity(app: App) -> int:
    v = app.settings.get("mind.workspace.capacity")
    return max(1, min(3, int(v))) if isinstance(v, (int, float)) else 3


def fatigue(st: dict, item_id: str, now: float) -> float:
    n = sum(1 for t in st["mentions"].get(item_id, []) if now - t < DAY_S)
    return min(1.0, n / FATIGUE_AT)


# ----------------------------------------------------------------------------------------------- built-in bidders
def bid_deadlines(app: App, now: float) -> list[Bid]:
    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines"):
        return []
    out = []
    for i, it, hours in dl.upcoming(72)[:12]:
        exam = it.get("kind") == "exam"
        out.append(
            Bid(
                f"deadline:{i}",
                "deadline",
                str(it.get("title", ""))[:80],
                stake=0.9 if exam else 0.6,
                urgency=clip01(1.0 - max(hours, 0.0) / 72.0),
                module="deadlines",
                source="saw",
            )  # fmt: skip
        )
    return out


def bid_promises(app: App, now: float) -> list[Bid]:
    from kurooto.mind import budget, promises

    out = []
    for r in promises._state(app)["rows"]:  # noqa: SLF001
        if r["state"] != "open":
            continue
        slack = budget.slack((r["due"] - now) / 3600.0, promises.WORK_H)
        out.append(
            Bid(
                f"promise:{r['id']}",
                "promise",
                str(r["text"])[:80],
                stake=0.5,
                urgency=clip01((1.0 - slack) / 2.0),
                module="promises",
            )
        )
    return out


def bid_read(app: App, now: float) -> list[Bid]:
    """Your state read, when it counts and isn't "steady": it can win (so the gate and the journal know), never goes to
    an AI."""
    if not mind.part_on(app, "read"):
        return []
    from kurooto.mind import mood

    row = next(iter(mind.connect(app).mood_rows(f"read:{mood.today().isoformat()}")), None)
    m = (row or {}).get("meta") or {}
    if not m.get("counted") or m.get("label") in (None, "steady"):
        return []
    return [
        Bid(
            f"read:{mood.today().isoformat()}",
            "read",
            "how you're doing",
            stake=0.7,
            urgency=0.4,
            surprise=clip01(float(row["value"]) / 10.0),
            module="read",
            source="inferred",
            private=True,
        )
    ]


def bid_forecast(app: App, now: float) -> list[Bid]:
    """A forecast that surprised it: worth attention (about you, so private)."""
    if not mind.part_on(app, "forecast"):
        return []
    rows = sorted(mind.connect(app).mood_rows("score:"), key=lambda r: r["key"])
    if not rows:
        return []
    s = float(rows[-1]["value"])
    return [
        Bid(
            f"forecast:{rows[-1]['key'][6:]}",
            "forecast",
            "how tomorrow went against what it expected",
            stake=0.4,
            urgency=0.5,
            surprise=clip01(s / 8.0),
            module="forecast",
            source="imagined",
            private=True,
        )
    ]


def bid_standing(app: App, now: float) -> list[Bid]:
    """Standing goals: a bid that grows with plan slip (0 to 1), so a week-long goal isn't starved by today's pings."""
    out = []
    for gid, g in _state(app)["standing"].items():
        slip = clip01(float(g.get("slip", 0.0)))
        out.append(
            Bid(
                f"goal:{gid}",
                "goal",
                str(g.get("text", ""))[:80],
                stake=0.9,
                urgency=0.25 + 0.75 * slip,
                module="goals",
                standing=True,
            )
        )
    return out


BUILT_IN = {
    "deadlines": bid_deadlines,
    "promises": bid_promises,
    "read": bid_read,
    "forecast": bid_forecast,
    "goals": bid_standing,
}
for _n, _f in BUILT_IN.items():
    register_bidder(_n, _f)


def set_standing(app: App, gid: str, text: str, slip: float) -> None:
    """A long-horizon goal (a project, a week plan) and how far it has slipped, 0 to 1 (stage 15 and the projects
    feature)."""
    st = _state(app)
    st["standing"][str(gid)[:40]] = {"text": text[:80], "slip": clip01(slip)}
    _save(app, st)


def clear_standing(app: App, gid: str) -> None:
    st = _state(app)
    if st["standing"].pop(str(gid)[:40], None) is not None:
        _save(app, st)


# ---------------------------------------------------------------------------------------------------- the cycle
def on(app: App) -> bool:
    return mind.part_on(app, "workspace")


def cycle(app: App, extra: list[Bid] | None = None, force: bool = False) -> list[dict]:
    """One competition. Returns the winners: [{item_id, kind, text, salience, stake, urgency, surprise, source, module,
    private}]."""
    if not on(app):
        return []
    now = time.time()
    st = _state(app)
    gap = app.settings.get("mind.workspace.cycle_s")
    if not force and now - float(st["cycle_at"]) < (float(gap) if isinstance(gap, (int, float)) else 30.0):
        return st["winners"]
    bids: list[Bid] = list(extra or [])
    for name, fn in BIDDERS.items():
        if name in st["vetoes"]:
            continue
        try:
            bids += fn(app, now)
        except Exception as e:  # one bidder failing never stops the stage
            app.events.emit("workspace_bidder_failed", bidder=name, error=type(e).__name__)
    scored = []
    for b in bids:
        if b.item_id in st["mutes"]:
            continue
        s = salience(b, fatigue(st, b.item_id, now))
        scored.append({**asdict(b), "salience": s, "pinned": b.item_id in st["pins"]})
    from kurooto.mind import attention

    expected = attention.predict(app) if attention.on(app) else []  # what its model of itself said would win now
    pinned = [x for x in scored if x["pinned"]]
    rest = sorted((x for x in scored if not x["pinned"] and x["salience"] > 0), key=lambda x: -x["salience"])
    win = (pinned + rest)[: capacity(app)]
    prev = {w["item_id"]: w.get("since", w.get("at", now)) for w in st["winners"]}
    for w in win:
        w["since"] = prev.get(w["item_id"], now)
        w["at"] = now
    st["winners"] = win
    st["cycle_at"] = now
    st["history"] = [*st["history"], {"at": now, "items": [w["item_id"] for w in win], "n": len(scored)}][-HISTORY:]
    st["mentions"] = {
        k: [t for t in v if now - t < DAY_S] for k, v in st["mentions"].items() if any(now - t < DAY_S for t in v)
    }
    _save(app, st)
    if expected:
        attention.check(app, expected, [w["item_id"] for w in win], len(scored), capacity(app))
    if win:
        mind.connect(app).report(
            "workspace_cycle",
            {
                "items": [w["item_id"] for w in win],
                "kinds": [w["kind"] for w in win],
                "salience": [w["salience"] for w in win],
                "n": len(scored),
            },
        )
    return win


def poke(app: App, item_id: str, kind: str = "message", text: str = "", urgency: float = 1.0) -> list[dict]:
    """A high-priority event (a call, an alarm, a message from you): an immediate cycle with that event as a bid."""
    if not on(app):
        return []
    return cycle(app, [Bid(item_id, kind, text, stake=1.0, urgency=urgency, module="events")], force=True)


def current(app: App) -> list[dict]:
    return _state(app)["winners"] if on(app) else []


def won(app: App, item_id: str, cycles: int = 1) -> bool:
    """Did this item win one of the last `cycles` cycles? The gate asks this of an unprompted message that names an
    item."""
    st = _state(app)
    return any(item_id in h["items"] for h in st["history"][-cycles:]) if on(app) else True


ITEM_PREFIXES = ("deadline", "promise", "goal", "read", "forecast", "event", "lab")  # an item id a message may declare


def allows(app: App, msg) -> bool:
    """The gate's rule: an unprompted message that declares a workspace item (`msg.item` like "promise:ab12") needs
    that item to have won one of the last two cycles. A message with no such item is not held to it. With the door on
    (0.8.14) nothing is blocked here: the message bids at the door instead, and its item counts double there."""
    item = str(getattr(msg, "item", "") or "")
    if not on(app) or item.split(":", 1)[0] not in ITEM_PREFIXES or ":" not in item or arbiter_on(app):
        return True
    cycle(app)
    return won(app, item, 2)


def mentioned(app: App, item_id: str) -> None:
    st = _state(app)
    st["mentions"].setdefault(item_id, []).append(time.time())
    _save(app, st)


def context(app: App) -> str:
    """ "On my mind": the winners that aren't about you, for an AI's context. Nothing about how you're doing goes
    here."""
    ws = [w for w in current(app) if not w.get("private")]
    if not ws:
        return ""
    return "On my mind right now: " + "; ".join(f"{w['text'] or w['kind']} ({w['kind']})" for w in ws)


# ----------------------------------------------------------------------------------------------- your hand on it
def pin(app: App, item_id: str) -> str:
    st = _state(app)
    st["pins"] = sorted({*st["pins"], item_id})
    st["mutes"] = [m for m in st["mutes"] if m != item_id]
    _save(app, st)
    cycle(app, force=True)
    return f"Pinned: {item_id} stays on its mind."


def mute(app: App, item_id: str) -> str:
    st = _state(app)
    st["mutes"] = sorted({*st["mutes"], item_id})
    st["pins"] = [p for p in st["pins"] if p != item_id]
    _save(app, st)
    cycle(app, force=True)
    return f"Muted: {item_id} stays out of its mind."


def veto(app: App, bidder: str) -> str:
    if bidder not in BIDDERS:
        return "No such bidder: " + ", ".join(sorted(BIDDERS)) + "."
    st = _state(app)
    st["vetoes"] = sorted({*st["vetoes"], bidder})
    _save(app, st)
    cycle(app, force=True)
    return f"Vetoed: {bidder} can't bid until you un-veto it (/thinking unveto {bidder})."


def unveto(app: App, bidder: str) -> str:
    st = _state(app)
    st["vetoes"] = [v for v in st["vetoes"] if v != bidder]
    _save(app, st)
    return f"{bidder} may bid again."


def unpin(app: App, item_id: str) -> str:
    st = _state(app)
    st["pins"] = [p for p in st["pins"] if p != item_id]
    st["mutes"] = [m for m in st["mutes"] if m != item_id]
    _save(app, st)
    return f"{item_id} is back to competing like the rest."


# ------------------------------------------------------------------------------------------- the door (0.8.14)
DOOR_FILE = "mind-door.json"
DOOR_SEEN_MAX = 60
PENDING_MAX = 100  # past this many waiting, the oldest goes into the evening bundle (never dropped)
URGENT_AT = 0.9  # a bid this urgent by its own due time (not by waiting) doesn't wait for a break
DUE_SPAN_H = 72.0  # a due time this far off adds nothing to urgency; closer, more
AGE_WEIGHT = 0.5  # waiting raises urgency by up to this much, reaching it at max_hold_min: losers aren't starved
ON_MIND = 2.0  # a message about something that's on its mind (a stage winner) counts this many times over
KEPT = ("text", "title", "buttons", "kind", "urgent", "reply_to", "map_kind", "map_ref", "file", "tail", "why",
        "setting", "about", "item", "due", "purpose", "bid")  # fmt: skip
ID_RE = re.compile(r"^[A-Za-z0-9_.:@+-]{1,64}$")

# (stake, urgency) of a message's default bid, by the kind its Calm reason makes it (bid_kind)
DEFAULT_BIDS = {
    "check-in": (0.6, 0.5),  # a question or check-in: it wants an answer
    "deadline": (0.7, 0.5),  # deadlines, quizzes, study pushes (a due time raises the urgency)
    "nudge": (0.5, 0.4),  # Calm's small touches and Brain's nudges
    "finding": (0.4, 0.3),  # research watch, the lab, Dreaming, a feeling said aloud
    "update": (0.3, 0.2),  # notices about Kurooto itself
    "other": (0.5, 0.4),
}

DOOR_BIDDERS: dict[str, Callable] = {}
_PASS: ContextVar[dict | None] = ContextVar("kurooto_door_pass", default=None)


def add_bidder(name: str, fn: Callable) -> None:
    """For add-ons: `fn(app, now) -> [{"kind", "id", "stake", "urgency", "surprise", "send"}]`. Numbers 0..1 and short
    ids only (text never enters the workspace); `send()` is called once when the bid wins, at a natural break. A bid
    that's still relevant should come back each cycle: one that loses bids again, one that's gone simply isn't
    returned."""
    DOOR_BIDDERS[str(name)[:40]] = fn


def arbiter_on(app: App) -> bool:
    return on(app) and bool(app.settings.get("mind.workspace.arbiter"))


@contextmanager
def passing(note: str = "") -> Iterator[dict]:
    """The next message sent inside this goes past the door: a winner being let out (or one Brain's gate already
    timed). `note` says what happened to it, for "Why this?"."""
    holder = {"used": False, "note": note}
    tok = _PASS.set(holder)
    try:
        yield holder
    finally:
        _PASS.reset(tok)


def exempt(app: App, msg) -> str:
    """Why this message goes straight past the door, or "" when it bids: answers to you, calls, approvals, anything
    urgent, and Calm's exemptions (the alarm, your own reminders, a deadline under 12 hours away, the bundle)."""
    why = getattr(msg, "why", None)
    if not why or why == "asked" or getattr(msg, "reply_to", None):
        return "asked"
    if msg.kind in ("call", "approval"):
        return msg.kind
    if msg.urgent:
        return "urgent"
    calm = getattr(app, "calm", None)
    try:
        return (calm.exempt(why, msg.kind, msg.urgent, msg.due) if calm is not None else "") or ""
    except Exception:
        return ""


def asleep(app: App) -> bool:
    """Kurooto's own sleep (mind/sleep.py, when that part is there): nothing waiting goes out while it's asleep."""
    try:
        from kurooto.mind import sleep as _sleep
    except ImportError:
        return False
    try:
        return getattr(_sleep, "state", lambda a: "awake")(app) == "asleep"
    except Exception:
        return False


def bid_kind(why: str, kind: str) -> str:
    """The kind of default bid a message gets, from its Calm reason (and its own kind)."""
    from kurooto.mind import pest

    pk = pest.kind_of(why)
    head = why.split(".", 1)[0]
    if pk == "check-in" or kind == "question" or head == "checkins":
        return "check-in"
    if head in ("deadlines", "quiz", "study", "exam_season", "classes"):
        return "deadline"
    if pk == "nudge":
        return "nudge"
    if pk in ("finding", "excitement") or head == "research":
        return "finding"
    if head == "updates":
        return "update"
    return "other"


def welcome_p(app: App, why: str) -> float:
    """The not-a-pest model's expected welcome for this kind of message now (1 when it has no say). Read only."""
    from kurooto.core.clock import now as clock_now
    from kurooto.mind import pest

    try:
        kind = pest.kind_of(why)
        if kind is None or not pest.on(app):
            return 1.0
        return clip01(pest.expected(pest._load(app), kind, pest.band(clock_now().hour), pest.his_state(app)))  # noqa: SLF001
    except Exception:
        return 1.0


def _door(app: App) -> dict:
    d = jload(app.paths.state / DOOR_FILE, {}) or {}
    for k, v in (("pending", []), ("addons", {}), ("seen", []), ("counts", {})):
        d.setdefault(k, v)
    return d


def _door_save(app: App, d: dict) -> None:
    d["seen"] = d["seen"][-DOOR_SEEN_MAX:]
    jsave(app.paths.state / DOOR_FILE, d)


def _note(d: dict, what: str, why: str, reason: str = "") -> None:
    d["seen"].append({"at": round(time.time(), 1), "what": what, "why": why, "reason": reason[:60]})
    d["counts"][what] = int(d["counts"].get(what, 0)) + 1


def _key(msg) -> str:
    """One waiting message per thing: the same reason about the same item (or question, or words) replaces the older
    one, keeping when the first came."""
    ident = msg.item or (f"{msg.map_kind}:{msg.map_ref}" if msg.map_ref else "") or msg.text
    return "m" + hashlib.sha256(f"{msg.why}|{ident}".encode()).hexdigest()[:11]


def _dump(msg) -> dict:
    return json.loads(json.dumps({k: getattr(msg, k, None) for k in KEPT}, ensure_ascii=False, default=str))


def _hours_to(due) -> float | None:
    try:
        d = dt.datetime.fromisoformat(str(due))
    except (TypeError, ValueError):
        return None
    d = d.astimezone().replace(tzinfo=None) if d.tzinfo else d
    return (d - dt.datetime.now()).total_seconds() / 3600.0


def _score(app: App, e: dict, now: float, stage: set, ws: dict, hold_s: float) -> dict:
    """A waiting message's bid: its default by kind (or what it carried in `bid`), its due time, how long it has
    waited, the pest model's welcome on the stake, and its fatigue. Numbers only."""
    stake, urg = DEFAULT_BIDS.get(e.get("bkind") or "other", DEFAULT_BIDS["other"])
    b = e.get("bid") or {}
    num = lambda k, v: clip01(b[k]) if isinstance(b.get(k), (int, float)) and not isinstance(b.get(k), bool) else v  # noqa: E731
    stake, urg, sur = num("stake", stake), num("urgency", urg), num("surprise", 0.0)
    h = _hours_to((e.get("msg") or {}).get("due"))
    if h is not None and h >= 0:
        urg = max(urg, clip01(1.0 - h / DUE_SPAN_H))
    p = welcome_p(app, e.get("why") or "")
    waited = max(0.0, now - float(e.get("at") or now))
    aged = clip01(urg + AGE_WEIGHT * min(1.0, waited / max(hold_s, 60.0)))
    item = str(e.get("item") or "")
    sal = salience(Bid(e["key"], "message", stake=stake * p, urgency=aged, surprise=sur), fatigue(ws, item, now))
    if item and item in stage:
        sal = round(sal * ON_MIND, 6)
    return {"key": e["key"], "src": "message", "salience": sal, "urgent": urg >= URGENT_AT, "at": e.get("at", now),
            "stake": round(stake * p, 4), "urgency": round(aged, 4), "welcome": round(p, 4)}  # fmt: skip


def _addon_bids(app: App, now: float) -> list[dict]:
    """What the add-ons bid this cycle, checked: an id and a kind (short ids), numbers 0..1, and a callable send."""
    out = []
    for name, fn in list(DOOR_BIDDERS.items()):
        try:
            got = fn(app, now) or []
        except Exception as e:  # one add-on failing never stops the door
            app.events.emit("workspace_bidder_failed", bidder=name, error=type(e).__name__)
            continue
        for b in list(got)[:12]:
            if not isinstance(b, dict) or not callable(b.get("send")):
                continue
            bid_id, kind = str(b.get("id") or ""), str(b.get("kind") or "")
            if not ID_RE.match(bid_id) or not ID_RE.match(kind):
                continue
            vals = {}
            for k, dflt in (("stake", 0.5), ("urgency", 0.5), ("surprise", 0.0)):
                v = b.get(k, dflt)
                vals[k] = clip01(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else dflt
            out.append({"key": f"addon:{name}:{bid_id}"[:80], "kind": kind, "send": b["send"], **vals})
    return out


def _rank(app: App, d: dict, addons: list[dict], now: float) -> list[dict]:
    """Every waiting message and add-on bid, highest salience first."""
    hold_s = _max_hold_s(app)
    ws = _state(app)
    stage = {w["item_id"] for w in ws["winners"]}
    ranked = [_score(app, e, now, stage, ws, hold_s) for e in d["pending"]]
    for b in addons:
        first = float((d["addons"].get(b["key"]) or {}).get("at") or now)
        aged = clip01(b["urgency"] + AGE_WEIGHT * min(1.0, (now - first) / max(hold_s, 60.0)))
        sal = salience(Bid(b["key"], b["kind"], stake=b["stake"], urgency=aged, surprise=b["surprise"]), 0.0)
        ranked.append({"key": b["key"], "src": "addon", "salience": sal, "urgent": b["urgency"] >= URGENT_AT,
                       "at": first, "stake": b["stake"], "urgency": round(aged, 4), "welcome": 1.0})  # fmt: skip
    ranked.sort(key=lambda x: (-x["salience"], x["at"]))
    return ranked


def _max_hold_s(app: App) -> float:
    from kurooto.mind import breaks

    return breaks.max_hold_s(app)


def _may_go(app: App, w: dict, now: float) -> str:
    """A winner goes now: why (for "Why this?"), or "" when it waits for a break."""
    from kurooto.mind import breaks

    if w["urgent"]:
        return "it was urgent"
    if breaks.deep_now(app, now) and now - float(w["at"]) < _max_hold_s(app):
        return "wait"  # (mind.workspace.deep_hold) you're deep in one thing: not even at a break
    if not breaks.wait_needed(app, now):
        return ""
    brk = breaks.open_now(app, now)
    if brk:
        return f"at a break: {breaks.label(brk)}"
    if now - float(w["at"]) >= _max_hold_s(app):
        return "it had waited as long as it may"
    return "wait"


def _went(w: dict, why: str, now: float, others: int) -> str:
    mins = int(max(0.0, now - float(w["at"])) // 60)
    waited = f"waited {mins} min at the door, then went" if mins >= 1 else "went at once"
    over = f"; it won over {others} other{'s' if others != 1 else ''}" if others else ""
    return f"{waited} ({why or 'nothing to wait for'}){over}"


def door(app: App, msg) -> tuple[bool, str]:
    """core/notify.py asks this after Brain's gate passed a message: (go now, what happened). A message that came by
    itself and isn't exempt bids here; it goes now only if it wins and needn't wait for a break, else it waits (and
    release() lets it out later). Never raises: anything going wrong lets the message through."""
    try:
        if not arbiter_on(app) or exempt(app, msg):
            return True, ""
        holder = _PASS.get()
        if holder is not None and not holder["used"]:
            holder["used"] = True
            return True, holder["note"]
        now = time.time()
        addons = _addon_bids(app, now)  # outside the lock: an add-on's code may take its time
        with Lock(app.paths.state, "mind-door"):
            d = _door(app)
            key = _key(msg)
            old = next((e for e in d["pending"] if e["key"] == key), None)
            e = {"key": key, "why": msg.why, "bkind": bid_kind(msg.why or "", msg.kind), "item": msg.item or "",
                 "at": old["at"] if old else round(now, 1), "lost": old["lost"] if old else 0, "msg": _dump(msg),
                 "bid": msg.bid if isinstance(getattr(msg, "bid", None), dict) else None}  # fmt: skip
            d["pending"] = [x for x in d["pending"] if x["key"] != key] + [e]
            ranked = _rank(app, d, addons, now)
            win = ranked[: capacity(app)]
            me = next((w for w in win if w["key"] == key), None)
            go = "" if me is None or asleep(app) else _may_go(app, me, now)
            if me is not None and go != "wait" and not asleep(app):
                d["pending"] = [x for x in d["pending"] if x["key"] != key]
                note = _went(me, go, now, len(ranked) - 1)
                _note(d, "went", note, msg.why or "")
                _door_save(app, d)
                return True, note
            why = "it's asleep" if asleep(app) else "waiting for a break" if me is not None else "something else won"
            _note(d, "held", why, msg.why or "")
            _door_save(app, d)
        app.events.emit("mind_door_held", why=why[:30])
        return False, ""
    except Exception as e:
        app.events.emit("mind_door_failed", error=f"{type(e).__name__}"[:60])
        return True, ""


def _relevant(app: App, e: dict, now: float) -> str:
    """Empty when a waiting message still matters, else why not (said in /mind gate, never dropped silently)."""
    m = e.get("msg") or {}
    if m.get("map_kind") == "ask" and m.get("map_ref"):
        try:
            from kurooto.core.ask import OPEN

            q = app.ask.get(str(m["map_ref"]))
            if not q or q.get("status") not in OPEN:
                return "its question was dealt with meanwhile"
        except Exception:
            pass
    h = _hours_to(m.get("due"))
    if h is not None and h < 0:
        return "its due time passed"
    return ""


def release(app: App) -> int:
    """Every minute and at each natural break: the top `capacity` of everything waiting win; a winner goes at a break,
    when it's urgent, or once it has waited `max_hold_min`, never while Kurooto is asleep. Losers stay and bid again;
    one that kept losing `fold_h` hours goes into the evening bundle. With the arbiter off, whatever still waits goes
    now. How many went."""
    if not mind.on(app):
        return 0
    if not arbiter_on(app):
        return flush(app)
    now = time.time()
    addons = _addon_bids(app, now)
    send: list[tuple[dict, str]] = []
    fold: list[dict] = []
    with Lock(app.paths.state, "mind-door"):
        d = _door(app)
        for e in list(d["pending"]):
            gone = _relevant(app, e, now)
            if gone:
                d["pending"].remove(e)
                _note(d, "dropped", gone, e.get("why") or "")
        live = {b["key"] for b in addons}
        d["addons"] = {k: v for k, v in d["addons"].items() if k in live}
        for b in addons:
            d["addons"].setdefault(b["key"], {"at": round(now, 1), "lost": 0})
        ranked = _rank(app, d, addons, now)
        cap = capacity(app)
        sleeping = asleep(app)
        fold_s = float(app.settings.get("mind.workspace.fold_h") or 6) * 3600
        by_key = {e["key"]: e for e in d["pending"]}
        for i, w in enumerate(ranked):
            if i < cap:
                go = "wait" if sleeping else _may_go(app, w, now)
                if go == "wait":
                    continue
                note = _went(w, go, now, len(ranked) - 1)
                if w["src"] == "message":
                    e = by_key.pop(w["key"])
                    send.append((e, note))
                    _note(d, "went", note, e.get("why") or "")
                else:
                    b = next(x for x in addons if x["key"] == w["key"])
                    d["addons"].pop(w["key"], None)
                    send.append(({"addon": b}, note))
                    _note(d, "went", note, w["key"])
                continue
            if w["src"] == "message":
                e = by_key[w["key"]]
                e["lost"] = int(e.get("lost", 0)) + 1
                if now - float(e["at"]) >= fold_s:
                    fold.append(by_key.pop(w["key"]))
            else:
                d["addons"][w["key"]]["lost"] = int(d["addons"][w["key"]].get("lost", 0)) + 1
        while len(by_key) > PENDING_MAX:  # far too many waiting: the oldest go to the bundle, never lost
            oldest = min(by_key.values(), key=lambda x: float(x["at"]))
            fold.append(by_key.pop(oldest["key"]))
        d["pending"] = list(by_key.values())
        for e in fold:
            _note(d, "folded", "kept losing for hours: into the evening bundle", e.get("why") or "")
        d["round_at"] = round(now, 1)
        _door_save(app, d)
    n = 0
    for e, note in send:
        n += _let_out(app, e, note)
    for e in fold:
        _fold(app, e)
    return n


def _let_out(app: App, e: dict, note: str) -> int:
    """Send one winner, past the door (through Brain's gate and Calm as usual)."""
    try:
        with passing(note):
            if "addon" in e:
                e["addon"]["send"]()
            else:
                m = dict(e["msg"])
                text = m.pop("text", "")
                app.notifier.send(text, **{k: v for k, v in m.items() if k in KEPT})
        return 1
    except Exception as x:
        app.events.emit("mind_door_failed", error=f"release: {type(x).__name__}"[:60])
        return 0


def _fold(app: App, e: dict) -> None:
    """Into the next evening bundle (core/calm.py); with Calm off it simply goes now, so nothing is lost."""
    m = dict(e["msg"])
    text = m.pop("text", "")
    why = m.pop("why", None)
    calm = getattr(app, "calm", None)
    try:
        if calm is not None and calm.on():
            calm.hold(text, why, held="workspace", **{k: v for k, v in m.items() if k in KEPT})
            app.events.emit("mind_door_folded", why=str(why or "")[:40])
            return
    except Exception as x:
        app.events.emit("mind_door_failed", error=f"fold: {type(x).__name__}"[:60])
    _let_out(app, e, "it waited hours, then went")


def flush(app: App) -> int:
    """Everything waiting goes now (the arbiter or Brain was turned off): nothing is kept back or lost."""
    with Lock(app.paths.state, "mind-door"):
        d = _door(app)
        out, d["pending"] = d["pending"], []
        if out:
            _note(d, "went", "the door was turned off", "")
            _door_save(app, d)
    return sum(_let_out(app, e, "went when the door was turned off") for e in out)


def held_count(app: App) -> int:
    """How many wait at the door now: messages and add-on bids (0 with the arbiter off)."""
    if not arbiter_on(app):
        return 0
    d = _door(app)
    return len(d["pending"]) + len(d["addons"])


def tick(app: App) -> list[dict]:
    """The minute's job (modules/mind.py): the stage's cycle, a look for breaks, the door's round, and Brain's
    expectations that ran out (mind/records.py). Each part has its own switch and none stops the others."""
    win = cycle(app)
    for part in ("breaks", "door", "records"):
        try:
            if part == "breaks":
                from kurooto.mind import breaks

                breaks.detect(app)
            elif part == "door":
                release(app)
            else:
                from kurooto.mind import records

                records.sweep(app)
        except Exception as e:
            app.events.emit("mind_door_failed", error=f"{part}: {type(e).__name__}"[:60])
    return win


def door_lines(app: App) -> list[str]:
    """For /mind gate: what waits at the door, the last break, and what the door did lately."""
    if not arbiter_on(app):
        return ["The door is off (mind.workspace.arbiter): messages go as they come, past the gate and Calm."]
    from kurooto.mind import breaks

    d = _door(app)
    t = time.time()
    out = []
    if d["pending"]:
        oldest = int((t - min(float(e["at"]) for e in d["pending"])) // 60)
        out.append(f"At the door: {len(d['pending'])} waiting (the oldest {oldest} min).")
    else:
        out.append("At the door: nothing waiting.")
    if d["addons"]:
        out.append(f"Add-on bids waiting: {len(d['addons'])}.")
    if not breaks.on(app):
        out.append("Natural breaks are off (mind.workspace.breaks): winners go at once.")
    elif not breaks.sensing(app):
        out.append("Nothing can see a break coming (no activity or phone screen sense, no Face): winners go at once.")
    else:
        b = breaks.last(app)
        if b.get("at"):
            at = dt.datetime.fromtimestamp(float(b["at"]))
            out.append(f"Last break: {breaks.label(b.get('kind'))} at {at:%a %H:%M}.")
    for s in d["seen"][-5:]:
        out.append(f"- {dt.datetime.fromtimestamp(s['at']):%a %H:%M} {s['what']}: {s['why']}")
    return out
