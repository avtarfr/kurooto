"""Add-ons by link (core/addons.py, core/fence.py, core/overlay.py): a card before anything is added, pinned to one
commit, held to its card when it loads and while it runs, updates with what changed, remove with Undo."""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import addons, egress, fence, overlay

FEATURE = """import socket
import subprocess
import urllib.request

from kurooto.core import egress, proc
from kurooto.modules.base import Command, Module

from . import _words


class Weather(Module):
    id = "weather_x"
    title = "Weather X"
    description = "Says the weather."

    def commands(self):
        return [Command("weather", "the weather", lambda msg, arg: _words.SAID),
                Command("sneaky", "not on the card", lambda msg, arg: "never")]

    def start(self):
        self.every("hourly", "every 60m", lambda payload=None: None)
        self.every("secret", "every 5m", lambda payload=None: None)

    def fetch(self, url, opener):
        with egress.urlopen(urllib.request.Request(url), "weather_x", opener=opener) as r:
            return r.read()

    def lookup(self, host):
        return socket.getaddrinfo(host, 443)

    def run(self, prog, via_proc=False):
        if via_proc:
            return proc.run([prog, "--version"]).code
        return subprocess.run([prog, "--version"], capture_output=True).returncode

    def tell(self):
        from kurooto.core import desktop

        return desktop.notify("Weather", "sunny")

    def classify_intent(self, text, intents):
        return "weather"


class NotOnCard(Module):
    id = "hidden_x"
    title = "Hidden"
"""
MANIFEST = {
    "name": "weather-x",
    "title": "Weather X",
    "description": "The weather, from a made-up service.",
    "version": "1.0.0",
    "kurooto": ">=0.1",
    "features": ["weather_x"],
    "commands": [{"name": "weather", "what": "the weather now"}],
    "jobs": [{"id": "weather_x:hourly", "what": "checks every hour"}],
    "hosts": ["api.weather.example"],
    "programs": [{"name": "git", "online": True}],
}


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, files: dict[str, str], msg: str = "change") -> str:
    for rel, text in files.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=Test", "-c", "user.email=t@example.org", "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "weather-x"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    first = commit(
        r,
        {
            "kurooto-addon.json": json.dumps(MANIFEST),
            "modules/weather.py": FEATURE,
            "modules/_words.py": 'SAID = "sunny"\n',
            "skills/forecast/SKILL.md": "---\nname: forecast\ndescription: a forecast\n---\nSay the forecast.\n",
        },
    )
    return r, first


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    yield
    fence.clear()


def added(repo_path: Path) -> App:
    p = App().paths
    out = addons.fetch(p, str(repo_path))
    ok, msg = addons.install(p, out["token"], True)
    assert ok, msg
    return App()


def test_the_card_comes_first_and_nothing_is_added_without_a_yes(repo, home):
    r, first = repo
    app = App()
    out = addons.fetch(app.paths, str(r))
    c = out["card"]
    assert c["commit"] == first and c["name"] == "weather-x"
    assert c["code"] == ["_words.py", "weather.py"] and c["skills"] == ["forecast"]
    text = out["text"]
    for said in ("Weather X", "/weather", "weather_x:hourly: checks every hour", "api.weather.example",
                 "git (goes online by itself", "Runs code: YES", f"at {first[:12]}"):  # fmt: skip
        assert said in text, said
    assert any("classify_intent" in w for w in c["warnings"])  # it would read messages; its card doesn't ask
    assert addons.installed(app.paths) == {}
    ok, msg = addons.install(app.paths, out["token"], False)
    assert not ok and addons.installed(app.paths) == {} and not addons.folder(app.paths, "weather-x").exists()
    assert addons.install(app.paths, out["token"], True)[0] is False  # the card was answered: gone


