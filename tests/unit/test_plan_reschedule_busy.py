"""A reschedule steps around classes, commitments and calendar events (0.9.0, L51): the day's blocks move to start
then, but a block that would overlap something you have to be at goes after it, and what no longer fits before
LATEST_H is still named and undoable."""

from kurooto.core.tools import run_tool
from tests.unit.test_google import allow, gx  # noqa: F401
from tests.unit.test_plan_stale import DAY, at, night, tonight  # noqa: F401


def test_a_reschedule_goes_around_a_commitment_and_a_class(night):  # noqa: F811
    env, ap, clock = night
    app = env.app
    env.on("commitments", "subjects")
    app.modules["commitments"].add("night shift", [f"{DAY:%a}".lower()], "22:30", "23:30")
    out = run_tool(app, "reschedule_day", {"start": "22:00"}, via="call")
    # the homework (2 h) can't start at 22:00 and run through the shift: it starts after it, then the break and
    # Real Analysis would end after 03:00, so that one is named as not fitting
    assert tonight(ap)[0] == ("23:30", "01:30", "Bayesian: HW08 importance sampling")
    assert "Didn't fit before 03:00, taken off the plan: Real Analysis II: quiz prep" in out
    assert ap.undo_reschedule().startswith("Put ")


def test_without_anything_in_the_way_it_is_as_before(night):  # noqa: F811
    env, ap, clock = night
    env.on("commitments")
    run_tool(env.app, "reschedule_day", {"start": "22:00"}, via="call")
    assert tonight(ap) == [
        ("22:00", "00:00", "Bayesian: HW08 importance sampling"),
        ("00:30", "02:30", "Real Analysis II: quiz prep"),
    ]
    assert ap._busy_else(at(22), at(23)) == []  # noqa: SLF001
