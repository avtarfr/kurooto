"""Learns from its own work (modules/learning.py): the tool log of a request, the search index of past requests, calls
and chats (/history, search_history, the Space keeper), skills from requests that took many steps, lessons from
corrections, and facts the nightly look back keeps. The AI's answers are faked."""

import datetime as dt
import json
import time

import pytest

from kurooto import providers
from kurooto.core import mcp, space
from kurooto.core.tools import agent_tools, run_tool
from kurooto.modules import learning as lrn
from kurooto.modules.remember import PICKED, help_file
from kurooto.modules.skills import load_skill, parse, user_dir
from kurooto.providers.base import Brain, Result, Task, Verdict
from kurooto.web import tools_api
from tests.fakes.openai import FakeOpenAI


class Worker(Brain):
    """An API brain that uses `steps` tools (list_notes) and then answers."""

    id, label, kind = "worker", "Worker", "api"

    def __init__(self, steps=6, answer="Done: the lab report is in lab/week-3."):
        self.steps, self.answer, self.tasks = steps, answer, []

    def available(self):
        return True, ""

    def run(self, task: Task) -> Result:
        self.tasks.append(task)
        for _ in range(self.steps):
            task.run_tool("list_notes", {"folder": ""})
        return Result(Verdict.OK, self.answer)


@pytest.fixture
def app(env, monkeypatch):
    env.app.settings.set("notify.desktop", False)
    worker = Worker()
    orig = providers.build
    monkeypatch.setattr(providers, "build", lambda a, w: worker if w == "worker" else orig(a, w))
    env.app.settings.set("brain.main", "worker")
    env.on("chat", "skills", "learning")
    env.app.worker = worker
    return env.app


def ask(app, text):
    """A request of yours, run to the end: its job."""
    jid = app.jobs.submit(text, title=text[:40])
    assert app.jobs.run_next("you") == jid
    return app.jobs.get(jid)


def judged(app, title_start):
    return [j for j in app.jobs.recent(20) if j.title.startswith(title_start)]


def ago(days):
    return dt.datetime.now().replace(microsecond=0) - dt.timedelta(days=days)


def buttons(fake):
    sent = [p for m, p in fake.sent if m == "sendMessage" and p.get("reply_markup")][-1]
    return [b["callback_data"] for row in sent["reply_markup"]["inline_keyboard"] for b in row]


SKILL = """NEW
```skill
---
name: weekly-lab-report
description: write the week's lab report from the lab notes
effort: medium
args: the week, e.g. week 3
internal: true
---
1. Read lab/$ARGUMENTS notes with read_note.
2. Write lab/report-$ARGUMENTS with write_note.
3. Reply with where it is.
```"""


# ------------------------------------------------------------------------------------------- the tool log
def test_a_requests_tool_uses_are_its_steps_for_api_and_agent_programs(app, env, monkeypatch):
    seen = []
    app.jobs.watchers.append(lambda job, result, info: seen.append((job.id, len(info["steps"]))))
    job = ask(app, "file my lab notes")
    assert seen == [(job.id, 6)] and app.jobs.steps == {}  # the log goes with the request
    assert app.jobs.usage(1)[0]["tool_calls"] == 6
    task = app.worker.tasks[-1]
    assert task.mcp_env[mcp.ENV_JOB] == job.id  # agent programs: `kurooto mcp` marks each use with the request

    # what `kurooto mcp` sends for an agent program, and what the local API makes of it
    sent = {}

    class Stub:
        def request(self, method, path, body=None):
            sent.update(body or {})
            return 200, {"ok": True, "result": "fine"}

    monkeypatch.setenv(mcp.ENV_JOB, "j123")
    mcp.Server(Stub(), None).call_tool({"name": "list_notes", "arguments": {}})
    assert sent["job"] == "j123" and sent["via"] == "mcp"
    jid = app.jobs.submit("another", title="another")
    assert app.jobs._claim("you") == jid  # running here: its steps are kept
    for _ in range(2):
        assert tools_api.post(app, "tools/call", {"name": "list_notes", "args": {}, "job": jid})[0] == 200
    tools_api.post(app, "tools/call", {"name": "list_notes", "args": {}, "job": "jnotours"})
    assert len(app.jobs.steps[jid]) == 2 and "jnotours" not in app.jobs.steps


