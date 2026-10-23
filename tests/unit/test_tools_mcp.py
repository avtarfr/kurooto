"""`kurooto mcp` end to end (a real subprocess against a running test Kurooto), the agent programs' MCP wiring
(fake claude and agy that really start the server), `kurooto call`, `kurooto ask` and /usage."""

import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from kurooto import cli, providers
from kurooto.app import App
from kurooto.core import mcp
from kurooto.modules.base import Module
from kurooto.modules.calls.tools import Tool
from kurooto.modules.chat import usage_text
from kurooto.providers.agy import (
    ALLOW,
    CONSENT,
    NON_WORKSPACE,
    Agy,
    connect_tools,
    consent_file,
    tools_once,
    wanted_rules,
)
from kurooto.providers.base import Task, Verdict
from kurooto.providers.claude import ClaudeCode
from kurooto.web import tools_api
from kurooto.web.api import Api
from kurooto.web.server import start
from tests.fakes.openai import FakeOpenAI

FAKES = Path(__file__).parents[1] / "fakes"
AGENT = [sys.executable, str(FAKES / "fake_mcp_agent.py")]


class Slow(Module):
    id = "slow"
    title = "Slow"

    def call_tools(self):
        return [Tool("slow", "takes a while", lambda a: time.sleep(1.5) or "slept")]


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A throwaway Kurooto and a fake home folder: nothing here touches this computer's own agent programs."""
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    for k in (mcp.ENV_URL, mcp.ENV_TOKEN):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "home").mkdir()
    return tmp_path


@pytest.fixture
def live(home):
    app = App()
    srv = start(app, port=18800 + os.getpid() % 100)
    yield app, srv
    srv.stop()
    app.close()


