"""The call line speaking for the computer while it's gone (core/presence.py, worker.js): the real Worker under
`wrangler dev`, the real connector, and fake Telegram, ntfy and Gemini servers. Nothing leaves this machine.

Skipped unless the Worker's packages are installed (`npm ci` in src/kurooto/data/worker) and Node is on PATH.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import urllib.request

import pytest

from kurooto.modules.calls import deploy, line
from tests.fakes.cloud import FakeCloud
from tests.fakes.telegram import FakeTelegram
from tests.integration.test_call_line import WORKER, Line, Loop, free_port, pytestmark, wait  # noqa: F401 (its skip)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("presence-line")
    old_home = os.environ.get("KUROOTO_HOME")
    os.environ["KUROOTO_HOME"] = str(tmp / "kurooto")
    from kurooto.app import App

    cloud, tgfake = FakeCloud(), FakeTelegram()
    app = App()
    app.settings.set("notify.desktop", False)
    app.settings.set("telegram.api_base", tgfake.base)
    tg = app.modules["telegram"]
    link = tg.pair_start(tgfake.token)
    tgfake.message(f"/start {link['code']}")
    tg.pair_poll(wait=0)
    app.enable("telegram")
    app.settings.set("you.timezone", "Europe/Berlin")
    app.settings.set("calls.ntfy_server", cloud.base)
    app.secrets.set("gemini.api_key", "fake-gemini-key")
    app.settings.set("notify.presence.channels", ["telegram", "app"])
    app.settings.set("notify.presence.line_telegram", True)
    app.settings.set("availability.night", {"enabled": False, "from": "23:30", "to": "07:00"})
    over = {"after_min": 0}  # the line speaks at its first cron (the computer's own setting is at least a minute)
    real = app.presence.line_config
    app.presence.line_config = lambda: {**real(), **over}

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    work = tmp / "worker"
    shutil.copytree(WORKER, work, ignore=shutil.ignore_patterns("node_modules", ".wrangler", "wrangler.toml"))
    (work / "node_modules").symlink_to(WORKER / "node_modules", target_is_directory=True)
    values = {
        "name": "kurooto-test",
        "owner_id": "owner",
        "tz": "Europe/Berlin",
        "public_url": url,
        "version": "test",
        "live_model": "gemini-test-live",
        "ntfy_server": cloud.base,
        "notes_repo": "",
    }
    (work / "wrangler.toml").write_text(deploy.render_toml((work / "wrangler.template.toml").read_text(), values))
    sec = deploy.ensure_secrets(app)
    (work / ".dev.vars").write_text("".join(f"{k}='{v}'\n" for k, v in sec.items()))
    env = {**deploy.wrangler_env(tmp / "wcfg", tmp / "wcache"), "CI": "1", "PATH": os.environ["PATH"]}
    cmd = ["node", "node_modules/wrangler/bin/wrangler.js", "dev", "--ip", "127.0.0.1", "--port", str(port)]
    cmd += ["--test-scheduled", "--persist-to", str(tmp / "do"), "--var", f"GEMINI_BASE_URL:{cloud.base}"]
    cmd += ["--var", f"TELEGRAM_API:{tgfake.base}", "--show-interactive-dev-session=false", "--log-level", "warn"]
    proc = subprocess.Popen(
        cmd, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True
    )
    ln = Line(url)
    try:
        wait(lambda: ln.call("GET", "/health")[0] == 200 if proc.poll() is None else True, 90, "wrangler dev")
        assert proc.poll() is None, proc.stdout.read().decode()[-2000:]
        app.settings.set("calls.worker", {"url": url, "name": "kurooto-test"})
        app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "calls"])
        calls = app.modules["calls"]
        w = {"app": app, "calls": calls, "line": ln, "cloud": cloud, "tg": tgfake, "sec": sec, "over": over}
        w["loop"] = Loop(app)
        wait(lambda: calls.connector.connected, 30, "the connector")
        p = calls.pair_start()  # an Android phone, for the app channel
        code, got = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "android", "name": "Test phone"})
        assert code == 200, got
        w["device"] = got["device"]
        yield w
        w["loop"].halt()
    finally:
        os.killpg(proc.pid, 15)
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
        cloud.close()
        tgfake.close()
        app.close()
        if old_home is None:
            os.environ.pop("KUROOTO_HOME", None)
        else:
            os.environ["KUROOTO_HOME"] = old_home


def push(w) -> None:
    """The state push (it carries notify.presence for the line), now."""
    c = w["calls"].connector
    asyncio.run_coroutine_threadsafe(c.push_state(), w["loop"].loop).result(15)


def away(w) -> None:
    w["loop"].halt()
    wait(lambda: w["line"].call("GET", "/status", key=w["device"])[1].get("computer") == "offline", 20, "offline")


def back(w) -> None:
    w["loop"] = Loop(w["app"])
    wait(lambda: w["calls"].connector.connected, 30, "reconnect")


def cron(w) -> None:
    with urllib.request.urlopen(w["line"].base + "/__scheduled?cron=*+*+*+*+*", timeout=30) as r:
        assert r.status == 200


def line_texts(w) -> list[str]:
    """What the call line sent on Telegram (it sends the chat id as text; this computer as a number)."""
    return [p["text"] for m, p in w["tg"].sent if m == "sendMessage" and isinstance(p.get("chat_id"), str)]


def app_texts(w) -> list[dict]:
    out = []
    for m in w["cloud"].ntfy:
        inner = json.loads(line.open_k1(w["sec"]["NTFY_KEY"], m["message"]))
        if "kind-info" in inner.get("tags", []):
            out.append(inner)
    return out


def test_the_line_says_the_computer_is_gone_once(world):
    w = world
    push(w)
    away(w)
    cron(w)
    wait(lambda: line_texts(w), 15, "the line's Telegram message")
    said = line_texts(w)[-1]
    assert said.startswith("Kurooto has been offline since ") and "(asleep, off or without internet)" in said
    assert "your call line still places scheduled calls" in said
    tg = [p for m, p in w["tg"].sent if m == "sendMessage" and isinstance(p.get("chat_id"), str)][-1]
    assert tg["chat_id"] == "7"
    wait(lambda: app_texts(w), 15, "the phone app's message")
    assert app_texts(w)[-1]["message"] == said and app_texts(w)[-1]["title"] == "Kurooto"
    n, a = len(line_texts(w)), len(app_texts(w))
    cron(w)
    time.sleep(1)
    assert len(line_texts(w)) == n and len(app_texts(w)) == a  # once per time away


def test_back_the_computer_hears_what_the_line_said_and_says_its_back(world):
    w, app = world, world["app"]
    sent = len(w["tg"].texts())
    back(w)
    wait(lambda: (json.loads(app.presence.file.read_text()) or {}).get("pending"), 15, "the line's report")
    p = json.loads(app.presence.file.read_text())["pending"]
    assert p["kinds"] == ["line"] and p["told"] is True
    assert [e for e in app.events.tail(50) if e["kind"] == "presence_offline"][-1]["by"] == "line"
    real = app.presence.clock
    app.presence.clock = lambda: real() + 120  # a minute and more later
    try:
        app.presence._maybe_send(app.presence.clock())
    finally:
        app.presence.clock = real
    mine = [t for t in w["tg"].texts()[sent:] if t and t.startswith("Kurooto is back online (offline since")]
    assert len(mine) == 1
    push(w)  # the line hears it's back (it's told on every push anyway)
    # the next time away is a new one: said again
    n = len(line_texts(w))
    away(w)
    cron(w)
    wait(lambda: len(line_texts(w)) > n, 15, "a new message for a new time away")


def test_a_clean_stop_says_it_once_with_the_line_doing_the_phone(world):
    w, app = world, world["app"]
    back(w)
    from kurooto.core.presence import Presence

    app.presence = pres = Presence(app)  # a fresh daemon: it hasn't said goodbye yet
    pres.line_config = lambda: {**Presence.line_config(pres), **w["over"]}
    push(w)
    n, a = len(line_texts(w)), len(app_texts(w))
    mine = len(w["tg"].texts())
    app.stop_reason = "stopped"
    asyncio.run_coroutine_threadsafe(pres.going_offline(), w["loop"].loop).result(10)
    bye = "Kurooto is going offline (stopped): reminders will wait until it's back; your call line still places "
    assert w["tg"].texts()[mine:] == [bye + "scheduled calls."]  # from this computer
    wait(lambda: len(app_texts(w)) > a, 15, "the phone app's goodbye from the line")
    assert app_texts(w)[-1]["message"].startswith("Kurooto is going offline (stopped)")
    stop = json.loads(pres.file.read_text())["stop"]
    assert stop["told"] == ["telegram", "app"]
    away(w)
    cron(w)
    time.sleep(1)
    assert len(line_texts(w)) == n  # it said goodbye itself, so the line doesn't


def test_an_update_restart_and_the_night_say_nothing(world):
    w, app = world, world["app"]
    back(w)
    from kurooto.core.presence import Presence

    app.presence = pres = Presence(app)
    w["over"]["after_min"] = 60  # a restart only counts after a long time away
    pres.line_config = lambda: {**Presence.line_config(pres), **w["over"]}
    push(w)
    n, a = len(line_texts(w)), len(app_texts(w))
    app.restart_requested = True
    try:
        asyncio.run_coroutine_threadsafe(pres.going_offline(), w["loop"].loop).result(10)
    finally:
        app.restart_requested = False
    away(w)
    cron(w)
    time.sleep(1)
    assert len(line_texts(w)) == n and len(app_texts(w)) == a
    # at night (hush) nothing either, even after the time is up
    back(w)
    now = int(time.time() * 1000)
    w["over"].update(after_min=0, hush=[[now - 3600_000, now + 3600_000]])
    push(w)
    away(w)
    cron(w)
    time.sleep(1)
    assert len(line_texts(w)) == n and len(app_texts(w)) == a
    w["over"].pop("hush")


def test_turning_the_token_off_takes_it_off_the_line(world):
    w, app = world, world["app"]
    back(w)
    app.settings.set("notify.presence.line_telegram", False)
    push(w)
    n, a = len(line_texts(w)), len(app_texts(w))
    away(w)
    cron(w)
    wait(lambda: len(app_texts(w)) > a, 15, "the phone app still hears")
    assert len(line_texts(w)) == n  # no token on the line any more, so no Telegram from it
    back(w)
