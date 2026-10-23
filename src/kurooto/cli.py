"""The `kurooto` command.

kurooto --version
kurooto paths            where settings, data and logs live on this machine
kurooto doctor [--json]  check that everything Kurooto needs is in place (exit code = number of problems)
kurooto setup [STEP]     open the setup page where you left off (or at one step: about, telegram…)
kurooto fixme [WORDS]    what's wrong and what to do, matched by rules (no AI): the troubleshooting page, known issues
kurooto off / on         turn Kurooto off completely (no start at sign-in) / back on
kurooto pause [2h|18:00] / resume   pause it (Telegram says "paused" and keeps what you send) / wake it
kurooto notify [--title T] [--kind K] [--urgent] [--button "Label=prefix:ref:action"]... [--click URL]
               [--reply-to ID] [--print-id] TEXT   send yourself a message through Kurooto (for scripts and tools)
kurooto ask ["plain English"]       talk to Kurooto from a terminal; quick things at once, bigger ones print later
kurooto call "reason" [--at TIME] [--alarm] [--force]   ring your phone now or later
kurooto call --list | --cancel KEY  the calls booked for later, and taking one off
kurooto mcp              Kurooto's tools for agent programs (an MCP server on stdin/stdout)
kurooto ask-me "question" [--choices "a|b|c"] [--expires 2d] [--wait [--timeout MIN]]   ask yourself something
kurooto ask-me --pending [--json] | --id ID [--wait]   the open questions; one asked earlier (wait for its answer)
kurooto ask-me "question" --then "CMD {answer}"   run a command with the answer once it comes (no shell; {id} too)
kurooto ask-approval "question" [--timeout MIN]   ask for a yes/no and wait (exit 0 yes, 1 no, 2 timeout)
kurooto send FILE [--caption T]     send yourself a file on Telegram (up to 50 MB; --to drive: Google Drive;
                                    no Telegram: a link in the phone app's chat)
kurooto note [--title T] TEXT       save a quick note to your notes' inbox (or pipe text in)
kurooto top [--once]     a status board: this computer and Kurooto (q quits)
kurooto term [--print]   Kurooto Terminal: your AI, your shell, Kurooto chat and its log in one window
kurooto logs [-f]        the end of Kurooto's log (-f: keep showing new lines)
kurooto sync [--no-wait | --status]   sync everything that's on, now (notes, Classroom, calendar, research, notes
                         brain, backup); --status: is one running, and how the last one went
kurooto usage [DAYS]     AI requests per day, and agy's own count from its logs
kurooto export-skills [on [--to agy,agents,claude] | off | status]   your skills as /commands in your agent programs
kurooto space [--clean]   what Kurooto takes, and cleaning off its own old backups and leftovers
kurooto hardware [--profile P] [--add MODEL] [--install]   what this computer suits; go past it and have it installed
kurooto backup [--to F]  make a backup now · kurooto restore <zip>  put one back (stops, restores, starts)
kurooto profile save|restore|status   your setup, encrypted in your private repository; restore on a new computer
kurooto runlog start|metric|note|end|ls   log experiment runs into your notes (research/<project>/runs/)
kurooto watch -- CMD...  run a long job; you get a message when it ends (exit code, time, last lines)
kurooto autostart on|off|status|boot|login   start at sign-in or not; boot: before anyone logs in (Linux)
kurooto idle away|back   for your idle tool (hypridle, swayidle): you've stepped away / you're back
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

from kurooto import __version__
from kurooto.core.paths import paths


def _writable(folder) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder):
            pass
        return True
    except OSError:
        return False


def doctor(as_json: bool, make_bundle: bool = False) -> int:
    """Checks; the exit code is the number of problems (notes marked "--" don't count)."""
    try:
        from kurooto import diagnostics
        from kurooto.app import App

        app = App()
    except Exception as e:  # Kurooto itself can't start: the basics only
        app, err = None, f"{type(e).__name__}: {e}"
    if app is None:
        p = paths()
        checks = [("python", sys.version_info >= (3, 12), platform.python_version()), ("kurooto", False, err)]
        checks += [
            (f"{n} folder", _writable(getattr(p, n)), str(getattr(p, n))) for n in ("config", "data", "state", "logs")
        ]
    else:
        try:
            if make_bundle:
                dest, names = diagnostics.bundle(app)
                print(f"Saved: {dest}\nInside: {', '.join(names)}\n")
                print("Secrets, names, email and web addresses and your folders are blanked out; your messages, notes")
                print("and AI requests are never included. Nothing was sent: look inside, then send it to whoever is")
                print("helping you.")
                return 0
            checks = diagnostics.checks(app)
        finally:
            app.close()
    problems = sum(1 for _, ok, _ in checks if ok is False)
    if as_json:
        print(
            json.dumps(
                {
                    "version": __version__,
                    "problems": problems,
                    "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
                },
                indent=1,
            )
        )
    else:
        for n, ok, d in checks:
            print(f"{'ok  ' if ok else '--  ' if ok is None else 'FAIL'} {n:<22} {d}")
        print("all good" if not problems else f"{problems} problem{'s' if problems > 1 else ''}")
    if make_bundle and app is None:  # the bundle needs Kurooto itself; say so instead of making nothing silently
        print(
            "\nNo diagnostics zip: Kurooto itself can't start, so it couldn't be made. Send what's above instead "
            "(look through it first).",
            file=sys.stderr,
        )
    return problems


def wait_for_web(seconds: float = 40) -> str | None:
    """The page's address once Kurooto answers on it."""
    import time
    import urllib.request

    from kurooto.core.state import jload

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        url = (jload(paths().state / "web.json", {}) or {}).get("url")
        if url:
            try:
                with urllib.request.urlopen(url + "health", timeout=3) as r:  # noqa: S310 (our own 127.0.0.1 page)
                    if r.status == 200:
                        return url
            except OSError:
                pass
        time.sleep(0.5)
    return None


def start_background() -> int:
    """Start the supervisor detached from this window (it survives closing the terminal)."""
    import subprocess

    from kurooto.core.autostart import command

    if wait_for_web(1):
        print("Kurooto is already running.")
        return 0
    from kurooto.core import autostart, pathfix

    if pathfix.allowed():
        if autostart.managed() and autostart.service("start"):
            return 0  # under systemd or launchd: started there, so stop and restarts stay consistent
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            command(),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            command(),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print("Kurooto is starting.")
    return 0


def start_and_say() -> int:
    """`kurooto start`: start it, wait until its page answers, and print the page's address."""
    url = wait_for_web(1)
    if url:
        print(f"Kurooto is already running: {url}")
        return 0
    start_background()
    url = wait_for_web(60)
    if not url:
        print("It didn't come up within a minute. Logs:", paths().logs)
        return 1
    print(f"Kurooto is running: {url}")
    return 0


def ask_running(path: str, body: dict | None = None) -> dict | None:
    """Ask the running assistant to do something through its local page. None if it isn't running."""
    import urllib.request

    from kurooto.core.secrets import Secrets

    url = wait_for_web(1)
    if not url:
        return None
    req = urllib.request.Request(  # noqa: S310 (our own 127.0.0.1 page)
        f"{url}api/{path}",
        data=json.dumps(body or {}).encode(),
        headers={"X-Kurooto": Secrets(paths().config).get("web.token") or "", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read())
    except OSError:
        return None


def ask_me(
    text: str, choices: str, expires: str, title: str, wait: bool, timeout: float, approval: bool, then: str = ""
) -> int:
    """Ask the person something through the running assistant (Telegram, desktop, phone app, the next call).
    Without --wait it prints the question's id; with --wait, the answer (exit 2 if none came in time). --then: a
    command run with the answer (after --wait here, else by a background copy of this command)."""
    if not text.strip():
        print("What's the question?", file=sys.stderr)
        return 2
    argv = then_argv(then) if then else []
    if then and not argv:
        print('--then needs a command, e.g. --then "notify-send Answer {answer}"', file=sys.stderr)
        return 2
    body = {
        "text": text,
        "choices": [c for c in (choices or "").split("|") if c.strip()],
        "kind": "approval" if approval else "question",
        "expires": expires or (f"{max(1, round(timeout))}m" if wait else ""),
        "title": title,
        "source": "cli",
    }
    r = ask_running("ask", body)
    if not r or not r.get("ok"):
        print("Kurooto isn't running (`kurooto start` starts it), so nobody was asked.", file=sys.stderr)
        return 2
    if argv and not wait:
        then_in_background(r["id"], argv, expires_minutes(expires))
        print(r["id"])
        print(f"When you answer, {argv[0]} runs with it.", file=sys.stderr)
        return 0
    if argv:
        answer = wait_open(r["id"], timeout)
        if answer is None:
            ask_running("ask/expire", {"id": r["id"]})
            print("timeout")
            return 2
        print(answer, flush=True)
        return run_then(r["id"], argv, answer, background=False)
    if not wait:
        print(r["id"])
        return 0
    return wait_answer(r["id"], timeout, approval)


def wait_answer(qid: str, timeout_min: float, approval: bool) -> int:
    """Wait for the first answer. Approvals print yes / no (exit 0 / 1); questions print the answer (exit 0).
    No answer in time prints "timeout" (exit 2), and the question is closed so a late answer isn't taken."""
    import time

    end = time.monotonic() + timeout_min * 60
    try:
        while time.monotonic() < end:
            q = (ask_running("ask/get", {"id": qid}) or {}).get("question") or {}
            if q.get("status") == "answered":
                if not approval:
                    print(q.get("answer") or "")
                    return 0
                yes = q.get("answer") == "Approve"
                print("yes" if yes else "no")
                return 0 if yes else 1
            if q.get("status") == "expired":
                break
            time.sleep(max(0.0, min(3.0, end - time.monotonic())))
    except KeyboardInterrupt:
        ask_running("ask/expire", {"id": qid})
        return 130
    ask_running("ask/expire", {"id": qid})
    print("timeout")
    return 2


def turn_off(keep_calls: bool) -> int:
    """Off completely: it stops, and doesn't start at sign-in until `kurooto on`."""
    import time

    from kurooto.core import autostart
    from kurooto.core.state import jsave

    r = ask_running("power/off", {"keep_calls": keep_calls})
    if r is not None:
        for _ in range(40):  # it shuts itself down (telling your call line first)
            if not wait_for_web(0.5):
                break
            time.sleep(0.5)
    jsave(paths().state / "off.json", {"at": time.time(), "keep_calls": keep_calls})
    if os.environ.get("KUROOTO_NO_AUTOSTART") != "1":
        autostart.disable()
    stop(quiet=True)  # anything left over
    print("Kurooto is off, and won't start when you sign in. Turn it back on with `kurooto on`, or open Kurooto")
    print("from your app menu.")
    if r is None and not keep_calls:
        print("(It wasn't running, so if you use phone calls, your call line may still place scheduled calls.)")
    return 0


def turn_on() -> int:
    """Back on: start at sign-in again, start now, open the dashboard."""
    import webbrowser

    from kurooto.core import autostart

    (paths().state / "off.json").unlink(missing_ok=True)
    managed = False
    if os.environ.get("KUROOTO_NO_AUTOSTART") != "1":
        print(autostart.enable())
        managed = bool(autostart.managed())
    url = wait_for_web(8 if managed else 1)  # under systemd or launchd, turning autostart on also started it
    if not url:
        start_background()
        url = wait_for_web(60)
    if not url:
        print("Kurooto didn't come up. Logs:", paths().logs)
        return 1
    print(f"Kurooto is on: {url}")
    if os.environ.get("KUROOTO_NO_BROWSER") != "1":
        webbrowser.open(url)
    return 0


def stop_gracefully(timeout: float = 90) -> bool:
    """Ask the running assistant to stop the normal way (what it's doing ends cleanly and its features' last steps
    run: Notes sync sends up what's left) and wait for it. Through its page, or with SIGTERM on macOS and Linux if the
    page doesn't answer. True once it has stopped (or wasn't running); False if it's still running after `timeout`
    seconds, for stop() to force."""
    import signal
    import time

    from kurooto.core import proc
    from kurooto.core.state import jload

    pid = (jload(paths().state / "daemon.json", {}) or {}).get("pid")
    if not pid or not proc.pid_alive(pid, "kurooto"):
        return True
    asked = ask_running("power/stop") is not None
    if not asked and sys.platform != "win32":
        try:
            os.kill(int(pid), signal.SIGTERM)  # the daemon treats it like a stop request
            asked = True
        except OSError:
            pass
    if not asked:
        return False
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not proc.pid_alive(pid, "kurooto"):
            return True
        time.sleep(0.25)
    return False


def stop(quiet: bool = False, graceful: bool = False) -> int:
    """Stop the supervisor (so it doesn't restart the assistant) and the assistant. graceful: ask it to stop the normal
    way first (its features' last steps run, e.g. Notes sync sends up what's left), then force what's left."""
    from kurooto.core import proc
    from kurooto.core.state import jload

    p = paths()
    stopped = False
    pid = (jload(p.state / "daemon.json", {}) or {}).get("pid")
    if graceful and pid and proc.pid_alive(pid, "kurooto") and stop_gracefully(30):
        stopped = True
    from kurooto.core import autostart, pathfix

    if pathfix.allowed():  # tests, rehearsals and portable copies never touch the real service
        if autostart.managed() and autostart.service("stop"):
            stopped = bool(jload(p.state / "daemon.json", {}))  # the manager stopped it; the loop tidies up
    for f, marker in (
        (p.app / "launcher.json", "launcher.py"),
        (p.state / "supervisor.json", "kurooto"),
        (p.state / "daemon.json", "kurooto"),
    ):
        pid = (jload(f, {}) or {}).get("pid")
        if pid and proc.pid_alive(pid, marker):
            proc.kill_tree(pid)  # the launcher or supervisor first, so nothing restarts what we stop
            stopped = True
        f.unlink(missing_ok=True)
    if not quiet:
        print("Kurooto stopped." if stopped else "Kurooto wasn't running.")
    return 0


def uninstall(keep_data: bool, revoke: bool = False) -> int:
    import shutil

    from kurooto.core import autostart

    stop()
    if revoke:  # (revoke) take back the call line, Google's grant, the bot's webhook: while the keys are still here
        from kurooto.core import leave

        if not leave.uninstall_revoke(print):
            print("Nothing was removed. `kurooto uninstall` without --revoke removes Kurooto anyway.")
            return 1
    try:  # (ws5) the copies of your skills Kurooto put in agy and other agent programs (core/agent_export.py)
        from kurooto.core import agent_export

        gone = agent_export.remove_all(paths().state, paths().config)
        if gone:
            print(f"Removed Kurooto's {len(gone)} skill copies from your agent programs; your own skills stay.")
    except Exception as e:
        print(f"Couldn't remove Kurooto's skills from your agent programs: {e}")
    if os.environ.get("KUROOTO_NO_AUTOSTART") != "1":
        print(autostart.disable())
        autostart.forget_boot(paths().state)  # lingering off again, if Kurooto turned it on
        from kurooto.core import shortcuts

        shortcuts.remove()
        from kurooto.modules.terminal import remove_everything  # Kurooto Terminal's launcher, profiles, default

        for line in remove_everything(paths()):
            print(line)
    p = paths()
    if not keep_data:
        for d in (p.config, p.data, p.state, p.cache, p.logs):
            shutil.rmtree(d, ignore_errors=True)
        print("Removed Kurooto's settings and data. Your notes folder was left alone.")
    (BIN / "kurooto").unlink(missing_ok=True)
    if sys.platform != "win32":  # on Windows, kurooto.cmd is running this; it goes after we exit (below)
        (BIN / "kurooto.cmd").unlink(missing_ok=True)
    if sys.platform == "win32":
        import subprocess
        import winreg

        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        except OSError:
            pass
        # this program is running from the app folder; remove it a moment after we exit
        # one string, not a list: cmd /c needs its own quoting rules (outer quotes stripped, inner kept)
        line = f'cmd /c "ping -n 4 127.0.0.1 >nul & del /q "{BIN / "kurooto.cmd"}" & rmdir /s /q "{p.app}""'
        subprocess.Popen(
            line, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True
        )
    elif (p.app / "launcher.py").exists():
        shutil.rmtree(p.app, ignore_errors=True)
    print("Kurooto is uninstalled. (uv and Python stay; they're harmless and other tools may use them.)")
    return 0


BIN = Path(os.environ.get("KUROOTO_BIN") or Path.home() / ".local" / "bin")  # KUROOTO_BIN: tests
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Kurooto"


def install_finish(uv: str, python: str) -> int:
    """The installer's last step, run by the newly installed version: the launcher, the `kurooto` command,
    start-at-sign-in, the entry in Windows' Apps list, then start it and open the setup page."""
    import shutil
    import time
    from importlib import resources

    from kurooto import __version__
    from kurooto.core import autostart, proc
    from kurooto.core.state import jload, jsave

    app = paths().ensure().app
    cur = (jload(app / "current.json", {}) or {}).get("version")
    if cur and cur != __version__:
        jsave(app / "previous.json", {"version": cur})
    jsave(app / "current.json", {"version": __version__})
    jsave(app / "update.json", {"phase": "ok", "to": __version__, "since": time.time()})
    jsave(app / "install.json", {"uv": uv, "python": python, "installed": time.time(), "version": __version__})
    (app / "launcher.py").write_bytes(resources.files("kurooto.update").joinpath("launcher.py").read_bytes())
    if shutil.which("uv") and proc.run(["uv", "tool", "list"], timeout=30).out.find("kurooto") >= 0:
        proc.run(["uv", "tool", "uninstall", "kurooto"], timeout=120)  # an older developer install would shadow us
    BIN.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        (BIN / "kurooto.cmd").write_text(
            f'@echo off\r\n"{python}" "{app / "launcher.py"}" cli %*\r\n', encoding="utf-8"
        )
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE) as k:
            for name, val in (
                ("DisplayName", "Kurooto"),
                ("DisplayVersion", __version__),
                ("Publisher", "avtarfr"),
                ("InstallLocation", str(app)),
                ("UninstallString", f'"{python}" "{app / "launcher.py"}" cli uninstall'),
            ):
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
    else:
        shim = BIN / "kurooto"
        shim.write_text(f'#!/bin/sh\nexec "{python}" "{app / "launcher.py"}" cli "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
    from kurooto.core import pathfix  # so `kurooto` works in new terminals even when uv was already installed

    if pathfix.allowed():
        for what in pathfix.ensure_on_path(BIN):
            print(f"  The kurooto command's folder ({BIN}) is now on the PATH ({what}).")
    if os.environ.get("KUROOTO_NO_AUTOSTART") != "1":  # tests and rehearsals leave this computer alone
        print(" ", autostart.enable())
        try:
            from kurooto.core import shortcuts

            shortcuts.create()  # "Kurooto" in the app menu: turns it on and opens the dashboard
        except Exception as e:
            print("  (no app-menu shortcut:", e, ")")
    stop()
    start_background()
    url = wait_for_web(60)
    if not url:
        print("  Kurooto didn't come up. Logs:", paths().logs)
        return 1
    print(f"  Kurooto {__version__} is running: {url}")
    if os.environ.get("KUROOTO_NO_BROWSER") != "1":
        import webbrowser

        webbrowser.open(url)
    return 0


def selftest() -> int:
    """Start everything in a throwaway folder, answer one web request, stop. Exit 0 if that worked."""
    import tempfile
    import urllib.request

    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("KUROOTO_HOME")
        os.environ["KUROOTO_HOME"] = tmp
        try:
            from kurooto.app import App
            from kurooto.web.server import start

            app = App()
            srv = start(app, port=18700 + os.getpid() % 200)
            try:
                with urllib.request.urlopen(srv.url + "health", timeout=10) as r:  # noqa: S310 (our own page)
                    ok = json.loads(r.read()).get("ok") is True
            finally:
                srv.stop()
                app.close()
        finally:
            if old is None:
                os.environ.pop("KUROOTO_HOME", None)
            else:
                os.environ["KUROOTO_HOME"] = old
    print("selftest ok" if ok else "selftest failed")
    return 0 if ok else 1


def update(now: bool) -> int:
    from kurooto.app import App

    app = App()
    try:
        if not app.updates.u.managed():
            print("This copy wasn't installed by the Kurooto installer, so it can't update itself.")
            return 1
        rel = app.updates.u.check(app.settings.get("updates.channel") or "stable")
        if not rel:
            for v, why in app.updates.u.withdrawn.items():  # on the signed yank list: never installed
                print(f"Kurooto {v} was withdrawn by its maintainer ({why}), so it isn't installed.")
            print(f"Up to date ({app.updates.u.installed()}).")
            return 0
        print(f"Kurooto {rel.version} is available.")
        if not now:
            return 0
        if not app.updates._stage(rel):
            return 1
        app.updates.u.switch(rel.version)
        print(f"Installed {rel.version}. Restarting Kurooto on it…")
    finally:
        app.close()
    stop()
    return start_background()


# ------------------------------------------------------------- top, logs, sync, backup, restore, runlog, watch
def home_parsers(sub) -> None:
    t = sub.add_parser("top", help="a status board in this terminal: this computer and Kurooto (q quits)")
    t.add_argument("--once", action="store_true", help="print one screen and exit")
    t.add_argument("--size", default="", help=argparse.SUPPRESS)
    lg = sub.add_parser("logs", help="the end of Kurooto's log")
    lg.add_argument("-f", "--follow", action="store_true", help="keep showing new lines (Ctrl+C stops)")
    lg.add_argument("-n", type=int, default=60, help="how many lines (default 60)")
    sy = sub.add_parser("sync", help="sync everything that's on, now")
    sync_flags(sy)
    bk = sub.add_parser("backup", help="make a backup now (to the backup folder, or --to another folder)")
    bk.add_argument("--to", default="", help="a folder for this one backup")
    rs = sub.add_parser("restore", help="put a backup back: stops Kurooto, restores, starts it again")
    rs.add_argument("zip")
    rs.add_argument("--yes", action="store_true", help="don't ask first")
    rs.add_argument("--no-notes", action="store_true", help="leave your notes folder alone")
    rs.add_argument("--no-start", action="store_true", help="don't start Kurooto afterwards")
    rl = sub.add_parser("runlog", help="log experiment runs into your notes (research/<project>/runs/)")
    rsub = rl.add_subparsers(dest="action", required=True)
    st = rsub.add_parser("start", help="start a run; prints its id")
    st.add_argument("project")
    st.add_argument("--name", default="")
    st.add_argument("--config", default="", help="a JSON object, e.g. '{\"lr\": 0.001}'")
    st.add_argument("--repo", default="", help="the code's folder (default: this one)")
    me = rsub.add_parser("metric", help="numbers for the run: loss=0.3 acc=0.9")
    me.add_argument("values", nargs="+")
    me.add_argument("--step", type=int)
    me.add_argument("--run", default=None)
    no = rsub.add_parser("note", help="a line in the run's notes")
    no.add_argument("text", nargs="+")
    no.add_argument("--run", default=None)
    en = rsub.add_parser("end", help="finish the run")
    en.add_argument("--status", default="ok", choices=["ok", "failed", "interrupted"])
    en.add_argument("--run", default=None)
    ls = rsub.add_parser("ls", help="the runs so far")
    ls.add_argument("project", nargs="?")
    w = sub.add_parser("watch", help="run a long job; you get a message when it ends: kurooto watch -- CMD ...")
    w.add_argument("--lines", type=int, default=10, help="how many of its last lines to send (0: none)")
    w.add_argument("--log", default="", metavar="PROJECT", help="also log it as a run of this research project")
    w.add_argument("command", nargs=argparse.REMAINDER)


def home_run(a) -> int | None:
    """Runs the commands home_parsers() added; None for any other command."""
    if a.cmd == "top":
        from kurooto import top

        return top.main(a.once, a.size)
    if a.cmd == "logs":
        from kurooto.watch import follow_log

        return follow_log(paths().logs / "kurooto.log", a.n, a.follow)
    if a.cmd == "watch":
        from kurooto import watch

        return watch.main(list(a.command), a.lines, a.log or None)
    if a.cmd == "runlog":
        from kurooto import runlog

        return runlog.main(a)
    if a.cmd == "sync":
        return sync_status() if a.status else sync_all(wait=not a.no_wait)
    if a.cmd == "backup":
        return backup_now(a.to)
    if a.cmd == "restore":
        return restore(Path(a.zip), a.yes, not a.no_notes, not a.no_start)
    return None


def sync_all(wait: bool = True) -> int:
    import time

    r = ask_running("sync/all", {"notify": not wait})
    if r is None:
        print("Kurooto isn't running (kurooto start), and the syncs run inside it.")
        return 1
    print(r.get("message", ""))
    if not r.get("ok"):
        return 0 if "already running" in r.get("message", "") else 1
    if not wait:
        print("It goes on in the background; the summary comes as a message (kurooto sync --status meanwhile).")
        return 0
    wait_for_web(1)
    for _ in range(3600):  # Classroom can take a while
        time.sleep(1)
        st = ask_running("sync/status") if wait_for_web(1) else None
        if st is None:
            from kurooto.core.state import jload

            st = jload(paths().state / "sync-all.json", {}) or None
        if st is None and not wait_for_web(1):
            print("Kurooto stopped before the sync finished.")
            return 1
        if st and not st.get("running"):
            print(st.get("text", ""))
            return 1 if "failed" in (st.get("text") or "").split("\n", 1)[0] else 0
    return 1


def _settings_secrets_workspace():
    from kurooto.app import default_workspace
    from kurooto.core.config import Settings
    from kurooto.core.secrets import Secrets

    p = paths().ensure()
    s = Settings(p.config / "settings.json")
    ws = s.get("you.workspace")
    return p, s, Secrets(p.config), Path(ws) if ws else default_workspace()


def backup_now(to: str = "") -> int:
    from kurooto.modules import backups  # registers the backup settings' defaults

    p, s, sec, ws = _settings_secrets_workspace()
    folder = Path(to).expanduser() if to else None
    if not to and not s.get("backups.folder"):
        print("No backup folder yet: dashboard → Features → Backups, or kurooto backup --to <folder>.")
        return 1
    print("Backing up…")
    try:
        ok, msg = backups.backup_now(p, s, sec, ws, folder=folder, reason="command")
    except Exception as e:
        ok, msg = False, f"{type(e).__name__}: {e}"
    print(msg if ok else f"Backup didn't work: {msg}")
    return 0 if ok else 1


def restore(zip_path: Path, yes: bool, notes: bool, start: bool) -> int:
    import time
    import zipfile

    from kurooto.modules import backups

    try:
        m = backups.read_manifest(zip_path)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        print(f"Can't restore that: {e}")
        return 1
    f = m.get("files") or {}
    print(f"A backup from {str(m.get('created', '?')).replace('T', ' ')} (Kurooto {m.get('kurooto', '?')}):")
    print(f"  settings, data and state: {f.get('config', 0) + f.get('data', 0) + f.get('state', 0)} files")
    print(
        f"  notes: {f.get('notes', 0)} files" + ("" if notes else " (left alone: --no-notes)")
        if m["has_notes"]
        else "  notes: not in this backup"
    )
    print("  passwords and keys: " + ("yes" if m["has_secrets"] else "no (sign in again afterwards)"))
    print("Kurooto's current settings and data are replaced (a copy of them is kept first). Notes are only added:")
    print("a note that's different now is kept, and the backup's copy goes to restored-<date>/ beside it.")
    if not yes:
        try:
            if input("Restore it? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing changed.")
                return 1
        except EOFError:
            print("Nothing changed (run it with --yes to restore without asking).")
            return 1
    p, s, sec, ws = _settings_secrets_workspace()
    if wait_for_web(1) is not None:
        print("Stopping Kurooto (it sends up your notes first, if Notes sync is on)…")
    if not stop_gracefully(90):
        print("It didn't stop by itself in time, so it was stopped.")
    stop(quiet=True)  # anything left over (the supervisor, a stuck copy)
    for _ in range(20):  # let it let go of its files
        if not wait_for_web(0.2):
            break
        time.sleep(0.5)
    safety = p.data / backups.SAFETY
    safety.mkdir(parents=True, exist_ok=True)
    try:
        dest, _ = backups.make_zip(p, safety, None, notes=False, secrets=None, index=True)
        backups.prune(safety, 2)
        print(f"Kept a copy of how it was: {dest}")
    except Exception as e:
        print(f"Couldn't keep a copy of the current settings ({e}); nothing was changed.")
        return 1
    try:
        out = backups.restore(zip_path, p, secrets=sec if m["has_secrets"] else None, notes=notes)
    except backups.InUse as e:
        print(f"Nothing was restored: {e}.")
        return 1
    except Exception as e:
        print(f"The restore stopped: {type(e).__name__}: {e}. To go back: kurooto restore {dest}")
        return 1
    print(f"Notes folder: {out['workspace']}")
    if not start:
        print("Restored. Start Kurooto with: kurooto start")
        return 0
    start_background()
    url = wait_for_web(60)
    print(
        f"Restored, and Kurooto is running: {url}" if url else f"Restored. Kurooto didn't come up; logs: {paths().logs}"
    )
    return 0


# ------------------------------------------------------- `kurooto profile save|restore|status` (owner: profile)
PASSPHRASE = "KUROOTO_PROFILE_PASSPHRASE"  # noqa: S105 (the variable's name): for scripts; typed otherwise


def profile_parsers(sub) -> None:
    pr = sub.add_parser("profile", help="your setup, encrypted in your private repository: save, restore, status")
    psub = pr.add_subparsers(dest="action", required=True)
    psub.add_parser("status", help="what's saved, and when")
    sv = psub.add_parser("save", help="save it now (the first time: pick the repository and a passphrase)")
    sv.add_argument("--replace", action="store_true", help="save over a profile another computer saved since")
    rs = psub.add_parser("restore", help="bring your profile to this computer (stops Kurooto, restores, starts it)")
    rs.add_argument("--repo", default="", help="owner/name of your private repository")
    rs.add_argument("--remote", default="", help=argparse.SUPPRESS)  # tests: any Git address
    rs.add_argument("--yes", action="store_true", help="don't ask first")
    rs.add_argument("--no-start", action="store_true", help="don't start Kurooto afterwards")


def _secret(prompt: str, env: str | None) -> str:
    """A token or passphrase: from the environment (scripts), else typed without showing it."""
    if env and os.environ.get(env) is not None:
        return os.environ[env]
    if not sys.stdin.isatty():
        return ""
    import getpass

    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


def profile_run(a) -> int | None:
    """Runs `kurooto profile …`; None for any other command."""
    if a.cmd != "profile":
        return None
    from kurooto.app import App
    from kurooto.core import profile as core
    from kurooto.modules.profile import describe

    if a.action == "restore":
        return profile_restore(a)
    app = App()
    try:
        if a.action == "status":
            print(describe(core.status(app)))
            return 0
        if not app.is_on("profile") or not core.cached_key(app):  # the first time: connect, then it saves
            print("Profile sync isn't set up on this computer yet.")
            ask = sys.stdin.isatty()
            repo = input("Repository (owner/name; empty: the one Notes sync uses): ").strip() if ask else ""
            token = _secret("Token for it (empty: Notes sync's): ", "KUROOTO_PROFILE_TOKEN") if repo else ""
            phrase = _secret("Pick a passphrase (10+ characters; you need it on a new computer): ", PASSPHRASE)
            again = phrase if os.environ.get(PASSPHRASE) is not None else _secret("The passphrase again: ", None)
            if not phrase:
                print("No passphrase given: nothing saved (or set it up in the dashboard: Features → Profile sync).")
                return 1
            out = app.modules["profile"].configure({"repo": repo, "token": token, "passphrase": phrase, "again": again})
            print(out["message"])
            if out["ok"] and not app.is_on("profile"):
                if ask_running("modules/enable", {"ids": ["profile"]}) is None:
                    app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), "profile"])
            return 0 if out["ok"] else 1
        try:
            ok, msg = core.save(app, force=a.replace)
        except core.ProfileError as e:
            ok, msg = False, str(e)
        print(msg if ok else f"Couldn't save: {msg}")
        return 0 if ok else 1
    finally:
        app.close()


