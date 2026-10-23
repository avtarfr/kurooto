# Roadmap

Ideas that aren't built yet. Nothing here is promised; each one ships as an opt-in feature through the normal
signed updates when it's ready.

## Next
- ~~**Your notes, your layout.** Choose where Kurooto writes: the daily note, subject folders, the inbox, your
  profile. It then fits an existing notes system instead of bringing its own.~~ (0.5.20: the setup page's Notes step,
  also Settings → notes and `kurooto setup notes`, reads the folder without AI (daily-note names and folder, link
  style, header keys, subject folders, inbox) and proposes `notes.layout` + `notes.paths` with a confidence per line
  and a preview; Kurooto's own notes move as one plan shown first, with Undo from a move log. Not yet: writing
  markdown links instead of wikilinks for folders that use them.)

## From the ideation panel (2026-10-23)
Seven viewpoints (student, researcher, notes, phone, AI, friends, skeptic) argued these out; the most backed first.
- ~~**Link recall cards.** The concept graph's links become review cards ("how does Itô's lemma relate to
  Fokker–Planck?"), answered in your own words and graded by you (a small local model may check, never the free
  key). A miss points to the book pages. Up to five a day, also as phone notifications, never in class or focus.~~
  (0.5.16: `/card`, `/cards on`, `quiz.links*`, the quiz's spacing; "Where to read" adds the subject's own notes and
  Classroom files; `quiz.links_check` for the local model. Not yet: papers from the research digest, which don't go
  through Books.)
- ~~**Revision plan.** When exam season starts, a course's topics are ranked (no note, stub, weak recall, the rest)
  and laid over Start-by's free slots with the pages to read; the evening check-in asks "did you cover X?" and feeds
  the same recall score as the quiz. Plain arithmetic, no AI.~~ (0.5.16: Exam season's `revision` part, `/revise`;
  topics from the exam prep note, else lecture or concept notes; class material's pages before books'; Yes / Partly /
  No grade the topic's quiz items, with Undo)
- ~~**Turn on from chat.** A message that needs a feature that's off ("wake me at 7") offers [Turn on] [Not now]; one
  tap turns on it and what it needs, then does the original request.~~ (0.5.10)
- ~~**Run receipt.** Every AI answer ends with one grey line built from the tool log, not the answer's words: brain,
  effort, time, share of today's limit, and what it actually did ("did nothing" when it did nothing).~~ (0.5.15:
  italics on Telegram, plain text in the dashboard and the terminal; `jobs.receipt`)
- ~~**/fixme that works when the AI is what broke.** Doctor's symptoms matched by rules to the manual's
  troubleshooting and a signed known-issues list shipped with releases; Fix buttons run `doctor --fix`; your AI only
  explains, if it answers.~~ (0.5.15: `/fixme`, `/fixme <what you see>` and `kurooto fixme`; Ask my AI only explains,
  after)
