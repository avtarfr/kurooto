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
- [Your phone](#your-phone)
- [The dashboard](#the-dashboard)
- [Taking your laptop with you (battery, pause, off)](#taking-your-laptop-with-you-battery-pause-off)
- [Updates and going back](#updates-and-going-back)
- [Your computer and Kurooto (hardware profiles)](#your-computer-and-kurooto-hardware-profiles)
- [Where things are](#where-things-are)
- [Troubleshooting](#troubleshooting)
- [Getting help (diagnostics)](#getting-help-diagnostics)
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
- **A Google account** (free): for the recommended AI (Antigravity) or a free Gemini key.

**Optional, depending on the features you pick:**

| Feature | Needs |
|---|---|
| Phone calls, Morning alarm | a free [Cloudflare](https://dash.cloudflare.com/sign-up) account and a free Gemini key |
| Notes sync | a free [GitHub](https://github.com/signup) account |
| Google Classroom, Gmail drafts | your Google account, plus about 10 minutes in Google Cloud (free) |
| ChatGPT as the AI | a paid ChatGPT plan |
| Claude as the AI | a paid Claude plan |

Nothing costs money unless you choose a paid AI plan you already have.

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
as you go, so you can close it and come back.

1. **You:** what Kurooto calls you, your time zone (filled in from your browser) and the assistant's name.
2. **Your computer:** what Kurooto found (processor, memory, graphics card, free space) and what it recommends for
   it, marked ★. You can change any of it later.
3. **AI:** pick the AI that answers you (see [Your AI brain](#your-ai-brain)). ★ marks the recommendation. Press
   **Install** if it isn't installed, follow the sign-in, then press **Test**: it asks the AI to reply, and tells you
   if it worked.
4. **About you** (★ recommended, optional): teach Kurooto what your other AI accounts already know about you. See
   [About you](#about-you) below.
5. **Features:** the **★ Starter** set is a good start (Telegram, chat, reminders, check-ins, deadlines, and the notes
   brain if there's room). **Everything** or **Pick myself** for more. Some features ask for a detail right in their
   card (a calendar link, a repository); phone calls, voice notes and the alarm ask for a free Gemini key.
6. **Telegram:** make your own bot in two minutes:
   1. Open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, answer its two questions (a display name,
      then a username ending in `bot`).
   2. BotFather replies with a token like `123456789:AAH…`. Paste it in the wizard and press **Check**.
   3. Tap the link the wizard shows, then **Start** in Telegram. Kurooto now knows that chat is yours and ignores
      everyone else.
7. **Done:** Kurooto installs what your features need (with progress), turns them on, and, if you chose Phone calls,
   shows a QR code to pair your phone. Send `/help` to your bot.

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
5. Press **Build my profile.** Your AI merges the reports into one profile, `about-me/profile.md` in your notes. Read
   it and fix anything that's off; Kurooto reads its short "In brief" part before every AI request. Building again
   keeps the previous version next to it.

The reports themselves stay in Kurooto's private data folder (not your notes, never synced). Remove anything you'd
rather not keep before adding a report. Come back any time with more accounts: open the setup page (`kurooto open`, then
"setup") and go to About you.

## Your AI brain

The "brain" is the AI that answers your messages and does tasks. You can change it any time (dashboard → Settings, or
the setup page), and set a **fallback** that takes over when the first one hits its limit.

| Brain | Cost | Good for | Setup |
|---|---|---|---|
| **Antigravity (agy)** ★ | free with a Google account | the strongest free option; can read your notes | Install → a window opens → sign in with Google |
| **Gemini API key** | free | simplest; also needed for calls and voice notes | [Google AI Studio](https://aistudio.google.com/apikey) → Create API key → paste |
| **ChatGPT / Codex** | needs a paid ChatGPT plan | if you already pay for ChatGPT | Install → sign in with your ChatGPT account |
| **FreeLLMAPI** | free | a pool of many providers' free tiers; more setup | install its app, copy its key into the wizard (personal experimenting only) |
| **Local (Ollama)** | free | private and offline, but much weaker | only offered on computers with a graphics card or Apple Silicon |
| **Custom** | depends | any OpenAI-compatible service | its address, key and model names |
| **Claude Code** (Advanced) | needs a paid Claude plan | if you already pay for Claude | Install → sign in with your Claude account |

**Limits:** free tiers have daily limits. When the brain hits one, Kurooto tells you once and uses your fallback if
you set one. **How hard it thinks:** Kurooto picks low, medium or high effort per request; start a message with
`high:` or `low:` to choose.

## Features

Every feature is off until you turn it on (wizard, or dashboard → **Features**). Turning one off stops it at once;
its data stays unless you delete it. Each section says what leaves your computer; [PRIVACY.md](PRIVACY.md) has the
full list.

Plain English works for many things ("remind me at 9 to call mum", "move tonight's check-in to 21:30", "what's due?",
"wake me at 6:45"). `/help` lists the commands of the features you have on.

### Telegram
Your own bot, which only answers you. Commands: `/status` (what's going on), `/hold 2h` or `/hold 18:00` (no calls
until then), `/calls` (allow calls again), `/focus 2h` (do-not-disturb: messages wait until it ends).
*Leaves your computer:* your messages travel through Telegram to your bot.

### Chat with your AI
Anything that isn't a command or an instant request goes to your AI; the answer comes back as a reply. Long answers
arrive as a file. `/brain` shows which AI answers and whether it works; `/jobs` the last few requests.
*Leaves:* what you ask, and notes it reads, go to the AI you picked.

### Reminders
"remind me at 9 to call mum", "remind me in 20 minutes to take the pasta off", `/remind tomorrow 7am gym`,
`/reminders`. A reminder due while the computer slept arrives when it wakes, marked late. Buttons: +10 min, +1 h.

### Check-ins
At times you choose (default 22:00; a midday one is optional), Kurooto asks how the day is going. Reply to the message
and it goes into your journal (`journal/YYYY-MM-DD.md` in your notes folder). "move tonight's check-in to 21:30",
"skip the midday check-in", `/checkins`. With **Phone calls** on, a check-in can be a call instead (Settings →
`checkins.by_call`): what you say goes into your journal, and a missed call falls back to Telegram.

### Deadlines
From what you add (`/due fri 17:00 essay draft`, "the essay is due friday 5pm"), from dated tasks in your notes, and
from Google Classroom if you use it. A nudge a day before, an urgent one six hours before; buttons for Done, Not mine,
Snooze. `/deadlines` shows two weeks.

### Subjects and timetable
Your courses with short names (`/subject add Linear Algebra (la, linalg)`) and your timetable
(`/class mon 09:00-09:55 la`). Kurooto never calls you during a class. `/classes today`, `/skip la` (not going
today), `/attend la` (undo). Other features use the subjects: after-class notes, the quiz, the study tracker.

### Quiz
Practice questions from your notes, spaced out so you see each again just before you'd forget it. Put a note named
like `exam-prep.md` with a `## Must know` list in a subject's folder. `/quiz`, `/quiz la`, `/quizstatus`. Reply with
your answer; grade yourself with the buttons. Works on calls too.

### Weekly summary
Every Sunday evening: the week in numbers (requests, reminders, check-ins, deadlines, quiz, study hours). `/week`.

### Files into notes
Send a photo or PDF to your bot: it's saved in your notes folder's `inbox/`. With Chat on, the AI files it properly
(a note that describes and links it, in the right place). The caption tells it what it's for.

### Notes brain (GBrain)
Search your notes by meaning (`/notes what is a compact space`), and your AI gets a memory of them. Kurooto installs
[GBrain](https://github.com/garrytan/gbrain) and keeps its index in Kurooto's own folder; it re-reads your notes
every 15 minutes. On computers without a graphics card the index is made with Gemini (note text goes to Google) or
keyword-only; with a graphics card or Apple Silicon it stays on your computer.

### Local AI models
Small AI models on your computer (through [Ollama](https://ollama.com)), picked for its graphics card, for quick
decisions and the notes index: private and offline. Not offered on computers without a graphics card or Apple
Silicon. `/models`.

### After-class notes
A couple of minutes after each class in your timetable ends, Kurooto asks what was worth keeping. Your reply goes into
that subject's `class-log.md`. Needs Subjects with a timetable.

### Nightly look back
Once a day, the AI looks at how the day went (counts only: what you answered, ignored, moved) and suggests at most
three small changes to your settings, such as a better check-in time. Nothing changes unless you tap **Approve**.

### Phone calls
Talk to Kurooto like a phone call, and let it call you: reminders ("call me at 5 about the laundry"), check-ins, the
morning alarm. During a call it can search your notes, add reminders and deadlines, start tasks on your computer, and
more, depending on which features you have on.

**How it works:** setup makes your own *call line*, a small program on your own free Cloudflare account (it's yours;
nobody else's server is involved). Your computer keeps a connection to it, and your phone pairs with it. Calls use
Google's Gemini Live with your own free key, so the audio goes between your phone and Google. If your computer is off,
calls still work from what it last sent, and anything that needs the computer waits until it's back.

**Set up:**
1. A free Gemini key (the wizard asks for it).
2. **Set up** Phone calls. Kurooto installs what it needs (about 350 MB, once), then opens Cloudflare's sign-in in
   your browser: sign in or make a free account, and approve. Kurooto makes the call line (named `kurooto-` plus
   random letters) at a `workers.dev` address. The address is public but useless without a key from your computer.
3. Pair your phone (see [Your phone](#your-phone)).

**Use:** `/call` gives you a link to call now from any phone or browser (it works for 2 hours). "call me in 20 minutes
about the essay". `/phones` lists paired phones, `/unpair <id>` removes one. Kurooto tells you whenever a new device
pairs; if it wasn't you, remove it.

**On the call:** speak naturally. If the loudspeaker's echo cuts Kurooto off, use **Interrupt** to talk over it, or
the earpiece / earphones. The mic gate slider makes it need a louder voice in a noisy room.

*Leaves:* call audio goes to Google (your key); the call line keeps a short brief (what's due, today's classes, your
notes' titles) on your Cloudflare account for calls while the computer is off. Transcripts stay on your computer.

### Morning alarm
Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm volume, so it rings even
on silent; answer and it says good morning and goes through your day. The call line places it, so it rings even if
your computer is asleep. "wake me at 6:45", `/alarm 7:30`, `/alarm off`, or a daily default (Settings →
`alarm.daily`). Not answered: it rings twice more, 5 minutes apart. **Snooze** gives 10 minutes. Needs Phone calls.

### Voice notes
Send your bot a voice message: it's written out (you see what it heard) and handled like a typed message. Uses your
free Gemini key. *Leaves:* the recording goes to Google; on the free tier Google may use what you send to improve its
products, so don't say anything you wouldn't type.

### Stay awake on charger
While your computer is plugged in, it doesn't go to sleep by itself, so Kurooto keeps answering; on battery it sleeps
as usual. The screen can still turn off. **A closed lid usually still sleeps a laptop:** to keep it running with the
lid closed, change the lid setting. Windows: Control Panel → Power Options → "Choose what closing the lid does" → "Do
nothing" when plugged in. macOS: only with an external display. Linux: your desktop's power settings.

### Calendar
Your calendar's events, read-only, from its private iCal link. Google Calendar on a computer: Settings → your calendar
→ Integrate calendar → **Secret address in iCal format**. Outlook and Apple Calendar have one too. Paste it in the
feature's card. `/today`, `/cal` (7 days), "what's on tomorrow?". Kurooto doesn't call you during an event (Settings →
`calendar.no_calls_in_events`) and can remind you before each one (`calendar.remind_min`). Refreshed every 15 minutes.
The link lets anyone read that calendar, so it's kept in your computer's keychain.

### Notes sync
Your notes folder, kept in your own **private** GitHub repository: every change is in its history, and edits made
elsewhere (another computer, GitHub's website) come in too. Every 10 minutes, and with `/sync`.

**Set up:** 1. [Make a repository](https://github.com/new): any name, **Private**, nothing ticked. 2. [Make a
fine-grained token](https://github.com/settings/personal-access-tokens/new): Repository access → Only select
repositories → that one; Permissions → Contents → **Read and write**. 3. Paste both in the feature's card. Kurooto
refuses a public repository. Git is installed for you if it's missing (on a Mac, Apple's installer opens: click
Install, then press Set up again).

If the same lines of a note changed in two places at once, your computer's version wins; the other is still in the
history. With Phone calls on, your call line can read whole notes from the repository while your computer is off.

### Google (Classroom, Gmail drafts)
Classroom assignments go into Deadlines (marked done when you hand them in); new posts in your courses come to
Telegram. Gmail drafts: `/draft someone@example.com ask for an extension on problem set 3` (the AI writes it) or
`/draft someone@example.com | subject | the email`. **Kurooto never sends email**: drafts wait in Gmail for you.

**Set up (about 10 minutes, once):** Kurooto uses your own Google "OAuth client", so no one else's app ever holds your
Google access. The feature's card links each page:
1. Make a Google Cloud project (any name).
2. Turn on the **Google Classroom API** (and the **Gmail API** for drafts).
3. **OAuth consent screen:** External, your email as the contact, then **Publish app** ("In production"; otherwise
   Google signs you out every 7 days).
4. **Credentials → Create credentials → OAuth client ID → Desktop app → Download JSON.**
5. Paste the file's contents in the card and press Save; Google's sign-in opens. It says "Google hasn't verified this
   app": that's expected for your own client. Advanced → Go to (your project) → Continue.

Gmail drafts are off by default (Settings → `google.gmail_drafts`; then sign in again). School accounts sometimes
block unverified apps; then use the Calendar feature's iCal link for your timetable instead.

### Handwritten notes
Drop a PDF or photo of handwritten pages into a folder (by default `handwritten-inbox` in your notes folder; set
`handwritten.folder` to one your tablet syncs to through Google Drive, OneDrive or Dropbox). Kurooto writes it out as
a Markdown note with the maths in LaTeX, saved in `handwritten/` next to a copy of the original. Every 15 minutes, or
`/handwritten`. Uses Gemini (your free key), or, on computers with 12 GB of graphics memory and Local models on, a
model on your computer for photos.

### Study tracker
How long you spend on each subject, counted from the window you're working in: a window whose title names a subject
(its name or a short name, a PDF called `linear-algebra-week3.pdf`, a note in that subject's folder) counts while
you're active. Only minutes per subject are kept, never window titles. `/study`, `/study week`, `/studied 2h linear
algebra` (time away from the computer). Works on Windows, macOS (it asks once to see window titles) and Linux on X11,
Hyprland or Sway. Needs Subjects.

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

**Project logs:** for your code repositories on this computer (on the Research tab, or `/repos add ~/code/my-model`),
each day's new commits are written into `research/<repository>-log.md` in your notes.

### Other programs can message you
Scripts and other tools on your computer can send you a message through Kurooto (Telegram, the desktop, however you
set it up): `kurooto notify --title "Backup" "The backup finished."`. It needs Kurooto running; otherwise the message
only shows on this computer, and the command exits with 2.

## Your phone

### Android (recommended)
The Kurooto app rings like a real phone call (full screen, even on the lock screen), uses the earpiece with the screen
off at your ear, rings wake-up calls on the alarm volume, and lets you share files to your notes. It works from
Android 6.

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
4. Tap **Turn on call notifications** and allow them.

**What doesn't work on iPhone:** calls arrive as notifications you tap to answer; they can't ring like a phone call,
ring on silent, or show on the lock screen as a call. If you need those, use Telegram reminders or an Android phone.

## The dashboard

`http://127.0.0.1:8770` (or `kurooto open`). STATUS shows your computer; SYSTEMS shows each feature as a living cell
that pulses when something happens; NOTES is a map of your notes and their links (click a note to read it). The tabs:
**Activity** (what happened), **AI jobs**, **Schedule** (what's coming), **Features** (turn on/off, set up), **Phone**
(your call line, pairing, a test ring), **Settings** (every setting, with what it means).

Only your computer can open the dashboard; it needs a key that only this computer has.

## Taking your laptop with you (battery, pause, off)

**On battery**, Kurooto saves your battery by default: everything that leans on the laptop waits for the charger,
and **Telegram keeps working**.

| Keeps working on battery | Waits until it's plugged in |
|---|---|
| Telegram: messages, commands, plain-English requests | Local AI models (unloaded, freeing the graphics card) |
| Reminders, check-ins, deadlines, the calendar | The notes brain's indexing, Notes sync |
| Answers to what you ask the AI | Handwritten notes, Research, the nightly look back |
| Phone calls and the morning alarm | AI work nobody asked for (e.g. the weekly paper picks) |

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

## Updates and going back

Kurooto updates itself. Settings → `updates.mode`:
- **night** (default): a new version is downloaded when found and switched to between 03:00 and 05:00, when the
  computer isn't busy and you're not on a call.
- **ask**: Telegram asks you (Update / Later / Skip).
- **off**.

Every release is signed; Kurooto refuses anything unsigned, older, or changed on the way. The previous two versions
stay installed. If a new version crashes three times in its first five minutes, Kurooto goes back to the one before
and won't offer the broken one again; you're told on Telegram. `kurooto update --now` installs an update right away.

Your call line is updated after Kurooto updates, if its code changed. The Android app shows an Update button; the
iPhone web app updates itself.

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

## Where things are

`kurooto paths` prints them. By default:

| | Windows | macOS | Linux |
|---|---|---|---|
| Settings | `%LOCALAPPDATA%\Kurooto\config` | `~/Library/Application Support/Kurooto/config` | `~/.config/kurooto` |
| Data | `%LOCALAPPDATA%\Kurooto\data` | `~/Library/Application Support/Kurooto/data` | `~/.local/share/kurooto/data` |
| Logs | `%LOCALAPPDATA%\Kurooto\state\logs` | `~/Library/Logs/Kurooto` | `~/.local/state/kurooto/logs` |
| The program | `%LOCALAPPDATA%\Programs\Kurooto` | `~/Library/Application Support/Kurooto/app` | `~/.local/share/kurooto/app` |
| Your notes | `Documents\Kurooto` | `~/Documents/Kurooto` | `~/Documents/Kurooto` (or `~/Kurooto`) |

Secrets (bot token, keys) are in your system's keychain (Windows Credential Manager, macOS Keychain, or the Secret
Service on Linux), or, where there is none, in a file only your user can read in the settings folder.

Commands: `kurooto on` / `kurooto off` (completely, until turned on again), `kurooto pause [2h]` / `kurooto
resume`, `kurooto start` / `kurooto stop` (just for now), `kurooto open`, `kurooto doctor`, `kurooto update`,
`kurooto autostart on|off|status`, `kurooto paths`, `kurooto uninstall`.

## Troubleshooting

| What you see | What to do |
|---|---|
| The bot doesn't answer | `kurooto doctor`; is it running? Turned off? `kurooto on` (or Kurooto in your app menu). Is the computer asleep? See Stay awake on charger. |
| The bot says it's paused | `/resume`; or it's on battery with `power.on_battery` set to `pause`: plug in, or choose `saver`. |
| Building my profile failed | It's a big request: if your AI hit a limit, try again later or with a stronger AI (Settings → `brain.main`). |
| Something only happens when I plug in | That's the battery saver (Taking your laptop with you); set `power.on_battery` to `normal` to keep it all running. |
| "I can't answer free text yet" | Turn on **Chat** (Features). |
| The AI says it isn't signed in | Setup page → AI → Install / sign in again → Test. |
| "It's at its usage limit" | Free tiers have daily limits: wait, or set a fallback brain (Settings → `brain.fallback`). |
| The setup page won't open | `kurooto open`, or go to `http://127.0.0.1:8770`. If another program uses that port, Kurooto picks the next one (`kurooto paths` → `web.json` in the state folder says which). |
| Not enough space | The wizard says what needs it. Free some space, or choose fewer features. |
| Phone calls: "not connected to your call line" | Is this computer online? It reconnects by itself within a minute. Still not: Features → Phone calls → Set up (redeploys). |
| Cloudflare sign-in didn't finish | Press Set up again; the sign-in link is also shown in the progress log. |
| The phone doesn't ring | App checklist all ✓? Battery unrestricted, and not on a "sleeping apps" list? Dashboard → Phone → Ring my phone. |
| A call keeps cutting itself off on loudspeaker | Use the earpiece or earphones, or move the mic gate slider to the right. |
| iPhone gets no notifications | Opened from the Home Screen (not Safari)? Turned on in the app? iOS 16.4+? Settings → Notifications → Kurooto. |
| Notes sync: "a change elsewhere clashes" | Nothing was lost. Open the repository on GitHub, keep the version you want in the note, then `/sync`. |
| Google: "sign-in expired" | Features → Google → Save (signs in again). If it happens every 7 days, publish the consent screen (step 3). |
| Something else | `kurooto doctor --bundle` and send the zip to whoever is helping you (see below). |

## Getting help (diagnostics)

`kurooto doctor` checks Kurooto, your AI, every feature you have on, and free space; each line says what's wrong.

`kurooto doctor --bundle` saves a zip you can send to someone helping you. It contains Kurooto's checks, its log,
your settings and what happened recently, with **secrets, names, email and web addresses and your folders blanked
out**. It never contains your messages, notes, journal, transcripts, or what you asked the AI. Nothing is sent
anywhere: look inside the zip first, then send it yourself.

## Uninstall

`kurooto uninstall` removes Kurooto: the program, its settings, data and start-at-sign-in. `kurooto uninstall
--keep-data` keeps your settings and data. On Windows you can also use Settings → Apps → Kurooto.

**Your notes folder is never deleted.** Things Kurooto installed for you that live in its own folder (Node.js, MinGit,
Ollama on Linux) go with it; programs installed system-wide (agy, Ollama on Windows/macOS, Telegram Desktop) stay,
since you may use them. Your call line stays on your Cloudflare account until you delete it there (Workers & Pages →
the `kurooto-…` worker → Settings → Delete); paired phones stop working once it's gone. A Google client can be deleted
in Google Cloud; a notes repository stays yours.

## FAQ

**Does it cost anything?** No, unless you pick a paid AI plan you already have. Cloudflare, Gemini (free tier),
Telegram, GitHub and Google Cloud are used within their free plans.

**Does my data go to whoever made Kurooto?** No. Nothing is ever sent to Kurooto's author. What leaves your computer
goes to the services you chose, under your own accounts; [PRIVACY.md](PRIVACY.md) lists it per feature.

**Does it work when my computer is off?** Telegram messages wait until it's back. Phone calls and the alarm still
work from your call line; anything that needs the computer is done when it's back.

**Can someone else talk to my bot?** It answers only the Telegram account that tapped the pairing link; everyone else
is ignored.

**Can I use it on two computers?** One at a time per Telegram bot. Notes sync keeps notes in step across computers.

**Where is the code?** [github.com/avtarfr/kurooto](https://github.com/avtarfr/kurooto), Apache-2.0.
