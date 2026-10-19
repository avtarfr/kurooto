"""Bugs found by the 0.1.5 -> 0.2.0 upgrade rehearsal and the fresh-install walkthrough (real installs, sealed)."""

from __future__ import annotations

import json
import os
import socket
import sys

import pytest

from kurooto import __version__


def test_battery_choice_can_be_saved(env):
    """The setup page's Computer step saves power.on_battery through the settings API."""
    from kurooto.web.api import Api

    api = Api(env.app)
    assert api.post("settings", {"key": "power.on_battery", "value": "normal"}) == (200, {"ok": True})
    assert env.app.settings.get("power.on_battery") == "normal"
    assert any(s["section"] == "power" for s in api.get("settings")[1]["sections"])


@pytest.mark.skipif(sys.platform == "win32", reason="SO_REUSEADDR means something else on Windows")
def test_the_dashboard_keeps_its_port_after_a_quick_restart():
    from kurooto.web.server import free_port

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen()
    assert free_port(port) != port  # someone is listening there
    c = socket.create_connection(("127.0.0.1", port))
    a, _ = srv.accept()
    a.close()  # the server side closes first: its socket waits in TIME_WAIT, as after a restart
    srv.close()
    c.close()
    assert free_port(port) == port


def test_rehearsals_leave_start_at_sign_in_alone(env, monkeypatch):
    from kurooto.core import autostart
    from kurooto.web.api import Api

    touched = []
    monkeypatch.setattr(autostart, "enable", lambda *a, **k: touched.append("enable") or "on")
    monkeypatch.setattr(autostart, "disable", lambda *a, **k: touched.append("disable") or "off")
    monkeypatch.setattr(env.app, "request_stop", lambda: None)
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    assert Api(env.app).post("autostart", {"on": True})[1]["ok"] is True
    env.app.power.off(keep_calls=True)
    assert touched == []
    monkeypatch.delenv("KUROOTO_NO_AUTOSTART")
    Api(env.app).post("autostart", {"on": True})
    env.app.power.off(keep_calls=True)
    assert touched == ["enable", "disable"]


def test_a_stale_update_badge_is_cleared(env):
    """`kurooto update --now` installs without the daemon, so its "ready" file stayed and the dashboard kept saying
    "update <this version> ready tonight"."""
    u = env.app.updates
    u.ready_file.write_text(json.dumps({"version": __version__, "staged": True, "notes": ""}))
    u.start()
    assert not u.ready_file.exists()
    u.ready_file.write_text(json.dumps({"version": "999.0.0", "staged": True, "notes": ""}))
    u.start()
    assert u.ready_file.exists()  # a newer one is still to come
    (env.app.paths.app / "bad.json").write_text(json.dumps(["999.0.0"]))
    u.start()
    assert not u.ready_file.exists()  # ...unless it was rolled back: it won't be installed


def test_a_rollback_is_told_once(env):
    u = env.app.updates
    f = env.app.paths.app / "update.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"phase": "rolled_back", "from": "999.0.0", "to": __version__, "since": 1}))
    u.start()
    assert env.app.scheduler.get("updates:rolled_back") is not None
    u.tell_rolled_back()
    u.tell_rolled_back()
    told = [t for t in env.fake.texts() if "didn't start properly" in (t or "")]
    assert len(told) == 1 and "999.0.0" in told[0] and __version__ in told[0]
    assert json.loads(f.read_text())["told"]


def test_kurooto_stop_asks_first(tmp_path, monkeypatch):
    """`kurooto stop` stops it the normal way first (Notes sync's last push runs), then forces what's left."""
    from kurooto import cli
    from kurooto.core import proc

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "daemon.json").write_text(json.dumps({"pid": os.getpid()}))
    asked = []
    monkeypatch.setattr(proc, "pid_alive", lambda pid, marker=None: not asked)
    monkeypatch.setattr(cli, "stop_gracefully", lambda timeout=90: asked.append(timeout) or True)
    monkeypatch.setattr(proc, "kill_tree", lambda pid: pytest.fail("it stopped by itself; nothing to force"))
    assert cli.main(["stop"]) == 0
    assert asked and not (tmp_path / "state" / "daemon.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="file modes are POSIX")
def test_the_databases_are_owner_only(env):
    """jobs.db keeps what you asked the AI (an About-you merge prompt has your whole report); schedule.db your
    reminders. Like the JSON state files, only your account may read them, also after an update from 0.1.x."""
    import stat

    st = env.app.paths.state
    for name in ("jobs.db", "schedule.db"):
        assert stat.S_IMODE((st / name).stat().st_mode) == 0o600, name
    os.chmod(st / "jobs.db", 0o644)  # as 0.1.x left it
    from kurooto.core.jobs import Jobs

    Jobs(env.app)._db.close()
    assert stat.S_IMODE((st / "jobs.db").stat().st_mode) == 0o600


def test_the_overdue_question_is_asked_once_per_message(env):
    import datetime as dt

    from kurooto.core.clock import now

    env.on("deadlines")
    dl = env.app.modules["deadlines"]
    dl.add("Lab sheet", now() - dt.timedelta(hours=2))
    dl._tick()
    t = next(t for t in env.fake.texts() if "Lab sheet was due" in (t or ""))
    assert t.startswith("Overdue?") and t.count("Overdue?") == 1


def test_the_unattended_redeploy_never_opens_a_sign_in_page(env, monkeypatch):
    """The 05:10 redeploy after an update: with Cloudflare's sign-in expired it says so instead of opening a browser
    tab and waiting ten minutes for someone who's asleep."""
    from kurooto.modules.calls import deploy

    env.app.secrets.set("gemini.api_key", "k")
    env.app.settings.set("you.timezone", "UTC")
    monkeypatch.setattr(deploy.Deployer, "prepare", lambda self: None)
    monkeypatch.setattr(deploy.Deployer, "signed_in", lambda self: False)
    monkeypatch.setattr(deploy.Deployer, "sign_in", lambda self, wait_s=600: pytest.fail("opened a sign-in page"))
    ok, msg = deploy.deploy(env.app, progress=lambda line: None, unattended=True)
    assert ok is False and "sign in" in msg
