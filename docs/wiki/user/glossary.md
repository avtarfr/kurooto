# Glossary

Words this wiki uses, in plain terms. Back to the [wiki's front page](index.md).

| Word | What it means here |
|---|---|
| **About you profile** | A note in your notes folder (`about-me/profile.md`) that Kurooto builds from what your other AI accounts know about you. Its **In brief** part goes along with every AI request. See [Teaching Kurooto](teaching-kurooto.md). |
| **Add-on** | Your own extra features, skills or prompts, loaded from a folder you name. Optional, for people who write code. See [Add-ons and scripts](add-ons.md). Not the same as an optional feature such as Exam season, which is part of Kurooto and simply off until you turn it on. |
| **agy (Antigravity)** | Google's AI agent program that runs on your computer. One of the [AI brains](ai-brains.md) you can pick. |
| **AI brain** | The AI service that answers your messages and does tasks for Kurooto: a Gemini API key, agy, Claude Code, a local Ollama model, or another OpenAI-compatible service. See [AI brains](ai-brains.md). |
| **API key** | A long secret code a service gives you so a program can use it on your behalf. Kurooto keeps keys in your computer's keychain. |
| **Approval** | A message that asks for your OK before Kurooto does something (Approve / Deny, or choices like Send / Edit / Discard). Nothing is ever approved for you. |
| **Bot / Telegram bot** | Your own Telegram account for Kurooto, made with @BotFather. It answers only you. |
| **@BotFather** | Telegram's official bot that makes new bots and gives you their token. |
| **Brief (call brief)** | A short summary your call line keeps (what's due, today's classes, open questions) so calls work even while your computer is off. |
| **Call line** | A small program Kurooto puts on your own free Cloudflare account. Your phone talks to it for calls; it can ring your phone while your computer sleeps. See [Phone calls](calls.md). |
| **Calm** | The rules that keep Kurooto quiet: every message that comes by itself says why, and at most 6 messages and 1 call a day come by themselves. See [Messages Kurooto sends by itself](messages-it-sends.md). |
| **Case / test case** | A plain-English request Kurooto got wrong (or didn't understand), kept so you can teach it what you meant. See [Teaching Kurooto](teaching-kurooto.md). |
| **Chat** | The feature that sends free text to your AI brain. Without it, only commands and instant requests work. |
| **Check-in** | A message (or call) at a time you choose asking how the day is going; your reply goes to your journal. |
| **Class pack** | A small file with a class section's timetable, term dates and recurring quizzes, which classmates import into their own Kurooto. |
| **Claude Code** | Anthropic's AI agent program. One of the [AI brains](ai-brains.md); needs a paid Claude plan. |
| **Cloudflare** | A company whose free plan hosts your call line. You make the account; it's yours. |
| **Concept graph** | The feature that reads a finished book and weaves its ideas into your notes as linked concept notes. See [Notes and the concept graph](notes-and-concept-graph.md). |
| **Daily note** | One note per day in your notes folder (`journal/<date>.md` by default) that holds your journal, the day's plan, check-in answers and study hours. |
| **Dashboard** | Kurooto's page in your browser at `http://127.0.0.1:8770`, only reachable from your own computer. See [Dashboard](dashboard.md). |
| **Deadline list** | Everything that's due, gathered from what you add, your notes, Google Classroom, your calendar, recurring quizzes and your term note. |
| **Evening bundle** | One message at 20:00 listing what waited because the day's limit was reached (or because you chose "Another time"). |
| **Exam mode** | Turns on by itself for a subject two weeks before its quiz or exam: more practice, calls know about it. |
| **Exam season** | An optional feature (off, in no preset) for the whole exam period: alarm checks, exam-eve questions, an alarm to leave, debriefs. See [Quiz and exams](quiz-and-exams.md). |
| **Fallback brain** | A second AI that answers when your main one hits its limit (`brain.fallback`; or a list of them; with none picked, Claude Code and agy stand in for each other at a limit). |
| **Feature** | One part of Kurooto you can turn on or off on the dashboard's Features page. Everything is off until you turn it on. |
| **Fine-grained token** | A GitHub access key limited to one repository; Notes sync and Profile sync use one. |
| **Focus** | Do-not-disturb: calls are held and messages that can wait are kept until it ends (`/focus 2h`). |
| **GBrain / notes brain** | The search index of your notes that lets `/notes` find things by meaning and gives your AI a memory of them. |
| **Gemini / Gemini Live** | Google's AI. A Gemini API key is one of the brains, and phone calls, voice notes and the alarm always use it; Gemini Live is its real-time voice, used for calls. |
| **Hold** | No calls until a time (`/hold 2h`); messages still come. |
| **Instant request** | A plain-English message Kurooto understands by itself, without asking an AI ("remind me at 9 to call mum"). See [Commands](commands.md#plain-english-requests-understood-instantly). |
| **Intent** | The developer word for an instant request. |
| **Journal** | Your own words about the day, kept in the daily note. |
| **Keychain** | Your system's password store (Windows Credential Manager, macOS Keychain, Linux Secret Service) where Kurooto keeps tokens and keys. |
| **Lessons (call lessons)** | What Kurooto learned from looking back at a call; every later call is told them. `/lessons` lists them. See [Phone calls](calls.md). |
| **Local models / Ollama** | AI models that run on your own computer (through the Ollama program). Private and offline, but weaker; mostly used for quick decisions. Need a graphics card or Apple Silicon. |
| **Look back (nightly)** | Once a day the AI reads how the day went and suggests up to three small improvements, which you approve or not. |
| **MCP** | Model Context Protocol, a standard way for AI agent programs to use another program's tools. `kurooto mcp` gives agent programs Kurooto's tools. |
| **Night (night hours)** | 23:30 to 07:00 by default (`availability.night`); no calls then, and messages that can wait wait. With the alarm set, the night runs from your bedtime to the alarm. |
| **Notes folder (workspace)** | The folder of Markdown notes Kurooto reads and writes, `Documents/Kurooto` by default. Works with Obsidian. |
| **OAuth client** | Your own registration with Google (a small JSON file) that lets Kurooto sign in to your Google account without anyone else's server. See [Google](google.md). |
| **Pairing** | Connecting your Telegram chat or your phone to Kurooto with a one-time link or QR code. |
| **Pause** | Kurooto stops working for a while but Telegram still answers, keeps what you send, and does it all when you `/resume`. |
| **Preset** | A ready set of features in the setup wizard: Starter (Telegram, Chat, Reminders, Check-ins, Deadlines) or Everything. |
| **Profile sync** | Your Kurooto setup, encrypted with your passphrase, kept in your private GitHub repository so a new computer is set up in a minute. |
| **Quiet hours** | Times when Kurooto doesn't call or send messages that can wait: the night, focus, `/hold`, classes and calendar events (for calls). |
| **Repository (repo)** | A folder kept with its full history on GitHub. Notes sync uses a private one. |
| **Reserve, the** | Plain Markdown copies of Kurooto's state (alarm, deadlines, calendar, settings) that AI programs can read. Also: the end of the AI's free daily limit kept back for what you're waiting on. |
| **Routine** | A command or request that runs on a schedule (`/every monday 9:00 /journal plan my week`). |
| **self.md** | What Kurooto is running (version, AIs and models, features and their health, recent failures), kept for its AI to read before answering a question about Kurooto itself. |
| **Setting** | A named option such as `deadlines.ping_h`, changed on the dashboard's Settings page. The part before the dot is the section. |
| **Skill** | Ready-made instructions for your AI, run as a command (`/journal`, `/study-log`, `/pack`). See [Skills and routines](skills-and-routines.md). |
| **Start-by date** | The day Kurooto estimates you should start working on a deadline, from its size and your free time. |
| **State folder** | Kurooto's own working files (schedule, history, logs). `kurooto paths` shows where it is. |
| **Study pack** | A zip of a subject's notes and course files, with a prompt, for you to give to another AI (`/studypack`). |
| **Term note** | A note with your weekly timetable and key dates that Kurooto reads live (`/term note`). |
| **Tesseract** | A free program that reads text from scanned pages (OCR). Kurooto can install it for books. |
| **Tectonic** | A small LaTeX engine Kurooto can install to turn revision packs into PDFs. |
| **Token** | A secret code that lets a program use an account (your Telegram bot's token, a GitHub token). |
| **Turn by turn** | A way of calling where your phone's own speech recognition listens and you take turns, used when Google's live voice is down or when you choose it. |
| **Webhook** | A setting that sends a bot's messages to a web address. Kurooto can't read a bot that has one; the setup page offers to remove it. |
| **Zettelkasten layout** | An alternative way of arranging your notes folder (`dailies/`, `zettel/`, `sources/`, `maps/`). See [Notes](notes-and-concept-graph.md). |
