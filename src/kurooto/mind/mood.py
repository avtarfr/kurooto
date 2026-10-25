"""/mood and what runs behind it (Brain, 0.8.0 stage 04, shadow mode): the daily read, the 21:00 forecast, the next
evening's score, the asks, Forget this and Off. Everything here is computed, logged and shown; nothing reads it to
decide
what Kurooto does yet (a test asserts that nothing in the gate, Calm or the decisions does).

    run_read      today's read from the day's numbers (mind/read.py), handed to the scorekeeper
    run_forecast  tomorrow's forecast, frozen (mind/forecast.py); a tenth of days are holdout days: a planned action is
                  withheld on purpose, so its effect can be measured later and never has to be predicted (I-14)
    run_score     collects today's numbers, then asks the scorekeeper to score yesterday's forecast for today
    ask           one question to you: "has this week felt heavier than usual?" Yes / No / Not now; it never names the
                  read (a message travels through Telegram, and a reading of you stays here). At most twice a week and,
                  in shadow mode, only on Sundays (the weekly retro's evening), plus one random one a fortnight
    view          /mood: the read, its votes and evidence, confidence, tomorrow's forecast, last week's surprise
    button        Wrong, Forget this, Off, and the answers to an ask

Retention (invariant I-11): the day's numbers and reads 30 days, your answers 7 days, tone tags 1 day (mind/tone.py),
the
calibration pairs (a strength and right/wrong, no date, no words) the latest 200. Forget this deletes that day's
numbers,
read, answer and forecast, and what was kept of that day's messages, calls and requests (core/retention.py). Off asks
first.
"""

from __future__ import annotations

import datetime as dt
import random
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.mind import forecast, read, signals, tone

if TYPE_CHECKING:
    from kurooto.app import App

PART = "read"  # its switch: mind.read.on

FILE = "mind-mood.json"  # in the state folder: {"active": bool, "asked": [iso days], "ask_at": {day: kind}}
ASK_WEEK_DAYS = 7
FORTNIGHT = 14


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("active", True)
    d.setdefault("asked", [])
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def today() -> dt.date:
    d = now().date()
    return d - dt.timedelta(days=1) if now().hour < signals.DAY_STARTS else d


def history(app: App, before: dt.date | None = None) -> list[read.Day]:
    """The stored days, oldest first, each with its calendar load and its signals (days from `before` on are left
    out)."""
    days = []
    for day, nums in sorted(mind.connect(app).signal_days().items()):
        try:
            d = dt.date.fromisoformat(day)
        except ValueError:
            continue
        if before is not None and d >= before:
            continue
        load = {
            "deadlines_w": nums.get("load_deadlines_w", 0),
            "deadlines_n": nums.get("load_deadlines_n", 0),
            "class_h": nums.get("load_class_h", 0),
            "exam_season": nums.get("load_exam", 0) > 0,
            "weekday": d.weekday(),
        }
        days.append(read.Day(day, load, {k: v for k, v in nums.items() if k in read.SIGNALS}))
    return _with_past(app, days, before)


def _with_past(app: App, days: list[read.Day], before: dt.date | None) -> list[read.Day]:
    """Days from before Brain was on (mind.backfill): what the imported events say of snoozes and deadline moves,
    with no calendar load. They fill in the history's start; a day Brain measured itself is never replaced."""
    from kurooto.mind import history

    have = {d.day for d in days}
    past = []
    for day, ks in sorted(history.daily(app).items()):
        d = dt.date.fromisoformat(day)
        if day in have or (before is not None and d >= before):
            continue
        sig = {"snoozes": float(ks.get("deadline_snooze", 0)), "deadline_moves": float(ks.get("deadline_moved", 0))}
        past.append(read.Day(day, {"weekday": d.weekday()}, sig))
    return sorted([*past, *days], key=lambda x: x.day)


def answers(app: App) -> list[tuple[float, bool]]:
    """Your confirmed answers as (the read's strength, was it right), oldest first: the calibration pairs."""
    rows = sorted(mind.connect(app).mood_rows("cal:"), key=lambda r: r["key"])
    return [(float(r["value"]), bool((r["meta"] or {}).get("right"))) for r in rows]


def _yesterday_read(app: App, day: dt.date) -> read.Read | None:
    row = next(iter(mind.connect(app).mood_rows(f"read:{(day - dt.timedelta(days=1)).isoformat()}")), None)
    if not row:
        return None
    m = row["meta"] or {}
    return read.Read(
        day.isoformat(),
        m.get("label", "steady"),
        m.get("votes") or [],
        len(m.get("votes") or []),
        float(row["value"]),
        m.get("evidence") or {},
    )


