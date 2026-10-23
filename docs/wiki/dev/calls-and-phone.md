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
| `modules/calls/review.py` | the post-call look back and `/lessons` (0.5.8) |
| `modules/calls/tools.py` | the `Tool` dataclass (shared with `core/tools.py`) and notes helpers |
| `data/worker/src/worker.js` | the Worker: `fetch`, `scheduled`, Durable Object `class Line` |
| `data/worker/web/app.js`, `web/fallback.js` | the call page source (bundled into `public/app.js` at deploy) |
| `data/worker/public/` | `index.html`, `pair.html`/`pair.js`, `inbox.html`/`inbox.js`, `sw.js`, `worklet.js`, icons |
| `data/worker/wrangler.template.toml`, `package.json`, `package-lock.json` | Worker config and pinned packages |
| `android/` | the app (Java, no Gradle), `build.sh`, `smoke.sh`, `test/` |

## Settings and secrets

`register_defaults("calls", ...)` in `modules/calls/__init__.py`: `worker` (`{url, name, version}`; deploy also
writes `account`, `hash`, `deployed`), `live_model`, `live_models`, `voice_by_model`, `voice_mode` (`auto` | `live` |
`phone`), `voice_by_kind`, `turn_brain` (`gemini` | `local`), `text_model`, `voice`, `persona`, `ntfy_server`
(`https://ntfy.sh`), `ring_s` (60), `later_min` (30), `realert_min` ([3, 6]), `notes_repo`, and for the look back
`review` (true), `review_effort` (`high`), `review_brain` (`""` = main), `lessons_max` (12).

Secrets (`Calls.SECRETS` and `deploy.ensure_secrets`): `calls.call_secret`, `calls.connector_secret`,
`calls.ntfy_topic`, `calls.ntfy_key`, `calls.vapid_jwk`, `calls.vapid_public`; also `gemini.api_key` (required) and
`calls.github_token` (set by Notes sync, `modules/notes_sync.py`, so the line can read notes while the computer is off).

## Deploying the line (`modules/calls/deploy.py`)

`deploy(...)` runs `Deployer.run`:

1. `prepare`: Node via `core/prereqs.py`; copy `FILES` from `data/worker` into `<app>/call-line` (`skip_built` leaves
   out `public/app.js` and `node_modules`); copy `data/kurooto.apk` (put into release builds by `tools/release.py
   build --apk`) to `public/kurooto.apk`; `npm ci --ignore-scripts` (skipped when the `.kurooto-lock` stamp matches the
   lockfile); esbuild bundles `web/app.js`.
2. `sign_in`: `wrangler login --browser=false`, the URL opened in the user's browser. `wrangler_env` gives wrangler its
   own config home and strips `CLOUDFLARE_*`, `CF_*`, `WRANGLER_*` from the environment, so a developer's own
   Cloudflare login is never used or touched.
3. `subdomain`: the account's workers.dev subdomain through the Cloudflare API (created as `k-<hex>` if missing).
4. `write_config` / `render_toml`: fills `wrangler.template.toml`; the Worker name is `kurooto-<hex>` (`new_name`).
5. `ensure_secrets`, `wrangler deploy`, `wrangler secret bulk`.
6. Save `calls.worker`, then poll `/health` (24 times, 5 s apart).

Redeploys: `fingerprint` hashes the Worker source and the values baked into it (time zone, `live_model`,
`ntfy_server`, `notes_repo`, whether a GitHub token exists); `needs_redeploy` compares it with `calls.worker.hash`.
`Calls._line_update` runs daily at 05:10 and redeploys unattended unless `updates.mode` is `off`.

## The connector (`modules/calls/connector.py:Connector`)

- One outbound WebSocket to `wss://<worker>/connect` with header `x-connector-secret`; `max_size` 8 MB; the library's
  own pings off. Runs as `Calls.background(stop)`, started by `App.start_background`.
- Heartbeat: text `"ping"` every `PING_S = 30` s; the Durable Object answers `"pong"` through
  `setWebSocketAutoResponse` without waking. Nothing heard for `DEAD_S = 75` s ends the session and redials.
