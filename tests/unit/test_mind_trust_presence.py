"""Brain, 0.8.16: the trust ladder on real actions (mind.act.more: study blocks, reshaped plans, revision packs and
keeping the night's cards and lines ask below the bar, act and tell with Undo above it), presence prediction as a
reward (mind.presence_forecast: forecast, scored for accuracy, preferred by check-ins and calls), the nightly voice
learner through the body gate, and the register cutting ready-made unprompted messages (mind.register.templates)."""

import datetime as dt
import time

import pytest

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.notify import Message
from kurooto.mind import act, dream, presence_forecast, presence_reward, register, study_push
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.senses import intero


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "quiz", "subjects", "deadlines", "reminders", "checkins"])
    a.settings.set("availability.night.enabled", False)
    a.settings.set("mind.sleep.on", False)
    a.settings.set("subjects.list", [{"slug": "measure-theory", "name": "Measure Theory", "aliases": ["mt"]}])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)) or "m1")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def pump(app, klass, n, kind="ok"):
    for i in range(n):
        app.keeper.append("trust_evidence", {"class": klass, "evidence": kind, "seen": True}, time.time() + i)


def trust_n(app, klass, kind="ok"):
    row = next((r for r in mind.connect(app).trust_rows() if r["key"] == klass), None)
    return int((((row or {}).get("meta") or {}).get("n") or {}).get(kind, 0))


def undo_ref(buttons) -> str:
    return next(b[1] for row in buttons for b in row if str(b[1]).startswith("aut:")).split(":")[1]


# ------------------------------------------------------------------------------------------------- the ladder
def test_below_the_bar_it_asks_above_it_acts_and_tells(app, monkeypatch):
    undone = []
    monkeypatch.setitem(act.UNDOERS, "study.block", lambda a, p: undone.append(p) or "Taken back.")
    assert act.trusted(app, "study.block") is False  # R1's prior is under its bar: it asks, as before
    assert act.attempt(app, "study.block", lambda _: {"x": 1}) is None
    pump(app, "R1", 40)
    did = act.attempt(app, "study.block", lambda _: {"x": 1}, summary="a block", undo_from=lambda o: {"p": 1})
    assert did["out"] == {"x": 1} and did["buttons"] == [[("Undo", f"aut:{did['id']}:undo")]]
    assert act._state(app)["kinds"]["study.block"] == {"done": 1, "asked": 2}
    assert act.digest_lines(app) == ["a block"]  # in the Sunday digest too
    assert act.button(app, did["id"], "undo") == "Taken back." and undone == [{"p": 1}]
    assert act.trusted(app, "study.block") is False  # an undo costs trust and pauses the class
    assert act.attempt(app, "deadline.reshape", lambda _: 1) is None  # R2 is a different class: not earned


def test_the_knobs_a_low_mood_and_the_switch_make_it_ask(app, monkeypatch):
    pump(app, "R1", 40)
    assert act.trusted(app, "dream.keep_card")
    from kurooto.mind import feelings, status

    monkeypatch.setattr(status, "knobs", lambda a: {"ask": True})
    assert not act.trusted(app, "dream.keep_card")  # its beliefs are no better than a guess: ask first
    monkeypatch.setattr(status, "knobs", lambda a: {"ask": False})
    monkeypatch.setattr(feelings, "mood_band", lambda a: "low")
    assert not act.trusted(app, "dream.keep_card")
    monkeypatch.setattr(feelings, "mood_band", lambda a: "mid")
    app.settings.set("mind.act.more", False)
    assert not act.trusted(app, "dream.keep_card") and act.kinds_lines(app) == []
    app.settings.set("mind.act.more", True)
    lines = "\n".join(act.kinds_lines(app))
    for label in act.KINDS.values():
        assert label in lines
    assert "R1, trust" in lines and "acts and tells" in lines and "asks first" in lines  # R2 kinds still ask
    assert "keeping a quiz card" in act.status(app)[0]  # /autonomy lists them too


