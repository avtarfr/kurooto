# Talking to Kurooto

You talk to Kurooto through your own Telegram bot: plain sentences, `/commands`, voice messages, photos and files.
Quick requests ("remind me at 9 to call mum") are done at once on your computer; anything else goes to your AI, which
answers as a reply. The same requests work in the dashboard's Today page and Ctrl+K box ([dashboard.md](dashboard.md)),
on a phone call ([calls.md](calls.md)) and in a terminal (`kurooto ask`).

- [Your bot](#your-bot)
- [What happens to a message](#what-happens-to-a-message)
- [Chat with your AI](#chat-with-your-ai)
- [Questions and approvals](#questions-and-approvals)
- [Buttons](#buttons)
- [Status, pause, hold and focus](#status-pause-hold-and-focus)
- [Voice notes](#voice-notes)
- [Sending files and photos](#sending-files-and-photos)
- [Getting files from Kurooto](#getting-files-from-kurooto)
- [Other core commands](#other-core-commands)
- [Renaming your assistant](#renaming-your-assistant)
- [From a terminal](#from-a-terminal)

## Your bot

**What it does.** Your own bot, made with @BotFather during setup ([getting-started.md](getting-started.md#6-telegram-connect-your-bot)).
It serves only the Telegram account that tapped the one-time pairing link, and only in a private chat; messages from
anyone else, and from groups, are ignored.

**The "/" menu.** Typing `/` in the chat lists `/help`, the commands of the features you have on, `/q`, `/jobs`,
`/aboutme`, `/calm`, `/why` (and `/sync` when Notes sync is off), then your skills. A skill with a dash in its name shows
with `_`: `/term_setup` runs term-setup. Telegram shows at most 100. Kurooto updates the menu within a minute of a
feature going on or off, and looks for new skills every 15 minutes.

**`/help`** (and `/start`) lists everything that works right now: the commands of each feature you have on, grouped
by feature, Kurooto's own (`/q`, `/aboutme`, `/health`, `/calm`, `/why`, `/jobs`, `/sync`), every request it
understands at once in plain words, and the features that are off. It ends with a link to this wiki. **`/help <word>`**
searches everything, on or off: `/help call` shows Phone calls, its commands and how to turn it on. If Chat is off it
says free text isn't sent to an AI. The full list is in [commands.md](commands.md).

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
6. **A plain-English request Kurooto understands instantly** ("remind me in 20 minutes to take the pasta off", "what's
   due?", "no calls for 2 hours"). These run on your computer with no AI. Long messages (over 300 characters), and
   messages with several requests in one ("..., also ...", "... and then ...", two sentences), always go to the AI so it
   reads the whole thing. A question ("what...?", "when...?") only matches requests that answer questions. A phrasing
   you taught with the Wrong button goes first ([teaching-kurooto.md](teaching-kurooto.md)).
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

**Memory of the conversation.** Chat remembers your last few exchanges (up to 6, each cut to 1,200 characters) as long
as the last one was within 2 hours; after 2 hours of quiet a new message starts fresh. Requests from a terminal start
fresh every time. Background requests (digests, the look back) never become part of the chat.

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
then nothing happens ("That question expired"). Answered and expired questions are forgotten after 30 days
(`ask.keep_days`).

**What leaves your computer:** the question goes wherever Kurooto reaches you (Telegram, the phone app, the desktop);
open questions are part of the brief your call line keeps for calls while the computer is off.

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

## Other core commands

| Command | Does |
|---|---|
| `/aboutme` | the In-brief part of your profile (what goes along with every AI request) and a link to edit it on your computer ([teaching-kurooto.md](teaching-kurooto.md)) |
| `/health`, `/health now` | what isn't working, with Fix buttons; `now` also checks online services ([messages-it-sends.md](messages-it-sends.md#kurooto-keeps-itself-working)) |
| `/calm`, `/why` | the daily message limit and what's turned down; why the last message came ([messages-it-sends.md](messages-it-sends.md)) |
| `/sync` | with Notes sync off: sync everything that's on. With Notes sync on, `/sync` syncs your notes and `/sync all` everything |

## Renaming your assistant

Settings → you → `you.assistant_name`, or the setup page's first step. The new name is used everywhere at once, and the
Telegram bot is renamed too; it says so once ("I'm Nova now."). Telegram limits how often a bot can be renamed: if it
refuses, the message says the name shows in Kurooto's messages, the app and the dashboard anyway. The bot's
@username can't change (that's set in @BotFather).

## From a terminal

`kurooto ask "what's due this week?"` handles plain English as on Telegram: quick things answer at once, bigger ones go
to your AI and the answer prints in the terminal, not on Telegram. `kurooto ask` alone opens a prompt for one request
after another. More, including `kurooto notify` and `kurooto ask-me` for your own scripts: [add-ons.md](add-ons.md).
