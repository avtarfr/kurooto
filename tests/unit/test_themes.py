"""The named themes (look.palette = catppuccin-mocha, gruvbox, ...): each project's official colours kept as published,
mapped onto Kurooto's roles, every text colour readable (WCAG AA) on the backgrounds it's read on, a dark flavour for
the dashboard and terminals with the family's light flavour for light pages, and the themes on the pages, in Settings,
in the terminals' colours and in `kurooto top`."""

import json
import re
from importlib import resources
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import palette, syscolors, themes
from kurooto.web.server import start
from tests.unit.test_web import call

HEX = re.compile(r"#[0-9a-f]{6}")


# ------------------------------------------------------------------------------------------------ the table
@pytest.mark.parametrize("fid", list(themes.FLAVOURS))
def test_every_flavour_is_complete_and_readable(fid):
    f = themes.FLAVOURS[fid]
    assert all(HEX.fullmatch(c) for c in f.colours.values()), fid  # the official palette, as lower-case hex
    assert set(themes.ROLES) <= set(f.roles) and all(n in f.colours for n in f.roles.values()), fid
    v = palette.flavour(fid)
    assert list(v) == [f"--{k}" for k in palette.KEYS] and all(HEX.fullmatch(c) for c in v.values()), fid
    assert palette.failures(v) == [], (fid, palette.failures(v))
    for key in palette.TEXT:  # every pair, said out loud
        for back in ("bg", "panel"):
            assert palette.contrast(v[f"--{key}"], v[f"--{back}"]) >= 4.5, (fid, key, back)
    assert (palette.luminance(v["--bg"]) < 0.18) == (f.mode == "dark"), fid
    # backgrounds and lines are always the official ones; nothing else moved unless it had to
    for role in ("bg", "panel", "line"):
        assert v[f"--{role}"] == f.colours[f.roles[role]], (fid, role)
    moved = {m["role"] for m in palette.adjusted() if m["flavour"] == fid}
    for role in themes.ROLES:
        if role not in moved:
            assert v[f"--{role}"] == f.colours[f.roles[role]], (fid, role)


def test_official_colours_and_names():
    v = palette.flavour
    assert v("catppuccin-mocha")["--bg"] == "#1e1e2e" and v("catppuccin-mocha")["--accent"] == "#cba6f7"
    assert v("catppuccin-latte")["--bg"] == "#eff1f5" and v("tokyonight-night")["--bg"] == "#1a1b26"
    assert v("tokyonight-storm")["--bg"] == "#24283b" and v("tokyonight-moon")["--fg"] == "#c8d3f5"
    assert v("rose-pine")["--bg"] == "#191724" and v("rose-pine-dawn")["--bg"] == "#faf4ed"
    assert v("gruvbox-dark")["--bg"] == "#282828" and v("nord")["--bg"] == "#2e3440"
    assert v("dracula")["--fg"] == "#f8f8f2" and v("everforest-dark")["--bg"] == "#2d353b"
    assert v("kanagawa-wave")["--bg"] == "#1f1f28" and v("solarized-dark")["--bg"] == "#002b36"
    names = {f.name for f in themes.FLAVOURS.values()}
    assert {"Catppuccin Frappé", "Rosé Pine", "Rosé Pine Moon", "Rosé Pine Dawn", "Tokyo Night Day"} <= names
    for fam in themes.FAMILIES.values():  # where they came from, and on what terms
        assert fam.url.startswith("https://") and fam.licence in ("MIT", "MIT/X11", "Apache-2.0"), fam.id


def test_every_family_pairs_dark_with_light():
    seen: list[str] = []
    for fam in themes.FAMILIES.values():
        assert fam.dark and all(themes.FLAVOURS[d].mode == "dark" for d in fam.dark), fam.id
        assert themes.FLAVOURS[fam.light].mode == "light", fam.id
        assert all(themes.FLAVOURS[x].family == fam.id for x in (*fam.dark, fam.light)), fam.id
        seen += [*fam.dark, fam.light]
    assert sorted(seen) == sorted(themes.FLAVOURS)  # every flavour is in exactly one family
    assert len(themes.THEMES) == sum(len(f.dark) for f in themes.FAMILIES.values())
    for tid, t in themes.THEMES.items():
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", tid) and tid not in palette.OWN, tid
        assert palette.variables(tid, "dark") == palette.flavour(t.dark)
        assert palette.variables(tid, "light") == palette.flavour(t.light)
        assert t.label.startswith(themes.FLAVOURS[t.dark].name) and "light mode: " in t.label
    assert themes.THEMES["catppuccin-macchiato"].light == "catppuccin-latte"
    assert themes.THEMES["gruvbox"].dark == "gruvbox-dark" and themes.THEMES["solarized"].light == "solarized-light"
    assert themes.THEMES["kanagawa-dragon"].light == "kanagawa-lotus"
    assert themes.THEMES["catppuccin-mocha"].label == "Catppuccin Mocha (light mode: Latte)"


def test_adjustments_are_minimal_and_documented():
    moved = palette.adjusted()
    assert moved and all(m["official"] != m["used"] for m in moved)
    for m in moved:  # the official colour really failed, and the one used is the palette's hue made readable
        f = themes.FLAVOURS[m["flavour"]]
        assert f.colours[m["name"]] == m["official"]
    dev = (Path(__file__).parents[2] / "docs" / "wiki" / "dev" / "core.md").read_text(encoding="utf-8")
    for m in moved:  # the developer wiki lists every one
        assert f"| {m['flavour']} | {m['role']} | {m['name']} {m['official']} | {m['used']} |" in dev, m


