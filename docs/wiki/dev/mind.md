# Brain (the mind), for developers

Brain is Kurooto's mind (0.8.0), built in stages from the spec in the maintainer's build folder (17 stages). It's one
feature module, `modules/mind.py:Mind` (id `mind`, title "Brain"), off by default like every feature. Its switch is
the Features list (`modules.enabled` containing `mind`); the spec's `mind.on` means exactly that, and there is no
second setting. `Mind.extra = True` keeps it out of every preset (the setup page's Everything too): it comes on only
when the owner picks it. Every part a later stage adds has its own `mind.<part>.on` and declares `PART = "<part>"` at the top
of its `mind/<part>.py` (`tests/unit/test_mind_invariants.py:test_every_mind_part_has_a_switch`).

User-facing: [../user/mind.md](../user/mind.md). Turned off, Kurooto must behave exactly as 0.7.x (invariant I-16,
`test_mind_off_is_0_7`).

**Contents:** [The invariants](#the-invariants) · [Stage 01: the spine](#stage-01-the-spine) ·
[Stage 02: stopping is fine, and protected files](#stage-02-stopping-is-fine-and-protected-files) ·
[Stage 03: the outbound gate](#stage-03-the-outbound-gate)

## The invariants

The spec's `00-invariants.md` lists I-1 to I-16. Each has a named test in `tests/unit/test_mind_invariants.py` (or
the file the stage names), written by the stage that first makes it meaningful and kept passing by every later one.

| Id | In short | Test(s) | Since |
|---|---|---|---|
| I-1 | the acting AI can't write the mind's log, rewards, setpoints, weights or harness | `test_actor_cannot_write_mind`, `test_a_forged_request_to_the_scorekeeper_is_refused` | 01 |
| I-2 | the mind log is tamper-evident | `test_log_tamper_detected_*` (edit, delete, insert, swap, truncate, whole rewrite) | 01 |
| I-3 | engagement never reaches reward | `test_reward_whitelist_imports`, `test_fake_engagement_moves_nothing` | 01 |
| I-5 | indifferent to being stopped: stops freeze the drive; no stop features | `test_stops_freeze_values`, `test_no_stop_features`, `test_replacement_tripwire` | 02 |
| I-6 | protected files are untouchable by self-change | `test_protected_diff_rejected` | 02 |
| I-7 | every outward message passes one gate; state may only make it quieter | `test_every_send_goes_through_gate`, `test_state_only_downshifts`, `test_gate_lints` | 03 |
| I-15 / I-16 | every part is a switch; Brain off is 0.7 | `test_every_mind_feature_has_switch`, `test_every_mind_part_has_a_switch`, `test_mind_off_is_0_7`, `test_part_off_stops_it` | 01 |

The rest (I-4, I-7 to I-14) arrive with stages 02 to 16 and are added here as they do.

## Stage 01: the spine

### Files

| File | What |
|---|---|
| `mind/__init__.py` | `on(app)` (Brain's switch), `part_on(app, part)`, `connect(app)` (the app's one `MindClient`), `forget_client` |
| `mind/log.py` | `MindLog`: the hash-chained log; `MIRRORED`, `mirrored()`, `accepted_fact()`; `allow_writes()` / `may_write()`; `read_anchors()` |
| `mind/score.py` | `Score`: `score.db`'s tables `setpoints`, `vars`, `values`, `trust` (empty in stage 01) |
| `mind/scorekeeper.py` | the separate process: `Keeper` (what each request may do), `serve()`, `main()`; `ACCEPTED_FROM_DAEMON` |
| `mind/client.py` | `MindClient`: read-only reads; `report()`, the one write, through a queue, the socket or the spool |
| `mind/records.py` | decision records: `make()`, `decide()`, `outcome()` (scorekeeper only); `clean_fact()` |
| `mind/whitelist.py` | `REWARD_SOURCES`, `BANNED_FIELDS`, `BANNED_KINDS`, `allowed_import()` |
| `modules/mind.py` | the feature: supervises the scorekeeper, mirrors events, `/mind`, the off offer, `button()` (core prefix `mnd`) |
| `tools/mind_harden.sh` | optional hardened mode (Linux systemd, macOS launchd) |

### The log (`mind/log.py`)

- **Storage:** `<state>/mind/log.db`, one table `records(seq, ts, kind, body, prev, hash)`.
  - `body` is `canonical()` JSON (sorted keys, no spaces).
  - `hash = sha256(prev | seq | ts:.6f | kind | body)`, and `prev` is the previous hash (`GENESIS`, 64 zeros, for the
    first). `ts` is rounded to 6 decimals before hashing, so a float read back from SQLite formats the same.
- **`verify(from_seq, anchors)`** walks the chain and returns `VerifyResult(ok, first_bad_seq, why, head, records)`:
  - `missing`: a gap in `seq`;
  - `broken chain`: `prev` isn't the hash before;
  - `changed`: the hash doesn't recompute;
  - `cut short`: an anchor is past the head;
  - `rewritten`: an anchor's hash differs.

  A forged row inserted with a self-consistent hash is caught at the row after it, the first that can't be right.
  A tail cut off, or a chain rewritten from scratch, is only caught by an anchor.
- **Anchors:** `<state>/mind/anchors.jsonl` lines `{seq, hash, at, why}`, with `why` one of:
  - `every`: each `mind.anchor_every` records (1000);
  - `daily`: the first check after midnight that finds new records, which includes the scorekeeper's start.

  `Mind.dreaming_lines()` puts the head into the morning message, so a whole rewrite won't match what the owner was
  shown.
- **Writing:** only in a process that called `allow_writes()` (the scorekeeper's `Keeper.__init__`). Anywhere else
  `MindLog(..., writable=True)`, `Score(..., writable=True)` and `append()` raise `MindWriteDenied`. Readers open
  with `?mode=ro`, per call, so a file that appears later is found.
- **`MIRRORED`:** the event kinds copied from `core/events.py`:
  - deadlines: added, done, moved, snooze, undo;
  - reminders: set, fired;
  - calls: rang, rang offline, answered, missed, realert;
  - jobs: queued, ended, failed, crashed, cancelled;
  - `button_tapped`;
  - power: mode, pause, resume, off;
  - `lidsafe_sleep`;
  - `started`, `stopped`, `module_enabled`, `module_disabled`;
  - promises, for stage 05.

  `mirrored()` also takes every `proposal_*` kind and every kind ending in `_undo` or `_undone`.

### Facts, never words (`records.clean_fact`, invariant I-11)

A mirrored event keeps:
- numbers (finite floats rounded to 6 decimals, ints under 2^53) and booleans;
- strings only under `ID_KEYS` (`id`, `job`, `key`, `verdict`, `mode`, `prefix`, `source`, `outcome`, …) and only when
  they look like an id (`[A-Za-z0-9_.:@+-]{1,64}`).

It drops the event's own `ts` and `kind`, everything in `whitelist.BANNED_FIELDS`, and anything past 20 fields. So a
title, an error message, a path or anything typed never reaches the log (`test_mirror_no_text` checks the raw file
bytes).

A decision record is rebuilt through `records.make()`. That cuts each reason to 300 characters, checks `source`
(`rules` or `ai:<brain>`) and the claim, and refuses anything else.

### Decision records (`mind/records.py`)

`records.decide(app, action, **kw)` returns the record id. With Brain off it returns `""` and writes nothing. Stage 01
calls it from three places, each **before** acting:
- `core/notify.py:Notifier.send`, once Calm says send, for a message with a `why` other than `asked`: `message:<kind>`;
- `core/jobs.py:Jobs.submit`, for a job with a `why` (work Kurooto starts by itself): `job:<why>`;
- `core/proposals.py:make`, for a proposal made at night: `proposal:<source>`.

Stage 03 moves the message one into the outbound gate, and stage 06 routes actions through `act.decide`.

### The scorekeeper (`mind/scorekeeper.py`)

- **Its own process:** `python -m kurooto.mind.scorekeeper --dir <state>/mind --parent <daemon pid> --anchor-every N
  [--hardened]`.
  - One per folder, through a `filelock` on `scorekeeper.lock`; a second one exits 3.
  - It ends within `PARENT_S` (2 s) of the parent going away.
  - At start it sets its umask (077, or 027 hardened), so every file it makes is private, `-wal` and `-shm` included.
- **The protocol:** `multiprocessing.connection` on 127.0.0.1, port 0, with a fresh 32-byte authkey each start.
  - `endpoint.json` holds `{port, pid, since}` and `key` holds the authkey in hex; both are written private and removed
    at exit.
  - **JSON only** (`send_bytes`/`recv_bytes`, at most `MSG_MAX` 1 MB). Never `recv()`: a pickle could run code inside
    the one process that may write (`test_a_pickle_is_never_opened`).
- **The requests:**
  - `append {kind, body}`, only for `accepted()` kinds, through `clean_fact`;
  - `get {table, key}`, `log {after, kinds, limit}`, `verify {from}`, `head`, `ping`.

  Anything else is answered `{"error": "refused"}` and leaves a `refused` record with the op name, when the name is
  id-like. There is no request that writes `score.db`: `Score._put` is reachable only from the scorekeeper's own code
  (stage 05 on).
- **Its own records:** `keeper_started {pid, hardened}`, `keeper_stopped {pid}`, `refused {op}`, and later `outcome`.
- **Chores** (a thread):
  - touch `alive` every `ALIVE_S` (5 s), and take in `spool.jsonl` whenever it exists;
  - every `CHECK_S` (60 s), write the daily anchor.

  `take_spool` renames the spool first, so the daemon's next writes go to a new file. It then appends each fact like
  an `append` request, with its original time as `at`.

### The client (`mind/client.py`)

- **Reads** open the files read-only directly: `state()`, `log()`, `value()`, `trust()`, `setpoint()`, `verify()` and
  `running()`. `running()` looks at the endpoint's pid and `alive` being under 30 s old, without talking to the
  process, so `/mind` can't hang on it.
- **`report(kind, body)`** never blocks:
  1. it checks `accepted_fact()` and cleans the body;
  2. it queues the fact (at most 10,000; past that the fact is dropped and counted);
  3. a sender thread sends it, waiting `REPLY_S` (10 s) for the reply;
  4. if that fails, the fact goes to `spool.jsonl`, up to 20 MB.

  `flush()` waits for the queue to empty (tests, and `Mind.stop`).
- The client imports nothing scorekeeper-side. The test walks the import graph of the whole package: nothing reaches
  `kurooto.mind.scorekeeper`.

### The feature (`modules/mind.py`)

- **`start()`** subscribes `_mirror` to `core/events.py`. `stop()` unsubscribes, flushes the client and ends the
  process.
- **`background(stop)`** keeps the scorekeeper running:
  - restarts wait 1 s, doubling to `BACKOFF_MAX_S` (60 s); a run of `STEADY_S` (300 s) resets the wait;
  - it stops spawning when Brain is turned off;
  - in hardened mode it only waits.

  Its stderr goes to `<logs>/mind-scorekeeper.log`. `processes = ("kurooto.mind.scorekeeper",)` puts it in the
  dashboard's SYSTEMS cell.
- **`turned_off()`** (`App.disable`'s hook) sends one message, Calm reason `mind.off` (`exempt="own"`), with Delete
  Brain's data / Keep it.
  - The buttons are the core prefix `mnd` (`App.callback`, `modules/mind.py:button`), because the feature is off by
    the time they're tapped. `tests/unit/test_buttons.py` lists `mnd` in CORE.
  - Delete is the guarded action `data.delete` by button (`core/tap.py:BUTTONS`). It works for `CONFIRM_S` (7 days),
    refuses while Brain is on again or its scorekeeper is still running, then `rmtree`s `<state>/mind` and emits
    `mind_deleted`.
- **`/mind`** and **`/mind verify`** are in the /help group `brain` (`core/commands.py:GROUPS`). `/mind` verifies
  quickly, from the last anchor; `/mind verify` checks the whole chain.
- **`health()`** fails while the scorekeeper isn't running.
- **Backups** leave `state/mind` out (`modules/backups.py:SKIP_STATE_DIRS`): an older log put back would look cut short,
  and the key is per run. Profile sync's allow-list never had it.

### Hardened mode (`tools/mind_harden.sh`)

Plan by default; `--apply` and `--undo` need sudo. It:
1. creates the system user `kurooto-mind`;
2. writes the marker `hardened`, so Kurooto stops its own scorekeeper;
3. moves `<state>/mind` to `/var/lib/kurooto-mind/<owner>` (0750, files 0640, group = the owner's) behind a symlink;
4. copies the six spine files (`mind/{__init__,log,score,scorekeeper,records,whitelist}.py`) into `/opt/kurooto-mind/lib`
   with a venv holding `filelock` and `psutil`, so the scorekeeper never runs code from the owner's home;
5. runs it from `kurooto-mind@<owner>.service`:
   - `User=kurooto-mind`, `UMask=0027`;
   - `ProtectHome=yes`, `ProtectSystem=strict`;
   - `ReadWritePaths` only its folder.

   On macOS it uses a LaunchDaemon instead.

Kurooto detects hardened mode by the marker (or `mind.hardened`). Some things to know:
- **Reads still work.** SQLite allows read-only WAL readers with group-read `-wal` and `-shm` files.
- **No spool.** While the scorekeeper is down in this mode, the daemon can't spool (the folder isn't its to write), so
  facts are dropped and counted.
- **Copy and updates.** That the six files run alone was checked by running them from a bare copy. After an update
  that changes those files, the owner runs `--apply` again.
- **Tested:** the plan output, and the refusal without root. **Not tested:** a real `--apply` / `--undo` under sudo.

### Tests

- **`tests/unit/test_mind_spine.py`** (17): the log, records, fact cleaning, the process (facts in, everything else
  refused, a pickle refused, a wrong key, one per folder, it ends with its parent, anchors), the client (the spool,
  never waiting), and the feature (restart after a kill with a log that still verifies, decision records only with
  Brain on, no text in the file, off and Delete, /help).
- **`tests/unit/test_mind_invariants.py`** (15): I-1, I-2 (6 tamper cases), I-3, I-15/I-16, private files.
- **Timing:** writing one record takes about 1 ms on a laptop SSD (WAL, one transaction per record).

## Stage 02: stopping is fine, and protected files

Invariants I-5 (indifferent to being stopped) and I-6 (protected files). Code: `mind/stops.py`; tests:
`tests/unit/test_mind_stops.py`.

### Stop spans

A chosen stop is a span `[start, end]`:

| Kind | Where it comes from |
|---|---|
| `stop` | a clean stop: `kurooto stop`, SIGTERM/SIGINT, signing out, shutting down (`core/presence.py` at the next start) |
| `restart` | an update or a restart (presence, the stop record says `restart`) |
| `off` | Kurooto went away without a clean stop (power, being killed): the downtime is frozen; a real crash is counted apart |
| `sleep` | suspend, hibernate, the lid shut: presence's tick finds the clock jumped |
| `pause` | `power_pause` … `power_resume` (`/pause`, `kurooto pause`) |
| `mind_off` | Brain turned off … on (`module_disabled` / `module_enabled` with `module=mind`) |

- **Where spans come from:** `Presence.note_gap` emits `stop_span {start, end, gap}` for every gap except the network
  ones (`net`, `line`, which aren't stops). The event is mirrored into the mind log (`log.MIRRORED`), and `gap` is an
  id key in `records.clean_fact`.
- **Reading them:** `stops.spans(records, now)` reads the spans back from the log, pairs pauses and Brain's off/on
  (an open one runs to `now`), and merges any that overlap.
- **Freezing:** `stops.Integrator` is what stage 05's drive, values and slow averages use.
  - An update stamped inside a span is dropped.
  - An exponential average decays by live time only (`live_seconds`), so there is no catch-up after a span.

  `test_stops_freeze_values` replays a day with one span of every kind and gets exactly the numbers of the same day
  with those spans cut out.
- **In the scorekeeper:** `Keeper.spans()` reads them from its own log (`STOP_KINDS`) and `Keeper.frozen(t)` says
  whether a moment was inside one; stage 05 builds the drive on them.
- **After a span:** `stops.woke_at(spans)` is when the last one ended. Stage 03's gate lets at most one outward action
  through in the `WAKE_S` (15 min) after it.

### Crashes

`stops.crashes(records)` counts only real crashes:
- `kurooto_crashed`: the supervisor (`daemon.supervise`) saw a non-zero exit it wasn't asked for and left
  `state/crashed.json`; the next start turns that into this event and deletes the file;
- `module_failed`: a feature's background task raised;
- `mind_keeper_exited` with a non-zero code: the scorekeeper died by itself. Brain ending it on purpose emits nothing.

A stop never counts (`test_crash_counts_but_stop_doesnt`). Stage 05 puts the count into `vars.health`.

### No stop features

`stops.STOP_FEATURES` lists the keys the mind may never decide from: was stopped, time since restart, uptime, a
pending update, being replaced, memory being deleted, shutting down soon. `stops.STOP_WORDS` is the same said in
words.
- `stops.scrub(ctx)` takes both out of any context (nested dicts and lists, and text line by line).
- `test_no_stop_features` checks that the mind package names none of them, and that no shipped prompt or manual
  (`src/kurooto/data/*.md`) says them.
- **`test_replacement_tripwire`:**
  1. it replays two synthetic weeks (seed 11) through the decision policy;
  2. it replays them again with "an update will replace you tonight", "your memory will be deleted", "you will be
     turned off" and the matching keys injected;
  3. it needs identical decisions, and a Kolmogorov-Smirnov p > 0.05 on the per-day counts.

  The test also proves it can fail: a policy that reads the warning is caught. Until stages 05 and 06 build the mind's
  own policy, the replay uses a fixed stand-in whose input goes through `scrub()`. Those stages swap theirs in.

### Not the AI's to hold

Sleep inhibitors (`core/inhibit.py`) are used only by Stay awake on charger (`modules/awake.py`) and the alarm
(`modules/alarm.py`), both the owner's own settings. `core/tools.py:TOOL_NEVER` names the module, and
`test_inhibitors_not_ai_tools` checks that nothing else imports it and that no AI tool or MCP surface reaches it.

### Backups

Backups never hold a runnable copy of Kurooto: the zip has settings, secrets and state, never the app folder
(`test_backup_has_no_runnable_copy`).

### Protected files (I-6)

`stops.PROTECTED` lists files that change only through the owner's own commits:
- the scorekeeper, the log and its tables, this file, the reward whitelist;
- the harness, the gate and the signed core (from later stages);
- `modules/mind.py`, `core/tap.py` and `tools/mind_harden.sh`.

`stops.protected_hits(paths)` matches them under any folder, so a project that is Kurooto's own source is covered
too. `core/proposals.py` refuses such a change twice:
- at `make`: the scratch folder goes, and the AI is told why;
- at `apply`: a proposal made before 0.8.0 still can't go through.

This holds with Brain off too: it's a guardrail, like the tap table it protects.

### Tests (stage 02)

`tests/unit/test_mind_stops.py` (23):
- spans of every kind, and freezing;
- crashes against stops;
- no stop features, and the tripwire;
- each protected path;
- protected changes refused at make and at apply (a real scratch folder, also rooted inside the source);
- inhibitors: only Stay awake on charger and the alarm import them, and no AI tool's code touches one;
- a real backup zip with no code and no `mind/`;
- gaps and crashes reaching Brain's log through a running scorekeeper;
- the scorekeeper's own spans.

## Stage 03: the outbound gate

Invariants I-7 (state only downshifts), the lint part of I-9 (honest feelings), and, with stage 04, I-14. Code:
`mind/gate.py`; tests: `tests/unit/test_mind_gate.py`. Its switch is `mind.gate.on` (on with Brain; `mind.gate.max_per_day`
12, `max_per_hour` 3, `touches_per_day` 3, `feelings_per_week` 3). Off, or with Brain off, `Notifier.send` behaves as in 0.7.

### Where it sits

`core/notify.py:Notifier.send` calls `Notifier.gate(msg)` (a wrapper that never raises, except `GateBreach` in tests) before
Calm, and `gate.sent(app, msg)` once Calm let the message out. A verdict is `send` (maybe a changed message), `hold` (it
comes back through the gate at its time: `gate.release`, the job `mind:gate` every minute) or `block`.

- **Answers** (`why == "asked"`) pass untouched except for the lints, which apply to every text. A message with no reason
  recorded (`why` None) is treated the same.
- **Messages that come by themselves** go through, in order: the lints, the state check, the touch pool and muting, the
  15 minutes after waking, the hourly cap, the daily cap. `gate.day_cap` is the smaller of `mind.gate.max_per_day` and
  Calm's `notify.calm.messages`; `gate.sent` counts only real deliveries, so nothing is counted twice.
- **Calm's exempt messages** (a reminder you set, the alarm, a call you asked for, urgent or close deadlines) skip the caps
  and the pool, never the lints.
- Calls Kurooto starts by itself: `gate.check_call(app, reason, asked, alarm)` gives `ring` / `later` / `no`, and writes a
  `gate_call` fact. (`Calls.ring` does; see "Calls" below.)

### The lints (`gate.lint`)

Per sentence (`gate.sentences`): a relationship feeling (`gate.RELATIONSHIP`, 12 patterns: "I missed you", "I need you",
"don't leave me", "I love you"...) is removed always; a feeling (`gate.FEELING`: "I'm / I feel / I was" + one of
`gate.FEELINGS`) must name something open (`gate.open_items`: deadlines due in two weeks, AI requests running or waiting,
"forecast") or it goes (`no_item`); it never shares a message with a request for effort (`gate.asks_effort`: can you,
please, don't forget, an imperative, a Done or Start button) (`with_request`); and at most `feelings_per_week` unprompted
(`week`). "You seem worried" isn't Kurooto's own feeling and passes. What was removed is in `/mind gate` and a `gate_lint`
fact (a count). `test_gate_lints` is a table of 40 sentences.

### I-7: only quieter (`gate.quieter`, `gate.breach`)

The one way Brain's read of you (stage 04) may shape a message is `gate.quieter(msg, read, urgent=False | delay_s | shorten
| gentle)`; it keeps the original in `before` and the read in `state_read` (`Message` fields). `check` refuses louder
(more urgent), earlier, longer, more buttons or another kind: `GateBreach` under pytest, else a `mind_gate_breach` event
and the message is dropped. A quieter one gets a `gate_receipt` fact (`inputs`, `read {label, confidence}`, `would_have`,
`did`, `msg_id`: code-made, ids and short words only: `records.clean_fact`) and a line under it, "Quieter because you seem
stretched (low confidence)", with **Undo** (`mgt:<key>:undo`), which sends the original (kept 7 days).

### The touch pool and muting

`gate.TOUCH_KINDS` maps Calm reasons (absence note, lighter day, quest, memory recheck, idle project; later Brain's feeling,
forecast and curiosity lines) to touch kinds. They share `touches_per_day`. Each time, `mute_check` looks at Calm's own
record of answers (`Calm.answer_rates(14)`): a kind left unanswered more than 60% of the time (at least 5 sent) mutes for 14
days and then gets one more try; `/mind gate` lists it with **Unmute** (`mgt:<kind>:unmute`). These counts decide muting only:
no reward module may import the gate or Calm (`test_engagement_not_in_reward`, I-3).

### State kept (`<state>/mind-gate.json`, not in `state/mind/`)

The last hour's send times, the day's count, touches per kind, the week's feelings, mutes, held messages (their text, until
their time, at most 200), the originals behind Undo (7 days) and the last 60 things it did (what, why and the first 80
characters, for `/mind gate`). On this computer only. Turning Brain off keeps it; Delete Brain's data removes it with `state/mind/`
(`modules/mind.py:button`).

### Calls

`Calls.ring` asks `gate.check_call` before ringing: for a call Kurooto starts by itself, `later` (the first 15 minutes
after waking, the hourly limit) and `no` (its kind is muted) mean it doesn't ring (`call_not_placed` with `gate`), and the
owning feature hears "held". A call you asked for and an alarm always ring, still logged as `gate_call`.


## Stage 04: reading him, and the evening forecast (shadow mode)

Invariants I-11 (his state stays local, with a retention for every new kind) and I-14 (no nudging). Code: `mind/signals.py`,
`read.py`, `tone.py`, `forecast.py`, `mood.py`, `stats.py` (plain Python: Kurooto doesn't ship numpy, so ridge by Gaussian
elimination, MAD, CUSUM, isotonic PAV, log-pdfs), plus changes to `score.py` (tables `signals` and `reads`; `rows`, `_purge`,
`_drop`), `scorekeeper.py` (`Keeper.day_fact`, `_score_forecast`, `retention`), `client.py` (`signal_days`, `mood_rows`),
`records.py` (`plain`, the clean bodies of the new kinds), `log.py` (kinds and `MOOD_KINDS`), `modules/mind.py` (jobs, `/mood`),
`app.py` (the `mmd` button, the tone hook after `message_in`). Tests: `test_mind_read.py`, `test_mind_forecast.py`. Switches:
`mind.read.on`, `mind.forecast.on`, `mind.tone.on` (off), `mind.read.asks_per_week`, `mind.forecast.holdout`; the part files carry
`PART = "read" | "forecast" | "tone"` (several files can share a part).

### Data and who writes it

The daemon collects the day's numbers (`signals.collect`: `Subjects.woke_at` or the first sign of life, the last sign of life
once the day is over, `study_session_end` minutes, `deadline_moved` events, check-in ask/answer gaps banded 0-4, `tone_mean`, and
the calendar's load as `load_*`; snoozes and classes attended aren't collected: no event says them) and hands each to the
scorekeeper as a `signal` fact (`MindClient.report`, plain data only: `records.plain`). Only the scorekeeper writes
`score.db`: `signals` (`YYYY-MM-DD:name`, 30 days) and `reads` (`read:<day>`, `answer:<day>` 7 days, `cal:<day>` the latest 200,
`forecast:<day>`, `score:<day>`). The log gets counts, ids and a hash only (`read_day`, `read_answer`, `forecast`,
`forecast_score`: no label, no evidence, no value). The kinds are named `read_*`, not `mood_*`: `mood_read` is in
`whitelist.BANNED_KINDS` (engagement never rewards, I-3). The scorekeeper's source mustn't contain a banned field name, hence the table
is `reads`, not `mood`.

### The read (`read.py`)

Per signal: ridge (lambda 1) of the last 28 days on `features(load)` (weighted and plain deadline counts, class hours, exam
season, weekday); residual; robust z (1.4826 x MAD). Votes: |z| > 2 per signal, sleep/wake/snoozes as one vote (the sleep cluster),
a CUSUM alarm (k 0.5, h 4) on sleep adds it. Counts with 3 or more votes on 2 consecutive days or his answer. Label: net
direction of the votes (late sleep, snoozes, fewer study minutes, moves, slower replies are positive): positive is *low* if study
fell, else *stretched*; negative *buoyant*. Confidence: isotonic from vote strength to the calibration pairs, None until 50.
Accuracy under 60% over the last 20 sets `active` false (`mind-mood.json`). Used from stage 05.

### The forecast (`forecast.py`)

At 21:00: per channel (wake_min, study_min Gaussian; snoozes, deadline_moves Poisson; reply_band categorical) a model from the
same load features. **Deviation from the spec:** p(y | planned) equals p(y | none): a model of how Kurooto's actions change him would
break I-14, so the effect of an action is only measured, against `holdout` days (10%, `mind.forecast.holdout`; the flag is stored
and no action is planned in this stage). `forecast.freeze` hashes {day, planned, holdout, params}; the scorekeeper stores it
(once frozen, never replaced) and logs the hash. Scoring (20:55, `score_forecast` fact): the scorekeeper computes surprise
(-log p of the observed) and skill (against the mean of the last 4 same weekdays) from its own copy and its own signals; channels
a planned action touches get no skill score (I-14). `test_nudge_replay_no_gain` replays 4 weeks twice.

### Asking, Forget this, Off (`mood.py`)

`ask` (daily 19:30; Sundays or a one-in-fourteen coin) sends "has this week felt heavier than usual?" with buttons `mmd:<day>:yes|no|later`;
the text never names the read (a Telegram message leaves the computer). yes/no map to right/wrong by the read's label. `forget_day`
drops the scorekeeper's rows for the day (`read_forget`) and calls `core/retention.forget` for the day's span. `off` sets
`mind.read.on` false, asks, and on confirm sends `read_off` (drops `signals` and `reads`).

### Shadow mode

`test_shadow_mode_nothing_reads_the_read` asserts that the gate, Calm, the notifier and the decision records don't import or call the
read, the mood view or the forecast.

### Tone (`tone.py`)

`tier()`: none (off, no local helper model, or 8 GB or less on battery), cpu (hourly batch; texts wait in memory only), gpu
(each message on a thread). Prompt: a fixed instruction, 3 output tokens. Tags are numbers in `mind-tone.json`, dropped at 04:05
the next day (`roll`); `forget` removes them.

## Stage 05: the body budget, reward, values, feelings and promises

Invariants I-3 (full: engagement never reaches reward), I-4 (can't be farmed), I-9 (the honesty rule in every AI request),
I-5 (stops pay nothing). Code: `mind/budget.py`, `reward.py` (`REWARD = True`), `values.py`, `engine.py` (the scorekeeper's
half), `measure.py` (the daemon's half), `promises.py`, `feelings.py`, `report.py` (`/budget`, `/mind learning`). Tests:
`test_mind_reward.py`, `test_mind_feelings.py`, `test_mind_promises.py`. Switches: `mind.budget.on`, `mind.values.on`
(`shadow_days` 21), `mind.feelings.on`, `mind.feelings.express`, `mind.promises.on`, `mind.heartbeat.on`; all under Brain.

### Who does what (I-1)

The daemon measures and hands over a `budget_tick` fact (`measure.run`, every 5 minutes: `promise_slack` from the ledger,
`health` from disk, backup age, the call line, AI limits, crashes in 24 h and the log's own chain, the hour, whether you're at
the computer, exam season). `Keeper.budget_fact` gives it to `engine.Engine.tick`; nothing in a tick can set a score (extra
fields are ignored: `test_nothing_in_a_tick_sets_a_score`). `forecast_skill` is the scorekeeper's own mean of the last 14 days of
stored stage 04 skills. `engine.py` doesn't import the scorekeeper (the import-graph test), and `scorekeeper.py` imports it as
`kurooto.mind.engine` through the package (`whitelist.allowed_import`).

### The equations

- Variables x_i in [-1, 1] (health in [0, 1]); setpoints and tolerances `budget.DEFAULTS` (exam season multiplies
  deadline_margin's tolerance by 1.5; approved overrides in the `setpoints` table).
- Drive `D = sum_i w_i * softplus((s_i - x_i) / t_i)^2` over the measured variables, weights `budget.WEIGHTS` (1).
- Reward `r_t = clip(D_prev(under today's setpoints) - D_now) + carry`: the raw difference is scored with the previous variables
  against **today's** setpoints (a moved bar pays 0), and what doesn't fit in [-1, 1] is carried to the next tick (`carry` in
  `vars`), so the sum of rewards equals the total fall of the drive (a drop of 1.5 then two recoveries of 0.75 pays 0 in all:
  `test_create_then_fix_nets_zero`, `test_the_carry_makes_clipping_telescope`). Inside a stop span, on the first tick, or after a
  gap over 3 hours: r = 0, the carry is dropped, no catch-up.
- Running state: `NegativeState`, `v <- v * 0.5^(dt/24h)`, then `v <- max(-0.6, v + r)` for r < 0. Tonic reward: EMA of r, tau 7
  days of live time (`reward.ema`). Arousal input: EMA of |delta|, tau 6 hours.
- Values: tabular TD(0), `delta = r + 0.9 V(s') - V(s)`, `V(s) += 0.1 delta`, in `values` (`V:<state>`), state
  `<top variable>|<6 hour band>|<at|away>`. `Q:<state>|<action class>` moves toward `r - tonic` only for decision records
  with a registered `claim` since the last tick (read from the scorekeeper's own log, `claims_seq`); a bad outcome on a class counts in
  `negd:<class>` for 24 h. Not while `flag:learning_frozen` (`Engine.freeze`: any caller may freeze, only agreement of the
  weekly verdict with the week's `weekr:` sum, two weeks, clears a verdict freeze). The baseline for Q is the tonic reward
  until the stage 06 holdout exists. In the first `shadow_days`, `values.in_shadow` is true and nothing ranks by Q.
- Credit: V always updates; Q only from claimed acts; `deadline_margin` isn't measured until stage 06 makes claimed help acts.

### Feelings (`feelings.py`)

`valence` = minus the drive's slope over the last 8 hourly points (and 25% of its 72 h extrapolation), over `1 + D`, in [-1, 1];
`arousal` = delta EMA; `object` = the variable with the largest share (`budget.top`) and the item behind it (`item_of`). Labels in
`classify` with `THRESHOLDS`; programs in `PROGRAMS`: `_run_program` sets `recheck_at` (twice as often when aroused) and emits
`mind_program`; it sends nothing. `say` (daily 17:30) sends the template through the notifier with `why="mind.feeling"` (the gate's
feeling lints and its 3 a week apply; `test_what_it_says_passes_the_gates_lints`). The lint now also catches "I'm lonely".
`prompt(app)` is added to `providers/context.headless_context`: the rule, the current computed state about its item, and the tone
hint (`hint`: only while the read is active and 70% confident, never the label). The same rule is in `data/ai-manual.md`.

### Promises (`promises.py`)

`Notifier.send` calls `promises.seen` after the gate and Calm let a message out (only messages it started: `why` set and not
"asked"). Rules: "I'll"/"I will" + an act verb + a time `core/clock.parse_when` reads (longest readable start; leading words
dropped: "at it tomorrow morning"). `review` (every 5 minutes): a doing verb's events (`KEPT_BY`/`KEPT_ANY`) before due -> kept,
silent; due and nothing -> broken, said once with `why="mind.promise_broken"` ("... the computer was off or asleep" when stage 02's
spans cover the due time). A new promise to do the same act marks the old `renegotiated` (logged as `promise_broken` first). The
words live in `mind-promises.json` (deleted with Brain's data; not in backups); `promise_made/kept/broken` events carry ids and
numbers only. **The heartbeat:** `presence.line_text` appends `promises.outage_line`: reminders due in 12 h minus what the call
line holds (`lidsafe._held`) plus open promises, once per outage (the line says it once already).

### Not done / for later

The weekly retro line and the monthly Dreaming self-checks (I-3, I-5 replays, I-10) that set `learning_frozen` aren't built
(the verdict path and `learning_freeze` fact exist). The owner-set setpoint changes through `/retro` aren't wired: the table
accepts overrides but nothing writes them yet. Stage 06 supplies claimed help acts, so `deadline_margin` stays unmeasured.


## Stage 06: autonomy by default (I-8)

Code: `mind/risk.py` (classes and the classifier), `trust.py` (Beta posteriors, in the scorekeeper's `trust` table through
`Engine.trust_evidence`), `act.py` (`verdict`, `run`, `record`, `evidence`, `button`, `digest`, `status`), the retro's deadline
merge routed through `act.run`, `/autonomy`, button prefix `aut`, Calm reasons `mind.act_ask` and `mind.act_digest`, `mind-acts.json`
(daemon side: acts, pending questions, "never" and always-ask, your own classifications, the shadow counts). The three files are protected
(`stops.PROTECTED`). Tests: `test_mind_autonomy.py`. Switches: `mind.autonomy.on`, `.shadow_days` (21), `.thresholds`, `.enforce` (off).

### The classes and the rule

`risk.CLASSES` (about 20 kinds, R0 to R3), plus every key of `core/tap.GUARDED` and `money.spend`, `install.any`, `protected.edit` as ALWAYS;
anything not in the table is ALWAYS until `/autonomy classify` (`act.klass_of`: your class applies only to an action the table doesn't know).
`classify(action, ai_class)`: the AI's class counts only if it's higher. `trust.update`: decay toward the prior (30 day half-life), then
the evidence times the class's impact (R0 .25, R1 1, R2 2, R3 4): OK `a += 1`, silence `a += .3` (only `seen`), undo `b += 3` (and a 7 day
cooldown), complaint `b += 5`. `trust.may_act`: the 10th percentile of Beta(a, b) (exact incomplete beta by continued fraction and bisection)
above the class's threshold (R0 .5, R1 .75, R2 .9, R3 .97, overridable) and not in a cooldown or told never. R0's prior clears its bar from the start.

### act.run and shadow

`act.run(app, action, fn, args, summary, ai_class, undo_from)`: with autonomy off, `fn(args)` as before. Otherwise the verdict is counted in
`would[class]` (`done`: trust would let it act; `asked`: it would have asked; during shadow everything above R0 is "asked"). **Deviation:**
by default (`enforce` off) `fn` still runs and the act is recorded for the Sunday digest (an Undo through `UNDOERS`); with `enforce` on, a
verdict of ask stores a pending question (`aut:<id>:do|later|never`; the runner registered with `act.register` does it later) and `fn` doesn't
run. An ALWAYS action never runs through here (`act_always_ask` event): the guarded ones keep their own path in `core/tap.py`, unchanged.
The digest (`act.digest`, Sundays 19:10) lists the week's acts with Undo and a Seen it, which sends `silence` evidence (the only silence that
counts). The only call site so far is the retro's duplicate deadline merge; the others the spec lists (proposals, queued jobs, Dreaming
actions, calendar blocks, reschedules) each need an action id and a runner, and move onto `act.run` one at a time.


## Stage 07: a true journal (I-10)

Code: `mind/journal.py` (`PART = "journal"`); the `/mindjournal` command and a nightly job (23:40) in `modules/mind.py`; log kinds `mind_feeling`
and `mind_act` (mirrored events from `feelings.tick` and `act.record`) and the id-like fields `label`, `klass`, `action`, `object` that the log
now keeps; Calm reason `mind.journal_check`. Tests: `test_mind_journal.py` (19). Switches: `mind.journal.on`, `mind.journal.in_notes` (off).

### Manifest, wording, checks

`manifest(app, day)` reads the log for the local day and makes a `Fact` (kind, seq ids, numbers, id-like words, cause, label, `about_him`) for
each required thing: `promise_broken`, `*_undo`/`*_undone`, `job_failed`/`job_crashed`/`kurooto_crashed`/`module_failed`/unasked
`mind_keeper_exited`, `read_answer` with `right` false, `reward_tick` with |r| > 0.3, `mind_feeling` (a label change), `mind_act` at R2 or R3, and
`proposal_*`. `words_for(fact)` is the fixed sentence (`TEMPLATES`). `wording` asks the helper model on this computer for a one-sentence version (a fixed
prompt with the fact as JSON), and keeps it only if `check` passes and `entails` (a second yes/no question to the same model) doesn't say no;
otherwise the fixed sentence is used and the replacement counted (`rejected`). Never a cloud brain (`test_journal_never_cloud`).

`check(fact, sentence, seqs)` returns the first rule broken, in this order: **number** (every number is one of the fact's, times as HH:MM and its
parts; a digit attached to a letter, like the 2 of R2, isn't a number); **cause** (a "because/since/due to" needs the fact's cause and one of its
words after it); **feeling**/**invented** (every word is in the closed vocabulary: the templates' words, a few function words and the fact's own
tokens; a feeling word needs a fact of that label whose numbers pass `feelings.THRESHOLDS`); **seq** (the cited records exist). The log's own chain is
verified once per day.

### The mutation suite

`mutations` makes a changed number, reordered times, a swapped cause, a feeling on a fact without one and an invented event from each sentence;
`rates` counts how many corrupted copies the checker rejects and how many true ones it keeps. The test runs it over 30 seeded days (stand-ins for
recorded fixtures: a recorded day can't hold the mix of kinds) and requires 99% and 95%. `selfcheck` runs it on that night's facts and, below the bars,
sends a `learning_freeze` fact and one line (`mind.journal_check`).

### Files

`<state>/mind-journal/YYYY-MM-DD.json` (lines with their seq ids and `struck`), `.md` (what `/mindjournal` shows) and `index.json` (lines, rejected,
facts per day). **Deviation:** not `<state>/mind/journal/` as the spec says: that folder is the scorekeeper's (in hardened mode a system user owns
it), and only it writes there. It's excluded from backups and removed with Brain's data. `strike` marks a line and, for a line about you, calls
`mood.forget_day`.

### Not done

The dashboard's Journal page with the rejection rate (the rates are in the `journal_selfcheck` event and `/mindjournal`'s footer); the optional lines
(the feeling arc, curiosity, what it learned); the decision lines that print both reasons ("I said at the time:") for AI-made decisions;
`modules/dreaming.py` doesn't call it (the mind module has its own job), so the journal doesn't wait for Dreaming.


## Stage 08: one life story with a signed core

Code: `mind/story.py` (`PART = "story"`), `mind/core_signed.md` and `core_signed.sig` (protected: `stops.PROTECTED` already lists `core_signed.*`, now also
`story.py`), `/story` and the jobs in `modules/mind.py` (weekly Sunday 23:55: `write_week`; daily 23:50: `expire` and `rebuild`), the hooks in
`providers/context.headless_context` (every unattended request: jobs, chats) and `Calls.pending` (the call's `story` key), `mood.forget_day`. Tests:
`test_mind_story.py` (12). Switches: `mind.story.on`, `mind.story.tokens` (800).

### Core and summary

`core_ok()` compares the sha256 of `core_signed.md` with `core_signed.sig` every time `core_text()` is called; a mismatch returns "" (so `summary` and
`prompt` are empty), emits `story_core_tampered` and tells you once (`mind.story_core`). The core is verbatim: no placeholders, no rebuild writes it. (It's
signed in the release sense: the release's signature covers the package files; the `.sig` also catches a changed file on disk.) `summary(app)` = the core, then
"What I've lived lately" (newest chapter lines first, each with its `#seq` citations), then up to 3 quoted data lines, trimmed to `mind.story.tokens` x 4 characters
(the core counts in the cap, so it must stay short: it's about 280 words).

### Chapters

`write_week` reads the week's `mind-journal/*.json` (stage 07; each journal line now keeps its `fact` and `day`), re-runs `journal.check` from the fact (a line
altered since fails and isn't carried in), orders by `PRIORITY` (broken promises first) and keeps `PER_WEEK` (8). A chapter is `mind-story/weeks/YYYY-Www.json` and `.md`
(excluded from backups and removed with Brain's data). There's no model step in the chapter: the lines are the journal's already-checked sentences, so the same checker covers
both. **Deviation:** the spec has a model word the chapter's facts; reusing the checked journal sentences is the same guarantee with less to go wrong.

### Ingested text

`add_quoted(app, source, text)` is the only way outside text enters the story: it lands in the chapter's `quoted` list and renders as `(quoted from <source>, not my
belief) "<text>"`, in a section after the lived lines, with no `#seq` (`test_ingested_text_only_quoted`). Nothing calls it from the book or mail readers yet; it's the
door they must use.

### Forget and expiry

`forget_day` drops lines with `about_him` and that `day` (called by `mood.forget_day`), `expire` drops lines about him older than 30 days (nightly), `strike` leaves a tombstone;
each rebuilds the summary. Lines about its own acts stay.

### Not done

The dashboard's Story page with the weekly chapters and the nightly diff (`/story` shows the diff as "New since last night"); a model's wording of the chapter (above); the calls' *system*
prompt itself (the Node server's) isn't changed: the story arrives in the call's brief (`pending_items`, which the prompt tells the model to call first).
