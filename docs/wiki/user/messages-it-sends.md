# Messages Kurooto sends by itself

Most of what Kurooto sends is an answer to something you did. The rest comes **by itself**: a reminder, a check-in, a
digest, a warning. This page lists every kind, why it comes and how to get fewer of it. If a message surprised you,
tap its **Why?** button, or send `/why`.

- [Calm: Why?, Less of this and the daily limit](#calm-why-less-of-this-and-the-daily-limit)
- [Keep or drop: the features you don't use](#keep-or-drop-the-features-you-dont-use)
- [Every message that comes by itself](#every-message-that-comes-by-itself)
- [Going offline and back online](#going-offline-and-back-online)
- [Kurooto keeps itself working](#kurooto-keeps-itself-working)
- [The night, focus and urgent messages](#the-night-focus-and-urgent-messages)
- [Where messages show up](#where-messages-show-up)

## Calm: Why?, Less of this and the daily limit

**What it does.** On by default. Every message that comes by itself records why it came: which feature sent it, what
for, the setting that controls it, and what it was about (the deadline, the class, the project). Then:

- **Why?** (a button on Telegram) answers from that record, for example: "Why: Deadlines, a reminder before something
  on your deadline list is due. About: Report on groups. Setting: deadlines.ping_h = 24 (Settings → Deadlines)." It
  also says when it was sent, how many have come today, and whether it waited for the evening bundle and why. A message
  with no reason recorded came from an add-on or a script: "No reason recorded"; Kurooto never guesses. With Brain on
  (0.8.14), it also says what Brain's gate and the door did with it, what it expected (a reply, or that you'd act on it)
  and what came of it, and the phone app chat's copy gets a **Why this?** button that answers the same way
  ([Brain: one door](mind.md#one-door-at-a-natural-break-0814)). A message that kept losing at Brain's door for hours
  waits for the evening bundle, which says so. Since 0.8.17 the bundle comes one by one: a short header, then each
  message that waited, with its own buttons (`notify.calm.bundle_one` on: one message, as before). The phone app's
  chat shows six buttons under a message; a message with more goes on in a follow-up message ("More choices for the
  message above:") instead of losing them.
- **Less of this** offers up to three choices. Each changes **one** setting and is followed by an **Undo** button:
  - **Stop**: that kind stops. Where the feature has its own setting, that's what changes (practice offers:
    `quiz.offer_at` emptied; a check-in: its time cleared; after-class questions: After-class notes turned off).
    Otherwise the kind goes on Calm's own list, `notify.calm.stopped`.
  - **Fewer**: where it makes sense: the mail digest once a day instead of twice, the papers digest weekly, quiet
    projects asked about half as often, no after-class question for that one subject, at most one Classroom
    announcement a day (the rest wait for the evening).
  - **Another time**: that kind always waits for the evening bundle (`notify.calm.evening`).

  "Done: no more doubt lists." with **Undo** confirms it.

The phone app, the desktop and calls get the plain message, without these buttons.

**The daily limit.** At most **6 messages and 1 call a day** come by themselves (`notify.calm.messages`,
`notify.calm.calls`). Past that:

- **the first time a day the limit holds a message, you're told at once**, in one line on Telegram and in the phone
  app's chat: "That's today's 6 messages that came by themselves. The rest wait for the evening bundle at 20:00, which
  lists each one." It has three buttons:
  - **Send them as they come today**: the limit is off for the rest of today, and what it held so far comes now, in
    the order it came (with Why? and Less of this). Tomorrow the limit holds again.
  - **Raise to 12**: `notify.calm.messages` doubles (6 to 12), with **Undo**; what waited comes now, up to the new
    limit.
  - **Fine**: nothing changes; they come at 20:00.

  It comes at most once a day, and only for the daily limit: messages held for exam season, a quiet week, Another
  time, Fewer or the per-kind rules below don't bring it. With `notify.calm.messages` = 0 it doesn't come (you chose
  that). It isn't counted.
- messages wait for **one evening bundle** at 20:00 (`notify.calm.evening_at`): one Telegram message, "This evening's
  bundle: 4 messages that waited, held by the daily limit of 6" (or, when there were several reasons, "(3 held by the
  daily limit of 6; 1 because you asked for these in the evening)"), each item numbered, with each item's buttons
  numbered to match ("2: Nothing new"). Long bundles come in parts. Files that waited follow it.
- a question that waits is still open meanwhile (`/q`, and on your next call). If it's answered before 20:00 it isn't
  in the bundle. Replying to the bundle answers its question when it's the only one in it. The phone app gets the
  waiting questions one by one at bundle time.
- a **call** past the limit isn't placed: a check-in comes as a message instead; anything else waits in the bundle with
  a **Call now** link. A call that rings again (its repeat) counts once.
- after the bundle time, messages come as they are.

**Never held, never stopped, not counted:** the alarm (and the alarm to leave for an exam, and "tonight's alarm might
not ring"); approvals; your own reminders (reminders, calls you asked for, quiz times and study sessions you set,
calendar event reminders); a deadline less than 12 hours away (and its call); anything urgent (Kurooto can't work until
you act: a sign-in that ended, crashes); a newly paired device on your call line; the evening bundle itself. These
have no Less of this. Answers to what you asked or did (AI answers, `/sync`, a skill you ran, a button you tapped)
aren't counted at all.

**Update notices aren't counted either** ("Kurooto updated to 0.5.19."), and several in one day fold into one: on
Telegram the first one is changed in place to the newest, "Kurooto updated to 0.5.19 (and 2 earlier today).", so three
overnight updates leave one message. Where the first can't be changed (no Telegram, or it was deleted), the newest
comes as a new message with the same "(and 2 earlier today)". They still have Why? and Less of this.

**Classroom → notes sends one message per check**, once the AI has filed everything that check found, whichever
courses it came from: "Classroom: filed 9 new items into your notes:" and the items by title (the first eight, then
"and 1 more").

**Exam season.** With [Exam season](quiz-and-exams.md) turned on and its "Only deadlines, quizzes and the alarm by day"
part on, during the exam period only Deadlines, Quiz, the alarm and Exam season itself come during the day; everything
else that comes by itself waits for the evening bundle, even after 20:00 (then until the next one). The daily limit
still applies to what comes. Calls from other features are held the same way.

**Getting used to things (tuned while dreaming).** With [Dreaming](teaching-kurooto.md#dreaming) on, each night
Kurooto replays the messages it sent you by itself in the last 45 days under a few variants of when they come, and
scores each variant with what you actually did: answered ones that would still reach you in time count for it,
interruptions you ignored count against it, and holding back one you answered quickly counts heavily against it. If a
variant clearly beats things as they are (`dreaming.tune_margin`), it makes that **one** change and says so in the
morning message with **Undo**: "Learned while you slept: questions about quiet projects wait for your evening bundle
once 2 in a row go unanswered; over the last 14 days that would have saved 8 ignored pings and delayed none you
answered." At most one change a night. The changes it can make:

- **after N unanswered in a row** (`notify.calm.habituate`): that kind waits for the evening bundle once you've left
  the last N unanswered (3 hours or older), and comes as it happens again as soon as you answer one;
- **the evening bundle** for that kind (`notify.calm.evening`, the same as Another time);
- **only at the hours you answered it** (`notify.calm.windows`, e.g. `10:00-13:00`): at other times it waits.

It never touches what always comes (the alarm, your reminders and calls, approvals, deadlines under 12 hours), kinds
that can't wait for the evening (practice offers, check-ins, doubt lists), the kinds in `dreaming.never_tune`
(deadline reminders and calls among them), or anything you set yourself (stopped, fewer, the evening list, the limit,
the night). It only moves messages that had something to answer, and it can't judge what it never sent. After an Undo
it leaves that kind alone for 30 days. `/dream policy` shows the rules as they are and the last nights' decisions;
`dreaming.tune_messages` = false turns it off. The same night pass also tunes the effort your requests get, which AI
goes first and Start-by's sizes ([Teaching Kurooto](teaching-kurooto.md)); all of them together still make at most one
change a night.

**Once a month**, Kurooto looks at the kind of question you answer least. If 8 or more came in 30 days and you answered
a fifth of them or fewer: "In the last 30 days you answered 1 of 19 after-class questions. Turn them off? (Turns off
After-class notes; Undo puts it back.)" with **Apply** / **No**. Only for questions you're meant to answer (marked
"monthly" in the table below), never for reminders. **No** keeps that kind out of it for 90 days. It needs a month of
records first.

**From Telegram:**

| Command | Does |
|---|---|
| `/calm` | today's count ("2 of 6 messages and 0 of 1 calls", or "the limit is off today" after Send them as they come today), how many wait for the bundle and how many of those the daily limit held, what you stopped or moved to the evening (and what waits after some go unanswered, or outside its hours), with **Start ... again** buttons |
| `/calm 8` | allow 8 messages a day |
| `/calm calls 2` | allow 2 calls a day |
| `/calm evening 21:00` | move the evening bundle |
| `/calm off`, `/calm on` | turn Calm off (everything comes as it happens, no Why? buttons) or back on |
| `/why` | why the last message that came by itself came, with Less of this |
| `/dream policy` | when messages that come by themselves reach you, the effort, AI order and Start-by sizes it tunes, and what Dreaming changed (with the replay's scores) |

**Settings** (Dashboard → Settings → notify → calm):

| Setting | Default | Effect |
|---|---|---|
| `notify.calm.on` | `true` | `false` restores the old behaviour exactly: nothing waits, no Why? buttons, nothing recorded |
| `notify.calm.messages` | `6` | messages a day that come by themselves; more wait for the bundle |
| `notify.calm.calls` | `1` | calls a day that come by themselves |
| `notify.calm.evening_at` | `20:00` | the evening bundle |
| `notify.calm.monthly` | `true` | the monthly suggestion |
| `notify.calm.stopped` | `[]` | kinds you stopped (filled by Less of this) |
| `notify.calm.evening` | `[]` | kinds that always wait for the bundle |
| `notify.calm.fewer` | `{}` | kinds limited to a number a day |
| `notify.calm.habituate` | `{}` | kind → after this many unanswered in a row, they wait for the bundle until you answer one |
| `notify.calm.windows` | `{}` | kind → `"10:00-13:00"`: outside those hours they wait for the bundle |

**What leaves your computer:** nothing. The records stay in `calm.db` in Kurooto's state folder for 45 days: when,
the reason, the setting, what it was about, the first 300 characters (forgotten after `privacy.keep_days` when you set it:
[privacy.md](privacy.md#how-long-its-kept)), and whether you tapped or answered it; a waiting message in full until its
evening.

**Turn it off / undo:** every Less-of-this choice and every Apply has an Undo button that puts that one setting back
(a feature it turned off goes back on). `/calm` lists what's stopped, with a button to start each again. `/calm off`
turns Calm off; anything already waiting still comes at the evening bundle.

## Keep or drop: the features you don't use

**What it does.** Kurooto counts, on this computer, what you actually use of each feature: requests it answered at
once ("remind me at 9 to call mum"), its commands, taps on its messages' buttons, its tools used on a call, and your
replies to its messages. On **day 10** (counted from Kurooto's first start, or from the update that brought this), once
setup is done, one message lists every feature that's on with its use in those 10 days and the messages it sent by
itself:

> Ten days in: what you used of each feature that's on, and what it sent by itself.
> - Weekly summary: not used; 1 message by itself
> - Reminders: used 12 times (9 requests, 3 commands)

Under it, per feature (the least used first): **Keep**, **Quiet** and **Off**.

- **Keep:** nothing changes, and it isn't asked about again for 90 days.
- **Quiet:** the feature keeps working (its commands, requests and scheduled work), but what it sends by itself stops:
  its kinds of message go on Calm's stopped list. Your own reminders, the alarm and approvals still come. Calls it
  places follow their own settings.
- **Off:** the feature is turned off, as in Features (its data stays).

Quiet and Off each come with an **Undo** button. **Then monthly:** a feature that's on, hasn't been used for 60 days
and still runs something on a schedule gets the same question. Nothing is turned down without a tap. Telegram, which
these come on, is never asked about.

| Command | Does |
|---|---|
| `/keep` | each feature that's on, what you used of it in the last 30 days, and what it sent by itself |
| `/keep 60` | the same for 60 days (up to 90) |
| `/keep weekly` | one feature, with its Keep / Quiet / Off buttons |

**Settings:** `keep.ask` (`true`): `false` stops the questions; `/keep` still shows the counts.

**What leaves your computer:** nothing. The counts are in `keep.json` in Kurooto's state folder: per feature and day,
only numbers (kept 90 days), and when each feature was last used.

**Turn it off / undo:** the Undo button under Quiet or Off puts it back; `keep.ask` = `false`, or Less of this → Stop
on the question, stops the questions.

## Every message that comes by itself

Columns: **Setting** is what Why? names and what Stop changes. **Always** means it ignores the daily limit and has no
Less of this. **Stop** says what Stop does ("list" = it goes on Calm's own stopped list; "feature off" = the feature is
turned off). **Fewer** and **Later** (Another time) are offered where marked. **Monthly** marks questions the monthly
suggestion may offer to turn off.

### Always come

| Message | Feature | Setting | Why it always comes |
|---|---|---|---|
| a reminder you set | Reminders | | you set it |
| a call you asked for | Phone calls | | you asked for it |
| the end of a study session you started with a length | Study tracker | | you set it |
| a quiz time you set ("quiz me at 9") | Quiz | | you set it |
| a reminder before a calendar event | Calendar | `calendar.remind_min` | you set it |
| a reminder you asked for about a project ("Remind me tomorrow") | Research | | you asked |
| a reminder your call line couldn't get to your phone while the computer slept | Reminders with the lid shut | | your own reminder |
| the part of a deadline's work you moved to today (you tapped **Do that** on a reshaped plan) | Start-by dates | | you agreed to it |
| your wake-up alarm | Morning alarm | | alarm |
| the alarm to leave for an exam | Exam season | `exam_season.leave_alarm` | alarm |
| the nightly alarm check during exams | Exam season | `exam_season.alarm_check` | alarm |
| "Your alarm at 07:00 might not ring ... Set your phone's own alarm too." | Kurooto keeps itself working | | alarm |
| a device was paired with your call line | Phone calls | | security: if it wasn't you, `/unpair` it |
| a reply draft waiting for Send, Edit or Discard | Email reply drafts | | approval |
| whether agy may use Kurooto's tools | the AI | | approval |
| whether your call line may say when this computer is offline (keep your bot's token) | Online and offline messages | | approval |
| the evening bundle | Calm | `notify.calm.evening_at` | it is the bundle |
| "That's today's 6 messages that came by themselves" (once a day, when the limit starts holding) | Calm | `notify.calm.messages` | it tells you about the limit |

### Problems Kurooto needs you for

No Stop; only Another time. When sent as urgent they always come.

| Message | Setting |
|---|---|
| the AI you picked hit a limit or was signed out | `brain.fallback` |
| a Google sign-in ended, so what uses it is paused | |
| Kurooto kept crashing | |
| a call that couldn't ring because your call line wasn't connected | |
| a new version to install (only when `updates.mode` is `ask`: Update / Later / Skip) | `updates.mode` |

### Deadlines, study and exams

| Message | Feature | Setting | Stop | Fewer | Later | Monthly |
|---|---|---|---|---|---|---|
| a reminder a day before something on your deadline list is due (Done / Not mine / Snooze 3 h) | Deadlines | `deadlines.ping_h` | no more day-ahead reminders; the last few hours' ones still come | | yes | |
| deadlines and exams in a class calendar you subscribed to, with Add buttons | Calendar | `calendar.shared_offer` | they only show as events, without Add buttons | | yes | |
| the call a few hours before a deadline | Deadlines | `deadlines.call` | no deadline calls; a message instead | | yes | |
| "Overdue?" after a deadline passed (Done / New date / Drop) | Deadlines | `deadlines.overdue_check` | no more "Overdue?" | | yes | yes |
| exam mode starting for a quiz or exam | Deadlines | `deadlines.exam_mode_days` | list | | yes | |
| "Time to start: ..." (a start-by date, an estimate) | Start-by dates | `startby.tell` | no more (`/startby` still shows them) | | yes | |
| a reshaped plan instead of the same reminder again ("1 h now, 1 h tomorrow?" with Do that / Not today) | Start-by dates | `startby.negotiate` | no more reshaped plans; reminders come as before | | yes | |
| how long a subject's exams take to prepare for | Start-by dates | `startby.ask_exams` | no more of these | | yes | yes |
| the evening before a quiz or exam, an offer to practise | Quiz | `quiz.offer_at` | no more offers (`/quiz` still works) | | | yes |
| exam mode's daily practice check-in | Quiz | `quiz.exam_daily` | no daily practice | | | yes |
| a quiz by call | Quiz | `quiz.by_call` | quizzes come as messages | | yes | |
| a link recall card: how two of your concepts relate | Quiz | `quiz.links` | no more cards by themselves (`/card` still gives one) | one a day | yes | yes |
| "A revision pack for it tonight?" before an exam | Skills | `skills.auto_pack` | no more offers | | yes | yes |
| after a class, what was worth keeping | After-class notes | `capture.skip_subjects` | feature off | none after that subject | yes | yes |
| your open doubts before a subject's class | Doubt queue | `doubts.before_min` | list | | | |
| exam season starting | Exam season | | list | | yes | |
| the evening before an exam: where, seat, calculator, ID | Exam season | `exam_season.eve` | no more exam-eve questions | | | yes |
| a two-minute debrief after an exam | Exam season | `exam_season.debrief` | no more debriefs | | yes | yes |
| the evening question: did you cover today's revision topics? | Exam season | `exam_season.revision_ask` | no more revision questions | | | yes |

### Your day

| Message | Feature | Setting | Stop | Fewer | Later | Monthly |
|---|---|---|---|---|---|---|
| a check-in (evening, night, midday) | Check-ins | `checkins.times` | that check-in is off | | | yes |
| a check-in by call | Check-ins | `checkins.by_call` | check-ins come as messages | | yes | |
| a check-in call that moved to another time | Check-ins | `checkins.by_call` | list | | yes | |
| the weekly summary (Sunday 19:00) | Weekly summary | `weekly.when` | feature off | | yes | |
| the Sunday review call | Weekly summary | `weekly.call` | no Sunday call | | yes | |
| a first-week quest | First-week quests | `quests.days` | feature off | | yes | yes |
| night hours (and mornings) moved to when you're usually quiet (Undo) | Your rhythm | `availability.learn_night` | the night hours stay where they are | | yes | |
| "A lighter day after your exam ..." (Not today; Dreaming's morning message carries it when that's on) | Your rhythm | `notify.calm.lighter_after` | no more lighter days | | | |
| "Haven't heard from you in two days. All good? Nothing's urgent." (I'm fine / Busy, quiet for a week) | Your rhythm | `availability.absence_days` | no more of these | | | |
| "You usually wake around 16:30; set an alarm?" (Set / Not tonight) | Morning alarm | `alarm.suggest` | no more alarm suggestions | | | |
| "You're up already: skip the 07:00 alarm?" (Skip it / Keep it) | Morning alarm | `alarm.skip_if_up` | no more of these | | | |
| "You've told me to stop 3 times lately when I spoke up by myself (...). Stop these?" (Stop these / Keep them) | Calm | `notify.calm.voice_stops` | no more of these offers | | | |
| "It's 02:00 and your alarm is at 07:00: a short night ... Ring at 09:30 instead?" (Ring at / Keep it) | Morning alarm | `alarm.sleep_aware` | no more of these | | | |

### Google

| Message | Feature | Setting | Stop | Fewer | Later |
|---|---|---|---|---|---|
| a new announcement in a Classroom course | Google | `google.classroom` | list | one a day | yes |
| a Google feature paused until you set it up again | Google | | list | | yes |
| Classroom posts filed into your notes (one message per check) | Classroom → notes | `classroom_notes.at` | list | one a day | yes |
| Classroom posts the AI couldn't file (after three failures) | Classroom → notes | | list | | yes |
| your mail digest (08:00 and 18:00) | Mail digest | `mail_digest.at` | feature off | once a day | yes |
| what the mail digest may read (until you choose) | Mail digest | `mail_digest.read` | list | | yes |
| a mail digest that didn't come together | Mail digest | | list | | yes |
| the digest couldn't be emailed to you | Mail digest by email | | list | | yes |
| mail you sent in (+kurooto or your Email in label), filed into your notes, its dates with Add buttons | Mail digest (Email in) | `mail_digest.mail_in` | Email in off | | yes |

### Notes, books and research

| Message | Feature | Setting | Stop | Fewer | Later | Monthly |
|---|---|---|---|---|---|---|
| the new-papers digest | Research | `research.papers` | list | weekly | yes | |
| a question about a project with no commits for a while | Research | `research.idle_days` | no more | half as often | yes | yes |
| the LaTeX tracker's morning line: a build that broke, or words written | Research add-on | `research_addon.latex` | the LaTeX tracker off | | yes | |
| "Waiting for your OK": changes the AI proposed during the night, with Apply / Change / Discard (only with Dreaming off; with it on they're in its morning message) | Kurooto itself ([proposals](proposals.md)) | `proposals.morning` | | | yes | |
| a suggestion from the nightly look back | Nightly look back | `retro.when` | feature off | weekly | yes | yes |
| a routine the look back saw in your records (Add / No) | Nightly look back | `retro.routines` | no more | | yes | yes |
| a data fix the look back was sure of (two copies of one deadline), with Undo | Nightly look back | `retro.fixes` | no more | | yes | |
| a skill learned or improved from a request that took many steps | Learns from its own work | `learning.skills` | no more learned skills | one a day | yes | |
| a lesson a skill took from your correction | Learns from its own work | `learning.corrections` | no more lessons | | yes | |
| facts from your chats and calls kept in your how-to-help-me note | Learns from its own work | `learning.remember` | nothing kept by itself | | yes | |
| "Still true?" about a line in your how-to-help-me note that hasn't come up in a while (at most two a week) | Remember | `remember.recheck_days` | no more (0) | | yes | yes |
| the look back at what you typed that I didn't understand | Wrong button and test cases | `cases.review_days` | list | half as often | yes | |
| a PDF of handwriting waiting to be written out at night | Handwritten notes | | list | | yes | |
| handwritten pages written out into notes | Handwritten notes | | list | one a day | yes | |
| a handwritten file that couldn't be written out | Handwritten notes | | list | | yes | |
| handwritten notes linked to their lecture, course page and concepts | Handwritten notes | | list | one a day | yes | |
| a book that was read | Books and PDFs | `books.at` | list | | yes | |
| what the concept graph did overnight | Concept graph | `integrate.at` | list | | yes | |
| concept notes that look like one concept, up to three pairs (Merge / Keep both / Add alias, each with Undo) | Concept graph | `integrate.duplicates` | no more | | yes | |
| what Kurooto did while you slept, the loose ends, a topic you keep asking about with no note, a line from the past, and what's worth a look in what it remembers (Make a stub / Not interested, Open it / Less of this, Keep A / Keep B / Both true) | Dreaming | `dreaming.when` | list | | yes | |
| the notes brain's nightly upkeep didn't finish | Notes brain | `gbrain.upkeep` | list | | yes | |
| the notes brain's weekly checkup | Notes brain | `gbrain.checkup` | no checkup | | yes | |
| the notes brain's weekly one-line checkup | Notes brain | `gbrain.checkup_line` | no checkup line | | yes | |
| notes that changed in two places at once | Notes sync | | list | | yes | |
| Notes sync didn't work | Notes sync | | list | | yes | |
| Profile sync didn't work | Profile sync | | list | | yes | |
| a backup didn't work | Backups | | list | | yes | |
| the Space keeper cleaned off old files (only when it freed 50 MB or more) | Space keeper | `space.when` | list | | yes | |

### Kurooto itself

| Message | Setting | Stop | Later |
|---|---|---|---|
| something stopped working that could make you miss a deadline or exam in the next 48 hours (with Fix) | `health.on` | list | yes |
| things that stopped working and need a look (with the weekly summary, or Sundays) | `health.on` | list | yes |
| an update that couldn't be prepared | `updates.mode` | list | yes |
| Kurooto updated itself (not counted; several a day fold into one) | `updates.mode` | list | yes |
| an update that was undone because it kept crashing | `updates.mode` | list | yes |
| what's new after an update | | list | yes |
| once per version: a newer official add-on you have came with Kurooto (Look shows what changes; nothing updates without your yes) | `addons.official_updates` | no more of these (Update still shows on the dashboard and under /addons) | yes |
| your call line couldn't be updated | `updates.mode` | list | yes |
| a call your call line placed while this computer was off | | list | yes |
| a call that waits for a better time ("Held a call until 18:02 (class: Linear Algebra)") | | list | yes |
| what Kurooto fixed and learned looking back at a call | `calls.review` | list | yes |
| a phrasing learned because you picked the same one of two readings twice (with Undo) | `cases.learn` | list | yes |
| the monthly look at what you rarely answer | `notify.calm.monthly` | no more monthly suggestions | |
| day 10, then monthly: what you use of each feature, with Keep / Quiet / Off | `keep.ask` | no more of these questions | yes |
| after two weeks, once: the offline helper, when your free AI limit ran short or the internet often dropped (Install / Not now) | `local_helper.offer` | no more offers of the offline helper | yes |

Also by itself, but not counted as above:

- **"I'm Nova now."** after you rename the assistant (once).
- **Going offline / back online** (next section).
- Messages from your own scripts and add-ons (`kurooto notify`): "No reason recorded", never limited.

## Going offline and back online

**What it does.** Kurooto tells you on Telegram when it goes away and when it's back. On by default; nothing ever rings
for this.

- **A clean stop** (`kurooto stop` or `off`, the dashboard, signing out, shutting down): just before it goes, "Kurooto
  is going offline (shutting down): calls and reminders will wait until it's back". With Phone calls set up: "reminders
  will wait until it's back; your call line still places scheduled calls". It never holds up a shutdown by more than a
  few seconds. An update's restart says nothing.
- **Sleep, a crash, a lost network or a power cut:** the computer can't speak then. With Phone calls set up, your call
  line notices the link gone for 10 minutes and says it: "Kurooto has been offline since 22:10 (asleep, off or without
  internet): ..." on the phone app, and on Telegram if you allowed it (below). **Without Phone calls there's no message
  for these**, only the "back" one afterwards.
- **Back:** when Kurooto starts, when the computer wakes, and when the network works again: "Kurooto is back online
  (offline since 22:10, 7 h)" or "Back online: the network was down from 14:02 to 14:31 (29 min)", with what it caught
  up on (reminders that went out late, calls your call line placed meanwhile).
- **The network:** when Telegram or the call line can't be reached several times in a row, the network counts as down
  from the first failure. Messages meanwhile are kept and follow the "back online" message, in order, each marked
  "Delayed, from 14:05".

**Not every blip.** Nothing for less than 10 minutes away (except right after a goodbye). Several sleeps or drops close
together give one message, once the computer has been up for a minute. At night (your night hours, or bedtime to the
alarm) and in focus time it waits for the morning; if nothing told you Kurooto had gone and it's back before then,
nothing is said.

**Telegram from your call line.** For the line to tell you on Telegram while your computer can't, it needs your bot's
token. Kurooto asks once (**Approve** / **Deny**). Approve: the token and your chat id go to your call line on your own
Cloudflare account. Deny: only the phone app hears from the line (add `"app"` to `notify.presence.channels`).

| Setting (Settings → notify → presence) | Default | Effect |
|---|---|---|
| `notify.presence.on` | `true` | the offline/online messages |
| `notify.presence.after_min` | `10` | how long away before it counts (at least 1) |
| `notify.presence.channels` | `["telegram"]` | add `"app"` for the phone app |
| `notify.presence.line` | `true` | your call line speaks while the computer can't |
| `notify.presence.line_telegram` | `null` (ask once) | may the call line keep your bot's token; `false` deletes it there at the next sync (within 5 minutes) |

"Back online" every morning because the laptop sleeps at night? Raise `after_min` past your night, or turn it off.

## Kurooto keeps itself working

**What it does.** Every feature that's on has one health check, and Kurooto runs all of them once a day (21:00, before
bedtime, so tonight's alarm is checked in time). It stays quiet unless something is wrong.

**What's checked** (only features that are on). Only hours the computer was awake and Kurooto wasn't paused count, and
for work that waits for the charger, battery time doesn't count either: a shut lid never makes a sync "late".

| Check | A problem when |
|---|---|
| Telegram | the bot doesn't answer (a revoked token), or Kurooto stopped reading your messages |
| Google | a Google account in use isn't signed in, or its sign-in ends within 8 days (an app still in Testing ends every 7); Classroom not synced in 26 hours |
| Notes sync | the GitHub token fails or expires within 10 days; no sync in 24 hours |
| Calendar | no refresh in 12 hours |
| Phone calls | this computer isn't linked to your call line, the line doesn't answer, or the Cloudflare login it needs for updates is missing |
| Morning alarm | tonight's alarm isn't planned, your call line doesn't have it, or no phone is paired to ring |
| Backups, Profile sync, Notes brain | no good run in 72, 72 and 24 hours |
| Kurooto | messages stuck in its own queues (focus time that's over, a network that's back) |

**When you hear about it:**

- tonight's alarm might not ring: at once ("Set your phone's own alarm too");
- your Telegram bot stopped answering: at once, on the desktop and the phone app (Telegram can't carry it);
- a problem that could make you miss a deadline or exam in the next 48 hours (Classroom, Calendar, the call line): one
  message now, with a **Fix** button when there's one;
- anything else waits for the weekly summary ("Needs a look: ..."); with the weekly summary off, one message on
  Sundays.

Each problem is told once; if it's fixed and breaks again, you hear again.

**Fixes.** Before telling you, Kurooto tries a fix that's safe to run unasked, then looks again ten minutes later.
There are five, all limited to Kurooto's own state, never your notes:

| Fix | Does |
|---|---|
| **Sync now** | runs that feature's sync once (only when you tap it) |
| **Put its timers back** | a feature whose timers went missing gets them back; work held for a pause that's over runs |
| **Reconnect** | restarts the link to your call line, or Telegram's reading of your messages |
| **Set the alarm again** | plans your daily alarm now and sends it to your call line |
| **Send them now** | sends messages stuck in Kurooto's queues |

A sign-in that ended has no fix Kurooto can do; the message says what to do. After you tap **Fix**, you hear ten
minutes later whether it worked.

**Where to look:** `/health` (what's wrong, with Fix buttons; "Everything Kurooto checks is working (12 checks)" when
all is well); `/health now` also asks online services; the dashboard's "needs a look" badge and the Features tab;
`kurooto doctor` (`kurooto doctor --fix <id>` runs a fix); the weekly summary.

| Setting (Settings → Health checks) | Default | Effect |
|---|---|---|
| `health.on` | `true` | the daily pass and its messages (`/health`, the dashboard and doctor check either way) |
| `health.when` | `daily 21:00` | when the daily pass runs |
| `health.auto_fix` | `true` | try the safe fixes before telling you; `false` leaves every fix to your tap |

**What leaves your computer:** nothing new. The checks ask services Kurooto already uses: Telegram whether your bot
answers, GitHub whether your notes token works, your call line whether it's up.

## Lighter days and when you've gone quiet

**Lighter days** (`notify.calm.lighter_after`, on). The day after an exam (a quiz or exam on your deadline list whose
time passed the day before) or a heavy day (8 hours or more on the Study tracker), Kurooto goes easier: half the daily
limit of messages that come by themselves (3 instead of 6; the rest wait for the evening bundle), and your first
check-in an hour later. The morning message says so in one line ("A lighter day after your exam (Linear Algebra
midsem): fewer messages from me and the first check-in an hour later."), with **Not today**, which puts the day back
as usual. Without Dreaming, the line comes on its own once your night hours are over.

**When you've gone quiet** (`availability.absence_days`, 2; `0` turns it off). If nothing came from you for two days
(no message, no button, no answered call) while Kurooto kept running, one message: "Haven't heard from you in two days.
All good? Nothing's urgent.", with **I'm fine** and **Busy, quiet for a week**. It's never repeated, never followed up
and never a call: the next one can only come after you've been back. It waits out the night, focus, `/hold`, `/pause`
and a quiet week. **Busy, quiet for a week**: no calls for a week (like `/hold`; `/calls` lifts it), and whatever comes
by itself waits for one message each evening until then; the alarm, approvals and your own reminders still come.
**Undo** under the reply ends it early.

## The night, focus and urgent messages

| | Calls | Messages |
|---|---|---|
| **Night** (23:30 to 07:00, `availability.night`, or your learned quiet hours; or bedtime to your alarm) | held until it ends, except the alarm | still arrive (mute the chat in Telegram if you like); the "back online" message waits for the morning |
| **Focus** (`/focus 2h`, a `#focus` calendar event) | held | wait until focus ends, then come together; approvals, calls and urgent messages still come |
| **`/hold`**, a class, a calendar event | held ("Held a call until 18:02 (class: ...)") and placed by itself when it ends | not affected |
| **Paused** (`/pause`) | your call line still places scheduled calls (the alarm rings) | reminders and other messages wait until you resume |
| **On a call** | nothing else rings; wake-up calls still do | not affected |
| **Kurooto asleep** (with [Brain](mind.md#kurooto-sleeps), 0.8.14: your night, following your bedtime, alarm and phone) | as the night | what it starts by itself waits for the morning; reminders and calls you set, close deadlines, approvals and answers still come |

See [calls.md](calls.md) for the night, bedtime and no-call rules, and
[talking-to-kurooto.md](talking-to-kurooto.md#status-pause-hold-and-focus) for pause, hold and focus.

## Where messages show up

Every message goes to Telegram. Some also go elsewhere:

| Setting | Default | Effect |
|---|---|---|
| `notify.app_kinds` | `["call", "question", "approval"]` | what also reaches your paired phone app. Add `"reminder"`, `"deadline"`, `"result"` or `"info"`; remove `"question"` and `"approval"` to keep them on Telegram only |
| `notify.desktop` | `true` | pop-up notifications on this computer |
| `notify.desktop_kinds` | `["call", "question", "approval", "deadline", "update"]` | which kinds pop up on this computer (anything pops up there when no other channel took it) |
| `telegram.silent_kinds` | `["call"]` | kinds sent to Telegram without a sound (while the phone app is paired, since it rings itself) |

When you answer a question or tap a button somewhere, the copies elsewhere (the phone app's notification) are taken
down.
