# Teaching Kurooto about you

Kurooto gets better at helping you in seven ways, and you can see and change every one of them:

| What | What it keeps | Where | Goes along with |
|---|---|---|---|
| [About you](#about-you-your-profile) | a profile built from what your other AI accounts know about you | `about-me/profile.md` in your notes | every AI request (its **In brief** part only, up to 2,500 characters) |
| [Your persona card](#your-persona-card) | what to call you, tone, length, things to avoid (empty to start) | Settings (`persona.*`) | every AI request and every call |
| [Remember](#remember) | how you like to be helped, in your words | `about-me/how-to-help-me.md` in your notes | every AI request (a short version, up to 1,500 characters) |
| [Nightly look back](#nightly-look-back) | suggestions you approve: settings, lines for the note above, skill changes, ideas, routines from your records; data fixes it is sure of, with Undo | your settings, that note, your skills, `kurooto/ideas.md`, your commitments, your deadlines | |
| [Learns from its own work](#learns-from-its-own-work) (optional) | a search of past requests, calls and chats; skills from requests that took many steps; lessons from your corrections; facts you state | Kurooto's state folder (the search index); your skills; that note | requests that search it (the passages found) |
| [Wrong button and test cases](#wrong-button-and-test-cases) | requests it got wrong, your words for things, the reading you picked | Kurooto's state folder | instant requests on Telegram |
| [Call lessons](#call-lessons) | how calls could go better | Kurooto's state folder | every call |

Nothing changes without your say: the look back asks before every change, taught phrasings need your tap, and the
two notes are yours to edit (your edits win). The one exception is the optional **Learns from its own work**, which you
turn on by hand: it acts, tells you in one line each time, and every change has an Undo. Paths are the default notes layout's; in the zettelkasten layout the
`about-me/` notes are in `master/` and `kurooto/ideas.md` is `master/ideas.md`.

Some times it also learns by rules alone, each told in one line with **Undo**: check-in times
([check-ins-and-journal.md](check-ins-and-journal.md)), Start-by's day window, and your quiet hours at night and the
morning things that follow them ([calls.md](calls.md#morning-alarm)). Settings you set yourself are never changed.

---

## About you (your profile)

**What it does.** Your other AI accounts (ChatGPT, Claude, Gemini, Copilot, Perplexity and the rest) already know a
lot about you: your projects, how you work, what you keep asking for help with. The setup page's **About you** step
brings that into Kurooto once, so it starts out knowing you.

**How to build it.**
1. Open the setup page (`kurooto open`, then setup; or the dashboard's **About you** tab, Alt+Y). Type which AI and
   account you're starting with (e.g. "ChatGPT personal") and copy a prompt: **Your main AI** (the fullest audit)
   for the account you use most, **Every other account** for all the rest.
2. Paste it into a **new chat** in that account. Turn on its memory or "search past chats" first if it has them: it
   can only report what it can see.
3. Do this in as many accounts as you can, including school, work and old ones. Each knows different things.
4. Each AI writes a long report and ends with a few questions. Answer them there if you like and ask it to update
   the report. Copy its whole answer (or download it as a file) and add it on the page: paste it, or upload several
   files at once. A report can be up to 2 million characters.
5. Press **Build my profile.** Your AI merges the reports into one profile. It's a big request: a free AI may hit a
   limit; try again later or with a stronger AI.
6. **Read it and fix anything that's off,** right there in the editor under the button.

**The editor.**

| Button | What it does |
|---|---|
| **Save** | saves your edits and keeps the previous version beside it (`profile-<date>.md`) |
| **Revert** | goes back to what's saved |
| **Preview In brief** | shows exactly what goes along with every AI request: the section under `## In brief` |

Without a `## In brief` heading (or with it empty), nothing from your profile goes along with your requests; Kurooto
warns you but saves. A profile can be up to 200,000 characters. You can also edit the file in your notes.

**Building again never replaces your edits silently.** If you changed the profile since it was built, **Build my
profile again** asks first; say yes and the new one replaces yours, with yours kept beside it as `profile-<date>.md`.
If you edit it while a new one is being built, yours stays and the new one goes beside it as
`profile-new-<date>.md`.

**What Dreaming adds.** With Dreaming on, the morning message can offer lasting things you said for your profile
("For your profile", see [Dreaming](#dreaming)); a line goes in only when you tap **Keep**, into Kurooto's own block
(`<!-- kurooto:learned -->`, at the end of the In-brief part), with where and when you said it. Those lines go along
with every request too. They don't count as your edits, building the profile again keeps them, and you can edit or
delete them like any line. With no profile yet, the first Keep starts one with just that block.

**From Telegram.** `/aboutme` shows the In-brief part and a link to the editor (it opens on your computer).

**What leaves your computer.** Building the profile sends the reports to the AI you picked. After that, the In-brief
part goes with every AI request. The reports stay in Kurooto's private data folder (not your notes, never synced):
remove anything you'd rather not keep before adding a report.

**Undo.** Edit or delete `about-me/profile.md`; delete its `## In brief` section to stop sending it.

---

## Your persona card

**What it does.** Four short lines on how Kurooto talks to you: **what to call you**, **tone**, **length** and
**things to avoid** ("plain and direct, no pep talk", "short unless I ask for detail", "emojis"). They go along with
every AI request and every call, so it words things the same way on Telegram, the phone app and calls.

**It starts empty.** No name, voice or tone is picked for you; empty means plain answers.

**Where to set it.** The dashboard's **About you** tab (Persona card, with a preview of exactly what's sent), Settings
→ persona, or Telegram:

| You send | What happens |
|---|---|
| `/persona` | shows the card |
| `/persona tone: plain, no pep talk` | sets one line (several lines in one message work: `call me: Sam` on the next) |
| `/persona clear tone` · `/persona clear` | clears one line, or the whole card |

The lines are `call me`, `tone`, `length` and `avoid`, up to 200 characters each.

**It sets wording only.** Kurooto has no feelings, backstory or life of its own, so a part of a line that asks for
one is left out, and you're told which: "Left out "say you missed me" (saying it missed you)". That covers feelings
("tell me you love talking to me", "I'm so happy to see you"), a backstory ("you grew up in Pune", "you're 23"), and
a relationship or being human ("be my girlfriend", "pretend you're human"). A tone like "friendly" or "dry humour"
is fine. The same rules apply to a card edited by hand in the settings file, and to `calls.persona`.

**What leaves your computer.** The card goes to the AI you picked with each request, and to your call line's voice
model with each call, like your profile's In brief.

**Undo.** `/persona clear`, or empty the lines on the About you tab.

---

## Remember

**What it does.** Tell Kurooto how you like to be helped and it keeps it. The line goes into
`about-me/how-to-help-me.md`, under "You told me", with the date. A short version of that note goes along with every
AI request Kurooto makes, next to your profile's In brief.

**Turn it on.** Features → Remember. It needs Telegram.

**From Telegram.**

| You send | What happens |
|---|---|
| `/remember I hate calls before 8` | "Noted in about-me/how-to-help-me.md: I hate calls before 8." |
| `remember that I like a plan before 9` · `keep in mind that I prefer short answers` · `remember: no emojis` | the same |
| `/remember` | what it keeps |

On a call: "remember that I study best in the morning" (the `remember` tool).

**Rules.**
- One line, under 300 characters. Longer things belong in your notes.
- **Health, money and password details are refused** ("I'd rather not keep that: health details would go along with
  every AI request"), because they'd travel with every request. Reword it if it isn't one.
- "Remember to buy milk" is a reminder, not this: it's left for [Reminders](reminders-and-deadlines.md) or your AI.
- A line it already has: "I know that already."
- The note is yours: read it, edit it, add your own lines. Kurooto never rewords or removes a line, and what you write
  there wins. The nightly look back adds lines only when you approve them (under "Learned in the nightly look
  back"), except the facts [Learns from its own work](#learns-from-its-own-work) picks up, if you turned it on (under
  "Picked up from your chats and calls", each with an Undo that takes only that line out again).

**Still true?** People change. A line Kurooto wrote (under "You told me", "Picked up from your chats and calls" or
"Learned in the nightly look back", with its date) that hasn't come up in 90 days (not in what you asked, said on a
call or told it again, and not kept with Keep) gets one quiet message: 'Still true? "I study topology on Sundays"',
with **Keep**, **Change** and **Forget**. At most two a week, three days apart.
- **Keep**: it stays, and isn't asked about for another 90 days.
- **Forget**: the line comes out of the note, with an **Undo** that puts it back.
- **Change**: reply with the new wording (or reply to the question itself); same rules as `/remember`, with an
  **Undo**. Replying "yes" keeps it, "no" forgets it.
- Lines you wrote yourself, or anywhere else in the note, are never asked about or touched. Editing a line counts as
  new. `remember.recheck_days` (90; 0 never asks); Less of this on the message works too.

**A time rule, as a setting too** (0.9.0, `remember.offer_settings`, on). When what you ask it to remember has a time
rule it can act on, it asks once whether to set that too, with **Set it** and **No**:
- "I hate calls before 8", "don't call me before 9am" → your night hours end then (`availability.night.to`);
- "no calls after 10 pm", "never call me after 11" → your night hours start then (`availability.night.from`);
- "I'm usually up from 8 to 11pm", "I work best between 9 and 6pm" → Start-by plans work in those hours
  (`startby.window`; set this way it counts as yours, so the weekly learning leaves it alone).

Nothing changes without the tap; each change it makes has an **Undo** (the same as Less of this). Off: the line is
only kept in the note, as before.

**What leaves your computer.** The short version of the note goes to the AI you picked with every request.

**Turn it off.** Features → Remember. The note stays; while it exists, AI requests still read it. Delete the note to
stop that.

## What it remembers, and when it uses it

Everything Kurooto remembers sits in one encrypted store on your computer, the memory ledger
([privacy.md](privacy.md#the-memory-ledger)): the gists of faded conversations, the threads you're in the middle of
([talking-to-kurooto.md](talking-to-kurooto.md#open-threads-and-that-thing)), the lines it keeps in your
how-to-help-me note, and what your daily notes and project meetings say. Your notes stay the source of truth; the
ledger reads them when they change.

- **`/memory`** lists it, **`/memory lab`** finds rows with those words, **`/memory forget 3`** forgets one (a
  how-to-help-me line comes out of the note too), **`/memory export`** writes the gists and threads to a note.
- **Ask it plainly:** "when did I last talk to Prof Ortiz?", "what was I doing last Thursday?".
- **What an answer is told.** Only when your message refers to past things or to something you're in the middle of,
  your AI gets the few items it's about, at most about 600 tokens (`memory.budget_tokens`), each saying where it's
  from ("call at 07:56 today"), never a transcript. The grey line under the answer counts them ("used 2 remembered
  items"). Calls get your open threads and the last day's gists in their brief, so a call can pick up what you said in
  a chat. `memory.recall` off: none of it goes.
- **Nothing it isn't told.** It never guesses how you feel or keeps health, money or password details; a thread found
  from "that thing" is only read or asked about, never acted on without your OK.

---

## Nightly look back

**What it does.** Once a day (23:50) the AI looks at how the day went and suggests at most three small improvements,
each with the evidence behind it. Nothing changes without your tap, except data fixes it is sure of (below), which
it makes and tells you with **Undo**.

**Before the AI, by rules on this computer:**
- **Routines it sees in your records.** The same thing at the same time of the week on 3 or more different weeks (in
  the last six): a study session for one course, or calls held with `/hold`. If it isn't a commitment or a class
  yet, one message a night: "From your records: you started studying Linear Algebra around Tue 18:00 on 3 different
  weeks. Add it as a routine (study linear algebra, Tue 18:00–19:30), so calls wait then?" with **Add** / **No**.
  **Add** makes it one of your [commitments](classes-and-timetable.md#commitments-gym-shifts-standups) (how long it
  usually took, else an hour; Commitments is turned on if it was off). **No** keeps it away for 30 days.
- **Data fixes it is sure of**, made at once with one line and **Undo**: two copies of one deadline (Classroom's and
  the one you said, or yours moved onto Classroom's day) become one, when they're due the same day, from different
  places, for the same course, with the same words and numbers. The one kept is the one Classroom (or your notes)
  brings back; it takes the other's time if it only had "end of the day", and the copy's buttons still work.
  "Problem set 3" and "Problem set 3 prep" are left alone. Anything that sends, an alarm or a call still waits for
  your tap.

**Turn it on.** Features → Nightly look back. It needs Telegram and Chat.

**What it reads.**
- what happened: the questions Kurooto asked you and your answers (how fast, on which channel), check-ins you moved or
  skipped, calls answered or missed, after-class prompts, deadlines, AI requests, study sessions, quizzes, focus;
- today's call transcripts and journal note (each can be left out: `retro.transcripts`, `retro.journal`);
- your how-to-help-me note and the settings it may change.

**What it can suggest.**

| Kind | Example | Apply does |
|---|---|---|
| a setting | a better evening check-in time; night hours; deadline nudges (`deadlines.ping_h`, `urgent_h`); quiz length; the after-class delay | changes that one setting (shown as `key: old -> new`) |
| a line for your how-to-help-me note | "Prefers a plan before 9" | adds it under "Learned in the nightly look back" |
| something to watch | "whether you study better before noon" (7 days) | starts watching it |
| a change to one of your skills | "the journal skill should ask fewer questions" | the AI writes the change; you see the lines removed and added, with **Save** / **Discard**. Saving writes your own copy in `kurooto/skills/<name>/SKILL.md` and keeps the old one in Kurooto's backups. If you edited the skill meanwhile, nothing is saved |
| an idea | something new Kurooto could do for you | adds `- [ ] the idea (date)` to `kurooto/ideas.md` |

**Answering.** Each suggestion comes as a question with **Apply**, **Observe longer** and **No** (and **Later**). Tap a
button, reply ("yes", "observe 14", "no"), or answer on your next call.
- **Apply** does it at once.
- **Observe longer** watches it for a week first (reply "observe 14" for 14 days, up to 60); when the watching ends,
  the next look back tells you what it found.
- **No** drops that idea, however it's worded next time, for 30 days.
- **Later** keeps it for your next call. Unanswered suggestions stay open for three days.

**Steer it.**

| You send | What happens |
|---|---|
| `/observe whether I study better before noon for 2 weeks` | watches it (default 7 days, up to a year) |
| `observe whether I sleep better after evening walks` · `keep an eye on how often I skip the gym` | the same |
| `/observing` | what's being watched, each with **Stop** and **+7 days** |
| `/lookback` | the last look back: when, how many suggestions and findings, and what it noticed |
| `/lookback now` | runs one now; suggestions come in a few minutes |

On a call: "keep an eye on whether I study better before noon". When a watch ends you get "What I found about ..."
with the finding (or that there wasn't enough to go on).

**Settings that matter** (Dashboard → Settings → Nightly look back):

| Setting | Default | Effect |
|---|---|---|
| `retro.when` | `daily 23:50` | when it runs; `weekly sun 21:00` looks back over the whole week |
| `retro.max_proposals` | `3` | the most suggestions per look back |
| `retro.observe_days` | `7` | how long Observe longer and `/observe` watch by default |
| `retro.no_days` | `30` | how long a No keeps an idea away |
| `retro.transcripts` | on | read today's call transcripts |
| `retro.journal` | on | read today's journal |
| `retro.routines` | on | ask about a routine it sees in your records |
| `retro.routine_weeks` | `3` | on how many different weeks the same thing has to happen |
| `retro.fixes` | on | make data fixes it is sure of (two copies of one deadline), with Undo |

How it thinks is the `retro` skill: put your own copy in `kurooto/skills/retro/SKILL.md` to change it (it isn't a
command).

**Limits and edge cases.**
- On a laptop it waits for the charger (battery saver), and past 70% of a known free AI limit it waits for the
  limit to reset ([ai-brains.md](ai-brains.md)). Most days the right answer is no suggestion at all.
- A skill change that's identical, or that broke the skill's header, isn't saved ("nothing changed").

**What leaves your computer.** Once a day, the day's events, your answers, today's transcripts and journal (unless
turned off), your how-to-help-me note and the settings it may change go to the AI you picked.

**Turn it off.** Features → Nightly look back. Waiting suggestions stay answerable for three days.

---

## Learns from its own work

**What it does.** Kurooto keeps what its own finished work teaches it, in four parts, each with its own switch. It
doesn't ask first: it acts and tells you in one line, with an **Undo** button. (The idea comes from Hermes Agent, by
Nous Research; none of its code is used.)

| Part | What happens | Setting |
|---|---|---|
| Search its memory | a search index of your past AI requests and their answers, call transcripts and chats, on this computer. `/history <words>` searches it, and the AI can too (the `search_history` tool) when you say "like last week" or "what did I ask about ..." | `learning.search` |
| Skills from experience | after a request that went well and took 5 or more steps (tool uses), the AI looks at how it was done. A procedure you're likely to want again becomes a skill in your skills folder ("Learned a skill: /weekly-lab-report, from today's request"), or, when a skill already does it, a few tips added to that skill under "Learned from experience". Never a second skill for the same thing | `learning.skills`, `learning.skill_min_steps` |
| Skills learn from corrections | correct a skill's answer (reply to it with what was wrong, or send "no, ...", "that's wrong", "next time ..." within two hours of it) and the skill gets a line under "## Lessons" ("Lesson for /journal: Put the date in the title"); rarely, the step that went wrong is rewritten instead | `learning.corrections` |
| Worth remembering | the nightly look back also picks out up to 3 lasting facts or preferences you stated in the day's chats and calls ("I'm a morning person") and adds them to your how-to-help-me note, under "Picked up from your chats and calls" | `learning.remember`, `learning.remember_max` |

**Turn it on.** Features → Add-ons → Learns from its own work (it's in no preset). It needs Chat. Learned skills and
lessons need [Skills](skills-and-routines.md) on; picking up facts needs the [Nightly look back](#nightly-look-back)
on. The card on the Features page has a switch for each part.

**From Telegram.**

| You send | What happens |
|---|---|
| `/history lab report` | the best matches among past requests, calls and chats: when, what kind, the title and the passage |
| `/history 7d linear algebra` | only the last 7 days |
| `/learned` | what it learned lately (skills, tips, lessons, facts), each with **Undo** |

**Undo.** Every message has an **Undo** button, and `/learned` lists the last ten changes with theirs. With Brain on,
the same `/learned` also lists Brain's tested skills after them (0.9.0: before, whichever feature came first answered
and the other list couldn't be reached).
- A new skill is removed. Tips or a lesson are taken out again: the skill file goes back to how it was (a copy of it is
  kept in Kurooto's state folder, `learning/before/`). For a skill that comes with Kurooto, the change was made in your
  own copy (`kurooto/skills/<name>/SKILL.md`), and Undo removes that copy.
- If you edited the skill since, Undo leaves it alone and says where the earlier version is.
- A fact is taken out of your how-to-help-me note, unless you changed that line.

**Rules it keeps.**
- Only your own requests are looked at, not background work (digests, routines, the concept graph). At most five a
  day are looked at as possible skills.
- A learned skill's file says so in its header: `learned: true`, the request it came from (`learned_from`) and the
  date (`learned_on`). Edit or delete it like any of your skills.
- Facts follow [Remember](#remember)'s rules: one short line, never health, money or password details, and never
  anything about other people (a line about your sister, a phone number or an email address is left out).
- A reply that only answers a skill's question ("week 3") isn't a correction.

**What leaves your computer.** The search index is built and kept on this computer. When the AI searches it during a
request, the passages it finds go to that AI with the request. Learning a skill sends the finished request, its answer
and the steps it took to the AI that takes second looks (`learning.brain`; by default the concept graph's second-look
AI, else your main one); a lesson sends your correction and the skill. Picking up facts sends the day's requests to
the AI the nightly look back uses.

**Turn it off.** Features → Learns from its own work, or one part on its card. Learned skills, lessons and facts stay
where they are (they're yours now); the search index stays in the state folder until the Space keeper trims it (it
forgets what's older than `space.jobs_days`, 60 days, like finished requests).

---

## Wrong button and test cases

**What it does.** When Kurooto gets a plain-English request wrong, you tell it, and it keeps the request as a
**case**. Reviewed cases become **test cases**, and they can teach Kurooto your own words for things ("whats on my
plate" taken as "what's due").

**Turn it on.** Features → Wrong button and test cases. It needs Telegram.

**Telling it.**
- Tap **Wrong** under a reply to a plain-English request (or under the AI's answer to one), or send `/wrong` right
  after it. The case keeps what you wrote, what Kurooto did with it, the time and the settings that decided it.
- Short requests no instant request understood (they went to the AI, or nowhere with Chat off) are kept as cases
  too, so you see what Kurooto keeps missing.
- Never kept: messages over 120 characters, several requests in one, and anything about health, money or passwords.

**Teaching it your words.**
- **At once:** `/wrong what's due` right after the reply: "what you meant" in words Kurooto already understands.
  `/wrong ai` says the AI was the right place for it.
- **Once a month** (a Sunday evening): the look back lists the phrasings that came up most (up to 5), each with
  **Make it a test case**. Tap it, then reply with what you meant, or tap **The AI**.
- **By itself, when you say it again in other words** (`cases.learn_rephrased`, on): "whats on my plate" goes to the
  AI, and within 3 minutes you write "what's due this week". The second time that same phrasing is followed by the
  same request, it's learned, under the same two rules below: "You said "whats on my plate" and then "what's due this
  week" 2 times, so: Learned: ...", with **Undo**.

<a id="two-readings"></a>**Two readings.** When no instant request takes a short message but two of them are about
equally close to it ("whats my plan" between "what's my plan today" and "what's my day plan"), Kurooto asks with both
as buttons instead of guessing (see [talking-to-kurooto.md](talking-to-kurooto.md#what-happens-to-a-message)). Tap
one and it runs. The second time you pick the same request for the same words, they're learned, under the same two
rules below: "You picked "what's my day plan" for "whats my plan" 2 times, so: Learned: ...", with **Undo**. A
phrasing that's a test case already is taken as it says, without asking. Needs this feature on to learn; the question
itself works either way (`repair.on`).

From then on that phrasing is taken as the request you named, at once, with today's time ("skip gym tmrw" taught as
"skip gym tomorrow" always means the day after you say it). A taught phrasing is matched whole (capitals and
punctuation aside) and goes before the usual patterns.

**Two rules keep this safe.**
- A phrasing is learned only if every test case that passed before still passes with it. Otherwise: "Saved as a test
  case, but not learned", and which case it would break.
- Requests that send, delete, call, ring or approve anything are never learned this way (calls, holds on calls,
  quizzes by call, the alarm, an add-on's "send" or "delete"). They keep needing their usual words; the test case is
  still kept.

**From Telegram.**

| You send | What happens |
|---|---|
| `/wrong` | keeps your last request as a case |
| `/wrong <what you meant>` | keeps it and teaches the phrasing |
| `/wrong ai` | keeps it; the AI was right to take it |
| `/cases` | how many test cases pass, fail or belong to features that are off; how many wait for review; the phrasings you taught, each with **Unlearn** |
| `/cases review` | the monthly list now |

**From a terminal.**

| Command | What it does |
|---|---|
| `kurooto cases` | lists the cases and taught phrasings |
| `kurooto cases check` | runs the test cases here |
| `kurooto cases export` | writes them as a test file, `test_kurooto_cases.py` (`--out FILE`; `--all` adds cases not reviewed yet). It holds what you typed: read it before sharing it |
| `kurooto cases forget <id>` · `kurooto cases forget all` | deletes cases and taught phrasings |

**Settings that matter** (Dashboard → Settings → Wrong button and test cases):

| Setting | Default | Effect |
|---|---|---|
| `cases.button` | on | the Wrong button (`/wrong` works either way) |
| `cases.fallthroughs` | on | keep short requests nothing understood |
| `cases.keep_days` | `0` | cases you didn't make test cases are forgotten after this many days (0: `privacy.keep_days` when set, else 30); test cases stay |
| `cases.review` | `weekly sun 19:00` | when the monthly list may come |
| `cases.review_days` | `28` | at most this often |
| `cases.review_max` | `5` | phrasings in one list |
| `cases.learn` | on | off keeps test cases without teaching anything |
| `cases.learn_rephrased` | on | learn a phrasing you twice said again in other words within 3 minutes |
| `repair.on` | on | ask with both readings as buttons when two requests are about equally close |

**Limits.** At most 500 cases and 200 taught phrasings. If a taught phrasing stops working (its feature changed or
went off), it goes to the AI as before, and `/health` (and `kurooto doctor`) says so.

**What leaves your computer.** Nothing. Cases are in Kurooto's state folder (`cases/`), never in Backups, Profile sync
or the diagnostics zip.

**Turn it off.** Features → Wrong button and test cases: the button goes and taught phrasings stop at once. Unlearn one
phrasing in `/cases`; `kurooto cases forget all` deletes everything.

---

## Call lessons

After every call, Kurooto looks back at the transcript with a stronger AI: it does what was asked but slipped through
(a reminder misheard, a note forgotten, a tool that failed) and writes down lessons for later calls. Every later call
is told them. `/lessons` lists them; `/lessons forget 2` removes the second, `/lessons clear` all of them. Details are
in [calls.md](calls.md).

---

## Messages these features send by themselves

Each has **Why?** and **Less of this** on Telegram ([messages-it-sends.md](messages-it-sends.md)).

| Message | Why it came | Less of this |
|---|---|---|
| "Suggestion: ..." with Apply / Observe longer / No | the nightly look back (`retro.when`) | Stop; Fewer makes it weekly |
| "What I found about ..." | a watch you or the look back started ended | (an answer to what you asked) |
| "Look back: phrasings that came up most..." | the monthly review of cases (`cases.review_days`) | Fewer makes it half as often |
| "You picked ... for ... 2 times, so: Learned ..." with Undo | the same reading picked twice (`cases.learn`) | |
| "What I fixed and learned looking back at a call" | the call look back (`calls.review`) | |
| "Learned a skill: /..." or "Improved a skill: /..." with Undo | Learns from its own work (`learning.skills`) | Stop; Fewer makes it one a day |
| "Lesson for /...: ..." with Undo | a correction of a skill's answer (`learning.corrections`) | Stop |
| "Kept from today's chats and calls ..." with Undo | the nightly look back with Learns from its own work (`learning.remember`) | Stop |

---

## When something goes wrong

| What you see | What to do |
|---|---|
| Building my profile failed | It's a big request: if your AI hit a limit, try later or with a stronger AI (Settings → `brain.main`). |
| "There's no ## In brief section" | Add a `## In brief` heading with a few lines about you, or nothing from the profile goes with requests. |
| "I'd rather not keep that" after /remember | It looked like a health, money or password detail. Put it in your own notes instead; reword it if it isn't one. |
| The look back never suggests anything | Most days that's right. `/lookback` shows when it last ran; on a laptop it waits for the charger. `/lookback now` runs one. |
| A skill change says "nothing changed" | The AI's version was the same, or it broke the skill's header. It may suggest it again another night. |
| "Saved as a test case, but not learned" | Teaching that phrasing would break another test case (the message says which), or it's a request that sends, calls or deletes. |
| A learned skill or lesson isn't what you wanted | Tap its **Undo** (or `/learned`). Turn that part off on the card if it keeps happening. |
| `/history` finds nothing you know you asked | Only your own requests that ended well are kept, and only for 60 days (`space.jobs_days`). Searching by a word from the answer works too. |
| "1 phrasing you taught no longer works" | The request it stood for changed or its feature is off. `/cases`: Unlearn it, then teach it again with `/wrong <words>`. |

## Set up from what you say

You don't need a settings page for the facts of your work: say them, in the chat or in your journal, and Kurooto sets
up what they imply, then tells you in one line with an Undo button.

| You say | Kurooto |
| --- | --- |
| "I got a project under Prof Lena Ortiz on glacier flow" | starts the project note *Glacier flow* with "With: Prof Lena Ortiz (supervisor)" and a Meetings section (it's listed on your research hub) |
| "I'm doing my thesis under Prof Ana Ruiz", "I started working with Prof Cole on a project about sea ice", "My supervisor is Dr Ken Ito" | the same: *Thesis with Prof Ana Ruiz*, *Sea ice* with Prof Cole, *Project with Dr Ken Ito* (a thesis or dissertation counts as a project; "my supervisor/guide/advisor/mentor is ..." starts one named after them) |
| "Met Ortiz today, we agreed on the forcing runs" | adds a dated line under that project's Meetings, and sets "Last met: <date>" in Kurooto's block under the "With:" line |
| "I have a meeting with Ortiz on Friday at 4" | adds "Meeting: Prof Lena Ortiz" to your deadlines, so it's planned around and reminded; the evening before (`deadlines.meeting_brief`, 20:00) a **meeting brief** comes: what the project's Log has since you last met, its open "## Next steps" (`- [ ]` lines), the last meeting's line and the last minutes |
| "I meet my manager Mira Castell every Monday at 10 about onboarding" | a weekly meeting with anyone (guide, manager, coach: your word): "With: Mira Castell (manager)" and "Meets: every Mon 10:00" in the project note *Onboarding*; a brief the evening before each one, and notes you send after it become minutes with action items ([Research → Meetings](research.md#meetings-with-someone-briefs-minutes-and-action-items)) |
| "Every Monday at 9 I have a linear algebra lab" | puts the class in your timetable (55 minutes unless you say the end; only for a subject you have) |
| "By POTA I mean Physics of the Atmosphere", "LA is short for linear algebra", "I call stochastic calculus stoch" | gives that subject the short name, so "POTA quiz friday" lands on it (only your subjects; never a name another one has) |
| "Every Tuesday and Thursday at 7pm I go to the gym", "I work a shift every weekend from 9 to 5", "gym Tue Thu 7am" | adds it to your [commitments](classes-and-timetable.md#commitments-gym-shifts-standups) (an hour unless you say the end), so calls wait for it; turns Commitments on if it was off. The short way needs two days or more (or "every", or "on Tuesdays") and a clock time like `7am` or `19:00`: "dentist Tue 7am" is a one-off, so nothing is set up |
| "I have lab every Thursday 2-5" (no course named) | adds "lab" to your commitments, Thu 14:00–17:00, and says how to make it a class instead (`/class thu 14:00-17:00 <course>`) |
| "I've got a lab on Mondays at 9", "I go running every morning at 6" | "on Mondays" counts as every Monday and "I've got" as "I have"; "go running" is a commitment too (every day). A meeting or a call with someone ("a weekly call with Jun on Fridays") is never a commitment: it's a meeting, and only with someone a project is With |
| "There's a quiz on Linear Algebra every Monday at 10", "LA has a test every other Friday from 2026-10-30" | adds the row to your [recurring quizzes](reminders-and-deadlines.md) table, so each one becomes a deadline. Only when the course, the day and (every other week) a date are all said; a message that is only that request ("la has a quiz every thursday") is answered by the request itself, which asks for what's missing |
| "LA problem set" in one message and "LA notes" in another, when Linear Algebra is the only subject whose initials are LA | takes "LA" as Linear Algebra's short name ("you've called it that twice"). Only names written in capitals, two messages within 60 days, and never one that fits two subjects or is a common word (OK, PM, PDF) |

It only acts on what you say about yourself: "my friend got a project", "I didn't get it" or "maybe I'll ask" set
nothing up, and a line is looked at once even when it reaches both the chat and the journal. A question sets up
nothing, with or without its question mark: "do I have lab every Thursday", "is there a quiz every Monday". It works by rules on this
computer (the one pass below can ask an AI about a line the rules can't read). It never sets alarms, places calls,
sends anything or attaches code (`/repos add` does that).

**The one pass** (`infer.sweep`, on). Besides what you send, Kurooto reads what never came as a message: your chats
with it and your journal and daily notes as they are in your notes folder (your lines, not its own blocks). It does
that once a few minutes after it's first on, over the last 30 days (`infer.sweep_days`), and then each night at 04:20
over what's new. The rules come first. A line they can't read but that looks like one of the cases above ("Prof Lena
Ortiz said yes, so I'm on her glacier team now as my project") gets one more try with `infer.sweep_ai`: `local` (the
default) asks the model on this computer, when there is one, to restate it in one of the forms in the table, and the
rules read that; a restatement that brings in a name, day or number your line doesn't have is dropped. `main` asks your
own AI instead (only that line goes to it); `off` leaves it to the rules. What one pass sets up comes in one line:

```
Set up 2 things from your recent chats and journal (1 project, 1 class). /inferred shows each, with its Undo.
```

with **Undo all**. `/inferred scan` runs it now.

`/inferred` lists what was set up, newest first, including the pieces of a project you set up from its repository
([`/project add`](research.md#set-up-a-project-from-a-repository)); `/inferred undo <id>` (or the Undo button) takes
one back. Turn it off
with `infer.on`, or a part with `infer.projects`, `infer.meetings`, `infer.classes`, `infer.aliases`, `infer.commitments`,
`infer.quizzes`, `infer.short_names`; `infer.sweep` = false stops only the pass.

## Dreaming

Turn on **Dreaming** (Features) and Kurooto's night comes to you as one message in the morning (`dreaming.when`, 07:30
by default, or half an hour after you're usually up once that's learned, [calls.md](calls.md#morning-alarm)) instead
of several. The day after an exam or a heavy day it starts with one line saying the day will be lighter, with
**Not today**:

- **While you slept:** how much of your books was read into your notes (new concept notes, links), new books taken in,
  broken links tidied, handwritten notes linked, lessons the calls learned (`/lessons`), skills and facts learned
  (`/learned`), things set up from what you said (`/inferred`).
- **Loose ends:** your own open doubts from the last two weeks (the Doubts of your handwritten notes), notes nothing
  links to yet, links that point at notes that don't exist, tasks past due, AI requests that failed overnight.
- **The self-check** (`dreaming.self_check`, on): with Wrong button and test cases on, it replays your test cases and
  names any that went right yesterday but go wrong now (after an update or a settings change), and counts the requests
  it didn't understand and the Wrong taps since the last message (the Sunday look back shows them).
- **Tuning its own messages** (`dreaming.tune_messages`, on): it replays the messages it sent you by itself (the last
  45 days) under a few variants of when they come, and when one clearly beats things as they are, it makes that one
  change, with **Undo**: "Learned while you slept: questions about quiet projects wait for your evening bundle once 2
  in a row go unanswered; over the last 14 days that would have saved 8 ignored pings and delayed none you answered."
  One change a night at most, never to what always comes or what you set yourself.
  [Messages it sends](messages-it-sends.md#calm-why-less-of-this-and-the-daily-limit) has the details; `/dream policy`
  shows the rules and the last decisions.
- **Tuning the rest** (Dream RSI, part three): the same nightly replay on three more of its decisions, each with its
  own switch, all on:
  - **effort** (`dreaming.tune_effort`): how hard the AI thinks about your requests, per what picked it (the quick
    check's low, medium or high, or the study-from-notes rule). It counts your requests of the last 45 days that you
    asked again within 15 minutes, marked **Wrong**, followed with "that's not what I asked" (or "you misunderstood",
    "no, I meant ..."), or that ran out of time, and how long they took. One step at a time; a level you type
    ("high: ...") is never changed;
  - **which AI goes first** (`dreaming.tune_fallbacks`): with a fallback AI set, at an effort level where your main AI
    keeps hitting limits or timing out, the fallback is tried first (`brain.fallback_first`);
  - **Start-by sizes** (`dreaming.tune_sizing`): how long each kind of deadline takes (`startby.sizes`), from the study
    time on its subject between its start-by date and when you marked it done, "4/7" progress, and sizes you tapped.
    A size you set yourself is never changed.

  Today's rules are always among what it compares, and it changes something only when the replay clearly wins
  (`dreaming.tune_margin`). Still one change a night across everything (messages included), said in the morning
  message with **Undo**: "Learned while you slept: Start-by sizes a report at about 5 h (a day), not 12 h; the last 4
  took about 5 h (4 from study time)."
- **It improves the way it improves:** every change's outcome is kept. A kind of change you undid needs a clearer win
  next time (up to four times the margin), one you kept earns some of that back, and what you undid is left alone for
  30 days. `/dream policy` shows all of it.
- **Proposed fixes to skills** (`dreaming.propose_prompts`, off): when a skill's answers were corrected, marked Wrong or
  asked again twice or more in two weeks, the night asks Learning's second-look AI for the skill with the failing step
  rewritten. If, by that AI's replay, it fixes at least half of those cases, the morning message offers it as a
  [proposal](proposals.md) with **Apply**, **Change** and **Discard** (`/dream proposal` shows it whole, `/proposals`
  as a diff). Nothing changes without your tap; Apply replays your test cases and puts the skill back at once if one
  that passed goes wrong; Undo in `/learned`. Change has the AI rework it in a scratch folder; Discard leaves that
  skill alone for 30 days.
- **Curious** (`dreaming.curious`, on): a topic you asked about 3 or more times this week (your requests to the AI,
  what calls searched your notes for, quiz questions you got wrong) with no note on it, or only a stub, gets one line:
  "You've asked about the Fokker–Planck equation 3 times this week and there's no note on it. Want one?" **Make a
  stub** writes a short concept note in that subject's folder (where your notes layout puts concept notes) and links
  it from the course page under "Concepts"; **Not interested** puts the topic on your not-interested list (`/unignore`
  takes it back). It's careful about what counts as a topic: the name of one of your concept notes, or a phrase that
  ends in a word like equation, lemma, theorem or distribution ("Itô's lemma"), or a pair of names ("Navier–Stokes").
- **From the past** (`dreaming.resurface`, on): one line about a note you last changed 10 to 30 days ago, or a subject
  you last practised in a quiz then ("You last worked on Itô's lemma 12 days ago"; one with an exam in the next two
  weeks first), or an anniversary ("A month ago today you started work on L96": a project's first Log line, or a
  repository's first commit). **Open it** opens the note on your computer (**Practise** starts a quiz); **Less of
  this** turns these lines off, with Undo.

  Each comes at most once a day, and the same topic or note not again for 30 days.
- **Worth a look in what I remember** (`dreaming.consolidate`, on): each night (04:45) it looks for the same thing
  remembered twice and for lines that disagree, and lists a few (`dreaming.consolidate_max`, 3) as one short section:

  ```
  Worth a look in what I remember (nothing changes until you tap):
  1. These disagree (different dates): A "Stats quiz 3 postponed, due 02 Nov now" (journal/2026-10-22.md, Thu 22 Oct);
     B "Statistics: Stats quiz 3, due Fri 30 Oct" (your deadlines).
  2. The same thing twice: A "No calls before 8" (about-me/how-to-help-me.md, 12 Oct); B "Don't call me before
     8am" (about-me/how-to-help-me.md, 20 Oct).
  ```

  Each has **Keep A**, **Keep B** and **Both true** (**Keep both** for a duplicate). What's compared: gists (two of
  the same kind from the same day that say the same thing), the lines Kurooto keeps in your how-to-help-me note, your
  daily notes and project meetings from the last 30 days, your open deadlines, and, with the notes brain on, its
  contradictions report. Two lines disagree when they're about the same thing (the same key words, the same "Quiz 3")
  and give a different date, weekday, time or number ("Quiz 3 is due Fri" and "Quiz 3 is due Mon"); a line that only
  says when you did something ("studied for quiz 3 on Thursday") doesn't count.

  Nothing changes until you tap. Keeping one side takes the other out of your how-to-help-me note (a line Kurooto
  wrote), drops the other gist, or moves the deadline to the date your note says; a line in your own notes is never
  changed: Kurooto says which note it's in, for you to change. Every change has **Undo**. **Both true** keeps both and
  the pair isn't asked about again; one shown on two mornings without a tap is let go. `/dream check` looks now.

  It's rules first. A pair that's close but not clear can get a second opinion (`dreaming.consolidate_ai`): `local`
  (the default) asks the model on this computer when Local AI models has one, `main` asks your own AI (only
  how-to-help-me lines and note lines go to it, never a gist), `off` asks nobody; at most 8 a night.
- **For your profile** (`dreaming.fold`, on): each night (04:50) it reads what you said since the last time (your
  chats with Kurooto, your lines on calls, the AI requests you made, your journal and daily notes) for lines that say
  something lasting about you or how you like to be helped, and offers a few (`dreaming.fold_max`, 3):

  ```
  For your profile (what you said that seems to last; nothing is written until you tap Keep):
  1. "I'm a second-year geology student" (a chat, 23 Oct) → your profile
  2. "Please don't call me before 9" (a call, 23 Oct) → how to help you
  ```

  Each has **Keep** and **Not that**. Keep adds it, in your words with where it came from ("- Please don't call me
  before 9 (from a call, 2026-10-23)"): a fact about you into Kurooto's block of your profile, how to help you into
  your how-to-help-me note; both go along with every AI request. Each Keep has **Undo** (the line comes out and is
  offered again). Not that drops it for good; a line shown on two mornings without a tap is let go. It only picks
  lines in the first person that state something (not a question, not "maybe" or "if", not only about today), not
  already in your profile or note, and never about anyone else (a "he", "she", "my friend" or a phone number, so a
  message you forwarded isn't learned from), health, money or passwords. With `dreaming.fold_ai` = `local` (the
  default) the model on this computer, when there is one, takes a second look and drops what isn't lasting; `main`
  asks your AI (only those lines go to it); `off` leaves it to the rules. `/dream fold` looks now.
  **What it set up** (0.9.0, `dreaming.fold_inferred`, on): the projects and classes it set up from what you said
  (`/inferred`) are offered too, in its own words, with a role and never a name ("I have a project with my supervisor
  on glacier flow", "I have a weekly Linear Algebra lab (Mon 09:00)"), marked "what it set up from what you said". They
  have a cap of their own (`dreaming.fold_inferred_max`, 1 a morning), so they never take one of your own lines' places.

Apart from that second opinion, nothing new runs for it: it reads Kurooto's own log, its memory and your notes, so it
uses no AI and nothing leaves the computer.
A quiet night with no loose ends sends nothing. `/dream` shows the same any time. With it on, the concept graph's own
morning line comes inside it. `dreaming.loose_ends` = false leaves the loose ends out (the curious and past lines have
their own settings). What calls searched your notes for is kept 8 days at most, and `/forget` clears it.
