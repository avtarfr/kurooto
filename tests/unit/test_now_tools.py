"""kurooto_now (core/tools.py, L124) and Brain's read-only tools with schedule_call's "when I'm free" (modules/mind.py,
modules/calls, L125), 0.9.0: words only (never chances, the read, mood, tone or sense readings), each behind its own
switch, read-only, and schedule_call still asks first."""

from __future__ import annotations

import datetime as dt

from kurooto.core import rightnow, tools
from kurooto.core.clock import now


def names(app):
    return {t.name for t in tools.agent_tools(app)}


def test_kurooto_now_says_where_you_are_in_words(env):
    app = env.app
    tool = next(t for t in tools.agent_tools(app) if t.name == "kurooto_now")
    assert tool.writes is False
    v = tool.run({})
    assert v["desk"].startswith("not known") and v["camera"] == "Face presence is off"
    assert v["call"] == "not on a call" and v["messages_go_to"] == "Telegram"
    assert "voice_id" not in v and "plan" not in v  # Voice and Brain are off
    app.settings.set("face.tools", False)
    assert "kurooto_now" not in names(app)


def test_kurooto_now_with_face_presence(env, monkeypatch):
    app = env.app
    face = app.modules["face"]
    monkeypatch.setattr(app, "is_on", lambda mid: mid in ("face", "telegram"))
    monkeypatch.setattr(face, "line", lambda: "camera on: looking for you")
    app.events.emit("face_arrived")
    v = rightnow.now_view(app)
    assert v["camera"] == "camera on: looking for you"
    assert v["desk"].startswith("at the desk since ")
    app.events.emit("face_left")
    assert rightnow.now_view(app)["desk"].startswith("away from the desk since ")
    text = repr(rightnow.now_view(app))
    for word in ("mood", "tone", "read", "frame", "p_free"):
        assert word not in text


def test_brain_tools_and_when_im_free(env, monkeypatch):
    from kurooto.mind import presence_forecast as pf
    from kurooto.modules import mind as mind_mod

    app = env.app
    m = app.modules["mind"]
    assert m.call_tools() == []  # Brain is off
    monkeypatch.setattr(mind_mod.mind, "part_on", lambda a, part: True)
    got = {t.name: t for t in m.call_tools()}
    assert set(got) == {"brain_plan", "brain_free_time", "brain_precedents"}
    assert all(t.writes is False for t in got.values())
    later = (now() + dt.timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    monkeypatch.setattr(pf, "on", lambda a: True)
    monkeypatch.setattr(pf, "free_now", lambda a, t=None: False)
    monkeypatch.setattr(pf, "next_free", lambda a, t=None, hours=12: (later, 0.83))
    said = got["brain_free_time"].run({})
    assert said.startswith("Likely free from ") and "%" not in said and "0.83" not in said
    # schedule_call: "when I'm free" goes to the forecast's hour (and stays guarded: core/tap.py)
    calls = app.modules["calls"]
    booked = []
    monkeypatch.setattr(calls, "schedule", lambda at, reason, **kw: booked.append(at) or f"Booked {at:%H:%M}")
    assert calls._schedule_tool({"when": "when I’m free", "reason": "the essay"}, live=False).startswith("Booked")
    assert booked == [later]
    monkeypatch.setattr(pf, "next_free", lambda a, t=None, hours=12: None)
    assert "can't tell" in calls._schedule_tool({"when": "when I'm free", "reason": "x"}, live=False)
    sched = next(t for t in calls._own_tools(live=False) if t.name == "schedule_call")
    assert sched.guarded == "call.place"
