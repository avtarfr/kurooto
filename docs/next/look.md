# look: the setup page's layout and guidance, and the system palette (for the coordinator)

MANUAL ("The setup wizard", new "Colours (Look)" section, two Troubleshooting rows) and CHANGELOG ("0.2.1" and
"0.3.0" headings) are edited directly on this branch, as asked.

## 0.2.1 (cherry-pick)
- d06d2ee: setup page uses the width on desktops (setup.html, setup.js, style.css only).
- d5c144a: CHANGELOG, the 0.2.1 heading and its line.

## The palette API (for `kurooto top`, `kurooto term`, the dashboard)
- `kurooto.core.palette.current(app_or_settings, mode=None) -> dict[str, str]`: the palette in use as CSS variables
  with their `--` prefix: bg, fg, dim, line, panel, accent, accent-text, accent-contrast, link, hover, lav, pink,
  peach, sand, rose, ok, warn, bad. Every value is a checked `#rrggbb`; every text colour passes WCAG AA on bg and
  panel. `mode` "dark"/"light"; None = the computer's mode with the system palette, else dark. Takes an App or a
  plain `Settings` (it reads only look.palette and look.theme_file).
- `palette.describe(app)` (= GET /api/look), `palette.css(app)` (the pages' <style>), `palette.NAMES`,
  `palette.KURO`/`palette.ROSE` (static dicts equal to style.css; a test keeps them in sync).
- `kurooto.core.syscolors`: `read()`/`detect(theme_file=...)` -> SysColors(source, label, accent, mode, schemes);
  pure parsers `from_matugen`, `from_material_scss`, `from_pywal`, `from_kitty`, `from_kdeglobals`, `from_gnome`,
  `from_gtk`, `from_windows`, `from_macos`, `from_file`.
- Pages: `Server.fill()` puts `<style id="kurooto-palette">` and `<script src="/static/palette.js" defer>` before
  `</head>` of every filled page. palette.js asks GET /api/look every 30 s and when the tab comes back, swaps the
  colours in place and fires `window` event `kurooto:palette` (detail = the /api/look body);
  `window.kurootoLook.refresh()` asks at once. home.js should re-read its canvas colours on that event (dense agreed).

## Shared files touched
- web/server.py: `register_defaults("look", {"palette": "kuro", "theme_file": ""})`, PALETTES gains "system",
  `Server.fill()` body (palette name via palette.resolve, the style and script injection).
- web/api.py: GET `look` (4 lines after GET settings); `_settings()` adds `choices`/`help` to the look section
  (`palette.settings_choices`); `_set()` validates look.palette and look.theme_file (`palette.check`) first.
- static/style.css: the wizard block at the end (scoped to `.wizard`), and the rose palette's light text colours.
- New: core/palette.py, core/syscolors.py, static/palette.js, tests/unit/test_look.py, tests/fixtures/syscolors/*.

## Settings (dashboard, home.js: dense's)
GET /api/settings's "look" section now has `"choices": {"palette": [[id, label], ...]}` and `"help": {key: text}`;
dense will render a <select> and the help lines.
