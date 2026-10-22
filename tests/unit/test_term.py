"""Kurooto Terminal (modules/terminal): the plan, the colours and the chat look, kitty's files and Windows Terminal's
fragment, for every OS. Pure functions with fake programs: nothing here starts a terminal or writes outside tmp_path.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from kurooto.modules.terminal import kitty, look, wt
from kurooto.modules.terminal.plan import Plan, Tab, build, describe, find_kitty, find_shell, kurooto_argv


class S:
    """Settings: dotted keys over the module's defaults."""

    def __init__(self, **kw):
        from kurooto.modules.terminal import KurootoTerminal  # noqa: F401 (registers terminal.* defaults)

        self.v = {k.replace("__", "."): v for k, v in kw.items()}

    def get(self, key, default=None):
        from kurooto.core.config import _DEFAULTS

        if key in self.v:
            return self.v[key]
        sec, _, rest = key.partition(".")
        return (_DEFAULTS.get(sec) or {}).get(rest, default)


@pytest.fixture(autouse=True)
def own_home(tmp_path, monkeypatch):
    """Your real home stays out of it (programs in ~/.local and the like)."""
    monkeypatch.setenv("HOME", str(tmp_path / "realhome"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "realhome"))


def fake_which(**found):
    """which(name, dirs) that knows only these programs."""
    return lambda name, dirs: found.get(name)


def plan_for(tmp_path, os_="linux", settings=None, version=(0, 49, 2), **found):
    found = {"kitty": "/usr/bin/kitty", "fish": "/usr/bin/fish", "agy": "/home/you/.local/bin/agy", **found}
    found = {k: v for k, v in found.items() if v}
    return build(
        settings or S(),
        tmp_path / "app",
        tmp_path / "notes",
        os_=os_,
        which=fake_which(**found),
        version_of=lambda exe: version,
        login=lambda: "/bin/zsh",
        home=tmp_path / "home",
        env={"LOCALAPPDATA": str(tmp_path / "local")},
    )


# ------------------------------------------------------------------------------------------------- the plan
def test_linux_plan_is_laid_out_like_the_dashboard(tmp_path):
    p = plan_for(tmp_path)
    assert [t.title for t in p.tabs] == ["agy", "fish", "kurooto", "logs"]
    assert [t.key for t in p.tabs] == ["agent", "shell", "chat", "logs"]
    assert p.top is not None and p.top.argv[-1] == "top"
    assert p.terminal == "kitty" and p.exe == "/usr/bin/kitty"
    agent = p.tabs[0]
    assert agent.argv == ["/home/you/.local/bin/agy"] and agent.cwd == str(tmp_path / "notes") and agent.hold
    assert p.tabs[1].argv == ["/usr/bin/fish", "-l"] and not p.tabs[1].hold
    assert p.tabs[2].argv[-1] == "ask" and p.tabs[3].argv[-2:] == ["logs", "-f"]
    assert p.notes == []


def test_tabs_top_and_name_follow_the_settings(tmp_path):
    s = S(terminal__tabs=["chat", "shell", "nonsense", "chat"], terminal__top="tab", you__assistant_name="Jarvis")
    p = plan_for(tmp_path, settings=s)
    assert [t.key for t in p.tabs] == ["chat", "shell", "top"] and p.top is None
    assert p.tabs[0].title == "jarvis"
    p = plan_for(tmp_path, settings=S(terminal__top="off"))
    assert p.top is None and "top" not in [t.key for t in p.tabs]
    p = plan_for(tmp_path, settings=S(terminal__tabs=[], terminal__top="left"))  # nothing beside: top is a tab
    assert [t.key for t in p.tabs] == ["shell"] and p.top is not None
    p = plan_for(tmp_path, settings=S(terminal__tabs=["agent"]), agy=None)  # no AI program: the top gets the tab
    assert [t.key for t in p.tabs] == ["top"] and p.top is None
    assert any("No AI program" in n for n in p.notes)


def test_agent_is_your_ai_program_else_whichever_is_installed(tmp_path):
    p = plan_for(tmp_path, settings=S(brain__main="claude"), claude="/x/claude")
    assert p.tabs[0].title == "claude" and p.tabs[0].argv == ["/x/claude"]
    p = plan_for(tmp_path, settings=S(brain__main="gemini"))  # an API brain: an installed AI program's tab
    assert p.tabs[0].title == "agy"
    p = plan_for(tmp_path, settings=S(brain__main="gemini"), agy=None, claude="/x/claude")
    assert p.tabs[0].title == "claude"


