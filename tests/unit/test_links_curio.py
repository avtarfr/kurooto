"""0.9.0 links for add-ons (batch 3): the generic hooks an add-on uses, tested with made-up features. No add-on, AI,
network or device is real."""

from __future__ import annotations

import datetime as dt

from kurooto.modules.base import Module
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
