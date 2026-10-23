"""Dream RSI, part two: the rules for when Kurooto reaches you by itself, tuned each night by replaying what happened.

The policy is a few parameters per kind of message (a Calm reason, core/calm.py), read from today's settings:
    evening    the kind always waits for the evening bundle (notify.calm.evening)
    habituate  after N in a row you left unanswered, it waits for the evening until you answer one
               (notify.calm.habituate: getting used to things)
    windows    the hours it may come in; outside them it waits for the evening (notify.calm.windows)
Everything else is yours and a hard constraint, never tuned: the daily limit, stopped and fewer, exam season, the
evening time, quiet and night hours, kinds that always come (the alarm, your reminders and calls, approvals, a
deadline under 12 hours), kinds that can't wait (Reason.later False) and dreaming.never_tune.

The record is calm.db (every message that came by itself, kept 45 days: all of it is replayed, so the pool grows to
that) and "Less of this" taps from the event log. replay() decides for each recorded message whether a policy would
have sent it then or let it wait for that evening, and scores it with what was recorded only: it can move a message,
never invent an answer, and it can't judge messages that never came or that had nothing to answer:
    answered, and still in time (it came, or the bundle came before you answered)   +ANSWERED
    answered before that evening, but the policy would have held it                 -DELAYED (-DELAYED_QUICK if
                                                                                      answered within QUICK_MIN)
    unanswered, and it interrupted you                                              -IGNORED
    unanswered, in the evening bundle                                               -IGNORED_BUNDLED
    "Less of this" tapped on it, and it interrupted you                             -LESS
    minus the lever's own cost for a policy that differs from today's               CHANGE[lever]

Each morning Dreaming calls morning() before its message: tune() proposes variants by rules (one setting each, for
the kinds most often ignored: habituation N in HABITUATE_N, the evening bundle, the hours they were answered in), keeps
today's policy as a candidate, replays all of them on the whole record and applies the best only if it beats today's by
dreaming.tune_margin. So it's never worse on the replay, and it changes at most one setting a night, through
Calm.apply (with Undo). A kind whose change was undone or reverted is left alone for BLOCK_DAYS. Every night's
decision is kept in <state>/dream-policy.json; /dream policy shows them.

To add a lever: a Calm setting that _wait() reads (the runtime), its line in Candidate.place() (the replay), its
proposals in propose() with a CHANGE cost and a said() text, and a test in tests/unit/test_dream_policy.py.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from kurooto.core.calm import REASONS, Change, inside, streak
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "dreaming",
    {
        "tune_messages": True,  # each night, replay the messages it sent you and tune when they come (one change, Undo)
        "tune_margin": 3.0,  # how much better (in the replay's score) a change must be than leaving things as they are
        "never_tune": [
            "deadlines.reminder",
            "deadlines.call",
            "health.now",
            "ai.limit",
            "google.signin",
            "kurooto.crash",
            "dreaming.morning",
        ],  # kinds it never tunes (besides the alarm, your reminders and calls, deadlines under 12 hours)
    },
)

ANSWERED, DELAYED, DELAYED_QUICK, IGNORED, IGNORED_BUNDLED, LESS = 1.0, 5.0, 10.0, 1.0, 0.2, 2.0
CHANGE = {"habituate": 0.5, "window": 0.75, "evening": 1.0}  # habituation undoes itself once you answer: cheapest
QUICK_MIN = 30
HABITUATE_N = (2, 3, 5)
MIN_SEEN = 5  # a kind needs this many judged messages...
MIN_IGNORED = 3  # ...and this many that interrupted you unanswered, before anything is proposed for it
TOP_KINDS = 3  # variants for the kinds most often ignored
BLOCK_DAYS = 30
KEEP_DECISIONS = 30
BY = "dreaming.policy"  # what Calm records as the change's cause (calm_less, its Undo); not a message reason
KEYS = {"evening": "notify.calm.evening", "habituate": "notify.calm.habituate", "window": "notify.calm.windows"}


@dataclass
class Row:
    """One recorded message: when, its reason, how it went (now or bundled, and why it waited) and what you did."""

    ts: float
    why: str
    bundled: bool
    held: str
    answered: float | None
    answerable: bool
    less: bool = False

    @property
    def t(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.ts)


@dataclass
class Candidate:
    evening: frozenset = frozenset()
    habituate: dict = field(default_factory=dict)
    windows: dict = field(default_factory=dict)
    lever: str = ""  # "" for today's own policy
    kind: str = ""
    value: object = None

    def place(self, row: Row, ignored: int, evening: dt.datetime) -> str:
        """ "now" or "evening": where this policy would have put a recorded message (`ignored` in a row before it)."""
        if row.t >= evening:
            return "now"  # after the bundle, messages come as they are
        if row.bundled and row.held not in ("evening", "habit", "window"):
            return "evening"  # the daily limit, fewer, exam season: yours, not the policy's
        if row.why in self.evening:
            return "evening"
        window = self.windows.get(row.why)
        if window and not inside(window, row.t):
            return "evening"
        n = self.habituate.get(row.why)
        return "evening" if n and ignored >= int(n) else "now"

    def said(self) -> str:
        r = REASONS.get(self.kind)
        plural = r.plural if r else self.kind
        if self.lever == "evening":
            return f"{plural} now wait for your evening bundle"
        if self.lever == "habituate":
            return f"{plural} wait for your evening bundle once {self.value} in a row go unanswered"
        if self.lever == "window":
            return f"{plural} come only {self.value}; at other times they wait for your evening bundle"
        return "as it was"

    def change(self) -> Change:
        if self.lever == "evening":
            return Change(self.said(), key=KEYS["evening"], value=sorted(self.evening))
        return Change(
            self.said(), key=KEYS[self.lever], value=self.habituate if self.lever == "habituate" else self.windows
        )


def today(app: App) -> Candidate:
    s = lambda k: app.settings.get(f"notify.calm.{k}")  # noqa: E731
    return Candidate(frozenset(s("evening") or []), dict(s("habituate") or {}), dict(s("windows") or {}))


def record(app: App) -> list[Row]:
    """The messages that came by themselves and that a policy may move, oldest first, with your Less-of-this taps."""
    with app.calm._db() as db:
        got = db.execute(
            "select ts, why, state, held, answered, buttons, map_kind from sent where kind!='ring' and why!='' and "
            "state in ('sent','bundled') and coalesce(exempt,'')='' order by ts, rowid"
        ).fetchall()
    rows = [
        Row(float(ts), why, state == "bundled", held or "", a, buttons not in ("", "[]", None) or bool(mk))
        for ts, why, state, held, a, buttons, mk in got
        if why in REASONS
    ]
    for e in app.events.tail(20000, kinds={"calm_less"}):
        try:
            at = dt.datetime.fromisoformat(e["ts"]).timestamp()
        except (KeyError, ValueError):
            continue
        hit = [r for r in rows if r.why == e.get("why") and at - 86400 <= r.ts <= at]
        if hit:
            hit[-1].less = True
    return rows


def tunable(why: str, never: set[str]) -> bool:
    r = REASONS.get(why)
    return bool(r and not r.exempt and r.later and why not in never)


def never_tuned(app: App) -> set[str]:
    return set(app.settings.get("dreaming.never_tune") or [])


@dataclass
class Replay:
    score: float = 0.0
    saved: int = 0  # unanswered interruptions it would have moved to the evening (vs. today's policy)
    delayed: int = 0  # answered ones it would have held past when you answered (vs. today's policy)
    judged: int = 0


def replay(app: App, c: Candidate, rows: list[Row], base: Candidate | None = None) -> Replay:
    """Score a policy on the record (see the module's notes). With base, also count what it saves and delays."""
    out = Replay()
    past: dict[str, list[tuple[float, float | None]]] = {}  # per kind, newest first: what streak() reads
    never, at = never_tuned(app), app.calm.evening_at().time()
    for row in rows:
        if not tunable(row.why, never) or not (row.answerable or row.less):
            continue
        evening = dt.datetime.combine(row.t.date(), at)
        prev = past.setdefault(row.why, [])
        ignored = streak(prev, row.ts) if row.answerable else 0
        p = c.place(row, ignored, evening)
        b = base.place(row, ignored, evening) if base is not None else p
        if row.answerable:
            prev.insert(0, (row.ts, row.answered))
        out.judged += 1
        if row.answered is not None:
            late = p == "evening" and not row.bundled and row.answered < evening.timestamp()
            if late:
                quick = row.answered - row.ts <= QUICK_MIN * 60
                out.score -= DELAYED_QUICK if quick else DELAYED
                out.delayed += b == "now"
            else:
                out.score += ANSWERED
        elif row.answerable:
            out.score -= IGNORED if p == "now" else IGNORED_BUNDLED
            out.saved += p == "evening" and b == "now"
        if row.less and p == "now":
            out.score -= LESS
    if c.lever:
        out.score -= CHANGE[c.lever]
    return out


def blocked(app: App, st: dict) -> set[str]:
    """Kinds whose change from here was undone (or put back by hand) in the last BLOCK_DAYS days."""
    cutoff, out = now() - dt.timedelta(days=BLOCK_DAYS), set()
    for d in st.get("decisions") or []:
        if not d.get("applied") or dt.datetime.fromisoformat(d["at"]) < cutoff:
            continue
        if not live(app, d):
            out.add(d["kind"])
    return out


def propose(app: App, cur: Candidate, rows: list[Row], skip: set[str]) -> list[Candidate]:
    """The variants: one setting each, for the kinds you most often left unanswered (none you've set yourself)."""
    taken = set(cur.evening) | set(cur.habituate) | set(cur.windows) | skip
    taken |= set(app.settings.get("notify.calm.stopped") or []) | set(app.settings.get("notify.calm.fewer") or {})
    stats: dict[str, dict] = {}
    never = never_tuned(app)
    for row in rows:
        if row.why in taken or not tunable(row.why, never) or not row.answerable:
            continue
        s = stats.setdefault(row.why, {"n": 0, "ignored": 0, "hours": []})
        s["n"] += 1
        if row.answered is None and not row.bundled:
            s["ignored"] += 1
        elif row.answered is not None and not row.bundled:
            s["hours"].append(row.t.hour)
    kinds = [k for k, s in stats.items() if s["n"] >= MIN_SEEN and s["ignored"] >= MIN_IGNORED]
    kinds.sort(key=lambda k: (-stats[k]["ignored"], k))
    out = []
    for k in kinds[:TOP_KINDS]:
        out += [
            replace(cur, habituate={**cur.habituate, k: n}, lever="habituate", kind=k, value=n) for n in HABITUATE_N
        ]
        out.append(replace(cur, evening=cur.evening | {k}, lever="evening", kind=k, value=True))
        hours = stats[k]["hours"]
        if len(hours) >= 2:
            lo, hi = min(hours), max(hours) + 1
            window = f"{lo:02d}:00-{hi:02d}:00" if hi < 24 else f"{lo:02d}:00-23:59"
            if lo > 0 or hi < 24:
                out.append(replace(cur, windows={**cur.windows, k: window}, lever="window", kind=k, value=window))
    return out


def state_file(app: App):
    return app.paths.state / "dream-policy.json"


def consider(app: App) -> tuple[dict, Change | None] | None:
    """Tonight's round, without applying anything: replay today's policy and its variants on the whole record. (the
    decision, the best variant's change or None), or None when there is no round (off, Calm off, done today)."""
    if not app.settings.get("dreaming.tune_messages") or not app.calm.on():
        return None
    st = jload(state_file(app), {}) or {}
    if st.get("day") == now().date().isoformat():
        return None  # one round (and at most one change) a night
    rows = record(app)
    cur = today(app)
    base = replay(app, cur, rows)
    best, best_r = cur, base
    cands = propose(app, cur, rows, blocked(app, st))
    for c in cands:
        r = replay(app, c, rows, base=cur)
        if r.score > best_r.score:  # ties keep today's
            best, best_r = c, r
    days = max(1, round((now().timestamp() - rows[0].ts) / 86400)) if rows else 0
    d = {
        "at": now().isoformat(timespec="seconds"),
        "candidates": len(cands) + 1,
        "judged": base.judged,
        "days": days,
        "score": round(base.score, 2),
        "best": round(best_r.score, 2),
        "applied": False,
    }
    if best.lever:
        d.update(kind=best.kind, lever=best.lever, value=best.value, said=best.said())
        d.update(saved=best_r.saved, delayed=best_r.delayed)
    return d, (best.change() if best.lever else None)


def settle(app: App, d: dict, change: Change | None, apply: bool, why: str = BY) -> dict:
    """Keep tonight's decision (and apply its change when `apply`, through Calm, with Undo)."""
    if apply and change is not None:
        ok, _said, uid = app.calm.apply(change, why=why)
        d.update(applied=ok, uid=uid)
    st = jload(state_file(app), {}) or {}
    st["day"] = now().date().isoformat()
    st["decisions"] = [*(st.get("decisions") or []), d][-KEEP_DECISIONS:]
    jsave(state_file(app), st)
    app.events.emit("dreaming_policy", applied=d["applied"], kind=d.get("kind", ""), gain=d["best"] - d["score"])
    return d


def tune(app: App) -> dict | None:
    """Tonight's round on its own: apply the best variant if it beats today's by dreaming.tune_margin. Once a day.
    Returns the decision (also kept), or None when there was no round. Dreaming's morning goes through
    core/tuning.py:night instead, which weighs this against the other areas (one change a night in all)."""
    got = consider(app)
    if got is None:
        return None
    d, change = got
    margin = float(app.settings.get("dreaming.tune_margin") or 0)
    return settle(app, d, change, change is not None and d["best"] - d["score"] >= margin)


def morning(app: App, send: bool = True) -> tuple[list[str], list | None]:
    """Dreaming's hook: (its line for the morning message, its Undo button). Tunes only for the sent message; /dream
    shows today's decision again."""
    try:
        if send:
            d = tune(app)
        else:
            last = ((jload(state_file(app), {}) or {}).get("decisions") or [None])[-1]
            d = last if last and last["at"][:10] == now().date().isoformat() else None
    except Exception as e:  # tuning must not cost the morning message
        app.events.emit("dreaming_policy_failed", error=f"{type(e).__name__}: {e}"[:200])
        return [], None
    if not d or not d.get("applied"):
        return [], None
    return [line(d)], [[("Undo", f"calm:{d['uid']}:undo")]]


def line(d: dict) -> str:
    """The morning message's line for an applied decision."""
    s = "s" if d["saved"] != 1 else ""
    return (
        f"Learned while you slept: {d['said']}; over the last {d['days']} days that would have saved {d['saved']} "
        f"ignored ping{s} and delayed {d['delayed'] or 'none'} you answered."
    )


def applied_today(app: App) -> dict | None:
    """Today's decision when it changed something (for the morning message and /dream)."""
    last = ((jload(state_file(app), {}) or {}).get("decisions") or [None])[-1]
    ok = last and last.get("applied") and last["at"][:10] == now().date().isoformat()
    return last if ok else None


def live(app: App, d: dict) -> bool:
    """Is an applied decision's change still in place (not undone or put back by hand)?"""
    cur, k = today(app), d.get("kind")
    lever = d.get("lever")
    if lever == "evening":
        return k in cur.evening
    return k in (cur.habituate if lever == "habituate" else cur.windows)


def show(app: App) -> str:
    """/dream policy: today's policy, what's never tuned, and the last decisions with their replay scores."""
    cur = today(app)
    plural = lambda k: REASONS[k].plural if k in REASONS else k  # noqa: E731
    on = "on" if app.settings.get("dreaming.tune_messages") else "off (dreaming.tune_messages)"
    lines = [f"When messages that come by themselves reach you. Tuned while dreaming: {on}."]
    if cur.evening:
        lines.append("Always the evening bundle: " + ", ".join(plural(k) for k in sorted(cur.evening)) + ".")
    if cur.habituate:
        bits = [f"{plural(k)} after {n}" for k, n in cur.habituate.items()]
        lines.append("Evening once that many in a row go unanswered: " + ", ".join(bits) + ".")
    if cur.windows:
        lines.append("Only at these hours: " + ", ".join(f"{plural(k)} {w}" for k, w in cur.windows.items()) + ".")
    if len(lines) == 1:
        lines.append("Every kind comes as it happens (within the daily limit, /calm).")
    never = app.settings.get("dreaming.never_tune") or []
    lines.append(
        f"Never tuned: the alarm, your reminders and calls, approvals, deadlines under 12 hours, and {len(never)} "
        "more (dreaming.never_tune)."
    )
    ds = (jload(state_file(app), {}) or {}).get("decisions") or []
    if ds:
        lines.append("Last nights (replay score: as it was / best variant):")
    for d in ds[-5:][::-1]:
        when = dt.datetime.fromisoformat(d["at"])
        what = d["said"] if d.get("applied") else "kept as it was" + (f" (best: {d['said']})" if d.get("said") else "")
        lines.append(f"- {when:%a %d %b}: {what}; {d['score']:+.1f} / {d['best']:+.1f}, {d['candidates']} tried.")
    return "\n".join(lines)
