"""Kurooto's installer core, run by install.ps1 / install.sh through uv (with the `cryptography` package):

    uv run --python 3.12 --with cryptography bootstrap.py [--source DIR] [--channel stable]

Without --source it fetches the signed release pointer, checks both signatures and every file's sha256 before
using anything. --source DIR installs an unsigned copy from a source folder (development and CI only).
Then it builds that version's own Python environment and hands over to `kurooto install-finish`, which places
the launcher and the `kurooto` command, turns on start-at-sign-in, starts Kurooto and opens the setup page.
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PAGES = "https://avtarfr.github.io/kurooto"
PUBLIC_KEYS = ["ScONcap27e/YGb+KR8e2Oq4rkOIGTvjUbyk9Y5HcIhs="]  # the same keys as kurooto/update/signing.py


def say(text):
    print(f"  {text}", flush=True)


def app_dir():
    if os.environ.get("KUROOTO_HOME"):
        return Path(os.environ["KUROOTO_HOME"]) / "app"
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Programs" / "Kurooto"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Kurooto" / "app"
    data = os.environ.get("XDG_DATA_HOME")
    return (Path(data) if data and data.startswith("/") else home / ".local" / "share") / "kurooto" / "app"


def canonical(doc):
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def trusted(wrapper):
    keys = PUBLIC_KEYS + (
        [os.environ["KUROOTO_EXTRA_UPDATE_KEY"]] if os.environ.get("KUROOTO_EXTRA_UPDATE_KEY") else []
    )
    doc, sig = wrapper.get("doc"), base64.b64decode(wrapper.get("sig", ""))
    for k in keys:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(k)).verify(sig, canonical(doc))
            return doc
        except Exception:  # noqa: S112 (try the next trusted key)
            continue
    raise SystemExit("  The release isn't signed by a trusted key. Nothing was installed.")


def get(url):
    if not (url.startswith("https://") or url.startswith("http://127.0.0.1")):
        raise SystemExit("  Refusing a download that isn't https.")
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (https checked above)
        return r.read()


def venv_python(vdir):
    v = vdir / ".venv"
    return v / "Scripts" / "python.exe" if os.name == "nt" else v / "bin" / "python"


def run(args, what):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"  Couldn't {what}:\n{(r.stderr or r.stdout)[-800:]}")


def main():
    args = sys.argv[1:]
    source = Path(args[args.index("--source") + 1]) if "--source" in args else None
    channel = args[args.index("--channel") + 1] if "--channel" in args else "stable"
    base = (os.environ.get("KUROOTO_UPDATE_BASE") or PAGES).rstrip("/")
    uv = shutil.which("uv") or os.environ.get("UV")
    # the Python that stays: uv's managed 3.12, not this script's short-lived environment
    clean = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "CONDA_PREFIX")}
    py = subprocess.run(
        [uv, "python", "find", "--managed-python", "--no-project", "3.12"],
        capture_output=True,
        text=True,
        env=clean,
        cwd=tempfile.gettempdir(),
    ).stdout.strip()
    if not uv or not py:
        raise SystemExit("  uv or Python 3.12 is missing; run the installer again.")
    app = app_dir()
    (app / "versions").mkdir(parents=True, exist_ok=True)

    if source:
        version = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        say(f"Installing Kurooto {version} from {source} (unsigned: development only)")
        vdir = app / "versions" / version
        shutil.rmtree(vdir, ignore_errors=True)
        shutil.copytree(
            source, vdir / "src", ignore=shutil.ignore_patterns(".git", ".venv", "dist", "__pycache__", "node_modules")
        )
    else:
        ptr = trusted(json.loads(get(f"{base}/{channel}.json")))
        man = trusted(json.loads(get(ptr["manifest_url"])))
        version = str(man["version"])
        if version != str(ptr["version"]):
            raise SystemExit("  The release files don't match each other. Nothing was installed.")
        say(f"Installing Kurooto {version} (signature checked)")
        vdir = app / "versions" / version
        if (vdir / ".venv").exists() and (app / "current.json").exists():
            say("That version is already here; repairing it.")
        shutil.rmtree(vdir, ignore_errors=True)
        name = next(n for n in man["files"] if n.endswith(".tar.gz"))
        data = get(man["files"][name]["url"])
        if hashlib.sha256(data).hexdigest() != man["files"][name]["sha256"]:
            raise SystemExit("  The download didn't match its signed checksum. Nothing was installed.")
        with tempfile.TemporaryDirectory() as tmp:
            tgz = Path(tmp) / name
            tgz.write_bytes(data)
            with tarfile.open(tgz) as t:
                for m in t.getmembers():
                    parts = Path(m.name).parts[1:]
                    if not parts or ".." in parts or Path(m.name).is_absolute():
                        continue
                    m.name = str(Path(*parts))
                    t.extract(m, vdir / "src", filter="data")

    say("Preparing its Python environment (a minute or two)...")
    run([uv, "venv", "--python", py, str(vdir / ".venv")], "make its Python environment")
    vpy = str(venv_python(vdir))
    lock = vdir / "src" / "requirements.lock"
    if lock.exists():
        run([uv, "pip", "install", "--python", vpy, "--require-hashes", "-r", str(lock)], "install its parts")
        run([uv, "pip", "install", "--python", vpy, "--no-deps", str(vdir / "src")], "install it")
    else:
        run([uv, "pip", "install", "--python", vpy, str(vdir / "src")], "install it")
    run([vpy, "-m", "kurooto", "selftest"], "start it (self-test)")
    # Kurooto starts from here and keeps this environment until it restarts: leave out what `uv run` added for this
    # short-lived script (its throwaway environment and the uv cache on the PATH), so programs it runs don't see them
    cache = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True, env=clean).stdout.strip()
    drop = [p for p in (sys.prefix, cache) if p]
    keep = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p and not any(p.startswith(d) for d in drop)]
    env = {k: v for k, v in clean.items() if k != "UV_RUN_RECURSION_DEPTH"}
    env["PATH"] = os.pathsep.join(keep)
    r = subprocess.run([vpy, "-m", "kurooto", "install-finish", "--uv", uv, "--python", py], env=env)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