def ntfy_token(clear: bool) -> int:
    """`kurooto ntfy-token`: keep an ntfy account token (typed without showing it, or KUROOTO_NTFY_TOKEN), checked
    with ntfy first; then the call line is deployed again so it publishes with it too. --clear: without one again."""
    from kurooto.app import App
    from kurooto.modules.calls import check_ntfy_token, deploy

    app = App()
    try:
        if clear:
            app.secrets.delete("calls.ntfy_token")
            print("No ntfy token now: rings are published without one.")
        else:
            print("Make a free account at https://ntfy.sh/signup, then Account → Access tokens → Create a token.")
            token = _secret("ntfy token (tk_...): ", "KUROOTO_NTFY_TOKEN").strip()
            if not token:
                print("No token given: nothing changed.")
                return 1
            user, err = check_ntfy_token(app.settings.get("calls.ntfy_server") or "https://ntfy.sh", token)
            if err:
                print(err)
                return 1
            app.secrets.set("calls.ntfy_token", token)
            print(f"Kept: rings from this computer are published as {user}.")
        if not deploy.needs_redeploy(app):
            return 0
        print("Your call line is deployed again with it (a minute or two)...")
        ok, msg = deploy.deploy(app, progress=print)
        print("Done." if ok else f"The call line couldn't be updated: {msg} (it tries again at 05:10).")
        return 0 if ok else 1
    finally:
        app.close()