def test_a_yes_to_its_question_is_an_ok_a_no_is_nothing(app):
    act.answered(app, "deadline.reshape", True)
    act.answered(app, "deadline.reshape", False)
    assert trust_n(app, "R2") == 1 and trust_n(app, "R2", "complaint") == 0
    app.settings.set("mind.act.more", False)
    act.answered(app, "deadline.reshape", True)
    assert trust_n(app, "R2") == 1


def test_never_for_an_always_ask_action(app):
    for k in ("R0", "R1", "R2", "R3"):
        pump(app, k, 300)
    assert act.attempt(app, "alarm.set", lambda _: 1) is None
    assert act.attempt(app, "never.heard.of.it", lambda _: 1) is None


# ------------------------------------------------------------------------------------------------- its call sites
def _deadline(app, title, hours, **kw):
    dl = app.modules["deadlines"]
    dl.add(title, now() + dt.timedelta(hours=hours), **kw)
    return next(i for i, it in dl.items().items() if it["title"] == title)


def test_the_morning_study_block_set_by_itself_with_undo(app, monkeypatch):
    _deadline(app, "Measure Theory problem set", 60, subject="measure-theory")
    monkeypatch.setattr(act, "trusted", lambda a, action: action == "study.block")
    text = study_push.push(app)
    assert text.startswith("Uneasy about Measure Theory") and "I've set it: I'll remind you at " in text
    msg, kw = app.sent[-1]
    assert kw["kind"] == "info" and "Yes" not in str(kw["buttons"])
    key = f"reminders:msp{now().date().isoformat().replace('-', '')}"
    assert app.scheduler.get(key) is not None
    assert act.button(app, undo_ref(kw["buttons"]), "undo") == "Taken back: no study reminder."
    assert app.scheduler.get(key) is None
    assert study_push.button(app, now().date().isoformat(), "yes") == "Already answered."


def test_the_morning_line_still_asks_below_the_bar_and_yes_builds_trust(app):
    _deadline(app, "Measure Theory problem set", 60, subject="measure-theory")
    study_push.push(app)
    assert [b[0] for b in app.sent[-1][1]["buttons"][0]] == ["Yes", "Later"]
    assert study_push.button(app, now().date().isoformat(), "yes").startswith("Done: I'll remind you at ")
    assert trust_n(app, "R1") == 1


def test_dream_cards_kept_by_itself_once_trusted(app, monkeypatch):
    st = dream._load(app)
    card = {"ref": "r1", "slug": "measure-theory/fubini", "title": "Fubini theorem", "q": "What is Fubini?", "a": "x"}
    st["cards"].append({**card, "subject": "measure-theory", "made": now().date().isoformat(), "shown": 0})
    st["lessons"].append({"ref": "l1", "h": "h1", "line": "Fewer nudges in the evening", "why": "3 ignored",
                          "day": now().date().isoformat(), "shown": 0})  # fmt: skip
    dream._save(app, st)
    monkeypatch.setattr(act, "trusted", lambda a, action: action == "dream.keep_card")  # cards (R1), not lessons (R2)
    text, buttons = dream.section(app, send=True)
    assert "Kept by itself" in text and "What is Fubini?" in text
    assert "Fewer nudges in the evening" in text and "mdr:ll1:keep" in str(buttons)  # the lesson still asks
    quiz = app.modules["quiz"]
    assert quiz.load("measure-theory")["items"]
    assert act.button(app, undo_ref(buttons), "undo") == "Taken out of your quiz cards."
    assert not quiz.load("measure-theory")["items"]


def test_a_keep_tap_is_an_ok_for_its_kind(app):
    st = dream._load(app)
    st["lessons"].append({"ref": "l1", "h": "h1", "line": "Fewer nudges in the evening", "why": "3 ignored",
                          "day": now().date().isoformat(), "shown": 0})  # fmt: skip
    dream._save(app, st)
    assert dream.button(app, "ll1", "keep").startswith("Added to your how-to-help-me note")
    assert trust_n(app, "R2") == 1


