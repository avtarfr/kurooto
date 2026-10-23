"""Study mode on the dashboard: the setting and its event, /study mode and plain English, the timer (focus time that
holds messages, minutes logged to the subject, the break, pause and reset, a longer focus of yours left alone, Study
mode ending with the focus when chosen), what the STUDY pane is given, and the page's markup."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from kurooto.core import actions
from kurooto.core.clock import now
from kurooto.modules import study as study_mod
from kurooto.web.api import Api
from kurooto.web.server import Server

SUBJECTS = [
    {"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]},
    {"name": "Probability", "slug": "probability", "aliases": ["prob"]},
]


@pytest.fixture
def study(env, monkeypatch):
    env.app.settings.set("availability.night.enabled", False)  # the tests run at the real time, maybe at night
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "study")
    monkeypatch.setattr(study_mod, "active_title", lambda: "x")
    return env, env.app.modules["study"]


def later(monkeypatch, minutes):
    t = now() + dt.timedelta(minutes=minutes)
    monkeypatch.setattr(study_mod, "now", lambda: t)
    return t


def test_study_mode_from_the_command_plain_english_and_the_page(study):
    env, _ = study
    assert env.say("/study mode on").startswith("Study mode on:")
    assert env.app.settings.get("look.study_mode") is True
    assert env.app.events.tail(5)[-1]["kind"] == "study_mode" and env.app.events.tail(5)[-1]["on"] is True
    assert env.say("leave study mode").startswith("Study mode off:")
    assert env.app.settings.get("look.study_mode") is False
    assert env.say("turn on study mode").startswith("Study mode on:")
    assert env.say("/study mode off").startswith("Study mode off:")
    assert env.say("/study basket weaving").startswith("I don't know the subject")  # sessions still work as before
    api = Api(env.app)
    assert api.post("act", {"action": "study.mode", "args": {"on": True}})[1]["ok"]
    assert api.get("study", {})[1]["on"] is True
    assert api.post("settings", {"key": "look.study_mode", "value": False}) == (200, {"ok": True})
    # the page is served in the mode it was left in
    page = '<body data-layout="{{LAYOUT}}" data-study="{{STUDY}}">'
    fake = SimpleNamespace(app=env.app, token="t")
    assert 'data-study=""' in Server.fill(fake, page)
    env.app.settings.set("look.study_mode", True)
    assert 'data-study="on"' in Server.fill(fake, page)


def test_a_focus_holds_messages_logs_its_minutes_then_a_break(study, monkeypatch):
    if (now() + dt.timedelta(minutes=30)).date() != now().date():
        pytest.skip("the focus would end after midnight: its minutes count on the day it started")
    env, st = study
    r = actions.act(env.app, "study.timer", {"do": "start", "subject": "la"})
    assert r["ok"] and r["message"].startswith("Linear Algebra: focus until")
    t = st.timer()
    ends = dt.datetime.fromisoformat(t["ends"])
    assert t["phase"] == "focus" and round((ends - now()).total_seconds() / 60) == 25
    assert env.app.availability.focus_until() == ends.replace(microsecond=0)  # calls and messages wait
    assert env.app.scheduler.get("study:timer") and st.session()["timer"]
    assert st.sample(30) is None  # the window doesn't count twice
    env.app.notify("a message that can wait")
    assert "a message that can wait" not in (env.fake.texts() or [])
    later(monkeypatch, 26)  # its end runs a little late: the focus counts at most its length
    st._timer_end({})
    assert st.day()["linear-algebra|manual"] == 1500 and not st.session()
    assert env.app.availability.focus_until() is None
    texts = env.fake.texts()
    assert "a message that can wait" in texts and texts[-1].startswith("Focus done. Linear Algebra: 25 min logged.")
    t = st.timer()
    assert t["phase"] == "break" and st.timer_view()["running"]
    st._timer_end({})  # the break is over: the next focus waits for start
    v = st.timer_view()
    assert v["phase"] == "focus" and not v["running"] and v["round"] == 2 and v["left"] == 1500
    assert env.fake.texts()[-1].startswith("Break's over")
    kinds = [e["kind"] for e in env.app.events.tail(40)]
    assert "study_timer" in kinds and "study_session_end" in kinds


def test_pause_keeps_whats_left_and_stop_or_reset_ends_it(study, monkeypatch):
    env, st = study
    st.timer_start("probability")
    later(monkeypatch, 10)
    assert st.timer_pause() == "Paused. Probability: 10 min logged."
    assert st.timer()["left"] == 900 and env.app.availability.focus_until() is None
    assert not env.app.scheduler.get("study:timer")
    assert st.timer_pause() == "The timer isn't running."
    assert actions.act(env.app, "study.timer", {"do": "start"})["message"].startswith("Probability: focus until")
    assert round((dt.datetime.fromisoformat(st.timer()["ends"]) - study_mod.now()).total_seconds()) == 900
    assert st.timer_start() == "The timer is already running."
    later(monkeypatch, 15)
    assert env.say("/study stop") == "Timer reset. Probability: 5 min logged."  # a stop by hand ends the timer too
    assert not st.timer() and not st.session() and env.app.availability.focus_until() is None
    assert st.day()["probability|manual"] == 900
    assert actions.act(env.app, "study.timer", {"do": "start", "subject": "basket weaving"})["message"].startswith(
        "I don't know the subject"
    )
    assert actions.act(env.app, "study.timer", {"do": "dance"})["ok"] is False


def test_a_longer_focus_of_yours_is_left_alone(study):
    env, st = study
    av = env.app.availability
    mine = (now() + dt.timedelta(hours=2)).replace(microsecond=0)
    av.set_focus(mine)
    st.timer_start("la")
    assert st.timer()["focus_set"] is None
    st.timer_reset()
    assert av.focus_until() == mine


def test_study_mode_ends_with_the_focus_when_you_chose_that(study):
    env, st = study
    env.app.settings.set("study.timer_ends_mode", True)
    actions.study_mode(env.app, True)
    st.timer_start("la")
    assert st.timer_view()["then"] == "end"
    st._timer_end({})
    assert env.app.settings.get("look.study_mode") is False and not st.timer()
    assert "Study mode off" in env.fake.texts()[-1]


def test_the_study_pane_gets_the_subjects_notes_whats_due_and_recall_cards(study):
    env, st = study
    env.on("deadlines", "quiz")
    app = env.app
    root = app.workspace / "linear-algebra"
    root.mkdir(parents=True, exist_ok=True)
    (root / "course.md").write_text("# Linear Algebra\n", encoding="utf-8")
    (root / "2026-10-20-eigenvalues.md").write_text("# Eigenvalues\n", encoding="utf-8")
    (root / "exam-prep.md").write_text("# Prep\n## Must know\n- Rank plus nullity is dimension.\n", encoding="utf-8")
    (app.workspace / "probability").mkdir(exist_ok=True)
    (app.workspace / "probability" / "bayes.md").write_text("# Bayes\n", encoding="utf-8")
    app.modules["deadlines"].add("Linear Algebra quiz", now() + dt.timedelta(days=3), kind="exam")
    app.modules["deadlines"].add("Problem set 4", now() + dt.timedelta(days=5), subject="linear-algebra")
    st.add("probability", 1200)
    code, v = Api(app).get("study", {"subject": "la"})
    assert code == 200 and v["subject"] == "linear-algebra" and v["name"] == "Linear Algebra"
    kinds = {n["id"]: n["kind"] for n in v["notes"]}
    assert kinds == {
        "linear-algebra/course": "course",
        "linear-algebra/exam-prep": "exam_prep",
        "linear-algebra/2026-10-20-eigenvalues": "lecture",
    }
    assert [n["kind"] for n in v["notes"]][:2] == ["course", "exam_prep"]  # its own pages first
    assert {(d["title"], d["kind"]) for d in v["due"]} >= {("Linear Algebra quiz", "exam"), ("Problem set 4", "task")}
    assert v["recall"]["due"] == 1 and v["recall"]["cards"][0]["section"] == "Must know"
    assert v["today"] == [{"slug": "probability", "name": "Probability", "seconds": 1200}]
    assert v["timer"]["phase"] == "" and v["focus_min"] == 25
    # no subject asked: the one studied most today
    assert Api(app).get("study", {})[1]["subject"] == "probability"


def test_without_the_study_tracker_the_mode_still_works_and_the_timer_says_why(env):
    assert actions.act(env.app, "study.mode", {"on": "on"})["ok"] and env.app.settings.get("look.study_mode")
    v = actions.study_view(env.app)
    assert v["timer"] is None and v["subjects"] == [] and v["notes"] == []
    r = actions.act(env.app, "study.timer", {"do": "start"})
    assert r["ok"] is False and "off" in r["message"]
    assert actions.act(env.app, "study.mode", {"on": "off"})["message"].startswith("Study mode off")


def test_the_page_has_the_control_the_pane_and_the_key():
    from importlib import resources

    static = resources.files("kurooto.web") / "static"
    html = (static / "home.html").read_text(encoding="utf-8")
    js = (static / "home.js").read_text(encoding="utf-8")
    css = (static / "home.css").read_text(encoding="utf-8")
    assert 'data-study="{{STUDY}}"' in html and 'id="study-btn"' in html and 'id="pane-study"' in html
    assert "Alt+M study mode" in html
    assert 'e.code === "KeyM"' in js and 'key: "look.study_mode"' in js and 'w: "study"' in js
    assert "prefers-reduced-motion" in css and "cubic-bezier(0.23, 1, 0.32, 1)" in css
