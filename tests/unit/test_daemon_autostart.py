import asyncio
import json
import sys
import urllib.request

import pytest

from kurooto.app import App
from kurooto.core import autostart
from kurooto.daemon import serve


def test_daemon_serves_and_stops(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    app.settings.set("web.port", 18790)

    async def main():
        stop = asyncio.Event()
        task = asyncio.create_task(serve(app, stop))
        for _ in range(100):
            await asyncio.sleep(0.05)
            if (app.paths.state / "web.json").exists():
                break
        url = json.loads((app.paths.state / "web.json").read_text())["url"]
        health = await asyncio.to_thread(lambda: json.loads(urllib.request.urlopen(url + "health", timeout=5).read()))
        stop.set()
        await task
        return health

    try:
        assert asyncio.run(main())["ok"] is True
        kinds = [e["kind"] for e in app.events.tail(10)]
        assert "started" in kinds and "stopped" in kinds
    finally:
        app.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux autostart files")
def test_linux_autostart_without_systemd(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart.shutil, "which", lambda name: None)
    assert "desktop autostart" in autostart.enable(home=tmp_path)
    desk = (tmp_path / ".config/autostart/kurooto.desktop").read_text()
    assert "-m kurooto supervise" in desk and autostart.status(home=tmp_path)
    autostart.disable(home=tmp_path)
    assert not autostart.status(home=tmp_path)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS LaunchAgent")
def test_macos_launch_agent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(autostart.proc, "run", lambda args, **kw: calls.append(args))
    autostart.enable(home=tmp_path)
    plist = (tmp_path / "Library/LaunchAgents/io.github.avtarfr.kurooto.plist").read_text()
    assert "<string>supervise</string>" in plist and "RunAtLoad" in plist and calls
    autostart.disable(home=tmp_path)
    assert not autostart.status(home=tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows registry")
def test_windows_run_key(monkeypatch):
    monkeypatch.setattr(autostart, "NAME", "KurootoTest")
    try:
        autostart.enable()
        assert autostart.status()
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.RUN_KEY) as k:
            assert '-m" "kurooto" "supervise' in winreg.QueryValueEx(k, "KurootoTest")[0]
    finally:
        autostart.disable()
    assert not autostart.status()
