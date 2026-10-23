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


# ---------------------------------------------------------------------------- updating from 0.1 (core/upgrade.py)
def test_a_new_install_keeps_the_new_defaults(tmp_path, monkeypatch):
    from kurooto.app import App
    from kurooto.core import upgrade

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()  # its first start comes before the setup page is ever used
    try:
        assert upgrade.run(app) == "fresh"
        assert app.settings.get("deadlines.call") is True and app.settings.get("calls.realert_min") == [3, 6]
        app.settings.set("setup.done", True)
        assert upgrade.run(app) == ""  # once: setting it up later changes nothing
        assert app.settings.get("alarm.open_page") is True and app.scheduler.get("upgrade:whats_new") is None
    finally:
        app.close()


def test_an_install_from_0_1_keeps_its_behaviour(env):
    import datetime as dt

    from kurooto.core import upgrade
    from kurooto.core.clock import now

    app = env.app
    app.settings.set("setup.done", True)
    app.settings.set("modules.enabled", ["telegram", "deadlines"])
    app.settings.set("retro.journal", True)  # set by you: kept
    dl = app.modules["deadlines"]
    dl.add("Old lab sheet", now() - dt.timedelta(hours=5))
    dl.add("Essay", now() + dt.timedelta(days=3))
    assert upgrade.run(app) == "upgraded"
    s = app.settings
    assert s.get("alarm.open_page") is False and s.get("alarm.prep_min") is None
    assert s.get("capture.study_log") is False and s.get("retro.transcripts") is False
    assert s.get("retro.journal") is True
    assert s.get("deadlines.call") is False and s.get("deadlines.from_calendar") is False
    assert s.get("calls.realert_min") == [3]
    assert s.get("quiz.exam_daily") == "" and s.get("quiz.offer_at") == "19:00"  # for everyone
    env.on("deadlines")
    dl._tick()
    assert not [t for t in env.fake.texts() if "Old lab sheet was due" in (t or "")]  # no flood on the first tick
    assert [it for it in dl.items().values() if it["title"] == "Essay"][0]["told"] == []
    assert upgrade.run(app) == ""
    job = app.scheduler.get("upgrade:whats_new")
    assert job is not None and job.label == "what's new"
    upgrade.whats_new(app)
    text = env.fake.texts()[-1]
    assert text.startswith("Kurooto 0.2.0: what's new") and upgrade.MANUAL in text
    assert 5 <= len(text.splitlines()) <= 9 and "off until you turn them on in Settings" in text


@pytest.mark.skipif(not __import__("shutil").which("git"), reason="needs git")
def test_projects_quiet_at_the_update_are_not_asked_about(env, tmp_path):
    import subprocess
    import time

    app = env.app
    app.settings.set("research.topics", ["x"])
    env.on("research")
    repo = tmp_path / "solver"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f.txt").write_text("x", encoding="utf-8")
    when = time.strftime("%Y-%m-%dT12:00:00", time.localtime(time.time() - 6 * 86400))
    for args in (["add", "-A"], ["commit", "-qm", "first"]):
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            check=True,
            env={**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when},
        )
    env.say(f"/repos add {repo}")
    r = app.modules["research"]
    r.quiet_idle_once()
    assert r.idle_check() == [] and not [q for q in app.ask.pending() if q["source"] == "research"]
    assert r.idle_check() == []  # and it stays noted for this quiet stretch


def test_an_install_that_had_attendance_on_starts_and_lists_its_features(env):
    """Attendance is gone in 0.5.8: an install that had it on, with its settings and a job, starts; it's taken out of
    the features you have on with its settings and jobs, and Features and Settings list as before."""
    import time

    from kurooto.core import upgrade
    from kurooto.web.api import Api

    app = env.app
    env.on("subjects")
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "attendance"])
    app.settings.set("attendance.since", "2026-08-03")
    app.settings.set("attendance.rules", {"la": 80})
    app.settings.set("classpacks.min_pct", 80)  # only Attendance read it
    app.scheduler.at(time.time() - 60, "attendance.weekly", key="attendance:weekly", module="attendance")
    assert [m.id for m in app.enabled()] == ["telegram", "subjects"]  # before the start too: never a missing feature
    app.start()
    assert app.settings.get("modules.enabled") == ["telegram", "subjects"]
    assert "attendance" not in app.settings.user() and app.settings.get("classpacks.min_pct") is None
    assert app.scheduler.get("attendance:weekly") is None
    assert upgrade.drop_retired(app) == []  # once
    api = Api(app)
    mods = {m["id"]: m for m in api.get("state")[1]["modules"]}
    assert "attendance" not in mods and mods["subjects"]["on"]
    sections = [s["section"] for s in api.get("settings")[1]["sections"]]
    assert "subjects" in sections and "attendance" not in sections and "classpacks" not in sections
    assert api.post("settings", {"key": "attendance.min_pct", "value": 75})[0] == 400
    assert env.say("/skip").startswith("Which subject?")


def test_24_hour_times_are_taken_as_written(env):
    env.on("checkins")
    assert env.say("/checkin midday 04:29") == "Midday check-in at 04:29."
    assert env.say("/checkin midday 4:29am") == "Midday check-in at 04:29."


def test_starter_leaves_the_notes_brain_to_you(env, monkeypatch):
    from kurooto.modules.gbrain import GBrain
    from kurooto.web.api import Api

    monkeypatch.setattr(GBrain, "exe", lambda self: None)  # not installed here

    mods = {m["id"]: m for m in Api(env.app)._modules()}
    assert not mods["gbrain"]["starter"] and mods["deadlines"]["starter"]
    assert "0.5 GB" in mods["gbrain"]["why"]  # shown on its card


def test_status_says_what_is_coming_in_words(env):
    import time

    env.on("reminders")
    env.app.scheduler.at(time.time() + 3600, "checkins.fire", {"name": "evening", "day": "x"}, key="checkins:evening")
    env.app.scheduler.at(time.time() + 7200, "calendar.focus_end", key="calendar:focus:2026-10-22T17:00:00+01:00")
    text = env.say("/status")
    assert "evening check-in" in text and "focus ends" in text and "calendar:focus" not in text


def test_kurooto_start_says_where(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    urls = iter([None, "http://127.0.0.1:8770/"])
    monkeypatch.setattr(cli, "wait_for_web", lambda seconds=40: next(urls))
    monkeypatch.setattr(cli, "start_background", lambda: 0)
    assert cli.main(["start"]) == 0
    assert "Kurooto is running: http://127.0.0.1:8770/" in capsys.readouterr().out


def test_kurooto_on_does_not_wait_for_a_service_that_is_not_there(tmp_path, monkeypatch):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    monkeypatch.setenv("KUROOTO_NO_BROWSER", "1")
    waits = []
    monkeypatch.setattr(cli, "wait_for_web", lambda seconds=40: waits.append(seconds) or "http://127.0.0.1:1/")
    assert cli.main(["on"]) == 0 and waits == [1]


def test_doctor_warns_when_the_time_zones_differ(env, monkeypatch):
    import datetime as dt

    from kurooto.diagnostics import timezone_check

    assert timezone_check(env.app) is None
    here = dt.datetime.now().astimezone().utcoffset()
    other = "Pacific/Kiritimati" if here != dt.timedelta(hours=14) else "Pacific/Niue"
    env.app.settings.set("you.timezone", other)
    name, ok, why = timezone_check(env.app)
    assert ok is False and other in why and "Set them the same" in why
    env.app.settings.set("you.timezone", "Not/AZone")
    assert timezone_check(env.app)[1] is False
