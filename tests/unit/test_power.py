"""On battery, paused, and off: what waits for the charger, what keeps working (Telegram), and turning it all off."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time

import pytest

from kurooto import cli
from kurooto.core import shortcuts


@pytest.fixture
def plug(env):
    """A laptop whose charger the test controls."""
    state = {"ac": True}
    env.app.power.on_ac = lambda: state["ac"]
    env.app.power.current = env.app.power.mode()
    return state


def test_modes(env, plug):
    p = env.app.power
    assert p.mode() == "normal"
    plug["ac"] = False
    assert p.mode() == "saver"  # the default on battery
    env.app.settings.set("power.on_battery", "pause")
    assert p.mode() == "paused" and p.why() == "while this laptop is on battery"
    env.app.settings.set("power.on_battery", "normal")
    assert p.mode() == "normal"
    plug["ac"] = True
    assert p.pause(30).startswith("Paused until ")
    assert p.current == "paused"
    assert p.resume() == "Back on." and p.current == "normal"
    p.pause(None)
    assert p.why() == "until you resume me"
    p.resume()


def test_heavy_work_waits_for_the_charger_and_runs_when_plugged_in(env, plug):
    app = env.app
    env.on("reminders")
    ran = []
    app.scheduler.action("research.papers", lambda p: ran.append("research"))
    app.scheduler.action("reminders.fire", lambda p: ran.append("reminder"))
    app.scheduler.at(time.time() - 1, "research.papers", key="research:papers", module="research")
    app.scheduler.at(time.time() - 1, "reminders.fire", key="reminders:x", module="reminders")
    plug["ac"] = False
    assert app.power.apply() == "saver"
    out = dict(asyncio.run(app.scheduler.tick()))
    assert out == {"research:papers": "held", "reminders:x": "ran"} and ran == ["reminder"]
    assert app.scheduler.get("research:papers").next_run > time.time() + 3000  # parked until the charger
    plug["ac"] = True
    assert app.power.apply() == "normal"  # releases it at once
    out = dict(asyncio.run(app.scheduler.tick()))
    assert out == {"research:papers": "ran"} and ran == ["reminder", "research"]


def test_background_ai_work_waits_but_what_you_ask_runs(env, plug):
    jobs = env.app.jobs
    bg = jobs.submit("rank these papers", background=True)
    mine = jobs.submit("what's 2+2")
    plug["ac"] = False
    env.app.power.apply()
    assert jobs._claim() == mine
    assert jobs._claim() is None  # the background one waits
    plug["ac"] = True
    env.app.power.apply()
    assert jobs._claim() == bg


def test_paused_telegram_keeps_what_you_send_and_does_it_on_resume(env, plug):
    env.on("reminders")
    env.app.power.pause(None)
    out = env.say("remind me in 10 minutes to stretch")
    assert out.startswith("I'm paused until you resume me; I'll do this when I'm back")
    assert not env.app.scheduler.jobs("reminders:")
    before = len(env.fake.texts())
    env.say("/resume")
    assert "Back on." in env.fake.texts()[before:]  # the replay may answer first: it runs in its own thread
    for _ in range(100):  # the replay runs in its own thread
        if env.app.scheduler.jobs("reminders:") and any("remind you" in t for t in env.fake.texts()):
            break
        time.sleep(0.05)
    assert env.app.scheduler.jobs("reminders:")
    assert any("remind you" in t for t in env.fake.texts())


def test_pause_command_reads_times(env, plug):
    assert env.say("/pause 2h").startswith("Paused until ")
    assert env.say("/pause until 18:00").startswith("Paused until ")
    assert env.say("/pause forever and ever").startswith("How long?")
    env.app.power.resume()


def test_off_tells_the_call_line_stops_and_disables_autostart(env, monkeypatch):
    from kurooto.core import autostart

    calls = []
    monkeypatch.setattr(autostart, "disable", lambda: calls.append("autostart off") or "off")
    stopped = threading.Event()
    env.app._stop, env.app._loop = stopped, None
    env.app.power.off()
    assert calls == ["autostart off"] and stopped.is_set()
    assert json.loads(env.app.power.off_file.read_text())["keep_calls"] is False


def test_local_models_rest_without_a_server_is_harmless(env):
    env.app.modules["local_models"].rest()  # no Ollama here: nothing to unload, nothing to stop


def test_cli_off_when_not_running(env, monkeypatch, capsys):
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    assert cli.turn_off(keep_calls=False) == 0
    out = capsys.readouterr().out
    assert "Kurooto is off" in out and "kurooto on" in out
    assert (env.app.paths.state / "off.json").exists()


@pytest.mark.skipif(sys.platform != "linux", reason="the Linux app-menu entry")
def test_app_menu_entry_turns_it_on(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    path = shortcuts.create(home=tmp_path)
    text = path.read_text()
    exec_line = next(ln for ln in text.splitlines() if ln.startswith("Exec="))
    assert path.name == "kurooto.desktop" and "Name=Kurooto" in text and exec_line.endswith(" on")
    shortcuts.remove(home=tmp_path)
    assert not path.exists()


def test_power_through_the_api(env, plug):
    from kurooto.web.api import Api

    api = Api(env.app)
    st = api.get("state")[1]["power"]
    assert st["mode"] == "normal" and st["on_battery"] == "saver"
    r = api.post("power/pause", {"when": "2h"})[1]
    assert r["ok"] and r["power"]["mode"] == "paused"
    assert api.post("power/pause", {"when": "whenever"})[1]["ok"] is False
    r = api.post("power/resume", {})[1]
    assert r["message"] == "Back on." and r["power"]["mode"] == "normal"