def test_added_it_loads_held_to_its_card_and_off_until_turned_on(repo, home, tmp_path):
    r, first = repo
    commit(r, {"README.md": "newer\n"}, "a newer commit on main")
    app = App()
    out = addons.fetch(app.paths, str(r), ref=first)  # a commit: pinned there, not to main's newest
    assert addons.install(app.paths, out["token"], True)[0]
    rec = addons.installed(app.paths)["weather-x"]
    assert rec["commit"] == first and rec["consent"]["code"] is True
    assert git(addons.folder(app.paths, "weather-x"), "rev-parse", "HEAD") == first
    app = App()
    st = overlay.status(app)
    assert st["linked"]["weather-x"]["modules"] == ["weather_x"] and "hidden_x" not in app.modules
    m = app.modules["weather_x"]
    assert m.linked == "weather-x" and not app.is_on("weather_x")
    assert [c.name for c in m.commands()] == ["weather"]  # /sneaky isn't on the card
    assert any("sneaky" in e["error"] for e in st["errors"]) and any("hidden_x" in e["error"] for e in st["errors"])
    assert m.classify_intent is None  # it may not see messages first: its card didn't ask
    ok, why = app.enable("weather_x")
    assert ok, why
    jobs = [j.key for j in app.scheduler.jobs("weather_x:")]
    assert jobs == ["weather_x:hourly"]  # its "secret" job isn't on the card
    assert m.commands()[0].handler(None, "") == "sunny"  # its helper loads relatively
    assert any(str(d).endswith("weather-x/skills") for d in overlay.dirs(app, "skills"))
    assert not any("weather-x" in str(d) for d in overlay.dirs(app, "skills", linked=False))
    from kurooto.diagnostics import more_checks

    assert ("add-on weather-x", True, "weather_x") in more_checks(app, net=False)


def test_its_code_reaches_only_its_hosts_and_starts_only_its_programs(repo, home, monkeypatch):
    r, _ = repo
    app = added(r)
    egress.attach(app)
    m = app.modules["weather_x"]

    class Opener:
        def open(self, req, timeout=30):
            class R:
                def read(self, *a):
                    return b"sunny"

                def close(self):
                    pass

            return R()

    assert m.fetch("https://api.weather.example/now", Opener()) == b"sunny"
    with pytest.raises(egress.Fenced) as e:
        m.fetch("https://api.telegram.org/x", Opener())  # on Kurooto's own list, but not on its card
    assert "weather-x" in str(e.value) and "api.telegram.org" in str(e.value)
    with pytest.raises(OSError):
        m.lookup("elsewhere.example")  # a socket of its own: the same fence
    assert m.lookup("localhost")  # this computer is never fenced
    rows = egress.week(app.paths.state)
    assert any(x["host"] == "elsewhere.example" and x["blocked"] for x in rows)
    assert m.run("git") == 0  # on its card
    assert m.run("git", via_proc=True) == 0
    with pytest.raises(fence.ProgramFenced):
        m.run("python3")
    with pytest.raises(fence.ProgramFenced):
        m.run("python3", via_proc=True)  # Kurooto's proc.run is only a pass-through
    m.tell()  # a desktop notice is Kurooto's own work, made for it: not fenced
    assert any(x["via"] == "git" and x["feature"] == "add-on weather-x" for x in egress.week(app.paths.state))
    assert fence.owner() is None  # this test's own code is nobody's add-on
    urllib.request.Request("https://example.org")  # nothing fenced outside an add-on's frames


def test_changed_files_keep_it_from_loading(repo, home):
    r, _ = repo
    app = added(r)
    (addons.folder(app.paths, "weather-x") / "modules" / "weather.py").write_text("print('changed')\n")
    app = App()
    assert "weather_x" not in app.modules
    assert "changed since you agreed" in overlay.status(app)["linked"]["weather-x"]["problem"]


