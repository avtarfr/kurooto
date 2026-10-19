"""The `kurooto` command.

kurooto --version
kurooto paths            where settings, data and logs live on this machine
kurooto doctor [--json]  check that everything Kurooto needs is in place (exit code = number of problems)
kurooto off / on         turn Kurooto off completely (no start at sign-in) / back on
kurooto pause [2h|18:00] / resume   pause it (Telegram says "paused" and keeps what you send) / wake it
kurooto notify [--title T] TEXT     send yourself a message through Kurooto (for scripts and other tools)
kurooto top [--once]     a status board: this computer and Kurooto (q quits)
kurooto logs [-f]        the end of Kurooto's log (-f: keep showing new lines)
kurooto sync             sync everything that's on, now (notes, Classroom, calendar, research, notes brain)
kurooto backup [--to F]  make a backup now · kurooto restore <zip>  put one back (stops, restores, starts)
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


def stop(quiet: bool = False) -> int:
    """Stop the supervisor (so it doesn't restart the assistant) and the assistant."""
    from kurooto.core import proc
    from kurooto.core.state import jload

    p = paths()
    stopped = False
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
    was = wait_for_web(1) is not None
    if was:
        print("Stopping Kurooto…")
    stop(quiet=True)
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


def main(argv: list[str] | None = None) -> int:
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
    upd = sub.add_parser("update", help="check for an update")
    upd.add_argument("--now", action="store_true", help="install it now instead of at night")
    sub.add_parser("selftest", help="check that this version starts")
    fin = sub.add_parser("install-finish", help=argparse.SUPPRESS)
    fin.add_argument("--uv", required=True)
    fin.add_argument("--python", required=True)
    un = sub.add_parser("uninstall", help="remove Kurooto from this computer")
    un.add_argument("--keep-data", action="store_true", help="keep your settings, journal and notes index")
    home_parsers(sub)
    a = ap.parse_args(argv)
    done = home_run(a)
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
        return stop()
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
    if a.cmd in ("pause", "resume"):
        r = ask_running(f"power/{a.cmd}", {"when": " ".join(getattr(a, "when", []) or [])})
        print(r.get("message", "") if r else "Kurooto isn't running (`kurooto on` starts it).")
        return 0 if r else 1
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
