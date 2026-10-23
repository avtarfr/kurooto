"""Calm by default (core/calm.py): reasons on the main senders, Why?, each Less-of-this action and its Undo, the daily
limit and the evening bundle, the exemptions, the call limit, exam season's tightening, the monthly suggestion, the
plain message for the phone app, and notify.calm.on = false. A fake Telegram and a fake clock."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.core import ask as ask_mod
from kurooto.core import calm as calm_mod
from kurooto.modules import calls as calls_mod
from kurooto.modules import capture as capture_mod
from kurooto.modules import checkins as checkins_mod
from kurooto.modules import deadlines as dl_mod
from kurooto.modules import exam_season as es_mod
from kurooto.modules import quiz as quiz_mod
from kurooto.modules import subjects as subjects_mod
from kurooto.modules.calls import deploy

MON = dt.date(2026, 11, 2)


def at(day: dt.date, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(h, m))


class Clock:
    """The time Calm, the features and the scheduler see."""

    def __init__(self, env, monkeypatch, t: dt.datetime):
        self.env, self.app, self.t = env, env.app, t
        for mod in (calm_mod, ask_mod, dl_mod, capture_mod, checkins_mod, es_mod, quiz_mod, subjects_mod, calls_mod):
            monkeypatch.setattr(mod, "now", lambda: self.t)
        monkeypatch.setattr(self.app.scheduler, "clock", lambda: self.t.timestamp())

    @property
    def calm(self) -> calm_mod.Calm:
        return self.app.calm

    def sent(self) -> list[dict]:
        return [p for m, p in self.env.fake.sent if m == "sendMessage"]

    def last(self) -> dict:
        return self.sent()[-1]

    def labels(self, p: dict | None = None) -> list[str]:
        p = p or self.last()
        return [b["text"] for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]

    def data(self, label: str, p: dict | None = None) -> str:
        p = p or self.last()
        rows = (p.get("reply_markup") or {}).get("inline_keyboard", [])
        return next(b["callback_data"] for row in rows for b in row if b["text"] == label)

    def say(self, text: str, **kw):
        """A message that comes by itself, as a feature sends it."""
        return self.app.notify(text, **kw)


@pytest.fixture
def clock(env, monkeypatch):
    env.app.settings.set("availability.night.enabled", False)
    return Clock(env, monkeypatch, at(MON, 10))


def with_subjects(c: Clock) -> Clock:
    c.env.on("subjects", "capture")
    c.env.say("/subject add Linear Algebra (la)")
    return c


def add(app, title: str, due: dt.datetime) -> str:
    """A deadline on the list; its id."""
    dl = app.modules["deadlines"]
    dl.add(title, due)
    return next(i for i, it in dl.items().items() if it["title"] == title)


def after_class(c: Clock, name: str = "Linear Algebra") -> str:
    c.app.modules["capture"]._ask({"subject": "la", "name": name, "day": c.t.date().isoformat(), "start": "09:00"})
    return c.app.ask.pending(source="capture")[-1]["id"]


# ------------------------------------------------------------------------------------- the envelope
def test_reasons_on_the_main_senders(clock):
    c, app = clock, clock.app
    c.env.on("deadlines", "quiz", "reminders")
    with_subjects(c)
    dl = app.modules["deadlines"]
    i = add(app, "Report on groups", at(MON, 10) + dt.timedelta(hours=30))
    dl._tell(i, dl.items()[i], 30, urgent=False)
    rec = c.calm.last()
    assert (rec["why"], rec["setting"], rec["about"], rec["item"]) == (
        "deadlines.reminder",
        "deadlines.ping_h",
        "Report on groups",
        i,
    )
    assert c.labels() == ["Done", "Not mine", "Snooze 3 h", "Why?", "Less of this"]
    assert rec["ref"] == str(c.env.fake._next_msg)  # Why? answers under it
    # the evening-before offer to practise
    e = {"id": i, "title": "Topology quiz", "due": at(MON, 10).replace(day=3).isoformat(), "subject": ""}
    app.modules["quiz"]._offer(e, "tomorrow")
    assert c.calm.last()["why"] == "quiz.offer" and c.calm.last()["setting"] == "quiz.offer_at"
    # the after-class question goes through questions (core/ask.py) with its reason
    after_class(c)
    rec = c.calm.last()
    assert (rec["why"], rec["about"], rec["item"], rec["map_kind"]) == (
        "capture.after_class",
        "Linear Algebra",
        "la",
        "ask",
    )
    assert c.labels()[-2:] == ["Why?", "Less of this"]
    # a check-in names its own time setting
    c.env.on("checkins")
    app.modules["checkins"]._fallback("evening", MON, "no answer")
    assert c.calm.last()["setting"] == "checkins.times.evening"
    # answers to what you asked carry "asked": no buttons, not counted, not recorded
    n = c.calm.today()["messages"]
    c.say("Here's your answer.", kind="result", why="asked")
    assert "Why?" not in c.labels() and c.calm.today()["messages"] == n and c.calm.last()["why"] != "asked"


def test_every_reason_used_in_the_code_is_known():
    """A reason id at a call site that isn't in the registry would say less than it should on Why?."""
    import pathlib
    import re

    src = pathlib.Path(calm_mod.__file__).parents[1]
    used = set()
    for f in src.rglob("*.py"):
        used |= set(re.findall(r"""why=["']([a-z_]+\.[a-z_]+)["']""", f.read_text(encoding="utf-8")))
    assert used and used <= set(calm_mod.REASONS), used - set(calm_mod.REASONS)


