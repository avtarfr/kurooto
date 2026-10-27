# Kurooto user wiki

Kurooto is a personal assistant that runs on your own computer. You talk to it through your own Telegram bot (and, if
you like, by phone). It reminds you of things, keeps track of what's due, asks how your day went and writes it into
your journal, searches your notes, reads your books into notes, and can ring your phone, including a wake-up alarm.
An AI you choose answers your questions and does the bigger tasks. Every feature is off until you turn it on.

This wiki is the guide for people who use Kurooto. Read it top to bottom once and you'll know everything it can do and
how to ask for it. `/help` on Telegram lists the commands of the features you have on; [Commands](commands.md) lists
all of them.

## Where things happen

| Place | What you do there |
|---|---|
| **Telegram** | Talk to Kurooto in plain English or with `/commands`; it sends reminders, questions with buttons and files. Your main channel. |
| **The dashboard** | `http://127.0.0.1:8770` in a browser on the computer Kurooto runs on: turn features on and off, change settings, the Today page, Ctrl+K for everyday things, a map of your notes. |
| **Your phone** | The Android app, or the iPhone Home Screen app: calls, the wake-up alarm, questions and approvals. |
| **Phone calls** | Call Kurooto like a person, and let it call you for reminders, check-ins, deadlines, quizzes and the alarm. |
| **Your notes folder** | Plain Markdown files (works with Obsidian): journal, course notes, book notes, everything Kurooto writes. |
| **Out loud** | With Voice on, Kurooto speaks on this computer and can listen for you; see [Voice](voice.md). |
| **A terminal** | `kurooto` commands for setup, repairs, scripts and a status board. Optional. |

## How the wiki is organised

