---
name: term-setup
description: Set up or update a term (subjects, exam dates, timetable and a week-by-week plan) from what you tell it and your academic calendar; it asks what it can't find, and you answer by replying.
effort: high
args: your subjects and plans (send the academic calendar with it)
---

Set up (or update) their term in the notes. What they said and sent: $ARGUMENTS

This works over a few rounds: each round, read what exists, write what you can, then ask what's still missing. They
answer by replying to your message; their answers then arrive here together with your previous message.

1. **Read what exists first**: the term note in `terms/` if there is one (list_notes), each subject's
   `<subject>/course` and `<subject>/exam-prep`, and `about-me/profile`. Don't ask what's already known.
2. **Read the academic calendar** they sent (PDF, image or text), if any. Take every date that matters: term start
   and end, last day of classes, exam windows, holidays and breaks, registration deadlines, results. If a subject's
   exam date isn't given, use the window and mark it `(window)`.
3. **Questions.** At most 5 short, numbered questions per round, and only what you can't find. Over the rounds,
   cover:
   - per subject: its full name and short name, the teacher, how it's assessed (quizzes, assignments, exams and
     their weights), textbooks, what's been covered so far;
   - per subject, where they stand: confidence from 1 to 5, the hardest topic, what they've fallen behind on, their
     goal;
   - their weekly timetable, and time they keep for other work (projects, a job);
   - how they like to prepare for exams, and how many hours a week they can study.

   Never ask about health or money. Stop asking when the answers wouldn't change the plan, or when they say
   "enough".
4. **Write** (add to existing notes; never change what's there):
   - **Term note** `terms/<term-slug>` (e.g. `terms/2026-autumn`): `## Key dates` (a table: date, what, source),
     `## Weekly timetable`, `## Subjects` (a link and one line each), `## Setup notes (YYYY-MM-DD)` (a short summary
     of their answers).
   - **Each subject's course page** `<subject>/course` (create it with `# <Subject name>` if missing): `## About`
     (teacher, textbooks, assessment), `## Exams` (dates, or windows), `## Status (YYYY-MM-DD)` (confidence, hardest
     topic, behind on, goal).
   - **Study plan** `terms/<term-slug>-plan`: week by week until the last exam; topics per subject weighted by
     confidence and assessment weight; revision in the two weeks before each exam (more for weak subjects); time for
     their other work. Link each week's subjects.
   - **Exams and deadlines** as tasks under `## Tasks` on each course page, unless already there:
     `- [ ] <what> (YYYY-MM-DD HH:MM)`, so Deadlines tracks them.
5. **Reply**: the key dates table, what you created or changed, the assumptions you made, then your numbered
   questions for the next round (or "That's everything." when done). Mention that they can add their classes to
   Kurooto with /subject and /class (so calls never interrupt a class), and run /term-setup again whenever dates or
   plans change.