def test_a_reshaped_plan_moved_by_itself_with_undo(env, monkeypatch):
    from kurooto.modules import deadlines as dl_mod
    from kurooto.modules import startby as sb_mod
    from tests.unit.test_negotiate import at

    for mod in (sb_mod, dl_mod):
        monkeypatch.setattr(mod, "now", lambda: at(2, 19))
    a = env.app
    a.settings.set("availability.night.enabled", False)
    a.settings.set("startby.window", "09:00-21:00")
    a.settings.set("startby.share", 50)
    a.settings.set("startby.sizes", {"problem_set": 3, "report": 12, "quiz": 3, "exam": 10, "other": 2})
    env.on("deadlines", "startby")
    dl = a.modules["deadlines"]
    dl.add("Problem set 4", at(3, 11))
    i = next(iter(dl.items()))
    monkeypatch.setattr(act, "trusted", lambda app, action: action == "deadline.reshape")
    assert a.modules["startby"].offer_reshape(i, again=True) is True
    assert env.fake.texts()[-1].endswith("I've moved it: 1 h now, 1 h tomorrow from 09:00. I'll remind you then.")
    assert a.scheduler.get(f"startby:moved:{i}") is not None
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    ref = sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert ref.startswith("aut:") and env.press(ref).startswith("Taken back: the plan is as it was")
    assert a.scheduler.get(f"startby:moved:{i}") is None
    assert env.press(f"neg:{i}:yes") == "Already answered."


def test_a_revision_pack_started_by_itself_with_undo(app, monkeypatch):
    sk_mod = app.modules["skills"]
    started, cancelled = [], []
    monkeypatch.setattr(sk_mod, "pack_for", lambda text, **kw: started.append((text, kw)) or "j1")
    monkeypatch.setattr(app.jobs, "cancel", lambda jid: cancelled.append(jid) or object())
    assert sk_mod._pack_auto("e1", "mt: midsem") is None and not started  # not trusted yet: it asks
    monkeypatch.setattr(act, "trusted", lambda a, action: action == "job.revision_pack")
    did = sk_mod._pack_auto("e1", "mt: midsem")
    assert did["out"] == "j1" and started[-1][1]["lane"] == "bg"
    assert sk_mod._auto_pack_button("e1", "yes") == "It's on its way already."
    assert act.button(app, undo_ref(did["buttons"]), "undo") == "Stopped: no revision pack." and cancelled == ["j1"]


# ------------------------------------------------------------------------------------------------- presence
class Clock:
    def __init__(self, t):
        self.t = t


@pytest.fixture
def clock(monkeypatch):
    c = Clock(dt.datetime(2026, 11, 2, 8, 0))
    monkeypatch.setattr(presence_forecast, "now", lambda: c.t)
    return c


def test_the_forecast_knows_classes_and_starts_with_no_opinion(app):
    t = dt.datetime(2026, 11, 2, 10, 0)
    assert presence_forecast.p_free(app, t) == 0.5
    app.availability.blockers["subjects:class"] = lambda x: ("a class", x) if 10 <= x.hour < 11 else None
    assert presence_forecast.p_free(app, t) == presence_forecast.BLOCKED_P
    assert presence_forecast.blocked(app, t) == "class" and presence_forecast.blocked(app, t.replace(hour=12)) is None


def test_hours_are_looked_at_checked_and_paid_for_accuracy(app, clock, monkeypatch):
    seen = {"free": True}
    monkeypatch.setattr(presence_forecast, "sensing", lambda a: True)
    monkeypatch.setattr(presence_forecast, "free_now", lambda a, t=None: seen["free"])
    assert presence_forecast.tick(app) == []  # 08:00: a look, the next six hours frozen
    st = presence_forecast._load(app)
    assert set(st["frozen"]) == {f"2026-11-02T{h:02d}" for h in range(9, 15)}
    for m in (0, 15, 30, 45):  # 09:xx, at the desk and free
        clock.t = dt.datetime(2026, 11, 2, 9, m)
        presence_forecast.tick(app)
    clock.t = dt.datetime(2026, 11, 2, 10, 0)
    checks = presence_forecast.tick(app)
    assert checks == [(0.5, 1.0, 0.5)]  # no opinion, all free, nothing yesterday
    assert presence_forecast.accuracy(app) == {"n": 1, "brier": 0.25, "base": 0.25}
    recs = [r for r in mlog.MindLog(app.paths.state / "mind" / "log.db").read() if r.kind == "presence_reward"]
    assert recs and recs[-1].body["r"] == 0.0  # no better than "same as yesterday": nothing paid
    st = presence_forecast._load(app)
    assert st["cells"]["0-9"] == [1.0, 1] and presence_forecast.p_free(app, dt.datetime(2026, 11, 9, 9)) > 0.5
    assert "Presence forecast: Brier 0.250 over 1 hour" in presence_forecast.line(app)
    app.settings.set("mind.presence_forecast.on", False)
    assert presence_forecast.tick(app) == [] and presence_forecast.line(app) == ""


