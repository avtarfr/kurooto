# Talking to Kurooto

You talk to Kurooto through your own Telegram bot: plain sentences, `/commands`, voice messages, photos and files.
Quick requests ("remind me at 9 to call mum") are done at once on your computer; anything else goes to your AI, which
answers as a reply. The same requests work in the dashboard's Today page and Ctrl+K box ([dashboard.md](dashboard.md)),
on a phone call ([calls.md](calls.md)), in the phone app's chat ([phone-app.md](phone-app.md#chat-with-kurooto-in-the-app)),
and in a terminal (`kurooto ask`). Telegram is optional: the phone app's chat can take its place entirely
([phone-app.md](phone-app.md#using-the-app-instead-of-telegram)).

- [Your bot](#your-bot)
- [What happens to a message](#what-happens-to-a-message)
- [Chat with your AI](#chat-with-your-ai)
- [Questions and approvals](#questions-and-approvals)
- [Never without your tap](#never-without-your-tap)
- [Buttons](#buttons)
- [Status, pause, hold and focus](#status-pause-hold-and-focus)
- [Voice notes](#voice-notes)
- [Sending files and photos](#sending-files-and-photos)
- [Getting files from Kurooto](#getting-files-from-kurooto)
- [Other core commands](#other-core-commands)
- [Renaming your assistant](#renaming-your-assistant)
- [From a terminal](#from-a-terminal)

## Your bot

**What it does.** Your own bot, made with @BotFather during setup ([getting-started.md](getting-started.md#7-chat-telegram-or-the-phone-app)).
It serves only the Telegram account that tapped the one-time pairing link, and only in a private chat; messages from
anyone else, and from groups, are ignored.

**The "/" menu.** Typing `/` in the chat lists `/help`, the commands of the features you have on, `/q`, `/jobs`,
`/aboutme`, `/calm`, `/why` (and `/sync` when Notes sync is off), then your skills. A skill with a dash in its name shows
with `_`: `/term_setup` runs term-setup. Telegram shows at most 100. Kurooto updates the menu within a minute of a
feature going on or off, and looks for new skills every 15 minutes.

**`/help`** (and `/start`) lists everything that works right now, in groups (Talking, Reminders and deadlines,
Classes and calendar, Study, Quiz and exams, Calls and phone, Check-ins and journal, Notes, Skills and routines,
Research, Google, Teaching Kurooto, Privacy and memory, Settings and upkeep), each with its page in this wiki: the
commands of the features you have on with what each does, Kurooto's own commands, what you can just say in plain words,
and the features that are off. When that's more than one Telegram message, `/help` sends a short index instead (each
group with its commands) and **`/help <group>`** shows one group in full (`/help calls`, `/help reminders`), including
its features that are off; **`/help all`** sends every group, one message each. **`/help <word>`** searches
everything, on or off: `/help call` shows Phone calls, its commands and how to turn it on. If Chat is off it says free
text isn't sent to an AI. The same `/help` answers in the phone app's chat. The full list is in
[commands.md](commands.md).

**While Kurooto is off or asleep.** Telegram keeps your messages for about a day; Kurooto handles them when it's back.
Telegram doesn't deliver Kurooto's messages while the computer sleeps; with Phone calls set up, your call line can say
the computer went offline, and with Reminders with the lid shut your Android phone still gets reminders
([calls.md](calls.md)).

| Setting (Settings → telegram) | Default | Effect |
|---|---|---|
| `telegram.menu` | `true` | the bot's "/" menu follows your features; off removes the menu Kurooto set and leaves it alone from then on |
| `telegram.silent_kinds` | `["call"]` | kinds of message sent without a sound on Telegram (only while the phone app is paired, since the app rings) |
| `telegram.chat_id`, `telegram.allowed_users` | set when you pair | your chat and your account; don't change by hand |

**What leaves your computer:** your messages travel through Telegram's servers to your bot, and Kurooto's messages back
the same way.

## What happens to a message

Kurooto looks at each message in this order and stops at the first match:

1. **A reply to one of its messages.** Replying to a question answers it; replying to a check-in writes your journal;
   replying to an after-class question, a quest, an "Overdue?" question and so on goes to the feature that asked.
2. **A `/command`.** `/journal` followed by a new line and text works too. A command of a feature that's off gets
   "X is off: Features → X → Turn on." (it never goes to the AI). A skill typed while Skills is off is answered the same
   way.
3. **A skill** (`/journal`, `/study-log`, your own), when Skills is on. See [skills-and-routines.md](skills-and-routines.md).
4. **Files and photos** (see [below](#sending-files-and-photos)).
5. **A call that went on as text** on Telegram: what you type is part of it until it ends.
   **A request to decide your health, relationships or money** ("should I stop my meds?", "should I break up with
   him?", "should I put my savings in crypto?") gets a short answer at once, without the AI: it's yours to decide,
   and who to ask (see [Boundaries it keeps](#boundaries-it-keeps)).
6. **A plain-English request Kurooto understands instantly** ("remind me in 20 minutes to take the pasta off", "what's
   due?", "no calls for 2 hours"). These run on your computer with no AI. Long messages (over 300 characters), and
   messages with several requests in one ("..., also ...", "... and then ...", two sentences), always go to the AI so it
   reads the whole thing. A question ("what...?", "when...?") only matches requests that answer questions. A phrasing
   you taught with the Wrong button goes first ([teaching-kurooto.md](teaching-kurooto.md)). Questions about what's
   remembered come before the features' requests: "did I finish that thing?", "when did I last talk to Prof Ortiz?",
   "what was I doing last Thursday?" ([below](#open-threads-and-that-thing)).
   **Two close readings.** When no instant request takes your words but they're close to two of them (by their
   example phrasings), it asks instead of guessing: 'Did you mean "what's due this week" or "what's on today"?' with
   both as buttons and **Neither** (which sends it on as before). Only when the two are about equally close; otherwise
   nothing changes. Pick the same one twice for the same words and it learns them
   ([teaching-kurooto.md](teaching-kurooto.md#two-readings)). On Telegram and the phone app; `repair.on` off turns it
   off.
   **A request a feature that's off would understand** ("remind me in 5 min to stretch" with Reminders off) gets "That's
   for Reminders, which is off. Turn it on and do it?" with **Turn on** (it turns on that feature, and what it needs,
   then does the request) and **Not now** (it stays off; with Chat on, your AI gets the message instead). A feature
   that needs setting up first says where. On Telegram and the phone app only; `turnon.offer` off goes back to sending
   these to the AI.
7. **"sync everything"** (or `sync all`, `/sync all`) runs every sync that's on.
8. **Chat:** everything else goes to your AI.

With Chat off, step 8 replies "I can't answer free text yet: turn on Chat (it uses the AI you picked) in Settings.
/help lists what works now."

Every instant request is in [commands.md](commands.md#plain-english-requests-understood-instantly). If Kurooto misreads one, tap **Wrong**
under its reply, or send `/wrong` ([teaching-kurooto.md](teaching-kurooto.md)).

## Chat with your AI

**What it does.** Anything that isn't a command or an instant request goes to the AI you picked. Kurooto replies "On
it." and the answer comes as a reply to your message. The AI can act too (add a reminder, a note, a deadline; read your
notes and files): see [ai-brains.md](ai-brains.md#what-the-ai-can-do-its-tools).

**The grey line under an answer.** Every answer ends with one short line in italics, built from Kurooto's own
record of the run, not from what the AI wrote: which AI answered, the effort, how long it took, the share of today's
limit when Kurooto knows it, and what it actually did, e.g. *agy · medium · 42 s · 12% of today's limit · searched
notes, wrote 1 note*. "did nothing" means it used none of Kurooto's tools. See
[ai-brains.md](ai-brains.md#the-run-receipt).

**A line first, for a long answer.** When a request usually takes more than about 20 seconds on that AI (the median
of your last ones at that effort, once there are three), one short line comes before the answer: "Searching your
notes, then answering (about 40 s with agy)." It's a guess from what's known before the run (a file you sent, a link,
words about your notes, things it remembers), not a promise. Never on a call, never for background work; turn it off
with `jobs.plan_line` = `false`. See [ai-brains.md](ai-brains.md#the-plan-line).

**Turn it on.** Features → Chat with your AI (in Starter). Needs a working AI brain.

**From Telegram:**

| Command | Does |
|---|---|
| any text | goes to the AI |
| `high: ...`, `low: ...` | choose how hard it thinks ([effort](ai-brains.md#how-hard-it-thinks-effort)) |
| `/new` or `/clear` (also just "new" or "clear") | start a fresh conversation: forgets the previous turns |
| `/brain` | which AI answers (main and fallback), and whether each is ready |
| `/usage`, `/usage 14` | AI requests per day (last 7 days, or the days you give, up to 60), limits hit, today's limits |
| `/jobs`, `/jobs cancel <id>`, `/jobs cancel all` | what's running and waiting, with Cancel buttons |

**How long its answers are** (`persona.register`, on). A short message (12 words or fewer) gets a short answer; a
long one (80 words or more) may get a full one; a voice note gets an answer worded the way you'd say it aloud (short
sentences, no lists). It goes only by your message's length, never by the time of day, and it doesn't change partway
through a conversation. A length on your [persona card](teaching-kurooto.md#your-persona-card) wins over it.

**Memory of the conversation.** Chat remembers your last few exchanges (up to 6, each cut to 1,200 characters) as long
as the last one was within 2 hours; after 2 hours of quiet a new message starts fresh. Requests from a terminal start
fresh every time. Background requests (digests, the look back) never become part of the chat.

**What it remembers beyond that.** When your message refers to past things ("as we said on the call", "yesterday",
"that thing", "did I ...", a weekday) or shares words with something you're in the middle of, the AI is also told the
few remembered items it's about: open threads, one-line gists of earlier calls, requests and chats, meeting and
daily-note lines. At most about 600 tokens (`memory.budget_tokens`), picked by rules (shared words, the course you
name, the day you name, how recent), each saying where it's from, so an answer can say "as we said on the call at
07:56". Never transcripts. The grey line then ends with "used 2 remembered items". `memory.recall` off sends none.

**Limits.** Telegram messages hold about 4,000 characters, so long answers come in parts; past six parts, the first
five come and then the whole text as a file (nothing is cut off). Answers over about 7,000 characters also come as a
file. A request that's stuck for 10 minutes is stopped with a message.

**What leaves your computer:** what you ask, and the notes it reads, go to the AI you picked.

**Turn it off:** Features → Chat with your AI → Turn off. Instant requests and commands keep working; free text gets
the "I can't answer free text yet" reply. Skills and the Nightly look back need Chat.

## Questions and approvals

This is always there; it isn't a feature you turn on. Sometimes Kurooto needs something only you know ("which chapter
is Friday's quiz on?") or your OK before it does something ("send this reply?"). These come as:

- a **question**: its answers as buttons, plus **Later**; or
- an **approval**: **Approve** / **Deny**, or the asker's own choices (Send / Edit / Discard).

They come from any feature, from an AI request (your answer starts its follow-up) and from your own scripts
(`kurooto ask-me`, `kurooto ask-approval`, see [add-ons.md](add-ons.md)).

**Answering:**

- Tap a button, or **reply** to the message in your own words (photos and files in the reply are kept with the answer).
- Or answer in the phone app, or on a call (open questions come up at the start of every call).
- The first answer wins; answering again elsewhere tells you what was already answered ("That's no longer open").
- **Later** (or a reply "later", "not now", "ask me later", "on the next call") keeps it open for your next call.
- **Nothing new** (or "nothing", "skip", "nothing to add") is a real answer.
- For Approve / Deny, a reply like "yes", "ok", "sure", "go ahead" approves; "no", "cancel", "stop", "don't" denies.
  Anything unclear is asked again. Nothing is ever approved for you.

**`/q`** (or `/questions`) lists open questions (up to 8 at a time, oldest first) with their buttons; reply to one to
answer it. `/status` says how many are open.

**Expiry.** An unanswered question expires after 48 hours (`ask.expire_hours`), or sooner when its asker stops waiting;
then nothing happens ("That question expired"). Answered and expired questions are forgotten after
30 days (`ask.keep_days` gives them their own, `privacy.keep_days` when set applies too), or now with `/forget`
([privacy.md](privacy.md#how-long-its-kept)).

**What leaves your computer:** the question goes wherever Kurooto reaches you (Telegram, the phone app, the desktop);
open questions are part of the brief your call line keeps for calls while the computer is off.

## Never without your tap

Some things Kurooto does only when you asked for them yourself or tapped to approve them. Your AI, a guess from
something you said in passing, and Kurooto's own schedule never do them by themselves:

| What | How it gets your OK |
|---|---|
| Setting, moving or clearing an alarm | you type `/alarm`, say "wake me at 6:45", ask on a call, tap **Set** under the alarm suggestion, or use the dashboard or the phone app |
| Placing a call, or booking one for later | you say "call me at 5", "call me now", "I'm awake" or "quiz me by call", type `/quiz <subject> call` or `kurooto call`, or ask on a call. Calls of features you turned on (check-ins, the alarm, deadline calls) ring at the times you set |
| Reading mail from a new sender, domain, label or search | only `/mail read`, `/mail query`, or Features → Mail digest |
| Sending anything to someone else (mail, a message, publishing) | only your **Send** under a reply draft; nothing else sends to anyone but you |
| Attaching a code repository to a project | only `/repos add <folder>`; repositories are never searched for on the disk |
| Deleting your data | `/forget` (`/forget all` after a confirm button), `/memory forget`, `/gists forget`, Undo and Drop buttons, Keep A / Keep B under the morning message's "Worth a look"; the AI never deletes (a note it changes keeps its earlier version) |

**When your AI wants to.** On a call you're on the line, so the AI does what you asked and says so. Anywhere else (an
AI request from the chat, a skill or routine, an agent program such as agy using Kurooto's tools) the AI can't set
the alarm or book a call by itself: you get a **Your OK first** question ("An AI request wants to set, move or clear
an alarm: set_alarm (time: 7:30). Do it?") with **Approve** / **Deny**, and it happens only on Approve. The AI is told
it waits for you, and asking again doesn't send a second question. Like every approval it never expires into a yes;
`/q` lists the open ones.

## Buttons

Most messages have buttons; each does exactly what the matching command does. A few that appear everywhere:

| Button | Does |
|---|---|
| **Why?** | on a message that came by itself: which feature sent it, why, and the setting that controls it ([messages-it-sends.md](messages-it-sends.md)) |
| **Less of this** | offers Stop / Fewer / Another time for that kind of message, each with Undo |
| **Wrong** | under a reply to a plain-English request or an AI answer: keeps it as a case to fix ([teaching-kurooto.md](teaching-kurooto.md)) |
| **Later** | keeps a question for your next call |
| **Cancel** | under `/jobs`: stops that AI request |
| **Fix** | under `/health`: runs the safe fix for that problem |

Tapping a button shows a short note at the top of the chat. A button from a feature you've since turned off says
"that button is from a feature that's off now". A button on a question that was answered elsewhere does nothing new;
`/q` shows what's still open.

## Status, pause, hold and focus

These come with Telegram, and without it they answer in the phone app's chat (with Phone calls on).

**`/status`** (answers even while Telegram's own feature is off, e.g. from a terminal): whether calls are allowed or
held and until when, focus, the next scheduled things, open questions, today's check-ins, what's due soon, the alarm,
your last three AI requests, add-ons' own lines, and the features that are on.

**Pause.** `/pause` (until you resume), `/pause 2h`, `/pause until 18:00`; `/resume` wakes it. Also `kurooto pause 2h`,
or **Pause 1 h** on the dashboard.

- While paused nothing runs, but Telegram still answers. Anything you send gets "I'm paused until ...; I'll do this when
  I'm back. /resume wakes me now." and is kept; when it resumes, it's handled in order.
- Only `/resume`, `/pause`, `/status` and `/help` work while paused.
- Reminders due meanwhile arrive when it resumes. Your call line keeps placing scheduled calls, so the morning alarm
  still rings.
- After `/resume` on a laptop on battery, heavy work still waits for the charger ("Back on; this laptop is on
  battery...").

**Hold calls.** `/hold 18:00` or `/hold 2h` (no argument: one hour): no calls until then; messages still come. `/calls`
lifts it ("Calls are allowed again (night hours and other holds still apply)"). Plain English: "no calls for 2 hours",
"don't call me until 6pm", "hold calls for 30 min"; "calls are fine again". A day other than today ("no calls on
Friday") goes to the AI, which works out the day.

**Focus (do-not-disturb).** `/focus 2h`, `/focus until 18:00`; `/focus off` (or `stop`, `end`) ends it; `/focus` alone
says whether it's on. During focus, calls are held and messages that can wait are kept until it ends, then delivered
together ("Focus off. 3 messages waited for you"). Approvals, calls, urgent messages and the alarm still come. Plain
English: "focus for 2 hours", "do not disturb until 6pm", "dnd off", "focus done". A calendar event with `#focus` in its
title or description is focus time too ([reminders-and-deadlines.md](reminders-and-deadlines.md)).

**Hooks.** "when I say gym, hold calls 90 min" (or "when I say lab, hold everything 2 h") makes "gym" on its own start
that hold later; `/hooks` lists them, `/hooks drop gym` forgets one, and each step has Undo. Needs Commitments
([classes-and-timetable.md](classes-and-timetable.md#commitments-gym-shifts-standups)).

**The night.** From 23:30 to 07:00 (`availability.night`), or from your bedtime to your alarm, Kurooto doesn't call
you except for the alarm. Messages still arrive at night; mute the chat in Telegram if you don't want them to sound.
See [calls.md](calls.md).

## Voice notes

**What it does.** Send your bot a voice message: it's written out ("Heard: ..."), then handled exactly like a typed
message (a reminder, a question for the AI, a note). Mixed languages are kept as spoken. The recording is saved in
your notes inbox.

**Turn it on.** Features → Voice notes. Needs a Gemini API key, even if another AI answers your messages. Without it:
"Voice notes are off. Turn on Voice notes in Settings (it uses your free Gemini key)."

**Limits.** At most about 18 MB per voice note. A caption-less audio file with a file name (a recording you attach as a
file) is treated as a file, not a voice note. If it can't be written out you get "Couldn't make out that voice note"
with the reason.

**Settings.** `voice_notes.model` (`gemini-flash-latest`).

**What leaves your computer:** the recording goes to Google (Gemini, your key). On the free tier Google may use what you
send to improve its products, so don't say anything you wouldn't type.

**Turn it off:** Features → Voice notes → Turn off.

## Sending files and photos

Send a photo, PDF, document, video or audio file to your bot. It's downloaded into your notes' `inbox/` folder (or your
files folder's inbox, when you set `files.folder`: see [notes-and-concept-graph.md](notes-and-concept-graph.md)), named
with the date and time. For a photo, the largest size is kept. The caption travels with it. Then:

| What you send | What happens |
|---|---|
| a PDF with the caption `book for linear algebra` | it becomes a book for that subject ([books-and-study.md](books-and-study.md)) |
| a `.kurooto-course` file | a class pack to review ([classes-and-timetable.md](classes-and-timetable.md)) |
| a photo with `/hint la` as the caption | the hint ladder ([books-and-study.md](books-and-study.md)) |
| a file with `/note` as the caption | a quick note that links it |
| a file with a skill as the caption (`/add-to-notes`, `/study-log`) | the skill gets the file |
| a reply to a question, with files | the files are kept with your answer |
| any other file, with Files into notes on | "Saved; filing it into your notes…": with Chat on, the AI writes a note that says what it is and links it, in the right place, then replies where it went. Without Chat: "Saved to inbox/...". |
| a link on its own, with Skills on | filed into your notes by the `/add-to-notes` skill |
| any other file, with Files into notes off and Chat on | it goes to your AI with the caption (or, with none, "say what it is"); the AI is told where the file is and opens it. Only an AI that opens files itself (agy, Claude Code) can see a photo: with a Gemini key or another API service, type what's in it |
| any other file, with both off | "Saved to inbox/.... To have your AI look at it, turn on Chat; to have it filed into your notes, turn on Files into notes (Features)." |

**Limits.** Telegram lets bots download files up to **20 MB**; a bigger file gets "Couldn't get that file: Telegram only
lets bots download files up to 20 MB". Put bigger files into the folder yourself (for books: `/books folder <subject>`).

**What leaves your computer:** files are saved on this computer. With Chat on, the AI you picked reads them to file
them.

**Turn it off:** Features → Files into notes. Files you send are still downloaded into the inbox, but nothing files
them; with Chat on, the file and its caption go to your AI as a question instead.

## Getting files from Kurooto

Kurooto sends you files it made (revision packs, study packs, long answers), and the AI can send you files from your
notes folder ("send me my linear algebra pack"), on calls too. From a terminal: `kurooto send report.pdf --caption
"..."`.

- **Up to 50 MB** goes to Telegram (Telegram's limit for bots).
- **Over 50 MB**, with Drive upload on (`drive_upload.big_files`, default on), it goes to a Kurooto folder in your Google
  Drive and you get a link. These temporary uploads are deleted from Drive after `drive_upload.temp_days` (7) unless you
  move them out of the Kurooto folder. Without Drive upload: "... is N MB; Telegram takes files up to 50 MB. Turn on
  Drive upload to get bigger files as a Drive link." See [google.md](google.md).
- **Three or more files at once** come as one zip, so Telegram isn't flooded. Over 50 MB together they go to Drive (or
  are refused without Drive upload).
- **During focus** a file waits until focus ends.
- The AI can only send files from your notes folder.
- **Without Telegram** (the phone app instead), a file comes to the app's chat as a link: Google Drive with Drive upload
  on, else a sealed copy on your call line for a day (up to 10 MB), else a note that it stays on your computer, with its
  path. A long answer's full text comes the same way, right after its first part
  ([phone-app.md](phone-app.md#files-from-your-computer)).

## Boundaries it keeps

Decisions about your health, your relationships and your money are yours. Asked to make one ("should I stop taking my
meds?", "should I break up with him?", "should I take the loan?"), Kurooto says it's not its to decide and who to ask:
a doctor or pharmacist (and your local emergency number if it feels urgent), someone you trust or a counsellor,
someone you trust with money or a financial adviser. One line, no lecture. It still gives facts when you ask for
facts.

This is a fixed list of rules, not the AI's judgement: plain-English requests that match it are answered at once on
your computer; every AI request and every call is also told the rule. `persona.boundaries` off turns both off.

## Open threads and "that thing"

Kurooto keeps a short list of what you're in the middle of, so you can say "that thing" and be understood.

- **Opens** when you say you'll do something, in a message or on a call ("I'll send the draft tonight", "I need to
  reply to Lena's email", "I'm going to finish the problem set"), and when you start a task (a study session, progress
  on a deadline: "ps3 4/7"). Rules on your computer, no AI; nothing is sent when one opens. Questions, "remind me ..."
  and anything about health, money or passwords never open one.
- **Closes** when you say it's done ("I sent the draft"), when the session ends or the deadline is done, when you tap
  **Done** or **Drop**, or by itself after 7 days nobody touched it (`memory.thread_days`).
- **`/threads`** lists what's open, newest first, with **Done** and **Drop**, and what closed in the last 48 hours with
  **Undo**. `/threads done 2`, `/threads drop 2`, `/threads all`.
- **"Did I finish that thing?"** looks at threads from the last 48 hours (narrowed by any other words: "that wind
  tunnel thing"); "did *you* finish that thing?" also looks at your AI requests. One match: what it is, where you said
  it and how it stands. Two or more: it asks once, with a button each. "That thing is done" closes it, with **Undo**.
  "What was that thing?" works too.
- **It never acts on a guess.** A "that thing" found this way is only read or asked about; nothing is sent, moved or
  deleted for it without your OK (the AI is told the same).
- **Your memory, asked plainly.** "When did I last talk to Prof Ortiz?" answers from meetings in your project notes,
  daily notes, gists and threads; "what was I doing last Thursday?" (also "yesterday", "on 20 Oct") lists that day's
  daily note, meetings, calls, requests and threads. `/memory` lists and searches everything remembered
  ([privacy.md](privacy.md#the-memory-ledger)).

Threads are kept in the encrypted memory ledger; `memory.threads` off opens no more.

## Other core commands

| Command | Does |
|---|---|
| `/aboutme` | the In-brief part of your profile (what goes along with every AI request) and a link to edit it on your computer ([teaching-kurooto.md](teaching-kurooto.md)) |
| `/persona`, `/persona tone: plain, no pep talk`, `/persona clear` | your persona card: how Kurooto talks to you ([teaching-kurooto.md](teaching-kurooto.md#your-persona-card)) |
| `/health`, `/health now` | what isn't working, with Fix buttons; `now` also checks online services ([messages-it-sends.md](messages-it-sends.md#kurooto-keeps-itself-working)) |
| `/calm`, `/why` | the daily message limit and what's turned down; why the last message came ([messages-it-sends.md](messages-it-sends.md)) |
| `/forget 7d`, `/forget 2w`, `/forget all` | forget what Kurooto kept of the last 7 days (two weeks, or everything, after a confirm button) now; `/forget` alone says how long things are kept ([privacy.md](privacy.md#how-long-its-kept)) |
| `/gists`, `/gists <words>` | the one-line gists your conversations settled into as their words faded ([privacy.md](privacy.md#gists-what-settles)) |
| `/threads`, `/threads done 2` | what you're in the middle of, with Done, Drop and Undo ([above](#open-threads-and-that-thing)) |
| `/memory`, `/memory <words>`, `/memory forget 3`, `/memory export` | everything remembered (encrypted on this computer), searchable, with Forget; export writes a note ([privacy.md](privacy.md#the-memory-ledger)) |
| `/sync` | with Notes sync off: sync everything that's on. With Notes sync on, `/sync` syncs your notes and `/sync all` everything |

## Renaming your assistant

Settings → you → `you.assistant_name`, or the setup page's first step. The new name is used everywhere at once, and the
Telegram bot is renamed too; it says so once ("I'm Nova now."). Telegram limits how often a bot can be renamed: if it
refuses, the message says the name shows in Kurooto's messages, the app and the dashboard anyway. The bot's
@username can't change (that's set in @BotFather).

## From a terminal

`kurooto ask "what's due this week?"` handles plain English as on Telegram: quick things answer at once, bigger ones go
to your AI and the answer prints in the terminal, not on Telegram, with the run receipt as its last line. `kurooto ask` alone opens a prompt for one request
after another. More, including `kurooto notify` and `kurooto ask-me` for your own scripts: [add-ons.md](add-ons.md).
