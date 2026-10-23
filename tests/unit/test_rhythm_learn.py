"""Your rhythm (core/rhythm.py): quiet hours learned from when you're around (the night hours and the morning follow,
with Undo; never ones you set), the alarm's suggestion, lighter days after an exam or a heavy day, and one gentle
message after days of silence."""

import datetime as dt
import json

from kurooto.core import rhythm as rhythm_mod
from kurooto.modules import alarm as alarm_mod

TODAY = dt.datetime.combine(dt.date.today(), dt.time(0))


def _events(app, rows):
    with open(app.events.file, "a", encoding="utf-8") as f:
        f.writelines(json.dumps({"ts": t.isoformat(), "kind": k}) + "\n" for t, k in rows)


def _nights(app, days, hours=(16.17, 19, 22, 25, 28, 31.83)):
    """`days` days back (from the day before yesterday), you around at these hours (past 24: the next morning): up
    at 16:10, last at 07:50."""
    rows = []
    for k in range(2, days + 2):
        rows += [(TODAY - dt.timedelta(days=k) + dt.timedelta(hours=h), "message_in") for h in hours]
    _events(app, rows)


def test_quiet_hours_move_to_a_night_that_runs_into_the_afternoon_and_undo_puts_them_back(env):
    app = env.app
    _nights(app, 10)
    assert app.rhythm.usual() == {"from": "08:00", "to": "16:00", "nights": 9}
    line = app.rhythm.learn()
    assert line.startswith(
        "Quiet hours at night (no calls) now run from 08:00 to 16:00, not 23:30 to 07:00: that's when you've been "
        "quiet on 9 of the last 21 days. Mornings move with it: the check-in day turns at 14:00"
    )
    assert app.settings.get("availability.night")["from"] == "08:00"
    assert app.settings.get("availability.night")["to"] == "16:00"
    assert app.settings.get("checkins.day_starts") == "14:00"
    assert app.settings.get("dreaming.when") == "daily 16:30"
    assert app.settings.get("startby.when") == "daily 17:00"
    assert app.availability.night(TODAY + dt.timedelta(hours=12))  # noon: quiet
    assert not app.availability.night(TODAY + dt.timedelta(hours=23, minutes=45))  # around
    assert app.rhythm.learn() == ""  # not again within a week
    assert env.press("rhy:night:undo").startswith("Back as it was")
    assert app.settings.get("availability.night")["from"] == "23:30"
    assert app.settings.get("dreaming.when") == "daily 07:30"
    assert "when" not in (app.settings.user().get("dreaming") or {})  # back to the default, not a copy of it


def test_too_few_nights_or_night_hours_you_set_stay(env):
    app = env.app
    _nights(app, 5)
    assert app.rhythm.learn() == ""  # 5 nights: too few
    _nights(app, 10)
    app.settings.set("availability.night.from", "01:00")  # yours
    line = app.rhythm.learn()
    assert line.startswith("You're usually around from 16:00, so: the check-in day turns at 14:00")
    assert app.settings.get("availability.night")["from"] == "01:00"
    assert app.settings.get("availability.night")["to"] == "07:00"


def test_the_alarm_suggests_your_usual_time_once_and_never_sets_it(env, monkeypatch):
    app = env.app
    al = app.modules["alarm"]
    app.rhythm._put(usual={"from": "08:00", "to": "16:00", "nights": 10})
    monkeypatch.setattr(alarm_mod, "now", lambda: TODAY + dt.timedelta(hours=6))  # two hours before bedtime
    assert al.suggest() == ""
    monkeypatch.setattr(alarm_mod, "now", lambda: TODAY + dt.timedelta(hours=7, minutes=20))
    assert al.suggest() == "You usually wake around 16:00; set an alarm?"
    assert al.upcoming() == []  # not set by itself
    assert al.suggest() == ""  # once a day
    app.settings.set("alarm.suggest", False)
    monkeypatch.setattr(alarm_mod, "now", lambda: TODAY + dt.timedelta(days=1, hours=7, minutes=20))
    assert al.suggest() == ""