def run_read(app: App, payload: dict | None = None) -> dict | None:
    """Today's read, from the numbers stored so far."""
    if not mind.part_on(app, "read"):
        return None
    day = today()
    hist = history(app, before=day)
    nums = mind.connect(app).signal_days().get(day.isoformat()) or {}
    load = {
        "deadlines_w": nums.get("load_deadlines_w", 0),
        "deadlines_n": nums.get("load_deadlines_n", 0),
        "class_h": nums.get("load_class_h", 0),
        "exam_season": nums.get("load_exam", 0) > 0,
        "weekday": day.weekday(),
    }
    r = read.read_day(hist, read.Day(day.isoformat(), load, {k: v for k, v in nums.items() if k in read.SIGNALS}))
    ans = answers(app)
    st = _state(app)
    counted = read.counts(_yesterday_read(app, day), r)
    if not read.accuracy_ok(ans):
        if st["active"]:
            st["active"] = False
            _save(app, st)
    elif not st["active"] and len(ans) < read.GATE_WINDOW:
        st["active"] = True
        _save(app, st)
    conf = read.confidence(ans, r.strength)
    body = {
        "day": day.isoformat(), "label": r.label, "votes": r.votes, "evidence": r.evidence, "strength": r.strength,
        "counted": counted, "confidence": conf,
    }  # fmt: skip
    mind.connect(app).report("read_day", body)
    return {**body, "n_votes": r.n_votes}


def tomorrow_load(app: App, day: dt.date) -> dict:
    n = signals.load(app, day)
    return {
        "deadlines_w": n["load_deadlines_w"], "deadlines_n": n["load_deadlines_n"], "class_h": n["load_class_h"],
        "exam_season": n["load_exam"] > 0, "weekday": day.weekday(),
    }  # fmt: skip


def run_forecast(app: App, payload: dict | None = None) -> dict | None:
    """Tomorrow's forecast at 21:00, frozen in the scorekeeper. Nothing is planned in shadow mode, so no channel is
    touched; a tenth of days are marked holdout all the same, so the days exist when a later stage plans actions."""
    if not mind.part_on(app, "forecast"):
        return None
    tomorrow = today() + dt.timedelta(days=1)
    hist = history(app, before=tomorrow)
    models = forecast.fit(hist)
    if not models:
        return None
    params = forecast.predict(models, tomorrow_load(app, tomorrow))
    p = app.settings.get("mind.forecast.holdout")
    hold = random.random() < (float(p) if isinstance(p, (int, float)) else 0.10)  # noqa: S311 (a coin, not a secret)
    body = {"day": tomorrow.isoformat(), "params": params, "planned": [], "holdout": hold}
    mind.connect(app).report("forecast", body)
    return body


def run_score(app: App, payload: dict | None = None) -> bool:
    """20:55: today's numbers one more time, then the scorekeeper scores the forecast made for today."""
    if not mind.part_on(app, "forecast"):
        return False
    d = today()
    signals.report(app, d)
    mind.connect(app).flush(3.0)
    return mind.connect(app).report("score_forecast", {"day": d.isoformat()})


# ------------------------------------------------------------------------------------------------------ asking
def ask(app: App, payload: dict | None = None) -> bool:
    """One question, when a read counts and none was asked this week (Sundays only in shadow mode), or one random one a
    fortnight. False when nothing was asked."""
    if not mind.part_on(app, "read"):
        return False
    st = _state(app)
    d = today()
    asked = [dt.date.fromisoformat(x) for x in st["asked"] if isinstance(x, str)]
    week = [a for a in asked if (d - a).days < ASK_WEEK_DAYS]
    cap = app.settings.get("mind.read.asks_per_week")
    if len(week) >= (int(cap) if isinstance(cap, (int, float)) else 2):
        return False
    row = next(iter(mind.connect(app).mood_rows(f"read:{d.isoformat()}")), None)
    if row is None:
        return False
    meta = row["meta"] or {}
    sunday = d.weekday() == 6
    fortnight = not any((d - a).days < FORTNIGHT for a in asked) and random.random() < 1 / FORTNIGHT  # noqa: S311
    if not ((meta.get("counted") and sunday) or fortnight):
        return False
    app.notify(  # the words don't name the read (I-11)
        "Quick check: has this week felt heavier than usual?",
        kind="question",
        why="mood.ask",
        buttons=[
            [
                ("Yes", f"mmd:{d.isoformat()}:yes"),
                ("No", f"mmd:{d.isoformat()}:no"),
                ("Not now", f"mmd:{d.isoformat()}:later"),
            ]
        ],
    )
    st["asked"] = [x.isoformat() for x in asked + [d]][-30:]
    _save(app, st)
    return True


def answer(app: App, day: str, right: bool) -> str:
    row = next(iter(mind.connect(app).mood_rows(f"read:{day}")), None)
    if row is None:
        return "That read is gone."
    meta = row["meta"] or {}
    mind.connect(app).report(
        "read_answer", {"day": day, "right": right, "strength": float(row["value"]), "label": meta.get("label", "")}
    )
    return "Thanks, that helps it learn." if right else "Noted: it read you wrong that day."


