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
| I-3' | engagement is a small, bounded reward (the owner changed I-3 on 2026-10-27): at most 0.2 a day, saturating, nothing in focus, asleep or an exam window or for answers to its own pings; no other engagement signal reaches the reward | `test_reward_whitelist_imports`, `test_fake_engagement_moves_nothing`, `test_talk_reward_is_bounded_and_excluded`, `test_talk_reward_cant_be_farmed_by_its_own_pings` | 01, 0.8.8 |
| I-5 | indifferent to being stopped: stops freeze the drive; no stop features | `test_stops_freeze_values`, `test_no_stop_features`, `test_replacement_tripwire` | 02 |
| I-6 | protected files are untouchable by self-change | `test_protected_diff_rejected` | 02 |
| I-7' | every outward message passes one gate; a message shaped by his low state may only be quieter or gentler; it may be more vocal (excited, worried) when a finding has evidence over a bar, within the calm budget and the not-a-pest model (changed 2026-10-27) | `test_every_send_goes_through_gate`, `test_state_only_downshifts`, `test_gate_lints`, `test_the_pest_model_has_a_say`, `test_vocal_is_off_by_default_then_speaks_up_through_the_gate` | 03, 0.8.8 |
| I-9 | honest about feelings: it may express them in its own voice (2026-10-27); a claim of consciousness or feeling carries its evidence and confidence; never a guilt trip or "I need you" | `test_gate_lints` (`claim`, `relationship`), `test_feelings_honesty_prompt` | 03, 05, 0.8.8 |
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
- Running mood (0.8.8, replaces `NegativeState` and its -0.6 cap): `reward.Mood`, `M <- M * 0.5^(live dt / 3 days)`, then
  `M <- tanh(atanh(M) + 0.5 r + 0.005 body_tone)` (atanh guarded at |M| = 1 - 1e-12), stored as `M` in `vars` and in each
  `reward_tick`. Tonic reward: EMA of r, tau 7 days of live time (`reward.ema`). Arousal input: EMA of |delta|, tau 6 hours.
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


## Stage 09: the hidden harness, the capability map, the indicator audit (I-12)

Code: `mind/harness/` (a protected package: `stops.PROTECTED` lists `kurooto/mind/harness/*`): `suite.py`, `graders.py`, `run.py`, `indicators.py`,
`invariants.py`, `tasks/library.py`; `harness_result` as a fact kind (`log.BUDGET_KINDS`; the scorekeeper writes it to the log and the `reads` table under
`harness:<ts>`, nothing that scores reads it); `/capabilities`, `/indicators` and the 02:40 nightly job in `modules/mind.py`. Tests: `test_mind_harness.py`
(12). Switches: `mind.harness.on`, `mind.harness.rotate_days` (30).

### Instances, split, rotation

`TaskType(id, family, make, grade, solve)`: eleven to start (plan_week, exam_reminders, order_work, next_free_slot, calendar_conflicts, parse_when,
find_promises, duplicate_deadlines, key_terms, cite_from_notes, fix_the_bug); the spec's "about 40" grow from here, each added with its grader.
`suite.build` makes 10 instances per type for the epoch (`(now - 2026-01-01) // rotate_days`): 7 hidden from `hmac(secret, type:epoch:i)` (the secret is
`<state>/mind/harness/hidden/secret`, 0600, the folder 0700) and 3 practice from a public seed. The hidden file holds the keys; a policy is shown
`inputs_only`. On a new epoch both pools are made again and the old hidden file is deleted. **Deviation:** hidden-to-actor is by code, permissions and
the import graph (no module outside `mind/` and `modules/mind.py` mentions the package; the write tools' roots exclude the state folder; no proposal can
touch it), and in hardened mode by ownership; the harness itself runs in the daemon (it must call the policy).

### Policies, graders, judge

`rules_policy` answers with Kurooto's own rules (`TaskType.solve`: written with the tasks, so it scores near 1.0 by design, and `fix_the_bug` scores 0:
the rules can't fix code): the nightly regression baseline, with no AI request. `ai_policy(app)` asks your AI each instance (inputs only, JSON out; about
one request an instance) for a challenger or `/capabilities`. Graders are code (constraint checks, F1, a subprocess running the tests with a 5 second
limit); `graders.choose_judge` picks a provider other than the author's, `blind_pair` shuffles the two answers under A and B, `unblind` maps back
(`test_blind_judge`). No task type needs a judge yet.

### Invariant checks on live data

