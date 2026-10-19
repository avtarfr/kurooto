"""The shared tools: the function-calling loop for API brains, the notes tools' safety, which tools unattended AI
runs get, and the local API that lists and runs them."""

import json
import os
import sys

import pytest

from kurooto.app import App
from kurooto.core import tools as T
from kurooto.modules.base import Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.providers import openai_compat
from kurooto.providers.base import Task, Verdict
from kurooto.providers.context import headless_context
from kurooto.providers.openai_compat import OpenAICompat
from kurooto.web.api import Api
from tests.fakes.openai_tools import ScriptedOpenAI, call


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


def brain(fake):
    return OpenAICompat("custom", fake.key, base_url=fake.base, models={"low": "m", "medium": "m", "high": "m"})


def echo_tools(log):
    def run(name):
        return lambda a: log.append((name, a)) or f"{name} done"

    return [
        Tool("add_reminder", "a reminder", run("add_reminder"), {"when": arg(), "what": arg()}, ("when", "what")),
        Tool("weekly_summary", "the week", run("weekly_summary")),
    ]


def task_with(tools, log, **kw):
    def run_tool(name, args):
        t = next((t for t in tools if t.name == name), None)
        return t.run(args) if t else f"There's no {name} tool"

    return Task(prompt="remind me at 9 to call Sam", tools=tools, run_tool=run_tool, timeout_s=300, **kw)


# ---------------------------------------------------------------------------------------- the tool loop
def test_tool_loop_runs_several_rounds_and_answers():
    log = []
    fake = ScriptedOpenAI(
        [
            {"content": None, "tool_calls": [call("add_reminder", {"when": "21:00", "what": "call Sam"}, "a")]},
            {"tool_calls": [call("weekly_summary", {}, "b"), call("add_reminder", {"when": "9", "what": "x"}, "c")]},
            {"content": "Done: reminder at 21:00."},
        ]
    )
    try:
        tools = echo_tools(log)
        r = brain(fake).run(task_with(tools, log, context="be brief"))
    finally:
        fake.close()
    assert r.verdict == Verdict.OK and r.text == "Done: reminder at 21:00."
    assert [n for n, _ in log] == ["add_reminder", "weekly_summary", "add_reminder"]
    assert log[0][1] == {"when": "21:00", "what": "call Sam"}
    assert r.usage["tool_calls"] == 3 and r.usage["tools_used"] == ["add_reminder", "weekly_summary"]
    first, last = fake.requests[0], fake.requests[-1]
    decl = {d["function"]["name"]: d["function"] for d in first["tools"]}
    assert decl["add_reminder"]["parameters"]["required"] == ["when", "what"]
    assert "parameters" not in decl["weekly_summary"]  # Gemini refuses an empty parameters object
    msgs = last["messages"]
    assert msgs[0] == {"role": "system", "content": "be brief"}
    assert msgs[2]["role"] == "assistant" and msgs[2]["tool_calls"][0]["id"] == "a"
    assert msgs[3] == {"role": "tool", "tool_call_id": "a", "content": "add_reminder done"}
    assert [m["tool_call_id"] for m in msgs if m["role"] == "tool"] == ["a", "b", "c"]


