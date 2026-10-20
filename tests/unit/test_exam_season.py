"""Exam season (modules/exam_season.py): nothing without exam dates; the season from exam periods and exams; the update
hold (and a release signed as critical); the eve question and the leave-by alarm (a call, or a message); the debrief
into the course note; the nightly alarm check; the quiz call only when picked; the card and its switches. A fake clock
for the features and the scheduler; rings are recorded, not placed."""

from __future__ import annotations

import asyncio
import datetime as dt
import json

import pytest

from kurooto.core import ask as ask_mod
from kurooto.core.health import Check
from kurooto.modules import alarm as alarm_mod
from kurooto.modules import deadlines as dl_mod
from kurooto.modules import exam_season as es_mod
from kurooto.modules import quiz as quiz_mod
from kurooto.modules.calls import deploy
from kurooto.update import service as service_mod
from kurooto.update.updater import Release
from kurooto.web.api import Api

TUE = dt.date(2026, 12, 8)  # the Linear Algebra exam


def at(day: dt.date, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(h, m))


def days(n: int) -> dt.timedelta:
    return dt.timedelta(days=n)


def local(job) -> dt.datetime:
    """When a scheduled job runs, in local time."""
    return dt.datetime.fromtimestamp(job.next_run)


class World:
    """The time the features and the scheduler see; tick() runs what's due then."""

    def __init__(self, env, monkeypatch, t: dt.datetime):
        self.env, self.app, self.t = env, env.app, t
        for mod in (es_mod, dl_mod, ask_mod, quiz_mod, alarm_mod, service_mod):
            monkeypatch.setattr(mod, "now", lambda: self.t)
        monkeypatch.setattr(self.app.scheduler, "clock", lambda: self.t.timestamp())
        self.rang: list[tuple[str, bool, str]] = []
        monkeypatch.setattr(
            self.app.modules["calls"],
            "ring",
            lambda reason, alarm=False, key="", buttons=None, **kw: self.rang.append((key, alarm, reason)) or "1",
        )

    @property
    def es(self):
        return self.app.modules["exam_season"]

    def go(self, t: dt.datetime) -> dict:
        """It's t now: the exam season's tick runs."""
        self.t = t
        return self.es._tick()

    def run_due(self, t: dt.datetime):
        self.t = t
        return asyncio.run(self.app.scheduler.tick())

    def texts(self) -> list[str]:
        return self.env.fake.texts()

    def question(self) -> dict:
        return self.app.ask.pending(source="exam_season")[-1]


def exam_id(app, title: str) -> str:
    return next(i for i, it in app.modules["deadlines"].items().items() if it["title"] == title)


@pytest.fixture
def season(env, monkeypatch):
    app = env.app
    app.settings.set("availability.night.enabled", False)
    w = World(env, monkeypatch, at(dt.date(2026, 12, 1), 10))
    env.on("subjects", "deadlines")
    env.say("/subject add Linear Algebra (la)")
    env.say("/subject add Topology")
    env.on("exam_season")
    return w


def with_calls(w: World) -> World:
    app = w.app
    app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(app)
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    w.env.on("calls")
    return w


# --------------------------------------------------------------------------------------- the exam dates
def test_nothing_happens_without_exam_dates(season):
    w, app = season, season.app
    before = len(w.texts())
    for t in (at(dt.date(2026, 12, 1), 18, 30), at(dt.date(2026, 12, 1), 21, 45), at(dt.date(2026, 12, 2), 9)):
        assert w.go(t) == {}
    assert len(w.texts()) == before and app.ask.pending() == []
    assert w.es.update_hold() == "" and w.es.budget_during_exams() is None and app.updates.held() == ""
    assert w.es.card()["lines"][0].startswith("No exam dates yet, so nothing happens.")
    assert w.env.say("/examseason").startswith("Exam season. No exam dates yet")
    # a weekly quiz outside an exam period isn't an exam season, unless quizzes count
    app.modules["deadlines"].add("Topology quiz", at(dt.date(2026, 12, 3), 10))
    assert w.es.exams() == [] and w.go(at(dt.date(2026, 12, 2), 18, 30)) == {}
    app.settings.set("exam_season.quizzes", True)
    assert [e["title"] for e in w.es.exams()] == ["Topology quiz"]


