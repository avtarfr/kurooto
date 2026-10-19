#!/usr/bin/env python3
"""Make and sign Kurooto releases. The signing key never leaves the maintainer's laptop.

    uv run tools/release.py keygen [--out ~/.config/kurooto-dev/release-key.pem] [--no-passphrase]
    uv run tools/release.py build --site SITE --base URL [--version V] [--notes TEXT] [--break-run]
    uv run tools/release.py sign  --site SITE --base URL --version V --key PEM [--channel stable]
    uv run tools/release.py publish --site SITE [--message TEXT]     push SITE to the gh-pages branch (GitHub Pages)

build --apk PATH puts the release-signed Android app in the package (your call line serves it at /kurooto.apk) and
on the site, with android.json for the app's update check. See docs/RELEASING.md for the whole routine.

SITE is a folder laid out like the GitHub Pages site:
    SITE/install.ps1, install.sh, bootstrap.py, index.html (the landing page)
    SITE/stable.json, beta.json                 signed channel pointers
    SITE/releases/<v>/manifest.json             signed list of files with sha256
    SITE/releases/<v>/kurooto-<v>.tar.gz        the source release (with requirements.lock, hash-pinned)
    SITE/releases/<v>/kurooto.apk, android.json the Android app and its version (with --apk)
The passphrase for the key comes from KUROOTO_RELEASE_PASSPHRASE, or is asked for.
--break-run builds a version whose `kurooto run` crashes at once (only for testing rollback).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from kurooto.update import signing  # noqa: E402


def passphrase(confirm: bool = False) -> bytes:
    p = os.environ.get("KUROOTO_RELEASE_PASSPHRASE")
    if p is None:
        p = getpass.getpass("Signing key passphrase: ")
        if confirm and getpass.getpass("Again: ") != p:
            raise SystemExit("they didn't match")
    return p.encode()


def keygen(out: Path, no_pass: bool) -> None:
    out = out.expanduser()
    if out.exists():
        raise SystemExit(f"{out} already exists; refusing to overwrite a signing key")
    key = Ed25519PrivateKey.generate()
    enc = serialization.NoEncryption() if no_pass else serialization.BestAvailableEncryption(passphrase(True))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc))
    os.chmod(out, 0o600)
    print(
        f"key: {out}\npublic: {signing.public_b64(key)}\nAdd the public key to PUBLIC_KEYS in "
        "src/kurooto/update/signing.py and installer/bootstrap.py, and back the key file up offline."
    )


def load_key(path: Path) -> Ed25519PrivateKey:
    data = path.expanduser().read_bytes()
    try:
        return serialization.load_pem_private_key(data, password=None)
    except TypeError:
        return serialization.load_pem_private_key(data, password=passphrase())


def version_code(version: str) -> int:
    """The Android versionCode for a version, the same way android/build.sh makes it."""
    m = re.match(r"(\d+)\.(\d+)\.(\d+)(?:(?:rc|-rc\.?)(\d+))?", version)
    major, minor, patch, rc = int(m[1]), int(m[2]), int(m[3]), int(m[4] or 9)
    return ((major * 1000 + minor) * 1000 + patch) * 10 + rc


def build(site: Path, base: str, version: str | None, notes: str, break_run: bool, apk: Path | None = None) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        shutil.copytree(
            ROOT,
            src,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "dist",
                "build",
                "__pycache__",
                "node_modules",
                ".pytest_cache",
                ".ruff_cache",
                ".wrangler",
                "*.keystore",
                "*.jks",
                "*.pem",
                ".dev.vars",
            ),
        )
        pp = src / "pyproject.toml"
        text = pp.read_text(encoding="utf-8")
        if version:
            text = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', text, count=1)
            pp.write_text(text, encoding="utf-8")
        version = re.search(r'(?m)^version = "([^"]+)"', text)[1]
        if apk:
            shutil.copy(apk, src / "src/kurooto/data/kurooto.apk")  # the call line serves it to phones
        if break_run:
            d = src / "src/kurooto/daemon.py"
            d.write_text(
                d.read_text(encoding="utf-8").replace(
                    "def run(web: bool = True) -> int:\n",
                    "def run(web: bool = True) -> int:\n    raise SystemExit(1)  # broken on purpose (rollback test)\n",
                ),
                encoding="utf-8",
            )
        subprocess.run(
            ["uv", "build", "--sdist", "--out-dir", str(Path(tmp) / "dist")], cwd=src, check=True, capture_output=True
        )
        sdist = next((Path(tmp) / "dist").glob("*.tar.gz"))
        rel = site / "releases" / version
        rel.mkdir(parents=True, exist_ok=True)
        name = f"kurooto-{version}.tar.gz"
        shutil.copy(sdist, rel / name)
    data = (rel / name).read_bytes()
    doc = {
        "version": version,
        "notes": notes,
        "created": time.time(),
        "files": {
            name: {
                "url": f"{base.rstrip('/')}/releases/{version}/{name}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        },
    }
    (rel / "manifest.unsigned.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    for f in ("install.ps1", "install.sh", "bootstrap.py", "index.html"):
        shutil.copy(ROOT / "installer" / f, site / f)
    if apk:
        shutil.copy(apk, rel / "kurooto.apk")
        (site / "android.json").write_text(
            json.dumps(
                {
                    "versionCode": version_code(version),
                    "versionName": version,
                    "url": f"{base.rstrip('/')}/releases/{version}/kurooto.apk",
                    "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
                },
                indent=1,
            ),
            encoding="utf-8",
        )
    (site / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {version}: {rel / name} ({len(data) // 1024} KB)")
    return version


def sign(site: Path, base: str, version: str, key_path: Path, channel: str) -> None:
    key = load_key(key_path)
    allowed = [*signing.PUBLIC_KEYS, os.environ.get("KUROOTO_EXTRA_UPDATE_KEY", "")]  # the extra: test keys only
    if signing.public_b64(key) not in allowed:
        raise SystemExit(
            "This key isn't one of the public keys built into Kurooto (signing.PUBLIC_KEYS): installs would "
            "refuse what it signs. Wrong key file?"
        )
    rel = site / "releases" / version
    doc = json.loads((rel / "manifest.unsigned.json").read_text(encoding="utf-8"))
    (rel / "manifest.json").write_text(
        json.dumps({"doc": doc, "sig": signing.sign(doc, key)}, indent=1), encoding="utf-8"
    )
    ptr = {
        "version": version,
        "manifest_url": f"{base.rstrip('/')}/releases/{version}/manifest.json",
        "issued": time.time(),
        "channel": channel,
    }
    (site / f"{channel}.json").write_text(
        json.dumps({"doc": ptr, "sig": signing.sign(ptr, key)}, indent=1), encoding="utf-8"
    )
    print(f"signed {version} on {channel}")


def publish(site: Path, message: str) -> None:
    """Put the site on the gh-pages branch and push it (GitHub Pages serves it). Older releases stay."""
    site = site.resolve()
    git = lambda *a, cwd=ROOT: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)  # noqa: E731
    subprocess.run(["git", "fetch", "-q", "origin", "gh-pages"], cwd=ROOT, capture_output=True)
    has = (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "origin/gh-pages"], cwd=ROOT, capture_output=True
        ).returncode
        == 0
    )
    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "pages"
        if has:
            git("worktree", "add", "-q", "-B", "gh-pages", str(wt), "origin/gh-pages")
        else:
            git("worktree", "add", "-q", "--detach", str(wt))
            git("checkout", "-q", "--orphan", "gh-pages", cwd=wt)
            git("rm", "-rq", "--cached", ".", cwd=wt)
            for item in wt.iterdir():
                if item.name != ".git":
                    shutil.rmtree(item) if item.is_dir() else item.unlink()
        try:
            shutil.copytree(site, wt, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.unsigned.json"))
            git("add", "-A", cwd=wt)
            if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=wt).returncode == 0:
                print("nothing new to publish")
                return
            git("commit", "-q", "-m", message, cwd=wt)
            git("push", "-q", "origin", "gh-pages", cwd=wt)
            print("published to gh-pages")
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--out", default="~/.config/kurooto-dev/release-key.pem")
    k.add_argument("--no-passphrase", action="store_true")
    b = sub.add_parser("build")
    b.add_argument("--site", required=True)
    b.add_argument("--base", required=True)
    b.add_argument("--version")
    b.add_argument("--notes", default="")
    b.add_argument("--break-run", action="store_true")
    b.add_argument("--apk", help="the release-signed Android app (android/build/kurooto.apk)")
    s = sub.add_parser("sign")
    s.add_argument("--site", required=True)
    s.add_argument("--base", required=True)
    s.add_argument("--version", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--channel", default="stable")
    pb = sub.add_parser("publish")
    pb.add_argument("--site", required=True)
    pb.add_argument("--message", default="release")
    a = ap.parse_args()
    if a.cmd == "keygen":
        keygen(Path(a.out), a.no_passphrase)
    elif a.cmd == "build":
        build(Path(a.site), a.base, a.version, a.notes, a.break_run, Path(a.apk) if a.apk else None)
    elif a.cmd == "publish":
        publish(Path(a.site), a.message)
    else:
        sign(Path(a.site), a.base, a.version, Path(a.key), a.channel)


if __name__ == "__main__":
    main()