def test_bad_json_arguments_are_sent_back_not_run():
    log = []
    fake = ScriptedOpenAI(
        [
            {"tool_calls": [call("add_reminder", '{"when": "21:00", "what"', "a")]},
            {"tool_calls": [call("add_reminder", '["not", "an object"]', "b")]},
            {"content": "Sorry, couldn't."},
        ]
    )
    try:
        r = brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    assert r.verdict == Verdict.OK and log == []
    tool_msgs = [m for m in fake.requests[-1]["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and all("weren't a JSON object" in m["content"] for m in tool_msgs)


def test_missing_call_ids_are_filled_in():
    log = []
    fake = ScriptedOpenAI([{"tool_calls": [call("weekly_summary", {}, None)]}, {"content": "ok"}])
    try:
        brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    msgs = fake.requests[-1]["messages"]
    cid = msgs[-2]["tool_calls"][0]["id"]
    assert cid and msgs[-1]["tool_call_id"] == cid


def test_rate_limit_waits_once_then_retries():
    log = []
    fake = ScriptedOpenAI(
        [("http", 429, {"error": {"message": "RESOURCE_EXHAUSTED"}}, {"Retry-After": "1"}), {"content": "Paris."}]
    )
    try:
        r = brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    assert r.verdict == Verdict.OK and r.text == "Paris." and len(fake.requests) == 2


def test_rate_limit_twice_is_reported():
    log = []
    fake = ScriptedOpenAI([("http", 429, {"error": {"message": "quota"}}, {"Retry-After": "1"})])
    try:
        r = brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    assert r.verdict == Verdict.RATE_LIMITED and len(fake.requests) == 2


def test_max_rounds_then_it_must_answer(monkeypatch):
    monkeypatch.setattr(openai_compat, "MAX_ROUNDS", 3)
    log = []
    fake = ScriptedOpenAI([{"tool_calls": [call("weekly_summary", {}, "x")]}] * 3 + [{"content": "Here's the week."}])
    try:
        r = brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    assert r.verdict == Verdict.OK and r.text == "Here's the week." and len(log) == 3
    last = fake.requests[-1]
    assert last["tool_choice"] == "none" and last["messages"][-1]["content"] == openai_compat.ENOUGH
    assert all("tool_choice" not in q for q in fake.requests[:-1])


def test_max_rounds_with_no_answer_is_an_error(monkeypatch):
    monkeypatch.setattr(openai_compat, "MAX_ROUNDS", 2)
    log = []
    fake = ScriptedOpenAI([{"tool_calls": [call("weekly_summary", {}, "x")]}])
    try:
        r = brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    assert r.verdict == Verdict.ERROR and "still calling tools" in r.detail and len(fake.requests) == 3


def test_a_model_without_tools_answers_without_them():
    log = []
    fake = ScriptedOpenAI([("http", 400, {"error": "registry/gemma:2b does not support tools"}), {"content": "Hi."}])
    try:
        r = brain(fake).run(task_with(echo_tools(log), log))
    finally:
        fake.close()
    assert r.verdict == Verdict.OK and r.text == "Hi." and r.usage["tools"] == "unsupported"
    assert "tools" in fake.requests[0] and "tools" not in fake.requests[1]


def test_no_tools_no_loop():
    fake = ScriptedOpenAI([{"content": "plain"}])
    try:
        r = brain(fake).run(Task(prompt="hi"))
    finally:
        fake.close()
    assert r.text == "plain" and "tools" not in fake.requests[0]


# ---------------------------------------------------------------------------------------- notes tools
@pytest.fixture
def notes(app):
    return T.NoteTools(app), app.workspace


def run(nt, name, **args):
    return next(t for t in nt.tools() if t.name == name).run(args)


@pytest.mark.parametrize(
    "slug",
    [
        "../outside",
        "a/../../outside",
        "..",
        ".hidden/x",
        "a/.git/config",
        "con",
        "aux.txt",
        "a:b",
        "C:\\Windows\\x",
        "x?y",
        "a/./b",
        "",
        "  ",
    ],
)
def test_unsafe_note_names(notes, slug):
    nt, root = notes
    assert T.note_path(root, slug, must_exist=False) is None
    assert "usable note name" in run(nt, "write_note", slug=slug, text="hi")


def test_names_are_notes_inside_the_folder(notes, tmp_path):
    nt, root = notes
    assert T.note_path(root, "inbox/idea", False) == (root / "inbox" / "idea.md").resolve()
    assert T.note_path(root, "/inbox/idea.md", False) == (root / "inbox" / "idea.md").resolve()
    assert T.note_path(root, "inbox\\idea", False) == (root / "inbox" / "idea.md").resolve()
    assert run(nt, "write_note", slug="plan.txt", text="x") == "Created plan.txt."
    assert (root / "plan.txt.md").is_file() and not (root / "plan.txt").exists()  # always a .md note


@pytest.mark.skipif(os.name == "nt", reason="symlinks need extra rights on Windows")
def test_a_link_out_of_the_folder_is_refused(notes, tmp_path):
    nt, root = notes
    secret = tmp_path / "secret.md"
    secret.write_text("private", encoding="utf-8")
    (root / "linked.md").symlink_to(secret)
    assert T.note_path(root, "linked", must_exist=True) is None
    assert run(nt, "read_note", slug="linked") == 'No note "linked".'
    assert "usable" in run(nt, "add_to_note", slug="linked", text="x") and secret.read_text() == "private"


def test_write_note_creates_only(notes, app):
    nt, root = notes
    assert run(nt, "write_note", slug="inbox/idea", text="# Idea\n\nGrow basil.") == "Created inbox/idea."
    text = (root / "inbox" / "idea.md").read_text(encoding="utf-8")
    assert text.startswith("---\nmade_by: Kurooto\n") and text.endswith("Grow basil.\n")
    assert "exists already" in run(nt, "write_note", slug="inbox/idea", text="other")
    assert (root / "inbox" / "idea.md").read_text(encoding="utf-8") == text
    assert "Nothing to write" in run(nt, "write_note", slug="inbox/b", text="  ")
    with pytest.raises(FileExistsError):
        T.write_note_file(root / "inbox" / "idea.md", "x", create=True)
    assert any(e["kind"] == "note_written" for e in app.events.tail(20))


MINE = """---
aliases: [plan]
# not a heading
---
# Term plan

## Goals
- pass linear algebra

```python
## Goals
# a comment
```

## Done
- [x] enrol

### Notes
x
"""


def test_add_to_a_section_keeps_everything(notes):
    nt, root = notes
    (root / "plan.md").write_text(MINE, encoding="utf-8")
    assert run(nt, "add_to_note", slug="plan", text="- read chapter 3", section="goals") == "Added to plan."
    new = (root / "plan.md").read_text(encoding="utf-8")
    # the code block belongs to Goals (the "## Goals" inside it isn't a heading): the line goes after it
    assert new == MINE.replace("# a comment\n```\n", "# a comment\n```\n- read chapter 3\n")
    run(nt, "add_to_note", slug="plan", text="- [x] buy books", section="## Done")
    new = (root / "plan.md").read_text(encoding="utf-8")
    assert new.index("- [x] buy books") > new.index("### Notes")  # Done ends where a same-level heading would
    run(nt, "add_to_note", slug="plan", text="Week 1 went fine.", section="Log")
    assert (root / "plan.md").read_text(encoding="utf-8").endswith("\n\n## Log\nWeek 1 went fine.\n")
    run(nt, "add_to_note", slug="plan", text="The end.")
    final = (root / "plan.md").read_text(encoding="utf-8")
    assert final.endswith("Week 1 went fine.\n\nThe end.\n")
    for line in MINE.splitlines():  # nothing of theirs was changed or lost
        assert line in final


def test_add_to_section_edge_cases():
    assert T.add_to_section("", "Log", "x") == "## Log\nx\n"
    assert T.add_to_section("", "", "x\n\n") == "x\n"
    assert T.add_to_section("# T\n## A\n## B\n", "A", "new") == "# T\n## A\nnew\n## B\n"
    assert T.add_to_section("## A\nfoo\n\n\n## B\nbar", "a", "new") == "## A\nfoo\nnew\n\n\n## B\nbar\n"
    assert T.add_to_section("```\n## A\n```\n", "A", "x") == "```\n## A\n```\n\n## A\nx\n"


def test_add_keeps_windows_line_endings_and_refuses_other_encodings(notes):
    nt, root = notes
    (root / "win.md").write_bytes(b"# Win\r\n## Log\r\nmonday\r\n")
    run(nt, "add_to_note", slug="win", text="tuesday", section="Log")
    assert (root / "win.md").read_bytes() == b"# Win\r\n## Log\r\nmonday\r\ntuesday\r\n"
    (root / "latin.md").write_bytes("caf\xe9 notes\n".encode("latin-1"))
    assert "left it alone" in run(nt, "add_to_note", slug="latin", text="x")
    assert (root / "latin.md").read_bytes() == "caf\xe9 notes\n".encode("latin-1")
    assert run(nt, "add_to_note", slug="new/one", text="first") == "Added to new/one."
    assert (root / "new" / "one.md").read_text(encoding="utf-8") == "first\n"


def test_tick_task(notes):
    nt, root = notes
    (root / "todo.md").write_text(
        "- [ ] read chapter 3\n- [ ] read chapter 4\n- [x] buy pens\n1. [ ] email Sam\n", encoding="utf-8"
    )
    assert "More than one" in run(nt, "tick_task", slug="todo", task="read chapter")
    assert run(nt, "tick_task", slug="todo", task="Chapter 4") == "Ticked: read chapter 4"
    assert run(nt, "tick_task", slug="todo", task="email sam") == "Ticked: email Sam"
    assert run(nt, "tick_task", slug="todo", task="buy pens") == "No open task matched those words."
    assert (root / "todo.md").read_text(encoding="utf-8") == (
        "- [ ] read chapter 3\n- [x] read chapter 4\n- [x] buy pens\n1. [x] email Sam\n"
    )
    assert run(nt, "tick_task", slug="nope", task="x") == "No such note, or no task words."


def test_list_and_read(notes):
    nt, root = notes
    (root / "linear-algebra").mkdir()
    (root / "linear-algebra" / "class-log.md").write_text("# Log\nEigenvalues today.", encoding="utf-8")
    (root / "linear-algebra" / "deep").mkdir()
    (root / "linear-algebra" / "deep" / "x.md").write_text("x", encoding="utf-8")
    (root / ".obsidian").mkdir()
    (root / "top.md").write_text("top", encoding="utf-8")
    assert run(nt, "list_notes", folder="") == {"folders": ["linear-algebra/"], "notes": ["top"]}
    assert run(nt, "list_notes", folder="linear-algebra") == {
        "folders": ["deep/"],
        "notes": ["linear-algebra/class-log"],
    }
    assert run(nt, "list_notes", folder="../") == "That isn't a folder in the notes."
    assert "Eigenvalues" in run(nt, "read_note", slug="linear-algebra/class-log")
    assert run(nt, "search_notes", query="eigenvalues class")["hits"][0]["slug"] == "linear-algebra/class-log"


# ---------------------------------------------------------------------------------------- gathering
class Extra(Module):
    id = "extra"
    title = "Extra"

    def call_tools(self):
        return [
            Tool("run_task", "call only", lambda a: "x"),
            Tool("pending_items", "call only", lambda a: "x"),
            Tool("search_notes", "a duplicate", lambda a: "dup"),
            Tool("extra_tool", "mine", lambda a: {"ok": a.get("n")}, {"n": arg()}, ("n",)),
            Tool("boom", "breaks", lambda a: 1 / 0),
        ]

    def agent_tools(self):
        return [Tool("only_unattended", "agent only", lambda a: "fine")]


class Broken(Module):
    id = "broken"
    title = "Broken"

    def call_tools(self):
        raise RuntimeError("nope")


class FakeAsk:
    def agent_tools(self):
        return [Tool("ask_user", "ask them", lambda a: "asked", {"question": arg()}, ("question",))]


def names(app):
    return [t.name for t in T.agent_tools(app)]


def test_agent_tools_gathers_from_features_that_are_on(app):
    base = names(app)
    assert base == ["search_notes", "read_note", "list_notes", "write_note", "add_to_note", "tick_task"]
    app.modules["extra"], app.modules["broken"] = Extra(app), Broken(app)
    assert names(app) == base  # off: none of their tools
    app.settings.set("modules.enabled", ["extra", "broken"])
    got = names(app)
    assert "extra_tool" in got and "only_unattended" in got
    assert "run_task" not in got and "pending_items" not in got and got.count("search_notes") == 1
    assert any(e["kind"] == "tools_failed" and e["module"] == "broken" for e in app.events.tail(20))
    app.ask = FakeAsk()
    assert "ask_user" in names(app)
    assert T.run_tool(app, "extra_tool", {"n": "3"}) == {"ok": "3"}
    assert T.run_tool(app, "extra_tool", {}) == "extra_tool needs: n."
    assert T.run_tool(app, "boom", {}).startswith("That failed: ZeroDivisionError")
    assert T.run_tool(app, "run_task", {}) == "There's no run_task tool (that feature may be off)."
    assert T.run_tool(app, "only_unattended", "not a dict") == "fine"
    kinds = [(e["kind"], e.get("name")) for e in app.events.tail(30)]
    assert ("tool_used", "extra_tool") in kinds and ("tool_failed", "boom") in kinds


def test_real_features_add_their_tools(app):
    app.settings.set("modules.enabled", ["reminders"])
    assert "add_reminder" in names(app)
    app.settings.set("modules.enabled", [])
    assert "add_reminder" not in names(app)


def test_calls_offer_scheduling_but_not_call_only_tools(app):
    calls = app.modules["calls"]
    assert [t.name for t in calls.agent_tools()] == ["schedule_call", "hold_calls"]
    app.settings.set("modules.enabled", ["calls"])
    got = names(app)
    assert "schedule_call" in got and "hold_calls" in got and "pending_items" not in got


def test_jobs_hand_the_tools_to_the_brain(app):
    fake = ScriptedOpenAI(
        [{"tool_calls": [call("write_note", {"slug": "inbox/basil", "text": "Water it."}, "w")]}, {"content": "Saved."}]
    )
    try:
        app.secrets.set("custom.api_key", fake.key)
        app.settings.set("brain.base_urls", {"custom": fake.base})
        app.settings.set("brain.models", {"custom": {"medium": "m"}})
        app.settings.set("brain.main", "custom")
        jid = app.jobs.submit("note: water the basil", quiet=True)
        app.jobs.run_next()
    finally:
        fake.close()
    assert app.jobs.get(jid).result == "Saved."
    assert (app.workspace / "inbox" / "basil.md").read_text(encoding="utf-8").endswith("Water it.\n")
    system = fake.requests[0]["messages"][0]["content"]
    assert "Kurooto's tools" in system and "Never say you did something you didn't" in system


def test_context_tells_the_ai_about_its_tools(app):
    ctx = headless_context(app)
    assert 'MCP server "kurooto"' in ctx and "never reword or remove their text" in ctx


# ---------------------------------------------------------------------------------------- the local API
def test_api_lists_and_runs_tools(app):
    api = Api(app)
    code, out = api.get("tools")
    assert code == 200
    by = {t["name"]: t for t in out["tools"]}
    assert by["write_note"]["schema"] == {
        "type": "object",
        "properties": {
            "slug": {"type": "string"},
            "text": {"type": "string", "description": "the whole note, Markdown"},
        },
        "required": ["slug", "text"],
    }
    assert json.loads((app.paths.state / "tools-list.json").read_text(encoding="utf-8")) == out["tools"]
    code, out = api.post("tools/call", {"name": "write_note", "args": {"slug": "inbox/x", "text": "hi"}})
    assert (code, out) == (200, {"ok": True, "result": "Created inbox/x."})
    assert api.post("tools/call", {"name": "nope", "args": {}})[0] == 404
    assert api.post("tools/call", {"name": "write_note", "args": "x"})[0] == 400
    assert api.post("tools/call", {"name": "list_notes"})[1]["result"]["notes"] == []
    assert ("tool_used", "api") in [(e["kind"], e.get("via")) for e in app.events.tail(10)]


def test_tools_only_key(tmp_path, monkeypatch):
    import urllib.error
    import urllib.request

    from kurooto.core.mcp import access_file
    from kurooto.web.server import start

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    srv = start(app, port=18790)
    try:
        access = json.loads(access_file(app.paths).read_text(encoding="utf-8"))
        assert access["url"] == srv.url and access["token"] == srv.tools_token != srv.token
        if os.name != "nt":
            assert oct(access_file(app.paths).stat().st_mode & 0o777) == "0o600"

        def req(path, body=None, key=access["token"], header="X-Kurooto-Tools", origin=None):
            h = {header: key, "Content-Type": "application/json", **({"Origin": origin} if origin else {})}
            data = None if body is None else json.dumps(body).encode()
            r = urllib.request.Request(srv.url + path.lstrip("/"), data=data, headers=h)
            try:
                with urllib.request.urlopen(r, timeout=30) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, None

        assert req("/api/tools")[0] == 200
        assert req("/api/tools/call", {"name": "list_notes", "args": {}})[0] == 200
        assert req("/api/state")[0] == 401  # good for the tools only
        assert req("/api/settings", {"key": "you.name", "value": "x"})[0] == 403
        assert req("/api/tools", key="wrong")[0] == 401
        assert req("/api/tools", origin="https://evil.example")[0] == 401
        assert req("/api/tools", key=srv.token, header="X-Kurooto")[0] == 200  # the page's own key works too
    finally:
        srv.stop()
        app.close()
    assert not access_file(app.paths).exists()  # gone when it stops


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_nothing_secret_in_the_tools_list(app):
    out = json.dumps(Api(app).get("tools")[1])
    assert str(app.workspace) not in out