def test_export_for_other_apps():
    data = json.loads(json.dumps(palette.export()))
    assert set(data["themes"]) == {"kuro", "rose", *themes.THEMES}
    assert data["themes"]["nord"] == {"name": "Nord (light mode: Nord Light)", "family": "Nord", "dark": "nord",
                                      "light": "nord-light", "source": "https://github.com/nordtheme/nord",
                                      "licence": "MIT"}  # fmt: skip
    for fid, f in data["flavours"].items():
        assert set(f["roles"]) == set(palette.KEYS) and all(HEX.fullmatch(c) for c in f["roles"].values()), fid
    assert data["flavours"]["kuro"]["roles"]["bg"] == "#0b0f0a" and data["flavours"]["rose-light"]["mode"] == "light"
    assert palette.role_map("catppuccin-frappe", "light") == palette.role_map("catppuccin-latte")
    with pytest.raises(KeyError):
        palette.role_map("system")


# ------------------------------------------------------------------------------------------------ the app
@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setattr(syscolors, "read", lambda *a, **k: None)
    syscolors.forget()
    app = App()
    srv = start(app, port=18796)
    yield app, srv
    srv.stop()
    app.close()
    syscolors.forget()


def test_a_theme_on_the_pages_settings_and_api(web):
    app, srv = web
    assert call(srv, "/api/settings", {"key": "look.palette", "value": "catppuccin-mocha"})[1] == {"ok": True}
    page = call(srv, "/setup", token=False)[1]
    assert '<html lang="en" data-palette="catppuccin-mocha">' in page
    style = re.search(r'<style id="kurooto-palette">(.*?)</style>', page, re.S)[1]
    assert ':root[data-palette="catppuccin-mocha"] { color-scheme: dark; --bg: #1e1e2e;' in style
    assert '@media (prefers-color-scheme: light) { :root[data-palette="catppuccin-mocha"] { color-scheme: light; ' \
           '--bg: #eff1f5;' in style  # fmt: skip
    assert '[data-palette="catppuccin-mocha"] body.home { color-scheme: dark; --bg: #1e1e2e;' in style
    assert "<" not in style and ">" not in style
    look = call(srv, "/api/look")[1]
    assert (look["chosen"], look["palette"], look["css"]) == ("catppuccin-mocha", "catppuccin-mocha", style)
    assert look["vars"] == palette.flavour("catppuccin-mocha")
    mocha = next(c for c in look["choices"] if c["id"] == "catppuccin-mocha")
    assert mocha == {"id": "catppuccin-mocha", "label": "Catppuccin Mocha (light mode: Latte)",
                     "family": "Catppuccin", "dark": "Catppuccin Mocha", "light": "Catppuccin Latte"}  # fmt: skip
    assert "family" not in look["choices"][0] and set(look["previews"]) >= set(themes.THEMES)
    assert look["previews"]["nord"]["dark"][0] == "#2e3440" and look["previews"]["nord"]["light"][0] == "#eceff4"
    sec = next(s for s in call(srv, "/api/settings")[1]["sections"] if s["section"] == "look")
    assert ["rose-pine-moon", "Rosé Pine Moon (light mode: Dawn)"] in sec["choices"]["palette"]
    assert "named theme" in sec["help"]["palette"]
    assert call(srv, "/api/settings", {"key": "look.palette", "value": "catppuccin-latte"})[0] == 400  # a flavour
    assert app.settings.get("look.palette") == "catppuccin-mocha"
    assert call(srv, "/api/settings", {"key": "look.palette", "value": "rose"})[1] == {"ok": True}
    assert call(srv, "/api/look")[1]["css"] == ""  # kuro and rose stay in style.css, as before


def test_terminals_and_top_take_the_theme(tmp_path, monkeypatch):
    from kurooto import top
    from kurooto.core.config import Settings
    from kurooto.modules.terminal import look

    monkeypatch.setattr(syscolors, "read", lambda *a, **k: None)
    syscolors.forget()
    s = Settings(tmp_path / "settings.json")
    s.set("look.palette", "tokyonight-moon")
    assert palette.current(s) == palette.flavour("tokyonight-moon")
    assert palette.current(s, "light") == palette.flavour("tokyonight-day")
    assert top.colours(s)["bg"] == "#222436" and top.colours(s)["accent"] == "#82aaff"
    term = look.colours("gruvbox")
    assert term["background"] == "#282828" and term["foreground"] == "#ebdbb2" and term["color1"] == "#ff5540"
    assert look.palette("rose")["bg"] == "#22181a" and look.palette("kuro")["bg"] == "#0b0f0a"  # as before
    syscolors.forget()


def test_dashboard_canvases_read_the_palette_from_css():
    js = resources.files("kurooto.web").joinpath("static", "home.js").read_text(encoding="utf-8")
    # every colour the canvases draw with is a CSS variable, read again on "kurooto:palette"
    assert 'window.addEventListener("kurooto:palette"' in js and "function readPalette()" in js
    code = "\n".join(ln for ln in js.splitlines() if not ln.lstrip().startswith("//"))
    literals = set(re.findall(r'"(#[0-9a-fA-F]{6})"', code))
    pal = re.search(r"const PAL = \{(.*?)\};", js, re.S)[1]
    assert literals <= set(re.findall(r'"(#[0-9a-fA-F]{6})"', pal))  # only the fallbacks before the style loads
    assert "swatch-row" in js  # Settings shows the chosen palette's colours
