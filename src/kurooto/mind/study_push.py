"""One worry, not five nudges (Brain, 0.8.14; mind.study_push.on, on with Brain).

Each morning (mind.study_push.when, 07:55, before Start-by's 08:00 pass) Brain picks the one subject it's most uneasy
about and says it in one line, with Yes and Later:

    "Uneasy about Measure Theory: due Fri, 0 min logged this week, 9 cards due. 25 min at 16:00?"

The subject: one with an open deadline in the next mind.study_push.horizon_days (7) that's further off than the
deadline's urgent window (deadlines.urgent_h: those reminders are never folded). Brain's status names the deadline it's
uneasy about when that's there (mind/status.py); else its feelings' concern about each deadline (mind/feelings.py,
empathy), else how close it is; less study logged and more quiz cards due break a tie. Nothing close enough: no line.

Yes sets a reminder at the time offered (Reminders; else Start-by counts the deadline as started today). Later leaves
it. With mind.study_push.start_timer (on, 0.9.0) that reminder carries "Start 25 min": Study mode's timer for the
subject, tied to the deadline (modules/study.py), started only by that tap; Study mode opens on that subject too.
Either way, that day the subject's separate nudges are folded into the line: the deadline's day-before reminder
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
            # (0.9.0) the reminder a Yes sets has a "Start 25 min" button (Study mode's timer, for that deadline), and
            # Study mode and a tap on the uneasy glow pick that subject; the timer starts only on your tap
            "start_timer": True,
            "frontier": False,  # equally uneasy: the subject with concepts you are ready for; the line names one
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
        r["next"] = next_concepts(app, r["subject"])
    best = max(rows, key=lambda r: (round(r["risk"], 2), len(r["next"]), -r["logged"], r["cards"] or 0))
    return best if best["risk"] >= RISK_MIN else None


def next_concepts(app: App, subject: str) -> list[str]:
    """mind.study_push.frontier (0.9.0, off): the titles of the subject's concepts at your frontier (mind/frontier.py;
    a concept is the subject's when its note sits in a folder named after it). Used only after deadline risk, to break
    a tie, and to name one in the line. Else none."""
    if app.settings.get("mind.study_push.frontier") is not True:
        return []
    try:
        from kurooto.mind import frontier
        from kurooto.mind.tom import knowledge

        grades = frontier.grades(app)
        if not grades:
            return []
        notes = knowledge.concepts(app)
        mine = [s for s, g in grades.items() if g == frontier.FRONTIER and subject in s.split("/")[:-1] and s in notes]
        return [notes[s].title for s in sorted(mine)][:3]
    except Exception:
        return []


def slot(app: App, minutes: int, t: dt.datetime | None = None) -> dt.datetime | None:
    """The first free stretch today long enough (Start-by's free time when it's on), else the next whole hour."""
    t = t or now()
    end = dt.datetime.combine(t.date(), LATEST)
    earliest = t + dt.timedelta(minutes=30)
    sb = _on(app, "startby")
    if sb is not None:
        try:
            rank = sb.rank() if hasattr(sb, "rank") else None  # 0.9.0: mind.presence_forecast.plan
            fits, need = [], dt.timedelta(minutes=minutes)
            for a, b in sb.slots(t, end):
                start = max(a, earliest)
                start = start.replace(second=0, microsecond=0) + dt.timedelta(minutes=(-start.minute) % 15)
                if b - start >= need:
                    fits.append(start)
                    hour = start.replace(minute=0) + dt.timedelta(hours=1)
                    while rank is not None and hour + need <= b:  # each whole hour in it, to rank
                        fits.append(hour)
                        hour += dt.timedelta(hours=1)
            if rank is not None and fits:
                return max(fits, key=lambda s: (rank(s), -s.timestamp()))  # likeliest free, the earliest of equals
            return fits[0] if fits else None
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


def line(app: App, r: dict, at: dt.datetime | None, minutes: int, ask: bool = True) -> str:
    due = dt.datetime.fromisoformat(r["due"])
    when = f"{due:%a}" if (due.date() - now().date()).days < 6 else f"{due:%a %d %b}"
    bits = [f"due {when}", f"{r['logged']} min logged this week"]
    if r.get("cards") is not None:
        bits.append(f"{r['cards']} card{'s' if r['cards'] != 1 else ''} due")
    head = f"Uneasy about {_name(app, r['subject'])}: " + ", ".join(bits) + "."
    if r.get("next"):  # mind.study_push.frontier: where you're ready to go next in it
        head += f" Next up there: {r['next'][0]}."
    if not ask:
        return head
    return head + (f" {minutes} min at {at:%H:%M}?" if at else f" {minutes} min today?")


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
    # 0.8.16 (mind.act.more): once its trust in study blocks is earned, it sets the block itself and says so, with Undo
    did = _auto(app, today, minutes)
    if did is not None:
        text = f"{line(app, r, at, minutes, ask=False)} {did['out']['said']}"
        app.notify(text, kind="info", why="mind.study_push", about=r["title"], buttons=did["buttons"] or None)
    else:
        app.notify(
            text,
            kind="question",
            why="mind.study_push",
            about=r["title"],
            buttons=[[("Yes", f"msp:{today}:yes"), ("Later", f"msp:{today}:later")]],
        )
    app.events.emit("mind_study_push", cards=bool(r.get("cards")), logged=bool(r["logged"]), slot=at is not None)
    return text


def _auto(app: App, day: str, minutes: int) -> dict | None:
    try:
        from kurooto.mind import act
    except ImportError:
        return None
    return act.attempt(
        app,
        "study.block",
        lambda _: _do(app, day, "auto"),
        summary=f"set {minutes} min of study from the morning line",
        undo_from=lambda out: out.get("undo"),
    )


def _do(app: App, day: str, how: str = "yes") -> dict | None:
    """The study block itself (Yes, or Kurooto by itself once trusted): a reminder at the time offered, else
    Start-by counts the deadline as started today. {"said", "undo"}; None when it's answered already or gone."""
    with Lock(app.paths.state, "mind-study-push"):
        st = _state(app)
        if st.get("day") != day or st.get("answer"):
            return None
        st["answer"] = how
        jsave(app.paths.state / FILE, st)
    name = _name(app, st["subject"])
    minutes = int(st.get("minutes") or 25)
    at = dt.datetime.fromisoformat(st["at"]) if st.get("at") else None
    lead = "Done:" if how == "yes" else "I've set it:"
    rem = _on(app, "reminders")
    if rem is not None:
        when = at if at and at > now() else now() + dt.timedelta(minutes=30)
        key = f"reminders:msp{day.replace('-', '')}"
        start = _start_button(app, day)
        rem.add(when, f"{minutes} min of {name} ({st.get('title') or 'the deadline'})", key=key, buttons=start)
        return {"said": f"{lead} I'll remind you at {when:%H:%M} for {minutes} min of {name}.",
                "undo": {"day": day, "reminder": key}}  # fmt: skip
    sb = _on(app, "startby")
    if sb is not None and hasattr(sb, "start_today"):
        sb.start_today(st["deadline"])
        return {"said": f"{'Noted' if how == 'yes' else 'I counted it as started'}: "
                f"{st.get('title') or name} counts as started today.", "undo": {"day": day}}  # fmt: skip
    return {"said": f"Noted. {minutes} min of {name}" + (f" at {at:%H:%M}." if at else " today."), "undo": None}


