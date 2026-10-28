# AI models

The AI model is the AI that reads your messages and does tasks: answering questions, writing notes, filing files,
running skills. Kurooto doesn't come with one; you pick one in the setup page's AI step, and you can change it any
time (Dashboard → Settings → AI model, or the setup page). Instant requests ("remind me at 9", "what's due?") never need
the AI model: they run on your computer without any AI.

- [The AI models you can choose](#the-ai-models-you-can-choose)
- [Main and fallback](#main-and-fallback)
- [Two Claude accounts](#two-claude-accounts)
- [How hard it thinks (effort)](#how-hard-it-thinks-effort)
- [Free limits and the reserve](#free-limits-and-the-reserve)
- [What the AI can do (its tools)](#what-the-ai-can-do-its-tools)
- [AI requests and the queue (/jobs)](#ai-requests-and-the-queue-jobs)
- [What goes along with every request](#what-goes-along-with-every-request)
- [Settings](#settings)

## The AI models you can choose

| AI model | Cost | Good for | Setup |
|---|---|---|---|
| **Antigravity (agy)** (marked ★ on the setup page) | free with a Google account | Google's agent program, run on your computer: it can read your notes and act within strict limits. Higher limits than a free key. | Install agy → Open the sign-in window → sign in with Google → Test it |
| **Gemini API key** | free tier, or paid | the simplest, and the way Google recommends for tools like this. Also what phone calls, voice notes and the alarm always use. | Google AI Studio → Create API key → paste it (starts with `AIza`) → Save and test |
| **Claude Code** (Advanced) | needs a paid Claude plan | if you already pay for Claude: the same reach as agy | Install → sign in with your Claude account → Test it |
| **Ollama on this computer** | free | private and offline, but much weaker; needs a good graphics card. Best as a helper next to another AI | Install Ollama → Test |
| **Another OpenAI-compatible service** | depends | any service that works like OpenAI's (OpenRouter, Groq, Together, LM Studio on this computer...) | its address (usually ends in `/v1`), key and model name |

**About agy.** Kurooto runs Google's official agy program on this computer, signed in as you, and never touches its
sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to your
Google account. For tools like Kurooto, Google recommends a Gemini API key.

**About a free Gemini key.** On the free tier, Google may use what you send and what it answers to improve its
products, and human reviewers may read it. You must be 18 or older. In the EEA, the UK and Switzerland you need a paid
key (billing on). Free keys have small daily limits; the setup page warns that they run out quickly, so they're best
kept for calls and voice notes, with agy or another AI model for everything else. Phone calls and voice notes always go
through Gemini, whichever AI answers your messages; if you don't want Google's free-tier terms there, use a paid key.

**About Claude Code.** Each request run by Claude Code gets only what Kurooto gives it, for that request: Kurooto's
tools (and your own GBrain's, if you use one), reading your notes, course files, Documents, Downloads and Screenshots,
writing in your notes, course-files and add-on skills folders, reading web pages, and harmless commands (`ls`, `cat`,
`grep`, `ls`, `pdftotext`...; none that can start another program through its options, so not `find`, `git`,
`latexmk`, `rg` or `sort`). Anything else is refused, and the answer says what was refused.

**Your own scripts.** To let your AI programs run a script of yours unattended (one that does one thing, such as
`make-figures`), put its full path in `agents.scripts` (Settings → Skills in other AI programs, or settings.json). It's
allowed by its path, and by its name when it's on your PATH. Shells and interpreters (`bash`, `python`, `node`...) are
never accepted there: they would run anything. It must be a program: on Windows one ending in `.exe`, `.bat` or
`.cmd` (your `PATHEXT`), elsewhere a file with its execute bit set.
Nothing is saved in Claude Code's own settings, and your own Claude Code hooks, projects and history aren't used. The
`kurooto` command itself never runs from a request. Models: `brain.models.claude` (default `haiku` for quick
requests, `sonnet` for the rest).

**Claude Code kept running for a conversation (0.8.17).** Your chat with Kurooto (Telegram, the phone app, voice)
keeps one Claude Code running between turns instead of starting it again for each message, so answers start sooner
(no program start-up each turn) and it remembers the conversation itself. It gets exactly the permissions, tools and
folders a fresh run would; a request with other ones (another effort or model) gets its own. It closes after 10
minutes without a message (`brain.claude.session_idle_min`), when you change your AI, when you `/new` the chat, and
when Kurooto stops; if it ever fails, that message is answered the old way. Off: `brain.claude.session` = false (each
message starts Claude Code fresh, as before).

**Ollama** runs models on your computer. Without a graphics card (or Apple Silicon) it's too slow to be your main
AI model. With **Local AI models** on (see [your-computer.md](your-computer.md)), a small model on your computer answers
the quick "how hard is this?" question and makes the notes index; your main AI model still does the real work. A small
model that can't use tools just answers without them.

**Reading pictures.** Photo to dates ([reminders-and-deadlines.md](reminders-and-deadlines.md#photo-to-dates)) needs
an AI that reads pictures. agy and Claude Code open the photo where it was saved; a Gemini key gets it with the
request. Ollama does when its model reads pictures (gemma3, gemma4, llava...; Kurooto asks Ollama, and with a model
that doesn't it says so instead of sending it). Another OpenAI-compatible service gets the photo with the request; if
it can't read pictures, the answer says so.

**Retired:** Codex is no longer offered. If a setting named it, it's cleared, and the next request says to choose
another AI in Settings → AI. An AI set up with an earlier version as "FreeLLMAPI" keeps working and shows as "Another
OpenAI-compatible service".

**Checking it works:** `/brain` on Telegram lists the main and fallback AI model and whether each is ready. The setup
page's **Test it** asks the AI for a reply and says what to do if it fails:

| AI model | When the test fails |
|---|---|
| Gemini key | Copy the key again from Google AI Studio (all of it; it starts with `AIza`). "Limit": wait a minute, or use a paid key. |
| agy, Claude Code | Open the sign-in window again, finish signing in, close it, test again. |
| Ollama | Make sure Ollama is running (open the Ollama app, or `ollama serve`), then test again. |
| Another service | Check the address (usually ends in `/v1`), the key and the model name. |

## Main and fallback

- `brain.main`: the AI that handles requests.
- `brain.fallback`: another one that takes over when the main one is at its limit, signed out, refused the request,
  failed or gave no answer. Empty means none. Set it in Dashboard → Settings → AI model.

When the fallback answers, the answer says so in one line. Three more rules:

- **At a limit, the other AI answers (0.6.0).** When Claude Code hits its limit (its 5-hour window or the weekly
  cap), the request goes to agy, and the other way round; a Gemini key you saved comes after them. The run receipt
  says so: *Claude Code hit its limit; agy answered · 3.8-flash · medium · 40 s*. The AI at its limit is then skipped
  until it resets (the time it said, like "resets 3pm"; otherwise half an hour, then an hour, up to 5 hours), so the
  next requests go straight to the other one without waiting for a refusal. A Claude limit belongs to the account that
  hit it: sign in to another account in Claude Code (`/login`, or an account switcher) and Kurooto uses it straight
  away instead of waiting for the first one's reset (0.8.10). An AI only stands in once it has answered
  on this computer (a request, or the setup page's test). That's the automatic order, used when you haven't picked a
  fallback: `brain.fallback` can also be a list (`["agy", "gemini"]`), which then is the order, tried on any failure.
  `brain.fallback_on` sets what moves a request on: `rate_limited` (the default), and also `auth` (signed out) and
  `timeout` if you add them; `[]` turns the automatic order off. The
  concept graph's reading and second looks move the same way, and what a stand-in reads counts on its own nightly
  budget, not the other AI's. `/usage` and `/brain` show who is at a limit and until when.
  Two things aren't a fallback: with the internet down, a request waits for it (the
  [offline helper](your-computer.md#the-offline-helper)) instead of going to the next AI; and dreaming may learn that
  your first fallback does better at some effort level and try it first there (`brain.fallback_first`, with Undo).

- **A free Gemini key stretches further:** when one Gemini model's free daily limit is used up, the next model of the
  same family answers (`gemini-flash-latest`, `gemini-flash-lite-latest`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`).
  Smaller or older models answer less well, so the answer says which one it was: "(Answered with ...: ...'s free limit
  for today was used up.)"
- **Last resort:** if your main AI model is a Gemini key and nothing else can answer, the request goes to an agent
  program (agy or Claude Code) that is installed and has worked on this computer before. The other way round happens
  only at a limit, in the automatic order: a refusal, an empty answer or an error from an agent
  program doesn't go to your free Gemini key, because its limit is small and kept for calls.

## Two Claude accounts

If you have more than one Claude subscription (a personal and a work one, say), each can be signed in and used as a
separate AI (0.7.0). Your usual sign-in (`claude`) stays exactly as it is.

**Adding one:**

1. Setup page (`kurooto setup brain`) → AI → **Claude Code** (set up the usual one first: install, sign in, Test it).
2. Under **Another Claude account**, type a short name (`work`) and press **Add another Claude account**.
3. A sign-in window opens for that account only: sign in with your *other* Claude account, then close the window.
4. Press **Test it** next to it. Once it answers, it's ready.

In a terminal instead: `kurooto ai add-claude work` (Claude Code starts right there for that account: sign in, then
type `/exit`), then `kurooto ai test claude:work`. `kurooto ai accounts` lists them.

Using a second subscription to get around the first one's usage limits may not be allowed by Anthropic's terms; check them for your use.

**What it shows:** each extra account is its own AI, `claude:work`, named "Claude Code (work)":

- **its own limits**: one at its 5-hour or weekly limit doesn't hold up the other;
- **at a limit, the other account answers first** (with no fallback picked): Claude Code → Claude Code (work) → agy →
  a Gemini key. The run receipt says so: *Claude Code hit its limit; Claude Code (work) answered · opus-4.5 · ...*;
- `/brain`, `/usage`, `kurooto usage` and the AI's own page about Kurooto (`self.md`) name each account, and which is
  at its limit until when; the dashboard shows it as "claude (work)".
- Use its id wherever an AI is named: `brain.main` = `claude:work`, `brain.fallback` = `["claude:work", "agy"]`, the
  concept graph's `integrate.roles`. Models: `brain.models["claude:work"]`, else the same as `brain.models.claude`.

**Where its sign-in lives:** in a folder of Kurooto's (data folder → `claude-accounts/work/`; Claude Code's
`CLAUDE_CONFIG_DIR`). Kurooto never opens, copies or prints what's in it, never writes in your own `~/.claude`, and
leaves it out of backups unless `backups.secrets` is on. A profile restored on another computer brings the account's
name but not its sign-in: press **Open the sign-in window** for it there.

**Rename or remove:** dashboard → Settings → **Claude accounts**. Type a new name (its id stays, so your settings keep
working). **Remove** asks first, then deletes only Kurooto's folder for it (your Claude account itself isn't touched)
and takes it out of `brain.main` and `brain.fallback`. Terminal: `kurooto ai rename-claude work "day job"`,
`kurooto ai remove-claude work`.

## How hard it thinks (effort)

Each request runs at low, medium or high effort. Higher effort uses a stronger or slower model and is allowed more
time.

- **Choose it yourself:** start a message with `low:`, `medium:` (or `med:`) or `high:`. Example: `high: derive the
  normal equations for least squares`.
- **Otherwise Kurooto picks.** Requests about notes, revision, summaries, explanations, derivations, proofs or exam prep
  always get high. Others are judged by the rules, your AI or a local model (`brain.classify`: `rules`, `main` or
  `ollama`; default `rules`), and medium is the default. With the [offline helper](your-computer.md#the-offline-helper)
  on, it judges where the rules would otherwise decide alone. Anything that changes, schedules or remembers something
  is never treated as a quick lookup.
- **Time limits:** a request is stopped after `brain.timeout_min` minutes: 10 for low, 15 for medium, 30 for high.

## Free limits and the reserve

Free AI has a daily limit, and Google doesn't say how much is left. Kurooto counts requests itself and keeps the end of
the day's limit for what you're waiting on: calls, voice notes, the morning plan and your own requests.

- **It learns the limits.** The first time a service answers "limit reached", Kurooto keeps the number it names or,
  when it names none, how many requests the day had. It learns when the limit comes back the same way; otherwise it
  assumes Google's day, which ends at midnight Pacific time (`/usage` shows that in your time). Each model of your
  Gemini key has its own limit, and agy has one (counted from agy's own logs, so runs you type yourself count too).
  Until a limit has been hit once, it isn't known and nothing waits.
- **Background work waits past 70%.** Once the day's count passes 70% of a known limit, work nobody is waiting for
  waits: the Classroom digest, the nightly look back, skill changes it suggests, research digests, and book and
  handwritten pages read by Gemini. The quick "how hard is this" question moves to the model on your computer or to the
  rules. Nothing is dropped: waiting work runs after the reset. Your own requests never wait; a used-up limit is
  tried last, after your fallback.
- **One plain line instead of an error:** "Google's free limit for today is used up, resets at 12:30; your calls and
  alarm still work." Calls use a different Gemini model with its own limit.
- **`/usage`** lists AI requests per day over the last 7 days (`/usage 14` for two weeks, up to 60), per AI model, how
  often a limit was hit, today's limits ("143 of 250 requests (57%); background work waits from 175. Resets at
  12:30.") and how many background requests wait for a reset. If agy is on this computer, it also counts agy's own runs
  from agy's logs (only counted; nothing in the logs is read out). Quick checks (how hard a request is, grading a quiz
  answer) and phone calls aren't counted. In a terminal: `kurooto usage [days]`. Needs Chat on.

| Setting (Settings → AI limits) | Default | Effect |
|---|---|---|
| `quota.on` | `true` | `false`: background work never waits (counting and the plain line stay) |
| `quota.background_pct` | `70` | the share of a known daily limit after which background work waits |
| `quota.limits` | `{}` | your own numbers, which win over learned ones, e.g. `{"gemini:gemini-flash-latest": 250, "agy": 900}` |
| `quota.soft` | `learned` | `learned`: a limit Kurooto learned from its own count is only a measure (shown, never a reason to wait); `all`: Google's numbers too; `off`: every known limit keeps its reserve |
| `quota.local` | `quick` | `quick`: only the "how hard" question moves to the local model; `background`: background work moves there too instead of waiting (a small model writes weaker digests); `off`: nothing moves |

Only counts and times are kept (`quota.json` in Kurooto's state folder). Delete that file to forget what was learned.

**Subscriptions (Claude Code, agy) and the concept graph.** A Claude plan has a rolling 5-hour window and a weekly
cap, shared between Kurooto and your own Claude chats and Claude Code, and Anthropic doesn't publish the numbers. The
one big background job, the concept graph reading your books at night, therefore has a budget of its own that learns
your plan: it starts small, grows after nights with no limit hit, halves at a limit, waits for its reset, and leaves
40% of a window for you. It starts reading 5 hours before you usually wake, so a window it opens has reset when you
get up. With a free Gemini key it takes 60% of the day's limit; with a paid API key, at most $0.50 a night. Details:
[Notes and the concept graph](notes-and-concept-graph.md). `/usage` shows tonight's budget and the last limit hit.

## What the AI can do (its tools)

Your AI doesn't only answer: it can act, the same way in Chat, on a phone call and in background requests. Each feature
you turn on adds its own tools; a feature that's off has none. Examples: add a reminder, call you back later, hold
calls, add a deadline or mark one done, log study time, create a note or add to one, tick a `- [ ]` task, edit a note
when you ask, read your files and web pages, send you a file from your notes (over 50 MB as a Drive link, with Drive
upload on), say how your syncs are doing ("what's the sync status?"), and ask you a question when it needs your
answer.

**What it may read and write** (the same for Kurooto's own tools, agy and Claude Code):

- **Read:** your notes folder; your Documents, Downloads and Screenshots folders; Kurooto's copies of Classroom (course
  files) and mail (the digest's batches); the files you attached on the dashboard's Chat page (0.9.0, once there are
  any). Hidden files and folders (like `.git`) are left out, and a link leading
  anywhere else is refused.
- **Write:** your notes folder, the folder Classroom's course files go to, and (with Your add-ons on) your add-ons'
  `skills/`. Text files only (`.md`, `.txt`, `.tex`, `.bib`, `.csv`, `.json`, `.yaml`...). Documents and Downloads
  stay read-only.
- **Your own text:** it creates notes and adds to them. It changes existing text only with `edit_note`, when you asked,
  one exact passage at a time, and that change comes to you as a [proposal](proposals.md) you apply (with
  `proposals.notes_edits` off it changes the note and keeps the previous version first: Kurooto's state folder →
  `note-history/`, the last 20 per file).
- **Change requests** (Help with your project, a change to your notes you asked for, a fix Dreaming proposes): it may
  write in a scratch folder of its own and nowhere else, and what it did reaches your files only when you tap Apply on
  its proposal. Claude Code's permissions for that request allow editing only the scratch folder; agy's own allow-list
  is the same for every run, so for agy it's Kurooto's tools that keep it there, and the proposal names anything in
  the original that changed while it worked. [Projects and proposals](proposals.md).
- **The web:** a public page as plain text (at most a few MB); never this computer or your local network.
- **Never:** send anything to anyone but you, or run the `kurooto` command.

The AI is told to say plainly when it couldn't do something, never to claim it did. If it says it did something and
nothing happened, tell it so and check `/jobs`.

**agy's permission question.** agy gets Kurooto's tools once: when you test agy on the setup page (the page lists what
it allows), or, if you set agy up before, when you tap **Approve** on the question Kurooto asks. **Deny** means agy
works without Kurooto's tools, and Kurooto asks again after 30 days at the earliest; it also asks before adding more
later (for example when you turn on add-ons). Approving adds Kurooto's rules to agy's own settings file (a backup is
kept in Kurooto's state folder → `backups/`; your own rules stay). To take them away: `agy mcp remove kurooto`, then
delete Kurooto's lines from agy's settings (or put back the backup).

**Your own agent programs** can use the same tools: add `kurooto mcp` as an MCP server in any MCP client (it works
while Kurooto is running). See [add-ons.md](add-ons.md).

## AI requests and the queue (/jobs)

Requests that may take minutes run in the background; Kurooto replies "On it." and the answer comes back as a reply to
your message. Answers longer than about 7,000 characters also come as a file.

- **Two lanes.** Your own requests (Telegram, calls, the terminal, the dashboard) have their own lane and never wait
  behind background work (the morning plan, routines, automatic revision packs, digests).
- **`/jobs`** lists what's running and waiting, each with a **Cancel** button (and **Cancel all** when there are
  several), then the last few that finished with their effort, time and result. `/jobs cancel <id>` or `/jobs cancel
  all` from the keyboard; `kurooto jobs --cancel ID` in a terminal. A running agent program is stopped with everything
  it started.
- **Stuck requests.** A watchdog stops a request with no AI at work and no program running for `jobs.stuck_min`
  minutes (10), or one past its time limit: "It got stuck (nothing was happening), so I stopped it. Send it again to try
  once more."
- **No internet.** A request that needs it waits instead of failing ("No internet connection right now: it waits and
  runs as soon as it's back"), runs when the connection is back, and its answer says it waited; after 24 hours it ends
  with a message. `/jobs` shows it as waiting for the internet connection. See
  [the offline helper](your-computer.md#the-offline-helper).
- **The run receipt.** See below.
- **What failures say:**

| Reply | Meaning |
|---|---|
| "... isn't signed in any more (or its key stopped working)" | Open the setup page (`kurooto open`) → AI → sign in again. |
| "... has hit its usage limit for now" | The other AI program answers meanwhile if it's set up (no fallback picked, or `brain.fallback``); otherwise wait, or set a fallback (`brain.fallback`). |
| "The AI stopped without an answer: it tried something unattended runs aren't allowed to do" | Rephrase it, or do that part yourself. |
| "The AI gave no answer this time" | Try rephrasing. |
| "No answer in time; the request was stopped" | It ran past `brain.timeout_min`. Ask with `low:` or split it up. |
| "It waited for the internet connection for 24 h and didn't run" | The internet stayed down. Send it again once you're online. |

When Kurooto stops (shutdown, update), running requests stop where they are and run again at the next start.

## The run receipt

Every answer from your AI ends with one short line, in italics on Telegram and as plain text in the dashboard and the
terminal:

*agy · 3.8-flash · medium · 42 s · 12% of today's limit · searched notes, wrote 1 note, set 1 reminder*

It's built from Kurooto's own record of the run, never from the answer's words, so an AI that says "I've added it to
your notes" without using a tool for it shows up: the line says what it did.

- **Which AI, which model and effort**: the one that answered (a fallback, if the main one couldn't), the model it
  actually ran with, shortened (agy: the `--model` it was started with, `gemini-3.8-flash-medium` → `3.8-flash`;
  Claude Code: the model it says it used, `claude-opus-4-5-...` → `opus-4.5`, or the one it was given), and how hard
  it thought.
- **Who decided**: when a small model picked the effort (`brain.classify`) and it isn't the one that answered, the
  line starts with it: *decided by gemma4:e4b, answered by Claude Code · opus-4.5 · high · 2 min · ...*.
- **Who stood in**: *Claude Code hit its limit; agy answered · ...*, or *Claude Code is at its limit until 15:00; agy
  answered · ...* when the limited one was skipped.
- **Time**: from the start of the run to the answer, fallback tries included.
- **Share of today's limit**: only when Kurooto knows the limit (learned from a "limit reached" answer, or set in
  `quota.limits`); `/usage` shows them all.
- **What it did**: Kurooto's tools it used, counted: "searched notes", "read 2 notes", "wrote 1 note", "set 1
  reminder", "used 1 other tool". "did nothing" means it used none. agy and Claude Code can also read and write files
  with tools of their own, which Kurooto doesn't see: for them it says "did nothing through Kurooto". A tool that
  was used but failed still counts.

Failed requests get it too. Quiet background work that doesn't message you (the look back, the concept graph) gets
none. Turn it off with `jobs.receipt` = `false` (Settings → AI jobs). `/jobs` and the dashboard's AI jobs page show the
AI and model of each finished request too (the receipt is the result's tooltip there).

## Your AI knows what's running

Ask it "why didn't my alarm ring?", "which model answered that?" or "is Claude at its limit?" and it answers from the
facts: Kurooto keeps a short page of what it's running, `self.md` in its reserve folder (state folder → `reserve/`),
which your AI reads first for any question about Kurooto itself:

- Kurooto's version and update channel, this computer's system and hardware profile;
- the AIs set up, their models, the fallback order, any at a limit and until when, today's counts;
- each feature that's on and whether its health check passes, and which are off;
- the last day's failures, counted by kind (a request that hit a limit, a sync that failed: never what it was about);
- where the log and settings are, and what to send to look further (`/health`, `/fixme`, `kurooto doctor`).

It holds no messages, notes, request titles or secrets. It's written at start, every 10 minutes when something
changed, and when it's read after the version, the features, the AI settings or the update channel changed. Beside it
is a manual for the AI (how Kurooto works, what it may and may not do), shipped with each version. Your AI reads them
with the tool `kurooto_self`; agent programs also get them as `kurooto://self` and `kurooto://manual` through `kurooto
mcp`; `/fixme`'s **Ask my AI** sends `self.md` along. It goes to the AI you picked only with a question about Kurooto
itself, never with your other requests.

## The plan line

Before an answer that will likely take a while, one short line says what's coming: "Searching your notes, then
answering (about 40 s with agy)."

- **When**: the request is one of yours as text (Telegram, the phone app's chat, the dashboard), and your last
  requests on that AI at that effort took a median of more than 20 seconds (it waits until there are three to go on).
- **What it says**: from what's known before the run: "Opening the file you sent", "Reading the link", "Searching your
  notes" (when you mention your notes), "going over 2 remembered items"; otherwise "Thinking it through". Then the
  usual time and the AI. The run receipt under the answer says what it really did.
- **Never**: on a call (a call's requests are quiet, and none goes while you're on one), for background work, or in
  the terminal.

Turn it off with `jobs.plan_line` = `false` (Settings → AI jobs).

## What goes along with every request

Every request carries a short context: who you are, the time and time zone, where your notes are, and the rules (plain
text, never reword your notes, never claim what it didn't do). Two things of yours go along too:

- the **In brief** part of your profile (`about-me/profile.md`, the section under `## In brief`), built in the setup
  page's About you step; `/aboutme` shows it;
- a short version of your **how-to-help-me** note (what you told it with `/remember`).

Both are yours to edit: see [teaching-kurooto.md](teaching-kurooto.md). Answers come in the language you write in
(`you.language` = `follow`); set it to a language name, e.g. `German`, to always get that language.

## Settings

Dashboard → Settings → AI model (and quota, jobs, you):

| Setting | Default | Effect |
|---|---|---|
| `brain.main` | empty | the AI that handles requests: `agy`, `gemini`, `claude`, `ollama` or `custom`, or an extra Claude account (`claude:work`) |
| `brain.fallback` | empty | the AI that takes over when the main one can't answer, or a list of them in order (`["agy", "gemini"]`); empty: at a limit, the other agent program, then a Gemini key |
| `brain.claude_accounts` | `{}` | your extra Claude accounts, each its own AI `claude:<name>` ([Two Claude accounts](#two-claude-accounts)); change them in Settings → Claude accounts |
| `brain.fallback_on` | `["rate_limited"]` | what moves a request on to the automatic order: `rate_limited`, `auth`, `timeout` (`[]`: off) |
| `brain.classify` | `rules` | who judges how hard a request is: `rules`, `main` or `ollama` |
| `brain.models` | `{}` | models per AI and effort, e.g. `{"custom": {"low": "...", "medium": "...", "high": "..."}}`, `{"claude": {"high": "opus"}}` |
| `brain.base_urls` | `{}` | override a preset's address |
| `brain.timeout_min.low` / `.medium` / `.high` | `10` / `15` / `30` | minutes a request may run |
| `brain.agy.io_mode` | `pipe` | how Kurooto talks to agy (leave it unless agy gives no output) |
| `jobs.stuck_min` | `10` | minutes without progress before a request is stopped (Settings → AI jobs) |
| `jobs.header` | `true` | (0.8.17) the first line of each answer, "[Claude Code · medium] what you asked"; off: the answer alone (a failed request keeps it) |
| `jobs.receipt` | `true` | the run receipt: one quiet line under each answer saying which AI and model, who decided, who stood in, effort, time, limit used and what it did |
| `you.language` | `follow` | answer in the language you write in, or always in the one named |

**What leaves your computer:** what you ask, and the notes and files the AI reads for it, go to the AI service you
picked, under that service's terms. Ollama and an OpenAI-compatible server on your own computer keep it there. See
[privacy.md](privacy.md).
