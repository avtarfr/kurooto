"""Questions and approvals (core/ask.py): asking, answering anywhere (first answer wins), Later, Nothing new,
expiry, hooks, events, Telegram buttons and replies, /q, and the call tools."""

import datetime as dt
import json

import pytest

from kurooto.core.ask import APPROVE, DENY, NOTHING
from kurooto.core.clock import now


@pytest.fixture
def app(env):
    env.app.settings.set("notify.desktop", False)
    return env.app


def events(app, kind):
    return [e for e in app.events.tail(500) if e["kind"] == kind]


def sent_with_buttons(fake):
    return [p for m, p in fake.sent if m == "sendMessage" and p.get("reply_markup")]


# ------------------------------------------------------------------------------------------------ the API
def test_ask_saves_delivers_and_emits(app, env):
    qid = app.ask.ask("Which chapter is the quiz on?", choices=["3", "4", " ", "3"], source="study")
    q = app.ask.get(qid)
    assert q["status"] == "open" and q["choices"] == ["3", "4"] and q["source"] == "study"
    assert q["msg"] is not None  # the Telegram message id, for editing it later
    assert (app.paths.state / "ask" / f"{qid}.json").is_file()
    msg = sent_with_buttons(env.fake)[-1]
    assert msg["text"].startswith("Question\n\nWhich chapter is the quiz on?")
    rows = msg["reply_markup"]["inline_keyboard"]
    assert [[b["text"] for b in r] for r in rows] == [["3"], ["4"], ["Later"]]
    assert rows[0][0]["callback_data"] == f"ask:{qid}:0" and rows[-1][0]["callback_data"] == f"ask:{qid}:L"
    ev = events(app, "question_asked")[-1]
    assert ev["id"] == qid and ev["subkind"] == "question" and ev["source"] == "study" and ev["choices"] == 2
    assert [p["id"] for p in app.ask.pending()] == [qid]


def test_approval_defaults_and_custom_choices(app, env):
    a = app.ask.ask("Delete the old drafts?", kind="approval")
    assert app.ask.get(a)["choices"] == [APPROVE, DENY]
    rows = sent_with_buttons(env.fake)[-1]["reply_markup"]["inline_keyboard"]
    assert [[b["text"] for b in r] for r in rows] == [["Approve", "Deny"], ["Later"]]
    assert sent_with_buttons(env.fake)[-1]["text"].startswith("Approval needed")
    b = app.ask.ask("Reply to Sam?", choices=["Send", "Edit", "Discard"], kind="approval")
    assert app.ask.get(b)["choices"] == ["Send", "Edit", "Discard"]
    assert app.ask.answer(b, "yes", "app")["ok"] is False  # yes doesn't guess which of three
    assert app.ask.answer(b, "send", "app")["answer"] == "Send"


def test_unknown_kind_and_empty_text(app):
    assert app.ask.get(app.ask.ask("x?", kind="weird"))["kind"] == "question"
    with pytest.raises(ValueError):
        app.ask.ask("  ")


def test_first_answer_wins_across_channels(app):
    got = []
    app.ask.hooks["t.h"] = lambda q, a: got.append((q["hook_payload"], a))
    qid = app.ask.ask("Approve the plan?", kind="approval", hook="t.h", hook_payload={"plan": 1})
    r = app.ask.answer(qid, "yes please", "call")
    assert r["ok"] and r["answer"] == APPROVE and r["via"] == "call" and r["status"] == "answered"
    again = app.ask.answer(qid, "no", "telegram")
    assert again["ok"] is False and "Already answered: Approve (via call)" in again["note"]
    assert got == [({"plan": 1}, APPROVE)]  # the hook ran once
    assert app.ask.pending() == []
    ev = events(app, "question_answered")[-1]
    assert ev["via"] == "call" and ev["seconds"] >= 0 and ev["choice"] == 0 and ev["subkind"] == "approval"


@pytest.mark.parametrize(
    ("typed", "want"),
    [("No", DENY), ("deny.", DENY), ("ok", APPROVE), ("Approve", APPROVE), ("1", None), ("maybe", None)],
)
def test_approval_words(app, typed, want):
    qid = app.ask.ask("Go?", kind="approval")
    r = app.ask.answer(qid, typed, "app")
    assert (r["answer"] if r["ok"] else None) == want
    if want is None:
        assert r["note"] == "Approve or Deny?" and app.ask.get(qid)["status"] == "open"


