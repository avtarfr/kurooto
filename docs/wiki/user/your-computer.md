# Your computer

Kurooto runs on your own computer, so what it can do depends on whether that computer is on, awake, online and
plugged in. This page says what happens in each case, how to pause or turn Kurooto off, how to keep it reachable, what
your hardware allows, where its files are, and how to check that it's healthy.

- [On, paused, off: the four states](#on-paused-off-the-four-states)
- [On battery](#on-battery)
- [Pausing by hand](#pausing-by-hand)
- [Turning it off, stopping and starting](#turning-it-off-stopping-and-starting)
- [When the computer sleeps or is off](#when-the-computer-sleeps-or-is-off)
- [Stay awake on charger](#stay-awake-on-charger)
- [Starting at boot](#starting-at-boot)
- [Hardware profiles](#hardware-profiles)
- [Local AI models](#local-ai-models)
- [The offline helper](#the-offline-helper)
- [Where things are](#where-things-are)
- [The reserve](#the-reserve)
- [Checking that it works (diagnostics)](#checking-that-it-works-diagnostics)
- [Lost phone or keys that got out](#lost-phone-or-keys-that-got-out)

---

## On, paused, off: the four states

| State | How you get there | Telegram | Reminders and scheduled work | Calls from your call line |
|---|---|---|---|---|
| **Running** (plugged in) | normal | answers | run on time | ring |
| **Battery saver** | on battery, `power.on_battery` = `saver` | answers | light work runs; heavy work waits for the charger | ring |
| **Paused** | `/pause`, `kurooto pause`, Pause on the dashboard, or on battery with `power.on_battery` = `pause` | says it's paused and keeps what you send | wait until you resume | still ring (the alarm too) |
| **Off** | `kurooto off`, or Turn off on the dashboard | doesn't answer; Telegram keeps your messages up to a day | nothing runs | stop, unless you used `--keep-calls` |

Kurooto checks every 30 seconds whether the computer is plugged in or a pause has ended, and switches by itself.

---

## On battery

**What it does.** By default Kurooto saves your battery: everything that leans on the laptop waits for the charger,
and **Telegram keeps working**.

| Keeps working on battery | Waits until it's plugged in |
|---|---|
| Telegram: messages, commands, plain-English requests | Local AI models (unloaded, freeing the graphics card) |
| Reminders, check-ins, deadlines, the calendar | The notes brain's indexing and upkeep, Notes sync, Backups |
| Answers to what you ask the AI | Handwritten notes, Books reading, the concept graph, Research, Classroom → notes, the nightly look back |
| Phone calls and the morning alarm; Profile sync (it's small) | AI work nobody asked for (the mail and Classroom digests, the papers digest's picks) |

Nothing is skipped: waiting work runs the moment you plug in. Your own requests never wait.

**Settings that matter** (Dashboard → Settings → power, or the setup page's "Your computer" step):

| Setting | Default | What it does |
|---|---|---|
| `power.on_battery` | `saver` | `saver`: as above. `normal`: everything keeps running, as if plugged in. `pause`: everything pauses until you plug in |

**Edge cases.**

- A desktop computer (no battery) is always "plugged in".
- Some commands still run on battery when you ask for them directly: `/backup`, and `/books read force`.
- `/resume` while on battery says "Back on; this laptop is on battery, so heavy work still waits for the charger."

---

## Pausing by hand

**What it does.** Nothing runs while paused, but Telegram still answers: it replies "I'm paused until ...; I'll do
this when I'm back. /resume wakes me now", keeps what you send, and handles all of it, in order, when you resume.
Reminders due meanwhile arrive when it resumes. Your call line keeps placing scheduled calls, so the morning alarm
still rings.

| Where | How |
|---|---|
| Telegram | `/pause` (until you resume), `/pause 2h`, `/pause until 18:00`; `/resume` to wake it |
| Terminal | `kurooto pause`, `kurooto pause 2h`, `kurooto pause 18:00`; `kurooto resume` |
| Dashboard | **Pause 1 h** in the header |

While paused, only `/resume`, `/pause`, `/status`, `/help` and `/start` are answered at once; everything else waits.

---

## Turning it off, stopping and starting

| Command | What it does |
|---|---|
| `kurooto off` (or **Turn off** on the dashboard) | stops Kurooto completely (and the local models it started) and keeps it from starting when you sign in. Your call line stops placing scheduled calls |
| `kurooto off --keep-calls` | the same, but your call line keeps placing scheduled calls (for example, the alarm) |
| `kurooto on` (or open **Kurooto** from your app menu) | turns it back on: start-at-sign-in again, starts it now, opens the dashboard |
| `kurooto stop` | stops it just for now; it starts again at your next sign-in |
| `kurooto start` | starts it in the background now |
| `kurooto open` | opens the setup page or dashboard in your browser |
| `kurooto run` | runs it in this terminal window (for troubleshooting) |
| `kurooto supervise` | runs it and restarts it if it crashes |

**Edge cases.**

- Telegram keeps messages for about a day. Messages sent while Kurooto is off are handled when it's back, if it's back
  within that day.
- `kurooto off` while Kurooto isn't running can't tell your call line to stop; it says so.
- A clean stop sends "Kurooto is going offline" on Telegram; coming back sends "back online". See
  [Messages it sends](messages-it-sends.md) for the full rules (`notify.presence.*`).

---

## When the computer sleeps or is off

- **Telegram** messages wait until it's back.
- **Reminders** due while it slept arrive when it wakes, marked late. With
  [Reminders with the lid shut](calls.md) on, your Android phone gets them at their time instead.
- **Calls and the morning alarm** still ring: your call line places them from your Cloudflare account. Anything that
  needs the computer waits.
- **Questions** can still be answered in the phone app; the answer waits on your call line.
- **Scheduled work** that came due runs when it's back. A routine missed while off runs once, if that's still one of
  its days.
- **"Back online"** comes when it starts, wakes or the network returns, with what it caught up on. Without Phone calls,
  there's no "going offline" message for sleep, a crash or a lost network.

To keep it reachable all day, leave it on and plugged in, with [Stay awake on charger](#stay-awake-on-charger) on. To
have the morning plan drafted overnight, turn on `alarm.keep_awake` (see [Calls: Morning alarm](calls.md)).

---

## Stay awake on charger

**What it does.** While your computer is plugged in, it doesn't go to sleep by itself, so Kurooto keeps answering. On
battery it sleeps as usual. The screen can still turn off.

**Turn it on.** Dashboard → Features → Stay awake on charger.

**Closing the lid:**

| System | What happens with the lid closed |
|---|---|
| Linux | turn on `awake.lid` and it keeps running with the lid closed while plugged in. If your system doesn't let a background program hold the lid switch, it holds the rest and `kurooto doctor` says so |
| Windows | follows Power Options: Control Panel → Power Options → "Choose what closing the lid does" → "Do nothing" when plugged in. An app can't change this without admin rights |
| macOS | a closed lid sleeps a Mac unless an external display is attached |

**Settings that matter:**

| Setting | Default | What it does |
|---|---|---|
| `awake.lid` | `false` | Linux: keep running with the lid closed while plugged in |

**Edge cases.** The hold ends when Kurooto stops, even if it crashes. On Linux, if the lid still sleeps the laptop,
allow the lid hold in polkit (`org.freedesktop.login1.inhibit-handle-lid-switch`) or set
`HandleLidSwitchExternalPower=ignore` in logind.conf.

**What leaves your computer.** Nothing.

**Turn it off.** `awake.lid` off, or turn the feature off; the computer sleeps as usual at once.

---

## Starting at boot

By default Kurooto starts when you sign in (Windows: a Run entry, no window; macOS: a LaunchAgent; Linux: a systemd
user service, or an autostart entry without systemd). It restarts by itself if it crashes.

**On Linux with systemd it can start when the computer does**, before anyone logs in, so Telegram and calls work after a
power cut or a remote reboot:

| Command | What it does |
|---|---|
| `kurooto autostart boot` (or Dashboard → Settings → Starting) | turns on lingering for your account (`loginctl enable-linger`; it may ask for your password, or tell you to run that yourself). Because your keychain stays locked until you log in, Kurooto's keys move to its owner-only settings file (`secrets.json`, readable only by your account) |
| `kurooto autostart login` | back to starting at sign-in: lingering is turned off again only if Kurooto turned it on, and the keys go back to the keychain |
| `kurooto autostart status` | says `on` or `off` |
| `kurooto autostart on` / `off` | turns start-at-sign-in on or off |

The setting is `autostart.when` (`login` or `boot`).

**Edge cases.**

- Windows and macOS start at sign-in only: starting before would need admin rights. On a Mac that restarts by itself,
  automatic login brings Kurooto back.
- If your home folder is encrypted and only unlocked at login, starting at boot can't reach Kurooto's files.
- "Linux didn't allow that from here": run `loginctl enable-linger` in a terminal, then `kurooto autostart boot` again.

**Undo.** `kurooto autostart login` (or `kurooto uninstall`, which also turns off lingering Kurooto turned on).

---

## Hardware profiles

The setup page reads your computer (processor, memory, graphics card, free space, battery) and recommends a setup,
marked ★. The main answers always come from the AI you picked; local models only take quick decisions, make the notes
index and, on bigger cards, read handwriting.

| Profile | Example | Local models | Notes brain index |
|---|---|---|---|
| **light** | no usable graphics card, or under 8 GB of memory, or an Intel Mac | none | Gemini (your key) or keywords |
| **apple-8** | Apple Silicon, 8 GB | embeddings only (0.27 GB) | on your Mac |
| **apple** | Apple Silicon, 16 GB or more | a small helper model (2.5 GB) + embeddings | on your Mac |
| **small-gpu** | an NVIDIA card with 4 to 8 GB | a small helper model (2.5 GB) + embeddings | on your computer |
| **big-gpu** | an NVIDIA card with 8 GB or more | a larger helper model (6.6 GB, also reads handwriting) + embeddings | on your computer |
| **big-gpu-12** | an NVIDIA card with 12 GB or more | the above + a vision model (8 GB) for handwriting and images | on your computer |

Only NVIDIA cards and Apple Silicon count for local models; other graphics cards get the light profile.

**Going past what's recommended.** You know your computer better than the detection:

| Command | What it does |
|---|---|
| `kurooto hardware` | what it detected, what it recommends, and any warnings |
| `kurooto hardware --profile big-gpu-12` | use another setup's models (`auto` goes back; also `light`, `apple-8`, `apple`, `small-gpu`, `big-gpu`) |
| `kurooto hardware --add gemma4:12b` | add an Ollama model of your own (repeatable; its size is looked up in Ollama's registry); `--remove MODEL` takes one off |
| `kurooto hardware --add-prereq tesseract` | add another program for Kurooto to install; `--remove-prereq ID` takes it off |
| `kurooto hardware --install` | install Ollama, every model on the list and those programs now, after checking there's room |

The setup page's computer step has the same choices and an install button. Kurooto never refuses: if a model is bigger
than your graphics memory, it says part of it will run on the processor, slowly, and goes ahead.

| Setting | Default | What it does |
|---|---|---|
| `hardware.force_profile` | empty (detected) | another profile's models (Settings → This computer, `kurooto hardware` or the setup page) |
| `hardware.extra_models` | `[]` | Ollama models of your own, e.g. `["gemma4:12b"]` |
| `hardware.extra_prereqs` | `[]` | other programs to install, by id (e.g. `tesseract`, `poppler`, `tectonic`, `git`) |

Dashboard → Settings → **Your computer** shows what was found and lets you change it; `kurooto doctor` checks again.

---

## Local AI models

**What it does.** Small AI models on your computer, through [Ollama](https://ollama.com), picked for its hardware:
they decide quickly how hard a request is, make the notes brain's index, read handwriting on bigger cards, and can
summarise confidential mail on this computer. Private and offline. The main answers still come from the AI you picked
(see [AI models](ai-brains.md)).

**Turn it on.** Dashboard → Features → Local AI models. It installs Ollama and the models for your profile. Not offered
on computers without a usable graphics card or Apple Silicon.

**From Telegram:** `/models` says whether Ollama is running and lists the models with a tick or cross for each, its
size and what it's for.

**Limits and edge cases.**

- On battery (saver mode) or when paused, the models are unloaded and an Ollama Kurooto started is stopped, freeing
  the graphics card; they come back when you plug in.
- One graphics card runs one big model at a time, so handwriting waits while the card is busy.
- A small model may not support the AI's tools; it then answers without them.

**What leaves your computer.** Nothing; the models run here.

**Turn it off.** Features → Local AI models → Turn off. Kurooto then asks whether to remove what it installed for
it (Ollama, the models), with their size: **Remove** / **Keep**, in Today → Waiting for you or your chat. Nothing goes
without that tap, and only what Kurooto installed (see [What Kurooto installed](#what-kurooto-installed)).

[Voice notes](talking-to-kurooto.md) don't use local models: they use your Gemini key.

---

## The offline helper

**What it does.** On a laptop without a graphics card, a small model on the processor (about 1 GB, through Ollama)
takes the quick decisions: how hard a request is, which instant request a short message means when no pattern is
sure, and whether a short reply to "Still true?" means yes or no. Your AI still writes the answers. With the internet
down, it also answers quick questions itself.

**When the internet is down** (this works with or without the helper):

- A quick question to Chat is answered by the helper, with a line saying the offline helper answered.
- Everything else waits: "No internet connection right now: it waits and runs as soon as it's back." When the
  connection comes back, one line says what's running now, and each answer says it waited.
- A request that waited 24 hours (`local_helper.hold_h`) ends with a message saying so. Nothing is dropped silently.
- Plain-English requests (reminders, deadlines, "what's due") work as always: they never needed the internet.
- An AI on this computer (Ollama as your main AI) keeps answering as usual.

Kurooto knows the internet is down from its own traffic: Telegram and your call line not answering, or its requests
to two or more places failing. It doesn't ping anything else to find out. When only Telegram stops answering and
other services still do, that's Telegram, not the internet: a request waits a couple of minutes at most, then runs.

**Turn it on.** `/helper on`, or **Install** when it's offered. It installs Ollama if needed, checks there's room,
downloads the model, then times a few one-word answers: if the middle one takes more than 1.5 seconds
(`local_helper.max_s`), it's too slow to help here, stays off and its model is removed again. `/helper` shows how it's
doing, `/helper test` times it again.

**When it's offered.** Once, two weeks after Kurooto started on this computer, if your free AI limit ran short on 3 of
the last 14 days or the internet dropped 3 times in that time, and only on a computer without a graphics card for
local models: one message with **Install** and **Not now**. Not now asks once more a month later at most;
`local_helper.offer` off stops it.

**Settings** (`local_helper.*`): `on`, `model` (empty: the table's choice, `qwen2.5:1.5b-instruct`), `max_s` (1.5),
`timeout_s` (4: a decision that takes longer is left to the rules), `offline` (on: the waiting described above; off:
requests fail as before when the internet is down), `hold_h` (24), `offer` (on).

**What leaves your computer.** Only the one download, which Ollama makes from its own registry. The helper's decisions
and answers stay here.

**Turn it off.** `/helper off`. If Kurooto downloaded its model and nothing else uses it, you're asked whether to
remove it (Remove / Keep); kept, `/helper on` uses it again.

---

## What Kurooto installed

Kurooto keeps a receipt of what it installs on this computer: programs (Ollama, Node.js, Bun and GBrain, kitty and
fish, Tectonic, Tesseract, ...), with the files and folders each install made, and the Ollama models it downloads.
Voice's speech packages and models live in Kurooto's own folder and are listed with them.

**Never what was there before.** A program that's already on the computer isn't installed again, so it never gets on
the receipt; nor does a model Ollama already had. Of the folders an install touches, only what wasn't there before is
written down, so `~/.local/bin` itself or your own programs in it are never touched. A folder Kurooto's install made
that now holds things of yours stays: Ollama's model store with models you pulled yourself, Bun's folder with your
own global packages. The receipt is this computer's only: it isn't in backups or your profile, so a restore on a new
computer never removes anything there.

**See it:** `kurooto installed` in a terminal, or `/installed` in your chat: each one with its size, the features it's
for, and what uses it now. It also names programs that are here but weren't installed by Kurooto (never removed by it).

**Remove one:** `kurooto remove <name>` (`ollama`, `gemma4:e4b`, `voice`, ...) says what goes and asks first
(`--yes` doesn't). Ollama's models go with Ollama, GBrain with Bun. Something a feature that's on still uses can't be
removed until it's off. In the chat, **Remove…** under `/installed` asks Remove / Keep.

**Turning a feature off** (or `/helper off`) asks whether to remove what Kurooto installed for it that nothing else
uses, with the size: **Remove** / **Keep**, in Today → Waiting for you on the dashboard, Telegram or the phone app.
Changing This computer's setup (Settings → `hardware.force_profile`, `hardware.extra_models`, `kurooto hardware
--profile`) asks the same about Local AI models' models the new setup doesn't use. Nothing is removed without that tap, and never by
the AI or a schedule. `uninstall.offer` off: no questions (the commands still work).

**Uninstalling Kurooto** follows the receipt: `kurooto uninstall` lists what Kurooto installed outside its own folder
and asks once before removing it too (`--yes` doesn't ask, `--keep-programs` leaves it all, and so does
`uninstall.with_programs` off).

---

## Where things are

`kurooto paths` prints them. By default:

| | Windows | macOS | Linux |
|---|---|---|---|
| Settings | `%LOCALAPPDATA%\Kurooto\config` | `~/Library/Application Support/Kurooto/config` | `~/.config/kurooto` |
| Data | `%LOCALAPPDATA%\Kurooto\data` | `~/Library/Application Support/Kurooto/data` | `~/.local/share/kurooto/data` |
| State | `%LOCALAPPDATA%\Kurooto\state` | `~/Library/Application Support/Kurooto/state` | `~/.local/state/kurooto` |
| Logs | `%LOCALAPPDATA%\Kurooto\state\logs` | `~/Library/Logs/Kurooto` | `~/.local/state/kurooto/logs` |
| Cache (safe to delete) | `%LOCALAPPDATA%\Kurooto\cache` | `~/Library/Caches/Kurooto` | `~/.cache/kurooto` |
| The program | `%LOCALAPPDATA%\Programs\Kurooto` | `~/Library/Application Support/Kurooto/app` | `~/.local/share/kurooto/app` |
| Your notes | `Documents\Kurooto` | `~/Documents/Kurooto` | `~/Documents/Kurooto` (or `~/Kurooto`) |

Your notes folder can be anywhere (`you.workspace`; see [Notes and the concept graph](notes-and-concept-graph.md)).

**Secrets** (bot token, API keys, sign-ins) are in your system's keychain: Windows Credential Manager, macOS Keychain,
or the Secret Service on Linux. Where there is none (or when starting at boot on Linux), they're in `secrets.json` in
the settings folder, readable only by your user account.

The dashboard runs at `http://127.0.0.1:8770`. If another program uses that port, Kurooto picks the next one;
`web.json` in the state folder says which.

---

## The reserve

Kurooto keeps plain Markdown copies of its own state in the state folder, under `reserve/`, so an AI program can just
open a file instead of running a command it may not be allowed to run:

| File | What it holds |
|---|---|
| `alarm.md` | the next alarm and the daily one |
| `deadlines.md` | what's due, nearest first |
| `calendar.md` | the next two weeks of events |
| `today.md` | (0.9.0, `reserve.today`) today at a glance: the next alarm, today's classes (skipped ones marked), what's due today and tomorrow, today's events; never a line about health or money, your mood or the senses |
| `settings.md` | every setting that differs from its default, and which features are on (never a secret) |
| `addons.md` | your add-ons and whether each loaded |
| `agent-guide.md` | what an AI program may read, write and run here, its tools, and the chat commands |

They're rewritten every 10 minutes and when an alarm changes, only when their text changed. `kurooto reserve` writes
them now. AI programs may read this folder, never write to it, and Kurooto never reads it back.

---

## Checking that it works (diagnostics)

| Command | What it does |
|---|---|
| `kurooto doctor` | checks Kurooto, your AI, every feature you have on and free space; each line says what's wrong. It also asks Telegram whether your bot answers, asks your call line whether it's up, checks the skills copied into agy and runs your add-ons' own checks. The exit code is the number of problems (lines marked `--` are notes, not problems; a setup step you skipped is one, with the command that opens it: `kurooto setup about`) |
| `kurooto doctor --fix <id>` | runs the fix a problem offers, inside the running Kurooto (needs it running) |
| `kurooto doctor --json` | the same checks as JSON, for programs |
| `kurooto doctor --bundle` | saves a zip to send someone helping you: the checks, the log, your settings, recent events and how long each setup step took (finished or skipped; never what you typed), with secrets, names, email and web addresses and your folders blanked out. Never your messages, notes, journal, transcripts or what you asked the AI. Nothing is sent: look inside, then send it yourself. If Kurooto itself can't start, there's no zip and it says so: send the checks it prints instead |
| `kurooto top` | a live status board in any terminal: this computer (processor, memory, graphics card, network, disks, battery, processes) beside Kurooto (running or not, battery mode, the call line, today, what's due, AI requests, recent events). `q` quits, `r` refreshes, `c` and `m` sort processes by cpu or memory; `--once` prints one screen; `NO_COLOR=1` turns colours off |
| `kurooto logs` | the end of Kurooto's log (`-n 200` for more lines); `kurooto logs -f` keeps following it (Ctrl+C stops) |
| `kurooto selftest` | checks that this version starts |
| `kurooto --version` | the version you run |

On Telegram, `/status` says what's going on and `/health` what isn't working, with Fix buttons (`/health now` checks
online too). Kurooto also runs its own daily health pass and fixes what it safely can; see
[Messages it sends](messages-it-sends.md).

---

## Lost phone or keys that got out

`kurooto rotate` gives your call line new keys after a lost phone or a backup zip with keys that got out. Every phone
then has to pair again. See [Phone app](phone-app.md).

## Local models stay on the graphics card

A model that runs partly on the processor is several times slower and heats the laptop. Every 10 minutes Kurooto looks
at what Ollama has loaded: if models together don't fit your graphics card, it unloads them, so the next request loads
its one model fully on the card; if one model doesn't fit even alone, you're told once, with what to do (a smaller
model in Features → Local AI models). `/models` shows each loaded model and how much of it is on the card.
