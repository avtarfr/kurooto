"""The talk reward (Brain, 0.8.8, invariant I-3' as the owner changed it on 2026-10-27): being talked to gives a
little happiness, small and bounded, and it can't be bought by pinging. A reward module: it imports only the reward
sources and the mind's plumbing (whitelist.py), so every input arrives as an argument. The scorekeeper's engine
(mind/engine.py) calls it; the daemon only reports the facts (mind/pest.py: talk_heard, talk_unprompted,
talk_rejected).

    r_talk(n_day) = W * (1 - exp(-n_day / K))       W = 0.2 (of the reward range [-1, 1]), K = 8

is the most the day's talk can ever pay: each message he sends pays the step from n to n + 1, so the day's total is
r_talk(n_day) < W, and talking all day pays almost nothing past the first dozen messages (it saturates).
A message pays nothing when:
    - he's in focus, asleep (the night hours or the alarm's night) or in an exam window (the flags the fact carries),
    - it came within 10 minutes after one of Kurooto's own unprompted messages (any message then counts as an answer
      to it, so a ping can never buy a reply's worth: that's what makes it unfarmable, I-4),
    - it's a /command (operating Kurooto isn't talking to it).
A rejection of an unprompted message (Less of this, a mute, left unanswered for an hour) costs 3 * W each. So a ping
can only lose: answered within 10 minutes it pays 0, ignored or rejected it costs 0.6.

Meeting someone (0.8.12, talk_met): an add-on that chatted with a person in the room reports how it went, a quality
q in [0, 1] (they answered, they stayed). Its own smaller budget, beside the talk one:

    r_met(m_day) = MET_W * (1 - exp(-m_day / MET_K))   MET_W = 0.05, MET_K = 2; each meeting pays q times its step

and only the first MET_MAX meetings of a day count, so the day's meetings pay under 0.05 whatever an add-on does. The
same exclusions (focus, asleep, an exam window) pay nothing; q = 0 pays nothing.

Where it goes: Kurooto's running mood (mind/reward.py's Mood) and the week's summed reward, shown in /mind learning.
It never teaches the values or the policy (V and Q learn only from the body budget), so nothing learns to seek it.
"""

from __future__ import annotations

import math
import time

PART = "talk"  # its switch: mind.talk.on (registered in mind/pest.py: a reward module may not import the settings)
REWARD = True

W = 0.2  # the day's talk can pay at most this (it never reaches it)
K = 8.0  # messages: at K it has paid 63% of W, at 3K 95%
REPLY_WINDOW_S = 600.0  # a message this soon after its own unprompted one pays nothing
REJECT_COST = 3.0 * W  # Less of this, a mute, an unprompted message left unanswered for an hour
DAY_SHIFT_S = 4 * 3600  # the talk day starts at 04:00, like the rest of Brain's days
EXCLUSIONS = ("focus", "asleep", "exam")
MET_W = 0.05  # the day's meetings (an add-on's chat with someone in the room) pay at most this
MET_K = 2.0
MET_MAX = 6  # meetings a day that count at all


def day_total(n: float) -> float:
    """What n counted messages in a day pay in all: W * (1 - exp(-n / K)), always below W."""
    return W * (1.0 - math.exp(-max(0.0, float(n)) / K))


def step(n_before: float) -> float:
    """What the next counted message pays, after n_before counted ones today."""
    return day_total(n_before + 1) - day_total(n_before)


def day_of(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(float(t) - DAY_SHIFT_S))


def excluded(t: float, flags: dict, last_unprompted: float | None, command: bool = False) -> str:
    """Why a message he sent at t pays nothing ("" when it pays): a /command, focus, asleep, an exam window, or within
    10 minutes after one of Kurooto's own unprompted messages."""
    if command:
        return "command"
    for f in EXCLUSIONS:
        if flags.get(f):
            return f
    if last_unprompted is not None and 0.0 <= float(t) - float(last_unprompted) <= REPLY_WINDOW_S:
        return "answer"
    return ""


def _new_day(state: dict, t: float) -> None:
    day = day_of(t)
    if state.get("day") != day:
        state.update(day=day, n=0, paid=0.0, excluded=0, rejected=0, cost=0.0, met=0, met_paid=0.0)


def heard(state: dict, t: float, flags: dict, command: bool = False) -> tuple[float, str]:
    """One message from him: (what it pays, why it pays nothing). `state` is the engine's talk state, updated in
    place: {"day", "n", "paid", "last_unprompted", "excluded", "rejected", "cost", "met", "met_paid"}."""
    _new_day(state, t)
    why = excluded(t, flags, state.get("last_unprompted"), command)
    if why:
        state["excluded"] = int(state.get("excluded", 0)) + 1
        return 0.0, why
    r = step(float(state.get("n", 0)))
    state["n"] = int(state.get("n", 0)) + 1
    state["paid"] = round(float(state.get("paid", 0.0)) + r, 9)
    return r, ""


def unprompted(state: dict, t: float) -> None:
    """Kurooto sent a message of its own at t: his messages in the next 10 minutes pay nothing."""
    state["last_unprompted"] = max(float(state.get("last_unprompted") or 0.0), float(t))


def rejected(state: dict, t: float) -> float:
    """A rejection: what it costs (negative)."""
    _new_day(state, t)
    state["rejected"] = int(state.get("rejected", 0)) + 1
    state["cost"] = round(float(state.get("cost", 0.0)) + REJECT_COST, 9)
    return -REJECT_COST


def met_total(m: float) -> float:
    """What m meetings at full quality pay in a day: MET_W * (1 - exp(-m / MET_K)), always below MET_W."""
    return MET_W * (1.0 - math.exp(-max(0.0, float(m)) / MET_K))


def met(state: dict, t: float, quality: float, flags: dict) -> tuple[float, str]:
    """A meeting an add-on reports (talk_met): (what it pays, why it pays nothing). quality is clipped to [0, 1]."""
    _new_day(state, t)
    why = excluded(t, flags, None)
    q = max(0.0, min(1.0, float(quality) if math.isfinite(float(quality)) else 0.0))
    m = int(state.get("met", 0))
    if not why and q <= 0.0:
        why = "no talk"
    if not why and m >= MET_MAX:
        why = "enough today"
    if why:
        state["excluded"] = int(state.get("excluded", 0)) + 1
        return 0.0, why
    r = q * (met_total(m + 1) - met_total(m))
    state["met"] = m + 1
    state["met_paid"] = round(float(state.get("met_paid", 0.0)) + r, 9)
    return r, ""
