# Quiz and exams

Practice questions from your own notes, spaced so you see each one again just before you'd forget it; a stronger
routine in the two weeks before a quiz or exam; an optional exam-season mode for the whole exam period, with a revision
plan before each exam; revision packs as PDFs; and a hint ladder for problems you're stuck on.

- [Quiz](#quiz)
- [Link recall cards](#link-recall-cards)
- [Exam mode](#exam-mode)
- [Exam season (optional)](#exam-season)
  - [The revision plan](#the-revision-plan)
- [Revision packs](#revision-packs)
- [Hint ladder](#hint-ladder)

---

## Quiz

**What it does.** Turns lists in your notes into questions, asks a few at a time on Telegram or on a call, and
reschedules each by how well you knew it (items you know come back less often; ones you forgot come back tomorrow).

**Turn it on.** Dashboard → Features → Quiz (needs Telegram). With Deadlines on it follows your quizzes and exams;
with Phone calls on it can quiz you by call; with Chat on your AI grades your answers.

**Where the questions come from.** Any note whose file name contains `exam-prep` or `quiz` (for example
`linear-algebra/exam-prep.md`). Every bullet line under one of these headings is one question:

```
## Must know
- The rank-nullity theorem: dim V = rank T + nullity T for T: V → W linear.
- A matrix is invertible exactly when its determinant is non-zero.
```

Headings that count: **Must know**, **Typical questions**, **Key results**, **Key theorems**, **Key definitions**,
**Definitions**, **Theorems**, **Formulas**. A bullet needs at least 12 characters. The note's folder name is the
subject. [Classroom → notes](google.md) keeps such an exam-prep note for each course, and `/exam-prep <subject>`
(see [Books and study](books-and-study.md#the-source-mix)) brings one up to date. Edit the note any time; new bullets
join at the next quiz.

**From Telegram.**

| You send | What happens |
|---|---|
| `/quiz` | a session: the exam-mode subject first, else the subject with most questions due |
| `/quiz la` | a session on Linear Algebra |
| `/quiz la here` | on Telegram, even when quizzes would ring you |
| `/quiz la call` | a quiz call now (it waits out classes and other no-call times) |
| `/quiz at 21:00 la`, `/quiz la tomorrow 8pm` | a quiz check-in later: the first question arrives then (a call instead with `quiz.by_call` on, or `/quiz la call at 21:00`) |
| `/quizstatus` | items and how many are due, per subject, and any exam mode |
| "quiz me", "quiz me on topology", "test me on LA", "give me a quiz" | a session now |
| "quiz me by call", "call me for a quiz" | a quiz call |
| "quiz me at 9 tonight", "quiz me by call at 9" | a check-in later |

With Phone calls on, `/quiz` first asks **Here or by call?** (buttons **Here** / **By call**). With `quiz.by_call` on as
well, `/quiz` and "quiz me" call you straight away; add "here" to keep it on Telegram.

**Answering.** Reply to the question with your answer.
- With Chat on, your AI gives the key idea and a grade from 0 to 5, and the next question follows.
- Without Chat (or if the AI fails), Kurooto shows what your note says and you grade yourself: **Forgot** (0),
  **Hard** (3), **Good** (4), **Easy** (5).
- A session is `quiz.per_session` questions (3; 6 in exam mode). It ends with "That's the session. /quiz for more."
  A session left unfinished is forgotten at midnight.

**The evening before a quiz or exam.** From 19:00 (`quiz.offer_at`) the evening before something on your deadline list
that's a quiz or exam: "Linear Algebra quiz is tomorrow at 10:00. Practise? 7 questions are due." with **Quiz me now**,
**Call me for a quiz** (with Phone calls on) and **Not tonight**. On the day itself, if it's at least 2 hours away and
wasn't offered yet, you get the same with **No thanks**. If you have no material for it yet, it says where to put
some. Never during your night hours. Once per quiz or exam.

**On calls.** Say "quiz me" on any call for a spoken quiz: the assistant asks a question, listens, grades it and moves
on. In exam mode the call's brief says how many questions are due. A missed quiz call becomes a message: "Missed the
quiz call. /quiz la practises here instead."

**Settings that matter** (Dashboard → Settings → Quiz)

| Setting | Default | Effect |
|---|---|---|
| `quiz.per_session` | 3 | questions per session |
| `quiz.exam_per_session` | 6 | questions per session in exam mode |
| `quiz.offer_at` | `19:00` | when the evening-before offer can come; empty turns the offer off |
| `quiz.exam_daily` | empty (off) | a time like `18:00` turns on a daily practice check-in in exam mode |
| `quiz.by_call` | off | on: `/quiz`, "quiz me" and quiz check-ins ring you (with Phone calls on) |
| `quiz.call_min` | 10 | how long a quiz call is meant to take, in minutes |

**Messages it sends by itself.** The evening-before offer (Less of this → Stop empties `quiz.offer_at`), exam mode's
daily practice check-in, quiz calls in exam mode, and the "Quiz time" check-ins you set (those are your own and never
held back). See [Messages it sends](messages-it-sends.md).

**What leaves your computer.** With Chat on, the question and your answer go to your AI to grade it. Otherwise nothing.

**Turn it off / undo.** Features → Quiz → Turn off; your progress stays in Kurooto's state folder (`quiz/`).
`quiz.by_call` off brings back **Here or by call?**.

## Link recall cards

**What it does.** The links between your concept notes become questions. Each link the
[concept graph](notes-and-concept-graph.md) writes (or one you write the same way), like
`- used-in:: [[zettel/fokker-planck]] — its generator gives the drift and diffusion terms`, is a card: "How is Itô's
lemma used in Fokker-Planck?". You answer in your own words, see what the note says and where to read, and grade
yourself. Spacing is the quiz's: a card you knew comes back later, one you forgot comes back tomorrow.

**Turn it on.** It's part of Quiz. `/card` gives a card any time; for cards that come by themselves, `/cards on` (or
`quiz.links` in Settings → Quiz).

**A card, step by step.**
1. "Link card (Stochastic Calculus): How is Itô's lemma used in Fokker-Planck? Reply in your own words."
2. Reply to it on Telegram, or with **Reply** in the phone app.
3. You see the link's reason, then **Where to read**: the book pages where the two concepts are met (from the concept
   graph's "Seen in"), and the best match in that subject's own notes and Classroom files.
4. Grade it: **Forgot** (0), **Hard** (3), **Good** (4), **Easy** (5). After **Forgot**, the first place to read is
   repeated. In the phone app the grade buttons come as their own message.

**When they come.** With `quiz.links` on, up to `quiz.links_per_day` cards (3; never more than 5) at the times in
`quiz.links_at` (11:00, 16:00 and 20:00), one at a time. They reach the phone app too (they're questions). Never during
a class, focus time, a call or the night: a card that falls then comes 5 minutes after it ends (the same day). A card
you haven't answered holds back the next one that day. Cards you've seen come before new ones.

**From Telegram.**

| You send | What happens |
|---|---|
| `/card` | a card now (it doesn't count toward the day's) |
| `/cards` | how many cards, how many seen and due, how many you answered and got right this week |
| `/cards on`, `/cards off` | cards by themselves on or off (`/card` works either way) |

**Local check (optional).** With `quiz.links_check` on and [Local AI models](your-computer.md#local-ai-models) on, the small model on
this computer says in one sentence how close your answer came, before you grade. It's never a cloud AI, and you still
grade.

**Settings that matter** (Dashboard → Settings → Quiz)

| Setting | Default | Effect |
|---|---|---|
| `quiz.links` | off | link cards come by themselves |
| `quiz.links_per_day` | 3 | the most a day (at most 5) |
| `quiz.links_at` | `daily 11:00,16:00,20:00` | when one may come |
| `quiz.links_check` | off | the local model's one-sentence check |

**Messages it sends by itself.** The cards (Less of this → Stop turns `quiz.links` off; Fewer makes it one a day).

**What leaves your computer.** Nothing: the cards, your answers and the local check stay here.

**Turn it off / undo.** `/cards off`. What you graded stays in Kurooto's state folder (`quiz/_links.json`); a link you
delete from your notes stops being asked.

**Left out for now.** Papers from the research digest don't go through Books yet, so they don't get cards.

## Exam mode

**What it does.** Two weeks before each quiz or exam on your [deadline list](reminders-and-deadlines.md), that subject
is in exam mode until the exam has passed. You're told once when it starts. While it's on:
- `/exam` (or "exam mode", "when's my next exam?", "when is my next quiz?") lists each subject's next quiz or exam with
  how many questions are due;
- calls start knowing it, and a spoken quiz picks that subject;
- quiz sessions are longer (`quiz.exam_per_session`), and items you know still come back at least once before the exam;
- with `quiz.exam_daily` set, a practice check-in every day: "Exam mode: Linear Algebra midterm in 5 days. 9 questions
  to practise. Now?" with **Quiz me now**, **Call me** and **Skip today** (not the day before the exam, when the evening
  offer takes its place). With `quiz.by_call` on it calls instead.

Exams come from whatever feeds your deadline list: `/due`, your notes, Classroom, your calendar, recurring quizzes, the
term note, a class pack.

**Settings.** `deadlines.exam_mode_days` (14; `0` turns exam mode off). The full deadline settings are in
[Reminders and deadlines](reminders-and-deadlines.md).

## Exam season

**This is optional and off by default.** It isn't part of the Starter or Everything choices in setup: turn it on by
hand in Dashboard → Features → Exam season. It needs Deadlines.

**What it does.** One card for the whole exam period, on top of exam mode. It does nothing without exam dates: the exam
periods in Subjects (`/term exams 2026-12-07 to 2026-12-18`, or your term note, a class pack) and the exams on your
deadline list whose title says exam, midterm, final, mid-sem, end-sem, viva or oral. Quizzes and tests count only
inside an exam period, unless you turn on `exam_season.quizzes`. A season runs from the day before its first exam to
the end of its last; exam days up to three days apart are one season. You're told once when one starts, with what it
will do ("Exam season: Mon 7 Dec to Fri 18 Dec, 5 exams. Until it's over: …").

**Its parts.** Each has its own switch: on the card in the dashboard's Features tab, with `/examseason` on Telegram (tap
a part to switch it on or off), or in Settings → Exam season. All are on when you turn the feature on.

| Part (setting) | What it does |
|---|---|
| Hold non-critical updates (`hold_updates`) | updates wait until the exams are over. A release marked critical still installs, and so does `kurooto update --now` or an Update tap. |
| Check the alarm every night (`alarm_check`) | every night of the period, at `night_at` (21:30), Kurooto checks that tomorrow's alarm will ring (with the Morning alarm on), and your call line when a leave-by call is set for tomorrow. It tries a safe fix first; if the alarm still might not ring: "… Set your phone's own alarm too." A morning exam with no alarm before it gets its own line: "No alarm is set for tomorrow, and the Linear Algebra final is at 09:00. /alarm 7:00 sets one." |
| Ask the evening before (`eve`) | once per exam, from `eve_at` (18:00) the evening before until 2 hours before it starts: "Tomorrow: Linear Algebra final exam at 09:00. Where is it, which seat? Calculator? ID card?" Reply in one line ("Hall B, seat 34, calculator, ID card"), tap **Later** for your next call, or answer in the phone app. If the exam's time isn't known it asks that too ("starts 14:00"). |
| Alarm to leave on time (`leave_alarm`) | on the exam day, `leave_min` (45) minutes before it starts, or the time you said ("leave 8:10"). With Phone calls on it's a call that rings like the wake-up alarm (also on silent, also while this computer sleeps) and says where to go and what you said; **Later** rings again in 5 minutes, twice; a missed one also sends an urgent message. Without Phone calls it's an urgent message. "no alarm" in your answer turns it off for that exam. |
| Two-minute debrief (`debrief`) | half an hour after the exam ends (`exam_min`, 180 minutes after its start; the evening, when its time isn't known): "How did it go? What came up, what went well, what to fix before the next one." Your answer goes, as you said it, into the subject's course note (`<subject>/course.md`) under **Exam debriefs**, or into that day's daily note when the exam has no subject. **Nothing new** skips it. Asked up to 36 hours after, and open for 2 days. |
| No calls during an exam (`no_calls`) | from 15 minutes before an exam until `exam_min` after its start. |
| Only deadlines, quizzes and the alarm by day (`budget`) | during the season the [daily message limit](messages-it-sends.md) tightens: only Deadlines, Quiz, the alarm and Exam season itself come during the day; everything else that comes by itself waits for the evening bundle. Your own reminders, approvals and anything urgent still come. |
| Revision plan before each exam (`revision`) | from two weeks before each exam, its course's topics ranked and laid into your free time, with what to read; the evening asks whether you covered them. See [the revision plan](#the-revision-plan). |

**The quiz call before an exam** is off unless you pick it for that exam: the card (and `/examseason`, with Quiz and
Phone calls on) has a **Quiz call before …** button per exam. Picked, Kurooto calls you for a quiz at `quiz_call_at`
(19:00) the evening before, instead of the practice offer, and exam mode's daily practice may call with `quiz.by_call`
on. For the season's other exams, practice stays a message.

**From Telegram.** `/examseason` or "exam season?" (also "show my exam season", "how's my exam season") shows the
season, its exams with what you told Kurooto, and the parts that are on, with their switches.

**On calls.** On the exam day and the day before, every call's brief has the exam and what you said about it.

### The revision plan

**What it does.** From `revision_days` (14) before an exam, the exam's course gets a revision plan: its topics, weakest
first, laid into your free time before the exam, one topic per block, with what to read. Plain arithmetic on this
computer: no AI. It needs the exam to have a course (`/due 2026-12-08 09:00 Linear Algebra final exam`, with the course
in the title or set on the deadline).

**Where the topics come from.** The course's exam prep note (`<subject>/exam-prep.md`): each line under **Covered so
far** (the exam-prep skill writes it), then the short lines under **Gaps**; **Topics** or **Syllabus** work too. A
line's link is the topic's note; "Lecture 5: Eigenvalues" is the topic "Eigenvalues". Without an exam prep note, the
course's lecture notes (`<subject>/2026-11-05-....md`), in date order; without those, its concept notes (the concept
graph's for the course, and the other notes in its folder).

**How they're ranked.** Four groups, in this order: topics with **no note yet**; **a stub** (a note with under 50 words
of your own; a missed-class stub counts until you fill it in); **weak recall** (its quiz grades and your answers to the
evening question average under 3 of 5); the rest. In each group the weakest recall comes first, then the course's
order. A topic's quiz items are the quiz questions that name it or link to its note. A topic you said **Yes** to isn't
laid again for `revision_days`.

**When the blocks go.** Into [Start-by's](reminders-and-deadlines.md#start-by-dates-and-crunch-weeks) free time: each day's window
(`startby.window`, so never at night) less your classes and calendar events, and here also your
[commitments](classes-and-timetable.md#commitments-gym-shifts-standups) and the exams themselves. `revision_share` (50%) of each day's free time goes
to blocks of `block_min` (60) minutes. Each block goes to the soonest exam still ahead that has topics left, and ends
before you leave for it (`leave_min`). An exam gets at most as many blocks as Start-by's size for it (10 hours until
you say: `/startby exam la a week`); `/revise` says when topics didn't fit.

**What to read.** With each topic: its own note, then the pages of class material that name it (Classroom's
downloaded files, your files folder: "Lecture 5 slides.pdf, pp. 3-7"), then book pages (the pages the concept graph
found it on, and pages of books Books has read that name it). Class material always comes first.

**Every day.** Today's blocks are fixed the first time they're worked out that day; later days are worked out again as
your notes and answers change. They're in the morning plan with Start-by's lines (the morning page, the wake-up call,
the drafted plan; with Start-by dates on) and on the Exam season card. At the evening check-in's time (`night_at`,
21:30, without Check-ins) one message asks about the day's topics: "Revision: did you cover Jordan form (Linear
Algebra) today?" with **Yes**, **Partly** and **No**. The answer counts like a quiz answer: the topic's quiz items are
graded (Yes as Good, 4 of 5; Partly 2; No 1, so they come back tomorrow) and the topic keeps the grade too. Tapping
another answer replaces the first; `/revise undo` takes the last one back.

**From Telegram.** `/revise` shows today's blocks and the next days'; `/revise la` one course's topics, ranked, with
why; "what should I revise today?" today's blocks.

**Settings that matter** (Dashboard → Settings → Exam season)

| Setting | Default | Effect |
|---|---|---|
| `exam_season.hold_updates`, `alarm_check`, `eve`, `leave_alarm`, `debrief`, `no_calls`, `budget` | all on | the parts above |
| `exam_season.night_at` | `21:30` | when the nightly alarm check runs |
| `exam_season.eve_at` | `18:00` | when the evening-before question can come |
| `exam_season.leave_min` | 45 | minutes before the start for the leave alarm |
| `exam_season.exam_min` | 180 | how long an exam is taken to last |
| `exam_season.quizzes` | off | on: quizzes and tests outside an exam period count too |
| `exam_season.quiz_call_at` | `19:00` | when a picked quiz call rings the evening before |
| `exam_season.revision` | on | the revision plan |
| `exam_season.revision_days` | 14 | the plan starts this many days before each exam |
| `exam_season.revision_share` | 50 | % of each day's free time that revision blocks may take |
| `exam_season.block_min` | 60 | one revision block, in minutes |
| `exam_season.revision_ask` | on | the evening question about the day's topics |

**What leaves your computer.** With Phone calls on, the leave-by alarm's time, the exam and what you said about it go
to your call line so it can ring, like any call. Nothing else.

**Turn it off / undo.** Features → Exam season → Turn off: its timers, leave-by alarms (also on your call line) and the
update hold go at once, and calls during exams are allowed again. Or switch off just the part you don't want.
Debriefs already written stay in your notes; your answers are kept in Kurooto's state folder (`exam_season.json`) for 30
days after each exam. The revision plan writes nothing in your notes; its days and your answers are in
`revision.json` (14 days of plans), and `/revise undo` puts a topic's quiz grades back as they were.

## Revision packs

**What it does.** `/pack` reads a subject's notes (course page, exam prep, lecture notes, solutions, and your books'
pages in the [source mix](books-and-study.md#the-source-mix)) and builds a 2 to 6 page revision pack: what's on it,
definitions, theorems with their hypotheses, formulas, worked problems, pitfalls and a self-test with answers. It comes
to Telegram as a PDF and is saved in your notes (`<subject>/revision-pack-<date>.tex` and `.pdf`; `revision-packs/`
when the subject has no folder; your files folder when you set one).

**Turn it on.** It's part of Skills (needs Chat): Features → Skills.

**From Telegram.** `/pack linear algebra`, or say what it's for: `/pack linear algebra midterm friday`. It takes a few
minutes. `/revision-pack` is the same skill. Your AI can also send you a pack you made before ("send me my linear
algebra pack").

**Making the PDF.** Kurooto uses **Tectonic** (a small LaTeX engine) if it's installed, else your computer's own LaTeX
(latexmk or pdflatex). With neither, the pack comes as a `.tex` file and a message asks **Install Tectonic** /
**Not now**. Install fetches about 25 MB from Tectonic's official releases; the first PDF then takes a few minutes while
it fetches about 50 MB of LaTeX packages into Kurooto's cache; later ones take seconds. After **Not now** it doesn't
ask again for 30 days. If a pack doesn't compile, the AI gets one try to fix its LaTeX; otherwise you get the `.tex`
with the first error line.

**Packs before exams.** With Deadlines on, the evening before a quiz or exam that has a subject (12 to 36 hours ahead,
from 16:00) you're asked "Linear Algebra midterm is tomorrow 10:00. A revision pack for it tonight?" with **Build it** /
**No thanks**, once per quiz or exam. With `skills.auto_pack` = `auto` it's built without asking and comes like a
`/pack` (in the background, never ahead of your own requests).

**Settings that matter** (Dashboard → Settings → Skills)

| Setting | Default | Effect |
|---|---|---|
| `skills.auto_pack` | `ask` | `ask`: the Build it / No thanks question; `auto`: build it; `off`: never offer |
| `skills.auto_pack_after` | `16:00` | not before this time of day |

**What leaves your computer.** The notes and book excerpts the AI reads go to your AI. Tectonic's install and its LaTeX
packages are downloaded from Tectonic's servers.

**Turn it off / undo.** `skills.auto_pack` = `off` stops the offers; packs already made stay where they are. Tectonic
lives in Kurooto's own folder and goes with `kurooto uninstall` (see [Updates and backups](updates-and-backups.md)).

## Hint ladder

**What it does.** Stuck on a problem? You get one step at a time: **the idea** first, then **the setup**, then **the
key step**. The full solution comes only when you ask for it. Every step names the lecture note the problem belongs to.

**Turn it on.** Features → Hint ladder (needs Subjects; uses your AI).

**From Telegram.**
- Send a photo of the problem with `/hint la` as the caption, or type it: `/hint la show that the trace is
  basis-free`. The subject's short name goes first (with only one subject, it's used anyway).
- **Next hint** (or reply "next", "more", "go on") gives the next step.
- After the key step, **Show the solution** (or reply "solution", "answer", "show me the answer" to any hint) gives the
  full solution.

**The course's AI policy.** The first time you use `/hint` for a subject, Kurooto asks what the course allows: **Hints
and full solutions**, **Hints only, no full solutions**, **No AI help**, or your own words. Your answer becomes a line
in the subject's course note: `AI policy: Hints only, no full solutions (your answer to Kurooto, 2026-10-20)`. After
that it reads the line from the note, so change it there; a line you wrote yourself (`AI policy: ...`) counts too.
A policy set for the course itself (`/subject policy la hints`, or the AI help box in the dashboard's Study pane:
allowed, hints, off) comes first, and then nothing is asked.
- "No full solutions" or "hints only": the ladder ends at the key step.
- "No AI help", "not allowed": no hints for that subject, and nothing is sent to the AI.

**How it's made.** The AI works out the whole ladder once and Kurooto shows it a step at a time. An answer that doesn't
come in steps is never passed on (it could give the solution away): you get "No hints this time" and can `/hint` again.
If the photo can't be read, it asks you to send it sharper or typed. It's the shipped `hint` skill: copy it into your
skills folder (`/skills copy hint`) to change how hints are written.

**Limits.** Photos need an AI that opens files itself (agy or Claude Code). With a Gemini key or another API service,
type the problem instead.

**What leaves your computer.** The problem (photo or text), the subject's AI-policy line, and the notes the AI reads to
find the lecture note go to your AI.

**Turn it off / undo.** Features → Hint ladder → Turn off. The "AI policy" lines stay in your course notes; delete them
there if you like.