class Client:
    """An MCP client talking to `kurooto mcp` over pipes."""

    def __init__(self, env: dict):
        self.p = subprocess.Popen(
            [sys.executable, "-m", "kurooto", "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            self.q.put(json.loads(line))

    def send(self, obj):
        raw = obj if isinstance(obj, (bytes, str)) else json.dumps(obj)
        self.p.stdin.write((raw if isinstance(raw, bytes) else raw.encode()) + b"\n")
        self.p.stdin.flush()

    def recv(self, timeout=60):
        return self.q.get(timeout=timeout)

    def rpc(self, method, params=None, mid=1):
        self.send({"jsonrpc": "2.0", "id": mid, "method": method, **({"params": params} if params else {})})
        return self.recv()

    def close(self):
        self.p.stdin.close()
        return self.p.wait(30)


def env_for(**extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith("KUROOTO_TOOLS_")}
    return {**e, **extra}


def test_mcp_server_end_to_end(live):
    app, srv = live
    c = Client(env_for())
    try:
        r = c.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}})
        assert r["id"] == 1 and r["result"]["protocolVersion"] == "2025-06-18"
        assert r["result"]["serverInfo"]["name"] == "kurooto" and "tools" in r["result"]["capabilities"]
        c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})  # no answer to a notification
        assert c.rpc("ping", mid=2) == {"jsonrpc": "2.0", "id": 2, "result": {}}
        tools = {t["name"]: t for t in c.rpc("tools/list", mid=3)["result"]["tools"]}
        assert tools["write_note"]["inputSchema"]["required"] == ["slug", "text"]
        assert "run_task" not in tools

        r = c.rpc("tools/call", {"name": "write_note", "arguments": {"slug": "inbox/from-mcp", "text": "hi"}}, 4)
        assert r["result"] == {"content": [{"type": "text", "text": "Created inbox/from-mcp."}], "isError": False}
        assert (app.workspace / "inbox" / "from-mcp.md").is_file()
        r = c.rpc("tools/call", {"name": "list_notes", "arguments": {"folder": "inbox"}}, 5)
        assert json.loads(r["result"]["content"][0]["text"])["notes"] == ["inbox/from-mcp"]
        assert c.rpc("tools/call", {"name": "nope", "arguments": {}}, 6)["error"]["code"] == -32602
        assert c.rpc("tools/call", {"arguments": {}}, 7)["error"]["code"] == -32602
        assert c.rpc("tools/call", {"name": "list_notes", "arguments": [1]}, 8)["result"]["isError"] is True
        uris = [x["uri"] for x in c.rpc("resources/list", mid=9)["result"]["resources"]]  # (0.5.22) what it runs
        assert uris == ["kurooto://self", "kurooto://manual"]
        assert c.rpc("prompts/list", mid=9)["error"]["code"] == -32601
        c.send(b"{not json")
        assert c.recv() == {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        c.send({"id": 10, "method": "ping"})  # no "jsonrpc": "2.0"
        assert c.recv()["error"]["code"] == -32600
        c.send([{"jsonrpc": "2.0", "id": 11, "method": "ping"}, {"jsonrpc": "2.0", "method": "x/y"}])
        assert c.recv() == [{"jsonrpc": "2.0", "id": 11, "result": {}}]
        r = c.rpc("initialize", {"protocolVersion": "1999-01-01"}, 12)
        assert r["result"]["protocolVersion"] == mcp.PROTOCOLS[0]
        assert any(e["kind"] == "tool_used" and e.get("via") == "mcp" for e in app.events.tail(30))

        srv.stop()  # Kurooto stops: the list stays, calls say so
        r = c.rpc("tools/call", {"name": "list_notes", "arguments": {}}, 13)
        assert r["result"]["isError"] is True and "isn't running" in r["result"]["content"][0]["text"]
        assert "write_note" in [t["name"] for t in c.rpc("tools/list", mid=14)["result"]["tools"]]
    finally:
        assert c.close() == 0
        srv.stop = lambda: None  # stopped already


def test_mcp_without_kurooto_running(home):
    c = Client(env_for())
    try:
        assert c.rpc("tools/list")["result"] == {"tools": []}
        r = c.rpc("tools/call", {"name": "add_reminder", "arguments": {}}, 2)
        assert r["result"]["isError"] and "kurooto on" in r["result"]["content"][0]["text"]
    finally:
        assert c.close() == 0


def test_mcp_takes_the_address_from_its_environment(live, tmp_path):
    app, srv = live
    access = json.loads(mcp.access_file(app.paths).read_text(encoding="utf-8"))
    elsewhere = tmp_path / "elsewhere"  # as if the agent program passed only these variables
    c = Client(
        env_for(KUROOTO_HOME=str(elsewhere), KUROOTO_TOOLS_URL=access["url"], KUROOTO_TOOLS_TOKEN=access["token"])
    )
    try:
        r = c.rpc("tools/call", {"name": "list_notes", "arguments": {}})
        assert r["result"]["isError"] is False
    finally:
        c.close()
    # an old key in the environment (Kurooto restarted since): it uses the new one it left in its folder
    c = Client(env_for(KUROOTO_TOOLS_URL=access["url"], KUROOTO_TOOLS_TOKEN="old"))
    try:
        assert c.rpc("tools/call", {"name": "list_notes", "arguments": {}})["result"]["isError"] is False
    finally:
        c.close()


def test_two_calls_at_once_and_a_ping_meanwhile(live):
    app, srv = live
    app.modules["slow"] = Slow(app)
    app.settings.set("modules.enabled", ["slow"])
    c = Client(env_for())
    try:
        c.send({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "slow", "arguments": {}}})
        c.send({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        assert c.recv()["id"] == 2  # not stuck behind the slow tool
        assert c.recv(30)["result"]["content"][0]["text"] == "slept"
    finally:
        c.close()


# ------------------------------------------------------------------------------ agent programs, per run
def agent_task(app, tool, args):
    return Task(
        prompt="add it",
        cwd=app.workspace,
        timeout_s=120,
        mcp=mcp.command(),
        mcp_env=mcp.run_env(app.paths),
    ), {"FAKE_AGENT_TOOL": tool, "FAKE_AGENT_ARGS": json.dumps(args)}


def log_of(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_claude_code_gets_the_tools_for_one_run(live, monkeypatch, tmp_path):
    app, srv = live
    task, env = agent_task(app, "add_to_note", {"slug": "journal/today", "text": "Ran 5 km.", "section": "Log"})
    for k, v in {**env, "FAKE_AGENT_LOG": str(tmp_path / "claude.log")}.items():
        monkeypatch.setenv(k, v)
    r = ClaudeCode(exe=AGENT).run(task)
    assert r.verdict == Verdict.OK and r.text == "Added to journal/today."
    assert (app.workspace / "journal" / "today.md").read_text(encoding="utf-8") == "## Log\nRan 5 km.\n"
    rec = log_of(tmp_path / "claude.log")[0]
    a = rec["argv"]
    assert "--strict-mcp-config" in a and a[a.index("--permission-mode") + 1] == "dontAsk"
    assert "mcp__kurooto" in rec["settings"]["permissions"]["allow"]
    server = rec["config"]["mcpServers"]["kurooto"]
    assert server["command"] == sys.executable and server["args"] == ["-m", "kurooto", "mcp"]
    assert server["env"][mcp.ENV_TOKEN] == srv.tools_token and server["env"]["KUROOTO_HOME"]
    assert not Path(a[a.index("--mcp-config") + 1]).exists()  # the key's file is gone after the run


def test_jobs_give_agent_programs_the_server(live):
    app, srv = live
    seen = {}

    class Spy:
        id, label, kind = "spy", "Spy", "api"

        def available(self):
            return True, ""

        def run(self, task):
            seen["task"] = task
            from kurooto.providers.base import Result

            return Result(Verdict.OK, "fine")

    import kurooto.providers as providers

    orig = providers.build
    providers.build = lambda a, which: Spy() if which == "spy" else orig(a, which)
    try:
        app.settings.set("brain.main", "spy")
        app.jobs.submit("hello", quiet=True)
        app.jobs.run_next()
    finally:
        providers.build = orig
    t = seen["task"]
    assert t.mcp == mcp.command() and t.mcp_env[mcp.ENV_TOKEN] == srv.tools_token
    assert {x.name for x in t.tools} >= {"write_note", "tick_task"}


def test_agy_runs_pass_the_address_on(home, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "agy.log"))
    Agy(exe=AGENT).run(Task(prompt="hi", timeout_s=60, mcp_env={mcp.ENV_URL: "http://x/", mcp.ENV_TOKEN: "t"}))
    assert log_of(tmp_path / "agy.log")[0]["tools_env"] == {mcp.ENV_URL: "http://x/", mcp.ENV_TOKEN: "t"}


# ------------------------------------------------------------------------------ agy, at setup
def settings(home):
    return home / "home" / ".gemini" / "antigravity-cli" / "settings.json"


def test_agy_setup_registers_and_allows_the_tools(home, monkeypatch, tmp_path):
    # the system's own folders are whatever this computer (or CI) has; only a portable copy's folder is saved in agy
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    app = App()
    try:
        monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "agy.log"))
        f = settings(home)
        f.parent.mkdir(parents=True)
        original = {"model": "x", "permissions": {"allow": ["command(ls)"]}, "trustedWorkspaces": ["/w"]}
        f.write_text(json.dumps(original), encoding="utf-8")
        assert connect_tools(app, AGENT) == (True, "agy may use Kurooto's tools")
        argv = log_of(tmp_path / "agy.log")[0]["argv"]
        assert argv == [
            "mcp",
            "add",
            "--env",
            f"KUROOTO_HOME={os.environ['KUROOTO_HOME']}",
            "kurooto",
            "--",
            *mcp.command(),
        ]
        data = json.loads(f.read_text(encoding="utf-8"))
        rules = wanted_rules(app)
        mine = ["command(ls)", *(r for r in rules if r != "command(ls)")]  # theirs first, nothing twice
        assert data == {**original, **NON_WORKSPACE, "permissions": {"allow": mine}}
        backups = list((app.paths.state / "backups").iterdir())
        assert len(backups) == 1 and json.loads(backups[0].read_text(encoding="utf-8")) == original
        assert connect_tools(app, AGENT) == (True, "agy may already use Kurooto's tools")  # again: no change
        assert json.loads(f.read_text(encoding="utf-8"))["permissions"]["allow"].count(ALLOW) == 1
        assert len(list((app.paths.state / "backups").iterdir())) == 1
        assert json.loads((app.paths.state / "agy-tools.json").read_text(encoding="utf-8"))["ok"] is True
    finally:
        app.close()


