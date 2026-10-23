# The web page: setup wizard, dashboard, local API

Everything a browser, the `kurooto` CLI and `kurooto mcp` say to the running daemon goes through one local HTTP
server in `src/kurooto/web/`. There is no framework: it is the standard library's `http.server`.

The user's view: [../user/dashboard.md](../user/dashboard.md).

## The server (`web/server.py`)

- `start(app, port=None) -> Server` is called by `daemon.py:serve`. `Server.__init__` builds a
  `ThreadingHTTPServer` (`daemon_threads = True`) with a `Handler(BaseHTTPRequestHandler)` defined as a closure, and
  `Server.start` runs `serve_forever` in a thread named `web`. It binds **only** `127.0.0.1`.
- Port: `free_port(start)` tries `web.port` (default 8770) and the next 29 ports; none free raises
  `RuntimeError`. The chosen URL is written to `<state>/web.json` (`{port, url, started}`), which the CLI
  (`cli.py:wait_for_web`, `ask_running`), `top.py` and `core/aboutyou.py` read. `app.web_port` is set too (the Google
  OAuth redirect `http://127.0.0.1:<port>/oauth/google`, `modules/google.py`, and the alarm read it).
- `Server.stop()` sets `stopping`, stops `Live`, shuts the server down and deletes `<state>/tools-access.json` if it
  still holds this server's tools key.
