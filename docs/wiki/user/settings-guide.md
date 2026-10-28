# Settings guide

Every setting Kurooto has, one entry each: what it does, what it can be set to and its default, when you'd change it
and what changes when you do, what it costs or sends outward, and what it depends on. Grouped by feature; the
[contents](#contents) below lists the groups.

**Finding one.** On the dashboard, Settings (Alt+S) has a search box that also looks through these entries: type what
you want ("night", "calls", "battery") rather than a setting's name. Each setting there shows its one-line tip under
its name; click the tip for the whole entry. In the phone app, long-press a setting for its entry. On this page, your
browser's find (Ctrl+F) finds a name like `brain.main`.

**Changing one.** On the dashboard's Settings page (a feature's settings appear once it's on), or in `settings.json` in
Kurooto's config folder (`kurooto paths` says where), which holds only what you changed: a dotted name such as
`brain.main` is the key `main` inside `brain`, `{"brain": {"main": "agy"}}`, and deleting a line goes back to the
default. Restart Kurooto after editing the file by hand (`kurooto stop`, then `kurooto start`). A few settings are set
by Kurooto itself (pairing, the call line's address); their entries say so. Secrets (keys, tokens) are never settings:
they're in the system keyring.

**Times and schedules.** A time is 24-hour `HH:MM`. A schedule is `daily 07:30` (several times: `daily 07:00,13:00`),
`weekly sun 19:00`, `hourly`, or `every 15m` / `every 3h`.

This page is written by `tools/gen_settings_guide.py` from Kurooto's code and the guide's source
(`tools/settings_guide/`), so every setting is here; [the table](../../SETTINGS_GUIDE.md) lists them all on one page.

## Contents

- [You and how it talks to you](#you-and-how-it-talks-to-you): 11 settings
- [Your AI](#your-ai): 34 settings
- [Messages and where they reach you](#messages-and-where-they-reach-you): 31 settings
- [When it may interrupt you](#when-it-may-interrupt-you): 13 settings
- [Phone calls and the call line](#phone-calls-and-the-call-line): 35 settings
- [Morning alarm](#morning-alarm): 11 settings
- [Reminders, deadlines and start-by dates](#reminders-deadlines-and-start-by-dates): 34 settings
- [Check-ins, journal and the week](#check-ins-journal-and-the-week): 18 settings
- [Classes and timetable](#classes-and-timetable): 18 settings
- [Calendar](#calendar): 11 settings
- [Quiz and exams](#quiz-and-exams): 39 settings
- [Books, study time and handwritten notes](#books-study-time-and-handwritten-notes): 42 settings
- [Notes, files and sync](#notes-files-and-sync): 29 settings
- [Notes brain (GBrain)](#notes-brain-gbrain): 19 settings
- [Concept graph](#concept-graph): 27 settings
- [Google: Classroom, Gmail, Calendar and Drive](#google-classroom-gmail-calendar-and-drive): 51 settings
- [Research, projects and proposals](#research-projects-and-proposals): 48 settings
- [Teaching Kurooto and what it remembers](#teaching-kurooto-and-what-it-remembers): 61 settings
- [Brain](#brain): 129 settings
- [Voice and voice notes](#voice-and-voice-notes): 80 settings
- [Privacy and what it keeps](#privacy-and-what-it-keeps): 6 settings
- [Updates, backups and upkeep](#updates-backups-and-upkeep): 29 settings
- [This computer](#this-computer): 11 settings
- [Dashboard and terminal](#dashboard-and-terminal): 27 settings
- [Add-ons](#add-ons): 4 settings
- [The phone app's own settings](#the-phone-apps-own-settings): 26 settings
- [Face presence](#face-presence): 34 settings

## You and how it talks to you

Who you are to Kurooto (your name, time zone, notes folder) and how its AI words things for you. The persona card's four
lines go with every AI request and every call, so the wording is the same on Telegram, in the app and on the phone. They
set wording only: a line that would give Kurooto feelings, a backstory or a relationship is dropped, and you're told
why. More in [Teaching Kurooto about you](teaching-kurooto.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing by itself. The persona card's lines travel with each request to the
  AI you chose, like the rest of the request.
- **Depends on:** Nothing: these are core settings, always there.

### `you.name`

Your name, as Kurooto uses it in messages and calls.

- **Values:** Any text. **Default:** empty.
- **When to change it:** Set it at setup or when it gets your name wrong. Messages, the morning page and calls use it
  from the next one; empty, Kurooto just doesn't use a name.

### `you.timezone`

Your time zone, for every time Kurooto keeps; empty follows this computer's clock.

Reminders, check-ins, the alarm, night hours and every schedule are worked out in this zone.

- **Values:** An IANA zone name such as `Asia/Kolkata` or `Europe/Berlin`, or empty. **Default:** empty.
- **When to change it:** When this computer's clock is set to another zone than the one you live in (a server, a travel
  laptop). The schedule reads it when Kurooto starts, so restart it after a change; times already set keep their
  wall-clock time in the new zone.

### `you.workspace`

Your notes folder: where Kurooto reads and writes notes, journal and course files.

Everything Kurooto writes (journal, course notes, book notes, its own blocks) goes inside it. Obsidian works on it as it
is.

- **Values:** A full folder path, or empty for `Documents/Kurooto`. **Default:** empty.
- **When to change it:** Set it at setup to the folder you already keep notes in. Changing it later points Kurooto at
  the new folder from its next start; nothing is moved, so move your notes yourself first.
- **Depends on:** Read when Kurooto starts: restart after changing it. Notes sync, the notes brain and the sorter all
  work in this folder.

### `you.assistant_name`

The name your assistant goes by in messages, calls and the dashboard.

- **Values:** Any short name. **Default:** `Kurooto`.
- **When to change it:** When you'd rather call it something else. Your Telegram bot takes the new name at once and says
  so; messages, calls and the AI use it from the next one.

### `you.language`

Which language answers come in: the one you wrote in, or always one you name.

- **Values:** `follow` (the language of your message), or a language's name such as `English` or `Hindi`. **Default:**
  `follow`.
- **When to change it:** When you write in a mix and want answers always in one language. Only the wording of AI answers
  changes; Kurooto's own fixed messages stay in English.

### `persona.call_me`

What the AI calls you: a nickname, your first name, or nothing.

The dashboard's About you page and `/persona` change it too.

- **Values:** Any text; empty uses your name, or nothing. **Default:** empty.
- **When to change it:** When the AI's way of addressing you feels off. The next answer and the next call use it.

### `persona.tone`

The tone you want answers in, in your own words.

- **Values:** A short phrase, e.g. "plain and direct, no pep talk". Empty: the AI's usual tone. **Default:** empty.
- **When to change it:** When answers feel too chirpy, too formal or too long-winded. It shapes wording from the next
  request; facts and actions don't change.

### `persona.length`

How long answers should be, in your own words.

- **Values:** A short phrase, e.g. "short unless I ask for detail". Empty: by the length of your message (see
  `persona.register`). **Default:** empty.
- **When to change it:** When answers keep coming out longer or shorter than you like. What you write here wins over the
  length-matching of `persona.register`.

### `persona.avoid`

Things answers should never have, such as emojis or motivational lines.

- **Values:** A short list in your own words, e.g. "emojis, exclamation marks". **Default:** empty.
- **When to change it:** When something in the AI's style keeps annoying you. The next answer and call leave it out.

### `persona.register`

A short message gets a short answer, a voice note a spoken-style one.

By the message's length only: nothing changes with the time of day or partway through a conversation.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you want the same style of answer whatever you send. A length on your persona
  card wins over it either way.

### `persona.boundaries`

Health, relationship and money decisions stay yours: Kurooto names who to ask instead.

Every AI request and call is told so, and a request that asks Kurooto to make such a decision ("should I stop my meds")
is answered at once, without the AI, with a short line naming a person to ask. It's a list of rules, not a judgement:
anything else goes on as usual.

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on. Turn it off only if the rule keeps catching ordinary questions; then such requests
  go to the AI like any other.
- **Costs and what leaves this computer:** Nothing: rules on this computer. Off, those requests go to your AI like any
  other.

## Your AI

Which AI answers your requests, what stands in when it can't, how long it may work, how the free limits are kept for
what you're waiting on, and the small offline helper. Everything an AI does goes through the AI you chose here; a
request's words go to that AI's service, and nowhere else. More in [AI models](ai-brains.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Requests go to the AI you chose (agy and Claude Code through their own
  programs; a Gemini key to Google; Ollama stays on this computer). Changing these settings decides which of them is
  asked, not how much is sent.
- **Depends on:** Nothing: core settings. The dashboard's AI step on the setup page and `kurooto ai` change the main
  ones with their checks.

### `brain.main`

The AI that answers your requests and does the bigger tasks.

- **Values:** `agy`, `claude`, `gemini` (a key), `ollama` (on this computer), `custom`, or an extra Claude account
  `claude:<name>`. Empty until setup picks one. **Default:** empty.
- **When to change it:** When you switch AI programs or subscriptions. The next request goes to the new one; requests
  already running finish where they are. The setup page's AI step does the same with a test first, which is the safer
  way.
- **Costs and what leaves this computer:** Your requests' words, the files you attach and the notes a request needs go
  to this AI's service (nothing for `ollama`). Its free limit or subscription is what's used.
- **Depends on:** The program or key for that AI (setup installs and signs in). `brain.fallback` covers it when it can't
  answer.

### `brain.fallback`

Which AI takes over when your main one can't answer, in order.

- **Values:** One AI's id, a list in order such as `["agy", "gemini"]`, or empty for the automatic order: at a limit,
  the other agent program, then a Gemini key. **Default:** empty.
- **When to change it:** When you have a second AI you'd rather use as the stand-in, or none you want used. Empty is
  right for most people.
- **Costs and what leaves this computer:** A request that falls back sends the same words to the stand-in's service.
- **Depends on:** `brain.fallback_on` decides what counts as "can't answer".

### `brain.fallback_on`

What makes a request move on to the stand-in AI: a limit, a sign-in problem or a timeout.

- **Values:** A list of `rate_limited`, `auth`, `timeout`; `[]` never falls back. **Default:** `["rate_limited"]`.
- **When to change it:** Add `timeout` if your main AI is often slow, `auth` if its sign-in often lapses. Empty it if
  you'd rather wait than have another AI answer.
- **Depends on:** `brain.fallback`.

### `brain.classify`

Who decides how hard a request is (and so how much effort it gets).

- **Values:** `rules` (no AI), `main` (asks your AI first), or `ollama` (a model on this computer). **Default:**
  `rules`.
- **When to change it:** `rules` is quick and free. Pick `ollama` if you have a local model and the rules misjudge your
  requests; `main` costs one small extra request each time.
- **Costs and what leaves this computer:** `main` sends each request's text to your AI once more, to rate it; `rules`
  and `ollama` stay here.

### `brain.timeout_min.low`

Minutes a quick request may run before it's stopped.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Raise it if quick requests get cut off on a slow connection; lower it to give up sooner on
  stuck ones.

### `brain.timeout_min.medium`

Minutes a normal request may run before it's stopped.

- **Values:** A whole number. **Default:** `15`.
- **When to change it:** Raise it if ordinary requests (reading a few notes, a short write-up) get cut off.

### `brain.timeout_min.high`

Minutes a hard request may run before it's stopped.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it for long jobs (a whole chapter, a big project change) that get cut off; a stopped
  request says so and can be asked again.

### `brain.models`

Which model each AI uses at each effort level, where you want other than its preset.

- **Values:** A JSON object per AI, e.g. `{"custom": {"low": "...", "medium": "...", "high": "..."}}` or `{"claude":
  {"high": "opus"}}`. **Default:** none.
- **When to change it:** When you want a cheaper or stronger model at one level. Settings doesn't show it: the AI step
  on the setup page and `kurooto ai` set it, with a test.

### `brain.base_urls`

Another address for an AI's service, in place of its preset.

- **Values:** A JSON object, e.g. `{"custom": "http://localhost:8000/v1"}`. **Default:** none.
- **When to change it:** Only for `custom` (an OpenAI-style server of your own) or a proxy. Set through the setup page's
  AI step, which tests it.
- **Costs and what leaves this computer:** Requests go to the address you give, so make sure it's one you trust.

### `brain.claude_accounts`

Your extra Claude accounts, each its own AI you can pick (`claude:<name>`).

- **Values:** Set by Kurooto when you add an account: `{"work": {"name": "Work"}}`. **Default:** none.
- **When to change it:** Add one on the setup page (AI → Claude Code → Add another Claude account) or with `kurooto ai
  add-claude NAME`; rename or remove it in Settings → Claude accounts. Don't edit it by hand.

### `brain.effort_map`

Effort changes Dreaming learned for your requests, e.g. low ones run at medium.

- **Values:** A JSON object from one effort to another: `{"low": "medium"}`. **Default:** none.
- **When to change it:** Set by Dreaming's nightly replay, one change at a time with Undo. Empty it to go back to the
  efforts as rated.
- **Depends on:** Dreaming with `dreaming.tune_effort` on.

### `brain.fallback_first`

Effort levels at which your first stand-in AI is tried before the main one (learned by Dreaming).

- **Values:** A list of `low`, `medium`, `high`. **Default:** none.
- **When to change it:** Set by Dreaming when its replay shows the stand-in does better at a level. Empty it to always
  start with the main AI.
- **Depends on:** Dreaming with `dreaming.tune_fallbacks` on, and a `brain.fallback`.

### `brain.agy.io_mode`

How Kurooto talks to the agy program: through a pipe, or a pseudo-terminal.

- **Values:** One of: `pipe`; `pty` (a pseudo-terminal, where pipes give no output). **Default:** `pipe`.
- **When to change it:** Only if agy runs but Kurooto gets no output from it (some versions buffer when piped): try
  `pty`.
- **Depends on:** agy as your main or fallback AI.

### `brain.claude.session`

Keep Claude Code running between turns of a conversation, so each message doesn't start it again.

Your chat with Kurooto (Telegram, the phone app's chats, voice) keeps one Claude Code program running and sends it each
message, instead of starting it for every request, so its answers start sooner. It gets exactly the permissions, tools,
folders and model a fresh run would, and a request that needs other ones gets its own; it remembers the conversation
itself. It closes after `brain.claude.session_idle_min`, when your AI or this switch changes, when the chat starts over
(`/new`) and when Kurooto stops; if it fails, that message is answered by a fresh run.

- **Values:** `true` (default) or `false`. **Default:** on.
- **When to change it:** Turn it off if a kept Claude Code misbehaves, or to have every message start Claude Code fresh
  as before 0.8.17.
- **Costs and what leaves this computer:** Nothing more is sent: the same messages go to Anthropic through Claude Code.
  A kept program uses some memory while it waits (at most two).
- **Depends on:** Claude Code as your AI (`brain.main` `claude` or `claude:<name>`).

### `brain.claude.session_idle_min`

Minutes a kept Claude Code waits for your next message before it closes.

- **Values:** Minutes, more than 0. **Default:** `10`.
- **When to change it:** Longer keeps it for slow conversations; shorter frees its memory sooner.
- **Costs and what leaves this computer:** Nothing is sent; a waiting program uses memory.
- **Depends on:** `brain.claude.session`.

### `quota.on`

Keep part of each AI's free limit for what you're waiting on, so background work never uses it all.

Background work (digests, nightly reading) waits once a day's count reaches `quota.background_pct` of a known limit.
Your own requests never wait.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off on a paid plan with room to spare: background work then never waits. Counting and
  the usage line stay.
- **Costs and what leaves this computer:** Nothing: counts and times only, in quota.json on this computer.

### `quota.background_pct`

The share of an AI's daily limit background work may use before it waits for the reset.

- **Values:** A percentage, 0 to 100. **Default:** `70`.
- **When to change it:** Lower it if you run out before evening; raise it if background work waits while you hardly use
  the AI yourself.
- **Costs and what leaves this computer:** Nothing: counts and times only, in quota.json on this computer.
- **Depends on:** `quota.on`.

### `quota.limits`

Your own daily limits per AI, which win over the ones Kurooto learned.

- **Values:** A JSON object: `{"agy": 900, "gemini:gemini-flash-latest": 250}`. **Default:** none.
- **When to change it:** When you know your plan's real limit and the learned one is wrong. Kurooto then keeps its
  reserve against your number.
- **Costs and what leaves this computer:** Nothing: counts and times only, in quota.json on this computer.
- **Depends on:** `quota.on`.

### `quota.soft`

Whether a limit Kurooto only measured makes background work wait, or is just shown.

- **Values:** `learned` (a limit learned from its own count is a measure only), `all` (Google's numbers too), `off`
  (every known limit keeps its reserve, as before 0.7.5). **Default:** `learned`.
- **When to change it:** Pick `off` if background work keeps using up your day before you need the AI. A "limit reached"
  answer always pauses that AI until its reset, whatever this says.
- **Costs and what leaves this computer:** Nothing: counts and times only, in quota.json on this computer.
- **Depends on:** `quota.on`.

### `quota.local`

What a model on this computer takes over to spare the free limit.

- **Values:** `quick` (only the "how hard is this" question), `background` (queued background work too, instead of
  waiting), `off`. **Default:** `quick`.
- **When to change it:** `background` keeps digests coming on a tight limit, written by a smaller model (weaker). `off`
  if you have no local model.
- **Costs and what leaves this computer:** Nothing leaves: the local model runs here; it uses this computer's memory and
  graphics card while it works.
- **Depends on:** Local AI models on, with a model installed.

### `jobs.receipt`

One quiet line under each answer: which AI, effort, time, limit used and what it did.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't care which AI answered. Nothing else changes; the AI jobs page keeps
  the same record.
- **Costs and what leaves this computer:** Nothing.

### `jobs.header`

A first line on each answer naming the AI and repeating what you asked.

On (the default): "[Claude Code · medium] what you asked" comes first, then the answer. Off: the answer alone. A failed
request keeps its first line either way, so you know what failed.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off for shorter messages, above all in the phone app.
- **Costs and what leaves this computer:** Nothing.

### `jobs.plan_line`

Before a long answer, one short line saying what it's about to do and roughly how long.

Only when your last requests of the same kind took more than about 20 seconds. Never on a call.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather get just the answer.
- **Costs and what leaves this computer:** Nothing: worked out from what's known before the request runs.

### `jobs.stuck_min`

Minutes a request may sit with no AI at work and no program running before the watchdog stops it.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Raise it if long-thinking requests are stopped while they're still fine; lower it to free a
  stuck queue sooner. A stopped request says so.
- **Costs and what leaves this computer:** Nothing.

### `agents.export`

Which other AI programs get your skills as slash commands, so /journal works there too.

- **Values:** A list of `agy`, `agents` (Copilot CLI and others that read ~/.agents) and `claude` (Claude Code); empty:
  none. **Default:** none.
- **When to change it:** Add a program you use directly. Its skills folder gets a copy of each skill (marked as
  Kurooto's; yours are never touched), kept up to date every hour. Emptying it removes every copy Kurooto made.
- **Costs and what leaves this computer:** Nothing leaves: files written into those programs' own skills folders on this
  computer.
- **Depends on:** Those programs installed. `kurooto export-skills on|off` changes it too.

### `agents.prefix`

A prefix put before every skill copied into your other AI programs, e.g. `k-` for /k-journal.

- **Values:** Short text, or empty. **Default:** empty.
- **When to change it:** When a copied skill's name clashes with one of the program's own commands. The copies are
  renamed within the hour.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** `agents.export`.

### `agents.scripts`

Scripts of your own the AI programs may run during a request (full paths).

- **Values:** A list of full paths. **Default:** none.
- **When to change it:** When you want a request to be able to use a tool you wrote (say, `make-figures`). Everything
  else stays refused; add only scripts you trust to run unattended.
- **Costs and what leaves this computer:** The scripts run as you on this computer when the AI calls them; what they do
  is up to them.
- **Depends on:** agy or Claude Code as the AI.

### `local_helper.on`

A small model on this computer (about 1 GB) for quick decisions and as a stand-in while the internet is down.

It rates how hard a request is, picks between close readings of a short message and reads a short yes/no. Never answers
your requests while you're online.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on (or `/helper on`) on a computer without a graphics card when the free limit runs
  short or the internet often drops. It only stays on if it passes a speed test here.
- **Costs and what leaves this computer:** One download from Ollama's registry (about 1 GB of disk). Nothing else
  leaves; it uses some memory while it runs.
- **Depends on:** Ollama (installed for you).

### `local_helper.model`

Which Ollama model the offline helper uses; empty picks the standard small one.

- **Values:** An Ollama model name, or empty. **Default:** empty.
- **When to change it:** Only if you want a different small model; it must still pass the speed test.
- **Costs and what leaves this computer:** Downloads that model from Ollama's registry.
- **Depends on:** `local_helper.on`.

### `local_helper.timeout_s`

Seconds a quick decision waits for the helper before the rules decide instead.

- **Values:** A whole number. **Default:** `4`.
- **When to change it:** Raise it on a slow computer if the helper keeps timing out; the rules are always the fallback.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** `local_helper.on`.

### `local_helper.max_s`

How fast the helper must answer in its speed test (seconds), or it stays off.

- **Values:** A number. **Default:** `1.5`.
- **When to change it:** Raise it to let a slower computer use the helper anyway; decisions will feel slower.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** `local_helper.on`.

### `local_helper.offline`

With the internet down: quick things answered here, AI requests wait in the queue until it's back.

You're told once that a request waits; when the connection is back, one line says what's running. Nothing is dropped
silently.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have requests fail at once while offline instead of waiting.
- **Costs and what leaves this computer:** Nothing: nothing extra is pinged to find out the connection is down.

### `local_helper.hold_h`

Hours a request waits for the internet before it gives up and says so.

- **Values:** A whole number. **Default:** `24`.
- **When to change it:** Lower it if old requests coming back much later would be useless; raise it for long trips
  offline.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** `local_helper.offline`.

### `local_helper.offer`

Offer the offline helper once if your free limit keeps running short or the internet often drops.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you never want to be asked. `/helper on` works either way.
- **Costs and what leaves this computer:** Nothing: one message with Install / Not now, two weeks after setup, and only
  when it fits.

## Messages and where they reach you

Where Kurooto's messages go (Telegram, the phone app, this computer's notifications), how many come by themselves in a
day (Calm), the offline and back-online messages, and questions waiting for your answer. Answers to what you asked are
never held or counted; the alarm, approvals, your own reminders and deadlines under 12 hours never wait. More in
[Messages Kurooto sends by itself](messages-it-sends.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Messages go out through Telegram's servers to your chat, or sealed through
  your call line to the phone app; desktop notifications stay on this computer. Calm's records (state/calm.db, 45 days)
  stay here.
- **Depends on:** Nothing: core settings, always there.

### `notify.calm.on`

Calm: each message Kurooto sends by itself says why, has Why? and Less of this, and there's a daily limit.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have everything come as it happens, with no buttons and nothing recorded,
  exactly as before Calm existed.
- **Costs and what leaves this computer:** Nothing leaves. On, what was sent and why is recorded on this computer for 45
  days.

### `notify.calm.messages`

How many messages a day may come by themselves; the rest wait for the evening bundle.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Raise it if useful things keep waiting until evening; lower it for a quieter day. The first
  time a day the limit holds one, a line says so with Send them as they come today / Raise to 12 / Fine.
- **Depends on:** `notify.calm.on`.

### `notify.calm.calls`

How many calls a day may come by themselves; one past it waits in the evening bundle as a call link.

- **Values:** A whole number; 0: none by themselves. **Default:** `1`.
- **When to change it:** Raise it if you like being called for reminders and check-ins; set 0 to be called only when you
  asked. The alarm and calls you asked for never count.
- **Depends on:** `notify.calm.on`, Phone calls.

### `notify.calm.evening_at`

When the evening bundle comes with everything that waited today.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `20:00`.
- **When to change it:** Move it to when you usually look at your phone in the evening. After this time, messages come
  as they are.
- **Depends on:** `notify.calm.on`.

### `notify.calm.bundle_one`

Send the evening bundle as one long message instead of one by one.

Off (the default since 0.8.17): the bundle is a short header, then each message that waited, by itself, in order, with
its own buttons, so replying to one or tapping its buttons works as if it had come at once. On: one message (split only
where Telegram's length limit makes it), every item numbered and its buttons numbered to match, as before 0.8.17; the
phone app's chat shows six buttons under a message, and the rest go on in follow-up messages.

- **Values:** `false` (default) or `true`. **Default:** off.
- **When to change it:** Turn it on if a busy evening fills your chat with too many separate messages.
- **Depends on:** `notify.calm.on`.

### `notify.calm.evening`

Kinds of message that always wait for the evening bundle.

- **Values:** A list of message kinds, e.g. `["research", "weekly"]`; filled by Less of this → Another time.
  **Default:** none.
- **When to change it:** Usually set by tapping Less of this → Another time. Remove a kind to get it as it happens
  again.
- **Depends on:** `notify.calm.on`.

### `notify.calm.fewer`

Kinds of message limited to a number a day; more wait for the evening.

- **Values:** A JSON object, kind → number: `{"quiz": 1}`; filled by Less of this → Fewer. **Default:** none.
- **When to change it:** Usually set by tapping Less of this → Fewer. Raise or remove a kind's number to get more of it.
- **Depends on:** `notify.calm.on`.

### `notify.calm.habituate`

After this many of a kind go unanswered in a row, they wait for the evening until you answer one.

- **Values:** A JSON object, kind → number; set by Dreaming, with Undo. **Default:** none.
- **When to change it:** Dreaming fills it in from what you leave unanswered. Remove a kind to have it always come as it
  happens.
- **Depends on:** `notify.calm.on`; Dreaming tunes it.

### `notify.calm.windows`

Hours a kind of message may come in; outside them it waits for the evening bundle.

- **Values:** A JSON object, kind → `"10:00-18:00"`; set by Dreaming, with Undo. **Default:** none.
- **When to change it:** Dreaming sets it from when you actually answer; edit or remove a kind to change its hours.
- **Depends on:** `notify.calm.on`; Dreaming tunes it.

### `notify.calm.stopped`

Kinds of message you stopped with Less of this → Stop.

- **Values:** A list of kinds. **Default:** none.
- **When to change it:** Remove a kind to start getting it again (or use Undo on the message that stopped it).
- **Depends on:** `notify.calm.on`. Used only for kinds whose feature has no switch of its own.

### `notify.calm.lighter_after`

After an exam or a heavy day, the next day's limit is halved.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather have the same flow every day.
- **Depends on:** `notify.calm.on`.

### `notify.calm.monthly`

Once a month, it names a kind of question you hardly ever answer and offers to turn it off.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want the monthly suggestion. Nothing is turned off without your tap
  either way.
- **Depends on:** `notify.calm.on`.

### `notify.presence.on`

Tell you when Kurooto goes offline, and again when it's back with what it caught up on.

A clean stop says so before it exits; coming back says how long it was away and what it caught up on. Never a call; at
night it waits for the morning.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't care when the computer sleeps or restarts.

### `notify.presence.after_min`

How long Kurooto must be away before going offline or coming back is worth a message.

- **Values:** Minutes, at least 1. **Default:** `10`.
- **When to change it:** Raise it if short sleeps and network blips cause messages you don't need.
- **Depends on:** `notify.presence.on`.

### `notify.presence.channels`

Where the offline and back-online messages go.

- **Values:** A list of `telegram` and `app` (the phone app). **Default:** `["telegram"]`.
- **When to change it:** Add `app` if you mostly use the phone app; remove `telegram` to keep them off your chat.
- **Depends on:** `notify.presence.on`; a paired phone for `app`.

### `notify.presence.line`

While this computer can't speak (asleep, crashed, offline), your call line tells you so.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want messages from the call line while the computer is away.
- **Costs and what leaves this computer:** Your call line (on your own Cloudflare account) watches the computer's link
  and sends the message itself.
- **Depends on:** `notify.presence.on` and a call line (Phone calls).

### `notify.presence.line_telegram`

Whether your call line may keep your bot's token, so it can tell you on Telegram while the computer is away.

- **Values:** none (asked once), on, or off (off deletes the token there at the next sync, within 5 minutes).
  **Default:** none.
- **When to change it:** Answer the question when it comes; change it later here. Off, the call line can only reach the
  phone app.
- **Costs and what leaves this computer:** On, your bot's token is kept on your call line (your own Cloudflare account),
  so it can send to your chat.
- **Depends on:** `notify.presence.line`.

### `notify.desktop`

Pop-up notifications on this computer.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only want messages on your phone. A message that no other channel took still
  pops up.
- **Costs and what leaves this computer:** Nothing leaves: the system's own notifications.

### `notify.desktop_kinds`

Which kinds of message pop up on this computer.

- **Values:** A list of kinds: `call`, `question`, `approval`, `deadline`, `update`, `reminder`, `result`, `info`.
  **Default:** `["call", "question", "approval", "deadline", "update"]`.
- **When to change it:** Add `reminder` if you sit at this computer all day; remove kinds that distract you.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** `notify.desktop`.

### `notify.app_kinds`

Which kinds of message also reach your phone app.

- **Values:** A list of kinds: `call`, `question`, `approval`, plus `reminder`, `deadline`, `result`, `info` if you want
  those. **Default:** `["call", "question", "approval"]`.
- **When to change it:** Add kinds you want on the phone too; remove `question` and `approval` to keep those on Telegram
  only.
- **Costs and what leaves this computer:** Each one goes sealed with your phone's key through your call line, which
  can't read it.
- **Depends on:** A paired phone app.

### `notify.app_chat`

Kurooto's own messages also show in the phone app's chat, not just on Telegram.

Everything not already in `notify.app_kinds`: reminders, results, information.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on where Telegram is blocked or you'd rather use the app's chat.
- **Costs and what leaves this computer:** Sealed with your phone's key through your call line.
- **Depends on:** A paired phone app.

### `ask.expire_hours`

Hours an unanswered question stays open before it expires (unless its asker set another time).

- **Values:** A whole number. **Default:** `48`.
- **When to change it:** Raise it if you often answer days later; lower it so old questions stop lingering.
- **Costs and what leaves this computer:** Nothing.

### `ask.keep_days`

Days answered and expired questions are kept before they're forgotten.

- **Values:** Days; 0 follows `privacy.keep_days`, and if that's 0 too, 30 days. **Default:** `0`.
- **When to change it:** Lower it to forget your answers sooner; raise it if the weekly look back should see more of
  them.
- **Costs and what leaves this computer:** Nothing: kept in the state folder on this computer.

### `telegram.menu`

The bot's "/" menu lists the commands of the features you have on.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather keep a menu you set yourself in BotFather: Kurooto removes its own
  and leaves the menu alone.
- **Depends on:** Telegram.

### `telegram.silent_kinds`

Kinds of message sent to Telegram without a sound.

- **Values:** A list of kinds. **Default:** `["call"]`.
- **When to change it:** Add kinds you don't want buzzing your phone twice. Only while a phone app is paired (it rings
  by itself).
- **Depends on:** Telegram and a paired phone app.

### `telegram.chat_id`

Your chat with the bot (set when you pair; don't change by hand).

- **Values:** Text. **Default:** none.
- **When to change it:** Never by hand: pairing sets it. Pair again (`kurooto telegram`) to move to another chat.
- **Depends on:** Telegram. Not shown on the dashboard.

### `telegram.allowed_users`

The Telegram accounts that may use your bot (set when you pair).

- **Values:** A list of Telegram user ids. **Default:** none.
- **When to change it:** Set by pairing. Anyone not on it is ignored, so don't add accounts you don't own.
- **Depends on:** Telegram. Not shown on the dashboard.

### `telegram.api_base`

Telegram's API address. Leave it alone.

- **Values:** Text. **Default:** `https://api.telegram.org`.
- **When to change it:** Only for tests or a Bot API server of your own.
- **Costs and what leaves this computer:** Every Telegram message goes to this address.
- **Depends on:** Telegram. Not shown on the dashboard.

### `keep.ask`

On day 10, then at most monthly: Keep / Quiet / Off for features you don't use.

From use counted on this computer. Nothing is turned down without your tap.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you never want the question. `/keep` shows the counts either way.
- **Costs and what leaves this computer:** Nothing: counted on this computer.

### `turnon.offer`

When you ask for something a feature that's off would do, offer to turn it on.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have such requests go straight to your AI instead.
- **Costs and what leaves this computer:** Nothing: rules only.
- **Depends on:** Telegram or the phone app (where a button can be tapped).

### `repair.on`

When a short request could mean either of two things, ask which with both as buttons.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather it went to your AI than asked.
- **Costs and what leaves this computer:** Nothing: rules on this computer.

## When it may interrupt you

The night, focus time, calendar events that hold calls, and the regular commitments in your week. A held call or message
isn't lost: it comes once the hold ends (or in the evening bundle). Learned changes to your hours are said once, with
Undo, and never touch hours you set yourself. More in [Phone calls and the morning alarm](calls.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing: rules on this computer. What it learns about your hours (two times)
  is kept in state/rhythm.json.
- **Depends on:** Nothing: core settings, always there.

### `availability.night.enabled`

No calls during the night hours.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off only if calls at any hour are fine with you. With the wake-up alarm set, the night
  runs from your bedtime to the alarm instead.

### `availability.night.from`

When the night hours start.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `23:30`.
- **When to change it:** Set it to when you usually go to sleep. Kurooto may move it for you
  (`availability.learn_night`) unless you set it here yourself.

### `availability.night.to`

When the night hours end.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `07:00`.
- **When to change it:** Set it to when you're usually up. Once you set it, the learning leaves it alone.

### `availability.night.alarm_only`

Hold calls at night only on nights you've set a wake-up alarm.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you set the alarm every night you want quiet, and calls on other nights are fine.
- **Depends on:** The Morning alarm.

### `availability.learn_night`

Move the night hours to when you're actually quiet, learned from three weeks of your activity, with Undo.

At most once a week, never night hours you set yourself, and not for a month after an Undo.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if your hours vary a lot or you want them fixed.

### `availability.learn_morning`

The check-in day, the morning message and "Time to start" follow your learned hours.

Unless you set those times yourself: the check-in day turns two hours before you're up, the morning message comes half
an hour after, Time to start an hour after.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep those at their clock times.
- **Depends on:** `availability.learn_night`.

### `availability.absence_days`

After this many days with nothing from you, one gentle "all good?" message.

- **Values:** Days; 0: never. **Default:** `2`.
- **When to change it:** Set 0 if you often go quiet for days on purpose. It's never repeated, never a call, and Busy
  gives you a quiet week.
- **Costs and what leaves this computer:** One Telegram message, through Calm.

### `availability.focus_keyword`

A calendar event with this word in its title is focus time: messages and calls wait.

- **Values:** A word, e.g. `#focus`. **Default:** `#focus`.
- **When to change it:** Change it if you already use another tag for deep-work blocks.
- **Depends on:** The Calendar feature.

### `availability.nocall_keyword`

A calendar event with this word in its title holds calls while it's on.

- **Values:** A word, e.g. `#nocall`. **Default:** `#nocall`.
- **When to change it:** Change it to a tag you already use. Matters when `calendar.nocall_events` is `tagged`.
- **Depends on:** The Calendar feature.

### `availability.nocall_calendar`

Part of a calendar's name: every event in such a calendar holds calls.

- **Values:** Part of a calendar's name, any case. **Default:** `no call`.
- **When to change it:** Name a calendar (say, "Shifts") whose events should always hold calls. Matters when
  `calendar.nocall_events` is `tagged`.
- **Depends on:** The Calendar feature.

### `commitments.items`

Your regular commitments (the gym, a shift, a standup), each on its days and hours.

- **Values:** A list of `{"name": "gym", "days": ["mon", "wed"], "start": "18:00", "end": "19:00", "calls": true}`.
  **Default:** none.
- **When to change it:** Easier with `/busy add gym mon,wed 18:00-19:00` or by saying "every Tuesday at 7pm I go to the
  gym". Edit here to fix a time.
- **Depends on:** The Commitments feature.

### `commitments.no_calls`

No calls while a commitment is on.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep commitments only as a list. Each one can also opt out alone: `/busy calls
  gym off`.
- **Depends on:** The Commitments feature.

### `commitments.hooks`

Words of yours that start a hold: "gym" alone holds calls for 90 minutes.

- **Values:** A list of `{"word": "gym", "hold": "calls" or "all", "minutes": 90}`. **Default:** none.
- **When to change it:** Set by saying "when I say gym, hold calls 90 min"; `/hooks drop gym` forgets one. A hook never
  sets an alarm or sends anything.
- **Depends on:** The Commitments feature.

## Phone calls and the call line

Calls both ways through your own call line (a small Cloudflare Worker on your account), the voice they use, how
persistently they ring, the look back after each call, what the phone app gets from the computer, and reminders that
still arrive while this computer's lid is shut. More in [Phone calls and the morning alarm](calls.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Calls run through your call line on your own Cloudflare account. Live calls
  stream your voice to Google's Gemini Live with your key; turn-by-turn calls send each turn's text to Gemini (or stay
  here with a local model). What goes to the phone app is sealed with its key.
- **Depends on:** The Phone calls feature, with its call line deployed and a phone paired.

### `calls.voice_mode`

How calls listen and speak: Gemini Live, your phone's own speech turn by turn, or Live with the phone as backup.

- **Values:** `auto` (Live, and the phone's speech when Live fails), `live` (Live only; a failed call goes to Telegram),
  `phone` (the phone's speech every time). **Default:** `auto`.
- **When to change it:** Pick `phone` if Live is often down or you're on a weak connection; `live` if you never want the
  walkie-talkie style. Applies from the next call.

### `calls.voice_by_kind`

The voice mode for one kind of call, e.g. the alarm always on the phone's speech.

- **Values:** A JSON object, kind → mode: `{"alarm": "phone", "checkins:evening": "live"}`. Kinds: a feature (`alarm`,
  `checkins`, `weekly`, `quiz`, `deadlines`, `research`), one of its calls (`checkins:night`), `reminder`, `outgoing`.
  **Default:** none.
- **When to change it:** When one kind of call works better another way (a sleepy alarm call on the plainer phone
  speech, say). The more exact kind wins over `calls.voice_mode`.

### `calls.live_model`

The Gemini Live model calls try first.

- **Values:** A Gemini Live model name. **Default:** `gemini-3.8-live`.
- **When to change it:** When Google brings out a newer Live model, or this one is retired. A model that fails moves the
  call to the next in `calls.live_models`.

### `calls.live_models`

Other Live models to try, in order, when the first one is down.

- **Values:** A list of model names; `[]` keeps to `calls.live_model`. **Default:** `["gemini-3.1-flash-live-preview",
  "gemini-2.5-flash-native-audio-latest"]`.
- **When to change it:** Add a model you know works on your key; empty it if you'd rather fall back to turn by turn than
  to an older model.

### `calls.voice`

Which Gemini Live voice calls speak in; empty is Google's default.

- **Values:** A Live voice name such as `Kore`, `Puck` or `Charon`. **Default:** empty.
- **When to change it:** When you'd like a different voice. Takes effect on the next call.

### `calls.voice_by_model`

A voice for each Live model, where a model doesn't know the one in `calls.voice`.

- **Values:** A JSON object, model → voice name. **Default:** none.
- **When to change it:** Only if a fallback model refuses your chosen voice.

### `calls.turn_brain`

Who answers turn-by-turn calls on your computer: Gemini with your key, or a local model.

- **Values:** One of: `gemini` (your key); `local` (Local AI models). **Default:** `gemini`.
- **When to change it:** Pick `local` to keep turn-by-turn calls entirely on this computer (needs a capable local model;
  answers are slower and plainer).
- **Costs and what leaves this computer:** `gemini` sends each turn's words to Google with your key; `local` keeps them
  here.

### `calls.text_model`

The Gemini model that answers turn-by-turn calls (here, or on your call line while the computer is off).

- **Values:** A Gemini model name. **Default:** `gemini-flash-latest`.
- **When to change it:** When a cheaper or faster model suits you, or this one is retired.

### `calls.persona`

Your own words on how calls should sound, such as "be brief and a bit cheeky".

- **Values:** Text. **Default:** empty.
- **When to change it:** When calls feel too chatty or too stiff. Your persona card applies to calls too; this adds
  call-only wording.

### `calls.ring_s`

Seconds a call rings before it counts as missed (a wake-up call rings 5 minutes).

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it if you often reach the phone just too late.

### `calls.realert_min`

Minutes after the first ring that an unanswered call rings again.

- **Values:** A list of minutes, e.g. `[3, 6]`; `[]` rings once. **Default:** `[3, 6]`.
- **When to change it:** Empty it if one ring is enough; add a later one if you sleep through calls you asked for.

### `calls.later_min`

Minutes until it calls back after you tap Later on a ringing call.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Set it to how long you're usually busy when you tap Later.

### `calls.review`

After every call, an AI request looks back at it: does what slipped through and keeps lessons.

It finishes anything the call promised but didn't do, and keeps short lessons every later call is told.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to save AI requests, or if you don't want calls read back. Calls still work the
  same.
- **Costs and what leaves this computer:** The call's transcript goes to your AI (or `calls.review_brain`) once per
  call.

### `calls.review_brain`

Which AI does the look back after a call; empty is your main one.

- **Values:** An AI id such as `agy`, `gemini` or `claude`, or empty. **Default:** empty.
- **When to change it:** Pick a cheaper AI if look backs use too much of your main AI's limit.
- **Costs and what leaves this computer:** That AI gets the call's transcript.
- **Depends on:** `calls.review`.

### `calls.review_effort`

How hard the look back after a call thinks.

- **Values:** One of: `low`; `medium`; `high`. **Default:** `high`.
- **When to change it:** Lower it to spend less of your AI's limit on look backs.
- **Depends on:** `calls.review`.

### `calls.lessons_max`

How many lessons from past calls every call is told; a repeat replaces the older one.

- **Values:** A whole number. **Default:** `12`.
- **When to change it:** Lower it if calls feel weighed down by old rules; raise it if useful lessons drop off.
- **Depends on:** `calls.review`.

### `calls.notes_repo`

Your notes' repository on GitHub, so calls can read whole notes while this computer is off.

- **Values:** `owner/repo`; set by Notes sync. **Default:** empty.
- **When to change it:** Set for you by Notes sync. Empty it if calls shouldn't read your notes from GitHub.
- **Costs and what leaves this computer:** Your call line reads notes from that repository with Notes sync's token, only
  during a call.
- **Depends on:** Notes sync, and `notes_sync.share_with_calls`.

### `calls.ntfy_server`

The push server the phone app listens on. Change it only if you run your own.

- **Values:** A web address. **Default:** `https://ntfy.sh`.
- **When to change it:** Only if you host your own ntfy server. Pair the phone again afterwards.
- **Costs and what leaves this computer:** Wake-up pushes (no content) go through this server.

### `calls.today`

Your phone app's Today screen and its copy of your alarm, kept up to date from this computer.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't use the app's Today screen. The app then says it's turned off.
- **Costs and what leaves this computer:** Sealed for each phone with its own key through your call line, every 5
  minutes when it changed.
- **Depends on:** Phone calls and a paired Android phone.

### `calls.views`

Systems and the Notes map in the phone app: your notes' titles and links, and each feature's health.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to see your notes map on the phone. Off by default because it sends note titles to
  the phone.
- **Costs and what leaves this computer:** Note titles and links (never what notes say), sealed with the phone's key,
  through your call line.
- **Depends on:** Phone calls and a paired Android phone.

### `calls.views_notes`

The most notes on the phone's Notes map (best linked first).

- **Values:** A whole number. **Default:** `5000`.
- **When to change it:** Lower it if the map is slow on your phone.
- **Depends on:** `calls.views`.

### `calls.views_links`

The most links on the phone's Notes map (a book's "Seen in" links go first).

- **Values:** A whole number. **Default:** `20000`.
- **When to change it:** Lower it if the map is slow or cluttered on your phone.
- **Depends on:** `calls.views`.

### `calls.worker.url`

Your call line's address (set when it's deployed).

- **Values:** Text. **Default:** empty.
- **When to change it:** Never by hand: deploying the call line sets it.

### `calls.worker.name`

Your call line's name on Cloudflare (set when it's deployed).

- **Values:** Text. **Default:** empty.
- **When to change it:** Never by hand: deploying the call line sets it.

### `calls.worker.version`

The version of your call line that's deployed (set by Kurooto).

- **Values:** Text. **Default:** empty.
- **When to change it:** Never by hand: Kurooto updates the call line and writes it here.

### `calls.chat_sessions`

Separate chats in the phone app, each its own conversation whose context carries over.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep one chat, as on Telegram.
- **Costs and what leaves this computer:** Messages travel sealed through your call line; each chat's context goes to
  your AI with its requests.
- **Depends on:** Phone calls and a paired phone.

### `calls.chat_files_inline`

Files in the app's chat show inline and open in the app.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to get files as a link instead.
- **Depends on:** Phone calls and a paired phone.

### `calls.chat_edit`

Edit your own messages in the app's chat for 15 minutes after sending.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if edits confuse you; Kurooto isn't asked again after an edit either way.
- **Depends on:** Phone calls and a paired phone.

### `calls.chat_titles`

How a new chat gets its title: its first words, or a short title from your AI.

- **Values:** `first words` or `ai`. **Default:** `first words`.
- **When to change it:** Pick `ai` for neater titles; it costs one small AI request per new chat.
- **Costs and what leaves this computer:** `ai` sends the chat's first message and answer to your AI once.

### `lidsafe.hours`

How far ahead your call line holds reminders and the morning line, in hours.

- **Values:** 12 to 24. **Default:** `24`.
- **When to change it:** Lower it to keep less on the call line; 24 covers a whole night and day away.
- **Costs and what leaves this computer:** Your call line keeps each item as a time, an id and ciphertext it can't read.
- **Depends on:** Reminders with the lid shut, Phone calls and an Android phone.

### `lidsafe.reminders`

Your reminders still reach the phone while this computer is asleep or off.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have reminders only from this computer (late, if it slept).
- **Costs and what leaves this computer:** Sealed for each Android phone with its own key; your call line holds
  ciphertext only.
- **Depends on:** Reminders with the lid shut.

### `lidsafe.today`

A morning line on your phone with the day's first class and what's due, even with the lid shut.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the morning page and check-ins are enough.
- **Costs and what leaves this computer:** Sealed for each Android phone; your call line holds ciphertext only.
- **Depends on:** Reminders with the lid shut.

### `lidsafe.morning`

When the morning line comes if no wake-up alarm is set.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `07:30`.
- **When to change it:** Set it to when you're usually up. With the alarm set, it comes with the alarm.
- **Costs and what leaves this computer:** Sealed for each Android phone; your call line holds ciphertext only.
- **Depends on:** `lidsafe.today`.

### `calls.views_brain`

Show the Brain console in the phone app's Views (the Brain choice), sealed for your phone like Systems and the Notes
map.

- **Values:** `true` (the phone gets the Brain's copy, but only while you're looking at it), `false` (the Brain choice
  says it's off). **Default:** on.
- **When to change it:** Turn it off if you'd rather the Brain's decisions and plans never travel to your phone.
- **Costs and what leaves this computer:** A sealed copy of what the Brain logged (decisions, plans, beliefs: never
  health or money) passes through your call line while you watch it.
- **Depends on:** Phone views (`calls.views`) and Brain on, with the Brain console (`mind.console.on`).

### `calls.views_being`

Show the being in the phone app's Views: the dashboard's own body of Kurooto, drawn on the phone from a sealed copy.

- **Values:** `true` (each Systems copy carries the being's block: features on or off, AI requests and their titles,
  what's scheduled, the coil's readings, Voice's state, event kinds and times, the panels' settings), `false` (the Being
  choice says it's off). **Default:** on.
- **When to change it:** Turn it off if you'd rather the titles of your AI requests and schedule never travel to your
  phone. Note previews are only fetched when you tap a note.
- **Costs and what leaves this computer:** A slightly bigger sealed copy through your call line every few seconds while
  Views is open.
- **Depends on:** Phone views (`calls.views`).

## Morning alarm

Kurooto wakes you with a call that rings on the alarm stream (so it rings on silent), placed by your call line so it
rings even if this computer is asleep. Set one in plain English ("wake me at 6:45"), with /alarm, or as a daily default
here. While an alarm is set, the night runs from your bedtime to the alarm. More in [Phone calls and the morning
alarm](calls.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** The alarm is held by your call line (your own Cloudflare account) and rings
  your phone; the call itself is like any other (see Phone calls).
- **Depends on:** The Morning alarm feature, with Phone calls and a paired phone.

### `alarm.daily`

A wake-up time that rings every day (on the days below) unless you set another for that morning.

- **Values:** A time `HH:MM`, or none (off). **Default:** none.
- **When to change it:** Set it if you get up at the same time most days; "no alarm tomorrow" skips one day and it's
  back after. `/alarm daily 7:00` and `/alarm daily off` change it too.

### `alarm.days`

The days the daily alarm rings.

- **Values:** A list of `mon` … `sun`. **Default:** `["mon", "tue", "wed", "thu", "fri", "sat", "sun"]`.
- **When to change it:** Take the weekend out if you sleep in: `["mon", "tue", "wed", "thu", "fri"]`.
- **Depends on:** `alarm.daily`.

### `alarm.reason`

What the wake-up call says it's for.

- **Values:** Short text. **Default:** `Wake-up call`.
- **When to change it:** Change the words if "Wake-up call" isn't how you'd put it; it shows on the ringing screen.

### `alarm.retries`

How many more times the alarm rings if you don't answer (5 minutes apart).

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Raise it if you sleep through it; 0 rings once.

### `alarm.snooze_min`

Minutes a snoozed alarm waits before it rings again.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Shorten it if you fall back asleep; Later on the ringing call uses it.

### `alarm.bedtime`

With an alarm set, no calls from this time until it rings; none uses the night hours' start.

- **Values:** A time `HH:MM`, or none. **Default:** none.
- **When to change it:** Set it if you go to bed earlier than your night hours start on nights you've set an alarm.

### `alarm.prep_min`

Minutes before the alarm that your AI drafts the day's plan into today's daily note.

- **Values:** Minutes; 0: no plan. **Default:** `20`.
- **When to change it:** Set 0 if you don't want a drafted plan; raise it if the plan isn't ready when the alarm rings.
- **Costs and what leaves this computer:** One AI request each morning with an alarm; it reads your calendar, deadlines
  and notes for the day.
- **Depends on:** Chat with your AI on.

### `alarm.notes`

After the wake-up call, today's plan (or what you said on the call) goes into your daily note.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want the morning call in your notes.
- **Costs and what leaves this computer:** Nothing leaves: written to your notes on this computer.

### `alarm.open_page`

When the alarm rings, the morning page opens on this computer (if it's awake).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the page opening on a shared or sleeping-room screen bothers you.
- **Costs and what leaves this computer:** Nothing leaves.

### `alarm.keep_awake`

Keep this computer awake before the alarm so the day's plan is drafted in time.

From 12 hours before until 15 minutes after it rings. On Linux, with the lid closed too; a Mac still sleeps with its lid
closed.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if the plan is often missing because the computer slept overnight. Plug it in: it
  stays awake all night.
- **Costs and what leaves this computer:** Battery and power overnight.

### `alarm.suggest`

Before your usual bedtime with no alarm set, one message offering your usual wake-up time.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't use an alarm every night. It never sets one by itself.
- **Costs and what leaves this computer:** At most one Telegram message a day.

## Reminders, deadlines and start-by dates

The deadline list and how it chases what's due (a message a day before, a call or urgent message six hours before,
"Overdue?" after), where deadlines come from (your notes, Classroom, the calendar, the term note, photos), and start-by
dates worked back from your free time. Start-by is local arithmetic: no AI. More in [Reminders and
deadlines](reminders-and-deadlines.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer beyond the messages and calls themselves
  (Telegram, the phone app, your call line).
- **Depends on:** The Deadlines feature.

### `deadlines.ping_h`

Hours before a deadline that its first nudge comes (one message, with Done / Not mine / Snooze).

- **Values:** A whole number. **Default:** `24`.
- **When to change it:** Raise it to hear about deadlines earlier; lower it if a day's notice is too early to act.

### `deadlines.urgent_h`

Hours before a deadline that it's urgent: a call (with Phone calls) or an urgent message.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Raise it if six hours isn't enough to finish things; lower it if the urgent nudge comes too
  early.

### `deadlines.call`

The urgent nudge is a call, when Phone calls is on (a message when no call fits before it).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to get a message instead of a call.
- **Depends on:** Phone calls.

### `deadlines.plan_h`

How far ahead "due soon" looks, in hours: the morning plan, /status and calls.

- **Values:** A whole number. **Default:** `72`.
- **When to change it:** Raise it to see the week's deadlines every morning; lower it to see only the next day or two.

### `deadlines.overdue_check`

After a deadline's due time: "Overdue?" with Done / New date / Drop.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather let past deadlines drop quietly.

### `deadlines.tick_notes`

Done ticks the `- [ ]` line in your notes when the deadline came from one.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if Kurooto shouldn't change your task lines.
- **Costs and what leaves this computer:** Nothing leaves: it changes only that checkbox.
- **Depends on:** `deadlines.scan_notes`.

### `deadlines.scan_notes`

Find deadlines in your notes: dated `- [ ]` tasks.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if your notes' dated tasks aren't deadlines you want chased.

### `deadlines.skip_notes`

Notes or folders the deadline scan leaves alone.

- **Values:** A list of note paths or folders inside your notes. **Default:** none.
- **When to change it:** Add an ideas list or an archive whose dates aren't due dates.
- **Depends on:** `deadlines.scan_notes`.

### `deadlines.max_files`

The most notes read when looking for deadlines (notes over 1 MB are skipped).

- **Values:** A whole number. **Default:** `3000`.
- **When to change it:** Raise it if you have a very large notes folder and some tasks are missed; lower it on a slow
  computer.
- **Depends on:** `deadlines.scan_notes`.

### `deadlines.from_calendar`

Calendar events that look like deadlines or exams join the deadline list.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if your calendar's events aren't deadlines.
- **Depends on:** The Calendar feature.

### `deadlines.from_term_note`

The term note's quizzes, exams and deadlines join the deadline list.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you keep that list elsewhere.
- **Depends on:** Subjects and timetable, with a term note (`/term note`).

### `deadlines.from_photos`

Send a photo with the caption "dates" and its dates come back as buttons to add.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you never send notice-board photos.
- **Costs and what leaves this computer:** The photo goes to your AI to read its dates.

### `deadlines.recurring`

Recurring quizzes (from kurooto/recurring.md in your notes) become dated deadlines.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't keep a recurring quizzes table.

### `deadlines.horizon_days`

How far ahead recurring quizzes become dated deadlines, in days.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Lower it to keep the list short; raise it to see a whole term ahead.
- **Depends on:** `deadlines.recurring`.

### `deadlines.exam_mode_days`

Days before a quiz or exam that exam mode starts (more practice, revision); 0 turns it off.

- **Values:** A whole number. **Default:** `14`.
- **When to change it:** Raise it if you start revising earlier; 0 if you don't want exam mode.
- **Depends on:** Quiz for the practice it brings.

### `deadlines.meeting_brief`

The evening before a meeting with a project's person: a short brief of where things stand.

- **Values:** A schedule such as `daily 20:00`; empty: off. **Default:** `daily 20:00`.
- **When to change it:** Move it to when you prepare for the next day; empty it to stop the briefs.
- **Costs and what leaves this computer:** One AI request per brief, with that project's notes.
- **Depends on:** Help with your project, with meetings logged in a project note.

### `startby.horizon_days`

Deadlines due this far ahead (in days) get a start-by date.

- **Values:** A whole number. **Default:** `35`.
- **When to change it:** Raise it to plan big deadlines further ahead.
- **Depends on:** Start-by dates.

### `startby.window`

The hours of each day that count as free time for planning deadlines.

- **Values:** `HH:MM-HH:MM`; an end before the start runs past midnight. **Default:** `09:00-22:00`.
- **When to change it:** Set it to the hours you actually work. A window you set is never moved by the learning.
- **Depends on:** Start-by dates.

### `startby.learn_window`

Once a week, move the window to when you're actually up, with one line and Undo.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep the window fixed. It never changes one you set yourself.
- **Depends on:** Start-by dates.

### `startby.share`

The share of your free time (in %) that goes to deadlines; the rest is for everything else.

- **Values:** A whole number. **Default:** `40`.
- **When to change it:** Raise it if start-by dates come too late for you; lower it if they come too early.
- **Depends on:** Start-by dates.

### `startby.min_gap_min`

Gaps between classes and events shorter than this (minutes) don't count as free time.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Lower it if you do get work done in short gaps.
- **Depends on:** Start-by dates.

### `startby.sizes.problem_set`

Hours a problem set or homework takes.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Change it if your problem sets take more or less than an evening. A size you tap in "Time to
  start" overrides it for that one.
- **Depends on:** Start-by dates.

### `startby.sizes.report`

Hours a report, essay, project or presentation takes.

- **Values:** A whole number. **Default:** `12`.
- **When to change it:** Change it to how long such work really takes you.
- **Depends on:** Start-by dates.

### `startby.sizes.quiz`

Hours to prepare for a quiz.

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Change it to how long you really revise for a quiz.
- **Depends on:** Start-by dates.

### `startby.sizes.exam`

Hours to prepare for an exam, unless its subject has its own.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Change it, or set per subject in `startby.exam_by_subject` (the first exam of a subject asks
  you).
- **Depends on:** Start-by dates.

### `startby.sizes.other`

Hours any other deadline takes.

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Change it if your other deadlines are usually bigger or smaller.
- **Depends on:** Start-by dates.

### `startby.exam_by_subject`

Hours to prepare for a subject's exams, where it differs from the usual.

- **Values:** A JSON object, subject → hours: `{"linear-algebra": 25}`. **Default:** none.
- **When to change it:** Answer the question at a subject's first exam, or use `/startby exam la 2-3 days`.
- **Depends on:** Start-by dates.

### `startby.ask_exams`

The first time a subject has an exam, ask how long its exams take you to prepare for.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the usual exam size is fine for every subject.
- **Depends on:** Start-by dates.

### `startby.when`

When the day's "Time to start" messages come (they wait out quiet hours).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 08:00`.
- **When to change it:** Move it to when you plan your day.
- **Depends on:** Start-by dates.

### `startby.tell`

A message on a deadline's start-by day (only when that's two days or more before it's due).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to see start-by dates only in the morning plan and /startby.
- **Depends on:** Start-by dates.

### `startby.crunch_weeks`

Weeks the Sunday summary looks ahead for crunch weeks (more work due than free time); 0: none.

- **Values:** A whole number. **Default:** `4`.
- **When to change it:** Raise it to see trouble further ahead; 0 to drop the crunch-week line.
- **Depends on:** Start-by dates and the Weekly summary.

### `startby.negotiate`

A deadline that keeps slipping gets a reshaped plan once a day instead of the same reminder again.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather keep the plain reminders.
- **Depends on:** Start-by dates.

### `reminders.places`

Location reminders: "remind me when I reach the library to …".

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to use places you saved in the Android app.
- **Costs and what leaves this computer:** Where your places are never leaves the phone; the computer and call line only
  see their names.
- **Depends on:** Reminders and the Android app, with places saved in it.

### `date_offers.remind_min`

An event you tap Add on (from a photo, mail or a shared calendar) is reminded this long before.

- **Values:** Minutes. **Default:** `60`.
- **When to change it:** Change it to how much warning you like for such events.
- **Depends on:** Reminders.

## Check-ins, journal and the week

The evening, night and midday check-ins that ask how the day went and write your answer into your journal, the Sunday
summary of the week, and the first week's small quests. Your answers stay in your notes; with Chat on, your AI may write
them up. More in [Check-ins and journal](check-ins-and-journal.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Check-in questions and answers travel over Telegram, the app or a call like
  any message; your answers are written into your notes on this computer. Where an entry says so, your AI also gets
  them.
- **Depends on:** The Check-ins feature.

### `checkins.times.evening`

When the evening check-in comes: the day in review.

- **Values:** A time `HH:MM`, or none (off). **Default:** `22:00`.
- **When to change it:** Move it to when your day winds down; none turns the evening check-in off.

### `checkins.times.night`

When the night check-in comes, just before bed (off unless you set a time).

- **Values:** A time `HH:MM` such as `23:15`, or none (off). **Default:** none.
- **When to change it:** Set it if you want a last line in your journal before sleeping.

### `checkins.times.midday`

When the midday check-in comes (off unless you set a time).

- **Values:** A time `HH:MM` such as `13:00`, or none (off). **Default:** none.
- **When to change it:** Set it if you'd like to re-plan the afternoon halfway through the day.

### `checkins.questions.evening`

What the evening check-in asks.

- **Values:** Any question. **Default:** `How did today go? What got done, and what slipped?`.
- **When to change it:** Reword it to what you actually want to reflect on.

### `checkins.questions.night`

What the night check-in asks.

- **Values:** Any question. **Default:** `Before bed: anything else for your journal? What's first tomorrow, and when
  should I wake you?`.
- **When to change it:** Reword it to suit your bedtime routine.

### `checkins.questions.midday`

What the midday check-in asks.

- **Values:** Any question. **Default:** `How's the morning been? Anything to re-plan for the afternoon?`.
- **When to change it:** Reword it to what you want to check at midday.

### `checkins.journal`

Each check-in's answer goes into your journal.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only want the questions, not the writing.

### `checkins.day_starts`

When a check-in day begins, so a night check-in at 00:30 still counts for the evening before.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `05:00`.
- **When to change it:** Move it if you often stay up past 5. Kurooto moves it with your learned hours unless you set
  it.

### `checkins.learn_times`

A check-in you keep moving or answering late moves to when you actually do it, with Undo.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep check-ins at the times you set.

### `checkins.reflect`

The evening check-in lists up to three things today's records show you did, and asks what's first tomorrow.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off for the plain question only.

### `checkins.by_call`

Check-ins come as a call (a missed call falls back to Telegram).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd rather talk than type at the end of the day.
- **Costs and what leaves this computer:** A call like any other: through your call line and Gemini Live.
- **Depends on:** Phone calls.

### `checkins.asleep_defers`

With check-ins by call and an alarm set, the night check-in waits for the morning once you've gone to bed.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to be called anyway.
- **Depends on:** `checkins.by_call` and the Morning alarm.

### `checkins.ai_notes`

After a check-in call, your AI writes your journal and study logs from what you said.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have your words go into the journal as they are.
- **Costs and what leaves this computer:** The call's transcript goes to your AI once.
- **Depends on:** Chat with your AI on, and `checkins.by_call`.

### `weekly.when`

When the week's summary comes.

- **Values:** `weekly <day> HH:MM`, e.g. `weekly sun 19:00`. **Default:** `weekly sun 19:00`.
- **When to change it:** Move it to when you plan your week.
- **Costs and what leaves this computer:** Nothing leaves: counted from the local event log.
- **Depends on:** The Weekly summary.

### `weekly.people`

One line about the people in your project notes: who you met this week and who's next.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want people in the summary. Only from meetings logged in your project
  notes.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Weekly summary.

### `weekly.call`

A Sunday review call after the summary: the week, what went well, next week's priorities.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like to talk the week through.
- **Costs and what leaves this computer:** A call (call line and Gemini Live); with Chat on, its write-up goes through
  your AI.
- **Depends on:** The Weekly summary and Phone calls.

### `quests.when`

When the day's first-week quest comes.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 18:00`.
- **When to change it:** Move it to a time you'll have a minute to try something.
- **Costs and what leaves this computer:** Nothing leaves: no AI.
- **Depends on:** First-week quests (they run for the first `quests.days` days).

### `quests.days`

How many days the first-week quests run.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Shorten it if you've found your way around already; `/quests stop` ends them at once.
- **Costs and what leaves this computer:** Nothing leaves: no AI.
- **Depends on:** First-week quests.

## Classes and timetable

Your subjects and weekly timetable, the term's dates, the question after each class, and doubts saved for the next
class. Classes hold calls while they're on; a missed class gets a catch-up task. Most of these are easier to set with
`/subject`, `/class` and `/term` than by typing JSON. More in [Classes, timetable and
calendar](classes-and-timetable.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer; with Chat on, the after-class answer goes to
  your AI to become a lecture note.
- **Depends on:** The Subjects and timetable feature.

### `subjects.list`

Your subjects: each one's name, short names and notes folder.

- **Values:** A list, typed as JSON; `/subject add` fills it in. **Default:** none.
- **When to change it:** Use `/subject` to add or rename one; edit here only to fix a folder or short name.

### `subjects.timetable`

Your weekly classes: subject, day, start and end.

- **Values:** A list, typed as JSON; `/class` fills it in, and so do a term note and "every Monday at 9 I have a lab".
  **Default:** none.
- **When to change it:** Use `/class` or say it; edit here only to fix a time.

### `subjects.term_note`

The note that holds your term's dates and timetable, read whenever it changes.

- **Values:** A note's path, a pattern, `auto` (find it), or empty (off). **Default:** empty.
- **When to change it:** Set it if your college gives a term calendar you keep as a note; its key dates join the
  deadline list.

### `subjects.term_ends`

The last day of classes; no classes are expected after it.

- **Values:** A date `YYYY-MM-DD`, or empty. **Default:** empty.
- **When to change it:** Set it each term (`/term ends 2026-12-04`) so calls aren't held for classes that are over.

### `subjects.holidays`

Days with no classes.

- **Values:** A list of dates: `["2026-12-25"]`. **Default:** none.
- **When to change it:** Add holidays your timetable should skip (the term note's and a holiday calendar's count too).

### `subjects.exam_periods`

Exam periods: no classes then, exams instead.

- **Values:** A list of `["start", "end"]` date pairs; `/term exams` fills it in. **Default:** none.
- **When to change it:** Set them each term; Exam season and staged updates use them too.

### `subjects.no_calls_in_class`

No calls while a class is on.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if calls during classes are fine (an online course, say).

### `subjects.margin_min`

Minutes around a class when calls already wait (walking in, settling down).

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Raise it if calls catch you on the way to class.
- **Depends on:** `subjects.no_calls_in_class`.

### `subjects.catch_up`

A class you missed gets a catch-up task and a lecture note to fill in.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want catch-up tasks; Went to … on the message takes one back.
- **Costs and what leaves this computer:** Nothing leaves: a task in Deadlines and a stub note.

### `capture.delay_min`

Minutes after a class ends before it asks what happened in it.

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Raise it if the question comes while you're still packing up.
- **Depends on:** After-class notes.

### `capture.subjects`

Ask only after these subjects' classes; empty asks after every subject.

- **Values:** A list of subject short names: `["la", "stats"]`. **Default:** none.
- **When to change it:** Narrow it to the classes where a note is worth it.
- **Depends on:** After-class notes.

### `capture.skip_subjects`

Never ask after these subjects' classes.

- **Values:** A list of subject short names: `["pe"]`. **Default:** none.
- **When to change it:** Add classes where there's nothing to write down.
- **Depends on:** After-class notes.

### `capture.study_log`

Your AI turns your after-class answer into a lecture note.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have your answer saved as you wrote it.
- **Costs and what leaves this computer:** Your answer goes to your AI once per class.
- **Depends on:** After-class notes and Chat with your AI.

### `doubts.before_min`

Open doubts for a subject come this many minutes before its next class.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it if you want time to look them over before class.
- **Depends on:** The Doubt queue.

### `doubts.to_revision`

An open doubt about a topic ranks it with the weak-recall topics in Exam season's revision plan.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if doubts shouldn't change the revision plan.
- **Depends on:** The Doubt queue and Exam season's revision plan.

### `doubts.share`

Open doubts go with a hint request for that subject, and in the brief of a call in the hours before its class.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like hints and calls to connect to what you're unsure of.
- **Costs and what leaves this computer:** The open doubts' words go to your AI (and the call's AI, which may be a cloud
  one).

### `doubts.share_h`

How many hours before a class a call carries its open doubts.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Raise it if your calls before class come earlier in the day.
- **Depends on:** `doubts.share`.

### `doubts.recent_h`

A doubt that names no subject is filed under the class that's on, or ended this many hours ago.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it if doubts land under the wrong class.
- **Depends on:** The Doubt queue.

## Calendar

Your calendar's events in Kurooto, read-only: from a private iCal link, or from Google's Calendar API with the Google
Calendar feature. Events hold calls, #focus events are focus time, private events show only as "Busy (private)", and
shared class calendars offer their deadlines with an Add button. More in [Classes, timetable and
calendar](classes-and-timetable.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Kurooto reads your calendar from its link (or Google's API); nothing is ever
  written back. Event titles reach your AI only when a request needs the day's events, and private ones never do.
- **Depends on:** The Calendar feature (Google calendars: the Google Calendar feature).

### `calendar.days`

How many days ahead Kurooto reads your calendar.

- **Values:** A whole number. **Default:** `14`.
- **When to change it:** Raise it to see deadlines and exams further ahead; lower it on a very busy calendar.

### `calendar.refresh`

How often the calendar is read again.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `every 15m`.
- **When to change it:** Shorten it if events you add late don't show up in time; lengthen it to fetch less.

### `calendar.remind_min`

Minutes before each timed event for a reminder; 0 is off.

- **Values:** A whole number. **Default:** `0`.
- **When to change it:** Set it (say, 10) if you want a nudge before every event.

### `calendar.no_calls_in_events`

No calls while a calendar event is on.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if events in your calendar don't mean you're busy.

### `calendar.nocall_events`

Which events hold calls: every timed one, or only those you tagged.

- **Values:** One of: `all` (every timed event holds calls); `tagged` (#nocall ones and no-call calendars). **Default:**
  `all`.
- **When to change it:** Pick `tagged` if your calendar is full of things that don't mean you're busy; then only #nocall
  events and "no call" calendars hold calls.
- **Depends on:** `calendar.no_calls_in_events`.

### `calendar.mask_private`

Private events show only as "Busy (private)": no title, place or description kept.

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on. Off, private events' titles show again here and to your AI.

### `calendar.private_keyword`

An event with this word in its title or description is private.

- **Values:** A word, e.g. `#private`. **Default:** `#private`.
- **When to change it:** Change it to a tag you already use.
- **Depends on:** `calendar.mask_private`.

### `calendar.class_calendars`

Calendars whose events are classes: they hold calls and get the after-class question.

- **Values:** Names (any part, any case): `["Timetable"]`; `/cal classes Timetable` sets it. **Default:** none.
- **When to change it:** Set it if your timetable lives in a calendar instead of `/class`.

### `calendar.holiday_calendars`

Calendars whose all-day events are holidays (no classes).

- **Values:** Names (any part, any case): `["Holidays"]`. **Default:** none.
- **When to change it:** Set it to your college's holiday calendar so no classes are expected on those days.

### `calendar.shared_offer`

A subscribed calendar's deadlines and exams are offered with an Add button each.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to see shared calendars' entries only as events. They're never added by themselves.

### `google_calendar.skip`

Google calendars to leave out, by any part of their name.

- **Values:** A list: `["Birthdays"]`. **Default:** none.
- **When to change it:** Leave out calendars you don't want read (birthdays, a shared family calendar).
- **Costs and what leaves this computer:** Calendars you skip are never read.
- **Depends on:** The Google Calendar feature.

## Quiz and exams

Spaced practice from your notes, exam mode before a quiz or exam, the optional Exam season with its revision plan and
exam-day help, revision packs, and study packs to give another AI. With Chat on, your AI grades your answers; otherwise
you grade yourself. More in [Quiz and exams](quiz-and-exams.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Quiz questions and your answers go to your AI for grading when Chat is on; a
  quiz call goes through your call line and Gemini Live. Everything else stays here.
- **Depends on:** The Quiz feature (Exam season is a feature of its own).

### `quiz.per_session`

Questions in one quiz.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Raise it for longer sessions; lower it for a quick daily habit.

### `quiz.exam_per_session`

Questions in one quiz while exam mode is on.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Raise it if you want heavier practice close to exams.
- **Depends on:** Exam mode (`deadlines.exam_mode_days`).

### `quiz.offer_at`

The evening before a quiz or exam, practice is offered from this time; empty: never.

- **Values:** A time `HH:MM`, or empty. **Default:** `19:00`.
- **When to change it:** Move it to when you'd study; empty it to stop the offer.

### `quiz.exam_daily`

In exam mode, a practice check-in every day at this time; empty: never.

- **Values:** A time `HH:MM`, or empty. **Default:** empty.
- **When to change it:** Set it (say, `18:00`) for a daily habit in the weeks before exams.
- **Depends on:** Exam mode.

### `quiz.by_call`

/quiz, "quiz me" and quiz check-ins ring you instead of coming as text.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you revise better out loud. Saying "here" keeps one quiz in text.
- **Depends on:** Phone calls.

### `quiz.call_min`

Minutes a quiz call is meant to take.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Change it to fit how long you like to be quizzed.
- **Depends on:** `quiz.by_call`.

### `quiz.links`

Recall cards from the links in your concept graph come by themselves.

A card asks how two linked concepts relate. `/card` gives one any time.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on for small daily recall between sessions.
- **Depends on:** The Concept graph.

### `quiz.links_at`

When a link card may come (never during a class, focus time or the night).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 11:00,16:00,20:00`.
- **When to change it:** Pick times you're usually free for a minute.
- **Depends on:** `quiz.links`.

### `quiz.links_per_day`

The most link cards in a day (at most 5).

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it if they feel like too many.
- **Depends on:** `quiz.links`.

### `quiz.links_check`

A model on this computer says how close your answer to a link card came.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you want feedback on link cards; it never uses a cloud AI.
- **Costs and what leaves this computer:** Nothing leaves: Local AI models only.
- **Depends on:** `quiz.links` and Local AI models.

### `exam_season.hold_updates`

During exams, updates that aren't critical wait until the exams are over.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you want updates as usual during exams.
- **Depends on:** Exam season, with exam periods set (`/term exams`).

### `exam_season.budget`

During exams, only deadlines, quizzes and the alarm come in the day; the rest waits for the evening.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep your usual flow of messages during exams.
- **Depends on:** Exam season.

### `exam_season.no_calls`

Hold every call while an exam is on.

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on; turn it off only if exams aren't on your timetable at their real times.
- **Depends on:** Exam season.

### `exam_season.exam_min`

How long an exam lasts, in minutes (no calls then; the debrief comes half an hour after).

- **Values:** A whole number. **Default:** `180`.
- **When to change it:** Set it to your exams' usual length.
- **Depends on:** Exam season.

### `exam_season.alarm_check`

Every night of the exam period: will tomorrow's alarm ring?

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't use Kurooto's alarm for exam mornings.
- **Depends on:** Exam season and the Morning alarm.

### `exam_season.night_at`

When the nightly alarm check runs.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `21:30`.
- **When to change it:** Set it before you usually go to bed.
- **Depends on:** `exam_season.alarm_check`.

### `exam_season.eve`

The evening before an exam, a checklist: where it is, your seat, calculator, ID card.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you have your exam-day checklist under control.
- **Depends on:** Exam season.

### `exam_season.eve_at`

When the evening-before question can come.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `18:00`.
- **When to change it:** Move it to when you pack your bag.
- **Depends on:** `exam_season.eve`.

### `exam_season.leave_alarm`

On an exam day, an alarm to leave (a call with Phone calls, else a message).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you live next to the exam hall.
- **Depends on:** Exam season.

### `exam_season.leave_min`

Minutes before the exam the leave alarm goes, unless you say a time ("leave 8:10").

- **Values:** A whole number. **Default:** `45`.
- **When to change it:** Set it to your travel time plus a margin.
- **Depends on:** `exam_season.leave_alarm`.

### `exam_season.debrief`

After each exam, a two-minute debrief that goes into the subject's course note.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not look back right after an exam.
- **Costs and what leaves this computer:** Nothing: your debrief is saved as you said it.
- **Depends on:** Exam season.

### `exam_season.quiz_call_at`

When a quiz call you picked rings the evening before an exam.

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `19:00`.
- **When to change it:** Move it to when you'd revise.
- **Depends on:** Exam season and Phone calls.

### `exam_season.quizzes`

Treat quizzes and tests outside an exam period as exams too.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if your quizzes matter as much as exams.
- **Depends on:** Exam season.

### `exam_season.revision`

A revision plan before each exam: its topics ranked and fitted into your free time (/revise).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you plan revision yourself.
- **Costs and what leaves this computer:** Nothing: plain arithmetic on this computer, no AI.
- **Depends on:** Exam season; free time comes from Start-by dates.

### `exam_season.revision_days`

Days before each exam that the revision plan starts.

- **Values:** A whole number. **Default:** `14`.
- **When to change it:** Raise it to spread revision out; lower it for a shorter run-up.
- **Depends on:** `exam_season.revision`.

### `exam_season.revision_share`

The share of your free time (in %) revision blocks may take.

- **Values:** A whole number. **Default:** `50`.
- **When to change it:** Raise it in heavy exam weeks; lower it if the plan crowds out everything else.
- **Depends on:** `exam_season.revision`.

### `exam_season.block_min`

Minutes in one revision block (one topic each).

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Shorten it if you focus better in short bursts.
- **Depends on:** `exam_season.revision`.

### `exam_season.revision_ask`

Each evening: did you cover today's revision topics? (Counts like a quiz answer.)

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not be asked.
- **Depends on:** `exam_season.revision`.

### `skills.auto_pack`

The evening before a quiz or exam, a revision pack: ask first, build it, or never.

- **Values:** One of: `ask` (a button); `auto` (build it); `off`. **Default:** `ask`.
- **When to change it:** Pick `auto` if you always want one; `off` if you never use them.
- **Costs and what leaves this computer:** Building a pack is an AI request with that subject's notes.
- **Depends on:** Skills.

### `skills.auto_pack_after`

Revision packs aren't offered before this time of day (12 to 36 hours before the exam).

- **Values:** A time of day, 24-hour `HH:MM`. **Default:** `16:00`.
- **When to change it:** Move it to when you'd look at one.
- **Depends on:** `skills.auto_pack`.

### `studypack.instructions`

Your own extra lines and a format phrase ("pdf too") go into the study pack's prompt.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to use the plain prompt only.
- **Costs and what leaves this computer:** Nothing leaves: the pack is a zip you send yourself; it never uses your AI.
- **Depends on:** Skills (`/studypack`).

### `studypack.extra`

Your own rules for the other AI, added to the end of every study pack's prompt.

- **Values:** Lines of text, one rule each. **Default:** empty.
- **When to change it:** Add standing instructions ("use my notation", "LaTeX for maths") you'd otherwise type each
  time.
- **Costs and what leaves this computer:** Nothing leaves: it goes into the zip you send yourself.
- **Depends on:** `studypack.instructions`.

### `studypack.cited_pages`

Pages of the readings your class cites ("B&D S2.3") a study pack takes whole, past the usual 250; `0`: off.

The readings your class material cites (a syllabus's "B&D S2.3", "Salby Chapter 2") go into a study pack whole, before
any other book pages and past the usual 250, up to this many pages for all the books.

- **Values:** A number of pages for all the books together; `0`: off (cited pages share the usual 250 and come only with
  a topic, as before 0.8.13). **Default:** `400`.
- **When to change it:** Lower it if the other AI can't hold that much; raise it for a long syllabus. INDEX.md lists
  each citation and the pages it became.
- **Costs and what leaves this computer:** Nothing leaves: the pages go into the zip you send yourself.
- **Depends on:** Skills (`/studypack`), and Books having read the books.

### `quiz.to_doubts`

After a call, the quiz questions you missed on it (graded below 3) are offered as doubts, in one message.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not get that message after quiz calls.
- **Depends on:** The Doubt queue.

### `hints.weak_sign`

Needing the last hint (the key step) counts as a small sign of a gap in Brain's model of what you know.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if hints shouldn't change how Kurooto pitches explanations.
- **Depends on:** Brain, with its model of what you know (`mind.tom.on`).

### `quiz.call_frontier`

On a call, the due questions on concepts you're ready for (Brain's frontier, or partly known) come first.

Only the order of the questions already due changes; none is added or dropped. The call's AI also gets those concepts'
names.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like a call's quiz to aim where you're learning now.
- **Depends on:** Brain, with its model of what you know (`mind.tom.on`).

### `exam_season.use_mastery`

The revision plan places topics with no quiz grade yet by Brain's mastery of their concept, frontier first.

Only within a topic's group (no note, a stub, weak recall, the rest); your grades and answers still decide, and no topic
is dropped.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on with Brain if you'd like its model of what you know to order ungraded topics.
- **Depends on:** Exam season, and Brain with its model of what you know (`mind.tom.on`).

### `exam_season.graph_first`

In exam season, the concept graph reads the courses with an exam in the next revision days first.

Like putting them in `integrate.first` by hand until the exam: their class material and books move up the queue; nothing
is dropped.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like the graph to catch up on what you're about to be examined on.
- **Depends on:** Exam season and the Concept graph.

### `quiz.links_frontier`

Of the link cards due the same day, those on concepts you're ready for (Brain's frontier) come first.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like link cards to aim where you're learning now; an overdue card still
  comes first.
- **Depends on:** `quiz.links` (or `/card`), and Brain's model of what you know.

## Books, study time and handwritten notes

Books and PDFs read overnight into text your AI can cite, the mix of sources (your notes, books, class material) that
goes into answers, the study tracker that counts time per subject, and handwritten pages written out as notes. Reading
happens at night on the charger and carries on the next night. More in [Books and study](books-and-study.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Reading happens on this computer unless an entry says otherwise. The study
  tracker keeps minutes per subject only, never window titles.

### `books.folder`

Your own folder for books, with a subfolder per subject.

- **Values:** A full folder path; empty: `files.folder`, else Kurooto's own. **Default:** empty.
- **When to change it:** Point it at where you already keep your PDFs; `/books folder` says where to drop them.
- **Depends on:** Books and PDFs.

### `books.at`

When the night's book reading begins (on the charger).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 01:00`.
- **When to change it:** Move it to after you've gone to bed; it reads only on the charger.
- **Depends on:** Books and PDFs.

### `books.until`

When the night's reading stops; it carries on the next night from that page.

- **Values:** A time `HH:MM`. **Default:** `07:00`.
- **When to change it:** Move it earlier if the computer's fan wakes you; later for big backlogs.
- **Depends on:** Books and PDFs.

### `books.yield_to_owner`

The night's reading waits while you're in a Voice turn (heard, answered or spoken), then carries on.

Only while the turn lasts; the night's end moves by the wait, so every page still gets its turn that night.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if a local reading model slows Voice down on this computer.
- **Depends on:** Books and PDFs, and Voice (it only waits for a Voice turn).

### `books.max_mb`

PDFs bigger than this (MB) are left alone.

- **Values:** A whole number. **Default:** `400`.
- **When to change it:** Raise it for big scanned books; they take several nights.
- **Depends on:** Books and PDFs.

### `books.ocr`

Who reads scanned pages: Tesseract, a vision model on this computer, either, or nobody.

- **Values:** One of: `auto` (Tesseract, else the vision model); `tesseract`; `vision` (vision model); `off`.
  **Default:** `auto`.
- **When to change it:** Pick `vision` for maths-heavy scans (equations come out as LaTeX) if you have a graphics card;
  `off` to skip scanned pages.
- **Depends on:** Books and PDFs; Tesseract or Local AI models installed for those choices.

### `books.ocr_lang`

Tesseract's languages for scanned pages, e.g. `eng+deu`.

- **Values:** Tesseract language codes joined by `+`; each needs its language data installed. **Default:** `eng`.
- **When to change it:** Add the languages your books are in.
- **Depends on:** `books.ocr` using Tesseract.

### `books.latex`

Which pages the vision model reads for LaTeX: only ones whose maths came out in pieces, all, or never.

- **Values:** One of: `maths` (pages whose maths came out in pieces); `all` (all pages); `never`. **Default:** `maths`.
- **When to change it:** Pick `all` for heavy maths books (slower); `never` to save time.
- **Depends on:** A vision model (Local AI models, graphics cards from 8 GB).

### `books.dpi`

How sharp the page pictures are for reading scanned pages.

- **Values:** A whole number. **Default:** `200`.
- **When to change it:** Raise it for small print (slower, more disk while reading); lower it for speed.
- **Depends on:** Books and PDFs.

### `books.gemini`

Pages nothing on this computer can read go to Google's Gemini as pictures.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on only if your scans are unreadable here and you're fine with those pages going to
  Google.
- **Costs and what leaves this computer:** Those page pictures go to Google with your Gemini key (free limit).
- **Depends on:** A Gemini key.

### `books.gemini_model`

Which Gemini model reads scanned book pages, when `books.gemini` is on.

- **Values:** A Gemini model name. **Default:** `gemini-flash-latest`.
- **When to change it:** Change it when a better or cheaper vision model is out.
- **Costs and what leaves this computer:** Page pictures go to Google with your key.
- **Depends on:** `books.gemini`.

### `books.brain`

Index each book's text into the notes brain, so search by meaning finds it.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep books out of the notes brain's search.
- **Depends on:** The Notes brain (GBrain).

### `books.brain_source`

Which notes-brain source the book text goes into; empty is the default one.

- **Values:** A source name from `gbrain sources list`, or empty. **Default:** empty.
- **When to change it:** Only if you run your own GBrain and keep books in a separate source.
- **Depends on:** `books.brain`.

### `books.duplicates`

A book that's the same file as one already read is linked to it, not read again.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off only if you want copies read separately.
- **Depends on:** Books and PDFs.

### `books.after_read`

A command of yours run after each book is read, with its subject and id added.

- **Values:** A command as a list: `["prog", "-x"]`. **Default:** none.
- **When to change it:** When you want to do something with each new book (copy it, index it elsewhere). It runs as you.
- **Depends on:** Books and PDFs.

### `sources.mix`

How much each kind of source counts in answers: your notes, books, class material.

- **Values:** A JSON object of shares adding up to 1: `{"own": 0.4, "book": 0.3, "classroom": 0.3}`. **Default:** own
  0.4, book 0.3, classroom 0.3.
- **When to change it:** Give books more weight for theory-heavy subjects, your own notes more where you trust them
  most. `/books mix` sets it.
- **Costs and what leaves this computer:** Changes only what goes into a request, not how much.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `sources.prefer`

An order of sources instead of the mix: the first counts most.

- **Values:** A list such as `["own", "book", "classroom"]` (3:2:1); empty uses the mix. **Default:** none.
- **When to change it:** When you'd rather rank sources than set shares.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `sources.cap.book`

The most characters from books in one answer.

- **Values:** A whole number. **Default:** `12000`.
- **When to change it:** Lower it if book text crowds out your notes; raise it for book-led subjects.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `sources.cap.classroom`

The most characters from class material in one answer.

- **Values:** A whole number. **Default:** `10000`.
- **When to change it:** Lower it if slides crowd out the rest.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `sources.cap.own`

The most characters from your own notes in one answer.

- **Values:** A whole number. **Default:** `12000`.
- **When to change it:** Raise it if answers miss what you wrote yourself.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `sources.budget`

Characters of notes, books and class material in all, per answer.

- **Values:** A whole number. **Default:** `24000`.
- **When to change it:** Raise it for deeper answers (more of your AI's limit per request); lower it to keep requests
  small.
- **Costs and what leaves this computer:** More characters means more of your notes go to your AI with each request that
  uses them.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `sources.subjects`

A different mix or order for one subject.

- **Values:** A JSON object: `{"linear-algebra": {"mix": {"book": 0.6, "own": 0.4}}}`. **Default:** none.
- **When to change it:** Use `/books mix` for a subject whose best material is different.
- **Depends on:** Nothing: core. It shapes every request that draws on your notes, books and class material (skills that
  write course notes, answers that cite them).

### `study.idle_min`

Minutes without activity before study time stops counting.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Raise it if reading on screen without touching anything counts as away.
- **Depends on:** The Study tracker.

### `study.sample_s`

Seconds between looks at the window you're working in.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it to look less often (rounder counts); lower it for exact minutes.
- **Depends on:** The Study tracker.

### `study.keywords`

Extra words per subject that count a window for it.

- **Values:** A JSON object: `{"linear-algebra": ["matrix", "eigen"]}`. **Default:** none.
- **When to change it:** Add words that show up in your windows for a subject but aren't its name.
- **Depends on:** The Study tracker.

### `study.research_paths`

Words or folders whose windows count as Research time.

- **Values:** A list of words or folder names. **Default:** none.
- **When to change it:** Add your project folders so time there isn't lost.
- **Depends on:** The Study tracker.

### `study.daily_note`

When the day's study hours go into your daily note; none: never.

- **Values:** A time `HH:MM`, or none. **Default:** `23:45`.
- **When to change it:** Move it to just before you stop for the day.
- **Depends on:** The Study tracker.

### `study.focus_min`

Study mode's timer: minutes of focus (calls and messages wait, the time is logged).

- **Values:** A whole number. **Default:** `25`.
- **When to change it:** Set it to the length you focus well for.
- **Depends on:** The Study tracker; Study mode on the dashboard.

### `study.break_min`

Minutes of break the Study mode timer gives after each focus session.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Set it to the break you actually take.
- **Depends on:** The Study tracker; Study mode on the dashboard.

### `study.timer_ends_mode`

When a focus ends, Study mode ends too, instead of starting a break.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you use one focus session at a time.
- **Depends on:** The Study tracker; Study mode on the dashboard.

### `handwritten.folder`

Where scans of handwritten pages land to be read.

- **Values:** A full folder path; empty: `handwritten-inbox` in your notes (or your files folder). **Default:** empty.
- **When to change it:** Point it at the folder your scanner app saves into.
- **Depends on:** Handwritten notes.

### `handwritten.into`

Where the written-out notes go, inside your notes folder.

- **Values:** A folder inside your notes; empty: your layout's `handwritten/`. **Default:** empty.
- **When to change it:** Pick the folder you want them in.
- **Depends on:** Handwritten notes.

### `handwritten.every`

How often the handwritten-notes folder is checked for new scans.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `every 15m`.
- **When to change it:** Shorten it if you want notes sooner after scanning.
- **Depends on:** Handwritten notes.

### `handwritten.local`

A model on this computer reads the pages when there is one.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to always use Gemini (if `handwritten.cloud` is on).
- **Costs and what leaves this computer:** Nothing leaves: read here.
- **Depends on:** Handwritten notes and Local AI models with a model that reads pictures.

### `handwritten.local_model`

An Ollama model of your choice that reads pictures; empty uses Local AI models' pick.

- **Values:** An Ollama model name. **Default:** empty.
- **When to change it:** When you know a model that reads your handwriting better.
- **Costs and what leaves this computer:** Downloaded from Ollama's registry once.
- **Depends on:** `handwritten.local`.

### `handwritten.cloud`

With no model on this computer, Gemini reads the pages; off, they wait for a model here.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep your handwriting on this computer.
- **Costs and what leaves this computer:** Page pictures go to Google with your Gemini key.
- **Depends on:** Handwritten notes, a Gemini key.

### `handwritten.model`

Which Gemini model reads handwriting when it's used.

- **Values:** A Gemini model name. **Default:** `gemini-flash-latest`.
- **When to change it:** Change it when a better vision model is out.
- **Costs and what leaves this computer:** Page pictures go to Google with your key.
- **Depends on:** `handwritten.cloud`.

### `handwritten.pdf_hours`

When the model on this computer reads PDFs (on the charger); empty: any time.

- **Values:** `HH:MM-HH:MM`, or empty. **Default:** `23:00-07:00`.
- **When to change it:** Empty it if you want PDFs read straight away and the computer can take it.
- **Depends on:** `handwritten.local`.

### `handwritten.max_pages`

The most pages written out per PDF.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it for long notebooks.
- **Depends on:** Handwritten notes.

### `handwritten.dpi`

How sharp the pictures of handwritten pages are when they're read.

- **Values:** A whole number. **Default:** `110`.
- **When to change it:** Raise it if small handwriting is misread; lower it for speed.
- **Depends on:** Handwritten notes.

### `handwritten.keep_original`

Keep a copy of the scan next to the note, or link to where it already is.

- **Values:** One of: `copy` (next to the note); `link` (leave it where it is). **Default:** `copy`.
- **When to change it:** Pick `link` if your scans already live somewhere tidy and you don't want copies.
- **Depends on:** Handwritten notes.

### `handwritten.link`

Link each written-out note to its lecture, course page and concept notes.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to save one AI request per note.
- **Costs and what leaves this computer:** One AI request per note, with the note's text.
- **Depends on:** Handwritten notes.

## Notes, files and sync

How your notes folder is laid out and linked, where files outside it go, Notes sync to a private GitHub repository, the
sorter that files notes from a scratch folder, and Find files. Kurooto writes only inside its own blocks in your notes
and never rewrites your text. More in [Notes and the concept graph](notes-and-concept-graph.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer, except with Notes sync (your notes go to your
  own private GitHub repository) and the sorter's short question to your AI.
- **Depends on:** Nothing: core settings, always there.

### `notes.layout`

How your notes folder is laid out: Kurooto's folders, or a Zettelkasten.

- **Values:** `kurooto` (journal/, about-me/, a folder per subject) or `zettelkasten` (dailies/, master/, sources/,
  zettel/). **Default:** `kurooto`.
- **When to change it:** Pick the one closest to how you already keep notes. The setup page's Notes step reads your
  folder and moves Kurooto's own notes to fit, with Undo.

### `notes.paths`

Your own place for a kind of note, over the layout's.

- **Values:** A JSON object, kind → path: `{"daily": "journal/{date}.md", "doubts": "school/doubts.md"}`. **Default:**
  none.
- **When to change it:** When one kind of note should live somewhere else than the layout puts it. New notes of that
  kind go there.

### `notes.links`

How Kurooto links notes: `[[wikilinks]]` or Markdown links.

- **Values:** `wiki` (`[[path|Name]]`) or `markdown` (`[Name](path.md)`, relative). **Default:** `wiki`.
- **When to change it:** Pick `markdown` if you read your notes outside Obsidian (GitHub, a static site). Only new links
  change; old ones stay.

### `notes.open_with`

The program that opens a note from the dashboard; empty uses the system's.

- **Values:** A command, with `{path}` for the note: `kitty nvim {path}`. **Default:** empty.
- **When to change it:** Set it to open notes in your own editor.

### `files.folder`

A folder for files outside your notes (course files, PDFs); empty keeps them inside the notes.

- **Values:** A full folder path, or empty. **Default:** empty.
- **When to change it:** Set it to keep big files out of your notes (and out of Notes sync's repository).

### `files.links`

How notes link to files outside the notes folder.

- **Values:** Empty (the layout's way), `relative`, or `file` (`file://` links). **Default:** empty.
- **When to change it:** Pick `file` if your note app can't follow relative links out of the notes folder.
- **Depends on:** `files.folder`.

### `notes_sync.repo`

The private GitHub repository your notes sync to.

- **Values:** `owner/name`. Kurooto refuses a public repository. **Default:** empty.
- **When to change it:** Set during Notes sync's setup, with a token for just that repository.
- **Costs and what leaves this computer:** Your whole notes folder is copied to that private repository on GitHub, and
  kept in step.
- **Depends on:** Notes sync.

### `notes_sync.every`

How often your notes sync.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `every 10m`.
- **When to change it:** Shorten it if you edit on several devices; lengthen it to sync less often.
- **Costs and what leaves this computer:** Changed notes go up to GitHub each time.
- **Depends on:** Notes sync.

### `notes_sync.after_jobs`

Minutes after an AI request finishes that the notes it wrote go up; 0 waits for the timer.

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Set 0 to sync only on the timer.
- **Depends on:** Notes sync.

### `notes_sync.on_conflict`

When a note changed in two places at once: keep both versions, or stop and wait for you.

- **Values:** `keep both` (this computer's copy goes next to it as a conflict note) or `stop` (sync stops, changes
  nothing, tells you once). **Default:** `keep both`.
- **When to change it:** Pick `stop` if you'd rather sort out every clash yourself. Nothing is lost either way.
- **Depends on:** Notes sync.

### `notes_sync.branch`

The branch your notes sync to (filled in from the repository).

- **Values:** Text. **Default:** `main`.
- **When to change it:** Only if you keep notes on another branch than the repository's default.
- **Depends on:** Notes sync.

### `notes_sync.share_with_calls`

Let your call line read notes from your repository during a call while this computer is off.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if calls shouldn't read your notes at all while the computer is away.
- **Costs and what leaves this computer:** Your call line reads notes from GitHub during a call, with the sync token.
- **Depends on:** Notes sync and Phone calls.

### `notes_sync.api`

The Git host's API address. Leave it alone.

- **Values:** Text. **Default:** `https://api.github.com`.
- **When to change it:** Only for GitHub Enterprise or tests.
- **Costs and what leaves this computer:** Sync talks to this address.
- **Depends on:** Notes sync.

### `notes_sync.remote`

For tests only: a local repository instead of GitHub.

- **Values:** Text. **Default:** empty.
- **When to change it:** Never in normal use.
- **Depends on:** Notes sync.

### `sorter.folder`

The scratch folder inside your notes: what lands here is sorted into place.

- **Values:** A folder inside your notes. **Default:** `inbox`.
- **When to change it:** Point it at the folder you already dump notes into.
- **Depends on:** The Notes sorter.

### `sorter.at`

When the nightly sorting pass runs (`/sort now` runs one any time).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 03:30`.
- **When to change it:** Move it to when the computer is on and you're not writing.
- **Depends on:** The Notes sorter.

### `sorter.per_night`

The most notes the sorter moves in one day.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Raise it to clear a big backlog; lower it to keep each morning's list short.
- **Depends on:** The Notes sorter.

### `sorter.min_conf`

How sure a guess must be (0 to 1) before a note is moved; below it, you get Move buttons.

- **Values:** A number. **Default:** `0.75`.
- **When to change it:** Raise it if notes land in the wrong place; lower it if too many wait for you.
- **Depends on:** The Notes sorter.

### `sorter.ai`

Ask your AI about a note the rules can't place; off, rules only.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep notes away from the AI; unplaced notes then wait for you.
- **Costs and what leaves this computer:** The note's first lines and your folder names go to your AI, one short request
  per note.
- **Depends on:** The Notes sorter.

### `sorter.settle_min`

A note touched in the last this-many minutes is left alone (you may still be writing it).

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Raise it if notes get moved while you're writing.
- **Depends on:** The Notes sorter.

### `sorter.learn`

A note you move again after it was filed teaches the sorter where such notes go.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you move notes around for other reasons.
- **Depends on:** The Notes sorter.

### `sorter.recheck`

Weekly: a note it moved that now clearly fits another folder moves once more (with Undo).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if notes should stay where they were first put.
- **Depends on:** The Notes sorter.

### `sorter.duplicates`

A note in the scratch folder that copies one you have is asked about, not filed.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to file copies like any other note.
- **Depends on:** The Notes sorter.

### `sorter.by_class`

A note written in or just after a class gets that class's folder as a hint: in the AI's request, and the first Move
button if it waits.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you jot notes in class and drop them in the scratch folder.
- **Depends on:** The Notes sorter, Subjects with a timetable.

### `sorter.read_files`

Documents dropped in the scratch folder (PDF, Word, slides, text) become notes.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to drop documents in and get notes out.
- **Depends on:** The Notes sorter.

### `sorter.read_mb`

The biggest file the sorter reads, in MB.

- **Values:** A whole number. **Default:** `25`.
- **When to change it:** Raise it for big documents.
- **Depends on:** `sorter.read_files`.

### `finder.folders`

The folders Find files indexes and searches (`/find add <folder>` adds one).

- **Values:** A list of full paths (`~` allowed). **Default:** none.
- **When to change it:** Add folders you look for files in. Keys, passwords and hidden folders are never read.
- **Costs and what leaves this computer:** Nothing leaves: the index stays on this computer. A file is sent only when
  you tap Send (to your own Telegram).
- **Depends on:** Find files.

### `finder.max_files`

The most files Find files indexes.

- **Values:** A whole number. **Default:** `60000`.
- **When to change it:** Raise it for big folders; lower it to keep the index small.
- **Depends on:** Find files.

### `finder.read_mb`

Files bigger than this (MB) have their name indexed but not their text.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Raise it to search inside bigger PDFs (slower indexing).
- **Depends on:** Find files.

## Notes brain (GBrain)

An index of your notes folder you can search by meaning (`/notes <question>`), which your AI also uses as memory. It
runs on this computer with its own database. Its nightly extras each have their own switch; the ones that would rewrite
your notes or call an AI model are left out unless you add them. More in [Notes and the concept
graph](notes-and-concept-graph.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer, except note text sent to Google for embeddings
  when `gbrain.embeddings` is `gemini`.
- **Depends on:** The Notes brain (GBrain) feature.

### `gbrain.embeddings`

How the notes brain makes its search-by-meaning index: a model here, Google's, or keywords only.

- **Values:** `auto` (picked for your computer), `ollama` (a model on this computer), `gemini` (your key), `off`
  (keyword search only). **Default:** `auto`.
- **When to change it:** Pick `ollama` to keep note text on this computer if you have a graphics card or Apple Silicon;
  `off` for keyword search only.
- **Costs and what leaves this computer:** `gemini` sends your notes' text to Google to be embedded; `ollama` and `off`
  keep it here.

### `gbrain.sync`

How often your notes are read into the notes brain.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `every 15m`.
- **When to change it:** Shorten it if new notes take too long to show up in search; lengthen it on a slow computer.

### `gbrain.timelines`

Nightly, dated log lines in your notes become each note's timeline (`/timeline <note>`).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't write dated log lines. No AI, nothing leaves.

### `gbrain.course_pages`

Nightly, each course page gets its key concepts and a dated timeline, in Kurooto's own block.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want Kurooto's block on your course pages. Your own text is never
  touched.

### `gbrain.course_announcements`

The course page's timeline also has the course's Classroom posts and the dated lines under its Announcements heading.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if announcements make the timeline too long.
- **Depends on:** `gbrain.course_pages`.

### `gbrain.upkeep`

Nightly upkeep of the brain (links, facts, the index), light steps only; waits for the charger.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on for a tidier, faster brain over time.

### `gbrain.upkeep_steps`

Which upkeep steps run (GBrain's own phase names); empty: the light ones.

- **Values:** A list of GBrain phase names. **Default:** none.
- **When to change it:** Add steps only if you know what they do: some rewrite note files or call an AI model. Kurooto
  never runs purge.
- **Costs and what leaves this computer:** Steps that call an AI model send note text to the model GBrain is set up
  with.
- **Depends on:** `gbrain.upkeep`.

### `gbrain.nightly`

When the brain's nightly timelines and upkeep run.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 03:00`.
- **When to change it:** Move it to when the computer is on and charging.

### `gbrain.checkup_line`

Once a week, one line on how the notes brain is (read only).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want the line.

### `gbrain.checkup`

A weekly checkup of the brain; a message only when something needs a look.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you run a big brain and want to hear about problems early.

### `gbrain.checkup_when`

When the weekly checkup runs.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `weekly sun 19:30`.
- **When to change it:** Move it to when you'd deal with a finding.
- **Depends on:** `gbrain.checkup`.

### `gbrain.checkup_ignore`

Checkup findings starting with these words aren't reported.

- **Values:** A list of words. **Default:** `["backup_", "mcp_", "chronicle", "auto_chronicle", "uninstalled_",
  "publish_skills_off", "writeback_consent", "versio…`.
- **When to change it:** Add a finding's first word if it keeps coming up and doesn't matter to you.
- **Depends on:** `gbrain.checkup`.

### `gbrain.contradictions`

The brain's last contradictions report joins Dreaming's morning section, with Keep A / Keep B.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't run GBrain's contradictions check. Kurooto only reads the report; you
  make it.
- **Depends on:** Dreaming.

### `gbrain.managed`

Kurooto runs its own notes brain; off, it uses a GBrain you already run.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off only if you have your own GBrain (on Postgres, say). Kurooto then never creates,
  migrates or reconfigures it.

### `gbrain.exe`

Your own GBrain: your gbrain program; empty uses the one on your PATH.

- **Values:** A full path, or empty. **Default:** empty.
- **When to change it:** Set it if your gbrain isn't on PATH.
- **Depends on:** `gbrain.managed` off.

### `gbrain.home`

Your own GBrain: its GBRAIN_HOME folder; empty uses GBrain's default.

- **Values:** A full path, or empty. **Default:** empty.
- **When to change it:** Set it if your brain lives somewhere other than GBrain's default.
- **Depends on:** `gbrain.managed` off.

### `gbrain.source`

Your own GBrain: the source that is your notes folder, kept in step every 15 minutes.

- **Values:** A source name, or empty (you keep it in step yourself). **Default:** empty.
- **When to change it:** Name it if you want Kurooto to sync and embed your notes into your brain for you.
- **Depends on:** `gbrain.managed` off.

### `gbrain.agy_mcp`

Your own GBrain: agy gets its MCP tools too (you're asked first).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to let agy search and read your brain directly during requests.
- **Costs and what leaves this computer:** agy reads from your brain; what it reads goes to agy's service with the
  request.
- **Depends on:** `gbrain.managed` off, agy as your AI.

### `gbrain.mcp_surface`

What your brain's MCP server offers agy: everything, a starter set, or only verbs.

- **Values:** One of: `full`; `starter`; `verbs`. **Default:** `full`.
- **When to change it:** Pick `starter` or `verbs` to give agy fewer tools to choose from.
- **Depends on:** `gbrain.agy_mcp`.

## Concept graph

What you read in books and class material, woven into the notes you already have: a concept note per new concept, typed
links with reasons, "Seen in" lines on existing notes. It works at night, batch after batch, within a budget of your
AI's limit. Only lines are added; nothing you wrote is changed. More in [Notes and the concept
graph](notes-and-concept-graph.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Each batch of pages goes to your AI (the bulk AI), and doubtful answers to a
  second one (the check AI), within `integrate.share_pct` of its limit; with an API key, within
  `integrate.max_cost_per_night`.
- **Depends on:** The Concept graph feature, and Books and PDFs or Classroom → notes for something to read.

### `integrate.sources`

What's read into the graph: books, Classroom files, handwritten notes, repositories, reference files, papers.

- **Values:** A list of `books`, `classroom`, `handwritten`, `repos`, `reference` (files from the inbox), `papers`
  (papers you add to Zotero from the research digest, read after the books). **Default:** `["books", "classroom",
  "reference"]`.
- **When to change it:** Add `handwritten` once your handwritten notes are written out; remove one to stop reading it.

### `integrate.at`

When the night's reading starts (it carries on batch after batch).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 01:30`.
- **When to change it:** Move it to after you've stopped using your AI for the day.

### `integrate.per_night`

How many batches a night: fitted to your AI's plan, or a number you set as a hard ceiling.

- **Values:** `auto`, or a whole number. **Default:** `auto`.
- **When to change it:** Set a number if the reading uses more of your AI than you like.

### `integrate.share_pct`

The most of a subscription's usage window (or a free key's day) the reading may take, in %.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Lower it if you run short of your AI the next morning; raise it to get through books faster.

### `integrate.max_cost_per_night`

With a paid API key: the most a night's reading may cost, in US dollars.

- **Values:** A number. **Default:** `0.5`.
- **When to change it:** Raise it to read faster; lower it to spend less.
- **Costs and what leaves this computer:** This is money on your API key's bill, as the service reports it.

### `integrate.price_per_mtok.in`

An API key that reports no cost: its price per million input tokens (USD), for the estimate.

- **Values:** A number. **Default:** `2.0`.
- **When to change it:** Set it to your key's real price so the night's budget is right.

### `integrate.price_per_mtok.out`

An API key that reports no cost: its price per million output tokens (USD), for the estimate.

- **Values:** A number. **Default:** `8.0`.
- **When to change it:** Set it to your key's real price so the night's budget is right.

### `integrate.batch_pages`

About how many pages go into one request.

- **Values:** A whole number. **Default:** `12`.
- **When to change it:** Lower it if requests time out or answers get sloppy; raise it to read faster.

### `integrate.roles.bulk`

The AI that does the bulk reading; empty is chosen for you.

- **Values:** An AI id (`agy`, `claude`, `gemini`…), or empty. **Default:** empty.
- **When to change it:** Pick the AI with the most room in its limit.
- **Costs and what leaves this computer:** The pages go to that AI.

### `integrate.roles.check`

The AI that takes the second look at doubtful answers; empty is chosen for you.

- **Values:** An AI id, or empty. **Default:** empty.
- **When to change it:** Pick a different AI from the bulk one for a real second opinion.
- **Costs and what leaves this computer:** Doubtful answers and their pages go to that AI.

### `integrate.first`

Subjects to read first.

- **Values:** A list of subject short names: `["deep-learning"]`. **Default:** none.
- **When to change it:** Put the subject you're studying now first.

### `integrate.order`

Which books first: the smallest (most books done soonest) or by name.

- **Values:** One of: `smallest` (fewest pages first); `name`. **Default:** `smallest`.
- **When to change it:** Pick `name` if you want them in a fixed order.

### `integrate.garden`

A daily second pass that links the notes the reading touched and notes nothing links to yet.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to save AI requests; links then come only from the first reading.

### `integrate.garden_at`

When the daily second pass runs (`/graph garden` runs it now).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 06:20`.
- **When to change it:** Move it to a time your AI is free.
- **Depends on:** `integrate.garden`.

### `integrate.garden_per_day`

The most notes in the daily second pass.

- **Values:** A whole number. **Default:** `40`.
- **When to change it:** Lower it to spend less of your AI's limit.
- **Depends on:** `integrate.garden`.

### `integrate.embeddings`

How related notes are found by meaning: a model here, Google's, or not at all.

- **Values:** One of: `auto`; `ollama` (a model on this computer); `gemini` (your key); `off`. **Default:** `auto`.
- **When to change it:** Pick `ollama` to keep note text here; `off` matches by keywords and names only.
- **Costs and what leaves this computer:** `gemini` sends note text to Google to be embedded.

### `integrate.rerank`

A local model judges which notes belong together (a graphics card helps).

- **Values:** One of: `auto`; `off`. **Default:** `auto`.
- **When to change it:** Turn it off on a slow computer.
- **Costs and what leaves this computer:** Nothing leaves: a model on this computer.

### `integrate.rerank_model`

Which local model does that judging; empty uses this computer's helper model.

- **Values:** An Ollama model name, or empty. **Default:** empty.
- **When to change it:** Only if you have a better reranking model.
- **Costs and what leaves this computer:** Downloaded from Ollama's registry once.
- **Depends on:** `integrate.rerank`.

### `integrate.commit`

One git commit per batch, when your notes folder is a repository.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you commit your notes yourself.
- **Costs and what leaves this computer:** Nothing leaves: a local commit (Notes sync sends it up later, if that's on).

### `integrate.summary`

One line each morning about what the reading changed.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want the line.
- **Costs and what leaves this computer:** One Telegram message.

### `integrate.duplicates`

Each morning, up to three pairs of look-alike concept notes: Merge / Keep both / Add alias.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave look-alikes as they are.

### `integrate.duplicates_all`

Each morning, also ask about notes of any kind that are copies of each other, old ones included.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to be asked only about concept notes.

### `integrate.duplicates_per_day`

How many pairs of copied notes it asks about in a day, at most.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it if the morning list is long.

### `integrate.auto_merge`

Look-alike concept notes that are clearly one concept merge by themselves (Undo in the morning line).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to be asked about every pair. It only ever merges notes Kurooto wrote.

### `integrate.auto_merge_min`

How alike two notes must be (0.92 to 1) to merge without asking.

- **Values:** A number. **Default:** `0.97`.
- **When to change it:** Raise it if merges surprise you; it never goes below 0.92.
- **Depends on:** `integrate.auto_merge`.

### `integrate.yield_to_owner`

The concept graph's next batch waits while you're in a Voice turn, and starts a minute after it ends.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if the graph's reading on a local model slows Voice down.
- **Depends on:** The Concept graph, and Voice (it only waits for a Voice turn).

### `integrate.notation`

A Notation table when a second source writes a concept differently.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want notation tables on concept notes.

## Google: Classroom, Gmail, Calendar and Drive

Classroom deadlines and materials, the Gmail digest and reply drafts, Email in, Google Calendar, the Agent plan calendar
and Drive upload, through your own Google sign-in. Each feature asks Google for its own permission when you set it up;
Gmail is only read (nothing sent, deleted or marked read) except for drafts you tap Send on. More in [Google: Classroom,
Gmail, Calendar and Drive](google.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Kurooto talks to Google's APIs with your own sign-in. What your AI may read
  of your mail is only what your read rules allow; everything else is only counted, here.
- **Depends on:** The Google feature, signed in.

### `google.accounts`

The names of your signed-in Google accounts; "main" is the one you signed in with first.

- **Values:** A list of short names: `["main", "school"]`. **Default:** `["main"]`.
- **When to change it:** Add an account on the Google card (or `/google add school`) to use, say, a school account for
  Classroom.

### `google.use`

Which of your Google accounts each feature uses; unset means main.

- **Values:** A JSON object: `{"mail_digest": "school", "calendar_read": ["main", "school"]}`. **Default:** none.
- **When to change it:** Pick per feature on its card, or `/google use mail school`.

### `google.classroom`

Read Classroom: courses, assignments and announcements, for deadlines.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only want other Google features.
- **Costs and what leaves this computer:** Read-only access to your Classroom courses and coursework.

### `google.classroom_on_calls`

A call's brief gets the titles of the last day's Classroom posts.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like calls to mention new Classroom posts.
- **Costs and what leaves this computer:** The posts' course names and titles go to the call's AI (Gemini Live on your
  key, or your call AI).
- **Depends on:** `google.classroom` and Phone calls.

### `google.classroom_every`

How often Classroom is checked for new deadlines.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `every 3h`.
- **When to change it:** Shorten it in busy weeks; lengthen it to check less.
- **Depends on:** `google.classroom`.

### `google.classroom_notes`

Permission for Classroom → notes: materials and attached Drive files, read-only.

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up Classroom → notes; Google asks you to allow it.
- **Depends on:** Classroom → notes.

### `google.mail_digest`

Permission for the mail digest: read Gmail, read-only.

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up the Mail digest; Google asks you to allow it.
- **Depends on:** The Mail digest.

### `google.reply_drafts`

Permission for reply drafts in Gmail, sent only when you tap Send.

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up Email reply drafts.
- **Depends on:** Email reply drafts.

### `google.gmail_drafts`

Allow `/draft` to save drafts in your Gmail (one more sign-in: Google calls it a restricted permission).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you want to draft mail from Telegram.
- **Costs and what leaves this computer:** Kurooto may create drafts in your Gmail; it never sends without your tap.

### `google.digest_email`

Permission to send the mail digest to your own inbox (send only).

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up Mail digest by email.
- **Depends on:** Mail digest by email.

### `google.calendar_read`

Permission to read your calendars (Google Calendar), read-only.

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up Google Calendar.
- **Depends on:** Google Calendar.

### `google.agent_calendar`

Permission for Kurooto's own "Agent plan" calendar (it can't see your others).

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up the Agent plan calendar.
- **Depends on:** Agent plan calendar.

### `google.drive_upload`

Permission to put files you send yourself into a Kurooto folder in Drive (its own files only).

- **Values:** On or off. **Default:** off.
- **When to change it:** Set for you when you set up Drive upload.
- **Depends on:** Drive upload.

### `google.endpoints.auth`

Google's sign-in address. Leave it alone.

- **Values:** Text. **Default:** `https://accounts.google.com/o/oauth2/v2/auth`.
- **When to change it:** Only for tests or a proxy.

### `google.endpoints.token`

Google's token address. Leave it alone.

- **Values:** Text. **Default:** `https://oauth2.googleapis.com/token`.
- **When to change it:** Only for tests or a proxy.

### `google.endpoints.calendar`

Google Calendar's API address. Leave it alone.

- **Values:** Text. **Default:** `https://www.googleapis.com/calendar/v3`.
- **When to change it:** Only for tests or a proxy.

### `google.endpoints.classroom`

Google Classroom's API address. Leave it alone.

- **Values:** Text. **Default:** `https://classroom.googleapis.com/v1`.
- **When to change it:** Only for tests or a proxy.

### `google.endpoints.gmail`

Gmail's API address. Leave it alone.

- **Values:** Text. **Default:** `https://gmail.googleapis.com/gmail/v1`.
- **When to change it:** Only for tests or a proxy.

### `google.endpoints.drive`

Google Drive's API address. Leave it alone.

- **Values:** Text. **Default:** `https://www.googleapis.com/drive/v3`.
- **When to change it:** Only for tests or a proxy.

### `google.endpoints.drive_upload`

Google Drive's upload address. Leave it alone.

- **Values:** Text. **Default:** `https://www.googleapis.com/upload/drive/v3`.
- **When to change it:** Only for tests or a proxy.

### `classroom_notes.at`

When new Classroom posts are fetched into your notes.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 07:00,13:00,19:00`.
- **When to change it:** Add or move times to match when your teachers usually post.
- **Depends on:** Classroom → notes.

### `classroom_notes.files`

Download the Drive files attached to posts and read their text into your notes.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep only the posts, with links to the files.
- **Costs and what leaves this computer:** Downloads from your Drive to this computer.
- **Depends on:** Classroom → notes.

### `classroom_notes.max_file_mb`

Attached files bigger than this (MB) are only linked, not downloaded.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it for big lecture recordings or scans.
- **Depends on:** `classroom_notes.files`.

### `classroom_notes.folders`

Which notes folder each course goes into, where Kurooto's own pick is wrong.

- **Values:** A JSON object, a course's exact name → folder: `{"MA101 Linear Algebra (2026)": "linear-algebra"}`.
  **Default:** none.
- **When to change it:** Set it when a course lands in the wrong folder.
- **Depends on:** Classroom → notes.

### `classroom_notes.skip`

Courses to leave out, by words from their names (`/classnotes skip` fills it).

- **Values:** A list of words. **Default:** none.
- **When to change it:** Add clubs and old courses you don't want in your notes.
- **Depends on:** Classroom → notes.

### `classroom_notes.backfill_days`

How far back (days) it looks; older posts not edited since are left alone.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it once to bring in a whole term's material.
- **Depends on:** Classroom → notes.

### `mail_digest.at`

When the mail digest checks your Gmail.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 08:00,18:00`.
- **When to change it:** Set the times you'd like a summary of your mail.
- **Depends on:** The Mail digest.

### `mail_digest.read`

What the AI may read for the digest: senders, @domains or Gmail labels you chose.

- **Values:** A list: `["label:Courses", "sam@example.org", "@school.example"]`; `/mail read` fills it. **Default:**
  none.
- **When to change it:** Add the senders and labels that matter. Everything else is only counted, never summarised.
- **Costs and what leaves this computer:** Mail matching these goes to your AI to be summarised.
- **Depends on:** The Mail digest.

### `mail_digest.never_read`

Senders, @domains or labels the digest never reads, even if chosen elsewhere.

- **Values:** A list; `/mail never` fills it. **Default:** none.
- **When to change it:** Add anything that must never reach the AI (a bank, a doctor).
- **Depends on:** The Mail digest.

### `mail_digest.own_domain`

On a school or work account, mail from your own organisation's domain is read too.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if your organisation's mail shouldn't go to your AI.
- **Costs and what leaves this computer:** Your organisation's mail goes to your AI to be summarised.
- **Depends on:** The Mail digest.

### `mail_digest.query`

A Gmail search: mail it matches is read too, e.g. everything but Promotions and Social.

- **Values:** Gmail search words, e.g. `-category:promotions -category:social`; empty: none. **Default:** empty.
- **When to change it:** Use it to widen what's read without listing senders. Personal mail is still only counted.
- **Costs and what leaves this computer:** Matching mail goes to your AI.
- **Depends on:** The Mail digest.

### `mail_digest.on_calls`

A call's brief gets the last digest's "Needs you" line, so the call can bring it up.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like calls to remind you of mail that needs you.
- **Costs and what leaves this computer:** That line goes to the call's AI (Gemini Live on your key, or your call AI).
  Confidential and personal mail never reach it.
- **Depends on:** The Mail digest and Phone calls.

### `mail_digest.first_days`

How far back (days) the first digest looks.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Raise it once if you want older mail in the first digest.
- **Depends on:** The Mail digest.

### `mail_digest.max_messages`

The most mails looked at per check.

- **Values:** A whole number. **Default:** `200`.
- **When to change it:** Raise it for a busy inbox; mails over the limit wait for the next check.
- **Depends on:** The Mail digest.

### `mail_digest.save_note`

A copy of each digest goes into your notes (mail/).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to get digests only as messages.
- **Depends on:** The Mail digest.

### `mail_digest.skip_confidential`

Mail marked confidential is only counted: never read by the AI, summarised or answered.

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on, especially on a work or school account.
- **Depends on:** The Mail digest.

### `mail_digest.confidential_words`

The markings that make a mail confidential (in its subject, text or a label).

- **Values:** A list of regular expressions, any case; a space matches any run of spaces or line breaks. **Default:**
  `["confidential", "do not forward", "restricted", "private and confidential", "privileged and confidential",
  "propriet…`.
- **When to change it:** Add your organisation's own marking if it uses another phrase.
- **Depends on:** `mail_digest.skip_confidential`.

### `mail_digest.confidential`

What happens to confidential mail: only counted, or summarised by a model on this computer.

- **Values:** `count` (only counted) or `local` (summarised here by a local model, kept only in Kurooto's data folder).
  **Default:** `count`.
- **When to change it:** Pick `local` if you want confidential mail summarised and have Local AI models.
- **Costs and what leaves this computer:** Nothing leaves either way: `local` runs on this computer.
- **Depends on:** `mail_digest.skip_confidential`; Local AI models for `local`.

### `mail_digest.local_model`

Which Ollama model summarises confidential mail; empty uses Local AI models' helper.

- **Values:** An Ollama model name, or empty. **Default:** empty.
- **When to change it:** Pick a bigger model for better summaries if your computer can run it.
- **Costs and what leaves this computer:** Nothing leaves: a model on this computer.
- **Depends on:** `mail_digest.confidential` = `local`.

### `mail_digest.mail_in`

Email in: mail you forward to you+kurooto@ (or label) is filed into your notes, its dates as buttons.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on (`/mail in on`) to send things into your notes by email.
- **Costs and what leaves this computer:** That mail goes to your AI to be filed.
- **Depends on:** The Mail digest.

### `mail_digest.mail_in_label`

A Gmail label whose mail goes into your notes too, from anyone.

- **Values:** A Gmail label's name, or empty. **Default:** empty.
- **When to change it:** Set it with a Gmail filter that labels mail you want filed.
- **Depends on:** `mail_digest.mail_in`.

### `mail_digest.mail_in_senders`

Your other email addresses that may send mail into your notes (your own always can).

- **Values:** A list of email addresses. **Default:** none.
- **When to change it:** Add your phone's or work's address if you forward from there.
- **Depends on:** `mail_digest.mail_in`.

### `mail_digest.mail_in_anyone`

Mail to +kurooto from anyone goes in. A stranger could then write into your notes.

- **Values:** On or off. **Default:** off.
- **When to change it:** Leave it off unless you know why you need it.
- **Depends on:** `mail_digest.mail_in`.

### `mail_digest.mail_in_every`

How often Gmail is checked for mail you sent in.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `every 10m`.
- **When to change it:** Shorten it if you want forwarded mail filed sooner.
- **Depends on:** `mail_digest.mail_in`.

### `reply_drafts.per_day`

The most reply drafts written in a day.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Raise it for a busy inbox; lower it to spend less of your AI.
- **Costs and what leaves this computer:** Each draft is an AI request with the mail it answers.
- **Depends on:** Email reply drafts.

### `reply_drafts.ask_days`

Days the Send / Edit / Discard question on a draft stays open.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Shorten it so old drafts stop lingering.
- **Depends on:** Email reply drafts.

### `agent_plan.name`

The name of Kurooto's own calendar for the time blocks it plans with you.

- **Values:** A calendar name. **Default:** `Agent plan`.
- **When to change it:** Rename it to tell it apart from your own calendars. Kurooto writes only to this one.
- **Depends on:** The Agent plan calendar.

### `agent_plan.remind_min`

Minutes before each planned block for Google's pop-up reminder; 0: none.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Set 0 if Kurooto's own reminders are enough.
- **Depends on:** The Agent plan calendar.

### `drive_upload.big_files`

A file too big for Telegram (over 50 MB) comes as a Drive link instead of failing.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have big files refused rather than uploaded.
- **Costs and what leaves this computer:** Those files go to your Google Drive.
- **Depends on:** Drive upload.

### `drive_upload.folder`

The Google Drive folder files go to.

- **Values:** A folder name in your Drive. **Default:** `Kurooto`.
- **When to change it:** Rename it if you'd like another folder.
- **Depends on:** Drive upload.

### `drive_upload.temp_days`

Days a too-big-for-Telegram upload is kept in your Drive before it's deleted; 0 keeps them.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Set 0 to keep every upload; raise it if you need the links longer.
- **Depends on:** Drive upload.

## Research, projects and proposals

A digest of new papers, your code repositories' commits and runs written into project logs, projects set up from a
repository, help with a project in a scratch folder, and proposals: every change the AI wants to make to your files
comes as a diff you apply, change or discard. Nothing in a repository is ever run except a check you set. More in
[Research](research.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Paper searches go to arXiv, bioRxiv, PubMed and your feeds; ranking, project
  help and minutes go to your AI. Repositories are read on this computer.
- **Depends on:** The Research feature.

### `research.about`

What you work on, in a sentence or two: the AI uses it to pick papers for you.

- **Values:** A sentence or two. **Default:** empty.
- **When to change it:** Write it once; update it when your research changes. Better picks follow at the next digest.
- **Costs and what leaves this computer:** It goes to your AI with each digest's ranking request.

### `research.feeds`

Where papers come from: arXiv categories with keywords, RSS feeds, and more.

- **Values:** A list such as `[{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}, {"type": "rss", "url":
  "..."}]`. **Default:** none.
- **When to change it:** Add the arXiv categories and journal feeds you follow; `/feeds` helps.
- **Costs and what leaves this computer:** Kurooto fetches from those services and feeds.

### `research.topics`

Old-style keywords searched across all of arXiv; `research.feeds` is the newer way.

- **Values:** A list of keywords. **Default:** none.
- **When to change it:** Use `research.feeds` instead for anything new; `/topics` edits this list.
- **Costs and what leaves this computer:** Searches go to arXiv.

### `research.papers`

When the paper digest comes.

- **Values:** `daily HH:MM` or `weekly <day> HH:MM`. **Default:** `weekly mon 08:00`.
- **When to change it:** Pick weekly for a calm field, daily for a fast one.

### `research.max_papers`

The most papers in one digest (1 to 30).

- **Values:** A whole number. **Default:** `8`.
- **When to change it:** Lower it for a shorter read; raise it to miss less.

### `research.window_days`

How far back each digest looks, in days.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Match it to how often the digest comes (7 for weekly).

### `research.rank`

Your AI picks the papers and says why; off, the newest come as they are.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to save AI requests or if you prefer the raw list.
- **Costs and what leaves this computer:** Titles and abstracts go to your AI, with `research.about`.
- **Depends on:** Chat with your AI.

### `research.save_note`

Keep each paper digest as a note in your inbox too.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you want digests in your notes.
- **Costs and what leaves this computer:** Nothing leaves.

### `research.zotero`

Put papers into Zotero with one tap: the app here, the web API with your key, or no Zotero buttons.

- **Values:** `auto` (the app when it's running, else the web API), `app`, `web`, `off`. **Default:** `auto`.
- **When to change it:** Pick `off` if you don't use Zotero.
- **Costs and what leaves this computer:** `web` sends the paper's details to api.zotero.org with your key; `app` stays
  on this computer.

### `research.zotero_links`

Notes that link a paper you put in Zotero get a link to its Zotero item.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want Kurooto adding Zotero links.
- **Depends on:** `research.zotero` not `off`.

### `research.repos`

Your code repositories on this computer, for project logs and quiet-project questions.

- **Values:** A list of full paths. **Default:** none.
- **When to change it:** Add the repositories you work in.
- **Costs and what leaves this computer:** Nothing leaves: read on this computer.

### `research.projects`

Which project each repository belongs to (its notes go in research/<project>/).

- **Values:** A JSON object, repository folder → project name; unset uses the folder's name. **Default:** none.
- **When to change it:** Set it when a repository's folder name isn't the project's name.
- **Costs and what leaves this computer:** Nothing leaves.

### `research.log_when`

When the day's commits and runs are written into your project logs.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 23:30`.
- **When to change it:** Move it to after you usually stop working.
- **Costs and what leaves this computer:** Nothing leaves.

### `research.repo_runs`

The folder in each repository where your scripts keep their runs (its index.csv); empty: don't read.

- **Values:** A folder name, or empty. **Default:** `runs`.
- **When to change it:** Change it if your runs live elsewhere.
- **Costs and what leaves this computer:** Nothing leaves.

### `research.idle_days`

After this many days without commits, ask about a project; 0: never.

- **Values:** A whole number. **Default:** `4`.
- **When to change it:** Raise it for slow projects; 0 if you don't want to be asked.
- **Costs and what leaves this computer:** One Telegram message, through Calm.

### `research.idle_when`

When the quiet-project check runs.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 18:00`.
- **When to change it:** Move it to when you'd answer.
- **Depends on:** `research.idle_days` above 0.

### `research.remind_by_call`

"Remind me tomorrow" on a quiet-project question is a call at 18:00.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to get a message instead.
- **Depends on:** Phone calls.

### `research.endpoints.arxiv`

arXiv's API address. Leave it alone.

- **Values:** Text. **Default:** `https://export.arxiv.org/api/query`.
- **When to change it:** Only for tests or a mirror.

### `research.endpoints.biorxiv`

bioRxiv's API address. Leave it alone.

- **Values:** Text. **Default:** `https://api.biorxiv.org/details`.
- **When to change it:** Only for tests or a mirror.

### `research.endpoints.pubmed`

PubMed's API address. Leave it alone.

- **Values:** Text. **Default:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`.
- **When to change it:** Only for tests or a mirror.

### `research_addon.run_compare`

Run compare: `/runs` and `kurooto runlog diff A B` (part of the Research add-on).

- **Values:** On or off. **Default:** on.
- **When to change it:** Switch it off on the add-on's card if you don't use it.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Research add-on.

### `research_addon.latex`

The LaTeX tracker: a nightly build of the documents you attach with `/latex add`.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you build your documents yourself.
- **Costs and what leaves this computer:** Nothing leaves: built on this computer.
- **Depends on:** The Research add-on, and a LaTeX installation.

### `research_addon.latex_repos`

The LaTeX documents you attached with `/latex add`.

- **Values:** A list of `{"path": folder, "main": "main.tex"}`. **Default:** none.
- **When to change it:** Use `/latex add` and `/latex remove` rather than editing it.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** `research_addon.latex`.

### `research_addon.latex_when`

When your attached LaTeX documents are built each night.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 03:30`.
- **When to change it:** Move it to when the computer is on and idle.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** `research_addon.latex`.

### `research_addon.latex_morning`

When the morning line comes (only when a build broke or you wrote something).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 08:00`.
- **When to change it:** Move it to when you start work.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** `research_addon.latex`.

### `research_addon.latex_timeout_min`

Minutes a build may take before it's stopped and counted as an error.

- **Values:** A whole number. **Default:** `15`.
- **When to change it:** Raise it for long documents.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** `research_addon.latex`.

### `research_addon.members_off`

Parts of the Research add-on you switched off on its card (they stay off when it's turned on).

- **Values:** A list of feature ids. **Default:** none.
- **When to change it:** Change it on the add-on's card.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** The Research add-on.

### `repo_projects.on`

Set a project up from its repository: `/project add` and "set up my project from github.com/…".

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want projects set up from repositories.
- **Costs and what leaves this computer:** A GitHub address is cloned to this computer; your AI reads its README and
  docs in one request.

### `repo_projects.max_mb`

The most of a cloned repository's files that are checked out to be read, in MB (history isn't counted).

- **Values:** A whole number. **Default:** `50`.
- **When to change it:** Raise it for documentation-heavy repositories.
- **Costs and what leaves this computer:** Disk on this computer.
- **Depends on:** `repo_projects.on`.

### `repo_projects.github_extras`

With gh signed in: the repository's description, topics, open issues and milestones too.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to read only the files.
- **Costs and what leaves this computer:** Read from GitHub through your own gh sign-in.
- **Depends on:** `repo_projects.on` and the gh program signed in.

### `repo_projects.refresh`

Each night, watched repositories are looked at again: README, docs, releases, milestones.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to update a project only with `/project update`.
- **Costs and what leaves this computer:** A fetch from GitHub, and an AI request when something changed.
- **Depends on:** `repo_projects.on`, and Research on.

### `repo_projects.refresh_at`

When the nightly repository refresh runs.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 04:20`.
- **When to change it:** Move it to when the computer is on.
- **Depends on:** `repo_projects.refresh`.

### `projects.help`

The projects your AI may help with (none until you say so).

- **Values:** A list of project names; `/project help on <name>` adds one. **Default:** none.
- **When to change it:** Add a project you want help on; remove it to stop.
- **Costs and what leaves this computer:** Help requests send that project's files to your AI; it works in a scratch
  copy, never in your folder.
- **Depends on:** Help with your project.

### `projects.folders`

More project folders of yours, by name.

- **Values:** A JSON object, project name → folder. **Default:** none.
- **When to change it:** Add a project that isn't a repository Kurooto knows. `/project add` keeps its own list.
- **Costs and what leaves this computer:** Nothing by itself.
- **Depends on:** Help with your project.

### `projects.checks`

A command that checks a project (its tests, a LaTeX build), run after the AI's changes.

- **Values:** A JSON object, project → command. **Default:** none.
- **When to change it:** Set one so proposals come with a pass or fail. It runs in the scratch folder, with a time limit
  and no network.
- **Costs and what leaves this computer:** Runs on this computer, in the scratch copy.
- **Depends on:** Help with your project.

### `projects.check_timeout_s`

Seconds a project check may run before it's stopped.

- **Values:** A whole number. **Default:** `300`.
- **When to change it:** Raise it for slow test suites.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** `projects.checks`.

### `projects.effort`

How hard your AI thinks about project work.

- **Values:** One of: `low`; `medium`; `high`; `auto`. **Default:** `high`.
- **When to change it:** Lower it to spend less of your AI's limit on project help.
- **Depends on:** Help with your project.

### `proposals.notes_edits`

A change to text already in your notes comes as a proposal (Apply / Change / Discard).

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on: off, the AI may change your existing note text without asking.
- **Costs and what leaves this computer:** Nothing leaves: the diff is shown to you.
- **Depends on:** Nothing: core.

### `proposals.keep_days`

Days an unanswered proposal is kept, with its scratch folder.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Raise it if you review proposals weekly.
- **Costs and what leaves this computer:** Disk on this computer.
- **Depends on:** Nothing: core.

### `proposals.max_kb`

A bigger change than this (KB) isn't proposed: ask for a smaller part.

- **Values:** A whole number. **Default:** `400`.
- **When to change it:** Raise it if you work on big documents.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** Nothing: core.

### `proposals.max_files`

A change touching more files than this isn't proposed.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it for project-wide changes.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** Nothing: core.

### `proposals.inline_lines`

A change up to this many lines is shown inside the message; a bigger one comes as a file.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it to read more diffs inline.
- **Costs and what leaves this computer:** The diff travels with the message (Telegram or the app).
- **Depends on:** Nothing: core.

### `proposals.morning`

When the night's proposals are told, if Dreaming is off (else in Dreaming's message).

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 07:30`.
- **When to change it:** Move it to when you'd review them.
- **Costs and what leaves this computer:** One message.
- **Depends on:** Nothing: core.

### `meetings.minutes`

Notes you send after a meeting with a project's person become minutes, through your AI.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep such notes as you sent them.
- **Costs and what leaves this computer:** Your notes from the meeting go to your AI once.
- **Depends on:** A project note with that person (Help with your project or Research).

### `meetings.after_h`

Hours after a meeting's start that a voice note or long note counts as notes from it.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Raise it if you write up meetings later in the day.
- **Costs and what leaves this computer:** Nothing.
- **Depends on:** `meetings.minutes`.

### `drafts.max_comments`

The most comments "Check my draft" puts on one draft.

- **Values:** A whole number. **Default:** `15`.
- **When to change it:** Lower it for only the main points.
- **Costs and what leaves this computer:** The draft goes to your AI to be checked.
- **Depends on:** Check my draft (part of the Research add-on).

### `drafts.note_block`

For checked notes, the comments also go into a block in the matching lecture note.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to get comments only as a message.
- **Costs and what leaves this computer:** Nothing more leaves.
- **Depends on:** Check my draft.

### `drafts.recent_minutes`

"Check this" right after you sent a file checks that file, if it came this recently (minutes).

- **Values:** A whole number. **Default:** `15`.
- **When to change it:** Raise it if you send the file and ask later.
- **Costs and what leaves this computer:** Nothing more leaves.
- **Depends on:** Check my draft.

## Teaching Kurooto and what it remembers

How Kurooto learns: setting itself up from what you say, the Wrong button and test cases, the nightly look back, lessons
from its own work, what it remembers and recalls in a reply, and Dreaming's morning message with its nightly tuning.
Every change it makes to itself is said in one line with Undo. More in [Teaching Kurooto about
you](teaching-kurooto.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Rules on this computer unless an entry says otherwise. Health, money and
  password details are never kept.
- **Depends on:** The feature each entry names: Remember, Learns from its own work, the Nightly look back, Wrong button
  and test cases, Dreaming; inference and memory are core.

### `infer.on`

Set things up from what you say in the chat and the journal ("every Monday at 9 I have a lab"), each with Undo.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather set everything up yourself. `/inferred` lists what it set up.
- **Depends on:** Nothing: core. Each kind below has its own switch.

### `infer.projects`

"I got a project under Prof X" makes a project note with them and a Meetings section.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if such sentences shouldn't create project notes.
- **Depends on:** `infer.on`.

### `infer.meetings`

"Met X today" adds a dated line to that project's Meetings; a meeting ahead becomes a deadline.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you log meetings yourself.
- **Depends on:** `infer.on` and a project note with that person.

### `infer.classes`

"Every Monday at 9 I have a <subject> lab" adds a class to your timetable.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if your timetable is set elsewhere.
- **Depends on:** `infer.on` and Subjects and timetable.

### `infer.commitments`

"Every Tuesday at 7pm I go to the gym" adds a commitment (it holds calls like a class).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if such sentences shouldn't become commitments.
- **Depends on:** `infer.on`.

### `infer.quizzes`

"There's a quiz on Linear Algebra every Monday" adds a row to the recurring quizzes table.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you keep that table yourself.
- **Depends on:** `infer.on` and Deadlines.

### `infer.aliases`

"By POTA I mean Physics of the Atmosphere" gives that subject a short name.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you set short names yourself.
- **Depends on:** `infer.on`.

### `infer.short_names`

"LA" becomes Linear Algebra's short name after two messages use it (when it fits only that subject).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if it guesses short names you don't mean.
- **Depends on:** `infer.on`.

### `infer.sweep`

One pass over your chats and journal for such sentences: once when first on, then nightly on what's new.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to only catch sentences as you say them.
- **Depends on:** `infer.on`.

### `infer.sweep_days`

How far back (days) the first pass over your chats and journal reads.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it to catch more of your past; lower it for a lighter first pass.
- **Depends on:** `infer.sweep`.

### `infer.sweep_ai`

A line the rules can't read: a model here restates it, your AI does, or it's skipped.

- **Values:** One of: `local` (this computer's model); `main` (your AI); `off`. **Default:** `local`.
- **When to change it:** Pick `off` to keep the sweep to rules only; `main` reads more but uses your AI.
- **Costs and what leaves this computer:** `main` sends those lines to your AI; `local` keeps them here.
- **Depends on:** `infer.sweep`; Local AI models for `local`.

### `memory.recall`

Replies and calls are told the few remembered items your message refers to ("as we said on the call").

Only when your message points at the past or an open thread; gists only, never transcripts.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather each request start fresh.
- **Costs and what leaves this computer:** Those remembered items go to your AI with the request (within
  `memory.budget_tokens`).
- **Depends on:** Nothing: core.

### `memory.budget_tokens`

At most about this much of what's remembered goes with one reply or call (about 4 characters a token).

- **Values:** A whole number. **Default:** `600`.
- **When to change it:** Raise it for richer recall; lower it to send less.
- **Costs and what leaves this computer:** More tokens means more remembered text goes to your AI.
- **Depends on:** `memory.recall`.

### `memory.threads`

What you say you'll do, and tasks you start, become open threads ("did I finish that thing?").

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want that kept. `/threads` shows them.
- **Depends on:** Nothing: core.

### `memory.thread_days`

Days an untouched open thread waits before it closes by itself.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Raise it if your tasks run long.
- **Depends on:** `memory.threads`.

### `remember.offer_settings`

A line you ask it to remember with a time rule ("I hate calls before 8") offers the setting that does it, with Set it /
No.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only want the line kept in your note.
- **Depends on:** Remember.

### `remember.recheck_days`

A kept line that hasn't come up in this many days gets one "Still true?"; 0: never.

- **Values:** A whole number. **Default:** `90`.
- **When to change it:** Raise it to be asked less; 0 to never be asked. Lines you wrote yourself are never touched.
- **Depends on:** Remember.

### `learning.search`

A search index of past requests, calls and chats on this computer: `/history`, and the AI's search_history.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want past conversations searchable.
- **Costs and what leaves this computer:** The index stays here; passages the AI finds go to that AI with its request.
- **Depends on:** Learns from its own work.

### `learning.skills`

A request that took many steps can become a skill, or improve the one that does it.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather write skills yourself. Each new skill comes with Undo.
- **Costs and what leaves this computer:** The request, its answer and steps go to the second-look AI once.
- **Depends on:** Learns from its own work and Skills.

### `learning.skill_min_steps`

How many tool uses a request needs before it's considered for a new skill.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Raise it to learn only from big tasks.
- **Depends on:** `learning.skills`.

### `learning.corrections`

When you correct a skill's answer, the skill keeps it as a lesson.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep skills exactly as written.
- **Costs and what leaves this computer:** Your correction and the skill go to the second-look AI.
- **Depends on:** Learns from its own work and Skills.

### `learning.remember`

The nightly look back keeps facts you stated in your chats and calls in your how-to-help-me note.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep only what you tell it with Remember.
- **Costs and what leaves this computer:** The day's requests go to the AI the look back uses.
- **Depends on:** Learns from its own work and the Nightly look back.

### `learning.remember_max`

The most facts kept in a night.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it if it keeps too much.
- **Depends on:** `learning.remember`.

### `learning.brain`

The AI that looks at finished work; empty uses the concept graph's second-look AI, else your main one.

- **Values:** An AI id, or empty. **Default:** empty.
- **When to change it:** Pick a cheaper AI if learning uses too much of your main one.
- **Costs and what leaves this computer:** That AI gets what's being learned from.
- **Depends on:** Learns from its own work.

### `cases.button`

A Wrong button under replies to plain-English requests (`/wrong` works either way).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the button clutters your chat.
- **Depends on:** Wrong button and test cases.

### `cases.fallthroughs`

Keep short requests no instant request understood, to learn from later.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not keep them.
- **Depends on:** Wrong button and test cases.

### `cases.keep_days`

Cases you didn't make test cases are forgotten after this many days (0: `privacy.keep_days`, else 30).

- **Values:** A whole number. **Default:** `0`.
- **When to change it:** Lower it to forget sooner. Test cases stay.
- **Depends on:** Wrong button and test cases.

### `cases.learn`

A test case may teach its phrasing, but only if every test case that passed still passes.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep test cases without learning from them.
- **Depends on:** Wrong button and test cases.

### `cases.learn_rephrased`

The same not-understood phrasing twice followed by the same request: it's learned.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to learn only from test cases you make.
- **Depends on:** Wrong button and test cases.

### `cases.review`

When the monthly list of most common not-understood phrasings may come.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `weekly sun 19:00`.
- **When to change it:** Move it to when you have a few minutes.
- **Depends on:** Wrong button and test cases.

### `cases.review_days`

Days at least between two such lists.

- **Values:** A whole number. **Default:** `28`.
- **When to change it:** Raise it to see the list less often.
- **Depends on:** Wrong button and test cases.

### `cases.review_max`

Phrasings in one list.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Lower it for a shorter list.
- **Depends on:** Wrong button and test cases.

### `retro.when`

When the nightly look back runs; `weekly sun 21:00` looks back over the whole week instead.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 23:50`.
- **When to change it:** Pick weekly if a nightly look back is too much.
- **Costs and what leaves this computer:** One AI request with the day's records (and transcripts and journal, if
  allowed below).
- **Depends on:** The Nightly look back.

### `retro.max_proposals`

The most changes one look back proposes.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it for fewer suggestions.
- **Depends on:** The Nightly look back.

### `retro.observe_days`

How long Observe longer (and `/observe` without a length) watches, in days.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Raise it to gather more before deciding.
- **Depends on:** The Nightly look back.

### `retro.no_days`

How long a No keeps an idea away, in days.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it if the same ideas come back too soon.
- **Depends on:** The Nightly look back.

### `retro.transcripts`

The look back reads today's call transcripts.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep transcripts out of it.
- **Costs and what leaves this computer:** The transcripts go to your AI with the look back.
- **Depends on:** The Nightly look back.

### `retro.journal`

The look back reads today's journal note.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep your journal out of it.
- **Costs and what leaves this computer:** Your journal note goes to your AI with the look back.
- **Depends on:** The Nightly look back.

### `retro.routines`

Propose a routine it sees in your records (the same thing at the same time, 3+ weeks).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want routine suggestions.
- **Depends on:** The Nightly look back.

### `retro.routine_weeks`

On how many different weeks something must happen before it's a routine.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Raise it for fewer, surer suggestions.
- **Depends on:** `retro.routines`.

### `retro.fixes`

Make data fixes it's sure of (two copies of one deadline become one), with Undo.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to be asked about every fix.
- **Depends on:** The Nightly look back.

### `dreaming.when`

When the morning message comes ("While you slept"), covering everything since the last one.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 07:30`.
- **When to change it:** Move it to when you're up. It follows your learned hours unless you set it.
- **Costs and what leaves this computer:** Nothing: it gathers what the night did; no AI.
- **Depends on:** Dreaming.

### `dreaming.loose_ends`

The morning message also lists loose ends: open doubts, unlinked notes, broken links, tasks past due.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off for a shorter morning message.
- **Depends on:** Dreaming.

### `dreaming.self_check`

Each morning, replay your test cases and say which ones went wrong since yesterday.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you have no test cases.
- **Depends on:** Dreaming and Wrong button and test cases.

### `dreaming.tune_messages`

Each night, replay the messages it sent you and tune when they come (one change, with Undo).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep message timing exactly as set.
- **Depends on:** Dreaming.

### `dreaming.tune_effort`

Each night, replay your requests and tune the effort they get (one change, with Undo).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep efforts as rated.
- **Depends on:** Dreaming.

### `dreaming.tune_fallbacks`

Each night, check which AI did best at each effort and let that one go first (with Undo).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep your main AI first always.
- **Depends on:** Dreaming.

### `dreaming.tune_sizing`

Each night, adjust Start-by's sizes to how long your deadlines really took.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep the sizes you set.
- **Depends on:** Dreaming and Start-by dates.

### `dreaming.tune_margin`

How much better a change must score in the replay than leaving things as they are.

- **Values:** A number. **Default:** `3.0`.
- **When to change it:** Raise it for fewer, surer changes.
- **Depends on:** Dreaming's tuning switches.

### `dreaming.never_tune`

Kinds of message it never tunes (besides the alarm, your reminders and calls, deadlines under 12 hours).

- **Values:** A list of message kinds. **Default:** `["deadlines.reminder", "deadlines.call", "health.now", "ai.limit",
  "google.signin", "kurooto.crash", "dreaming.morning"]`.
- **When to change it:** Add a kind whose timing you never want moved.
- **Depends on:** `dreaming.tune_messages`.

### `dreaming.propose_prompts`

Offer a fix for a skill that keeps going wrong, as a proposal you apply or not.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like skills to improve with your approval.
- **Costs and what leaves this computer:** The skill and its failures go to your AI to draft the fix.
- **Depends on:** Dreaming.

### `dreaming.curious`

Mention a topic you asked about 3+ times this week that has no note, with Make a stub.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want the suggestion.
- **Depends on:** Dreaming.

### `dreaming.resurface`

Bring back one thing from the past: a note or quiz subject from 10-30 days ago, or an anniversary.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want it.
- **Depends on:** Dreaming.

### `dreaming.consolidate`

Ask about things it remembers twice or that disagree: Keep A / Keep B / Both true.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave what it remembers as it is.
- **Depends on:** Dreaming.

### `dreaming.consolidate_ai`

A second opinion on near misses: a model here, your AI, or none.

- **Values:** One of: `local` (this computer's model); `main` (your AI); `off`. **Default:** `local`.
- **When to change it:** Pick `off` to keep it to rules only.
- **Costs and what leaves this computer:** `main` sends the two lines to your AI; `local` keeps them here.
- **Depends on:** `dreaming.consolidate`.

### `dreaming.consolidate_max`

The most such questions in one morning message; the rest wait.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it for a shorter message.
- **Depends on:** `dreaming.consolidate`.

### `dreaming.fold`

In the morning message, offer lasting things you said for your profile (Keep / Not that).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to build your profile only by hand.
- **Depends on:** Dreaming.

### `dreaming.fold_ai`

A second look at what the rules found for your profile: a model here, your AI, or none.

- **Values:** One of: `local` (this computer's model); `main` (your AI); `off`. **Default:** `local`.
- **When to change it:** Pick `off` to keep it to rules only.
- **Costs and what leaves this computer:** `main` sends those lines to your AI; `local` keeps them here.
- **Depends on:** `dreaming.fold`.

### `dreaming.fold_inferred`

The morning's profile suggestions also offer the projects and classes it set up from what you said, with a role, never a
name.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only want your own lines suggested.
- **Depends on:** `dreaming.fold`.

### `dreaming.fold_inferred_max`

The most of those suggestions in one morning, besides `dreaming.fold_max`.

- **Values:** A whole number. **Default:** `1`.
- **When to change it:** Raise it to catch up faster; 0 offers none.
- **Depends on:** `dreaming.fold_inferred`.

### `dreaming.fold_max`

The most profile suggestions in one morning message.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it for a shorter message.
- **Depends on:** `dreaming.fold`.

## Brain

Kurooto's mind, off until you turn it on: a log of what it saw and decided that it can't quietly change, a gate that
only ever makes it quieter, its read of how you're doing (shadow mode first), its journal, plans, skills, lab and the
rest. Each part has its own switch; turning Brain off stops all of them at once and asks whether to delete what it kept.
Brain's data stays in the mind folder on this computer and isn't in backups or Profile sync. More in [Brain](mind.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer: no cloud AI ever gets Brain's read of you, its
  journal facts or its numbers.
- **Depends on:** Brain (Features → Brain).

### `mind.anchor_every`

How often (in records) Brain notes where its log has got to, besides once a day.

- **Values:** A whole number. **Default:** `1000`.
- **When to change it:** Leave it. Lower it for more anchors on a very busy log.

### `mind.hardened`

The scorekeeper runs as its own system user, so not even a program running as you can change the log.

- **Values:** On or off. **Default:** off.
- **When to change it:** Set by `sudo tools/mind_harden.sh --apply` (Linux, macOS); undone by `--undo`. Don't set it by
  hand.

### `mind.gate.on`

Brain's gate on everything Kurooto sends by itself: only ever quieter, honest feelings, a shared pool of small touches.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have messages go exactly as before Brain. `/mind gate` shows what it held and
  why.

### `mind.gate.max_per_day`

Messages a day that may come by themselves (Calm's limit applies too: the smaller wins).

- **Values:** A whole number. **Default:** `12`.
- **When to change it:** Lower it for a quieter day. Your reminders, the alarm and close deadlines are never held.
- **Depends on:** `mind.gate.on`.

### `mind.gate.max_per_hour`

Messages an hour that may come by themselves.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it if messages bunch up.
- **Depends on:** `mind.gate.on`.

### `mind.gate.touches_per_day`

Small human touches a day in all (an absence note, a lighter-day line, a feeling).

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it, or 0, if you'd rather have none.
- **Depends on:** `mind.gate.on`.

### `mind.gate.feelings_per_week`

How often Brain may say how it feels about something unasked, per week.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it, or 0, to hear its feelings only when you ask.
- **Depends on:** `mind.gate.on` and `mind.feelings.express`.

### `mind.pest.on`

Learn for each kind of unprompted message whether it's welcome; send one only when it likely is.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to send by the other limits alone. `/mind learning` shows each kind's chance.
- **Depends on:** `mind.gate.on`.

### `mind.read.on`

Brain's read of how you're doing, from numbers about your days; in shadow mode it only watches.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want it; `/mood` → Off also asks whether to delete what it kept.

### `mind.read.asks_per_week`

How many times a week, at most, it may ask whether the week felt heavier than usual.

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Lower it, or 0, to never be asked.
- **Depends on:** `mind.read.on`.

### `mind.forecast.on`

Each evening at 21:00, what Brain expects of tomorrow, scored the next evening.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want the forecast.
- **Depends on:** `mind.read.on`.

### `mind.forecast.holdout`

The share of days a planned action is held back on purpose, to measure what it does.

- **Values:** A share between 0 and 1 (0.1 is one day in ten). **Default:** `0.1`.
- **When to change it:** Leave it: it's how Brain can tell whether its actions help.
- **Depends on:** `mind.forecast.on`.

### `mind.tone.on`

Tag each message you write with one word (calm, tired…), using the model on this computer only.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on only if you want tone in Brain's read. Only the day's average is kept.
- **Costs and what leaves this computer:** Nothing leaves: a local model; on a computer without one it does nothing.
- **Depends on:** `mind.read.on` and Local AI models.

### `mind.budget.on`

The body budget: a few things about Kurooto's own state it tries to keep level, and its drive.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to drop rewards and moods built on it. `/budget` shows it.

### `mind.values.on`

Brain learns which kinds of things help (values), never affecting a choice in the shadow days.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep Brain from learning values.
- **Depends on:** `mind.budget.on`.

### `mind.values.shadow_days`

Days learned values are only counted, never used for a choice.

- **Values:** A whole number. **Default:** `21`.
- **When to change it:** Raise it to watch longer before values count.
- **Depends on:** `mind.values.on`.

### `mind.talk.on`

Being talked to is a small reward for Brain (at most 0.2 a day; nothing for answers to its own pings).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if talking to it shouldn't count for anything.
- **Depends on:** `mind.budget.on`.

### `mind.talk.met`

An add-on's chat with someone in the room is a smaller reward for Brain (at most 0.05 a day, 6 meetings).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if meeting people shouldn't count for anything.
- **Depends on:** `mind.talk.on`, and an add-on that reports meetings.

### `mind.feelings.on`

Brain's states about specific things (uneasy, relieved…) and what they make it do inwardly.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to drop feelings; outward behaviour still passes the gate either way.
- **Depends on:** `mind.budget.on`.

### `mind.feelings.mood`

Its mood shapes it: low, it does less unasked, asks first, says less; high, a little bolder.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep its behaviour the same whatever its mood.
- **Depends on:** `mind.feelings.on`.

### `mind.feelings.empathy`

Concern for what it looks after (deadlines, projects, its machine): it notices sooner, speaks more gently.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you want plainer wording.
- **Depends on:** `mind.feelings.on`.

### `mind.feelings.express`

Brain may say a feeling about something open, through the gate, at most 3 times a week unasked.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep its feelings to itself.
- **Depends on:** `mind.feelings.on` and `mind.gate.on`.

### `mind.feelings.vocal`

Let Brain say unasked that it's excited or worried, when it has strong evidence.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like it to speak up about strong findings (at most one a day, with its
  evidence).
- **Depends on:** `mind.feelings.express`.

### `mind.stimulation.on`

Its senses felt as a body (heat, load, touch), for its feelings and the dashboard.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to drop the body. What it senses about you never moves its mood either way.
- **Depends on:** `mind.senses.intero`.

### `mind.stimulation.addons`

Let an add-on feed another device's sensors into its body (light, motion, battery, loudness...).

Each reading is felt as its physical analogue (light on its face, being moved, being picked up, hunger, heat, sound) and
drawn by the being's senses; numbers only, kept in memory and the body map.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to ignore what add-ons report; its own body and your phone's sensors are untouched.
- **Depends on:** `mind.stimulation.on` and an add-on that reports a device.

### `mind.stimulation.jolt`

Something sudden (a pickup, something close, a loud room) is felt at once: a jolt, and a fresh look at its mind.

Add-ons and senses call it; it fades in about two minutes and each kind jolts at most once a minute. Kinds and numbers
only, kept in memory.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have sudden things felt only at the next minute's reading.
- **Depends on:** `mind.stimulation.on`.

### `mind.sleep.on`

Kurooto sleeps in your sleep window: nothing it starts by itself is sent or said aloud until morning.

Asleep, what it would start by itself waits and goes out once the window is over (through the usual limits). Alarms,
reminders and calls you set, close deadlines, approvals and every answer to you still come. Its name or a message from
you wakes it; it answers, then dozes off again. Half an hour before, it's drowsy: nothing said aloud by itself.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have Kurooto keep the day's rules all night (the night hours still hold calls).
- **Costs and what leaves this computer:** Nothing leaves. The waiting messages stay on this computer until they're
  sent.

### `mind.sleep.follow_owner`

Its sleep follows yours: bedtime to the alarm, refined by your phone (screen off, dark, charging; first use).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have it sleep through the night hours (`availability.night`) exactly as set.
- **Depends on:** `mind.sleep.on`; the phone part needs the screen, light and charging sensors (`mind.senses.phone`).

### `mind.sleep.window`

Set Kurooto's sleep by hand, like 00:30-08:00 (empty: follow your night).

- **Values:** Empty, or two times `HH:MM-HH:MM` (it may run past midnight). **Default:** empty.
- **When to change it:** Set it if your nights don't match the night hours and you don't use the alarm.
- **Depends on:** `mind.sleep.on`.

### `mind.sleep.wake_minutes`

Woken by its name or a message at night, it dozes off again after this many quiet minutes.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Raise it if you often talk with it a while at night.
- **Depends on:** `mind.sleep.on`.

### `mind.sleep.senses_off`

Asleep, Kurooto's camera and microphone are off: Face presence pauses and Voice stops listening.

While it's asleep nothing watches or listens, so its name can't wake it: /wake, a message, a tap or a call from you
does. Woken, the camera and microphone come back; they go off again when it dozes off. The half hour before (drowsy)
they stay on. The Body add-on stops the desk phone's camera and microphone too.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have Voice keep listening while it sleeps, so its name wakes it (as before
  0.8.18).
- **Depends on:** `mind.sleep.on`.

### `mind.sleep.desk_holds`

While you're at this computer, Kurooto doesn't fall asleep: its night starts after you leave.

Face presence says when you were last here (your face, or your keyboard and mouse while it watches). Inside the sleep
window, it starts `mind.sleep.desk_after_min` minutes after that, at most at the window's end. Once it's asleep, coming
back to the desk doesn't wake it (only /wake, a message, a tap or a call); after a wake, the desk keeps it up again.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have it sleep at its window whether you're at the desk or not.
- **Depends on:** `mind.sleep.on` and Face presence on and enrolled.

### `mind.sleep.desk_after_min`

With desk_holds: how many minutes after you leave the desk its sleep starts.

- **Values:** Minutes, at least 1 (default 15). **Default:** `15`.
- **When to change it:** Raise it if it falls asleep while you've only stepped out for a while.
- **Depends on:** `mind.sleep.desk_holds`.

### `mind.yield.on`

The Brain's heavy work waits while your jobs use the graphics card, during a call, on battery or when hot.

It covers the lab, play, plans, the model of you, skills, the harness and the fine-tune; it tries again every 5 minutes
and gives up for the night after 12 hours. What you ask for yourself never waits. /mind shows the contention minutes a
week (its heavy work running while yours held the card).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have the Brain's work run at its times whatever the computer is doing.

### `mind.yield.prefer_sleep`

The Brain's nightly work also waits for Kurooto to be asleep (until that night's window ends).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have it run at the scheduled time even while you're still up.
- **Depends on:** `mind.yield.on` and `mind.sleep.on`.

### `mind.autonomy.on`

Brain learns from your reactions how far it may act on its own, per class of action (shadow first).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have it always ask (or never act) as before.

### `mind.autonomy.enforce`

Make its trust verdicts bind: it asks first for what it isn't trusted with.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on after the shadow weeks if you want its learned trust to take effect.
- **Depends on:** `mind.autonomy.on`.

### `mind.autonomy.shadow_days`

Days its trust verdicts are only counted and shown, not used.

- **Values:** A whole number. **Default:** `21`.
- **When to change it:** Raise it to watch longer before anything changes.
- **Depends on:** `mind.autonomy.on`.

### `mind.autonomy.thresholds`

Your own trust bars per class of action, over the defaults.

- **Values:** A JSON object, class → bar between 0 and 1: `{"R1": 0.8}`. **Default:** none.
- **When to change it:** Raise a class's bar to make it harder to earn acting on its own.
- **Depends on:** `mind.autonomy.on`.

### `mind.journal.on`

A daily journal of Brain's own states, reasons and mistakes, every line checked against its log.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't read it. `/mindjournal` shows it.
- **Costs and what leaves this computer:** Nothing leaves: a model on this computer words the facts, or fixed sentences.

### `mind.journal.in_notes`

Also keep Brain's journal as a block in a note of yours.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to read it with your notes.
- **Costs and what leaves this computer:** If your notes sync to a service, this note syncs with them.
- **Depends on:** `mind.journal.on`.

### `mind.journal.in_notes_folder`

The folder inside your notes the journal note goes in; empty is the top.

- **Values:** Text. **Default:** empty.
- **When to change it:** Pick a folder to keep it out of the way.
- **Depends on:** `mind.journal.in_notes`.

### `mind.journal.in_notes_file`

The journal note's file name (`.md` is added if missing).

- **Values:** Text. **Default:** `Kurooto journal.md`.
- **When to change it:** Rename it to suit your notes.
- **Depends on:** `mind.journal.in_notes`.

### `mind.workspace.on`

A small "now" stage that parts compete to enter; only what wins may start a message or act on its own.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off and nothing it decides by salience gates messages any more. `/thinking` shows it.

### `mind.workspace.capacity`

How many things can be on Brain's mind at once (1 to 3).

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it for a more single-minded Brain.
- **Depends on:** `mind.workspace.on`.

### `mind.workspace.cycle_s`

The least gap in seconds between two cycles (events poke it sooner).

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it to save a little work on a slow computer.
- **Depends on:** `mind.workspace.on`.

### `mind.workspace.arbiter`

One door for everything Kurooto says by itself: each message bids, and only winners are sent.

Check-ins, Calm's small touches, research watch, Dreaming's results, a feeling said aloud and add-on bids all compete at
the door after Brain's gate. Each gets a bid from its kind, its due time, how long it has waited and how welcome that
kind has been lately; the top few win. Losers wait and bid again, and one that kept losing for hours goes into the
evening bundle. Alarms, your own reminders, calls, approvals, close deadlines and answers to you go straight past.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have messages go as they come (past the gate and Calm, as in 0.8.13). Whatever
  waited goes at once. `/mind gate` shows what waits.
- **Depends on:** `mind.workspace.on`.

### `mind.workspace.breaks`

A winner that isn't urgent waits for a natural break: a window switch after a long stretch, a phone pickup, a session
ending.

Breaks come from the activity sense (a window switch after `mind.workspace.break_after_min` minutes in one window), the
phone's screen sense (an unlock), a study session or focus time ending, Face presence (you came back) and add-ons. With
none of those on, there's nothing to wait for and winners go at once.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have winners go as soon as they win.
- **Depends on:** `mind.workspace.arbiter`.

### `mind.workspace.max_hold_min`

The longest a winner waits for a break, in minutes (unless Kurooto is asleep).

- **Values:** A whole number. **Default:** `90`.
- **When to change it:** Lower it if things come too late; raise it for longer stretches undisturbed.
- **Depends on:** `mind.workspace.breaks`.

### `mind.workspace.break_after_min`

Minutes in one window before switching to another counts as a natural break.

- **Values:** A whole number. **Default:** `25`.
- **When to change it:** Lower it if your stretches are short; raise it so only long ones count.
- **Depends on:** `mind.workspace.breaks` and the activity sense (`mind.senses.activity`).

### `mind.workspace.fold_h`

Hours a message may keep losing at the door before it goes into the evening bundle instead.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Lower it to clear the door sooner; nothing is ever dropped, only moved to the bundle.
- **Depends on:** `mind.workspace.arbiter` and Calm (`notify.calm.on`); with Calm off it simply goes.

### `mind.expect.on`

Each message Kurooto starts says what it expects (a reply, or done within 2 hours), and what came of it is recorded.

A question or check-in expects a reply within 3 hours; a nudge expects to be acted on within 2. Your reply, a tap on one
of its buttons or the time running out closes it; the scorekeeper writes the outcome. Ids and numbers only, never the
words.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop recording expectations and outcomes.

### `mind.why.on`

"Why this?" under a message Kurooto started says what Brain's gate and door did with it, what it expected, and how many
it has sent today.

It adds to Calm's Why? on Telegram, and puts a Why this? button on the phone app chat's copy.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep Calm's Why? as it was.

### `mind.attention.on`

A model of its own attention: "what are you thinking about?" is answered from it.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't ask.
- **Depends on:** `mind.workspace.on`.

### `mind.beliefs.on`

Keep where each belief came from (said, saw, inferred, imagined) and how sure it is.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to drop the hedging rules. `/beliefs` lists them.

### `mind.precedents.on`

Judgement calls between your values are asked once, then followed (off until you turn it on).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like fewer repeat questions. It can never unlock anything on the always-ask
  list.

### `mind.precedents.threshold`

How alike two situations must be (0 to 1) for a precedent to be followed.

- **Values:** A number. **Default:** `0.75`.
- **When to change it:** Raise it to be asked more often; lower it to follow precedents more widely.
- **Depends on:** `mind.precedents.on`.

### `mind.play.on`

A little nightly time to explore its own questions on your topics (off until you turn it on).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you're curious what it finds. Outputs are never shown unprompted.
- **Costs and what leaves this computer:** Runs on this computer, on the charger with the lid open and the computer
  cool; its outputs stay in Kurooto's state folder.

### `mind.play.minutes_per_night`

Minutes of play a night, on the charger only.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Lower it to save the battery and your AI.
- **Depends on:** `mind.play.on`.

### `mind.forget.on`

Old things fade from use, old misses stop coming up, and `/forget` goes everywhere Brain kept something.

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on; off, faded items rank as fresh and old misses can come up again.

### `mind.forget.half_lives.default`

Days for a remembered item to fade to half, when its kind has no own setting.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it to keep things in use longer.
- **Depends on:** `mind.forget.on`.

### `mind.forget.half_lives.fact`

Days for a fact about you to fade to half.

- **Values:** A whole number. **Default:** `90`.
- **When to change it:** Raise it if facts fade too soon.
- **Depends on:** `mind.forget.on`.

### `mind.forget.half_lives.gist`

Days for a conversation's gist to fade to half.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it to keep older conversations in use.
- **Depends on:** `mind.forget.on`.

### `mind.forget.half_lives.project`

Days for a project fact to fade to half.

- **Values:** A whole number. **Default:** `180`.
- **When to change it:** Raise it for long projects.
- **Depends on:** `mind.forget.on`.

### `mind.forget.misses_weeks`

After this many weeks, a past miss is no longer brought up.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Lower it to be reminded of misses for less time.
- **Depends on:** `mind.forget.on`.

### `mind.plans.on`

Plans over weeks: which milestones are at risk, from simulated futures. A suggestion, never a push.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't use `/plan`.

### `mind.plans.rollouts`

How many simulated futures a plan runs.

- **Values:** A whole number. **Default:** `1000`.
- **When to change it:** Lower it on a slow computer (rougher odds).
- **Depends on:** `mind.plans.on`.

### `mind.plans.weeks`

How far ahead (weeks) the simulated futures look.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Raise it for long projects.
- **Depends on:** `mind.plans.on`.

### `mind.tom.on`

A model of what you know, believe, want and prefer, each row with its source (`/model`).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want one kept. It never models health, relationships, politics,
  religion or money.

### `mind.tom.false_beliefs`

When something you were told turns out wrong, tell you once, with the evidence.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not get these corrections.
- **Depends on:** `mind.tom.on`.

### `mind.tom.from_chat`

An exam result you report ("I got 12/30 on the LA midterm") counts as evidence of what you know.

It also adds a dated line in Kurooto's own block of the course's exam prep note, and after a low score offers more
preparation hours (a tap).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if results you mention shouldn't change anything.
- **Depends on:** `mind.tom.on` and Subjects.

### `mind.tom.attention`

Hold a message (at most 15 minutes) while you're deep in one project.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if interruptions while you're focused bother you.
- **Depends on:** `mind.tom.on` and the activity stream (`mind.senses.activity`).

### `mind.senses.intero`

Its own machine's state every minute: temperatures, memory, battery, disk, AI limits.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop Brain sensing the computer.

### `mind.senses.activity`

The activity stream: the app in front, hashed window titles, saves and commits (never keystrokes, the screen or URLs).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on for plans and skills that learn from what you do. It's never used to check up on
  you.
- **Costs and what leaves this computer:** Nothing leaves. Raw events last 7 days, then only totals.

### `mind.senses.phone`

Each of your phone's sensors, off until you switch it on (here and in the phone app).

- **Values:** A JSON object, sensor → on/off: `screen`, `charging`, `motion`, `steps`, `light`, `places`, `headphones`,
  `dnd`, `alarm`, `wifi`, `usage`. **Default:** every sensor off.
- **When to change it:** Switch on the ones you're happy to share; both here and on the phone must be on.
- **Costs and what leaves this computer:** Readings are sealed on the phone and travel through your call line, which
  can't read them.
- **Depends on:** A paired Android phone with the sensor on in the app.

### `mind.skills.on`

Solved tasks become tested, reusable skills; each new one starts out asking first.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not have Brain learn skills. `/learned` lists them.

### `mind.skills.from_demos`

Also offer skills from what you do over and over (asked once).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on with the activity stream if you'd like Brain to spot repeats.
- **Depends on:** `mind.skills.on` and `mind.senses.activity`.

### `mind.finetune.on`

A weekly local fine-tune of the model on this computer, from checked examples only.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on only with an 8 GB graphics card and the training packages.
- **Costs and what leaves this computer:** A night of graphics-card time on the charger; nothing leaves.

### `mind.finetune.day`

The night of the week it trains.

- **Values:** One of: `mon`; `tue`; `wed`; `thu`; `fri`; `sat`; `sun`. **Default:** `sun`.
- **When to change it:** Pick a night the computer is plugged in.
- **Depends on:** `mind.finetune.on`.

### `mind.finetune.base`

The local model's name in Ollama to build the adapter into; empty is the helper model.

- **Values:** Text. **Default:** empty.
- **When to change it:** Only if you want another base model.
- **Depends on:** `mind.finetune.on`.

### `mind.finetune.base_hf`

The Hugging Face name of the base model, which the trainer loads.

- **Values:** Text. **Default:** empty.
- **When to change it:** Set it when you set `mind.finetune.base`.
- **Costs and what leaves this computer:** The base weights are downloaded from Hugging Face once.
- **Depends on:** `mind.finetune.on`.

### `mind.finetune.min_examples`

With fewer checked examples than this, it skips the week.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it for steadier adapters.
- **Depends on:** `mind.finetune.on`.

### `mind.finetune.practice`

Include the harness' practice tasks in training.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to train only on your own checked work.
- **Depends on:** `mind.finetune.on`.

### `mind.finetune.probe_words`

Words of a forgotten prompt kept to check a new adapter forgot it (3 or more).

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Leave it unless the check is too strict or too loose.
- **Depends on:** `mind.finetune.on`.

### `mind.harness.on`

Nightly on the charger: how it does on tasks it has never seen, and checks of Brain's own promises.

- **Values:** On or off. **Default:** on.
- **When to change it:** Leave it on: without it, nothing can be promoted. `/capabilities` shows the scores.
- **Costs and what leaves this computer:** Runs on this computer with its own rules (no AI requests), on the charger.

### `mind.harness.rotate_days`

The hidden tasks are made new this often (days), so old ones can't be memorised.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Leave it.
- **Depends on:** `mind.harness.on`.

### `mind.improve.on`

Brain improving itself through gated proposals: nothing changes without the hidden harness and your say-so.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop it proposing changes to itself. `/improve` lists them.
- **Costs and what leaves this computer:** Challengers run on this computer; applying one is always your tap.
- **Depends on:** `mind.harness.on`.

### `mind.lab.on`

Overnight pre-registered experiments on the projects you list (Linux and macOS, in a sandbox).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't use the lab. Your files are never changed; winners come as proposals.
- **Costs and what leaves this computer:** Runs on this computer, on the charger, with no network.

### `mind.lab.projects`

Folders (or repository projects' names) the lab may run experiments on.

- **Values:** A list; `/lab add <folder>` adds one. **Default:** none.
- **When to change it:** Add a project with a number you want to move.
- **Depends on:** `mind.lab.on`.

### `mind.lab.max_per_night`

The most configurations in one night's batch.

- **Values:** A whole number. **Default:** `40`.
- **When to change it:** Lower it for shorter nights.
- **Depends on:** `mind.lab.on`.

### `mind.lab.run_wall_s`

Seconds one lab run may take before it's stopped.

- **Values:** A whole number. **Default:** `1800`.
- **When to change it:** Raise it for slow experiments.
- **Depends on:** `mind.lab.on`.

### `mind.lab.gpu`

Let lab runs use the graphics card (off: CPU only).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on for GPU-bound projects.
- **Depends on:** `mind.lab.on`.

### `mind.lab.gpu_hours_per_night`

The most graphics-card hours the lab uses in a night.

- **Values:** A whole number. **Default:** `2`.
- **When to change it:** Lower it to keep the card free.
- **Depends on:** `mind.lab.gpu`.

### `mind.lab.seed`

A fixed seed for the sampled configurations; 0 draws a new sample each day.

- **Values:** A whole number. **Default:** `0`.
- **When to change it:** Set one to repeat a batch exactly.
- **Depends on:** `mind.lab.on`.

### `mind.lab.in_repo`

Keep a project's lab protocol in its `.kurooto` folder (off: in Kurooto's own state).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to keep the protocol with the project; git never sees it.
- **Depends on:** `mind.lab.on`.

### `mind.heartbeat.on`

When this computer is down, your call line also says what the next 12 hours have no guarantee for.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off for the plain offline message.
- **Costs and what leaves this computer:** Nothing more leaves: it adds a line to the offline message your call line
  already sends.
- **Depends on:** Phone calls.

### `mind.promises.on`

Its own promises ("I'll check back at 6") are noticed, kept, or owned up to first.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't want them tracked. `/promises` lists them.

### `mind.story.on`

One life story every part of Kurooto reads first: a fixed core, then its recent weeks.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have each request start without it.
- **Costs and what leaves this computer:** The story goes with each AI request (at most `mind.story.tokens`).

### `mind.story.tokens`

The life story's summary is at most this many tokens (about 4 characters each).

- **Values:** A whole number. **Default:** `800`.
- **When to change it:** Lower it to send less with each request.
- **Costs and what leaves this computer:** That many tokens go with each AI request.
- **Depends on:** `mind.story.on`.

### `mind.backfill.on`

Brain reads what Kurooto kept before it was on, once (`/mind backfill`); off until you turn it on.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on so Brain's read, forecasts and plans start with your past. `/mind backfill forget`
  undoes it.

### `mind.backfill.events`

Read Kurooto's own event history: what happened and when.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.jobs`

Read the AI request history: effort, whether it worked, how long (never the words).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.deadlines`

Read when past deadlines were due and done (no titles).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.checkins`

Read which check-ins were asked, answered or skipped each day, never what you said.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.quiz`

Read your quiz record per day and subject (asked, right, wrong), never the questions.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.calls`

Read past calls (answered or missed, who placed them, how long), never what was said.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.learning`

Read how many requests and calls a day were indexed (chats left out).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.backfill.study`

Read the study tracker's time per day, for your real pace in week plans.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to leave this source out.
- **Depends on:** `mind.backfill.on`.

### `mind.console.on`

The Brain console: a dashboard page (Alt+O) and the phone's Brain view showing what the Brain decided and why.

- **Values:** `true` (the page and the view read what the Brain keeps), `false` (both say the console is off; the Brain
  itself runs as before). **Default:** on.
- **When to change it:** Turn it off if you don't want its reasoning on screen. It only reads; nothing the Brain does
  depends on it.
- **Depends on:** Brain on.

### `mind.dream.on`

Brain goes over the day at night and brings cards, how-to-help lines and a voice line to the morning message.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop all of its dreaming at once; each piece also has its own switch.

### `mind.dream.cards`

Each night, 1 to 3 quiz cards for concepts you studied that day that are on your frontier, kept by a tap.

Concepts you changed notes on, answered quiz cards about or logged study time for, that Brain's model of what you know
puts on your frontier (not mastered, prerequisites solid). The model on this computer writes each card from your note;
without one it's a plain "what is ...?" card. They wait in the morning message with Keep and Drop; a kept card goes into
Quiz, first due about a day after it was written. /mind shows your recall on them next to your own cards.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather write every card yourself.
- **Costs and what leaves this computer:** Nothing leaves: the local model or a fixed card. A card you keep is graded
  like any other (by your AI with Chat on).
- **Depends on:** `mind.tom.on` and Quiz.

### `mind.dream.cards_max`

The most dream cards a night (1 to 3).

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it for fewer cards to look at in the morning.
- **Depends on:** `mind.dream.cards`.

### `mind.dream.lessons`

Each night, 1 to 3 lines for your how-to-help-me note from the day's outcomes, written only when you tap Keep.

It replays what you undid, the messages left unanswered or given Less of this, the times you told Voice off and its
guesses about you marked wrong; clear patterns become lines like "Fewer nudges in the evening". Keep writes the line
(with Undo); Not that drops it for good.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather write that note yourself.

### `mind.dream.voice`

One morning line on what the nightly voice learning saw: turns it learned from and any misfire pattern.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't need it. Counts and flags only, never words.
- **Depends on:** Voice with `voice.listen.learn_nightly`.

### `mind.study_push.on`

One morning line about the subject Brain is most uneasy about (due date, minutes logged, cards due), with Yes and Later.

That day the subject's day-before deadline reminder, Start-by's "Time to start" and exam mode's daily practice check-in
are folded into it. Yes sets a reminder at the time it offers (or counts the deadline as started). The six-hour
reminder, "Overdue?" and the evening-before practice offer still come.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to get the separate reminders back.
- **Depends on:** Deadlines (a deadline with a subject); Study and Quiz add their numbers when on.

### `mind.study_push.when`

When the morning line comes.

- **Values:** A schedule like `daily 07:55`. **Default:** `daily 07:55`.
- **When to change it:** Keep it before Start-by's morning pass (`startby.when`), so its message is folded.
- **Depends on:** `mind.study_push.on`.

### `mind.study_push.minutes`

How long a study stretch the morning line offers.

- **Values:** A whole number. **Default:** `25`.
- **When to change it:** Change it to the length you'd actually start with.
- **Depends on:** `mind.study_push.on`.

### `mind.study_push.frontier`

Between subjects it's equally uneasy about, the one with concepts you're ready for wins, and the line names one.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like the morning line to say where to go next in the subject.
- **Depends on:** `mind.study_push.on` and Brain's model of what you know (`mind.tom.on`).

### `mind.study_push.horizon_days`

How far ahead a deadline can be for Brain to be uneasy about it.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Lower it to hear only about what's close.
- **Depends on:** `mind.study_push.on`.

### `mind.checkins.surprise`

The next check-in comes early when the day departs strongly from Brain's forecast.

Two hours past the predicted wake time with no sign of you while your phone shows you up, or a deadline moved twice in a
day: the next check-in planned today comes now instead of at its time, once a day. Never in a class or while you're
asleep.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have check-ins only at their times.
- **Depends on:** `mind.forecast.on` and Check-ins (the phone's screen sense for the wake case).

### `mind.status.on`

One status stream: focus, asleep, messages held, the one thing it's uneasy about, its own mood and arousal.

Enums and numbers only, made again whenever something happens (at most once a second) and pushed to the dashboard's
being, copied to the phone's Views, and handed to add-ons that listen (an add-on's own face, for example). The mood is
Brain's own; nothing in it says how you are. It stays on this computer and your phone's sealed copy.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off and the being, the phone and add-ons stop getting it: the glance and the mood in
  the drawing go neutral.
- **Depends on:** Brain on.

### `mind.knobs.on`

Three knobs: its mood sets how much it explores, arousal how soon it speaks up, calibration whether it asks first.

Mood: with a low mood the lab and play get half their nightly budget (never more than you set), and an add-on's interest
bar rises a little. Arousal: how soon unprompted things may go (the arbiter's longest hold is scaled by 0.75 to 1.25).
Calibration: while its beliefs score no better than a coin flip (a Brier score of 0.25 or worse, after 10), its own acts
above R0 ask first. Drawn as the being's pupil and pulse. Nothing here touches what you asked for: no confirm step, no
slower answer. Add-ons read it with `kurooto.mind.status.knobs(app)`.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep the budgets and asking as they were in 0.8.13.
- **Depends on:** Brain on.

### `mind.register.on`

One temperament: its mood and arousal set how long its unprompted words are, its call openers and Voice's pace.

Quiet (low mood), even or lively (high mood and roused). An AI request Kurooto starts itself is told at most 2, 3 or 4
sentences for anything that goes to you unasked; a call it places itself opens in one short sentence, a greeting and the
reason, or two warm sentences; what Voice says unasked (a greeting, an add-on's line) is spoken at `voice.speak.rate`
scaled within 8% either way. Never for replies to you or calls you asked for.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep every unprompted message, opener and pace as in 0.8.13.
- **Depends on:** Brain on.

### `mind.context.on`

Every AI request gets Brain's hints: concepts you're shaky on, and what's on its mind.

Read from Brain's own files with no model call (under 50 ms): up to three concepts below solid from your quizzes and
notes in the last two weeks, and the workspace's winners that aren't about you. Your read, tone, mood and body state
never go in, so a cloud AI never gets them. Answers use it silently. Off, the workspace's winners go as they did in
0.8.13.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather requests carry nothing from Brain beyond its story and feelings.
- **Costs and what leaves this computer:** The concept names and what's on its mind go with each request to the AI you
  picked.
- **Depends on:** Brain on; the hints need the model of you (`mind.tom.on`).

### `mind.act.more`

Its trust decides study blocks, reshaped plans, revision packs and keeping its night's cards and lines.

Five kinds of thing it proposes: a study block from the morning line (R1), moving part of a slipping deadline's work to
tomorrow (R2), a revision pack the evening before a quiz or exam (R1, with packs set to ask), keeping a quiz card it
wrote at night (R1) and keeping a how-to-help-me line from the night (R2). While its trust in that class is below the
bar (`mind.autonomy.thresholds`), it asks with the feature's own buttons, as before, and each yes is an OK that builds
trust. Once it's above, it does it and says so with Undo; an Undo costs trust and pauses the class for a week. A low
mood, or beliefs no better than a guess lately (`mind.knobs.on`), make it ask first again. It works whether or not
`mind.autonomy.enforce` is on, and needs no shadow weeks: the bar is the gate. /mind and /autonomy list each kind with
its trust.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have every one of them ask, as in 0.8.15.
- **Depends on:** `mind.autonomy.on`; each kind needs its feature (Deadlines, Start-by, Reminders, Skills, Quiz, Brain's
  dreaming).

### `mind.presence_forecast.on`

Forecast, hour by hour for the next six hours, when you'll be at your desk and free; scored against what the senses then
show.

Free means at your desk (the activity sense saw the computer in use, or Face presence saw you, in the last quarter
hour), not on a call and not in a class; the night and Kurooto's sleep window count as not free. It learns each hour of
the week from its looks every 15 minutes. Each hour that's over is scored against the forecast made hours before and
against "same as yesterday"; Brain is paid a little for beating that baseline (at most 0.05 a day of its reward), for
accuracy only: nothing here counts what you said to Kurooto. /mind shows its accuracy and the next likely-free hour.
Numbers only, on this computer.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't use the activity sense or Face presence (without them nothing is
  scored), or don't want it.
- **Depends on:** Brain on; the activity sense (`mind.senses.activity`) or Face presence to score it.

### `mind.presence_forecast.prefer`

Check-ins and calls Kurooto places by itself prefer an hour you're likely free.

A check-in just planned for an hour the forecast thinks you won't be free (a class, a call, an hour you're usually away)
moves to a clearly likelier one nearby, the same check-in day; the night check-in isn't held to your sleep. A call
Kurooto places by itself (not one you asked for, not an alarm, not a deadline under 12 hours away) waits for a likelier
time when you aren't seen at your desk, and says so. With nothing learned yet, only classes, the night and calls move
anything.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep check-ins and calls exactly at their times.
- **Depends on:** `mind.presence_forecast.on`.

### `mind.presence_forecast.within_min`

How far (minutes) a check-in or a call may move to a likelier hour.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Lower it to keep them close to their times; 0 never moves them.
- **Depends on:** `mind.presence_forecast.prefer`.

### `mind.register.templates`

Its ready-made unprompted messages keep the register's 2, 3 or 4 sentences too, not only what the AI writes.

A nudge or a line a feature sends by itself keeps its first sentences, and any later one its buttons answer (a question,
or one naming a button). Digests and lists (more than one paragraph, or a line that starts a list) stay whole, and so do
answers to you and anything exempt: alarms, your own reminders, a deadline under 12 hours away, calls, approvals,
anything urgent.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have Kurooto's ready-made messages come whole, as in 0.8.15.
- **Depends on:** `mind.register.on`.

## Voice and voice notes

Kurooto speaks through this computer's speakers with a voice made here, and, if you turn listening on, hears the room
through the microphone, all on this computer: noise and people talking to each other are dropped on the spot, and only
what's said to Kurooto goes on, like a chat message. Voice notes you send on Telegram are written out by Gemini. More in
[Voice: talk and listen](voice.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Sound is handled on this computer and never touches the disk. Only turns said
  to Kurooto go to your AI, as a chat message would.
- **Depends on:** The Voice feature.

### `voice.speak.on`

Kurooto speaks through this computer's speakers.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep Voice for listening only, or for a silent room.

### `voice.speak.engine`

The voice made on this computer: Kokoro (natural, about 0.55 GB), Piper (lighter) or off.

- **Values:** `kokoro`, `piper` or `off`. **Default:** `kokoro`.
- **When to change it:** Pick `piper` on an older computer; `kokoro` sounds more natural.
- **Costs and what leaves this computer:** The voice's files are downloaded once.
- **Depends on:** `voice.speak.on`.

### `voice.speak.voice`

Which Kokoro voice it speaks in; empty is `af_heart`.

- **Values:** A Kokoro voice name: `af_heart`, `af_bella`, `am_michael`, `bf_emma`, `bm_george` and more. **Default:**
  empty.
- **When to change it:** Try a few with `/voice say` and keep the one you like.
- **Depends on:** `voice.speak.engine` = `kokoro`.

### `voice.speak.rate`

How fast it speaks: 1.0 is normal, 0.8 slower, 1.2 faster.

- **Values:** A number around 0.5 to 2. **Default:** `1.0`.
- **When to change it:** Slow it down for long answers, speed it up if you're used to it.
- **Depends on:** `voice.speak.on`.

### `voice.speak.what`

What's read aloud: answers to what you said aloud, every AI answer, or nothing.

- **Values:** `voice` (answers to what you said aloud), `all` (every AI answer) or `off`. **Default:** `voice`.
- **When to change it:** Pick `all` if you work away from the screen.
- **Depends on:** `voice.speak.on`.

### `voice.speak.max_chars`

How much of a long answer is read aloud before it says "the rest is on screen".

- **Values:** Characters. **Default:** `800`.
- **When to change it:** Raise it to hear long answers in full.
- **Depends on:** `voice.speak.on`.

### `voice.speak.join_sentences`

Speak short sentences together, up to about 200 characters at a time, instead of each on its own.

Kokoro reads a few words on their own with a hurried, flat tune; joined to their neighbours they get a natural one, and
it still pauses at each full stop. The first piece is kept under about 120 characters, so speech starts as soon as
before.

- **Values:** `true` (short sentences joined) or `false` (one sentence at a time, as before 0.8.13). **Default:** on.
- **When to change it:** Turn it off if a long pause before the first word bothers you on a slow computer.
- **Depends on:** `voice.speak.on`.

### `voice.speak.numbers_as_words`

Say numbers as a person would: 21:31 as "nine thirty-one PM", ₹3,000 as "three thousand rupees".

Times, dates, years, money, versions, ranges, percentages and units are said in words: 12 GB as "twelve gigabytes",
0.8.13 as "zero point eight point thirteen", 2026 as "twenty twenty-six". Only what's said changes; the screen shows
what was written.

- **Values:** `true` (times, dates, years, money, versions, ranges and units in words) or `false` (the speech engine
  reads the digits itself). **Default:** on.
- **When to change it:** Turn it off if it ever reads a number wrongly and you'd rather hear the engine's own reading.
- **Depends on:** `voice.speak.on`.

### `voice.listen.on`

Listen through the microphone, all on this computer; only what's said to Kurooto leaves it.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to talk to Kurooto out loud. It stops during calls, when paused, on battery saver
  and when muted.
- **Costs and what leaves this computer:** The speech models are downloaded once. Only turns addressed to Kurooto go to
  your AI.

### `voice.listen.wake_word`

A wake-word model of your own (an openWakeWord `.onnx` path); empty: its name wakes it.

- **Values:** A full path, or empty. **Default:** empty.
- **When to change it:** Only if you trained your own wake word.
- **Depends on:** `voice.listen.on`.

### `voice.listen.wake_threshold`

How sure the wake-word model must be (0 to 1).

- **Values:** A number. **Default:** `0.5`.
- **When to change it:** Raise it if it wakes by mistake; lower it if it misses you.
- **Depends on:** `voice.listen.wake_word`.

### `voice.listen.name_variants`

More spellings of its name to accept (the common mishearings of Kurooto are built in).

- **Values:** A list of spellings. **Default:** none.
- **When to change it:** Add the way the transcriber writes the name you gave it, if it keeps missing it.
- **Depends on:** `voice.listen.on`.

### `voice.listen.model_judge`

When the rules can't tell whether you're talking to it, the model on this computer judges.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to use rules only (fewer false starts, more misses).
- **Costs and what leaves this computer:** Nothing leaves: a local model.
- **Depends on:** `voice.listen.on` and Local AI models.

### `voice.listen.threshold`

How sure the local model must be (0 to 1) that speech is said to Kurooto.

- **Values:** A number. **Default:** `0.7`.
- **When to change it:** Raise it if it answers conversations not meant for it; lower it if it ignores you.
- **Depends on:** `voice.listen.model_judge`.

### `voice.listen.after_speak_s`

Seconds after it spoke during which a question counts as an answer to it.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Raise it if you think before answering.
- **Depends on:** `voice.listen.on`.

### `voice.listen.close_s`

Seconds of nothing said to it before the spoken conversation closes.

- **Values:** A whole number. **Default:** `8`.
- **When to change it:** Raise it for slower back-and-forth.
- **Depends on:** `voice.listen.on`.

### `voice.listen.night`

Keep listening during the night hours.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop listening at night.
- **Depends on:** `voice.listen.on`.

### `voice.listen.calls`

Keep listening while you're on a phone call (off: listening pauses during calls).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on only if your calls are on another device out of earshot.
- **Depends on:** `voice.listen.on`.

### `voice.listen.stt_model`

How big the speech-to-text model is: tiny (75 MB), base (145 MB) or small (484 MB, more accurate).

- **Values:** `tiny`, `base` or `small`. **Default:** `base`.
- **When to change it:** Pick `small` if it often mishears you and the computer is fast enough.
- **Costs and what leaves this computer:** The model is downloaded once.
- **Depends on:** `voice.listen.on`.

### `voice.listen.language`

The language you speak, e.g. `en` or `hi`; empty works it out each time.

- **Values:** A language code, or empty. **Default:** empty.
- **When to change it:** Set it if it guesses your language wrong, or misses its name: worked out on each short clip, an
  accent is often taken for another language (English for Hindi or Urdu) and the name never comes out right.
- **Depends on:** `voice.listen.on`.

### `voice.listen.early`

Write the words out at your first short pause, so the turn goes on the moment you've finished.

At your first pause of about 0.3 seconds, what you've said so far is written out (on this computer) while Kurooto still
waits to see if you go on. If you don't, the turn goes straight on with those words instead of writing the whole stretch
out again, and a finished question (or a finished sentence of three words or more) ends the turn after 0.35 to 0.55
seconds of quiet instead of 0.7. If you go on talking, the early words are thrown away. With Voice ID's gate on, a voice
that isn't yours (with no conversation open) is never written out early. Nothing is sent anywhere early: only the
writing out happens sooner.

- **Values:** `true` (default), `false` (the words are written out after 0.7 seconds of quiet, as before). **Default:**
  on.
- **When to change it:** Turn it off if Kurooto starts answering while you're only pausing mid-thought.
- **Depends on:** `voice.listen.on`.

### `voice.listen.auto_gain`

Hearing follows the room: speech must stand above its noise, and a quiet voice is evened up.

While nothing is being said, Kurooto follows the room's noise floor (the loudness of what isn't speech, over a few
seconds). Speech starts a stretch only when it's at least voice.listen.auto_gain_snr_db above that floor, so a noisy
room asks for a clearer voice and a quiet one still hears a soft one. Each stretch is then brought to one level (never
turned down, at most eight times louder, never clipped) before it's written out, so a quiet or far voice reads as well
as a near one. All inside Kurooto: the system's microphone volume is never changed, so calls and other apps hear exactly
as before. Only the noise floor and the last gain are kept (in memory, numbers only; /voice status).

- **Values:** `true` (default), `false` (every stretch the voice detector finds counts, at the level it came in).
  **Default:** on.
- **When to change it:** Turn it off if soft speech close to the microphone is missed in a noisy room.
- **Depends on:** `voice.listen.on`.

### `voice.listen.auto_gain_snr_db`

How far above the room's noise speech must be to count, in dB.

- **Values:** A number of dB, 0 or more (default 6). Higher is stricter in a noisy room; 0 lets any speech through.
  **Default:** `6`.
- **When to change it:** Raise it if far-off talk or a TV starts stretches; lower it if you're missed when you speak
  softly.
- **Depends on:** `voice.listen.auto_gain`.

### `voice.listen.device`

Which microphone to use; empty is the system's default.

- **Values:** A device's name or number as your sound system lists it (the sounddevice library's names). **Default:**
  empty.
- **When to change it:** Set it if you have several microphones.
- **Depends on:** `voice.listen.on`.

### `voice.audio.backend`

How Kurooto plays and records sound: PipeWire's own tools, or the PortAudio library inside Kurooto.

`pipewire`: speech plays through `pw-play` and the microphone is read through `pw-record`, separate programs, so a sound
driver problem can't take Kurooto down, and the microphone follows your system's default (a source that comes and goes
is picked up again). `portaudio`: the sounddevice library inside Kurooto, as before 0.8.16. `auto` picks `pipewire` on
Linux when PipeWire is running and its tools are installed, unless `voice.listen.device` names a microphone (those are
sounddevice's names); else `portaudio`. Takes effect for speaking at once, for listening the next time it starts
(`/voice mute`, then `/voice unmute`).

- **Values:** `auto` (default), `pipewire` or `portaudio`. **Default:** `auto`.
- **When to change it:** Pick `portaudio` if speech or the microphone misbehaves through PipeWire's tools, or to use a
  sounddevice microphone by name; `pipewire` to pass a PipeWire node name in `voice.listen.device`.

### `voice.listen.levels`

Show the microphone's loudness as a waveform on the dashboard (numbers only).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you don't watch the waveform.
- **Depends on:** `voice.listen.on`.

### `voice_notes.model`

Which Gemini model writes out your voice notes.

- **Values:** A Gemini model name. **Default:** `gemini-flash-latest`.
- **When to change it:** Change it when a better or cheaper speech model is out.
- **Costs and what leaves this computer:** Each voice note's audio goes to Google with your Gemini key.
- **Depends on:** Voice notes, and a Gemini key.

### `voice_notes.api_base`

Another address for the voice-note model; empty is Google's.

- **Values:** A web address, or empty. **Default:** empty.
- **When to change it:** Only for a proxy or a compatible server of your own.
- **Costs and what leaves this computer:** Voice notes go to that address.
- **Depends on:** Voice notes.

### `voice.speaker_id.on`

Voice ID: only your voice can make Kurooto act; others can only chat, with none of your data. Enrol first.

- **Values:** `true` (each turn is checked against your voice print, on this computer), `false` (any voice is treated as
  yours, as before). **Default:** off.
- **When to change it:** Turn it on if other people are ever near the computer while Voice listens. Enrol on the Your
  voice page first.
- **Costs and what leaves this computer:** About 20-60 ms of processor per thing said. Your voice print is stored
  encrypted on this computer, never sent anywhere.
- **Depends on:** Voice: talk and listen, and an enrolled voice.

### `voice.speaker_id.mode`

What other voices get: a chat with no actions and none of your data, or just one line saying it only talks with you.

- **Values:** `owner_only_acts` (others may chat), `owner_only_at_all` (others hear one line, nothing more).
  **Default:** `owner_only_acts`.
- **When to change it:** Pick `owner_only_at_all` if you don't want Kurooto chatting with anyone else at all.

### `voice.speaker_id.gate`

Check who's speaking before writing words out: other people not calling Kurooto are never transcribed.

- **Values:** `true` (others' talk is dropped before transcription), `false` (everything is transcribed, then sorted as
  in 0.8.8). **Default:** on.
- **When to change it:** Leave it on: it keeps other people's conversations private and saves the transcription's
  processor time.

### `voice.speaker_id.guest_brain`

Who answers other voices: your AI (none of your data, no tools) or the model on this computer.

- **Values:** `main` (your AI, only if it can be held to plain text: an API or Claude Code; with agy or Codex the local
  model answers), `local` (always this computer). **Default:** `main`.
- **When to change it:** Pick `local` to keep guests' words on this computer.
- **Depends on:** For `local`, Local AI models with a chat model.

### `voice.speaker_id.guest_per_hour`

At most this many answers to other voices an hour.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Lower it if guests use up your AI's quota.

### `voice.speaker_id.tell_guests`

Once per conversation, tell others they can chat but only you can make Kurooto act.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather it just chats without saying so.

### `voice.speaker_id.strictness`

How sure it must be that it's you: relaxed, normal or strict (strict turns you away more often).

- **Values:** `relaxed`, `normal`, `strict`. **Default:** `normal`.
- **When to change it:** Strict if a lot of people are around; relaxed if it keeps asking you again in a noisy room.

### `voice.speaker_id.threshold`

0: worked out from your own samples when you train. A number overrides it, held to 0.30 to 0.95.

- **Values:** A number. **Default:** `0.0`.
- **When to change it:** Leave it at 0 unless the Test step on the Your voice page shows it gets it wrong.

### `voice.speaker_id.margin`

The 'not sure' band just below the threshold, at most 0.2 wide. Not sure always counts as not you.

- **Values:** A number. **Default:** `0.05`.
- **When to change it:** Widen it to be safer; narrow it if you're asked to repeat yourself too often.

### `voice.speaker_id.min_speech_s`

Speech shorter than this is too short to tell who it is, so it counts as not sure.

- **Values:** A number. **Default:** `1.0`.
- **When to change it:** Raise it if quick one-word sounds get mistaken; lower it if your short answers are often 'not
  sure'.

### `voice.speaker_id.carry`

A short reply right after a turn it knew was you counts as you (not when the voice is clearly someone else).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off (or use strict) if guests could answer 'yes' for you.

### `voice.speaker_id.carry_s`

The window, in seconds, in which a quick reply after you spoke still counts as you.

- **Values:** A whole number. **Default:** `15`.
- **When to change it:** Shorten it in a shared room; lengthen it if your quick follow-ups get refused.

### `voice.speaker_id.adapt`

Improve over time: turns it was very sure were you refine your voice print, slowly and with undo.

- **Values:** `false` (default: your voice print stays as trained), `true`. **Default:** off.
- **When to change it:** Turn it on if your voice changes (a cold, a new mic) and you'd rather it keeps up by itself.

### `voice.speaker_id.adapt_max`

At most this many learned turns are kept in your voice print (the oldest are replaced).

- **Values:** A whole number. **Default:** `40`.
- **When to change it:** Lower it to keep your voice print closer to the samples you trained with.

### `voice.speaker_id.adapt_per_day`

A daily cap on how many of your turns may be added to your voice print.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Lower it to make the voice print change more slowly.

### `voice.speaker_id.model`

The speaker model: campplus-en (English, the most accurate) or campplus-multi. Changing it means enrolling again.

- **Values:** `campplus-en`, `campplus-multi`. **Default:** `campplus-en`.
- **When to change it:** Pick campplus-multi if you speak to Kurooto mostly in another language.

### `voice.addons.listen`

Let an add-on take one stretch of speech at a time through the microphone (written out here, never sent).

An add-on may ask for the next thing said, by any voice, while Kurooto is listening: it's written out on this computer
and handed to that add-on only, never to the gate, the conversation or your AI. Mute, the night, calls and every other
pause still stop it, and it never takes a conversation that's open with you.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep add-ons from hearing anything.
- **Depends on:** `voice.listen.on`, and an add-on that uses it.

### `voice.addons.chat`

Let an add-on have Kurooto chat with someone who isn't you, the guest way: no tools, none of your data.

The add-on's chat goes through the same sealed path as another voice's (Voice ID's guests): text only, no tools, none of
your notes, memory or history, refusals for commands and your things, and the hourly guest limit.
voice.speaker_id.guest_brain picks who answers.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep add-ons from starting chats.
- **Costs and what leaves this computer:** One AI turn per reply, from your main AI or this computer's model
  (voice.speaker_id.guest_brain).
- **Depends on:** An add-on that uses it.

### `voice.speaker_id.spoken_enrol`

During enrolment Kurooto says each step aloud. Off: the page shows the steps only.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you enrol somewhere you can't have it talk aloud.

### `voice.listen.conversation_mode`

While another voice is here, Kurooto stays out of people talking: only its name said to it opens a talk.

- **Values:** `true` (default with Voice ID), `false` (the usual gate). **Default:** on.
- **When to change it:** Leave it on so it doesn't join your conversations with other people; nothing said then is kept.
- **Depends on:** Voice ID (it knows which voice is yours).

### `voice.listen.conversation_s`

Seconds after the other person last spoke before Kurooto stops staying out of the conversation.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Lengthen it if Kurooto joins in too soon after the other person stops talking.

### `voice.listen.conversation_follow_s`

In conversation mode, a reply to what Kurooto just said counts only this soon after it.

- **Values:** A whole number. **Default:** `4`.
- **When to change it:** Lengthen it if your replies to Kurooto in a conversation get ignored.

### `voice.listen.careful_name`

When someone else may be talking, its name wakes Kurooto only said first, as a call ("Kurooto, what's ...").

Someone else may be talking when Voice ID isn't sure the voice is yours (or knows it isn't), when people talked here
within voice.listen.chatter_s without talking to Kurooto, or when Face presence sees two or more faces. Then its name at
the end or in the middle of a sentence, or a word that only sounds like it, is just a mention: the other rules and the
model on this computer decide. With you alone, its name first or last still wakes it as before.

- **Values:** `true` (default), `false` (its name first or last always wakes it, as before 0.8.13). **Default:** on.
- **When to change it:** Leave it on if Kurooto joins your conversations when you mention it; turn it off if it ignores
  you at the end of a sentence when you're alone.

### `voice.listen.chatter_s`

Speech here that wasn't to Kurooto (any voice) this many seconds ago makes it careful with its name.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Lengthen it if it still jumps into a conversation that paused for a while.

### `voice.listen.follow_s`

After Kurooto answers, what the same voice says this many seconds after counts as said to it, statements too.

You don't have to say its name again to go on: within this window of its answer ending, anything the voice it answered
says goes to it. Another voice, two voices at once, or being told off ("not you", "stop") end it. In conversation mode
this window applies to the voice that opened the talk instead of voice.listen.conversation_follow_s. The conversation
stays open at least this long after an answer.

- **Values:** Seconds; `20` (default), `0` (off: only questions and requests within voice.listen.close_s count).
  **Default:** `20`.
- **When to change it:** Shorten it (or 0) if it takes what you say to someone else right after its answer; lengthen it
  if it stops listening while you think.

### `voice.listen.told_off`

"Stop", "not you", "never mind" and the like, right after it woke or spoke, stop it at once and close the talk.

Within about 10 seconds of the conversation opening or of Kurooto speaking: it stops speaking, closes the conversation
and doesn't reply. It notes a misfire (the rule that opened it, never your words) and, with voice.listen.learn_nightly,
a training row of numbers for the night's learning. With voice.listen.barge_in you can say it over Kurooto while it
speaks; without it, say it as soon as it stops, or use /voice stop.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if one of those phrases is something you often say to Kurooto as a request.

### `voice.listen.barge_in`

Talk over Kurooto while it speaks to stop it: "stop", a new question, or anything you want to say.

While Kurooto speaks it keeps listening, but never takes its own voice coming back through the room for you. A stretch
of speech counts as you cutting in when Voice ID (on and enrolled) recognises your voice in it (at least about 0.6
seconds of speech, closer to your voice print than to Kurooto's own, which is made once in memory from a phrase its
voice says silently), or when it's clearly louder than the echo of what's playing just then and its words, written out
here, aren't Kurooto's own. Then it goes quiet at once (on this computer, or on another device an add-on plays it on),
and what you said is: a told-off phrase ("stop", "never mind"): it stops; a question or a request: a new turn in the
same conversation; anything else ("mm", a cough, a word to someone else): it carries on, saying the sentence it was cut
in from its start (0.8.17), or stops if that isn't settled within about 12 seconds. Limits: on a speakerphone or at a
high volume its echo can drown you out, so speak up or come closer; without Voice ID only the loudness check works; and
with Voice ID only your voice can cut in by voice (a guest has to be louder than its echo). Nothing extra is kept: the
sound stays in memory as for any stretch, and the event says only how it was noticed and what came of it.

- **Values:** `true` (default), `false` (the microphone is dropped while it speaks, as before; /voice stop still stops
  it). **Default:** on.
- **When to change it:** Turn it off if Kurooto stops for the TV or other people talking loudly near it while it speaks.

### `voice.listen.need_face`

Answer only someone in front of it: a face close to the camera and facing it while they speak.

With Face presence on and enrolled, a turn is answered only when the camera saw a face close to it
(voice.listen.face_near) and facing it (voice.listen.face_yaw_deg) while it was said or within about 1.5 seconds after.
Anything else, by any rule (its name, a follow-up, the local model's judgement, cutting in), is chatter: someone on a
phone call across the room, the TV, a person talking to you from the door. The wake word and the told-off phrases
("stop", "never mind") work without a face, and typed /voice commands are never affected. While Voice listens it keeps
Face presence's camera looking (its card says "voice: who's talking"), never past Face presence's own pauses: a call, a
locked screen, /face pause, the night, a busy or covered camera; then voice.listen.need_face_fallback decides. Only the
time of each look and how many faces were close and facing are kept, in memory: no picture, no face numbers. With Face
presence off or not enrolled this does nothing.

- **Values:** `true` (default), `false` (the voice rules alone, as before). **Default:** on.
- **When to change it:** Turn it off if you often talk to Kurooto from across the room or without looking at the screen.
- **Costs and what leaves this computer:** The camera's light stays on while Voice listens, and a little processor time;
  on Linux a video call app can't use the camera then (/voice mute or /face pause frees it).
- **Depends on:** Face presence on and enrolled; Voice listening.

### `voice.listen.face_near`

How close counts: a face at least this share of your usual face height at the desk (0.5 is about twice as far).

Your usual height comes from Face presence's recent sightings of you at the desk (or your enrolment). Until it knows, a
face at least face.recognise.min_face_px tall counts.

- **Values:** A number from 0.1 to 1. **Default:** `0.5`.
- **When to change it:** Lower it if it ignores you when you lean back or sit further away; raise it if it answers
  people across the room.
- **Depends on:** `voice.listen.need_face`.

### `voice.listen.face_yaw_deg`

How directly someone must face the camera: turned at most this many degrees away (an estimate).

- **Values:** Degrees, 10 to 80. **Default:** `35`.
- **When to change it:** Raise it if it ignores you when you glance at a second screen; lower it if it answers people
  talking side-on.
- **Depends on:** `voice.listen.need_face`.

### `voice.listen.need_face_fallback`

What happens when the camera can't see (paused, covered, busy, no camera): the voice rules alone, or nothing.

`voice`: it answers by the voice rules alone, as without voice.listen.need_face. `none`: nothing is answered by voice
until the camera can see again; the wake word and "stop" still work. /voice and /health say which applies now ("needs a
face: camera paused (screen locked), using voice rules").

- **Values:** `voice` (default) or `none`. **Default:** `voice`.
- **When to change it:** Pick `none` if being answered when nobody's there is worse than not being answered.
- **Depends on:** `voice.listen.need_face`.

### `voice.listen.look_to_talk`

Look at the camera for a second and Kurooto starts listening, as if you'd said its name.

With Face presence on and enrolled, your face (recognised as yours), close to the camera and turned to it within
voice.listen.look_yaw_deg and voice.listen.look_pitch_deg, for voice.listen.look_dwell_s, opens the conversation the way
its name alone does, without a sound: the next thing you say counts as said to it, no name needed. The camera sees which
way your head points, not your eyes, so the angles are tighter than voice.listen.face_yaw_deg: looking at the screen
beside the camera shouldn't count. It stays open while you keep looking; look away for voice.listen.look_away_s before
saying anything and it closes. A conversation already going on is left alone. One look opens it once: after it closes
(you said something not to it, "stop", or looked away) look away and back. It never opens while Voice is off or muted,
on a call, at night with listening off, while Kurooto is asleep, or with Face presence off or paused. What you then say
still goes through the other checks: with Voice ID, someone else's voice isn't even written out; two voices at once, or
people talking here lately, need a question or a request. Only two times are kept, in memory: when you started looking
and when you last did.

- **Values:** `true` (default), `false` (only its name, the wake word and the usual follow-ups open it). **Default:**
  on.
- **When to change it:** Turn it off if it starts listening while you're only reading something near the camera.
- **Costs and what leaves this computer:** Like voice.listen.need_face, the camera stays looking while Voice listens
  (its light on), and a little processor time.
- **Depends on:** Face presence on and enrolled; Voice listening.

### `voice.listen.look_dwell_s`

How long you look at the camera before it starts listening: a glance shorter than this doesn't count.

Face presence looks about once a second (every 3 seconds on battery), so the wait is this long or a little more.

- **Values:** Seconds, 0 to 10 (default 1). **Default:** `1.0`.
- **When to change it:** Raise it if passing glances open it; lower it to have it react sooner.
- **Depends on:** `voice.listen.look_to_talk`.

### `voice.listen.look_yaw_deg`

How straight at the camera your head must point, left or right: at most this many degrees (an estimate).

- **Values:** Degrees, 5 to 35 (default 15). **Default:** `15`.
- **When to change it:** Raise it if looking at the camera doesn't open it; lower it if looking at the screen next to it
  does.
- **Depends on:** `voice.listen.look_to_talk`.

### `voice.listen.look_pitch_deg`

How straight at the camera your head must point, up or down, judged against your face at enrolment.

Measured from the front step of your Face presence enrolment (where you looked straight at the camera). If that isn't on
record, only the left-right angle counts.

- **Values:** Degrees, 5 to 35 (default 15). **Default:** `15`.
- **When to change it:** Raise it if it misses you when the camera sits above the screen; lower it if looking down at
  the keyboard opens it.
- **Depends on:** `voice.listen.look_to_talk`.

### `voice.listen.look_away_s`

Looking away this long, before you've said anything, closes it again.

- **Values:** Seconds, 0 to 30 (default 3). **Default:** `3.0`.
- **When to change it:** Raise it if it closes while you glance at your notes before asking.
- **Depends on:** `voice.listen.look_to_talk`.

### `voice.listen.look_gaze`

With your eyes calibrated on the Face page, a look counts by your eyes on the camera, not your head's turn.

Needs the eye model (Get the eye model on the Face page: MediaPipe Iris, 2.6 MB) and Calibrate my eyes (about three
seconds looking at the camera's lens). Then each frame, while Voice listens, the irises are found in your eyes (cut from
the camera's full picture) and combined with your head's turn: eyes on the lens count even with your head a little
turned, and eyes on the screen below the camera don't, even with your head facing it. Calibration keeps four numbers in
your sealed face model (where your irises sat and how your head was turned), never a picture; Clear on the Face page
drops them, and Forget drops them with the rest. Without the model or a calibration, or with this off, the head's turn
counts (voice.listen.look_yaw_deg and look_pitch_deg), and /voice says which.

- **Values:** `true` (default), `false` (the head's turn only). **Default:** on.
- **When to change it:** Turn it off if glasses or the light make your eyes hard to read and looks stop opening it.
- **Costs and what leaves this computer:** About 7 ms of one processor core per frame while Voice listens, for the eyes
  (measured on a Ryzen 7 laptop).
- **Depends on:** `voice.listen.look_to_talk`; the eye model and a calibration (the Face page).

### `voice.listen.look_gaze_dwell_s`

By the eyes: how long your eyes must be on the camera before it starts listening (0: at once).

With your eyes calibrated, eyes on the lens are a clear sign, so by default the first frame that sees them there opens
the conversation (Face presence looks up to 5 times a second while Voice listens: face.watch.look_fps). Without a
calibration, voice.listen.look_dwell_s applies instead.

- **Values:** Seconds, 0 to 5 (default 0). **Default:** `0.0`.
- **When to change it:** Raise it a little (0.3) if a passing glance at the camera opens it.
- **Depends on:** `voice.listen.look_gaze` and a calibration.

### `voice.listen.look_anyone`

Anyone's look opens the conversation, not only yours: a guest looking at it can talk to it too.

Face presence reads where every close face looks (the three biggest besides yours), by the head's turn, or by the eyes
judged against your calibration when you've calibrated. People talking to each other without looking at it stay ignored.
A guest is still a guest: Voice ID decides, and someone who isn't you gets chat only (no tools, none of your data). Only
numbers for where a face points are used, never who it is, and they go with the frame.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have only your own look open it (as 0.8.17).
- **Depends on:** `voice.listen.look_to_talk`, Face presence on and enrolled.

### `voice.listen.look_in_company`

With others here, looking at it and saying its name (even misheard) counts as calling it.

With two or more faces in view or other voices about, its name has to be said first and heard exactly. After a look, its
name first or last spelled any way (a near miss too) is enough, so a garbled transcript doesn't drop what you said.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have a look count, in company, only before a question or a request.
- **Depends on:** `voice.listen.look_to_talk`.

### `voice.listen.look_gaze_yaw_deg`

By the eyes: how close to the camera's lens your gaze must be, left or right (an estimate in degrees).

- **Values:** Degrees, 3 to 30 (default 10). **Default:** `10`.
- **When to change it:** Raise it if looking at the camera doesn't open it; lower it if looking at a screen beside it
  does. The Face page shows your last look's angles while Voice listens.
- **Depends on:** `voice.listen.look_gaze` and a calibration.

### `voice.listen.look_gaze_pitch_deg`

By the eyes: how close to the camera's lens your gaze must be, up or down (an estimate in degrees).

- **Values:** Degrees, 3 to 30 (default 10). **Default:** `10`.
- **When to change it:** Raise it if it misses you; lower it if looking at the screen just below the camera opens it.
- **Depends on:** `voice.listen.look_gaze` and a calibration.

### `voice.listen.learn_nightly`

Every night Kurooto learns from how its voice turns went: ones you carried on with, and ones you told off.

Each turn the gate let through is labelled once it's known how it went: you went on talking to it (good), or told it off
(a misfire). Only flags and numbers are kept, in Kurooto's state under voice/: the rule that decided, how its name was
said, how many voices, Voice ID's decision and score, seconds since other talk, faces in view; never words or sound. At
night (04:10) a small model is fitted to them; with 20 turns or more, some of each, it can hold back a borderline
opening (its name heard only as a near miss, a follow-up, the local model's judgement) that looks like past misfires. It
can never stop its name said first ("Kurooto, ..."). /voice and /health show the numbers; forgetting your voice (/voice
id forget) deletes them too.

- **Values:** `true` (default), `false` (nothing recorded, nothing held back). **Default:** on.
- **When to change it:** Turn it off to keep the gate's rules fixed.

### `voice.speaker_id.face_assist`

When Voice ID is only "not sure" it's your voice and Face presence sees just your face, it counts as you.

Only a voice already inside the "not sure" margin, only while the camera's last look (a few seconds old at most) shows
exactly one face and it's yours. A voice clearly not yours, two voices, two faces, or strict strictness never count.
With "improve over time" (voice.speaker_id.adapt) on, such a turn that went well may be added to your voice print like a
very sure turn, with the same caps and undo.

- **Values:** `true` (default), `false`. **Default:** on.
- **When to change it:** Turn it off if a photo of you plus a voice close to yours is a risk where you are.
- **Depends on:** Voice ID and Face presence, both enrolled.

### `voice.speaker_id.carry_talk`

In a talk Voice ID knew you opened, a voice it's only "not sure" of stays you, so history and tools carry.

Extends voice.speaker_id.carry: not only a short reply, but any turn whose score is inside the "not sure" margin, while
the conversation you opened is open and within voice.speaker_id.carry_s or voice.listen.follow_s (the longer) of its
last answer to you. A voice clearly someone else's, or two voices, are never carried; strict turns it off.

- **Values:** `true` (default), `false` (only short replies carry, as before 0.8.13). **Default:** on.
- **When to change it:** Turn it off in a shared room where someone with a voice like yours might carry on your
  conversation.

### `voice.speak.ack`

While your AI thinks, a short soft sound says Kurooto heard you.

The moment a turn you said goes to your AI, a soft sound plays through the same speakers or output as its voice (a phone
an add-on plays it on, say), so the silence while the AI works doesn't feel like it didn't hear. It's skipped when the
answer is already on its way (a plain-English request done at once) or something is being said. `tone` is a short, quiet
rising note made on this computer; `word` is "Hmm." in Kurooto's own voice, made once and kept in memory. Only for turns
heard through the microphone; never for typed messages.

- **Values:** `tone` (default), `word` or `off`. **Default:** `tone`.
- **When to change it:** Pick `word` if a voice sounds friendlier to you than a note; `off` if you'd rather have
  silence.
- **Depends on:** `voice.speak.on` and `voice.listen.on`.

### `voice.speak.stream`

Speak the answer a sentence at a time while your AI is still writing it.

When your AI can stream its answer (Claude Code, a Gemini key or Ollama answering without tools), each finished sentence
is spoken as soon as it arrives, instead of after the whole answer is in; the rest follows as it's written. Words the AI
writes before it uses a tool ("Let me check your notes.") are spoken too. An AI that can't stream (agy) is spoken when
it's done, as before. /voice stop, mute and talking over it stop it at once.

- **Values:** `true` (default) or `false` (the whole answer first, as before 0.8.16). **Default:** on.
- **When to change it:** Turn it off if you'd rather hear only the finished answer.
- **Depends on:** `voice.speak.on`.

### `voice.listen.timing`

Time each spoken turn from your last word to Kurooto's first sound, as numbers only.

Each turn that goes to your AI is timed from the end of your speech: written out, decided (the face check included),
sent, the AI starting, its first words, the whole answer, the acknowledgement, the first sound made and the first sound
playing (on an add-on's output: when it's handed the sound). One voice_timing event a turn (milliseconds, never words),
and the medians of the last 20 turns in /voice and on GET /api/voice ("speed"). Kept in memory.

- **Values:** `true` (default) or `false`. **Default:** on.
- **When to change it:** Leave it on; turn it off only if you don't want the events in the log.
- **Depends on:** `voice.listen.on`.

### `voice.listen.fast_brain`

Which AI answers plain chat said aloud: your AI as usual, the model on this computer, or the quickest.

Only turns that need nothing of yours and no tools are moved: small talk and general questions with none of "my",
"notes", "remind", "today", "search" and the like, that no plain-English request of Kurooto's would take. Those are
asked as text only at low effort. `same`: your AI with its tools, as always. `local`: the Ollama model on this computer
(nothing leaves it). `fastest`: the quickest set up here by its first words in your recent voice turns (each is tried
once first: your AI when it's a service, a Gemini key, the model on this computer, then your AI with no tools). Anything
else, and every turn when unsure, goes to your AI as before.

- **Values:** `same` (default), `local` or `fastest`. **Default:** `same`.
- **When to change it:** Pick `local` or `fastest` if chatting by voice feels slow and you don't mind a smaller model
  for small talk.
- **Depends on:** `voice.listen.on`; `local` needs Local AI models (Ollama) set up.

### `voice.listen.warm_up`

When listening starts, warm the transcriber and the voice, so your first turn isn't the slow one.

Half a second of silence is written out (on the hearing thread, never beside a turn) and one word is made by the voice
and never played, once each time they're loaded. Nothing is recorded or sent.

- **Values:** `true` (default) or `false`. **Default:** on.
- **When to change it:** Turn it off on a computer short of memory if you rarely talk to it.
- **Depends on:** `voice.listen.on`.

### `voice.listen.warm_brain`

When listening starts, get your AI's program ready on this computer.

With Claude Code as your AI, its program is run once for its version (at most every 10 minutes), so its files are read
from the disk then and not on your first turn; nothing is sent. With voice.listen.fast_brain `local`, the model on this
computer answers one word so it's loaded. After your first turn, `brain.claude.session` keeps Claude Code running for
the conversation, so later turns don't start it again.

- **Values:** `true` (default) or `false`. **Default:** on.
- **When to change it:** Turn it off if you don't want the extra start of the AI's program.
- **Depends on:** `voice.listen.on`.

### `voice.listen.live`

Your own turns answered by Gemini Live, speech to speech, in about a second. Their sound goes to Google.

Instead of writing your words out, asking your AI and making the answer's voice here, the turn's sound goes to Google's
Gemini Live (with your Gemini key) and its spoken answer plays through the same speakers or add-on output. A different
AI answers: Google's Live model, with the tools a phone call has. What leaves the computer is the sound of the turns
Kurooto already decided you said to it, and only those: the gate called it addressed (not chatter or noise), Voice ID
said it's your voice, and you were facing it, close by: only turns you say to it while facing it, close by (the face
check saw a face near the camera and turned to it during the turn). A turn let through without a face seen (the wake
word and the request right after it, voice.listen.need_face off, Face presence off or paused, or the camera blind with
voice.listen.need_face_fallback "voice") goes the usual way, as do chatter, other voices and a voice it's unsure of.
With each session goes what a call's setup carries (your name, the assistant's, which tools exist, the lessons from
earlier calls), and a turn's tool results (a note it reads, say). The session stays open while the conversation does and
closes with it. Tools that need your tap ask Approve / Deny first. No key, Google refusing, or no sound within about 5
seconds: that turn goes the usual way. Nothing is written to disk; events hold numbers only. It uses calls.live_model
(then calls.live_models) and calls.voice.

- **Values:** `false` (default) or `true`. **Default:** off.
- **When to change it:** Turn it on if you want quick spoken answers at the desk and are fine with your voice going to
  Google.
- **Depends on:** `voice.listen.on`, a Gemini key, Voice ID (`voice.speaker_id.on`, enrolled) and Face presence.

## Privacy and what it keeps

Where Kurooto may reach on the internet, how long it keeps transcripts, requests and chats, and the one-line gists
conversations settle into as their words fade. Every request Kurooto makes is counted by host; `/egress` shows them.
These settings only ever keep less or reach less. More in [Privacy: what stays and what leaves](privacy.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing: these settings decide what is kept and where requests may go; they
  send nothing themselves.
- **Depends on:** Nothing: core settings, always there.

### `privacy.egress`

Count every request Kurooto makes on the internet, also refuse hosts not on the list, or neither.

- **Values:** `record` (count everything; a host not on the list is counted and still reached), `enforce` (refuse such
  hosts, naming them and how to allow them), `off`. **Default:** `record`.
- **When to change it:** Look at `/egress` for a while on `record`, allow what you trust, then switch to `enforce`.
  Add-ons by link are fenced to their own hosts in every mode.

### `privacy.allow_hosts`

More hosts Kurooto may reach, besides its list and the addresses you set up yourself.

- **Values:** A list of host names: `["feeds.example.org"]`; `.example.org` allows all of it. **Default:** none.
- **When to change it:** Add a host `/egress` shows as not on the list and that you trust, before turning on `enforce`.
- **Costs and what leaves this computer:** Kurooto may reach those hosts.

### `privacy.keep_days`

Transcripts, AI requests and answers, chats and logs are deleted after this many days; 0 keeps them.

- **Values:** Days; 0: kept until you `/forget`. **Default:** `0`.
- **When to change it:** Set it (say, 30) if you don't want old conversations kept. Other features' own retention
  follows it where they say so.

### `privacy.keep_gist`

As a conversation's words fade, it settles into one line of what it decided (`/gists`).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep nothing once the words are gone.

### `privacy.gist_days`

Gists are deleted after this many days; 0 keeps them until you `/forget all`.

- **Values:** A whole number. **Default:** `0`.
- **When to change it:** Set it if even one-line gists shouldn't be kept for long.
- **Depends on:** `privacy.keep_gist`.

### `privacy.gist_model`

A model on this computer adds a sentence to a call's gist.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on for richer call gists; it never uses a cloud AI.
- **Depends on:** `privacy.keep_gist` and Local AI models.

## Updates, backups and upkeep

How Kurooto updates itself, the daily backup zip, Profile sync (your setup, encrypted, in your own private repository),
the Space keeper that clears Kurooto's own leftovers, and the daily health pass. Kurooto only ever removes its own
files: never your notes, books or anything else in a folder you chose. More in [Updates, backups and
moving](updates-and-backups.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Updates are downloaded from Kurooto's release site and checked against its
  signing key. Backups stay on the drive or folder you pick. Profile sync goes, encrypted, to your own private GitHub
  repository.
- **Depends on:** Updates and health are core; Backups, Profile sync and the Space keeper are features of their own.

### `updates.mode`

How updates happen: by themselves at night, after asking you, or not at all.

- **Values:** `night` (download when found, switch in the night window), `ask` (a message with Update / Later), `off`
  (only a note on the dashboard). **Default:** `night`.
- **When to change it:** Pick `ask` if you want to choose when; `off` only if you update by hand (`kurooto update`).
- **Depends on:** Nothing: core.

### `updates.window`

The hours an automatic update may switch versions.

- **Values:** A pair of times: `["03:00", "05:00"]`. **Default:** `["03:00", "05:00"]`.
- **When to change it:** Move it to hours the computer is on and you're not using it.
- **Depends on:** `updates.mode` = `night`.

### `updates.channel`

Stable releases, or beta for every version the day it's signed.

- **Values:** Text. **Default:** `stable`.
- **When to change it:** Pick `beta` to try new things first (and report problems); `stable` for an older, steadier
  version.
- **Depends on:** Nothing: core.

### `updates.staged`

Wait until a release has been out a while (and not during exams) before installing it; critical ones don't wait.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd rather let others find the bugs first.
- **Depends on:** Nothing: core.

### `updates.wait_hours`

Hours a new version must have been out before it's installed.

- **Values:** A whole number. **Default:** `48`.
- **When to change it:** Raise it to wait longer.
- **Depends on:** `updates.staged`.

### `updates.exam_hold`

Nothing installs in an exam period or within a day of a quiz or exam.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if updates during exams are fine.
- **Depends on:** `updates.staged`; exam dates from Subjects and Deadlines.

### `backups.folder`

Where the backup zips go: an external drive or a cloud-synced folder.

- **Values:** A full folder path. **Default:** empty.
- **When to change it:** Set it to a drive that isn't this computer's own disk, so a dead disk doesn't take the backup
  with it.
- **Costs and what leaves this computer:** If the folder is synced by a cloud service, the zips go there.
- **Depends on:** Backups.

### `backups.when`

When the automatic backup runs.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 03:30`.
- **When to change it:** Move it to when the computer is on and the drive is plugged in.
- **Depends on:** Backups.

### `backups.keep`

How many backup zips to keep; Kurooto removes only its own older zips.

- **Values:** A whole number. **Default:** `7`.
- **When to change it:** Raise it to go back further; lower it to save space.
- **Depends on:** Backups.

### `backups.notes`

Include your notes folder in the backup.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on unless Notes sync or something else already backs up your notes.
- **Depends on:** Backups.

### `backups.secrets`

Include passwords and keys (bot token, API keys, sign-ins): anyone with the zip can use them.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on only if the backup folder is somewhere only you can reach. It's what lets a restore
  come back fully signed in.
- **Costs and what leaves this computer:** Your secrets sit unencrypted in the zip.
- **Depends on:** Backups.

### `backups.index`

Include the notes brain's index (big, but slow to rebuild).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep zips small; the index is rebuilt after a restore.
- **Depends on:** Backups.

### `backups.memory`

Include the memory ledger (encrypted: it opens only where its key is).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on to keep gists and threads across a restore; on another computer it also needs
  `backups.secrets`.
- **Depends on:** Backups.

### `backups.confidential_mail`

Include confidential mail summarised on this computer (the Mail digest's local mode).

- **Values:** On or off. **Default:** off.
- **When to change it:** Leave it off unless you need those summaries back after a restore.
- **Depends on:** Backups, and `mail_digest.confidential` = `local`.

### `profile.repo`

Your private GitHub repository for Profile sync; empty uses the one Notes sync uses.

- **Values:** `owner/name`, or empty. **Default:** empty.
- **When to change it:** Set it to keep your profile apart from your notes' repository.
- **Depends on:** Profile sync.

### `profile.when`

When your profile is saved each day.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 04:40`.
- **When to change it:** Move it to when the computer is usually on.
- **Depends on:** Profile sync.

### `profile.after_changes`

Minutes after you change a setting (or turn a feature on or off) that the profile is saved.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Lower it to save sooner after changes.
- **Depends on:** Profile sync.

### `profile.branch`

The branch your saved profile lives on (set by Kurooto).

- **Values:** Text. **Default:** `kurooto-profile`.
- **When to change it:** Never by hand.
- **Depends on:** Profile sync.

### `profile.remote`

For tests only: a local repository instead of GitHub.

- **Values:** Text. **Default:** empty.
- **When to change it:** Never in normal use.
- **Depends on:** Profile sync.

### `space.when`

When the Space keeper clears Kurooto's own leftovers by itself.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `weekly sun 04:30`.
- **When to change it:** Move it to when the computer is on. `/space` cleans now.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper.

### `space.cache_days`

Downloads, made zips and cut-off downloads older than this (days) go.

- **Values:** A whole number. **Default:** `14`.
- **When to change it:** Lower it on a small disk.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper.

### `space.log_mb`

A log file bigger than this (MB) is cut to its newest part.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Raise it to keep more history for troubleshooting.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper.

### `space.jobs_days`

Finished AI requests older than this (days) are forgotten.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it if you search old requests with `/history`.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper.

### `space.undo_days`

The concept graph's before-copies and unfinished work files older than this (days) go.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Raise it to keep Undo for the concept graph longer.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper.

### `space.backups_max_gb`

The most the backup zips may take in all (GB); 0: no limit. The newest is never removed.

- **Values:** A number. **Default:** `3.0`.
- **When to change it:** Set it to fit your backup drive.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper and Backups.

### `space.backups_max_age_days`

Backup zips older than this (days) go; 0: no limit (`backups.keep` still applies).

- **Values:** A whole number. **Default:** `0`.
- **When to change it:** Set it if you only care about recent backups.
- **Costs and what leaves this computer:** Nothing leaves.
- **Depends on:** The Space keeper and Backups.

### `health.on`

The daily health pass: it checks what matters and tells you only when something needs you.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop the daily pass; `/health`, the dashboard and `kurooto doctor` still check.
- **Costs and what leaves this computer:** Nothing leaves beyond the message.
- **Depends on:** Nothing: core.

### `health.when`

When the daily health pass runs; tonight's alarm is checked then.

- **Values:** A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`.
  **Default:** `daily 21:00`.
- **When to change it:** Keep it before bedtime so a broken alarm is found in time.
- **Depends on:** `health.on`.

### `health.auto_fix`

Try a safe fix before telling you (never a sync: that one waits for your tap).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to have every fix wait for your tap.
- **Depends on:** `health.on`.

## This computer

How Kurooto behaves on this computer: starting with it, battery and sleep, which local models and programs it installs
for you, its dashboard's port, the features list, and running every nightly process at once. More in [Your
computer](your-computer.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer, except downloads of the models and programs you
  ask it to install.
- **Depends on:** Nothing: core settings, always there.

### `modules.enabled`

The features that are on. The Features page changes it.

- **Values:** A list of feature ids. **Default:** none.
- **When to change it:** Use the Features page (or `kurooto enable`/`disable`), which sets each feature up properly;
  editing this list by hand skips that.

### `power.on_battery`

What Kurooto does on battery: put off heavy work, carry on as usual, or pause.

- **Values:** `saver` (heavy work waits for the charger; Telegram and reminders keep working), `normal` (as if plugged
  in), `pause` (nothing runs until you plug in; the call line still rings the alarm). **Default:** `saver`.
- **When to change it:** Pick `normal` on a laptop with a big battery; `pause` if you want it quiet whenever you're
  unplugged.

### `autostart.when`

When Kurooto starts: when you log in, or (Linux with systemd) when the computer starts, before anyone logs in.

- **Values:** One of: `login`; `boot` (before anyone logs in (Linux with systemd)). **Default:** `login`.
- **When to change it:** Pick `boot` for a home server or a computer you rarely log in to. Settings → Starting does it
  and says what it did.

### `awake.lid`

Linux: keep running with the lid closed while plugged in.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you keep the laptop shut on a desk. Elsewhere it's the system's own lid setting.
- **Costs and what leaves this computer:** Power while the lid is closed.
- **Depends on:** Stay awake on charger.

### `hardware.force_profile`

Use another hardware profile's models than the one detected for this computer.

- **Values:** Empty (detected), `light`, `apple-8`, `apple`, `small-gpu`, `big-gpu`, `big-gpu-12`. **Default:** empty.
- **When to change it:** Pick a lighter profile if local models make this computer slow; a bigger one only if the
  detection undersold it.
- **Costs and what leaves this computer:** A different profile may download different Ollama models.
- **Depends on:** Local AI models.

### `hardware.extra_models`

Ollama models of your own to install, past what suits this computer.

- **Values:** A list of Ollama model names: `["gemma4:12b"]`. **Default:** none.
- **When to change it:** Add a model you want to use (in `brain.models` or elsewhere).
- **Costs and what leaves this computer:** Each one is downloaded from Ollama's registry, and takes disk space.
- **Depends on:** Local AI models.

### `hardware.extra_prereqs`

Other programs Kurooto should install for you, by id.

- **Values:** A list of ids: `tesseract`, `poppler`, `tectonic`, `git`… **Default:** none.
- **When to change it:** Add a program a feature you use would benefit from (Tesseract for scanned books, say).
- **Costs and what leaves this computer:** Each one is downloaded from its project's site or your system's package
  source.

### `web.port`

The dashboard's port on this computer (read when Kurooto starts).

- **Values:** A port number. **Default:** `8770`.
- **When to change it:** Change it only if another program uses 8770. Restart Kurooto afterwards; bookmarks need the new
  port.

### `runall.on`

`/run all` and `kurooto run all`: every nightly process that's on, now, one after another.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you never want the nightly work run on demand.

### `uninstall.offer`

When you turn a feature off, ask whether to remove what Kurooto installed for it (a model, a program), with its size.

- **Values:** `true` (ask, Remove or Keep; nothing goes without your tap), `false` (never ask; `kurooto installed` and
  `kurooto remove` still work). **Default:** on.
- **When to change it:** Turn it off if you switch features on and off a lot and would rather clear things up yourself.
- **Depends on:** Only what's on Kurooto's install receipt is ever offered: never something that was there before
  Kurooto.

### `uninstall.with_programs`

`kurooto uninstall` also removes the programs and models Kurooto installed for you, not only Kurooto itself.

- **Values:** `true` (everything on the install receipt goes too), `false` (only Kurooto, its settings and data; Ollama,
  Node and the rest stay). **Default:** on.
- **When to change it:** Turn it off before uninstalling if you want to keep using Ollama, Node or the other programs on
  your own.
- **Costs and what leaves this computer:** With it on, models you pulled through Kurooto are deleted and have to be
  downloaded again if you want them back.

## Dashboard and terminal

How the dashboard looks and what's on its board: the design, the board, colours, panes, the being, Study mode and the
talk box; and the Kurooto Terminal, a real terminal window laid out like the dashboard's terminals. Look changes show at
once (the palette reloads the page). More in [The dashboard](dashboard.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing leaves this computer. Fonts and colours come with Kurooto; nothing is
  fetched.
- **Depends on:** Nothing: the dashboard's own settings, always there.

### `look.design`

The dashboard's design: new (sans-serif, rounded panes) or classic (the monospace look of 0.5.18).

- **Values:** One of: `new`; `classic` (the monospace look of 0.5.18). **Default:** `new`.
- **When to change it:** Pick classic if you prefer a terminal look; the board, keys and data are the same in both.

### `look.board`

The board: Kurooto as one living body (being), three panes on top (three), or STATUS on the left (classic).

- **Values:** One of: `being` (Kurooto as one living body, its work lighting up as it happens (0.8.9)); `three` (NOTES,
  SYSTEMS and BRAIN on top, STATUS and TERMINAL below); `classic` (STATUS down the left (before 0.8.3)). **Default:**
  `being`.
- **When to change it:** Pick `three` or `classic` on an older computer or if you'd rather see plain panes.

### `look.layout`

Dense (everything on one full-screen board) or roomy (bigger panes and type).

- **Values:** `dense` (screens 1280 px wide or more; narrower ones get roomy) or `roomy`. **Default:** `dense`.
- **When to change it:** Pick `roomy` on a small screen or if you want bigger type.

### `look.palette`

The colours of Kurooto's pages and terminals: its own palettes, your desktop's, or a named theme.

- **Values:** `kuro`, `rose`, `system` (your desktop's accent and light or dark mode), or a named theme such as a
  Catppuccin flavour. **Default:** `kuro`.
- **When to change it:** Pick the one you like; the dots under it preview the dashboard's and the light pages' colours.
  The page reloads to take it.

### `look.theme_file`

A colours file of your own (a kitty theme, or matugen or pywal JSON) instead of the desktop's.

- **Values:** A full path, or empty. **Default:** empty.
- **When to change it:** Set it if your desktop's colours come from a file; it switches the palette to `system`. Empty
  it to stop.

### `look.panes`

Panes hidden from the dense board: status, systems, notes, terminal.

- **Values:** A list of pane names; empty: none hidden. **Default:** none.
- **When to change it:** Hide panes you never look at (the panes menu on the board does the same).

### `look.brain_monitor`

BRAIN's part monitor: shown beside the model, or in a drawer behind a tab.

- **Values:** One of: `shown` (the part monitor stays beside the model); `drawer` (it slides out from a tab).
  **Default:** `shown`.
- **When to change it:** Pick `drawer` for more room for the model.

### `look.being_theme`

The being's colours: white light on black, or the page's palette.

- **Values:** One of: `void` (white light on black); `theme` (the page's palette). **Default:** `void`.
- **When to change it:** Pick `theme` to have the being match your palette.
- **Depends on:** `look.board` = `being`.

### `look.being_hints`

The being's hints: what to click and what each part is (H on the board toggles them).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn them off once you know your way around.
- **Depends on:** `look.board` = `being`.

### `look.being_resting_sparks`

The being's resting sparks: a low trickle in the brain from what Kurooto does all the time.

Each reading of its body (every 2 seconds) is a spark in the insula, one more for each quarter of the processor in use;
its own processor use keeps the thalamus going in proportion; a timer of the scheduler that fires lights its feature's
region; changed notes light the hippocampus, sound heard the auditory cortex. Events (AI requests, messages, syncs)
spark either way.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather the brain sparked only for events. Remove animations and the
  system's reduced motion turn it off too.
- **Depends on:** `look.board` = `being`.

### `look.being_live_waveform`

The being's YOU lane live: a trace of the microphone's loudness as you speak, the last six seconds.

While Voice listens and the dashboard is open, the microphone's loudness (five numbers every 100 ms, never sound or
words) scrolls through the YOU lane, newest at the right; when your turn ends it settles into that turn's outline, and
with nothing heard for a moment and a half the trace fades out. Remove animations and the system's reduced motion keep
it still: it sweeps across instead of scrolling. Off, the lane shows only each turn's outline once it's over.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the moving trace distracts you.
- **Depends on:** `look.board` = `being`, Voice listening, and `voice.listen.levels` on.

### `look.being_status`

The being as a glance: eyes shut in focus or asleep, the held count by the heart, a glow on the deadline it's uneasy
about.

From Brain's status stream (`mind.status.on`). Tap the glow to open that deadline (Today) or promise (the Brain
console); on the phone's organ pages the same shows as a line under the organ's name. The phone's whole being and organ
pages show it too.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather the being didn't show Brain's state.
- **Depends on:** `look.board` = `being`, Brain on.

### `look.being_mood`

Brain's own mood in the drawing: the fluid's tint and the heart's beat; its pupil and pulse show the three knobs.

A low mood is only quieter (dimmer, a softer, slower beat), never a sad face. Arousal quickens the pulse; the pupil
widens with how much it explores and narrows a little while its beliefs are no better than a guess. It's Brain's mood,
not a reading of you.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep the being's colours and beat as they were.
- **Depends on:** `look.board` = `being`, Brain on.

### `look.talk_box`

A small box over the board to talk to Kurooto in plain English (Alt+K).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you use the terminal or Telegram instead.

### `look.chat_page`

The Chat page (Alt+H): the phone app's chat on the dashboard, live, with its buttons, and a box to write in it.

The same chats and messages as the app: Kurooto's messages and answers with their buttons, files as links, the app's
Waiting for you questions, and what you wrote in the app or on this page. A tap or a message here goes the same way as
one in the app, so a question settles everywhere and the chat's AI context carries. Off, the page leaves the dashboard's
pages and its live messages stop.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only use the chat on your phone or Telegram.
- **Depends on:** Phone calls on (the chat comes with the phone app).

### `look.settings_guide`

On the Settings page, a line under each setting that says what it does and opens its whole guide entry.

With it on, the search box also looks through the entries, so "battery" finds `power.on_battery`. Off, the page shows
only the settings, with what each does when you hover its name.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off once you know your settings and want a shorter page; the guide stays in the user
  wiki.

### `look.study_mode`

The dashboard in Study mode: the notes map, the study timer and what's due (Alt+M, `/study mode`).

- **Values:** On or off. **Default:** off.
- **When to change it:** Usually switched with Alt+M rather than here.
- **Depends on:** The Study tracker for the timer's log.

### `look.projects`

Folders of git repositories the PROJECTS box shows; empty uses Research's repositories.

- **Values:** A list of full paths. **Default:** none.
- **When to change it:** Set it if your projects aren't in Research's list.

### `look.hidden_features`

Features hidden from the Features list (they still run if they're on).

- **Values:** A list of feature ids. **Default:** none.
- **When to change it:** Usually set by hiding a card on the Features page; a search there still finds hidden ones.

### `look.links_in`

Where links to other sites open: this computer's default browser, or the browser showing the dashboard.

- **Values:** `default` or `here`. **Default:** `default`.
- **When to change it:** Pick `here` if the dashboard runs in a browser that isn't your default.

### `terminal.tabs`

The Kurooto Terminal's tabs, in order: your AI's program, your shell, Kurooto chat, the log.

- **Values:** A list of `agent`, `shell`, `chat`, `logs`, and `top`. **Default:** `["agent", "shell", "chat", "logs"]`.
- **When to change it:** Drop tabs you don't use, or reorder them.
- **Depends on:** Kurooto Terminal.

### `terminal.top`

Where `kurooto top` goes: a column beside the first tab, a tab of its own, or nowhere.

- **Values:** One of: `left` (a column beside the first tab); `tab` (a tab of its own); `off`. **Default:** `left`.
- **When to change it:** Pick `tab` on a narrow screen.
- **Depends on:** Kurooto Terminal.

### `terminal.shell`

Which shell the terminal runs: fish if you have it, else yours, or one you name.

- **Values:** `auto`, or a program such as `zsh` or `pwsh`. **Default:** `auto`.
- **When to change it:** Name your shell if `auto` picks the wrong one.
- **Depends on:** Kurooto Terminal.

### `terminal.font_size`

The Kurooto Terminal's font size.

- **Values:** A whole number. **Default:** `11`.
- **When to change it:** Raise it on a high-resolution screen.
- **Depends on:** Kurooto Terminal.

### `terminal.kitty`

Linux and macOS: use kitty (yours, or Kurooto's copy); off uses your usual terminal, a window per tab.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather not install kitty.
- **Costs and what leaves this computer:** Kurooto's copy of kitty is downloaded once, if you don't have one.
- **Depends on:** Kurooto Terminal.

### `terminal.default`

Make Kurooto Terminal your default terminal (turning it off undoes it).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you'd like every new terminal in Kurooto's layout and colours.
- **Depends on:** Kurooto Terminal.

### `terminal.default_opens`

As your default terminal, what a launch opens: one shell tab, or the whole window.

- **Values:** One of: `shell` (one tab); `layout` (all tabs). **Default:** `shell`.
- **When to change it:** Pick `layout` to get every tab each time.
- **Depends on:** `terminal.default`.

## Add-ons

Your own add-ons folder (extra features, skills, prompts and default settings laid over Kurooto), and add-ons by link
from someone else's repository at a pinned commit, each fenced to the hosts on its card. Add-ons run as you, with your
permissions: turn on only ones you wrote or read. More in [Add-ons, scripts and other programs](add-ons.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Your own add-ons run as you and may reach whatever they're written to.
  Add-ons by link reach only the hosts on the card you agreed to.
- **Depends on:** Your add-ons (overlay) and Add-ons by link are features of their own.

### `overlay.path`

The full path of your add-ons folder.

- **Values:** A full folder path. **Default:** empty.
- **When to change it:** Point it at the folder with your modules, skills, prompts and settings.json. Read when Kurooto
  starts.
- **Depends on:** Your add-ons.

### `overlay.code`

Also run the Python add-ons in its modules/ folder (off: only skills, prompts and settings).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to use an add-ons folder's skills and settings without running its code.
- **Depends on:** Your add-ons.

### `addons.on`

Load the add-ons you added by link (`kurooto addons add`); off, none load from the next start.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop all of them at once; they stay where they are.
- **Depends on:** Add-ons by link.

### `addons.official_updates`

Say once when a newer version of an official add-on you have is out; it's never updated by itself.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to stop the message (the update buttons stay on the card).
- **Costs and what leaves this computer:** Nothing beyond the message: Kurooto's own list says what's newer.
- **Depends on:** Add-ons by link.

## The phone app's own settings

Settings that live on the phone itself, in the Android app's Settings, not on your computer: how the app looks, its
ringtones, bedside mode, location reminders, and the senses it may share. Long-press any of them in the app for its
entry here. More in [Your phone](phone-app.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** Nothing: these stay on the phone, except the senses, which go sealed to your
  computer when you switch them on.
- **Depends on:** The Android app, paired with your computer.

### `app.vivid`

Vivid colours from your wallpaper; off uses the wallpaper's quieter colours (Calm).

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off for a quieter app.

### `app.floatingBar`

The navigation bar floats above the screen; off, it sits on the bottom edge.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the floating bar covers things you want to tap.

### `app.moving`

The moving background; off, a still picture.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to save battery or if motion bothers you (Android's Remove animations stops it
  too).

### `app.newCallScreen`

The new call screen (ringing and, since 0.8.16, the call itself); off, the call screens from before 0.8.7.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off only if the new screen misbehaves on your phone.

### `app.direct`

Connect straight to your call line; off, calls and messages come through ntfy.sh only.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off only if the straight connection keeps dropping on your network.
- **Costs and what leaves this computer:** Off, wake-up pushes (no content) go through ntfy.sh.

### `app.viewMode`

Which view the Views tab opens on.

- **Values:** `systems` or `notes` (the Notes map). **Default:** `systems`.
- **When to change it:** Pick the one you look at most.
- **Depends on:** `calls.views` on your computer.

### `app.viewsOrgans`

Views shows the being as four pages, Brain, Heart, Senses and Memory, each organ alone with its parts listed under it.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to see the whole being in one drawing, with the dashboard's panels, as before
  0.8.10's organ pages.
- **Depends on:** `calls.views` and `calls.views_being` on your computer.

### `app.viewOrgan`

Which organ page Views opens on: the one you looked at last.

- **Values:** `brain`, `heart`, `senses` or `memory`. **Default:** `brain`.
- **When to change it:** Nothing to set: tap another page and Views remembers it.
- **Depends on:** `app.viewsOrgans`.

### `app.callTone`

The ringtone for Kurooto's calls; empty is the phone's default.

- **Values:** A ringtone picked from the phone's list. **Default:** the phone's default ringtone.
- **When to change it:** Pick one you'll recognise as Kurooto.

### `app.alarmTone`

The tone for the wake-up alarm; it plays on the alarm stream, so it rings even on silent.

- **Values:** A tone picked from the phone's list. **Default:** the phone's default alarm.
- **When to change it:** Pick one loud enough to wake you.

### `app.bedsideAuto`

Open bedside mode by itself while charging between the hours you set.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on for a phone that lives on a charger by your bed.

### `app.bedsideFrom`

When bedside mode may start opening by itself.

- **Values:** A time `HH:MM`. **Default:** `22:00`.
- **When to change it:** Set it to when you go to bed.
- **Depends on:** `app.bedsideAuto`.

### `app.bedsideTo`

When bedside mode stops opening by itself.

- **Values:** A time `HH:MM`. **Default:** `07:00`.
- **When to change it:** Set it to when you get up.
- **Depends on:** `app.bedsideAuto`.

### `app.bedsideKeepOn`

Keep the screen on while bedside mode is open and charging.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to let the screen sleep; bedside mode still dims at night.

### `app.places.on`

Location reminders: "remind me when I reach the library" for the places you saved.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on (Places) and save your places on the phone.
- **Costs and what leaves this computer:** Where your places are never leaves the phone; your computer only sees their
  names.
- **Depends on:** `reminders.places` on your computer, and location permission.

### `app.senses.screen`

Share when the screen is on and how often you unlock (counts only).

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on if you want Brain's timing to know when you're on your phone.
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line, every 15 minutes.
- **Depends on:** Brain on your computer, with `mind.senses.phone` for this sensor.

### `app.senses.charging`

Share whether the phone is charging.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on to help Brain tell night from day.
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`.

### `app.senses.motion`

Share whether you're still, walking or in a vehicle (worked out on the phone).

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on so messages wait while you're on the move.
- **Costs and what leaves this computer:** Sealed with this phone's key; the accelerometer's readings never leave the
  phone.
- **Depends on:** Brain, with `mind.senses.phone`; the physical activity permission.

### `app.senses.steps`

Share your steps a day.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on if you'd like steps in Brain's picture of your day.
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`; the physical activity permission.

### `app.senses.light`

Share the room's light: dark, dim or bright.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on to help Brain notice lights-out.
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`.

### `app.senses.places`

Share arriving at and leaving your saved places (by name).

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on so Brain knows when you're home or out.
- **Costs and what leaves this computer:** Only the place's name, sealed; where it is never leaves the phone.
- **Depends on:** Brain, with `mind.senses.phone`; places saved in the app.

### `app.senses.headphones`

Share whether headphones are connected.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on to help timing (a call is fine with headphones in, say).
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`.

### `app.senses.dnd`

Share whether Do Not Disturb is on.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on so messages wait while your phone is on Do Not Disturb.
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`.

### `app.senses.alarm`

Share when your next phone alarm is.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on if you set alarms on the phone itself rather than with Kurooto.
- **Costs and what leaves this computer:** Sealed with this phone's key, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`.

### `app.senses.wifi`

Share which Wi-Fi you're on, as a code made on the phone, never its name.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on, then tell Kurooto once what a code is (`/senses wifi label <code> home`).
- **Costs and what leaves this computer:** Only the code, sealed; Android asks for location to read the Wi-Fi name,
  which stays on the phone.
- **Depends on:** Brain, with `mind.senses.phone`; location permission.

### `app.senses.usage`

Share your total screen time a day, never per app.

- **Values:** On or off. **Default:** off.
- **When to change it:** Switch it on if you'd like it in Brain's picture of your day.
- **Costs and what leaves this computer:** Only the day's total, sealed, through your call line.
- **Depends on:** Brain, with `mind.senses.phone`; Usage access in Android's settings.

## Face presence

Kurooto learns your face, on this computer only, and greets you by voice when you sit down at your desk after a while.
The camera looks at a few frames a second at most, only while you're not typing, and never keeps a picture: your face is
a small encrypted template, a stranger's face is dropped with the frame, and nothing is sent anywhere. More in [Face
presence: greet you at your desk](face.md).

For every setting in this group, unless its entry says otherwise:

- **Costs and what leaves this computer:** A little processor time while it watches (about 1-3% of one core), and the
  camera's light on while it looks.
- **Depends on:** The Face presence feature, a camera, and Voice speaking for the greeting.

### `face.away.on`

Notice when you leave the desk and come back.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you want calls and pop-ups held while you're away from the computer.

### `face.away.after_min`

No sign of you (your face or the keyboard) this long means you've left, in minutes.

- **Values:** A whole number. **Default:** `5`.
- **When to change it:** Lengthen it if it decides you've left while you're reading.

### `face.away.hold_calls`

While you're away, calls Kurooto would start by itself wait for you (up to the longest wait below).

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it off if you'd rather a call rings the phone anyway.
- **Depends on:** Noticing when you leave (face.away.on).

### `face.away.hold_desktop`

Hold desktop pop-ups and spoken answers until you're back at the desk.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it off if others at the computer should still see Kurooto's pop-ups.

### `face.away.hold_max_min`

The longest a call waits while you're away, in minutes.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Shorten it for things that can't wait long.

### `face.camera.device`

The camera to use: empty for the first ordinary one (infrared ones are skipped), or a number or part of its name.

- **Values:** Text. **Default:** empty.
- **When to change it:** Set it if you have several cameras and it picks the wrong one (`kurooto face test-camera` lists
  them).

### `face.camera.width`

The picture width asked of the camera (it may give another).

- **Values:** A whole number. **Default:** `640`.
- **When to change it:** Lower it on a slow computer; recognition needs only a small picture.

### `face.camera.height`

The picture height asked of the camera.

- **Values:** A whole number. **Default:** `480`.
- **When to change it:** Change it together with the width.

### `face.greet.on`

Greet you by voice when you arrive at the desk.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you only want it to notice you, without speaking.
- **Depends on:** Voice speaking.

### `face.greet.after_absent_min`

Greet you only after you've been away at least this long, in minutes.

- **Values:** A whole number. **Default:** `20`.
- **When to change it:** Raise it if it greets you after short breaks.

### `face.greet.gap_min`

The fewest minutes between two greetings.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it if the greetings feel too frequent.

### `face.greet.per_day`

A daily cap on greetings.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Lower it to one for just a morning greeting.

### `face.greet.say`

What the greeting tells you: what's next today, what's waiting, deadlines in 24 h, what was held while you were away.

- **Values:** A list, typed as JSON. **Default:** `["next", "waiting", "deadline"]`.
- **When to change it:** Trim it to what you want to hear first when you sit down.

### `face.greet.talk`

After the greeting, listen for a reply without its name being said.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather start every talk by saying its name.
- **Depends on:** Voice listening.

### `face.greet.listen_s`

How long that conversation stays open with nothing said, in seconds.

- **Values:** A whole number. **Default:** `12`.
- **When to change it:** Shorten it if it keeps listening longer than you'd like.

### `face.greet.with_others`

When someone else is in view too: skip the greeting, say just "Welcome back.", or the full greeting.

- **Values:** `skip`, `short`, `full`. **Default:** `skip`.
- **When to change it:** Leave it on skip so your day isn't read out in front of others.

### `face.track.on`

While the camera is open, follow every face in view (where it is and how much it moves) for the being's eye.

Each face gets a number that stays with it from frame to frame, its place, its size, whether it's you and how much it
moves (small nods and turns). The being's eye looks at one person, then another every few seconds, sooner when someone
new appears or moves more. Nobody else is identified, nothing is kept, and it never opens the camera by itself.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if you'd rather the eye only finds you, or to save the processor time.
- **Costs and what leaves this computer:** With a dashboard in sight, roughly a tenth of one processor core while the
  camera is open.
- **Depends on:** Face presence watching; a dashboard page in sight, or an add-on that follows faces.

### `face.track.fps`

How many times a second it looks for faces while following them (1 to 15).

Only finding faces runs this often; recognising you stays at face.watch.fps. On a slow computer it lowers itself when a
look takes too long.

- **Values:** A whole number. **Default:** `10`.
- **When to change it:** Lower it to save processor time; raise it for a livelier eye.
- **Costs and what leaves this computer:** Each look a second costs about 1% of one processor core.
- **Depends on:** face.track.on.

### `face.addons.watch`

Let an add-on see who's in view: each face's place, size and numbers, in memory only, never a picture.

An add-on gets every face in each frame Face presence already looks at: where it is, how big, which way it's turned,
whether it's you, someone else or unsure, and its numbers (kept by the add-on only if it says so). With no add-on
asking, nothing is worked out for it.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off to keep add-ons from seeing faces at all.
- **Depends on:** An add-on that uses it; Face presence watching (every pause still applies).

### `face.addons.hold`

Let an add-on keep the camera looking while you type (never past a pause, the night, a call or a switch).

Normally the camera closes while you use the keyboard and mouse. An add-on may ask it to keep looking, for at most 10
minutes at a time unless it asks again; the Face card and /face then say which add-on and why. Every pause reason still
comes first. While it looks, other programs (a video call) can't use the camera on Linux.

- **Values:** On or off. **Default:** on.
- **When to change it:** Turn it off if the camera's light on while you type bothers you, or you want the camera free
  for calls.
- **Costs and what leaves this computer:** The camera's light on, and a little processor time, while an add-on holds it.
- **Depends on:** An add-on that uses it; Face presence watching.

### `face.learn.on`

Slowly refine your face template from times it was very sure it was you (never unsure ones), with Undo.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if your look changes (glasses, a beard, the light at your desk) and you'd rather it
  keeps up.

### `face.learn.every_h`

At most one new sample this often, in hours.

- **Values:** A whole number. **Default:** `6`.
- **When to change it:** Raise it to make the template change more slowly.

### `face.learn.margin`

How far above your threshold a frame's score must be before it may refine your template.

- **Values:** A number. **Default:** `0.08`.
- **When to change it:** Raise it to learn only from the surest frames.

### `face.learn.max`

At most this many learned samples (the oldest goes first); the enrolled ones are never replaced.

- **Values:** A whole number. **Default:** `30`.
- **When to change it:** Lower it to keep the template closer to your enrolment.

### `face.recognise.frames`

Recognised in this many of the last 4 frames means you're here.

- **Values:** A whole number. **Default:** `3`.
- **When to change it:** Raise it if it thinks you've arrived when you only passed by.

### `face.recognise.min_face_px`

Faces smaller than this many pixels are ignored: too far away to judge.

Pixels of a 640x480 (or 480x640) picture; a sharper camera scales it (2.25 times at 1080x1440).

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Lower it if you sit far from the camera.

### `face.recognise.strictness`

How rarely a stranger may pass: loose (1 in 100 frames), normal (1 in 1,000) or strict (1 in 10,000).

- **Values:** `loose`, `normal`, `strict`. **Default:** `normal`.
- **When to change it:** Strict if others often sit at your desk; loose if it fails to recognise you in poor light.

### `face.recognise.threshold`

0 uses the calibrated threshold; a score from 0 to 1 overrides it (never below 0.363).

- **Values:** A number. **Default:** `0.0`.
- **When to change it:** Leave it at 0 unless the live test on the Face page shows it gets it wrong.

### `face.watch.fps`

How many pictures a second it checks while waiting for you (0.2 to 2).

- **Values:** A number. **Default:** `1.0`.
- **When to change it:** Lower it to save processor time; raise it if it's slow to notice you.

### `face.watch.fps_battery`

Frames a second while the computer is on battery.

- **Values:** A number. **Default:** `0.33`.
- **When to change it:** Lower it (or to 0) to save battery.

### `face.watch.look_fps`

While Voice listens for a look (voice.listen.look_to_talk), the camera checks at least this many pictures a second.

A look opens the conversation after voice.listen.look_dwell_s of frames (by your eyes, at the first one:
voice.listen.look_gaze_dwell_s), so a faster rate makes it react sooner. It applies only while Voice holds the camera to
listen; otherwise face.watch.fps does. At most 5; a slow computer halves it as it does face.watch.fps.

- **Values:** Frames a second, 0 to 5 (default 5; 0 keeps face.watch.fps). **Default:** `5.0`.
- **When to change it:** Lower it to save processor time; raise it if a look is slow to open it.
- **Costs and what leaves this computer:** A frame takes about 50 ms of one processor core at 1080x1440 (finding faces
  14, recognising you 29, your eyes 7; a Ryzen 7 laptop), so 5 a second is about a quarter of one core while Voice
  listens.
- **Depends on:** `voice.listen.look_to_talk`; Voice listening.

### `face.watch.idle_s`

Seconds with no keyboard or mouse before the camera looks; while you type it doesn't need to.

- **Values:** A whole number. **Default:** `60`.
- **When to change it:** Raise it to keep the camera off more of the time.

### `face.watch.night`

Also look during the night hours (Availability's night); off pauses it at night.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you work at your desk at night and want the greeting then too.

### `face.watch.when_locked`

Also look while the screen is locked; off pauses it while locked.

- **Values:** On or off. **Default:** off.
- **When to change it:** Turn it on if you want it to notice you arriving at a locked computer.
