"""What goes with a chat turn to the AI (0.9.0): how a typed turn came ("[How it came]", chat.context_line), the phone's
saved place and Wi-Fi name only with chat.context_places, the greeting it had just said when you answer it
(face.greet.tell_ai), and the reasons for its own recent messages when you ask why (mind.why.to_ai). Fakes only: no
AI is asked, no camera or microphone is opened."""

from __future__ import annotations

import time
from types import SimpleNamespace

from kurooto.modules.base import Incoming


def ask(app, text, via="telegram", **kw):
    msg = Incoming(text, via=via, respond=lambda t, buttons=None: None, **kw)
    app.modules["chat"].ask(msg)
    return app.jobs.get(msg.job).prompt


# ------------------------------------------------------------------------------------- L3 how a typed turn came
def test_a_typed_turn_says_where_it_was_typed(env):
    app = env.app
    assert "[How it came] They typed this on Telegram." in ask(app, "what's due?")
    assert "[How it came] They typed this in the phone app." in ask(app, "what's due?", via="app")
    assert "[How it came] They typed this on this computer" in ask(app, "what's due?", via="terminal")
    p = ask(app, "capital of peru")
    assert p.index("[How it came]") < p.index("[Reply style]")  # the register line stays last
    app.settings.set("chat.context_line", False)
    assert "[How it came]" not in ask(app, "what's due?")


def test_away_from_the_desk_and_a_call_in_coarse_words(env, monkeypatch):
    import datetime as dt

    from kurooto.web import tools_api

    app = env.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "face"])
    f = app.modules["face"]
    monkeypatch.setattr(f, "left_at", lambda: dt.datetime(2026, 11, 3, 14, 10))
    monkeypatch.setattr(tools_api, "live_call", lambda a: True)
    p = ask(app, "what now?", via="app")
    assert "Face presence noticed they stepped away from their desk at 14:10." in p
    assert "They're on a phone call right now." in p
    assert "place" not in p.split("[How it came]")[1]  # no place without its own switch


def test_the_context_line_never_reaches_the_chat_history(env):
    from kurooto.core.state import jload

    app = env.app
    chat = app.modules["chat"]
    middling = " ".join(["word"] * 30)  # no register line: the context line is last
    chat.record_turn(ask(app, middling), "ok")
    assert jload(chat.history_file, [])[-1]["user"] == middling


def test_places_go_only_with_their_own_switch(env, monkeypatch):
    from kurooto import mind
    from kurooto.core import nearby
    from kurooto.mind.senses import phone, store

    app = env.app
    monkeypatch.setattr(mind, "on", lambda a: True)
    app.settings.set("mind.senses.phone.places", True)
    app.settings.set("mind.senses.phone.wifi", True)
    store.add(app, "phone:places", "event", "the library", 0.0)
    store.add(app, "phone:wifi", "id", "a1b2c3d4e5f6", 0.0)
    phone.label_wifi(app, "a1b2c3d4e5f6", "campus")
    assert "library" not in ask(app, "where am I?") and "campus" not in ask(app, "where am I?")
    app.settings.set("chat.context_places", True)
    p = ask(app, "where am I?")
    assert 'was last at or near the place they saved as "the library"' in p and 'Wi-Fi they call "campus"' in p
    nearby.set_phone_out(app, True)
    assert 'Their phone left the place they saved as "the library"' in ask(app, "where am I?")


# ------------------------------------------------------------------------------- L7 the greeting it just said
def test_answering_the_greeting_tells_the_ai_what_it_said(env, monkeypatch):
    app = env.app
    portal = SimpleNamespace(open=True, opened_why="greeting", turns=0, last_reply="Welcome back. Two questions wait.")
    monkeypatch.setitem(app.modules, "voice", SimpleNamespace(portal=portal))
    p = ask(app, "yes", via="voice", voice=True)
    assert 'you had greeted them aloud, unasked, with: "Welcome back. Two questions wait."' in p
    portal.turns = 1  # a later turn in that conversation: the history carries it
    assert "greeted them aloud" not in ask(app, "and then?", via="voice", voice=True)
    portal.turns, portal.opened_why = 0, "its name"
    assert "greeted them aloud" not in ask(app, "yes", via="voice", voice=True)
    portal.opened_why = "greeting"
    app.settings.set("face.greet.tell_ai", False)
    assert "greeted them aloud" not in ask(app, "yes", via="voice", voice=True)
    app.settings.set("face.greet.tell_ai", True)
    assert "greeted them aloud" not in ask(app, "yes")  # typed: not an answer to what it said aloud


# ------------------------------------------------------------------------------- L88 why it did things lately
def test_asking_why_gives_the_reasons_for_its_own_recent_messages(env, monkeypatch):
    from kurooto import mind
    from kurooto.mind import records

    app = env.app
    monkeypatch.setattr(mind, "on", lambda a: True)
    rows = [
        {"id": "a" * 32, "ref": "r1", "why": "face.greet", "kind": "spoken", "at": time.time() - 600,
         "expect": {"what": "reply", "within_h": 0.05}, "door": "the read said tired", "gate": "it passed Brain's "
         "gate as it was", "outcome": {"result": "missed"}},
        {"id": "b" * 32, "ref": "r2", "why": "deadlines.ping", "kind": "info", "at": time.time() - 60, "expect": None,
         "door": "", "gate": "Brain's gate made it quieter (the line under it says why)", "outcome": None},
        {"id": "c" * 32, "ref": "r3", "why": "x", "kind": "info", "at": time.time() - 3 * 86400, "expect": None},
    ]  # fmt: skip
    records._save(app, {"rows": rows})
    assert "[Why it did things lately]" not in ask(app, "what's next?")  # only a turn that asks why
    p = ask(app, "why did you greet me?")
    line = p.split("[Why it did things lately]")[1]
    assert "a spoken greeting when you sat down" in line and "setting face.greet.on" in line
    assert "nothing came of it in time" in line and "Brain's gate made it quieter" in line
    assert "tired" not in line and "the read" not in line  # never what the door's words cite
    assert line.count(";") >= 1 and "r3" not in line
    app.settings.set("mind.why.to_ai", False)
    assert "[Why it did things lately]" not in ask(app, "why?")
    app.settings.set("mind.why.to_ai", True)
    app.settings.set("mind.why.on", False)
    assert "[Why it did things lately]" not in ask(app, "why?")
    monkeypatch.setattr(mind, "on", lambda a: False)
    app.settings.set("mind.why.on", True)
    assert "[Why it did things lately]" not in ask(app, "why?")  # Brain off
