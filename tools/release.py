#!/usr/bin/env python3
"""Make and sign Kurooto releases. The signing key never leaves the maintainer's laptop.

    uv run tools/release.py keygen [--out ~/.config/kurooto-dev/release-key.pem] [--no-passphrase]
    uv run tools/release.py build --site SITE --base URL [--version V] [--notes TEXT] [--critical] [--break-run]
    uv run tools/release.py sign  --site SITE --base URL --version V --key PEM [--channel stable] [--critical]
                                  [--apk [--keystore KS] [--new-app-key]]
    uv run tools/release.py yank  --site SITE --key PEM V [V ...] [--reason TEXT] [--undo]
    uv run tools/release.py publish --site SITE [--message TEXT]     push SITE to the gh-pages branch (GitHub Pages)

--critical (on build or sign: either is enough, installs treat them the same) marks the release critical (a fix that
can't wait): it skips every hold, Exam season's and the staged wait (updates.staged: 48 hours, the end of exams).
yank adds versions to the signed yank list (SITE/yank.json; with --undo it takes them off): installs never update
to a yanked version, even one already downloaded. Publish after either. A yanked version that a channel pointer
still names stays refused, so sign a fixed version on that channel.

sign --apk builds the Android app from the release's own tarball (android/build.sh, so its version is the release's),
signs it with the Android release keystore (--keystore, default ~/.config/kurooto-dev/android-release.keystore; its
password from KUROOTO_KEYSTORE_PASS, else asked for and never shown, logged or written), checks its versionName and
versionCode against the version, and that its certificate is the one the last app shipped with (phones refuse an
update signed with another key; --new-app-key accepts a new one). The app goes in SITE/releases/<v>/kurooto.apk, its
url, sha256, versions and certificate in the manifest before it's signed, and signed android-<channel>.json and
android.json (the app's update check; it never moves back to an older app) are written. It needs ANDROID_HOME, a JDK
and bash. A version gets its app once: signing it again (another channel) without --apk keeps the app and rewrites the
signed android files. Installs don't carry the app inside the package: after an update they download the one their
version's signed manifest names, check its sha256, and the call line serves it at /kurooto.apk.
build warns when android/ changed since the last app that shipped, so that release needs sign --apk.
See docs/RELEASING.md for the whole routine.

SITE is a folder laid out like the GitHub Pages site:
    SITE/install.ps1, install.sh, bootstrap.py, index.html (the landing page)
    SITE/privacy.html                           docs/PRIVACY.md as a page (Google's sign-in setup links to it)
    SITE/changelog.html                         CHANGELOG.md's released versions as a page
    SITE/ongoing.html                           what's being built (CHANGELOG's unreleased part), the beta channel, and
                                                REQUESTED.md's Always and Open; SITE/roadmap.html: ROADMAP.md
    SITE/wiki/index.html, wiki/user/*.html, wiki/dev/*.html   both wikis (docs/wiki), linked from everywhere
    SITE/media/                                 its screenshots and animation (from docs/media)
    SITE/stable.json, beta.json                 signed channel pointers
    SITE/yank.json                              signed list of withdrawn versions, with reasons (yank)
    SITE/releases/<v>/manifest.json             signed list of files with sha256
    SITE/releases/<v>/kurooto-<v>.tar.gz        the source release (with requirements.lock, hash-pinned)
    SITE/releases/<v>/kurooto.apk               the Android app (sign --apk)
    SITE/android.json, android-<channel>.json   signed: the newest app (the app's update check), and each channel's
The passphrase for the key comes from KUROOTO_RELEASE_PASSPHRASE, or is asked for.
--break-run builds a version whose `kurooto run` crashes at once (only for testing rollback).
build --critical marks it in the signed manifest, sign --critical in the signed channel pointer (gone when that
channel is signed again without it). Only for fixes that can't wait.
Never build a version again after it's signed: sign pins the tarball's sha256, and a rebuilt tarball isn't the same.
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
import tarfile
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


# ------------------------------------------------------------------------------------------- the Android app
KEYSTORE = "~/.config/kurooto-dev/android-release.keystore"
PACKAGE = "io.github.avtarfr.kurooto"


def android_source(android: Path) -> str:
    """A fingerprint of the app's sources (android/ without its build output). sign --apk records it with the app, so
    build can tell whether the app changed since it last shipped."""
    h = hashlib.sha256()
    files = [p for p in android.rglob("*") if p.is_file()]
    for f in sorted(files, key=lambda p: p.relative_to(android).as_posix()):
        rel = f.relative_to(android)
        if rel.parts[0] == "build" or "__pycache__" in rel.parts:
            continue
        h.update(rel.as_posix().encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


def last_app(site: Path, before: str) -> dict:
    """The newest app that shipped in a version older than `before`: the android entry of its manifest (sign --apk
    records it there), else what the site's android.json names (build --apk wrote it, up to 0.5.18), with "apk" the
    file on the site. {} when no app has shipped."""
    limit = version_code(before)
    found: list[tuple[int, dict]] = []
    for d in (site / "releases").glob("*"):
        if not re.match(r"\d+\.\d+\.\d+", d.name) or version_code(d.name) >= limit:
            continue
        for name in ("manifest.json", "manifest.unsigned.json"):  # what was signed, else what was built
            try:
                j = json.loads((d / name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            a = (j.get("doc", {}) if name == "manifest.json" else j).get("android")
            if isinstance(a, dict) and a.get("versionName"):
                found.append((version_code(d.name), {**a, "apk": d / "kurooto.apk"}))
            break
    if found:
        return max(found, key=lambda x: x[0])[1]
    try:
        vn = str(json.loads((site / "android.json").read_text(encoding="utf-8")).get("versionName") or "")
    except (OSError, ValueError, AttributeError):
        return {}
    if not re.match(r"\d+\.\d+\.\d+", vn) or version_code(vn) >= limit:
        return {}
    return {"versionName": vn, "apk": site / "releases" / vn / "kurooto.apk"}


def app_changed(site: Path, version: str) -> str:
    """A warning when android/ changed since the last app that shipped (that release needs sign --apk); "" if not."""
    if not (ROOT / "android").is_dir():
        return ""
    last = last_app(site, version)
    fix = f"sign {version} with --apk so phones get the new app"
    if not last:
        return f"note: no phone app has shipped from {site} yet; {fix}"
    if not last.get("source"):
        return f"warning: the phone app last shipped in {last['versionName']} (no record of its sources); {fix}"
    if last["source"] != android_source(ROOT / "android"):
        return f"warning: the phone app (android/) changed since it last shipped in {last['versionName']}; {fix}"
    return ""


def build_tools() -> Path:
    """The newest build-tools of the Android SDK in ANDROID_HOME, as android/build.sh picks them."""
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    tools = [p for p in (Path(sdk) / "build-tools").glob("*") if p.is_dir()] if sdk else []
    if not tools:
        raise SystemExit("Set ANDROID_HOME to your Android SDK: sign --apk builds the app with it.")
    return max(tools, key=lambda p: [int(x) for x in re.findall(r"\d+", p.name)])


def apk_cert(apk: Path) -> str:
    """The SHA-256 of the certificate an APK is signed with (apksigner; it also checks the signature)."""
    r = subprocess.run(
        [str(build_tools() / "apksigner"), "verify", "--print-certs", str(apk)], capture_output=True, text=True
    )
    c = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", r.stdout)
    if r.returncode or len(c) != 1:
        raise SystemExit(f"{apk} isn't properly signed by exactly one key: {(r.stderr or r.stdout)[-300:]}")
    return c[0]


def apk_info(apk: Path) -> dict:
    """What the APK says it is (aapt2) and its certificate."""
    r = subprocess.run([str(build_tools() / "aapt2"), "dump", "badging", str(apk)], capture_output=True, text=True)
    m = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", r.stdout)
    if r.returncode or not m:
        raise SystemExit(f"couldn't read {apk}: {r.stderr[-300:]}")
    return {"package": m[1], "versionCode": int(m[2]), "versionName": m[3], "cert_sha256": apk_cert(apk)}


def release_sources(rel: Path, doc: dict, out: Path) -> Path:
    """The release's own tarball, checked against its manifest and unpacked into out: the app is built from exactly
    what was released, whatever the working tree holds now."""
    name = next((n for n in doc.get("files", {}) if n.endswith(".tar.gz")), "")
    if not name or not (rel / name).is_file():
        raise SystemExit(f"no release tarball in {rel}; build it first")
    if hashlib.sha256((rel / name).read_bytes()).hexdigest() != doc["files"][name]["sha256"]:
        raise SystemExit(f"{name} doesn't match its manifest (built again?); don't sign it")
    with tarfile.open(rel / name) as t:
        t.extractall(out, filter="data")
    tops = [p for p in out.iterdir() if p.is_dir()]
    if len(tops) != 1 or not (tops[0] / "android" / "build.sh").is_file():
        raise SystemExit(f"{name} has no android/build.sh")
    return tops[0]


def build_app(src: Path, keystore: Path, password: str) -> Path:
    """android/build.sh in the unpacked release, signing with the release keystore. The password only reaches it in
    its environment (build.sh hands apksigner env:KUROOTO_KEYSTORE_PASS); it's never printed, logged or written."""
    env = {**os.environ, "KUROOTO_KEYSTORE": str(keystore), "KUROOTO_KEYSTORE_PASS": password}
    r = subprocess.run(["bash", str(src / "android" / "build.sh")], cwd=src, env=env, capture_output=True, text=True)
    if r.returncode:
        said = r.stdout + r.stderr
        if password:
            said = said.replace(password, "***")
        raise SystemExit("building the app failed (wrong keystore password?):\n" + said[-1500:])
    apk = src / "android" / "build" / "kurooto.apk"
    if not apk.is_file():
        raise SystemExit("android/build.sh made no release-signed kurooto.apk")
    return apk