def test_agy_setup_leaves_odd_settings_alone(home, monkeypatch):
    app = App()
    try:
        f = settings(home)
        f.parent.mkdir(parents=True)
        f.write_text("{ // comments are not JSON\n}", encoding="utf-8")
        ok, msg = connect_tools(app, AGENT)
        assert not ok and "permissions.allow" in msg and f.read_text(encoding="utf-8").startswith("{ //")
        f.unlink()
        assert connect_tools(app, AGENT)[0] is True  # no settings yet: made with just Kurooto's part
        assert json.loads(f.read_text(encoding="utf-8")) == {
            "permissions": {"allow": wanted_rules(app)},
            **NON_WORKSPACE,
        }
        monkeypatch.setenv("FAKE_AGENT_EXIT", "1")
        f.unlink()
        ok, msg = connect_tools(app, AGENT)
        assert not ok and "didn't take" in msg and not f.exists()
    finally:
        app.close()


@pytest.mark.skipif(os.name == "nt", reason="a POSIX script stands in for an installed agy")
def test_agy_tools_once_after_an_update(home, monkeypatch, tmp_path):
    app = App()
    try:
        monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "agy.log"))
        exe = tmp_path / "agy"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{AGENT[1]}" "$@"\n', encoding="utf-8")
        exe.chmod(0o755)
        tools_once(app, Agy(exe=AGENT))  # a test's fake (a list): never
        tools_once(app, Agy(exe=str(exe)))  # a portable or test copy (KUROOTO_HOME): not by itself
        assert not (tmp_path / "agy.log").exists() and not app.ask.pending()
        monkeypatch.setenv("KUROOTO_AGY_TOOLS", "1")
        tools_once(app, Agy(exe=str(exe)))  # set up before tools existed: agy's settings are yours, so it asks
        tools_once(app, Agy(exe=str(exe)))  # once
        (q,) = app.ask.pending()
        assert q["text"] == CONSENT and q["kind"] == "approval"
        assert not (tmp_path / "agy.log").exists() and not settings(home).exists()
        app.ask.answer(q["id"], "Approve")
        assert len(log_of(tmp_path / "agy.log")) == 1 and settings(home).exists()
        tools_once(app, Agy(exe=str(exe)))
        assert len(log_of(tmp_path / "agy.log")) == 1
        f = app.paths.state / "agy-tools.json"  # an update changed Kurooto's command: connected again, no question
        f.write_text(json.dumps({**json.loads(f.read_text(encoding="utf-8")), "command": ["old"]}), encoding="utf-8")
        tools_once(app, Agy(exe=str(exe)))
        assert len(log_of(tmp_path / "agy.log")) == 2 and not app.ask.pending()
    finally:
        app.close()