def test_nothing_is_scored_without_a_sense_that_sees_the_desk(app, clock):
    for h in (8, 9, 10, 11):
        clock.t = dt.datetime(2026, 11, 2, h, 0)
        assert presence_forecast.tick(app) == []
    assert presence_forecast.accuracy(app)["n"] == 0
    assert "needs the activity sense or Face presence" in presence_forecast.line(app)


def test_the_presence_reward_is_accuracy_bounded_a_day():
    st: dict = {}
    t = time.mktime((2026, 11, 2, 12, 0, 0, 0, 0, -1))
    assert presence_reward.pay(st, t, 0.5, 1.0, 0.5) == (0.0, "even")  # no better than the baseline
    r, _ = presence_reward.pay(st, t, 1.0, 1.0, 0.0)
    assert r == pytest.approx(presence_reward.GAIN)
    for _ in range(50):
        presence_reward.pay(st, t, 1.0, 1.0, 0.0)
    assert st["sum"] == pytest.approx(presence_reward.W)  # a perfect day pays at most W
    assert presence_reward.pay(st, t, 2.0, 1.0, 0.0) == (0.0, "bad")
    st2: dict = {}
    r, _ = presence_reward.pay(st2, t, 0.0, 1.0, 1.0)
    assert r == pytest.approx(-presence_reward.GAIN)  # worse than "same as yesterday" costs a little
    nxt = t + 86400
    assert presence_reward.pay(st, nxt, 1.0, 1.0, 0.0)[0] > 0  # a new day


def test_the_scorekeeper_pays_presence_into_the_mood_within_the_bound(app):
    for _ in range(30):
        assert app.keeper.append("presence_check", {"p": 1.0, "y": 1.0, "base": 0.0})["ok"]
    row = next(r for r in mind.connect(app).vars_rows("presence"))
    assert row["value"] == pytest.approx(presence_reward.W) and row["meta"]["n"] == 30
    assert next(r for r in mind.connect(app).vars_rows("M"))["value"] > 0
    assert mlog.accepted_fact("presence_check")


def test_prefer_moves_out_of_a_class_only_when_clearly_better(app):
    t = dt.datetime(2026, 11, 2, 10, 0)
    assert presence_forecast.prefer(app, t) == t  # no opinion anywhere: left alone
    app.availability.blockers["subjects:class"] = lambda x: ("a class", x) if 10 <= x.hour < 11 else None
    assert presence_forecast.prefer(app, t) == dt.datetime(2026, 11, 2, 9, 45)  # the nearest likelier time
    assert presence_forecast.prefer(app, t, earliest=t) == dt.datetime(2026, 11, 2, 11, 0)
    assert presence_forecast.prefer(app, t, within_min=0) == t
    app.settings.set("mind.presence_forecast.prefer", False)
    assert presence_forecast.prefer(app, t) == t