def make_app(site: Path, base: str, version: str, doc: dict, keystore: Path, new_key: bool = False) -> dict:
    """sign --apk: build and sign the app from the release's tarball, check it, put it in SITE/releases/<v>/ and
    return its manifest entry."""
    keystore = keystore.expanduser()
    if not keystore.is_file():
        raise SystemExit(f"no Android keystore at {keystore} (--keystore)")
    rel = site / "releases" / version
    with tempfile.TemporaryDirectory() as tmp:
        src = release_sources(rel, doc, Path(tmp))
        got = re.search(r'(?m)^version = "([^"]+)"', (src / "pyproject.toml").read_text(encoding="utf-8"))
        if not got or got[1] != version:
            raise SystemExit(f"the tarball in {rel} is {got[1] if got else '?'}, not {version}")
        source = android_source(src / "android")  # before build.sh adds android/build
        password = os.environ.get("KUROOTO_KEYSTORE_PASS")
        if password is None:
            password = getpass.getpass("Android keystore password: ")
        built = build_app(src, keystore, password)
        password = None
        info = apk_info(built)
        if info["package"] != PACKAGE:
            raise SystemExit(f"the app is {info['package']}, not {PACKAGE}")
        if info["versionName"] != version or info["versionCode"] != version_code(version):
            raise SystemExit(
                f"the app says {info['versionName']} ({info['versionCode']}), not {version} ({version_code(version)}); "
                "not signing it"
            )
        last = last_app(site, version)
        want = last.get("cert_sha256", "")
        if not want and last.get("apk") and last["apk"].is_file():
            want = apk_cert(last["apk"])
        if want and info["cert_sha256"] != want and not new_key:
            raise SystemExit(
                f"the app is signed with another key than {last['versionName']}'s ({info['cert_sha256'][:16]}…, not "
                f"{want[:16]}…): phones would refuse it as an update. Wrong keystore? (--new-app-key if every phone "
                "should uninstall the app and install it again)"
            )
        shutil.copy(built, rel / "kurooto.apk")
    data = (rel / "kurooto.apk").read_bytes()
    print(f"app {version} (code {info['versionCode']}) signed: {rel / 'kurooto.apk'} ({len(data) // 1024} KB)")
    return {
        "file": "kurooto.apk",
        "url": f"{base.rstrip('/')}/releases/{version}/kurooto.apk",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "versionCode": info["versionCode"],
        "versionName": info["versionName"],
        "cert_sha256": info["cert_sha256"],
        "source": source,
    }


