"""Tonight's call (0.8.17): a day planned in the morning, then rescheduled from 22:00 after a quiz that was that morning
and a deadline moved a week out, with three things due the next morning. Blocks for what's over or moved are dropped
and said, what's due soonest goes first, an order the owner gives wins, plan_block doesn't overlap, and remove_blocks
takes blocks out with Undo. The call's instructions say nothing is done until a tool says so."""

import datetime as dt

import pytest

from kurooto.core.tools import run_tool
from kurooto.modules import google_plan
from tests.unit.test_google import allow, gx  # noqa: F401

DAY = (dt.datetime.now() + dt.timedelta(days=2)).date()
NEXT = DAY + dt.timedelta(days=1)


def at(h, m=0, day=DAY):
    return dt.datetime.combine(day, dt.time(h, m))


@pytest.fixture
def night(gx, monkeypatch):  # noqa: F811
    """The morning plan of that day (made with plan_block, as the morning plan does), and what was due."""
    env, g, ai = gx
    allow(env, g, "agent_plan")
    app = env.app
    ap, dl = app.modules["agent_plan"], app.modules["deadlines"]
    clock = {"t": at(7, 30)}
    monkeypatch.setattr(google_plan, "now", lambda: clock["t"])
    dl.add("Time Series Analysis: Quiz 2", at(11), kind="exam")
    dl.add("Lab: Lab Journal Submission", at(23, 59, DAY - dt.timedelta(days=1)))  # overdue that morning
    dl.add("Bayesian: HW 08", at(10, 0, NEXT))
    dl.add("Bayesian: Quiz", at(10, 0, NEXT), kind="exam")
    dl.add("Real Analysis II: Quiz", at(11, 0, NEXT), kind="exam")
    for s, e, title in (
        ("08:15", "10:30", "Time Series Analysis: Quiz 2 revision"),
        ("14:00", "16:00", "Lab: finish and submit journal"),
        ("16:30", "18:30", "Bayesian: HW08 importance sampling"),
        ("19:00", "21:00", "Real Analysis II: quiz prep"),
    ):
        out = run_tool(app, "plan_block", {"start": f"{DAY} {s}", "end": e, "title": title}, via="call")
        assert out.startswith("Planned"), out
    clock["t"] = at(20, 30)
    lab = next(i for i, it in dl.items().items() if it["title"].startswith("Lab"))
    assert dl.move(lab, at(23, 59, DAY + dt.timedelta(days=7))).startswith("Moved")  # move_deadline on the call
    return env, ap, clock


def tonight(ap):
    got = ap.plan_blocks(DAY) + ap.plan_blocks(NEXT)
    return [(f"{b['start']:%H:%M}", f"{b['end']:%H:%M}", b["title"]) for b in sorted(got, key=lambda b: b["start"])]


def test_blocks_know_what_they_are_for(night):
    env, ap, clock = night
    b = next(b for b in ap.plan_blocks(DAY) if b["title"].startswith("Bayesian"))
    assert ap.source(b["title"], DAY, b["item"])[1]["title"] == "Bayesian: HW 08"
    assert b["due"].startswith(f"{NEXT}T10:00")
    # "Bayesian: Quiz prep" is the Bayesian quiz, not Real Analysis's, and not the homework
    assert ap.source("Bayesian: Quiz prep", DAY)[1]["title"] == "Bayesian: Quiz"


def test_reschedule_from_22_drops_what_is_over_or_moved_and_puts_the_soonest_first(night):
    env, ap, clock = night
    out = run_tool(env.app, "reschedule_day", {"start": "22:00"}, via="call")
    # the homework (due 10:00) first, then Real Analysis (11:00), the 30-minute break between them kept
    assert tonight(ap) == [
        ("22:00", "00:00", "Bayesian: HW08 importance sampling"),
        ("00:30", "02:30", "Real Analysis II: quiz prep"),
    ]
    assert "Time Series Analysis: Quiz 2 revision (over (" in out
    assert "Lab: finish and submit journal (moved to " in out
    assert "Didn't fit" not in out
    assert "Due within a day with no block yet: Bayesian: Quiz (" in out  # said, so the call can plan it
    # a second reschedule sees the blocks past midnight too (no duplicates, nothing lost)
    clock["t"] = at(21, 0)
    run_tool(env.app, "reschedule_day", {"start": "22:00"}, via="call")
    assert [b[2] for b in tonight(ap)] == ["Bayesian: HW08 importance sampling", "Real Analysis II: quiz prep"]
    # Undo puts back the plan before that reschedule
    assert ap.undo_reschedule().startswith("Put 2 blocks back")


