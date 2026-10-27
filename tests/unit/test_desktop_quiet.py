"""0.8.10: a developer's scratch run (KUROOTO_NO_DESKTOP) never shows a real desktop notification."""

from kurooto.core import desktop, proc


def test_a_scratch_run_shows_nothing_on_the_desktop(monkeypatch):
    ran = []
    monkeypatch.setattr(proc, "run", lambda *a, **k: ran.append(a))
    monkeypatch.setenv("KUROOTO_NO_DESKTOP", "1")
    assert desktop.notify("Removed something", "it shouldn't show") is False
    assert ran == []
