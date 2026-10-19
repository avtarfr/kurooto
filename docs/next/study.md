# study: deadlines, recurring quizzes, the not-interested list, exam mode, quizzes (for the 0.2.0 docs)

## MANUAL: replace "### Deadlines"

### Deadlines
One list of what's due, from:
- what you add: `/due fri 17:00 essay draft`, or "add a deadline: essay draft due friday 5pm";
- dated tasks in your notes, written like `- [ ] Essay draft (2026-11-02 17:00)` (a time like `5:00 PM` works too);
- Google Classroom coursework (with Google on);
- calendar events that look like deadlines or exams: "due", "deadline", "submit", "assignment", "homework",
  "report", "quiz", "exam", "midterm", "test", "viva"... (with Calendar on);
- recurring quizzes and tests (below).

The same thing from two places (say Classroom, your calendar and a task in your notes) is kept once; a known time
beats "end of the day". Topics on your not-interested list are left out.

**The chase**, for things you hand in:
- a day before: a message with **Done / Not mine / Snooze 3 h**;
- six hours before: with Phone calls on, **a call** ("is it done, or how will you finish it?"). It waits out
  classes, `/hold`, focus and the night; when that would leave less than half an hour, or Phone calls is off, you
  get an urgent message instead. A missed call also becomes that message;
- after the due time: **Overdue?** with **Done / New date / Drop**. New date asks you for the date (reply, or answer
  on the phone or on your next call) and starts the chase over.

**Done** ticks the `- [ ]` box in your notes when the deadline came from one (only that box changes). Quizzes and
exams aren't "done": you get a reminder a day before or, with Quiz on, a practice offer the evening before.

`/deadlines` shows two weeks; "what's due this week?" works too. On calls, the brief has what's due in the next
72 hours, and you can say "the lab report is done", "it got moved to Friday", "add a deadline".

**Settings** (Settings → Deadlines): `ping_h` (24), `urgent_h` (6), `call` (on: the six-hour nudge is a call when
Phone calls is on), `overdue_check` (on), `tick_notes` (on), `from_calendar` (on), `recurring` (on),
`horizon_days` (30: how far ahead recurring quizzes become dated items), `exam_mode_days` (14; 0 turns exam mode
off), `scan_notes` (on).

**Turn off:** the whole thing in Features; the call alone with `deadlines.call` off; the overdue question with
`deadlines.overdue_check` off.

### Recurring quizzes
For quizzes and tests that repeat ("Linear Algebra quiz every Thursday 10:00", "Statistics test every other
Friday"). Say it ("linear algebra has a quiz every thursday"), or `/recurring add la quiz every 2 weeks thu 10:00`.
They live in your notes as a table at `kurooto/recurring.md`, which you can edit like any note:

| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| linear-algebra | Quiz | 1 | Thu | 10:00 | | |

"Every" is in weeks (or "weekly", "every other week"); "Next" is any date it happens on, needed for every two weeks;
"Until" is optional. Each row becomes dated items on the deadline list, so the reminders, exam mode and quiz offers
follow. When the day or time is missing, Kurooto uses the subject's class from your timetable, and asks you when it
can't tell (which day, or which week for every two weeks); for a row you wrote yourself, your answer is kept by
Kurooto and your note is left as it is. Holidays from your subjects settings are skipped.

`/recurring` lists them; `/recurring remove la quiz` removes one (just that row).

### Not interested
Topics you don't care about (a club, a kind of event, a course you dropped): `/ignore drama club`, or say "I don't
care about the drama club". `/ignored` lists them, `/unignore drama club` takes one off. The list is a note,
`about-me/not-interested.md`, one per line (`- drama club`, or `- drama club — not this term`); edit it freely.
Matching deadlines are left out of the list and the chase, and the mail and Classroom digests only count matching
items instead of making tasks from them. Matching is on whole words, ignoring case.

### Exam mode
On by itself two weeks before a quiz or exam (from the deadline list), for that subject; off after it. You're told
once when it starts. While it's on:
- `/exam` (or "when's my next exam?") shows it, with how many questions are due;
- calls start knowing it (pending items);
- quizzes come more often: longer sessions (`quiz.exam_per_session`, 6), items you know still come back before the
  exam, and a short practice check-in every day (`quiz.exam_daily`, 18:00).

Turn it off with `deadlines.exam_mode_days` = 0.

## MANUAL: replace "### Quiz"

### Quiz
Practice questions from your notes, spaced out so you see each again just before you'd forget it. Put a note named
like `exam-prep.md` with a `## Must know` list in a subject's folder (also: "Typical questions", "Definitions",
"Theorems", "Formulas", "Key results").
- `/quiz` or `/quiz la`: a session of a few questions (`quiz.per_session`, 3). Reply with your answer: with Chat on,
  the AI gives the key idea and a grade; otherwise grade yourself with the buttons. The next question follows.
  With Phone calls on, `/quiz` asks **Here or by call?**; `/quiz la call` calls you straight away (it waits out
  classes and other no-call times). "quiz me on topology", "quiz me by call" and "call me for a quiz" work too.
