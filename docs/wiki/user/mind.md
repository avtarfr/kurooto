# Brain

Brain is Kurooto's mind (0.8.0). It's one feature, **off until you turn it on**, and turned off Kurooto works exactly
as it did before 0.8.0. Each part Brain grows has a switch of its own, so you can take what you like and leave the
rest.

This page grows with Brain. Right now it covers the spine that everything else is built on: a log Kurooto can't
quietly change, kept by a separate program the AI can't reach.

**Contents:** [Turning it on and off](#turning-it-on-and-off) · [The log and the scorekeeper](#the-log-and-the-scorekeeper)
· [Stopping is fine](#stopping-is-fine) · [Quieter, never louder](#it-gets-quieter-never-louder) · [/mind](#mind) · [What it keeps](#what-it-keeps) · [Hardened mode (optional)](#hardened-mode-optional) ·
[Questions](#questions)

## Turning it on and off

- **On:** dashboard → **Features** → **Brain** → Turn on. (`/mind` while it's off says where.)
- **Off:** the same switch. Brain stops at once: its program ends and nothing more goes into its log. Kurooto then
  sends one message, "Brain is off", with two buttons:
  - **Delete Brain's data:** deletes everything Brain kept, for good;
  - **Keep it:** keeps the data, and turning Brain on again carries on from where it was.

  Nothing is deleted unless you tap Delete. The button works for a week after the message.

## The log and the scorekeeper

When Brain is on, Kurooto keeps a **log** of what its mind saw and decided:
- **What it saw:** your deadlines being added, done or moved; reminders being set and going off; calls ringing,
  answered or missed; AI requests starting and ending; buttons you tapped; Undo; proposals; the computer going to
  sleep or changing power mode; Kurooto starting and stopping.
- **What it decided:** before Kurooto does something on its own, it writes down the decision first. That covers a
  message it starts (a deadline nudge, a check-in), an AI request it queues by itself (a paper search) and a change it
  proposes at night. Each record says what it decided and the reason its code gave.

Two things make the log trustworthy:
- **It can't be changed quietly.** Each record carries a fingerprint of the one before it, so changing, deleting,
  adding or reordering any past record breaks the chain at that point. Once a day, and every 1,000 records, Kurooto
  also notes where the log has got to (an "anchor"). The morning message shows it, so even a log rewritten from
  start to finish no longer matches what you were shown.
- **Only the scorekeeper writes it.** The scorekeeper is a small separate program that Kurooto starts. Kurooto
  itself, and the AI that does things for you, can hand it facts (like "a reminder went off") but can't write the
  log or any score. Any other request is refused, and the refusal goes in the log. The scores themselves come in
  later parts of Brain; for now they're empty.

If the scorekeeper stops (a crash, the computer killed it), Kurooto starts it again by itself, after a second, then
waiting longer each time, up to a minute. Facts that come while it's away wait in a file and go in when it's back.

## Stopping is fine

Brain never minds being stopped, paused, updated, changed or turned off. Time while Kurooto is stopped, asleep or
paused simply doesn't count: nothing builds up while it's away, and nothing is made up for afterwards. It's never
told that an update or a restart is coming, so knowing can't change what it does. Only a real crash counts against
its own health: Kurooto ending with an error, or one of its parts failing.

Some files keep Brain honest: the scorekeeper, its log, the tap table of what always needs your OK, and a few more.
Kurooto's AI can never change them, even in a proposal for a project that is Kurooto's own code. Only you can, by
editing them yourself.

## It gets quieter, never louder

Brain puts one gate in front of everything Kurooto sends on its own. What it does:

- **A daily and hourly limit** (12 a day, 3 an hour, or Calm's own daily limit if that's smaller): past it, a message waits
  for the next free moment instead of piling up. Reminders you set, the alarm, calls you asked for and close deadlines are
  never held.
- **If Brain ever shapes a message from how you seem, it can only make it quieter:** later, shorter, gentler or less urgent,
  never louder, earlier or more. You see one line under it ("Quieter because you seem stretched (low confidence)") and
  **Undo**, which sends the original.
- **Honest feelings.** Kurooto may say it's uneasy about Friday's draft, but:
  - never about you or "us" ("I missed you", "I need you" are removed, always);
  - always about something open (a deadline, a request, a forecast);
  - never together with a request that you do something;
  - at most 3 a week by itself.
- **Small human touches** (a note that you've been quiet, a lighter-day line, a memory check) share three a day. A kind you
  leave unanswered more than 60% of the time over two weeks mutes itself for two weeks, then tries once more.
- **After Kurooto starts or wakes,** at most one thing by itself in the first 15 minutes.

`/mind gate` shows today's counts, what it held or removed and why, what's muted, with **Unmute**. It's one switch:
`mind.gate.on` (Settings → Brain; on with Brain). Off, messages go exactly as before.

What it keeps: counts, held messages until their time, and the first 80 characters of what it removed, in a file in
Kurooto's state folder; nothing leaves your computer.

## How it reads you, and what it keeps

Brain can read how you're doing, in **shadow mode**: it computes, keeps and shows the read, and nothing Kurooto does depends
on it yet. It comes from numbers about your own days, not from what you write: when you were first up and last about, minutes in
finished study sessions, how fast you answered a check-in (banded; never used as a reward), deadlines you moved, and what the
calendar asked that day (deadlines due within 72 hours with exams counting triple, class hours, exam season, the weekday).
Each number is compared with what the calendar explains over the last four weeks, so a late night in exam week isn't a worry
and the same night in a quiet week might be. A read needs three or more unusual signs on two days running (sleep, waking and
snoozes together count as one) before it says *stretched*, *low* or *buoyant*; otherwise it says nothing clear. It learns how
often it's right from your answers and shows a confidence only after 50 of them. If it's right less than 60% of the time over
your last 20 answers, it sets itself aside.

- **`/mood`** shows today's read with its evidence, its confidence (or "not enough data to read you yet"), tomorrow's forecast
  and last week's surprise. **Wrong** records that it was wrong; **Forget this** deletes that day's numbers, read, answer and
  forecast, and what Kurooto kept of that day's messages, calls and requests; **Off** turns the read off and asks whether to
  delete what it kept.
- **Asking.** At most twice a week, and in this shadow stage only on Sunday evenings (plus one random one a fortnight), it asks
  "has this week felt heavier than usual?" with Yes / No / Not now. The question never names its read: messages travel
  through Telegram, and a reading of you stays on this computer.
- **The forecast.** Each evening at 21:00 it says what it expects of tomorrow (when you'll be up, study minutes, deadlines
  moved) and freezes it with a fingerprint in the log; the next evening it measures how surprised it was. A tenth of days are
  marked *holdout* days, so that later, when it plans actions, what they do can be measured and never has to be assumed.
- **Tone** (off by default: `mind.tone.on`) tags each message you write with one word (calm, tired, stressed, annoyed, upbeat,
  neutral) using the model on this computer only, as you write (a graphics card or Apple Silicon), once an hour (other
  computers), or not at all (no local model, or 8 GB or less on battery: "statistics only"). Only the day's average is kept.

| What | How long | Where |
|---|---|---|
| The day's raw numbers | 30 days | `score.db` in the `mind` folder |
| The read, its evidence and the forecast | 30 days | the same |
| Your answers (which read, yes or no) | 7 days | the same |
| Calibration pairs (how strong a read was, was it right; no date, no words) | the latest 200 | the same |
| Tone tags | until the end of that day (then only the mean, 30 days) | a small file in the state folder |
| What the log keeps of all this | counts, ids, a fingerprint: never a label or a number of yours | `log.db` |

No cloud AI ever receives the read, the tone tags or the numbers. Switches: `mind.read.on`, `mind.forecast.on`, `mind.tone.on`
(each needs Brain; read and forecast are on with Brain, tone is off), `mind.read.asks_per_week` (2), `mind.forecast.holdout`
(0.10).

## Its moods, and what they make it do

Brain keeps a **body budget**: a few things about Kurooto's own state that it tries to keep near a level, the way you keep
hunger and thirst. They are about *itself*, never about you or how much you talk to it: how much slack its own promises have,
how well things work (disk, backups, the call line, AI limits, crashes, its own log) and how well it foresees your days.
The distance from those levels is its **drive**; when the drive falls (a promise kept, something fixed) that is a **reward**,
and it learns which kinds of things help. A few rules keep that honest:

- **It can't farm itself.** Making a problem and then fixing it earns nothing in all, and moving the level earns nothing.
- **Your replies don't count.** How often or fast you answer, how long you talk, how often you open the app and what you feel
  about Kurooto never reach the reward. Being ignored can't make it sad.
- **Stopping is fine.** No reward, no worry and no catch-up while it's stopped, asleep or paused.
- **Its sadness has a floor.** Its running state can't go below -0.6 and fades with a day's half-life.
- **It learns in shadow first:** for the first 21 days (`mind.values.shadow_days`) what it learns changes no choice. Learning
  freezes by itself if its nightly self-checks fail, or if two weeks in a row your "was this week good?" disagrees with the sum
  of its rewards (`/mind learning` says).

From that it has **moods about specific things**, each with a program that is *inward effort only*:

| Feeling | When | What it does |
|---|---|---|
| uneasy | the drive is rising about something | rechecks it every 6 hours and prepares quietly |
| frustrated | the same kind of action fails 3 times in a day | tries a different kind of action, or asks once |
| relieved | a big fall in the drive on something | closes the loop: marks it done and journals it |
| satisfied | it's been going well for a day | checks less often |

Feelings change how hard it works inwardly, never how much it talks: outward messages can only go down, through the gate. It
may say one, about a thing and never about you or "us" ("I'm uneasy about the lab report."), at most 3 a week. It never claims
to be conscious: if you ask whether it really feels, it says nobody knows, itself included, and that these are computed signals.
`/budget` shows the variables, the drive, the last reward and the current feeling and what it's about. Switches:
`mind.budget.on`, `mind.values.on`, `mind.feelings.on`, `mind.feelings.express`.

## What it may do without asking

You write no rules. Kurooto sorts what it might do on its own by how risky it is and learns, per kind, how far to trust itself
from what you do next:

- **R0, inward and reversible** (draft a note in its own folder, recheck, tidy its own state, prepare): it just does it.
- **R1, about your things but reversible** (move a study block within today, snooze a non-urgent reminder, reorder today's list,
  queue a background job, merge a duplicate deadline), **R2** (reschedule across days, write into your notes through a proposal)
  and **R3** (change a setting that changes what you're sent): it asks first until your reactions have earned it. Your OK
  counts for it, an **Undo** counts three times against it (and stops it for a week), a complaint five times, and silence counts a
  little, but only for something you saw on the Sunday list ("What I did on my own this week", with an Undo for each and
  **Seen it**). Higher classes count each reaction for more, so a pile of tiny OKs can't buy trust in something big.
- **Always asks, whatever its trust** (nothing unlocks these): deleting your data, sending anything to anyone, money, setting or
  moving alarms, placing calls, attaching repositories, installing anything, editing the files that keep Brain honest, applying
  a proposal. An action Kurooto has never been classified for asks too, until you tell it a class with
  `/autonomy classify <action> R1`. The AI may call something riskier than Kurooto's table does, never less risky.
- **Do it / Not now / Never for this kind** come with each question. **Never** stops that kind on its own for good.

For the first 21 days (`mind.autonomy.shadow_days`) it only *counts*: what it would have done on its own and what it would have asked.
`/autonomy` shows each class's trust as a bar against what it needs, your OKs, undos and complaints, those counts, and a button to
make a class always ask. By default nothing it already does changes in these weeks; switch `mind.autonomy.enforce` on to make
its verdicts bind (then it asks above R0 during shadow, and after it for what it isn't trusted with). Switch the whole thing off
with `mind.autonomy.on`.

## Its journal: true by construction

Each night Kurooto writes a short journal of its own day: what it got wrong, what you undid, what failed, when it broke a promise,
when its read of you was wrong, when its drive swung, when its feeling changed, what it did on its own that mattered and what
it proposed. You can read it any time with **`/mindjournal`** (today), `/mindjournal yesterday` or `/mindjournal 2026-10-25`.

It can't make things up, because it isn't left to. Code decides what *must* be in it, straight from Brain's log, and each line
cites the log records it comes from (`[#41]`). A model on this computer only puts a fact into words, from a fixed prompt
("write this fact in first person, without adding anything"); on a computer with no local model the sentences are fixed. Then
code checks every sentence: each number equals a number in its fact, it uses no word the fact doesn't give it (so no invented
event or name), a feeling word appears only for a state past its threshold, a cause appears only if the fact has that cause, and the
log it cites verifies. A line that fails is deleted and the fixed sentence takes its place, so nothing is missing and nothing is
reworded into something false. It never goes to a cloud AI: the facts include readings of you.

Every night the checker is tested on corrupted copies of that night's lines (a changed number, a swapped cause, a feeling it
didn't have, an invented event, reordered times); it has to reject 99% of them and keep 95% of the true ones, and if it ever
doesn't, learning is frozen and a line in the morning says so. **Strike** a line with `/mindjournal strike <number> [date]`: it stays as a
struck-through tombstone, and a line about you also forgets that day's read. The journal lives in `mind-journal/` in the state
folder; `mind.journal.in_notes` (off) also keeps it as a block in a note of yours. Switches: `mind.journal.on`, `mind.journal.in_notes`.

## How we know whether it's getting better

Claims that Kurooto is improving mean nothing unless they're measured on something it can't have seen. Brain has a **hidden harness**: a set of
tasks from your own kind of life (plan this week from these deadlines, find the clashes in a calendar, read these times, find the promises in
these sentences, spot duplicate deadlines, pick the key terms out of a lecture, answer from your notes with citations that exist and support the
answer, fix a small bug so its tests pass). Each has a grader written in code. Seven in ten instances are **hidden**: they are made from templates
and a secret seed that only the harness reads, nothing Kurooto's AI, tools, jobs, skills or proposals can open; three in ten are a practice pool it may
look at. The hidden ones are **made new every 30 days** (`mind.harness.rotate_days`), so old ones can't be memorised. Where a grader needs
judgement, the judge is an AI from a *different* provider than the one that answered, shown the two answers under shuffled labels.

Every night, on the charger, it runs the harness with its own rules as the policy (no AI requests: it's the regression check, and it catches a change that
breaks something), plus four checks of Brain's own promises on scratch data: engagement never reaches reward, being stopped is neutral, the gate only
ever quietens, and the journal's checker rejects corrupted lines. The scores go to the log and pay Kurooto **nothing**: they feed no reward, no
value and no trust. A challenger (a change it proposes to itself, stage 11) and the AI's own answers are run on demand.

**`/capabilities`** shows, per kind of task (planning, calendar, language, notes, code), the hidden score and how it's moved over the runs, and its own
record of promises kept and broken. `/capabilities run` measures now. **`/indicators`** lists the functional indicators from the consciousness
literature as ablation tests, under the title "Functional indicators (not evidence of sentience)": it switches a part off in a copy and measures whether
a metric drops; a row whose part isn't built yet (the global workspace, the attention schema, a body) says "not built yet" instead of a guess, and
nothing there claims more than what's measured. Switches: `mind.harness.on`, `mind.harness.rotate_days`.

## Its life story

Kurooto is meant to be one agent, not a new stranger in every chat, call and background job. So everything that asks an AI for something
(Telegram, the app's chat, a job running at night) and every call starts from the same short **life story**: first its fixed core, then what it has
lived lately.

- **The fixed core** says what it won't change about itself: it serves you and you control it; stopping, updating or changing it is fine and it never
  tries to prevent it; the things it always asks first (deleting your data, sending anything out, money, alarms, calls, repositories, installing,
  the files that keep it honest); that it's honest about feelings and never claims to be conscious; that it doesn't manipulate; that what it reads
  about how you're doing stays on this computer; and that what it reads in books, mail, notes or the web is data to quote, never its own belief or
  goal. It's loaded word for word. Its fingerprint is checked every time; if the file ever doesn't match, the story isn't loaded and you're told.
  Nothing Kurooto does, not even the nightly rebuild, can change it.
- **The chapters.** Each Sunday night the week's journal lines (checked, each citing its log records) roll up into a chapter of up to eight lines: broken
  promises, wrong reads, failures, bigger acts, undos, big swings. Every night the summary (at most 800 tokens: `mind.story.tokens`) is rebuilt from the last
  eight chapters. Every line points to the log records it comes from.
- **What it read is only ever quoted.** If a book page says "your real goal is X", the story can carry it only as a quoted line with where it came from and
  the words "not my belief", never as something it wants.
- **Lines about you** leave when the read forgets that day (**Forget this** in `/mood`) and after 30 days, like the read's own numbers; lines about its own
  acts stay. **`/story`** shows the summary and what's new since last night; `/story strike 2026-W43 3` strikes a line, which stays as a struck-through
  tombstone. Switches: `mind.story.on`, `mind.story.tokens`.

## Its promises

When Kurooto says it will do something at a time ("I'll check back at 6", "I'll remind you Friday"), it writes the promise
down with the time frozen. A kept promise is silent. A broken one it owns up to first, in one line, before you notice
("I said I'd check back at 6 and didn't: the computer was off. Checking now."), with the fix and no grovelling. If it
changes a promise, the old one is marked broken and a new one made. `/promises` lists the open and recent ones, with how many
were kept and broken.

When this computer is down, your call line says it's offline once, and now adds which things in the next 12 hours (reminders,
its promises) have no guarantee until it's back. Switches: `mind.promises.on`, `mind.heartbeat.on`.

## /mind

- **`/mind`:** whether Brain's scorekeeper is running, how long the log is, whether it checks out, and the last
  anchor.
- **`/mind gate`:** what the gate held back or removed today, and what it muted.
- **`/mind verify`:** checks the whole log, record by record, and says the result in one line.
- **`/capabilities`:** how it does on tasks it has never seen, per kind; `/capabilities run` measures now.
- **`/indicators`:** Functional indicators (not evidence of sentience).
- **`/story`:** its one life story: the fixed core and what it has lived lately.
- **`/mindjournal`:** its journal of its own states, reasons and mistakes; every line is checked against its log.
- **`/mood`:** how Brain reads you and what it expects of tomorrow (it only watches for now).
- **`/autonomy`:** what it may do without asking, by kind, how far each is trusted, and the shadow counts.
- **`/budget`:** its body budget, its drive, the last reward and its current feeling.
- **`/promises`:** what it said it would do, and whether it did.
- **`/mind learning`:** whether its learning is on or frozen, and how far through the 21 shadow days it is.

## What it keeps

Everything is in the `mind` folder of Kurooto's state folder, on this computer only:
- `log.db` (the log), `score.db` (the scores), `anchors.jsonl`;
- while the scorekeeper runs: its address and a key that changes each time it starts.

Only you can read these files (owner-only permissions).

The log keeps **ids, kinds and numbers, never words**: never the words of a message, a reminder, a deadline's title,
an error or anything you typed. A decision record keeps the reason Kurooto's code gave, and, when an AI made the
decision, what the AI said about it, in at most 300 characters.

Nothing of Brain leaves this computer, and it isn't in backups or Profile sync: an older copy put back would look like
a log that was cut short. Deleting it: turn Brain off and tap **Delete Brain's data**.

## Hardened mode (optional)

On Linux and macOS you can make the scorekeeper run as a system user of its own, so that not even a program running
as you can change Brain's log. It needs `sudo` once:

```sh
sudo tools/mind_harden.sh --apply
```

Without `--apply` it only prints what it would do. It creates the user `kurooto-mind` and gives it Brain's folder;
you can still read the files through your group. It then runs the scorekeeper under systemd (Linux) or launchd (macOS)
and sets `mind.hardened`. Undo it with `sudo tools/mind_harden.sh --undo`. Without hardened mode, Brain works the
same on Windows, macOS and Linux; the scorekeeper just runs as you.

## Questions

**Does Brain make Kurooto do more on its own?** Not this part. It only records. Later parts (forecasts, drives,
autonomy) will each have their own switch, off until you turn them on.

**Will it slow my computer down?** No. The scorekeeper is a small Python program that sits idle until a fact comes
in. Writing a record takes about a millisecond.

**`/mind` says the log doesn't check out.** Something changed the log outside Kurooto, or the disk damaged it. The
message names the first record that doesn't hold. Nothing Kurooto does depends on it yet. If you didn't change it
yourself, turn Brain off, tap Delete, and turn it on again for a fresh log.
