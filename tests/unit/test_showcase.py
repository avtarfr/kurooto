"""The pages' palette (look.palette): kuro, the deep greens, by default; rose, the original, as a choice."""

import re

import pytest

from kurooto.app import App
from kurooto.web.server import start
from tests.unit.test_web import call


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    srv = start(app, port=18790)
    yield app, srv
    srv.stop()
    app.close()


def palette(page: str) -> str:
    return re.search(r'<html lang="en" data-palette="([a-z]+)">', page)[1]


def test_kuro_by_default_rose_on_request(web):
    app, srv = web
    for path in ("/setup", "/morning", "/confidential"):
        code, page = call(srv, path, token=False)
        assert code == 200 and palette(page) == "kuro" and "{{" not in page
    app.settings.set("setup.done", True)
    assert palette(call(srv, "/", token=False)[1]) == "kuro"
    assert call(srv, "/api/settings", {"key": "look.palette", "value": "rose"})[1] == {"ok": True}
    assert palette(call(srv, "/", token=False)[1]) == "rose"
    assert any(s["section"] == "look" for s in call(srv, "/api/settings")[1]["sections"])
    app.settings.set("look.palette", '"><script>')  # anything else is the default, never written into the page
    page = call(srv, "/setup", token=False)[1]
    assert palette(page) == "kuro" and '<script>"' not in page


def test_status_colours_are_not_the_accent():
    from importlib import resources

    css = resources.files("kurooto.web").joinpath("static", "style.css").read_text(encoding="utf-8")
    first = re.search(r":root, body\.home \{(.*?)\}", css, re.S)[1]
    tokens = dict(re.findall(r"--([a-z-]+): (#[0-9a-f]{6})", first))
    assert tokens["bg"] == "#0b0f0a" and tokens["accent"] == "#6b8a42"
    assert len({tokens["accent"], tokens["accent-text"], tokens["warn"], tokens["bad"]}) == 4
    home = resources.files("kurooto.web").joinpath("static", "home.css").read_text(encoding="utf-8")
    assert ".bad2 { color: var(--bad); }" in home and ".warn { color: var(--warn); }" in home