- Every response goes through `Handler._send`, which adds `Content-Security-Policy` (constant `CSP`:
  `default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`, `form-action 'none'` ...),
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` for pages (they
  hold the key) and the API. Static files (0.6.1) get `Cache-Control: no-cache` and an `ETag` (the first 20 hex digits
  of the file's SHA-1, worked out per request), and a matching `If-None-Match` gets a bodyless 304: the browser keeps
  `home.js` (230 KB), the styles, fonts and xterm, and what it compiled of them, and asks again on each load, so an
  update's new file is never missed. Nothing is compressed: on 127.0.0.1 it would cost more than it saves. Because
  of the CSP, pages may not use inline scripts or load anything from another origin.
- Static files: `static(name)` reads them with `importlib.resources`, only names matching
  `(?:vendor/xterm/)?[a-z0-9_-]+\.(html|js|css|svg|png|ico)` or `fonts/[a-z0-9_-]+\.woff2` (served as `font/woff2`).
- `Server.fill(html)` substitutes `{{TOKEN}}`, `{{VERSION}}`, `{{PALETTE}}`, `{{LAYOUT}}`, `{{DESIGN}}` (`look.design`,
  anything but `DESIGNS` is `new`), `{{STUDY}}` and injects the
  palette style and `/static/palette.js` / `/static/links.js` before `</head>`.
- Settings registered here: `web.port`, and the `look.*` section (`palette`, `theme_file`, `layout`, `design`,
  `projects`, `panes`, `hidden_features`, `links_in`, `study_mode`). `Api._set` refuses a `look.design` that isn't
  `new` or `classic`; `core/palette.py:settings_choices` gives Settings → Look its choices and help.

## Who may call it

| Check | Where | Applies to |
|---|---|---|
| Host header must be `127.0.0.1:<port>` or `localhost:<port>` (DNS-rebinding guard) | `Handler._host_ok` | every GET and POST |
| Same OS account (Linux only: owner of the client socket from `/proc/net/tcp{,6}`, must be this uid or root; unknown is refused) | `web/peer.py:same_user`, `peer_uid` | every request except `/health` and `/static/*` |
| Page token in header `X-Kurooto`, compared in constant time (`compare_digest`); `Origin` absent or one of the allowed hosts | `Handler._authed` | every `/api/*` |
| Tools-only key in header `X-Kurooto-Tools`, no Origin, and only `/api/tools` and `/api/tools/call` (`TOOLS_ONLY`) | `Handler._tools_authed` | `kurooto mcp` |

- The page token is the secret `web.token` (created with `secrets.token_urlsafe(24)` on first start, kept in the
  keychain or `secrets.json`, so it survives restarts). It is embedded in each served page as
  `<meta name="kurooto-token">`; the JS sends it as `X-Kurooto`. The CLI reads the same secret directly
  (`cli.py:ask_running`).
- The tools key is new at every start and written to `<state>/tools-access.json` (`core/mcp.py:access_file`).
- There is no CSRF token: a cross-site page cannot set the custom header without a CORS preflight, which is never
  answered; the Origin check and `form-action 'none'` back that up.
- Failures: GET without auth 401 `{"error":"no"}`; wrong Host 403; another account 403; any POST auth failure 403;
  body over 4 000 000 bytes 413; a non-numeric or negative `Content-Length` 400; bad JSON 400.
- Unauthenticated by design: `/health` (`{ok, version}`), `/static/*`, and `/oauth/google` (Host and same-user checked,
  plus the one-time OAuth `state`).

## Routes

Non-API routes (`Handler.do_GET`): `/` (the wizard until the setting `setup.done`, then the dashboard), `/setup`,
`/morning`, `/confidential` (local mail summaries), `/static/<name>`, `/oauth/google`, `/health`, and `/api/stream`
(SSE; the token comes as `?t=` because `EventSource` can't send headers).

API routes: `Handler` strips `/api/` and calls `web/api.py:Api.get(path, q)` or `Api.post(path, body)`, which both
return `(status, dict)`. Each first delegates paths listed in `web/tools_api.py:GETS` / `POSTS`. Query strings are
flattened to their first value; a non-dict JSON body becomes `{}`. Anything unmatched is 404.

GET (in `Api.get`): `tools`, `job?id=`, `usage?days=` (tools_api); `addons` (the add-ons by link: `linked` rows with their card and text, `kept` for Undo, `official`: the official list with what you have of each), `jobs`, `term`, `health`, `sync/status`,
`profile`, `note?id=`, `settings`, `look`, `events` (last 80), `board` (503 without `Live`), `state` (the wizard's
whole state, with `setup` and `calm` below), `setup` (`core/setupsteps.py:view`: each step's status, `resume`, `left`), `phone`, `power`, `aboutyou/profile`, `aboutyou?source=`, `persona`, `research`, `progress`, `ask`, `ask/<id>`,
`today` (`core/actions.py:today`), `study?subject=` (`core/actions.py:study_view`), `morning`
(`modules/daily.py:morning_view`), `mail/confidential?day=`, `books`, `notes/fit?folder=` (`core/notesfit.py:view`: the proposal for that folder or the notes
folder, `in_use`, `presets`, the move to `undo`).

POST (in `Api.post`):

| Area | Paths |
|---|---|
| tools_api | `tools/call`, `say`, `job`, `call`, `call/list`, `call/cancel` |
| AI | `brain`, `brain/test`, `brain/models`, `jobs/cancel`, `tryit` |
| features | `modules/enable`, `modules/disable`, `modules/setup`, `modules/configure`, `modules/card` |
| add-ons by link | `addons/look` (`{url, ref}`: clone and the card, `{token, card, text}`; `{official: name}`: an official add-on's, at its pinned commit), `addons/add` and `addons/update` (`{token, code}`: `code` true is the "I trust this code" box, needed when it runs code), `addons/check` (`{name}`: a newer commit's card and `changes_text`, or `same`), `addons/drop`, `addons/remove`, `addons/undo` (`{name}`), `addons/reload` (`kurooto addons` after its change); each change reloads them (`overlay.reload_linked`) and returns `modules` |
| settings and you | `settings`, `you`, `autostart`, `hardware/refresh`, `hardware/override`, `keys/gemini` |
| setup | `prereqs/install`, `prereqs/signin`, `telegram/token`, `telegram/poll`, `telegram/relink`, `telegram/webhook-off`, `setup/channel` (`{"channel": "telegram" \| "app"}` into `setup.channel`; `GET state` returns it as `channel`), `setup/step` (`{step, how: next\|skip\|leave, seconds, chosen}`; 400 for an unknown step or skipping a required one), `setup/done`, `notes/fit/preview` (`{layout, lines, folder}`: preview, problems, the move plan with its `digest`), `notes/fit/apply` (the same plus `digest`), `notes/fit/undo` (`{id?}`); these three answer 200 with `ok: false` and `error` for a refusal, so the page can say it |
| everyday | `act`, `ask`, `ask/get`, `ask/pending`, `ask/answer`, `ask/expire`, `notify`, `send-file`, `open-note`, `open-url` |
| health and sync | `health/fix`, `sync/all`, `sync/status` |
| power | `power/stop`, `power/pause`, `power/resume`, `power/off` |
| profile and about | `profile/save`, `profile/restore`, `aboutyou/add`, `aboutyou/remove`, `aboutyou/profile`, `aboutyou/preview`, `aboutyou/merge`, `persona` (`{values}`: the persona card, `core/persona.py:save`) |
| phone | `phone/pair`, `phone/revoke`, `phone/test` |
| terminals | `term/<name>/attach`, `input`, `resize`, `leave`, `restart` (403 when Terminals is off) |
| live stream | `stream/seen` (`{cid, visible}`: the dashboard is in sight or not, `Live.seen`; `ok: false` for no such page, 400 for a cid that isn't a number) |
| other | `research/save`, `research/preview`, `research/run`, `classpack/import`, `mail/confidential/settle`, `books/add` |

`web/tools_api.py` is the API for agent tools and terminal commands: `say` routes text through `App.handle` with
`Incoming(via="terminal")` (a bigger request becomes a job whose answer is fetched with `job`); `call`, `call/list`,
`call/cancel` place and manage calls; `GET tools` also caches the list into `<state>/tools-list.json` for `kurooto mcp`.

Long work runs through `Api._background(fn, then_enable=None)`: one slot (`_installing`), log lines into
`Api.progress`, polled with `GET /api/progress`.

### Adding a route

1. Add a branch in `Api.get` or `Api.post` (or in `tools_api.py`, also adding the name to `GETS`/`POSTS`). Return
   `(status, dict)`, usually `200, {"ok": ..., "message"|"error": ...}`.
2. Do not touch the auth in `server.py`: every `/api/` path already gets Host, same-user, token and Origin checks.
   Never add an unauthenticated route.
3. Guard feature routes with `self.app.modules.get(id)` and `self.app.is_on(id)`.
4. Run slow work with `self._background(fn)`; defer something that would kill the response (stopping) with a
   `threading.Timer`, as `power/stop` does.
5. Emit an event (`app.events.emit`) if the dashboard should see it live.
6. Test with `Api(app).get/post` directly or over HTTP like `tests/unit/test_web.py`.

## Live updates (SSE)

- `Handler._stream`: `cid, q = server.live.add()`, then loops on `q.get(timeout=15)`, sends up to 50 messages per write
  as `data: <json>\n\n`, and a `: ping` comment on timeout. Always `live.drop(cid)` at the end.
- `web/live.py:Live`: one bounded queue per client (`Queue(maxsize=2000)`; a full queue drops the message).
  `push(msg, only=None)` fans out (`only` restricts to a set of client ids). On `add()` a client first gets `graph`,
  a `body` snapshot and `hello` (with its `cid`).
- `Live.__init__` calls `core/events.py:subscribe(self._event)`: every `Events.emit` is pushed as
  `{"t": "event", "cell": cell_of(kind), ...}` (`EVENT_CELL` maps event-kind prefixes to dashboard cells).
  `Live.stop()` unsubscribes it.
- `Live._loop` runs only while a page is open and in sight (`Live.watched()`): a `Vitals.snapshot()` (`body`: machine
  vitals from `core/vitals.py`, feature cells, jobs, schedule, updates, power, processes) every 2 s, and the notes
  graph (`Graph.scan()`) every 5 s when notes changed. Errors emit `dashboard_error`.
- Out of sight (0.6.1): `static/home.js` posts `stream/seen` `{cid, visible: !document.hidden}` on every
  `visibilitychange` (and on `hello` if it starts hidden). `Live.seen(cid, visible)` keeps `Live.hidden`; while every
  open page is hidden the loop reads nothing (a dashboard left in a background tab kept the daemon at 13-30% of a
  core). Coming back sets `_wake`, so the loop takes a reading at once instead of within 2 s. Events and terminal
  output are still pushed to hidden pages; a new page counts as in sight; `drop` forgets its `hidden` entry.
- What one turn costs (0.6.1, a 2,271-note folder, ~500 processes): `snapshot()` about 30 ms, mostly the process
  list; `Graph.scan()` about 11 ms when nothing changed (it names notes with plain strings: a `Path` per note made it
  145 ms); the loop as a whole about 2.5% of one core with a page in sight (6% before, plus the 0.6.0 settings cost),
  0% with every page hidden. `Sampler.processes` (`core/vitals.py`) reads memory, cpu times and start time for every
  process and the name and thread count only for the rows it lists (`as_dict(["name", "num_threads"])`), which halves
  it. `jobs.recent()` uses the `jobs_created` index (it sorted the whole table, 20 ms with 900 jobs).
- Message types the page handles (`static/home.js:connect`): `graph`, `body`, `event`, `hello`, `pty`.
- NOTES names (0.5.19): the pure part of `home.js` between `// -- the pure part` and `// -- end of the pure part`
  (`noteRole`, `hoodOf`, `assignHoods`, `rankLabels`, `regionSpots`; no DOM, so `tests/unit/test_notes_labels.py`
  runs it in node) gives each note a role (`course`, `hub`, `book` for `<subject>/books/<book>`, `note`), a
  neighbourhood (a subject folder, `project:<name>` for `projects/<name>/` or `research/<name>/`, `hub`, or by vote),
  `sdeg` (links not to a book; a book's is capped at 4, so its dot stays small) and `bridge` (other neighbourhoods its
  links reach). `Mind.draw` names regions (the course page's or project index's title at the weighted centroid of its
  notes) below `ZOOM_NAMES` (1.35) and notes above it (`rankLabels`: course pages and hubs, then bridges, books never
  unless pointed at or found); focus, search, R and Study mode work as before.
- NOTES research regions (0.5.21): `Graph.scan` (`web/live.py`) adds `layout` (`graph_layout(app)`: the layout's
  research hub and project place, kept current by `Live._loop`; a layout change rescans) and `research`
  (`research_entries`: per project, the hub line that links to it plus the lines indented under it: `name` (the link's
  alias, else the words before a colon or dash) and `topics` (the other notes it links to)). `assignHoods(nodes,
  {layout, research})` makes every project a region (not only the `MAX_HOODS` biggest), seeds it with its index's
  out-links (`n.out`, one hop) and its hub topics (a note in a course or project folder stays in its folder), then
  every other note votes by its links' regions (folder or seed; a tie goes to the course). Project regions use
  `PAL.accent` (courses cycle the other colours), `regionSpots` keeps them however small and lists them first so
  their names are placed before the courses', and `Mind.draw` sets their names in the accent at weight 750. All of it
  runs once per graph update (`Mind.update`); a frame only reads `n.neighborhood`.
- NOTES provenance links (0.6.1): `note_info` (`web/live.py`) splits a note's wikilinks into `targets` (outside
  Kurooto's provenance blocks) and `via` (only inside them: `PROVENANCE`, the blocks `seen`, `concepts`, `books`,
  `source` and `material<hash>`, see [concept-graph.md](concept-graph.md)); `Graph.scan` sends `[a, b]` for a link
  and `[a, b, 1]` for a via-only one. `Mind.update` keeps both as lines (`l.via`) and in `n.nb` (lit on hover, votes for
  a neighbourhood), but only non-via ones go into `n.snb`, which `assignHoods` uses for `sdeg` (dot size, `rankLabels`)
  and `bridge`: a lecture note or a class post that many concepts were read from stays a small dot and isn't named
  first. `n.via` counts them for the card ("3 links (+152 from reading)"). Tests: `tests/unit/test_notes_labels.py`.
- NOTES hover and keyboard focus (0.6.1, `Mind.draw`): `focus = hover || selected`; each frame every node's light
  `n.a` (lit: the focus, its `n.nb`, a search's matches, R's recent notes; else 0) and focus `n.f` ease toward their
  targets with `1 - exp(-dt / HL_TAU)` (33 ms: about 100 ms to settle, an ease-out; `STILL` sets them at once), so
  dots, lines (`0.015 + 0.065·min(p.a, q.a) + 0.77·max(p.f·q.a, q.f·p.a)`) and names fade together with no layout
  work. Lit notes of no neighbourhood (`PAL.dim`) are drawn lighter (`mix(dim, fg, 0.55)`). Names are placed before
  they're drawn: the focus's first (forced on screen), then up to `NB_NAMES` (24) neighbours from `neighboursOf(n)`
  (links in `n.snb` before via ones, then course pages and hubs, then `sdeg`; sorted once per focus and graph
  update), each in the first of eight slots around its dot that collides with nothing placed; region names fade with
  `this.rk` (0 while a note is pointed at, 0.37 while searching or R) and only take places that are free; the pills are
  drawn last, the focus's on top. Every colour is `PAL` (the page's CSS variables via `readPalette`). Keys on the
  canvas (`tabindex=0`, an `aria-label`, `#mind-card` is `aria-live`): arrows `stepTo([dx, dy])` (the linked note that
  way, by distance / cos² within 60°, else any note that way; none chosen: the note nearest the middle) and
  `keepInView` glides the view to it (`glideStep`; at once with reduced motion), Enter `open-note`, Esc lets go (and
  `preventDefault`s the board's own Esc). The pointer leaving the canvas clears `hover`. Checked in headless Chromium
  on 2,100 notes: a frame's `draw()` costs the same with a note pointed at as without (about 3.6 ms).
- The NOTES map (`static/home.js:Mind`) is a force layout run each frame: pairwise repulsion, a spring per link,
  a pull to the neighbourhood's anchor. A note's spring force is scaled by `min(1, HUB_LINKS / links)` and a step is
  capped at `MAX_STEP`: without that, a map note with hundreds of links (the concept graph's course maps) overshoots
  by more each step and the layout diverges (positions near 1e50, an empty pane). `fit()` zooms out to 0.08.
- Terminals use no websockets: output arrives as `{"t":"pty","n":name,"d":<base64>,"replay":bool}` pushed only to the
  viewers (`modules/terminals.py`), and keystrokes go up as `POST /api/term/<name>/input` batched every 12 ms. xterm.js is
  vendored in `static/vendor/xterm/`.

## Front end (`web/static/`)

- Pages: `setup.html` + `setup.js` (wizard), `home.html` + `home.js` + `home.css` (dashboard), `morning.html` +
  `morning.js`, `confidential.html` + `confidential.js`. Shared: `style.css`, `palette.js` (colour palette: polls
  `GET /api/look` every 30 s), `links.js` (external links through `POST /api/open-url` unless `look.links_in = here`),
  `aboutme.js`.
- Plain scripts with `"use strict"`, no bundler, no framework, no modules. Each page has its own `TOKEN`, `$` and
  `api(path, body)` helper (GET without a body, JSON POST with one). `tests/unit/test_static_js.py` runs
  `node --check` on every file.
- Dashboard tabs (`TABS` in `home.js`): today, activity, jobs, schedule, features, phone, research, about, settings,
  and terminals. Alt+letter shortcuts in `PKEY` (Alt+T Today, Alt+S Settings). Layouts `dense` and `roomy`
  (`look.layout`).
- Ctrl+K (0.5.8): markup `#cmdk*` in `home.html`, logic in `home.js` (`VERBS`: ask, journal, note, remind, due, alarm,
  find, open, study; `cmdOpen`, `cmdGo`, ...). Every verb except `find`/`open`/`study` calls `POST /api/act`, the same
  path as the Today page (`study` calls `setStudy`). Note: `core/palette.py` is the colour palette and
  `core/shortcuts.py` is the app-menu launcher entry; neither is about keyboard shortcuts.

- Designs (0.5.19, `look.design`): `home.css` is the classic design and is left as it was; `home-new.css`, loaded
  after it, holds the new design, every rule scoped to `body[data-design="new"]` (one more attribute than the classic
  selector it overrides, so it wins without `!important`). Tokens on `body.home[data-design="new"]`: `--ui` (Public
  Sans, then system-ui), `--code` (the old monospace stack), `--mono` and `--sans` redefined to `--ui` so every classic
  rule that says `var(--mono)` takes the sans-serif, `--well`/`--raised`/`--rule`/`--track` (steps mixed from the
  palette's `--fg` and `--panel`, so kuro, rose and system all work), `--hd` (a pane's header row), radii and
  `--ease-out`. Figures are `tabular-nums` everywhere (`!important`, because classic's `font:` shorthands reset it).
  Monospace stays on `code`, `pre`, the terminals (`home.js:MONO`, given to xterm in both designs), file paths and
  setting names. The font is `static/fonts/public-sans-latin{,-ext}.woff2` (fontsource's variable cut, weights
  100-900) with `fonts/OFL.txt`; it is never fetched from the internet (CSP `default-src 'self'` would refuse it).
  In `home.js`: `NEW`, `FONT` (canvas words: `SANS` or `MONO`), `FSC` (the canvas font scale, 1.12 in the new
  design) and `cf(px, weight, family)` build every canvas font; `useDesign()` reads `<body data-design>`;
  `setDesign(v)` saves the setting and `applyDesign(v)` switches live (rebuilds STATUS, redraws the borders, clears
  the label width cache, moves `#panes-ctl` into `.bar .right` with `placeCtl()` in the new dense board).
  `[data-design-toggle]` buttons (the top bar's `.design-tg`, the panes menu) toggle it; a `setting_changed` event for
  `look.design` from elsewhere reloads it. Design-dependent wording is small: STATUS box names (`buildBoard`'s `L()`),
  the clock's case, the page title's case, the chat banner, ✦ against a CSS dot, and `grad()` (classic: cool to warm;
  new: the ink, peach from 70%, bad from 90%), `areaGraph` instead of `dotGraph`'s dots, and meters' `.hi` class.
  Tests: `tests/unit/test_design.py`.
- SYSTEMS (`home.js:Body`, 0.5.21). The new design draws it with `membrane()` (the core: three rims from `blob()`,
  each feeling the systole a little later, `lub(now, lag)`; a denser centre carries the name), `neuron()` (a cell:
  five branches outside its nerve's side, each one's length the mean of a fifth of `o.hist`; the soma is `blob()`),
  `axon()` (the nerve as a filled taper sampled at 17 points along the quadratic, widening into the soma; a second
  fibre and a twig) and `synapses()` (a flash, an arc and three sparks where a pulse lands, from `this.syn`), over
  `meshLayer()` (specks and threads drawn once per size and palette into an offscreen canvas). Classic keeps
  `cell()` and the plain curves. Hot paths allocate little: `blob()` and `axon()` write into `BLOB`/`AX`
  (Float32Arrays), each nerve's control point is computed once a frame (`o.q`, read by `at(o, s, P)`), and `rgba()`
  memoises its strings. `STILL` (prefers-reduced-motion) freezes the shapes (`tm = 0`) and the springs; `CAN_HOVER`
  gates the pointer's hover.
  Input: `wire()` (pointer events; a press that moves more than 5 px turns the ring, `view.rot`, rubber-banded by
  `rubber()`; the wheel sets `view.zt` in the dense layout; `springs()` brings both back, k 90, damping 13), `hit()`,
  `hot()` (pointed at, focused or menu open: `o.hv` eases to it and lights the nerve and the cell). `#body-cells`
  holds one visually hidden button per cell (`cellList()`, rebuilt only when the set changes) for Tab and screen
  readers; `#body-menu` is `openMenu(o, byKey)` (instant and focused from the keyboard, `.instant`; faded in from a
  click), `menuAct()` and `closeMenu()`. `place()` puts the hover card and the menu beside the cell, above or below
  it, or in the pane's nearest corner, whichever covers least of the core. The menu asks `GET /api/cell?id=` which
  actions there are (`sync`: the feature is in `core/syncall.py:steps`; `quiet`: `core/keep.py:quiet_change` has
  something to stop) and acts through `POST /api/cell/sync` (`syncall.start_one`: the feature alone, in a thread,
  ending with the event `sync_one` whose `cell` field puts the pulse on its cell), `POST /api/cell/quiet`
  (`calm.apply(keep.quiet_change(m))`, returning the undo id) and `POST /api/calm/undo`. **activity** sets
  `ACT_CELL` and opens the Activity page (`activity()`), filtered by each event's `cell`: `GET /api/events` now
  carries it too (`live.cell_of`). Layout: in the new design `paneGrid` gives SYSTEMS 1.45 parts of the top row to
  NOTES' 1 and the top row 63% of the height (classic: 1:1 and 55%). Tests: `tests/unit/test_systems_menu.py`.
- Study mode (`home.js:setStudy`, Alt+M, `#study-btn` in `.panes-ctl`, `.study-tg` in the roomy bar, Ctrl+K `study`):
  `body.study`; `applyPanes` gives the grid `"notes study"` and `shownPanes`/`paneShown` answer only NOTES, while
  `HIDE`, `MAX`, `dtab` and the terminals stay as they were; an open page is closed and reopened on the way out
  (`SM.page`), so leaving restores the board exactly. The STUDY pane (`#pane-study`, `smBuild`, `smDraw`, `smTick`)
  polls `GET /api/study` every 30 s and after `study_*`, `deadline_*`, `quiz_*` and `setting_changed` events, and acts
  through `POST /api/act` (`study.timer`). `Mind.only` lights the subject's notes and `fit()` frames them;
  `Mind.goTo(node)` centres a note. Entering and leaving replay `@keyframes sm-in` on the panes that show (`.grid.swap`,
  320 ms, `cubic-bezier(0.23, 1, 0.32, 1)`; none with `prefers-reduced-motion`). The page starts in the mode
  `look.study_mode` holds (`data-study`, filled by `Server.fill`) and follows the `study_mode` event, so
  `/study mode on|off` elsewhere switches it live.

## The Today page and actions (`core/actions.py`)

An action is a function `fn(app, args) -> dict` in `ACTIONS`: `journal.add`, `note.capture`, `reminder.add`,
`reminder.cancel`, `reminder.snooze`, `deadline.add` (`{title, when, course?}`), `deadline.done`, `deadline.move`,
`alarm.set`, `alarm.skip`, `alarm.clear`, `alarm.daily`, `checkin.skip`, `checkin.postpone` (`Checkins.postpone`, the
Today page's **+30 min**), `checkin.defer` (to tomorrow morning), `ask`, `question.answer`, `study.mode` (`{on}`:
`study_mode`, which `/study mode on|off` and its intent call too: it sets `look.study_mode` and emits `study_mode`),
`study.timer` (`{do: start|pause|reset, subject}`: `modules/study.py:Study.timer_start`, `timer_pause`,
`timer_reset`), and the Study pane's COURSE box (0.6.0): `subject.policy` (`{subject, policy}`:
`Subjects.set_ai_policy`), `notes.pdf` (`{subject}`: `core/coursepdf.command`), `draft.check` (`{path, subject?,
text?}`: `Drafts.check(..., via="dashboard")`; the comments come as a message).

Study mode's timer (`modules/study.py`, state `<state>/study/timer.json`): a focus writes a study session marked
`timer` (so the window sampler doesn't count twice, and a stop by hand ends the timer: `stop_session`), sets focus
time with `Availability.set_focus` unless a longer focus already holds, and schedules `study.timer_end` (key
`study:timer`). Its end logs the session (capped at its length), clears only the focus it set and flushes the queued
messages (`_focus_end`), then starts the break, or with `study.timer_ends_mode` turns Study mode off. A break's end
leaves the next focus waiting. `study_view(app, subject)` assembles the pane: subjects, the timer, today's totals,
`Deadlines.upcoming(336)` with kinds, `StartBy.morning_rows`, `Quiz.due` cards, and `subject_notes` (the subject's
course, exam-prep, doubts and class-log pages from `core/layout.py`, then the notes in its folder, and in the
zettelkasten layout concept notes tagged with it). Tests: `tests/unit/test_study_mode.py`.

`act(app, name, args, via)` never raises: a `Problem` becomes `{"ok": False, "message"}`, any other exception becomes
a sentence plus an `action_failed` event; success emits `action` and returns `{"ok": True, ...}`. Actions call the
same code as the Telegram command and the AI tool (deadlines go through `core/tools.py:run_tool`, `ask` through
`tools_api` `say`), so the three paths cannot drift. `_on(app, module, what)` refuses when the feature is off.
`today(app)` assembles the page from `modules/daily.py:morning_view` plus reminders, deadlines, alarm state, check-ins,
open questions, the journal and today's inbox. Tests: `tests/unit/test_actions.py`.

To add an action: write `fn(app, args)` that calls the existing module method, add it to `ACTIONS`, add a button in
`home.js:renderToday` (`data-act` / `data-args`) or a Ctrl+K verb, and a test.

## The wizard

`static/setup.js`: `STEPS = ["you", "notes", "computer", "brain", "about", "features", "telegram", "finish"]`, plus a hidden
`restore` section ("I've used Kurooto before": `POST /api/profile/restore`). Each step saves through its own route
and reloads `GET /api/state`. The brain list comes from `web/api.py:BRAIN_ORDER`; features from `MODULE_ORDER`, with
`STARTER` pre-ticked. The `telegram` step (labelled Chat) picks the channel first (`pickChannel`, `setup/channel`):
Telegram's pairing, or the phone app instead (`renderAppChannel`: needs Phone calls set up on the features step; ticks
`calls`, unticks `telegram`; **Pair my phone now** shows `pairBox`). `channelOk()` decides the step's "!" mark.
`finish()` runs `modules/setup` for chosen features that aren't ready, then `modules/enable` (which turns `calls` on
first when Telegram isn't chosen, so what needs somewhere to talk can follow), `autostart` and `setup/done`. Secrets typed in the wizard go to `app.secrets.set` (keychain or `secrets.json`),
never to `settings.json`.

The `notes` step (`renderNotes`, 0.5.20) loads `GET notes/fit`, draws the layout buttons and one input per line, and
posts `notes/fit/preview` 400 ms after typing stops; **Use this layout** posts `notes/fit/apply` with the digest of the
plan last shown (`fitShown`), so a plan that changed since is refused, not applied. **Keep Kurooto's own layout** moves
on when nothing would change, else fills in `presets.kurooto` for the notes folder. A fresh start (`fresh` in
`drawFit`: no notes, the workspace itself, nothing to undo, Kurooto's own layout with no custom places) says there is
nothing to fit in with and folds that editor into a `<details class="fit-more">`; the "Next keeps the layout" hint
shows only while it's open. Settings → notes links to
`/setup#notes` (`home.js:renderSettings`).

**Where you are (`core/setupsteps.py`, `<state>/setup.json`).** The daemon keeps each step's status, not the browser.
`go(i, how)` posts `setup/step` before moving: forward (Next, or a later step in the list) is `next`, **Skip for now**
(`[data-skip]`, on every step but `REQUIRED = ("you", "brain", "finish")`) is `skip`, going back is `leave`; closing
the page posts `leave` with `fetch(..., {keepalive: true})` on `pagehide`. The server decides the status with
`finished(app, step)`: `brain` = the main brain's `available()`, `about` = a report or the profile exists, `telegram` =
paired, or the phone app picked with Calls ready; the rest have nothing to check (`None`). `next` on an unfinished
step gives `open` for a required one and `skipped` otherwise; `skip` on a finished one gives `done`; `leave` keeps
what was there (`open` if nothing). `setup/done` calls `finish()`: optional steps never finished count as skipped
(an opened Features counts as done). `status()` turns a skipped step whose work got done since into `done`, so
`left()` (the dashboard's Finish setting up, `diagnostics.setup_rows`) drops it. `resume()`: the first step neither
done nor skipped, else the first skipped, else `you`; the page opens there unless the address names a step
(`/setup#about`). Seconds per visit are capped at `MAX_VISIT` (an hour). `chosen` restores the features' ticks while
`setup.done` is false. `kurooto setup [STEP]` opens `<url>setup#STEP`. The dashboard (`home.js:setupLeft`) reads `GET
setup` at start and `state.setup` on the Features tab: the corner link becomes **finish setup (N)** and a **Finish
setting up** box lists each step with its link. The features step also says Calm's daily limit, under the cards
(`state.calm`, the number field saves `notify.calm.messages` through `POST settings`). The hint beside Next
(`navHint`) gets its own line above the buttons under 520 px wide. There, too, the current step's chip keeps its accent
through a tap's sticky hover. The Telegram step's channel buttons show Telegram picked until you pick (`renderTelegram`:
its steps are what shows first). Tests: `tests/unit/test_setup_resume.py`,
`tests/unit/test_look_setup.py`.

## How a module shows up in the UI

There is no per-module route registration. `web/api.py:Api._modules` and `_card` read these optional attributes:

| Attribute | Effect |
|---|---|
| `id`, `title`, `description`, `privacy`, `requires`, `ready()` | the feature card |
| `setup(progress)` -> `(ok, msg)` | a "Set up" button, run in the background by `modules/setup`; enables the feature on success |
| `setup_form()` -> `{intro, links, fields: [...], ...}` and `configure(values)` -> `{ok, message, ...}` | a form on the card, saved by `modules/configure` (example: `modules/notes_sync.py`) |
| `card()` -> `{lines, toggles}` and `card_action(act, value)` | extra lines and switches while on (example: `modules/exam_season.py`) |
| `processes`, `processes_intermittent` | CPU and memory for the feature's dashboard cell (`web/live.py`) |
| `health_check()` | the Features tab's health line and Fix button (`core/health.py`) |
| `addon` (set by `core/overlay.py:guard`) | listed under "Your add-ons" |
| `linked` (set by `core/overlay.py:held`) | listed under "Add-ons by link" (home.js `linkBlock`, with the link box, the waiting card, each add-on's Check for update and Remove, and Undo); above it `officialBlock`: GET `addons`'s `official` rows (`core/official.py`), each with the Official badge and Add, Update to vX or Check for update and Remove (official ones aren't repeated among the linked rows) |

Settings UI: `Api._settings` lists `Api.EDITABLE` sections (`you`, `notify`, `availability`, `updates`, `brain`, `ask`,
`look`, `power`, `notes`, `files`, `quota`, `health`, `jobs`, `sources`, `agents`, `hardware`, `web`, `date_offers`; titled from
`Api.TITLES` where the name says little) plus the section of every enabled module whose id is a settings section,
rendered generically by value type. Two rows are made by hand: Starting (`_autostart_section`, after Power) and Quick
ask (`_quick_ask_section`, after it: the `fixed` command `core/shortcuts.py:popup_command()` and the per-system steps
`quick_ask_steps()` as its help; nothing to change there). Left out: `modules` (the Features page's), `autostart` (its own row), and
`Api.HIDDEN` (`telegram.api_base`, `allowed_users`, `chat_id`: set by pairing; `brain.base_urls`, `models`: the brain
page sets them, with its checks; `subjects.list`, `timetable`: their own pages). A new core section that's meant to be
set by hand goes into `EDITABLE` (and its defaults' module into the import at the top of `_settings`). `Api._set`
refuses a bare section key, a section that isn't editable and a hidden key, canonicalises `you.timezone`, requires the
new value to have the old value's type, saves, and emits `setting_changed`.

`MODULE_ORDER` must list exactly the catalog's ids: `tests/unit/test_dashboard.py:
test_every_feature_is_listed_in_the_wizard_and_dashboard` enforces it.

## Known rough edges

- `setup.js` treats any 403 as "the page is out of date", though Host, account and Origin failures also give 403.
