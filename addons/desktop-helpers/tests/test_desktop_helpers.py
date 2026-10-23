"""Desktop helpers: the alarm rings the phone through KDE Connect and wakes the screen; chosen kinds of messages
ping it with the kind only; /findphone rings it; nothing but its four programs may start."""

from __future__ import annotations

import time

import pytest

KDE = """#!/bin/sh
echo "$@" >> @LOG@
case "$*" in
  *--id-name-only*) echo "a1b2c3 Pixel Test"; echo "d4e5f6 Tablet Test" ;;
esac
exit 0
"""
HYPR = '#!/bin/sh\necho "$@" >> @LOG@\nexit 0\n'


def wait_for(f, text, s=5.0):
    end = time.time() + s
    while time.time() < end:
        if f.exists() and text in f.read_text():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def app(env, load_addon, fake_programs, monkeypatch):
    d = fake_programs({"kdeconnect-cli": KDE, "hyprctl": HYPR})
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    load_addon("desktop-helpers", env.app)
    env.on("desktop_helpers")
    yield env.app, d
    if env.app.is_on("desktop_helpers"):
        env.app.disable("desktop_helpers")  # its listener is the process's, like any other's


def test_the_alarm_rings_the_phone_and_wakes_the_screen(app):
    a, d = app
    a.events.emit("alarm_rang", page=False)
    assert wait_for(d / "kdeconnect-cli.log", "-d a1b2c3 --ring")
    assert wait_for(d / "hyprctl.log", "dispatch dpms on")


def test_a_named_phone_is_the_one_rung(app, env):
    a, d = app
    a.settings.set("desktop_helpers.phone", "Tablet Test")
    assert env.say("/findphone") == "Ringing your phone."
    assert "-d d4e5f6 --ring" in (d / "kdeconnect-cli.log").read_text()


def test_chosen_kinds_ping_with_the_kind_only(app):
    a, d = app
    a.settings.set("desktop_helpers.ping_kinds", ["deadline"])
    a.notify("Essay draft due in 2 hours", kind="deadline", urgent=True)
    assert wait_for(d / "kdeconnect-cli.log", "--ping-msg Kurooto: deadline")
    assert "Essay" not in (d / "kdeconnect-cli.log").read_text()


def test_turned_off_it_stops_listening(app):
    a, d = app
    a.disable("desktop_helpers")
    a.events.emit("alarm_rang", page=False)
    time.sleep(0.3)
    assert not (d / "kdeconnect-cli.log").exists() or "--ring" not in (d / "kdeconnect-cli.log").read_text()
