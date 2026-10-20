"""0.5.1 first-day fixes: time zones compared by meaning (an old name and today's are one zone), a research project
folder that isn't a git repository is a note, reminders lose the ":" after their time, and the installers' beta
channel sticks."""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import zones
from kurooto.web.api import Api

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


@pytest.fixture
def local_zone():
    """This computer's clock set to a zone for the test (POSIX: TZ and tzset), and put back after."""
    if not hasattr(time, "tzset"):
        pytest.skip("needs time.tzset")
    old = os.environ.get("TZ")

    def use(name):
        os.environ["TZ"] = name
        time.tzset()

    yield use
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


# --------------------------------------------------------------------------------------------- time zones
@pytest.mark.parametrize(
    "given, today",
    [
        ("Asia/Calcutta", "Asia/Kolkata"),
        ("Europe/Kyiv", "Europe/Kyiv"),
        ("Europe/Kiev", "Europe/Kyiv"),
        ("US/Eastern", "America/New_York"),
        ("America/Buenos_Aires", "America/Argentina/Buenos_Aires"),
        ("Asia/Katmandu", "Asia/Kathmandu"),
        ("Etc/UTC", "UTC"),
        ("  europe/kyiv ", "Europe/Kyiv"),
        ("Europe/Oslo", "Europe/Oslo"),  # a place of its own, though it keeps Berlin's clock
        ("Not/AZone", "Not/AZone"),
        ("", ""),
        (None, ""),
    ],
)
def test_canonical_names(given, today):
    assert zones.canonical(given) == today


def test_zones_are_compared_by_meaning():
    assert zones.same_zone("Europe/Kiev", "Europe/Kyiv")
    assert zones.same_zone("Europe/Berlin", "Europe/Paris")  # the same clock all year
    assert not zones.same_zone("Europe/Berlin", "Africa/Lagos")  # the same in winter, not in summer
    assert not zones.same_zone("Europe/Kyiv", "Not/AZone")
    picker = zones.names()
    assert "Europe/Kyiv" in picker and "Europe/Kiev" not in picker and "UTC" in picker


def test_doctor_takes_an_old_name_for_the_computers_zone(app, local_zone):
    from kurooto.diagnostics import timezone_check

    local_zone("Europe/Kyiv")
    app.settings.set("you.timezone", "Europe/Kiev")
    name, ok, why = timezone_check(app)
    assert ok is True and "the same as this computer" in why
    assert zones.computer_zone() == "Europe/Kyiv"
    local_zone("Europe/Kiev")  # and the other way round
    app.settings.set("you.timezone", "Europe/Kyiv")
    assert timezone_check(app)[1] is True and zones.computer_zone() == "Europe/Kyiv"
    local_zone("Europe/Berlin")
    name, ok, why = timezone_check(app)
    assert ok is False and "(Europe/Berlin)" in why and "Set them the same" in why


def test_the_zone_is_saved_under_todays_name(app):
    api = Api(app)
    code, r = api.post("you", {"name": "Sam", "timezone": "Asia/Saigon"})
    assert code == 200 and r == {"ok": True, "timezone": "Asia/Ho_Chi_Minh"}
    assert app.settings.get("you.timezone") == "Asia/Ho_Chi_Minh"
    assert api.post("settings", {"key": "you.timezone", "value": "Europe/Kiev"})[1]["ok"]
    assert app.settings.get("you.timezone") == "Europe/Kyiv"
    st = api.get("state")[1]
    assert "Asia/Ho_Chi_Minh" in st["zones"] and "Asia/Saigon" not in st["zones"] and "computer_zone" in st


def test_an_old_name_already_saved_is_settled_at_start(app):
    app.settings.set("you.timezone", "Europe/Kiev")
    assert zones.settle(app) == "Europe/Kyiv"
    assert app.settings.get("you.timezone") == "Europe/Kyiv" and str(app.scheduler.tz) == "Europe/Kyiv"
    assert zones.settle(app) == ""  # once
    app.settings.set("you.timezone", "Not/AZone")
    assert zones.settle(app) == "" and app.settings.get("you.timezone") == "Not/AZone"  # left for doctor to say


def test_an_old_name_doesnt_redeploy_the_call_line(app):
    from kurooto.modules.calls import deploy

    app.settings.set("you.timezone", "Europe/Kyiv")
    before = deploy.fingerprint(app)
    app.settings.set("you.timezone", "Europe/Kiev")
    assert deploy.fingerprint(app) == before
    app.settings.set("you.timezone", "Europe/Berlin")
    assert deploy.fingerprint(app) != before


def test_the_setup_page_offers_todays_names():
    js = (ROOT / "src/kurooto/web/static/setup.js").read_text(encoding="utf-8")
    assert "state.zones" in js and "BROWSER_ZONES.includes(v)" in js and "r.timezone" in js


# ------------------------------------------------------------------------------------------- research
def test_a_project_folder_without_git_is_a_note(app, tmp_path):
    plain = tmp_path / "proposal-only"
    plain.mkdir()
    (plain / "proposal.md").write_text("# plan\n")
    app.settings.set("research.repos", [str(plain)])
    r = app.modules["research"]
    ok, why = r.health()
    assert ok is None
    assert f"{plain} isn't a git repository (no commits to follow): `git init` it, or /repos remove it" in why
    assert "missing" not in why
    assert list(r.projects()) == ["proposal-only"] and r.project_logs() == 0
    app.settings.set("research.repos", [str(plain), str(tmp_path / "gone")])
    ok, why = r.health()
    assert ok is False and why.startswith(f"repository folder missing: {tmp_path / 'gone'}")


