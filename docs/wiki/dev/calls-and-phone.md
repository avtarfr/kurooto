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
| `modules/calls/today.py` | `PhoneToday`: the Android app's Today list, sealed for each phone, and Done / +1 tapped on it (0.6.0) |
| `modules/calls/views.py` | `PhoneViews`, `trim_notes`: Systems and the Notes map for the Android app, sealed for each phone; Systems live while watched (0.7.0); the Brain console's copy, kind `brain`, only while watched (0.8.10) |
| `modules/calls/review.py` | the post-call look back and `/lessons` (0.5.8) |
| `modules/calls/tools.py` | the `Tool` dataclass (shared with `core/tools.py`) and notes helpers |
| `data/worker/src/worker.js` | the Worker: `fetch`, `scheduled`, Durable Object `class Line` |
| `data/worker/web/app.js`, `web/fallback.js` | the call page source (bundled into `public/app.js` at deploy) |
| `data/worker/public/` | `index.html`, `pair.html`/`pair.js`, `inbox.html`/`inbox.js`, `talk.html`/`talk.js` (the web app's chat, 0.5.18), `file.html`/`file.js` (a sealed file for the chat, 0.5.18), `settings.html` + `shortcut.js` (the Tell Kurooto recipe, 0.6.0) and `qr.js` (a QR maker), `sw.js`, `worklet.js`, icons |
| `data/worker/wrangler.template.toml`, `package.json`, `package-lock.json` | Worker config and pinned packages |
| `android/` | the app (Java, its main screen in Kotlin and Compose; Gradle run by `build.sh`), `smoke.sh`, `test/` |

## Settings and secrets

`register_defaults("calls", ...)` in `modules/calls/__init__.py`: `worker` (`{url, name, version}`; deploy also
writes `account`, `hash`, `deployed`), `live_model`, `live_models`, `voice_by_model`, `voice_mode` (`auto` | `live` |
`phone`), `voice_by_kind`, `turn_brain` (`gemini` | `local`), `text_model`, `voice`, `persona`, `ntfy_server`
(`https://ntfy.sh`), `ring_s` (60), `later_min` (30), `realert_min` ([3, 6]), `notes_repo`, and for the look back
`review` (true), `review_effort` (`high`), `review_brain` (`""` = main), `lessons_max` (12); for the Android app
`today` (true) and `views` (false: Systems and the Notes map, below).

Secrets (`Calls.SECRETS` and `deploy.ensure_secrets`): `calls.call_secret`, `calls.connector_secret`,
`calls.ntfy_topic`, `calls.ntfy_key`, `calls.vapid_jwk`, `calls.vapid_public`, `calls.ntfy_token` (optional, from
`kurooto ntfy-token`: an ntfy account token, sent as `Authorization: Bearer` by `Calls.publish_ntfy` and the Worker's
`publish()`, each retrying once without it on a 401/403. It does *not* lift the limit for a free account: ntfy.sh
reports a free account's limits with `basis: ip` (250 messages a day for the address), counted like an anonymous
visitor, so on a campus network the token changes nothing; only a paid plan is counted apart. Since 0.7.0 the
Android app doesn't depend on ntfy while it's connected (below), which is the real fix. `check_ntfy_token(server, token)` asks `GET /v1/account`; `Calls.set_ntfy_token` keeps or clears it and
redeploys the line in the background, from `POST /api/phone/ntfy {token}` (the Phone tab, the setup page's call
box) and `kurooto ntfy-token`; `GET /api/phone` has `ntfy_token` and `ntfy_limited`. A 429 from ntfy emits
`calls_ntfy_limited`; `Calls.health` is not OK while any came in the last 7 days unless `Calls.phones_direct()`: every
paired Android phone was `connected` in the last device list (`Calls.devices()` keeps it, `_devices_seen`, trusted
`PHONES_FRESH_S` = 30 min); its advice is to update the app and let it run in the background, not a free account); also `gemini.api_key` (required) and
`calls.github_token` (set by Notes sync, `modules/notes_sync.py`, so the line can read notes while the computer is off).

## Deploying the line (`modules/calls/deploy.py`)

`deploy(...)` runs `Deployer.run`:

1. `prepare`: Node via `core/prereqs.py`; copy `FILES` from `data/worker` into `<app>/call-line` (`skip_built` leaves
   out `public/app.js` and `node_modules`); copy the phone app (`update/phone_app.py:current`: the one
   downloaded from the running version's signed release, else `data/kurooto.apk` from an older package) to
   `public/kurooto.apk`, with `public/kurooto-app.json` (`{"versionName"}`, `phone_app.TAG`) beside it for the
   pairing page's label (`pair.js`; removed when there's no app), and remembers the app's sha256 (`Deployer.apk`);
   `npm ci --ignore-scripts` (skipped when the `.kurooto-lock` stamp matches the
   lockfile); esbuild bundles `web/app.js`.
2. `sign_in`: `wrangler login --browser=false`, the URL opened in the user's browser. `wrangler_env` gives wrangler its
   own config home and strips `CLOUDFLARE_*`, `CF_*`, `WRANGLER_*` from the environment, so a developer's own
   Cloudflare login is never used or touched.
3. `subdomain`: the account's workers.dev subdomain through the Cloudflare API (created as `k-<hex>` if missing).
4. `write_config` / `render_toml`: fills `wrangler.template.toml`; the Worker name is `kurooto-<hex>` (`new_name`).
5. `ensure_secrets`, `wrangler deploy`, `wrangler secret bulk`.
6. Save `calls.worker` (with `apk`: the served app's sha256), then poll `/health` (24 times, 5 s apart).

`deploy()` runs one deploy at a time (`_one`; a second gets `BUSY`, `deploying()` tells).

Redeploys: `fingerprint` hashes the Worker source and the values baked into it (time zone, `live_model`,
`ntfy_server`, `notes_repo`, whether a GitHub token exists, the ntfy token, hashed); `needs_redeploy` compares it with `calls.worker.hash`.
`Calls._line_update` runs daily at 05:10 and redeploys unattended unless `updates.mode` is `off`.

A new phone app (0.5.21): `Updates.phone_app` (`update/service.py`, 2 min after a start and every 6 h) ends with
`_app_to_line`: when `deploy.app_behind(app)` (a line exists, an app is here, and `calls.worker.apk` isn't its
sha256; lines deployed before 0.5.21 have no `apk`, so they count as behind once), it books `calls.app_line` in
`APP_LINE_SOON_MIN` (1) minute, key `calls:app_line`, not replacing one already booked. `Calls._app_line` does
nothing once the line has the app; on a call (`availability.on_call_until()`) or while another deploy runs it books
itself again in `APP_LINE_BUSY_MIN` (10); otherwise it deploys unattended in a thread (`_spawn`). Each try emits one
`calls_line_updated` (`why="phone_app"`, `app`, and on failure `tries`, `error`); a failure is retried in
`APP_LINE_RETRY_MIN` (30) up to `APP_LINE_TRIES` (6), then the 05:10 update takes over. The second failure sends
one message (`why="calls.line_update"`). Tests: `tests/unit/test_apk_ship.py` (the `line` fixture fakes `deploy`).

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
   - sends `admin_later("ring", ...)`: the Worker's `Line.ring` mints a ticket (2 h; 3 h for alarms), sends a
     k1-sealed message to paired Android devices (`Line.toPhones`: their own connections first, and ntfy as a
     second path for rings, below), and an empty Web Push (VAPID) to every subscribed browser, whose service worker
     (`public/sw.js`) then fetches `/pending`;
   - when the line's WebSocket isn't connected, hands the ring to the line over HTTPS instead
     (`Calls.send_phones`: `POST <line>/send`, below) and publishes to ntfy from the computer (`Calls.publish_ntfy`)
     only when that fails (unreachable, an older line) or the line had no way to an Android phone; when connected,
     publishes only when its answer to `ring` (`Calls._ring_fallback`) doesn't say `"android": true` (an error, no
     answer, neither path worked) and doesn't say `"phones": 0` (a 0.7.0 line with no Android phone paired: nothing
     to ring). One ring, not two;
   - sends a Telegram notice with an Answer link (`Calls.link`, a `t1` ticket in the URL fragment), or an urgent
     "the call line isn't connected" notice;
   - schedules `calls.missed` at `ring_s + 30` s, or `ALARM_RING_S` (300, the Worker's and the app's alarm ring)
     + 30 s for an alarm.
