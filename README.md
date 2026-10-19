# Kurooto

A personal assistant that runs on your own computer. You talk to it on Telegram, and it can ring your phone. It
reminds you of things, keeps track of deadlines and your calendar, asks how your day went, searches your notes, and
wakes you up in the morning. You choose the AI behind it, and every feature is off until you turn it on.

> **Status: pre-release.** The install line below works once the first release (v0.1.0) is published.

## Install

**Windows** (PowerShell):
```powershell
irm https://avtarfr.github.io/kurooto/install.ps1 | iex
```
**macOS / Linux** (Terminal):
```sh
curl -LsSf https://avtarfr.github.io/kurooto/install.sh | sh
```

No admin password needed. It installs Kurooto for your user, checks the release's signature, starts it at sign-in and
opens the setup page in your browser. A wizard then reads your computer (graphics card, memory, free space),
recommends settings for it (★), installs whatever the features you pick need, and connects your Telegram bot.

## Your first 15 minutes
1. Paste the line above; the setup page opens.
2. Pick an AI: **Antigravity (agy) ★** is free with a Google account. Install, sign in, Test.
3. Pick features: **★ Starter** is a good start.
4. Make your Telegram bot with @BotFather (the wizard walks you through it) and tap Start.
5. Send `/help` to your bot. Try "remind me in 2 minutes to stretch".

## What it can do
| | |
|---|---|
| **Talk** | Telegram, plain English or commands; voice messages too |
| **Remember** | reminders, check-ins into a journal, deadlines (also from Google Classroom), your calendar |
| **Phone** | call it like a phone call, and it calls you (reminders, check-ins, a wake-up alarm that rings on silent), even with your computer off; Android app from Android 6, iPhone as a Home Screen app |
| **Notes** | search your notes by meaning, files and handwritten pages into notes, sync to your private GitHub repository |
| **Study** | subjects and timetable, a spaced-repetition quiz, after-class notes, a study-time tracker |
| **Research** | a digest of new papers in your fields (arXiv, bioRxiv, medRxiv, PubMed, any journal's feed), project logs from your code |
| **See it all** | a local dashboard of everything happening |

**AI, your choice:** Antigravity (agy), a free Gemini key, ChatGPT/Codex, FreeLLMAPI, Claude Code, or local models
through Ollama on computers that can run them.

**Updates:** automatic at night, signed, and rolled back if a new version misbehaves.

**Privacy:** it runs on your computer; nothing is ever sent to Kurooto's author. What each feature sends where is in
[docs/PRIVACY.md](docs/PRIVACY.md).

## Docs
- [docs/MANUAL.md](docs/MANUAL.md): everything, from install to uninstall, every feature, troubleshooting.
- [docs/PRIVACY.md](docs/PRIVACY.md): what leaves your computer, per feature.
- [AGENTS.md](AGENTS.md): for your own AI agent, if you ask one to help you set it up or fix it.
- [CHANGELOG.md](CHANGELOG.md) · [docs/RELEASING.md](docs/RELEASING.md) (for the maintainer)

## License
Apache-2.0, © Sumangalam Avtar Sharma. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
