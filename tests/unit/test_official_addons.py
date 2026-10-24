"""Official add-ons (core/official.py): Kurooto's own list of published add-ons, each pinned to one commit. Adding one
is still the card and a yes (a guarded tap); "official" means in the list and at that commit; a newer pinned commit is
offered once and never applied without a yes. Git and the network are faked: the "clone" copies the add-on's folder
from addons/."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import kurooto
from kurooto.app import App
from kurooto.core import addons, fence, official, overlay, tap
from kurooto.modules.base import Incoming

ROOT = Path(__file__).resolve().parents[2] / "addons"
NEW = "1" * 40  # the commit a newer Kurooto pins (made up)
OTHER = "2" * 40  # any other commit of the same repository


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    if addons._version(kurooto.__version__) < (0, 6, 0):
        monkeypatch.setattr(kurooto, "__version__", "0.6.1")
    yield
    fence.clear()


@pytest.fixture
def clones(monkeypatch):
    """addons._clone, faked: the add-on's folder from addons/ (its repository is in the official list, or a made-up
    fork of it), at the commit asked for: the pinned one (by commit or tag), NEW (with a changed README) or OTHER."""
    asked: list[tuple[str, str]] = []

    def fake(p, url, ref, dest):
        asked.append((url, ref))
        e = official.entry_for(url) or official.find(url.rstrip("/").rsplit("/", 1)[-1].removeprefix("fork-"))
        assert e is not None, url
        shutil.copytree(ROOT / e["name"], dest, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        if ref == NEW:
            with open(dest / "README.md", "a", encoding="utf-8") as f:
                f.write("\nA newer version.\n")
            return NEW
        return ORIGINAL[e["name"]] if ref in (ORIGINAL[e["name"]], "v1.0.0", "") else OTHER

    monkeypatch.setattr(addons, "_clone", fake)
    return asked


ORIGINAL = {e["name"]: e["commit"] for e in official.catalog()}


def newer(monkeypatch, name: str) -> dict:
    """A newer Kurooto: the list pins NEW for this one, and the commit before it is in "earlier"."""
    entries = []
    for e in official.catalog():
        if e["name"] == name:
            e = {**e, "earlier": [e["commit"]], "commit": NEW, "tag": "v1.1.0"}
        entries.append(e)
    monkeypatch.setattr(official, "_load", lambda: tuple(entries))
    return next(e for e in entries if e["name"] == name)


def add(p, word: str) -> dict:
    out = official.fetch(p, word)
    ok, msg = addons.install(p, out["token"], True)
    assert ok, msg
    return out


def test_the_list_ships_with_kurooto_and_finds_by_name_or_repository():
    names = [e["name"] for e in official.catalog()]
    assert names == ["restic-backups", "desktop-helpers", "habits", "handwriting-pull", "night-performance"]
    for e in official.catalog():
        assert e["url"].startswith("https://github.com/") and len(e["commit"]) == 40 and e["tag"] == "v1.0.0"
    assert official.find("habits")["name"] == "habits"
    assert official.find("command-words")["name"] == "habits"  # its repository is kurooto-command-words
    assert official.find("kurooto-command-words")["name"] == "habits"
    assert official.find("weather-x") is None


def test_official_means_in_the_list_and_at_that_commit():
    e = official.find("restic-backups")
    for url in (
        e["url"],
        e["url"] + ".git",
        e["url"] + "/",
        e["url"].upper().replace("HTTPS", "https"),
        "git" + "@github.com:avtarfr/kurooto-restic-backups.git",
    ):  # fmt: skip  (ssh; split: not an email)
        assert official.match(url, e["commit"], "restic-backups") is not None, url
    assert official.match(e["url"], OTHER) is None  # another commit
    assert official.match("https://github.com/someone/kurooto-restic-backups", e["commit"]) is None  # a fork
    assert official.match(e["url"], e["commit"], "something-else") is None


def test_adding_one_shows_its_card_and_waits_for_a_yes(home, clones):
    p = App().paths
    out = official.fetch(p, "habits")
    e = official.find("habits")
    assert clones[-1] == (e["url"], e["commit"])  # checked out at the pinned commit, not wherever the tag points
    assert out["card"]["official"] == "v1.0.0" and out["card"]["commit"] == e["commit"]
    assert "Official: in this Kurooto's list" in out["text"] and "Runs code: YES" in out["text"]
    assert addons.installed(p) == {}  # nothing yet
    assert addons.install(p, out["token"], False)[0] is False and addons.installed(p) == {}
    add(p, "habits")
    rec = addons.installed(p)["habits"]
    assert rec["commit"] == e["commit"] and rec["ref"] == "v1.0.0"
    assert {r["name"]: r["have"] for r in official.rows(p)}["habits"] == "official"
    assert addons.listing(p)[0]["official"] == "v1.0.0"
    with pytest.raises(addons.AddonError, match="no official add-on"):
        official.fetch(p, "weather-x")


def test_by_hand_at_that_commit_is_official_a_fork_or_another_commit_is_not(home, clones):
    p = App().paths
    e = official.find("restic-backups")
    out = addons.fetch(p, e["url"] + ".git", "v1.0.0")  # by hand: same repository, its tag's commit
    assert out["card"]["official"] == "v1.0.0"
    addons.drop(p, out["token"])
    out = addons.fetch(p, e["url"], "main")  # same repository, another commit
    assert out["card"]["official"] == "" and "Official" not in out["text"]
    addons.drop(p, out["token"])
    out = addons.fetch(p, "https://github.com/someone/fork-restic-backups", "v1.0.0")  # a fork, same files
    assert out["card"]["official"] == ""
    assert addons.install(p, out["token"], True)[0]
    assert {r["name"]: r["have"] for r in official.rows(p)}["restic-backups"] == "other"
    assert official.update_for(addons.installed(p)["restic-backups"]) is None


def test_a_newer_pinned_commit_is_offered_once_and_needs_a_yes(home, clones, monkeypatch):
    app = App()
    p = app.paths
    add(p, "desktop-helpers")
    assert official.offers(app) == []
    newer(monkeypatch, "desktop-helpers")
    assert {r["name"]: r["have"] for r in official.rows(p)}["desktop-helpers"] == "update"
    assert addons.listing(p)[0]["official_update"] == "v1.1.0" and addons.listing(p)[0]["official"] == ""

    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    assert official.offer(app) == 1 and official.offer(app) == 0  # once per pinned commit
    text, kw = sent[0]
    assert "Desktop helpers (v1.1.0)" in text and kw["why"] == "addons.official_update"
    assert kw["buttons"] == [[("Look: Desktop helpers", "oad:desktop-helpers:check")]]
    assert app.calm.reason("addons.official_update").setting == "addons.official_updates"

    out = addons.check_update(p, "desktop-helpers")  # goes to the commit this Kurooto pins
    assert clones[-1][1] == NEW and out["card"]["official"] == "v1.1.0" and "README.md +2" in out["changes_text"]
    assert addons.install(p, out["token"], False)[0] is False
    assert addons.installed(p)["desktop-helpers"]["commit"] == ORIGINAL["desktop-helpers"]  # no yes: unchanged
    out = addons.check_update(p, "desktop-helpers")
    assert addons.install(p, out["token"], True)[0]
    assert addons.installed(p)["desktop-helpers"]["commit"] == NEW
    assert {r["name"]: r["have"] for r in official.rows(p)}["desktop-helpers"] == "official"


def test_the_offer_has_an_off_switch(home, clones, monkeypatch):
    app = App()
    add(app.paths, "habits")
    newer(monkeypatch, "habits")
    app.settings.set("addons.official_updates", False)
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append(text))
    assert official.offer(app) == 0 and sent == []


def test_add_on_telegram_is_a_guarded_tap_with_the_card_first(home, clones, monkeypatch):
    assert tap.BUTTONS["oad"] == "addon.install" and "button" in tap.GUARDED["addon.install"].ways

    monkeypatch.setattr(official, "_aside", lambda fn, *args: fn(*args))  # the card's fetch runs aside: here, at once
    app = App()
    sent = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: sent.append((text, kw)))
    assert app.callback("oad:habits:look") == "Fetching its card…"
    text, kw = sent[-1]
    assert "Your command words" in text and "Official:" in text and "Nothing is added until you tap" in text
    (yes, data), (no, _) = kw["buttons"][0]
    assert yes == "Add, I trust its code" and data.startswith("oad:") and data.endswith(":yes")
    assert addons.installed(app.paths) == {}  # the first tap only showed the card
    said = app.callback(data)
    assert said.startswith("Added Your command words") and "habits" in addons.installed(app.paths)
    assert "habits" in app.modules  # loaded at once, off until turned on
    assert not app.is_on("habits")

    assert app.callback("oad:desktop-helpers:look")
    tok = sent[-1][1]["buttons"][0][1][1].split(":")[1]
    assert app.callback(f"oad:{tok}:no") == "Not added; nothing was kept."
    assert "desktop-helpers" not in addons.installed(app.paths)
    assert app.callback("oad:weather-x:look").startswith("That add-on isn't")
    assert app.callback("oad:nonsense:yes").startswith("That card isn't waiting")


def test_telegram_addons_lists_them_with_add_buttons(home, clones):
    app = App()
    got = []
    msg = Incoming("/addons official", respond=lambda text, buttons=None: got.append((text, buttons)))
    app.handle(msg)  # answers with Your add-ons off too
    text, buttons = got[-1]
    assert text.startswith("Official add-ons") and "Machine backups (restic)" in text and "not added" in text
    assert [("Add Your command words", "oad:habits:look")] in buttons
    add(app.paths, "habits")
    overlay.reload_linked(app)  # what the Add button does after the yes
    app.handle(Incoming("/addons", respond=lambda text, buttons=None: got.append((text, buttons))))
    text, buttons = got[-1]
    assert "• habits (official) at d18cb4df8d21: Your command words (off)" in text
    assert "Your command words (habits): " in text and "added (v1.0.0)" in text
    assert all(b[0][1] != "oad:habits:look" for b in buttons)


def test_the_cli_lists_and_adds_by_name(home, clones, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setattr(cli, "ask_running", lambda *a, **k: None)  # never the owner's running Kurooto
    assert cli.main(["addons", "official"]) == 0
    out = capsys.readouterr().out
    assert "Handwriting from the cloud (handwriting-pull)" in out and "kurooto addons add <name>" in out
    assert cli.main(["addons", "add", "habits", "--ref", "main"]) == 1
    assert "official add-on comes at the commit" in capsys.readouterr().err
    assert cli.main(["addons", "add", "command-words", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Official: in this Kurooto's list" in out and "Added Your command words" in out
    assert cli.main(["addons"]) == 0
    assert "official v1.0.0" in capsys.readouterr().out
    newer(monkeypatch, "habits")
    assert cli.main(["addons"]) == 0
    assert "official v1.1.0 ready: kurooto addons update habits" in capsys.readouterr().out


def test_the_dashboard_offers_add_with_the_card_and_the_code_box(home, clones):
    from kurooto.web.api import Api

    app = App()
    api = Api(app)
    code, got = api.get("addons")
    assert [o["name"] for o in got["official"]] and all(o["have"] == "" for o in got["official"])
    code, out = api.post("addons/look", {"official": "restic-backups"})
    assert out["ok"] and out["card"]["official"] == "v1.0.0" and "Runs code: YES" in out["text"]
    assert not api.post("addons/add", {"token": out["token"]})[1]["ok"]  # the box for code first
    said = api.post("addons/add", {"token": out["token"], "code": True})[1]
    assert said["ok"] and any(m["id"] == "restic" and m["linked"] == "restic-backups" for m in said["modules"])
    got = api.get("addons")[1]
    assert {o["name"]: o["have"] for o in got["official"]}["restic-backups"] == "official"
    assert got["linked"][0]["official"] == "v1.0.0"
    assert api.post("addons/look", {"official": "nope"})[1]["ok"] is False


def test_the_dashboard_page_shows_the_official_group():
    js = (Path(kurooto.__file__).parent / "web" / "static" / "home.js").read_text(encoding="utf-8")
    assert "function officialBlock(al)" in js and 'api("addons/look", { official:' in js
    assert 'class="tag-off"' in js
