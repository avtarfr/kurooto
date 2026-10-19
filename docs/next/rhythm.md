# rhythm: check-ins, mornings, study sessions, the Sunday review, after-class notes, no-call times (for the 0.2.0 docs)

No new feature cards: everything below extends features that already exist. No new dependencies.

## MANUAL: replace "### Check-ins"

### Check-ins
At times you choose, Kurooto asks how the day is going: the **evening** check-in (default 22:00, the day in review),
the **night** one (default 23:15, goodnight) and an optional **midday** one. Reply to the message and it goes into
your journal (`journal/YYYY-MM-DD.md` in your notes folder).

- **Change one in plain English:** "move tonight's check-in to 21:30", "push the check-in by 30 min", "skip the night
  check-in". Other days work too: "skip Friday's check-in", "move tomorrow's check-in to 9". A day Kurooto can't pin
  down ("yesterday", "next week", a date) goes to the AI instead of guessing.
- `/checkins` lists today's, with **+30 min** and **Skip** buttons (and **Tomorrow morning** for the night one);
  `/checkin evening 21:30`, `/checkin night morning`.

**By call** (with Phone calls on; Settings → `checkins.by_call`):
- **Evening debrief** (5 to 8 minutes): how the day went; what each of today's classes covered (and the after-class
  questions you kept for this call); what slipped from today's plan; open questions; the study time it counted, and
  study away from the computer; a short quiz if an exam or quiz is in the next two weeks.
- **Night check-in** (3 to 5 minutes): anything more for the journal, study logs still due, tomorrow's top priority
  and when to wake you (it sets the alarm), goodnight. With the night check-in off, the evening one asks tomorrow's
  priority and the wake-up time.
- **Too tired?** Tap **Tomorrow morning** (on the ringing call's Telegram message, the missed-call message or
  `/checkins`), or say so on the call: the rest moves to your wake-up call, which starts with it before planning the
  day. With no alarm set, it's asked by message in the morning.
- **Afterwards**, with Chat on, the AI writes your journal entry from what you said (your words, not its own) and a
  study log for each class you talked about. Without Chat, what you said goes into the journal as it is.
- **"Call me back in an hour"** on a check-in call moves that check-in (the same call, with the same steps), never a
  plain reminder call. "Later" on the ringing phone does the same, half an hour on.
- **A call you don't answer** (after its repeats) **or decline** becomes a message with **Call me now / Tomorrow
  morning / Skip**; reply to it to answer by text. A check-in never stays "calling".
- A check-in call never interrupts a class, `/hold`, focus or another call: it waits until that ends, or comes as a
  message if that would be too late. The night itself doesn't hold the night check-in.

*Settings:* `checkins.times` (`evening`, `night`, `midday`; empty = off), `checkins.by_call`, `checkins.journal`,
`checkins.ai_notes` (default on: with Chat on, the AI writes the journal and study logs after a check-in call).

## MANUAL: replace "### Subjects and timetable"

### Subjects and timetable
Your courses with short names (`/subject add Linear Algebra (la, linalg)`) and your timetable
(`/class mon 09:00-09:55 la`). Kurooto never calls you during a class. `/classes today`, `/skip la` or "skipping LA
today" (not going), `/attend la` (undo). "not going to LA on Friday" and "skipping stats tomorrow" mark that day.

**Term dates:** `/term ends 2026-12-04` (the last day of classes) and `/term exams 2026-12-07 to 2026-12-18` (an exam
period; add as many as you need). On those days, after the term ends and on holidays there are no classes: no
after-class questions, and the timetable doesn't hold calls. `/term` shows them, `/term clear` removes them.

*Settings:* `subjects.holidays`, `subjects.exam_periods`, `subjects.term_ends`, `subjects.no_calls_in_class`,
`subjects.margin_min`.

## MANUAL: replace "### Weekly summary"

### Weekly summary
Every Sunday evening: the week in numbers (requests, reminders, check-ins, deadlines, quiz, study hours, journal
days). `/week` any time.

**Sunday review call** (optional, with Phone calls on; Settings → `weekly.call`): after the summary, a call of about
15 minutes: the week in numbers and study hours per subject, what went well and what didn't, anything Kurooto should
do differently, and next week's deadlines and your priorities. Afterwards it becomes a weekly review in your journal
(written by the AI with Chat on, your own words without). If the computer was off all Sunday evening, you get only the
summary.

## MANUAL: replace "### After-class notes"

