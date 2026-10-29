"""0.9.0 links, messages and memory (batch 2): follow me (L76), someone else here (L78), pop-ups that close once
answered (L77). Fake channels, a fake desktop and a fake Face presence."""

from __future__ import annotations

import pytest

from kurooto.core import biometric, desktop, nearby
from kurooto.core import notify as notify_mod


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("notify.calm.on", False)
    a.sent = {"telegram": [], "app": [], "desktop": [], "closed": []}
    a.notifier.channels["telegram"] = lambda m: a.sent["telegram"].append(m) or 7
    a.notifier.channels["app"] = lambda m: a.sent["app"].append(m)
    ids = iter(range(100, 200))

    def show(title, text, urgent=False):
        a.sent["desktop"].append((title, text))
        desktop.last_id = str(next(ids))
        return True

    monkeypatch.setattr(desktop, "notify", show)
    monkeypatch.setattr(desktop, "close", lambda nid: a.sent["closed"].append(nid) or True)
    yield a
    a.close()


class FakeFace:
    def __init__(self):
        from collections import deque

        self.held = deque(maxlen=20)

    def hold_desktop(self, title, text, urgent=False, key=None):
        self.held.append((title, text, urgent, key))

    def drop_held(self, gone):
        from kurooto.modules.face import Face

        return Face.drop_held(self, gone)


def test_follow_me_adds_a_phone_copy_when_away_and_keeps_everything_else(app, monkeypatch):
    face = FakeFace()
    monkeypatch.setitem(app.modules, "face", face)
    monkeypatch.setattr(app, "away_from_desk", lambda: True)
    app.settings.set("face.away.hold_desktop", True)
    app.notify("Due tomorrow: Report", kind="deadline")
    assert len(face.held) == 1 and not app.sent["app"]  # off (the default): as before
    app.settings.set("notify.follow_me", True)
    app.notify("Due tomorrow: Essay", kind="deadline")
    assert len(face.held) == 2 and [m.text for m in app.sent["app"]] == ["Due tomorrow: Essay"]
    assert len(app.sent["telegram"]) == 2  # Telegram as always
    app.notify("Approve?", kind="approval")  # the app gets approvals already: not twice
    assert len(app.sent["app"]) == 2


def test_at_the_desk_telegram_is_silent_and_the_desktop_goes_first(app, monkeypatch):
    monkeypatch.setattr(app.notifier, "at_desk", lambda: True)
    app.notify("New papers", kind="info")
    assert not app.sent["telegram"][-1].silent and not app.sent["desktop"]
    app.settings.set("notify.follow_me", True)
    app.settings.set("notify.desk_silent_phone", True)
    app.settings.set("notify.desk_first", True)
    app.notify("More papers", kind="info")
    assert app.sent["telegram"][-1].silent and app.sent["desktop"][-1] == (app.name, "More papers")
    app.notify("Ring", kind="info", urgent=True)
    assert not app.sent["telegram"][-1].silent  # urgent ones ring as always
    monkeypatch.setattr(app.notifier, "at_desk", lambda: False)  # can't tell: exactly as now
    app.notify("Even more", kind="info")
    assert not app.sent["telegram"][-1].silent


def test_someone_else_here_gets_a_plain_pop_up(app, monkeypatch):
    app.notify("Due soon: thesis chapter", kind="deadline")
    assert app.sent["desktop"][-1][1] == "Due soon: thesis chapter"
    app.settings.set("notify.guests_hold", True)
    nearby.set_facing(app, 2, 2)  # two faces close and looking
    app.notify("Due soon: thesis chapter", kind="deadline")
    assert app.sent["desktop"][-1] == (app.name, notify_mod.GENERIC)
    assert app.sent["telegram"][-1].text == "Due soon: thesis chapter"  # the full text elsewhere, as now
    monkeypatch.setattr(nearby, "facing_many", lambda a, within=10.0: False)
    biometric.note_others(app, 30)  # another voice
    assert app.notifier.guests_here()


def test_a_pop_up_closes_once_its_question_is_answered(app, monkeypatch):
    qid = app.ask.ask("Which chapter?", choices=["3", "4"])
    assert app.sent["desktop"] and app.notifier.shown
    face = FakeFace()
    face.hold_desktop("Question", "Held", key=("ask", qid, ()))
    monkeypatch.setitem(app.modules, "face", face)
    app.ask.answer(qid, "3", "telegram")
    assert app.sent["closed"] and not app.notifier.shown and not face.held
    app.settings.set("notify.desktop_retract", False)
    q2 = app.ask.ask("Which day?", choices=["Mon"])
    app.ask.answer(q2, "Mon", "telegram")
    assert len(app.sent["closed"]) == 1  # off: pop-ups stay as before