def test_why_says_feature_setting_and_item(clock):
    c, app = clock, clock.app
    c.env.on("deadlines")
    dl = app.modules["deadlines"]
    i = add(app, "Report on groups", at(MON, 10) + dt.timedelta(hours=30))
    dl._tell(i, dl.items()[i], 30, urgent=False)
    rid = c.calm.last()["id"]
    assert c.env.press(f"calm:{rid}:why") == "Why it came: below."
    said = c.last()
    assert said["text"].splitlines()[:3] == [
        "Why: Deadlines, a reminder before something on your deadline list is due.",
        "About: Report on groups.",
        "Setting: deadlines.ping_h = 24 (Settings → Deadlines).",
    ]
    assert "Today: 1 of 6 messages." in said["text"]
    assert said["reply_parameters"]["message_id"] == int(c.calm.get(rid)["ref"]) and c.labels(said) == ["Less of this"]
    assert c.calm.get(rid)["answered"] is None  # Why? isn't an answer


def test_no_reason_recorded_is_said_not_guessed(clock):
    c = clock
    c.say("From an add-on of mine.")
    assert "Why?" not in c.labels()  # nothing to turn down, and no guess
    out = c.env.say("/why")
    assert "No reason recorded for that message" in out and "From an add-on" in out
    assert c.calm.today()["messages"] == 0  # not counted against the limit either


# ------------------------------------------------------------------------------------- Less of this
def test_stop_a_feature_setting_and_undo(clock):
    c, app = clock, clock.app
    c.env.on("quiz")
    c.say("Topology quiz is tomorrow at 10:00. Practise?", kind="question", why="quiz.offer")
    rid = c.calm.last()["id"]
    assert c.env.press(f"calm:{rid}:less") == "Pick one below."
    assert c.last()["text"] == (
        "Less of these: practice offers.\nStop: no more practice offers (/quiz still works)."
    )  # no Another time: they belong to an evening
    assert c.labels() == ["Stop"]
    assert c.env.press(f"calm:{rid}:stop") == "Done: no more practice offers (/quiz still works)."
    assert app.settings.get("quiz.offer_at") == "" and c.labels() == ["Undo"]
    c.env.press(c.data("Undo"))
    assert app.settings.get("quiz.offer_at") == "19:00" and "offer_at" not in app.settings.user().get("quiz", {})
    assert c.last()["text"].startswith("Undone: back to how it was before")


def test_stop_without_a_setting_mutes_that_kind_and_undo(clock):
    c, app = clock, clock.app
    c.say("Exam mode for the Topology quiz.", why="deadlines.exam_mode", about="Topology quiz")
    rid = c.calm.last()["id"]
    c.env.press(f"calm:{rid}:stop")
    assert app.settings.get("notify.calm.stopped") == ["deadlines.exam_mode"]
    n = len(c.sent())
    assert c.say("Exam mode for the Analysis exam.", why="deadlines.exam_mode") is None
    assert len(c.sent()) == n and _all(c)[-1]["state"] == "stopped"
    out = c.env.say("/calm")
    assert "Stopped: exam mode starting for a quiz or exam." in out
    c.env.press(c.data("Start exam mode starting for a quiz or exam again"))
    assert app.settings.get("notify.calm.stopped") == []
    c.say("Exam mode for the Algebra exam.", why="deadlines.exam_mode")
    assert len(c.sent()) == n + 2 and c.last()["text"] == "Exam mode for the Algebra exam."  # /calm, then this


