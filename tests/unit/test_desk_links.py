"""0.9.1 (B), the desk/voice/calls links: the Desk chat (L40), the talk box's answers kept after the page closes
(L140), the held-messages view and the being's link to it (L84), the "while you were away" summary (L85), what a call
covered settling held pings and questions (L29), the shared spoken answer (L41) and messages said aloud at the desk
(L42), desk-first calls (L34) and the missed check-in offered at the desk (L35). Calls' line, the AI, the speaker and
the microphone are faked."""

from __future__ import annotations

import pytest

from kurooto.core.state import jload
from kurooto.modules.calls.sessions import DESK
from kurooto.web import tools_api
from tests.unit.test_chat_sessions import chat  # noqa: F401 (the shared fixture)
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import said


# --------------------------------------------------------------------------------------------- L40
def test_desk_turns_make_one_desk_chat_quietly(chat):  # noqa: F811
    pc = chat.pc
    assert pc.desk_turn("what's due today?", "The lab report, at 17:00.", "spoken")
    rows = {r["id"]: r for r in chat.calls.sessions.listing()}
    assert rows[DESK]["title"] == "Desk"
    msgs = [m for m in said(chat) if m["session"] == DESK]
    assert [m["from"] for m in msgs] == ["you", "kurooto"] and msgs[1]["quiet"] is True
    assert [m["text"] for m in pc.thread(DESK)] == ["what's due today?", "The lab report, at 17:00."]
    ctx = jload(chat.ai.session_file(DESK), [])
    assert ctx[-1] == {**ctx[-1], "user": "what's due today?", "assistant": "The lab report, at 17:00."}
    assert chat.calls.sessions.rename(DESK, "Mine") == (False, "The Desk chat keeps its name.")
    chat.app.settings.set("calls.chat_desk", False)  # off: out of sight, nothing new goes in
    assert DESK not in {r["id"] for r in chat.calls.sessions.listing()}
    assert not pc.desk_turn("again?", "Yes.")


def test_the_board_box_feeds_the_desk_chat_and_history_only_when_asked(chat):  # noqa: F811
    app = chat.app
    code, out = tools_api.say(app, "/q", board=True)
    assert out["replies"] == ["No open questions."]
    assert [m["text"] for m in chat.pc.thread(DESK)][-2:] == ["/q", "No open questions."]
    tools_api.say(app, "/q")  # the kurooto command and the terminal: not in the Desk chat
    assert len(chat.pc.thread(DESK)) == 2
    code, out = tools_api.say(app, "explain eigenvalues", board=True)
    assert out["job"] and "Previous conversation" not in chat.prompts[-1][1]
    app.settings.set("calls.chat_desk_history", True)
    tools_api.say(app, "and eigenvectors?", board=True)
    assert "Previous conversation" in chat.prompts[-1][1] and "/q" in chat.prompts[-1][1]
    tools_api.say(app, "and eigenvectors?")  # never the CLI
    assert "Previous conversation" not in chat.prompts[-1][1]


# --------------------------------------------------------------------------------------------- L140
class _Job:
    def __init__(self, status, result):
        self.status, self.result = status, result


def test_a_talk_box_answer_reaches_the_desk_chat_after_the_page_closed(chat, monkeypatch):  # noqa: F811
    app = chat.app
    code, out = tools_api.say(app, "summarise chapter 3", board=True)
    jid = out["job"]
    monkeypatch.setattr(app.jobs, "get", lambda j: _Job("ok", "Chapter 3 is about rings.") if j == jid else None)
    n_tg = len(chat.fake.texts())
    chat.pc.on_event({"kind": "job_done", "job": jid})
    assert [m["text"] for m in chat.pc.thread(DESK)][-2:] == ["summarise chapter 3", "Chapter 3 is about rings."]
    got = chat.pc.answers_since(0)
    assert got[-1]["answer"] == "Chapter 3 is about rings." and got[-1]["asked"] == "summarise chapter 3"
    assert len(chat.fake.texts()) == n_tg  # never Telegram
    chat.pc.on_event({"kind": "job_done", "job": jid})  # told once
    assert len(chat.pc.answers_since(0)) == 1


