"""Start-by's learned window (modules/startby.py:learn_window): it moves to when your messages come in, with Undo;
never a window you set yourself, and not on too few days."""

import datetime as dt
import json


def _messages(app, days, first, last, n=4):
    """`days` days back, each with n messages from `first` to `last` (hours, last may be past 24)."""
    rows = []
    today = dt.datetime.combine(dt.date.today(), dt.time(0))
    for k in range(1, days + 1):
        for i in range(n):
            h = first + (last - first) * i / (n - 1)
            rows.append(
                {"ts": (today - dt.timedelta(days=k) + dt.timedelta(hours=h)).isoformat(), "kind": "message_in"}
            )
    with open(app.events.file, "a", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)


def test_the_window_moves_to_when_you_are_up_and_undo_takes_it_back(env):
    app = env.app
    env.on("deadlines", "startby")
    sb = app.modules["startby"]
    _messages(app, 10, 11.25, 25.5)  # up from about 11:15, last message at 01:30
    line = sb.learn_window()
    assert line.startswith("Start-by dates now count your free time from 11:00 to 01:30, not 09:00 to 22:00")
    assert app.settings.get("startby.window") == "11:00-01:30"
    assert sb.learn_window() == ""  # not again within a week
    assert app.callback("sby:window:undo").startswith("Back to 09:00-22:00")
    assert app.settings.get("startby.window") == "09:00-22:00"


def test_too_few_days_or_your_own_window_stay(env):
    app = env.app
    env.on("deadlines", "startby")
    sb = app.modules["startby"]
    _messages(app, 5, 11, 25)
    assert sb.learn_window() == ""  # 5 days: too few
    _messages(app, 8, 11, 25)
    app.settings.set("startby.window", "08:00-20:00")  # yours
    assert sb.learn_window() == "" and app.settings.get("startby.window") == "08:00-20:00"
