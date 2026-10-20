"""`kurooto term`: Kurooto Terminal, a real terminal window laid out like the dashboard's terminals.

    kurooto term                    open it: your AI's program, your shell, Kurooto chat and its log, one tab each,
                                    with `kurooto top` as a column beside the first (Alt+1 to Alt+9 switch tabs)
    kurooto term --print            what it would open, without opening anything
    kurooto term --install          get what's missing into Kurooto's folder: kitty and fish
    kurooto term --default on|off|status    make Kurooto Terminal your default terminal, or undo it
    kurooto term --shell            one window with just your shell, in Kurooto's colours (Kurooto Shell)
    kurooto term -e CMD [ARGS...]   one window in Kurooto's colours running CMD (also --title T, --dir D, --hold)

Linux and macOS: kitty, with Kurooto's colours (your own kitty if you have one, or Kurooto's copy); without kitty,
each tab opens in a window of your usual terminal. Windows: Windows Terminal (built into Windows 11); without it,
each tab opens in a console window of its own. The shell is fish if you have it, otherwise your own (PowerShell on
Windows). The files it makes live in Kurooto's state folder (terminal/).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from kurooto.core.state import jload, jsave
from kurooto.modules.terminal import defaults, kitty, look, wt
from kurooto.modules.terminal.launchers import outside
from kurooto.modules.terminal.plan import LINUX_TERMINALS, Plan, Tab, build, describe, kurooto_argv


def parsers(sub) -> None:
    t = sub.add_parser("term", help="open Kurooto Terminal: your AI, your shell, Kurooto chat and its log")
    t.add_argument("--print", action="store_true", help="show what it would open, and open nothing")
    t.add_argument("--install", action="store_true", help="get kitty and fish into Kurooto's folder")
    t.add_argument("--default", choices=["on", "off", "status"], help="make it your default terminal, or undo it")
    t.add_argument("--shell", action="store_true", help="one window with just your shell, in Kurooto's colours")
    t.add_argument("--title", default="", help=argparse.SUPPRESS)
    t.add_argument("--dir", default="", help=argparse.SUPPRESS)
    t.add_argument("--hold", action="store_true", help=argparse.SUPPRESS)
    t.add_argument("-e", dest="command", nargs=argparse.REMAINDER, help="run one command in a Kurooto window")


# ------------------------------------------------------------------------------------------------- context
class Context:
    """Settings, folders and the notes folder, read without starting Kurooto (it needn't be running)."""

    def __init__(self, p=None):
        from kurooto.app import default_workspace
        from kurooto.core.config import Settings
        from kurooto.core.paths import paths

        self.paths = p or paths()
        self.settings = Settings(self.paths.config / "settings.json")
        ws = self.settings.get("you.workspace")
        self.workspace = Path(ws) if ws else default_workspace()
        self.dir = self.paths.state / "terminal"

    def plan(self, **kw) -> Plan:
        return build(self.settings, self.paths.app, self.workspace, **kw)

    def is_on(self) -> bool:
        return "terminal" in (self.settings.get("modules.enabled") or [])


def running(ctx: Context) -> bool:
    from kurooto.core.proc import pid_alive

    pid = (jload(ctx.paths.state / "daemon.json", {}) or {}).get("pid")
    return bool(pid) and pid_alive(pid)


def colours_for(plan: Plan) -> dict[str, str]:
    return look.colours(plan.palette)


def tab_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONSTARTUP", "PYTHONINSPECT")}
    env["KUROOTO_TERMINAL"] = "1"
    return env


# ------------------------------------------------------------------------------------------------ launching
def _detached(argv: list[str], cwd: str | None = None, log: Path | None = None, wait: float = 0.0) -> str:
    """Start a program on its own (it outlives this command). "" if it's running; what went wrong if it ended
    within `wait` seconds with an error."""
    kw: dict = {"cwd": cwd or None, "env": tab_env(), "stdin": subprocess.DEVNULL, "close_fds": True}
    out = open(log, "w", encoding="utf-8") if log else subprocess.DEVNULL
    kw["stdout"] = kw["stderr"] = out
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kw["start_new_session"] = True
    try:
        p = subprocess.Popen(argv, **kw)
    except OSError as e:
        return f"couldn't start {argv[0]}: {e}"
    finally:
        if log:
            out.close()
    from kurooto.core import children

    children.keep(p.pid)  # your terminal window stays open when Kurooto stops
    if wait:
        try:
            code = p.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            return ""
        if code:
            tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:] if log else []
            return f"{Path(argv[0]).name} stopped at once ({code})" + (": " + " / ".join(tail) if tail else "")
    return ""