def test_stop_turns_the_feature_off_and_fewer_skips_one_subject(clock):
    c, app = with_subjects(clock), clock.app
    after_class(c)
    rid = c.calm.last()["id"]
    c.env.press(f"calm:{rid}:less")
    assert c.last()["text"].splitlines() == [
        "Less of these: after-class questions.",
        "Stop: turns off After-class notes.",
        "Fewer: none after Linear Algebra.",
        "Another time: they wait for the evening bundle (20:00).",
    ]
    assert c.labels() == ["Stop", "Fewer", "Another time"]
    c.env.press(f"calm:{rid}:fewer")
    assert app.settings.get("capture.skip_subjects") == ["la"]
    c.env.press(c.data("Undo"))
    assert app.settings.get("capture.skip_subjects") == []
    c.env.press(f"calm:{rid}:stop")
    assert not app.is_on("capture")
    c.env.press(c.data("Undo"))
    assert app.is_on("capture")


def test_fewer_and_another_time_hold_for_the_evening(clock):
    c, app = clock, clock.app
    c.say("New in Topology: room change.", why="google.announcement", about="Topology")
    rid = c.calm.last()["id"]
    c.env.press(f"calm:{rid}:fewer")
    assert app.settings.get("notify.calm.fewer") == {"google.announcement": 1}
    assert c.say("New in Algebra: slides up.", why="google.announcement") is None  # one today came already
    assert c.calm.held()[-1]["held"] == "fewer"
    c.say(
        "Due tomorrow: Report.",
        kind="deadline",
        why="deadlines.reminder",
        due=(c.t + dt.timedelta(hours=30)).isoformat(),
    )
    rid = c.calm.last()["id"]
    c.env.press(f"calm:{rid}:later")
    assert app.settings.get("notify.calm.evening") == ["deadlines.reminder"]
    undo = c.data("Undo")
    assert c.say("Due tomorrow: Essay.", kind="deadline", why="deadlines.reminder") is None
    assert c.calm.held()[-1]["held"] == "evening"
    c.env.press(undo)
    assert app.settings.get("notify.calm.evening") is None or app.settings.get("notify.calm.evening") == []
    assert c.say("Due tomorrow: Notes.", kind="deadline", why="deadlines.reminder") is not None


# --------------------------------------------------------------------------- the limit and the bundle
def test_the_daily_limit_holds_the_rest_for_one_evening_bundle(clock):
    c, app = with_subjects(clock), clock.app
    kinds = [
        "research.papers",
        "google.announcement",
        "handwritten.done",
        "books.read",
        "notes_sync.clash",
        "space.cleaned",
    ]
    for k in kinds:
        assert c.say(f"About {k}.", why=k) is not None
    assert c.calm.today()["messages"] == 6
    n = len(c.sent())
    assert c.say("Seventh: new papers.", why="research.papers") is None
    assert len(c.sent()) == n + 1 and c.last()["text"].startswith("That's today's 6 messages")  # said once, at once
    qid = after_class(c)  # a question waits too; it stays open for /q and the next call
    assert len(c.sent()) == n + 1 and app.ask.get(qid)["status"] == "open"
    assert c.calm.today()["waiting"] == 2
    gone = after_class(c, "Topology")  # answered before the evening (/q): it isn't in the bundle
    app.ask.answer(gone, "Nothing new", "telegram")
    c.t = at(MON, 19, 55)
    assert c.calm.tick() == {}
    c.t = at(MON, 20, 2)
    assert c.calm.tick() == {"bundled": 2, "suggested": None}
    b = c.last()
    assert b["text"].startswith("This evening's bundle: 2 messages that waited, held by the daily limit of 6.")
    assert "\n\n1. Seventh: new papers.\n\n2. After class: How was Linear Algebra?" in b["text"]
    assert c.labels(b) == ["2: Nothing new", "2: Later"]
    assert c.calm.tick() == {}  # once a day
    # one question in it: replying to the bundle answers it, and that counts as answered
    c.env.reply_to_last("We did eigenvalues.")
    assert app.ask.get(qid)["status"] == "answered"
    assert [r for r in c.calm.answer_rates() if r["why"] == "capture.after_class"][0]["answered"] == 1
    # after the bundle, messages come as they are
    assert c.say("Late news.", why="research.papers") is not None
    # a new day, a new count
    c.t = at(MON + dt.timedelta(days=1), 9)
    assert c.calm.today()["messages"] == 0 and c.say("Morning news.", why="research.papers") is not None


