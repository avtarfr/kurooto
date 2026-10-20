"""The system palette (look.palette = system): this computer's colours read from each source's own files and settings
(fixtures only: nothing here reads the real system), turned into page colours that stay readable (WCAG AA), served to
the pages and kept current, with kuro as the fallback; and the setup page's pieces that explain and guide."""

import random
import re
import shutil
from importlib import resources
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import palette, syscolors
from kurooto.core.syscolors import SysColors
from kurooto.web.server import start
from tests.unit.test_web import call

FIX = Path(__file__).parent.parent / "fixtures" / "syscolors"


def fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def table(name: str) -> dict[str, str]:
    """A fixture of "key<TAB>value" lines (what a command or the registry would say)."""
    return dict(ln.split("\t", 1) for ln in fx(name).splitlines() if ln and not ln.startswith("#"))


# ------------------------------------------------------------------------------------------------ parsers
def test_hex_values_are_checked():
    assert syscolors.hexcolor("#ABC") == "#aabbcc" and syscolors.hexcolor("d0bcff") == "#d0bcff"
    assert syscolors.hexcolor("#d0bcff80") == "#d0bcff" and syscolors.hexcolor("61, 174, 233") == "#3daee9"
    assert (
        syscolors.hexcolor("bad") is None
        and syscolors.hexcolor("red") is None
        and syscolors.hexcolor("300,1,1") is None
    )
    assert syscolors.hexcolor("#fff;}</style><script>") is None


def test_matugen_flat_as_end4_writes_it():
    c = syscolors.from_matugen(fx("matugen-flat-dark.json"))
    assert (c.source, c.accent, c.mode) == ("matugen", "#d0bcff", "dark")
    assert c.schemes["dark"]["surface_container"] == "#211f26" and "light" not in c.schemes


def test_matugen_both_modes_and_role_shapes():
    c = syscolors.from_matugen(fx("matugen-modes.json"), mode_hint="light")
    assert c.mode == "light" and c.accent == "#6750a4" and c.schemes["dark"]["primary"] == "#d0bcff"
    r = syscolors.from_matugen(fx("matugen-roles.json"))
    assert r.mode == "light" and r.schemes["dark"]["background"] == "#141218" and r.accent == "#6750a4"
    cael = syscolors.from_matugen(fx("caelestia-scheme.json"))
    assert cael.mode == "light" and cael.accent == "#6750a4" and cael.schemes["light"]["on_primary"] == "#ffffff"
    assert syscolors.from_matugen("not json") is None and syscolors.from_matugen('{"primary": 3}') is None


def test_material_scss():
    c = syscolors.from_material_scss(fx("material_colors.scss"))
    assert (c.accent, c.mode) == ("#d0bcff", "dark") and c.schemes["dark"]["on_surface_variant"] == "#cac4d0"
    assert "term1" not in c.schemes["dark"] and syscolors.scss_mode(fx("material_colors.scss")) == "dark"


def test_pywal_takes_the_most_colourful():
    c = syscolors.from_pywal(fx("pywal-colors.json"))
    assert (c.source, c.accent, c.mode) == ("pywal", "#2f7fd0", "dark")
    assert syscolors.from_pywal('{"special": {}}') is None


def test_kde():
    c = syscolors.from_kdeglobals(fx("kdeglobals"))
    assert (c.source, c.accent, c.mode) == ("kde", "#e9643d", "dark")
    light = syscolors.from_kdeglobals(fx("kdeglobals-light-noaccent"))
    assert (light.accent, light.mode) == ("#3daee9", "light")  # the selection colour without an AccentColor


def test_gnome_and_gtk():
    g = table("gsettings.txt")
    c = syscolors.from_gnome(g["accent-color"], g["color-scheme"], g["gtk-theme"])
    assert (c.accent, c.mode) == ("#2190a4", "dark")
    assert syscolors.from_gnome("'blue'", "'default'").mode == "light"
    assert syscolors.from_gnome("'nonsense'", "'nonsense'") is None
    t = syscolors.from_gtk(fx("gtk-settings.ini"), fx("gtk.css"))
    assert (t.accent, t.mode) == ("#904a43", "dark")
    assert syscolors.from_gtk(fx("gtk-settings-theme.ini"), None).mode == "dark"


