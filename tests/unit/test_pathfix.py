"""The kurooto command's folder ends up on the PATH of new terminals, changing only what's missing."""

import sys
import types

import kurooto.core.pathfix as pf

REAL_ALLOWED = pf.allowed  # the suite's autouse fixture replaces it; this is the original


def test_fish_gets_its_own_file_once(tmp_path, monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda name: None)
    (tmp_path / ".config" / "fish").mkdir(parents=True)
    (tmp_path / ".bashrc").write_text("alias ll='ls -l'\n")
    bin_dir = tmp_path / ".local" / "bin"
    done = pf.ensure_on_path(bin_dir, home=tmp_path, platform="linux")
    fish = tmp_path / ".config" / "fish" / "conf.d" / "kurooto.fish"
    assert str(fish) in done and '"$HOME/.local/bin"' in fish.read_text()
    assert pf.MARK in (tmp_path / ".bashrc").read_text() and "alias ll" in (tmp_path / ".bashrc").read_text()
    assert pf.ensure_on_path(bin_dir, home=tmp_path, platform="linux") == []  # nothing twice


def test_a_path_the_person_set_up_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda name: None)
    (tmp_path / ".zshrc").write_text('export PATH="$HOME/.local/bin:$PATH"\n')
    assert pf.ensure_on_path(tmp_path / ".local" / "bin", home=tmp_path, platform="linux") == []


def test_no_startup_file_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda name: None)
    b = tmp_path / ".local" / "bin"
    assert pf.ensure_on_path(b, home=tmp_path, platform="linux") == [str(tmp_path / ".profile")]
    mac = tmp_path / "mac"
    mac.mkdir()
    assert pf.ensure_on_path(mac / ".local" / "bin", home=mac, platform="darwin") == [str(mac / ".zshrc")]
    assert 'export PATH="$HOME/.local/bin:$PATH"' in (mac / ".zshrc").read_text()


def test_windows_user_path(monkeypatch):
    store = {"Path": ("C:\\Tools;%USERPROFILE%\\bin", 2)}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake = types.SimpleNamespace(
        HKEY_CURRENT_USER=0,
        KEY_READ=1,
        KEY_SET_VALUE=2,
        REG_EXPAND_SZ=2,
        OpenKey=lambda *a: Key(),
        QueryValueEx=lambda k, name: store[name],
        SetValueEx=lambda k, name, _r, kind, val: store.__setitem__(name, (val, kind)),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    b = pf.Path("D:\\tools\\kurooto-bin")
    assert pf.ensure_on_path(b, platform="win32") == ["your user PATH"]
    assert store["Path"][0].endswith(";" + str(b))
    assert pf.ensure_on_path(b, platform="win32") == []  # already there


def test_tests_and_portable_copies_leave_the_computer_alone(monkeypatch):
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    assert REAL_ALLOWED() is False
    monkeypatch.delenv("KUROOTO_NO_AUTOSTART")
    monkeypatch.setenv("KUROOTO_HOME", "/tmp/x")
    assert REAL_ALLOWED() is False
    monkeypatch.delenv("KUROOTO_HOME")
    assert REAL_ALLOWED() is True