# ------------------------------------------------------------------- availability: L12, L13, L86, L87
import datetime as dt  # noqa: E402

from kurooto.core import availability as av_mod  # noqa: E402
from kurooto.mind import sleep as sleep_mod  # noqa: E402
from kurooto.mind.senses import phone as phone_mod  # noqa: E402


def _at(h: int, m: int = 0, day: int = 3) -> dt.datetime:
    return dt.datetime(2026, 11, day, h, m)


def test_brain_asleep_holds_its_own_calls_only_when_switched_on(app, monkeypatch):
    av = app.availability
    t = _at(21, 30)  # before the night hours
    monkeypatch.setattr(sleep_mod, "state", lambda a, tt=None: "asleep")
    monkeypatch.setattr(sleep_mod, "window", lambda a, tt=None: (_at(21), _at(6, 30, 4)))
    assert av.night(t) is None  # off (the default): as before
    app.settings.set("checkins.asleep_follows_brain", True)
    assert av.night(t) == (av_mod.BRAIN_ASLEEP, _at(6, 30, 4))
    assert av.call_block(t, why="checkins.call")[0] == av_mod.BRAIN_ASLEEP
    assert av.call_block(t, why="calls.own") == (None, None)  # a call you asked for goes on
    soon = (t + dt.timedelta(hours=3)).isoformat()
    monkeypatch.setattr(av_mod, "now", lambda: t)
    assert av.call_block(t, why="deadlines.call", due=soon) == (None, None)  # a deadline under 12 hours


def test_the_phones_own_alarm_ends_the_night_early_never_late(app, monkeypatch):
    av = app.availability
    alarm = {"at": _at(6, 0).timestamp()}
    monkeypatch.setattr(phone_mod, "next_alarm", lambda a: alarm["at"])
    assert av.night(_at(5)) == ("it's night", _at(6, 0))  # 07:00 before
    assert av.night(_at(6, 30)) is None  # it rang: the night is over
    alarm["at"] = _at(8, 0).timestamp()
    assert av.night(_at(5)) == ("it's night", _at(7, 0))  # later than the night's end: ignored
    app.settings.set("availability.night.phone_alarm", False)
    alarm["at"] = _at(6, 0).timestamp()
    assert av.night(_at(5)) == ("it's night", _at(7, 0))


def test_phone_alarm_and_mine_disagree_asked_once(app, monkeypatch):
    from kurooto.modules import alarm as alarm_mod

    t = _at(22)
    monkeypatch.setattr(alarm_mod, "now", lambda: t)
    al = app.modules["alarm"]
    monkeypatch.setattr(al, "next", lambda: _at(7, 30, 4))
    monkeypatch.setattr(phone_mod, "next_alarm", lambda a: _at(6, 0, 4).timestamp())
    said = al.phone_mismatch()
    assert said == "Your phone's alarm is at 06:00, mine at 07:30. Keep both?"
    buttons = app.sent["telegram"][-1].buttons[0]
    assert buttons[0] == ("Keep both", "alm:phone:keep") and buttons[1][1] == "alm:202611040600:set"
    assert al.phone_mismatch() == ""  # once per pair
    assert al._suggest_button("phone", "keep") == "Both stay as they are."


def test_phone_dnd_queues_what_can_wait_and_holds_its_calls(app, monkeypatch):
    dnd = {"on": True}
    monkeypatch.setattr(phone_mod, "dnd_on", lambda a: dnd["on"])
    app.notify("New papers", kind="info", why="research.papers")
    assert len(app.sent["telegram"]) == 1  # off (the default): as before
    app.settings.set("notify.respect_phone_dnd", True)
    app.notify("More papers", kind="info", why="research.papers")
    assert len(app.sent["telegram"]) == 1  # waits, like focus
    app.notify("Approve?", kind="approval")
    app.notify("Your reminder", kind="reminder", why="reminders.own")
    assert len(app.sent["telegram"]) == 3  # never held
    av = app.availability
    assert av.call_block(_at(12), why="checkins.call")[0] == "your phone is on Do Not Disturb"
    assert av.call_block(_at(12), why="calls.own") == (None, None)
    assert app.notifier.flush_dnd() == 0  # still on
    dnd["on"] = False
    assert app.notifier.flush_dnd() == 1 and app.sent["telegram"][-1].text == "More papers"


