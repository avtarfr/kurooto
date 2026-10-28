"""The dashboard's two designs (0.5.19): look.design = "new" (the default: a sans-serif, Public Sans, bundled with
Kurooto, monospace only for terminals, code and paths) or "classic" (the monospace look of 0.5.18 and earlier,
home.css alone). The page says which in <body data-design>, the new design's rules are all scoped to it, and the
typeface is served from this computer."""

from importlib import resources

import pytest

from tests.unit.test_web import call

STATIC = resources.files("kurooto.web") / "static"


@pytest.fixture
def srv(env):
    from kurooto.web.server import start

    env.app.settings.set("setup.done", True)
    s = start(env.app, port=18977)
    yield env.app, s
    s.stop()


def test_the_new_design_is_the_default_and_classic_is_one_setting_away(srv):
    app, s = srv
    assert app.settings.get("look.design") == "new"
    page = call(s, "/", token=False)[1]
    assert 'data-design="new"' in page and "/static/home-new.css" in page and "/static/home.css" in page
    assert "data-design-toggle" in page  # the button in the top bar
    assert call(s, "/api/settings", {"key": "look.design", "value": "classic"})[1] == {"ok": True}
    page = call(s, "/", token=False)[1]
    assert 'data-design="classic"' in page and "{{DESIGN}}" not in page
    assert call(s, "/api/settings", {"key": "look.design", "value": "fancy"})[0] == 400  # new or classic only
    look = next(x for x in call(s, "/api/settings")[1]["sections"] if x["section"] == "look")
    assert [c[0] for c in look["choices"]["design"]] == ["new", "classic"]
    assert "classic" in look["help"]["design"].lower()


def test_an_unknown_design_in_the_settings_file_shows_the_new_one(srv):
    app, s = srv
    app.settings.set("look.design", "neon")
    assert 'data-design="new"' in call(s, "/", token=False)[1]


def test_the_typeface_is_served_from_this_computer(srv):
    _, s = srv
    from kurooto.web.server import static

    for name in ("public-sans-latin.woff2", "public-sans-latin-ext.woff2"):
        body = static(f"fonts/{name}")
        assert body and body[:4] == b"wOF2"
    assert static("fonts/../server.py") is None and static("fonts/OFL.txt") is None
    assert (STATIC / "fonts" / "OFL.txt").read_text(encoding="utf-8").count("SIL Open Font License") >= 1
    css = (STATIC / "home-new.css").read_text(encoding="utf-8")
    assert 'url("/static/fonts/public-sans-latin.woff2")' in css
    assert "://" not in css  # nothing from the internet


def test_classic_stays_as_it_was_and_the_new_rules_are_scoped():
    css = (STATIC / "home-new.css").read_text(encoding="utf-8")
    rules = [ln for ln in css.splitlines() if "{" in ln and not ln.lstrip().startswith(("/*", "@", "}"))]
    unscoped = [ln for ln in rules if 'data-design="new"' not in ln and not ln.startswith(("  ", "@"))]
    # the only rules for both designs: the heading's margin (classic's name was a div) and classic's button
    assert unscoped == [
        "h1.brand { margin: 0; }",
        ".bar .right .design-tg { display: inline-block; padding: 2px 8px; font: 12px var(--mono); }",
    ]
    home = (STATIC / "home.css").read_text(encoding="utf-8")
    assert "body.dense { font: var(--fs) / var(--lh) var(--mono); }" in home  # classic: the whole board in monospace
    js = (STATIC / "home.js").read_text(encoding="utf-8")
    assert "function setDesign" in js and 'key: "look.design"' in js
    assert 'if (key === "look.design") applyDesign(value);' in js  # a change in Settings applies at once
    assert "fontFamily: MONO" in js  # terminals keep the monospace in both designs


def test_a_settings_search_keeps_every_row_under_its_heading():
    """0.8.17: the new design floats each fieldset's heading the full width, and only the row right after it cleared
    the float. A search that hid that row left the next one beside the heading with no width: its name one letter a
    line down the right edge and its box tiny. Every row after the heading clears it now."""
    css = (STATIC / "home-new.css").read_text(encoding="utf-8")
    assert 'body[data-design="new"] .form legend { float: left; width: 100%;' in css
    assert 'body[data-design="new"] .form legend ~ * { clear: both; }' in css
    assert "legend + *" not in css


def test_reduced_motion_is_respected():
    css = (STATIC / "home-new.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css