@pytest.mark.skipif(os.name == "nt", reason="a POSIX script stands in for an installed agy")
def test_agy_tools_denied_holds_for_30_days(home, monkeypatch, tmp_path):
    app = App()
    try:
        monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "agy.log"))
        monkeypatch.setenv("KUROOTO_AGY_TOOLS", "1")
        exe = tmp_path / "agy"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{AGENT[1]}" "$@"\n', encoding="utf-8")
        exe.chmod(0o755)
        tools_once(app, Agy(exe=str(exe)))
        (q,) = app.ask.pending()
        app.ask.answer(q["id"], "Deny")
        tools_once(app, Agy(exe=str(exe)))
        assert not app.ask.pending() and not (tmp_path / "agy.log").exists() and not settings(home).exists()
        f = consent_file(app.paths.state)
        f.write_text(json.dumps({"denied": json.loads(f.read_text(encoding="utf-8"))["denied"] - 31 * 86400}))
        tools_once(app, Agy(exe=str(exe)))
        assert len(app.ask.pending()) == 1  # a month later it asks again
    finally:
        app.close()


def test_agy_setup_test_connects_the_tools(home, monkeypatch, tmp_path):
    app = App()
    try:
        monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "agy.log"))
        fake = tmp_path / "agy_answers.py"
        fake.write_text(
            "import sys, runpy\n"
            "if sys.argv[1:3] == ['mcp', 'add']:\n"
            f"    sys.argv = [{AGENT[1]!r}] + sys.argv[1:]; runpy.run_path({AGENT[1]!r}, run_name='__main__')\n"
            "else:\n    print(sys.argv[sys.argv.index('-p') + 1].split(': ')[-1])\n",
            encoding="utf-8",
        )
        import kurooto.providers as providers

        monkeypatch.setattr(providers, "build", lambda a, which: Agy(exe=[sys.executable, str(fake)]))
        r = Api(app).post("brain/test", {"which": "agy"})[1]
        assert r["ok"] and r["message"].endswith("and write in your notes folder.")
        assert ALLOW in settings(home).read_text(encoding="utf-8")
    finally:
        app.close()


