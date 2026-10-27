"""0.8.10: the Brain on the phone app (modules/calls/views.py, kind "brain"): the Brain console's copy, sealed for each
Android phone like Systems, sent only while a phone watches it, and replaced by an "off" copy once it's turned off.
The page that shows it (static/views/brain.html, brainconsole.js) keeps to what Android 6's WebView runs."""

from __future__ import annotations

import time

from kurooto import mind
from kurooto.modules.calls import views
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_views import STATIC, Connector, v  # noqa: F401 (the shared fixture)


def watched(v, monkeypatch):  # noqa: F811
    monkeypatch.setattr(views, "WATCH_S", 1.5)
    monkeypatch.setattr(views, "BRAIN_S", 0.3)
    c = Connector(v.line)
    v.calls.connector = c
    return c


def wait_quiet(v, n=100):  # noqa: F811
    for _ in range(n):
        if not v.views.brain_looping:
            return
        time.sleep(0.1)


def test_off_unless_views_and_brain_are_on(v, monkeypatch):  # noqa: F811
    c = watched(v, monkeypatch)
    try:
        assert v.views.watch({"kind": "brain"}) is False  # calls.views off: nothing at all
        v.app.settings.set("calls.views", True)
        assert v.app.settings.get("calls.views_brain") is True  # on by default: nothing goes until a phone watches
        assert v.views.watch({"kind": "brain"}) is True
        wait_quiet(v)
        snap, _ = v.line.opened(v.key, "brain")  # Brain itself is off: one "off" copy, and it stops
        assert snap["off"] and "Brain is off" in snap["why"] and len(v.line.puts("brain")) == 1
        assert v.line.puts("systems") == []
    finally:
        c.loop.call_soon_threadsafe(c.loop.stop)
        mind.forget_client(v.app)


def test_live_while_watched_then_off_replaces_it(v, monkeypatch):  # noqa: F811
    c = watched(v, monkeypatch)
    v.app.settings.set("calls.views", True)
    v.app.settings.set("modules.enabled", ["mind", *(v.app.settings.get("modules.enabled") or [])])
    try:
        v.calls.on_event({"name": "views_watch", "device": "abcd1234", "kind": "brain"})  # from the call line
        time.sleep(0.4)
        snap, _ = v.line.opened(v.key, "brain")
        assert snap["kind"] == "brain" and not snap.get("off") and snap["islands"] and "decisions" in snap
        wait_quiet(v)
        n = len(v.line.puts("brain"))
        assert n >= 2 and not v.views.brain_looping  # live while watched, then it stops
        assert any(e["kind"] == "phone_views_watching" and e.get("view") == "brain" for e in v.app.events.tail(30))
        v.app.settings.set("calls.views_brain", False)
        v.views.on_event({"kind": "setting_changed", "key": "calls.views_brain"})
        wait_quiet(v)
        snap, _ = v.line.opened(v.key, "brain")
        assert snap["off"] and "views_brain" in snap["why"]
        m = len(v.line.puts("brain"))
        v.views.watch({"kind": "brain"})
        wait_quiet(v)
        assert len(v.line.puts("brain")) == m  # the "off" copy went once
    finally:
        c.loop.call_soon_threadsafe(c.loop.stop)
        mind.forget_client(v.app)


def test_the_phone_page_loads_only_its_own_files():
    page = (STATIC / "views" / "brain.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in page and "script-src 'self'" in page and "style-src 'self'" in page
    assert 'src="brainconsole.js"' in page and 'href="brainconsole.css"' in page
    js = (STATIC / "views" / "brainconsole.js").read_text(encoding="utf-8")
    assert "KurootoView" in js and "BrainConsole" in js and 'style="' not in js  # the page's CSP has no inline styles
    import re

    css = (STATIC / "views" / "brainconsole.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", css)  # every colour from the palette


def test_the_dashboard_has_the_page():
    home = (STATIC / "home.js").read_text(encoding="utf-8")
    assert 'console: "Brain console"' in home and 'console: "o"' in home
    assert "views/brainconsole.js" in home and "api(`brain/console?" in home and "function renderConsole" in home
