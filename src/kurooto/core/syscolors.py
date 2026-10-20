"""This computer's own colours: its accent colour and whether it's in light or dark mode, for the "system" palette
(Settings → Look → look.palette = system; core/palette.py turns them into the pages' colours).

Read best source first:
  Linux    Material You colours made from the wallpaper by matugen (end-4's Hyprland setup writes them to
           ~/.local/state/quickshell/user/generated/, and others to similar places), then pywal (~/.cache/wal), then
           the desktop's own: KDE (kdeglobals), GNOME (accent-color and color-scheme), GTK (a libadwaita accent in
           gtk.css, the prefer-dark setting or a "-dark" theme name).
  Windows  the accent colour (DWM AccentColor, else ColorizationColor) and "apps use light theme".
  macOS    the accent colour (AppleAccentColor) and dark mode (AppleInterfaceStyle).

The parsers are pure (text in, colours out) and every value comes back as a checked "#rrggbb". `read()` does the
reading, with the files, commands and registry injectable so tests never touch the real system; `detect()` caches it
for a few seconds, so pages asking every 30 seconds cost almost nothing. Nothing leaves the computer.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

HEX = re.compile(r"#?([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})")  # "#rgb", "rrggbb", "#rrggbbaa"
STRICT = re.compile(r"#[0-9a-f]{6}")

# GNOME 47+ named accent colours (libadwaita's accent_bg_color for each)
GNOME_ACCENTS = {
    "blue": "#3584e4",
    "teal": "#2190a4",
    "green": "#3a944a",
    "yellow": "#c88800",
    "orange": "#ed5b00",
    "red": "#e62d42",
    "pink": "#d56199",
    "purple": "#9141ac",
    "slate": "#6f8396",
}
# macOS AppleAccentColor: number -> (light, dark) system colour; no value means "multicolour", which is blue
MAC_ACCENTS = {
    -1: ("#8e8e93", "#98989d"),  # graphite
    0: ("#ff3b30", "#ff453a"),  # red
    1: ("#ff9500", "#ff9f0a"),  # orange
    2: ("#ffcc00", "#ffd60a"),  # yellow
    3: ("#28cd41", "#32d74b"),  # green
    4: ("#007aff", "#0a84ff"),  # blue
    5: ("#af52de", "#bf5af2"),  # purple
    6: ("#ff2d55", "#ff375f"),  # pink
}


@dataclass
class SysColors:
    """What was found: where from, the accent, the mode, and (matugen, pywal) named colours for each mode."""

    source: str  # matugen, pywal, kde, gnome, gtk, windows, macos
    label: str  # for people: "Material You colours from your wallpaper (matugen)"
    accent: str | None = None  # "#rrggbb"
    mode: str | None = None  # "dark", "light", or None (unknown: the page follows the browser)
    schemes: dict[str, dict[str, str]] = field(default_factory=dict)  # mode -> {role: "#rrggbb"}
    where: str = ""  # the file or setting it came from

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "label": self.label,
            "accent": self.accent,
            "mode": self.mode,
            "where": self.where,
            "full": bool(self.schemes),
        }


# --------------------------------------------------------------------------------------------- colour basics
def hexcolor(value) -> str | None:
    """'#rgb', 'rrggbb', '#rrggbbaa' or 'r,g,b' as '#rrggbb'; None for anything else."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            r, g, b = (int(v) for v in value[:3])
        except (TypeError, ValueError):
            return None
        return f"#{r:02x}{g:02x}{b:02x}" if all(0 <= v <= 255 for v in (r, g, b)) else None
    if not isinstance(value, str):
        return None
    s = value.strip().strip("'\"")
    if re.fullmatch(r"\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(\s*,\s*\d{1,3})?", s):
        return hexcolor(s.split(","))
    m = HEX.fullmatch(s)
    if not m:
        return None
    h = m.group(1).lower()
    if len(h) == 3 and not s.startswith("#"):
        return None  # "bad" is a word, "#bad" a colour
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h[:6]  # #rrggbbaa: the colour without its transparency


def luminance(color: str) -> float:
    """WCAG relative luminance of '#rrggbb'."""

    def ch(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def mode_of(background: str | None) -> str | None:
    """A background's mode: dark below the middle grey."""
    return None if not background else ("dark" if luminance(background) < 0.18 else "light")


def snake(name: str) -> str:
    """onSurfaceVariant / on-surface-variant -> on_surface_variant."""
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).replace("-", "_").lower()


