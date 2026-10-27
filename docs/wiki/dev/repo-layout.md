# Repository layout

One line per folder or important file. Paths are relative to the repository root.

## Top level

| Path | What it is |
|---|---|
| `README.md` | the public front page: what Kurooto does, install, first steps, links to docs |
| `AGENTS.md` | a guide for AI agents helping a **user** install, set up and fix Kurooto (not for developing it; that's [agents.md](agents.md)) |
| `CHANGELOG.md` | user-facing changes per version, newest first, `(unreleased)` for work in progress |
| `LICENSE`, `NOTICE` | Apache-2.0 |
| `pyproject.toml` | package metadata and **the version**, dependencies, the `kurooto` entry point (`kurooto.cli:main`), ruff and pytest config, hatch build (the APK as an artifact) |
| `uv.lock` | the locked development environment (`uv sync --locked`) |
| `requirements.lock` | hashed runtime requirements used by installs and updates (`--require-hashes`); must match `uv export` |
| `.github/workflows/` | CI: `ci.yml` (tests, call line, Android, privacy, update rehearsal), `android-emulator.yml`, `spike-agy.yml`, `spike-gbrain.yml` |
| `.gitleaks.toml`, `.gitleaksignore` | gitleaks configuration for the privacy job and hook |
| `.gitignore` | build output, venvs, `node_modules`, `.wrangler`, keys, `.env*`, the bundled `public/app.js`, `wrangler.toml`, the APK |
| `src/kurooto/` | the Python package (below) |
| `tests/` | pytest suite, fakes, JS tests, fixtures (below) |
| `addons/` | add-ons ready to publish as repositories of their own (restic-backups, desktop-helpers, habits, handwriting-pull, night-performance), each with `kurooto-addon.json`, a README and tests; `conftest.py` adds one by link in tests (in `testpaths`) |
| `tools/` | release, privacy scanner, settings guide generator, update rehearsal, git hooks (below) |
| `installer/` | `install.sh`, `install.ps1`, `bootstrap.py` (verifies signed releases, builds the first version), `index.html` and `privacy.html` templates for the site |
| `android/` | the Android app (below) |
| `docs/` | user and maintainer documentation (below) |

## `src/kurooto/`

| Path | What it is |
|---|---|
| `__init__.py` | `__version__` from the installed metadata |
| `__main__.py` | `python -m kurooto` → `cli.main` |
| `cli.py` | every `kurooto` subcommand (argparse in `main()`); talks to the daemon through the local API (`ask_running`) |
| `daemon.py` | `run()` (the daemon), `serve()`, `supervise()`, logging setup, single-instance lock |
| `app.py` | `App`: builds the core services and modules, `handle()` routes messages, `callback()` routes buttons, enable/disable |
| `diagnostics.py` | `kurooto doctor` rows and the redacted diagnostics zip |
| `top.py` | `kurooto top`, the terminal status board |
| `watch.py` | `kurooto watch -- CMD` and the log follower for `kurooto logs -f` |
| `runlog.py` | `kurooto runlog`, experiment-run logs written into the notes |
| `runcompare.py` | run compare (the Research add-on): `kurooto runlog diff` and `/runs compare` |
| `popup.py` | `kurooto ask --popup`, the Quick ask window (Tk); `Asker` is its logic, testable without a window |
| `core/` | shared services: settings, secrets, paths, scheduler, jobs, events, notify, Calm, ask, availability, power, presence, quota, health, tools, MCP, places, layout, the concept graph's engine, ... ([core.md](core.md)) |
| `providers/` | AI brains: `base.py` (interface), `agy.py`, `claude.py`, `openai_compat.py`, `effort.py`, `context.py`, registry in `__init__.py` ([brains.md](brains.md)) |
| `modules/` | one file (or package) per feature, `base.py` (the `Module` class), `catalog.py` (the list) ([modules.md](modules.md)) |
| `modules/telegram/` | the Telegram channel and a stdlib Bot API client (`api.py`) |
| `modules/calls/` | phone calls: connector, deploy, fallback, crypto (`line.py`), phone app channel, post-call review ([calls-and-phone.md](calls-and-phone.md)) |
| `modules/terminal/` | Kurooto Terminal (kitty, Windows Terminal, launchers, default terminal) |
| `modules/curious.py` | not a feature: Dreaming's curious and resurfacing lines (rules only) and their buttons |
| `modules/latex_tracker.py` | not a feature: the Research add-on's LaTeX tracker (build, log, words, BibTeX) |
| `modules/consolidate.py` | not a feature: Dreaming's "Worth a look in what I remember" (duplicates and lines that disagree) and its buttons |
| `modules/fold.py` | not a feature: Dreaming's "For your profile" (lasting things you said, Keep / Not that / Undo into your profile or how-to-help-me note) |
| `modules/coursepages.py` | not a feature: the notes brain's course pages (key concepts and a dated timeline per course) |
| `modules/photodates.py` | not a feature: Photo to dates, part of Deadlines (a photo's dates read by the AI, offered through `core/dateoffers.py`) |
| `modules/mailin.py` | not a feature: Email in, part of Mail digest (mail to +kurooto or a label, filed into notes) |
| `web/` | the local HTTP server, API, live events, tools API, try-it; `web/static/` the pages and scripts ([web.md](web.md)) |
| `update/` | `launcher.py` (stdlib-only, copied into the app folder), `updater.py`, `service.py`, `signing.py` ([release-and-updates.md](release-and-updates.md)) |
| `data/` | package data: `skills/<name>/SKILL.md` (shipped skills), `prompts/`, `prereqs.toml` (helper programs and their checksums), `ollama_models.toml` (models per hardware profile), `research_sources.json`, `troubleshooting.md` (a copy of the user wiki's, for `/fixme`), `known_issues.json` (`/fixme`'s known issues, signed with the release), `worker/` (the call line's Worker source) |
| `data/worker/` | `src/worker.js`, `web/app.js` + `web/fallback.js` (call page source), `public/` (static pages, service worker), `package.json` + `package-lock.json`, `wrangler.template.toml` |

## `tests/`

| Path | What it is |
|---|---|
| `conftest.py` | the `env` fixture (a paired app with a fake Telegram), autouse isolation fixtures, the guard's pytest hooks |
| `isolation.py` | the real-install guard: pretend home, stand-in programs, audit hook ([testing.md](testing.md#the-real-install-guard)) |
| `unit/` | about a hundred test files, roughly one per feature or core service |
| `integration/` | the call line under `wrangler dev` with fakes (needs Node and the Worker's packages) |
| `fakes/` | Telegram, OpenAI-style APIs, Ollama, agy, Claude Code, an MCP agent, Google, the cloud services the Worker uses |
| `js/` | Node tests for the call page, its fallback logic and the Worker's crypto |
| `fixtures/` | `call-vectors.json` (crypto vectors shared by Python, the Worker and Java), `syscolors/` |

## `tools/`

| Path | What it is |
|---|---|
| `release.py` | `keygen`, `build`, `sign`, `yank`, `publish` ([release-and-updates.md](release-and-updates.md)) |
| `privacy_scan.py`, `privacy_allow.txt` | the scanner for secrets and personal data, and the paths exempt from its pattern layer |
| `gen_settings_guide.py` | writes the settings guide (the user wiki's page, `docs/SETTINGS_GUIDE.md`, the dashboard's and the app's help) from the code and `settings_guide/` (`--check` for CI and tests) |
| `settings_guide/` | the settings guide's source: one TOML file per feature group, an entry per setting (0.8.10) |
| `update_rehearsal.py` | installs, updates, rolls back and uninstalls with the real installer in a sandbox |
| `hooks/pre-commit`, `hooks/pre-push` | privacy scan and noreply identity checks (`git config core.hooksPath tools/hooks`) |

## `android/`

| Path | What it is |
|---|---|
| `AndroidManifest.xml` | permissions and components (Gradle sets the package, minSdk 23, target 35) |
| `src/.../kurooto/*.java` | activities (`PairActivity`, `CallActivity`, `AnswerActivity`, `ShareActivity`, `ChatActivity`, ...), `ListenService`, receivers, `Crypto`/`Seal` (k1/s1), `Line`/`Net` (HTTP), `Speech`, `Inbox`, `Prefs`, `Tls`, `Ui` |
| `src/.../kurooto/*.kt` | the main screen in Compose (0.7.0): `MainActivity`, `Home`, `Nav`, `TodayTab`, `AlarmsPane`, `SettingsPane`, `InboxTab`, `Kit`, `Theme`, `Sky` (0.8.10: panes) |
| `src-demo/`, `src-nodemo/` | `Demo.kt`: made-up data for debug and dev builds; empty in release builds |
| `res/`, `assets/isrgrootx1.der` | icons; the Let's Encrypt root for old Android versions |
| `build.sh` | builds with a pinned Gradle it downloads (`--dev` a dev build beside the real app, `--lint`, `--test` the JVM tests) |
| `settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`, `proguard-rules.pro` | the Gradle build (versions pinned in `build.gradle.kts`) |
| `smoke.sh` | emulator smoke test |
| `test/` | `CryptoTest.java` (shared vectors), `SpeechTest.java` |

## `docs/`

| Path | What it is |
|---|---|
| `MANUAL.md` | the user manual: every feature, its setup, troubleshooting, and how to undo it |
| `SETTINGS_GUIDE.md` | every setting and default (generated; don't edit by hand) |
| `PRIVACY.md` | per feature, what leaves the computer and where it goes (rendered into the site's privacy page by `tools/release.py:privacy_page`) |
| `RELEASING.md` | the maintainer's release checklist |
| `ROADMAP.md`, `REQUESTED.md` | ideas not built; requests from users (struck through when done) |
| `friend-test.md` | a script for watching a first-time install |
| `next/` | working notes from earlier branches (`books.md`, `rehearsal.md`); historical |
| `media/` | screenshots and video for the README and site (left out of release builds) |
| `wiki/dev/` | this developer wiki |