### After-class notes
A couple of minutes after each class in your timetable ends, Kurooto asks what was worth keeping. Answer with a line
or two, photos of the board or slides, files or a voice note (reply to the question, or answer in the phone app or on
a call). It goes into that subject's `class-log.md`; photos and files are moved next to it (`<subject>/files/`) and
linked. With Chat on, the AI also writes a study log for the class (a lecture note in the subject's folder, linked from
the day's note). **Nothing new** ends it; **Later** keeps the question for your evening check-in call. No questions
for classes you skip, on holidays, in exam periods or after the term ends (Subjects → `/term`). Needs Subjects with a
timetable.

*Settings:* `capture.delay_min`, `capture.study_log` (default on: with Chat on, the AI writes a study log).

## MANUAL: Phone calls, add after "**Use:**"

**When Kurooto calls you:** a call you don't answer rings again 3 and 6 minutes later (`calls.realert_min`; `[]`
rings once), then becomes a "Missed call" message. The alarm has its own repeats. No calls during a class you attend,
a calendar event (or only `#nocall` ones, see Calendar), focus, `/hold`, the night or another call: one that comes due then is
held, you're told ("Held a call until 18:02 (class: Linear Algebra)"), and it's placed by itself when that ends.
"call me now" (or "ring me about the essay") calls right away.

## MANUAL: replace "### Morning alarm"

### Morning alarm
Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm volume, so it rings even
on silent. The call line places it, so it rings even if your computer is asleep. "wake me at 6:45", `/alarm 7:30`,
`/alarm off`, the evening check-in call ("wake me at 7"), or a daily default (Settings → `alarm.daily`). Not
answered: it rings twice more, 5 minutes apart. **Snooze** gives 10 minutes. Needs Phone calls.

- **The night follows your alarm:** while it's set, no other calls from your bedtime (`alarm.bedtime`, default: the
  start of the night hours) until it rings; once you're up, calls can come even if the usual night hours aren't over.
  Without an alarm, the night is the fixed hours (`availability.night`).
- **Your day, drafted:** with Chat on, 20 minutes before the alarm the AI drafts today's plan into today's daily note
  ("## Plan for today (draft …)": classes, what's due, a top 3, suggested blocks, and questions for you).
- **The wake-up call** goes through that plan, asks which classes you're skipping and when to call you today (the
  evening check-in, and a midday one if you want), and afterwards, with Chat on, settles "## Plan for today" in the
  daily note from what you said.
- **The morning page:** at the alarm, if this computer is awake, it opens the morning page in your browser (today's
  plan, classes, calendar, what's due, check-ins). It's also at `http://127.0.0.1:8770/morning`.

*Settings:* `alarm.daily`, `alarm.days`, `alarm.bedtime`, `alarm.prep_min` (default 20; 0 = no draft),
`alarm.open_page` (default on), `alarm.notes` (default on: the wake-up call goes into the daily note).

## MANUAL: replace "### Calendar"

### Calendar
Your calendar's events, read-only, from its private iCal link. Google Calendar on a computer: Settings → your calendar
→ Integrate calendar → **Secret address in iCal format**. Outlook and Apple Calendar have one too. Paste it in the
feature's card. `/today`, `/cal` (7 days), "what's on tomorrow?". It can remind you before each event
(`calendar.remind_min`). Refreshed every 15 minutes. The link lets anyone read that calendar, so it's kept in your
computer's keychain.

- **No calls during events:** every timed event holds calls (`calendar.no_calls_in_events`). If that's too much, set
  `calendar.nocall_events` to `tagged`: then only events with `#nocall` in the title or description hold calls, and
  every event in a calendar whose name contains "no call" (all-day ones too, e.g. "Exam day #nocall").
- **Focus events:** an event with `#focus` in its title or description is focus time while it runs: calls are held
  and messages that can wait are kept until it ends, then delivered together.

*Settings:* `availability.nocall_keyword` (`#nocall`), `availability.nocall_calendar` (`no call`),
`availability.focus_keyword` (`#focus`).

## MANUAL: replace "### Study tracker"

### Study tracker
How long you spend on each subject, counted from the window you're working in: a window whose title names a subject
(its name or a short name, a PDF called `linear-algebra-week3.pdf`, a note in that subject's folder) counts while
you're active. Only minutes per subject are kept, never window titles. Works on Windows, macOS (it asks once to see
window titles) and Linux on X11, Hyprland or Sway. Needs Subjects.

- **Away from the computer:** `/study la 50` (or "starting linear algebra for 50 min") starts a session; `/study
  stop` (or "done studying") ends it, and a timed one ends by itself with a nudge to take a break. While a session
  runs, the window doesn't count. Afterwards: `/studied 2h linear algebra` or "studied stats for an hour", or tell
  the evening call.
- **How much:** `/study` (today), `/study week`, "how much did I study today?".
- **In your notes:** at 23:45 the day's hours go into your daily note as "## Study hours" (`study.daily_note`; empty
  to turn it off).

## MANUAL: The dashboard, one line

The **morning page** (`http://127.0.0.1:8770/morning`) shows today's plan from your daily note, with your classes,
calendar, what's due, check-ins and open questions. The alarm opens it.

## Troubleshooting rows

