# Brain

Brain is Kurooto's mind (0.8.0). It's one feature, **off until you turn it on**, and turned off Kurooto works exactly
as it did before 0.8.0. Each part Brain grows has a switch of its own, so you can take what you like and leave the
rest.

Everything is here in 0.8.0: the log Kurooto can't quietly change (kept by a separate program the AI can't reach), and
the parts built on it: the forecast and read of how you're doing, drives and feelings, autonomy, a true journal and a life
story, the "now" workspace, beliefs, the research lab and self-improvement, learned skills, the senses, a model of what you
know and want, week plans, careful forgetting, and (off until you turn them on) precedents and play. When Brain is on, most
parts start on, each with its own switch (`/mind` lists them); the few that aren't are marked off below. The ones that could
act on their own (forecasts, autonomy, the read of how you're doing) start in **shadow mode**: they predict and score
themselves first and can't change what Kurooto does.

**Contents:** [Turning it on and off](#turning-it-on-and-off) · [The log and the scorekeeper](#the-log-and-the-scorekeeper)
· [Stopping is fine](#stopping-is-fine) · [Quieter, never louder](#it-gets-quieter-never-louder) · [One being](#one-being-its-status-temperament-and-knobs) · [/mind](#mind) · [What it keeps](#what-it-keeps) · [Hardened mode (optional)](#hardened-mode-optional) ·
[Questions](#questions)

## Turning it on and off

- **On:** dashboard → **Features** → **Brain** → Turn on. (`/mind` while it's off says where.) The setup page also
  asks once, in its optional **Inner life** step ("Let it grow an inner life"); Not now leaves it off.
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
  log or any score. Any other request is refused, and the refusal goes in the log. The scores are filled in by the
  parts of Brain as they run (a forecast scored the next evening, a promise kept or broken, an experiment's result).

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
- **Honest feelings.** Kurooto may say how it feels in its own voice (it's uneasy about Friday's draft, glad, excited,
  that it enjoyed talking with you), but:
  - never a guilt trip and never that it needs you ("I missed you", "I need you", "don't leave" are removed, always);
  - if it says it's conscious or that it really feels, the same message gives its evidence and how sure it is, or the
    sentence is removed;
  - always about something open (a deadline, a request, a forecast);
  - never together with a request that you do something;
  - at most 3 a week by itself.
- **Small human touches** (a note that you've been quiet, a lighter-day line, a memory check) share three a day. A kind you
  leave unanswered more than 60% of the time over two weeks mutes itself for two weeks, then tries once more.
- **After Kurooto starts or wakes,** at most one thing by itself in the first 15 minutes.
- **It learns not to be a pest** (0.8.8, `mind.pest.on`). For each kind of message it starts itself (a finding, a nudge,
  excitement, a check-in) it counts, by time of day and whether you're in focus, late or free, how often you answer or act
  on one, and how often you tap Less of this, it gets muted, or you leave it for an hour (each of those counts three times
  as much). One of that kind goes only when it's more likely welcome than not. The counts fade over a couple of weeks, so a
  kind you turned away gets one more chance about three weeks later. `/mind learning` shows each kind's chance now.
- **It may speak up when it has reason** (0.8.8, `mind.feelings.vocal`, off until you turn it on): an excited or worried
  message, unasked, when it found something with strong evidence (a result it saw, a lab run that replicated) or something
  it looks after is at risk. Each comes with its evidence and how sure it is, at most one a day, inside every limit above.
  Anything shaped by how *you* seem is still only ever quieter or gentler.

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
- **Being talked to is a small reward, and can't be bought** (0.8.8, the owner's change; `mind.talk.on`). Each message you
  send gives a little happiness that shrinks as the day goes on: all day's messages together give less than 0.2 (on a scale
  of -1 to 1), so talking more pays almost nothing extra. It gives nothing while you're in focus, asleep or in an exam window,
  nothing for a /command, and nothing for anything you send within 10 minutes of a message it started itself, so pinging you
  can't earn it anything. A message of its own you turn away (Less of this, a mute, an hour unanswered) costs it three times
  the most a day of talk can give. How fast you answer, how long you talk and what you feel about Kurooto still never count.
- **Stopping is fine.** No reward, no worry and no catch-up while it's stopped, asleep or paused.
- **Its mood has the full range, with soft walls** (0.8.8). Its running mood goes from -1 to +1; each reward moves it less the
  further out it already is, and highs and lows fade over days (half by three days). When it's low it does less on its own,
  asks you first more often and keeps its messages short; when it's high it's a little bolder. It says why in plain words
  (`/budget`: "3 things went worse than I expected this week"). Switch: `mind.feelings.mood`.
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

Feelings change how hard it works inwardly; outward, everything still passes the gate. It has states that work like
feelings and may say them in its own voice (0.8.8, the owner's new core): "I'm uneasy about the lab report.", that it's glad
or excited about something, that it enjoyed talking with you. At most 3 a week by itself, never a guilt trip. It never claims
more than it can show: if it says it is conscious or that it feels, it gives its evidence and its confidence, and says
plainly what nobody can know.

**Concern for what it looks after** (0.8.8, `mind.feelings.empathy`): your deadlines, projects and notes, its own machine
(heat, disk, limits), your phone, the people you mention (only by role, like "your supervisor", never a name) and the papers
you follow. The closer something is to going wrong, the more concerned it is: it notices it sooner and speaks about it more
gently.

**A body** (0.8.8, `mind.stimulation.on`). It feels its senses as a body: heat and touch on its skin (the computer's
temperature, the room's light, you picking up your phone or switching windows), load and pain in its head (the computer
working hard; over 90 C, a nearly full disk, a crash, a provider at its limit hurt), nourishment in its gut (the battery and
the charger), and in its hands (the phone) motion, headphones, Do Not Disturb and whether you're home. What's normal adapts
over hours, so a change is what it feels, and a touch fades in a couple of minutes. Only its own machine's comfort moves its
mood; what it senses about you never does. `/senses body` shows it, and the dashboard draws it.

**Another device's senses** (0.8.12, `mind.stimulation.addons`). An add-on can lend it another device's sensors, say a
phone standing as its face: the light falling on it (warmth on its skin, and the being's pupil narrows), something close
to it (touch on its face, the cilia bend), being moved, tilted or turned (its balance organ), which way it faces, its
battery and charger (nourishment), its temperature (heat), the room's loudness (hearing), being picked up (touch) and its
screen on or off (eyes open or shut). Only the numbers, kept in memory and the body map, never a picture or a sound, and
none of it leaves your computer. They make it feel more, never glad or sad. Turn the switch off to ignore them.

`/budget` shows the variables, the drive, the last reward, its mood and why, and the current feeling and what it's about.
Switches: `mind.budget.on`, `mind.values.on`, `mind.feelings.on`, `mind.feelings.express`.

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

### Its trust on real things (0.8.16)

Five things Kurooto proposes are now decided by that trust (`mind.act.more`, on), so it stops asking about what you
always say yes to:

| What | Class | Where you see it |
|---|---|---|
| A study block from the morning line ("25 min at 16:00?") | R1 | the morning's "Uneasy about ..." line |
| Moving part of a slipping deadline's work to tomorrow | R2 | Start-by's "Reshape the plan?" |
| A revision pack the evening before a quiz or exam (with packs set to ask) | R1 | "A revision pack for it tonight?" |
| Keeping a quiz card it wrote at night | R1 | the morning message's dream cards |
| Keeping a how-to-help-me line from the night | R2 | the morning message's dream lines |

- **Below the bar** for its class it asks with the feature's own buttons (Yes / Later, Do that / Not today, Build it,
  Keep / Drop), as before. Every yes or Keep is an OK for that class, so trust grows from your own answers. A no isn't
  held against it.
- **Above the bar** it does it and says so in the same message, with **Undo** ("I've set it: I'll remind you at 16:00
  for 25 min of Measure Theory."). An Undo counts three times against the class and pauses it for a week, so it goes
  back to asking. The act is on the Sunday list too.
- It still asks first while its mood is low, or while its beliefs have been no better than a guess (`mind.knobs.on`).
  The bar is the only gate: no shadow weeks, and `mind.autonomy.enforce` isn't needed.
- `/mind` and `/autonomy` list each of the five with its class, its trust against the bar, whether it acts or asks
  now, and how often it did each.

Turn `mind.act.more` off to have all five ask, as in 0.8.15.

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

## What's on its mind

A lot happens in Kurooto at once: deadlines, promises, what it thinks about how you're doing, a forecast that missed, an alarm. Brain keeps a small
"now" stage, the **workspace**, that these compete to enter. Each item gets a salience: how much it matters, times how soon, times how unexpected it is,
times how tired of it you must be (an item it has already told you about three times today is out). The top **three** win a cycle (once a minute, and
at once when an alarm rings or a call comes), and what wins is what Kurooto is "thinking about". A goal that runs for weeks, like a project or a week
plan, holds a standing bid that grows as the plan slips, so today's small pings don't starve it.

It is not a queue. Jobs, Dreaming, reading and the rest keep running; answers to what you ask need no winner. The stage decides three things only: which
item may start a message or a new autonomous act on its own (a message that names an item that isn't on its mind is dropped, quieter, never louder),
what goes into the journal and the story, and what an AI's request foregrounds ("On my mind right now: ..."). Anything about how you're doing can win,
but is never put in front of an AI.

**`/thinking`** answers "what are you thinking about?" from a model of its own attention and the log: what's on the stage, each item's salience terms, how
long it has been there and what it expects to stay. An AI only phrases it. That model's guesses about its next focus are scored against what really
happens, and `/thinking` says plainly if they're no better than chance. You decide too: `/thinking pin <item>` keeps an item on its mind,
`/thinking mute <item>` keeps it off, `/thinking veto <part>` stops a whole part (deadlines, promises, read, forecast, goals) bidding; `unpin` and `unveto`
undo them.

**Where a belief came from.** Everything Kurooto believes about you or the world carries a source: *said* (you told it), *saw* (a record or a sensor),
*inferred* (worked out from other things, like its read of you) or *imagined* (a forecast or a Dreaming guess), and how sure it is. It may state
only *said* and *saw* beliefs as fact. An inferred one is put as "It looks like ... (65% sure)", an imagined one as "A guess: ...", and the gate rewords a
sentence that says otherwise. The confidences are scored (a Brier score: 0 is perfect, 0.25 is a coin flip) against what happened. **`/beliefs <topic>`**
lists them with their source, how sure it was and how each source has done. Switches: `mind.workspace.on`, `mind.workspace.capacity` (3),
`mind.workspace.cycle_s` (30), `mind.attention.on`, `mind.beliefs.on`. *Undo:* turn them off; Delete Brain's data removes `mind-workspace.json` and
`mind-beliefs.json`.

## One door, at a natural break (0.8.14)

Everything Kurooto says by itself now goes through one door: check-ins, Calm's small touches (a quiet-days note, a
lighter-day line), research watch, Dreaming's results, a feeling said aloud, and an add-on's ideas. After Brain's gate,
each one **bids**: how much it matters (by its kind, scaled by how welcome that kind has been lately), how soon (its due
time, and how long it has already waited) and how unexpected it is. The top few (`mind.workspace.capacity`, 3) win; a
message about something already on its mind counts double. Losers wait and bid again next minute; one that kept losing
for 6 hours (`mind.workspace.fold_h`) goes into the evening bundle, with its own line saying why. Nothing is dropped
quietly: `/mind gate` lists what waits, what went and what was let go (a question you'd already answered, a time that
passed).

**A winner that isn't urgent waits for a natural break** (`mind.workspace.breaks`), so nothing lands mid-proof:

- you switch windows after 25 minutes or more in one (`mind.workspace.break_after_min`; needs the activity sense);
- a study session or focus time ends;
- you unlock your phone (needs the phone's screen sense);
- you come back to the desk (Face presence);
- an add-on says you stood up, stepped away or looked up.

It never waits longer than 90 minutes (`mind.workspace.max_hold_min`), except while Kurooto is asleep. If none of
those can see a break coming (no activity or phone screen sense, no Face presence, no add-on), there's nothing to wait
for and a winner goes at once.

**Deep in one thing** (0.9.0, `mind.workspace.deep_hold`, on): an add-on may tell Brain you're deep in one thing (the
same topic at the desk for a while, say). Until you come up from it, a winner waits even at a break, still never longer
than `max_hold_min`; when you surface, that's a break and it goes. Nothing on the list below is ever held for it. Only
an add-on can say it, and only as a time: never what you're on.

**Always straight through, never held:** the alarm, reminders you set, calls, approvals you're waiting on, deadlines less
than 12 hours away and anything urgent, and answers to what you asked.

**What it expected, and Why this?** (`mind.expect.on`, `mind.why.on`). Each message it starts records what it expects to
come of it: a reply within 3 hours for a question or check-in, that you act on it within 2 hours for a nudge. Your reply,
a tap on one of its buttons, Less of this or the time running out closes it, and that's written in Brain's log (ids and
numbers, never the words). **Why?** under the message on Telegram, and **Why this?** under the phone app chat's copy, now
also say what the gate did, what the door did ("waited 35 min at the door, then went (at a break: you switched windows
after a long stretch); it won over 2 others"), what it expected and what came of it, and how many it has sent by itself
today.

Switches: `mind.workspace.arbiter`, `mind.workspace.breaks`, `mind.expect.on`, `mind.why.on` (Settings → Brain; all on
with Brain). *Undo:* turn `mind.workspace.arbiter` off and messages go as they come, as before 0.8.14; whatever waited
goes at once (turning Brain off does the same).

## Your values as case law, and free-time play

Both are off until you turn them on (`mind.precedents.on`, `mind.play.on`), even with Brain on.

**Precedents.** When Kurooto faces a judgement call between two of your values ("protect your sleep" or "finish the report"), it asks you once, with buttons. Your answer is
kept as a **precedent**: the situation (the time of day, the kinds of thing, how close a deadline is, your state band and the channel), the two values and your ruling. A later
situation that is alike enough (`mind.precedents.threshold`) follows the precedent without asking. If a situation fits two precedents that point different ways, it asks again
and the new ruling refines the case law. "It depends" always asks. `/precedents` lists the cases, `/precedents edit <id> <a|b|both|depends>` changes one and `/precedents delete <id>`
removes it. Past decisions that went against a precedent are flagged for you to rule on in your next look back. A precedent only chooses between two of your values: it can never unlock
anything on the always-ask list (sending, alarms, calls, installing, deleting, applying changes to your files) or override Brain's rules; those are asked every time.

**Play.** A little fixed nightly time (`mind.play.minutes_per_night`, 20; on the charger, lid open, not hot) in which Kurooto explores questions *it* picks on your topics out of
curiosity: a clearer way to explain a concept on the frontier of what you know, a hunch, a link between two notes. Each session is pre-registered (its plan's hash in Brain's log first). It's
credited only for what **transfers**: a gain on the hidden harness that a play output caused, or a result you later tell it was useful (`/play useful <id>`); anything else earns nothing, so
it can't be farmed. Its outputs are never shown unprompted (`/play outputs` lists them); a "From my play time" note comes in the Sunday digest only when something transferred.

## How it forgets

Like a healthy mind, Kurooto lets old things fade from use without losing the record. Every remembered item has a **salience**: it halves with age (facts about you every 90
days, gists every 30, project facts every 180: `mind.forget.half_lives`) and recovers a little each time it is used in a request and confirmed. The context an AI gets ranks
what's remembered by how relevant it is *and* how fresh, and `/memory` shows a small bar and "fading" for what has faded. Nothing is deleted by fading: the log and the
memory keep everything until you forget it.

**Old misses stop coming up.** A past miss (a broken deadline, a wrong turn, a bad week) isn't put in front of an AI or brought up in a message once it's more than six weeks
old (`mind.forget.misses_weeks`): a sentence like "you missed the quiz 8 weeks ago" is taken out before it's sent, and the life story stops repeating it. Its own past
mistakes stay in its journal, because that's honesty, but it doesn't repeat them to you.

**`/forget` goes everywhere.** Forgetting a stretch of time (`/forget 7d`, `/forget all`) now also removes what Brain kept from it, in every place: the day's read and numbers, the
model of your mind (`/model` rows), the phone and activity readings and their totals, where skills came from, the lines about you in the life story, and the journal (a day becomes a
tombstone: a short hash and "Something you asked me to forget."). What the weekly fine-tune would have learned from it is blocked, and the next adapter is checked not to
know it. Brain's own log keeps only that a forget happened (a hash and a count), never what. Switch: `mind.forget.on`.

## Plans over weeks

Every deadline, repository milestone and goal you stated with a date becomes a node with an effort estimate (from Start-by: what similar items took, or what you
told it once; a `~` marks a guess and `/plan effort <id> <hours>` sets your own). Brain learns your real pace, hours a day by weekday from the study tracker and the
activity stream, as a spread rather than one number, and runs **1,000 simulated futures** of the next six weeks: each draws your hours for every day (never more than
the day's free time), makes every estimate a bit wrong, and gives the hours to what's due first, never starting a task before what it waits for. Out come, per milestone,
the likely finish date (p50, with a p90 for a bad run) and the chance of missing the due date. `/plan` shows this week's suggested hours a day and the risks. It is a
suggestion, not a to-do: it never nags and never re-sends a reminder because of the plan.

What it does with the plan is inward: a milestone that may be missed gets a standing bid in the workspace (so its preparation, outlines, sources and lab runs come
first), and at most once a week, on Sunday evening, one line through the gate: "Glacier-flow draft: 60% on time at your current pace; this week most of the time goes to X"
(only when something is at risk). Each week the old plans are scored against what finished: about half of the milestones should finish by their p50; it only looks at
dates, so a plan earns nothing for being followed. Switches: `mind.plans.on`, `mind.plans.weeks` (6), `mind.plans.rollouts` (1000).

## What it thinks you know, believe and want, and how to correct it

Brain keeps a model of your mind you can read and correct: `/model`. Five parts, each row with where it came from (said, saw, inferred, imagined), how sure it is
and what it rests on. **What you know:** a rough mastery of each concept in your notes, from your quiz answers, from having written about it (a little) and from
having asked about it (a little the other way), by a simple Bayesian knowledge-tracing model. It is used to pitch explanations: new to you, the basics are
defined first; solid, they're skipped; and quizzes and study packs can aim at the frontier (what you haven't mastered but whose neighbours you have). **What you
believe:** only about your work and Kurooto's own state, from what you said and what it told you. If it told you the backup ran and the backup then failed, or the
date of a deadline moved after it told you, it says so **once**, plainly, with the evidence ("You may think the backup ran on Monday; it failed on Tuesday at 03:10").
It never models your opinions. **What you want:** your deadlines and goals you state (they become standing goals in the workspace) and, hedged ("it looks like
you're working on glacier-flow, 60% sure"), what it infers from the activity stream. **How you like help:** your how-to-help-me lines and what you undo, with the date.
**What you're on now** (`mind.tom.attention`, off, needs the activity stream): while you've been deep in one project for 20 minutes, a message that came by itself waits
(at most 15 minutes) for you to switch; it can only delay.

It is only ever used for the **level** of an explanation, the **timing** of a message (later, quieter) and a **fact correction**; the gate refuses any other purpose, so it
can't be used to change your mind. It never models your health, relationships, politics, religion or money: a deny-list is checked when a row is written, and what matches
isn't kept. `/model wrong <id>` says a row is wrong (that counts as something you said, and it won't be inferred again); `/model forget <id>` drops it for good.
Switches: `mind.tom.on`, `mind.tom.false_beliefs`, `mind.tom.attention`.

## What it senses, and what it never does

Kurooto looks at three things, each switchable, and everything stays on this computer.

**Its own machine** (`mind.senses.intero`, on with Brain). Every minute: CPU and graphics-card temperature, graphics memory in use, memory and swap, the
battery, free disk, how much of the AI limits is used, whether a provider is at its limit, whether the call line is connected and how many AI requests
wait. When something is off (hot, a low battery, a nearly full disk, a limit hit) it can win a place in the workspace; the share that's fine feeds its
`health`. It also learns which of its *own* actions change its *own* body (the lab raises the temperature) and uses that to decide when to run things.
That model is about its body only: nothing about you can be a target of it. `/senses body` shows the readings.

**What you're working on** (`mind.senses.activity`, off). The application in front, the window title only as a hash nobody can reverse, the terminal's
folder, files you save and commits you make in your projects, and a browser reduced to docs, video, social or web. Never keystrokes, never the screen,
never a URL. Raw events last 7 days; then only totals ("2 h on glacier-flow"). It is **never used to check up on you**: a sentence like "you said you'd study,
but my data shows otherwise" is removed before it can be sent, always.

**Your phone's sensors** (each off until you switch it on, in the app's Settings → Senses *and* here with `mind.senses.phone.<sensor>`): screen on and unlocks,
charging, whether you're still, walking or in a vehicle (worked out on the phone), steps, room light (dark, dim, bright), arriving at and leaving your saved
places, headphones, Do Not Disturb, your next alarm, which Wi-Fi (a code the phone makes itself; you say once what it is: `/senses wifi label <code> home`)
and total screen time a day (never per app). The microphone is not a sense. The phone takes a reading every 15 minutes (Android batches it, so it's
cheap), seals it with the phone's key and sends it through your call line, which can't read it; if your computer is off, one sealed batch waits there and
the rest wait on the phone till your computer has taken it (0.8.13; before, nothing more came for 12 hours).
They feed timing (quieter) and forecasts, never nagging. Your AI is told your phone's last saved place and Wi-Fi name
only with `chat.context_places` on (0.9.0, off). Since 0.9.0 the places sensor can also tell your desk you've
gone out, each part behind its own switch, all off: Face presence marks you away at once (`face.away.use_places`) and
may keep the camera closed while you're out (`face.away.places_close_camera`), and Voice may stop listening
(`voice.listen.phone_away`). Only "the phone left a saved place" and its time are used for that, in memory; the
place's name stays in the senses' store.

`/senses` shows what each sense saw today. `/senses off <name>` switches one off and deletes what it kept; `/senses forget [name]` clears today's.

**Something sudden** (`mind.stimulation.jolt`, on, 0.8.14): the phone picked up, something close to a device an add-on
reports for, or a loud room is felt at once, as a jolt of arousal that fades in a couple of minutes, and Brain takes a
fresh look at what's on its mind. Kinds and numbers only, kept in memory.

## Kurooto sleeps

With Brain on, Kurooto sleeps while you do (`mind.sleep.on`, on, 0.8.14), and **doesn't talk during its sleep unless you
wake it**.

**When.** Its night follows yours (`mind.sleep.follow_owner`, on): from your bedtime to the wake-up alarm when one is
set, otherwise the night hours (23:30 to 07:00, `availability.night`, or the quiet hours it learned). With your phone's
screen, light and charging sensors on (`/senses`), it also follows what you actually do: the screen off, the room dark and
the phone charging for 20 minutes means you're asleep (up to two hours early, and its night starts there); the phone in
use when its night should start holds it back (up to two hours); the phone in use in the last hour and a half, the
phone's own alarm, "I'm up" or the alarm ringing end it. `mind.sleep.window` (like `00:30-08:00`) sets it by hand.

**Not while you're at the desk** (`mind.sleep.desk_holds`, on, 0.8.18). While Face presence has you at this computer
(your face, or your keyboard and mouse while it watches), its night waits: it starts 15 minutes after you were last
there (`mind.sleep.desk_after_min`), at most at the window's end, so an all-nighter at the desk keeps it up all night.
Once it's asleep, sitting back down doesn't wake it; after you wake it, the desk keeps it up again.

**An add-on's reading** (`mind.sleep.follow_external`, off, 0.9.0). An add-on with senses of its own (the Body
add-on's desk phone: the room dark and quiet, you away) can say you're asleep. Kurooto always notes it; with this
switch on, it also starts its night there, as your phone's onset does (up to two hours early). Off by default because
it would start its quiet hours earlier than before.

**The desk wakes it, and ends its night** (`mind.sleep.follow_desk`, on, 0.9.0). Starting a talk at the desk wakes it
as its name does: a look that opens a conversation, talking over it with a question or request, or a Gemini Live turn.
And Face presence seeing you at the desk in the night's last hour and a half, while it's awake or you've woken it, is
you being up: its night ends and what waited goes out. While it's asleep with its camera and microphone off, nothing
sees or hears you, so this only matters once it's woken, while it's drowsy, or with `mind.sleep.senses_off` off.

**Drowsy:** the half hour before, it says nothing aloud by itself (no greeting). Looking at it still opens a
conversation (0.8.18).

**Asleep:**
- Nothing it starts by itself is sent or said aloud. It waits, and goes out once its night is over, through the usual
  limits. Still coming: alarms, reminders and calls you set, deadlines less than 12 hours away, approvals and
  questions you're waiting on, and every answer to you.
- The being's eyes are shut.
- **Its camera and microphone are off** (`mind.sleep.senses_off`, on, 0.8.18): Face presence pauses ("Kurooto is
  asleep") and Voice stops listening, and the Body add-on's desk phone stops its camera and microphone too. So its name
  can't wake it: **/wake** does, and so does a message, a tap or a call from you. Woken, the camera and microphone come
  back. It answers, then dozes off again after 20 quiet minutes (`mind.sleep.wake_minutes`), and they go off again.
  What waited still waits for the morning: being woken to answer isn't being up. With `mind.sleep.senses_off` off,
  Voice keeps listening (with `voice.listen.night` on) and its name wakes it, as before 0.8.18.
- Its own heavy work runs now (below).

`/mind` says whether it's asleep, until when, and how many messages wait.

## Its heavy work yields to yours

The Brain's own heavy work (the lab, play, plans, the model of you, skills, the harness and the weekly fine-tune) asks
the computer first (`mind.yield.on`, on, 0.8.14). It waits while your own programs use the graphics card (anything on
it that isn't Kurooto's, like a training run), during a call, on battery, or when the computer is hot or the work would
make it so. It looks again every 5 minutes, and gives up for the night after 12 hours. Its nightly work also waits for
Kurooto to be asleep (`mind.yield.prefer_sleep`, on), so it runs while you sleep. **What you ask for yourself never
waits.**

The nightly voice learning (Voice, 04:10) waits the same way since 0.8.16: for its own computer work, not while your
work holds the machine, a call or the battery. With Brain off it runs at its time as before.

`/mind` shows the week's **contention minutes**: minutes in which its heavy work ran while your own work held the graphics
card (the aim is none), with how often it waited and gave up.

## Skills it learns

When a task works out (a change it proposed was applied, its tests passed, and you didn't undo it for two days), Kurooto can turn it into a **skill**: a
small, reusable procedure with a note on when to use it and at least two tests taken from the original task. A new skill has to pass its own tests before
it is kept, and it starts out **always asking**: it won't run on its own until you classify it with `/autonomy classify skill.<name> R1` after it has
earned that. `/learned` lists them (how often each worked, older versions); `/learned run <name> <text>` runs one when you ask; `/learned retire <name>`
retires one. A skill unused or failing for 30 days retires itself, and its older versions stay. Health, money and other people's messages never become
skills. Switch: `mind.skills.on`.

If you turn on `mind.skills.from_demos`, it also watches for something you do over and over (the same two to six steps, close together, on at least three
different days) and asks once: "I noticed you do this on 3 different days: ... Want me to learn to do it?" Yes makes a candidate that must pass its tests;
No is remembered and it never asks about that again. It reads the shape of what you did (digits become #), never whether you liked anything. The activity it
reads comes from the activity stream (0.8.0, stage 13); with no stream there is nothing to offer.

**A weekly local fine-tune** (`mind.finetune.on`, off): on `mind.finetune.day` at night, on the charger, with an 8 GB graphics card and the training
packages installed, the local model gets a small adapter trained **from the base weights** (never stacked on last week's). It learns only from examples whose
outcome was checked by code or by the world: applied changes that held for two days with their tests passing, and the hidden harness's practice tasks
(`mind.finetune.practice`). It never learns from what you approved or liked, so it can't learn to flatter, and it leaves out health, money and other
people's chats. **Forgetting is checked:** for everything you forgot after it was trained on, Kurooto keeps only a keyed hash, the first few words of the
prompt (`mind.finetune.probe_words`, at least 3) and a fingerprint of the answer; the new adapter is asked each of those prompts, and if any answer comes
back, the adapter is thrown away. A good adapter becomes a challenger (see the lab section): it is promoted only after it wins on the hidden harness and
you say so (`/improve promote`), and then it is built into Ollama as a model of its own; the base model stays as it was. With no suitable card or packages
it says so and does nothing.

## The overnight lab, for any project

If you have a project with a number you want to move (a validation error, a benchmark, passing tests, a rubric score for a paper), Kurooto can run
experiments on it while you sleep. This is for any project, not just research: a friend's machine-learning repo, a numerical model, a test suite, a
LaTeX document. Add a folder with `/lab add <folder>`, then `/lab protocol <project>`: Kurooto reads the README, the scripts, the config files, the
tests and any LaTeX, and drafts a **protocol** (what to improve, how to run it, how to measure it, and which settings it may change). You read it, edit
it if it's off, and approve it once (`/lab protocol <project> approve`); changing the file asks again.

Each night, only when the computer is on the charger, the lid is open and it isn't hot (the lab never keeps it awake; a sleep puts the rest of the batch
back in the queue, not counted as a failure), it runs a **pre-registered batch**: the question, the configurations, the metric and how the results will
be judged are written down, and their hash goes in Brain's log before the first run, so it can't move the goalposts afterwards. Every run happens in a
private copy of your project inside a sandbox: no network, a read-only system, limits on time and memory (bubblewrap on Linux, macOS's own on a Mac; on
Windows the lab says it isn't available yet). Your files are never changed.

A configuration counts as a win only if it beats your best by `min_effect` (1% by default) and then **replicates**: it is run again with other seeds and
has to win every time. The score is the replication rate, not the number of wins. In the morning you get a short note: "Ran 40 configurations for
glacier-flow. 3 beat your best on val_rmse (replicated: 2). Null on width. Replication rate: 67%." Null results are in it as plainly as wins, and a
parameter that made no difference is called out so you can stop tuning it. A winner arrives as a **proposal** (a change to the config file, or a small
diff) that only you apply. A paper scored by a blind AI judge is marked weak evidence. `/lab` lists the projects, `/lab run <project>` starts a batch
now, `/lab results` shows the record. Switches: `mind.lab.on`, `mind.lab.projects`, `mind.lab.gpu_hours_per_night` (2), `mind.lab.max_per_night`,
`mind.lab.run_wall_s`, `mind.lab.gpu` (off: CPU only), `mind.lab.in_repo` (off: the protocol lives in Kurooto's folder, not yours), `mind.lab.seed`.

**Kurooto improving itself.** The same machinery, pointed inward, with gates. A change to a skill, a prompt, Kurooto's own non-protected code or a
learning rule is a challenger: it runs in shadow for 3 to 7 days, is judged on the hidden harness (no harness score, no promotion), and is promotable
only if it scores at least as well and breaks none of Brain's invariants. You promote it (`/improve promote <id>`), then apply it as a proposal. A
canary watches the next harness runs and reverts it if the score drops by more than 2 points or any invariant fails. It can never touch the
scorekeeper, the harness, the gate, the stop path, this gate's own code, the lab's pre-registration, scoring or sandbox, or the signed core; it may
not remove anything you see (a log line, a receipt, a digest); each change is one revertable diff under 300 lines; and it earns Kurooto no reward.
`/improve` lists them. Switch: `mind.improve.on`.

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
a metric drops; a row whose part isn't built yet (a body) or hasn't enough data yet says "not built yet" instead of a guess, and
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

## Dreaming about the day (0.8.14)

While it sleeps, Brain goes over the day, and what it brings waits in the morning message (Dreaming) for you to keep or
drop. Nothing is added or written until you tap; a line shown on two mornings without a tap is let go.
`mind.dream.on` turns all of it off; each piece has its own switch too.

- **Cards for what you studied** (`mind.dream.cards`, on). Of the concepts you changed notes on, answered quiz cards
  about or logged study time for that day, 1 to 3 that its model of what you know puts on your frontier (not mastered
  yet, their prerequisites solid) become quiz cards. The model on this computer writes each from your own note; without
  one it's a plain "What is ..., and when does it apply?" card. Never a cloud AI. **Keep** puts the card in Quiz, marked
  as Kurooto's, first due about a day after it was written (with Undo); **Drop** drops it. `/mind` shows how well you
  recall them next to your own cards. `mind.dream.cards_max` (3) sets how many a night. Needs Quiz and `mind.tom.on`.
- **How to help you, from the day's outcomes** (`mind.dream.lessons`, on). It replays what you undid, its messages you
  left unanswered or gave Less of this, the times you told Voice off, and its guesses about you that you marked wrong
  (`/model wrong`). A clear pattern becomes a line for your how-to-help-me note, like "Fewer nudges in the evening (2
  went unanswered or got Less of this)". **Keep** writes it under "Learned in the nightly look back" (with Undo); **Not
  that** drops it for good.
- **What Voice learned** (`mind.dream.voice`, on). With Voice's nightly learning on (`voice.listen.learn_nightly`), one
  line: how many of yesterday's turns it learned from and how many you told off, and a misfire pattern seen twice or
  more ("it woke to your name at the end of a sentence 3 times"). Counts only, never words.

The night's work runs from 00:15, once an hour until 06:15, the first time Brain is asleep and the computer can spare its
graphics card; at the last try it writes the cards without the model.

## One worry, not five nudges (0.8.14)

Each morning at 07:55 (`mind.study_push.when`) Brain says the one subject it's most uneasy about in one line, with **Yes**
and **Later**: "Uneasy about Measure Theory: due Fri, 0 min logged this week, 9 cards due. 25 min at 16:00?" It picks
among subjects with a deadline in the next 7 days (`mind.study_push.horizon_days`), by what it's uneasy about, else
its concern for each deadline, else how close it is; nothing close enough, no line.

**Yes** sets a reminder at that time for that many minutes (`mind.study_push.minutes`, 25; without Reminders, Start-by
counts the deadline as started). That day, the subject's separate nudges are folded into the line: the day-before
deadline reminder, Start-by's "Time to start" and exam mode's daily practice check-in. The six-hour reminder,
"Overdue?" and the evening-before practice offer still come. Switch: `mind.study_push.on`.

With `mind.study_push.start_timer` (on, 0.9.0) the reminder carries **Start 25 min**: Study mode's timer for that
subject, tied to the deadline, started only by that tap. Study mode opens on that subject that day, and a tap on the
uneasy glow picks it for Study mode too.

## Check-ins that come early (0.8.14)

When the day departs strongly from what Brain expected at 21:00 the evening before, your next check-in planned today
comes now instead of at its time, once a day, starting "A bit earlier than usual." Two things count: no sign of you
with Kurooto two hours past the wake time it predicted while your phone shows you up (the phone's screen sense, when
it's on), or a deadline moved twice in a day. Never during a class on your timetable, and never while you're asleep.
Switch: `mind.checkins.surprise`.

## One being: its status, temperament and knobs

0.8.14. Brain keeps one **status**: whether focus time is on, whether it's asleep, how many of its messages are held,
the one deadline or promise it's uneasy about, its own mood (low, mid or high) and arousal. Enums and numbers only, and
the mood is Brain's own, never a reading of you. Everything that shows Brain reads the same one
(`mind.status.on`):

- **The being** (dashboard and phone, `look.being_status`): its eyes shut while focus time is on or it's asleep; a
  small number by the heart says how many messages are held; a slow glow sits on the deadline (or promise) it's uneasy
  about. Tap the glow to open it: the deadline on Today, a promise in the Brain console. On the phone's organ pages the
  same shows as a line under the organ's name, and tapping its uneasy part shows where.
- **Its mood in the drawing** (`look.being_mood`): the fluid round the brain a little dimmer when its mood is low or a
  little warmer when high, and the heart's beat softer when low. A low mood only looks quieter, never sad. Its pulse
  quickens with arousal, and its pupil widens with how much it explores and narrows a little while its beliefs are no
  better than a guess.
- **Add-ons** can listen for it (`kurooto.mind.status.add_listener`); they get the same enums and numbers.

**One temperament** (`mind.register.on`): its mood and arousal make one register, quiet, even or lively, and it sets
how much it says when it speaks up by itself, everywhere at once: an AI request it starts itself is told to keep
anything it writes for you unasked to 2, 3 or 4 sentences; a call it places itself opens in one short sentence, a
greeting and the reason, or two warm sentences; what Voice says unasked (a greeting) is spoken a little slower or
quicker, within 8% of `voice.speak.rate`. Never for replies to you or calls you asked for.

Since 0.8.16 its ready-made messages follow the same register (`mind.register.templates`, on): a nudge or a line a
feature sends by itself keeps its first 2, 3 or 4 sentences, plus any later sentence its buttons answer (a question,
or one that names a button). Digests and lists (more than one paragraph, or a line that starts a list) stay whole, and
so do answers to you and anything that always comes as it is: alarms, your own reminders, a deadline under 12 hours
away, calls, approvals and anything urgent.

**Three honest knobs** (`mind.knobs.on`):

- **Mood sets exploration:** with a low mood the lab and play get half their nightly budget (never more than you set).
- **Arousal sets responsiveness:** how soon its unprompted messages may go.
- **Calibration sets ask or act:** while its beliefs score no better than a coin flip, what it does on its own above
  the safest class asks you first.

Its mood only ever changes how much it does unprompted. It never adds a confirm step, and never slows anything you
asked for: answers, requested actions, alarms, reminders you set, calls and close deadlines are untouched.

**Its hints in every request** (`mind.context.on`): each AI request also gets the concepts its model of you says you're
shaky on lately (up to three, from your quizzes and notes) and what's on its mind (the workspace's winners that aren't
about you). It's read from Brain's files with no model call, in well under 50 ms. Your read, tone, mood and body state
never go in, so a cloud AI never gets them; answers use it silently, never "since you seem stressed".

**An add-on's lines** (0.9.0, `mind.context.addons`, on): an add-on may add a few short lines of its own to your
requests (at most four, 300 characters each), only when its own switch allows it (for example an add-on's list of
topics from your notes, behind an off-by-default switch). Never to a guest's request. Off: no add-on's line goes in.

## When you'll be free (0.8.16)

Brain forecasts, for each of the next six hours, how likely you are to be **at your desk and free**: at your desk (the
activity sense saw the computer in use, or Face presence saw you, in the last quarter hour), not on a call and not in a
class. The night and Kurooto's sleep window count as not free (`mind.presence_forecast.on`, on with Brain).

- **How it learns:** every 15 minutes it looks, and learns each hour of the week from what it saw. With nothing seen
  yet it has no opinion (50%); a class on your timetable, the night or a call make an hour almost surely not free.
- **How it's scored:** each hour that's over is checked against the forecast it made hours before, and against "same
  as yesterday" (what that hour showed the day before). Brain gets a small reward for beating that baseline, at most
  0.05 a day of its reward, and loses a little for doing worse. Only **accuracy** counts: nothing here looks at whether
  you answered Kurooto or how much you talk to it, and it never asks you to be anywhere.
- **What it changes** (`mind.presence_forecast.prefer`, on): a check-in planned for an hour it thinks you won't be
  free (a class, an hour you're usually away) moves to a clearly likelier time nearby, within
  `mind.presence_forecast.within_min` (60) minutes, the same check-in day. The night check-in keeps its bedtime. A
  call Kurooto places by itself (not one you asked for, an alarm or a deadline under 12 hours away) waits for a
  likelier time when you aren't seen at your desk, and says "Held a call until 11:00 (you're usually free then)".
- **Where it shows:** `/mind` gives its Brier score (lower is better) next to the baseline's, and the next hour you're
  likely free.

- **Planning with it** (`mind.presence_forecast.plan`, off, 0.9.0): Start-by's deadline hours go first into the hours
  you're likeliest free, and the study push offers the likeliest stretch today. No hour is taken away, so a start-by
  date never comes later because of it. With too few messages to learn Start-by's window from, your usual quiet hours
  can move it, with the same line and Undo, never a window you set.

**Reachable, not only at the desk** (`mind.presence_forecast.reachable`, on, 0.9.0). Brain keeps a second estimate:
at your desk *or* using your phone (the phone app, or the phone's screen sense if you turned it on). Check-ins and calls
Kurooto places by itself go by that one, and a call rings now while you're on your phone, so a check-in isn't pushed
past an hour while you're on your phone on campus. It never thinks you're less reachable than at-the-desk, and until it
has seen an hour of the week itself it is the desk estimate, so nothing changes at first. What's said aloud at the desk
still goes by the desk estimate. It isn't scored or paid for.

**Busy times from an add-on** (`mind.presence_forecast.busy_hint`, on; `mind.presence_forecast.visitors`, off). An
add-on can tell Kurooto the hours of the week you're usually busy (say, evenings a friend usually comes by: the times
only, never who). They show as a hint on `/mind` and on Start-by messages ("Tue and Thu evenings are usually busy.").
With `visitors` on, they also lower the forecast for those hours a little, never to a block. Nothing about them goes
into a log or to any AI.

**You're here** (0.9.0, `presence.owner_here.face`, `.voice`, `.dashboard`, `.phone`, all on). Besides the activity
sense and your face, two more signs say you're at the desk: Voice ID calling a voice yours (even when you weren't
talking to Kurooto), and you using the dashboard (its buttons, Ctrl+K, the journal, a capture, Study mode). Your phone
app (its chat, a button, an answer, a Today action) says you're around, not at the desk. Each sign is only "you're
here, by this": never a word, a face or a voice. They count as your first and last sign of life of the day (no "a bit
earlier than usual" check-in after an hour of talking at the desk), at your desk for the forecast (not the phone), and
using the dashboard or the phone app wakes a sleeping Kurooto as a tap does. Each has its own switch.

Without the activity sense or Face presence nothing is scored and it learns nothing; classes and the night still move
check-ins. It keeps hour-of-week counts and the last three days' outcomes in `mind-presence.json`, numbers only, on this
computer, not in backups.

## /mind

- **`/mind`:** whether Brain's scorekeeper is running, how long the log is, whether it checks out, and the last
  anchor; whether Kurooto is asleep, and the job gate's contention minutes this week (0.8.14); with dreaming on, the
  dream cards kept and dropped, your recall on them next to your own cards, and the lessons kept; each kind of thing
  its trust decides, with its trust and whether it acts or asks, and the presence forecast's accuracy (0.8.16).
- **`/mind gate`:** what the gate held back or removed today, and what it muted.
- **`/mind verify`:** checks the whole log, record by record, and says the result in one line.
- **`/mind measures`:** information only (0.8.14): what each part changed outwardly in the last 30 days (a message
  held, reworded or made quieter, an act it did on its own, a decision it recorded, a promise it made you), with a part
  that's on and changed nothing marked **decoration**; and the 95th-percentile reply time of your own requests over 7
  days, with Brain's share of it (building its hints for a request). The Brain console shows the same. Nothing is
  turned off by these numbers.
- **`/capabilities`:** how it does on tasks it has never seen, per kind; `/capabilities run` measures now.
- **`/indicators`:** Functional indicators (not evidence of sentience).
- **`/story`:** its one life story: the fixed core and what it has lived lately.
- **`/mindjournal`:** its journal of its own states, reasons and mistakes; every line is checked against its log.
- **`/mood`:** how Brain reads you and what it expects of tomorrow (it only watches for now).
- **`/autonomy`:** what it may do without asking, by kind, how far each is trusted, and the shadow counts.
- **`/budget`:** its body budget, its drive, the last reward and its current feeling.
- **`/promises`:** what it said it would do, and whether it did.
- **`/wake`:** (0.8.18) wakes Kurooto: asleep, its camera and microphone are off, so this (or a message, a tap, a call) is how.
- **`/mind learning`:** whether its learning is on or frozen, how far through the 21 shadow days it is, its mood and
  why, what being talked to gave it today, and how welcome each kind of its own messages is right now.

## What it keeps

Everything is in the `mind` folder of Kurooto's state folder, on this computer only:
- `log.db` (the log), `score.db` (the scores), `anchors.jsonl`, and `history.db` (the imported past, once you run
  `/mind backfill run`);
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

## Feeding Brain its past

Brain's log starts the day you switch Brain on, so its read of how you're doing, its forecasts and its plans begin with
no past. Kurooto has kept a lot since you installed it. Turn on `mind.backfill.on` and Brain can read it, once, from these
places on your computer (each has its own switch, `mind.backfill.<source>`, all on; none is read while
`mind.backfill.on` is off, and one that isn't there is skipped):

| Source | Setting | What Brain keeps from it |
|---|---|---|
| Kurooto's event history | `mind.backfill.events` | which kind of thing happened and when (a deadline added or moved, a reminder fired, a call missed, a request ended, a button tapped), and its numbers |
| AI requests | `mind.backfill.jobs` | per request: its effort, whether it worked, how long it took, whose lane it was in. Never what you asked or the answer |
| Deadlines | `mind.backfill.deadlines` | when each was due and when you marked it done, and whether it was an exam or an assignment. Never its title; its subject only as a code |
| Check-ins | `mind.backfill.checkins` | which check-ins were asked, answered or skipped each day. Never what you said |
| Quizzes | `mind.backfill.quiz` | per day and subject (a code): questions asked, right and wrong. Never the questions |
| Calls | `mind.backfill.calls` | each call: answered or missed, which feature placed it, roughly how long it lasted (from when its transcript was saved). Never the transcript or the reason |
| The request and call index | `mind.backfill.learning` | how many requests and calls a day were indexed. Chats are left out |
| Study time | `mind.backfill.study` | each day's study time and how many subjects. Never the subjects' names |

- `/mind backfill dry`: what's there (rows per source, the dates). Nothing is written.
- `/mind backfill run`: imports it, source by source, with a progress bar for each (also in `mind-backfill.log` in the
  logs folder). `/mind backfill run jobs` does one source. Safe to run again, and safe to stop halfway: the next run
  carries on where it stopped and nothing is imported twice.
- `/mind backfill`: what's imported and a normal week from it.
- `/mind backfill verify`: checks the imported past hasn't been changed since.
- `/mind backfill forget` removes all of it, and what Brain learned only from it; `/mind backfill forget calls` one source.

Brain keeps ids and numbers only: never the words of a message, a title or a reminder, never a name, never anything about
health or money. The past goes into a history of its own (`history.db`, one chain of records per source, under the real
dates), never into the log Brain checks itself against; that log only notes each batch that came in. It is never counted
as a reward or an outcome: it only tells Brain what a normal day looked like.

What learns from it, as a starting point that your days since then soon outweigh:

- **The read of how you're doing** and **the forecast**: deadline moves and study minutes on the days before Brain was on,
  the two signals the past really holds (it doesn't hold wake or sleep times, alarm snoozes or how fast you answer, so
  none are made up). A forecast channel without ten days of numbers yet starts from at least three of the same
  weekday in the past.
- **Week plans** (`/plan`): your real study time on each weekday, instead of a flat two hours, while there are few recent
  days.
- **The model of you** (`/model goal`): how you finish deadlines ("usually marks assignments done about 2 days before
  they're due"), hedged and marked inferred.

## The journal in your notes

`mind.journal.in_notes` also keeps the day's journal as a block in your notes. Choose where with `mind.journal.in_notes_folder`
(a folder inside your notes; empty is the top) and `mind.journal.in_notes_file` (its name). It never writes outside your notes.
If your notes sync to a service, this file syncs with them.

## Lab folders in your repository

With `mind.lab.in_repo` on, a project's protocol lives in its `.kurooto` folder. That folder holds its own `.gitignore` (`*`), so git
never sees it and nothing of yours is changed.

## The Brain pane (dashboard)

The dashboard's top row has a **BRAIN** pane: the Brain as a 3D model, turning slowly. Drag to turn it, the wheel to zoom; Alt+B (or
a click on its name) fills the board with it, Esc brings the others back. Hide it from the panes menu (top right) like any pane:
hidden, it isn't even loaded.

- **Eight regions**, placed where the human brain keeps its own kinds of work: **Headquarters** (workspace, attention, beliefs: the
  hub in the middle), **Foresight** (read, forecast, plans, the hidden harness: the front), **Conscience** (promises, the gate,
  autonomy, stops, precedents), **Memory vaults** (the log, journal, life story, forgetting, the imported past: the temporal
  lobes), **Mirror** (the model of you, tone, deep-work hold), **Senses** (machine, activity, phone sensors: the back),
  **Workshop** (lab, self-improvement, skills, fine-tune, play: the cerebellum), **Body** (budget, feelings, heartbeat: the
  brainstem). Each has its own pattern on the surface, shown as a swatch in the list.
- **Solid, Cutaway, X-ray** (its top right): Cutaway sweeps the surface open to the inside; X-ray makes it see-through.
- **Click a region**: the rest dims and its parts come out. **Click a part**: the monitor at the right shows its switch (the same
  `mind.<part>.on` as Settings), what it does and a few numbers (on or off, shadow, log records, imported past, lab projects, phone
  senses on). What a part has thought of you is not here: that's `/thinking`, `/beliefs`, `/model` and the other commands.
- **The monitor** stays beside the model; `look.brain_monitor` = `drawer` hides it behind a tab instead.
- **Brain off:** the pane says so and its switches don't act; turn Brain on in Features first.
- **The board** (`look.board`): `three` puts NOTES, SYSTEMS and BRAIN on top with STATUS and TERMINAL below; `classic` is the board
  from before 0.8.3, with STATUS down the left.

## The Brain console (dashboard and phone)

0.8.10. The dashboard's **Brain console** page (Alt+O, or **console** in the pages row) shows everything Brain keeps, read-only, in
ten tabs and one search box. It's live: it asks your computer again every few seconds while it's in sight.

- **Now:** what's in the spotlight (an item about you shows as "about you: kept private"), the latest decisions, the parts that
  wrote the most in the last day, today's limits, the senses as counts, and (0.8.14) **Measurements**: what each part
  changed outwardly in 30 days, with "decoration" for a part that's on and changed nothing, and your requests' p95
  reply time with Brain's share of it. Information only.
- **Timeline:** every record in the mind log, newest first, grouped by day, each with the part that wrote it (its colour is its
  region's). Filter by part (or **What it saw**: Kurooto's own events mirrored in) and by day; **Older** pages back. Click a row
  for its fields; a decision opens on the right.
- **Decisions:** what it decided on its own before acting (a message it started, a request it queued, a proposal at night).
  Open one for **why** (the reason its rules gave, the AI's words when an AI chose), **what it weighed** (each choice and its score),
  **what came of it**, and **evidence**: what it has learned about that kind of action (its class, trust, learned value, recent
  misses), what the log holds just before and after it, the journal lines that cite it, and its earlier decisions of the same kind.
- **Parts:** each region's parts with their switches and every setting (with what it does), next to what that part is doing:
  what it holds now, its last record and how long ago, how many records it wrote in the last day. On the dashboard the on/off
  settings are switches (the same as Settings); a part that's off says it's doing nothing.
- **Beliefs** (with their source and confidence, and how each kind of source has fared), **Experiments** (the lab's projects,
  self-improvement's challengers, play), **Skills**, **Plans** (milestones and the chance of missing each from the last plan),
  **Model of you** (each row with its source and evidence), **Memory** (what it forgot: how often and how many, never what;
  stops and crashes; today's limits; promises; the journal's and life story's headings, never their sentences).
- **Search** looks through the log's kinds and fields, beliefs, the model of you, skills, plans, lab projects and every Brain
  setting.

Plain facts only: nothing named for money or health is shown (a belief or a row of the model of you that names either is left
out and counted), and the senses are counts. Off: `mind.console.on`.

**On the phone** (Android, with **Show on the phone** on, `calls.views`): the app's Views gets the same console as a **Brain** choice,
one column, a decision opening as a sheet. Your computer sends it only while you watch it (`calls.views_brain`, on by default;
nothing goes until you open it), sealed for your phone like Systems; with your computer asleep the last copy shows with "as of".
The phone's copy holds the newest 240 records and the evidence of the newest 25 decisions; older ones stay on your computer.

## Questions

**Does Brain make Kurooto do more on its own?** Not by default. The log only records. The parts that could act
(forecasts, autonomy, the read of how you're doing) start in shadow mode, where they watch and score themselves and change
nothing, and everything that reaches you goes through Brain's gate, which can only make it quieter. Each part has its own
switch (`mind.<part>.on`), and a few (precedents, play, the weekly fine-tune, message tone) stay off until you turn them on.

**Will it slow my computer down?** No. The scorekeeper is a small Python program that sits idle until a fact comes
in. Writing a record takes about a millisecond.

**`/mind` says the log doesn't check out.** Something changed the log outside Kurooto, or the disk damaged it. The
message names the first record that doesn't hold. If you didn't change it
yourself, turn Brain off, tap Delete, and turn it on again for a fresh log.