# ---------------------------------------------------------------------------------------- the search index
def test_history_finds_past_requests_calls_and_chats_and_keeps_up(app, env):
    app.worker.steps = 0
    app.worker.answer = "The Fourier transform of a Gaussian is a Gaussian."
    ask(app, "what is the fourier transform of a gaussian")
    calls = app.paths.state / "calls" / "transcripts"
    calls.mkdir(parents=True)
    said = "you: remind me about the thermodynamics quiz\n"
    (calls / f"{ago(3):%Y-%m-%d-%H%M%S}.txt").write_text(said, encoding="utf-8")
    hist = app.paths.state / "chat" / "history.json"
    hist.parent.mkdir(parents=True, exist_ok=True)
    hist.write_text(json.dumps([{"user": "plan my topology revision", "assistant": "Sure.", "at": time.time()}]))

    out = env.say("/history fourier gaussian")
    assert "AI request" in out and "Gaussian" in out
    assert "call" in env.say("/history thermodynamics quiz") and "chat" in env.say("/history topology")
    assert env.say("/history 1d thermodynamics").startswith("Nothing found")  # that call was days ago
    assert app.modules["learning"].index.update() == 0  # nothing new: nothing added again
    (calls / f"{ago(1):%Y-%m-%d-%H%M%S}.txt").write_text("you: entropy question\n", encoding="utf-8")
    assert app.modules["learning"].index.update() == 1

    # the same search for the AI: agy, Claude Code and API brains all get it
    tools = agent_tools(app)
    assert "search_history" in {t.name for t in tools}
    found = run_tool(app, "search_history", {"query": "entropy"}, tools)
    assert found["hits"][0]["kind"] == "call"
    app.settings.set("learning.search", False)
    assert "search_history" not in {t.name for t in agent_tools(app)}
    assert "off" in env.say("/history entropy")


def test_the_space_keeper_counts_and_trims_the_index(app, env):
    idx = app.modules["learning"].index
    calls = app.paths.state / "calls" / "transcripts"
    calls.mkdir(parents=True)
    (calls / "2020-01-01-090000.txt").write_text("an old call about sourdough\n", encoding="utf-8")
    new = ago(2)
    (calls / f"{new:%Y-%m-%d-%H%M%S}.txt").write_text("a new call about sourdough\n", encoding="utf-8")
    idx.update()
    assert "search index of past requests" in space.footprint(app)
    items = [i for i in space.plan(app) if i.kind == "history"]
    assert len(items) == 1 and items[0].what.startswith("1 items older than")
    space.clean(app, items)
    hits = idx.search("sourdough")
    assert len(hits) == 1 and hits[0]["title"] == f"Call on {new:%a %d %b %H:%M}"
    assert not [i for i in space.plan(app) if i.kind == "history"]


# ---------------------------------------------------------------------------------- skills from experience
def test_a_request_with_many_steps_becomes_a_skill_with_undo(app, env):
    job = ask(app, "write this week's lab report from my lab notes, week 3")
    check = judged(app, "Worth a skill?")
    assert len(check) == 1
    c = check[0]
    assert c.lane == "chk" and c.effort_req == "low" and c.background
    assert "list_notes" in c.prompt and "week 3" in c.prompt and "journal:" in c.prompt  # steps and skills shown

    today = {"job": job.id, "title": job.title, "day": time.strftime("%Y-%m-%d")}
    app.jobs.then_actions["learning.skill"](c, Result(Verdict.OK, SKILL), today)
    f = user_dir(app) / "weekly-lab-report" / "SKILL.md"
    meta, body = parse(f.read_text(encoding="utf-8"))
    assert meta["learned"] == "true" and meta["learned_from"] == job.title and meta["learned_on"]
    assert "internal" not in meta and "$ARGUMENTS" in body
    s = load_skill(app, "weekly-lab-report")
    assert s is not None and s.source == "yours" and not s.internal
    told = env.fake.texts()[-1]
    assert told.startswith("Learned a skill: /weekly-lab-report, from today's request. /skills weekly-lab-report")
    undo = [b for b in buttons(env.fake) if b.startswith("lrn:")][0]
    assert env.press(undo) == "Removed the skill /weekly-lab-report."
    assert not f.exists() and env.press(undo) == "Undone already."

    # never a duplicate: the same skill again (or one that says what an existing one says) is left out
    app.jobs.then_actions["learning.skill"](c, Result(Verdict.OK, SKILL), {"job": job.id, "title": "x"})
    n = len(env.fake.texts())
    app.jobs.then_actions["learning.skill"](c, Result(Verdict.OK, SKILL.replace("weekly-lab-report", "lab-weekly")), {})
    assert len(env.fake.texts()) == n and not (user_dir(app) / "lab-weekly").exists()
    app.jobs.then_actions["learning.skill"](c, Result(Verdict.OK, "NONE: a one-off question"), {})
    assert len(env.fake.texts()) == n


