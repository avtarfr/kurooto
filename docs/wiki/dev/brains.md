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
| `Task` (dataclass) | One request: `prompt`, `effort`, `title`, `cwd` (the notes folder, or a change request's scratch folder), `scratch` (a change request's scratch folder: the one place it may write), `reads` (the original, read-only), `timeout_s`, `context` (the headless preamble), `tools` + `run_tool` (for API brains), `mcp` + `mcp_env` (for agent programs), `text_only`, `on_process(pid)`, `stop` (a `threading.Event`), `images` (pictures to look at, paths: `OpenAICompat` sends them with the request as `image_url` data URLs; agent programs open them where the prompt says). |
| `Result` (dataclass) | `verdict`, `text`, `seconds`, `detail` (log only, never shown raw), `retry_after_s`, `usage` (dict; keys used: `note`, `limit`, `tool_calls`, `tools_used`, `cost`, `denied`, `prompt_tokens` / `completion_tokens` (OpenAI-compatible), and `limits`, which the queue adds: every limit hit while trying the chain), `model` (the model that answered, as the brain knows it: agy's `--model`, Claude Code's `modelUsage`, the OpenAI-compatible response's `model`; set on failures too). `.ok` is `verdict == OK`. |
| `short_model(model, effort="")` | A model id for the run receipt: no vendor prefix, date or `-latest`, versions dotted (`claude-opus-4-5-20251101` → `opus-4.5`), and no effort suffix when it equals the effort shown (`gemini-3.8-flash-medium` at medium → `3.8-flash`). |
| `Brain` | Base class. Attributes `id`, `label`, `kind` (`"api"` or `"cli"`), `meter`, `denied_help`. Methods `available() -> (bool, why)`, `run(task) -> Result`, `complete(prompt, system, effort, timeout) -> Result`, and for CLI brains `prepare(app)`, `has_worked(app)` / `mark_worked(app)` (a `<state>/<id>-worked.json` marker), `after_test(app)`, and `sees() -> (True | False | None, why)`: can it read pictures (agy and Claude Code: yes; `OpenAICompat`: Gemini yes, Ollama asks `/api/show` for the model's `vision` capability and caches it in `_SEES`, others `None` = try). `providers.sees(app)` answers for `brain.main` with the sentence to show. |
| `RATE_LIMIT`, `AUTH_FAIL` | Regexes every brain uses to classify error text. |
| `TEXT_ONLY` | The sentence prepended for text-only requests on agent programs. |

`kind` matters: `cli` brains get `prepare()` before each run and `mark_worked()` after a success
(`core/jobs.py:Jobs._run`), and only `cli` brains are eligible as the last resort for a Gemini key
(`Jobs._last_resort`).

## The registry

`providers/__init__.py`:

- `register_defaults("brain", ...)`: `brain.main`, `brain.fallback`, `brain.classify` (`rules` | `main` | any brain id),
  `brain.fallback_on` (registered in `providers/fallback.py`, see below); `brain.fallback` may be one id or a list
  (`fallback.chosen()` reads both),
  `brain.agy.io_mode` (`pipe` | `pty`), `brain.models` (per brain: `{"low","medium","high"}` model names),
  `brain.base_urls` (per preset), `brain.timeout_min` (`{"low": 10, "medium": 15, "high": 30}`).
- `CHOICES`: id to label, for every buildable brain (static: extra Claude accounts aren't in it).
- `label(bid, default=None)`: the name to show for any brain id, extra Claude accounts included ("Claude Code
  (work)"). Use it instead of `CHOICES.get`. `choices(app)`: `CHOICES` with the extra accounts after `claude` (the
  setup page's and Settings' lists, `POST /api/brain`'s check).
- `AGENT_PROGRAMS = ("agy", "claude")`: the CLI brains, in preference order. `agent_programs(app)` adds the extra
  Claude accounts after `claude` (the queue's pinned stand-in and `_last_resort`).
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
- `Agy.model(effort)`: the `--model` id for an effort; `run()` puts it on `Result.model`.
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
- A change request runs agy with the scratch folder as its working folder (`Task.cwd`), and its Kurooto tools are the
  confined set (`KUROOTO_JOB` reaches `kurooto mcp`, which lists and calls `tools_for(app, job)`). Nothing is added to
  agy's allow-list for scratch folders (that would ask every agy user again), and the allow-list can't be narrowed per
  run, so agy's built-in file tools keep the usual write roots; `core/scratch.py:audit` reports what changed in the
  original while it ran, in the proposal.

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
  `Bash(kurooto *)`. (0.8.17) `Task.images` that exist get `Read(//file)` for each file exactly and their folders in
  `--add-dir` (before, a picture outside the read roots, such as Interest's screenshot in the runtime folder, was
  named in the prompt but denied).
- Text-only requests get `--tools ""` and no MCP config.
- A change request (`Task.scratch` set, [architecture.md](architecture.md#scratch-folders-and-proposals)): `Edit` is
  allowed for the scratch folder only (`write_roots(app, scratch=...)`), `Edit` of the original and of every usual
  write root is in `deny`, `Read` of `core/scratch.py:SECRETS` is denied in every read root (and `Edit` of them in the
  scratch folder), `SCRATCH_NO` (`mkdir`, `echo`) and agents.scripts are left out, and no GBrain server is given.
  `--add-dir` covers the original and the scratch folder; the run's cwd is the scratch folder.
- `ClaudeCode.verdict()` parses the last JSON line (`type == "result"`): `is_error` goes through `_fail()`
  (`RATE_LIMIT` or `PLAN_LIMIT`: "5-hour limit reached", "You've hit your limit", "Weekly limit reached" are
  `RATE_LIMITED`); `permission_denials` with no text becomes `DENIED`. At a limit `limited()` reads the reset
  (`reset_at()`: "...|<epoch>" (`LIMIT_RESET`), "resets 3pm", "resets 3:30pm (Europe/Berlin)", "resets Oct 27, 9am",
  "resets Mon 9am"; a bare number is never a time) into `retry_after_s` and `usage["limit"] = {"reset_at": ...}`, so
  `core/quota.py` marks the pool used up and `providers/fallback.py` skips it until then.
- `used_model(data)`: the model from `modelUsage` (the entry that cost the most, else wrote the most) or `model`;
  `run()` falls back to the model it passed (`brain.models.claude[effort]`, an alias like `sonnet`).
- With Kurooto's tools, the run's permissions also allow `ListMcpResourcesTool` and `ReadMcpResourceTool`, so it can
  read `kurooto://self`.
- Default models: `MODELS = {"low": "haiku", "medium": "sonnet", "high": "sonnet"}`, overridable through
  `brain.models.claude`.
- Streaming (0.8.16, `voice.speak.stream`): with `task.on_text` set, `args()` asks for `--output-format stream-json
  --verbose --include-partial-messages` and `run()` uses `stream_run()` (proc.run's process handling: own session,
  `children.session`, `kill_tree` at the timeout from a `threading.Timer`; stdout read a line at a time, stderr on a
  thread). `Lines` turns the lines into `on_text(message id, text so far)`: `content_block_delta` text deltas, else a
  whole `assistant` message (block by block or whole); `parent_tool_use_id` (a subagent) is skipped; non-JSON lines
  are ignored. The last line is the same `result` object as `--output-format json`, so `verdict()` is unchanged.
  Without `on_text` the command line and `proc.run` are exactly as before.
- Kept per conversation (0.8.17, `brain.claude.session`, on; `brain.claude.session_idle_min`, 10): a request with
  `Task.session` set (`core/jobs.py:_conversation` from `modules/chat.py:Chat.conversation`: `"main"` or a phone app
  chat's id; never the terminal's, a guest's or a change request) goes to `_session_run()`, a `Session` that runs the
  command `args()` makes (always stream-json, plus `--input-format stream-json`) and gets one
  `{"type": "user", "message": {...}}` line per turn, read up to that turn's `result` line, so `Lines` and `verdict()`
  are unchanged. Sessions are keyed by (conversation, sha256 of the command and its settings.json/mcp.json with the
  temp folder blanked, cwd, account folder): another effort, model, permissions or text-only is another program, so
  nothing it may do changes. The context file is the first turn's context; later turns send the context lines it
  wasn't given yet (`NEWS`, e.g. the time and what was recalled) and leave out chat's `Previous conversation` block
  when every line of it was already sent or answered there (`Session.message`); a prompt without that block (cleared,
  or quiet for 2 hours) opens a new program. Kurooto's tools find the request through `KUROOTO_JOB_FILE`
  (`core/mcp.py:job_id`, written each turn) instead of `KUROOTO_JOB`. One turn at a time (`Session.lock`): a second
  request at once runs on its own. A session that's gone, ends without a result, or says nothing for `FIRST_S` (45 s)
  on its first turn returns None and the turn runs on its own (not after a cancel). `reap()` (a thread, every
  `REAP_S`) closes idle, dead, switched-off ones and those opened under another `brain.main`; at most `SESSIONS_MAX`
  (2) are kept, the longest idle evicted. Closing: stdin closed, then `proc.kill_tree(pid)` after 5 s; `App.close()`
  calls `close_sessions()`. `task.on_process(pid)` is told the session's pid each turn, so a cancel ends it.

### Extra Claude accounts (`providers/claude_accounts.py`, 0.7.0)

Claude Code keeps one sign-in per config folder: `CLAUDE_CONFIG_DIR` names the folder, and the sign-in lives in it
(`.credentials.json` on Linux and Windows; on macOS a keychain item whose service name carries a hash of the folder
path, so the sign-in window and every run must use the same absolute path: `folder()`). Checked against the shipped
CLI's code, not guessed.

- Setting `brain.claude_accounts` = `{"<key>": {"name": "..."}}` (hidden from the brain section; Settings shows its
  own **Claude accounts** section, `Api._claude_section`). Brain id `claude:<key>`; the key (`KEY`, `[a-z0-9-]`, at
  most 24) is made from the name at `add()`, or numbered (`claude:2`), and never changes: `rename()` changes only the
  name, so settings naming the id keep working.
- Folder: `<data>/claude-accounts/<key>/`, mode 0700. `providers._build` makes a `ClaudeCode(account=key, name=...,
  config_dir=folder)`: `id` = `claude:<key>`, `label` = `Claude Code (<name>)`, models `brain.models["claude:<key>"]`
  else `brain.models.claude`. `ClaudeCode.env()` adds `CLAUDE_CONFIG_DIR` for an extra account and returns `None`
  (inherit, as before) for the usual sign-in. `available()` is false when the folder isn't here (a profile restored
  elsewhere: sign in again).
- Because the id differs, everything keyed by brain id is separate per account: `brain-limits.json` (`fallback.cool`,
  `cooling`), the quota pool (`pool_id` gives `claude:<key>`; `quota.label` names it), `Brain.worked_file`
  (`claude-<key>-worked.json`: no `:` in file names), the reading budget (`readbudget.kind` treats any Claude id as a
  plan), the receipt (`brain.label`).
- A limit is also tied to the account signed in (0.8.10): `claude_accounts.signed_in_as(app, bid)` reads only
  `oauthAccount`'s account and organisation ids from that sign-in's `.claude.json` (`~/.claude.json`, or
  `$CLAUDE_CONFIG_DIR/.claude.json`, or the extra account's folder), keeps a 16-character SHA-256 of them (cached by
  mtime), and `fallback.cool` / `Quota._hit` store it as `who`. `fallback.cooling` and `Quota._entry` end the limit
  when a different fingerprint is signed in; no record (None) keeps it until the reset.
- `fallback.auto(app)`: `AUTO` with the extra accounts after `claude`; when `brain.main` is a Claude id, the other
  Claude ids go first. `order()` and `selfdoc` use it.
- Sign-in: `Prereqs.open_signin("claude", env=...)` starts the usual sign-in window with the variable set (Linux:
  `env VAR=... claude` in the terminal, and in `Popen`'s env; macOS: in the Terminal script; Windows: `$env:VAR=...`
  in PowerShell).
- API: `GET brain/claude-accounts`; `POST brain/claude-accounts/add {name}` (folder + sign-in window),
  `.../signin {id}`, `.../rename {id, name}` or `{key: name}`, `.../remove {id, yes: true}` (deletes only that
  folder, only inside `<data>/claude-accounts`, and scrubs `brain.main`, `brain.fallback`, `brain.classify`,
  `brain.models`, the worked marker and the limit record). The setup state carries `claude_accounts` and
  `claude_terms`. CLI: `kurooto ai accounts | add-claude [NAME] | test ID | rename-claude | remove-claude [--yes]`
  (`cli.py:ai_run`).
- Never read, copied or logged: Kurooto doesn't open the folder's files; `modules/backups.py` skips
  `data/claude-accounts` unless `backups.secrets`; the encrypted profile's allow-list never had it.
- Tests: `tests/unit/test_claude_accounts.py` (`tests/fakes/fake_cli.py`: `FAKE_CLI_LIMIT_FOR`, mode `whoami`).

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
- Streaming (0.8.16): `chat(..., on_text=)` and `run()` without tools pass `on_text` down to `_request`, which then
  sends `"stream": true` and reads server-sent events in `_post_stream()` (`data: {...}` lines, `choices[0].delta.
  content`, `[DONE]`), calling `on_text(model, text so far)` and returning a dict shaped like a non-streamed answer.
  The tool loop never streams. Errors are the same exceptions as `_post`, so the verdicts don't change.
- 429 responses carry `usage["limit"] = core.quota.hints(...)`, which teaches the quota its numbers.
- `task.images`: the user message's content becomes `with_pictures()` (the text part, then one `image_url` part per
  picture of a `PICTURE_TYPES` kind under `PICTURE_MAX`, 15 MB); none: the plain string, as before.

## Effort

`providers/effort.py:pick(prompt, classify)`, called by `Jobs._run` when the job's `effort_req` isn't fixed:

1. A `low:` / `medium:` / `med:` / `high:` prefix (`FORCED`, stripped at `Jobs.submit` by `strip_forced`).
2. Anything matching `NOTES` (notes, revision, explain, derive, proof...) is `high`.
3. Otherwise a classifier, if `brain.classify` isn't `rules` (`Jobs._classifier`): the main brain or another one
   answers `QUESTION + prompt` at low effort with a 30 s timeout. If that brain's limit is kept for the user, it moves
   to the local model (unless `quota.local = off`) or falls back to the rules. Where the rules would decide alone
   (`rules`, no brain left, or the internet down), the offline helper decides when it's ready
   (`core/helper.py:Helper.classifier`, see [core.md](core.md#the-offline-helper-corehelperpy)).
4. Default `medium`. A `low` answer is raised to `medium` when the prompt contains an action word (`ACTS`).

Timeouts per level: `brain.timeout_min`.

## Fallback order for one job

**A refused run is tried once more (0.7.3).** When a brain's run ends DENIED (agy tried a command unattended runs
refuse, e.g. `python3 -c` to read Kurooto's source, which ends the whole run even when its notes were written), `Jobs._run`
runs that brain once more with a note appended: don't run commands, and the Kurooto tools it already used (from
`self.steps`) so it doesn't repeat them; `job_retried` is emitted. A second refusal is final and the chain goes on as
before (`test_a_refused_run_is_tried_once_more_and_told_what_is_done`).

`core/jobs.py:Jobs._run` builds the chain:

1. `main` = `build(brain.main)`; `fallbacks` = each of `fallback.chosen(app)` (`brain.fallback`: one id, or a list in
   order; an old single string is a list of one), `fallback` = the first of them.
2. If the job was submitted with `brain=` (e.g. a concept-graph role), that brain becomes main and the first other
   available agent program becomes the fallback.
   With the job not pinned and its effort in `brain.fallback_first` (tuned at night, `core/tuning.py`, which scores
   the main AI against the first of `brain.fallback`), that first fallback moves ahead of main.
3. `_last_resort(main)`: only when main is `gemini`, the first agent program that is available and `has_worked()` is
   appended.
4. The automatic order (0.6.0, `providers/fallback.py`), only when no fallback is picked: `candidates(app, skip)`
   appends the brains of `auto(app)` (`AUTO = ("agy", "claude", "gemini")`, extra Claude accounts after `claude`, and
   the other Claude accounts first when main is one) not already in the chain and set up here (`ready()`:
   built, `available()`, and for a `cli` brain `has_worked()`). They are tried only after a failure whose verdict is in
   `brain.fallback_on` (`triggers()`, default `{"rate_limited"}`; also `auth`, `timeout`) happened in this request, or
   when a limited brain was skipped. `brain.fallback` is the one setting that holds an order (the nightly policy look
   may tune it, with `brain.fallback_first`); there's no separate order setting.
5. `skip_cooling(app, chain)`: brains waiting for a limit's reset (`cooling()`) are left out, unless that would leave
   nothing that will run (then the chain stays whole: the limit may be back early).
6. `quota.arrange(chain, level, background)` (`core/quota.py:Quota.arrange`): for your own requests, brains whose limit
   is used up go last; for background requests, brains whose limit is kept for you are dropped, and with none left the
   job is deferred (`Jobs._defer`, `not_before` set to the reset time) or moved to the local model.
   Then the offline helper's check (`core/helper.py`): with the internet down (`Helper.holds()`), only brains on this
   computer (`Helper.here`) stay; with none, the request is held (`Jobs._hold`, `held`/`held_until`) instead.
7. Each brain is tried in order; a verdict in `RETRY = (RATE_LIMITED, AUTH, ERROR, DENIED, EMPTY)` or in
   `fallback_on` moves to the next. `TIMEOUT` (unless in `fallback_on`), `CANCELLED`, `STUCK` and `OK` stop. A
   `RATE_LIMITED` result calls `fallback.cool(app, brain, result)`: skipped until the reset it named
   (`usage["limit"]["reset_at"]`, `retry_after_s`, `retry_s`), a minute for a per-minute limit, else a back-off
   (`BACKOFF_S` 30 min, doubling while it stays limited, at most `MAX_BACKOFF_S` 5 h); state
   `<state>/brain-limits.json`, event `brain_limited`. An answer from a cooling brain clears it (`clear()`,
   `brain_back`). `Jobs._problem` tells the user about a rate limit or sign-out at most once an hour per brain
   (marker files `<state>/jobs/told-<brain>-<verdict>`).
   A brain that fails with `ERROR`/`TIMEOUT` because the connection went (`Helper.lost(tried)`) ends the loop and the
   request is held for the internet: losing the connection is never a fallback case (no hand-over, no `cool()`).
8. An answer from the last resort carries a one-line note saying why (`_why`). Any stand-in is named in the run receipt
   (`handed()`: "Claude Code hit its limit; agy answered", "Claude Code is at its limit until 15:00; agy answered").

`/brain` lists the order and who is waiting; `/usage` adds a line per waiting brain (`modules/chat.py:limit_lines`).

**The concept graph's roles** (`modules/integrate.py:Integrate.roles`) go through `stand_in(bid)`: a role whose AI is
cooling goes to the first other ready, non-cooling brain of the order, so reading goes on. `core/readbudget.py` keeps
one record per brain: `Budget.count(job.brain)` counts a batch on the AI that read it, and `seen()` records each limit
in `usage["limits"]` on the record of the AI that hit it, so a stand-in's reading never spends the bulk AI's budget.

## The run receipt and the model

`core/jobs.py:receipt(brain, effort, seconds, pct, steps, recalled, model, decided, fell)` builds the one line under
each answer, at most `RECEIPT_MAX` (160) characters: `[decided by X, answered by] AI · model · effort · time · share
of today's limit · what it did · remembered items`. When it's too long, what it did goes first; then it's cut with
"…". `model` is `Result.model`, shortened by `short_model` and stored in `jobs.model` (shown by `/jobs`, `public()` and
the dashboard's AI jobs page, whose result cell has the receipt as its tooltip). `decided`: `Jobs._classifier(main,
jid)` records in `Jobs.decided[jid]` the brain and model that answered the effort question (`who()`: a `cli` brain by
name and model, an API or local one by its model alone; the offline helper, through `_helper_classifier`, by its
Ollama tag); it's shown only when that isn't the brain and model that
answered. `fell` comes from `handed()` (step 8 above).

## Tools exposed to the AI

`core/tools.py:agent_tools(app)` is the single list every unattended request gets:

- `NoteTools.tools()`: `search_notes`, `read_note`, list/create/append/section-add, tick a task, `edit_note` (keeps up to
  `HISTORY = 20` earlier versions in `<state>/note-history/`). Writes go through `writable()` and `write_note_file()`
  (atomic rename, original line endings kept, Windows-reserved names refused).
- `FileTools.tools()`: `read_file`, `list_files` (read-only, inside `places.read_roots`, links resolved and checked by
  `places.inside`), `fetch_url` (GET only, refuses this computer and private networks, at most `MAX_PAGE` bytes).
- `sync_tools()`: `sync_status`, `sync_now`.
- `core/selfdoc.py:tool(app)`: `kurooto_self` (read-only): this computer's `self.md`, or with `part=manual` the shipped
  manual. See [self-manual.md](self-manual.md).
- `latex_tools()` (0.9.0, `tools.latex`): `compile_latex(path)`. The source must be inside `places.read_roots`;
  `_latex_workdir` copies its folder (at most `LATEX_COPY_MAX` files/bytes, hidden files left out; else the `.tex`
  alone) into a temp dir and `modules/skills.py:compile_tex` compiles there (Tectonic `--untrusted`, else `latexmk -norc
  -no-shell-escape` or `pdflatex` twice, `openin_any`/`openout_any` paranoid, `LATEX_TIMEOUT`). Only the PDF is copied
  out, to `latex_dest`: beside the source inside `files.folder` or `places.course_files`; else `layout.file_dir("latex")`
  (the files folder's inbox), except that with no files folder a source in a write root keeps its PDF beside it.
  `latex_rule()` adds a line to the AI's context (`providers/context.py`) when `files.folder` is set: documents it makes
  go there, not in the notes. Events `latex_compiled` (beside), `latex_compile_failed` (the first error line).
- `app.ask.agent_tools()`: `ask_user`.
- For each enabled module: `call_tools()` and `agent_tools()`, deduplicated by name; `CALL_ONLY = {"run_task",
  "pending_items"}` are never given to unattended work. Learns from its own work adds `search_history` this way.

`run_tool(app, name, args, tools, via, job=None)` validates `required`, emits `tool_used` / `tool_failed`, notes the
use in the request's tool log when `job` is given (`Jobs.note_step`, see [core.md](core.md#jobs)), and never raises: an
error comes back as a sentence. Text-only jobs get no tools at all (`Jobs._run`: `tools=[] if text_only`). A guarded
tool (`Tool.guarded`, see [modules.md](modules.md#never-without-a-tap-coretappy)) isn't run unless `via` is in
`tap.DIRECT` (`"call"`: a live call, or one that went on as text): `tap.ask_first()` makes an Approve / Deny
(`source="tap"`, hook `tap.tool`, one per tool and arguments) and the AI is told it waits; Approve runs the tool
(`tap.approved`). `via` from the local API is only ever `mcp`, `dashboard`, `terminal` or `api`, so a program with the
tools-only key can't claim a call.

The `Tool` dataclass lives in `modules/calls/tools.py` (shared with calls): `name`, `description`, `run(args)`,
`params` (JSON schema per argument; build with `arg()`), `required`, `offline` (`needs` | `queue` | `brief`, what a call
does when the computer is off), `hint`, `writes` (True/False/None; MCP turns it into `readOnlyHint`), and for "never
without a tap" `guarded` (an action in `core/tap.py:GUARDED`), `guard_if(args)` (guarded only when it says so) and
`asks` (the tool itself only asks, like `draft_reply`).

### How agent programs get them: `kurooto mcp`

`core/mcp.py` is a stdio MCP server (JSON-RPC 2.0, one message per line; protocol versions in `PROTOCOLS`), standard
library only. It is a bridge: `Bridge.request()` calls the running daemon's `GET /api/tools` and
`POST /api/tools/call` (`web/tools_api.py`) with header `X-Kurooto-Tools: <token>`. The URL and token come from the
environment (`KUROOTO_TOOLS_URL`, `KUROOTO_TOOLS_TOKEN`, set per run by `run_env()`; `KUROOTO_JOB`, the request's id,
which `call_tool` passes on as `job` so the use counts as one of its steps), falling back to
`<state>/tools-access.json` (rewritten at every daemon start). When the daemon is down, `tools/list` answers from
`<state>/tools-list.json` and every call returns `NOT_RUNNING`. It also answers `resources/list` and
`resources/read` for `RESOURCES` (`kurooto://self`, `kurooto://manual`), read from files (`resource_text()`), so they
work while Kurooto is stopped. `command(persistent=True)` (used for agy's saved
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
folder, answer style, "nobody can answer follow-up questions", the tool rules (and, since 0.7.3, never to run commands or
scripts to look inside Kurooto), a pointer to `<state>/reserve/`, the
profile brief (`core/aboutyou.py`), "how to help me" (`modules/remember.py:help_brief`), the persona card and the
boundaries rule (`core/persona.py:card_text`, `rule`), the notes layout (`core/layout.py:describe`) and a line pointing
at `kurooto_self` / `reserve/self.md` for questions about Kurooto itself; a request about Kurooto
(`core/selfdoc.py:wanted`) also gets `self.md` itself in its context (`for_request`, at most `CONTEXT_MAX`). Chat's own
requests also end with one register line (`core/persona.py:register_line`, marked `[Reply style]`, left out of chat
history by `strip_register`).

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
