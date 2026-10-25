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

Words (an item's text) stay in `<state>/mind-workspace.json`; the log gets ids and numbers.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
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
        },
        "attention": {"on": True},  # a model of its own attention; "what are you thinking about?" is answered from it
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
    that item to have won one of the last two cycles. A message with no such item is not held to it."""
    item = str(getattr(msg, "item", "") or "")
    if not on(app) or item.split(":", 1)[0] not in ITEM_PREFIXES or ":" not in item:
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
