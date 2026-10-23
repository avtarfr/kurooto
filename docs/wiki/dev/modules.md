# Feature modules

Every feature is a `Module` subclass (`src/kurooto/modules/base.py`). All of them are instantiated at startup
(`App.__init__` loops over `modules/catalog.py:CATALOG`), whether on or off; a feature is **on** when its id is in the
setting `modules.enabled`. Nothing is on by default.

What each feature does for the user is described in the user wiki ([../user/index.md](../user/index.md)); this page
is about how they are built.

## The Module class

Class attributes:

| Attribute | Meaning |
|---|---|
| `id` | the feature's id: its settings section, scheduler key prefix (`<id>:`), action prefix (`<id>.`), Calm reason prefix |
| `title`, `description` | shown on the feature card |
| `privacy` | one or two plain sentences: what leaves the computer and where it goes. The default is "Stays on this computer.", so a module that sends anything must override it |
| `requires` | ids of features that must be on first (`App.enable` refuses otherwise; `App.disable` refuses to turn off something another feature requires) |
| `extra` | True: an add-on that ships with Kurooto: in no preset, listed apart under Features, on only by hand (Exam season) |
| `heavy` | True: its scheduled work and background task wait for the charger in battery saver mode (`core/power.py`) |
| `processes`, `processes_intermittent` | program names or command-line fragments to show CPU and memory for on the dashboard |
| `defaults` | **not used**: nothing reads it. Register settings with `register_defaults` (below) |

Methods on the base class:

| Method | Default | Called by |
|---|---|---|
| `commands() -> [Command]` | `[]` | `App.handle` for `/name`; `help()`; the Telegram menu |
| `callbacks() -> {prefix: fn(ref, action) -> str}` | `{}` | `App.callback` for buttons `"<prefix>:<ref>:<action>"` |
| `replies() -> {kind: fn(msg, ref) -> str | None}` | `{}` | `App.handle` when the user replies to a message sent with `map_kind=kind` |
| `intents() -> [Intent]` | `[]` | `App.handle` for plain English |
| `help() -> [str]` | one line per command | `/help` |
| `ready() -> (bool, why)` | `(True, "")` | `App.enable`, the feature card, Chat |
| `start()` | nothing | at startup for every enabled module, and on enable |
| `stop()` | `scheduler.cancel_prefix(f"{id}:")` | on disable. Override with `super().stop()` |
| `health() -> (bool, why)` | `ready()` | `kurooto doctor` |
| `health_check() -> Check | None` | `core/health_checks.py:builtin(self)` | the daily health pass |
| `setting(key, default)` | | reads `<id>.<key>` |
| `every(name, spec, fn, payload=None, **kw)` | | registers action `<id>.<name>` and recurring job `<id>:<name>` |
| `action(name, fn) -> str` | | registers action `<id>.<name>` |

Optional hooks, found by `getattr`/`hasattr` where they are used:

| Hook | Used by | Purpose |
|---|---|---|
| `background(stop)` (async) | `App.start_background`, `App._guard` | a long-running task (Telegram polling, the call line, the study sampler). A crash emits `module_failed` and restarts it after 30 s |
| `setup(progress) -> (ok, msg)` | `web/api.py` (`modules/setup`), wizard | install or sign in what the feature needs; on success the feature is turned on |
| `setup_form()`, `configure(values)` | `web/api.py` | a form on the feature card |
| `card()`, `card_action(act, value)` | `web/api.py` | extra lines and switches on the card while on |
| `call_tools() -> [Tool]` | `modules/calls/__init__.py:Calls.tools`, `core/tools.py:agent_tools` | tools on calls **and** in unattended AI runs |
| `agent_tools() -> [Tool]` | `core/tools.py:agent_tools` | tools only for unattended AI runs |
| `call_brief() -> dict` | `Calls.pending` | what needs attention, for calls |
| `call_schedule`, `call_outcome`, `call_reschedule`, `call_transcript` | `modules/calls/__init__.py` | a feature that places calls hears what happened |
| `take_files(msg)` | `App.handle` | files sent without a command (the first enabled module that has it wins) |
| `shutdown()` | `App.close` | last steps when the daemon stops (Notes sync pushes) |
| `rest()` | `core/power.py` | release resources in battery saver (local models unload) |
| `sync_now()` | `core/syncall.py` | part of "sync everything" |
| `status_lines() -> [str]` | Telegram `/status` | extra status lines |
| `weekly_lines() -> [str]` | `modules/weekly.py` | lines in the weekly summary |
| `doctor_checks() -> [(name, ok, detail)]` | `diagnostics.py:more_checks` | extra doctor rows |
| `tunable` | `modules/retro.py` | settings the nightly look back may propose to change |
| `classify_intent(text, intents)` | `core/overlay.py:classify` | add-ons only: pick an intent before the built-in patterns |