def test_the_season_its_first_message_and_the_update_hold(season):
    w, app = season, season.app
    dl = app.modules["deadlines"]
    app.settings.set("subjects.exam_periods", [["2026-12-07", "2026-12-11"]])
    dl.add("Linear Algebra final exam", at(TUE, 9))
    dl.add("Topology quiz", at(dt.date(2026, 12, 10), 10))  # inside the exam period: it counts
    dl.add("Statistics quiz", at(dt.date(2026, 12, 3), 10))  # outside: it doesn't
    assert [e["title"] for e in w.es.exams()] == ["Linear Algebra final exam", "Topology quiz"]
    assert w.es.seasons() == [(dt.date(2026, 12, 7), dt.date(2026, 12, 11))]
    w.go(at(dt.date(2026, 12, 5), 12))
    assert not [t for t in w.texts() if t.startswith("Exam season")] and app.updates.held() == ""
    w.go(at(dt.date(2026, 12, 6), 12))  # the day before the first exam day
    said = [t for t in w.texts() if t.startswith("Exam season:")]
    assert said == [
        "Exam season: Mon 7 Dec to Fri 11 Dec, 2 exams. Until it's over: updates wait (critical fixes still install); "
        "your alarm is checked every night; the evening before each exam I ask where it is; an alarm to leave on "
        "time; a two-minute debrief after each one; no calls during an exam; during the day only deadlines, quizzes "
        "and the alarm message you (the rest waits for the evening). /examseason shows it and switches parts off."
    ]
    w.go(at(dt.date(2026, 12, 6), 12, 15))
    assert len([t for t in w.texts() if t.startswith("Exam season:")]) == 1  # once a season
    assert app.updates.held() == "your exams (until Fri 11 Dec)"
    assert w.es.budget_during_exams() == {"keep": es_mod.BUDGET_KEEP, "until": at(dt.date(2026, 12, 11), 23, 59)}
    app.settings.set("exam_season.hold_updates", False)
    assert app.updates.held() == ""
    app.settings.set("exam_season.hold_updates", True)
    w.t = at(dt.date(2026, 12, 12), 3)
    assert app.updates.held() == "" and w.es.season() is None
    app.disable("exam_season")
    assert "exam_season" not in app.updates.holds and "exam_season:exam" not in app.availability.blockers


def test_updates_wait_during_exams_unless_critical(season, monkeypatch, tmp_path):
    w, app = season, season.app
    app.modules["deadlines"].add("Linear Algebra final exam", at(TUE, 9))
    w.t = at(dt.date(2026, 12, 7), 20)
    up = app.updates
    staged: list[str] = []
    monkeypatch.setattr(up.u, "managed", lambda: True)
    monkeypatch.setattr(up, "_stage_then_wait", lambda rel: staged.append(rel.version))
    monkeypatch.setattr(up, "switch_to", lambda v: f"switching to {v}")
    monkeypatch.setattr("kurooto.update.service.threading.Thread", _Inline)
    rel = Release("9.0.0", "stable", 0, {}, "notes")
    monkeypatch.setattr(up.u, "check", lambda channel="stable": rel)
    assert up.check() == "9.0.0 is held back: your exams (until Tue 8 Dec)" and staged == []
    assert json.loads(up.ready_file.read_text())["held"] == "your exams (until Tue 8 Dec)"
    rel.critical = True
    assert up.check() == "preparing 9.0.0" and staged == ["9.0.0"]  # a critical fix doesn't wait
    # prepared before the hold began: the switch waits a day, unless it's critical
    up.ready_file.write_text(json.dumps({"version": "9.0.0", "staged": True, "notes": ""}))
    assert up.apply_if_quiet() == "held back: your exams (until Tue 8 Dec)"
    assert app.scheduler.get("updates:apply").next_run == pytest.approx((w.t + days(1)).timestamp())
    up.ready_file.write_text(json.dumps({"version": "9.0.0", "staged": True, "notes": "", "critical": True}))
    assert up.apply_if_quiet() == "switching to 9.0.0"
    w.t = at(dt.date(2026, 12, 9), 3)  # the exams are over
    rel.critical = False
    assert up.check() == "preparing 9.0.0"


