"""The Android app that goes with the running version, for the call line to hand to phones at /kurooto.apk.

A release doesn't carry the app inside its package: the package's hash is fixed when it's built, and the app is built
and signed later, when the maintainer signs the release (tools/release.py sign --apk). The app's url, sha256 and
version are in the release's signed manifest instead ("android"). ensure() reads that manifest for the version that
runs, checks its signature and version, downloads the app once, checks it against the signed sha256 (a mismatch is
thrown away) and keeps it in <data>/phone-app/kurooto.apk with app.json beside it. A release without an app keeps the
one already here. current() is what the call line serves: that file while it still matches its recorded hash, else
the copy an older package carried inside it (data/kurooto.apk, from build --apk up to 0.5.18), else none. The line
also serves TAG (kurooto-app.json, {"versionName": ...}) beside it, so its pairing page can say which app it hands out.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.error
from pathlib import Path

from kurooto.core.state import jload, jsave
from kurooto.update.updater import UpdateError, Updater

EMBEDDED = Path(__file__).resolve().parent.parent / "data" / "kurooto.apk"
NAME = "kurooto.apk"
TAG = "kurooto-app.json"  # beside the app on the call line: its version, for the pairing page


def folder(data: Path) -> Path:
    return Path(data) / "phone-app"


def _sha(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def fetched(data: Path) -> tuple[Path, dict] | None:
    """The downloaded app and its record, when the file still matches the hash it was checked against."""
    rec = jload(folder(data) / "app.json", {}) or {}
    f = folder(data) / NAME
    if rec.get("sha256") and f.is_file() and _sha(f) == rec["sha256"]:
        return f, rec
    return None


def current(data: Path) -> Path | None:
    """The app the call line serves: the downloaded one, else the one inside an older package, else none."""
    got = fetched(data)
    if got:
        return got[0]
    return EMBEDDED if EMBEDDED.is_file() else None


def version(data: Path) -> str:
    """The served app's version ("" when it isn't known: the copy inside an older package, or none)."""
    got = fetched(data)
    return str(got[1].get("versionName") or "") if got else ""


def fingerprint(data: Path) -> str:
    """The served app's sha256 ("" for none): part of the call line's fingerprint, so a new app redeploys it."""
    f = current(data)
    return _sha(f) if f else ""


def ensure(u: Updater, data: Path, version: str) -> str:
    """Get the app named in `version`'s signed manifest, unless it's here already. Returns "fetched", "kept" (nothing
    to download), "none" (that release has no app, or isn't on the site) or "skipped" (a source tree). Raises
    UpdateError for a manifest that isn't signed or doesn't match, or a download that doesn't match its hash."""
    if not version or "+" in version:
        return "skipped"
    d = folder(data)
    rec = jload(d / "app.json", {}) or {}
    have = fetched(data)
    if rec.get("for") == version and (rec.get("none") or have):
        return "kept"  # this version was looked at already: no network
    try:
        man = u._signed(f"{u.base}/releases/{version}/manifest.json")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "none"  # not published (a build that never shipped): not recorded, so it's looked for again
        raise UpdateError(f"couldn't read the release manifest ({e.code})") from e
    if str(man.get("version")) != version:
        raise UpdateError("the release manifest isn't this version's; ignored")
    a = man.get("android")
    if not isinstance(a, dict) or not str(a.get("url", "")) or not re.fullmatch(r"[0-9a-f]{64}", str(a.get("sha256"))):
        jsave(d / "app.json", {**rec, "for": version, "none": True})  # keeps an older app, if one is here
        return "none"
    meta = {"for": version, "none": False, "sha256": a["sha256"], "versionName": a.get("versionName")}
    if have and have[1].get("sha256") == a["sha256"]:
        jsave(d / "app.json", {**have[1], **meta})
        return "kept"
    body = u._get(str(a["url"]), timeout=300)
    if hashlib.sha256(body).hexdigest() != a["sha256"]:
        raise UpdateError("the phone app didn't match its signed checksum; not kept")
    d.mkdir(parents=True, exist_ok=True)
    part = d / (NAME + ".partial")
    part.write_bytes(body)
    os.replace(part, d / NAME)
    jsave(d / "app.json", {**meta, "fetched": time.time()})
    return "fetched"