Data classes (`modules/base.py`):

- `Incoming(text, via="telegram", message_id, files, reply_to, voice, respond)`; `msg.reply(text, buttons=None)`.
  `via` is `telegram`, `terminal` (`kurooto ask`), `setup` (the try-it box), `routine`, ...
- `Command(name, help, handler(msg, arg) -> str | None, usage="")`. Return the reply text, or `None` if you replied
  yourself.
- `Intent(name, description, match(text) -> dict | None, run(msg, slots) -> str, questions=False)`. `questions=True`
  lets it answer questions ("what's due?"); otherwise text that looks like a question goes to the AI.
- `Tool` lives in `modules/calls/tools.py` (see [brains.md](brains.md#tools-exposed-to-the-ai)).

## Lifecycle

```
App.__init__   cls(app) for every class in CATALOG         (no side effects here beyond registering
               overlay.load(app)                            actions/hooks that must exist even when off)
App.start      for each enabled module: m.start(); start_background(m)
App.enable(id) requires on? -> m.ready()? -> modules.enabled += id -> m.start() -> start_background(m)
               -> event module_enabled
App.disable    refuse if an enabled module requires it -> m.stop() -> stop_background(m)
               -> modules.enabled -= id -> event module_disabled
App.close      jobs.halt(); m.shutdown() for enabled modules; scheduler and jobs closed
```

Rules that follow from it:

- `__init__` runs for every feature, on or off, in tests and in CLI processes. Keep it cheap and free of I/O beyond
  setting attributes. Register in `__init__` only what must work while off: a scheduler action whose one-off jobs may
  outlive the feature being on (`Reminders.__init__` registers `reminders.fire`), a then-action whose job may finish
  after a restart (`Hints.__init__`).
- `start()` is called again whenever settings it depends on change in some paths (`modules/retro.py:_restart_owner`,
  health's `rearm` fix), so it must be idempotent: `scheduler.every` with the same key updates, `at(..., replace=False)`
  doesn't duplicate.
- `stop()` must call `super().stop()` (cancels `<id>:*` jobs), then undo anything else `start()` set up: hooks in
  `app.availability.blockers`, `app.ask.hooks`, `app.updates.holds`, notifier channels, event subscriptions.
  `modules/handwritten.py:Handwritten.stop` forgets the `super()` call and its scan keeps running after turn-off.
- Every scheduled action is called as `fn(payload)`. A method without a parameter fails on every run
  (`modules/space.py:Space.run_clean`, `modules/integrate.py:Integrate.tick/garden/summary` today). Write
  `def x(self, p=None)`.
- Long work in a scheduled action blocks the event loop: start a thread.

## Settings

Declare at import time, in the module's file, under the module's id:

```python
from kurooto.core.config import register_defaults

register_defaults("pomodoro", {
    "minutes": 25,          # how long one session lasts
    "nudge": "daily 09:00", # when to suggest the first one; "" turns it off
})
```

The comment on each line becomes the description in `docs/SETTINGS_GUIDE.md`; run
`python tools/gen_settings_guide.py` after changing settings (`tests/unit/test_settings_guide.py` checks it). The
dashboard's Settings tab shows every enabled module's section automatically, rendered by value type, and
`POST /api/settings` refuses a value whose type differs from the current one. Read with `self.setting("minutes")`.
Secrets go in `app.secrets`, never in settings.

## Messages, buttons, replies

- Send with `self.app.notify(text, kind=..., buttons=..., map_kind=..., map_ref=..., why="<id>.<reason>",
  setting=..., about=..., item=...)`. `why="asked"` for a direct answer to something the user just did.
- Every message that comes by itself needs a Calm reason: add an `R("<id>.<reason>", "plain words",
  setting="<id>.<key>", ...)` to `core/calm.py:REASONS` so Why? and Less of this work. See [core.md](core.md#notify-and-calm).
- Buttons: `[[("Label", f"{prefix}:{ref}:{action}")]]`, handled in `callbacks()[prefix]`; keep the data under 64 bytes.
- Questions with a hook: `self.app.ask.ask(text, choices=[...], hook="<id>.<name>", source=self.id)` and
  `self.app.ask.hooks["<id>.<name>"] = fn(q, answer)`.
- AI work: `self.app.jobs.submit(prompt, ..., then="<id>.<name>")` and
  `self.app.jobs.then_actions["<id>.<name>"] = fn(job, result, payload)` registered in `__init__` or `start()`.
  Background work: `background=True`, a `why`, and usually `quiet=True` with the then-action deciding what to say.
- Events: `self.app.events.emit("<id>_<what>", ...)`, ids and counts only.
- Notes: always through `core/layout.py` for paths and `core/tools.py:write_note_file` for writes; add to the user's
  notes, never reword or remove their text.

## A worked example

A minimal "Pomodoro" feature: a command, an intent, a scheduled nudge, a button, a tool, a Calm reason.

```python
# src/kurooto/modules/pomodoro.py
"""Pomodoro: "start a pomodoro" or /pomodoro starts a timed focus session; a message says when it ends."""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults("pomodoro", {
    "minutes": 25,           # how long one session lasts
    "nudge": "",             # e.g. "daily 09:00": suggest one then; "" for never
})

START = re.compile(r"^(start|begin) (a )?pomodoro$", re.I)


class Pomodoro(Module):
    id = "pomodoro"
    title = "Pomodoro"
    description = "Timed focus sessions: /pomodoro, or say start a pomodoro."
    requires = ("telegram",)
    # privacy stays the default: nothing leaves this computer

    def __init__(self, app):
        super().__init__(app)
        # the one-off "session ends" job may fire after a restart, so its action exists from the start
        app.scheduler.action("pomodoro.end", self._end)

    def start(self):
        spec = self.setting("nudge")
        if spec:
            self.every("nudge", spec, self._nudge)       # key pomodoro:nudge, action pomodoro.nudge

    # ---- what it offers
    def commands(self):
        return [Command("pomodoro", "start a focus session", lambda msg, arg: self.begin(arg))]

    def intents(self):
        return [Intent("pomodoro", "start a focus session",
                       match=lambda t: {} if START.match(t) else None,
                       run=lambda msg, slots: self.begin(""))]

    def callbacks(self):
        return {"pom": self._button}

    def call_tools(self):
        return [Tool("start_pomodoro", "Start a focus session for the user.",
                     lambda a: self.begin(a.get("minutes", "")),
                     {"minutes": arg("length in minutes; empty for the default")},
                     offline="queue", writes=True,
                     hint="When they ask to focus for a while, call start_pomodoro.")]

    # ---- the work
    def begin(self, minutes: str) -> str:
        m = int(minutes) if str(minutes).strip().isdigit() else int(self.setting("minutes") or 25)
        until = now() + dt.timedelta(minutes=m)
        self.app.scheduler.at(until, "pomodoro.end", {"minutes": m}, key="pomodoro:end", module=self.id)
        self.app.events.emit("pomodoro_started", minutes=m)
        return f"Focus until {until:%H:%M}."

    def _end(self, p: dict):                               # every action takes the payload
        late = " (late: the computer was asleep)" if p.get("late_s") or p.get("missed") else ""
        self.app.notify(f"Pomodoro done{late}.", kind="reminder", why="pomodoro.end",
                        buttons=[[("Another", "pom:x:again")]])

    def _nudge(self, p=None):
        self.app.notify("Start a pomodoro?", why="pomodoro.nudge", setting="pomodoro.nudge",
                        buttons=[[("Start", "pom:x:again")]])

    def _button(self, ref: str, act: str) -> str:
        return self.begin("") if act == "again" else "unknown button"
```

Then, to make it a real feature:

1. Add `Pomodoro` to `modules/catalog.py:CATALOG` and `"pomodoro"` to `web/api.py:MODULE_ORDER` (same position;
   `tests/unit/test_dashboard.py` checks the two lists match).
2. Add the Calm reasons to `core/calm.py:REASONS`:
   `R("pomodoro.end", "the end of a focus session you started", exempt="own", stop=None)` and
   `R("pomodoro.nudge", "a suggestion to start a focus session", setting="pomodoro.nudge", stop=to("", "no nudges"))`.
3. If it should be checked daily, add a `Check` in `core/health_checks.py` (or return one from `health_check()`).
4. Meet the [definition of done](conventions.md#definition-of-done): a page or section in the user wiki
   (`docs/wiki/user/`, and `commands.md` for the new command), the module reference below, `/help` (the `Command`
   help texts), a `CHANGELOG.md` line, the site pages; plus `docs/MANUAL.md` (with its undo), `docs/PRIVACY.md` if
   anything leaves the computer, and a regenerated `docs/SETTINGS_GUIDE.md`.
5. Tests, with the `env` fixture from `tests/conftest.py`:

```python
def test_pomodoro_starts_and_ends(env):
    env.on("pomodoro")
    assert "Focus until" in env.say("start a pomodoro")
    job = env.app.scheduler.get("pomodoro:end")
    env.app.modules["pomodoro"]._end(job.payload)
    assert "Pomodoro done" in env.fake.texts()[-1]
```

## How features are listed and turned on

- `modules/catalog.py:CATALOG` is the list of built-in classes (instantiation order; first-wins for duplicate tool
  names in `core/tools.py:agent_tools`).
- `web/api.py:MODULE_ORDER` is the order the wizard and the Features tab show; add-ons come after
  (`core/overlay.py:status(app)["modules"]`).
- `web/api.py:STARTER` (`telegram`, `chat`, `reminders`, `checkins`, `deadlines`) is the wizard's preset of ticked
  features. (Not to be confused with `providers/openai_compat.py:PRESETS`, which are AI services, or
  `core/layout.py:PRESETS`, which are notes layouts.)
- Turning on: `App.enable(id)` from the wizard (`POST /api/modules/enable`, or `modules/setup` which runs `setup()` and
  then enables), the dashboard, Google sign-in (which enables the Google parts that became ready), or
  `modules/google.py:GooglePart` `with_modules`.
- 0.5.8 changes: Attendance is gone. `core/upgrade.py:drop_retired` (called from `App.start`) turns a retired
  feature off on an install that had it, resets its settings and cancels its jobs; class packs keep accepting the old
  `attendance` keys and drop them. Exam season is an add-on that ships with Kurooto: `Module.extra = True` keeps a
  feature out of every preset (setup.js leaves it out of "Everything") and lists it apart on the Features page
  (`/api/state` sends `extra`).
- `extra` versus `addon`: `extra` is an optional feature that comes with Kurooto; `addon` is set by `core/overlay.py`
  on features loaded from the user's own add-ons folder.

## Add-ons (`core/overlay.py`)

The "Your add-ons" feature (`modules/overlay.py:AddOns`, id `overlay`, settings `overlay.path`, `overlay.code`) lays a
user's folder over Kurooto:

- `modules/*.py`: imported as `kurooto_addons.<name>` (files starting with `_` are helpers, imported by name). Every
  `Module` subclass defined in the file is instantiated; its `id` must match `[a-z][a-z0-9_]{1,39}` and not collide with
  an existing feature. Each is off until the user turns it on.
- `skills/<name>/SKILL.md`, `prompts/*.md`, `settings.json` (defaults between Kurooto's and the user's).
- `guard(app, m)` marks `m.addon = True` and wraps every method in `GUARDED` (commands, callbacks, replies, intents,
  help, call_tools, agent_tools, call_brief, classify_intent, status_lines, doctor_checks, health_check) plus `ready`,
  `health`, `start`, `stop`, `take_files`, so an exception is logged (`addon_failed`, shown by `/addons` and
  `kurooto doctor`) and the call returns a safe default.
- Extra hooks only add-ons get: `classify_intent(text, intents)` (runs before the built-in patterns, with
  `classify_timeout` seconds, default 2, at most 10; answers under `MIN_CONFIDENCE = 0.6` fall through).
- The folder can't be inside Kurooto's own folders (`inside_kurooto`), and updates never touch it.
- Turning add-ons on changes `core/places.py:write_roots` (their `skills/`), which makes agy's consent question appear
  again.

## Module reference

One line of purpose and the internals worth knowing. Commands are Telegram commands; "jobs" are scheduler keys
(full table in [core.md](core.md#every-scheduled-job)); state is under `<state>` unless noted.

### Channels and conversation

- **telegram** (`modules/telegram/__init__.py:Telegram`, `api.py:TelegramAPI`): the main channel. `background` long-polls
  `getUpdates` (timeout 50 s, `allowed_updates` message and callback_query), saving the offset to
  `telegram/offset.json` *before* handling each update (at-most-once). Back-off 5-120 s; 409 (another reader or a
  webhook) waits 30 s; 401 (revoked token) drops the `telegram` notifier channel until the module restarts. Pairing
  (`pair_start`, `pair_poll`): the token is checked with `getMe`, a one-hour code in a `t.me/<bot>?start=<code>` link,
  accepted only from a private chat; on success `telegram.chat_id` and `telegram.allowed_users = [from.id]`. Only
  `allowed_users` in a private chat are served; everyone else is ignored. While paused, messages go to
  `telegram/paused.jsonl` and are replayed by `replay_paused`. Files are downloaded into the notes inbox (20 MB
  Telegram download limit); voice goes to Voice notes. Sending: `api.send` splits at 3900 chars and sends at most 6
  parts (longer text is cut; the job queue sends answers over 7000 chars as a file too); files via `sendDocument`
  (captions 1000 chars, no buttons). No 429 handling. `telegram/map.json` maps sent message ids to `{kind, ref}` for
  replies (capped at 3000). The `/` menu is synced from enabled features (`_menu_tick`). Commands `/pause`, `/resume`,
  `/status`, `/hold`, `/calls`, `/focus`; intents `hold_calls`, `calls_ok`, `focus`. Settings `telegram.chat_id`,
  `allowed_users`, `silent_kinds`, `api_base` (tests point it at `tests/fakes/telegram.py`), `menu`.
- **chat** (`modules/chat.py:Chat`): free text that isn't a command or intent becomes a job (`Chat.ask`), and so does
  a file nothing else took (`App.route`): its paths are added to the prompt for an agent program to open (no caption:
  "say what it is"); with Chat off, the reply names what to turn on. Within two hours, the last six turns are
  prepended. `Chat.mine` / `Chat.owns(jid)`: only Chat's own jobs are recorded into
  `chat/history.json` (see [core.md](core.md#jobs)); the set is in memory, so an answer finishing after a restart isn't
  recorded. Commands `/new`, `/clear`, `/brain`, `/usage`.
- **cases** (`modules/cases.py`): the Wrong button on answers and a store of requests that fell through; a monthly
  review can turn one into a test case and teach a phrasing, only if the whole suite still passes. `cases/cases.json`,
  never backed up. `kurooto cases export` writes a pytest file.
- **voice_notes** (`modules/voice_notes.py`): `transcribe()` posts audio to Gemini `generateContent`; used by Telegram.
  18 MB limit.
- **library** (`modules/library.py`): `/note` into the inbox; `/prompts`, `/prompt` (the prompt library in
  `<notes>/prompts`).
- **remember** (`modules/remember.py`): "remember that ..." appended to `about-me/how-to-help-me.md` (health, money and
  credentials refused by `SENSITIVE`); `help_brief()` goes into every AI request's context.

### Time and attention

- **reminders** (`modules/reminders.py`): one-off `reminders:<id>` jobs (`reminders.fire`, registered in `__init__`),
  snooze buttons `rem`, cancel `remx`, tool `add_reminder`. `stop()` parks the pending jobs in
  `<state>/reminders-parked.json` before the base cancel, and `start()` sets them again (a time that passed while off
  fires at once with `while_off`, "late: Reminders was off"). Asks lidsafe whether the phone already said it. The
  plain-English intent reads the time with `modules/text.py:when_from`, which takes a weekday only where
  `text.WHEN_DAY` says it's the when ("friday at 5pm", "on friday"; "next friday" returns None, to the AI);
  `/remind` and `/due` use `core/clock.py:parse_when`, where a bare number is minutes.
- **checkins** (`modules/checkins.py`): evening/midday/night prompts by message or call, answers into the daily note;
  `checkins:plan` books the day's `checkins:<name>` jobs; call hooks `call_schedule`, `call_outcome`,
  `call_reschedule`, `call_transcript`. A check-in day starts at `checkins.day_starts` (05:00).
- **deadlines** (`modules/deadlines.py`): merges deadlines from manual entries, notes tasks, Classroom, the calendar,
  recurring quizzes and the term note; the hourly `deadlines:tick` chases them (24 h ping, 6 h call or urgent message,
  overdue check) and runs exam mode. Ids are hashes of title plus date. `deadlines.json` under the `deadlines` lock.
- **startby** (`modules/startby.py`): start-by dates from size estimates and free time; local arithmetic only.
- **exam_season** (`modules/exam_season.py`): one card for an exam period (update hold, alarm check, the eve question,
  leave-by alarm, debrief, no calls in exams, the Calm budget). Registers `app.updates.holds["exam_season"]` and an
  availability blocker; `budget_during_exams()` is read by Calm. An add-on since 0.5.8 (`extra = True`).
- **alarm** (`modules/alarm.py`, requires `calls`): the wake-up call is booked on the call line so it rings with the
  computer asleep; `alarm:plan` every 30 min; the morning plan drafted `prep_min` before; sets
  `app.availability.sleep`; mirrors to `reserve/alarm.md`.
- **lidsafe** (`modules/lidsafe.py`, requires `calls`): seals the next day's reminders for paired Android phones (s1)
  and hands them to the call line, so they arrive with the lid shut; whichever side is awake says each once.
- **awake** (`modules/awake.py`): holds a sleep inhibitor on mains power (`core/inhibit.py`).
- **calendar** (`modules/calendar.py`): iCal links (secret `calendar.ics`) and Google Calendar, recurrences expanded,
  private events masked; blocks calls during events, `#focus` and `#nocall`; `calendar:refresh` every 15 min. Each
  stored event has a `src` (`ics:<hash of the link>`, `google:<account>`); a source that fails keeps its rows from
  the last copy (`google_calendar.fetch` returns the failed accounts by name).
- **weekly** (`modules/weekly.py`): Sunday summary from `events.jsonl` and modules' `weekly_lines`; optional review call.
- **quests** (`modules/quests.py`): one onboarding quest a day for a week, judged from the event log.

### Study

- **subjects** (`modules/subjects.py`): subjects, timetable, holidays, exam periods, the term note
  (`modules/termnote.py` parser); a call blocker during classes; class packs layered under.
- **classpacks** (`modules/classpacks.py`, format in `modules/coursepack.py`): import/export a section's setup as a
  `.kurooto-course` file with a strict schema that refuses personal data.
- **capture** (`modules/capture.py`): after each class, a question about what was worth keeping; answers to the class log,
  a `study-log` skill job with Chat on.
- **doubts** (`modules/doubts.py`): a per-subject doubts list, sent before the next class.
- **quiz** (`modules/quiz.py`): spaced repetition over "must know" bullets in exam-prep notes; graded by the AI with Chat
  on; calls with Phone calls on. Tools `quiz_next`, `quiz_grade`, `schedule_quiz`.
- **hints** (`modules/hints.py`): a hint ladder for a problem, respecting a course's AI policy line.
- **study** (`modules/study.py`): minutes per subject from the focused window title (read and discarded), idle and lock
  aware (`core/idle.py`); Windows `GetForegroundWindow`, macOS System Events, Linux `hyprctl` / `swaymsg` / `xdotool`.
- **skills** (`modules/skills.py`): runs `SKILL.md` files (shipped `data/skills`, add-ons, prompts with `skill: true`,
  the user's own) as AI jobs; routines (`/every`), drafts (`/newskill`), LaTeX revision packs (Tectonic, `latexmk`,
  `pdflatex`), study packs, `send_file(s)` (over 50 MB goes to Drive upload).
- **books** and **integrate**: see [concept-graph.md](concept-graph.md).
- **handwritten** (`modules/handwritten.py`): transcribes PDFs and photos from an inbox folder (local vision model or
  Gemini) into Markdown.

### Notes, sync and safety

- **notes_sync** (`modules/notes_sync.py`): git add/commit/fetch/rebase (or merge keeping both)/push to a private GitHub
  repository; refuses public repos; the token is passed through `GIT_CONFIG_*` environment variables, never argv; never
  force-pushes; pushes a couple of minutes after AI jobs (`notes_sync:soon`). Shares the repo with the call line.
- **gbrain** (`modules/gbrain.py`): the GBrain notes index (Bun + PGlite) in `<data>/gbrain`, synced every 15 min;
  "external" mode for the user's own GBrain; shares the `gbrain` lock with backups.
- **local_models** (`modules/local_models.py`): installs Ollama and the models the hardware profile suggests; wires the
  helper model into `brain.models.ollama` and `brain.classify`; `rest()` unloads models on battery.
- **backups** (`modules/backups.py`): a daily zip of config, data and state (notes, secrets, the GBrain index optional)
  to a folder the user picks; SQLite copied with the backup API; `kurooto restore`.
- **profile** (`modules/profile.py`, crypto in `core/profile.py`): the setup, encrypted with the user's passphrase, on
  a branch of a private repository; restore on a new computer.
- **space** (`modules/space.py`): the Space keeper (see [core.md](core.md#space-keeper)).
- **overlay**: add-ons (above).

### Google

`modules/google.py:Google` is the sign-in hub (OAuth with PKCE through the user's own Desktop client; tokens in secret
`google.tokens[.<account>]`; redirect to `http://127.0.0.1:<port>/oauth/google`) and Classroom/Gmail drafts.
`GooglePart` subclasses each need their own scopes: **classroom_notes** (`google_classroom.py`, Classroom posts and
Drive files filed into notes by an AI job), **mail_digest** / **reply_drafts** / **digest_email**
(`google_mail.py`), **agent_plan** (`google_plan.py`, its own calendar of time blocks), **google_calendar**
(`google_calendar.py`, read-only), **drive_upload** (`google_drive.py`, resumable uploads; temporary uploads expire
after `drive_upload.temp_days`: `expire` deletes each as the account recorded with it, and only while the file's
`parents` still hold the Kurooto folder it went into; a moved, trashed or unknown-folder one is forgotten, not deleted). `google_confidential.py` is a helper for summarising confidential mail with a local
model. Any HTTP 401 is treated as a lost sign-in (the refresh token is dropped).

### Computer

- **calls**: see [calls-and-phone.md](calls-and-phone.md).
- **terminals** (`modules/terminals.py`): live PTYs behind the dashboard's Terminals tab (`UnixPty` via `os.openpty`,
  `WinPty` via pywinpty/ConPTY), 400 KB replay buffer, input 100 KB per request.
- **terminal** (`modules/terminal/`): Kurooto Terminal, a real terminal window (`kurooto term`): `plan.py` decides tabs,
  shell and terminal program; `kitty.py` (Linux, macOS) and `wt.py` (Windows Terminal fragment) draw it; `look.py`
  turns the palette into a terminal scheme; `launchers.py` adds app-menu entries; `defaults.py` (opt-in) makes it the
  default terminal and can undo exactly what it changed; `run.py` is the CLI.
- **research** (`modules/research.py`): a weekly papers digest (arXiv, bioRxiv, medRxiv, PubMed, feeds), daily
  project logs from git and `runs/`, and questions about idle projects. `papers()` collects with `mark_seen=False` and
  marks them in `research-papers.json` once delivered: right after the plain digest, or in the `research.digest`
  then-action when the AI-picked one succeeded.
- **retro** (`modules/retro.py`, requires `chat`): the nightly look back proposes setting, profile, skill and idea
  changes, each confirmed through `app.ask`; only settings in `TUNABLE` (and modules' `tunable`) may be proposed.
- **files** (`modules/files.py`): `take_files` for incoming files; with Chat on, an AI job files them.

Helpers that aren't modules: `modules/text.py` (time parsing, `too_complex`, `tidy`), `modules/daily.py` (the daily
note, `run_skill`, `morning_view`), `modules/termnote.py`, `modules/recurring.py`, `modules/coursepack.py`,
`modules/google_confidential.py`.

## Known problems (as of this writing)

- `modules/handwritten.py:Handwritten.stop` doesn't call `super().stop()`: `handwritten:scan` keeps running after the
  feature is turned off, and after a restart it is a `missing-action` (a `job_failed` event) every 15 minutes.
- `modules/space.py:Space.run_clean` and `modules/integrate.py:Integrate.tick` / `garden` / `summary` take no payload,
  so their scheduled runs fail (see [core.md](core.md#every-scheduled-job)).
- `modules/google.py:Google._draft` registers the `google.draft` then-action only when a draft is requested, so an
  AI-written draft whose job finishes after a restart is dropped.
- `modules/google.py:Google.api` and `modules/google_drive.py:DriveUpload._call` treat any HTTP 401 as a lost sign-in
  and delete the refresh token instead of refreshing once and retrying.
- `modules/telegram/__init__.py:Telegram.run` drops the `telegram` notifier channel on a 401 and only `start()`
  registers it again, so after a new token works, outgoing messages stay off until the module restarts. `api.send`
  sends at most 6 parts of 3900 characters and silently drops the rest; there is no 429 handling.
- `modules/telegram/__init__.py`: `telegram.focus_end` is registered only inside the `/focus` handler, so a restart
  during focus leaves `telegram:focus-end` as a `missing-action` and the focus queue isn't flushed at its end.
- `modules/chat.py:Chat.mine` lives in memory: an answer that finishes after a restart isn't recorded into the history,
  and `list(self.mine)[-50:]` keeps an arbitrary 50 ids rather than the newest.
- `modules/hints.py:policy_kind` tests "no solutions" before "no AI", so a policy line saying both is read as hints
  allowed.
- `modules/skills.py:compile_tex` passes `-no-shell-escape` to pdflatex but not to latexmk.
- `modules/classpacks.py`: `attendance_rules`, `attendance_rule` and `class_kind` have no callers once Attendance is
  removed.
