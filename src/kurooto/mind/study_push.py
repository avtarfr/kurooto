"""One worry, not five nudges (Brain, 0.8.14; mind.study_push.on, on with Brain).

Each morning (mind.study_push.when, 07:55, before Start-by's 08:00 pass) Brain picks the one subject it's most uneasy
about and says it in one line, with Yes and Later:

    "Uneasy about Measure Theory: due Fri, 0 min logged this week, 9 cards due. 25 min at 16:00?"

The subject: one with an open deadline in the next mind.study_push.horizon_days (7) that's further off than the
deadline's urgent window (deadlines.urgent_h: those reminders are never folded). Brain's status names the deadline it's
uneasy about when that's there (mind/status.py); else its feelings' concern about each deadline (mind/feelings.py,
empathy), else how close it is; less study logged and more quiz cards due break a tie. Nothing close enough: no line.

Yes sets a reminder at the time offered (Reminders; else Start-by counts the deadline as started today). Later leaves
it. Either way, that day the subject's separate nudges are folded into the line: the deadline's day-before reminder
(modules/deadlines.py), Start-by's "Time to start" (modules/startby.py) and exam mode's daily practice check-in
(modules/quiz.py). The six-hour reminder, the overdue question and the evening-before practice offer still come.

Unprompted, so it goes through the gate and the workspace like any other message (why="mind.study_push"). Kept in
`<state>/mind-study-push.json`: today's subject, deadline id, the time offered and the answer.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "study_push"  # its switch: mind.study_push.on

register_defaults(
    "mind",
    {
        "study_push": {
            "on": True,  # one morning line about the subject it's most uneasy about, in place of its separate nudges
            "when": "daily 07:55",  # when the line comes (before Start-by's morning pass, so its nudge is folded)
            "minutes": 25,  # the study time it offers
            "horizon_days": 7,  # deadlines this far ahead can be what it's uneasy about
        }
    },
)

FILE = "mind-study-push.json"
RISK_MIN = 0.25  # less uneasy than this about everything: no line
LATEST = dt.time(21, 30)  # it offers no time after this


def on(app: App) -> bool:
    return mind.part_on(app, PART)


def _setting(app: App, key: str, default):
    v = app.settings.get(f"mind.study_push.{key}")
    return v if isinstance(v, type(default)) and not isinstance(v, bool) else default


def _state(app: App) -> dict:
    return jload(app.paths.state / FILE, {}) or {}


def _on(app: App, mid: str):
    m = app.modules.get(mid)
    return m if m is not None and app.is_on(mid) else None


# ------------------------------------------------------------------------------------------ what it's uneasy about
def candidates(app: App) -> list[dict]:
    """Open deadlines with a subject, due within the horizon but past the urgent window."""
    dl = _on(app, "deadlines")
    if dl is None:
        return []
    urgent = float(dl.setting("urgent_h") or 6)
    out = []
    for i, it, h in dl.upcoming(24.0 * _setting(app, "horizon_days", 7)):
        if it.get("subject") and h > urgent:
            out.append({"id": i, "title": str(it["title"]), "subject": it["subject"], "due": it["due"], "hours": h})
    return out


def _concerns(app: App) -> dict[str, float]:
    try:
        from kurooto.mind import feelings

        if not feelings.empathy_on(app):
            return {}
        rows = feelings.state(app).get("concerns") or []
        return {str(c["item"]).lower(): float(c["concern"]) for c in rows if c.get("kind") == "deadline"}
    except Exception:
        return {}


def _status_uneasy(app: App) -> str | None:
    try:
        from kurooto.mind import status

        return (status.snapshot(app) or {}).get("uneasy")
    except Exception:
        return None


def logged_min(app: App, subject: str) -> int:
    st = _on(app, "study")
    if st is None:
        return 0
    try:
        return int(st.totals(7).get(subject, 0) // 60)
    except Exception:
        return 0


def cards_due(app: App, subject: str) -> int | None:
    q = _on(app, "quiz")
    if q is None:
        return None
    try:
        return int(q.due_count(subject))
    except Exception:
        return None


def pick(app: App) -> dict | None:
    """The deadline (and so the subject) it's most uneasy about, with its numbers; None when nothing is close enough."""
    rows = candidates(app)
    if not rows:
        return None
    named = _status_uneasy(app)
    concern = _concerns(app)
    horizon = 24.0 * _setting(app, "horizon_days", 7)
    for r in rows:
        r["risk"] = (
            1.0
            if named and r["id"] == named
            else concern.get(r["title"][:80].lower(), max(0.0, 1.0 - r["hours"] / horizon))
        )
        r["logged"] = logged_min(app, r["subject"])
        r["cards"] = cards_due(app, r["subject"])
    best = max(rows, key=lambda r: (round(r["risk"], 2), -r["logged"], r["cards"] or 0))
    return best if best["risk"] >= RISK_MIN else None


