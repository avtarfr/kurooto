# Check-ins and journal

At times you choose, Kurooto asks how your day is going. Your answers go into a journal in your notes, one daily note
per day. Once a week you get your week in numbers, and in your first week a small daily quest helps you try things.

- [Check-ins](#check-ins)
- [Check-ins by call](#check-ins-by-call)
- [Your journal (the daily note)](#your-journal-the-daily-note)
- [Weekly summary](#weekly-summary)
- [First-week quests](#first-week-quests)
- [Messages these features send by themselves](#messages-these-features-send-by-themselves)
- [When something goes wrong](#when-something-goes-wrong)

---

## Check-ins

**What it does.** Up to three questions a day, each at its own time:

| Check-in | Default | Default question |
|---|---|---|
| **evening** | 22:00 | "How did today go? What got done, and what slipped?" |
| **night** | off | "Before bed: anything else for your journal? What's first tomorrow, and when should I wake you?" |
| **midday** | off | "How's the morning been? Anything to re-plan for the afternoon?" |

Reply to the message (Telegram's Reply) and your answer goes into today's journal: "Saved to your journal
(journal/2026-11-12.md)". In the Android app it's a card under **Waiting for you**: type how it went and tap **Send**,
or tap its buttons; with the computer asleep the answer waits on your call line
([phone-app.md](phone-app.md#check-in-and-quiz-cards)).

**The day's reflection** (`checkins.reflect`, on). The evening check-in message also lists up to three things the
day's records show you did, and asks one thing about tomorrow:

```
Evening check-in: How did today go? What got done, and what slipped?

From today's records:
- Problem set 3: done
- send the glacier draft to Ortiz: done
- Studied Linear Algebra 1.5 h

What's first tomorrow?
```

Only records count, never a guess from what you wrote: a deadline marked done (Done, ticked in your notes, handed in on
Classroom), an [open thread](talking-to-kurooto.md#open-threads-and-that-thing) closed as done, progress you gave on a
deadline ("Essay draft: 4 of 7 done"), study time of 15 minutes or more for a subject, and classes whose after-class
question you answered. In that order, three at most. Fewer happened: it lists what there is. Nothing recorded: no list
at all, just the question. There's no streak, no score and nothing about what you didn't do. **Not tonight** under it
ends the check-in for the day. Turn the reflection off with `checkins.reflect` (the message is then as before, with
**Skip today**).

**Turn it on.** Features → Check-ins. It needs Telegram. It's in the ★ Starter set. To turn on the night or midday
one, give it a time: Dashboard → Settings → Check-ins → `times`, e.g. `"night": "23:15"`. Both are off until you do.

**The buttons on a check-in message.**

| Button | What it does |
|---|---|
| **In 30 min** | asks again 30 minutes later (a night check-in pushed past the end of the day moves to the morning instead) |
| **Tomorrow morning** (night check-in only) | you're too tired: the rest moves to your wake-up call, or, with no alarm set, to a message in the morning |
| **Skip today** | no more of that check-in today |
| **Not tonight** (evening, with the reflection on) | the same as Skip today: the check-in is over for the day |

**From Telegram.**

| You send | What happens |
|---|---|
| `/checkins` | today's check-ins with their times and state, and buttons: **Evening +30 min**, **Skip evening** (and **Tomorrow morning** for the night one) for each still planned |
| `/checkin evening 21:30` | today's evening check-in at 21:30 (today only; the setting stays) |
| `/checkin midday 13:00` | turns on a midday check-in for today |
| `/checkin night skip` | no night check-in today |
| `/checkin night morning` | moves it to your wake-up call |
| `move tonight's check-in to 21:30` · `make the check-in at 9:30` | moves it (an evening or night time from 6 to 11 without "am" means pm) |
| `push the check-in by 30 min` · `postpone the evening check-in by an hour` | pushes it back |
| `skip the night check-in` · `no check-in today` · `cancel the midday check-in` | skips it |
| `skip Friday's check-in` · `move tomorrow's check-in to 9` | another day works for today, tomorrow, the day after or a weekday name |

A day Kurooto can't pin down ("yesterday", "next week", a date) goes to your AI instead of being guessed. "call me" in
the sentence is about a call, not a check-in.

**It learns your times** (`checkins.learn_times`, on). When, over the last two weeks, you answered a check-in on at
least 5 days and on 4 or more of them 30 minutes or more away from its time, always on the same side (you moved it,
or replied late but within 3 hours), its time moves to when you actually did it, to the quarter hour: "Your evening
check-in is at 23:00 from now on, not 22:00: on 5 of the last 6 days you did it around then", with **Undo**. It isn't
moved again for two weeks, and one you undid is left alone for a month.

**The check-in day runs from 05:00 to 05:00** (`checkins.day_starts`). A night check-in at 00:30, or one you push past
midnight, still belongs to the evening before: its journal entry and study logs go to that day. Still up at 1 am,
"move the evening check-in to 21:00" means the coming evening, and "skip the night check-in" skips the coming night's
once tonight's is over. Set it to `00:00` for plain calendar days. Once Kurooto has learned when you're usually up
([calls.md](calls.md#morning-alarm), `availability.learn_morning`), the day turns two hours before that (14:00 if you're
up around 16:00), unless you set it yourself.

**Lighter days.** The day after an exam or a heavy study day (`notify.calm.lighter_after`), the day's first check-in
comes an hour later. **Not today** under the morning line puts it back
([messages-it-sends.md](messages-it-sends.md#lighter-days-and-when-youve-gone-quiet)).

**On the dashboard.** The [Today page](dashboard.md) lists today's check-ins with their state, **+30 min** (pushes it
back half an hour, like **In 30 min** on Telegram) and **skip**.

**Limits and edge cases.**
- **The computer was off at check-in time:** if it's back within 2 hours, the check-in comes then. Later than that,
  you get "I missed your evening check-in (the computer was off). Reply here any time and I'll put it in your
  journal."
- **Focus time** holds a check-in message until focus ends. **Paused**: it comes when you resume.
- [Calm](messages-it-sends.md) counts check-in messages against the daily limit; past it they wait for the evening
  bundle.
- With `checkins.journal` off, replies are only thanked, not saved.

**Settings that matter** (Dashboard → Settings → Check-ins):

| Setting | Default | Effect |
|---|---|---|
| `checkins.times` | evening `22:00`, night off, midday off | when each one comes; empty or `null` turns it off |
| `checkins.questions` | as above | what each one asks |
| `checkins.journal` | on | save answers to your journal |
| `checkins.day_starts` | `05:00` | when a check-in day starts |
| `checkins.by_call` | off | with Phone calls on, check-ins are calls ([below](#check-ins-by-call)) |
| `checkins.ai_notes` | on | with Chat on, after a check-in call the AI writes your journal and study logs |
| `checkins.asleep_defers` | on | the night check-in call doesn't ring once you've gone to bed |
| `checkins.reflect` | on | the evening check-in lists up to three things today's records show you did and asks what's first tomorrow |

**What leaves your computer.** Nothing for message check-ins (your reply travels through Telegram to your own bot).
By call, see below.

**Turn it off.** Features → Check-ins → Turn off. One check-in only: empty its time in `checkins.times`. Your journal
stays.

---

## Check-ins by call

With [Phone calls](calls.md) on and `checkins.by_call` on, each check-in is a phone call instead of a message.

**Evening debrief** (5 to 8 minutes): how the day went; what each of today's classes covered (with the
after-class questions you kept for this call); what slipped from today's plan; open questions; the study time
Kurooto counted, and study away from the computer; a short quiz if a quiz or exam is in the next two weeks. With
`checkins.reflect` on, it says back in one line what the day's records show you did (the same list as the message).

**Night check-in** (3 to 5 minutes, if you turned it on): anything more for the journal, study logs still due,
tomorrow's top priority and when to wake you (it sets the alarm), goodnight. With the night check-in off, the evening
one asks tomorrow's priority and the wake-up time.

**Midday check-in**: a short call about the morning and the afternoon's plan.

**Afterwards.** With Chat on (and `checkins.ai_notes` on), the AI writes your journal entry from what you said, in
your words, not its own, and a study log for each class you talked about. Without Chat, what you said goes into the
journal as it is.

**When it can't ring now.** A check-in call never interrupts a class, a calendar event, `/hold`, focus, the night or
another call. It waits until that ends ("Your evening check-in call waits until 18:02 (class: Linear Algebra)"), or,
if that would push it into the next day, comes as a message. The night itself doesn't hold the night check-in (it's
the goodnight call).

**Too tired?** Say so on the call, or tap **Tomorrow morning**: the rest moves to your wake-up call, which starts with
it ("anything for Tuesday's journal? What did Linear Algebra cover?") before planning the day. With no alarm set,
you get a message in the morning instead ("Last night's check-in, as promised: ...") at the end of your night hours
(08:00 if you have none).

**"Call me back in an hour"** on a check-in call moves that check-in (the same call, with the same steps), never a
plain reminder call. Past tonight, a night check-in goes to the wake-up call. **Later** on the ringing phone does the
same, half an hour on (`calls.later_min`).

**Missed or declined.** A call you don't answer (after its repeats) or decline becomes a message with **Call me now**,
**Tomorrow morning** and **Skip**; reply to it to answer by text. A call with no outcome after 15 minutes becomes that
message too, so a check-in never stays "calling".

**Gone to bed.** With the [Morning alarm](calls.md) set, the night check-in doesn't ring once it's past your bedtime
(`alarm.bedtime`), or within 3 hours of you setting the alarm yourself. It moves to your wake-up call, and a message
says so ("Your alarm is set, so I took it you're asleep: the night check-in moves to your wake-up call.") with
**Call me now** and **Skip**. A night check-in you moved after setting the alarm still rings. Turn this off with
`checkins.asleep_defers`.

**The daily call limit.** [Calm](messages-it-sends.md) allows one call a day that comes by itself
(`notify.calm.calls`). Past it, a check-in comes as a message ("today's call came already"). `/calm calls 2` allows
two.

**While the computer is off.** Your call line knows today's check-in calls and rings them from what it last heard.

**What leaves your computer.** The call audio goes to Google (Gemini Live, your key) as for any call. With Chat on,
what you said goes to the AI you picked to write your journal and study logs.

**Turn it off.** `checkins.by_call` off: check-ins come as messages again.

---

## Your journal (the daily note)

Every day has one note in your notes folder:

| Notes layout | Where |
|---|---|
| `kurooto` (default) | `journal/YYYY-MM-DD.md` |
| `zettelkasten` | `dailies/YYYY-MM-DD.md` |
| your own | `notes.paths.daily`, e.g. `diary/{date}.md` |

Kurooto only ever adds sections at the end; what's already there stays as it is. What goes in:

| Section | From |
|---|---|
| `## Evening check-in (22:04)` (and night, midday) | your reply to a check-in |
| the AI's journal entry | a check-in call, with Chat on |
| `## Journal 14:30` | the dashboard's journal box or Ctrl+K `journal ...` |
| `## Plan for today` | the plan drafted before your alarm and settled after the wake-up call ([calls.md](calls.md)) |
| `## Study hours` | the [study tracker](books-and-study.md), at 23:45 |
| links to lecture notes and mail digests | study logs, the mail digest |
| your words, tasks ticked, ideas filed | the `/journal` skill ([skills-and-routines.md](skills-and-routines.md)) |

**Writing in it.**
- Reply to a check-in.
- `/journal <your day>`: the skill saves your words as written, links the notes you mention, ticks tasks you
  finished and files new ideas in `inbox/` (needs Skills and Chat).
- The dashboard's [Today page](dashboard.md): the Journal box (Ctrl+Enter saves), or `j had a good lab today` in
  its main box, or Ctrl+K `journal ...` anywhere on the board.
- Edit the note yourself, in any editor (Obsidian works).

The [weekly summary](#weekly-summary) counts journal days, and the [nightly look back](teaching-kurooto.md) reads
today's note unless you turn that off (`retro.journal`).

---

## Weekly summary

**What it does.** Every Sunday at 19:00 (`weekly.when`), your week in numbers:
- messages to Kurooto and AI requests answered (and failed);
- reminders set and delivered;
- check-ins answered out of those asked, and skipped;
- deadlines marked done and nudges sent;
- quiz answers and the average grade;
- journal days out of 7;
- lines from other features: study hours per subject (Study tracker), research activity, crunch weeks and what to
  start next week ([Start-by dates](reminders-and-deadlines.md#start-by-dates-and-crunch-weeks));
- **Needs a look**: what isn't working and could wait until Sunday ([your-computer.md](your-computer.md)).
- **People** (`weekly.people`, on): one line about the people in your [project notes](research.md), only from
  what's logged there (minutes, "Last met", "Meets:"): who you met this week, who's next in the coming week, and
  anyone you meet regularly but haven't met for three weeks. "People (from your project notes): met Dr Okafor
  (guide, Glacier drift) Tue. next: Mira Castell Mon 10:00." It's never a message of its own, and nobody is mentioned
  from chats or mail.

`/week` shows it any time (the last 7 days). Everything is counted from Kurooto's own event log on this computer.

**Sunday review call** (optional; needs Phone calls; `weekly.call` on): after the summary, a call of about 15 minutes:
the week in numbers and study hours per subject, what went well and what didn't, anything Kurooto should do
differently, next week's deadlines and your priorities. Afterwards it becomes a weekly review in your journal (written
by the AI with Chat on, your own words without). If the computer was off all Sunday evening (more than 3 hours past
the time), you get only the text.

**Turn it on.** Features → Weekly summary. It needs Telegram.

**Settings that matter.**

| Setting | Default | Effect |
|---|---|---|
| `weekly.when` | `weekly sun 19:00` | when it comes (`weekly <day> <HH:MM>`) |
| `weekly.call` | off | the Sunday review call after it |
| `weekly.people` | on | the People line from your project notes |

**What leaves your computer.** Nothing but the message itself. With the call, the call audio goes to Google, and with
Chat on, the transcript goes to your AI to write the review.

**Turn it off.** Features → Weekly summary → Turn off (or **Less of this → Stop** on a summary). With it off, health
problems that could wait come as one message on Sundays instead.

---

## First-week quests

**What it does.** For your first seven days, one short message a day at 18:00 with one thing to try. Each leaves
something real behind. The quests, as your features allow:

| Quest | Needs | What it suggests |
|---|---|---|
| timetable | Subjects | add tomorrow's classes: `/class tue 09:00-09:55 la` |
| deadline | Deadlines | send one real deadline: "I have problem set 3 due fri 17:00" |
| reminder | Reminders | "remind me at 21:00 to pack my bag" |
| doubt | Doubt queue | "I have a doubt about Linear Algebra: ..." |
| quiz | Quiz | "quiz me on Linear Algebra" |
| study | Study tracker | `/study la 25` |
| check-in | Check-ins | answer tonight's check-in in a line or two |
| remember | Remember | "remember that I prefer short answers" |
| journal | Skills | `/journal what I did today` |

**Rules.**
- Only features that are on and pass their checks (what `kurooto doctor` looks at) get a quest; one you've already
  done (there's a timetable, you set a reminder this week) is left out. A day with nothing to suggest sends nothing.
- A quest is done when the thing happens. Replying to the quest message with it works too: "remind me at 21:00 to
  pack my bag" as a reply sets the reminder.
- **Skip this one**: tomorrow brings another.
- **Stop these**, or a reply of "stop", "no more" or "no": no more quests, for good.
- Leaving a day's quest alone (not done, not skipped, not answered) also stops them for good. No nagging.
- No AI is involved and nothing leaves your computer.

**Turn it on.** Features → First-week quests (in the setup page's Features step or the dashboard).

**From Telegram.** `/quests` shows how far they got (and why they stopped, if they did). `/quests stop` ends them.

**Settings.** `quests.when` (`daily 18:00`), `quests.days` (`7`).

**Turn it off.** Features → First-week quests, or `/quests stop`. What the quests had you add (classes, deadlines,
reminders) is yours and stays.

---

## Messages these features send by themselves

Each has **Why?** and **Less of this** buttons on Telegram ([messages-it-sends.md](messages-it-sends.md)).

| Message | Why it came | Less of this → Stop does |
|---|---|---|
| "Evening check-in: How did today go?..." | a check-in you set up (`checkins.times`) | that check-in's time is turned off |
| A check-in call | `checkins.by_call` | check-ins come as messages |
| "Your evening check-in call waits until ..." · "...moves to your wake-up call" | a check-in call that moved | |
| "I missed your evening check-in (the computer was off)..." | a check-in the computer was off for | |
| The weekly summary | `weekly.when` | Weekly summary is turned off |
| The Sunday review call | `weekly.call` | no Sunday review call |
| A first-week quest | `quests.days` | the quests stop |

Once a month, Calm may suggest turning off a kind of question you rarely answer, such as check-ins.

---

## When something goes wrong

| What you see | What to do |
|---|---|
| No night check-in | It's off until you give it a time: Settings → Check-ins → `times`, e.g. `"night": "23:15"`. |
| A night check-in I didn't want | Empty its time in `checkins.times`, or `/checkin night skip` for today. |
| The night check-in didn't ring | The alarm was set and it was past your bedtime: it moved to the wake-up call (a message said so). `checkins.asleep_defers` off makes it always ring. |
| The evening check-in didn't list something I did | It lists only what was recorded that day (a deadline marked done or given progress, a thread closed, 15+ minutes of study, an after-class answer), three at most. Mark the deadline Done, or `/threads done N`. |
| A check-in call came as a message | The day's one call (`notify.calm.calls`) had come already, or a class, event, `/hold` or the night would have held it into the next day. `/calm calls 2` allows two calls. |
| "skip Friday's check-in" went to the AI | Kurooto acts by itself only for today, tomorrow, the day after or a weekday name. |
| "I missed your evening check-in" | The computer was off for more than 2 hours past the time. Reply to that message and it still goes into the journal. |
| My reply wasn't saved | Reply to the check-in message itself (Telegram's Reply), and check `checkins.journal` is on. |
| No Sunday review call | `weekly.call` off, Phone calls not set up, or the computer was off more than 3 hours past the summary's time. |
| The quests stopped | You tapped Stop, replied "stop", or left a day's quest alone. `/quests` says which. |