def test_persistent_command_goes_through_the_launcher(home, monkeypatch):
    from kurooto.core.paths import paths
    from kurooto.core.state import jsave

    p = paths().ensure()
    assert mcp.command(persistent=True) == mcp.command() == [sys.executable, "-m", "kurooto", "mcp"]
    (p.app / "launcher.py").write_text("# launcher", encoding="utf-8")
    py = home / "py" / "bin" / "python3"
    jsave(p.app / "install.json", {"python": str(py)})
    assert mcp.command(persistent=True) == [str(py), str(p.app / "launcher.py"), "cli", "mcp"]
    # Windows: a windowless pythonw.exe has no stdin/stdout, so the python.exe next to it is used
    scripts = home / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_bytes(b"")
    (scripts / "pythonw.exe").write_bytes(b"")
    jsave(p.app / "install.json", {"python": str(scripts / "pythonw.exe")})
    assert mcp.command(persistent=True)[0] == str(scripts / "python.exe")
    monkeypatch.setattr(sys, "executable", str(scripts / "pythonw.exe"))
    assert mcp.command() == [str(scripts / "python.exe"), "-m", "kurooto", "mcp"]


# ------------------------------------------------------------------------------ kurooto call
class FakeCalls:
    id = "calls"

    def __init__(self):
        self.rang, self.scheduled = [], []

    def ring(self, reason, alarm=False, key="", **kw):
        self.rang.append((reason, alarm))
        return "1"

    def schedule(self, at, reason, key=None, alarm=False, **kw):
        self.scheduled.append((at, reason, alarm))
        return f"I'll call you {at:%a %d %b at %H:%M}: {reason}"

    def agent_tools(self):
        return []


@pytest.fixture
def calls(home):
    app = App()
    fake = FakeCalls()
    app.modules["calls"] = fake
    app.settings.set("modules.enabled", ["calls"])
    yield app, fake
    app.close()


def test_call_now_waits_out_no_call_rules(calls):
    import datetime as dt

    app, fake = calls
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00"})
    assert tools_api.place_call(app, "the build finished") == (True, "Calling your phone: the build finished")
    until = dt.datetime.now().replace(microsecond=0) + dt.timedelta(hours=1)
    app.availability.set_quiet(until)
    ok, msg = tools_api.place_call(app, "lunch")
    assert ok and msg.startswith(f"Held until {until + dt.timedelta(minutes=2):%H:%M} (you asked for no calls)")
    assert fake.scheduled[-1][1] == "lunch" and len(fake.rang) == 1
    assert tools_api.place_call(app, "now!", force=True)[1] == "Calling your phone: now!"
    assert tools_api.place_call(app, "wake up", alarm=True)[0] and fake.rang[-1] == ("wake up", True)
    app.availability.on_call_until = lambda t=None: dt.datetime.now() + dt.timedelta(seconds=90)  # the phone's state
    ok, msg = tools_api.place_call(app, "urgent", force=True)
    assert not ok and "on a call" in msg and len(fake.rang) == 3
    app.availability.on_call_until = lambda t=None: None
    app.availability.blockers["phone:live"] = lambda t: ("you're on a call", t + dt.timedelta(minutes=5))
    assert tools_api.place_call(app, "urgent", alarm=True)[0] is False and len(fake.rang) == 3
    app.availability.set_quiet(None)
    ok, msg = tools_api.place_call(app, "after the call")  # not forced: held until the call is over
    assert ok and "(you're on a call)" in msg and fake.scheduled[-1][1] == "after the call" and len(fake.rang) == 3


