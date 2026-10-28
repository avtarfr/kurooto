"""(0.8.17, brain.claude.session) A conversation's Claude Code kept running: two turns are one program, its words come
as they're written, an idle one closes, a broken one hands the turn to a run of its own, and the switch off is the
old way. No real Claude Code: a fake that speaks its stream-json."""

import json
import os
import sys
import time

import psutil
import pytest

from kurooto.providers import claude as claude_mod
from kurooto.providers.base import Task, Verdict

FAKE = r"""
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(argv) + "\n")

def answer(text, n):
    words = f"pid={os.getpid()} n={n} got={text}"
    ev = lambda e: print(json.dumps({"type": "stream_event", "event": e}), flush=True)
    ev({"type": "message_start", "message": {"id": f"m{n}"}})
    half = len(words) // 2
    ev({"type": "content_block_delta", "delta": {"type": "text_delta", "text": words[:half]}})
    ev({"type": "content_block_delta", "delta": {"type": "text_delta", "text": words[half:]}})
    print(json.dumps({"type": "result", "result": words, "modelUsage": {"claude-haiku": {"costUSD": 0.001}}}),
          flush=True)

if "--input-format" in argv:  # kept: one message a line, an answer each
    n = 0
    for line in sys.stdin:
        msg = json.loads(line)
        if os.environ.get("FAKE_CRASH"):
            sys.exit(3)
        if os.environ.get("FAKE_SLOW"):  # starts, then works past the request's time
            print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
            import time; time.sleep(60)
        if os.environ.get("FAKE_MUTE"):  # a version that doesn't answer this way
            import time; time.sleep(60)
        n += 1
        answer(msg["message"]["content"], n)
else:
    answer(sys.stdin.read(), 0)
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "argv.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    yield [sys.executable, str(script)], log
    claude_mod.close_sessions()


def pid_of(text: str) -> int:
    return int(text.split()[0].split("=")[1])


def after(one, text: str) -> str:
    """chat's request after one answered turn of "hi" (modules/chat.py)"""
    return f"Previous conversation:\nUser: hi\nAssistant: {one.text}\n\nCurrent request:\n{text}"


def task(tmp_path, prompt="hi", **kw):
    return Task(prompt=prompt, cwd=tmp_path, timeout_s=60, session="main", **kw)


def test_two_turns_are_one_program_and_stream_as_before(tmp_path, fake):
    exe, log = fake
    brain = claude_mod.ClaudeCode(exe=exe)
    got = []
    one = brain.run(task(tmp_path, context="You are Kurooto.\nIt is 10:00.", on_text=lambda k, t: got.append((k, t))))
    assert one.ok and one.model == "claude-haiku" and one.text.endswith("got=hi")
    assert got[-1] == ("m1", one.text) and len(got) == 2  # the deltas, as a run of its own gives them
    two = brain.run(task(tmp_path, after(one, "and now?"), context="You are Kurooto.\nIt is 10:05."))
    assert two.ok and pid_of(two.text) == pid_of(one.text) and " n=2 " in two.text
    sent = two.text.split("got=", 1)[1]
    assert sent.endswith("\n\nand now?") and "Previous conversation" not in sent  # it has that history already
    assert sent.startswith(claude_mod.NEWS) and "It is 10:05." in sent and "You are Kurooto." not in sent
    runs = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(runs) == 1  # one program
    args = runs[0]
    assert args[args.index("--input-format") + 1] == "stream-json" and "--include-partial-messages" in args
    plain = brain.args(Task(prompt="hi", cwd=tmp_path, on_text=lambda k, t: None), tmp_path)
    for flag in ("--permission-mode", "--setting-sources", "--no-session-persistence", "--settings", "--model"):
        assert flag in args and flag in plain  # the same command a run of its own has
    assert "--append-system-prompt-file" in args


def test_history_it_never_saw_is_sent_and_a_fresh_start_is_a_new_program(tmp_path, fake):
    exe, _log = fake
    brain = claude_mod.ClaudeCode(exe=exe)
    one = brain.run(task(tmp_path))
    told = "Previous conversation:\nUser: typed on another computer\nAssistant: ok\n\nCurrent request:\nwell?"
    two = brain.run(task(tmp_path, told))
    assert pid_of(two.text) == pid_of(one.text) and "typed on another computer" in two.text
    three = brain.run(task(tmp_path, "new topic"))  # no history: the chat was cleared or went quiet
    assert pid_of(three.text) != pid_of(one.text) and " n=1 " in three.text


