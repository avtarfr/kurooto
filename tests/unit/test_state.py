import os

import pytest

from kurooto.core import state
from kurooto.core.state import jload, jsave


def test_round_trip_keeps_unicode(tmp_path):
    f = tmp_path / "a" / "s.json"
    jsave(f, {"note": "नमस्ते", "n": 1})
    assert jload(f) == {"note": "नमस्ते", "n": 1}
    assert "नमस्ते" in f.read_text(encoding="utf-8")


def test_missing_or_broken_gives_a_copy_of_the_default(tmp_path):
    d = {"x": [1]}
    got = jload(tmp_path / "none.json", d)
    got["x"].append(2)
    assert d == {"x": [1]}
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert jload(tmp_path / "bad.json", {}) == {}


@pytest.mark.skipif(os.name == "nt", reason="file modes are POSIX-only")
def test_private_mode(tmp_path):
    f = tmp_path / "s.json"
    jsave(f, {})
    assert (f.stat().st_mode & 0o777) == 0o600


def test_retries_a_briefly_locked_target(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = os.replace

    def flaky(a, b):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("held by the indexer")
        return real(a, b)

    monkeypatch.setattr(state.os, "replace", flaky)
    monkeypatch.setattr(state.time, "sleep", lambda s: None)
    jsave(tmp_path / "s.json", {"ok": True})
    assert jload(tmp_path / "s.json") == {"ok": True} and calls["n"] == 3


def test_gives_up_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setattr(state.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("stuck")))
    monkeypatch.setattr(state.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        jsave(tmp_path / "s.json", {})
    assert list(tmp_path.iterdir()) == []
