"""Your add-ons (the overlay): a folder of your own with features, skills, prompts and default settings; off until
turned on; a broken add-on never stops Kurooto and shows up in `kurooto doctor`."""

from __future__ import annotations

from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import overlay
from tests.unit.test_profile import registered  # noqa: F401 (the fixture: Profile sync and add-ons registered)

HELLO = """from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Module
from kurooto_addons._words import WORD

register_defaults("hello", {"greeting": "hello"})


class Hello(Module):
    id = "hello"
    title = "Hello"
    description = "Says hello."

    def commands(self):
        return [Command("hello", "say hello", lambda msg, arg: f"{self.setting('greeting')} {WORD}")]
"""
BADCMD = """from kurooto.modules.base import Intent, Module


class Bad(Module):
    id = "badcmd"
    title = "Bad"

    def commands(self):
        raise RuntimeError("commands broke")

    def intents(self):
        def match(text):
            raise ValueError("match broke")

        return [Intent("bad", "always breaks", match, lambda msg, slots: "never")]
"""
CLASH = """from kurooto.modules.base import Module


class Mine(Module):
    id = "telegram"
"""


def make_addons(root: Path) -> Path:
    m = root / "modules"
    m.mkdir(parents=True)
    (m / "hello.py").write_text(HELLO, encoding="utf-8")
    (m / "_words.py").write_text('WORD = "there"\n', encoding="utf-8")
    (m / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    (m / "exits.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    (m / "clash.py").write_text(CLASH, encoding="utf-8")
    (m / "badcmd.py").write_text(BADCMD, encoding="utf-8")
    (root / "skills" / "tidy-desk").mkdir(parents=True)
    (root / "skills" / "tidy-desk" / "SKILL.md").write_text(
        "---\nname: tidy-desk\ndescription: tidy my desk list\neffort: low\n---\nTidy $ARGUMENTS\n", encoding="utf-8"
    )
    (root / "prompts").mkdir()
    (root / "prompts" / "weekly-plan.md").write_text(
        "---\ntitle: Weekly plan\nskill: true\n---\nPlan my week: $ARGUMENTS\n", encoding="utf-8"
    )
    (root / "settings.json").write_text(
        '{"hello": {"greeting": "hi"}, "checkins": {"evening": "20:15"}, "you": {"name": "Overlay"},'
        ' "modules": {"enabled": ["hello"]}}',
        encoding="utf-8",
    )
    return root


def test_add_ons_load_and_a_broken_one_never_stops_kurooto(env, tmp_path):
    from kurooto import diagnostics
    from kurooto.modules.library import prompts
    from kurooto.modules.skills import all_skills

    app = env.app
    addons = make_addons(tmp_path / "addons")
    app.settings.set("overlay.path", str(addons))
    assert "hello" not in app.modules  # off until "Your add-ons" is turned on
    app.settings.set("you.name", "Sam")
    env.on("overlay")

    assert app.modules["hello"].addon and app.modules["badcmd"].addon
    assert not app.is_on("hello")  # an add-on folder can't turn its own features on
    assert app.settings.get("checkins.evening") == "20:15"  # its defaults lie under yours...
    assert app.settings.get("you.name") == "Sam"  # ...and yours win
    st = overlay.status(app)
    where = " ".join(e["where"] for e in st["errors"])
    assert "broken.py" in where and "exits.py" in where and "clash.py" in where
    assert app.modules["telegram"].__class__.__name__ == "Telegram"  # the clash didn't replace it

    env.on("hello", "badcmd")
    assert env.say("/hello") == "hi there"
    app.settings.set("hello.greeting", "hey")
    assert env.say("/hello") == "hey there"
    assert "/hello" in env.say("/help")  # badcmd's commands() raising doesn't break /help or other commands
    env.say("what's on my plate this week, roughly")  # its intent's match() raising doesn't break plain English
    assert "badcmd.commands" in " ".join(e["where"] for e in overlay.status(app)["errors"])

    skills = all_skills(app)
    assert skills["tidy-desk"].source == "add-on" and skills["weekly-plan"].source == "add-on"
    assert "from your add-ons" in app.modules["skills"]._list(None, "tidy-desk")
    assert "/tidy-desk (add-on)" in app.modules["skills"]._list(None, "")
    assert "add-ons/weekly-plan" in [p["name"] for p in prompts(app.workspace, overlay.dirs(app, "prompts"))]
    assert "Hello (on)" in env.say("/addons")

    ok, why = app.modules["overlay"].health()
    assert ok is False and "problem" in why
    assert any(n == "Your add-ons" and ok is False for n, ok, _ in diagnostics.checks(app))

    ok, msg = app.disable("overlay")
    assert ok and "hello" not in app.modules and app.settings.get("checkins.evening") != "20:15"
    assert overlay.dirs(app, "skills") == [] and "tidy-desk" not in all_skills(app)


def test_add_ons_load_at_start_and_code_can_stay_off(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    addons = make_addons(tmp_path / "addons")
    app = App()
    app.settings.set("overlay.path", str(addons))
    app.settings.set("modules.enabled", ["overlay"])
    app.close()
    app = App()
    assert "hello" in app.modules and overlay.status(app)["path"] == str(addons)
    app.settings.set("overlay.code", False)
    app.close()
    app = App()
    assert "hello" not in app.modules and overlay.status(app)["settings"]  # skills, prompts, settings only
    app.close()


def test_add_ons_folder_must_be_outside_kurooto(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    app = App()
    inside = app.paths.data / "addons"
    inside.mkdir(parents=True)
    out = app.modules["overlay"].configure({"path": str(inside)})
    assert not out["ok"] and "outside" in out["message"]
    out = app.modules["overlay"].configure({"path": str(tmp_path / "nope")})
    assert not out["ok"]
    good = tmp_path / "mine"
    good.mkdir()
    assert app.modules["overlay"].configure({"path": str(good)})["ok"]
    assert app.modules["overlay"].ready() == (True, "")
    app.close()


@pytest.fixture(autouse=True)
def forget_layer():
    yield
    from kurooto.core import config

    config.set_layer({})
