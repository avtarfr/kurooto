"""Claude Code as a brain: the permissions each run is given (the same reach as agy's allow-list), what it makes of
the answer, and the command it's started with. No real Claude Code: fakes."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

from kurooto.providers.base import Task, Verdict
from kurooto.providers.claude import LIMIT_RESET, ClaudeCode, permissions, rule_path


@pytest.fixture
def app(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


@pytest.mark.skipif(sys.platform == "win32", reason="a POSIX path means another drive's folder on Windows")
def test_rule_paths_are_the_form_claude_code_reads():
    assert rule_path("/home/me/notes") == "//home/me/notes"
    assert rule_path("/home/me/notes/") == "//home/me/notes"


def test_rule_paths_on_windows_name_the_drive_first(monkeypatch):
    from kurooto.providers import claude

    monkeypatch.setattr(claude.os.path, "abspath", lambda p: str(p))  # the path as given, as on Windows
    assert claude.rule_path("C:\\Users\\me\\Notes") == "//c/Users/me/Notes"
    assert claude.rule_path("D:\\") == "//d"


def test_a_run_may_write_in_notes_and_read_documents_but_not_write_there(app, tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    task = Task(prompt="x", mcp=["kurooto", "mcp"], cwd=app.workspace)
    cfg, dirs = permissions(app, task)
    p = cfg["permissions"]
    assert p["defaultMode"] == "dontAsk"
    notes = rule_path(app.workspace)
    assert f"Edit({notes}/**)" in p["allow"] and f"Read({notes}/**)" in p["allow"]
    assert not any(r.startswith("Edit(") and "Documents" in r for r in p["allow"])
    assert "Bash(ls *)" in p["allow"]
    # nothing that can start another program through its arguments (a prompt hidden in a mail mustn't run code)
    for risky in ("latexmk", "find", "git", "rg", "sort"):
        assert not any(r in (f"Bash({risky})", f"Bash({risky} *)") for r in p["allow"]), risky
    assert "WebFetch" in p["allow"] and "mcp__kurooto" in p["allow"]
    assert "Bash(kurooto *)" in p["deny"] and "Bash(kurooto)" in p["deny"]
    assert not any(r.startswith("Bash(sed") or r.startswith("Bash(rm") for r in p["allow"])
    assert str(app.workspace) in dirs or Path(app.workspace).resolve() in [Path(d).resolve() for d in dirs]


def test_a_job_s_pictures_can_be_read_and_nothing_else_beside_them(app, tmp_path):
    """(0.8.17) Interest's screenshot sat outside every folder it could read: opening it was denied every time."""
    shots = tmp_path / "interest"
    shots.mkdir()
    pic, other = shots / "look-1.jpg", shots / "look-0.jpg"
    pic.write_bytes(b"\xff\xd8")
    other.write_bytes(b"\xff\xd8")
    cfg, dirs = permissions(app, Task(prompt="x", images=[pic]))
    allow = cfg["permissions"]["allow"]
    assert f"Read({rule_path(pic)})" in allow and shots in [Path(d) for d in dirs]
    assert f"Read({rule_path(other)})" not in allow and f"Read({rule_path(shots)}/**)" not in allow
    cfg, dirs = permissions(app, Task(prompt="x", images=[tmp_path / "gone.jpg"]))  # a file that's gone: nothing
    assert not any("gone.jpg" in r for r in cfg["permissions"]["allow"])


def test_no_kurooto_tools_unless_the_run_has_them(app):
    cfg, _ = permissions(app, Task(prompt="x"))
    assert "mcp__kurooto" not in cfg["permissions"]["allow"]


def test_command_line_has_its_files_and_nothing_of_yours(app, tmp_path):
    c = ClaudeCode(exe="claude", app=app)
    t = Task(prompt="hi", effort="high", context="Who they are. " * 5000, mcp=["kurooto", "mcp"])
    a = c.args(t, tmp_path)
    assert a[a.index("--setting-sources") + 1] == "" and a[a.index("--permission-mode") + 1] == "dontAsk"
    assert "--no-session-persistence" in a and "--strict-mcp-config" in a
    assert a[a.index("--effort") + 1] == "high" and a[a.index("--model") + 1] == "sonnet"
    assert Path(a[a.index("--append-system-prompt-file") + 1]).read_text(encoding="utf-8").startswith("Who they are.")
    assert not any(len(x) > 5000 for x in a)  # a long context isn't on the command line
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
    assert "mcpServers" in json.loads((tmp_path / "mcp.json").read_text(encoding="utf-8"))