def kitty_files(ctx: Context, plan: Plan) -> tuple[Path, Path]:
    ctx.dir.mkdir(parents=True, exist_ok=True)
    conf, sess = ctx.dir / "kitty.conf", ctx.dir / "session.kitty"
    conf.write_text(kitty.conf(plan, colours_for(plan)), encoding="utf-8")
    sess.write_text(kitty.session(plan), encoding="utf-8")
    return conf, sess


def window_per_tab(plan: Plan) -> tuple[bool, str]:
    """No kitty or Windows Terminal: each tab in a window of its own, in the terminal this computer has."""
    tabs = ([plan.top] if plan.top else []) + plan.tabs
    if plan.terminal == "console":
        from kurooto.core import children

        for t in tabs:
            w = subprocess.Popen(t.argv, cwd=t.cwd, env=tab_env(), creationflags=subprocess.CREATE_NEW_CONSOLE)
            children.keep(w.pid)
        return True, f"Opened {len(tabs)} console windows."
    if plan.terminal == "terminal-app":
        script = 'on run argv\ntell application "Terminal"\nactivate\ndo script (item 1 of argv)\nend tell\nend run'
        import shlex

        for t in tabs:
            subprocess.run(["osascript", "-e", script, f"cd {shlex.quote(t.cwd)} && {shlex.join(t.argv)}"], timeout=20)
        return True, f"Opened {len(tabs)} Terminal windows."
    flag = LINUX_TERMINALS.get(plan.terminal)
    if flag is None:
        return False, "There's no terminal program to open it in."
    for t in tabs:
        err = _detached([plan.exe, *flag, *t.argv], cwd=t.cwd)
        if err:
            return False, err
    return True, f"Opened {len(tabs)} {plan.terminal} windows."


def launch(ctx: Context, plan: Plan) -> tuple[bool, str]:
    if plan.terminal == "kitty":
        conf, sess = kitty_files(ctx, plan)
        cmd = kitty.command(plan.exe, conf, sess, kitty.user_conf(os_=plan.os))
        err = _detached(cmd, cwd=str(Path.home()), log=ctx.dir / "kitty.log", wait=2.0)
        if not err:
            return True, "Kurooto Terminal is open."
        ok, msg = window_per_tab(ctx.plan(no_kitty=True))  # kitty itself failed (no graphics, say)
        return ok, f"kitty didn't start ({err}). {msg}"
    if plan.terminal == "wt":
        profiles = wt.has_fragment(*outside())
        if profiles:
            wt.write_fragment(plan, colours_for(plan), *outside())  # your current tabs, shell and colours
        err = _detached([plan.exe, *wt.args(plan, profiles)])
        if err:
            return False, err
        return True, "Kurooto Terminal is open." + (
            "" if profiles else " (Turn on Kurooto Terminal in the dashboard's Features for Kurooto's colours.)"
        )
    return window_per_tab(plan)


def run_one(ctx: Context, plan: Plan, argv: list[str], title: str, cwd: str, hold: bool) -> tuple[bool, str]:
    """One window in Kurooto's colours running a command (or your shell): what launches through "default
    terminal" (xdg-terminal-exec, "Open in Terminal") ask for."""
    if plan.terminal == "kitty":
        conf, _ = kitty_files(ctx, plan)
        cmd = kitty.one(plan.exe, conf, argv, kitty.user_conf(os_=plan.os), title, cwd, hold)
        err = _detached(cmd, cwd=cwd or str(Path.home()), log=ctx.dir / "kitty.log", wait=2.0)
        return (not err), err or ""
    if plan.terminal == "wt":
        err = _detached([plan.exe, *wt.one(argv, title, cwd, wt.has_fragment(*outside()))])
        return (not err), err or ""
    t = Tab("shell", title or "shell", argv or plan.shell, cwd or str(Path.home()))
    return window_per_tab(Plan(plan.os, [t], terminal=plan.terminal, exe=plan.exe))


# ------------------------------------------------------------------------------------------------ installing
def missing(ctx: Context, plan: Plan) -> list[str]:
    """What Kurooto could get for a better terminal: kitty and fish (Linux, macOS)."""
    out = []
    if plan.os != "windows" and plan.terminal != "kitty" and bool(ctx.settings.get("terminal.kitty", True)):
        out.append("kitty")
    if plan.os != "windows" and str(ctx.settings.get("terminal.shell") or "auto") in ("auto", "fish"):
        if Path(plan.shell[0]).name != "fish":
            out.append("fish")
    return out


def install(ctx: Context, keys: list[str], progress=print) -> tuple[bool, list[str]]:
    from kurooto.core.prereqs import Prereqs

    pre = Prereqs(ctx.paths.app, ctx.paths.cache)
    ok_all, lines = True, []
    for k in keys:
        ok, msg = pre.install(k, progress)
        ok_all = ok_all and ok
        lines.append(msg)
    return ok_all, lines