def test_exempt_kinds_always_come_and_cant_be_stopped(clock):
    c, app = clock, clock.app
    app.settings.set("notify.calm.messages", 0)  # nothing by itself during the day...
    soon = (c.t + dt.timedelta(hours=5)).isoformat()
    later = (c.t + dt.timedelta(hours=30)).isoformat()
    sent = [
        c.say("Reminder: call the bank", kind="reminder", why="reminders.own"),
        c.say("Due in 5 h: Report", kind="deadline", why="deadlines.reminder", due=soon),
        c.say("Tonight's alarm might not ring.", kind="deadline", why="health.alarm"),
        c.say("Time to leave", kind="reminder", why="exam_season.leave", urgent=True),
        c.say("Your AI was signed out.", why="ai.limit", urgent=True),
    ]
    qid = app.ask.approval("Send the reply to Sam?", why="reply_drafts.approval")
    assert all(x is not None for x in sent) and app.ask.get(qid)["msg"] is not None
    assert c.say("Due tomorrow: Essay", kind="deadline", why="deadlines.reminder", due=later) is None  # ...but these
    recs = [r for r in _all(c) if r["state"] == "sent"]
    assert {r["exempt"] for r in recs} == {"own", "deadline", "alarm", "urgent", "approval"}
    for r in recs:
        assert "Less of this" not in json_labels(r)
        text, buttons = c.calm.less_text(r)
        assert buttons is None and ("always come" in text)
        assert c.calm.options(r) == []
    assert c.calm.today()["messages"] == 0  # and they don't use up the day's messages


def _all(c: Clock) -> list[dict]:
    with c.calm._db() as db:
        return [dict(r) for r in db.execute("select * from sent order by ts")]


def json_labels(rec: dict) -> list[str]:
    import json

    return json.loads(rec.get("buttons") or "[]")


# ------------------------------------------------------------------- saying so when the limit starts holding
def test_the_limit_says_so_once_a_day_and_only_for_its_own_holds(clock):
    c, app = clock, clock.app
    app.settings.set("notify.calm.messages", 2)
    for i in range(2):
        assert c.say(f"Papers {i}.", why="research.papers") is not None
    n = len(c.sent())
    assert c.say("Papers 2.", why="research.papers") is None
    told = c.last()
    assert len(c.sent()) == n + 1 and told["text"] == (
        "That's today's 2 messages that came by themselves. The rest wait for the evening bundle at 20:00, "
        "which lists each one."
    )
    assert c.labels(told) == ["Send them as they come today", "Raise to 4", "Fine"]
    rec = c.calm.last()
    assert (rec["why"], rec["exempt"], rec["budgeted"]) == ("calm.limit", "limit", 0)
    assert c.say("Papers 3.", why="research.papers") is None and len(c.sent()) == n + 1  # once a day
    assert c.env.press(c.data("Fine", told)) == "OK, they come at 20:00."
    assert c.calm.today()["waiting_limit"] == 2 and "2 of them held by the daily limit" in c.env.say("/calm")
    # another day: a hold for another reason (Another time, exam season, a quiet week) doesn't bring it
    c.t = at(MON + dt.timedelta(days=1), 10)
    app.settings.set("notify.calm.evening", ["books.read"])
    n = len(c.sent())
    assert c.say("A book was read.", why="books.read") is None and len(c.sent()) == n
    # the bundle says how many waited and why
    c.t = at(MON + dt.timedelta(days=1), 20, 1)
    c.calm.tick()
    assert c.last()["text"].startswith(
        "This evening's bundle: 3 messages that waited (2 held by the daily limit of 2; "
        "1 because you asked for these in the evening). /calm changes the limit."
    )


