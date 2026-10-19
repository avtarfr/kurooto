"""The learning loop: remember (how-to-help-me.md and the AI's context), observations (/observe, /observing, the
intent and call tool) and the nightly look back (evidence, the five proposal kinds, Apply / Observe longer / No)."""

import datetime as dt
import json

import pytest

from kurooto.core.clock import now
from kurooto.core.tools import agent_tools, run_tool
from kurooto.modules import retro as retro_mod
from kurooto.modules.remember import HELP_NOTE, Remember, help_brief, sensitive
from kurooto.providers.base import Result, Verdict
from kurooto.providers.context import headless_context
from tests.fakes.openai import FakeOpenAI


@pytest.fixture
def app(env):
    if "remember" not in env.app.modules:  # the coordinator adds it to the catalog
        env.app.modules["remember"] = Remember(env.app)
    env.app.settings.set("notify.desktop", False)
    return env.app


@pytest.fixture
def ai(app):
    fake = FakeOpenAI()
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"medium": "m", "low": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    fake.answer = json.dumps({"proposals": []})
    yield fake
    fake.close()


def help_text(app):
    return (app.workspace / HELP_NOTE).read_text(encoding="utf-8")


def last_prompt(ai):
    return ai.requests[-1]["messages"][-1]["content"]


def propose(ai, *proposals, **extra):
    ai.answer = json.dumps({"noticed": "", "findings": [], "proposals": list(proposals), **extra})


def retro_questions(app):
    return app.ask.pending(source="retro")


def question(app, words):
    return next(q for q in retro_questions(app) if words in q["text"])


# --------------------------------------------------------------------------------------------- remember
def test_remember_keeps_lines_and_refuses_health_money_and_passwords(app, env):
    env.on("remember")
    assert env.say("/remember I hate calls before 8").startswith(f"Noted in {HELP_NOTE}")
    text = help_text(app)
    assert text.startswith("# How to help me") and "## You told me" in text
    assert f"- I hate calls before 8 ({now():%Y-%m-%d})" in text
    assert env.say("/remember i hate calls before 8.") == "I know that already."
    for fact in ("my bank pin number is 1234", "my password is hunter2", "I take insulin at 9"):
        assert env.say(f"/remember {fact}").startswith("I'd rather not keep that")
    assert "hunter2" not in help_text(app) and "insulin" not in help_text(app)
    assert sensitive("I have ADHD") == "health" and sensitive("I like short answers") is None
    assert [e["what"] for e in app.events.tail(50, {"remember_refused"})] == ["money", "credentials", "health"]
    assert "I hate calls before 8" in env.say("/remember")  # no argument: what it keeps


def test_remember_intent_appends_and_your_edits_win(app, env):
    env.on("remember")
    f = app.workspace / HELP_NOTE
    f.parent.mkdir(parents=True, exist_ok=True)
    mine = "# How I work\n\nI write my own notes here.\n\n## You told me\n- Keep answers short (my own words)\n"
    mine += "\n## Mine\nX\n"
    f.write_text(mine, encoding="utf-8")
    assert env.say("remember that I like a plan before 9").startswith("Noted")
    text = help_text(app)
    assert text.startswith("# How I work\n\nI write my own notes here.\n\n## You told me\n- Keep answers short")
    assert text.index("I like a plan before 9") < text.index("## Mine") and text.endswith("## Mine\nX\n")
    assert env.say("remember: keep answers short (my own words)") == "I know that already."
    env.say("remember to buy milk")  # a reminder, not a preference: not this intent
    assert "milk" not in help_text(app)


def test_how_to_help_me_goes_into_every_ai_request_capped(app):
    assert "how-to-help-me" not in headless_context(app)
    app.modules["remember"].remember("Call me Sam")
    ctx = headless_context(app)
    assert f"How they like to be helped ({HELP_NOTE}" in ctx and "- Call me Sam" in ctx
    assert "What Kurooto has learned" not in ctx  # the standard intro is left out
    f = app.workspace / HELP_NOTE
    f.write_text(f.read_text(encoding="utf-8") + "".join(f"- line {i} " + "x" * 80 + "\n" for i in range(200)))
    brief = help_brief(app)
    assert len(brief) < 1600 and brief.endswith(f"(…the rest is in {HELP_NOTE})")
    f.write_text("# How to help me\n\n## You told me\n", encoding="utf-8")
    assert help_brief(app) == ""  # only headings: nothing to send


