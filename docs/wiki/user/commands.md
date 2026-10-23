# Commands

Everything you can type, in one place: Telegram commands, the plain-English requests Kurooto understands instantly,
the `kurooto` terminal commands, and the dashboard's keyboard shortcuts. Each row links to the page that explains it.

- On Telegram, typing `/` shows a menu of the commands of the features you have on, plus your skills. `/help` lists
  the same with a line each.
- A command of a feature that's off answers "X is off: Features → X → Turn on" and does nothing else.
- Commands work in any case (`/Remind` is `/remind`), and `/remind@yourbot` works in a group-style chat too.
- Most commands take the rest of the line as their argument; `/journal` followed by a new line works as well.
- The same plain words also work in the dashboard's Today box and Ctrl+K, in `kurooto ask`, and many of them on a call.

## Telegram commands

### Always there

These belong to Kurooto itself and answer whichever features are on.

| Command | What it does | More |
|---|---|---|
| `/help`, `/start` | everything I can do: the commands and plain-word requests of the features you have on, the features that are off, and a link to this wiki; `/help <word>` finds a command or feature, on or off | [Talking to Kurooto](talking-to-kurooto.md) |
| `/status` | what's going on: calls held or allowed, focus, what's coming up, open questions, today's check-ins, what's due soon, the alarm, recent AI requests, the features that are on (answers even with Telegram off, from a terminal) | [Talking to Kurooto](talking-to-kurooto.md) |
| `/q` (or `/questions`) | the open questions Kurooto asked you, each with its buttons; reply to one to answer it | [Talking to Kurooto](talking-to-kurooto.md#questions-and-approvals) |
| `/jobs` | what the AI is working on and what waits, with Cancel buttons, and the last few that finished; `/jobs cancel <id>` or `/jobs cancel all` | [AI brains](ai-brains.md) |
| `/aboutme` | the In-brief part of your profile and a link to edit it | [Teaching Kurooto](teaching-kurooto.md) |
| `/health` | what isn't working, with Fix buttons; `/health now` also checks online services | [Messages it sends](messages-it-sends.md) |
| `/calm` | messages that came by themselves today, the limit, what waits for the evening and what you turned down; `/calm 8` (messages a day), `/calm calls 2`, `/calm evening 21:00`, `/calm off`, `/calm on` | [Messages it sends](messages-it-sends.md) |
| `/why` | why the last message that came by itself came | [Messages it sends](messages-it-sends.md) |
| `/sync` | with Notes sync off: sync everything that's on (with it on, see Notes sync below) | [Notes](notes-and-concept-graph.md) |

### Telegram feature

| Command | What it does |
|---|---|
| `/pause`, `/pause 2h`, `/pause until 18:00` | pause Kurooto; what you send meanwhile is kept and done when it resumes; reminders wait too |
| `/resume` | wake it up after `/pause` |
| `/hold 18:00`, `/hold 2h` | no calls until then (default 1 hour); messages still come |
| `/calls` | allow calls again (night hours and other holds still apply) |
| `/focus 2h`, `/focus until 18:00`, `/focus off` (or `stop`, `end`), `/focus` | do-not-disturb: messages that can wait are held until it ends (approvals, calls you asked for and urgent ones still come); `/focus` alone says whether it's on |

More: [Talking to Kurooto](talking-to-kurooto.md).

### Chat with your AI

| Command | What it does |
|---|---|
| `/new`, `/clear` | start a fresh conversation (forget the recent chat turns) |
| `/brain` | which AI answers, and whether it's working |
| `/usage`, `/usage 14` | AI requests per day (7 days by default, up to 60), limits hit, today's limits and when they reset |

More: [AI brains](ai-brains.md), [Talking to Kurooto](talking-to-kurooto.md#chat-with-your-ai).

### Reminders, deadlines and planning

| Command | What it does | Feature |
|---|---|---|
| `/remind 21:30 call mum`, `/remind tomorrow 7am gym`, `/remind in 20m tea`, `/remind fri 17:00 hand in form`, `/remind 2026-11-02 14:00 dentist` | a reminder (a bare number is the hour: `9` is the next 9:00; minutes need their unit: `20m`) | Reminders |
| `/reminders` | your upcoming reminders, each with a Cancel button | Reminders |
| `/deadlines` | what's due in the next two weeks | Deadlines |
| `/due fri 17:00 essay draft`, `/due 2026-11-02 lab report` | add a deadline | Deadlines |
| `/exam` | exam mode: quizzes and exams in the next two weeks, and what's due to practise | Deadlines |
| `/recurring`, `/recurring add la quiz every 2 weeks thu 10:00`, `/recurring remove la quiz` | repeating quizzes and tests | Deadlines |
| `/ignore drama club`, `/ignored`, `/unignore drama club` | topics you don't care about | Deadlines |
| `/startby`, `/startby exam la 2-3 days`, `/startby exam` | when to start each deadline; set how long a subject's exams take | Start-by dates |
| `/checkins` | today's check-ins with +30 min and Skip buttons | Check-ins |
| `/checkin evening 21:30`, `/checkin midday 13:00`, `/checkin night skip`, `/checkin night morning` | move or skip one check-in today (`morning`: to your wake-up call) | Check-ins |
| `/week` | the week in numbers | Weekly summary |
| `/quests`, `/quests stop` | your first-week quests | First-week quests |

More: [Reminders and deadlines](reminders-and-deadlines.md), [Check-ins and journal](check-ins-and-journal.md).

### Phone calls and the alarm

| Command | What it does | Feature |
|---|---|---|
| `/call` | a link to call Kurooto now, from any phone or browser (works for 2 hours) | Phone calls |
| `/phone` | a link to pair a phone so calls ring it (valid 15 minutes) | Phone calls |
| `/phones` | your paired phones | Phone calls |
| `/unpair <id>` | remove a paired phone | Phone calls |
| `/lessons`, `/lessons forget 2`, `/lessons clear` | what calls have learned from looking back; forget one, or all | Phone calls |
| `/alarm 6:45`, `/alarm tomorrow 7`, `/alarm off`, `/alarm skip friday`, `/alarm skip tomorrow`, `/alarm daily 7:00`, `/alarm daily off`, `/alarm` | the wake-up call; `/alarm` alone shows what's set | Morning alarm |

More: [Phone calls](calls.md), [Phone app](phone-app.md).

### Classes, study and exams

| Command | What it does | Feature |
|---|---|---|
| `/subject add Linear Algebra (la, linalg)`, `/subject`, `/subject remove la` | add, list or remove subjects | Subjects and timetable |
| `/class mon 09:00-09:55 la` · `/class remove mon 09:00` | add a class to your timetable, or remove one | Subjects and timetable |
| `/classes`, `/classes today` | your timetable | Subjects and timetable |
| `/skip la` (or `/skip la, stats`), `/attend la` | you're not going to a class today (no after-class question, calls allowed then); `/attend` undoes it | Subjects and timetable |
| `/term`, `/term ends 2026-12-04`, `/term exams 2026-12-07 to 2026-12-18`, `/term note terms/2026-autumn`, `/term note off`, `/term clear` | term dates, or a term note to read them from | Subjects and timetable |
| `/classpack`, `/classpack export`, `/classpack export from terms/section-b`, `/classpack set electives ml, topology`, `/classpack set batch B`, `/classpack set la quiz off`, `/classpack set la reset`, `/classpack remove`, `/classpack undo` | share your section's setup, or change or remove an imported one | Class packs |
| `/doubt la why does the rank not change?`, `/doubts`, `/doubts la` | doubts for the next class | Doubt queue |
| `/quiz`, `/quiz la`, `/quiz la call`, `/quiz la here`, `/quiz at 21:00 la`, `/quiz la tomorrow 8pm` | practice questions from your notes | Quiz |
| `/quizstatus` | what's due to practise, per subject | Quiz |
| `/examseason` | exam season: dates, exams and parts (tap a part to switch it) | Exam season (optional) |
| `/hint la` (with a photo, or the problem typed after it) | one hint at a time | Hint ladder |
| `/pack linear algebra midterm` | a revision PDF from your notes | Skills |
| `/studypack <subject> [what it's for]`, e.g. `/studypack la quiz on eigenvalues`; `/studypack prompt` (edit the prompt), `/studypack prompt reset` | a zip of a subject's materials, with a prompt for another AI sent as its own message; a topic narrows it, class material first; over 50 MB comes as a temporary Drive link | Skills |
| `/study`, `/study week`, `/study la 50`, `/study stop` | study time; start or stop a session away from the computer | Study tracker |
| `/studied 2h linear algebra` | log study time done away from the computer | Study tracker |
| `/books`, `/books read now`, `/books read force` (also on battery), `/books stop`, `/books folder la`, `/books mix la book 30 classroom 30 own 40`, `/books mix la prefer own book classroom`, `/books mix la reset`, `/books setup` | your books and how far reading got; the source mix | Books and PDFs |
| `/handwritten`, `/handwritten status`, `/handwritten retry` | write out waiting handwritten pages now | Handwritten notes |
| `/handwritten link`, `/handwritten undo` | link the notes written out before to their lecture, course page and concepts / take back the last linking | Handwritten notes |

More: [Classes and timetable](classes-and-timetable.md), [Quiz and exams](quiz-and-exams.md),
[Books and study](books-and-study.md).

### Notes, skills and research

| Command | What it does | Feature |
|---|---|---|
| `/note buy graph paper` | save a quick note to your inbox (a photo with `/note` as caption is linked) | Quick notes and prompts |
| `/prompts`, `/prompt <name>`, `/prompt save <name>` | your prompt library | Quick notes and prompts |
| `/notes what is a compact space` | search your notes by meaning | Notes brain |
| `/timeline research/reading-group` | a note's dated log | Notes brain |
| `/sync`, `/sync all` | sync your notes now; `all`: everything that syncs | Notes sync |
| `/graph`, `/graph now`, `/graph stop` | the concept graph's state; start or stop its work | Concept graph |
| `/skills`, `/skills journal`, `/skills copy journal` | the skills you can run; show one; make your own copy to edit | Skills |
| `/newskill <what it should do>` | the AI writes a new skill (Save / Discard) | Skills |
| `/every monday 9:00 /journal plan my week`, `/every weekdays 7:30 /morning-prep`, `/every daily 21:00 how did today go?` | run a skill, a command or a request on a schedule (days: daily, weekdays, weekends, a day, or several like `mon,thu`; at most 30) | Skills |
| `/routines` | what runs on a schedule, with Cancel buttons | Skills |
| `/papers` | the new-papers digest now | Research |
| `/feeds` | your research sources | Research |
| `/topics add …`, `/topics remove …` | quick keywords searched across arXiv | Research |
| `/repos`, `/repos add ~/code/my-model`, `/repos add ~/code/model_v2 as Climate model`, `/repos remove …` | repositories for project logs | Research |

More: [Notes and the concept graph](notes-and-concept-graph.md), [Skills and routines](skills-and-routines.md),
[Research](research.md).

### Skills you run as commands

With Skills (and Chat) on, these send ready-made instructions to your AI. Type the command and what it's about; files
sent with it (as the caption) go along; reply to the answer to carry on. In the `/` menu a dash shows as `_`
(`/study_log`). See [Skills and routines](skills-and-routines.md).

| Command | What it does |
|---|---|
| `/journal <your day>` | your words into today's daily note, linked to the notes you mention |
| `/study-log <classes and notes>` | one lecture note per class from slides and your notes |
| `/add-to-notes <link or files>` | file anything where it belongs, as a source note |
| `/assignment <which one>` | worked solutions in your course's notation, with a confidence for each |
| `/connect-notes [topic]` | real connections between notes, added as links with reasons |
| `/term-setup <subjects, plans>` | set up a term: key dates, course pages, a week-by-week plan |
| `/exam-prep <subject>` | bring a subject's exam prep up to date from your notes, Classroom and books |
| `/goodnight <wake-up time>` | sets the alarm and notes anything for tomorrow |
| `/morning [answers]` | today's plan, time-blocked, with your top 3 |
| `/morning-prep` | drafts today's plan before you wake |
| `/revision-pack <subject>` | the same as `/pack` |
| `/classroom-digest`, `/mail-digest` | the skills Classroom → notes and the mail digest run by themselves |
| your own skills | `/newskill` makes them; they're listed in `/skills` |

### Google

| Command | What it does | Feature |
|---|---|---|
| `/classroom` | check Google Classroom now | Google |
| `/draft someone@example.com ask for an extension` | an email draft in Gmail, written by the AI (never sent); `/draft to | subject | text` for your own words; only with `google.gmail_drafts` on | Google |
| `/google`, `/google use mail school`, `/google forget school` | your Google accounts and which feature uses which (features: `classroom`, `drafts`, `mail`, `email`, `calendar`, `plan`, `drive`, `classroom_notes`) | Google |
| `/classnotes`, `/classnotes courses`, `/classnotes skip chess`, `/classnotes unskip chess` | file new Classroom posts into your notes now | Classroom → notes |
| `/mail`, `/mail read @school.example`, `/mail unread …`, `/mail never …`, `/mail unnever …`, `/mail query …`, `/mail query off`, `/mail rules`, `/mail confidential` | your mail digest now, and what it may read | Mail digest |
| `/blocks`, `/blocks add 14:00-15:30 problem set`, `/blocks clear` | today's planned time blocks | Agent plan calendar |
| `/today` | today's calendar | Calendar |
| `/cal`, `/cal classes Timetable`, `/cal classes none` | the next 7 days; which calendars hold classes | Calendar |

More: [Google](google.md), [Classes and timetable](classes-and-timetable.md#calendar).

### Kurooto itself

| Command | What it does | Feature |
|---|---|---|
| `/remember I hate calls before 8` | keep how you like to be helped; `/remember` alone shows what it keeps | Remember |
| `/observe whether I sleep better for 2 weeks` | watch something before deciding | Nightly look back |
| `/observing` | what's being watched (Stop and +7 days buttons) | Nightly look back |
| `/lookback`, `/lookback now` | the last nightly look back; run one now | Nightly look back |
| `/history lab report`, `/history 7d lab report` | search past requests, calls and chats (the last 7 days) | Learns from its own work (optional) |
| `/learned` | what it learned lately, each with Undo | Learns from its own work (optional) |
| `/wrong`, `/wrong <what you meant>`, `/wrong ai` | my last reply was wrong: keep it as a case, or teach me | Wrong button and test cases |
| `/cases`, `/cases review` | test cases and the phrasings you taught (Unlearn buttons) | Wrong button and test cases |
| `/backup`, `/backups` | make a backup now; list them | Backups |
| `/profile`, `/profile save` | what your saved profile holds; save it now | Profile sync |
| `/space`, `/space clean` | what Kurooto takes and what can go; clean it | Space keeper |
| `/models` | the local models and whether they're running | Local AI models |
| `/addons` | your add-ons: what loaded and what didn't | Your add-ons |

More: [Teaching Kurooto](teaching-kurooto.md), [Updates and backups](updates-and-backups.md),
[Your computer](your-computer.md), [Add-ons and scripts](add-ons.md).

## Plain-English requests understood instantly

These are answered at once on your computer, without asking an AI, so they work even when the AI is out of free
requests. Anything else goes to your AI (with Chat on). Long messages, or several requests in one message, always go to
the AI. A request that asks a question only matches the requests below that answer questions. Times about the past
("since I didn't wake up at 12") are never used as the time of a call or reminder.

| You say | What happens | Feature |
|---|---|---|
| "remind me at 9 to call mum", "remind me in 20 minutes to take the pasta off", "remind me tomorrow at 7am to go to the gym", "remind me tonight to pack" (21:00), "remind me tomorrow to …" (09:00) | a reminder for today or tomorrow; for another day use `/remind fri 17:00 …` | Reminders |
| "what's due?", "anything due?", "show my deadlines" (two weeks), "what's due this week?" (7 days), "what's due soon?" (`deadlines.plan_h`, 3 days) | the deadline list | Deadlines |
| "add a deadline: essay draft due friday 5pm", "I have a lab report due fri 17:00" | a new deadline | Deadlines |
| "I don't care about the drama club", "stop telling me about …" | a topic on your not-interested list | Deadlines |
| "linear algebra has a quiz every thursday" | a recurring quiz | Deadlines |
| "when's my next exam?", "exam mode" | exam mode and your next quiz or exam | Deadlines |
| "when should I start the lab report?" | its start-by date | Start-by dates |
| "any crunch weeks coming?" | weeks with more work than free time | Start-by dates |
| "move tonight's check-in to 21:30", "push the check-in by 30 min", "skip the night check-in", "skip Friday's check-in", "move tomorrow's check-in to 9" | move or skip a check-in (today, tomorrow, the day after or a weekday; other days go to the AI) | Check-ins |
| "skipping LA today", "not going to LA on Friday", "skipping stats tomorrow", "missing topology" | mark a class you're not going to (today, tomorrow, the day after or a weekday; a question is never taken as a skip) | Subjects and timetable |
| "I have a doubt about eigenvalues", "doubt: …" | a doubt for the next class (short ones; use `/doubt` for long ones) | Doubt queue |
| "show my doubts" | your open doubts | Doubt queue |
| "quiz me", "quiz me on topology", "test me on LA", "quiz me by call", "call me for a quiz", "quiz me at 9 tonight", "quiz me here" | a practice session | Quiz |
| "exam season?" | what exam season does now | Exam season |
| "starting linear algebra for 50 min" | a study session away from the computer | Study tracker |
| "done studying" | end the session | Study tracker |
| "studied stats for an hour" | log study time | Study tracker |
| "how much did I study today?" | study time | Study tracker |
| "what's on today?", "what's on tomorrow?", "anything planned tomorrow?" | your calendar | Calendar |
| "call me at 5 about the laundry", "call me in 20 minutes about the essay" | a call later ("at 5" in the afternoon means 17:00) | Phone calls |
| "call me now", "ring me about the essay" | a call right away, even during a class or a `/hold` (you asked for it) | Phone calls |
| "call me" with only a past time in it | asks when instead of booking | Phone calls |
| "cancel that call", "cancel the 12:00 call" | cancels a booked call, or lists them with Cancel buttons | Phone calls |
| "wake me at 6:45", "no alarm tomorrow", "cancel Friday's alarm", "cancel my alarm", "turn my daily alarm off" | the wake-up alarm | Morning alarm |
| "do I have any alarms?", "when is my alarm?" | the alarm that's set | Morning alarm |
| "I'm awake", "I just woke up", "I'm up" | the morning call now, planned from the current time (with Morning alarm on) | Morning alarm |
| "no calls for 2 hours", "don't call me until 6", "hold calls until 18:00" | no calls until then (a named other day goes to the AI) | Telegram |
| "calls are fine again" | allow calls again | Telegram |
| "focus for 2 hours", "do not disturb until 18:00", "focus off" | do-not-disturb on or off | Telegram |
| "remember that I like a plan before 9", "keep in mind that …" | a line for your how-to-help-me note | Remember |
| "observe whether I study better before noon", "keep an eye on ..." | something for the look back to watch | Nightly look back |
| "every friday at 6pm send me a summary of my week" | a routine | Skills |
| a link on its own | filed into your notes (the `/add-to-notes` skill) | Skills |
| "sync everything", "sync it all", "sync all now" | every sync that's on, one after another | always there |

Phrasings you taught with the Wrong button are matched first, as a whole message. See
[Teaching Kurooto](teaching-kurooto.md#wrong-button-and-test-cases).

**Effort prefixes.** Start a message for the AI with `low:`, `medium:` or `high:` to choose how hard it thinks. See
[AI brains](ai-brains.md).

## Terminal commands (`kurooto ...`)

Open a terminal (PowerShell on Windows, Terminal on a Mac) and type these. You never need them for everyday use; they
help with setup, repairs and scripts. `kurooto <command> --help` shows each one's options.

### Running Kurooto

| Command | What it does |
|---|---|
| `kurooto on` | turn it back on (and open the dashboard) |
| `kurooto off`, `kurooto off --keep-calls` | turn it off completely: it doesn't start at sign-in until `kurooto on`; `--keep-calls` lets your call line keep placing scheduled calls (the alarm) |
| `kurooto start` | start it in the background now |
| `kurooto stop` | stop it for now (it starts again at sign-in) |
| `kurooto pause [2h \| 18:00]`, `kurooto resume` | pause it (the same as `/pause`), and wake it |
| `kurooto open` | open the setup page or dashboard |
| `kurooto autostart on \| off \| status \| boot \| login` | start at sign-in or not; `boot` starts it before anyone logs in (Linux) |
| `kurooto run`, `kurooto supervise` | run it in this window; run it and restart it if it crashes (for troubleshooting) |

### Checking and fixing

| Command | What it does |
|---|---|
| `kurooto doctor` | check that everything is in place; the exit code is the number of problems |
| `kurooto doctor --fix <id>` | run the fix a problem offers |
| `kurooto doctor --bundle` | a diagnostics zip with secrets, names and addresses blanked out, to send to someone helping you |
| `kurooto doctor --json` | the same checks for programs |
| `kurooto top`, `kurooto top --once` | a status board in the terminal (q quits) |
| `kurooto logs`, `kurooto logs -f`, `kurooto logs -n 200` | the end of Kurooto's log; `-f` keeps following it |
| `kurooto paths` | where settings, data, state, logs, cache and the program live |
| `kurooto usage [days]` | AI requests per day, and agy's own count |
| `kurooto jobs`, `kurooto jobs --cancel <id \| all>` | what the AI is working on; cancel |
| `kurooto hardware`, `--profile <name>`, `--add <model>`, `--remove <model>`, `--add-prereq <id>`, `--remove-prereq <id>`, `--install` | what this computer suits, and going past it |
| `kurooto space`, `kurooto space --clean` | what Kurooto takes and what can go |
| `kurooto selftest` | check that this version starts |
| `kurooto --version` | the version you have |

### Updates, backups and moving

| Command | What it does |
|---|---|
| `kurooto update`, `kurooto update --now` | check for an update; install it now instead of at night |
| `kurooto backup`, `kurooto backup --to <folder>` | make a backup now |
| `kurooto restore <zip>` (`--yes`, `--no-notes`, `--no-start`) | put a backup back |
| `kurooto profile status \| save \| restore` (`save --replace`; `restore --repo owner/name`, `--yes`, `--no-start`) | your setup, encrypted in your private repository |
| `kurooto sync`, `kurooto sync --no-wait`, `kurooto sync --status` | sync everything that's on |
| `kurooto rotate`, `kurooto rotate --yes` | new keys for your call line (a lost phone, keys that got out) |
| `kurooto uninstall`, `--keep-data`, `--revoke` | remove Kurooto; `--revoke` first takes back what it set up on your accounts |

### Talking to Kurooto from a terminal or script

| Command | What it does |
|---|---|
| `kurooto ask "what's due this week?"`, `kurooto ask` | plain English as on Telegram; alone, a prompt for one request after another (`!command` runs a shell command there); `--no-wait`, `--job <id>`, `--timeout <minutes>` |
| `kurooto note "an idea"`, `… \| kurooto note --title "output"` | a quick note in your inbox (works with Kurooto stopped) |
| `kurooto notify "text"` (`--title`, `--kind`, `--urgent`, `--button "Label=…"`, `--click URL`, `--print-id`, `--reply-to ID`) | send yourself a message |
| `kurooto send <file>` (`--caption`, `--to drive`) | send yourself a file on Telegram (up to 50 MB), or to your Google Drive |
| `kurooto ask-me "question"` (`--choices "a\|b"`, `--wait`, `--timeout`, `--expires`, `--title`, `--then CMD`, `--pending`, `--id`) | ask yourself something, answered anywhere |
| `kurooto ask-approval "question"` (`--timeout`) | wait for Approve / Deny: exit 0 approved, 1 denied, 2 timeout |
| `kurooto call "reason"` (`--at 17:30`, `--alarm`, `--force`, `--list`, `--cancel <key>`) | ring your phone now or later |
| `kurooto watch -- <command>` (`--lines N`, `--log <project>`) | run a long job; a message when it ends |
| `kurooto runlog start \| metric \| note \| end \| ls` | log experiment runs into your notes |
| `kurooto idle away \| back` | for your idle tool: you've stepped away, or you're back |
| `kurooto mcp` | Kurooto's tools for agent programs (an MCP server) |
| `kurooto export-skills on \| off \| status` (`--to agy,agents,claude`) | your skills as /commands in agent programs |
| `kurooto reserve` | write Markdown copies of alarms, deadlines, calendar and settings for AI programs |
| `kurooto cases [list \| check \| export \| forget <id \| all>]` (`--out`, `--all`) | test cases from the Wrong button |
| `kurooto classpack check <file>`, `export --checked today [--from <note>] [--title …] [--elective …] [--out …]`, `import <file>` | class packs |
| `kurooto term` (`--shell`, `--print`, `--install`, `--default on \| off \| status`, `-e <command>`) | open Kurooto Terminal |

`kurooto ask`, `call`, `send`, `notify`, `ask-me` and `ask-approval` need Kurooto running; they say so (and exit with
2) when it isn't. See [Add-ons and scripts](add-ons.md).

## Dashboard keyboard shortcuts

The dashboard is at `http://127.0.0.1:8770` (`kurooto open`). Shortcuts don't fire while you type in a box, and
inside a terminal the terminal keeps its own keys (Alt+F is a word forward in a shell; Ctrl+K is the shell's). On a
Mac, Option+letter in a text box types a character instead. Full details: [Dashboard](dashboard.md).

| Keys | Does | Where |
|---|---|---|
| **Ctrl+K** (⌘K) | open or close the do-anything line (below) | anywhere outside a terminal |
| ↑ ↓, Tab, Enter, Esc | pick a line, put the highlighted verb in front, run, close | the Ctrl+K line |
| **Alt+T** | Today | |
| **Alt+A** | Activity | |
| **Alt+J** | AI jobs | |
| **Alt+C** | Schedule | |
| **Alt+F** | Features | |
| **Alt+P** | Phone | |
| **Alt+R** | Research | |
| **Alt+Y** | About you | |
| **Alt+S** | Settings | |
| the same Alt key again | close that page | dense layout |
| **Esc** | close the panes menu, then the open page, then give back the panes when one fills the board | dense layout |
| **Alt+1** … **Alt+9** | switch the terminal tabs | |
| **Alt+/** or **/** | find a note on the NOTES map (Enter jumps, Esc closes) | `/` only outside Features and Settings |
| **?** | what the board shows: the core, cells, nerves, notes' colours, and every key | not while typing |
| **/** or **Ctrl+F** | the search box (Ctrl+F again is the browser's own) | Features and Settings |
| **Esc** | empty the search box | Features and Settings |
| **L** | open or fold every corner panel and legend (remembered in this browser) | the board |
| **R** | highlight notes edited in the last day (Recent) | the board, while the NOTES map is showing (not while you type in a box) |
| **Enter** | send | the kurooto chat tab, the Today box |
| **↑ / ↓** | earlier lines you typed | the kurooto chat tab |
| **Ctrl+L** | clear the chat tab | the kurooto chat tab |
| **Ctrl+Enter** (⌘Enter) | save the journal entry | Today page |
| click a pane's name, or double-click its border | fill the board with it; again (or Esc) to go back | dense layout |

The kurooto chat tab also has its own words: `help`, `check`, `jobs` and `clear`.

### The Ctrl+K line and the Today box

| Type | Does | Example |
|---|---|---|
| `ask …`, or anything that isn't a verb | goes to Kurooto as if typed on Telegram | `what's due this week?` |
| `journal …` or `j …` | a line in today's journal | `j finished the lab report` |
| `note …` or `. …` | a timed line in today's inbox note (one note per day, unlike `/note`, which makes a new note each time) | `. look up Sylow theorems` |
| `remind <when> <what>` or `! <when> <what>` | a reminder; the time comes first (`18:30`, `6pm`, `in 20m`, `in 2 hours`, `tomorrow 9am`, `friday 9:00`) | `! 18:30 call mum` |
| `due <what> <when>` | a deadline; the time comes last (`fri 17:00`, `tomorrow`, `2026-11-02 17:00`, `in 3 days`) | `due essay draft fri 17:00` |
| `alarm <time>`, `alarm skip [day]`, `alarm off`, `alarm daily <time>`, `alarm daily off` | the wake-up alarm | `alarm 7:30` |
| `find <name>` | a note on the NOTES map | `find eigenvalues` |
| `open <page>` | a page: today, activity, jobs, schedule, features, phone, research, about, settings | `open set` |

The Today box takes the same `j`, `.` and `!` shortcuts. A bare verb is completed first (`re` then Enter gives
`remind `).

### `kurooto top`

| Key | Does |
|---|---|
| `q` (or Esc, Ctrl+C) | quit |
| `r` | refresh now |
| `c` / `m` | sort processes by cpu / memory |

`kurooto top --once` prints one screen; `NO_COLOR=1` turns colours off.

## How this list was checked

Every Telegram command above comes from the code's command list (each feature's `commands()` and Kurooto's own
`/help`, `/start`, `/q`, `/aboutme`, `/health`, `/calm`, `/why`, `/jobs`), every plain-English row from each feature's
instant requests, and every terminal command from `kurooto --help`.
