"""The phone app ships with the release it belongs to: tools/release.py sign --apk builds it from the release's own
tarball (here a fake android/build.sh and a fake SDK), checks its version and signing key, records it in the manifest
before signing and writes signed android.json files; the password never lands anywhere. An install then downloads
the app its version's signed manifest names, checks it, and the call line serves it."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from kurooto.update import phone_app, signing
from kurooto.update.updater import UpdateError, Updater
from tests.unit.test_quick_updates import release_tool
from tests.unit.test_update import KEY, OTHER, PUB, wrap
from tests.unit.test_update import site as site  # noqa: F401 (the fixture)

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "kspw-not-real"  # a throwaway, for the fake build.sh
CERT = "ab" * 32
needs_bash = pytest.mark.skipif(os.name == "nt", reason="android/build.sh is bash")

FAKE_BUILD = r"""#!/usr/bin/env bash
# a stand-in for android/build.sh: checks it got the keystore, writes an "APK" that the fake aapt2 reads back
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
[ -f "$KUROOTO_KEYSTORE" ] || { echo "no keystore" >&2; exit 1; }
[ "$KUROOTO_KEYSTORE_PASS" = "$FAKE_WANT_PASS" ] || { echo "keystore password was $KUROOTO_KEYSTORE_PASS" >&2; exit 1; }
V=$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/../pyproject.toml")
NAME=${FAKE_APK_VERSION:-$V}
IFS=. read -r MA MI PA <<< "$NAME"
CODE=$(( ((MA * 1000 + MI) * 1000 + PA) * 10 + 9 ))
mkdir -p "$HERE/build"
echo "package: name='io.github.avtarfr.kurooto' versionCode='$CODE' versionName='$NAME'" > "$HERE/build/kurooto.apk"
echo "built"
"""
FAKE_AAPT2 = '#!/usr/bin/env bash\ncat "$3"\n'
FAKE_APKSIGNER = (
    '#!/usr/bin/env bash\necho "Signer #1 certificate DN: CN=Kurooto"\n'
    'echo "Signer #1 certificate SHA-256 digest: ${FAKE_CERT}"\n'
)


def _exe(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    p.chmod(0o755)


def tarball(version: str) -> bytes:
    b = io.BytesIO()
    files = {
        "pyproject.toml": f'[project]\nname = "kurooto"\nversion = "{version}"\n',
        "android/build.sh": FAKE_BUILD,
        "android/src/A.java": "class A {}\n",
    }
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"kurooto-{version}/{name}")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return b.getvalue()


@pytest.fixture
def rel(tmp_path, monkeypatch):
    """The release tool with a fake SDK, a throwaway update key and Android keystore, and a site with 0.5.19 built."""
    monkeypatch.setenv("KUROOTO_EXTRA_UPDATE_KEY", PUB)
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "sdk"))
    monkeypatch.setenv("KUROOTO_KEYSTORE_PASS", PASSWORD)
    monkeypatch.setenv("FAKE_WANT_PASS", PASSWORD)
    monkeypatch.setenv("FAKE_CERT", CERT)
    monkeypatch.delenv("FAKE_APK_VERSION", raising=False)
    _exe(tmp_path / "sdk/build-tools/35.0.0/aapt2", FAKE_AAPT2)
    _exe(tmp_path / "sdk/build-tools/35.0.0/apksigner", FAKE_APKSIGNER)
    _exe(tmp_path / "sdk/build-tools/9.0.0/aapt2", "#!/bin/sh\nexit 1\n")  # older: never picked
    (tmp_path / "ks").write_bytes(b"not a real keystore")
    pem = tmp_path / "key.pem"
    pem.write_bytes(
        KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    tool = release_tool()
    tool.test = {"site": tmp_path / "site", "pem": pem, "ks": tmp_path / "ks", "base": "https://example.test/k"}
    built(tool, "0.5.19")
    return tool


def built(tool, version: str) -> Path:
    """What `build` leaves for a version: its tarball and unsigned manifest."""
    r = tool.test["site"] / "releases" / version
    r.mkdir(parents=True, exist_ok=True)
    data = tarball(version)
    name = f"kurooto-{version}.tar.gz"
    (r / name).write_bytes(data)
    doc = {"version": version, "files": {name: {"url": "u", "sha256": hashlib.sha256(data).hexdigest(), "size": 1}}}
    (r / "manifest.unsigned.json").write_text(json.dumps(doc))
    return r


def sign(tool, version="0.5.19", channel="beta", **kw):
    t = tool.test
    tool.sign(t["site"], t["base"], version, t["pem"], channel, keystore=t["ks"], **kw)


def signed(f: Path) -> dict:
    j = json.loads(f.read_text())
    assert signing.verify(j["doc"], j["sig"], [PUB])
    return j


def everything_written(root: Path) -> bytes:
    return b"".join(f.read_bytes() for f in root.rglob("*") if f.is_file())


@needs_bash
def test_sign_apk_puts_the_app_in_the_signed_manifest_and_android_json(rel, tmp_path, capsys):
    site = rel.test["site"]
    sign(rel, apk=True)
    apk = site / "releases/0.5.19/kurooto.apk"
    man = signed(site / "releases/0.5.19/manifest.json")["doc"]
    a = man["android"]
    assert a["sha256"] == hashlib.sha256(apk.read_bytes()).hexdigest() and a["size"] == apk.stat().st_size
    assert (a["versionName"], a["versionCode"]) == ("0.5.19", rel.version_code("0.5.19")) == ("0.5.19", 50199)
    assert a["url"] == "https://example.test/k/releases/0.5.19/kurooto.apk" and a["cert_sha256"] == CERT
    assert len(a["source"]) == 64
    for name in ("android.json", "android-beta.json"):
        j = signed(site / name)
        assert j["doc"]["sha256"] == a["sha256"] and j["doc"]["channel"] == "beta"
        assert j["doc"]["manifest_url"].endswith("/releases/0.5.19/manifest.json")
        assert {k: j[k] for k in ("versionCode", "versionName", "url", "sha256")} == {
            k: a[k] for k in ("versionCode", "versionName", "url", "sha256")
        }  # what apps up to 0.5.18 read, unsigned
    assert signed(site / "beta.json")["doc"]["version"] == "0.5.19"
    # the password is nowhere: not in the site, not in anything written under the test's folder, not on screen
    assert PASSWORD.encode() not in everything_written(tmp_path)
    out = capsys.readouterr()
    assert PASSWORD not in out.out + out.err and "android.json: app 0.5.19" in out.out


@needs_bash
def test_a_version_mismatch_is_refused_and_nothing_is_written(rel, monkeypatch):
    monkeypatch.setenv("FAKE_APK_VERSION", "0.5.18")
    site = rel.test["site"]
    with pytest.raises(SystemExit, match=r"says 0\.5\.18 .*not 0\.5\.19"):
        sign(rel, apk=True)
    assert not (site / "releases/0.5.19/kurooto.apk").exists() and not (site / "android.json").exists()
    assert "android" not in json.loads((site / "releases/0.5.19/manifest.unsigned.json").read_text())
    assert not (site / "releases/0.5.19/manifest.json").exists()


@needs_bash
def test_a_wrong_password_fails_without_showing_it(rel, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FAKE_WANT_PASS", "the-right-one")
    with pytest.raises(SystemExit) as e:
        sign(rel, apk=True)
    assert "***" in str(e.value) and PASSWORD not in str(e.value)
    out = capsys.readouterr()
    assert PASSWORD not in out.out + out.err and PASSWORD.encode() not in everything_written(tmp_path)


@needs_bash
def test_the_password_is_asked_for_when_not_in_the_environment(rel, monkeypatch):
    monkeypatch.delenv("KUROOTO_KEYSTORE_PASS")
    asked = []
    monkeypatch.setattr(rel.getpass, "getpass", lambda prompt: asked.append(prompt) or PASSWORD)
    sign(rel, apk=True)
    assert asked == ["Android keystore password: "] and "KUROOTO_KEYSTORE_PASS" not in os.environ
    assert (rel.test["site"] / "releases/0.5.19/kurooto.apk").is_file()


@needs_bash
def test_a_tarball_built_again_after_the_manifest_is_refused(rel):
    (rel.test["site"] / "releases/0.5.19/kurooto-0.5.19.tar.gz").write_bytes(tarball("0.5.19") + b"x")
    with pytest.raises(SystemExit, match="doesn't match its manifest"):
        sign(rel, apk=True)


@needs_bash
def test_another_signing_key_than_the_last_apps_is_refused(rel, monkeypatch):
    sign(rel, apk=True)
    built(rel, "0.5.20")
    monkeypatch.setenv("FAKE_CERT", "cd" * 32)
    with pytest.raises(SystemExit, match="phones would refuse it"):
        sign(rel, "0.5.20", apk=True)
    sign(rel, "0.5.20", apk=True, new_app_key=True)
    assert signed(rel.test["site"] / "android.json")["doc"]["versionName"] == "0.5.20"


@needs_bash
def test_the_key_is_checked_against_an_app_from_before_sign_apk(rel):
    site = rel.test["site"]
    (site / "releases/0.5.4").mkdir(parents=True)
    (site / "releases/0.5.4/kurooto.apk").write_text("old")  # the fake apksigner gives it CERT too
    (site / "android.json").write_text(json.dumps({"versionCode": 50049, "versionName": "0.5.4"}))
    assert rel.last_app(site, "0.5.19") == {"versionName": "0.5.4", "apk": site / "releases/0.5.4/kurooto.apk"}
    sign(rel, apk=True)
    assert signed(site / "android.json")["doc"]["versionName"] == "0.5.19"


@needs_bash
def test_signing_again_keeps_the_app_and_android_json_never_goes_back(rel, capsys):
    site = rel.test["site"]
    sign(rel, apk=True)
    sha = signed(site / "android.json")["doc"]["sha256"]
    with pytest.raises(SystemExit, match="already has its app"):
        sign(rel, channel="stable", apk=True)
    sign(rel, channel="stable")  # promoted: the same app, now on stable too
    assert signed(site / "releases/0.5.19/manifest.json")["doc"]["android"]["sha256"] == sha
    assert signed(site / "android-stable.json")["doc"]["sha256"] == sha
    j = json.loads((site / "android.json").read_text())
    (site / "android.json").write_text(json.dumps({**j, "versionCode": 50209}))  # a newer app is out
    sign(rel, channel="stable")
    assert json.loads((site / "android.json").read_text())["versionCode"] == 50209
    assert "keeps the newer app" in capsys.readouterr().out


def test_build_warns_when_the_app_changed_since_it_last_shipped(tmp_path):
    rel = release_tool()
    site = tmp_path / "site"
    assert "no phone app has shipped" in rel.app_changed(site, "0.5.19")
    site.mkdir()
    (site / "android.json").write_text(json.dumps({"versionCode": 50049, "versionName": "0.5.4"}))
    assert "last shipped in 0.5.4" in rel.app_changed(site, "0.5.19")
    r = site / "releases/0.5.18"
    r.mkdir(parents=True)
    now = rel.android_source(ROOT / "android")
    (r / "manifest.json").write_text(json.dumps({"doc": {"android": {"versionName": "0.5.18", "source": now}}}))
    assert rel.app_changed(site, "0.5.19") == ""
    (r / "manifest.json").write_text(json.dumps({"doc": {"android": {"versionName": "0.5.18", "source": "0" * 64}}}))
    assert "changed since it last shipped in 0.5.18" in rel.app_changed(site, "0.5.19")
    assert "last shipped in 0.5.4" in rel.app_changed(site, "0.5.18")  # only older versions count


def test_build_apk_is_gone(monkeypatch):
    rel = release_tool()
    monkeypatch.setattr("sys.argv", ["release.py", "build", "--site", "s", "--base", "b", "--apk", "x.apk"])
    with pytest.raises(SystemExit, match="sign --apk"):
        rel.main()


# ------------------------------------------------------------------------------------------- the install's side
APK = b"PK\x03\x04 a phone app"


def release(site, version="0.5.19", apk=APK, key=KEY, android=True, sha=None):
    """A signed manifest for version (with an android entry) and the app on the fake site."""
    site.files[f"/releases/{version}/kurooto.apk"] = apk
    doc = {"version": version, "files": {}}
    if android:
        doc["android"] = {
            "url": f"{site.base}/releases/{version}/kurooto.apk",
            "sha256": sha or hashlib.sha256(apk).hexdigest(),
            "versionName": version,
            "versionCode": 50199,
        }
    site.files[f"/releases/{version}/manifest.json"] = wrap(doc, key)


def upd(tmp_path, site):
    return Updater(tmp_path / "app", tmp_path / "state", site.base, keys=[PUB])


def test_the_app_is_downloaded_checked_kept_and_reused(tmp_path, site):
    release(site)
    u, data = upd(tmp_path, site), tmp_path / "data"
    assert phone_app.current(data) in (None, phone_app.EMBEDDED)
    assert phone_app.ensure(u, data, "0.5.19") == "fetched"
    assert phone_app.current(data).read_bytes() == APK
    assert phone_app.fingerprint(data) == hashlib.sha256(APK).hexdigest()
    del site.files["/releases/0.5.19/manifest.json"]
    assert phone_app.ensure(u, data, "0.5.19") == "kept"  # looked at already: no network
    # a newer version naming the same app: nothing downloaded
    release(site, "0.5.20")
    del site.files["/releases/0.5.20/kurooto.apk"]
    assert phone_app.ensure(u, data, "0.5.20") == "kept"
    # a version without an app keeps the one here
    release(site, "0.5.21", android=False)
    assert phone_app.ensure(u, data, "0.5.21") == "none" and phone_app.current(data).read_bytes() == APK


def test_a_bad_app_or_manifest_is_refused(tmp_path, site):
    data = tmp_path / "data"
    u = upd(tmp_path, site)
    release(site, sha="0" * 64)
    with pytest.raises(UpdateError, match="signed checksum"):
        phone_app.ensure(u, data, "0.5.19")
    assert phone_app.fetched(data) is None and not (phone_app.folder(data) / "kurooto.apk").exists()
    release(site, key=OTHER)
    with pytest.raises(UpdateError, match="trusted key"):
        phone_app.ensure(u, data, "0.5.19")
    release(site, "0.5.18")
    site.files["/releases/0.5.19/manifest.json"] = site.files["/releases/0.5.18/manifest.json"]
    with pytest.raises(UpdateError, match="isn't this version's"):
        phone_app.ensure(u, data, "0.5.19")
    assert phone_app.ensure(u, data, "0.6.0") == "none"  # not on the site (yet)
    assert phone_app.ensure(u, data, "0.0.0+source") == "skipped"


def test_a_changed_file_is_not_served(tmp_path, site):
    release(site)
    data = tmp_path / "data"
    phone_app.ensure(upd(tmp_path, site), data, "0.5.19")
    (phone_app.folder(data) / "kurooto.apk").write_bytes(b"tampered")
    assert phone_app.fetched(data) is None and phone_app.current(data) != phone_app.folder(data) / "kurooto.apk"


@pytest.fixture
def app(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    a = App()
    yield a
    a.close()


def test_after_an_update_the_call_line_gets_the_new_app(app, tmp_path, site, monkeypatch):
    from kurooto.modules.calls import deploy
    from kurooto.update import service

    monkeypatch.setattr(service, "__version__", "0.5.19")
    monkeypatch.setattr(phone_app, "EMBEDDED", tmp_path / "none.apk")
    release(site)
    app.updates.u = upd(tmp_path, site)
    assert app.updates.phone_app() == "skipped"  # Phone calls off: nothing to serve it
    app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), "calls"])
    app.settings.set("updates.mode", "off")
    assert app.updates.phone_app() == "skipped"
    app.settings.set("updates.mode", "night")
    app.settings.set("calls.worker", {"url": "https://line.example", "hash": deploy.fingerprint(app)})
    assert not deploy.needs_redeploy(app)
    assert app.updates.phone_app() == "fetched"
    assert any(e.get("kind") == "phone_app_fetched" for e in app.events.tail(50))
    assert deploy.needs_redeploy(app) and deploy.app_behind(app)
    job = app.scheduler.get("calls:app_line")  # the line takes the new app in a minute, not at 05:10
    assert job and job.action == "calls.app_line" and job.next_run - time.time() < 120
    assert phone_app.current(app.paths.data).read_bytes() == APK
    release(site, "0.5.20", sha="1" * 64)
    monkeypatch.setattr(service, "__version__", "0.5.20")
    assert app.updates.phone_app().startswith("failed")
    assert any(e.get("kind") == "phone_app_failed" for e in app.events.tail(50))


def test_the_call_line_serves_the_downloaded_app(app, tmp_path, site, monkeypatch):
    from kurooto.modules.calls import deploy

    release(site)
    phone_app.ensure(upd(tmp_path, site), app.paths.data, "0.5.19")
    d = deploy.Deployer(app, progress=lambda s: None)
    monkeypatch.setattr(d, "_node", lambda: "node")
    monkeypatch.setattr(d, "_npm_cli", lambda: ["npm"])
    monkeypatch.setattr(deploy, "FILES", ())  # the line's own code isn't what's tested here

    def stop(*a, **k):
        raise RuntimeError("stop after the copy")

    monkeypatch.setattr(deploy.proc, "run", stop)
    (d.dir / "public").mkdir(parents=True)
    (d.dir / "package-lock.json").write_text("{}")
    with pytest.raises(RuntimeError, match="stop after the copy"):
        d.prepare()
    assert (d.dir / "public" / "kurooto.apk").read_bytes() == APK
    assert json.loads((d.dir / "public" / phone_app.TAG).read_text()) == {"versionName": "0.5.19"}  # pair.js shows it
    assert d.apk == hashlib.sha256(APK).hexdigest()  # recorded as calls.worker.apk once deployed


def test_an_older_package_with_the_app_inside_still_works(tmp_path, monkeypatch):
    inside = tmp_path / "kurooto.apk"
    inside.write_bytes(b"embedded")
    monkeypatch.setattr(phone_app, "EMBEDDED", inside)
    assert phone_app.current(tmp_path / "data") == inside
    assert phone_app.fingerprint(tmp_path / "data") == hashlib.sha256(b"embedded").hexdigest()


# ------------------------------------------------------------------- a new app goes to the line soon (0.5.21)
@pytest.fixture
def line(app, tmp_path, site, monkeypatch):
    """Phone calls on with a deployed line that serves an older app, and the new app fetched here."""
    from kurooto.modules.calls import deploy

    monkeypatch.setattr(phone_app, "EMBEDDED", tmp_path / "none.apk")
    release(site)
    phone_app.ensure(upd(tmp_path, site), app.paths.data, "0.5.19")
    app.settings.set("calls.worker", {"url": "https://line.example", "hash": "old", "apk": "0" * 64})
    c = app.modules["calls"]
    c._spawn = lambda fn, name: fn()  # the deploy runs in a thread; here, right away
    ran, said = [], []

    def fake(a, progress=None, unattended=False):
        ran.append(unattended)
        if c.fails:
            return False, "couldn't reach Cloudflare"
        w = a.settings.get("calls.worker")
        a.settings.set("calls.worker", {**w, "apk": phone_app.fingerprint(a.paths.data)})
        return True, "live"

    c.fails = False
    monkeypatch.setattr(deploy, "deploy", fake)
    monkeypatch.setattr(app, "notify", lambda text, **k: said.append(text))
    c.ran, c.said = ran, said
    return c


def booked(app):
    j = app.scheduler.get("calls:app_line")
    return (round((j.next_run - time.time()) / 60), j.payload.get("tries")) if j else None


def line_events(app):
    return [e for e in app.events.tail(50) if e.get("kind") == "calls_line_updated"]


def test_a_new_app_is_taken_to_the_line_then_nothing_more(line):
    app = line.app
    app.updates._app_to_line()
    assert booked(app) == (1, 0)
    assert line._app_line({"tries": 0}).startswith("updating")
    assert line.ran == [True]  # unattended: never a sign-in page
    ev = line_events(app)
    assert len(ev) == 1 and ev[0]["ok"] is True and ev[0]["app"] == "0.5.19" and not line.said
    # the line has it now: nothing booked, nothing deployed
    app.scheduler.cancel("calls:app_line")
    app.updates._app_to_line()
    assert booked(app) is None
    assert "already" in line._app_line({}) and line.ran == [True]


def test_the_same_app_books_nothing(line):
    from kurooto.modules.calls import deploy

    app = line.app
    w = app.settings.get("calls.worker")
    app.settings.set("calls.worker", {**w, "apk": phone_app.fingerprint(app.paths.data)})
    assert not deploy.app_behind(app)
    app.updates._app_to_line()
    assert booked(app) is None and line.ran == []
    app.settings.set("calls.worker", {})  # no line at all: nothing either
    app.updates._app_to_line()
    assert booked(app) is None


def test_never_during_a_call(line):
    import datetime as dt

    app = line.app
    app.availability.set_on_call(dt.datetime.now() + dt.timedelta(seconds=90))
    assert "busy" in line._app_line({"tries": 0})
    assert line.ran == [] and booked(app) == (10, 0)
    app.availability.set_on_call(None)
    line._app_line({"tries": 0})
    assert line.ran == [True]


def test_a_failure_is_retried_and_told_only_the_second_time(line):
    app = line.app
    line.fails = True
    line._app_line({"tries": 0})
    assert booked(app) == (30, 1) and not line.said
    line._app_line({"tries": 1})
    assert booked(app) == (30, 2) and len(line.said) == 1 and "new phone app 0.5.19" in line.said[0]
    ev = line_events(app)
    assert [e["ok"] for e in ev] == [False, False] and ev[-1]["tries"] == 2
    line._app_line({"tries": 2})
    assert len(line.said) == 1  # told once
    line.fails = False
    line._app_line({"tries": 3})
    assert line_events(app)[-1]["ok"] is True
    for t in range(5, 7):  # gives up after a few tries: the 05:10 line update takes it from there
        line.fails = True
        app.scheduler.cancel("calls:app_line")
        w = app.settings.get("calls.worker")
        app.settings.set("calls.worker", {**w, "apk": "0" * 64})
        line._app_line({"tries": t})
    assert booked(app) is None


def test_another_deploy_running_waits(line, monkeypatch):
    from kurooto.modules.calls import deploy

    monkeypatch.setattr(deploy, "deploying", lambda: True)
    assert "busy" in line._app_line({"tries": 1})
    assert line.ran == [] and booked(line.app) == (10, 1)
