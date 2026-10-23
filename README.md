# Kurooto

A personal assistant that runs on your own computer. You talk to it on Telegram, and it can ring your phone. It
reminds you of things, keeps track of deadlines and your calendar, asks how your day went, searches your notes, and
wakes you up in the morning. You choose the AI behind it, and every feature is off until you turn it on.

## Showcase

<p align="center">
  <img src="docs/media/systems-loop.webp" width="720" alt="The dashboard's Systems view: each feature that's on is a cell around a beating core labelled KUROOTO, with a heartbeat trace behind it; pulses run along the lines between the core and the cells as messages, reminders and AI answers come and go. Recent events, the AI's latest answers, today and what's due sit in the corners.">
</p>

![The dashboard on a full screen: this computer on the left (processor, memory, graphics card, network, disks, processes, study today, projects), Kurooto's features as cells around a beating core in the middle, the notes and their links on the right, and a terminal below where Sam asks what's due this week and gets an AI answer.](docs/media/dashboard.webp)

<table>
  <tr>
    <td width="50%"><img src="docs/media/dashboard-system.webp" alt="The same dashboard in this computer's colours: blues taken from the desktop's wallpaper colours instead of Kurooto's own greens."></td>
    <td width="50%"><img src="docs/media/top.webp" alt="kurooto top in a terminal: the processor, memory, graphics card, network, disks and processes on the left; on the right Kurooto running, today, what's due, AI requests, what's next, study today, projects and recent events."></td>
  </tr>
</table>

<p align="center">
  <img src="docs/media/chat-example-1.webp" width="32%" alt="Example chat: Sam asks for a reminder in two minutes and what's due this week, then logs an hour of study; the reminder arrives with +10 min and +1 h buttons.">
  &nbsp;
  <img src="docs/media/chat-example-2.webp" width="32%" alt="Example chat: an AI answer about the Gibbs phenomenon, then the evening check-in with In 30 min and Skip today buttons, Sam's reply, and the note that it went into the journal.">
</p>

<table>
  <tr>
    <td width="50%"><picture><source media="(prefers-color-scheme: light)" srcset="docs/media/setup-computer-light.webp"><img src="docs/media/setup-computer.webp" alt="The setup page's Your computer step, with the steps listed down the left: the graphics card, memory and free space it found, the local models it recommends, what to do on battery, and the colours to use."></picture></td>
    <td width="50%"><picture><source media="(prefers-color-scheme: light)" srcset="docs/media/morning-light.webp"><img src="docs/media/morning.webp" alt="The morning page: today's plan from the daily note, next to the day's classes, calendar, what's due soon and check-ins."></picture></td>
  </tr>
</table>

More: [setup: welcome](docs/media/setup-welcome.webp) · [setup: AI](docs/media/setup-ai.webp) ·
[setup: about you](docs/media/setup-about-you.webp) · [setup: features](docs/media/setup-features.webp) ·
[setup on a phone](docs/media/setup-phone.webp) · [the dashboard's terminal](docs/media/dashboard-terminal.webp) ·
[features tab](docs/media/dashboard-features.webp) · [research sources](docs/media/dashboard-research.webp) ·
[phone: call](docs/media/phone-call.webp) · [phone: inbox](docs/media/phone-inbox.webp) ·
[phone: pairing](docs/media/phone-pair.webp) · [the Systems view as video](docs/media/systems-loop.mp4). All of it is a demo with made-up data: Sam, a student taking
Linear Algebra, Organic Chemistry and Signals & Systems.

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
2. Pick an AI: **Antigravity (agy) ★**, Google's agent program, is free with a Google account: Install, sign in,
   Test. (A Gemini API key works too; calls and voice notes use one.)
3. Pick features: **★ Starter** is a good start.
4. Make your Telegram bot with @BotFather (the wizard walks you through it) and tap Start.
5. Send `/help` to your bot. Try "remind me in 2 minutes to stretch".

## What it can do
| | |
|---|---|
| **Talk** | Telegram or the phone app's own chat (Telegram is optional), plain English or commands; voice messages too; it asks you questions and waits for your OK before anything outward; a persona card you write sets how it talks |
| **Remember** | reminders, check-ins into a journal, deadlines (also from Google Classroom and your calendar), recurring quizzes, how you like to be helped; an encrypted memory you can search and forget (`/memory`), and the threads you're in the middle of (`/threads`) |
| **Phone** | call it like a phone call, and it calls you (reminders, check-in debriefs, deadline nudges, quizzes, a wake-up alarm that rings on silent), even with your computer off; Android app from Android 6, iPhone as a Home Screen app |
| **Notes** | search your notes by meaning, skills like `/journal` and `/study-log`, revision packs as PDF, quick notes, files and handwritten pages into notes, sync to your private GitHub repository; books and class materials read into a concept graph of your notes |
| **Study** | subjects, timetable and term dates, a spaced-repetition quiz with an exam mode, an exam-season card, after-class notes, a study-time tracker, a study mode for the dashboard |
| **Google** | Classroom materials into your notes, a mail digest that reads only what you choose, reply drafts you send with a tap, its own calendar for planned time |
| **Research** | a digest of new papers in your fields (arXiv, bioRxiv, medRxiv, PubMed, any journal's feed), project notes from your code, experiment run logs, a message when a long job ends; minutes and action items for any recurring meeting |
| **Your setup** | daily backups to a folder you pick; your setup encrypted in your private repository, so a new computer is ready in a minute |
| **See it all** | a local dashboard (a calm new look, or the classic one a click away; terminals if you like), a status board in any terminal, and a look back each night that suggests small improvements |

**AI, your choice:** Antigravity (agy) ★ (recommended) or Claude Code (both get the same reach: your notes, your
tools, harmless commands, nothing else), a Gemini API key, local models through Ollama on computers that can run
them, or any OpenAI-compatible service.

**Updates:** automatic at night, signed, and rolled back if a new version misbehaves.

**Privacy:** it runs on your computer; nothing is ever sent to Kurooto's author. What each feature sends where is in
[docs/PRIVACY.md](docs/PRIVACY.md).

## Docs
- [docs/MANUAL.md](docs/MANUAL.md): everything, from install to uninstall, every feature, troubleshooting.
- [docs/SETTINGS_GUIDE.md](docs/SETTINGS_GUIDE.md): every setting with its default and what it does, and what an AI is allowed to do.
- [docs/PRIVACY.md](docs/PRIVACY.md): what leaves your computer, per feature.
- [AGENTS.md](AGENTS.md): for your own AI agent, if you ask one to help you set it up or fix it.
- [docs/REQUESTED.md](docs/REQUESTED.md): what people asked for, open and done.
- [docs/ROADMAP.md](docs/ROADMAP.md): ideas that aren't built yet.
- [CHANGELOG.md](CHANGELOG.md) · [docs/RELEASING.md](docs/RELEASING.md) (for the maintainer)

## License
Apache-2.0, © Sumangalam Avtar Sharma. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