- ~~**Keep or drop.** A local count of what you actually use per feature; on day 10, Keep / Quiet / Off per feature,
  then monthly for features unused for 60 days that still run jobs. Never switched off without asking.~~ (0.5.15:
  `/keep`; Quiet uses Calm's stopped list, Off the usual turn-off, both with Undo)
- ~~**Egress ledger, enforced.** Every request Kurooto makes goes through one place that records host, feature and
  bytes and blocks hosts not listed in PRIVACY.md; `/egress` shows the week. Requests your AI program makes itself
  show as "handed to agy / Claude Code".~~ (0.5.16: `core/egress.py`, PRIVACY.md's "Where requests go" table;
  `privacy.egress` records by default and refuses unlisted hosts with `enforce`; `privacy.allow_hosts`; git, npm,
  wrangler, Ollama, GBrain, Tectonic and installers show as "handed to" as well)
- ~~**Retention.** `privacy.keep_days` (30) expires transcripts, prompts, answers, audio and logs, also the call
  line's queued copies; `/forget 7d`.~~ (0.5.15: nightly, call transcripts, AI requests' words, chats, questions,
  cases, sent messages' words, the search index and log lines; `/forget 7d`, `/forget all` with a confirm button.
  Voice recordings stay, being in your notes; the call line's queue is emptied whenever the computer connects)
- ~~**Problem-set progress.** Deadlines with parts (Q1–7): reply "4/7" or tap +1 on the phone; Start-by plans from
  what's left; the morning says "ps3 4/7, due Fri".~~ (0.5.10: "ps3 4/7" in chat and on calls, shown in lists and
  Start-by; 0.5.20: a reply "4/7", "4", "+1" or "done" to a deadline's message on Telegram, in the app's chat or the
  phone's Reply, with Undo; **+1** on the message and the phone's notification, which stays for the next tap and
  counts each tap in order through the phone outbox; the wake-up call, morning page and /status say "ps3 4/7, due
  Fri")
- ~~**Phone outbox.** Captures and taps made while the laptop sleeps wait on the call line and merge on wake~~ (0.5.16:
  chat messages, button taps, answers and shared files wait on the call line and reach the computer in order, each
  once, and the phone hears when each went through); ~~still to come: a home screen widget and a capture tile
  (launcher shortcut on Android 6)~~ (0.6.0: Talk widgets 1x1 and 2x1, a Quick note launcher shortcut on 7.1+ and a
  Quick Settings tile on 7+; Android 6 gets the widgets).
- **iPhone Shortcut.** Pairing an iPhone ends with a ready "Tell Kurooto" Shortcut (Siri, Back Tap) with a
  revocable link.
- **CPU micro-helper.** A ~1 GB model for one-word decisions only (effort, intent, yes/no) on laptops without a
  graphics card, enabled only if a speed test passes, offered after week 2 when the free limit is being used up.
- **Notation crosswalk.** When a concept appears in a second source, its notation and conventions are written side
  by side (B_t vs W_t, Fourier 2π), quote-checked like every graph claim.
- **Near-duplicate concepts.** "Wiener process" and "Brownian motion": Merge / Keep both / Add alias.
- ~~**Supervisor meeting brief.** (0.5.10 has the brief from the project note; still to come: a voice note becoming
  minutes, action items becoming deadlines.) The evening before a tagged meeting, a page from the project log since the last
  one; after it, a voice note becomes minutes, and action items become deadlines on a tap.~~ (0.5.20: for any
  meeting with someone a project note is With, weekly ones included; a voice note or typed note after it becomes
  minutes through your AI, and each action item is a deadline on a tap)
- **Run compare.** `kurooto runlog diff A B` and `/runs compare`: config differences, code diff, metrics and loss
  curves side by side, written to the project's notes.
- **LaTeX writing tracker.** Nightly build of your `.tex` repos: errors, undefined references, missing citations
  (BibTeX suggested, you approve), words added.
- **Check my attempt.** A photo of a proof (or a `.tex` derivation) before you submit: gaps marked, nothing
  rewritten; a course's AI policy can turn it off.
- ~~**Missed-class catch-up.** Skipping a class makes a catch-up item with that day's Classroom posts and a note stub.~~
  (0.5.14: a task due before the next class and a lecture note stub, also for classes you slept through; 0.5.15:
  that day's Classroom posts in the message and the stub, and without Classroom it works the same)
- **Bedside mode.** An old Android phone as a dock: clock, today, alarm, a talk button.
- **Add-ons by link.** `kurooto addons add <git url>`: a manifest card first, consent for code, pinned to a commit.

## From the skeptic review (2026-10-23)
Three skeptics checked the panel's ideas for a public release and looked for setup Kurooto could do itself.
- **Make the panel's ideas general**: link recall cards and ~~the revision plan~~ (0.5.16) also draw on course notes
  and Classroom files, not only books; ~~the meeting brief is for any recurring meeting ("With: X", their role in your
  own word: guide, manager, coach)~~ (0.5.20, with "Meets:", "Last met" and Next steps kept in Kurooto's block);
  "check my attempt" becomes "check my draft" (essays, accounts working, code, proofs); missed-class catch-up works
  without Classroom.
- **A Research add-on** for the narrow ones: notation crosswalk, run compare, LaTeX tracker, proof checking. Bedside
  mode is an Android add-on.
- ~~**No college-term defaults**: the check-in times and Start-by's day window are learned from when you actually
  reply (with a notice and Undo), not 09:00-22:00; a first-run question (student, working, research, other) picks the
  features; public holidays come from your country's calendar.~~ (0.5.9: learned check-in times and window, "What do
  you do?" in the wizard, holiday calendars)
- ~~**The phone app as a full chat channel** beside Telegram, for places where Telegram is blocked or little used.~~
  (0.5.16: Android's chat, handled like a Telegram message with working buttons; `notify.app_chat` sends Kurooto's
  own messages there too) (0.5.18: the iPhone app's chat; Telegram is optional: setup offers the phone app instead,
  and without Telegram everything comes to the chat, files as Drive links or a sealed copy on the call line)
- **Small gaps**: ~~`add_deadline` takes the course, so a mail's "Lab report" lands on the right course page~~
  (0.5.15: `course` by name or short name; an unknown one is said, never guessed); ~~a recurring fact said in chat
  becomes a class, a recurring quiz or a routine instead of being dropped~~ (0.5.20: "I have lab every Thursday 2-5",
  "quiz on Linear Algebra every Monday", "gym Tue Thu 7am", with `/inferred` Undo; questions set up nothing); ~~the
  nightly look back can propose routines and acts on data changes with Undo instead of waiting for a tap~~ (0.5.20:
  the same thing at the same time on 3+ weeks comes with Add / No; two copies of one deadline become one with Undo;
  `core/tap.py` `BY_ITSELF`); project notes keep "With:", "last met" and "## Next steps"; ~~subject aliases are learned
  from how you name them~~ (0.5.20: a short name in capitals used in two messages, when it fits one subject's
  initials).
- ~~**Routines for people who aren't students**: gym, shifts, standups, tuition; they hold calls like a class does.~~
  (0.5.9: Commitments, `/busy`, also set up from what you say)
- **Never without a tap**: setting or moving an alarm, placing calls, reading new mail senders, sending anything out,
  attaching a code repository to a project. Repositories are never searched for on the disk.

## Human-like (2026-10-23)
- ~~**Gists before forgetting.** Conversations settle instead of vanishing: one line of what each call, request or chat
  decided or did, from records, before its words fade.~~ (0.5.17: `privacy.keep_gist`, kept for good or
  `privacy.gist_days`; `/gists`, `/gists forget 3`; `/forget all` asks about them; a local model only with
  `privacy.gist_model`)
- ~~**Rechecking memories.** A kept line that hasn't come up in 90 days gets one "Still true?" with Keep, Change and
  Forget.~~ (0.5.17: `remember.recheck_days`, at most two a week, only Kurooto's own dated lines, Undo on Change and
  Forget)
- ~~**Your real body clock**: the night hours move to when you're actually quiet (nights into the afternoon too), the
  morning things follow, and the alarm suggests your usual time when none is set.~~ (0.5.17: `availability.learn_night`
  and `learn_morning`, `alarm.suggest`, with Undo; never ones you set)
- ~~**Lighter days after heavy ones**: after an exam or a long study day, fewer messages, the first check-in later, and
  one line in the morning with Not today.~~ (0.5.17: `notify.calm.lighter_after`)
- ~~**Noticing absence**: two days without a word from you brings one gentle message, never a call, with I'm fine /
  Busy, quiet for a week.~~ (0.5.17: `availability.absence_days`)
- ~~**Dream RSI, part two: it learns when to reach you.** Each night it replays the messages it sent by itself under a
  few variants of when they come, keeps today's rules as a candidate, and applies the best only if it clearly wins, one
  change a night with Undo; a kind you keep ignoring fades to the evening bundle.~~ (0.5.17: `notify.calm.habituate`
  and `notify.calm.windows`, the nightly replay in Dreaming, `/dream policy`)
- ~~**Curious**: a topic you asked about 3+ times this week with no note gets one morning line, with Make a stub and
  Not interested.~~ (0.5.17: `dreaming.curious`, rules only)
- ~~**Remembering**: one morning line from a shared past, a note or quiz subject from 10-30 days ago (exam subjects
  first) or a project's anniversary, with Open it and Less of this.~~ (0.5.17: `dreaming.resurface`)

## Ideas
- **Dream RSI, part three.** The nightly replay that tunes when messages come (part two) applied to Kurooto's
  other recorded decisions: which effort an AI request gets, the order of fallback AIs when one fails, and how
  Start-by sizes work. Each candidate is replayed against what actually happened, the current rules always among
  them, and a change is kept only if it's better, one at a time, with Undo. After part two has proven itself.
- **Offline fallback.** When the internet drops, a small model on your computer answers quick things and queues the
  rest.
- **An email-in address.** Forward a notice or a receipt to your own call line, and it's filed in your notes or
  becomes a deadline.
- **Zotero.** A paper from the research digest goes into Zotero with one tap, and reading notes link to it.
- **Photo → dates.** Share a photo of a notice or a timetable from your phone, and the events and deadlines are
  pulled out.
- **Shared class lists.** Friends in the same course can opt in to share deadlines and exam dates.
- **Quick-ask hotkey.** A small prompt window on the desktop, on every system.
- **Location reminders on Android.** "When I reach the library", without draining the battery.
- **Course notes to PDF.** A LaTeX template for course notes.

## More human (2026-10-23)
- ~~**Open threads and "that thing".** A small list of what you're in the middle of, opened from what you say you'll
  do and tasks you start, closed when done; "did I finish that thing?" resolves from the last 48 hours and asks once
  when two fit.~~ (0.5.18: `/threads` with Done, Drop and Undo; also from what you say on calls; `memory.thread_days`;
  a thing found that way is only read or asked about, never acted on without your OK)
- ~~**A context assembler with a memory budget.** Each AI reply gets only the remembered items your message refers to,
  capped, and the receipt says how many.~~ (0.5.18: `memory.budget_tokens` 600, `memory.recall`; open threads, gists,
  meetings and daily notes by rules; gists only, never transcripts; "used 2 remembered items"; calls get open threads
  and the day's gists)
- ~~**A memory ledger with an episodic timeline.** One local store of everything remembered, each row with its source
  and a Forget; "when did I last talk to Prof X?", "what was I doing last Thursday?".~~ (0.5.18: always encrypted with
  a key in your keychain, out of backups unless `backups.memory`, covered by `/forget`; `/memory`, `/memory forget 3`,
  `/memory export` to a note)
- ~~**Persona card**: what to call you, tone, length, things to avoid, in every AI request and call.~~ (0.5.18:
  `/persona`, the About you tab, Settings; empty to start; feelings, a backstory and "I missed you" are left out)
- ~~**Negotiate, don't repeat**: a reshaped plan from your own plan instead of the same reminder again.~~ (0.5.18:
  "1 h now, 1 h tomorrow?" with Do that / Not today, once per deadline per day, on Telegram, the app and calls)
- ~~**Repair with two readings**: ask with both as buttons when two requests are about equally close.~~ (0.5.18: the
  same pick twice teaches the phrasing through test cases)
- ~~**Boundaries it keeps**: health, relationship and money decisions point to a person.~~ (0.5.18: a rule list for
  plain-English requests, and an instruction to every AI request and call)
- ~~**Register that follows yours**: a short message gets a short answer, a voice note a spoken one.~~ (0.5.18: by
  length band only, `persona.register`)

What people have asked for, open and done, is in [REQUESTED.md](REQUESTED.md). Have an idea? Open an issue on GitHub.