def start_timer_on(app: App) -> bool:
    """(0.9.0) mind.study_push.start_timer, with the study tracker on."""
    return on(app) and app.settings.get("mind.study_push.start_timer") is not False and _on(app, "study") is not None


def _start_button(app: App, day: str) -> list | None:
    """The "Start 25 min" row under the reminder a Yes sets (its length is Study mode's focus, study.focus_min)."""
    if not start_timer_on(app):
        return None
    try:
        mins = int(float(app.settings.get("study.focus_min") or 25))
    except (TypeError, ValueError):
        mins = 25
    return [[(f"Start {mins} min", f"msp:{day}:start")]]


def subject_today(app: App) -> str | None:
    """(0.9.0) The subject today's line was about, for Study mode to open on (None: no line today, or the switch is
    off)."""
    if not start_timer_on(app):
        return None
    st = _state(app)
    return st.get("subject") if st.get("day") == now().date().isoformat() else None


def _start(app: App, day: str) -> str:
    """Start under the reminder: Study mode's timer for the line's subject, tied to its deadline (your tap only)."""
    st = _state(app)
    if st.get("day") != day or not st.get("subject"):
        return "That was for another day."
    study = _on(app, "study")
    if study is None or not start_timer_on(app):
        return "Study mode's timer is off (Study tracker, or mind.study_push.start_timer)."
    return study.timer_start(st["subject"], deadline=st.get("deadline"))


def undo(app: App, payload: dict | None) -> str:
    """Undo under a study block Kurooto set by itself: the reminder goes, and the morning line counts as unanswered."""
    p = payload or {}
    gone = bool(p.get("reminder") and app.scheduler.cancel(str(p["reminder"])))
    with Lock(app.paths.state, "mind-study-push"):
        st = _state(app)
        if st.get("day") == p.get("day") and st.get("answer") == "auto":
            st["answer"] = "undone"
            jsave(app.paths.state / FILE, st)
    return "Taken back: no study reminder." if gone else "Taken back."


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
    """msp:<day>:yes|later under the morning line; msp:<day>:start under the reminder a Yes set (0.9.0)."""
    if act == "start":
        return _start(app, day)
    with Lock(app.paths.state, "mind-study-push"):
        st = _state(app)
        if st.get("day") != day:
            return "That was for another day."
        if st.get("answer"):
            return "Already answered."
        if act != "yes":
            st["answer"] = "later"
            jsave(app.paths.state / FILE, st)
    app.events.emit("mind_study_answer", how="yes" if act == "yes" else "later")
    if act != "yes":
        return "OK, later. Its other reminders stay folded today; the six-hour one still comes."
    out = _do(app, day, "yes")
    if out is None:
        return "Already answered."
    try:  # 0.8.16: a yes to a study block is an OK for its kind (mind.act.more), so trust can grow
        from kurooto.mind import act as _act

        _act.answered(app, "study.block", True)
    except ImportError:
        pass
    return out["said"]


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)


def _register() -> None:
    try:
        from kurooto.mind import act
    except ImportError:
        return
    act.register("study.block", undoer=undo)


_register()

__all__ = ["push", "folded", "button", "pick", "line", "slot", "undo"]