def test_send_them_as_they_come_today_sends_whats_held_in_order_and_holds_nothing_more(clock):
    c, app = with_subjects(clock), clock.app
    app.settings.set("notify.calm.messages", 1)
    c.say("First.", why="research.papers")
    assert c.say("Second.", why="books.read") is None
    told = c.last()
    qid = after_class(c)  # a question waits too
    assert c.say("Third.", why="space.cleaned") is None
    n = len(c.sent())
    toast = c.env.press(c.data("Send them as they come today", told))
    assert toast == "Today they come as they happen; the 3 that waited are below."
    out = [p["text"] for p in c.sent()[n:]]
    assert out[0] == "Second." and out[1].startswith("After class\n\nHow was Linear Algebra?") and out[2] == "Third."
    assert c.labels(c.sent()[n])[-2:] == ["Why?", "Less of this"]
    assert app.ask.get(qid)["status"] == "open" and c.calm.today()["waiting"] == 0
    assert c.say("Fourth.", why="research.papers") is not None  # nothing more is held today
    assert c.calm.today()["flowing"] and "messages (the limit is off today)" in c.env.say("/calm")
    assert c.env.press(c.data("Send them as they come today", told)).startswith("Today they come")  # again: harmless
    c.t = at(MON + dt.timedelta(days=1), 9)  # the next day the limit holds again
    assert c.say("Fifth.", why="research.papers") is not None and c.say("Sixth.", why="books.read") is None
    assert c.env.press(c.data("Send them as they come today", told)).startswith("That was about an earlier day")


def test_raise_doubles_the_limit_with_undo(clock):
    c, app = clock, clock.app
    app.settings.set("notify.calm.messages", 2)
    for i in range(5):
        c.say(f"Papers {i}.", why="research.papers")
    told = next(p for p in c.sent() if p["text"].startswith("That's today's"))
    n = len(c.sent())
    assert c.env.press(c.data("Raise to 4", told)) == "Done: up to 4 messages a day by themselves (was 2)."
    assert app.settings.get("notify.calm.messages") == 4
    out = [p["text"] for p in c.sent()[n:]]
    assert out[:2] == ["Papers 2.", "Papers 3."]  # up to the new limit, in order
    assert out[2] == "Done: up to 4 messages a day by themselves (was 2). 2 that waited come now."
    assert c.calm.today()["waiting"] == 1 and c.calm.today()["messages"] == 4
    c.env.press(c.data("Undo"))
    assert app.settings.get("notify.calm.messages") == 2


def test_update_notices_dont_count_and_fold_into_one(clock):
    c, app = clock, clock.app
    app.settings.set("notify.calm.messages", 1)
    first = c.say("Kurooto updated to 0.5.15.", kind="update", why="updates.done")
    assert first is not None and c.calm.today()["messages"] == 0
    n = len(c.sent())
    assert c.say("Kurooto updated to 0.5.16.", kind="update", why="updates.done") is None  # folded: nothing new
    assert c.say("Kurooto updated to 0.5.17.", kind="update", why="updates.done") is None
    edits = [p for m, p in c.env.fake.sent if m == "editMessageText"]
    assert len(c.sent()) == n and [e["message_id"] for e in edits] == [first, first]
    assert edits[-1]["text"] == "Kurooto updated to 0.5.17 (and 2 earlier today)."
    assert [b["text"] for row in edits[-1]["reply_markup"]["inline_keyboard"] for b in row] == ["Why?", "Less of this"]
    assert c.calm.today()["messages"] == 0
    assert c.say("New papers.", why="research.papers") is not None  # the day's one is still there
    # where the first can't be changed (no Telegram to edit), the newest comes with the same line
    app.notifier.editors.clear()
    assert c.say("Kurooto updated to 0.5.18.", kind="update", why="updates.done") is not None
    assert c.last()["text"] == "Kurooto updated to 0.5.18 (and 3 earlier today)."
    c.t = at(MON + dt.timedelta(days=1), 9)  # a new day starts afresh
    c.say("Kurooto updated to 0.5.19.", kind="update", why="updates.done")
    assert c.last()["text"] == "Kurooto updated to 0.5.19."


# ------------------------------------------------------------------------------------------- calls
def with_calls(c: Clock) -> Clock:
    app = c.app
    app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(app)
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    c.env.on("calls")
    return c


