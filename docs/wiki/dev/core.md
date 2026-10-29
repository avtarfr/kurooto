# Core services

`src/kurooto/core/` holds everything features share. `App.__init__` (`app.py`) builds the services in this order:
`Paths` → `Settings` → `Secrets` → `egress.attach` → `Events` → `Availability` → `Scheduler` (with gates) → `Notifier` → `Power` →
`AboutYou` → `Quota` → `Jobs` → `Updates` → `Ask` → `Presence` → `Health` → `Calm` → `Keep` → `Rhythm` → every module in the catalog →
add-ons. Anything a module needs is reached through `self.app.<service>`.

Contents: [settings](#settings) · [secrets](#secrets) · [paths](#paths-and-the-notes-layout) ·
[files and folders](#files-and-folders) · [scheduler](#scheduler) · [scheduled jobs](#every-scheduled-job) ·
[jobs](#jobs) · [events](#events) · [notify and Calm](#notify-and-calm) · [ask](#ask-questions-and-approvals) ·
[availability](#availability) · [power](#power) · [presence](#presence) · [quota](#quota-free-ai-limits) ·
[reserve](#the-reserve) · [space keeper](#space-keeper) · [retention](#retention-and-forget) ·
[egress](#egress-every-request-on-the-internet) ·
[memory](#memory-the-ledger-threads-and-the-assembler) · [hardware](#hardware-profiles) ·
[processes](#running-programs) · [locks](#locks-and-atomic-writes) · [Windows](#windows-notes) ·
[smaller pieces](#smaller-core-pieces) · [keep or drop](#keep-or-drop-corekeeppy) ·
[your rhythm](#your-rhythm-corerhythmpy) ·
[the message policy](#the-message-policy-dream-rsi-part-two-corepolicypy)

## Settings

`core/config.py`.

- Defaults: every section is declared by `register_defaults(section, dict)` at **import time** of the module that owns
  it (e.g. `register_defaults("jobs", {"stuck_min": 10})` at the top of `core/jobs.py`). Calls for the same section
  merge (`merge`). It's the only way (`Module` has no `defaults` attribute), and `tools/gen_settings_guide.py` reads
  only these calls.
- User overrides: `<config>/settings.json` holds only what the user changed. `Settings.all()` is
  `merge(defaults, add-on layer, user)`, so a new default in an update reaches everyone who didn't change that key.
- Add-on layer: `set_layer()` (called by `core/overlay.py:load`) lays an add-ons folder's `settings.json` between the
  defaults and the user's file; it can't set `modules`, `overlay` or `profile` (`overlay.NO_DEFAULTS`).
- API: `get("a.b.c", default)`, `set("a.b", value) -> old` (rewrites the user file with `jsave`), `reset("a.b")`
  (drops the override). Dotted keys address nested dicts.
- `Settings` keeps the merged tree (`_merged`) and makes it again only when the file's mtime, size or inode changed
  (a `set` here, the CLI, a hand edit) or the defaults or layer did (`register_defaults` and `set_layer` bump `_GEN`).
  `get` hands out a copy of a dict or list it returns, `all()` a copy of the whole tree, so callers may change what
  they get. The copies are made by `config._copy` (dicts, lists and plain values directly, anything else through
  `copy.deepcopy`), several times quicker than `copy.deepcopy` (0.6.1). Before 0.6.1 every `get` merged and deep-copied everything (about 6 ms), and a dashboard request made a
  thousand or more: 5 to 13 s for `/api/state` and `/api/today`. There is no cross-process lock, so the CLI and the
  daemon can overwrite each other's concurrent `set`. Change settings in the daemon (the API's `POST /api/settings` or a module
  method), not by editing the file while it runs.
- Sections and where they are registered (the full list with every key and default is generated into
  `docs/SETTINGS_GUIDE.md` and the user wiki's settings guide by `tools/gen_settings_guide.py`, from the code and
  `tools/settings_guide/`; `tests/unit/test_settings_guide.py` fails when it's stale or a setting has no entry, so add the
  entry and regenerate after adding or changing a setting; see "The settings guide" below):

| Section | Registered in |
|---|---|
| `you`, `modules` | `app.py` |
| `brain` | `providers/__init__.py` |
| `jobs` | `core/jobs.py` |
| `notify` (`desktop`, `desktop_kinds`, `app_kinds`, `app_chat`), `notify.calm`, `notify.presence` | `core/notify.py`, `core/calm.py`, `core/presence.py` |
| `availability` | `core/availability.py` |
| `ask` | `core/ask.py` |
| `keep` | `core/keep.py` |
| `memory` (`threads`, `thread_days`; `recall`, `budget_tokens`) | `core/threads.py`, `core/assembler.py` |
| `power` | `core/power.py` |
| `quota` | `core/quota.py` |
| `health` | `core/health.py` |
| `hardware` | `core/hardware.py` |
| `space` | `core/space.py` |
| `notes`, `files` | `core/layout.py` |
| `sources` | `core/sources.py` |
| `agents` | `core/agent_export.py` |
| `autostart` | `core/autostart.py` |
| `web`, `look` | `web/server.py` |
| `updates` | `update/service.py` |
| one section per feature (`<module id>`) | the module's own file |

Modules read their own section with `Module.setting(key)` (= `settings.get(f"{id}.{key}")`).

## Secrets

`core/secrets.py:Secrets`. Never in `settings.json`.

- The OS keychain through `keyring` (service `kurooto`), else `<config>/secrets.json` (mode 0600).
- The file is used when there is no usable keyring backend, when `KUROOTO_HOME` is set, when
  `KUROOTO_SECRETS=file`, or when the marker `<config>/secrets-in-file` exists (`keep_in_file(True, names)`, used by
  `core/autostart.py` when Kurooto starts at boot on Linux, before the keychain is unlocked).
- API: `get(name)`, `set(name, value)`, `delete(name)`, `names()` (file only: the keychain can't be listed).
- Names in use include `telegram.token`, `web.token`, `gemini.api_key`, `<brain>.api_key`, `google.client`,
  `google.tokens[.<account>]`, `calendar.ics`, `calls.call_secret`, `calls.connector_secret`, `calls.ntfy_topic`,
  `calls.ntfy_key`, `calls.vapid_jwk`, `calls.vapid_public`, `calls.github_token`, `notes_sync.token`,
  `profile.token`, `profile.key`, `ledger.key` (the memory ledger's key, `core/ledger.py`; in `profile.NEVER`).
  `diagnostics.py:KNOWN_SECRETS` lists the ones the bundle redacts; add new names there.

## Paths and the notes layout

`core/paths.py:paths()` returns a frozen `Paths(config, data, state, logs, cache, app)`:

| Root | Linux | macOS | Windows | `KUROOTO_HOME=H` |
|---|---|---|---|---|
| config | `$XDG_CONFIG_HOME/kurooto` | `~/Library/Application Support/Kurooto/config` | `%LOCALAPPDATA%\Kurooto\config` | `H/config` |
| data | `$XDG_DATA_HOME/kurooto/data` | `.../Kurooto/data` | `%LOCALAPPDATA%\Kurooto\data` | `H/data` |
| state | `$XDG_STATE_HOME/kurooto` | `.../Kurooto/state` | `%LOCALAPPDATA%\Kurooto\state` | `H/state` |
| logs | `<state>/logs` | `~/Library/Logs/Kurooto` | `<state>\logs` | `H/state/logs` |
| cache | `$XDG_CACHE_HOME/kurooto` | `~/Library/Caches/Kurooto` | `%LOCALAPPDATA%\Kurooto\cache` | `H/cache` |
| app | `$XDG_DATA_HOME/kurooto/app` | `.../Kurooto/app` | `%LOCALAPPDATA%\Programs\Kurooto` | `H/app` |

XDG variables are honoured only when absolute. `Paths.ensure()` creates them all. `KUROOTO_HOME` is the switch that
keeps tests, portable installs and development runs away from a real install.

The notes folder ("workspace") is `you.workspace`, else `~/Documents/Kurooto` (`app.py:default_workspace`; `H/workspace`
under `KUROOTO_HOME`). Where each kind of note goes is decided only by `core/layout.py`: `KINDS` (daily, profile,
how_to_help, inbox, course, lecture, concept, exam_prep, doubts, home, research, project, runs, ...), two `PRESETS`
(`kurooto` and `zettelkasten`), per-kind overrides in `notes.paths`, and `files.folder` for binary files. Use
`layout.path(app, kind, **fields)`, `layout.rel`, `layout.link`, `layout.file_dir`, `layout.frontmatter`; never build
a notes path by hand. Links between notes go through `layout.note_link(app, target, label, from_note=)` (0.6.0):
`notes.links` "wiki" gives `[[target|label]]`, "markdown" gives `[label](rel/path.md)` relative to `from_note` (else
the notes root; spaces `%20`). Read links back with `layout.link_targets(text, from_rel)` / `Layout.note_targets`,
which take both styles; never match `[[` by hand, so a switch can't break a reader. `describe()` tells the AI the
markdown style. `Layout.check()` feeds `kurooto doctor`'s `notes layout` row. Templates may use `{year}`,
`{month}` and `{day}` too (`Layout._fields` derives them from `date`; `translate` maps `journal/<YYYY-MM-DD>` to the
whole place when the date isn't one part of it).

`core/notesfit.py` fits that to an existing folder (0.5.20; the setup page's Notes step, `web/api.py` `notes/fit*`):
- `scan(root)` walks it (no AI; hidden folders and `node_modules` skipped; `MAX_FILES` 20,000, headers read for all,
  links from the first `SAMPLE` 3,000) and `facts()` counts top-level folders, daily-note shapes (`daily_shape`:
  `Daily Notes/{date}.md`, `{year}/{month}/{day}.md`), wikilinks against markdown links (with or without `.md`) and
  header keys.
- `propose(root, current)` proposes `link_style` (`notes.links`, from the scan's link counts; nothing found keeps
  the one in use) and picks the preset (`choose_layout`: zettelkasten folders and `id`+`aliases` headers against
  kurooto folders) and one line per `LINES` kind (daily, inbox, subject, concept, project) with `confidence` (0 to 1),
  `why` and `found`. `paths_from(preset, lines)` adds the places that follow (course, lecture, class log, exam prep,
  doubts under the subject folder; note under the inbox; runs beside a `{project}/index.md`) and drops what equals
  the preset; `merged_paths` keeps earlier `notes.paths` entries the lines don't decide. `preview()` renders `PREVIEW`
  with today's date and `linear-algebra`.
- `plan(root, old, new)` is the dry run. `kind_of` matches each note against the old layout's templates (most literal
  text first; a `{subject}` that is one of the layout's own top folders doesn't count; folder kinds `handwritten`,
  `runs`, `inbox` keep the rest of the path). Only `ours(front, old)` notes move: `made_by`, or `trust_tier:
  agent_written` when the old layout is the zettelkasten. Daily notes are counted (`daily_left`), never moved.
  `fix_links` rewrites `[[path]]` and relative markdown links to moved notes only inside Kurooto's text (`_spans`: the
  whole of its own notes, `<!-- kurooto:k -->...<!-- /kurooto:k -->` blocks, the hubs one-liner, `- [[...]]` lines in
  the home and research hubs) and counts the rest in `theirs`; a moved note's own relative links are rebased and a
  zettelkasten `id:` follows it. Clashes: a taken place (`os.path.samefile` tells a case-only rename from another
  file) or two notes on one place.
- `apply_plan(plan, state_dir, digest)` refuses unless the digest (moves, settings, each edited file's text) matches
  the one shown and there are no clashes; it renames, writes the link fixes (`newline=""`, so CRLF stays), removes the
  folders it emptied and writes `<state>/notes-moves/<stamp>.json` (moves, edits with their old text and the new
  text's sha256, folders made and removed, settings before and after). A failure halfway puts back what was done.
  `undo(state_dir)` reverses the newest log: an edited file whose sha changed since is left (a problem is reported),
  the notes move back, the folders it made go if empty; `undo_app` restores `notes.layout`, `notes.paths` and `notes.links`.
- Another folder than `you.workspace`: `apply` only switches `you.workspace` and the settings; nothing moves between
  folders.
- `scanned(root)` (0.6.1) is what `GET notes/fit` uses: `scan()` and `facts()` kept for the last folder asked about,
  while its notes stay the same (the same notes and folders from `walk()`, each note with the same mtime and size).
  The kept scan drops the full texts (only `facts()` reads them) and each call gets a copy of the facts. A 2,271-note
  folder: 180 ms read afresh, 15 ms kept. `preview`, `apply` and `undo` still `scan()` afresh.

Tests: `tests/unit/test_notesfit.py` (fixture folders in Kurooto's layout, Obsidian-style, zettelkasten and mixed).

## Files and folders

Everything Kurooto writes, by root. JSON files go through `core/state.py:jsave` unless noted. "Backup" is
`modules/backups.py` (state is included except `SKIP_STATE`: `web.json`, `daemon.json`, `supervisor.json`, `off.json`,
`pause.json`, `power-held.json`, `update-ready.json`, `backups.json`, `focus-queue.jsonl`, `profile.json`, and the
folders `locks/`, `logs/`, `cases/`, plus `telegram/offset.json`, `telegram/pairing.json`, `calls/link.json`). "Profile"
is the encrypted profile (`core/profile.py:KEEP`).

### config/

| File | Format | Owner |
|---|---|---|
| `settings.json` | JSON, user overrides only | `core/config.py:Settings` |
| `secrets.json` | JSON, 0600, the keychain fallback | `core/secrets.py:Secrets` |
| `secrets-in-file` | text marker | `Secrets.keep_in_file` |
| `cloudflare/` | wrangler's own config home for the call line | `modules/calls/deploy.py:wrangler_env` |

### state/ (core)

| File | Format | Owner |
|---|---|---|
| `schedule.db` | SQLite, table `schedule` (WAL, 0600) | `core/scheduler.py:Scheduler` |
| `jobs.db` | SQLite, tables `jobs` (`scratch`: the scratch folder a change request writes in), `attempts` (WAL, 0600) | `core/jobs.py:Jobs` |
| `jobs/<id>-result.md`, `jobs/told-<brain>-<verdict>` | long answers (kept `privacy.keep_days`); once-an-hour markers | `Jobs._deliver`, `Jobs._problem` |
| `calm.db` | SQLite, table `sent`, kept 45 days (`text`/`title` only `privacy.keep_days`) | `core/calm.py:Calm` |
| `calm.json`, `calm-undo.json` | bundle day and suggestion state; undo records | `Calm` |
| `ledger.db` | SQLite, tables `rows` (kind, sub, at, upd, src, h, `blob` = AES-GCM sealed JSON), `seen`, `forgot` (WAL, 0600): the memory ledger, encrypted; gists, threads, rows read from notes. Not backed up unless `backups.memory` | `core/ledger.py:Ledger` |
| `gists.jsonl` | (0.5.17 only) the gists before the ledger; moved into it and removed on first use | `core/gists.py:_move` |
| `dream-policy.json` | the day of the last tuning round and the last 30 decisions with their replay scores | `core/policy.py:tune` |
| `dream-tuning.json` | Dream RSI part three: the day of the last night round, the last 60 decisions (every area's, with mirrors of applied message changes), outcomes per kind of change, the skill proposal | `core/tuning.py:night` |
| `tuning/proposal-<id>.md` | a proposed skill waiting for Apply or No | `core/tuning.py:proposal_ready` |
| `keep.json` | uses per feature and day (90 days), last use, when counting started, answers | `core/keep.py:Keep` |
| `local-helper.json` | the offline helper's speed test, outages seen (30 days), the internet down since, the offer | `core/helper.py:Helper` |
| `notes-moves/<stamp>.json` | each Notes-step move: moves, link edits (old text, new sha256), folders made and removed, settings before and after, `undone` | `core/notesfit.py` |
| `setup.json` | the setup page's steps: `steps.<id>` = `{status: done\|skipped\|open, seconds, visits, left_at}`, and `chosen` (the features ticked before the page was closed) | `core/setupsteps.py` |
| `rhythm.json` | usual quiet hours, the last learned change and its Undo, lighter-day and absence marks, quiet week | `core/rhythm.py:Rhythm` |
| `repair.json` | two-readings questions waiting for a tap (20, for 24 h) | `core/repair.py` |
| `meetings.json` | minutes requests and their action-item offers (60; your words kept 2 days, for Not about the meeting), weekly briefs sent | `core/meetings.py` |
| `repo-projects.json` | projects set up from repositories: `repos` by key (address or folder, the copy's folder, commit, tags, the rules' and the AI's summary, `pieces` = inferred ids, files' text hashes, graph item keys, milestones offered), `offers` (Set it up / Not now, 3 days) | `core/repoproject.py` |
| `events.jsonl`, `events.jsonl.1` | JSON lines, append-only; past 10 MB it moves to `.1` (replacing the one before) | `core/events.py:Events` |
| `focus-queue.jsonl` | JSON lines: messages held during focus | `core/notify.py:Notifier` |
| `net-outbox.jsonl` | JSON lines: Telegram messages held while offline (rewritten with `write_text`) | `core/presence.py` |
| `presence.json` | heartbeat, last stop, offline periods (15 days) | `core/presence.py:Presence` |
| `ask/<qid>.json` | one question each, kept `ask.keep_days` (0: `privacy.keep_days`) after settling | `core/ask.py:Ask` |
| `quiet.json`, `focus.json`, `oncall.json` | `{"until": iso, ...}` | `core/availability.py:Availability._set` |
| `pause.json`, `off.json`, `power-held.json` | pause until, turned off, jobs held by power mode | `core/power.py:Power` |
| `quota.json` | counts and learned limits per pool (no content) | `core/quota.py:Quota` |
| `brain-limits.json` | AIs skipped until a limit's reset: `{brain: {until, src, hits, at}}` | `providers/fallback.py` |
| `health.json` | last results, what was told | `core/health.py:Health` |
| `fixme.json` | the last `/fixme` answer, for `/fixme ai` | `core/fixme.py:answer` |
| `hardware.json`, `model-sizes.json` | the machine as read once; registry sizes | `core/hardware.py:current` |
| `daemon.json`, `supervisor.json` | `{pid, started}` | `daemon.py:run`, `supervise` |
| `web.json` | `{port, url, started}` | `web/server.py` |
| `tools-access.json`, `tools-list.json` | the tools-only key and URL; the last tool list | `web/server.py`, `web/tools_api.py`, `core/mcp.py` |
| `reserve/*.md` | Markdown copies for AI programs, including `self.md` (what Kurooto runs; `.self.json` its fingerprint) and `ai-manual.md` | `core/reserve.py`, `modules/alarm.py:_mirror`, `core/selfdoc.py` |
| `note-history/...` | earlier versions of notes the AI edited (20 each) | `core/tools.py:NoteTools` |
| `scratch/<sid>/` | a change request's scratch folder: `scratch.json`, `work/` (a git worktree, or a mirror), `base/` (originals as first copied); removed after Apply, Discard or `proposals.keep_days`; `.nohooks/` an empty hooks folder for Kurooto's git calls | `core/scratch.py` |
| `proposals/<pid>.json`, `<pid>.diff`, `<pid>/before/` | proposals (title, summary, files, status, how it was applied), their diffs, the earlier versions Undo puts back; settled ones go after a month | `core/proposals.py` |
| `sync-all.json` | the last "sync everything" | `core/syncall.py` |
| `profile.json` | Profile sync state | `core/profile.py` |
| `aboutyou.json` | About you state | `core/aboutyou.py` |
| `agent-skills.json` | what was exported where | `core/agent_export.py` |
| `upgrades.json` | one-time upgrade steps done | `core/upgrade.py` |
| `update-ready.json`, `update-seen.json`, `yank.json` | staged update; anti-replay; yank cache | `update/service.py`, `update/updater.py` |
| `<brain>-worked.json` | marker: this agent program has answered here | `providers/base.py:Brain.mark_worked` |
| `agy-tools.json`, `backups/agy-settings-*.json` | what was granted to agy; backups of agy's settings | `providers/agy.py` |
| `locks/<name>.lock` | file locks | `core/lock.py:Lock` |
| `logs/` (Linux, Windows, `KUROOTO_HOME`) | `kurooto.log` | `daemon.py:setup_logging` |

### state/ (features)

| Path | Owner |
|---|---|
| `telegram/{offset,pairing,map,menu,name}.json`, `telegram/paused.jsonl` | `modules/telegram` |
| `chat/history.json` (last 10 turns, 1200 chars each) | `modules/chat.py` |
| `calls/{rings,live,link,inbox,answer-nonces,live-health,textcalls}.json`, `calls/lessons.md`, `calls/transcripts/*.txt` (and `*.did.json`: what each call's tools did, for its gist; goes with the transcript) | `modules/calls`, `core/gists.py:note_call` |
| `calls/searches.json` (what calls searched your notes for, 8 days at most), `dreaming-curious.json` (lines shown, settled, their buttons' offers, repositories' first commits) | `modules/curious.py` |
| `dreaming-consolidate.json` (duplicates and disagreements waiting, by reference only; pairs settled by keyed hash; Undo records, a gist's words sealed with the ledger's key) | `modules/consolidate.py` |
| `dreaming-fold.json` (owner-only: lines waiting for Keep, in your words with source and day; decided by hash; Undo records; each source's read mark) | `modules/fold.py` |
| `alarm.json`, `alarm-last.json`, `alarm-skip.json`, `alarm-ringing.json` | `modules/alarm.py` |
| `deadlines.json`, `deadlines-recurring.json` | `modules/deadlines.py` |
| `checkins/<day>.json`, `capture/<day>.json`, `study/<day>.json`, `study/session.json`, `study/timer.json` | check-ins, capture, study (`timer.json`: Study mode's timer) |
| `subjects/term-note.json`, `subjects/skip-<day>.json`, `subjects-short-names.json` (short names used once, waiting for a second use) | `modules/subjects.py` |
| `exam_season.json`, `revision.json`, `startby.json`, `quests.json`, `reminders-snooze.json` | those modules (`revision.json`: Exam season's revision plan, `modules/revision.py`) |
| `doubts/*.json`, `hints/<id>.json`, `quiz/<subject>.json`, `quiz/{session,offered}.json`, `quiz/_links.json` (link recall cards) | doubts, hints, quiz |
| `retro.json`, `retro-state.json` (also `routines` asked, added or declined, and `fixes` with their undo), `observations.json`, `retro-skills/` | `modules/retro.py` |
| `research-papers.json`, `research-logs.json`, `research/digest-papers.json`, `research/digest-last.json`, `research/zotero.json` (Zotero's user id and the items added) | `modules/research.py`, `modules/zotero.py` |
| `drafts/<id>.json` | Check my draft (`modules/drafts.py`), the last 100 |
| `books.json`, `gbrain.json`, `gbrain-checkup.json`, `gbrain/` | books, gbrain |
| `integrate/` (`ledger.json`, `seen.json`, `chapters.json`, `garden.json`, `budget.json`, `notation.json`, `made.json`, `dupes.json`, `pending/`, `undo/`, `vectors.db`) | `modules/integrate.py`, `core/conceptgraph.py`, `core/graphmerge.py`, `core/readbudget.py` |
| `handwritten*.json`, `handwritten/<id>/` | `modules/handwritten.py` |
| `handwritten-links.json`, `handwritten-undo/` | `modules/handwritten_links.py` |
| `calendar.json` | `modules/calendar.py` |
| `google-classroom.json`, `google-signin.json`, `google-needs-<part>` | `modules/google.py` |
| `classroom-posts.json` (each course's posts of the last 30 days: time, title, link; for missed-class catch-up) | `modules/google_classroom.py:remember_posts`, written by both Classroom checks |
| `classroom-notes/`, `mail-digest/`, `reply-drafts/`, `digest-email-*`, `drive-upload.json`, `drive-temporary.json`, `agent-plan.json` | the Google parts |
| `notes-sync.json`, `backups.json`, `ollama-ours.json` | notes sync, backups, local models |
| `skills/{packs,auto-packs}.json`, `skills/drafts/`, `skills/tectonic-declined` | `modules/skills.py` |
| `remember/recheck.json` (per kept line, by `fact_key`: seen, used, kept, asked; the week's asks; undo records) | `modules/remember.py` |
| `learning/history.db` (FTS5 search index, not backed up), `learning/{state,changes}.json`, `learning/before/` | `modules/learning.py` |
| `classpacks/active.json`, `classpacks/drafts/` | `modules/classpacks.py` |
| `lidsafe/{held,waiting,said}.json` | `modules/lidsafe.py` |
| `cases/cases.json` (never backed up or bundled) | `modules/cases.py` |
| `terminal/` (kitty config, session, log, default-terminal record) | `modules/terminal` |

### data/, cache/, app/, and outside

- data: `about-you/*.md` (About you reports), `skills/routines.json`, `profile/` (encrypted profile working copy),
  `books/`, `book-text/`, `book-brain/`, `gbrain/`, `classroom/<subject>/`, `classpacks/`, `mail/confidential/`,
  `backups/skills/`, `kurooto-diagnostics-*.zip`.
- cache (safe to delete; Space keeper prunes after `space.cache_days`): `books/`, `handwritten/`, `send/`,
  `study-packs/`, `tectonic/`, installer downloads.
- app: see [release-and-updates.md](release-and-updates.md#install-layout-srckurootoupdate).
- Notes folder: daily notes, class logs, course and concept notes, `about-me/*`, `inbox/*`, `research/*`,
  `kurooto/*`, `.gitignore` (Notes sync), `.kurooto/requests/` (agy handover, git-ignored).
- Outside Kurooto's folders, only on purpose: autostart entries (`core/autostart.py`: HKCU `Run`, a LaunchAgents plist,
  `~/.config/systemd/user/kurooto.service` or `~/.config/autostart/kurooto.desktop`), PATH edits (`core/pathfix.py`),
  app-menu entries (`core/shortcuts.py`, `modules/terminal/launchers.py`), the Windows Terminal fragment
  (`modules/terminal/wt.py`), the `kurooto` command shim (`cli.py:install_finish`), exported skills
  (`core/agent_export.py`: `~/.claude/skills`, `~/.agents/skills`, `~/.gemini/antigravity-cli/skills`, only when the
  user turns it on), agy's settings file (`providers/agy.py:allow_tools`, backed up first, consent asked). Each of these
  is a place the test guard protects (`tests/isolation.py:protected_paths`).

## Scheduler

`core/scheduler.py:Scheduler`, SQLite `<state>/schedule.db`, so jobs survive restarts and sleep.

- `action(name, fn)`: register a handler. **Every handler is called as `fn(payload)`** (a dict); it may be async. A
  bound method that takes no argument fails with `TypeError` on every run. Write `def tick(self, p=None)` or wrap it
  (`lambda p: self.tick()`).
- `every(key, spec, action, payload=None, *, module="", misfire="coalesce", respect="none")`: a recurring job. Calling
  it again with the same spec keeps the job's next run; a changed spec reschedules.
- `at(when, action, payload=None, *, key=None, module="", replace=True, grace_s=43200, respect="none") -> key`: a
  one-off. Naive datetimes are local time. `replace=False` leaves an existing key alone (a debounce).
- `cancel(key)`, `cancel_prefix(prefix)`, `get(key)`, `jobs(prefix)`, `due()`.
- Specs (`next_after`), in `you.timezone`: `every 10m`, `every 2h` (at least a minute), `hourly`,
  `daily 05:00`, `daily 07:00,13:00,19:00`, `weekly sun 19:30`. A bad spec raises `ValueError`.
- `run_forever(stop)` runs `tick()` and sleeps until the next job, at most 30 s, so clock jumps are noticed.
  `_poke()` wakes it when a job is added.

What `tick()` does with each due job, in order:

1. **Hold** (`Scheduler.hold = Power.hold`): in saver or paused mode a job whose module may not run is pushed an hour and
   recorded in `power-held.json`; `Power.release()` runs them the moment the mode allows. Jobs with `module=""` are held
   only when paused.
2. **Gate** (`respect`): `"quiet"` uses `Availability.quiet_gate`, which postpones to the end of **focus** time, not the
   `quiet.json` "no calls" window: every job that uses it sends a message (check-ins, quizzes, the morning lists), and
   "no calls" lets messages through while focus holds them; `"call_block"` uses `Availability.call_gate` (no built-in
   job uses it). Postponed jobs keep their key.
3. **Misfire**: a one-off later than its `grace_s` gets `payload["missed"] = True`; later than 120 s gets
   `payload["late_s"]`. A recurring job with `misfire="skip"` more than 120 s late doesn't run (no built-in job uses
   `skip`); `coalesce` runs it once. Either way the next run is computed from now.
4. **Run**: `outcome` is `ran`, `error` (the exception text goes to `last_result`), `missing-action` (nothing registered
   under that action name: its module is off or never registered it), or `skipped`/`held`/`postponed`. One-offs are
   deleted unless the handler rescheduled the same key.
5. `on_result` = `App._job_done`, which emits `job_failed` for `error` (the exception) and `missing-action`
   (`no action '<name>'`).

Handlers run on the event loop thread. A slow synchronous handler (git, a zip, an HTTP call) blocks every other job and
async task for its duration; long work should start a thread (`threading.Thread`, `asyncio.to_thread`) as
`gbrain`, `books`, `retro`, `profile` and `handwritten` do.

Keys are `"<module id>:<name>"` so `Module.stop()` (`cancel_prefix(f"{id}:")`) removes them; actions are
`"<module id>.<name>"`. `Module.every()` and `Module.action()` build both. `LABELS` and `describe()` give the words
`/status` and `kurooto top` show.

## Every scheduled job

Recurring (key → when; setting that controls it):

| Key | When | Setting | Owner |
|---|---|---|---|
| `calm:tick` | every 5m | | `core/calm.py:Calm.start` |
| `keep:tick` | daily 12:00 (respects quiet) | `keep.ask` | `core/keep.py:Keep.start` |
| `local_helper:tick` | every 1m | `local_helper.offline`, `local_helper.on` | `core/helper.py:Helper.start` |
| `local_helper:offer` | daily 12:30 (respects quiet) | `local_helper.offer` | `core/helper.py:Helper.start` |
| `rhythm:tick` | every 30m | `availability.learn_night`, `notify.calm.lighter_after`, `availability.absence_days` | `core/rhythm.py:Rhythm.start` |
| `ask:sweep` | every 10m | | `core/ask.py:Ask.start` |
| `retention:expire` | daily 04:15 | `privacy.keep_days` | `core/retention.py:start` |
| `memory:nightly` | daily 04:30 | `memory.thread_days` | `core/ledger.py:start` (notes read again, `threads.expire`) |
| `proposals:cleanup` | daily 04:20 | `proposals.keep_days` | `core/proposals.py:start` (unanswered proposals expire, scratch folders go) |
| `proposals:morning` | `proposals.morning` (daily 07:30) | `proposals.morning` | `core/proposals.py:start` (the night's proposals, only while Dreaming is off) |
| `reserve:refresh` | every 10m | | `core/reserve.py:start` |
| `agents:export` | hourly (only while export is on) | `agents.export` | `core/agent_export.py` |
| `health:daily` | daily 21:00 | `health.when` | `core/health.py:Health.start` |
| `updates:check` | every 6h | | `update/service.py:Updates.start` |
| `updates:phone_app` | every 6h (and `updates:phone_app:start` 2 min after a start) | | `update/service.py:Updates.start` |
| `alarm:plan` | every 30m | | `modules/alarm.py` |
| `alarm:suggest` | every 30m | `alarm.suggest` | `modules/alarm.py` |
| `alarm:up_ask` | every 5m | `alarm.skip_if_up`, `alarm.sleep_aware` | `modules/alarm.py` |
| `backups:run`, `backups:catchup` | daily 03:30; hourly | `backups.when` | `modules/backups.py` |
| `books:read` | daily 01:00 | `books.at` | `modules/books.py` |
| `calendar:refresh` | every 15m | `calendar.refresh` | `modules/calendar.py` |
| `calls:line_update` | daily 05:10 | | `modules/calls/__init__.py` |
| `capture:plan` | daily 00:10 | | `modules/capture.py` |
| `cases:review` | weekly sun 19:00 | `cases.review` | `modules/cases.py` |
| `checkins:plan` | daily, `checkins.day_starts` + 5 min | `checkins.day_starts` | `modules/checkins.py` |
| `deadlines:tick` | hourly | | `modules/deadlines.py` |
| `doubts:before` | every 5m | | `modules/doubts.py` |
| `exam_season:tick` | every 15m | | `modules/exam_season.py` |
| `gbrain:sync`, `gbrain:nightly`, `gbrain:checkup` | every 15m; daily 03:00; weekly sun 19:30 | `gbrain.sync`, `gbrain.nightly`, `gbrain.checkup_when` | `modules/gbrain.py` |
| `dreaming:consolidate` | daily 04:45 | `dreaming.consolidate` | `modules/consolidate.py` |
| `dreaming:fold` | daily 04:50 | `dreaming.fold` | `modules/fold.py` |
| `infer:sweep` (and `infer:first` once) | daily 04:20 | `infer.sweep` | `core/infer.py:start` |
| `google:classroom` | every 3h | `google.classroom_every` | `modules/google.py` |
| `classroom_notes:sync` | daily 07:00,13:00,19:00 | `classroom_notes.at` | `modules/google_classroom.py` |
| `mail_digest:digest` | daily 08:00,18:00 | `mail_digest.at` | `modules/google_mail.py` |
| `drive_upload:expire` | daily 04:10 | | `modules/google_drive.py` |
| `handwritten:scan` | every 15m | `handwritten.every` | `modules/handwritten.py` |
| `learning:index` | every 15m | `learning.search` | `modules/learning.py` |
| `remember:recheck` | daily 18:30 | `remember.recheck_days` | `modules/remember.py:Remember.start` |
| `integrate:night`, `integrate:retry`, `integrate:plan`, `integrate:garden`, `integrate:summary` | daily 01:30; every 3h; hourly; daily 06:20; daily 07:10 | `integrate.at`, `integrate.garden`, `integrate.summary` | `modules/integrate.py` |
| `local_models:keepalive` | every 10m | | `modules/local_models.py` |
| `notes_sync:sync` | every 10m | `notes_sync.every` | `modules/notes_sync.py` |
| `profile:daily` | daily 04:40 | `profile.when` | `modules/profile.py` |
| `quests:daily` | daily 18:00, respect quiet | `quests.when` | `modules/quests.py` |
| `quiz:offers`, `quiz:exam_daily`, `quiz:links` | hourly; `daily <quiz.exam_daily>` if set; `quiz.links_at` if `quiz.links` is on | `quiz.exam_daily`, `quiz.links` | `modules/quiz.py`, `modules/quiz_links.py` |
| `research:papers`, `research:logs`, `research:idle` | weekly mon 08:00; daily 23:30; daily 18:00 (quiet) | `research.papers`, `research.log_when`, `research.idle_when` | `modules/research.py` |
| `research:repo_refresh` | daily 04:20 (heavy: waits for the charger) | `repo_projects.refresh_at`, `repo_projects.refresh` | `modules/research.py` → `core/repoproject.py:refresh` |
| `research:zotero_links` | daily 04:40 | `research.zotero_links`, `research.zotero` | `modules/research.py` → `modules/zotero.py:link_notes` (a thread) |
| `retro:nightly` | daily 23:50 | `retro.when` | `modules/retro.py` |
| `skills:autopack`, `skills:routine:<id>` | every 30m; the user's `/every` spec | | `modules/skills.py` |
| `space:clean` | weekly sun 04:30 | `space.when` | `modules/space.py` |
| `startby:morning` | daily 08:00 (quiet) | `startby.when` | `modules/startby.py` |
| `study:write` | `daily <study.daily_note>` (23:45) | `study.daily_note` | `modules/study.py` |
| `subjects:term_note` | every 10m | | `modules/subjects.py` |
| `weekly:summary` | weekly sun 19:00 | `weekly.when` | `modules/weekly.py` |

One-offs (`at`), by key: `reminders:<id>` (`reminders.fire`, registered in `Reminders.__init__` so try-it reminders
fire even before the feature is on), `alarm:ring` / `alarm:prep` / `alarm:awake`, `calls:ring:<key>`,
`calls:missed:<since>`, `calls:realert:<first>`, `calls:task:<job>`, `calls:textcall:<cid>`, `checkins:<name>`,
`checkins:unstick:<name>`, `checkins:deferred`, `capture:<subject>:<end>`, `calendar:focus:<end>`,
`calendar:remind:*`, `google_calendar:refresh`, `quiz:checkin:<ts>`, `quiz:links:later` (a link card held by a class or focus),
`exam_season:leave:<id>`,
`exam_season:night_again`, `health:after:<id>`, `health:recheck`, `integrate:soon`, `integrate:early` (the night's
start moved earlier for an early wake, set by `integrate:plan`), `notes_sync:soon` (debounced after
`job_done`), `profile:soon` (debounced after setting changes), `research:remind:<slug>`, `retro:after-reset`,
`study:session-end`, `study:timer`, `telegram:focus-end`, `books:now`, `books:resume`, `updates:apply`,
`updates:probation`, `updates:rolled_back`, `upgrade:whats_new`, `addons:official_offer` (2 minutes after a start
that brought a newer official add-on you have: `core/official.py`). Profile restore re-books saved `reminders:`,
`calls:ring:` and `alarm:ring` jobs (`core/profile.py`).

Every scheduled action takes the job's payload (`tests/unit/test_scheduled_actions.py` checks it).

## Jobs

`core/jobs.py:Jobs`, SQLite `<state>/jobs.db`. The only way a feature should run a full AI request.

```python
jid = app.jobs.submit(
    prompt,
    title=None,
    effort="auto",  # "low" | "medium" | "high" | "auto"
    reply_to=None,
    quiet=False,  # quiet: no answer is sent (the then-action handles it)
    then=None,
    then_payload=None,  # a follow-up registered in app.jobs.then_actions
    background=False,
    text_only=False,  # background: waits for the charger and for kept free limits
    why=None,  # a Calm reason for an answer that comes by itself
    lane=None,
    brain=None,  # lane "you" | "bg" | "chk"; pin to a brain id
    offline=False,  # the internet is down and the caller said it waits (Chat): it waits from now
    images=None,  # pictures to look at (paths), kept as the `images` column (JSON); Task.images
)
```

- Status: `queued` → `running` → `ok` | `failed`. Verdicts are `providers.base.Verdict`.
- **Claim order (0.7.3):** within a lane a job with a reply target (something you typed) is claimed before one
  without (`order by (reply_to is null), created`), and a check-in's journal and study-log jobs run in "bg", so an
  evening check-in can't hold up a request you type right after it.
- **Lanes** (`LANES = ("you", "bg", "chk")`): one job at a time per lane, so the user's own request never waits
  behind background work. Unset, `background=True` goes to `bg`, everything else to `you`. `chk` is a second
  background lane so two agent programs can work at once (the concept graph's check role, call reviews).
- **Worker** (`Jobs.worker`, an asyncio task): `recover()` first (jobs left `running` by a dead process, identified by
  `runner` = pid plus start time, go back to `queued`), then every 5 s or on `poke()`: `watchdog()`, and for each free
  lane `_claim()` the oldest ready job and run it in a thread (`_start`). Nothing runs while paused; background jobs
  only run in `normal` power mode (`_READY`). (0.9.0) `Jobs.boosts` (name -> `fn(info) -> bool`, `info`: id, lane, why,
  title; `boosted()`, a boost that raises counts as no) reorders `_claim`'s ready rows: a reply target first as before,
  then boosted ones, each group oldest first. Exam season registers `boosts["exam_season"]` (`jobs_priority`).
- **Effort**: a fixed `low`/`medium`/`high`, or `providers/effort.py:pick` (see [brains.md](brains.md#effort)).
  Timeout per level: `brain.timeout_min`. (0.9.0) A boosted job whose effort was picked goes one step up
  (`_step_up`: low -> medium -> high, `job_effort_up`), unless `Quota.wait_until(pool(brain, up))` says that limit is
  kept or used up; a forced or asked-for effort is never changed.
- **Retries** are the fallback chain, not repeats: each brain in `[main, fallback, last resort]` (rearranged by
  `Quota.arrange`) is tried once; `RETRY` verdicts move on. There's no automatic re-run of a failed job; features that
  need one (the concept graph) count tries themselves.
- **Deferral**: background work whose free limits are kept for the user goes back to `queued` with `not_before`
  (`_defer`, event `job_deferred`); `resume()` clears it when a limit answers again.
- **Waiting for the internet** (0.6.0, `_hold`): with `app.helper.holds()` (the internet down and
  `local_helper.offline` on), `_run` keeps only brains on this computer (`Helper.here`: `OpenAICompat.local()`); with
  none, the job goes back to `queued` with `held` (when it first waited) and `held_until` (now + `RETRY_S`, 120 s),
  event `job_held`. A job that waited already tries its brain at its next look unless `Helper.sure()`
  (`egress.net_down()`): its own request is the check, so a Telegram-only outage never holds AI requests for long. A try
  that failed with `error`/`timeout` while `Helper.lost(tried)` (the internet down, or `egress.failed_since` the try
  began) waits the same way. The first hold of a `you`-lane, non-quiet job tells the user (`Helper.waiting_line`, why
  `asked`); Chat says it itself and submits with `offline=True`. `_READY` also needs `held_until` past. `unhold()` (from
  `Helper.back`) clears `held_until` and returns the user's titles; a held job's answer gets "(It waited for the
  internet connection from 14:02.)" as its `note`. Past `local_helper.hold_h` it ends `timeout` with a `GAVE_UP` detail,
  which `_deliver` shows as is. `held()` counts them; `/jobs` says "for the internet connection".
- **Watchdog** (`watchdog()`): a running job of this process with no AI process and no sign of life
  (`_mark` updates `activity`) for `jobs.stuck_min` minutes ends `stuck`; one past its deadline (time limit plus the
  brain's `grace_s` plus `GRACE_S = 120`) ends `timeout`. Ending kills the process tree (`proc.kill_tree`).
- **Cancel**: `cancel(jid)`, `cancel_text("all")`, `/jobs`, `POST /api/jobs/cancel`, `kurooto jobs --cancel`.
- **Delivery** (`_deliver`, unless `quiet`): `[<brain label> · <effort>] <title>` (0.8.17: left out when
  `jobs.header` is off and the request succeeded) then the answer, through
  `app.notify(kind="result", why=job.why or "asked", reply_to=...)`. Answers over `LONG = 7000` chars are also sent as
  a file (`jobs/<id>-result.md`). Cases adds a Wrong button when on.
- **Run receipt** (0.5.15): `_run` builds one line from the run's own record before the request's tool log is dropped
  (`Jobs._receipt` → `receipt()`), and keeps it in the `receipt` column: the AI (`NAMES`), effort, time since it
  started (fallback tries included), the share of today's limit when `Quota.status(pool)["pct"]` knows the limit, and
  what it did from `Jobs.steps` (`_did`: each tool in `ACTS` becomes a phrase like "wrote 2 notes", the rest "used N
  other tools"; none is "did nothing", or "did nothing through Kurooto" for an agent program, whose own tools Kurooto
  doesn't see). At most `RECEIPT_MAX = 120` characters. `Jobs.receipt(jid)` gives it while `jobs.receipt` is on:
  `_deliver` adds it as the message's last line and passes it as `Message.tail`, which the Telegram sender
  (`TelegramAPI.send(tail=)`) marks italic with a message entity (UTF-16 offsets, no parse mode, so the answer needs
  no escaping); other channels show it as plain text. `GET /api/job` (`web/tools_api.py:job`) appends it to `answer`
  and returns it as `receipt`, so the terminal chat, `kurooto ask` and the dashboard show it too. Quiet requests are
  never delivered, so they get none. Tests run with it off (`tests/conftest.py:no_receipts`);
  `tests/unit/test_receipt.py` turns it on. When the request was told remembered items (below), the line ends
  "· used N remembered items" (`receipt(..., recalled=)`; it stays when the line is shortened).
- **Plan line** (0.6.0, `jobs.plan_line`): in `_run`, after `quota.arrange` and before the first brain runs,
  `Jobs.plan_line(job, chain[0], level, recalled)` sends one line (`kind="info"`, `why="asked"`, `reply_to` the
  request) when the job is lane `you`, not quiet, not background, the user isn't on a call
  (`availability.on_call_until()`), and `Jobs.expected(brain, level)` (the median `seconds` of the last 9 ok lane-`you`
  jobs on that brain and effort, None under `PLAN_SAMPLES` = 3) is over `PLAN_S` = 20. The words come from the prompt
  before the run (after "Current request:"): "Opening the file you sent" (Chat's "Files they sent with it"), "Reading
  the link" (`URL`), "Searching your notes" (`NOTES_CUE`), "going over N remembered items"; else "Thinking it through";
  then "then answering (about <_took> with <SHORT or label>)." Calls' requests are quiet, so they never get one. Event
  `job_plan_line`. Tests: `tests/unit/test_plan_line.py`.
- **Memory in the context** (0.5.18): `_run` calls `core/assembler.py:for_request(app, job)` before building the
  `Task` and passes the block as `headless_context(app, extra)`; the count goes into `Jobs.recalled[jid]` for the
  receipt and is dropped with the tool log. Only lane `you`; never raises (`recall_failed`).
- **Chat history** (0.5.8): after delivery, the answer is recorded into Chat's history only if
  `chat.owns(job.id)` (`modules/chat.py:Chat.owns`, the set of job ids `Chat.ask` submitted). Digests, research,
  call reviews and skills therefore never become "the conversation".
- **Tool log** (0.5.8): `Jobs.note_step(jid, name, args)` records each tool use of a request running in this process
  in `Jobs.steps[jid]` (at most `MAX_STEPS`). API brains reach it through `Task.run_tool` (`run_tool(..., job=jid)`);
  agent programs through `kurooto mcp`, which sends the request's id from the `KUROOTO_JOB` variable
  (`core/mcp.py:ENV_JOB`, put into `Task.mcp_env` by `_run`) as `job` in `POST /api/tools/call`. When a brain's
  `Result.usage` has no `tool_calls`, the log's count is used, so `attempts.tool_calls` and `/usage` count agy and
  Claude Code too. The log is dropped when the request ends.
- **Turn options** (0.8.16, Voice): `with app.jobs.turn_options(brain=, text_only=, effort=, on_text=, on_start=) as
  got:` around `app.handle(msg)`: the first `submit()` on that thread takes `brain`, `text_only` and `effort` (only in
  place of `"auto"`; a typed prefix still wins) and puts `got["jid"]`; `on_text`/`on_start` go to `Jobs.hooks[jid]`
  (memory, dropped in `_run_safe`). `_run` calls `on_start(brain.id)` before each try and sets `task.on_text` per try
  (`_streamer`: the key is `("<i>:<brain>", message key)`, so a stand-in's answer is a new message). A hook that
  raises never costs the request.
- **Watchers** (0.5.8): `app.jobs.watchers` holds `fn(job, result, info)` called by `_after` for every finished request,
  after delivery and the then-action, success or not, with `info = {"steps", "then", "payload"}`; a failure emits
  `job_watcher_failed`. Learns from its own work (`modules/learning.py`) is the one user. `finished_since(t)` lists
  requests that ended well after `t` (its search index).
- **Then-actions**: `app.jobs.then_actions[name] = fn(job, result, payload)`, run by `_after` after delivery, for
  success and failure alike (check `result.ok`). A name not registered when the job finishes is skipped silently, so
  register then-actions in `__init__` or `start()`, never lazily just before submitting (`modules/google.py` registers
  `google.draft` lazily and loses drafts across a restart). Exceptions become `job_then_failed`.
  `result.usage["limits"]` lists every usage limit hit on the way (`{"brain", "retry_after_s", "detail"}`), also one a
  stand-in then answered for; the concept graph's reading budget reads it (`core/readbudget.py`).
- **Shutdown**: `halt()` stops running jobs where they are; they stay `running` and `recover()` re-queues them at the
  next start.
- `usage(days)` (from `attempts`) feeds `/usage`; `public(job)` is what the dashboard and CLI may show (no prompt, no
  answer).

## Events

`core/events.py`: `Events(state).emit(kind, **fields) -> dict` appends `{"ts": iso, "kind": kind, ...}` to
`<state>/events.jsonl` (a field named `kind` is stored as `subkind`), then calls every `subscribe(cb)` listener in this
process. `tail(n, kinds=None)` reads backwards from the end a block at a time (`lines_back`, `Events.lines()`), so its
cost is what it reads, not the log's size. Writes are serialised by a thread lock only; CLI processes append to the
same file but their events never reach the daemon's listeners. Like the logs it's trimmed: past `MAX_BYTES` (10 MB)
`emit` moves it to `events.jsonl.1` (replacing the one before) and starts a new one; `tail`, `Events.lines()` and
`health.Latest` read on into `.1`. Readers that keep a byte offset (presence, quests, `Latest`) start again from the
top when the file is smaller than their offset.

Consumers: the dashboard feed (`web/live.py`, `EVENT_CELL` prefix → cell), `/api/events`, the diagnostics bundle,
the nightly look back (`modules/retro.py:evidence`), the weekly summary (`modules/weekly.py`), health
(`core/health.py:Latest`, by byte offset), presence, quests, and subscribers in notes sync, profile, Telegram, the
terminals and cases.

Event kinds that something reads (not just the feed):

| Kind | Read by |
|---|---|
| `setting_changed`, `module_enabled`, `module_disabled` | profile auto-save, Telegram rename, terminal sync, health |
| `job_done` | notes sync (push after AI work), weekly (AI requests answered and failed, by its `ok`), retro |
| `message_in`, `intent` | weekly, retro, cases (`intent`) |
| `message_in`, `button_tapped` (emitted by `App.callback`, prefix only), `call_answered`, `alarm_up_now` | `core/rhythm.py` (when you're around, absence) |
| `question_asked`, `question_answered`, `question_later`, `question_expired` | retro |
| `classroom_synced`, `notes_synced`, `calendar_synced`, `backup_done`, `profile_save`, `gbrain_sync`, `calls_link`, `calls_line_updated`, `power_mode` | health checks (`core/health_checks.py`) |
| `reminder_set`, `reminder_fired`, `checkin_*`, `deadline_added`, `deadline_done`, `deadline_told`, `quiz_graded`, `quiz_session`, `doubt_added`, `study_session_start`, `remembered`, `skill_run` | weekly, quests, presence |

Other kinds, by area (shown in the feed and counted by retro): lifecycle `started`, `stopped`, `module_failed`,
`commands_failed`, `upgraded`, `brain_retired`, `claude_account_added`, `claude_account_removed`; jobs `job_queued`, `job_crashed`, `job_deferred`, `job_cancelled`,
`job_ended`, `job_then_failed`, `jobs_failed`, `tool_used`, `tool_failed`, `tools_failed`, `note_written`,
`quota_limit`, `quota_back`, `quota_reserve`, `agy_tools`; messages `notified`, `notify_queued`, `notify_failed`,
`notify_delayed`, `calm_*`, `rhythm_*`, `keep_asked`, `keep_answer`, `keep_failed`, `presence_online`, `presence_offline`, `question_hook_failed`, `question_hook_missing`;
power `power_pause`, `power_resume`, `power_off`; health `health_checked`, `health_fixed`, `health_told`,
`health_failed`, `fixme`; updates `update_found`, `update_waiting`, `update_held`, `update_yanked`, `update_check_failed`,
`update_failed`, `update_progress`, `update_switch`; Telegram `telegram_error`, `telegram_paired`, `telegram_menu_*`;
calls `call_scheduled`, `call_rang`, `call_rang_offline`, `call_answered`, `call_missed`, `call_held`,
`call_transcript`, `call_reviewed`, `call_review_failed`, `call_live_failed`, `call_fallback`, `calls_*`; concept graph
`book_read`, `integrate_batch`, `integrate_refused`, `integrate_waiting`, `integrate_limit`, `integrate_pruned`,
`integrate_moved`, `hubs_updated`; and one family per feature (`alarm_*`, `deadline_*`, `exam_*`, `study_*`, `quiz_*`, `skill_*`,
`retro_*`, `learning_*`, `google_*`, `mail_*`, `classroom_notes_*`, ...). Grep `events.emit("` to find the emitter of any kind.

When you add an event: name it `<area>_<what happened>` in the past tense, keep fields to ids, counts and short error
text (never message content, notes or secrets: the bundle and the feed show them), and if a health check should
depend on it, list it in that check's `events` in `core/health_checks.py`.

## Notify and Calm

`core/notify.py:Notifier`; `app.notify(text, **kw)` is the one way to tell the user something.

- (0.9.0) `respect_phone_dnd`: `release()` also queues to `focus-queue.jsonl` when `_phone_dnd(msg)` (the switch,
  not `asked`/a reply, not `calm.exempt(...)`, `mind/senses/phone.dnd_on`). `flush_dnd()` (focus not running, DND off)
  is called from `phone.ingest` and `Calm.tick`.
- `Message` fields: `text`, `title`, `buttons` (`[[("label", "prefix:ref:action" | {"url": ...}), ...]]`), `kind`
  (`info` | `result` | `reminder` | `question` | `approval` | `deadline` | `call` | `update`), `urgent`, `reply_to`,
  `map_kind` / `map_ref` (so a reply or button finds its handler: `Module.replies()[map_kind]`), `file`, `tail` (the
  text's own last line to show quietly: the run receipt, italic on Telegram), and the Calm envelope `why`, `setting`,
  `about`, `item`, `due`, and (0.9.0) `ws_item`, the same item as Brain's workspace names it (`deadline:<id>`,
  `class:<subject>`, `quiz:<deadline id>`; see mind.md), kept apart from `item` so Less of this keeps reading the bare id.
- `send()`: Calm decides first (`Calm.decide`: `send`, `hold`, `stop` or `folded`), then `release()`: during focus, non-urgent messages that aren't
  `approval`/`call` go to `focus-queue.jsonl` (flushed by `flush_queue()` when focus ends); otherwise `_deliver()`:
  Telegram (unless presence holds it because the network is down), the phone app for `notify.app_kinds`, the app's
  chat (`chat`) for the rest when `notify.app_chat` is on or `App.app_main()` (Telegram off, Phone calls on: Calm's
  `extra` rows come along then), the desktop (`core/desktop.py`) for `notify.desktop_kinds` or when no other channel
  delivered. A `reply_to` of `"app:<id>"` goes to the chat only. Emits `notified`.
- Telegram is optional (0.5.18). `app.py:met(need, on, m)` is the requirement check `App.enable`, `App.disable`,
  `core/turnon.py` and `core/profile.py` use: `"telegram"` in a module's `requires` means somewhere to talk, met by
  Telegram or by `calls` (the phone app's chat) unless the module sets `telegram_only` (Voice notes, Files into notes).
  `App.need_title` words it ("Telegram or the phone app (Phone calls)"). `App.basics()` hands Telegram's own commands
  and intents (`/pause`, `/resume`, `/status`, `/hold`, `/calls`, `/focus`) to `App.handle` and `App.help` when
  `app_main()`; `App.start` registers `telegram.focus_end` itself, so `/focus` ends without Telegram.
  `core/presence.py:Presence.channels` uses `app` in place of `telegram` then. Files: `Message.file` to the chat
  becomes a link (`modules/calls/chat.py:PhoneChat.send_file`, see calls-and-phone.md); `Jobs._deliver` sends a long
  answer's file with the same `reply_to` as its text.
- (0.9.0) Presence routing in `_deliver` / `_desktop`: `at_desk()` (Face presence's `desk_seen_at()` within `DESK_S`
  = 120 s; False when it can't tell) and the app's `away_from_desk()`. `notify.follow_me`: away, `_follow()` sends the
  app a copy unless the kind is in `app_kinds`; the `face.away.hold_desktop` hold stays. `notify.desk_silent_phone`
  sets `Message.silent` (Telegram's `disable_notification`, `telegram._send`) at the desk, never for urgent, `call` or
  `approval`. `notify.desk_first` adds any kind to the desktop at the desk. `notify.guests_hold`: `guests_here()`
  (`nearby.facing_many`: two faces close and facing in a frame of the last 10 s, or `biometric.voice_others`) shows
  `GENERIC` instead of the text; emits `notify_generic`. Voice's `speak.guests_private` asks `guests_here()` too and
  keeps the answer in memory for the `vrd:0:read` button. `notify.desktop_retract`: `desktop.notify()` leaves the
  pop-up's id in `desktop.last_id` (`show()`: Linux `notify-send --print-id`, falling back to the plain call); `Notifier.shown` keeps the last 50 as
  (map_kind, map_ref, button data, id); `retract()` ends with `_desktop_retract`, which `desktop.close()`s matching
  ones (`gdbus ... CloseNotification`) and drops matching Face holds (`Face.drop_held`; held entries now carry that
  key as a fourth item). Emits `notify_retracted` (`channel=desktop`).
- Channels are registered by modules: `notifier.register("telegram", send, retract=None, edit=None)`. `retract(map_kind,
  map_ref, button)` takes a question down from channels that keep copies (the phone app) once it's dealt with anywhere.
  `edit(ref, msg)` changes a Telegram message in place (Telegram registers `_edit`, which uses `TelegramAPI.edit(...,
  strict=True)`); False when there's no editor or Telegram refused, so the caller can send a new message instead.
- Button data is `"<prefix>:<ref>:<action>"`; `App.callback` routes core prefixes (`calm`, `upd`, `ask`, `health`,
  `fixme`, `job`, `inf`, `ton`, `keep`, `fgt`, `rhy`) and then each enabled module's `callbacks()[prefix]`. Keep a module's prefixes unique and short (Telegram
  limits callback data to 64 bytes).

`core/calm.py:Calm`:

- Every message that comes by itself carries `why=<reason id>`. Reasons are declared in `REASONS` (built with `R(id,
  what, setting=..., stop=..., fewer=..., later=..., exempt=..., suggest=..., feature=...)`). A message with
  `why="asked"` (`ASKED`) is an answer to the user and is never held, counted or buttoned; a message with no `why` is
  sent and recorded as "No reason recorded".
- Exempt (`EXEMPT`): `own` (reminders the user set), `alarm`, `approval`, `deadline` (due within `DEADLINE_H = 12`),
  `urgent`, `security`, `bundle`, `limit` (the once-a-day line below).
- The daily limit: `notify.calm.messages` (6) and `notify.calm.calls` (1, `Calm.call_ok`). Past it, messages are held
  for the evening bundle at `notify.calm.evening_at` (20:00, sent by `calm:tick`). Per-kind user choices: `stopped`,
  `evening`, `fewer`. Exam season tightens it (`modules/exam_season.py:budget_during_exams`). `Calm.day_limit()`
  is the messages limit after `Rhythm.lighter_limit` (half on a lighter day); `_wait` holds with `"quiet"` during a
  quiet week (`Rhythm.quiet_week`), like `"exams"`, past the evening too. Two per-kind rules
  Dreaming tunes (`core/policy.py`): `habituate` (kind → N: `Calm.ignored(why, t)`, the `streak()` of answerable
  records left unanswered, at least `IGNORED_H = 3` hours old, reaching N holds it as `held="habit"`) and `windows`
  (kind → `"HH:MM-HH:MM"`, `inside()`; outside it `held="window"`). Both are checked in `Calm._wait` after `fewer`.
- (0.9.1, `notify.calm.night_bedside`, off) With bedside mode open on the phone (`PhoneChat.bedside()`) at the
  bundle's time, `tick` keeps `bundle_held` in its state and bundles once it closes (`calls/chat.py:_bedside` calls
  `tick()`).
- The first `held="budget"` of a day calls `Calm._tell_limit`: one exempt message (`why="calm.limit"`, not counted;
  `calm.json` `limit_told` keeps it to once a day; skipped when the limit is 0) with buttons
  `calm:<YYYY-MM-DD>:flow|raise|fine` (`Calm._limit_button`). `flow` sets `calm.json` `flow_day` (`Calm.flowing()`:
  `_wait` skips the budget check today) and `Calm.release()` sends today's budget holds in order through
  `Notifier.release` (focus still applies; settled questions are dropped as in the bundle). `raise` applies a `Change`
  doubling `notify.calm.messages` (Undo as usual) and `release(cap=day_limit())`. Other holds never bring the line.
- `Reason.counted=False` (`updates.done`): never held by the daily limit, recorded with `budgeted=0`.
  `Reason.fold=True` (`updates.done`): `Calm._fold` adds "(and N earlier today)" and, when an earlier one today has a
  Telegram ref, edits that message (`Notifier.edit`) and returns `folded` (nothing new sent); otherwise the new text
  goes out as a new message. Chosen over deleting the earlier ones: one call, no notification, and nothing to do for
  channels without edit (the phone app's chat gets the new message with the note when there's no Telegram; with
  Telegram it keeps the first notice only).
- The bundle's head counts holds by `held` (`BUNDLED`): "N messages that waited, held by the daily limit of 6", or
  "(3 held by the daily limit of 6; 1 because ...)" when mixed. `Calm.today()` adds `waiting_limit` and `flowing`.
- On Telegram a counted message gets "Why?" and "Less of this" (`calm:<rid>:why|less`); `Less of this` offers Stop /
  Fewer / Another time, each changing one setting (`Change`), with Undo. `/calm` and `/why` show the state.
- Records: `calm.db` table `sent` (45 days; `Calm.forget` blanks `text` and `title` after `privacy.keep_days`).
  `notify.calm.on = false` turns all of it off.
- (0.9.0) The recheck: `calm.still(app, msg)` says what changed about a held message's item (from `ws_item`, or a
  `deadline` map_ref): `done HH:MM`, `marked not yours`, `dropped`, `moved to <Ddd HH:MM>` (its `due` differs),
  `quiz over`, `class skipped` (`subjects.skipped()`). `calm.recheck(app, msg)` applies `notify.calm.recheck`:
  `rewrite` appends "(Since then: ...)" once (`STILL_MARK`), `drop` returns None, false returns it unchanged. Called
  where held messages are let out: `Calm.release`, `Calm.bundle` (a dropped one is `settled`), `Notifier.flush_queue`,
  `Presence.flush_outbox`, `mind/sleep.release`, `mind/workspace._let_out` (through `Notifier._recheck`, which never
  raises). Emits `calm_rechecked` (`what`: rewritten | dropped). The door's own `_relevant` drop of a passed due time is
  unchanged.
- (0.9.0, `notify.calm.talk`) `Calm.intent(plain)` → `(name, reply, buttons)`: `TALK_WHY` (why_last), `TALK_LESS`
  (`less_of()`: the last record's options), `TALK_HELD` (`send_held()`: the bundle now), `TALK_COUNT` (`/calm`), and
  `TALK_STOP` / `TALK_FEWER` with a kind `kind_named()` resolves (exact `plural`/`what`, or a multi-word part of one;
  ambiguous or unknown: None, so the words go on). `App.handle` asks it after every module's intents, so a feature's
  own "stop ..." wins. `Calm.call_tools()` (added in `Calls.tools`, so Live gets them): `why_that_message`,
  `less_of_these` (kind, action: stop | fewer | later; the Undo goes to the chat), `send_waiting_messages`,
  `messages_today`. Every change goes through `Calm.apply`, so it has Undo.

(0.9.0) Add-ons: `calm.register_reason(rid, what, setting="", counted=False, exempt="", rules="", **Reason fields)` adds
a reason (`<add-on>.<what>`, lower case; a built-in id raises ValueError; registering again replaces the add-on's own;
`unregister_reason` takes it back). `Reason.rules` names a setting: while it's off, `Calm.rules_apply(r)` is False, so
`_decide` and `speak_ok` skip `_wait` (no evening, Fewer, window, habit, exam or limit holds) and `options()` offers Stop
only; the stopped list applies always. The add-on then passes `why=` (and calls `speak_ok` before speaking), and its
messages get Why? and Less of this.

To add a message that comes by itself: pick a reason id `<module>.<what>`, add an `R(...)` to `REASONS` with the
setting that controls it (so Less of this can change it), and pass `why=` (plus `about=`/`item=` when it concerns
one thing) to `app.notify`. A message without a reason still works but can't be turned down.

## Ask: questions and approvals

`core/ask.py:Ask` (`app.ask`). Any feature, background job or script can ask the user and act on the answer.

```python
qid = app.ask.ask(
    "Which chapter is the quiz on?",
    choices=["3", "4"],
    hook="study.quiz_topic",
    hook_payload={...},
    expires="2d",
    source="study",
    why="study.quiz",
)
app.ask.hooks["study.quiz_topic"] = lambda q, answer: "noted"  # register in __init__/start
app.ask.approval("Send this draft?", hook="mail.send")  # Approve / Deny
```

- Delivered to Telegram (choices as buttons plus Later), the desktop, the phone app and the next call
  (`call_brief`, `call_tools`). First answer wins. `Later` keeps it for the next call; "Nothing new" is an answer.
- Each question is `<state>/ask/<id>.json`; unanswered ones expire after `ask.expire_hours` (48) (`sweep`, every 10 min,
  `ask:sweep`); settled ones are kept `retention.days(settings, "ask")`: `ask.keep_days` when set, else
  `privacy.keep_days` when set, else 30 (`retention.TIDY`). `Ask.forget(lo, hi)` drops those settled in a stretch.
- Hooks run once with the first answer; a hook not registered at that moment emits `question_hook_missing` and the
  answer is kept. Built-in hook `ask.ai` starts an AI job from `hook_payload["prompt"]` with `{answer}` filled in.
- Tools: `ask_user` for unattended AI (`agent_tools`), plus call tools to answer questions by voice.
- CLI: `kurooto ask-me`, `kurooto ask-approval` (exit 0 approved, 1 denied, 2 timeout or not running) go through the
  local API.

## Availability

`core/availability.py:Availability` (`app.availability`): when Kurooto may interrupt.

- `quiet_until()` / `set_quiet()` (`quiet.json`, "no calls until"), `focus_until()` / `set_focus()` (`focus.json`
  plus `focus:*` blockers; non-urgent messages wait), `on_call_until()` / `set_on_call()` (`oncall.json`, kept ahead by
  Phone calls during a call), `night(t)` (`availability.night`: fixed hours, or from bedtime to the alarm when the alarm
  provides `sleep` windows; `alarm_only`).
- `blockers[name] = fn(t) -> (reason, until) | None`: modules add their own (classes from Subjects, calendar events,
  exams). Names starting `focus:` count as focus.
- `call_block(t) -> (reason, until)` checks on-call, quiet, focus, night, then blockers. `next_callable(t)` follows
  chained blocks. `quiet_gate` / `call_gate` are the scheduler gates.
- Settings: `availability.night`, `nocall_keyword` (`#nocall`), `nocall_calendar`, `focus_keyword` (`#focus`);
  `learn_night`, `learn_morning`, `absence_days` belong to `core/rhythm.py`, which may move `availability.night`.
- (0.9.0) `Availability.app` (set by `App.__init__`) lets it read Brain and the phone's senses. `night(t, brain=True)`
  starts with `_brain_asleep` (`checkins.asleep_follows_brain`: `mind/sleep.state() == "asleep"` until its window's
  end, reason `BRAIN_ASLEEP`), and `_phone_end` (`availability.night.phone_alarm`: `mind/senses/phone.next_alarm` inside
  the night ends it earlier; once rung, no night) applies to both the alarm's windows and the fixed hours.
  `call_block(t, why=None, due=None)` / `next_callable(..., why, due)`: `own_call(why, due)` (`OWN_WHY`: calls.own,
  alarm.ring, reminders.own; or a due time under 12 h) skips the brain night and `soft_block(t)`: `calls.phone_busy`
  (`phone_busy_until()` / `set_phone_busy()`, `phone-busy.json`, fed by `calls/chat.py:_busy` from the app's
  `{"busy": {"until": ms}}`, at most 3 h; apart from `oncall.json`), `notify.respect_phone_dnd` (`phone.dnd_on`),
  `calls.hold_moving` (`phone.moving`), each rechecked after 10 minutes. `Calls._held_call` passes the call's why/due;
  callers without them (retries, `call_gate`) get the soft holds. Phone readings older than 15 minutes
  (`phone.FRESH_S`) say nothing. Voice's `listen.phone_call` makes `blocked()` say "you're on a phone call".
  Alarm: `Alarm.phone_mismatch()` (on the `suggest` job) asks once per pair (`alarm-phone.json`) with
  `alm:phone:keep` / `alm:<YYYYmmddHHMM>:set`; reason `alarm.phone_mismatch`.

## Power

`core/power.py:Power` (`app.power`), mode recomputed every 30 s (`Power.watch`):

- `normal`; `saver` (on battery with `power.on_battery = "saver"`, the default): modules with `heavy = True` and
  background jobs wait, local models rest (`Module.rest()`); `paused` (`/pause`, `kurooto pause`, or
  `on_battery = "pause"`): nothing runs except Telegram, which queues messages (`telegram/paused.jsonl`) and replays
  them on resume.
- `may_run(module)`, `hold(job)` / `release()` for the scheduler, `pause(minutes)`, `resume()`, `off(keep_calls)`
  (`off.json`: no autostart until `kurooto on`).
- `App.start_background` doesn't start a module's background task while `may_run` is false; `Power.apply` starts or
  stops them as the mode changes.

## Presence

`core/presence.py:Presence`: "going offline" (`going_offline()`, at most `BYE_S = 2.5` s, called by `daemon.serve`
before stopping; Windows sign-out through `core/endsession.py`) and "back online" (after sleep, detected as a clock jump
between `TICK_S` ticks; after network outages). Messages that couldn't reach Telegram wait in `net-outbox.jsonl`
(`hold`, `failed`, `flush_outbox`). `offline(start, end)` gives the offline periods health subtracts. Settings
`notify.presence.*`. The call line reports outages the computer can't (`line_report`).

## The offline helper (`core/helper.py`)

`Helper` (`app.helper`), 0.6.0: a small model on the processor through Ollama (`ollama_models.toml` `cpu-helper`,
`qwen2.5:1.5b-instruct`, about 1 GB; or `local_helper.model`) for quick decisions, and the queue's behaviour while the
internet is down.

- **The model**: talked to through `LocalModels.api("/api/generate")` (`_generate`, temperature 0, a few tokens,
  `keep_alive` 30 min). `ready()`: `local_helper.on`, a passed speed test for this tag in `local-helper.json`, and the
  tag in `LocalModels.have()` (believed for `HAVE_S`). (0.9.3, a fix) `tick()` calls `maybe_retest()`: on, but the test
  on file is for another tag (`local_helper.model` changed, or the table's model replaced the tested one) and the tag in
  use is here: `speed_test()` again on a thread of its own (`retest` in the state file: at most once per `RETEST_S`
  per tag), event `helper_retest {ok, seconds}`; it never changes `local_helper.on`. Voice's `judge_state()` says in
  /voice and doctor when the helper is on but can't be used. `word(prompt, choices)` is the one decision call, capped at
  `local_helper.timeout_s` (4 s); anything not among the choices is None (the rules decide). Event `helper_decided`.
- **Decisions**: `classifier()` for `providers/effort.py` (`Jobs._classifier` uses it where the rules would decide
  alone: `brain.classify = rules`, the chosen classifier's limit kept with no local brain, or the internet down);
  `pick(text, rows)` among `core/repair.py:readings` at `NEAR` (0.6) or closer, top three, by number, run with
  `repair.run(..., via="helper")` in `App.handle` before `repair.offer`; `yes_no(question, reply)` for replies of six
  words or fewer (`modules/remember.py:_reply`, yes / no / other).
- **Setting up** (`setup`, one at a time): `room()` (core/prereqs.py `room`, Ollama too when missing), Ollama installed
  and served (`LocalModels.serve`), `LocalModels.pull(tag, size, progress, feature="Offline helper")` (handed to
  Ollama), then `speed_test()`: a warm-up (`WARM_S`), `TESTS` timed one-word answers (`self.timer`), the median
  against `local_helper.max_s`. Failed: `local_helper.on` stays off and a model pulled just now is removed
  (`LocalModels.remove`). `/helper on`, `/helper test` and the offer's Install run in a thread and report through
  `notify(why="asked")`.
- **Offline**: `offline()` is `egress.net_down()`, or `presence.net_down()` with no answer through `egress` since
  its failures began (`egress.answered_since`: then it's Telegram or the call line, not the internet); `sure()` is
  `egress.net_down()` alone; `holds()` adds `local_helper.offline`.
  `offline_reply(text)` (Chat, before submitting; not with files or a conversation in the last 2 h): with the internet
  down and the helper ready, a question up to `QUICK_CHARS` that `effort.pick` (with the helper) calls `low` is
  answered by the model (`ANSWER`; "CANNOT" means no), with a closing line naming the offline helper. Otherwise Chat
  submits with `offline=True` and says `waiting_line()`. The queue side is in [Jobs](#jobs).
- **`tick()`** (`local_helper:tick`, every minute): `down_since` set when the internet goes (`helper_offline`); when
  it's back, the outage (`OUTAGE_MIN_S` or longer) is kept in `outages` (30 days), `back()` calls `Jobs.unhold()` and
  says once what's running now (why `asked`); every 10 minutes, Ollama is started if the helper is on and it isn't
  running.
- **The offer** (`local_helper:offer`, daily 12:30, quiet respected; Calm reason `local_helper.offer`): `why_offer()`
  needs `local_helper.offer`, the helper off, `setup.done`, fewer than `OFFERS` (2) offers and none in `AGAIN_D` (30)
  days, `OFFER_AFTER_D` (14) days since the earliest of its own `since` and Keep's, `eligible()` (no `helper*` model
  in `LocalModels.wanted()`, `MIN_RAM_GB`), `room()` ok, and either `TIGHT_DAYS` (3) days with `quota_reserve` /
  `quota_limit` events in the last 14 (`tight_days`, from the event log) or `OUTAGES` (3) outages. Buttons
  `lh:<ref>:install` / `lh:<ref>:later` (`App.callback` → `button`). Events `helper_offered`, `helper_offer_answered`.
- `/helper` (core command): `status()`, `on`, `off`, `test`.
- State `local-helper.json`: `since`, `test` {ok, model, at, seconds}, `down_since`, `outages`, `offer` {count, at,
  why, ref}. Tests: `tests/unit/test_helper.py` (a fake `_generate` and fake `LocalModels` methods; no Ollama, no
  download).

## Quota (free AI limits)

`core/quota.py:Quota` (`app.quota`): counts requests per pool (`pool_id`: `gemini:<model>` per model, `agy`, a
brain id; local models have none), learns limits from 429 answers (`hints`), knows Google's day ends at midnight
Pacific. Once a day's count passes `quota.background_pct` (70%) of a known limit, background work waits
(`wait_until`, `arrange`); `used_up` pools go last for the user's own requests; `line()` is the one plain sentence when a
limit is used up. Settings `quota.on`, `background_pct`, `limits` (user numbers win), `local` (`quick` |
`background` | `off`). State `quota.json` holds counts only.

Quota thinks in daily limits (Google's). Subscription plans (Claude's rolling 5-hour window and weekly cap, shared
with the user's own chats) aren't modelled here; the concept graph's nightly reading, the one big background consumer,
has its own budget that learns them: `core/readbudget.py`, see
[concept-graph.md](concept-graph.md#reading-budget-corereadbudgetpy).

## The reserve

`core/reserve.py`: Markdown copies an AI program can read instead of running commands: `alarm.md`, `deadlines.md`,
`calendar.md`, `today.md` (0.9.0, `reserve.today`: `today_md`, the alarm, `classes_on(include_skipped)`, deadlines due
today or tomorrow, today's events; titles past `remember.sensitive` only; no clock time, so it changes once a day or
when they do; listed in `guide_md` while on), `settings.md` (non-default settings, never secrets), `addons.md`,
`agent-guide.md`, in
`<state>/reserve/`. Rewritten every 10 minutes (`reserve:refresh`), on change, and by `kurooto reserve`; a file is only
written when its text changed (`write_if_changed`). Kurooto never reads them back. `<state>/reserve` is in
`places.read_roots`, and the headless context points the AI at it.

## Going through what waits, aloud (0.9.0)

`core/walkthrough.py` (`voice.answers_questions`): `Face._greet` calls `offered(app)` when the greeting ended with
"Want to go through them?" and opened the conversation. `App.handle` gives every voice turn to `take(app, msg,
plain)` first: within `OFFER_S` (120 s) a `YES` from the owner (speaker "" or "owner") starts it (`ask.pending`
questions, approvals only counted; not while `biometric.others_present`); each next owner turn answers the current one
(`ask.answer(..., "voice")`), `SKIP` leaves it, `STOP` ends it; `IDLE_S` (300 s) lapses it. In memory only (`_state`
by app). Interest's (the Body add-on's) own spoken questions aren't wired to it here.

## The Memory page (0.9.0)

`core/memorypage.py:view(app)` (`GET /api/memory`, `look.memory_page`): the ledger (`counts` by `NAMES`, the newest
`ROWS` rows with `label`), `threads.open_threads`, `infer` items not undone, `learning.changes()`,
`notinterested.ignored_topics`, `mind/console.model` (with `edit`), and `COUNTERS`: `register_counter(name, fn(app) ->
{title, count, what})` for an add-on's own store (counts only). `home.js:renderMemory` draws it (page `memory`, Alt+U;
Alt+M stays Study mode); the model's Wrong/Forget post to `brain/console` (L90), and an `offer` asks with `confirm()`
before `unline`. Everything else is read-only here: each store's command keeps its Undo.

## Space keeper

`core/space.py`: `plan(app) -> [Item]` lists Kurooto's own leftovers (old backup zips beyond `backups.keep` /
`space.backups_max_gb` / `space.backups_max_age_days`, never the newest; cache files older than `space.cache_days`;
log files over `space.log_mb`; finished jobs older than `space.jobs_days`, and search-index items (`modules/learning.py`) as old; concept-graph
`pending/` and `undo/` older
than `space.undo_days`; diagnostics zips; extra program versions). `clean(app, items)` removes them. Run by the Space
keeper feature (`space:clean`, `space.when`), `/space`, `kurooto space [--clean]`; `kurooto doctor` only reports.
`low_disk(app)` feeds health. `footprint(app)` lists the search index of past requests apart from the rest of the
state folder. Never touches notes, books or user folders except Kurooto's own zips there.

## Retention and /forget

`core/retention.py`: what's kept of conversations goes after `privacy.keep_days` (default 0: kept; `TIDY` keeps the
old 30-day tidy-up of settled questions and cases). Kinds, each a function
over a stretch `[lo, hi)` in epoch seconds (`STEPS`):

| Kind | What | How |
|---|---|---|
| `calls` | `calls/transcripts/*.txt` (time from the file name, else mtime), finished `calls/textcalls.json` conversations, `calls/searches.json` rows | removed |
| `requests` | finished jobs; `jobs/*-result.md` by mtime | `Jobs.forget`: `title='(forgotten)'`, `prompt=''`, `result`/`detail`/`then_payload` null; the row and `attempts` stay for `/usage` and the Space keeper |
| `chats` | `chat/history.json` turns by `at` | removed |
| `questions` | settled `ask/` files | `Ask.forget` |
| `cases` | non-test cases by `at` | `cases.Store.forget` |
| `messages` | `calm.db` rows not held | `Calm.forget` blanks `text`, `title` |
| `index` | `learning/history.db` docs by `at` | `learning.forget` (`History.forget`; `prune` calls it) |
| `threads` | `ledger.db` rows of kind `thread` by when they opened | `threads.forget` (`Ledger.drop`) |
| `logs` | every file in the logs folder | `trim_log`: lines by their `asctime`, continuation lines follow the stamped line; no stamps: by mtime. Rewritten in place (the handler keeps appending); emptied rotated copies are removed |

- `forget(app, lo, hi=END, kinds, gist=True, settle=False)` runs each kind under its own try (`retention_failed`,
  `what=<kind>`) and returns `{kind: n}`; `summary()` words it. Before `calls`, `requests` and `chats` it calls
  `gists.keep(app, kind, lo, hi)` (below); with `settle` (the daily job) a kind whose gists raised keeps its words
  until next time (`gist_failed`). `days(settings, section)` resolves `ask.keep_days` / `cases.keep_days` (0 means
  follow `privacy.keep_days`); `cases.Cases._keep_days` and the `kurooto cases` CLI use it too.
- `expire(app)` is `retention:expire` (daily 04:15, `misfire="coalesce"`, run in a thread): `forget(0, now -
  keep_days, settle=True)` for every kind, questions and cases with their own days, then `gists.expire`. Emits
  `retention_expired` (counts only). Sends nothing, so it has no Calm reason.
- `/forget` is a core command (`App.handle` → `command`): `7d`, `2w`, `12h` (`span`) forget `[now - span, END)` at
  once (`retention_forgot`); `all` replies with `fgt:<asked>:all` (keep the gists) / `fgt:<asked>:gists` (`gists.clear`
  too; only offered while gists are on or exist) / `fgt:0:no` buttons (`App.callback` → `button`); they work for
  `CONFIRM_S` (10 min), then answer in the toast and with a `why="asked"` message.
- Left alone on purpose: the notes folder (voice-note recordings are saved in its inbox), `events.jsonl` (metadata
  only; features learn from it over weeks), open questions and text calls, test cases, the Worker's queue (handed
  over and emptied at every `hello`, `data/worker/src/worker.js`). `Jobs.finished_since` skips forgotten rows so the
  search index doesn't take them back.

## Egress: every request on the internet

`core/egress.py`. **New code never calls `urllib.request.urlopen` (or another HTTP client) for an internet address;
it calls `egress.urlopen(req, "<feature>", timeout=..., own=...)`**, which takes the same `Request` or URL, returns the
same answer (wrapped to count the bytes read; use it as a context manager) and raises the same errors.

- `_check`: `127.0.0.1`, `localhost`, `::1` pass without a count (nothing leaves); `privacy.egress` `off` passes
  everything. Otherwise the host is on the list when it's in `HOSTS` (exact, or `.domain` for every host under it) or
  in `privacy.allow_hosts`, or the call site says `own=True`: an address the user gave (the iCal link, a Research feed,
  the custom AI service's `base_url`, the call line and its ntfy server, the AI's `fetch` tool, whose pages are chosen
  for the user's request). In `enforce`, a host that's none of those raises `Blocked`, an `urllib.error.URLError`
  whose text names the host and `privacy.allow_hosts`, so existing `except OSError` / `URLError` handling copes.
  `record` (the default) counts it with `unlisted`. A request whose innermost owner is an add-on by link
  (`core/fence.py:owner`) is checked against its card instead, in every mode: an undeclared host raises `Fenced` (a
  `Blocked`).
- `urlopen` counts `len(req.data)` out and what's read in, once, when the answer is closed (`_Counted`); a request that
  raised (an `HTTPError` too) is counted with what went out. `urllib.request.urlopen` is looked up at call time, so
  tests that put a fake there still work. Redirects are followed by urllib and aren't checked again.
- `allow(url, feature, own)`: the same check for a connection made another way (`calls/connector.py`'s websocket),
  counted once per connection, no bytes.
- `handed(program, feature)`: a subprocess that goes online by itself, counted as "handed to <program>" and not looked
  into: `providers/agy.py:Agy.run`, `providers/claude.py:ClaudeCode.run`, git's `GIT_ONLINE` steps in
  `modules/notes_sync.py:NotesSync.git` (not for a local `remote`) and `core/profile.py`, `calls/deploy.py`
  (`_wrangler`, `npm ci`), `local_models.py` (a pull through Ollama), `gbrain.py:GBrain.run` (`ONLINE` steps when the
  index uses Gemini or the brain is the user's own), `skills.py` (Tectonic), `core/prereqs.py:Prereqs.install`
  (`HANDED` kinds).
- The ledger: `<state>/egress.json`, `{"days": {"YYYY-MM-DD": {"<host>|<feature>" or ">program|<feature>": {host, via,
  feature, n, out, in, blocked, unlisted}}}}`, the last `DAYS` (30) days, at most `MAX_ROWS` rows a day (then
  `other`). `record` takes a thread lock and the `egress` file lock (2 s; on timeout the count is dropped) and never
  raises. `attach(app)` (in `App.__init__`) points it at the running app's state folder and settings; before that
  (a bare CLI command, the launcher) nothing is counted and only `HOSTS` applies.
- **Is the internet down?** (0.6.0) `urlopen` also tells `seen(host, err)` each outcome, in memory only (`_net`, reset
  by `attach`): an answer (an `HTTPError` too) clears the failures; a failure to reach the host (`URLError`, `OSError`,
  timeouts; not `Blocked`) is added. `net_down()`: failures to `NET_HOSTS` (2) hosts or more, the last within
  `NET_FRESH_S` (600 s), with no answer since. `failed_since(t)`: a failure after `t` with no answer after it.
  Loopback never counts. `core/helper.py` reads both; nothing is pinged for them.
- `/egress` is a core command (`App.handle` → `command`): `week()` sums the last `SHOWN` (7) days per row, blocked
  first, then by count.
- `HOSTS` and `docs/PRIVACY.md`'s "Where requests go" table must list the same hosts
  (`tests/unit/test_egress.py:test_the_privacy_page_lists_the_same_hosts`). A new built-in host goes into both, with
  the feature that reaches it.
- Not routed, on purpose: requests to this computer (`top.py`, `cli.py`, `core/mcp.py`, `core/rerank.py`,
  `modules/local_models.py:LocalModels.api`, `modules/google_confidential.py`: Ollama and Kurooto's own page). Add-ons'
  own code is counted only when it uses `egress.urlopen`.

### Gists (consolidation)

`core/gists.py`: words fade, meaning settles. `keep(app, kind, lo, hi)` makes one line per item `MAKERS[kind]` finds
in the stretch, by rules from records, and keeps it in the memory ledger as rows of kind `gist` (sub = call, request,
chat; under `Lock(state, "gists")`; `load()`/`_save()` read and replace them all, `_move()` brings a 0.5.17
`gists.jsonl` in once; an item already gisted by `(kind, at)` is skipped, so a retry never doubles). While the
ledger's key can't be read, `load()` is empty and `_save()` raises `ledger.Locked` before changing anything, so the
daily job keeps the words:

- `calls`: `call_line()` from `<transcript>.did.json`, which `Calls.save_transcript` writes with `note_call(f,
  purpose, tool_log)`: acting tools (`core/jobs.py:ACTS`, verbs not in `READS`) with their result, read-only and
  unknown tools by name only, failures as "<tool> failed". Without it (older calls): the `calls_tool` names in the
  event log since the call before (at most 2 h back). `drop_did` removes the side file with its transcript.
- `requests`: `Jobs.ending(lo, hi)` (lane `you`, not yet forgotten): title · outcome (`OUTCOME` by verdict) · receipt.
- `chats`: the turn's first 80 characters (Chat's request title), skipped when a request or chat gist has that name.
- Every line goes through `_safe` (`modules/remember.py:sensitive`): health, money, credentials keep only the kind.
- `local_model()`/`local_line()`: only with `privacy.gist_model` and Local AI models on and a `helper*` model pulled
  (`LocalModels.wanted`/`have`), one sentence from `/api/generate` is appended to a call's line; never a cloud AI.
- `expire()` drops gists older than `privacy.gist_days` (0, the default: never); `clear()` for `/forget all` → Gists
  too; `command()` is `/gists` (core command in `App.handle`): newest first, numbered; words filter (all must match);
  `forget N`. Events: `gists_kept`, `gists_expired`, `gist_forgotten`, `gist_failed` (counts and kinds only).
- `MAKERS` also feed `ledger.live()`: the same lines for what's still kept in full, made on demand and never stored
  (`_calls(..., local=False)`: never a model).

## Memory: the ledger, threads and the assembler

Three pieces (0.5.18), all rules, no AI.

**The ledger** (`core/ledger.py`). One SQLite store, `state/ledger.db`, opened lazily per app (`of(app)`, closed by
`App.close`). Kinds (`NAMES`): `gist`, `thread` (only here), `fact`, `day`, `meeting` (`NOTES`: read from notes), and
(0.9.0, `memory.day_rows`, off) `dayrow`: `day_row(app, day)` from events only (`face_back`→`face_left` spans, rounded to
the hour and said from 1 h; `study_logged`/`study_session_end` minutes by subject; `class_skip`/`class_attend` from your
taps), written by `memory:nightly` for yesterday at noon (`write_day_row`, replacing that day's), shown by `day_story`.

- Crypto: `Ledger.key()` is a 32-byte key in `app.secrets` as `ledger.key` (base64), made under
  `Lock(state, "ledger-key")` on first use. With rows present and no key it raises `Locked` (never a new key over old
  rows: a keychain still locked at boot). `seal(kind, payload)` = 12-byte nonce + `AESGCM.encrypt(json, aad =
  "kurooto-ledger:<kind>")`; `unseal` returns None on `InvalidTag` (counted in `ledger_unreadable`). `mac(*parts)` is
  HMAC-SHA256 under a key derived from it (`src` = a note's path, `h` = a note row's identity, `forgot` = forgotten
  note rows). Plain on disk: kind, sub (a thread's state), at, upd, those hashes.
- Search decrypts into memory: no token index, so equal words in two rows can't be told apart on disk. `words()` is
  the shared tokenizer (3+ letters, `STOP` removed, "'s" stripped), used by threads and the assembler too.
- `refresh(force)` (throttled to `REFRESH_S`, forced by `/memory` and the plain-English answers) walks
  `note_sources()`: the how-to-help-me note (`_facts`: `remember.kept_lines`), daily notes matched by the layout's
  `daily` template (`_day`: headings, then lines, sensitive lines dropped, `DAY_MAX`; `DAYS_BACK` = 730), project notes
  (`_meetings`: `- YYYY-MM-DD: ...` under `## Meetings`, with the `With:` people, `infer.WITH_LINE`). A note whose
  mtime changed has its rows replaced in one transaction; a note that's gone takes its rows; rows whose `h` is in
  `forgot` are skipped.
- `everything(app, live_days, fresh)`: all rows plus `live()` gists. `label()`, `said()`, `when_text()` word where a
  row is from ("call at 07:56 today", "open thread, said on the call at 07:56 today").
- Plain English (`intent()`, from `App.handle` before the modules' intents): `LAST_TALK` → `last_talk()` (rows naming
  the last name, newest first, two before); `DOING` + `a_past_day()` (yesterday, today, N days ago, last/on
  <weekday> = the latest before today, 20 Oct, Oct 20, ISO) → `day_story()`.
- `/memory` (`command`): newest first and numbered; words filter; `forget N` (`forget()`: a `fact` also
  `remember.remove_line`; a note row is tombstoned in `forgot`); `export` (`export()`: gists and threads into
  `layout.path("note", slug="memory-<stamp>")`, `create=True`).
- Backups skip `ledger.db*` unless `backups.memory` (`modules/backups.py:LEDGER`); the profile never carries it or its
  key. Events: `ledger_key_made`, `ledger_locked`, `ledger_unreadable`, `ledger_read_failed`, `ledger_live_failed`,
  `memory_forgotten`, `memory_exported` (counts and kinds only).

**Threads** (`core/threads.py`). Rows of kind `thread`, sub `open` | `done` | `dropped` | `expired`; payload `text`,
`via` (chat, call, study, deadline), `key` (a started task's: `study:<slug>`, `deadline:<id>`), `due`, `closed_at`.

(0.9.1) `due_by(app, edge, n)`: open threads with a due time before `edge`, soonest first, each with `due_dt` (the
greeting's `threads` part, `agent_plan.thread_slot`).

**One read of the chat's turns** (0.9.1, L94, `core/nightread.py`, `memory.night_read`, on). `turns(app)` parses
`chat/history.json` once per (mtime, size) and hands the same list to `core/infer.recent_text` (via `said_since`),
`modules/fold.said` and `modules/learning.History._chats`; each keeps its own marks, schedule and output.
`nightread.reads` counts parses and shared reads. Off: each reads the file, as before.

- Open: `observe(app, text, via)` (called by `App.handle` after `infer.observe`, and by `from_call()` from
  `Calls.save_transcript` with the user's lines) matches `INTENT` per sentence, skips questions, "remind me", `NOT_TASK`
  and `remember.sensitive`; the same words already open are touched instead. `started(app, text, key, via)` from
  `Study.start_session` and `Deadlines.progress` (0 < done < total); `finish(app, key)` from `stop_session` and
  `Deadlines._after_status` (done, ignored).
- Close: a sentence matching `DONE` that shares at least two words (or all of a short thread's) with exactly one open
  thread (`_closes`); `/threads done|drop N`; buttons `thr:<id>:done|drop|undo|show` (`button`, routed in
  `App.callback`); `expire()` nightly after `memory.thread_days` without a touch (`upd`).
- "That thing" (`intent`): `THING` plus `ASK` / `WHAT` / `THING_DONE`; `resolve()` = threads with `max(at, upd)` in
  the last `RECENT_S` (48 h), plus `_requests()` (lane `you` jobs) for "did *you*", narrowed to the best word overlap.
  One: `_answer` (read only; buttons only change the thread); several: one reply with a button each
  (`thr:<id|job>:show`, or `:done` for "that thing is done"). Nothing outside the thread is ever changed.
- `forget(app, lo, hi)` is retention's `threads` kind. Events `thread_opened`, `thread_closed`, `thread_reopened`,
  `threads_failed`. `closed_between(app, lo, hi, how="done")` gives the threads closed in a time range (the evening
  check-in's reflection).

**The assembler** (`core/assembler.py`), the memory budget.

- `build(app, text) -> (block, n)`: nothing unless `memory.recall`; the persona card first (settings `persona.card`, a
  string or a dict, when another feature set one), then `pick()`'s lines under `HEAD`, then `GUARD` when the message
  says "that/this ... thing" (`THAT`): one open thread is named with the rule that it's only read or asked about;
  several: ask which. Everything within `budget()` = `memory.budget_tokens` × `CHARS_PER_TOKEN` (4); a line that
  doesn't fit is skipped for a shorter one. `n` counts remembered items only (not the card).
- `pick(app, text, call)`: open threads when the message shares two words with one, or one with a past cue (`PAST`),
  or says "that thing"; with a cue, ledger rows of kind gist, meeting, day from the last `LOOK_DAYS` (60) plus
  `live()` gists of the last `LIVE_DAYS` (3) that share a word or fall on the day named. Score: 3 × shared words + 2
  × subject words (`Subjects.find_in`) + 2 × the day named + recency. `ITEM_MAX` 240 characters each.
- `for_request(app, job)` (core/jobs.py): lane `you` only, the text after "Current request:" (Chat's history isn't
  what was asked now). `call_brief(app)` (`Calls.pending`): `open_threads` and `earlier` (gists of the last day),
  within the same budget.

## Hardware profiles

`core/hardware.py`: `detect()` reads OS, CPU, memory, GPUs (`nvidia-smi`, Windows/macOS/Linux probes), disk and
battery; `current(app)` caches the machine in `hardware.json` and recomputes the recommendation each time.
`profile(m)`: `light` (under 8 GB or no usable GPU), `apple-8` / `apple` (Apple Silicon, 16 GB+), `small-gpu`
(NVIDIA 4-8 GB), `big-gpu` (8 GB+), `big-gpu-12` (12 GB+). `recommend()` picks Ollama models from
`data/ollama_models.toml` (e.g. `helper-*` models, embeddings) and says plainly what an override goes past (`limits`).
Settings `hardware.force_profile`, `extra_models`, `extra_prereqs`; `kurooto hardware --profile P --add MODEL
--install`. Used by Local AI models, the reranker and the dashboard. The table's `cpu-helper` row is in no profile:
the offline helper (`core/helper.py`) offers it on computers whose profile has no `helper-*` model.

## Running programs

- `core/proc.py:run(args, *, input=None, timeout=60, cwd=None, env=None, on_start=None) -> Result(code, out, err)`:
  long text goes through stdin, npm `.cmd` shims run through node directly (`resolve_cmd_shim`), UTF-8 decoding, no
  console window on Windows (`CREATE_NO_WINDOW`), a new session on POSIX, and the whole process tree killed on timeout
  (`kill_tree`). `which(name, extra_dirs)` also looks in user install folders; `ensure_user_path()` adds
  `~/.local/bin`, `~/.cargo/bin` and Homebrew to a short boot-time PATH. Use these instead of `subprocess` directly.
- `core/children.py`: at shutdown `stop_all()` stops every process Kurooto started (SIGTERM, then a kill after
  `GRACE_S = 5`), found as descendants and by session (`session(pid)` for PTY programs). Programs opened for the user on
  purpose are excluded with `keep(pid)` (`core/opener.py`, Kurooto Terminal).
- `core/opener.py`: opening a note in the user's editor and links in the browser, detached.

## Locks and atomic writes

- `core/state.py:jsave(path, obj, mode=0o600)`: temp file then `os.replace`; on Windows the rename is retried 10 times on
  `PermissionError` (antivirus, indexer). `jload(path, default)` returns a copy of the default for a missing or broken
  file. `owner_only(db)` sets 0600 on a database and its `-wal`/`-shm`.
- `core/tools.py:write_note_file(f, text, create=False)`: the safe way to write a note (atomic, keeps CRLF, `create=True`
  never overwrites). Several older writers still use `write_text` (the deadline tick in `modules/deadlines.py`,
  `modules/remember.py`, `core/hubs.py`, parts of skills, retro, books); prefer `write_note_file` for anything in the
  notes.
- `core/lock.py:Lock(state, name, timeout=-1)`: a `filelock.FileLock` at `<state>/locks/<name>.lock`, shared by the
  daemon and CLI processes. `timeout=0` fails at once (`Timeout`). Names in use include `daemon` (single instance),
  `backups`, `gbrain` (shared by backups and gbrain), `notes-sync`, `profile`, `ask`, `deadlines`, `calendar`,
  `exam_season`, `startby`, `study`, `books`, `handwritten`, `cases`, `google-token`, `telegram-map`,
  `telegram-paused`, `calls-*`, `lidsafe*`, `classroom-notes*`, `mail-digest*`, `skills-routines`, `skills-packs`,
  `ollama-pull`. Use a lock for any state file the CLI and the daemon may both write.

## Windows notes

- Paths: `%LOCALAPPDATA%\Kurooto` (not Roaming); the program in `%LOCALAPPDATA%\Programs\Kurooto`. Documents and
  Downloads come from `SHGetKnownFolderPath` (OneDrive may have moved them; `core/places.py:_known_folder`).
- Renames fail transiently while a scanner holds a file: always go through `jsave` / `write_note_file`.
- Always pass `encoding="utf-8"` to text I/O; the default is a code page.
- No console windows: `CREATE_NO_WINDOW` for helpers (`core/proc.py`, `daemon.supervise`), `DETACHED_PROCESS |
  CREATE_NEW_PROCESS_GROUP` for programs that outlive the call (`cli.py:start_background`, `core/opener.py`). `pythonw.exe`
  has no stdio: `core/mcp.py:_console` and `modules/terminal/plan.py` switch to `python.exe`.
- Command lines are limited to about 32 000 characters and `cmd.exe` mangles `" & ^ %`: prompts go through stdin or a
  file (`providers/agy.py:handover`, `ARG_LIMIT`; Claude Code's context file).
- npm programs are `.cmd` shims: `proc.resolve_cmd_shim`.
- PTYs: ConPTY through `pywinpty` (`providers/agy.py:run_pty`, `modules/terminals.py:WinPty`), `ptyprocess` elsewhere.
- No signals: `loop.add_signal_handler` isn't available, so Ctrl+C arrives as `KeyboardInterrupt`
  (`daemon.run`); sign-out and shutdown come through `core/endsession.py`.
- File modes don't apply (`jsave` skips `chmod` on `nt`); secrets rely on the profile's ACLs or the Credential Manager.
- The registry is used for autostart (`core/autostart.py`), PATH (`core/pathfix.py`) and the uninstall entry
  (`cli.py:install_finish`).

## Smaller core pieces

| File | What it is |
|---|---|
| `core/aboutyou.py` | "About you": imports what other AI accounts know into `about-me/profile.md`; `AboutYou.brief()` for the headless context |
| `core/actions.py` | the Today page and Ctrl+K actions ([web.md](web.md#the-today-page-and-actions-coreactionspy)) |
| `core/agent_export.py` | skills as slash commands in agent programs (`agents.export`) |
| `core/autostart.py` | start at sign-in or boot, per OS; `refresh()` brings old installs' entries up to date |
| `core/clock.py` | `now()` (local, naive), `parse_when()` for typed times |
| `core/commands.py` | the command table and `/help`: `CORE`, `GROUPS`, `help()`, `find()` ([modules.md](modules.md#help-and-the-command-table-corecommandspy)) |
| `core/conceptgraph.py`, `core/graphwrite.py`, `core/graphmerge.py`, `core/integrate_ai.py`, `core/segment.py`, `core/rerank.py`, `core/hubs.py`, `core/pdfread.py` | the concept graph ([concept-graph.md](concept-graph.md)) |
| `core/desktop.py` | desktop notifications; text passed as arguments or environment, never pasted into script source |
| `core/endsession.py` | Windows sign-out and shutdown messages |
| `core/health.py`, `core/health_checks.py` | "Kurooto keeps itself working" ([debugging.md](debugging.md#health-kurooto-keeps-itself-working-corehealthpy-corehealth_checkspy)) |
| `core/fixme.py` | `/fixme`: failing checks matched by rules to the troubleshooting page and known issues ([debugging.md](debugging.md#fixme-corefixmepy)) |
| `core/idle.py` | idle time and screen lock per OS (`kurooto idle away|back` for Wayland idle tools) |
| `core/inhibit.py` | keeping the computer awake (Stay awake on charger, the alarm) |
| `core/leave.py` | uninstall (`--revoke`) and `kurooto rotate` |
| `core/mcp.py` | `kurooto mcp` ([brains.md](brains.md#how-agent-programs-get-them-kurooto-mcp)) |
| `core/notinterested.py` | topics the user doesn't care about (`about-me/not-interested.md`); (0.9.0) `notinterested.tell_ai` puts them in `providers/context.py:not_interested_part`, and `demote(app, reader, items, text_of, tagged)` moves a reader's matching items last, tagged "you said not interested in X" (`notinterested.filter.<reader>`, each off: `research.papers`, `integrate.queued_items`, `quiz_links.next_card`, `retro` proposals, `mind/dream.make_cards` and `mind/frontier.score` halved). Never drops an item; the older filters (deadlines, mail, Classroom, curious, start-by, exam season) are unchanged |
| `core/overlay.py` | add-ons: your folder's, and loading the add-ons by link ([modules.md](modules.md#add-ons-coreoverlaypy)) |
| `core/addons.py` | add-ons by link: fetch at a pinned commit, the card, consent, update with what changes, remove and undo ([modules.md](modules.md#add-ons-by-link-coreaddonspy-corefencepy)) |
| `core/official.py` | official add-ons: the shipped list (`data/official_addons.json`), what counts as official, Add / Update buttons (`oad:`), the once-per-commit update offer ([modules.md](modules.md#official-add-ons-coreofficialpy)) |
| `core/fence.py` | the fence around add-ons by link: only the hosts and programs on their card (an audit hook) |
| `core/palette.py`, `core/syscolors.py`, `core/themes.py` | the pages' colour palette, the OS accent colour for the `system` palette, and the named themes ([Colours](#colours-palettes-and-named-themes-corepalettepy-corethemespy)) |
| `core/pathfix.py` | putting `~/.local/bin` on PATH (disabled in tests) |
| `core/persona.py` | the persona card (`persona.call_me/tone/length/avoid`, empty by default; `clean()` drops parts matching `GUARD`: feelings, saying it missed you, a backstory, a relationship; applied on save and on every read), `/persona` (`command`), the dashboard's `persona` API (`view`, `save`); boundaries (`DECIDE` + `AREAS` rules, `keeps()` in `App.handle`, `BOUNDARY_RULE` in the headless context and calls; `persona.boundaries`); register (`register_line()`: `SHORT_WORDS` 12, `LONG_WORDS` 80, voice notes; `persona.register`). Events `persona_saved`, `boundary_kept`. Tests: `tests/unit/test_persona.py` |
| `core/places.py` | the AI's read and write roots ([brains.md](brains.md#read-and-write-allow-lists)) |
| `core/prereqs.py` | installing helper programs from `data/prereqs.toml`, checksum-checked, no admin where possible; `install()` takes a look before (`_look`) and writes the receipt after (`_receipt`), never failing an install over it |
| `core/uninstall.py` | the install receipt (`<app>/installed.json`) and removing from it: `look`/`record_program` (only what an install made; `features` and `owns` in prereqs.toml), `record_model` (`LocalModels.pull`, only a model Ollama didn't have), `things`/`things_for` (prunes what's gone; `users` = what uses it now: `brain.classify` = ollama counts only while Local AI models is on, since its setup sets it and the classifier falls back to the rules), `remove` (models through Ollama's API, packages through their manager, paths re-checked with `safe()`), the offer (`after_off` from `App.disable` and `/helper off`, `after_hardware`/`after_setting` (only Local AI models' own models, only while it's on) from the settings API and `kurooto hardware`; an approval with hook `uninstall.offer`, guarded `install.remove`), `/installed` and `uni:` (Remove… asks). CLI: `kurooto installed`, `kurooto remove`, `kurooto uninstall` (`uninstall_receipt`). Settings `uninstall.offer`, `uninstall.with_programs`. Event `uninstalled`. Tests: `tests/unit/test_uninstall.py` |
| `core/profile.py` | Profile sync: the encrypted profile and restore |
| `core/shortcuts.py` | the app-menu "Kurooto" entry |
| `core/sources.py` | the book / Classroom / own-notes mix for note-writing skills |
| `core/tap.py` | never without a tap: `GUARDED`, `WAYS`, `ask_first()` and `approved()` for guarded tools; `BY_ITSELF`, the data fixes the look back makes with Undo ([modules.md](modules.md#never-without-a-tap-coretappy)) |
| `core/coursepdf.py` | `/notes pdf <course>` (answered in `App.handle` before the modules' `/notes`, so it works without the notes brain; listed in `CORE` while Subjects is on) and the Study pane's `notes.pdf` action: `notes_for()` (the course page, `DATED` lecture notes by name, and wiki-linked notes in the concept folder or the course folder, up to `MAX_LINKED`), `document()` fills `data/latex/course-notes.tex` (or the user's `course-notes-template.tex` beside the study pack prompt, when it has `%%BODY%%`) with `md_to_tex()` per note (frontmatter and Kurooto blocks dropped; maths passed through, or as `\texttt` with `safe=True`), `build()` (a thread) writes `out_path()` (the `pack` file kind; a `.tex` not starting with `MARK` is never overwritten), compiles with `skills.compile_tex`, retries once with `safe=True`, and sends with `skills.send_file`; no engine: the `.tex` and Skills' Tectonic offer (`skt:` buttons) |
| `core/studyflow.py` | (0.9.0, `study.notes_workflow`) the tools of "study notes from an upload", which the shipped skill `study-notes-from-upload` walks the AI through; added to `core/tools.py:agent_tools()`: `find_uploads()` (walks `upload_roots()`: the handwritten inbox (`_hw_inbox()`, without making it), its originals, the sent-files inbox, `files.folder`, the notes, Downloads; PDFs anywhere, pictures only in the inbox; by mtime and a course's slug, short names and name in the path; says when `handwritten-notes.json` knows the scan's note); `read_handwritten()` (`start_read()` runs `_work()` on a daemon thread per file version (`_READS`), holding the reader's `handwritten` lock, `_transcribe()` as `Handwritten._one` does but at any hour: `read_pdf` page by page with the local model, else `write_out` with `PROMPT + PAGED` through Gemini when `handwritten.cloud` allows; a scan in the inbox also gets its note (`_file`) and is marked seen; the result is kept in `<state>/studyflow/reads/`; the call waits up to `WAIT_S`, notifying "page N of M" every `PROGRESS_S`, else answers how far it got; `from_topic` cuts with N12's `handwritten_overlap.find_topic` when present, else `_find_topic`; `start` pages a long text by `CHUNK`); `build_study_pack()` (`studypack.build(limit=None, topics=)` to `<cache>/study-packs/<subject>-notes-pack.zip`, unpacked beside it, a read root; the answer has PROMPT.md, INDEX.md and a .tex path in `places.work_folder()`, a write root, so the AI's fixes there are never proposals); `save_course_file()` (copies into `layout.file_dir("subject")`, never the notes' top folder; a same-named file Kurooto didn't file is kept (`_free_name`, `<state>/studyflow/filed.json`); a source note `<layout subject folder>/<file stem>.md` with `trust_tier: agent_written`, its `files` block of links rewritten with `graphwrite.put_block` and refused if `guarded()` fails; `copy_to` only into Downloads, Documents or a write root); `study_progress` (one `why="asked"` line); `compile_tool_thin()` only when `n2_present()` is false; `latex_line()` for `providers/context.py:headless_context`; `intent_match()` for Skills' `study_notes` intent |
| `core/latexcheck.py` | (0.9.0, N2b) `check(text, folder)`: braces (`_braces`), `\begin`/`\end` (`_environments`), optional arguments with `[...]` inside (`_optional_args`), commands whose package isn't loaded (`NEEDS`, `packages()` with `LOADS` for what loads what; colour mixes `MIX` and colour keys need xcolor), `\input`/`\include`/`\includegraphics` of missing files, minted; comments and verbatim blanked first (`_strip`). `log_errors()`: pdflatex's `! ...` with its `l.N`, Tectonic's `error: x.tex:N:`, a missing `.sty`. `compile_checked(app, path, dest=None)`: the compile tool's answer (self-check, one `skills.compile_tex` in a copy of the folder, the PDF to `default_dest()`, a file's failed tries counted in `_TRIES` up to `MAX_TRIES`, then "stop and report") |
| `core/studypack.py` | a subject's notes and files as a zip with a prompt for another AI. `note_files()`: the subject's folders, then notes linking to it, except notes under another subject's, book subject's or project's folder (`_other_owners`; 0.6.1). `sources()` merges Books' reads (`book-text/<subject>/*/meta.json`, bookmarks in `chapters`) with Classroom's files and their `<file>.txt` (pages split on form feeds), dropping copies (`same_doc`); `is_class()` tells class material from books by length and title; `citations()` returns `Cite`s (book names or a syllabus abbreviation, kind chapter/section/item/opening, number) from class texts: by name ("Salby Chapter 2"), a syllabus's abbreviation block and code legend (`_abbreviations()`, `_legend()`), its table (a heading row of abbreviations; `_table_row()` puts layout cells under the column starting where they do, plain-text rows in order when they fill every column) and inline "B&D S2.3"; `cited_pages()` matches each abbreviation to one book (`_match()`: surnames in the title, first five letters for a misspelling, the abbreviation's letters as a title word, or two surnames on its first 8 pages; surest first, one book each) and resolves codes with `_Book` (section headings at line starts, skipping contents pages and a chapter opening's list of sections; a section runs to the next later heading not under it, a chapter from "Chapter N" to the next, items by "Definition 1.11" plus a page), giving a `CitedPlan` (pages per book, INDEX.md lines, the cited chapters each cited book's topic pages are limited to); `book_tiers()` ranks a book's pages (cited, then the chapters `choose_chapters()` picks, then hit pages; 0.9.0: `chapters()` from the top-level bookmarks, else "Chapter N" headings, else where each chapter's numbered headings start, each with its heading lines (`_head_lines`: Markdown headings, lines in capitals such as running heads, numbered headings' first words) and cut before back matter; a chapter scores `NAMED` per topic its title names, `HEADED` per other topic a heading in it names, `CITED` when the class cites pages in it, plus mentions per page capped at `MAX_DENSITY`; every chapter with heading or citation evidence scoring at least half the best is taken, the best one's neighbours first, whole when `Chapter.whole`; scattered pages outside the chosen chapters only for topics none of them names (`pattern()` keeps one regex per topic in `_PARTS`, `parts()`); `why=` collects `ChapterChoice.lines()` for INDEX.md's "Chapters taken from the books, and why"; `pattern()`'s `JOIN` lets up to two small words sit between a phrase's words) and `book_share(cap=studypack.cited_pages)` takes cited pages whole up to the cap, past `MAX_PACK_BOOK_PAGES`, then fills the rest of `MAX_PACK_BOOK_PAGES` (0.8.13); an aim with more than `BROAD_TOPICS` topics or `BROAD_AIM` characters (`broad()`) picks book pages by citation only and uses its words to rank class files and notes; `_elsewhere()` keeps another subject's notes (folder, `course:` or tags in the header) out of `note_files()`' topic matches and `brain_notes(subject=)`; `build(limit=None)` (going to Drive) leaves nothing out for size, while with a limit a file over `MAX_FILE` is left out as `OVER_FILE` and one past the zip's limit as `OVER_ZIP` (`sources(any_size=True)`, so INDEX.md names them; 0.8.13); the prompt is `prompt_text()`, from the user's `study_pack_prompt` note when there is one |
| `core/syncall.py` | "sync everything" (`sync_now` on each module that has one) |
| `core/upgrade.py` | one-time steps at the first start of a new version (`upgrades.json`), the "what's new" message |
| `core/vitals.py` | CPU, memory, GPU, network, disk and battery samples for the board and `kurooto top`; processor use comes from the cores' own counters over at least a second (`Sampler._core_use`), the same for every reader in that second (psutil.cpu_percent measured since whichever caller asked last) |
| `core/zones.py` | old and new names of the same time zone |

## Turn on from chat (`core/turnon.py`)

At the end of `App.handle`'s instant requests, `turnon.offer(app, msg, plain, mods, asks)` asks every module that's
off for an intent whose `match` takes the text (errors are skipped, `turnon_skipped`). Not ready (`Module.ready()`):
says where to set it up. Otherwise the text waits in `<state>/turnon.json` (20, for 24 h) under a ref, and the reply
carries `ton:<ref>:on` / `ton:<ref>:no` (routed by `App.callback`). `on` enables the module's `requires`, then the
module, re-matches and runs the intent with an `Incoming` whose replies go out through `app.notify(..., why="asked")`;
`no` hands it to Chat when that's on. Only for `msg.via` in `BUTTONS` (telegram, app): the setup page's try-it box and
terminals go on to the AI. Events `turnon_offered`, `turnon_done`. Setting `turnon.offer`. Tests:
`tests/unit/test_turnon.py`.

## Two readings (`core/repair.py`)

Just before `turnon.offer`, when no enabled intent's `match` took the text, `repair.offer(app, msg, plain, mods,
asks)` scores each learnable intent (`modules/cases.py:learnable`) by its best example phrasing (`examples()`: its
description split at commas, semicolons and "or"; only examples its own `match` takes with no filled slots) against
the text (`difflib.SequenceMatcher` on `cases.norm`). When the top two are `close()` (both ≥ `MIN` 0.75, within
`CLOSE` 0.08), the text waits in `<state>/repair.json` (20, for 24 h) and the reply carries `rpr:<ref>:0`,
`rpr:<ref>:1` and `rpr:<ref>:no` (routed by `App.callback`). A pick runs that intent on its example (`run()`, event
`intent` with `via="repair"`), replying through `app.notify(..., why="asked")`, and calls
`modules/cases.py:Cases.repaired` with Cases on: a `repair` case with `repaired_to`; at `REPHRASE_TIMES` (2) for the
same `norm` text and target it calls `teach()` (the replay gate applies; Calm reason `cases.repaired`, event
`case_repaired`). A test case for the phrasing (`Cases.expected`) runs its reading without asking. `no` hands it to
Chat when on. Only for `msg.via` in `BUTTONS` (telegram, app); a pattern match always runs as before. Setting
`repair.on`. Events `repair_asked`, `repair_neither`. Tests: `tests/unit/test_repair.py`.

## Setting up from what's said (`core/infer.py`)

`infer.observe(app, text, via)` runs on every plain chat message (`App.handle`, before routing; it never consumes the
message) and every `daily.append` body. Rules only: `PROJECT` + `WITH` (first person, no `NOT` words) start a project
via `modules/research.py:ensure_project` and write `With: <who> (<role>)` (in Kurooto's `meeting` block,
`core/meetings.py:set_fields`) and `## Meetings`; `MEET` first tries `RECURRING` (`_recurring`: "I meet my <role>
<Name> every <days> at <time> [about <topic>]", "every <day> at <time> I have a meeting with ...", "a weekly call with
... on <day>s at <time>"; `PERSON` parses the role, title and name), which sets `Meets: every <days> <HH:MM>` (and the
`With:` line, in a new "<topic>" or "Meetings with <who>" project note when nobody's With them and a role or title was
said; undo `note_before` restores the note unless it changed since); otherwise `MEET` with a project person's surname
logs a dated line (and sets `Last met: <date>` in the block; undo puts back the block as it was, `block_before`; old
records with `met`/`met_before` still undo), or a deadline "Meeting: <who>" when `modules/text.py:when_from` finds a time
more than 30 minutes ahead; `brief()` reads `meetings.last_met` (the newest date anywhere), steps under `## Next steps`
(blocks included), `## Meetings` lines outside blocks, and the newest `minutes-<date>` block (`MINUTES`); `CLASS` adds a `subjects.timetable` row for a known subject; `REGULAR` ("every <days> at <time> I go to/have/work
<what>", or the other order; not for class, test or quiz words, which `NOT_REGULAR` leaves to the classes rule and
Deadlines) adds a `commitments.items` row via `modules/commitments.py:Commitments.add`, turning the feature on if it
was off (undo turns it off again when the list is empty); `ALIAS` ("by X I mean <subject>", "X is short for/stands
for <subject>", "I call <subject> X") adds a short name to a `subjects.list` entry (one is made for a subject that's
only in the term note or a class pack), refused for `NOT_ALIAS` words and for any name a subject already has. Since
0.5.20: `TERSE` ("gym Tue Thu 7am": the whole sentence, two days or more, "every" or a plural day, an am/pm or HH:MM
time; `NOT_TERSE` words such as call, wake, remind, due, quiz, and a subject's name, refuse it) and a bare `BARE` kind
with no subject in the sentence ("I have lab every Thursday 2-5") also make commitments, the latter's line saying how
to make it a class; `_quiz` (`QUIZ` words plus `modules/recurring.py:read_rule` with a day, exactly one subject from
`find_in`, and a `next` date when it's every 2+ weeks) calls `Deadlines.add_recurring` (undo: `remove_recurring`),
skipped when the whole chat message is one the `add_recurring` intent takes (`_request`: not `too_complex` and its
matcher matches), so it isn't added twice; after a message's sentences, `_short_names` hands the new ones to
`Subjects.short_names_used` (below) and adds what it returns with `_add_alias` (the `ALIAS` rule's helper). A sentence
that ends in "?" or starts like one (`ASKS`) is skipped before any rule. Each sentence is keyed
(`_key`, sha256 of the normalised text) and looked at once. Changes are kept in `<state>/inferred.json` (`items` with
their `undo` data, `seen`); `undo()` reverses one (a note it made and nobody touched is deleted; otherwise only its own
line goes); `App.callback` routes `inf:<id>:undo`, `/inferred` is in `App.handle` and `core/commands.py:CORE`. Calm reason
`infer.done`. Settings `infer.on`, `projects`, `meetings`, `classes`, `aliases`, `commitments`, `quizzes`,
`short_names`. Tests: `tests/unit/test_infer.py`.

The one pass (`sweep(app, first, tell)`, `infer.sweep`): `start(app)` (from `App.start`, after the ledger) registers
the action `infer.sweep`, the recurring job `infer:sweep` (`SWEEP_WHEN`, daily 04:20) and, while `inferred.json` has
no `swept` time, a one-off `infer:first` three minutes on. `recent_text(app, since)` gives `(via, text)`: your turns
in `<state>/chat/history.json` and each daily note (`layout.path(app, "daily")`) changed since, outside Kurooto's
blocks (`graphwrite.outside`), list markers and headings stripped. The first pass reads `infer.sweep_days` back, later
ones from `swept`. Each text goes through `_observe(..., quiet=True, misses=..., tag=...)` (the same rules and `seen`
keys, now `SEEN` = 5000 kept, so nothing is set up twice; each change gets `pass` = the tag). Misses that are first
person (`FIRST`), hint at something (`HINT`) and aren't negated (`NOT`) go to `_restate()` (`infer.sweep_ai`:
`consolidate._brain`, `SWEEP_AI_MAX` 10, `SWEEP_PROMPT`'s five forms); a restatement passes only if `faithful()` (each
word not in `FORM_WORDS` is in the line, a weekday the line names) and goes through `_observe` again. One
`said_line()` notification with `inf:pass-<tag>:undo` (**Undo all**: `undo()` of each item of that pass); `/inferred
scan` runs it with `tell=False` and answers with the line. Events `infer_swept`, `infer_restated`.
## Projects from repositories (`core/repoproject.py`)

0.7.0. `/project add <target> [as <name>]` and `/project update <name>` (`App.handle` → `modules/projects.py:command`
→ `command` here; the rest of `/project` is [Help with your project's](modules.md)), `kurooto project add` (`cli.project_run`, which
types the command to the running Kurooto through `/api/say`), the Research tab (`POST /api/research/project`), the
setup form's `repo` field and the plain-English `intent()` all end in `start(app, target, name, via)`: `parse()`
checks the target (`GITHUB`: https, bare, `git@` and `ssh://` forms, `/tree/...` ignored; another host is refused;
a local folder must be an absolute, existing path) and `_spawn` runs `add()` in a thread (tests make it inline).
`intent()` (`asked()`: `INTENT` / `INTENT2`, and the target must look like a repository) never fetches: it keeps an
offer and answers with `rpo:<token>:go|no`; `App.callback` routes `rpo` to `button()`. The `repo.attach` guard
allows `typed` and `button` (core/tap.py).

- **Fetch** (`clone()`): git through `core/addons.py:_run_git` (no prompts, no `ext::`/`fd::`, `core.symlinks=false`,
  no submodules; the user's own credential helper and ssh keys), `clone --depth=50 --single-branch --no-checkout
  --filter=blob:none` into `<data>/repos/.staging/<id>`, refused over `CLONE_MAX`; `ls_tree()` lists HEAD's blobs with
  sizes (no links, no gitlinks); `choose()` keeps docs and manifests first, then a PDF (≤ `PDF_MAX`), notebooks
  (≤ `NB_MAX`), other text (≤ `FILE_MAX`), up to `repo_projects.max_mb`, never `secret()` names (`SECRET_NAMES`,
  `SECRET_DIRS`) or `BINARY` extensions; `checkout HEAD --pathspec-from-file` with `:(literal)` paths fetches only
  those blobs. The full tree (secrets left out) goes to `.git/kurooto-tree.json`; the staging folder replaces
  `<data>/repos/<owner>__<repo>` (the old copy is removed after). `remote_url(t)` is the one place the GitHub address
  is made (tests point it at a `file://` bare repository). `egress.handed("git", FEATURE)`. A local folder is read in
  place (`walk()` skips `SKIP_DIRS`, links and secret folders) and never written. Backups leave `<data>/repos` out.
- **Read** (`gather()`): README, docs, manifests (`_deps`: pyproject, package.json, Cargo, requirements,
  environment.yml), licence (`_licence`), CITATION, notebooks' markdown cells, a paper PDF's text (`pdf_text`:
  pdftotext, else `core/pdfread.py`), `git log -n 40` (date, author name, subject), `git tag`, the user's own
  `git config user.name` (left out of collaborators, never sent), and `gh_extras()` when `gh auth status` passes
  (`gh api -X GET` for the repository, open milestones, open issues; `egress.handed("gh", ...)`). Every text goes
  through `redact()` (the secret patterns of `diagnostics.PATTERNS`, PEM blocks, `password = ...` assignments).
- **Understand**: `rules_info()` always (README title and first paragraph, install-section commands, roadmap bullets
  or open issues, languages and dependencies, commit authors, `SUP_RULE` for a supervisor the README names, subjects
  and projects named in the text). With Chat on, one `jobs.submit(prompt(), quiet=True, text_only=True,
  then="repoproject.understood")` (registered in `App.__init__`): `PROMPT` + `material()` (≤ `SEND` characters; the
  material is said to be data). `understood()` → `parse_json` → `validate()` (sizes; a person must be in `rec["seen"]`,
  the README, CITATION and authors; "supervisor" only when `said_supervisor()` finds the word near the name; subjects
  only `subjects.list` slugs or names; projects only existing project notes) → `merge()` over the rules. A failed or
  unusable answer falls back to the rules and says so.
- **Set up** (`finish()`): pieces recorded in `inferred.json` with `record_item()` (`kind` `repo-project`,
  `repo-watch`, `repo-graph`; `undo` = `{"repo": key, "piece": ...}`; `infer.undo` hands them to `undo_piece()`).
  `write_project()`: `research.ensure_project` (+ the hub line), a supervisor via `meetings.set_fields` and
  `infer.add_section("Meetings")`, then `graphwrite.put_block_top(text, "repo", block_body())`; `write_block()`
  rewrites only that block (refused by `graphwrite.guarded` if anything outside would change). `watch()`: the folder
  into `research.repos` and `research.projects`, Research enabled if off (`enabled` kept for Undo). `queue_graph()`:
  see [concept-graph.md](concept-graph.md#sources-beyond-books-0519). `offer_milestones()`: dated milestones not
  offered before → `dateoffers.make(app, "repo", ...)` (deadline source `repository`). One `notify(why="asked")` with
  an Undo row and the date buttons. A piece already active is kept (update mode); an undone one is made again.
- **Refresh** (`refresh()`, from Research's `research:repo_refresh`): for each record whose folder is in
  `research.repos` and whose note exists, `_refresh_one()`: a clone asks `remote_state()` (`git ls-remote origin
  refs/heads/<branch> refs/tags/*`) and is cloned again only on a new commit; README/docs whose text hash changed →
  `rules_info` (keeping the AI's last fields), `write_block`, `queue_graph(only_changed=True)`, and an AI pass in the
  background lane (`mode: refresh`); new tags ("new release") and new milestones go in one Calm message
  (`repo_projects.refresh`).

Settings `repo_projects.on`, `refresh`, `refresh_at`, `max_mb`, `github_extras`. Tests:
`tests/unit/test_repo_projects.py` (a real git repository in tmp, a bare one standing in for GitHub over `file://`,
fake AI answers, gh stubbed).

## Meetings: minutes and action items (`core/meetings.py`)

A meeting is someone a project note is With (`infer.projects_with`) plus a time: the note's `Meets:` line
(`schedule()`, weekly) or an open/done "Meeting: <who>" deadline matched by surname; `on_day(app, day)` lists them,
`recent(app)` the latest that started within `meetings.after_h` hours (36 for the explicit form), `next_after()` the
next one in a note. The note's lines live in Kurooto blocks (`<!-- kurooto:<key> -->`, written with `put()`/`drop()`
via `core/graphwrite.py:block`): `meeting` (`With:`/`Last met:`/`Meets:`, `set_fields()`: made under the last bare
`With:`/`Last met:` lines, else the title; a `With:` outside the block is never edited, `Last met` only moves forward),
`minutes-YYYY-MM-DD` (right under `## Meetings`), `next-steps` (under `## Next steps`, made before `## Meetings` or
`## Log` if missing; existing lines kept as they are, new `- [ ]` items appended).

`take(app, msg, text, window)` is called twice from `App.handle`: after `infer.observe` for `EXPLICIT` (the message
starts "about/notes from ... meeting [with X]" and a colon or dash; `person()` matches surname, first name or role),
and just before Chat with `window=True` (a voice note of 8+ words or a typed one of `MIN_WORDS` 20+, not ending in "?",
within the window). Both need `meetings.minutes` and Chat on. `submit()` queues one quiet, text-only job (`PROMPT`, the
same day's earlier minutes included) with `then="meetings.minutes"` (`App.__init__` registers it) and replies with
**Not about the meeting** (`mtg:<id>:not`). `minutes_written()` parses `Summary:` / `Decisions:` / `Action items:`
(`parse()`; "(by YYYY-MM-DD)" sets an item's due at 17:00, else the next meeting, else a week on), writes the blocks
and `Last met`, keeps the blocks' previous bodies as `undo`, and answers (`why="asked"`, `reply_to` the message: the
phone app's chat when it came from there) with `offer()`: up to `BUTTONS` (4) `mtg:<id>:a<n>` buttons plus `none` and
`later`. A failed answer writes the notes verbatim. `button()`: `a<n>` calls `Deadlines.add(source="meeting")` (the
only way an item becomes a deadline), `none`, `later` (`offers_due()`, run from `Deadlines.meeting_briefs`, re-sends
them the next evening, Calm reason `meetings.actions`), `not` (cancels the job or restores the blocks, then
`jobs.submit` of the text as a plain request). State `<state>/meetings.json` (`minutes` by id, `KEEP` 60; `briefed`
keys for `Meets:` briefs). `mtg` is a core prefix (`App.callback`, `tests/unit/test_buttons.py:CORE`). Events
`meeting_notes`, `meeting_minutes`, `meeting_button` (counts only). Settings `meetings.minutes`, `meetings.after_h`.
Tests: `tests/unit/test_meetings.py`.

**People in the weekly summary** (0.6.0): `week_line(app, days=7)` is one line built only from project notes
(`infer.projects_with`, de-duplicated by note and surname): "met" from the `minutes-YYYY-MM-DD` block keys
(`MINUTES_DAY`) and `Last met:` dates in the window, "next" from `next_after()` within 7 days (sorted by time), and
"not met for a while" for notes with a `Meets:` schedule whose `last_met()` is `QUIET_DAYS` (21) or more ago. "" when
there's nothing. `modules/weekly.py:summary` adds it when `weekly.people` is on (a failure is `weekly_line_failed`);
nothing else sends it.

## Dates offered with a button (`core/dateoffers.py`)

What Photo to dates (`modules/photodates.py`), Email in (`modules/mailin.py`) and a shared class calendar
(`modules/calendar.py:_offer_shared`) found, offered one **Add** button each; nothing is added without a tap.
`clean_items(raw)` checks an AI's or a calendar's items (title, ISO date not before yesterday, `HH:MM` or "", type
`deadline` | `exam` | `event`, optional `where`; repeats dropped; sorted by date and time) and `clean_classes(raw)` a
timetable's (`subject`, `day` mon..sun, `start` < `end`). `make(app, source, items, classes, about)` keeps a batch in
`<state>/date-offers/<id>.json` (the newest `KEEP` 100) and returns its id (None: nothing); `message(app, id, intro)`
gives the text and buttons: `dof:<id>:<n>` (at most `SHOWN` 10), `:tt` (the classes), `:all`, `:none`. `button()`
(a core prefix in `App.callback`; `tests/unit/test_buttons.py:CORE`) under the `date-offers` lock: a deadline or exam
→ `Deadlines.add(source=photo | mail | shared-calendar, kind=exam | task)` (no time: 23:59); an event →
`Reminders.add` `date_offers.remind_min` (60) before it (no time: 08:00 that day; never in the past); classes →
`add_classes()`: `Subjects.resolve()` else a new subject in `subjects.list`, then `subjects.timetable` rows unless one
starts then. A feature that's off is named in the answer and the item stays open. Events `dates_offered`,
`dates_tapped`, `timetable_from_photo` (counts). Tests: `tests/unit/test_inputs.py`.

## Keep or drop (`core/keep.py`)

`app.keep` (`Keep`) counts what the user uses of each feature: `Keep.used(module, how, via)` with `how` one of
`intent`, `command`, `button`, `tool`, `reply`. Called from `App.handle` (a module's `replies()` handler, its
command, its intent; a taught or classifier-picked intent through `intent_owner`), `App.callback` (a module's
button), `modules/calls/__init__.py:Calls.run_tool` and `core/tools.py:run_tool` with `via="call"` (`tool_owner`: the
module whose `call_tools()` has it, else `calls`). `via="setup"` (the try-it box) isn't counted. Stored in
`<state>/keep.json`: `used[module][YYYY-MM-DD][how]` (pruned to `KEEP_DAYS = 90` by the tick), `last[module]`,
`since` (set by the first `start()`), `first`, `monthly_at`, `answered[module]`.

`keep:tick` (daily 12:00): with `setup.done`, at `FIRST_DAYS = 10` after `since`, one message (Calm reason
`keep.ask`, kind `question`) lists every enabled feature but `NEVER = ("telegram",)` with `counts(days)` and
`Calm.sent_by(since)` (messages and calls that came by themselves, not exempt `own`), and a row per feature (least
used first, at most `MAX_ROWS = 15`): `keep:<id>:keep|quiet|off` (routed in `App.callback`). After `UNUSED_DAYS = 60`
of counting, at most every `MONTH_DAYS = 30`: `idle()` = enabled features with no use for 60 days, a recurring job
under `<id>:`, and no answer in `AGAIN_DAYS = 90`. `keep.ask = false` sends neither (the day-10 one is then skipped
for good).

Quiet is `quiet_change()`: a Calm `Change` adding the feature's non-exempt, stoppable `REASONS` to
`notify.calm.stopped` (offered only while Calm is on and something is left to stop). Off is `Change(module=id)`
(`App.disable`; not offered when another enabled feature requires it). Both go through `Calm.apply`, so Undo is
`calm:<uid>:undo`. Calls a quiet feature places aren't stopped (`Calm.call_ok` doesn't read the stopped list).
`/keep` (`Keep.command`, in `App.handle` and `core/commands.py:CORE`): counts for 30 days, `/keep <1-90>`, `/keep <feature>`
with its row. Events `keep_asked`, `keep_answer`, `keep_failed`. Tests: `tests/unit/test_keep.py`.

## Your rhythm (`core/rhythm.py`)

`app.rhythm` (`Rhythm`), started after Keep; `rhythm:tick` every 30 min runs, outside the night, `learn()` once a day
(`looked` in `<state>/rhythm.json`) and `tell_lighter()`, and `absence()` always (it checks the night itself). Errors go
to `rhythm_failed` per part. Rules only, no AI.

- **Quiet hours.** `usual()` reads `ACTIVE` events (`message_in`, `button_tapped`, `call_answered`, `alarm_up_now`) of
  `LEARN_DAYS = 21`, keeps per wake date the longest gap of `QUIET_MIN_H`–`QUIET_MAX_H` (4–16 h), skipping a gap that
  ends within `BACK_MIN` of Kurooto coming back online (`Presence.offline`), and with `LEARN_NIGHTS = 7` or more takes
  the circular middle (`middle()`) of starts and ends, rounded to 30 min, within `NIGHT_MIN_H`–`NIGHT_MAX_H` and an end
  between `WAKE_FROM` and `WAKE_TO` (03:00–18:00). Stored as `usual` (the alarm's `suggest()` reads it via
  `usual_hours()`). `learn()` (`availability.learn_night`) moves `availability.night.from/to` when either end is
  `LEARN_GAP_MIN` (60) off, and with `availability.learn_morning` the `MORNING` settings (`checkins.day_starts` wake −
  2 h, `dreaming.when` wake + 30 min, `startby.when` wake + 1 h, only single `daily HH:MM` specs); never a key the user
  set (`_yours`: a user value other than the last learned one). Cooldown `AGAIN_DAYS` (7), `UNDONE_DAYS` (30) after
  Undo. Changed modules are restarted (`_restart`: `Module.start()`, so `every` jobs take the new spec). One message,
  Calm reason `rhythm.night`, `rhy:night:undo` (restores each key it still holds, `Settings.reset` where there was no
  user value). Event `rhythm_night_learned`, `rhythm_night_undone`.
- **Lighter days.** `lighter(day)` (`notify.calm.lighter_after`): the previous check-in day (from `checkins.day_starts`)
  had an `exam` deadline (`open` or `done`) due in it, or `HEAVY_H` (8) study hours on its date (`Study.totals`).
  Used by `Calm.day_limit` (`lighter_limit`), `Checkins._plan` (first check-in `LATER_MIN` later) and the morning line
  `lighter_line(mark)` (Dreaming's report when it's on, else `tell_lighter()`, Calm reason `rhythm.lighter`), once a
  day (`lighter_told`). `rhy:lighter:no` sets `not_today` and calls `Checkins.unlighten`. Events `rhythm_lighter`,
  `rhythm_lighter_cancelled`.
- **Absence.** `absence()` (`availability.absence_days`, 2): `last_seen()` that many days back, Kurooto offline less
  than half of it, not night/focus/quiet/paused/quiet week, and not already asked for this `seen`: one question, Calm
  reason `rhythm.absence`, `rhy:absence:fine|busy`. Busy: `Availability.set_quiet` a week and `quiet_until` in state
  (`quiet_week()`); its reply (`why="asked"`) has `rhy:quiet:undo`. Events `rhythm_absence_asked`, `rhythm_quiet_week`.

Tests: `tests/unit/test_rhythm_learn.py`.

## The message policy: Dream RSI, part two (`core/policy.py`)

Dream-RSI (arXiv 2609.14858) mapped onto Calm: the base assistant isn't changed; a small policy decides when messages
that come by themselves reach the user; every past message is the record; offline, the record is a replay simulator
that can reorder (now vs. the evening bundle) but never invent outcomes; each night variants are proposed, today's
policy is always one of them, all are scored on the whole record, and the best becomes the new policy only if it wins
by a margin. Part one is Dreaming's self-check (`modules/dreaming.py:self_check`).

- **The policy** (`Candidate`, `today(app)`): `evening` (`notify.calm.evening`), `habituate`
  (`notify.calm.habituate`), `windows` (`notify.calm.windows`). Everything else in Calm, availability and the user's
  settings is a hard constraint. Tunable kinds (`tunable(why, never)`): a known `Reason`, not `exempt`, `later` true,
  not in `dreaming.never_tune`. Kinds the user already has an entry for (in any of the three, `stopped` or `fewer`) or
  whose change from here was undone or reverted within `BLOCK_DAYS = 30` (`blocked()`) aren't proposed.
- **The record** (`record(app)`): `calm.db` rows with `kind!='ring'`, a known `why`, state `sent` or `bundled`, no
  `exempt` (all 45 days: the pool grows to that), as `Row(ts, why, bundled, held, answered, answerable)`;
  `answerable` = it had buttons or a reply mapping. `calm_less` events mark the latest row of that reason in the day
  before as `less`.
- **The replay** (`replay(app, c, rows, base)`): per judged row (tunable, and answerable or `less`),
  `Candidate.place(row, ignored, evening)` says `now` or `evening`: after that day's `evening_at` always `now`; a row
  held for a reason the policy doesn't own (limit, fewer, exams) stays `evening`; then `evening`, `windows`, and
  `habituate` against `streak()` over earlier rows of the kind. Score: `+ANSWERED` (1) for an answered row still in
  time; `-DELAYED` (5), or `-DELAYED_QUICK` (10) when answered within `QUICK_MIN = 30` minutes, for one sent now and
  answered before that evening that the policy would hold; `-IGNORED` (1) for an unanswered interruption,
  `-IGNORED_BUNDLED` (0.2) in the bundle; `-LESS` (2) for a `less` row sent now; minus `CHANGE[lever]` (habituate
  0.5, window 0.75, evening 1.0) for a variant. With `base`, `saved` and `delayed` count rows that differ from it.
- **A round** (`tune(app)`, once a day: `dream-policy.json` `day`): `propose()` makes one-setting variants for the
  `TOP_KINDS = 3` kinds with the most unanswered interruptions (at least `MIN_SEEN = 5` judged, `MIN_IGNORED = 3`):
  habituate N in `HABITUATE_N = (2, 3, 5)`, the evening bundle, and a window from the hours of the answered ones. The
  best strictly beats today's or today's stays (so it's never worse on the replay); it's applied only when it beats
  today's by `dreaming.tune_margin` (3.0), through `Calm.apply(change, why=BY)` (`"dreaming.policy"`), so Undo is
  `calm:<uid>:undo`. Every round is kept (last 30) and emits `dreaming_policy`; an exception emits
  `dreaming_policy_failed` and costs nothing else.
- **Dreaming's hook**: `Dreaming.report` calls `policy.morning(app, send)`: `(lines, buttons)`; it tunes only for the
  sent morning message (`/dream` shows today's decision again) and gives one "Learned while you slept: ..." line with
  an Undo button. `/dream policy` is `policy.show(app)`.
- **Adding a lever**: a Calm setting `_wait` reads (the runtime, with a `HELD` text), its rule in `Candidate.place`
  (the replay must decide it from recorded fields only), its proposals in `propose()` with a `CHANGE` cost and a
  `Candidate.said()`/`change()` branch, `KEYS`, and a test in `tests/unit/test_dream_policy.py`. Never a lever that
  sends something that wasn't sent: the replay can't judge it.
- **Split for part three**: `consider(app)` is the round without applying (`(decision, change)` or None),
  `settle(app, d, change, apply, why)` applies through Calm and keeps the decision; `tune(app)` is both with the plain
  margin. `line(d)`, `applied_today(app)` and `live(app, d)` serve `core/tuning.py`.

## Tuning the rest: Dream RSI, part three (`core/tuning.py`)

The same method on three more recorded decisions, each an "area" with its switch (`dreaming.tune_effort`,
`tune_fallbacks`, `tune_sizing`, on) and a `*_plan(app, st)` returning `(decision, Change | None)` or None (off, no
record): today's rules are scored by a replay, one-setting variants are scored the same way minus `CHANGE[area]` (0.5),
the best strictly better one (ties keep today's) is the area's proposal.

- **Effort** (`effort_plan`): the runtime is `Jobs._run`: `effort.pick_with_origin` gives `(level, origin)` (origin
  `notes`, `low`, `medium`, `high`; None for a typed prefix), and for lane `you` `effort.tuned(level, origin,
  brain.effort_map)`; the origin goes in `jobs.effort_from`. The record (`asks()`): lane-`you` jobs of 45 days with
  their misses: `wrong` (a Wrong case with that `job`, modules/cases.py), `corrected` (`jobs.corrected`, set by
  `heard()` from `App.handle` on `CORRECTS` within 10 minutes of the answer; the words, 300 chars, blanked by
  `Jobs.forget`), `retried` (a later lane-`you` job within `RETRY_MIN = 15` of its end with word overlap ≥ 0.6, or
  the same skill), and verdicts empty/timeout/stuck. Judged: a known origin and level, verdict in
  `JUDGED_VERDICTS`. `_effort_score`: recorded level → `+GOOD` or `-MISS[k]` minus minutes × `MINUTE` (0.1);
  another level is estimated: run time scaled by the levels' recorded median ratio (`TIME` when under 3 each); more
  effort fixes `MORE_FIXES` (half) of a miss and never a timeout; less breaks a good answer with p = max(`LESS_BREAKS`,
  that level's own miss rate) and half the timeouts finish. Variants: one level up or down for an origin with
  `MIN_ASKS = 8` judged requests. Trust kinds `effort.up` / `effort.down`.
- **AI order** (`fallbacks_plan`): runtime in `Jobs._run`: unpinned jobs whose level is in `brain.fallback_first` get
  `[fallback, main, ...]`. The record (`tries()`): attempts of 45 days per unpinned job with a level. `_chain_score`
  plays an order: a recorded try is used as it happened (an answer: `ANSWER` minus minutes and `TRY` per failed try
  before it; a failure in `RETRY_VERDICTS` hands on, others end it with `-FAIL`); an untried AI is estimated by
  `_Odds.guess`: limited (fails fast) when its last try in the `LIMIT_H = 2` hours before was a limit or sign-out, else
  its Laplace-smoothed record at that level (all levels under `MIN_TRIES`). Variants toggle one level, needing
  `MIN_JOBS = 6` jobs there and, to add it, `MIN_FAILS = 3` failed main tries and a fallback record. Trust kinds
  `fallbacks.first` / `fallbacks.back`.
- **Start-by sizes** (`sizing_plan`): `samples()`: deadlines due in 90 days with a size you tapped (startby state
  `sizes`), or done (`done_at`) / with parts half done (`progress_at`, extrapolated) and a subject: study seconds on
  that subject (`Study.day`, manual entries too) each day from its start-by date (`told`, else `SPAN_DAYS = 14` before
  due) to then, shared among that subject's open spans by planned size. Score: `-Σ |ln(h / actual)|`, `UNDER = 1.5`
  times when h is too small. Variants per kind with `MIN_SAMPLES = 4`, not set by the user (a user value that isn't the
  last one applied here): the ladder step nearest the median and the next step toward it. Trust kinds `sizing.up` /
  `sizing.down`.
- **The night** (`night(app)`, from `morning(app, send=True)`, once a day: `dream-tuning.json` `day`): `review()`
  first, then `policy.consider` and each area's plan (an exception skips that area: `dreaming_tuning_failed`). Each
  plan's margin is `dreaming.tune_margin × trust(st, kind)`; of the plans whose gain clears it, the largest gain /
  margin is applied (`Calm.apply(change, why="dreaming.tuning")`, Undo `calm:<uid>:undo`; messages through
  `policy.settle`). The others are kept, with `waited` when they'd have cleared. Events `dreaming_tuned`,
  `dreaming_outcome`.
- **Outcomes and trust** (`review`, `trust`, `live`, `blocked`): an applied decision not `live` any more is `undone`,
  still live after `KEPT_DAYS = 14` is `kept`, counted per trust kind in `outcomes`. `trust = 1 + undone - kept/2`,
  clamped to 1..`MAX_TRUST` (4). `blocked(app, st, area)`: targets applied (or declined) in `BLOCK_DAYS = 30` that
  aren't live.
- **Proposals** (`propose`, `proposal_ready`, `answer`; `dreaming.propose_prompts`, off; needs Skills and Learning):
  `failures()` groups lane-`you` skill jobs (`then_action` skills.done/latex, payload name) of `FAIL_DAYS = 14` with a
  wrong/corrected/retried miss; a skill with `REPEAT = 2`, not blocked, at most every `PROPOSE_EVERY_DAYS = 7`, gets
  one quiet, text-only, background job on `Learning.check_brain()` (lane `chk`) with `PROPOSE`, follow-up
  `dreaming.proposal`. `proposal_ready` drops it unless: not NONE, an extractable skill (`extract_skill`, `make`), the
  file unchanged since (sha), length ratio 0.5-2, and `FIXES k: yes` lines ≥ `FIX_SHARE × trust("prompts")` of the
  cases; else status `ready` with `proposal-<pid>.md`. `morning` offers a ready one (≤ `PROPOSAL_DAYS = 7`) with
  `rsi:<pid>:apply|no`. Apply: `Learning._change(name, ..., "proposal")` (before-copy, `lrn:` Undo), then
  `_replay_cases`: `cases.suite()` against this morning's `passing`; a newly failing case undoes it. No: `declined`,
  counted `undone` for `prompts`, and the skill blocked.
- **Adding an area**: a setting the runtime reads, a `*_plan` with a replay from recorded fields, a `live()` branch, a
  trust kind per direction, its entry in `AREAS`, a line in `show()`, and a test in `tests/unit/test_dream_tuning.py`.

## Colours: palettes and named themes (`core/palette.py`, `core/themes.py`)

`look.palette` picks the colours of every page, the dashboard's canvases, the terminals (kitty, Windows Terminal, the
dashboard's xterm tabs) and `kurooto top`. `palette.NAMES` is `OWN` (`kuro`, `rose`, `system`) and then the named
themes (0.7.0). Everything that draws asks `palette.py`: `current(app, mode)` (CSS variables, `kurooto top`),
`css(app)` (the `<style id="kurooto-palette">` that `Server.fill` writes into each page and `static/palette.js`
refreshes every 30 s), `describe(app)` (`GET /api/look`: choices, previews, vars, css), `settings_choices` and
`check` (Settings → Look). `modules/terminal/look.py:palette()` reads kuro and rose from `style.css` and a named
theme from `palette.role_map(name, "dark")`. The dashboard's canvases (SYSTEMS, the notes map, meters, the mesh)
draw only with `PAL` in `home.js`, read from the CSS variables at load and again on the `kurooto:palette` event; a
change in Settings reloads the dashboard.

**Roles** (`palette.KEYS`): `bg` the page, `panel` panes and cards, `line` borders, `fg` text, `dim` secondary text,
`accent` the fill of buttons with `accent-contrast` as its text and `hover` its hover, `accent-text` the accent as
text, `link`, the secondary colours `lav`, `pink`, `peach`, `sand`, `rose` (the dashboard's cells, neighbourhoods
and graphs, headings), and `ok`, `warn`, `bad` for status (never the accent). `palette.TEXT` is every text colour:
each must reach WCAG AA (4.5:1) on `bg` and on `panel`, and `accent-contrast` on `accent` and `hover`
(`failures()`).

**Named themes.** `core/themes.py` is plain data:

- `Flavour`: an id (`catppuccin-latte`), the project's own name (`Catppuccin Latte`, with its spelling: Rosé Pine,
  Frappé), `mode` dark or light, `colours` (the official palette, the project's colour names to hex, copied exactly
  from its repository; `tests/unit/test_themes.py` spot-checks them) and `roles` (Kurooto's role → one of those
  names; `on` is the preferred text on the accent).
- `Family`: its dark flavours, its light flavour, the source URL and licence.
- `THEMES`: one per dark flavour, keyed by `look.palette`'s value: the flavour id (`catppuccin-mocha`), or the
  family's name where it has one dark flavour (`gruvbox`, `everforest`, `solarized`; `nord` and `dracula` are both).
  A theme is (family, dark flavour, light flavour): the dashboard (always dark) and the terminals use the dark
  flavour, the other pages the light flavour when the browser is in light mode. Light flavours aren't values of
  their own (`check` refuses `catppuccin-latte`): the pairing keeps the dashboard dark.

`palette._flavour(fid)` turns a flavour into CSS variables: `bg`, `panel` and `line` as published; each text colour
through `readable()` (lighter on dark pages, darker on light ones, in OKLCH, hue kept, the smallest step that
reaches 4.5:1 on both backgrounds); the accent fill kept unless it's under 3:1 on the page; its text the flavour's
`on` colour, else its background, else its text colour, whichever reads at 4.5:1, else the fill a shade darker or
lighter. Where an official colour failed and a sibling of the same palette passes, the role map uses the sibling
instead (Nord's links nord8, Kanagawa's errors peachRed, Rosé Pine Dawn's success pine, Solarized's text the
emphasized tone); the rest moved, listed by `palette.adjusted()`. `css(app)` for a theme: the dark flavour on
`:root[data-palette="<id>"]`, the light flavour inside `@media (prefers-color-scheme: light)`, and the dark flavour
again on `[data-palette="<id>"] body.home`.

`palette.role_map(name, mode)` gives a role → hex map (no `--`) for kuro, rose, a theme or a flavour, and
`palette.export()` everything but `system` as JSON-ready data (`themes` with their flavours, source and licence;
`flavours` with their roles). The phone app's colour scheme will take the same palettes from it (planned with the
Compose app; not built).

**Adding a theme:** its official colours and a role map in `themes.py` (a comment with the source), a `Flavour`
per flavour, a `Family`; then the user wiki's theme list and credits, and the table below
(`palette.adjusted()`; a test checks every row is here). `test_themes.py` checks every pair.

Role maps (the palette's own colour names):

| family | bg | panel | line | fg | dim | accent | accent-text | link | lav | pink | peach | sand | rose | ok | warn | bad | on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Catppuccin | base | mantle | surface0 | text | subtext0 | mauve | mauve | blue | lavender | pink | peach | rosewater | flamingo | green | yellow | red | crust |
| Tokyo Night | bg | bg_dark | fg_gutter | fg | fg_dark | blue | blue | cyan | magenta | purple | orange | yellow | green1 | green | yellow | red | bg_dark |
| Rosé Pine | base | surface | highlight_med | text | subtle | rose | rose | iris | foam | love | gold | rose | iris | foam | gold | love | base |
| Rosé Pine Dawn | base | surface | highlight_med | text | subtle | rose | rose | iris | foam | love | gold | rose | iris | pine | gold | love | base |
| Gruvbox Dark | dark0 | dark0_hard | dark2 | light1 | light4 | bright_yellow | bright_yellow | bright_blue | bright_blue | bright_purple | bright_orange | light2 | bright_aqua | bright_green | bright_yellow | bright_red | dark0 |
| Gruvbox Light | light0 | light0_hard | light2 | dark1 | dark4 | faded_yellow | faded_yellow | faded_blue | faded_blue | faded_purple | faded_orange | dark2 | faded_aqua | faded_green | faded_yellow | faded_red | light0 |
| Nord | nord0 | nord1 | nord3 | nord6 | nord4 | nord8 | nord8 | nord8 | nord7 | nord15 | nord12 | nord13 | nord9 | nord14 | nord13 | nord11 | nord0 |
| Nord Light | nord6 | nord5 | nord4 | nord0 | nord3 | nord10 | nord10 | nord10 | nord10 | nord15 | nord12 | nord3 | nord9 | nord14 | nord13 | nord11 | nord6 |
| Dracula | background | background | current_line | foreground | comment | purple | purple | cyan | cyan | pink | orange | yellow | purple | green | orange | red | background |
| Alucard | background | background | selection | foreground | comment | purple | purple | cyan | cyan | pink | orange | yellow | purple | green | orange | red | background |
| Everforest | bg0 | bg_dim | bg4 | fg | grey2 | green | green | blue | blue | purple | orange | yellow | aqua | green | yellow | red | bg0 |
| Kanagawa Wave | sumiInk3 | sumiInk4 | sumiInk6 | fujiWhite | oldWhite | crystalBlue | crystalBlue | springBlue | oniViolet | sakuraPink | surimiOrange | carpYellow | waveAqua2 | springGreen | roninYellow | peachRed | sumiInk3 |
| Kanagawa Dragon | dragonBlack3 | dragonBlack4 | dragonBlack6 | dragonWhite | oldWhite | dragonBlue2 | dragonBlue2 | dragonTeal | dragonViolet | dragonPink | dragonOrange | dragonYellow | dragonAqua | springGreen | roninYellow | peachRed | dragonBlack3 |
| Kanagawa Lotus | lotusWhite3 | lotusWhite2 | lotusViolet1 | lotusInk1 | lotusGray2 | lotusBlue4 | lotusBlue4 | lotusTeal2 | lotusViolet4 | lotusPink | lotusOrange | lotusYellow | lotusAqua | lotusGreen | lotusOrange2 | lotusRed3 | lotusWhite3 |
| Solarized Dark | base03 | base02 | base01 | base1 | base0 | blue | blue | blue | violet | magenta | orange | yellow | cyan | green | yellow | red | base03 |
| Solarized Light | base3 | base2 | base1 | base01 | base00 | blue | blue | blue | violet | magenta | orange | yellow | cyan | green | yellow | red | base3 |

Official colours moved to reach AA (everything else is exactly as published):

| flavour | role | official | used |
|---|---|---|---|
| catppuccin-latte | dim | subtext0 #6c6f85 | #63667c |
| catppuccin-latte | accent-text | mauve #8839ef | #8535eb |
| catppuccin-latte | link | blue #1e66f5 | #135cea |
| catppuccin-latte | lav | lavender #7287fd | #4c5bcd |
| catppuccin-latte | pink | pink #ea76cb | #a93a8f |
| catppuccin-latte | peach | peach #fe640b | #b44300 |
| catppuccin-latte | sand | rosewater #dc8a78 | #9d5141 |
| catppuccin-latte | rose | flamingo #dd7878 | #aa4b4d |
| catppuccin-latte | ok | green #40a02b | #1e7900 |
| catppuccin-latte | warn | yellow #df8e1d | #955b00 |
| catppuccin-latte | bad | red #d20f39 | #ce0436 |
| tokyonight-storm | pink | purple #9d7cd8 | #a07fdb |
| tokyonight-day | fg | fg #3760bf | #2f57b5 |
| tokyonight-day | dim | fg_dark #6172b0 | #485893 |
| tokyonight-day | accent-text | blue #2e7de9 | #0058bd |
| tokyonight-day | link | cyan #007197 | #006283 |
| tokyonight-day | lav | magenta #9854f1 | #7b30ce |
| tokyonight-day | pink | purple #7847bd | #7241b6 |
| tokyonight-day | peach | orange #b15c00 | #904a00 |
| tokyonight-day | sand | yellow #8c6c3e | #745527 |
| tokyonight-day | rose | green1 #387068 | #2c645d |
| tokyonight-day | ok | green #587539 | #476428 |
| tokyonight-day | warn | yellow #8c6c3e | #745527 |
| tokyonight-day | bad | red #f52a65 | #ba0046 |
| tokyonight-day | accent | blue #2e7de9 | #0058bd |
| rose-pine-moon | dim | subtle #908caa | #938fad |
| rose-pine-dawn | dim | subtle #797593 | #706c8a |
| rose-pine-dawn | accent-text | rose #d7827e | #a85855 |
| rose-pine-dawn | link | iris #907aa9 | #7b6693 |
| rose-pine-dawn | lav | foam #56949f | #3b7984 |
| rose-pine-dawn | pink | love #b4637a | #a7576e |
| rose-pine-dawn | peach | gold #ea9d34 | #9b6200 |
| rose-pine-dawn | sand | rose #d7827e | #a85855 |
| rose-pine-dawn | rose | iris #907aa9 | #7b6693 |
| rose-pine-dawn | warn | gold #ea9d34 | #9b6200 |
| rose-pine-dawn | bad | love #b4637a | #a7576e |
| rose-pine-dawn | accent | rose #d7827e | #a95855 |
| gruvbox-dark | bad | bright_red #fb4934 | #ff5540 |
| gruvbox-light | dim | dark4 #7c6f64 | #76695e |
| gruvbox-light | accent-text | faded_yellow #b57614 | #986000 |
| gruvbox-light | rose | faded_aqua #427b58 | #3f7855 |
| gruvbox-light | ok | faded_green #79740e | #736e00 |
| gruvbox-light | warn | faded_yellow #b57614 | #986000 |
| gruvbox-light | accent | faded_yellow #b57614 | #986000 |
| nord | pink | nord15 #b48ead | #caa4c3 |
| nord | peach | nord12 #d08770 | #e89d85 |
| nord | rose | nord9 #81a1c1 | #90b1d1 |
| nord | bad | nord11 #bf616a | #f6929a |
| nord-light | accent-text | nord10 #5e81ac | #476993 |
| nord-light | link | nord10 #5e81ac | #476993 |
| nord-light | lav | nord10 #5e81ac | #476993 |
| nord-light | pink | nord15 #b48ead | #7f5c79 |
| nord-light | peach | nord12 #d08770 | #98553f |
| nord-light | rose | nord9 #81a1c1 | #4d6b89 |
| nord-light | ok | nord14 #a3be8c | #566e40 |
| nord-light | warn | nord13 #ebcb8b | #806322 |
| nord-light | bad | nord11 #bf616a | #a44953 |
| nord-light | accent | nord10 #5e81ac | #4a6c96 |
| dracula | dim | comment #6272a4 | #7f90c4 |
| everforest-light | dim | grey2 #829181 | #5f6e5e |
| everforest-light | accent-text | green #8da101 | #606e00 |
| everforest-light | link | blue #3a94c5 | #00709e |
| everforest-light | lav | blue #3a94c5 | #00709e |
| everforest-light | pink | purple #df69ba | #af3d8e |
| everforest-light | peach | orange #f57d26 | #aa4f00 |
| everforest-light | sand | yellow #dfa000 | #8b6200 |
| everforest-light | rose | aqua #35a77c | #007753 |
| everforest-light | ok | green #8da101 | #606e00 |
| everforest-light | warn | yellow #dfa000 | #8b6200 |
| everforest-light | bad | red #f85552 | #c9232b |
| everforest-light | accent | green #8da101 | #687700 |
| kanagawa-wave | lav | oniViolet #957fb8 | #9e88c2 |
| kanagawa-lotus | dim | lotusGray2 #716e61 | #636053 |
| kanagawa-lotus | accent-text | lotusBlue4 #4d699b | #456092 |
| kanagawa-lotus | link | lotusTeal2 #6693bf | #38638d |
| kanagawa-lotus | pink | lotusPink #b35b79 | #994462 |
| kanagawa-lotus | peach | lotusOrange #cc6d00 | #954e00 |
| kanagawa-lotus | sand | lotusYellow #77713f | #66602e |
| kanagawa-lotus | rose | lotusAqua #597b75 | #456761 |
| kanagawa-lotus | ok | lotusGreen #6f894e | #50682e |
| kanagawa-lotus | warn | lotusOrange2 #e98a00 | #8e5200 |
| kanagawa-lotus | bad | lotusRed3 #e82424 | #c5000f |
| solarized-dark | dim | base0 #839496 | #8c9d9f |
| solarized-dark | accent-text | blue #268bd2 | #41a1ea |
| solarized-dark | link | blue #268bd2 | #41a1ea |
| solarized-dark | lav | violet #6c71c4 | #8c93e9 |
| solarized-dark | pink | magenta #d33682 | #fe60a6 |
| solarized-dark | peach | orange #cb4b16 | #f57243 |
| solarized-dark | sand | yellow #b58900 | #bf921a |
| solarized-dark | rose | cyan #2aa198 | #37aaa1 |
| solarized-dark | ok | green #859900 | #8ea219 |
| solarized-dark | warn | yellow #b58900 | #bf921a |
| solarized-dark | bad | red #dc322f | #ff695d |
| solarized-dark | accent | blue #268bd2 | #3294dc |
| solarized-light | fg | base01 #586e75 | #556b72 |
| solarized-light | dim | base00 #657b83 | #576c74 |
| solarized-light | accent-text | blue #268bd2 | #006cac |
| solarized-light | link | blue #268bd2 | #006cac |
| solarized-light | lav | violet #6c71c4 | #5b5fb0 |
| solarized-light | pink | magenta #d33682 | #c12173 |
| solarized-light | peach | orange #cb4b16 | #b83d00 |
| solarized-light | sand | yellow #b58900 | #826200 |
| solarized-light | rose | cyan #2aa198 | #00746d |
| solarized-light | ok | green #859900 | #5e6d00 |
| solarized-light | warn | yellow #b58900 | #826200 |
| solarized-light | bad | red #dc322f | #ca1a1e |
| solarized-light | accent | blue #268bd2 | #0075ba |

## Setting choices and tooltips (0.8.0)

`core/choices.py` (`CHOICES`, `for_section`) lists the settings whose valid values are known (about 25); the API's
`_settings()` merges them in as drop-downs.

**The settings guide (0.8.10).** Every setting has an entry in `tools/settings_guide/NN-<group>.toml`, one file per
feature group (the file's `title`, `intro`, `page`, and the group's `cost` and `needs`), one table each:
`[s."brain.main"]` with `tip` (the tooltip: one sentence for a person, not the code comment), `when` (when you'd change
it and what changes), and where they add something `what`, `values`, `cost`, `needs`, `default` (for computed defaults).
`values` is worked out from `core/choices.py` or the default's type when it's left out, and `cost`/`needs` fall back to the
group's. `[parent."availability.night"] tip` explains a box of several settings (the dashboard shows those as one JSON box).
The phone app's own settings are `app.<Prefs key>` with an explicit `default`. A setting another branch is adding can be
written ahead with `pending = "<why>"`. `tools/gen_settings_guide.py` reads that and `collect()` (every
`register_defaults` call) and writes: `docs/wiki/user/settings-guide.md` (the guide, grouped, an anchor per setting),
`docs/SETTINGS_GUIDE.md` (the one-table view, each line linked to its entry), `src/kurooto/data/settings-help.json`
(`{"section.key": tip}` plus the boxes, which the API's `_tips()` sends per section as `tips`),
`src/kurooto/web/static/settings-guide.js` (every entry, as `window.KUROOTO_SETTINGS_GUIDE`, for the Settings page: a
script because `server.static()` serves no `.json`) and `android/assets/settings-help.json` (the same entries, for
`SettingHelp.kt`). `--check` fails on a setting with no entry, an entry with no `tip` or `when`, an entry for a setting
that's gone, or a stale file; `tests/unit/test_settings_guide.py` also checks that no tip is the code comment copied.
So: register the setting with a comment, add its entry to the group file the error names, run the generator.

`home.js` (`renderSettings`) loads `settings-guide.js` once when Settings opens and puts each setting's tip under it as a
`<details class="set-guide">` line that opens the whole entry, with a link to its anchor on the site's wiki page; the
search box (`settingsFind`) searches the entries too and opens one whose match is only inside it. `look.settings_guide`
(on) is the switch: off, the page renders without the lines and the search keeps to the settings. A test
(`test_every_setting_has_a_tooltip`) fails if a setting has no tooltip. Some defaults only register after their
module is imported (`core.autostart`, `core.infer`, `core.palette`, `web.server`, `web.api`); the test imports them.
`deadlines.skip_notes` (notes or folders the notes scan leaves alone) is one such setting.
