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
| `requires` | ids of features that must be on first (`App.enable` refuses otherwise; `App.disable` refuses to turn off something another feature requires). `"telegram"` means somewhere to talk: Telegram or the phone app's chat (`calls`), via `app.py:met` |
| `telegram_only` | `True` when `"telegram"` in `requires` means Telegram itself (Voice notes, Files into notes): the phone app doesn't stand in |
| `extra` | True: an add-on that ships with Kurooto: in no preset, listed apart under Features, on only by hand (Exam season, Learns from its own work) |
| `bundle` | the id of the add-on bundle it lives in (`"research_addon"`): no card or wizard entry of its own (`/api/state` sends `bundle`; home.js and setup.js leave it out), a switch on the bundle's card instead, and it comes on and goes off with the bundle |
| `heavy` | True: its scheduled work and background task wait for the charger in battery saver mode (`core/power.py`) |
| `processes`, `processes_intermittent` | program names or command-line fragments to show CPU and memory for on the dashboard |

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
| `dreaming_lines() -> [str]` | `modules/dreaming.py:loose_ends` | its own loose ends in the morning message (at most 2; an add-on's too, e.g. Night performance's "couldn't switch") |
| `weekly_lines() -> [str]` | `modules/weekly.py` | lines in the weekly summary |
| `doctor_checks() -> [(name, ok, detail)]` | `diagnostics.py:more_checks` | extra doctor rows |
| `tunable` | `modules/retro.py` | settings the nightly look back may propose to change |
| `classify_intent(text, intents)` | `core/overlay.py:classify` | add-ons only: pick an intent before the built-in patterns |

Data classes (`modules/base.py`):

- `Incoming(text, via="telegram", message_id, files, reply_to, voice, respond)`; `msg.reply(text, buttons=None)`.
  `via` is `telegram`, `terminal` (`kurooto ask`), `setup` (the try-it box), `routine`, ...
- `Command(name, help, handler(msg, arg) -> str | None, usage="")`. Return the reply text, or `None` if you replied
  yourself.
