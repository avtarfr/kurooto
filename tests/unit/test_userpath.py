"""A service started at boot has a short PATH; tools in ~/.local/bin and friends were "not found" (restic, rclone, an AI
program) until the desktop session handed its PATH over."""

import os
import sys

import pytest

from kurooto.core import proc


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX folders")
def test_user_bin_is_added_when_missing_and_nothing_is_shadowed(tmp_path, monkeypatch):
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    (tmp_path / ".cargo" / "bin").mkdir(parents=True)
    exe = tmp_path / ".local" / "bin" / "mytool"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert proc.which("mytool") is None  # the boot-time PATH can't see it
    added = proc.ensure_user_path(tmp_path)
    assert str(tmp_path / ".local" / "bin") in added and os.environ["PATH"].startswith("/usr/bin:/bin")
    assert proc.which("mytool") == str(exe)
    assert proc.ensure_user_path(tmp_path) == []  # again: nothing more to add


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX folders")
def test_folders_that_do_not_exist_are_not_added(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    assert not [d for d in proc.ensure_user_path(tmp_path) if str(tmp_path) in d]
