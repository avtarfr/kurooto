# Phone calls, the call line and the phone app

Phone calls (`modules/calls/`, class `Calls`, id `calls`) let the user talk to Kurooto by voice and let Kurooto ring
the user's phone. Three parties are involved:

1. **The daemon** on the user's computer (`modules/calls/*.py`).
2. **The call line**: a Cloudflare Worker plus one Durable Object (`Line`), deployed to the user's own free
   Cloudflare account from `src/kurooto/data/worker/`. It is reachable from the internet; the computer is not.
3. **The phone**: the Android app (`android/`) or the installable web app (any browser, including iPhones, which only
   get notifications).

Audio never passes through the computer or the Worker: the Worker mints a short-lived Gemini Live token and the call
page talks to Google directly.

The user's side of this is in [../user/calls.md](../user/calls.md) and [../user/phone-app.md](../user/phone-app.md).

## Files

| File | Role |
|---|---|
| `modules/calls/__init__.py` | `Calls`: settings, commands, placing and ringing, events from the line, relayed HTTP, transcripts |
| `modules/calls/connector.py` | `Connector`: the outbound WebSocket to the Worker |
| `modules/calls/deploy.py` | `deploy`, `Deployer`: building and deploying the Worker with wrangler |
| `modules/calls/fallback.py` | `LiveHealth`, `VoiceTurns`, `TextCall`, `rotate`, `live_profile`: when Gemini Live fails |
| `modules/calls/line.py` | the shared crypto (k1, t1, s1, pair codes, VAPID keys) |
| `modules/calls/phone.py` | `PhoneApp`: questions and approvals as phone notifications with answer buttons |
| `modules/calls/chat.py` | `PhoneChat`: the phone app as a chat channel (0.5.16), the `chat` notify channel, files for it as links and files shared from the phone (0.5.18) |
| `modules/calls/review.py` | the post-call look back and `/lessons` (0.5.8) |
| `modules/calls/tools.py` | the `Tool` dataclass (shared with `core/tools.py`) and notes helpers |
| `data/worker/src/worker.js` | the Worker: `fetch`, `scheduled`, Durable Object `class Line` |
| `data/worker/web/app.js`, `web/fallback.js` | the call page source (bundled into `public/app.js` at deploy) |
| `data/worker/public/` | `index.html`, `pair.html`/`pair.js`, `inbox.html`/`inbox.js`, `talk.html`/`talk.js` (the web app's chat, 0.5.18), `file.html`/`file.js` (a sealed file for the chat, 0.5.18), `sw.js`, `worklet.js`, icons |
| `data/worker/wrangler.template.toml`, `package.json`, `package-lock.json` | Worker config and pinned packages |
| `android/` | the app (Java, no Gradle), `build.sh`, `smoke.sh`, `test/` |

## Settings and secrets

`register_defaults("calls", ...)` in `modules/calls/__init__.py`: `worker` (`{url, name, version}`; deploy also
writes `account`, `hash`, `deployed`), `live_model`, `live_models`, `voice_by_model`, `voice_mode` (`auto` | `live` |
`phone`), `voice_by_kind`, `turn_brain` (`gemini` | `local`), `text_model`, `voice`, `persona`, `ntfy_server`
(`https://ntfy.sh`), `ring_s` (60), `later_min` (30), `realert_min` ([3, 6]), `notes_repo`, and for the look back
`review` (true), `review_effort` (`high`), `review_brain` (`""` = main), `lessons_max` (12).

Secrets (`Calls.SECRETS` and `deploy.ensure_secrets`): `calls.call_secret`, `calls.connector_secret`,
`calls.ntfy_topic`, `calls.ntfy_key`, `calls.vapid_jwk`, `calls.vapid_public`, `calls.ntfy_token` (optional, from
`kurooto ntfy-token`: an ntfy account token, sent as `Authorization: Bearer` by `Calls.publish_ntfy` and the Worker's
`publish()`, each retrying once without it on a 401/403; it moves ntfy's rate limits from the shared IP to the
account; `check_ntfy_token(server, token)` asks `GET /v1/account`; `Calls.set_ntfy_token` keeps or clears it and
redeploys the line in the background, from `POST /api/phone/ntfy {token}` (the Phone tab, the setup page's call
box) and `kurooto ntfy-token`; `GET /api/phone` has `ntfy_token` and `ntfy_limited`. A 429 from ntfy emits
`calls_ntfy_limited`; `Calls.health` is not OK while any came in the last 7 days and there's no token); also `gemini.api_key` (required) and
`calls.github_token` (set by Notes sync, `modules/notes_sync.py`, so the line can read notes while the computer is off).

## Deploying the line (`modules/calls/deploy.py`)

`deploy(...)` runs `Deployer.run`:

1. `prepare`: Node via `core/prereqs.py`; copy `FILES` from `data/worker` into `<app>/call-line` (`skip_built` leaves
   out `public/app.js` and `node_modules`); copy the phone app (`update/phone_app.py:current`: the one
   downloaded from the running version's signed release, else `data/kurooto.apk` from an older package) to
   `public/kurooto.apk`; `npm ci --ignore-scripts` (skipped when the `.kurooto-lock` stamp matches the
   lockfile); esbuild bundles `web/app.js`.
2. `sign_in`: `wrangler login --browser=false`, the URL opened in the user's browser. `wrangler_env` gives wrangler its
   own config home and strips `CLOUDFLARE_*`, `CF_*`, `WRANGLER_*` from the environment, so a developer's own
   Cloudflare login is never used or touched.
3. `subdomain`: the account's workers.dev subdomain through the Cloudflare API (created as `k-<hex>` if missing).
4. `write_config` / `render_toml`: fills `wrangler.template.toml`; the Worker name is `kurooto-<hex>` (`new_name`).
5. `ensure_secrets`, `wrangler deploy`, `wrangler secret bulk`.
6. Save `calls.worker`, then poll `/health` (24 times, 5 s apart).

Redeploys: `fingerprint` hashes the Worker source and the values baked into it (time zone, `live_model`,
`ntfy_server`, `notes_repo`, whether a GitHub token exists, the ntfy token, hashed); `needs_redeploy` compares it with `calls.worker.hash`.
`Calls._line_update` runs daily at 05:10 and redeploys unattended unless `updates.mode` is `off`.

## The connector (`modules/calls/connector.py:Connector`)

- One outbound WebSocket to `wss://<worker>/connect` with header `x-connector-secret`; `max_size` 8 MB; the library's
  own pings off. Runs as `Calls.background(stop)`, started by `App.start_background`.
- Heartbeat: text `"ping"` every `PING_S = 30` s; the Durable Object answers `"pong"` through
  `setWebSocketAutoResponse` without waking. Nothing heard for `DEAD_S = 75` s ends the session and redials.
- Reconnect back-off 2 s doubling to 60 s; failures go to `app.presence.net_failed("line", e)`. Link state:
  `<state>/calls/link.json`.
- Computer to Worker: `hello` (`pull: true`: hand over what waited one item at a time), `state` (`Calls.state_message`: setup, tools, brief, schedule, texts, voices, presence
  hours ...; pushed every `STATE_S = 300` s or 1 s after `poke()`), `index` (the notes index, in parts, at most
  hourly), `reply` (answers to relayed requests), `admin` (operations).
- Worker to computer: `welcome` (version, `outbox`: how many items wait, an away report; to a computer without
  `pull`, the whole queue as before), `request` (relayed HTTP), `admin-reply`, `event`, `outbox` (something was
  queued while the link looked away, or the queue isn't empty at a state push: take it).
- `_drainer` (a session task): on `outbox`, asks `admin("outbox", done={seq, status, note})` in a loop, handing each
  item to `Calls.take_queued` in a thread, until the answer has no `item`. The Worker drops an item only when the next
  ask names it done, so a crash mid-way repeats at most one item (answers and chat messages refuse a used nonce).
- `admin(...)` / `admin_wait(...)` (from a thread; refuses on the event loop) / `admin_later(...)` (fire and forget;
  its True only means a socket existed).

## Placing a call and ringing

1. `Calls.place(...)` checks `core/availability.py:Availability.call_block` (on a call, quiet / held calls, focus,
   night, then module blockers such as classes and calendar events) unless `alarm` or `force`. A blocked call is booked
   for `next_callable()` and the user is told.
2. `Calls.schedule` books it with `scheduler.at(..., "calls.ring", key="calls:ring:<key>", grace_s=900)` and pokes the
   connector so the line has the schedule too.
   Turned off, `Calls.stop` parks the booked `calls:ring:*` jobs in `calls/parked-calls.json`; `start()` books
   them again (`_unpark`), and one whose time passed is reported in a message, not rung late.
3. `Calls.ring`:
   - asks Calm first (`core/calm.py:Calm.call_ok`: by default one self-started call a day; the alarm and calls the user
     asked for are exempt). A refused call is held for the evening bundle as a line with a call link;
   - records it in `<state>/calls/rings.json`;
   - sends `admin_later("ring", ...)`: the Worker's `Line.ring` mints a ticket (2 h; 3 h for alarms), publishes a
     k1-sealed message to ntfy for paired Android devices, and sends an empty Web Push (VAPID) to every subscribed
     browser, whose service worker (`public/sw.js`) then fetches `/pending`;
   - publishes to ntfy directly from the computer (`Calls.publish_ntfy`) only when the line isn't connected, or
     its answer to `ring` (`Calls._ring_fallback`) doesn't say `"android": true` (an error, no answer, its publish
     failed, or no Android device paired): one ntfy message per ring;
   - sends a Telegram notice with an Answer link (`Calls.link`, a `t1` ticket in the URL fragment), or an urgent
     "the call line isn't connected" notice;
   - schedules `calls.missed` at `ring_s + 30` s, or `ALARM_RING_S` (300, the Worker's and the app's alarm ring)
     + 30 s for an alarm.
4. `Calls._missed`: stops the ring (`stop-ring`, or a direct ntfy stop when the line isn't connected), re-alerts at `realert_min` (not for alarms),
   and finally "Missed call" with Call back / In 30 min buttons; the owning module hears `call_outcome(..., "missed")`.
5. `Calls._scheduled_ring` skips a late or missed one-off when a line exists, assuming the line's cron placed it.

There is no FCM. Android rings through an ntfy JSON stream held by `ListenService`; browsers through Web Push.

When the computer is off, the Worker's cron (`Line.tick`, every minute) places scheduled calls itself (skipping ones
more than 180 s late, holding non-alarm calls during a call), answers tools from the last brief, and queues tool calls,
transcripts, events and answers until the computer takes them (`Calls.take_queued`, see the phone outbox below).

## During a call

- The call page (`web/app.js`, in `CallActivity`'s WebView or a browser) POSTs `/token`; `Line.token` mints a single-use
  ephemeral Live token (30 min expiry, 2 min to start) and emits `call_started` (stops the ring; `Calls.on_event`
  marks the ring answered and writes `<state>/calls/live.json`).
- The Live session is configured from `Calls.config_template` (system instruction with each tool's hint, the persona
  card and boundaries rule from `core/persona.py`, `calls.persona` through the same `persona.clean`, learned lessons, transcription, context compression) and `Calls.texts`. Its time line is `It is %%NOW%%, their
  local time (<zone>)`, filled in by the Worker (`TZ`) or `fallback.py`; `pending()` starts with `now` too. Without
  the zone named, a Live model once planned in UTC ("1:30 PM" at 17:00 IST). Voice by kind: `Calls.voice_for`.
- Tool calls: page to `/tool`, Worker to WebSocket, `Calls.handle_request` to `Calls.run_tool`. Tools are
  `Calls.tools()`: its own (`pending_items`, `search_notes`, `read_note`, `schedule_call`, `call_now`, `hold_calls`,
  `run_task` when Chat is on), `app.ask.call_tools()`, `core/tools.py:sync_tools`, and every enabled module's
  `call_tools()`. With the computer off, each tool's `offline` value decides: `brief` (answered from the last pushed
  brief), `queue` (done later), `needs` (the assistant says it can't).
- `/tasks` is polled for finished jobs and approvals; `Calls.on_call` keeps `availability.set_on_call` 90 s ahead
  (`ON_CALL_S`), so nothing else rings and updates wait.
- What needs attention: `Calls.pending` merges every enabled module's `call_brief()` with `app.ask.call_brief()` and
  `core/assembler.py:call_brief()` (`open_threads`, `earlier`: the last day's gists, within `memory.budget_tokens`).
  `save_transcript` also hands the user's lines to `core/threads.py:from_call` ("I'll send the draft tonight" opens a
  thread).
- Module hooks the calls module looks for (`hasattr` in `modules/calls/__init__.py`): `call_tools`, `call_brief`,
  `call_schedule`, `call_outcome`, `call_transcript`, `call_reschedule`. `Calls.agent_tools` gives unattended AI runs
  only `schedule_call` and `hold_calls`.
- Relayed HTTP paths handled by `Calls.handle_request`: `/tool`, `/tasks`, `/answer`, `/chat`, `/transcript`, `/turn`,
  `/textcall`, `/upload` (1 MB per part, 50 MB total, into the notes inbox folder from `core/layout.py`).

## Fallback layers

`modules/calls/fallback.py` with `data/worker/web/fallback.js` (the page drives them):

1. **Live again**: `rotate()` retries with `BACKOFF_MS = [0, 1000, 3000]`, moving through `calls.live_models`;
   `MID_CALL_RETRIES = 1` for a drop mid-call. `live_profile` adapts settings per model.
2. **Turn by turn**: the phone's own speech recognition and TTS (`speechKind`: the Android bridge or Web Speech). Each
   turn goes to `/turn`, relayed to `VoiceTurns.answer` on the computer: a quick brain (Gemini `text_model`, or the local
   model with `turn_brain = local`), never an agent program, `TURN_S = 25`. With the computer off, the Worker's
   `Line.textTurn` uses Gemini directly with up to 4 tool rounds.
3. **Text on Telegram**: `/text-call` to `/textcall` to `TextCall.start`; replies go through jobs
   (`then="calls.textcall_said"`), the conversation in `<state>/calls/textcalls.json`, ended after 20 min idle
   (`TEXT_IDLE_S`) or by the End button. While a text call is open, `App.handle` sends messages to it first
   (`calls.textcall.takes(msg)`).

Failures are counted in `<state>/calls/live-health.json` (`LiveHealth.record`) and reported by
`Calls.doctor_checks`.

## Transcripts and the look back

- `Calls.save_transcript(b)` writes `<state>/calls/transcripts/YYYY-MM-DD-HHMMSS.txt` (mode 0600) with a
  `# <purpose> (layer)` header, calls the owning module's `call_transcript`, then `review.review`.
- `modules/calls/review.py:review(calls, lines, tools, purpose)`: when `calls.review` is on, the transcript has at least
  `MIN_LINES = 4` lines and `brain.main` is set, it submits

  ```python
  app.jobs.submit(
      prompt,
      title="Call review",
      effort=calls.review_effort,
      quiet=True,
      then="calls.reviewed",
      lane="bg",
      why="calls.review",
      brain=calls.review_brain or None,
  )
  ```

  with the transcript (last 24 000 chars), that call's `Calls.tool_log[since]` (last 60 tool uses; the call page sends
  its `since` with `/tool` and `/transcript`, and the Worker keeps it on tools it queues while the computer is off)
  and the current lessons. Because it is a
  normal job with tools, the AI can do what the call missed (a reminder never set, a note never written).
- `reviewed(calls, job, result, payload)` (registered as the `calls.reviewed` then-action) reads the ```` ```lessons ````
  fence, `merge()`s it into the existing lessons (60% word overlap replaces an old one; capped at `lessons_max`),
  `save_lessons()` to `<state>/calls/lessons.md`, and notifies "After the call: ..." (Calm reason `calls.review`) unless
  nothing was done or learned.
- `lessons(app)` is read by `Calls.config_template`, so every later call is told them.
- `/lessons` (`Calls._cmd_lessons` to `review.command`): list, `/lessons forget N`, `/lessons clear`.
- Because the review is a job not submitted by Chat, its prompt and answer are not recorded into the chat history
  (`Chat.owns`, checked in `core/jobs.py:Jobs._deliver`).

Other files in `<state>/calls/`: `rings.json`, `live.json`, `link.json`, `inbox.json`, `chat.json`, `answer-nonces.json`,
`live-health.json`, `textcalls.json`, `lessons.md`, `transcripts/`, `searches.json` (each `search_notes` query, from
`Calls.run_tool` through `modules/curious.py:searched`, kept 8 days for Dreaming's curious line; retention's `calls`
kind clears it).

## The Worker (`data/worker/src/worker.js`)

- `export default {fetch, scheduled}` and the Durable Object `Line` (SQLite-backed, migration v1). Cron `* * * * *`.
- Vars baked in at deploy: `OWNER_ID`, `TZ`, `PUBLIC_URL`, `VERSION`, `LIVE_MODEL`, `NTFY_SERVER`, `NOTES_REPO`.
  Secrets: `CALL_SECRET`, `CONNECTOR_SECRET`, `GEMINI_API_KEY`, `NTFY_TOPIC`, `NTFY_KEY`, `VAPID_JWK`, `VAPID_PUBLIC`,
  `NTFY_TOKEN` (always sent, empty without one, so clearing it clears the line's copy),
  optional `GITHUB_TOKEN`.
- Routes: top level `/health`, `/manifest.webmanifest`; the rest goes to `Line.fetch`. No auth: `/connect` (checked by
  the connector secret), `/pair/claim` and `GET /sealed/<32 hex>` (a sealed file: only its link's key opens it). Any valid key (device key `d1`, ticket `t1`, or a minted ticket):
  `/status`, `/token`, `/turn`, `/text-call`, `/call-report`, `/tool`, `/tasks`, `/transcript`, `/upload`. Paired
  devices only: `/pending`, `/answer`, `/chat` (GET and POST), `/outbox`, `/app-call`, `/ring-reply`,
  `/push/subscribe`, `/device/key`.
- Admin operations over the WebSocket: `ring`, `stop-ring`, `pair-code`, `devices`, `revoke`, `ticket`, `bye`, `notify`,
  `notify-clear`, `sealed-put`, `sealed-claim`, `outbox`, `chat-say`, `file-put`.
- Pinned packages in `package.json` / `package-lock.json` (`@google/genai`, esbuild, wrangler). CI installs them with
  `npm ci --ignore-scripts`.

## The app's chat and the phone outbox (0.5.16)

**The chat.** `modules/calls/chat.py:PhoneChat`. A message typed in the app reaches `PhoneChat.take`, which builds
`Incoming(text, via="app", message_id="app:<id>", respond=...)` and calls `App.handle`: commands, intents and Chat as
on Telegram (`core/turnon.py` already offers its buttons for `via` `app`). `respond` and later answers go through
`PhoneChat.say`, which keeps the buttons' data in `<state>/calls/chat.json` (last 100, 7 days) and sends
`admin_later("chat-say", msg=...)`; failed pushes are sent again from `state_message` (`flush`, last hour).
Jobs answer with `reply_to="app:<id>"`: `core/notify.py:Notifier._deliver` sends such a message to the `chat` channel
only (and the desktop, by its kinds); with no `chat` channel it goes to Telegram without the reply_to. With
`notify.app_chat` on, messages whose kind isn't in `notify.app_kinds` (and isn't `call`) also go to `chat`.
A button press runs `App.callback(data)` and says its answer in the chat unless it's empty or "ok"; under the answer
to a counting button (`core/notify.py:counts`, a "+1"; 0.5.20) the same button again, so the chat's notification can
offer it too.
Without Telegram (`App.app_main()`: Telegram off, Phone calls on; 0.5.18) the chat gets everything not in
`notify.app_kinds` as if `app_chat` were on, Calm's Why? / Less of this rows included (core.md, Notify and Calm).

**Files for the chat (0.5.18).** `PhoneChat.send` hands a `Message.file` to `send_file(path, caption, re_id)`, which
makes the link in a thread (`_file_now`) and says it in the chat as a URL button:

1. Drive upload on and ready: `modules/google_drive.py:DriveUpload.put(path, temporary=True)` (deleted after
   `drive_upload.temp_days`), button "Open in Drive".
2. Else `to_line(path)`: a fresh 32-byte key, `line.seal_f1` (AES-256-GCM, raw `nonce ‖ ciphertext+tag`), sent with
   `admin_wait("file-put", fid, part, parts, size, hours, data)` in `FILE_PART` (384 KB) pieces, in order (`fid`,
   not `id`: `id` is the admin request's own). At most `FILE_MAX` (10 MB); kept `FILE_HOURS` (24). The link is
   `<worker>/file#i=<fid>&k=<base64url key>&n=<name>`; `public/file.js` fetches `/sealed/<fid>`, decrypts with
   WebCrypto, offers Save and shows text files. The Worker (`Line.filePut`, `filesLive`, `fileGet`) keeps parts under
   `f:<id>:<n>` and an index `files` (`{parts, size, got, bytes, exp}`), at most `FILES_BYTES` (30 MB) at once
   (`{"error": "full", "note"}` past it), and drops expired files on access and every cron tick.
3. Else a plain message: the file stays on the computer, with its path and the dashboard's address.

`modules/skills.py:send_file` (`kurooto send`, the AI's `send_file`) goes to `send_file` directly when
`app_main()`. `Jobs._deliver` sends a long answer's file with the text's `reply_to`, so an answer to the app's chat
gets its file there too.

**Files from the phone.** `Calls._upload` records each saved file in `<state>/calls/shared.json` (`PhoneChat.shared`:
name, path, note, time; last 20), and the filing job it submits with Chat on is Chat's own (`Chat.own`), so where it
went joins the conversation. `modules/chat.py:Chat.ask` adds the last two hours' shares (`SHARED_S`) to a request
that talks of a file (`REFERS`); `record_turn` keeps that note out of the history.

**The web app's chat.** `public/talk.html` / `talk.js` (at `/talk`): the documented API below with the device key from
`localStorage` (`kurootoDevice`); its own copy of the chat in `localStorage` (`kurootoChat`); `GET /chat?after=` on
opening, every 5 s while visible and on `visibilitychange`; a Kurooto chat push opens `/talk` (`sw.js`). The call
page (paired browsers), the inbox and the pairing page link to it.

**The phone outbox.** The Worker's `queue` (one value: an index of items, each with a rising `seq`; a phone item's body
under its own key `q:<seq>`) holds both the line's own items (`tool`, `transcript`, `event`) and phone items
(`answer`, `chat`, `upload`, with `device` and `oid`). Past 200 items the oldest line items go, never phone items.
A phone request is relayed only when the computer is online and no phone item is queued; otherwise it's queued, so
order holds. Limits: `OUTBOX_MAX` 100 things (distinct `oid`), `OUTBOX_BYTES` 20 MB of files (checked for the whole
file, `parts × 512 KB`, at part 0); over them, 507 with `note`. Only paired devices can queue; a ticket's upload while
offline still gets 503. When the computer finishes an item (`outbox` op with `done`), the Worker drops it, records
`{oid, kind, ok, note, t}` in `odone` (100, one day) and tells an Android sender by ntfy (below). Web devices aren't
pushed for this (an iPhone must show something for every push); they poll `/outbox` or `/chat`.

**Sealing.** Android: the fields are k1-sealed with the ntfy key (as answers are), so ntfy can't read them; the Worker
holds that key (`NTFY_KEY`) and stores the sealed form. Web: plain JSON over HTTPS with the device key. Either way
`ts` + `n` (16-64 hex) make it single use (`PhoneApp._spend_nonce`, 10-minute freshness against the Worker's `at`).
Shared files are stored as sent (base64) while they wait.

### API for phone apps

All with header `x-call-secret: d1.<id>.<secret>` (a paired device). Ids are 16 lowercase hex.

| Route | Body / query | Answer |
|---|---|---|
| `POST /chat` (Android) | `{"id", "k1": seal_k1(ntfy key, JSON fields)}` | see below |
| `POST /chat` (web) | `{"id", "ts", "n", "text", "to"?}` or `{"id", "ts", "n", "button": <number>, "msg": <Kurooto message id>}` | see below |
| `GET /chat?after=<seq>` | | `{"seq", "msgs": [message...] with seq > after, "waiting", "done", "computer", "assistant"}` |
| `GET /outbox` | | `{"waiting": [{"oid", "kind", "at"}], "done": [{"oid", "kind", "ok", "note", "t"}], "computer": "online"\|"offline"}` |
| `GET /pending` | | as before, plus `"chat"`: the last 5 messages from Kurooto (for the service worker) |
| `POST /answer` | as before | as before; offline and queued: `{"ok": true, "queued": true, "note"}` |
| `POST /upload?name&note&id&part&parts` | raw bytes, at most 512 KB a part | online: the computer's answer; offline (device key, `id` given): `{"ok": true, "queued": true, "part", "note"}` |

The sealed fields (Android) are the web body's fields plus `"id"` (must match the outer id): `{"id", "ts", "n",
"text", "to"?}` or `{"id", "ts", "n", "button", "msg"}`. `text` is at most 4000 characters (16 000 bytes of body).

`POST /chat` answers: computer online, `200 {"ok": true, "id", "said": [message...]}` (the immediate replies; later
ones arrive as chat messages), or a button's `200 {"ok": true, "note"}`; offline, `200 {"ok": true, "queued": true,
"note"}`; `400 {"ok": false, "note"}` (empty, no id, can't be opened: pair again); `409 {"ok": false, "note"}` (stale
or used nonce); `507 {"error": "full", "note"}` (the outbox is full); `401` (not paired).

A chat message: `{"id", "seq", "from": "you"|"kurooto", "text" (at most 6000), "at" (seconds), "buttons":
[{"label"} | {"label", "url"}] (at most 6; a button with `url` opens it, one without is pressed by its index),
"reply" (true: a reply to it, with `to`, reaches the feature that sent it), "re"? (the message it answers),
"title"?}`. Your own message appears in the log (`from: "you"`) once the computer took it. The line keeps the last
50, each 3 days.

What an app should do: keep its own copy of the chat; generate the id; show "Waiting for your computer" for anything
answered `queued`, until `GET /outbox` (or `/chat`) no longer lists its `oid` (the chat message's id, the answer's
item id, the upload's `id`); catch up with `GET /chat?after=<last seq>` on opening and after a push.

**Pushes.** Each Kurooto message: Android gets a k1 ntfy message `{"title", "message", "tags": ["stop", "chat"],
"id", "seq", "re", "reply", "buttons", "time", "assistant"}` (text trimmed to fit ntfy; the app fetches `/chat` for
the rest); web devices get an empty Web Push and find it in `/pending`'s `chat`. When a queued item from an Android
phone went through: `{"tags": ["stop", "outbox"], "dev": <device id>, "done": [{"oid", "kind", "ok", "note"}]}`.
`stop` makes apps older than 0.5.16 ignore both.

**Admin ops.** `chat-say {msg, assistant}`: store a message (`from` you or kurooto; once per id) and push it if it's
Kurooto's; answers `{ok, seq, android, web}`. `outbox {done?}`: drop `done.seq` and tell its phone; answer the next
item `{"item": {seq, kind, at, ..., body | body_b64}, "left"}` or `{"item": null}`.

## Pairing

1. `Calls.pair_start`: `line.pair_code()` (8 characters from `CODE_ALPHABET`) sent with
   `admin_wait("pair-code", minutes=15)`; the Worker keeps only its SHA-256 hash. The link `<worker>/pair#c=CODE` is
   shown as a QR (`segno`). Commands `/phone`, `/phones`, `/unpair`; dashboard `POST /api/phone/pair`, `phone/revoke`,
   `phone/test`.
2. The phone opens the link. `public/pair.js` either hands it to the Android app (`kurooto://pair` / `intent://` to
   `PairActivity`) or pairs the browser itself.
3. `Line.claim` (single-use code, 30 failures an hour, at most 10 devices) returns a device key
   `d1.<8 hex>.<64 hex>` (the Worker stores only its hash), names, the ntfy topic and key (Android only) and the VAPID
   public key.
4. Browsers subscribe to Web Push (`/push/subscribe`); Android sends its P-256 public key to `/device/key` for sealed
   (s1) data.

`kurooto rotate` (`cli.py` to `core/leave.py:rotate_command`, `rotate_line`): deletes the line keys (`LINE_KEYS`),
makes new ones (`deploy.ensure_secrets`) and redeploys, restoring the old keys if that fails. The Worker's `Line.fresh`
notices the new call secret and forgets devices, tickets and pair codes, so every phone pairs again. The Gemini key is
not rotated.

## Crypto, and the shared vectors

All three implementations must agree byte for byte: Python `modules/calls/line.py`, the Worker (`sealK1`, `openK1`,
`signedTicketOk` in `worker.js`), Java (`android/src/.../Crypto.java`, `Seal.java`).

| Name | Format |
|---|---|
| k1 | AES-256-GCM, 12-byte nonce: `"k1." + base64url(nonce ‖ ciphertext+tag)` |
| f1 | a file for the chat: raw bytes `nonce ‖ ciphertext+tag` (AES-256-GCM, a fresh key per file, base64url in the link's fragment; Python `line.seal_f1`/`open_f1`, browser `public/file.js`; no Java side) |
| t1 | `t1.<expiry ms>.<hex HMAC-SHA256 with the call secret>` |
| d1 | device keys `d1.<id>.<secret>` |
| s1 | ECDH P-256, HKDF-SHA256 (salt: the ephemeral public key, info `"kurooto s1"`) to an AES key, then k1 |
| Web Push | VAPID ES256 JWT (`line.vapid_keys`, `worker.js:webPush`) |

`tests/fixtures/call-vectors.json` holds k1, t1 and s1 vectors, checked by `tests/unit/test_calls.py`
(`test_k1_and_t1_match_the_shared_vectors`, and `test_the_worker_agrees_with_the_vectors` running
`tests/js/vectors.mjs` in Node), `android/test/CryptoTest.java` (k1, s1; CI job `android`), and
`tests/unit/test_lidsafe.py` (s1). Changing any format means changing all three and the vectors in one commit.

## The Android app (`android/`)

- The package is named in `android/AndroidManifest.xml`; minSdk 23, target 35. Built without Gradle by `android/build.sh` (aapt2, javac
  `-source 8`, d8, zipalign, apksigner); versionCode from `pyproject.toml`. Release signing uses `KUROOTO_KEYSTORE` and
  `KUROOTO_KEYSTORE_PASS` on the maintainer's machine (`tools/release.py sign --apk` sets them and builds from the
  release's tarball; see [release-and-updates.md](release-and-updates.md#the-phone-app-sign---apk)); otherwise a
  throwaway debug key. `build.sh --test` runs
  `test/CryptoTest.java` and `test/SpeechTest.java` on a plain JVM.
- Components: `MainActivity` (the checklist: battery, notifications, full-screen calls), `PairActivity`,
  `CallActivity` (WebView with the `KurootoApp` JS bridge), `AnswerActivity`, `ChatActivity` (the chat; its store and
  the outbox's waiting list are `Chat`, `chat.json` in the app's files), `ShareActivity` (share to Kurooto, with the
  device key so it can wait on the line),
  `ListenService` (foreground, type `remoteMessaging`, holds the ntfy stream), `BootReceiver`, `ActionReceiver`,
  `QuickNoteActivity`, `NoteTile`, `TalkWidget` / `TalkWideWidget` (below).
  Helpers: `Crypto`, `Seal`, `Line`, `Net`, `Prefs`, `Inbox`, `Chat`, `Speech`, `Tls` (adds ISRG Root X1 on API < 25),
  `B64`, `Ui` (the look), `BlobView` (the main screen's background).
- Widgets, Quick note and the tile (0.6.0), no laptop or Worker changes:
  - `TalkWidget` (1x1, `res/xml/widget_talk.xml`, layout `widget_talk.xml`) opens `ChatActivity` with the extra
    `type` (focus the box, keyboard up). `TalkWideWidget` (2x1, a subclass only because Android tells providers apart
    by component) adds the newest item of `GET /pending` (`Line.waiting`, what MainActivity lists under "Waiting for
    you"), kept in `Prefs.widgetLine`. It looks it up in `onUpdate` (`updatePeriodMillis` 30 min, `goAsync`), on
    `TalkWidget.refreshSoon` (debounced 3 s: `Inbox.show`, `Inbox.cancel`, `Prefs.savePairing`), and takes
    MainActivity's own fetch through `TalkWidget.waiting(c, items)`; with no 2x1 placed nothing is fetched.
    `Prefs.forget` redraws them unpaired. A Today screen can feed the 2x1 the same way (`Prefs.setWidgetLine` +
    `TalkWidget.draw`). Colours are the `k_*` resources, so the widgets follow light/dark and Material You;
    `drawable-v31/k_widget.xml` takes the launcher's corner radius.
  - `QuickNoteActivity` (`Kurooto.Dialog`, exported so every launcher can open the static shortcut; it sends only on
    Save) uploads the note as `quick-note.md` with `Line.upload`, exactly as `ShareActivity` does with shared text: the
    computer's `Calls._upload` saves it to the notes inbox, the phone outbox holds it while the computer is off
    (`Line.WAITING`, `Chat.waitFor`). An unsent note stays in `Prefs.noteDraft`. Opened by the static shortcut
    (`res/xml/shortcuts.xml`, `android.app.shortcuts` meta-data on MainActivity; launchers before 7.1 ignore it) and
    `NoteTile` (`TileService`, API 24, `@TargetApi(24)`; `startActivityAndCollapse(PendingIntent)` on 14+, the
    Intent form below; `unlockAndRun` when locked).
- Counting buttons (0.5.20, a deadline's **+1**): `Inbox.counts(button)` is a label `+<n>` (the Worker passes only
  labels). `Inbox.send` shows such an item again after a tap that went through or waits on the line (`setOnlyAlertOnce`,
  the answer's note as its text) instead of `done()`; the computer keeps the item open for it (`PhoneApp._button`).
  `ListenService.chatNote` (the chat's notification) adds up to two such buttons as actions, `ActionReceiver.CHAT_TAP`
  sends them with `Chat.tap` (the outbox when the computer is off) and shows the waiting or failed note with the
  action kept; one that went through comes back as a new chat message with the button again.
- The look is Material 3 from the framework alone (no AndroidX or Material Components), views built in code:
  - Colours are resources named after Material 3's roles (`k_bg`, `k_card`, `k_fg`, `k_dim`, `k_primary`,
    `k_tonal`, `k_ok`, `k_bad`, ...): `res/values/colors.xml` is the web pages' light "kuro" palette, `values-night`
    the dark one, and `values-v31` / `values-night-v31` map Material You's `system_accent1_*` / `system_neutral*_*`
    onto the same names on Android 12+. `k_call_*` (the ringing screen, from `call.css`) and `k_brand` (notifications)
    never change. Light or dark follows the system (`-night`); Android 9 and older are light.
  - Themes (`res/values/themes.xml`): `Kurooto` (full-screen pages, the app's default), `Kurooto.Dialog` (`AnswerActivity`,
    `PairActivity`, `ShareActivity`: a 28dp-cornered card, `drawable/k_dialog.xml`) and `Kurooto.Call` (`CallActivity`,
    always dark). `Base.Kurooto*` only pick the framework's light or dark `Theme.Material` parent.
  - `Ui.java` builds the views: `page(activity)` / `dialog(activity)` set the content and return the column to fill
    (`page` keeps clear of the system bars, which Android 15 draws over; `page(activity, behind)` puts a view behind
    the scrolling column, full screen); `appBar(activity, title, onBack)` is the small top app bar for a screen that
    isn't one scrolling page (the chat: its root is `fitsSystemWindows`, so on Android 15 it keeps clear of the bars
    and the keyboard); `headline`, `title`, `heading` (a section, in
    the accent colour), `body`, `dim`, `small`, `status` + `ok()` / `bad()`; `card`, `list` + `item` (two-line rows),
    `tapCard`; buttons `filled`, `tonal`, `outlined`, `flat`, `large(b)`, `end(b)`, or `button(c, text, fill, ink,
    stroke)`; `field(c, hint)`; `icon`; `busy(activity, title, text)` + `done(status, worked)` for a dialog that waits;
    `tint(c, builder)` for notifications (`ListenService.builder` does it). Every view comes with full-width
    LinearLayout params and a small gap above, so `col.addView(v)` is enough. A new screen: declare it with
    `android:theme="@style/Kurooto"` (or leave it to the app's default) and start `onCreate` with
    `LinearLayout col = Ui.page(this);`.
  - The chat (`ChatActivity`) is built from `Ui` too: your messages on `k_primary_container`, Kurooto's on `k_card`,
    20dp corners, dp spacing, tonal buttons under a message, a pill-shaped box and a 56dp Send.
  - `BlobView` is the main screen's background (`Ui.page(this, new BlobView(this))`): four blobs, each a closed
    quadratic curve through 24 points whose radius is a sum of three slow sines (the dashboard's `blob()` in
    `home.js`), filled with a `RadialGradient` (local matrix per frame, nothing allocated per frame) in `k_blob_1..4`
    (the web palette's accent, lav, peach, pink; `system_accent1..3_*` on Android 12+), alpha 0.15 light / 0.22 dark.
    About 20 frames a second while attached, shown and its window visible (`onWindowVisibilityChanged`,
    `onVisibilityChanged`); one still frame when `Settings.Global.ANIMATOR_DURATION_SCALE` is 0 or in battery saver.
  - The launcher icon is `public/icon.svg`'s motif: on Android 8+ the adaptive `mipmap-anydpi-v26/ic_launcher.xml`
    (background `k_call_bg`, foreground `drawable/ic_launcher_fg.xml` with icon.svg's 24 units in the middle 72dp,
    monochrome `ic_launcher_mono.xml` for themed icons); on 6 and 7 the plain vector `mipmap/ic_launcher.xml`.
    `drawable/ic_agent.xml` is Kurooto as a caller (the ringing notification's picture).
  - The ringing notification (`ListenService.ring`): on Android 12+ `Notification.CallStyle.forIncomingCall` (Person =
    the assistant's name, or "Wake-up call"; Decline and Answer are the same intents as before, Later/Snooze is an
    extra action between them). If Android refuses it (`notify` throws), and below 12, the old BigText notification
    with three actions. Both share `ringNotice()` (full-screen intent, ongoing, timeout).
  - `CallActivity` puts the WebView in a `fitsSystemWindows` FrameLayout, so on Android 15 (edge to edge) the call page
    stays clear of the status and navigation bars; on 6 to 14 the insets are 0 and nothing changes.
  - Touch targets are 48dp at least (56dp for `large`, list rows 64dp). Use `Ui.color(c, R.color.k_*)`, never a
    hard-coded colour, so dark mode and Material You keep working.
- CI: `ci.yml` job `android` (vectors, debug build, `NewApi`/`InlinedApi` lint as errors);
  `android-emulator.yml` runs `smoke.sh` on API 23 to 35.

## Tests

- `tests/integration/` runs the real Worker under `wrangler dev` with fakes for Google, ntfy and Web Push
  (`tests/fakes/cloud.py:FakeCloud`) and the real `Connector`: `test_call_line.py` (auth, pairing, tokens, tool relay,
  ringing with VAPID signature checks, uploads, transcripts, the offline queue and cron), `test_lidsafe_line.py`,
  `test_livefallback_line.py`, `test_phone_line.py`, `test_phone_chat_line.py` (the chat and the phone outbox),
  `test_presence_line.py`, `test_rotate_line.py`. `test_phone_chat_line.py` also covers a sealed file put and fetched. They need Node;
  CI's `call-line` job installs the Worker's packages and bundles the page first.
- Unit: `tests/unit/test_calls.py`, `test_phone.py`, `test_phone_chat.py`, `test_app_first.py` (no Telegram: routing,
  files as links, shared files, setup, doctor), `test_livefallback.py` (runs `tests/js/fallback.mjs` and
  `tests/js/callpage.mjs`).

## Known problems and doc mismatches

- A shared file's part that the computer took but didn't confirm (it crashed in between) is written twice when the
  outbox is taken again; chat messages and answers are protected by their nonce, file parts aren't.

- With no Android device paired, the computer still publishes each ring to ntfy once (the Worker's answer can't tell
  "no Android device" from "its publish failed").
- A sealed file's link holds its key, and the link is part of a chat message the call line keeps (3 days): the file
  is only as private from the call line as the chat is.
- `calls.ring_s` is never sent to the Worker or the app, which ring 60 s (5 minutes for an alarm) whatever it says.
- Turn-by-turn calls run tools through `core/tools.py:run_tool` and don't reach `Calls.tool_log`; a call page from
  before 0.5.8 (until the Worker is deployed again) sends no `since`, so its tools share the `""` log.