def test_remember_and_observe_are_tools_for_calls_and_unattended_runs(app, env, ai):
    env.on("chat", "remember", "retro")
    names = [t.name for t in agent_tools(app)]
    assert "remember" in names and "observe" in names
    assert run_tool(app, "remember", {"fact": "no calls during lunch"}).startswith("Noted")
    assert "No calls during lunch" in help_text(app)
    assert run_tool(app, "remember", {"fact": "my salary is 10"}).startswith("I'd rather not")
    assert run_tool(app, "observe", {"what": "whether I sleep better after a walk", "days": "10"}).startswith(
        "Watching until"
    )
    o = app.modules["retro"].observations()[-1]
    assert o["what"] == "whether I sleep better after a walk"
    assert dt.datetime.fromisoformat(o["until"]).date() == (now() + dt.timedelta(days=10)).date()
    calls = app.modules["calls"]
    assert {"remember", "observe"} <= {t.name for t in calls.tools()}


# ----------------------------------------------------------------------------------------- observations
def test_split_length():
    s = retro_mod.split_length
    assert s("whether I study better before noon for 2 weeks", 7) == ("whether I study better before noon", 14)
    assert s("my sleep over the next three days", 7) == ("my sleep", 3)
    assert s("whether lunch walks help for a month", 7) == ("whether lunch walks help", 30)
    assert s("whether I focus better.", 7) == ("whether I focus better", 7)