4. `Calls._missed`: stops the ring (`stop-ring`, or `send_phones` when the line isn't connected), re-alerts at `realert_min` (not for alarms),
   and finally "Missed call" with Call back / In 30 min buttons; the owning module hears `call_outcome(..., "missed")`.
5. `Calls._scheduled_ring` skips a late or missed one-off when a line exists, assuming the line's cron placed it.

There is no FCM. Android rings through its own WebSocket to the line (0.7.0, `Direct`) and an ntfy JSON stream as
the fallback, both held by `ListenService`; browsers through Web Push.

## The Android app's own connection (0.7.0)

Why: ntfy.sh limits each internet address (a free account too: `GET /v1/account` says `basis: ip`, 250 messages a
day), and a campus shares one address, so rings were refused with 429 and phones stayed silent. Now the line delivers
to the app directly and ntfy is the fallback.

**Transport: a WebSocket to the Durable Object, hibernatable.** Chosen over Server-Sent Events or long polling
because only a hibernated WebSocket costs nothing while idle: an SSE stream or a held long-poll keeps the Durable
Object awake (billed duration the whole time; one phone all day would be ~10 800 GB-s of the free plan's 13 000), while
a socket accepted with `state.acceptWebSocket` lets it sleep, and the text `"ping"` is answered `"pong"` by
`setWebSocketAutoResponse` without waking it. Android 6 has no WebSocket client and the app uses no libraries, so
`android/src/.../WebSock.java` is a small RFC 6455 client over `java.net` sockets (TLS from
`HttpsURLConnection.getDefaultSSLSocketFactory()`, so `Tls`'s ISRG Root X1 applies on Android < 7.1.1, and the host
name checked with `HttpsURLConnection.getDefaultHostnameVerifier()`); text messages, fragments, ping/pong, close, masked
client frames, a 1 MB cap; a read timeout only between messages (one that stalls mid-message breaks the stream).

**The Worker** (`worker.js`):
- `GET /phone?after=<seq>` (an upgrade, header `x-call-secret: d1...`; Android devices only: 403 for web, 401 unpaired,
  426 without an upgrade). `Line.phoneConnect` closes the device's older socket (one per device), accepts with tags
  `["phone", "dev:<id>"]` and attachment `{kind: "phone", dev, at}`, sends `{"type": "hello", seq, version}`, then
  replays from the phone log: every item with `seq > after` if `0 < after <= log.seq`, else the last `PHONE_NEW_MS`
  (10 min). Then each message as `{seq, k1}`; the k1 is the same sealed JSON ntfy gets, plus `mid` (16 hex).
- Sockets are told apart by attachment: `Line.computers()` (no `kind: "phone"`; a socket from before 0.7.0 counts as
  the computer's) is what `online`, `lastSeen`, `tell`, `relay` and `connect` (which replaces only the computer's) use;
  `webSocketMessage` from a phone only refreshes its `at` and is otherwise ignored (a phone can't send `admin` or
  anything else to the computer's handler); `webSocketClose`/`Error` of a phone doesn't touch `seen`.
- `Line.phonesHeard()`: `{device id: ms}` from each phone socket's auto-response timestamp or `at`. Connected =
  heard within `PHONE_FRESH_MS` (6 min).
- `Line.toPhones(fields, assistant)` (rings, stops, inbox messages, clears, chat, outbox done, Today nudges, sealed
  reminders): no Android device paired, nothing; else seal once with `mid`, append to the phone log (`plog`: `{seq,
  items: [{seq, t, k1}]}`, last `PHONE_LOG_MAX` 60, `PHONE_LOG_MS` 6 h), send down every phone socket, and `publish()`
  to ntfy when it's a ring (tag `call`) or some paired Android device isn't connected. Returns true when a connected
  phone has it or ntfy took it. `publish(env, k1, priority)` now takes the sealed message.
- `POST /send` (no device key; `x-connector-secret`): `{fields, assistant}` (at most `SEND_MAX` 8000 bytes) through
  `toPhones`; answers `{ok, android, phones}` (`phones`: Android devices paired). `ring` answers carry `phones` too.
- `devices` (admin) gives Android devices `connected` and `heard` (ISO or null); `revoke` closes the device's socket
  (code 1008).

**The computer** (`modules/calls/__init__.py`): `Calls.send_phones(fields)` is what used to be a direct
`publish_ntfy` (the ring and its stop while the line's WebSocket is down): `_via_line` POSTs `/send` (10 s, through
`core/egress.py` as the line's own host); `None` (unreachable, 401/404 from a line before 0.7.0, not `ok`) or
`android: false` with `phones > 0` falls back to `publish_ntfy` with the existing token logic; `phones: 0` publishes
nothing. `Calls.devices()` keeps the list for `phones_direct()`; the Phone tab shows **connected** per Android phone.

**The app** (`android/`): `ListenService` runs `Direct` (`Direct.java`) beside the ntfy stream; both hand opened
messages to `ListenService.deliver`, which drops a `mid` seen before (`Prefs.firstTime`, `LinkRules.seen`: the last
`SEEN_MAX` 200 ids in prefs `seenIds`; a message without `mid`, from an older line, is never a copy), so a ring
arriving both ways rings once and a replayed message isn't shown twice. `Direct`:
- connects to `LinkRules.target(Prefs.url, Prefs.directSeq)`; after each `{seq, k1}` stores `directSeq`; a `hello`
  with a lower seq than stored (the log started again: a new line, a rotate) lowers it;
- pings with `"ping"` when `PING_MS` (60 s, elapsedRealtime, so time asleep counts) has passed, checked on every read
  timeout (`READ_MS` 20 s), after every message, on every line of the ntfy stream (ntfy's own ~45 s keepalive wakes
  the phone anyway) and from an inexact `setAndAllowWhileIdle` wake-up alarm every `KEEP_MS` (4 min; Doze spaces these
  to about one per 9-15 min; `ActionReceiver.KEEPALIVE`, `goAsync`, re-armed each time, which also restarts the service
  if Android stopped it); a ping unanswered for `DEAD_MS` (30 s) closes the socket;
- reconnects after `LinkRules.backoffMs` (2 s doubling to 60 s, plus up to a third at random); 404, 401, 403 or 426
  (a line before 0.7.0, or unpaired) waits `OLD_MS` (30 min) and ntfy carries everything meanwhile;
- on each connection sends the seal key and fetches Today if it's 5 minutes old, as the ntfy loop does.
`MainActivity`'s **This phone** card says whether it's connected now (`ListenService.direct()`).

**Mixed versions.** Old app + new line: no socket, so the device is never connected and everything also goes to ntfy,
as before (the extra `mid` field is ignored). New app + old line: `/phone` is 404, the app keeps to ntfy and asks again
every 30 minutes. New computer + old line: `/send` is 401, so `publish_ntfy` as before; no `phones` in ring answers, so
`_ring_fallback` behaves as before. The line itself is redeployed by the existing paths: the new phone app fetched
after an update (`Updates.phone_app` → `app_behind` → `calls.app_line` within minutes), else the 05:10
`_line_update` (`needs_redeploy`: the Worker source is in `fingerprint`). A deploy disconnects every WebSocket; the
computer and the phones reconnect by themselves, and the phones get what was sent meanwhile from the log.

**Cloudflare's free plan** (Workers Free; Durable Objects on it are SQLite-backed only), from Cloudflare's pricing and
limits pages as of 2026-10: 100 000 Worker requests a day; for Durable Objects 100 000 requests a day, 13 000 GB-s of
duration a day, 5 million rows read and 100 000 rows written a day, 5 GB stored; limits reset at 00:00 UTC, and past
one, operations of that kind fail. WebSockets: opening one is a request; incoming messages are billed 20 to 1 as
requests; outgoing messages and incoming protocol pings are free; a hibernated object isn't billed for duration (it
hibernates after about 10 s with nothing to do), and auto-responses don't wake it or add duration (the docs don't say
whether they count as requests; counted below as incoming messages). Up to 32 768 hibernatable sockets per object,
10 tags each, 32 MiB a message.
One phone connected all day: at most 1 440 pings a day (one a minute; far fewer asleep) = at most 72 billed requests,
plus one Worker request and one Durable Object request per reconnect (even 300 reconnects on a bad network is 600),
no extra duration while idle, and one row read and one written per message to the phones (a few hundred a day).
Ten phones (`MAX_DEVICES`) would still be well under 5% of the request limits. For comparison, what the line already
uses: the cron wakes the object every minute (1 440 requests, roughly 1 440 × 10 s × 128 MB ≈ 1 850 GB-s a day), and
the computer's connector pings every 30 s (at most 144 billed requests).

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

Other files in `<state>/calls/`: `rings.json`, `live.json`, `link.json`, `inbox.json`, `chat.json`, `today.json` (the
digest, time, revision and phone count of the last Today hand-over), `answer-nonces.json`,
`live-health.json`, `textcalls.json`, `lessons.md`, `transcripts/`, `searches.json` (each `search_notes` query, from
`Calls.run_tool` through `modules/curious.py:searched`, kept 8 days for Dreaming's curious line; retention's `calls`
kind clears it).

With Notes brain on, `search_notes` (`Calls._search`) asks `GBrain.search` first (keyword search when it finds
nothing or is busy), its description says "by meaning", and GBrain's `call_tools()` adds `note_timeline` with a hint
that `config_template` puts in the call's instructions.

## The Worker (`data/worker/src/worker.js`)

- `export default {fetch, scheduled}` and the Durable Object `Line` (SQLite-backed, migration v1). Cron `* * * * *`.
- Vars baked in at deploy: `OWNER_ID`, `TZ`, `PUBLIC_URL`, `VERSION`, `LIVE_MODEL`, `NTFY_SERVER`, `NOTES_REPO`.
  Secrets: `CALL_SECRET`, `CONNECTOR_SECRET`, `GEMINI_API_KEY`, `NTFY_TOPIC`, `NTFY_KEY`, `VAPID_JWK`, `VAPID_PUBLIC`,
  `NTFY_TOKEN` (always sent, empty without one, so clearing it clears the line's copy),
  optional `GITHUB_TOKEN`.
- Routes: top level `/health`, `/manifest.webmanifest`; the rest goes to `Line.fetch`. No auth: `/connect` and
  `POST /send` (0.7.0; both checked by the connector secret), `/pair/claim` and `GET /sealed/<32 hex>` (a sealed file: only its link's key opens it). Any valid key (device key `d1`, ticket `t1`, or a minted ticket):
  `/status`, `/token`, `/turn`, `/text-call`, `/call-report`, `/tool`, `/tasks`, `/transcript`, `/upload`. Paired
  devices only: `/pending`, `/answer`, `/chat` (GET and POST), `/outbox`, `/today`, `/view`, `/view/watch` (Android
  only), `/app-call`, `/ring-reply`,
  `/push/subscribe`, `/device/key`, `/upcoming` (bedside mode), `/shortcut`, `/shortcut/new`, `/shortcut/off`, `/phone`
  (Android only: the app's own WebSocket, 0.7.0). Only a
  Tell Kurooto link: `/tell/tk1.<id>.<secret>` (below).
- Admin operations over the WebSocket: `ring`, `stop-ring`, `pair-code`, `devices`, `revoke` (`device`), `ticket`,
  `bye`, `notify`, `notify-clear`, `sealed-put`, `sealed-claim`, `outbox`, `chat-say`, `file-put`, `today-put`,
  `view-put`, `tells`,
  `tell-revoke` (`tid`). An op's own fields never use `id`: that's the request's id, and `connector.admin(op, id=...)`
  replaced it, so the answer never matched (before 0.6.0, `revoke` sent `id` and `/unpair` timed out; it also deletes
  the device's Today copy and its Tell Kurooto link).
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
pushed for this (an iPhone must show something for every push); they poll `/outbox` or `/chat`. The Android senses
(`Senses.send`, 0.8.13) poll `/outbox` too: after a batch is queued they send nothing more until its `oid` is gone
from `waiting` (`SensesRules.maySend`), so at most one senses batch is ever on the line; before 0.8.13 a 12-hour
clock held them back instead.

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

## The chat's protocol (0.8.10: sessions, replies, files, changes, the being)

The authoritative description the phone app follows. Code: `modules/calls/chat.py` (`PhoneChat.take`, `_op`,
`_session_op`, `_msg_op`, `_being`, `say`, `status`), `modules/calls/sessions.py` (`Sessions`), `modules/chat.py`
(each session's AI context), `data/worker/src/worker.js` (`chat`, `chatSay`, `chatAll`, `chatSessionsPut`,
`chatStatusPut`, `toLinked`). Everything from 0.5.16 above keeps working unchanged: a message without `session`
belongs to `main`, `to` still works, `GET /chat` without `sessions=1` returns `main` only, and new fields are extra.

**Switches** (Settings → calls; each on by default, invisible until used): `calls.chat_sessions` (off: every message
is `main`, session ops are refused, the list holds `main` only; sessions and their context stay until it's back on),
`calls.chat_files_inline` (off: files from the computer come as the Open button only, files from the phone are
refused, a `chat=` upload is handled as an ordinary share), `calls.chat_edit` (off: `msg.*` ops refused),
`calls.chat_titles` (`"first words"` or `"ai"`). The `sessions` message carries `switches: {chat_sessions,
chat_files_inline, chat_edit}` so the app can hide what's off.

### Phone → computer

`POST /chat`, sealed (Android: `{"id", "k1"}`, the fields below sealed with the ntfy key, `id` repeated inside) or
plain (web: the fields beside `id`). Every body has `id` (16 hex, single use), `ts` (ms) and `n` (16-64 hex nonce),
as before. The Worker passes a plain body's `text`, `to`, `button`, `msg`, `ts`, `n`, `session`, `reply`, `file`,
`voice`, `op`, `args`, `title`, `target`, `on`, `upto`, `key`, `value` on; anything else is dropped.

A **message**:

| Field | |
|---|---|
| `session` | the chat: 16 hex, or `"main"`; missing means `main`. An id the computer hasn't seen makes that chat (titled from this message). Anything else: 400. |
| `text` | at most 4000 characters; may be empty when `file` is given |
| `reply` | the id of any message (yours or Kurooto's) this one replies to. Its text (200 characters) goes to the AI as context; if it's a feature's message that takes replies (a reminder, a check-in), it goes to that feature instead, as on Telegram |
| `to` | the 0.5.16 name for `reply`; same handling |
| `file` | `{"fid", "name", "mime", "size"}`: a file already sent with `POST /upload?…&id=<fid>&chat=<session>` (below). 404 `{"ok": false, "note"}` if it never arrived; 403 with `chat_files_inline` off |
| `voice` | `true`: `file` is a voice note; with Voice notes on it's transcribed and "Heard: …" is said first, else the chat says Voice notes is off |

Answer (as before): `200 {"ok": true, "id", "said": [message…]}`; offline `200 {"ok": true, "queued": true, "note"}`.
While an AI request it started runs, the chat gets `status` working, then idle.

**Files from the phone.** Upload first, the way Share does: `POST /upload?name=&note=&id=<fid>&part=&parts=&chat=<session>`
(`fid`: up to 40 of `[A-Za-z0-9_-]`, made by the phone). With `chat` the computer saves it to the inbox, records it in
`<state>/calls/shared.json` with `fid` and `session`, starts no filing job, and answers `{"ok": true, "saved", "fid"}`.
Offline it waits in the outbox like any upload, and the chat message after it waits behind it, so order holds. The
message then names it in `file`; the AI gets the path, and the session's later requests that talk of a file list the
files sent in that session (main lists main's, last 2 hours, as before).

An **op** (instead of `text`): `"op": "<name>"` and `"args": {…}`. Arguments may also sit beside `op` at the top
level, except `id` (that's the message's own), so `module` and `note.get` need `args`. Answers are JSON over HTTP;
a refusal is `{"ok": false, "op", "note"}` with 400 (bad), 403 (not allowed / off), 404 (no such message), 409.

| op | args | answer |
|---|---|---|
| `session.new` | `session` (16 hex, made by the phone), `title`? | `{"ok", "op", "session", "note", "sessions": [row…]}`; again with the same id: ok, the same chat |
| `session.rename` | `session`, `title` (≤ 80) | same; `main` can't be renamed |
| `session.delete` | `session` | same; `main` can't be deleted. The chat's AI context and its messages here and on the line go; files sent in it stay where they were saved |
| `session.pin` | `session`, `on` | same |
| `read` | `session`, `upto` (a message id) | same; the list goes to the line quietly (no notification) |
| `sync` | — | `{"ok", "op", "kind": "sessions", "srev", "sessions", "commands", "switches"}`, and the line gets the list too |
| `msg.edit` | `target`, `text` | `{"ok", "op", "msg": message}`; yours only, within 15 minutes, not deleted. The AI isn't asked again |
| `msg.delete` | `target` | `{"ok", "op", "msg"}`: yours only; text emptied, `file`, `quote`, `buttons` dropped, `deleted: true`. Kurooto's: delete it on the phone alone |
| `msg.pin` | `target`, `on` | `{"ok", "op", "msg"}` with `pinned`; any message |
| `settings.set` | `key`, `value` | sealed (below): `{"ok", "op", "key", "value", "note"}` |
| `module` | `id`, `on` | sealed: `{"ok", "op", "id", "on", "note"}` |
| `note.get` | `id` (a note's path in the notes folder without `.md`) | sealed: `{"ok", "op", "id", "text", "mtime"}` (front matter cut, 4000 characters, as `GET /api/note`) or `{"ok": false, "op", "id", "note"}` |

**The being's requests** (`settings.set`, `module`, `note.get`): only from the paired Android app (a `k1` body;
plain: 403), only now. Send them with the outer, unsealed `"live": true`: the Worker relays them even when the outbox
holds things, and with the computer off answers at once `503 {"ok": false, "offline": true, "note": "Your computer
is off, try again when it's on."}` instead of keeping them. One that still came from the outbox (an app that left out
`live`) is refused with 409 and `OFF_NOW`, never done late. They go through the dashboard's own handlers (`web/api.py`:
`POST /api/settings` → `_set`, `modules/enable`, `modules/disable`, `GET /api/note`), so the same checks apply ("not a
setting you can change here", "notify.app_chat takes a bool"...). One extra rule: `module` can't turn `calls` off from
the phone (it's what connects it). The answer is `200 {"ok", "op", "s1"}`, sealed for the phone that asked with the
key it gave the line (`Seal.java` opens it; the line can't), or `{"ok", "op", "k1"}` with the chat's key when that
phone gave none. Open it for the fields above.

### Computer → phone

A **chat message** (in `POST /chat`'s `said`, `GET /chat`, and the pushes) is the 0.5.16 one plus:

| Field | |
|---|---|
| `session` | always (`"main"` for Kurooto's own messages and everything from before 0.8.10) |
| `quote` | `{"id", "from", "text"}` (first 200 characters) on a message that replies to another: yours with `reply`/`to`. Kurooto's answers carry `re` (the message they answer), not `quote` |
| `file` | Kurooto's: `{"name", "size", "mime", "url"}`, `url` the sealed call-line link (`<line>/file#i=<fid>&k=<key>&n=<name>`, line.py f1): fetch `/sealed/<i>`, open with the key from the fragment (AES-256-GCM, `nonce ‖ ciphertext+tag`). The message keeps its Open button with the same `url` for older apps: hide a button whose `url` equals `file.url`. Yours: `{"name", "size", "mime"}` (no url: the phone has it) |
| `edited`, `deleted` | `true` once changed |
| `pinned` | `true`/`false` once pinned or unpinned |

Answers go to the chat of the message they answer (`reply_to "app:<id>"`); an answer for a chat deleted meanwhile
lands in `main`. Kurooto's own messages (`notify`) go to `main`.

**`kind: "status"`**: `{"kind": "status", "session", "state": "working"|"idle", "job"}`. Not kept, never through ntfy:
only to Android phones connected straight to the line (a `{k1}` frame without `seq`; sealed fields also have `title:
"stop"`, `tags: ["stop", "status"]`), and as `status` in `GET /chat?sessions=1` (`{<session>: {"state", "job"}}`, working
ones only, forgotten after 3 hours). Working is sent when a message started an AI request, idle when it ended
(`job_done`, `job_ended`, `job_cancelled`).

**`kind: "sessions"`**: `{"kind": "sessions", "srev", "sessions": [{"id", "title", "created", "updated", "pinned",
"last", "read"}], "commands": [{"name", "help"}], "switches"}`. `main` first, then pinned, then latest. `commands` are
Telegram's "/" menu (`/help`, each feature's commands that's on, the core ones, skills), at most 100. Sent to the line
after every session change (`chat-sessions`); the line pushes `{"kind": "sessions", "srev", "sessions"?, "tags":
["stop", "sessions"]}` (the list inline when it's small; never `commands`: fetch `GET /chat?sessions=1`). A `read`
change goes only to the phones connected straight to the line (the others get it with their next `GET /chat?…
&sessions=1`). `read` is the id of the newest message read on the computer's side (the dashboard's Chat page, or a
phone's `read` op). Since 0.8.16 the app takes it: `Chat.setSessions` and `Chat.putAll` (a mark may name a message
that only now arrived) run `takeReadMarks`, which moves the phone's own mark (`read` in `chat.json`, a local number
`ln`) forward to that message's `ln` when the phone has it in that session (`ChatRules.readMarks`, pure Java,
`test/ChatTest.java`), never back; a session left with nothing of Kurooto's unread loses its notification
(`ChatNotes.cancel`). Before, the app kept its own marks only, so reading on the dashboard didn't clear its badges. The line updates `last` and `updated` itself with each
message, so the computer doesn't push the list per message. Titles: the first message's first 6 words (40
characters; a file's name when there are none); with `calls.chat_titles` = `"ai"`, after the first answer a quiet,
text-only, low-effort request writes one (`then` action `calls.chat_title`). A title you set (`session.new` with
`title`, `session.rename`) is never replaced.

**Changes** (`msg.*`): the line changes the message in place and gives it a new `seq`; it goes only to phones
connected straight to the line, tagged `["stop", "chat-update"]` (older apps ignore it); the others see it on their
next `GET /chat?…&after=<seq>`. Merge by `id`.

### Call line

`GET /chat?after=<seq>&sessions=1` → `{"seq", "msgs": [every chat's messages with seq > after, in seq order],
"sessions", "commands", "switches", "srev", "status", "waiting", "done", "computer", "assistant"}`. Without
`sessions=1`: `main` only, as 0.5.16 (older apps). One `seq` counts across all chats.

Storage: `chat` (`{seq, msgs}`: main's messages and the shared seq), `chat:<id>` (`{msgs}` of each other chat),
`chatIdx` (the chats with a log), `chatSessions` (`{rev, sessions, commands, switches}`). Each chat keeps its last
50 messages, each at most 3 days; the list stays until the chat is deleted (a chat missing from a pushed list loses
its log). Admin ops: `chat-say {msg, assistant, update}` (`update`: change the one with that id, or add it if it
isn't there), `chat-sessions {rev, sessions, commands, switches, quiet}`, `chat-status {session, state, job}`.

### On the computer

`<state>/calls/sessions.json` (`Sessions`): `{rev, sessions: {id: {id, title, created, updated, pinned, last, read,
named}}}`, at most 100 chats; `named`: `fixed` (main), `you`, `words`, `ai`. `<state>/calls/chat.json` keeps the last
100 messages of each chat (7 days) for buttons, replies and changes. `modules/chat.py`: `main` and Telegram share
`chat/history.json` (6 turns from the last 2 hours, as before); each other chat has `chat/sessions/<id>.json` (40
turns, each side 4000 characters), and its newest turns up to 16 000 characters go with every request, however old.
`chat/session-jobs.json` remembers which chat a request was asked in, so its answer becomes that chat's turn after a
restart too (`core/jobs.py` passes `jid` to `record_turn`). `/new` in a chat starts that chat over. Retention
(`privacy.keep_days`, `/forget`) and gists cover the sessions' turns (`modules/chat.py:history_files`).
`Incoming` has `session` and `quote` for this.

### The chat on the dashboard (0.8.14)

The dashboard's Chat page (`web/chat_api.py`, `static/chat.js`; [web.md](web.md#the-chat-page-0814)) uses the chat
above without a protocol of its own. `PhoneChat.take`'s message handling is `_yours(mid, sid, text, to_id, path, sent,
voice, on)`; `typed(text, session, reply)` calls it for a message from the page (a fresh id; the chat must exist), so
it's kept, pushed with `chat-say` as `from: "you"` (the phones show it like one typed on another phone) and handled
as `Incoming(via="app")`; its `phone_chat` event carries `on: "dashboard"`. `press(mid, n)` is `_button`, `thread(sid)`
lists one chat, `change(op, args)` runs the session and message ops (never `BEING_OPS`). `PhoneApp.answer` checks the
seal and nonce, then `act(item_id, fields)` does the answer; the page calls `act` directly (behind the dashboard's
key). `PhoneChat.live` tells the dashboard's open pages about each change (`{"t": "chat"}`; nothing goes to the call
line for it, and nothing with `look.chat_page` off). Only what `chat.json` holds is shown: the app's and the page's
messages, their answers, and Kurooto's own messages that went to the `chat` channel; Telegram, Voice, the talk box and
the terminal aren't recorded there.

## Today and the phone's own alarm (0.6.0)

**The list.** `modules/calls/today.py:PhoneToday.snapshot()` builds it from `core/actions.py:today` (the dashboard's
Today API) plus the deadlines' parts and kinds and `core/threads.py:open_threads`: `{"v": 1, "date", "day", "classes":
[{"time", "name", "skipping"}], "events": [line], "due": [{"id", "title", "due", "when", "parts"?, "done"?, "acts":
["done", "+1"?] | "exam": true}], "reminders": [{"when", "what"}], "alarm": {"next", "daily", "at": [s...] (every
alarm still to ring: `Alarm.upcoming()`), "snooze_min", "reason"} | {}, "threads": [{"text"}], "questions": n}`. No
relative times ("in 3 hours"), so an unchanged day is byte-for-byte the same; cut to `TODAY_MAX` (40 000 bytes) by
dropping the longest list's last rows.

**Handing it over.** `Connector.push_state` calls `PhoneToday.push(connector)` after each state push (every 5 minutes,
and on `poke()`). It asks the line for its devices, seals the list (plus `"made"`) for each Android device with a
`seal` key (`line.seal_s1`, as Reminders with the lid shut does) and sends `today-put {rev, seal: {device id: s1
token}, changed}` when the digest of list + keys changed, `poke()` was called, or the last hand-over is `REFRESH_S`
(15 minutes) old. `changed` (the list itself changed) makes the Worker nudge Android phones. Events in `CHANGES`
(deadline, alarm, reminder, thread events, `action`, `button_tapped`) call `poke()` through `core/events.py:subscribe`
(registered in `Calls.start`), and so does the line's `device_key` event. `calls.today = false`: one `today-put {seal:
{}, off: true}` and nothing more. An older line answers `unknown op` and is left alone until it's redeployed.

**The Worker.** `today-put`: a lower `rev` than the stored one is refused (`stale`); each token (`TODAY_TOKEN`, an s1 of
at most 110 000 characters, for an Android device) is stored under `today:<device id>`, devices no longer listed lose
theirs, the index `today` keeps `{rev, devs, at (ISO), off}`; `changed` or `off` publishes `{"tags": ["stop", "today"]}`
to ntfy (`stop`: older apps ignore it). `revoke` deletes the device's copy. `GET /today` (a paired device): `{"today":
this device's token | null, "at": when it came | null, "off", "computer": "online" | "offline"}`.

**Taps.** The app sends Done / +1 as a chat message `{"id", "ts", "n", "today": {"id": <deadline id>, "do": "done" |
"+1"}}` (k1-sealed, through `/chat`, so it waits in the phone outbox like any chat message); `PhoneChat.take` passes
`today` to `PhoneToday.act`, which checks the action and the id (open, not a quiz or exam) and runs
`App.callback("dl:<id>:<do>")`, the deadline Telegram message's own button. Nothing is said in the chat; the note
comes back in the answer (`200 {"ok", "note"}`, `400` bad or not tappable, `410` gone or not open).

**The app.** `Today.fetch` (on opening, on the `today` nudge, when the ntfy stream reconnects more than 5 minutes after
the last fetch) first calls `Line.sendSealKey` (a no-op once `sealSent` matches; 0.6.1: before, only the stream's
reconnect retried a failed send, and a stream can stay up for days, so a phone whose first send failed got no list),
then opens the token with `Seal`, keeps it in `today.json` and hands `alarm` to `Alarms.update`.
`TodayTab.kt` draws it on the Today pane (0.8.10: `TodayPane`, a bento grid; `HomeState.today`; `Today.listener`
re-reads it when a fetch lands), with Done / +1 under a tapped deadline (`MainActivity.dueAct` -> `Chat.today`, waiting
kind `today`).

**The alarm on the phone.** `Alarms.schedule` sets the next of the computer's times and a snooze tapped here
(`AlarmPlan.next`, which leaves out the one that last rang here and anything within `SAME_S`, 5 minutes, of it) with
`AlarmManager.setAlarmClock` (shown in the status bar, exempt from Doze), or `setAndAllowWhileIdle` when Android 12+
refuses exact alarms (`SCHEDULE_EXACT_ALARM` on 12, `maxSdkVersion` 32; `USE_EXACT_ALARM` from 13). It's set again
after every change, after it rings, and on boot (`BootReceiver`). Firing: `ActionReceiver.ALARM` →
`Alarms.fired` → `ListenService.localAlarm` (the running service, or a start with `ACTION_ALARM`; if Android won't
start it, the ringing notification alone) → `ringLocal`: rings as the wake-up call with since `local:<s>`, Stop and
Snooze, on `CallActivity`'s ringing screen (`local` extra, no call link). One alarm, not two:
- the call for an alarm arriving while `local:` rings joins it (`ListenService.ring`): no second sound, the
  notification becomes the call's, and a showing `CallActivity` gets the call's intent (Answer appears);
- the phone's alarm doesn't ring when an alarm call within `SAME_S` rang already (`Alarms.callRang`/`lastCall`);
- Stop or Snooze (local or the call's) is recorded (`Alarms.replied`: `alarmDone` = "<s>:decline|later:<when>"); a
  call for the same alarm arriving within `HANDLED_KEEP_S` (30 minutes) is answered that way at once with
  `/ring-reply`, without ringing (`AlarmPlan.answered`). Snooze also sets the phone's own snooze
  (`alarm.snooze_min` from the list), so it rings again with nothing else reachable.
The app never adds an alarm of its own beyond that snooze: what it rings is the computer's list, which only has the
alarms `core/tap.py` lets through.

**Notification buttons.** `Buttons.pick` (plain Java, `TodayTest`) chooses a message's quick buttons by label:
counting (`+<n>`), `Done`, then snoozes (`Snooze...`, `+<n> min|h`), at most 3; `Buttons.addDone` when it snoozes but
has no Done. `Inbox.show` uses them for kinds `reminder` and `deadline` (Reply moves to the answer window when there's
no room; the app's own Done answers `{"dismiss": true}`, which `PhoneApp.answer` already takes: off every phone);
`ListenService.chatNote` for any chat message (its own Done just cancels the notification). A sealed reminder
(`ListenService.sealedNote`) gets Done and +10 min / +1 h, kept on the phone (`ActionReceiver.SEALED_SNOOZE` shows it
again with an inexact alarm): the computer is asleep when those come.

## Systems and the Notes map on the phone (0.7.0)

The dashboard's SYSTEMS and NOTES map in the Android app, drawn by the dashboard's own code
(`web/static/views/`, see [web.md](web.md#the-shared-drawings-webstaticviews)); off by default (`calls.views`; the
dashboard's Phone card has the switch, through `POST /api/settings`; `GET /api/phone` has `views`).

**The copies.** `modules/calls/views.py`:
- `notes_snapshot()`: `web/live.py:Graph` (its own instance, so the folder is read again only where files changed) with
  `graph_layout`, then `trim_notes(payload)`: `{"v": 1, "kind": "notes", "nodes": [[path, title, mtime, words]] (path
  order), "links": [[i, j]] (places in nodes), "layout": {research, project}, "research": {<project>: {name, topics}},
  "total": {notes, links}, "cut": {notes, links}}`. Past `NOTES_MAX` (1500) the best-linked notes stay (ties: newest);
  past `LINKS_MAX` (6000) the links between the least-linked notes stay (a book index's hundreds of "Seen in" links go
  first). Never a note's text.
- `systems_snapshot()`: `web/live.py:Vitals.board()` and `cells_of()` (shared with the dashboard's `Vitals.snapshot`):
  `{"v", "kind": "systems", "name", "version", "sys": {cpu, mem}, "cells": [{id, title, act, events}] (on only),
  "features": [{id, title, events, last, next, proc: {cpu, mem, threads, up, n} | null, down, idle, intermittent,
  health?}], "core": {cpu, mem}, "link": {connected}, "today": {"items": [{at, end, kind, state}]} (no names), "health":
  [{id, title, detail}] (at most 8)}`. `health` on a feature is its `/health` line (`core/health.py:board`).
- Sizes (a made-up 896-note folder, 3362 links): notes 97 KB of JSON, 20 KB sealed; a 2961-note one is cut to 1500
  notes and 4223 links, 144 KB, 32 KB sealed; Systems with 13 features 3 KB, 0.6 KB sealed.

**Sealing (`line.py` v1).** `put(c, kind, snap, keys)` adds `"made"`, then `pack_v1`: gzip (mtime 0), then f1 with a
fresh 32-byte key (the blob); `head_v1` = `"v1 <kind> <rev> <key b64url> <sha256 hex of the blob>"`, sealed s1 for
each Android device with a `seal` key (as Today). The blob goes once, whatever the number of phones. `rev` is
`max(last + 1, time_ns // 1000)` per kind (`<state>/calls/views.json`, under the `calls-views` lock).

**Handing over.** `view-put {view, rev, part, parts, data (base64), size and keys on part 0}` in `PART` (96 KB) pieces,
in order; at most `VIEW_MAX` (2 MB sealed). `Connector.push_state` calls `PhoneViews.push(c)` after Today's: turned
off (and it was on), one `view-put {off: true}`; on, the notes map goes when its digest (with the phones' keys)
changed and the last went `NOTES_MIN_S` (180) ago or the phones changed, or it's `NOTES_REFRESH_S` (an hour) old. The
event `phone_views_pushed` (view, phones, bytes, notes, cut) on a change; `phone_views_failed` on an error (an older
line's `unknown op` is left alone). `setting_changed` for `calls.views` pokes the connector (`PhoneViews.on_event`,
subscribed in `Calls.start`).

**Watching.** The app posts `/view/watch` every 20 s while Systems is open; the Worker passes it at most every 5 s per
phone (`WATCH_MS`) as the event `views_watch` (only while the computer is connected: never queued) and answers `{ok,
told, computer}` (`{ok: false, off: true}` when off; 403 for a web device). `Calls.on_event` hands it to
`PhoneViews.watch`, which sets `until = now + WATCH_S` (30) and, if not running, starts `_watching` on the connector's
loop: a Systems copy every `SYSTEMS_S` (4) until `until` passes, the connection drops or it's turned off (one
`phone_views_watching` event per stretch). The phones' keys are asked for at most every `KEYS_S` (60) there; `revoke`
clears that cache.

**The Brain (0.8.10).** Kind `brain` (`VIEW_KINDS` in the Worker): `PhoneViews.brain_snapshot()` is
`mind/console.py:snapshot(app, phone=True)` (see [mind.md](mind.md#0810-the-brain-console-mindconsolepy-get-apibrainconsole)).
Sent only while watched: the app posts `/view/watch?kind=brain`; the Worker passes `views_watch` with `kind: "brain"`, rate-limited
per phone and kind; `PhoneViews.watch(m)` hands that to `watch_brain`, which runs `_watching_brain` (a copy every `BRAIN_S` 6 s
until `WATCH_S` passes without a word; event `phone_views_watching` with `view: "brain"`). With `calls.views_brain` off,
`mind.console.on` off or Brain off, one copy `{"kind": "brain", "off": true, "why"}` replaces the kept one, at the next watch or at
once on the `setting_changed` / `module_disabled` event (`brain_event`, from `on_event`); then nothing more goes. The phone fetches it
with `/view?kind=brain` and shows it with `views/brain.html` (`KurootoView.take`, as phone.html). Never pushed with the state push.

**The Worker.** `Line.viewPut`: part 0 (with `size`, `keys`: only paired Android devices, `VIEW_KEY` tokens) starts a
pending copy (`views.pend[kind]`, replacing one still coming in); a `rev` not above the kept one's is refused (`stale`);
parts in order (`v:<kind>:<rev>:<n>`, at most `VIEW_PART` 96 KB and `VIEW_PARTS` 24); the last part swaps it in (the old
parts go), so only the newest whole copy is kept, under `views` `{off, notes, systems: {rev, parts, size, keys, at},
pend}`. `off` deletes everything (`viewsDrop`, also after `kurooto rotate` in `fresh()`); `revoke` drops the device's
keys. `GET /view?kind=notes|systems` (a paired device): `{"view": {rev, at, key: this device's s1 head, data: the blob
base64url} | null, "off", "computer"}` (400 for another kind).

**The app.** `Views.fetch(c, kind)` (`Line.sendSealKey` first, as Today) opens a new `rev` with `ViewSeal.open` (s1 head,
sha256, AES-GCM, gunzip, at most 16 MB unpacked) and keeps it in `view-<kind>.json` (`{snap, rev, at, computer, off,
fetched, old}`); `Views.watch` posts `/view/watch`; unpairing deletes both (`Prefs.forget`). `ViewsActivity` (extra
`mode`): a WebView loading `https://appassets.androidplatform.net/views/phone.html`, every request answered by
`shouldInterceptRequest` from the APK's assets (`views/*.html|js|css`, `fonts/*.woff2`) and anything else 404, so the
page reaches nothing; no file or content access, no DOM storage, no new windows, Safe Browsing off (8+), no navigation,
and no JavaScript interface: the app hands data in with `evaluateJavascript("KurootoView.take(...)")` (`{mode, snap,
computer, reach, off, palette}`; the palette is the app's colours: `k_bg`, `k_fg`, `k_primary`, `k_view_lav`, `k_view_pink`,
`k_view_peach` (Material You's accents on 12+, `values-v31`), `k_sand`, `k_rose`, `k_bad`, `k_card`). Systems: watch every 20 s, fetch every 4 s (20 s while the computer is asleep); notes:
fetched when opened. A WebView older than Chrome 58 (`MIN_CHROME`) gets a message instead. The Gradle task
`kurootoViewAssets` copies `src/kurooto/web/static/views/*` to `assets/views/` and the Public Sans files to
`assets/fonts/` at build time. The main screen's **Views** pane (0.8.10: `Pane.VIEWS`, hosted by `ViewsTab`) opens it; at its top two buttons, **Systems** and **Notes map**, switch between them (`show(mode)`: the page is
loaded afresh, as it draws one kind), and it opens on the one looked at last (`Prefs.viewMode`) unless the extra `mode`
says. With `demo` (debug and dev builds) it shows `Demo.view(kind)`, made-up copies of both, and fetches nothing.

**The being and the Brain (0.8.10).** `PhoneViews.being_snapshot(board)` adds `"being"` to each Systems copy while
`calls.views_being` is on (default): `cells` (every feature, on or off: `{id, title, on, act, events}`), `jobs` (the
running ones and the last `BEING_JOBS` 10: `{status, title}`), `schedule` (the next 12: `{when, what}`), `calls`
(booked), `link` (`{connected, beat}` or `{off}`), `sys` (`Vitals.machine()` cut to what the coil draws: cpu, cores,
mem, swap, gpu, 3 disks, battery, 4 temps, cpu_name, load), `events` (the last 40 within `BEING_EVENT_S` 10 minutes:
`{kind, ts}`, plus `sensor`/`value` for `senses_phone`), `voice` (`Voice.status()` cut down, or null), `look` (`theme`,
`hints`), and `settings_digest`; `settings` (`Api._settings()` without `tips`) and `brain` (`brainview.view` islands,
comps as `[id, name, on, state, [], key, ""]`) only when their digest changed, `SETTINGS_S` (60) passed, or a phone
started watching (`watch(m)` resets `being_sent` for a device new to the stretch, `watchers`). With 13 features a copy
is ~7.5 KB of JSON (2 KB gzipped) with the settings, ~5.5 KB (1.5 KB) without.
The app (`ViewsPane`, `ViewsTab`): modes `being` (`views/being.html`), `brain` (the brain-console part's
`views/brain.html` and `brainconsole.js`, handed its copy with `KurootoView.take` as Systems is; the copy
`view-brain.json` from `GET /view?kind=brain` every `BRAIN_MS` 8 s, watched with `POST /view/watch?kind=brain` every
`WATCH_MS`, since the Brain is sent only while watched; demo builds hand it no copy), `systems`, `notes` (`phone.html`). Being watches
and fetches as Systems does, fetches the Notes map once per opening, and keeps the last `settings`/`brain` in the kept
copy when a new one comes without them (`carry`). `serve` adds the being's files at the dashboard's paths
(`/static/being*.js`, `/static/vendor/three/*.js`, `/static/body/anatomy.bin|cerebrum.vol`, copied by
`kurootoViewAssets`) and two answers of its own: `/ask?op=&a=` (only in `being`; on the WebView's IO thread) and
`/state?depth=&gl=`. `/ask` is `BeingRules`: the fields `{op, args, id, ts, n}` sealed k1 with the chat key, POSTed to
`/chat` as `{id, k1, live: true}` (the line passes it on now or answers 503 `offline`; an older line's `queued` counts as
off too, and chat.py refuses a queued op), the answer `{ok, op, s1}` opened with this phone's own key (`Seal`) or
`{k1}` with the chat key, a refusal with its `note` passed on. Ops: `settings.set {key, value}`, `module {id, on}`,
`note.get {id}` (chat.py `_being`, the chat-core part: the dashboard's own `POST /api/settings`,
`modules/enable|disable`, `GET /api/note`) and `voice.mute {on?}` (chat.py needs a branch for it: until then the
computer answers "doesn't know that yet"). `beingOk()`: WebView 80+ (`??` in being.js) and WebGL 2 (the page says
`gl=0` once, kept in the `kurooto-views` preferences); else Being shows Systems with a note. The first opening of
Views after the update shows the being (`beingShown`). `ViewsTab`: an Expressive connected `ButtonGroup` of
`ToggleButton`s; `BackHandler` while `depth() > 0` calls `KurootoBeing.back()`. Tests: `tests/unit/test_being_phone.py`,
`android/test/BeingTest.java`.
**Organ pages** (0.8.10, `Prefs.viewsOrgans`, on; Look → Organ pages in Views; off: `ViewsTab`'s `WholeViews`, the
above as it was): `OrganViews.kt`. A floating pill of connected `ToggleButton`s, Brain · Heart · Senses · Memory and a
More toggle with a menu (Systems, Notes map, Brain console: `pane.show(m)` as before). `ViewsPane.organs(reduced)`
(before `page()`) sets `organ` (`Prefs.viewOrgan`, `ORGANS`), and `hand` adds `"only"` and `"still"` to the being's
copy; `showOrgan(o)` calls `KurootoBeing.only(o)` on the page as it is (the WebView and its WebGL stay; from More it
loads `being.html` once). `/state?rev=` (a new list) makes it read `KurootoBeing.organState()` with
`evaluateJavascript`; `organState()` is that JSON, and the watcher re-reads it into `OrganState`. Under the drawing a
floating panel: the organ's name and line, Solid · Cutaway · X-ray on Brain, a `LazyRow` of part cards (the picked one
filled, scrolled into sight when picked on the drawing), and the part in full (rows, bars, Brain parts, features and
the yes-or-no settings as `Switch`es: `pane.setting`, `pane.feature`, sealed through `/ask` as before; a neighbourhood's
notes; a note's text). Taps call `pane.pick(kind, key)`. The bars' heights go to the page as `pane.inset(top, bottom)`
in dp, re-sent when the page loads. Depth on an organ page is 0 or 1 (a part), so Back leaves from the organ.
Memory's framing (0.8.13, `being.js` `memFit`/`memRing`/`memFrame`, organ pages only): the notes' centroid and 95th
percentile radius (group units) after each build and when the layout worker finishes; the feature lights on a ring at
`1.3 r + .12` (their lines from the cloud's edge, re-added if a rebuild took them off); the camera on the centroid at
the distance that fits the ring in `beingPhone.room(H)` (the share of the height the bars leave, from `inset`) and the
width, again when that share or the aspect changes and on Back. The bloom's radius is .1 there, and (0.8.15) the page
renders at the screen's own density (`FULL`, devicePixelRatio up to 3, through `GLR()` in `size()`, re-run when `only()`
moves to or from Memory) with the notes at the dashboard's size in CSS pixels; the other organ pages keep the 1.5 cap.

## The settings guide in the app (0.8.10)

`assets/settings-help.json` is written by `tools/gen_settings_guide.py` (committed, checked by `--check`, the same entries
as the dashboard's `static/settings-guide.js`): `{page, groups: [{id, title, intro}], settings: {key: {g, tip, what,
values, default, when, cost, needs, anchor}}, parents: {key: {g, tip, children, anchor}}}`, about 340 KB. Keys are the
computer's settings (`brain.main`) and the app's own as `app.<Prefs key>` (`app.vivid`, `app.senses.steps`,
`app.places.on`); a test checks each of those names a key `Prefs`, `SensesRules` or `Places` keeps. `SettingHelp.kt`:
`SettingHelp.load(context)` reads and parses it once on `Dispatchers.IO` (`parse(json)` is plain), `rememberSettingHelp()`
gives the `Guide` to a composable once it's loaded (null before, or with no asset), `guide.helpFor(key)` finds an entry
(`"vivid"` and `"app.vivid"` alike; null for a key with no entry), `guide.search(words)` matches every entry's text, and
`SettingHelpSheet(guide, entry, onClose)` shows it in a `ModalBottomSheet` (its group, the key, the tip as the headline,
what it does, then values, default, when to change it, what it costs or sends and what it depends on on a tonal card; a
box's settings as a card each; **In the settings guide** opens the entry's anchor on the site). The Settings pane calls
it on a long-press. A setting added in the app needs its `app.<key>` entry in `tools/settings_guide/26-phone-app.toml`.

## Tell Kurooto, the iPhone Shortcut (0.6.0)

Apple doesn't allow generating a Shortcut file, so the phone shows a recipe with a link to paste.

- **The link.** `<line>/tell/tk1.<8 hex id>.<32 hex secret>`, made by the Worker for a paired device:
  `POST /shortcut/new` (device key; any older link of that device is dropped, so one per device) answers
  `{ok, id, token, url}`; `GET /shortcut` says whether the device has one (`{shortcut: {id, created, used} | null}`);
  `POST /shortcut/off` drops it. Stored in the Durable Object under `tells`: `{<id>: {hash: sha256(secret), device,
  created, used}}`. Making one emits the event `shortcut_made` (`Calls.on_event` notifies, Calm reason
  `calls.shortcut_made`, exempt "security").
- **Scope.** `Line.fetch` routes `/tell/tk1.` before `auth()`, which never accepts a `tk1` token, so the link opens no
  other route (401 everywhere else). `Line.tellSend` takes `{"text"}` as JSON, a form or plain text (at most
  `TELL_TEXT`, 4000), checks the hash and that its device is still paired, sets `used`, and builds the body the web
  app's chat would (`{device, at, id, ts, n, text, via: "shortcut"}`: no `button`, no `to`): relayed to `/chat` (so
  `PhoneChat.take` handles it like any phone message, nonce and all) or queued in the phone outbox as `chat`. The answer
  is `text/plain` for the Shortcut to speak: the immediate `said` texts joined, or the queued note, or the refusal
  (401 revoked/wrong, 400 empty, 405 not POST, 413, 507).
- **The computer's side.** `Calls.shortcuts()` (`admin_wait("tells")`; `[]` from an older line) and
  `Calls.shortcut_revoke(id)` (`tell-revoke`, `tid`); `GET /api/phone` has `shortcuts`, `POST /api/phone/shortcut/revoke
  {id}`; the Phone tab lists them with Revoke. `revoke` (unpairing) drops the device's link; `Line.fresh` (after
  `kurooto rotate`) deletes `tells` with the devices.
- **The pages.** `public/shortcut.js` renders the recipe into `#shortcut` (on `settings.html`, and on `pair.html` once an
  iPhone in standalone mode has paired: `data-auto` makes a link if the device has none). The link is kept in
  `localStorage` (`kurootoTell`) only; if the line's id differs (revoked or remade elsewhere), the page drops it and
  offers a new one. `public/qr.js` (`KurootoQR.svg(text)`): byte mode, level M, versions 1-20, drawn on the phone so the
  link never leaves it; `tests/unit/test_shortcut.py` compares it module by module with segno (segno pads a
  byte-aligned stream with a zero byte where the standard has 0xEC, so the test uses data that fills each version).

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
| v1 | a view (0.7.0): the blob `nonce ‖ ciphertext+tag` of gzip(snapshot) under a fresh AES-256-GCM key, and the head `"v1 <kind> <rev> <key b64url> <sha256 hex of the blob>"` sealed s1 per phone (Python `line.pack_v1`/`head_v1`/`open_v1`, Java `ViewSeal`; the Worker only stores it) |
| Web Push | VAPID ES256 JWT (`line.vapid_keys`, `worker.js:webPush`) |

`tests/fixtures/call-vectors.json` holds k1, t1, s1 and v1 vectors (v1: `tests/unit/test_views.py`,
`android/test/ViewsTest.java`), checked by `tests/unit/test_calls.py`
(`test_k1_and_t1_match_the_shared_vectors`, and `test_the_worker_agrees_with_the_vectors` running
`tests/js/vectors.mjs` in Node), `android/test/CryptoTest.java` (k1, s1; CI job `android`), and
`tests/unit/test_lidsafe.py` (s1). Changing any format means changing all three and the vectors in one commit.

## The Android app (`android/`)

- The build (0.7.0): Gradle, run only through `android/build.sh`, which keeps the old contract (`tools/release.py sign
  --apk` runs it with `KUROOTO_KEYSTORE` / `KUROOTO_KEYSTORE_PASS` / `KUROOTO_KEY_ALIAS` and takes
  `android/build/kurooto.apk`; without a keystore it makes `kurooto-debug.apk`; see
  [release-and-updates.md](release-and-updates.md#the-phone-app-sign---apk)). minSdk 23, target 35. Pinned: Gradle
  8.14.6 (build.sh downloads `gradle-8.14.6-bin.zip` once and checks its SHA-256, hard-coded), AGP 8.13.2, Kotlin
  2.3.21 with the Compose compiler plugin, Compose BOM 2026.06.01 (Compose 1.11.4), activity-compose 1.12.4,
  compileSdk 36. material3 is **1.5.0-alpha18**, not the BOM's 1.4.0: 1.4.0 keeps the Expressive APIs
  (`MaterialExpressiveTheme`, `MotionScheme.expressive()`, `ButtonGroup`, `SegmentedListItem`, `ToggleButton`,
  `LoadingIndicator`, the wavy indicators, `MaterialShapes`, the emphasized type) internal or doesn't have them, and
  alpha18 is the newest that builds with compileSdk 36 and AGP 8 (alpha19 on, like newer Compose, need compileSdk 37
  and AGP 9.1).
  - `android/settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`, `proguard-rules.pro`: one project (android/
    itself) whose source sets point at the existing `src/` (Java and Kotlin), `res/`, `assets/` and
    `AndroidManifest.xml` (no `package` or `<uses-sdk>` any more: Gradle sets the namespace and the SDK levels, and
    the label through the `appLabel` placeholder). No wrapper jar is committed. The task `kurootoViewAssets`
    (`ViewAssets`, added to every variant's assets with `addGeneratedSourceDirectory`) copies
    `src/kurooto/web/static/views/*.{html,js,css}` to `assets/views/` and `static/fonts/public-sans-latin*.woff2` and
    `OFL.txt` to `assets/fonts/` at build time, so the drawing code ViewsActivity serves has one copy in the repository.
  - build.sh: `GRADLE_USER_HOME` defaults to `gradle-home` next to the SDK (`$ANDROID_HOME/../gradle-home`; one already
    set wins), `ANDROID_USER_HOME` to a folder in it (nothing goes in `~`). Gradle runs with `--no-daemon`, its
    project cache and Kotlin's folder in `build/` (Kotlin compiles in Gradle's process). versionCode and versionName
    are computed as before (from `pyproject.toml`) and passed as `-PkurootoVersionCode` / `-PkurootoVersionName`;
    `KUROOTO_APP_ID` (optional) becomes `-PkurootoAppId`, another application id for a test build (`--dev` adds
    `.dev` to it).
    Gradle makes an unsigned APK; build.sh zipaligns and signs it with apksigner as before. The debug key is
    `kurooto-debug.keystore` in `GRADLE_USER_HOME`, so it outlives `android/build`.
  - Release: R8 on, with `-keep class io.github.avtarfr.kurooto.** { *; }` (only the libraries shrink) and the
    `@JavascriptInterface` methods kept; English resources only (`localeFilters`); no dependency block in the APK.
    About 1.4 MB (0.6.x: 0.2 MB).
  - `build.sh --dev`: build type `dev` (debuggable, `applicationIdSuffix ".dev"`, label "Kurooto dev"), so it installs
    beside the real app; signed with the debug key: `build/kurooto-dev.apk`. Debug and dev builds compile
    `src-demo/Demo.kt` (made-up Today, Inbox, checklist, an update and copies of Systems and the Notes map for
    ViewsActivity, `Demo.view`; `Demo.ON` true); release builds compile
    `src-nodemo/Demo.kt` (empty, `ON` false), so no sample data ships. MainActivity's extras in those builds: `demo`
    (true: the tabs without pairing, with the sample data; Call, Chat, answers and Done / +1 only say "Demo"),
    `palette` (a named palette instead of Material You, e.g. `kuro`), `hour` (a float: the sky at that hour); `tab`
    (today, inbox, phone) works in every build. For example
    `adb shell am start -n io.github.avtarfr.kurooto.dev/io.github.avtarfr.kurooto.MainActivity --ez demo true --es tab inbox`.
  - `build.sh --lint`: Gradle's `lintRelease` with only `NewApi` and `InlinedApi` (Java and Kotlin), failing on any;
    CI runs it. `build.sh --test` is unchanged (plain javac and java, no Gradle): `test/CryptoTest.java`,
    `test/SpeechTest.java`, `test/CardsPlacesTest.java` (`CardRules`, `PlaceRules`), `test/TodayTest.java`
    (`Buttons`, `AlarmPlan`), `test/DockTest.java`, `test/ViewsTest.java` (`ViewSeal`) and `test/CallRulesTest.java`
    (`CallRules`, 0.8.7).
  - CI (`ci.yml` job `android`, `android-emulator.yml`) sets `GRADLE_USER_HOME` to the runner's temp folder and needs
    the network for Gradle's first run; `smoke.sh` is unchanged.
- `build.sh --test` also runs `test/LinkTest.java` (0.7.0: `LinkRules`, and `WebSock` against a local server:
  handshake, fragments, ping/pong, masking, close, a 404) on a plain JVM.
- The Chat pane (0.8.10, the "Rail" design; `ChatPane.kt`, `ChatRail.kt`, `ChatThread.kt`, `ChatComposer.kt`,
  `ChatModel.kt`, `ChatFiles.kt`, `ChatNotes.kt`, `ChatRules.java`, the store in `Chat.java`):
  - **Store.** `chat.json` gains `v: 2`, `sessions` (the computer's list, kept), `commands`, `read` (session → the local
    number `ln` read up to; unread = Kurooto's messages after it), `archived` (this phone only), `hidden` (deleted on
    this phone, never brought back by a sync) and `ln` on each message. `Chat.migrate` puts every message from before
    into `main`. At most 300 messages per session and 1500 in all. `Chat.putAll` writes a batch in one go (sync used
    to rewrite the file per message). `Chat.demo`: the whole store in memory (`--ez demo true`; `src-demo/ChatDemo.kt`).
  - **Sending** (the protocol is the computer's, "The chat's protocol (0.8.10)"). Everything to the call line runs on
    `Chat.IO`, one thread, in order (a new session's op before its first message). Fields sent (sealed k1 as before):
    `session` (left out for `main`), `reply` (any message's id; plus the old `to` when the quoted message is Kurooto's,
    so old computers and the features that asked still get it), `file {fid, name, mime, size}` (and `voice: true` for
    a voice note) after the bytes went up through `/upload?…&id=<fid>&chat=<session>` in 512 KB parts, and ops as
    `{"op", "args": {…}}`: `session.new {session, title?}`, `session.rename {session, title}`, `session.delete
    {session}`, `session.pin {session, on}`, `msg.edit {target, text}`, `msg.delete {target}`, `msg.pin {target, on}`,
    `read {session, upto}`, `sync {}`. An op's answer is applied at once (its `sessions` list, its changed `msg`); a
    refusal's `note` shows as a snackbar (`Chat.say`). A session id is `Chat.newId()` (16 hex).
  - **Receiving.** `ListenService.chat` hands every push tagged `chat`, `chat-update`, `status` or `sessions` to
    `Chat.incoming`: `kind: "status"` sets `Chat.working` (not stored; ten minutes at most without an "idle"),
    `kind: "sessions"` replaces the list (`Chat.setSessions`: a session made here in the last ten minutes stays until
    the computer lists it; one the computer no longer lists goes, with its messages) and, when the list or the commands
    aren't inline, syncs; anything else is a message, new or changed, merged by id (`message` maps the push's `message`
    / `time` and keeps `session`, `quote`, `file`, `edited`, `deleted`, `pinned`, `re`, `reply`, `buttons`). `Chat.sync`
    asks `GET /chat?after=<seq>&sessions=1` (every chat's messages, `sessions`, `commands`, `switches`, `status` as
    `{session: {state, job}}`). The computer's `switches` hide what's off: "+" and New chat (`chat_sessions`), attach,
    camera and voice notes (`chat_files_inline`), Edit (`chat_edit`). A Kurooto message's Open button whose url is its
    `file.url` is hidden (the file shows instead); Kurooto's answers carry `re`, shown as a quote only when the message
    they answer isn't right above.
  - **Drawing.** `ChatStore.read` turns the store into immutable values off the main thread (sessions with unread and
    working, each thread's rows newest first with date separators and sender runs worked out), coalescing reloads;
    the pane only reads `ChatStore.snap`. The thread is a reversed `LazyColumn` with keys and content types; the rail's
    drag and the drawer are a `DraggableState` settled with `animate` and the motion scheme's `defaultSpatialSpec`
    (the fling's speed carried; `snap()` with Remove animations); the drawer and the bubbles move with `offset {}` /
    `graphicsLayer`; the active avatar morphs (`Morph` of its `MaterialShapes` shape into `Square`) in the layer.
    Markdown is `ChatRules.blocks` / `inline` (test/ChatTest.java). Photos decode at their drawn size on
    `Dispatchers.IO` into a 24 MB `LruCache`, in a fixed 4:3 frame so the list never jumps.
  - **Files from the computer**: `file.url` is the f1 link; `ChatFiles.local` fetches `<line>/sealed/<i>` and opens it
    (AES-256-GCM, key from the fragment) into `cache/chat/`; open and share go through the FileProvider
    `${applicationId}.chatfiles` (`res/xml/chat_files.xml`: only `cache/chat-open/` and the camera's `cache/chat-cam/`).
    Voice notes: `MediaRecorder` AAC in `.m4a`, sent as `audio/mp4`.
  - **Notifications** (`ChatNotes`): one per session, tag `chat` for `main` (the old one) and `chat:<id>` otherwise, id 9;
    `MessagingStyle` (Android 7+; 6 gets BigText) with the unread messages, Reply (`RemoteInput`, action
    `CHAT_REPLY`) and Mark read (`CHAT_READ`) through `ActionReceiver`, and the newest message's quick buttons as before
    (`ListenService.chatNote` now calls `ChatNotes.again`). None for the session on screen (`ChatStore.visible`).
  - **Ways in.** `ChatActivity` (translucent, no UI) starts MainActivity with `chat_open` (a session) and `chat_type`;
    `ChatOpen` (one `OnNewIntentListener` per activity) brings the pane to Chat and opens it. Notifications, the Talk
    widget, bedside mode and old shortcuts keep working.
  - **Switches** (`ChatPrefs`, preferences file `chat`, shown by `ChatSettings` in Settings → Chat): notify,
    inline_reply, swipe_reply, markdown, fold, auto_photos, commands, enter_sends (off), haptics.
  - `build.sh --test` runs `test/ChatTest.java` (`ChatRules`).
- Bedside mode (0.6.0): `BedsideActivity` (theme `Kurooto.Call`, `showWhenLocked`, immersive): clock, date, next
  alarm (the first `alarm` call from `GET /upcoming`, or `AlarmManager.getNextAlarmClock()` if earlier), up to three
  calls (reasons hidden while a secure keyguard is locked), the waiting count, and the Talk button (`Line.callLink` then
  `CallActivity`, which shows over the lock screen itself); Chat and the main screen go through
  `requestDismissKeyguard` (8+). `/upcoming` (device key) answers `{calls: [{at, reason, alarm}] from the pushed
  schedule (next day, at most 8), waiting, computer, assistant}`; read every 5 minutes. Window brightness and colours
  by the hour come from `Dock` (pure Java, `test/DockTest.java`); a tap sets 0.3 for 15 s; `FLAG_KEEP_SCREEN_ON` while
  plugged in (`bedsideKeepOn`). Opening by itself: `BedsideActivity.watch()` registers `Watcher` (POWER_CONNECTED,
  TIME_TICK) from `ListenService.onCreate`; in the chosen hours (`bedsideAuto`, `bedsideFrom`, `bedsideTo`; `Dock.within`
  crosses midnight) plugging in, or the hours starting while charging, opens it: `startActivity` below Android 10, a
  full-screen notification on channel `bedside` (silent, `ID_BEDSIDE` 9) from 10. Opened that way (`auto`), unplugging
  closes it. While it's visible, `ListenService.ring` also starts `CallActivity` directly (with the screen kept on,
  Android shows a full-screen intent only as a heads-up). Its settings are in Settings → Bedside
  (`SettingsPane.kt`, 0.8.10; the hours dialog is `BedsideActivity.hours`; the Alarms pane's Bedside card opens it); `MainActivity` with the extra `bedside` opens it
  (`smoke.sh` uses that).
- Components: `MainActivity` (Kotlin, Compose: the panes or pairing, below), `PairActivity`,
  `CallActivity` (WebView with the `KurootoApp` JS bridge), `AnswerActivity`, `ChatActivity` (0.8.10: only a way in that hands
  over to MainActivity's Chat pane; the chat's store and the outbox's waiting list are `Chat`, `chat.json` in the app's files), `ShareActivity` (share to Kurooto, with the
  device key so it can wait on the line),
  `ListenService` (foreground, type `remoteMessaging`, holds the line's own connection, `Direct`, and the ntfy stream),
  `BootReceiver`, `ActionReceiver`,
  `PlacesActivity` + `PlaceReceiver` (location reminders), `QuickNoteActivity`, `NoteTile`, `TalkWidget` /
  `TalkWideWidget` (below).
  Helpers: `Crypto`, `Seal`, `Line`, `Net`, `Prefs`, `Inbox`, `Chat`, `Speech`, `Tls` (adds ISRG Root X1 on API < 25),
  `B64`, `Ui` (the framework screens' look), `Dock` (bedside mode's rules), `CardRules` (check-in and quiz cards),
  `Places` + `PlaceRules`; 0.6.0: `Today` (the Today list), `Alarms` and `AlarmPlan` (the phone's own alarm), `Buttons`
  (quick notification buttons). 0.7.0, Kotlin: `MainActivity` + `HomeState`, `Home.kt`, `TodayTab.kt`, `InboxTab.kt`
  (with `InboxCard`), `PhoneTab.kt`, `Kit.kt`, `Theme.kt`, `Sky.kt`, `Demo.kt`; Java: `Direct`, `WebSock`, `LinkRules` (the line's own connection).
- Check-in and quiz cards (0.6.0): `PhoneApp.item` adds `card` ("checkin" / "quiz", `phone.py:card_of`, from the
  map kind or the buttons' `chk:` / `qz:` / `ql:` data) to the item; the Worker stores items as they are, so `/pending`
  has it (the ntfy push doesn't need it). The Inbox tab shows such an item as an `InboxCard` (answer box, choices and
  buttons in rows by `CardRules.perRow`, drafts kept by item id while the process lives), which answers
  through `Line.answer` like `AnswerActivity` (sealed, single use, the outbox with the computer off) and re-reads the
  list 2.5 s after a delivered answer. Without a `card` field (an older computer) `CardRules.kind` goes by the text.
  `PhoneApp.answer` turns a reply's buttons (the quiz's self-grading) into the next phone item instead of dropping
  them, so the grading is the next card.
- Location reminders (0.6.0): `modules/reminders.py` `PLACE` + `at_place` (setting `reminders.places`, off) send a
  phone item of kind `place` / `place_every` straight through `PhoneApp.send` (not `notify`: it isn't for Telegram),
  title = the place's name, text = the reminder. On the phone `Inbox.show` and `MainActivity.loadWaiting` give it to
  `Places.adopt`, which keeps it (SharedPreferences `places`: places with lat/lon/radius/inside/last, reminders by the
  place's `PlaceRules.key`) and dismisses the item on the line. `PlacesActivity` turns it on (the battery text first,
  then `ACCESS_FINE_LOCATION`, and `ACCESS_BACKGROUND_LOCATION` on 10+), saves the current fix under a name
  (`Places.here`: GPS and network, 50 m or the best in 30 s) and edits reminders. Each place is one
  `LocationManager.addProximityAlert` (150 m, no expiry, a mutable explicit `PendingIntent` to `PlaceReceiver`, keyed
  by a `kurooto-place:<id>` data URI); `App.onCreate` sets them again (they don't survive a restart or an update).
  `PlaceRules.fire`: only entering from outside (a place saved where you stand starts as inside; Android also says
  "entering" when an alert is set while you're there), at most once in 20 minutes; once-reminders are removed when
  said. No Play services; nothing about where the places are leaves the phone.
- Widgets, Quick note and the tile (0.6.0), no laptop or Worker changes:
  - `TalkWidget` (1x1, `res/xml/widget_talk.xml`, layout `widget_talk.xml`) opens `ChatActivity` with the extra
    `type` (focus the box, keyboard up; ChatActivity passes it on to the Chat pane, 0.8.10). `TalkWideWidget` (2x1, a subclass only because Android tells providers apart
    by component) adds the newest item of `GET /pending` (`Line.waiting`, what the Inbox tab lists), kept in `Prefs.widgetLine`. It looks it up in `onUpdate` (`updatePeriodMillis` 30 min, `goAsync`), on
    `TalkWidget.refreshSoon` (debounced 3 s: `Inbox.show`, `Inbox.cancel`, `Prefs.savePairing`), and takes
    MainActivity's own fetch through `TalkWidget.waiting(c, items)`; with no 2x1 placed nothing is fetched.
    `Prefs.forget` redraws them unpaired. The Today screen could feed the 2x1 the same way (`Prefs.setWidgetLine` +
    `TalkWidget.draw`). Colours are the `k_*` resources, so the widgets follow light/dark and Material You;
    `drawable-v31/k_widget.xml` takes the launcher's corner radius.
  - `QuickNoteActivity` (`Kurooto.Sheet`, exported so every launcher can open the static shortcut; it sends only on
    Save) uploads the note as `quick-note.md` with `Line.upload`, exactly as `ShareActivity` does with shared text: the
    computer's `Calls._upload` saves it to the notes inbox, the phone outbox holds it while the computer is off
    (`Line.WAITING`, `Chat.waitFor`). An unsent note stays in `Prefs.noteDraft`. Opened by the static shortcut
    (`res/xml/shortcuts.xml`, `android.app.shortcuts` meta-data on MainActivity; launchers before 7.1 ignore it) and
    `NoteTile` (`TileService`, API 24, `@TargetApi(24)`; `startActivityAndCollapse(PendingIntent)` on 14+, the
    Intent form below; `unlockAndRun` when locked).
- Counting buttons (0.5.20, a deadline's **+1**): `Inbox.counts(button)` is a label `+<n>` (the Worker passes only
  labels). `Inbox.send` shows such an item again after a tap that went through or waits on the line (`setOnlyAlertOnce`,
  the answer's note as its text) instead of `done()`; the computer keeps the item open for it (`PhoneApp._button`).
  `ListenService.chatNote` (the chat's notification) adds them as actions (0.6.0: with Done and the snoozes,
  `Buttons`), `ActionReceiver.CHAT_TAP` sends them with `Chat.tap` (the outbox when the computer is off) and shows the
  waiting or failed note, a +1 kept; one that went through comes back as a new chat message with the button again.
- The main screen (0.7.0) is Jetpack Compose with Material 3 Expressive. Since 0.7.6 so are `AnswerActivity`,
  `QuickNoteActivity`, `ShareActivity` and `PairActivity` (small floating sheets: `Sheets.kt`'s `SheetActivity` and `Sheet` over a
  dimmed screen, window theme `Kurooto.Sheet`: translucent, tap outside to close), and `PlacesActivity` and `ChatActivity` (full pages
  over the sky: `PageActivity` / `Page` (the chat became the main screen's Chat pane in 0.8.10, below);
  0.8.10, the Rail look: `Sheet` floats at the bottom (12dp margins, `shapes.extraLargeIncreased`, a drag handle), springs in
  and out with `motionScheme.defaultSpatialSpec`/`fastSpatialSpec` (an `Animatable` read in `graphicsLayer`, the scrim in
  `drawBehind`), follows a drag on the handle or an overscroll of its content (`NestedScrollConnection`) and settles or
  closes past 120dp or a fling, and shrinks with the predictive back gesture (`PredictiveBackHandler`; the five activities
  have `enableOnBackInvokedCallback`). `SheetActivity.finish()` plays the closing slide first (straight away when not
  resumed; a 900ms fallback) and turns the window animations off (`overrideActivityTransition` / `overridePendingTransition`).
  Pieces: `SheetHeader` (mark, title, line), `SheetBubble` (Kurooto's message as a chat bubble), `SheetButton`/`SheetTonal`
  (56dp, `ButtonDefaults.MediumContainerHeight`), `SheetFoot` (the status line beside the buttons when short, above when
  long, so the sheet doesn't jump). `Page` is a `LazyColumn` (`LazyListScope` content, a round back button, the title):
  Places keys its cards (place id, `w:<name>` for waiting ones) and moves them with `animateItem` and the motion scheme, and
  reads and writes `Places` on a single-thread executor (`load()` → `Snap`). `ShareActivity` sends through a `ShareSink`
  (`NotesInbox` = `Line.upload`; `sink(intent)` is the one place to add a chat-session sink later) and lists each item
  (name and size from `OpenableColumns`, off the main thread) with its state. Dev builds: `demo` on Quick note and Share
  sends nothing (Share shows made-up files when nothing was shared); an Inbox item with a `demo-` id answers "Demo: nothing was sent.";
  `ChatActivity.visible` and `ID_NOTE` stay static for `ListenService`). Since 0.8.7 so are bedside mode and the call screen,
  each keeping its Java activity as the entry point with every rule, intent extra and lifecycle hook (`ViewsActivity` is a thin
  wrapper too, see Views below), and everything else (services, receivers, calls, alarms, crypto, notifications, widgets) stays
  framework Java:
  - `BedsideActivity` (a `ComponentActivity`, still Java) writes what to show into `BedsideState` (Compose state: clock, date,
    alarm line, up to three calls, the waiting line, status, Talk's label and enabled, Dock's `ink`/`dim`, `night`) on every
    `paint()`; `BedsideScreen.kt` draws it on black (`KurootoTheme(forceDark = true)`): the clock (a third of the width, 56 to
    160sp, light), date, alarm, the calls in a floating card, the waiting pill (`openInbox()`), the Talk button (expressive
    `ButtonDefaults.shapes()`, `talk()`), the status line, Chat (`openChat()`) and Close in a floating pill. At night
    (`Dock.warm`) the Talk fill is the old warm `#2A1408` with Dock's ink and the cards are 7% ink; by day the scheme's primary
    and `surfaceContainerHigh`. Taps on the background call `tapped()` (0.3 for 15 s). The window brightness, keep-on flag,
    immersive mode, lock-screen flags, battery receiver, `auto` closing, `/upcoming` every 5 minutes, `requestDismissKeyguard`,
    `Watcher`/`open()` and the Phone tab's `hours()` dialog are as before. The pure parts moved into `Dock`
    (`brightness(hour, tapped)`, `alarmLine`, `waitingLine`, `test/DockTest.java`). Extras: `auto`, and in dev/debug builds
    `demo` (`Demo.upcoming()`, nothing fetched or sent) with `hour` (int) to look at any hour's colours.
  - `CallActivity` (a `ComponentActivity`, still Java) keeps all of a call's plumbing: the intents (`url`, `ringing`,
    `reason`, `since`, `alarm`, `local`; `singleTask`, `onNewIntent`), `FLAG_KEEP_SCREEN_ON`, show-when-locked and turn
    screen on, `STREAM_VOICE_CALL`, the WebView and its `KurootoApp` bridge, `MIN_WEBVIEW` and the browser fallback, the
    microphone request, routing and the proximity wake lock, turn-by-turn speech, `showing`, and the clean-up in
    `onDestroy`. `Prefs.newCallScreen` (Phone tab → Switches → **New call screen**, default on), read in `onCreate`, picks
    the screen: on, `EdgeToEdge.enable` with dark bars and `CallScreen.kt` (`ringing()`: always dark over `Sky` at 0.6, a
    turning, breathing `Cookie9Sided` badge, still with reduced motion, `displaySmallEmphasized` caller, and
    Decline/Later/Answer as 64dp expressive buttons in a floating pill; `call()`, 0.8.16, below); off, the framework
    screen from before 0.8.7 (`showRingingClassic`, the `fitsSystemWindows` frame with the call page itself). The
    decision of what an intent does, the ringing words, which replies reach the line and `withAuto` are `CallRules`
    (pure Java, `test/CallRulesTest.java`). Dev/debug `demo`: a made-up ring with no link; its buttons send nothing and
    Answer shows `Demo.callPage()`, a stand-in with the call page's element ids that acts out a short call (connects,
    a moving level, a few lines; Mute, Speaker, the mic gate and Hang up change it as in a real call) with no `KurootoApp`
    bridge, so no microphone, nothing fetched and no audio changes. Extra `placed` goes straight into it (Today's Call in
    demo does that; `MainActivity --ez demo true --es call in|ring` opens it from adb, since `CallActivity` isn't exported).
  - **The call itself in Compose (0.8.16).** Up to 0.8.15 only the ringing screen was redrawn: `page()` put the call
    line's web page (`public/index.html`, dark green, "Ready", the mic gate, Hang up / Mute / Earpiece) in the frame, so
    every answered call, every call placed from the app (`requestCall`, straight to `answer()`) and every call answered
    from the notification (`answerPi`, `ringing` false) looked like the old page. Now `CallScreen.call()` keeps the
    page running the call (microphone, Live or turn by turn, the transcript to your computer, the `KurootoApp` bridge)
    in a 1 dp `AndroidView` under the sky (hidden from accessibility), and draws the call from `CallUi`: `CallMirror`
    is the page's `window.KurootoScreen`; on `onPageFinished` (not `about:`) the activity runs `CallScreen.MIRROR`, a
    `MutationObserver` that posts at most every 60 ms a snapshot of `#who`, `#reason`, `#status` (and its class),
    `#call` (text, `end`, disabled), `#mute`, `#out`, `#int`, `#gatebox`/`#gate`/`#gateval`, `#level` (width, open
    when its colour is `--ok`), `#mode`, `#heard`, `#talk` (text, `data-state`, disabled) and `#log` (the last 80 lines
    with their class, only when the count or the last line's length changed). The buttons press the page's own
    (`CallScreen.press(id)`, only `call`, `mute`, `out`, `int`, `talk`; `gate(v)` sets the slider and fires `input`), so
    the page tells the line, mutes and calls `toggleSpeaker` exactly as before; Hang up before the page is ready, or
    with no call on, just closes. Speaker's state is the activity's own (`route()` sets `CallUi.speaker`), since the
    page's button names where a tap goes. No change to the page is needed, so it works with a call line not yet
    updated; `tests/unit/test_calls.py` checks every id the mirror reads is on the page and on the demo stand-in. A page
    that isn't the call page (`ok: false`: no `#call` or `#status`) or says nothing within `MIRROR_WAIT_MS` (8 s) is
    shown itself, full screen with the bars' insets on `k_call_bg`, as before (`CallUi.raw`). The look: always dark,
    Material You or the chosen palette (`KurootoTheme(forceDark)`), `Sky` at 0.45; before anything is said a 148 dp
    `Cookie9Sided` badge in the middle (it swells with the level while the gate is open, turns while the call is on,
    still with reduced motion), `displaySmallEmphasized` caller, reason and a status pill (`live` primaryContainer,
    `err` errorContainer); then a floating header card and the transcript as bubbles (Kurooto primaryContainer left, you
    secondaryContainer right, notes as tertiary pills, the partial `#heard` faded). A floating card holds Talk (72 dp),
    Interrupt and the level with **Mic gate** (its `Slider`, 0.6 to 3 in 0.2 steps, folds away); the floating pill bar has
    Mute and Speaker (`ToggleButton`s, `ic_mic_off`, `ic_volume_up`/`ic_phone_in_talk`) and Hang up (`ic_call_end`, error
    colours), or Close and the page's Call/Answer when no call is on. "New call screen" off keeps the page itself.
  - `MainActivity` (a `ComponentActivity`, edge to edge, `enableOnBackInvokedCallback` for the predictive back
    gesture) holds `HomeState` (Compose state: paired, name, pane, settingsGroup, waitingSheet, unread, today, waiting,
    queued, the status lines, update, tick) and does what the screens ask (`refresh`, `pull`, `loadWaiting`, `requestCall`, `chat`, `dueAct`, `answer`,
    `checks`, `pickTone`, `unpair`, `pair`, the update check); the composables only draw it. `tick` is bumped on resume
    and after a setting changes, and what reads settings (the checklist, ringtones, bedside, the alarm toggle) reads it.
    The pane and the open Settings group survive rotation and `recreate()` (`onSaveInstanceState`; a restored pane wins
    over the intent's extra); the extra `tab` picks a pane (`chat`, `today`, `alarms`, `views`, `settings`; `inbox` opens
    Chat with the waiting sheet, `phone` Settings → This phone); a launcher intent in `onNewIntent` goes back to Chat.
    0.8.10: the palette is `Prefs.palette` ("you" or `Apricot.NAME`): `setContent` wraps `Home` in `ApricotTheme` (a
    nested `MaterialExpressiveTheme` with only the colour scheme) inside `KurootoTheme`.
  - **0.8.10, the panes** (`Home.kt`, `Nav.kt`): `Panes` draws the sky, then one `SharedTransitionLayout` around
    `Transition<Pane>.AnimatedContent` with `contentKey = { it == CHAT }`: the move between Chat and the rest slides
    (the motion scheme's `defaultSpatialSpec`) and Today/Alarms/Views/Settings stay one content under the horizontal
    `KNav` (`Others`, an inner `AnimatedContent` that fades through with a 0.96 scale). The transition comes from
    `rememberBackTransition` (a `SeekableTransitionState` that `PredictiveBackHandler` seeks towards Chat; Settings uses
    it for group → grid). Each pane's content gets `LocalNavShared` (the layout) and `LocalNavPane` (its
    `AnimatedVisibilityScope`). `KNav(vertical)`: the capsule is `sharedBounds(key = "knav")` (`RemeasureToBounds`, its
    content cross-faded), each icon `sharedElement("knav-<PANE>")` and the pill `sharedElement("knav-pill")`; the
    horizontal pill slides with an `Animatable` read in `Modifier.offset { }`. `Modifier.paneStagger(i)` (for Chat's
    rail) adds a 20 ms-per-row delayed slide (`Delayed`, a `FiniteAnimationSpec` wrapper, since springs have no delay).
    ChatPane gets no room (`PaddingValues()`): it has no bar and handles its insets itself; the other panes get the
    bar's room. `WaitingSheet` (a `ModalBottomSheet` with `InboxContent`) is hosted by `Panes` on `ui.waitingSheet`.
    The bento kit: `PaneGrid` (pull to refresh around a two-column `LazyVerticalGrid`, a status-bar scrim), `wide`,
    `paneTitle`, `Tile` (a press scales it in `graphicsLayer`), `TileLabel`, `tileColor`. `TodayTab.kt` (`TodayPane`:
    `NowCard` with a `Canvas` ring, count tiles, `DayStrip` drawn in one `Canvas`, `slots()` parses "09:30–11:00" and
    "16:30 Event"), `AlarmsPane.kt` (the hero from `alarmTimes(today)`, `Numeral`s, `Tones`, `Bedside`), `SettingsPane.kt`
    (`SetGroup`, the tile ↔ page container transform as `sharedBounds("set-<GROUP>")`, `index()`/`search()` over every
    setting, the group pages; the old `PhoneTab.kt` is gone), `InboxTab.kt` (`InboxContent`, `InboxCard`, `WaitingBar`).
  - `Home.kt` (0.7.5: `Prefs.floatingBar` on, the default, draws `FloatingBar`, a `HorizontalFloatingToolbar` over the page
    in a `Box` and the pages get `FLOAT_ROOM` at their end; off: the docked `DockedBar` below):
    `Pairing` (unpaired) or `Tabs`: a `Scaffold` with Material 3 Expressive's `ShortNavigationBar` (Today,
    Inbox with a `Badge` of what waits, Views, Phone), the tabs cross-fading with the motion scheme's fast effects spec (none
    with "Remove animations", `LocalReducedMotion`), each tab's state kept by a `SaveableStateHolder`; Back on Inbox or
    Phone goes to Today (`BackHandler`). `TABS` also takes a destination that opens another screen (`Tab.opens`):
    **Views** is a page of the screen (0.8.0): `ViewsPage` hosts `ViewsPane` (the WebView, extracted from `ViewsActivity`, with `build/resume/pause/destroy`) in an `AndroidView`, its lifecycle bound by a `DisposableEffect` on the activity's lifecycle; `ViewsActivity` stays as a thin wrapper for intents. `Tab.opens` remains for destinations that open another screen. `TabPage`
    is a tab's page: a `TwoRowsTopAppBar` sized as `LargeFlexibleTopAppBar` (the expanded title in
    `displaySmallEmphasized`, Today's date in `displayMediumEmphasized`; it folds on scroll, `exitUntilCollapsed`),
    `PullToRefreshBox` with the expressive `LoadingIndicator`, and a column at most 640dp wide that keeps clear of the
    navigation bar and the keyboard.
  - Before 0.8.10: `TodayTab.kt` (the date as the title, the assistant's initial in a `MaterialShapes.Cookie9Sided`, Call and Chat
    as a connected `ButtonGroup` of large buttons, then Today's sections: the alarm with its toggle, classes and events,
    due with a still `LinearWavyProgressIndicator` for parts and Done / +1, reminders, threads, "N questions wait in
    Inbox", "as of", the update button), `InboxTab.kt` (cards answered in place, the rest opening `AnswerActivity`,
    what waits for your computer; a `SoftBurst` when nothing waits), `PhoneTab.kt` (the checklist with Fix, location
    reminders, ringtones, bedside mode, this phone with Unpair behind a confirmation).
  - `Kit.kt`: `Heading`, `Group` of `Item`s (Material 3 Expressive's `SegmentedListItem`: 2dp gaps, small inner
    corners and large ones at the group's ends, a pressed row morphs; an on/off `Item` has a `ToggleButton` and switch
    semantics), `ShapeBadge` (something inside a `MaterialShapes` polygon), `Footnote`, `Dim`, `Said` + `SaidLine`,
    `KCard` (0.8.10: `container` makes a hero card in a scheme colour), `rowColor()` (the surface, a little translucent over
    the sky; Vivid from `LocalVivid`). Containers with a translucent colour set their `contentColor` themselves: such a colour
    has no matching "on" colour, and text would fall back to black. 0.8.10: `toneOf(i)` (the palette's tonal pairs, or the
    scheme's three containers), `IconBadge(shape, icon, tone)`, `Overline` (a card's small capital label), `KField` (a filled,
    fully rounded `TextField` with a placeholder and room for a trailing action) and `RoundAction` (a round `FilledIconButton`
    with `IconButtonDefaults.shapes()`). New icons are `ic_sheet_*` and `ic_place_*` (Material icons' paths).
  - `Vivid.kt` (0.7.5, `Prefs.vivid`, default on): a Material colour scheme from `com.materialkolor`'s `SchemeExpressive` made
    from the wallpaper's primary (`Vivid.seed`; below `MIN_CHROMA` 16 Kurooto's olive), used by `KurootoTheme` for the
    Material You palette on Android 12+ and on Android 11 and older; off: the system's own tonal scheme (Android 11 and
    older: Kuro). `rowColor(accent)` and `KCard(accent)` stain the surfaces with the primary, secondary or tertiary container.
    `Sky.kt`'s nerves and rim are about twice as strong.
  - `Theme.kt`: `KurootoTheme(palette, dynamic, forceDark)` is `MaterialExpressiveTheme` with the expressive type scale
    (its emphasized display and headline styles a step bolder, semibold, as the phone's Roboto reads medium as regular at
    display sizes, and 0.8.10 a little tighter), 0.8.10's shape scale (8/12/16/24/32dp, `largeIncreased` 28,
    `extraLargeIncreased` 36, `extraExtraLarge` 48) and `MotionScheme.expressive()`, or a scheme of `snap()`s with "Remove
    animations" (so anything that takes its motion from `MaterialTheme.motionScheme` stops by itself; `LocalReducedMotion`
    stays for the rest). `dynamic` (default): the palette chosen in Look, `Palettes.chosen(c)` (`palette` in the app's
    preferences, the same key as `Prefs.palette`: `you` for Material You, the default so an update changes nobody's
    colours, `apricot` or `kuro`; `Palettes.choose(c, name)` sets it,
    `Palettes.choices` lists them for a Settings row); `dynamic = false`: the named `palette` (the dev builds' `palette`
    extra). `Palettes.apricot` is the Rail mockup's dark values (`build-specs/0.8.10/mockups/rail.py`) and, for light mode,
    the same hues' tones (primary 40, containers 90, on-containers 30). `LocalKurooto` adds Kurooto's ok, bad, hot (unread
    badges) and tonal pairs; `LocalVivid` the Vivid switch, read once per screen.
  - `Sky.kt`: the background behind the tabs and pairing, in the SYSTEMS view's language (`home.js`): the sky tinted by
    the hour (keyframes, light and dark), two deep soft forms, a mesh of specks, the core as a membrane (three wobbling
    rims and a nucleus, `home.js` `blob()`'s formula, breathing about every nine seconds) that crosses the top right
    with the hour like the site's sun, six tapered nerves drifting like threads, and grain. Android 13+: one AGSL
    `RuntimeShader` drawn at half resolution into an offscreen layer and scaled up (about 3 ms of GPU a frame on the
    test phone); Android 12: the same from Canvas paths and gradients; 6 to 11: the same, still. About 14 frames a
    second while the activity is started (`repeatOnLifecycle(STARTED)`), none otherwise, none with "Remove
    animations". Strength 1 on Today and pairing, 0.35 on Inbox and Phone; Today's scroll moves it (parallax).
- The framework screens' look is Material 3 from the framework alone (no AndroidX or Material Components), views
  built in code:
  - Colours are resources named after Material 3's roles (`k_bg`, `k_card`, `k_fg`, `k_dim`, `k_primary`,
    `k_tonal`, `k_ok`, `k_bad`, ...): `res/values/colors.xml` is the web pages' light "kuro" palette, `values-night`
    the dark one, and `values-v31` / `values-night-v31` map Material You's `system_accent1_*` / `system_neutral*_*`
    onto the same names on Android 12+. `k_call_*` (the ringing screen, from `call.css`) and `k_brand` (notifications)
    never change. Light or dark follows the system (`-night`); Android 9 and older are light. Later (the Compose
    app): the named themes too, from `core/palette.py:export()` (each theme's flavours and their role → hex maps).
  - Themes (`res/values/themes.xml`): `Kurooto` (full-screen pages, the app's default), `Kurooto.Dialog` (`AnswerActivity`,
    `PairActivity`, `ShareActivity`: a 28dp-cornered card, `drawable/k_dialog.xml`) and `Kurooto.Call` (`CallActivity` and
    `BedsideActivity`, always dark; their Compose screens draw over it). `Base.Kurooto*` only pick the framework's light or dark `Theme.Material` parent.
  - `Ui.java` builds the views: `page(activity)` / `dialog(activity)` set the content and return the column to fill
    (`page` keeps clear of the system bars, which Android 15 draws over; `page(activity, behind)` puts a view behind
    the scrolling column, full screen; 0.7.0: `dialog` sets the window to 90% of the screen's width, at most 560dp,
    because on Android 16 the dialog theme's minimum width didn't hold); `appBar(activity, title, onBack)` is the small top app bar for a screen that
    isn't one scrolling page (the chat: its root is `fitsSystemWindows`, so on Android 15 it keeps clear of the bars
    and the keyboard); `headline`, `title`, `heading` (a section, in
    the accent colour), `body`, `dim`, `small`, `status` + `ok()` / `bad()`; `card`, `list` + `item` (two-line rows),
    `tapCard`; buttons `filled`, `tonal`, `outlined`, `flat`, `large(b)`, `end(b)`, or `button(c, text, fill, ink,
    stroke)`; `field(c, hint)`; `icon`; `busy(activity, title, text)` + `done(status, worked)` for a dialog that waits;
    `tint(c, builder)` for notifications (`ListenService.builder` does it). Every view comes with full-width
    LinearLayout params and a small gap above, so `col.addView(v)` is enough. A new screen: declare it with
    `android:theme="@style/Kurooto"` (or leave it to the app's default) and start `onCreate` with
    `LinearLayout col = Ui.page(this);`.
  - The launcher icon is `public/icon.svg`'s motif: on Android 8+ the adaptive `mipmap-anydpi-v26/ic_launcher.xml`
    (background `k_call_bg`, foreground `drawable/ic_launcher_fg.xml` with icon.svg's 24 units in the middle 72dp,
    monochrome `ic_launcher_mono.xml` for themed icons); on 6 and 7 the plain vector `mipmap/ic_launcher.xml`.
    `drawable/ic_agent.xml` is Kurooto as a caller (the ringing notification's picture).
  - The ringing notification (`ListenService.ring`): on Android 12+ `Notification.CallStyle.forIncomingCall` (Person =
    the assistant's name, or "Wake-up call"; Decline and Answer are the same intents as before, Later/Snooze is an
    extra action between them). If Android refuses it (`notify` throws), and below 12, the old BigText notification
    with three actions. Both share `ringNotice()` (full-screen intent, ongoing, timeout). 0.6.0: `ringingSince` is set
    after `startRing()` (which clears it): before, a ring neither stopped after its 60 s / 5 minutes nor on the line's
    `stop` (answered elsewhere) until it was tapped.
  - `CallActivity` (the old screen, "New call screen" off) puts the WebView in a `fitsSystemWindows` FrameLayout, so on
    Android 15 (edge to edge) the call page stays clear of the status and navigation bars; on 6 to 14 the insets are 0 and
    nothing changes. The new screen pads it with Compose's `WindowInsets.systemBars` instead.
  - Touch targets are 48dp at least (56dp for `large`, list rows 64dp). Use `Ui.color(c, R.color.k_*)`, never a
    hard-coded colour, so dark mode and Material You keep working.
- CI: `ci.yml` job `android` (vectors, debug build, `NewApi`/`InlinedApi` lint as errors);
  `android-emulator.yml` runs `smoke.sh` on API 23 to 35.

## Tests

- `tests/integration/` runs the real Worker under `wrangler dev` with fakes for Google, ntfy and Web Push
  (`tests/fakes/cloud.py:FakeCloud`) and the real `Connector`: `test_call_line.py` (auth, pairing, tokens, tool relay,
  ringing with VAPID signature checks, uploads, transcripts, the offline queue and cron), `test_lidsafe_line.py`,
  `test_livefallback_line.py`, `test_phone_line.py`, `test_phone_chat_line.py` (the chat and the phone outbox), `test_chat_sessions_line.py` (0.8.10: each chat kept
  on the line, the list, changes, status, deleted chats, `live`),
  `test_presence_line.py`, `test_rotate_line.py`, `test_phone_today_line.py` (Today sealed per phone, kept while the
  computer is away, Done from the outbox, off), `test_shortcut_line.py` (Tell Kurooto links: made, scoped, revoked,
  ended by unpairing, queued offline; and `/upcoming`), `test_phone_direct_line.py` (the app's own connection: who may connect, messages down it and not on
  ntfy, rings both ways with one `mid`, ping/pong, `/send`, one socket per phone, replay after reconnecting, unpairing
  closes it), `test_phone_views_line.py` (the notes map sealed per phone and
  kept while the computer is away, watching Systems, parts in order and the newest only, off). `test_phone_chat_line.py` also covers a sealed file put and
  fetched. They need Node; CI's `call-line` job installs the Worker's packages and bundles the page first.
- Unit: `tests/unit/test_calls.py`, `test_phone.py`, `test_phone_chat.py`, `test_chat_sessions.py` (0.8.10: sessions and their context, replies, files,
  changes, the being's requests and refusals, old-format messages), `test_phone_cards.py`,
  `test_place_reminders.py`, `test_phone_direct.py` (`send_phones` through `/send` and its ntfy fallback, `_ring_fallback` with
  `phones`, `connected` on the Phone tab), `test_phone_today.py` (the Today list, its hand-over, Done / +1, reminder and deadline
  buttons), `test_views.py` (the views' copies, sealing, parts, watching, off; the shared drawing code against
  Chrome 58 with esbuild), `test_shortcut.py` (the computer's side of the links, the dashboard, `public/qr.js` against segno through
  `tests/js/qr.mjs`), `test_app_first.py` (no Telegram: routing,
  files as links, shared files, setup, doctor), `test_livefallback.py` (runs `tests/js/fallback.mjs` and
  `tests/js/callpage.mjs`).

## Not ringing over a call (0.7.3)

- **The computer:** `Calls.busy_with()` says "a call is going on" (`live.json`) or "a call is ringing" (an unanswered
  ring younger than `calls.ring_s` + 20 s) for anything but an alarm; `ring()` then emits `call_not_placed` with
  `busy` and tells the owning feature "held" (a check-in or deadline call tries again by its own rules).
- **The phone:** `ListenService.phoneBusy()` reads `AudioManager.getMode()` (IN_CALL or IN_COMMUNICATION; no
  permission, API 23). Not an alarm and a busy phone: a quiet notice in the messages channel, no ring; the line's
  re-ring (+3 and +6 minutes) tries again. A wake-up alarm always rings.
- Tests: `tests/unit/test_fixes_073.py`; the phone side is checked by reading the source in a test and by hand on a
  phone (not an emulator).

## Known problems and doc mismatches

- A shared file's part that the computer took but didn't confirm (it crashed in between) is written twice when the
  outbox is taken again; chat messages and answers are protected by their nonce, file parts aren't.

- With no Android device paired and a line from before 0.7.0, the computer still publishes each ring to ntfy once (that
  line's answer can't tell "no Android device" from "its publish failed"; a 0.7.0 line says `phones`).
- The app's own connection is untested on a real phone as of 0.7.0's build (JVM tests against a local server, the debug
  build, lint and the Worker tests): how often Doze lets the keepalive alarm and the socket through on each maker's
  phone, and whether a carrier or campus NAT drops a socket idle for 4+ minutes, are unknown. A dropped socket that
  still looks connected to the line (heard within 6 min) means a non-ring message waits until the phone's next ping
  fails and it reconnects (the replay brings it; rings always also go through ntfy).
- `Line.toPhones` writes the phone log on every message even when no phone ever connects (an app before 0.7.0): one
  row write each, well inside the free plan.
- A sealed file's link holds its key, and the link is part of a chat message the call line keeps (3 days): the file
  is only as private from the call line as the chat is.
- The phone's own alarm and its call are matched by time (`AlarmPlan.SAME_S`, 5 minutes): alarms set less than 5
  minutes apart ring on the phone as one. A sealed reminder snoozed on the phone isn't known to the computer.
- Today and the phone's alarm are untested on a real phone as of 0.6.0's build (JVM tests, the debug build, lint and
  the Worker tests only).
- Systems and the Notes map (0.7.0) were checked on one real phone only with a stored sample copy (the
  WebView, its assets, the colours, a tap); fetching from a real call line and watching ran against `wrangler dev`
  only. The notes map's layout is worked out on the phone each time (no positions are kept), so it differs a little
  from the dashboard's and takes a few seconds to settle.
- `calls.ring_s` is never sent to the Worker or the app, which ring 60 s (5 minutes for an alarm) whatever it says.
- Turn-by-turn calls run tools through `core/tools.py:run_tool` and don't reach `Calls.tool_log`; a call page from
  before 0.5.8 (until the Worker is deployed again) sends no `since`, so its tools share the `""` log.

- **Never draw `R.mipmap.ic_launcher` with Compose's `painterResource`.** From API 26 that id resolves to the adaptive
  icon XML (`mipmap-anydpi-v26/ic_launcher.xml`), which `painterResource` rejects ("Only VectorDrawables and
  rasterized asset types are supported"). 0.7.0 did this for the mark at the top of Today and crashed on launch on
  every phone from Android 8; 0.7.1 draws `R.drawable.k_mark` (a PNG in `drawable-nodpi`) instead. Lint and
  `build.sh --test` don't catch it: open a `--dev` build on a real phone (`--ez demo true` reaches Today unpaired)
  before every release that touches the app.
