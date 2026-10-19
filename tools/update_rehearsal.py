#!/usr/bin/env python3
"""A full install and update rehearsal against a local, signed release site, in a sandbox folder:
install 0.1.0 with the real installer, update to 0.2.0, push a 0.3.0 that crashes and watch the launcher roll back
to 0.2.0 by itself, then uninstall. CI runs this on Windows, macOS and Linux.

    uv run tools/update_rehearsal.py [SANDBOX]
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN = sys.platform == "win32"


def step(msg):
    print(f"\n== {msg}", flush=True)


def main() -> int:
    box = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="kurooto-rehearsal-"))
    box.mkdir(parents=True, exist_ok=True)
    site, home, binp, key = box / "site", box / "home", box / "bin", box / "key.pem"
    site.mkdir(exist_ok=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    rel = [sys.executable, str(ROOT / "tools" / "release.py")]

    def release(version, *extra):
        subprocess.run(rel + ["build", "--site", str(site), "--base", base, "--version", version, *extra], check=True)
        time.sleep(1.1)  # each pointer must be issued after the last one
        subprocess.run(
            rel + ["sign", "--site", str(site), "--base", base, "--version", version, "--key", str(key)],
            check=True,
            env={**os.environ, "KUROOTO_EXTRA_UPDATE_KEY": pub},  # a throwaway key, trusted for this rehearsal only
        )

    out = subprocess.run(
        rel + ["keygen", "--out", str(key), "--no-passphrase"], check=True, capture_output=True, text=True
    )
    pub = next(line.split(": ", 1)[1] for line in out.stdout.splitlines() if line.startswith("public: "))
    env = {
        **os.environ,
        "KUROOTO_HOME": str(home),
        "KUROOTO_BIN": str(binp),
        "KUROOTO_UPDATE_BASE": base,
        "KUROOTO_EXTRA_UPDATE_KEY": pub,
        "KUROOTO_NO_AUTOSTART": "1",
        "KUROOTO_NO_BROWSER": "1",
    }
    env.pop("KUROOTO_SOURCE", None)
    kurooto = [str(binp / ("kurooto.cmd" if WIN else "kurooto"))]

    def k(*args, check=True):
        r = subprocess.run(kurooto + list(args), env=env, capture_output=True, text=True, timeout=900)
        print(r.stdout.strip(), r.stderr.strip()[-500:], sep="\n" if r.stderr.strip() else "")
        if check and r.returncode != 0:
            raise SystemExit(f"kurooto {' '.join(args)} failed ({r.returncode})")
        return r

    def running_version(timeout=240):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                url = json.loads((home / "state" / "web.json").read_text())["url"]
                with urllib.request.urlopen(url + "health", timeout=3) as r:  # noqa: S310 (our own local page)
                    return json.loads(r.read())["version"]
            except (OSError, ValueError, KeyError):
                time.sleep(1)
        return None

    def wait_for(version, timeout=240):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if running_version(5) == version:
                return True
            time.sleep(2)
        return False

    try:
        step("release 0.1.0 and install it with the real installer")
        release("0.1.0", "--notes", "first")
        installer = (
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "installer/install.ps1")]
            if WIN
            else ["sh", str(ROOT / "installer/install.sh")]
        )
        subprocess.run(installer, env=env, check=True, timeout=1800)
        assert wait_for("0.1.0"), "0.1.0 isn't running after install"
        assert "0.1.0" in k("--version").stdout

        step("release 0.2.0 and update to it")
        release("0.2.0", "--notes", "second")
        k("update", "--now")
        assert wait_for("0.2.0"), "0.2.0 isn't running after the update"

        step("release a 0.3.0 that crashes, update to it, and expect the launcher to roll back to 0.2.0")
        release("0.3.0", "--break-run")
        k("update", "--now")
        deadline = time.time() + 300
        app = home / "app"
        while time.time() < deadline:
            cur = json.loads((app / "current.json").read_text()).get("version")
            bad = json.loads((app / "bad.json").read_text()) if (app / "bad.json").exists() else []
            if cur == "0.2.0" and "0.3.0" in bad:
                break
            time.sleep(3)
        else:
            raise AssertionError("no rollback")
        assert wait_for("0.2.0"), "0.2.0 isn't running after the rollback"
        print("rolled back:", json.loads((app / "update.json").read_text()))
        assert k("update").stdout.strip().startswith("Up to date"), "a bad version must not be offered again"

        step("uninstall")
        k("uninstall")
        for _ in range(30):  # on Windows the command and the app folder go a few seconds after it exits
            if not Path(kurooto[0]).exists() and not (home / "app" / "launcher.py").exists():
                break
            time.sleep(1)
        assert not Path(kurooto[0]).exists(), "the kurooto command is still there"
        assert not (home / "app" / "launcher.py").exists(), "the app folder is still there"
        print("\nREHEARSAL PASSED")
        return 0
    finally:
        subprocess.run(kurooto + ["stop"], env=env, capture_output=True) if Path(kurooto[0]).exists() else None
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