def test_question_answers_choices_numbers_free_text(app):
    a = app.ask.ask("Which?", choices=["Linear algebra", "Analysis"])
    assert app.ask.answer(a, "analysis", "telegram")["answer"] == "Analysis"
    b = app.ask.ask("Which?", choices=["Linear algebra", "Analysis"])
    assert app.ask.answer(b, "1", "telegram")["answer"] == "Linear algebra"  # typed numbers count from 1
    c = app.ask.ask("How did it go?")
    assert app.ask.answer(c, "Fine, did the exercises", "telegram")["answer"] == "Fine, did the exercises"
    d = app.ask.ask("How did it go?")
    assert app.ask.answer(d, "", "telegram")["ok"] is False


def test_later_keeps_it_for_the_next_call(app):
    got = []
    app.ask.hooks["t.h"] = lambda q, a: got.append(a)
    qid = app.ask.ask("What did you cover?", hook="t.h")
    r = app.ask.answer(qid, "Later", "telegram")
    assert r["ok"] and r["status"] == "later" and got == []
    assert [q["id"] for q in app.ask.pending()] == [qid]
    brief = app.ask.call_brief()["open_questions"][0]
    assert brief["id"] == qid and brief["kept_for_this_call"] is True
    assert events(app, "question_later")[-1]["id"] == qid
    assert app.ask.answer(qid, "chapter 4", "call")["answer"] == "chapter 4" and got == ["chapter 4"]


def test_nothing_new_is_an_answer(app):
    got = []
    app.ask.hooks["t.h"] = lambda q, a: got.append((a, q["nothing"]))
    qid = app.ask.ask("Anything from class?", hook="t.h")
    r = app.ask.answer(qid, "nothing new", "telegram")
    assert r["ok"] and r["answer"] == NOTHING and got == [(NOTHING, True)]
    assert events(app, "question_answered")[-1]["nothing"] is True
    b = app.ask.ask("After class: anything?", choices=["Nothing new"], hook="t.h", title="After class")
    app.ask.button(b, "0")
    assert got[-1] == (NOTHING, True)


def test_expiry_sweep_and_no_hook(app, env):
    got = []
    app.ask.hooks["t.h"] = lambda q, a: got.append(a)
    old = app.ask.ask("Old one?", hook="t.h", expires=now() - dt.timedelta(minutes=1))
    keep = app.ask.ask("Fresh?", expires="2d")
    assert dt.datetime.fromisoformat(app.ask.get(keep)["expires"]) > now() + dt.timedelta(hours=47)
    assert app.ask.sweep() == 1
    assert app.ask.get(old)["status"] == "expired" and [q["id"] for q in app.ask.pending()] == [keep]
    r = app.ask.answer(old, "yes", "telegram")
    assert r["ok"] is False and "expired" in r["note"] and got == []
    assert events(app, "question_expired")[-1]["id"] == old
    edits = [p for m, p in env.fake.sent if m == "editMessageText"]
    assert edits and "(expired" in edits[-1]["text"] and edits[-1]["reply_markup"] == {"inline_keyboard": []}


def test_default_expiry_setting_and_old_files_forgotten(app):
    app.settings.set("ask.expire_hours", 1)
    qid = app.ask.ask("Short-lived?")
    exp = dt.datetime.fromisoformat(app.ask.get(qid)["expires"])
    assert now() < exp <= now() + dt.timedelta(hours=1)
    app.ask.answer(qid, "sure", "telegram")
    f = app.paths.state / "ask" / f"{qid}.json"
    q = json.loads(f.read_text())
    q["answered"] = (now() - dt.timedelta(days=31)).isoformat()
    f.write_text(json.dumps(q))
    app.ask.sweep()
    assert not f.exists()


def test_hook_missing_or_failing_keeps_the_answer(app):
    a = app.ask.ask("x?", hook="gone.away")
    assert app.ask.answer(a, "fine", "telegram")["ok"]
    assert events(app, "question_hook_missing")[-1]["hook"] == "gone.away"

    def boom(q, a):
        raise RuntimeError("no")

    app.ask.hooks["t.boom"] = boom
    b = app.ask.ask("y?", hook="t.boom")
    assert app.ask.answer(b, "fine", "telegram")["ok"] and app.ask.get(b)["status"] == "answered"
    assert "RuntimeError" in events(app, "question_hook_failed")[-1]["error"]


