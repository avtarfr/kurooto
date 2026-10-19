"""The `kurooto` command.

kurooto --version
kurooto paths            where settings, data and logs live on this machine
kurooto doctor [--json]  check that everything Kurooto needs is in place (exit code = number of problems)
kurooto off / on         turn Kurooto off completely (no start at sign-in) / back on
kurooto pause [2h|18:00] / resume   pause it (Telegram says "paused" and keeps what you send) / wake it
kurooto notify [--title T] TEXT     send yourself a message through Kurooto (for scripts and other tools)
kurooto ask ["plain English"]       talk to Kurooto from a terminal; quick things at once, bigger ones print later
kurooto call "reason" [--at TIME] [--alarm] [--force]   ring your phone now or later
kurooto mcp              Kurooto's tools for agent programs (an MCP server on stdin/stdout)
kurooto ask-me "question" [--choices "a|b|c"] [--expires 2d] [--wait [--timeout MIN]]   ask yourself something
kurooto ask-approval "question" [--timeout MIN]   ask for a yes/no and wait (exit 0 yes, 1 no, 2 timeout)
kurooto send FILE [--caption T]     send yourself a file on Telegram (up to 50 MB)
kurooto note [--title T] TEXT       save a quick note to your notes' inbox (or pipe text in)
kurooto top [--once]     a status board: this computer and Kurooto (q quits)
kurooto logs [-f]        the end of Kurooto's log (-f: keep showing new lines)
kurooto sync             sync everything that's on, now (notes, Classroom, calendar, research, notes brain)
kurooto backup [--to F]  make a backup now · kurooto restore <zip>  put one back (stops, restores, starts)
kurooto profile save|restore|status   your setup, encrypted in your private repository; restore on a new computer
kurooto runlog start|metric|note|end|ls   log experiment runs into your notes (research/<project>/runs/)
kurooto watch -- CMD...  run a long job; you get a message when it ends (exit code, time, last lines)
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


def ask_me(text: str, choices: str, expires: str, title: str, wait: bool, timeout: float, approval: bool) -> int:
    """Ask the person something through the running assistant (Telegram, desktop, phone app, the next call).
    Without --wait it prints the question's id; with --wait, the answer (exit 2 if none came in time)."""
    if not text.strip():
        print("What's the question?", file=sys.stderr)
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
    if os.environ.get("KUROOTO_NO_AUTOSTART") != "1":
        print(autostart.enable())
    url = wait_for_web(8)  # under systemd or launchd, turning autostart on also started it
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


def uninstall(keep_data: bool) -> int:
    import shutil

    from kurooto.core import autostart

    stop()
    if os.environ.get("KUROOTO_NO_AUTOSTART") != "1":
        print(autostart.disable())
        from kurooto.core import shortcuts

        shortcuts.remove()
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
    sub.add_parser("sync", help="sync everything that's on, now")
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
        return sync_all()
    if a.cmd == "backup":
        return backup_now(a.to)
    if a.cmd == "restore":
        return restore(Path(a.zip), a.yes, not a.no_notes, not a.no_start)
    return None


def sync_all() -> int:
    import time

    r = ask_running("sync/all", {"notify": False})
    if r is None:
        print("Kurooto isn't running (kurooto start), and the syncs run inside it.")
        return 1
    print(r.get("message", ""))
    if not r.get("ok"):
        return 0 if "already running" in r.get("message", "") else 1
    url = wait_for_web(1)
    for _ in range(3600):  # Classroom can take a while
        time.sleep(1)
        st = ask_running("sync/status") if url else None
        if st is None:
            print("Kurooto stopped before the sync finished.")
            return 1
        if not st.get("running"):
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


