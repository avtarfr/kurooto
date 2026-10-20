"""Quick win 1: staged updates and the signed yank list. A release waits 48 h (updates.staged) unless it's signed
critical, nothing installs during exams, and a yanked version is never installed: not on a check, not when it was
already downloaded, and not when the site later can't be read. The yank list comes from tools/release.py yank."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import threading
import time
import types
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from kurooto.core.state import jload, jsave
from kurooto.update.updater import UpdateError
from tests.unit.test_update import KEY, OTHER, PUB, publish, updater, wrap
from tests.unit.test_update import site as site  # noqa: F401 (the fixture)

ROOT = Path(__file__).resolve().parents[2]


def yank_doc(site, versions: dict, issued: float | None = None, key=KEY):
    site.files["/yank.json"] = wrap({"yanked": versions, "issued": issued or time.time()}, key)


def critical(site, version):
    """Re-sign the channel pointer with critical: true."""
    ptr = json.loads(site.files["/stable.json"])["doc"]
    site.files["/stable.json"] = wrap({**ptr, "critical": True, "issued": ptr["issued"] + 1})


# ------------------------------------------------------------------------------------------ the updater
def test_a_yanked_version_is_refused_and_the_list_is_kept(tmp_path, site):
    u = updater(tmp_path, site)
    publish(site, "0.2.0")
    assert u.check().version == "0.2.0" and u.yanked() == {}  # no yank list on the site: nothing withdrawn
    yank_doc(site, {"0.2.0": "loses reminders"})
    assert u.check() is None and u.withdrawn == {"0.2.0": "loses reminders"}
    del site.files["/yank.json"]  # gone from the site (or the site is unreachable): the last list seen stands
    assert u.check() is None and u.yanked(fetch=False) == {"0.2.0": "loses reminders"}
    publish(site, "0.2.1", issued=time.time() + 5)
    assert u.check().version == "0.2.1" and u.withdrawn == {}  # a fixed version goes through


def test_a_yank_list_must_be_signed_and_new(tmp_path, site):
    u = updater(tmp_path, site)
    publish(site, "0.2.0")
    yank_doc(site, {}, key=OTHER)
    with pytest.raises(UpdateError, match="yank list wasn't signed"):
        u.check()
    site.files["/yank.json"] = b"not json"
    with pytest.raises(UpdateError, match="unreadable yank list"):
        u.check()
    yank_doc(site, {"0.1.9": "x"}, issued=time.time())
    u.check()
    yank_doc(site, {}, issued=time.time() - 86400)  # an older list replayed (it would un-yank)
    with pytest.raises(UpdateError, match="older than one already seen"):
        u.check()


def test_a_critical_release_is_marked(tmp_path, site):
    publish(site, "0.2.0")
    assert updater(tmp_path, site).check().critical is False
    critical(site, "0.2.0")
    assert updater(tmp_path, site).check().critical is True


# ------------------------------------------------------------------------------------- the release tool
def release_tool():
    spec = importlib.util.spec_from_file_location("kurooto_release", ROOT / "tools" / "release.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_tool_yanks_and_signs_critical(tmp_path, site, monkeypatch, capsys):
    pem = tmp_path / "key.pem"
    pem.write_bytes(
        KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    monkeypatch.setenv("KUROOTO_EXTRA_UPDATE_KEY", PUB)
    rel = release_tool()
    out = tmp_path / "site"
    (out / "stable.json").parent.mkdir(parents=True)
    (out / "stable.json").write_text(json.dumps({"doc": {"version": "0.2.1"}}))
    rel.yank(out, pem, ["0.2.1"], "loses reminders")
    assert "stable.json still names 0.2.1" in capsys.readouterr().out
    site.files["/yank.json"] = (out / "yank.json").read_bytes()
    u = updater(tmp_path, site)
    publish(site, "0.2.1")
    assert u.check() is None and u.withdrawn == {"0.2.1": "loses reminders"}
    rel.yank(out, pem, ["0.2.1"], undo=True)
    site.files["/yank.json"] = (out / "yank.json").read_bytes()
    assert u.check().version == "0.2.1"  # taken off again: a newer signed list wins
    # sign --critical puts a signed critical flag on the pointer
    (out / "releases" / "0.2.2").mkdir(parents=True)
    (out / "releases" / "0.2.2" / "manifest.unsigned.json").write_text(json.dumps({"version": "0.2.2", "files": {}}))
    rel.sign(out, site.base, "0.2.2", pem, "stable", critical=True)
    ptr = json.loads((out / "stable.json").read_text())
    assert ptr["doc"]["critical"] is True and "critical" in capsys.readouterr().out
    rel.sign(out, site.base, "0.2.2", pem, "beta")
    assert "critical" not in json.loads((out / "beta.json").read_text())["doc"]


# ------------------------------------------------------------------------------------------- the service
class Now:
    """threading.Thread that runs its target at once (the service prepares updates in a thread)."""

    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def svc(env, site, tmp_path, monkeypatch):
    """The running app's updater pointed at a fake site, installed by the installer (so it may update)."""
    from kurooto.update import service

    monkeypatch.setattr(service, "threading", types.SimpleNamespace(Thread=Now, Lock=threading.Lock))
    u = env.app.updates
    (tmp_path / "updates").mkdir()
    u.u = updater(tmp_path / "updates", site)
    u.u.state = env.app.paths.state
    u.clock = time.time
    staged: list[str] = []

    def stage(rel):  # no download or venv in tests
        staged.append(rel.version)
        ready = {"version": rel.version, "staged": True, "notes": "", "issued": rel.issued, "critical": rel.critical}
        jsave(u.ready_file, ready)

    u._stage = u._stage_then_wait = stage
    switched: list[str] = []
    u.switch_to = lambda v: switched.append(v) or f"switching to {v}"
    env.app.settings.set("availability.night.enabled", False)
    return env, u, staged, switched