def test_windows_and_macos():
    w = {k: int(v) for k, v in table("windows.txt").items()}
    c = syscolors.from_windows(w["AccentColor"], w["ColorizationColor"], w["AppsUseLightTheme"])
    assert (c.accent, c.mode) == ("#0078d7", "dark")
    assert syscolors.from_windows(None, w["ColorizationColor"], 1).accent == "#0078d7"
    assert syscolors.from_windows(None, None, 1).mode == "light"
    m = table("macos.txt")
    assert (syscolors.from_macos(m["AppleAccentColor"], m["AppleInterfaceStyle"]).accent) == "#bf5af2"
    blue = syscolors.from_macos(None, None)  # no accent set means multicolour (blue); no style means light
    assert (blue.accent, blue.mode) == ("#007aff", "light")


# ------------------------------------------------------------------------------------------------ reading
def place(home: Path, rel: str, fixture: str) -> None:
    p = home / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIX / fixture, p)


def nothing_runs(argv):
    raise AssertionError(f"ran {argv}")


def test_linux_reads_best_source_first(tmp_path):
    env = {"XDG_CURRENT_DESKTOP": "Hyprland"}
    assert syscolors.read("linux", tmp_path, env, run=lambda a: None) is None  # nothing set: the default palette
    place(tmp_path, ".config/gtk-4.0/gtk.css", "gtk.css")
    assert syscolors.read("linux", tmp_path, env, run=lambda a: None).source == "gtk"
    place(tmp_path, ".config/kdeglobals", "kdeglobals")  # has an AccentColor: used even outside Plasma
    assert syscolors.read("linux", tmp_path, env, run=lambda a: None).source == "kde"
    place(tmp_path, ".cache/wal/colors.json", "pywal-colors.json")
    assert syscolors.read("linux", tmp_path, env, run=nothing_runs).source == "pywal"
    place(tmp_path, ".local/state/quickshell/user/generated/colors.json", "matugen-flat-dark.json")
    c = syscolors.read("linux", tmp_path, env, run=nothing_runs)
    assert c.source == "matugen" and c.where.endswith("quickshell/user/generated/colors.json")


def test_linux_xdg_dirs_and_end4_scss_mode(tmp_path):
    state = tmp_path / "state"
    place(state, "quickshell/user/generated/colors.json", "matugen-roles.json")
    place(state, "quickshell/user/generated/material_colors.scss", "material_colors.scss")  # says dark
    c = syscolors.read("linux", tmp_path, {"XDG_STATE_HOME": str(state)}, run=lambda a: None)
    assert c.mode == "dark" and c.accent == "#d0bcff"