def test_shell_choice(tmp_path):
    app = tmp_path / "app"
    no_fish = fake_which()
    assert find_shell("auto", "linux", app, no_fish, lambda: "/bin/zsh") == (["/bin/zsh", "-l"], "")
    argv, note = find_shell("fish", "linux", app, no_fish, lambda: "/bin/bash")
    assert argv == ["/bin/bash", "-l"] and "kurooto term --install" in note
    argv, note = find_shell("fish", "macos", app, no_fish, lambda: "/bin/zsh")
    assert argv == ["/bin/zsh", "-l"] and "kurooto term --install" in note  # the official fish app, on a Mac too
    assert find_shell("auto", "linux", app, fake_which(fish="/a/fish"), lambda: "/bin/zsh")[0] == ["/a/fish", "-l"]
    assert find_shell("zsh", "linux", app, fake_which(zsh="/bin/zsh"), lambda: "/bin/sh")[0] == ["/bin/zsh", "-l"]
    assert find_shell("nope", "linux", app, no_fish, lambda: "/bin/sh")[1] == "nope isn't installed; using sh."
    pw = fake_which(pwsh="C:/pwsh.exe")
    assert find_shell("auto", "windows", app, pw)[0] == ["C:/pwsh.exe", "-NoLogo"]
    ps = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    assert find_shell("auto", "windows", app, fake_which(powershell=ps))[0] == [ps, "-NoLogo"]


def test_terminal_per_os_and_fallbacks(tmp_path):
    assert plan_for(tmp_path, os_="windows", wt="C:/wt.exe").terminal == "wt"
    w = plan_for(tmp_path, os_="windows", kitty=None)
    assert w.terminal == "console" and "aka.ms/terminal" in w.notes[0]
    assert w.shell[0] == "powershell.exe"
    m = plan_for(tmp_path, os_="macos", kitty=None)
    assert m.terminal == "terminal-app" and "kurooto term --install" in m.notes[0]
    lin = plan_for(tmp_path, kitty=None, **{"gnome-terminal": "/usr/bin/gnome-terminal"})
    assert lin.terminal == "gnome-terminal"
    off = plan_for(tmp_path, settings=S(terminal__kitty=False), xterm="/usr/bin/xterm")
    assert off.terminal == "xterm" and not off.notes  # kitty turned off on purpose: nothing to say
    none = plan_for(tmp_path, kitty=None)
    assert none.terminal == "" and any("No terminal program" in n for n in none.notes)


def test_an_old_kitty_loses_to_kurootos_own_copy(tmp_path):
    own = tmp_path / "app" / "kitty" / "bin"
    own.mkdir(parents=True)
    (own / "kitty").write_text("#!/bin/sh\n")
    (own / "kitty").chmod(0o755)
    versions = {"/usr/bin/kitty": (0, 21, 2), str(own / "kitty"): (0, 49, 2)}
    exe, v = find_kitty(tmp_path / "app", "linux", fake_which(kitty="/usr/bin/kitty"), versions.get)
    assert exe == str(own / "kitty") and v == (0, 49, 2)
    exe, v = find_kitty(tmp_path / "nothing", "linux", fake_which(kitty="/usr/bin/kitty"), versions.get)
    assert exe == "/usr/bin/kitty"  # only the old one: still used
    p = plan_for(tmp_path / "x", version=(0, 30, 0))
    assert any("0.30.0" in n for n in p.notes)


def test_kurooto_commands_go_through_the_launcher_when_installed(tmp_path):
    app = tmp_path / "app"
    assert kurooto_argv("ask", app_dir=app) == [sys.executable, "-m", "kurooto", "ask"]
    app.mkdir()
    (app / "launcher.py").write_text("")
    (app / "install.json").write_text(json.dumps({"python": "/opt/py/bin/python3"}))
    assert kurooto_argv("logs", "-f", app_dir=app) == [
        str(Path("/opt/py/bin/python3")),  # as this OS writes it
        str(app / "launcher.py"),
        "cli",
        "logs",
        "-f",
    ]


def test_describe_lists_the_tabs(tmp_path):
    text = "\n".join(describe(plan_for(tmp_path)))
    assert "kitty 0.49.2" in text and "1 agy" in text and "kurooto top beside it" in text and "4 logs" in text