- Reconnect back-off 2 s doubling to 60 s; failures go to `app.presence.net_failed("line", e)`. Link state:
  `<state>/calls/link.json`.
- Computer to Worker: `hello`, `state` (`Calls.state_message`: setup, tools, brief, schedule, texts, voices, presence
  hours ...; pushed every `STATE_S = 300` s or 1 s after `poke()`), `index` (the notes index, in parts, at most
  hourly), `reply` (answers to relayed requests), `admin` (operations).
- Worker to computer: `welcome` (version, the offline queue, an away report), `request` (relayed HTTP), `admin-reply`,
  `event`.
- `admin(...)` / `admin_wait(...)` (from a thread; refuses on the event loop) / `admin_later(...)` (fire and forget;
  its True only means a socket existed).

## Placing a call and ringing

1. `Calls.place(...)` checks `core/availability.py:Availability.call_block` (on a call, quiet / held calls, focus,
   night, then module blockers such as classes and calendar events) unless `alarm` or `force`. A blocked call is booked
   for `next_callable()` and the user is told.
2. `Calls.schedule` books it with `scheduler.at(..., "calls.ring", key="calls:ring:<key>", grace_s=900)` and pokes the
   connector so the line has the schedule too.
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
transcripts, events and answers until `welcome` replays them (`Calls.on_queue`).

## During a call

