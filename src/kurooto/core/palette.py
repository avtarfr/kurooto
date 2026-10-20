"""The pages' colours (Settings → Look → look.palette), as CSS variables, in one place for everything that draws:

  kuro     deep greens (the default)
  rose     the original pinks
  system   this computer's own colours: its accent colour and light or dark mode (core/syscolors.py reads them from
           matugen, pywal, KDE, GNOME, GTK, Windows or macOS). Text stays readable: every text colour is moved
           lighter or darker until it passes WCAG AA (4.5:1) on the backgrounds it's used on. When nothing is found,
           it's kuro.

current(app) -> {"--bg": "#0b0f0a", "--fg": ..., ...} is what `kurooto top` and the terminal themes use; css(app)
is what the pages get (written into them by web/server.py, refreshed every 30 seconds by static/palette.js).
The dashboard is always dark; the other pages follow the light or dark mode.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from kurooto.core import syscolors
from kurooto.core.syscolors import SysColors, luminance, mode_of

if TYPE_CHECKING:
    from kurooto.app import App

NAMES = ("kuro", "rose", "system")
LABELS = {"kuro": "Kuro (deep greens)", "rose": "Rose (the original pinks)", "system": "This computer's colours"}
KEYS = ("bg", "fg", "dim", "line", "panel", "accent", "accent-text", "accent-contrast", "link", "hover",
        "lav", "pink", "peach", "sand", "rose", "ok", "warn", "bad")  # fmt: skip
# text colours and what they're read on: each pair must pass AA (4.5:1)
TEXT = ("fg", "dim", "accent-text", "link", "lav", "pink", "peach", "sand", "rose", "ok", "warn", "bad")


def _v(s: str) -> dict[str, str]:
    vals = s.split()
    return {f"--{k}": v for k, v in zip(KEYS, vals, strict=True)}


# the same values as static/style.css (a test keeps them equal)
KURO = {
    "dark": _v("#0b0f0a #dad3c8 #95a682 #26311f #151b12 #6b8a42 #a6c07a #0a0e08 #a6c07a #7e9a52 "
               "#8dbdb3 #d6967a #ddb866 #e4d8b4 #b9a6cc #8ccb98 #e2b550 #e8735a"),
    "light": _v("#f4f2ec #2f3a26 #52624a #d4ccbe #ffffff #3f5626 #3a4f22 #f6f3ec #3a4f22 #4c672e "
                "#3e6e66 #9a4e33 #8a6414 #6e5a2e #6a5384 #2e6b3f #8a5a00 #b23a26"),
}  # fmt: skip
ROSE = {
    "dark": _v("#22181a #efd1d0 #a9908f #4a3a3d #2b1f22 #ff4e79 #ff4e79 #1d1416 #ec8fa8 #ec8fa8 "
               "#b3a3d5 #ec8fa8 #ffba92 #f9d7ac #ffbcb2 #9fd8a8 #ffba92 #ff4e79"),
    "light": _v("#fbf3f2 #2a1c1f #7b6466 #e2cfcf #ffffff #ff4e79 #d72059 #1d1416 #a9536c #ec8fa8 "
                "#766795 #a9536c #9f613b #896b43 #9c6058 #447a4f #9f613b #d72059"),
}  # fmt: skip
STATIC = {"kuro": KURO, "rose": ROSE}
OK_HEX = re.compile(r"#[0-9a-f]{6}")


# ------------------------------------------------------------------------------------------- colour maths
def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_oklch(color: str) -> tuple[float, float, float]:
    """'#rrggbb' as OKLCH (lightness 0-1, chroma, hue in degrees): even steps of lightness look even."""
    r, g, b = (_lin(int(color[i : i + 2], 16) / 255) for i in (1, 3, 5))
    lc = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    mc = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    sc = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * lc + 0.7936177850 * mc - 0.0040720468 * sc  # noqa: N806
    A = 1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc  # noqa: N806
    B = 0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc  # noqa: N806
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def _rgb(L: float, C: float, h: float) -> tuple[float, float, float]:  # noqa: N803
    A, B = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))  # noqa: N806
    lc = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
    mc = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
    sc = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
    return (
        4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc,
        -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc,
        -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc,
    )


def oklch(L: float, C: float, h: float) -> str:  # noqa: N803
    """OKLCH back to '#rrggbb', with less chroma until it fits the screen's colours."""
    L = min(1.0, max(0.0, L))  # noqa: N806
    lo, hi = 0.0, max(0.0, C)
    if all(-1e-4 <= v <= 1 + 1e-4 for v in _rgb(L, hi, h)):
        lo = hi
    else:
        for _ in range(24):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if all(-1e-4 <= v <= 1 + 1e-4 for v in _rgb(L, mid, h)) else (lo, mid)
    return "#" + "".join(f"{round(min(1, max(0, _gam(v))) * 255):02x}" for v in _rgb(L, lo, h))


def mix(a: str, b: str, t: float) -> str:
    """a with t of b, in sRGB."""
    pa, pb = ([int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb, strict=True))