def profile_restore(a) -> int:
    from kurooto.app import App
    from kurooto.core import profile as core

    app = App()
    try:
        s = app.settings
        repo = a.repo or s.get("profile.repo") or s.get("notes_sync.repo") or ""
        if not a.remote and not repo:
            if not sys.stdin.isatty():
                print("Which repository? kurooto profile restore --repo owner/name")
                return 1
            repo = input("Your private repository (owner/name): ").strip()
        token = (
            ""
            if a.remote
            else _secret(f"Token for {repo} (empty: the one this computer has): ", "KUROOTO_PROFILE_TOKEN")
        )
        phrase = _secret("Your profile's passphrase: ", PASSPHRASE)
    finally:
        app.close()
    if not phrase:
        print("No passphrase given: nothing changed.")
        return 1
    print("Kurooto's settings, keys and saved state here are replaced by your profile's (a copy of the settings is")
    print("kept first). Your notes folder isn't touched; Notes sync brings your notes back if it was on.")
    if not a.yes:
        try:
            if input("Restore it? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing changed.")
                return 1
        except EOFError:
            print("Nothing changed (run it with --yes to restore without asking).")
            return 1
    was = wait_for_web(1) is not None
    if was:
        print("Stopping Kurooto…")
        stop(quiet=True)
    app = App()
    try:
        try:
            report = core.restore(app, phrase, repo=repo, token=token, remote=a.remote, progress=print)
        except Exception as e:  # a ProfileError reads well as it is; anything else says what it was
            print(f"Couldn't restore: {e if isinstance(e, core.ProfileError) else f'{type(e).__name__}: {e}'}")
            if was and not a.no_start:
                start_background()
            return 1
        for line in report["notes"]:
            print(f"Note: {line}")
        b = report.get("brain") or {}
        if b.get("main") and not b.get("ready"):
            print(f"Your AI ({b.get('label')}) isn't ready here: {b.get('why')}. The dashboard's setup page installs")
            print("it and signs it in again (agent programs keep their sign-ins on the computer they ran on).")
        left = [x for x in report["left"] if x["setup"]]
        if left and sys.stdin.isatty() and not a.yes:
            names = ", ".join(x["title"] for x in left)
            if input(f"Set up {names} now? It installs what they need. [y/N] ").strip().lower() in ("y", "yes"):
                for x in left:
                    m = app.modules[x["id"]]
                    try:
                        ok, msg = m.setup(print)
                    except Exception as e:
                        ok, msg = False, f"{type(e).__name__}: {e}"
                    print(msg)
                    if ok and m.ready()[0] and not app.is_on(m.id):
                        app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), m.id])
        elif left:
            print("Set these up in the dashboard (Features): " + ", ".join(x["title"] for x in left))
    finally:
        app.close()
    if a.no_start:
        print("Restored. Start Kurooto with: kurooto start")
        return 0
    start_background()
    url = wait_for_web(60)
    print(
        f"Restored, and Kurooto is running: {url}" if url else f"Restored. Kurooto didn't come up; logs: {paths().logs}"
    )
    return 0