def test_an_order_they_give_wins(night):
    env, ap, clock = night
    out = run_tool(
        env.app, "reschedule_day", {"start": "22:00", "order": "quiz prep first, then homework, then stats"}, via="call"
    )
    assert [b[2] for b in tonight(ap)] == ["Real Analysis II: quiz prep", "Bayesian: HW08 importance sampling"]
    assert "No block for: stats" in out


def test_plan_block_never_overlaps_and_never_plans_what_is_over(night):
    env, ap, clock = night
    run_tool(env.app, "reschedule_day", {"start": "22:00"}, via="call")
    # tonight's overlap: no free time after the homework and Real Analysis before 03:00, so it isn't planned
    out = run_tool(
        env.app, "plan_block", {"start": f"{DAY} 22:00", "end": f"{NEXT} 00:00", "title": "Bayesian: Quiz prep"}
    )
    assert out.startswith(
        "Not planned: 22:00–00:00 overlaps Bayesian: HW08 importance sampling (22:00–00:00), and there's no free time"
    )
    out = run_tool(env.app, "plan_block", {"start": f"{DAY} 21:00", "end": f"{DAY} 22:00", "title": "Bayesian: Quiz"})
    assert out == f"Planned {DAY:%a} 21:00–22:00: Bayesian: Quiz."
    out = run_tool(env.app, "plan_block", {"start": f"{DAY} 21:30", "end": f"{DAY} 22:00", "title": "Break"})
    assert out == (
        "21:30–22:00 overlapped Bayesian: Quiz (21:00–22:00), so it went in the first free time after: "
        f"Planned {NEXT:%a} 00:00–00:30: Break."
    )
    out = run_tool(
        env.app, "plan_block", {"start": f"{DAY} 23:00", "end": f"{DAY} 23:30", "title": "Time Series: Quiz 2 revision"}
    )
    assert out.startswith("Not planned: Time Series Analysis: Quiz 2 is over (")


def test_remove_blocks_by_name_or_time_with_undo(night):
    env, ap, clock = night
    run_tool(env.app, "reschedule_day", {"start": "22:00"}, via="call")
    out = run_tool(env.app, "remove_blocks", {"what": "real analysis"}, via="call")
    assert out.startswith("Removed 1 block from the plan: Real Analysis II: quiz prep (00:30–02:30)")
    assert [b[2] for b in tonight(ap)] == ["Bayesian: HW08 importance sampling"]
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and p.get("reply_markup")][-1]
    undo = sent["reply_markup"]["inline_keyboard"][0][0]
    assert undo["text"] == "Undo" and undo["callback_data"].startswith("apl:")
    assert env.press(undo["callback_data"]).startswith("Put 1 block back")
    assert len(tonight(ap)) == 2
    assert env.press(undo["callback_data"]).startswith("The plan changed again since")
    assert run_tool(env.app, "remove_blocks", {"what": "physics"}, via="call").startswith(
        "No planned block matches that, so nothing was removed. Planned now: 22:00–00:00 Bayesian"
    )
    assert run_tool(env.app, "remove_blocks", {"what": "those sessions"}, via="call").startswith("Which blocks?")
    clock["t"] = at(23, 30)  # a time already past tonight still means tonight
    out = run_tool(env.app, "remove_blocks", {"after": "23:00"}, via="call")
    assert out.startswith("Removed 1 block") and [b[2] for b in tonight(ap)] == ["Bayesian: HW08 importance sampling"]
    assert run_tool(env.app, "undo_plan", {}, via="call").startswith("Put 1 block back")
    assert env.say("/blocks remove all").startswith("Removed 2 blocks") and tonight(ap) == []


def test_the_call_is_told_to_say_only_what_a_tool_did(env):
    cfg = env.app.modules["calls"].config_template()
    assert "unless a tool's result in this call says it was done" in cfg["systemInstruction"]