def test_a_checkin_planned_in_a_class_moves_but_the_night_one_keeps_bedtime(app, monkeypatch):
    from kurooto.modules import checkins as ck_mod

    ck = app.modules["checkins"]
    day = dt.date(2026, 11, 2)
    monkeypatch.setattr(ck_mod, "now", lambda: dt.datetime(2026, 11, 2, 8, 0))
    app.availability.blockers["subjects:class"] = lambda x: ("a class", x) if 13 <= x.hour < 14 else None
    plan = {"midday": {"time": "13:00", "status": "planned"}, "evening": {"time": "22:00", "status": "planned"}}
    ck._presence(plan, ["midday", "evening"], day)
    assert plan["midday"] == {"time": "12:45", "status": "planned", "presence": "13:00"}
    assert plan["evening"]["time"] == "22:00"
    app.settings.set("availability.night.enabled", True)
    app.settings.set("availability.night.from", "23:00")
    app.settings.set("availability.night.to", "07:00")
    night = {"night": {"time": "23:15", "status": "planned"}}
    ck._presence(night, ["night"], day)
    assert night["night"]["time"] == "23:15"  # meant for bedtime: its sleep isn't held against it


def test_a_call_it_places_waits_for_a_likelier_time(app, monkeypatch):
    calls = app.modules["calls"]
    from kurooto.modules import calls as calls_mod

    t0 = dt.datetime(2026, 11, 2, 10, 0)
    monkeypatch.setattr(calls_mod, "now", lambda: t0)
    app.availability.blockers["subjects:class"] = lambda x: ("a class", x) if 10 <= x.hour < 11 else None
    monkeypatch.setattr(presence_forecast, "free_now", lambda a, t=None: None)
    assert calls._presence_later("weekly.call", None) == dt.datetime(2026, 11, 2, 11, 0)
    assert calls._presence_later("calls.own", None) is None  # one you asked for rings
    assert calls._presence_later(None, None) is None
    assert calls._presence_later("deadlines.call", (t0 + dt.timedelta(hours=3)).isoformat()) is None  # close
    monkeypatch.setattr(presence_forecast, "free_now", lambda a, t=None: True)
    assert calls._presence_later("weekly.call", None) is None  # seen at the desk: it rings now


# ------------------------------------------------------------------------------------------------- small gaps
def test_the_nightly_voice_learner_waits_for_the_body(app, monkeypatch):
    from kurooto.modules.voice import _gated

    ran = []
    monkeypatch.setattr(intero, "ok", lambda a, cost="gpu", action="": (False, "your GPU work"))
    assert _gated(app, lambda: ran.append(1) or "done") is None and not ran  # deferred for retry()
    assert "voice:learn" in (intero.jload(app.paths.state / intero.FILE, {}) or {}).get("pending", {})
    monkeypatch.setattr(intero, "ok", lambda a, cost="gpu", action="": (True, ""))
    assert _gated(app, lambda: ran.append(1) or "done") == "done" and ran == [1]
    app.settings.set("modules.enabled", [])  # Brain off: it runs as in 0.8.13
    assert _gated(app, lambda: ran.append(2) or "done") == "done" and ran == [1, 2]


LONG = "First line here. Second one. Third thing to say. A fourth sentence. And a fifth."


def test_the_register_cuts_ready_made_unprompted_messages(app, monkeypatch):
    monkeypatch.setattr(register, "sentences", lambda a, snap=None: 2)
    n = app.notifier
    out = n.temperament(Message(LONG, why="research.watch"))
    assert out.text == "First line here. Second one."
    asks = n.temperament(Message(LONG + " Want it now?", why="research.watch", buttons=[[("Yes", "x:1:y")]]))
    assert asks.text == "First line here. Second one. Want it now?"  # the sentence its buttons answer stays
    for msg in (
        Message(LONG, why="asked"),  # an answer to you
        Message(LONG, why="research.watch", reply_to=5),
        Message(LONG, why="reminders.own"),  # exempt: your own reminder
        Message(LONG, why="research.watch", kind="approval"),
        Message(LONG, why="research.watch", urgent=True),
        Message("Today:\n- one. two. three.\n- four", why="research.watch"),  # a list
        Message("Part one. Two. Three.\n\nPart two. Five.", why="research.watch"),  # a digest
    ):
        assert n.temperament(msg).text == msg.text, msg
    app.settings.set("mind.register.templates", False)
    assert n.temperament(Message(LONG, why="research.watch")).text == LONG
    app.settings.set("mind.register.templates", True)
    app.settings.set("mind.register.on", False)
    assert n.temperament(Message(LONG, why="research.watch")).text == LONG