- `Intent(name, description, match(text) -> dict | None, run(msg, slots) -> str, questions=False, examples=(),
  guarded="")`. `questions=True` lets it answer questions ("what's due?"); otherwise text that looks like a question
  goes to the AI. `examples`: what you'd say, as `/help` shows it (each must be taken by `match`; a test checks).
  `guarded`: see [Never without a tap](#never-without-a-tap-coretappy). To answer with buttons (an Undo), `run` returns
  `Answer(text, buttons)` (`modules/base.py`, a `str`): `Incoming.reply` and Turn on's replier send its buttons, so
  every place that runs an intent keeps them. A command handler can return one too.
- `Tool` lives in `modules/calls/tools.py` (see [brains.md](brains.md#tools-exposed-to-the-ai)).

## Never without a tap (`core/tap.py`)

Setting or moving an alarm, placing a call, reading mail from a new sender, sending anything out, attaching a code
repository to a project and deleting the user's data happen only when the user asked (typed, said, on a live call) or
tapped. `core/tap.py:GUARDED` names each action (`alarm.set`, `call.place`, `mail.read`, `send.out`, `repo.attach`,
`addon.install` (adding or updating an add-on by link, official ones too: the terminal, a dashboard button or an
`oad:` button, never a tool or request),
`data.delete`), the ways that approve it (`WAYS`: `typed`, `said`, `call`, `button`, `approval`, `confirm`) and where it
happens.

When your code does one of these, tag it:

- a tool: `Tool(..., guarded="alarm.set")`. Outside a live call `run_tool` turns it into an Approve / Deny first
  ([brains.md](brains.md#tools-exposed-to-the-ai)). `guard_if=lambda a: ...` when only some arguments do it
  (`schedule_quiz` rings only by call); `asks=True` when the tool itself only asks (`draft_reply` drafts, and Send
  waits for the tap). The action must allow `call` (or `approval` with `asks`).
- a plain-English request: `Intent(..., guarded="call.place")`; its action must allow `said`.
- a command: nothing to tag (typing it is the request), but add it to `GUARDED[...].where`.
- a button: its prefix in `BUTTONS` (`"oad": "addon.install"`), and the action must allow `button`.
- a request that would do it: don't do it from the words; offer a button (`button` way) and act on the tap, as
  "set up my project from <repository>" does (`core/repoproject.py:intent` → `rpo:<token>:go`).
- anything that does it by itself (a schedule, `core/infer.py`, the look back): don't. Ask with
  `app.ask.approval(...)` and act in the hook.

The other side is `BY_ITSELF`: the data fixes the nightly look back makes without a tap, each told in one line with
Undo (`deadline.merge`, `Retro.fix_data`). A new one goes there first; `tests/unit/test_retro_records.py` checks that
none of them is a guarded action.

`tests/unit/test_tap.py` runs every tool (as on a call, and unattended via `ai`, `mcp`, `api`) and every request's
examples on Telegram with every feature on, with the guarded actions replaced by recorders (`Alarm.set`...,
`Calls.place/schedule/ring`, the `mail_digest.read`/`query` and `research.repos`/`projects` settings, Gmail's
`/send`, `retention.forget`, `ledger.forget`, `addons.install`). It fails when one reaches an action it isn't tagged with, when a tag's
way isn't allowed, or when an unattended run reaches one at all. A new guarded action: add it to `GUARDED`, its
recorder to the test's `hits` fixture, and the user wiki's table (talking-to-kurooto.md, "Never without your tap").

## /help and the command table (`core/commands.py`)

`/help` is made from the real command table: `CORE` (Kurooto's own commands, answered in `App.handle`), each module's
`commands()`, and each request's `examples`, in `GROUPS` (key, title, user wiki page, module ids, core names; `moved`
takes a command into another group, as Telegram's `/hold` and `/calls` go to Calls and phone). A module no group names
lands in `MORE`. `App.help_parts(arg)` returns the messages (each under `LIMIT` = 3900 characters), `App.help(arg)`
joins them: always the index (one line per group, from `_parts()`; since 0.6.0, as everything no longer fits one
message), packed by `_pack()` into as few messages as fit; `/help <group>`, `/help all`, `/help <word>`
(`find()`). Lines a module's `help()` adds that aren't one of its commands (Skills' `/<skill> …`) are kept.

Adding a command: give it a `help` line; a new feature goes into a group. Adding one to `App.handle` itself: add it to
`CORE` and to a group's `core`. `tests/unit/test_help.py` fails when a command registered anywhere (every module's,
every name `App.handle` compares with) isn't in `/help`, when a feature has no group, a group's page isn't in
docs/wiki/user, a message is too long, or an example isn't taken by its request.

## Tools a module offers

`Module.agent_tools()` (and `call_tools()` for live calls) return `Tool`s; `core/tools.py:agent_tools` gathers those of
every feature that's on, and `kurooto mcp` serves the same list. Since 0.7.3 the concept graph (`Integrate`) offers four
read-only ones (`graph_status`, `graph_search`, `concept_card`, `graph_links`; see concept-graph.md).

## Lifecycle

```
App.__init__   cls(app) for every class in CATALOG         (no side effects here beyond registering
               overlay.load(app)                            actions/hooks that must exist even when off)
App.start      for each enabled module: m.start(); start_background(m)
App.enable(id) requires on? -> m.ready()? -> modules.enabled += id -> m.start() -> start_background(m)
               -> event module_enabled -> m.turned_on() if it has one (a bundle enables its members)
App.disable    refuse if an enabled module requires it -> m.turned_off() if it has one and was on (a bundle
               disables its members) -> m.stop() -> stop_background(m) -> modules.enabled -= id
               -> event module_disabled
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

register_defaults(
    "pomodoro",
    {
        "minutes": 25,  # how long one session lasts
        "nudge": "daily 09:00",  # when to suggest the first one; "" turns it off
    },
)
```

This is the only way to declare settings (there's no `defaults` class attribute). Keep a comment on each line for
developers; what people read is the setting's entry in `tools/settings_guide/` (a tooltip and a guide entry, written
for a person: [core.md](core.md#setting-choices-and-tooltips-080)). Add it, then run
`python tools/gen_settings_guide.py` (`tests/unit/test_settings_guide.py` fails on a setting with no entry). The
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

register_defaults(
    "pomodoro",
    {
        "minutes": 25,  # how long one session lasts
        "nudge": "",  # e.g. "daily 09:00": suggest one then; "" for never
    },
)

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
            self.every("nudge", spec, self._nudge)  # key pomodoro:nudge, action pomodoro.nudge

    # ---- what it offers
    def commands(self):
        return [Command("pomodoro", "start a focus session", lambda msg, arg: self.begin(arg))]

    def intents(self):
        return [
            Intent(
                "pomodoro",
                "start a focus session",
                match=lambda t: {} if START.match(t) else None,
                run=lambda msg, slots: self.begin(""),
                examples=("start a pomodoro",),  # what /help shows; START must take it
            )
        ]

    def callbacks(self):
        return {"pom": self._button}

    def call_tools(self):
        return [
            Tool(
                "start_pomodoro",
                "Start a focus session for the user.",
                lambda a: self.begin(a.get("minutes", "")),
                {"minutes": arg("length in minutes; empty for the default")},
                offline="queue",
                writes=True,
                hint="When they ask to focus for a while, call start_pomodoro.",
            )
        ]

    # ---- the work
    def begin(self, minutes: str) -> str:
        m = int(minutes) if str(minutes).strip().isdigit() else int(self.setting("minutes") or 25)
        until = now() + dt.timedelta(minutes=m)
        self.app.scheduler.at(until, "pomodoro.end", {"minutes": m}, key="pomodoro:end", module=self.id)
        self.app.events.emit("pomodoro_started", minutes=m)
        return f"Focus until {until:%H:%M}."

    def _end(self, p: dict):  # every action takes the payload
        late = " (late: the computer was asleep)" if p.get("late_s") or p.get("missed") else ""
        self.app.notify(
            f"Pomodoro done{late}.", kind="reminder", why="pomodoro.end", buttons=[[("Another", "pom:x:again")]]
        )

    def _nudge(self, p=None):
        self.app.notify(
            "Start a pomodoro?", why="pomodoro.nudge", setting="pomodoro.nudge", buttons=[[("Start", "pom:x:again")]]
        )

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
  on features loaded from the user's own add-ons folder, and from add-ons by link (which also get `linked = <name>`).
- Bundles (0.6.0): an `extra` feature can group others. `modules/research_addon.py:ResearchAddon` is the Research
  add-on; a feature joins it with `bundle = "research_addon"` (and `extra = True`, and its id in `MODULE_ORDER` so
  `/api/state` knows it). `ResearchAddon.members()` finds them; `turned_on()` enables each one not in
  `research_addon.members_off`, `turned_off()` disables them; the card (`card()`/`card_action`) has a switch per own
  part (`run_compare`, `latex`: settings; `PART_SETTING` lets a part's switch be another feature's setting, none at
  present: the notation crosswalk runs with the concept graph and switches on its card) and per member (`m:<id>`: enables or disables it and keeps
  `members_off`). `core/commands.py:_footer` leaves bundle members out of /help's off list and counts the other
  `extra` features as "and N add-ons", so a new add-on doesn't push the one-message /help over Telegram's limit.

## Add-ons (`core/overlay.py`)

The "Your add-ons" feature (`modules/overlay.py:AddOns`, id `overlay`, settings `overlay.path`, `overlay.code`) lays a
user's folder over Kurooto:

- `modules/*.py`: imported as `kurooto_addons.<name>` (files starting with `_` are helpers, imported by name). Every
  `Module` subclass defined in the file is instantiated; its `id` must match `[a-z][a-z0-9_]{1,39}` and not collide with
  an existing feature. Each is off until the user turns it on.
- `skills/<name>/SKILL.md`, `prompts/*.md`, `settings.json` (defaults between Kurooto's and the user's).
- `guard(app, m)` marks `m.addon = True` and wraps every method in `GUARDED` (commands, callbacks, replies, intents,
  help, call_tools, agent_tools, call_brief, classify_intent, status_lines, dreaming_lines, doctor_checks, health_check)
  plus `ready`,
  `health`, `start`, `stop`, `take_files`, so an exception is logged (`addon_failed`, shown by `/addons` and
  `kurooto doctor`) and the call returns a safe default.
- Extra hooks only add-ons get: `classify_intent(text, intents)` (runs before the built-in patterns, with
  `classify_timeout` seconds, default 2, at most 10; answers under `MIN_CONFIDENCE = 0.6` fall through).
- What other features offer add-ons (0.8.12), each behind its own switch and never past a pause or a mute:

  | Feature | Call | What an add-on can do |
  |---|---|---|
  | Face presence | `watch_people(cb)`, `hold_watch(reason)`, `release_watch(reason)`, `owner_desk_height()` | see every face in view each frame (place, size, yaw, owner/unsure/stranger, its numbers in memory), keep the camera looking while the owner types, know how big the owner's face is at the desk (`face.addons.watch`, `face.addons.hold`; [face.md](face.md#hooks-for-add-ons-0812)) |
  | Voice | `say(text, wait=True)`, `listen_once(timeout_s)`, `guest_reply(text, name, history)` | speak a line, take the next stretch of speech (text, voice numbers, seconds; never sent anywhere), chat with someone the sealed guest way (`voice.addons.listen`, `voice.addons.chat`; [voice.md](voice.md#hooks-for-add-ons-0812)) |
  | Voice (0.9.0) | the add-on's own `guest_name() -> str` | name the guest in front of it for the ordinary guest path: a greeting by name made by Voice, the name to the guest's AI only when that's the local model (`voice.addons.guest_name`; [voice.md](voice.md#hooks-for-add-ons-0812)) |
  | Brain | `kurooto.mind.pest.met(app, quality)` | a small, capped reward for a conversation that went well (`mind.talk.met`; [mind.md](mind.md#the-talk-reward-i-3-talkpy)) |
  | Brain | `kurooto.mind.stimulation.feed(app, source, readings)` | report another device's sensors (light, proximity, accelerometer, gyroscope, compass, battery, its temperature, the room's loudness, being picked up, its screen) as raw numbers; each is felt on the body map as its physical analogue and drawn by the being's senses, in memory only (`mind.stimulation.addons`; [mind.md](mind.md#another-devices-senses-0812-stimulationfeed-mindstimulationaddons)) |

  An add-on that keeps anything about other people (a face's or a voice's numbers) does so on its own terms: it should
  ask them first, seal what it keeps (`core/biometric.py`'s stores) and delete it when asked.
- Playing Kurooto's voice elsewhere (0.8.12): `app.modules["voice"].add_output(fn)` in `start()`, and the returned
  `remove()` in `stop()`. `fn(pcm, sr, stop) -> bool` gets each spoken sentence instead of this computer's speakers,
  blocks until it has played (or `stop` is set) and returns False to let the speakers play it; details and threading
  in [voice.md](voice.md#outputs-playing-the-voice-elsewhere-0812).
- The folder can't be inside Kurooto's own folders (`inside_kurooto`), and updates never touch it.
- Turning add-ons on changes `core/places.py:write_roots` (their `skills/`), which makes agy's consent question appear
  again.

## Add-ons by link (`core/addons.py`, `core/fence.py`)

Someone else's add-on from a git address: `kurooto addons add <url> [--ref R]` (`cli.py:addons_run`) or the
dashboard's Features → Add-ons by link (`web/api.py:_addons_post`: `addons/look`, `add`, `check`, `update`, `drop`,
`remove`, `undo`, `reload`; GET `addons`). The same folder layout as "Your add-ons" (`modules/`, `skills/`, `prompts/`;
no `settings.json`), plus a manifest at the top:

```json
{"name": "weather-x", "title": "Weather X", "description": "...", "version": "1.0.0", "kurooto": ">=0.6.0",
 "license": "Apache-2.0", "homepage": "https://...",
 "features": ["weather_x"],
 "commands": [{"name": "weather", "what": "the weather now"}],
 "jobs": [{"id": "weather_x:hourly", "what": "checks every hour"}],
 "tools": [{"name": "weather_now", "what": "..."}],
 "hosts": ["api.weather.example", ".tiles.weather.example"],
 "programs": [{"name": "git", "online": true, "what": "..."}],
 "classify": false}
```

- **Fetching** (`fetch`): `check_url` takes `https://`, `ssh://`, `git@host:path`, `file://` or an absolute folder;
  `http://`, `ext::`/`fd::` transports and anything starting with `-` are refused. git runs with
  `GIT_TERMINAL_PROMPT=0`, `protocol.ext.allow=never`, `core.symlinks=false`, no submodules, into
  `<data>/addons/.staging/<token>`; the ref (`refs/tags/R`, `origin/R`, `R`; default `HEAD`) is resolved to a commit id
  and checked out detached. Symlinks, special files, over 2000 files or 50 MB are refused (`files`). The pending card
  waits under its token in `<state>/addons.json` for `PENDING_S` (an hour) with the tree's `digest`.
- **The card** (`card`, `card_text`): the manifest plus what the files say: `code` (modules/*.py), `skills`, `prompts`,
  size, and `warnings` (code without features, `classify_intent` without `"classify": true`, a Kurooto too old:
  `fits`).
- **Consent** (`install(p, token, yes, via)`): yes moves the staging folder to `<data>/addons/<name>` (an existing one is
  kept aside first) and records `{url, ref, commit, digest, manifest, added, updated, consent}`; the digest is checked
  again so files changed after the card was shown aren't added. The dashboard needs `code: true` (the box) when
  `runs_code`. Guarded as `addon.install` in `core/tap.py`.
- **Update** (`check_update`): a fresh clone of the same URL and ref (or `--ref`), `{"same": True}` when the commit
  didn't move; otherwise the card plus `changes()` (files added/removed/changed with line counts, and what's new on the
  card: hosts, features, commands, tools, jobs, programs, classify, code), then `install`.
- **Remove / Undo**: `remove` moves the folder to `<data>/addons/.kept/<name>-<stamp>` with its record; `undo` puts the
  last kept one back (after checking its digest), keeping the current one aside in turn. `KEEP` (3) per add-on.
- **Loading** (`core/overlay.py:load_linked`, called from `load`, and `reload_linked` after a change; `addons.on`
  false skips them): `addons.loadable` re-hashes each folder against the recorded digest (a change: "didn't load",
  shown by `/addons`, `kurooto doctor`'s `add-on <name>` rows and the reserve's `addons.md`). Each loads as the package
  `kurooto_linked.<name>` (fresh each load, helpers too: `from . import _helpers`), after `fence.add(...)`. `_modules`
  skips a feature id that isn't in `features`; `held(app, m, manifest)` sets `m.linked`, filters `commands()`,
  `agent_tools()`, `call_tools()` to the card (`"*"` in commands: any name, for commands the user names), wraps
  `every()` so only `<id>:<name>` jobs on the card are made, and drops `classify_intent` unless `"classify": true`.
  Anything left out is logged once as a problem. Their `skills/` count in `overlay.dirs(..., linked=True)` but never in
  `places.write_roots` (the AI writing there would break the digest).
- **The fence** (`core/fence.py`): an audit hook (`sys.addaudithook`, installed with the first fence, inert without
  one) on `socket.getaddrinfo`, `socket.connect`, `subprocess.Popen`, `os.exec`, `os.posix_spawn`, `os.spawn`,
  `os.system`, `os.startfile`. `_walk` goes from the innermost frame out, passing over library frames and
  `PASS` (`core/egress.py`, `core/proc.py`, `core/fence.py`): the first `kurooto.*` or `kurooto_addons.*` frame means
  Kurooto's own work (no fence); the first `kurooto_linked.<name>.*` frame means that add-on's card applies. A lookup
  of an undeclared host raises `egress.Fenced` (a `Blocked`, so an `URLError`/`OSError`) and is recorded as blocked for
  `add-on <name>`; an allowed lookup lets the thread connect for `WINDOW` seconds; an undeclared program (and always
  `os.system`/`os.startfile`) raises `fence.ProgramFenced` (a `PermissionError`). Requests through
  `egress.urlopen` are checked in `egress._check` the same way, in every `privacy.egress` mode. Programs marked
  `online` are counted as handed to them. Limits, said in the docstring: a thread started directly on a library
  function, ctypes, or an allowed program that goes online by itself get past it; it's a fence, the card and consent
  are the line.

The published ones' sources live in `addons/<name>/` (restic-backups, desktop-helpers, habits, handwriting-pull, and
night-performance), each with its manifest, README and
tests; `addons/conftest.py:load_addon` adds one by link in a test (a git repo made from
a copy), and `tests/unit/test_addon_packages.py` checks each loads with exactly its card and that the official list
matches the folders.

### Official add-ons (`core/official.py`)

`src/kurooto/data/official_addons.json` is the list, shipped in the package (so the release's signature covers it):
per add-on `name` (the manifest's), `title`, `line`, `needs`, `url` (its public repository), `tag`, `commit` (pinned),
`earlier` (commits pinned by older Kurootos) and `source` (`addons/<name>`). `test_addon_packages.py` checks names,
titles and that `tag` is `v` + the folder's manifest version.

- **Official** = `match(url, commit, name)`: the same repository (`_repo` folds `https://github.com/o/r`, `.git`, a
  trailing `/`, the ssh address and case into one spelling) at the pinned commit. `card()` stores it as
  `card["official"]` (the tag, or ""), `card_text` adds an "Official:" line, `listing()` adds `official` and
  `official_update`. Nothing is stored in the record: it's worked out from the list each time, so a fork, another
  commit or a newer list changes it.
- **Adding** (`fetch(p, word)`, `word` a name or the repository's name, `find`): `addons.fetch(p, url, tag,
  pin=commit)`: the clone checks out the pinned commit (the tag is the record's `ref`, a label), then the usual card
  and `install` with your yes.
- **Updates** (`update_for(rec)`): the record's commit is in the entry's `earlier` and isn't the pinned one. Then
  `addons.check_update(p, name)` (with no `--ref`) goes to the pinned commit with the tag as ref, with `changes()` as
  usual. `start(app)` (from `App.start`) schedules `offer` 2 minutes on when there's one to tell: one message through
  Calm (`why="addons.official_update"`, setting `addons.official_updates`) with a `Look: <title>` button per add-on
  (`oad:<name>:check`), once per pinned commit (`<state>/official-addons.json`).
- **Buttons** (`button(app, ref, act)`, routed from `App.callback`'s `oad` prefix, so they work with Your add-ons off):
  `oad:<name>:look` / `:check` fetch aside (`_aside`, a thread) and send the card as a message with
  `oad:<token>:yes` ("Add, I trust its code" when it runs code) and `oad:<token>:no`; `yes` is `install(..., via="button")`
  then `overlay.reload_linked`. `tap.BUTTONS` tags `oad` as `addon.install`.
- **Where it shows:** `/addons` and `/addons official` (`modules/overlay.py:_cmd`, an `Answer` with an Add or Update
  button per add-on: `official.buttons`), the dashboard (GET `addons` → `official`: `rows()` with `have` `""`,
  `official`, `update` or `other`; home.js `officialBlock`; POST `addons/look` `{official: name}`), the CLI
  (`kurooto addons official`, `add <name>` refusing `--ref`, the list's `official` marks).
- **A new version:** publish the folder to its repository, tag it, then in the JSON move `commit` into `earlier` and
  set the new `tag` and `commit` (`addons/README.md`).

## Module reference

One line of purpose and the internals worth knowing. Commands are Telegram commands; "jobs" are scheduler keys
(full table in [core.md](core.md#every-scheduled-job)); state is under `<state>` unless noted.

### Channels and conversation

- **telegram** (`modules/telegram/__init__.py:Telegram`, `api.py:TelegramAPI`): the main channel. `background`
  long-polls `getUpdates` (timeout 50 s, `allowed_updates` message and callback_query), saving the offset to
  `telegram/offset.json` *before* handling each update (at-most-once). Back-off 5-120 s; 409 (another reader or a
  webhook) waits 30 s; 401 (revoked token) drops the `telegram` notifier channel until `getUpdates` works again (a new
  token), then registers it again. Pairing (`pair_start`, `pair_poll`): the token is checked with `getMe`, a one-hour
  code in a `t.me/<bot>?start=<code>` link, accepted only from a private chat; on success `telegram.chat_id` and
  `telegram.allowed_users = [from.id]`. Only `allowed_users` in a private chat are served; everyone else is ignored.
  While paused, messages go to `telegram/paused.jsonl` and are replayed by `replay_paused`. Files are downloaded into
  the notes inbox (20 MB Telegram download limit); voice goes to Voice notes. Sending: `api.send` splits at 3900 chars;
  past `MAX_PARTS` (6) it sends the first 5 and a line saying the rest follows, then the whole text as `message.txt`
  (with the buttons), so nothing is cut (the job queue sends answers over 7000 chars as a file too); files via
  `sendDocument` (captions 1000 chars, no buttons). `telegram.focus_end` (the end of a `/focus`) is registered in
  `start()`. No 429 handling. `telegram/map.json` maps sent message ids to `{kind, ref}` for replies (capped at 3000).
  The `/` menu is synced from enabled features (`_menu_tick`). Commands `/pause`, `/resume`, `/status`, `/hold`,
  `/calls`, `/focus`; intents `hold_calls`, `calls_ok`, `focus`. Settings `telegram.chat_id`, `allowed_users`,
  `silent_kinds`, `api_base` (tests point it at `tests/fakes/telegram.py`), `menu`.
- **deadlines** call tools (0.5.8): `remove_deadline` (status "ignored" via `_button(id, "drop")`, never reopened by
  `_put`), `unignore_topic`; `upcoming()` leaves out exams already past; `full_title()` puts the subject's name in
  front of a bare title; `subject_of()` checks every folder of a path and the note's own name; `_put` renames an item
  when the same source finds it again under a fuller title.
- **chat** (`modules/chat.py:Chat`): free text that isn't a command or intent becomes a job (`Chat.ask`), and so does
  a file nothing else took (`App.route`): its paths are added to the prompt for an agent program to open (no caption:
  "say what it is"); with Chat off, the reply names what to turn on. Within two hours, the last six turns are
  prepended. `Chat.mine` / `Chat.owns(jid)`: only Chat's own jobs are recorded into
  `chat/history.json` (see [core.md](core.md#jobs)); the set is in memory, so an answer finishing after a restart isn't
  recorded. Commands `/new`, `/clear`, `/brain`, `/usage`.
- **cases** (`modules/cases.py`): the Wrong button on answers and a store of requests that fell through; a monthly
  review can turn one into a test case and teach a phrasing, only if the whole suite still passes. `cases/cases.json`,
  never backed up; cases that aren't test cases go after `cases.keep_days` (0: `privacy.keep_days`, via
  `core/retention.py:days`), and `Store.forget(lo, hi)` serves `/forget`. `kurooto cases export` writes a pytest
  file. `_rephrased(d)` runs after the first reply to an understood request: if the draft before it (same channel,
  `REPHRASE_S` 180 s earlier) was kept as a fallthrough, the case gets `rephrased`/`rephrased_to`; at
  `REPHRASE_TIMES` (2) cases with the same `norm` text and target it calls `teach()` (the replay gate applies) and
  notifies with Undo (Calm reason `cases.rephrased`, event `case_rephrased`). Setting `cases.learn_rephrased`.
  `repaired(text, target, means)` does the same for a reading picked in `core/repair.py` (kind `repair`,
  `repaired_to`; Calm reason `cases.repaired`), and `expected(text)` is a test case's target for a phrasing.
- **voice_notes** (`modules/voice_notes.py`): `transcribe()` posts audio to Gemini `generateContent`; used by Telegram.
  18 MB limit.
- **face** (`modules/face/`, 0.8.10): Face presence: YuNet and SFace (OpenCV, CPU) recognise the owner; enrolment
  and an honest "training" (centroids, a calibrated threshold), the watcher (camera closed while he types), a spoken
  greeting through `Voice.greet` and `Calm.speak_ok`, `/face`; never authorises anything. [face.md](face.md).
- **voice** (`modules/voice/`, 0.8.8): speaking (Kokoro or Piper) and listening on this computer; a local gate decides
  noise, chatter or addressed, and only addressed turns reach the brain through the portal. `heavy`; its listener is
  `background()`; parts fetched by `setup()` (`parts.py`). See [voice.md](voice.md).
- **library** (`modules/library.py`): `/note` into the inbox; `/prompts`, `/prompt` (the prompt library in
  `<notes>/prompts`).
- **remember** (`modules/remember.py`): "remember that ..." appended to `about-me/how-to-help-me.md` (health, money and
  credentials refused by `SENSITIVE`); `help_brief()` goes into every AI request's context. `keep(app, fact, via,
  section)` is the one path for a fact (Remember's command, intent and call tool, and Learns from its own work's
  facts); `remove_line()` takes a line Kurooto added out again, exactly as written (an Undo). Rechecking:
  `kept_lines()` is the dated `- fact (YYYY-MM-DD)` lines under `MANAGED` (`TOLD`, `PICKED`, `LEARNED`, the last
  now defined here and imported by retro) keyed by `fact_key()` (hash of `_norm`, so an edit is a new line);
  `Remember.recheck()` (`remember:recheck`, daily 18:30) seeds `seen` (from the line's date on the very first run,
  else now), marks `used` from `came_up()` (most content words) over your own requests (`Jobs.finished_since`, lane
  `you`, `learning.asked`) and the "You:" lines of transcripts since the last scan, `touch()` from `keep()` when a fact
  is said again, then sends at most one "Still true?" (`why="remember.recheck"`, `map_kind="recheck"`) for the line
  quiet longest past `remember.recheck_days`, at most `RECHECK_WEEK` (2) a week, `RECHECK_GAP_DAYS` (3) apart.
  Buttons `rck:<key>:keep|change|forget`, `rck:<undo>:undo`; replies (`recheck`): yes/no or the new wording,
  through `keep()`'s rules (`_change` → `_swap`). State `remember/recheck.json`.

### Time and attention

- **reminders** (`modules/reminders.py`): one-off `reminders:<id>` jobs (`reminders.fire`, registered in `__init__`),
  snooze buttons `rem`, cancel `remx`, tool `add_reminder`. `stop()` parks the pending jobs in
  `<state>/reminders-parked.json` before the base cancel, and `start()` sets them again (a time that passed while off
  fires at once with `while_off`, "late: Reminders was off"). Asks lidsafe whether the phone already said it. The
  plain-English intent reads the time with `modules/text.py:when_from`, which takes a weekday only where
  `text.WHEN_DAY` says it's the when ("friday at 5pm", "on friday"; "next friday" returns None, to the AI);
  `/remind` and `/due` use `core/clock.py:parse_when`, where a bare number is minutes. (0.9.0) `_addon_buttons(what)`:
  each enabled feature's `reminder_buttons(what) -> [(label, data)]` (an add-on's hook; `reminders.addon_buttons`)
  goes in a second row under the snooze row: at most `ADDON_BUTTONS` (2), a label cut at 30, data with a `prefix:`
  that fits Telegram's 64 bytes, answered by that feature's own `callbacks()`. A failing one emits
  `reminder_buttons_failed` (its id and the error's type) and is skipped.
- **checkins** (`modules/checkins.py`): evening/midday/night prompts by message or call, answers into the daily note;
  `checkins:plan` books the day's `checkins:<name>` jobs; call hooks `call_schedule`, `call_outcome`,
  `call_reschedule`, `call_transcript`. A check-in day starts at `checkins.day_starts` (05:00). `learn()`
  (`checkins:learn`, daily 12:00, `checkins.learn_times`) reads the last 14 days' plans (`<state>/checkins/<day>.json`;
  `answered_at` is written on a reply and on an answered call; a moved entry counts at its moved time), and with
  `LEARN_MIN_DAYS` answered and `LEARN_OFF_DAYS` 30+ min off on one side sets `checkins.times.<name>` to the median,
  rounded to 15 min; `<state>/checkins/learned.json` keeps from/to/at/undone; button prefix `chkl:<name>:undo`;
  events `checkin_time_learned`/`_unlearned`; Calm reason `checkins.learned`. A lighter day (`core/rhythm.py`):
  `_plan` moves the day's first check-in, when it's just been planned, `LATER_MIN` later (the entry keeps its own time
  under `lighter`; `learn()` skips such entries); `unlighten(day)` (Not today) puts it back unless you moved it since.
  The day's reflection (`checkins.reflect`): `_fire` adds `done_today(day)` and `TOMORROW` to the evening message and
  swaps Skip today for Not tonight (`chk:evening|<day>:not`, a skip with `via="not_tonight"`); the evening call script
  gets a "say these back" step. `done_today` reads records only, in this order, at most `REFLECT_N` (3), over the
  check-in day (`day_starts` to the next): deadlines with `status` done and `done_at` in the day (written by
  `_status`, `mark_done` and a ticked notes task), `threads.closed_between()` rows closed as done (not those keyed
  `deadline:`/`study:`, told from their own record), deadlines with `progress_at` in the day, study totals of
  `REFLECT_STUDY_MIN` (15) min or more per subject (one line), and classes whose after-class question is `answered`.
  Each part fails alone (`checkin_reflect_failed`). Nothing found: no list.
- **deadlines** (`modules/deadlines.py`): merges deadlines from manual entries, notes tasks, Classroom, the calendar,
  recurring quizzes and the term note; the hourly `deadlines:tick` chases them (24 h ping, 6 h call or urgent message,
  overdue check) and runs exam mode. Ids are hashes of title plus date. `deadlines.json` under the `deadlines` lock.
  The `add_deadline` tool (and the `deadline.add` action) takes an optional `course` (`subject`, its old name, still
  works): `Subjects.resolve()`, else the one subject `find_in()` names; unknown or naming two, the answer says so and
  lists the courses, and the item gets no subject from it (`subject_of()` on the title still applies).
- **deadlines** Photo to dates (0.6.0, `modules/photodates.py`, `deadlines.from_photos`): `App.handle` hands a
  message with a picture whose caption matches `photodates.WORDS` ("dates", "/dates", "timetable", "find the
  dates") to `start()` before the books and class-pack checks; `/dates` (a photo, or alone: `latest()`, the newest
  picture of `RECENT_S` 2 h from `calls/shared.json` (found again by name with `moved()` after the AI filed it) or the
  inbox) and the `photo_dates` intent ("dates from that photo") do the same; `calls._upload` does for a phone share
  whose note matches. `start()` refuses when `providers.sees()` says the main brain can't read pictures, else submits
  one quiet job with `images=[...]` and `then="photo_dates.ready"` (registered in `Deadlines.__init__`, so a late answer
  arrives). `ready()` parses the JSON (`parse()`), cleans it and offers it through `core/dateoffers.py`
  (`why="asked"`); `unreadable`, nothing found, a failure (one mentioning images says the AI may not read pictures):
  one line. `scan_calendar()` skips rows with `from` (a shared calendar's: offered instead).
- **deadlines** meeting brief: `meeting_briefs()` (`deadlines:meeting_brief`, `deadlines.meeting_brief` daily 20:00)
  takes open "Meeting: <who>" deadlines due tomorrow whose surname matches a project's `With:` person
  (`infer.projects_with`), then tomorrow's weekly `Meets:` meetings (`core/meetings.py:on_day(..., deadlines=False)`,
  once per note and day via `meetings.briefed()`, skipping a note briefed from a deadline), builds
  `infer.brief(note, who, due)` (Log lines dated on or after `Last met`, else two weeks; unchecked `## Next steps`;
  the newest `## Meetings` line; the newest minutes' first points), notifies once (`told` gets "briefed"; Calm reason
  `deadlines.meeting_brief`), then re-offers action items you said Later to (`meetings.offers_due()`). Items tapped
  from minutes are added with `source="meeting"`.
- **deadlines** progress: `PROGRESS` patterns and the `deadline_progress` intent/tool set `parts`/`parts_done` (and
  `progress_at`, for the evening reflection) on an
  open deadline found by `find_open()` (`similar()` on the title or the full title, the soonest due); `parts_text()`
  adds "(4/7)" to lists and the call brief; Start-by's `size_of()` scales `_whole_size()` by what's left.
  0.5.20: every change goes through `_record(i, done, total, plus)` (under the deadlines lock, so +1 taps merged from
  the phone outbox count in order), which keeps the replaced state in the item's `undo` (`_snapshot`: a 6-hex token
  `u`, `parts`, `parts_done`, `status`) and returns the Undo button `dl:<id>:undo<u>`; `_undo` refuses a token that
  isn't the latest. The reminder (`_tell`) and "Overdue?" message carry `map_kind="deadline"`, `map_ref=<id>`, so
  `replies()["deadline"]` (`_reply`) gets a reply on Telegram, the app's chat and the phone's Reply: `REPLY` reads
  "4/7", "4", "+1", "done" (`_done_by_reply`: the Done button's path plus `undo`, `ticked` for `_untick_note`);
  anything else is handed back to `App.handle` without `reply_to`. `_plus_button()` puts **+1** (`dl:<id>:+1`) first
  on those messages and `/deadlines` rows while parts remain; `core/notify.py:counts()` marks such a counting button
  (action starting "+"): `App.callback` doesn't retract its message and `PhoneApp._button` keeps the phone item open,
  so it can be tapped again; `PhoneChat._button` says the answer with the same button under it. `_row()` adds
  `parts` ("4/7"); `due_line()` / `due_day()` make "ps3 4/7, due Fri" for the wake-up call (`alarm.py`), `/status`
  (Telegram) and the morning page (`daily.morning_view`).
- **startby** (`modules/startby.py`): start-by dates from size estimates and free time; local arithmetic only.
  `learn_window()` (`startby:learn_window`, weekly sun 12:00, `startby.learn_window`) reads `message_in` events of the
  last 21 days (a day turns at 04:00), and with 7+ days of 3+ messages sets `startby.window` from the medians of the
  first and last, clamped and rounded to 30 min, when either end is 60+ min off; skipped when the user's own value
  isn't the last learned one. State `window_learned` in `startby.json`; Undo is `sby:window:undo`; Calm reason
  `startby.window`. Negotiate, don't repeat (`startby.negotiate`): `modules/deadlines.py:_chase` (ping, urgent,
  exam; `again` when "ping" was told before) and `call_outcome` (a missed call) call `_negotiate` →
  `offer_reshape(i, again)`, which needs `again` or a `told` date before today. `reshape(i)` runs `compute()` from
  today's window start with `pieces` (`allocate` records where each item's hours went), takes the hours placed
  today, and if what's left of today's free time × share is under them by more than 15 min, offers now (to the half
  hour, down) and the rest at tomorrow's first free slot, when that ends before the due time. `_take_offer` keeps one
  per deadline per day in `startby.json` `reshape` (`offered`, `done`, `declined`); buttons `neg:<id>:yes|no` →
  `reshape_answer` (yes: a one-off `startby:moved:<id>` → `_moved`, Calm reason `startby.moved`; blocks via
  `agent_plan.plan_block` when that's ready). The offer's Calm reason is `startby.negotiate`; call tools
  `reshape_plan`, `reshape_answer`. Events `startby_reshape_offered`, `_done`, `_declined`. Tests:
  `tests/unit/test_negotiate.py`.
- **exam_season** (`modules/exam_season.py`): one card for an exam period (update hold, alarm check, the eve question,
  leave-by alarm, debrief, no calls in exams, the Calm budget). Registers `app.updates.holds["exam_season"]` and an
  availability blocker; `budget_during_exams()` is read by Calm. An add-on since 0.5.8 (`extra = True`). Its
  `revision` part is `modules/revision.py` (not a module: `ExamSeason.revision`, a `Revision`, settings in
  `exam_season.*`): `topics()` reads the exam prep note's "Covered so far"/"Gaps" lines, else dated lecture notes, else
  concept notes (`integrate`'s `chapters.json`, the subject folder); `ranked()` sorts by `rank_key` (tier: no note,
  stub by `body_words() < STUB_WORDS`, weak recall `< WEAK`; then recall, course order), recall being the last grades
  of the topic's quiz items (`_items`: they name it or link its note) and its own last answer; `plan()` lays them with
  the pure `lay()` into `startby.slots()` less commitments and the exams (`minus()`), soonest exam first, at most
  Start-by's `size_of()` hours per exam; `reading()` lists the note, then `core/studypack.sources()` pages (class
  material first) and the concept graph's `seen.json` pages. The day's blocks are fixed in `revision.json` the first
  time (`today()`, also from the tick, the card and `StartBy.morning_rows/morning_lines`, which append them). The tick
  sends `ask()` once a day (Calm reason `exam_season.revise`); buttons `rv:<yyyymmdd>-<n>:y|p|n` go to `answer()`,
  which grades the quiz items through `Quiz.grade` and keeps their previous state for `undo()` (`Quiz.restore`).
  Commands `/revise`, intent "what should I revise today". Tests: `tests/unit/test_revision.py`.
- **alarm** (`modules/alarm.py`, requires `calls`): the wake-up call is booked on the call line so it rings with the
  computer asleep; `alarm:plan` every 30 min; the morning plan drafted `prep_min` before; sets
  `app.availability.sleep`; mirrors to `reserve/alarm.md`. Alarms you set are a list (`alarm-set.json`, `mine()`, at
  most `MAX_SET`); the scheduler holds one ring (`alarm:ring`), the soonest of that list and the daily alarm
  (`_plan`); `_ring` drops the one ringing, `call_schedule()` sends every one still to come (`upcoming()`) to the
  line, and `next_daily()` treats a morning with one of yours as had. `clear()` the next, `clear_at("HH:MM")`,
  `clear_all()` (the daily alarm stays). `script()` opens with the current local time and only asks about classes
  still to come. `suggest()` (`alarm:suggest`, every 30 min, `alarm.suggest`): within `SUGGEST_MIN` of the usual
  bedtime (`app.rhythm.usual_hours()`), with nothing in `upcoming()` or `next_daily()` up to 3 h past the usual wake,
  one message once per bedtime date (`<state>/alarm-suggest.json`), Calm reason `alarm.suggest`, buttons
  `alm:<YYYYmmddHHMM>:set` (calls `set()`) and `alm:suggest:no`; event `alarm_suggested`. It never sets one itself.
- **lidsafe** (`modules/lidsafe.py`, requires `calls`): seals the next day's reminders for paired Android phones (s1)
  and hands them to the call line, so they arrive with the lid shut; whichever side is awake says each once.
- **awake** (`modules/awake.py`): holds a sleep inhibitor on mains power (`core/inhibit.py`).
- **calendar** (`modules/calendar.py`): iCal links (secret `calendar.ics`) and Google Calendar, recurrences expanded,
  private events masked; blocks calls during events, `#focus` and `#nocall`; `calendar:refresh` every 15 min. Each
  stored event has a `src` (`ics:<hash of the link>`, `google:<account>`); a source that fails keeps its rows from
  the last copy (`google_calendar.fetch` returns the failed accounts by name). Shared class calendars (0.6.0):
  secret `calendar.shared` (`[{"url", "name"}]`), `subscribe()` / `unsubscribe()` (`/cal subscribe <link> as <name>`,
  `/cal shared`, `/cal unsubscribe`, or the setup card's `shared` and `shared_name` fields, which work without a link
  of your own); rows `src` `shared:<hash>` and `from` (the name, shown by `line()`); after each refresh
  `_offer_shared()` offers deadline- and exam-like entries (`deadlines.EXAMISH` / `DUEISH`) not offered before
  (`calendar-shared-offered.json`, the last 1000 keys) through `core/dateoffers.py`, one message per calendar, Calm
  reason `calendar.shared` (`calendar.shared_offer`).
- **weekly** (`modules/weekly.py`): Sunday summary from `events.jsonl` and modules' `weekly_lines`; optional review call.
  `weekly.people` (on) adds `core/meetings.py:week_line` (people from project notes only; see core.md, Meetings).
- **quests** (`modules/quests.py`): one onboarding quest a day for a week, judged from the event log.

### Study

- **subjects** (`modules/subjects.py`): subjects, timetable, holidays, exam periods, the term note
  (`modules/termnote.py` parser); a call blocker during classes; class packs layered under. Missed-class catch-up:
  `catch_up()`, job `subjects:catch_up` every 30 min; classes over today that were skipped or ended before
  `woke_at(day)` (the first `message_in`, `alarm_up_now` or `call_answered` after `checkins.day_starts`) get a
  `deadlines.add(..., source="catch_up", kind="task")` due at the course's next class and a lecture stub; state
  `subjects/catchup-<date>.json`; button `cup:<date>|<slug>:went`; Calm reason `subjects.catch_up`. With Classroom
  on (`google` with `google.classroom`, or `classroom_notes`), `google_classroom.posts_on(app, slug, day)` gives that
  day's posts of the courses filed under the subject (`classroom_notes.folders`, `classroom-notes/folders.json`, else
  `course_subject()`, the longest subject name in the course's name) from `classroom-posts.json`
  (`remember_posts`, called by `Google.classroom_sync` and `ClassroomNotes.fetch`); they end the message line and go
  under `## Classroom posts that day` in the stub. Each run, `_more_posts` rewrites that list in a stub still the size
  it was made (`size` and `posts` in the catch-up file), so posts that come later that day join it.
- **commitments** (`modules/commitments.py:Commitments`): `commitments.items` rows `{name, days, start, end, calls}`;
  `on(day)` gives a day's with `start_dt`/`end_dt` (an end before the start runs into the next day); the call blocker
  `commitments` checks yesterday's and today's (night shifts); skips per day in `<state>/commitments/skip-<date>.json`;
  `/busy` (add splits the words as the first split whose rest `parse_days` reads), intent `skip_commitment`, call tool
  `skip_commitment`, brief `commitments_today`. Distinct from Skills' `/every` routines. Hooks: `commitments.hooks`
  rows `{word, hold: "calls"|"all", minutes}`; intent `hook` (`questions=True`, since "when ..." reads as a question)
  takes `HOOK` ("when/whenever/if I say W, hold calls|everything N") to `add_hook`, a bad one (no length, no kind, a
  `NOT_HOOK` word) to a how-to line, and a message that is exactly a hook word (trailing `.`/`!` allowed, never `?`)
  to `fire_hook`: `set_quiet` (calls) or `set_focus` plus `telegram.focus_end` (all), keeping a longer hold already
  on. `/hooks`, `/hooks drop W`. Undo buttons `hook:<word>:unadd|undrop|unhold`; what they put back is in
  `<state>/commitments/hooks-undo.json`; `unhold` only acts while the hold is still the one the hook set. Telegram's
  `hold_calls` and `focus` intents skip `HOOK_SAID` so a hook sentence never holds now. Events `hook_added`,
  `hook_fired`, `hook_dropped`, `hook_undone` (no words). Never an alarm (`core/tap.py`).
- **subjects** short names from use (0.5.20): `short_names_used(text)` finds `SHORT` tokens (2-5 capitals, not
  `NOT_SHORT`, not resolving already) whose lower case is in exactly one subject's `initials()` (all words, without
  `MINOR` words, and without `ROMAN` numerals too); the first use is kept in `<state>/subjects-short-names.json`, a
  second within `SHORT_DAYS` (60) returns it (and forgets it) for `core/infer.py` to add with Undo.
- **deadlines** copies (0.5.20): `duplicates()` pairs open items due the same day with no source in common, compatible
  subjects, equal `NUM` sets and equal title words (less `STOP` and the subject's words); the kept one is the one with
  a source other than `manual`/`call`/`inferred`. `merge(keep, copy)` moves the copy's id and aliases into the kept
  one's `aliases` (`_resolve` finds it), joins `sources`, fills `subject`/`link`/`note`/`line`/`parts`, takes a known
  time over 23:59, cancels the copy's ring; `unmerge(undo)` reverses it.
- **classpacks** (`modules/classpacks.py`, format in `modules/coursepack.py`): import/export a section's setup as a
  `.kurooto-course` file with a strict schema that refuses personal data.
- **capture** (`modules/capture.py`): after each class, a question about what was worth keeping; answers to the class log,
  a `study-log` skill job with Chat on.
- **doubts** (`modules/doubts.py`): a per-subject doubts list, sent before the next class.
- **quiz** (`modules/quiz.py`): spaced repetition over "must know" bullets in exam-prep notes; graded by the AI with Chat
  on; calls with Phone calls on. `sources()` finds the notes with `md_files(root, keep)`: `rglob("*.md")`'s files in
  its order, without going into hidden folders (a notes folder's `.git` was walked twice per Study-pane request
  before 0.6.1) and building paths only for the names `keep` takes. Tools `quiz_next`, `quiz_grade`, `schedule_quiz`. Link recall cards
  (`modules/quiz_links.py:LinkCards`, `Quiz.links`): every `- relation:: [[target]] — reason` line between two concept
  notes (`conceptgraph.scan`) is a card in the quiz's own storage (`quiz/_links.json`, `Quiz.load` / `Quiz.grade`,
  so the same SM-2-lite spacing and history), with `a`, `b`, `relation`, `reason`, `names`, `subject` (from
  `integrate/seen.json`'s book key, else the note's folder) and `gone` for a link that's no longer there. Reply kind
  `qlink`, buttons `ql:<id>:<0|3|4|5>`; the reveal's "Where to read" is the `seen.json` pages of both concepts plus
  `sources.pick` over `sources.notes_material` (own notes, Classroom files). A reply from the phone app gets the grade
  buttons as a new message (`why="asked"`): the app's reply note can't carry buttons. `LinkCards.tick` (`quiz:links` at
  `quiz.links_at`, and `quiz:links:later` after a block) sends one with Calm reason `quiz.links` when `quiz.links` is
  on, fewer than `links_per_day` (capped at `MOST = 5`) came today, the last one was answered, and `busy()` (focus, a
  call, the night, any non-focus availability blocker such as a class) is clear. `quiz.links_check`: one sentence from
  the profile's helper model through `LocalModels.api("/api/generate")`, only with Local AI models on. `/card`
  (doesn't count toward the day), `/cards [on|off]`. Tests: `tests/unit/test_link_cards.py`.
  Since 0.6.0 `links()` also reads each subject's own notes (`course_notes()`: the subject folder and course page,
  Subjects on, not concept notes, not `books/`): `LINE` typed links, or `PLAIN` "- [[b]]: reason" lines whose reason
  passes `graphwrite.lint_reason` (relation "", asked "How does A relate to B?", revealed "A → B: reason"); the target
  must be a concept note (`conceptgraph.scan`, and `concept_like` for these), by slug or by bare name
  (`[[itos-lemma]]`). `subject_of()` maps a `seen.json` row whose `book` is an item key
  (`classroom:<hash>`, `handwritten:<hash>`) to that item's subject (`Integrate.items()`). `recent()`: concepts with a
  seen row from an item dated in the last `RECENT_DAYS` (14), and dated course notes from then; cards touching one
  carry `recent`, and `next_card` puts new recent cards before other new ones.
- **hints** (`modules/hints.py`): a hint ladder for a problem, respecting a course's AI policy line. Since 0.6.0
  `Hints.policy(slug)` reads the subject's `ai_policy` first (mapped to `CHOICES`), so a course set to `off` refuses
  without asking.
- **subjects** AI policy (0.6.0): a subject row in `subjects.list` may carry `ai_policy` (`POLICIES`: `allowed`,
  `hints`, `off`). `Subjects.ai_policy(slug)` returns it, else Hint ladder's course-note line mapped through
  `hints.policy_kind`, else `None` (treated as allowed); `set_ai_policy(slug, value)` validates through `POLICY_WORDS`
  and gives a term-note subject a row of its own. `/subject policy <s> [allowed|hints|off|clear]`; `/subject add` again
  keeps the policy. The dashboard's Study pane shows it (`study_view()["ai_policy"]`, action `subject.policy`).
- **drafts** (`modules/drafts.py`, Check my draft; `extra`, `bundle = "research_addon"`): `App.handle` calls
  `Drafts.take(msg)` before Books/Class packs/`take_files`: a message with files whose text isn't a request is
  remembered (`_recent`, in memory) and goes on; `CHECK` (`wants()`) with files, or with a file from the last
  `drafts.recent_minutes` (Telegram's `_recent`, the phone app's `calls/shared.json`), starts `check()`. `/check` does
  the same, and from `terminal`/`dashboard` takes a file path in the text (`_path_in`). A phone share whose note is a
  request goes straight to `check()` (`calls/__init__.py:_upload`). The course: `_course()` (named first, named once,
  the file's name, its subject folder, the class now or ended within 30 min, the only subject), else
  `app.ask.ask(..., hook="drafts.course")` (not from `terminal`). `_go()` refuses for `ai_policy == "off"`, then sends
  the shipped `check-draft` skill (`data/skills/check-draft/SKILL.md`) with the course, its policy (`POLICY_WORDS`),
  the course's lecture notes, and each text draft (`TEXT_TYPES`, up to `MAX_TEXT`) numbered (`numbered()`); other
  files go as paths. The quiet job's then-action `drafts.ready` (registered in `__init__`) parses `KIND`/`NOTE`/
  `SUMMARY` and `- where | cat | what` lines (`parse_check`), drops comments matching `REWRITE` (`tidy_comments`, which
  also cuts to the policy's length: `hints` keeps one sentence), and never passes on an answer in another form. Notes
  (a `.md` inside the notes, or `KIND: notes` with a course) get `graphwrite.put_block(..., "draft-check", ...)` in the
  sent note or the matching lecture note (the AI's `NOTE` if it's one of the course's lectures, else the best word
  match), checked by `guarded`. `via == "terminal"` sets `msg.job` and sends nothing (the dashboard's chat prints the
  answer). State `<state>/drafts/<id>.json` (last 100). Events `draft_check_started`, `draft_checked`,
  `draft_refused`. Tests: `tests/unit/test_drafts.py`.
- **study** (`modules/study.py`): minutes per subject from the focused window title (read and discarded), idle and lock
  aware (`core/idle.py`); Windows `GetForegroundWindow`, macOS System Events, Linux `hyprctl` / `swaymsg` / `xdotool`.
  Paper sessions (`/study la 50`), and Study mode's focus and break timer (`timer_start`, `timer_pause`, `timer_reset`,
  `_timer_end`; focus time through `core/availability.py`; see
  [web.md](web.md#the-today-page-and-actions-coreactionspy)).
  `/study mode on|off` and the `study_mode` intent call `core/actions.py:study_mode`.
  (0.9.0) `add_seen(slug, seconds)` for an add-on (`study.seen`): a known subject (or Research) and a number only,
  at most 600 s a call, refused while `session()` has a subject (sessions and the timer's focus); kept under
  `"<slug>|seen"`, so `totals()` counts it and `seen_seconds(days)` gives the line `report()` adds.
- **skills** (`modules/skills.py`): runs `SKILL.md` files (shipped `data/skills`, add-ons, prompts with `skill: true`,
  the user's own) as AI jobs; routines (`/every`), drafts (`/newskill`), LaTeX revision packs (Tectonic `--untrusted`,
  else `latexmk` or `pdflatex` with `-no-shell-escape`: the AI wrote the LaTeX), study packs, `send_file(s)` (over
  50 MB goes to Drive upload). A study pack (`_send_study_pack`) builds with `limit=None` when Drive upload is ready
  with `big_files`, or for `to="drive"` (the `study_pack` tool's `to`, whose result gives the zip's path in the cache's
  `study-packs/`, which `_sendable()` allows); `left_out_line()` counts `left_out` by reason (`studypack.OVER_ZIP`,
  `OVER_FILE`, else a book's page cap). Drive ready but `big_files` off and something left out for size: an
  `app.ask` question (hook `skills.pack_drive`, registered in `__init__`) whose yes rebuilds with `limit=None` and sends
  with `to="drive"` (0.8.13).
- **books** and **integrate**: see [concept-graph.md](concept-graph.md). Since 0.5.19 `integrate` also reads the
  Classroom files `classroom_notes` files (`ClassroomNotes._to_graph` → `Integrate.take_classroom`) and, with
  `"handwritten"` in `integrate.sources`, linked handwritten notes (`Linker.to_graph` → `Integrate.take_handwritten`),
  in one queue with the books: [concept-graph.md](concept-graph.md#sources-beyond-books-0519).
- **handwritten** (`modules/handwritten.py`): transcribes PDFs and photos from an inbox folder (local vision model or
  Gemini) into Markdown; `stop()` cancels its `handwritten:scan` job and halts a scan in progress. Then `modules/handwritten_links.py` (`Linker`, `hw.linker`) links the note like any other:
  `_file` calls `linker.submit(note, src)`, which works out when the pages were written (`written_times`: the PDF's
  CreationDate/ModDate, a stamp in the scan's name, the file's mtime) and the class by time (`class_for`: during a
  class ±10 min, else the last class that ended earlier that day, via `subjects.classes_on`), gets candidates from
  `conceptgraph.Index.candidates` (`integrate.index()` when the concept graph is on, else a keyword-only index), and
  queues one job (`lane="chk"`, brain = `integrate.roles()[1]` or `brain.main`, `then="handwritten.linked"`,
  registered in `__init__`). `Linker.done`/`apply` then: title (only when the heading still looks like the file name
  and nothing of the user's is above the marker), subject (a "during" class wins, else the AI's slug, else the class
  before), header (`aliases`, `tags`, `course:`), a `<!-- kurooto:linked -->` block right after the closing marker with
  `## Links` (lecture, course page, AI-picked concepts: must exist, `graphwrite.lint_reason`, confidence ≥ 0.5, at most
  12) and `## Doubts`, the course page's `<!-- kurooto:handwritten-notes -->` block (`graphwrite.put_block`, checked by
  `guarded`). `yours()` must be unchanged or nothing is written. Before-copies per run in `<state>/handwritten-undo/`
  (last 60; `/handwritten undo` restores only files still as written); `/handwritten link` (`link_all`) queues every
  transcription without a Links section as one batch (one message at the end), skipping ones already queued. State:
  `<state>/handwritten-links.json`. Tests: `tests/unit/test_handwritten_links.py`.

### Notes, sync and safety

- **notes_sync** (`modules/notes_sync.py`): git add/commit/fetch/rebase (or merge keeping both)/push to a private GitHub
  repository; refuses public repos; the token is passed through `GIT_CONFIG_*` environment variables, never argv; never
  force-pushes; pushes a couple of minutes after AI jobs (`notes_sync:soon`). Shares the repo with the call line.
- **gbrain** (`modules/gbrain.py`): the GBrain notes index (Bun + PGlite) in `<data>/gbrain`, synced every 15 min;
  "external" mode for the user's own GBrain; shares the `gbrain` lock with backups. `run()` refuses `doctor` without
  `--no-migrate` (any brain) and anything outside `EXTERNAL_OK` on an external one (`doctor` and `find-contradictions`
  are in it). `nightly()` first writes course pages (`gbrain.course_pages`: `modules/coursepages.py:write_all`, its
  key in the result only when a page changed), then timelines or the upkeep. The weekly job is `weekly()`:
  `health_line()` (`gbrain.checkup_line`: `doctor --json --no-migrate --scope=brain`, `brain_checks_score` and the
  first non-ignored warn/fail check, preferring its `top_issues` fix; event `gbrain_checkup_line`; Calm reason
  `gbrain.checkup_line`; "" when busy) and `checkup(line)` (the advisor; its message starts with the line, so one
  message). `contradictions()` (`gbrain.contradictions`): `find-contradictions --json --limit 20`, which only reads
  the last stored probe run (Kurooto never runs `eval suspected-contradictions`), keeping `verdict == contradiction`
  and severity above `low`; read by `modules/consolidate.py:gbrain_pairs`. `call_tools()`: `note_timeline` with a
  call hint (search_notes, which `Calls._search` already routes to `GBrain.search`, says "by meaning" when it's on).
- **coursepages** (`modules/coursepages.py`, not a feature): `write_all(app)` gives each subject's course page one
  `graphwrite.put_block` block, key `course-overview` (`## <Name> at a glance`, classes from `Subjects.timetable()`,
  `### Key concepts` = `conceptgraph.scan` notes the subject folder's notes link to most, own pages and dated lecture
  notes left out, up to 10, and `### Timeline` = `- **YYYY-MM-DD** | lecture|deadline|exam|term note — ...` lines in
  GBrain's timeline format, ±120 days, at most 40 nearest today). A missing page is made with the layout's
  frontmatter; an existing one is written only when `graphwrite.guarded` holds. Event `course_pages` (`changed`).
  Tests: `tests/unit/test_gbrain_more.py`.
- **local_models** (`modules/local_models.py`): installs Ollama and the models the hardware profile suggests; wires the
  helper model into `brain.models.ollama` and `brain.classify`; `rest()` unloads models on battery.
- **backups** (`modules/backups.py`): a daily zip of config, data and state (notes, secrets, the GBrain index optional)
  to a folder the user picks; SQLite copied with the backup API; `kurooto restore`. The memory ledger (`LEDGER`) only
  with `backups.memory` (`sources(memory=)`); it opens only with its key, which `backups.secrets` carries. Only
  regular files go in (`_plain`: a named pipe, socket or device is skipped; reading an add-on's pipe never ends), and
  the scheduled `run` and `catchup` are `thread=True` (0.8.13: before, a backup held the daemon's loop for its whole
  length, and a pipe in state froze Voice and Face).
- **profile** (`modules/profile.py`, crypto in `core/profile.py`): the setup, encrypted with the user's passphrase, on
  a branch of a private repository; restore on a new computer.
- **space** (`modules/space.py`): the Space keeper (see [core.md](core.md#space-keeper)).
- **overlay**: add-ons (above).

### Google

`modules/google.py:Google` is the sign-in hub (OAuth with PKCE through the user's own Desktop client; tokens in secret
`google.tokens[.<account>]`; redirect to `http://127.0.0.1:<port>/oauth/google`) and Classroom/Gmail drafts.
`GooglePart` subclasses each need their own scopes: **classroom_notes** (`google_classroom.py`, Classroom posts and
Drive files filed into notes by an AI job; each `queue()` is a run in `classroom-notes/runs.json` (`left` batches,
`filed` titles): `_filed` reports back with `_run_back` and the run's one message (`_tell_filed`, `LIST_MAX` titles)
goes when nothing is left; a failed batch leaves its run and joins the next one, and a run older than `RUNS_DAYS` is
let go at the next `queue()`), **mail_digest** / **reply_drafts** / **digest_email**
(`google_mail.py`; Email in, 0.6.0, is `mailin.py`: `mail_digest.mail_in` (off), `mailin.check()` every
`mail_in_every` asks Gmail for `deliveredto:/to:` the `+kurooto` address or `label_query(mail_in_label)`, takes mail
to +kurooto only from `me` or `mail_in_senders` (others aren't even fetched; `mail_in_anyone` overrides), applies
`blocked()` and the confidentiality check, and submits one text-only `lane="bg"` job per mail (`PER_CHECK` 10,
`then="mail_digest.mail_in_done"`); `done()` writes a new `note`-kind note (summary, Gmail link, the text; never
over another) and offers the dates via `core/dateoffers.py`, Calm reason `mail_digest.mail_in`; state
`mail-digest/mail-in.json` (`since`, `seen`); `/mail in [on|off|label|from|unfrom]`), **agent_plan** (`google_plan.py`, its own calendar of time blocks; each event's
`extendedProperties.private` carries `item` (the deadline id it's for, given or found by `source()`: `similar()` on the
full title, same subject, due from the day before on) and `due` (that one's due date then); `plan_block(..., item,
due=, shift=, check=)` refuses a block whose item `_over()` says is done, dropped or an exam that's over, and with
`shift` (the call tool and `/blocks add`) moves an overlapping one to the first free time before `LATEST_H` or
refuses, saying which; `reschedule(start, by, order)` takes today's blocks and tonight's past midnight
(`_tonight`), drops the ones `_over()` (also a due moved past `deadlines.plan_h` since planning), orders the rest with
`_arrange` (`order`'s parts first, matched by `words()`, then blocks with an item soonest due in the slots they held;
not for a `by` push), keeps lengths and gaps up to `GAP_MAX`, deletes what doesn't fit before `LATEST_H` and names it
and `_unplanned` items due within a day; `remove_blocks(what, after)`; `undo` (with `uid`, for the `apl:<uid>:undo`
button) in `agent-plan.json`, used by `/blocks undo` and the `undo_plan` tool; intent `reschedule_day`, call tools
`plan_block`, `reschedule_day`, `remove_blocks`, `undo_plan`), **google_calendar**
(`google_calendar.py`, read-only), **drive_upload** (`google_drive.py`, resumable uploads; temporary uploads expire
after `drive_upload.temp_days`: `expire` deletes each as the account recorded with it, and only while the file's
`parents` still hold the Kurooto folder it went into; a moved, trashed or unknown-folder one is forgotten, not deleted). `google_confidential.py` is a helper for summarising confidential mail with a local
model. An HTTP 401 from an API drops the access token and tries once more with a new one (`Google.api`,
`DriveUpload._call`); only `invalid_grant` when renewing it is a lost sign-in (`_lost_signin` drops the refresh token).
Then-action `google.draft` (an AI-written `/draft`) is registered in `start()`, so one finishing after a restart
arrives.

### Computer

- **calls**: see [calls-and-phone.md](calls-and-phone.md).
- **terminals** (`modules/terminals.py`): live PTYs behind the dashboard's Terminals tab (`UnixPty` via `os.openpty`,
  `WinPty` via pywinpty/ConPTY), 400 KB replay buffer, input 100 KB per request.
- **terminal** (`modules/terminal/`): Kurooto Terminal, a real terminal window (`kurooto term`): `plan.py` decides tabs,
  shell and terminal program; `kitty.py` (Linux, macOS) and `wt.py` (Windows Terminal fragment) draw it; `look.py`
  turns the palette into a terminal scheme (a named theme's dark flavour from `core/palette.py:role_map`); `launchers.py` adds app-menu entries; `defaults.py` (opt-in) makes it the
  default terminal and can undo exactly what it changed; `run.py` is the CLI.
- **research** (`modules/research.py`): a weekly papers digest (arXiv, bioRxiv, medRxiv, PubMed, feeds), daily
  project logs from git and `runs/`, and questions about idle projects. `papers()` collects with `mark_seen=False` and
  marks them in `research-papers.json` once delivered: right after the plain digest, or in the `research.digest`
  then-action when the AI-picked one succeeded.
  Since 0.7.0 `start()` also schedules `research:repo_refresh` (`repo_projects.refresh_at`, when
  `repo_projects.refresh`) → `core/repoproject.py:refresh`; `setup_form`/`configure` take an optional `repo` (started
  with `repoproject.start`), and `view()` lists `repo_projects` for the Research tab, whose **Add a project from a
  repository** posts `/api/research/project`. Projects from repositories themselves are core:
  [core.md](core.md#projects-from-repositories-corerepoprojectpy).
- **research_addon** (`modules/research_addon.py`, `extra`, `heavy`): the Research add-on bundle (see "How
  features are listed and turned on"). Run compare is `kurooto/runcompare.py` (no App needed, so `kurooto runlog
  diff` runs it from `runlog.main` with `for_this_install()`; it refuses unless `research_addon` is on and its
  `run_compare` part isn't off: `runcompare.on(settings)`): `all_runs` (runlog's state, then `<repo>/<research.repo_runs>`
  folders), `find` (id, unique start or end, or the /runs number), `config_diff` over `flat` configs, `code_diff`
  (read-only `git diff`/`rev-list`/`cat-file` between `meta.commit`s, in the repository `meta.cwd` is in; capped at
  `CODE_DIFF_MAX`), `metric_rows` (last, lowest, change; `meta.last` when there's no metrics.jsonl), `curves_png`
  (matplotlib with Agg when `has_matplotlib()`) or `spark_table`. `compare()` writes
  `runs/compare/<A>--<B>.md` as one `run-compare` block (`core/graphwrite.py:put_block`, `guarded`) and keeps the
  project note's `run-compare` block to the last `KEPT` lines. The LaTeX tracker is `modules/latex_tracker.py`:
  `Tracker.attach` (only from `/latex add`, typed: `core/tap.py` `repo.attach`; `tests/unit/test_tap.py` watches
  `research_addon.latex_repos`), `build` (Tectonic `--untrusted --keep-logs --outdir <cache>/latex/<key>`, else
  `latexmk -norc ... -no-shell-escape` or `pdflatex` with `skills.TEX_ENV`; never writes into the user's folder),
  `parse_log` (joins TeX's 79-column lines; `! ` errors with `l.N`, Tectonic's `error: file:line:` lines, LaTeX,
  natbib and biblatex undefined references and citations, BibTeX's `.blg`), `count_words` (`tex_files` follows
  `\input`/`\include`/`\subfile` inside the folder; `prose` drops the preamble, comments, maths and commands). State is
  `research-latex.json`: per folder `words` by day (`KEEP_DAYS`), `last`/`prev` builds, a build counter `n` and
  `reported` (the morning line tells each build once), and `_pending` (button refs for missing citations). Jobs:
  `research_addon:latex` (`latex_when`) and `research_addon:morning` (`latex_morning`, `respect="quiet"`, Calm reason
  `research_addon.latex`). Buttons `rlx:<ref>:bib` (submits a quiet text-only job with then-action
  `research_addon.bibtex`; needs Chat), `rlx:<ref>:add` (`latex_tracker.add_entry` appends to the first existing `.bib`
  the document names, never twice), `rlx:<ref>:no`.
- **research** Zotero (0.6.0, `modules/zotero.py`, `Research.zotero`): `Zotero.way()` is `app` (the connector at
  `LOCAL` answers `/connector/ping`), `web` (a key in `research.zotero_key`, the secret named by `KEY_NAME`) or `""`, by
  `research.zotero`. The digest keeps its papers by `ref_of(id)` in `<state>/research/digest-papers.json` (last 400) and
  the numbered ones in `digest-last.json`; `zotero_buttons()` adds `zot:<ref>:add` rows (at most 8) when `way()` isn't
  empty. The AI-picked digest is then submitted `quiet` and `_digested` sends it itself with buttons for the papers
  whose links it names (and its receipt); a failure says so with `why="research.papers"`. A tap runs `add_later` (a
  thread): `_web_add` (`/keys/current` for the user id, cached in `research/zotero.json`; `POST /users/<id>/items` with
  a `Zotero-Write-Token`) or `_local_add` (`/connector/saveItems`, then the item key from the local API
  `/api/users/0/items?q=`, else none). `items` in `research/zotero.json` stops a second add. `link_notes()` (after an
  add, and job `research:zotero_links` daily 04:40 in a thread) puts a `zotero` block with `zotero://select` links in
  every note (up to `MAX_NOTES`) whose own text has a paper's link, arXiv id or DOI (`_needles`). `/zotero`,
  `/zotero key <key>|off` (checked: write access), `/zotero <n>`, `/zotero links`; Research's setup form takes the key.
  Host `api.zotero.org` is in `core/egress.py:HOSTS`. Tests: `tests/unit/test_zotero.py` (a fake web API and
  connector; `tests/conftest.py:no_real_zotero` points both at nothing for every other test).
- **retro** (`modules/retro.py`, requires `chat`): the nightly look back proposes setting, profile, skill and idea
  changes, each confirmed through `app.ask`; only settings in `TUNABLE` (and modules' `tunable`) may be proposed. With
  Learns from its own work's `remember` part on (`Learning.picks_facts()`), `_run` appends `learning.REMEMBER_ASK` to
  the instructions, adds `chats` (the day's own requests, `Learning.chats`) to the input, and hands the answer's
  `remember` list to `Learning.keep_facts`, which keeps them without a tap. Before the AI (and without it), `_run`
  calls `records()`: `fix_data()` (`retro.fixes`) merges `Deadlines.duplicates()` pairs with `Deadlines.merge` and
  notifies each with `rfx:<id>:undo` (`undo_fix` -> `Deadlines.unmerge`; Calm reason `retro.fixed`; kept in
  `retro-state.json` `fixes`); `propose_routines()` (`retro.routines`) takes `routines_seen()` (the `SEEN` events of
  the last `SEEN_WEEKS` weeks, `study_session_start`/`_end` and `calls_held`, by name, weekday and half hour, kept when
  on `retro.routine_weeks` different ISO weeks; days with the same name and start join; the end is the median length
  to 15 min, an hour if unknown), skips any `_covered()` by a commitment or class or asked/added/declined in
  `retro-state.json` `routines`, and asks one a night with `app.ask.ask(..., hook="retro.routine")` (Add / No; Calm
  reason `retro.routine`); `routine_answer` adds it with `Commitments.add`, turning the feature on if needed.
- **dreaming** (`modules/dreaming.py:Dreaming`): `morning` (`dreaming:morning`, `dreaming.when`) builds one message
  from the event log since the last one (`since()`: `<state>/dreaming.json`, at most 30 h back): `night()` counts
  `integrate_batch`, `book_read`, `integrate_pruned`, `handwritten_linked`, `gbrain_upkeep`, `call_reviewed`,
  `learning_skill_learned`/`_improved`, `learning_remembered`, `inferred`; `loose_ends()` reads open doubts (`## Doubts`
  bullets in notes changed in 14 days), `Integrate.metrics()` (broken, no links in), past-due tasks
  (`Deadlines.upcoming`), `job_failed` events, and each enabled feature's `dreaming_lines()` (at most 2 each; a
  failure emits `dreaming_check_failed`). No AI. `Integrate.summary` doesn't send its own line while it's on.
  On a lighter day `report()` starts with `app.rhythm.lighter_line(mark=send)` and adds `rhy:lighter:no` (Not today).
  `/dream` shows it without marking it sent. Calm reason `dreaming.morning`. `self_check(ev)` (`dreaming.self_check`):
  counts `case_kept` events (missed vs `wrong`), then with Cases on runs `cases.suite()` and reports test cases in
  `fail` whose id was in the stored `passing` list (`<state>/dreaming.json`), emitting `dreaming_regressed`; only the
  sent morning message replaces `passing`. A suite error emits `dreaming_check_failed` and skips the check. Before
  the message, `tuning.morning(app, send)` (Dream RSI parts two and three; see
  [core.md](core.md#the-message-policy-dream-rsi-part-two-corepolicypy) and
  [core.md](core.md#tuning-the-rest-dream-rsi-part-three-coretuningpy)) runs `tuning.night` on the sent message (one
  change a night across messages, effort, AI order and Start-by sizes) and adds its line and Undo button, and a ready
  skill proposal's line with `rsi:<pid>:apply|no` (`callbacks()` → `tuning.answer`); `/dream policy` is `policy.show`
  plus `tuning.show`, `/dream proposal` is `tuning.show_proposal`. `__init__` registers the job follow-up
  `dreaming.proposal` (`tuning.proposal_ready`).
  `curious_lines(send)` adds at most two lines to the loose ends from `modules/curious.py` (rules only), their buttons
  in `self.buttons` (the morning message carries them; `/dream` replies with them). `curious_line`
  (`dreaming.curious`): `asks()` = lane-`you` job titles of 7 days (`Jobs.finished_since`), call `search_notes`
  queries (`<state>/calls/searches.json`, written by `searched()` from `Calls.run_tool`), quiz items graded under 3;
  `gaps()` = a concept note (`conceptgraph.scan`) named in 3+ of them that `is_stub` (under 15 words of its own), or a
  `phrases()` phrase (2-3 words ending in a `HEADS` word, or a Name–Name pair; `REQUEST_WORDS` split runs) in 3+
  with no note of that name (`note_names`: concept names and aliases, every note's file name) and not on the
  not-interested list. `resurface_line` (`dreaming.resurface`): `anniversaries()` (whole months or years since a
  project note's first `## Log` date, or a Research repository's first commit, cached in `roots`), else `faded()`
  (concept and dated lecture notes changed, and quiz subjects practised, 10-30 days ago; a subject with an exam in
  14 days first). `pick()` keeps one a day per kind and skips keys shown (or settled by a button) in 30 days; only
  `send` marks them shown (`<state>/dreaming-curious.json`), emitting `dreaming_curious` / `dreaming_resurface`.
  Buttons `drm:<offer>:stub|no|open|quiz|less` (`curious.button`): `make_stub` writes `layout.path("concept", ...)`
  (or kind `note` with no subject in the default layout) with the layout's frontmatter and adds `- [[...|Name]]`
  under the course page's `## Concepts`; `no` is `notinterested.add_topic`; `open` is `opener.open_note`; `quiz` is
  `Quiz.start_session`; `less` applies a Calm `Change` (`dreaming.resurface` false) with an Undo button. Tests:
  `tests/unit/test_curious.py`.
  Consolidating (`modules/consolidate.py`, `dreaming.consolidate`): `scan(app, ai)` runs at `dreaming:consolidate`
  (`daily 04:45`, in a thread) and, when the last scan is over 20 h old, inline (rules only) before the morning
  message. Sides (`Side`): `facts()` (`remember.kept_lines`), `gists()` and `note_lines()` (ledger rows of the last 30
  days; a day or meeting row's lines re-read from its note by `lines_of`, the ledger's own `DAY_LINE`/`_meetings`
  rules), `deadline_sides()` (open, -7..90 days; its value is the due date), `gbrain_pairs()`. `read(text, base)`
  gives key terms (stemmed, stop words out), identifiers (`quiz#3`) and values by kind (`date`: ISO dates, "3 Nov",
  weekdays as the next one on or after the line's day, today/tomorrow; `time`: clock times and "before 8"; `num`).
  `_pairs` only pairs sides sharing two terms (an inverted index). `check(a, b)`: `dup` for two facts or two gists of
  one kind and day (`same`: equal normalised text, or Jaccard ≥ 0.75 with equal values and ids); `clash` for pairs
  without gists, not of one daily note, ids not disjoint, overlap ≥ 0.75 over the smaller set and a value kind both
  give that differs (facts: date, time, num; otherwise date only, and a note side needs a scheduling word,
  `SCHEDULE`); `near` (overlap ≥ 0.5) goes to `second_opinion()` (`dreaming.consolidate_ai`: `local` =
  `providers.local`, `main` = `brain.main` unless its quota is kept, then local; never a gist; `AI_MAX` 8; one word
  SAME / CLASH). New items (A = the older side by day then place) go to `<state>/dreaming-consolidate.json`
  (`items`: ref, kind, why, `pair` = `ledger.mac` of both side ids, the sides' references; `decided`: pair → how;
  `undo`): no gist words, only row ids. `section(app, send)` re-resolves each side (`resolve`; gone or changed: the
  item goes), renders up to `dreaming.consolidate_max` with rows `(n: Keep A, dcn:<ref>:a)`, `b`, `both`, and on send
  counts shows (an item already shown `SHOWN_MAX` = 2 times is decided `unanswered`). `button` (`dcn`): `both`
  decides; `a`/`b` `_let_go` the other side: a fact `remember.remove_line`, a gist `Ledger.delete` with its payload
  `Ledger.seal`ed into the Undo record, a deadline `Deadlines.move` to the kept note's single date, a note or GBrain
  side unchanged (says where). The Undo (`dcn:<uid>:undo`) puts it back and forgets the decision (re-queuing the item
  unless it was a gist). Events `dreaming_consolidate`, `dreaming_second_opinion`, `dreaming_settled`,
  `dreaming_settle_undone`. `/dream check` is `consolidate.show`. Tests: `tests/unit/test_consolidate.py`.
  Folding into your profile (`modules/fold.py`, `dreaming.fold`): `scan(app, ai)` runs at `dreaming:fold` (`daily
  04:50`, in a thread) and inline (rules only) before the morning message when the last scan is over 20 h old.
  `said(app, st)` reads, from the per-source marks in `<state>/dreaming-fold.json` (`marks`: chat, request, call,
  journal; the first look `FIRST_DAYS` = 2 back): your turns in `<state>/chat/history.json`, `jobs.finished_since`
  with lane `you` and no then-action (`learning.asked`), call transcripts' lines whose speaker isn't Kurooto or
  `(note)`, and daily notes changed since (`graphwrite.outside`, so not Kurooto's blocks). `kind_of(sentence)`:
  `help` (`HELP`) or `about` (`ABOUT`), never a question (`?`, `ASKS`), `SKIP` (today, maybe, if, "remember that"...),
  `remember.sensitive` or `learning.OTHERS`. `known()` (profile and how-to-help-me lines, `learning.similar`) and
  `decided` (hash → kept/no) filter; `second_look()` (`dreaming.fold_ai`, `consolidate._brain`, `AI_MAX` 8, one word
  KEEP / SKIP) after the lock. `items` hold the words (the file is `owner_only`), at most `PENDING_MAX` 20.
  `section(app, send)` renders up to `dreaming.fold_max` with rows `(n: Keep, dfo:<ref>:keep)`, `(n: Not that,
  dfo:<ref>:no)`; shown `SHOWN_MAX` = 2 times without a tap, an item goes. `button` (`dfo`): `keep` writes
  `"<text> (from <where>, <day>)"`, an `about` line by `AboutYou.add_learned` (core/aboutyou.py: the
  `<!-- kurooto:learned -->` block, at the end of the In-brief part or the note; a stub profile if none, recorded as
  built so it isn't "edited"), a `help` line by `remember.add_line(LEARNED)` (`KEPT_LINE` reads the `from ...,`
  part, so rechecking and consolidating see it); `no` decides for good. Undo (`dfo:<uid>:undo`) is
  `AboutYou.remove_learned` / `remember.remove_line` (exact line only) and re-queues the item. `brief_of` adds the
  block's lines to the In-brief part; `save_profile` carries the block into a rebuilt profile and `edited()` compares
  a hash without it (`_outside`). Events `dreaming_fold_found`, `dreaming_second_look`, `dreaming_fold`,
  `dreaming_fold_undone`. `/dream fold` is `fold.show`. Tests: `tests/unit/test_fold.py`.
- **learning** (`modules/learning.py:Learning`, requires `chat`, `extra = True`): "Learns from its own work", four parts
  each behind a setting (`learning.search`, `skills`, `corrections`, `remember`; `part(name)` is the feature and the
  part both on) and a card toggle (`card`, `card_action`, `PARTS`).
  - Search: `History` keeps an SQLite FTS5 table `docs(title, body, key, kind, at)` in `<state>/learning/history.db`
    (a plain table matched with `LIKE` when this Python's SQLite lacks FTS5). `update()` adds only what's new: jobs
    from `Jobs.finished_since(mark)` (lane `you`, not `learning.*` then-actions; the request text through `asked()`,
    which drops Chat's earlier turns and a skill's `RULES`), transcripts by file mtime (`marks` table), chat turns
    newer than the last one, skipping a turn whose answer hash is already indexed (`answers` table). It runs every
    15 minutes (`learning:index`, in a thread) and before each `search()` (all words with prefix match, then any word;
    `bm25` with the title weighted 4x). `/history [Nd] <words>`; tool `search_history` (`agent_tools()`, so unattended
    runs of every brain get it, not calls). `core/space.py:history_items` prunes items older than `space.jobs_days`;
    `footprint` shows the index on its own; Backups skip it (`SKIP_STATE_FILES`).
  - Skills from experience: `_finished` is a `Jobs.watchers` entry (registered in `__init__`, gated on the feature).
    For an ok job in lane `you` with no then-action and at least `skill_min_steps` steps (the tool log, or
    `usage["tool_calls"]`), at most `CHECKS_A_DAY` a day, `judge_skill` submits `LEARN_SKILL` text-only, low effort,
    background, lane `chk`, on `check_brain()` (`learning.brain`, else `modules/integrate.py:Integrate.roles()[1]`),
    then-action `learning.skill`. `_skill_judged` reads `NONE` / `IMPROVE <name>` + bullets / `NEW` + a fenced
    SKILL.md. New: `make()` must accept it, no existing skill may share its name or mostly its words (`similar`, a
    Jaccard of 0.5 over name and description), not a command name; written with `stamp()` (`learned: true`,
    `learned_from`, `learned_on`; `internal:` dropped) via `write_note_file(create=True)` into `skills.user_dir`.
    Improve: tips under "## Learned from experience" through `_change`.
  - Corrections: `_finished` also remembers the last skill answer (`then` `skills.done`/`skills.latex`) in
    `state.json`. `heard(msg, text)` is called from `App.handle` for every non-reply message that isn't a command
    (it never consumes it): `CORRECTION` within `CORRECTION_WINDOW_S` of that answer. `Skills._again` (a reply to a
    skill's answer) calls `corrected(..., replied=True)`, which needs `CORRECTING` words. `LESSON` goes to the same
    lane and brain (then-action `learning.lesson`): `LESSON: ...` adds a line under "## Lessons"; `REWRITE` + a fenced
    file replaces it only if the file is unchanged since (`base` hash), still a skill with its header, and 0.5 to 2x
    the old length.
  - `_change(name, fn, kind)` edits a skill: your file for `yours`/`prompt` skills, else `Skills.customize` makes your
    copy (`created`, so Undo deletes it). The old text is kept in `<state>/learning/before/`; every change is a record
    in `changes.json` (last `KEEP_CHANGES`) with the new text's hash. `undo(id)` (button `lrn:<id>:undo`, `/learned`)
    refuses when the file's hash changed since; a fact is removed with `modules/remember.py:remove_line`.
  - Facts: `keep_facts` drops lines matching `OTHERS` (relatives and friends, third-person pronouns, `@`, phone
    numbers), then `modules/remember.py:keep` (Remember's own rules: `MAX_FACT`, `sensitive()`, no duplicates) into
    the section `PICKED`; one message with an Undo per fact.
  - Calm reasons `learning.skill`, `learning.lesson`, `learning.remember`; events `learning_*`, `history_searched`.
- **files** (`modules/files.py`): `take_files` for incoming files; with Chat on, an AI job files them.
- **projects** (`modules/projects.py:Projects`, 0.7.0, Help with your project) and the whole `/project` family:
  `command(app, msg, arg)` (`App.handle` sends every `/project` here; the module registers no command of its own):
  nothing or `list` → `listing()` (every source's project with its folder, "set up from it" for a repoproject folder,
  `helps` / `off` and its checks while the feature is on, then the GitHub repositories set up with `/project add`,
  which are Kurooto's read-only copies); `add`, `update`, `refresh` → `core/repoproject.py:command`; `help on|off
  <name>` (into `projects.help`), `help <name> <what>`, `checks <name> <command>|off` (into `projects.checks`, with
  `suggest_checks()`) → `Projects.help_cmd`, only while the feature is on. `kurooto project list|add|update|help|checks`
  types the same (`cli.project_run`). The intent `project_help` ("help with my thesis: ...", "in my thesis project,
  ..."; "in my <name> ..." only for a known project); "set up my project from github.com/..." is repoproject's, in
  `App.handle`. `sources()` merges `SOURCES`: `own_folders` (`projects.folders`), `repo_projects` (repoproject's
  records that are local folders, by project name), `research_repos` (`research.repos` named by `research.projects`,
  skipping anything under `<data>/repos`: repoproject's GitHub copies, which it also puts in `research.repos` for the
  commit log), `latex_documents` (`research_addon.latex_repos`); another feature or an add-on appends its own
  `fn(app) -> {name: folder}`. `start_help()` refuses a project not switched on, one already busy
  (`scratch.busy`), then `scratch.create(...)` (a worktree for a repository) and `proposals.submit(...)` at
  `projects.effort`. The rest is core: [architecture.md](architecture.md#scratch-folders-and-proposals).

Helpers that aren't modules: `modules/text.py` (time parsing, `too_complex`, `tidy`), `modules/daily.py` (the daily
note, `run_skill`, `morning_view`), `modules/termnote.py`, `modules/recurring.py`, `modules/coursepack.py`,
`modules/google_confidential.py`.

## Known problems (as of this writing)

- `modules/telegram/api.py`: there is no 429 (flood limit) handling.
- `modules/chat.py:Chat.mine` lives in memory: an answer that finishes after a restart isn't recorded into the history,
  and `list(self.mine)[-50:]` keeps an arbitrary 50 ids rather than the newest.
- `modules/hints.py:policy_kind` tests "no solutions" before "no AI", so a policy line saying both is read as hints
  allowed.
- `modules/research.py`: papers are marked seen before the AI-ranked digest is delivered; a failed digest loses them.
- `modules/capture.py` and `modules/checkins.py` declare no `privacy` and inherit "Stays on this computer.", though with
  Chat on their content goes to the AI. `modules/google_mail.py:MailDigest.privacy` says confidential mail is never
  read, but `mail_digest.confidential = "local"` has a local model read it.
- `modules/skills.py:compile_tex` passes `-no-shell-escape` to pdflatex but not to latexmk.
- `modules/calendar.py:Calendar.refresh` keeps the old copy only when every link failed; one failing link among several
  silently drops that link's events.
- `modules/classpacks.py`: `attendance_rules`, `attendance_rule` and `class_kind` have no callers once Attendance is
  removed.
- `modules/learning.py`: only the last skill answer is remembered for a "no, ..." correction (`state.json`
  `last_skill`), so a correction meant for an earlier skill answer goes to the latest one. The duplicate check for a
  learned skill compares words of names and descriptions only, so a reworded duplicate can slip through. The tool log
  is in memory: a request that finishes after a restart counts only the steps since.

## Added in 0.8.0

- **Threaded jobs.** `Module.every(..., thread=True)` (`modules/base.py`) wraps a synchronous action in
  `asyncio.to_thread`, so a heavy job never holds Kurooto's loop (the call line's heartbeat, Telegram replies, other jobs).
  Used by the Brain's lab, play, harness, senses, plans and skills jobs, the duplicates scans and the finder index.
  `tests/unit/test_every_thread.py`.
- **Set-up steps.** `Module.setup_notes` (a list of plain lines) and `setup_steps()` say what's left to do after a module is
  turned on (a key, a sign-in, a program). `modules/enable` returns `setup`; POST `modules/steps` returns them again; the
  dashboard prints "To finish setting it up:"; `/health setup` lists what is left across enabled modules (plain `/health` is
  unchanged). Set on Books, Google, LocalModels, Calls, Telegram and Backups. `tests/unit/test_setup_steps.py`.
- **Find files** (`core/finder.py`, `modules/finder.py`, module `finder`). A local SQLite FTS5 index at
  `<state>/finder/index.db` (`index`, `search`, `inside`); settings `finder.folders`, `finder.read_mb`, `finder.max_files`.
  Names, dates and sizes for everything; text for PDFs (`pdftotext`), Office files (their XML), text and code. Hidden
  folders, build folders and secret-looking names (`scratch.secret`) are skipped. `/find <words>|add|remove|folders|reindex`;
  results carry `fnd:<key>:send` buttons that use `modules/skills.send_file`. The job `index` runs daily at 04:50 on a
  thread. No AI is involved. `tests/unit/test_finder.py`.