def test_call_later_and_mistakes(calls):
    app, fake = calls
    ok, msg = tools_api.place_call(app, "stand-up", at="in 20 min")
    assert ok and msg.startswith("I'll call you") and fake.scheduled[-1][1] == "stand-up"
    assert tools_api.place_call(app, "x", at="whenever")[1].startswith("I couldn't read the time")
    assert tools_api.place_call(app, " ")[1] == "Say what the call is for."
    app.settings.set("modules.enabled", [])
    assert tools_api.place_call(app, "x")[1].startswith("Phone calls are off")


def test_kurooto_call_cli(calls, capsys):
    app, fake = calls
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00"})
    assert cli.main(["call", "the", "backup", "finished"]) == 2  # not running (like send, notify, ask-me)
    assert "isn't running" in capsys.readouterr().err
    srv = start(app, port=18900 + os.getpid() % 100)
    try:
        assert cli.main(["call", "--alarm", "wake", "up"]) == 0
        assert capsys.readouterr().out.strip() == "Calling your phone: wake up" and fake.rang == [("wake up", True)]
        assert cli.main(["call", "--at", "nonsense", "x"]) == 1
    finally:
        srv.stop()


# ------------------------------------------------------------------------------ kurooto ask
@pytest.fixture
def chat(home):
    ai = FakeOpenAI()
    app = App()
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    assert app.enable("chat")[0]
    srv = start(app, port=19000 + os.getpid() % 100)
    yield app, ai
    srv.stop()
    app.close()
    ai.close()


def pump(app, until):
    """Run queued AI requests (the daemon's worker isn't running in tests) until the thread finishes."""
    while until.is_alive():
        app.jobs.run_next()
        until.join(0.2)


def test_kurooto_ask(chat, capsys):
    app, ai = chat
    assert cli.main(["ask", "/brain"]) == 0
    assert capsys.readouterr().out.strip() == "main: Another OpenAI-compatible service (ready)"
    sent = []
    app.notifier.send = lambda text, **kw: sent.append(text)
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("code", cli.main(["ask", "capital", "of", "France?"])))
    t.start()
    pump(app, t)
    assert out["code"] == 0 and capsys.readouterr().out.strip() == "Paris."
    assert sent == []  # the answer came here, not to Telegram
    assert cli.main(["ask", "--no-wait", "and", "of", "Spain?"]) == 0
    jid = capsys.readouterr().out.strip()
    assert jid.startswith("j")
    t = threading.Thread(target=lambda: out.update(code=cli.main(["ask", "--job", jid])))
    t.start()
    pump(app, t)
    assert out["code"] == 0 and capsys.readouterr().out.strip() == "Paris."
    ai.mode = "500"
    t = threading.Thread(target=lambda: out.update(code=cli.main(["ask", "will", "this", "work?"])))
    t.start()
    pump(app, t)
    assert out["code"] == 1 and "went wrong" in capsys.readouterr().out


def test_kurooto_ask_when_not_running(home, capsys):
    assert cli.main(["ask", "hello"]) == 1 and "isn't running" in capsys.readouterr().err


def test_say_api_without_chat(home):
    app = App()
    try:
        code, r = Api(app).post("say", {"text": "hello there"})
        assert code == 200 and r["job"] is None and "turn on Chat" in r["replies"][0]
        assert Api(app).post("say", {"text": " "})[0] == 400
        assert Api(app).get("job", {"id": "jnope"})[0] == 404
    finally:
        app.close()


