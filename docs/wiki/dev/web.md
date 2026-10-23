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
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`. Because of the CSP,
  pages may not use inline scripts or load anything from another origin.
- Static files: `static(name)` reads them with `importlib.resources`, only names matching
  `(?:vendor/xterm/)?[a-z0-9_-]+\.(html|js|css|svg|png|ico)`.
- `Server.fill(html)` substitutes `{{TOKEN}}`, `{{VERSION}}`, `{{PALETTE}}`, `{{LAYOUT}}`, `{{STUDY}}` and injects the
  palette style and `/static/palette.js` / `/static/links.js` before `</head>`.
- Settings registered here: `web.port`, and the `look.*` section (`palette`, `theme_file`, `layout`, `projects`,
  `panes`, `hidden_features`, `links_in`, `study_mode`).

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

GET (in `Api.get`): `tools`, `job?id=`, `usage?days=` (tools_api); `jobs`, `term`, `health`, `sync/status`,
`profile`, `note?id=`, `settings`, `look`, `events` (last 80), `board` (503 without `Live`), `state` (the wizard's
whole state), `phone`, `power`, `aboutyou/profile`, `aboutyou?source=`, `persona`, `research`, `progress`, `ask`, `ask/<id>`,
`today` (`core/actions.py:today`), `study?subject=` (`core/actions.py:study_view`), `morning`
(`modules/daily.py:morning_view`), `mail/confidential?day=`, `books`.

POST (in `Api.post`):

| Area | Paths |
|---|---|
| tools_api | `tools/call`, `say`, `job`, `call`, `call/list`, `call/cancel` |
| AI | `brain`, `brain/test`, `brain/models`, `jobs/cancel`, `tryit` |
| features | `modules/enable`, `modules/disable`, `modules/setup`, `modules/configure`, `modules/card` |
| settings and you | `settings`, `you`, `autostart`, `hardware/refresh`, `hardware/override`, `keys/gemini` |
| setup | `prereqs/install`, `prereqs/signin`, `telegram/token`, `telegram/poll`, `telegram/relink`, `telegram/webhook-off`, `setup/done` |
| everyday | `act`, `ask`, `ask/get`, `ask/pending`, `ask/answer`, `ask/expire`, `notify`, `send-file`, `open-note`, `open-url` |
| health and sync | `health/fix`, `sync/all`, `sync/status` |
| power | `power/stop`, `power/pause`, `power/resume`, `power/off` |
| profile and about | `profile/save`, `profile/restore`, `aboutyou/add`, `aboutyou/remove`, `aboutyou/profile`, `aboutyou/preview`, `aboutyou/merge`, `persona` (`{values}`: the persona card, `core/persona.py:save`) |
| phone | `phone/pair`, `phone/revoke`, `phone/test` |
| terminals | `term/<name>/attach`, `input`, `resize`, `leave`, `restart` (403 when Terminals is off) |
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
- `Live._loop` runs only while clients exist: a `Vitals.snapshot()` (`body`: machine vitals from `core/vitals.py`,
  feature cells, jobs, schedule, updates, power, processes) every 2 s, and the notes graph (`Graph.scan()`) every
  5 s when notes changed. Errors emit `dashboard_error`.
- Message types the page handles (`static/home.js:connect`): `graph`, `body`, `event`, `hello`, `pty`.
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
`timer_reset`).

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

`static/setup.js`: `STEPS = ["you", "computer", "brain", "about", "features", "telegram", "finish"]`, plus a hidden
`restore` section ("I've used Kurooto before": `POST /api/profile/restore`). Each step saves through its own route
and reloads `GET /api/state`. The brain list comes from `web/api.py:BRAIN_ORDER`; features from `MODULE_ORDER`, with
`STARTER` pre-ticked. `finish()` runs `modules/setup` for chosen features that aren't ready, then `modules/enable`,
`autostart` and `setup/done`. Secrets typed in the wizard go to `app.secrets.set` (keychain or `secrets.json`),
never to `settings.json`.

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

Settings UI: `Api._settings` lists `Api.EDITABLE` sections (`you`, `notify`, `availability`, `updates`, `brain`, `ask`,
`look`, `power`, `notes`, `files`, `quota`, `health`, `jobs`, `sources`, `agents`, `hardware`, `web`; titled from
`Api.TITLES` where the name says little) plus the section of every enabled module whose id is a settings section,
rendered generically by value type. Left out: `modules` (the Features page's), `autostart` (its own row), and
`Api.HIDDEN` (`telegram.api_base`, `allowed_users`, `chat_id`: set by pairing; `brain.base_urls`, `models`: the brain
page sets them, with its checks; `subjects.list`, `timetable`: their own pages). A new core section that's meant to be
set by hand goes into `EDITABLE` (and its defaults' module into the import at the top of `_settings`). `Api._set`
refuses a bare section key, a section that isn't editable and a hidden key, canonicalises `you.timezone`, requires the
new value to have the old value's type, saves, and emits `setting_changed`.

`MODULE_ORDER` must list exactly the catalog's ids: `tests/unit/test_dashboard.py:
test_every_feature_is_listed_in_the_wizard_and_dashboard` enforces it.

## Known rough edges

- `setup.js` treats any 403 as "the page is out of date", though Host, account and Origin failures also give 403.
