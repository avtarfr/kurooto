"""0.8.0: every feature says how to finish setting it up, every time it is switched on, and /health says what's left."""

from __future__ import annotations

import pytest

from kurooto.modules.catalog import CATALOG


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def test_every_feature_declares_its_steps(app):
    for cls in CATALOG:
        steps = app.modules[cls.id].setup_steps()
        assert steps and all({"what", "done", "how", "undo"} <= set(s) and s["what"] for s in steps), cls.id


def test_hands_on_steps_come_with_a_command_and_an_undo(app):
    for mid in ("books", "calls", "telegram", "google", "local_models", "backups"):
        notes = [s for s in app.modules[mid].setup_steps() if not s["done"] and s["how"]]
        assert notes and all(s["undo"] for s in notes), mid
    assert "pacman -S poppler" in str(app.modules["books"].setup_steps())


def test_what_a_feature_needs_is_listed(app):
    app.settings.set("modules.enabled", [])
    need = [s for s in app.modules["startby"].setup_steps() if s["what"].startswith("Turn on")]
    assert need and not need[0]["done"] and "Deadlines" in need[0]["what"]
    app.settings.set("modules.enabled", ["deadlines"])
    assert [s for s in app.modules["startby"].setup_steps() if s["what"].startswith("Turn on")][0]["done"]
    assert app.modules["alarm"].setup_steps()  # never empty


def test_enable_returns_the_steps_and_health_setup_lists_what_is_left(app):
    steps = app.modules["books"].setup_steps()
    assert any("Poppler" in s["what"] and s.get("note") for s in steps)
    app.settings.set("modules.enabled", ["books", "startby"])
    text, _ = app.health.command("setup")
    assert "Books" in text and "Poppler" in text and "Turn on Deadlines" in text
    app.settings.set("modules.enabled", [])
    assert "Nothing is left" in app.health.command("setup")[0]
    plain, _ = app.health.command("")
    assert "set-up" not in plain.lower() or "Everything" in plain  # /health itself is as it was