# ------------------------------------------------------------------------------ /usage
def test_usage_counts_every_try_and_limit_hits(chat):
    app, ai = chat
    fb = FakeOpenAI(key="sk-fb")
    try:
        app.secrets.set("ollama.api_key", fb.key)
        app.settings.set("brain.base_urls", {"custom": ai.base, "ollama": fb.base})
        app.settings.set("brain.models", {"custom": {"medium": "m"}, "ollama": {"medium": "q"}})
        app.settings.set("brain.fallback", "ollama")
        app.notifier.send = lambda text, **kw: None
        ai.mode = "429"
        app.jobs.submit("one", quiet=True, effort="medium")
        app.jobs.run_next()
        ai.mode = "ok"
        providers.fallback.clear(app, "custom")  # (0.5.22) else skipped until its limit's reset
        app.jobs.submit("two", quiet=True, effort="medium")
        app.jobs.run_next()
    finally:
        fb.close()
    rows = {r["brain"]: r for r in app.jobs.usage(7)}
    assert rows["custom"]["requests"] == 2 and rows["custom"]["limited"] == 1 and rows["ollama"]["requests"] == 1
    text = Api(app).get("usage", {"days": "7"})[1]
    assert text["days"] == 7 and len(text["rows"]) == 2
    msg = usage_text(app.jobs.usage(7), 7)
    lines = msg.splitlines()
    assert lines[0] == "AI requests, last 7 days:" and len([x for x in lines if x[:3].isalpha()]) >= 7
    today = [x for x in lines if x.startswith(time.strftime("%a %d %b"))][0]
    assert "Another OpenAI-compatible service 2 (limit hit 1)" in today and "Ollama on this computer 1" in today
    assert "Usage limit hit 1 time;" in msg and "Total: 3 requests" in msg


def test_usage_starts_from_older_jobs(home):
    from kurooto.core.paths import paths

    p = paths().ensure()
    db = sqlite3.connect(p.state / "jobs.db")
    db.execute(
        "create table jobs (id text primary key, title text, prompt text, effort_req text, effort text, status text, "
        "verdict text, brain text, reply_to text, quiet integer, created real, started real, finished real, "
        "seconds real, result text, detail text, then_action text, then_payload text)"
    )
    db.execute(
        "insert into jobs(id, status, verdict, brain, created, finished, seconds) values('j1','ok','ok','agy',?,?,3)",
        (time.time(), time.time()),
    )
    db.commit()
    db.close()
    app = App()
    try:
        assert [(r["brain"], r["requests"]) for r in app.jobs.usage(7)] == [("agy", 1)]
        app.jobs.close()
        app.jobs = type(app.jobs)(app)  # opening it again doesn't count them twice
        assert app.jobs.usage(7)[0]["requests"] == 1
    finally:
        app.close()


def test_usage_on_telegram_with_nothing_yet(home):
    text = usage_text([], 3)
    assert text.count(" -") == 3 and "Total: 0 requests." in text and "limit hit" not in text


def test_long_agy_requests_go_through_a_file(home, monkeypatch, tmp_path):
    from kurooto.providers import agy as agy_mod

    monkeypatch.setattr(agy_mod, "ARG_LIMIT", 50)
    fake = tmp_path / "reads_file.py"
    fake.write_text(
        "import re, sys\np = sys.argv[sys.argv.index('-p') + 1]\n"
        "f = re.search(r'file (\\S+) ', p).group(1)\nprint(len(p), open(f, encoding='utf-8').read()[-12:])\n",
        encoding="utf-8",
    )
    ws = tmp_path / "notes"
    ws.mkdir()
    r = Agy(exe=[sys.executable, str(fake)]).run(Task(prompt="x" * 500 + " the end now", cwd=ws, timeout_s=60))
    short, tail = r.text.split(" ", 1)
    assert r.verdict == Verdict.OK and int(short) < 200 and tail == " the end now"
    req = ws / ".kurooto" / "requests"
    assert [p.name for p in req.iterdir()] == [".gitignore"]  # the request file is gone after the run
    assert (req / ".gitignore").read_text(encoding="utf-8") == "*\n"
    short_run = Agy(exe=AGENT).run(Task(prompt="short", cwd=ws, timeout_s=60))
    assert short_run.text == "no tools given"