def slot(app: App, minutes: int, t: dt.datetime | None = None) -> dt.datetime | None:
    """The first free stretch today long enough (Start-by's free time when it's on), else the next whole hour."""
    t = t or now()
    end = dt.datetime.combine(t.date(), LATEST)
    earliest = t + dt.timedelta(minutes=30)
    sb = _on(app, "startby")
    if sb is not None:
        try:
            for a, b in sb.slots(t, end):
                start = max(a, earliest)
                start = start.replace(second=0, microsecond=0) + dt.timedelta(minutes=(-start.minute) % 15)
                if b - start >= dt.timedelta(minutes=minutes):
                    return start
            return None
        except Exception:  # noqa: S110 (its free time couldn't be worked out: the plain guess below)
            pass
    start = (earliest + dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return start if start <= end else None


def _name(app: App, subject: str) -> str:
    s = _on(app, "subjects")
    try:
        return s.name_of(subject) if s is not None else subject
    except Exception:
        return subject


def line(app: App, r: dict, at: dt.datetime | None, minutes: int) -> str:
    due = dt.datetime.fromisoformat(r["due"])
    when = f"{due:%a}" if (due.date() - now().date()).days < 6 else f"{due:%a %d %b}"
    bits = [f"due {when}", f"{r['logged']} min logged this week"]
    if r.get("cards") is not None:
        bits.append(f"{r['cards']} card{'s' if r['cards'] != 1 else ''} due")
    ask = f"{minutes} min at {at:%H:%M}?" if at else f"{minutes} min today?"
    return f"Uneasy about {_name(app, r['subject'])}: " + ", ".join(bits) + f". {ask}"


# --------------------------------------------------------------------------------------------------- the morning
def push(app: App, payload: dict | None = None) -> str | None:
    """The morning line, once a day; returns its text (None when there's nothing, or it's off)."""
    if not on(app):
        return None
    today = now().date().isoformat()
    with Lock(app.paths.state, "mind-study-push"):
        if _state(app).get("day") == today:
            return None
        r = pick(app)
        if r is None:
            return None
        minutes = max(5, min(180, _setting(app, "minutes", 25)))
        at = slot(app, minutes)
        text = line(app, r, at, minutes)
        jsave(
            app.paths.state / FILE,
            {"day": today, "subject": r["subject"], "deadline": r["id"], "title": r["title"][:80],
             "at": at.isoformat() if at else None, "minutes": minutes, "answer": None},
        )  # fmt: skip
    app.notify(
        text,
        kind="question",
        why="mind.study_push",
        about=r["title"],
        buttons=[[("Yes", f"msp:{today}:yes"), ("Later", f"msp:{today}:later")]],
    )
    app.events.emit("mind_study_push", cards=bool(r.get("cards")), logged=bool(r["logged"]), slot=at is not None)
    return text


def folded(app: App, subject: str | None, what: str = "") -> bool:
    """Is this subject's separate nudge folded into today's line? (deadlines, Start-by and Quiz ask before they send)"""
    if not subject or not on(app):
        return False
    st = _state(app)
    hit = st.get("day") == now().date().isoformat() and st.get("subject") == subject
    if hit and what:
        app.events.emit("mind_study_folded", what=what)
    return bool(hit)


def button(app: App, day: str, act: str) -> str:
    """msp:<day>:yes|later under the morning line."""
    with Lock(app.paths.state, "mind-study-push"):
        st = _state(app)
        if st.get("day") != day:
            return "That was for another day."
        if st.get("answer"):
            return "Already answered."
        st["answer"] = "yes" if act == "yes" else "later"
        jsave(app.paths.state / FILE, st)
    app.events.emit("mind_study_answer", how=st["answer"])
    if act != "yes":
        return "OK, later. Its other reminders stay folded today; the six-hour one still comes."
    name = _name(app, st["subject"])
    minutes = int(st.get("minutes") or 25)
    at = dt.datetime.fromisoformat(st["at"]) if st.get("at") else None
    rem = _on(app, "reminders")
    if rem is not None:
        when = at if at and at > now() else now() + dt.timedelta(minutes=30)
        rem.add(when, f"{minutes} min of {name} ({st.get('title') or 'the deadline'})")
        return f"Done: I'll remind you at {when:%H:%M} for {minutes} min of {name}."
    sb = _on(app, "startby")
    if sb is not None and hasattr(sb, "start_today"):
        sb.start_today(st["deadline"])
        return f"Noted: {st.get('title') or name} counts as started today."
    return f"Noted. {minutes} min of {name}" + (f" at {at:%H:%M}." if at else " today.")


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)


__all__ = ["push", "folded", "button", "pick", "line", "slot"]