# ------------------------------------------------------------------- `kurooto ask`, `kurooto call` (owner: tools)
def wait_job(jid: str, minutes: float) -> tuple[bool | None, str]:
    """Wait for a request's answer: (True, answer) / (False, why it failed) / (None, "") if it took too long."""
    import time

    deadline, misses = time.monotonic() + minutes * 60, 0
    while time.monotonic() < deadline:
        j = ask_running("job", {"id": jid})
        if j is None:
            misses += 1
            if misses > 30:
                return False, "Kurooto stopped before the answer came."
        elif j.get("status") in ("ok", "failed"):
            return j["status"] == "ok", str(j.get("answer") or "")
        elif j.get("ok") is False:
            return False, str(j.get("error") or "no such request")
        time.sleep(2)
    return None, ""


def say(text: str) -> dict | None:
    r = ask_running("say", {"text": text})
    if r is None:
        print("Kurooto isn't running (`kurooto on` starts it).", file=sys.stderr)
    elif not r.get("ok"):
        print(r.get("error") or "That didn't work.", file=sys.stderr)
        return None
    return r


# (wakefix) `kurooto ask` and shell commands: "!command" runs one in this terminal (after echoing it); a line typed
# as a shell command without the ! ("call-me --cancel …", "systemctl …", "kurooto status") is never sent to Kurooto
# or its AI, where it would be read as English.
SHELL_CMDS = frozenset(
    "kurooto call-me ask-me ask-approval systemctl journalctl launchctl sudo git agy gemini claude ls dir cd cat rm mv "
    "cp mkdir grep rg python python3 py pip uv bash sh zsh fish pwsh powershell nvim vim nano npm npx node bun brew "
    "apt pacman yay winget docker podman ssh curl wget chmod tail htop btop pkill killall taskkill".split()
)
SHELL_HINT = "that's a shell command: run it in a shell tab, or prefix it with !"


def shell_line(text: str) -> bool:
    """A line typed as a shell command: a known command name first ("systemctl …", "call-me --cancel …"), or any
    installed command followed by a flag or a pipe. A command that's also a word ("focus off") stays English."""
    import re
    import shutil

    m = re.match(r"([a-z][a-z0-9._+-]*)(?=\s|$)(.*)$", text.strip(), re.S)
    if not m:
        return False
    word, rest = m[1], m[2]
    if word in SHELL_CMDS or ("-" in word and shutil.which(word)):
        return True
    flagged = re.match(r"\s+--?[a-z]", rest) or re.search(r"\|\s*\w|&&|\$\(|`|\s>>?\s*\S", rest)
    return bool(flagged) and ("-" in word or bool(shutil.which(word)))


def run_shell(cmd: str, echo) -> None:
    """ "!command" in `kurooto ask`: echo it, then run it here, with your shell (cmd.exe on Windows)."""
    import subprocess

    print(echo(f"$ {cmd}"), flush=True)
    try:
        if sys.platform == "win32":
            subprocess.run(cmd, shell=True)  # noqa: S602 (you typed it, in your own terminal)
        else:
            subprocess.run(cmd, shell=True, executable=os.environ.get("SHELL") or "/bin/sh")  # noqa: S602
    except KeyboardInterrupt:
        print()
    except OSError as e:
        print(f"Couldn't run it: {e}")


