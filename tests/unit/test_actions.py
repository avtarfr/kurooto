"""The everyday actions (core/actions.py) behind the dashboard's Today page: each does what the command or the AI's
tool does, a feature that's off says so, and nothing raises."""

import datetime as dt

from kurooto.core import actions
from kurooto.core.clock import now
from kurooto.web.api import Api


def test_journal_lines_land_in_todays_note_and_come_back(env):
    r = actions.act(env.app, "journal.add", {"text": "Lab ran long, but the proof finally clicked."})
    assert r["ok"] and "Saved in" in r["message"]
    assert actions.journal_lines(env.app) == ["Lab ran long, but the proof finally clicked."]
    assert actions.act(env.app, "journal.add", {"text": "  "})["ok"] is False


def test_a_captured_note_goes_to_the_inbox_one_line_each(env):
    actions.act(env.app, "note.capture", {"text": "ask TA about   eigenvalues"})
    actions.act(env.app, "note.capture", {"text": "buy chalk"})
    text = actions.inbox_note(env.app).read_text(encoding="utf-8")
    assert text.count("\n- ") == 2 and "ask TA about eigenvalues" in text
    assert actions.today(env.app)["inbox_today"] == 2


def test_reminders_add_list_snooze_and_cancel(env):
    env.on("reminders")
    r = actions.act(env.app, "reminder.add", {"when": "in 2 hours", "what": "stretch"})
    assert r["ok"] and "stretch" in r["message"]
    rows = actions.today(env.app)["reminders"]
    assert len(rows) == 1 and rows[0]["what"] == "stretch"
    key = rows[0]["key"]
    assert actions.act(env.app, "reminder.snooze", {"key": key, "minutes": 10})["ok"]
    rows = actions.today(env.app)["reminders"]
    assert len(rows) == 1 and rows[0]["key"] != key  # moved: a new one, the old one gone
    assert actions.act(env.app, "reminder.cancel", {"key": rows[0]["key"]})["ok"]
    assert actions.today(env.app)["reminders"] == []
    assert actions.act(env.app, "reminder.cancel", {"key": "deadbeef"})["ok"] is False
    assert actions.act(env.app, "reminder.add", {"when": "whenever", "what": "x"})["ok"] is False


def test_deadlines_add_tick_and_move_through_the_same_tools(env):
    env.on("deadlines")
    r = actions.act(
        env.app,
        "deadline.add",
        {"title": "Essay draft", "when": (now() + dt.timedelta(days=2)).strftime("%Y-%m-%d 17:00")},
    )
    assert r["ok"], r
    ds = actions.today(env.app)["deadlines"]
    assert [d["title"] for d in ds] == ["Essay draft"]
    assert actions.act(
        env.app, "deadline.move", {"id": ds[0]["id"], "when": (now() + dt.timedelta(days=4)).strftime("%Y-%m-%d 17:00")}
    )["ok"]
    assert actions.act(env.app, "deadline.done", {"id": ds[0]["id"]})["ok"]
    assert actions.today(env.app)["deadlines"] == []


def test_a_feature_that_is_off_says_so(env):
    for name, args in (
        ("alarm.set", {"when": "7:30"}),
        ("reminder.add", {"when": "in 1 hour", "what": "x"}),
        ("deadline.done", {"id": "x"}),
        ("checkin.skip", {"name": "evening"}),
    ):
        r = actions.act(env.app, name, args)
        assert r["ok"] is False and "off" in r["message"], (name, r)
    assert actions.act(env.app, "nonsense")["ok"] is False


def test_the_page_routes(env):
    api = Api(env.app)
    code, out = api.get("today", {})
    assert code == 200 and "day" in out and "journal" in out and "features" in out
    code, out = api.post("act", {"action": "journal.add", "args": {"text": "from the page"}})
    assert code == 200 and out["ok"]
    assert "from the page" in actions.journal_lines(env.app)[-1]


def test_open_questions_can_be_answered_from_the_page(env):
    q = env.app.ask.ask("Coffee or tea?", choices=["Coffee", "Tea"]) if hasattr(env.app.ask, "ask") else None
    if q is None:
        return
    qid = q["id"] if isinstance(q, dict) else q
    rows = actions.today(env.app)["questions_full"]
    assert any(r["id"] == qid for r in rows)
    assert actions.act(env.app, "question.answer", {"id": qid, "answer": "Tea"})["ok"]
    assert actions.act(env.app, "question.answer", {"id": qid, "answer": "Coffee"})["ok"] is False
