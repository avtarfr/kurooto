"""Kurooto Terminal in kitty (Linux and macOS): a kitty.conf with Kurooto's colours and your settings, and a session
file with the tabs. Both are made again in Kurooto's own folder every time it opens. Your own kitty.conf is read
first (so your fonts and keys still apply) and is never changed.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from kurooto.modules.terminal.look import kitty_theme
from kurooto.modules.terminal.plan import KITTY_GOOD, Plan, Tab

CLASS = "kurooto"  # the window's class (X11) or app id (Wayland), for your window manager's rules
TRAIL = (0, 37)  # the cursor trail
FOCUS_TAB = (0, 44)  # sessions can pick the tab that opens first


def user_conf(home: Path | None = None, env: dict | None = None, os_: str = "linux") -> Path | None:
    """Your own kitty.conf, where kitty itself would look for it."""
    home, env = home or Path.home(), os.environ if env is None else env
    found = []
    if env.get("KITTY_CONFIG_DIRECTORY"):
        found.append(Path(env["KITTY_CONFIG_DIRECTORY"]) / "kitty.conf")
    xdg = env.get("XDG_CONFIG_HOME")
    if xdg and os.path.isabs(xdg):
        found.append(Path(xdg) / "kitty" / "kitty.conf")
    found.append(home / ".config" / "kitty" / "kitty.conf")
    if os_ == "macos":
        found.append(home / "Library" / "Preferences" / "kitty" / "kitty.conf")
    return next((f for f in found if f.is_file()), None)


def conf(plan: Plan, colours: dict[str, str]) -> str:
    v = plan.version or ()
    lines = [
        "# Kurooto Terminal's kitty settings, made by `kurooto term` from Kurooto's colours and your settings.",
        "# They're made again every time, so edits here don't last: use Kurooto's Settings (Kurooto Terminal).",
        f"font_size {plan.font_size:g}",
        "cursor_shape beam",
        *(["cursor_trail 1"] if v >= TRAIL else []),
        "window_padding_width 6",
        "remember_window_size no",
        "initial_window_width 150c",
        "initial_window_height 42c",
        "confirm_os_window_close 0",
        "enable_audio_bell no",
        f"shell {shlex.join(plan.shell)}" if plan.shell else "shell .",
        "enabled_layouts splits,stack",
        "tab_bar_edge top",
        "tab_bar_style separator",
        'tab_separator ""',
        'tab_title_template " {index} {title} "',
        "active_tab_font_style bold",
        "inactive_tab_font_style normal",
    ]
    if plan.os != "macos":  # on a Mac, Cmd+1 to Cmd+9 already switch tabs (Option+number types characters)
        lines += [f"map alt+{i} goto_tab {i}" for i in range(1, 10)]
    return "\n".join(lines) + "\n\n# colours\n" + kitty_theme(colours)


def _launch(t: Tab, extra: str = "") -> str:
    hold = " --hold" if t.hold else ""
    return f"launch --title {shlex.quote(t.title)} --cwd {shlex.quote(t.cwd)}{hold}{extra} {shlex.join(t.argv)}"


def session(plan: Plan) -> str:
    """The tabs, in order; `kurooto top` as a column on the left of the first one, like the dashboard."""
    v = plan.version or ()
    lines = ["# Kurooto Terminal's tabs, made by `kurooto term` from your settings every time it opens."]
    for i, t in enumerate(plan.tabs):
        lines.append(f"new_tab {t.title}")
        if i == 0 and plan.top is not None:
            lines.append("layout splits")
            lines.append(_launch(plan.top))
            lines.append(_launch(t, " --location=vsplit" + (" --bias=68" if v >= KITTY_GOOD else "")))
            lines.append("focus")
        else:
            lines.append(_launch(t))
    if v >= FOCUS_TAB:
        lines.append("focus_tab 0")
    return "\n".join(lines) + "\n"


def _configs(conf_file: Path, mine: Path | None) -> list[str]:
    return (["--config", str(mine)] if mine else []) + ["--config", str(conf_file)]


def command(exe: str, conf_file: Path, session_file: Path, mine: Path | None = None) -> list[str]:
    """The whole window: every tab."""
    return [exe, *_configs(conf_file, mine), "--class", CLASS, "--title", "Kurooto", "--session", str(session_file)]


def one(
    exe: str,
    conf_file: Path,
    argv: list[str],
    mine: Path | None = None,
    title: str = "",
    cwd: str = "",
    hold: bool = False,
) -> list[str]:
    """One window in Kurooto's colours running a command, or your shell (what "default terminal" launches use)."""
    cmd = [exe, *_configs(conf_file, mine), "--class", CLASS]
    if title:
        cmd += ["--title", title]
    if cwd:
        cmd += ["--directory", cwd]
    if hold:
        cmd.append("--hold")
    return cmd + list(argv)
