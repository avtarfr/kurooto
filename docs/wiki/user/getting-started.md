# Getting started

Paste one line into a terminal, follow the setup page that opens, make a Telegram bot (or pair the Kurooto phone app
instead), then send `/help` to it. That takes 15 to 30 minutes the first time. This page walks through each step and says what to do when something looks
wrong.

- [What you need](#what-you-need)
- [Install](#install)
- [The setup wizard, step by step](#the-setup-wizard-step-by-step)
- [Choosing an AI brain](#choosing-an-ai-brain)
- [Your first 15 minutes](#your-first-15-minutes)
- [Used Kurooto before?](#used-kurooto-before)
- [Where to go next](#where-to-go-next)

## What you need

**Always:**

| What | Why |
|---|---|
| A computer with Windows 10 or 11, macOS 12 or newer, or Linux | Kurooto runs on it. No graphics card is needed: the AI runs in the cloud unless you choose otherwise. |
| About 1 GB of free disk space, plus what your features need | The installer checks for at least 2 GB free. The setup page shows the total before installing anything, and Kurooto always leaves some space spare (it skips local AI models rather than fill your disk). |
| Telegram on your phone or computer (free), or the Kurooto phone app | This is where you talk to Kurooto. The phone app instead of Telegram needs Phone calls (a free Gemini key and a free Cloudflare account); see [step 7](#7-chat-telegram-or-the-phone-app). |
| A Google account (free) | For an AI brain: agy signs in with it, and a Gemini API key is made with it. |

Kurooto only works while the computer is on and awake. If you want it reachable all day, leave the computer on and
plugged in (see [Stay awake on charger](your-computer.md)).

**Only for some features:**

| Feature | Needs |
|---|---|
| Phone calls, Morning alarm, Reminders with the lid shut | a free Cloudflare account and a free Gemini API key |
| Voice notes | a free Gemini API key |
| Notes sync, Profile sync | a free GitHub account |
| Backups | a folder on an external drive, or a folder your computer syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox) |
| Google Classroom, Gmail drafts, the mail digest, reply drafts, Google Calendar, Drive upload, the Agent plan calendar | your Google account and about 10 to 15 minutes in Google Cloud (free; see [google.md](google.md)) |
| Revision packs as PDF | a LaTeX engine: your own (TeX Live, MiKTeX, MacTeX), or Tectonic, a small one Kurooto offers to install the first time |
| Claude Code as the AI | a paid Claude plan |

Nothing costs money unless you choose a paid plan (a paid AI plan you already have, or a paid Gemini key).

## Install

The installer works for your user only: no admin password. It sets Kurooto to start when you sign in, starts it, and
opens the setup page in your browser.

**Windows:** press Start, type `PowerShell`, open it, and paste:

```powershell
irm https://avtarfr.github.io/kurooto/install.ps1 | iex
```

**macOS:** open Terminal (Spotlight, then "Terminal") and paste:

```sh
curl -LsSf https://avtarfr.github.io/kurooto/install.sh | sh
```

**Linux:** open a terminal and paste the same line as macOS.

What the installer does, in order:

1. Checks there are at least 2 GB free.
2. Installs uv (a small Python manager) and Python 3.12, just for your user.
3. Downloads Kurooto, checks its signature and every file's checksum, and refuses anything that doesn't match.
4. Turns on start-at-sign-in, starts Kurooto, and opens `http://127.0.0.1:8770/setup`.

Run the same line again any time to repair or update an installation.

**The beta channel (testers).** To get releases before everyone else, put `KUROOTO_CHANNEL=beta` in front:

```sh
curl -LsSf https://avtarfr.github.io/kurooto/install.sh | KUROOTO_CHANNEL=beta sh
```

```powershell
$env:KUROOTO_CHANNEL = 'beta'; irm https://avtarfr.github.io/kurooto/install.ps1 | iex
```

The install then keeps following beta (the setting `updates.channel` becomes `beta`). To go back: Dashboard → Settings
→ updates → `updates.channel` = `stable`; you get the next stable release once it's newer than your beta.

**If something looks scary:**

| What you see | What it means |
|---|---|
| Windows Defender or an antivirus warns about a script | The line downloads a PowerShell script from Kurooto's release page. You can open the address in a browser and read it first. |
| macOS asks whether Terminal may control other apps or reach files | Only when a feature needs it (the Study tracker reads window titles). You can say no; that feature then says it can't. |
| The setup page didn't open | Open `http://127.0.0.1:8770/setup` yourself, or run `kurooto open`. If another program already uses port 8770, Kurooto takes the next free one; `kurooto paths` shows the state folder, where `web.json` names it. |

`127.0.0.1` means "this computer". Nothing outside your computer can open the setup page or the dashboard.

## The setup wizard, step by step

The setup page saves as you go: close it and come back any time (`kurooto setup`, or **setup** in the dashboard's
corner), and it opens on the first step you haven't finished. The steps are listed down the left on a wide screen, or
as numbered dots on a phone; tap any step to open it. Finished steps have a tick, skipped ones a dash, and a step you
passed but didn't finish (an AI that doesn't answer yet) shows **!**. Words with a dotted underline (API key, token,
repository, webhook...) explain themselves when you tap them.

**Skip for now.** Every step except **You** and **AI** has a **Skip for now** button: Kurooto needs your name and an AI
that answers, the rest can wait. Skipped steps aren't forgotten: the dashboard lists them under **Features → Finish
setting up** (the corner link then says **finish setup (2)**, say), `kurooto doctor` shows each as a note, and each
links back to its step (`kurooto setup about` opens About you). A step leaves that list once it's done, wherever you
did it.

Kurooto also notes how long you spend on each step and whether you finished or skipped it, so someone helping you can
see where setup got stuck. That stays on this computer; it's only in the zip `kurooto doctor --bundle` saves for you
(see [your-computer.md](your-computer.md#checking-that-it-works-diagnostics)), never what you typed.

If a button says "Kurooto isn't answering", Kurooto stopped or is restarting: start it from your app menu (or run
`kurooto on`), then press the button again; what you typed is kept. "This page is out of date" means Kurooto
restarted: reload the page.

### 1. You

- **What should it call you?** Your name, as it should greet you.
- **Your time zone.** Filled in from this computer. Reminders, check-ins and calls go by it. Start typing a city or
  region and pick from the list (`Europe/Berlin`, `America/New_York`), or leave it empty to use the computer's own.
  An old name for a zone is saved under today's name (`Europe/Kiev` becomes `Europe/Kyiv`).
- **Your assistant's name.** "Kurooto" by default. Change it later in Settings (`you.assistant_name`); the Telegram
  bot takes the new name too (see [talking-to-kurooto.md](talking-to-kurooto.md#renaming-your-assistant)).

The first page also has **I've used Kurooto before** (see [below](#used-kurooto-before)).

### 2. Your notes

Where Kurooto writes its notes (the daily note, a folder per subject, quick notes), and how. Already keep notes, in
Obsidian or any folder of Markdown files? Type that folder's full path (a Windows path like
`C:\Users\you\Documents\Notes` works, spaces too) and press **Look at this folder**. Kurooto reads the folder's names,
dates, links and headers, with no AI, and proposes a place for each kind of note: daily notes, the inbox, subject
folders, concept notes and research projects. Each line says how sure it is and why ("3 daily notes like
`Daily Notes/2026-10-20.md`"), and you can change any line. The preview under it shows where notes will go ("Daily
notes → `Daily Notes/2026-10-20.md`").

- **Use this layout** saves it. Nothing in your notes changes before you press it.
- **Keep Kurooto's own layout** keeps (or goes back to) Kurooto's folders: `journal/`, `about-me/`, a folder per
  subject.
- **Skip for now** leaves it for later. Kurooto's own layout is used until then.

You can come back to this any time from **Dashboard → Settings → notes → Fit Kurooto to your notes**, or with
`kurooto setup notes`. If Kurooto has already written notes, the step also shows which of them would move. Starting
fresh, with the notes folder still empty? There's nothing to fit in with: the step says so, folds all of the above under
**Change where each kind of note goes**, and **Next** is all there is to do. More:
[notes-and-concept-graph.md](notes-and-concept-graph.md#fit-kurooto-to-the-notes-you-have).

### 3. Your computer

Kurooto reads the computer: system, processor, memory, graphics card, free space, and what kind of setup it suits
(no local models, small local models, bigger ones, Apple Silicon). It lists what it recommends, marked ★. Nothing is
installed here: local models come with the features that use them (Local AI models, Notes brain) if you turn those on
in step 6.

- **Use more than this computer suggests:** pick another setup, add an Ollama model of your own (`gemma4:12b`) or
  another program (`tesseract`), then **Save** or **Save and install now**. Kurooto says plainly what you're going past
  (a model bigger than your graphics memory runs partly on the processor, slowly) but never refuses. See
  [your-computer.md](your-computer.md).
- **When this laptop is on battery** (laptops only): **★ Save battery** (Telegram keeps working; heavy work waits for
  the charger), **Keep everything running**, or **Pause everything**. This is `power.on_battery`.
- **Colours:** Kurooto's own greens (kuro), the older pinks (rose), or this computer's own colours (system, marked ★
  when Kurooto finds them). Only how Kurooto's pages look. See [dashboard.md](dashboard.md).

### 4. AI: pick the AI that answers you

Pick a card, then follow its panel. The first card is marked ★. Each panel ends with a test: Kurooto asks the AI to
reply and tells you whether it worked, and if not, what to do.

| Card | What you do |
|---|---|
| Antigravity (agy) | **Install agy** (Google's official installer), **Open the sign-in window**, sign in with Google, close the window, **Test it**. |
| Gemini API key | Open Google AI Studio → Create API key, paste the key (it starts with `AIza`), **Save and test**. |
| Claude Code (under Advanced) | **Install Claude Code**, **Open the sign-in window**, sign in with your Claude account, **Test it**. Needs a paid Claude plan. |
| Ollama on this computer | **Install Ollama**. Private and offline, much weaker; best as a helper next to another AI. |
| Another OpenAI-compatible service | Its address (usually ending in `/v1`), key and model name, then **Save and test**. |

If the test fails, the panel says what to do. You can go on without a working AI and finish this step later. Details
of each brain, and what each costs: [ai-brains.md](ai-brains.md).

**Try it now.** Once the AI answers its test, a chat box appears under it. What you type there is handled exactly like
a Telegram message, before Telegram is set up:

- `remind me in 2 minutes to stretch` pops up on this computer two minutes later;
- a question goes to your AI and its answer comes back in the box (it can take up to a few minutes).

Chat and Reminders answer there even though you turn them on later; other features answer once they're on. Nothing
said in the box goes to Telegram or your phone. A reminder set there still comes after a restart; cancel it with
`/reminders` once Telegram is connected.

### 5. About you (recommended, optional)

Your other AI accounts (ChatGPT, Claude, Gemini, Copilot and the rest) already know a lot about you. This step brings
that into Kurooto once:

1. Type which AI and account you're starting with ("ChatGPT personal"), then press **Copy the prompt** on **Your main
   AI** (the account you use most, the fullest audit) or **Every other account**.
2. Paste it into a new chat in that account. Turn on its memory or "search past chats" first if it has them.
3. Copy its whole answer (or download it), paste it in the box and press **Add this report**, or upload `.md` /
   `.txt` files. Repeat for as many accounts as you can.
4. Press **Build my profile**. Your AI merges the reports into `about-me/profile.md` in your notes.
5. Read it in the editor under the button and fix anything that's off. **Save** keeps the old version beside it;
   **Preview In brief** shows the part that goes along with every AI request.

The reports stay in Kurooto's private folder (not your notes, never synced); building the profile sends them to the AI
you picked. **Skip for now** (or Next with no reports added) skips this step. More:
[teaching-kurooto.md](teaching-kurooto.md).

### 6. Features: what should it do?

Every feature is off until you tick it. First, **What do you do?** adds what suits it to Starter (each such card
says "★ suits what you do"); you can still untick anything:

| Answer | Added to Starter |
|---|---|
| **Student** | Subjects and timetable, Start-by dates, Quiz, After-class notes, Doubt queue, Weekly summary |
| **Working** | Commitments, Start-by dates, Calendar, Weekly summary |
| **Research** | Research, Commitments, Start-by dates, Weekly summary |
| **Something else** | nothing: Starter as it is |

Then three buttons pick a set:

| Button | Turns on |
|---|---|
| **★ Starter (recommended)** | Telegram, Chat with your AI, Reminders, Check-ins, Deadlines |
| **Everything** | every feature offered (Exam season is not in any set: turn it on by hand later) |
| **Pick myself** | only what you tick |

The cards for you come first: Starter's, what suits your answer, and what you've ticked. The rest (about 45) wait
under **More features**: open it to pick from all of them. Each card says what the feature does and what leaves your
computer. Some ask for a detail right on the card once
ticked: a calendar link, a repository and token, a Google client file, a backup folder. Phone calls shows what it
needs in order (a Gemini key, then a free Cloudflare account) and a **Set up now** button that makes your call line
right there; a Cloudflare sign-in page opens in your browser. Phone calls, Voice notes and the Morning alarm need a
Gemini key even if another AI answers your messages: a key box appears under the first of those cards you tick.

The Notes brain is a 0.5 GB download, so it's not in Starter. You can change any of this later on the dashboard
(Features, Alt+F).

**How many messages a day.** Under the cards, one line says it plainly: "Kurooto sends at most 6 messages a day on its
own; the rest wait for one evening bundle at 20:00. Your own reminders, alarms and approvals always come." Change the
number in the box beside it (`notify.calm.messages`); more about the limit in
[messages-it-sends.md](messages-it-sends.md#calm-why-less-of-this-and-the-daily-limit).

### 7. Chat: Telegram or the phone app

Pick where you talk to Kurooto: **Telegram** (your own private bot) or **The Kurooto phone app instead**.

**The phone app instead.** Its chat does what the bot does: commands, reminders, check-ins, questions with buttons,
your AI's answers; files come as links. It needs Phone calls: tick it on the Features step and press **Set up now**
(a free Gemini key, then your call line on a free Cloudflare account). Back here, **Pair my phone now** shows a QR code
(or pair after **Finish setup**). Telegram can be added later from the dashboard. More:
[Using the app instead of Telegram](phone-app.md#using-the-app-instead-of-telegram).

**Telegram.** You talk to Kurooto through your own private bot. It takes about two minutes:

1. In Telegram, open **@BotFather** (Telegram's official bot-maker, with the blue tick) and send `/newbot`.
2. Answer its two questions: a display name, then a username ending in `bot`.
3. BotFather replies with a token like `123456789:AAH…`. Copy the whole token, paste it on the setup page and press
   **Check the token**.
4. The page says "Found your bot @yourbot" and shows **Open @yourbot**. Tap it, then press **Start** in Telegram.
5. The page says it's connected, and the bot greets you: "This chat is now ours; I'll ignore everyone else."

From then on the bot answers only your Telegram account; anyone else who finds it is ignored.

**If it doesn't connect:**

| What the page says | What to do |
|---|---|
| "That doesn't look like a bot token" | Copy the whole token line from BotFather's message (a number, a colon and a long code), not the bot's name or link. |
| Telegram didn't accept the token | Copy it again, or send `/token` to BotFather to get it again. |
| "Got a /start without the code" | You pressed Start without the code. Send the message the page shows (it starts with `/start` and a code); there is a **Copy** button. |
| "This link expired: get a new one" | The link works for one hour. Press **Get a new link**. |
| "That token was revoked" | Get the new token from @BotFather and paste it. |
| "This bot is connected to a web address (a webhook)" | Another service was set up to receive this bot's messages. Press **Disconnect it**. |
| "Another program is reading this bot's messages" | Maybe another Kurooto using the same bot. Stop the other one, or make a new bot with @BotFather. |
| "Can't reach Telegram right now" | Check the internet; it keeps trying. |

You can **Skip for now** and connect it later (Next without a connection skips it too); the step waits on the
dashboard's Finish setting up list until Telegram is paired or, with the phone app picked, Phone calls is set up.

### 8. Almost done

The summary lists your AI, Telegram (or the phone app), the features you picked, the steps you skipped (each with
**Go back to it**) and your notes folder (by default `Documents/Kurooto`,
or `~/Kurooto` on Linux without a Documents folder). Tick or untick **Start Kurooto when I sign in to this computer**
(★ recommended), then **Finish setup**. Kurooto installs what your features need (with progress for each), turns them
on, and starts. Anything that isn't ready is listed as "Not turned on yet" with the reason; finish it later from the
dashboard. If you chose Phone calls, a QR code appears to pair your phone (it works for 15 minutes; `/phone` on
Telegram makes a new one). Then **Open the dashboard**.

## Choosing an AI brain

Short version:

- **Antigravity (agy)** is free with a Google account and can read your notes and act on your computer within limits.
  There is some risk to the Google account, because Google's answers differ on whether other tools may start agy
  unattended.
- **A Gemini API key** is the simplest and the way Google recommends for tools like this. The free tier has small daily
  limits, and Google may use what you send to improve its products. You need one anyway for calls, voice notes and
  the alarm.
- **Claude Code** if you already pay for Claude.
- **Ollama** only as a private, offline helper on a computer with a good graphics card.

Set a **fallback** too, so a second AI takes over when the first hits its limit. Everything about brains:
[ai-brains.md](ai-brains.md).

## Your first 15 minutes

Send these to your bot, one at a time:

| Type | What happens |
|---|---|
| `/help` | Lists the commands of the features you have on, in groups, and what you can just say. |
| `remind me in 2 minutes to stretch` | A reminder arrives in two minutes, with **+10 min** and **+1 h** buttons. |
| `what's due?` | Your deadline list (empty at first). |
| `/due fri 17:00 essay draft` | Adds a deadline; you'll get a nudge a day before. |
| `what is a vector space?` | A question for your AI (needs Chat). It replies "On it." and the answer follows. |
| `/checkins` | Today's check-ins. The evening one comes at 22:00 by default. |
| `/status` | What's going on: calls, focus, what's coming, open questions. |
| `/brain` | Which AI answers, and whether it works. |

Then, if you like:

- Reply to the evening check-in when it comes: your reply goes into your journal.
- Add your subjects and classes: `/subject add Linear Algebra (la)`, `/class mon 09:00-09:55 la`
  ([classes-and-timetable.md](classes-and-timetable.md)).
- Open the dashboard (`kurooto open`, or `http://127.0.0.1:8770`) and look at **Today** (Alt+T).
- Turn on more features: dashboard → Features (Alt+F). **First-week quests** sends one small thing to try each day
  for a week.

## Used Kurooto before?

On the first page, press **I've used Kurooto before**. This works if Profile sync was on before. Give:

- the private repository Profile sync used (`owner/name`);
- a token for it (lost it? make a new fine-grained token for that repository with Contents: Read and write);
- your profile's passphrase.

Press **Restore**. Your settings, keys and saved state come back, and with Notes sync your notes too. The page then
lists what's still to do on this computer (sign your AI in again, install what features need, pick folders that were
on the old computer), and **Continue** walks you through it. Turn Kurooto off on the old computer first (`kurooto
off`): two computers can't share one Telegram bot or one call line. Details:
[updates-and-backups.md](updates-and-backups.md).

## Where to go next

- How to talk to it, and what it does with your messages: [talking-to-kurooto.md](talking-to-kurooto.md)
- Every command and phrase in one place: [commands.md](commands.md)
- Why a message came, and how to get fewer: [messages-it-sends.md](messages-it-sends.md)
- What leaves your computer: [privacy.md](privacy.md)
- Something wrong: [troubleshooting.md](troubleshooting.md)


## Settings: drop-downs and explanations

In the dashboard's Settings, a setting that takes one of a few values (who reads scanned pages, how often, which day) is a drop-down instead of a box to type a word into, and hovering over any setting
shows what it does. Free text stays a box only where any text is valid.


## Finishing a feature's set-up

Every time you switch a feature on in Features, the message under it lists what is left to set it up: what to turn on first, what its own check says is missing, and the steps only you can do (a bot token, a
sign-in, installing Poppler or Ollama) with the exact command and how to undo it. `/health setup` lists what is left for every feature that is on.