class _Inline:
    """threading.Thread that runs at once (the update service stages in a thread)."""

    def __init__(self, target=None, args=(), **kw):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def test_the_signed_manifest_says_critical(tmp_path):
    from tests.unit.test_prereqs import Files
    from tests.unit.test_update import KEY, updater, wrap

    site = Files()
    try:
        man = {"version": "0.9.0", "files": {}, "critical": True}
        site.files["/releases/0.9.0/manifest.json"] = wrap(man, KEY)
        ptr = {"version": "0.9.0", "manifest_url": f"{site.base}/releases/0.9.0/manifest.json", "issued": 1}
        site.files["/stable.json"] = wrap(ptr, KEY)
        assert updater(tmp_path, site).check().critical is True
        man.pop("critical")
        site.files["/releases/0.9.0/manifest.json"] = wrap(man, KEY)
        site.files["/stable.json"] = wrap({**ptr, "issued": 2}, KEY)
        assert updater(tmp_path, site).check().critical is False
    finally:
        site.server.shutdown()


# ------------------------------------------------------------------------------ the eve and leaving on time
def test_the_eve_question_and_the_leave_by_call(season):
    w = with_calls(season)
    app = w.app
    app.modules["deadlines"].add("Linear Algebra final exam", at(TUE, 9))
    i = exam_id(app, "Linear Algebra final exam")
    w.go(at(TUE - days(1), 17, 50))
    assert app.ask.pending(source="exam_season") == []  # not before 18:00
    w.go(at(TUE - days(1), 18, 5))
    q = w.question()
    assert q["text"] == (
        "Tomorrow: Linear Algebra final exam at 09:00. Where is it, which seat? Calculator? ID card? Reply in one "
        'line, like "Hall B, seat 34, calculator, ID card". I\'ll ring you at 08:15 to leave ("leave 8:00" '
        'changes it, "no alarm" turns it off).'
    )
    job = app.scheduler.get(f"calls:ring:exam_season:leave:{i}")
    assert local(job) == at(TUE, 8, 15) and job.payload["alarm"] is True
    w.go(at(TUE - days(1), 18, 20))
    assert len(app.ask.pending(source="exam_season")) == 1  # asked once
    out = app.ask.answer(q["id"], "Hall B, seat 34, calculator, ID card, leave 8:00", via="test")
    assert out["note"] == "Kept for the exam day. I'll ring you at 08:00 to leave."
    job = app.scheduler.get(f"calls:ring:exam_season:leave:{i}")
    assert local(job) == at(TUE, 8)
    assert job.payload["reason"] == (
        "Time to leave for Linear Algebra final exam at 09:00. You said: Hall B, seat 34, calculator, ID card, "
        "leave 8:00."
    )
    assert job.module == "calls" and job.payload["key"] == f"exam_season:leave:{i}"  # the call line gets it a day ahead
    assert w.es.call_brief()["exam_season"] == [
        "Linear Algebra final exam: Tue 8 Dec 09:00. Hall B, seat 34, calculator, ID card, leave 8:00. Leave 08:00"
    ]
    w.go(at(TUE - days(1), 18, 35))
    assert local(app.scheduler.get(f"calls:ring:exam_season:leave:{i}")) == at(TUE, 8)  # kept
    # the morning: "Later" rings again in 5 minutes (twice), a missed one is an urgent message too
    w.t = at(TUE, 8)
    key = f"exam_season:leave:{i}"
    assert w.es.call_outcome(key, "later") is True
    assert local(app.scheduler.get(f"calls:ring:{key}")) == at(TUE, 8, 5)
    assert w.es.call_outcome(key, "missed") is False
    assert "Time to leave for Linear Algebra final exam at 09:00." in w.texts()[-1]
    # no calls during the exam (from 15 minutes before), and not with that part off
    assert app.availability.call_block(at(TUE, 8, 50)) == ("you're in an exam", at(TUE, 12))
    assert app.availability.call_block(at(TUE, 12, 5)) == (None, None)
    app.settings.set("exam_season.no_calls", False)
    assert app.availability.call_block(at(TUE, 9, 30)) == (None, None)


