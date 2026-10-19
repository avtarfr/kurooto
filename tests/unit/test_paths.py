from pathlib import Path

from kurooto.core.paths import paths

HOME = Path("/h")


def test_kurooto_home_puts_everything_under_one_folder(tmp_path):
    p = paths(env={"KUROOTO_HOME": str(tmp_path)}, home=HOME)
    for f in (p.config, p.data, p.state, p.logs, p.cache, p.app):
        assert tmp_path in f.parents


def test_windows_uses_localappdata():
    local = Path("C:/Users/you/AppData/Local")
    p = paths("win32", {"LOCALAPPDATA": str(local)}, HOME)
    assert p.config == local / "Kurooto" / "config"
    assert p.app == local / "Programs" / "Kurooto"


def test_macos_uses_library():
    p = paths("darwin", {}, HOME)
    assert p.config == HOME / "Library" / "Application Support" / "Kurooto" / "config"
    assert p.logs == HOME / "Library" / "Logs" / "Kurooto"


def test_linux_follows_xdg():
    p = paths("linux", {"XDG_CONFIG_HOME": "/x/cfg", "XDG_STATE_HOME": "relative/ignored"}, HOME)
    assert p.config == Path("/x/cfg/kurooto")
    assert p.state == HOME / ".local" / "state" / "kurooto"
    assert p.data == HOME / ".local" / "share" / "kurooto" / "data"


def test_ensure_creates_folders(tmp_path):
    p = paths(env={"KUROOTO_HOME": str(tmp_path / "k")}, home=HOME).ensure()
    assert p.logs.is_dir() and p.cache.is_dir()