def test_few_steps_or_parts_off_are_not_looked_at(app, env):
    app.worker.steps = 4
    ask(app, "a short one")
    app.settings.set("learning.skill_min_steps", 2)
    app.settings.set("learning.skills", False)
    ask(app, "skills part off")
    assert judged(app, "Worth a skill?") == []
    app.settings.set("learning.skills", True)
    app.disable("learning")
    ask(app, "feature off")
    assert judged(app, "Worth a skill?") == []
    env.on("learning")
    ask(app, "now it counts")
    assert len(judged(app, "Worth a skill?")) == 1
    background = app.jobs.submit("routine work", lane="bg")
    app.jobs.run_next("bg")
    assert app.jobs.get(background).status == "ok" and len(judged(app, "Worth a skill?")) == 1


def test_an_existing_skill_is_improved_instead_and_undo_puts_it_back(app, env):
    c = ask(app, "write today's journal")
    out = "IMPROVE journal\n- Start with the day's classes from the timetable.\n- Keep it under ten lines."
    app.jobs.then_actions["learning.skill"](c, Result(Verdict.OK, out), {"day": time.strftime("%Y-%m-%d")})
    mine = user_dir(app) / "journal" / "SKILL.md"
    text = mine.read_text(encoding="utf-8")
    assert "## Learned from experience" in text and "- Keep it under ten lines." in text
    assert load_skill(app, "journal").source == "yours"
    assert env.fake.texts()[-1].startswith("Improved a skill: /journal")
    env.press([b for b in buttons(env.fake) if b.startswith("lrn:")][0])
    assert not mine.exists() and load_skill(app, "journal").source == "shipped"


# ------------------------------------------------------------------------------------------- corrections
def run_skill(app, name="journal"):
    jid = app.modules["skills"].run(name, "today", reply_to=None)
    app.jobs.run_next("you")
    return app.jobs.get(jid)


def test_no_after_a_skills_answer_teaches_it_a_lesson_with_undo(app, env):
    app.worker.steps = 0
    run_skill(app)
    env.say("no, put the date in the title")
    lesson = judged(app, "A lesson for /journal?")
    assert len(lesson) == 1 and "put the date in the title" in lesson[0].prompt and lesson[0].lane == "chk"
    env.say("no, something else")  # one correction per answer
    assert len(judged(app, "A lesson for /journal?")) == 1

    app.jobs.then_actions["learning.lesson"](
        lesson[0], Result(Verdict.OK, "LESSON: Put the date in the title."), {"name": "journal"}
    )
    mine = user_dir(app) / "journal" / "SKILL.md"
    assert "## Lessons\n- Put the date in the title." in mine.read_text(encoding="utf-8")
    assert env.fake.texts()[-1].startswith("Lesson for /journal: Put the date in the title.")
    undo = [b for b in buttons(env.fake) if b.startswith("lrn:")][0]

    # your own edit since wins over the Undo
    mine.write_text(mine.read_text(encoding="utf-8") + "\nmy own line\n", encoding="utf-8")
    assert "changed since" in env.press(undo) and mine.exists()


