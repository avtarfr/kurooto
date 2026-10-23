# For AI coding agents

This page is for an AI agent (Claude Code, Antigravity, Copilot CLI or any other) changing Kurooto's code. If you are
helping a person **use** Kurooto, read the repository's `AGENTS.md` instead.

Kurooto runs unattended on people's own computers, holds their keys, reads their notes, rings their phones and updates
itself from signed releases. Most of the rules below exist because a mistake reaches someone's real machine.

## Definition of done

A standing rule from the owner: **no change to Kurooto is done until all of these match the code, updated in the same
commit as the change**:

1. the user wiki, `docs/wiki/user/` (the page for the feature, plus `commands.md`, `messages-it-sends.md`,
   `privacy.md`, `troubleshooting.md` or `glossary.md` when they're affected);
2. this developer wiki, `docs/wiki/dev/` (the area's page, and its known problems when you fix or find one);
3. `/help`: the command list Telegram and the phone app's chat show (`core/commands.py`: each module's `commands()`
   help text, `CORE`, the group in `GROUPS`, each request's `examples`), and the `/` menu;
4. `CHANGELOG.md`, a line under the unreleased version;
5. the site pages `tools/release.py` publishes (`site_pages`: the landing page from `installer/index.html`, the privacy
   page (`docs/PRIVACY.md` rendered into `installer/privacy.html` between its `PRIVACY:START`/`PRIVACY:END` markers),
   the changelog page from `CHANGELOG.md`, the install scripts).

Also, when they apply: `docs/MANUAL.md` (with the Undo), `docs/PRIVACY.md`, `docs/SETTINGS_GUIDE.md` (regenerated with
`tools/gen_settings_guide.py`), tests.

## Read first

1. [architecture.md](architecture.md): the daemon's pieces and the path of a message.
2. [core.md](core.md): the services you'll call (settings, scheduler, jobs, notify/Calm, ask, events, locks).
3. [modules.md](modules.md): how a feature is built, its lifecycle, and the module reference.
4. The page for the area you're touching: [brains.md](brains.md), [web.md](web.md),
   [calls-and-phone.md](calls-and-phone.md), [concept-graph.md](concept-graph.md),
   [release-and-updates.md](release-and-updates.md).
5. [testing.md](testing.md) and [conventions.md](conventions.md) before you write code.
6. The code you're changing, its tests, and its section in `docs/MANUAL.md`. The module and function docstrings are
   accurate and dense; read them rather than guessing.

## Invariants that must hold

- **Every feature is off until the user turns it on**, and turning it off stops it: `stop()` calls `super().stop()`
  and undoes what `start()` registered.
- **Nothing leaves the computer unless a feature that is on says so** in its `privacy` text and in `docs/PRIVACY.md`.
  No telemetry, no "phone home". Kurooto never sends mail or messages to anyone but its owner on its own.
- **The user's notes are theirs**: add, never reword or remove their text. Write notes with
  `core/tools.py:write_note_file`, place them with `core/layout.py`. A change to their text, or to any file of a
  project, is made by the AI in a scratch folder and reaches them only as a proposal they apply
  (`core/scratch.py`, `core/proposals.py`; [architecture.md](architecture.md#scratch-folders-and-proposals)).
- **Secrets only in `app.secrets`** (keychain or the owner-only file), never in settings, logs, events, notes, the
  reserve, prompts, argv or the diagnostics bundle.
- **The AI's reach is `core/places.py`**: read and write roots shared by Kurooto's tools, agy's allow-list and Claude
  Code's per-run permissions. A change request's write root is its scratch folder alone (`write_roots(app,
  scratch=...)`). `kurooto` itself is never runnable from an AI request. Widening any of this changes what
  unattended AI can do to someone's files: it needs the owner's OK and makes agy ask the user again.
- **Unattended AI runs can't ask follow-ups**: they get `providers/context.py:headless_context`, the tools, and
  `ask_user` for questions. Don't add anything that would make an agent program prompt interactively.
- **Every scheduled action takes the payload**: `fn(payload)`. Long work starts a thread.
- **Every message that comes by itself has a Calm reason** (`why=`, an entry in `core/calm.py:REASONS`); direct answers
  use `why="asked"`.
- **A failure in one feature never stops the others**: catch at the boundary, emit `<area>_failed`, carry on.
- **Settings defaults come from `register_defaults`** at import time; `docs/SETTINGS_GUIDE.md` is regenerated, not
  edited.
- **Three implementations of the call crypto agree** (Python `modules/calls/line.py`, `data/worker/src/worker.js`,
  Android `Crypto.java`/`Seal.java`) and `tests/fixtures/call-vectors.json` pins them. Change all four together or none.
- **Signed releases are the owner's.** Version bumps, `tools/release.py sign`, `yank` and `publish`, and the keys, are
  never yours to run.

## Commands to run before finishing

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -m "not live"                    # the guard must report 0 violations
python3 tools/privacy_scan.py --staged         # or --files <the files you changed>
python3 tools/gen_settings_guide.py --check    # when settings changed (regenerate without --check)
```

Run the Node-backed tests too when you touched `web/static/`, `data/worker/` or `modules/calls/`
(`tests/unit/test_static_js.py`, `test_livefallback.py`, `test_calls.py`, and `tests/integration/` if the Worker's
packages are installed). Run `android/build.sh --test` when you touched the crypto.

If you used the CLI at all, it was with `KUROOTO_HOME` set to a scratch folder (below).

## Never do

- **Touch a real install.** Don't run `kurooto` (or `python -m kurooto`, or code that builds `App()`) without
  `KUROOTO_HOME` pointing at a scratch folder. Without it the command reads and writes the developer's real settings,
  secrets, scheduler and notes, can reach the running daemon, and some commands change the system (autostart, PATH,
  agy's settings, the app menu). Don't edit anything under the real config, state or data folders, the notes folder,
  `~/.gemini`, systemd units, LaunchAgents or the registry. Don't connect to the running dashboard's port.
- **Weaken the test guard** (`tests/isolation.py`) or mark a test to skip it. A guard violation means the code
  computed a path outside `core/paths.py`, ran a real system tool, or reached the real daemon; fix that.
- **Rebuild after signing.** Once the owner has signed a release, `tools/release.py build` for that version must not run
  again and nothing in `SITE/releases/<v>/` may change: the signed manifest's checksums would stop matching and every
  update would fail. A problem means a new version or a yank, decided by the owner.
- **Add an outward network call without declaring it**: a new host or API needs the module's `privacy` text, a
  `docs/PRIVACY.md` entry, an off switch where it isn't the feature's whole point, and the owner's OK. Updates only fetch
  from `https://` or `http://127.0.0.1` (`update/updater.py:_get`); keep it that way.
- **Inline secrets**: no keys, tokens, passwords or real webhook/Worker URLs in code, tests, fixtures, docs, commit
  messages or logs. Tests use the fakes and obviously fake values (`"123:fake"`). Pass secrets to child processes by
  environment or file, never argv.
- **Commit personal data**: real names, emails, phone numbers, chat ids, home-folder paths from any machine. The privacy
  scanner blocks most of it; don't work around it.
- **Change another program's settings silently.** agy's settings are changed only after consent and with a backup
  (`providers/agy.py:allow_tools`); Claude Code's settings are never written. Follow those patterns.
- **Send, delete, install or sign in on the user's behalf** in code paths that don't ask first.
- **Add dependencies or bump the version** without being asked. A dependency means `uv.lock` and `requirements.lock`
  both change.
- **Reformat files** or make drive-by changes outside the task.

## Working style

- Read the code path end to end before changing it; the docstrings say why things are the way they are.
- Keep diffs minimal. Match the surrounding style: plain-English comments, short user-facing messages.
- Add or update tests in the same change. Test scheduled actions the way the scheduler calls them (`fn(payload)`).
- Meet the [definition of done](#definition-of-done): user wiki, developer wiki, `/help`, `CHANGELOG.md` and the
  site pages, in the same commit as the code.
- Don't commit unless asked; others may be working in the same tree.

## How to report

End with a short report for the person who asked:

- what changed, by file, and why (one line each), including which wiki pages, `/help` text and changelog lines;
- how it was verified: the exact commands and their results (tests passed/failed counts, ruff, the guard's line);
- what you didn't do or couldn't verify (no Node, no Android SDK, a test skipped and why);
- anything that needs the owner: a decision, a release step, a privacy change, a new dependency;
- bugs you noticed outside the task, with `path:symbol`, rather than fixing them unasked.

Be plain about failures: a failing test or an unverified path is reported as such, not described as done.