def _roles(d: dict) -> dict[str, str]:
    out = {}
    for k, v in d.items():
        c = hexcolor(v) if isinstance(v, str) else None
        if c:
            out[snake(str(k))] = c
    return out


# --------------------------------------------------------------------------------------------- the parsers
def from_matugen(text: str, mode_hint: str | None = None, where: str = "") -> SysColors | None:
    """matugen's colours as JSON, in any of its shapes:
    flat {"primary": "#..", "background": ..} (end-4's colors.json, most templates);
    {"colors": {"dark": {..}, "light": {..}}} (`matugen --json hex`, older);
    {"colors": {"primary": {"dark": "#..", "light": "#..", "default": ..}}} (newer);
    {"mode": "dark", "colours": {"primary": "ffb1c1", ..}} (Caelestia's scheme.json: no "#")."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    schemes: dict[str, dict[str, str]] = {}
    mode = mode_hint if mode_hint in ("dark", "light") else None
    colors = data.get("colors", data.get("colours"))
    if isinstance(data.get("mode"), str) and data["mode"].lower() in ("dark", "light"):
        mode = mode or data["mode"].lower()
    if isinstance(colors, dict) and any(k in colors for k in ("dark", "light")):
        for m in ("dark", "light"):
            if isinstance(colors.get(m), dict):
                schemes[m] = _roles(colors[m])
    elif isinstance(colors, dict) and colors and all(isinstance(v, dict) for v in colors.values()):
        for m in ("dark", "light"):
            schemes[m] = _roles({k: v.get(m) for k, v in colors.items() if isinstance(v.get(m), str)})
        default = _roles({k: v.get("default") for k, v in colors.items() if isinstance(v.get("default"), str)})
        if default.get("background") and not mode:
            mode = mode_of(default["background"])
    else:
        flat = _roles(colors if isinstance(colors, dict) else data)
        if flat:
            m = mode or mode_of(flat.get("background") or flat.get("surface"))
            schemes[m or "dark"] = flat
            mode = m
    schemes = {m: r for m, r in schemes.items() if r.get("primary")}
    if not schemes:
        return None
    if mode is None and len(schemes) == 1:
        mode = next(iter(schemes))
    accent = (schemes.get(mode or "") or next(iter(schemes.values())))["primary"]
    return SysColors("matugen", "Material You colours from your wallpaper (matugen)", accent, mode, schemes, where)


def from_material_scss(text: str, where: str = "") -> SysColors | None:
    """SCSS variables ($darkmode: True; $primary: #FFB1C1; ...), as end-4's setups write them next to colors.json."""
    vals = dict(re.findall(r"^\s*\$([A-Za-z0-9_-]+)\s*:\s*([^;]+);", text or "", re.M))
    dm = vals.get("darkmode", "").strip().lower()
    mode = "dark" if dm == "true" else "light" if dm == "false" else None
    roles = _roles({k: v for k, v in vals.items() if not k.startswith("term")})
    if not roles.get("primary"):
        return None
    mode = mode or mode_of(roles.get("background"))
    return SysColors("matugen", "Material You colours from your wallpaper (matugen)", roles["primary"], mode,
                     {mode or "dark": roles}, where)  # fmt: skip


def scss_mode(text: str) -> str | None:
    """Only the $darkmode line of an SCSS colours file (end-4 writes it beside colors.json)."""
    m = re.search(r"^\s*\$darkmode\s*:\s*(\w+)", text or "", re.M)
    return (
        None
        if not m
        else "dark"
        if m.group(1).lower() == "true"
        else "light"
        if m.group(1).lower() == "false"
        else None
    )


def from_pywal(text: str, where: str = "") -> SysColors | None:
    """pywal's colors.json: {"special": {"background", "foreground"}, "colors": {"color0".."color15"}}. pywal has no
    accent, so the most colourful of color1-color6 is used."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    special, cols = data.get("special") or {}, data.get("colors") or {}
    bg, fg = hexcolor(special.get("background")), hexcolor(special.get("foreground"))
    palette = [hexcolor(cols.get(f"color{i}")) for i in range(16)]
    if not bg or not fg or not any(palette[1:7]):
        return None

    def chroma(c: str) -> float:
        r, g, b = (int(c[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return max(r, g, b) - min(r, g, b)

    picks = [c for c in palette[1:7] if c]
    accent = max(picks, key=lambda c: (round(chroma(c), 2), c == palette[4]))
    mode = mode_of(bg)
    roles = {"background": bg, "on_surface": fg, "primary": accent}
    roles.update({f"color{i}": c for i, c in enumerate(palette) if c})
    return SysColors("pywal", "Colours from your wallpaper (pywal)", accent, mode, {mode or "dark": roles}, where)


def ini(text: str) -> dict[str, dict[str, str]]:
    """A forgiving INI reader (KDE's files have [$i] markers, odd keys and repeats)."""
    out: dict[str, dict[str, str]] = {}
    sec = out.setdefault("", {})
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and "]" in line:
            sec = out.setdefault(line[1 : line.index("]")], {})
        elif "=" in line:
            k, v = line.split("=", 1)
            sec[re.sub(r"\[\$\w+\]$", "", k.strip())] = v.strip()
    return out


def from_kdeglobals(text: str, where: str = "") -> SysColors | None:
    """KDE Plasma: [General] AccentColor (else the selection colour); dark if the window background is dark (else
    by the colour scheme's name)."""
    c = ini(text)
    gen = c.get("General", {})
    accent = hexcolor(gen.get("AccentColor", "")) or hexcolor(c.get("Colors:Selection", {}).get("BackgroundNormal", ""))
    window = hexcolor(c.get("Colors:Window", {}).get("BackgroundNormal", ""))
    scheme = gen.get("ColorScheme", "")
    mode = mode_of(window) or ("dark" if "dark" in scheme.lower() else "light" if "light" in scheme.lower() else None)
    if not accent and not mode:
        return None
    return SysColors("kde", "KDE's accent colour", accent, mode, {}, where)


def gnome_mode(color_scheme: str | None, gtk_theme: str | None = None) -> str | None:
    """`gsettings get org.gnome.desktop.interface color-scheme` ('prefer-dark', 'prefer-light', 'default') and the
    GTK theme's name ('Adwaita-dark')."""
    cs = (color_scheme or "").strip().strip("'\"")
    if cs == "prefer-dark":
        return "dark"
    if cs == "prefer-light":
        return "light"
    theme = (gtk_theme or "").strip().strip("'\"").lower()
    return "dark" if theme.endswith("dark") or "-dark" in theme else None


def from_gnome(accent_color: str | None, color_scheme: str | None, gtk_theme: str | None = None) -> SysColors | None:
    """GNOME 47+: the named accent colour and the colour scheme (as `gsettings get` prints them)."""
    name = (accent_color or "").strip().strip("'\"")
    accent = GNOME_ACCENTS.get(name)
    mode = gnome_mode(color_scheme, gtk_theme)
    if (color_scheme or "").strip().strip("'\"") == "default" and mode is None:
        mode = "light"  # GNOME's default is light
    if not accent and not mode:
        return None
    return SysColors("gnome", "GNOME's accent colour", accent, mode, {}, "org.gnome.desktop.interface")


def from_gtk(settings_ini: str | None, gtk_css: str | None, where: str = "") -> SysColors | None:
    """GTK: a libadwaita accent in gtk.css (@define-color accent_bg_color #..; matugen and theme tools write one),
    and dark mode from settings.ini (gtk-application-prefer-dark-theme, or a "-dark" theme name)."""
    accent = None
    for name in ("accent_bg_color", "accent_color"):
        m = re.search(rf"@define-color\s+{name}\s+(#[0-9a-fA-F]{{3,8}})\s*;", gtk_css or "")
        if m and (accent := hexcolor(m.group(1))):
            break
    s = ini(settings_ini or "").get("Settings", {})
    pref = s.get("gtk-application-prefer-dark-theme", "").lower()
    mode = "dark" if pref in ("1", "true") else gnome_mode(None, s.get("gtk-theme-name"))
    if mode is None and pref in ("0", "false") and s.get("gtk-theme-name"):
        mode = "light"
    if not accent and not mode:
        return None
    return SysColors("gtk", "Your GTK theme's colours", accent, mode, {}, where)


def from_windows(accent: int | None, colorization: int | None, apps_light: int | None) -> SysColors | None:
    """Windows: DWM AccentColor (0xAABBGGRR), else ColorizationColor (0xAARRGGBB); AppsUseLightTheme 1 or 0."""
    color = None
    if isinstance(accent, int) and accent >= 0:
        color = f"#{accent & 0xFF:02x}{(accent >> 8) & 0xFF:02x}{(accent >> 16) & 0xFF:02x}"
    elif isinstance(colorization, int) and colorization >= 0:
        color = f"#{(colorization >> 16) & 0xFF:02x}{(colorization >> 8) & 0xFF:02x}{colorization & 0xFF:02x}"
    mode = None if apps_light is None else "light" if apps_light else "dark"
    if not color and not mode:
        return None
    return SysColors("windows", "Windows' accent colour", color, mode, {}, "Personalization")


def from_macos(accent_out: str | None, style_out: str | None) -> SysColors | None:
    """macOS: `defaults read -g AppleAccentColor` (a number; nothing means multicolour, i.e. blue) and
    `defaults read -g AppleInterfaceStyle` ("Dark"; nothing means light)."""
    mode = "dark" if (style_out or "").strip().lower() == "dark" else "light"
    try:
        n = int((accent_out or "").strip())
    except ValueError:
        n = 4
    light, dark = MAC_ACCENTS.get(n, MAC_ACCENTS[4])
    return SysColors("macos", "macOS's accent colour", dark if mode == "dark" else light, mode, {}, "System Settings")


def from_kitty(text: str, where: str = "") -> SysColors | None:
    """A kitty-style theme ("background #1a1110", "color4 #2f7fd0" ...; end-4 and matugen templates write one): like
    pywal, the most colourful of color1-color6 is the accent."""
    vals = {}
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("#") and (c := hexcolor(parts[1])):
            vals[parts[0].lower()] = c
    wal = {"special": {"background": vals.get("background"), "foreground": vals.get("foreground")},
           "colors": {f"color{i}": vals.get(f"color{i}") for i in range(16)}}  # fmt: skip
    found = from_pywal(json.dumps(wal), where)
    if found:
        found.source, found.label = "file", "Your theme file"
    return found


def from_file(path: str | Path) -> SysColors | None:
    """Your own colours file (look.theme_file): matugen or pywal JSON, SCSS variables, or a kitty-style theme."""
    p = Path(str(path)).expanduser()
    text = _text(p)
    if not text:
        return None
    found = None
    if text.lstrip().startswith("{"):
        found = from_pywal(text, str(p)) if '"special"' in text else from_matugen(text, where=str(p))
    elif re.search(r"^\s*\$[A-Za-z]", text, re.M):
        found = from_material_scss(text, str(p))
    else:
        found = from_kitty(text, str(p))
    if found:
        found.source, found.label, found.where = "file", f"Your theme file ({p.name})", str(p)
    return found


# --------------------------------------------------------------------------------------------- reading
Run = Callable[[list[str]], "str | None"]
Reg = Callable[[str, str], "int | None"]


def _run(argv: list[str]) -> str | None:
    import shutil

    if not shutil.which(argv[0]):
        return None
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def _reg(path: str, name: str) -> int | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            v, _ = winreg.QueryValueEx(k, name)
        return int(v) & 0xFFFFFFFF
    except (ImportError, OSError, TypeError, ValueError):
        return None


def _text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() and p.stat().st_size < 2_000_000 else None
    except OSError:
        return None


def linux_paths(home: Path, env: dict) -> dict[str, list[Path]]:
    """Where each Linux source keeps its colours, best first."""
    state = Path(env.get("XDG_STATE_HOME") or home / ".local" / "state")
    cache = Path(env.get("XDG_CACHE_HOME") or home / ".cache")
    config = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    return {
        "matugen": [
            state / "quickshell" / "user" / "generated" / "colors.json",  # end-4's dots (Quickshell)
            state / "matugen" / "user" / "generated" / "colors.json",
            state / "caelestia" / "scheme.json",  # Caelestia's dots
            cache / "matugen" / "colors.json",
            config / "matugen" / "colors.json",
        ],
        "scss": [
            state / "ags" / "scss" / "_material.scss",  # end-4's dots (older, AGS)
            state / "quickshell" / "user" / "generated" / "material_colors.scss",
        ],
        "pywal": [cache / "wal" / "colors.json"],
        "kde": [config / "kdeglobals"],
        "gtk_css": [config / "gtk-4.0" / "gtk.css", config / "gtk-3.0" / "gtk.css"],
        "gtk_ini": [config / "gtk-4.0" / "settings.ini", config / "gtk-3.0" / "settings.ini"],
    }


def _linux(home: Path, env: dict, run: Run) -> SysColors | None:
    paths = linux_paths(home, env)
    desktop = (env.get("XDG_CURRENT_DESKTOP") or env.get("DESKTOP_SESSION") or "").lower()
    found: SysColors | None = None
    scss_text = next((t for p in paths["scss"] if (t := _text(p))), None)
    for p in paths["matugen"]:
        if (t := _text(p)) and (found := from_matugen(t, scss_mode(scss_text or ""), str(p))):
            break
    if not found:
        for p in paths["scss"]:
            if (t := _text(p)) and (found := from_material_scss(t, str(p))):
                break
    if not found:
        for p in paths["pywal"]:
            if (t := _text(p)) and (found := from_pywal(t, str(p))):
                break

    def kde() -> SysColors | None:
        t = _text(paths["kde"][0])
        if not t or not ("kde" in desktop or "plasma" in desktop or "AccentColor" in t):
            return None
        return from_kdeglobals(t, str(paths["kde"][0]))

    def gnome() -> SysColors | None:
        if "gnome" not in desktop and "unity" not in desktop:
            return None  # elsewhere gsettings says "blue" whatever the desktop looks like
        q = ["gsettings", "get", "org.gnome.desktop.interface"]
        return from_gnome(run([*q, "accent-color"]), run([*q, "color-scheme"]), run([*q, "gtk-theme"]))

    def gtk() -> SysColors | None:
        css = next((t for p in paths["gtk_css"] if (t := _text(p))), None)
        settings = next((t for p in paths["gtk_ini"] if (t := _text(p))), None)
        return from_gtk(settings, css, str(paths["gtk_css"][0]))

    desk = [kde, gnome] if ("kde" in desktop or "plasma" in desktop) else [gnome, kde]
    others = [] if found else [f() for f in (*desk, gtk)]
    if not found:
        found = next((o for o in others if o and o.accent), None)
    if found and found.mode is None:  # colours without a mode: the desktop's dark/light setting
        cs = run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
        found.mode = gnome_mode(cs) or next((o.mode for o in others if o and o.mode), None)
        if found.mode is None and (g := gtk()):
            found.mode = g.mode
    return found


def read(
    platform: str | None = None,
    home: Path | None = None,
    env: dict | None = None,
    run: Run | None = None,
    reg: Reg | None = None,
) -> SysColors | None:
    """This computer's colours, best source first; None when nothing is set (Kurooto's default palette then)."""
    platform = platform or sys.platform
    home = Path(home or Path.home())
    env = dict(os.environ if env is None else env)
    run = run or _run
    reg = reg or _reg
    try:
        if platform == "win32":
            dwm = r"Software\Microsoft\Windows\DWM"
            accent = reg(dwm, "AccentColor")
            if accent is None:
                accent = reg(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent", "AccentColorMenu")
            light = reg(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme")
            return from_windows(accent, reg(dwm, "ColorizationColor"), light)
        if platform == "darwin":
            return from_macos(run(["defaults", "read", "-g", "AppleAccentColor"]),
                              run(["defaults", "read", "-g", "AppleInterfaceStyle"]))  # fmt: skip
        return _linux(home, env, run)
    except Exception:  # a strange file or setting never breaks the pages: the default palette it is
        return None


_cache: dict = {"at": 0.0, "value": None, "file": ""}
_lock = threading.Lock()


def detect(ttl: float = 20.0, theme_file: str = "") -> SysColors | None:
    """Your theme file (look.theme_file) if it has colours, else read(); remembered for `ttl` seconds."""
    with _lock:
        if _cache["at"] and time.monotonic() - _cache["at"] < ttl and _cache["file"] == theme_file:
            return _cache["value"]
    value = None
    if theme_file:
        try:
            value = from_file(theme_file)
        except Exception:
            value = None
    value = value or read()
    with _lock:
        _cache.update(at=time.monotonic(), value=value, file=theme_file)
    return value


def forget() -> None:
    """Read again next time (tests, or after the user changes their colours and asks)."""
    with _lock:
        _cache.update(at=0.0, value=None, file="")
