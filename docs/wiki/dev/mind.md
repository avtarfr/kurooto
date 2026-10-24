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
[Stage 02: stopping is fine, and protected files](#stage-02-stopping-is-fine-and-protected-files)

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