def offer(ctx: Context, plan: Plan, ask=input) -> Plan:
    """At a terminal: ask once whether to get kitty (and fish) for it. A no is remembered (`--install` later)."""
    keys = missing(ctx, plan)
    seen = jload(ctx.dir / "offered.json", {}) or {}
    keys = [k for k in keys if not seen.get(k)]
    if not keys or not sys.stdin.isatty():
        return plan
    what = " and ".join(keys)
    mb = {"kitty": 45 if plan.os == "linux" else 78, "fish": 3 if plan.os == "linux" else 17}
    print(
        f"Kurooto Terminal looks its best with {what}. Get the official {what} into Kurooto's own folder now "
        f"(about {sum(mb[k] for k in keys)} MB to download; no admin, nothing else on your system changes)?"
    )
    try:
        yes = ask("[y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        yes = False
    jsave(ctx.dir / "offered.json", {**seen, **dict.fromkeys(keys, True)})
    if not yes:
        print("Fine: using what's here. `kurooto term --install` gets them any time.")
        return plan
    ok, lines = install(ctx, keys)
    print("\n".join(lines))
    return ctx.plan()


# ---------------------------------------------------------------------------------------------------- main
def default_command(ctx: Context, what: str) -> int:
    from kurooto.modules.terminal import KurootoTerminal

    if what == "status":
        rec = defaults.status(ctx.dir)
        print(
            f"default terminal: {'yes' if rec else 'no'}" + (f" ({rec.get('file')})" if rec and rec.get("file") else "")
        )
        return 0
    if what == "on":
        if not ctx.is_on():
            print("Turn on Kurooto Terminal first (the dashboard's Features tab), then run this again.")
            return 1
        KurootoTerminal.files(ctx.settings, ctx.paths, ctx.workspace)
        opens = str(ctx.settings.get("terminal.default_opens") or "shell")
        ok, msg = defaults.apply(ctx.plan().os, ctx.dir, *outside(), opens=opens)
        if ok:
            ctx.settings.set("terminal.default", True)
        print(msg)
        return 0 if ok else 1
    ok, msg = defaults.undo(ctx.dir, *outside())
    ctx.settings.set("terminal.default", False)
    print(msg)
    return 0 if ok else 1


def main(a, ctx: Context | None = None) -> int:
    from kurooto.modules.terminal import KurootoTerminal  # noqa: F401 (its settings' defaults)

    ctx = ctx or Context()
    if a.default:
        return default_command(ctx, a.default)
    plan = ctx.plan()
    if a.install:
        keys = missing(ctx, plan)
        if plan.os == "windows":
            print("Nothing to get: on Windows, Kurooto Terminal uses Windows Terminal (built into Windows 11).")
            return 0
        if not keys:
            print("Everything Kurooto Terminal uses is here.")
            return 0
        ok, lines = install(ctx, keys)
        print("\n".join(lines))
        return 0 if ok else 1
    one = a.command is not None or bool(a.dir) or a.shell
    if a.print:
        print("\n".join(describe(plan)))
        if one:
            print("one window: " + " ".join(a.command or plan.shell) + (f"   in {a.dir}" if a.dir else ""))
        elif plan.terminal == "kitty":
            conf, sess = ctx.dir / "kitty.conf", ctx.dir / "session.kitty"
            print("runs: " + " ".join(kitty.command(plan.exe, conf, sess, kitty.user_conf(os_=plan.os))))
            print(f"--- {sess.name} ---\n{kitty.session(plan)}", end="")
        elif plan.terminal == "wt":
            print("runs: " + subprocess.list2cmdline([plan.exe, *wt.args(plan, wt.has_fragment(*outside()))]))
        return 0
    if one:
        ok, msg = run_one(ctx, plan, list(a.command or []), a.title, a.dir, a.hold)
        if msg:
            print(msg, file=sys.stderr)
        return 0 if ok else 1
    plan = offer(ctx, plan)
    notes = list(plan.notes)
    if any(t.key == "chat" for t in plan.tabs) and not running(ctx):
        notes.append("Kurooto isn't running, so the chat tab can't answer yet: `kurooto on` starts it.")
    ok, msg = launch(ctx, plan)
    for line in [*notes, msg]:
        print(line)
    if not sys.stdout.isatty() and (notes or not ok):  # opened from the app menu: nobody sees what's printed
        from kurooto.core import desktop

        desktop.notify("Kurooto Terminal", " ".join(notes if ok else [msg, *notes])[:400])
    try:
        from kurooto.core.events import Events

        Events(ctx.paths.state).emit("terminal_window", tabs=len(plan.tabs), terminal=plan.terminal, ok=ok)
    except OSError:
        pass
    return 0 if ok else 1


def kurooto_term_argv(app_dir: Path | None = None) -> list[str]:
    """What launchers run: `kurooto term` through the installed launcher (or this Python)."""
    return kurooto_argv("term", app_dir=app_dir)
