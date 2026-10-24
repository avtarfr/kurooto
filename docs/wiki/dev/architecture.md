# Architecture

Kurooto is one long-running Python process (the daemon) per user, plus short-lived CLI processes that talk to it, a
per-user Cloudflare Worker for phone calls, and an Android app. Everything the user has (settings, state, notes) stays
on their computer unless a feature they turned on says otherwise.

## The pieces

```
                      ┌──────────────────────────── the daemon (kurooto run) ─────────────────────────────┐
 Telegram Bot API ◀──▶│ modules/telegram  (background task: long polling)                                 │
                      │        │ Incoming                                                                  │
 Browser (127.0.0.1)◀▶│ web/server.py ── web/api.py, tools_api.py, live.py (SSE)                          │
 kurooto CLI ────────▶│        │                                                                           │
 kurooto mcp ────────▶│        ▼                                                                           │
                      │ App.handle ──▶ ask / replies / commands / skills / files / intents / Chat          │
                      │        │                                         │                                 │
                      │        │                                         ▼                                 │
                      │        │                          core/jobs.py (lanes you, bg, chk; worker threads)│
                      │        │                                         │ providers.build                 │
                      │        │                                         ▼                                 │
                      │        │                agy / Claude Code (subprocess) · OpenAI-compatible (HTTP)  │
                      │        │                    │ MCP: kurooto mcp ─▶ /api/tools/call      │ tool calls │
                      │        │                    └──────────────▶ core/tools.py:run_tool ◀──┘            │
                      │        ▼                                                                           │
                      │ app.notify ─▶ core/calm.py ─▶ core/notify.py ─▶ channels: telegram, app, desktop   │
                      │                                                                                    │
                      │ core/scheduler.py (asyncio task) ── actions registered by modules and core         │
                      │ core/power.py, core/presence.py (asyncio tasks)                                    │
                      │ modules/calls: Connector (background task) ──WebSocket──▶ Cloudflare Worker ◀──▶ phone │
                      └────────────────────────────────────────────────────────────────────────────────────┘
                      state: settings.json · secrets (keychain/file) · schedule.db · jobs.db · calm.db · events.jsonl
```

Startup (`daemon.py:run`):

1. `proc.ensure_user_path()`, `paths().ensure()`, `setup_logging()`.
2. Take the `daemon` file lock (`core/lock.py`, timeout 0; exit 3 "already running"), write `<state>/daemon.json`.
3. `App(p)` (`app.py:App.__init__`): core services, every catalog module, add-ons. See [core.md](core.md).
4. Small repairs: PATH (`core/pathfix.py`), launcher and service entries (`core/autostart.py:refresh`); remove
   `off.json`.
