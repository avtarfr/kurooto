# Classes, timetable and calendar

Tell Kurooto your subjects and when your classes are, and it stops calling you during class, asks after each class
what was worth keeping, brings your doubts back before the next lecture, and knows your term's holidays and exams.
Your calendar can feed it too. Everything on this page runs on your computer; only the parts that use your AI say so.

- [Subjects and timetable](#subjects-and-timetable)
- [Skipping a class](#skipping-a-class)
- [Term dates and holidays](#term-dates-and-holidays)
- [The term note](#the-term-note)
- [Calendar](#calendar)
- [Class calendars](#class-calendars)
- [Class packs](#class-packs)
- [After-class notes](#after-class-notes)
- [Doubt queue](#doubt-queue)

---

## Subjects and timetable

**What it does.** Keeps your courses, each with short names ("la" for Linear Algebra), and an optional weekly
timetable. Other features use them: after-class notes, doubts, the quiz, the hint ladder, the study tracker, study
packs, books, start-by dates and deadlines. With a timetable, Kurooto never calls you during a class, or in the 5
minutes before one.

**Turn it on.** Dashboard → Features → Subjects and timetable. It needs nothing else.

**From Telegram.**

| Command | What it does |
|---|---|
| `/subject add Linear Algebra (la, linalg)` | adds a subject; the words in brackets are its short names. `add` is optional: `/subject Statistics (stats)` works too. Adding a subject with the same name again replaces its short names. |
| `/subject` | lists your subjects and their short names |
| `/subject remove la` | removes a subject you added (by name or short name) |
| `/subject policy la hints` | the course's AI policy: `allowed`, `hints` or `off` (`/subject policy la` shows it, `clear` unsets it). [Check my draft](books-and-study.md#check-my-draft) and the [Hint ladder](quiz-and-exams.md) go by it; it's also the AI help box in the dashboard's Study pane |
| `/class mon 09:00-09:55 la` | adds a class: a day (`mon`…`sun`, longer names work), a start and end time, and the subject. A class at the same day and start time replaces the old one. The subject must exist first (Kurooto says so if not). |
| `/classes` | your whole week's timetable |
| `/classes today` | today's classes, marked "(skipping)" where you skip one |

A subject is matched by its full name, its id (`linear-algebra`) or any short name, in any case. A word of four
letters or more that is part of a subject's name also matches ("algebra").

**From a photo of the timetable.** Send a photo of your timetable with `timetable` (or `dates`) as its caption: your AI
reads it and offers its classes with one button, **Add N classes to my timetable**. Each class is added unless one
already starts then, and a course you don't have yet becomes a subject (give it a short name with `/subject add Name
(short)`). Nothing is added before you tap ([reminders-and-deadlines.md](reminders-and-deadlines.md#photo-to-dates)).

**No calls during class.** While a class is on (from `subjects.margin_min` minutes before it starts until it ends),
calls wait. A call that comes due then is held, you're told ("Held a call until 10:00 (class: Linear Algebra)"), and
it rings by itself when the class ends. Your wake-up alarm is not held. Classes don't hold calls on holidays, in exam
periods, after the last day of classes, or for a class you skip.

**On calls.** The brief your calls start with includes today's classes. The evening debrief call goes through what
each class covered. The assistant on a call can mark a class skipped for you ("I'm not going to Statistics today").

**Settings that matter** (Dashboard → Settings → Subjects and timetable)

| Setting | Default | Effect |
|---|---|---|
| `subjects.no_calls_in_class` | on | off: classes no longer hold calls |
| `subjects.margin_min` | 5 | minutes before a class when calls already wait |
| `subjects.list`, `subjects.timetable` | empty | what `/subject` and `/class` fill in (lists, typed as JSON on the Settings page) |

**Limits and edge cases.**
- `/class remove mon 09:00` removes one of your own classes ("Removed the class on Mon 09:00."). A class from a term
  note or a class pack is changed there instead.
- Times are 24-hour (`14:00-14:55`).
- Short names also come from what you say: "by POTA I mean Physics of the Atmosphere" or "I call stochastic calculus
  stoch" adds one, with an Undo button (see [Teaching Kurooto](teaching-kurooto.md)). So does using one: "LA problem
  set" in two messages, when Linear Algebra is the only subject whose initials are LA, makes "LA" its short name
  (written in capitals; never one that fits two subjects).
- Classes from a term note, a class pack or a class calendar join yours; where two say there's a class at the same day
  and time, yours wins.

**What leaves your computer.** Nothing.

**Turn it off.** Features → Subjects and timetable → Turn off. Features that need it (after-class notes, doubts, hints,
study tracker, class packs) must be turned off first. Your subjects and timetable stay in Settings.

## Skipping a class

**What it does.** Tells Kurooto you're not going to a class. For that class there's no after-class question, it isn't
in your day's classes on calls and the morning plan, and calls are allowed during it.

**From Telegram.**

| You send | What happens |
|---|---|
| `/skip la` | skips today's Linear Algebra (several: `/skip la, stats`) |
| `/attend la` | undoes `/skip` for today |
| "skipping LA today", "not going to stats tomorrow", "not attending LA on Friday", "missing topology", "bunking LA" | marks that day. Works for today, tomorrow, the day after and a weekday name. |

A question ("can I skip LA on Friday?") is never taken as a skip. A day Kurooto can't pin down ("next week", a date)
goes to your AI, which can use the same skip tool. A plain-English skip must name exactly one subject.

**On calls.** Say you're skipping a class; the wake-up call also asks which classes you're skipping today.

**What leaves your computer.** Nothing. **Undo:** `/attend la` for today; a skip for another day ends by itself.

## Catching up on a class you missed

**What it does.** A class you skipped, or one that was over before you were up (you answered the alarm, said "I'm
awake", or sent your first message of the day after it ended), gets:
- a catch-up task in [Deadlines](reminders-and-deadlines.md), "Catch up: Point Set Topology (Fri 23 Oct class)", due
  when that course's next class starts (with none in the next two weeks, in 3 days at 18:00);
- a lecture note for that day: the one you already have, else a short one to fill in ("## What was covered").

With Google Classroom on ([Google](google.md)), the message and the short note also list what was posted on Classroom
that day for that course (title and link): "on Classroom that day: Slides: radiative transfer https://...". Posts
that come later that day join the short note while you haven't written in it. Without Classroom it works the same,
minus that list.

One message lists them once the classes are over (it looks every 30 minutes), each with a **Went to ...** button for
a class you did go to: it takes the task back, and the note too if you haven't written in it.

**Went to it, by place** (`subjects.attend_by_place`, off, 0.9.0). With the phone app's places sense on (Brain), the
phone arriving at a place you saved while a class is on (from a quarter of an hour before it starts) asks once:
"You've arrived at a place you saved while Topology (10:00) is on. Went to it?" **Went** means no catch-up for it.
Nothing is decided from where the phone was: no answer, and the catch-up comes as usual; a class you `/skip` is never
asked about. The place's name isn't used or said.

**Settings.** `subjects.catch_up` (on). **What leaves your computer.** Nothing (the Classroom posts come from what
Kurooto already read). **Undo:** **Went to ...**, or tick the task off in Deadlines; turning the setting off stops new
ones.

## Commitments (gym, shifts, standups)

**What it does.** The regular things in your week that aren't classes, each on its days and hours. While one is on,
calls wait for it the way they wait for a class; a shift that runs past midnight holds them until it ends. Turn it on
in Features → Commitments, or just say one (below).

**From Telegram.**

| You send | What happens |
|---|---|
| `/busy add gym mon,wed,fri 18:00-19:00` | adds it. Days: `mon,wed`, `tuesday and thursday`, `weekdays`, `weekends`, `daily`, `mon-fri`. A longer name works: `/busy add night shift daily 22:00-06:00` |
| `/busy` | lists them, with today's skips |
| `/busy skip gym`, "skipping gym today", "not going to the gym tomorrow" | that day it doesn't hold calls; `/busy unskip gym` undoes today's |
| `/busy calls standup off` | keeps it listed but lets calls through (`on` to undo) |
| `/busy remove gym` | removes it |
| "every Tuesday and Thursday at 7pm I go to the gym", "I work a shift every weekend from 9 to 5", "we have standup every weekday at 10", "gym Tue Thu 7am" | added for you (an hour unless you say the end), with an Undo button; Commitments is turned on if it was off |
| "I have lab every Thursday 2-5" (no course named) | "lab" added, Thu 14:00–17:00, with a line on how to make it a class |
| the nightly look back sees the same thing at the same time on 3+ weeks (a study session, calls held) | it asks once, with **Add** / **No** ([Teaching Kurooto](teaching-kurooto.md#nightly-look-back)) |

Things with class, lab, lecture, tutorial, quiz or test in them aren't taken as commitments: classes go in the
timetable, quizzes and tests in Deadlines. The one exception is a bare "lab", "tutorial", "seminar" or "lecture"
with no course named, which becomes a commitment of that name. These aren't Skills' routines (`/every`), which run a skill on a schedule.

**On calls.** Kurooto knows today's commitments and can mark one skipped when you say so.

**Hooks: a word that starts a hold.** For the things that don't keep a timetable, give Kurooto a word:

| You send | What happens |
|---|---|
| "when I say gym, hold calls 90 min" | keeps the hook: "Hook set: "gym" on its own holds calls for 90 min", with **Undo**. Nothing is held yet |
| "when I say lab, hold everything 2 h" | "everything" is [focus](talking-to-kurooto.md#status-pause-hold-and-focus): calls wait, and messages that can wait are kept until it ends |
| `gym` (the word on its own) | the hold starts now: "gym: no calls until 19:42. Messages still come. /calls lifts it.", with **Undo** (puts back what was there before). A longer hold already on is kept |
| `/hooks` | your hooks |
| `/hooks drop gym` | forgets one, with **Undo** |

Only the word on its own starts it: "I'm off to the gym", "gym tomorrow" or "gym?" are ordinary messages. Saying the
same "when I say gym, ..." again changes the hook (its Undo puts the old one back). A hook needs a length ("90 min",
"2 h", "an hour") and calls or everything; without them, or with a word as common as "ok" or "done", Kurooto says how
to put it and sets nothing. A hook only holds calls and messages for you: it never sets or moves an alarm and never
sends anything to anyone.

**Settings.** `commitments.items` (the list), `commitments.no_calls` (on: they hold calls), `commitments.hooks` (your
hook words: `{"word": "gym", "hold": "calls", "minutes": 90}`, `"hold": "all"` for everything).

**What leaves your computer.** Nothing. **Undo:** `/busy remove <name>`, `/hooks drop <word>`, or turn it off in
Features (the lists stay).

## Term dates and holidays

**What it does.** Knows when classes stop. On holidays, in exam periods and after the last day of classes there are
no classes: no after-class questions, no doubt reminders, and the timetable doesn't hold calls.

**From Telegram.**

| Command | What it does |
|---|---|
| `/term` | the last day of classes, the exam periods, and what your term note says (with the next three key dates) |
| `/term ends 2026-12-04` | sets the last day of classes |
| `/term exams 2026-12-07 to 2026-12-18` | adds an exam period (add as many as you need) |
| `/term clear` | removes the last day and every exam period you set this way |

Dates are always written `YYYY-MM-DD`.

**Settings that matter** (Dashboard → Settings → Subjects and timetable)

| Setting | Default | Effect |
|---|---|---|
| `subjects.holidays` | `[]` | dates with no classes, e.g. `["2026-12-25"]` (no command for these: add them here or in the term note) |
| `subjects.exam_periods` | `[]` | what `/term exams` fills in |
| `subjects.term_ends` | empty | what `/term ends` sets |

Exam periods also feed [Exam season](quiz-and-exams.md#exam-season) and [staged updates](updates-and-backups.md).

## The term note

**What it does.** Instead of typing classes and dates one by one, keep them in a note and point Kurooto at it. Kurooto
reads it again whenever it changes (it looks every 10 minutes): its subjects, classes, holidays, exam periods and last
day of classes count from then on, and its quizzes, exams and deadlines go onto your
[deadline list](reminders-and-deadlines.md). Your note itself is never changed.

**From Telegram.**

| Command | What it does |
|---|---|
| `/term note terms/2026-autumn` | reads that note from now on (with or without `.md` or `[[ ]]`). If the note isn't found, nothing changes and you're told. |
| `/term note maps/semester-*` | a pattern: the note for the current term among the matches, else the newest name (semester-10 comes after semester-9) |
| `/term note auto` | `terms/*` in your notes (or `maps/semester-*` in the zettelkasten layout) |
| `/term note` | what it read: how many classes, holidays, exam periods and key dates |
| `/term note off` | stops reading it; its classes and dates stop counting and its dated items leave the deadline list |

The `/term-setup` skill writes such a note for you from what you tell it (see [Skills](skills-and-routines.md)).

**What the note looks like.** Two tables, each under its own heading:

```
## Weekly timetable
| Day | Time | Subject | Code |
| :--- | :--- | :--- | :--- |
| Mon | 09:00-09:55 | [[linear-algebra/course|Linear Algebra]] | MA101 |
|     | 11:00-11:55 | Statistics | |
| Tue, Thu | 2:00-2:50 pm | Statistics | |

## Key dates
| Date | What |
| :--- | :--- |
| 2026-10-02 | Holiday |
| 2026-10-19 – 2026-10-23 | Mid-term break |
| 2026-11-12 | Linear Algebra midterm (10:00-11:00) |
| 2026-11-20 17:00 | Statistics project due |
| 2026-12-04 | Last day of classes |
| 2026-12-07 – 2026-12-18 | End-term exams |
```

- **Weekly timetable** (a heading with "timetable" in it). Columns are found by name: Day; Time (or Start and End);
  Subject, Course or Class; an optional Code. Without those names: day, time, subject in that order. An empty Day
  continues the row above; "Tue, Thu" means both days. The subject can be plain text or a link to its notes. A Code
  becomes a short name for the subject. Lunch and break rows are skipped. Optional Type (lecture, lab, tutorial,
  elective) and Batch (a lab batch such as "A") columns are kept for [class packs](#class-packs).
- **Key dates** (a heading with "dates" in it). Dates as `YYYY-MM-DD`; a range as "A – B", "A - B" or "A to B"; a
  time after the date or in the text ("(10:00-11:00)", "5 pm"). What each row means, from its words, or from a Kind
  column (holiday, break, exams, last day, exam, quiz, due) if you add one:
  - holiday, break, vacation, recess, "no classes": no classes those days;
  - "last day of classes" (or of instruction, teaching, lectures), "classes end": the term's last day;
  - an exam period (a range, or "exams", "examinations", "exam week"): no classes then;
  - a quiz, test, exam, midterm or viva: a dated exam on your deadline list (exam mode and quiz offers follow);
  - due, deadline, submission, assignment, report: a deadline, but only when it names one of your subjects (or Kind
    says "due");
  - anything else is just shown by `/term`.

What you set with `/class` and `/term` wins where it and the note disagree.

**Settings that matter**

| Setting | Default | Effect |
|---|---|---|
| `subjects.term_note` | empty (off) | the note's path, a pattern, `auto`, or empty |
| `deadlines.from_term_note` | on | off: the note's quizzes, exams and deadlines stay off the deadline list |

**Limits and edge cases.** If the note you named disappears, `/health` and `kurooto doctor` say so ("the term note …
isn't in your notes"). `/term` says "Term note …: not found" when the path is wrong: paths are relative to your notes
folder.

## Calendar

**What it does.** Reads your calendar's events (read-only; nothing is ever changed in it). You get `/today` and
`/cal`, today's events on calls and the morning page, no calls during events, focus time from tagged events, private
events shown only as busy, and optionally a reminder before each event.

**Turn it on.** Dashboard → Features → Calendar, then paste your calendar's **private iCal link** in its card:
- **Google Calendar** (on a computer): Settings → your calendar on the left → Integrate calendar → **Secret address in
  iCal format** → copy.
- **Outlook** and **Apple Calendar** have a similar private or published iCal link (it ends in `.ics`).
- Links starting `webcal://` are accepted too. Add more calendars by pasting more links, one at a time.

The link lets anyone who has it read that calendar, so Kurooto keeps it in your computer's keychain, not in Settings.
No such link (some school accounts), or two Google accounts at once? Set up
[Google Calendar](google.md#google-calendar) instead: it reads your calendars through Google and turns this feature on.

**From Telegram.**

| You send | What you get |
|---|---|
| `/today` | today's events |
| `/cal` | the next 7 days (only days with something on) |
| "what's on today?", "what's on tomorrow?", "tomorrow's schedule", "anything planned tomorrow?" | that day's events, at once |
| `/cal classes …` | see [Class calendars](#class-calendars) |

**No calls during events.** Every timed event holds calls (all-day events don't). A call that comes due is held until
the event ends. If that is too much, set `calendar.nocall_events` to `tagged`: then only these hold calls:
- events with `#nocall` in the title or description (all-day ones too, e.g. "Exam day #nocall");
- every event in a calendar whose name contains "no call".

**Focus events.** An event with `#focus` in its title or description is focus time while it runs: calls are held and
messages that can wait are kept, then delivered together when it ends (see
[Focus](talking-to-kurooto.md)).

**Private events.** An event marked private (Google's **Private** visibility, `CLASS:PRIVATE` in an iCal calendar, or
`#private` in its title or description) shows as **Busy (private)** everywhere Kurooto shows or says it: `/today`,
`/cal`, the dashboard, calls, reminders and the AI. Only its time is kept. It still holds calls like any event.

**Reminders before events.** Set `calendar.remind_min` (say `10`) and a message comes that many minutes before each
timed event: "Seminar at 14:00 (Room 2)." These count as your own reminders, so the daily message limit never holds
them back. A reminder missed while the computer slept (more than 10 minutes late) is dropped.

**Deadlines from your calendar.** Events whose title looks like a deadline or exam ("due", "deadline", "submit",
"assignment", "homework", "report", "quiz", "exam", "midterm", "test", "viva"…) go onto your
[deadline list](reminders-and-deadlines.md) (`deadlines.from_calendar`).

**On calls and the dashboard.** Today's events are in every call's brief, the morning page, the wake-up call's plan,
and the dashboard's **today** corner. Start-by dates count your timed events as busy time.

**Settings that matter** (Dashboard → Settings → Calendar, and → Availability for the keywords)

| Setting | Default | Effect |
|---|---|---|
| `calendar.remind_min` | 0 (off) | minutes before each timed event for a reminder |
| `calendar.no_calls_in_events` | on | off: events never hold calls |
| `calendar.nocall_events` | `all` | `tagged`: only `#nocall` events and "no call" calendars hold calls |
| `calendar.days` | 14 | how many days ahead events are read |
| `calendar.refresh` | `every 15m` | how often the calendar is read again |
| `calendar.mask_private` | on | off: private events show their titles again (here and to your AI) |
| `calendar.private_keyword` | `#private` | the word that makes an event private |
| `calendar.class_calendars` | `[]` | see [Class calendars](#class-calendars) |
| `availability.nocall_keyword` | `#nocall` | the word that makes an event hold calls in `tagged` mode |
| `availability.nocall_calendar` | `no call` | calendars whose name contains this hold calls in `tagged` mode |
| `availability.focus_keyword` | `#focus` | the word that makes an event focus time |
| `deadlines.from_calendar` | on | off: calendar events never become deadlines |

**Limits and edge cases.** The link must be `https://`. A calendar file over 20 MB is cut off. Calendars in Outlook's
Windows time-zone names are read in your own zone. Events far ahead (past `calendar.days`) aren't known yet, so start-by
dates see those weeks as freer than they are. A link (or a Google account) that can't be read for a while keeps the
events it last gave; the others still update.

**What leaves your computer.** Nothing is sent: Kurooto only downloads your calendar from its link. Event descriptions
are read only for `#nocall`, `#focus` and `#private` and aren't kept.

**Turn it off / undo.** Features → Calendar → Turn off. `calendar.nocall_events` = `all` brings back "every event
holds calls"; `calendar.mask_private` = `false` shows private titles again.

## Class calendars

**What it does.** If your timetable lives in a calendar (a "Timetable" calendar, a lab calendar), mark that calendar as
classes. Its events then count as classes: no calls during them (with the class margin), they're in your day's
classes on the morning call, the evening debrief and the dashboard, `/skip` works on them, and an event whose title
names one of your subjects ("Linear Algebra lecture") gets the [after-class question](#after-class-notes).

**From Telegram.**

| Command | What it does |
|---|---|
| `/cal classes` | which calendars count as classes now, and the names of all your calendars |
| `/cal classes Timetable` | events in calendars whose name contains "Timetable" are classes (several: `/cal classes Timetable, Labs`, up to 10) |
| `/cal classes none` | no calendar counts as classes |

A timetable class at the same time isn't counted twice. Needs Calendar (or Google Calendar) and Subjects.

## Shared class calendars

**What it does.** Friends in the same course, or the course itself, keep one calendar of its deadlines and exams; you
subscribe to it by its iCal link. Kurooto has no shared server between friends, and doesn't need one: the calendar
lives where its owner keeps it (Google Calendar, Outlook), and each of you reads it. Its events come in like your own,
marked with its name (`10:00–11:00  Quiz 3 (from LA class)` in `/today` and `/cal`). Entries that look like a
deadline or an exam ("PS5 due", "Quiz 3", "Midsem") come with an **Add** button each, once each; they're never added
to Deadlines by themselves, since anyone with edit access to that calendar wrote them. Nothing goes back: what you add
or skip stays on your computer.

**Get the link.** The calendar's owner: Google Calendar → Settings → the calendar → Access permissions → Make
available to public, then Integrate calendar → Public address in iCal format (or share the secret address with the
class only). Outlook: Calendar settings → Shared calendars → Publish a calendar → ICS.

| Command | What it does |
|---|---|
| `/cal subscribe <iCal link> as LA class` | subscribe (webcal:// links work); without "as", the calendar's own name |
| `/cal shared` | the calendars you subscribed to |
| `/cal unsubscribe LA class` · `/cal unsubscribe 1` | drop one |

Or on the dashboard: Features → Calendar → Set up, in "a class calendar someone shares"; that also works with no
calendar of your own. Its events hold calls like your own events do (`calendar.no_calls_in_events`), and `/cal classes
<its name>` makes its events classes. `calendar.shared_offer` off: its entries only show as events. The link is kept
in your keychain.

## Holiday calendars

**What it does.** Public holidays without typing dates in: add your country's holiday calendar to Calendar (Google
Calendar: Other calendars → Browse calendars of interest → Holidays → your country; then that calendar's iCal link
in Calendar's setup) and mark it. Its all-day events become holidays: no classes those days, no after-class
questions, nothing held for classes. Timed events in it aren't holidays. It reads as far ahead as Calendar does
(`calendar.days`, 14).

| Command | What it does |
|---|---|
| `/cal holidays` | which calendars mark holidays now, and the names of all your calendars |
| `/cal holidays Holidays in India` | all-day events in calendars whose name contains that are holidays (several with commas) |
| `/cal holidays none` | no calendar marks holidays |

Setting `calendar.holiday_calendars`. Holidays you list yourself (`subjects.holidays`) and the term note's still count.

## Class packs

**What it does.** One person turns the section's setup into a small file; everyone else sends it to their own Kurooto
and has the timetable, term dates, holidays, recurring quizzes and dated exams from day one, after ticking their own
electives and lab batch.

**Turn it on.** Dashboard → Features → Class packs (needs Telegram and Subjects).

**What a pack carries, and nothing else:** the courses (names, short names, which are electives), the weekly
timetable (lecture, lab or tutorial, and a lab batch), the term (last day of classes, holidays, exam periods),
recurring quizzes, dated exams, and the day the maker checked it against the official timetable. The file is strict
JSON named `<name>.kurooto-course`, at most 200 KB. A field it doesn't know makes the whole file invalid, so there is no
place in it for names, keys, notes, skills, your skips or your own deadlines, and every piece of text in it is checked
for an email address, phone number, link, @handle, file path or anything that looks like a key. A file that breaks a
rule is refused whole, with the reason.

**Making one.**
1. `/classpack export` makes a pack of your own setup: subjects, timetable, term note, `/term` dates and holidays,
   recurring quizzes. For the whole section (every elective, every lab batch), keep a [term note](#the-term-note)
   whose timetable has Type and Batch columns and add a `## Recurring quizzes` table, then
   `/classpack export from terms/section-b` reads that note alone.
2. Kurooto's message lists what's in the pack and what it left out (and why), with a button per course to mark it an
   elective (`[x]` ticked).
3. Reply to change anything: `title Year 2 section B`, `electives ml, topology`, `la elective` / `la core`,
   `la quiz off`, `la quiz fri 11:00`, `holiday 2026-10-02 off`, `checked 2026-10-18`.
4. Check it against the official timetable, then tap **Checked today, make it** (or reply `checked 2026-10-18`; a date
   in the future is refused). The file comes to your Telegram for you to forward; a copy stays in Kurooto's data folder
   (`classpacks/`).

Example of the extra columns and table in a section's term note:

```
## Weekly timetable
| Day | Time | Subject | Code | Type | Batch |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Mon | 09:00-09:55 | Linear Algebra | MA101 | | |
| Thu | 14:00-16:55 | Statistics | | Lab | A |
| Fri | 14:00-16:55 | Statistics | | Lab | B |
| Wed | 10:00-10:55 | Machine Learning | | Elective | |

## Recurring quizzes
| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Linear Algebra | Quiz | 1 | Thu | 10:00 | | |
```

Write a lab under its course's name ("Statistics", Type Lab) so it stays one course.

**Importing one.** Send the `.kurooto-course` file to your bot. Nothing counts yet: a review shows when it was checked
(where it and the official timetable differ, the official one is right), what's in it and what it means for you
("N classes a week"). Then:
- tap the electives you take (`[ ]` / `[x]`) and your lab batch (**Batch A**, **Batch B**…; tap again to untick);
- reply to change something: `la quiz off`, `la quiz fri 11:00`, `electives ml`, `batch B`, `la reset`;
- **Show again** sends the review again; **Import** makes it count; **Cancel** drops it.

If Class packs is off when you send the file, Kurooto says to turn it on and send it again. Sending the pack you
already have changes nothing.

**After importing.** The pack sits under your own setup, never in it: your own `/class` classes, `/term` dates, term
note and recurring table win where they say something else, and nothing is written into your notes. Its classes keep
calls away like yours, its holidays and exam periods have no classes, and its quizzes and exams reach your deadline
list (with `deadlines.recurring` and `deadlines.from_term_note` on). `/recurring` marks its quizzes "(class pack)".
After a mid-term reshuffle, send the new pack: the review lists what changes for you (classes moved, holidays, quiz
times, exam dates) before anything does, and keeps your electives, batch and changes.

| Command | What it does |
|---|---|
| `/classpack` | what you have: the pack, your electives and batch, your changes |
| `/classpack export [from <note>]` | make a pack (above) |
| `/classpack set <change>` | change it later: `electives ml, topology`, `batch B`, `la quiz off`, `la quiz on`, `la quiz fri 11:00`, `la reset` (back to what the pack says), `all reset` |
| `/classpack remove` | takes the pack out; your own setup stays |
| `/classpack undo` | goes back one step (the pack before a re-import, or back after a remove) |

**From a terminal.**
- `kurooto classpack check FILE`: is this a pack Kurooto can use, and what's in it.
- `kurooto classpack export --checked today [--from terms/section-b] [--title "Year 2 section B"] [--elective machine-learning] [--out FOLDER]`
- `kurooto classpack import FILE`: sends its review to your Telegram.

**Limits and edge cases.** At most 40 courses, 250 classes, 80 quizzes, 150 exams, 80 holidays and 12 exam periods per
pack; the review shows up to 12 electives and 8 batches as buttons. A pack whose term ended more than two weeks ago
shows up in `/health`. Drafts being made or reviewed are kept for a week.

**What leaves your computer.** Nothing. A pack you make goes to your own Telegram; you decide whom to forward it to.

**Turn it off / undo.** Features → Class packs → Turn off: the pack stops counting and is kept for when you turn it on
again. `/classpack remove` takes it out; `/classpack undo` brings it back.

## After-class notes

**What it does.** A couple of minutes after each class ends, Kurooto asks: "How was Linear Algebra? Anything worth
keeping (a definition, a doubt, homework)?" Your answer goes into that subject's class log in your notes
(`<subject>/class-log.md`, under a heading with the date). Photos and files you send with it are moved next to it
(`<subject>/files/`, or your files folder) and linked. With Chat on, the AI also writes a proper lecture note for the
class (the `/study-log` skill), linked from the day's note.

**Turn it on.** Features → After-class notes (needs Telegram and Subjects with a timetable, a term note, a class pack
or a class calendar).

**Answering.** Reply to the question on Telegram with a line or two, photos of the board or slides, files or a voice
note; or answer in the phone app or on a call.
- **Nothing new** (button, or reply "nothing"): nothing is saved for that class.
- **Later**: keeps the question open for your evening check-in call.
- Unanswered, the question expires after 20 hours.

**When it doesn't ask.** For a class you skipped, on holidays, in exam periods, after the term's last day, for a
class-calendar event that names none of your subjects, and for subjects you left out (below). If the computer was asleep
when the question was due, it still comes when it wakes, up to 3 hours late.

**Settings that matter** (Dashboard → Settings → After-class notes)

| Setting | Default | Effect |
|---|---|---|
| `capture.delay_min` | 2 | minutes after the class ends |
| `capture.study_log` | on | with Chat on, the AI writes a lecture note from your answer |
| `capture.subjects` | `[]` (every subject) | ask only after these subjects' classes, e.g. `["la", "stats"]` |
| `capture.skip_subjects` | `[]` | never ask after these, e.g. `["pe"]` |

A subject's short name, full name or alias works in both lists. A class left out still comes up in the evening debrief
like any class without a log.

**Why it messaged you.** These questions come by themselves, so they count against the
[daily message limit](messages-it-sends.md). **Less of this** on one offers **Stop** (turns After-class notes off),
**Fewer** (no more questions for that one subject) or **Another time** (they wait for the evening bundle). If you
rarely answer them, the monthly suggestion may offer to turn the feature off.

**What leaves your computer.** Nothing, unless Chat is on: then your answer and the photos and files you sent with it go
to your AI to write the lecture note.

**Turn it off / undo.** Features → After-class notes → Turn off. To ask about every subject again, empty both lists.

## Doubt queue

**What it does.** A doubt from class, kept for the next one. It's added as a task line to that subject's doubts note
(`<subject>/doubts.md`): `- [ ] why does the rank not change? (2026-10-20)`. Half an hour before the subject's next
class, its open doubts come to you as one message with a **Tick** button per doubt. No AI answers them: they're for
asking in class, a tutorial or office hours.

**Turn it on.** Features → Doubt queue (needs Subjects).

**From Telegram.**

| You send | What happens |
|---|---|
| `/doubt la why does the rank not change?` | adds it to Linear Algebra's doubts |
| "I have a doubt about eigenvalues", "doubt: why is the trace basis-free" | adds it (short, one-sentence doubts; longer ones go to the AI, so use `/doubt`) |
| `/doubts` or "show my doubts" | every subject's open doubts, with **Tick** buttons |
| `/doubts la`, "show my doubts for LA" | one subject's |

**Which subject.** The one you name (its name or short name, anywhere in the doubt); else the class that's on now or
ended in the last 3 hours; else buttons ask which subject.

**Buttons.** **Tick 1**, **Tick 2**… tick that doubt in the note (`[x]`). Ticking it by hand in the note works just as
well. A message lists up to 8 doubts; the rest are named by where they are.

**Settings that matter** (Dashboard → Settings → Doubt queue)

| Setting | Default | Effect |
|---|---|---|
| `doubts.before_min` | 30 | minutes before the subject's next class when its open doubts come |
| `doubts.recent_h` | 3 | a doubt naming no subject is for the class that ended this many hours ago |
| `notes.paths.doubts` | empty | your own place for doubts notes (see [notes layout](notes-and-concept-graph.md)) |

**What leaves your computer.** Nothing.

**Turn it off.** Features → Doubt queue → Turn off. The doubts notes are yours and stay.
