# Helping someone with Kurooto (a guide for AI agents)

You're an AI agent (Antigravity, Codex, Claude Code, or any other) helping a person install, set up, use or fix
Kurooto on their own computer. Kurooto is a personal assistant: a background program plus a local web page, talking
to its owner on Telegram and, optionally, by phone. The person may know very little about computers: explain in plain
words, one step at a time, and let them do the clicking in their browser.

## A prompt the person can paste to you

> Help me install and set up Kurooto (github.com/avtarfr/kurooto) on this computer. Read its AGENTS.md first and
> follow it. Ask me before anything that installs, deletes or signs in, and never ask me to paste passwords or keys
> into this chat.

## Ground rules

- **Never ask the person to paste secrets into the chat:** Telegram bot tokens, API keys, GitHub tokens, Google client
  files, call links, pairing codes. Those go only into Kurooto's own setup page (`http://127.0.0.1:8770`), which keeps
  them in the system keychain. If they paste one anyway, tell them to revoke it and make a new one.
- **Don't edit Kurooto's files by hand** (settings, databases, the installed program). Use the setup page, the
  dashboard's Settings, or the `kurooto` command. Settings changed by hand while it runs can be overwritten.
- **Don't delete anything** in Kurooto's folders or the person's notes folder without asking. `kurooto uninstall`
  removes Kurooto but never the notes folder; say so before running it.
- **Sign-ins are the person's:** Google, Telegram, Cloudflare, GitHub, ChatGPT and Claude sign-ins happen in their
  browser. Don't try to automate them.
- **Ask first** before installing anything, before uninstalling, and before turning on a feature that sends data
  somewhere (see `docs/PRIVACY.md`).

## Commands

| Command | What it does | Safe to run? |
|---|---|---|
| `kurooto --version` | the installed version | yes |
| `kurooto paths` | where settings, data, logs and the program live | yes |
| `kurooto doctor` | checks Kurooto, the AI, every feature that's on, free space; exit code = number of problems | yes |
| `kurooto doctor --json` | the same, as JSON | yes |
| `kurooto doctor --bundle` | saves a diagnostics zip (secrets and personal details blanked out) | yes; ask before sending it anywhere |
| `kurooto open` | opens the setup page or dashboard in the browser | yes |
| `kurooto start` / `kurooto stop` | starts / stops the background program (it starts again at sign-in) | yes |
| `kurooto pause [2h\|18:00]` / `kurooto resume` | pauses it (Telegram answers "paused" and keeps what's sent) / wakes it | yes |
| `kurooto notify [--title T] TEXT` | sends the person a message through Kurooto (exit 2: not running, shown on the desktop only) | yes, when they asked to be told |
| `kurooto off` / `kurooto on` | off completely (no start at sign-in, call line silent) / back on | ask first |
| `kurooto autostart status` | whether it starts at sign-in | yes |
| `kurooto autostart on` / `off` | turns start-at-sign-in on or off | ask first |
| `kurooto update` / `kurooto update --now` | checks for / installs an update now | ask first |
| `kurooto uninstall [--keep-data]` | removes Kurooto | **ask first**; explain what goes |

Install (only if it isn't installed; ask first):
- Windows PowerShell: `irm https://avtarfr.github.io/kurooto/install.ps1 | iex`
- macOS / Linux: `curl -LsSf https://avtarfr.github.io/kurooto/install.sh | sh`

Running the installer again repairs an installation.

## Where to look

- **Settings:** `settings.json` in the settings folder (`kurooto paths`). Read it to understand the setup; change
  settings through the dashboard (Settings tab).
- **Log:** `kurooto.log` in the logs folder. The newest lines are at the end.
- **What happened:** `events.jsonl` in the state folder (one JSON object per line: `ts`, `kind`, details).
- **The person's notes:** the notes folder (`you.workspace` in settings; default `Documents/Kurooto`). It's theirs:
  read it only if they ask you to.

## Reading `kurooto doctor`

Each line is `ok`, `--` (a note, not a problem) or `FAIL`, then what it checked and the detail.

| Line | Meaning | Fix |
|---|---|---|
| `running  no` | the background program isn't running | `kurooto start`; if it stops again, read the end of `kurooto.log` |
| `AI ... not signed in` / `isn't installed` | the chosen AI can't answer | setup page → AI → Install / sign in → Test |
| `free space FAIL` | under 5 GB free | help them free space; don't delete their files yourself |
| `Telegram FAIL ... token` | the bot token is missing or revoked | setup page → Telegram (a new token from @BotFather if it was revoked) |
| `Phone calls FAIL not connected` | the call line isn't reachable | check the internet connection; it reconnects by itself; else Features → Phone calls → Set up |
| `Notes sync FAIL` | the repository can't be reached or a change clashes | read the detail; clashes are resolved on GitHub, then `/sync` on Telegram |
| `Google FAIL sign in` | Google's sign-in expired | Features → Google → Save; if it happens weekly, the consent screen isn't published |
| a folder `FAIL` | Kurooto can't write its own folder | check disk space and permissions on that folder |

## Common jobs

- **"The bot doesn't answer":** `kurooto doctor`. Turned off (`off.json` in the state folder) → ask, then
  `kurooto on`. Paused → `/resume` on Telegram or `kurooto resume`. Not running → `kurooto start`. The computer asleep → suggest the
  "Stay awake on charger" feature. Chat off → free text needs the Chat feature.
- **"It says I'm at my limit":** free AI tiers have daily limits. Suggest setting a fallback AI in Settings
  (`brain.fallback`), for example a free Gemini key.
- **"My phone doesn't ring":** in the Kurooto Android app, every checklist item should be ✓ (battery unrestricted,
  notifications, full-screen calls). On Samsung/Xiaomi/Oppo/Vivo/OnePlus/Huawei, take it off "sleeping apps". Then
  dashboard → Phone → "Ring my phone". iPhones only get notifications, not rings.
- **Setting up a feature:** dashboard → Features → the feature's card. `docs/MANUAL.md` has every feature's steps.
- **Something you can't fix:** `kurooto doctor --bundle`, then tell the person where the zip is and that they can
  send it to whoever gave them Kurooto. Don't upload it anywhere yourself.

## Facts that help

- The setup page and dashboard are at `http://127.0.0.1:8770` (or the next free port; `web.json` in the state folder
  says which). They need a key that's embedded in the page Kurooto serves; you can't call the API without it, and
  shouldn't try.
- Every feature is a module, off until turned on. The full list with what each needs is in `docs/MANUAL.md`.
- Updates install themselves at night by default, signed and with automatic rollback.
- On battery (`power.on_battery`, default `saver`) heavy work waits for the charger on purpose; Telegram keeps working.
- The notes folder is plain Markdown files; Kurooto never deletes it.
- `about-me/profile.md` in the notes folder is the person's profile, built from what their other AI accounts know
  ("About you" on the setup page). Read it for context. The raw reports are in Kurooto's data folder: personal, so
  don't open or quote them unless the person asks.
