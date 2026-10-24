"""The add-ons in addons/ (each to be published as its own repository): every manifest reads, every card is clean,
and each one loads by link with exactly what its card says (the add-ons' own tests: uv run pytest addons/)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import kurooto
from kurooto.app import App
from kurooto.core import addons, fence, overlay

ROOT = Path(__file__).resolve().parents[2] / "addons"
NAMES = sorted(p.parent.name for p in ROOT.glob(f"*/{addons.MANIFEST}"))
# in addons/ but not in the official list yet: published and pinned after review (then taken out of here)
UNLISTED: set[str] = set()


def test_there_are_the_five_generic_add_ons():
    assert NAMES == ["desktop-helpers", "habits", "handwriting-pull", "night-performance", "restic-backups"]


def test_the_official_list_matches_the_folders():
    """data/official_addons.json (core/official.py) names each folder here, with its manifest's title and version as
    the tag, a public repository on github.com and one pinned commit."""
    from kurooto.core import official

    listed = official.catalog()
    assert sorted(e["name"] for e in listed) == sorted(set(NAMES) - UNLISTED)
    assert UNLISTED <= set(NAMES)  # a name here that's no folder: take it out
    for e in listed:
        man = addons.read_manifest(ROOT / e["name"])
        assert e["source"] == f"addons/{e['name']}", e["name"]
        assert e["title"] == man["title"], e["name"]
        assert e["tag"] == f"v{man['version']}", (e["name"], "a new version: publish it and update the list")
        assert e["url"].startswith("https://github.com/") and addons.check_url(e["url"]) == e["url"]
        assert addons.SHA.fullmatch(e["commit"]) and e["commit"] not in e["earlier"]
        assert e["line"] and e["needs"]
        assert official.find(e["name"])["commit"] == e["commit"]


@pytest.mark.parametrize("name", NAMES)
def test_each_loads_by_link_with_exactly_its_card(name, tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    if addons._version(kurooto.__version__) < (0, 5, 22):  # a checkout between releases still says the last one
        monkeypatch.setattr(kurooto, "__version__", "0.6.0")
    src = ROOT / name
    man = addons.read_manifest(src)
    assert man["name"] == name and man["description"] and man["version"] and man["kurooto"] == ">=0.6.0"
    assert (src / "README.md").is_file() and list((src / "tests").glob("test_*.py"))
    repo = tmp_path / name
    shutil.copytree(src, repo, ignore=shutil.ignore_patterns("__pycache__"))
    for args in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["-c", "user.name=T", "-c", "user.email=t@example.org", "commit", "-q", "-m", "x"]):  # fmt: skip
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    app = App()
    out = addons.fetch(app.paths, str(repo))
    assert out["card"]["warnings"] == [] and "Runs code: YES" in out["text"]
    assert addons.install(app.paths, out["token"], True)[0]
    try:
        app = App()
        st = overlay.status(app)
        assert st["errors"] == [] and st["linked"][name]["modules"] == man["features"]
        named = {c["name"] for c in man["commands"]} - {"*"}
        offered = {c.name for mid in man["features"] for c in app.modules[mid].commands()}
        assert named <= offered, named - offered
        assert st["errors"] == []  # nothing it offers was beyond its card
    finally:
        fence.clear()
