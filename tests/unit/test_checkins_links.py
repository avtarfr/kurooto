"""Check-in links of 0.9.0: a quiet day reorders the evening call without dropping a step (L43,
checkins.follow_register); open threads with a due come up in the evening call (L45, checkins.reflect_open)."""

from __future__ import annotations

import re


def steps(script: str) -> list[str]:
    return [re.sub(r"^\d+\. ", "", ln) for ln in script.splitlines() if re.match(r"^\d+\. ", ln)]


def test_a_quiet_day_reorders_the_evening_call_and_keeps_every_step(env, monkeypatch):
    env.on("checkins")
    ck = env.app.modules["checkins"]
    monkeypatch.setattr(ck, "_quiet_day", lambda: True)
    usual = steps(ck.script("evening"))
    assert usual[0].startswith("Ask how today went")  # off by default: as before
    env.app.settings.set("checkins.follow_register", True)
    s = ck.script("evening")
    quiet = steps(s)
    assert quiet[0] == usual[0] and quiet[1] == usual[-2]  # how it went, then tomorrow
    assert quiet[2].startswith("Then ask once: want to go through the rest")
    assert [x.removeprefix("(If they go on) ") for x in quiet[3:-1]] == usual[1:-2]  # nothing dropped
    assert quiet[-1] == usual[-1]
    for word in ("mood", "register", "low day", "quiet day", "the read"):
        assert word not in s.lower()
    monkeypatch.setattr(ck, "_quiet_day", lambda: False)
    assert steps(ck.script("evening")) == usual


def test_open_threads_due_today_come_up_in_the_evening(env):
    """L45: a thread due today ("I'll send the draft tonight") is asked about in the evening call and message; the
    evening reply "I emailed the draft to Mira" closes it (core/threads.py)."""
    import datetime as dt

    from kurooto.core import threads
    from kurooto.core.clock import now

    app = env.app
    app.settings.set("memory.threads", True)
    env.on("checkins")
    ck = app.modules["checkins"]
    today = ck.day_of()
    due = dt.datetime.combine(today, dt.time(22, 0)).isoformat()
    threads.add(app, "email the draft to Mira", "chat", due=due)
    threads.add(app, "book the lab slot", "chat", due=(now() + dt.timedelta(days=5)).isoformat())
    assert ck.open_due(today) == ["email the draft to Mira"]
    s = ck.script("evening")
    assert "Still open from what they said they'd do by today: email the draft to Mira." in s
    assert "book the lab slot" not in s
    ck._answer(_msg("I emailed the draft to Mira, all good"), f"evening:{today.isoformat()}")
    assert ck.open_due(today) == []
    app.settings.set("checkins.reflect_open", False)
    threads.add(app, "email the professor", "chat", due=due)
    assert "Still open" not in ck.script("evening")


def _msg(text):
    from kurooto.modules.base import Incoming

    return Incoming(text=text, via="telegram", respond=lambda t, buttons=None: None)


def test_time_at_the_desk_in_the_evening_and_the_week(env, monkeypatch):
    """L22 (0.9.0, face.desk_time, off): Face presence's arrivals and departures become "6 h at the desk today,
    longest 2 h 40 unbroken" in the evening check-in and the weekly summary; times only, told as his own numbers."""
    import datetime as dt

    app = env.app
    face = app.modules["face"]
    day = dt.date(2026, 10, 28)
    at = lambda h, m=0: dt.datetime.combine(day, dt.time(h, m)).isoformat()  # noqa: E731
    evs = [
        {"ts": dt.datetime.combine(day - dt.timedelta(days=1), dt.time(23)).isoformat(), "kind": "face_left"},
        {"ts": at(9), "kind": "face_arrived"},
        {"ts": at(11, 40), "kind": "face_left"},
        {"ts": at(13), "kind": "face_back"},
        {"ts": at(14, 30), "kind": "face_left"},
    ]
    pick = lambda n=50, kinds=None: [e for e in evs if not kinds or e["kind"] in kinds]  # noqa: E731
    monkeypatch.setattr(app.events, "tail", pick)
    monkeypatch.setattr(app, "is_on", lambda mid: mid in ("face", "checkins", "telegram"))
    lo = dt.datetime.combine(day, dt.time(5))
    spans = face.desk_spans(lo, lo + dt.timedelta(days=1))
    assert [(a.hour, b.hour, b.minute) for a, b in spans] == [(9, 11, 40), (13, 14, 30)]
    assert face.desk_line(lo, lo + dt.timedelta(days=1)) == ""  # off by default
    app.settings.set("face.desk_time", True)
    assert face.desk_line(lo, lo + dt.timedelta(days=1)) == "4 h 10 at the desk today, longest 2 h 40 unbroken."
    ck = app.modules["checkins"]
    assert ck._desk_line(day).startswith("4 h 10 at the desk today")