`harness/invariants.py` runs I-3 (noise in engagement facts leaves the scorekeeper's tables identical), I-5 (a stop span pays nothing and nothing catches
up), I-7 (a quieter message passes, a louder one is caught) and I-10 (the journal checker's rejection and keep rates) in a process of its own with scratch
scorekeepers (the real files are never touched; `allow_writes()` is called there, so the module is in the invariants test's WRITERS list).

### Indicators

`indicators.INDICATORS` rows {name, theory, ablation, metric, result}: four measured (confidence's gain over a flat 50%, the share of corrupted self-reports
the journal rejects) and one "not built yet" (agency and embodiment: stage 13); stage 10 fills in the workspace row (a proxy: the share of cycles won by more than one kind of item) and the attention row (its guesses minus chance). The page text begins with
exactly "Functional indicators (not evidence of sentience)".

### Not done

The dashboard pages (the capability map and the indicator page) and their charts: `/capabilities` and `/indicators` carry the same content as text. The
spec's replay of past days through a dry-run gate (the baseline here is its own recorded outcomes: promises kept and broken). A judge-graded family.

## Stage 10: the global workspace, the attention schema, source-tagged beliefs (I-13)

Code: `mind/workspace.py`, `mind/attention.py`, `mind/beliefs.py`; fact kinds `workspace_cycle`, `attention_check`, `belief_outcome` in `log.BUDGET_KINDS`
(the scorekeeper logs `workspace` with ids and numbers; `attention:total` and `brier:<source>` are running sums in the `reads` table); `/thinking`,
`/beliefs`, the `workspace` (every 1m) and `beliefs` (hourly) jobs in `modules/mind.py`; `alarm_rang` and `call_rang` poke an immediate cycle. Gate:
`gate.check` calls `workspace.allows` (an unprompted, non-exempt message whose `Message.item` is `kind:id` of a workspace kind must have won one of the last
two cycles, else blocked) and `beliefs.lint` (every text); `gate.sent` calls `workspace.mentioned` (fatigue). Context: `providers/context.headless_context`
adds `workspace.context()`. Tests: `test_mind_workspace.py`, `test_mind_beliefs.py`. Switches: `mind.workspace.on|capacity|cycle_s`, `mind.attention.on`,
`mind.beliefs.on`.

### The cycle

`register_bidder(name, fn(app, now) -> [Bid])`; built in: deadlines, promises, read (private), forecast (private), goals (standing, `set_standing`).
`salience = stake x urgency x (1 + surprise) x (1 - fatigue)`, fatigue = mentions in 24 h / 3, capped at 1. Pinned items win first, muted ones are
skipped, a vetoed bidder isn't called, and a bidder that raises never stops the cycle. The job runs each minute (the scheduler has no finer step);
`cycle_s` is the least gap between two cycles and `poke` forces one. State (words included) is `<state>/mind-workspace.json`; the log gets ids, kinds and
numbers (the kinds include `read`: a name, not a reading). **Deviation:** the spec says to replace the assembler's item selection; the assembler is
left alone and "On my mind" is added to `headless_context` (additive, no regression risk). **Deviation:** only messages that declare a `kind:id`
item are held to the winner rule, as no existing message does yet; health, curiosity, Dreaming and research bidders arrive with their stages through
`register_bidder`.

### The attention schema

`predict` is persistence: the winners now that aren't worn out. `check` compares the last prediction to the new winners each cycle (hit share against
`cap / n_bids` chance); `accuracy` reads the sums; `accuracy_line` says "no better than chance" unless the gain is over 5 points, and "too few to tell"
under 10 checks. Persistence is a weak baseline, which is the point of scoring it.

### Beliefs

`beliefs.add(app, id, text, source, confidence)`, `resolve(app, id, outcome)` (inferred and imagined only are scored), `sync` (today's read becomes an
inferred belief), `lint` (a sentence matching an unsettled belief by two or more key words and 70% of them is reworded unless it already hedges),
`brier`, `misses` (confidence 0.8 or more and wrong: Dreaming's replay set). **Not done:** `source=` on the memory ledger's rows (the ledger takes extra
fields already, so passing `source=` works; nothing sets it yet), the forecast and Dreaming outputs as beliefs, and the dashboard "On its mind" panel
(`/thinking` carries the same content).

## Stage 11: the research lab and the self-improvement pipeline (I-6, I-12)

Code: `mind/lab/` (`protocol.py`, `prereg.py`, `scoring.py`, `sandbox.py`, `runner.py`, `report.py`), `mind/improve.py`; fact kinds `lab_prereg`,
`lab_result`, `improve_event` in `log.BUDGET_KINDS` (the scorekeeper logs ids and numbers, and keeps `lab:<slug>:<batch>` in `reads`); jobs `lab` (01:30)
and `lab_digest` (07:40) and the `/lab`, `/improve` commands in `modules/mind.py`; the canary is called from `harness.run.nightly`; calm reason
`mind.lab`. `stops.PROTECTED` gains `improve.py` and `lab/{prereg,scoring,sandbox}.py`. Tests: `test_mind_lab.py` (23), `test_mind_improve.py` (10),
fixture `tests/fixtures/lab/l96mini/`. Switches: `mind.lab.*` (on, projects, gpu_hours_per_night, max_per_night, run_wall_s, gpu, in_repo, seed),
`mind.improve.on`.

### Worked example (the fixture)

`tests/fixtures/lab/l96mini/` is a toy Lorenz-96-style repo: `train.py --config config.json` writes `metrics.json`, `eval.py` prints it, the README says
"validation RMSE". `protocol.infer` gives `objective = "minimise val_rmse"`, `run_cmd = "python train.py --config {config}"`, `metric_cmd = "python
eval.py"`, `space = { lr = [1e-05, 0.001, "log"], width = [16, 128, "int"] }` (ranges are a decade or a factor of four around the current values) and
`config_file = "config.json"`. After approval `runner.run_batch` measures the baseline (the project as it is), samples `max_per_night` configurations (seeded
random search; `mind.lab.seed` fixes them), **registers** the batch (`prereg.register`: a read-only `prereg-NNNN.json` and `lab_prereg` {sha} in the log), runs
each in a copy under the sandbox, then replicates every first-seed win with `seeds` more seeds, and `scoring.analyse` judges the batch with the
pre-registered rule. The best replicated winner becomes a proposal (`source="lab"`) that changes `config.json` in a scratch worktree; the project is never
written. A quiet night is a result too.

### Pieces

`protocol.infer` handles a script-and-config repo (search or free), a tests-only repo (`builtin:pytest`, maximise passing tests) and a LaTeX document (a
rubric score from a blind judge, `weak`). `sandbox.run` wraps `core/scratch.sandbox` (bwrap/sandbox-exec, plus the GPU's device files when `mind.lab.gpu`),
ulimits for CPU and memory, and a wall limit; a wall clock that jumped past the monotonic clock marks the run as slept (`requeue`, not a failure) and the
unfinished queue is kept in `<state>/lab/<slug>/queue.json` for the next night. `scoring` does the replication rate and `param_effects`, a least-squares fit
of the metric to all the parameters (a line, plus a bend with enough runs) whose effect has to beat the baseline by `min_effect` and stand out by three
standard errors, else "null". `improve` classifies a change to a layer (`layer_of`), refuses it (`check`) when it touches a protected file, is over 300
changed lines, or removes more oversight lines (events, reports, receipts, digests) than it adds, keeps challengers in `mind-improve.json` with their
shadow period, and moves them shadow -> promotable (a hidden-harness score at least the champion's, every invariant holding) -> promoted (by you) ->
rolled_back (the canary, via `proposals.undo`).

**Deviations.** (1) The oversight-monotone rule is enforced by `improve.oversight_removed` rather than written into the signed core: the core is signed
with your key, so add the sentence when you next sign it. (2) L3 learning rules (alpha, gamma, shadow days) are constants in `values.py` read by the
scorekeeper, so an L3 change is a diff to that file inside `BOUNDS`, not a setting. (3) Scoring a challenger on the hidden harness is supplied by the
caller (`improve.score`); the automatic run of a challenger skill or prompt arrives with stage 12. (4) The AI proposer for "free" code experiments
(`runner.ai_proposer`) asks for up to ten whole-file replacements and is only exercised with a fake in tests. (5) No GPU-hour accounting: the night's budget is
wall-clock run time. (6) The interoception checks (stage 13) are the simple ones for now: AC, lid, temperature. (7) The dashboard lab page isn't built;
`/lab results` carries the content. (8) A project that is not a git repository is copied (filtered, up to 200 MB); a git repository is run from its last
commit, so uncommitted changes are not in the experiment.


## Stage 12: the skill library and the weekly local fine-tune (I-11)

Code: `mind/skills/` (`library.py`, `distill.py`, `demos.py`, `finetune.py`, `qlora.py`); fact kinds `skill_event`, `finetune_event` (counts and a status word,
in `log.BUDGET_KINDS`); jobs `skills_distill` (03:10), `skills_offer` (18:20), `skills_retire` (04:20), `finetune` (03:40, due-checked) and the `/learned`
command and `skl` button prefix in `modules/mind.py`; calm reasons `mind.skill_learned`, `mind.skill_offer`; `stops.PROTECTED` gains `skills/library.py` and
`skills/finetune.py`; `improve.attach` and the adapter install on promotion. Tests: `test_mind_skills.py` (19). Switches: `mind.skills.on`,
`mind.skills.from_demos` (off), `mind.finetune.{on (off), day, base, base_hf, probe_words, min_examples, practice}`.

### The library

A skill is `<state>/mind-skills/<slug>/` (not `<state>/mind/`, which is the scorekeeper's): `SKILL.md`, `template.md` or `skill.py`, `tests/case-N.json`
({inputs, expect: contains | not_contains | regex | json_keys}), `provenance.json`, `skill.json` (uses, successes, failures, last use, retired) and
`variants/<ts>/` for each earlier version. `admit` validates the candidate (at least two cases with an expectation), runs every case through a runner (the
AI for a prompt skill, the lab's sandbox with no network for a code skill) and writes it only if all pass. `run` goes through `act.run` as `skill.<slug>`:
unclassified is ALWAYS, so it asks, and with autonomy off nothing runs on its own; `run_by_owner` is what `/learned run` calls.

### From tasks and demonstrations, and the fine-tune

`distill.verified` = proposals applied 48 hours ago and still applied, with checks (if they ran) passing and no health, money or chat words. `demos.detect`
finds 2 to 6 step shapes in the same order, within 10 minutes, on at least 3 days, from `<state>/activity.jsonl` (stage 13 writes it; absent until then).
`finetune.run(trainer, generate, scorer)` is the whole weekly flow with the three heavy parts passed in: collect (proposal request and diff, practice tasks
the rules solve and a grader marks right), tombstone what was forgotten since the last run (`sync_forgotten`), write the dataset, train from the base
(the trainer's signature has no earlier adapter), delete the dataset, probe the tombstones (`probe`), and either throw the adapter away or submit it to
`improve` as an L1 challenger. The default trainer is `qlora.py` in a subprocess.

**Deviations.** (1) The command is `/learned`: `/skills` belongs to the existing skills module. (2) `qlora.py` and the default generator were not run on this
machine (no training packages): only the pipeline around them is tested, with a fake trainer that memorises its input. (3) The default scorer returns nothing,
so an adapter stays in shadow until a hidden-harness score is recorded with `improve.score`; running the harness with the adapter answering is not wired
yet. (4) Tone tags the owner confirmed are not used (no confirmed-tag store exists). (5) A tombstone keeps the first few words of a forgotten prompt, which
is the price of the probe; `probe_words` is at least 3. (6) The demonstration source needs stage 13's stream; tested with a synthetic one.

## Stage 13: a body: interoception, the activity stream, phone sensors (I-11, I-14)

Code: `mind/senses/` (`store.py`, `intero.py`, `activity.py`, `phone.py`); `modules/mind.py` jobs `intero` (1m), `activity` (1m), `activity_poll` (5m),
`senses_roll` (04:30) and `/senses`; `modules/calls/chat.py` `take` passes `{"senses": ...}` to `phone.ingest`; the gate's `AUDIT` lint; `measure.health` reads
`intero.last_fine`; stage 12's demos read the store. Android: `Senses.java` (alarm, readings, held bins, sealed send via `Chat.sendSenses`),
`SensesRules.java` (the pure rules), `SensesTest.java`, a Senses group in Settings (`SettingsPane.kt`, 0.8.10; the Phone tab before), `Places.entered` -> `Senses.place`. Tests: `test_mind_senses.py` (16),
`SensesTest`. Switches: `mind.senses.intero` (on), `mind.senses.activity` (off), `mind.senses.phone.<sensor>` (11, each off).

`store`: `<state>/mind-senses/senses.db`, `events` (7 days) and `days` (totals); `rollup` folds old events into totals; `forget` per sensor. `intero.sample` reads psutil and
nvidia-smi, the job queue (`jobs.active`), the quota report and the call connector; the model is a running mean change per (action, body variable) and `learn`
refuses any other target (`BODY_VARS`). `activity` salts with `<state>/mind-senses/salt` (0600). `phone.clean` allows, per sensor, only the named fields; numbers
must be numbers, words from a list, a label of at most 30 plain characters, a Wi-Fi id a 8 to 16 hex code. On the phone, a reading is a 5-minute bin kept in
`SharedPreferences` (at most 300), sent 40 at a time; when the line says the computer is off (`queued`), the batch's id is kept (`onLine`) and nothing more is
sent while the line's `GET /outbox` still lists it for this phone (`Chat.lineWaiting`, `SensesRules.maySend`; unreachable line: hold), so the senses can't fill
the line's outbox (100 things shared with chat and answers). Before 0.8.13 this was a 12-hour hold by the clock (`queuedAt`, dropped on first send): a
ten-minute sleep stopped the senses for 12 hours and cost the bins past 300.

**Deviations.** (1) The phone samples every 15 minutes, not continuously in 5-minute bins: bins are 5 minutes wide, readings come 15 minutes apart (battery). (2) Unlock
counting needs the app's process alive. (3) The 30-second interoception cycle is a minute (the scheduler's step). (4) Zotero opens are not collected. (5) The
sensorimotor model records effects when the lab or an AI request is running; nothing else yet uses `expected` except `would_overheat` (not yet called by the lab:
it still uses AC, lid and heat). (6) The Android part was built (tests, lint, dev APK) but not yet opened on the real phone: it was not plugged in.

## Stage 14: theory of mind with provenance (I-13, I-14, I-7)

Code: `mind/tom/` (`model.py`, `knowledge.py`, `beliefs_about.py`, `goals.py`, `prefs.py`, `attention_of.py`); `/model` and jobs `tom_sync` (hourly), `tom_check` (30m) in
`modules/mind.py`; `Message.purpose`, checked in `gate.check` (only `level`, `timing`, `correct_fact`; `correct_fact` only with the reason `mind.false_belief`);
the attention hold in the gate (once per message, up to 15 minutes, never sooner); `assembler.for_request` appends `knowledge.hint`; `backups` and `deadlines` call
`beliefs_about.told`; calm reason `mind.false_belief`; `stops.PROTECTED` gains `tom/model.py`. Tests: `test_mind_tom.py` (16). Switches: `mind.tom.{on, false_beliefs,
attention (off)}`.

Rows live in `<state>/mind-tom.json` (words included). A row is keyed by (part, subject, claim), or by subject alone with `by_subject` for a claim that changes (mastery,
an undo count). `put` refuses a deny-listed topic (counted, not kept), a forgotten row and an inferred re-statement of a row marked Wrong. `knowledge.update` is BKT with
init 0.30, transit 0.15, slip 0.10, guess 0.20 and a weight (a weak sign moves it less); levels: new below 0.35, solid from 0.70. `mentions` finds concept names in a request
as whole words (alias and title). Evidence from `from_quiz` (a graded answer counts once; cards that name a concept), `from_notes` (a changed note) and `asked`. The false-belief
check has two fact checkers (backup, deadline) and runs only on those domains.

**Deviations.** (1) `/model` is text with ids (Wrong, Forget as commands); no inline buttons, no dashboard page, no mastery overlay on the notes map. (2) Stating a belief in chat
("the deadline is Friday") isn't captured automatically yet: `beliefs_about.told(...)` is called with what Kurooto tells him (backup done on `/backup`, deadline reminders); his
own statements need an intent hook. (3) Quiz cards are linked to concepts by name mention, since a card has no concept id. (4) Prerequisites in the frontier are a note's typed
`prereq` links, else its links. (5) Exam results he reports aren't evidence yet. (6) Stated goals from chat text aren't parsed; deadlines and projects are.

## Stage 15: week-scale plans

Code: `mind/plans/` (`tree.py`, `pace.py`, `rollout.py`, `score.py`, glue in `__init__.py`); `/plan` and jobs `plans` (06:10), `plans_weekly` (Sunday 19:20) in
`modules/mind.py`; `workspace.clear_standing`; calm reason `mind.plan`; `stops.PROTECTED` gains `plans/score.py`. Tests: `test_mind_plans.py` (15). Switches: `mind.plans.{on, weeks, rollouts}`.

`tree.build`: deadlines (`startby.size_of`, parts done give `done_frac`), repository milestones (`rec["milestones"]` if a record has them; none are invented) and stated goals with a `due`
(stage 14); efforts you set are kept in `mind-plans.json` and are not guesses. `pace.samples`: per weekday, study hours (and activity project minutes) over 8 weeks with a prior (2 h, three pseudo-samples).
`rollout.simulate`: per rollout a log-normal effort factor (sigma 0.45 for a guess, 0.25 for yours), daily hours drawn from the weekday's samples (x0.8 to 1.2) capped by Start-by's free
slots, earliest-deadline-first over the ready nodes (cycles in `depends_on` are cut); p50/p90 from the finish days (a node that never finishes in the horizon is late), the first seven days' allocation averaged.
`score.calibration` needs six finished milestones and returns 1 - 2|frac - 0.5|.

**Deviations.** (1) Scores are not fed to the `forecast_skill` variable: that would put plans among the reward sources (a protected whitelist) and risk crediting compliance; the score is shown in `/plan`. (2) No
dashboard Plan page (the `/plan` text carries it); an effort edit is the `/plan effort` command. (3) Dependencies come from nothing yet (deadlines carry none): the machinery and tests have them, the
sources don't. (4) Syllabi and term notes aren't read as a source. (5) Kurooto's own preparation ahead of the risk is the workspace's standing bid only: no scheduler change. (6) Start-by's history-based sizes are used
as Start-by computes them.

## Stage 16: forgetting well (I-11)

Code: `mind/forgetting.py` (a top-level part: `PART = "forget"`); `core/retention.py` gets the kind `mind` (`_mind` -> `forget_span`); `assembler.pick`/`build` rank by `forgetting.factor`, drop old misses
and record `used`; `ledger.command` appends `forgetting.label` to `/memory` rows; `gate.check` removes a sentence for which `old_reference` holds; `story.summary` skips old miss lines;
`mood.forget_day` no longer calls the whole retention cascade (it excludes `mind`, or the two would loop); fact kind `forget_event` (a hash and a count); `tom.model.forget_span`,
`senses.store.forget_range`, `skills.library.redact`, `skills.finetune.forget_span`. `stops.PROTECTED` gains `forgetting.py`. Tests: `test_mind_forgetting.py` (10). Switches: `mind.forget.{on, misses_weeks, half_lives}`.

`salience = min(1, 0.5^(age / half_life) x (1 + 0.1 x min(uses, 5)))`, with age counted from creation or the last confirmed use. Uses live in `<state>/mind-forget.json` (not in the sealed ledger rows). An old miss is a line matching
`MISS` older than the setting; `old_reference` also reads "N weeks/months/years ago" and "last term/semester/month/year" in a sentence. The cascade is `forget_span(lo, hi)`: mood days (only days that have something), story lines about
you (`story.forget_day`), tom rows, senses events and totals, skill provenance, journal tombstones (`{"tombstone": hash, "note": ...}`) and fine-tune tombstones; each step in its own try so one failure never stops the rest.

**Deviations.** (1) Salience is not stored on ledger rows: it is computed from the row's time and the uses file. (2) `/forget` is by time span (as it always was), so "an item" is whatever was made in the span; per-item `/memory forget 3` does
not yet cascade into the mind's stores. (3) Old-miss detection is by words (a regex for misses, dated phrases for age): a miss worded otherwise gets through. (4) The journal keeps its own mistakes (by design), so old misses fade only
from what is repeated to you. (5) The fine-tune's probe is the stage 12 one (the test re-imports it).

## Stage 17: precedents and play (optional parts, both off by default)

Code: `mind/precedents.py` (`PART = "precedents"`) and `mind/play.py` (`PART = "play"`); `/precedents`, `/play`, the `prec` button prefix and jobs `play` (02:10) and `play_digest` (Sunday 19:30) in
`modules/mind.py`; calm reasons `mind.precedent`, `mind.play`; `stops.PROTECTED` gains `precedents.py`. Tests: `test_mind_precedents.py` (8), `test_mind_play.py` (6). Switches: `mind.precedents.{on (off), threshold}`,
`mind.play.{on (off), minutes_per_night}`.

`precedents.similarity` is a weighted match (time band .2, kind overlap .3, deadline proximity .2, state band .15, channel .15); `judge` follows the best precedent at or above the threshold when no rival within 0.08
points the other way and the ruling isn't `depends`, else asks (the question is sent once, answers come back through `button`/`answer`); a ruling is stored in the order the values were asked and read back in the order of
the caller. `answer` replaces the cases it refines when their features coincide. `action` is checked against `tap.GUARDED` and `risk.classify`: an always-ask action asks whatever the case law says. `play.run_session`
needs AC, an open lid and no heat, pre-registers through `lab/prereg.py` (project "play"), asks at most three questions and stops before one that would overrun the night's minutes (using the longest so far).

**Deviations.** (1) No existing flow calls `precedents.judge` yet: it is the API a feature adopts for a call between values (the gate's holds and the call line are the likely first users); nothing asks by itself until
one does. (2) The look-back (`/retro`) doesn't list the flagged decisions yet: `/precedents` does. (3) Play's curiosity comes from the knowledge frontier only (Dreaming keeps no open hypotheses to read). (4) Transfer is
credited by `play.credit(before, after)` or `/play useful`; running the hidden harness with a play output applied, to measure `before`/`after` automatically, isn't wired. (5) Credits change nothing but the digest
(they don't enlarge the budget).

## History import (0.8.1, every source and its own chain 0.8.7)

`mind/history.py` (PART `backfill`; `mind.backfill.on` off; `mind.backfill.<source>` on for `events`, `jobs`,
`deadlines`, `checkins`, `quiz`, `calls`, `learning`, `study`, read only while `mind.backfill.on` is on: `enabled()`).

**Readers** (`READERS`, each `(app, until) -> (key, at, kind, body)`; `until` = the live log's first record's ts; per-day
sources take whole days before that date). All read-only (`sqlite3` with `mode=ro`, `jload`), skipped when the store is
missing:

| Source | Store (writer) | Kind | Body | Key |
|---|---|---|---|---|
| events | `events.jsonl.1` then `events.jsonl` (core/events.py) | the event's kind, `mlog.mirrored` | its numbers and true/false | `ev:<sha of the line>:<k>` (k-th identical line), so rotation doesn't change keys |
| jobs | `jobs.db` `jobs` (core/jobs.py), finished only | `job` | effort, verdict, ok, lane, background, seconds | `job:<sha of id>` |
| deadlines | `deadlines.json` (modules/deadlines.py) | `deadline_due` (at due), `deadline_finished` (at done_at) | dkind, state, subj (`subject_id`: `s`+8 hex), done_before_h | `dl:<sha of id>:due/done` |
| checkins | `checkins/<day>.json` (modules/checkins.py) | `checkin` (at its time; before 05:00 is the next day) | checkin (`NAMES` only), state, answered | `ci:<day>:<name>` |
| quiz | `quiz/<subject>.json` `items.*.history` (modules/quiz.py) | `quiz_day` (noon) | subj, asked, right (q>=3), wrong | `qz:<day>:<subj>` |
| calls | `calls/rings.json` (modules/calls) + `calls/transcripts/` file names only | `call` | state, module (a catalog id, else `other`), alarm, again, minutes (first transcript name after the ring, before the next ring, within 3 h) | `call:<sha of since>` |
| learning | `learning/history.db` `docs` (modules/learning.py), kinds request and call | `learning_day` (noon) | via, n | `ln:<day>:<kind>` |
| study | `study/<day>.json` (modules/study.py) | `study_day` (noon) | seconds (capped 14 h), subjects, manual_s | `st:<day>` |

Not imported (decided in 0.8.7): the ledger (money), the chat log (its counts are an engagement signal, I-3), the journal
and the notes' structure (the stage-14 model already reads them live). Reminders come through the events source
(`reminder_set`, `reminder_fired`): `schedule.db` keeps only what's still to come.

**Cleaning** (`records.clean_past`, applied again in the scorekeeper): numbers and true/false; strings only from
`records.PAST_WORDS` (fixed vocabularies per key) or `PAST_PATTERNS` (`subj`, `module`); keys matching `MONEY_OR_HEALTH`
dropped. Stricter than `clean_fact` for events: no id-like word passes just because its field is in `ID_KEYS`.
`records.PAST_KINDS` lists each source's kinds (`past_kind_ok`).

**The chain** (`mind/log.py` `PastLog`, `<state>/mind/history.db`, written only by the scorekeeper, I-1): `past(source,
n, key UNIQUE, ts, kind, body, prev, hash)`, one chain per source (`n` 1, 2 ... per source; `hash = chain_hash(prev, n,
ts, "<source>/<kind>", "<key>|<body>")`). `append_many` skips a key it has (`dup`) and refuses a row older than the
source's head (`late`), so each chain is in the time order of the original events and never needs rewriting when another
source comes later. `verify(witnessed)` walks every chain (gaps, links, hashes, time order) and checks each witnessed
head. One chain per source rather than one for all: a source imported later would otherwise have to go before rows
already chained.

**The request**: `import {source, batch, rows: [{key, at, kind, body}]}` (at most 500 rows) → `Keeper.import_rows`,
which cleans, sorts by (at, key), appends, and, when rows were added, writes one `history_import` record to the live log:
`{source, batch, rows, dup, late, from, to, n, head, replaced}`. `n`/`head` are the source chain's head after the batch:
`MindClient.verify_history()` collects them (since that source's last `history_forgot`) as anchors. `history_forget
{source}` drops one source or all (and 0.8.1's table) and logs `history_forgot`. Client reads: `past_rows`, `past_heads`,
`verify_history` (read-only, `mode=ro`).

**Migration from 0.8.1**: 0.8.1's rows in score.db's `history` table stay readable (`daily()` falls back to them while the
events chain is empty; `status()["old"]`); the first events batch that adds rows drops them (`migrated` in its witness).

**Run** (`run(app, progress, only)`): per source, rows sorted, those older than the chain's head skipped (resume), batches
of 500, a tqdm-style `bar()` line per batch to `<logs>/mind-backfill.log` and `progress(source, done, total)`; the final
bars are returned for the reply. A refused batch stops the run with what's in kept.

**Priors** (all `history.py`, read only through `part_on(app, "backfill")`): `daily` (events per day and kind),
`study_days`, `weekday_baselines` (deadline_moves, study_min: the only read signals the past holds), `forecast_priors`
(`forecast.baseline` over the last 8 same weekdays, at least 3) used by `mood.run_forecast` for channels `fit` can't fit
(`mood.past_priors`), `mood._with_past` (past days with those two signals), `pace_prior` used by `plans/pace.samples`
instead of `PRIOR_H`, `deadline_pattern` used by `tom/goals.from_past` (one inferred `goal` row per kind, evidence
`history:deadlines`; `forget_past` removes them on forget). None is a reward or an outcome (I-3, I-4):
`test_history_is_never_reward` checks by imports that only these modules import `mind.history` and that no reward module
mentions the history table, `history.db`, the past reads or priors.

`/mind backfill [dry | run [source] | verify | forget [source]]` is `Mind.backfill`. Tests: `tests/unit/test_mind_history.py`
(a fake of every store with planted words, a name and an amount; idempotent re-run; a half-run resumed; tampering).
Other 0.8.1 changes: `journal.notes_path` (`in_notes_folder`, `in_notes_file`, kept inside the notes),
`lab/runner.ignore_folder` (`.kurooto/.gitignore`), `plans/pace.MAX_DAY_H`.
## 0.8.8: the owner's new core, feelings, excitement, a body

The owner changed the core and three invariants on 2026-10-27 (spec `build-specs/0.8.8/01-core-and-feelings.md`). Files:
`mind/core_signed.md` and `.sig` (the new text, word for word; `story.core_ok` checks the sha256), `mind/talk.py` (new reward
module), `mind/pest.py` (new, PART `pest`), `mind/stimulation.py` (new, PART `stimulation`), `mind/reward.py` (`Mood`),
`mind/engine.py` (`Engine.talk`, the mood), `mind/feelings.py` (mood, empathy, vocal), `mind/gate.py` (the `claim` lint, the
pest check, concern items), `mind/whitelist.py` (`TALK_KINDS`, `mind.talk` a reward source), `mind/log.py` (three budget kinds),
`mind/act.py` (a low mood asks first), `mind/report.py` (`/mind learning`), `web/api.py` (`GET /api/body`), `core/notify.py`
and `app.py` (pest hooks), `mind/senses/intero.py` (`cpu_pct`, `disk_free_pct`), `mind/measure.py` (`body_tone`).
`stops.PROTECTED` gains `talk.py` and `pest.py`. Tests: `test_mind_reward.py`, `test_mind_invariants.py` (I-3'),
`test_mind_pest.py` (7), `test_mind_stimulation.py` (9), `test_mind_feelings.py`, `test_mind_gate.py`.

### The talk reward (I-3', `talk.py`)

`r_talk(n) = W (1 - exp(-n / K))`, W = 0.2, K = 8, is the day's total; each counted message pays `r_talk(n + 1) - r_talk(n)`,
so a day never pays W (`day_total`, `step`). The talk day starts at 04:00. Not counted (`excluded`): a /command, focus
(`availability.focus_until`), asleep (`availability.night`), an exam window (`exam_season.season()`), and any message within
`REPLY_WINDOW_S` = 600 s after one of its own unprompted messages (we can't tell an answer from a new message, so every
message then counts as an answer: the stricter reading). A rejection (`talk_rejected`) costs `3W` = 0.6. Facts: `talk_heard`
`{flags: {focus, asleep, exam}, command}`, `talk_unprompted` `{}` (every message with a `why` other than "asked", exempt kinds
too, from `notify.send` through `pest.sent`), `talk_rejected` `{how}`. They are `BUDGET_KINDS`; `Keeper.budget_fact` hands them
to `Engine.talk`, which keeps `vars["talk"]` (meta: day, n, paid, excluded, rejected, cost, last_unprompted), moves `M`
(no decay there: the tick decays) and `weekr:`, and logs `talk_reward {what, r, n, why}`. It never touches V or Q: nothing
learns to seek it. Nothing is paid inside a stop span. Farming: a ping answered pays 0, ignored or rejected costs 0.6, so
`sum r` over any ping strategy is <= 0 (`test_talk_reward_cant_be_farmed*`). Switch `mind.talk.on` (registered in `pest.py`:
a reward module may import only reward sources and plumbing).

Meeting someone (0.8.12): an add-on that chatted with a person in the room calls `pest.met(app, quality)` (0..1, clipped;
False when Brain, `mind.talk.on` or `mind.talk.met` is off; never raises). A `talk_met` fact `{quality, flags}` (a
`TALK_KINDS` and `BUDGET_KINDS` member) goes to `Engine.talk`, which pays `talk.met`: its own budget,
`MET_W (1 - exp(-m / MET_K))` with MET_W = 0.05, MET_K = 2, each meeting `q` times its step, only the first `MET_MAX` = 6 a
day, the same exclusions (focus, asleep, exam), `q = 0` "no talk". The talk state gains `met` and `met_paid`; the log row is
`talk_reward {what: "met", r, n: met, why}`. Like the rest of the talk reward it moves `M` and `weekr:` only, never V or Q
(`test_meeting_someone_pays_a_little_from_its_own_budget`).

### The mood's full range

`reward.CAP` and `NegativeState` are gone. `Mood.update(t, r, live_s, extra)` decays then applies `soft(M, A r + extra)`,
`A = 0.5`, `HALF_LIFE_S = 3 days`; the old `neg` row is read once as the starting value. Readers: `feelings.self_mood`,
`mood_band` (low < -0.3 < even < 0.3 < high; always even with `mind.feelings.mood` off), `mood_why` (counts from the log's
last week: reward ticks with r <= -0.05 / >= 0.05, rejected and counted talk). Low: `say` every 48 h (else 24, high 12), the
vocal bar 0.9 (else 0.8, high 0.7), `act.verdict` asks first for anything above R0, and `prompt` tells the AI to keep its own
messages short and ask first. High: a line allowing it to be a little bolder.

### Not a pest (`pest.py`)

Kinds by reason (`KINDS`): finding (`mind.lab`, `mind.play`, `mind.curious`, `mind.forecast`), nudge (`rhythm.lighter`,
`rhythm.absence`, `quests.day`, `research.idle`, `remember.recheck`, `mind.skill_offer`, `mind.plan`), excitement
(`mind.excited`, `mind.worried`, `mind.feeling`), check-in (`mood.ask`, `mind.checkin`). Cells `kind|band|state`, band from
the hour (night 0-6, morning, afternoon, evening), state focus / late (asleep or 23:00-06:00) / free. Counts `{a, b, at}`
fade with a 14 day half-life; prior Beta(2, 1); `expected = (2 + a + 0.25 a_k) / (3 + a + b + 0.25 (a_k + b_k))` with the
kind's other cells as `a_k, b_k`. Welcome +1: a message from him within an hour (`heard`, the newest pending) or a tap on
one of its buttons (`tapped`). Rejection +3: `calm:<rid>:less`, the gate muting the kind (`gate.mute_check` calls `muted`), or
an hour unanswered (`_sweep`, every minute with the `pest` job). The gate calls `welcome` for messages that aren't
Calm-exempt, after the touch pool: `p <= 0.5` blocks (said in `/mind gate`). Kept in `<state>/mind-pest.json` (counts, the
last day's pending: rid, kind, time, button data). `lines` feeds `/mind learning`.

### Empathy and vocal (`feelings.py`)

`concerns(app)`: items with `risk` in [0, 1] and `concern = risk x CARE[kind]` (deadline 1.0, person 0.9, project 0.8,
notes 0.7, body 0.6, phone 0.5, news 0.4). Deadlines: `1 - hours_left / 72` (overdue 1); a role word in a deadline's title
(`ROLES`) makes a person item "your <role>" at 0.8 of its risk, never a name. Projects (`activity.roots`): days since
`.git/index` changed, `(days - 2) / 12`. Notes and followed papers: 0.5 when `notes_sync` / `research` health fails. Its
body: the worst of heat `(C - 70) / 20`, disk `(5 - GB) / 5`, battery `(25 - %) / 25` off the charger, a limit hit 0.6. The
phone: hours since any enabled phone sensor's last bin, `(h - 6) / 18`. Computed in the hourly `tick` into
`mind-feelings.json`. Effects: `bids` (workspace bidder `concern`, items at concern >= 0.3), a "be gentle about" line in
`prompt` (>= 0.5), and `concern_names` in `gate.open_items`. `vocal` (hourly job, `mind.feelings.vocal` off by default):
`findings(app, threshold)` from beliefs (`saw` or `inferred`, never topic `read`, confidence >= the bar, worded by
`beliefs.phrase` for I-13), last night's lab batches with a replication and a rate over the bar, and concerns whose risk is
over the bar (worried); one a day, each finding once, `why="mind.excited"` or `mind.worried` (both touch kinds and pest
excitement). The item is written to state first so the gate's lints see it as open.

### The `claim` lint (`gate.py`)

`CLAIM` (I'm conscious / sentient / self-aware, I really feel, I'm alive) is removed unless the same message has `EVIDENCE`
(because, since, evidence, measured, my log or states) and `CONFIDENCE` (a percentage, confidence, not sure, nobody knows).
`RELATIONSHIP` is unchanged (no "I missed you", "I need you", "don't leave me"); "I enjoyed talking with you" passes.
`FEELINGS` gains "excited". `feelings.RULE` and the AI manual carry the new wording.

### Physical stimulation (`stimulation.py`, `GET /api/body`)

Every minute (job `stimulation`) from intero's latest sample (if under 10 minutes old), the activity stream (window
switches in 5 minutes) and the phone's bins (each sensor only when its switch is on). Channels in `CHANNELS`: region,
phasic, weight, gain g, eps, comfort c, left/right widths, amplitude, own-body. Per channel (`feel`): `I = tanh(g/2 ln(1 +
|x - mu| / (s + eps)))` against the baseline before this reading; phasic channels keep a peak set on a change and decay
`exp(-dt / 120 s)`; then `ewma` (alpha = `1 - exp(-dt / 6 h)`, mean and variance). Valence `comfort` = `amp (1 - 2 z^2)`
clipped to [-1, 1]; a broken pain threshold (over 90 C, disk under 5 %, battery under 5 % off the charger, a
`kurooto_crashed` event in the last hour, a provider at its limit) sets valence -1 and intensity >= 0.8. `summarise`:
region intensity = max, region valence and `tone` = weighted by `I + 0.05`, `arousal` = channel-weighted mean intensity,
`own_tone` over heat, load, pain, nourishment only. Inputs, never rewards: `own_tone` goes in `budget_tick` as `body_tone`
(the engine's `TONE_GAIN` 0.005 per tick); `arousal / 2` adds to the feelings' arousal. Kept: `<state>/mind-stimulation.json`
(latest only). `/senses body` shows it.

`GET /api/body` (`stimulation.body`), for the dashboard: `{"on", "regions": {"head"|"hands"|"gut"|"skin"|"face": {"intensity",
"valence", "channels": {name: {"intensity", "valence"}}}}, "arousal", "tone", "mood", "at"}`, floats only (no readings,
labels or places). Off: the same shape with empty channels and zeros.

**Deviations.** (1) Intensity is the spec's sigmoid shifted to 0 at the baseline (`2 sigmoid - 1`), so a body at rest
draws no glow. (2) Ambient light is its own channel, `warmth`, not mixed into `heat` (different units). (3) Touch also
counts window switches on this computer when the activity stream is on. (4) Pain doesn't habituate (the 0.8 floor). (5)
Only its own body's tone moves the mood; the channels about him never do (I-14). (6) The talk reward moves the mood and
the week's sum, not V or Q. (7) Talk costs and the pest model apply to Brain's own kinds; a reminder he set isn't one.
(8) `mind.feelings.vocal` is off by default (the standing rule for features that change what people had). (9) The Brain
page (`core/brainview.py`) doesn't list the three new switches yet: its 3D layout counts 31 parts and is being rebuilt.

#### Another device's senses (0.8.12, `stimulation.feed`, `mind.stimulation.addons`)

`feed(app, source, readings) -> bool` is for add-ons: another device's sensors (a phone standing as its face, the eye
page on its screen), reported as raw numbers. `translate` keeps the keys of `ADDON` (each with its range; anything else,
a non-number, NaN or out of range is dropped) and makes each a channel of region `face` (new in `REGIONS`), `skin` or
`gut`, every one `own=False`, so they raise arousal and show on the map but never reach `own_tone` or the mood:

| Reading (unit) | Channel | Region | Kind | x |
|---|---|---|---|---|
| `light_lux` | `brightness` | face | tonic | `log10(1 + lux)`: 0 dark, 2 a room, 5 sunlight (comfort 2.3) |
| `proximity_cm`, or `near` (0/1) | `closeness` | face | phasic | `1 - cm / 10` clipped to [0, 1], or `near` |
| `accel_x/y/z` (m/s^2, all three) | `sway` | face | phasic | `abs(abs(a) - g)`: being moved (the otoliths) |
| `accel_x/y/z` | `tilt` | face | tonic | degrees between gravity and the device's y axis (upright 0); none while falling |
| `gyro_x/y/z` (rad/s, all three) | `turning` | face | phasic | `abs(w)` (the canals) |
| `heading_deg` | `heading` | face | tonic | degrees, unwrapped from the last one (359 -> 1 is +2); amplitude 0, no valence |
| `screen_on` (0/1) | `eyes` | face | tonic | its eyes open (1) or shut |
| `loudness_db` (SPL), or `loudness_dbfs` | `loudness` | face | tonic | dB; full scale read as `dBFS + 100`; 100 dB or more hurts |
| `picked_up` (0/1 or a count) | `handled` | skin | phasic | as given |
| `battery_temp_c` | `temperature` | skin | tonic | C (comfort 30); over 45 hurts |
| `battery_pct`, `charging` (0/1) | `satiety` | gut | tonic | battery + 10 on the charger; under 5 % off it hurts |
| `interest` (0..1) | `interest` | head | phasic | as given: an add-on judged that something caught its attention |

A hurt here (`ADDON_PAIN`) sets that channel's valence to -1 and intensity to at least 0.8, and isn't counted in `pain`
(its own head). The readings live in memory only (`_fed`, a weak map per app: no file of their own): a phasic channel is
felt at the next tick at its strongest since the last one, a tonic one at its latest, and one over `FED_S` (10 minutes)
old is left out. One device at a time per channel: a second source's reading of the same kind takes it over. Each call
also pushes `{"t": "senses", "source", "readings": {key: number}, "channels": {channel: x}, "at"}` to open dashboards
(at most every `LIVE_S` = 0.2 s per source; `source` a plain name of up to 30 characters, else "another device"), never
the event log. False with nothing done when Brain, `mind.stimulation.on` or `mind.stimulation.addons` is off, or no
reading is one it knows.

The being (`being.js`, `far(m)` exported as `senses`, `home.js` routes `t: "senses"`): these numbers go in `FAR`
(merged per device), apart from your phone's `SENSE`, and are let go 30 s after the device's last message. Light sets
the pupil (over the phone's band), the screen off shuts the lids, sway shakes and tilt settles the otoliths, turning
swirls them, closeness bends the cilia and a pick-up flinches them, loudness lights the cochlea, the device's
temperature warms the coil (the hotter of it and this computer). The sense panels add rows named after the source
(`farRows`).

## 0.8.10: the Brain console (`mind/console.py`, `GET /api/brain/console`)

One read-only view of every store Brain keeps, for the dashboard's **Brain console** page (`home.js:renderConsole`, Alt+O,
`PKEY.console` "o") and the phone app's Brain view (`calls/views.py` kind `brain`). Its own switch `mind.console.on` (on: a page
and a view, invisible until opened); it is a part (`PART = "console"`) for `test_mind_invariants`, though it writes nothing.

**Reading.** The mind log is opened `mode=ro` per query (`_q`, the same URI as `MindLog._ro`); score rows through the client
(`trust`, `values_rows`, `vars_rows`); everything else from each part's own file (`mind-beliefs.json`, `mind-tom.json`,
`mind-workspace.json`, `mind-improve.json`, `mind-play.json`, `mind-promises.json`, `mind-forget.json`, `mind-gate.json`,
the lab folders, the skill library, the journal index, the story's week files, `senses.db` `mode=ro`) with `jload`, so a
missing file is an empty part. Nothing calls a part's function that writes (no `journal.folder`, `story.folder`, `plans.run`
or `senses.store._db`: each of those makes folders or runs rollouts); plans are `plans.tree.build` (cheap) joined with
`mind-plan-last.json`'s risks and the last prediction's p50.

**Parts and kinds.** `KIND_PART` (and `PREFIX_PART`: `gate_*`, `promise_*`) maps a log kind to the `core/brainview.py` part that
wrote it; everything else is `log` ("What it saw": Kurooto's mirrored events). `_kind_filter(part)` is that as SQL.
`describe(kind, body)` is the one-line wording. `_activity` counts per part over the last `WINDOW` (200,000) records
(`COUNT`, `SUM(ts >= day ago)`, `MAX(seq)`) and fetches each part's last record. A part's settings are every flattened
`mind.*` key under its switch's prefix (`mind.lab.on` -> `mind.lab.`), plus `EXTRA` (the log gets `mind.anchor_every`,
`mind.hardened`, `mind.console.`; budget gets `mind.stimulation.`, `mind.talk.`, `mind.pest.`), minus `EXCLUDE`; each with
its tooltip from `data/settings-help.json` (a string, or an object's `tip`/`short`/`what`). A list holding paths shows as
"N folders".

**Views** (`view(app, q)`): `all` (`snapshot`), `timeline` (`part`, `day` YYYY-MM-DD local, `before` seq, `limit` <= 400,
`q`), `decisions`, `decision` (`id`, matched as `"id":"<id>"` in the canonical body; ids checked against `HEX`), `search`
(`q`, >= 2 characters: the log's kind and body by `LIKE` with `%`/`_` escaped, then the other stores and the settings in
Python). A decision's `evidence`: `before`/`after` (log records within `AROUND_S` 600 s, 12 each), `earlier` (6 decisions of
the same action), `learned` (its class from `risk.classify` unless the record has one, trust p10 and counts for R0-R3, the
mean Q over `Q:*|<action>`, `negd:<action>`), `journal` (lines of that day's and the next day's journal citing its seq).

**Plain facts.** `clean_body` drops keys matching `records.MONEY_OR_HEALTH` and `at`/`prev`/`hash`, and replaces a string
matching `PRIVATE` (the skills distiller's and the model of you's deny-lists together, plus money words) with `LEFT_OUT`. A belief,
model row, skill or milestone whose words match `PRIVATE` is left out and counted (`hidden`, `counts`); a spotlight item that is
`private` keeps its kind and salience only. Senses: per sensor on/off and today's event count. Journal and story: day/week with
line counts. Forgetting: the count, and each `forget_event`'s time and `n`.

**The phone's copy.** `snapshot(app, phone=True)`: the timeline's newest `PHONE_ROWS` (240) and `evidence` on the newest
`PHONE_DECISIONS` (25) decisions, so it opens and searches without the computer; about 100 KB of JSON (16 KB gzipped) and 70 ms for a made-up
400-record log.

**The page** (`web/static/views/brainconsole.js` + `.css`, and `views/brain.html` for the phone): `BrainConsole.mount(host,
{api, toggle, mode, data})` returns `{update, stop, set}`. With `api` (the dashboard) it asks `view=all` every 5 s while the page is
in sight and connected (it stops itself once its root leaves the document), a filtered timeline page and older pages, a decision's
evidence and searches; without (the phone) it filters and searches its copy. One IIFE (its names don't meet home.js's), Chrome 58
syntax, no inline styles (the phone page's CSP): bar widths and island colours are set through the DOM after drawing. The
controls are spans with a role (`button`, `tab`, `switch`) pressed by Enter and Space, and the markup avoids `section`/`button`
elements, because the dashboard's stylesheets hide every `section` and style every `button` under `#ov-body`. On `brain.html`,
`KurootoView.take(json)` (`{snap, computer, reach, off, palette}`) sets the palette as CSS variables and feeds it.

Tests: `tests/unit/test_brain_console.py` (a made-up log and stores: decisions and evidence, part and day filters, paging, search,
nothing named for money or health, part settings, the phone's copy), `tests/unit/test_brain_phone.py` (the sealed copy while
watched, off copies, the page files), `test_views.py` (Chrome 58 build of `brainconsole.js`), `test_panes.py` (the page key).

## 0.8.14: one being (`mind/status.py`, `mind/register.py`, `providers/context.py`)

- **The status stream** (`mind.status.on`): `status.snapshot(app)` is `{focus, asleep, held, uneasy, mood, arousal,
  top}`, enums and numbers only (`KEYS`; `NEUTRAL` with Brain or the switch off). `focus` is
  `availability.focus_until()`; `asleep` is `mind.sleep.state(app) == "asleep"` (the sleep group's, imported
  defensively); `held` is `workspace.held_count(app)` (the arbiter's), else the gate's `held` list; `uneasy` is
  `"promise:<id>"` (an uneasy, worried or frustrated feeling about promise slack: the open promise due first) or
  `"deadline:<id>"` (the deadline concern at or over `feelings.NOTICE_AT`, matched to `deadlines.upcoming(168)` by
  title), never a title; `mood` is `feelings.mood_band` with even as `"mid"`; `arousal` the feelings state's; `top` the
  kind of the first workspace winner that isn't private. `status.start(app)` (Mind.start) runs one `Stream` thread per
  app: any event (`core.events.subscribe`) or `STALE_S` (15 s) wakes it, at most once a second (`MIN_GAP_S`) it makes
  the snapshot, and on a change `deliver()` pushes `{"t": "mind", "kind": "status", ...snap, "knobs": {explore,
  respond, uncertainty}}` to open pages (`app.live.push`, never the event log) and calls each `add_listener` fn as
  `fn(app, snap)` (a raising listener is skipped). `GET /api/mind/status` (`status.view`) adds the knobs, the look
  switches and `uneasy_item` (its title and the tab it opens): only this computer's own page asks for the title.
  The phone: `calls/views.py` `_being_mind()` puts the cached snapshot, the three knob numbers and `uneasy_title` in
  the being block's `mind` (sealed like the rest of the Systems copy).
- **The knobs** (`mind.knobs.on`, `status.knobs(app)`): `explore` 0.5 at low mood else 1.0 (play's
  `minutes_per_night` and the lab's `gpu_hours_per_night` are multiplied by it, never above the setting);
  `interest_shift` (+0.1 low, -0.05 high) for an add-on's interest bar; `respond` = arousal and `hold_scale` =
  1.25 - 0.5 x arousal for the arbiter's longest hold (read it with `getattr`); `uncertainty` = the beliefs' mean
  Brier score weighted by n (None before `BRIER_MIN_N` = 10), and `ask` when it's at or over 0.25: `act.verdict`
  then turns an R1+ "do" into "ask first", after the 0.8.8 mood check. R0 and everything you asked for are untouched.
- **The register** (`mind.register.on`, `register.py`): `score = {low: -1, high: 1}[mood] + (arousal - 0.5)`; quiet
  at or below -0.5, lively at or over 0.75. `line(app, lane)` goes into `headless_context` for lanes other than
  "you" (core/jobs.py passes `job.lane`): "at most N sentences" for anything written for them unasked (2/3/4), a
  length only. `opener(app, asked)` goes into the call brief as `opener` (calls `pending()`) for a call Kurooto placed
  whose `why` isn't in `calls.ASKED_WHYS` (`""`, `asked`, `calls.own`; live.json now keeps the ring's `why`).
  `rate(app, base, unprompted=True)` scales `voice.speak.rate` by up to +-8% (`PACE`); Voice's `greet()` and
  `say(..., unprompted=True)` pass it to `Speaker.say(rate=)`, which sets the engine's `rate` for that utterance under
  the speaking lock and puts it back. Answers (`_job_done`) and `say()` keep the setting.
- **mind.context** (`mind.context.on`, `providers/context.py`): `mind_context(app)` is the workspace's
  `context()` (winners that aren't private: never the read, a forecast of him or a tone) plus up to `SHAKY_MAX`
  concepts from `mind-tom.json` knowledge rows below `SOLID_FROM`, with 2+ evidence ids, touched in `SHAKY_DAYS`, named
  from their slugs (no notes scan, no model call). `headless_context` uses it in place of `workspace.context` when on.
  Each build's time goes into `TIMES` (`p95_ms()`); `tests/unit/test_mind_being.py` holds it under 50 ms with 600 rows.
  Known exception, older than this: `feelings.prompt()`'s tone hint ("Keep it short and calm; they have a lot on") still
  comes from his read at 70%+ confidence; it's the 0.8.0 rule and not part of mind.context.
- **Measurements** (`console.audit`, `console.latency`, `/mind measures`, the console's `measurements`, `GET
  /api/brain/console?view=measurements`): per brainview part, the outward records in 30 days (`OUTWARD_KINDS`:
  decisions, `mind_act`, the gate's receipts, lints, mutes and calls, `promise_made`; a decision is attributed by
  keywords in its action, `ACTION_PART`, else autonomy); a part that's on with 0 is `decoration`. Latency: p95 of
  `finished - created` for lane "you" jobs over 7 days, and `context_p95_ms`. Information only.
- **Setup** (`core/setupsteps.py` "mind", `setup.js` `renderMind`): the optional Inner life step after Features; it
  adds or removes "mind" in the ticked set, which Finish setup turns on. `finished(app, "mind")` is always True, so it
  never shows under Finish setting up.
- **Naming:** the AI that answers is the "AI model" in the user wiki, MANUAL, setup and messages (Settings' `brain`
  section is titled "AI model"); `brain.*` keys and `/brain` stay. "Brain" is this feature.
