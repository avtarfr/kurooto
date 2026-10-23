"""Problem-set progress (modules/deadlines.py:progress): "ps3 4/7" or "did 4 of 7 on the stats problem set" keeps
how much is done; the lists show it and Start-by plans from what's left."""

import datetime as dt


def test_progress_is_kept_shown_and_planned_from(env):
    app = env.app
    env.on("deadlines", "startby")
    dl, sb = app.modules["deadlines"], app.modules["startby"]
    due = dt.datetime.combine(dt.date.today() + dt.timedelta(days=6), dt.time(17))
    dl.add("Problem set 3", due)
    ((i, it),) = [(i, it) for i, it in dl.items().items()]
    whole = sb.size_of(i, it)[0]
    out = env.say("problem set 3 4/7")
    assert out.startswith("Problem set 3: 4/7, 3 to go, due")
    it = dl.items()[i]
    assert (it["parts"], it["parts_done"]) == (7, 4)
    assert abs(sb.size_of(i, it)[0] - whole * 3 / 7) < 1e-9  # what's left
    assert "Problem set 3 (4/7)" in env.say("what's due this week")
    assert env.say("did 7 of 7 on problem set 3").endswith(
        "all done: tap Done on it in /deadlines once it's handed in."
    )
    assert sb.size_of(i, dl.items()[i])[0] == 0.25


def test_numbers_that_name_no_deadline_are_left_alone(env):
    env.on("deadlines")
    env.app.modules["deadlines"].add("Problem set 3", dt.datetime.now() + dt.timedelta(days=3))
    assert env.app.modules["deadlines"].find_open("chemistry lab") is None
    out = env.say("chemistry lab 4/7")
    assert not (out or "").startswith("Chemistry")  # not a deadline: not taken as progress
