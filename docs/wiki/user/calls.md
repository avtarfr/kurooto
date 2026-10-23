# Phone calls and the morning alarm

Kurooto can ring your phone, and you can ring it. Calls go through your own **call line**, a small free program on
your own Cloudflare account, and the voice is Google's Gemini Live with your own Gemini key. Calls keep working while
your computer is asleep or off, from what it last sent.

This page covers calls, the morning alarm and reminders with the lid shut. Pairing and using the phone itself is on
[Your phone](phone-app.md).

- [How calls work](#how-calls-work)
- [Set up Phone calls](#set-up-phone-calls)
- [Calling Kurooto](#calling-kurooto)
- [Kurooto calling you](#kurooto-calling-you)
- [When calls are held](#when-calls-are-held)
- [On a call](#on-a-call)
- [What a call can do](#what-a-call-can-do)
- [When the voice service is down](#when-the-voice-service-is-down)
- [Live voice or your phone's own speech](#live-voice-or-your-phones-own-speech)
- [The look back after every call](#the-look-back-after-every-call)
- [While your computer is off](#while-your-computer-is-off)
- [Morning alarm](#morning-alarm)
- [Reminders with the lid shut](#reminders-with-the-lid-shut)
- [Calls from a terminal or script](#calls-from-a-terminal-or-script)
- [All call settings](#all-call-settings)
- [What leaves your computer](#what-leaves-your-computer)
- [Turn it off](#turn-it-off)

---

## How calls work

**What it does.** Three pieces work together:

| Piece | What it is |
|---|---|
| Your computer | Runs Kurooto. It keeps one outgoing connection to your call line (works behind any home or campus network; nothing on your computer listens to the internet) and answers what calls ask for: your notes, reminders, deadlines. |
| Your call line | A Cloudflare Worker named `kurooto-` plus random letters, at a `workers.dev` address, on your own free Cloudflare account. It rings your phone, hosts the call page, and keeps a short brief so calls work while the computer is off. The address is public but useless without the keys only your computer and paired phones have. |
| Your phone | The Kurooto Android app, or the Kurooto web app on an iPhone's Home Screen, or any browser with a call link. See [Your phone](phone-app.md). |

During a call the audio goes between your phone and Google (Gemini Live, your key). Only tool requests ("what's
due?", "add a reminder") come back to your computer.

Every 5 minutes, and whenever your scheduled calls change, your computer sends the call line what it needs while the
computer is off: how to talk, a brief (what's due, today's classes and check-ins, open questions), and the calls
booked for the next 24 hours (up to 30).

## Set up Phone calls

**What it needs.**
- A Gemini API key (free from Google AI Studio). If your main AI is something else, the setup asks for one; calls,
  voice notes and the alarm always use it. See [AI brains](ai-brains.md).
- A free Cloudflare account. You can make one during setup.
- About 350 MB of disk, once: Node.js (about 120 MB, inside Kurooto's own folder) and the call line's packages (about
  230 MB).

**Turn it on.**
1. Dashboard → **Features** → **Phone calls** → paste your Gemini key if it asks → **Set up** (or tick Phone calls in
   the setup wizard).
2. Kurooto installs what it needs (with progress), then opens Cloudflare's sign-in in your browser. Sign in or make
   an account, and approve. Kurooto uses its own Cloudflare login, kept apart from any other Cloudflare login on your
   computer.
3. Kurooto makes your `workers.dev` subdomain if you don't have one, creates the call line's keys, deploys it, checks
   it answers, and connects.
4. Pair your phone: [Your phone](phone-app.md).

Setup is safe to repeat. If the Cloudflare sign-in didn't finish, press **Set up** again; the sign-in link is also in
the progress log.

**After Kurooto updates itself**, it checks at 05:10 whether the call line's code changed and redeploys it in the
background. If that fails you get "Your call line couldn't be updated: ... (calls keep working on the old version;
Settings → Features → Phone calls → Set up tries again)." This doesn't happen when `updates.mode` is `off`.

## Calling Kurooto

**From Telegram:** `/call` sends a **Call now** button with a link. It works from any phone or browser for 2 hours.

**From the phone app:** the Android app and the iPhone Home Screen app have a **Call** button.

**What happens:** Kurooto picks up, starts by looking at what needs your attention (open questions first), and talks
like a friend on the phone. Talk in any language Gemini Live speaks; it follows yours.

## Kurooto calling you

Every kind of call Kurooto can place, and where each is explained:

| Call | When | More |
|---|---|---|
| A reminder call | "call me at 5 about the laundry", "call me in 20 minutes about the essay" | below |
| Right now | "call me now", "ring me", "give me a call" | below |
| Morning alarm | the time you set, or your daily alarm | [Morning alarm](#morning-alarm) |
| Morning call on request | "I'm awake", "I just woke up", "I'm up" (needs the Morning alarm feature) | [Morning alarm](#morning-alarm) |
| Check-in debrief | evening (and night or midday if you set them), with `checkins.by_call` on | [Check-ins](check-ins-and-journal.md) |
| Deadline nudge | six hours before something you hand in (`deadlines.urgent_h`), with `deadlines.call` on | [Reminders and deadlines](reminders-and-deadlines.md) |
| Quiz | `/quiz la call`, "quiz me by call", or the practice offer's **Call me for a quiz** | [Quiz and exams](quiz-and-exams.md) |
| Sunday review | after the weekly summary, with `weekly.call` on | [Check-ins and journal](check-ins-and-journal.md) |
| Leave for an exam | exam day, with Exam season on and its leave alarm part on | [Quiz and exams](quiz-and-exams.md) |
| Quiet research project | **Remind me tomorrow** on the "what's up with this project?" question | [Research](research.md) |
| From a script | `kurooto call "the backup finished"` | [below](#calls-from-a-terminal-or-script) |

**Plain English that books or places calls** (these work on Telegram, the dashboard's box and `kurooto ask`):

| You say | What happens |
|---|---|
| "call me at 5 about the laundry" | A call at five o'clock. "at 5" is a clock time, never "in 5 minutes"; said in the afternoon, it means 17:00. |
| "call me in 20 minutes about the essay", "call me tomorrow at 7", "call me tonight at 9 to revise" | A call then. Without "about ..." the reason is "a reminder call". |
| "call me now", "ring me about the essay", "give me a call" | Rings right away, even during a class or a hold (you asked). |
| "call me, I didn't wake up at 12" | Nothing is booked. A time that's about the past, or something that didn't happen, is never used as the time of a call; Kurooto asks "When should I call?". |
| "cancel that call", "cancel the 12:00 call", "cancel tomorrow's 9 call" | Cancels the one booked call it can mean. If several fit (or none), it lists your booked calls, each with a **Cancel** button and its key. Check-ins and the alarm aren't in that list: use `/checkins` and `/alarm`. |
| "call me for a quiz", "quiz me by call" | A quiz call (Quiz's own request). |

**When it rings.** Your paired phones ring for up to 60 seconds (`calls.ring_s`). Telegram gets a quiet "Calling
you: ..." message with an **Answer** link, so you can pick up from any device. That Telegram message is silent when a
phone app is paired (`telegram.silent_kinds`). If your computer can't reach your call line, Telegram instead gets an
urgent "I tried to call you, but your call line isn't connected." with the same **Answer** link.

**Buttons on the ringing phone:**

| Button | Does |
|---|---|
| Answer | Starts the call. |
| Later | Rings again in 30 minutes (`calls.later_min`). For a check-in it moves the check-in by that much; for the alarm it's **Snooze** (10 minutes, `alarm.snooze_min`); for an exam leave-by alarm, 5 minutes (twice at most). |
| Decline | Stops ringing. A reminder call ends there (no missed-call message). A declined check-in becomes a message you can answer by text. A declined alarm counts as "you're up". |

**Not answered.** A call you don't answer rings again 3 and 6 minutes after the first (`calls.realert_min`; `[]` rings
once), unless calls are held by then. After the last ring you get **Missed call: ...** on Telegram with:

| Button | Does |
|---|---|
| Call back | A link that calls Kurooto about the same thing. |
| In 30 min | Books the same call again 30 minutes later. |

Check-ins, the alarm, deadline nudges and exam leave-by alarms have their own follow-ups instead (a check-in becomes
a message with **Call me now / Tomorrow morning / Skip**; the alarm repeats; a missed deadline call becomes an urgent
message; a missed leave-by alarm becomes an urgent "Time to leave" message).

**The daily call limit.** With Calm on (the default), at most 1 call a day comes by itself
(`notify.calm.calls`). Past that, a check-in comes as a message, and any other call waits in the evening bundle with a
**Call now** link (valid for 26 hours). Calls you asked for, the alarm, the exam leave-by alarm and a deadline less
than 12 hours away never count and are never held. `/calm calls 2` allows two. See
[Messages Kurooto sends by itself](messages-it-sends.md).

## When calls are held

A call that comes due when you shouldn't be disturbed waits, and you're told: **"Held a call until 18:02 (class:
Linear Algebra): the essay"**. It's placed by itself when the block ends.

| What holds calls | Details |
|---|---|
| Another call | Nothing else rings while you're on a call (also when the computer is off). Updates wait too. |
| `/hold 18:00`, `/hold 2h`, "no calls for an hour" | Until then. `/calls` or "calls are fine again" lifts it. Messages still come. |
| Focus | `/focus 2h`, or a calendar event with `#focus`. Calls held and non-urgent messages wait. |
| The night | `availability.night`, 23:30 to 07:00. With the alarm set, the night is from your bedtime until the alarm instead (see [Morning alarm](#morning-alarm)). |
| A class | Every class on your timetable, plus 5 minutes before it (`subjects.margin_min`), while `subjects.no_calls_in_class` is on. A class you `/skip` doesn't hold calls. Holidays, exam periods and days after the term ends have no classes. |
| A calendar event | Every timed event (`calendar.no_calls_in_events`), or only events tagged `#nocall` and events in a calendar whose name contains "no call" when `calendar.nocall_events` = `tagged`. |
| An exam | With Exam season on and its `no_calls` part on: from 15 minutes before an exam until `exam_season.exam_min` (180) minutes after it starts. |

Never held: the morning alarm and exam leave-by alarms (they ring through the night and holds), "call me now", and
`kurooto call --force`. A repeat ring of an unanswered call is dropped (it becomes a missed call) if a block started
meanwhile.

**Check-ins** wait out a block and ring when it ends, or come as a message if that would be too late. See
[Check-ins](check-ins-and-journal.md).

## On a call

- **Speak naturally.** You can interrupt it, as on a real call.
- **Interrupt** button: talk over it when the loudspeaker's echo keeps cutting it off.
- **Mic gate** slider: needs a louder voice before it counts as speech. Move it right in a noisy room.
- **Earpiece / Speaker**: switches output. Some browsers can't switch; use earphones then. In the Android app the
  screen goes off at your ear.
- **Mute**, **Hang up**.
- **Open questions and approvals come first.** Every call starts with what needs you (`pending_items`): open
  questions, approvals, deadlines soon, today's classes and check-ins, calls booked. Answer them by voice. An approval
  that arrives during a call is asked right away.
- **"Call me back in an hour"** during a check-in or the wake-up call moves that same call (with its steps), not a new
  reminder call. On the wake-up call it works like a snooze.
- **Long jobs:** ask for something that needs real work ("write up a plan for the lab report") and it hands it to the
  AI on your computer (`run_task`, needs Chat). It says it's started and keeps talking; the result is told on the call
  when it's ready, or sent to Telegram as "From your call: ..." if the call ended.
- **Your persona:** `calls.persona` adds words on how to talk, e.g. "be brief and a bit cheeky".

The call's transcript is kept on your computer (Kurooto's state folder → `calls/transcripts/`, readable only by your
user account). A check-in's transcript becomes your journal and study logs; the wake-up call's becomes today's plan.

## What a call can do

Each feature you turn on adds what calls can do; a feature that's off adds nothing. In plain words:

| You can ask | Needs | Works while the computer is off |
|---|---|---|
| What needs my attention? (asked at the start of every call) | Phone calls | yes, from the last brief |
| Search my notes; read a note | Phone calls | keyword search over titles and headings only; whole notes only with Notes sync on |
| Call me back later about something | Phone calls | yes (queued) |
| Call me now | Phone calls | needs the computer |
| No calls until a time, or lift a hold | Phone calls | yes (queued) |
| Do a bigger job on my computer (write, plan, file) | Chat | yes (queued) |
| Answer an open question or approval | always | yes (queued) |
| How are my syncs doing? | always | needs the computer |
| Add a reminder | Reminders | yes (queued) |
| Move, skip or defer a check-in; the check-in's steps | Check-ins | yes (queued) |
| Mark a deadline done, add or move one, ignore a topic, add a recurring quiz | Deadlines | yes (queued) |
| When should I start X; this is about a day of work | Start-by dates | start dates from the last brief; sizes queued |
| I'm skipping a class today | Subjects | yes (queued) |
| Quiz me (questions, grading); schedule a quiz | Quiz | questions from the last brief; grades and scheduling queued |
| Set, skip or turn off the alarm; when is my alarm | Morning alarm | yes |
| Log study time; how much did I study | Study tracker | logging queued; totals need the computer |
| Remember how I like to be helped | Remember | yes (queued) |
| Keep an eye on something for a while | Nightly look back | yes (queued) |
| The week in numbers; the Sunday review's steps | Weekly summary | the review's steps from the last brief; the numbers need the computer |
| Block time in the Agent plan calendar | Agent plan calendar | yes (queued) |
| Send me a file, several files, or a study pack | Skills | yes (queued) |

"Queued" means it's saved on your call line and done as soon as the computer is back; you then get "Done what you
asked for on a call while the computer was off (N item(s))."

## When the voice service is down

Google's live voice sometimes refuses calls ("503: the service is currently unavailable"). The call still happens, in
one of three ways, tried in order:

1. **Live again.** The call page shows "Reconnecting…" and tries after about 1 second, then 3, each time with the next
   Live model: `calls.live_model`, then `calls.live_models`. A call that drops in the middle is tried again once.
2. **Turn by turn.** "The live voice isn't working, so we'll take turns." Your phone's own speech recognition hears
   you, a text AI answers, and your phone reads the answer aloud. Tap **Talk** if it stopped listening; tap while it
   speaks to skip the rest. Same call, same steps, same tools. Your computer answers each turn (your Gemini key, or the
   model on your computer with `calls.turn_brain` = `local`; never agy or Claude Code, which are too slow to start).
   If the computer is off or doesn't answer within 25 seconds, Gemini on your call line answers.
3. **Text on Telegram.** When your phone can't turn speech into text, or there's no microphone: "Your call couldn't
   go on by voice (...), so let's carry on here." The call goes on as messages, about the same thing. Reply or just
   type; what you type is part of the call, not a new request. **End the call** ends it, and so do 20 minutes without
   a message ("Ended the call (no messages for 20 minutes)."). Without Telegram, it goes to the phone app with a Reply
   box. If it happened while the computer was off, it starts on Telegram when the computer is back, within 2 hours;
   later than that you get "A call couldn't connect by voice while this computer was off ... Tell me here if it still
   matters."

Whichever way the call went, its transcript is kept and used the same way. `kurooto doctor` has a line "Phone calls:
voice service": how often Live failed this week and what calls did instead, and it names a model in your list that
Google says no longer exists.

## Live voice or your phone's own speech

`calls.voice_mode` decides how calls listen and speak:

| Value | Does |
|---|---|
| `auto` (default) | Gemini Live, and your phone's speech when Live fails. |
| `live` | Live only. When it fails, the call goes to Telegram. |
| `phone` | Your phone's speech, turn by turn, every time. Live only when the phone can't. |

`calls.voice_by_kind` sets it per kind of call, e.g. `{"alarm": "phone", "checkins:night": "phone",
"checkins:evening": "live"}`. Kinds: a feature's name (`alarm`, `checkins`, `weekly`, `quiz`, `deadlines`,
`research`), one of its calls (`checkins:evening`, `checkins:night`, `checkins:midday`), `reminder` (reminder calls)
and `outgoing` (calls you start). The more exact kind wins.

| | Live (Gemini Live) | Your phone's speech (turn by turn) |
|---|---|---|
| Feel | a real conversation: you can interrupt, it hears your tone | walkie-talkie: you talk, then it answers; tap Talk to cut in |
| Wait for an answer | under a second | about 2 to 5 seconds a turn |
| Languages | the ones Gemini Live speaks | the ones your phone's recognizer and voice have installed (your phone's language) |
| Where your voice goes | audio to Google (Gemini Live, your key) | Android 13+ with your language downloaded for on-device recognition: stays on the phone. Otherwise your phone's speech service (usually Google; Apple on iPhone; Chrome sends it to Google). Each turn's text goes to your computer's AI or Gemini. |
| When Google's live voice is down | retries, then turn by turn | not affected |
| Screen | off at your ear (Android app, earpiece) | stays on, on the loudspeaker (phones stop listening when the screen goes off) |

**Limits of turn by turn:** the screen has to stay on (the app keeps it on; in a browser don't lock the phone or switch
apps, or tap **Talk** again). It uses the loudspeaker by default; **Earpiece** switches, but your cheek can tap
buttons. It can't hear you while it speaks. On iPhones and some browsers, answers are read aloud only where the
browser has a voice; otherwise you read them.

**The voice itself:** `calls.voice` names a Gemini Live voice (e.g. `Kore`); empty is Google's default.
`calls.voice_by_model` picks a voice per Live model. The backup Live models only get one of Google's prebuilt voices.

## The look back after every call

**What it does.** New in 0.5.8. After every call that said something (at least 4 lines), a stronger AI request (your
main AI, at high effort) reads the transcript and the tools the call used, and:

1. **Does what slipped through.** Anything you asked for that the call misheard, forgot, promised without doing, or
   where a tool failed: it does it now if it's safe to do unasked (a reminder, a note, a deadline, a journal line, an
   answer you wanted). Anything that sends a message, places a call, deletes or spends money it doesn't do: it lists
   it under "Needs you".
2. **Keeps lessons.** Up to 3 short, general instructions for future calls ("When they say 'after class', ask when
   class ends before setting the reminder."). Every later call is told them. No names or details of other people,
   nothing secret.

**The message.** Only when something was fixed or learned: "After the call: <what it fixed>", "Needs you: ...", and
"Learned for next time: ..." with a pointer to `/lessons`. A call where nothing slipped and nothing was learned sends
nothing.

**From Telegram:**

| Command | Does |
|---|---|
| `/lessons` | Lists what calls have learned, numbered. |
| `/lessons forget 2` | Removes lesson 2 (`remove 2` and `drop 2` work too). |
| `/lessons clear` | Removes every lesson. |

The lessons are a plain file you can edit: Kurooto's state folder → `calls/lessons.md` (one `- ` line each). At most
`calls.lessons_max` (12) are kept: a new lesson that says much the same as an old one replaces it, and the oldest go
first.

**Settings that matter** (Dashboard → Settings → calls):

| Setting | Default | Effect |
|---|---|---|
| `calls.review` | `true` | The look back after every call. `false` turns it off. |
| `calls.review_effort` | `high` | How hard the AI thinks. |
| `calls.review_brain` | empty | Which AI does it; empty is your main AI. |
| `calls.lessons_max` | `12` | How many lessons are kept. |

**Limits.** It needs a main AI set. It runs in the background lane, so it waits behind nothing you asked for, and it
counts as background work for free limits (it can wait past 70% of a known daily limit; see
[AI brains](ai-brains.md)).

**What leaves your computer.** The transcript and the call's tool results go to the AI you picked, like any request.

**Turn it off.** `calls.review` = `false`. Lessons already kept stay until you `/lessons clear`.

## While your computer is off

- **Calls Kurooto booked still ring:** your call line holds the next 24 hours of calls (reminder calls, check-ins,
  the alarm, leave-by alarms) and places them itself. When the computer is back: "While this computer was off, your
  call line called you: ...".
- **You can still call.** The call says the computer is off and answers from the last brief: what's due, today's
  classes and check-ins, open questions, your notes' titles. Notes search is keyword-only; whole notes can be read only
  with [Notes sync](notes-and-concept-graph.md) on (from your GitHub repository).
- **What needs the computer** is either saved and done when it's back ("Saved. Their computer is off; it will do this
  as soon as it's back on.") or the call says it can't right now.
- **Answers you give on the phone** wait on your call line and are used when the computer is back.
- **Paused** (`/pause`): the call line keeps placing scheduled calls, so the alarm still rings.
- **Turned off** (`kurooto off`): the call line stops placing scheduled calls and drops what it holds, until you turn
  Kurooto on again. `kurooto off --keep-calls` keeps them (for the alarm).
- **On battery:** calls and the alarm keep working in every battery mode except `pause`. See
  [Your computer](your-computer.md).

## Morning alarm

**What it does.** Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm volume,
so it rings even on silent. Your call line places it, so it rings even if your computer is asleep or off.

**Turn it on.** Dashboard → Features → Morning alarm. Needs Phone calls.

**From Telegram:**

| Command | Does |
|---|---|
| `/alarm` | What's set: the next alarm, the daily alarm and its days, skipped days. |
| `/alarm 6:45`, `/alarm tomorrow 7`, `/alarm 7:30am` | Sets the alarm. |
| `/alarm off` | Clears the alarm that's set. With a daily alarm, that morning is skipped and the daily one comes back after. |
| `/alarm skip friday`, `/alarm skip tomorrow` | No alarm that day; the daily alarm is back the day after. |
| `/alarm daily 7:00` | The daily alarm. |
| `/alarm daily off` | Stops the daily alarm (an alarm you set for one morning stays). |

**Plain English:** "wake me at 6:45", "wake me up at 7 tomorrow", "set my alarm for 7", "cancel my alarm", "no alarm
tomorrow", "cancel Friday's alarm", "don't wake me on Saturday", "turn my daily alarm off", "do I have any alarms?",
"when is my alarm?". On the evening check-in call: "wake me at 7". The `/goodnight 7:00` skill sets it too.
"Tomorrow" said at 2 am means the coming morning (the day runs from `checkins.day_starts`, 05:00).

**The Today page** has the alarm with a box ("7:30", "tomorrow 6:45"), skip tomorrow, off, and the daily alarm. See
[Dashboard](dashboard.md).

**How it rings:**
- Not answered: rings again 5 minutes later, up to twice more (`alarm.retries`).
- **Snooze** on the ringing phone: 10 minutes (`alarm.snooze_min`). "Call me back in ten minutes" on the call does the
  same.
- One alarm per morning: one you set for a morning replaces the daily alarm.
- The daily alarm is always with your call line well before the night: the next one is sent as soon as one has rung,
  at start, after the computer wakes, and checked every 30 minutes.

**The night follows your alarm.** While an alarm is set, no other calls from your bedtime (`alarm.bedtime`; empty means
the start of the night hours, 23:30) until it rings, and once you're up calls can come even if the usual night hours
aren't over. An alarm set for a nap counts from when you set it. Without an alarm, the night is the fixed hours
(`availability.night`). With `availability.night.alarm_only` on, the fixed hours stop holding calls: only bedtime to
the alarm does, and with no alarm set nothing holds calls overnight (a reminder call you set for 02:00 rings at 02:00).
Off (the default) is the safe choice.

**Your day, drafted.** With Chat on, 20 minutes before the alarm (`alarm.prep_min`) the AI drafts today's plan into
today's daily note under "## Plan for today (draft …)": classes, what's due, a top 3, suggested blocks, questions for
you (the `morning-prep` skill). It runs once a day and never holds up your own requests.

**The wake-up call** goes through that plan, asks which classes you're skipping, what's due, start-by dates that have
come, when to call today (the evening check-in, and a midday one if you want), and wishes you a good day. If last
night's check-in was moved to this call, it starts with that. Afterwards, with Chat on, the AI settles "## Plan for
today" in the daily note from what you said (the `morning` skill); without Chat, your words go into the daily note as
they are (`alarm.notes`).

**The morning page.** At the alarm, if this computer is awake and has a screen, it opens
`http://127.0.0.1:8770/morning` in your browser (`alarm.open_page`): today's plan, classes, calendar, what's due,
check-ins and open questions.

**"I'm awake".** Say "I'm awake", "I just woke up" or "I'm up" (even with "call me if you need to ...") and Kurooto
rings the morning call now, planning from the current time, and opens the morning page. It's a plain call, not the
alarm: no snooze, no repeat rings. If an alarm is still set within 12 hours, it says so ("cancel my alarm" turns it
off).

**Keep this computer awake until the alarm** (`alarm.keep_awake`, off): from 12 hours before the alarm until 15
minutes after it rings (or until you answer), the computer doesn't sleep by itself, so the plan is drafted in time.
Linux: it keeps running with the lid closed too. macOS: a closed lid still sleeps a Mac (unless an external display is
attached). Windows: the lid follows Power Options. On battery, setting the alarm says "Plug this computer in: it stays
awake until then." The hold ends by itself, even if Kurooto stops; the screen can still turn off.

**Settings that matter** (Dashboard → Settings → alarm):

| Setting | Default | Effect |
|---|---|---|
| `alarm.daily` | empty (off) | A time like `07:00`: rings every day on `alarm.days`. |
| `alarm.days` | every day | Days the daily alarm rings, e.g. `["mon","tue","wed","thu","fri"]`. |
| `alarm.reason` | `Wake-up call` | What the ringing phone shows. |
| `alarm.retries` | `2` | Extra rings, 5 minutes apart, if you don't answer. |
| `alarm.snooze_min` | `10` | Snooze length. |
| `alarm.bedtime` | empty | With an alarm set, no calls from this time until it rings. Empty: the night's start (23:30). |
| `alarm.prep_min` | `20` | Minutes before the alarm the plan is drafted (needs Chat). `0`: no draft. |
| `alarm.open_page` | `true` | Open the morning page at the alarm. |
| `alarm.notes` | `true` | The wake-up call goes into the daily note. |
| `alarm.keep_awake` | `false` | Keep the computer awake until the alarm. |
| `availability.night` | `{"enabled": true, "from": "23:30", "to": "07:00", "alarm_only": false}` | The fixed night hours; `enabled` false: no night at all; `alarm_only` true: only bedtime to the alarm holds calls. |

**Limits and edge cases.**
- A skipped day can't be un-skipped; set that morning's alarm yourself ("wake me at 7 tomorrow").
- The plan needs the alarm set at least a few minutes ahead, Chat on, and the computer awake then.
- Every night at 21:00 Kurooto's health pass checks tonight's alarm is planned, on your call line, and that a phone
  is paired. If not, at once: "Your alarm at 07:00 might not ring: ... Set your phone's own alarm too." with a **Fix**
  button. See [Your computer](your-computer.md).

**What leaves your computer.** The alarm time goes to your call line. With Chat on, the AI reads your notes to draft
the plan, and the wake-up call's transcript to settle it.

**Turn it off.** Features → Morning alarm → Turn off. `alarm.keep_awake` off lets the computer sleep at once.

## Reminders with the lid shut

**What it does.** When your computer is asleep or off (a shut lid, a flat battery, `kurooto stop`), your Android
phone still gets your reminders at their time, and in the morning one line with the day's first class and what's due:
"First class 09:00: Linear Algebra. Due today: Problem set 3 (17:00)."

**Turn it on.** Dashboard → Features → Reminders with the lid shut. Needs Phone calls and the Kurooto app on an
Android phone (open it once after updating so it makes its key). An iPhone can't get these.

**How it works.**
- Whenever your reminders change, every 10 minutes, and as the computer goes to sleep (Linux and Windows say so),
  Kurooto hands your call line what's timed in the next day (up to 40 items), each sealed with a key only your phone
  has. The call line keeps the times, not the text.
- **Whichever side is awake says it, once.** Computer awake: Telegram as usual. Asleep: the call line sends it to your
  phone (through ntfy.sh, still sealed) as a normal notification, and the computer doesn't repeat it when it wakes.
  Telegram doesn't get reminders while the computer sleeps; they come when it wakes, unless your phone already had
  them.
- **The morning line** comes with your alarm if one is set that morning, else at `lidsafe.morning` (07:30), never
  later than 30 minutes before the first class. It only comes from the call line: when the computer is awake, the
  morning page and check-ins have it.
- **Computer on but can't reach the call line** when a reminder is due: it waits 2 minutes (30 just after waking), then
  says it anyway. If the call line sent it meanwhile, it comes twice.
- **macOS** doesn't tell programs it's about to sleep: a reminder set in the seconds before you shut a Mac's lid may
  wait until it wakes.
- A reminder the call line couldn't get to your phone (5 tries, a minute apart) comes on Telegram when the computer is
  back: "Your call line couldn't get this to your phone: ...".

**Settings that matter** (Dashboard → Settings → lidsafe):

| Setting | Default | Effect |
|---|---|---|
| `lidsafe.hours` | `24` | How far ahead the call line holds things (12 to 24). |
| `lidsafe.reminders` | `true` | Your reminders. |
| `lidsafe.today` | `true` | The morning line. |
| `lidsafe.morning` | `07:30` | When the morning line comes if no alarm is set. |

**Check it.** `kurooto doctor` or `/health`: "Reminders with the lid shut: your call line holds 5 for 1 phone(s)".
"No phone can open them yet": update the Android app and open it once.

**What leaves your computer.** The next day's reminder times and ids, and for each Android phone a copy sealed with
its key, go to your call line; your phone's public key too. Sent ones pass through ntfy.sh, still sealed.

**Turn it off.** Features → Reminders with the lid shut → Turn off. Your call line drops what it holds at once (or the
next time the computer reaches it).

## Calls from a terminal or script

`kurooto call "the backup finished"` rings your phone. It waits out your no-call rules (classes, `/hold`, focus, the
night) and calls when they end.

| Option | Does |
|---|---|
| `--at 17:30`, `--at "in 20 min"`, `--at "tomorrow 7:00"` | Calls later. |
| `--force` | Rings now despite no-call rules (never during another call). |
| `--alarm` | Rings as a wake-up alarm (no-call rules don't apply). |
| `--list` | The calls booked for later, with their keys. |
| `--cancel KEY` | Takes a booked call off (your call line forgets it too). |

It needs Kurooto running (`kurooto on`); otherwise it says so and exits with 2, like `kurooto send`, `notify` and
`ask-me` (1 means Kurooto refused the call, with the reason). More script commands are on
[Add-ons and scripts](add-ons.md).

## All call settings

Dashboard → Settings → calls. The ones you're likely to change:

| Setting | Default | Effect |
|---|---|---|
| `calls.realert_min` | `[3, 6]` | Minutes after the first ring that an unanswered call rings again. `[]`: once. |
| `calls.later_min` | `30` | **Later** on a ringing call calls back after this long. |
| `calls.ring_s` | `60` | How long a call rings before it counts as missed. |
| `calls.voice_mode` | `auto` | `auto`, `live` or `phone` (above). |
| `calls.voice_by_kind` | `{}` | Voice mode per kind of call. |
| `calls.voice` | empty | A Gemini Live voice name; empty is Google's default. |
| `calls.voice_by_model` | `{}` | A voice per Live model. |
| `calls.live_model` | `gemini-3.8-live` | The Live model calls try first. |
| `calls.live_models` | `["gemini-3.1-flash-live-preview", "gemini-2.5-flash-native-audio-latest"]` | Live models to try next. `[]` keeps to `live_model`. |
| `calls.turn_brain` | `gemini` | Who answers turn-by-turn calls on your computer: `gemini` (your key) or `local` (Local AI models). |
| `calls.text_model` | `gemini-flash-latest` | The Gemini model for turn-by-turn calls. |
| `calls.persona` | empty | Extra words on how to talk on calls. |
| `calls.review`, `review_effort`, `review_brain`, `lessons_max` | `true`, `high`, empty, `12` | The look back after every call (above). |
| `calls.notes_repo` | set by Notes sync | Lets calls read whole notes from GitHub while the computer is off. |
| `notify.app_kinds` | `["call", "question", "approval"]` | What goes to the phone app (see [Your phone](phone-app.md)). |
| `telegram.silent_kinds` | `["call"]` | Telegram's "Calling you" message is silent while a phone app is paired. |

## What leaves your computer

- Call audio goes between your phone and Google (Gemini Live, your key). On the free tier Google may use what you send
  to improve its products.
- Turn by turn: your speech goes to your phone's speech service unless it's recognised on the phone; each turn's text
  goes to Gemini (your key) or the model on your computer.
- Text on Telegram: the conversation goes through your Telegram bot and your AI, like your other messages.
- Your call line, on your Cloudflare account, keeps: your Gemini key; a short brief (what's due, today's classes and
  check-ins, open questions, the steps for check-in, wake-up and Sunday review calls, your notes' titles); the calls
  booked for the next day; questions and messages waiting for your phones; and, only if you approved it, your bot's
  token (for "Kurooto has been offline since ..." messages; see [Messages it sends](messages-it-sends.md)).
- Transcripts, lessons and everything else stay on your computer. The look back sends a call's transcript to your AI.
- Full list: [Privacy](privacy.md).

## Turn it off

- Features → Phone calls → Turn off. Morning alarm and Reminders with the lid shut need it, so turn those off first.
- Just the look back: `calls.review` = `false`.
- Just turn by turn: `calls.voice_mode` = `live` (failed calls go to Telegram).
- Keep calls from ringing for a while: `/hold 2h`, or `/focus`.
- The call line stays on your Cloudflare account until you delete it (Cloudflare dashboard → Workers & Pages → the
  `kurooto-…` worker → Settings → Delete), or until `kurooto uninstall --revoke` deletes it for you. See
  [Updates and backups](updates-and-backups.md).