**Start here**
- [Getting started](getting-started.md): install on Windows, macOS or Linux, the setup wizard, your first 15 minutes.
- [What it can't do yet](what-it-cant-do-yet.md): what doesn't work, or only partly, said plainly: iPhone calls are
  notifications, the computer has to be on, few real computers tested so far.
- [AI brains](ai-brains.md): which AI answers you, free limits, what the AI may do on your computer, and the run
  receipt under each answer.
- [Talking to Kurooto](talking-to-kurooto.md): Telegram, plain English, chat, questions and approvals, pause, focus, voice notes, sending files.
- [Voice](voice.md): Kurooto speaks with a voice made on your computer and, if you turn listening on, hears you; a
  local model tells noise and people talking from you talking to it, and only that leaves the computer.
- [Messages Kurooto sends by itself](messages-it-sends.md): every message it sends unasked and why, the daily limit, going offline, health checks.

**Your day**
- [Reminders and deadlines](reminders-and-deadlines.md): reminders, the deadline list and its chase, recurring quizzes, topics you don't care about, exam mode, start-by dates.
- [Check-ins and journal](check-ins-and-journal.md): evening, night and midday check-ins, your journal, the weekly summary, first-week quests.
- [Phone calls](calls.md): the call line, calls both ways, when calls are held, the wake-up alarm, reminders with the lid shut, what calls learn.
- [Phone app](phone-app.md): Android and iPhone, pairing, answering on the phone, a lost phone.

**Study**
- [Classes and timetable](classes-and-timetable.md): subjects, timetable, term dates, class packs, after-class notes, doubts.
- [Quiz and exams](quiz-and-exams.md): spaced practice, exam mode, the optional Exam season, revision packs, the hint ladder.
- [Books and study](books-and-study.md): books and PDFs read into notes, the study tracker, study packs, handwritten notes.

**Notes and knowledge**
- [Notes and the concept graph](notes-and-concept-graph.md): your notes folder, quick notes, files into notes, search by meaning, Notes sync, the concept graph.
- [Skills and routines](skills-and-routines.md): `/journal`, `/study-log` and the other skills, your own skills, things on a schedule.
- [Research](research.md): a digest of new papers, project logs, experiment runs, a message when a long job ends.
- [Projects and proposals](proposals.md): the AI drafts in a scratch folder of its own; every change to your files
  (notes, a project, a skill) comes as a proposal with the diff, and only your tap applies it. Help with your project.
- [Brain](mind.md): Kurooto's mind (0.8.0), off until you turn it on: a log of what it saw and decided that it can't
  quietly change, kept by a separate program the AI can't reach; each part it grows has its own switch.
- [Google](google.md): Classroom, Gmail digest and reply drafts, Google Calendar, the Agent plan calendar, Drive upload, and setting up your own Google sign-in.

**Kurooto itself**
- [Teaching Kurooto](teaching-kurooto.md): your profile, Remember, the nightly look back, learning from its own work, the Wrong button.
- [Dashboard](dashboard.md): every pane and page, Today, Ctrl+K, keyboard shortcuts, colours, terminals, `kurooto top`.
- [Your computer](your-computer.md): battery, pause and off, staying awake, starting at boot, hardware and local models, diagnostics.
- [Updates and backups](updates-and-backups.md): updates and going back, backups and restore, Profile sync, a new computer, Space keeper, uninstalling.
- [Privacy](privacy.md): what leaves your computer, per feature, and where it goes.
- [Add-ons and scripts](add-ons.md): optional, for people who write code: your own add-ons, and scripts that message or call you.

**Reference**
- [Commands](commands.md): every Telegram command, every plain-English request understood instantly, every `kurooto` terminal command, and the dashboard's keyboard shortcuts.
- [Settings guide](settings-guide.md): every setting, one entry each: what it does, its values and default, when you'd
  change it, what it costs or sends, and what it depends on; grouped by feature.
- [FAQ](faq.md) · [Troubleshooting](troubleshooting.md) · [What it can't do yet](what-it-cant-do-yet.md) ·
  [Glossary](glossary.md)

## Every feature, and where it's explained

Turn features on and off on the dashboard's **Features** page (or in the setup wizard). A feature that's off answers
its commands with "X is off: Features → X → Turn on". Some features need another one first (shown below).

| Feature | What it does | Needs | Page |
|---|---|---|---|
| Telegram | your own bot, Kurooto's main channel | | [Talking to Kurooto](talking-to-kurooto.md) |
| Chat with your AI | free text goes to the AI you picked | | [Talking to Kurooto](talking-to-kurooto.md#chat-with-your-ai) |
| Reminders | "remind me at 9 to call mum" | Telegram | [Reminders and deadlines](reminders-and-deadlines.md) |
| Check-ins | asks how the day is going; replies go to your journal | Telegram | [Check-ins and journal](check-ins-and-journal.md) |
| Deadlines | one list of what's due, with nudges, a call and an overdue check; exam mode; dates from a photo | Telegram | [Reminders and deadlines](reminders-and-deadlines.md) |
| Start-by dates | when to start each deadline (an estimate) | Deadlines | [Reminders and deadlines](reminders-and-deadlines.md) |
| Subjects and timetable | your courses and classes; no calls in class | | [Classes and timetable](classes-and-timetable.md) |
| Class packs | share or import a section's timetable and dates | Telegram, Subjects | [Classes and timetable](classes-and-timetable.md) |
| Doubt queue | doubts from class, brought back before the next one | Subjects | [Classes and timetable](classes-and-timetable.md) |
| Quiz | spaced practice questions from your notes | Telegram | [Quiz and exams](quiz-and-exams.md) |
| Exam season (optional) | one card for the whole exam period, and a revision plan before each exam | Deadlines | [Quiz and exams](quiz-and-exams.md) |
| Weekly summary | the week in numbers on Sundays | Telegram | [Check-ins and journal](check-ins-and-journal.md) |
| First-week quests | one thing to try each day of your first week | | [Check-ins and journal](check-ins-and-journal.md) |
| Files into notes | photos and PDFs you send go into your notes | Telegram | [Notes](notes-and-concept-graph.md) |
| Skills | `/journal`, `/study-log`, `/pack` and more; routines | Chat | [Skills and routines](skills-and-routines.md) |
| Hint ladder | one hint at a time for a problem | Subjects | [Quiz and exams](quiz-and-exams.md) |
| Quick notes and prompts | `/note`, `/prompts` | Telegram | [Notes](notes-and-concept-graph.md) |
| Notes brain (GBrain) | search your notes by meaning | | [Notes](notes-and-concept-graph.md) |
| Local AI models | small models on your computer | | [Your computer](your-computer.md) |
| After-class notes | after each class, what was worth keeping | Telegram, Subjects | [Classes and timetable](classes-and-timetable.md) |
| Remember | how you like to be helped | Telegram | [Teaching Kurooto](teaching-kurooto.md) |
| Nightly look back | small improvements suggested each night | Telegram, Chat | [Teaching Kurooto](teaching-kurooto.md) |
| Learns from its own work (optional) | searches past requests and calls; skills from its own work and your corrections; facts you state | Chat | [Teaching Kurooto](teaching-kurooto.md#learns-from-its-own-work) |
| Wrong button and test cases | teach it your words | Telegram | [Teaching Kurooto](teaching-kurooto.md) |
| Phone calls | call Kurooto, and let it call you | | [Phone calls](calls.md) |
| Morning alarm | a wake-up call that rings on silent | Phone calls | [Phone calls](calls.md) |
| Reminders with the lid shut | reminders reach your Android phone while the computer sleeps | Phone calls | [Phone calls](calls.md) |
| Voice notes | voice messages written out and handled | Telegram | [Talking to Kurooto](talking-to-kurooto.md) |
| Stay awake on charger | the computer doesn't sleep while plugged in | | [Your computer](your-computer.md) |
| Calendar | your calendar's events; no calls during them; class calendars others share, by link | | [Classes and timetable](classes-and-timetable.md#calendar), [Google](google.md) |
| Notes sync | your notes in your private GitHub repository | | [Notes](notes-and-concept-graph.md) |
| Backups | a daily zip in a folder you pick | | [Updates and backups](updates-and-backups.md) |
| Profile sync | your setup, encrypted, for a new computer | | [Updates and backups](updates-and-backups.md) |
| Google (Classroom, Gmail drafts) | Classroom deadlines and posts; email drafts | | [Google](google.md) |
| Classroom → notes | Classroom posts filed into your notes | Google | [Google](google.md) |
| Mail digest | your new mail, sorted, twice a day; Email in (mail you forward to +kurooto, filed into notes) | Google | [Google](google.md) |
| Email reply drafts | reply drafts you send with a tap | Google, Mail digest | [Google](google.md) |
| Mail digest by email | the digest in your own inbox too | Google, Mail digest | [Google](google.md) |
| Agent plan calendar | planned time blocks in a calendar of their own | Google | [Google](google.md) |
| Google Calendar | your Google calendars without an iCal link | Google | [Google](google.md) |
| Drive upload | files to a Kurooto folder in your Drive | Google | [Google](google.md) |
| Handwritten notes | handwritten pages into Markdown notes | | [Books and study](books-and-study.md) |
| Books and PDFs | books read at night into text your AI cites | | [Books and study](books-and-study.md) |
| Concept graph | a read book woven into your notes | Books | [Notes](notes-and-concept-graph.md) |
| Space keeper | cleans Kurooto's own old files | | [Updates and backups](updates-and-backups.md) |
| Study tracker | minutes per subject | Subjects | [Books and study](books-and-study.md) |
| Research | new papers, project logs | | [Research](research.md) |
| Terminals | real terminals in the dashboard | | [Dashboard](dashboard.md) |
| Kurooto Terminal | Kurooto in a terminal window of its own | | [Dashboard](dashboard.md) |
| Your add-ons | your own features from a folder | | [Add-ons and scripts](add-ons.md) |

Some things are always there and aren't features you turn on: questions and approvals (`/q`), `/status`, `/pause`,
`/health`, `/calm` and `/why`, `/jobs`, `/aboutme`, updates, and the "going offline / back online" messages.

## Three rules Kurooto keeps

- **It sends nothing to anyone but you.** Emails, replies and anything outward wait for your tap; approvals are never
  given for you.
- **Your own text is never reworded or deleted.** Kurooto adds notes and lines; when you ask it to edit a note, it keeps
  the previous version first.
- **Nothing goes to whoever made Kurooto.** What leaves your computer goes to services you chose, under your own
  accounts. [Privacy](privacy.md) lists it per feature.