# ------------------------------------------------------------------------------------------------ colours
def test_palette_comes_from_the_dashboards_style_sheet():
    kuro = look.palette("kuro")
    assert kuro["bg"] == "#0b0f0a" and kuro["accent"] == "#6b8a42"  # the dark block, not the light-mode one
    rose = look.palette("rose")
    assert rose["accent"] == "#ff4e79" and rose["bg"] == "#22181a"
    assert look.palette("no-such") == kuro
    css = ':root { --bg: #000000; --fg: #ffffff; } :root[data-palette="x"] { --accent: #123456; }'
    css += ' @media (prefers-color-scheme: light) { :root[data-palette="x"] { --accent: #abcdef; } }'
    x = look.palette("x", css)
    assert x["bg"] == "#000000" and x["accent"] == "#123456" and x["lav"] == look.KURO["lav"]
    assert look.palette("kuro", "") == look.KURO  # unreadable style sheet: the built-in default


def test_scheme_kitty_theme_and_windows_terminal_scheme():
    c = look.colours("kuro")
    assert all(f"color{i}" in c for i in range(16))
    assert c["color1"] == look.KURO["bad"] and c["color2"] == look.KURO["ok"] and c["background"] == "#0b0f0a"
    theme = look.kitty_theme(c)
    assert "background              #0b0f0a" in theme and "color15" in theme and "active_tab_background" in theme
    s = look.wt_scheme(c)
    for n in look.WT_NAMES:
        assert n in s and "bright" + n[0].upper() + n[1:] in s
    assert s["name"] == "Kurooto" and s["purple"] == c["color5"] and s["brightBlack"] == c["color8"]


def test_chat_look():
    p = look.palette("kuro")
    plain = look.ChatLook(p, colour=False, unicode=True)
    assert plain.banner().startswith("  K U R O O T O   plain English, right here")
    assert '"what\'s due this week?"' in plain.banner()
    assert plain.prompt() == "kurooto ❯ "
    assert look.ChatLook(p, False, unicode=False).prompt() == "kurooto ) "
    assert look.ChatLook(p, False, True, name="Sam's helper").prompt() == "sam's helper ❯ "
    coloured = look.ChatLook(p, colour=True, unicode=True, readline=True)
    assert coloured.prompt().startswith("\001\x1b[1;38;2;166;192;122m\002") and "kurooto ❯ " in coloured.prompt()
    assert "\001" not in coloured.prompt(for_input=False)
    assert coloured.done("Set.").endswith("Set.") and "\x1b[" in coloured.done("Set.")
    assert "(failed)" in plain.answer("summarise", False, "no")


# -------------------------------------------------------------------------------------------------- kitty
def test_kitty_conf_and_session(tmp_path):
    p = plan_for(tmp_path)
    conf = kitty.conf(p, look.colours(p.palette))
    assert "font_size 11\n" in conf and "shell /usr/bin/fish -l" in conf and "cursor_trail 1" in conf
    assert "map alt+1 goto_tab 1" in conf and "color1 " in conf
    sess = kitty.session(p).splitlines()
    assert sess[1:4] == ["new_tab agy", "layout splits", sess[3]]
    assert sess[3].startswith("launch --title top --cwd ") and sess[3].endswith(" top")
    assert "--hold --location=vsplit --bias=68 /home/you/.local/bin/agy" in sess[4] and sess[5] == "focus"
    assert "new_tab kurooto" in sess and sess[-1] == "focus_tab 0"
    old = plan_for(tmp_path, version=(0, 30, 0))
    assert "cursor_trail" not in kitty.conf(old, look.colours())
    assert "--bias" not in kitty.session(old) and "focus_tab" not in kitty.session(old)
    mac = plan_for(tmp_path, os_="macos")
    assert "map alt+" not in kitty.conf(mac, look.colours())  # Cmd+number already switches tabs there


def test_kitty_session_quotes_paths(tmp_path):
    t = Tab("agent", "agy", ["/opt/My Tools/agy"], "/home/you/My Notes", hold=True)
    line = kitty.session(Plan("linux", [t], version=(0, 49, 2))).splitlines()[2]
    assert line == "launch --title agy --cwd '/home/you/My Notes' --hold '/opt/My Tools/agy'"


def test_kitty_command_reads_your_conf_first(tmp_path):
    mine = tmp_path / "home" / ".config" / "kitty" / "kitty.conf"
    assert kitty.user_conf(tmp_path / "home", {}) is None
    mine.parent.mkdir(parents=True)
    mine.write_text("font_family Iosevka\n")
    found = kitty.user_conf(tmp_path / "home", {})
    assert found == mine
    cmd = kitty.command("/usr/bin/kitty", Path("/s/kitty.conf"), Path("/s/session.kitty"), found)
    assert cmd[:5] == ["/usr/bin/kitty", "--config", str(mine), "--config", str(Path("/s/kitty.conf"))]
    assert cmd[-2:] == ["--session", str(Path("/s/session.kitty"))] and "--class" in cmd
    one = kitty.one("/k", Path("/c"), ["vim", "x"], None, "edit", "/w", hold=True)
    assert one == [
        "/k",
        "--config",
        str(Path("/c")),
        "--class",
        "kurooto",
        "--title",
        "edit",
        "--directory",
        "/w",
        "--hold",
        "vim",
        "x",
    ]


