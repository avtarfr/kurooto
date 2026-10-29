"""Planning links, 0.9.0: Start-by counts the study tracker's time with a tap to use it (L52) and says Brain's miss
risk, with a weekly offer to change its share (L54); a block that starts with you at the desk offers a focus (L56);
Face helps the study tracker by asking, never by dropping time (L58); phone places offer a study session (L59) and
ask "went to it?" during a class (L61); the exam debrief can wait for you to be back (L62); the wake-up call and
the night check-in name the exam (L44). Every one behind its own switch."""

import datetime as dt
import json

import pytest

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.state import jsave
from kurooto.mind import presence_forecast as pf
from kurooto.mind.senses import phone


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["subjects", "deadlines", "reminders", "study", "startby", "exam_season"])
    a.settings.set("availability.night.enabled", False)
    a.settings.set("subjects.list", [{"slug": "topology", "name": "Topology"}])
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)) or "m1")
    yield a
    mind.forget_client(a)
    a.close()


def add(app, title, hours, **kw):
    dl = app.modules["deadlines"]
    dl.add(title, now() + dt.timedelta(hours=hours), **kw)
    return next(i for i, it in dl.items().items() if it["title"] == title)


def row(app, i):
    return next(r for r in app.modules["startby"].plan() if r["id"] == i)


# ------------------------------------------------------------------------------------------ Start-by
def test_time_to_start_counts_study_and_count_it_sets_the_size(app):
    sb, st = app.modules["startby"], app.modules["study"]
    i = add(app, "Topology report", 24 * 5, subject="topology")
    st.add("topology", 3 * 3600)  # three hours this week, its subject's only deadline
    assert sb.studied_h(row(app, i)) == pytest.approx(3.0)
    sb._tell(row(app, i))  # noqa: SLF001
    text, kw = app.sent[-1]
    assert "You've put about 3 h into it already; about 9 h left if that counts." in text
    assert kw["buttons"][0] == [("Count it", f"sby:{i}:9")]
    assert sb.size_of(i, app.modules["deadlines"].items()[i])[0] == 12  # unchanged until the tap
    assert app.callback(f"sby:{i}:9").startswith("Topology report: about 9 h")
    # a second deadline in the subject: it can't tell which, so nothing is said
    add(app, "Topology sheet", 24 * 6, subject="topology")
    assert sb.studied_h(row(app, i)) == 0.0
    # sessions tied to the deadline (Study push's Start) count exactly
    app.events.emit("study_session_end", subject="topology", minutes=90, deadline=i)
    assert sb.studied_h(row(app, i)) == pytest.approx(1.5)
    app.settings.set("startby.count_study", False)
    assert sb.studied_h(row(app, i)) == 0.0


def test_miss_risk_is_said_when_brains_plans_think_it_may_slip(app, monkeypatch):
    from kurooto.mind import plans

    sb = app.modules["startby"]
    i = add(app, "Topology report", 24 * 5, subject="topology")
    jsave(app.paths.state / "mind-plan-last.json", {"on": "x", "risks": {f"d:{i}": 0.4}})
    assert sb.miss_risk(i) == 0.0  # Brain's plans are off
    monkeypatch.setattr(plans, "on", lambda a: True)
    assert sb.miss_risk(i) == 0.4
    sb._tell(row(app, i))  # noqa: SLF001
    assert "about a 40% chance of missing it" in app.sent[-1][0]
    app.settings.set("startby.miss_risk", False)
    assert sb.miss_risk(i) == 0.0


def test_the_share_is_offered_from_your_pace_never_set_by_itself(app, monkeypatch):
    from kurooto.mind.plans import pace

    sb = app.modules["startby"]
    assert sb.learn_share() == ""  # off by default
    app.settings.set("startby.learn_share", True)
    monkeypatch.setattr(pace, "samples", lambda a, today=None: {d: [8.0] for d in range(7)})
    line = sb.learn_share()
    assert "use 60% instead?" in line and "count 40%" in line  # 8 h of 13 free a day
    assert app.settings.get("startby.share") == 40  # only an offer
    assert sb.learn_share() == ""  # once a week
    assert app.callback("sby:share:yes") == "Done: 60%."
    assert app.settings.get("startby.share") == 60
    assert app.callback("sby:share:undo").startswith("Back to 40%")
    assert app.settings.get("startby.share") == 40


