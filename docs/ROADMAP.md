# Roadmap

Ideas that aren't built yet. Nothing here is promised; each one ships as an opt-in feature through the normal
signed updates when it's ready.

## Next
- **Your notes, your layout.** Choose where Kurooto writes: the daily note, subject folders, the inbox, your
  profile. It then fits an existing notes system instead of bringing its own.

## From the ideation panel (2026-10-23)
Seven viewpoints (student, researcher, notes, phone, AI, friends, skeptic) argued these out; the most backed first.
- **Link recall cards.** The concept graph's links become review cards ("how does Itô's lemma relate to
  Fokker–Planck?"), answered in your own words and graded by you (a small local model may check, never the free
  key). A miss points to the book pages. Up to five a day, also as phone notifications, never in class or focus.
  Papers opened from the research digest go through Books into the graph and get the same cards.
- **Revision plan.** When exam season starts, a course's topics are ranked (no note, stub, weak recall, the rest)
  and laid over Start-by's free slots with the pages to read; the evening check-in asks "did you cover X?" and feeds
  the same recall score as the quiz. Plain arithmetic, no AI.
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
- **Egress ledger, enforced.** Every request Kurooto makes goes through one place that records host, feature and
  bytes and blocks hosts not listed in PRIVACY.md; `/egress` shows the week. Requests your AI program makes itself
  show as "handed to agy / Claude Code".
- ~~**Retention.** `privacy.keep_days` (30) expires transcripts, prompts, answers, audio and logs, also the call
  line's queued copies; `/forget 7d`.~~ (0.5.15: nightly, call transcripts, AI requests' words, chats, questions,
  cases, sent messages' words, the search index and log lines; `/forget 7d`, `/forget all` with a confirm button.
  Voice recordings stay, being in your notes; the call line's queue is emptied whenever the computer connects)
- **Problem-set progress.** (0.5.10 has "ps3 4/7" in chat and on calls, shown in lists and Start-by, which plans from
  what's left; still to come: replying "4/7" to a deadline message, +1 on the phone.) Deadlines with parts (Q1–7):
  reply "4/7" or tap +1 on the phone; Start-by plans from what's left; the morning says "ps3 4/7, due Fri".
- **Phone outbox.** Captures and taps made while the laptop sleeps wait on the call line and merge on wake; a home
  screen widget and a capture tile (launcher shortcut on Android 6).
- **iPhone Shortcut.** Pairing an iPhone ends with a ready "Tell Kurooto" Shortcut (Siri, Back Tap) with a
  revocable link.
- **CPU micro-helper.** A ~1 GB model for one-word decisions only (effort, intent, yes/no) on laptops without a
  graphics card, enabled only if a speed test passes, offered after week 2 when the free limit is being used up.
- **Notation crosswalk.** When a concept appears in a second source, its notation and conventions are written side
  by side (B_t vs W_t, Fourier 2π), quote-checked like every graph claim.
- **Near-duplicate concepts.** "Wiener process" and "Brownian motion": Merge / Keep both / Add alias.
- **Supervisor meeting brief.** (0.5.10 has the brief from the project note; still to come: a voice note becoming
  minutes, action items becoming deadlines.) The evening before a tagged meeting, a page from the project log since the last
  one; after it, a voice note becomes minutes, and action items become deadlines on a tap.
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
- **Make the panel's ideas general**: link recall cards and the revision plan also draw on course notes and Classroom
  files, not only books; the meeting brief is for any recurring meeting ("With: X", their role in your own word: guide,
  manager, coach); "check my attempt" becomes "check my draft" (essays, accounts working, code, proofs); missed-class
  catch-up works without Classroom.
- **A Research add-on** for the narrow ones: notation crosswalk, run compare, LaTeX tracker, proof checking. Bedside
  mode is an Android add-on.
- ~~**No college-term defaults**: the check-in times and Start-by's day window are learned from when you actually
  reply (with a notice and Undo), not 09:00-22:00; a first-run question (student, working, research, other) picks the
  features; public holidays come from your country's calendar.~~ (0.5.9: learned check-in times and window, "What do
  you do?" in the wizard, holiday calendars)
- **The phone app as a full chat channel** beside Telegram, for places where Telegram is blocked or little used.
- **Small gaps**: ~~`add_deadline` takes the course, so a mail's "Lab report" lands on the right course page~~
  (0.5.15: `course` by name or short name; an unknown one is said, never guessed); a recurring fact said in chat
  becomes a class, a recurring quiz or a routine instead of being dropped; the nightly look back can propose routines
  and acts on data changes with Undo instead of waiting for a tap; project notes keep "With:", "last met" and
  "## Next steps"; subject aliases are learned from how you name them.
- ~~**Routines for people who aren't students**: gym, shifts, standups, tuition; they hold calls like a class does.~~
  (0.5.9: Commitments, `/busy`, also set up from what you say)
- **Never without a tap**: setting or moving an alarm, placing calls, reading new mail senders, sending anything out,
  attaching a code repository to a project. Repositories are never searched for on the disk.

## Human-like (2026-10-23)
- ~~**Your real body clock**: the night hours move to when you're actually quiet (nights into the afternoon too), the
  morning things follow, and the alarm suggests your usual time when none is set.~~ (0.5.18: `availability.learn_night`
  and `learn_morning`, `alarm.suggest`, with Undo; never ones you set)
- ~~**Lighter days after heavy ones**: after an exam or a long study day, fewer messages, the first check-in later, and
  one line in the morning with Not today.~~ (0.5.18: `notify.calm.lighter_after`)
- ~~**Noticing absence**: two days without a word from you brings one gentle message, never a call, with I'm fine /
  Busy, quiet for a week.~~ (0.5.18: `availability.absence_days`)

## Ideas
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

What people have asked for, open and done, is in [REQUESTED.md](REQUESTED.md). Have an idea? Open an issue on GitHub.