def test_a_lighter_day_after_an_exam_and_not_today(env):
    app = env.app
    env.on("deadlines")
    exam = {"title": "Linear Algebra midsem", "kind": "exam", "status": "open", "source": "manual"}
    exam["due"] = (TODAY - dt.timedelta(hours=14)).isoformat()  # yesterday 10:00
    (app.paths.state / "deadlines.json").write_text(json.dumps({"d1": exam}))
    assert app.rhythm.lighter() == {"why": "exam", "what": "Linear Algebra midsem"}
    assert app.calm.day_limit() == 3  # half of 6
    env.on("checkins")
    ck = app.modules["checkins"]
    assert ck.today()["evening"] == {"time": "23:00", "status": "planned", "lighter": "22:00"}
    env.on("dreaming")
    text = app.modules["dreaming"].report(send=True)
    assert text.startswith(
        "A lighter day after your exam (Linear Algebra midsem): fewer messages from me and the first check-in an hour "
        "later."
    )
    assert app.rhythm.lighter_line(mark=True) == ""  # told once
    assert env.press("rhy:lighter:no") == "OK, a usual day."
    assert app.calm.day_limit() == 6
    assert ck.today()["evening"] == {"time": "22:00", "status": "planned"}


def test_a_heavy_study_day_makes_the_next_lighter_and_the_setting_turns_it_off(env):
    app = env.app
    yday = (TODAY - dt.timedelta(days=1)).date()
    (app.paths.state / "study").mkdir(parents=True, exist_ok=True)
    (app.paths.state / "study" / f"{yday.isoformat()}.json").write_text(json.dumps({"la": 5 * 3600, "prob": 4 * 3600}))
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "subjects", "study"])
    assert app.rhythm.lighter() == {"why": "heavy", "what": "9 hours of study"}
    assert app.rhythm.tell_lighter().startswith("A lighter day after yesterday's 9 hours of study")
    app.settings.set("notify.calm.lighter_after", False)
    assert app.rhythm.lighter() is None and app.calm.day_limit() == 6


def test_two_quiet_days_bring_one_gentle_message_and_busy_holds_a_week(env, monkeypatch):
    app = env.app
    noon = TODAY + dt.timedelta(hours=12)
    monkeypatch.setattr(rhythm_mod, "now", lambda: noon)
    _events(app, [(noon - dt.timedelta(days=1), "message_in")])
    assert app.rhythm.absence() == ""  # a day: nothing yet
    app.events.file.write_text(json.dumps({"ts": (noon - dt.timedelta(days=3)).isoformat(), "kind": "message_in"}))
    monkeypatch.setattr(rhythm_mod, "now", lambda: noon.replace(hour=3))  # the night: it waits
    assert app.rhythm.absence() == ""
    monkeypatch.setattr(rhythm_mod, "now", lambda: noon)
    assert app.rhythm.absence() == "Haven't heard from you in two days. All good? Nothing's urgent."
    assert app.rhythm.absence() == ""  # never again for this silence
    assert app.rhythm.button("absence", "busy") == "Quiet for a week."
    assert app.availability.quiet_until(noon) == noon + dt.timedelta(days=7)
    assert app.calm._wait("weekly.summary", "weekly", noon) == "quiet"
    assert app.rhythm.button("quiet", "undo") == "Back to usual."
    assert app.availability.quiet_until(noon) is None


def test_absence_is_off_at_zero_and_a_tap_counts_as_being_around(env, monkeypatch):
    app = env.app
    noon = TODAY + dt.timedelta(hours=12)
    monkeypatch.setattr(rhythm_mod, "now", lambda: noon)
    _events(app, [(noon - dt.timedelta(days=3), "message_in")])
    app.settings.set("availability.absence_days", 0)
    assert app.rhythm.absence() == ""
    app.settings.set("availability.absence_days", 2)
    app.callback("zz:x:y")  # any button you tap
    assert app.rhythm.last_seen() > noon - dt.timedelta(days=1)
