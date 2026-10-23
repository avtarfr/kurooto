# Privacy: what stays and what leaves

Kurooto runs on your own computer. **Nothing is ever sent to Kurooto's author**: no analytics, no crash reports, no
"phone home". Everything that leaves your computer goes to a service you chose, under your own account, and only for a
feature you turned on. Every feature is off until you turn it on, and each one says on its card in Dashboard →
Features what it sends where.

This page is the full list. Each feature's own page repeats its part under **What leaves your computer**.

- [The principles](#the-principles)
- [What leaves, feature by feature](#what-leaves-feature-by-feature)
- [Features that send nothing](#features-that-send-nothing)
- [Where requests go](#where-requests-go)
- [Free AI tiers and their terms](#free-ai-tiers-and-their-terms)
- [What stays on your computer, and where](#what-stays-on-your-computer-and-where)
- [How long it's kept](#how-long-its-kept)
- [Backups, Profile sync and the diagnostics zip](#backups-profile-sync-and-the-diagnostics-zip)
- [Things Kurooto refuses to keep](#things-kurooto-refuses-to-keep)
- [What the AI may read and write on your computer](#what-the-ai-may-read-and-write-on-your-computer)
- [Removing your data](#removing-your-data)

## The principles

- **It runs here.** Your notes, journal, deadlines, reminders, call transcripts and settings live on your computer.
- **Nothing to the author.** The only thing Kurooto fetches from its own release site is updates and the list of
  withdrawn versions, both checked against a signature. Nothing about you goes the other way.
- **Your own accounts.** The AI, Telegram bot, call line (Cloudflare), Google project, GitHub repository and backup
  folder are all yours. Kurooto signs in to each as you; no middleman server holds your access.
- **Nothing goes to anyone but you without your tap.** Kurooto never emails, messages or shares on its own. An email
  reply is sent only when you tap **Send**; a class pack you make comes to your own Telegram for you to forward;
  approvals are never given for you.
- **The AI sees only what a request needs.** What you ask, the notes it reads to answer, what its tools return, and
  two short notes about you that go along with every request: the "In brief" part of your profile
  ([teaching-kurooto.md](teaching-kurooto.md)) and your how-to-help-me note.
- **Some things are never read by any cloud AI**: mail marked confidential, calendar events marked private (only their
  time is kept), and anything Kurooto refuses to keep (below).

## What leaves, feature by feature

"The AI you picked" means the brain you chose ([ai-brains.md](ai-brains.md)): Google for a Gemini key or agy, Anthropic
for Claude Code, the service you entered for an OpenAI-compatible one, or nothing at all for local models.

### Talking to Kurooto

| Feature | What leaves | Where to |
|---|---|---|
| Telegram | your messages to the bot, its replies, files you send it | Telegram, to your own bot |
| Questions and approvals | each question or approval, wherever Kurooto reaches you; open ones are also in the brief your call line keeps | Telegram and your paired phones; desktop notifications stay here |
| Chat with your AI | what you ask; notes it reads to answer; what its tools return; your profile's "In brief" part, your how-to-help-me note and your persona card (empty unless you write one) | the AI you picked |
| Setup page: Try it now | what you type that isn't an instant request, like a Chat message; nothing goes to Telegram or your phone | the AI you picked |
| Voice notes | the recordings | Google (Gemini, your key) |
| Files into notes | with Chat on, the files you send, so the AI can file them | the AI you picked |
| Photo to dates | the photo you sent for its dates (`dates` as its caption, `/dates`); nothing is added before you tap | the AI you picked |
| Going offline and coming back (on by default) | the "going offline" and "back online" messages, and messages kept while the network was down | Telegram; with Phone calls, the phone app through your call line |
| Going offline, with Phone calls | your night and focus hours for the next day and the message's wording; only after you approve (asked once): your bot's token and chat id, so the line can say "offline since 22:10" | your own Cloudflare account (your call line) |
| Calm by default | nothing (see [What stays](#what-stays-on-your-computer-and-where)) | stays here |
| Memory: what an AI reply is told | only when your message refers to past things ("on the call", "yesterday", "that thing") or shares words with something you're in the middle of: at most about 600 tokens (`memory.budget_tokens`) of one-line items from the [memory ledger](#the-memory-ledger) (open threads, gists, meeting and daily-note lines), never transcripts, with that request; a call's brief also gets your open threads and the last day's gists | the AI you picked; for calls, Google (Gemini Live, your key) |
| Wrong button and test cases | nothing | stays here |

### Your AI and what it learns

| Feature | What leaves | Where to |
|---|---|---|
| About you | the reports you add stay on this computer; building the profile sends them to the AI once; afterwards its "In brief" part goes along with every AI request | the AI you picked |
| Remember | your how-to-help-me note goes along with every AI request | the AI you picked |
| What Kurooto is running (`self.md`) | only with a question about Kurooto itself, when your AI reads it (`kurooto_self`), or with `/fixme`'s Ask my AI: the version and update channel, this computer's system and hardware profile, the AIs and models set up (fallback order, limits), each feature and whether it works, the last day's failures counted by kind, the last few requests' AI, model and time, and where the settings and log are. Never messages, notes, request titles, answers or secrets | the AI you picked |
| Nightly look back | what happened today (what you answered, moved, skipped, and when), Kurooto's questions and your answers, today's call transcripts and journal (each can be left out: `retro.transcripts`, `retro.journal`), your how-to-help-me note, the settings it may change; for a skill change you approved, that skill's text | the AI you picked |
| Dreaming: a second opinion (`dreaming.consolidate_ai` = `main` only; the default asks the model on this computer) | two lines that may say the same thing or disagree: how-to-help-me lines and lines of your notes, never a gist; at most 8 pairs a night | the AI you picked |
| Dreaming: for your profile, a second look (`dreaming.fold_ai` = `main` only; the default asks the model on this computer) | the lines of yours the rules picked as lasting (from your chats, calls, requests and journal; never health, money, passwords or other people), one at a time, at most 8 a night. A line you Keep then goes along with every AI request, in your profile or how-to-help-me note | the AI you picked |
| Set up from what you say: the one pass (`infer.sweep_ai` = `main` only; the default asks the model on this computer) | a line of your chats or journal that the rules couldn't read but that looks like a project, a class, a routine or a short name, one at a time, at most 10 a night | the AI you picked |
| Learns from its own work | nothing to build its search index (it stays on this computer); the passages the AI finds when it searches it, with that request; to learn a skill, the finished request, its answer and its steps; to learn a lesson, your correction and the skill; to pick up facts, the day's requests (with the nightly look back) | the AI that takes second looks (`learning.brain`), else the AI you picked |
| Dreaming: proposed fixes to skills (`dreaming.propose_prompts`, off) | the skill that keeps going wrong and the requests that went wrong (what was asked and your words about it); tuning effort, AI order and Start-by sizes sends nothing | the AI that takes second looks (`learning.brain`), else the AI you picked |
| Skills | what you send with a skill and the notes it reads; for `/newskill`, your description and the names of your tools and skills | the AI you picked |
| Skills: revision packs | Tectonic, if you install it, downloads LaTeX packages; nothing of yours is sent | Tectonic's public package server |
| Research add-on: LaTeX tracker | Tectonic, if it's installed, downloads LaTeX packages it lacks; nothing of yours is sent. **BibTeX for a key** (only when you tap it): the citation key and the sentence it's cited in | Tectonic's public package server; the AI you picked |
| Skills: packs before exams | the same as `/pack`, only after you tap Build it (unless `skills.auto_pack` is `auto`) | the AI you picked |
| Study packs (`/studypack`) | nothing to your AI: Kurooto only collects files and fills in a prompt. The zip and the prompt come to your own Telegram (or as a Drive link when over 50 MB); you decide which other AI to give them to | Telegram (your bot); your Drive for big packs |
| Hint ladder | the problem (photo or text), the course's AI-policy line and the notes the AI reads; with "no AI help" in that line, nothing | the AI you picked |
| Quiz | with Chat on, the question from your notes and your answer, to grade it | the AI you picked |
| Concept graph | a few pages of a book's text at a time, and the titles and opening lines of related notes; the checks and matching run here | the AI you picked |
| Notes brain (GBrain) | on computers with a graphics card or Apple Silicon, nothing (the index is made here); on others, note text to make the index, unless you chose keyword-only | Google (Gemini, your key) |
| Notes brain: your own GBrain | whatever your own brain is set up to use; with `gbrain.agy_mcp` and your approval, agy may use its tools | your brain's own services; Google (agy) |

### Study

| Feature | What leaves | Where to |
|---|---|---|
| Check-ins | nothing; with check-ins by call and Chat on, what you said on the call, to write your journal and study logs | the AI you picked |
| After-class notes | nothing; with Chat on, your answer and the photos and files sent with it, for a study log | the AI you picked |
| Weekly summary | nothing; with the Sunday review call and Chat on, the call's transcript, to write the weekly review | the AI you picked |
| Handwritten notes | nothing when a model on this computer reads the pages; otherwise the scans and photos (unless `handwritten.cloud` is `false`: then they wait for a model here). To link a written-out note: its text and the titles and opening lines of the notes it may relate to (`handwritten.link` = `false`: none) | Google (Gemini, your key) only when nothing here reads them; the linking to the AI you picked |
| Books and PDFs | nothing while reading (text layer, Tesseract and a local vision model all work here). Only with `books.gemini` on (off by default; books may be copyrighted): pictures of pages nothing here could read. When the AI writes notes: excerpts of your books, Classroom materials and notes, in the mix you chose | Google with `books.gemini`; the excerpts to the AI you picked |
| Books: `/books setup` | installing Tesseract downloads it (winget or Homebrew; on Linux it opens the install page) | Microsoft's winget sources or Homebrew |
| Class packs | a pack you make: the section's courses, timetable, term dates, recurring quizzes and exams; never names, keys, notes or skills. Importing sends nothing | Telegram, to your own bot; you choose whom to forward it to |
| Exam season | nothing; with Phone calls on, the leave-by alarm (its time, the exam and what you said about the venue), and the exam in calls' brief that day and the day before | your call line; Google (Gemini Live) on the call |
| Research | your fields, keywords and searches (never your notes) | the sources you pick: arXiv, bioRxiv, medRxiv, PubMed, feeds (all public) |
| Research: Zotero | a paper you tap into Zotero: its public details (title, authors, abstract, link) | the Zotero app on this computer, or Zotero's web API (`api.zotero.org`) with your key |
| Check my draft | the draft you send, and the course notes the AI reads | the AI you picked |
| Research: "Remind me tomorrow" by call | the project's name, as the call's reason | your call line, like any call |
| Research: `kurooto watch` | the command's name, exit code, run time and last lines (`--lines 0`: none) | Telegram, like any message |

### Calls and your phone

| Feature | What leaves | Where to |
|---|---|---|
| Phone calls (live voice) | call audio and what's said; the call's setup (your name, the assistant's name, which tools exist, the lessons from earlier calls) | Google (Gemini Live, your key) |
| Phone calls: transcripts while the computer is off | the call's transcript, held by your call line until the computer is back | your call line |
| Phone calls: while the computer is off | a short brief (what's due, today's classes and check-ins, open questions, quiz questions, the alarm), the steps for check-in, wake-up and Sunday calls with what they need, and your notes' titles, headings and first lines | your own Cloudflare account (your call line) |
| Phone calls: turn by turn | your speech, to your phone's speech recognizer (on Android 13+ with your language downloaded it stays on the phone; otherwise usually Google's, or Apple's on iPhone); the text of each turn | your phone's speech service; Google (Gemini, your key) or the model on your computer (`calls.turn_brain` = `local`) |
| Phone calls: text on Telegram | the call's conversation, as messages | Telegram and the AI you picked |
| Calls look back (after every call, `calls.review`) | the call's transcript and the tools it used, to do what slipped through and write lessons. The lessons are kept here and told to every later call | the AI you picked (`calls.review_brain`, empty: your main one); the lessons then go with each call to Gemini Live |
| Ringing and phone messages | "a call is ringing" messages and the questions and messages you send to the phone (`notify.app_kinds`), encrypted with a key your Android phones, your computer and your call line hold (ntfy can't read them; your call line could, and so could the Android app's answers) | ntfy.sh (Android; with `kurooto ntfy-token`, as your ntfy account: the token is kept on this computer and your call line) or Apple/Google push (iPhone web app; the push itself is empty) |
| What's waiting for your phone | the text of open questions, approvals and messages for your phones (at most 40; gone after a day, or once answered or expired) | your call line |
| The app's chat | what you type in the app (sealed from Android with the same key as the ring messages, so ntfy can't read it but your call line could; over HTTPS from an iPhone) and Kurooto's answers; the line keeps the chat's last 50 messages, each for at most 3 days; with `notify.app_chat` on, or without Telegram, Kurooto's own messages too | your call line; ntfy.sh (Android, encrypted as above) or Apple/Google push (iPhone; the push itself is empty) |
| Files for the app's chat (without Telegram) | where Telegram would get a document: with Drive upload on, the file, into your own Drive; otherwise a copy encrypted on your computer, kept for a day (up to 10 MB). The key is only in the link inside the chat message, so the copy is as private as the chat | your call line; Google (your Drive) with Drive upload on |
| Files you shared, for the chat's AI | the names and paths of files shared from the phone in the last two hours, when your request talks of a file | the AI you picked |
| Tell Kurooto (the iPhone Shortcut) | what you say to the Shortcut, as text, like a chat message from that iPhone; the call line keeps a hash of the link, the phone it belongs to, and when it was made and last used | Apple (dictation on the iPhone); your call line, then this computer |
| Bedside mode (Android) | nothing new: the phone reads the calls already booked on your call line (times and reasons) and how many things wait | your call line, already |
| The phone outbox (computer off) | chat messages, button taps, answers and shared files (up to 20 MB) you send from a phone while the computer is off, held until the computer takes them, then deleted; for a day after, the ids of what went through and the computer's short note | your call line |
| Morning alarm | the alarm time; with Chat on, the AI reads your notes to draft the day's plan, and the wake-up call's transcript to settle it | your call line; the AI you picked |
| Location reminders (`reminders.places`, off by default) | the place's name and the reminder's text, to your Android app; where your places are and when you arrive stay on the phone | your call line; ntfy.sh (encrypted, as phone messages are) |
| Reminders with the lid shut | the next day's reminders and a morning line, each sealed with a key only your Android phone has (your call line sees only times and ids); each phone's public key. When the computer sleeps, the sealed copy goes out through ntfy.sh | your call line; ntfy.sh, still sealed |

### Notes, sync and backups

| Feature | What leaves | Where to |
|---|---|---|
| Notes sync | your whole notes folder (conflict copies too) | your own private GitHub repository |
| Notes sync with Phone calls | read access to that repository, so calls can read notes while the computer is off | your call line's secret store |
| Backups | a zip of Kurooto's settings, data and state; your notes and keys only if you turn them on. Not encrypted | the folder you pick, and whatever cloud syncs that folder |
| Profile sync | your settings, passwords and keys, and saved state, all encrypted with your passphrase; only the save time, Kurooto's version, the kind of computer and a random id are in plain text | your own private GitHub repository |

### Google

| Feature | What leaves | Where to |
|---|---|---|
| Google (Classroom, Gmail drafts) | nothing new: Kurooto reads Classroom and writes drafts in your Gmail, with your own sign-in | Google |
| Classroom → notes | post text and the text of attached files, to write the notes | the AI you picked |
| Mail digest | the text of the mail you chose (senders, domains and labels you named; your own school or work domain; what your mail query matches, where personal mail is only counted). Everything else, mail marked confidential and your never-read list: only counted, here | the AI you picked |
| Mail digest, local confidential summaries | nothing: a model on this computer reads it; the summary stays in Kurooto's data folder | stays here |
| Email in (off by default) | the text of mail you forwarded to your +kurooto address or labelled for it; mail to +kurooto from anyone but you (and addresses you listed) is never opened | the AI you picked |
| Email reply drafts | the draft, into your Gmail Drafts; sent only when you tap Send | Google (your Gmail) |
| Mail digest by email | each digest's text, to your own address only; not sent if it mentions confidential material | Google (your Gmail, to yourself) |
| Agent plan calendar | each block's title and time | your Google Calendar, in Kurooto's own calendar |
| Google Calendar | nothing; Kurooto only reads | (read from Google) |
| Drive upload | the files you send yourself, and files too big for Telegram | your Google Drive, Kurooto folder; nothing is shared |

Details of each Google permission are in [google.md](google.md#what-each-feature-asks-google-for).

### Your computer and setup

| Feature | What leaves | Where to |
|---|---|---|
| Updates | a request for the newest version and the withdrawn-versions list; nothing about you | Kurooto's public release site |
| Kurooto Terminal | nothing by itself; getting kitty or fish (only when you say yes) downloads them | their official releases |
| Terminals, and your AI's program in them | nothing by themselves; what you type to your AI's program goes to its service, as when you run it yourself | that program's service |
| Your add-ons | nothing by the feature; your add-ons' own code can send whatever it's written to send | wherever your add-ons send it |
| Add-ons by link (official ones too) | git fetches it when you add or update one; then only what its card says: the hosts it may reach, and what the programs it may start send | the git address you gave (github.com for the official add-ons); the hosts on its card |
| Diagnostics zip (`kurooto doctor --bundle`) | nothing: it's saved on this computer for you to look at and send yourself | stays here until you send it |
| Setup page progress | nothing: which setup steps you finished or skipped, and the seconds spent on each, stay in `setup.json` in Kurooto's state folder (never what you typed); the diagnostics zip includes them | stays on your computer |
| `kurooto uninstall --revoke` | requests to delete your call line (Cloudflare), revoke each Google sign-in (Google), and clear your bot's webhook, waiting messages and command menu (Telegram) | those services |

## Features that send nothing

These work entirely on your computer: Reminders, Deadlines (with recurring quizzes, the not-interested list and exam
mode), Start-by dates, Subjects and timetable, Doubt queue, First-week quests, Calendar (it only reads your calendar's
private link; event descriptions are read only for `#nocall`, `#focus` and `#private` and aren't kept; private events
are kept only as "Busy (private)", not even told to your AI), Study tracker (window titles are read and thrown away;
only minutes per subject are kept; the idle check never reads what you type), Quick notes and prompts, Local AI models,
the [offline helper](your-computer.md#the-offline-helper) (only its model's download goes out, made by Ollama),
Stay awake on charger, Space keeper, the reserve (Markdown copies of Kurooto's state for AI programs, in the state
folder), notes brain timelines, course pages, weekly checkup and checkup line, Dreaming's consolidating and its
"For your profile" lines (rules, and the model on this computer for a second look; the lines waiting for your Keep
are kept owner-only in Kurooto's state folder), setting up from what you say and its nightly pass (rules, and the
model on this computer for a line the rules can't read), `kurooto top`, `kurooto runlog` (and run compare). Sync everything sends only what each
sync's own feature sends.

## Where requests go

Every request Kurooto makes on the internet goes through one place that counts it: the host, the feature, how many
requests, and how many bytes went out and came back, per day. **`/egress`** shows the last 7 days. Only the counts are
kept (`egress.json` in the state folder, 30 days), never what was sent.

Each host is checked against Kurooto's list, which is the "Where requests go" table in `docs/PRIVACY.md`: Telegram,
Google's APIs (Gemini, sign-in, Classroom, Gmail, Drive and Calendar), GitHub, Cloudflare and your call line
(`.workers.dev`), ntfy.sh, Node.js and Ollama downloads, arXiv, bioRxiv and PubMed, and Kurooto's release site.
Addresses you gave are yours and always allowed: your calendar's link, class calendars you subscribed to, your Research feeds, your own AI service, your
call line, your ntfy server, and pages your AI reads for a request. This computer (`127.0.0.1`) is never counted.

Programs that go online by themselves show as **handed to** them, with the feature: git (Notes sync, Profile sync, add-ons by link),
npm and wrangler (setting up the call line), agy and Claude Code, Ollama (a model download), GBrain, Tectonic and
installers. Kurooto doesn't see what they send; the tables above say where it goes.

**`privacy.egress`** decides what happens to a host that isn't on the list:
- `record` (the default): it's counted and marked "not on the list", and the request goes ahead. It's the default
  because an add-on or an address changed in settings can reach hosts Kurooto can't know of.
- `enforce`: it's refused, and the feature says "Kurooto didn't connect to <host>". Add hosts you trust to
  **`privacy.allow_hosts`** (`["feeds.example.org"]`; `".example.org"` allows every host under it).
- `off`: nothing is checked or counted.

**Add-ons by link** are fenced apart in every mode: their code reaches only the hosts on the card you agreed to and
starts only the programs on it; anything else is refused and listed by `/egress` as blocked for "add-on <name>"
([add-ons.md](add-ons.md#add-ons-by-link)).

## Free AI tiers and their terms

**A free Gemini API key** (Google AI Studio's free tier):
- Google may use what you send and what it answers to improve its products, and human reviewers may read it. Don't
  say or type anything there you wouldn't want read.
- You must be 18 or older.
- In the EEA, the UK and Switzerland you need a paid key (billing on).
- Phone calls and voice notes always use Gemini, whichever AI answers your messages (a turn-by-turn call can use the
  model on your computer instead).

On a paid key Google doesn't use what you send to improve its products. Or keep those features off, or use local
models where they're offered.

**Antigravity (agy):** Kurooto runs Google's own agy program on your computer, signed in as you, and never touches its
sign-in. Google's answers differ on whether other tools may start agy unattended, so there is some risk to your Google
account; for tools like Kurooto, Google recommends a Gemini key.

**Claude Code and OpenAI-compatible services** work under their own terms and your own account. Claude Code gets its
reach for each request only; nothing is saved in its own settings.

## What stays on your computer, and where

`kurooto paths` prints the folders. By default:

| | Windows | macOS | Linux |
|---|---|---|---|
| Settings | `%LOCALAPPDATA%\Kurooto\config` | `~/Library/Application Support/Kurooto/config` | `~/.config/kurooto` |
| Data | `%LOCALAPPDATA%\Kurooto\data` | `~/Library/Application Support/Kurooto/data` | `~/.local/share/kurooto/data` |
| State and logs | `%LOCALAPPDATA%\Kurooto\state` | `~/Library/Application Support/Kurooto/state`, logs in `~/Library/Logs/Kurooto` | `~/.local/state/kurooto` |
| Your notes | `Documents\Kurooto` | `~/Documents/Kurooto` | `~/Documents/Kurooto` (or `~/Kurooto`) |

- **Secrets** (bot token, API keys, Google sign-ins, call line keys, calendar links) are in your system's keychain:
  Windows Credential Manager, macOS Keychain, or the Secret Service on Linux. Where there is none (and when Kurooto
  starts at boot on Linux, while the keychain is still locked), they're in `secrets.json` in the settings folder,
  readable only by your user account. They're never written to logs.
- **The state folder** holds your check-ins, deadlines, AI requests and answers, call transcripts, the schedule,
  questions, the record of messages that came by themselves (`calm.db`, kept 45 days: when, why, the setting, what it
  was about, the first 300 characters, whether you tapped it), test cases (`cases/`), the calls' lessons
  (`calls/lessons.md`), and earlier versions of notes the AI edited (`note-history/`, the last 20 per file). With
  Learns from its own work on: the search index of past requests, calls and chats (`learning/history.db`), and the
  earlier versions of skills it changed (`learning/before/`). What's kept of conversations stays until you
  set how long:
  [How long it's kept](#how-long-its-kept).
- **The memory ledger** (`ledger.db` in the state folder) holds what Kurooto remembers, encrypted with a key in your
  keychain: [The memory ledger](#the-memory-ledger).
- **The data folder** holds the About you reports (never synced), Classroom's downloaded files, books and their text,
  and confidential mail summaries (`mail/confidential/`, readable only by your user account).
- **Mail copies:** the text of mail chosen for the digest only until the digest is written; the sender, subject and a
  short excerpt of digested mail for 30 days, so a reply draft can answer it.
- **The dashboard** (`http://127.0.0.1:8770`) answers only this computer, needs a key only its own page gets, refuses
  other websites, and on Linux checks that each request comes from your own user account.

## How long it's kept

What Kurooto keeps of your conversations stays until you choose otherwise. Set **`privacy.keep_days`** (e.g. 30) and
it's forgotten after that many days, every night at 04:15 (or when the computer wakes, if it slept through it); 0, the
default, keeps it until you `/forget` it:

| What | Where (state folder) |
|---|---|
| Call transcripts, calls that went on as text, and what calls searched your notes for (8 days at most) | `calls/transcripts/`, `calls/textcalls.json`, `calls/searches.json` |
| What you asked the AI and what it answered, and your words when you said an answer missed (the time, AI and effort stay, without the words, for `/usage`) | `jobs.db`, `jobs/*-result.md` |
| Chat's recent turns | `chat/history.json` |
| Answered and expired questions (`ask.keep_days` gives them their own time) | `ask/` |
| Wrong-button cases you didn't make test cases (`cases.keep_days` likewise) | `cases/` |
| The words of messages that came by themselves (when and why stay for 45 days) | `calm.db` |
| The search index of past requests (Learns from its own work) | `learning/history.db` |
| Threads you were in the middle of (by when each opened) | `ledger.db` (encrypted) |
| Log lines | the logs folder |

**`/forget 7d`** forgets the last 7 days of all that now (also `/forget 12h`, `/forget 2w`), and says how many of each
kind went. **`/forget all`** forgets everything, after a confirm button. `privacy.keep_days` = `0` keeps everything
until you forget it.

### Gists: what settles

Conversations settle the way memories do: as the words of a call, an AI request or a chat fade (`privacy.keep_days`
or `/forget`), it settles into a **one-line gist** of what it decided or did. The nightly job lets the words go only
once their gist exists. Gists are made by rules from Kurooto's own records, never by rereading the words with an AI:

| What | Its gist keeps |
|---|---|
| A call | what it was for, and what its tools did ("set reminder: I'll remind you Fri 23 Oct at 09:00: book the lab slot"); tools that only read are named, never what they read |
| An AI request of yours | its title (the first 80 characters of what you asked), how it ended and its run receipt; never the answer |
| A chat turn | its request's name, once |

A line that looks like a health, money or password detail keeps only its kind ("an AI request about something
money"). They stay in the [memory ledger](#the-memory-ledger) (encrypted, never your notes) for good, or
`privacy.gist_days` days when you set it. **`/gists`** shows the latest, **`/gists lab`** finds them, **`/gists forget 3`** drops one. `/forget 7d`
keeps them; **`/forget all`** asks: **Forget all, keep gists** or **Forget gists too**. `privacy.keep_gist` = `false`
makes none. With `privacy.gist_model` on and [Local AI models](ai-brains.md) on, a model on this computer adds one
sentence of what a call decided; a cloud AI never does.

### The memory ledger

Everything Kurooto remembers is in one place on this computer, `ledger.db` in the state folder, and it's always
encrypted, whether or not you use Profile sync:

| Row | Where it comes from |
|---|---|
| Gists | conversations whose words faded (above) |
| Threads | what you said you'd do, in a message or on a call, and tasks you started ([Talking to Kurooto](talking-to-kurooto.md#open-threads-and-that-thing)) |
| How-to-help-me lines | the dated lines Kurooto keeps in your how-to-help-me note |
| Days | your daily notes' headings and lines (a health, money or password line is left out) |
| Meetings | the dated lines under a project note's "## Meetings" |

- **Encrypted at rest.** Each row's words and where it came from are sealed (AES-256-GCM) with a key made on first use
  and kept in your keychain (Windows Credential Manager, macOS Keychain, the Secret Service on Linux; the owner-only
  `secrets.json` where there's none). On disk stay only each row's kind, its times, a thread's open or done, and
  keyed hashes. Searching decrypts into memory, so no index of your words is written. If the key can't be read (a
  keychain still locked at boot), nothing is shown or written until it can.
- **Your notes stay the source of truth.** Days, meetings and how-to-help-me lines are read from your notes when they
  change; gists and threads live only here. **`/memory export`** writes the gists and threads to a note in your inbox.
- **Find and forget.** **`/memory`** lists it, newest first and numbered; **`/memory glacier`** finds rows with those
  words; **`/memory forget 3`** forgets one (a how-to-help-me line comes out of that note too; a daily-note or meeting
  line stays in your note, which is yours, and stays forgotten here).
- **Ask it.** "When did I last talk to Prof Ortiz?" and "what was I doing last Thursday?" are answered from it, by
  rules on this computer.
- **Covered by `/forget`.** `/forget 7d` drops the threads from those days, `/forget all` all of them (and the gists if
  you choose); `privacy.keep_days` expires threads like the rest.
- **Out of backups** unless you turn on `backups.memory`; a backed-up ledger opens only where its key is (`backups.secrets`
  carries the key). Never in Profile sync, never in the diagnostics zip.

What it never touches:
- **Your notes folder.** A voice note's recording is saved in your notes' inbox, so it stays; delete it there.
- **Test cases you made, open questions, a call still going.**
- **The event log** (`events.jsonl`): times, counts and request names, never what you typed or what was answered.
  Features learn your rhythm from it over weeks.
- **Messages on Telegram or your phone:** they're in those apps; delete them there.
- **Backup zips** you made before.

Your call line holds a call's transcript only while the computer is off and hands it over when it's back, so nothing
waits there to be forgotten.

## Backups, Profile sync and the diagnostics zip

| | Backups | Profile sync | Diagnostics zip |
|---|---|---|---|
| Where it goes | the folder you pick | your private GitHub repository | stays on this computer until you send it |
| Encrypted | no | yes, with your passphrase (never stored) | no, but secrets are blanked |
| Settings | yes | yes | yes, with secrets, names, email and web addresses and folders blanked |
| Passwords and keys | only with `backups.secrets` (then anyone with the zip can use them) | yes, encrypted | never |
| State (deadlines, check-ins, routines, schedule) | yes | the parts worth keeping | only how things went (counts, never what was said) |
| AI requests and answers, transcripts | yes | no | no |
| Your notes | only with `backups.notes` | no (Notes sync keeps them) | no |
| About you reports | yes | no | no |
| Confidential mail summaries | only with `backups.confidential_mail` | no | no |
| Calm records | yes | no | no |
| Test cases | no | no | no |
| The search index of past requests (Learns from its own work) | no (it's built again from the rest) | no | no |
| The memory ledger (encrypted) | only with `backups.memory`; it opens only with its key (`backups.secrets`) | no | no |

More on each: [updates-and-backups.md](updates-and-backups.md). Before you share a diagnostics zip, open it and look.

## Things Kurooto refuses to keep

- **Remember** asks "Still true?" about a line it kept that hasn't come up in 90 days, at most two a week
  ([Teaching Kurooto](teaching-kurooto.md#remember)); only its own dated lines, never ones you wrote.
- **Remember** won't store health, money or password details: they'd travel with every AI request. It says so and
  keeps nothing. Skills are told to keep health, money and other people's private details out of your notes too.
- **Learns from its own work** never keeps a fact about health, money, passwords or other people (a line naming a
  relative or friend, a phone number, an email address).
- **Wrong button and test cases** never keep long messages, several requests in one, or anything about health, money
  or passwords. Cases you didn't review are forgotten after 30 days (`cases.keep_days`).
- **Mail marked confidential** is never read by the AI you picked, never summarised by it, and never answered with an
  AI draft. Kurooto reads its text on your computer only to spot the marking, then drops it.
- **Open threads** never open from a sentence about health, money or passwords.
- **Private calendar events** keep only their time.
- **Events** (the activity log) record counts and request names, never what you typed or answered.

## What the AI may read and write on your computer

- **Read:** your notes folder; your Documents, Downloads and Screenshots folders; Kurooto's copies of Classroom and
  mail; the reserve. Hidden files and folders (like `.git`) are left out, and a link that leads elsewhere is refused.
- **Write:** your notes folder, Classroom's course files folder, and (with add-ons on) your add-ons' `skills/`. Text
  files only. Documents and Downloads stay read-only.
- **Your text:** it adds notes and lines; it changes existing text only when you asked, one passage at a time, after
  keeping the previous version.
- **The web:** public pages, read only, a few MB at most; never this computer or your local network.
- Everything it reads goes to the AI you picked, like the notes it reads to answer.

Details: [ai-brains.md](ai-brains.md).

## Removing your data

- **Conversations:** `/forget 7d` or `/forget all` ([How long it's kept](#how-long-its-kept)).
- **One feature:** turn it off (Dashboard → Features). Its data stays until you delete it; your notes are never
  deleted.
- **A paired phone:** `/phones`, then `/unpair <id>`. A lost phone: `kurooto rotate` gives your call line new keys and
  forgets every paired phone ([phone-app.md](phone-app.md)).
- **Google access:** `/google forget <name>`, or myaccount.google.com/connections ([google.md](google.md#taking-access-away)).
- **Leaving for good:** `kurooto uninstall --revoke` first deletes your call line from your Cloudflare account,
  revokes each Google sign-in and clears your Telegram bot's webhook and menu, then removes Kurooto's keys from your
  keychain and Kurooto itself. Your notes folder is never deleted. It lists what's left for you: the GitHub token(s),
  the Gemini key, the Google Cloud project, Profile sync's `kurooto-profile` branch, the bot itself (`/deletebot` to
  @BotFather), backup zips in the folder you picked. Step by step: [updates-and-backups.md](updates-and-backups.md).
