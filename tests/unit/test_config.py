from kurooto.core import config
from kurooto.core.config import Settings, merge, register_defaults


def test_merge_is_deep_and_does_not_alias():
    base = {"a": {"b": 1, "c": [1]}, "d": 1}
    out = merge(base, {"a": {"b": 2}})
    out["a"]["c"].append(2)
    assert out == {"a": {"b": 2, "c": [1, 2]}, "d": 1} and base["a"] == {"b": 1, "c": [1]}


def test_defaults_then_user_values(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULTS", {})
    register_defaults("checkins", {"evening": "22:00", "weekly": "19:30"})
    s = Settings(tmp_path / "settings.json")
    assert s.get("checkins.evening") == "22:00"
    assert s.set("checkins.evening", "21:30") == "22:00"
    assert s.get("checkins.evening") == "21:30" and s.get("checkins.weekly") == "19:30"
    assert s.user() == {"checkins": {"evening": "21:30"}}  # only the change is stored
    s.reset("checkins.evening")
    assert s.get("checkins.evening") == "22:00" and s.user() == {"checkins": {}}


def test_missing_key_gives_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULTS", {})
    s = Settings(tmp_path / "settings.json")
    assert s.get("nope.deeper", 5) == 5