def test_moving_and_a_phone_call_hold_only_what_is_switched_on(app, monkeypatch):
    av = app.availability
    monkeypatch.setattr(phone_mod, "moving", lambda a: "walking")
    assert av.call_block(_at(12), why="checkins.call") == (None, None)
    app.settings.set("calls.hold_moving", True)
    assert av.call_block(_at(12), why="checkins.call")[0] == "you're on the move (walking)"
    app.settings.set("calls.hold_moving", False)
    chat = app.modules["calls"].chat
    until = (dt.datetime.now() + dt.timedelta(minutes=20)).timestamp() * 1000
    assert chat._busy({"until": until}) == (200, {"ok": True})
    assert av.phone_busy_until() is not None and av.on_call_until() is None  # apart from its own calls
    app.settings.set("availability.night.enabled", False)  # whatever the hour the test runs at
    soon = dt.datetime.now() + dt.timedelta(minutes=1)
    assert av.call_block(soon, why="checkins.call") == (None, None)  # off: only noted
    app.settings.set("calls.phone_busy", True)
    assert av.call_block(soon, why="checkins.call")[0] == av_mod.PHONE_CALL
    assert av.call_block(soon, why="calls.own") == (None, None)  # a call you asked for goes on
    assert chat._busy({"until": 0})[0] == 200 and av.phone_busy_until() is None


# ------------------------------------------------------------------------- Wrong everywhere: L81, L82, L75, L99
from kurooto.modules import cases as cases_mod  # noqa: E402
from kurooto.modules.base import Incoming  # noqa: E402


def _said(cs, text: str, via: str, speaker: str = ""):
    got = []
    msg = Incoming(text, via=via, respond=lambda t, buttons=None: got.append((t, buttons)), speaker=speaker)
    cs.watch(msg, text, [])
    return msg, got


def test_wrong_on_the_app_chat_and_said_aloud(app, monkeypatch):
    cs = app.modules["cases"]
    msg, got = _said(cs, "whats on my plate", "app")
    msg.reply("Nothing due.")
    assert got[-1][1][-1][0][0] == "Wrong"  # the app's chat gets the Wrong button
    heard = []
    monkeypatch.setitem(cases_mod.WRONG_LISTENERS, "probe", lambda a, c: heard.append(c))
    msg, got = _said(cs, "whats due", "voice", speaker="owner")
    msg.reply("Nothing due.")
    _said(cs, "that's wrong", "voice", speaker="guest")  # someone else's voice: nothing
    assert not heard
    _said(cs, "that's wrong", "voice", speaker="owner")
    assert len(heard) == 1  # the learners hear it
    case = cs.store.load()["cases"][heard[-1]["id"]]
    assert case["wrong"] and case["wrong_via"] == "voice" and case["text"] == "whats due"
    app.settings.set("cases.surfaces", [])
    msg, got = _said(cs, "whats on my plate", "app")
    msg.reply("Nothing due.")
    assert not got[-1][1]  # off: as before (Telegram and the terminal only)


def test_one_wrong_reaches_its_learners(app, monkeypatch):
    from kurooto.mind import act

    cs = app.modules["cases"]
    complaints = []
    monkeypatch.setattr(act, "evidence", lambda a, action, kind, seen=True: complaints.append((action, kind)))
    msg, _ = _said(cs, "skip gym", "telegram")
    msg.reply("Skipped.")
    with cs._lock:
        d = cs._drafts[cs._last]
    d.update(did="skip_commitment", tools=["search_notes"])
    cs.store.change(lambda dd: dd["cases"].get(d["id"], {}).update(did="skip_commitment"), cs._keep_days())
    cs.wrong(d["id"])
    assert complaints == []  # mind.trust.from_wrong is off by default
    kinds = [e["kind"] for e in app.events.tail(50)]
    assert "case_wrong_notes" in kinds  # flagged for Dreaming's morning
    app.settings.set("mind.trust.from_wrong", True)
    cs.wrong(d["id"])
    assert complaints == [("skip_commitment", "complaint")]
    dr = app.modules["dreaming"]
    ev = [e for e in app.events.tail(50) if e["kind"] == "case_wrong_notes"]
    app.settings.set("modules.enabled", ["dreaming"])
    assert any("marked Wrong" in line for line in dr.loose_ends(ev))
    app.settings.set("cases.to_dreaming", False)
    assert not any("marked Wrong" in line for line in dr.loose_ends(ev))


