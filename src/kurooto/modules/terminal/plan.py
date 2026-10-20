"""What Kurooto Terminal opens, worked out from your settings: its tabs (your AI's own program, your shell, Kurooto
chat, Kurooto's log, and `kurooto top` as a column beside the first tab), which shell, and which terminal program
draws them. Nothing here starts anything or writes anything.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from kurooto.core import proc
from kurooto.core.state import jload

TABS = ("agent", "shell", "chat", "logs", "top")
DEFAULT_TABS = ["agent", "shell", "chat", "logs"]
AGENTS = ("agy", "codex", "claude")  # AI programs with a terminal of their own
LOGIN_SHELLS = ("bash", "zsh", "fish", "ksh", "sh", "dash", "tcsh", "csh")
KITTY_GOOD = (0, 36)  # kitty from 0.36 sizes the column (launch --bias); older ones still work, half and half
# Linux terminals Kurooto can use without kitty (one window per tab), and how each takes a command to run
LINUX_TERMINALS = {
    "x-terminal-emulator": ["-e"],
    "gnome-terminal": ["--"],
    "konsole": ["-e"],
    "xfce4-terminal": ["-x"],
    "alacritty": ["-e"],
    "wezterm": ["start", "--"],
    "foot": [],
    "xterm": ["-e"],
}
Which = Callable[[str, list[Path]], "str | None"]


@dataclass
class Tab:
    key: str  # agent, shell, chat, logs or top
    title: str  # what the tab says: agy, fish, kurooto, logs, top
    argv: list[str]
    cwd: str
    hold: bool = False  # kitty: when the program ends, stay open at a shell prompt


@dataclass
class Plan:
    os: str  # linux, macos or windows
    tabs: list[Tab]
    top: Tab | None = None  # `kurooto top` as a column on the left of the first tab
    shell: list[str] = field(default_factory=list)
    terminal: str = ""  # kitty, wt (Windows Terminal), console, terminal-app (macOS), a Linux terminal, or ""
    exe: str = ""
    version: tuple = ()
    font_size: float = 11.0
    palette: str = "kuro"
    notes: list[str] = field(default_factory=list)  # what to tell you (something missing, a fallback)


def os_name(platform: str | None = None) -> str:
    return {"win32": "windows", "darwin": "macos"}.get(platform or sys.platform, "linux")


def _console(python: str) -> str:
    """python.exe, not pythonw.exe: a tab needs a program that talks to its terminal."""
    exe = Path(python)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return str(exe)


def kurooto_argv(*args: str, app_dir: Path | None = None) -> list[str]:
    """How a tab, a launcher or Windows Terminal runs a `kurooto` command: through the installed launcher, so it's
    always the current version (even after an update); otherwise this Python (a developer's install)."""
    if app_dir is None:
        from kurooto.core.paths import paths

        app_dir = paths().app
    python = (jload(app_dir / "install.json", {}) or {}).get("python")
    if python and (app_dir / "launcher.py").is_file():
        return [_console(python), str(app_dir / "launcher.py"), "cli", *args]
    return [_console(sys.executable), "-m", "kurooto", *args]


def _prereq_dirs(key: str, app_dir: Path, os_: str) -> list[Path]:
    from kurooto.core.prereqs import Prereqs

    item = Prereqs(app_dir, app_dir, os=os_).items.get(key)
    return list(item.dirs) if item else []


def login_shell() -> str:
    """Your own shell: $SHELL, else the one your account logs in with."""
    sh = os.environ.get("SHELL", "")
    if not sh:
        try:
            import pwd

            sh = pwd.getpwuid(os.getuid()).pw_shell
        except (ImportError, KeyError, OSError, AttributeError):
            sh = ""
    return sh or shutil.which("bash") or "/bin/sh"


def program_name(exe: str) -> str:
    """fish for /usr/bin/fish, pwsh for C:\\...\\pwsh.exe (either kind of path, on any OS)."""
    return PureWindowsPath(exe).name.lower().removesuffix(".exe")


def shell_argv(exe: str) -> list[str]:
    name = program_name(exe)
    if name in ("pwsh", "powershell"):
        return [exe, "-NoLogo"]
    return [exe, "-l"] if name in LOGIN_SHELLS else [exe]


def find_shell(
    choice: str, os_: str, app_dir: Path, which: Which = proc.which, login: Callable[[], str] = login_shell
) -> tuple[list[str], str]:
    """The shell for the shell tab, and a note when the one asked for isn't there. "auto": fish if you have it,
    otherwise your own shell (PowerShell on Windows)."""
    choice = (choice or "auto").strip()
    if os_ == "windows":
        if choice not in ("auto", "fish"):
            exe = which(choice, [])
            if exe:
                return shell_argv(exe), ""
        exe = which("pwsh", []) or which("powershell", []) or "powershell.exe"
        note = "" if choice in ("auto", "fish") else f"{choice} isn't installed; using PowerShell."
        return shell_argv(exe), note
    if choice in ("auto", "fish"):
        fish = which("fish", _prereq_dirs("fish", app_dir, os_))
        if fish:
            return shell_argv(fish), ""
        own = login()
        if choice == "auto":
            return shell_argv(own), ""
        hint = " (`kurooto term --install` gets it)" if os_ == "linux" else ""
        return shell_argv(own), f"fish isn't installed{hint}; using {program_name(own)}."
    exe = which(choice, []) or (choice if os.path.isabs(choice) and os.path.isfile(choice) else None)
    if exe:
        return shell_argv(exe), ""
    own = login()
    return shell_argv(own), f"{choice} isn't installed; using {program_name(own)}."


def find_agent(settings, app_dir: Path, os_: str, which: Which = proc.which) -> tuple[str, list[str]] | None:
    """Your AI's own program: the one Kurooto uses if it's agy, Codex or Claude Code, else agy if it's installed."""
    from kurooto.providers.agy import install_dirs

    main = settings.get("brain.main") or ""
    dirs = {
        "agy": install_dirs(),
        "codex": [Path.home() / ".local" / "bin", app_dir / "npm", app_dir / "npm" / "bin"],
        "claude": [Path.home() / ".local" / "bin"],
    }
    for key in [main] if main in AGENTS else ["agy"]:
        exe = which(key, dirs[key])
        if exe:
            return key, (proc.resolve_cmd_shim(exe) if os_ == "windows" else [exe])
    return None


def _in(folder: Path, name: str) -> str | None:
    """A program in this one folder (not on PATH)."""
    p = Path(folder) / name
    return str(p) if p.is_file() and os.access(p, os.X_OK) else None


def kitty_version(exe: str) -> tuple:
    """kitty's version as numbers, (0, 49, 2); () if it doesn't answer."""
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ()
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out or "")
    return tuple(int(x) for x in m.groups()) if m else ()