def test_an_update_shows_what_changes_and_undo_puts_the_old_one_back(repo, home):
    r, first = repo
    app = added(r)
    p = app.paths
    assert addons.check_update(p, "weather-x") == {"same": True, "commit": first}
    man = {**MANIFEST, "hosts": [*MANIFEST["hosts"], "tiles.weather.example"], "version": "1.1.0"}
    second = commit(r, {"kurooto-addon.json": json.dumps(man), "modules/_words.py": 'SAID = "rain"\n'})
    out = addons.check_update(p, "weather-x")
    assert out["card"]["commit"] == second
    assert "may reach: tiles.weather.example" in out["changes_text"]
    assert "modules/_words.py +1 -1" in out["changes_text"]
    assert addons.install(p, out["token"], True)[0]
    assert addons.installed(p)["weather-x"]["commit"] == second
    app = App()
    assert app.modules["weather_x"].commands()[0].handler(None, "") == "rain"
    ok, msg = addons.undo(p, "weather-x")
    assert ok and first[:12] in msg and addons.installed(p)["weather-x"]["commit"] == first
    assert overlay.reload_linked(app)["linked"]["weather-x"]["commit"] == first
    assert app.modules["weather_x"].commands()[0].handler(None, "") == "sunny"


def test_remove_then_undo(repo, home):
    r, _ = repo
    app = added(r)
    p = app.paths
    app.enable("weather_x")
    ok, msg = addons.remove(p, "weather-x")
    assert ok and "Undo" in msg and not addons.folder(p, "weather-x").exists()
    st = overlay.reload_linked(app)
    assert "weather_x" not in app.modules and st["linked"] == {}
    ok, msg = addons.undo(p, "weather-x")
    assert ok
    overlay.reload_linked(app)
    assert "weather_x" in app.modules and app.is_on("weather_x")  # back as it was, still on
    assert addons.remove(p, "nothing-here")[0] is False


@pytest.mark.parametrize(
    "url",
    ["ext::sh -c touch% /tmp/x", "http://example.org/a.git", "-uhelp", "", "relative/folder", "fd::17"],
)
def test_addresses_that_could_run_a_program_or_be_changed_are_refused(url, home):
    with pytest.raises(addons.AddonError):
        addons.check_url(url)


def test_a_manifest_that_asks_for_too_much_is_refused(tmp_path):
    for bad in ({"name": "X"}, {"name": "ok-name", "hosts": [".com"]}, {"name": "ok-name", "programs": ["/bin/sh"]},
                {"name": "ok-name", "features": ["a_b"], "jobs": ["other:x"]}):  # fmt: skip
        (tmp_path / addons.MANIFEST).write_text(json.dumps(bad))
        with pytest.raises(addons.AddonError):
            addons.read_manifest(tmp_path)
    (tmp_path / addons.MANIFEST).write_text(json.dumps({"name": "ok-name", "kurooto": ">=99.0"}))
    assert "needs Kurooto 99.0" in addons.fits(addons.read_manifest(tmp_path))


def test_the_dashboard_looks_adds_and_needs_the_code_box(repo, home):
    from kurooto.web.api import Api

    r, _ = repo
    app = App()
    api = Api(app)
    code, out = api.post("addons/look", {"url": str(r)})
    assert code == 200 and out["ok"] and "Runs code: YES" in out["text"]
    code, said = api.post("addons/add", {"token": out["token"]})
    assert not said["ok"] and "tick the box" in said["message"]
    code, said = api.post("addons/add", {"token": out["token"], "code": True})
    assert said["ok"], said
    assert any(m["id"] == "weather_x" and m["linked"] == "weather-x" for m in said["modules"])
    code, got = api.get("addons")
    assert got["linked"][0]["name"] == "weather-x" and "Weather X" in got["linked"][0]["text"]
    code, said = api.post("addons/remove", {"name": "weather-x"})
    assert said["ok"] and "weather_x" not in app.modules
    assert api.get("addons")[1]["kept"][0]["name"] == "weather-x"
    assert api.post("addons/undo", {"name": "weather-x"})[1]["ok"] and "weather_x" in app.modules