def test_gnome_only_on_gnome_and_mode_from_gsettings(tmp_path):
    g = table("gsettings.txt")
    seen = []

    def run(argv):
        seen.append(argv[-1])
        return g.get(argv[-1])

    assert syscolors.read("linux", tmp_path, {"XDG_CURRENT_DESKTOP": "Hyprland"}, run=run) is None
    c = syscolors.read("linux", tmp_path, {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, run=run)
    assert (c.source, c.accent, c.mode) == ("gnome", "#2190a4", "dark")
    # colours without a mode get it from the desktop's dark/light setting
    place(tmp_path, ".config/gtk-3.0/gtk.css", "gtk.css")
    c = syscolors.read("linux", tmp_path, {"XDG_CURRENT_DESKTOP": "sway"}, run=run)
    assert (c.source, c.mode) == ("gtk", "dark") and "color-scheme" in seen


def test_windows_and_macos_readers():
    w = {k: int(v) for k, v in table("windows.txt").items()}
    c = syscolors.read("win32", reg=lambda path, name: w.get(name), run=nothing_runs)
    assert (c.accent, c.mode) == ("#0078d7", "dark")
    m = table("macos.txt")
    c = syscolors.read("darwin", run=lambda argv: m.get(argv[-1]))
    assert (c.source, c.accent, c.mode) == ("macos", "#bf5af2", "dark")


def test_a_broken_source_never_breaks_anything(tmp_path):
    place(tmp_path, ".local/state/quickshell/user/generated/colors.json", "kdeglobals")  # not JSON
    (tmp_path / ".cache" / "wal").mkdir(parents=True)
    (tmp_path / ".cache" / "wal" / "colors.json").write_text("[1, 2", encoding="utf-8")
    assert syscolors.read("linux", tmp_path, {}, run=lambda a: None) is None

    def boom(*a):
        raise RuntimeError("registry gone")

    assert syscolors.read("win32", reg=boom) is None


# ------------------------------------------------------------------------------------------------ palettes
def test_static_palettes_match_style_css_and_are_readable():
    css = resources.files("kurooto.web").joinpath("static", "style.css").read_text(encoding="utf-8")
    blocks = {
        ("kuro", "dark"): re.search(r":root, body\.home \{(.*?)\}", css, re.S)[1],
        ("rose", "dark"): re.search(r':root\[data-palette="rose"\], \[data-palette="rose"\] body\.home \{(.*?)\}', css,
                                    re.S)[1],
        ("kuro", "light"): re.search(r':root, :root\[data-palette="kuro"\] \{(.*?)\}', css, re.S)[1],
        ("rose", "light"): re.search(r'  :root\[data-palette="rose"\] \{ color-scheme: light;(.*?)\}', css, re.S)[1],
    }  # fmt: skip
    for (name, mode), body in blocks.items():
        tokens = {f"--{k}": v.replace("#fff", "#ffffff") if v == "#fff" else v
                  for k, v in re.findall(r"--([a-z-]+): (#[0-9a-f]{3,6})\b", body)}  # fmt: skip
        want = palette.STATIC[name][mode]
        assert all(want[k] == v for k, v in tokens.items()), (name, mode)
        assert palette.failures(want) == [], (name, mode)


ACCENTS = (
    list(syscolors.GNOME_ACCENTS.values())
    + [c for pair in syscolors.MAC_ACCENTS.values() for c in pair]
    + ["#0078d7", "#ffff00", "#000080", "#00ff00", "#ffffff", "#000000", "#808080", "#d0bcff", "#6750a4"]
)


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_any_accent_gives_readable_text(mode):
    rnd = random.Random(7)  # noqa: S311 (colours, not secrets)
    for accent in ACCENTS + [f"#{rnd.randrange(1 << 24):06x}" for _ in range(150)]:
        v = palette.build(SysColors("x", "x", accent, mode), mode)
        assert set(v) == {f"--{k}" for k in palette.KEYS}
        assert palette.failures(v) == [], (accent, mode, palette.failures(v))
        assert all(palette.OK_HEX.fullmatch(c) for c in v.values())
        assert (palette.luminance(v["--bg"]) < 0.18) == (mode == "dark")


def test_full_schemes_keep_their_own_colours():
    c = syscolors.from_matugen(fx("matugen-modes.json"))
    dark, light = palette.build(c, "dark"), palette.build(c, "light")
    assert dark["--bg"] == "#141218" and dark["--accent"] == "#d0bcff" and dark["--accent-contrast"] == "#381e72"
    assert light["--bg"] == "#fef7ff" and light["--accent"] == "#6750a4" and light["--panel"] == "#f3edf7"
    assert dark["--lav"] == "#efb8c8" and palette.failures(dark) == palette.failures(light) == []
    only_dark = syscolors.from_matugen(fx("matugen-flat-dark.json"))  # a dark scheme can't dress a light page
    lp = palette.build(only_dark, "light")
    assert palette.luminance(lp["--bg"]) > 0.8 and palette.failures(lp) == []
    pywal = palette.build(syscolors.from_pywal(fx("pywal-colors.json")), "dark")
    assert pywal["--bg"] == "#1b1d22" and palette.failures(pywal) == []
    assert palette.build(None, "dark") == palette.KURO["dark"]


# ------------------------------------------------------------------------------------------------ the app
@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    found = {"value": None}
    monkeypatch.setattr(syscolors, "read", lambda *a, **k: found["value"])
    syscolors.forget()
    app = App()
    srv = start(app, port=18795)
    yield app, srv, found
    srv.stop()
    app.close()
    syscolors.forget()


def page_palette(page: str) -> str:
    return re.search(r'<html lang="en" data-palette="([a-z]+)">', page)[1]


def test_system_palette_on_the_pages_and_its_fallback(web):
    app, srv, found = web
    page = call(srv, "/setup", token=False)[1]
    assert '<style id="kurooto-palette"></style>' in page and "/static/palette.js" in page
    assert call(srv, "/api/settings", {"key": "look.palette", "value": "purple"})[0] == 400
    assert srv.api.post("settings", {"key": "look.palette", "value": "purple"})[1] == {
        "error": "look.palette is one of: kuro, rose, system"
    }
    assert call(srv, "/api/settings", {"key": "look.palette", "value": "system"})[1] == {"ok": True}
    page = call(srv, "/setup", token=False)[1]
    assert page_palette(page) == "kuro" and '<style id="kurooto-palette"></style>' in page  # nothing found yet
    look = call(srv, "/api/look")[1]
    assert (look["chosen"], look["palette"], look["system"], look["css"]) == ("system", "kuro", None, "")
    assert "system" not in look["previews"] and look["vars"] == palette.KURO["dark"]

    found["value"] = syscolors.from_matugen(fx("matugen-flat-dark.json"), where="/x/colors.json")
    syscolors.forget()
    page = call(srv, "/morning", token=False)[1]
    assert page_palette(page) == "system"
    style = re.search(r'<style id="kurooto-palette">(.*?)</style>', page, re.S)[1]
    assert ':root[data-palette="system"] { color-scheme: dark; --bg: #141218;' in style
    assert '[data-palette="system"] body.home { color-scheme: dark;' in style and "@media" not in style
    look = call(srv, "/api/look")[1]
    assert look["palette"] == "system" and look["system"]["source"] == "matugen" and look["css"] == style
    assert palette.current(app)["--accent"] == "#d0bcff" and palette.current(app, "light")["--bg"] != "#141218"

    found["value"] = SysColors("gtk", "Your GTK theme's colours", "#904a43", None)  # no mode: both, by the browser
    syscolors.forget()
    css = palette.css(app)
    assert "@media (prefers-color-scheme: light)" in css and css.count("color-scheme: dark") == 2


def test_settings_offer_the_palettes_with_what_they_are(web):
    app, srv, found = web
    look = next(s for s in call(srv, "/api/settings")[1]["sections"] if s["section"] == "look")
    assert [c[0] for c in look["choices"]["palette"]] == ["kuro", "rose", "system"]
    assert "nothing found here yet" in look["choices"]["palette"][2][1] and look["help"]["palette"]
    found["value"] = syscolors.from_kdeglobals(fx("kdeglobals"))
    syscolors.forget()
    look = next(s for s in call(srv, "/api/settings")[1]["sections"] if s["section"] == "look")
    assert "found: KDE's accent colour" in look["choices"]["palette"][2][1]
    assert "choices" not in next(s for s in call(srv, "/api/settings")[1]["sections"] if s["section"] == "you")


def test_your_own_theme_file(web, tmp_path):
    app, srv, found = web
    k = syscolors.from_kitty(fx("kitty-theme.conf"))
    assert (k.accent, k.mode, k.schemes["dark"]["background"]) == ("#ff5449", "dark", "#1a1110")
    assert syscolors.from_file(FIX / "pywal-colors.json").source == "file"
    assert syscolors.from_file(FIX / "material_colors.scss").accent == "#d0bcff"
    assert syscolors.from_file(FIX / "matugen-modes.json").label == "Your theme file (matugen-modes.json)"
    assert syscolors.from_file(tmp_path / "missing.conf") is None and syscolors.from_file(FIX / "gtk.css") is None
    bad = srv.api.post("settings", {"key": "look.theme_file", "value": str(FIX / "gtk.css")})
    assert bad[0] == 400 and "can't find colours" in bad[1]["error"] and app.settings.get("look.palette") == "kuro"
    assert srv.api.post("settings", {"key": "look.theme_file", "value": str(FIX / "kitty-theme.conf")})[0] == 200
    assert app.settings.get("look.palette") == "system"  # a theme file is used at once
    look = call(srv, "/api/look")[1]
    assert look["palette"] == "system" and look["system"]["source"] == "file" and look["vars"]["--bg"] == "#1a1110"
    assert srv.api.post("settings", {"key": "look.theme_file", "value": ""})[0] == 200
    assert call(srv, "/api/look")[1]["palette"] == "kuro"  # emptied, and this computer offers nothing: kuro


def test_detect_caches_and_forgets(monkeypatch):
    calls = []
    monkeypatch.setattr(syscolors, "read", lambda: calls.append(1) or None)
    syscolors.forget()
    syscolors.detect()
    syscolors.detect()
    assert len(calls) == 1
    syscolors.forget()
    syscolors.detect()
    assert len(calls) == 2
    syscolors.forget()


def test_current_needs_only_settings(tmp_path, monkeypatch):
    from kurooto.core.config import Settings

    monkeypatch.setattr(syscolors, "read", lambda *a, **k: None)
    syscolors.forget()
    s = Settings(tmp_path / "settings.json")
    assert palette.current(s) == palette.KURO["dark"] and palette.current(s, "light") == palette.KURO["light"]
    s.set("look.palette", "rose")
    assert palette.current(s)["--accent"] == "#ff4e79"
    s.set("look.palette", "system")
    s.set("look.theme_file", str(FIX / "kitty-theme.conf"))
    assert palette.current(s)["--bg"] == "#1a1110"
    syscolors.forget()