def test_what_agy_may_do(home, monkeypatch, tmp_path):
    from kurooto.core import places

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for d in ("Documents", "Downloads", "Pictures/Screenshots"):
        (home / "home" / d).mkdir(parents=True)
    app = App()
    try:
        rules = wanted_rules(app)
        notes = os.path.abspath(app.workspace)
        assert rules[0] == ALLOW and "read_url(*)" in rules
        writes = [r[11:-1] for r in rules if r.startswith("write_file(")]
        assert writes == [notes, str(app.paths.data / "classroom")]  # notes and course files; add-ons are off
        cmds = {r[8:-1] for r in rules if r.startswith("command(")}
        assert {"grep", "cat", "ls", "pdftotext", "mkdir"} <= cmds
        assert not cmds & {"sed", "kurooto", "rm", "mv", "cp", "python", "python3", "bash", "sh", "curl"}
        assert not cmds & {"find", "git", "latexmk", "rg", "sort"}  # each can start another program through options
        reads = [r[10:-1] for r in rules if r.startswith("read_file(")]
        assert reads == [str(p) for p in places.read_roots(app)] and reads[0] == notes
        assert str(app.paths.state / "mail-digest") in reads and str(app.paths.data / "classroom") in reads
        assert str(app.paths.config) not in reads and all(os.path.isabs(r) for r in reads)
        if sys.platform != "win32":  # Windows asks its known folders, which a fake home doesn't move
            assert {str(home / "home" / d) for d in ("Documents", "Downloads", "Pictures/Screenshots")} <= set(reads)
        assert not {str(home / "home" / d) for d in ("Documents", "Downloads")} & set(writes)  # read-only
        for words in ("Kurooto's tools", "Documents, Downloads", "course files", "stay read-only", "latexmk", "git"):
            assert words in CONSENT, words
        # the user's own choices stay: their rules, and a non-workspace setting they made themselves
        f = settings(home)
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps({"nonWorkspaceFileAccess": "deny", "permissions": {"allow": ["command(sed)"]}}))
        assert connect_tools(app, AGENT)[0]
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["nonWorkspaceFileAccess"] == "deny" and data["allowNonWorkspaceAccess"] is True
        assert data["permissions"]["allow"] == ["command(sed)", *rules]
    finally:
        app.close()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="XDG user dirs are Linux's")
def test_user_folders_follow_xdg(home, monkeypatch, tmp_path):
    from kurooto.core import places

    cfg = tmp_path / "xdg"
    cfg.mkdir()
    docs = tmp_path / "Dokumente"
    docs.mkdir()
    (cfg / "user-dirs.dirs").write_text(f'XDG_DOCUMENTS_DIR="{docs}"\nXDG_DOWNLOAD_DIR="$HOME/Nope"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    assert places.user_folder("documents") == docs
    assert places.user_folder("downloads") is None  # named, but not there
    assert places.screenshots() is None


@pytest.mark.skipif(os.name == "nt", reason="a POSIX script stands in for an installed agy")
def test_agy_asks_again_before_more_permissions(home, monkeypatch, tmp_path):
    app = App()
    try:
        monkeypatch.setenv("FAKE_AGENT_LOG", str(tmp_path / "agy.log"))
        monkeypatch.setenv("KUROOTO_AGY_TOOLS", "1")
        exe = tmp_path / "agy"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{AGENT[1]}" "$@"\n', encoding="utf-8")
        exe.chmod(0o755)
        f = app.paths.state / "agy-tools.json"  # connected by an earlier 0.2 build: only mcp(kurooto/*)
        f.write_text(json.dumps({"command": mcp.command(persistent=True), "ok": True}), encoding="utf-8")
        tools_once(app, Agy(exe=str(exe)))
        (q,) = app.ask.pending()
        assert q["text"] == CONSENT and not (tmp_path / "agy.log").exists()
        app.ask.answer(q["id"], "Approve")
        assert ALLOW in settings(home).read_text(encoding="utf-8")
        assert set(wanted_rules(app)) <= set(json.loads(f.read_text(encoding="utf-8"))["granted"])
        tools_once(app, Agy(exe=str(exe)))
        assert not app.ask.pending() and len(log_of(tmp_path / "agy.log")) == 1
    finally:
        app.close()


def test_add_ons_skills_become_writable_and_agy_is_asked_again(home, monkeypatch, tmp_path):
    from kurooto.core import places

    addons = tmp_path / "addons"
    (addons / "skills").mkdir(parents=True)
    (addons / "modules").mkdir()
    app = App()
    try:
        before = set(wanted_rules(app))
        app.settings.set("overlay.path", str(addons))
        app.settings.set("modules.enabled", ["overlay"])
        assert places.write_roots(app)[-1] == addons / "skills"
        assert f"write_file({addons / 'skills'})" in set(wanted_rules(app)) - before
        assert f"write_file({addons / 'modules'})" not in wanted_rules(app)  # never its code
    finally:
        app.close()
