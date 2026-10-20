"""Kurooto Terminal outside Kurooto's own folders: the app-menu launchers, "default terminal" and its undo, the
feature turned on and off, `kurooto term` itself, and kitty and fish as prerequisites. Every home folder here is a
fake one under tmp_path: nothing touches the real app menu, kitty or Windows Terminal settings.
"""

import hashlib
import json
import sys
import threading
from pathlib import Path

import pytest

from kurooto.core.prereqs import Prereqs
from kurooto.modules.terminal import defaults, launchers, wt


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "realhome"
    for k in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(k, str(home))
    for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "APPDATA", "LOCALAPPDATA", "KITTY_CONFIG_DIRECTORY"):
        monkeypatch.delenv(k, raising=False)
    return home


def with_shell(plan, argv):
    plan.shell = argv
    return plan


# --------------------------------------------------------------------------------------------- launchers
def test_desktop_entry_is_a_terminal_emulator(tmp_path):
    text = launchers.desktop_entry(["/opt/py 3/bin/python", "/app/launcher.py", "cli", "term"])
    assert "Name=Kurooto Terminal\n" in text and "Categories=System;TerminalEmulator;\n" in text
    assert 'Exec="/opt/py 3/bin/python" /app/launcher.py cli term\n' in text
    assert "X-TerminalArgExec=-e\n" in text and "X-TerminalArgDir=--dir\n" in text and "Terminal=false" in text
    assert launchers.exec_quote("50%") == "50%%"
    assert launchers.exec_quote("/a/$HOME") == '"/a/\\\\$HOME"'  # quoting rule, then the string escape


def test_launchers_per_os_in_a_fake_home(tmp_path):
    home, env = tmp_path / "h", {}
    cmd = ["/py", "/app/launcher.py", "cli", "term"]
    f = launchers.install("linux", cmd, home, env)
    assert f == home / ".local" / "share" / "applications" / "kurooto-terminal.desktop" and f.is_file()
    env2 = {"XDG_DATA_HOME": str(tmp_path / "data")}
    assert launchers.where("linux", home, env2) == tmp_path / "data" / "applications" / "kurooto-terminal.desktop"
    app = launchers.install("macos", cmd, home, env)
    assert app == home / "Applications" / "Kurooto Terminal.app"
    script = app / "Contents" / "MacOS" / "kurooto-terminal"
    assert script.read_text() == '#!/bin/sh\nexec /py /app/launcher.py cli term "$@"\n'
    assert "<string>kurooto-terminal</string>" in (app / "Contents" / "Info.plist").read_text()
    if sys.platform != "win32":
        assert script.stat().st_mode & 0o111
    assert launchers.where("windows", home, {"APPDATA": "C:/AppData/Roaming"}) == Path(
        "C:/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Kurooto Terminal.lnk"
    )
    ran = []
    launchers.install(
        "windows",
        cmd,
        home,
        {"APPDATA": str(tmp_path / "ad")},
        "C:/wt.exe",
        ["-w", "new"],
        lambda a, **k: ran.append(k),
    )
    assert ran[0]["env"]["KUROOTO_TARGET"] == "C:/wt.exe" and ran[0]["env"]["KUROOTO_ARGS"] == "-w new"
    assert launchers.remove("linux", home, env) == f and not f.exists()
    assert launchers.remove("macos", home, env) == app and not app.exists()
    assert launchers.remove("linux", home, env) is None


def test_outside_stays_inside_kurooto_home(tmp_path):
    assert launchers.outside({"KUROOTO_HOME": str(tmp_path)}) == (tmp_path / "home", {})
    home, env = launchers.outside({"PATH": "/bin"})
    assert home == Path.home() and env == {"PATH": "/bin"}


# ------------------------------------------------------------------------------------- default terminal
def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_linux_default_and_undo_when_there_was_no_list(tmp_path):
    home, state = tmp_path / "h", tmp_path / "state"
    ok, msg = defaults.apply("linux", state, home, {}, has_xdg_exec=False)
    f = home / ".config" / "xdg-terminals.list"
    assert ok and f.read_text() == "kurooto-terminal.desktop\n" and "isn't installed" in msg and "kurooto term" in msg
    assert defaults.status(state)["existed"] is False
    assert defaults.apply("linux", state, home, {}, has_xdg_exec=True)[0]  # twice: no change, no second backup
    assert not (state / "backups").exists()
    ok, msg = defaults.undo(state, home, {})
    assert ok and not f.exists() and defaults.status(state) is None


