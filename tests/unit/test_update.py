import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kurooto.update import signing
from kurooto.update.updater import UpdateError, Updater, vtuple
from tests.unit.test_prereqs import Files

KEY = Ed25519PrivateKey.generate()
PUB = signing.public_b64(KEY)
OTHER = Ed25519PrivateKey.generate()


def wrap(doc, key=KEY):
    return json.dumps({"doc": doc, "sig": signing.sign(doc, key)}).encode()


@pytest.fixture
def site():
    f = Files()
    yield f
    f.server.shutdown()


def publish(site, version, issued=None, key=KEY, tamper=False):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        data = b"print('hi')\n"
        info = tarfile.TarInfo(f"kurooto-{version}/x.py")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    tgz = b.getvalue()
    name = f"kurooto-{version}.tar.gz"
    site.files[f"/releases/{version}/{name}"] = tgz + (b"x" if tamper else b"")
    man = {
        "version": version,
        "files": {
            name: {
                "url": f"{site.base}/releases/{version}/{name}",
                "sha256": hashlib.sha256(tgz).hexdigest(),
                "size": len(tgz),
            }
        },
    }
    site.files[f"/releases/{version}/manifest.json"] = wrap(man, key)
    ptr = {
        "version": version,
        "manifest_url": f"{site.base}/releases/{version}/manifest.json",
        "issued": issued or time.time(),
    }
    site.files["/stable.json"] = wrap(ptr, key)


def updater(tmp_path, site, installed="0.1.0"):
    app = tmp_path / "app"
    app.mkdir(exist_ok=True)
    (app / "launcher.py").write_text("")
    (app / "current.json").write_text(json.dumps({"version": installed}))
    return Updater(app, tmp_path / "state", site.base, keys=[PUB])


def test_versions_compare_numerically():
    assert vtuple("0.10.0") > vtuple("0.9.9") and vtuple("1.0") == (1, 0, 0) and vtuple("0.2.0rc1") == (0, 2, 0)


def test_finds_a_signed_newer_release(tmp_path, site):
    publish(site, "0.2.0")
    rel = updater(tmp_path, site).check()
    assert rel.version == "0.2.0" and "kurooto-0.2.0.tar.gz" in rel.files


def test_refuses_unsigned_older_stale_and_bad(tmp_path, site):
    u = updater(tmp_path, site)
    publish(site, "0.2.0", key=OTHER)
    with pytest.raises(UpdateError, match="trusted key"):
        u.check()
    publish(site, "0.0.9")
    assert u.check() is None  # never a downgrade
    publish(site, "0.3.0", issued=time.time())
    assert u.check().version == "0.3.0"
    publish(site, "0.3.1", issued=time.time() - 86400)
    with pytest.raises(UpdateError, match="older than one already seen"):
        u.check()  # an old pointer replayed
    (u.app / "bad.json").write_text(json.dumps(["0.4.0"]))
    publish(site, "0.4.0", issued=time.time() + 5)
    assert u.check() is None


def test_tampered_download_is_refused(tmp_path, site):
    publish(site, "0.2.0", tamper=True)
    u = updater(tmp_path, site)
    rel = u.check()
    with pytest.raises(UpdateError, match="checksum"):
        u.stage(rel, "uv", sys.executable, progress=lambda s: None)
    assert not (u.app / "versions" / "0.2.0").exists() and not (u.app / "versions" / "0.2.0.partial").exists()


def test_switch_probation_and_prune(tmp_path, site):
    u = updater(tmp_path, site)
    for v in ("0.1.0", "0.2.0", "0.3.0", "0.4.0"):
        (u.app / "versions" / v).mkdir(parents=True)
    u.switch("0.4.0")
    assert json.loads((u.app / "previous.json").read_text()) == {"version": "0.1.0"}
    assert json.loads((u.app / "update.json").read_text())["phase"] == "trial"
    assert u.probation_passed("0.4.0") is False  # not five minutes yet
    upd = json.loads((u.app / "update.json").read_text())
    upd["since"] -= 400
    (u.app / "update.json").write_text(json.dumps(upd))
    assert u.probation_passed("0.4.0") is True
    u.prune(keep=2)
    assert sorted(p.name for p in (u.app / "versions").iterdir()) == ["0.1.0", "0.3.0", "0.4.0"]


def make_version(app: Path, version: str, crash: bool):
    """A fake installed version whose `python -m kurooto run` exits 0, or crashes."""
    vdir = app / "versions" / version / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    vdir.mkdir(parents=True)
    pkg = app / "versions" / version / "pkg" / "kurooto"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text(
        f"import sys\nopen(r'{app / 'ran.txt'}', 'a').write('{version}\\n')\nsys.exit({1 if crash else 0})\n"
    )
    exe = vdir / ("python.exe" if os.name == "nt" else "python")
    if os.name == "nt":
        (vdir / "python.cmd").write_text("")
        import shutil

        shutil.copy(sys.executable, exe)
    else:
        exe.write_text(f"#!/bin/sh\nPYTHONPATH='{pkg.parent}' exec '{sys.executable}' \"$@\"\n")
        exe.chmod(0o755)


@pytest.mark.skipif(os.name == "nt", reason="the fake python is a shell script; Windows runs the real rehearsal in CI")
def test_launcher_rolls_back_a_crash_loop(tmp_path):
    from importlib import resources

    app = tmp_path / "app"
    app.mkdir()
    (app / "launcher.py").write_bytes(resources.files("kurooto.update").joinpath("launcher.py").read_bytes())
    make_version(app, "0.2.0", crash=False)
    make_version(app, "0.3.0", crash=True)
    (app / "current.json").write_text(json.dumps({"version": "0.3.0"}))
    (app / "previous.json").write_text(json.dumps({"version": "0.2.0"}))
    (app / "update.json").write_text(json.dumps({"phase": "trial", "to": "0.3.0", "since": time.time()}))
    src = (app / "launcher.py").read_text().replace("time.sleep(backoff)", "time.sleep(0)")
    (app / "launcher.py").write_text(src)
    r = subprocess.run([sys.executable, str(app / "launcher.py")], timeout=60)
    assert r.returncode == 0
    assert (app / "ran.txt").read_text().split() == ["0.3.0", "0.3.0", "0.3.0", "0.2.0"]
    assert json.loads((app / "current.json").read_text()) == {"version": "0.2.0"}
    assert json.loads((app / "bad.json").read_text()) == ["0.3.0"]
    assert json.loads((app / "update.json").read_text())["phase"] == "rolled_back"