def test_observe_command_intent_and_stop_buttons(app, env, ai):
    env.on("chat", "retro")
    out = env.say("/observe whether I study better before noon for 2 weeks")
    assert out.startswith(f"Watching until {now() + dt.timedelta(days=14):%a %d %b}: whether I study better")
    assert env.say("observe whether I focus better after a walk for 3 days").startswith("Watching until")
    assert env.say("keep an eye on how often I skip the gym").startswith("Watching until")
    obs = app.modules["retro"].observations()
    assert [o["what"] for o in obs] == [
        "whether I study better before noon",
        "whether I focus better after a walk",
        "how often I skip the gym",
    ]
    assert [o["source"] for o in obs] == ["you"] * 3
    env.say("/observing")
    msgs = [p for m, p in env.fake.sent if m == "sendMessage" and p.get("reply_markup")][-3:]
    assert msgs[0]["text"].endswith("whether I study better before noon")
    stop = msgs[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert stop == f"obs:{obs[0]['id']}:stop"
    assert env.press(stop).startswith("Stopped watching: whether I study better")
    assert env.press(stop) == "That isn't being watched any more."
    assert [o["status"] for o in app.modules["retro"].observations()] == ["stopped", "active", "active"]


# ----------------------------------------------------------------------------------------- the look back
def test_evidence_has_events_answers_transcripts_and_journal(app, env, ai):
    env.on("chat", "retro")
    app.events.emit("checkin_moved", name="evening", from_time="22:00", to_time="21:30", day="today", via="intent")
    app.events.emit("capture_skipped", subject="Linear Algebra", why="exam")
    qid = app.ask.ask("Which chapter is the quiz on?", choices=["three", "four"], source="study")
    app.ask.answer(qid, "four", "call")
    tr = app.paths.state / "calls" / "transcripts"
    tr.mkdir(parents=True)
    (tr / f"{now():%Y-%m-%d-%H%M%S}.txt").write_text("# evening check-in\nyou: call me at nine tomorrow\n")
    (tr / "2020-01-01-090000.txt").write_text("you: an old call\n")
    j = app.workspace / "journal" / f"{now():%Y-%m-%d}.md"
    j.parent.mkdir(parents=True)
    j.write_text("# Today\nGot the eigenvalue sheet done.\n")
    app.modules["remember"].remember("Short answers please")
    assert app.modules["retro"].run() == 0
    prompt = last_prompt(ai)
    assert prompt.startswith("You are the learning loop of a personal assistant.")  # the shipped retro skill
    ctx = json.loads(prompt.split("INPUT (JSON):\n", 1)[1])
    assert "checkin_moved name=evening from_time=22:00 to_time=21:30" in ctx["evidence"]
    assert "capture_skipped subject=Linear Algebra why=exam" in ctx["evidence"]
    assert "Questions: asked 1, answered 1" in ctx["evidence"] and "by channel call 1" in ctx["evidence"]
    assert ctx["answers"][0]["question"] == "Which chapter is the quiz on?" and ctx["answers"][0]["answer"] == "four"
    assert "call me at nine tomorrow" in ctx["call_transcripts"] and "an old call" not in ctx["call_transcripts"]
    assert "eigenvalue sheet" in ctx["journal"]
    assert "Short answers please" in ctx["how_to_help_me"]
    assert ctx["settings"]["checkins.times.evening"] == {"means": "time HH:MM or null", "now": "22:00"}
    assert "retro" in ctx["skills"] and ctx["max_proposals"] == 3
    app.settings.set("retro.transcripts", False)
    app.settings.set("retro.journal", False)
    app.modules["retro"].run()
    ctx = json.loads(last_prompt(ai).split("INPUT (JSON):\n", 1)[1])
    assert ctx["call_transcripts"] == "" and ctx["journal"] == ""


def test_each_kind_of_proposal_applies_only_after_a_tap(app, env, ai):
    env.on("chat", "checkins", "retro")
    app.settings.set("retro.max_proposals", 5)
    propose(
        ai,
        {"type": "setting", "key": "checkins.times.evening", "value": "21:30", "text": "Move the check-in?"},
        {"type": "profile", "line": "Prefers a plan before 9", "text": "Add this?", "evidence": "said so 3 times"},
        {"type": "observe", "observe": "whether quizzes go better in the morning", "days": 10, "text": "Watch?"},
        {"type": "idea", "idea": "A Sunday reading list from the week's notes", "text": "Add to ideas?"},
        {"type": "skill", "skill": "retro", "change": "Propose at most one setting a night", "text": "Change it?"},
    )
    assert app.modules["retro"].run() == 5
    qs = retro_questions(app)
    assert [q["choices"] for q in qs] == [["Apply", "Observe longer", "No"]] * 5
    profile = question(app, "Prefers a plan")
    assert "Why: said so 3 times" in profile["text"]
    assert 'The line for about-me/how-to-help-me.md: "Prefers a plan before 9"' in profile["text"]
    assert app.settings.get("checkins.times.evening") == "22:00"  # nothing until you tap
    assert not (app.workspace / HELP_NOTE).exists() and not (app.workspace / "kurooto" / "ideas.md").exists()
    answers = [app.ask.answer(q["id"], "Apply", "telegram") for q in qs]
    assert all(a["ok"] for a in answers)
    assert app.settings.get("checkins.times.evening") == "21:30"
    assert "## Learned in the nightly look back\n- Prefers a plan before 9 (" in help_text(app)
    obs = app.modules["retro"].observations()[-1]
    assert obs["what"] == "whether quizzes go better in the morning" and obs["source"] == "retro"
    ideas = (app.workspace / "kurooto" / "ideas.md").read_text(encoding="utf-8")
    assert ideas.startswith("# Ideas") and "- [ ] A Sunday reading list from the week's notes (" in ideas
    job = app.jobs.recent(1)[0]
    assert job.title == "Skill change: retro" and "Propose at most one setting a night" in job.prompt
    assert sorted(e["type"] for e in app.events.tail(50, {"retro_applied"})) == [
        "idea",
        "observe",
        "profile",
        "setting",
    ]


def test_skill_change_is_shown_then_saved_with_a_backup(app, env, ai):
    env.on("chat", "retro")
    r = app.modules["retro"]
    propose(ai, {"type": "skill", "skill": "retro", "change": "Say hello first", "text": "Change it?"})
    assert r.run() == 1
    q = retro_questions(app)[0]
    assert app.ask.answer(q["id"], "Apply", "telegram")["ok"]
    pid = q["hook_payload"]["pid"]
    old = r._skill_text("retro")
    new = old.replace("You are the learning loop", "Say hello first. You are the learning loop")
    r._skill_ready(None, Result(Verdict.OK, f"Here you go\n===BEGIN===\n{new}===END===\n"), {"pid": pid})
    msg = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert "+Say hello first. You are the learning loop" in msg["text"] and "-You are the learning loop" in msg["text"]
    assert [b["text"] for b in msg["reply_markup"]["inline_keyboard"][0]] == ["Save", "Discard"]
    mine = app.workspace / "kurooto" / "skills" / "retro" / "SKILL.md"
    assert not mine.exists()  # nothing written before Save
    assert env.press(f"retro:{pid}:save").startswith("Saved your retro skill")
    assert mine.read_text(encoding="utf-8") == new
    backups = list((app.paths.data / "backups" / "skills").glob("retro-*.md"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == old
    assert r.instructions()[0].startswith("Say hello first.")  # your copy wins from now on
    assert app.events.tail(5, {"skill_edited"})[-1]["name"] == "retro"


def test_skill_change_never_overwrites_your_own_edits(app, env, ai):
    env.on("chat", "retro")
    r = app.modules["retro"]
    propose(ai, {"type": "skill", "skill": "retro", "change": "Be brief", "text": "Change it?"})
    r.run()
    q = retro_questions(app)[0]
    app.ask.answer(q["id"], "Apply", "telegram")
    pid = q["hook_payload"]["pid"]
    mine = app.workspace / "kurooto" / "skills" / "retro" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("---\nname: retro\n---\nMy own instructions.\n", encoding="utf-8")  # edited meanwhile
    r._skill_ready(None, Result(Verdict.OK, "===BEGIN===\n---\nname: retro\n---\nAI version\n===END==="), {"pid": pid})
    assert r.answer(pid, "Save").startswith("Your retro skill changed in the meantime")
    assert mine.read_text(encoding="utf-8") == "---\nname: retro\n---\nMy own instructions.\n"
    # an AI answer that lost the header, or changed nothing, is never offered
    propose(ai, {"type": "skill", "skill": "retro", "change": "Be briefer", "text": "Change it?"})
    r.run()
    q = retro_questions(app)[0]
    app.ask.answer(q["id"], "Apply", "telegram")
    r._skill_ready(None, Result(Verdict.OK, "no header here"), {"pid": q["hook_payload"]["pid"]})
    assert "lost the skill's header" in [p for m, p in env.fake.sent if m == "sendMessage"][-1]["text"]
    assert r.answer(q["hook_payload"]["pid"], "Save") == "That suggestion is gone."


def test_no_keeps_an_idea_away_for_30_days(app, env, ai):
    env.on("chat", "checkins", "retro")
    r = app.modules["retro"]
    prop = {"type": "setting", "key": "checkins.times.evening", "value": "21:30", "text": "Move it?"}
    propose(ai, prop)
    assert r.run() == 1
    q = retro_questions(app)[0]
    out = app.ask.answer(q["id"], "No", "telegram")
    assert out["ok"] and app.settings.get("checkins.times.evening") == "22:00"
    propose(ai, {**prop, "value": "21:15"})  # the same idea, a different value
    assert r.run() == 0
    state = json.loads(r.state_file.read_text())
    state["rejected"][0]["date"] = (now() - dt.timedelta(days=31)).isoformat()
    r.state_file.write_text(json.dumps(state))
    assert r.run() == 1
    ctx = json.loads(last_prompt(ai).split("INPUT (JSON):\n", 1)[1])
    assert ctx["declined_recently"] == []
    # reworded profile lines count as the same idea too
    app.ask.answer(question(app, "Move it?")["id"], "No", "telegram")
    propose(ai, {"type": "profile", "line": "Likes a short plan before 9 am", "text": "Add?"})
    assert r.run() == 1
    app.ask.answer(question(app, "Likes a short plan")["id"], "No", "telegram")
    propose(ai, {"type": "profile", "line": "Likes a short plan before 9", "text": "Add this line?"})
    assert r.run() == 0


def test_observe_longer_waits_then_reports_a_finding(app, env, ai):
    env.on("chat", "retro")
    r = app.modules["retro"]
    prop = {"type": "profile", "line": "Studies better before noon", "text": "Add?", "evidence": "4 of 5 sessions"}
    propose(ai, prop)
    assert r.run() == 1
    q = retro_questions(app)[0]
    app.ask.answer(q["id"], "observe 14", "telegram")
    o = r.observations()[-1]
    assert o["source"] == "retro" and o["proposal"] == {"type": "profile", "main": "Studies better before noon"}
    assert (dt.datetime.fromisoformat(o["until"]) - now()).days in (13, 14)
    assert r.run() == 0  # watched first: not proposed again yet
    ctx = json.loads(last_prompt(ai).split("INPUT (JSON):\n", 1)[1])
    assert ctx["observing"][0]["what"] == "Studies better before noon" and ctx["observations_ended"] == []
    items = r.observations()
    items[-1]["until"] = (now() - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
    r.obs_file.write_text(json.dumps(items))
    propose(ai, prop, findings=[{"id": o["id"], "finding": "Mornings went better on 9 of 12 days."}])
    assert r.run() == 1  # the window is over: reported, and it may be proposed again
    ctx = json.loads(last_prompt(ai).split("INPUT (JSON):\n", 1)[1])
    assert ctx["observations_ended"] == [
        {"id": o["id"], "what": "Studies better before noon", "since": o["created"][:10]}
    ]
    found = [p["text"] for m, p in env.fake.sent if m == "sendMessage" and "What I found about" in p["text"]]
    assert found and found[-1].endswith("Mornings went better on 9 of 12 days.")
    assert r.observations()[-1]["status"] == "ended"


def test_bad_proposals_are_dropped(app, env, ai):
    env.on("chat", "retro")
    app.settings.set("retro.max_proposals", 9)
    propose(
        ai,
        {"type": "setting", "key": "telegram.chat_id", "value": 1, "text": "sneaky"},
        {"type": "setting", "key": "deadlines.ping_h", "value": "lots"},
        {"type": "setting", "key": "deadlines.ping_h", "value": True},
        {"type": "setting", "key": "checkins.times.evening", "value": "25:00"},
        {"type": "setting", "key": "checkins.times.evening", "value": "22:00"},  # that's what it is already
        {"type": "profile", "line": "Takes medication at 8", "text": "Add?"},
        {"type": "skill", "skill": "no-such-skill", "change": "x", "text": "?"},
        {"type": "skill", "skill": "retro", "change": "", "text": "?"},
        {"type": "delete_notes", "text": "?"},
        "not even a dict",
    )
    assert app.modules["retro"].run() == 0
    ai.answer = "I couldn't decide."
    assert app.modules["retro"].run() == 0
    assert app.events.tail(1, {"retro_failed"})[-1]["reason"] == "unreadable"


def test_buttons_without_the_questions_service_and_old_suggestions(app, env, ai, monkeypatch):
    env.on("chat", "checkins", "retro")
    r = app.modules["retro"]
    monkeypatch.setattr(app, "ask", None)
    propose(ai, {"type": "setting", "key": "capture.delay_min", "value": 5, "text": "Wait 5 minutes?"})
    assert r.run() == 1
    msg = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    row = msg["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["Apply", "Observe longer", "No"]
    assert env.press(row[1]["callback_data"]).startswith("OK, I'll keep watching for 7 days")
    assert env.press(row[0]["callback_data"]) == "That suggestion is gone."
    # a suggestion sent by 0.1.0 (Approve / Skip) still works after the update
    r.file.write_text(json.dumps({"abc": {"key": "quiz.per_session", "value": 5, "why": "w", "at": "x"}}))
    assert env.press("retro:abc:yes") == "Done: quiz.per_session = 5."
    assert app.settings.get("quiz.per_session") == 5


def test_tunable_settings_can_be_extended(app, env, ai):
    assert retro_mod.valid("time HH:MM", "07:30") and not retro_mod.valid("time HH:MM", None)
    assert retro_mod.valid("time HH:MM or null", None) and not retro_mod.valid("time HH:MM", "7:30")
    assert retro_mod.valid("on or off (true/false)", False) and not retro_mod.valid("(true/false)", 1)
    assert retro_mod.valid("tone (one of: brief, chatty)", "brief") and not retro_mod.valid("(one of: a, b)", "c")
    assert retro_mod.valid("(number)", 3) and not retro_mod.valid("(number)", 0) and not retro_mod.valid("x", True)
    env.on("chat", "retro")
    monkeypatch_key = "weekly.example_flag"
    retro_mod.tunable(monkeypatch_key, "an example (true/false)")
    try:
        propose(ai, {"type": "setting", "key": monkeypatch_key, "value": True, "text": "Turn it on?"})
        assert app.modules["retro"].run() == 1
    finally:
        retro_mod.TUNABLE.pop(monkeypatch_key, None)


def test_lookback_command_shows_the_last_run(app, env, ai):
    env.on("chat", "retro")
    assert env.say("/lookback").startswith("No look back yet; the next is at daily 23:50")
    propose(ai, noticed="You answered most questions within 10 minutes.")
    app.modules["retro"].run()
    out = env.say("/lookback")
    assert "0 suggestion(s), 0 finding(s)" in out and out.endswith("within 10 minutes.")