def test_without_calls_the_time_unknown_and_no_alarm(season):
    w, app = season, season.app
    dl = app.modules["deadlines"]
    thu = dt.date(2026, 12, 10)
    dl.add("Topology midterm", at(thu, 23, 59))  # the time isn't known
    dl.add("Linear Algebra viva", at(thu, 11))
    w.go(at(thu - days(1), 18, 1))
    qs = {q["text"].split(":")[1].split(" (")[0].split(" at")[0].strip(): q for q in app.ask.pending()}
    topo, viva = qs["Topology midterm"], qs["Linear Algebra viva"]
    assert topo["text"].startswith(
        "Tomorrow: Topology midterm (I don't know the time). Where and when is it, which seat? Calculator? ID card?"
    )
    assert topo["text"].endswith("With the start time I'll message you 45 minutes before it, to leave.")
    i = exam_id(app, "Topology midterm")
    assert app.scheduler.get(f"exam_season:leave:{i}") is None
    out = app.ask.answer(topo["id"], "Room 4, seat 12, starts 2", via="test")
    assert out["note"] == "Kept for the exam day. I'll message you at 13:15 to leave."
    assert [e["start"] for e in w.es.exams() if e["id"] == i] == [at(thu, 14)]
    out = app.ask.answer(viva["id"], "Lab 2, no alarm please", via="test")
    assert out["note"] == "Kept for the exam day. No alarm to leave."
    assert app.scheduler.get(f"exam_season:leave:{exam_id(app, 'Linear Algebra viva')}") is None
    w.run_due(at(thu, 13, 15))
    assert w.texts()[-1].endswith("Time to leave for Topology midterm at 14:00. You said: Room 4, seat 12, starts 2.")
    # switched off: no leave-by alarm at all
    app.settings.set("exam_season.leave_alarm", False)
    dl.add("Topology final exam", at(thu + days(4), 9))
    w.go(at(thu + days(3), 18, 30))
    assert app.scheduler.get(f"exam_season:leave:{exam_id(app, 'Topology final exam')}") is None
    assert "to leave" not in w.question()["text"]


# ------------------------------------------------------------------------------------------- the debrief
def test_the_debrief_goes_into_the_course_note(season):
    w, app = season, season.app
    dl = app.modules["deadlines"]
    dl.add("Topology midterm", at(TUE, 9))
    dl.add("Group viva", at(TUE, 14))  # no subject: the daily note
    course = app.workspace / "topology" / "course.md"
    course.parent.mkdir(parents=True, exist_ok=True)
    course.write_text("# Topology\n\nMy own words about the course.\n", encoding="utf-8")
    app.settings.set("exam_season.eve", False)
    w.go(at(TUE, 12, 25))
    assert app.ask.pending(source="exam_season") == []  # 3 h exam + 30 min: not yet
    w.go(at(TUE, 12, 31))
    q = w.question()
    assert q["text"] == (
        "How did Topology midterm go? Two minutes: what came up, what went well, what to fix before the next one. "
        "It goes into topology/course.md, as you say it."
    )
    w.go(at(TUE, 12, 46))
    assert len(app.ask.pending(source="exam_season")) == 1
    out = app.ask.answer(q["id"], "Compactness proof came up. Ran out of time on Q4.", via="test")
    assert out["note"] == "Saved to topology/course.md."
    text = course.read_text(encoding="utf-8")
    assert text.startswith("# Topology\n\nMy own words about the course.\n")
    assert "## Exam debriefs\n### Topology midterm (2026-12-08)\n\nCompactness proof came up." in text
    w.go(at(TUE, 17, 31))
    viva = w.question()
    assert "It goes into journal/2026-12-08.md" in viva["text"]
    assert app.ask.answer(viva["id"], "Nothing new", via="test")["note"] == "OK, no debrief this time."
    assert not (app.workspace / "journal" / "2026-12-08.md").exists()
    w.es.save_debrief(None, "Group viva", TUE, "Went fine.")
    assert "## Exam debrief: Group viva\n\nWent fine." in (app.workspace / "journal" / "2026-12-08.md").read_text()
    # a new course note gets a header and a title; switched off, no debrief is asked
    f = w.es.save_debrief("linear-algebra", "Linear Algebra midterm", TUE, "Eigenvalues.")
    assert f.read_text(encoding="utf-8").split("---\n\n", 1)[1].startswith("# Linear Algebra\n\n## Exam debriefs")
    app.settings.set("exam_season.debrief", False)
    dl.add("Topology final exam", at(TUE + days(2), 9))
    assert "debrief" not in w.go(at(TUE + days(2), 12, 40))