- The call page (`web/app.js`, in `CallActivity`'s WebView or a browser) POSTs `/token`; `Line.token` mints a single-use
  ephemeral Live token (30 min expiry, 2 min to start) and emits `call_started` (stops the ring; `Calls.on_event`
  marks the ring answered and writes `<state>/calls/live.json`).
- The Live session is configured from `Calls.config_template` (system instruction with each tool's hint, persona,
  learned lessons, transcription, context compression) and `Calls.texts`. Voice by kind: `Calls.voice_for`.
- Tool calls: page to `/tool`, Worker to WebSocket, `Calls.handle_request` to `Calls.run_tool`. Tools are
  `Calls.tools()`: its own (`pending_items`, `search_notes`, `read_note`, `schedule_call`, `call_now`, `hold_calls`,
  `run_task` when Chat is on), `app.ask.call_tools()`, `core/tools.py:sync_tools`, and every enabled module's
  `call_tools()`. With the computer off, each tool's `offline` value decides: `brief` (answered from the last pushed
  brief), `queue` (done later), `needs` (the assistant says it can't).
- `/tasks` is polled for finished jobs and approvals; `Calls.on_call` keeps `availability.set_on_call` 90 s ahead
  (`ON_CALL_S`), so nothing else rings and updates wait.
- What needs attention: `Calls.pending` merges every enabled module's `call_brief()` with `app.ask.call_brief()`.
- Module hooks the calls module looks for (`hasattr` in `modules/calls/__init__.py`): `call_tools`, `call_brief`,
  `call_schedule`, `call_outcome`, `call_transcript`, `call_reschedule`. `Calls.agent_tools` gives unattended AI runs
  only `schedule_call` and `hold_calls`.
- Relayed HTTP paths handled by `Calls.handle_request`: `/tool`, `/tasks`, `/answer`, `/transcript`, `/turn`,
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
  app.jobs.submit(prompt, title="Call review", effort=calls.review_effort, quiet=True, then="calls.reviewed",
                  lane="bg", why="calls.review", brain=calls.review_brain or None)
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

Other files in `<state>/calls/`: `rings.json`, `live.json`, `link.json`, `inbox.json`, `answer-nonces.json`,
`live-health.json`, `textcalls.json`, `lessons.md`, `transcripts/`.

## The Worker (`data/worker/src/worker.js`)

- `export default {fetch, scheduled}` and the Durable Object `Line` (SQLite-backed, migration v1). Cron `* * * * *`.
- Vars baked in at deploy: `OWNER_ID`, `TZ`, `PUBLIC_URL`, `VERSION`, `LIVE_MODEL`, `NTFY_SERVER`, `NOTES_REPO`.
  Secrets: `CALL_SECRET`, `CONNECTOR_SECRET`, `GEMINI_API_KEY`, `NTFY_TOPIC`, `NTFY_KEY`, `VAPID_JWK`, `VAPID_PUBLIC`,
  optional `GITHUB_TOKEN`.
- Routes: top level `/health`, `/manifest.webmanifest`; the rest goes to `Line.fetch`. No auth: `/connect` (checked by
  the connector secret) and `/pair/claim`. Any valid key (device key `d1`, ticket `t1`, or a minted ticket):
  `/status`, `/token`, `/turn`, `/text-call`, `/call-report`, `/tool`, `/tasks`, `/transcript`, `/upload`. Paired
  devices only: `/pending`, `/answer`, `/app-call`, `/ring-reply`, `/push/subscribe`, `/device/key`.
- Admin operations over the WebSocket: `ring`, `stop-ring`, `pair-code`, `devices`, `revoke`, `ticket`, `bye`, `notify`,
  `notify-clear`, `sealed-put`, `sealed-claim`.
- Pinned packages in `package.json` / `package-lock.json` (`@google/genai`, esbuild, wrangler). CI installs them with
  `npm ci --ignore-scripts`.

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
  `KUROOTO_KEYSTORE_PASS` on the maintainer's machine; otherwise a throwaway debug key. `build.sh --test` runs
  `test/CryptoTest.java` and `test/SpeechTest.java` on a plain JVM.
- Components: `MainActivity` (the checklist: battery, notifications, full-screen calls), `PairActivity`,
  `CallActivity` (WebView with the `KurootoApp` JS bridge), `AnswerActivity`, `ShareActivity` (share to Kurooto),
  `ListenService` (foreground, type `remoteMessaging`, holds the ntfy stream), `BootReceiver`, `ActionReceiver`.
  Helpers: `Crypto`, `Seal`, `Line`, `Net`, `Prefs`, `Inbox`, `Speech`, `Tls` (adds ISRG Root X1 on API < 25), `B64`.
- CI: `ci.yml` job `android` (vectors, debug build, `NewApi`/`InlinedApi` lint as errors);
  `android-emulator.yml` runs `smoke.sh` on API 23 to 35.

## Tests

- `tests/integration/` runs the real Worker under `wrangler dev` with fakes for Google, ntfy and Web Push
  (`tests/fakes/cloud.py:FakeCloud`) and the real `Connector`: `test_call_line.py` (auth, pairing, tokens, tool relay,
  ringing with VAPID signature checks, uploads, transcripts, the offline queue and cron), `test_lidsafe_line.py`,
  `test_livefallback_line.py`, `test_phone_line.py`, `test_presence_line.py`, `test_rotate_line.py`. They need Node;
  CI's `call-line` job installs the Worker's packages and bundles the page first.
- Unit: `tests/unit/test_calls.py`, `test_phone.py`, `test_livefallback.py` (runs `tests/js/fallback.mjs` and
  `tests/js/callpage.mjs`).

## Known problems and doc mismatches

- `worker.js`'s header and `docs/PRIVACY.md` say the Worker can't read the Android app's sealed answers, but the Worker
  holds `NTFY_KEY` (it seals with it in `publish` and hands it out in `Line.claim`). k1 protects against ntfy, not
  against the line. Only s1 data is opaque to the Worker.
- "Transcripts stay on your computer" (`Calls.privacy`) does not hold while the computer is off: `Line.transcript`
  queues them in Durable Object storage until `welcome`.
- With no Android device paired, the computer still publishes each ring to ntfy once (the Worker's answer can't tell
  "no Android device" from "its publish failed").
- `calls.ring_s` is never sent to the Worker or the app, which ring 60 s (5 minutes for an alarm) whatever it says.
- Turn-by-turn calls run tools through `core/tools.py:run_tool` and don't reach `Calls.tool_log`; a call page from
  before 0.5.8 (until the Worker is deployed again) sends no `since`, so its tools share the `""` log.
- `docs/MANUAL.md` and `docs/SETTINGS_GUIDE.md` don't yet describe `calls.review*` or `/lessons`, and `docs/PRIVACY.md`
  doesn't say that the transcript and tool log go to the main (or review) AI after every call, or that lessons are
  part of the call setup pushed to the Worker and Gemini.
- `tests/fixtures/call-vectors.json` names `tests/unit/test_calls_line.py`, which doesn't exist.