def plain(text: str, wait: bool, minutes: int, job: str = "") -> int:
    """`kurooto ask`: like typing to Kurooto on Telegram. Quick things answer at once; a bigger request goes to
    the AI and its answer prints here (not on Telegram)."""
    if job:
        ok, answer = wait_job(job, minutes)
    elif not text:
        return plain_loop(minutes)
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
    """Type requests one after another; answers to bigger ones print when they're ready."""
    import threading

    try:
        import readline  # noqa: F401 (line editing and history, where Python has it)
    except ImportError:
        pass
    lock = threading.Lock()

    def later(jid: str, text: str) -> None:
        ok, answer = wait_job(jid, minutes)
        with lock:
            head = f"── {text[:60]}" + ("" if ok else " (failed)" if ok is False else " (no answer yet)")
            print(f"\n{head}\n{answer or f'still going: kurooto ask --job {jid}'}\n──", flush=True)

    print("Plain English, as on Telegram: quick things happen at once; answers to bigger requests print here when")
    print("they're ready. Ctrl-D (Ctrl-Z, Enter on Windows) leaves.")
    while True:
        try:
            line = input("kurooto> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        if not line:
            continue
        r = say(line)
        if r is None:
            continue
        if r.get("job"):
            print("Working on it; the answer prints here.")
            threading.Thread(target=later, args=(r["job"], line), daemon=True).start()
        else:
            with lock:
                print("\n".join(r.get("replies") or []) or "Done.")


def call(reason: str, at: str, alarm: bool, force: bool) -> int:
    """`kurooto call`: what the private call-me did, for scripts and agent programs."""
    r = ask_running("call", {"reason": reason, "at": at, "alarm": alarm, "force": force})
    if r is None:
        print("Kurooto isn't running, so it can't call you (`kurooto on` starts it).", file=sys.stderr)
        return 1
    print(r.get("message", ""))
    return 0 if r.get("ok") else 1


# ------------------------------------------------------------------- files and quick notes (`send`, `note`)
def skills_parsers(sub) -> None:
    se = sub.add_parser("send", help="send yourself a file on Telegram (up to 50 MB)")
    se.add_argument("file")
    se.add_argument("--caption", default="")
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
        r = ask_running("send-file", {"path": str(f.resolve()), "caption": a.caption})
        if r is None:
            print("Kurooto isn't running (`kurooto on` starts it), so nothing was sent.", file=sys.stderr)
            return 2
        print(r.get("message", ""))
        return 0 if r.get("ok") else 1
    if a.cmd == "note":
        from kurooto.app import default_workspace
        from kurooto.core.config import Settings
        from kurooto.modules.library import capture

        text = " ".join(a.text)
        if not text and not sys.stdin.isatty():
            text = sys.stdin.read()
        if not text.strip():
            print('Nothing to save: kurooto note "your text" (or pipe text in).', file=sys.stderr)
            return 1
        ws = Settings(paths().config / "settings.json").get("you.workspace")
        f = capture(Path(ws) if ws else default_workspace(), text, title=a.title, source="terminal")
        print(f)
        return 0
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
    sub.add_parser("run", help="run the assistant in this window")
    sub.add_parser("supervise", help="run it and restart it if it crashes")
    sub.add_parser("start", help="start it in the background now")
    sub.add_parser("open", help="open the setup page or dashboard")
    au = sub.add_parser("autostart", help="start at sign-in, or not")
    au.add_argument("state", choices=["on", "off", "status"])
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
    no.add_argument("--kind", default="info", choices=["info", "result", "reminder", "deadline"])
    no.add_argument("--urgent", action="store_true")
    am = sub.add_parser("ask-me", help="ask yourself something, answered anywhere (prints its id, or the answer)")
    am.add_argument("text", nargs="+")
    am.add_argument("--choices", default="", help='answers to offer as buttons, e.g. "yes|no|later today"')
    am.add_argument("--expires", default="", help="how long it stays open: 2d, 6h, 30m (default 2 days)")
    am.add_argument("--title", default="", help='a label instead of "Question"')
    am.add_argument("--wait", action="store_true", help="wait for the answer and print it")
    am.add_argument("--timeout", type=float, default=30, help="minutes to wait (default 30)")
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
    ca.add_argument("reason", nargs="+")
    ca.add_argument("--at", default="", help='when: 17:30, "in 20 min", "tomorrow 7:00" (default: now)')
    ca.add_argument("--alarm", action="store_true", help="ring as a wake-up alarm (no-call rules don't apply)")
    ca.add_argument("--force", action="store_true", help="ring now despite no-call rules (never during a call)")
    sub.add_parser("mcp", help="Kurooto's tools for agent programs: an MCP server on stdin/stdout")
    skills_parsers(sub)
    fin = sub.add_parser("install-finish", help=argparse.SUPPRESS)
    fin.add_argument("--uv", required=True)
    fin.add_argument("--python", required=True)
    un = sub.add_parser("uninstall", help="remove Kurooto from this computer")
    un.add_argument("--keep-data", action="store_true", help="keep your settings, journal and notes index")
    home_parsers(sub)
    profile_parsers(sub)
    a = ap.parse_args(argv)
    done = home_run(a)
    done = profile_run(a) if done is None else done
    if done is not None:
        return done

    if a.cmd == "paths":
        p = paths()
        for name in ("config", "data", "state", "logs", "cache", "app"):
            print(f"{name:<7} {getattr(p, name)}")
        return 0
    if a.cmd == "doctor":
        return doctor(a.json, a.bundle)
    if a.cmd == "run":
        from kurooto.daemon import run

        return run()
    if a.cmd == "supervise":
        from kurooto.daemon import supervise

        return supervise()
    if a.cmd == "start":
        return start_background()
    if a.cmd == "open":
        import webbrowser

        url = wait_for_web()
        if not url:
            print("Kurooto isn't running yet; start it with: kurooto start")
            return 1
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
        r = ask_running("notify", {"text": text, "title": a.title, "kind": a.kind, "urgent": a.urgent})
        if r and r.get("ok"):
            return 0
        from kurooto.core import desktop  # not running: at least show it on this computer

        desktop.notify(a.title or "Kurooto", text, urgent=a.urgent)
        print("Kurooto isn't running, so this was only shown on this computer.", file=sys.stderr)
        return 2
    if a.cmd == "ask-me":
        return ask_me(" ".join(a.text), a.choices, a.expires, a.title, a.wait, a.timeout, approval=False)
    if a.cmd == "ask-approval":
        return ask_me(" ".join(a.text), "", "", "", True, a.timeout, approval=True)
    if a.cmd in ("pause", "resume"):
        r = ask_running(f"power/{a.cmd}", {"when": " ".join(getattr(a, "when", []) or [])})
        print(r.get("message", "") if r else "Kurooto isn't running (`kurooto on` starts it).")
        return 0 if r else 1
    if a.cmd == "ask":
        return plain(" ".join(a.text).strip(), not a.no_wait, a.timeout, a.job)
    if a.cmd == "call":
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
        return uninstall(a.keep_data)
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
