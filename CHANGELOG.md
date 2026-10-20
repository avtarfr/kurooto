# Changelog

## 0.5.0 (unreleased)

**Free-tier reserve** (on; nothing waits until a limit is known)
- Kurooto counts AI requests per free limit (each model of your Gemini key, agy, another service) and learns each
  limit and when it resets from Google's "limit reached" answers, instead of a table that goes stale. agy's count comes
  from its own logs, so the runs you type count too.
- Past 70% of a day's known limit (`quota.background_pct`), background work waits in the queue and runs after the
  reset: the Classroom digest, the nightly look back, skill changes, research digests, book and handwritten pages read
  by Gemini. The "how hard is this" question moves to the model on this computer, or the rules. Calls, voice notes,
  the morning plan and your own requests keep the rest; nothing is dropped. `quota.local` = `background` moves
  background work to the model on this computer instead of waiting.
- A used-up limit is one plain line: "Google's free limit for today is used up, resets at 12:30; your calls and alarm
  still work." Your own requests try it last, after the fallback brain.
- `/usage`, `kurooto usage` and the usage API show today's limits, what's used of them, and the requests waiting.
- A daily limit no longer waits a minute and asks again before the fallback; handwritten files that hit a limit are
  tried again later instead of being written off.

## 0.4.0 (unreleased)

**Books and PDFs** (new; off until you turn it on)
- Reference books and PDFs per subject: send one on Telegram with "book for <subject>", add it on the dashboard, or
  drop it in the subject's books folder. Books live outside your notes (`files.folder`, or Kurooto's data folder).
- Read at night on the charger, page by page, the best way for each page: the PDF's own text (Poppler, or Kurooto's
  built-in reader), Tesseract OCR for scanned pages, or a local vision model that writes the maths in LaTeX. Gemini
  only if you turn on `books.gemini`. It stops at 07:00 or when you unplug and carries on the next night.
- Each book gets an index note in your notes (`<subject>/books/<book>.md`: chapters with their pages); its text, with
  page markers, stays in Kurooto's data folder, and goes into the Notes brain when that's on.
- `/books` (per subject, how far reading got), `/books read now`, `/books stop`, `/books folder`, `/books setup`.
- Tesseract and Poppler join the things Kurooto can help install (winget for your user on Windows, Homebrew on a Mac;
  on Linux your package manager, which Kurooto never runs for you).

**Notes from every source**
- The source mix: how much books, Classroom materials and your own class notes each count when the AI writes notes,
  per subject (`/books mix <subject> book 30 classroom 30 own 40`, or an order: `prefer own book classroom`). Only the
  sources a subject has are used; the shares grow to fill the gap.
- `/study-log`, Classroom → notes, `/pack`, `/add-to-notes` and the new `/exam-prep` draw on all three through the AI's
  `course_sources` tool and cite where each part came from: (book: <title>, p. 123), (Classroom: <post>),
  (your notes: [[<note>]]). Your own words are quoted, never reworded.
- `/exam-prep <subject>`: brings a subject's exam prep up to date from everything there is, also without Classroom.

**Handwriting on an 8 GB graphics card**
- Handwritten notes are read by a model on your computer whenever there is one: the 12 GB vision model, or now the
  8 GB helper model (gemma4:e4b reads handwriting), or one you name (`handwritten.local_model`). PDFs too, not only
  photos: page by page with the maths in LaTeX, at night on the charger (`handwritten.pdf_hours`), resuming from the
  next page after an unplug or the morning, and waiting while the graphics card is busy. Gemini only when no model
  here can read them; `handwritten.cloud` = `false` never sends them.
- A changed original updates the same note between `kurooto:handwritten` markers and keeps what you wrote around it.
  `handwritten.keep_original` = `link` links to the original where it is instead of copying it. `/handwritten status`,
  `/handwritten retry`.

**Research**
- arXiv sources in arXiv's own search words (`{"type": "arxiv", "name": …, "query": "abs:… AND (…)"}`), each named
  in the digest; arXiv requests three seconds apart. `research.save_note` keeps each digest as `inbox/papers-<date>.md`.