def app_pointers(site: Path, base: str, version: str, app: dict, channel: str, key: Ed25519PrivateKey) -> None:
    """Signed android-<channel>.json, and android.json (what the app's update check and the pairing page read) unless
    it already names a newer app. The four plain fields on top are for apps up to 0.5.18, which read them unsigned;
    the signed doc repeats them."""
    doc = {
        "versionCode": app["versionCode"],
        "versionName": app["versionName"],
        "url": app["url"],
        "sha256": app["sha256"],
        "size": app["size"],
        "manifest_url": f"{base.rstrip('/')}/releases/{version}/manifest.json",
        "channel": channel,
        "issued": time.time(),
    }
    plain = {k: doc[k] for k in ("versionCode", "versionName", "url", "sha256")}
    body = json.dumps({**plain, "doc": doc, "sig": signing.sign(doc, key)}, indent=1)
    (site / f"android-{channel}.json").write_text(body, encoding="utf-8")
    try:
        now = int(json.loads((site / "android.json").read_text(encoding="utf-8")).get("versionCode") or 0)
    except (OSError, ValueError, AttributeError):
        now = 0
    if app["versionCode"] >= now:
        (site / "android.json").write_text(body, encoding="utf-8")
        print(f"android.json: app {app['versionName']}")
    else:
        print(f"android.json keeps the newer app (code {now}); android-{channel}.json names {app['versionName']}")