@pytest.mark.parametrize("desk_on", [True, False])
def test_the_answer_is_kept_for_the_summary_even_with_the_desk_chat_off(chat, monkeypatch, desk_on):  # noqa: F811
    app = chat.app
    app.settings.set("calls.chat_desk", desk_on)
    code, out = tools_api.say(app, "what is a ring?", board=True)
    monkeypatch.setattr(app.jobs, "get", lambda j: _Job("ok", "A set with two operations."))
    chat.pc.on_event({"kind": "job_done", "job": out["job"]})
    assert chat.pc.answers_since(0)[-1]["answer"] == "A set with two operations."
    assert bool(chat.pc.thread(DESK)) is desk_on


# --------------------------------------------------------------------------------------------- L84
def test_the_waiting_page_lists_what_calm_holds_in_full_with_send_now(chat):  # noqa: F811
    from kurooto.core import waiting

    app = chat.app
    app.calm.hold("The lab report is due at 17:00, and the first part is still open.", "deadlines.soon", title="Due")
    rows = waiting.view(app)["held"]
    assert rows[-1]["text"].startswith("The lab report is due at 17:00") and rows[-1]["title"] == "Due"
    assert rows[-1]["waits"] == "the day's call was used"
    assert chat.calls.today._waiting()["held"] == len(rows)  # the same list Today counts
    assert waiting.send_held(app).startswith("Sent the 1")
    assert waiting.view(app)["held"] == []
    app.settings.set("look.being_held_link", False)
    assert waiting.view(app) == {"off": True}


# --------------------------------------------------------------------------------------------- L85
@pytest.fixture
def away(chat, monkeypatch):  # noqa: F811
    from kurooto.core import desktop

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(desktop, "notify", lambda title, text, urgent=False: shown.append((title, text)))
    app = chat.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "face"])
    f = app.modules["face"]
    f.hold_desktop("Reminder", "Call the lab at 15:00.")
    f.hold_desktop("Deadline", "Problem set 4 is due tomorrow.")
    return chat, f, shown


def test_back_at_the_desk_the_pop_ups_still_show_without_the_summary(away):
    env, f, shown = away
    f._on_watch("left")
    f.flush_desktop()
    assert [t for _, t in shown] == ["Call the lab at 15:00.", "Problem set 4 is due tomorrow."]
    assert f.away_card is None


def test_the_away_summary_adds_one_pop_up_and_a_card(away, monkeypatch):
    env, f, shown = away
    app = env.app
    app.settings.set("face.away.summary", True)
    f._on_watch("left")
    code, out = tools_api.say(app, "what is a ring?", board=True)
    monkeypatch.setattr(app.jobs, "get", lambda j: _Job("ok", "A set with two operations."))
    env.pc.on_event({"kind": "job_done", "job": out["job"]})
    f.flush_desktop()
    assert shown[0] == ("While you were away", "2 messages and 1 answer to what you asked in the talk box. "
                        "The dashboard's Waiting page has them.")  # fmt: skip
    assert [t for _, t in shown[1:]] == ["Call the lab at 15:00.", "Problem set 4 is due tomorrow."]  # as before
    from kurooto.core import waiting

    card = waiting.view(app)["card"]
    assert [p["text"] for p in card["popups"]][0] == "Call the lab at 15:00." and card["shown"] is True
    assert card["answers"][0]["answer"] == "A set with two operations."
    assert env.calls.today._waiting()["away"] == 3
    assert waiting.show_away(app) == "Cleared." and len(shown) == 3  # shown already: not again


def test_summary_only_replaces_the_storm_and_send_now_shows_them(away):
    env, f, shown = away
    app = env.app
    app.settings.set("face.away.summary", True)
    app.settings.set("face.away.summary_only", True)
    f._on_watch("left")
    f.flush_desktop()
    assert [t for t, _ in shown] == ["While you were away"] and not f.held
    from kurooto.core import waiting

    assert waiting.show_away(app) == "Showed 2 pop-ups."
    assert [t for _, t in shown[1:]] == ["Call the lab at 15:00.", "Problem set 4 is due tomorrow."]
    assert waiting.view(app)["card"] is None