def plain(text: str, wait: bool, minutes: int, job: str = "") -> int:
    """`kurooto ask`: like typing to Kurooto on Telegram. Quick things answer at once; a bigger request goes to
    the AI and its answer prints here (not on Telegram)."""
    if job:
        ok, answer = wait_job(job, minutes)
    elif not text:
        return plain_loop(minutes)
    elif text.startswith("!") or shell_line(text):
        print("That's a shell command: run it in your shell, not through kurooto ask.", file=sys.stderr)
        return 2
    else:
        r = say(text)
        if r is None:
            return 1
        if not r.get("job"):
            print("\n".join(r.get("replies") or []) or "Done.")
            return 0
        if not wait:
            print(r["job"])
            return 0
        print("Working on it…", file=sys.stderr)
        ok, answer = wait_job(r["job"], minutes)
        job = r["job"]
    if ok is None:
        print(f"No answer within {minutes} min; it's still going (wait again: kurooto ask --job {job}).")
        return 2
    print(answer)
    return 0 if ok else 1


def plain_loop(minutes: int) -> int:
    """Type requests one after another; answers to bigger ones print when they're ready. It looks like Kurooto
    Terminal's chat tab: the name, a few examples and the `kurooto ❯` prompt, in Kurooto's colours. "!command" runs
    a shell command here; a shell command typed without the ! is refused, never sent (shell_line)."""
    import threading

    from kurooto.modules.terminal.look import chat_look

    try:
        import readline  # line editing and history, where Python has it
    except ImportError:
        readline = None
    history = paths().state / "ask_history"
    if readline is not None:
        try:
            readline.read_history_file(history)
        except OSError:
            pass
        readline.set_history_length(500)
    look = chat_look(sys.stdout, readline is not None)
    lock = threading.Lock()

    def above(text: str) -> None:
        """Print an answer above the prompt without losing what's being typed."""
        typed = readline.get_line_buffer() if readline is not None else ""
        sys.stdout.write("\r\x1b[K" + text + "\n" + look.prompt(for_input=False) + typed)
        sys.stdout.flush()

    def later(jid: str, text: str) -> None:
        ok, answer = wait_job(jid, minutes)
        with lock:
            above(look.answer(text, ok, answer or f"still going: kurooto ask --job {jid}"))

    print(look.banner())
    while True:
        try:
            line = input(look.prompt()).strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        if readline is not None:
            try:
                readline.write_history_file(history)
            except OSError:
                pass
        if not line:
            continue
        if line.lower() == "clear":
            print("\x1b[2J\x1b[H" + look.banner())
            continue
        if line.startswith("!"):  # a shell command, on purpose
            if line[1:].strip():
                run_shell(line[1:].strip(), lambda t: look.paint("dim", t))
            continue
        if shell_line(line):  # never to Kurooto or its AI
            print(look.paint("peach", SHELL_HINT) + look.paint("dim", f"   !{line}"))
            continue
        r = say(line)
        if r is None:
            continue
        if r.get("job"):
            print(look.working())
            threading.Thread(target=later, args=(r["job"], line), daemon=True).start()
        else:
            with lock:
                print(look.done("\n".join(r.get("replies") or []) or "Done."))


def call(reason: str, at: str, alarm: bool, force: bool) -> int:
    """`kurooto call`: what the private call-me did, for scripts and agent programs."""
    r = ask_running("call", {"reason": reason, "at": at, "alarm": alarm, "force": force})
    if r is None:
        print("Kurooto isn't running, so it can't call you (`kurooto on` starts it).", file=sys.stderr)
        return 2
    print(r.get("message", ""))
    return 0 if r.get("ok") else 1


# ------------------------------------------------------------------- files and quick notes (`send`, `note`)
def skills_parsers(sub) -> None:
    se = sub.add_parser("send", help="send yourself a file on Telegram (up to 50 MB)")
    se.add_argument("file")
    se.add_argument("--caption", default="")
    se.add_argument("--to", choices=["telegram", "drive"], default="telegram", help="drive: your Google Drive, a link")
    nt = sub.add_parser("note", help="save a quick note to your notes' inbox (the text, or what's piped in)")
    nt.add_argument("text", nargs="*")
    nt.add_argument("--title", default="")


def skills_command(a) -> int | None:
    """`kurooto send` and `kurooto note`; None for any other command."""
    if a.cmd == "send":
        f = Path(a.file).expanduser()
        if not f.is_file():
            print(f"There's no file {a.file}.", file=sys.stderr)
            return 1
        r = ask_running("send-file", {"path": str(f.resolve()), "caption": a.caption, "to": a.to})
        if r is None:
            print("Kurooto isn't running (`kurooto on` starts it), so nothing was sent.", file=sys.stderr)
            return 2
        print(r.get("message", ""))
        return 0 if r.get("ok") else 1
    if a.cmd == "note":
        from kurooto.core import layout
        from kurooto.modules.library import capture

        text = " ".join(a.text)
        if not text and not sys.stdin.isatty():
            text = sys.stdin.read()
        if not text.strip():
            print('Nothing to save: kurooto note "your text" (or pipe text in).', file=sys.stderr)
            return 1
        f = capture(layout.for_install(), text, title=a.title, source="terminal")  # your notes layout's inbox
        print(f)
        return 0
    return None


# ------------------------------------------------------------------------- Kurooto Terminal (`kurooto term`)
def term_parsers(sub) -> None:
    from kurooto.modules.terminal.run import parsers

    parsers(sub)


def term_run(a) -> int | None:
    """`kurooto term` (modules/terminal/run.py); None for any other command."""
    if a.cmd != "term":
        return None
    from kurooto.modules.terminal.run import main as term_main

    return term_main(a)


# ------------------------------------------------------------------- (ws5) flags for scripts, usage, skills in agents
def notify_flags(no) -> None:
    no.add_argument(
        "--button",
        action="append",
        default=[],
        metavar='"Label=WHAT"',
        help="a button (one row each): WHAT is a feature's prefix:ref:action, or a web address",
    )
    no.add_argument("--click", default="", metavar="URL", help="a link to open, as an Open button")
    no.add_argument("--reply-to", type=int, default=None, metavar="ID", help="answer an earlier Telegram message")
    no.add_argument("--print-id", action="store_true", help="print the Telegram message's id (for --reply-to)")


def notify_extra(a) -> dict:
    buttons = [b.split("=", 1) for b in a.button if "=" in b]
    return {"buttons": buttons, "click": a.click, "reply_to": a.reply_to}


def call_flags(ca) -> None:
    ca.add_argument("--list", action="store_true", help="the calls booked for later")
    ca.add_argument("--cancel", default="", metavar="KEY", help="take a booked call off (its key from --list)")


def booked_calls(cancel: str = "") -> int:
    """`kurooto call --list` / `--cancel KEY`."""
    r = ask_running("call/cancel", {"key": cancel}) if cancel else ask_running("call/list")
    if r is None:
        print("Kurooto isn't running (`kurooto on` starts it), so its booked calls can't be read.", file=sys.stderr)
        return 2
    if cancel:
        print(r.get("message", ""))
        return 0 if r.get("ok") else 1
    calls = r.get("calls") or []
    if not calls:
        print("No calls booked. (Check-ins and the alarm: /checkins and /alarm on Telegram.)")
        return 0
    for c in calls:
        print(f"{c['when']}  {c['key']:<18} {'(alarm) ' if c.get('alarm') else ''}{c['reason'][:80]}")
    print("Take one off: kurooto call --cancel KEY")
    return 0


def ask_me_flags(am) -> None:
    am.add_argument("--pending", action="store_true", help="the questions still open (--json for programs)")
    am.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    am.add_argument("--id", default="", help="with --wait: wait for the answer to a question asked before")
    am.add_argument(
        "--then",
        default="",
        help='a command to run with the answer, e.g. --then "notify-send Answer {answer}" ({answer}, {id}); it runs '
        "as a program, never through a shell, from here (in the background unless --wait)",
    )
    am.add_argument("--poll", type=float, default=3, help=argparse.SUPPRESS)  # seconds between looks
    am.add_argument("--bg", action="store_true", help=argparse.SUPPRESS)  # the background copy: failures message you


# (ws cutgaps) `kurooto ask-me --then CMD`: a follow-up command for scripts, like a hook. Kurooto itself never runs
# it: this terminal command (or the background copy of it that it starts) waits for the answer and runs it, so
# nothing typed on Telegram or decided by an AI can start a program.
def then_argv(text: str) -> list[str]:
    """--then's command as a program and its arguments: a JSON list, or words split like a shell would (quotes
    keep spaces) without running one. [] when it can't be read."""
    import shlex

    t = (text or "").strip()
    if t.startswith("["):
        try:
            v = json.loads(t)
        except ValueError:
            return []
        return [str(x) for x in v] if isinstance(v, list) and v and all(isinstance(x, str) for x in v) else []
    try:
        parts = shlex.split(t, posix=os.name != "nt")
    except ValueError:
        return []
    if os.name == "nt":
        parts = [x[1:-1] if len(x) >= 2 and x[0] == x[-1] and x[0] in "\"'" else x for x in parts]
    return parts


def then_fill(argv: list[str], answer: str, qid: str) -> list[str]:
    """{answer} and {id} filled in; each stays one argument whatever the answer holds."""
    return [x.replace("{answer}", answer).replace("{id}", qid) for x in argv]


def expires_minutes(text: str, default: float = 2 * 24 * 60) -> float:
    """--expires (2d, 6h, 30m) in minutes: how long a background follow-up keeps waiting."""
    import re

    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([mhd])\w*\s*", text or "")
    return float(m[1]) * {"m": 1, "h": 60, "d": 1440}[m[2]] if m else default


def wait_open(qid: str, timeout_min: float, poll: float = 3.0) -> str | None:
    """The answer to a question once it comes, or None (it expired, or the time ran out; the question stays open).
    Kurooto restarting meanwhile is fine: this keeps asking."""
    import time

    end = time.monotonic() + timeout_min * 60
    while time.monotonic() < end:
        q = (ask_running("ask/get", {"id": qid}) or {}).get("question") or {}
        if q.get("status") == "answered":
            return q.get("answer") or ""
        if q.get("status") == "expired":
            return None
        time.sleep(max(0.0, min(poll, end - time.monotonic())))
    return None


