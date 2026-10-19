# showcase: the green palette and the screenshots (for the coordinator to merge)

## MANUAL: add to "The dashboard" (or wherever Settings are described)

### Colours
Kurooto's pages (the setup page, the dashboard, the morning page, and your call line's pages on the phone) use deep
greens, like the website. If you liked the earlier pink and rose colours better, set **Settings → Look →
look.palette** to `rose` and reload the page; `kuro` brings the greens back. The setup and morning pages follow your
system's light or dark mode; the dashboard is always dark. (The call line's pages on your phone stay green.)

*Settings:* `look.palette` (default `kuro`; or `rose`).
*Leaves your computer:* nothing.

## README / website (done on this branch)
- README.md: a "Showcase" section under the status note: the Systems view as an animated WebP, the dashboard, two
  example chat screens, the setup wizard's computer step and the morning page (these two switch to their light
  versions in GitHub's light mode), and links to the rest.
- installer/index.html: the hero shows the Systems view as a looping video (muted, plays inline, a pause button,
  still for reduced motion), a "Showcase" link in the menu, and a Showcase section of screenshot cards (setup,
  morning page and features cards switch to their light versions with the page's light theme).
- docs/media/: every image and the video. tools/release.py copies it to SITE/media/ (the site's page uses
  `media/...`) and leaves it out of the release tarball.

## CHANGELOG
- Kurooto's pages are now deep green, like the website: the setup page, the dashboard (its drawings too), the morning
  page and your call line's pages and icon. The old colours stay available: Settings → Look → look.palette = rose.
- Warnings and errors have their own colours (amber and red), never the accent colour.
- The dashboard's feature ring gives every feature a short label and its own colour.
- Phone: the call page's "Waiting for you" link no longer grows to fill the screen.
- README and website: screenshots and an animation of the dashboard, from a demo with made-up data.

## PRIVACY
Nothing changes: the palette is a local setting. The screenshots come from a demo with made-up data ("Sam") and fake
services (a stand-in Telegram, a scripted AI, a local calendar file), run with its own home folder and the network
closed.

## Notes for the coordinator
- Palette tokens live in src/kurooto/web/static/style.css (`:root, body.home` = kuro dark; `[data-palette="rose"]`;
  light versions in the `prefers-color-scheme: light` block). home.js reads the canvas colours from these tokens, so
  a future palette is CSS only. Status colours: `--ok`, `--warn`, `--bad`; `--accent` fills, `--accent-text` is the
  accent as text.
- server.py: `register_defaults("look", {"palette": "kuro"})`, `PALETTES`, and `Server.fill()` (writes the key, the
  version and `data-palette` into the pages); api.py: "look" added to `EDITABLE` (one line) so Settings shows it.
- The Worker (call, pairing, inbox pages, manifest colours, icon.svg and its PNGs) is green only; it has no palette
  setting (it's deployed separately). The Android app's own colours are unchanged.
- The showcase was made with throwaway scripts (a demo instance from this worktree with tests/fakes, headless Chrome
  over CDP, a virtual clock for the seamless loop); they aren't in the repo.
