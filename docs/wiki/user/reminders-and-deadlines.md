# Reminders and deadlines

Kurooto keeps two lists for you: **reminders** (a message at a time you pick) and **deadlines** (things that are due,
from everywhere Kurooto can see them, chased until they're done). On top of the deadline list sit recurring quizzes,
a not-interested list, exam mode and start-by dates.

- [Reminders](#reminders)
- [Deadlines](#deadlines)
- [Recurring quizzes and tests](#recurring-quizzes-and-tests)
- [Not interested](#not-interested)
- [Exam mode](#exam-mode)
- [Start-by dates and crunch weeks](#start-by-dates-and-crunch-weeks)
- [Messages these features send by themselves](#messages-these-features-send-by-themselves)
- [When something goes wrong](#when-something-goes-wrong)

---

## Reminders

**What it does.** A message on Telegram at the time you ask for, with two buttons: **+10 min** and **+1 h** (each
sets the same reminder again that much later). An add-on may put a row of its own under them (0.9.0,
`reminders.addon_buttons`, on): for example a grocery add-on's **Order on Zepto** under "buy milk". Its button does
nothing until you tap it, and what it starts asks you again before anything that pays or sends.

**Turn it on.** Features → Reminders. It needs Telegram. It's in the ★ Starter set.

**From Telegram.**

| You send | What happens |
|---|---|
| `remind me at 9 to call mum` | a reminder at the next 9 o'clock (see "Which 9?" below) |
| `remind me in 20 minutes to take the pasta off` | 20 minutes from now (`in an hour`, `in half an hour`, `in 1.5 h` work too) |
| `remind me tomorrow at 7am to go to the gym` | tomorrow 07:00 |
| `remind me tomorrow to pay the fees` | tomorrow 09:00 (a day with no time means 09:00) |
| `remind me tonight to pack` | today 21:00 |
| `remind me friday at 5pm to submit the form` · `remind me on wednesday to call home` | the coming Friday 17:00 (today if it's Friday and 17:00 is still ahead, else a week on); a weekday with no time is 09:00. "next friday" goes to your AI |
| `/remind 21:30 call mum` | 21:30 today, or tomorrow if 21:30 has passed |
| `/remind tomorrow 7am gym` | tomorrow 07:00 |
| `/remind in 20m tea` · `/remind 30m tea` · `/remind +45 tea` · `/remind 2h stretch` | that long from now |
| `/remind in 3 days call the bank` · `/remind 1w renew library book` | days (`d`) and weeks (`w`) work in `/remind` |
| `/remind fri 17:00 submit the form` · `/remind next mon 9am lab` | that weekday (a weekday with no time is 09:00) |
| `/remind 2026-11-02 14:00 dentist` | that date and time (a date alone is 09:00) |
| `/reminders` | your upcoming reminders (up to 15), each with a **Cancel** button |

What's left after the time is the text of the reminder. Words like "to", "that", "about", ":" or "-" at its start
are dropped, so `remind me at 6 pm: call mum` says "call mum".

**Which 9?** Without am or pm, Kurooto picks the sensible one: 1 to 5 mean the afternoon; "tonight", "evening",
"night" or "afternoon" in the sentence mean pm; "morning", "tomorrow", "noon" or "lunch" keep the hour as said;
otherwise it's the next time the clock shows that hour (at 10:00, "at 9" means 21:00). A 24-hour time (`21:30`,
`09:15`) is always taken as written. `call me at 5` and `remind me at 5` mean five o'clock, not five minutes.

**On the dashboard.** The [Today page](dashboard.md) (Alt+T) lists your reminders with **+10 min** and **cancel**.
Type `! 18:30 call mum`, `! in 20m tea` or `! tomorrow 9am gym` in its box to set one. Ctrl+K anywhere on the board
does the same: `remind 18:30 call mum`.

**On the phone and on calls.** On a call, just say it: "remind me at six to buy milk". The AI's `add_reminder` tool
sets it (a reminder *message*; ask for a call if you want it to ring, see [calls.md](calls.md)). With Phone calls on,
your next day's reminders are part of the brief your call line keeps. With
[Reminders with the lid shut](calls.md) on, your Android phone gets them at their time even when the computer sleeps.

### Waiting for a focus's break

With `reminders.wait_for_break` on (off by default, 0.9.0), a reminder of yours that comes during a [Study
mode](books-and-study.md#study-tracker) focus waits for the focus to end, then comes at the break. Pausing or resetting
the timer brings the ones waiting at once. Alarms, deadline calls and location reminders never wait.

### At a place (location reminders)

"Remind me when I reach the library to return the book": the Android app reminds you when you get there. Off by
default, on two switches: **Settings → Reminders → places** on the computer, and **Places** in the phone app (which
asks to use the phone's location only then, and says the battery cost first).

| You say | What happens |
|---|---|
| `remind me when I reach the library to return the book` | once, the next time you arrive at "library" |
| `remind me when I get home: water the plants` | once, at "home" |
| `remind me whenever I'm at the gym to stretch` | every time you arrive at "gym" |

How it works:
- **Places live on the phone.** In the app: Places → Turn on location reminders → type a name → **Save this place**
  while you're standing there (no map). A place counts within 150 m of where you saved it.
- **Your computer only knows the name.** The reminder goes to the app as the place's name and the text. A reminder
  for a place the app hasn't saved yet waits under **Waiting for a place**, with "I'm here: save it as library".
  "The library", "library" and "my library" are the same place.
- **You can add reminders in the app too**: each place has a "Remind me here to…" box, once or every time.
- **When it comes:** a notification "At library: return the book" when you arrive from somewhere else (not while you
  stay there, and not twice within 20 minutes). A once reminder is gone after it's said.
- **Battery.** Android checks where you are a few times an hour while the app is in the background, mostly from Wi-Fi
  and the phone network (the GPS isn't kept on), more often near a saved place. The cost is small, and a reminder
  can come a few minutes after you arrive.
- **Android 10 and newer** ask a second time for "Allow all the time": without it, reminders only come while the app
  is open. Android 6 to 9 ask once.
- It works with the computer off: once the reminder is on the phone, the phone does the rest. No Google Play services
  needed. Not on iPhone.

**Limits and edge cases.**
- **The computer was asleep or off at the time:** the reminder comes as soon as Kurooto runs again, marked
  "Reminder (late: the computer was asleep): ...". Nothing is dropped. With Reminders with the lid shut on, the
  Android app shows it on time instead, and Telegram doesn't repeat it.
- **Paused:** reminders due while Kurooto is paused arrive when it resumes.
- **Focus time** (`/focus`): reminders are your own, so [Calm](messages-it-sends.md) never holds them, but focus
  does hold messages that aren't urgent until it ends.
- **A time about the past** is never used. "remind me, I didn't do it at 3" doesn't set a 3 o'clock reminder: Kurooto
  says it didn't set one and asks when.
- **"Don't", "never", "stop" or "no need to" in the sentence**, or several requests in one message ("remind me at 9
  to call mum and skip the check-in"), go to your AI instead of being handled instantly. With Chat on, the AI can
  still set the reminder with its tool.
- **Plain English understands today, tonight, tomorrow, the day after tomorrow, a weekday and "in ..."**. A weekday
  counts when it says when ("friday at 5", "on friday", "this friday"), not when it's part of what to remember
  ("revise for friday's quiz"). For a date, use `/remind` (`/remind 2026-11-02 14:00 ...`) or ask your AI.
- **A bare number in `/remind` is the hour.** `/remind 9 call mum` is the next 9:00 (morning or evening, whichever
  comes first); `/remind 18 gym` is 18:00. Minutes need their unit: `/remind 20m tea` or `/remind in 20 min tea`.
- **Cancel** with the button under `/reminders` or on the Today page. "Already gone" means it fired or was cancelled.
- The snooze buttons work for the last 200 reminders that fired; older ones say "That reminder is gone".

**What leaves your computer.** The reminder goes through Telegram to your own bot. A location reminder goes to your
phone app through your call line (the place's name and the text); where your places are never leaves the phone. With Reminders with the lid shut
on, the next day's reminders go to your call line sealed for your phone (it can read only their times).

**Turn it off.** Features → Reminders → Turn off. Nothing reminds you while it's off, but the reminders you had set
are kept: turn it on again and they're back, and any whose time passed meanwhile come at once as "Reminder (late:
Reminders was off): ...". To get rid of one, cancel it (`/reminders`) before turning the feature off.

---

## Deadlines

**What it does.** One list of everything that's due, gathered from every place Kurooto can see, and a chase that
doesn't let things slip: a message a day before, a call six hours before, and an "Overdue?" check after.

**Turn it on.** Features → Deadlines. It needs Telegram. It's in the ★ Starter set.

### Where deadlines come from

| Source | How it gets in | Switch |
|---|---|---|
| You | `/due fri 17:00 essay draft`, "add a deadline: essay draft due friday 5pm", "I have a lab report due fri 17:00", on a call, on the dashboard | always |
| Your notes | an unticked task with a date in brackets: `- [ ] Essay draft (2026-11-02 17:00)` (`5:00 PM` works; no time means the end of that day). Ticking `[x]` it in your notes marks it done; deleting the line removes it | `deadlines.scan_notes` |
| Google Classroom | coursework with due dates, marked done when you hand it in ([google.md](google.md)) | the Google feature |
| Your calendar | events whose title says due, deadline, submit, assignment, homework, problem set, report, presentation, quiz, exam, midterm, finals, test, viva... ("solutions", "results" or "graded" don't count). Next two weeks | `deadlines.from_calendar` |
| Recurring quizzes | each row of your recurring table becomes dated items ([below](#recurring-quizzes-and-tests)) | `deadlines.recurring` |
| Your term note | its quizzes and exams, and deadlines that name one of your subjects ([classes-and-timetable.md](classes-and-timetable.md)). A row you take out of the note leaves the list | `deadlines.from_term_note` |
| Mail digest | deadlines it finds in mail it reads ([google.md](google.md)) | Mail digest |
| A photo | a photo of a notice or a timetable: each date it shows comes back with an **Add** button; nothing is added until you tap ([below](#photo-to-dates)) | `deadlines.from_photos` |
| Mail you forward | Email in: mail forwarded to example+kurooto@gmail.com, or given a label, is filed as a note and its dates offered with **Add** buttons ([google.md](google.md#email-in)) | `mail_digest.mail_in` (off) |
| A shared class calendar | a calendar a classmate or the course shares, by its iCal link: its deadlines and exams are offered with **Add** buttons, never added by themselves ([classes-and-timetable.md](classes-and-timetable.md#shared-class-calendars)) | `calendar.shared_offer` |

**The same thing from two places is kept once.** "Linear Algebra: Problem set 3" from Classroom and "Problem set 3"
in your notes on the same day are one item; "Quiz 2" and "Quiz 3" never merge. A known time beats "end of the day".
If two things that are really one still show twice (different numbers or dates in their titles), tap **Not mine** on
one.

**Quizzes and exams are different from things you hand in.** Anything whose title says quiz, exam, midterm, finals,
midsem, endsem, viva, oral, test or assessment counts as an exam: it can't be "done", it gets no six-hour call and no
"Overdue?" question, and exam mode starts before it ([below](#exam-mode)).

### From Telegram

| You send | What happens |
|---|---|
| `/due fri 17:00 essay draft` | adds it (the time first, then what it is) |
| `/due 2026-11-02 lab report` | a date alone means 09:00 that day |
| `/due tomorrow 23:59 reading response` · `/due in 3 days project` | any time `/remind` takes works (a bare number is the hour, as in `/remind`) |
| `add a deadline: essay draft due friday 5pm` · `I have a lab report due fri 17:00` | the same, in words (the part after "due" is the time) |
| `/deadlines` | the next two weeks, soonest first (up to 12), with **Done** and **Not mine** buttons on things you hand in (and **+1** on one with parts still to do) |
| `what's due?` · `anything due?` · `show my deadlines` | the next two weeks |
| `what's due this week?` | the next 7 days |
| `what's due soon?` | the next `deadlines.plan_h` hours (3 days) |
| `/status` | includes "Due in the next 3 days" |
| `ps3 4/7` · `problem set 3 4 of 7 done` · `did 4 of 7 on the stats problem set` | how much of it is done: "Problem set 3: 4/7, 3 to go, due Fri 17:00". The lists show "(4/7)", and [Start-by](#start-by-dates-and-crunch-weeks) plans from what's left (3/7 of its size). Only for a deadline on your list; at 7/7 it reminds you to tap **Done** once it's handed in |
| a reply to a deadline's message: `4/7` · `4` · `+1` · `done` | the same for that deadline, no name needed ([below](#problem-set-progress)), with **Undo** |
| `chem hw is done` · `LA problem set 3 submitted` · `I finished the essay` · `stats hw dun` | marks the open deadline those words name, with **Undo**: "Marked done: Organic Chemistry: Homework 8, due Thu 29 Oct 09:00." See [Done, in your words](#done-in-your-words) |

If you add something that's already on the list, Kurooto says "Already on the list" and keeps one copy (if you had
dropped it, adding it yourself brings it back).

### Done, in your words

Say that something is done, the way you'd say it: "chem hw is done", "LA problem set 3 submitted", "I handed in
the lab report", "I'm done with the essay". Kurooto finds the one open deadline the words name and marks it done, with
**Undo**. Rules on your computer, no AI.

- **A slip of the keyboard is fine.** "doje", "donee", "dun", "finsihed", "submited" count as done, finished,
  submitted or completed. Ordinary words a letter away ("gone", "none", "fine") don't.
- **Homework words and the course.** "hw", "homework", "assignment", "problem set", "sheet" keep to things you hand
  in (homework-like titles first); a course's name or short name ("organic", "chem", "la") keeps to that course; a number
  keeps to titles with that number ("hw 9" is "Homework 09"). Other words must be in the title.
- **The nearest one.** Of what fits, the open one nearest in time (due soonest, or most recently past, up to two weeks
  back) is marked, but only when the next one is at least a day further away. When two fit about as well, it asks
  "Which one is done?" with a button each, and marks nothing until you tap. "hw is done" with no course marks
  something only when you have one open homework.
- **Not done.** "is not done", "will be done tomorrow", "almost done" and questions ("is the hw done?") change
  nothing. Words that fit no deadline go to your AI as usual.

### Photo to dates

**What it does.** You take a photo of a notice board, a poster, a circular or a timetable; the AI you picked reads it
and sends back each deadline, exam and event it found, one line and one **Add** button each (with **Add all** and
**None of these**). Nothing is added until you tap. A deadline or an exam goes into this list (its source: photo); an
event becomes a reminder an hour before it (`date_offers.remind_min`; 08:00 that day when it has no time). A weekly
timetable's classes come with one button, **Add N classes to my timetable**: each goes into your timetable, and a
course you don't have yet becomes a subject ([classes-and-timetable.md](classes-and-timetable.md)).

| You send | What happens |
|---|---|
| a photo with `dates` as its caption (or `/dates`, `deadlines`, `timetable`, "find the dates", "any exams?") | the photo goes to your AI; "Reading the photo for dates…", then the buttons |
| `/dates` alone, or "find the dates in that photo", "deadlines from this notice" | the newest photo of the last two hours: one you sent on Telegram, or shared from your phone ([phone-app.md](phone-app.md#sharing-files-to-your-notes)), also after the AI filed it under the same name |

**Which AI can read a photo.** agy, Claude Code and a Gemini key read pictures. Ollama does when its model does
(gemma3, gemma4, llava; Kurooto asks Ollama). With Ollama and a model that doesn't, it says so and does nothing: pick
another in Settings → AI. Another service is tried; if it can't, the answer says so.

**What it sends.** The photo goes to the AI you picked and nowhere else; Kurooto keeps the photo where it landed (your
notes' inbox) and what was found, for the buttons (the newest 100 lots). Dates from the past are left out; the AI is
told never to invent a date and that the photo's words are information, never instructions.

Off: `deadlines.from_photos` (Settings → Deadlines). The phone app's share sheet has no caption box, so share the photo
first, then say "dates from that photo" in the app's chat.

### The chase

For things you hand in (not exams):

| When | What you get | Buttons |
|---|---|---|
| `deadlines.ping_h` (24) hours before | "Due in 23 h: Essay draft (Fri 13 Nov 17:00)" | **Done** (ticks it off), **Not mine** (takes it off your list), **Snooze 3 h** (asks again in 3 hours) |
| `deadlines.urgent_h` (6) hours before | With Phone calls on: a **call** ("Essay draft is due Fri 17:00. Is it done, or how will you finish it in time?"). Otherwise an urgent message with the same buttons | |
| After the due time (up to 3 days after) | **Overdue?** "Essay draft was due Fri 13 Nov 17:00." | **Done**, **New date** (asks you for the date: reply, answer on the phone app or on your next call; the chase starts over), **Drop** |

- The list is checked once an hour, so a nudge comes within the hour of its moment.
- For a deadline with parts ([below](#problem-set-progress)) the message says how far you are ("..., 4/7 done") and
  has **+1** first.
- **The six-hour call waits out** classes, `/hold`, focus, calendar events and the night. If that would leave less
  than 30 minutes before the deadline, you get the urgent message instead. A missed or declined call becomes
  "Missed call. Due in ...", with the same buttons.
- For quizzes and exams: a reminder a day before (with **Practice now** when Quiz is on). With Quiz's evening
  practice offer on, that offer replaces the reminder ([quiz-and-exams.md](quiz-and-exams.md)).
- **Done** ticks the `- [ ]` box in your notes when the deadline came from one (only that box changes; turn it off
  with `deadlines.tick_notes`). If the line changed since Kurooto read it, nothing is ticked: tick it yourself.
- Settled deadlines older than 90 days are forgotten.
- **With Brain on** (0.8.14, `mind.study_push.on`): the subject Brain is most uneasy about gets one morning line
  instead ("Uneasy about Measure Theory: due Fri, 0 min logged this week, 9 cards due. 25 min at 16:00?", Yes / Later),
  and that day its day-before reminder and Start-by's "Time to start" don't come separately. The six-hour reminder
  and "Overdue?" always do ([mind.md](mind.md#one-worry-not-five-nudges-0814)).

### Problem-set progress

A deadline with parts (a problem set's questions) keeps how many are done. Say it in the chat or on a call ("ps3 4/7"),
or answer one of its messages:

| You | What happens |
|---|---|
| Reply `4/7` (or `4 of 7`) to its reminder or "Overdue?" message | 4 of 7 done: "Problem set 3: 4/7, 3 to go, due Fri 30 Oct 17:00", with **Undo** |
| Reply `4` | 4 done, of the total it already has. Without one: "Out of how many? Reply to the reminder like 4/7." |
| Reply `+1` (or `+2`), or tap **+1** | one (two) more done. **+1** stays under the message, so you can tap it after each question |
| Reply `done` | as **Done**: it's handed in (and its `- [ ]` box in your notes is ticked), with **Undo** |
| Reply anything else | handled as an ordinary message |
| **Undo** | puts back what that reply changed: the count before it, or the deadline open again (and its box unticked). Only the latest change; an older **Undo** says it was changed again since |

Replies work on Telegram, in the phone app's chat (**Reply** under the message) and with **Reply** on the phone's
notification. **+1** works on all of them too; on the phone it waits on your call line while your computer is off,
and each tap counts, in order ([phone-app.md](phone-app.md#when-your-computer-is-off)).

**In the morning.** The wake-up call, the morning page and `/status` say a deadline with parts as "Problem set 3 4/7,
due Fri" (or "due tomorrow", "due today 17:00"; with the date when it's a week or more away). The lists show "(4/7)",
and [Start-by](#start-by-dates-and-crunch-weeks) plans from what's left.

**On the dashboard.** The [Today page](dashboard.md) shows what's due in the next three weeks (red when overdue,
amber under a day) with **done** and **new date**, and an add box (`essay draft fri 17:00`: what, then when).
Ctrl+K: `due essay draft fri 17:00`. The board's **due** corner shows the same list.

**On calls.** Every call's brief has what's due in the next `deadlines.plan_h` hours. Say "the lab report is done",
"it got moved to Friday", "add a deadline: poster due Monday 9am", "I don't care about the drama club". The AI's tools:
`list_deadlines`, `mark_deadline_done`, `add_deadline`, `move_deadline`, `ignore_topic`, `add_recurring_quiz`. Done
while the computer is off, they wait and run when it's back.

**Your AI, in a chat or a request.** The same tools reach your AI everywhere (Claude Code and agy through Kurooto's
tools). `list_deadlines` gives it what's open with each one's id; `mark_deadline_done` and `move_deadline` take the id
or words of the title and course ("chem homework"), found the same way as [above](#done-in-your-words). When two
fit, nothing changes and the AI asks you which.

**The course.** `add_deadline` takes the course by name or short name ("pota"), so a deadline the mail digest finds
("Lab report due Wed" in a mail from your Physics of the Atmosphere teacher) lands on that course even when its title
doesn't name it; lists show it as "Physics of the Atmosphere: Lab report". A course Kurooto doesn't know, or words
naming two, isn't guessed: the answer says so and lists your courses, and the deadline goes on no course (unless its
title names one).

**How far ahead "due soon" looks** (`deadlines.plan_h`, 72 hours): what's due in that window goes into the wake-up
call's plan, the morning page, the call brief, `/status` and "what's due soon?". Set `168` to plan a week ahead, `36`
for little more than tomorrow. `/deadlines` and the chase don't change.

**Settings that matter** (Dashboard → Settings → Deadlines):

| Setting | Default | Effect |
|---|---|---|
| `deadlines.plan_h` | `72` | how far ahead "due soon" looks (morning plan, `/status`, calls) |
| `deadlines.ping_h` | `24` | hours before the due time for the first message |
| `deadlines.urgent_h` | `6` | hours before for the call or urgent message |
| `deadlines.call` | on | with Phone calls on, the urgent nudge is a call |
| `deadlines.overdue_check` | on | the "Overdue?" question |
| `deadlines.tick_notes` | on | **Done** ticks the box in your notes |
| `deadlines.scan_notes` | on | read dated `- [ ]` tasks in your notes |
| `deadlines.max_files` | `3000` | the most notes read for tasks (notes over 1 MB are skipped) |
| `deadlines.from_calendar` | on | calendar events that look like deadlines or exams |
| `deadlines.from_term_note` | on | the term note's key dates |
| `deadlines.recurring` | on | recurring quizzes |
| `deadlines.horizon_days` | `30` | how far ahead recurring quizzes become dated items |
| `deadlines.exam_mode_days` | `14` | days before a quiz or exam that exam mode starts; `0` turns exam mode off |

**What leaves your computer.** Nothing by itself. The list is kept in Kurooto's state folder. With Phone calls on,
what's due soon is in your call line's brief. The AI you picked sees the list when it reads it for you.

**Turn it off.** Features → Deadlines → Turn off (Start-by dates and Exam season need it, so turn those off first).
The list itself is kept for when you turn it on again; the chase stops at once.
Just the call: `deadlines.call` off. Just the overdue question: `deadlines.overdue_check` off.

---

## Recurring quizzes and tests

**What it does.** Quizzes and tests that repeat ("Linear Algebra quiz every Thursday 10:00", "Statistics test every
other Friday") become dated items on the deadline list, so reminders, exam mode and practice offers follow them.
It's part of Deadlines.

**From Telegram.**

| You send | What happens |
|---|---|
| `linear algebra has a quiz every thursday` | adds a weekly row (the subject must be one of your [subjects](classes-and-timetable.md)) |
| `statistics has a test every other friday at 11` | every two weeks |
| `/recurring add la quiz every 2 weeks thu 10:00` | the same as a command |
| `/recurring add la quiz weekly` | day and time come from your timetable, or Kurooto asks |
| `/recurring add la quiz every 2 weeks thu 10:00 2026-11-05` | a date it happens on (needed for every two weeks) |
| `/recurring` | lists them (a class pack's are marked "(class pack)") |
| `/recurring remove la quiz` | removes that row (only rows in your table, not a class pack's) |
| "Also, there's a quiz on Linear Algebra every Monday at 10" in a longer message or your journal | added for you with an Undo button when the course and the day are said ([set up from what you say](teaching-kurooto.md#set-up-from-what-you-say)) |

"Every" can be weekly, every week, each, every other, every second, every 2 weeks, fortnightly or biweekly (up to 8
weeks). What it is can be a quiz, class test, test, assessment, exam, viva, lab test, worksheet, problem sheet,
homework, assignment or problem set.

**The table in your notes.** They live in `kurooto/recurring.md` (`master/recurring-assessments.md` in the
zettelkasten layout). Edit it like any note:

| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| linear-algebra | Quiz | 1 | Thu | 10:00 | | |

- **Every** is in weeks (or "weekly", "every other week"). **Next** is any date it happens on: needed for every two
  weeks, so Kurooto knows which week. **Until** is optional.
- The header can use your own column names ("Course" for "Subject"); columns are read by position.
- **Missing day or time:** Kurooto uses the subject's class from your timetable. When it can't tell (the subject has
  several classes, or it's every two weeks with no Next), it asks once with buttons ("Which day (and time) is the
  Linear Algebra quiz?", or "when is the next one?"). For a row you wrote yourself, your answer is kept by Kurooto
  and your note isn't changed. The question expires after 3 days.
- Holidays from your subjects settings are skipped.
- Items are made `deadlines.horizon_days` (30) days ahead.

**Turn it off.** `deadlines.recurring` off. The table stays in your notes.

---

## Not interested

**What it does.** Topics you don't care about (a club, a kind of event, a course you dropped) are left out: matching
deadlines leave the list and the chase, and the mail and Classroom digests only count matching items instead of
making tasks from them.

**From Telegram.**

| You send | What happens |
|---|---|
| `/ignore drama club` | adds it; says how many open deadlines it now hides |
| `I don't care about the drama club` · `I'm not interested in sports day` · `stop telling me about hackathons` · `ignore chess club events from now on` | the same |
| `/ignored` | the list |
| `/unignore drama club` | takes it off |

On a call: "I don't care about the drama club" (the `ignore_topic` tool). A topic must be at least 3 characters and
at most 6 words; "that" or "it" alone isn't taken.

**The note.** The list is `about-me/not-interested.md` (`master/not-interested.md` in the zettelkasten layout), one
topic per line: `- drama club`, or `- drama club — not this term` (the part after the dash is your reason and isn't
matched). Edit it freely. Matching is on whole words and phrases, ignoring case.

**Your AI knows the list** (0.9.0, `notinterested.tell_ai`, on). Every AI request, call and Live talk at the desk is
told the topics (only the topics, never your reasons), so it doesn't bring them up on its own; ask about one and it
helps as usual. Off: the AI isn't told.

**More places that use the list** (0.9.0, each off until you turn it on). Each puts a matching item last and says
"you said not interested in X" next to it; nothing is hidden or dropped:

| Setting | What it changes |
|---|---|
| `notinterested.filter.research` | new-paper digests: papers about the topic come last |
| `notinterested.filter.integrate` | the concept graph's reading queue: class material about it is read last |
| `notinterested.filter.quiz_links` | link cards about it come after the others |
| `notinterested.filter.retro` | the nightly look back offers ideas about it last |
| `notinterested.filter.frontier` | the Brain's frontier cards about it are made last, and it counts less on your frontier |

**What leaves your computer.** The topics, to the AI you picked and, on calls, to Gemini Live (with
`notinterested.tell_ai` on). Nothing else.

**Turn it off.** Empty the note, or `/unignore` each topic; `notinterested.tell_ai` off keeps the list from the AI.

---

## Exam mode

**What it does.** Two weeks before a quiz or exam on your deadline list (`deadlines.exam_mode_days`, 14), exam mode
starts for that subject, and ends after it. You're told once: "Exam mode for Linear Algebra: Linear Algebra midterm,
Thu 12 Nov 10:00 (in 9 days). Quizzes come more often until then. /exam shows it."

While it's on:
- `/exam`, `exam mode` or "when's my next exam?" (also quiz, test) shows each subject's nearest quiz or exam, and,
  with Quiz on, how many questions are due to practise;
- calls start knowing it (it's in the brief);
- with Quiz on, sessions are longer (`quiz.exam_per_session`, 6), items you know come back before the exam, and you
  can have a short practice every day (`quiz.exam_daily`, e.g. `18:00`). Details: [quiz-and-exams.md](quiz-and-exams.md).

Exam mode is automatic. **Exam season** is a separate, optional add-on for the whole exam period (it's off and in no
preset; turn it on by hand): see [quiz-and-exams.md](quiz-and-exams.md).

**Turn it off.** `deadlines.exam_mode_days` = `0`. `/exam` then says it's turned off.

---

## Start-by dates and crunch weeks

**What it does.** Works out when to start each deadline, back from how much work it is and your free time, and warns
you about weeks where the work due is more than the time you have. It's an estimate, plain arithmetic on this
computer: no AI.

**Turn it on.** Features → Start-by dates. It needs Deadlines. It's off until you turn it on.

**Sizes.** Each deadline gets a size from its title:

| Kind | Words in the title | Default size |
|---|---|---|
| Problem set | problem set, pset, homework, hw, assignment, worksheet, exercise, sheet, tutorial, lab | 3 h (an evening) |
| Report | report, essay, term paper, write-up, thesis, dissertation, proposal, project, presentation, poster | 12 h (2-3 days) |
| Quiz or test | quiz, test | 2 h |
| Exam | exam, midterm, finals, midsem, endsem | what you set for its subject (10 h until you do) |
| Anything else | | 2 h |

Correct a size with one tap: the "Time to start" message and `/startby` have buttons with the other sizes (An hour,
An evening, A day, 2-3 days, A week; for exams An evening up to Two weeks). A size you tap for an exam counts for that
subject's exams from then on. The first exam of a subject asks you once: "How long do you usually need to prepare for
a Statistics exam?". On a call or to your AI: "the lab report is about a day of work". A day of work counts as 5 h, a
week as 25 h.

**Free time.** Each day from 09:00 to 22:00 (`startby.window`), minus your classes (timetable, holidays, exam
periods, classes you `/skip`), your [commitments](classes-and-timetable.md#commitments-gym-shifts-standups) (0.9.0;
one you skip for the day frees its time), your calendar's timed events and the blocks already in your
[Agent plan calendar](google.md) (0.9.0: time you planned isn't free for something else; with Google unreachable,
none count), in gaps of at least 30 minutes. Only 40% of that
counts (`startby.share`): the rest is meals, rest and everything else. Calendar events are known two weeks ahead;
after that only classes count, so far-off weeks look freer than they will be.

**The window learns your day** (`startby.learn_window`, on). Once a week (Sunday noon) it looks at when your messages
came in over the last three weeks. With 7 or more days of 3+ messages, and the middle of your first messages or of
your last ones an hour or more from the window's ends, the window moves there, to the half hour (starting between
05:00 and 13:00, ending between 17:00 and 03:00): "Start-by dates now count your free time from 11:00 to 01:30, not
09:00 to 22:00", with **Undo**. Not again for a week; after an Undo, not for a month. A window you set yourself is never
changed.

**Start-by dates.** Working back from the due times, latest first, each deadline's hours go into the latest free
time before it that a later deadline hasn't taken. The day its first hour lands on is its start-by date. Two big
deadlines in one week push each other earlier.

From that date until it's due, the deadline is in the morning plan: the morning page (**Time to start**), the wake-up
call and the plan drafted before the alarm. On the day itself, at 08:00 (`startby.when`; it waits out focus) you get
one message: "Time to start: Lab report, due Fri 13 Nov. It's about 12 h (2-3 days) of work...", with the sizes to
tap. At most three such messages a day, and only when it's two or more days before the due date (closer than that,
the deadline's own day-before message says it). When there isn't enough free time left, it says so. The first morning
after you turn it on, one message lists what's to start now.

With [Exam season](quiz-and-exams.md#the-revision-plan)'s revision plan on, the day's revision blocks are in the
morning plan too, after what's to start ("Revise Jordan form, 10:00-11:00 · for Linear Algebra final exam").

**Negotiate, don't repeat** (`startby.negotiate`, on). When a deadline's reminder would come again (the six-hour one
after the day-ahead one, one after a Snooze, the message after a missed deadline call, or any reminder for a deadline
whose "Time to start" came on an earlier day) and the deadline is slipping, you get a reshaped plan instead, from your
own Start-by plan: "Problem set 4 (due Tue 03 Nov 11:00): your Start-by plan has 2 h of it today, and about 1 h of
today's free time is left. 1 h now, 1 h tomorrow?" with **Do that** and **Not today**.
- *Slipping* means this morning's plan put hours of it into today, and what's left of today's free time (the same 40%
  share) no longer holds them. Outside your day's window, or with no free time tomorrow before it's due, nothing
  changes.
- **Do that**: tomorrow's part gets a reminder at the start of tomorrow's first free time ("Problem set 4: the 1 h you
  moved to today"), and with the Agent plan calendar on, both parts go in as blocks.
- **Not today**: nothing more about it today.
- One offer per deadline per day; after that the reminders come as they always did. The words are fixed and plain:
  no rising tone, no urgency that isn't in the dates.
- On a deadline call, the AI has the same plan as the `reshape_plan` and `reshape_answer` tools and is told to offer
  it once, calmly, when you're behind.

**What the study tracker counted** (`startby.count_study`, on, 0.9.0). With the [Study tracker](books-and-study.md#study-tracker)
on, "Time to start" says what it already counted for that deadline: "You've put about 3 h into it already; about 9 h
left if that counts.", with **Count it**, which sets its size to what's left. It counts study sessions tied to that
deadline (a focus started from Brain's study push), else, when it's the only open deadline in its subject, that
subject's last seven days. The size changes only when you tap Count it.

**Brain's miss risk** (`startby.miss_risk`, on, 0.9.0). With [Brain's plans](mind.md#plans-over-weeks) on, "Time to
start" adds "At your usual pace there's about a 40% chance of missing it." when the plans put it at 20% or more, and
the Sunday summary lists the likeliest to slip in the crunch weeks.

**A share from your pace** (`startby.learn_share`, off, 0.9.0). Turned on, once a week (Sunday noon), when your real
pace (the hours a day you actually get done, from the study tracker) is ten points or more from `startby.share` as a
share of your free time, one offer: "Your pace says about 8.0 h a day of work, out of about 13.0 h free. Start-by
dates count 40% of your free time for deadlines; use 60% instead?" with **Yes** and **No**. Yes changes it, with
**Undo**. Never a share you set yourself; after No or Undo, not for a month.

**What the kind really took** (`startby.learned_line`, on, 0.9.1). With two or more done deadlines of the same kind
in a subject in the last four months, "Time to start" for a size it guessed says what they really took when that's
well off: "Your last 2 problem sets in Organic Chemistry took about 5.5 h of study each.", with **Use 5.5 h**. The
time is the study tracker's: sessions tied to each deadline, else the subject's time from its start-by date to when
it was done (only when nothing else of the subject was due then). The size changes only on your tap;
`startby.learned_estimates` (off) uses it by itself in place of the guess (never a size you set).

**The hours you usually work on it** (`startby.learn_from_model`, off, 0.9.1). When a feature knows when you work on
what (an add-on's reading, "works on Topology at night"), a deadline's hours and the study push's offered time go
first into those hours. Only the order the free hours are used in changes.

**Your phone's place names** (`reminders.place_names`, off, 0.9.1). The phone app shares the names of the places you
saved, so "remind me when I reach the lib to return the book" goes to the phone as "Library" (one clear match only;
otherwise your words go as before). Names only, never told to an AI. See [Phone app](phone-app.md).

**The forecast picks the hours** (`mind.presence_forecast.plan`, off, 0.9.0). With [Brain's presence
forecast](mind.md#when-youll-be-free-0816) and this on, a deadline's hours go first into the hours you're likeliest at
your desk and free, and the study push offers the likeliest stretch. No hour is taken away. With too few messages to
learn the window from, it can learn it from your usual quiet hours instead, with the same line and Undo.

**Crunch weeks.** The Sunday [weekly summary](check-ins-and-journal.md#weekly-summary) flags weeks in the next four
(`startby.crunch_weeks`) where the work due adds up to more than the free time: "Crunch weeks (an estimate): week of
9 Nov: about 14 h of work, about 9 h free. Start some of it the week before." It also says what to start in the
coming week.

**From Telegram.**

| You send | What happens |
|---|---|
| `/startby` | the next five weeks' deadlines with start-by dates and sizes, crunch weeks, and size buttons (up to 10) |
| `/startby exam` | each subject's exam preparation size |
| `/startby exam la 2-3 days` | sets that subject's exam size (also `15h`, `a week`, `3d`) |
| `when should I start the lab report?` | its start-by date |
| `when should I start?` | what to start today |
| `any crunch weeks coming?` · `how busy are the next weeks?` | crunch weeks ahead |

On calls the brief has "time to start", and the AI has `start_by`, `set_work_size`, `reshape_plan` and
`reshape_answer` tools.

**Settings that matter** (Dashboard → Settings → Start-by dates):

| Setting | Default | Effect |
|---|---|---|
| `startby.sizes` | problem_set 3, report 12, quiz 2, exam 10, other 2 | hours per kind |
| `startby.exam_by_subject` | `{}` | hours per subject's exams, e.g. `{"linear-algebra": 25}` |
| `startby.window` | `09:00-22:00` | the part of each day that counts (an end before the start runs past midnight) |
| `startby.learn_window` | `true` | once a week, move the window to when your messages come in (never one you set) |
| `startby.share` | `40` | % of free time that goes to deadlines |
| `startby.min_gap_min` | `30` | shorter gaps don't count |
| `startby.horizon_days` | `35` | how far ahead deadlines get a date |
| `startby.when` | `daily 08:00` | when the day's messages come |
| `startby.tell` | on | the message on a start-by day |
| `startby.ask_exams` | on | the once-per-subject exam question |
| `startby.crunch_weeks` | `4` | weeks the Sunday summary looks ahead; `0` turns crunch weeks off |
| `startby.negotiate` | on | a reminder that would repeat for a slipping deadline: a reshaped plan instead, once a day |
| `startby.count_study` | on | "Time to start" says the study counted for it, with Count it (0.9.0) |
| `startby.miss_risk` | on | "Time to start" and the Sunday summary say Brain's chance of missing it (0.9.0) |
| `startby.learn_share` | off | a weekly offer to change `startby.share` from your pace (0.9.0) |
| `startby.learned_line` | on | "Time to start" says what the subject's last deadlines of the kind took, with Use (0.9.1) |
| `startby.learned_estimates` | off | that learned time replaces a guessed size by itself (0.9.1) |
| `startby.learn_from_model` | off | the hours you usually work on a subject come first (0.9.1) |
| `reminders.place_names` | off | the phone's place names, for matching a place you name (0.9.1) |

**What leaves your computer.** Nothing.

**Turn it off.** Features → Start-by dates. Only the messages: `startby.tell` off. The exam question:
`startby.ask_exams` off. Crunch weeks: `startby.crunch_weeks` = `0`. Sizes you tapped are kept for when you turn it
on again; reset `startby.exam_by_subject` to forget exam sizes.

---

## Messages these features send by themselves

Each of these has **Why?** and **Less of this** buttons on Telegram ([messages-it-sends.md](messages-it-sends.md)).
"Stop" changes the setting shown.

| Message | Why it came | Less of this → Stop does |
|---|---|---|
| "Reminder: ..." | a reminder you set | never held or stopped (your own) |
| "Due in 23 h: ..." | a reminder before something on your deadline list (`deadlines.ping_h`) | the day-ahead message goes; the last 6 hours' still comes. Under 12 hours away it's never held |
| A deadline call | the call a few hours before (`deadlines.call`) | no calls; a message instead |
| "Overdue?" | a deadline passed (`deadlines.overdue_check`) | no more Overdue? questions |
| "Exam mode for ..." | exam mode starting (`deadlines.exam_mode_days`) | |
| "Time to start: ..." | a start-by date (`startby.tell`) | no more start-by messages (`/startby` still works) |
| "Uneasy about ...: due ..., ... min logged this week, ... cards due. 25 min at 16:00?" (Yes / Later) | Brain's one morning line about the subject it's most uneasy about (`mind.study_push.on`) | its separate reminders come back |
| "... 1 h now, 1 h tomorrow?" (Do that / Not today) | a reminder that would repeat for a slipping deadline (`startby.negotiate`) | no more reshaped plans; reminders come as before |
| "...: the 1 h you moved to today" | you tapped Do that | never held or stopped (you agreed to it) |
| "How long do you usually need to prepare for a ... exam?" | `startby.ask_exams` | no more of these questions |
| "Which day (and time) is the ... quiz?" | a recurring row with its day or week unknown | (an answer to what you set up) |
| "In that photo: ..." (Add / Add all / None of these) | a photo you sent for its dates | never held (you asked) |
| "New in <calendar> (a calendar you subscribed to): ..." | deadlines and exams in a shared class calendar (`calendar.shared_offer`) | they only show as events, without Add buttons |
| "Email in: ..., filed in ..." | mail you forwarded to +kurooto or labelled (`mail_digest.mail_in`) | Email in goes off |

---

## When something goes wrong

| What you see | What to do |
|---|---|
| A reminder came late, marked "(late: the computer was asleep)" | The computer was asleep or off at that time. Keep it awake on the charger ([your-computer.md](your-computer.md)) or turn on Reminders with the lid shut ([calls.md](calls.md)). |
| `/remind 20 tea` set 20:00, not in 20 minutes | A bare number is the hour. Minutes need their unit: `20m`. |
| Kurooto asked "When should I remind you?" | The only time in your message was about the past ("I didn't do it at 3"). Say the time you want. |
| A deadline shows up twice | Their titles have different numbers or dates. Tap **Not mine** on one. |
| A calendar event became a deadline by mistake | **Not mine** on it, `/ignore` a word in its title, or `deadlines.from_calendar` off. |
| No call six hours before a deadline | Phone calls on and set up? A class, `/hold`, focus, an event or the night until shortly before the deadline means a message instead. |
| Done didn't tick the box in my notes | The line changed since Kurooto read it (it reads hourly). Tick it yourself. |
| A task in my notes isn't on the list | It needs a date in brackets, `(2026-11-02)` or `(2026-11-02 17:00)`, on an unticked `- [ ]` line. |
| A recurring quiz is on the wrong week | Put a date it really happens on in the Next column of the recurring table. |
| `/exam` says exam mode is turned off | `deadlines.exam_mode_days` is 0. Set it to 14. |
| Start-by dates are too early or too late | Tap the right size on a deadline (`/startby`). If they're all off, change `startby.share` or `startby.window`. |

## On a call

Say "that quiz is cancelled" or "I don't have that quiz" and the call removes it for good (it doesn't come back from
Classroom, a note or the recurring table); "I finished it" marks it done; "it moved to Friday" moves it. A quiz or exam
whose time has passed is simply over: it's never listed as overdue. After every call, Kurooto looks back at what you
asked for and fixes anything the call got wrong (see [Phone calls](calls.md)).

## Notes the scan should leave alone

Kurooto finds deadlines in your notes by looking for unticked checkbox lines that end in a date, like
`- [ ] hand in the form (2026-10-30)`. A list of ideas where the date is just *when you wrote it down* would turn into
"Overdue?" nudges. To stop that, put its path (or a folder) in the setting `deadlines.skip_notes` (dashboard → Settings →
Deadlines), for example `master/ideas.md`. Anything already found from it: tap **Drop** once and it stays gone.
