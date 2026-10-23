"""Named colour themes for look.palette, with each project's official names and colours (core/palette.py turns them
into the pages' CSS variables and checks every text colour reaches WCAG AA).

A theme is a family (Catppuccin) and one of its dark flavours (Mocha): the dashboard and the terminals, always dark,
use the dark flavour; the pages that follow light or dark mode use the family's light flavour in light mode. The
setting's value is the theme's id (catppuccin-mocha; a family with one dark flavour has its own name: gruvbox).

Every flavour keeps its palette exactly as published (`colours`: the project's own colour names and hex values) and
says which of them plays each of Kurooto's roles (`roles`). Nothing here is approximated; where an official colour
doesn't reach 4.5:1 on its background, palette.py moves it (lighter on dark pages, darker on light ones) just enough,
and palette.adjusted() lists every such move (docs/wiki/dev/core.md has the list).

Sources (all fetched from the projects' own repositories; colour values as published there):
  Catppuccin   https://github.com/catppuccin/palette (palette.json)                              MIT
  Tokyo Night  https://github.com/folke/tokyonight.nvim (lua/tokyonight/colors/*.lua;             Apache-2.0
               Day from extras/lua/tokyonight_day.lua, which the project generates)
  Rosé Pine    https://github.com/rose-pine/palette (palette.json, dist/css/rose-pine.css)       MIT
  Gruvbox      https://github.com/morhetz/gruvbox (colors/gruvbox.vim)                           MIT/X11
  Nord         https://github.com/nordtheme/nord (src/nord.css; light per Nord's own guidance:    MIT
               Snow Storm backgrounds, Polar Night text, for "bright ambiance designs")
  Dracula      https://github.com/dracula/dracula-theme (README: Dracula and Alucard palettes)   MIT
  Everforest   https://github.com/sainnhe/everforest (palette.md; the medium backgrounds)        MIT
  Kanagawa     https://github.com/rebelot/kanagawa.nvim (lua/kanagawa/colors.lua, themes.lua)    MIT
  Solarized    https://ethanschoonover.com/solarized, https://github.com/altercation/solarized   MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The palettes stay laid out as published, a line of names and colours at a time (no reformatting until "fmt: on").
# fmt: off

# Kurooto's roles (palette.KEYS without accent-contrast and hover, which palette.py works out from the accent)
ROLES = ("bg", "panel", "line", "fg", "dim", "accent", "accent-text", "link", "lav", "pink", "peach", "sand", "rose",
         "ok", "warn", "bad")


@dataclass(frozen=True)
class Flavour:
    id: str
    name: str  # as the project spells it
    family: str
    mode: str  # "dark" or "light"
    colours: dict[str, str]  # the official palette: the project's names -> "#rrggbb"
    roles: dict[str, str]  # Kurooto's role -> a name in `colours`; "on" (optional): text on the accent
    short: str = ""  # the name in "light mode: ..." (Latte), when it's shorter than `name`


@dataclass(frozen=True)
class Family:
    id: str
    name: str
    url: str
    licence: str
    dark: tuple[str, ...]  # flavour ids; each is a theme
    light: str
    note: str = ""
    theme_ids: dict[str, str] = field(default_factory=dict)  # dark flavour id -> theme id, where they differ


def _h(s: str) -> dict[str, str]:
    """'name=#hex name=#hex ...' (as published) -> {name: '#hex'} in lower case."""
    return {k: v.lower() for k, v in (p.split("=") for p in s.split())}


# ------------------------------------------------------------------------------------------------ Catppuccin
_CTP = {
    "latte": _h("rosewater=#dc8a78 flamingo=#dd7878 pink=#ea76cb mauve=#8839ef red=#d20f39 maroon=#e64553 "
                "peach=#fe640b yellow=#df8e1d green=#40a02b teal=#179299 sky=#04a5e5 sapphire=#209fb5 blue=#1e66f5 "
                "lavender=#7287fd text=#4c4f69 subtext1=#5c5f77 subtext0=#6c6f85 overlay2=#7c7f93 overlay1=#8c8fa1 "
                "overlay0=#9ca0b0 surface2=#acb0be surface1=#bcc0cc surface0=#ccd0da base=#eff1f5 mantle=#e6e9ef "
                "crust=#dce0e8"),
    "frappe": _h("rosewater=#f2d5cf flamingo=#eebebe pink=#f4b8e4 mauve=#ca9ee6 red=#e78284 maroon=#ea999c "
                 "peach=#ef9f76 yellow=#e5c890 green=#a6d189 teal=#81c8be sky=#99d1db sapphire=#85c1dc blue=#8caaee "
                 "lavender=#babbf1 text=#c6d0f5 subtext1=#b5bfe2 subtext0=#a5adce overlay2=#949cbb "
                 "overlay1=#838ba7 overlay0=#737994 surface2=#626880 surface1=#51576d surface0=#414559 base=#303446 "
                 "mantle=#292c3c crust=#232634"),
    "macchiato": _h("rosewater=#f4dbd6 flamingo=#f0c6c6 pink=#f5bde6 mauve=#c6a0f6 red=#ed8796 maroon=#ee99a0 "
                    "peach=#f5a97f yellow=#eed49f green=#a6da95 teal=#8bd5ca sky=#91d7e3 sapphire=#7dc4e4 "
                    "blue=#8aadf4 lavender=#b7bdf8 text=#cad3f5 subtext1=#b8c0e0 subtext0=#a5adcb overlay2=#939ab7 "
                    "overlay1=#8087a2 overlay0=#6e738d surface2=#5b6078 surface1=#494d64 surface0=#363a4f "
                    "base=#24273a mantle=#1e2030 crust=#181926"),
    "mocha": _h("rosewater=#f5e0dc flamingo=#f2cdcd pink=#f5c2e7 mauve=#cba6f7 red=#f38ba8 maroon=#eba0ac "
                "peach=#fab387 yellow=#f9e2af green=#a6e3a1 teal=#94e2d5 sky=#89dceb sapphire=#74c7ec blue=#89b4fa "
                "lavender=#b4befe text=#cdd6f4 subtext1=#bac2de subtext0=#a6adc8 overlay2=#9399b2 overlay1=#7f849c "
                "overlay0=#6c7086 surface2=#585b70 surface1=#45475a surface0=#313244 base=#1e1e2e mantle=#181825 "
                "crust=#11111b"),
}
# Catppuccin's style guide: base the background, mantle and crust secondary panes, text and subtext for text
_CTP_ROLES = {"bg": "base", "panel": "mantle", "line": "surface0", "fg": "text", "dim": "subtext0", "accent": "mauve",
              "accent-text": "mauve", "link": "blue", "lav": "lavender", "pink": "pink", "peach": "peach",
              "sand": "rosewater", "rose": "flamingo", "ok": "green", "warn": "yellow", "bad": "red",
              "on": "crust"}

# ------------------------------------------------------------------------------------------------ Tokyo Night
_TN_STORM = _h("bg=#24283b bg_dark=#1f2335 bg_dark1=#1b1e2d bg_highlight=#292e42 blue=#7aa2f7 blue0=#3d59a1 "
               "blue1=#2ac3de blue2=#0db9d7 blue5=#89ddff blue6=#b4f9f8 blue7=#394b70 comment=#565f89 cyan=#7dcfff "
               "dark3=#545c7e dark5=#737aa2 fg=#c0caf5 fg_dark=#a9b1d6 fg_gutter=#3b4261 green=#9ece6a "
               "green1=#73daca green2=#41a6b5 magenta=#bb9af7 magenta2=#ff007c orange=#ff9e64 purple=#9d7cd8 "
               "red=#f7768e red1=#db4b4b teal=#1abc9c terminal_black=#414868 yellow=#e0af68")
_TN = {
    "storm": _TN_STORM,
    "night": {**_TN_STORM, **_h("bg=#1a1b26 bg_dark=#16161e bg_dark1=#0C0E14")},  # night.lua: storm, darker
    "moon": _h("bg=#222436 bg_dark=#1e2030 bg_dark1=#191B29 bg_highlight=#2f334d blue=#82aaff blue0=#3e68d7 "
               "blue1=#65bcff blue2=#0db9d7 blue5=#89ddff blue6=#b4f9f8 blue7=#394b70 comment=#636da6 cyan=#86e1fc "
               "dark3=#545c7e dark5=#737aa2 fg=#c8d3f5 fg_dark=#828bb8 fg_gutter=#3b4261 green=#c3e88d "
               "green1=#4fd6be green2=#41a6b5 magenta=#c099ff magenta2=#ff007c orange=#ff966c purple=#fca7ea "
               "red=#ff757f red1=#c53b53 teal=#4fd6be terminal_black=#444a73 yellow=#ffc777"),
    "day": _h("bg=#e1e2e7 bg_dark=#d0d5e3 bg_dark1=#c1c9df bg_highlight=#c4c8da blue=#2e7de9 blue0=#7890dd "
              "blue1=#188092 blue2=#07879d blue5=#006a83 blue6=#2e5857 blue7=#92a6d5 comment=#848cb5 cyan=#007197 "
              "dark3=#8990b3 dark5=#68709a fg=#3760bf fg_dark=#6172b0 fg_gutter=#a8aecb green=#587539 "
              "green1=#387068 green2=#38919f magenta=#9854f1 magenta2=#d20065 orange=#b15c00 purple=#7847bd "
              "red=#f52a65 red1=#c64343 teal=#118c74 terminal_black=#a1a6c5 yellow=#8c6c3e"),
}
_TN_ROLES = {"bg": "bg", "panel": "bg_dark", "line": "fg_gutter", "fg": "fg", "dim": "fg_dark", "accent": "blue",
             "accent-text": "blue", "link": "cyan", "lav": "magenta", "pink": "purple", "peach": "orange",
             "sand": "yellow", "rose": "green1", "ok": "green", "warn": "yellow", "bad": "red", "on": "bg_dark"}

# ------------------------------------------------------------------------------------------------ Rosé Pine
_RP = {
    "main": _h("base=#191724 surface=#1f1d2e overlay=#26233a muted=#6e6a86 subtle=#908caa text=#e0def4 love=#eb6f92 "
               "gold=#f6c177 rose=#ebbcba pine=#31748f foam=#9ccfd8 iris=#c4a7e7 highlight_low=#21202e "
               "highlight_med=#403d52 highlight_high=#524f67"),
    "moon": _h("base=#232136 surface=#2a273f overlay=#393552 muted=#6e6a86 subtle=#908caa text=#e0def4 love=#eb6f92 "
               "gold=#f6c177 rose=#ea9a97 pine=#3e8fb0 foam=#9ccfd8 iris=#c4a7e7 highlight_low=#2a283e "
               "highlight_med=#44415a highlight_high=#56526e"),
    "dawn": _h("base=#faf4ed surface=#fffaf3 overlay=#f2e9e1 muted=#9893a5 subtle=#797593 text=#464261 love=#b4637a "
               "gold=#ea9d34 rose=#d7827e pine=#286983 foam=#56949f iris=#907aa9 highlight_low=#f4ede8 "
               "highlight_med=#dfdad9 highlight_high=#cecacd"),
}
# Rosé Pine's roles: love errors, gold warnings, foam git additions, iris inline links; pine is the terminal green
_RP_ROLES = {"bg": "base", "panel": "surface", "line": "highlight_med", "fg": "text", "dim": "subtle", "accent": "rose",
             "accent-text": "rose", "link": "iris", "lav": "foam", "pink": "love", "peach": "gold", "sand": "rose",
             "rose": "iris", "ok": "foam", "warn": "gold", "bad": "love", "on": "base"}

# ------------------------------------------------------------------------------------------------ Gruvbox
_GB = _h("dark0_hard=#1d2021 dark0=#282828 dark0_soft=#32302f dark1=#3c3836 dark2=#504945 dark3=#665c54 "
         "dark4=#7c6f64 gray=#928374 light0_hard=#f9f5d7 light0=#fbf1c7 light0_soft=#f2e5bc light1=#ebdbb2 "
         "light2=#d5c4a1 light3=#bdae93 light4=#a89984 bright_red=#fb4934 bright_green=#b8bb26 "
         "bright_yellow=#fabd2f bright_blue=#83a598 bright_purple=#d3869b bright_aqua=#8ec07c bright_orange=#fe8019 "
         "neutral_red=#cc241d neutral_green=#98971a neutral_yellow=#d79921 neutral_blue=#458588 "
         "neutral_purple=#b16286 neutral_aqua=#689d6a neutral_orange=#d65d0e faded_red=#9d0006 faded_green=#79740e "
         "faded_yellow=#b57614 faded_blue=#076678 faded_purple=#8f3f71 faded_aqua=#427b58 faded_orange=#af3a03")
# gruvbox.vim: dark mode is bg0 dark0, fg1 light1 and the bright colours; light mode bg0 light0, fg1 dark1, faded
_GB_DARK = {"bg": "dark0", "panel": "dark0_hard", "line": "dark2", "fg": "light1", "dim": "light4",
            "accent": "bright_yellow", "accent-text": "bright_yellow", "link": "bright_blue", "lav": "bright_blue",
            "pink": "bright_purple", "peach": "bright_orange", "sand": "light2", "rose": "bright_aqua",
            "ok": "bright_green", "warn": "bright_yellow", "bad": "bright_red", "on": "dark0"}
_GB_LIGHT = {"bg": "light0", "panel": "light0_hard", "line": "light2", "fg": "dark1", "dim": "dark4",
             "accent": "faded_yellow", "accent-text": "faded_yellow", "link": "faded_blue", "lav": "faded_blue",
             "pink": "faded_purple", "peach": "faded_orange", "sand": "dark2", "rose": "faded_aqua",
             "ok": "faded_green", "warn": "faded_yellow", "bad": "faded_red", "on": "light0"}

# ------------------------------------------------------------------------------------------------ Nord
_NORD = _h("nord0=#2e3440 nord1=#3b4252 nord2=#434c5e nord3=#4c566a nord4=#d8dee9 nord5=#e5e9f0 nord6=#eceff4 "
           "nord7=#8fbcbb nord8=#88c0d0 nord9=#81a1c1 nord10=#5e81ac nord11=#bf616a nord12=#d08770 nord13=#ebcb8b "
           "nord14=#a3be8c nord15=#b48ead")
# Polar Night (nord0-3) backgrounds, Snow Storm (nord4-6) text, Frost (nord7-10) the accents (nord8 the primary one,
# also the links: nord9 doesn't reach AA on nord1), Aurora (nord11-15) red, orange, yellow, green, purple; bright
# ambiance designs swap Polar Night and Snow Storm
_NORD_DARK = {"bg": "nord0", "panel": "nord1", "line": "nord3", "fg": "nord6", "dim": "nord4", "accent": "nord8",
              "accent-text": "nord8", "link": "nord8", "lav": "nord7", "pink": "nord15", "peach": "nord12",
              "sand": "nord13", "rose": "nord9", "ok": "nord14", "warn": "nord13", "bad": "nord11", "on": "nord0"}
_NORD_LIGHT = {"bg": "nord6", "panel": "nord5", "line": "nord4", "fg": "nord0", "dim": "nord3", "accent": "nord10",
               "accent-text": "nord10", "link": "nord10", "lav": "nord10", "pink": "nord15", "peach": "nord12",
               "sand": "nord3", "rose": "nord9", "ok": "nord14", "warn": "nord13", "bad": "nord11", "on": "nord6"}

# ------------------------------------------------------------------------------------------------ Dracula
_DRACULA = _h("background=#282a36 current_line=#44475a selection=#44475a foreground=#f8f8f2 comment=#6272a4 "
              "cyan=#8be9fd green=#50fa7b orange=#ffb86c pink=#ff79c6 purple=#bd93f9 red=#ff5555 yellow=#f1fa8c")
_ALUCARD = _h("background=#fffbeb current_line=#6c664b selection=#cfcfde foreground=#1f1f1f comment=#6c664b "
              "cyan=#036a96 green=#14710a orange=#a34d14 pink=#a3144d purple=#644ac9 red=#cb3a2a yellow=#846e15")
# Dracula has one background: panes are drawn on it and set apart by lines (Current Line / Selection)
_DRACULA_ROLES = {"bg": "background", "panel": "background", "line": "current_line", "fg": "foreground",
                  "dim": "comment", "accent": "purple", "accent-text": "purple", "link": "cyan", "lav": "cyan",
                  "pink": "pink", "peach": "orange", "sand": "yellow", "rose": "purple", "ok": "green",
                  "warn": "orange", "bad": "red", "on": "background"}
_ALUCARD_ROLES = {**_DRACULA_ROLES, "line": "selection"}

# ------------------------------------------------------------------------------------------------ Everforest
_EF_DARK = _h("bg_dim=#232A2E bg0=#2D353B bg1=#343F44 bg2=#3D484D bg3=#475258 bg4=#4F585E bg5=#56635f "
              "fg=#D3C6AA red=#E67E80 orange=#E69875 yellow=#DBBC7F green=#A7C080 aqua=#83C092 blue=#7FBBB3 "
              "purple=#D699B6 grey0=#7A8478 grey1=#859289 grey2=#9DA9A0")
_EF_LIGHT = _h("bg_dim=#EFEBD4 bg0=#FDF6E3 bg1=#F4F0D9 bg2=#EFEBD4 bg3=#E6E2CC bg4=#E0DCC7 bg5=#BDC3AF "
               "fg=#5C6A72 red=#F85552 orange=#F57D26 yellow=#DFA000 green=#8DA101 aqua=#35A77C blue=#3A94C5 "
               "purple=#DF69BA grey0=#A6B0A0 grey1=#939F91 grey2=#829181")
_EF_ROLES = {"bg": "bg0", "panel": "bg_dim", "line": "bg4", "fg": "fg", "dim": "grey2", "accent": "green",
             "accent-text": "green", "link": "blue", "lav": "blue", "pink": "purple", "peach": "orange",
             "sand": "yellow", "rose": "aqua", "ok": "green", "warn": "yellow", "bad": "red", "on": "bg0"}

# ------------------------------------------------------------------------------------------------ Kanagawa
# (colors.lua's palette; themes.lua says which colour each theme uses for what: ui.bg, ui.fg, syn.fun, diag.ok, ...)
_KANAGAWA = _h("sumiInk2=#1a1a22 sumiInk3=#1F1F28 sumiInk4=#2A2A37 sumiInk5=#363646 sumiInk6=#54546D "
               "oldWhite=#C8C093 fujiWhite=#DCD7BA samuraiRed=#E82424 roninYellow=#FF9E3B oniViolet=#957FB8 "
               "crystalBlue=#7E9CD8 springBlue=#7FB4CA waveAqua2=#7AA89F springGreen=#98BB6C carpYellow=#E6C384 "
               "sakuraPink=#D27E99 waveRed=#E46876 peachRed=#FF5D62 surimiOrange=#FFA066 dragonBlack2=#1D1C19 "
               "dragonBlack3=#181616 dragonBlack4=#282727 dragonBlack5=#393836 dragonBlack6=#625e5a "
               "dragonWhite=#c5c9c5 dragonPink=#a292a3 dragonOrange=#b6927b dragonBlue2=#8ba4b0 dragonViolet=#8992a7 "
               "dragonRed=#c4746e dragonAqua=#8ea4a2 dragonTeal=#949fb5 dragonYellow=#c4b28a lotusInk1=#545464 "
               "lotusInk2=#43436c lotusGray2=#716e61 lotusWhite2=#e5ddb0 lotusWhite3=#f2ecbc lotusWhite4=#e7dba0 "
               "lotusViolet1=#a09cac lotusViolet4=#624c83 lotusBlue4=#4d699b lotusTeal2=#6693bf lotusGreen=#6f894e "
               "lotusPink=#b35b79 lotusOrange=#cc6d00 lotusOrange2=#e98a00 lotusYellow=#77713f lotusAqua=#597b75 "
               "lotusRed3=#e82424")
# fun the accent, special1 links, statement lav, number pink, constant peach, identifier sand, type rose, diag.ok
# and diag.warning; errors in peachRed (special3), as diag.error's samuraiRed doesn't reach AA on the panes
_KG_WAVE = {"bg": "sumiInk3", "panel": "sumiInk4", "line": "sumiInk6", "fg": "fujiWhite", "dim": "oldWhite",
            "accent": "crystalBlue", "accent-text": "crystalBlue", "link": "springBlue", "lav": "oniViolet",
            "pink": "sakuraPink", "peach": "surimiOrange", "sand": "carpYellow", "rose": "waveAqua2",
            "ok": "springGreen", "warn": "roninYellow", "bad": "peachRed", "on": "sumiInk3"}
_KG_DRAGON = {"bg": "dragonBlack3", "panel": "dragonBlack4", "line": "dragonBlack6", "fg": "dragonWhite",
              "dim": "oldWhite", "accent": "dragonBlue2", "accent-text": "dragonBlue2", "link": "dragonTeal",
              "lav": "dragonViolet", "pink": "dragonPink", "peach": "dragonOrange", "sand": "dragonYellow",
              "rose": "dragonAqua", "ok": "springGreen", "warn": "roninYellow", "bad": "peachRed",
              "on": "dragonBlack3"}
# lotus: its fg_dim (lotusInk2) is darker than its fg, so the dim text is lotusGray2, its own muted grey
_KG_LOTUS = {"bg": "lotusWhite3", "panel": "lotusWhite2", "line": "lotusViolet1", "fg": "lotusInk1",
             "dim": "lotusGray2", "accent": "lotusBlue4", "accent-text": "lotusBlue4", "link": "lotusTeal2",
             "lav": "lotusViolet4", "pink": "lotusPink", "peach": "lotusOrange", "sand": "lotusYellow",
             "rose": "lotusAqua", "ok": "lotusGreen", "warn": "lotusOrange2", "bad": "lotusRed3",
             "on": "lotusWhite3"}

# ------------------------------------------------------------------------------------------------ Solarized
_SOL = _h("base03=#002b36 base02=#073642 base01=#586e75 base00=#657b83 base0=#839496 base1=#93a1a1 base2=#eee8d5 "
          "base3=#fdf6e3 yellow=#b58900 orange=#cb4b16 red=#dc322f magenta=#d33682 violet=#6c71c4 blue=#268bd2 "
          "cyan=#2aa198 green=#859900")
# dark: base03 background, base02 highlights, base0 body text, base1 emphasized; light: base3, base2, base00, base01.
# Body text doesn't reach AA on the highlights (base02, base2): text is the emphasized tone, dim the body tone.
_SOL_DARK = {"bg": "base03", "panel": "base02", "line": "base01", "fg": "base1", "dim": "base0", "accent": "blue",
             "accent-text": "blue", "link": "blue", "lav": "violet", "pink": "magenta", "peach": "orange",
             "sand": "yellow", "rose": "cyan", "ok": "green", "warn": "yellow", "bad": "red", "on": "base03"}
_SOL_LIGHT = {**_SOL_DARK, "bg": "base3", "panel": "base2", "line": "base1", "fg": "base01", "dim": "base00",
              "on": "base3"}


# ------------------------------------------------------------------------------------------------ the table
def _f(fid, name, family, mode, colours, roles, short=""):
    return Flavour(fid, name, family, mode, colours, roles, short)


FLAVOURS: dict[str, Flavour] = {f.id: f for f in (
    _f("catppuccin-mocha", "Catppuccin Mocha", "catppuccin", "dark", _CTP["mocha"], _CTP_ROLES),
    _f("catppuccin-macchiato", "Catppuccin Macchiato", "catppuccin", "dark", _CTP["macchiato"], _CTP_ROLES),
    _f("catppuccin-frappe", "Catppuccin Frappé", "catppuccin", "dark", _CTP["frappe"], _CTP_ROLES),
    _f("catppuccin-latte", "Catppuccin Latte", "catppuccin", "light", _CTP["latte"], _CTP_ROLES, "Latte"),
    _f("tokyonight-night", "Tokyo Night", "tokyonight", "dark", _TN["night"], _TN_ROLES),
    _f("tokyonight-storm", "Tokyo Night Storm", "tokyonight", "dark", _TN["storm"], _TN_ROLES),
    _f("tokyonight-moon", "Tokyo Night Moon", "tokyonight", "dark", _TN["moon"], _TN_ROLES),
    _f("tokyonight-day", "Tokyo Night Day", "tokyonight", "light", _TN["day"], _TN_ROLES, "Day"),
    _f("rose-pine", "Rosé Pine", "rose-pine", "dark", _RP["main"], _RP_ROLES),
    _f("rose-pine-moon", "Rosé Pine Moon", "rose-pine", "dark", _RP["moon"], _RP_ROLES),
    # Dawn's foam doesn't reach AA on its base; pine (Rosé Pine's terminal green) does
    _f("rose-pine-dawn", "Rosé Pine Dawn", "rose-pine", "light", _RP["dawn"], {**_RP_ROLES, "ok": "pine"}, "Dawn"),
    _f("gruvbox-dark", "Gruvbox Dark", "gruvbox", "dark", _GB, _GB_DARK),
    _f("gruvbox-light", "Gruvbox Light", "gruvbox", "light", _GB, _GB_LIGHT),
    _f("nord", "Nord", "nord", "dark", _NORD, _NORD_DARK),
    _f("nord-light", "Nord Light", "nord", "light", _NORD, _NORD_LIGHT),
    _f("dracula", "Dracula", "dracula", "dark", _DRACULA, _DRACULA_ROLES),
    _f("dracula-alucard", "Alucard", "dracula", "light", _ALUCARD, _ALUCARD_ROLES),
    _f("everforest-dark", "Everforest Dark", "everforest", "dark", _EF_DARK, _EF_ROLES),
    _f("everforest-light", "Everforest Light", "everforest", "light", _EF_LIGHT, _EF_ROLES),
    _f("kanagawa-wave", "Kanagawa Wave", "kanagawa", "dark", _KANAGAWA, _KG_WAVE),
    _f("kanagawa-dragon", "Kanagawa Dragon", "kanagawa", "dark", _KANAGAWA, _KG_DRAGON),
    _f("kanagawa-lotus", "Kanagawa Lotus", "kanagawa", "light", _KANAGAWA, _KG_LOTUS, "Lotus"),
    _f("solarized-dark", "Solarized Dark", "solarized", "dark", _SOL, _SOL_DARK),
    _f("solarized-light", "Solarized Light", "solarized", "light", _SOL, _SOL_LIGHT),
)}

FAMILIES: dict[str, Family] = {f.id: f for f in (
    Family("catppuccin", "Catppuccin", "https://github.com/catppuccin/palette", "MIT",
           ("catppuccin-mocha", "catppuccin-macchiato", "catppuccin-frappe"), "catppuccin-latte"),
    Family("tokyonight", "Tokyo Night", "https://github.com/folke/tokyonight.nvim", "Apache-2.0",
           ("tokyonight-night", "tokyonight-storm", "tokyonight-moon"), "tokyonight-day"),
    Family("rose-pine", "Rosé Pine", "https://github.com/rose-pine/palette", "MIT",
           ("rose-pine", "rose-pine-moon"), "rose-pine-dawn"),
    Family("gruvbox", "Gruvbox", "https://github.com/morhetz/gruvbox", "MIT/X11", ("gruvbox-dark",),
           "gruvbox-light", theme_ids={"gruvbox-dark": "gruvbox"}),
    Family("nord", "Nord", "https://github.com/nordtheme/nord", "MIT", ("nord",), "nord-light",
           note="Nord has one palette for dark and bright designs; its light pages follow Nord's own guidance "
           "(Snow Storm backgrounds, Polar Night text)."),
    Family("dracula", "Dracula", "https://github.com/dracula/dracula-theme", "MIT", ("dracula",),
           "dracula-alucard"),
    Family("everforest", "Everforest", "https://github.com/sainnhe/everforest", "MIT", ("everforest-dark",),
           "everforest-light", note="The medium-contrast backgrounds (Everforest's default).",
           theme_ids={"everforest-dark": "everforest"}),
    Family("kanagawa", "Kanagawa", "https://github.com/rebelot/kanagawa.nvim", "MIT",
           ("kanagawa-wave", "kanagawa-dragon"), "kanagawa-lotus"),
    Family("solarized", "Solarized", "https://ethanschoonover.com/solarized", "MIT", ("solarized-dark",),
           "solarized-light", theme_ids={"solarized-dark": "solarized"}),
)}

# fmt: on


@dataclass(frozen=True)
class Theme:
    id: str  # look.palette's value
    family: str
    dark: str  # flavour ids
    light: str

    @property
    def label(self) -> str:
        """'Catppuccin Mocha (light mode: Latte)'."""
        dark, light = FLAVOURS[self.dark], FLAVOURS[self.light]
        return f"{dark.name} (light mode: {light.short or light.name})"


THEMES: dict[str, Theme] = {
    fam.theme_ids.get(d, d): Theme(fam.theme_ids.get(d, d), fam.id, d, fam.light)
    for fam in FAMILIES.values()
    for d in fam.dark
}
