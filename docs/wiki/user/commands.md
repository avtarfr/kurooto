# Commands

Everything you can type, in one place: Telegram commands, the plain-English requests Kurooto understands instantly,
the `kurooto` terminal commands, and the dashboard's keyboard shortcuts. Each row links to the page that explains it.

- On Telegram, typing `/` shows a menu of the commands of the features you have on, plus your skills. `/help` lists
  the same as an index, one line per group with its commands; `/help <group>` (`/help calls`) shows one group in
  full, with a line each and what you can just say, `/help all` every group.
- A command of a feature that's off answers "X is off: Features → X → Turn on" and does nothing else.
- Commands work in any case (`/Remind` is `/remind`), and `/remind@yourbot` works in a group-style chat too.
- Most commands take the rest of the line as their argument; `/journal` followed by a new line works as well.
- The same plain words also work in the dashboard's Today box and Ctrl+K, in `kurooto ask`, and many of them on a call.
- Commands and plain words work in the phone app's chat (Android and iPhone) exactly as on Telegram
  ([Phone app](phone-app.md#chat-with-kurooto-in-the-app)). Without Telegram, `/pause`, `/resume`, `/status`, `/hold`,
  `/calls` and `/focus` answer there too, and `/help` lists them.

## Telegram commands

### Always there

These belong to Kurooto itself and answer whichever features are on.

| Command | What it does | More |
|---|---|---|
| `/dream` | what Kurooto did since the last morning message, and the loose ends; `/dream policy`: what it tunes while you sleep (when messages reach you, effort, which AI first, Start-by sizes) and what it changed; `/dream proposal`: a fix for a skill, waiting for your OK (a proposal: Apply, Change, Discard); `/dream check`: duplicates and lines that disagree in what it remembers, now (Keep A / Keep B / Both true) | Dreaming |
| `/inferred` · `/inferred undo <id>` | what was set up from what you said (a project, a meeting, a class, a recurring quiz, a commitment, a short name), and taking one back | Kurooto itself |
| `/help`, `/start` | everything I can do, as an index: one line per group with its commands and its page in this wiki, then the features that are off. `/help <group>` (talking, voice, face, reminders, classes, study, quiz, calls, checkins, notes, projects, skills, research, google, teaching, privacy, settings) shows one group in full, `/help all` every group, `/help <word>` finds a command or feature, on or off | [Talking to Kurooto](talking-to-kurooto.md) |
| `/status` | what's going on: calls held or allowed, focus, what's coming up, open questions, today's check-ins, what's due soon, the alarm, recent AI requests, the features that are on (answers even with Telegram off, from a terminal) | [Talking to Kurooto](talking-to-kurooto.md) |
| `/q` (or `/questions`) | the open questions Kurooto asked you, each with its buttons; reply to one to answer it | [Talking to Kurooto](talking-to-kurooto.md#questions-and-approvals) |
| `/jobs` | what the AI is working on and what waits, with Cancel buttons, and the last few that finished; `/jobs cancel <id>` or `/jobs cancel all` | [AI models](ai-brains.md) |
| `/proposals` · `/proposals 2` · `/proposals apply\|discard\|undo <id>` | the AI's changes to your files waiting for your OK (Apply, Change, Discard), and what you applied lately (Undo); a number shows one with its diff | [Projects and proposals](proposals.md) |
| `/aboutme` | the In-brief part of your profile and a link to edit it | [Teaching Kurooto](teaching-kurooto.md) |
| `/persona` · `/persona tone: plain, no pep talk` · `/persona clear [line]` | your persona card (what to call you, tone, length, things to avoid; empty to start): show it, set a line, clear it. Feelings, a backstory or "I missed you" are left out, and it says so | [Teaching Kurooto](teaching-kurooto.md#your-persona-card) |
| `/health` | what isn't working, with Fix buttons; `/health now` also checks online services | [Messages it sends](messages-it-sends.md) |
| `/fixme` · `/fixme <what you see>` | what's wrong and what to do, matched by rules with no AI (so it works when the AI is what broke): each failing check with its troubleshooting row, known issues of your version and a Fix button where there's one; `/fixme the phone doesn't ring` finds the rows for what you see; `/fixme now` checks online too; `/fixme fix <id>` runs a fix (in a terminal); `/fixme ai` has your AI explain the last answer, if it works | [Troubleshooting](troubleshooting.md) |
| `/calm` | messages that came by themselves today, the limit, what waits for the evening and what you turned down; `/calm 8` (messages a day), `/calm calls 2`, `/calm evening 21:00`, `/calm off`, `/calm on` | [Messages it sends](messages-it-sends.md) |
| `/why` | why the last message that came by itself came | [Messages it sends](messages-it-sends.md) |
| `/installed` | what Kurooto installed on this computer, with sizes and what uses each; **Remove…** asks Remove / Keep | [Your computer](your-computer.md#what-kurooto-installed) |
| `/helper` · `/helper on` · `/helper off` · `/helper test` | the offline helper, a small model on this computer for quick decisions and quick answers while the internet is down: how it's doing (its speed test, requests waiting for the connection); `on` sets it up (downloads about 1 GB, then times it), `test` times it again | [Your computer](your-computer.md#the-offline-helper) |
| `/keep` · `/keep 60` · `/keep <feature>` | what you used of each feature that's on (last 30 days, or as many as you say, up to 90) and what it sent by itself; one feature with Keep / Quiet / Off buttons | [Messages it sends](messages-it-sends.md#keep-or-drop-the-features-you-dont-use) |
| `/forget 7d` · `/forget 2w` · `/forget all` | forget what Kurooto kept of your conversations from the last 7 days (12h, 2w...) now, with a count per kind; `all` forgets everything after a button that asks whether the gists go too; `/forget` alone says how long things are kept (`privacy.keep_days`) | [Privacy](privacy.md#how-long-its-kept) |
| `/egress` | where Kurooto's requests went in the last 7 days: each host with the feature, requests and bytes out and in; programs it handed work to (git, agy, Claude Code...); hosts not on the list, and any it blocked | [Privacy](privacy.md#where-requests-go) |
| `/gists` · `/gists <words>` · `/gists forget 3` | the one-line gists conversations settled into as their words faded (what each call or request decided or did), newest first and numbered; with words, the ones that have them all; `forget 3` drops number 3 | [Privacy](privacy.md#gists-what-settles) |
| `/memory` · `/memory <words>` · `/memory forget 3` · `/memory export` | everything Kurooto remembers (gists, threads, how-to-help-me lines, daily notes, project meetings), encrypted on this computer: newest first and numbered; with words, the rows that have them all; `forget 3` forgets one (a how-to-help-me line leaves that note too); `export` writes the gists and threads to a note in your inbox | [Privacy](privacy.md#the-memory-ledger) |
| `/threads` · `/threads done 2` · `/threads drop 2` · `/threads all` | what you're in the middle of (what you said you'd do, in a message or on a call; tasks you started), newest first, with Done and Drop; what closed in the last 48 hours with Undo; `all` shows older closed ones too | [Talking to Kurooto](talking-to-kurooto.md#open-threads-and-that-thing) |
| `/sync` | with Notes sync off: sync everything that's on (with it on, see Notes sync below) | [Notes](notes-and-concept-graph.md) |
| `/run all` · `/run all status` · `/run all stop` | every nightly process that's on, now, one after another: read new books, file the inbox (and read the files in it), the concept graph's queue, look-alike notes (clear ones merged with Undo, the rest asked), then the garden; one progress line with an ETA per step (Telegram edits one message), then a summary. Never two at once; `stop` stops the step running at its next safe point. Off: `runall.on` | [Notes](notes-and-concept-graph.md#run-everything-now) |

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

More: [AI models](ai-brains.md), [Talking to Kurooto](talking-to-kurooto.md#chat-with-your-ai).

### Voice

| Command | What it does |
|---|---|
| `/voice` | what Voice is doing (speaking, listening, why not), and counts of what it heard since it started |
| `/voice mute`, `/voice unmute` | stop and start listening and speaking (it stays muted across restarts) |
| `/voice stop` | stop speaking now |
| `/voice say <text>` | say this aloud now |
| `/voice id` | Voice ID: whether it knows your voice, its grade, thresholds and last test; `/voice id test` (one try at the computer), `/voice id retrain`, `/voice id undo today` or `undo all` (what it learned over time), `/voice id forget` (deletes your voice print, with buttons). Typed only, never by voice |
| `/voice enrol` | start or continue enrolling your voice at the computer (spoken prompts, and the Your voice page `/voice-id`); `/voice enrol again` (start over from nothing; the voice print you have works until the new one is built), `/voice enrol stop`, `/voice enrol keep` (keep what's done for later). Typed only |

More: [Voice](voice.md).

### Face presence

| Command | What it does |
|---|---|
| `/face` | what Face presence is doing (camera on or off, and why), the model's grade, faces seen since start (counts only) |
| `/face pause [1h\|30m\|off]` | keep the camera off for that long (or until `/face pause off`) |
| `/face forget` | delete your face model (asks first: Forget / Keep it) |

More: [Face presence](face.md).

### Reminders, deadlines and planning

| Command | What it does | Feature |
|---|---|---|
| `/remind 21:30 call mum`, `/remind tomorrow 7am gym`, `/remind in 20m tea`, `/remind fri 17:00 hand in form`, `/remind 2026-11-02 14:00 dentist` | a reminder (a bare number is the hour: `9` is the next 9:00; minutes need their unit: `20m`) | Reminders |
| `/reminders` | your upcoming reminders, each with a Cancel button | Reminders |
| `/deadlines` | what's due in the next two weeks | Deadlines |
| `/due fri 17:00 essay draft`, `/due 2026-11-02 lab report` | add a deadline | Deadlines |
| `/exam` | exam mode: quizzes and exams in the next two weeks, and what's due to practise | Deadlines |
| `/recurring`, `/recurring add la quiz every 2 weeks thu 10:00`, `/recurring remove la quiz` | repeating quizzes and tests | Deadlines |
| a photo with `/dates` (or `dates`, `timetable`) as its caption; `/dates` alone | the photo's deadlines, exams and events as Add buttons, a timetable's classes with one button; alone: the newest photo of the last two hours ([Photo to dates](reminders-and-deadlines.md#photo-to-dates)) | Deadlines |
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
| `/alarm 6:45`, `/alarm tomorrow 7`, `/alarm off`, `/alarm off 10:30`, `/alarm off all`, `/alarm skip friday`, `/alarm skip tomorrow`, `/alarm daily 7:00`, `/alarm daily off`, `/alarm` | the wake-up call; `/alarm` alone shows what's set | Morning alarm |

More: [Phone calls](calls.md), [Phone app](phone-app.md).

### Classes, study and exams

| Command | What it does | Feature |
|---|---|---|
| `/subject add Linear Algebra (la, linalg)`, `/subject`, `/subject remove la` | add, list or remove subjects | Subjects and timetable |
| `/subject policy la hints` (`allowed`, `hints`, `off`; `clear`) | a course's AI policy, for Check my draft and the Hint ladder | Subjects and timetable |
| `/class mon 09:00-09:55 la` · `/class remove mon 09:00` | add a class to your timetable, or remove one | Subjects and timetable |
| `/classes`, `/classes today` | your timetable | Subjects and timetable |
| `/busy add gym mon,wed,fri 18:00-19:00`, `/busy`, `/busy skip gym`, `/busy unskip gym`, `/busy calls gym off`, `/busy remove gym` | the regular things that aren't classes (gym, shifts, standups); calls wait for them | Commitments |
| `/hooks`, `/hooks drop gym` | your hook words ("when I say gym, hold calls 90 min"); forget one, with Undo | Commitments |
| `/skip la` (or `/skip la, stats`), `/attend la` | you're not going to a class today (no after-class question, calls allowed then); `/attend` undoes it | Subjects and timetable |
| `/term`, `/term ends 2026-12-04`, `/term exams 2026-12-07 to 2026-12-18`, `/term note terms/2026-autumn`, `/term note off`, `/term clear` | term dates, or a term note to read them from | Subjects and timetable |
| `/classpack`, `/classpack export`, `/classpack export from terms/section-b`, `/classpack set electives ml, topology`, `/classpack set batch B`, `/classpack set la quiz off`, `/classpack set la reset`, `/classpack remove`, `/classpack undo` | share your section's setup, or change or remove an imported one | Class packs |
| `/doubt la why does the rank not change?`, `/doubts`, `/doubts la` | doubts for the next class | Doubt queue |
| `/quiz`, `/quiz la`, `/quiz la call`, `/quiz la here`, `/quiz at 21:00 la`, `/quiz la tomorrow 8pm` | practice questions from your notes | Quiz |
| `/quizstatus` | what's due to practise, per subject | Quiz |
| `/card`, `/cards`, `/cards on`, `/cards off` | a link recall card now (how two of your concepts relate); how they're going; cards by themselves on or off | Quiz |
| `/examseason` | exam season: dates, exams and parts (tap a part to switch it) | Exam season (optional) |
| `/revise`, `/revise la`, `/revise undo` | the revision plan: today's blocks and the next days'; one course's topics, ranked; take back the last Yes / Partly / No | Exam season (optional) |
| `/hint la` (with a photo, or the problem typed after it) | one hint at a time | Hint ladder |
| `/check la` (with a file or photo; or "check this" as its caption) | gaps, unclear steps, errors and missing reasons marked, nothing rewritten | Check my draft (Research add-on) |
| `/pack linear algebra midterm` | a revision PDF from your notes | Skills |
| `/studypack <subject> [what it's for]`, e.g. `/studypack la quiz on eigenvalues`; `/studypack prompt` (edit the prompt), `/studypack prompt reset` | a zip of a subject's materials, with a prompt for another AI sent as its own message; a topic narrows it, class material first; over 50 MB comes as a temporary Drive link | Skills |
| `/study`, `/study week`, `/study la 50`, `/study stop` | study time; start or stop a session away from the computer | Study tracker |
| `/study mode on`, `/study mode off` | the dashboard's [Study mode](dashboard.md#study-mode): notes, the study timer, what's due | Study tracker |
| `/studied 2h linear algebra` | log study time done away from the computer | Study tracker |
| `/books`, `/books read now`, `/books read force` (also on battery), `/books stop`, `/books folder la`, `/books mix la book 30 classroom 30 own 40`, `/books mix la prefer own book classroom`, `/books mix la reset`, `/books setup` | your books and how far reading got; the source mix | Books and PDFs |
| `/handwritten`, `/handwritten status`, `/handwritten retry` | write out waiting handwritten pages now | Handwritten notes |
| `/handwritten link`, `/handwritten undo` | link the notes written out before to their lecture, course page and concepts / take back the last linking | Handwritten notes |
| `/handwritten only <file or course> from <topic>` | add the part of a handwritten note from that topic's heading on, marked where your notes already have it | Handwritten notes |

More: [Classes and timetable](classes-and-timetable.md), [Quiz and exams](quiz-and-exams.md),
[Books and study](books-and-study.md).

### Notes, skills and research

| Command | What it does | Feature |
|---|---|---|
| `/note buy graph paper` | save a quick note to your inbox (a photo with `/note` as caption is linked) | Quick notes and prompts |
| `/prompts`, `/prompt <name>`, `/prompt save <name>` | your prompt library | Quick notes and prompts |
| `/notes what is a compact space` | search your notes by meaning | Notes brain |
| `/notes pdf la`, `/notes pdf template` | a course's notes (course page, lectures, the concept notes they link) as one PDF; your own copy of its LaTeX template | Kurooto (with Subjects) |
| `/timeline research/reading-group` | a note's dated log | Notes brain |
| `/sync`, `/sync all` | sync your notes now; `all`: everything that syncs | Notes sync |
| `/sort`, `/sort now`, `/sort undo` | the notes sorter: what's waiting; sort the scratch folder now; put the last pass back | Notes sorter |
| `/graph`, `/graph now`, `/graph stop` | the concept graph's state; start or stop its work | Concept graph |
| `/graph backfill classroom` | read the Classroom files filed before 0.5.19 into the concept graph, night by night | Concept graph |
| `/graph backfill handwritten` | read the handwritten notes linked before into the concept graph (with `handwritten` in `integrate.sources`); `/handwritten link` links older ones first | Concept graph |
| `/graph backfill all` | both backfills, for every source that's on | Concept graph |
| `/graph same` | concept notes that look like one concept: the clear ones merged now (with Undo), the rest asked with Merge / Keep both / Add alias | Concept graph |
| `/graph garden` | the daily linking pass now (the notes the reading touched, then notes nothing links to; at most `garden_per_day`) | Concept graph |
| `/skills`, `/skills journal`, `/skills copy journal` | the skills you can run; show one; make your own copy to edit | Skills |
| `/newskill <what it should do>` | the AI writes a new skill (Save / Discard) | Skills |
| `/every monday 9:00 /journal plan my week`, `/every weekdays 7:30 /morning-prep`, `/every daily 21:00 how did today go?` | run a skill, a command or a request on a schedule (days: daily, weekdays, weekends, a day, or several like `mon,thu`; at most 30) | Skills |
| `/routines` | what runs on a schedule, with Cancel buttons | Skills |
| `/papers` | the new-papers digest now | Research |
| `/zotero`, `/zotero key <key>`, `/zotero 3`, `/zotero links` | papers into Zotero with one tap (the app, or the web API with your key) | Research |
| `/feeds` | your research sources | Research |
| `/topics add …`, `/topics remove …` | quick keywords searched across arXiv | Research |
| `/repos`, `/repos add ~/code/my-model`, `/repos add ~/code/model_v2 as Climate model`, `/repos remove …` | repositories for project logs | Research |
| `/runs`, `/runs compare 2 1`, `/runs compare` | recent experiment runs; two side by side in the project's notes (alone: the last two) | Research add-on |
| `/latex`, `/latex add ~/papers/thesis [main.tex]`, `/latex build`, `/latex remove …`, `/latex install` | the LaTeX tracker: your documents' last build, attaching one, building now | Research add-on |
| `/project`, `/project add github.com/ana-ruiz/glacier-flow`, `/project add ~/papers/thesis as thesis`, `/project update <name>` | your projects, from every source; one set up from its repository: the note, its commit log, its docs in the concept graph, its milestones as buttons; also "set up my project from github.com/…" | [Research](research.md#set-up-a-project-from-a-repository) |
| `/project help on thesis`, `/project help thesis add footnotes to chapter 2 citing refs.bib`, `/project checks thesis latexmk -pdf main.tex` | let the AI help with one; ask it (the change comes as a proposal); a check run in its scratch folder | Help with your project |

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
| `/mail in`, `/mail in on`, `/mail in off`, `/mail in label Kurooto`, `/mail in label off`, `/mail in from you@school.example`, `/mail in unfrom …` | Email in: mail forwarded to you+kurooto@…, or labelled, filed into your notes with its dates as Add buttons ([google.md](google.md#email-in)) | Mail digest |
| `/blocks`, `/blocks add 14:00-15:30 problem set`, `/blocks shift [19:00]`, `/blocks shift by 2 hours`, `/blocks remove <what> [after 22:00]`, `/blocks undo`, `/blocks clear` | today's planned time blocks; shift reschedules the day (what's due soonest first); remove takes some out | Agent plan calendar |
| `/today` | today's calendar | Calendar |
| `/cal`, `/cal classes Timetable`, `/cal classes none`, `/cal holidays Holidays`, `/cal holidays none` | the next 7 days; which calendars hold classes; which mark holidays | Calendar |
| `/cal subscribe <iCal link> as LA class`, `/cal shared`, `/cal unsubscribe LA class` | a class calendar a classmate or the course shares: its events marked with its name, its deadlines and exams offered with Add buttons ([classes-and-timetable.md](classes-and-timetable.md#shared-class-calendars)) | Calendar |

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
| `/addons` | your add-ons (your folder's and those added by link): what loaded and what didn't, and the [official add-ons](add-ons.md#official-add-ons) with Add and Update buttons; `/addons official` lists only those; answers with the feature off too | Your add-ons |

More: [Teaching Kurooto](teaching-kurooto.md), [Updates and backups](updates-and-backups.md),
[Your computer](your-computer.md), [Add-ons and scripts](add-ons.md).

## Plain-English requests understood instantly

These are answered at once on your computer, without asking an AI, so they work even when the AI is out of free
requests. Anything else goes to your AI (with Chat on). Long messages, or several requests in one message, always go to
the AI. A request that asks a question only matches the requests below that answer questions. Times about the past
("since I didn't wake up at 12") are never used as the time of a call or reminder.

| You say | What happens | Feature |
|---|---|---|
| "did I finish that thing?", "did you finish that thing?", "what was that thing?", "the draft thing is done" | what "that thing" is, from your open threads of the last 48 hours (and your AI requests, for "you"), read only; two or more: one question with a button each; "done" closes it with Undo | Kurooto itself ([threads](talking-to-kurooto.md#open-threads-and-that-thing)) |
| "when did I last talk to Prof Ortiz?", "when did I last meet Lena?" | the newest meetings, daily-note lines, gists and threads that name them | Kurooto itself ([memory](privacy.md#the-memory-ledger)) |
| "what was I doing last Thursday?", "what did I do yesterday?", "what was I doing on 20 Oct?" | that day's daily note, meetings, calls, requests and threads | Kurooto itself ([memory](privacy.md#the-memory-ledger)) |
| "help with my thesis: add footnotes to chapter 2 citing refs.bib", "in my thesis add footnotes …" (a project of yours), "in my thesis project, write the README's install section" | the AI works on that project in a scratch folder; the change comes as a proposal (once you let it help with that project) | Help with your project |
| "tidy my LA notes' headings", "add a summary to this lecture note", "fix the links in my probability notes" | the AI changes them in a scratch copy of your notes; the change comes as a proposal (with Chat on; `proposals.notes_edits`) | Kurooto itself ([proposals](proposals.md#changes-to-your-notes)) |
| "remind me at 9 to call mum", "remind me in 20 minutes to take the pasta off", "remind me tomorrow at 7am to go to the gym", "remind me tonight to pack" (21:00), "remind me tomorrow to …" (09:00) | a reminder for today or tomorrow; for another day use `/remind fri 17:00 …` | Reminders |
| "remind me when I reach the library to return the book", "remind me whenever I'm at the gym to stretch" | a location reminder: the Android app says it when you arrive at a place saved there (`reminders.places`, off by default) | Reminders |
| "what's due?", "anything due?", "show my deadlines" (two weeks), "what's due this week?" (7 days), "what's due soon?" (`deadlines.plan_h`, 3 days) | the deadline list | Deadlines |
| "add a deadline: essay draft due friday 5pm", "I have a lab report due fri 17:00" | a new deadline | Deadlines |
| "I don't care about the drama club", "stop telling me about …" | a topic on your not-interested list | Deadlines |
| "find the dates in that photo", "deadlines from this notice" | the newest photo of the last two hours, read for its dates (Add buttons) | Deadlines |
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
| "what should I revise today?" | today's revision blocks | Exam season |
| "starting linear algebra for 50 min" | a study session away from the computer | Study tracker |
| "done studying" | end the session | Study tracker |
| "studied stats for an hour" | log study time | Study tracker |
| "how much did I study today?" | study time | Study tracker |
| "study mode", "turn on study mode", "leave study mode" | the dashboard's Study mode | Study tracker |
| "what's on today?", "what's on tomorrow?", "anything planned tomorrow?" | your calendar | Calendar |
| "call me at 5 about the laundry", "call me in 20 minutes about the essay" | a call later ("at 5" in the afternoon means 17:00) | Phone calls |
| "call me now", "ring me about the essay" | a call right away, even during a class or a `/hold` (you asked for it) | Phone calls |
| "call me" with only a past time in it | asks when instead of booking | Phone calls |
| "cancel that call", "cancel the 12:00 call" | cancels a booked call, or lists them with Cancel buttons | Phone calls |
| "wake me at 6:45", "no alarm tomorrow", "cancel Friday's alarm", "cancel my alarm", "cancel the 10:30 alarm", "cancel all my alarms", "turn my daily alarm off" | the wake-up alarm | Morning alarm |
| "do I have any alarms?", "when is my alarm?" | the alarm that's set | Morning alarm |
| "reschedule my day", "I just woke up, reschedule my day", "reschedule my day from 19:00", "push my day by 2 hours" | today's blocks not done, moved to start from then (`/blocks undo` puts them back) | Agent plan calendar |
| "I'm awake", "I just woke up", "I'm up" | the morning call now, planned from the current time (with Morning alarm on) | Morning alarm |
| "no calls for 2 hours", "don't call me until 6", "hold calls until 18:00" | no calls until then (a named other day goes to the AI) | Telegram |
| "calls are fine again" | allow calls again | Telegram |
| "when I say gym, hold calls 90 min", "when I say lab, hold everything 2 h"; later "gym" on its own | a hook: the word alone starts that hold (everything is focus), with Undo; the word in a sentence does nothing | Commitments |
| "focus for 2 hours", "do not disturb until 18:00", "focus off" | do-not-disturb on or off | Telegram |
| "remember that I like a plan before 9", "keep in mind that …" | a line for your how-to-help-me note | Remember |
| "observe whether I study better before noon", "keep an eye on ..." | something for the look back to watch | Nightly look back |
| "every friday at 6pm send me a summary of my week" | a routine | Skills |
| a link on its own | filed into your notes (the `/add-to-notes` skill) | Skills |
| "sync everything", "sync it all", "sync all now" | every sync that's on, one after another | always there |
| "should I stop my meds?", "should I break up with him?", "should I take the loan?" | not Kurooto's to decide: one line on who to ask (a doctor or pharmacist; someone you trust or a counsellor; a financial adviser) | always there (`persona.boundaries`) |

Phrasings you taught with the Wrong button are matched first, as a whole message. See
[Teaching Kurooto](teaching-kurooto.md#wrong-button-and-test-cases). A short message none of these take, but about
equally close to two of them, gets both as buttons ("Did you mean ...?") instead of a guess
([Talking to Kurooto](talking-to-kurooto.md#what-happens-to-a-message)).

**Effort prefixes.** Start a message for the AI with `low:`, `medium:` or `high:` to choose how hard it thinks. See
[AI models](ai-brains.md).

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
| `kurooto setup [STEP]` | open the setup page where you left off, or at one step (`about`, `telegram`…) |
| `kurooto autostart on \| off \| status \| boot \| login` | start at sign-in or not; `boot` starts it before anyone logs in (Linux) |
| `kurooto run`, `kurooto supervise` | run it in this window; run it and restart it if it crashes (for troubleshooting) |

### Checking and fixing

| Command | What it does |
|---|---|
| `kurooto doctor` | check that everything is in place; the exit code is the number of problems |
| `kurooto doctor --fix <id>` | run the fix a problem offers |
| `kurooto doctor --bundle` | a diagnostics zip with secrets, names and addresses blanked out, to send to someone helping you |
| `kurooto doctor --json` | the same checks for programs |
| `kurooto fixme [words]` | what's wrong and what to do, matched by rules (no AI), also with Kurooto stopped: each failing check with its troubleshooting row and known issues; with words, the rows for what you see (`kurooto fixme the phone doesn't ring`); the exit code is the number of problems |
| `kurooto top`, `kurooto top --once` | a status board in the terminal (q quits) |
| `kurooto logs`, `kurooto logs -f`, `kurooto logs -n 200` | the end of Kurooto's log; `-f` keeps following it |
| `kurooto paths` | where settings, data, state, logs, cache and the program live |
| `kurooto usage [days]` | AI requests per day, and agy's own count |
| `kurooto ai accounts` | your Claude accounts: the usual sign-in and the extra ones ([two Claude accounts](ai-brains.md#two-claude-accounts)) |
| `kurooto ai add-claude [name]` | add another Claude account and sign it in, in this terminal |
| `kurooto ai test ID` | ask an AI for a reply, e.g. `kurooto ai test claude:work` |
| `kurooto ai rename-claude NAME NEW` / `remove-claude NAME [--yes]` | rename an extra Claude account (its id stays) / remove it and Kurooto's sign-in folder for it (asks first) |
| `kurooto jobs`, `kurooto jobs --cancel <id \| all>` | what the AI is working on; cancel |
| `kurooto graph [now \| stop \| same \| garden \| backfill …]` | the same as `/graph` from a terminal; `garden` runs the daily linking pass now |
| `kurooto run all`, `kurooto run all status`, `kurooto run all stop` | `/run all` from a terminal: it prints the progress line live, a line per step, then the summary (Ctrl-C leaves it running in Kurooto). `kurooto run` alone still runs the assistant in the window |
| `kurooto hardware`, `--profile <name>`, `--add <model>`, `--remove <model>`, `--add-prereq <id>`, `--remove-prereq <id>`, `--install` | what this computer suits, and going past it |
| `kurooto space`, `kurooto space --clean` | what Kurooto takes and what can go |
| `kurooto installed` | what Kurooto installed on this computer (programs, Ollama models), with sizes and what uses each ([What Kurooto installed](your-computer.md#what-kurooto-installed)) |
| `kurooto remove <name>`, `--yes` | remove one of them (asks first); only what Kurooto put there goes |
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
| `kurooto uninstall`, `--keep-data`, `--revoke`, `--keep-programs`, `--yes` | remove Kurooto, and what it installed (its receipt; asks first); `--revoke` first takes back what it set up on your accounts |

### Talking to Kurooto from a terminal or script

| Command | What it does |
|---|---|
| `kurooto ask "what's due this week?"`, `kurooto ask` | plain English as on Telegram; alone, a prompt for one request after another (`!command` runs a shell command there); `--no-wait`, `--job <id>`, `--timeout <minutes>` |
| `kurooto ask --popup`, `kurooto ask --shortcut` | a small window to type one request in, the answer shown there (bind it to a hotkey in your system: [Quick ask](talking-to-kurooto.md#quick-ask-a-hotkey)); `--shortcut` adds Kurooto Quick ask to your app menu (on Windows its Properties take a shortcut key) |
| `kurooto note "an idea"`, `… \| kurooto note --title "output"` | a quick note in your inbox (works with Kurooto stopped) |
| `kurooto voice`, `kurooto voice mute`, `kurooto voice unmute`, `kurooto voice stop`, `kurooto voice say <text>` | Voice, as `/voice` ([Voice](voice.md)) |
| `kurooto voice id`, `kurooto voice id forget [--yes]` | Voice ID's status; forget your voice print and its key (asks y/N; works with Kurooto stopped too) ([Voice](voice.md#voice-id-only-your-voice-can-make-it-act)) |
| `kurooto voice parts add FILE...` | install Voice's parts from files on this computer (a model file checked against its pinned checksum, or a package's `.whl`), for a computer without internet |
| `kurooto face`, `kurooto face pause 1h`, `kurooto face forget [--yes]`, `kurooto face install-from FOLDER`, `kurooto face test-camera` | Face presence ([Face presence](face.md)); forget and install-from work with Kurooto stopped; test-camera prints numbers only |
| `kurooto notify "text"` (`--title`, `--kind`, `--urgent`, `--button "Label=…"`, `--click URL`, `--print-id`, `--reply-to ID`) | send yourself a message |
| `kurooto send <file>` (`--caption`, `--to drive`) | send yourself a file on Telegram (up to 50 MB), or to your Google Drive |
| `kurooto ask-me "question"` (`--choices "a\|b"`, `--wait`, `--timeout`, `--expires`, `--title`, `--then CMD`, `--pending`, `--id`) | ask yourself something, answered anywhere |
| `kurooto ask-approval "question"` (`--timeout`) | wait for Approve / Deny: exit 0 approved, 1 denied, 2 timeout |
| `kurooto call "reason"` (`--at 17:30`, `--alarm`, `--force`, `--list`, `--cancel <key>`) | ring your phone now or later |
| `kurooto watch -- <command>` (`--lines N`, `--log <project>`) | run a long job; a message when it ends |
| `kurooto runlog start \| metric \| note \| end \| ls` | log experiment runs into your notes |
| `kurooto runlog diff A B` | two runs side by side (config, code, metrics, curves) into the project's notes (Research add-on) |
| `kurooto idle away \| back` | for your idle tool: you've stepped away, or you're back |
| `kurooto mcp` | Kurooto's tools for agent programs (an MCP server) |
| `kurooto export-skills on \| off \| status` (`--to agy,agents,claude`) | your skills as /commands in agent programs |
| `kurooto ntfy-token` (`--clear`) | a paid ntfy account's token for the phone app's fallback (ntfy counts a free account by internet address, so it doesn't help; since 0.7.0 the app gets calls straight from your call line anyway). Asks for it without showing it, checks it with ntfy, then updates your call line |
| `kurooto reserve` | write Markdown copies of alarms, deadlines, calendar and settings for AI programs |
| `kurooto cases [list \| check \| export \| forget <id \| all>]` (`--out`, `--all`) | test cases from the Wrong button |
| `kurooto classpack check <file>`, `export --checked today [--from <note>] [--title …] [--elective …] [--out …]`, `import <file>` | class packs |
| `kurooto term` (`--shell`, `--print`, `--install`, `--default on \| off \| status`, `-e <command>`) | open Kurooto Terminal |
| `kurooto addons` (`list`), `add <git url> [--ref <tag>] [--yes]`, `add <name>` (an official one), `official`, `update <name> [--ref …] [--yes]`, `show <name>`, `remove <name>`, `undo <name>` | [add-ons by link](add-ons.md#add-ons-by-link) and [official add-ons](add-ons.md#official-add-ons): read its card, then add, update, remove, undo |

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

Every Telegram command above comes from the code's command list (each feature's `commands()` and Kurooto's own, in
`core/commands.py`), every plain-English row from each feature's instant requests (their examples are what `/help`
shows), and every terminal command from `kurooto --help`. A test fails when a command isn't in `/help`.

Some of these never happen without your tap (an alarm, a call, a new mail sender, anything sent out, a repository,
deleting your data): [Never without your tap](talking-to-kurooto.md#never-without-your-tap).