# -------------------------------------------------------------------------------------- Face, places
def test_on_paper_is_asked_once_and_counted_only_on_yes(app, monkeypatch):
    st = app.modules["study"]
    st._last_slug = "topology"  # noqa: SLF001
    monkeypatch.setattr(st, "_face_sees_you", lambda: True)
    st._ask_paper()  # noqa: SLF001
    assert app.sent == []  # study.face is off by default
    app.settings.set("study.face", True)
    st._ask_paper()  # noqa: SLF001
    st._ask_paper()  # noqa: SLF001
    assert len(app.sent) == 1 and "on paper?" in app.sent[0][0]
    assert st.session() == {}  # nothing counted without a Yes
    assert app.callback("stf:topology:paper").startswith("Topology: session started")
    st.stop_session()


def test_stepping_away_in_a_focus_offers_a_pause_and_back_a_resume(app):
    st = app.modules["study"]
    app.settings.set("study.face", True)
    st.timer_start("topology")
    st.face_event("left")
    assert app.sent[-1][1]["buttons"] == [[("Pause", "stf:-:pause")]]
    assert st.timer()["ends"]  # nothing paused by itself
    assert app.callback("stf:-:pause").startswith("Paused.")
    st.face_event("back")
    assert app.sent[-1][1]["buttons"] == [[("Resume", "stf:-:resume")]]
    assert app.callback("stf:-:resume").startswith("Topology: focus until")
    st.timer_reset()


def test_arriving_at_a_saved_place_offers_a_session_and_leaving_ends_it(app):
    st = app.modules["study"]
    add(app, "Topology report", 24 * 3, subject="topology")
    st.place_event("Library", "arrive")
    assert app.sent == []  # study.places is off by default
    app.settings.set("study.places", True)
    st.place_event("Library", "arrive")
    text, kw = app.sent[-1]
    assert "Library" not in text and kw["buttons"][0] == [("Topology", "stp:topology:go")]
    st.place_event("Library", "arrive")
    assert len(app.sent) == 1  # once a day per place
    assert app.callback("stp:topology:go").startswith("Topology: session started")
    st.place_event("Cafe", "leave")
    assert st.session().get("subject") == "topology"  # another place: nothing
    st.place_event("Library", "leave")
    assert st.session() == {} and app.sent[-1][0].startswith("Session ended as you left.")


def test_phone_places_reach_the_features_only_when_fresh(app, monkeypatch):
    got = []
    monkeypatch.setattr(app.modules["study"], "place_event", lambda *a: got.append(a))
    t = now().timestamp()
    phone.place_hooks(app, "arrive", "Library", t)
    phone.place_hooks(app, "arrive", "Library", t - 3600)  # an old one: kept only
    phone.place_hooks(app, "noise", "Library", t)
    assert [a[:2] for a in got] == [("Library", "arrive")]


def test_went_to_class_is_asked_by_place_and_never_inferred(app, monkeypatch):
    subj = app.modules["subjects"]
    start = (now() - dt.timedelta(minutes=10)).replace(second=0, microsecond=0)
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][start.weekday()]
    end = start + dt.timedelta(hours=1)
    app.settings.set(
        "subjects.timetable",
        [{"day": day, "start": f"{start:%H:%M}", "end": f"{end:%H:%M}", "subject": "topology"}],
    )
    subj.place_event("Campus", "arrive")
    assert app.sent == []  # subjects.attend_by_place is off by default
    app.settings.set("subjects.attend_by_place", True)
    subj.place_event("Campus", "arrive")
    text, kw = app.sent[-1]
    assert "Went to it?" in text and "Campus" not in text
    data = kw["buttons"][0][0][1]
    f = subj._catch_file(start.date())  # noqa: SLF001
    assert json.loads(f.read_text(encoding="utf-8"))["topology"] == {"asked": True}  # not a "went"
    assert app.callback(data) == "OK, you went: no catch-up for it."
    assert json.loads(f.read_text(encoding="utf-8"))["topology"] == {"went": True}