def test_one_call_a_day_by_itself(clock):
    c, app = with_calls(clock), clock.app
    calm = c.calm
    assert calm.call_ok("weekly.call", key="weekly:review:2026-11-02")
    assert calm.call_ok("weekly.call", key="weekly:review:2026-11-02")  # its repeat isn't a second call
    assert not calm.call_ok("quiz.call", key="quiz:any")
    assert calm.call_ok(None, key="alarm", alarm=True) and calm.call_ok("calls.own", key="x")
    assert calm.call_ok("deadlines.call", key="deadlines:1", due=(c.t + dt.timedelta(hours=6)).isoformat())
    assert calm.today()["calls"] == 1
    # a call past the limit doesn't ring: it waits in the bundle with a link to call
    calls = app.modules["calls"]
    assert calls.ring("Quiz call, about 10 minutes.", key="quiz:any", why="quiz.call") == ""
    item = calm.held()[-1]
    assert item["text"] == "A call that waited (1 a day comes by itself): Quiz call, about 10 minutes."
    c.t = at(MON, 20, 1)
    calm.tick()
    assert c.labels()[-1] == "1: Call now"  # the bundle: the call is its only item
    url = c.last()["reply_markup"]["inline_keyboard"][-1][-1]["url"]
    assert url.startswith("https://kurooto-abc.your-subdomain.workers.dev/")


def test_a_check_in_call_past_the_limit_comes_as_a_message(clock):
    c, app = with_calls(clock), clock.app
    c.env.on("checkins")
    assert c.calm.call_ok("weekly.call", key="weekly:review:x")  # the day's call
    ch = app.modules["checkins"]
    ch._call("evening", MON)
    assert c.last()["text"].startswith("Evening check-in (today's call came already):")
    assert ch.today(MON)["evening"]["status"] == "asked"
    assert not [x for x in c.calm.held() if x["why"] == "checkins.call"]  # the message took its place
    # "Call me now" on that message rings anyway: you asked
    assert c.calm.call_ok("calls.own", key="checkins:evening:2026-11-02")


# ------------------------------------------------------------------------------------ exam season
def test_exam_season_tightens_the_day_to_deadlines_quizzes_and_the_alarm(clock):
    c, app = clock, clock.app
    c.env.on("subjects", "deadlines", "exam_season")
    app.settings.set("subjects.exam_periods", [["2026-11-04", "2026-11-06"]])
    app.modules["deadlines"].add("Linear Algebra final exam", at(dt.date(2026, 11, 5), 9))
    c.t = at(dt.date(2026, 11, 4), 10)
    assert app.modules["exam_season"].budget_during_exams() is not None
    assert c.say("New papers.", why="research.papers") is None  # held, though nothing came today yet
    assert c.calm.held()[-1]["held"] == "exams"
    assert c.say("Topology quiz tomorrow. Practise?", kind="question", why="quiz.offer") is not None
    later = (c.t + dt.timedelta(hours=30)).isoformat()
    assert c.say("Due tomorrow: Report", kind="deadline", why="deadlines.reminder", due=later) is not None
    assert not c.calm.call_ok("checkins.call", key="checkins:evening:x") and c.calm.call_ok("quiz.call", key="quiz:la")
    assert "Exam season: during the day only deadlines, quizzes and the alarm come." in c.env.say("/calm")
    c.t = at(dt.date(2026, 11, 4), 20, 5)
    assert c.calm.tick()["bundled"] == 1
    assert "because of exam season (during the day only deadlines, quizzes and the alarm come)" in c.last()["text"]
    assert c.say("More papers.", why="research.papers") is None  # after the bundle too: until the next one
    # the part has its own switch on the card
    assert "budget" in es_mod.PIECES
    app.modules["exam_season"].card_action("budget", False)
    assert c.say("Even more papers.", why="research.papers") is not None
    c.t = at(dt.date(2026, 11, 8), 10)  # after the season
    app.modules["exam_season"].card_action("budget", True)
    assert c.calm.exam_keep() is None


# ----------------------------------------------------------------------------- the monthly suggestion
def test_the_monthly_suggestion_from_the_same_records(clock):
    c, app = with_subjects(clock), clock.app
    first = None
    for d in range(19):
        c.t = at(MON + dt.timedelta(days=d), 11)
        qid = after_class(c)
        if first is None:
            first = qid
            app.ask.answer(first, "Nothing new", "telegram")
    c.t = at(MON + dt.timedelta(days=29), 20, 1)
    out = c.calm.tick()
    assert out["suggested"] == "capture.after_class"
    s = c.last()
    assert s["text"] == (
        "Calm\n\nIn the last 30 days you answered 1 of 19 after-class questions. Turn them off? (Turns off "
        "After-class notes; Undo puts it back.)"
    )
    assert c.labels(s)[:2] == ["Apply", "No"]
    c.env.press("calm:capture.after_class:apply")
    assert not app.is_on("capture")
    c.env.press(c.data("Undo"))
    assert app.is_on("capture")
    c.t = at(MON + dt.timedelta(days=30), 20, 1)
    assert c.calm.tick()["suggested"] is None  # once a month
    c.env.press("calm:capture.after_class:no")
    c.t = at(MON + dt.timedelta(days=61), 20, 1)
    assert c.calm.monthly() is None  # "No" keeps it out for 90 days