def test_hook_note_is_shown(app):
    app.ask.hooks["t.note"] = lambda q, a: f"Saved {a} to your log."
    qid = app.ask.ask("What did you study?", hook="t.note")
    assert app.ask.answer(qid, "bayes", "telegram")["note"] == "Saved bayes to your log."


def test_ai_hook_starts_a_request(app, monkeypatch):
    seen = []
    monkeypatch.setattr(app.jobs, "submit", lambda prompt, **kw: seen.append((prompt, kw)) or "j1")
    qid = app.ask.ask(
        "What should the summary focus on?", hook="ask.ai", hook_payload={"prompt": "Summarise with focus: {answer}"}
    )
    assert app.ask.answer(qid, "proofs", "telegram")["note"] == "Got it; working on it."
    assert seen[0][0] == "Summarise with focus: proofs"
    q2 = app.ask.ask("Anything else?", hook="ask.ai", hook_payload={"prompt": "Do {answer}"})
    app.ask.answer(q2, "nothing new", "telegram")
    assert len(seen) == 1  # nothing new starts nothing


def test_recent_lists_settled_questions(app):
    a = app.ask.ask("x?", source="retro")
    app.ask.ask("y?", source="retro")
    app.ask.answer(a, "Apply", "telegram")
    assert [q["id"] for q in app.ask.recent(source="retro")] == [a]
    assert app.ask.recent(now() + dt.timedelta(minutes=1)) == []


def test_unknown_question(app):
    r = app.ask.answer("qnope1234", "yes", "app")
    assert r["ok"] is False and "no such question" in r["note"]
    assert app.ask.get("../../etc") is None


def test_retract_called_when_a_channel_offers_it(app):
    seen = []
    app.notifier.retract = lambda kind, ref: seen.append((kind, ref))
    qid = app.ask.ask("x?")
    app.ask.answer(qid, "later", "app")
    app.ask.answer(qid, "done", "app")
    assert seen == [("ask", qid), ("ask", qid)]


# -------------------------------------------------------------------------------------------- calls
@pytest.fixture
def calls(env):
    from kurooto.modules.calls import deploy

    env.app.settings.set("notify.desktop", False)
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls")
    return env.app.modules["calls"]


def test_calls_brief_tools_and_approvals(calls):
    app = calls.app
    names = {t.name for t in calls.tools()}
    assert {"answer_question", "answer_approval"} <= names
    from kurooto.core.tools import agent_tools

    assert not {"answer_question", "answer_approval"} & {t.name for t in agent_tools(app)}  # never for an AI
    assert "answer_question" in calls.config_template()["systemInstruction"]
    assert "open_questions" not in calls.pending()
    q = app.ask.ask("Which chapter?", choices=["3", "4"])
    a = app.ask.ask("Send the weekly summary to your notes repo?", kind="approval")
    brief = calls.run_tool("pending_items", {})["open_questions"]
    assert [x["id"] for x in brief] == [q, a] and brief[0]["choices"] == ["3", "4"]
    code, out = calls.handle_request("GET", "/tasks", b"")
    assert out["approvals"] == [{"id": a, "question": "Send the weekly summary to your notes repo?"}]
    assert calls.handle_request("GET", "/tasks", b"")[1]["approvals"] == []  # told once
    assert "use answer_question" in calls.run_tool("answer_approval", {"id": q, "decision": "approve"})
    assert calls.run_tool("answer_question", {"id": q, "answer": "4"}) == "Got it: 4"
    assert calls.run_tool("answer_approval", {"id": a, "decision": "deny"}) == "Deny."
    assert app.ask.get(a)["via"] == "call" and app.ask.pending() == []
    assert "open_questions" not in calls.pending()


def test_calls_brief_is_in_the_offline_state(calls):
    calls.app.ask.ask("What did you cover today?")
    st = calls.state_message()
    assert st["brief"]["pending_items"]["open_questions"][0]["question"] == "What did you cover today?"
    assert "answer_question" in st["offline"]["queue"]