# ----------------------------------------------------------------------------------------- exams
def test_the_debrief_waits_for_you_back_at_most_90_minutes(app, monkeypatch):
    from kurooto.modules import exam_season as es_mod

    es = app.modules["exam_season"]
    t = now()
    e = {"id": "x1", "end": t - dt.timedelta(minutes=15), "day": t.date(), "start": t - dt.timedelta(hours=3)}
    t = now()
    assert es._debrief_due(e, t) is False  # noqa: SLF001  (as before: 30 minutes after it ends)
    app.settings.set("exam_season.debrief_at_desk", True)
    monkeypatch.setattr(pf, "at_desk", lambda a, t=None: False)
    assert es._debrief_due(e, t) is False  # noqa: SLF001
    es.place_event("Home", "arrive", t)
    assert es._debrief_due(e, t) is True  # noqa: SLF001  (home before the half hour)
    with_desk = {**e, "end": t - dt.timedelta(minutes=5)}
    monkeypatch.setattr(es, "_load", lambda: {})
    assert es._debrief_due(with_desk, t) is False  # noqa: SLF001
    monkeypatch.setattr(pf, "at_desk", lambda a, t=None: True)
    assert es._debrief_due(with_desk, t) is True  # noqa: SLF001
    monkeypatch.setattr(pf, "at_desk", lambda a, t=None: False)
    late = {**e, "end": t - dt.timedelta(minutes=es_mod.DEBRIEF_WAIT_MIN + 1)}
    assert es._debrief_due(late, t) is True  # noqa: SLF001  (never later than 90 minutes)


def test_the_calls_name_the_exam_and_propose_a_wake_time(app):
    es = app.modules["exam_season"]
    tomorrow = dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(9, 0))
    app.settings.set("exam_season.quizzes", True)
    app.modules["deadlines"].add("Topology final exam", tomorrow, subject="topology", kind="exam")
    line = es.call_line("tomorrow")
    assert line.startswith("Tomorrow: Topology final exam at 09:00, leave by 08:15.")
    assert "Propose waking at 07:15" in line and "only if they agree" in line
    assert es.call_line("today", tomorrow - dt.timedelta(hours=3)).startswith("Today: Topology final exam at 09:00")
    app.settings.set("exam_season.in_calls", False)
    assert es.call_line("tomorrow") == ""


def test_a_block_starting_with_you_at_the_desk_offers_a_focus(app, monkeypatch):
    from kurooto.modules.google_plan import AgentPlan

    ap = AgentPlan(app)
    i = add(app, "Topology report", 24 * 3, subject="topology")
    t = now().replace(second=0, microsecond=0)
    jsave(ap.file, {"days": {t.date().isoformat(): [
        {"title": "Topology report", "start": (t - dt.timedelta(minutes=2)).isoformat(),
         "end": (t + dt.timedelta(hours=1)).isoformat()}]}})  # fmt: skip
    monkeypatch.setattr(pf, "at_desk", lambda a, t=None: False)
    assert ap.block_start(t) is False and app.sent == []  # away: nothing, nothing noted
    monkeypatch.setattr(pf, "at_desk", lambda a, t=None: True)
    assert ap.block_start(t) is True
    text, kw = app.sent[-1]
    assert text.startswith("Your block Topology report starts now. Start a 25-minute focus")
    assert ap.block_start(t) is False  # once per block
    assert ap._button("focus", "start").startswith("Topology: focus until")  # noqa: SLF001
    assert app.modules["study"].timer()["deadline"] == i
    app.modules["study"].timer_reset()
