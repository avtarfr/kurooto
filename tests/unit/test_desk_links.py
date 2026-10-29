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