def readable(color: str, on: list[str], ratio: float = 4.5) -> str:
    """`color`, made lighter (on dark backgrounds) or darker (on light ones) just enough to reach `ratio` on all of
    `on`; its hue stays."""
    if min(contrast(color, b) for b in on) >= ratio:
        return color
    L, C, h = to_oklch(color)  # noqa: N806
    up = sum(luminance(b) for b in on) / len(on) < 0.18
    for i in range(1, 101):
        c = oklch(L + (i if up else -i) * 0.01, C, h)
        if min(contrast(c, b) for b in on) >= ratio:
            return c
    return max(("#ffffff", "#000000"), key=lambda c: min(contrast(c, b) for b in on))


# ------------------------------------------------------------------------------------------- the system palette
NEUTRAL = {  # OKLCH lightness and chroma of the backgrounds and text, tinted toward the accent's hue
    "dark": {"bg": (0.165, 0.012), "panel": (0.205, 0.016), "line": (0.30, 0.022), "fg": (0.90, 0.012),
             "dim": (0.74, 0.03)},
    "light": {"bg": (0.965, 0.008), "panel": (1.0, 0.0), "line": (0.86, 0.016), "fg": (0.26, 0.02),
              "dim": (0.46, 0.03)},
}  # fmt: skip
# the secondary colours (the dashboard's cells and graph, headings, chips) turn the accent's hue round the wheel
TURNS = {"lav": 60, "pink": -80, "peach": -40, "sand": -35, "rose": 180}


def build(colors: SysColors | None, mode: str) -> dict[str, str]:
    """The system palette for a light or dark page: CSS variables, every text colour readable (AA)."""
    mode = "light" if mode == "light" else "dark"
    if not colors or not colors.accent:
        return dict(KURO[mode])
    roles = dict(colors.schemes.get(mode) or {})
    back = roles.get("background") or roles.get("surface")
    if back and mode_of(back) != mode:
        roles = {}  # a light scheme can't dress a dark page: only its accent is used
    accent = roles.get("primary") or colors.accent
    _, ac, ah = to_oklch(accent)
    n = NEUTRAL[mode]

    def tone(key: str) -> str:
        L, C = n[key]  # noqa: N806
        return oklch(L, min(C, ac), ah)

    bg = roles.get("background") or roles.get("surface") or tone("bg")
    fg = roles.get("on_surface") or roles.get("on_background") or tone("fg")
    panel = roles.get("surface_container") or roles.get("surface_container_low") or (
        mix(bg, fg, 0.05) if roles.get("background") else tone("panel"))  # fmt: skip
    line = roles.get("outline_variant") or (mix(bg, fg, 0.16) if roles.get("background") else tone("line"))
    if contrast(line, bg) < 1.3:
        line = mix(bg, fg, 0.2)
    fg = readable(fg, [bg, panel], 7.0)
    dim = readable(roles.get("on_surface_variant") or (mix(fg, bg, 0.3) if roles.get("background") else tone("dim")),
                   [bg, panel])  # fmt: skip
    # the accent as a fill (buttons): visible on the page, and its text readable on it
    fill = readable(accent, [bg], 3.0)
    on = roles.get("on_primary")
    if not on or contrast(on, fill) < 4.5:
        # dark text on dark pages' buttons, white on light pages' (the button a shade darker if that's all it takes)
        first, other = ("#ffffff", "#111111") if mode == "light" else (bg, "#ffffff")
        darker = readable(fill, [first], 4.5)
        if contrast(first, fill) >= 4.5 or abs(to_oklch(darker)[0] - to_oklch(fill)[0]) <= 0.12:
            on, fill = first, darker
        else:
            on = other
    if contrast(on, fill) < 4.5:
        fill = readable(fill, [on], 4.5)
    hover = mix(fill, fg if luminance(fill) < luminance(fg) else bg, 0.16)
    if contrast(on, hover) < 4.5:
        hover = readable(hover, [on], 4.5)
    text = readable(accent, [bg, panel])
    out = {"--bg": bg, "--fg": fg, "--dim": dim, "--line": line, "--panel": panel, "--accent": fill,
           "--accent-text": text, "--accent-contrast": on, "--link": text, "--hover": hover}  # fmt: skip
    sl, sc = (0.80, 0.09) if mode == "dark" else (0.47, 0.10)
    for key, turn in TURNS.items():
        own = {"lav": roles.get("tertiary"), "sand": roles.get("secondary")}.get(key)
        c = own or oklch(sl, 0.045 if key == "sand" else max(0.06, min(sc, ac + 0.02)), (ah + turn) % 360)
        out[f"--{key}"] = readable(c, [bg, panel])
    for key in ("ok", "warn", "bad"):
        c = roles.get("error") if key == "bad" and roles.get("error") else KURO[mode][f"--{key}"]
        out[f"--{key}"] = readable(c, [bg, panel])
    return out


def failures(v: dict[str, str]) -> list[str]:
    """Text colours that don't reach AA on the backgrounds they're used on (for tests and the health check)."""
    bad = [f"{k} on {b}" for k in TEXT for b in ("bg", "panel") if contrast(v[f"--{k}"], v[f"--{b}"]) < 4.5]
    for b in ("accent", "hover"):
        if contrast(v["--accent-contrast"], v[f"--{b}"]) < 4.5:
            bad.append(f"accent-contrast on {b}")
    return bad


