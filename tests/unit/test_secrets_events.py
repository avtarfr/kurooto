import os

import pytest

from kurooto.core.events import Events, subscribe
from kurooto.core.secrets import Secrets


def test_file_fallback_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    s = Secrets(tmp_path / "config")
    assert s.kr is None and s.get("telegram_token") is None
    s.set("telegram_token", "t-123")
    assert s.get("telegram_token") == "t-123" and s.names() == ["telegram_token"]
    s.delete("telegram_token")
    assert s.get("telegram_token") is None


@pytest.mark.skipif(os.name == "nt", reason="file modes are POSIX-only")
def test_secrets_file_is_private(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    s = Secrets(tmp_path / "config")
    s.set("k", "v")
    assert (s.file.stat().st_mode & 0o777) == 0o600


def test_events_log_tail_and_listeners(tmp_path):
    ev = Events(tmp_path)
    seen = []
    off = subscribe(seen.append)
    try:
        ev.emit("message_in", text="hi")
        ev.emit("reminder_fired", what="tea")
    finally:
        off()
    ev.emit("message_in", text="after")
    assert [e["kind"] for e in seen] == ["message_in", "reminder_fired"]
    assert [e.get("text") for e in ev.tail(5, {"message_in"})] == ["hi", "after"]
