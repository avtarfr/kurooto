"""Turn on from chat (core/turnon.py): a request a feature that's off would do gets [Turn on] [Not now]; Turn on
switches it on and does the request; Not now leaves it off; a feature that needs setting up says where."""


def _offer(env, text):
    out = env.say(text)
    p = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    data = [b["callback_data"] for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
    return out, data


def test_turn_on_switches_it_on_and_does_the_request(env):
    app = env.app
    assert not app.is_on("reminders")
    out, data = _offer(env, "remind me in 5 min to stretch")
    assert out == "That's for Reminders, which is off. Turn it on and do it?"
    on = next(d for d in data if d.endswith(":on"))
    assert env.press(on) == "Reminders is on."
    assert app.is_on("reminders") and app.scheduler.jobs("reminders:")
    assert "stretch" in env.fake.texts()[-1]  # the request was done
    assert env.press(on) == "That's old now: ask again."


def test_not_now_leaves_it_off_and_the_setting_turns_it_off(env):
    app = env.app
    _out, data = _offer(env, "remind me in 5 min to stretch")
    assert env.press(next(d for d in data if d.endswith(":no"))) == "OK, left as it is."
    assert not app.is_on("reminders")
    app.settings.set("turnon.offer", False)
    assert not env.say("remind me in 5 min to stretch").startswith("That's for Reminders")