def test_linux_default_undo_puts_your_list_back_exactly(tmp_path):
    home, state = tmp_path / "h", tmp_path / "state"
    f = home / ".config" / "xdg-terminals.list"
    f.parent.mkdir(parents=True)
    f.write_text("# mine\nfoot.desktop\nkurooto-terminal.desktop\n")
    before = f.read_bytes()
    defaults.apply("linux", state, home, {}, has_xdg_exec=True)
    assert f.read_text() == "kurooto-terminal.desktop\n# mine\nfoot.desktop\n"
    assert list((state / "backups").iterdir())[0].read_bytes() == before
    defaults.undo(state, home, {})
    assert f.read_bytes() == before


def test_linux_default_undo_keeps_your_later_changes(tmp_path):
    home, state = tmp_path / "h", tmp_path / "state"
    f = home / ".config" / "xdg-terminals.list"
    f.parent.mkdir(parents=True)
    f.write_text("foot.desktop\n")
    defaults.apply("linux", state, home, {}, has_xdg_exec=True)
    f.write_text(f.read_text() + "alacritty.desktop\n")  # you changed it since
    ok, msg = defaults.undo(state, home, {})
    assert f.read_text() == "foot.desktop\nalacritty.desktop\n" and "as you left it" in msg


def wt_settings(tmp_path, text: str, bom: bool = False) -> tuple[Path, dict]:
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    f = wt.settings_files(tmp_path, env)[0]
    f.parent.mkdir(parents=True)
    f.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode())
    return f, env


