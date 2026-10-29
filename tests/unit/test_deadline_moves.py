"""A deadline that moves or is done (0.9.0): deadline_moved and deadline_done carry its id (L26); a new date at the
source (a Classroom post's own id, the calendar or term note, mail) moves the one already there instead of adding a
twin (L28); Revision re-plans today's blocks for a moved exam and drops a done one's (L26); the Agent plan calendar
marks a moved deadline's blocks and asks Remove or Keep, never removing them by itself (L26)."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.core.tools import run_tool
from tests.unit.test_google import allow, gx  # noqa: F401
from tests.unit.test_plan_stale import NEXT, at, night, tonight  # noqa: F401
from tests.unit.test_revision import EXAM, MON, world  # noqa: F401
from tests.unit.test_revision import at as rat

FAR = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(days=10)


def kinds(app, kind: str) -> list[dict]:
    return [e for e in app.events.tail(500, kinds={kind})]


@pytest.fixture
def dl(env):
    env.on("deadlines")
    return env.app.modules["deadlines"]


def only(dl, title: str) -> tuple[str, dict]:
    got = [(i, it) for i, it in dl.items().items() if it["title"] == title]
    assert len(got) == 1, got
    return got[0]


def test_moved_and_done_carry_the_id(env, dl):
    dl.add("Problem set 4", FAR)
    i, _ = only(dl, "Problem set 4")
    dl.move(i, FAR + dt.timedelta(days=2))
    assert kinds(env.app, "deadline_moved")[-1]["id"] == i
    env.app.callback(f"dl:{i}:done")
    assert kinds(env.app, "deadline_done")[-1]["id"] == i


def test_a_classroom_post_with_a_new_due_date_moves_the_one_there(env, dl):
    dl.add("Topology: Sheet 3", FAR, source="classroom", ref="classroom:c1/w1")
    i, _ = only(dl, "Topology: Sheet 3")
    dl.add("Topology: Sheet 3", FAR + dt.timedelta(days=3), source="classroom", ref="classroom:c1/w1")
    j, it = only(dl, "Topology: Sheet 3")
    assert j == i and it["due"].startswith(f"{(FAR + dt.timedelta(days=3)):%Y-%m-%d}")
    ev = kinds(env.app, "deadline_moved")[-1]
    assert ev["id"] == i and ev["source"] == "classroom"
    # another post (another id) with the same title is its own deadline
    dl.add("Topology: Sheet 3", FAR + dt.timedelta(days=9), source="classroom", ref="classroom:c1/w2")
    assert len([x for x in dl.items().values() if x["title"] == "Topology: Sheet 3"]) == 2


def test_mail_giving_a_new_date_moves_the_one_it_gave(env, dl):
    dl.add("Seminar abstract", FAR, source="mail")
    i, _ = only(dl, "Seminar abstract")
    dl.add("Seminar abstract", FAR + dt.timedelta(days=5), source="mail")
    j, it = only(dl, "Seminar abstract")
    assert j == i and kinds(env.app, "deadline_moved")[-1]["source"] == "mail"


def test_a_synced_source_moving_a_date_keeps_the_id(env, dl):
    until = (FAR + dt.timedelta(days=30)).isoformat()
    due = f"{FAR:%Y-%m-%d}T09:00:00"
    later = f"{FAR + dt.timedelta(days=4):%Y-%m-%d}T09:00:00"
    assert dl._sync_source("term-note", [("Analysis midterm", due, {"kind": "exam"})], until) == 1  # noqa: SLF001
    i, _ = only(dl, "Analysis midterm")
    assert dl._sync_source("term-note", [("Analysis midterm", later, {"kind": "exam"})], until) == 0  # noqa: SLF001
    j, it = only(dl, "Analysis midterm")
    assert j == i and it["due"] == later and it["status"] == "open"
    assert kinds(env.app, "deadline_moved")[-1]["id"] == i
    # taken out of the note with nothing like it: gone, as before
    dl._sync_source("term-note", [], until)  # noqa: SLF001
    assert dl.items()[i]["status"] == "gone"


# ------------------------------------------------------------------------------------- revision follows
def test_revision_replans_a_moved_exam_and_drops_a_done_one(world):  # noqa: F811
    env, app, clock = world
    rv = app.modules["exam_season"].revision
    first = rv.today()
    assert [(f"{b['start']:%H:%M}", b["name"]) for b in first] == [("10:00", "Jordan form")]
    dl = app.modules["deadlines"]
    i = next(k for k, it in dl.items().items() if it["kind"] == "exam")
    dl.move(i, EXAM + dt.timedelta(days=3))
    day = rv._state()["days"][MON.isoformat()]  # noqa: SLF001
    assert day["replan"] == [i] and day["blocks"] == []
    again = rv.today()  # worked out again once, for the new date
    assert all(b["exam"] == i for b in again)
    assert rv._state()["days"][MON.isoformat()]["replan"] == []  # noqa: SLF001
    names = lambda bs: [(b["start"], b["name"]) for b in bs]  # noqa: E731
    assert names(rv.today()) == names(again)  # and fixed again
    clock["t"] = rat(MON, 8, 30)
    app.callback(f"dl:{i}:done")
    assert [b for b in rv.today() if b["start"] > clock["t"]] == []


# ----------------------------------------------------------------------------------- the Agent plan asks
def test_a_moved_deadline_marks_its_blocks_and_asks_remove_or_keep(night):  # noqa: F811
    env, ap, clock = night
    app = env.app
    run_tool(app, "reschedule_day", {"start": "22:00"}, via="call")  # the homework's block at 22:00, still ahead
    dl = app.modules["deadlines"]
    hw = next(i for i, it in dl.items().items() if it["title"] == "Bayesian: HW 08")
    dl.move(hw, at(10, 0, NEXT + dt.timedelta(days=6)))
    titles = [b[2] for b in tonight(ap)]
    assert any(t.startswith("Bayesian: HW08 importance sampling (moved to ") for t in titles), titles
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and p.get("reply_markup")][-1]
    assert "Bayesian: HW 08 moved to" in sent["text"] and "remove its 1 plan block from" in sent["text"]
    row = sent["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["Remove", "Keep"]
    # Keep: the title goes back, nothing removed
    assert env.press(row[1]["callback_data"]) == "Kept: the blocks stay where they are."
    assert "Bayesian: HW08 importance sampling" in [b[2] for b in tonight(ap)]
    assert env.press(row[1]["callback_data"]) == "Already answered."


def test_remove_takes_them_out_with_undo(night):  # noqa: F811
    env, ap, clock = night
    run_tool(env.app, "reschedule_day", {"start": "22:00"}, via="call")
    dl = env.app.modules["deadlines"]
    hw = next(i for i, it in dl.items().items() if it["title"] == "Bayesian: HW 08")
    dl.move(hw, at(10, 0, NEXT + dt.timedelta(days=6)))
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and p.get("reply_markup")][-1]
    assert env.press(sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"]).startswith("Removed 1 block.")
    assert not any(b[2].startswith("Bayesian: HW08") for b in tonight(ap))
    assert ap.undo_reschedule().startswith("Put 1 block back")
    assert any(b[2] == "Bayesian: HW08 importance sampling" for b in tonight(ap))
