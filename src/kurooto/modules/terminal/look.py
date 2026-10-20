"""Kurooto Terminal's colours: the dashboard's palette (Settings → look.palette) turned into a terminal colour scheme
for kitty and Windows Terminal, and the look of the chat tab (`kurooto ask`): the spaced name, a few examples and the
`kurooto ❯` prompt.

The palette is read from the dashboard's own style sheet (web/static/style.css), so a new palette there reaches the
terminal too. Terminals are always dark, like the dashboard.
"""

from __future__ import annotations

import os
import re
import sys
from importlib import resources

# the dashboard's default palette ("kuro", dark): used when the style sheet can't be read
KURO = {
    "bg": "#0b0f0a",
    "fg": "#dad3c8",
    "dim": "#95a682",
    "line": "#26311f",
    "panel": "#151b12",
    "accent": "#6b8a42",
    "accent-text": "#a6c07a",
    "accent-contrast": "#0a0e08",
    "link": "#a6c07a",
    "hover": "#7e9a52",
    "lav": "#8dbdb3",
    "pink": "#d6967a",
    "peach": "#ddb866",
    "sand": "#e4d8b4",
    "rose": "#b9a6cc",
    "ok": "#8ccb98",
    "warn": "#e2b550",
    "bad": "#e8735a",
}
TOKEN = re.compile(r"--([a-z-]+)\s*:\s*(#[0-9a-fA-F]{6})\b")
BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
MEDIA = re.compile(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")


# ----------------------------------------------------------------------------------------------- the palette
def stylesheet() -> str:
    try:
        return resources.files("kurooto.web").joinpath("static", "style.css").read_text(encoding="utf-8")
    except (OSError, ModuleNotFoundError):
        return ""


def palette(name: str = "kuro", css: str | None = None) -> dict[str, str]:
    """The palette's dark colours by token name (bg, fg, accent, lav, ...). Unknown names give the default."""
    css = stylesheet() if css is None else css
    css = MEDIA.sub("", re.sub(r"/\*.*?\*/", "", css, flags=re.S))  # light-mode variants and comments out
    base, named = dict(KURO), {}
    for selector, body in BLOCK.findall(css):
        tokens = dict(TOKEN.findall(body))
        if not tokens:
            continue
        if ":root" in selector and "data-palette" not in selector:
            base.update(tokens)
        elif f'data-palette="{name}"' in selector:
            named.update(tokens)
    return {**base, **named}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """a moved t of the way towards b."""
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    return "#{:02x}{:02x}{:02x}".format(*(round(x + (y - x) * t) for x, y in ((r1, r2), (g1, g2), (b1, b2))))


def scheme(p: dict[str, str]) -> dict[str, str]:
    """The 16 terminal colours and the rest, from a palette. Red, green and yellow keep their meaning (errors,
    success, warnings); the other hues are the palette's own secondary colours."""
    base = [p["line"], p["bad"], p["ok"], p["warn"], p["rose"], p["pink"], p["lav"], p["fg"]]
    bright = [p["dim"], *(mix(c, "#ffffff", 0.22) for c in base[1:7]), p["sand"]]
    out = {f"color{i}": c for i, c in enumerate(base + bright)}
    out.update(
        background=p["bg"],
        foreground=p["fg"],
        cursor=p["accent-text"],
        cursor_text=p["bg"],
        selection_background=p["accent"],
        selection_foreground=p["accent-contrast"],
        url=p["link"],
        tab_bar_background=p["bg"],
        active_tab_background=p["accent"],
        active_tab_foreground=p["accent-contrast"],
        inactive_tab_background=p["panel"],
        inactive_tab_foreground=p["dim"],
        active_border_color=p["accent"],
        inactive_border_color=p["line"],
    )
    return out


def colours(palette_name: str = "kuro", css: str | None = None) -> dict[str, str]:
    return scheme(palette(palette_name, css))


def kitty_theme(c: dict[str, str]) -> str:
    keys = [
        "foreground",
        "background",
        "cursor",
        "cursor_text_color",
        "selection_foreground",
        "selection_background",
        "url_color",
        "tab_bar_background",
        "active_tab_foreground",
        "active_tab_background",
        "inactive_tab_foreground",
        "inactive_tab_background",
        "active_border_color",
        "inactive_border_color",
    ]
    alias = {"cursor_text_color": "cursor_text", "url_color": "url"}
    lines = [f"{k:<24}{c[alias.get(k, k)]}" for k in keys]
    lines += [f"{f'color{i}':<24}{c[f'color{i}']}" for i in range(16)]
    return "\n".join(lines) + "\n"


WT_NAMES = ["black", "red", "green", "yellow", "blue", "purple", "cyan", "white"]


def wt_scheme(c: dict[str, str], name: str = "Kurooto") -> dict[str, str]:
    """A Windows Terminal colour scheme (every colour is required in a fragment)."""
    out = {
        "name": name,
        "background": c["background"],
        "foreground": c["foreground"],
        "cursorColor": c["cursor"],
        "selectionBackground": c["selection_background"],
    }
    for i, n in enumerate(WT_NAMES):
        out[n] = c[f"color{i}"]
        out["bright" + n[0].upper() + n[1:]] = c[f"color{i + 8}"]
    return out


# ------------------------------------------------------------------------------------------- the chat tab
EXAMPLES = ('"remind me at 6 to stretch"', '"what\'s due this week?"', '"no calls till 6"')


def _windows_ansi() -> bool:
    """Windows 10 and later: let this console understand colour codes."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


def _can(stream, text: str) -> bool:
    try:
        text.encode(getattr(stream, "encoding", None) or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


class ChatLook:
    """How `kurooto ask` looks when you type to it: in colour when the terminal can, plain text otherwise."""

    def __init__(self, p: dict[str, str], colour: bool, unicode: bool, name: str = "Kurooto", readline: bool = False):
        self.p, self.colour, self.unicode, self.readline = p, colour, unicode, readline
        self.name = (name or "Kurooto").strip() or "Kurooto"
        self.sep = " · " if unicode else " | "

    def paint(self, token: str, s: str, bold: bool = False) -> str:
        if not self.colour:
            return s
        r, g, b = _rgb(self.p[token])
        return f"\x1b[{'1;' if bold else ''}38;2;{r};{g};{b}m{s}\x1b[0m"

    def banner(self) -> str:
        spaced = " ".join(self.name.upper())
        return "\n".join(
            [
                "  " + self.paint("accent-text", spaced, True) + self.paint("dim", "   plain English, right here"),
                "  " + self.paint("dim", "quick: ") + self.paint("fg", self.sep.join(EXAMPLES)),
                "  "
                + self.paint("dim", "bigger: ")
                + self.paint("fg", "anything else goes to your AI; the answer prints here")
                + self.paint(
                    "dim", f"   (clear{self.sep}{'Ctrl-Z Enter' if sys.platform == 'win32' else 'Ctrl-D'} leaves)"
                ),
                "",
            ]
        )

    def prompt(self, for_input: bool = True) -> str:
        """The prompt. For input() with readline, the colour codes are marked as taking no room on the screen;
        for_input=False gives it as printed (to redraw it under an answer that arrived while you typed)."""
        text = f"{self.name.lower()} {'❯' if self.unicode else ')'} "
        if not self.colour:
            return text
        r, g, b = _rgb(self.p["accent-text"])
        on, off = f"\x1b[1;38;2;{r};{g};{b}m", "\x1b[0m"
        if for_input and self.readline:
            on, off = f"\001{on}\002", f"\001{off}\002"
        return on + text + off

    def done(self, text: str) -> str:
        return self.paint("pink", "✓ " if self.unicode else "ok ") + text

    def working(self) -> str:
        arrow = "→" if self.unicode else "->"
        return self.paint("peach", f"{arrow} working on it") + self.paint("dim", "; the answer prints here")

    def answer(self, request: str, ok: bool | None, text: str) -> str:
        rule = "──" if self.unicode else "--"
        tail = "" if ok else " (failed)" if ok is False else " (no answer yet)"
        head = self.paint("lav" if ok else "bad", f"{rule} {request[:60]}{tail}", True)
        return f"{head}\n{text}\n{self.paint('dim', rule)}"


def chat_look(stream=None, readline: bool = False) -> ChatLook:
    """The chat look for this terminal: Kurooto's palette and name from your settings, colour only on a real
    terminal (NO_COLOR=1 turns it off)."""
    stream = stream or sys.stdout
    name, pal = "Kurooto", "kuro"
    try:
        from kurooto.core.config import Settings
        from kurooto.core.paths import paths

        s = Settings(paths().config / "settings.json")
        name, pal = s.get("you.assistant_name") or name, s.get("look.palette") or pal
    except Exception:
        pass
    colour = bool(getattr(stream, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR") and _windows_ansi()
    return ChatLook(palette(pal), colour, _can(stream, "❯·✓→─"), name, readline)