def test_dream_lessons_learn_from_wrongs_calls_and_discarded_proposals(app):
    from kurooto.mind import dream

    day = dt.date.today()
    for _ in range(2):
        app.events.emit("case_kept", kind="wrong", did="skip_commitment", wrong=True)
        app.events.emit("call_reviewed", lessons=1)
        app.events.emit("proposal_made", id="p1", source="repo_refresh")
        app.events.emit("proposal_discarded", id="p1")
    out = dream.outcomes(app, day)
    assert out["cases"]["skip_commitment"] == 2 and out["calls"] == 2 and out["proposals"]["repo_refresh"] == 2
    lines = [x["line"] for x in dream.distil(out)]
    assert "Check with me before taking a request as skip commitment" in lines
    assert "Fewer proposals from repo refresh" in lines
    for k in ("mind.dream.from_wrong", "mind.dream.from_calls", "mind.dream.from_proposals"):
        app.settings.set(k, False)
    out = dream.outcomes(app, day)
    assert not out["cases"] and not out["calls"] and not out["proposals"]


# --------------------------------------------------------------------------------------- L90: the console edits
def test_console_wrong_and_forget_and_the_note_line(app):
    from kurooto.mind.tom import model, prefs
    from kurooto.modules import remember

    app.settings.set("modules.enabled", ["mind"])
    f = remember.help_file(app)
    f.parent.mkdir(parents=True, exist_ok=True)
    body = f"# How to help me\n\n- Be brief in the mornings\n\n## {remember.LEARNED}\n\n- Fewer nudges in the evening\n"
    f.write_text(body, encoding="utf-8")
    prefs.sync(app)
    rows = {r["claim"]: r for r in model.rows(app, prefs.PART)}
    mine, its = rows["Be brief in the mornings"], rows["Fewer nudges in the evening"]
    got = prefs.console_edit(app, "wrong", mine["id"])
    assert got["ok"] and "offer" not in got  # your own line is never offered
    got = prefs.console_edit(app, "wrong", its["id"])
    assert got["offer"] == {"act": "unline", "id": its["id"], "line": "Fewer nudges in the evening"}
    prefs.sync(app)
    assert model.get(app, its["id"])["wrong"]  # the fix: reading the note again doesn't undo the Wrong
    assert prefs.console_edit(app, "unline", its["id"])["ok"]
    assert "Fewer nudges" not in f.read_text(encoding="utf-8") and "Be brief" in f.read_text(encoding="utf-8")
    assert prefs.console_edit(app, "forget", mine["id"])["said"] == "Forgotten."
    app.settings.set("mind.console.edit", False)
    assert not prefs.console_edit(app, "forget", its["id"])["ok"]


# ------------------------------------------------------------------------------------------ L89: the Memory page
def test_the_memory_page_reads_every_store_side_by_side(app, monkeypatch):
    from kurooto.core import memorypage, threads

    threads.observe(app, "I'll send the draft tonight", via="chat")
    monkeypatch.setitem(memorypage.COUNTERS, "gadget", lambda a: {"title": "Gadget facts", "count": 3, "what": "kept"})
    v = memorypage.view(app)
    assert not v["off"] and {"ledger", "threads", "inferred", "learned", "not_interested", "model"} <= set(v)
    assert v["addons"] == [{"title": "Gadget facts", "count": 3, "what": "kept"}]
    assert isinstance(v["ledger"].get("rows", []), list)
    app.settings.set("look.memory_page", False)
    assert memorypage.view(app) == {"off": True}


# ------------------------------------------------------------------------- L41: going through what waits, aloud
def test_a_spoken_yes_goes_through_the_waiting_questions(app, monkeypatch):
    from kurooto.core import walkthrough

    q1 = app.ask.ask("Which chapter is the quiz on?", choices=["3", "4"], title="Quiz")
    q2 = app.ask.ask("Anything to add to the lab report?")
    app.ask.approval("Send the draft to your supervisor?")
    said = []

    def say(text, speaker="owner"):
        msg = Incoming(text, via="voice", speaker=speaker, respond=lambda t, buttons=None: said.append(t))
        return walkthrough.take(app, msg, text)

    assert say("yes") is None  # nothing was offered
    walkthrough.offered(app)
    assert say("yes", speaker="guest") is None  # someone else's voice
    first = say("sure")
    assert first.startswith("1 approval waits for your tap") and "Which chapter" in first
    assert "lab report" in say("chapter 4")
    assert app.ask.get(q1)["status"] == "answered" and app.ask.get(q1)["via"] == "voice"
    assert say("later").endswith("That's all of them.")
    assert app.ask.get(q2)["status"] == "open" and not walkthrough.active(app)
    walkthrough.offered(app)
    biometric.note_others(app, 30)
    assert say("yes").startswith("Not with someone else here")
    app.settings.set("voice.answers_questions", False)
    walkthrough.offered(app)
    assert say("yes") is None