# --------------------------------------------------------------------------------------------- L29
def _call_with(env, tools, lines):
    c = env.calls
    c.tool_log["s9"] = tools
    return c.save_transcript({"since": "s9", "lines": lines, "purpose": "Evening debrief"})


def test_what_a_call_went_over_is_marked_talked_through_never_closed(chat):  # noqa: F811
    from kurooto.core import waiting

    app = chat.app
    app.calm.hold("Problem set 4 is due tomorrow at 9.", "deadlines.soon", ws_item="deadline:d1", about="Problem set 4")
    app.calm.hold("Organic Chemistry has a quiz on Friday.", "deadlines.soon", about="Organic Chemistry quiz")
    qid = app.ask.ask("How was Linear Algebra?", source="capture", about="Linear Algebra", item="linear-algebra")
    aid = app.ask.approval("Send the draft to the lab?", about="Linear Algebra")
    lines = [
        {"who": "Kurooto", "text": "How did today go?"},
        {"who": "Sam", "text": "Fine. Linear Algebra was on eigenvalues."},
    ]
    _call_with(chat, [{"name": "deadline_progress", "args": str({"id": "d1", "done": "2", "total": "4"})}], lines)
    rows = waiting.view(app)["held"]
    assert [r["talked"].startswith("on your ") for r in rows] == [True, False]
    assert app.ask.get(qid)["talked"].startswith("on your ") and app.ask.get(qid)["status"] == "open"
    assert "talked" not in app.ask.get(aid)  # never an approval
    assert [q["id"] for q in waiting.view(app)["talked"]] == [qid]
    from kurooto.core.calm import still
    from kurooto.core.notify import Message

    m = Message("x", ws_item="deadline:d9")
    m.talked = "on your 17:00 call"
    assert still(app, m) == ""  # no such deadline: nothing it can tell
    m = Message("x")
    m.talked = "on your 17:00 call"
    assert still(app, m) == "talked through on your 17:00 call"
    assert waiting.settle(app, "held", rows[0]["id"]) == "Settled."
    assert waiting.settle(app, "question", qid) == "Settled." and app.ask.get(qid)["status"] == "expired"
    assert waiting.settle(app, "question", aid) == "That's not an open question."


def test_calls_settle_messages_closes_them_instead(chat):  # noqa: F811
    app = chat.app
    app.settings.set("calls.settle_messages", True)
    app.calm.hold("Problem set 4 is due tomorrow at 9.", "deadlines.soon", ws_item="deadline:d1")
    qid = app.ask.ask("How was Linear Algebra?", source="capture", ws_item="class:linear-algebra")
    aid = app.ask.approval("Skip Linear Algebra's quiz?", ws_item="class:linear-algebra")
    app.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]}])
    chat.on("subjects")
    tools = [
        {"name": "deadline_progress", "args": str({"id": "d1"})},
        {"name": "skip_class", "args": str({"subjects": ["la"]})},
    ]
    _call_with(chat, tools, [{"who": "Sam", "text": "skipping la"}])
    assert app.calm.held_rows() == []
    assert app.ask.get(qid)["status"] == "expired" and app.ask.get(aid)["status"] == "open"


# --------------------------------------------------------------------------------------------- L41, L42
@pytest.fixture
def desk_voice(tmp_path, monkeypatch):
    """Voice on with a fake mouth and ear: say() records, listen_once returns the next scripted answer."""
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    v = app.modules["voice"]
    monkeypatch.setattr(v.parts, "missing", lambda keys: [])
    monkeypatch.setattr(v, "_on_call", lambda: False)
    monkeypatch.setattr(v, "_night", lambda: False)
    ok, why = app.enable("voice")
    assert ok, why
    v.said, v.heard = [], []
    monkeypatch.setattr(v, "say", lambda text, wait=False, unprompted=False, why="": v.said.append(text) or (True, ""))
    monkeypatch.setattr(v, "listen_once", lambda timeout_s=8.0, own=False: v.heard.pop(0) if v.heard else None)
    monkeypatch.setattr(v, "others_here", lambda: False)
    monkeypatch.setattr(app.notifier, "at_desk", lambda: True)
    started = []

    class Now:  # the thread runs at once, here
        def __init__(self, target, args=(), **kw):
            self.target, self.args = target, args

        def start(self):
            started.append(1)
            self.target(*self.args)

    import kurooto.modules.voice as vmod

    monkeypatch.setattr(vmod.threading, "Thread", Now)
    yield app, v
    app.close()