- **The evening before a quiz or exam** (from 19:00, `quiz.offer_at`): "Linear Algebra quiz is tomorrow at 10:00.
  Practise?" with **Quiz me now / Call me for a quiz / Not tonight**. If you haven't any material for it yet, it
  says where to put some.
- **Quiz check-ins**: `/quiz at 21:00 la`, or "quiz me at 9 tonight": the first question arrives then (a call
  instead with `quiz.by_call` on, or "quiz me by call at 9"). In exam mode there's one every day (above).
- On a call: "quiz me" runs a spoken quiz (it picks the exam subject unless you name one).
- `/quizstatus`: items and what's due per subject, and exam mode.

**Settings:** `per_session` (3), `exam_per_session` (6), `offer_at` (19:00; empty turns the evening offer off),
`exam_daily` (18:00; empty turns the daily exam-mode practice off), `by_call` (off), `call_min` (10).

## Troubleshooting rows
| What you see | What to do |
|---|---|
| A deadline shows up twice | They didn't look like the same thing (different dates or numbers in the title). Tap **Not mine** on one. |
| A calendar event became a deadline by mistake | **Not mine** on it, or `/ignore` a word in its title; to stop calendar deadlines altogether, `deadlines.from_calendar` off. |
| No call six hours before | Phone calls on and set up? A class, `/hold`, focus or the night until shortly before the deadline means a message instead. |
| Done didn't tick the box in my notes | The line was changed since Kurooto read it (it's re-read every hour); tick it yourself, nothing else depends on it. |
| A recurring quiz is on the wrong week | Put any date it really happens on in the "Next" column of `kurooto/recurring.md`. |

## CHANGELOG lines (0.2.0)
- Deadlines: calendar events that look like deadlines or exams, and recurring quizzes (a table in your notes,
  `/recurring`) join the list; the same thing from Classroom, the calendar and your notes is kept once.
- Deadlines: the six-hour nudge is a call when Phone calls is on (it waits out classes and other no-call times);
  an "Overdue?" check after the due time (Done / New date / Drop); Done ticks the box in your notes.
- Not interested: `/ignore`, `/ignored`, `/unignore` (or "I don't care about X"); a note you can edit; deadlines
  leave matches out and the mail and Classroom digests only count them.
- Exam mode: on by itself two weeks before a quiz or exam (`/exam`); calls know about it; quizzes come more often.
- Quiz: sessions of several questions; a practice offer the evening before a quiz or exam; quizzes by call
  (`/quiz la call`, "call me for a quiz"); quiz check-ins (`/quiz at 21:00 la`); a daily practice in exam mode.

## PRIVACY notes
- No change to what leaves the computer: Deadlines, recurring quizzes, the not-interested list, exam mode and Quiz
  stay on this computer. Two notes are written in your notes folder (`kurooto/recurring.md`,
  `about-me/not-interested.md`); if Notes sync is on they go wherever your notes go.
- Deadline and quiz calls are ordinary Phone calls: the brief they start from includes what's due in the next 72
  hours, exam mode, and quiz questions (already listed under Phone calls).

## For the catalog / coordinator
- No new module classes. New files: `src/kurooto/core/notinterested.py` (shared helper), `src/kurooto/modules/recurring.py`
  (table helpers, not a module).
