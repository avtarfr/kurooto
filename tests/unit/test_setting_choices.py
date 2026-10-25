"""0.8.0: settings with a known list of values are drop-downs, and every setting is explained in a tooltip."""

from __future__ import annotations

import json
from pathlib import Path

from kurooto.core import choices


def test_every_default_is_one_of_its_choices(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    import importlib

    from kurooto.app import App

    for m in ("core.autostart", "core.infer", "core.palette", "core.themes", "web.server", "web.api"):  # (their defaults are registered on import)
        try:
            importlib.import_module(f"kurooto.{m}")
        except ImportError:
            pass
    a = App()
    try:
        bad = []
        for key, opts in choices.CHOICES.items():
            d = a.settings.get(key)
            if d is None:
                bad.append(f"{key}: no such setting")
            elif d not in [o[0] for o in opts]:
                bad.append(f"{key}: default {d!r} not in {[o[0] for o in opts]}")
        assert not bad, bad
    finally:
        a.close()


def test_for_section():
    assert choices.for_section("books")["ocr"][0][0] == "auto" and choices.for_section("nothing") == {}
    assert "latex" in choices.for_section("books") and "books.ocr" not in choices.for_section("books")


def test_the_dashboard_gets_the_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App
    from kurooto.web.api import Api

    a = App()
    try:
        api = Api.__new__(Api)
        api.app = a
        secs = {s["section"]: s for s in api._settings()["sections"]}  # noqa: SLF001
        assert secs["quota"]["choices"]["local"][1][0] == "background"
        assert secs["updates"]["choices"]["mode"][0][0] == "night"  # the older, per-section lists stay
        assert secs["updates"]["tips"]["mode"] and secs["quota"]["tips"]["local"]
    finally:
        a.close()


def test_every_setting_has_a_tooltip():
    import json as _j

    from gen_settings_guide import collect

    help_ = _j.loads(
        (Path(__file__).resolve().parents[2] / "src" / "kurooto" / "data" / "settings-help.json").read_text()
    )
    rows = collect()
    assert len(help_) == len(rows)
    missing = [k for k, _v, why in rows if not why and not help_.get(k)]
    assert not missing, missing
    assert json.dumps(help_, sort_keys=True)  # plain JSON