def test_the_spoken_answer_says_whose_voice_and_never_with_others_here(desk_voice, monkeypatch):
    app, v = desk_voice
    v.heard = [("yes please", None, 1.4)]
    assert v.spoken_answer("Shall I?") == {"text": "yes please", "who": ""}  # Voice ID off: unchecked
    assert v.said == ["Shall I?"]
    monkeypatch.setattr(v, "verdict_of", lambda emb, s: "owner")
    v.heard = [("yes", None, 1.2)]
    assert v.spoken_yes("Shall I?") is True
    monkeypatch.setattr(v, "verdict_of", lambda emb, s: "guest")
    v.heard = [("yes", None, 1.2)]
    assert v.spoken_yes("Shall I?") is None  # not your voice
    monkeypatch.setattr(v, "others_here", lambda: True)
    v.heard = [("yes", None, 1.2)]
    assert v.spoken_answer("Shall I?") is None and v.heard  # nothing said, nothing taken


def test_a_question_is_said_aloud_and_your_spoken_answer_closes_it(desk_voice, monkeypatch):
    app, v = desk_voice
    app.settings.set("voice.speak.messages", True)
    monkeypatch.setattr(v, "verdict_of", lambda emb, s: "owner")
    v.heard = [("chapter four", None, 1.5)]
    qid = app.ask.ask("Which chapter is the quiz on?", source="study")
    assert v.said[0] == "A question for you: Which chapter is the quiz on?"
    q = app.ask.get(qid)
    assert q["status"] == "answered" and q["answer"] == "chapter four" and q["via"] == "voice"
    aid = app.ask.approval("Send the draft?")
    assert len(v.said) == 2 and app.ask.get(aid)["status"] == "open"  # an approval is never said: "Noted." only


def test_messages_aloud_is_off_by_default_and_not_your_voice_changes_nothing(desk_voice, monkeypatch):
    app, v = desk_voice
    v.heard = [("chapter four", None, 1.5)]
    qid = app.ask.ask("Which chapter is the quiz on?", source="study")
    assert v.said == [] and app.ask.get(qid)["status"] == "open"
    app.settings.set("voice.speak.messages", True)
    monkeypatch.setattr(v, "verdict_of", lambda emb, s: "unsure")
    qid = app.ask.ask("Which chapter is the quiz on?", source="study")
    assert v.said and app.ask.get(qid)["status"] == "open"


def test_a_reminder_said_aloud_and_done_takes_its_copies_down(desk_voice, monkeypatch):
    app, v = desk_voice
    app.settings.set("voice.speak.messages", True)
    monkeypatch.setattr(v, "verdict_of", lambda emb, s: "owner")
    gone = []
    monkeypatch.setattr(app.notifier, "retract", lambda k=None, r=None, b=None: gone.append((k, r)))
    v.heard = [("done", None, 0.9)]
    app.notify(
        "Call the lab.\n\nDone · Snooze", kind="reminder", map_kind="reminder", map_ref="r1", why="reminders.own"
    )
    assert v.said == ["Reminder: Call the lab."] and gone == [("reminder", "r1")]


# --------------------------------------------------------------------------------------------- L34, L35
class DeskVoice:
    """Stands in for Voice at the desk: its answer to "shall we do it here?" and the calls it took."""

    def __init__(self, yes):
        self.yes, self.calls = yes, []
        self.voiceid = type("V", (), {"on": staticmethod(lambda: False)})()

    def spoken_yes(self, prompt, timeout_s=8.0, why="", need_owner=True):
        self.asked = prompt
        return self.yes

    def desk_call(self, since, reason, script):
        self.calls.append((since, reason, script))
        return True