| What you see | What to do |
|---|---|
| "Held a call until …" | A class, `/hold`, focus, a calendar event or the night was on. The call comes by itself when it ends; `/calls` lifts a hold. Too many events hold calls? Set `calendar.nocall_events` to `tagged`. |
| A call rang three times | It wasn't answered: repeats at +3 and +6 minutes. Answer, tap **Later**, or set `calls.realert_min` to `[]`. |
| No plan before my alarm | It needs Chat on and the alarm set at least a few minutes ahead (`alarm.prep_min`). The AI's answer is in the AI jobs tab. |
| The morning page didn't open | It opens only if the computer is awake with a screen at alarm time (`alarm.open_page`). Open `http://127.0.0.1:8770/morning` yourself. |
| No after-class question | The class was skipped, it's a holiday or exam period, or the term is over (`/term`). |
| A night check-in I didn't want | Set `checkins.times.night` to empty (Settings), or `/checkin night skip` for today. |
| "skip Friday's check-in" went to the AI | Kurooto acts by itself only for today, tomorrow, the day after or a weekday name; anything else (dates, "next week") goes to the AI. |

## CHANGELOG lines (0.2.0)

- Check-ins: the evening call is a debrief (classes, what slipped, open questions, study time, a quiz offer before
  exams); a new night check-in says goodnight (journal, study logs still due, tomorrow's priority, the alarm), or
  moves to your wake-up call with "Tomorrow morning"; afterwards the AI writes your journal and study logs from what
  you said. "Call me back later" on a check-in call keeps it a check-in. Unanswered or declined check-in calls become
  a message with Call me now / Tomorrow morning / Skip. Change another day's check-in ("skip Friday's check-in");
  `/checkins` has +30 min and Skip buttons.
- Mornings: the AI drafts your day 20 minutes before the alarm; the wake-up call goes through it, asks which classes
  you're skipping and when to call; the morning page opens on your computer.
- The night follows your alarm (bedtime to alarm); unanswered calls ring again at +3 and +6 minutes; held calls tell
  you so and come by themselves when the block ends; "call me now".
- Calendar: `#focus` events are focus time; `#nocall` events, or only those (`calendar.nocall_events: tagged`).
- Study tracker: study sessions away from the computer (`/study la 50`, `/study stop`, "starting stats for 50
  min", "done studying", "studied stats for an hour"), and a "Study hours" section in your daily note.
- Weekly summary: an optional Sunday review call, written up in your journal.
- After-class notes: answer later on the evening call, photos and files filed next to the class log, an AI study log,
  and no questions in exam periods or after the term (`/term`).
- Fixed: "skip Friday's check-in" (and "no calls on Friday", "skipping LA on Friday") changed today's instead.

## PRIVACY notes (rows to change in "Always (when the feature is on)")

| Feature | What leaves | Where to |
|---|---|---|
| Check-ins | nothing; with Check-ins by call and Chat on: what you said on the check-in call (and, after the evening debrief, both sides of it) goes to the AI to write your journal and study logs | the AI service you picked |
| After-class notes | nothing; with Chat on: your answer and the photos and files you sent with it, for the AI to write a study log | the AI service you picked |
| Morning alarm | the alarm time (your call line); with Chat on: the AI reads your notes before the alarm to draft the day's plan, and the wake-up call's transcript to settle it | your call line; the AI service you picked |
| Weekly summary | nothing; with the review call and Chat on: the call's transcript, to write the weekly review | the AI service you picked |
| Calendar | nothing leaves; event descriptions are read only for `#nocall` / `#focus` and aren't kept | (read from Google/Outlook/Apple) |
| Phone calls (add to its row) | the brief for calls while the computer is off now also has the steps for check-in, wake-up and Sunday review calls: today's plan from your daily note, today's classes, study hours counted, the week's numbers | your call line; Google (Gemini Live) on those calls |

Study tracker and its daily note section: nothing leaves (unchanged).

## For the coordinator

- No new module classes. New helper module `src/kurooto/modules/daily.py` (the daily note, running a skill,
  transcripts, the morning page's data).
- `app.py`, `cli.py`, `core/config.py`: untouched. `web/server.py`: one block, the `/morning` page route (before
  `/` and `/setup`). `web/api.py`: one block, `GET /api/morning`. New static files `web/static/morning.html`,
  `morning.js`.
- Shared API for others: `app.modules["calls"].place(reason, key="", alarm=False, force=False)` (study uses it);
  `app.availability.sleep` (a callable the alarm sets: the nights it covers); `calls.ring(..., buttons=[...])` adds
  buttons to the ring's Telegram message; `calls.live_call()` is the call going on now ({key, reason}); a module that
  places calls may define `call_reschedule(key, at) -> str` so "call me back later" during its call stays its call
  (check-ins and the alarm do; others get the same key and reason back).
- New call tool `defer_checkin`; `change_checkin` gained the action `defer` and the name `night`.
- Default change: `checkins.times.night` = "23:15" (on for everyone with Check-ins); set it to None to ship it off.
- Existing tests changed: `tests/unit/test_calls.py` (one ring test sets `calls.realert_min` to `[]`; scheduled
  calls now have `respect == "none"` because the hold is checked when they're due, to tell you).
