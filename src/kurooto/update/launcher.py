"""Kurooto's launcher: what starts at sign-in. Standard library only, and it lives outside the versions so an
update can never break it. It runs the current version and keeps it running:

    exit 0   stopped on purpose: stop too
    exit 3   another copy is already running: stop
    exit 75  "restart me": an update was installed; start whatever current.json now names
    other    a crash: restart after a pause; during a new version's probation, three crashes roll it back

    python launcher.py            run (what autostart does)
    python launcher.py cli ARGS   run a `kurooto` command with the current version (the `kurooto` shim uses this)
"""

import json
import os
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


def run():
    write("launcher.json", {"pid": os.getpid(), "started": time.time()})
    crashes, backoff = 0, 5
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    while True:
        version = (read("current.json", {}) or {}).get("version")
        if not version or not python_of(version).exists():
            sys.stderr.write(f"Kurooto: version {version!r} isn't installed properly; run the installer again.\n")
            return 1
        started = time.monotonic()
        code = subprocess.run([str(python_of(version)), "-m", "kurooto", "run"], creationflags=flags).returncode
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
