# Testing

## Running the tests

```sh
uv sync --locked                    # Python 3.12+, the dev group (pytest, ruff)
uv run pytest -m "not live"         # what CI runs; -q is the default (pyproject.toml addopts)
uv run pytest tests/unit/test_jobs.py -k watchdog
uv run ruff check . && uv run ruff format --check .
```

- `pyproject.toml [tool.pytest.ini_options]`: `testpaths = ["tests"]`, marker `live` ("needs real accounts or
  network; not run in CI"). Never write a test that needs a real account or the internet without that marker.
- Some tests need Node: `tests/unit/test_static_js.py` (`node --check` on every dashboard script),
  `tests/unit/test_livefallback.py` (runs `tests/js/*.mjs`), `tests/unit/test_calls.py` (the Worker against the
  crypto vectors). They skip when `node` isn't on PATH.
- `tests/integration/` runs the real call-line Worker under `wrangler dev`. It needs Node and the Worker's packages
  (`npm ci --no-audit --no-fund --ignore-scripts` in `src/kurooto/data/worker`, then bundle the call page with
  `npx esbuild web/app.js --bundle --minify --format=esm --target=es2019 --outfile=public/app.js`), and skips on
  Windows or without them (`pytestmark` in each file).
- Android: `android/build.sh --test` runs the crypto and speech tests on a plain JVM; `android/build.sh` builds a
  debug APK (needs the Android SDK).

## The real-install guard

`tests/isolation.py:start()` runs from `tests/conftest.py` before anything imports `kurooto`. It makes every test run
as if on an empty computer and fails any test that touches the developer's real Kurooto:

- A pretend home in a temporary folder: `HOME`, `USERPROFILE`, `XDG_*`, `APPDATA`, `LOCALAPPDATA` and `KUROOTO_HOME`
  (unless set for the run) point into it; `Path.home()` follows `HOME`; `PYTHON_KEYRING_BACKEND` is the null keyring.
  The autouse fixture `nowhere_real` gives **each test** its own fresh pretend home and sets `KUROOTO_SECRETS=file`.
- Stand-ins first on PATH (`_stand_ins`): quiet `notify-send` / `osascript`, and `loginctl`, `systemctl`,
  `launchctl`, `kurooto` that refuse to do anything.
- An audit hook (`sys.addaudithook(_hook)`) refuses and records: opening for write, creating, renaming, deleting or
  chmod-ing anything under the real install's folders and the places Kurooto changes outside them
  (`protected_paths`: the config/data/state/cache folders on every OS, systemd user units, autostart, the app menu,
  `~/.gemini`, `~/.local/bin/kurooto`, LaunchAgents, Start-menu shortcuts); opening a SQLite database there (read-only
  `mode=ro` URIs excepted); running the real `loginctl` / `systemctl` / `launchctl` / `kurooto`; connecting to the
  running dashboard's port (8770 and whatever the real `web.json` says); binding that port is refused so test servers
  move on.
- `pytest_runtest_makereport` turns any recorded violation into a failure of that test, whatever it asserted; the
  terminal summary prints "real-install guard" with violations and reads. Reads of protected folders are only counted.
- Other autouse fixtures: `no_desktop_popups` (stand-ins first on PATH), `no_path_changes` (`core/pathfix.allowed`
  returns False), `calendar_day_checkins` (check-in days start at midnight in tests).

If the guard fires, the code under test computed a path without going through `core/paths.py:paths()` /
`KUROOTO_HOME`, called a real system tool, or reached the real daemon. Fix the code, not the guard.

## CLI runs need a scratch `KUROOTO_HOME`

Outside pytest nothing protects a real install. `kurooto <anything>` from a source checkout, without `KUROOTO_HOME`,
reads and writes the developer's real settings, secrets, scheduler and notes, can talk to the running daemon through
`web.json`, and some commands change the system (autostart, PATH, agy's settings, the app menu). A development run
once changed a live install's settings this way. Always:

```sh
export KUROOTO_HOME="$(mktemp -d)"        # or a fixed scratch folder you reuse
uv run kurooto doctor
uv run kurooto run                         # foreground daemon on the next free port, logs in $KUROOTO_HOME/state/logs
```

With `KUROOTO_HOME` set, secrets go to a file, the default notes folder is `$KUROOTO_HOME/workspace`, agy's settings
are left alone (`providers/agy.py:tools_once` unless `KUROOTO_AGY_TOOLS=1`), and add-on/terminal launchers are
redirected (`modules/terminal/launchers.py:outside`). Still avoid `autostart`, `install-finish`, `uninstall`,
`export-skills`, `term --default`, `rotate` and anything that signs in, unless that is what you are testing in a VM.
Set `KUROOTO_NO_AUTOSTART=1` and `KUROOTO_NO_BROWSER=1` for installer experiments (as `tools/update_rehearsal.py`
does).

## Fakes

| Fake | Stands in for | Used by |
|---|---|---|
| `tests/fakes/telegram.py:FakeTelegram` | the Bot API on localhost (records `sent`, serves `updates` and files, can fail per method, simulates a webhook) | the `env` fixture, most module tests |
| `tests/fakes/openai.py:FakeOpenAI` | an OpenAI-compatible API (modes ok, 429, 401, empty, 500; per-model modes) | brain and quota tests |
| `tests/fakes/openai_tools.py` | a scripted function-calling API | tool-loop tests, the call line's turn fallback |
| `tests/fakes/ollama.py` | Ollama `/api/tags`, `/api/chat` | local models, confidential mail |
| `tests/fakes/fake_agy.py` | the `agy` CLI (`FAKE_AGY_MODE`: ok, prompt, denied, limit, auth, silent, slow, crash) | `test_agy_fallback.py`, jobs |
| `tests/fakes/fake_cli.py` | `claude -p --output-format json` (`FAKE_CLI_MODE`: ok, limit, auth) | `test_claude.py` |
| `tests/fakes/fake_mcp_agent.py` | an agent program that starts `kurooto mcp` and calls one tool | `test_tools_mcp.py` |
| `tests/fakes/google.py` | OAuth token endpoint (checks PKCE), Classroom, Drive, Gmail, Calendar, several accounts | Google tests |
| `tests/fakes/cloud.py:FakeCloud` | Gemini's token endpoint, ntfy, Web Push | `tests/integration/` |
| `tests/js/fake-genai.mjs` | `@google/genai`'s Live API | `tests/js/callpage.mjs` |

Brains accept a list as their executable (`Agy(exe=[sys.executable, "tests/fakes/fake_agy.py"])`), and
`telegram.api_base` points the bot at the fake. Fixtures data: `tests/fixtures/call-vectors.json` (k1, t1, s1),
`tests/fixtures/syscolors/`.

## Writing a test

```python
def test_something(env):                       # a paired app talking to a fake Telegram (tests/conftest.py:Env)
    env.on("reminders")                        # App.enable, asserting it worked
    reply = env.say("remind me in 5 min to stretch")
    assert "I'll remind you" in reply
    assert env.app.scheduler.jobs("reminders:")
    text = env.press("rem:abcd:10")            # a button tap; returns the answerCallbackQuery text
```

- For code that doesn't need Telegram, build an app directly: `monkeypatch.setenv("KUROOTO_HOME", str(tmp_path)); app
  = App()`, and `app.close()` at the end.
- Time: `core/scheduler.py:Scheduler(..., clock=...)` and `Quota.clock` take fake clocks; run due jobs with
  `await app.scheduler.tick()` (or `asyncio.run(...)`).
- AI work: set `brain.main` to a fake (or monkeypatch `providers.build`), submit, then `app.jobs.run_next()` runs one
  job synchronously, including its then-action.
- Scheduled actions: call them the way the scheduler does, `fn(payload)`, not `fn()`. Several real bugs (the Space
  keeper's weekly clean, the concept graph's nightly start) exist because tests called the method directly.
- Cover each user-visible path: the command, the intent, the button, the tool, and the feature being off
  (`App.handle` answers "X is off").
- Keep tests hermetic: no network (use a fake on 127.0.0.1), no sleeping on wall-clock time where a fake clock works.

## CI (`.github/workflows/`)

| Workflow / job | What it runs |
|---|---|
| `ci.yml` `test` | Linux, Windows, macOS x Python 3.12, 3.13: `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest -m "not live"`, then `kurooto --version` and `kurooto doctor` as a smoke test |
| `ci.yml` `call-line` | Node 24, the Worker's packages, the bundled call page, `pytest tests/integration tests/unit/test_calls.py` |
| `ci.yml` `android` | `android/build.sh --test` (vectors), a debug build, Android lint `NewApi` / `InlinedApi` as errors, the debug APK as an artifact |
| `ci.yml` `privacy` | `tools/privacy_scan.py --tree` and `--history` (with the `PRIVACY_DENYLIST` secret), gitleaks over the whole history |
| `ci.yml` `update-rehearsal` | Linux, Windows, macOS: `requirements.lock` matches `uv.lock`, then `tools/update_rehearsal.py` (install, update, rollback, uninstall with the real installer) |
| `android-emulator.yml` | `android/smoke.sh` on emulators API 23 to 35 (android changes, weekly, or by hand) |
| `spike-agy.yml`, `spike-gbrain.yml` | manual one-off probes of agy and GBrain installs on three OSes |

Actions are pinned by commit hash; keep them pinned when updating.

## Before you push

```sh
uv run ruff check . && uv run ruff format --check .
uv run pytest -m "not live"
python3 tools/privacy_scan.py --staged         # the pre-commit hook does this (git config core.hooksPath tools/hooks)
python3 tools/gen_settings_guide.py --check    # if you touched settings
```