def fresh_docs() -> None:
    """Refuse to build a release whose generated docs are older than the code: the AI's own manual
    (src/kurooto/data/ai-manual.md, tools/gen_ai_manual.py) and the settings guide."""
    for tool, what in (("gen_ai_manual.py", "the AI's manual"), ("gen_settings_guide.py", "the settings guide")):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / tool), "--check"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"{what} is out of date: python tools/{tool}, then commit it. {r.stderr.strip()}")


def build(site: Path, base: str, version: str | None, notes: str, break_run: bool, critical=False) -> str:
    fresh_docs()
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
                "*.apk",  # the app isn't in the package: sign --apk makes it, installs download it
            ),
        )
        shutil.rmtree(src / "docs" / "media", ignore_errors=True)  # screenshots: the site has them, releases don't
        pp = src / "pyproject.toml"
        text = pp.read_text(encoding="utf-8")
        if version:
            text = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', text, count=1)
            pp.write_text(text, encoding="utf-8")
        version = re.search(r'(?m)^version = "([^"]+)"', text)[1]
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
    (site / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {version}: {rel / name} ({len(data) // 1024} KB)")
    warn = app_changed(site, version)
    if warn:
        print(warn)
    return version


def site_pages(site: Path) -> None:
    """The site's own pages: the installers, the landing page, its media, the privacy and changelog pages, both wikis,
    and the in-progress page (what's being built, the beta channel, what's requested)."""
    site.mkdir(parents=True, exist_ok=True)
    for f in ("install.ps1", "install.sh", "bootstrap.py", "index.html"):
        shutil.copy(ROOT / "installer" / f, site / f)
    (site / "privacy.html").write_text(privacy_page(), encoding="utf-8")
    (site / "changelog.html").write_text(changelog_page(), encoding="utf-8")
    (site / "ongoing.html").write_text(ongoing_page(site), encoding="utf-8")
    (site / "roadmap.html").write_text(doc_page("ROADMAP.md", "Roadmap"), encoding="utf-8")
    wiki_pages(site)
    if (ROOT / "docs" / "media").is_dir():  # the landing page's screenshots and animation
        shutil.copytree(ROOT / "docs" / "media", site / "media", dirs_exist_ok=True)


REPO = "https://github.com/avtarfr/kurooto/blob/main/"
START, END = "<!-- PRIVACY:START", "<!-- PRIVACY:END -->"


def frame(title: str, body: str, depth: int = 0, updated: str = "") -> str:
    """A page of the site in the privacy page's frame (header, theme switch, footer), with body as its content. depth:
    how many folders down the page lives (wiki/user/x.html: 2), so the frame's own links still work."""
    page = (ROOT / "installer" / "privacy.html").read_text(encoding="utf-8")
    a, b = page.index(START), page.index(END) + len(END)
    head, tail = page[:a], page[b:]
    if updated:
        tail = re.sub(r'<p class="updated">.*?</p>', f'<p class="updated">{updated}</p>', tail, count=1, flags=re.S)
    if depth:
        up = "../" * depth
        fix = re.compile(r'(href|src)="(?!https?:|#|mailto:|data:|/)([^"]*)"')
        head, tail = (fix.sub(lambda m: f'{m[1]}="{up}{m[2]}"', x) for x in (head, tail))
    head = head.replace("<title>Privacy · Kurooto</title>", f"<title>{html.escape(title)} · Kurooto</title>")
    return head + body + tail


def privacy_page() -> str:
    """installer/privacy.html with docs/PRIVACY.md in it, so the page never drifts from the document."""
    page = (ROOT / "installer" / "privacy.html").read_text(encoding="utf-8")
    body = md_html((ROOT / "docs" / "PRIVACY.md").read_text(encoding="utf-8"))
    a, b = page.index(START), page.index(END) + len(END)
    return page[:a] + body + page[b:]


def released(text: str) -> tuple[str, str]:
    """CHANGELOG.md split into (what's out, what's being built: the "(unreleased)" sections)."""
    parts = re.split(r"(?m)^(?=## )", text)
    out = [p for p in parts if not re.match(r"## .*\(unreleased\)", p)]
    wip = [p for p in parts if re.match(r"## .*\(unreleased\)", p)]
    return "".join(out), "".join(wip)


def changelog_page() -> str:
    """CHANGELOG.md as a page of the site, in the privacy page's frame (so it looks like the rest of the site). What's
    still being built is on the in-progress page."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    text = re.sub(r"^# Changelog\s*\n", "", text)
    out, wip = released(text)
    intro = (
        "<h1>What's new</h1>\n<p>Every version of Kurooto, newest first. A new version arrives by itself at night "
        "(on the beta channel first, then stable); <code>kurooto update --now</code> gets it at once."
        + (' What\'s being built for the next one is <a href="ongoing.html">in progress</a>.' if wip else "")
        + "</p>\n"
    )
    return frame(
        "Changelog",
        intro + md_html(out),
        updated=f'Made from <a href="{REPO}CHANGELOG.md">CHANGELOG.md</a> when the site is built.',
    )


def channel_version(site: Path, channel: str) -> str:
    try:
        return str(json.loads((site / f"{channel}.json").read_text(encoding="utf-8"))["doc"]["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def section(md: str, *names: str) -> str:
    """The "## name" sections of a Markdown text, in the order asked."""
    parts = {m[1].strip(): m[0] for m in re.finditer(r"(?ms)^## (.+?)$.*?(?=^## |\Z)", md)}
    return "".join(parts.get(n, "") for n in names)


def ongoing_page(site: Path) -> str:
    """What's being built now (CHANGELOG's unreleased part), the beta channel and how to get it, and what people have
    asked for (REQUESTED.md's Always and Open), with a link to the roadmap."""
    stable, beta = channel_version(site, "stable"), channel_version(site, "beta")
    _, wip = released((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    req = (ROOT / "docs" / "REQUESTED.md").read_text(encoding="utf-8")
    versions = " · ".join(
        x
        for x in (
            f"stable: <strong>{stable}</strong>" if stable else "",
            f"beta: <strong>{beta}</strong>" if beta else "",
        )
        if x
    )
    body = [
        "<h1>In progress</h1>",
        "<p>What's being built for the next version, how to try versions before everyone else, and what people have "
        'asked for. Released versions are in the <a href="changelog.html">changelog</a>.</p>',
        '<h2 id="channels">Stable and beta</h2>',
        f"<p>Right now: {versions}.</p>" if versions else "",
        "<p><strong>Stable</strong> (the default) gets a version once it has run on the beta channel for a while. "
        "<strong>Beta</strong> gets every version first, the day it's signed: newer features sooner, and now and then "
        "a rough edge. Both update by themselves at night, and an update that keeps crashing is rolled back on its "
        "own.</p>",
        "<p><strong>To join beta</strong>: in the dashboard, Settings → updates → <code>channel</code>: "
        '<code>beta</code> (or <code>"updates": {"channel": "beta"}</code> in settings.json), then '
        "<code>kurooto update --now</code> to get the newest at once. <strong>To leave</strong>: set it back to "
        "<code>stable</code>; Kurooto never goes back to an older version, so you stay where you are until stable "
        "catches up.</p>",
        '<h2 id="being-built">Being built now</h2>',
        md_html(re.sub(r"(?m)^## ", "### ", wip)) if wip.strip() else "<p>Nothing unreleased right now.</p>",
        '<h2 id="requested">Requested</h2>',
        f'<p>From <a href="{REPO}docs/REQUESTED.md">REQUESTED.md</a>: what people have asked for. Ideas nobody has '
        'asked for yet are on the <a href="roadmap.html">roadmap</a>. To ask for something, open an issue on GitHub or '
        'tell your own Kurooto: "add to the requested list: …".</p>',
        md_html(re.sub(r"(?m)^## ", "### ", section(req, "Always", "Open"))),
    ]
    return frame(
        "In progress",
        "\n".join(x for x in body if x),
        updated=f'Made from <a href="{REPO}CHANGELOG.md">CHANGELOG.md</a> and '
        f'<a href="{REPO}docs/REQUESTED.md">REQUESTED.md</a> when the site is built.',
    )


def doc_page(name: str, title: str) -> str:
    """One of docs/*.md as a page."""
    text = (ROOT / "docs" / name).read_text(encoding="utf-8")
    return frame(
        title,
        md_html(text, link=lambda h: wiki_link("docs/" + name, h, 0)),
        updated=f'Made from <a href="{REPO}docs/{name}">docs/{name}</a> when the site is built.',
    )


WIKIS = {
    "user": ("User wiki", "Everything Kurooto does and how to use it: every feature, command, setting and fix."),
    "dev": (
        "Developer wiki",
        "How Kurooto is built, for people and for AI agents: every subsystem, how to add a "
        "feature, tests and releases.",
    ),
}


def wiki_link(src: str, href: str, depth: int) -> str:
    """A link in a Markdown file of the repo (src, e.g. docs/wiki/user/calls.md), as it works on the site: another
    wiki page, a docs page the site has, or the file on GitHub. depth: how far the page is below the site's root."""
    import posixpath

    if re.match(r"(https?://|#|mailto:)", href):
        return href
    path, _, frag = href.partition("#")
    target = posixpath.normpath(posixpath.join(posixpath.dirname(src), path)) if path else src
    up = "../" * depth
    m = re.fullmatch(r"docs/wiki/(user|dev)/([\w.-]+)\.md", target)
    if m:
        out = f"{up}wiki/{m[1]}/{m[2]}.html"
    else:
        out = {
            "CHANGELOG.md": f"{up}changelog.html",
            "docs/PRIVACY.md": f"{up}privacy.html",
            "docs/ROADMAP.md": f"{up}roadmap.html",
        }.get(target, REPO + target)
    return out + (f"#{frag}" if frag else "")


def title_of(md: str, fallback: str) -> str:
    m = re.search(r"(?m)^# (.+)$", md)
    return re.sub(r"[`*]", "", m[1]).strip() if m else fallback


def wiki_pages(site: Path) -> None:
    """docs/wiki/<user|dev>/*.md as site/wiki/<user|dev>/*.html, each with the wiki's page list on top, and
    site/wiki/index.html for both. /help links here."""
    root = ROOT / "docs" / "wiki"
    cards = []
    for part, (name, blurb) in WIKIS.items():
        d = root / part
        if not d.is_dir():
            continue
        files = {f.stem: f for f in sorted(d.glob("*.md"))}
        index_md = files["index"].read_text(encoding="utf-8") if "index" in files else ""
        linked = [m[1] for m in re.finditer(r"\]\(([\w.-]+)\.md(?:#[^)]*)?\)", index_md)]
        order = ["index", *dict.fromkeys(s for s in linked if s in files and s != "index")]
        order += [s for s in files if s not in order]
        titles = {s: title_of(files[s].read_text(encoding="utf-8"), s.replace("-", " ").title()) for s in order}
        other = "dev" if part == "user" else "user"
        nav = (
            f'<nav class="wiki-nav" aria-label="{name}"><a class="wiki-home" href="../index.html">Wikis</a> · '
            f"<strong>{name}</strong>: "
            + " ".join(f'<a href="{s}.html">{html.escape(titles[s] if s != "index" else "Start")}</a>' for s in order)
            + f' · <a href="../{other}/index.html">{WIKIS[other][0]}</a></nav>'
        )
        out = site / "wiki" / part
        out.mkdir(parents=True, exist_ok=True)
        for s in order:
            src = f"docs/wiki/{part}/{s}.md"
            text = files[s].read_text(encoding="utf-8")
            body = nav + "\n" + md_html(text, link=lambda h, src=src: wiki_link(src, h, 2))
            page = frame(
                f"{titles[s]} · {name}",
                body,
                depth=2,
                updated=f'Made from <a href="{REPO}{src}">{src}</a> when the site is built. Something wrong or '
                'missing? <a href="https://github.com/avtarfr/kurooto/issues">Open an issue</a>.',
            )
            # the active page in the list
            page = page.replace(f'<a href="{s}.html">', f'<a href="{s}.html" aria-current="page">', 1)
            (out / f"{s}.html").write_text(page, encoding="utf-8")
        cards.append(
            f'<h2 id="{part}"><a href="{part}/index.html">{name}</a></h2><p>{html.escape(blurb)}</p><ul>'
            + "".join(f'<li><a href="{part}/{s}.html">{html.escape(titles[s])}</a></li>' for s in order if s != "index")
            + "</ul>"
        )
    _, wip = released((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    ahead = re.search(r"(?m)^## (\S+) \(unreleased\)", wip)
    note = (
        f"<p>They describe the version being built ({ahead[1]}): until it's out, a few things here are still on "
        'their way; <a href="../ongoing.html#being-built">in progress</a> lists them.</p>'
        if ahead
        else ""
    )
    body = (
        "<h1>Kurooto wikis</h1><p>Two wikis, both made from the repository, so they say what the code does. Also: "
        '<a href="../changelog.html">the changelog</a>, <a href="../ongoing.html">what\'s in progress and the beta '
        'channel</a>, and <a href="../privacy.html">privacy</a>.</p>' + note + "".join(cards)
    )
    (site / "wiki").mkdir(parents=True, exist_ok=True)
    (site / "wiki" / "index.html").write_text(
        frame("Wikis", body, depth=1, updated=f'Made from <a href="{REPO}docs/wiki">docs/wiki</a>.'), encoding="utf-8"
    )


def _inline(text: str, link=None) -> str:
    """Markdown inside a line: `code`, **bold**, [links](url); everything else escaped. link: how a relative link is
    turned into the site's (default: the file in the repo's docs folder on GitHub)."""
    out, last = [], 0
    for m in re.finditer(r"`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)", text):
        out.append(html.escape(text[last : m.start()], quote=False))
        if m[1] is not None:
            out.append(f"<code>{html.escape(m[1], quote=False)}</code>")
        elif m[2] is not None:
            out.append(f"<strong>{_inline(m[2], link)}</strong>")
        else:
            if re.match(r"(https?://|#|mailto:)", m[4]):
                href = m[4]
            elif link is not None:
                href = link(m[4])
            else:
                href = REPO + "docs/" + m[4]
            out.append(f'<a href="{html.escape(href)}">{_inline(m[3], link)}</a>')
        last = m.end()
    out.append(html.escape(text[last:], quote=False))
    return "".join(out)


def md_html(text: str, link=None) -> str:
    """Enough Markdown for the docs and the wikis: headings, paragraphs, lists (bulleted and numbered, with wrapped
    lines; nested ones flattened), tables, fenced code, quotes and rules. HTML comments are dropped."""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    rows: list[list[str]] = []
    quote: list[str] = []
    kind = "ul"
    code: list[str] | None = None
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)

    def flush() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para), link)}</p>")
            para.clear()
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{_inline(i, link)}</li>" for i in items) + f"</{kind}>")
            items.clear()
        if quote:
            out.append(f"<blockquote><p>{_inline(' '.join(quote), link)}</p></blockquote>")
            quote.clear()
        if rows:
            head, *body = [r for r in rows if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]
            th = "".join(f"<th>{_inline(c, link)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{_inline(c, link)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
            rows.clear()

    for line in text.splitlines():
        s = line.rstrip()
        if code is not None:
            if s.strip().startswith("```"):
                out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        if s.strip().startswith("```"):
            flush()
            code = []
        elif not s.strip():
            flush()
        elif m := re.match(r"(#{1,6})\s+(.*)", s):
            flush()
            n, title = len(m[1]), m[2].strip()
            slug = re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")
            out.append(f'<h{n} id="{slug}">{_inline(title, link)}</h{n}>')
        elif re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", s):
            flush()
            out.append("<hr>")
        elif s.startswith("|"):
            if para or items or quote:
                flush()
            rows.append([c.strip() for c in re.split(r"(?<!\\)\|", s.strip().strip("|"))])
        elif m := re.match(r"\s*>\s?(.*)", s):
            if para or items or rows:
                flush()
            quote.append(m[1])
        elif m := re.match(r"\s*(?:([-*+])|(\d+)[.)])\s+(.*)", s):
            new = "ol" if m[2] else "ul"
            if para or rows or quote or (items and new != kind and not line.startswith(" ")):
                flush()
            if not items:
                kind = new
            items.append(m[3])
        elif items and line.startswith(" "):
            items[-1] += " " + s.strip()
        else:
            if items or rows or quote:
                flush()
            para.append(s.strip())
    if code is not None:
        out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
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


def sign(
    site: Path,
    base: str,
    version: str,
    key_path: Path,
    channel: str,
    critical: bool = False,
    apk: bool = False,
    keystore: Path = Path(KEYSTORE),
    new_app_key: bool = False,
) -> None:
    key = trusted_key(key_path)
    rel = site / "releases" / version
    doc = json.loads((rel / "manifest.unsigned.json").read_text(encoding="utf-8"))
    if apk:
        if doc.get("android"):
            raise SystemExit(
                f"{version} already has its app ({doc['android'].get('sha256', '')[:12]}…); sign it without --apk, "
                "which keeps that app"
            )
        doc["android"] = make_app(site, base, version, doc, keystore, new_app_key)  # in the doc before it's signed
        (rel / "manifest.unsigned.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
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
    if isinstance(doc.get("android"), dict):
        app_pointers(site, base, version, doc["android"], channel, key)
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
    b.add_argument("--critical", action="store_true", help="critical: skips every hold (exam season, staged waiting)")
    b.add_argument("--apk", help=argparse.SUPPRESS)  # gone: the app is made at sign time (sign --apk)
    s = sub.add_parser("sign")
    s.add_argument("--site", required=True)
    s.add_argument("--base", required=True)
    s.add_argument("--version", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--channel", default="stable")
    s.add_argument("--critical", action="store_true", help="critical: skips every hold (exam season, staged waiting)")
    s.add_argument("--apk", action="store_true", help="build the Android app from the release and sign it too")
    s.add_argument("--keystore", default=os.environ.get("KUROOTO_KEYSTORE") or KEYSTORE, help="Android keystore")
    s.add_argument("--new-app-key", action="store_true", help="accept an app signed with a new key (phones reinstall)")
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
        if a.apk:
            raise SystemExit("build --apk is gone: the app is built and signed with the release, by sign --apk")
        build(Path(a.site), a.base, a.version, a.notes, a.break_run, a.critical)
    elif a.cmd == "publish":
        publish(Path(a.site), a.message)
    elif a.cmd == "yank":
        yank(Path(a.site), Path(a.key), a.versions, a.reason, a.undo)
    else:
        sign(
            Path(a.site), a.base, a.version, Path(a.key), a.channel, a.critical, a.apk, Path(a.keystore), a.new_app_key
        )


if __name__ == "__main__":
    main()