def told(w: World) -> list[str]:
    """The alarm-path messages (Kurooto keeps itself working's way of saying it)."""
    return [t for t in w.texts() if "Set your phone's own alarm too" in t]


def checked(app) -> list[dict]:
    return [e for e in map(json.loads, app.events.file.read_text().splitlines()) if e["kind"] == "exam_alarm_checked"]


def again(w: World) -> None:
    """Forget that tonight was checked (as if it were another night)."""
    w.es.file.write_text(json.dumps({**json.loads(w.es.file.read_text()), "night": ""}))


# ------------------------------------------------------------------------------------ the nightly alarm check
def test_the_alarm_path_is_checked_every_night_of_the_period(season, monkeypatch):
    w = with_calls(season)
    app = w.app
    w.env.on("alarm")
    alarm = app.modules["alarm"]
    probe = {"ok": False}
    monkeypatch.setattr(
        alarm,
        "health_check",
        lambda: Check(
            "alarm",
            "Morning alarm",
            probe=lambda net: (True, "fine") if probe["ok"] else (False, "Your alarm at 07:00 might not ring"),
            kind="alarm",
            urgent=True,
        ),
    )
    monkeypatch.setattr(alarm, "next", lambda: at(TUE, 7))
    app.settings.set("subjects.exam_periods", [["2026-12-08", "2026-12-09"]])
    app.settings.set("exam_season.leave_alarm", False)  # the alarm's check alone (a leave-by call adds the line's)
    app.modules["deadlines"].add("Linear Algebra final exam", at(TUE, 9))
    w.go(at(TUE - days(2), 21, 40))  # not a night of the period
    w.go(at(TUE - days(1), 21, 20))  # too early
    assert told(w) == []
    w.go(at(TUE - days(1), 21, 35))
    assert told(w) == ["Your alarm at 07:00 might not ring. Set your phone's own alarm too."]
    w.go(at(TUE - days(1), 21, 50))
    assert len(told(w)) == 1  # once a night
    events = [json.loads(x) for x in app.events.file.read_text().splitlines()]
    assert [e["problems"] for e in events if e["kind"] == "exam_alarm_checked"] == [1]
    # the next night of the period: checked again; fine now, so nothing is said
    probe["ok"] = True
    w.go(at(TUE, 21, 35))
    assert len(told(w)) == 1
    # a morning exam and no alarm before it: one line
    monkeypatch.setattr(alarm, "next", lambda: None)
    app.modules["deadlines"].add("Topology final exam", at(TUE + days(1), 10))
    again(w)
    w.go(at(TUE, 21, 45))
    assert w.texts()[-1] == (
        "No alarm is set for tomorrow, and Topology final exam is at 10:00. /alarm 7:00 sets one (or set your phone's "
        "own)."
    )
    assert [e["checks"] for e in checked(app)] == [1, 1, 1]
    # a leave-by call for tomorrow: the call line's check runs too
    app.settings.set("exam_season.leave_alarm", True)
    again(w)
    w.go(at(TUE, 21, 50))
    assert [e["checks"] for e in checked(app)] == [1, 1, 1, 2]
    # switched off: no check
    app.settings.set("exam_season.alarm_check", False)
    again(w)
    w.go(at(TUE, 21, 55))
    assert len(checked(app)) == 4


