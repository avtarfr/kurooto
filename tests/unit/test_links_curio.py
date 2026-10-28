"""0.9.0 links for add-ons (batch 3): the generic hooks an add-on uses, tested with made-up features. No add-on, AI,
network or device is real."""

from __future__ import annotations

import datetime as dt
import time

import pytest

from kurooto.modules.base import Module
from tests.unit import test_mind_door as door
from tests.unit.test_features import run_due


# -------------------------------------------------------------------------- a feature's buttons on a reminder (L112)
class Shop(Module):
    id = "shop"
    title = "Shop"

    def __init__(self, app, buttons=None, fail=False):
        super().__init__(app)
        self.buttons, self.fail, self.asked = buttons, fail, []

    def reminder_buttons(self, what):
        self.asked.append(what)
        if self.fail:
            raise RuntimeError("no")
        return self.buttons if self.buttons is not None else [("Order on Zepto", "shop:r1:zepto")]


def keyboard(env):
    return [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"]


def with_features(env, monkeypatch, *mods):
    real = env.app.enabled
    monkeypatch.setattr(env.app, "enabled", lambda: [*real(), *mods])


def test_a_feature_adds_a_row_under_the_snooze_buttons(env, monkeypatch):
    env.on("reminders")
    shop = Shop(env.app)
    with_features(env, monkeypatch, shop)
    env.say("remind me in 20 minutes to buy milk and eggs")
    run_due(env.app, dt.timedelta(minutes=21))
    rows = keyboard(env)
    assert [b["text"] for b in rows[0]] == ["+10 min", "+1 h"]  # the snooze row stays first and the same
    assert [(b["text"], b["callback_data"]) for b in rows[1]] == [("Order on Zepto", "shop:r1:zepto")]
    assert shop.asked == ["buy milk and eggs"]


def test_bad_or_failing_buttons_are_left_out_and_the_switch_stops_them(env, monkeypatch):
    env.on("reminders")
    rem = env.app.modules["reminders"]
    many = [("A", "shop:1:a"), ("B", "shop:2:b"), ("C", "shop:3:c")]
    with_features(env, monkeypatch, Shop(env.app, fail=True), Shop(env.app, [("x", "")]), Shop(env.app, many))
    assert rem._addon_buttons("buy milk") == [("A", "shop:1:a"), ("B", "shop:2:b")]  # at most 2
    assert any(e["kind"] == "reminder_buttons_failed" for e in env.app.events.tail(20))
    with_features(env, monkeypatch, Shop(env.app, [("Long", "shop:" + "x" * 70)]))
    assert rem._addon_buttons("buy milk") == [("A", "shop:1:a"), ("B", "shop:2:b")]  # too long for Telegram: out
    env.app.settings.set("reminders.addon_buttons", False)
    assert rem._addon_buttons("buy milk") == []
    env.say("remind me in 20 minutes to buy bread")
    run_due(env.app, dt.timedelta(minutes=21))
    assert len(keyboard(env)) == 1


# ------------------------------------------------------------------------------------ seen minutes for Study (L118)
def test_seen_minutes_count_apart_never_during_a_session_and_have_a_switch(env):
    from tests.unit.test_m6 import SUBJECTS

    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "study")
    st = env.app.modules["study"]
    assert st.add_seen("linear-algebra", 1200) is True  # at most 10 minutes a call
    assert st.add_seen("not-a-subject", 60) is False
    assert st.day() == {"linear-algebra|seen": 600} and st.totals() == {"linear-algebra": 600}
    assert "(of which 0.2 h seen on screen, not timed)" in st.report()
    st.start_session("linear algebra")
    assert st.add_seen("linear-algebra", 60) is False  # a session counts that time itself
    st.stop_session()
    env.app.settings.set("study.seen", False)
    assert st.add_seen("linear-algebra", 60) is False
    assert st.seen_seconds() == 600


# ------------------------------------------------------------------------------ deep in one thing, at the door (L145)
@pytest.fixture
def door_app(tmp_path, monkeypatch):
    """Brain's door with test_mind_door.py's fakes."""
    yield from door.app._get_wrapped_function()(tmp_path, monkeypatch)  # noqa: SLF001


def test_deep_in_one_thing_holds_winners_even_at_a_break_never_exempt_ones(door_app):
    app = door_app
    from kurooto.mind import breaks, workspace

    assert breaks.deep(app, time.time() + 3600) is True
    assert breaks.deep_now(app) and breaks.deep_now(app, time.time() + breaks.DEEP_MAX_S + 5) is False  # capped
    app.notify("A new paper on glacier flow.", why="research.papers")
    assert app.out == [] and workspace.held_count(app) == 1  # held even though nothing can see breaks
    breaks.signal(app, "pickup")
    assert app.out == []  # a break doesn't let it out while you're deep
    app.notify("Your reminder: call the bank", kind="reminder", why="reminders.own")
    app.notify("Lab report due in 2 hours.", why="deadlines.reminder", due=door.due_in(2))
    assert len(app.out) == 2  # what goes past the door is never held
    breaks.deep(app, 0)
    breaks.signal(app, "surfaced")
    assert "A new paper on glacier flow." in door.texts(app)
    app.settings.set("mind.workspace.deep_hold", False)
    assert breaks.deep(app, time.time() + 60) is False and not breaks.deep_now(app)


def test_deep_waits_no_longer_than_max_hold(door_app):
    app = door_app
    from kurooto.mind import breaks, workspace

    breaks.deep(app, time.time() + 600)
    w = {"urgent": False, "at": time.time() - breaks.max_hold_s(app) - 1}
    assert workspace._may_go(app, w, time.time()) != "wait"
    assert workspace._may_go(app, {"urgent": False, "at": time.time()}, time.time()) == "wait"


# ------------------------------------------------------------------------------- features' context lines (L142, L147)
class Lines(Module):
    id = "lines"
    title = "Lines"

    def __init__(self, app, lines=None, fail=False):
        super().__init__(app)
        self.lines, self.fail = lines or [], fail

    def context_lines(self):
        if self.fail:
            raise RuntimeError("no")
        return self.lines


def test_a_features_context_lines_join_requests_never_a_guests(env, monkeypatch):
    from kurooto.providers import context

    many = [f"line {i}\nwith\tspaces" for i in range(6)]
    with_features(env, monkeypatch, Lines(env.app, fail=True), Lines(env.app, ["Topics: chaos, " + "x" * 400]))
    got = context.addon_context(env.app)
    assert got.startswith("Topics: chaos, ") and len(got) == context.ADDON_LINE_MAX
    assert "Topics: chaos" in context.headless_context(env.app)
    assert "Topics: chaos" not in context.guest_context(env.app)
    with_features(env, monkeypatch, Lines(env.app, many))
    assert context.addon_context(env.app).count("\n") == context.ADDON_LINES - 1 and "line 0 with spaces" in (
        context.addon_context(env.app)
    )
    env.app.settings.set("mind.context.addons", False)
    assert context.addon_context(env.app) == "" and "Topics: chaos" not in context.headless_context(env.app)