# ------------------------------------------------------------------------------------------- for the app
def _settings(app):
    """The App's settings, or a Settings itself (`kurooto top` reads settings without starting the App)."""
    return getattr(app, "settings", app)


def chosen(app: App) -> str:
    name = _settings(app).get("look.palette")
    return name if name in NAMES else "kuro"


def offered(app: App) -> SysColors | None:
    """This computer's colours, or your theme file's (look.theme_file) when it has some."""
    return syscolors.detect(theme_file=str(_settings(app).get("look.theme_file") or ""))


def resolve(app: App) -> tuple[str, SysColors | None]:
    """The palette in use: "system" falls back to kuro while nothing on this computer gives an accent colour."""
    name = chosen(app)
    if name != "system":
        return name, None
    found = offered(app)
    return ("system", found) if found and found.accent else ("kuro", None)


def variables(name: str, mode: str, colors: SysColors | None = None) -> dict[str, str]:
    if name == "system":
        return build(colors, mode)
    return dict(STATIC.get(name, KURO)["light" if mode == "light" else "dark"])


def current(app: App, mode: str | None = None) -> dict[str, str]:
    """The palette in use as CSS variables ({"--bg": "#0b0f0a", ...}). `mode` "dark" or "light"; by default the
    system's own mode for the system palette, else dark (like the dashboard and terminals). `app` may also be just a
    Settings (it only reads look.palette and look.theme_file)."""
    name, found = resolve(app)
    if mode not in ("dark", "light"):
        mode = found.mode if found and found.mode else "dark"
    return variables(name, mode, found)


def _block(selector: str, v: dict[str, str], mode: str) -> str:
    body = "; ".join(f"{k}: {c}" for k, c in v.items() if k in {f"--{x}" for x in KEYS} and OK_HEX.fullmatch(c))
    return f"{selector} {{ color-scheme: {mode}; {body}; }}"


def css(app: App) -> str:
    """The <style> the pages get: empty for kuro and rose (style.css has them); for system, the page's colours in the
    computer's mode (both, by the browser's setting, when the mode isn't known) and the dark dashboard's."""
    name, found = resolve(app)
    if name != "system" or not found:
        return ""
    page = ':root[data-palette="system"]'
    if found.mode:
        parts = [_block(page, build(found, found.mode), found.mode)]
    else:
        light = _block(page, build(found, "light"), "light")
        parts = [_block(page, build(found, "dark"), "dark"), f"@media (prefers-color-scheme: light) {{ {light} }}"]
    parts.append(_block('[data-palette="system"] body.home', build(found, "dark"), "dark"))
    return "\n".join(parts)


def describe(app: App) -> dict:
    """For /api/look and Settings: what's chosen, what's in use, what this computer offers, and the CSS."""
    name, found = resolve(app)
    sys_colors = offered(app)
    return {
        "chosen": chosen(app),
        "palette": name,
        "mode": found.mode if found else None,
        "system": sys_colors.to_dict() if sys_colors and sys_colors.accent else None,
        "choices": [{"id": n, "label": LABELS[n]} for n in NAMES],
        "previews": {  # a few colours of each, for the choice on the setup page
            n: {
                m: [variables(n, m, sys_colors)[f"--{k}"] for k in ("bg", "accent", "lav", "pink", "peach", "rose")]
                for m in ("dark", "light")
            }
            for n in NAMES
            if n != "system" or (sys_colors and sys_colors.accent)
        },
        "vars": current(app),
        "css": css(app),
    }


def settings_choices(app: App, section: str) -> dict:
    """For Settings → Look: the palettes with what each is, and a line on what each setting does."""
    if section != "look":
        return {}
    found = offered(app)
    system = f" (found: {found.label})" if found and found.accent else " (nothing found here yet: kuro until then)"
    return {
        "choices": {"palette": [[n, LABELS[n] + (system if n == "system" else "")] for n in NAMES]},
        "help": {
            "palette": "The colours of these pages. This computer's colours follow your desktop's accent colour and "
            "light or dark mode, and change when they do.",
            "theme_file": "Optional: a colours file of your own (a kitty theme, or matugen or pywal JSON) to use "
            "instead of the desktop's. Setting it switches the palette to this computer's colours; empty it to stop.",
        },
    }


def check(app: App, key: str, value) -> str | None:
    """What's wrong with a Look setting (None: nothing). A theme file must have colours in it, and choosing it uses
    it at once (look.palette = system); either change reads the colours afresh."""
    if key == "look.palette" and value not in NAMES:
        return f"look.palette is one of: {', '.join(NAMES)}"
    if key == "look.theme_file" and value:
        if not isinstance(value, str):
            return "look.theme_file is the path of a file"
        if not syscolors.from_file(value):
            return (f"Kurooto can't find colours in {value}: give the full path of a kitty theme (lines like "
                    "'background #1a1110'), or a matugen or pywal colours.json.")  # fmt: skip
        app.settings.set("look.palette", "system")
    syscolors.forget()
    return None
