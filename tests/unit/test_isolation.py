"""Tests stay off the computer they run on (tests/isolation.py, tests/conftest.py), and a home given to autostart or
the app-menu entries is the only home they use."""

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from kurooto.core import autostart, shortcuts
from kurooto.core.paths import paths
from tests import isolation


def forget(path):
    """Drop the violations (and reads) this test caused on purpose: they would fail it."""
    isolation.violations[:] = [v for v in isolation.violations if str(path) not in v["path"]]
    isolation.reads[:] = [r for r in isolation.reads if str(path) not in r["path"]]


def test_every_test_has_a_pretend_home(tmp_path_factory):
    home = Path(os.environ["HOME"])
    assert Path.home() == home and str(home).startswith(str(tmp_path_factory.getbasetemp()))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "APPDATA", "LOCALAPPDATA"):
        assert os.environ[var].startswith(str(home))
    assert str(paths().config).startswith(str(tmp_path_factory.getbasetemp()))
    assert os.environ["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
    assert isolation.PROTECTED and isolation.DAEMON_PORT in isolation.PORTS


def test_writing_or_deleting_in_the_real_install_is_blocked(tmp_path, monkeypatch):
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    keep = real / "settings.json"
    keep.write_text("{}")
    monkeypatch.setattr(isolation, "PROTECTED", (str(real),))
    try:
        for act in (
            lambda: keep.write_text("changed"),
            lambda: (real / "new.json").touch(),
            keep.unlink,
            lambda: os.replace(keep, tmp_path / "moved"),
            lambda: (real / "sub" / "deeper").mkdir(),
        ):
            with pytest.raises(PermissionError):
                act()
        assert keep.read_text() == "{}" and not (real / "new.json").exists()
        assert len([v for v in isolation.violations if str(real) in v["path"]]) >= 5
        assert isolation.reads[-1]["path"] == str(keep)  # reading is only counted
    finally:
        forget(real)


def test_the_running_kurooto_is_out_of_reach():
    with socket.socket() as s, pytest.raises(ConnectionRefusedError):
        s.connect(("127.0.0.1", isolation.DAEMON_PORT))
    forget(f":{isolation.DAEMON_PORT}")
    with socket.socket() as s, pytest.raises(OSError):
        s.bind(("127.0.0.1", isolation.DAEMON_PORT))  # test servers take the next port instead


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX service managers")
def test_real_service_managers_never_run():
    for name in ("loginctl", "systemctl", "launchctl", "kurooto"):
        found = isolation.shutil.which(name)
        if not found:
            continue
        assert Path(found).parent == isolation.BIN  # the refusing stand-in comes first
        assert subprocess.run([name, "--version"], capture_output=True).returncode == 1
        real = isolation.shutil.which(name, path=os.environ["PATH"].split(os.pathsep, 1)[1])
        if real:
            with pytest.raises(PermissionError):
                subprocess.run([real, "--version"], capture_output=True)
            forget(real)


def install(app: Path) -> None:
    app.mkdir(parents=True, exist_ok=True)
    (app / "launcher.py").write_text("")
    (app / "install.json").write_text('{"python": "/opt/py/bin/python3"}')


def test_a_given_home_is_the_only_home(tmp_path, monkeypatch):
    install(paths().app)  # this machine's install (here: the pretend one) is never what a given home runs
    home = tmp_path / "given"
    assert autostart.app_dir(home) == paths(env={}, home=home).app
    assert autostart.command(autostart.app_dir(home))[1:] == ["-m", "kurooto", "supervise"]
    assert autostart.command()[-1] == str(paths().app / "launcher.py")
    install(autostart.app_dir(home))
    assert autostart.command(autostart.app_dir(home))[-1] == str(autostart.app_dir(home) / "launcher.py")
    if sys.platform.startswith("linux"):
        monkeypatch.setattr(autostart.shutil, "which", lambda name: None)
        autostart.enable(home=tmp_path)
        desk = (tmp_path / ".config" / "autostart" / "kurooto.desktop").read_text()
        assert "-m kurooto supervise" in desk
        assert shortcuts.where(home) == home / ".local" / "share" / "applications" / "kurooto.desktop"
        assert str(autostart.app_dir(home)) in shortcuts.create(home).read_text()