# ---------------------------------------------------------------------------------------- Windows Terminal
def test_profile_guids_follow_microsofts_scheme():
    assert wt.guid("Git Bash", "Git") == "{2ece5bfe-50ed-5f3a-ab87-5cd4baafed2b}"  # Microsoft's documented example
    assert wt.guid("Kurooto") == wt.guid("Kurooto") != wt.guid("Kurooto chat")


def windows_plan(tmp_path):
    return plan_for(tmp_path, os_="windows", wt="C:/wt.exe", pwsh="C:/Program Files/PowerShell/7/pwsh.exe")


def test_fragment(tmp_path):
    p = windows_plan(tmp_path)
    frag = fragment = wt.fragment(p, look.colours())
    names = [x["name"] for x in fragment["profiles"]]
    assert names == ["Kurooto top", "Kurooto agy", "Kurooto", "Kurooto chat", "Kurooto logs"]
    shell = next(x for x in frag["profiles"] if x["name"] == "Kurooto")
    assert shell["guid"] == wt.guid("Kurooto") and shell["colorScheme"] == "Kurooto"
    assert shell["commandline"] == '"C:/Program Files/PowerShell/7/pwsh.exe" -NoLogo'
    assert "tabTitle" not in shell  # your shell's tab follows what runs in it
    chat = next(x for x in frag["profiles"] if x["name"] == "Kurooto chat")
    assert chat["tabTitle"] == "kurooto" and chat["suppressApplicationTitle"] is True
    assert frag["schemes"][0]["name"] == "Kurooto" and len(frag["schemes"][0]) == 21
    # the shell's profile is always there: "default terminal" points at it
    p2 = plan_for(tmp_path, os_="windows", wt="C:/wt.exe", settings=S(terminal__tabs=["chat"]))
    assert "Kurooto" in [x["name"] for x in wt.fragment(p2, look.colours())["profiles"]]


def test_fragment_goes_to_wts_fragments_folder(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    f = wt.write_fragment(windows_plan(tmp_path), look.colours(), tmp_path, env)
    assert f == tmp_path / "local" / "Microsoft" / "Windows Terminal" / "Fragments" / "Kurooto" / "kurooto.json"
    assert not f.read_bytes().startswith(b"\xef\xbb\xbf") and json.loads(f.read_text())["profiles"]
    assert wt.has_fragment(tmp_path, env)
    assert wt.remove_fragment(tmp_path, env) and not f.parent.exists() and not wt.has_fragment(tmp_path, env)


def test_wt_command_lines(tmp_path):
    p = windows_plan(tmp_path)
    a = wt.args(p, profiles=True)
    line = subprocess.list2cmdline(a)
    assert line.startswith('-w new new-tab -p "Kurooto top" ; split-pane -V -s 0.68 -p "Kurooto agy" ; ')
    assert line.endswith('new-tab -p "Kurooto logs" ; focus-tab -t 0')
    bare = wt.args(p, profiles=False)  # Kurooto Terminal off: no fragment, each tab says what to run
    assert bare[:4] == ["-w", "new", "new-tab", "--title"] and "--suppressApplicationTitle" in bare
    assert "-p" not in bare and p.tabs[0].argv[0] in bare
    assert wt.one(["vim"], "edit", "C:/w") == [
        "-w",
        "new",
        "new-tab",
        "-p",
        "Kurooto",
        "--title",
        "edit",
        "-d",
        "C:/w",
        "vim",
    ]


@pytest.mark.parametrize(
    "before,after,prev",
    [
        ('{\n    "defaultProfile": "{abc}",\n    "x": 1\n}', '{\n    "defaultProfile": "{K}",\n    "x": 1\n}', "{abc}"),
        (
            '// "defaultProfile": "{old}"\n{\n    "x": 1\n}',
            '// "defaultProfile": "{old}"\n{\n    "defaultProfile": "{K}",\n    "x": 1\n}',
            None,
        ),
        ("{}", '{\n    "defaultProfile": "{K}"}', None),
    ],
)
def test_default_profile_edits_only_that_value(before, after, prev):
    new, old = wt.with_default(before, "{K}")
    assert (new, old) == (after, prev)
    assert wt.current_default(new) == "{K}"
    assert wt.without_default(new, "{K}", old) == before
    assert wt.without_default(new, "{other}", old) == new  # not ours (any more): left alone