def test_staged_off_installs_as_before(svc, site):
    env, u, staged, _ = svc
    publish(site, "99.0.0")
    assert u.check() == "preparing 99.0.0"
    assert staged == ["99.0.0"]


def test_staged_waits_48_hours_unless_critical(svc, site):
    env, u, staged, switched = svc
    env.app.settings.set("updates.staged", True)
    t0 = time.time()
    publish(site, "99.0.0", issued=t0)
    u.clock = lambda: t0 + 3600
    out = u.check()
    assert out.startswith("99.0.0 waits: it has been out less than 48 h") and staged == []
    assert jload(u.ready_file, {})["waiting"].startswith("it has been out")
    u.clock = lambda: t0 + 49 * 3600
    assert u.check() == "preparing 99.0.0" and staged == ["99.0.0"]
    assert u.apply_if_quiet() == "switching to 99.0.0" and switched == ["99.0.0"]
    # a critical one goes at once
    staged.clear()
    publish(site, "99.1.0", issued=t0 + 10)
    critical(site, "99.1.0")
    u.clock = lambda: t0 + 20
    assert u.check() == "preparing 99.1.0"


def test_nothing_installs_during_exams(svc, site):
    env, u, staged, switched = svc
    env.app.settings.set("updates.staged", True)
    publish(site, "99.0.0", issued=time.time() - 72 * 3600)
    env.on("subjects")
    today = dt.date.today()
    env.app.settings.set(
        "subjects.exam_periods", [[(today - dt.timedelta(days=1)).isoformat(), (today + dt.timedelta(1)).isoformat()]]
    )
    assert u.check() == "99.0.0 waits: you're in an exam period" and staged == []
    # downloaded before the exams started: the night's switch waits a day instead
    jsave(u.ready_file, {"version": "99.0.0", "staged": True, "issued": time.time() - 72 * 3600})
    assert u.apply_if_quiet() == "99.0.0 waits: you're in an exam period" and switched == []
    assert env.app.scheduler.get("updates:apply") is not None
    env.app.settings.set("updates.exam_hold", False)
    assert u.apply_if_quiet() == "switching to 99.0.0"
    # a quiz tomorrow morning (Deadlines) holds it too
    env.app.settings.set("updates.exam_hold", True)
    env.app.settings.set("subjects.exam_periods", [])
    env.on("deadlines")
    env.app.modules["deadlines"].add("Linear algebra quiz", dt.datetime.now() + dt.timedelta(hours=10), kind="exam")
    assert u.check() == "99.0.0 waits: Linear algebra quiz is within a day"
    critical(site, "99.0.0")
    assert u.check() == "preparing 99.0.0"  # a critical fix isn't held, even for exams


def test_a_version_yanked_after_download_is_not_switched_to(svc, site):
    env, u, staged, switched = svc
    publish(site, "99.0.0")
    assert u.check() == "preparing 99.0.0"
    yank_doc(site, {"99.0.0": "breaks calls"})
    assert u.apply_if_quiet() == "99.0.0 was withdrawn (breaks calls); not installing it"
    assert switched == [] and not u.ready_file.exists()
    assert u.check() == "99.0.0 was withdrawn (breaks calls); not installing it"
    assert u.button("99.0.0", "now").startswith("99.0.0 was withdrawn")
    # Kurooto restarting with it still marked ready (from an older version) forgets it
    jsave(u.ready_file, {"version": "99.0.0", "staged": True})
    u.start()
    assert not u.ready_file.exists()
    # a yank list that isn't signed stops the switch for a day
    jsave(u.ready_file, {"version": "99.0.1", "staged": True})
    yank_doc(site, {}, key=OTHER)
    assert u.apply_if_quiet().startswith("not switching: the yank list wasn't signed") and switched == []