- Runs a script keeps in its repository (`runs/index.csv`) get a line in the project's log every night
  (`research.repo_runs`). `from kurooto.runlog import Run`: `with Run("name", config=…) as run: run.log(step=…, x=…)`,
  into your notes with a project, else into the repository's `runs/`; failed and interrupted runs keep their error.
- Run links in project notes follow your notes layout. "Remind me tomorrow" for a quiet project is a call at 18:00
  when Phone calls is on (`research.remind_by_call`).

**Revision packs before exams**
- The evening before a quiz or exam with a subject, Kurooto offers a revision pack (**Build it** / **No thanks**), or
  builds it by itself with `skills.auto_pack` = `auto` (`off`: never).

**Your own GBrain**
- `gbrain.managed` = `false` uses a GBrain you already run (Postgres or PGLite; `gbrain.exe`, `gbrain.home`) instead
  of Kurooto's own: Kurooto only searches it, adds pages through gbrain's commands, keeps your notes' source in step
  (`gbrain.source`) and runs the nightly steps you choose. It never inits, migrates or reconfigures that brain.
- `gbrain.upkeep_steps`: choose the nightly upkeep's steps (GBrain's phase names; `purge` is never run).
- `gbrain.agy_mcp`: after your approval, agy gets your brain's own MCP server ("gbrain", `mcp(gbrain/*)`), keeping an
  existing registration and your own allow-list picks.
**Google**
- **Several Google accounts** (a personal one and a school one, say): each feature uses the account you choose on its
  card (a new name signs that account in) or with `/google use <feature> <account>`; each account is asked only for
  what its features need. `/google` lists them; `/google forget <name>` removes one.
- **Google Calendar**: Calendar can read your Google calendars through Google's Calendar API, from one account or
  several, for accounts without a secret iCal address. Other people's shared calendars are left out.
- **Private events are "Busy (private)"** wherever Kurooto shows or tells them (Google's Private visibility,
  `CLASS:PRIVATE` in iCal, or `#private`); their title and place aren't kept (`calendar.mask_private`).
- **Class calendars**: `/cal classes Timetable` makes that calendar's events classes (no calls, in your day's classes,
  the after-class question when the title names a subject).
- **Mail digest by email**: each digest also comes to your own inbox, sent from the account you choose, only ever to
  that account's own address; held back if it mentions confidential material.
