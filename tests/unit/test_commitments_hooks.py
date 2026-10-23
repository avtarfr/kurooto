"""Hooks from chat (modules/commitments.py): "when I say gym, hold calls 90 min" keeps a word; "gym" on its own later
starts that hold (calls, or everything as focus); /hooks lists them, /hooks drop forgets one; each step has Undo; the
word inside an ordinary sentence does nothing."""

import datetime as dt
import json

import pytest


@pytest.fixture
def hk(env):
    env.on("commitments")
    return env, env.app.modules["commitments"], env.app.availability


def last_buttons(env) -> str:
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    return json.dumps(sent.get("reply_markup") or {})


def test_a_hook_is_set_from_the_sentence_and_the_word_alone_starts_it(hk):
    env, c, a = hk
    out = env.say("when I say gym, hold calls 90 min")
    assert out == 'Hook set: "gym" on its own holds calls for 90 min. /hooks lists them.'
    assert "hook:gym:unadd" in last_buttons(env)
    assert c.hooks() == [{"word": "gym", "hold": "calls", "minutes": 90}]
    assert a.quiet_until() is None  # setting it holds nothing yet
    t0 = dt.datetime.now()
    out = env.say("Gym")
    assert out.startswith("gym: no calls until ") and "hook:gym:unhold" in last_buttons(env)
    until = a.quiet_until()
    assert dt.timedelta(minutes=89) < until - t0 < dt.timedelta(minutes=91)
    reason, _ = a.call_block()
    assert reason == "you asked for no calls"
    assert a.focus_until() is None  # messages still come
    assert env.press("hook:gym:unhold") == "Calls are allowed again."
    assert a.quiet_until() is None
    assert env.press("hook:gym:unhold") == "Nothing to undo."


def test_hold_everything_is_focus(hk):
    env, c, a = hk
    assert env.say("when I say lab, hold everything 2 h").startswith('Hook set: "lab" on its own holds everything')
    assert c.hooks()[0]["hold"] == "all" and c.hooks()[0]["minutes"] == 120
    assert env.say("lab.").startswith("lab: focus until ")
    assert a.focus_until() is not None
    assert env.press("hook:lab:unhold") == "Focus off."
    assert a.focus_until() is None


def test_the_word_in_a_sentence_does_nothing(hk):
    env, c, a = hk
    env.say("when I say gym, hold calls 90 min")
    match = c.intents()[1].match
    for text in ("I'm off to the gym", "gym later?", "gym tomorrow", "the gym was closed"):
        assert match(text) is None, text
    env.say("I'm off to the gym")
    assert a.quiet_until() is None


def test_listed_dropped_and_undone(hk):
    env, c, a = hk
    assert env.say("/hooks").startswith("No hooks yet.")
    env.say("when I say gym, hold calls 90 min")
    env.say("whenever I say 'lab' hold everything for 2 hours")
    out = env.say("/hooks")
    assert '"gym": holds calls for 90 min' in out and '"lab": holds everything (focus) for 2 h' in out
    assert env.say("/hooks drop gym") == 'Hook "gym" dropped.'
    assert "hook:gym:undrop" in last_buttons(env)
    assert [h["word"] for h in c.hooks()] == ["lab"]
    assert env.say("gym") != "" and a.quiet_until() is None  # no hook any more: nothing held
    assert env.press("hook:gym:undrop") == 'Hook "gym" is back.'
    assert [h["word"] for h in c.hooks()] == ["lab", "gym"]
    assert env.say("/hooks drop swim") == 'No hook "swim". /hooks lists them.'
    # Undo on a new hook takes it back; on a changed one, puts the old one back
    env.say("when I say gym, hold everything 30 min")
    assert c._hook("gym")["hold"] == "all"
    assert env.press("hook:gym:unadd") == '"gym" is back to what it was.'
    assert c._hook("gym") == {"word": "gym", "hold": "calls", "minutes": 90}
    assert c.intents()[1].match("when I say swim, hold all calls 45 min")["hold"] == "calls"
    env.say("when I say run, no calls for an hour")
    assert env.press("hook:run:unadd") == "Hook undone." and c._hook("run") is None


def test_it_asks_when_the_sentence_is_unclear_and_never_holds_now(hk):
    env, c, a = hk
    assert env.say("when I say gym, hold calls").startswith("For how long?")
    assert env.say("when I say ok, hold calls 90 min").startswith('"ok" is too common a word')
    assert c.hooks() == [] and a.quiet_until() is None and a.focus_until() is None


def test_a_hook_never_touches_the_alarm(hk):
    env, c, a = hk
    alarm = env.app.modules["alarm"]
    before = alarm.next()
    env.say("when I say bed, hold everything 8 h")
    env.say("bed")
    assert alarm.next() == before


def test_the_word_reaches_the_hook_with_everything_on(hk):
    """No other instant request takes a hook word said alone, with every feature on."""
    env, c, a = hk
    app = env.app
    app.settings.set("modules.enabled", list(app.modules))
    for word in ("gym", "lab", "run", "study", "class"):
        c.add_hook(word, "calls", 30)
        first = next((it.name for m in app.enabled() for it in m.intents() if it.match(word) is not None), None)
        assert first == "hook", (word, first)
