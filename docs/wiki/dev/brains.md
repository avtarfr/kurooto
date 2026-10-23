# Brains (AI providers)

A "brain" is whatever answers an AI request: an agent program running on this computer (agy, Claude Code) or an
OpenAI-compatible HTTP service (a Gemini key, Ollama, anything else). Everything about them lives in
`src/kurooto/providers/`. The job queue (`core/jobs.py`, see [core.md](core.md#jobs)) is the only thing that runs full
requests; a few features call `Brain.complete()` directly for short answers.

The user's view (choosing an AI, limits, fallbacks): [../user/ai-brains.md](../user/ai-brains.md).

## The interface

`providers/base.py`:

| Symbol | What it is |
|---|---|
| `Verdict` (StrEnum) | `ok`, `empty`, `denied`, `rate_limited`, `auth`, `timeout`, `error`, `cancelled`, `stuck`. Every brain maps its failures onto these; the queue decides retries from them. |
| `Task` (dataclass) | One request: `prompt`, `effort`, `title`, `cwd` (the notes folder), `timeout_s`, `context` (the headless preamble), `tools` + `run_tool` (for API brains), `mcp` + `mcp_env` (for agent programs), `text_only`, `on_process(pid)`, `stop` (a `threading.Event`). |
| `Result` (dataclass) | `verdict`, `text`, `seconds`, `detail` (log only, never shown raw), `retry_after_s`, `usage` (dict; keys used: `note`, `limit`, `tool_calls`, `tools_used`, `cost`, `denied`). `.ok` is `verdict == OK`. |
| `Brain` | Base class. Attributes `id`, `label`, `kind` (`"api"` or `"cli"`), `meter`, `denied_help`. Methods `available() -> (bool, why)`, `run(task) -> Result`, `complete(prompt, system, effort, timeout) -> Result`, and for CLI brains `prepare(app)`, `has_worked(app)` / `mark_worked(app)` (a `<state>/<id>-worked.json` marker), `after_test(app)`. |
| `RATE_LIMIT`, `AUTH_FAIL` | Regexes every brain uses to classify error text. |
| `TEXT_ONLY` | The sentence prepended for text-only requests on agent programs. |

`kind` matters: `cli` brains get `prepare()` before each run and `mark_worked()` after a success
(`core/jobs.py:Jobs._run`), and only `cli` brains are eligible as the last resort for a Gemini key
(`Jobs._last_resort`).

## The registry

`providers/__init__.py`:

- `register_defaults("brain", ...)`: `brain.main`, `brain.fallback`, `brain.classify` (`rules` | `main` | any brain id),
  `brain.agy.io_mode` (`pipe` | `pty`), `brain.models` (per brain: `{"low","medium","high"}` model names),
  `brain.base_urls` (per preset), `brain.timeout_min` (`{"low": 10, "medium": 15, "high": 30}`).
- `CHOICES`: id to label, for every buildable brain.
- `AGENT_PROGRAMS = ("agy", "claude")`: the CLI brains, in preference order.
- `RETIRED = {"codex": "Codex"}` and `drop_retired(app)`: clears `brain.main`/`brain.fallback` naming a retired brain
  at startup (`App.__init__`), emitting `brain_retired`.
- `build(app, which)`: constructs a brain from settings and secrets and attaches the quota meter
  (`brain.meter = quota.count`). Always go through `build`, never instantiate a provider directly in feature code:
  a brain built without the meter is not counted against free limits.
- `local(app)`: the Ollama brain when `brain.models.ollama.medium` is set and it answers; used for quick decisions and,
  with `quota.local = background`, for background work while a free limit is kept for the user.

## Providers

### agy (`providers/agy.py:Agy`)

- `kind = "cli"`, `grace_s = 180`. Found with `proc.which("agy", install_dirs())`.
- Command: `agy --model <m> --effort <e> --print-timeout <N>m -p <prompt>` (`Agy._args`). Effort to model:
  `LEVELS` (`low`/`medium`/`high` to the Gemini Flash tiers), overridable through `brain.models.agy`.
- Output read through pipes (`proc.run`) or a pseudo-terminal (`run_pty`, ConPTY via `pywinpty` on Windows,
  `ptyprocess` elsewhere) depending on `brain.agy.io_mode`.
- Prompts longer than `ARG_LIMIT` (20 000 chars on Windows, 100 000 elsewhere) go through `handover()`: written to
  `<notes>/.kurooto/requests/<id>.md` (with a `*` `.gitignore`), and agy is told to read that file. The file is
  deleted after the run.
- Verdicts (`verdict()`): exit 0 with "no output produced" means `DENIED` (agy's way of saying a step was refused);
  rate-limit and auth patterns only count when the exit code is non-zero or there was no output.
- Tools: agy reaches Kurooto's tools through `kurooto mcp`, registered once as agy's MCP server "kurooto"
  (`connect_tools`), and through allow-list entries written into agy's own settings file
  (`settings_file()` = `~/.gemini/antigravity-cli/settings.json`) by `allow_tools()`, which backs the file up into
  `<state>/backups/` first and never removes a rule. `wanted_rules()` builds the list: `mcp(kurooto/*)`,
  `command(<c>)` for each of `COMMANDS`, `read_file(<root>)` / `write_file(<root>)` from `core/places.py`,
  `mcp(gbrain/*)` when the user's own GBrain is exposed, and `read_url(*)`. Non-workspace access keys
  (`NON_WORKSPACE`) are set only when absent.
- Consent: `tools_once()` runs in `Agy.prepare()`. If the wanted rules are not all already granted
  (`<state>/agy-tools.json` records the command and granted rules), it asks once with `ask_consent()` (an approval;
  Deny holds for `DENY_DAYS = 30`). The answer is handled by the `agy.tools` ask hook registered in `App.__init__`
  (`consent_answer`). With `KUROOTO_HOME` set (tests, portable copies) it does nothing unless
  `KUROOTO_AGY_TOOLS=1`.
- Usage counting: `log_usage()` / `log_requests_since()` read agy's own logs, so interactive agy use counts too.

### Claude Code (`providers/claude.py:ClaudeCode`)

- `kind = "cli"`, `grace_s = 120`. Found as `claude` in `~/.local/bin` or on PATH (`_which`).
- Nothing is written into Claude Code's own settings. Each run gets a temporary folder with `settings.json`
  (permissions), `mcp.json` (servers) and `context.md` (`ClaudeCode.args`), and is started with
  `-p --output-format json --no-session-persistence --setting-sources "" --permission-mode dontAsk`, plus
  `--settings`, `--add-dir`, `--mcp-config ... --strict-mcp-config`, `--append-system-prompt-file`, `--effort`,
  `--model`. The prompt goes on stdin.
- `permissions(app, task)`: `Edit(//path/**)` for every write root, `Read(//path/**)` for every read root
  (`rule_path()` converts Windows drive paths to `//c/...`), `Bash(<c>)` and `Bash(<c> *)` for agy's `COMMANDS`,
  `WebFetch`, `WebSearch`, `mcp__kurooto`, `mcp__gbrain` when applicable; `deny` always holds `Bash(kurooto)` and
  `Bash(kurooto *)`.
- Text-only requests get `--tools ""` and no MCP config.
- `ClaudeCode.verdict()` parses the last JSON line (`type == "result"`): `is_error` goes through `_fail()`;
  `permission_denials` with no text becomes `DENIED`; a "usage limit reached|<epoch>" message sets
  `retry_after_s` (`LIMIT_RESET`).
- Default models: `MODELS = {"low": "haiku", "medium": "sonnet", "high": "sonnet"}`, overridable through
  `brain.models.claude`.

### OpenAI-compatible (`providers/openai_compat.py:OpenAICompat`)

- One class for every HTTP brain, configured by `PRESETS`: `gemini` (Google's OpenAI-compatible endpoint, with
  `alternatives`: when one model's daily free limit is used up, `_turn()` tries the next of the family and adds a
  `note`), `ollama` (`http://127.0.0.1:11434/v1`), `custom`, and the retired-but-working `freellmapi`.
- Key: secret `<preset>.api_key` (`providers/__init__.py:_build`); Ollama gets the dummy key `"ollama"`.
- `available()` needs a base URL, a key and a `medium` model.
- `run()` is a function-calling loop: tools are declared with `declaration()`, each round's `tool_calls` are run
  through `task.run_tool` (results clipped to 20 000 chars), at most `MAX_ROUNDS = 16` rounds, then a final round with
  `tool_choice: "none"` and the `ENOUGH` instruction. One short rate-limit wait (at most 60 s, not for a daily limit)
  is retried. A 4xx saying the model can't take tools (`NO_TOOLS`) falls back to a plain chat.
- A non-loopback service's single request is capped at `REQUEST_S[effort]` (180/300/600 s) so a dead connection fails
  early; a local one gets the request's whole time (`OpenAICompat.local`).
- `reasoning_effort` is sent only for presets with `reasoning: True` (Gemini).
- 429 responses carry `usage["limit"] = core.quota.hints(...)`, which teaches the quota its numbers.

## Effort

`providers/effort.py:pick(prompt, classify)`, called by `Jobs._run` when the job's `effort_req` isn't fixed:

1. A `low:` / `medium:` / `med:` / `high:` prefix (`FORCED`, stripped at `Jobs.submit` by `strip_forced`).
2. Anything matching `NOTES` (notes, revision, explain, derive, proof...) is `high`.
3. Otherwise a classifier, if `brain.classify` isn't `rules` (`Jobs._classifier`): the main brain or another one
   answers `QUESTION + prompt` at low effort with a 30 s timeout. If that brain's limit is kept for the user, it moves
   to the local model (unless `quota.local = off`) or falls back to the rules.
4. Default `medium`. A `low` answer is raised to `medium` when the prompt contains an action word (`ACTS`).

Timeouts per level: `brain.timeout_min`.

## Fallback order for one job

`core/jobs.py:Jobs._run` builds the chain:

1. `main` = `build(brain.main)`, `fallback` = `build(brain.fallback)`.
2. If the job was submitted with `brain=` (e.g. a concept-graph role), that brain becomes main and the first other
   available agent program becomes the fallback.
3. `_last_resort(main)`: only when main is `gemini`, the first agent program that is available and `has_worked()` is
   appended. Agent programs never fall back to the Gemini key.
4. `quota.arrange(chain, level, background)` (`core/quota.py:Quota.arrange`): for your own requests, brains whose limit
   is used up go last; for background requests, brains whose limit is kept for you are dropped, and with none left the
   job is deferred (`Jobs._defer`, `not_before` set to the reset time) or moved to the local model.
5. Each brain is tried in order; `RETRY = (RATE_LIMITED, AUTH, ERROR, DENIED, EMPTY)` moves to the next. `TIMEOUT`,
   `CANCELLED`, `STUCK` and `OK` stop. `Jobs._problem` tells the user about a rate limit or sign-out at most once an
   hour per brain (marker files `<state>/jobs/told-<brain>-<verdict>`).
6. An answer from the last resort carries a one-line note saying why (`_why`).

## Tools exposed to the AI

`core/tools.py:agent_tools(app)` is the single list every unattended request gets:

- `NoteTools.tools()`: `search_notes`, `read_note`, list/create/append/section-add, tick a task, `edit_note` (keeps up to
  `HISTORY = 20` earlier versions in `<state>/note-history/`). Writes go through `writable()` and `write_note_file()`
  (atomic rename, original line endings kept, Windows-reserved names refused).
- `FileTools.tools()`: `read_file`, `list_files` (read-only, inside `places.read_roots`, links resolved and checked by
  `places.inside`), `fetch_url` (GET only, refuses this computer and private networks, at most `MAX_PAGE` bytes).
- `sync_tools()`: `sync_status`.
- `app.ask.agent_tools()`: `ask_user`.
- For each enabled module: `call_tools()` and `agent_tools()`, deduplicated by name; `CALL_ONLY = {"run_task",
  "pending_items"}` are never given to unattended work. Learns from its own work adds `search_history` this way.

`run_tool(app, name, args, tools, via, job=None)` validates `required`, emits `tool_used` / `tool_failed`, notes the
use in the request's tool log when `job` is given (`Jobs.note_step`, see [core.md](core.md#jobs)), and never raises: an
error comes back as a sentence. Text-only jobs get no tools at all (`Jobs._run`: `tools=[] if text_only`).

The `Tool` dataclass lives in `modules/calls/tools.py` (shared with calls): `name`, `description`, `run(args)`,
`params` (JSON schema per argument; build with `arg()`), `required`, `offline` (`needs` | `queue` | `brief`, what a call
does when the computer is off), `hint`, `writes` (True/False/None; MCP turns it into `readOnlyHint`).

### How agent programs get them: `kurooto mcp`

`core/mcp.py` is a stdio MCP server (JSON-RPC 2.0, one message per line; protocol versions in `PROTOCOLS`), standard
library only. It is a bridge: `Bridge.request()` calls the running daemon's `GET /api/tools` and
`POST /api/tools/call` (`web/tools_api.py`) with header `X-Kurooto-Tools: <token>`. The URL and token come from the
environment (`KUROOTO_TOOLS_URL`, `KUROOTO_TOOLS_TOKEN`, set per run by `run_env()`; `KUROOTO_JOB`, the request's id,
which `call_tool` passes on as `job` so the use counts as one of its steps), falling back to
`<state>/tools-access.json` (rewritten at every daemon start). When the daemon is down, `tools/list` answers from
`<state>/tools-list.json` and every call returns `NOT_RUNNING`. `command(persistent=True)` (used for agy's saved
registration) goes through the installed launcher so it survives updates; on Windows `pythonw.exe` is swapped for
`python.exe` (`_console`).

## Read and write allow-lists

`providers/agy.py:COMMANDS` holds only commands that can't start another program whatever their arguments: `find`
(`-exec`), `git` (`-c`, aliases, a repo's config), `latexmk` (`-e`, a `latexmkrc`), `rg` (`--pre`) and `sort`
(`--compress-program`) were removed in 0.5.8, because headless runs read untrusted text (mail, Classroom posts, web
pages) and an injected instruction must not reach code execution. agy's rules have no argument patterns, so a command is
either fully allowed or not listed. Kurooto compiles LaTeX itself (`modules/skills.py:compile_tex`): `-no-shell-escape`,
`-norc`, and `TEX_ENV` (`openin_any`/`openout_any` = `p`) so TeX reads and writes only beside the document.

`core/places.py` is the one source of truth for where the AI may go, used by Kurooto's own file tools, agy's
allow-list and Claude Code's per-run permissions:

- `write_roots(app)`: the notes folder (`notes_root`), the Classroom course-files folder (`course_files`, via
  `core/layout.py:file_dir`), the user's files folder if set (`files_folder`, `files.folder`), and add-ons'
  `skills/` (`core/overlay.py:dirs(app, "skills")`).
- `read_roots(app)`: everything writable, plus `<data>/classroom`, `<state>/classroom-notes`, `<state>/mail-digest`,
  `<state>/reserve`, the OS Documents and Downloads folders (`user_folder`, Windows known folders through
  `SHGetKnownFolderPath`, Linux XDG user dirs) and a Screenshots folder.
- `inside(path, roots)`: resolves links on both sides before comparing.

Changing either list changes what three different brains may do. It also changes agy's saved allow-list, which
triggers a fresh consent question (`tools_once`: "more is wanted than was agreed").

## Headless context

`providers/context.py:headless_context(app)` is prepended to every job: who the user is, the time and zone, the notes
folder, answer style, "nobody can answer follow-up questions", the tool rules, a pointer to `<state>/reserve/`, the
profile brief (`core/aboutyou.py`), "how to help me" (`modules/remember.py:help_brief`) and the notes layout
(`core/layout.py:describe`).

## Adding a brain

1. Subclass `Brain` in a new `providers/<name>.py`. Set `id`, `label`, `kind`. Implement `available()`, `run(task)`
   and `complete(...)`. Map every failure onto a `Verdict` (reuse `RATE_LIMIT`, `AUTH_FAIL`) and fill
   `Result.detail`. Call `self.metered(model, result)` after each request so quota counts it.
2. Honour `task.stop` (stop between steps), `task.on_process(pid)` (so cancel and the watchdog can kill the process
   tree), `task.timeout_s`, `task.text_only`, and either `task.tools`/`task.run_tool` (API) or `task.mcp`/
   `task.mcp_env` (agent program). Use `core/proc.py:run` for subprocesses, never bare `subprocess`.
3. For an agent program, take permissions from `core/places.py` and agy's `COMMANDS`, and deny `kurooto` itself.
   Prefer per-run configuration (as Claude Code does) over editing the program's own settings.
4. Register it in `providers/__init__.py:_build` and `CHOICES`; add it to `AGENT_PROGRAMS` if it is a CLI with tools;
   add it to `web/api.py:BRAIN_ORDER` to show it on the setup page; check `core/quota.py:pool_id` puts it in the right
   pool.
5. Add a fake (see `tests/fakes/fake_agy.py`, `tests/fakes/fake_cli.py`) and tests next to
   `tests/unit/test_brains.py` / `test_claude.py` / `test_agy_fallback.py`, covering each verdict.
6. Declare what it sends where in `docs/PRIVACY.md` and the module's or setup page's privacy text.