def run_then(qid: str, argv: list[str], answer: str, background: bool) -> int:
    """Run the follow-up with the answer; its exit code. In the background a failure comes as a message."""
    import shutil
    import subprocess

    from kurooto.core.proc import resolve_cmd_shim

    cmd = then_fill(argv, answer, qid)
    exe = shutil.which(os.path.expanduser(cmd[0]))
    run = resolve_cmd_shim(exe) if exe else []  # an npm .cmd wrapper on Windows: its script with node
    if not exe:
        code, why = 127, f"{cmd[0]} isn't on this computer"
    elif os.name == "nt" and run[0].lower().endswith((".cmd", ".bat")):
        code, why = 126, f"{cmd[0]} is a batch file, and cmd.exe would read the answer as commands; use a program"
    else:
        try:
            code = subprocess.run([*run, *cmd[1:]], check=False).returncode  # noqa: S603 (argv, no shell)
            why = f"exit code {code}"
        except OSError as e:
            code, why = 126, str(e)[:120]
    if code:
        print(f"The follow-up ({cmd[0]}) failed: {why}.", file=sys.stderr)
        if background:
            ask_running("notify", {"text": f"The follow-up to your answer ({cmd[0]}) failed: {why}.", "kind": "info"})
    return code


def then_in_background(qid: str, argv: list[str], minutes: float) -> None:
    """A copy of this command that waits for the answer on its own (it outlives this terminal) and then runs the
    follow-up; what it prints goes to the logs folder (ask-then.log)."""
    import subprocess

    cmd = [sys.executable, "-m", "kurooto", "ask-me", "--id", qid, "--wait", "--timeout", f"{minutes:g}"]
    cmd += ["--then", json.dumps(argv), "--poll", "10", "--bg"]
    paths().logs.mkdir(parents=True, exist_ok=True)
    log = open(paths().logs / "ask-then.log", "a", encoding="utf-8")  # noqa: SIM115 (the child keeps it)
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": log}
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        kw.update(creationflags=flags, close_fds=True)
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kw)  # noqa: S603 (this same program)
    finally:
        log.close()


def ask_me_more(a) -> int:
    """`kurooto ask-me --pending [--json]` and `kurooto ask-me --id ID --wait [--then CMD]`."""
    if a.id and a.then:
        argv = then_argv(a.then)
        if not argv:
            print('--then needs a command, e.g. --then "notify-send Answer {answer}"', file=sys.stderr)
            return 2
        if not a.wait:
            then_in_background(a.id, argv, a.timeout)
            return 0
        answer = wait_open(a.id, a.timeout, max(1.0, float(a.poll or 3)))
        if answer is None:
            print("timeout")
            return 2
        print(answer, flush=True)
        return run_then(a.id, argv, answer, background=a.bg)
    if a.id:
        if not a.wait:
            q = (ask_running("ask/get", {"id": a.id}) or {}).get("question")
            if not q:
                print(f"There's no question {a.id} (or Kurooto isn't running).", file=sys.stderr)
                return 2
            print(json.dumps(q, ensure_ascii=False) if a.json else f"{q['status']}: {q.get('answer') or ''}".rstrip())
            return 0
        import time

        end = time.monotonic() + a.timeout * 60
        while time.monotonic() < end:  # unlike `ask-me --wait`, a timeout here leaves the question open
            q = (ask_running("ask/get", {"id": a.id}) or {}).get("question") or {}
            if q.get("status") == "answered":
                print(q.get("answer") or "")
                return 0
            if q.get("status") == "expired":
                break
            time.sleep(max(0.0, min(3.0, end - time.monotonic())))
        print("timeout")
        return 2
    r = ask_running("ask/pending")
    if r is None:
        print("Kurooto isn't running (`kurooto on` starts it).", file=sys.stderr)
        return 2
    qs = r.get("questions") or []
    if a.json:
        print(json.dumps(qs, ensure_ascii=False))
    else:
        for q in qs:
            print(
                f"{q['id']}  {q['text'][:100]}"
                + (f"  [{' | '.join(q.get('choices') or [])}]" if q.get("choices") else "")
            )
        if not qs:
            print("No open questions.")
    return 0


def sync_flags(sy) -> None:
    sy.add_argument("--status", action="store_true", help="is a sync running, and how did the last one go")
    sy.add_argument("--no-wait", action="store_true", help="start it and return; the summary comes as a message")


def sync_status() -> int:
    """`kurooto sync --status`: works with Kurooto stopped too (it reads what the last sync left)."""
    import datetime as dt

    from kurooto.core.state import jload

    st = jload(paths().state / "sync-all.json", {}) or {}
    if not st:
        print("No sync has run yet (kurooto sync starts one).")
        return 0
    if st.get("running"):
        since = dt.datetime.fromtimestamp(st.get("started") or 0)
        print(f"Running since {since:%H:%M:%S}." + ("" if wait_for_web(1) else " (Kurooto isn't running now, though.)"))
        return 0
    done = dt.datetime.fromtimestamp(st.get("finished") or 0)
    print(f"Last sync finished {done:%a %d %b %H:%M}:\n{st.get('text') or ''}".rstrip())
    return 0


def usage_cmd(days: int) -> int:
    """`kurooto usage [DAYS]`: /usage in a terminal (Kurooto's own requests, agy's count from its logs, and today's
    free limits)."""
    from kurooto.app import App
    from kurooto.core.readbudget import usage_text as reading
    from kurooto.modules.chat import usage_text
    from kurooto.providers.agy import log_usage, log_usage_text

    days = days if 1 <= days <= 60 else 7
    app = App()
    try:
        print(
            usage_text(app.jobs.usage(days), days) + log_usage_text(log_usage(days)) + app.quota.text() + reading(app)
        )
    finally:
        app.close()
    return 0


def export_skills(state: str, to: str) -> int:
    """`kurooto export-skills on|off|status`: your skills as slash commands in agy, Claude Code, Copilot CLI."""
    from kurooto.app import App
    from kurooto.core import agent_export

    app = App()
    try:
        if state == "status":
            st = agent_export.status(app)
            if not st["targets"]:
                print("Off. kurooto export-skills on puts your skills in agy as /commands (--to agy,agents,claude adds")
                print("Claude Code and Copilot CLI).")
                return 0
            for t, names in st["skills"].items():
                folder = agent_export.target_dir(t)
                print(f"{agent_export.LABELS[t]} ({folder}): {len(names)}: {', '.join('/' + n for n in names)}")
            for p in st["problems"]:
                print(f"  ! {p}")
            return 0
        if state == "on":
            want = [t.strip() for t in (to or "agy").split(",") if t.strip()]
            bad = [t for t in want if t not in agent_export.TARGETS]
            if bad:
                print(f"Not a place Kurooto knows: {', '.join(bad)} (agy, agents, claude).", file=sys.stderr)
                return 2
            app.settings.set("agents.export", want)
        else:
            app.settings.set("agents.export", [])
        rep = agent_export.sync(app)
        print(agent_export.report(rep))
        return 1 if rep["problems"] else 0
    finally:
        app.close()


def reserve_cmd(a) -> int:
    """`kurooto reserve`: write the Markdown copies of alarms, deadlines, calendar, settings and what an AI may do."""
    from kurooto.app import App
    from kurooto.core import reserve

    app = App()
    try:
        changed = reserve.refresh(app)
        print(f"{reserve.folder(app)}: " + (", ".join(changed) if changed else "already up to date"))
        return 0
    finally:
        app.close()


def space_cmd(a) -> int:
    """`kurooto space [--clean]`: what Kurooto takes, and what can go (only its own leftovers; --clean does it)."""
    from kurooto.app import App
    from kurooto.core import space

    app = App()
    try:
        for k, v in space.footprint(app).items():
            print(f"{k}: {space.human(v)}")
        items = space.plan(app)
        print(space.report(items))
        if a.clean and items:
            out = space.clean(app, items)
            print(
                f"Cleaned off {space.human(out['freed'])}"
                + (f"; {out['failed']} couldn't be removed" if out["failed"] else "")
                + "."
            )
        elif items:
            print("kurooto space --clean does it.")
        return 0
    finally:
        app.close()


def hardware_cmd(a) -> int:
    """`kurooto hardware`: see what this computer suits, and go past it if you want: `--profile big-gpu`,
    `--add gemma4:12b`, `--add-prereq tesseract`, `--install` (Kurooto installs Ollama, the models and the programs,
    here and now)."""
    from kurooto.app import App
    from kurooto.core import hardware

    app = App()
    try:
        s = app.settings
        if a.profile:
            if a.profile == "auto":
                s.set("hardware.force_profile", "")
            elif a.profile in hardware.PROFILES:
                s.set("hardware.force_profile", a.profile)
            else:
                print(f"Not a setup: {a.profile} (auto, {', '.join(hardware.PROFILES)}).", file=sys.stderr)
                return 2
        for key, items, add in (
            ("hardware.extra_models", a.add, True),
            ("hardware.extra_models", a.remove, False),
            ("hardware.extra_prereqs", a.add_prereq, True),
            ("hardware.extra_prereqs", a.remove_prereq, False),
        ):
            if items:
                have = list(s.get(key) or [])
                for it in items:
                    if add and it not in have:
                        have.append(it)
                    if not add and it in have:
                        have.remove(it)
                s.set(key, have)
        cur = hardware.current(app)
        rec = cur["recommendation"]
        m = cur["machine"]
        gpus = ", ".join(g["name"] + (f" ({g['vram_gb']} GB)" if g.get("vram_gb") else "") for g in m["gpus"]) or "none"
        print(f"{m['cpu']}, {m['ram_gb']} GB memory, graphics: {gpus}")
        forced = s.get("hardware.force_profile")
        print(f"Setup: {rec['profile']}" + (" (chosen by you)" if forced else " (detected)"))
        for mod in rec["local_models"]:
            size = f"{mod['size_gb']:g} GB" if mod.get("size_gb") else "size unknown"
            print(f"  {mod['tag']} ({size}): {mod['use']}")
        for n in rec["notes"]:
            print(f"  ! {n}")
        if s.get("hardware.extra_prereqs"):
            print("  programs: " + ", ".join(s.get("hardware.extra_prereqs")))
        if a.install:
            lm = app.modules["local_models"]
            ok, msg = lm.setup(progress=lambda line: print("  " + line))
            print(("Done: " if ok else "Not done: ") + msg)
            return 0 if ok else 1
        return 0
    finally:
        app.close()