def test_a_reply_to_a_skills_answer_counts_only_when_it_corrects(app, env):
    app.worker.steps = 0
    run_skill(app)
    env.reply_to_last("week 3")  # an answer to its question: carries on, nothing to learn
    assert judged(app, "A lesson for /journal?") == []
    run_skill(app)
    env.reply_to_last("you forgot the deadlines section")
    assert len(judged(app, "A lesson for /journal?")) == 1


def test_a_careful_rewrite_keeps_the_header_and_a_bad_one_is_refused(app, env):
    from kurooto.modules.skills import load_skill as ls

    old = open(ls(app, "journal").path, encoding="utf-8").read()
    fixed = old.replace("journal", "journal", 1) + "\n(One step said better.)\n"
    job = run_skill(app)
    good = f"REWRITE\n```skill\n{fixed}```"
    app.jobs.then_actions["learning.lesson"](job, Result(Verdict.OK, good), {"name": "journal"})
    mine = user_dir(app) / "journal" / "SKILL.md"
    assert "(One step said better.)" in mine.read_text(encoding="utf-8")
    assert env.fake.texts()[-1].startswith("Rewrote the step of /journal")
    mine.unlink()
    n = len(env.fake.texts())
    bad = "REWRITE\n```skill\n---\nname: journal\ndescription: x\n---\nDo it.\n```"  # most of the skill gone
    app.jobs.then_actions["learning.lesson"](job, Result(Verdict.OK, bad), {"name": "journal"})
    assert not mine.exists() and len(env.fake.texts()) == n


# -------------------------------------------------------------------------------------- worth remembering
@pytest.fixture
def ai(app):
    fake = FakeOpenAI()
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"medium": "m", "low": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    yield fake
    fake.close()


def test_the_look_back_keeps_facts_you_stated_with_undo(app, env, ai):
    env.on("remember", "retro")
    app.jobs.submit("I'm a morning person, plan my study blocks before noon", title="plan")
    app.jobs.run_next("you")
    ai.answer = json.dumps(
        {
            "proposals": [],
            "remember": [
                "I'm a morning person",
                "My sister lives in Pune",  # other people: never
                "My bank PIN is 1234",  # money and passwords: never
                "I prefer short answers",
                "I like plans as checklists",
                "One too many",
            ],
        }
    )
    app.modules["retro"].run()
    prompt = ai.requests[-1]["messages"][-1]["content"]
    assert '"chats"' in prompt and "morning person" in prompt and '"remember"' in prompt
    note = help_file(app).read_text(encoding="utf-8")
    assert f"## {PICKED}" in note and "- I'm a morning person (" in note and "- I prefer short answers (" in note
    assert "sister" not in note and "PIN" not in note and "One too many" not in note  # at most remember_max (3)
    told = env.fake.texts()[-1]
    assert told.startswith("Kept from today's chats and calls") and "1. I'm a morning person" in told
    undo = [b for b in buttons(env.fake) if b.startswith("lrn:")]
    assert len(undo) == 3
    assert env.press(undo[0]) == "Taken out of your how-to-help-me note."
    assert "morning person" not in help_file(app).read_text(encoding="utf-8")

    # the part off: the look back neither reads the chats nor keeps anything
    app.settings.set("learning.remember", False)
    app.modules["retro"].run()
    assert '"chats"' not in ai.requests[-1]["messages"][-1]["content"]


def test_stamp_and_asked():
    out = lrn.stamp("---\nname: x\ninternal: true\nlearned: false\n---\nDo it.\n", "lab-report", 'say "hi"\n', "d")
    meta, body = parse(out)
    assert meta == {"name": "lab-report", "learned": "true", "learned_from": "say hi", "learned_on": "d"}
    assert body == "Do it.\n"
    assert lrn.asked("Previous conversation:\nUser: a\n\nCurrent request:\nwhat now") == "what now"
    assert lrn.asked("Skill: x\n\nsteps\n\nHow to work (the rules for every skill):\n- ...") == "Skill: x\n\nsteps"
