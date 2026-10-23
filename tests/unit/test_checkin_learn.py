"""Learned check-in times (modules/checkins.py:learn): a check-in you keep moving or answering late moves to when you
do it, with Undo; not on too few days, not when the days disagree, not again soon after an Undo."""

import datetime as dt


def _days(app, name, rows):
    """rows: per day back (1 = yesterday): (time it was at, moved?, answered at hh:mm or None)."""
    ck = app.modules["checkins"]
    today = ck.day_of()
    for k, (t, moved, ans) in enumerate(rows, start=1):
        d = today - dt.timedelta(days=k)
        e = {"time": t, "status": "answered" if (ans or moved) else "skipped"}
        if moved:
            e["moved"] = "x"
        if ans:
            e["answered_at"] = ck.at(d, ans).isoformat()
        ck._save({name: e}, d)


def test_a_check_in_you_keep_moving_moves(env):
    app = env.app
    env.on("checkins")
    ck = app.modules["checkins"]
    assert app.settings.get("checkins.times")["evening"] == "22:00"
    _days(app, "evening", [("23:00", True, None)] * 3 + [("22:00", False, "23:20"), ("22:00", False, "22:50")])
    told = ck.learn()
    assert told == [
        "Your evening check-in is at 23:00 from now on, not 22:00: on 5 of the last 5 days you did it around then."
    ]
    assert app.settings.get("checkins.times")["evening"] == "23:00"
    assert ck.learn() == []  # not again for two weeks
    assert app.callback("chkl:evening:undo").startswith("Back to 22:00")
    assert app.settings.get("checkins.times")["evening"] == "22:00"
    assert ck.learn() == []  # left alone after an Undo


def test_too_few_days_or_days_that_disagree_change_nothing(env):
    app = env.app
    env.on("checkins")
    ck = app.modules["checkins"]
    _days(app, "evening", [("23:00", True, None)] * 4)  # only 4 days
    assert ck.learn() == []
    _days(app, "evening", [("23:00", True, None)] * 3 + [("21:00", True, None)] * 3)  # later and earlier
    assert ck.learn() == []
    _days(app, "evening", [("22:00", False, "22:05")] * 6 + [("22:00", False, "08:00")] * 4)  # on time; next morning
    assert ck.learn() == []
    app.settings.set("checkins.learn_times", False)
    _days(app, "evening", [("23:30", True, None)] * 8)
    assert ck.learn() == []