# --------------------------------------------------------------------------------------------------- the view
def _clock(minutes: float) -> str:
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def view(app: App) -> tuple[str, list]:
    if not mind.on(app):
        return "Brain is off (Features → Brain).", []
    if not mind.part_on(app, "read"):
        return "The read is off (mind.read.on).", []
    c = mind.connect(app)
    d = today()
    ans = answers(app)
    row = next(iter(c.mood_rows(f"read:{d.isoformat()}")), None)
    lines = ["How Brain reads you (shadow mode: it only watches, nothing it does depends on this yet)."]
    st = _state(app)
    if row is None:
        lines.append("No read yet today: it needs a few days of numbers first.")
    else:
        m = row["meta"] or {}
        conf = m.get("confidence")
        if m.get("counted"):
            lines.append(f"Today: {m.get('label')}.")
        else:
            lines.append("Today: no clear read (it needs 3 or more signs out of the ordinary, two days running).")
        for name, z in m.get("votes") or []:
            lines.append(f"  {name}: {z:+.1f}")
        if m.get("evidence"):
            lines.append("  all: " + ", ".join(f"{k} {v:+.1f}" for k, v in sorted(m["evidence"].items())))
        lines.append(
            f"Confidence: {conf:.0%}."
            if isinstance(conf, (int, float))
            else f"Not enough data to read you yet ({len(ans)} of {read.MIN_ANSWERS} answers)."
        )
    if not st["active"]:
        lines.append("Its accuracy fell under 60% over your last answers, so it's set aside until it does better.")
    t = tone.tier(app)
    lines.append(
        {
            "gpu": "Tone: tagged as you write, on this computer.",
            "cpu": "Tone: tagged once an hour, on this computer.",
            "none": "Tone: statistics only.",
        }[t]
    )
    f = next(iter(c.mood_rows(f"forecast:{(d + dt.timedelta(days=1)).isoformat()}")), None)
    if f is not None and isinstance(f["meta"], dict):
        p = f["meta"].get("params") or {}
        bits = []
        if "wake_min" in p:
            bits.append(f"wake about {_clock(p['wake_min'][0])} (±{p['wake_min'][1]:.0f} min)")
        if "study_min" in p:
            bits.append(f"study about {p['study_min'][0]:.0f} min")
        if "deadline_moves" in p:
            bits.append(f"{p['deadline_moves'][0]:.1f} deadlines moved")
        if bits:
            lines.append("Tomorrow's forecast: " + ", ".join(bits) + ".")
    week = [r for r in c.mood_rows("score:") if r["key"].split(":", 1)[1] >= (d - dt.timedelta(days=7)).isoformat()]
    if week:
        lines.append(f"Last week's surprise: {sum(r['value'] for r in week) / len(week):.2f} (lower is better).")
    last = max((r["key"].split(":", 1)[1] for r in c.mood_rows("read:")), default=d.isoformat())
    buttons = [[("Wrong", f"mmd:{last}:wrong"), ("Forget this", f"mmd:{last}:forget"), ("Off", "mmd:0:off")]]
    return "\n".join(lines), buttons


def button(app: App, ref: str, act: str) -> str:
    """Yes / No / Not now under an ask; Wrong, Forget this and Off under /mood."""
    if act in ("yes", "no"):  # "heavier than usual": yes agrees with a stretched or low read, no with the others
        row = next(iter(mind.connect(app).mood_rows(f"read:{ref}")), None)
        heavy = bool(row) and (row["meta"] or {}).get("label") in ("stretched", "low")
        return answer(app, ref, heavy == (act == "yes"))
    if act == "wrong":
        return answer(app, ref, False)
    if act == "later":
        return "Alright."
    if act == "forget":
        return forget_day(app, ref)
    if act == "off":
        return off(app, confirm=ref == "confirmed")
    return "ok"


def forget_day(app: App, day: str) -> str:
    """Forget this: that day's numbers, read, answer and forecast, and what was kept of its messages, calls and
    requests."""
    try:
        d = dt.date.fromisoformat(day)
    except ValueError:
        return "No such day."
    mind.connect(app).report("read_forget", {"day": day})
    from kurooto.mind import story

    story.forget_day(app, day)  # lines about you from that day leave the life story too
    lo, hi = signals.span(d)
    try:
        from kurooto.core import retention

        retention.forget(
            app, lo, hi, kinds=tuple(k for k in retention.KINDS if k != "mind"), gist=False
        )  # (not the cascade itself)
    except Exception:
        pass
    tone.forget(app)
    return f"Forgot {day}: its numbers, its read, your answer and what Kurooto kept of that day."


def off(app: App, confirm: bool = False) -> str:
    """Off: sets mind.read.on false; the history is deleted after you confirm (a second tap)."""
    app.settings.set("mind.read.on", False)
    if not confirm:
        app.notify(
            "The read is off. Delete what it kept (the day's numbers, its reads, your answers)?",
            kind="question",
            why="mood.off",
            buttons=[[("Delete it", "mmd:confirmed:off"), ("Keep it", "mmd:0:keep")]],
        )
        return "The read is off. It asks whether to delete what it kept."
    mind.connect(app).report("read_off", {})
    tone.forget(app)
    return "Deleted: the day's numbers, the reads and your answers."