def test_no_suggestion_without_a_month_of_records_or_for_plain_messages(clock):
    c = with_subjects(clock)
    for d in range(10):
        c.t = at(MON + dt.timedelta(days=d), 11)
        after_class(c)
        c.say("Due tomorrow: Report", kind="deadline", why="deadlines.reminder", buttons=[[("Done", f"dl:{d}:done")]])
    c.t = at(MON + dt.timedelta(days=10), 20, 1)
    assert c.calm.monthly() is None  # not a month yet
    c.t = at(MON + dt.timedelta(days=29), 20, 1)
    rates = {r["why"]: r for r in c.calm.answer_rates()}
    assert rates["deadlines.reminder"]["answered"] == 0  # never tapped, but they're not questions
    assert c.calm.monthly() == "capture.after_class"
    c.env.press(f"dl:{3}:done")  # a tap counts as answered
    assert {r["why"]: r for r in c.calm.answer_rates()}["deadlines.reminder"]["answered"] == 1


# ------------------------------------------------------------------------------- fallback and off
def test_the_phone_app_and_the_desktop_get_the_plain_message(clock):
    c, app = with_subjects(clock), clock.app
    got = []
    app.notifier.register("app", lambda m: got.append(m))
    app.settings.set("notify.app_kinds", ["question", "info"])
    c.say("New papers.", why="research.papers")
    assert c.labels()[-2:] == ["Why?", "Less of this"]
    assert got[-1].text == "New papers." and got[-1].buttons is None
    app.settings.set("notify.calm.messages", 1)
    after_class(c)  # held: the app doesn't get it now (only the line saying the limit was reached)...
    assert got[-2].text == "New papers." and got[-1].text.startswith("That's today's 1 message that came by itself.")
    c.t = at(MON, 20, 1)
    c.calm.tick()
    assert got[-2].text.startswith("This evening's bundle")  # ...but on its own at the bundle, with its own buttons
    assert got[-1].kind == "question" and got[-1].text.startswith("How was Linear Algebra?")
    assert [b[0] for row in got[-1].buttons for b in row] == ["Nothing new", "Later"]


def test_off_restores_the_old_behaviour_exactly(clock):
    c, app = with_subjects(clock), clock.app
    assert c.env.say("/calm off").startswith("Calm is off")
    for i in range(9):
        assert c.say(f"Message {i}", why="research.papers") is not None
        assert "Why?" not in c.labels()
    after_class(c)
    assert "Why?" not in c.labels() and c.labels() == ["Nothing new", "Later"]
    assert not c.calm.db_file.exists() or _all(c) == []
    assert c.calm.call_ok("quiz.call", key="a") and c.calm.call_ok("quiz.call", key="b")
    assert c.env.say("/why").startswith("Calm is off")
    c.env.say("/calm on")
    c.env.say("/calm 8")
    c.env.say("/calm calls 2")
    c.env.say("/calm evening 21:30")
    got = {k: app.settings.get(f"notify.calm.{k}") for k in ("on", "messages", "calls", "evening_at")}
    assert got == {"on": True, "messages": 8, "calls": 2, "evening_at": "21:30"}
    assert "0 of 8 messages and 0 of 2 calls" in c.env.say("/calm")


def test_focus_still_holds_and_the_buttons_survive_it(clock):
    c, app = clock, clock.app
    app.availability.set_focus(c.t + dt.timedelta(hours=1))
    n = len(c.sent())
    assert c.say("New papers.", why="research.papers") is None
    assert len(c.sent()) == n and c.calm.today()["messages"] == 1  # counted when it was let through
    app.availability.set_focus(None)
    assert app.notifier.flush_queue() == 1
    assert c.labels()[-2:] == ["Why?", "Less of this"] and c.calm.last()["ref"] is not None