5. `asyncio.run(main())` → `serve(app, stop)`: `App.start()` (one-time upgrade steps, time-zone fix, updates, ask,
   presence, agent export, the reserve, each enabled module's `start()` and background task, health, calm, keep), then four
   tasks: `scheduler.run_forever`, `jobs.worker`, `power.watch`, `presence.watch`, plus the web server thread
   (`web/server.py:start`). Emit `started`.
6. On SIGINT/SIGTERM/SIGHUP (or Windows end-session): `presence.going_offline()`, cancel tasks, stop the web server,
   emit `stopped`; then `App.close()` (halt jobs, modules' `shutdown()`, close databases) and
   `daemon.end_children()` (`core/children.py:stop_all`). Exit 0, or 75 when an update asked for a restart.

Who starts the daemon: the launcher (`update/launcher.py`, installed in the app folder, started at sign-in by
`core/autostart.py`) runs `versions/<current>/.venv/... -m kurooto run` and restarts it on exit 75 or after a crash
(see [release-and-updates.md](release-and-updates.md#restart-and-rollback)). Without an installed launcher,
`kurooto supervise` (`daemon.py:supervise`) does the crash restarts. `kurooto start` (`cli.py:start_background`)
starts it detached.

Threads and the event loop: the asyncio loop runs the scheduler (handlers are called on the loop thread), the job
worker's polling, power, presence, every module's `background()` coroutine, and the call-line WebSocket. Blocking work
runs in threads: each AI job (`Jobs._start`, one thread per lane), each Telegram poll and update (two executors of their own, `Telegram._poller` and `_handlers`, since 0.7.3: the shared pool is busy with AI jobs and their tool calls, which once made a message wait 68 s before it was seen; `telegram_lag` in the event log notes any message seen over 10 s after Telegram took it), each
HTTP request (`ThreadingHTTPServer`), and the long scheduled jobs that start their own threads. Shared state is
protected by `threading.Lock`s inside each service and by file locks across processes.

## A message, end to end

What happens when the user types "what's due this week? and summarise my linear algebra notes" on Telegram.

1. **Telegram poll** (`modules/telegram/__init__.py:Telegram.run`, a `background` coroutine started by
   `App.start_background`): `getUpdates` long poll; for each update the offset is saved (`telegram/offset.json`), then
   `asyncio.to_thread(self._update, api, u, allowed)`.
2. **Filter** (`Telegram._update`): button taps from an allowed user go to `App.callback(data)`; messages must come
   from `telegram.allowed_users` in a private chat. While paused, they're queued to `telegram/paused.jsonl`. Files are
   downloaded into the notes inbox, voice notes transcribed (`modules/voice_notes.py`). A reply to one of Kurooto's
   messages is resolved through `telegram/map.json` into `reply_to = {"kind", "ref"}`. The result is an
   `Incoming(text, via="telegram", message_id, files, reply_to, voice, respond)` where `respond` sends straight back
   to this chat (`TelegramAPI.send`, replying to the message).
3. **Routing** (`app.py:App.handle`), first match wins:
   1. a reply to a question (`reply_to.kind == "ask"`) → `core/ask.py:Ask.reply`;
   2. a reply to a module's message → that module's `replies()[kind]` (the phone app's copy is retracted);
   3. `/start`, `/help`, `/aboutme`, `/persona`, `/q`, `/health`, `/fixme`, `/calm`, `/why`, `/keep`, `/inferred`, `/jobs`, `/forget`, `/egress` (core);
   4. a `/command` of an enabled module; a command of a disabled module answers "X is off: Features → X → Turn on"
      (except `ALWAYS = ("status",)`); a skill name when Skills is on (`modules/skills.py:Skills.typed`);
      (from here on, with Learns from its own work on, `Learning.heard` sees the text without taking it: "no, ..."
      soon after a skill's answer is a correction of that skill);
   5. files: a PDF captioned "book for <subject>" → Books; a `.kurooto-course` file → Class packs; otherwise the first
      enabled module with `take_files`;
   6. a text call in progress (`calls.textcall.takes`); then a request to decide the user's health, relationships or
      money (`core/persona.py:keeps`, rules) gets its one-line answer;
   7. a phrasing taught through the Wrong button (`modules/cases.py:Cases.watch`);
   8. **intents**, only when the text isn't `too_complex` (`modules/text.py`: long, or several requests in one): first
      an add-on classifier (`core/overlay.py:classify`), then each enabled module's `intents()` in catalog order; a
      text that looks like a question only goes to intents with `questions=True`. An intent emits `intent` and replies
      with its `run()` result. Instant, no AI. Requests, module commands, replies to a module's message and its
      buttons (`App.callback`) are counted per feature by `core/keep.py:Keep.used`. When none takes it,
      `core/repair.py:offer` may ask between two close readings, then `core/turnon.py:offer` for a feature that's off;
   9. "sync everything" or `/sync` (`core/syncall.py`);
   10. **Chat** (`modules/chat.py:Chat.ask`) if on; otherwise "turn on Chat".

   Our example has two requests in one message (`MULTI` matches "? and"), so `too_complex` sends it past the intents
   to Chat. "what's due this week?" alone would have been answered instantly by Deadlines' `show_due` intent.
4. **Chat** builds the prompt (with the last few turns if the conversation is under two hours old, and last the
   register line from `core/persona.py:register_line`), calls
   `app.jobs.submit(prompt, title, reply_to=message_id)`, remembers the job id in `Chat.mine`, and replies "On it."
5. **The queue** (`core/jobs.py`): the job is a row in `jobs.db` (status `queued`, lane `you`). The worker's next
   `_tick` claims it and runs `Jobs._run` in the lane's thread:
   - effort: `providers/effort.py:pick` ("summarise ... notes" matches `NOTES` → `high`);
   - the brain chain: `brain.main`, `brain.fallback`, a last resort, rearranged by free limits
     (`core/quota.py:Quota.arrange`);
   - the `Task`: prompt, effort, timeout (`brain.timeout_min.high`), the headless context
     (`providers/context.py:headless_context`), the tools (`core/tools.py:agent_tools`) and the MCP command
     (`core/mcp.py:command`) with its environment (`run_env`: the daemon's URL and tools-only key).
6. **The brain**:
   - agy or Claude Code: a subprocess in the notes folder (`core/proc.py:run`, or a PTY for agy). It starts
     `kurooto mcp` itself; each tool call travels `kurooto mcp` → `POST /api/tools/call` with `X-Kurooto-Tools`
     (`web/server.py:_tools_authed`) → `web/tools_api.py` → `core/tools.py:run_tool`. File access is limited by the
     per-brain allow-lists built from `core/places.py`.
   - an OpenAI-compatible API: `OpenAICompat.run` loops over function calls, calling `task.run_tool` →
     `core/tools.py:run_tool` directly in the daemon.
   Either way the tools are the same (`search_notes`, `read_note`, `read_file`, and the enabled modules' own, such as
   Deadlines' `add_deadline` or Reminders' `add_reminder`), and each use emits `tool_used` and goes into the request's
   tool log (`Jobs.note_step`; agent programs' uses carry the request's id from `KUROOTO_JOB`).
7. **Verdict and fallback**: the brain returns a `Result`; a retryable verdict moves to the next brain; the job row is
   updated (`ok` / `failed`), an `attempts` row added, `job_done` emitted.
8. **Delivery** (`Jobs._deliver`): `app.notify("[<brain> · high] <title>\n\n<answer>\n\n<run receipt>",
   kind="result", reply_to=<message id>, why="asked", tail=<run receipt>)` (the receipt, e.g. "agy · high · 2 min ·
   searched notes, wrote 1 note", is built in step 7 from the tool log; Telegram shows it in italics). `core/calm.py:Calm.decide` lets `asked` through untouched;
   `core/notify.py:Notifier._deliver` sends it to the Telegram channel (registered by `Telegram.start`), the phone app
   if `result` is in `notify.app_kinds`, the desktop if configured. A long answer is also attached as a file.
9. **After**: because `Chat.owns(job_id)`, the turn is appended to `chat/history.json`; the then-action, if any, runs
   (`Jobs._after`), then the watchers (`Jobs.watchers`, e.g. Learns from its own work) with the request's tool log.
   Notes sync, if on, schedules a push a couple of minutes after any `job_done`.

The same `App.handle` serves `kurooto ask` (`via="terminal"`, through `POST /api/say`), the setup page's try-it box
(`via="setup"`, `web/tryit.py`), routines (`via="routine"`), and the dashboard's Ctrl+K "ask". Calls take a different
path: the phone talks to Gemini Live directly and reaches the computer only for tools, transcripts and tasks (see
[calls-and-phone.md](calls-and-phone.md)).

## Something Kurooto does by itself

A reminder: `Reminders.add` books a one-off `reminders:<id>` job in `schedule.db`. At its time,
`Scheduler.tick` asks `Power.hold` (the reminder's module isn't heavy, so it runs) and the `respect` gate (none), adds
`late_s` if the laptop slept through it, and calls `Reminders._fire(payload)`, which calls
`app.notify(..., kind="reminder", why="reminders.own")`. Calm sees an exempt reason and records it; focus time would
queue it unless urgent; the notifier delivers it with snooze buttons. A tap comes back as `rem:<ref>:10` through
`Telegram._update` → `App.callback` → `Reminders.callbacks()["rem"]`.

## Scratch folders and proposals

Since 0.7.0 the AI may think, draft and write freely, but every change to the user's real files arrives as a proposal
(title, a few lines, the files, the diff) that only their tap applies. Two modules, both core:

- `core/scratch.py`: scratch folders, `<state>/scratch/<sid>/` with `scratch.json` (the `Scratch` dataclass), `work/`
  (what the AI may write) and, for a mirror, `base/` (each original as it was when first copied in). `create(app,
  origin, label, project=, checks=, lazy=, git_ok=)` makes a **git worktree** on a new branch `kurooto/<sid>` from HEAD
  when `origin` is a repository's top (`repo_top`), else a **mirror** that starts empty (`kind="files"`): `pull()`
  copies a file in on its first change (copy-on-write), `seed()` sets one from Kurooto itself (Dreaming's skill).
  `changes()` compares: a mirror with `difflib` against `base/` (or the original now, for files the AI made with its
  own tools), a worktree with `git add -A` and `git diff --cached --binary --full-index <base_commit>`; both drop keys
  and passwords (`SECRETS`, `secret()`), `.git` and `.kurooto`, and a mirror drops hidden files. `fingerprint()` /
  `audit()` name what changed in the original while the AI worked. `run_checks()` runs the project's check command in
  `sandbox()` (bubblewrap on Linux: read-only `/`, a tmpfs over Kurooto's state and config and the user's key folders,
  the scratch folder bound read-write, `--unshare-net`; macOS: `sandbox-exec` with a deny-network, write-only-here
  profile, untested; elsewhere none, so checks don't run). Every git call goes through `git()`, which sets
  `core.hooksPath` to an empty folder, no fsmonitor and no signing: nothing of the repository's runs.
- `core/proposals.py`: `submit()` queues a job with `scratch=<sid>` and the follow-up `proposal.make` (`job_done`);
  `make()` turns `changes()` into a record (`<state>/proposals/<pid>.json` and `<pid>.diff`), refusing past
  `proposals.max_kb` / `max_files`; `tell()` sends it (`why="asked"`, buttons `prop:<pid>:apply|change|discard`, the
  diff inline up to `proposals.inline_lines`, else as a file). Work nobody waits for (`lane != "you"`) is `night`: it
  isn't told one by one but in the morning (`morning_lines()`, in Dreaming's report, or `morning()` at
  `proposals.morning` when Dreaming is off, `why="proposals.morning"`). `apply()` is the guarded tap
  (`core/tap.py:GUARDED["proposal.apply"]`, ways typed and button): a mirror's files are checked unchanged since
  (`old_sha`), written atomically, and their earlier versions kept in `<state>/proposals/<pid>/before/` for `undo()`;
  a worktree's patch becomes one commit through a temporary index (`_commit`: `read-tree HEAD`, `apply --cached`,
  `write-tree`, `commit-tree --no-gpg-sign`, `update-ref` compare-and-swap on the current branch, then `checkout` of
  just those paths), refused for uncommitted changes in those paths, a detached HEAD or a merge in progress; never a
  push. Undo is the reverse patch as a revert commit. `change()` asks (hook `proposals.change`), `change_with()` runs
  the AI again in the same scratch folder with `pid`, and `job_done` updates the proposal (`rev`). `discard()` removes
  the folder. `cleanup()` (daily 04:20) expires proposals after `proposals.keep_days` and removes scratch folders
  nothing needs. `APPLY` / `UNDO` hold special Apply and Undo per `apply_hook` (Dreaming's `dream.skill`, which goes
  through Learning and the test-case replay: `core/tuning.py:wire`).

How the job is confined (`core/jobs.py:_run`): a job whose `scratch` column names a non-lazy scratch folder gets
`Task.cwd = Task.scratch = work`, `Task.reads = [origin]`, the context from `scratch.context()`, and its tools from
`core/tools.py:tools_for(app, job)`, which is `scratch.tools()`: everything that only reads (read_note and read_file
find the scratch copy first), and write_note, add_to_note, edit_note and delete_file writing in `work/` only (`locate()`
maps a path in the original to the same path in the scratch folder; anything else is refused with `block()`, recorded
in `Scratch.blocked` and the proposal), run_checks when the project has a check command. Every other writing tool is
left out. Per brain:

| Brain | How it's kept in the scratch folder |
|---|---|
| API brains (Gemini key, Ollama, others) | only Kurooto's tools exist for them, and those write only in `work/` |
| Claude Code | `providers/claude.py:permissions(app, task)`: `Edit` allowed for `work/**` only, `Edit` of the original and every usual write root denied, `Read` of `SECRETS` denied in every read root, no `mkdir`/`echo`, no agents.scripts, no GBrain server; given per run with `--settings` (its own settings files untouched) |
| agy | it runs with `work/` as its working folder and its Kurooto tools are confined (the MCP bridge passes `KUROOTO_JOB`; `web/tools_api.py` picks `tools_for(app, job)` for both the list and the call). agy's allow-list is one settings file for every run, so its built-in file tools keep their usual folders; `scratch.audit()` reports what changed in the original while it ran |

`kurooto mcp` (`core/mcp.py`) lists tools with `GET tools?job=<id>` so an agent program sees the confined set.

Ordinary requests: with `proposals.notes_edits` on, `tools_for()` wraps edit_note (`scratch.lazy_tools`): its first
change makes a *lazy* scratch folder of the notes for that job (`Scratch.lazy`, `jobs.set_scratch`), later reads of
that note find the copy, and the watcher `proposals.watch` turns it into a proposal when the job ends. Adding to notes
and new notes are unchanged.

### Making a feature produce proposals

1. Make a scratch folder: `sc = scratch.create(app, folder, "label", project=..., checks=...)` (or `git_ok=False` for a
   mirror even in a repository, as the notes do).
2. Either let the AI work in it: `proposals.submit(app, sc, prompt, title, reply_to=..., background=..., source=...)`;
   the job is quiet, and its answer (first line the title, then the summary) becomes the proposal, or a line saying
   why there's none. Or write the change yourself with `scratch.seed(sc, rel, new, old)` and call
   `proposals.make(app, sc, title, summary, source=..., night=...)` then `proposals.tell(app, p)` (or leave a night
   proposal for the morning).
3. A change that must be applied your way (through another feature) registers `proposals.APPLY[name] = fn(app, p, sc)
   -> (ok, message, undo_info)` and `proposals.UNDO[name]` (and `UNDO[f"{name}.discard"]`), and passes
   `apply_hook=name` to `make()`.
4. Never apply anything without the user's tap: Apply is `proposal.apply` in `core/tap.py`.

## Where to change what

| To change | Look at |
|---|---|
| how text is routed | `app.py:App.handle`, `modules/text.py` |
| a feature | its module in `modules/`, its tests, `docs/MANUAL.md` |
| which AI answers and how | `providers/`, `core/jobs.py`, `core/quota.py` |
| what the AI may touch | `core/places.py`, `core/tools.py`, `providers/agy.py:wanted_rules`, `providers/claude.py:permissions`, `core/scratch.py` |
| how the AI's changes reach your files | `core/scratch.py`, `core/proposals.py`, `modules/projects.py` |
| when messages arrive | `core/notify.py`, `core/calm.py`, `core/availability.py`, `core/presence.py` |
| scheduled work | `core/scheduler.py`, the module's `start()` |
| the dashboard | `web/`, `web/static/` |
| calls | `modules/calls/`, `data/worker/`, `android/` |
| installing and updating | `installer/`, `update/`, `tools/release.py`, `cli.py:install_finish` |
