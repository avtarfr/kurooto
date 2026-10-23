"""Fixtures for the add-ons in this folder. Each runs inside Kurooto (this checkout) with a pretend home, the way a
user gets it: cloned at one commit, its card agreed to, loaded by core/overlay.py and held to its card.

    uv run pytest addons/            every add-on's own tests (tests/unit/test_addon_packages.py checks the cards)

A published add-on's tests run the same way: put the add-on in addons/<name>/ of a Kurooto checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # the checkout, for its tests' fixtures

from tests.conftest import *  # noqa: E402,F403 (the pretend home, the stand-in programs, the env fixture)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def load_addon(tmp_path, monkeypatch):
    """load_addon(name, app) -> app: the add-on in addons/<name>, added by link as a user would add it."""
    import kurooto
    from kurooto.core import addons, fence, overlay

    if addons._version(kurooto.__version__) < (0, 5, 22):  # a checkout between releases still says the last one
        monkeypatch.setattr(kurooto, "__version__", "0.6.0")

    def load(name: str, app):
        repo = tmp_path / "repos" / name
        shutil.copytree(HERE / name, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        git(repo, "init", "-q", "-b", "main")
        git(repo, "add", "-A")
        git(repo, "-c", "user.name=Test", "-c", "user.email=t@example.org", "commit", "-q", "-m", "add-on")
        out = addons.fetch(app.paths, str(repo))
        ok, said = addons.install(app.paths, out["token"], True)
        assert ok, said
        st = overlay.reload_linked(app)
        assert not st["linked"][out["card"]["name"]]["problem"], st["linked"]
        return app

    yield load
    fence.clear()


@pytest.fixture
def fake_programs(tmp_path, monkeypatch):
    """fake_programs({"restic": "#!/bin/sh ..."}) -> the folder: stand-ins first on PATH, each logging its arguments
    to <name>.log beside it."""

    def make(progs: dict[str, str]) -> Path:
        d = tmp_path / "fakebin"
        d.mkdir(exist_ok=True)
        for name, body in progs.items():
            f = d / name
            f.write_text(body.replace("@LOG@", str(d / f"{name}.log")), encoding="utf-8")
            f.chmod(0o755)
        monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
        return d

    return make