def ws5_parsers(sub) -> None:
    us = sub.add_parser("usage", help="AI requests per day, and agy's own count from its logs")
    us.add_argument("days", nargs="?", type=int, default=7)
    ex = sub.add_parser("export-skills", help="your skills as /commands in agy (and Claude Code, Copilot CLI)")
    ex.add_argument("state", nargs="?", choices=["on", "off", "status"], default="status")
    ex.add_argument(
        "--to",
        default="",
        help="where: agy (default), agents (Copilot CLI, others), claude (Claude Code); several: agy,claude",
    )
    sub.add_parser("reserve", help="write Markdown copies of alarms, deadlines, calendar and settings for AI programs")
    sp = sub.add_parser("space", help="what Kurooto takes and what can go (only its own leftovers)")
    sp.add_argument("--clean", action="store_true", help="remove them now")
    hw = sub.add_parser("hardware", help="what this computer suits; go past it with --profile, --add, --install")
    hw.add_argument(
        "--profile", default="", help="use another setup: auto, light, apple-8, apple, small-gpu, big-gpu, big-gpu-12"
    )
    hw.add_argument(
        "--add", action="append", default=[], metavar="MODEL", help="an Ollama model of your own (repeatable)"
    )
    hw.add_argument("--remove", action="append", default=[], metavar="MODEL", help="take one of yours off the list")
    hw.add_argument(
        "--add-prereq", action="append", default=[], metavar="ID", help="another program to install (repeatable)"
    )
    hw.add_argument("--remove-prereq", action="append", default=[], metavar="ID")
    hw.add_argument("--install", action="store_true", help="install Ollama, the models and the programs now")


def ws5_run(a) -> int | None:
    """Runs the commands ws5_parsers() added; None for any other command."""
    if a.cmd == "usage":
        return usage_cmd(a.days)
    if a.cmd == "export-skills":
        return export_skills(a.state, a.to)
    if a.cmd == "hardware":
        return hardware_cmd(a)
    if a.cmd == "space":
        return space_cmd(a)
    if a.cmd == "reserve":
        return reserve_cmd(a)
    return None


