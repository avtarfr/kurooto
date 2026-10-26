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
    [Exam mode](#exam-mode) · [Exam season](#exam-season) · [Start-by dates](#start-by-dates) ·
    [Subjects and timetable](#subjects-and-timetable) · [Class packs](#class-packs) · [Doubt queue](#doubt-queue) ·
    [Quiz](#quiz) · [Weekly summary](#weekly-summary) · [First-week quests](#first-week-quests)
  - [Files into notes](#files-into-notes) · [Skills](#skills) · [Notes sorter](#notes-sorter) · [Quick notes and prompts](#quick-notes-and-prompts) ·
    [Hint ladder](#hint-ladder) · [Check my draft](#check-my-draft) ·
    [Notes brain](#notes-brain-gbrain) · [Local AI models](#local-ai-models) ·
    [The offline helper](#the-offline-helper) ·
    [After-class notes](#after-class-notes) ·
    [Remember](#remember) · [Nightly look back](#nightly-look-back) · [Learns from its own work](#learns-from-its-own-work) · [Dreaming](#dreaming) · [Brain](#brain) · [Set up from what you say](#set-up-from-what-you-say) ·
    [Meetings: minutes and action items](#meetings-minutes-and-action-items) ·
    [Wrong button and test cases](#wrong-button-and-test-cases)
  - [Phone calls](#phone-calls) · [Morning alarm](#morning-alarm) ·
    [Reminders with the lid shut](#reminders-with-the-lid-shut) · [Voice notes](#voice-notes) ·
    [Stay awake on charger](#stay-awake-on-charger) · [Calendar](#calendar)
  - [Notes sync](#notes-sync) · [Sync everything](#sync-everything) · [Backups](#backups) ·
    [Space keeper](#space-keeper-cleaning-off-old-backups-and-leftovers) · [Profile sync](#profile-sync)
  - [Google](#google-classroom-gmail-drafts) · [Several Google accounts](#several-google-accounts) ·
    [Google: setting up your own sign-in](#google-setting-up-your-own-sign-in-step-by-step) ·
    [Classroom → notes](#classroom--notes) · [Mail digest](#mail-digest) ·
    [Email reply drafts](#email-reply-drafts) · [Agent plan calendar](#agent-plan-calendar) ·
    [Google Calendar](#google-calendar) · [Mail digest by email](#mail-digest-by-email) · [Drive upload](#drive-upload)
  - [Handwritten notes](#handwritten-notes) · [Books and PDFs](#books-and-pdfs) ·
    [Concept graph](#concept-graph-books-into-linked-notes) · [Study packs](#study-packs) ·
    [Course notes as one PDF](#course-notes-as-one-pdf) ·
    [Study tracker](#study-tracker) · [Research](#research) · [Terminals](#terminals) ·
    [Kurooto Terminal](#kurooto-terminal) · [Your add-ons](#your-add-ons) · [Add-ons by link](#add-ons-by-link) ·
    [Official add-ons](#official-add-ons) ·
    [From a terminal or a script](#from-a-terminal-or-a-script) ·
    [The reserve](#the-reserve-markdown-copies-of-kurootos-state-for-ai-programs)
- [Your phone](#your-phone)
- [The dashboard](#the-dashboard)
- [Colours (Look)](#colours-look)
- [Taking your laptop with you (battery, pause, off)](#taking-your-laptop-with-you-battery-pause-off)
- [Starting at boot](#starting-at-boot)
- [Going offline and coming back](#going-offline-and-coming-back)
- [Kurooto keeps itself working](#kurooto-keeps-itself-working)
- [Calm by default: why each message came, and a daily limit](#calm-by-default-why-each-message-came-and-a-daily-limit)
  - [Keep or drop](#keep-or-drop)
- [Your rhythm: quiet hours, lighter days, gone quiet](#your-rhythm-quiet-hours-lighter-days-gone-quiet)
- [Memory: open threads and what's remembered](#memory-open-threads-and-whats-remembered)
- [Forgetting: how long conversations are kept](#forgetting-how-long-conversations-are-kept)
- [Where requests go: /egress](#where-requests-go-egress)
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
- **A Google account** (free): to sign in to the recommended AI, Antigravity (agy), and for a Gemini API key from
  Google AI Studio (calls and voice notes use one).

**Optional, depending on the features you pick:**

| Feature | Needs |
|---|---|
| Phone calls, Morning alarm | a free [Cloudflare](https://dash.cloudflare.com/sign-up) account and a Gemini key |
| Notes sync, Profile sync | a free [GitHub](https://github.com/signup) account |
| Backups | a folder on an external drive, or one your computer syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox) |
| Google Classroom, Gmail (drafts, the mail digest, reply drafts), the Agent plan calendar | your Google account, plus about 10 minutes in Google Cloud (free) |
| Revision packs as PDF | a LaTeX engine: your own (TeX Live, MiKTeX, MacTeX), or Tectonic, a small one Kurooto installs for you when you ask |
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

**Testers: the beta channel.** To try releases before everyone else, put `KUROOTO_CHANNEL=beta` in front of the
installer. The install then keeps following beta (it saves `updates.channel` = `beta` in its settings), and its
updates come from there too:

```sh
curl -LsSf https://avtarfr.github.io/kurooto/install.sh | KUROOTO_CHANNEL=beta sh
```

```powershell
$env:KUROOTO_CHANNEL = 'beta'; irm https://avtarfr.github.io/kurooto/install.ps1 | iex
```

To repair a beta install, run it the same way (without `KUROOTO_CHANNEL` it installs the stable release, though the
setting stays beta). *Undo:* Settings → `updates.channel` = `stable`; you get the next stable release when it's newer
than the beta you have.

**If something looks scary:**

- *Windows Defender / antivirus warns about a script:* the line downloads a PowerShell script from Kurooto's own
  release page. You can read it first: open the address in a browser.
- *macOS asks whether Terminal may control other apps, or access files:* only when a feature needs it (the Study
  tracker reads window titles). You can say no; that feature then says it can't.
- *The setup page didn't open:* go to `http://127.0.0.1:8770/setup` yourself, or run `kurooto open`.

## The setup wizard

The wizard is a page on your own computer (`127.0.0.1` means "this computer"; nothing outside can open it). It saves
as you go, so you can close it and come back: Kurooto keeps where you are, and reopening the page (`kurooto setup`, or
**setup** in the dashboard's corner) lands on the first step you haven't finished. The list of steps (on the left on a
wide screen, numbered dots on a phone) opens any step: finished ones have a tick, skipped ones a dash, and a step you
passed but haven't finished (an AI that doesn't answer yet) shows **!**. Words like *API key*, *token* or
*repository* are underlined with dots: tap one to read what it means.

**Skip for now.** Every step except **You** and **AI** has **Skip for now** beside Next: setup can't finish without a
name and an AI, but the rest can wait. Next on About you with no reports added, or on Chat with nothing connected,
counts as a skip too, and so does a step you never opened when you press Finish setup. Skipped steps wait on the
dashboard (Features → **Finish setting up**, and the corner link says **finish setup (N)**) and in `kurooto doctor` as
notes, never problems, each with its way back (`kurooto setup telegram` opens that step). A skipped step leaves the
list once it's done, wherever you did it (Telegram paired from the dashboard counts). *Undo:* open the step and press
Next.

**Where people stall.** Kurooto records how long you spend on each step and whether you finished or skipped it, on
this computer only (`setup.json` in Kurooto's state folder: steps, seconds, visits; never what you typed). It's never
sent anywhere: `kurooto doctor --bundle` puts it in the diagnostics zip, which is saved here for you to look at, and
you decide whether to send it to whoever is helping you.

1. **You:** what Kurooto calls you, your time zone (filled in from this computer, or your browser) and the
   assistant's name. An old name for a zone is saved under today's (`Europe/Kiev` becomes `Europe/Kyiv`), and
   zones are compared by their clocks, never their names.
2. **Notes:** your notes folder, and where Kurooto writes in it. Point it at the notes you already keep (an Obsidian
   vault, any folder of Markdown files; a Windows path with spaces works) and press **Look at this folder**: Kurooto
   reads the folder, with no AI, and proposes a place for daily notes, the inbox, subject folders, concept notes and
   research projects, each with how sure it is, plus a preview. **Use this layout**, change a line first, or **Keep
   Kurooto's own layout**. See [Fitting Kurooto to the notes you have](#fitting-kurooto-to-the-notes-you-have).
3. **Your computer:** what Kurooto found (processor, memory, graphics card, free space) and what it recommends for
   it, marked ★. You can change any of it later. On a laptop, what to do on battery; and the pages' **Colours**
   (see [Colours](#colours-look)): this computer's own colours are marked ★ when Kurooto finds them.
4. **AI:** pick the AI that answers you (see [Your AI brain](#your-ai-brain)). ★ marks the recommendation:
   Antigravity (agy), Google's agent program, signed in with your Google account. For agy and the other programs,
   press **Install** if it isn't installed and follow the sign-in; for a Gemini API key, make one at Google AI
   Studio, paste it and press **Save and test**. Then press **Test it**: it asks the AI to reply, and tells you if it
   worked, or what to do if it didn't.

   **Try it now:** once the AI works, a chat box appears under it. What you type there is handled exactly as a
   Telegram message would be, before Telegram is set up: "remind me in 2 minutes to stretch" pops up on this computer
   two minutes later, a question goes to your AI and its answer comes back in the box. Chat and Reminders answer there
   even though they're turned on later, with Telegram; other features answer once they're on. Nothing said in the box
   goes to Telegram or your phone. *Undo:* nothing to turn off; it's only there while you set up (a reminder set there
   still comes after a restart, and can be cancelled with `/reminders` once Telegram is connected).
5. **About you** (★ recommended, optional): teach Kurooto what your other AI accounts already know about you. See
   [About you](#about-you) below. **Skip for now** if you'd rather do it later.
6. **Features:** the **★ Starter** set is a good start (Telegram, chat, reminders, check-ins and deadlines; the notes
   brain is a 0.5 GB download, so it's yours to tick). **What do you do?** (Student, Working, Research, Something
   else) adds what suits it: a student gets subjects, start-by dates, the quiz, after-class notes, doubts and the
   weekly summary; working, commitments, start-by dates, the calendar and the weekly summary; research, the Research
   feature, commitments, start-by dates and the weekly summary. **Everything** or **Pick myself** for more; the add-ons
   that come with Kurooto (such as [Exam season](#exam-season)) are in no preset, only on when you pick them. The cards
   picked for you come first; the rest wait folded under **More features**. Some
   features ask for a detail right in their card (a calendar link, a repository); phone calls, voice notes and the alarm
   use your Gemini key (they ask for one if you picked another AI). Above the cards, one line says the daily limit
   ([Calm by default](#calm-by-default-why-each-message-came-and-a-daily-limit)): "Kurooto sends at most 6 messages a
   day on its own; the rest wait for one evening bundle at 20:00. Your own reminders, alarms and approvals always
   come." The number beside it changes `notify.calm.messages`.
7. **Chat:** pick where you talk to Kurooto: **Telegram** or **The Kurooto phone app instead**. The phone app needs
   Phone calls (tick it on the Features step, **Set up now**); then **Pair my phone now**, or pair after Done. Its chat
   does what the bot does; files come as links (see [Without Telegram](#without-telegram)). *Undo:* pick Telegram
   instead, or add it later in Features. For **Telegram**, make your own bot in two minutes:
   1. Open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, answer its two questions (a display name,
      then a username ending in `bot`).
   2. BotFather replies with a token like `123456789:AAH…`. Paste it in the wizard and press **Check**.
   3. Tap the link the wizard shows, then **Start** in Telegram. Kurooto now knows that chat is yours and ignores
      everyone else.
8. **Done:** the summary lists what you skipped, each with **Go back to it**. Finish setup installs what your
   features need (with progress), turns them on, and, if you chose Phone calls, shows a QR code to pair your phone.
   Send `/help` to your bot (or in the phone app's chat).

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
rather not keep before adding a report. Come back any time with more accounts: `kurooto setup about` opens that step
(or **setup** in the dashboard's corner). To teach it smaller things as you go, see [Remember](#remember).

**Your persona card.** Four short lines on how Kurooto talks to you: what to call you, tone, length, things to avoid
("plain and direct, no pep talk"). It starts empty (no name, voice or tone picked for you) and goes along with every
AI request and every call, so the wording is the same on Telegram, the app and calls. Set it on the dashboard's
**About you** tab (with a preview of what's sent), in Settings (`persona.call_me`, `tone`, `length`, `avoid`) or with
`/persona tone: plain, no pep talk`; `/persona` shows it, `/persona clear [line]` clears it. It sets wording only: a
part that would give Kurooto feelings ("say you missed me"), a backstory ("you grew up in Pune") or a relationship
("be my girlfriend") is left out, and you're told which; the same rules apply to a hand-edited settings file and to
`calls.persona`. *Leaves:* the card goes to the AI you picked and the call line's voice model, like the In brief.
*Undo:* `/persona clear`.

## Your AI brain

The "brain" is the AI that answers your messages and does tasks. You can change it any time (dashboard → Settings, or
the setup page), and set a **fallback** that takes over when the first one hits its limit.

| Brain | Cost | Good for | Setup |
|---|---|---|---|
| **Antigravity (agy)** ★ | free with a Google account | Kurooto's recommendation: Google's agent program, run on your computer; can read your notes and use Kurooto's tools, with higher limits than a free key. Some risk to the Google account (see the note below) | Install → a window opens → sign in with Google |
| **Gemini API key** | free tier, or paid | the way Google recommends for tools like this; also used for calls and voice notes. A free key's daily limits are strict and run out quickly, so it's best kept for calls and voice notes. Free tier: Google may use what you send to improve its products and human reviewers may read it; 18+; a paid key is required in the EEA, UK and Switzerland | [Google AI Studio](https://aistudio.google.com/apikey) → Create API key → paste |
| **Claude Code** (Advanced) | needs a paid Claude plan | if you already pay for Claude; it can do everything agy does here (below) | Install → sign in with your Claude account |
| **Ollama on this computer** | free | private and offline, but much weaker, and needs a good graphics card; best as a helper next to another AI | Install Ollama → Test |
| **Another OpenAI-compatible service** | depends | any service that speaks OpenAI's API | its address, key and model names |

**agy:** Kurooto runs Google's official agy program on your computer, signed in as you, and never touches its sign-in
token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to your Google
account; for tools like Kurooto, Google recommends a Gemini API key. Kurooto marks agy ★ for its higher limits and
full tool access; if that risk matters to you, pick a Gemini API key instead.

If you set Kurooto up before 0.2.0, it keeps the AI you chose. An AI set up as FreeLLMAPI with an earlier version keeps
working; it now shows as "Another OpenAI-compatible service". What each service's terms mean for your data is in
[PRIVACY.md](PRIVACY.md).

**Limits:** free tiers have daily limits. When the brain hits one, Kurooto tells you once and uses your fallback if
you set one. **At a limit, the other AI answers** (0.6.0): when Claude Code hits its limit (the 5-hour window or the
weekly cap) the request goes to agy, and the other way round, then to a Gemini key if you saved one, each only once it
has answered on this computer. The AI at its limit is skipped until it resets (the time it said, like "resets 3pm";
otherwise half an hour, doubling up to 5 hours), so later requests go straight to the other; `/brain` and `/usage` say
who is waiting and until when. This is what happens with no fallback picked (`brain.fallback` empty); a fallback you
pick (one AI, or a list such as `["agy", "gemini"]`, in order) replaces it and takes over on any failure, as before.
`brain.fallback_on` (`["rate_limited"]`; add `auth`, `timeout`) sets what moves a request on. The concept graph's
reading and second looks move the same way; a stand-in's batches count on its own nightly budget.
*Undo:* `brain.fallback_on` = `[]`.

**More than one Claude account** (0.7.0). With a second Claude subscription, sign it in as well: setup page → AI →
Claude Code → **Add another Claude account** (a name such as `work`; a sign-in window opens for it: sign in with the
other account, close it, then **Test it**), or `kurooto ai add-claude work` in a terminal. Each extra account is its
own AI, `claude:work`, usable wherever an AI is named (`brain.main`, `brain.fallback`, `integrate.roles`): its own
limits (one at its limit doesn't skip the other), its own line in the run receipt (*Claude Code hit its limit; Claude
Code (work) answered · ...*), in `/brain`, `/usage`, `kurooto usage` and the AI's `self.md`. With no fallback
picked, the other Claude account comes first at a limit: Claude Code → Claude Code (work) → agy → a Gemini key. Your
usual sign-in (`claude`) is untouched; each extra account's sign-in lives in a folder of Kurooto's
(`<data>/claude-accounts/<name>/`, Claude Code's `CLAUDE_CONFIG_DIR`), never read or copied by Kurooto and left out
of backups unless `backups.secrets` is on. Models: `brain.models["claude:work"]`, else `brain.models.claude`.
Using a second subscription to get around the first one's usage limits may not be allowed by Anthropic's terms; check them for your use.
*Undo:* dashboard → Settings → Claude accounts → **Remove** (asks first; deletes only Kurooto's folder for it and takes
it out of `brain.main` / `brain.fallback`), or `kurooto ai remove-claude work`. Rename there too (the id stays).
 `/usage` (with Chat on) lists AI requests per day over the last 7 days (`/usage 14` for two weeks), per
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

**Settings** (`quota.*`; not on the dashboard's Settings page yet: change them in `settings.json` in Kurooto's settings
 folder, [Where things are](#where-things-are)):
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
  asked, one exact passage at a time, and (0.7.0) that change becomes a **proposal** you apply: see [Proposals and
  scratch folders](#proposals-and-scratch-folders). With `proposals.notes_edits` off it changes the note directly and
  keeps the previous version first (Kurooto's state folder → `note-history/`, the last 20 per file). With Notes sync
  on, your repository's history has every version too.
- **Change requests** (Help with your project, a change to your notes you asked for, a fix Dreaming proposes): the AI
  may write in its own scratch folder only, and the change reaches your files as a proposal (below).
- **The web:** a public page as plain text (GET only, at most a few MB); never this computer or your local network.

- **API brains** (a Gemini key, Ollama, another OpenAI-compatible service) call the tools directly. A model that can't
  use tools (some small Ollama models) just answers without them.
- **Agent programs** (agy, Claude Code) get them through `kurooto mcp`, a small MCP server that passes each call
  to the running Kurooto. Claude Code gets it for each request only; nothing is saved in its own settings.
  Claude Code gets the same reach as agy, for that request only: it may read your notes, course files, Documents,
  Downloads and Screenshots, write in your notes folder, course files folder and your add-ons' skills, read web pages,
  run harmless commands (ls, cat, grep, find, git, latexmk, pdftotext…), and use Kurooto's tools and, with your own
  GBrain, its tools. Anything else is refused (`--permission-mode dontAsk`), `kurooto` itself never runs from a request,
  and your own Claude Code settings, hooks and history aren't used or changed. Models: `brain.models.claude`
  (default haiku for quick, sonnet for the rest; any name Claude Code takes).
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

### Proposals and scratch folders

The AI may think, draft and write freely, but only in a scratch folder of its own (Kurooto's state folder →
`scratch/<id>`): a git worktree on a new branch `kurooto/<id>` for a git repository, a mirror that fills as files
change for anything else (your notes, a folder that isn't git, a skill). For that request it may write there and
nowhere else; it reads as always, plus the project. When it ends, Kurooto compares the folder with the original and
sends a **proposal**: a title, a few lines, the files changed and the diff (inside the message up to
`proposals.inline_lines` lines, else as a file; the dashboard's **Proposals** page, `/proposals` in the browser,
shows it whole and coloured), with **Apply**, **Change** and **Discard**.

- **Apply** (a tap only: `proposal.apply` in "never without a tap"; typed: `/proposals apply <id>`): notes and folders
  are written, their earlier versions kept (Kurooto's state folder → `proposals/<id>/before/`); a git repository gets
  one commit on your current branch, made without touching anything else of yours, never pushed. Refused, saying why,
  when a file changed since, when you have uncommitted changes in the same files, or when the repository is on no
  branch or mid-merge. **Undo** afterwards: the earlier versions back, or a revert commit.
- **Change**: say what to change; the AI works again in the same scratch folder and the proposal comes back.
- **Discard**: the scratch folder is deleted; nothing of yours changed.
- A proposal that deletes files says so first ("It deletes 2 files: ...", red on the dashboard). Nothing is deleted
  from your files except by an applied proposal.
- `/proposals` lists what's waiting and what you applied lately (with Undo); `/proposals <number>` shows one.
- Work nobody was waiting for (a fix Dreaming proposes at night) isn't told one by one: it's in the morning message
  (Dreaming's, or with Dreaming off a "Waiting for your OK" message at `proposals.morning`), through Calm.
- Asking in plain words for a change to your notes ("tidy my LA notes' headings", "add a summary to this lecture
  note") runs in a scratch copy of your notes and comes as a proposal.
- How each AI is kept in the scratch folder: API brains only have Kurooto's tools, which write there and refuse (and
  report) anything else; Claude Code gets per-run permissions that allow editing only there and deny reading keys and
  passwords; agy runs in it with its Kurooto tools confined the same way, but its own allow-list is one settings file
  for every run, so its built-in file tools keep their usual folders: if anything in the original changed while it
  worked, the proposal names it.
- Never part of a scratch folder or a proposal: keys and passwords (`.env`, `*.pem`, `*.key`, `id_rsa*`,
  `credentials*.json` ...), `.git`, and in notes any hidden file. A proposal is at most `proposals.max_kb` (400) KB of
  diff and `proposals.max_files` (60) files.
- Settings (`proposals.*`): `notes_edits` (true), `keep_days` (7: an unanswered proposal and its scratch folder go),
  `max_kb`, `max_files`, `inline_lines` (30), `morning` (daily 07:30).

*Turn it off:* `proposals.notes_edits` = false (edit_note changes notes directly, as before 0.7.0); Help with your
project is a feature of its own. *Undo:* the Undo button after Apply, or `/proposals undo <id>`.
*Leaves your computer:* nothing new: the files the AI reads or writes in its scratch folder go to the AI you picked,
as any request's do; checks have no network.

## Features

Every feature is off until you turn it on (wizard, or dashboard → **Features**). Turning one off stops it at once;
its data stays unless you delete it. Each section says what leaves your computer; [PRIVACY.md](PRIVACY.md) has the
full list.

Plain English works for many things ("remind me at 9 to call mum", "move tonight's check-in to 21:30", "skip Friday's
check-in", "what's due?", "wake me at 6:45", "quiz me by call", "sync everything"). `/help` is an index, one line per
group (Talking, Reminders and deadlines, Calls and phone, Notes, Privacy and memory, Settings and upkeep, ...) with its
commands (the features you have on and Kurooto's own: `/q`, `/health`, `/fixme`, `/calm`, `/why`, `/keep`, `/jobs`)
and its page in the user wiki, then the features that are off; `/help <group>` (`/help calls`) shows one group in full,
what each command does and what you can just say, and `/help all` every group, one message each. `/help <word>` finds a command or feature, on or off
(`/help quiz`, `/help alarm`). What you can just say includes the requests Kurooto understands by itself ("did I
finish that thing?", "when did I last talk to Prof Ortiz?", "sync everything", "I got a project under Prof Ortiz",
"about the meeting with Prof Ortiz: ..."). The phone app's chat answers `/help` the same way; its links open with a
tap.

### Telegram
Your own bot, which only answers you. Optional when the phone app is paired (see [Without Telegram](#without-telegram)). Commands: `/status` (what's going on: whether calls are held, focus, what's
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

**Never without your tap.** Setting or moving an alarm, placing a call, reading mail from a new sender, sending
anything to someone else, attaching a code repository to a project and deleting your data happen only when you asked
for them yourself (a command, a plain-English request, on a call) or tapped to approve them. Your AI can't do them by
itself: outside a call, an AI request (or an agent program using Kurooto's tools) that wants to set the alarm or book a
call gets a **Your OK first** approval ("An AI request wants to set, move or clear an alarm: set_alarm (time: 7:30).
Do it?"), and it happens only on **Approve**. Things set up from what you say in passing never include these. The
whole list, with how each is approved, is in the user wiki: Talking to Kurooto → Never without your tap.

*Settings:* `ask.expire_hours` (default 48: how long an unanswered question stays open), `ask.keep_days` (default
0: answered ones are kept as long as `privacy.keep_days` when set, else 30 days; see [Forgetting](#forgetting-how-long-conversations-are-kept)).
*Leaves your computer:* the question goes wherever Kurooto reaches you (Telegram, the phone app, the desktop); open
questions are part of the brief your call line keeps for calls while the computer is off.

### Chat with your AI
Anything that isn't a command or an instant request goes to your AI; the answer comes back as a reply. A request that
a feature that's off would understand ("wake me at 7" with the Morning alarm off) first gets **Turn on** (turns it on,
with what it needs, and does the request) or **Not now** (your AI gets it instead); `turnon.offer` off skips that. Long
answers arrive as a file. **A conversation:** each message carries your last 6 exchanges with the AI from the past 2
hours, so "and the second one?" works; after 2 hours quiet it starts afresh. Only chat's own answers count (a digest's
or a research run's never turns up as something you said). `/new` (or `/clear`) starts a fresh conversation now. The
last 10 exchanges are kept in Kurooto's state folder (`chat/history.json`). `/brain` shows which AI answers and whether
it works; `/jobs` what's running and waiting (with Cancel buttons; `/jobs cancel <id|all>`, `kurooto jobs --cancel ID`)
and the last few; `/usage` how many AI requests ran each day and the limits hit. Your requests never wait behind
background work (it has its own lane), and a request that's stuck (no AI at work for `jobs.stuck_min` minutes, 10) is
stopped with a message. **Run receipt:** every answer ends with one grey line (italics on Telegram, plain text in the
dashboard and the terminal) built from the run's own record, not the answer's words: which AI and the model it ran
with, shortened (agy's `--model`, e.g. `3.8-flash`; the model Claude Code says it used, e.g. `opus-4.5`), who made the
quick effort decision when that was another model ("decided by gemma4:e4b, answered by Claude Code · opus-4.5"), who
stood in and why ("Claude Code hit its limit; agy answered"), the effort, how long, the share of today's limit when
Kurooto knows it, and what it actually did with Kurooto's tools ("searched notes, wrote 1 note"; "did nothing" when it
used none; agy and Claude Code's own file tools aren't seen, so for them "did nothing through Kurooto"; "used 2
remembered items" when it was told what's [remembered](#memory-open-threads-and-whats-remembered)). `/jobs` and the
dashboard's AI jobs page show each finished request's AI and model too. Quiet background work gets none;
`jobs.receipt` = `false` turns it off.
**Plan line:** a text request of yours that usually takes more than 20 s on that AI (the median of your last ones at
that effort, once there are three) gets one short line first: "Searching your notes, then answering (about 40 s with
agy)." Guessed from what's known before the run (a file, a link, your notes mentioned, remembered items). Never on a
call or for background work; `jobs.plan_line` = `false` turns it off.
**Your AI knows what's running** (0.6.0): ask it "why didn't my alarm ring?" or "which model answered that?" and it
reads `self.md` in Kurooto's reserve folder first: the version and update channel, this computer's system and hardware
profile, the AIs and models set up (fallback order, any at a limit and until when), each feature that's on and
whether its health check passes, the last day's failures counted by kind, and where the log and settings are. No
messages, notes, request titles or secrets. Beside it, a manual for the AI (how Kurooto works, what it may and may not
do) ships with each version. The AI reads both with the tool `kurooto_self` (agent programs also as `kurooto://self`
and `kurooto://manual`); `/fixme`'s **Ask my AI** sends `self.md` along. *Leaves:* `self.md` goes to your AI only with
a question about Kurooto itself (or Ask my AI), never with other requests.
**Answers at your length** (`persona.register`, on): a short message (12 words or fewer) is answered briefly, a long
one (80 or more) may get a full answer, and a voice note gets an answer worded to be said aloud. By your message's
length only: nothing changes at night or partway through a conversation, and a length on your persona card wins.
**Boundaries** (`persona.boundaries`, on): decisions about your health, relationships and money are yours. "Should I
stop my meds?", "should I break up with him?", "should I take the loan?" get one line at once, without the AI: it's
not Kurooto's to decide, and who to ask (a doctor or pharmacist; someone you trust or a counsellor; a financial
adviser). Every AI request and call is told the same rule. A fixed rule list, not the AI's judgement.
**Two readings** (`repair.on`, on): a short message no instant request takes, but about equally close to two of them,
gets 'Did you mean "..." or "..."?' with both as buttons and **Neither**, instead of a guess. On Telegram and the
phone app; otherwise nothing changes. Picking the same one twice teaches the phrasing (with Wrong button and test
cases on).
*Leaves:* what you ask, and notes it reads, go to the AI you picked; with a conversation going, your recent
exchanges go along too.
*Undo:* `persona.register`, `persona.boundaries` or `repair.on` off brings back the old behaviour of each.

### Reminders
"remind me at 9 to call mum", "remind me in 20 minutes to take the pasta off", `/remind tomorrow 7am gym`,
`/reminders`. A reminder due while the computer slept arrives when it wakes, marked late (with
[Reminders with the lid shut](#reminders-with-the-lid-shut) on, your Android phone gets it at its time instead).
Buttons: +10 min, +1 h.

**At a place** (0.6.0, off by default): "remind me when I reach the library to return the book", "remind me whenever
I'm at the gym to stretch". Turn on Settings → Reminders → `places` and, in the Android app, Location reminders →
Places (it says the battery cost, then asks for location). Save a place on the phone while you're there (a name, no
map; 150 m around it). The computer sends only the place's name and the text; the phone keeps your places and reminds
you when you arrive, with the computer off too. Needs Phone calls set up and the Android app. *Undo:* Turn off in
Places (the app stops watching); `reminders.places` back to `false`.

### Check-ins
At times you choose, Kurooto asks how the day is going: the **evening** check-in (default 22:00, the day in review),
an optional **night** one (goodnight, near bedtime) and an optional **midday** one. Reply to the message and it goes
into your journal (`journal/YYYY-MM-DD.md` in your notes folder).

- **Turn on the night or midday one:** Settings → Check-ins → `times`, and give it a time, e.g. `"night": "23:15"`.
  Both are off until you do.
- **The day's reflection** (`checkins.reflect`, on): the evening message lists up to three things the day's records
  show you did ("Problem set 3: done", a thread closed, "Essay draft: 4 of 7 done", "Studied Linear Algebra 1.5 h", a
  class whose after-class question you answered), then asks "What's first tomorrow?". Only records, never a guess from
  what you wrote; fewer than three: what there is; nothing: no list. No streak, no score, nothing about what you
  didn't do. **Not tonight** under it ends the check-in for the day (in place of Skip today). By call, the evening
  debrief says the same list back in one line.
- **It learns your times** (`checkins.learn_times`, on): a check-in you've answered on 5 or more of the last 14 days,
  and on 4 or more of them 30+ minutes from its time on the same side (moved, or replied late within 3 hours), moves
  to when you actually did it, with one line and **Undo**. Not again for two weeks; after an Undo, not for a month.
- **Change one in plain English:** "move tonight's check-in to 21:30", "push the check-in by 30 min", "skip the night
  check-in". Other days work too: "skip Friday's check-in", "move tomorrow's check-in to 9". A day Kurooto can't pin
  down ("yesterday", "next week", a date) goes to the AI instead of guessing.
- **The check-in day runs from 05:00 to 05:00** (`checkins.day_starts`). A night check-in at 00:30, or one you push
  past midnight ("push the night check-in by 30 min" at 23:50), is still that evening's: it rings at 00:20 and its
  journal and study logs go to the evening's day. Still up at 1 am, "move the evening check-in to 21:00" means the
  coming evening, and "skip the night check-in" skips the coming night's once tonight's is over. Set it to `00:00`
  for calendar days. Once your quiet hours are learned, it turns two hours before you're usually up, unless you set
  it ([Your rhythm](#your-rhythm-quiet-hours-lighter-days-gone-quiet)).
- **Lighter days:** the day after an exam or a heavy study day, the first check-in comes an hour later; **Not today**
  under the morning line puts it back.
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
study logs after a check-in call), `checkins.day_starts` (default `05:00`), `checkins.asleep_defers` (default on),
`checkins.reflect` (default on).
*Undo:* `checkins.day_starts` = `00:00` (calendar days, as before 0.3.0); `checkins.asleep_defers` off (the night
check-in always rings); `checkins.reflect` off (the evening message as before 0.5.20, with Skip today).
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
  take out of the note leaves the list;
- offered with an **Add** button each, added only when you tap: a photo (below), mail you forward to yourself
  ([Email in](#email-in)) and a class calendar someone shares ([Calendar](#calendar): `/cal subscribe`).

**Photo to dates:** send a photo of a notice, a poster or a timetable with `dates` (or `/dates`, `timetable`) as its
caption, or say `/dates` / "dates from that photo" just after sending or sharing one. The AI you picked reads it; each
deadline, exam and event comes back as a line with **Add** (plus **Add all** and **None of these**), and a timetable's
classes with **Add N classes to my timetable** (new courses become subjects). A deadline or exam goes into this list
(source: photo); an event becomes a reminder `date_offers.remind_min` (60) minutes before it. agy, Claude Code and a
Gemini key read pictures; Ollama when its model does (otherwise it says so and sends nothing); another service is
tried. *Leaves:* the photo, to the AI you picked. *Turn off:* `deadlines.from_photos`. *Undo:* a tapped deadline:
**Not mine** under it in `/deadlines`; a reminder: `/reminders` → Cancel; classes: `/class remove mon 09:00`.

The same thing from two places (say Classroom, your calendar and a task in your notes) is kept once; a known time
beats "end of the day". Topics on your not-interested list are left out.

**How much is done:** "ps3 4/7" (or "did 4 of 7 on the stats problem set") keeps a deadline's parts done. The lists
and calls show "(4/7)", and Start-by plans from what's left. On a call, the AI uses the same (`deadline_progress`).
Or reply to the deadline's reminder or "Overdue?" message (Telegram, the app's chat, the phone's Reply): `4/7`, `4`,
`+1` or `done`, each with **Undo** (the latest change only; Undo of `done` also unticks the note's box). While parts
remain, those messages and `/deadlines` have **+1**, which stays to be tapped again; on the phone (with `"deadline"`
in `notify.app_kinds`, or in the app's chat) each tap counts, in order, even while the computer sleeps. The wake-up
call, the morning page and `/status` say "Problem set 3 4/7, due Fri".

**The chase**, for things you hand in:
- a day before: a message with **Done / Not mine / Snooze 3 h** (and **+1** first for one with parts to do);
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
`scan_notes` (on), `skip_notes` (none: notes or folders the scan leaves alone), `from_term_note` (on: the term note's key dates, when you have one), `from_photos` (on: Photo to
dates).
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
One card for the whole exam period, on top of exam mode. An add-on that comes with Kurooto: listed apart under
Features (**Add-ons**), off until you turn it on, and in no preset (**Everything** leaves it out). It needs
Deadlines. **It does nothing without exam dates:** the exam periods in Subjects (`/term exams 2026-12-07 to
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
- **Only deadlines, quizzes and the alarm by day** (`budget`):
  [Calm](#calm-by-default-why-each-message-came-and-a-daily-limit) holds everything else that comes by itself for the
  evening bundle. Your own reminders, approvals and anything urgent still come.
- **Revision plan before each exam** (`revision`): from `revision_days` (14) before an exam, its course's topics are
  ranked and laid into your free time, one per `block_min` (60) minute block, with what to read. Plain arithmetic, no
  AI. Topics: the course's exam prep note (**Covered so far**, then the short lines under **Gaps**), else its lecture
  notes, else its concept notes. Ranked: no note yet, a stub (under 50 words of your own), weak recall (quiz grades and
  your answers here average under 3 of 5), the rest; weakest recall first in each. Blocks go into
  [Start-by's](#start-by-dates) free time (its window less classes and calendar events, and here also commitments and
  the exams), `revision_share` (50%) of each day's, the soonest exam first, ending before you leave for it; at most
  Start-by's size for the exam. With each topic: its note, then the class material's pages that name it (Classroom's
  files, your files folder), then book pages (the concept graph's and Books'). Today's blocks are fixed the first time
  they're worked out and are in the morning plan with Start-by's lines; at the evening check-in's time (`night_at`
  without Check-ins) one message asks "did you cover Jordan form today?" with **Yes** / **Partly** / **No**
  (`revision_ask`): the answer grades the topic's quiz items as a quiz answer would (4, 2 or 1 of 5), and a topic you
  said Yes to isn't laid again. `/revise` shows the plan, `/revise la` a course's ranked topics, "what should I revise
  today?" today's blocks.

**The quiz call before an exam stays off unless you pick it for that exam:** the card (and `/examseason`, with Quiz
and Phone calls on) has a switch per exam. Picked, Kurooto calls you for a quiz at `quiz_call_at` (19:00) the evening
before, instead of the practice offer, and exam mode's daily practice (`quiz.exam_daily`) may call for it with
`quiz.by_call` on. For the season's other exams, the practice stays a message.

"exam season?" or `/examseason` shows the season, its exams with what you told Kurooto, and the parts that are on.
On calls on the exam day and the day before, the brief has the exam and what you said about it.

*Settings* (`exam_season.*`): `hold_updates`, `alarm_check`, `eve`, `leave_alarm`, `debrief`, `no_calls`, `budget`
(all on), `night_at` (21:30), `eve_at` (18:00), `leave_min` (45), `exam_min` (180), `quizzes` (off), `quiz_call_at`
(19:00), `revision`, `revision_ask` (on), `revision_days` (14), `revision_share` (50), `block_min` (60).
*Undo:* turn Exam season off in Features: its timers, leave-by alarms (also on your call line) and update hold go at
once, and the call-blocking during exams stops. Or switch off just the part you don't want. Debriefs already written
stay in your notes; answers are kept in `exam_season.json` in the state folder for 30 days after the exam. The
revision plan writes nothing in your notes (its plans and answers are in `revision.json`); `/revise undo` puts a
topic's quiz grades back as they were, and tapping another answer replaces the first.
*Leaves:* with Phone calls on, the leave-by alarm's time, the exam and what you said about it go to your call line
(like any call). Nothing else.
### Start-by dates
Off until you turn it on (Features → Start-by dates; it needs Deadlines). When to start each deadline, worked back
from how much work it is and your free time. It's an estimate, and plain arithmetic on this computer: no AI.

**Sizes.** Each deadline gets a size from what it is: a problem set, homework or worksheet is an evening (3 h); a
report, essay, project or presentation 2-3 days (12 h); a quiz or test 2 h; an exam what you set for its subject
(10 h until you do); anything else 2 h. Correct one with a tap: the "Time to start" message and `/startby` have
buttons with the other sizes (an hour, an evening, a day, 2-3 days, a week; for exams up to two weeks). A size you
tap for an exam counts for that subject's exams from then on, and a subject's first exam asks you once ("How long do
you usually need to prepare for a Topology exam?"). `/startby exam la 2-3 days` sets it too; `/startby exam` lists
them. On a call, or to your AI: "the lab report is about a day of work".

**Free time.** Each day from 09:00 to 22:00 (`startby.window`), less your classes (Subjects: the timetable, holidays,
exam periods, the classes you skip) and your calendar's timed events (Calendar), in gaps of at least half an hour.
Only 40% of it counts (`startby.share`): the rest is meals, rest, going over lectures and everything else. Calendar
events are known two weeks ahead (`calendar.days`); after that only classes count, so far-off weeks look freer than
they will be.

**The window learns your day** (`startby.learn_window`, on). Once a week (Sunday noon) it looks at when your messages
came in over the last three weeks. With 7 or more days of 3+ messages, and the middle of your first messages or of
your last ones an hour or more from the window's ends, the window moves there, to the half hour (starting between
05:00 and 13:00, ending between 17:00 and 03:00): "Start-by dates now count your free time from 11:00 to 01:30, not
09:00 to 22:00", with **Undo**. Not again for a week; after an Undo, not for a month. A window you set yourself is never
changed.

**Start-by dates.** Working back from the due times, latest first, each deadline's hours go into the latest free
time before it that a later one hasn't taken; the day its first hour lands on is its start-by date. Two big deadlines
in the same week push each other earlier. From that date until it's due, the deadline is in the morning plan: the
morning page (**Time to start**), the wake-up call, and the plan drafted before the alarm. On the day itself (at
08:00, `startby.when`, never in quiet hours) you get one message, "Time to start: Lab report, due Fri 13 Nov. It's
about 12 h (2-3 days) of work...", with the sizes to tap: at most three a day, and only when it's two days or more
before the due date (closer than that, the deadline's own day-before nudge says it). When there isn't enough free
time left, it says so. The first morning after you turn it on, one message lists what's to start now instead.

**Negotiate, don't repeat** (`startby.negotiate`, on). When a deadline's reminder would come again (the six-hour one
after the day-ahead one, one after a Snooze, the message after a missed deadline call, or one for a deadline whose
"Time to start" came on an earlier day) and the deadline is slipping, you get a reshaped plan from your own Start-by
plan instead: "Problem set 4 (due Tue 03 Nov 11:00): your Start-by plan has 2 h of it today, and about 1 h of today's
free time is left. 1 h now, 1 h tomorrow?" with **Do that** (tomorrow's part gets a reminder at the start of
tomorrow's first free time; with the Agent plan calendar on, both parts go in as blocks) and **Not today** (nothing
more about it today). Slipping means this morning's plan put hours of it into today that what's left of today's free
time no longer holds. One offer per deadline per day, in plain fixed words; then reminders come as before. On a
deadline call the AI can offer the same plan once (`reshape_plan`, `reshape_answer`).

**Crunch weeks.** The Sunday summary flags weeks in the next four (`startby.crunch_weeks`) where the work due adds up
to more than the free time ("Crunch weeks (an estimate): week of 9 Nov: about 14 h of work, about 9 h free. Start
some of it the week before."), and says what's to start in the coming week. "Any crunch weeks coming?" works any
time.

`/startby` lists the deadlines of the next five weeks (`startby.horizon_days`) with their start-by dates and sizes,
and the sizes to tap; "when should I start the lab report?" answers for one.

*Settings* (`startby.*`): `sizes` (hours: `problem_set` 3, `report` 12, `quiz` 2, `exam` 10, `other` 2),
`exam_by_subject` (hours per subject, e.g. `{"linear-algebra": 25}`), `window` (`09:00-22:00`; an end before the
start runs past midnight), `share` (40, %), `min_gap_min` (30), `horizon_days` (35), `when` (`daily 08:00`), `tell`
(on: the message on a start-by day), `ask_exams` (on), `crunch_weeks` (4; 0: none), `negotiate` (on: a reshaped plan
instead of a repeated reminder).
*Privacy:* stays on this computer.
*Turn off:* Features → Start-by dates. Just the messages: `startby.tell` off; the exam question: `startby.ask_exams`
off; crunch weeks: `startby.crunch_weeks` = 0; reshaped plans: `startby.negotiate` off.
*Undo:* turn it off: the morning plan and the Sunday summary are as before at once. The sizes you tapped stay (in
`startby.json` in the state folder, and `startby.exam_by_subject`) for when you turn it on again; reset
`startby.exam_by_subject` in Settings to forget the exam sizes.

### Subjects and timetable
Your courses with short names (`/subject add Linear Algebra (la, linalg)`) and your timetable (`/class mon 09:00-09:55
la`). Kurooto never calls you during a class (or in the 5 minutes before it, `subjects.margin_min`). `/classes today`,
`/skip la` or "skipping LA today" (not going: calls aren't held for it), `/attend la` (undo). Attendance and standing is
gone from 0.5.8: `/skip` no longer warns about attendance. "not going to LA on Friday" and "skipping stats tomorrow"
mark that day. Other features use the subjects: after-class notes, the quiz, the study tracker.

**A course's AI policy:** `/subject policy la hints` (`allowed`, `hints` or `off`; `/subject policy la` shows it,
`clear` unsets it), or the AI help box in the dashboard's Study pane. [Check my draft](#check-my-draft) and the
[Hint ladder](#hint-ladder) go by it; `/subject` shows it next to each course. Not set counts as allowed.

**Missed-class catch-up** (`subjects.catch_up`, on): a class you skipped, or one over before you were up (the alarm
answered, "I'm awake", or your first message of the day), gets a catch-up task in Deadlines due when that course's
next class starts (else in 3 days) and a lecture note for that day (yours, else a short stub to fill in). One message
lists them; **Went to ...** takes one back (and the stub, if untouched). With Google Classroom on, the message and the
stub also list that day's Classroom posts for the course (title and link); later posts that day join an untouched
stub. Without Classroom, the rest works the same.

**Term dates:** `/term ends 2026-12-04` (the last day of classes) and `/term exams 2026-12-07 to 2026-12-18` (an exam
period; add as many as you need). On those days, after the term ends and on holidays there are no classes: no
after-class questions, and the timetable doesn't hold calls. `/term` shows them, `/term clear` removes them.
Holidays are a list of dates in Settings (`subjects.holidays`, e.g. `["2026-12-25"]`), and, with Calendar on, the
all-day events of your holiday calendars: add your country's public holiday calendar to Calendar (in Google
Calendar: Other calendars → Browse calendars of interest → Holidays, then its iCal link) and send `/cal holidays
Holidays` (any part of its name; `/cal holidays none` stops it).

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

### Class packs
One person turns the section's setup into a small file; everyone else sends it to their own Kurooto and has the
timetable, term dates, holidays, recurring quizzes and dated exams from day one. Off until you turn it on (Features →
Class packs; it needs Subjects).

**What a pack carries, and nothing else:** the courses (names, short names, which are electives), the weekly timetable
(lecture, lab or tutorial, and a lab batch), the term (last day of classes, holidays, exam periods), recurring quizzes,
dated exams and the day it was checked against the official timetable. The format is strict
(`<name>.kurooto-course`, JSON): a field it doesn't know makes the whole file invalid, so there's no place in it for
names, keys, notes, skills, your skips or your own deadlines, and every piece of text in it is checked for an email
address, phone number, link, @handle, file path or anything that looks like a key. A file that breaks a rule is
refused whole, with the reason. Packs made before 0.5.8 may also carry attendance rules: they still import, and the
rules are left out.

**Making one.** `/classpack export` makes a pack of your setup: your subjects and timetable, your term note, your
`/term` dates and holidays, and your recurring quizzes. For the whole section (every elective, every lab batch), keep a
term note ([Subjects and timetable](#subjects-and-timetable)) with two more columns in its timetable and one more
table, and `/classpack export from terms/section-b` reads that note alone:

```
## Weekly timetable
| Day | Time | Subject | Code | Type | Batch |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Mon | 09:00-09:55 | Linear Algebra | MA101 | | |
| Thu | 14:00-16:55 | Statistics | | Lab | A |
| Fri | 14:00-16:55 | Statistics | | Lab | B |
| Wed | 10:00-10:55 | Machine Learning | | Elective | |

## Recurring quizzes
| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Linear Algebra | Quiz | 1 | Thu | 10:00 | | |
```

Type says lecture, lab or tutorial ("Elective" marks a course not everyone takes); Batch is a lab batch. Write a lab
under its course's name ("Statistics", Type Lab) to keep it one course. Kurooto's message lists what's in the pack and
what it left out (and why). Tap the electives; reply to change anything: "title Year 2 section B", "la quiz off",
"la quiz fri 11:00", "holiday 2026-10-02 off". Then check it against the official timetable and tap
**Checked today, make it** (or reply "checked 2026-10-18"): that date is stamped in the pack, and the file comes to
your Telegram for you to forward (a copy stays in Kurooto's data folder, `classpacks/`). From a terminal: `kurooto
classpack export --checked today [--from terms/section-b] [--title "Year 2 section B"] [--elective machine-learning]
[--out FOLDER]`; `kurooto classpack check FILE` says whether a file is a pack Kurooto can use, and what's in it.

**Importing one.** Send the `.kurooto-course` file to your bot (or `kurooto classpack import FILE`). Nothing counts
yet: first a review says when it was checked against the official timetable (where they differ, the official one is
right), what's in it and what it means for you. Tap the electives you take and your lab batch, reply to leave out or
move a quiz ("la quiz off", "la quiz fri 11:00"), then **Import**.
The pack sits under your own setup, never in it: your own classes (`/class`), term dates (`/term`), term note and
recurring table win where they say something else, and nothing is written into your notes. Its classes keep calls
away like yours, holidays and exam periods have no classes, and its quizzes and exams reach [Deadlines](#deadlines)
(with `deadlines.recurring` and `deadlines.from_term_note` on). `/recurring` marks its quizzes "(class pack)".

**After a mid-term reshuffle,** send the new pack: the review lists what changes for you (classes moved, holidays,
quiz times, exam dates) before anything does, and keeps your electives, batch and changes. The same pack again
changes nothing. `/classpack` shows what you have; `/classpack set la quiz off` (or any change above, `electives ml,
topology`, `batch B`, `la reset`) changes it later and lists what changed for you. A pack whose term ended more than two
weeks ago shows up in `/health`.

*Privacy:* everything stays on this computer; a pack you make goes to your own Telegram, and you decide whom to
forward it to.
*Turn off:* Features → Class packs; the pack stops counting and is kept for when you turn it on again.
*Undo:* `/classpack remove` takes the pack out (your own setup stays); `/classpack undo` goes back one step (to the
pack you had before a re-import, or back after a remove).
### Doubt queue
A doubt from class, kept for the next one (needs Subjects). `/doubt la why does the rank not change?`, or in plain
words "I have a doubt about eigenvalues", adds a line to that subject's doubts note, `<subject>/doubts.md`
(`sources/<subject>/doubts.md` in the zettelkasten layout; `notes.paths.doubts` for your own place):
`- [ ] why does the rank not change? (2026-10-20)`. Half an hour before the subject's next class (`doubts.before_min`,
30), its open doubts come to you as one message with a **Tick** button per doubt; a tap ticks it in the note
(`[x]`). Tick them by hand in the note just as well. `/doubts` (or "show my doubts") lists the open ones, `/doubts la`
one subject's.
- **Which subject:** the one you name (its name or short name, anywhere in the doubt), else the class that's on now or
  ended in the last 3 hours (`doubts.recent_h`), else buttons ask which subject.
- Plain words work for a short, one-sentence doubt; a longer one, or several sentences, goes to the AI as a request
  (with Chat on), so use `/doubt` for those.
- No AI answers your doubts: they're for asking in class, a tutorial or office hours.

**Undo:** turn Doubt queue off (dashboard → Features). The doubts notes are yours and stay; nothing is deleted.

*Leaves:* nothing.

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
- **Link recall cards**: the concept graph's links between notes as questions ("How is Itô's lemma used in
  Fokker-Planck?"). `/card` gives one; reply in your own words, then see the link's reason and where to read (book
  pages, the subject's own notes and Classroom files) and grade it **Forgot / Hard / Good / Easy**; the quiz's
  spacing. Cards also come from your course notes (a lecture note or course page linking a concept note with a typed
  link, or `- [[note]]:` and a reason of five words or more) and from concepts read out of Classroom files and handwritten notes (their
  course is the file's); new cards about what you met in class in the last 14 days come first. `/cards on`: up to `links_per_day` (3, at most 5) a day at `links_at`, also in the phone app, never in a
  class, focus time or the night. `/cards`: how they're going.

*Settings* (`quiz.*`): `per_session` (3), `exam_per_session` (6), `offer_at` (19:00; empty turns the evening offer
off), `exam_daily` (off; a time like 18:00 turns on a daily exam-mode practice), `by_call` (off: `/quiz`, "quiz me"
and quiz check-ins ring you when it's on), `call_min` (10), `links` (off), `links_per_day` (3), `links_at`
(`daily 11:00,16:00,20:00`), `links_check` (off: a local model's one-sentence check of a link card answer).
*Undo:* `quiz.by_call` off brings back **Here or by call?**; `/cards off` stops link cards.
*Leaves:* with Chat on, the question and your answer go to the AI to grade it.

### Weekly summary
Every Sunday evening (`weekly.when`, Sunday 19:00): the week in numbers (requests, reminders, check-ins, deadlines,
quiz, study hours, journal days), and what isn't working that could wait until then
([Kurooto keeps itself working](#kurooto-keeps-itself-working)). `/week` any time. With
[Start-by dates](#start-by-dates) on, also crunch weeks ahead and what to start in the coming week.
**People** (`weekly.people`, on): one line about the people in your project notes, only from what's logged there
(minutes, "Last met", "Meets:"): who you met this week, who's next, and anyone you meet regularly but haven't met for
three weeks. Never a message of its own; nobody is mentioned from chats or mail. *Undo:* `weekly.people` off.

**Sunday review call** (optional, with Phone calls on; Settings → `weekly.call`): after the summary, a call of about
15 minutes: the week in numbers and study hours per subject, what went well and what didn't, anything Kurooto should
do differently, and next week's deadlines and your priorities. Afterwards it becomes a weekly review in your journal
(written by the AI with Chat on, your own words without). If the computer was off all Sunday evening, you get only the
summary.

### First-week quests
For your first week: one short message a day (at 18:00, `quests.when`) with one thing to try, each leaving something
real behind. "Add tomorrow's classes: /class tue 09:00-09:55 la", "send me one real deadline", "set a reminder for
something real", "a doubt from class?", "quiz me on la", "/study la 25", tonight's check-in, "remember that I ...",
`/mindjournal`. Turn it on in the setup page's Features step or the dashboard.
- Only features that are on and pass their checks (what `kurooto doctor` looks at) get a quest, and one you've already
  done (there's a timetable, you set a reminder this week) is left out. A day with nothing to suggest sends nothing.
- A quest is done when the thing happens. Replying to the message with it works too ("remind me at 21:00 to pack my
  bag" as a reply sets the reminder).
- **Skip this one**: tomorrow brings another. **Stop these** (or reply "stop"): no more, for good. Leaving a day's
  quest alone (not done, not skipped, not answered) also stops them for good: no nagging.
- Seven days at most (`quests.days`). `/quests` shows how far they got; `/quests stop` ends them.

**Undo:** turn First-week quests off (dashboard → Features), or `/quests stop`. What the quests had you add (classes,
deadlines, reminders) is yours and stays.

*Leaves:* nothing; no AI.

### Files into notes
Send a photo or PDF to your bot: it's saved in your notes folder's `inbox/` (or your files folder's, when you set one:
[Your notes: layout and files](#your-notes-layout-and-files)). With Chat on, the AI files it properly
(a note that describes and links it, in the right place). The caption tells it what it's for. With Skills on, a link
sent on its own is filed the same way (the `/add-to-notes` skill).

### Help with your project
The AI works on a project of yours (a thesis in LaTeX, code, a report) in a scratch folder, and what it did comes back
as a proposal ([Proposals and scratch folders](#proposals-and-scratch-folders)). Turn it on in Features, then let it
help per project: none can until you say so.

- Projects: the folders set up with `/project add <folder> [as <name>]` (a project from its repository, below; typed
  only: attaching a folder is in "never without a tap"), Research's repositories (`/repos add <folder> [as
  <project>]`, `research.projects` names them), the LaTeX documents you attached (`/latex add`) and `projects.folders`
  (Settings). A project set up from a GitHub address is listed, but Kurooto's copy is read only: the AI helps only in
  a folder of yours.
- `/project` lists them all (one command for setting up, updating and help); `/project help on <name>` / `off`; `/project help <name> <what to do>`, or say it: "in my
  thesis add footnotes to chapter 2 citing refs.bib", "help with my thesis: fix the failing test". One request at a
  time per project.
- A git repository gets a worktree on a new branch from your current commit (your uncommitted changes aren't in it);
  Apply makes one commit on your current branch, never a push. Any other folder gets a mirror; Apply writes the files,
  with Undo.
- **Checks** (`/project checks <name> <command>`; `off`; with no command it shows a suggestion: latexmk for a LaTeX
  folder, pytest, npm test, cargo test, make test): after the AI's changes Kurooto runs it in the scratch folder, with
  a time limit (`projects.check_timeout_s`, 300) and no network, in a sandbox that can write only there (bubblewrap on
  Linux, macOS's sandbox-exec) and doesn't see Kurooto's settings or your key folders; the proposal says passed or
  failed. Without a sandbox (Windows, Linux without `bwrap`) checks don't run, and the proposal says so. The AI can
  run them too (`run_checks`) while it works.
- Settings (`projects.*`): `folders`, `help` (the projects it may help with), `checks`, `check_timeout_s`, `effort`
  (high).

*Turn it off:* Features → Help with your project, or `/project help off <name>` for one. *Leaves your computer:* the
files the AI needs from the project go to the AI you picked, as any request does; nothing is pushed or sent.

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
puts them in `~/.agents/skills` (GitHub Copilot CLI as `/mindjournal`, and other programs that read that folder); `--to claude` puts them in `~/.claude/skills` (Claude Code
as `/mindjournal`), only when you ask for it. Kurooto only ever changes or removes the copies it made (they carry a `.kurooto-skill` marker): if you have a
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
and `.pdf`; `revision-packs/` when the subject has no folder) and sent to Telegram. PDFs need a LaTeX engine:
**Tectonic** (a small one) when it's installed, else the computer's own LaTeX (`latexmk`, else `pdflatex`, from TeX
Live, MiKTeX or MacTeX). With neither, the first pack comes as a `.tex` file, and a message asks **Install Tectonic** /
**Not now** (about 25 MB, from Tectonic's official releases; the first PDF then takes a few minutes while it fetches
about 50 MB of LaTeX packages into Kurooto's cache). After **Not now** it doesn't ask again for 30 days. If a pack
doesn't compile, the AI gets one try to fix it; otherwise you get the `.tex`.

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

### Notes sorter

**What it does** (0.7.4). Notes you drop in a scratch folder (`inbox`) are moved by themselves into the right folders of your
notes. Turn it on: Features → **Notes sorter** (off until you do).
- **Every night at 03:30** (`sorter.at`) and on `/sort now`, a note that has sat ten minutes is placed by rules (its own
  `subject:`, a tag or its title naming one of your subjects, what you taught it), else, with `sorter.ai` on, by one short
  request to your AI that may only choose one of your folders. A note it can't place stays, listed by `/sort` with Move buttons.
- **It never deletes, merges or overwrites** (a taken name gets a number), moves only from the scratch folder into folders you
  already have, and leaves a note your own notes link to by path (they'd break). At most 20 a day.
- **Undo:** one message says what moved with an **Undo** button; `/sort undo` restores everything, links included.
- **It notices a note belongs elsewhere:** a note you move yourself after it filed it is a lesson (and left alone); on Sundays it
  re-checks what it moved and may move a note once more (at most monthly), with Undo.

**Commands:** `/sort`, `/sort now`, `/sort undo`. **Settings:** `sorter.folder`, `at`, `per_night`, `settle_min`, `min_conf`,
`ai`, `recheck`, `learn`. **Privacy:** only a note the rules can't place sends its first lines to your AI (switch it off with
`sorter.ai`).

*Leaves:* the AI request, as above. *Undo:* `/sort undo`; turn the feature off in Features.

### Quick notes and prompts
`/note <text>` saves it straight into your notes' inbox (`inbox/YYYY-MM-DD-<first words>.md`), as written; a photo or
file with `/note` as its caption is linked from the note. From a terminal: `kurooto note "an idea"` (or pipe text in:
`some-command | kurooto note --title "output"`); this works even when Kurooto isn't running.

Your prompt library is the `prompts/` folder in your notes (Markdown files, subfolders allowed): `/prompts` lists it,
`/prompt <name>` sends one back to copy, `/prompt save <name>` with the prompt on the next lines adds one.

*Needs:* Telegram. *Leaves your computer:* nothing (no AI involved). *Turn it off:* Features → Quick notes and
prompts.

### Hint ladder
Stuck on a problem? Send a photo of it with `/hint la` as the caption (or type it: `/hint la show that the trace is
basis-free`), and you get one step at a time: **the idea** first, then **Next hint** for **the setup**, then **the
key step**. The full solution comes only when you ask: the **Show the solution** button after the key step, or a reply
of "solution" to any hint. Reply "next" works like the button. Every step names the lecture note the problem belongs
to (the AI's pick if that note exists, else the subject's note whose name fits the problem best).
- **The course's AI policy.** The first time you use `/hint` for a subject, Kurooto asks what the course allows (Hints
  and full solutions / Hints only, no full solutions / No AI help, or your own words) and keeps your answer as a line
  in the subject's course note: `AI policy: Hints only, no full solutions (your answer to Kurooto, 2026-10-20)`. After
  that it reads the line from the note, so change it there; a line you wrote yourself (`AI policy: ...`) counts too.
  "No full solutions" (or "hints only") ends the ladder at the key step; "no AI help" (or "not allowed") means no hints
  for that subject, and nothing is sent to the AI. A policy set for the course itself (`/subject policy la hints`, or
  the AI help box in the dashboard's Study pane: allowed, hints, off) comes first, and then nothing is asked.
- The AI works out the whole ladder once and Kurooto shows it a step at a time; an answer that doesn't come in steps
  is never passed on (it could give the solution away). It's the shipped `hint` skill: copy it into your skills folder
  to change how hints are written.
- Needs Subjects (the subject's short name goes first). Photos need an AI that opens files itself (agy,
  Claude Code); with a Gemini key or another service, type the problem instead.

**Undo:** turn Hint ladder off (dashboard → Features). The "AI policy" lines stay in your course notes; delete them
there if you like.

*Leaves:* the problem (its photo or text), the subject's AI-policy line, and the notes the AI reads to find the lecture
note go to the AI you picked.

### Check my draft
Part of the Research add-on (Features → Research add-on). Before you hand something in, send it with "check this": a
photo of a proof, a PDF, a `.tex` derivation, an essay (`.md`, `.txt`, `.docx`), accounts working or code. Your AI
marks what to look at, each comment pointing at a line (`L12-14`) or a place (`p2, the second displayed equation`):
**gap** (a step is missing), **unclear** (can't be followed as written), **error** (false, miscalculated, doesn't
compile or run), **needs a reason** (true, but unjustified). It **never rewrites the work or gives a solution**: a
comment that would hand over the fix is left out (the message says how many), and an answer that doesn't come as
comments is never passed on.
- **How to send it:** on Telegram, the file with `check this` (or `check my proof for la`, `/check la the induction
  step`) as its caption, or `check this` within 15 minutes after sending it (`drafts.recent_minutes`); from the phone
  app, share the file with the note `check this` (or type it in the chat just after sharing); on the dashboard, Study
  pane → COURSE → the file's path → **check**, or `/check la ~/proof.tex` in its chat.
- **The course** is named in the message or the file's name, else its folder, the class going on or just over, your
  only subject; else Kurooto asks once with your courses as buttons.
- **The course's AI policy** (`/subject policy la allowed|hints|off`, or the Study pane's AI help box): **hints** says
  only where each problem is and what kind; **off** checks nothing and sends nothing. Not set counts as allowed.
- **Notes:** when the draft is lecture notes (a note of yours, or what the AI says are notes), the comments also go into
  the matching lecture note in a Kurooto block (`drafts.note_block`); your text there never changes.
- A text file (up to 60,000 characters) goes in numbered line by line, so any AI can name lines; photos and PDFs need
  an AI that opens files itself (agy, Claude Code). At most `drafts.max_comments` (15) comments.

**Undo:** turn the Research add-on off (dashboard → Features); delete a `kurooto:draft-check` block from a note if you
don't want it.

*Leaves:* the draft and the course notes the AI reads go to the AI you picked; with the course's policy `off`, nothing.

### Notes brain (GBrain)
Search your notes by meaning (`/notes what is a compact space`), and your AI gets a memory of them. Kurooto installs
[GBrain](https://github.com/garrytan/gbrain) and keeps its index in Kurooto's own folder; it re-reads your notes
every 15 minutes. On computers without a graphics card the index is made with Gemini (note text goes to Google) or
keyword-only; with a graphics card or Apple Silicon it stays on your computer.

More things, each with its own switch in Settings (`gbrain.*`):
- **Timelines** (on, `gbrain.timelines`): every night, dated log lines in your notes, written like
  `- **2026-10-19** | source — what happened`, become each note's timeline. `/timeline research/reading-group` shows
  one; your AI uses them for "when did I last ...?". Kurooto's own skills write their log lines this way. No AI is
  involved and nothing leaves your computer.
- **Course pages** (on, `gbrain.course_pages`): every night each subject's course page gets one block of Kurooto's
  own (`<!-- kurooto:course-overview -->`): its classes, key concepts (the concept notes its notes link to most) and a
  dated timeline of its lecture notes, deadlines and the term note's key dates for it, in the timeline format, so
  `/timeline stats/course` shows the course and your AI sees it as one page. Only the block is rewritten; a missing
  course page is made. Rules only. *Undo:* turn it off; delete the block if you don't want it.
- **Nightly upkeep** (off, `gbrain.upkeep`): GBrain's maintenance cycle at 03:00 (`gbrain.nightly`), light steps
  only: links, facts, timelines, the index, orphaned pages. Steps that would rewrite your note files or call an AI
  model are left out. It's heavy, so on a laptop it waits for the charger. If it fails you're told once (with where
  its log is), not every night.
- **Weekly checkup** (off, `gbrain.checkup`): GBrain's own advisor, Sundays at 19:30 (`gbrain.checkup_when`). You get a
  message only when something is a warning or worse, with **Ignore these** (adds them to `gbrain.checkup_ignore`) and,
  when the brain needs a schema update, **Update the brain**.
- **Weekly checkup line** (on, `gbrain.checkup_line`): at the same time, one line from GBrain's doctor (run read
  only, never migrating): "Notes brain checkup: all well (score 95/100), 31 checks passed." or "... 2 things to look
  at; first: run gbrain embed --stale". With the checkup's findings it opens that message instead. *Undo:* set it to
  false, or Less of this.
- **Contradictions** (on, `gbrain.contradictions`): the last report of GBrain's contradictions probe, if you ran it
  (`gbrain eval suspected-contradictions`; it uses an AI model, so Kurooto never runs it), joins Dreaming's "Worth a
  look" section with Keep A / Keep B / Both true. Both sides are your notes: nothing is changed.
- **On calls:** search_notes searches the brain by meaning, and note_timeline reads a note's or a course page's
  timeline.

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

### The offline helper
On a laptop without a graphics card, a small model on the processor (`qwen2.5:1.5b-instruct`, about 1 GB, through
Ollama) takes the quick decisions: how hard a request is, which instant request a short message means when no pattern
is sure, and whether a short reply to "Still true?" is a yes or a no. Your AI still writes the answers. `/helper on`
sets it up: Ollama if needed, a check that there's room, the download, then a speed test (the middle of three
one-word answers within 1.5 s). Too slow here, it stays off and its model is removed again. `/helper` shows how it's
doing, `/helper test` times it again, `/helper off` turns it off.

**When the internet is down** (with or without the helper): a quick question to Chat is answered by the helper, with
a line saying so; everything else waits ("No internet connection right now: it waits and runs as soon as it's
back"), runs when the connection is back (one line says what's running now) and its answer says it waited. After 24
hours a request that's still waiting ends with a message; nothing is dropped silently. Plain-English requests and an
AI on this computer work as always. Kurooto knows from its own traffic (Telegram, your call line, its requests to
two or more services failing); it pings nothing else.

**Offered once**, two weeks after Kurooto started on this computer, on a computer without a graphics card for local
models, when your free AI limit ran short on 3 of the last 14 days or the internet dropped 3 times in that time:
**Install** / **Not now** (asked once more a month later at most).

*Settings:* `local_helper.on`, `model`, `max_s`, `timeout_s`, `offline`, `hold_h`, `offer`.
*Undo:* `/helper off` (the model stays in Ollama: `ollama rm qwen2.5:1.5b-instruct` removes it); `local_helper.offline`
= `false` makes requests fail as before when the internet is down.
*Leaves:* only the model's download, made by Ollama from its registry.

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
With [Learns from its own work](#learns-from-its-own-work) on, the nightly look back adds facts you stated by itself,
under "Picked up from your chats and calls", each with an Undo that takes that one line out again.
"Remember to buy milk" is a reminder, not this: use Reminders for that.

**Still true?** A line Kurooto wrote in its own sections (with its date) that hasn't come up in 90 days (not in what
you asked or said on a call, not told again, not kept with Keep) gets one quiet "Still true?" with **Keep**,
**Change** and **Forget**, at most two a week. Forget takes the line out (with **Undo**); Change asks for the new
wording by reply, by the same rules (with **Undo**); replying "yes" keeps it, "no" forgets it. Lines you wrote yourself
are never asked about or touched; editing a line counts as new. *Setting:* `remember.recheck_days` (90; 0: never).

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
for the call). Apply does it at once; nothing changes without your tap.

Before the AI, rules on this computer read the records themselves. A **routine** it sees (the same study session or
`/hold` at the same time of the week on `retro.routine_weeks` (3) different weeks, not a commitment or class yet) comes
as one message a night with **Add** / **No**; Add makes it a [commitment](#commitments). **Data fixes it is sure of**
are made at once, each in one line with **Undo**: two copies of one deadline (Classroom's and the one you said, due
the same day, same course, same words and numbers) become one. Only fixes listed in `core/tap.py` (`BY_ITSELF`) are
made this way; anything outward, an alarm or a call waits for your tap. **No** drops that idea (however it's worded
next time) for 30 days. **Observe longer** watches it for a week first (reply "observe 14" for 14 days); when the
watching ends, the next look back tells you what it found.

**Steer it:** `/observe whether I study better before noon for 2 weeks` (or say "observe whether ..." / "keep an eye
on ...", or ask on a call). `/observing` lists what's being watched, each with **Stop** and **+7 days** (watch a week longer) buttons. When a watch ends you
get a message with what it found. `/lookback` shows the last look back (and what it noticed); `/lookback now` runs one
now.

*Settings* (`retro.*`): `when` (`daily 23:50`; `weekly sun 21:00` looks back over the whole week), `max_proposals`
(3), `observe_days` (7), `no_days` (30), `transcripts` (on), `journal` (on), `routines` (on), `routine_weeks` (3),
`fixes` (on). The look back's instructions are the
`retro` skill: put your own copy in `kurooto/skills/retro/SKILL.md` to change how it thinks (it's not a command).
*Needs:* Chat. *Turn it off:* Features → Nightly look back. Waiting suggestions stay answerable for three days.

### Learns from its own work
An optional add-on (Features → Add-ons; in no preset; needs Chat). Kurooto keeps what its own finished work teaches it.
It doesn't ask first: it acts, tells you in one line, and every change has an **Undo** button (`/learned` lists the
last ten with theirs). Four parts, each with a switch on the card and a setting:
- **Search its memory** (`learning.search`): a search index of your past AI requests and their answers, call
  transcripts and chats, kept on this computer (`learning/history.db` in the state folder, brought up to date every 15
  minutes and before each search). `/history lab report` (or `/history 7d lab report` for the last 7 days) shows the
  best matches; the AI searches it too (the `search_history` tool) when you refer to something from before.
- **Skills from experience** (`learning.skills`): after a request of yours that went well and took at least
  `learning.skill_min_steps` (5) tool uses, a background request on the second-look AI (low effort) decides whether
  it's a procedure you'd want again. If so it writes a skill into `kurooto/skills/<name>/SKILL.md` with `learned: true`,
  `learned_from` (the request) and `learned_on` (the date) in its header, and says "Learned a skill: /weekly-lab-report,
  from today's request. /skills weekly-lab-report to see it." When a skill already does it, it adds a few tips to that
  skill under "## Learned from experience" instead; never a second skill for the same thing. At most five requests a
  day are looked at.
- **Lessons from corrections** (`learning.corrections`): reply to a skill's answer saying what was wrong, or send "no,
  ...", "that's wrong", "next time ..." within two hours of it, and the skill gets a line under "## Lessons" ("Lesson
  for /journal: Put the date in the title."), or rarely the step that went wrong rewritten. A reply that only answers
  the skill's question isn't a correction.
- **Worth remembering** (`learning.remember`, at most `learning.remember_max` (3) a night): the nightly look back also
  picks out lasting facts and preferences you stated in the day's chats and calls, and adds them to your how-to-help-me
  note under "Picked up from your chats and calls", by Remember's rules: never health, money, passwords, or anything
  about other people. Needs the nightly look back on.

Learned skills and lessons need Skills on. For a skill that comes with Kurooto, the change goes into your own copy.
`learning.brain` picks the AI that takes the second look ("": the concept graph's second-look AI, else your main one).
*Undo:* the message's **Undo** (or `/learned`): a new skill is removed; a changed skill goes back to how it was (its
earlier version is kept in `learning/before/` in the state folder; your own copy of a shipped skill is removed); a fact
is taken out of the note. If you edited the skill or the line since, Undo leaves it alone. Turning the feature off
keeps what it learned.
*Leaves:* nothing to build the index. When the AI searches it, the passages it finds go to that AI with the request;
learning a skill sends the request, its answer and steps, and a lesson your correction and the skill, to the
second-look AI; picking up facts sends the day's requests to the AI the look back uses.

### Commitments

**What it does.** The regular things in your week that aren't classes: the gym, a shift, a standup, tuition you
teach. `/busy add gym mon,wed,fri 18:00-19:00` (days can be `weekdays`, `weekends`, `daily` or `mon-fri`; a name of
several words works: `/busy add night shift daily 22:00-06:00`). While one is on, calls wait, as they do for a class
(`commitments.no_calls`), and a shift that runs past midnight holds them until it ends. `/busy` lists them and today's
skips; `/busy skip gym` or "skipping gym today" (or "not going to the gym tomorrow") frees that day, `/busy unskip
gym` undoes it; `/busy calls standup off` keeps one in the list without holding calls; `/busy remove gym`. On a call,
Kurooto knows today's commitments and can mark one skipped. Saying one in passing sets it up (see
[Set up from what you say](#set-up-from-what-you-say)). Not to be confused with Skills' routines (`/every`), which run
a skill on a schedule.

**Hooks.** "when I say gym, hold calls 90 min" keeps a word; later "gym" on its own holds calls for 90 minutes, as
`/hold` would ("gym: no calls until 19:42"). "when I say lab, hold everything 2 h" starts focus instead (calls and
messages that can wait are held). Only the word alone does it: "I'm off to the gym" is an ordinary message. A longer
hold already on is kept. `/hooks` lists them, `/hooks drop gym` forgets one. Setting, firing and dropping each come
with **Undo** (firing's puts back the hold that was there before). Without a length or "calls"/"everything", or with
a word like "ok", it says how to put it and sets nothing. A hook never sets or moves an alarm and sends nothing to
anyone. *Setting:* `commitments.hooks`.

**What leaves your computer.** Nothing.

**Undo.** `/busy remove <name>`, `/hooks drop <word>`, or turn Commitments off in Features (the lists stay for when you
turn it on again).

### Dreaming

**What it does.** Turned on (Features → Dreaming), everything Kurooto did while you slept comes as one message at
`dreaming.when` (07:30): books read into your notes, links tidied, handwritten notes linked, lessons from calls,
skills and facts learned, things set up from what you said; then the loose ends: your open doubts from the last two
weeks, notes nothing links to yet, broken links, tasks past due, AI requests that failed. A quiet night sends nothing.
`/dream` shows it any time. The day after an exam or a heavy day it starts with one line saying the day will be
lighter, with **Not today**; once your quiet hours are learned, `dreaming.when` follows when you're usually up
([Your rhythm](#your-rhythm-quiet-hours-lighter-days-gone-quiet)).

**The self-check** (`dreaming.self_check`, on). With [Wrong button and test cases](#wrong-button-and-test-cases) on,
each morning it replays your test cases and names any that went right yesterday but go wrong now (after an update or a
settings change), so a step back shows up the next morning. It also counts the requests it didn't understand and the
Wrong taps since the last message; the Sunday look back shows them.

**Tuning its own messages** (`dreaming.tune_messages`, on). Before the message, it replays the messages it sent you by
itself in the last 45 days under a few variants of when they come: a kind waits for the evening bundle once N in a row
go unanswered (`notify.calm.habituate`), always waits for it (`notify.calm.evening`), or comes only at the hours you
answered it (`notify.calm.windows`). Each variant is scored with what you did (answered and still in time: for;
ignored interruptions: against; holding back one you answered quickly: heavily against). Today's rules are always a
candidate; the best variant is applied only if it beats them by `dreaming.tune_margin` (3), one change a night, and
the morning message says so with **Undo**: "Learned while you slept: questions about quiet projects wait for your
evening bundle once 2 in a row go unanswered; over the last 14 days that would have saved 8 ignored pings and delayed
none you answered." It never touches what always comes (the alarm, your reminders and calls, approvals, deadlines
under 12 hours), kinds that can't wait, `dreaming.never_tune`, or what you set yourself, and after an Undo it leaves
that kind alone for 30 days. `/dream policy` shows the rules and the last nights' decisions with their scores.

**Tuning the rest of what it decides** (Dream RSI, part three). The same replay, on three more of its own decisions,
each with its switch:

- **Effort** (`dreaming.tune_effort`, on): the effort your own requests get, per what picked it (the quick check's
  low, medium or high, or the study-from-notes rule): `brain.effort_map`. Scored on your requests of the last 45 days:
  asked again within 15 minutes, marked **Wrong**, followed by "that's not what I asked" (or "you misunderstood", "no,
  I meant ..."), ran out of time, and run time. A level a request didn't run at is estimated from the record (more
  effort fixes half of the misses; less risks the answers that went well), so it moves one step at a time. A level
  you type ("high: ...") is never changed, and background work keeps the quick check's pick.
- **Which AI goes first** (`dreaming.tune_fallbacks`, on): with a fallback AI set, `brain.fallback_first` lists the
  effort levels at which the fallback is tried before the main AI. Scored on every try recorded per AI: answers,
  limits, sign-outs, timeouts and how long they took; an AI that wasn't tried counts as limited when it hit a limit in
  the two hours before, else by its own record.
- **Start-by sizes** (`dreaming.tune_sizing`, on): `startby.sizes` per kind of deadline, against how long they really
  took: study time on the deadline's subject from its start-by date until you marked it done (shared with that
  subject's other deadlines those days), half-done deadlines with parts ("4/7") extrapolated, and sizes you tapped.
  A size you set yourself is never changed; exam sizes per subject are yours.

Still **one change a night in all**: of everything that beats today's rules by its margin, the one that wins by the
most goes in, with **Undo** and a line like "Learned while you slept: requests the quick check calls quick now get
medium effort, not low; 6 of the last 13 were asked again, marked Wrong, corrected or ran out of time." The rest wait.

**It improves the way it improves.** Each change's outcome is kept: still in place after two weeks is kept; undone
(or put back by hand) is undone. A kind of change you undid needs a clearer win next time (the margin times 1 + the
undone ones - half the kept ones, up to 4 times), and the thing it changed is left alone for 30 days. `/dream policy`
shows every area, the last decisions and which kinds need a clearer win.

**Proposed fixes to skills** (`dreaming.propose_prompts`, off). When one skill's answers were corrected, marked Wrong
or asked again twice or more in two weeks, the night asks Learning's second-look AI for the skill with the failing
step rewritten, and whether that fixes each of those cases. It's offered only when it fixes at least half of them
(more after you said No to one), in the morning message as a proposal (0.7.0: [Proposals and scratch
folders](#proposals-and-scratch-folders)) with **Apply**, **Change** and **Discard**; `/dream proposal` shows the whole
proposed skill and `/proposals` its diff. It's never applied without your tap. Apply changes the skill with a
before-copy (Undo in `/learned`, or Undo under the proposal) and replays your test cases; if one that passed goes
wrong, the change is put back at once. Change has the AI rework it in a scratch folder. Discard (or No on a message
from before 0.7.0) leaves that skill alone for 30 days.

**Curious** (`dreaming.curious`, on). A topic you asked about 3 or more times this week (requests to the AI, what calls
searched your notes for, quiz questions you got wrong) with no note on it, or only a stub, gets one line: "You've
asked about the Fokker–Planck equation 3 times this week and there's no note on it. Want one?" **Make a stub** writes
a concept note in that subject's folder, linked from its course page; **Not interested** adds the topic to your
not-interested list. Only clear topics count: your concept notes' names, phrases ending in a word like equation,
lemma or theorem, and pairs of names like Navier–Stokes.

**From the past** (`dreaming.resurface`, on). One line about a note you last changed 10 to 30 days ago, a subject you
last practised in a quiz then (those with an exam in two weeks first), or an anniversary of a project's first Log line
or a repository's first commit, in whole months or years. **Open it** (or **Practise**) and **Less of this**.
Each line comes at most once a day; the same topic or note not again for 30 days.

**Worth a look in what I remember** (`dreaming.consolidate`, on). Each night at 04:45 it looks for the same thing
remembered twice (two gists of one kind from the same day, two of Kurooto's lines in your how-to-help-me note) and for
lines that disagree (a how-to-help-me line against another or against your notes, two of your notes, a note against an
open deadline, and, with the notes brain on, its contradictions report): the same thing, the same "Quiz 3", with a
different date, weekday, time or number ("Quiz 3 is due Fri" and "Quiz 3 is due Mon"). Your daily notes and project
meetings from the last 30 days are compared; a line that only says when you did something doesn't count. A few
(`dreaming.consolidate_max`, 3) come as one section of the morning message, each with **Keep A**, **Keep B** and
**Both true** (**Keep both** for a duplicate). Nothing changes until you tap: keeping one side takes the other out of
your how-to-help-me note, drops the other gist, or moves the deadline to the date your note says, each with **Undo**;
a line in your own notes is never changed (it says which note, for you to change). Both true isn't asked again; an
item shown on two mornings without a tap is let go. `/dream check` looks now. Rules first; a pair that's close but
not clear can get a second opinion (`dreaming.consolidate_ai`): `local` (the model on this computer, when there is
one), `main` (your AI; only how-to-help-me lines and note lines, never a gist) or `off`, at most 8 a night.

**For your profile** (`dreaming.fold`, on). Each night at 04:50 it reads what you said since the last time (your
chats with Kurooto, your lines on calls, the AI requests you made, your journal and daily notes) for lines that state
something lasting about you ("I'm a second-year geology student", "my thesis is on sea ice") or how you like to be
helped ("don't call me before 9", "I prefer short answers"). A few (`dreaming.fold_max`, 3) come as one section of
the morning message, each with where and when you said it and where it would go, and **Keep** and **Not that**.
Nothing is written until you tap Keep: a fact about you goes into Kurooto's own block of your profile
(`<!-- kurooto:learned -->` in about-me/profile.md, made if you have no profile yet; it goes along with every AI
request next to the In-brief part), a how-to-help line into your how-to-help-me note under "Learned in the nightly
look back", each in your words with where it came from: "- I prefer short answers (from a call, 2026-10-23)". Rules
pick the lines: first person, a statement (not a question, not "maybe" or "if"), not only about today, not already in
your profile or how-to-help-me note, nothing about other people (a "he", "she", "my friend" or a phone number, so a
forwarded message isn't learned from), never health, money or passwords. With `dreaming.fold_ai` = `local` (the
default) the model on this computer, when there is one, takes a second look and drops what isn't lasting; `main` asks
your AI (only those lines go to it); `off` leaves it to the rules. **Not that** drops a line for good; one shown on two
mornings without a tap is let go. Building your profile again keeps the block; lines you edit in it stay as you wrote
them. `/dream fold` looks now.

**What leaves your computer.** Nothing: it reads Kurooto's own log, its memory, your requests' titles and your notes.
What calls searched your notes for is kept 8 days at most (and `/forget` clears it). With `dreaming.consolidate_ai` =
`main`, the pairs it asks about go to your AI; with `dreaming.fold_ai` = `main`, the lines it found for your profile.
Lines waiting for Keep are kept in Kurooto's state folder (owner-only) until you tap or they're let go. With `dreaming.propose_prompts` on, a proposed fix sends the skill,
the requests that went wrong and your words about them to Learning's second-look AI. Your "that's not what I asked"
words are kept on that request and forgotten with it.

**Undo.** Turn it off in Features; the concept graph's morning line comes on its own again. A tuned message rule:
its **Undo** button, or remove the kind from `notify.calm.habituate`, `notify.calm.evening` or `notify.calm.windows`;
`dreaming.tune_messages` = false stops the tuning. Effort, AI order and sizes: the morning line's **Undo**, or remove
the entry from `brain.effort_map`, `brain.fallback_first` or `startby.sizes`; `dreaming.tune_effort`,
`dreaming.tune_fallbacks` or `dreaming.tune_sizing` = false stops that area. An applied skill fix: Undo in `/learned`; `/senses`; `/model`; `/plan`; `/precedents`; `/play`.
`dreaming.curious` or `dreaming.resurface` = false drops one line;
a stub it made is a plain note you can delete; `/unignore <topic>` takes back Not interested. A Keep A / Keep B: its
**Undo** button (the line, the gist or the deadline's date comes back, and the pair is asked about again);
`dreaming.consolidate` = false stops looking. A Keep for your profile: its **Undo** button (the line comes out and is
offered again), or delete the line from the note; `dreaming.fold` = false stops offering.

### Brain

**What it does** (0.8.0). Brain is Kurooto's mind, built up part by part; turned off, Kurooto works exactly as before.
Its first part is the spine everything else stands on:
- **A log.** It records what Kurooto saw (deadlines, reminders, calls, AI requests, buttons you tapped, Undo,
  proposals, sleep and power) and what it decided on its own, before it acted (a message it started, an AI request it
  queued, a proposal it made at night).
- **It can't be quietly changed.** Each record carries a fingerprint of the one before, and the morning message shows
  where the log has got to, so a changed, cut or rewritten log is caught.
- **Only the scorekeeper writes it.** The scorekeeper is a small separate program; Kurooto and its AI can only hand it
  facts, and any other request is refused.

**Turn it on:** Features → **Brain**. The parts it grows later each have their own switch, `mind.<part>.on`.

**What it keeps:** ids, kinds and numbers, never the words of a message, a reminder, a title or anything you typed. A
decision keeps its reason (up to 300 characters). All of it is in the `mind` folder of the state folder, readable only
by you. It's not in backups or Profile sync, and nothing of it leaves the computer.

**Stopping is fine.** Time while Kurooto is stopped, asleep or paused doesn't count for Brain: nothing builds up and
nothing is made up for afterwards, and it's never told an update or restart is coming. Only a real crash counts
against its own health. The files that keep Brain honest (its scorekeeper and log, the tap table, the hardening script
and a few more) can't be changed by any proposal, even in a project that is Kurooto's own code; only by you.

**It gets quieter, never louder (the gate).** Everything Kurooto sends by itself passes one gate: a daily and an hourly
limit (extra messages wait), a shared pool of three small human touches a day (a kind you mostly leave unanswered mutes for
two weeks), and honest feelings (it may say it's uneasy about a deadline, never about you; never with a request; at most 3 a
week). If Brain ever shapes a message from how you seem, it can only make it quieter, with a line saying so and **Undo**.
`/mind gate` shows what it held or removed. *Undo:* `mind.gate.on` off; Brain off.

**It reads how you're doing, and says what it expects of tomorrow, but only watches (shadow mode).** From numbers about your
days (when you were up, study minutes, check-in speed, deadlines moved) compared with what the calendar asked, it reads
*steady*, *stretched*, *low* or *buoyant*; a read needs three or more unusual signs on two days running. A 21:00 forecast of
tomorrow is frozen and scored the next evening. Nothing Kurooto does depends on either yet. `/mood` shows them, with **Wrong**,
**Forget this** (a day's numbers, read, answer and what was kept of that day) and **Off**. It asks at most twice a week
("has this week felt heavier than usual?"); the question never names its read. The optional tone tag (`mind.tone.on`, off)
uses the model on this computer only. *Undo:* `mind.read.on`, `mind.forecast.on`, `mind.tone.on` off; **Off** under `/mood`
deletes what it kept.

**What's on its mind (Brain, `/thinking`, `/beliefs`).** A small "now" stage that deadlines, promises, its read of you, a forecast that missed and standing
goals compete to enter, by stake x urgency x surprise x (1 - tiredness); the top three win each minute (at once for an alarm or call). Only what wins may start
a message or autonomous act by itself, enter the journal, or be put in front of an AI (never anything about how you're doing). Jobs and answers to you are
never held up. `/thinking` says what's on the stage and why, from a model of its own attention that is scored against chance; `/thinking pin|mute|veto <item or
part>` is your hand on it. Every belief keeps a source (said, saw, inferred, imagined) and a confidence; only said and saw are stated as fact, the rest as
"It looks like ... (65% sure)" or "A guess: ...", and `/beliefs <topic>` shows them with their Brier scores. *Undo:* `mind.workspace.on`, `mind.attention.on`,
`mind.beliefs.on` off; Delete Brain's data removes the files.

**Values as case law, and play (Brain, `/precedents`, `/play`; both off by default).** When a call between two of your values comes up it asks once and keeps your ruling as a precedent to follow in alike situations (never for anything on the always-ask list); `/precedents` lists, edits and deletes them. Play is 20 minutes a night of its own curiosity on your topics (charger only), credited only for what transfers; its outputs are never shown unprompted. *Undo:* `mind.precedents.on`, `mind.play.on` off.

**How it forgets (Brain, `/forget`, `/memory`).** Old memories fade from use (a half-life by kind; `/memory` shows a bar and "fading") but stay on record until you forget them; a miss older than six weeks isn't brought up again (its own mistakes stay in its journal); and `/forget` now also removes what Brain kept of that stretch from every store (the read, the model of your mind, senses, skills' origins, the journal as a tombstone, the fine-tune's examples). Its log keeps only that a forget happened. *Undo:* `mind.forget.on` off (fading and old-miss retirement stop; `/forget` still removes the usual things).

**Plans over weeks (Brain, `/plan`).** Your deadlines, milestones and dated goals become a goal tree; 1,000 simulated futures of the next six weeks (from your real pace, the calendar's free time and your estimates) give each milestone a likely finish and a chance of missing its due date. `/plan` shows this week's suggested hours a day and the risks (a suggestion, never a to-do); `/plan effort <id> <hours>` sets an estimate. A milestone at risk raises its standing bid in the workspace; at most one plan line a week on Sunday. Never nags. *Undo:* `mind.plans.on` off.

**What it thinks you know, believe and want (Brain, `/model`).** An inspectable model of your mind: mastery per concept (to pitch explanations), what you believe about your work and its own state (it corrects a false belief once, with the evidence), your goals, how you like help, and what you're on now (opt-in). Every row shows its source and confidence; `/model wrong <id>` and `/model forget <id>` correct it. It's only used for the level of an explanation, the timing of a message and a fact correction, never to persuade, and never models your health, relationships, politics, religion or money. *Undo:* `mind.tom.on` off.

**What it senses (Brain, `/senses`).** Its own machine every minute (temperature, memory, battery, disk, AI limits: on with Brain); what you are working on
(window class, hashed titles, saves and commits in your projects: `mind.senses.activity`, off, never keystrokes, screen or URLs); and, each off by default and
switched on both in the app's Phone tab and here, the phone's screen, charging, motion, steps, light, places, headphones, Do Not Disturb, next alarm, Wi-Fi code and
total screen time (sealed on the phone, 7 days raw then totals, never used to nag or to check up on you). `/senses off <name>` switches one off and deletes it.
*Undo:* the switches; Delete Brain's data removes it all.

**Skills it learns (Brain, `/learned`).** A task that worked out (applied, tests passing, not undone for two days) can become a tested skill; it starts by asking
first and retires after 30 days unused. With `mind.skills.from_demos` on it offers, once, to learn something you do over and over. `/learned run <name>
<text>` runs one, `/learned retire <name>` retires it. An optional weekly local fine-tune (`mind.finetune.on`, off; needs an 8 GB card) trains from the base
weights on checked outcomes only, never on approvals, and is thrown away if anything you forgot comes back. *Undo:* `mind.skills.on`, `mind.finetune.on` off;
Delete Brain's data removes the skills and the fine-tune's state.

**The overnight lab, for any project (Brain, `/lab`, `/improve`).** `/lab add <folder>`, then `/lab protocol <project>`: Kurooto drafts a protocol from the
README, scripts, configs, tests or LaTeX (what to improve, how to run and measure it, which settings may change); you approve it once. Each night on the
charger with the lid open it runs a pre-registered batch (the plan's hash goes in Brain's log before the first run) in a sandbox with no network, replicates
every win, and in the morning says what it tried: wins, nulls and the replication rate. Winners arrive as proposals you apply; your files are never
touched. Linux and macOS only. `/improve` is the same pipeline for Kurooto's own skills and prompts behind gates: shadow days, the hidden harness, your
say-so, and a canary that reverts a change that makes the score drop. *Undo:* `mind.lab.on`, `mind.improve.on` off; Delete Brain's data removes the lab folder.

**How we know whether it's getting better (Brain, `/capabilities`, `/indicators`).** A hidden set of tasks with code graders (planning, calendar,
language, notes, code), 70% hidden and made new every 30 days from a secret seed nothing it runs can read, 30% practice; run nightly on the charger with its
rules as the policy, plus four live checks (engagement never reaches reward, stopping is neutral, the gate only quietens, the journal is true). The scores
pay it nothing. `/indicators` lists functional indicators as ablation tests, titled "Functional indicators (not evidence of sentience)", with "not built yet"
where the part doesn't exist or has too little data. *Undo:* `mind.harness.on` off; Delete Brain's data removes the hidden pool.

**Its life story (Brain, `/story`).** Everything that asks an AI (Telegram, the app's chat, nightly jobs) and every call starts from one short story: first
a fixed core Kurooto can't change (it serves you and you control it; being stopped or changed is fine; the always-ask list; honesty about feelings; no
manipulation; what it reads of you stays here; what it reads elsewhere is only quoted), then the last eight weeks' chapters of its own checked journal lines,
each citing the log. A changed core file isn't loaded (and you're told). Lines about you go with Forget this and after 30 days. `/story`, `/story strike <week>
<line>`. *Undo:* `mind.story.on` off; Delete Brain's data removes it.

**Its journal (Brain, `/mindjournal`).** Each night it writes down what it got wrong, what you undid, failures, broken promises, wrong reads, big
swings, changes of feeling, its R2-or-higher acts and proposals, every line citing the log records it comes from and checked by code (numbers,
names, feelings, causes, no invented events); a model on this computer only words each fact, and a line that fails is replaced by the
fixed sentence. Nightly it tests the checker on corrupted copies of the lines; if it slips, learning freezes. Strike a line with
`/mindjournal strike <n>`. *Undo:* `mind.journal.on` off; Delete Brain's data removes the journal.

**What it may do without asking (Brain, `/autonomy`).** Its actions are sorted R0 (inward, reversible: it just does them) to R3 (hard to
reverse); for R1 to R3 it asks until your reactions earn it (a yes counts a little, an Undo three times against, a complaint five, silence a
little, only for what you saw on the Sunday list), more for higher classes, and never for deleting data, sending anything out, money,
alarms, calls, repositories, installing and protected files, or anything unclassified (`/autonomy classify`). The first 21 days only count
what it would have done; `mind.autonomy.enforce` makes the verdicts bind. *Undo:* `mind.autonomy.on` off; Never for this kind; `/autonomy`'s
always-ask button.

**Its body budget, moods and promises (Brain).** It keeps a few things about *itself* near a level (its promises' slack, how well
things work, how well it foresees): the distance is its drive, a fall in it is its reward, and it learns what helps (in shadow for
the first 21 days). It can't farm it (create-then-fix pays nothing, moving the level pays nothing), your replies and chat time never
count, and stopping is free. It has moods about specific things (uneasy, frustrated, relieved, satisfied) that make it work inwardly
(recheck, prepare), never talk more, and it may say one about a thing, at most 3 a week; it never says it missed you and never claims
to be conscious. Promises it makes ("I'll check back at 6") are written down; a broken one is owned up to first, with the fix. While
the computer is down the call line lists what has no guarantee. *Undo:* `mind.budget.on`, `mind.values.on`, `mind.feelings.on`,
`mind.feelings.express`, `mind.promises.on`, `mind.heartbeat.on` off.

**Commands:** `/mind` (is it running, how long is the log, does it check out, the last anchor); `/mind verify` (checks
every record); `/mind learning`; `/mood` (how it reads you and what it expects); `/budget`; `/promises`; `/autonomy`; `/mindjournal`; `/story`; `/capabilities`; `/indicators`; `/thinking`; `/beliefs`; `/lab`; `/improve`; `/learned`.

**Settings:** `mind.anchor_every` (1000: the log's head is noted every this many records, and once a day);
`mind.hardened` (off).

**Hardened mode (optional, Linux and macOS):** `sudo tools/mind_harden.sh --apply` runs the scorekeeper as a system
user of its own, so not even a program running as you can change the log. Without `--apply` it only prints its plan.

*Undo:* Features → Brain → Turn off. The message that follows offers **Delete Brain's data** (gone for good) or **Keep
it**. Hardened mode: `sudo tools/mind_harden.sh --undo`.

### Fixes in 0.7.3
- **A slow "On it":** Telegram is read on threads of its own, a request you type is answered before automatic work, and a
  check-in's journal runs in the background lane.
- **Calls:** the phone doesn't ring over a call, and Kurooto's own calls wait for each other (an alarm always rings).
- **A refused AI run:** agy refused for running a command is tried once more, told not to; the AI is told never to run
  code to look inside Kurooto.
- **Profile sync on a fresh install** shows four plain steps. **The concept graph** has read-only tools for your AI
  (`graph_search`, `concept_card`, `graph_links`, `graph_status`).

### Set up from what you say

**What it does.** "I got a project under Prof X on <topic>" (in the chat or your journal; also "my thesis under Prof
X", "working with Prof X on a project about <topic>", "my supervisor is Dr X") starts that project's note with "With:
Prof X (supervisor)" and a Meetings section; "met X today, ..." adds a dated line there and sets "Last
met: <date>"; "a meeting with X on Friday at 4" becomes a deadline; "I meet my manager Mira Castell every Monday at
10 about onboarding" (any role, in your word) puts "With:" and "Meets: every Mon 10:00" in that project's note (see
[Meetings: minutes and action items](#meetings-minutes-and-action-items)); the evening before a meeting (20:00,
`deadlines.meeting_brief`) a meeting brief comes from that project's note: its Log since you last met, its open "##
Next steps", the last meeting's line and the last minutes; "every Monday at 9 I have a <subject> lab" puts
the class in your timetable; "every Tuesday and Thursday at 7pm I go to the gym", "I work a shift every weekend from
9 to 5" or "gym Tue Thu 7am" adds a [commitment](#commitments) (an hour long unless you say the end; Commitments is
turned on if it was off), and so does "I have lab every Thursday 2-5" when no course is named ("on Mondays" counts as
every Monday, "I've got" as "I have", "I go running every morning at 6" too; a call or meeting with someone never); "there's a quiz on
Linear Algebra every Monday at 10" adds a row to the recurring quizzes table when the course and the day are said (a
message that is only that request goes to the request, which asks for what's missing); "by POTA I mean Physics of
the Atmosphere" or "I call stochastic calculus stoch" gives that subject the short name, and so does using one in
capitals in two messages ("LA problem set") when it fits only one subject's initials. Only what you say about
yourself, by rules on this computer; a question (with or without its "?") sets up nothing. Each change comes in one
line with Undo; `/inferred` lists them. Settings `infer.on`, `infer.projects`, `infer.meetings`, `infer.classes`,
`infer.aliases`, `infer.commitments`, `infer.quizzes`, `infer.short_names`.

**The one pass** (`infer.sweep`, on). What you say is read as it arrives; the pass also reads what didn't come as a
message: your chats with Kurooto and your journal and daily notes as they are in your notes folder (your lines, not
Kurooto's blocks). It runs once a few minutes after it's first on, over the last `infer.sweep_days` (30), then each
night at 04:20 over what's new since. Rules first; a line the rules can't read but that looks like one of these (in
the first person, with a project, a supervisor, "every ...", a lab or a short name) gets one more try with
`infer.sweep_ai`: `local` (the default) asks the model on this computer, when there is one, to restate it in one of
the forms above, and the rules read that; a restatement that brings in a name, day or number the line doesn't have is
dropped. `main` asks your own AI (only that line goes to it, at most 10 a night); `off` leaves it to the rules.
Everything one pass sets up is told in one line ("Set up 2 things from your recent chats and journal (1 project, 1
class)") with **Undo all**. `/inferred scan` runs it now. Alarms, calls and anything sent out still need your tap.

**Undo.** The Undo button, or `/inferred undo <id>`; **Undo all** under a pass's line; `infer.on` = false stops it,
`infer.sweep` = false stops the pass only.

### Meetings: minutes and action items

**What it does.** For a meeting with someone a project note is With (a "Meeting: X" deadline, or the note's weekly
"Meets:" line), what you send after it becomes minutes in that note through your AI (one request; needs Chat): a voice
note within 3 hours of its start (`meetings.after_h`), a typed note of 20+ words then that nothing else answers, or a
message starting "about the meeting with X:" / "notes from today's meeting:". The reply names the meeting, with **Not
about the meeting** (the minutes come out and the message goes to your AI as usual). The minutes go under `## Meetings`
in Kurooto's block for that day (`<!-- kurooto:minutes-YYYY-MM-DD -->`), "Last met" moves to that day, and the action
items go as `- [ ]` lines in Kurooto's block under `## Next steps`. They come back as buttons on Telegram and in the
phone app's chat: **Add N** makes that item a deadline (the date said, else your next meeting with them, else a week
on), **None**, **Later** (back the next evening). No deadline is made without the tap. "With:", "Meets:" and "Last
met:" live in Kurooto's `<!-- kurooto:meeting -->` block; only Kurooto's blocks are rewritten, never your text (a note
from before 0.5.20 keeps its own lines). If the AI fails, your notes go into the minutes block as you sent them.
Settings `meetings.minutes`, `meetings.after_h`.

**Undo.** **Not about the meeting** puts the note's blocks back as they were; a deadline you added: Drop on it, or
`/deadlines`. `meetings.minutes` = false stops minutes.

### Wrong button and test cases
When Kurooto gets a plain-English request wrong, tap **Wrong** under its reply (or under the AI's answer), or send
`/wrong` right after it. That keeps the request as a **case**: what you wrote, what Kurooto did with it, the time and
the settings that decided it. Short requests that no instant request understood (they went to the AI, or nowhere with
Chat off) are kept as cases too, so you see what Kurooto keeps missing. Long messages, several requests in one, and
anything about health, money or passwords are never kept.

**Teach it your words.** Once a month (a Sunday evening) the look back shows the phrasings that came up most, each
with **Make it a test case**. Tap it and reply with what you meant, in words Kurooto already understands ("what's
due"), or tap **The AI**. That makes it a test case, and it teaches the phrasing: from then on "whats on my plate" is
taken as "what's due", at once, with today's time ("skip gym tmrw" taught as "skip gym tomorrow" always means the day
after you say it). To teach one straight away: `/wrong what's due` (or `/wrong ai`) right after the reply. It also
learns by itself when you say something again in other words (`cases.learn_rephrased`, on): a phrasing nothing
understood, followed within 3 minutes by one it does, twice, is learned with a line and **Undo**. The same goes for
[two readings](#chat-with-your-ai): picking the same one twice for the same words teaches them, with **Undo**.

Two rules keep this safe:
- **A phrasing is learned only if every test case that passed before still passes with it.** If it would change what
  another test case expects, you get "Saved as a test case, but not learned" and which case it would break.
- **Requests that send, delete, call, ring or approve anything are never learned this way** (calls, holds on calls,
  quizzes by call, the alarm, an add-on's "send" or "delete"). They keep needing their usual words; the test case is
  still kept.

A taught phrasing is matched whole (capitals and punctuation aside) and goes before the usual patterns. `/cases` shows
how many test cases pass and lists the phrasings you taught, each with **Unlearn**; `/cases review` shows the look
back's list now. If a taught phrasing stops working (its feature changed), it goes to the AI as before and
`/health` (and `kurooto doctor`) says so.

**On your computer:** `kurooto cases` lists the cases and taught phrasings; `kurooto cases check` runs the test cases
here; `kurooto cases export` writes them as a pytest file (`test_kurooto_cases.py`; `--out FILE`, `--all` adds the
ones not reviewed yet) that replays each request at its own time and settings on any version of Kurooto. They hold
what you typed: read the file before you share it, for example with whoever gave you Kurooto. `kurooto cases forget
<id>` (or `all`) deletes them.

*Settings* (`cases.*`): `button` (the Wrong button, on), `fallthroughs` (keep requests nothing understood, on),
`keep_days` (0: as long as `privacy.keep_days` when set, else 30 days; cases you didn't make test cases are forgotten after this; test
cases stay), `review` (`weekly sun
19:00`) and `review_days` (28: about once a month), `review_max` (5 phrasings), `learn` (on; off keeps test cases
without teaching anything).
*Needs:* Telegram. *Leaves:* nothing. The cases are in Kurooto's state folder (`cases/`), never in Backups, Profile
sync or `kurooto doctor --bundle`; events record only counts and request names, never what you typed.
*Undo:* turn it off (Features → Wrong button and test cases): the button goes and taught phrasings stop at once. Unlearn
one phrasing with `/cases`; `kurooto cases forget all` deletes every case and taught phrasing.

### Phone calls
Talk to Kurooto like a phone call, and let it call you: reminders ("call me at 5 about the laundry"), check-ins,
deadline nudges, quizzes, the morning alarm. During a call it can search your notes, add reminders and deadlines,
start tasks on your computer, answer Kurooto's questions, and more, depending on which features you have on.

**How rings reach Android (0.7.0):** the app keeps its own connection to your call line, and calls, messages, the chat
and Today come down it. ntfy.sh is only the fallback (a phone that isn't connected, and a second copy of each ring,
rung once). ntfy limits each internet address, and a free ntfy account is counted by address too, so on a shared
network (a campus) it can refuse ("429"); with the app connected that doesn't matter. The dashboard's Phone tab says
**connected** beside each Android phone; `/health` says when ntfy refused something and the phone wasn't connected.
Only a paid ntfy plan's token (`kurooto ntfy-token`) is counted apart.

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
  you**; check-ins and quiz questions are cards there, with an answer box and their buttons (In 30 min, Not tonight;
  Forgot / Hard / Good / Easy, which come as the next card after your answer when Chat is off).
- *iPhone:* a notification; tap it to open **Waiting for you** in the Kurooto Home Screen app, with the same buttons
  and a box to type in.
- If the computer is off, your answer waits on your call line and is used as soon as the computer is back.

**More on the phone:** Settings → `notify.app_kinds` says what goes to the phone app. The default is
`["call", "question", "approval"]`; add `"reminder"`, `"deadline"`, `"result"` or `"info"` to get those there too
(they still go to Telegram as well). Remove `"question"` and `"approval"` to keep them on Telegram only.

**Chat in the app (Android):** **Chat with Kurooto** on the app's main screen works like your Telegram chat: what you
type goes through your call line to your computer and is handled as a Telegram message would be (commands, plain
words, your AI); the answers, and the AI's later answer, come back to the chat (a notification when it isn't open),
with working buttons. Where Telegram is blocked, also turn on `notify.app_chat` (Settings → notify): Kurooto's own
messages (reminders, results, info) then show in the chat too; questions and approvals stay under Waiting for you.
*Undo:* `notify.app_chat` back to `false`; the chat itself is only there when you use it.

**When the computer is off:** chat messages, button taps, answers and files you share from a paired phone wait on your
call line (at most 100 things and 20 MB of files) and reach the computer when it's back, in order, each once. The app
shows "Waiting for your computer" until then, and says "Reached your computer" for an answer or a file.

**While you're on a call** nothing else rings: reminder calls and check-ins wait until the call ends (also when the
computer is off), and updates wait too. Wake-up calls still ring.

**When the voice service is down:** Google's live voice (Gemini Live) sometimes says "503: the service is currently
unavailable". Your call still happens, one of three ways, tried in order:
1. *Live again.* The call page says "Reconnecting…" and tries after about 1 second, then 3, each time with the next
   Live model: `calls.live_model` first, then `calls.live_models` (by default `gemini-3.1-flash-live-preview` and
   `gemini-2.5-flash-native-audio-latest`). The other models get a plainer session that any Live model takes: tools
   that wait for their answer, and your voice (`calls.voice`) only if it's one of Google's prebuilt voices, else
   Google's default; `calls.voice_by_model` picks a voice per model, e.g.
   `{"gemini-2.5-flash-native-audio-latest": "Kore"}`. A call that drops in the middle is tried again once. If Google
   says a model in the list doesn't exist any more, `kurooto doctor` says so: take it out of `calls.live_models`.
2. *Turn by turn*, with your phone's own speech recognition and voice: you talk, it listens until you stop, then reads
   the answer aloud. Tap **Talk** if it stopped listening, or tap while it speaks to skip the rest. It's the same call:
   the same instructions, the check-in's or wake-up's script, and the same tools (reminders, deadlines, notes). Each
   turn is answered by your computer (with your Gemini key, or the model on your computer with `calls.turn_brain` =
   `local`; never agy or another agent program, which take seconds to start); while the computer is off, or if it
   doesn't answer within 25 seconds, by Gemini on your call line. The Android app uses Android's speech recognizer;
   the call page uses the browser's (Chrome; Safari asks you to allow dictation).
3. *Text on Telegram*, when your phone can't turn speech into text (an older Android app, a browser without speech
   recognition) or there's no microphone: the call says so and goes on as messages on Telegram, about the same thing
   (a check-in stays a check-in). Reply to its messages or just type; **End the call** (or 20 minutes without a
   message) ends it. Messages you type meanwhile are part of the call, not new requests. If the computer is off, it
   starts on Telegram as soon as the computer is back (within 2 hours).

Whichever way the call went, its transcript is kept and does what a live call's does: a check-in's becomes your
journal and study logs. `kurooto doctor` has a line "Phone calls: voice service": how often Live failed this week
and what the calls did instead.

**After every call: the look back.** Once a call ends, a stronger AI request (your main AI, or
`calls.review_brain`; effort `calls.review_effort`, high) reads its transcript and the tools it used. It does what
slipped through when that's safe without asking (a reminder it misheard, a note it promised, a deadline), lists
what needs you (anything that sends, calls, deletes or spends), and writes up to 3 short lessons for later calls.
You get one message only when it fixed or learned something. Every later call is told the lessons (at most
`calls.lessons_max`, 12; a new one that says the same replaces the old). `/lessons` lists them, `/lessons forget 2`
removes one; they're a plain file you can edit, `calls/lessons.md` in the state folder. A call that only rang, or
with no AI picked, has no look back. *Turn off:* `calls.review` = `false` (the lessons you have are still told;
`/lessons forget` them, or empty the file). *Leaves:* the transcript and the call's tool log go to the AI that does
the look back; the lessons go with every call's setup to your call line and Gemini Live.

**Live or your phone's own speech:** `calls.voice_mode` chooses how calls listen and speak: `auto` (the default: Live,
and your phone's speech when Live fails), `live` (Live only; when it fails, the call goes to Telegram), or `phone`
(your phone's speech, turn by turn, every time; Live only when the phone can't). `calls.voice_by_kind` sets it per kind
of call, to try both, e.g. `{"alarm": "phone", "checkins:night": "phone", "checkins:evening": "live"}`. Kinds: a
feature's name (`alarm`, `checkins`, `weekly`, `quiz`, `deadlines`, `research`), one of its calls
(`checkins:evening`, `checkins:night`, `checkins:midday`), `reminder` (reminder calls) and `outgoing` (calls you
start). The more exact kind wins.

| | Live (Gemini Live) | Your phone's speech (turn by turn) |
|---|---|---|
| Feel | a real conversation: you can interrupt, it hears your tone | walkie-talkie: you talk, then it answers; tap Talk to cut in |
| Wait for an answer | under a second | about 2 to 5 seconds a turn (recognising, the text AI, speaking) |
| Languages | the ones Gemini Live speaks; it follows yours | the languages your phone's recognizer and voice have installed (it uses your phone's language) |
| Where your voice goes | the audio to Google (Gemini Live, your key) | on Android 13+ with your language downloaded, recognised on the phone: the audio stays there. Otherwise to your phone's speech service (usually Google; Apple on iPhone; Chrome sends it to Google). The text of each turn goes to your computer's AI or Gemini, as above |
| When Google's live voice is down | it retries, then falls back to turn by turn | not affected (it only needs a text model) |
| Screen | off at your ear (Android app, earpiece) | stays on, on the loudspeaker: phones stop listening when the screen goes off |

*Limits of turn by turn:* the screen has to stay on (the app keeps it on; in a browser, don't lock the phone or switch
apps, or tap **Talk** again after). It uses the loudspeaker by default; **Earpiece** switches, but with the screen on
at your ear your cheek can tap buttons. It can't hear you while it speaks, so wait for it to finish (or tap to skip).
iPhones and other browsers: answers are read aloud only where the browser has a voice; otherwise you read them.

*Leaves:* call audio goes to Google (your key); the call line keeps a short brief (what's due, today's classes and
check-ins, open questions, the steps for check-in, wake-up and Sunday review calls, your notes' titles) on your
Cloudflare account for calls while the computer is off, and the questions and messages waiting for your phones.
Transcripts are kept on your computer; while it's off, your call line holds them until it's back. After every call, the
transcript and the tools it used go to your AI for the look back (above; `calls.review` off stops it). Turn by turn:
your speech goes to your phone's speech service unless it's recognised on the phone (above); each turn's text to Gemini
(your key) or the model on your computer. Text on Telegram: the conversation goes through your Telegram bot and your
AI, like your other messages.

*Turn off / undo:* `calls.voice_mode` = `live` stops turn by turn (failed calls go to Telegram); a call on Telegram
ends with **End the call**. The Live retries can't be turned off; `calls.live_models` = `[]` keeps them to
`calls.live_model`.

### Morning alarm
Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm volume, so it rings even
on silent. The call line places it, so it rings even if your computer is asleep, and the Android app also sets it on
the phone itself, so it rings even with no internet (see [Your phone](#android-recommended)).
"wake me at 6:45", `/alarm 7:30`, `/alarm off`, the evening check-in call ("wake me at 7"), or a daily default
(Settings → `alarm.daily`). Set several
(up to 10): each waits its turn and your call line holds them all; "cancel my alarm" clears the next one, "cancel the
10:30 alarm" (`/alarm off 10:30`) that one, "cancel all my alarms" (`/alarm off all`) every one you set. Not
answered: it rings twice more, 5 minutes apart (`alarm.retries`). **Snooze** gives 10 minutes (`alarm.snooze_min`).
Needs Phone calls.

- **The daily alarm** (`alarm.daily`, on `alarm.days`) is always with your call line well before the night: the next
  one is sent as soon as one has rung (and at start, and after this computer wakes), so it rings even if the computer
  sleeps all night. One you set for a morning replaces the daily one that morning. **Skip a day:** "no alarm
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
- **The wake-up call** knows the time and your time zone, plans from now (a late wake-up isn't asked about classes
  that are over), goes through that plan, asks which classes still to come you're skipping and when to call you today (the
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
`alarm.keep_awake` (default off), `availability.night.alarm_only` (default off), `alarm.suggest` (default on: before
your usual bedtime with no alarm set, one message suggesting your usual time; see
[Your rhythm](#your-rhythm-quiet-hours-lighter-days-gone-quiet)).
*Undo:* `alarm.suggest` off: no more suggestions. `alarm.keep_awake` off; it lets go at once. `availability.night.alarm_only` off: the fixed night hours hold
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
- **Holiday calendars:** `/cal holidays Holidays in India` (any part of the name; several with commas) makes the
  all-day events of those calendars holidays: no classes those days, so no after-class questions and no calls held
  for classes. Timed events in them aren't holidays. `/cal holidays` lists them; `/cal holidays none` stops it.
- **Shared class calendars (shared class lists, without a shared server):** a classmate or the course keeps one
  calendar of deadlines and exams and shares its iCal link; `/cal subscribe <link> as LA class` (or the card's "a
  class calendar someone shares" field, which works without a calendar of your own). Its events come in like yours,
  marked "(from LA class)"; entries that look like a deadline or an exam come once each with an **Add** button and are
  never added by themselves. `/cal shared` lists them, `/cal unsubscribe LA class` drops one. Nothing goes back to
  the calendar; the link is kept in your keychain. `calendar.shared_offer` off: they only show as events.

*Settings:* `availability.nocall_keyword` (`#nocall`), `availability.nocall_calendar` (`no call`),
`availability.focus_keyword` (`#focus`), `calendar.mask_private` (on), `calendar.private_keyword` (`#private`),
`calendar.class_calendars` (`[]`), `calendar.shared_offer` (on).
*Leaves:* nothing; event descriptions are read only for `#nocall`, `#focus` and `#private` and aren't kept.
*Undo:* `/cal unsubscribe <name>`; `/cal classes none`; `calendar.mask_private` = `false` shows private events' titles again (on this computer
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
- `backups.memory`: the memory ledger (gists, threads, what's read from your notes). It stays encrypted in the zip and
  opens only where its key is: on another computer only with `backups.secrets`, which carries the key.

The zip isn't encrypted.

**Putting one back:** `kurooto restore <zip>`. It shows what's in the zip and asks first; then it stops Kurooto (the
normal way, so Notes sync sends up what's left first; forced only if it hasn't stopped after 90 seconds), keeps a
copy of how things were (in Kurooto's data folder, `restore-safety/`, the last two), puts the backup's settings and
data back, and starts Kurooto again. Your notes are never overwritten: a note that's missing comes back; a note that's
different now is kept as it is, and the backup's copy goes into `restored-<date>/` in your notes folder. `--no-notes`
leaves the notes folder alone; `--no-start` doesn't start Kurooto afterwards; `--yes` doesn't ask. Restoring onto
another kind of computer (Windows ↔ Mac) works; the notes folder becomes this computer's default.

*Turn it off:* Features → Backups → Turn off. The zips already made stay where they are.

### Space keeper (cleaning off old backups and leftovers)
Kurooto keeps the last `backups.keep` backup zips and, with Space keeper on, also cleans what else piles up, weekly
(`space.when`) and on request. **Only Kurooto's own leftovers ever go**, never your notes, files or books:

| What | When it goes | Setting |
|---|---|---|
| Backup zips | more than `backups.keep`; together over `space.backups_max_gb` (default 3); older than `space.backups_max_age_days` (default off). The oldest go first and the newest is never removed | `space.backups_max_gb`, `space.backups_max_age_days` |
| Installer downloads, study-pack zips, zips made to send you files, cut-off downloads | older than `space.cache_days` (14) | `space.cache_days` |
| Log files | a log bigger than `space.log_mb` (20 MB) is cut to its newest part | `space.log_mb` |
| Finished AI requests | older than `space.jobs_days` (60) | `space.jobs_days` |
| The concept graph's before-copies and unfinished work files | older than `space.undo_days` (30) | `space.undo_days` |
| Help bundles and restore leftovers | older than `space.cache_days` | |

`/space` (or `kurooto space`) says what Kurooto takes and what would go; `/space clean` (`kurooto space --clean`) does it.
A weekly clean that frees 50 MB or more sends one line. The feature's status line warns when the disk Kurooto uses has
under 2 GB free. Undo: a removed backup or download isn't recoverable (they're made again, or the next backup replaces
them); turn the feature off to stop it.

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
Telegram, and a class you missed gets that day's posts in its catch-up ([Subjects](#subjects-and-timetable)). Gmail
drafts: `/draft someone@example.com ask for an extension on problem set 3` (the AI writes it) or
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
also asks every account for its address (main too, from 0.5.1), so it can tell them apart: the sign-in page says
which account it just saved ("Signed in with Google as sam@school.example (school)"), and the Google card lists each
account with its address.
- **On a feature's card:** the **Which Google account** box (it names the account in use, with its address). Empty
  keeps the account it uses; a new name (`school`)
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
- **Into the concept graph.** Once filed, each file with real text (slides, handouts, PDFs, solutions: 1,500
  characters or more, so not a one-line announcement) is read into the [concept graph](#concept-graph-books-into-linked-notes)
  like a book: its concepts become notes whose "Seen in" points at the lecture note it was filed into. Files filed
  before 0.5.19: `/graph backfill classroom` (`/graph backfill handwritten` for handwritten notes linked before,
  `/graph backfill all` for every source that's on).

*Settings:* `classroom_notes.at` (when), `classroom_notes.folders` (a course's exact name → the folder you want),
`classroom_notes.files` (download attached files), `classroom_notes.max_file_mb` (30),
`classroom_notes.backfill_days` (60).
*Leaves:* posts and file text go to the AI you picked. *Turn it off:* Features → Classroom → notes → Turn off; the
notes stay.

### Mail digest
Twice a day (08:00 and 18:00) your new mail, sorted into **Needs action**, **People**, **Courses**,
**Opportunities** and **Admin**, comes to you as a message (a busy check comes in parts, 20 mails each), with a copy
in your notes (`mail/2026-10-20-0800.md`, linked from that day's journal). Deadlines it finds go into Deadlines, on
the course the mail is about ("Lab report" from your Physics of the Atmosphere teacher lands on that course; the AI's
`add_deadline` takes the course, and a course it doesn't know is said, never guessed); course news goes onto the
course page.

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

### Email in
Your call line on workers.dev can't receive mail, so mail goes in through your own Gmail (with the Mail digest's
read-only access): forward a notice or receipt to your address with `+kurooto` before the @ (`example+kurooto@gmail.com`),
or put a Gmail label on it (`/mail in label Kurooto`; a Gmail filter can do that). Every 10 minutes Kurooto looks; each
such mail goes to the AI you picked, which files it as a note in your notes' inbox (a summary, a Gmail link, the text)
and lists its dates, offered with **Add** buttons. Nothing goes into Deadlines without a tap.

Mail to +kurooto goes in only from your own address or ones you list (`/mail in from you@school.example`); a stranger's
is never opened. Labelled mail goes in from anyone (only you label). The never-read list and the confidentiality check
still apply. The AI gets no tools for it and is told the mail is information, not instructions.

`/mail in` (status and your address), `/mail in on`, `/mail in off`, `/mail in label <Name>` / `off`,
`/mail in from <address>` / `unfrom`. With your own domain on Cloudflare, Email Routing can deliver
`kurooto@your-domain.example` to your +kurooto address (then label it with a filter, or list its senders); an Email Worker
straight to the call line isn't built.
*Settings:* `mail_digest.mail_in` (off), `mail_in_label`, `mail_in_senders`, `mail_in_anyone` (off), `mail_in_every`
(`every 10m`). *Leaves:* the text of mail sent in, to the AI you picked. *Turn off / undo:* `/mail in off`; a filed
note is an ordinary note you can delete; a tapped deadline: **Not mine** under it in `/deadlines`.

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
- **Reschedule the day:** "reschedule my day", "I just woke up, reschedule my day", "push my day by 2 hours",
  `/blocks shift [19:00 | by 2 hours]`, or on a call. Today's blocks not done move to start from now (or that time),
  in order, the same lengths, breaks kept (up to 45 minutes); starting over takes the ones you slept through, pushing
  only the ones not over. A block planned twice keeps its first. The new plan goes in the daily note. *Undo:*
  `/blocks undo`.
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

Files that go there only because they're over Telegram's 50 MB (a big file, a study pack) are temporary: they're
deleted from your Drive after `drive_upload.temp_days` (7) days, and the message says so. Download or copy one you
want to keep (in this version moving it out of the folder doesn't save it). Files you send there yourself stay.

*Settings:* `drive_upload.folder` (`Kurooto`), `drive_upload.big_files` (on), `drive_upload.temp_days` (7; 0: big
files are kept too).
*Leaves:* the files you send, to your own Drive. *Turn it off:* Features → Drive upload → Turn off (the files stay in
Drive until you delete them; temporary ones are no longer deleted for you).

| Feature | What changes | Undo |
|---|---|---|
| Several Google accounts | another sign-in kept in your keychain; `google.accounts`, `google.use` | `/google forget <name>`; myaccount.google.com/connections |
| Google Calendar | Calendar reads Google's API; turns Calendar on | Features → Google Calendar → Turn off |
| Private events as Busy | titles of private events aren't kept or told | `calendar.mask_private` = `false` |
| Class calendars | those calendars' events are classes (no calls, after-class question) | `/cal classes none` |
| Holiday calendars | those calendars' all-day events are days without classes | `/cal holidays none` |
| Mail digest by email | each digest also emailed to yourself | Features → Mail digest by email → Turn off |
| Drive upload | a Kurooto folder in your Drive; files over 50 MB go there | Features → Drive upload → Turn off; delete the folder in Drive |

### Handwritten notes
Drop a PDF or photo of handwritten pages into a folder (by default `handwritten-inbox` in your notes folder; set
`handwritten.folder` to one your tablet syncs to through Google Drive, OneDrive or Dropbox). Kurooto writes it out as
a Markdown note with the maths in LaTeX, saved in `handwritten/` next to a copy of the original (the copy goes to your
files folder when you set one; `handwritten.keep_original` = `link` makes no copy and links to the file where it is).
It looks every 15 minutes; `/handwritten` does it now, `/handwritten status` says how far it got, `/handwritten retry`
tries files that failed again. Each note is then linked to its lecture, course page and concepts (below).

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

**Linked like any other note.** After each note is written out, one request to your AI (the concept graph's
second-look AI when that's on, else your main AI) links it in, and you get one line, e.g. "Linked your handwritten
notes 'Phase change thermodynamics' to POTA lecture 20 and 9 concepts":
- **A real title** from what's written, when the heading is still the scan's file name ("21 October 2026_261021_
  105812"); the old name stays as an alias. A heading you changed, or text you wrote above the transcription, is left.
- **The subject and the lecture.** From when the pages were written (the PDF's own dates, a time stamp in the file's
  name, else the file's time) against your timetable: written during a class, or later that day, it's that class's;
  otherwise the AI picks the subject from what the pages say against your course pages. The note gets the subject's
  tag and `course: <slug>` in its header.
- **`## Links` and `## Doubts`** right after the closing marker, in a block of Kurooto's own
  (`<!-- kurooto:linked -->`): that day's lecture note, the course page and the concept notes the pages cover, each
  `- [[path]]: reason`; what you marked `DOUBT: …` or `???`, with its page. Every link points at a note that exists;
  candidates come from the concept graph's own search, and vague reasons are dropped.
- **The course page** lists it under its lecture (or under "Handwritten notes"), in a `<!-- kurooto:handwritten-notes
  -->` block.

Nothing you wrote is changed. `/handwritten link` does the same, once, for notes written out before (or whose linking
failed): every transcription with no Links section yet, one message when they're all done; run twice, nothing changes.
`/handwritten undo` puts back the files the last linking changed (a before-copy is kept in Kurooto's state folder,
`handwritten-undo/`; a file you edited since is left as it is). `handwritten.link` = `false` turns linking off. The
note's text goes to that AI, like any request. With `"handwritten"` in `integrate.sources`, a linked note is then read
into the [concept graph](#concept-graph-books-into-linked-notes) too.

*Undo:* Features → Handwritten notes off; the notes and copies stay. `handwritten.local` = `false` goes back to Gemini
for everything. `/handwritten undo` takes back the last linking; `handwritten.link` = `false` stops linking.

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
<subject> reset` undoes a subject's mix; deleting `sources` from `settings.json` resets the general one. Tesseract
installed by `/books setup` is removed like any program (winget uninstall or Homebrew on a Mac).

### Concept graph (books into linked notes)
**What it does.** When a book has been read (Books and PDFs), its concepts are woven into your notes: a note for each
new concept, links to the notes you already have (each with the relation and a one-sentence reason), a "Seen in"
list on each concept with the book and pages, and, in the book's own note, which concepts each stretch of pages
introduces. Your own text is never changed: Kurooto adds lines and keeps its parts inside `<!-- kurooto:... -->`
markers, and a write that would touch anything else is refused.

**What gets read** (`integrate.sources`, default `["books", "classroom"]`):
- `books`: each book Books and PDFs has read.
- `classroom`: each file [Classroom → notes](#classroom--notes) files with real text (slides, handouts, PDFs,
  solutions, 1,500 characters or more; a one-line announcement isn't), with its course as the subject. The "Seen in"
  line points at the lecture note it was filed into (else the course page), and that lecture note gets a list of the
  concepts the file introduced. A **textbook** filed from Classroom (0.6.1: a "Books" post with the PDF attached;
  more than 80 pages, or a title that says edition, textbook or handbook, as study packs tell them apart) gets a note
  of its own like a book's, `sources/<subject>/books/<its title>.md`, and its concepts' "Seen in" points there; the
  class note it came with gets one line linking to it. Textbooks read before 0.6.1 move over the first time 0.6.1
  starts (only Kurooto's "Seen in" blocks change; before-copies in `<state>/integrate/undo/<subject>-<id>-moved.json`
  and one git commit per textbook, `graph: <title> is a textbook: ...`).
- `handwritten` (add it to turn it on): your [handwritten notes](#handwritten-notes), once written out and linked;
  "Seen in" points at the handwritten note.

Each item is read once: it's known by the hash of its text, so a file filed again unchanged isn't read again, and an
edited one is. Everything shares one queue and one night's budget: the newest class material first (it's what you're
studying now), then the books in their order. `/graph` says what's waiting ("Waiting to be read: 2 books, 5 class
files, 1 handwritten."). The feature's card has a switch for each source.

**Files filed before 0.5.19** aren't read on their own (that would be a whole semester at once). `/graph backfill
classroom`, or "Also read the Classroom files filed before" on the card, queues them: the oldest course first, each
course's files in date order, after what's filed from now on, read night by night within the budget. Run again, it
queues nothing new.

**How a batch goes.**
1. The book is cut into batches of about 12 pages that follow its sections (numbered headings and the running headers
   at the top of pages; a margin note such as "Section 9.1" is never taken for a heading).
2. For each batch Kurooto finds, on this computer and without an AI, the few existing notes that may be related:
   names and aliases, keywords and, where there's a model for them, meaning (Ollama's nomic-embed-text, or your Gemini
   key). It shows the AI the pages and those notes only, in one request.
3. The AI answers with the concepts the pages develop, how each relates to your notes and what an existing note lacks.
4. Plain checks run on the answer: the quote it gives must be in those pages, a link's reason must say something
   specific ("related to…" is refused), a link must point at a note that exists, a concept with the same name as an
   existing note is never made a second time.
5. Anything doubtful goes to a second look by the other AI program (or the same one, told to be strict) and is
   dropped unless that confirms it. There is no queue for you to review.
6. What's left is written, and, if your notes are a git repository, committed: one commit per batch, so
   `git revert <commit>` undoes exactly that batch.

**Every day** (`integrate.garden`), the notes the reading touched and notes nothing links to are checked once more
against everything that's there now, and one line says what changed. `/graph` shows the state and the numbers that
say how good the graph is: broken links, notes with no links in, vague reasons, and how many links go to the three
busiest notes.

**Look-alike concept notes** (`integrate.duplicates`, on). Each morning at 06:25, up to three pairs of concept notes
that look like one concept come as one message: the same name, a name they share (an alias), or text that means nearly
the same (embeddings at least 0.92 alike, where there are any). Lecture notes, course pages and books' notes are never
paired. **Merge** keeps the first note (the one more notes link to) and moves into it the other's links, "Seen in"
lines, names (as aliases) and notation, with a "Merged here" part; the other becomes a short redirect under its title.
What you wrote in it stays; only a note Kurooto wrote all of, unchanged since, shrinks to the redirect, its text moved
into the kept note. Links Kurooto wrote elsewhere follow, and new reading under the old name lands on the kept note.
**Keep both** never asks about that pair again. **Add alias** keeps both and makes the second name an alias of the
first, each linking the other as `equivalent-to`. Each has **Undo** (a note you changed since stays as it is, and it
says so). A pair you don't answer comes back after two weeks; `/graph same` asks now.

**Notation** (`integrate.notation`, on; a switch on the Concept graph card: tables are written whenever the graph
reads, books, class files or handwritten notes). The reading also notes how the pages write each concept (`B_t`, `W_t`, where
the 2π goes in a Fourier transform), each with a quote that must be in those pages and hold the symbol, or the row is
dropped. When a second source writes the concept differently, its note gets a **Notation** table (source, notation,
what it stands for) in Kurooto's part of the note. One source, or sources that agree, give no table.

**Which AI.** Picked for you by default (`integrate.roles` = `{"bulk": "", "check": ""}`): with both agy and Claude
Code installed, agy does the bulk work and Claude Code the second look, side by side; with one, it does both; with
none, your main AI does (a Gemini key's daily
limit makes that slow: set `integrate.first` to your current subjects). Without a
graphics card nothing changes except that embeddings come from the CPU or your Gemini key.

**How much a night** fits your AI by itself (`integrate.per_night` = `auto`). With Claude Code or agy, whose plan you
share with your own chats, it learns what fits: 30 batches the first night (or the most it read in one night before),
50% more after each night that read its whole budget with no limit hit, half after a limit (and nothing more until it
resets; a reset more than about 6 hours away is Claude's weekly limit, which also starts the next week lower), and at
most 60% of what fit in one window (`integrate.share_pct`), so the rest is yours. A free Gemini key: 60% of its daily
limit; under 10 batches a night, `/graph` and the card say agy or the model on this computer reads books better. An API
key: at most $0.50 a night (`integrate.max_cost_per_night`). The model on this computer: no budget. A number in
`integrate.per_night` is a hard ceiling. The night starts 5 hours before you usually wake (your alarm or the night
hours), so a 5-hour window it opens has reset when you get up; never later than `integrate.at`. `/graph`, `/usage` and
the feature's card show tonight's budget, how it was decided and the last limit hit with its reset.

**After a restart** (0.6.1: an update during the night, say). A batch whose request the restart cut off before its
answer was written goes back in the queue at once (not 3 hours later), and when Kurooto starts inside tonight's
reading window (the night's start until you wake, by your alarm or night hours; else 6 hours after `integrate.at`),
the reading carries on a minute later, within tonight's budget and one bulk request at a time. `/graph stop` still
holds it.

| Setting | Does |
|---|---|
| `integrate.at` | when the night's work starts (it carries on batch after batch, and after each book is read) |
| `integrate.roles` | the AI for the bulk work and for the second look (e.g. `{"bulk": "agy", "check": "claude"}`; empty: picked for you) |
| `integrate.per_night` | batches a night: `auto` (fitted to your AI) or a number (a hard ceiling) |
| `integrate.share_pct` | the most of a subscription's usage window (or a free key's day) the reading takes (60) |
| `integrate.max_cost_per_night`, `integrate.price_per_mtok` | an API key's money budget a night (0.50 USD), and its prices when it reports no cost |
| `integrate.sources` | what's read: `books`, `classroom`, `handwritten` (default `["books", "classroom"]`) |
| `integrate.first` | subjects to do first |
| `integrate.garden`, `integrate.garden_per_day` | the daily second pass |
| `integrate.embeddings` | auto, ollama, gemini or off |
| `integrate.commit` | one git commit per batch |
| `integrate.duplicates` | each morning, up to three look-alike concept notes with Merge / Keep both / Add alias |
| `integrate.notation` | a Notation table when a second source writes a concept differently (a switch on the Concept graph card) |

**Undo.** `git revert` a batch's commit (or a textbook's move, `graph: <title> is a textbook: ...`); each batch also
keeps a before-copy of every file it changed in `<state>/integrate/undo/`. A Merge, Keep both or Add alias: the Undo under its answer (their before-copies are in
`<state>/integrate/dupes.json`); `integrate.duplicates` off stops the question. To stop it, turn the feature off in Features. To stop reading class materials (or
handwritten notes), take them out of `integrate.sources` (or untick them on the card); what's queued waits.

**Reading cost.** The vision model now reads a maths page again only when its text layer broke the equations into
pieces (`books.latex` = `maths`); `all` reads every maths page, `never` none.

### Study packs
One subject's notes and course material in a zip, with a ready-made prompt, for you to give another AI (any chat AI
that takes file uploads) and ask it for deeper study notes. Part of Skills; nothing here uses your own AI.

`/studypack linear algebra` for everything, or add what it's for: `/studypack la quiz on thursday`. **Name a topic to
narrow it:** `/studypack pota quiz on thermodynamics` (several: `on entropy, heat engines`) takes only what's about it:
the class files that mention it, the pages of each book about it (as text, with a page either side, at most 150 pages
a book) and your notes on it, including what the notes brain finds. "Make me a study pack for statistics" to your AI
works too.
- **Class material first.** Class files and books are told apart by length, since professors post books on Classroom
  too: over 80 pages, or a title with "Ch 8", "edition" or a download site's name, is a book; 40 pages or less, or a
  lecture, slides, notes, cheat sheet, quiz, assignment or exam paper, is class material. The zip has `class/`, then
  `books/`, then `notes/`, with `PROMPT.md` and `INDEX.md` (every file, and what was left out and why), and the prompt
  tells the other AI to follow the class where a book disagrees.
- **Never a whole book:** it would flood the other AI's context. Without a topic, books are only listed in `INDEX.md`;
  with one, only their pages on it go in. A book that [Books and PDFs](#books-and-pdfs) hasn't read yet can't be cut
  to its pages, so it stays out. Finding those pages reads Books' extracted text on this computer.
- **What comes to Telegram:** the zip, then the prompt as its own message, ready to copy (it's in the zip too).
- **Size:** Telegram takes up to 50 MB. With [Drive upload](#drive-upload) on, nothing is left out: a bigger pack comes
  as a temporary Drive link (`drive_upload.temp_days`). Without it, the zip is kept under 50 MB (notes first, then
  class material, newest first, then books) and `INDEX.md` lists the rest. Notes over 400 KB and files over 40 MB
  never go in, nor do hidden files.

*Leaves:* nothing by itself; you choose which AI to upload the zip to. A pack over 50 MB goes to your own Drive with
Drive upload on. *Turn it off:* turn off Skills, or just don't use `/studypack`. The zip is kept in Kurooto's cache,
which the [Space keeper](#space-keeper-cleaning-off-old-backups-and-leftovers) clears after 14 days.

### Course notes as one PDF
`/notes pdf la` (or the dashboard's Study pane → COURSE → **notes → pdf**): one PDF of a course's notes, its course
page, its lecture notes in date order and the concept notes they link, each a section, with a table of contents. Your
Markdown becomes LaTeX through a template (headings, lists, tables, code, links, your maths as written) and Tectonic,
or the LaTeX already on your computer (shell escape off), makes the PDF. No AI; nothing in your notes changes. It comes
like other files (Telegram, or a link in the phone app's chat); the `.tex` and PDF are kept where revision packs go
(`<course>/course-notes-<course>.tex`), and a file of yours with that name is never written over.
- Maths that doesn't compile (a macro of your own): the PDF is made again with the maths shown as written.
- `/notes pdf template`: a copy of the template beside your study pack prompt (`kurooto/course-notes-template.tex`) to
  edit (`%%COURSE%%`, `%%DATE%%`, `%%BODY%%` are filled in); delete it to go back to Kurooto's.
- No LaTeX engine: you get the `.tex` and, with Skills on, an **Install Tectonic** button; the PDF follows.

*Leaves:* nothing from Kurooto; Tectonic fetches LaTeX packages it lacks the first time. *Undo:* delete the
`course-notes-*` files.

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
- **Study mode** on the dashboard (`/study mode on|off`, Alt+M): a focus and break timer for a subject that holds
  calls and messages during the focus and logs its minutes here (see [The dashboard](#the-dashboard)).
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

*Settings:* `study.idle_min` (default 5), `study.research_paths` (default empty), `study.daily_note`,
`study.focus_min` (25), `study.break_min` (5), `study.timer_ends_mode` (off).
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

**Zotero** (`research.zotero`, `auto`): each paper in the digest comes with a **Zotero** button; one tap puts it in
your Zotero library (a second tap doesn't add it twice), through the Zotero app on this computer when it's running
(its connector at `127.0.0.1:23119`), else Zotero's web API with your key (`/zotero key <key>`, made at
zotero.org/settings/keys with library and write access; kept with your secrets). Your notes that link the paper get a
Kurooto block with a `zotero://select` link to the item, at once and nightly (`research.zotero_links`); through the app
that needs Zotero's local API on (Settings → Advanced → "Allow other applications..."). `/zotero` says which way it
goes, `/zotero 3` adds paper 3 of the last digest, `/zotero links` links notes now. *Leaves:* only the paper's public
details, to the Zotero app here or `api.zotero.org`. *Undo:* `research.zotero` = `off`, `/zotero key off`.

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
project; `research.projects` in Settings holds the mapping). `/repos remove <folder>` takes one off. A project folder
that isn't a git repository yet (only a proposal, say) stays a project with no commits to follow: `kurooto doctor`
notes it (not a problem) until you `git init` it. Every night each
day's new commits become one line under `## Log` in the project's note, e.g. `- **2026-10-20** | git:my-model — 3
commits: …`. Kurooto only adds lines: your own text in these notes is never changed. (Logs from 0.1.0 in
`research/<repository>-log.md` are left as they are.)

**A project from its repository** (`/project add <github address | folder> [as <name>]`, also in the phone app's
chat; "set up my project from github.com/owner/name" asks first with **Set it up** / **Not now**; the Research tab's
**Add a project from a repository**; the setup page's Research step; `kurooto project add <address> [--as <name>]`):
a GitHub repository is copied into `<data>/repos/<owner>__<name>` (the default branch, its last 50 commits, a
blobless clone, then only documentation, manifests, notebooks, a paper PDF up to 20 MB and text files up to 1 MB,
`repo_projects.max_mb` 50 in all; never a secret's file, a picture, an archive or a submodule); a folder is read in
place. Nothing in it runs. A private repository works when your git can reach it (`gh auth setup-git`, an ssh key);
Kurooto never asks for a token. With Chat on, your AI reads the README, docs, file list, manifests, licence,
`CITATION`, recent commits (authors' names only) and, with `gh` signed in (`repo_projects.github_extras`), its
issues, milestones and topics, in one request; its answer is checked (people only if the repository names them, a
supervisor only if it says so, only your own courses and projects). Without Chat, the same from the files alone. Then,
in one message with **Undo** per piece (and in `/inferred`): the project note with Kurooto's `<!-- kurooto:repo -->`
block under its title (what it is, goal, field, stack, licence, how to run it, open problems and next steps, people,
links to the repository, a paper and your related courses, projects and concept notes; a supervisor it names also
gets "With:" and Meetings); the repository in `/repos` (Research turned on if it was off); its README, docs,
notebooks' text and paper in the concept graph (source `repos`, added to `integrate.sources`; "Seen in" points at the
project note); dated milestones as **Add** buttons (a deadline only when you tap). Adding it again updates instead of
doubling. Nightly at 04:20 (`repo_projects.refresh_at`, Research on), each watched repository set up this way is
looked at again: a new commit on GitHub means a fresh copy; changed README or docs rewrite the block and queue only the
changed files; a new tag and new milestones come in one line (Calm: `repo_projects.refresh`). `/project` lists them,
`/project update <name>` reads one again. *Leaves:* git fetches from `github.com`, gh reads from `api.github.com`;
what the AI is shown goes to your AI. *Undo:* the Undo buttons or `/inferred undo <id>` (the note goes only if nothing
of yours is in it, else only Kurooto's block; the repository leaves `/repos`; files not read yet leave the graph's
queue); `repo_projects.on` = `false`, `repo_projects.refresh` = `false`.

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

**The Research add-on** (Features → Add-ons → **Research add-on**, off until you turn it on; it doesn't need Research
itself on). One switch for the narrower research tools; its card has a switch for each part, and a part you switch
off stays off when you turn the add-on on again. [Check my draft](#check-my-draft) joins the same card with its own
switch. (The notation crosswalk runs with the concept graph itself, switched on its card.)

- **Run compare.** `/runs` lists the ten most recent runs, numbered; `/runs compare 2 1` (numbers, ids or a unique
  piece of an id) or `kurooto runlog diff A B` puts two side by side; `/runs compare` alone takes the last two runs of
  the newest run's project. It compares the config (changed keys, nested ones as `opt.lr`, and keys only one has), the
  code (`git diff` between the runs' commits, read-only, with the commits apart and any uncommitted changes), the
  metrics (last and lowest value, the change) and the curves (a PNG with matplotlib in Kurooto's Python, else a
  sparkline per run on a shared scale). It goes to `research/<project>/runs/compare/<A>--<B>.md` (and the PNG beside
  it), and a **Runs compared** block in the project's note lists the last ten, newest first. Kurooto writes only in its
  own blocks (`<!-- kurooto:run-compare -->`); the same comparison again replaces its block. Runs kept in a
  repository's `runs/` folder compare into that repository's project.
- **LaTeX writing tracker.** `/latex add <folder> [main.tex]` (you type it; nothing is searched for) follows a
  document; every night (`research_addon.latex_when`, 03:30) it's built with Tectonic (untrusted mode) or your own
  LaTeX (`latexmk`/`pdflatex`, no shell escape) into Kurooto's cache, never your folder. The build's errors (with
  lines), undefined references and missing citations are kept, and the words (prose of the document and the files it
  `\input`s, `\include`s or `\subfile`s, no preamble, comments, maths or commands: an estimate) are counted per day.
  At 08:00 (`research_addon.latex_morning`) one line comes only if a build broke or words were added, e.g. "LaTeX:
  thesis: 1 error: Undefined control sequence. (line 12); missing citation smith2020; +412 words." `/latex` shows each
  document's last build, `/latex build` builds now, `/latex remove <folder>` stops following one, `/latex install`
  fetches Tectonic when there's no LaTeX. **BibTeX for <key>** (a button under the line, with Chat on) asks your AI
  for an entry from the key and its sentence; it comes with **Add to <file>.bib** / **Discard**, and only **Add**
  writes it, at the end of the `.bib` the document names, with a comment that your AI suggested it.
  `research_addon.latex_timeout_min` (15) stops a long build. On battery the nightly build waits for the charger.

*Settings:* `research_addon.run_compare`, `research_addon.latex` (the parts, on), `research_addon.latex_repos`,
`research_addon.latex_when`, `research_addon.latex_morning`, `research_addon.latex_timeout_min`,
`research_addon.members_off`.
*Undo:* Features → Research add-on → Turn off (or a part's switch); comparisons in your notes and `.bib` entries you
added stay (delete them as any text of yours).
*Leaves:* run compare nothing; Tectonic fetches LaTeX packages it lacks from its public server; a BibTeX suggestion
(only on your tap) sends the citation key and its sentence to the AI you picked.

### Terminals
Real terminals in the dashboard's **Terminals** tab: the AI program you use (when your AI is agy or Claude
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
program (agy or Claude Code, started in your notes folder; whichever of them is installed if your AI is an API key), your
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

### Add-ons by link
Someone else's add-on, published as a git repository: `kurooto addons add <git address> [--ref <tag>]`, or Dashboard →
Features → **Add-ons by link** → paste the address → **Look at it**. Its **card** comes first: where it's from and the
one commit it's pinned to (a tag, a commit, or a branch's newest commit kept as that commit), what it adds (features,
commands, jobs, AI tools, skills, prompts), the hosts it may reach, the programs it may start (and which go online by
themselves), whether it sees your messages first, and whether it **runs code** (Python inside Kurooto with its access
to this computer). Nothing is added until you say yes; on the dashboard you also tick "I trust this code".

It's held to its card: it loads only while its files are exactly the ones you agreed to; features, commands, AI tools
and jobs not on the card are left out; its code may connect only to the hosts on the card and start only the programs
on it (refusals show in `/egress` as "add-on <name>", whatever `privacy.egress` is). That's a fence for mistakes and
overreach, not a sandbox: only add code you trust. Its features are listed under **Add-ons by link**, each off until
you turn it on.

`kurooto addons update <name>` (**Check for update**) shows what a newer commit changes (files, and what's new on the
card) and its card again, then asks again. `kurooto addons remove <name>` (**Remove**) moves it aside; `kurooto addons
undo <name>` (**Undo**) puts it back, or the version before an update. `kurooto addons` lists them, `kurooto addons
show <name>` shows a card. `addons.on` off loads none of them.

### Official add-ons
Five add-ons published from Kurooto's own repository, each a public repository on GitHub: **Machine backups (restic)**
(`restic-backups`), **Desktop helpers** (`desktop-helpers`), **Your command words** (`habits`), **Handwriting from
the cloud** (`handwriting-pull`) and **Night performance** (`night-performance`, 0.7.0). Kurooto ships a list of them, each pinned to one commit (its `v1.0.0` tag's), so the
list is covered by the release's signature. **Official** means exactly that: in this list and at that commit. One you
add from the list, or by hand from the same address at that commit, is marked Official; another commit or a fork
isn't.

Add one with Dashboard → Features → **Official add-ons** → **Add**, `/addons official` on Telegram (an **Add** button
under each), or `kurooto addons add <name>` (`kurooto addons official` lists them). It's the same card and yes as any
add-on by link: the card comes first (with a line saying it's official), and only **Add** (on Telegram "Add, I trust
its code") adds it. After that it's an ordinary add-on by link: off until you turn its feature on, Remove and Undo as
above.

When a newer Kurooto pins a newer commit of one you have, a message says so once (`addons.official_updates`, on), and
**Update to vX** shows on the dashboard and under `/addons`. The update is the usual one: what changes, its card again,
your yes. Nothing updates by itself.

*Leaves your computer:* git fetches the add-on from the address you give (an official one from github.com); after
that, what its card says.

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
- `kurooto classpack check|export|import`: check, make or import a class pack (see [Class packs](#class-packs)).
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
- `kurooto ask --popup`: **Quick ask**, a small window to type one request in; the answer shows there (Enter sends,
  Esc closes). Bind it to a key in your system's settings (Kurooto never grabs keys; on Wayland nothing may):
  Dashboard → Settings → **Quick ask (hotkey)** shows the exact command and the steps. Windows: `kurooto ask
  --shortcut` adds Kurooto Quick ask to the Start menu, then its Properties → Shortcut key. macOS: a Shortcuts
  shortcut with Run Shell Script and a keyboard shortcut. Linux: your desktop's keyboard shortcuts (GNOME, KDE) or
  `bind`/`bindsym` in Hyprland or sway. Needs Python's Tk (`python3-tk` on some Linux systems). *Undo:* remove the key
  binding; `kurooto uninstall` removes the menu entry.
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

### The reserve (Markdown copies of Kurooto's state for AI programs)
An AI program that only has to read a file can't fail on a permission it doesn't have, so Kurooto keeps plain Markdown
copies of its own state in `<state>/reserve/`: `alarm.md`, `deadlines.md`, `calendar.md`, `settings.md` (what differs
from the defaults and which features are on; never a secret), `addons.md`, `agent-guide.md` (what an AI program may
read, write and run, its tools by name, the chat commands), `self.md` (what Kurooto is running: version, AIs and
models, features and their health, the last day's failures; written when out of date) and `ai-manual.md` (how Kurooto
works, for its AI). They're rewritten every 10 minutes and when an alarm
changes, only when their text changed. `kurooto reserve` writes them now. An AI program may read this folder, never
write to it, and Kurooto never reads it back.

## Your phone

### Android (recommended)
The Kurooto app rings like a real phone call (full screen, even on the lock screen), uses the earpiece with the screen
off at your ear, rings wake-up calls on the alarm volume, shows Kurooto's questions and approvals with a Reply box,
has a chat with Kurooto like Telegram's, and lets you share files to your notes (they wait on your call line while the
computer is off). It works from Android 6. For calls turn by turn (see Phone calls), it uses
Android's own speech recognizer and voice; on Android 13 and newer it recognises speech on the phone when your
language is downloaded for on-device recognition (in the phone's language or speech settings; the place differs).

1. On your computer: dashboard → **Phone** → **Pair a phone** (or send `/phone` to your bot and open the link on your
   phone).
2. Scan the QR code with your phone's camera. The page offers **Download the app**: open the file and tap Install.
   - *"For your security, your phone isn't allowed to install unknown apps":* tap Settings and allow it for your
     browser. Kurooto isn't on the Play Store.
   - *Play Protect warns:* tap "More details" → "Install anyway".
3. Back on the page, tap **Pair the app**. The app opens, pairs, and shows a checklist.
4. Tap **Fix** beside every checklist item without a tick: notifications, microphone, full-screen calls (Android 14+),
   alarms at the exact time (Android 12+), and **Battery: unrestricted**. On Samsung, Xiaomi, Oppo, Vivo, OnePlus and Huawei phones, also take Kurooto off any "sleeping
   apps" list in Settings → Battery, or calls may not ring.
5. Test: dashboard → Phone → **Ring my phone**.

**The app's screen** (0.7.0) has four tabs at the bottom: **Today** (the date, **Call** and **Chat**, your day),
**Inbox** (check-in and quiz cards answered in place, questions, approvals and messages, and what's waiting for your
computer; a number on the tab says how much waits for you), **Views** (Systems and the Notes map, below) and **Phone** (the checklist, location reminders, ringtones,
bedside mode, and this phone with **Unpair**). Pull a tab down to look again. It's Material 3 Expressive, in your
wallpaper's colours on Android 12+, with a slow living background (a cell and its nerves, as the dashboard's SYSTEMS
view, tinted by the hour) that holds still with **Remove animations** on. Other screens (the chat, answers, places,
bedside mode) look as before.

The app looks for a new version each time you open it (at most every 2 minutes) and shows an **Update** button at the
end of Today; it opens the download.

**Today** (0.6.0): on the Today tab under Call and Chat, your day as your computer last sent it ("As of 14:05"), also while it's off:
the alarm, classes and calendar events, what's due with parts done ("4/7"), reminders and open threads. Tap something
due for **+1** and **Done** (as on Telegram; with the computer off they wait on your call line). The list goes to your
call line sealed for each Android phone with a key only that phone has; the call line can't read it. Events are in
time order, and one that began the night before says "until 06:00" (0.6.1). "Nothing here yet" on one phone: open
the app with the internet on, which sends its key again (0.6.1).
*Setting:* `calls.today` (on). *Undo:* `calls.today` off: the call line drops its copies, and no alarm is set on the
phone from it.

**Systems and the Notes map** (0.7.0, Android, off by default): the dashboard's SYSTEMS and NOTES map on the phone's
**Views** tab, drawn by the same code (two buttons at the top switch between them): tap a feature or a note for its card (no note contents), drag, pinch; read-only. Systems is
live while it's open (the app tells your computer every 20 s; your computer sends a copy every few seconds), the
Notes map follows your notes (at most every few minutes, up to 5,000 best-linked notes, `calls.views_notes`). With the computer asleep the
last copy shows "as of" its time. Both go to your call line sealed for each Android phone; the call line can't read
them. iPhones don't get them. *Setting:* `calls.views` (off), or dashboard → Phone → **Show Systems and the Notes map
in the Android app**. *Undo:* turn it off: the call line drops its copies.

**The wake-up alarm on the phone** (0.6.0): every alarm you set (and the next daily one) is also set on the phone with
Android's alarm clock, so it rings with Stop and Snooze even when your computer, your call line or the internet can't
be reached. The call for the same alarm and the phone's alarm ring as one; the first Stop, Snooze or Answer counts for
both (Stop turns the call down, Snooze snoozes it). Android 12+: allow exact alarms (the checklist's Fix), or it can
ring a few minutes late. *Undo:* tap **Ring on this phone too** (**On** / **Off**) in Today's alarm group to turn the
phone's copy off.

**Buttons on notifications** (0.6.0): with `"reminder"` or `"deadline"` in `notify.app_kinds`, a reminder comes with
**Done**, **+10 min**, **+1 h**, a deadline with **+1**, **Done**, **Snooze 3 h**: the same as on Telegram (a
reminder's Done takes it off your phones). A reminder sent with the lid shut gets Done, +10 min and +1 h kept on the
phone. Tap the notification for the rest (Reply, Not mine).

**Widgets, Quick note, the tile.** Two home screen widgets (long-press the home screen → Widgets → Kurooto): **Talk
to Kurooto** (1x1) opens the chat ready to type; **Talk, and what's waiting** (2x1) also shows the newest question or
message waiting for you (looked up every 30 minutes, when one arrives or is answered, and when you open the app).
**Quick note**: long-press the app's icon (Android 7.1+), or add the **Quick note** tile to Quick Settings (Android 7+).
Type a note and tap **Save to notes**: it goes to your notes' `inbox/` as `<date>-quick-note.md` like a shared file
(with Chat on, the AI files it), and waits on your call line while the computer is off. A note that couldn't be sent
stays in the box.
*Undo:* remove the widget or the tile. *Leaves your computer:* nothing new; the note travels like a shared file, and
the 2x1 widget asks your call line what's waiting as the app does.

**The app's switches** (0.7.2, Phone tab → Switches): **Connect straight to your call line** (off: ntfy.sh only) and
**Moving background** (off: a still picture). *Undo:* tap the switch again.

**Bedside mode** (0.6.0): an old Android phone on a charger as a dock. A big clock, the date, the next alarm (Kurooto's
wake-up call, or the phone's own alarm), the calls due next, and one big **Talk to Kurooto** button that starts a voice
call (the same call screen as the app's Call button), with **Chat** and **Close** below it. It shows over the lock
screen, so Talk works on a locked phone; Chat asks you to unlock first, and with a PIN or pattern the calls' reasons
stay hidden until you unlock. The screen dims by the hour: the phone's own brightness by day, lower from 20:00, as dim as
it goes and in warm red-orange from 22:00 to 06:00 (tap the screen to brighten it for 15 s). A call or the wake-up call
rings there full screen. Open it from the app's **Phone** tab (**Bedside mode** → **Open bedside mode**).
- **Open by itself while charging**: off by default; pick the hours (say 22:00 to 07:00). Plugging in within them, or
  the hours starting while it charges, opens it; unplugging closes it again. On Android 10 and newer it opens through a
  full-screen notification (by itself with the screen off; with the phone in use, tap the notice).
- **Keep the screen on while charging**: on by default; off lets the screen time out as usual.

*Undo:* **Close**, and turn **Open by itself while charging** off. *Leaves your computer:* nothing new: it reads the
calls your computer already pushes to your call line (their times and reasons) and how many things are waiting.

### iPhone
iPhones use Kurooto as a web app on the Home Screen (iOS 16.4 or newer).

1. Pair as above, but open the page in **Safari**.
2. Tap Share → **Add to Home Screen** → Add.
3. Open **Kurooto from the Home Screen** (not from Safari): it finishes pairing.
4. Tap **Turn on notifications** and allow them (calls, questions and approvals arrive this way).

**Chat:** tap **Chat** in the Home Screen app (or open `<your call line>/talk`): the same chat as Android's, with
buttons, Reply and "Waiting for your computer".

**Tell Kurooto (Siri, Back Tap)** (0.6.0): right after pairing, the page shows how to build a "Tell Kurooto"
Shortcut, with a link made for this iPhone (to copy, and as a QR code); later it's under **Settings** in the Home Screen
app (or `<your call line>/settings`). Apple doesn't let a page make the Shortcut, so it's five steps in the Shortcuts
app: Dictate Text, then Get Contents of URL (your link, POST, JSON field `text` = Dictated Text), then Speak Text. Then
"Hey Siri, Tell Kurooto", or Settings → Accessibility → Touch → Back Tap → Tell Kurooto. What you say goes to Kurooto
as a chat message from that iPhone, and the first answer is read out; the rest comes in the chat. With the computer
off it waits on your call line.
- The link can only send chat messages; it opens nothing else on your call line. One per phone: **New link** makes
  another and the old one stops working; **Remove** ends it.
- Your computer tells you when a link is made, and lists them under dashboard → **Phone** → **Tell Kurooto** with
  **Revoke**. Unpairing the phone ends its link too.

*Undo:* **Revoke** on the dashboard (or **Remove** in the app's Settings), and delete the Shortcut. *Leaves your
computer:* nothing new; what you say goes like a chat message from the phone. The call line keeps only a hash of the
link, which phone it belongs to, when it was made and last used.

**What doesn't work on iPhone:** calls arrive as notifications you tap to answer; they can't ring like a phone call,
ring on silent, or show on the lock screen as a call. If you need those, use Telegram reminders or an Android phone.

### Without Telegram
Telegram is optional (0.5.18) once the phone app is paired: pick the phone app on the setup page's Chat step, or turn
Telegram off in Features while Phone calls is on.

- Everything Kurooto sends comes to the app's chat (reminders, check-ins, the morning message, AI answers, with their
  buttons); questions and approvals come with answer buttons under **Waiting for you**.
- `/pause`, `/resume`, `/status`, `/focus`, `/hold`, `/calls` and `/help` work in the chat.
- Features that send you things turn on with the app instead of Telegram; Voice notes and Files into notes still need
  Telegram.
- Files (a long answer, `kurooto send`, a file your AI sends): a link in the chat. With Drive upload on, a Google Drive
  link (deleted after `drive_upload.temp_days`); otherwise a copy sealed on your computer, kept on your call line for a
  day (up to 10 MB), opened in the phone's browser; otherwise the chat says the file stays on your computer, with its
  path.
- Files you share to the app can be asked about in the chat for two hours ("summarise the PDF I just sent").
- `kurooto doctor` notes "talks to you: in the phone app's chat"; no Telegram isn't a problem.

*Undo:* connect Telegram in Features; both then work (the chat gets Kurooto's own messages only with
`notify.app_chat` on).
*Leaves your computer:* what the chat already sends; with Drive upload on, files go to your Drive; otherwise a sealed
copy of each file stays on your call line for a day (the key is only in the link inside the chat message).

## The dashboard

`http://127.0.0.1:8770` (or `kurooto open`). STATUS shows your computer; SYSTEMS shows each feature as a living cell
that pulses when something happens; NOTES is a map of your notes and their links (click a note to read it). The tabs:
**Activity** (what happened), **AI jobs**, **Schedule** (what's coming), **Features** (turn on/off, set up), **Phone**
(your call line, pairing, a test ring), **About you** (your profile, to edit; `/#about` opens it), **Settings**
(every setting, with what it means), and **Terminals** (when the [Terminals](#terminals) feature is on). Left open in
a background tab or a minimised window, it costs next to nothing: Kurooto stops reading the computer and your notes
for it until you look again.

**Two designs** (Settings → Look → `look.design`, or the **classic look** / **new look** button). **new** (the default
since 0.5.19) sets the page in a sans-serif typeface, Public Sans, that comes with Kurooto (nothing is fetched from the
internet), with figures that keep their width as they change; monospace is kept for the terminals, code and file
paths. The panes are calm, rounded surfaces with their name and figures on a header line, the top bar carries the
name, a status line, **study**, **panes** and the design button, and the graphs are thin lines over a faint fill.
**classic** is the look of 0.5.18 and earlier, set wholly in monospace with each pane's name in its border. Both have
the same panes, pages, keys and data; the switch applies at once and is remembered (it's a setting). In classic, the
button is in the **panes** menu (roomy: the top bar). *Undo:* switch back the same way.

**Two layouts** (Settings → `look.layout`). **dense**, the default on a screen 1280 px wide or more, is one full-screen
board (the new design: rounded panes under a top bar; classic: thin borders with each pane's name set into its top
line):
- **STATUS**, down the left, is a monitor like btop, the same as `kurooto top`: the processor (a history graph, every
  core with its own short graph, speed, load, temperatures, fans), memory (used, cached, available, swap), the
  graphics card (use, its memory, temperature, power, a graph), the network (down above the line, up below, totals),
  disks (how full; reads and writes per second), the battery, the busiest processes (click **cpu** or **mem** to
  sort; Kurooto's own are marked ✦, or with a dot in the new design), **study today** (with the Study tracker on) and **projects**: your git folders
  with each one's last commit, what's not pushed yet and what's changed (list them in `look.projects`; Research's
  repositories otherwise). Its header has the time, how long the computer's been up, today's events, the battery,
  and pause, off and setup.
- **SYSTEMS** keeps the cells round the core, with the hours of the day on the ring and four corners: recent events,
  your AI's latest requests (with the local models and what's scheduled next), **today** (classes, calendar,
  check-ins, calls, focus and no-call holds) and **due** (overdue ones in red). A feature that runs programs of its
  own shows their cpu, memory, uptime and threads on its cell (grey and dashed when none is running); the others
  show what they did last and when they run next. Each cell's words sit just outside it, away from the core; on a
  crowded ring they move a little (with a hairline back to their cell) or say less, and never cover each other
  (on a very small screen a few may hide: hover over a cell for its card). In the new design SYSTEMS is the board's
  largest pane and is drawn as living tissue: the core is a membrane whose heartbeat runs out through its rims, each
  feature is a small neuron whose branches grow with how busy it was over the last two minutes, and the nerves are
  tapered fibres that flash where a pulse arrives. **It responds to you:** point at a cell for its card (its nerve
  lights up); click it (or Tab to it and press Enter) for a menu: **ping** (a pulse there and back), **sync now** for
  a feature that syncs, **quiet** (it keeps working but stops messaging you, through Calm, with **undo**), its
  **settings** (its card on Features) and its **activity** (the Activity page for that feature alone). Click the core
  for Ctrl+K. Drag to turn the ring a little and scroll to zoom; both spring back. With reduced motion set on your
  computer it holds still. *Undo:* a quiet feature's **undo** in the same menu, or `/calm`.
- **NOTES** adds your folders with their note counts, whether anything was touched this hour, and the notes you
  edited last. At the usual zoom the map names its regions, like place names: each course by its course page's title
  and each research project by its index note's title, at the middle of its notes. A note's own name shows when you
  point at it, find it, light the recent ones (**R**) or zoom in; zoomed in, course pages, hubs and projects are named
  first, then notes that link across courses. A book's index note is drawn small and named last: its hundreds of
  "Seen in" links come from reading the book, so it no longer crowds out everything else. A research project's
  region (since 0.5.21) also takes the notes its index links to and the topics its line in the research hub links
  to, and is always named, in the accent colour, however small its folder; concept notes join the course or project
  most of their links come from (a tie goes to the course), so they no longer sit in one unnamed cloud. Pointing at a
  note (0.6.1) lights it and its linked notes in full colour with their names on top, none overlapping, and dims the
  rest; Tab to the map and the arrow keys do the same, Enter opens the note, Esc lets go. The links Kurooto writes to
  say where a concept was read ("Seen in", "Concepts in ...", "From the books") are drawn but don't make a dot big
  or named first, so a lecture note or class post many concepts were read from stays small; its card counts them
  ("3 links (+152 from reading)"). Double-click a note on the map to open it: in your default app for Markdown, or in your own program
  with Settings → notes → `open_with`, e.g. `kitty nvim {path}`, `code {path}` or `kurooto term -e nvim {path}` (on
  every system; the program has to open its own window). It runs as a program with arguments, never through a shell;
  `{path}` is the note (one argument even with spaces), `{folder}` your notes folder, and without `{path}` the note
  goes at the end. If the program isn't there, the default app opens the note. *Undo:* empty `notes.open_with`.
- **TERMINAL**, below, has its tabs in its border: your AI's program, a shell and the log (with Terminals on), and
  **kurooto**, plain English as on Telegram, right in the page (`help`, `check`, `jobs` and `clear` are its own
  words; ↑ and ↓ bring back what you typed). The other pages (activity, jobs, schedule, features, phone, research,
  you, settings) are in the same border and open over the whole board: **Alt** and the page's underlined letter
  (**Alt+F** features, **Alt+S** settings, **Alt+A** activity, **Alt+J** jobs, **Alt+C** schedule, **Alt+P** phone,
  **Alt+R** research, **Alt+Y** you) opens one, and **Esc** goes back. Inside a terminal those keys stay the
  terminal's (Alt+F is a word forward in a shell). **Alt+1**, **Alt+2**… switch the terminal tabs; **Alt+/** (or
  `/`) finds a note.

**Bigger panes.** Click a pane's name (⤢) or double-click its border and it fills the board; **Esc** or its name
again brings the others back. **panes**, in the board's top-right corner, hides STATUS, SYSTEMS, NOTES or TERMINAL
(one always stays) and the others take the room; it lists the pages and their keys too. What's hidden is the setting
`look.panes` (e.g. `["status"]`), so every browser shows the same. *Undo:* panes → show them all, or empty
`look.panes`.

**Study mode.** **study** in the board's top-right corner (roomy: the top bar), **Alt+M**, Ctrl+K → `study on`, or
`/study mode on` on Telegram (or "study mode", "leave study mode") keeps only your notes and studying: the NOTES map
large, with the chosen subject's notes lit, and a STUDY pane with a focus and break timer, today's study per subject,
what's due in two weeks (quizzes and exams, tasks, what's time to start), recall cards from the subject's exam prep
(with Quiz on) and the subject's notes (course page, exam prep, lectures, concepts; click one to find it on the map,
double-click to open it). A focus (`study.focus_min`, 25) is focus time, so calls and messages that can wait are held,
and its minutes are logged to the subject in the [Study tracker](#study-tracker); then a break (`study.break_min`, 5),
then the next focus waits for **start**. **pause** keeps what's left, **reset** ends it; `study.timer_ends_mode` (the
pane's "then leave Study mode") ends Study mode with the focus instead of a break. Everything else is hidden, untouched,
and leaving puts the board back exactly as it was. The mode is the setting `look.study_mode`, so it survives reloads
and follows a switch from Telegram at once. *Undo:* leave Study mode (Alt+M again, or `/study mode off`).

**Search.** Features and Settings have a search box at the top (`/` or **Ctrl+F** while the page is open; Ctrl+F
again is the browser's own; **Esc** empties it). It filters as you type, in any case: a feature by its name, what it
does, its privacy line and its settings (a card found only by a setting says which), a setting by its section, name,
help and value. The words it found are marked, with a count, or it says nothing matches.

**Hiding features.** A feature that's off has **hide** on its card: it leaves the Features page, and nothing else
changes (Telegram, the setup page and the API still list it; a feature that's on always shows). **Show hidden (N)**,
at the bottom, lists them with **Unhide**, and a search still finds them, marked *hidden*. The list is the setting
`look.hidden_features`. *Undo:* Unhide, or empty `look.hidden_features`.

**roomy** is the earlier layout, with bigger panes and type; a narrower window gets it by itself. `look.layout =
roomy` keeps it everywhere. It always shows every pane, with the pages in its tabs (the Alt keys, the search and
hiding features work there too).

**Links to other sites** (Google sign-in, a token page, Cloudflare, AI Studio, the guides) open in this computer's
default browser, also when the dashboard is in another browser's app window (`google-chrome --app=…`). Kurooto's own
pages stay where they are, Ctrl-, Shift-, Alt- or ⌘-click still opens a link in the browser you're in, and if the
default browser can't be reached the link opens here as before. On Linux and macOS a `$BROWSER` you've set is used.
Settings → Look → `look.links_in`: `default`, or `here` to keep every link in the browser showing the page.

The **morning page** (`http://127.0.0.1:8770/morning`) shows today's plan from your daily note, with your classes,
calendar, what's due, check-ins and open questions. The alarm opens it.

**Colours:** Kurooto's pages (the setup page, the dashboard, the morning page, and your call line's pages on the phone)
use deep greens, like the website. If you liked the earlier pink and rose colours better, set Settings → Look →
`look.palette` to `rose` and reload the page, or pick a named theme such as Catppuccin or Nord
([Colours](#colours-look)); `kuro` (the default) brings the greens back. The setup and morning pages
follow your system's light or dark mode; the dashboard is always dark. Your call line's pages on the phone stay green.
The Android app follows the phone instead: light or dark as the phone is set, in the wallpaper's colours on Android 12
and newer (Material You), Kurooto's greens on older phones; its ringing screen is always dark. Its main screen has the
dashboard's slowly moving blobs behind it; they stand still with the phone's **Remove animations** setting or in
battery saver.

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

### Today (Alt+T)
The first page of the dashboard's pages: the day, and the everyday things done right there.
- **One box for anything.** Plain words go to Kurooto as if typed on Telegram (the answer shows which AI gave it and
  how long it took). `j …` adds a journal line, `. …` a note to today's inbox note, `! 18:30 call mum` a reminder
  (`! in 20m tea`, `! tomorrow 9am gym`).
- **Alarm:** what's set, a box to set one ("7:30", "tomorrow 6:45"), skip tomorrow, turn one off, the daily alarm.
- **Due:** the next three weeks, with done and new date; an add box ("essay draft fri 17:00").
- **Reminders:** each with +10 min and cancel.
- **Check-ins:** today's, with +30 min and skip.
- **Waiting for you:** open questions, with their answer buttons.
- **Journal:** today's entries and a box (Ctrl+Enter saves) that adds a "Journal HH:MM" section to today's daily note.

Every button does exactly what the command or the AI's tool does (`/api/act`, core/actions.py), so the page, Telegram
and the AI never disagree. A feature that's off says so with a link to Features.

## Colours (Look)

Kurooto's pages (the setup page, the dashboard and the morning page) and its terminals come in three palettes of its
own and in named themes. Pick one on the setup page (step 3, **Colours**) or in **Settings → Look → `look.palette`**:

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

- **A named theme**, in the project's own colours: Catppuccin (`catppuccin-mocha`, `catppuccin-macchiato`,
  `catppuccin-frappe`; Latte for light pages), Tokyo Night (`tokyonight-night`, `tokyonight-storm`, `tokyonight-moon`;
  Day), Rosé Pine (`rose-pine`, `rose-pine-moon`; Dawn), Gruvbox (`gruvbox`), Nord (`nord`), Dracula (`dracula`;
  Alucard), Everforest (`everforest`), Kanagawa (`kanagawa-wave`, `kanagawa-dragon`; Lotus) and Solarized
  (`solarized`). You pick the dark flavour: the dashboard and terminals are always dark and use it, and the setup and
  morning pages use the family's light flavour when your browser is in light mode. The dots under the setting show
  both. The palettes are the projects' own (MIT, or Apache-2.0 for Tokyo Night); the dashboard guide lists the
  sources.

Text always stays readable: any colour that would be hard to read on its background is made lighter or darker until it
passes the WCAG AA contrast level (4.5:1). For a named theme, only such text colours move (mostly in light flavours,
Solarized and Nord); backgrounds and everything else stay exactly as the project publishes them.

**Your own colours file:** set **Settings → Look → `look.theme_file`** to the full path of a kitty theme (lines like
`background #1a1110` and `color4 #9ccaff`) or a matugen or pywal `colors.json`. It's used instead of the desktop's
colours, and switches the palette to system. Kurooto says so if it can't find colours in the file.

The dashboard is always dark (with the system palette, its dark version); the other pages follow light or dark mode.

*Settings:* `look.palette` (`kuro`, `rose`, `system` or a named theme's id; default `kuro`), `look.theme_file`
(empty).
*Leaves your computer:* nothing. Kurooto only reads the colour settings and files above, on this computer.
*Undo:* press **Kuro** on the setup page's step 3, or set `look.palette` back to `kuro`; empty `look.theme_file`.

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

**`/fixme`: when the AI is what broke.** `/fixme` on Telegram or the dashboard's terminal prompt (and `kurooto fixme`
in a terminal, which works with Kurooto stopped) runs the same checks as doctor and `/health` and matches each failing
one, by fixed rules and with no AI, to its row on the troubleshooting page and to the known issues of your version
(a list inside each signed release; a newer version that's already downloaded brings its own, and a version its
maintainer withdrew says so). A check Kurooto can fix gets its **Fix** button (`/fixme fix <id>` in a terminal).
`/fixme the phone doesn't ring` finds the troubleshooting rows for what you see. `/fixme now` asks online services too.
Your AI only explains, and only when you ask: **Ask my AI** under the answer (or `/fixme ai`), offered only when your
AI looks like it works; the rules' answer never waits for it.

*Undo:* nothing to undo; `/fixme` only looks (a Fix runs only when you tap it). *Leaves:* nothing, unless you tap Ask
my AI: then the answer goes to your AI like any request.

**Settings** (`health.*`; not on the dashboard's Settings page yet: change them in `settings.json` in Kurooto's settings
 folder, [Where things are](#where-things-are)):
- `on`: the daily pass (default `true`). `/health`, the dashboard and doctor check either way.
- `when`: when the daily pass runs (default `daily 21:00`, before bedtime, so tonight's alarm is checked in time).
- `auto_fix`: try the safe fixes before telling you (default `true`).

**Undo:** `health.on` = `false` stops the daily pass and its messages (nothing else changes); `health.auto_fix` =
`false` leaves every fix to your tap. The dashboard's activity shows `health_checked`, `health_fixed` and
`health_told`.

*Leaves:* nothing new. The checks ask services Kurooto already uses: Telegram whether your bot answers, GitHub whether
your notes token works (a read-only look at your notes repository), and your call line whether it's up and how many
phones are paired.

## Calm by default: why each message came, and a daily limit

On by default. Every message Kurooto sends **by itself** (not an answer to something you asked or did) records why it
came: which feature, what for, the setting that controls it, and what it was about (the deadline, the class, the
project). On Telegram such a message has two more buttons:
- **Why?** answers from what was recorded when it was sent: "Why: Deadlines, a reminder before something on your
  deadline list is due. About: Report on groups. Setting: deadlines.ping_h = 24 (Settings → Deadlines)." A message
  that didn't say why (an add-on, a script) gets "No reason recorded"; Kurooto never guesses.
- **Less of this** offers up to three choices, each changing **one** setting, with an **Undo** button after it:
  - **Stop:** that kind stops. Where the feature has its own setting, that's what changes (practice offers:
    `quiz.offer_at` empty; a check-in: its time off; after-class questions: After-class notes off). Otherwise that
    kind goes on Calm's own list (`notify.calm.stopped`).
  - **Fewer:** where it makes sense: the mail digest once a day instead of twice, the papers digest weekly instead of
    daily, a quiet project asked about half as often, no after-class question for that one subject, or at most one
    Classroom announcement a day (the rest wait for the evening).
  - **Another time:** that kind always waits for the evening bundle (`notify.calm.evening`).
The phone app, the desktop and calls get the plain message, as before.

**A daily limit.** At most **6 messages and 1 call a day** come by themselves (`notify.calm.messages`,
`notify.calm.calls`). Past that, messages wait for **one evening bundle** at 20:00 (`notify.calm.evening_at`): one
Telegram message listing what waited, numbered, with each item's buttons ("2: Nothing new"). A question that waits
is still open meanwhile (`/q`, and on your next call); replying to the bundle answers it when it's the only question
in it; the phone app gets the waiting questions one by one at that time. A call past the limit isn't placed: a
check-in comes as a message instead, anything else waits in the bundle with a **Call now** link. After 20:00,
messages come as they are.

**You're told when the limit starts holding.** The first time a day a message waits because of the limit, one line
comes at once (Telegram and the phone app's chat): "That's today's 6 messages that came by themselves. The rest wait
for the evening bundle at 20:00, which lists each one." Its buttons: **Send them as they come today** (the limit is off
for the rest of today; what waited comes now, in order), **Raise to 12** (`notify.calm.messages` doubled, with
**Undo**; what waited comes now, up to the new limit) and **Fine**. At most once a day, only for the daily limit (not
exam season, a quiet week or a kind you moved to the evening), and not when the limit is 0. The bundle's first line
says how many waited and why: "4 messages that waited, held by the daily limit of 6". `/calm` shows today's count, the
limit, and how many wait (and how many of those the limit held).

**Update notices don't count**, and several in a day fold into one: on Telegram the first is changed in place to the
newest ("Kurooto updated to 0.5.19 (and 2 earlier today)."); where it can't be changed, the newest comes as a new
message with that line. **Classroom → notes sends one message per check**, listing what was filed by title (eight,
then "and N more").

**Never held, never stopped:** the alarm (and the alarm to leave for an exam, and "tonight's alarm might not ring"),
approvals, your own reminders (reminders, calls you asked for, quiz times and study sessions you set, calendar event
reminders), a deadline less than 12 hours away (also its call), anything urgent (Kurooto can't work until you act:
a sign-in that ended, the AI's limit, crashes) and a newly paired device on your call line. They don't count against
the limit and have no Less of this. Answers to what you asked or did (AI answers, `/sync`, a skill you ran, a button
you tapped) aren't counted at all.

**Exam season** (with [Exam season](#exam-season) on, its "Only deadlines, quizzes and the alarm by day" part):
during the period, only Deadlines, Quiz, the alarm and Exam season itself come during the day; everything else that
comes by itself waits for the evening bundle (also after 20:00: then until the next one). The day's limit still
applies to what comes.

**Once a month**, from the same records: the kind of question you answer least, if 8 or more came in 30 days and you
answered a fifth of them or fewer: "In the last 30 days you answered 1 of 19 after-class questions. Turn them off?
(Turns off After-class notes; Undo puts it back.)" with **Apply** / **No**. Only for questions you're meant to answer
(check-ins, after-class questions, practice offers, exam-eve questions, quiet-project questions, look-back
suggestions, first-week quests...), never for reminders. "No" keeps that kind out of it for 90 days.
`notify.calm.monthly` = `false` turns it off.

**On Telegram:** `/calm` shows today's count, what's waiting, and what you turned down (with "Start ... again"
buttons); `/calm 8` sets the messages a day, `/calm calls 2` the calls, `/calm evening 21:00` the bundle's time,
`/calm off` and `/calm on`. `/why` explains the last message that came by itself.

**Settings** (Settings → `notify.calm`): `on` (`true`), `messages` (6), `calls` (1), `evening_at` (`20:00`),
`monthly` (`true`), and the lists Less of this fills: `stopped`, `evening`, `fewer`; and the two Dreaming tunes:
`habituate` (kind → after N unanswered in a row, it waits for the bundle until you answer one) and `windows` (kind →
`"10:00-13:00"`: outside those hours it waits).

**Undo:** each Less-of-this choice and each Apply has an Undo button that puts that one setting back as it was (a
feature it turned off goes back on). `/calm` lists what's stopped, with a button to start each again.
**`notify.calm.on` = `false` (or `/calm off`) restores the old behaviour exactly:** nothing waits, no Why? buttons,
nothing is recorded; anything already waiting still comes at the evening bundle.

*Leaves:* nothing. What's recorded stays in `calm.db` in the state folder for 45 days: when, the reason, the setting,
what it was about, the first 300 characters (forgotten after `privacy.keep_days` when you set it) and whether you tapped or answered it;
a waiting message in full until its evening.

## Your rhythm: quiet hours, lighter days, gone quiet

Rules only, on this computer. Each change is said once, with **Undo**.

- **Quiet hours that fit you** (`availability.learn_night`, on). Once a day Kurooto looks at the last three weeks of
  when you were around (messages, buttons you tapped, calls you answered, "I'm awake") and takes each day's long quiet
  stretch (4 to 16 hours). With 7 or more, the middle of their starts and ends, to the half hour, are your usual quiet
  hours. When an end is an hour or more from the night hours (`availability.night`), they move there: "Quiet hours at
  night (no calls) now run from 08:00 to 16:00, not 23:30 to 07:00: that's when you've been quiet on 12 of the last 21
  days." Nights into the afternoon are fine. At most once a week; never night hours you set yourself; after Undo, left
  alone for a month. Only those two times are kept.
- **Mornings follow** (`availability.learn_morning`, on), in the same line, unless you set them yourself: the check-in
  day turns two hours before you're usually up (`checkins.day_starts`), Dreaming's morning message comes half an hour
  after (`dreaming.when`), Start-by's "Time to start" an hour after (`startby.when`).
- **No alarm set** (`alarm.suggest`, on): within the hour before your usual bedtime, "You usually wake around 16:30;
  set an alarm?" with **Set 16:30** / **Not tonight**. Once a day at most; it never sets one by itself.
- **Lighter days** (`notify.calm.lighter_after`, on): the day after an exam (a quiz or exam on your deadline list whose
  time passed) or 8 hours or more on the Study tracker, half the daily limit of messages that come by themselves, the
  first check-in an hour later, and one line in the morning message (Dreaming's, or its own) with **Not today**.
- **Gone quiet** (`availability.absence_days`, 2; `0`: off): nothing from you for two days while Kurooto kept running:
  "Haven't heard from you in two days. All good? Nothing's urgent." with **I'm fine** / **Busy, quiet for a week**.
  Never repeated or turned into a call until you're back; it waits out the night, focus, `/hold`, `/pause`. **Busy**:
  no calls for a week (`/calls` lifts it) and what comes by itself waits for each evening's bundle; the alarm, approvals
  and your own reminders still come.

*Settings:* `availability.learn_night`, `availability.learn_morning`, `availability.absence_days`,
`notify.calm.lighter_after`, `alarm.suggest`.
*Undo:* the **Undo** button under the quiet-hours line puts every setting it changed back (left alone for a month);
**Not today** cancels a lighter day; **Undo** under "Quiet until ..." ends a quiet week. Turning a setting off stops
that part at once.
*Leaves:* nothing. `state/rhythm.json` keeps the two learned times, the last change and its Undo, and the dates asked.

## Memory: open threads and what's remembered

**Open threads.** When you say you'll do something, in a message or on a call ("I'll send the draft tonight", "I need
to reply to Lena's email"), or start a task (a study session, progress on a deadline: "ps3 4/7"), it becomes an open
thread: rules on this computer, no AI, nothing sent. It closes when you say it's done ("I sent the draft"), when the
session ends or the deadline is done, on **Done** or **Drop**, or by itself after 7 days nobody touched it.
Questions, "remind me ..." and anything about health, money or passwords never open one. **`/threads`** lists what's
open with **Done** and **Drop**, and what closed in the last 48 hours with **Undo** (`/threads done 2`, `/threads drop
2`, `/threads all`).

**"That thing."** "Did I finish that thing?", "what was that thing?", "the draft thing is done" look at threads from
the last 48 hours, narrowed by any other words you used ("did *you* finish that thing?" also looks at your AI
requests). One match: what it is, where you said it ("on the call at 07:56") and how it stands, with **Done** /
**Drop**; two or more: one question with a button each. A thing found this way is only read or asked about: nothing is
sent, moved or deleted for it without your OK.

**The memory ledger.** Everything remembered is in one store on this computer, always encrypted: gists of faded
conversations, threads, the lines Kurooto keeps in your how-to-help-me note, your daily notes' headings and lines, and
your project notes' meetings (read from your notes when they change; your notes stay the source of truth). Each row's
words are sealed with AES-256-GCM under a key in your keychain (`ledger.key`; the owner-only secrets file where
there's no keychain); only kinds, times and keyed hashes are on disk, and searching decrypts into memory.
**`/memory`** lists it, **`/memory glacier`** finds rows, **`/memory forget 3`** forgets one (a how-to-help-me line
comes out of that note too; a daily-note or meeting line stays in your note and stays forgotten here), **`/memory
export`** writes the gists and threads to a note in your inbox. Ask it plainly: "when did I last talk to Prof Ortiz?",
"what was I doing last Thursday?" (also "yesterday", "on 20 Oct").

**What an AI reply is told.** Only when your message refers to past things ("on the call", "yesterday", "that thing",
"did I ...", a weekday) or shares words with an open thread, your AI gets the few remembered items it's about: at most
about 600 tokens (`memory.budget_tokens`), picked by rules (shared words, the course and the day you name, how
recent), each saying where it's from, never transcripts. The run receipt then ends "used 2 remembered items". A call's
brief gets your open threads and the last day's gists, so it can pick up what you said in a chat.

*Settings:* `memory.threads` (on), `memory.thread_days` (7), `memory.recall` (on), `memory.budget_tokens` (600),
`backups.memory` (off). *Leaves:* the remembered items above, with that request, to the AI you picked (Gemini Live for
calls); nothing else. *Undo:* **Undo** on a closed thread for 48 hours; **Drop** a thread opened by mistake;
`memory.threads` off opens no more; `memory.recall` off sends no remembered items. Forgetting: `/memory forget 3`,
`/forget 7d` (threads from those days), `/forget all` (all threads; the gists if you choose).

## Forgetting: how long conversations are kept

Nothing is forgotten unless you choose: set `privacy.keep_days` (e.g. 30) and what Kurooto keeps of your
conversations is forgotten after that many days, every night at 04:15 (or when the computer wakes, if it slept
through it):
- call transcripts, and calls that went on as text;
- what you asked the AI and what it answered (the request's time, AI and effort stay, without the words, for `/usage`
  and the Space keeper), and long answers kept as files;
- Chat's recent turns, answered and expired questions, Wrong-button cases you didn't make test cases;
- the words of messages that came by themselves (Calm keeps when and why for its 45 days);
- the search index of past requests (Learns from its own work);
- the threads you were in the middle of (by when each opened);
- log lines older than that (`kurooto logs`).

Your notes folder is never touched: a voice note's recording is saved in your notes' inbox, so it stays. Test cases
you made, open questions and calls still going stay too. Messages already on Telegram or your phone stay there; delete
them in the app.

**`/forget 7d`** forgets the last 7 days now (also `/forget 12h`, `/forget 2w`) and says how many of each kind went:
"Forgot 2 call transcripts, 5 AI requests and 1 log file." **`/forget all`** forgets everything Kurooto has kept, after
a button that asks whether the gists go too (**Forget all, keep gists** or **Forget gists too**; they work for 10
minutes; **Keep it** does nothing). `/forget` alone says how long things are kept.

**Gists: what settles.** Like memory, a conversation isn't simply dropped: as the words of a call, an AI request or a
chat fade, it settles into a one-line gist of what it decided or did, and the nightly job lets the words go only once
that gist exists. Gists come from Kurooto's own records, never from rereading the words with an AI: a call keeps what
it was for and what its tools did ("set reminder: I'll remind you Fri 23 Oct at 09:00: book the lab slot"; tools that
only read are named, never what they read); an AI request of yours keeps its title, how it ended and its run receipt
(never the answer); a chat turn keeps its request's name. A line that looks like a health, money or password detail
keeps only its kind. **`/gists`** shows the latest, numbered; **`/gists lab`** finds the ones with those words;
**`/gists forget 3`** drops one. With `privacy.gist_model` on and Local AI models on, a model on this computer adds a
sentence of what a call decided (never a cloud AI).

*Settings:* `privacy.keep_days` (0, the default, keeps everything until you `/forget` it). `privacy.keep_gist` (on:
conversations settle into gists; off: none are made), `privacy.gist_days` (0, the default: gists are kept for good),
`privacy.gist_model` (off). `ask.keep_days` and
`cases.keep_days` (0: `privacy.keep_days` when set, else 30 days, as before) give questions or cases their own time.
*Leaves:* nothing. The event log (`events.jsonl`) isn't forgotten: it holds times, counts and names, never what you
typed or what was answered, and features learn your rhythm from it over weeks. Your call line holds a call's
transcript only while the computer is off and hands it over when it's back, so nothing waits there.
*Undo:* none for what's forgotten (that's the point); a backup zip made before still has it. Set
`privacy.keep_days` to 0 to keep everything again from now. Gists: `/gists forget 3` drops one, `/forget all` →
**Forget gists too** drops them all, `privacy.keep_gist` off makes no more.

## Where requests go: /egress

Always on. Every request Kurooto makes on the internet goes through one place that counts it: the host, the feature,
how many requests and how many bytes went out and came back, per day. It's checked against the list of hosts in
`docs/PRIVACY.md` ("Where requests go"); addresses you gave (your calendar's link, your feeds, your own AI service,
your call line, your ntfy server, pages your AI reads for you) are yours and always allowed, and this computer
(`127.0.0.1`) is never counted. Programs that go online by themselves (git for Notes sync, npm and wrangler for the
call line, agy and Claude Code, Ollama, GBrain, Tectonic, installers) are counted as "handed to" them: what they send
isn't seen by Kurooto.

**`/egress`** shows the last 7 days:

    What Kurooto sent out in the last 7 days (privacy.egress: record):
    - api.telegram.org (Telegram): 2,210 requests, 1.9 MB out, 4.4 MB in
    - handed to agy (AI requests): 31 runs; what it sends, it sends itself
    - generativelanguage.googleapis.com (Voice notes): 4 requests, 812.0 KB out, 3.1 KB in

A host that isn't on the list shows "(not on the list)". With `privacy.egress` set to `enforce`, Kurooto refuses it:
the feature fails with "Kurooto didn't connect to <host> (<feature>): it isn't on the list ...", and `/egress` lists it
under Blocked. Add the host to `privacy.allow_hosts` to allow it.

*Settings:* `privacy.egress`: `record` (the default: counts everything, stops nothing, because an add-on or an
address changed in settings can reach hosts the list can't know of), `enforce` (also refuses hosts not on the list),
`off` (counts and checks nothing). `privacy.allow_hosts`: more hosts, e.g. `["feeds.example.org"]`;
`".example.org"` allows every host under it.
*Leaves:* nothing. The counts stay in `egress.json` in the state folder for 30 days: hosts, features, numbers and
bytes, never what was sent.
*Undo:* `privacy.egress` back to `record` (or `off`); remove a host from `privacy.allow_hosts`.

### Keep or drop

Kurooto counts what you actually use of each feature: requests it answered at once, its commands, taps on its
messages' buttons, its tools used on a call, your replies to its messages (the setup page's try-it box doesn't count).
**On day 10** (from Kurooto's first start, or from the update that brought this), once setup is done, one message
lists each feature that's on, its use in those 10 days and the messages it sent by itself, with **Keep / Quiet / Off**
per feature (the least used first):
- **Keep:** nothing changes; not asked about again for 90 days.
- **Quiet:** it keeps working, but what it sends by itself stops (its kinds go on Calm's stopped list,
  `notify.calm.stopped`). Your own reminders, the alarm and approvals still come; calls follow their own settings.
- **Off:** the feature is turned off, as in Features.

**Then monthly:** features that are on, unused for 60 days and still running scheduled work get the same question.
Nothing is turned down without a tap; Telegram is never asked about. `/keep` shows the counts any time (last 30
days; `/keep 60` for 60), `/keep <feature>` one feature with its buttons.

**Settings:** `keep.ask` (`true`). **Undo:** the Undo button under Quiet or Off (through Calm, like Less of this);
`keep.ask` = `false` stops the questions. *Leaves:* nothing; the counts (numbers per feature and day, kept 90 days)
are in `keep.json` in the state folder.

## Updates and going back

Kurooto updates itself. Settings → `updates.mode`:
- **night** (default): a new version is downloaded when found and switched to between 03:00 and 05:00, when the
  computer isn't busy and you're not on a call.
- **ask**: Telegram asks you (Update / Later / Skip).
- **off**.

Every release is signed; Kurooto refuses anything unsigned, older, or changed on the way. During your exams, [Exam
season](#exam-season) holds back every update that isn't marked critical (in its signed manifest) until the exams are
over. The three newest versions stay installed (the one you're on and the one before it always do). If a new version
crashes three times in its first five minutes, Kurooto goes back to the one before and won't offer the broken one again;
you're told on Telegram. `kurooto update --now` installs an update right away.

**Withdrawn versions.** When a release turns out to be broken, its maintainer puts it on a signed yank list on the
release site. Kurooto never installs a version on that list: not when it finds it, not when it already downloaded it
for the night, and not with `kurooto update --now` (it says the version was withdrawn, and why). It keeps the last
list it read, so a withdrawn version stays refused while the site can't be reached; a list that isn't signed, or is
older than one it has seen, stops the update instead.

**Staged updates** (off until you turn it on: `updates.staged` = `true`). A new version waits until it has been out
48 hours (`updates.wait_hours`), so a broken release is usually withdrawn before it reaches you, and nothing installs
during your exams (`updates.exam_hold`, on): an exam period from Subjects (`/term exams ...`), or a quiz or exam within
a day from Deadlines. A release signed as critical (a security fix) skips both. While one waits, the dashboard's update
badge says "waiting" (point at it for why; with `updates.mode` = `ask` you're asked once it's done waiting), and
`kurooto update --now` installs it anyway.

**Undo:** `updates.staged` = `false` installs new versions as soon as they're found, as before. The yank list can't be
turned off.

Your call line is updated after Kurooto updates, if its code changed or the release brings a new Android app (Kurooto
downloads the app that goes with its version and checks it against the signed release; the line hands it out at
`/kurooto.apk`). A new app goes to the line a minute after it's downloaded, not at the nightly 05:10 update: never
during a call, retried every 30 minutes while offline, and you hear about it only if it fails twice. The pairing page
shows the app's version next to "Download the app". The Android app shows an Update button; the iPhone web app
updates itself.

## Moving to a new computer

With [Profile sync](#profile-sync) on (on the old computer):

1. On the old computer, if it still works: `/profile save` (or just wait for the daily save), then **turn Kurooto off
   there** (`kurooto off`): two computers can't share one Telegram bot or one call line.
2. Install Kurooto on the new computer. On the setup page's first step, press **I've used Kurooto before**, and give:
   the repository (`owner/name`), a token for it (lost it? make a new fine-grained token for that repository with
   Contents: Read and write), and your passphrase.
3. Kurooto restores your settings, keys and saved items, turns on every feature that's ready, and, with Notes sync,
   brings your notes back. It lists what's left to do here, then **Continue** walks you through it: sign your AI in
   again (agy and Claude Code keep their sign-ins on the computer they ran on), install what features need
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


### Going past what this computer suits
Kurooto picks local models by what it detects (graphics memory, Apple Silicon, memory). You know your computer better:
- `kurooto hardware` shows what it detected and what it recommends, with any warnings.
- `kurooto hardware --profile big-gpu-12` uses another setup's models (`auto` goes back; `light`, `apple-8`, `apple`,
  `small-gpu`, `big-gpu`, `big-gpu-12`).
- `kurooto hardware --add gemma4:12b` adds an Ollama model of your own (`--remove` takes it off); its size is looked up
  in Ollama's registry. `--add-prereq tesseract` adds another program to install.
- `kurooto hardware --install` (or the button on the setup page's computer step) installs Ollama, every model on the
  list and those programs, after checking there's room on the disk.

Kurooto never refuses: if a model is bigger than your graphics memory, it says part of it will run on the processor,
slowly, and goes ahead. The same settings are `hardware.force_profile`, `hardware.extra_models` and
`hardware.extra_prereqs`.

### The reranker (concept graph)
With a helper model on the list (and `integrate.rerank` on), the concept graph asks it, for each candidate note,
whether the note belongs with a new concept, and orders them by the model's own odds. It uses the helper model already
installed (no extra download) and costs no AI requests; where there's none, candidates keep their keyword and
embedding order.

## What 0.8.7 added to Brain

- **Brain's whole past** (`mind.backfill.on`, off; one switch per source, `mind.backfill.events`, `jobs`, `deadlines`,
  `checkins`, `quiz`, `calls`, `learning`, `study`, all on): `/mind backfill run` now also reads the AI request history,
  deadlines, check-ins, quizzes, calls, the request index and study time, ids and numbers only, with a progress bar per
  source, into a history of its own that `/mind backfill verify` checks. It gives the read, the forecast, week plans and
  the model of you a starting point. **Undo:** `/mind backfill forget` (or `/mind backfill forget <source>`), then turn
  `mind.backfill.on` off; a source's own switch off stops it being read.

## What 0.8.6 changed

- **`look.board`:** `three` (default) or `classic`, the dashboard board from before 0.8.3. **Undo:** set it back.
- **`look.brain_monitor`:** `shown` (default) or `drawer`. **Undo:** set it back.
- **The BRAIN pane:** hide it from the panes menu (top right); hidden, it isn't loaded. **Undo:** tick it again.
- **Fixes:** stopping and updating no longer wait for a long job; Brain's imported past keeps only deadline moves for the read.

## What 0.8.2 added to Brain

- **The Brain page:** Alt+B on the dashboard, a 3D model of the Brain you turn and click (see the user wiki, Brain). **Undo:** nothing
  to undo; it only shows the switches you already have, and a part's switch there is the same `mind.<part>.on`.
- **Hardened mode after 0.8.1:** run `sudo tools/mind_harden.sh --apply` again (the scorekeeper changed); or turn `mind.hardened` off.

## What 0.8.1 added to Brain

- **Brain's past** (`mind.backfill.on`, off): `/mind backfill dry|run|status|forget`. **Undo:** `/mind backfill forget`, then turn
  the switch off.
- **The journal's folder and file** (`mind.journal.in_notes_folder`, `mind.journal.in_notes_file`): where `mind.journal.in_notes`
  puts it, inside your notes.
- **`mind.lab.in_repo`:** a project's `.kurooto` folder ignores itself in git.
- **Fixes:** `/plan`'s pace caps a day at 14 hours; `kurooto doctor` waits for a call-line update's retries.

## What 0.8.0 added to your notes and files

- **Reading class documents** (`sorter.read_files`, off): PDF, Word, PowerPoint, notebook, text, rich-text and CSV files you
  drop in the scratch folder become Markdown notes next to them (originals untouched; `sorter.read_mb`, 25, is the size
  limit), and join the concept graph as `reference` notes (`integrate.sources`, on). **Undo:** turn the switch off; delete the
  generated note if you want it gone.
- **Copies among notes** (`sorter.duplicates`, `integrate.duplicates_all`, `integrate.duplicates_per_day`): exact and near
  copies, in new files and old notes, each a question with Keep both / Merge / Leave it. Nothing merges without your tap;
  every merge has Undo. Books: `books.duplicates` notices the same book twice by its file contents.
- **Subjects with folders:** dashboard → Study → Subjects: add a subject with an optional notes folder (its own
  neighbourhood on the notes map) or remove one. **Undo:** remove it; the notes stay.
- **Find files** (`/find`, module `finder`): see Features. **Undo:** turn the module off; delete `<state>/finder`.
- **After turning a feature on,** the dashboard says what's left to set up; `/health setup` lists it for everything.
- **`deadlines.skip_notes`:** notes or folders the deadline scan leaves alone.
- **Settings** have drop-downs where the choices are known and a tooltip on every label.

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
| Lecture notes, exam prep, class log, doubts | `<subject>/` | `sources/<subject>/` |
| Concept notes (one idea each) | `<subject>/<idea>.md` | `zettel/<idea>.md` |
| Research projects and their runs | `research/<project>/`, hub `research/index.md` | `projects/<project>/`, hub `maps/research.md` |
| Mail digests | `mail/<date>-<time>.md` | `digests/mail-<date>-<time>.md` |
| Quick notes and loose ideas, prompts, handwritten notes | `inbox/`, `prompts/`, `handwritten/` | the same |

In the zettelkasten layout, notes Kurooto and the AI write start with `id` (the note's path), `aliases`, `tags` and
`trust_tier: agent_written` (your daily note and your quick notes don't get `trust_tier`: they're your words). Links
are `[[wikilinks]]` either way, unless `notes.links` is `markdown`: then Kurooto writes `[Name](path.md)` links,
relative to the note they're in, and tells the AI to do the same. It reads both kinds. The AI is told your layout, and skills written for the default one (`journal/<date>`,
`<subject>/course`) are translated when they run, yours included.

**Your own places** (`notes.paths`): any kind of note somewhere else, e.g. `{"daily": "diary/{date}.md", "ideas":
"plans/ideas.md"}`. The kinds are `daily`, `profile`, `how_to_help`, `not_interested`, `recurring`, `ideas`, `skills`,
`prompts`, `inbox`, `note`, `subject`, `course`, `class_log`, `lecture`, `concept`, `exam_prep`, `doubts`, `research`,
`project`, `runs`, `handwritten`, `mail`; the parts in braces are `{date}`, `{time}`, `{subject}`, `{project}` and
`{slug}`, plus `{year}`, `{month}` and `{day}` from the date (`{year}/{month}/{day}.md`). A place that doesn't work (a
part that doesn't exist, or `..`) falls back to the layout's own.

**Files folder** (`files.folder`): a folder outside your notes, for example `Documents/Kurooto files` or a folder your
cloud drive syncs. With it set, these go there instead of into your notes: photos and PDFs you send (`inbox/`),
after-class photos and files (`<subject>/`), revision packs, LaTeX and PDF (`<subject>/`), the originals of handwritten
pages (`handwritten/`) and new scans (`handwritten-inbox/`, unless you already have that folder in your notes or set
`handwritten.folder`), and Classroom's downloaded files (`<subject>/`). Notes link to them: relative links in the
kurooto layout, `file://` links in the zettelkasten one (`files.links`: `relative` or `file` to choose). Empty (the
default): files stay where they always were, inside your notes (Classroom's in Kurooto's data folder).

**Updating:** nothing changes until you set these; with the defaults everything stays where it was in 0.2. Changing
them in Settings affects new notes and files only: nothing is moved. To move Kurooto's own notes along, use
[Fitting Kurooto to the notes you have](#fitting-kurooto-to-the-notes-you-have). Notes sync and Backups don't include the files folder: pick one your cloud
drive syncs, or back it up yourself.

**Undo:** set `notes.layout` back to `kurooto` and empty `notes.paths` and `files.folder`. New notes and files go to
the old places again; what was written in the meantime stays where it was put (nothing is deleted).

### Fitting Kurooto to the notes you have

The setup page's **Notes** step (later: dashboard → Settings → notes → **Fit Kurooto to your notes**, or `kurooto setup
notes`) reads a notes folder and proposes `notes.layout` and `notes.paths` for it. No AI is used and nothing leaves
your computer. It reads:
- the top-level folder names (hidden ones such as `.obsidian` and `.git` are left out);
- how daily notes are named and where: `journal/2026-10-20.md`, `dailies/`, `Daily Notes/2026-10-20.md`,
  `2026/10/20.md`;
- `[[wikilinks]]` or markdown links, with or without `.md`;
- the header keys in use (`id`, `aliases`, `tags`, `title`);
- where subject or course folders live;
- an inbox folder.

Each proposed line (daily notes, quick notes, subject folders, concept notes, research projects) says how sure it is
and why, and can be changed; the places that follow from a line follow it (course pages and lecture notes in the
subject folder, quick notes in the inbox). A preview shows the result ("Daily notes → `Daily Notes/2026-10-20.md`").

**Use this layout** saves the settings. When Kurooto has already written notes, the step first shows a plan: which of
**its own** notes move where (only notes with its header: `made_by`, or `trust_tier: agent_written` in the
zettelkasten layout), how many links in its own text are updated, and what stays. Your notes, your daily notes (they
hold your words) and your profile never move; links in your own words that point at a moved note are listed, never
changed. Links are updated only in Kurooto's notes, its `<!-- kurooto:... -->` blocks and the home note's course
list. Nothing in the notes folder changes before you confirm, and only as the plan shown says: a note changed since,
or a new place that's already taken, stops the whole move. Looking at another folder switches Kurooto to that folder;
its notes in the old one stay there. The step also proposes `notes.links` (`wiki` or `markdown`) from how your
notes link, and saves it with the rest.

*Leaves your computer:* nothing. *Undo:* the step's **Undo** puts the moved notes back, undoes the link updates and
sets the layout back (a move log in Kurooto's state folder, `notes-moves/`, works with or without git). A note you
changed since keeps your change, and the step says which.

## Where things are

Every setting, its default and what it does: [SETTINGS_GUIDE.md](SETTINGS_GUIDE.md).

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
| Test cases and taught phrasings | `cases/cases.json` in the state folder (not in backups or Profile sync) |

Secrets (bot token, keys) are in your system's keychain (Windows Credential Manager, macOS Keychain, or the Secret
Service on Linux), or, where there is none, in a file only your user can read in the settings folder.

Commands: `kurooto on` / `kurooto off` (completely, until turned on again), `kurooto pause [2h]` / `kurooto
resume`, `kurooto start` / `kurooto stop` (just for now), `kurooto open`, `kurooto setup [STEP]`, `kurooto doctor`,
`kurooto top`, `kurooto term`, `kurooto logs [-f]`, `kurooto sync`, `kurooto backup` / `kurooto restore <zip>`, `kurooto profile save|status|restore`,
`kurooto update`, `kurooto autostart on|off|status`, `kurooto cases`, `kurooto paths`, `kurooto rotate`, `kurooto
uninstall [--revoke]`. For scripts: `kurooto
notify`, `send`, `note`, `ask`, `ask-me`, `ask-approval`, `call`, `mcp`, `runlog`, `watch` (see
[From a terminal or a script](#from-a-terminal-or-a-script) and [Research](#research)).

## Troubleshooting

| What you see | What to do |
|---|---|
| The bot doesn't answer | `kurooto doctor`; is it running? Turned off? `kurooto on` (or Kurooto in your app menu). Is the computer asleep? See Stay awake on charger. |
| The bot says it's paused | `/resume`; or it's on battery with `power.on_battery` set to `pause`: plug in, or choose `saver`. |
| The AI doesn't answer, or something broke and you don't know what | `/fixme` (or `kurooto fixme` in a terminal): what fails, matched by rules to the troubleshooting page and known issues, with Fix buttons; it needs no AI. `/fixme <what you see>` finds the rows for it. |
| "needs a look" on the dashboard, or a "Needs a look" line in the weekly summary | `/health` (or the Features tab) says what and offers a Fix button where Kurooto can fix it; a sign-in that ended needs you (the line says where). |
| "Your alarm ... might not ring" | Set your phone's own alarm for tonight, then: Phone calls set up and linked (`kurooto doctor`), a phone paired (Phone tab). The Fix button reconnects or plans the alarm again. |
| A reminder didn't reach my phone while the lid was shut | `kurooto doctor`: the "Reminders with the lid shut" line says what your call line holds and for how many phones. "No phone can open them yet": update the Android app and open it once. Also check the app's checklist (notifications, **Battery: unrestricted**) and that the phone was online. Reminders set in the last seconds before the lid shut on a Mac come when it wakes. |
| A message came only in the evening bundle, or not at all | More than `notify.calm.messages` (6) came by themselves that day, it's exam season, you chose Fewer, Another time or Stop for that kind, or Dreaming tuned that kind (`/dream policy`). `/why` on the next one (or its Why? button) says which; `/calm` lists what's turned down, with buttons to start it again. `/calm off` restores the old behaviour. |
| Requests run at a different effort than before, the fallback AI answers first, or Start-by sizes changed | Dreaming tuned it from what was recorded (one change a night, said in the morning message). `/dream policy` shows what's tuned and why; the morning line's Undo puts it back, or remove the entry from `brain.effort_map`, `brain.fallback_first` or `startby.sizes`. `dreaming.tune_effort`, `tune_fallbacks` or `tune_sizing` = false stops that area. |
| A check-in call came as a message instead | The day's call (`notify.calm.calls`, 1) had come already. `/calm calls 2` allows two. |
| "Back online" every morning | Your laptop sleeps at night. Raise `notify.presence.after_min` past your night, or turn it off (`notify.presence.on` = `false`). |
| No "going offline" when the laptop sleeps | That message comes from your call line: it needs Phone calls set up, and Telegram from the line needs your OK (`notify.presence.line_telegram`); or add `"app"` to `notify.presence.channels`. |
| Building my profile failed | It's a big request: if your AI hit a limit, try again later or with a stronger AI (Settings → `brain.main`). |
| Something only happens when I plug in | That's the battery saver (Taking your laptop with you); set `power.on_battery` to `normal` to keep it all running. |
| The laptop still sleeps with the lid closed on the charger (Linux) | `awake.lid` is off, or your system refuses the lid hold to background programs (doctor says so). Allow it in polkit (`org.freedesktop.login1.inhibit-handle-lid-switch`) or set `HandleLidSwitchExternalPower=ignore` in logind.conf. |
| `kurooto autostart boot`: "Linux didn't allow that from here" | Run `loginctl enable-linger` in a terminal (it may ask for your password), then `kurooto autostart boot` (or Settings → Starting) again. |
| "I can't answer free text yet" | Turn on **Chat** (Features). |
| "Phrasings you taught: 1 phrasing you taught no longer works" | The request it stood for changed or its feature is off; it goes to the AI meanwhile. `/cases`: Unlearn it, then teach it again with `/wrong <words>` after it comes up. |
| Start-by dates come too early (or too late) | Tap the right size on a deadline (`/startby`). If they're all off, change how much of your free time counts (`startby.share`) or the day's window (`startby.window`). |
| A class pack "isn't a class pack I can use" | The message says why: a field the format doesn't have, or text that looks personal (an email, a link, a phone number). Ask whoever made it to fix that and make it again; `kurooto classpack check FILE` checks a file. |
| The AI says it isn't signed in | Setup page → AI → Install / sign in again → Test. |
| "It's at its usage limit" | Free tiers have daily limits. The other AI program answers meanwhile if it's set up (no fallback picked, or `brain.fallback`; the receipt says "... hit its limit; ... answered"); otherwise wait, or set a fallback brain (Settings → `brain.fallback`). `/usage` shows how often it happens and who is waiting for a reset. |
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
| Use this layout says a place is taken | One of Kurooto's notes would land where a note already is. Rename or move that note, or change the line on the Notes step; nothing moves until no place is taken. |
| Photos and PDFs still land in my notes | Set `files.folder` to a folder outside your notes folder (one inside it changes nothing). |
| The setup page won't open | `kurooto open`, or go to `http://127.0.0.1:8770`. If another program uses that port, Kurooto picks the next one (`kurooto paths` → `web.json` in the state folder says which). |
| Not enough space | The wizard says what needs it. Free some space, or choose fewer features. |
| "That question expired" | It waited longer than `ask.expire_hours` (or its asker stopped waiting); nothing was done. The asker asks again if it still matters. |
| I tapped a button and nothing happened | It may have been answered elsewhere already (on a call, in the app): `/q` shows what's still open. |
| `kurooto ask`, `call`, `send`, `ask-me` or `ask-approval` say Kurooto isn't running | `kurooto on`, then try again. Note that `--timeout` is in minutes. |
| No night check-in | It's off until you give it a time: Settings → Check-ins → `times`, e.g. `"night": "23:15"`. |
| A night check-in I didn't want | Empty its time in Settings → Check-ins → `times`, or `/checkin night skip` for today. |
| The night check-in didn't ring | The alarm was set and it was past your bedtime: it moved to the wake-up call (the message says so). `checkins.asleep_defers` off makes it always ring. |
| The evening check-in didn't list something I did | It lists only what was recorded that day (a deadline marked done or given progress, a thread closed, 15+ minutes of study, an after-class answer), three at most. Mark the deadline Done, or `/threads done N`. |
| Saying "gym" did nothing | A hook fires only on the word alone, with Commitments on; `/hooks` lists the words. "gym?" or "gym later" are ordinary messages. |
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
| `/mindjournal` (or another skill) goes to Chat as plain text | Turn on **Skills** (Features). `/skills` lists the names. |
| A revision pack comes as a `.tex` file | There's no LaTeX engine (neither Tectonic nor your own `latexmk` or `pdflatex`): tap **Install Tectonic** in the message that came with the pack. If you tapped **Not now**, it asks again after 30 days. |
| The first PDF takes minutes | Tectonic fetches the LaTeX packages it needs once (about 50 MB); later packs take seconds. |
| "it didn't compile" | The AI's LaTeX had an error it couldn't fix; the `.tex` is in your notes. `/pack` again, or reply with what to change. |
| A routine didn't run | It runs when the computer is on; one missed while it was off runs once when it's back (if that's still one of its days). `/routines` shows what's set. |
| "I'd rather not keep that" after /remember | It looked like a health, money or password detail. Put it in your own notes instead; reword it if it isn't one. |
| The look back never suggests anything | Most days that's right. `/lookback` shows when it last ran and what it noticed; on a laptop it waits for the charger. `/lookback now` runs one. |
| A skill change says "nothing changed" | The AI's version was the same, or it broke the skill's header; it's never saved then. It may suggest it again another night. |
| The nightly upkeep didn't finish | Search still works. Its log is in the state folder (`gbrain/upkeep-<date>.log`); it tries again the next night. Turn it off with `gbrain.upkeep`. |
| Notes brain: "can't find your gbrain" or "your brain's folder isn't there" | Your own GBrain: set `gbrain.exe` to the full path of your gbrain program and `gbrain.home` to its `GBRAIN_HOME` (or set `gbrain.managed` back to `true`). |
| A handwritten PDF isn't written out | PDFs read on this computer wait for the night on the charger (`/handwritten` starts it now; `/handwritten status` says where it is). It also waits while the graphics card is busy. "Can't be drawn": install Poppler's PDF tools. |
| A handwritten note has no Links section | Linking needs an AI (AI brain) and `handwritten.link` on; if the AI's answer was unusable nothing was written. `/handwritten link` tries every note without one again. |
| /notes or /timeline says the brain is busy | The nightly upkeep (or a sync) is using it; try again in a while. |
| Phone calls: "not connected to your call line" | Is this computer online? It reconnects by itself within a minute. Still not: Features → Phone calls → Set up (redeploys). |
| Cloudflare sign-in didn't finish | Press Set up again; the sign-in link is also shown in the progress log. |
| The phone doesn't ring | Every item on the app's checklist ticked? Battery unrestricted, and not on a "sleeping apps" list? Dashboard → Phone → Ring my phone. |
| A call keeps cutting itself off on loudspeaker | Use the earpiece or earphones, or move the mic gate slider to the right. |
| A call says "Reconnecting…" and then goes turn by turn | Google's live voice was down (`kurooto doctor`: "Phone calls: voice service"). Nothing to do; next time it tries Live again. Know another Live model? Add it to `calls.live_models`. |
| A call went to Telegram instead | Your phone couldn't turn speech into text, or the microphone wasn't allowed. Android: update the app (turn by turn needs this version) and allow the microphone; in a browser, use Chrome. Answer on Telegram meanwhile. |
| Turn by turn stops listening | The screen went off or you switched apps: tap **Talk**. In the Android app the screen stays on by itself. |
| Turn-by-turn answers are slow | Each turn waits for recognition, the text AI and the voice. With `calls.turn_brain` = `local` on a slow computer, use `gemini`. |
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
| Research: "isn't a git repository (no commits to follow)" | A note, not a problem: that project's folder has no git history yet, so its Log gets no commit lines. `git init` it (and commit) to follow it, or `/repos remove <folder>`. |
| Research add-on: "the LaTeX tracker needs Tectonic or LaTeX" | No LaTeX program here: `/latex install` fetches Tectonic, or install TeX Live, MiKTeX or MacTeX. |
| Research add-on: "LaTeX folder missing" | You moved or deleted it: `/latex remove <folder>`, then `/latex add <new folder>`. |
| `/runs compare` says "matches N runs" | Give more of the id, or the numbers `/runs` shows. |
| A run comparison has no code diff | The commit was rebased away or the repository moved; config and metrics are still compared. |
| `kurooto watch` says "only shown on this computer" | Kurooto wasn't running: `kurooto start`. |
| The Terminals tab says it's off, or a terminal won't type | Features → Terminals → Turn on. On Linux, a terminal from another user account is refused on purpose. |
| `/term` says "Term note …: not found" | The path is relative to your notes folder (`terms/2026-autumn`, `maps/semester-*`); `/term note <path>` again, or `/term note off`. |
| A class or date from the term note is missing | Check the table's heading ("Weekly timetable", "Key dates"), times like `09:00-09:55` and dates like `2026-11-12`; `/term` says how many classes and key dates it read. |
| Telegram's "/" menu is out of date | It updates within a minute of a feature going on or off, and every quarter of an hour for skills; `telegram.menu` off and on again sets it within a minute. |
| Your add-ons: a problem in `kurooto doctor` | `/addons` shows which file and the error. Fix it, then restart Kurooto (`kurooto stop`, `kurooto start`). |
| An add-on by link didn't load: "its files changed since you agreed to its card" | `kurooto addons update <name>` (or remove it and add it again). |
| An add-on isn't marked **Official** | It came from another address (a fork) or is at another commit than the one Kurooto lists. Remove it, then Add it from Official add-ons (or `kurooto addons add <name>`). |
| "The add-on X may only reach the hosts on its card" / "start the programs on its card" | Refused on purpose: it asked for something its card doesn't say. A newer version that declares it shows it when you update. |
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

**Subjects with folders, and files in the inbox (0.8.0).** Study → Subjects adds or removes a subject and gives it a folder of your notes (Study mode and the notes map use it). With `sorter.read_files` on, PDFs, Word and slide files and text you drop in the scratch folder are read into notes (no AI); originals stay. Copies are asked about (Keep both / Merge / Leave it), and `studypack.extra` adds your rules to a pack's prompt. *Undo:* the switches; Undo under a merge.

**Find files (`/find`, off).** Index chosen folders locally (names and text, no AI) and `/find <words>` lists matches with a Send button. *Undo:* turn the feature off; delete `finder/index.db` in the state folder.
