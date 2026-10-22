#!/usr/bin/env python3
"""Make and sign Kurooto releases. The signing key never leaves the maintainer's laptop.

    uv run tools/release.py keygen [--out ~/.config/kurooto-dev/release-key.pem] [--no-passphrase]
    uv run tools/release.py build --site SITE --base URL [--version V] [--notes TEXT] [--critical] [--break-run]
    uv run tools/release.py sign  --site SITE --base URL --version V --key PEM [--channel stable] [--critical]
    uv run tools/release.py yank  --site SITE --key PEM V [V ...] [--reason TEXT] [--undo]
    uv run tools/release.py publish --site SITE [--message TEXT]     push SITE to the gh-pages branch (GitHub Pages)

sign --critical marks the release critical (a security fix): installs with staged updates on (updates.staged) don't
wait their 48 hours for it, nor for the end of exams. yank adds versions to the signed yank list (SITE/yank.json; with
--undo it takes them off): installs never update to a yanked version, even one already downloaded. Publish after
either. A yanked version that a channel pointer still names stays refused, so sign a fixed version on that channel.

build --apk PATH puts the release-signed Android app in the package (your call line serves it at /kurooto.apk) and
on the site, with android.json for the app's update check. See docs/RELEASING.md for the whole routine.

SITE is a folder laid out like the GitHub Pages site:
    SITE/install.ps1, install.sh, bootstrap.py, index.html (the landing page)
    SITE/privacy.html                           docs/PRIVACY.md as a page (Google's sign-in setup links to it)
    SITE/changelog.html                         CHANGELOG.md as a page (the landing page links to it)
    SITE/media/                                 its screenshots and animation (from docs/media)
    SITE/stable.json, beta.json                 signed channel pointers
    SITE/yank.json                              signed list of withdrawn versions, with reasons (yank)
    SITE/releases/<v>/manifest.json             signed list of files with sha256
    SITE/releases/<v>/kurooto-<v>.tar.gz        the source release (with requirements.lock, hash-pinned)
    SITE/releases/<v>/kurooto.apk, android.json the Android app and its version (with --apk)
The passphrase for the key comes from KUROOTO_RELEASE_PASSPHRASE, or is asked for.
--break-run builds a version whose `kurooto run` crashes at once (only for testing rollback).
--critical marks the release critical in its signed manifest: it installs even while a feature holds updates (Exam
season, during someone's exams). Only for fixes that can't wait.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import html
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


def build(
    site: Path, base: str, version: str | None, notes: str, break_run: bool, apk: Path | None = None, critical=False
) -> str:
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
        shutil.rmtree(src / "docs" / "media", ignore_errors=True)  # screenshots: the site has them, releases don't
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
        **({"critical": True} if critical else {}),
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
    site_pages(site)
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


def site_pages(site: Path) -> None:
    """The site's own pages: the installers, the landing page, its media, and the privacy page from PRIVACY.md."""
    site.mkdir(parents=True, exist_ok=True)
    for f in ("install.ps1", "install.sh", "bootstrap.py", "index.html"):
        shutil.copy(ROOT / "installer" / f, site / f)
    (site / "privacy.html").write_text(privacy_page(), encoding="utf-8")
    (site / "changelog.html").write_text(changelog_page(), encoding="utf-8")
    if (ROOT / "docs" / "media").is_dir():  # the landing page's screenshots and animation
        shutil.copytree(ROOT / "docs" / "media", site / "media", dirs_exist_ok=True)


def privacy_page() -> str:
    """installer/privacy.html with docs/PRIVACY.md in it, so the page never drifts from the document."""
    page = (ROOT / "installer" / "privacy.html").read_text(encoding="utf-8")
    body = md_html((ROOT / "docs" / "PRIVACY.md").read_text(encoding="utf-8"))
    a, b = page.index("<!-- PRIVACY:START"), page.index("<!-- PRIVACY:END -->") + len("<!-- PRIVACY:END -->")
    return page[:a] + body + page[b:]


def changelog_page() -> str:
    """CHANGELOG.md as a page of the site, in the privacy page's frame (so it looks like the rest of the site)."""
    page = (ROOT / "installer" / "privacy.html").read_text(encoding="utf-8")
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    text = re.sub(r"^# Changelog\s*\n", "", text)
    intro = (
        "<h1>What's new</h1>\n<p>Every version of Kurooto, newest first. A new version arrives by itself at night "
        "(on the beta channel first, then stable); <code>kurooto update --now</code> gets it at once.</p>\n"
    )
    a, b = page.index("<!-- PRIVACY:START"), page.index("<!-- PRIVACY:END -->") + len("<!-- PRIVACY:END -->")
    page = page[:a] + intro + md_html(text) + page[b:]
    page = page.replace("<title>Privacy · Kurooto</title>", "<title>Changelog · Kurooto</title>")
    return re.sub(
        r'<p class="updated">.*?</p>',
        '<p class="updated">Made from <a href="https://github.com/avtarfr/kurooto/blob/main/CHANGELOG.md">'
        "CHANGELOG.md</a> when the site is built.</p>",
        page,
        count=1,
        flags=re.S,
    )


