"""Links to other sites open in the default browser (0.5.1): core/opener.py open_url, POST /api/open-url, the
look.links_in setting and static/links.js on every page. The clicks themselves are checked in a headless browser
against a sandbox daemon with a fake $BROWSER."""

import sys
import threading
import time

import pytest

from kurooto.core import opener


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://aistudio.google.com/apikey", True),
        ("http://example.org/a?b=c#d", True),
        ("javascript:alert(1)", False),
        ("file:///etc/passwd", False),
        ("data:text/html,hi", False),
        ("https://", False),
        ("https://exa mple.org", False),
        ("https://example.org/\nx", False),
        ("https://example.org/" + "a" * 4000, False),
        (None, False),
        (["https://example.org"], False),
    ],
)
def test_only_web_addresses_go_to_the_browser(url, ok):
    assert (opener.safe_url(url) is not None) is ok and (not ok or opener.safe_url(url) == url)


def test_open_url_uses_webbrowser_and_doesnt_wait_for_a_slow_one(monkeypatch):
    import webbrowser

    monkeypatch.setattr(sys, "platform", "linux")
    seen = []
    monkeypatch.setattr(webbrowser, "open", lambda u, new=0: seen.append((u, new)) or True)
    assert opener.open_url("https://example.org/") == (True, "") and seen == [("https://example.org/", 2)]
    assert opener.open_url("file:///etc/passwd")[0] is False and len(seen) == 1  # never handed on

    done = threading.Event()
    monkeypatch.setattr(webbrowser, "open", lambda u, new=0: done.wait(5) or True)  # a $BROWSER that stays open
    t = time.monotonic()
    assert opener.open_url("https://example.org/", wait=0.2) == (True, "") and time.monotonic() - t < 2
    done.set()

    monkeypatch.setattr(webbrowser, "open", lambda u, new=0: False)
    ok, why = opener.open_url("https://example.org/")
    assert not ok and why

    def broken(u, new=0):
        raise OSError("no such program")

    monkeypatch.setattr(webbrowser, "open", broken)
    assert opener.open_url("https://example.org/") == (False, "no such program")


def test_open_url_on_windows_is_the_default_program(monkeypatch):
    import os

    monkeypatch.setattr(sys, "platform", "win32")
    seen = []
    monkeypatch.setattr(os, "startfile", seen.append, raising=False)
    assert opener.open_url("https://example.org/") == (True, "") and seen == ["https://example.org/"]


def test_the_api_route_and_the_setting(env, monkeypatch):
    from kurooto.web.server import start
    from tests.unit.test_dashboard import call

    app = env.app
    assert app.settings.get("look.links_in") == "default"
    seen = []
    monkeypatch.setattr(opener, "open_url", lambda u: seen.append(u) or (True, ""))
    srv = start(app, port=18976)
    try:
        assert call(srv, "/api/open-url", {"url": "https://example.org/"}) == (200, {"ok": True})
        assert call(srv, "/api/open-url", {"url": "javascript:alert(1)"})[0] == 400
        assert call(srv, "/api/open-url", {"url": "https://example.org/"}, token=False)[0] in (401, 403)
        assert seen == ["https://example.org/"]

        import urllib.request

        def page():
            with urllib.request.urlopen(srv.url) as r:
                return r.read().decode()

        assert '<meta name="kurooto-links" content="default">' in page() and "/static/links.js" in page()
        assert call(srv, "/api/settings", {"key": "look.links_in", "value": "here"})[1] == {"ok": True}
        assert call(srv, "/api/open-url", {"url": "https://example.org/"}) == (200, {"ok": False, "here": True})
        assert '<meta name="kurooto-links" content="here">' in page() and len(seen) == 1
        app.settings.set("look.links_in", '"><script>')  # anything else is "default", never written into the page
        assert '<meta name="kurooto-links" content="default">' in page()
    finally:
        srv.stop()


def test_links_js_leaves_this_computers_pages_and_modified_clicks_alone():
    from importlib import resources

    js = (resources.files("kurooto.web") / "static" / "links.js").read_text(encoding="utf-8")
    assert "u.origin !== location.origin" in js and "localhost" in js and "127\\." in js
    assert "e.ctrlKey || e.metaKey || e.shiftKey || e.altKey" in js
    assert '"/api/open-url"' in js and "window.open = " in js and "native(" in js  # falls back when it fails