def find_kitty(
    app_dir: Path, os_: str, which: Which = proc.which, version_of: Callable[[str], tuple] = kitty_version
) -> tuple[str, tuple]:
    """Your kitty if you have one, else Kurooto's own copy. A kitty too old for the layout loses to Kurooto's copy
    when that's there too."""
    found: list[str] = []
    for hit in [which("kitty", []), *(_in(d, "kitty") for d in _prereq_dirs("kitty", app_dir, os_))]:
        if hit and hit not in found:
            found.append(hit)
    best = ("", ())
    for exe in found:
        v = version_of(exe) or ()
        if v >= KITTY_GOOD:
            return exe, v
        if not best[0]:
            best = (exe, v)
    return best


def find_terminal(
    os_: str,
    use_kitty: bool,
    app_dir: Path,
    which: Which = proc.which,
    version_of: Callable[[str], tuple] = kitty_version,
    env: dict | None = None,
) -> tuple[str, str, tuple, list[str]]:
    """(kind, program, kitty version, notes): which terminal program draws Kurooto Terminal."""
    notes: list[str] = []
    if os_ == "windows":
        env = os.environ if env is None else env
        local = Path(env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        wt = which("wt", [local / "Microsoft" / "WindowsApps"])
        if wt:
            return "wt", wt, (), notes
        notes.append(
            "Windows Terminal isn't installed, so each tab opens in a window of its own. Get it free from the "
            "Microsoft Store (https://aka.ms/terminal), then run kurooto term again."
        )
        return "console", "", (), notes
    if use_kitty:
        exe, v = find_kitty(app_dir, os_, which, version_of)
        if exe:
            if v and v < KITTY_GOOD:
                notes.append(
                    f"Your kitty is {'.'.join(map(str, v))}; from 0.36 the status column gets its proper width "
                    "(`kurooto term --install` gets a current one into Kurooto's folder)."
                )
            return "kitty", exe, v, notes
        notes.append(
            "kitty isn't installed, so each tab opens in a window of its own. `kurooto term --install` gets the "
            "official kitty into Kurooto's folder (no admin needed)."
        )
    if os_ == "macos":
        return "terminal-app", "osascript", (), notes
    for name in LINUX_TERMINALS:
        exe = which(name, [])
        if exe:
            return name, exe, (), notes
    notes.append("No terminal program found. Install kitty: kurooto term --install")
    return "", "", (), notes


def _list_setting(value) -> list[str]:
    if not isinstance(value, list):
        return list(DEFAULT_TABS)
    out: list[str] = []
    for v in value:
        if isinstance(v, str) and v.strip().lower() in TABS and v.strip().lower() not in out:
            out.append(v.strip().lower())
    return out or ["shell"]


def font_size(value) -> float:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return 11.0
    return size if 6 <= size <= 40 else 11.0


def build(
    settings,
    app_dir: Path,
    workspace: Path,
    os_: str | None = None,
    which: Which = proc.which,
    version_of: Callable[[str], tuple] = kitty_version,
    login: Callable[[], str] = login_shell,
    home: Path | None = None,
    env: dict | None = None,
    no_kitty: bool = False,
) -> Plan:
    """The whole plan from your settings (terminal.tabs, .top, .shell, .font_size, .kitty)."""
    os_ = os_ or os_name()
    home = home or Path.home()

    def s(key, default=None):
        return settings.get(f"terminal.{key}", default)

    keys = _list_setting(s("tabs", DEFAULT_TABS))
    top_where = str(s("top", "left") or "off").lower()
    if top_where == "tab" and "top" not in keys:
        keys.append("top")
    shell, shell_note = find_shell(str(s("shell", "auto") or "auto"), os_, app_dir, which, login)
    use_kitty = bool(s("kitty", True)) and not no_kitty
    kind, exe, version, notes = find_terminal(os_, use_kitty, app_dir, which, version_of, env)
    name = (settings.get("you.assistant_name") or "Kurooto").strip().lower() or "kurooto"
    plan = Plan(os_, [], shell=shell, terminal=kind, exe=exe, version=version, notes=notes)
    plan.font_size = font_size(s("font_size", 11))
    plan.palette = settings.get("look.palette") or "kuro"
    if shell_note:
        plan.notes.append(shell_note)

    def tab(key: str) -> Tab | None:
        if key == "agent":
            found = find_agent(settings, app_dir, os_, which)
            if not found:
                plan.notes.append("No AI program (agy, Codex or Claude Code) is installed, so there's no tab for it.")
                return None
            return Tab("agent", found[0], found[1], str(workspace), hold=True)
        if key == "shell":
            return Tab("shell", program_name(shell[0]), shell, str(home))
        if key == "chat":
            return Tab("chat", name, kurooto_argv("ask", app_dir=app_dir), str(home), hold=True)
        if key == "logs":
            return Tab("logs", "logs", kurooto_argv("logs", "-f", app_dir=app_dir), str(home), hold=True)
        return Tab("top", "top", kurooto_argv("top", app_dir=app_dir), str(home))

    for key in keys:
        t = tab(key)
        if t:
            plan.tabs.append(t)
    if top_where == "left" and "top" not in keys:
        plan.top = tab("top")
        if not plan.tabs:  # nothing to stand beside: top gets the tab
            plan.tabs, plan.top = [plan.top], None
    if not plan.tabs:
        plan.tabs.append(tab("shell"))
    return plan


def describe(plan: Plan) -> list[str]:
    """The plan in a few lines, for `kurooto term --print`."""
    what = {
        "kitty": f"kitty {'.'.join(map(str, plan.version))}".rstrip(),
        "wt": "Windows Terminal",
        "console": "console windows",
        "terminal-app": "Terminal (one window per tab)",
        "": "no terminal program",
    }.get(plan.terminal, f"{plan.terminal} (one window per tab)")
    out = [f"Kurooto Terminal on {plan.os}: {what} {plan.exe}".rstrip(), f"shell: {' '.join(plan.shell)}"]
    for i, t in enumerate(plan.tabs, 1):
        beside = "   (kurooto top beside it)" if i == 1 and plan.top else ""
        out.append(f"  {i} {t.title:<9} {' '.join(t.argv)}   in {t.cwd}{beside}")
    out += [f"note: {n}" for n in plan.notes]
    return out