- **Drive upload**: `kurooto send FILE --to drive` (and the AI's send_file) puts a file in a Kurooto folder in your
  Drive and sends the link; files over Telegram's 50 MB go there by themselves. It sees only files it made.
- The Agent plan calendar can live on another account (`/google use plan personal`).

**Four settings for doing it your way** (defaults unchanged)
- `availability.night.alarm_only`: only a night with the alarm set holds calls (bedtime to the alarm); with no alarm,
  nothing holds them overnight. Off by default: the fixed night hours (23:30 to 07:00) still hold calls without one.
- `deadlines.plan_h` (72): how far ahead "due soon" looks, for the wake-up call's plan, the morning page, the call
  brief, `/status` and "what's due soon?".
- After-class notes for some subjects only: `capture.subjects` (ask only after these; empty: all) and
  `capture.skip_subjects` (never after these), by short name, full name or alias.
- Mail digest by Gmail search: `/mail query -category:promotions -category:social` (`mail_digest.query`, empty by
  default) reads the mail a Gmail search matches. Your never-read list, the not-interested list and the confidential
  check still come first, and personal mail among it is only counted, never summarised. `/mail query off` clears it.

## 0.3.0 (unreleased)
## 0.3.0 (2026-10-20)
The [manual](docs/MANUAL.md) has the detail.

**Kurooto Terminal**
- `kurooto term` (off until you turn it on): your AI's program, your shell, Kurooto chat and its log in a terminal
  window of its own, with `kurooto top` beside them, in Kurooto's colours. kitty on Linux and macOS (yours, or the
  official kitty in Kurooto's folder, no admin), Windows Terminal on Windows (Kurooto's profiles and colour scheme as
  a fragment, no admin); fish when you have it (or the official fish in Kurooto's folder).
- An app-menu entry, and `kurooto term --shell` for just your shell in Kurooto's colours.
- An opt-in "make Kurooto my default terminal", with a clear undo: opening a terminal then gives you that themed shell
  (`terminal.default_opens`: `layout` for the whole window).
- `kurooto ask` gets the chat tab's look: the spaced name, examples and a `kurooto ❯` prompt.

**Dashboard and `kurooto top`**
- A new **dense** layout, the default on screens 1280 px wide or more: one full-screen board with each pane's name in
  its border.
  - STATUS is a btop-like monitor: history graphs, every core, a memory breakdown, the graphics card, network, disks,
    processes with Kurooto's own marked, study today and projects.
  - SYSTEMS has today, what's due, the AI's corner and recent events round the cells, the hours on the ring, and each
    feature's own programs on its cell. The cells' words sit outside them and never overlap, however many features
    are on: a crowded ring becomes two, and labels move a little (with a hairline to their cell) or shorten.
  - NOTES shows folders and recent edits.
  - The terminal below has its tabs and every other page in its border, and a **kurooto** tab for plain English
    without the Terminals feature.
  - `look.layout = roomy` keeps the earlier layout, which narrower windows get by themselves. `look.projects` lists
    the git folders the board follows.
- Settings shows a list to choose from, with a line of help, where a setting has fixed choices (the palette, the
  dashboard's layout, the notes layout).
- Settings → Starting: start Kurooto when you log in, or (Linux) when the computer starts. Windows and macOS show that
  they start at sign-in.
- `kurooto top` is laid out like btop, with the same figures as the dashboard: history graphs, every core, speed,
  temperatures and fans where the computer has them, memory and swap, the graphics card, network, disks, battery,
  processes (sort with `c` / `m`), and Kurooto's features, call line, today, what's due, study and projects.

**Colours**
- A third palette, **system**: Kurooto's pages take this computer's own accent colour and light or dark mode, and
  follow them when they change. It reads Material You colours from matugen (end-4's Hyprland setup and others), pywal,
  KDE, GNOME 47+ and GTK on Linux, and the accent colour on Windows and macOS. The setup page recommends it when it
  finds your colours (step 2, Colours); Settings → Look → `look.palette` changes it. Text is always made readable
  (WCAG AA). When nothing is found, it looks like kuro.
- `look.theme_file`: a kitty theme or a matugen or pywal `colors.json` of your own, used instead of the desktop's.
- The rose palette's light version: its pink and coloured text is darker, so it's readable on the light background.

**Setup page**
- Each step says what it's for and what happens if you skip it; a step you passed but haven't finished shows "!".
- Words like API key, token, repository, iCal, Cloudflare, GBrain or agy have a one-line explanation: tap the dotted
  word.
- The time zone is picked from a list as you type; a name it doesn't know is caught before you go on.
- AI step: one **Save and test** button for a key, progress while it tests, and what to do when a test fails (for
  each kind of AI). Sign-in windows report back on the page instead of a pop-up.
- Telegram step: an empty or wrong token says what to paste.
- Done step: what's ready and what isn't (with a link back to it), progress for each feature being set up, and next
  steps with an **Open the dashboard** button.
- If Kurooto stops answering, a bar at the top says how to start it again; it goes away by itself.

**Going offline and coming back**
- Kurooto says "going offline (shutting down)" before a clean stop (stop, off, signing out, shutting down; never for
  an update's restart), and "back online (offline since 22:10, 7 h)" after a start, a wake from sleep or a network
  outage ("the network was down from 14:02 to 14:31"), with what it caught up on. Telegram messages that couldn't go
  out while the network was down follow, marked as delayed.
- Nothing for under 10 minutes away; sleeps close together give one message; at night it waits for the morning.
  Settings: `notify.presence`.
- With Phone calls, your call line says "offline since ..." when the computer can't (sleep, a crash, a lost network):
  on the phone app, and on Telegram if you approve giving it your bot's token (asked once). Without a call line there's
  no message for those.

**Check-ins and the computer**
- A check-in day runs from 05:00 to 05:00 (`checkins.day_starts`), so a night check-in after midnight, or one pushed
  past it, stays the evening's (it used to move to the morning), and its journal goes to the evening's day.
- Check-ins by call: with the alarm set and past your bedtime (or the alarm just set by you), the night check-in
  doesn't ring; it moves to the wake-up call, with **Call me now** and **Skip** on Telegram
  (`checkins.asleep_defers`).
- Morning alarm: `alarm.keep_awake` keeps this computer awake from 12 hours before the alarm until it rings (Linux:
  lid closed too; macOS through caffeinate; Windows), so the morning plan is drafted on time. Off until you turn it on.
- Stay awake on charger: `awake.lid` keeps a Linux laptop running with its lid closed while plugged in. Off until you
  turn it on. The hold now ends when Kurooto stops, even after a crash.
- Study tracker: it notices you're away on Wayland too (GNOME, KDE, logind, and a watch for change on Hyprland and
  Sway); a locked screen never counts; `kurooto idle away|back` for hypridle and swayidle; and a Research category
  (`study.research_paths`, plus Research's projects).
- Linux: `kurooto autostart boot` (or Settings → Starting) starts Kurooto when the computer starts, before anyone logs
  in (lingering; its keys are kept in the owner-only settings file); `kurooto autostart login` goes back.

**Your notes**
- Notes layout: `notes.layout` picks where Kurooto writes (the `kurooto` layout as before, or `zettelkasten`:
  `dailies/`, `master/`, `sources/<subject>/`, `maps/`, `zettel/`, `projects/`, `digests/`), `notes.paths` puts any
  kind of note where you like, and new notes get that layout's header. The AI, skills and `kurooto note` follow it.
- Files folder: with `files.folder` set, photos, PDFs, revision packs, handwriting originals and Classroom files go to
  a folder outside your notes, linked from them, so they stay out of your notes' history. Unset, nothing changes.
- Revision packs are also linked from the subject's course page.
- Notes sync: a note changed here and elsewhere at once keeps both versions (the other device's in the note, this
  computer's as a "conflict" copy beside it) instead of this computer's winning; `notes_sync.on_conflict = stop`
  stops and asks you instead. A half-finished merge is left alone, and an existing `origin` (e.g. over SSH) is kept.

**From a terminal or a script**
- `kurooto notify` takes buttons (`--button "Label=prefix:ref:action"` or a web address), a link to open (`--click`),
  a reply to an earlier message (`--reply-to`, with `--print-id`), and the kinds `question` and `approval`.
- `kurooto call --list` shows the calls booked for later; `kurooto call --cancel <key>` takes one off.
- `kurooto sync --status` (works with Kurooto stopped) and `kurooto sync --no-wait`; sync everything ends with a
  backup when Backups is on.
- `kurooto ask-me --pending [--json]` and `kurooto ask-me --id <id> --wait`.
- `kurooto usage [days]`: `/usage` in a terminal.

**Skills in agy and other agent programs**
- `kurooto export-skills on` makes your skills (Kurooto's, your add-ons', your own and prompts with `skill: true`)
  slash commands in agy (`--to agy,agents` adds Codex and Copilot CLI). Only Kurooto's own copies are ever changed or
  removed; one of yours with the same name stays, and Kurooto's goes in as `kurooto-<name>`. Kept up to date at start
  and hourly; `kurooto export-skills off` and `kurooto uninstall` remove them.

**Seeing what's going on**
- `/status` also shows today's check-ins, what's due in the next 3 days, the alarm and your last AI requests.
- `/usage` also counts agy itself from its own logs (every run, the ones you type too), with the days it hit its limit.
- `kurooto doctor` asks Telegram whether your bot answers and your call line whether it's up and linked, and no longer
  reports the call line as unlinked just because the check runs outside Kurooto. It also shows your notes layout and
  any problem with its settings (`notes.layout`, `notes.paths`, `files.folder`).
- `/observing` has a **+7 days** button.

**Add-ons**
- An add-on feature can pick which plain-English request a message is before Kurooto's own patterns
  (`classify_intent`, with a 2-second limit and a fall-through), and add lines to `/status` (`status_lines`) and to
  `kurooto doctor` (`doctor_checks`).
- Add-ons can name programs a feature watches (`processes` on the feature): their cpu, memory and uptime show on the
  dashboard and in `kurooto top`, and the cell turns grey when none is running.

## 0.2.1 (2026-10-20)
- Setup page: on a desktop it uses the whole window: the steps sit in a list on the left with what each one is for,
  and feature cards fill four columns instead of a narrow strip. On a phone the steps are numbered dots. Any step can
  be opened from the list, Back and Next stay in view on long steps, and buttons, boxes and cards are tidier, with a
  visible outline when you move through them with the keyboard.
- On laptops whose charger the system names unusually (e.g. ACAD on Linux), Kurooto thought it was on battery while
  plugged in, so battery-saving held back heavy work; it now asks the system directly.
- The confidential-mail page follows your colours (Settings → Look), like the other pages.

## 0.2.0 (2026-10-20)
Many new features, each off until you turn it on. The [manual](docs/MANUAL.md) has the detail.

**Updating from 0.1**
- Nothing new starts by itself: if you set Kurooto up with 0.1, the morning page doesn't open at the alarm, the AI
  doesn't draft a plan before it, deadlines don't ring you six hours before or come from your calendar, an unanswered
  call rings again once (not twice), after-class answers aren't turned into AI study logs, and the nightly look back
  doesn't read your journal or call transcripts, unless you turn them on (or had set them yourself).
- No flood on the first day: deadlines already overdue and research projects already quiet aren't asked about.
- One short "What's new" message after the update, with a link to the manual.
- agy and Kurooto's tools: if you set agy up before, Kurooto asks once (Approve / Deny) before adding itself to agy's
  settings; Deny holds for 30 days. On the setup page, testing agy says it connects the tools.

**Your AI**
- The setup page recommends a **Gemini API key ★** (the simplest, and Google's recommended route for tools like
  Kurooto), then agy, Codex, Claude Code, local models and any OpenAI-compatible service. Existing setups keep the AI
  they chose.
- The setup page says plainly what a free Gemini key means (Google may use and review what you send; 18+; a paid key
  in the EEA, UK and Switzerland) and what using agy through Kurooto means for your Google account.
- FreeLLMAPI is no longer offered; one set up earlier keeps working and shows as "Another OpenAI-compatible service".
- The AI can act, not just answer: every feature's tools (reminders, calls, deadlines, study log, notes, questions to
  you) reach API brains directly and agent programs (agy, Codex, Claude Code) through `kurooto mcp`, a built-in MCP
  server. The notes tools only create, add to and tick; they never change what you wrote.
- `/usage`: AI requests per day per brain over the last week, and usage limits hit.
- Your AI can read your files (notes, Documents, Downloads, Screenshots, Kurooto's Classroom and mail copies) and
  public web pages, write and edit text files in your notes (the previous version is kept), and tell you how your
  syncs are doing (`sync_status`). agy gets the same reach through its allow-list, after you approve it: those
  folders, the web, and harmless commands such as git and latexmk; never `kurooto` itself.

**Questions, approvals and your phone**
- Questions and approvals from features, AI requests and your own scripts, answered anywhere: Telegram buttons or a
  reply, the phone app, or a call; the first answer wins. **Later** keeps one for your next call; `/q` lists the open
  ones. AI requests can ask you a question; your answer starts the follow-up.
- Your phone is a second channel: questions and approvals reach the Android app (Reply box, choices, Approve / Deny,
  Later) and the iPhone Home Screen app ("Waiting for you"), also while the computer is off. `notify.app_kinds` picks
  what else goes there.
- Calls: open questions come up at the start of a call, and approvals that arrive during one are asked there. Nothing
  else rings while you're on a call, and updates wait for it to end.

**Check-ins, mornings and calls**
- The evening check-in call is a debrief (classes, what slipped, open questions, study time, a quiz offer before
  exams); afterwards the AI writes your journal and study logs from what you said.
- A night check-in (off until you give it a time) says goodnight and sets the alarm, or moves to your wake-up call
  with **Tomorrow morning**.
- Unanswered or declined check-in calls become a message with Call me now / Tomorrow morning / Skip; "call me back
  later" keeps it a check-in. Change another day's check-in ("skip Friday's check-in"); `/checkins` has buttons.
- Mornings: the AI drafts your day 20 minutes before the alarm, the wake-up call goes through it, and the morning page
  opens on your computer.
- The night follows your alarm; unanswered calls ring again at +3 and +6 minutes; held calls tell you so and come by
  themselves when the block ends; "call me now".
- Calendar: `#focus` events are focus time; optionally only `#nocall` events hold calls.
- Weekly summary: an optional Sunday review call, written up in your journal.

**Study**
- Deadlines: calendar events that look like deadlines or exams, and recurring quizzes (a table in your notes,
  `/recurring`), join the list; the same thing from two places is kept once.
- Deadlines: the six-hour nudge is a call when Phone calls is on; an "Overdue?" check (Done / New date / Drop); Done
  ticks the box in your notes.
- Not interested (`/ignore`): topics left out of deadlines, and only counted in the mail and Classroom digests.
- Exam mode: on by itself two weeks before a quiz or exam (`/exam`); calls know about it; quizzes come more often.
- Quiz: sessions of several questions, a practice offer the evening before, quizzes by call, quiz check-ins.
- Subjects: term dates and exam periods (`/term`); "skipping LA on Friday".
- After-class notes: answer later on the evening call; photos and files filed next to the class log; an AI study log.
- Study tracker: sessions away from the computer (`/study la 50`, `/study stop`) and a "Study hours" section in your
  daily note.

**Notes and skills**
- Skills: `/journal`, `/study-log`, `/add-to-notes`, `/assignment`, `/connect-notes`, `/term-setup`, `/goodnight`,
  `/morning`, `/morning-prep`; reply to a skill's answer to carry on. A link sent on its own is filed into your notes.
- Your own skills (`/newskill`, `/skills copy`), routines (`/every monday 9:00 /journal plan my week`) and revision
  packs as PDF (`/pack`, with Tectonic, which Kurooto can install for you).
- Quick notes and prompts: `/note`, `kurooto note`, `/prompts`, `/prompt`.
- About you: the profile is editable right after **Build my profile** (setup page, and a new **About you** tab in the
  dashboard), with a preview of the In-brief part that goes along with every AI request; saving keeps the previous
  version. Building again asks first if you've edited it, and never replaces an edit made while it was building.
  `/aboutme` shows the In-brief part.
- Remember: `/remember`, "remember that ...", and on calls; kept in `about-me/how-to-help-me.md`, which you edit and
  which wins. Health, money and passwords are refused.
- Nightly look back: reads your answers, check-ins, call transcripts and journal; suggests settings, how-to-help-me
  lines, things to watch, skill changes (shown before saving) and ideas. Apply / Observe longer / No. `/observe`,
  `/observing`, `/lookback`.
- Notes brain: timelines (`/timeline`), an optional nightly upkeep and a weekly checkup.
- `kurooto send FILE`: a file to your Telegram; the AI can send you files from your notes.

**Google**
- Classroom → notes: new materials, coursework, announcements and attached Drive files filed into your notes by the AI
  (a note per lecture, a course page, an exam-prep note that Quiz uses); dates go into Deadlines.
- Mail digest: twice a day, sorted into Needs action, People, Courses, Opportunities and Admin. It reads only the
  senders, domains and labels you choose; mail marked confidential (anywhere in it, standard confidentiality footers
  included) and your never-read list are only counted, never summarised or answered with an AI draft. Optional local
  mode (`mail_digest.confidential = local`): a local model summarises confidential mail on this computer, kept only
  in Kurooto's data folder (dashboard → Features → Mail digest → Confidential mail); dates found there are offered
  (`/mail confidential`), never added by themselves.
- Email reply drafts with Send / Edit / Discard: nothing is sent without your tap.
- Agent plan calendar: time blocks Kurooto plans with you go into a calendar of its own (`/blocks`).
- Each Google feature asks for its own permission and turns on by itself after the sign-in.
- Setting up Google is beginner-proof: a step-by-step guide in the manual (every screen of Google Auth Platform,
  with links), and the setup card has a numbered summary, copy buttons for the values Google asks for, and a file
  button for the client JSON. The site has a privacy page (made from docs/PRIVACY.md).

**Your setup, kept safe**
- Backups: a daily zip in a folder you pick (an external drive, a cloud-synced folder); `kurooto restore`, which
  never overwrites a note.
- Profile sync: your settings, keys and saved state, encrypted with a passphrase only you know, in your own private
  GitHub repository. Moving to a new computer: "I've used Kurooto before" on the setup page, or
  `kurooto profile restore`.
- Sync everything: `/sync all` or `kurooto sync`. Notes sync also sends notes up after AI requests and when Kurooto
  stops.

**Research and your terminal**
- Research projects: a note per project with a log of each day's commits, a hub note, and a question when a project
  goes quiet.
- `kurooto runlog` (experiment runs with their config, metrics and exact code state), `kurooto watch -- CMD` (a
  message when a long job ends), `kurooto top` (a status board), `kurooto logs`, `kurooto ask` (plain English),
  `kurooto call`, `kurooto ask-me` and `kurooto ask-approval`.
- Terminals in the dashboard (off by default): your AI program, a shell, `kurooto ask` and the log.
- Your add-ons: your own features, skills, prompts and default settings from a folder of yours.
- On Linux, the dashboard only answers your own user account.

**Look**
- Kurooto's pages are deep green now, like the website: the setup page, the dashboard (its drawings too), the morning
  page, and your call line's pages and icon. The old colours stay available: Settings → Look → `look.palette` = `rose`.
- Warnings and errors have their own colours (amber and red), never the accent colour.
- The dashboard's ring gives every feature a short label and its own colour.
- The README and the website show the dashboard, the setup page, the morning page and your phone, from a demo with
  made-up data.

**Fixes**
- The setup page's "When this laptop is on battery" choice was refused; it's saved again, and Settings can change it.
- The dashboard keeps its address after a quick restart or an update (macOS and Linux).
- `kurooto stop` stops Kurooto the normal way first (Notes sync sends up what's left), then forces what's left;
  `kurooto start` says where the page is; `kurooto on` doesn't wait for a service manager that isn't there.
- After `kurooto update --now`, or an update that was rolled back, the dashboard no longer says "update ready"; a
  rollback sends one message saying so.
- The 05:10 call-line update after an update never opens a Cloudflare sign-in page by itself; if the sign-in expired,
  you get a message (calls keep working on the old version).
- A 24-hour time is taken as written: "/checkin midday 04:30" is 04:30, not 16:30.
- /status and `kurooto top` say what's coming in words, not internal names. "Overdue?" isn't said twice.
- The ★ Starter set no longer includes the notes brain (a 0.5 GB download; its card says so). Exam mode's daily
  practice check-in is off unless you give it a time (`quiz.exam_daily`).
- `kurooto doctor` warns when your time zone (Settings → You) isn't this computer's.
- Kurooto's job and schedule databases are readable by your account only, like its other state files; the installer
  starts Kurooto without its own temporary Python environment on the PATH.
- The phone's call page: the "Waiting for you" link no longer grows to fill the screen.
- "skip Friday's check-in" (and "no calls on Friday", "skipping LA on Friday") changed today's instead.
- The phone app only ever got rings; the phone channel is now wired up.
- The notes brain's sync no longer holds up the rest of Kurooto, and GBrain no longer checks for its own updates.
- Long requests to agy no longer fail on Windows' command-line limit.

## 0.1.6 (2026-10-20)
- **Phone calls couldn't be set up at all**: building the call page always failed. Fixed; setup now goes on to the
  Cloudflare sign-in. The Phone calls card lists what's needed in order (a free Gemini key, needed even when agy
  answers your messages; a free Cloudflare account; then pairing your phone, which is where the app comes from) and
  has a **Set up now** button.
- **Google sign-in could seem to do nothing**: the browser blocked the pop-up. There's now always an **Open Google
  sign-in** button, the card notices when you're signed in, and each way it can fail says what to do (including
  boxes left unticked on Google's consent page).
- Setup logs no longer vanish when the page redraws, and a refused setup says why.
- Setting up local AI models on Linux could get Kurooto killed for running out of memory: Ollama's download was
  unpacked in memory. It's now unpacked straight from disk, and the space check counts Ollama's real size.
- Setup: click anywhere on a feature card to tick it, and the boxes are bigger.
- A request to the AI could now and then vanish or fail when the setup page or the dashboard checked on it at the
  same moment (mostly on Windows).
- `kurooto start` works on computers where systemd's user session doesn't (WSL, containers).

## 0.1.5 (2026-10-20)
Everything since 0.1.1, in one update.
- **`kurooto stop` didn't stay stopped** on Linux and macOS (the background service restarted it 10 seconds later),
  and `kurooto start` / `on` could start a second copy beside it: both now go through the service manager.
- **`kurooto` was an "unknown command"** on computers that already had uv: Kurooto now puts its folder on the PATH
  (your user PATH on Windows, fish, bash and zsh) when it installs and whenever it starts, and the installer says
  how to use it in the terminal you installed from.
- **Telegram setup could wait forever** after pressing Start: the page now says why (another program using the bot,
  a webhook, a revoked token, an expired link, no internet), offers the fix, and always shows the message to send by
  hand. Running setup again while Telegram is on no longer swallows the Start message.
- **"Build my profile" failed with agy**: text-only work now tells agy to answer with text only.
- **agy and a Gemini key back each other up**: if one can't do something (refused, limit reached, signed out,
  failed), the other answers, and a line at the end says which. Without a Gemini key, the message says what to do.
- Long requests reach agy through a file, so profile builds work on Windows too.
- About you: the profile is editable right after **Build my profile**, on the setup page, with a preview of the
  In-brief part that goes along with every AI request; saving keeps the previous version. Building again asks first if
  you've edited it, and never replaces an edit made while it was building. `/aboutme` shows the In-brief part.
- The setup page recommends the Gemini key first (★); agy is second, with a plain note about it.

## 0.1.1 (2026-10-20)
Fixes, delivered as the first automatic update.
- A check-in call that comes due during a class, a hold, focus or the night now waits until the block ends, or comes
  as a message if that's too late for today.
- What you say on a check-in call reaches your journal again.
- Checking Kurooto (`kurooto doctor`) while the AI is working no longer makes that request run a second time.
- A landing page at avtarfr.github.io/kurooto.

## 0.1.0 (2026-10-19)
The first release, for friends.
- One-line install on Windows, macOS and Linux (per user, no admin), signed releases, a setup wizard that reads the
  computer and recommends settings, and installs what each feature needs (with a storage check).
- AI brains: Antigravity (agy), Gemini key, ChatGPT/Codex, FreeLLMAPI, Ollama, any OpenAI-compatible service, and
  Claude Code (Advanced); a fallback brain; effort picked per request.
- Features (all opt-in): Telegram, Chat, Reminders, Check-ins (by message or call), Deadlines, Subjects and timetable,
  Quiz, Weekly summary, Files into notes, Notes brain (GBrain), Local AI models, After-class notes, Nightly look back,
  Phone calls (your own call line; Android app; iPhone web app), Morning alarm, Voice notes, Stay awake on charger,
  Calendar, Notes sync, Google (Classroom, Gmail drafts), Handwritten notes, Study tracker, Research (a digest of new
  papers from arXiv's 155 fields, bioRxiv, medRxiv, PubMed and any feed, with its own dashboard tab).
- About you: prompts to run in all your other AI accounts, their reports brought into Kurooto, and a profile built
  from them that every AI request starts from.
- A local dashboard; `kurooto doctor` and a redacted diagnostics bundle.
- Laptops: a battery saver (Telegram keeps working; heavy work waits for the charger and runs when plugged in),
  `/pause` and `/resume`, and `kurooto off` / `on` (with a Kurooto entry in the app menu to turn it back on).
- Automatic, signed updates with rollback.
