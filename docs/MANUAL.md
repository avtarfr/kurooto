# Kurooto manual

Kurooto is a personal assistant that runs on your own computer. You talk to it on Telegram (and, if you like, on the
phone); it reminds you of things, keeps track of deadlines, asks how your day went, searches your notes, and can
call you. You choose which AI answers you, and every feature is off until you turn it on.

This manual covers everything, from installing to uninstalling. If you're in a hurry, read **Before you start**,
**Install**, and **The setup wizard**; the rest is there when you need it.

- [Before you start](#before-you-start)
- [Install](#install)
- [The setup wizard](#the-setup-wizard)
- [About you](#about-you)
- [Your AI brain](#your-ai-brain)
- [Features](#features)
  - [Telegram](#telegram) · [Questions and approvals](#questions-and-approvals) ·
    [Chat with your AI](#chat-with-your-ai) · [Reminders](#reminders) · [Check-ins](#check-ins) ·
    [Deadlines](#deadlines) · [Recurring quizzes](#recurring-quizzes) · [Not interested](#not-interested) ·
    [Exam mode](#exam-mode) · [Exam season](#exam-season) · [Subjects and timetable](#subjects-and-timetable) ·
    [Quiz](#quiz) · [Weekly summary](#weekly-summary)
  - [Files into notes](#files-into-notes) · [Skills](#skills) · [Quick notes and prompts](#quick-notes-and-prompts) ·
    [Notes brain](#notes-brain-gbrain) · [Local AI models](#local-ai-models) · [After-class notes](#after-class-notes) ·
    [Remember](#remember) · [Nightly look back](#nightly-look-back)
  - [Phone calls](#phone-calls) · [Morning alarm](#morning-alarm) ·
    [Reminders with the lid shut](#reminders-with-the-lid-shut) · [Voice notes](#voice-notes) ·
    [Stay awake on charger](#stay-awake-on-charger) · [Calendar](#calendar)
  - [Notes sync](#notes-sync) · [Sync everything](#sync-everything) · [Backups](#backups) ·
    [Profile sync](#profile-sync)
  - [Google](#google-classroom-gmail-drafts) ·
    [Google: setting up your own sign-in](#google-setting-up-your-own-sign-in-step-by-step) ·
    [Classroom → notes](#classroom--notes) · [Mail digest](#mail-digest) ·
    [Email reply drafts](#email-reply-drafts) · [Agent plan calendar](#agent-plan-calendar)
  - [Handwritten notes](#handwritten-notes) · [Books and PDFs](#books-and-pdfs) · [Study tracker](#study-tracker) ·
    [Research](#research) · [Terminals](#terminals) · [Kurooto Terminal](#kurooto-terminal) ·
    [Your add-ons](#your-add-ons) ·
    [Email reply drafts](#email-reply-drafts) · [Agent plan calendar](#agent-plan-calendar) ·
    [Several Google accounts](#several-google-accounts) · [Google Calendar](#google-calendar) ·
    [Mail digest by email](#mail-digest-by-email) · [Drive upload](#drive-upload)
  - [Handwritten notes](#handwritten-notes) · [Study tracker](#study-tracker) · [Research](#research) ·
    [Terminals](#terminals) · [Kurooto Terminal](#kurooto-terminal) · [Your add-ons](#your-add-ons) ·
    [From a terminal or a script](#from-a-terminal-or-a-script)
- [Your phone](#your-phone)
- [The dashboard](#the-dashboard)
- [Colours (Look)](#colours-look)
- [Taking your laptop with you (battery, pause, off)](#taking-your-laptop-with-you-battery-pause-off)
- [Starting at boot](#starting-at-boot)
- [Going offline and coming back](#going-offline-and-coming-back)
- [Kurooto keeps itself working](#kurooto-keeps-itself-working)
- [Updates and going back](#updates-and-going-back)
- [Moving to a new computer](#moving-to-a-new-computer)
- [Your computer and Kurooto (hardware profiles)](#your-computer-and-kurooto-hardware-profiles)
- [Your notes: layout and files](#your-notes-layout-and-files)
- [Where things are](#where-things-are)
- [Troubleshooting](#troubleshooting)
- [Getting help (diagnostics)](#getting-help-diagnostics)
- [Lost phone or keys that got out](#lost-phone-or-keys-that-got-out)
- [Uninstall](#uninstall)
- [FAQ](#faq)

---

## Before you start

**You need:**

- **A computer** with Windows 10 or 11, macOS 12 or newer, or Linux. It doesn't need to be powerful: laptops without a
  graphics card work fine (the AI runs in the cloud). Kurooto runs while the computer is on; if you want it reachable
  all day, leave the computer on and plugged in (see **Stay awake on charger**).
- **Free disk space:** about 1 GB for Kurooto itself, plus what the features you pick need (the wizard shows the total
  before installing anything). Kurooto always leaves 5 GB free.
- **Telegram** on your phone (free): this is how you talk to Kurooto.
- **A Google account** (free): for the recommended AI, a Gemini API key from Google AI Studio.

**Optional, depending on the features you pick:**

| Feature | Needs |
|---|---|
| Phone calls, Morning alarm | a free [Cloudflare](https://dash.cloudflare.com/sign-up) account and a Gemini key |
| Notes sync, Profile sync | a free [GitHub](https://github.com/signup) account |
| Backups | a folder on an external drive, or one your computer syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox) |
| Google Classroom, Gmail (drafts, the mail digest, reply drafts), the Agent plan calendar | your Google account, plus about 10 minutes in Google Cloud (free) |
| Revision packs as PDF | Tectonic, a small LaTeX engine (Kurooto installs it for you when you ask) |
| ChatGPT as the AI | a paid ChatGPT plan |
| Claude as the AI | a paid Claude plan |

Nothing costs money unless you choose a paid plan: a paid AI plan you already have, or a paid Gemini key.

## Install

Open a terminal, paste one line, press Enter. It installs Kurooto for your user only (no admin password), sets it to
start when you sign in, and opens the setup page in your browser. It takes a few minutes the first time.

**Windows:** press Start, type `PowerShell`, open it, and paste:

```powershell
irm https://avtarfr.github.io/kurooto/install.ps1 | iex
```

**macOS:** open Terminal (Spotlight → "Terminal") and paste:

```sh
curl -LsSf https://avtarfr.github.io/kurooto/install.sh | sh
```

**Linux:** open a terminal and paste the same line as macOS.

What it does, in order:

1. Checks there's at least 2 GB free.
2. Installs [uv](https://docs.astral.sh/uv/) (a small Python manager) and Python 3.12, just for your user.
3. Downloads Kurooto, **checks its signature and every file's checksum**, and refuses anything that doesn't match.
4. Turns on start-at-sign-in, starts Kurooto, and opens `http://127.0.0.1:8770/setup`.

Run the same line again any time to repair or update an installation.

**If something looks scary:**

- *Windows Defender / antivirus warns about a script:* the line downloads a PowerShell script from Kurooto's own
  release page. You can read it first: open the address in a browser.
- *macOS asks whether Terminal may control other apps, or access files:* only when a feature needs it (the Study
  tracker reads window titles). You can say no; that feature then says it can't.
- *The setup page didn't open:* go to `http://127.0.0.1:8770/setup` yourself, or run `kurooto open`.

## The setup wizard

The wizard is a page on your own computer (`127.0.0.1` means "this computer"; nothing outside can open it). It saves
as you go, so you can close it and come back. The list of steps (on the left on a wide screen, numbered dots on a
phone) opens any step; a step you passed but haven't finished (an AI that doesn't answer yet, Telegram not connected)
shows **!** instead of a tick. Words like *API key*, *token* or *repository* are underlined with dots: tap one to read
what it means.

1. **You:** what Kurooto calls you, your time zone (filled in from your browser) and the assistant's name.
2. **Your computer:** what Kurooto found (processor, memory, graphics card, free space) and what it recommends for
   it, marked ★. You can change any of it later. On a laptop, what to do on battery; and the pages' **Colours**
   (see [Colours](#colours-look)): this computer's own colours are marked ★ when Kurooto finds them.
3. **AI:** pick the AI that answers you (see [Your AI brain](#your-ai-brain)). ★ marks the recommendation: a Gemini
   API key. Make one at Google AI Studio, paste it and press **Save and test**. For the others, press **Install** if
   it isn't installed and follow the sign-in. Then press **Test it**: it asks the AI to reply, and tells you if it
   worked, or what to do if it didn't.
4. **About you** (★ recommended, optional): teach Kurooto what your other AI accounts already know about you. See
   [About you](#about-you) below.
5. **Features:** the **★ Starter** set is a good start (Telegram, chat, reminders, check-ins and deadlines; the
   notes brain is a 0.5 GB download, so it's yours to tick). **Everything** or **Pick myself** for more. Some features ask for a detail right in their
   card (a calendar link, a repository); phone calls, voice notes and the alarm use your Gemini key (they ask for one
   if you picked another AI).
6. **Telegram:** make your own bot in two minutes:
   1. Open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, answer its two questions (a display name,
      then a username ending in `bot`).
   2. BotFather replies with a token like `123456789:AAH…`. Paste it in the wizard and press **Check**.
   3. Tap the link the wizard shows, then **Start** in Telegram. Kurooto now knows that chat is yours and ignores
      everyone else.
7. **Done:** Kurooto installs what your features need (with progress), turns them on, and, if you chose Phone calls,
   shows a QR code to pair your phone. Send `/help` to your bot.

**Used Kurooto before?** The first page has **I've used Kurooto before**: give your private repository, a token for it
and your profile's passphrase, and your setup comes back (see [Moving to a new computer](#moving-to-a-new-computer)).
The steps after it are then filled in from your profile; they help with what can't move by itself (signing your AI in
again, installing what a feature needs).

## About you

Your other AI accounts (ChatGPT, Claude, Gemini, Copilot and the rest) already know a lot about you: your projects,
how you work, what you keep asking for help with. The setup page's **About you** step brings that into Kurooto once,
so it starts out knowing you.

1. Type which AI and account you're starting with (e.g. "ChatGPT personal") and copy a prompt: **Your main AI** (the
   fullest audit) for the account you use most, **Every other account** for all the rest.
2. Paste it into a **new chat** in that account. Turn on its memory or "search past chats" settings first if it has
   them: it can only report what it can see.
3. **Do this in as many AI accounts as you can,** including school, work and old accounts. Each knows different
   things; the more reports, the better the profile.
4. Each AI writes a long report and ends with a few questions. Answer them in that chat if you like and ask it to
   update the report; then copy its whole answer (or download it as a file) and add it on the page (paste, or upload
   several files at once).
5. Press **Build my profile.** Your AI merges the reports into one profile, `about-me/profile.md` in your notes.
6. **Read it and fix anything that's off,** right there: the profile opens in an editor under the button. **Save**
   keeps the previous version next to it (`profile-<date>.md`); **Revert** goes back to what's saved. **Preview In
   brief** shows exactly the part that goes along with every AI request: the section under `## In brief`. Without that
   heading nothing goes along (Kurooto warns you, but saves). The dashboard's **About you** tab has the same editor,
   and you can also edit the file in your notes.

**Building again never replaces your edits silently.** If you changed the profile since it was built, **Build my
profile again** asks first; say yes and the new one replaces yours, with yours kept next to it as `profile-<date>.md`
to copy things back from. If you edit it while a new one is being built, yours stays as it is and the new one goes next
to it as `profile-new-<date>.md`. `/aboutme` on Telegram shows the In-brief part and the link to the editor (it opens on
this computer).

The reports themselves stay in Kurooto's private data folder (not your notes, never synced). Remove anything you'd
rather not keep before adding a report. Come back any time with more accounts: open the setup page (`kurooto open`, then
"setup") and go to About you. To teach it smaller things as you go, see [Remember](#remember).

## Your AI brain

The "brain" is the AI that answers your messages and does tasks. You can change it any time (dashboard → Settings, or
the setup page), and set a **fallback** that takes over when the first one hits its limit.

| Brain | Cost | Good for | Setup |
|---|---|---|---|
| **Gemini API key** ★ | free tier, or paid | the simplest, and the way Google recommends for tools like this; also used for calls and voice notes. Free tier: Google may use what you send to improve its products and human reviewers may read it; 18+; a paid key is required in the EEA, UK and Switzerland | [Google AI Studio](https://aistudio.google.com/apikey) → Create API key → paste |
| **Antigravity (agy)** | free with a Google account | Google's agent program on your computer; can read your notes. Some risk to the Google account (see the note below) | Install → a window opens → sign in with Google |
| **ChatGPT / Codex** | needs a paid ChatGPT plan | if you already pay for ChatGPT | Install → sign in with your ChatGPT account |
| **Claude Code** (Advanced) | needs a paid Claude plan | if you already pay for Claude | Install → sign in with your Claude account |
| **Ollama on this computer** | free | private and offline, but much weaker, and needs a good graphics card; best as a helper next to another AI | Install Ollama → Test |
| **Another OpenAI-compatible service** | depends | any service that speaks OpenAI's API | its address, key and model names |

**agy:** Kurooto runs Google's official agy program on your computer, signed in as you, and never touches its sign-in
token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to your Google
account; for tools like Kurooto, Google recommends a Gemini API key.

If you set Kurooto up before 0.2.0, it keeps the AI you chose. An AI set up as FreeLLMAPI with an earlier version keeps
working; it now shows as "Another OpenAI-compatible service". What each service's terms mean for your data is in
[PRIVACY.md](PRIVACY.md).

**Limits:** free tiers have daily limits. When the brain hits one, Kurooto tells you once and uses your fallback if
you set one. `/usage` (with Chat on) lists AI requests per day over the last 7 days (`/usage 14` for two weeks), per
brain, and how often a limit was hit, from Kurooto's own request log; quick checks (how hard a request is, grading a
quiz answer) and phone calls aren't counted. If agy is on this computer, `/usage` also counts **agy itself** from its
own logs: every agy run, including the ones you type yourself, its model requests and the days it hit its limit (only
counted; nothing in the logs is read out). `kurooto usage [days]` shows the same in a terminal. **How hard it thinks:** Kurooto picks low, medium or high effort per
request; start a message with `high:` or `low:` to choose.

### Free limits: the reserve

Free AI has a daily limit, and Google doesn't say how much of it is left. Kurooto counts each request itself and keeps
the end of the day's limit for what you're waiting on: calls, voice notes, the morning plan and your own requests.

- **It learns the limits.** The first time Google answers "limit reached" (a 429 error), Kurooto keeps the number
  Google names or, when it names none, how many requests the day had. It learns when the limit comes back the same
  way: from Google's own hint, else Google's day, which ends at midnight Pacific time (`/usage` shows it in your time).
  Each model of your Gemini key has its own limit and agy has one; agy's count comes from agy's own logs, so the runs
  you type yourself count too. Until a limit has been reached once, it isn't known and nothing waits.
- **Background work waits past 70%.** Once a day's count passes 70% of a known limit, background work waits: the
  Classroom digest, the nightly look back, skill changes it proposes, research digests, and book and handwritten pages
  read by Gemini. The "how hard is this" question moves to the model on this computer (Local AI models), or to the
  rules. Nothing is dropped: waiting work stays in the queue and runs after the reset, or as soon as that limit
  answers again. Your own requests never wait; a used-up limit is tried last, after your fallback brain.
- **One plain line instead of an error:** "Google's free limit for today is used up, resets at 12:30; your calls and
  alarm still work." Calls use another Gemini model, which has its own limit.
- **`/usage`** (and `kurooto usage`) ends with today's limits, for example "Gemini key, gemini-flash-latest: 143 of 250
  requests (57%, Google's number); background work waits from 175. Resets at 12:30.", and how many background
  requests wait for a reset.

**Settings** (Settings → `quota`):
- `on`: `true` (default); `false`: background work never waits (the counting and the plain line stay).
- `background_pct`: `70`, the share of a known limit after which background work waits.
- `limits`: your own numbers, which win over learned ones: `{"gemini:gemini-flash-latest": 250, "agy": 900}`
  (`gemini:<model>` for your Gemini key's models, `agy`, `<brain>:<model>` for another service).
- `local`: `quick` (default): only the "how hard is this" question moves to the model on this computer; `background`:
  background work moves there too instead of waiting (a small model writes weaker digests); `off`: nothing moves.

*Leaves:* nothing; only counts and times are kept, in Kurooto's state folder (`quota.json`).

**Undo:** `quota.on` = `false`: background work runs whatever the count, as before 0.5.0 (work already waiting runs at
once). To forget what was learned, delete `quota.json` in Kurooto's state folder; it's learned again at the next
"limit reached".

### What the AI can do (its tools)

Your AI doesn't only answer: it can act, the same way on a phone call, in Chat, and in background requests. It adds a
reminder, calls you back later, holds calls, adds a deadline, logs study time, creates a note or adds to one, ticks a
`- [ ]` task, edits a note when you ask, reads your files and web pages, says how your syncs are doing ("what's the
sync status?"), and asks you a question when it needs your answer. Each feature you turn on adds its own tools; a
feature that's off has none. Nothing is sent to anyone but you.

**What it may read and write** (the same for Kurooto's own tools and for agy):
- **Read:** your notes folder, your Documents, Downloads and Screenshots folders (each OS's real ones), and
  Kurooto's copies of Classroom (course files and the batches it files) and mail (the digest's batches). Hidden files
  and folders (like `.git`) are left out, and a link that leads anywhere else is refused.
- **Write:** your notes folder (all of it, so it can also make a `.tex` for a revision pack), the folder Classroom's
  course files go to, and, with **Your add-ons** on, your add-ons' `skills/` (never the skills Kurooto ships, which
  updates replace). Text files only (`.md`, `.txt`, `.tex`, `.bib`, `.csv`, `.json`, `.yaml`, ...). Documents and
  Downloads stay read-only.
- **Your text:** it creates notes and files and adds to them; it changes existing text only with `edit_note`, when you
  asked, one exact passage at a time, and keeps the previous version first (Kurooto's state folder →
  `note-history/`, the last 20 per file). With Notes sync on, your repository's history has every version too.
- **The web:** a public page as plain text (GET only, at most a few MB); never this computer or your local network.

- **API brains** (a Gemini key, Ollama, another OpenAI-compatible service) call the tools directly. A model that can't
  use tools (some small Ollama models) just answers without them.
- **Agent programs** (agy, Codex, Claude Code) get them through `kurooto mcp`, a small MCP server that passes each call
  to the running Kurooto. Codex and Claude Code get it for each request only; nothing is saved in their own settings.
  agy gets it once, when you test agy on the setup page (the page says what it allows), or, if you set agy up
  before, when you tap Approve on the question Kurooto asks (Deny: it asks again in 30 days at the earliest; it also
  asks before adding more later, e.g. when you turn on add-ons). Kurooto runs `agy mcp add kurooto ...` and adds to
  agy's allow-list (`~/.gemini/antigravity-cli/settings.json`, backed up first to Kurooto's state folder →
  `backups/`; your own rules stay): `mcp(kurooto/*)`; `read_file(...)` and `write_file(...)` for the folders above;
  `read_url(*)`; and harmless commands: cat, cd, date, echo, file, find, git, grep, head, jq, latexmk (to build PDFs),
  ls, mkdir, pdftotext, pwd, rg, sort, stat, tail, tree, uniq, wc, which. Never `kurooto` itself (its off, uninstall
  and restore must not run unattended; everything useful is a tool) and not `sed` (agy's rules can't stop `sed -i`
  from writing). Reading outside the notes folder needs agy's non-workspace access, so Kurooto turns that on
  (`allowNonWorkspaceAccess`, `nonWorkspaceFileAccess`) unless you've set it yourself; agy's other settings, such as
  its tool execution policy, are left as they are. agy doesn't get GBrain directly (Kurooto owns its index); it
  searches your notes through Kurooto's `search_notes`.
- **Your own agent sessions** can use them too: add `kurooto mcp` as an MCP server in any MCP client. It works while
  Kurooto is running.
- The AI is told to say plainly when it couldn't do something, never to claim it did.

*Turn it off:* the tools come from the features you have on; turn a feature off and its tools go. To take them away
from agy: `agy mcp remove kurooto`, and delete Kurooto's lines from agy's settings (or put back the copy in Kurooto's
state folder → `backups/`).
*Leaves your computer:* nothing new. What a tool returns (a note's text, your deadlines) goes to the AI you picked,
like the notes it reads.

## Features

Every feature is off until you turn it on (wizard, or dashboard → **Features**). Turning one off stops it at once;
its data stays unless you delete it. Each section says what leaves your computer; [PRIVACY.md](PRIVACY.md) has the
full list.

Plain English works for many things ("remind me at 9 to call mum", "move tonight's check-in to 21:30", "skip Friday's
check-in", "what's due?", "wake me at 6:45", "quiz me by call", "sync everything"). `/help` lists the commands of the
features you have on.

### Telegram
Your own bot, which only answers you. Commands: `/status` (what's going on: whether calls are held, focus, what's
coming up, open questions, today's check-ins, what's due in the next 3 days, the alarm, your last AI requests and
the features that are on), `/hold 2h` or `/hold 18:00` (no calls until then), `/calls` (allow calls again), `/focus 2h` (do-not-disturb: messages wait until it ends).

**The "/" menu.** Typing `/` in the chat lists the commands of the features you have on, and your skills (a skill
with a dash in its name shows with `_`: `/term_setup` runs term-setup). Kurooto updates the menu within a minute of a
feature going on or off, and looks again every quarter of an hour for new skills. *Undo:* Settings → telegram →
`menu` off: Kurooto takes the menu away and leaves the bot's menu alone from then on.
*Leaves your computer:* your messages travel through Telegram to your bot.

### Questions and approvals
This one is always there; it isn't a feature you turn on. Sometimes Kurooto needs something only you know ("which
chapter is Friday's quiz on?") or your OK before it does something ("send this reply to Sam?"). Those come as a
**question** (its answers as buttons, plus **Later**) or an **approval** (**Approve** / **Deny**, or the asker's own
choices such as Send / Edit / Discard). They can come from any feature, from an AI request (your answer starts its
follow-up) and from your own scripts (see [From a terminal or a script](#from-a-terminal-or-a-script)).

- **Answer anywhere:** tap a button, or reply to the message with your own words (photos and files in the reply are
  kept with the answer); in the phone app (see [Phone calls](#phone-calls)); or on a call (open questions come up at
  the start of every call). The first answer wins; answering again somewhere else just tells you what was already
  answered.
- **Later** keeps it open for your next call. **Nothing new** (or "nothing", "skip") is a real answer: there's
  nothing to add.
- For an approval with Approve / Deny, a reply of "yes", "ok", "no" or "cancel" counts too. Anything unclear is asked
  again; nothing is ever approved for you.
- Questions you don't answer expire after two days (or when their asker stops waiting); then nothing happens.
- `/q` lists the open ones with their buttons; `/status` says how many are waiting.

*Settings:* `ask.expire_hours` (default 48: how long an unanswered question stays open), `ask.keep_days` (default
30: how long answered ones are kept).
*Leaves your computer:* the question goes wherever Kurooto reaches you (Telegram, the phone app, the desktop); open
questions are part of the brief your call line keeps for calls while the computer is off.

### Chat with your AI
Anything that isn't a command or an instant request goes to your AI; the answer comes back as a reply. Long answers
arrive as a file. `/brain` shows which AI answers and whether it works; `/jobs` the last few requests; `/usage` how
many AI requests ran each day and the limits hit.
*Leaves:* what you ask, and notes it reads, go to the AI you picked.

### Reminders
"remind me at 9 to call mum", "remind me in 20 minutes to take the pasta off", `/remind tomorrow 7am gym`,
`/reminders`. A reminder due while the computer slept arrives when it wakes, marked late (with
[Reminders with the lid shut](#reminders-with-the-lid-shut) on, your Android phone gets it at its time instead).
Buttons: +10 min, +1 h.

### Check-ins
At times you choose, Kurooto asks how the day is going: the **evening** check-in (default 22:00, the day in review),
an optional **night** one (goodnight, near bedtime) and an optional **midday** one. Reply to the message and it goes
into your journal (`journal/YYYY-MM-DD.md` in your notes folder).

- **Turn on the night or midday one:** Settings → Check-ins → `times`, and give it a time, e.g. `"night": "23:15"`.
  Both are off until you do.
- **Change one in plain English:** "move tonight's check-in to 21:30", "push the check-in by 30 min", "skip the night
  check-in". Other days work too: "skip Friday's check-in", "move tomorrow's check-in to 9". A day Kurooto can't pin
  down ("yesterday", "next week", a date) goes to the AI instead of guessing.
- **The check-in day runs from 05:00 to 05:00** (`checkins.day_starts`). A night check-in at 00:30, or one you push
  past midnight ("push the night check-in by 30 min" at 23:50), is still that evening's: it rings at 00:20 and its
  journal and study logs go to the evening's day. Still up at 1 am, "move the evening check-in to 21:00" means the
  coming evening, and "skip the night check-in" skips the coming night's once tonight's is over. Set it to `00:00`
  for calendar days.
- `/checkins` lists today's, with **+30 min** and **Skip** buttons (and **Tomorrow morning** for the night one);
  `/checkin evening 21:30` (today only), `/checkin night skip`, `/checkin night morning` (to your wake-up call).

**By call** (with Phone calls on; Settings → `checkins.by_call`):
- **Evening debrief** (5 to 8 minutes): how the day went; what each of today's classes covered (and the after-class
  questions you kept for this call); what slipped from today's plan; open questions; the study time it counted, and
  study away from the computer; a short quiz if an exam or quiz is in the next two weeks.
- **Night check-in** (3 to 5 minutes, if you turned it on): anything more for the journal, study logs still due,
  tomorrow's top priority and when to wake you (it sets the alarm), goodnight. With the night check-in off, the
  evening one asks tomorrow's priority and the wake-up time.
- **Too tired?** Say so on the call, or tap **Tomorrow morning** (on the missed-call message; for the night check-in
  also on the ringing call's message and in `/checkins`): the rest moves to your wake-up call, which starts with it
  before planning the day. With no alarm set, it's asked by message in the morning.
- **Afterwards**, with Chat on, the AI writes your journal entry from what you said (your words, not its own) and a
  study log for each class you talked about. Without Chat, what you said goes into the journal as it is.
- **"Call me back in an hour"** on a check-in call moves that check-in (the same call, with the same steps), never a
  plain reminder call. "Later" on the ringing phone does the same, half an hour on (`calls.later_min`).
- **A call you don't answer** (after its repeats) **or decline** becomes a message with **Call me now / Tomorrow
  morning / Skip**; reply to it to answer by text. A check-in never stays "calling".
- A check-in call never interrupts a class, a calendar event, `/hold`, focus, the night or another call: it waits until
  that ends, or comes as a message if that would be too late. The night doesn't hold the night check-in.
- **Gone to bed:** with the alarm set, the night check-in doesn't ring once it's past your bedtime (`alarm.bedtime`),
  or within 3 hours of you setting the alarm yourself. It moves to your wake-up call, and a message says so with
  **Call me now** and **Skip**. A night check-in you moved after setting the alarm still rings.
  `checkins.asleep_defers` (default on) turns this off.

*Settings:* `checkins.times` (`evening`, `night`, `midday`; empty = off), `checkins.questions` (what each one asks),
`checkins.by_call`, `checkins.journal`, `checkins.ai_notes` (default on: with Chat on, the AI writes the journal and
study logs after a check-in call), `checkins.day_starts` (default `05:00`), `checkins.asleep_defers` (default on).
*Undo:* `checkins.day_starts` = `00:00` (calendar days, as before 0.3.0); `checkins.asleep_defers` off (the night
check-in always rings).
*Leaves:* nothing; with check-ins by call and Chat on, what you said on the call goes to the AI to write your journal
and study logs.

### Deadlines
One list of what's due, from:
- what you add: `/due fri 17:00 essay draft`, `/due 2026-11-02 lab report`, or "add a deadline: essay draft due
  friday 5pm";
- dated tasks in your notes, written like `- [ ] Essay draft (2026-11-02 17:00)` (a time like `5:00 PM` works too);
- Google Classroom coursework (with Google on);
- calendar events that look like deadlines or exams: "due", "deadline", "submit", "assignment", "homework",
  "report", "quiz", "exam", "midterm", "test", "viva"... (with Calendar on);
- recurring quizzes and tests (below);
- the key dates in your term note ([Subjects and timetable](#subjects-and-timetable): `/term note`): its quizzes and
  exams, and deadlines that name one of your subjects. They're read again whenever you change the note; a row you
  take out of the note leaves the list.

The same thing from two places (say Classroom, your calendar and a task in your notes) is kept once; a known time
beats "end of the day". Topics on your not-interested list are left out.

**The chase**, for things you hand in:
- a day before: a message with **Done / Not mine / Snooze 3 h**;
- six hours before: with Phone calls on, **a call** ("is it done, or how will you finish it?"). It waits out
  classes, `/hold`, focus and the night; when that would leave less than half an hour, or Phone calls is off, you
  get an urgent message instead. A missed call also becomes that message;
- after the due time: **Overdue?** with **Done / New date / Drop**. New date asks you for the date (reply, or answer
  on the phone or on your next call) and starts the chase over.

**Done** ticks the `- [ ]` box in your notes when the deadline came from one (only that box changes). Quizzes and
exams aren't "done": you get a reminder a day before or, with Quiz on, a practice offer the evening before.

`/deadlines` shows two weeks; "what's due this week?" works too. On calls, the brief has what's due in the next
72 hours (`deadlines.plan_h`), and you can say "the lab report is done", "it got moved to Friday", "add a deadline".

**How far ahead "due soon" looks** (`deadlines.plan_h`, 72 hours): what's due in that window goes into the wake-up
call's plan, the morning page, the call brief, `/status` ("Due in the next 3 days") and "what's due soon?". Set it to
`168` to plan a week ahead, or `36` for just tomorrow. `/deadlines` and the reminders above don't change.

*Settings* (`deadlines.*`): `plan_h` (72), `ping_h` (24), `urgent_h` (6), `call` (on: the six-hour nudge is a call
when Phone calls is on), `overdue_check` (on), `tick_notes` (on), `from_calendar` (on), `recurring` (on),
`horizon_days` (30: how far ahead recurring quizzes become dated items), `exam_mode_days` (14; 0 turns exam mode off),
`scan_notes` (on), `from_term_note` (on: the term note's key dates, when you have one).
*Turn off:* the whole thing in Features; the call alone with `deadlines.call` off; the overdue question with
`deadlines.overdue_check` off.
*Undo:* set `deadlines.plan_h` back to `72` (or reset it in Settings).

### Recurring quizzes
Part of Deadlines, for quizzes and tests that repeat ("Linear Algebra quiz every Thursday 10:00", "Statistics test
every other Friday"). Say it ("linear algebra has a quiz every thursday"), or `/recurring add la quiz every 2 weeks
thu 10:00`. They live in your notes as a table at `kurooto/recurring.md`, which you can edit like any note:

| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| linear-algebra | Quiz | 1 | Thu | 10:00 | | |

"Every" is in weeks (or "weekly", "every other week"); "Next" is any date it happens on, needed for every two weeks;
"Until" is optional. The header row can name the columns your own way ("Course" instead of "Subject"): the row above
the `| :--- |` line, or one made only of column names, is never read as a quiz. Each row becomes dated items on the deadline list, so the reminders, exam mode and quiz offers
follow. When the day or time is missing, Kurooto uses the subject's class from your timetable, and asks you when it
can't tell (which day, or which week for every two weeks); for a row you wrote yourself, your answer is kept by
Kurooto and your note is left as it is. Holidays from your subjects settings are skipped.

`/recurring` lists them; `/recurring remove la quiz` removes one (just that row). *Turn off:* `deadlines.recurring`.

### Not interested
Topics you don't care about (a club, a kind of event, a course you dropped): `/ignore drama club`, or say "I don't
care about the drama club". `/ignored` lists them, `/unignore drama club` takes one off. The list is a note,
`about-me/not-interested.md`, one per line (`- drama club`, or `- drama club — not this term`); edit it freely.
Matching deadlines are left out of the list and the chase, and the mail and Classroom digests only count matching
items instead of making tasks from them. Matching is on whole words, ignoring case.

### Exam mode
On by itself two weeks before a quiz or exam (from the deadline list), for that subject; off after it. You're told
once when it starts. While it's on:
- `/exam` (or "when's my next exam?") shows it, with how many questions are due;
- calls start knowing it;
- quizzes come more often: longer sessions (`quiz.exam_per_session`, 6), items you know still come back before the
  exam, and, if you like, a short practice check-in every day (set `quiz.exam_daily` to a time, e.g. 18:00).

*Turn off:* `deadlines.exam_mode_days` = 0.

### Exam season
One card for the whole exam period, on top of exam mode. Off until you turn it on (Features → Exam season; it needs
Deadlines). **It does nothing without exam dates:** the exam periods in Subjects (`/term exams 2026-12-07 to
2026-12-18`, or your term note) and the exams on your deadline list ("Linear Algebra final exam", "Topology midterm",
a viva). Quizzes and tests count only inside an exam period, unless you set `exam_season.quizzes` on. A season runs
from the day before its first exam to the end of its last; exam days up to three days apart are one season. You're
told once when one starts, with what it will do.

Each part has its own switch, on the card in the dashboard's Features tab, with `/examseason` on Telegram (tap a part
to switch it) or in Settings → Exam season:
- **Hold non-critical updates** (`hold_updates`): updates wait until the exams are over. A release marked critical
  still installs, and so does `kurooto update --now` or an Update tap.
- **Check the alarm every night** (`alarm_check`, at `night_at`, 21:30): every night of the period, the alarm check
  from [Kurooto keeps itself working](#kurooto-keeps-itself-working) runs (with the Morning alarm on), and your call
  line's check when a leave-by call is set for tomorrow. It tries the safe fix first; if tomorrow's alarm might still
  not ring: "... Set your phone's own alarm too." A morning exam with no alarm before it gets one line too.
- **Ask the evening before** (`eve`, from `eve_at`, 18:00): once per exam, "Tomorrow: Linear Algebra final exam at
  09:00. Where is it, which seat? Calculator? ID card?". Reply in one line ("Hall B, seat 34, calculator, ID card"),
  tap Later to answer on your next call, or answer on the phone app. When the exam's time isn't known it asks that
  too ("starts 14:00").
- **Alarm to leave on time** (`leave_alarm`): on the exam day, `leave_min` (45) minutes before it starts, or the time
  you said ("leave 8:10"). With Phone calls on it's a call that rings like the wake-up alarm (also on silent, also
  while this computer sleeps), saying where to go and what you said; **Later** rings again in 5 minutes, twice.
  Without Phone calls it's an urgent message. "no alarm" in your answer turns it off for that exam.
- **Two-minute debrief after each exam** (`debrief`): half an hour after it ends (`exam_min`, 180 minutes, after the
  start; the evening, when its time isn't known), "How did it go?". Your answer goes, as you said it, into the
  subject's course note (`<subject>/course.md`) under **Exam debriefs**, or into that day's daily note when the exam
  has no subject. "Nothing new" skips it.
- **No calls during an exam** (`no_calls`): from 15 minutes before an exam until `exam_min` after its start.

**The quiz call before an exam stays off unless you pick it for that exam:** the card (and `/examseason`, with Quiz
and Phone calls on) has a switch per exam. Picked, Kurooto calls you for a quiz at `quiz_call_at` (19:00) the evening
before, instead of the practice offer, and exam mode's daily practice (`quiz.exam_daily`) may call for it with
`quiz.by_call` on. For the season's other exams, the practice stays a message.

"exam season?" or `/examseason` shows the season, its exams with what you told Kurooto, and the parts that are on.
On calls on the exam day and the day before, the brief has the exam and what you said about it.

*Settings* (`exam_season.*`): `hold_updates`, `alarm_check`, `eve`, `leave_alarm`, `debrief`, `no_calls` (all on),
`night_at` (21:30), `eve_at` (18:00), `leave_min` (45), `exam_min` (180), `quizzes` (off), `quiz_call_at` (19:00).
*Undo:* turn Exam season off in Features: its timers, leave-by alarms (also on your call line) and update hold go at
once, and the call-blocking during exams stops. Or switch off just the part you don't want. Debriefs already written
stay in your notes; answers are kept in `exam_season.json` in the state folder for 30 days after the exam.
*Leaves:* with Phone calls on, the leave-by alarm's time, the exam and what you said about it go to your call line
(like any call). Nothing else.

### Subjects and timetable
Your courses with short names (`/subject add Linear Algebra (la, linalg)`) and your timetable
(`/class mon 09:00-09:55 la`). Kurooto never calls you during a class (or in the 5 minutes before it,
`subjects.margin_min`). `/classes today`, `/skip la` or "skipping LA today" (not going), `/attend la` (undo). "not
going to LA on Friday" and "skipping stats tomorrow" mark that day. Other features use the subjects: after-class
notes, the quiz, the study tracker.

**Term dates:** `/term ends 2026-12-04` (the last day of classes) and `/term exams 2026-12-07 to 2026-12-18` (an exam
period; add as many as you need). On those days, after the term ends and on holidays there are no classes: no
after-class questions, and the timetable doesn't hold calls. `/term` shows them, `/term clear` removes them.
Holidays are a list of dates in Settings (`subjects.holidays`, e.g. `["2026-12-25"]`).

**The term note: your timetable and key dates, read live.** Instead of typing classes and dates in, keep them in a
note and point Kurooto at it: `/term note terms/2026-autumn` (`/term-setup` writes such a note). Kurooto reads it
again whenever it changes: its classes, subjects (a code next to a subject becomes a short name for it), holidays,
exam periods and last day of classes count from then on, together with the ones you set with `/class` and `/term`
(yours win where both say something), and its quizzes and exams reach [Deadlines](#deadlines). `/term` shows what it
read and the next key dates. The note needs two tables:

```
## Weekly timetable
| Day | Time | Subject | Code |
| :--- | :--- | :--- | :--- |
| Mon | 09:00-09:55 | [[linear-algebra/course|Linear Algebra]] | MA101 |
|     | 11:00-11:55 | Statistics | |
| Tue, Thu | 2:00-2:50 pm | Topology | |

## Key dates
| Date | What | Source |
| :--- | :--- | :--- |
| 2026-10-02 | Holiday | calendar |
| 2026-10-19 – 2026-10-23 | Mid-term break | calendar |
| 2026-11-12 | Linear Algebra midterm (10:00-11:00) | me |
| 2026-12-04 | Last day of classes | calendar |
| 2026-12-07 – 2026-12-18 | End-term exams | calendar |
```

- **Weekly timetable** (a heading with "timetable" in it): columns by name (Day; Time, or Start and End; Subject,
  Course or Class; an optional Code), else day, time, subject in that order. An empty Day continues the day above;
  "Tue, Thu" is both. The subject is plain text or a link to its notes. Lunch and break rows are skipped.
- **Key dates** (a heading with "dates" in it): dates as YYYY-MM-DD, a range as "A – B" or "A to B", a time after the
  date or in the text. Holidays, breaks and vacations have no classes; "last day of classes" (or instruction,
  teaching) ends the term; an exam period (a range, or "exams", "examinations") has no classes; a quiz, test, exam or
  midterm becomes a dated exam; a deadline ("due", "submission", "assignment") counts when it names one of your
  subjects. Anything else is just shown by `/term`. A **Kind** column (holiday, exams, last day, exam, due) says it
  outright.
- **Which note:** a path in your notes (`terms/2026-autumn`, with or without `.md` or `[[ ]]`), a pattern
  (`maps/semester-*`: the current term's note among them, else the newest name, so semester-10 comes after
  semester-9), or `auto` (`terms/*`, or `maps/semester-*` in the zettelkasten notes layout).

*Settings:* `subjects.holidays`, `subjects.exam_periods`, `subjects.term_ends`, `subjects.no_calls_in_class`,
`subjects.margin_min`, `subjects.term_note` (empty: no term note).
*Undo:* `/term note off` (or empty `subjects.term_note`): the note's classes and dates stop counting, and its dated
items leave the deadline list. Your note itself is never changed.

### Quiz
Practice questions from your notes, spaced out so you see each again just before you'd forget it. Put a note named
like `exam-prep.md` (or with "quiz" in its name) with a `## Must know` list in a subject's folder (also: "Typical
questions", "Definitions", "Theorems", "Formulas", "Key results"). Classroom → notes keeps such a note for each course.
- `/quiz` or `/quiz la`: a session of a few questions (`quiz.per_session`, 3). Reply with your answer: with Chat on,
  the AI gives the key idea and a grade; otherwise grade yourself with the buttons. The next question follows.
  With Phone calls on, `/quiz` asks **Here or by call?**; `/quiz la call` calls you straight away (it waits out
  classes and other no-call times). "quiz me on topology", "quiz me by call" and "call me for a quiz" work too.
  With `quiz.by_call` on as well, `/quiz` and "quiz me" call you without asking; add "here" (`/quiz la here`,
  "quiz me here") for the questions on Telegram. Without Phone calls they stay on Telegram.
- **The evening before a quiz or exam** (from 19:00, `quiz.offer_at`): "Linear Algebra quiz is tomorrow at 10:00.
  Practise?" with **Quiz me now / Call me for a quiz / Not tonight**. If you haven't any material for it yet, it
  says where to put some.
- **Quiz check-ins**: `/quiz at 21:00 la`, or "quiz me at 9 tonight": the first question arrives then (a call
  instead with `quiz.by_call` on, or "quiz me by call at 9"). In exam mode there's one every day (above).
- On a call: "quiz me" runs a spoken quiz (it picks the exam subject unless you name one).
- `/quizstatus`: items and what's due per subject, and exam mode.

*Settings* (`quiz.*`): `per_session` (3), `exam_per_session` (6), `offer_at` (19:00; empty turns the evening offer
off), `exam_daily` (off; a time like 18:00 turns on a daily exam-mode practice), `by_call` (off: `/quiz`, "quiz me"
and quiz check-ins ring you when it's on), `call_min` (10).
*Undo:* `quiz.by_call` off brings back **Here or by call?**.
*Leaves:* with Chat on, the question and your answer go to the AI to grade it.

### Weekly summary
Every Sunday evening (`weekly.when`, Sunday 19:00): the week in numbers (requests, reminders, check-ins, deadlines,
quiz, study hours, journal days), and what isn't working that could wait until then
([Kurooto keeps itself working](#kurooto-keeps-itself-working)). `/week` any time.

**Sunday review call** (optional, with Phone calls on; Settings → `weekly.call`): after the summary, a call of about
15 minutes: the week in numbers and study hours per subject, what went well and what didn't, anything Kurooto should
do differently, and next week's deadlines and your priorities. Afterwards it becomes a weekly review in your journal
(written by the AI with Chat on, your own words without). If the computer was off all Sunday evening, you get only the
summary.

### Files into notes
Send a photo or PDF to your bot: it's saved in your notes folder's `inbox/` (or your files folder's, when you set one:
[Your notes: layout and files](#your-notes-layout-and-files)). With Chat on, the AI files it properly
(a note that describes and links it, in the right place). The caption tells it what it's for. With Skills on, a link
sent on its own is filed the same way (the `/add-to-notes` skill).

### Skills
Ready-made instructions for your AI, one command each. Type `/<skill>` and what it's about; the answer comes back as a
reply, and you can **reply to that answer** to carry on (answer its questions, ask for a change). Files you send with
the command (as the caption) go along. `/skills` lists them all; `/skills journal` shows one.

| Skill | What it does |
|---|---|
| `/journal <your day>` | Saves your words, as you wrote them, in today's daily note (`journal/YYYY-MM-DD.md`), and links the notes you mention, ticks tasks you finished, files new ideas in `inbox/`. |
| `/study-log <classes and notes>` | One lecture note per class (`<subject>/YYYY-MM-DD-<topic>.md`) from your slides and notes, linked from the subject's course page and today's daily note. |
| `/add-to-notes <link or files>` | Files anything (PDF, slides, photo of notes, a link) where it belongs, as a source note with links. A link sent on its own is filed this way too. |
| `/assignment <which one>` | Worked solutions in your course's notation, a confidence for each question, saved as a note. Check them and follow your course's rules on AI help. |
| `/connect-notes [topic]` | Finds real connections between notes and adds them as links, each with its reason. |
| `/term-setup <subjects, plans>` | Sets up a term from what you say and your academic calendar: key dates, course pages, a week-by-week plan; it asks what it can't find (reply to answer). |
| `/goodnight <wake-up time>` | Sets the alarm (with Morning alarm on) and notes anything for tomorrow. |
| `/morning [answers]` | Today's plan, time-blocked, with your top 3. |
| `/morning-prep` | Drafts today's plan before you wake (other features run it for you). |
| `/pack <subject> [what for]` | A revision pack as a PDF (see below). |

`/skills` also lists the skills other features run for you (`/classroom-digest`, `/mail-digest`, and
`/revision-pack`, the same as `/pack`).

**Your own skills.** `/newskill <what it should do>`: the AI writes a skill and sends it to you in full; **Save** puts
it in your notes (`kurooto/skills/<name>/SKILL.md`), **Discard** throws it away. Nothing is saved without your tap.
To change a skill that comes with Kurooto, `/skills copy journal` makes your own copy in that folder; edit it there
(your copy replaces Kurooto's for you; delete your copy to go back). A prompt in your prompt library with
`skill: true` in its header is a skill too.

**In agy and other agent programs.** `kurooto export-skills on` puts every skill you can run here (Kurooto's, your
add-ons', your own, and prompts with `skill: true`) into agy's skills folder, so `/journal my day` typed in agy runs
the same instructions; each copy says where your notes folder is and carries the same rules. `--to agy,agents` also
puts them in `~/.agents/skills` (Codex as `$journal`, GitHub Copilot CLI as `/journal`); Claude Code's folder is never
used. Kurooto only ever changes or removes the copies it made (they carry a `.kurooto-skill` marker): if you have a
skill of your own with the same name, yours stays and Kurooto's goes in as `kurooto-<name>`; a copy you edit by hand is
yours from then on. They're kept up to date when Kurooto starts (so after every update) and every hour, and ones whose
skill is gone are removed. `kurooto export-skills status` lists them; `agents.prefix` (e.g. `k-`) puts a prefix on
all of them. *Turn it off:* `kurooto export-skills off` removes every copy Kurooto made (`kurooto uninstall` does
too); your own skills stay.

**On a schedule.** `/every monday 9:00 /journal plan my week`, `/every weekdays 7:30 /morning-prep`,
`/every daily 21:00 how did today go?` (a request for the AI), or any command (`/every friday 18:00 /week`). Days:
`daily`, `weekdays`, `weekends`, a day, or several (`mon,thu`). Plain English works for requests: "every friday at
6pm send me a summary of my week". `/routines` lists them, each with a **Cancel** button. One that came due while the
computer was off runs once when it's back (if that's still one of its days).

**Revision packs.** `/pack linear algebra midterm friday` reads that subject's notes (course page, exam prep, lecture
notes, solutions) and builds a 2–6 page pack: what's on it, definitions, theorems with their hypotheses, formulas,
worked problems, pitfalls and a self-test with answers. It's saved in your notes (`<subject>/revision-pack-<date>.tex`
and `.pdf`; `revision-packs/` when the subject has no folder) and sent to Telegram. PDFs need **Tectonic**, a small
LaTeX engine: the first pack without it comes as a `.tex` file, and a message asks **Install Tectonic** / **Not now**
(about 25 MB, from Tectonic's official releases; the first PDF then takes a few minutes while it fetches about 50 MB
of LaTeX packages into Kurooto's cache). After **Not now** it doesn't ask again for 30 days. If a pack doesn't
compile, the AI gets one try to fix it; otherwise you get the `.tex`.

**Packs before exams.** With Deadlines on, the evening before a quiz or exam that has a subject (12 to 36 hours ahead,
from 16:00, `skills.auto_pack_after`) you're asked **A revision pack for it tonight?** with **Build it** / **No
thanks**, once per quiz or exam. `skills.auto_pack` = `auto` builds it without asking (it comes like a `/pack`); `off`
never offers. *Undo:* set `skills.auto_pack` to `off`; packs already made stay where they are.

The rules every skill follows: it only creates notes or adds to them (never rewords or deletes your text), puts your
own words in verbatim, gives every link a reason, keeps health, money and other people's private details out of your
notes, and sends nothing to anyone but you.

*Needs:* Chat. *Leaves your computer:* what you send with a skill, and the notes it reads, go to the AI you picked.
*Turn it off:* Features → Skills; your own skills, routines and packs stay (routines start again when you turn it back
on).

### Quick notes and prompts
`/note <text>` saves it straight into your notes' inbox (`inbox/YYYY-MM-DD-<first words>.md`), as written; a photo or
file with `/note` as its caption is linked from the note. From a terminal: `kurooto note "an idea"` (or pipe text in:
`some-command | kurooto note --title "output"`); this works even when Kurooto isn't running.

Your prompt library is the `prompts/` folder in your notes (Markdown files, subfolders allowed): `/prompts` lists it,
`/prompt <name>` sends one back to copy, `/prompt save <name>` with the prompt on the next lines adds one.

*Needs:* Telegram. *Leaves your computer:* nothing (no AI involved). *Turn it off:* Features → Quick notes and
prompts.

### Notes brain (GBrain)
Search your notes by meaning (`/notes what is a compact space`), and your AI gets a memory of them. Kurooto installs
[GBrain](https://github.com/garrytan/gbrain) and keeps its index in Kurooto's own folder; it re-reads your notes
every 15 minutes. On computers without a graphics card the index is made with Gemini (note text goes to Google) or
keyword-only; with a graphics card or Apple Silicon it stays on your computer.

Three more things, each with its own switch in Settings (`gbrain.*`):
- **Timelines** (on, `gbrain.timelines`): every night, dated log lines in your notes, written like
  `- **2026-10-19** | source — what happened`, become each note's timeline. `/timeline research/reading-group` shows
  one; your AI uses them for "when did I last ...?". Kurooto's own skills write their log lines this way. No AI is
  involved and nothing leaves your computer.
- **Nightly upkeep** (off, `gbrain.upkeep`): GBrain's maintenance cycle at 03:00 (`gbrain.nightly`), light steps
  only: links, facts, timelines, the index, orphaned pages. Steps that would rewrite your note files or call an AI
  model are left out. It's heavy, so on a laptop it waits for the charger. If it fails you're told once (with where
  its log is), not every night.
- **Weekly checkup** (off, `gbrain.checkup`): GBrain's own advisor, Sundays at 19:30 (`gbrain.checkup_when`). You get a
  message only when something is a warning or worse, with **Ignore these** (adds them to `gbrain.checkup_ignore`) and,
  when the brain needs a schema update, **Update the brain**.

**Which steps the upkeep runs** (`gbrain.upkeep_steps`): empty means the light ones above. List GBrain's own phase
names to choose, e.g. `["lint", "backlinks", "sync", "extract", "extract_facts", "consolidate",
"edge_contradictions", "embed", "orphans"]`. Know what you add: `lint` and the repair steps rewrite note files, and
`consolidate`, `synthesize` or `edge_contradictions` call the AI model GBrain is set up with (on a paid key, they
spend). Kurooto never runs `purge` (it deletes pages for good); unknown names are skipped. *Undo:* empty the list.

Kurooto pins GBrain's version and turns off its own update check.

**Your own GBrain.** Already run GBrain yourself (for example on Postgres, with your notes as one of its sources)?
Kurooto can use that brain instead of making its own: set `gbrain.managed` to `false`, `gbrain.exe` to your gbrain
program (empty: the one on your PATH) and `gbrain.home` to its `GBRAIN_HOME` (empty: GBrain's default), then Set up.
Setting up only checks that your brain answers. From then on Kurooto searches it (`/notes`, your AI's notes search,
calls), adds pages through gbrain's own commands (books, with Books on), runs the nightly steps you turned on, and,
if you name the source that is your notes folder (`gbrain.source`), runs `gbrain sync --source <it>` and
`gbrain embed --stale --source <it>` every 15 minutes. It never creates, migrates, upgrades or reconfigures your
brain (no `init`, no `apply-migrations`, no embedding set-up; the checkup has no **Update the brain** button), and it
doesn't back it up: that's yours. The embedding and AI models are whatever your brain is set up with.
**agy and your brain's own tools:** with `gbrain.agy_mcp` on, the next agy run asks you (the same Approve / Deny as
for Kurooto's own tools) to also give agy your brain's MCP server, registered as `gbrain` (`gbrain serve --surface
full`, or `gbrain.mcp_surface`: `starter`, `verbs`) and allowed with `mcp(gbrain/*)`. That is all of its tools, also the
ones that change or remove pages in that brain. If agy already has a `gbrain` server, it's kept; if you listed
gbrain's tools in agy's allow-list yourself, your list is kept and `mcp(gbrain/*)` isn't added.
*Undo:* set `gbrain.managed` back to `true` (Kurooto's own brain is still there; Set up again if it never was);
`agy mcp remove gbrain` and take `mcp(gbrain/*)` out of `~/.gemini/antigravity-cli/settings.json` (Kurooto kept a
backup in its state folder, `backups/`).

### Local AI models
Small AI models on your computer (through [Ollama](https://ollama.com)), picked for its graphics card, for quick
decisions and the notes index: private and offline. Not offered on computers without a graphics card or Apple
Silicon. `/models`.

### After-class notes
A couple of minutes after each class in your timetable ends, Kurooto asks what was worth keeping. Answer with a line
or two, photos of the board or slides, files or a voice note (reply to the question, or answer in the phone app or on
a call). It goes into that subject's `class-log.md`; photos and files are moved next to it (`<subject>/files/`) and
linked. With Chat on, the AI also writes a study log for the class (a lecture note in the subject's folder, linked from
the day's note). **Nothing new** ends it; **Later** keeps the question for your evening check-in call. No questions
for classes you skip, on holidays, in exam periods or after the term ends (see `/term`). Needs Subjects with a
timetable.

**Only some subjects:** Settings → After-class notes → `capture.subjects` lists the subjects to ask about (empty, the
default: every subject), and `capture.skip_subjects` the ones never to ask about, e.g. `["pe"]`. A subject's short
name, full name or alias works in both. A class left out gets no question; the evening debrief still goes through it
like any class without a log (use `/skip` for a class you aren't going to).

*Settings:* `capture.delay_min`, `capture.study_log` (default on: with Chat on, the AI writes a study log),
`capture.subjects`, `capture.skip_subjects`.
*Undo:* empty both lists (`[]`): every subject is asked about again from the next class.
*Leaves:* nothing; with Chat on, your answer and the photos and files you sent with it go to the AI for the study log.

### Remember
Tell Kurooto how you like to be helped and it keeps it: `/remember I hate calls before 8`, or just say "remember that
I like a plan before 9" (on Telegram or on a call). It goes into your notes, in `about-me/how-to-help-me.md`, under
"You told me". That note is yours: read it, edit it, add your own lines. Kurooto never rewords or removes a line, and
what you write there wins. A short version of it goes along with every AI request Kurooto makes, next to the "In
brief" part of your profile. `/remember` on its own shows what it keeps.

It won't keep health, money or password details (they'd travel with every AI request); it says so and keeps nothing.
"Remember to buy milk" is a reminder, not this: use Reminders for that.

*Turn it off:* Features → Remember. The note stays in your notes; delete or edit it as you like. While the note
exists, AI requests still read it; delete the note to stop that.

### Nightly look back
Once a day (23:50) the AI looks at how the day went and suggests at most three small improvements, each with the
evidence behind it. It reads:
- what happened: the questions Kurooto asked you and your answers (and how fast, on which channel), check-ins you
  moved or skipped, calls you answered or missed, after-class prompts, deadlines, AI requests, study sessions;
- today's call transcripts and journal (both can be left out: `retro.transcripts`, `retro.journal`);
- your how-to-help-me note and the settings it may change.

A suggestion can be:
- **a setting**: a better check-in time, quiet hours, deadline nudges, quiz length, the after-class delay;
- **a line for your how-to-help-me note** (under "Learned in the nightly look back");
- **something to watch** for a while before deciding anything;
- **a change to one of your skills**: after you tap Apply, the AI writes the change and you see exactly what changes
  (lines removed and added) with **Save** / **Discard**. Saving writes your own copy of the skill in
  `kurooto/skills/<name>/SKILL.md` and keeps the old version in Kurooto's data folder (`backups/skills`). If you edited
  the skill in the meantime, nothing is saved;
- **an idea**: something new Kurooto could do for you, added to `kurooto/ideas.md` in your notes.

Answer each with **Apply**, **Observe longer** or **No** (buttons, a reply, or on your next call; **Later** keeps it
for the call). Apply does it at once; nothing changes without your tap. **No** drops that idea (however it's worded
next time) for 30 days. **Observe longer** watches it for a week first (reply "observe 14" for 14 days); when the
watching ends, the next look back tells you what it found.

**Steer it:** `/observe whether I study better before noon for 2 weeks` (or say "observe whether ..." / "keep an eye
on ...", or ask on a call). `/observing` lists what's being watched, each with **Stop** and **+7 days** (watch a week longer) buttons. When a watch ends you
get a message with what it found. `/lookback` shows the last look back (and what it noticed); `/lookback now` runs one
now.

*Settings* (`retro.*`): `when` (`daily 23:50`; `weekly sun 21:00` looks back over the whole week), `max_proposals`
(3), `observe_days` (7), `no_days` (30), `transcripts` (on), `journal` (on). The look back's instructions are the
`retro` skill: put your own copy in `kurooto/skills/retro/SKILL.md` to change how it thinks (it's not a command).
*Needs:* Chat. *Turn it off:* Features → Nightly look back. Waiting suggestions stay answerable for three days.

### Phone calls
Talk to Kurooto like a phone call, and let it call you: reminders ("call me at 5 about the laundry"), check-ins,
deadline nudges, quizzes, the morning alarm. During a call it can search your notes, add reminders and deadlines,
start tasks on your computer, answer Kurooto's questions, and more, depending on which features you have on.

**How it works:** setup makes your own *call line*, a small program on your own free Cloudflare account (it's yours;
nobody else's server is involved). Your computer keeps a connection to it, and your phone pairs with it. Calls use
Google's Gemini Live with your own key, so the audio goes between your phone and Google. If your computer is off,
calls still work from what it last sent, and anything that needs the computer waits until it's back.

**Set up:**
1. A Gemini key (the wizard asks for it if your AI is another).
2. **Set up** Phone calls. Kurooto installs what it needs (about 350 MB, once), then opens Cloudflare's sign-in in
   your browser: sign in or make a free account, and approve. Kurooto makes the call line (named `kurooto-` plus
   random letters) at a `workers.dev` address. The address is public but useless without a key from your computer.
3. Pair your phone (see [Your phone](#your-phone)).

**Use:** `/call` gives you a link to call now from any phone or browser (it works for 2 hours). "call me in 20 minutes
about the essay". `/phones` lists paired phones, `/unpair <id>` removes one. Kurooto tells you whenever a new device
pairs; if it wasn't you, remove it. A lost phone: `kurooto rotate` ([Lost phone or keys that got
out](#lost-phone-or-keys-that-got-out)).

**When Kurooto calls you:** a call you don't answer rings again 3 and 6 minutes later (`calls.realert_min`; `[]` rings
once), then becomes a "Missed call" message. The alarm has its own repeats. No calls during a class you attend, a
calendar event (or only `#nocall` ones, see [Calendar](#calendar)), focus, `/hold`, the night or another call: one
that comes due then is held, you're told ("Held a call until 18:02 (class: Linear Algebra): the essay"), and it's
placed by itself when that ends. "call me now" (or "ring me about the essay") calls right away.

**On the call:** speak naturally. If the loudspeaker's echo cuts Kurooto off, use **Interrupt** to talk over it, or
the earpiece / earphones. The mic gate slider makes it need a louder voice in a noisy room. Open questions and
approvals come up at the start of the call, and you can answer them there; an approval that comes in during a call is
asked right away.

**Questions on your phone:** with Phone calls on, your paired phones also get Kurooto's questions and approvals (from
any feature: a check-in, after-class notes, a quiz, a suggestion to approve), as well as Telegram. Answer wherever is
handy; the first answer counts and the others go away.
- *Android:* a notification with **Reply** (type the answer in the notification; on Android 6 it opens a small answer
  window), the question's choices, **Approve / Deny** for approvals, **Later** (ask me on the next call), or the
  message's own buttons. Tap the notification for every option. The app's main screen lists what's **waiting for
  you**.
- *iPhone:* a notification; tap it to open **Waiting for you** in the Kurooto Home Screen app, with the same buttons
  and a box to type in.
- If the computer is off, your answer waits on your call line and is used as soon as the computer is back.

**More on the phone:** Settings → `notify.app_kinds` says what goes to the phone app. The default is
`["call", "question", "approval"]`; add `"reminder"`, `"deadline"`, `"result"` or `"info"` to get those there too
(they still go to Telegram as well). Remove `"question"` and `"approval"` to keep them on Telegram only.

**While you're on a call** nothing else rings: reminder calls and check-ins wait until the call ends (also when the
computer is off), and updates wait too. Wake-up calls still ring.

*Leaves:* call audio goes to Google (your key); the call line keeps a short brief (what's due, today's classes and
check-ins, open questions, the steps for check-in, wake-up and Sunday review calls, your notes' titles) on your
Cloudflare account for calls while the computer is off, and the questions and messages waiting for your phones.
Transcripts stay on your computer.

### Morning alarm
Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm volume, so it rings even
on silent. The call line places it, so it rings even if your computer is asleep. "wake me at 6:45", `/alarm 7:30`,
`/alarm off`, the evening check-in call ("wake me at 7"), or a daily default (Settings → `alarm.daily`). Not
answered: it rings twice more, 5 minutes apart (`alarm.retries`). **Snooze** gives 10 minutes (`alarm.snooze_min`).
Needs Phone calls.

- **The daily alarm** (`alarm.daily`, on `alarm.days`) is always with your call line well before the night: the next
  one is sent as soon as one has rung (and at start, and after this computer wakes), so it rings even if the computer
  sleeps all night. One alarm per morning: one you set for a morning replaces the daily one. **Skip a day:** "no alarm
  tomorrow", "cancel Friday's alarm", `/alarm skip friday` (the daily alarm is back the day after); "cancel my alarm"
  skips the morning that's set. **Turn it off:** "turn my daily alarm off" or `/alarm daily off`; `/alarm daily 7:00`
  sets it. *Undo:* a skipped day can't be un-skipped; set that morning's alarm yourself ("wake me at 7 tomorrow").
- **The night follows your alarm:** while it's set, no other calls from your bedtime (`alarm.bedtime`, default: the
  start of the night hours) until it rings; once you're up, calls can come even if the usual night hours aren't over.
  Without an alarm, the night is the fixed hours (`availability.night`, 23:30 to 07:00).
- **Only nights with an alarm** (`availability.night.alarm_only`, off by default): if you set the alarm every night you
  want quiet, turn this on and the fixed hours stop holding calls; only bedtime to the alarm does. With no alarm set,
  nothing holds calls overnight (a reminder call you set for 02:00 rings at 02:00), and Kurooto's "back online" notice
  doesn't wait for the morning. Off, the default, is the safe one: the fixed night hours hold calls whether or not you
  set an alarm.
- **Your day, drafted:** with Chat on, 20 minutes before the alarm the AI drafts today's plan into today's daily note
  ("## Plan for today (draft …)": classes, what's due, a top 3, suggested blocks, and questions for you).
- **The wake-up call** goes through that plan, asks which classes you're skipping and when to call you today (the
  evening check-in, and a midday one if you want), and afterwards, with Chat on, settles "## Plan for today" in the
  daily note from what you said.
- **The morning page:** at the alarm, if this computer is awake, it opens the morning page in your browser (today's
  plan, classes, calendar, what's due, check-ins). It's also at `http://127.0.0.1:8770/morning`.
- **Keep this computer awake until the alarm** (`alarm.keep_awake`, off until you turn it on): from 12 hours before
  the alarm until 15 minutes after it rings (or until you answer), this computer doesn't go to sleep by itself, so
  the day's plan is drafted 20 minutes before the alarm even if it would have slept overnight. Linux: it keeps running
  with the lid closed too. macOS: a closed lid still sleeps a Mac (unless an external display is attached). Windows:
  the lid follows Power Options. On battery, setting the alarm reminds you to plug in. The hold ends by itself, even
  if Kurooto stops; the screen can still turn off.

*Settings:* `alarm.daily`, `alarm.days`, `alarm.bedtime`, `alarm.prep_min` (default 20; 0 = no draft),
`alarm.open_page` (default on), `alarm.notes` (default on: the wake-up call goes into the daily note),
`alarm.keep_awake` (default off), `availability.night.alarm_only` (default off).
*Undo:* `alarm.keep_awake` off; it lets go at once. `availability.night.alarm_only` off: the fixed night hours hold
calls again at once.
*Leaves:* the alarm time goes to your call line; with Chat on, the AI reads your notes to draft the plan, and the
wake-up call's transcript to settle it.

### Reminders with the lid shut
When this computer is asleep or off (a shut lid, a flat battery, `kurooto stop`), your Android phone still gets your
reminders at their time, and in the morning one line with the day's first class and what's due that day. Off until you
turn it on (Settings → Features). Needs Phone calls and the Kurooto app on an Android phone. An iPhone can't get these:
its Home Screen app comes from your call line, so it can't hold a key the call line doesn't have.

- **How it works:** whenever your reminders change, every 10 minutes, and as the computer goes to sleep (Linux and
  Windows say so), Kurooto hands your call line what's timed in the next day: each reminder, and the morning line.
  Each one is sealed for your phone with a key only the phone has (the app makes it the first time it runs), so your
  call line holds a time and text it can't read.
- **Whichever side is awake says it, once:** if this computer is awake at the time, it says the reminder on Telegram
  as usual and your call line doesn't. If it's asleep, your call line sends it to your phone, which shows it as a
  normal notification, and when the computer wakes it doesn't say it again. Telegram doesn't get reminders while the
  computer sleeps (your bot's token never leaves this computer for this); they come when it wakes, unless your phone
  already had them.
- **The morning line**, e.g. "First class 09:00: Linear Algebra. Due today: Problem set 3 (17:00).", comes with your
  alarm if one is set that morning, else at `lidsafe.morning` (07:30), and never later than 30 minutes before the
  first class. It only comes from your call line: when this computer is awake, the morning page and your check-ins
  have it.
- **If this computer is on but can't reach your call line** when a reminder is due, it waits 2 minutes for it (30
  just after waking up), then says it anyway. If your call line sent it to your phone meanwhile, that one comes twice.
- **macOS** doesn't tell programs it's about to sleep, so there your call line has the reminders from the last change
  or the last 10 minutes: one you set in the seconds before you shut the lid may wait until the computer wakes.
- A reminder your call line couldn't get to your phone (5 tries, a minute apart) is said here when the computer is
  back. `kurooto off` silences your call line, these included, until you turn Kurooto on again.

*Settings:* `lidsafe.hours` (24; 12 to 24), `lidsafe.reminders` (on), `lidsafe.today` (on: the morning line),
`lidsafe.morning` ("07:30").
*Check:* `kurooto doctor` (or `/health`) says "Reminders with the lid shut: your call line holds 5 for 1 phone(s)".
"No phone can open them yet": update the Kurooto app on your Android phone and open it once.
*Undo:* turn it off (Settings → Features). Your call line drops what it holds at once (or the next time this computer
reaches it), and reminders are Telegram's only again, late after a sleep as before.
*Leaves:* the next day's reminder times and ids, and for each Android phone a copy sealed with that phone's key, go to
your call line; your phone's public key too. When your call line sends one, the sealed copy goes through ntfy.sh. The
text can be read only on your phones.

### Voice notes
Send your bot a voice message: it's written out (you see what it heard) and handled like a typed message. Uses your
Gemini key. *Leaves:* the recording goes to Google; on the free tier Google may use what you send to improve its
products, so don't say anything you wouldn't type.

### Stay awake on charger
While your computer is plugged in, it doesn't go to sleep by itself, so Kurooto keeps answering; on battery it sleeps
as usual. The screen can still turn off.

- **Lid closed (Linux):** turn on `awake.lid` and it keeps running with the lid closed while plugged in (it holds the
  lid switch through systemd-inhibit). If your system doesn't let a background program hold the lid switch, it holds
  the rest and its line in `kurooto doctor` says so.
- **Windows and macOS** can't be changed by an app here. Windows: Control Panel → Power Options → "Choose what closing
  the lid does" → "Do nothing" when plugged in. macOS: only with an external display.
- The hold ends when Kurooto stops, even if it crashes.

*Settings:* `awake.lid` (default off).
*Undo:* `awake.lid` off, or turn the feature off; the computer sleeps as usual at once.

### Calendar
Your calendar's events, read-only, from its private iCal link. Google Calendar on a computer: Settings → your calendar
→ Integrate calendar → **Secret address in iCal format**. Outlook and Apple Calendar have one too. Paste it in the
feature's card. `/today`, `/cal` (7 days), "what's on tomorrow?". It can remind you before each event
(`calendar.remind_min`, in minutes; 0, the default, is off). Refreshed every 15 minutes. The link lets anyone read
that calendar, so it's kept in your computer's keychain.

- **No calls during events:** every timed event holds calls (`calendar.no_calls_in_events`). If that's too much, set
  `calendar.nocall_events` to `tagged`: then only events with `#nocall` in the title or description hold calls, and
  every event in a calendar whose name contains "no call" (all-day ones too, e.g. "Exam day #nocall").
- **Focus events:** an event with `#focus` in its title or description is focus time while it runs: calls are held
  and messages that can wait are kept until it ends, then delivered together.
- Events that look like deadlines or exams go into [Deadlines](#deadlines) (`deadlines.from_calendar`).

- **Google calendars without an iCal link:** set up [Google Calendar](#google-calendar) instead (or as well). It
  reads your Google calendars through Google's API, from one account or several, and turns Calendar on.
- **Private events are "Busy (private)":** an event marked private (Google Calendar's **Private** visibility,
  `CLASS:PRIVATE` in an iCal calendar, or `#private` in its title or description) shows as **Busy (private)**
  wherever Kurooto shows or tells it: `/today`, `/cal`, the dashboard, calls, reminders and the AI. Its title, place
  and description aren't kept, only its time. It still holds calls like any event.
- **Class calendars:** `/cal classes Timetable` (several: `/cal classes Timetable, Labs`) makes the events of the
  calendars with those names classes: no calls during them (with Subjects' margin, and `/skip` works), they're in
  your day's classes (morning call, evening debrief, dashboard), and one whose title names a subject ("Linear Algebra
  lecture") gets the [after-class](#after-class-notes) question. `/cal classes` lists your calendars' names;
  `/cal classes none` stops it. A timetable class at the same time isn't counted twice.

*Settings:* `availability.nocall_keyword` (`#nocall`), `availability.nocall_calendar` (`no call`),
`availability.focus_keyword` (`#focus`), `calendar.mask_private` (on), `calendar.private_keyword` (`#private`),
`calendar.class_calendars` (`[]`).
*Leaves:* nothing; event descriptions are read only for `#nocall`, `#focus` and `#private` and aren't kept.
*Undo:* `/cal classes none`; `calendar.mask_private` = `false` shows private events' titles again (on this computer
and to your AI).

### Notes sync
Your notes folder, kept in your own **private** GitHub repository: every change is in its history, and edits made
elsewhere (another computer, GitHub's website) come in too. Every 10 minutes, and with `/sync`. What an AI request
writes in your notes is also sent up about two minutes after it finishes (one push for a burst of requests;
`notes_sync.after_jobs`, 0 turns it off), and whatever is left goes up when Kurooto stops (a shutdown, an update),
unless it's paused.

**Set up:** 1. [Make a repository](https://github.com/new): any name, **Private**, nothing ticked. 2. [Make a
fine-grained token](https://github.com/settings/personal-access-tokens/new): Repository access → Only select
repositories → that one; Permissions → Contents → **Read and write**. 3. Paste both in the feature's card. Kurooto
refuses a public repository. Git is installed for you if it's missing (on a Mac, Apple's installer opens: click
Install, then press Set up again).

**When a note changed in two places at once** (say, your phone and this computer), nothing is lost:

- `notes_sync.on_conflict` = `keep both` (the default): the note keeps the version from elsewhere, and this
  computer's goes beside it as `<note> (conflict, this computer, <date time>).md`. You get a message naming both;
  merge them when you like and delete the copy. Notes changed on one side only merge as usual. A note deleted on one
  side and changed on the other is kept, changed.
- `stop`: sync stops, changes nothing, and tells you (at most every 6 hours) until you've sorted it out yourself in
  the notes folder (`git pull --rebase`, fix the files it lists, `git add`, `git rebase --continue`). It never forces
  anything.
- A merge or rebase left half done in the notes folder (you, sorting one out) is left alone: sync waits until it's
  finished.

**A notes folder that's already a Git repository** keeps its remote: an `origin` that's the same repository (over
HTTPS or SSH) is used as it is; an `origin` that's another repository is left alone and Kurooto adds a remote of its
own (`kurooto`).

With Phone calls on, your call line can read whole notes from the repository while your computer is off.

*Settings:* `notes_sync.on_conflict` (`keep both` | `stop`).
*Undo:* `notes_sync.on_conflict` = `stop`. Conflict copies are ordinary notes: delete them once merged.

### Sync everything
`/sync all` or "sync everything" on Telegram, or `kurooto sync` in a terminal (with Kurooto running), runs every sync
that's on, one after another: your notes with your repository, Google (Classroom, Classroom → notes and the mail
digest), your calendars, research project logs, the notes brain's index, a backup (with Backups on; skipped when the
backup folder isn't there, e.g. the drive is unplugged), then your notes again (to send up what the others just
wrote). A feature that's off is left out. It runs in the background and you get one line each when it's done,
e.g. `Calendar: ok, 23 events`. With Notes sync off, plain `/sync` does the same. `kurooto sync` waits and prints the
summary; `kurooto sync --no-wait` starts it and returns (the summary comes as a message); `kurooto sync --status` says
whether one is running and how the last one went (it works with Kurooto stopped, too).

### Backups
Once a day, a zip of Kurooto's settings, data and state in a folder you pick: a folder on an external drive, or one
your computer already syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox), so the zip goes there too. The
last 7 are kept (`backups.keep`); Kurooto removes only its own older zips (`kurooto-backup-<date>-<time>.zip`), never
anything else in that folder.

**Set up:** Features → Backups → paste the folder's full path (the card lists cloud folders and drives it found on this
computer; it can't be inside your notes folder). It runs at 03:30 (`backups.when`); on a laptop it waits for the
charger, and if a day went by without one (the drive was unplugged, the laptop was off) it makes one within the hour
once it can. `/backup` makes one now, `/backups` lists them. From a terminal: `kurooto backup`, or `kurooto backup
--to <folder>` for a one-off copy somewhere else (handy before reinstalling).

**What's in it:** your settings, Kurooto's data (including the notes brain's index; `backups.index` off leaves it out:
smaller, but it has to be rebuilt) and its state (check-ins, deadlines, AI requests and answers, the schedule).
**Not in it, unless you turn them on in Settings:**
- `backups.notes`: your notes folder too (without `.git` and similar app folders). Turn it on if your notes aren't
  synced anywhere else.
- `backups.secrets`: your passwords and keys (bot token, API keys, sign-ins). Then **anyone with the zip can use
  them**: only for a folder that's yours alone. Without them, after a restore you sign in again where Kurooto asks.
- `backups.confidential_mail`: confidential mail summarised on this computer (Mail digest's local mode,
  `mail/confidential/` in Kurooto's data folder). Off, it stays out of the zip.

The zip isn't encrypted.

**Putting one back:** `kurooto restore <zip>`. It shows what's in the zip and asks first; then it stops Kurooto (the
normal way, so Notes sync sends up what's left first; forced only if it hasn't stopped after 90 seconds), keeps a
copy of how things were (in Kurooto's data folder, `restore-safety/`, the last two), puts the backup's settings and
data back, and starts Kurooto again. Your notes are never overwritten: a note that's missing comes back; a note that's
different now is kept as it is, and the backup's copy goes into `restored-<date>/` in your notes folder. `--no-notes`
leaves the notes folder alone; `--no-start` doesn't start Kurooto afterwards; `--yes` doesn't ask. Restoring onto
another kind of computer (Windows ↔ Mac) works; the notes folder becomes this computer's default.

*Turn it off:* Features → Backups → Turn off. The zips already made stay where they are.

### Profile sync
Your Kurooto setup, kept **encrypted** in your own private GitHub repository, so a new computer (or a reinstall) is set
up again in a minute instead of an evening.

**What's saved:** everything you changed in Settings and which features you have on; your passwords and keys (bot
token, API keys, the Google sign-in, your call line's keys and its Cloudflare sign-in, so the same call line and the
same paired phones keep working); and the state worth keeping: deadlines, quiz progress, routines, what the nightly
look back has observed, the Agent plan calendar, Classroom's "already seen" lists, and reminders, calls and the alarm
you've scheduled. **Not saved:** your notes (Notes sync keeps those; your how-to-help-me note and recurring quizzes
live in your notes anyway), AI request history, call transcripts, the reports you added in About you, caches and logs.

**Set up:** Features → Profile sync. Leave the repository and token empty to use the repository Notes sync uses (the
profile goes on a branch of its own, `kurooto-profile`, so your notes folder never sees it), or give another private
repository and a token for it, made the same way as for Notes sync. Then pick a **passphrase** of a few words (at least
10 characters). You need it on a new computer; it's never stored anywhere, and if you forget it the profile can't be
opened. Your notes are still fine: delete the `kurooto-profile` branch on GitHub (or use another repository) and set up
Profile sync again with a new passphrase.

**When:** once a day (04:40, `profile.when`), and ten minutes after you change a setting in the dashboard or turn a
feature on or off (`profile.after_changes`; several changes in a row make one save). A profile is small, so it also
runs on battery. Nothing changed: nothing is sent. `/profile` shows what's saved; `/profile save` saves now.

**Two computers:** if another computer saved the profile since this one last did, this one doesn't overwrite it; it
tells you (at most once a week), and `kurooto doctor` says so. Restore it here (`kurooto profile restore`), or save over
it (`/profile save`; the old one stays in the branch's history).

*Turn it off:* Features → Profile sync → Turn off. What's in the repository stays there; delete the `kurooto-profile`
branch on GitHub to remove it.

### Google (Classroom, Gmail drafts)
Classroom assignments go into Deadlines (marked done when you hand them in); new posts in your courses come to
Telegram. Gmail drafts: `/draft someone@example.com ask for an extension on problem set 3` (the AI writes it) or
`/draft someone@example.com | subject | the email`. **Kurooto never sends email by itself**: drafts wait in Gmail for
you.

**Set up (10 to 15 minutes, once):** Kurooto uses your own Google "OAuth client", so no one else's app ever holds your
Google access. Every click is in [Google: setting up your own sign-in (step by step)](#google-setting-up-your-own-sign-in-step-by-step);
in short:
1. Make a Google Cloud project, and turn on the APIs for the features you want (Classroom, Gmail, Drive, Calendar).
2. Google Auth Platform: app name Kurooto, your email, External; on **Branding**, Kurooto's home page, privacy page
   and the authorized domain (the card has copy buttons for them).
3. **Audience → Publish app** (In production; in Testing, Google signs you out every 7 days).
4. **Clients → Create client → Desktop app → Create → Download JSON** (Google shows the secret only once).
5. Paste the file in the card (or choose it) and press Save; Google's sign-in opens. It says "Google hasn't verified
   this app": that's your own project, which Google hasn't reviewed. Advanced → Go to Kurooto → Continue.

Gmail drafts are off by default (Settings → `google.gmail_drafts`; then sign in again). School accounts sometimes
block unverified apps; then use the Calendar feature's iCal link for your timetable instead.

**More Google features** build on this sign-in: Classroom → notes, Mail digest, Email reply drafts and the Agent plan
calendar. Each is off until you set it up, and each needs one more permission from Google. To set one up, turn on its
API in your Google Cloud project (its card links the page), press **Save** on its card, and sign in with Google again.
Google lists what it's asking for; it also shows the "Google hasn't verified this app" screen again (Advanced → Go to
(your project)). When you're back, the feature turns on by itself. If you untick a permission on Google's screen,
that feature stays off and everything else keeps working. Google may say a permission is "restricted" or "sensitive":
that's Google's label for mail and Drive access, and it's fine for your own client (the warning is about apps other
people publish).

What each one asks Google for, in plain words:

| Feature | Google's permission | What Kurooto does with it |
|---|---|---|
| Classroom → notes | See your Classroom course materials; see and download your Google Drive files (read-only) | Reads materials, coursework and announcements, and opens only the Drive files attached to or linked from a post. Changes nothing. |
| Mail digest | Read your email (read-only) | Reads only the mail you choose for the digest; the rest it counts by its sender, subject and labels, on your computer. Can't send, delete or mark anything. |
| Email reply drafts | Manage drafts and send email | Writes reply drafts to mail in your digest; sends one only when you tap Send. |
| Agent plan calendar | Make secondary calendars and manage their events | Makes one calendar of its own, "Agent plan", and writes only there. It can't see or change your other calendars. |
| Google Calendar | See your calendars (read-only) | Reads your own calendars and the ones you subscribed to, the next two weeks; other people's shared calendars are left out. Changes nothing. |
| Mail digest by email | Send email on your behalf; see your email address | Emails each mail digest to that account's own address, and to no one else. Can't read your mail. |
| Drive upload | See, edit, create and delete only the Drive files it uses | Makes one folder, "Kurooto", and uploads there the files you send yourself. Can't see your other files; shares nothing. |

To withdraw a permission: your Google account → Security → Third-party access → your project.

### Several Google accounts
A personal account and a school one, say: each feature can use the account you choose. The first account you sign in
with is **main**; every feature uses main unless you say otherwise. Each account signs in separately (with the same
Google Cloud project), and each is asked only for what the features using it need, when you set them up; Kurooto
also asks other accounts for their address, so it can tell them apart.
- **On a feature's card:** the **Which Google account** box. Empty keeps the account it uses; a new name (`school`)
  adds that account: Google's page opens with its account chooser, so pick the right one. Google Calendar can read
  several at once (`main, school`): press Save once for each account.
- **On Telegram:** `/google` lists your accounts, their addresses and what uses each. `/google use mail school` moves
  a feature (`classroom`, `drafts`, `mail`, `email`, `calendar`, `plan`, `drive`, `classroom_notes`); if that account
  hasn't allowed it yet, the feature pauses until you press Save on its card and sign in. Reply drafts always use the
  mail digest's account.
- If you sign in to the same Google account under two names, Kurooto says so.
- If one account's sign-in expires, only the features using it pause, and you're told which.

*Settings:* `google.accounts` (the names), `google.use` (feature → account).
*Undo:* `/google forget school` forgets that account's sign-in on this computer (its features go back to main); to
take Kurooto's access away at Google too, use myaccount.google.com/connections while signed in to that account.

### Google: setting up your own sign-in (step by step)
Kurooto signs in to Google with **your own app registration**: a free Google Cloud project that only you own, with an
"OAuth client" in it. Nobody else's server sits in between: Google sees your project asking for your data, and you
say yes or no. It costs nothing (no billing account), and it takes 10 to 15 minutes, once. You do it in the browser,
on any computer; the last step (signing in) happens on the computer Kurooto runs on.

Google renames these screens now and then. If a button has a slightly different name, pick the nearest match: the
order of the steps stays the same. You can make the project with any Google account; you sign in later with the
account whose Classroom, mail or calendar you want (a personal account is easiest; see Troubleshooting below for
school accounts).

**1. Create the project.** Open [console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate).
1. Project name: `Kurooto` (any name works; only you see it). Leave Organization or Location as it is.
2. Press **Create** and wait a few seconds for the notification.
3. Check that the project picker at the top of the page shows your new project: every step below happens inside it.

**2. Turn on the APIs your features use.** Each API is a switch that lets your project talk to one Google product.
Open the link for each feature you want, check the project name at the top, and press **Enable**. You can come back
for more later.

| For | API | Turn it on |
|---|---|---|
| Google (Classroom deadlines and posts), Classroom → notes | Google Classroom API | [classroom.googleapis.com](https://console.cloud.google.com/apis/library/classroom.googleapis.com) |
| Gmail drafts, Mail digest, Email reply drafts | Gmail API | [gmail.googleapis.com](https://console.cloud.google.com/apis/library/gmail.googleapis.com) |
| Classroom → notes (the files attached to posts) | Google Drive API | [drive.googleapis.com](https://console.cloud.google.com/apis/library/drive.googleapis.com) |
| Agent plan calendar | Google Calendar API | [calendar-json.googleapis.com](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) |

**3. Branding: what Google's sign-in screen says about your app.** Open
[Google Auth Platform → Branding](https://console.cloud.google.com/auth/branding). The first time it says "Google Auth
platform not configured yet": press **Get started**, and a short form asks four things:
1. **App Information:** App name `Kurooto`; User support email: pick your own address from the list. **Next**.
2. **Audience:** **External** (anyone with a Google account can sign in, which here means you). **Next**.
3. **Contact Information:** your own email address (Google writes to it about the project). **Next**.
4. **Finish:** tick "I agree to the Google API Services: User Data Policy", press **Continue**, then **Create**.

Then, back on the **Branding** page, fill in the rest and press **Save** at the bottom:

| Field | What to put |
|---|---|
| App name | `Kurooto` (already there) |
| User support email | your own email (already there) |
| App logo | leave it empty (a logo needs Google's review) |
| Application home page | `https://avtarfr.github.io/kurooto/` |
| Application privacy policy link | `https://avtarfr.github.io/kurooto/privacy.html` |
| Application terms of service link | the home page again, or leave it empty |
| Authorized domains | press **Add domain**, then `avtarfr.github.io` |
| Developer contact information | your own email |

Why Kurooto's pages: Google asks every app that's "in production" for a home page and a privacy policy, and those
links must be on an authorized domain. They describe what Kurooto does with your data; nothing is sent to that site.
The card in Kurooto has copy buttons for these values.

**4. Audience: publish the app.** Open [Google Auth Platform → Audience](https://console.cloud.google.com/auth/audience).
1. User type: **External** (from step 3).
2. Publishing status: **Testing**. Press **Publish app**, then **Confirm**. The status becomes **In production**.

Why: in Testing, Google ends every sign-in after **7 days** (Kurooto would ask you to sign in again every week), and
only accounts listed under Test users can sign in. In production, your app stays **unverified** (Google hasn't
reviewed it), which is fine for personal use: up to 100 people can ever sign in to an unverified app, and each sees a
warning first (step 7). You don't need to submit it for verification; if Google suggests it, you can ignore that.
(Made the project with a school or work account, and you'll only ever sign in with that organisation's accounts? Then
**Internal** works too, if Google offers it: no Publish step and no warning.)

**5. Data access: nothing to do.** [Google Auth Platform → Data access](https://console.cloud.google.com/auth/scopes)
lists the permissions ("scopes") an app declares. You can leave it empty: Kurooto asks for each permission when you set
a feature up, and Google shows it on the sign-in screen. If you add scopes here, Google may suggest verification;
ignore that too.

**6. Clients: make your desktop client.** Open [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients).
1. Press **Create client**.
2. Application type: **Desktop app**. Name: `Kurooto` (only you see it).
3. Press **Create**. A window shows your client ID and client secret: press **Download JSON** right away. Google shows
   the secret only this once. (Closed the window? Open the client, press **Add secret**, and download the file again.)
4. In Kurooto: Features → Google → paste the file's contents into the box (or press the file button and choose the
   file) → **Save**. In the setup wizard, the Google card has the same box.

Keep the file to yourself, like a password. On its own it can't read your data (that takes your sign-in too), but it
lets an app present itself as yours.

**7. Sign in.** After Save, Kurooto opens Google's sign-in (on the computer Kurooto runs on).
1. Pick the account whose Classroom, mail or calendar you want.
2. Google says **"Google hasn't verified this app"**. That's your own project: you made it a few minutes ago, and Google
   hasn't reviewed it (Google reviews apps that strangers use). Press **Advanced**, then **Go to Kurooto (unsafe)**.
   Google says "unsafe" because it can't vouch for an app it hasn't reviewed; this one is yours and runs on your
   computer.
3. Google lists what Kurooto asks for. Leave the boxes ticked and press **Continue**.
4. The tab says "Signed in with Google". Close it; the Google card in Kurooto turns on.

Later, a new Google feature (the mail digest, say) needs one more permission: turn on its API (step 2), press **Save**
on its card, and sign in again (step 7).

**Undo it, or delete it all:**
- Take back Kurooto's access to your account: [myaccount.google.com/connections](https://myaccount.google.com/connections)
  → Kurooto → **Delete all connections** (Kurooto then asks you to sign in again).
- Delete the client: Clients page → tick it → **Delete** (you can restore it for 30 days).
- Delete the whole project: [console.cloud.google.com/iam-admin/settings](https://console.cloud.google.com/iam-admin/settings)
  → **Shut down** → type the project ID. Google deletes it after 30 days; until then you can restore it.
- Google deletes a client that hasn't been used for six months (it emails you a month before). If that happens,
  make a new one (step 6) and paste it in.

| What you see | What to do |
|---|---|
| "Access blocked: Kurooto has not completed the Google verification process" | The app is still in Testing and this account isn't a test user: Publish app (step 4). Or add the account under Audience → Test users (but Testing signs you out after 7 days). |
| "Access blocked: (your school) has blocked access" or "Error 400: admin_policy_enforced" | Your school's or employer's account doesn't allow unverified apps. Sign in with a personal account where you can. For your timetable, use the Calendar feature's private iCal link instead (no Google project needed). Classroom has no way around it: ask your administrator, or leave it off. |
| "Error 400: redirect_uri_mismatch" | The client isn't a Desktop app (a "Web application" can't come back to Kurooto). Make a Desktop app client (step 6) and paste that file. |
| "Error 401: invalid_client" or "deleted_client" | The file is from a client that was deleted, or whose secret was replaced. Download a new file (Add secret, or a new client) and paste it. |
| Kurooto asks you to sign in again every week | The app is still in Testing: Publish app (step 4), then sign in once more. |
| A feature stays off after signing in ("access_denied") | You pressed Cancel, or unticked its permission. Press Save on its card and sign in again, leaving the box ticked. |
| Kurooto says an API "has not been used in project … or it is disabled" | Turn that API on (step 2), wait a minute, and try again. |
| The page after signing in "can't be reached" (127.0.0.1) | Sign in on the computer Kurooto runs on: Google sends you back to Kurooto there. |
| Google's screen says "Something went wrong" | Try again in a private window, signed in to one Google account only. |

### Classroom → notes
Three times a day (07:00, 13:00, 19:00) Kurooto reads what's new in your Google Classroom courses: materials,
coursework, announcements, and the files your teachers attach or link from Drive. The AI files each course into your
notes, in the course's folder (`linear-algebra/`; Kurooto uses the matching subject from Subjects when you have one):
- a note per lecture or problem set (`linear-algebra/2026-10-20-eigenvalues.md`): what it covers, the teacher's post,
  the files and links to your related notes;
- the course page `linear-algebra/course.md`: lecture notes in order, coursework under Tasks, exams and announcements;
- an always-current `linear-algebra/exam-prep.md`: next assessment, what's covered so far, must-know facts (which Quiz
  asks you), typical questions and gaps. Kurooto rewrites only the part between its two markers; anything you write
  above or below them stays as you wrote it.

Assignment due dates already reach Deadlines through the Google feature; dates in posts (a midterm, a moved quiz) are
added too. Files are kept in Kurooto's own data folder, not your notes: Word and PowerPoint files and Google Docs,
Slides and Sheets are read as text; PDFs are read when `pdftotext` (Poppler) is installed, or by an AI that can open
files (agy). Videos and images are linked, not downloaded. The first check goes back 60 days.

- `/classnotes` checks now (so does `/sync all`); `/classnotes courses` lists your courses and the folder each one
  goes to.
- `/classnotes skip chess` leaves out courses with "chess" in their name; `/classnotes unskip chess` undoes it.
- Posts about a topic on your not-interested list (`/ignore`) are only counted.
- If the AI fails, the posts wait and are tried again at the next check; after three failures you get a message.

*Settings:* `classroom_notes.at` (when), `classroom_notes.folders` (a course's exact name → the folder you want),
`classroom_notes.files` (download attached files), `classroom_notes.max_file_mb` (30),
`classroom_notes.backfill_days` (60).
*Leaves:* posts and file text go to the AI you picked. *Turn it off:* Features → Classroom → notes → Turn off; the
notes stay.

### Mail digest
Twice a day (08:00 and 18:00) your new mail, sorted into **Needs action**, **People**, **Courses**,
**Opportunities** and **Admin**, comes to you as a message (a busy check comes in parts, 20 mails each), with a copy
in your notes (`mail/2026-10-20-0800.md`, linked from that day's journal). Deadlines it finds go into Deadlines;
course news goes onto the course page.

**You choose what it may read.** Everything else is only counted, by its sender, subject and labels:
- `/mail read @school.example` (a domain), `/mail read sam@example.org` (a sender), `/mail read label:Courses` (a
  Gmail label); `/mail unread ...` takes one off; `/mail rules` lists them.
- On a school or work Google account, mail from your own organisation's domain is read too (setting
  `mail_digest.own_domain`). Personal mail among it (not about study or work) is only counted.
- Promotions, Social and topics on your not-interested list are only counted (Promotions and Social are read when a
  `/mail read` rule names them).
- **Or by Gmail's own search** (`mail_digest.query`, empty by default): `/mail query -category:promotions
  -category:social` reads all your mail except Promotions and Social (chats, sent mail, drafts, spam and trash are
  never looked at). Any Gmail search works (`label:Courses OR from:school.example`, `-category:forums`); the query
  decides on its own, so Promotions are read if it doesn't leave them out. Mail it brings in is treated like mail from
  your own domain: personal mail among it (not about study or work) is only counted, never summarised. Your
  never-read list, the not-interested list and the confidential check still come first. `/mail query` shows it,
  `/mail query off` clears it; `/mail rules` lists it.
- A personal Gmail account reads nothing until you choose something; the scheduled digest tells you how (once a day,
  until you do).

**Confidential mail is never read.** Work or school mail may be covered by your institution's email policy (many
forbid forwarding confidential messages, and institutional mail belongs to the institution). Kurooto never summarises
mail marked confidential: if its subject, its text (all of it, footers and quoted replies too) or a Gmail label's name
says "confidential", "do not forward", "restricted", "private and confidential", "privileged and confidential",
"proprietary and confidential", or carries a standard confidentiality footer ("intended solely for the addressee", "if
you are not the intended recipient", "this e-mail and any attachments are confidential / may be privileged"), it's
only counted, even from a sender or label you chose, and it never gets an AI reply draft. Kurooto checks the text on
your computer and drops the mail right there, without keeping it. Many institutional mails carry such a footer, so
expect more of your mail to be only counted. Tune the list in `mail_digest.confidential_words` (regular expressions,
any case; a space matches any run of spaces or line breaks). To keep a sender, domain or label out of the digest
altogether: `/mail never @office.example` (`/mail unnever ...` takes it off; `/mail rules` lists both lists). This is
on by default (`mail_digest.skip_confidential`).

**Optional: confidential mail summarised on this computer.** Set `mail_digest.confidential` to `local` (the default is
`count`) and, with **Local AI models** on, a model on this computer (Ollama) reads mail marked confidential instead of
leaving it only counted. The AI you picked still never sees it. The summary is kept only in Kurooto's data folder
(`mail/confidential/<date>.md`, readable only by your user account): not in your notes, not on Telegram (which only
says "Confidential (2): summarised on this computer; open the dashboard to read it"), not in Profile sync, and not in
Backups unless you turn on `backups.confidential_mail`. Read it in the dashboard: Features → Mail digest →
**Confidential mail**. Dates it finds are only offered, on that page or with `/mail confidential` on Telegram (titles
and dates only), each with **Add to Deadlines** / **Not needed**. Marked mail still never gets an AI reply draft.
Without a ready local model (Local AI models off, not set up, or resting on battery) it's only counted, and Kurooto
says so once. Up to 15 such mails a check, three per request to the local model, each cut to its first 3,500
characters; `mail_digest.local_model` picks another Ollama model (default: Local AI models' helper model).

`/mail` checks now (so does `/sync all`).
*Settings:* `mail_digest.at`, `mail_digest.read`, `mail_digest.never_read`, `mail_digest.own_domain`,
`mail_digest.query`, `mail_digest.skip_confidential`, `mail_digest.confidential_words`, `mail_digest.confidential`
(`count` or `local`), `mail_digest.local_model`, `mail_digest.save_note` (the copy in your notes),
`mail_digest.first_days` (how far back the first check looks: 3).
*Leaves:* the text of the mail you chose (and, with a query, the mail it matches) goes to the AI you picked; for the
rest, only counts. Nothing is ever sent, deleted, archived or marked read. *Turn it off:* Features → Mail digest →
Turn off. *Undo:* `/mail query off` goes back to only your `/mail read` rules (and your own domain).

### Email reply drafts
When the mail digest finds mail that needs your reply (a question or request to you), the AI drafts a short reply in
your voice into your Gmail Drafts and sends it to you with **Send / Edit / Discard**. **Nothing is sent unless you
tap Send.** Edit: say what to change ("say I can do 10am"); the AI rewrites the draft and asks again. Discard deletes
just that draft. Unanswered, it stays in your Gmail Drafts (the question expires after 3 days). Replies go only to
the sender of a mail in your digest (or its reply-to address), never to no-reply addresses or mail marked confidential
anywhere in it (footers included; even if it was read while the check was off, and even in local mode) or on your
never-read list, at most 5 a day (`reply_drafts.per_day`). Needs the Mail digest.
*Turn it off:* Features → Email reply drafts → Turn off.

### Agent plan calendar
Kurooto makes a calendar of its own, **Agent plan**, in your Google Calendar, for the time blocks it plans with you:
the morning plan, or "block 2 to 4 for the problem set" on a call. It writes only to that calendar: Google's permission
for it covers only calendars Kurooto makes, so it can't see or change your others. Each block has a 5-minute
reminder (`agent_plan.remind_min`; 0 for none).
- `/blocks` shows today's blocks; `/blocks add 14:00-15:30 problem set 4` adds one; `/blocks clear` removes today's.
- Hide or delete the calendar in Google Calendar any time; Kurooto makes a new one the next time it plans something.
- To see the blocks in Kurooto's own Calendar feature too, add the Agent plan calendar's private iCal link there.

*Turn it off:* Features → Agent plan calendar → Turn off (the calendar stays in Google Calendar until you delete it).
With [several accounts](#several-google-accounts), the calendar lives on the one you choose on its card (`/google use
plan personal`); moving it makes a new Agent plan calendar there.

### Google Calendar
Calendar reads your Google calendars through Google's own Calendar API instead of private iCal links: for school or
work accounts that don't offer a "secret address in iCal format", and for reading two accounts at once. Set it up on
its card (Which Google account: `main`, `school`, or `main, school`); when Google says yes, it turns Calendar on too.
Everything in [Calendar](#calendar) works the same: `/today`, no calls during events, `#focus`, reminders, class
calendars, private events as Busy (private).
- It reads your own calendars and the ones you subscribed to (a class calendar, holidays). Calendars other people
  share with you (a friend's or a teacher's own calendar) are their data and are left out, and so is Kurooto's own
  Agent plan calendar (`/blocks` shows that). Hidden calendars are left out too.
- Leave out more by name: `google_calendar.skip` = `["Birthdays"]`.
- A calendar that's also an iCal link in Calendar comes twice: leave it out here with `google_calendar.skip`.

*Leaves:* nothing; Kurooto reads from Google. *Turn it off:* Features → Google Calendar → Turn off (Calendar keeps
its iCal links, if any).

### Mail digest by email
Each [mail digest](#mail-digest) also comes to your own inbox, sent from your Gmail to yourself (subject "Mail
digest, Tue 20 Oct 18:00"). With [several accounts](#several-google-accounts) it can send from another one than the
digest reads: a personal account, say, while the digest reads a school one. It always goes to the sending account's
own address; there's no way to give it another recipient. A digest that mentions confidential material anywhere
(beyond its own "Confidential: 2" count) isn't emailed; you get it on Telegram only, and a note saying so.

*Leaves:* the digest's text, from your Gmail to your own inbox. *Turn it off:* Features → Mail digest by email → Turn
off.

### Drive upload
Files you send yourself go to a folder of Kurooto's own in your Google Drive, **Kurooto**, and the link comes to you
(an **Open in Drive** button). `kurooto send lecture.mp4 --to drive` sends one there; the AI can too (send_file with
`to` = drive); anything bigger than Telegram's 50 MB goes there by itself (`drive_upload.big_files`). Big files go up
in pieces in the background; the link comes when it's done. Google's permission covers only the files Kurooto makes,
so it can't see the rest of your Drive, and nothing is shared: the link opens only for you.

*Settings:* `drive_upload.folder` (`Kurooto`), `drive_upload.big_files` (on).
*Leaves:* the files you send, to your own Drive. *Turn it off:* Features → Drive upload → Turn off (the files stay in
Drive until you delete them).

| Feature | What changes | Undo |
|---|---|---|
| Several Google accounts | another sign-in kept in your keychain; `google.accounts`, `google.use` | `/google forget <name>`; myaccount.google.com/connections |
| Google Calendar | Calendar reads Google's API; turns Calendar on | Features → Google Calendar → Turn off |
| Private events as Busy | titles of private events aren't kept or told | `calendar.mask_private` = `false` |
| Class calendars | those calendars' events are classes (no calls, after-class question) | `/cal classes none` |
| Mail digest by email | each digest also emailed to yourself | Features → Mail digest by email → Turn off |
| Drive upload | a Kurooto folder in your Drive; files over 50 MB go there | Features → Drive upload → Turn off; delete the folder in Drive |

### Handwritten notes
Drop a PDF or photo of handwritten pages into a folder (by default `handwritten-inbox` in your notes folder; set
`handwritten.folder` to one your tablet syncs to through Google Drive, OneDrive or Dropbox). Kurooto writes it out as
a Markdown note with the maths in LaTeX, saved in `handwritten/` next to a copy of the original (the copy goes to your
files folder when you set one; `handwritten.keep_original` = `link` makes no copy and links to the file where it is).
It looks every 15 minutes; `/handwritten` does it now, `/handwritten status` says how far it got, `/handwritten retry`
tries files that failed again.

**Who reads the pages.** With Local models on, a model on your computer: the vision model on 12 GB graphics cards, or
on 8 GB cards the helper model (gemma4:e4b reads handwriting too); `handwritten.local_model` names another Ollama model
that reads pictures. Nothing leaves your computer then. Photos are read right away. PDFs are read **page by page at
night on the charger** (`handwritten.pdf_hours`, 23:00–07:00; empty: any time), each page kept as it's done, so
unplugging or the morning only pauses it and it carries on from the next page; you get one message when a PDF waits
for the night (`/handwritten` starts it now). It waits while the graphics card is busy with something else, and
writes out up to 60 pages per PDF (`handwritten.max_pages`). Drawing a tablet's PDF pages as pictures needs Poppler's
PDF tools (scanned PDFs don't). Without a model here, Gemini (your key) reads them; `handwritten.cloud` = `false` keeps
them on your computer: they wait for a model here.

**Your own notes in it.** Kurooto's part of the note sits between `<!-- kurooto:handwritten -->` markers. When you
change the original on your tablet, the same note is written again between the markers; what you wrote around them
stays. Machine transcriptions aren't checked: look at the original for anything that matters.

*Undo:* Features → Handwritten notes off; the notes and copies stay. `handwritten.local` = `false` goes back to Gemini
for everything.

### Books and PDFs
Your reference books and other PDFs, per subject, read at night into text your AI uses when it writes your course
notes, and cites by page.

**Add a book** in any of three ways:
- **Telegram:** send the PDF with a caption like `book for linear algebra` (or `linear algebra textbook`). It's moved
  out of your notes into that subject's books folder. Telegram lets bots fetch files up to 20 MB; bigger books go in
  the folder.
- **The dashboard:** Features → Books and PDFs: the PDF's place on this computer and its subject (a copy is made).
- **The folder:** drop PDFs into the subject's books folder. `/books folder linear-algebra` says where (and makes it).
  Books are never kept in your notes: with `files.folder` set they go in `<files.folder>/<subject>/books/`, otherwise
  in Kurooto's data folder (`books/<subject>/`); `books.folder` picks your own place (a folder per subject in it).

**Reading.** At 01:00, on the charger, Kurooto reads every new book page by page and picks the best way for each page:
1. the PDF's own text, when the page has a real text layer (Poppler's `pdftotext` if it's installed, otherwise
   Kurooto's built-in reader);
2. a scanned page: **Tesseract** OCR, if it's installed. Tesseract writes plain text: equations come out garbled,
   not as LaTeX;
3. without Tesseract, or for pages full of maths: a **vision model** on this computer (Local models, on computers with a
   graphics card of 8 GB or more), which writes the maths in LaTeX (`books.latex`: `maths`, `all` or `never`);
4. **Gemini** only if you turn on `books.gemini`: pictures of pages nothing on this computer could read go to Google
   with your key. Books may be copyrighted, so this is off by default.

It stops at 07:00 (`books.until`), when you unplug or with `/books stop`, and carries on the next night from the page
where it stopped. Pages no reader could handle wait, and are read once one is there (`/books setup` installs
Tesseract). Encrypted PDFs need Poppler's PDF tools: your package manager's `poppler-utils` on Linux, `brew install
poppler` on a Mac, or poppler.freedesktop.org.

**What it makes:**
- the text with page markers (`## [p. 123]`), in Kurooto's data folder (`book-text/<subject>/<book>/text.md`), outside
  your notes;
- an index note in your notes, `<subject>/books/<book>.md`: the title, the chapters with their pages (from the PDF's
  bookmarks, or "Chapter 3 …" headings), how each page was read and links to the original. Kurooto writes only between
  its two markers; your own notes around them stay;
- with the Notes brain on, the text in the brain too (`books/<subject>/<book>/…`), so `/notes` finds book pages.

Page numbers are the PDF's own (p. 1 is the first page of the file, often the cover).

**The source mix.** When the AI writes course notes (`/study-log`, Classroom → notes, `/exam-prep`, `/pack`,
`/add-to-notes`), it asks for a subject's material with the `course_sources` tool: your **books** (the pages on the
topic), **Classroom** materials (posts and the files Classroom → notes downloaded) and your **own** class notes (notes
you wrote, the class log, and the "My notes" part of lecture notes). How much each counts is yours to choose:
- `/books mix linear-algebra book 30 classroom 30 own 40` (shares, any numbers);
- `/books mix linear-algebra prefer own book classroom` (an order: the first counts most);
- `/books mix linear-algebra` shows it; `/books mix linear-algebra reset` goes back to the general mix.

Only the sources a subject has are used, and their shares grow to fill the room the others leave. The notes cite each
part: (book: Linear Algebra, p. 123), (Classroom: Problem set 3), (your notes: [[linear-algebra/2026-10-12-eigen]]).
Your own words are quoted, never reworded; notes the AI writes carry its header (`made_by`, or `trust_tier:
agent_written` in the zettelkasten layout).

- `/books`: your books per subject and how far reading got; `/books read now` starts now (on the charger).
- `/exam-prep linear-algebra`: brings that subject's exam prep up to date from all three sources (also without
  Classroom).

*Settings:* `books.at` (`daily 01:00`), `books.until` (`07:00`), `books.ocr` (`auto` | `tesseract` | `vision` |
`off`), `books.ocr_lang` (`eng`; e.g. `eng+deu`), `books.latex` (`maths`), `books.gemini` (off), `books.dpi` (200),
`books.brain` (on), `books.max_mb` (400), `books.folder`; `sources.mix`, `sources.prefer`, `sources.cap` (characters
from each source at most), `sources.budget` (24000), `sources.subjects` (per subject; `/books mix` sets it).
*Leaves:* nothing while reading, unless you turn on `books.gemini` (page pictures to Google). Excerpts of your books,
Classroom materials and notes go to the AI you picked when it writes your notes.
*Turn it off:* Features → Books and PDFs → Turn off: reading stops after the current page; books, their text and the
index notes stay.
*Undo:* delete a book's PDF from its folder; its index note (`<subject>/books/<book>.md`) and its text
(`book-text/<subject>/<book>/` in the data folder) are then yours to delete, Kurooto never deletes them. `/books mix
<subject> reset` undoes a subject's mix; Settings → `sources` resets the general one. Tesseract installed by
`/books setup` is removed like any program (winget uninstall or Homebrew on a Mac).

### Study tracker
How long you spend on each subject, counted from the window you're working in: a window whose title names a subject
(its name or a short name, a PDF called `linear-algebra-week3.pdf`, a note in that subject's folder) counts while
you're at the computer: not idle for 5 minutes (`study.idle_min`) and the screen not locked. Only minutes per subject
are kept, never window titles. Works on Windows, macOS (it asks once to see
window titles) and Linux on X11, Hyprland or Sway. Needs Subjects.

- **Away from the computer:** `/study la 50` (or "starting linear algebra for 50 min") starts a session; `/study
  stop` (or "done studying") ends it, and a timed one ends by itself with a nudge to take a break. While a session
  runs, the window doesn't count. Afterwards: `/studied 2h linear algebra` or "studied stats for an hour", or tell
  the evening call.
- **How much:** `/study` (today), `/study week`, "how much did I study today?".
- **In your notes:** at 23:45 the day's hours go into your daily note as "## Study hours" (`study.daily_note`; empty
  to turn it off).
- **How it tells you're away:** Windows and macOS from the system's last-input time; Linux from your desktop (X11,
  GNOME, KDE, logind's idle hint). On Hyprland, Sway and other Wayland desktops without an idle API it watches for
  change instead (keyboard and touchpad activity, the cursor on Hyprland, the focused window; nothing you type is
  read). A locked screen never counts (hyprlock, swaylock and other lockers, or your desktop's lock).
  `kurooto doctor` says how this computer tells you're away.
- **Your idle tool can tell it** (more exact on Wayland): `kurooto idle away` when you go idle, `kurooto idle back`
  when you're back. hypridle, in `~/.config/hypr/hypridle.conf`:
  ```
  listener {
      timeout = 300
      on-timeout = kurooto idle away
      on-resume = kurooto idle back
  }
  ```
  swayidle: `swayidle timeout 300 'kurooto idle away' resume 'kurooto idle back'`.
- **Research:** a window naming one of `study.research_paths` (words, or folders matched by their name, e.g.
  `~/code/flow-model`) counts as **Research**; with Research on, its projects and repository folders count too.

*Settings:* `study.idle_min` (default 5), `study.research_paths` (default empty), `study.daily_note`.
*Undo:* empty `study.research_paths`; remove the idle hook lines (and run `kurooto idle back` once).

### Research
A digest of new papers in your fields, on Telegram, weekly by default. Set it up on the dashboard's **Research** tab:

1. **What I work on:** a sentence or two. With Chat on, the AI uses it (and your notes) to pick the most relevant
   papers and say why each matters to you.
2. **Your sources:** start from a **quick pick** (machine learning, astrophysics, neuroscience, economics,
   epidemiology and more), or add your own:
   - **arXiv:** pick any of its 155 fields (mathematics, physics, computer science, statistics, quantitative biology
     and finance, economics, electrical engineering); type in the box to find one.
   - **bioRxiv / medRxiv:** biology and medical preprints, by subject area.
   - **PubMed:** published biomedical papers for a search (PubMed's own search words work).
   - **A journal's or blog's feed:** paste its RSS or Atom address (most journals have one).

   Add keywords to any source to keep only papers that mention them. **Preview** shows what a source would find this
   week before you add it.
3. **The digest:** daily or weekly (which day, what time), how many papers, and whether the AI picks. **Send a digest
   now** tries it.

On Telegram: `/papers` (the digest now), `/feeds` (your sources), `/topics add …` (quick keywords searched across all of
arXiv).

**arXiv in its own words.** A source in `research.feeds` can be a search written the way arXiv's API takes it, with a
name that heads its part of the digest: `{"type": "arxiv", "name": "Molecules", "query": "abs:\"graph neural
network\" AND (abs:molecule OR abs:protein)"}` (`ti:` title, `abs:` abstract, `all:`, `cat:`, with `AND`,
`OR`, `ANDNOT` and brackets; add `categories` to narrow it). Several arXiv sources are fetched three seconds apart, as
arXiv asks. **A copy in your notes:** `research.save_note` = `true` also keeps each digest as a note in your inbox,
`inbox/papers-<date>.md`, every new paper grouped by source with its first lines; keep what matters, delete the rest.
*Undo:* `research.save_note` = `false`; take a search out of `research.feeds`.

**Projects:** each project has a note in your notes, `research/<project>/index.md`, and `research/index.md` lists
them all. Add your code repositories on the Research tab or with `/repos add ~/code/my-model`; a repository's project
is its folder's name, or name it: `/repos add ~/code/model_v2 as Climate model` (several repositories can share a
project; `research.projects` in Settings holds the mapping). `/repos remove <folder>` takes one off. Every night each
day's new commits become one line under `## Log` in the project's note, e.g. `- **2026-10-20** | git:my-model — 3
commits: …`. Kurooto only adds lines: your own text in these notes is never changed. (Logs from 0.1.0 in
`research/<repository>-log.md` are left as they are.)

**Quiet projects:** when a project has had no commits or runs for 4 days (`research.idle_days`; 0 never asks),
Kurooto asks once, at 18:00, what's up: **Busy**, **Working off-git**, **Remind me tomorrow** (with Phone calls on, a
call the next day at 18:00, and a message if you miss it; otherwise a message then; `research.remind_by_call` =
`false` always makes it a message) or **Pausing it**. The answer goes into the project's log. It asks again only after
the next quiet stretch.

**Experiment runs (`kurooto runlog`):** log a training or simulation run into the project's notes, with the code's
exact state:
```
kurooto runlog start my-model --name lr-sweep --config '{"lr": 0.001}'
kurooto runlog metric loss=0.31 acc=0.88 --step 100
kurooto runlog note "diverged after step 800"
kurooto runlog end            # or --status failed
kurooto runlog ls
```
Each run is a folder `research/<project>/runs/<date>-<time>-<name>/` with `run.md` (what it was and how it went),
`config.json`, `meta.json` (git commit, branch, whether there were uncommitted changes), `diff.patch` (those changes,
so the exact code can be recovered), `metrics.jsonl` and `notes.md`; a row in `runs/index.csv`; and a line in the
project's log when it ends. The commands find the run from `--run <id>`, else `$KUROOTO_RUN`, else the one you started
last. It works without Kurooto running.

**From Python:** a run is a `with` block, and it ends as `ok`, `failed` (an exception: its traceback goes into
`meta.json` and `notes.md`, and the exception still stops your script) or `interrupted` (Ctrl+C):
```python
from kurooto.runlog import Run

with Run("lr-sweep", config={"lr": 1e-3}, project="my-model") as run:
    for step in range(n_steps):
        run.log(step=step, loss=loss)
    run.note("diverged after step 800")
```
With `project=` (or `$KUROOTO_PROJECT`) the run goes into your notes as above. Without one it stays in your code: a
`runs/` folder where the script starts (`$RUNLOG_DIR` to put it elsewhere), with the same files plus the host, Python
version and command line, and a row in `runs/index.csv`. **Runs kept in a repository** you added with `/repos add` are
read every night: each new row of its `runs/index.csv` becomes a line in the project's log, e.g. `- **2026-10-20** |
run:my-model/20261020-101500-lr-sweep — ok after 41m10s (step=900, loss=0.12)` (the first time, only the last 30
days'). `research.repo_runs` is that folder's name (`runs`; empty: don't read them). *Undo:* empty
`research.repo_runs`; the lines already in your notes stay.

**Long jobs (`kurooto watch`):** `kurooto watch -- python train.py --epochs 50` runs the command (its output still shows
in your terminal) and messages you when it ends: done, failed or stopped, the exit code, how long it took and its last
10 lines (`--lines 0` sends none). `--log my-model` also logs it as a run of that project (the job gets `$KUROOTO_RUN`,
so it can add metrics). If Kurooto isn't running, it shows on this computer only.

*Leaves:* your fields, keywords and searches go to the sources you pick (never your notes); `kurooto watch` sends its
message through Telegram, like any message.

### Terminals
Real terminals in the dashboard's **Terminals** tab: the AI program you use (when your AI is agy, Codex or Claude
Code), started in your notes folder as you'd run it yourself; your usual shell (PowerShell on Windows); `kurooto ask`
(plain English, like Telegram); and Kurooto's log. Alt+1, Alt+2 and so on switch between them. They keep running when
you close the page and show where they were when you open it again; one that ended starts again when you press a key
in it (or **restart**).

**Only turn this on if you're the only person who uses this computer:** anyone who can open your dashboard can type
into these terminals. The dashboard only answers this computer, needs a key only its own page gets, and refuses other
websites; on Linux it also checks that every request comes from your own user account (see
[The dashboard](#the-dashboard)).

*Turn it off:* Features → Terminals → Turn off (the terminals end).

### Kurooto Terminal
Kurooto in a real terminal window of its own, laid out like the dashboard's terminals: one tab each for your AI's own
program (agy, Codex or Claude Code, started in your notes folder; agy if you have it and your AI is an API key), your
shell, Kurooto chat (`kurooto ask`) and Kurooto's log, with `kurooto top` as a column on the left of the first tab.
Everything is in Kurooto's colours (Settings → `look.palette`). The chat tab shows Kurooto's name, a few examples and
a `kurooto ❯` prompt; type plain English as on Telegram.

**Open it:** `kurooto term`, or **Kurooto Terminal** in your app menu (Start menu, Launchpad, your Linux app launcher)
once the feature is on. `kurooto term --shell` opens just your shell in Kurooto's colours (also **Kurooto Shell** in
the Linux app menu, and Windows Terminal's **Kurooto** profile). `kurooto term --print` shows what it would open
without opening anything.

| | What it uses |
|---|---|
| Linux, macOS | **kitty**: yours if you have it; otherwise `kurooto term` offers once to get the official kitty into Kurooto's own folder (about 45 MB to download; no admin; checksum checked). Alt+1 to Alt+9 switch tabs on Linux, Cmd+1 to Cmd+9 on a Mac. Your own `kitty.conf` is read first (your fonts and keys stay) and never changed. Without kitty, each tab opens in a window of your usual terminal. |
| Windows | **Windows Terminal** (built into Windows 11; free in the Microsoft Store for Windows 10). Turning the feature on adds Kurooto's profiles and colour scheme to Windows Terminal (no admin): the **Kurooto** profile is PowerShell in Kurooto's colours, and Kurooto chat, top, logs and your AI are in Windows Terminal's new-tab menu too. Without Windows Terminal, each tab opens in a console window of its own. |
| The shell | **fish** if you have it; otherwise `kurooto term` also offers once to get the official fish into Kurooto's folder (Linux: 3 MB; Mac: the 17 MB fish app, unpacked there, not installed system-wide). If you say no, your own shell (PowerShell on Windows). |

`kurooto term --install` gets kitty and fish any time; so does **Set up** on the card when there's no terminal
program at all. `kurooto term -e CMD` opens one window in Kurooto's colours running CMD.

**Settings** (Settings → Kurooto Terminal, once it's on): `tabs` (in order; any of `agent`, `shell`, `chat`, `logs`,
`top`), `top` (`left`: a column beside the first tab; `tab`: a tab of its own; `off`), `shell` (`auto`, or a program
such as `zsh` or `pwsh`), `font_size`, `kitty` (Linux and macOS; off: your usual terminal, a window per tab),
`default`, and `default_opens` (what opening "a terminal" gives you while Kurooto is your default: `shell`, just your
shell in Kurooto's colours, or `layout`, the whole window; `kurooto term` always opens the whole window).

**Make Kurooto my default terminal** (off unless you turn it on: Settings → Kurooto Terminal → `default`, or
`kurooto term --default on`):

| | What changes | Undo |
|---|---|---|
| Linux | **Kurooto Shell** (or Kurooto Terminal, with `default_opens` = `layout`) goes first in `~/.config/xdg-terminals.list`, the list `xdg-terminal-exec` reads (newer GNOME and many window managers' "open a terminal" use it). Your desktop's keys and window manager config aren't touched: bind a key to `kurooto term --shell` or `kurooto term` yourself (GNOME: Settings → Keyboard → Custom Shortcuts; KDE: System Settings → Default Applications → Terminal Emulator → Kurooto Shell; Hyprland, Sway, i3: your own config). | `default` off, or `kurooto term --default off`: the list goes back exactly as it was (or just Kurooto's line comes out, if you've changed the list since). |
| Windows | Windows Terminal's default profile becomes **Kurooto** (your shell in Kurooto's colours: a profile is one tab, so `default_opens` doesn't apply), after a backup of Windows Terminal's `settings.json`. | `default` off, or `kurooto term --default off`: `settings.json` goes back from the backup (or just the default profile, if you've changed other settings since; if you've picked another default yourself, it's left alone). |
| macOS | macOS has no default-terminal setting: Kurooto Terminal is in your Applications folder; keep it in the Dock. | nothing to undo |

Backups of anything Kurooto changed are in the state folder, under `terminal/backups`. `kurooto term --default
status` says whether it's your default.

*Turn it off:* Features → Kurooto Terminal → Turn off. The app-menu entries and Kurooto's Windows Terminal profiles
are removed and "default terminal" is undone. kitty or fish that Kurooto got stay in its folder (they go with `kurooto
uninstall`). Nothing about this feature leaves your computer.

### Your add-ons
Your own extra features, skills and prompts, from a folder of yours: for example a private repository you cloned, so
you can keep things for yourself while running the normal Kurooto. Turn on **Your add-ons** and paste the folder's full
path. The folder may have:

| | What it does |
|---|---|
| `modules/*.py` | extra features: classes based on Kurooto's `Module` (see `src/kurooto/modules/base.py`). They're listed in the dashboard's Features tab under **Your add-ons**, each off until you turn it on. Files starting with `_` are helpers they can import (`from kurooto_addons import _helpers`). |
| `skills/<name>/SKILL.md` | extra skills, written like Kurooto's own; a skill of the same name in your notes (`kurooto/skills/`) still wins |
| `prompts/*.md` | extra prompts; `/prompts` lists them as `add-ons/<name>` |
| `settings.json` | default settings laid under yours, e.g. `{"checkins": {"evening": "21:30"}}`; what you set yourself still wins (it can't turn features on) |

A feature can name programs that are its own work, including ones Kurooto didn't start: `processes = ("my-bot",
"bots/reply.js")` on the class (a program's name, or a piece of its command line). Its cell on the dashboard and its
line in `kurooto top` then show their cpu, memory, uptime and threads, and turn grey ("not running") when none runs.
For programs that only run now and then (a backup run, a nightly job), add `processes_intermittent = True`: with none
running the cell says "idle" (not grey), and "running" with the figures while one runs; the feature's own `health()`
still says whether something is wrong.

**This runs your own code:** the Python files run inside Kurooto with its access to this computer. Only use add-ons you
wrote or trust. `overlay.code` off keeps the skills, prompts and settings and skips the Python. A broken add-on never
stops Kurooto: a file that fails to load is skipped, and an add-on that fails while running is cut off from that one
request; both are logged and shown by `/addons` and `kurooto doctor`. The folder can't be inside Kurooto's own folders,
and updates never change it. Restart Kurooto after editing their code.

**What an add-on feature can plug into,** besides commands, buttons, intents, tools and settings (the details are at
the top of `src/kurooto/core/overlay.py`):

- `classify_intent(text, intents)`: picks which plain-English request a message is, before Kurooto's own patterns try
  (for example a small local model that understands how you talk). It gets the message and the requests that are on,
  and answers with a request's name (and, if it likes, its details and how sure it is). Kurooto only uses an answer
  that names a request that's on, is at least 60% sure, and comes within 2 seconds (`classify_timeout` changes that,
  up to 10); anything else, or an error, falls through to the usual patterns. Long messages and several requests in
  one still go to the AI, and questions only go to requests that answer questions.
- `status_lines()`: extra lines at the end of `/status`.
- `doctor_checks()`: extra lines for `kurooto doctor`, each `(name, ok, detail)`; a failing one counts as a problem.

*Turn it off:* Features → Your add-ons → Turn off; the add-ons are unloaded and their folder stays as it is.

### From a terminal or a script
Scripts and other tools on your computer can reach you through Kurooto (Telegram, the phone app, the desktop, however
you set it up):

- `kurooto notify --title "Backup" "The backup finished."` sends you a message. If Kurooto isn't running, the message
  only shows on this computer, and the command exits with 2. `--kind` sets what it is (`info`, `result`, `reminder`,
  `deadline`, `question`, `approval`: that decides where it shows, as in Settings → notify; `approval` and `--urgent`
  get through focus). `--button "Rerun=runs:42:again"` adds a button (one row each, up to 8): after the `=` either a
  web address, or `prefix:ref:action` for a feature (or one of your add-ons) that handles that prefix; `--click URL`
  adds an **Open** button for a link. `--print-id` prints the Telegram message's id, and `--reply-to ID` sends the
  next message as a reply to it.
- `kurooto send report.pdf --caption "This week's numbers"` sends a file from this computer to your Telegram (up to
  50 MB; exit code 2 when Kurooto isn't running). `--to drive` puts it in your Google Drive instead and sends the
  link ([Drive upload](#drive-upload); bigger files go there by itself). With Skills on, the AI can send you files from your notes folder too
  ("send me my linear algebra pack"), on calls as well; it can't send files from anywhere else.
- `kurooto note "an idea"` saves a quick note (see [Quick notes and prompts](#quick-notes-and-prompts)).
- `kurooto ask-me "Which folder should the photos go in?" --choices "camera|screenshots"` asks you something (see
  [Questions and approvals](#questions-and-approvals)); it prints the question's id and returns. Add `--wait` (and
  `--timeout 30`, in minutes) to wait and print your answer. `--expires 6h` changes how long it stays open; `--title
  "Backup"` replaces the "Question" label. `kurooto ask-me --pending` lists the questions still open (`--json` for
  programs); `kurooto ask-me --id <id> --wait` waits for the answer to one asked earlier (a timeout leaves it open).
- `kurooto ask-me "Log today's study?" --choices "yes|no" --then "my-logger --answer {answer} --question {id}"` runs
  a command with your answer once it comes, like a hook. Without `--wait` a copy of the command waits in the
  background (until the question expires; it outlives the terminal) and prints the question's id now; with `--wait` it
  waits here, prints the answer, runs the command and exits with its exit code. The command runs as a program with
  its arguments, never through a shell, so an answer like `a; rm -rf ~` is just text in one argument; quotes keep
  spaces together, or give a JSON list (`--then '["my-logger", "{answer}"]'`). Only this command starts it: nothing
  from Telegram, a call or the AI can attach a command to a question. A follow-up that fails messages you; its output
  is in `ask-then.log` in the logs folder (`kurooto paths`). *Undo:* nothing to undo; a waiting copy ends when the
  question is answered or expires.
- `kurooto ask-approval "Delete last month's build folders?" --timeout 30` waits for Approve / Deny: it prints `yes`,
  `no` or `timeout` and exits with 0, 1 or 2. Use it in scripts before anything that needs your OK. If Kurooto isn't
  running, `ask-me` and `ask-approval` exit with 2 and nobody is asked.
- `kurooto ask "what's due this week?"`: plain English, as on Telegram. Quick things (reminders, holds, what's due,
  /commands) answer at once; anything bigger goes to your AI and its answer prints here, not on Telegram. `kurooto ask`
  alone opens a prompt where you type one request after another. `--no-wait` prints the request's id; `kurooto ask
  --job <id>` waits for its answer later.
- `kurooto call "the backup finished"`: rings your phone (needs Phone calls). It waits out your no-call rules
  (classes, /hold, focus, night) and calls when they end; `--force` rings now anyway, `--alarm` rings as a wake-up
  alarm, `--at 17:30` (or "in 20 min", "tomorrow 7:00") calls later. Nothing ever rings while you're on a call.
  `kurooto call --list` shows the calls booked for later with their keys, and `kurooto call --cancel <key>` takes one
  off (your call line forgets it too). Check-ins and the alarm have their own commands (`/checkins`, `/alarm`).
- `kurooto mcp`: Kurooto's tools for agent programs (see
  [What the AI can do](#what-the-ai-can-do-its-tools)). Without Kurooto running, it tells the agent so.
- `kurooto autostart boot|login|status`: start before anyone logs in (Linux), or at login; `status` says which (see
  [Starting at boot](#starting-at-boot)).
- `kurooto idle away|back`: for your idle tool, you've stepped away or you're back (see
  [Study tracker](#study-tracker)).

`kurooto ask` and `kurooto call` need Kurooto running (`kurooto on`).

## Your phone

### Android (recommended)
The Kurooto app rings like a real phone call (full screen, even on the lock screen), uses the earpiece with the screen
off at your ear, rings wake-up calls on the alarm volume, shows Kurooto's questions and approvals with a Reply box, and
lets you share files to your notes. It works from Android 6.

1. On your computer: dashboard → **Phone** → **Pair a phone** (or send `/phone` to your bot and open the link on your
   phone).
2. Scan the QR code with your phone's camera. The page offers **Download the app**: open the file and tap Install.
   - *"For your security, your phone isn't allowed to install unknown apps":* tap Settings and allow it for your
     browser. Kurooto isn't on the Play Store.
   - *Play Protect warns:* tap "More details" → "Install anyway".
3. Back on the page, tap **Pair the app**. The app opens, pairs, and shows a checklist.
4. Fix every ✗ on the checklist: notifications, microphone, full-screen calls (Android 14+), and **Battery:
   unrestricted**. On Samsung, Xiaomi, Oppo, Vivo, OnePlus and Huawei phones, also take Kurooto off any "sleeping
   apps" list in Settings → Battery, or calls may not ring.
5. Test: dashboard → Phone → **Ring my phone**.

The app checks for a new version once a day and shows an **Update** button; it opens the download.

### iPhone
iPhones use Kurooto as a web app on the Home Screen (iOS 16.4 or newer).

1. Pair as above, but open the page in **Safari**.
2. Tap Share → **Add to Home Screen** → Add.
3. Open **Kurooto from the Home Screen** (not from Safari): it finishes pairing.
4. Tap **Turn on notifications** and allow them (calls, questions and approvals arrive this way).

**What doesn't work on iPhone:** calls arrive as notifications you tap to answer; they can't ring like a phone call,
ring on silent, or show on the lock screen as a call. If you need those, use Telegram reminders or an Android phone.

## The dashboard

`http://127.0.0.1:8770` (or `kurooto open`). STATUS shows your computer; SYSTEMS shows each feature as a living cell
that pulses when something happens; NOTES is a map of your notes and their links (click a note to read it). The tabs:
**Activity** (what happened), **AI jobs**, **Schedule** (what's coming), **Features** (turn on/off, set up), **Phone**
(your call line, pairing, a test ring), **About you** (your profile, to edit; `/#about` opens it), **Settings**
(every setting, with what it means), and **Terminals** (when the [Terminals](#terminals) feature is on).

**Two layouts** (Settings → `look.layout`). **dense**, the default on a screen 1280 px wide or more, is one full-screen
board with thin borders and each pane's name set into its top line:
- **STATUS**, down the left, is a monitor like btop, the same as `kurooto top`: the processor (a history graph, every
  core with its own short graph, speed, load, temperatures, fans), memory (used, cached, available, swap), the
  graphics card (use, its memory, temperature, power, a graph), the network (down above the line, up below, totals),
  disks (how full; reads and writes per second), the battery, the busiest processes (click **cpu** or **mem** to
  sort; Kurooto's own are marked ✦), **study today** (with the Study tracker on) and **projects**: your git folders
  with each one's last commit, what's not pushed yet and what's changed (list them in `look.projects`; Research's
  repositories otherwise). Its header has the time, how long the computer's been up, today's events, the battery,
  and pause, off and setup.
- **SYSTEMS** keeps the cells round the core, with the hours of the day on the ring and four corners: recent events,
  your AI's latest requests (with the local models and what's scheduled next), **today** (classes, calendar,
  check-ins, calls, focus and no-call holds) and **due** (overdue ones in red). A feature that runs programs of its
  own shows their cpu, memory, uptime and threads on its cell (grey and dashed when none is running); the others
  show what they did last and when they run next. Each cell's words sit just outside it, away from the core; on a
  crowded ring they move a little (with a hairline back to their cell) or say less, and never cover each other
  (on a very small screen a few may hide: hover over a cell for its card).
- **NOTES** adds your folders with their note counts, whether anything was touched this hour, and the notes you
  edited last. Double-click a note on the map to open it: in your default app for Markdown, or in your own program
  with Settings → notes → `open_with`, e.g. `kitty nvim {path}`, `code {path}` or `kurooto term -e nvim {path}` (on
  every system; the program has to open its own window). It runs as a program with arguments, never through a shell;
  `{path}` is the note (one argument even with spaces), `{folder}` your notes folder, and without `{path}` the note
  goes at the end. If the program isn't there, the default app opens the note. *Undo:* empty `notes.open_with`.
- **TERMINAL**, below, has its tabs in its border: your AI's program, a shell and the log (with Terminals on), and
  **kurooto**, plain English as on Telegram, right in the page (`help`, `check`, `jobs` and `clear` are its own
  words; ↑ and ↓ bring back what you typed). The other pages (activity, jobs, schedule, features, phone, research,
  you, settings) are in the same border. **Alt+1**, **Alt+2**… switch the terminal tabs; **Alt+/** (or `/`) finds
  a note.

**roomy** is the earlier layout, with bigger panes and type; a narrower window gets it by itself. `look.layout =
roomy` keeps it everywhere.

The **morning page** (`http://127.0.0.1:8770/morning`) shows today's plan from your daily note, with your classes,
calendar, what's due, check-ins and open questions. The alarm opens it.

**Colours:** Kurooto's pages (the setup page, the dashboard, the morning page, and your call line's pages on the phone)
use deep greens, like the website. If you liked the earlier pink and rose colours better, set Settings → Look →
`look.palette` to `rose` and reload the page; `kuro` (the default) brings the greens back. The setup and morning pages
follow your system's light or dark mode; the dashboard is always dark. Your call line's pages on the phone stay green.

Only your computer can open the dashboard; it needs a key that only this computer has. On Linux, where several people
can be signed in to one computer at once, it also checks that the page and every request come from your own user
account, and refuses them when it can't tell.

**In a terminal:** `kurooto top` is the same board in any terminal (Windows 10 and later, macOS, Linux), laid out like
btop: this computer (a processor history graph and every core, speed, load, temperatures and fans, memory and swap,
the graphics card, the network's down and up graphs, disks, the battery, the busiest processes) beside Kurooto
(running or not, the battery mode, the call line and its heartbeat, Kurooto's own process and the features' programs,
today, what's due, AI requests, what's next, study today, projects, recent events), with lights for Kurooto, Telegram
and the call line, today's event count and a trace that beats with each event. `q` quits, `r` refreshes, `c` and `m`
sort the processes by cpu or memory. `kurooto top --once` prints one screen. Its colours are your palette, in true
colour where the terminal has it (`NO_COLOR=1` turns them off). What a computer can't tell is left out: most Windows
and Mac computers give no temperatures or fans, and the graphics card's live figures need NVIDIA's `nvidia-smi` (or
an AMD card on Linux); a laptop's sleeping NVIDIA card isn't woken to ask. It only reads, so it's safe while Kurooto
works. `kurooto logs -f` follows Kurooto's log.

## Colours (Look)

Kurooto's pages (the setup page, the dashboard and the morning page) come in three palettes. Pick one on the setup
page (step 2, **Colours**) or in **Settings → Look → `look.palette`**:

- **kuro** (the default): deep greens.
- **rose**: the pinks of earlier versions.
- **system**: this computer's own colours. Kurooto takes your desktop's accent colour and whether it's in light or
  dark mode, and follows them when they change (within half a minute, without reloading the page). It looks, best
  first:
  - **Linux:** Material You colours made from your wallpaper by matugen (end-4's Hyprland setup, Caelestia and
    others write them), pywal, then KDE's accent colour, GNOME's (GNOME 47 or later) and your GTK theme's (a
    libadwaita accent colour, or a dark theme).
  - **Windows:** the accent colour and app mode (Settings → Personalization → Colors).
  - **macOS:** the accent colour and appearance (System Settings → Appearance).

  When nothing is found, the pages look like kuro until something is. Settings → Look says what was found.

Text always stays readable: any colour that would be hard to read on its background is made lighter or darker until it
passes the WCAG AA contrast level (4.5:1).

**Your own colours file:** set **Settings → Look → `look.theme_file`** to the full path of a kitty theme (lines like
`background #1a1110` and `color4 #9ccaff`) or a matugen or pywal `colors.json`. It's used instead of the desktop's
colours, and switches the palette to system. Kurooto says so if it can't find colours in the file.

The dashboard is always dark (with the system palette, its dark version); the other pages follow light or dark mode.

*Settings:* `look.palette` (`kuro`, `rose` or `system`; default `kuro`), `look.theme_file` (empty).
*Leaves your computer:* nothing. Kurooto only reads the colour settings and files above, on this computer.
*Undo:* press **Kuro** on the setup page's step 2, or set `look.palette` back to `kuro`; empty `look.theme_file`.

## Taking your laptop with you (battery, pause, off)

**On battery**, Kurooto saves your battery by default: everything that leans on the laptop waits for the charger,
and **Telegram keeps working**.

| Keeps working on battery | Waits until it's plugged in |
|---|---|
| Telegram: messages, commands, plain-English requests | Local AI models (unloaded, freeing the graphics card) |
| Reminders, check-ins, deadlines, the calendar | The notes brain's indexing and upkeep, Notes sync, Backups |
| Answers to what you ask the AI | Handwritten notes, Research, Classroom → notes, the nightly look back |
| Phone calls and the morning alarm; Profile sync (it's small) | AI work nobody asked for (e.g. the weekly paper picks, the mail digest) |

Nothing is skipped: the waiting work runs the moment you plug in (Kurooto checks every 30 seconds). Choose what
happens on battery in the wizard ("Your computer") or Settings → `power.on_battery`:
- **`saver`** (★ default): as above.
- **`normal`:** everything keeps running, as if plugged in.
- **`pause`:** everything pauses (see below) until you plug in.

**Pause by hand:** `/pause` (until you resume), `/pause 2h`, `/pause until 18:00` on Telegram, `kurooto pause 2h`,
or **Pause 1 h** on the dashboard. While paused nothing runs, but Telegram still answers: it says it's paused, keeps
what you send, and does it all when you `/resume`. Reminders due meanwhile arrive when it resumes. Your call line
keeps placing scheduled calls, so the morning alarm still rings.

**Turn it off completely:** `kurooto off`, or **Turn off** on the dashboard. Kurooto stops (with the local models it
started), doesn't start when you sign in, and your call line stops placing scheduled calls (`kurooto off
--keep-calls` keeps them, e.g. for the alarm). It stays off until you open **Kurooto** from your app menu (Start
menu, Applications, or your Linux app launcher) or run `kurooto on`; both also open the dashboard. Telegram doesn't
answer while it's off; messages sent meanwhile (up to a day: Telegram keeps them that long) are handled when it's back.

## Starting at boot

Kurooto starts when you log in. On Linux (with systemd) it can start when the computer does, before anyone logs in, so
Telegram and calls work after a power cut or a remote reboot:

- **Settings → Starting** on the dashboard, or `kurooto autostart boot`, turns on lingering for your account
  (`loginctl enable-linger`; it may ask for your password, or say to run that command yourself). Your keychain stays
  locked until you log in, so Kurooto's keys move to its owner-only settings file (`secrets.json`, readable only by
  your account).
- **When you log in** (or `kurooto autostart login`) goes back: lingering is turned off again only if Kurooto turned
  it on (if something else did, it says so and leaves it), and the keys go back to the keychain.
- `kurooto autostart status` shows which. The setting is `autostart.when`.
- Windows and macOS start Kurooto at sign-in only (Settings → Starting says so): starting before would need admin
  rights (and on Windows your password kept in a scheduled task). On a Mac that restarts by itself, automatic login
  brings Kurooto back.
- If your home folder is encrypted and only unlocked at login, starting at boot can't reach Kurooto's files.

*Undo:* **When you log in** in Settings → Starting, or `kurooto autostart login` (or `kurooto uninstall`, which also
turns off the lingering Kurooto turned on).

## Going offline and coming back

Kurooto tells you when it goes away and when it's back, on Telegram (on by default; nothing ever rings for this).

**What you'll see:**
- **A clean stop** (`kurooto stop` or `off`, the dashboard, signing out or shutting down the computer): just before it
  goes, "Kurooto is going offline (shutting down): calls and reminders will wait until it's back". With Phone calls
  set up it says "reminders will wait until it's back; your call line still places scheduled calls" instead. It takes
  at most a few seconds and never holds up a shutdown. An update's restart says nothing.
- **Sleep, a crash, a lost network or the power going:** your computer can't speak then. If Phone calls is set up,
  your call line notices the computer's link gone for 10 minutes and says it for it: "Kurooto has been offline since
  22:10 (asleep, off or without internet): ..." (on the phone app, and on Telegram once you allow it; see below).
  **Without Phone calls there's no message for sleep, a crash or a lost network**, only the "back" one afterwards.
- **Back:** when Kurooto starts, when the computer wakes up, and when the network works again: "Kurooto is back online
  (offline since 22:10, 7 h)", or "Back online: the network was down from 14:02 to 14:31 (29 min)", with what it
  caught up on (reminders that went out late, calls your call line placed meanwhile).
- **The network:** when Telegram (or your call line) can't be reached several times in a row while the computer is
  on, Kurooto counts the network as down from the first failure. Messages meanwhile are kept, and once the network is
  back they follow the "back online" message, in order, each marked "Delayed, from 14:05".

**Not every blip:** nothing for less than 10 minutes away (except right after a goodbye: you were told it went, so
you're told it's back). Several sleeps or drops close together give one message: it waits until the computer has
been up for a minute. At night (your night hours, or bedtime to the alarm) and in focus time it waits for the
morning; if nothing told you Kurooto had gone and it's back before then, it's dropped.

**Telegram from your call line:** for the line to tell you on Telegram while your computer can't, it needs your
bot's token. Kurooto asks once (Approve / Deny). Approve, and the token and your chat go to your call line on your
Cloudflare account (where your Gemini key already is); Deny, and only the phone app hears from the line (add `"app"`
to the channels).

**Settings** (Settings → `notify.presence`):
- `on`: `true` (default) or `false`.
- `after_min`: how long away before it counts (default 10, at least 1).
- `channels`: where the messages go: `["telegram"]` (default); add `"app"` for the phone app.
- `line`: your call line speaks while the computer can't (default `true`).
- `line_telegram`: may your call line keep your bot's token for that? `null` asks once; `true` or `false`.

**Undo:** `notify.presence.on` = `false` turns the messages off (the call line then says nothing either; messages kept
while the network was down are still delivered, marked as delayed, once it's back). To take the bot's
token off your call line, set `line_telegram` to `false`: it's deleted there at the next sync (within 5 minutes,
while your computer is connected). The dashboard's activity shows `presence_offline` and `presence_online`.

*Leaves:* the messages (Telegram, your own bot; the phone app through your call line). With Phone calls: your night
and focus hours for the next day and the message's wording go to your call line, and, only after you approve, your
bot's token and chat id.

## Kurooto keeps itself working

Every feature that's on has one health check, and Kurooto looks at all of them once a day. **It stays quiet unless
something is wrong**, and even then it only messages you when it matters now.

**What's checked** (only for features that are on):
- **Things that should keep happening:** Classroom synced within 26 hours, Calendar within 12, Notes sync and the
  Notes brain within 24, Backups and Profile sync within 72. Only the hours your computer was awake and Kurooto wasn't
  paused count: a shut lid, a shutdown, a network outage or a pause never makes a sync "late", and for work that waits
  for the charger, time on battery doesn't count either.
- **Sign-ins that ended or end soon:** your Google sign-in (a Google app still in Testing ends it every 7 days), the
  GitHub token Notes sync uses (expiring within 10 days; GitHub also emails you 7 days before), the Cloudflare login
  your call line's updates need, and a Telegram bot whose token was revoked.
- **Your call line:** this computer is linked to it and it answers.
- **Tonight's alarm:** it's planned, your call line has it and answers, and a phone is paired to ring.
- **Kurooto's own queues:** messages that waited for focus time or the network and never went out.

**When you hear about it:**
- **Tonight's alarm might not ring:** at once: "Your alarm at 07:00 might not ring: ... Set your phone's own alarm
  too."
- **Your Telegram bot stopped answering:** at once (on the desktop and the phone app, since Telegram can't).
- **A problem that could make you miss a deadline or exam in the next 48 hours** (Classroom, Calendar or your call
  line): one message now, with a **Fix** button when there's one.
- **Anything else** waits for the weekly summary ("Needs a look: ..."). With the weekly summary off, you get one
  message on Sundays instead.
- Each problem is told once; if it's fixed and breaks again, you hear again.

**Fixes.** Before telling you, Kurooto tries a fix that's safe to run unasked, then looks again ten minutes later.
There are five, all limited to Kurooto's own state, never your notes or other data:
- **Sync now:** runs that feature's sync once (what its timer does anyway). Only when you tap it.
- **Put its timers back:** a feature whose timers went missing gets them back.
- **Reconnect:** restarts this computer's link to your call line, or Telegram's reading of your messages.
- **Set the alarm again:** plans your daily alarm now (it's otherwise planned at midnight, which a sleeping laptop
  misses) and sends it to your call line.
- **Send them now:** sends messages stuck in Kurooto's queues.
A sign-in that ended has no fix Kurooto can do; the message says what to do. After you tap **Fix**, you hear ten
minutes later whether it worked.

**Where to look:** `/health` on Telegram (what's wrong, with Fix buttons; `/health now` checks online too), the
dashboard (a "needs a look" badge; the Features tab lists them with Fix buttons), `kurooto doctor` (a `working: ...`
line each; `kurooto doctor --fix <id>` runs a fix in the running Kurooto) and the weekly summary.

**Settings** (Settings → `health`):
- `on`: the daily pass (default `true`). `/health`, the dashboard and doctor check either way.
- `when`: when the daily pass runs (default `daily 21:00`, before bedtime, so tonight's alarm is checked in time).
- `auto_fix`: try the safe fixes before telling you (default `true`).

**Undo:** `health.on` = `false` stops the daily pass and its messages (nothing else changes); `health.auto_fix` =
`false` leaves every fix to your tap. The dashboard's activity shows `health_checked`, `health_fixed` and
`health_told`.

*Leaves:* nothing new. The checks ask services Kurooto already uses: Telegram whether your bot answers, GitHub whether
your notes token works (a read-only look at your notes repository), and your call line whether it's up and how many
phones are paired.

## Updates and going back

Kurooto updates itself. Settings → `updates.mode`:
- **night** (default): a new version is downloaded when found and switched to between 03:00 and 05:00, when the
  computer isn't busy and you're not on a call.
- **ask**: Telegram asks you (Update / Later / Skip).
- **off**.

Every release is signed; Kurooto refuses anything unsigned, older, or changed on the way. During your exams,
[Exam season](#exam-season) holds back every update that isn't marked critical (in its signed manifest) until the
exams are over. The previous two versions stay installed. If a new version crashes three times in its first five minutes, Kurooto goes back to the one before
and won't offer the broken one again; you're told on Telegram. `kurooto update --now` installs an update right away.

Your call line is updated after Kurooto updates, if its code changed. The Android app shows an Update button; the
iPhone web app updates itself.

## Moving to a new computer

With [Profile sync](#profile-sync) on (on the old computer):

1. On the old computer, if it still works: `/profile save` (or just wait for the daily save), then **turn Kurooto off
   there** (`kurooto off`): two computers can't share one Telegram bot or one call line.
2. Install Kurooto on the new computer. On the setup page's first step, press **I've used Kurooto before**, and give:
   the repository (`owner/name`), a token for it (lost it? make a new fine-grained token for that repository with
   Contents: Read and write), and your passphrase.
3. Kurooto restores your settings, keys and saved items, turns on every feature that's ready, and, with Notes sync,
   brings your notes back. It lists what's left to do here, then **Continue** walks you through it: sign your AI in
   again (agy, Codex and Claude Code keep their sign-ins on the computer they ran on), install what features need
   (Git, the notes brain, local AI models: Done installs them), and pick folders that were on the old computer
   (backup folder, add-ons folder).

From a terminal instead: `kurooto profile restore --repo owner/name` (it asks for the token and passphrase without
showing them, stops Kurooto, restores, offers to set up what's left, and starts it again). Before restoring, Kurooto
keeps a copy of the settings it replaces in its data folder (`profile/before-restore-<date>/`, the last three). A
restore never changes your notes; with Notes sync on and no notes on this computer yet, it brings them down from your
repository.

`kurooto profile status` says what's saved and when; `kurooto profile save` saves now (the first time, it asks for the
repository and a passphrase). Without Profile sync, a backup zip works too (`kurooto restore <zip>`, see
[Backups](#backups)).

## Your computer and Kurooto (hardware profiles)

| Profile | Example | Local models | Notes brain index |
|---|---|---|---|
| **light** | no graphics card, ≤ 8 GB memory, Intel Mac | none | Gemini (your key) or keywords |
| **apple-8** | Apple Silicon, 8 GB | embeddings only | on your Mac |
| **apple** | Apple Silicon, 16 GB+ | a small helper model + embeddings | on your Mac |
| **small-gpu** | a 4–6 GB graphics card | a small helper model (~4B) + embeddings | on your computer |
| **big-gpu** | 8 GB+ graphics card | a larger helper model + embeddings | on your computer |
| **big-gpu-12** | 12 GB+ graphics card | + a vision model (handwriting) | on your computer |

The main answers always come from the AI you picked; local models only take quick decisions and make the notes
index. Settings → **Your computer** shows what was found and lets you change it; `kurooto doctor` re-checks.

## Your notes: layout and files

Kurooto writes into your notes folder in one of two layouts, and can keep big files (photos, PDFs) out of it so they
don't fill your notes or their history. Both are settings: dashboard → Settings → `notes` and `files`.

**Layout** (`notes.layout`):

| What | `kurooto` (the default) | `zettelkasten` |
|---|---|---|
| Daily note (journal, plans, check-ins, study hours) | `journal/<date>.md` | `dailies/<date>.md` |
| Your profile, how to help you, not-interested topics | `about-me/` | `master/` |
| Recurring quizzes, ideas, your own skills | `kurooto/recurring.md`, `kurooto/ideas.md`, `kurooto/skills/` | `master/recurring-assessments.md`, `master/ideas.md`, `master/skills/` |
| A subject's course page | `<subject>/course.md` | `maps/courses/<subject>.md` |
| Lecture notes, exam prep, class log | `<subject>/` | `sources/<subject>/` |
| Concept notes (one idea each) | `<subject>/<idea>.md` | `zettel/<idea>.md` |
| Research projects and their runs | `research/<project>/`, hub `research/index.md` | `projects/<project>/`, hub `maps/research.md` |
| Mail digests | `mail/<date>-<time>.md` | `digests/mail-<date>-<time>.md` |
| Quick notes and loose ideas, prompts, handwritten notes | `inbox/`, `prompts/`, `handwritten/` | the same |

In the zettelkasten layout, notes Kurooto and the AI write start with `id` (the note's path), `aliases`, `tags` and
`trust_tier: agent_written` (your daily note and your quick notes don't get `trust_tier`: they're your words). Links
are `[[wikilinks]]` either way. The AI is told your layout, and skills written for the default one (`journal/<date>`,
`<subject>/course`) are translated when they run, yours included.

**Your own places** (`notes.paths`): any kind of note somewhere else, e.g. `{"daily": "diary/{date}.md", "ideas":
"plans/ideas.md"}`. The kinds are `daily`, `profile`, `how_to_help`, `not_interested`, `recurring`, `ideas`, `skills`,
`prompts`, `inbox`, `note`, `subject`, `course`, `class_log`, `lecture`, `concept`, `exam_prep`, `research`,
`project`, `runs`, `handwritten`, `mail`; the parts in braces are `{date}`, `{time}`, `{subject}`, `{project}` and
`{slug}`. A place that doesn't work (a part that doesn't exist, or `..`) falls back to the layout's own.

**Files folder** (`files.folder`): a folder outside your notes, for example `Documents/Kurooto files` or a folder your
cloud drive syncs. With it set, these go there instead of into your notes: photos and PDFs you send (`inbox/`),
after-class photos and files (`<subject>/`), revision packs, LaTeX and PDF (`<subject>/`), the originals of handwritten
pages (`handwritten/`) and new scans (`handwritten-inbox/`, unless you already have that folder in your notes or set
`handwritten.folder`), and Classroom's downloaded files (`<subject>/`). Notes link to them: relative links in the
kurooto layout, `file://` links in the zettelkasten one (`files.links`: `relative` or `file` to choose). Empty (the
default): files stay where they always were, inside your notes (Classroom's in Kurooto's data folder).

**Updating:** nothing changes until you set these; with the defaults everything stays where it was in 0.2. Changing
them affects new notes and files only: nothing is moved, so move existing notes yourself if you want them in the new
places (Kurooto then finds them there). Notes sync and Backups don't include the files folder: pick one your cloud
drive syncs, or back it up yourself.

**Undo:** set `notes.layout` back to `kurooto` and empty `notes.paths` and `files.folder`. New notes and files go to
the old places again; what was written in the meantime stays where it was put (nothing is deleted).

## Where things are

`kurooto paths` prints them. By default:

| | Windows | macOS | Linux |
|---|---|---|---|
| Settings | `%LOCALAPPDATA%\Kurooto\config` | `~/Library/Application Support/Kurooto/config` | `~/.config/kurooto` |
| Data | `%LOCALAPPDATA%\Kurooto\data` | `~/Library/Application Support/Kurooto/data` | `~/.local/share/kurooto/data` |
| Logs | `%LOCALAPPDATA%\Kurooto\state\logs` | `~/Library/Logs/Kurooto` | `~/.local/state/kurooto/logs` |
| The program | `%LOCALAPPDATA%\Programs\Kurooto` | `~/Library/Application Support/Kurooto/app` | `~/.local/share/kurooto/app` |
| Your notes | `Documents\Kurooto` | `~/Documents/Kurooto` | `~/Documents/Kurooto` (or `~/Kurooto`) |

| What | Where |
|---|---|
| Backups | the folder you picked (`backups.folder`); before a restore, a copy of how things were: `restore-safety/` in the data folder |
| Experiment runs | `research/<project>/runs/` in your notes (paths here are the default notes layout's: [Your notes: layout and files](#your-notes-layout-and-files)) |
| Watched jobs | `watch.log` in the state folder (time, exit code, duration, folder, command) |
| Kurooto Terminal | its kitty settings and tabs: `terminal/` in the state folder (made again every time); the app-menu entries: `~/.local/share/applications/kurooto-terminal.desktop` and `kurooto-shell.desktop` (Linux), `~/Applications/Kurooto Terminal.app` (macOS), Start menu (Windows); Windows Terminal profiles: `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\Kurooto` |
| Your own skills, ideas, recurring quizzes | `kurooto/` in your notes (`skills/`, `ideas.md`, `recurring.md`) |
| How you like to be helped, not-interested list | `about-me/how-to-help-me.md`, `about-me/not-interested.md` in your notes |

Secrets (bot token, keys) are in your system's keychain (Windows Credential Manager, macOS Keychain, or the Secret
Service on Linux), or, where there is none, in a file only your user can read in the settings folder.

Commands: `kurooto on` / `kurooto off` (completely, until turned on again), `kurooto pause [2h]` / `kurooto
resume`, `kurooto start` / `kurooto stop` (just for now), `kurooto open`, `kurooto doctor`, `kurooto top`, `kurooto
term`, `kurooto logs [-f]`, `kurooto sync`, `kurooto backup` / `kurooto restore <zip>`, `kurooto profile save|status|restore`,
`kurooto update`, `kurooto autostart on|off|status`, `kurooto paths`, `kurooto rotate`, `kurooto uninstall
[--revoke]`. For scripts: `kurooto
notify`, `send`, `note`, `ask`, `ask-me`, `ask-approval`, `call`, `mcp`, `runlog`, `watch` (see
[From a terminal or a script](#from-a-terminal-or-a-script) and [Research](#research)).

## Troubleshooting

| What you see | What to do |
|---|---|
| The bot doesn't answer | `kurooto doctor`; is it running? Turned off? `kurooto on` (or Kurooto in your app menu). Is the computer asleep? See Stay awake on charger. |
| The bot says it's paused | `/resume`; or it's on battery with `power.on_battery` set to `pause`: plug in, or choose `saver`. |
| "needs a look" on the dashboard, or a "Needs a look" line in the weekly summary | `/health` (or the Features tab) says what and offers a Fix button where Kurooto can fix it; a sign-in that ended needs you (the line says where). |
| "Your alarm ... might not ring" | Set your phone's own alarm for tonight, then: Phone calls set up and linked (`kurooto doctor`), a phone paired (Phone tab). The Fix button reconnects or plans the alarm again. |
| A reminder didn't reach my phone while the lid was shut | `kurooto doctor`: the "Reminders with the lid shut" line says what your call line holds and for how many phones. "No phone can open them yet": update the Android app and open it once. Also check the app's checklist (notifications, **Battery: unrestricted**) and that the phone was online. Reminders set in the last seconds before the lid shut on a Mac come when it wakes. |
| "Back online" every morning | Your laptop sleeps at night. Raise `notify.presence.after_min` past your night, or turn it off (`notify.presence.on` = `false`). |
| No "going offline" when the laptop sleeps | That message comes from your call line: it needs Phone calls set up, and Telegram from the line needs your OK (`notify.presence.line_telegram`); or add `"app"` to `notify.presence.channels`. |
| Building my profile failed | It's a big request: if your AI hit a limit, try again later or with a stronger AI (Settings → `brain.main`). |
| Something only happens when I plug in | That's the battery saver (Taking your laptop with you); set `power.on_battery` to `normal` to keep it all running. |
| The laptop still sleeps with the lid closed on the charger (Linux) | `awake.lid` is off, or your system refuses the lid hold to background programs (doctor says so). Allow it in polkit (`org.freedesktop.login1.inhibit-handle-lid-switch`) or set `HandleLidSwitchExternalPower=ignore` in logind.conf. |
| `kurooto autostart boot`: "Linux didn't allow that from here" | Run `loginctl enable-linger` in a terminal (it may ask for your password), then `kurooto autostart boot` (or Settings → Starting) again. |
| "I can't answer free text yet" | Turn on **Chat** (Features). |
| The AI says it isn't signed in | Setup page → AI → Install / sign in again → Test. |
| "It's at its usage limit" | Free tiers have daily limits: wait, or set a fallback brain (Settings → `brain.fallback`). `/usage` shows how often it happens. |
| "Google's free limit for today is used up" | It comes back at the time the message says. Meanwhile set a fallback brain (Settings → `brain.fallback`); calls and reminders still work. `/usage` shows each limit and when it resets. |
| The Classroom digest or the look back didn't come | Past 70% of a free limit, background work waits for the reset ([Free limits: the reserve](#free-limits-the-reserve)); `/usage` says how many requests wait. Raise `quota.background_pct`, or set `quota.on` to `false`. |
| The setup page says agy "can't use Kurooto's tools yet" | agy's settings file isn't plain JSON, or `agy mcp add` failed. Add `mcp(kurooto/*)` to `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` yourself, then Test again. |
| The AI said it did something but nothing happened | Tell it so; check `/jobs`. With a small local model, tools may not be supported: it answers without them. |
| An agent program says Kurooto's tools aren't running | Kurooto is off or restarting; `kurooto on`, then ask again. |
| A book stays "not started" or "waiting for a reader" | Reading happens at night on the charger (`/books read now` starts it now). Scanned pages need Tesseract (`/books setup`) or a vision model (Local models); encrypted PDFs need Poppler. `/books` says which. |
| A book from Telegram wasn't added | Telegram lets bots fetch files up to 20 MB: drop bigger books into the folder (`/books folder <subject>`). The caption must say it's a book: `book for <subject>`. |
| Kurooto Terminal opens separate windows instead of tabs | kitty (Linux, macOS) or Windows Terminal isn't there: `kurooto term --install`, or Windows Terminal from the Microsoft Store. `kurooto term --print` says what it found. |
| "kitty didn't start" | kitty needs a graphics card driver with OpenGL 3.3 (some virtual machines lack it); set Settings → `terminal.kitty` off to use your usual terminal. kitty's own message is in `terminal/kitty.log` in the state folder. |
| Kurooto Terminal's tabs or colours look old in Windows Terminal | Close every Windows Terminal window and open it again: it reads Kurooto's profiles when it starts. |
| The system palette doesn't use my colours | Settings → Look shows what Kurooto found. Changes show within half a minute. Your setup keeps its colours somewhere else? Point `look.theme_file` at a kitty theme or a matugen or pywal `colors.json`. |
| The setup page says "Kurooto isn't answering" | It stopped or is restarting: start it from your apps menu (or `kurooto on`), then press the button again. What you typed stays. "Out of date": reload the page. |
| Notes appear in the wrong folders | Check `notes.layout` and `notes.paths` (Settings → notes); a custom place that doesn't work falls back to the layout's own. Existing notes aren't moved when you change the layout. |
| Photos and PDFs still land in my notes | Set `files.folder` to a folder outside your notes folder (one inside it changes nothing). |
| The setup page won't open | `kurooto open`, or go to `http://127.0.0.1:8770`. If another program uses that port, Kurooto picks the next one (`kurooto paths` → `web.json` in the state folder says which). |
| Not enough space | The wizard says what needs it. Free some space, or choose fewer features. |
| "That question expired" | It waited longer than `ask.expire_hours` (or its asker stopped waiting); nothing was done. The asker asks again if it still matters. |
| I tapped a button and nothing happened | It may have been answered elsewhere already (on a call, in the app): `/q` shows what's still open. |
| `kurooto ask`, `call`, `send`, `ask-me` or `ask-approval` say Kurooto isn't running | `kurooto on`, then try again. Note that `--timeout` is in minutes. |
| No night check-in | It's off until you give it a time: Settings → Check-ins → `times`, e.g. `"night": "23:15"`. |
| A night check-in I didn't want | Empty its time in Settings → Check-ins → `times`, or `/checkin night skip` for today. |
| The night check-in didn't ring | The alarm was set and it was past your bedtime: it moved to the wake-up call (the message says so). `checkins.asleep_defers` off makes it always ring. |
| "skip Friday's check-in" went to the AI | Kurooto acts by itself only for today, tomorrow, the day after or a weekday name; anything else (dates, "next week") goes to the AI. |
| "Held a call until …" | A class, `/hold`, focus, a calendar event or the night was on. The call comes by itself when it ends; `/calls` lifts a `/hold`. Too many events hold calls? Set `calendar.nocall_events` to `tagged`. |
| A call rang three times | It wasn't answered: repeats at +3 and +6 minutes. Answer, tap **Later**, or set `calls.realert_min` to `[]`. |
| No plan before my alarm | It needs Chat on and the alarm set at least a few minutes ahead (`alarm.prep_min`). The AI's answer is in the AI jobs tab. |
| The morning plan wasn't drafted (the computer slept) | Turn on `alarm.keep_awake`, and plug in overnight. |
| The morning page didn't open | It opens only if the computer is awake with a screen at alarm time (`alarm.open_page`). Open `http://127.0.0.1:8770/morning` yourself. |
| No after-class question | The class was skipped, it's a holiday or exam period, or the term is over (`/term`). |
| Study time counts while I'm away (Wayland) | Add the hypridle or swayidle hook (`kurooto idle away` / `back`, see [Study tracker](#study-tracker)). `kurooto doctor` shows what it uses now. |
| Study time stopped counting | A `kurooto idle away` without its `back`: run `kurooto idle back`. |
| A deadline shows up twice | They didn't look like the same thing (different dates or numbers in the title). Tap **Not mine** on one. |
| A calendar event became a deadline by mistake | **Not mine** on it, or `/ignore` a word in its title; to stop calendar deadlines altogether, `deadlines.from_calendar` off. |
| No call six hours before a deadline | Phone calls on and set up? A class, `/hold`, focus or the night until shortly before the deadline means a message instead. |
| Done didn't tick the box in my notes | The line was changed since Kurooto read it (it's re-read every hour); tick it yourself, nothing else depends on it. |
| A recurring quiz is on the wrong week | Put any date it really happens on in the "Next" column of `kurooto/recurring.md`. |
| `/journal` (or another skill) goes to Chat as plain text | Turn on **Skills** (Features). `/skills` lists the names. |
| A revision pack comes as a `.tex` file | Tectonic isn't installed: tap **Install Tectonic** in the message that came with the pack. If you tapped **Not now**, it asks again after 30 days. |
| The first PDF takes minutes | Tectonic fetches the LaTeX packages it needs once (about 50 MB); later packs take seconds. |
| "it didn't compile" | The AI's LaTeX had an error it couldn't fix; the `.tex` is in your notes. `/pack` again, or reply with what to change. |
| A routine didn't run | It runs when the computer is on; one missed while it was off runs once when it's back (if that's still one of its days). `/routines` shows what's set. |
| "I'd rather not keep that" after /remember | It looked like a health, money or password detail. Put it in your own notes instead; reword it if it isn't one. |
| The look back never suggests anything | Most days that's right. `/lookback` shows when it last ran and what it noticed; on a laptop it waits for the charger. `/lookback now` runs one. |
| A skill change says "nothing changed" | The AI's version was the same, or it broke the skill's header; it's never saved then. It may suggest it again another night. |
| The nightly upkeep didn't finish | Search still works. Its log is in the state folder (`gbrain/upkeep-<date>.log`); it tries again the next night. Turn it off with `gbrain.upkeep`. |
| Notes brain: "can't find your gbrain" or "your brain's folder isn't there" | Your own GBrain: set `gbrain.exe` to the full path of your gbrain program and `gbrain.home` to its `GBRAIN_HOME` (or set `gbrain.managed` back to `true`). |
| A handwritten PDF isn't written out | PDFs read on this computer wait for the night on the charger (`/handwritten` starts it now; `/handwritten status` says where it is). It also waits while the graphics card is busy. "Can't be drawn": install Poppler's PDF tools. |
| /notes or /timeline says the brain is busy | The nightly upkeep (or a sync) is using it; try again in a while. |
| Phone calls: "not connected to your call line" | Is this computer online? It reconnects by itself within a minute. Still not: Features → Phone calls → Set up (redeploys). |
| Cloudflare sign-in didn't finish | Press Set up again; the sign-in link is also shown in the progress log. |
| The phone doesn't ring | App checklist all ✓? Battery unrestricted, and not on a "sleeping apps" list? Dashboard → Phone → Ring my phone. |
| A call keeps cutting itself off on loudspeaker | Use the earpiece or earphones, or move the mic gate slider to the right. |
| iPhone gets no notifications | Opened from the Home Screen (not Safari)? Turned on in the app? iOS 16.4+? Settings → Notifications → Kurooto. |
| Questions don't show on the phone | Is `question` in `notify.app_kinds`? Android: is the app's "Questions and approvals" notification category on? iPhone: notifications on for Kurooto? Is the computer connected to your call line (Features → Phone calls)? |
| "Not sent: tap to try again" on Android | The phone was offline or the call line didn't answer. Tap it to try again, or answer on Telegram. |
| "That answer is too old (or this phone's clock is off)" | Set the phone's clock to automatic, then answer again. |
| "That's no longer open" | It was answered somewhere else (Telegram, a call, another phone) or expired. Nothing to do. |
| A file named "(conflict, this computer, …)" appeared in my notes | The note changed here and elsewhere at once: both versions are kept. Merge them, then delete the copy. |
| Notes sync: "a note was changed here and elsewhere at once" | `notes_sync.on_conflict` is `stop`. Nothing was lost: merge it in the notes folder (`git pull --rebase`, as the message says), or set it to `keep both`. |
| Notes sync: "a change elsewhere clashes" | Nothing was lost. Open the repository on GitHub, keep the version you want in the note, then `/sync`. |
| Notes sync: "a merge or rebase is unfinished" | Finish it in the notes folder (`git status` says how); sync goes on by itself. |
| `kurooto doctor`: Backups FAIL "the backup folder isn't there" | Plug the drive in (or sign in to the cloud app); the next backup comes within the hour. A drive that's unplugged for a day or two is only a note. |
| Backups: "not enough room in the backup folder" | Free space there, lower `backups.keep`, or turn `backups.index` off. |
| A restore went wrong | `kurooto restore <the zip in restore-safety/>` puts things back as they were before it. |
| Restore: "That passphrase doesn't open this profile" | It's the passphrase you picked when you turned on Profile sync (not your GitHub password). Try again; nothing was changed. |
| Restore: "…was changed or damaged, so it can't be trusted" | A file on the `kurooto-profile` branch was edited outside Kurooto. Nothing was changed here. On GitHub, open the branch's history and revert the last edit, then restore again. |
| Profile sync: "another computer saved your profile since this one did" | You restored or used Kurooto elsewhere. Restore it here (`kurooto profile restore`), or `/profile save` to make this computer's the one. |
| Two computers both answer, or the bot misses messages after moving | Turn Kurooto off on the old computer: `kurooto off`. |
| Google: "sign-in expired" | Features → Google → Save (signs in again). If it happens every 7 days, publish the app ([step 4 of the Google setup](#google-setting-up-your-own-sign-in-step-by-step)). |
| Google's sign-in says "Access blocked", or another Google error | See the table at the end of [Google: setting up your own sign-in](#google-setting-up-your-own-sign-in-step-by-step). |
| "Mail digest is paused: needs Google's OK" (or another Google feature) | Features → that feature → Save, then sign in with Google and leave its permission ticked. |
| A Google feature didn't turn on after signing in | Did you untick its permission on Google's screen? Save on its card again. Is its API on in your Google Cloud project (the link on its card)? |
| Google says "Access blocked" for a school account | Your school doesn't allow unverified apps for that permission. Use a personal Google account, or ask your school's admin. |
| A feature says "needs your school Google account" | Its account's sign-in is missing or expired. Features → that feature → Save, and pick that account on Google's page. `/google` shows which account each feature uses. |
| "That's the same Google account as your main one" | The browser picked the account you were already signed in with. Save on the card again and choose the other account in Google's chooser (or sign out of the first one in that browser). |
| The mail digest wasn't emailed | It mentioned confidential material (you got a note saying so), or the sending account's address isn't known: Features → Mail digest by email → Save, and sign in again. |
| The mail digest says it only counted my mail | It reads only what you chose: `/mail read @your-school.example` or `/mail read label:Name`. Mail marked confidential (a confidentiality footer counts) is always only counted, unless you choose local summaries (`mail_digest.confidential` = `local`). |
| "Confidential mail is only counted for now" | Local summaries need Local AI models on and ready (Features → Local AI models; on a laptop they run on the charger). |
| Classroom notes say a PDF wasn't read | Install Poppler (`pdftotext`), or use agy as your AI (it opens PDFs itself). |
| Classroom notes went to the wrong folder | Settings → `classroom_notes.folders`: `{"Exact course name": "folder-name"}`. |
| Research: "repository folder missing" | You moved or deleted it: `/repos remove <folder>`, then `/repos add <new folder>`. |
| `kurooto watch` says "only shown on this computer" | Kurooto wasn't running: `kurooto start`. |
| The Terminals tab says it's off, or a terminal won't type | Features → Terminals → Turn on. On Linux, a terminal from another user account is refused on purpose. |
| `/term` says "Term note …: not found" | The path is relative to your notes folder (`terms/2026-autumn`, `maps/semester-*`); `/term note <path>` again, or `/term note off`. |
| A class or date from the term note is missing | Check the table's heading ("Weekly timetable", "Key dates"), times like `09:00-09:55` and dates like `2026-11-12`; `/term` says how many classes and key dates it read. |
| Telegram's "/" menu is out of date | It updates within a minute of a feature going on or off, and every quarter of an hour for skills; `telegram.menu` off and on again sets it within a minute. |
| Your add-ons: a problem in `kurooto doctor` | `/addons` shows which file and the error. Fix it, then restart Kurooto (`kurooto stop`, `kurooto start`). |
| Something else | `kurooto doctor --bundle` and send the zip to whoever is helping you (see below). |

## Getting help (diagnostics)

`kurooto doctor` checks Kurooto, your AI, every feature you have on, and free space; each line says what's wrong, and
the exit code is the number of problems (handy after moving to a new computer). It also asks Telegram whether your
bot answers, asks your call line whether it's up (and whether the running Kurooto is linked to it), checks the skills
copied into agy, and runs your add-ons' own checks. A `working: ...` line per feature says whether it kept working
([Kurooto keeps itself working](#kurooto-keeps-itself-working)); `kurooto doctor --fix <id>` runs the fix one offers.
`kurooto top` and `kurooto logs -f` show what it's doing right now.

`kurooto doctor --bundle` saves a zip you can send to someone helping you. It contains Kurooto's checks, its log,
your settings and what happened recently, with **secrets, names, email and web addresses and your folders blanked
out**. It never contains your messages, notes, journal, transcripts, or what you asked the AI. Nothing is sent
anywhere: look inside the zip first, then send it yourself.

## Lost phone or keys that got out

`kurooto rotate` gives your call line new keys. Use it when a paired phone is lost or stolen, or when a backup zip
with your keys in it (`backups.secrets`) or a diagnostics file you didn't mean to share got out. It replaces:
- this computer's key to the line, and the key that signs call links (call links sent before stop working);
- the phone notification key and channel (Android) and the Web Push keys (iPhone).

It asks first (`--yes` skips that), deploys your call line again with the new keys (a minute or two; the same
address, so nothing else changes), and the line then **forgets every paired phone**, the call links it made and open
pairing codes. If the deploy fails, the old keys are put back and nothing changed. Then it walks you through pairing
again: with Kurooto running, it prints a pairing link (and a QR code) for one phone.
- *Android:* in the Kurooto app, tap **Unpair this phone**, then open the link on the phone (or scan the code).
- *iPhone:* delete Kurooto from the Home Screen, open the link in Safari and add it to the Home Screen again.
- Another phone: `/phone` on Telegram, or the dashboard's Phone tab → **Pair a phone**.

It also lists the keys only you can replace, from the health checks of the features you have on (your bot's token
with @BotFather's `/revoke`, Google's access at myaccount.google.com/connections, the GitHub token for your notes, and
your Gemini key; replace the Gemini key *before* `kurooto rotate`, and the redeploy takes the new one to your call
line). A lost phone that was signed in to Telegram: end that session from another device (Telegram → Settings →
Devices). With Profile sync on, run `kurooto profile save` afterwards, so a restore brings the new keys.

*Undo:* none, on purpose: the old keys are gone. Pair your phones again (above); a phone you didn't pair again can't
call or be called.

*Leaves:* the new keys go to your call line on your own Cloudflare account, as on every setup.

## Uninstall

`kurooto uninstall` removes Kurooto: the program, its settings, data and start-at-sign-in. `kurooto uninstall
--keep-data` keeps your settings and data. On Windows you can also use Settings → Apps → Kurooto. Want to keep a copy
first? `kurooto backup --to <folder>`.

**Leaving for good? `kurooto uninstall --revoke`** first takes back what Kurooto set up on your accounts, while its keys
are still on this computer:
- **Your call line:** deleted from your Cloudflare account, with its keys and stored data, through Kurooto's own
  Cloudflare sign-in, which is then signed out. If that sign-in has expired (or is for another account), it prints the
  steps instead: Cloudflare dashboard → Workers & Pages → the `kurooto-…` worker → Settings → Delete.
- **Google:** each signed-in Google account's access is revoked (Kurooto drops off myaccount.google.com/connections).
- **Telegram:** your bot's webhook and the messages waiting for Kurooto are dropped, and the command menu Kurooto set
  is removed. The bot stays yours (`/deletebot` to @BotFather deletes it).
- **Left for you,** with links: delete the GitHub token(s) you made for Kurooto
  (github.com/settings/personal-access-tokens), the Gemini key if you made it only for Kurooto, the Google client's
  Cloud project, Profile sync's branch.
- Then Kurooto's keys are removed from your system's keychain too (also with `--keep-data`; a plain uninstall leaves
  them there).

Each line says `ok`, `FAIL` (with what to do yourself) or `--` (nothing was set up). *Undo:* none: install again and
set up again (sign in to Google, paste your bot's token, Phone calls → Set up makes a new call line, pair your phones).
*Leaves:* Cloudflare gets the request to delete your line, Google the sign-in being revoked (that's how its revoke
endpoint works), Telegram the two requests to clear the bot.

**Your notes folder is never deleted.** Things Kurooto installed for you that live in its own folder (Node.js, MinGit,
Ollama on Linux, Tectonic) go with it; programs installed system-wide (agy, Ollama on Windows/macOS, Telegram Desktop)
stay, since you may use them. Without `--revoke`, your call line stays on your Cloudflare account until you delete it
there (Workers & Pages → the `kurooto-…` worker → Settings → Delete); paired phones stop working once it's gone. A
Google client can be deleted in Google Cloud, and the Agent plan calendar in Google Calendar; a notes repository stays
yours (delete its `kurooto-profile` branch if you used Profile sync). Backup zips stay in the folder you picked, and
your add-ons folder is never touched. Kurooto Terminal's app-menu entry and Windows Terminal profiles are removed and
"default terminal" is undone; kitty and fish that Kurooto got for it were in its folder, so they go too. The copies of
your skills Kurooto put in agy and other agent programs are removed; skills you made there yourself stay.

## FAQ

**Does it cost anything?** No, unless you pick a paid plan (a paid AI plan you already have, or a paid Gemini key).
Cloudflare, Gemini (free tier), Telegram, GitHub and Google Cloud are used within their free plans.

**Does my data go to whoever made Kurooto?** No. Nothing is ever sent to Kurooto's author. What leaves your computer
goes to the services you chose, under your own accounts; [PRIVACY.md](PRIVACY.md) lists it per feature.

**Will it send email or messages for me?** Never by itself. It sends nothing to anyone but you; anything outward (a
reply to an email, a draft) waits for your tap, and approvals are never given for you.

**Does it work when my computer is off?** Telegram messages wait until it's back. Phone calls and the alarm still
work from your call line, and you can answer questions on the phone app; anything that needs the computer is done when
it's back.

**Can someone else talk to my bot?** It answers only the Telegram account that tapped the pairing link; everyone else
is ignored.

**Can I use it on two computers?** One at a time per Telegram bot. Notes sync keeps notes in step across computers;
Profile sync moves your setup to a new one (see [Moving to a new computer](#moving-to-a-new-computer)).

**Where is the code?** [github.com/avtarfr/kurooto](https://github.com/avtarfr/kurooto), Apache-2.0. What might come
next is in [ROADMAP.md](ROADMAP.md).