def test_the_research_tab_keeps_and_removes_a_folder_without_git(app, tmp_path):
    plain = tmp_path / "proposal-only"
    plain.mkdir()
    app.settings.set("research.repos", [str(plain)])
    r = app.modules["research"]
    assert r.save({"repos": [str(plain)]})["repos"] == [str(plain)]  # already there: it stays
    with pytest.raises(ValueError, match="not a git repository"):
        r.save({"repos": [str(plain), str(tmp_path)]})  # a new one still has to be a repository
    r.save({"repos": []})
    assert app.settings.get("research.repos") == []


def test_doctor_lists_it_as_a_note(app, tmp_path):
    from kurooto import diagnostics

    plain = tmp_path / "proposal-only"
    plain.mkdir()
    app.settings.set("research.repos", [str(plain)])
    app.enable("research")
    row = next(c for c in diagnostics.checks(app) if c[0] == app.modules["research"].title)
    assert row[1] is None and "isn't a git repository" in row[2]


# ------------------------------------------------------------------------------------------- reminders
@pytest.mark.parametrize(
    "rest, what",
    [
        ("at 6 pm: research reminder about ebm", "research reminder about ebm"),
        ("at 6 pm - to call home", "call home"),
        ("at 6 pm — call home.", "call home"),
        ("tomorrow at 9: that the form is due", "the form is due"),
        ("at 7 about the exam", "the exam"),
        ("in 20 minutes: : tea", "tea"),
        ("to stretch in 10 minutes", "stretch"),
        ("at 7 tomato soup", "tomato soup"),
    ],
)
def test_reminder_text_loses_the_joins(rest, what):
    from kurooto.modules.reminders import WHEN_WORDS, tidy_what

    assert tidy_what(WHEN_WORDS.sub("", rest)) == what


def test_a_reminder_after_a_colon(env):
    env.on("reminders")
    out = env.say("remind me at 6 pm: research reminder about ebm")
    assert out.startswith("I'll remind you") and out.endswith("at 18:00: research reminder about ebm")
    assert ": :" not in out
    out = env.say("/remind 21:30 - call home")
    assert out.endswith("at 21:30: call home")


# ------------------------------------------------------------------------------------------- installer
def bootstrap():
    spec = importlib.util.spec_from_file_location("kurooto_bootstrap", ROOT / "installer" / "bootstrap.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "platform, env",
    [
        ("linux", {}),
        ("linux", {"XDG_CONFIG_HOME": "/xdg/config"}),
        ("linux", {"XDG_CONFIG_HOME": "relative/config"}),
        ("darwin", {}),
        ("win32", {"LOCALAPPDATA": "D:/AppData/Local"}),
        ("win32", {}),
        ("linux", {"KUROOTO_HOME": "/portable"}),
    ],
)
def test_bootstrap_finds_the_apps_settings_folder(platform, env, tmp_path):
    from kurooto.core.paths import paths

    assert bootstrap().config_dir(platform, env, tmp_path) == paths(platform, env, tmp_path).config


def test_bootstrap_remembers_the_channel(tmp_path, capsys):
    from kurooto.core.config import Settings

    b = bootstrap()
    folder = tmp_path / "config"
    assert b.remember_channel("stable", folder) is False and not folder.exists()  # the default: nothing written
    assert b.remember_channel("beta", folder) is True
    assert Settings(folder / "settings.json").get("updates.channel") == "beta"
    if os.name != "nt":
        assert (folder / "settings.json").stat().st_mode & 0o777 == 0o600
    (folder / "settings.json").write_text(json.dumps({"you": {"name": "Sam"}, "updates": {"mode": "off"}}))
    b.remember_channel("beta", folder)  # a repair keeps everything else
    assert json.loads((folder / "settings.json").read_text()) == {
        "you": {"name": "Sam"},
        "updates": {"mode": "off", "channel": "beta"},
    }
    (folder / "settings.json").write_text("{broken")
    assert b.remember_channel("beta", folder) is False
    assert (folder / "settings.json").read_text() == "{broken"  # never written over
    assert "updates.channel" in capsys.readouterr().out


def test_bootstrap_refuses_a_strange_channel(monkeypatch):
    b = bootstrap()
    monkeypatch.setattr(sys, "argv", ["bootstrap.py", "--channel", "../evil"])
    monkeypatch.setattr(b.shutil, "which", lambda name: pytest.fail("nothing runs before the channel is checked"))
    with pytest.raises(SystemExit, match="isn't a channel"):
        b.main()


def test_the_installers_pass_the_channel():
    sh = (ROOT / "installer" / "install.sh").read_text(encoding="utf-8")
    assert 'channel="${KUROOTO_CHANNEL:-stable}"' in sh and sh.count('--channel "$channel"') == 2
    ps = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8")
    assert "$env:KUROOTO_CHANNEL" in ps and ps.count("--channel $Channel") == 2


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell")
def test_install_sh_stops_at_a_strange_channel(tmp_path):
    env = {**os.environ, "KUROOTO_CHANNEL": "beta;x", "HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    r = subprocess.run(["sh", str(ROOT / "installer" / "install.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 1 and "Nothing was installed" in r.stdout
    assert list(tmp_path.iterdir()) == []
