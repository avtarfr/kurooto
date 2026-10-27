# Debugging

Where to look when something doesn't work, from the outside in. Everything here is read-only unless it says
otherwise. On a developer machine, point every command at a scratch install first (`KUROOTO_HOME=<folder>`, see
[testing.md](testing.md#cli-runs-need-a-scratch-kurooto_home)); never debug against someone's real install by changing
its files.

What a user sees and is told to do is in [../user/troubleshooting.md](../user/troubleshooting.md); keep the two in step.

## The first five minutes

1. `kurooto paths`: where config, data, state, logs, cache and the program are (`core/paths.py:paths`).
2. `kurooto doctor` (`cli.py:doctor`, rows from `diagnostics.py:checks`): exit code = number of `FAIL` rows.
   `kurooto fixme` adds the troubleshooting row and known issues to each failing one ([below](#fixme-corefixmepy)).
3. `kurooto logs -n 200` (`watch.py:follow_log` on `<logs>/kurooto.log`).
4. The event log: `<state>/events.jsonl`, one JSON object per line, newest last (past 10 MB the older part is in
   `events.jsonl.1`).
5. `kurooto top --once`: the machine, what's on, open questions, jobs, what's scheduled next.

## `kurooto doctor`

- Builds a full `App()`. If that fails, only basic rows are shown (Python, folders writable), and with `--bundle` a line
  on stderr says no zip could be made; the exception is the bug, so run `python -c "from kurooto.app import App; App()"`
  in a scratch `KUROOTO_HOME` to see it.
- Rows (`diagnostics.checks`): Python, OS, the folders writable, free space (at least 5 GB), running
  (`<state>/daemon.json` pid), time zone (`timezone_check`), the AI model, each enabled module's `health()` (for
  calls, `call_line()` when doctor runs outside the daemon), `more_checks` (Telegram `getMe`, agent export, add-ons'
  `doctor_checks()`), `health_rows` (`working: <feature>` from `app.health.evaluate(net=True, save=False)`),
  `layout_checks` (notes layout and files folder), `setup_rows` (a `--` note per setup step skipped for now,
  `core/setupsteps.py:doctor_rows`), backups, installed prerequisites.
- `ok` / `--` (a note, `ok is None`) / `FAIL` (`ok is False`; counted).
- `--json` prints `{version, problems, checks: [{name, ok, detail}]}`.
- `--fix ID` asks the **running** daemon to run a fix (`POST /api/health/fix`, `core/health.py:Health.fix`). `ID` is
  the check's id (a feature id, or `kurooto`). Exit 2 when Kurooto isn't running.
- `--bundle` writes the diagnostics zip (below).

## Health: "Kurooto keeps itself working" (`core/health.py`, `core/health_checks.py`)

- One `Check` per feature (`Module.health_check()`, built-ins in `core/health_checks.py:builtin` / `BUILTIN`; add-ons
  return their own). A check is either "should have worked within `every_h` awake hours" (an event it emits) and/or a
  read-only probe.
- Awake time (`Health.awake_s`) subtracts offline periods (`core/presence.py:Presence.offline`), pauses, and battery
  saver for heavy features, so a sync that couldn't run with the lid shut isn't a failure.
- Fixes (`FIXES`): `sync`, `rearm` (re-register a module's scheduler jobs: `Module.start()` again), `reconnect`,
  `alarm`, `deliver` (flush the focus queue and the network outbox). `AUTO` = all but `sync`.
- The daily pass (`health.when`, "daily 21:00"): auto-fixes, re-check after `RECHECK_S = 600`, then `decide()`: alarm
  problems and urgent ones (or a deadline within `SOON_H = 48` h) get a message now, the rest goes to the weekly
  summary or a digest. State: `<state>/health.json`. `/health` on Telegram and `GET /api/health` show the same.

| Check id | Fails when | Fix |
|---|---|---|
| `telegram` | `getMe` answers 401/404; the reader task died | `reconnect` |
| `google` | refresh token missing or about to end; Classroom not synced in 26 h | `sync` |
| `notes_sync` | GitHub token rejected or expiring; no sync in 24 awake hours | `sync` |
| `calendar` | no refresh in 12 h | `sync` |
| `calls` | line not linked for 15 awake minutes; Cloudflare login gone; the line doesn't answer | `reconnect` |
| `alarm` | tonight's alarm not planned, or can't ring (no line, no phones) | `alarm` |
| `backups` | no `backup_done` in 72 h | none |
| `profile` | no successful `profile_save` in 72 h | none |
| `gbrain` | no `gbrain_sync` in 24 h | `sync` |
| `kurooto` | the focus queue or the network outbox stuck for 30 min | `deliver` |

## `/fixme` (`core/fixme.py`)

What a user sends when something broke, maybe the AI itself, so nothing in it needs an AI. `/fixme` (Telegram, the
phone app, the dashboard's terminal prompt through `web/tools_api.py:say`) and `kurooto fixme [words]`
(`cli.py`, `fixme.cli`: builds an `App()` like doctor, so it works with the daemon stopped) call `fixme.answer`:

- `problems(app, net)`: the failing health results (`Health.evaluate(save=False)`, with their `Result` and so their
  fix), then doctor's other failing rows (`diagnostics.checks(app, health=False, net=net)`), one per check id
  (`_doctor_id` maps doctor's row names; a feature's row goes by its title). `net` is `False` for `/fixme` (the
  probes' last answers stand in, like `/health`) and `True` for `/fixme now` and `kurooto fixme`.
- Each problem gets troubleshooting rows: `ROWS` maps check ids to pieces of the "What you see" cell; a check that
  isn't there and has no `help` of its own is matched by words (`find`, at least two shared words and one from its
  title). The rows come from `data/troubleshooting.md`, an exact copy of `docs/wiki/user/troubleshooting.md` (the
  docs aren't in the package); `tests/unit/test_fixme.py` fails until you copy it again after editing the page, and
  checks every `ROWS` piece names exactly one row.
- Free text (`/fixme the phone doesn't ring`): `words` (stop words out, a rough stem, `SAME` for "rang"/"ring") and
  `find`: two points per word shared with "What you see", one with the section's title, half with "What to do"; the
  best three within 60% of the top score.
- Known issues (`issues`, `hits`): `data/known_issues.json`, plus the list of a newer version that's downloaded and
  checked (`update-ready.json` names it; `<app>/versions/<v>/src/src/kurooto/data/known_issues.json`), plus a line
  when the running version is on the signed yank list (`Updater.yanked(False)`, the cached copy).
- Buttons: health's own Fix buttons (`Health._buttons`, `health:<id>:fix`); a known issue's `"action": "fix:<id>"`
  adds that check's Fix, `"update"` an Update button (`upd:latest:now`). Where no button comes back (a terminal), the
  text says `/fixme fix <id>` (or `kurooto doctor --fix <id>` from `kurooto fixme`).
- The AI, only after: `ai_works` (a brain picked, `available()`, and its last finished request didn't fail; nothing is
  asked of it) decides whether **Ask my AI** (`fixme:last:ai`) and the `/fixme ai` hint are offered. `explain` sends the
  last answer (state `fixme.json`) as a `text_only`, low-effort job; in a terminal `msg.job` is set so the prompt
  shows the answer when it comes. Event: `fixme` (counts only).

**Adding a known issue.** An entry in `src/kurooto/data/known_issues.json` under `issues`:

| Field | Meaning |
|---|---|
| `id` | unique; a newer version's list adds only ids the running one lacks |
| `versions` | `"*"`, `"0.5.14"`, `"<0.5.16"` or comparisons joined by commas (`">=0.5.14,<0.5.16"`) |
| `seen` | what the user sees, in their words |
| `checks` | doctor or health check ids it explains (`calls`, `telegram`, `ai`, `space`, a feature id...) |
| `symptom` | a regular expression (case doesn't matter) for a failing check's line or what was typed |
| `keywords` | phrases; one matches when all its words were typed |
| `fix` | what to do, in plain words |
| `action` | optional: `"update"` (an Update button) or `"fix:<check id>"` (that check's Fix button) |

With none of `checks`, `symptom` and `keywords`, everyone on those versions sees it. Add a test case only when the
matching needs a new rule. It ships with the next release, and installs that downloaded that release already show it
before switching to it.

## Logs

- `daemon.py:setup_logging`: `<logs>/kurooto.log`, `RotatingFileHandler` 2 MB x 3, INFO, also stderr on a TTY.
  Logger names are `kurooto.*`.
- The launcher logs nothing, and `cli.py:start_background` sends the daemon's stdout/stderr to `DEVNULL`. A crash
  before logging is set up (an import error) leaves no trace in `kurooto.log`. To see it, run the daemon in the
  foreground in a scratch home: `KUROOTO_HOME=/tmp/k uv run kurooto run`.
- Other logs: `<state>/watch.log` (`kurooto watch`), `<state>/terminal/kitty.log`, `<state>/gbrain/upkeep-<date>.log`.
- Space keeper cuts files in the logs folder past `space.log_mb` (`core/space.py:log_items`).

## The event log

`core/events.py:Events.emit(kind, **fields)` appends `{"ts", "kind", ...}` to `<state>/events.jsonl` and calls live
listeners (the dashboard's feed). A caller's own `kind=` is renamed `subkind`. It is the best record of what happened:

```sh
tail -n 50 "$STATE/events.jsonl"
grep '"kind": "job_failed"' "$STATE/events.jsonl" | tail
```

Kinds worth grepping for (the full list is in [core.md](core.md#events)): `started` / `stopped`, `module_failed`
(a module's `start()` or background task raised), `job_failed` (a scheduled action raised or is missing:
`App._job_done`), `job_done` / `job_ended` / `job_crashed` / `job_then_failed` (AI jobs), `notify_failed`,
`calm_held` / `calm_stopped` (a message held or dropped on purpose), `telegram_error`, `tool_failed`,
`question_hook_missing` (an answer arrived for a feature that's now off), `update_*`, `health_*`, `presence_*`.

Note: `events.jsonl` is never trimmed by Kurooto (Space keeper only trims the logs folder), and `Events.tail` reads the
whole file.

## The diagnostics bundle

`kurooto doctor --bundle` (`diagnostics.py:bundle`, `Redactor`) writes
`<data>/kurooto-diagnostics-YYYYmmdd-HHMMSS.zip` with `doctor.json`, `versions.json`, user `settings.json`
(redacted), `features.json`, `hardware.json`, `jobs.json` (last 30, status only, no prompts), `events.json` (last 400,
only safe fields), `setup.json` (`core/setupsteps.py:timings`: each setup step's status, seconds and visits, nothing
typed), the last 1500 log lines (redacted) and a README. Redaction: every known secret value
(`KNOWN_SECRETS`, `Secrets.names()`, Google tokens) becomes `[secret]`; token and key patterns, emails and URLs are
masked; the notes path becomes `[notes folder]`, the home folder `~`, the user's name `[you]`; keys matching
`SENSITIVE_KEYS` become `[set]`. Nothing is sent anywhere. If you change what the bundle collects, extend
`tests/unit` coverage of the redactor and re-read the README text in `diagnostics.py`.

## Where the state is

All under `Paths.state` unless noted. Formats and owners are listed in [core.md](core.md#files-and-folders).

| Question | Look at |
|---|---|
| Is it running, which pid? | `daemon.json`, `supervisor.json`, `locks/daemon.lock` |
| Which port is the dashboard on? | `web.json` |
| What's scheduled? | `schedule.db` (SQLite, table `schedule`) or `kurooto top --once` |
| What did the AI do? | `jobs.db` (tables `jobs`, `attempts`), `jobs/<id>-result.md` for long answers, `kurooto jobs` |
| Why was a message held or dropped? | `calm.db` (table `sent`), `/why` on Telegram |
| Questions and approvals | `ask/<id>.json` |
| Paused, off, held for battery? | `power` state files (`off.json`, the held-jobs file from `core/power.py`) |
| Quiet, focus, on a call? | `quiet.json`, `focus.json`, `oncall.json` |
| Telegram | `telegram/offset.json`, `map.json`, `paused.jsonl` |
| Calls | `calls/link.json`, `rings.json`, `live-health.json`, `transcripts/` |
| Updates | app folder `current.json`, `update.json`, `bad.json`; state `update-seen.json` |
| Free AI limits | `quota.json` |

## Common failures

| Symptom | Where it's decided | What to check |
|---|---|---|
| "Kurooto is already running" (exit 3) | `daemon.py:run`, the `daemon` file lock | another copy, or a stale lock on a crashed process (`locks/daemon.lock`) |
| Starts, then dies at once | launcher back-off, `daemon.supervise` | run `kurooto run` in the foreground in a scratch home; crashes before logging aren't in `kurooto.log` |
| Rolled back after an update | `update/launcher.py:rollback` | `update.json` (`rolled_back`, reason), `bad.json`; see [release-and-updates.md](release-and-updates.md) |
| Bot doesn't answer | `modules/telegram/__init__.py:run` | `telegram_error` events (401 revoked token: the channel is dropped until the module restarts; 409: another reader or a webhook), `power` paused, `off.json`, Chat off |
| Answers never come back | `core/jobs.py` | `kurooto jobs`; `job_deferred` (waiting for a free limit's reset), on battery (background work waits for the charger), the watchdog (`stuck`, `timeout`) |
| "The AI stopped without an answer" | `Verdict.DENIED` | agy refused an unattended step; `<state>/agy-tools.json` (granted rules), the consent question, `~/.gemini/antigravity-cli/settings.json` |
| A scheduled thing never happens | `core/scheduler.py:Scheduler.tick` | `job_failed` with `outcome: error` (the action raised, often a signature mismatch: actions are called as `fn(payload)`) or `missing-action` (its module is off or didn't register it); `power` holds |
| Message arrived late or not at all | `core/notify.py`, `core/calm.py`, `core/presence.py` | `calm_held` (daily limit, evening bundle), focus queue `focus-queue.jsonl`, network outbox `net-outbox.jsonl` |
| Phone doesn't ring | `modules/calls/__init__.py:Calls.ring` | line linked (`calls/link.json`), `calls` health row, Calm's call limit, availability blocks (`call_block`), the Android app's checklist |
| Dashboard 403 | `web/server.py:Handler` | Host header (a proxy or another hostname), another OS account on Linux (`web/peer.py`), Origin |
| `notes layout FAIL` | `diagnostics.layout_checks`, `core/layout.py` | `notes.layout`, `notes.paths`, `files.folder` |
| Windows: `PermissionError` on save | `core/state.py:jsave` retries the rename 10 times | antivirus or the indexer holding the file; persistent means a real permission problem |

## Debugging in code

- Reproduce in a test first: `tests/conftest.py`'s `env` fixture gives a paired app talking to a fake Telegram
  (`env.say("text")`, `env.press("prefix:ref:act")`). See [testing.md](testing.md).
- Drive the scheduler by hand in tests: `await app.scheduler.tick()` runs what's due; `Scheduler(clock=...)` takes a
  fake clock.
- Run one job synchronously: `app.jobs.run_next()`.
- Inspect a live install's SQLite read-only: `sqlite3 "file:$STATE/jobs.db?mode=ro" "select id,status,verdict,brain
  from jobs order by created desc limit 10"`.