def test_an_idle_program_closes(tmp_path, fake):
    exe, _log = fake
    brain = claude_mod.ClaudeCode(exe=exe)
    one = brain.run(task(tmp_path))
    pid = pid_of(one.text)
    assert claude_mod.reap() == 0  # not idle yet
    assert claude_mod.reap(time.monotonic() + 11 * 60) == 1 and not claude_mod._SESSIONS
    for _ in range(100):
        if not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("the idle program is still running")
    two = brain.run(task(tmp_path, after(one, "x")))
    assert two.ok and pid_of(two.text) != pid


def test_a_broken_program_hands_the_turn_to_a_run_of_its_own(tmp_path, fake, monkeypatch):
    exe, log = fake
    brain = claude_mod.ClaudeCode(exe=exe)
    monkeypatch.setenv("FAKE_CRASH", "1")
    res = brain.run(task(tmp_path, on_text=lambda k, t: None))
    assert res.ok and " n=0 " in res.text and res.text.endswith("got=hi")  # answered by a run of its own
    assert not claude_mod._SESSIONS
    runs = [json.loads(x) for x in log.read_text().splitlines()]
    assert "--input-format" in runs[0] and "--input-format" not in runs[1]
    monkeypatch.delenv("FAKE_CRASH")
    monkeypatch.setenv("FAKE_MUTE", "1")
    monkeypatch.setattr(claude_mod, "FIRST_S", 0.5)
    t0 = time.monotonic()
    res = brain.run(task(tmp_path))
    assert res.ok and " n=0 " in res.text and time.monotonic() - t0 < 10 and not claude_mod._SESSIONS
    monkeypatch.delenv("FAKE_MUTE")
    one = brain.run(task(tmp_path))
    os.kill(pid_of(one.text), 9)  # gone between turns
    time.sleep(0.3)
    two = brain.run(task(tmp_path, after(one, "y")))
    assert two.ok and pid_of(two.text) != pid_of(one.text)


def test_a_turn_past_its_time_is_a_timeout_and_the_program_goes(tmp_path, fake, monkeypatch):
    exe, _log = fake
    brain = claude_mod.ClaudeCode(exe=exe)
    brain.grace_s = 0
    monkeypatch.setenv("FAKE_SLOW", "1")
    t0 = time.monotonic()
    res = brain.run(Task(prompt="hi", cwd=tmp_path, timeout_s=1, session="main"))
    assert res.verdict == Verdict.TIMEOUT and time.monotonic() - t0 < 15 and not claude_mod._SESSIONS


def test_a_busy_program_leaves_the_second_request_to_a_run_of_its_own(tmp_path, fake):
    exe, _log = fake
    brain = claude_mod.ClaudeCode(exe=exe)
    one = brain.run(task(tmp_path))
    (s,) = claude_mod._SESSIONS.values()
    with s.lock:
        two = brain.run(task(tmp_path, after(one, "z")))
    assert two.ok and " n=0 " in two.text and claude_mod._SESSIONS  # the kept one stays


def test_switch_off_and_requests_on_their_own_are_runs_of_their_own(tmp_path, fake, monkeypatch):
    from kurooto.app import App

    exe, log = fake
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    app = App()
    try:
        app.settings.set("brain.claude.session", False)
        brain = claude_mod.ClaudeCode(exe=exe, app=app)
        res = brain.run(task(tmp_path))
        assert res.ok and " n=0 " in res.text and not claude_mod._SESSIONS
        res = claude_mod.ClaudeCode(exe=exe).run(Task(prompt="hi", cwd=tmp_path, timeout_s=60))  # no conversation
        assert " n=0 " in res.text and not claude_mod._SESSIONS
        assert all("--input-format" not in json.loads(x) for x in log.read_text().splitlines())
        app.settings.set("brain.claude.session", True)
        on = brain.run(task(tmp_path))
        assert " n=1 " in on.text and len(claude_mod._SESSIONS) == 1
        app.settings.set("brain.claude.session", False)  # turned off meanwhile: it closes
        assert claude_mod.reap() == 1
    finally:
        app.close()


def test_chat_turns_name_their_conversation_and_tools_find_the_request(tmp_path, monkeypatch):
    from kurooto.app import App
    from kurooto.core import mcp
    from kurooto.modules.base import Incoming

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    app = App()
    try:
        chat = app.modules.get("chat")
        msg = Incoming(text="what's the time", via="telegram")
        chat.ask(msg)
        assert chat.conversation(msg.job) == "main" and app.jobs._conversation(msg.job) == "main"
        typed = Incoming(text="hello", via="terminal")
        chat.ask(typed)
        assert app.jobs._conversation(typed.job) == ""  # the terminal's: on its own
    finally:
        app.close()
    f = tmp_path / "job"
    f.write_text("j1234", encoding="utf-8")
    monkeypatch.setenv(mcp.ENV_JOB, "jold")
    assert mcp.job_id() == "jold"
    monkeypatch.setenv(mcp.ENV_JOB_FILE, str(f))
    assert mcp.job_id() == "j1234"