# ---------------------------------------------------------------------------------------------- quiz calls
def test_the_quiz_call_only_when_picked(season):
    w = with_calls(season)
    app = w.app
    w.env.on("quiz")
    app.settings.set("quiz.by_call", True)
    app.settings.set("quiz.exam_daily", "18:00")
    d = app.workspace / "linear-algebra"
    d.mkdir(exist_ok=True)
    (d / "exam-prep.md").write_text("# Prep\n## Must know\n- A fact that is worth remembering well.\n")
    app.modules["deadlines"].add("Linear Algebra final exam", at(TUE, 9))
    i = exam_id(app, "Linear Algebra final exam")
    quiz = app.modules["quiz"]
    assert quiz._season_call(i) is False
    w.t = at(TUE - days(5), 18)
    quiz._exam_daily()  # exam mode's check-in: a message, not a call, for a season exam you didn't pick
    assert not [r for r in w.rang if r[0].startswith("quiz:")]
    assert w.texts()[-1].startswith("Exam mode: Linear Algebra final exam")
    assert w.env.press(f"es:{i}:q") == "I'll call you for a quiz at 19:00 the evening before Linear Algebra final exam."
    assert quiz._season_call(i) is True
    w.go(at(TUE - days(1), 18, 50))
    assert not [r for r in w.rang if r[0].startswith("quiz:")]
    w.t = at(TUE - days(1), 19, 2)
    assert quiz._offers() == 0  # the call takes the offer's place
    w.go(at(TUE - days(1), 19, 5))
    w.go(at(TUE - days(1), 19, 20))
    assert [r[0] for r in w.rang if r[0].startswith("quiz:")] == ["quiz:linear-algebra"]  # once
    assert w.env.press(f"es:{i}:q") == "No quiz call before Linear Algebra final exam."
    assert quiz._season_call(i) is False
    app.disable("exam_season")
    assert quiz._season_call(i) is None  # exam season off: Quiz does what it always did


# ------------------------------------------------------------------------------------------- the card
def test_the_card_its_switches_on_telegram_and_the_dashboard(season):
    w, app = season, season.app
    app.modules["deadlines"].add("Linear Algebra final exam", at(TUE, 9))
    out = w.env.say("/examseason")
    assert out.startswith("Exam season. Next: Tue 8 Dec.\n- Linear Algebra final exam: Tue 8 Dec 09:00\nOn: Hold")
    sent = [p for m, p in w.env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    labels = [b["text"] for row in sent["reply_markup"]["inline_keyboard"] for b in row]
    assert labels[0] == "Hold non-critical updates: on" and len(labels) == len(es_mod.PIECES)  # no quiz picks
    assert w.env.press("es:debrief:t") == "Two-minute debrief after each exam: off."
    assert app.settings.get("exam_season.debrief") is False
    assert "\nOff: Two-minute debrief after each exam." in w.env.say("/examseason")
    assert w.env.say("exam season?").startswith("Exam season. Next: Tue 8 Dec.")
    api = Api(app)
    _, st = api.get("state")
    card = next(m for m in st["modules"] if m["id"] == "exam_season")["card"]
    assert card["lines"] == ["Next: Tue 8 Dec.", "Linear Algebra final exam: Tue 8 Dec 09:00"]
    pick = [x for x in card["toggles"] if x["id"].startswith("quiz:")]
    assert [x["id"] for x in card["toggles"][: len(es_mod.PIECES)]] == list(es_mod.PIECES) and pick[0]["disabled"]
    code, r = api.post("modules/card", {"id": "exam_season", "act": "debrief", "value": True})
    assert code == 200 and r["message"] == "Two-minute debrief after each exam: on."
    assert app.settings.get("exam_season.debrief") is True
    assert api.post("modules/card", {"id": "deadlines", "act": "x", "value": True})[0] == 400
    assert next(m for m in api.get("state")[1]["modules"] if m["id"] == "deadlines")["card"] is None