def test_windows_default_needs_terminal_settings_and_kurooto_profiles(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    ok, msg = defaults.apply("windows", tmp_path / "state", tmp_path, env)
    assert not ok and "Open Windows Terminal once" in msg
    wt_settings(tmp_path, "{}")
    ok, msg = defaults.apply("windows", tmp_path / "state", tmp_path, env)
    assert not ok and "Turn on Kurooto Terminal first" in msg


def frag(tmp_path, env):
    d = wt.fragment_dir(tmp_path, env)
    d.mkdir(parents=True)
    (d / "kurooto.json").write_text("{}")


def test_windows_default_is_backed_up_and_undone_exactly(tmp_path):
    text = '// my settings\n{\n    "defaultProfile": "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}",\n    "profiles": {}\n}\n'
    f, env = wt_settings(tmp_path, text, bom=True)
    frag(tmp_path, env)
    before, state = f.read_bytes(), tmp_path / "state"
    ok, msg = defaults.apply("windows", state, tmp_path, env)
    assert ok and "backed up" in msg
    now = f.read_bytes()
    assert now.startswith(b"\xef\xbb\xbf") and wt.guid("Kurooto").encode() in now and b"// my settings" in now
    rec = defaults.status(state)
    assert Path(rec["backup"]).read_bytes() == before and rec["previous"] == "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}"
    assert defaults.apply("windows", state, tmp_path, env)[1].startswith("Kurooto is already")
    defaults.undo(state, tmp_path, env)
    assert f.read_bytes() == before and defaults.status(state) is None


def test_windows_default_undo_after_your_changes(tmp_path):
    f, env = wt_settings(tmp_path, '{\n    "copyOnSelect": false\n}\n')
    frag(tmp_path, env)
    state = tmp_path / "state"
    defaults.apply("windows", state, tmp_path, env)
    f.write_text(f.read_text().replace("false", "true"))  # you changed something else since
    ok, msg = defaults.undo(state, tmp_path, env)
    assert f.read_text() == '{\n    "copyOnSelect": true\n}\n' and "back to the one you had" in msg
    # and if you picked another default yourself, it's yours
    defaults.apply("windows", state, tmp_path, env)
    f.write_text(f.read_text().replace(wt.guid("Kurooto"), "{mine}") + " ")
    ok, msg = defaults.undo(state, tmp_path, env)
    assert "{mine}" in f.read_text() and "left alone" in msg


def test_macos_default_explains_itself(tmp_path):
    ok, msg = defaults.apply("macos", tmp_path / "state")
    assert ok and "Applications" in msg and defaults.status(tmp_path / "state")["os"] == "macos"
    assert defaults.undo(tmp_path / "state")[0] and defaults.status(tmp_path / "state") is None
    assert defaults.undo(tmp_path / "state")[1] == "Kurooto Terminal isn't your default terminal."


# ---------------------------------------------------------------------------------- the feature on and off
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    from kurooto.app import App
    from kurooto.modules.terminal import KurootoTerminal

    a = App()
    a.modules["terminal"] = KurootoTerminal(a)
    yield a
    a.close()


def settle():
    for t in threading.enumerate():
        if t.name == "terminal-sync":
            t.join(10)


@pytest.mark.skipif(sys.platform == "win32", reason="the Windows launcher is made by PowerShell")
def test_turning_it_on_and_off(app, tmp_path):
    from kurooto.modules.terminal.plan import os_name

    m = app.modules["terminal"]
    home = tmp_path / "k" / "home"  # KUROOTO_HOME keeps every launcher inside it
    ok, why = app.enable("terminal")
    assert ok, why
    settle()
    launcher = launchers.where(os_name(), home, {})
    assert launcher.exists()
    assert not (Path.home() / ".local" / "share" / "applications" / "kurooto-terminal.desktop").exists()
    app.settings.set("terminal.default", True)
    app.events.emit("setting_changed", key="terminal.default")
    settle()
    assert defaults.status(app.paths.state / "terminal") is not None
    ok, msg = m.health()
    assert "default terminal" in msg or not ok
    app.disable("terminal")
    assert not launcher.exists() and defaults.status(app.paths.state / "terminal") is None
    if os_name() == "linux":
        assert not (home / ".config" / "xdg-terminals.list").exists()


def test_settings_have_safe_defaults():
    from kurooto.core.config import _DEFAULTS
    from kurooto.modules.terminal import KurootoTerminal

    d = _DEFAULTS["terminal"]
    assert d["default"] is False and d["tabs"] == ["agent", "shell", "chat", "logs"] and d["kitty"] is True
    assert KurootoTerminal.id == "terminal" and "Stays on this computer" in KurootoTerminal.privacy


# ------------------------------------------------------------------------------------------ `kurooto term`
def test_kurooto_term_print_opens_and_writes_nothing(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    assert cli.main(["term", "--print"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Kurooto Terminal on ") and "shell:" in out and " ask " in out + " "
    assert not (tmp_path / "k" / "state" / "terminal").exists()
    assert cli.main(["term", "--print", "-e", "vim", "notes.md"]) == 0
    assert "one window: vim notes.md" in capsys.readouterr().out


def test_default_needs_the_feature_on(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    assert cli.main(["term", "--default", "on"]) == 1
    assert "Turn on Kurooto Terminal first" in capsys.readouterr().out
    assert cli.main(["term", "--default", "status"]) == 0
    assert "default terminal: no" in capsys.readouterr().out


def test_install_offer_is_asked_once(tmp_path, monkeypatch, capsys):
    from kurooto.modules.terminal import run
    from kurooto.modules.terminal.plan import Plan

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    ctx = run.Context()
    plan = with_shell(Plan("linux", [], terminal="xterm"), ["/bin/zsh"])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    asked = []
    assert run.offer(ctx, plan, lambda q: asked.append(q) or "n") is plan
    assert asked and "kitty and fish" in capsys.readouterr().out
    assert run.offer(ctx, plan, lambda q: asked.append(q) or "n") is plan and len(asked) == 1
    assert run.missing(ctx, with_shell(Plan("windows", [], terminal="wt"), ["pwsh"])) == []


def test_kurooto_ask_looks_like_the_chat_tab(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    lines = iter(["remind me at 6 to stretch", "clear"])

    def fake_input(prompt=""):
        print(prompt, end="")
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli, "say", lambda text: {"ok": True, "replies": ["Reminder set for 18:00."]})
    assert cli.plain_loop(1) == 0
    out = capsys.readouterr().out
    assert "K U R O O T O" in out and ("kurooto ❯ " in out or "kurooto ) " in out)
    assert "Reminder set for 18:00." in out and out.count("plain English, right here") == 2  # clear: again


# ---------------------------------------------------------------------------------------- prerequisites
def test_kitty_and_fish_come_from_official_releases_with_checksums(tmp_path):
    for osn in ("linux", "macos", "windows"):
        items = Prereqs(tmp_path, tmp_path, os=osn).items
        for key in ("kitty", "fish"):
            step = items[key].step
            assert step["kind"] and items[key].size_gb > 0
            for url in [step.get("url", ""), *(step.get("urls") or {}).values()]:
                assert not url or url.startswith(
                    ("https://github.com/kovidgoyal/kitty/", "https://github.com/fish-shell/")
                )
            if step["kind"] == "download-tar":
                assert set(step["urls"]) == set(step["sha256s"]) == {"amd64", "arm64"}
                assert all(len(s) == 64 for s in step["sha256s"].values())
            if step["kind"] == "download-dmg":
                assert len(step["sha256"]) == 64 and step["app"] == "kitty.app"
    assert Prereqs(tmp_path, tmp_path, os="windows").items["kitty"].step["kind"] == "none"
    assert Prereqs(tmp_path, tmp_path, os="windows").status()["kitty"]["available"] is False


def test_none_kind_says_why_without_downloading(tmp_path, monkeypatch):
    m = Prereqs(
        tmp_path / "app",
        tmp_path / "cache",
        manifest={
            "x": {
                "title": "X",
                "programs": ["no-such-program-x"],
                "install": {Prereqs(tmp_path, tmp_path).os: {"kind": "none", "why": "Not made for this."}},
            }
        },
    )
    monkeypatch.setattr(m, "_download", lambda *a, **k: pytest.fail("downloaded"))
    assert m.install("x") == (False, "Not made for this.")


def test_dmg_app_is_copied_out_of_the_disk_image(tmp_path, monkeypatch):
    """macOS: hdiutil mounts the image read-only, ditto copies the app, the image is let go (faked here)."""
    import shutil

    from kurooto.core import prereqs as pq
    from kurooto.core.proc import Result

    calls = []

    def fake_run(args, **kw):
        calls.append(args[:2])
        if args[:2] == ["hdiutil", "attach"]:
            mount = Path(args[args.index("-mountpoint") + 1])
            (mount / "kitty.app" / "Contents" / "MacOS").mkdir(parents=True)
            (mount / "kitty.app" / "Contents" / "MacOS" / "kitty").write_text("k")
        elif args[0] == "ditto":
            shutil.copytree(args[1], args[2])
        elif args[:2] == ["hdiutil", "detach"]:
            shutil.rmtree(Path(args[2]) / "kitty.app")
        return Result(0, "", "")

    monkeypatch.setattr(pq.proc, "run", fake_run)
    into = tmp_path / "app"
    Prereqs._dmg(tmp_path / "kitty.dmg", "kitty.app", into)
    assert (into / "kitty.app" / "Contents" / "MacOS" / "kitty").read_text() == "k"
    assert calls == [["hdiutil", "attach"], ["ditto", calls[1][1]], ["hdiutil", "detach"]]
    assert not (into / ".kitty.app.part").exists()


def test_fragment_json_is_valid_for_windows_terminal(tmp_path):
    """Every new profile has a name; the colour scheme defines every colour (Windows Terminal's rules)."""
    from kurooto.modules.terminal import look
    from kurooto.modules.terminal.plan import Plan, Tab

    chat = Tab("chat", "kurooto", ["C:/py.exe", "-m", "kurooto", "ask"], "C:/Users/you")
    plan = with_shell(Plan("windows", [chat]), ["C:/pwsh.exe", "-NoLogo"])
    f = wt.write_fragment(plan, look.colours("rose"), tmp_path, {"LOCALAPPDATA": str(tmp_path / "l")})
    data = json.loads(f.read_text(encoding="utf-8"))
    assert all(p["name"] and p["guid"].startswith("{") for p in data["profiles"])
    s = data["schemes"][0]
    assert {"black", "red", "green", "yellow", "blue", "purple", "cyan", "white"} <= set(s)
    assert s["background"] == look.palette("rose")["bg"]