def test_models_can_be_changed_per_level(app, tmp_path):
    c = ClaudeCode(models={"low": "claude-haiku-5-5", "high": ""}, exe="claude", app=app)
    low = c.args(Task(prompt="x", effort="low"), tmp_path)
    high = c.args(Task(prompt="x", effort="high"), tmp_path)
    assert low[low.index("--model") + 1] == "claude-haiku-5-5" and high[high.index("--model") + 1] == "sonnet"


def test_text_only_runs_get_no_tools_at_all(app, tmp_path):
    a = ClaudeCode(exe="claude", app=app).args(Task(prompt="x", text_only=True, mcp=["kurooto", "mcp"]), tmp_path)
    assert a[a.index("--tools") + 1] == "" and "--settings" not in a and "--mcp-config" not in a


class R:
    def __init__(self, data, code=0, err=""):
        self.out, self.code, self.err = json.dumps(data), code, err


def test_an_answer_with_a_refused_tool_still_counts_and_names_it():
    d = {"type": "result", "is_error": False, "result": "Done.", "permission_denials": [{"tool_name": "Bash"}]}
    r = ClaudeCode(exe="claude").verdict(R(d), 1.0, 15)
    assert r.verdict == Verdict.OK and r.usage["denied"] == ["Bash"]


def test_no_answer_after_a_refusal_is_denied_not_empty():
    d = {"type": "result", "is_error": False, "result": "", "permission_denials": [{"tool_name": "Write"}]}
    r = ClaudeCode(exe="claude").verdict(R(d), 1.0, 15)
    assert r.verdict == Verdict.DENIED and "Write" in r.detail
    assert ClaudeCode(exe="claude").verdict(R({"type": "result", "result": ""}), 1.0, 15).verdict == Verdict.EMPTY


def test_a_usage_limit_says_when_it_resets():
    at = int(time.time()) + 3600
    d = {"type": "result", "is_error": True, "result": f"Claude AI usage limit reached|{at}"}
    r = ClaudeCode(exe="claude").verdict(R(d, 1), 1.0, 15)
    assert r.verdict == Verdict.RATE_LIMITED and 3500 < r.retry_after_s <= 3600
    assert LIMIT_RESET.search("usage limit reached|1792650606")


def test_signed_out_is_auth():
    d = {"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}
    assert ClaudeCode(exe="claude").verdict(R(d, 1), 1.0, 15).verdict == Verdict.AUTH


def test_your_own_gbrain_goes_to_claude_like_it_goes_to_agy(app, tmp_path, monkeypatch):
    from kurooto.providers import agy, claude

    exe = tmp_path / "gbrain"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")

    class GB:
        def setting(self, k):
            return {"mcp_surface": "starter"}.get(k)

        def exe(self):
            return str(exe)

        def brain_home(self):
            return tmp_path / "brain"

    monkeypatch.setattr(agy, "gbrain_mcp", lambda a: GB())
    task = Task(prompt="x", mcp=["kurooto", "mcp"])
    servers = claude.mcp_servers(app, task)
    assert set(servers) == {"kurooto", "gbrain"}
    assert servers["gbrain"]["args"][-2:] == ["--surface", "starter"]
    assert servers["gbrain"]["env"] == {"GBRAIN_HOME": str(tmp_path / "brain")}
    assert "mcp__gbrain" in permissions(app, task)[0]["permissions"]["allow"]


def test_your_own_scripts_are_allowed_by_path_but_never_a_shell_or_interpreter(app, tmp_path):
    from kurooto.providers.agy import safe_scripts, wanted_rules

    ext = ".cmd" if os.name == "nt" else ""  # on Windows a program is known by its extension
    mine = tmp_path / f"make-figures{ext}"
    mine.write_text("#!/bin/sh\necho ok\n")
    mine.chmod(0o755)
    shell = tmp_path / f"bash{ext}"
    shell.write_text("#!/bin/sh\n")
    shell.chmod(0o755)
    plain = tmp_path / "notes.txt"
    plain.write_text("x")
    app.settings.set("agents.scripts", [str(mine), str(shell), str(plain), "relative/script"])
    assert [f for f, _ in safe_scripts(app)] == [mine]  # an interpreter, a file that won't run, a relative path: no
    cfg, _ = permissions(app, Task(prompt="x", cwd=app.workspace))
    assert f"Bash({mine})" in cfg["permissions"]["allow"] and f"Bash({mine} *)" in cfg["permissions"]["allow"]
    assert not any(str(shell) in r or str(plain) in r for r in cfg["permissions"]["allow"])
    assert f"command({mine})" in wanted_rules(app)