def _inline(text: str) -> str:
    """Markdown inside a line: `code`, **bold**, [links](url); everything else escaped."""
    out, last = [], 0
    for m in re.finditer(r"`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)", text):
        out.append(html.escape(text[last : m.start()], quote=False))
        if m[1] is not None:
            out.append(f"<code>{html.escape(m[1], quote=False)}</code>")
        elif m[2] is not None:
            out.append(f"<strong>{_inline(m[2])}</strong>")
        else:
            href = (
                m[4]
                if re.match(r"(https?://|#|mailto:)", m[4])
                else "https://github.com/avtarfr/kurooto/blob/main/docs/" + m[4]
            )
            out.append(f'<a href="{html.escape(href)}">{_inline(m[3])}</a>')
        last = m.end()
    out.append(html.escape(text[last:], quote=False))
    return "".join(out)


def md_html(text: str) -> str:
    """Just enough Markdown for docs/PRIVACY.md: headings, paragraphs, lists (with wrapped lines), tables."""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    rows: list[list[str]] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
        if rows:
            head, *body = [r for r in rows if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]
            th = "".join(f"<th>{_inline(c)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
            rows.clear()

    for line in text.splitlines():
        s = line.rstrip()
        if not s.strip():
            flush()
        elif m := re.match(r"(#{1,4})\s+(.*)", s):
            flush()
            n, title = len(m[1]), m[2].strip()
            slug = re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")
            out.append(f'<h{n} id="{slug}">{_inline(title)}</h{n}>')
        elif s.startswith("|"):
            if para or items:
                flush()
            rows.append([c.strip() for c in s.strip().strip("|").split("|")])
        elif m := re.match(r"\s*[-*]\s+(.*)", s):
            if para or rows:
                flush()
            items.append(m[1])
        elif items and line.startswith("  "):
            items[-1] += " " + s.strip()
        else:
            if items or rows:
                flush()
            para.append(s.strip())
    flush()
    return "\n".join(out) + "\n"


def trusted_key(key_path: Path) -> Ed25519PrivateKey:
    key = load_key(key_path)
    allowed = [*signing.PUBLIC_KEYS, os.environ.get("KUROOTO_EXTRA_UPDATE_KEY", "")]  # the extra: test keys only
    if signing.public_b64(key) not in allowed:
        raise SystemExit(
            "This key isn't one of the public keys built into Kurooto (signing.PUBLIC_KEYS): installs would "
            "refuse what it signs. Wrong key file?"
        )
    return key


def sign(site: Path, base: str, version: str, key_path: Path, channel: str, critical: bool = False) -> None:
    key = trusted_key(key_path)
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
    if critical:
        ptr["critical"] = True
    (site / f"{channel}.json").write_text(
        json.dumps({"doc": ptr, "sig": signing.sign(ptr, key)}, indent=1), encoding="utf-8"
    )
    print(f"signed {version} on {channel}" + (" (critical: no waiting)" if critical else ""))


def yank(site: Path, key_path: Path, versions: list[str], reason: str = "", undo: bool = False) -> dict:
    """Add versions to the signed yank list (or take them off with undo). Returns the list's new document."""
    key = trusted_key(key_path)
    f = site / "yank.json"
    old = json.loads(f.read_text(encoding="utf-8")).get("doc", {}) if f.exists() else {}
    yanked = dict(old.get("yanked") or {})
    for v in versions:
        if undo:
            yanked.pop(v, None)
        else:
            yanked[v] = reason.strip() or "withdrawn"
    doc = {"yanked": yanked, "issued": max(time.time(), float(old.get("issued", 0)) + 1)}
    site.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"doc": doc, "sig": signing.sign(doc, key)}, indent=1), encoding="utf-8")
    print(("took off the yank list: " if undo else "yanked: ") + ", ".join(versions))
    for ch in ("stable", "beta"):
        p = site / f"{ch}.json"
        named = json.loads(p.read_text(encoding="utf-8")).get("doc", {}).get("version") if p.exists() else None
        if named in yanked:
            print(f"warning: {ch}.json still names {named}; sign a fixed version on {ch} (installs refuse it)")
    return doc


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
    b.add_argument("--critical", action="store_true", help="installs even during someone's exams")
    b.add_argument("--apk", help="the release-signed Android app (android/build/kurooto.apk)")
    s = sub.add_parser("sign")
    s.add_argument("--site", required=True)
    s.add_argument("--base", required=True)
    s.add_argument("--version", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--channel", default="stable")
    s.add_argument("--critical", action="store_true", help="a security fix: staged installs don't wait for it")
    y = sub.add_parser("yank")
    y.add_argument("--site", required=True)
    y.add_argument("--key", required=True)
    y.add_argument("--reason", default="")
    y.add_argument("--undo", action="store_true", help="take the versions off the yank list")
    y.add_argument("versions", nargs="+")
    pb = sub.add_parser("publish")
    pb.add_argument("--site", required=True)
    pb.add_argument("--message", default="release")
    a = ap.parse_args()
    if a.cmd == "keygen":
        keygen(Path(a.out), a.no_passphrase)
    elif a.cmd == "build":
        build(Path(a.site), a.base, a.version, a.notes, a.break_run, Path(a.apk) if a.apk else None, a.critical)
    elif a.cmd == "publish":
        publish(Path(a.site), a.message)
    elif a.cmd == "yank":
        yank(Path(a.site), Path(a.key), a.versions, a.reason, a.undo)
    else:
        sign(Path(a.site), a.base, a.version, Path(a.key), a.channel, a.critical)


if __name__ == "__main__":
    main()
