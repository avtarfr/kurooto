# AI brains

The "brain" is the AI that reads your messages and does tasks: answering questions, writing notes, filing files,
running skills. Kurooto doesn't come with one; you pick one in the setup page's AI step, and you can change it any
time (Dashboard → Settings → brain, or the setup page). Instant requests ("remind me at 9", "what's due?") never need
the brain: they run on your computer without any AI.

- [The brains you can choose](#the-brains-you-can-choose)
- [Main and fallback](#main-and-fallback)
- [How hard it thinks (effort)](#how-hard-it-thinks-effort)
- [Free limits and the reserve](#free-limits-and-the-reserve)
- [What the AI can do (its tools)](#what-the-ai-can-do-its-tools)
- [AI requests and the queue (/jobs)](#ai-requests-and-the-queue-jobs)
- [What goes along with every request](#what-goes-along-with-every-request)
- [Settings](#settings)

## The brains you can choose

| Brain | Cost | Good for | Setup |
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
kept for calls and voice notes, with agy or another brain for everything else. Phone calls and voice notes always go
through Gemini, whichever AI answers your messages; if you don't want Google's free-tier terms there, use a paid key.

**About Claude Code.** Each request run by Claude Code gets only what Kurooto gives it, for that request: Kurooto's
tools (and your own GBrain's, if you use one), reading your notes, course files, Documents, Downloads and Screenshots,
writing in your notes, course-files and add-on skills folders, reading web pages, and harmless commands (`ls`, `cat`,
`grep`, `ls`, `pdftotext`...; none that can start another program through its options, so not `find`, `git`,
`latexmk`, `rg` or `sort`). Anything else is refused, and the answer says what was refused.

**Your own scripts.** To let your AI programs run a script of yours unattended (one that does one thing, such as
`make-figures`), put its full path in `agents.scripts` (Settings → Skills in other AI programs, or settings.json). It's
allowed by its path, and by its name when it's on your PATH. Shells and interpreters (`bash`, `python`, `node`...) are
never accepted there: they would run anything.
Nothing is saved in Claude Code's own settings, and your own Claude Code hooks, projects and history aren't used. The
`kurooto` command itself never runs from a request. Models: `brain.models.claude` (default `haiku` for quick
requests, `sonnet` for the rest).

**Ollama** runs models on your computer. Without a graphics card (or Apple Silicon) it's too slow to be your main
brain. With **Local AI models** on (see [your-computer.md](your-computer.md)), a small model on your computer answers
the quick "how hard is this?" question and makes the notes index; your main brain still does the real work. A small
model that can't use tools just answers without them.

**Retired:** Codex is no longer offered. If a setting named it, it's cleared, and the next request says to choose
another AI in Settings → AI. An AI set up with an earlier version as "FreeLLMAPI" keeps working and shows as "Another
OpenAI-compatible service".

**Checking it works:** `/brain` on Telegram lists the main and fallback brain and whether each is ready. The setup
page's **Test it** asks the AI for a reply and says what to do if it fails:

| Brain | When the test fails |
|---|---|
| Gemini key | Copy the key again from Google AI Studio (all of it; it starts with `AIza`). "Limit": wait a minute, or use a paid key. |
| agy, Claude Code | Open the sign-in window again, finish signing in, close it, test again. |
| Ollama | Make sure Ollama is running (open the Ollama app, or `ollama serve`), then test again. |
| Another service | Check the address (usually ends in `/v1`), the key and the model name. |

## Main and fallback

- `brain.main`: the AI that handles requests.
- `brain.fallback`: another one that takes over when the main one is at its limit, signed out, refused the request,
  failed or gave no answer. Empty means none. Set it in Dashboard → Settings → brain.

When the fallback answers, the answer says so in one line. Two more rules:

- **A free Gemini key stretches further:** when one Gemini model's free daily limit is used up, the next model of the
  same family answers (`gemini-flash-latest`, `gemini-flash-lite-latest`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`).
  Smaller or older models answer less well, so the answer says which one it was: "(Answered with ...: ...'s free limit
  for today was used up.)"
- **Last resort:** if your main brain is a Gemini key and nothing else can answer, the request goes to an agent
  program (agy or Claude Code) that is installed and has worked on this computer before. The other way round never
  happens: an agent program doesn't fall back to your free Gemini key, because its limit is small and kept for calls.

## How hard it thinks (effort)

Each request runs at low, medium or high effort. Higher effort uses a stronger or slower model and is allowed more
time.

- **Choose it yourself:** start a message with `low:`, `medium:` (or `med:`) or `high:`. Example: `high: derive the
  normal equations for least squares`.
- **Otherwise Kurooto picks.** Requests about notes, revision, summaries, explanations, derivations, proofs or exam prep
  always get high. Others are judged by the rules, your AI or a local model (`brain.classify`: `rules`, `main` or
  `ollama`; default `rules`), and medium is the default. Anything that changes, schedules or remembers something is
  never treated as a quick lookup.
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
- **`/usage`** lists AI requests per day over the last 7 days (`/usage 14` for two weeks, up to 60), per brain, how
  often a limit was hit, today's limits ("143 of 250 requests (57%); background work waits from 175. Resets at
  12:30.") and how many background requests wait for a reset. If agy is on this computer, it also counts agy's own runs
  from agy's logs (only counted; nothing in the logs is read out). Quick checks (how hard a request is, grading a quiz
  answer) and phone calls aren't counted. In a terminal: `kurooto usage [days]`. Needs Chat on.

| Setting (Settings → AI limits) | Default | Effect |
|---|---|---|
| `quota.on` | `true` | `false`: background work never waits (counting and the plain line stay) |
| `quota.background_pct` | `70` | the share of a known daily limit after which background work waits |
| `quota.limits` | `{}` | your own numbers, which win over learned ones, e.g. `{"gemini:gemini-flash-latest": 250, "agy": 900}` |
| `quota.local` | `quick` | `quick`: only the "how hard" question moves to the local model; `background`: background work moves there too instead of waiting (a small model writes weaker digests); `off`: nothing moves |

Only counts and times are kept (`quota.json` in Kurooto's state folder). Delete that file to forget what was learned.

## What the AI can do (its tools)

Your AI doesn't only answer: it can act, the same way in Chat, on a phone call and in background requests. Each feature
you turn on adds its own tools; a feature that's off has none. Examples: add a reminder, call you back later, hold
calls, add a deadline or mark one done, log study time, create a note or add to one, tick a `- [ ]` task, edit a note
when you ask, read your files and web pages, send you a file from your notes (over 50 MB as a Drive link, with Drive
upload on), say how your syncs are doing ("what's the sync status?"), and ask you a question when it needs your
answer.

**What it may read and write** (the same for Kurooto's own tools, agy and Claude Code):

- **Read:** your notes folder; your Documents, Downloads and Screenshots folders; Kurooto's copies of Classroom (course
  files) and mail (the digest's batches). Hidden files and folders (like `.git`) are left out, and a link leading
  anywhere else is refused.
- **Write:** your notes folder, the folder Classroom's course files go to, and (with Your add-ons on) your add-ons'
  `skills/`. Text files only (`.md`, `.txt`, `.tex`, `.bib`, `.csv`, `.json`, `.yaml`...). Documents and Downloads
  stay read-only.
- **Your own text:** it creates notes and adds to them. It changes existing text only with `edit_note`, when you asked,
  one exact passage at a time, and keeps the previous version first (Kurooto's state folder → `note-history/`, the
  last 20 per file).
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
- **What failures say:**

| Reply | Meaning |
|---|---|
| "... isn't signed in any more (or its key stopped working)" | Open the setup page (`kurooto open`) → AI → sign in again. |
| "... has hit its usage limit for now" | Wait, or set a fallback (`brain.fallback`). |
| "The AI stopped without an answer: it tried something unattended runs aren't allowed to do" | Rephrase it, or do that part yourself. |
| "The AI gave no answer this time" | Try rephrasing. |
| "No answer in time; the request was stopped" | It ran past `brain.timeout_min`. Ask with `low:` or split it up. |

When Kurooto stops (shutdown, update), running requests stop where they are and run again at the next start.

## What goes along with every request

Every request carries a short context: who you are, the time and time zone, where your notes are, and the rules (plain
text, never reword your notes, never claim what it didn't do). Two things of yours go along too:

- the **In brief** part of your profile (`about-me/profile.md`, the section under `## In brief`), built in the setup
  page's About you step; `/aboutme` shows it;
- a short version of your **how-to-help-me** note (what you told it with `/remember`).

Both are yours to edit: see [teaching-kurooto.md](teaching-kurooto.md). Answers come in the language you write in
(`you.language` = `follow`); set it to a language name, e.g. `German`, to always get that language.

## Settings

Dashboard → Settings → brain (and quota, jobs, you):

| Setting | Default | Effect |
|---|---|---|
| `brain.main` | empty | the AI that handles requests: `agy`, `gemini`, `claude`, `ollama` or `custom` |
| `brain.fallback` | empty | the AI that takes over when the main one can't answer |
| `brain.classify` | `rules` | who judges how hard a request is: `rules`, `main` or `ollama` |
| `brain.models` | `{}` | models per brain and effort, e.g. `{"custom": {"low": "...", "medium": "...", "high": "..."}}`, `{"claude": {"high": "opus"}}` |
| `brain.base_urls` | `{}` | override a preset's address |
| `brain.timeout_min.low` / `.medium` / `.high` | `10` / `15` / `30` | minutes a request may run |
| `brain.agy.io_mode` | `pipe` | how Kurooto talks to agy (leave it unless agy gives no output) |
| `jobs.stuck_min` | `10` | minutes without progress before a request is stopped (Settings → AI jobs) |
| `you.language` | `follow` | answer in the language you write in, or always in the one named |

**What leaves your computer:** what you ask, and the notes and files the AI reads for it, go to the AI service you
picked, under that service's terms. Ollama and an OpenAI-compatible server on your own computer keep it there. See
[privacy.md](privacy.md).
