"""Kurooto's launcher: what starts at sign-in. Standard library only, and it lives outside the versions so an
update can never break it. It runs the current version and keeps it running:

    exit 0   stopped on purpose: stop too
    exit 3   another copy is already running: stop
    exit 75  "restart me": an update was installed; start whatever current.json now names
    other    a crash: restart after a pause; during a new version's probation, three crashes roll it back

    python launcher.py            run (what autostart does)
    python launcher.py cli ARGS   run a `kurooto` command with the current version (the `kurooto` shim uses this)

A stop signal (SIGTERM, SIGINT, SIGHUP: systemd, launchd, a logout) is passed on to the running version, which stops
the normal way (its programs end too); the launcher waits for it and then stops itself. So a service manager that
signals only the launcher (systemd's KillMode=mixed) still gets a clean stop.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

API = 1  # bump only if the files this reads or writes change shape
APP = Path(__file__).resolve().parent
RESTART = 75


def read(name, default=None):
    try:
        return json.loads((APP / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write(name, obj):
    tmp = APP / f"{name}.tmp{os.getpid()}"
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    for i in range(10):
        try:
            os.replace(tmp, APP / name)
            return
        except PermissionError:
            time.sleep(0.05 * (i + 1))
    os.replace(tmp, APP / name)


def python_of(version, windowless=False):
    venv = APP / "versions" / version / ".venv"
    if os.name == "nt":
        exe = venv / "Scripts" / ("pythonw.exe" if windowless else "python.exe")
        return exe if exe.exists() else venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def rollback(reason):
    """Go back to the previous version and remember this one as bad."""
    cur, prev = read("current.json", {}), read("previous.json", {})
    if not prev.get("version") or prev["version"] == cur.get("version"):
        return False
    bad = read("bad.json", [])
    if cur.get("version") and cur["version"] not in bad:
        bad.append(cur["version"])
    write("bad.json", bad)
    write("current.json", prev)
    write(
        "update.json",
        {
            "phase": "rolled_back",
            "from": cur.get("version"),
            "to": prev["version"],
            "reason": reason,
            "since": time.time(),
        },
    )
    return True


STOPPING = []  # a stop signal came: don't start the version again


def forward(child):
    """Pass stop signals on to the running version instead of dying at once (which leaves it to be killed)."""

    def on_signal(signum, frame):
        STOPPING.append(signum)
        if child[0] is not None and child[0].poll() is None:
            try:
                child[0].send_signal(signal.SIGTERM)  # the version treats it as a stop request
            except OSError:
                pass

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is not None and os.name != "nt":
            try:
                signal.signal(sig, on_signal)
            except (OSError, ValueError):
                pass


def run():
    write("launcher.json", {"pid": os.getpid(), "started": time.time(), "forwards": True})
    crashes, backoff = 0, 5
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    child = [None]
    forward(child)
    while not STOPPING:
        version = (read("current.json", {}) or {}).get("version")
        if not version or not python_of(version).exists():
            sys.stderr.write(f"Kurooto: version {version!r} isn't installed properly; run the installer again.\n")
            return 1
        started = time.monotonic()
        child[0] = subprocess.Popen([str(python_of(version)), "-m", "kurooto", "run"], creationflags=flags)
        if STOPPING and os.name != "nt":  # the signal came while it was starting
            child[0].send_signal(signal.SIGTERM)
        while True:
            try:
                code = child[0].wait()
                break
            except InterruptedError:
                continue
        if STOPPING:
            return 0
        if code in (0, 3):
            return code
        if code == RESTART:
            crashes, backoff = 0, 5
            continue
        lived = time.monotonic() - started
        crashes = crashes + 1 if lived < 300 else 1
        upd = read("update.json", {}) or {}
        if upd.get("phase") == "trial" and upd.get("to") == version and crashes >= 3:
            if rollback(f"version {version} crashed {crashes} times right after updating"):
                crashes, backoff = 0, 5
                continue
        backoff = min(backoff * 2, 300) if lived < 300 else 5
        time.sleep(backoff)
    return 0


def cli(args):
    version = (read("current.json", {}) or {}).get("version")
    if not version:
        sys.stderr.write("Kurooto isn't installed properly; run the installer again.\n")
        return 1
    return subprocess.run([str(python_of(version)), "-m", "kurooto", *args]).returncode


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        sys.exit(cli(sys.argv[2:]))
    sys.exit(run())