def utf8_output() -> None:
    """(home) Windows: write UTF-8 even when the output goes to a pipe or a file (the code page would turn notes'
    text and symbols such as "—" into "?" or mojibake). Consoles are UTF-8 already."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):  # replaced by a test harness, or already closed
            pass


# ------------------------------------- `kurooto idle away|back`, `kurooto autostart boot|login|status` (owner: ws3)
def machine_parsers(sub) -> None:
    idl = sub.add_parser("idle", help="for your idle tool (hypridle, swayidle): you've stepped away, or you're back")
    idl.add_argument("state", choices=["away", "back"])


def machine_run(a) -> int | None:
    """Runs `kurooto idle …` and `kurooto autostart boot|login|status`; None for anything else."""
    if a.cmd == "idle":
        from kurooto.core.idle import set_away

        print(set_away(paths().ensure().state, a.state == "away"))
        return 0
    if a.cmd != "autostart" or a.state not in ("boot", "login", "status"):
        return None
    from kurooto.core import autostart
    from kurooto.core.config import Settings
    from kurooto.core.secrets import Secrets

    p = paths().ensure()
    settings = Settings(p.config / "settings.json")
    if a.state == "status":
        print("on" if autostart.status() else "off")
        if autostart.when(settings) == "boot":
            print(
                "from boot, before anyone logs in"
                if autostart.lingering()
                else "at login (boot is chosen, but lingering is off: `kurooto autostart boot` again)"
            )
        return 0
    if os.environ.get("KUROOTO_NO_AUTOSTART") == "1":  # tests and rehearsals leave this computer alone
        print("Start at boot or login is left alone here (KUROOTO_NO_AUTOSTART).")
        return 0
    ok, msg = autostart.set_when(a.state, settings, Secrets(p.config), p.state)
    print(msg)
    return 0 if ok else 1


# ------------------------------------------ `kurooto cases [list|check|export|forget]` (owner: wrong, modules/cases.py)
def cases_parsers(sub) -> None:
    cs = sub.add_parser("cases", help="test cases from the Wrong button and requests I didn't understand")
    cs.add_argument("action", nargs="?", choices=["list", "check", "export", "forget"], default="list")
    cs.add_argument("ref", nargs="?", default="", help="forget: a case's id, or all")
    cs.add_argument("--out", default="", help="export: the file to write (default test_kurooto_cases.py here)")
    cs.add_argument("--all", action="store_true", help="export: the cases waiting for review too")


def cases_run(a) -> int | None:
    if a.cmd != "cases":
        return None
    from kurooto.modules.cases import cli

    return cli(a.action, a.ref, a.out, a.all)


# ------------------------------------------------- `kurooto classpack check|export|import` (modules/classpacks.py)
def classpack_parsers(sub) -> None:
    cp = sub.add_parser("classpack", help="your section's setup as a file to share, or a classmate's to import")
    cps = cp.add_subparsers(dest="pack_cmd", required=True)
    ch = cps.add_parser("check", help="is this a class pack Kurooto can use? what's in it")
    ch.add_argument("file")
    ex = cps.add_parser("export", help="make a class pack of your setup (or of one term note: --from)")
    ex.add_argument("--checked", required=True, help="the day you checked it against the official timetable, or today")
    ex.add_argument("--from", dest="note", default="", help="a term note (terms/2026-autumn, or a file)")
    ex.add_argument("--title", default="", help='what the section calls itself, e.g. "Year 2 section B"')
    ex.add_argument("--elective", default="", help="courses not everyone takes, by id: machine-learning,topology")
    ex.add_argument("--out", default="", help="where to write it (a file or a folder); Kurooto's data folder if not")
    im = cps.add_parser("import", help="review a class pack on Telegram (tick electives and batch there)")
    im.add_argument("file")


def classpack_run(a) -> int | None:
    """Runs `kurooto classpack ...`; None for any other command."""
    if a.cmd != "classpack":
        return None
    from kurooto.modules import coursepack

    if a.pack_cmd == "check":
        try:
            pack = coursepack.read(Path(a.file).expanduser())
        except coursepack.PackError as e:
            print(f"Not a class pack Kurooto can use: {e}.", file=sys.stderr)
            return 1
        print(f"{pack['title'] or 'Class pack'}: checked against the official timetable on {pack['checked']}.")
        print(f"{coursepack.overview(pack)}.")
        return 0
    if a.pack_cmd == "import":
        f = Path(a.file).expanduser()
        if not f.is_file():
            print(f"There's no file {a.file}.", file=sys.stderr)
            return 1
        r = ask_running("classpack/import", {"path": str(f.resolve())})
        if r is None:
            print("Kurooto isn't running (`kurooto on` starts it); the review happens on Telegram.", file=sys.stderr)
            return 2
        print(r.get("message", ""))
        return 0 if r.get("ok") else 1
    from kurooto.app import App
    from kurooto.core.clock import now

    app = App()
    try:
        mod = app.modules["classpacks"]
        if not app.is_on("classpacks"):
            print("Class packs is off: dashboard → Features → Class packs.", file=sys.stderr)
            return 1
        checked = now().date().isoformat() if a.checked.lower() == "today" else a.checked
        pack, left, why = mod.draft_pack(a.note, anywhere=True)
        if pack is None:
            print(why, file=sys.stderr)
            return 1
        wanted = [x.strip() for x in a.elective.split(",") if x.strip()]
        unknown = [x for x in wanted if x not in {c["id"] for c in pack["courses"]}]
        if unknown:
            print(
                f"Not a course in it: {', '.join(unknown)} ({', '.join(c['id'] for c in pack['courses'])}).",
                file=sys.stderr,
            )
            return 1
        for c in pack["courses"]:
            c["elective"] = c["elective"] or c["id"] in wanted
        if a.title:
            try:
                pack["title"] = coursepack.title(a.title)
            except coursepack.PackError as e:
                print(f"Not that title: {e}.", file=sys.stderr)
                return 1
        if checked > now().date().isoformat():
            print("That day hasn't come yet: check it against the official timetable first.", file=sys.stderr)
            return 1
        ok, said, f = mod.write(pack, checked, Path(a.out).expanduser() if a.out else None)
        print(said)
        for x in left:
            print(f"  left out: {x}")
        if f is not None:
            print(f)
        return 0 if ok else 1
    finally:
        app.close()


# ------------------------------------------------- `kurooto jobs [--cancel ID|all]` (owner: jobsfix, core/jobs.py)
def jobs_parsers(sub) -> None:
    jb = sub.add_parser("jobs", help="what the AI is working on and what waits; --cancel ID (or all) cancels")
    jb.add_argument("--cancel", default="", metavar="ID", help="cancel this request (an id from the list, or all)")


def jobs_run(a) -> int | None:
    """Runs `kurooto jobs`; None for any other command. A cancel goes through the running Kurooto (it stops the
    request's program and its thread); with Kurooto stopped, the queue itself is changed."""
    if a.cmd != "jobs":
        return None
    if a.cancel:
        r = ask_running("jobs/cancel", {"id": a.cancel})
        if r is not None:
            print(r.get("message", ""))
            return 0 if r.get("ok") else 1
    from kurooto.app import App

    app = App()
    try:
        if a.cancel:
            gone = a.cancel.lower() == "all" or app.jobs.find(a.cancel) is not None
            print(app.jobs.cancel_text(a.cancel))
            return 0 if gone else 1
        act = app.jobs.active()
        for j in act:
            print(f"{j.status:8}{app.jobs.line(j)[2:]}")
        if not act:
            print("Nothing running or waiting.")
        else:
            print("kurooto jobs --cancel ID (or all) cancels.")
        return 0
    finally:
        app.close()


def main(argv: list[str] | None = None) -> int:
    utf8_output()
    ap = argparse.ArgumentParser(prog="kurooto", description="Your assistant, on your own computer.")
    ap.add_argument("--version", action="version", version=f"kurooto {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("paths", help="where settings, data and logs live")
    d = sub.add_parser("doctor", help="check that everything is in place")
    d.add_argument("--json", action="store_true")
    d.add_argument(
        "--bundle", action="store_true", help="save a diagnostics zip (secrets blanked out) to send for help"
    )
    d.add_argument(
        "--fix", metavar="ID", help="run the fix a problem offers (the id doctor shows), in the running Kurooto"
    )
    fx = sub.add_parser("fixme", help="what's wrong and what to do, matched by rules (no AI needed)")
    fx.add_argument("words", nargs="*", help="what you see, e.g. the phone doesn't ring")
    sub.add_parser("run", help="run the assistant in this window")
    sub.add_parser("supervise", help="run it and restart it if it crashes")
    sub.add_parser("start", help="start it in the background now")
    sub.add_parser("open", help="open the setup page or dashboard")
    se = sub.add_parser("setup", help="open the setup page where you left off (or at one step)")
    se.add_argument("step", nargs="?", default="", help="you, computer, brain, about, features, telegram or finish")
    au = sub.add_parser("autostart", help="start at sign-in, or not (boot: before anyone logs in, on Linux)")
    au.add_argument("state", choices=["on", "off", "status", "boot", "login"])
    sub.add_parser("stop", help="stop it (it starts again at sign-in; `off` keeps it off)")
    off = sub.add_parser("off", help="turn it off completely: it doesn't start at sign-in until `kurooto on`")
    off.add_argument("--keep-calls", action="store_true", help="let your call line keep placing scheduled calls")
    sub.add_parser("on", help="turn it back on (and open the dashboard)")
    pa = sub.add_parser("pause", help="pause it: /pause on Telegram does the same")
    pa.add_argument("when", nargs="*", help="how long or until when: 2h, 18:00 (empty: until you resume)")
    sub.add_parser("resume", help="wake it after a pause")
    no = sub.add_parser("notify", help="send yourself a message through Kurooto (for scripts and other programs)")
    no.add_argument("text", nargs="+")
    no.add_argument("--title", default="")
    no.add_argument(
        "--kind", default="info", choices=["info", "result", "reminder", "deadline", "question", "approval"]
    )
    no.add_argument("--urgent", action="store_true")
    notify_flags(no)
    am = sub.add_parser("ask-me", help="ask yourself something, answered anywhere (prints its id, or the answer)")
    am.add_argument("text", nargs="*")
    am.add_argument("--choices", default="", help='answers to offer as buttons, e.g. "yes|no|later today"')
    am.add_argument("--expires", default="", help="how long it stays open: 2d, 6h, 30m (default 2 days)")
    am.add_argument("--title", default="", help='a label instead of "Question"')
    am.add_argument("--wait", action="store_true", help="wait for the answer and print it")
    am.add_argument("--timeout", type=float, default=30, help="minutes to wait (default 30)")
    ask_me_flags(am)
    aa = sub.add_parser("ask-approval", help="ask for a yes/no and wait: exit 0 approved, 1 denied, 2 timeout")
    aa.add_argument("text", nargs="+")
    aa.add_argument("--timeout", type=float, default=30, help="minutes to wait (default 30)")
    upd = sub.add_parser("update", help="check for an update")
    upd.add_argument("--now", action="store_true", help="install it now instead of at night")
    sub.add_parser("selftest", help="check that this version starts")
    ak = sub.add_parser("ask", help="talk to Kurooto in plain English; the answer prints here")
    ak.add_argument("text", nargs="*", help="what to ask (nothing: type one request after another)")
    ak.add_argument("--no-wait", action="store_true", help="for a bigger request: print its id instead of waiting")
    ak.add_argument("--job", default="", help="wait for the answer to a request started with --no-wait")
    ak.add_argument("--timeout", type=int, default=60, help="minutes to wait for an answer (default 60)")
    ca = sub.add_parser("call", help="ring your phone now or later (for scripts and agent programs)")
    ca.add_argument("reason", nargs="*")
    ca.add_argument("--at", default="", help='when: 17:30, "in 20 min", "tomorrow 7:00" (default: now)')
    ca.add_argument("--alarm", action="store_true", help="ring as a wake-up alarm (no-call rules don't apply)")
    ca.add_argument("--force", action="store_true", help="ring now despite no-call rules (never during a call)")
    call_flags(ca)
    sub.add_parser("mcp", help="Kurooto's tools for agent programs: an MCP server on stdin/stdout")
    skills_parsers(sub)
    fin = sub.add_parser("install-finish", help=argparse.SUPPRESS)
    fin.add_argument("--uv", required=True)
    fin.add_argument("--python", required=True)
    un = sub.add_parser("uninstall", help="remove Kurooto from this computer")
    un.add_argument("--keep-data", action="store_true", help="keep your settings, journal and notes index")
    un.add_argument(
        "--revoke", action="store_true", help="first delete your call line and take back Google's and the bot's access"
    )
    ro = sub.add_parser("rotate", help="new keys for your call line (a lost phone, a backup that got out)")
    ro.add_argument("--yes", action="store_true", help="don't ask first (every paired phone has to pair again)")
    nt = sub.add_parser("ntfy-token", help="an ntfy account token, so phone rings aren't refused for a shared address")
    nt.add_argument("--clear", action="store_true", help="publish without a token again")
    home_parsers(sub)
    profile_parsers(sub)
    term_parsers(sub)
    ws5_parsers(sub)
    machine_parsers(sub)
    cases_parsers(sub)
    classpack_parsers(sub)
    jobs_parsers(sub)
    a = ap.parse_args(argv)
    done = home_run(a)
    done = ws5_run(a) if done is None else done
    done = profile_run(a) if done is None else done
    done = term_run(a) if done is None else done
    done = machine_run(a) if done is None else done
    done = cases_run(a) if done is None else done
    done = classpack_run(a) if done is None else done
    done = jobs_run(a) if done is None else done
    if done is not None:
        return done

    if a.cmd == "paths":
        p = paths()
        for name in ("config", "data", "state", "logs", "cache", "app"):
            print(f"{name:<7} {getattr(p, name)}")
        return 0
    if a.cmd == "doctor":
        if a.fix:  # (core/health.py) the fix runs inside Kurooto: its links and timers live there
            r = ask_running("health/fix", {"id": a.fix})
            if r is None:
                print("Kurooto isn't running (`kurooto start` starts it); the fixes run inside it.", file=sys.stderr)
                return 2
            print(r.get("message", ""))
            return 0 if r.get("ok") else 1
        return doctor(a.json, a.bundle)
    if a.cmd == "fixme":  # (core/fixme.py) works with Kurooto stopped, and when the AI is what broke
        from kurooto.core import fixme

        return fixme.cli(" ".join(a.words))
    if a.cmd == "run":
        from kurooto.daemon import run

        return run()
    if a.cmd == "supervise":
        from kurooto.daemon import supervise

        return supervise()
    if a.cmd == "start":
        return start_and_say()
    if a.cmd in ("open", "setup"):
        import webbrowser

        from kurooto.core.setupsteps import STEPS

        if a.cmd == "setup" and a.step and a.step not in STEPS:
            print(f"Not a setup step: {a.step} ({', '.join(STEPS)}).", file=sys.stderr)
            return 2
        url = wait_for_web()
        if not url:
            print("Kurooto isn't running yet; start it with: kurooto start")
            return 1
        if a.cmd == "setup":  # the page itself lands on the first step not finished (core/setupsteps.py)
            url += "setup" + (f"#{a.step}" if a.step else "")
        if os.environ.get("KUROOTO_NO_BROWSER") != "1":
            webbrowser.open(url)
        print(url)
        return 0
    if a.cmd == "stop":
        return stop(graceful=True)
    if a.cmd == "off":
        return turn_off(a.keep_calls)
    if a.cmd == "on":
        return turn_on()
    if a.cmd == "notify":
        text = " ".join(a.text)
        r = ask_running(
            "notify", {"text": text, "title": a.title, "kind": a.kind, "urgent": a.urgent, **notify_extra(a)}
        )
        if r and r.get("ok"):
            if a.print_id:
                print(r.get("id") or "")
            return 0
        if r and r.get("error"):
            print(r["error"], file=sys.stderr)
            return 1
        from kurooto.core import desktop  # not running: at least show it on this computer

        desktop.notify(a.title or "Kurooto", text, urgent=a.urgent)
        print("Kurooto isn't running, so this was only shown on this computer.", file=sys.stderr)
        return 2
    if a.cmd == "ask-me":
        if a.pending or a.id:
            return ask_me_more(a)
        return ask_me(" ".join(a.text), a.choices, a.expires, a.title, a.wait, a.timeout, False, a.then)
    if a.cmd == "ask-approval":
        return ask_me(" ".join(a.text), "", "", "", True, a.timeout, approval=True)
    if a.cmd in ("pause", "resume"):
        r = ask_running(f"power/{a.cmd}", {"when": " ".join(getattr(a, "when", []) or [])})
        print(r.get("message", "") if r else "Kurooto isn't running (`kurooto on` starts it).")
        return 0 if r else 1
    if a.cmd == "ask":
        return plain(" ".join(a.text).strip(), not a.no_wait, a.timeout, a.job)
    if a.cmd == "call":
        if a.list or a.cancel:
            return booked_calls(a.cancel)
        return call(" ".join(a.reason), a.at, a.alarm, a.force)
    if a.cmd == "mcp":
        from kurooto.core.mcp import serve

        return serve()
    if a.cmd in ("send", "note"):
        return skills_command(a)
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "install-finish":
        return install_finish(a.uv, a.python)
    if a.cmd == "update":
        return update(a.now)
    if a.cmd == "uninstall":
        return uninstall(a.keep_data, a.revoke)
    if a.cmd == "ntfy-token":
        return ntfy_token(a.clear)
    if a.cmd == "rotate":  # (revoke) core/leave.py; the running Kurooto makes the new pairing link
        from kurooto.core import leave

        return leave.rotate_command(a.yes, ask_running, print, interactive=sys.stdin.isatty())
    if a.cmd == "autostart":
        from kurooto.core import autostart

        if a.state == "status":
            print("on" if autostart.status() else "off")
            return 0
        print(autostart.enable() if a.state == "on" else autostart.disable())
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