@pytest.fixture
def desk(phone, monkeypatch):  # noqa: F811
    import kurooto.modules.calls as cmod

    class Now:
        def __init__(self, target, args=(), **kw):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(cmod.threading, "Thread", Now)
    return phone


def rings_of(env):
    return [kw for op, kw in env.ops if op == "ring"]


def test_desk_first_is_off_by_default_and_the_phone_rings(desk):
    c = desk.calls
    assert c.setting("desk_first") is False and c.desk_free() is None
    desk.app.settings.set("calls.desk_first", True)
    assert c.desk_free() is None  # Voice and Face presence off: nobody to offer it to
    assert c.ring("Evening debrief", key="fakeq:evening", why="checkins.call") and len(rings_of(desk)) == 1


def test_a_yes_at_the_desk_takes_the_call_here_and_the_phone_never_rings(desk, monkeypatch):
    c, v = desk.calls, DeskVoice(True)
    desk.app.settings.set("calls.desk_first", True)
    monkeypatch.setattr(c, "desk_free", lambda: v)
    out = c.ring("Evening debrief", key="fakeq:evening", why="checkins.call")
    since = out.removeprefix("desk-")
    assert out.startswith("desk-") and rings_of(desk) == [] and "Shall we do it here?" in v.asked
    assert v.calls[0][:2] == (since, "Evening debrief")
    assert jload(c.dir / "rings.json", {})[since]["state"] == "taken"
    assert not desk.app.scheduler.get(f"calls:desk:{since}")
    c._desk_fallback({"since": since})  # too late: it was taken
    assert rings_of(desk) == []


@pytest.mark.parametrize("answer,rings_now", [(None, 0), (False, 1)])
def test_no_answer_or_no_rings_the_phone(desk, monkeypatch, answer, rings_now):
    c = desk.calls
    desk.app.settings.set("calls.desk_first", True)
    monkeypatch.setattr(c, "desk_free", lambda: DeskVoice(answer))
    since = c.ring("A reminder call", key="fakeq:r", why="reminders.call").removeprefix("desk-")
    assert len(rings_of(desk)) == rings_now  # "no": at once; nothing said: after desk_first_s
    c._desk_fallback({"since": since})
    assert len(rings_of(desk)) == 1 and jload(c.dir / "rings.json", {})[since]["state"] == "phone"
    assert c.ring("Wake-up call", alarm=True, key="alarm:next") and len(rings_of(desk)) == 2  # never the alarm


def test_the_waited_check_in_is_offered_by_the_greeting_and_taken_at_the_desk(desk):
    from kurooto.modules import daily
    from kurooto.modules.face import greet

    app = desk.app
    desk.on("checkins")
    app.settings.set("checkins.by_call", True)
    ck = app.modules["checkins"]
    day = ck.day_of()
    ck._status("evening", day, "asked")  # the call went unanswered: it came as a message
    assert ck.waited() == "evening"
    text, parts = greet.compose(["waiting", "missed_call"], [], (1, 0), None, 0, False, daily.now(), missed="evening")
    assert "Your evening check-in waited; say yes to do it here." in text and "Want to go through them" not in text
    assert parts == ["waiting", "missed_call"]
    v = app.modules["voice"]
    v.offer_checkin("evening")
    assert not v._take_checkin_offer("what's due?")  # not a yes: the offer lapses
    v.offer_checkin("evening")
    assert v._take_checkin_offer("yes")
    assert ck.today(day)["evening"]["status"] == "answered" and v.desk_calling["reason"] == "Evening debrief"
    assert "Evening debrief" in v.desk_call_line("fine") and v.desk_call_line("fine").endswith("They said: fine")
    lines = [{"who": "Kurooto", "text": "How did today go?"}, {"who": "Sam", "text": "Wrote the lab report."}]
    desk.calls.desk_done(v.desk_calling["since"], lines, "Evening debrief")
    assert "Wrote the lab report." in daily.note_path(app, day).read_text()  # its journal, as a call's
