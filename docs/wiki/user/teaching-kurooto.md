# Teaching Kurooto about you

Kurooto gets better at helping you in six ways, and you can see and change every one of them:

| What | What it keeps | Where | Goes along with |
|---|---|---|---|
| [About you](#about-you-your-profile) | a profile built from what your other AI accounts know about you | `about-me/profile.md` in your notes | every AI request (its **In brief** part only, up to 2,500 characters) |
| [Remember](#remember) | how you like to be helped, in your words | `about-me/how-to-help-me.md` in your notes | every AI request (a short version, up to 1,500 characters) |
| [Nightly look back](#nightly-look-back) | suggestions you approve: settings, lines for the note above, skill changes, ideas | your settings, that note, your skills, `kurooto/ideas.md` | |
| [Learns from its own work](#learns-from-its-own-work) (optional) | a search of past requests, calls and chats; skills from requests that took many steps; lessons from your corrections; facts you state | Kurooto's state folder (the search index); your skills; that note | requests that search it (the passages found) |
| [Wrong button and test cases](#wrong-button-and-test-cases) | requests it got wrong, and your words for things | Kurooto's state folder | instant requests on Telegram |
| [Call lessons](#call-lessons) | how calls could go better | Kurooto's state folder | every call |

Nothing changes without your say: the look back asks before every change, taught phrasings need your tap, and the
two notes are yours to edit (your edits win). The one exception is the optional **Learns from its own work**, which you
turn on by hand: it acts, tells you in one line each time, and every change has an Undo. Paths are the default notes layout's; in the zettelkasten layout the
`about-me/` notes are in `master/` and `kurooto/ideas.md` is `master/ideas.md`.

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

**From Telegram.** `/aboutme` shows the In-brief part and a link to the editor (it opens on your computer).

**What leaves your computer.** Building the profile sends the reports to the AI you picked. After that, the In-brief
part goes with every AI request. The reports stay in Kurooto's private data folder (not your notes, never synced):
remove anything you'd rather not keep before adding a report.

**Undo.** Edit or delete `about-me/profile.md`; delete its `## In brief` section to stop sending it.

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

**What leaves your computer.** The short version of the note goes to the AI you picked with every request.

**Turn it off.** Features → Remember. The note stays; while it exists, AI requests still read it. Delete the note to
stop that.

---

## Nightly look back

**What it does.** Once a day (23:50) the AI looks at how the day went and suggests at most three small improvements,
each with the evidence behind it. Nothing changes without your tap.

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

**Undo.** Every message has an **Undo** button, and `/learned` lists the last ten changes with theirs.
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
| `cases.keep_days` | `30` | cases you didn't make test cases are forgotten after this; test cases stay |
| `cases.review` | `weekly sun 19:00` | when the monthly list may come |
| `cases.review_days` | `28` | at most this often |
| `cases.review_max` | `5` | phrasings in one list |
| `cases.learn` | on | off keeps test cases without teaching anything |

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
| "Met Ortiz today, we agreed on the forcing runs" | adds a dated line under that project's Meetings |
| "I have a meeting with Ortiz on Friday at 4" | adds "Meeting: Prof Lena Ortiz" to your deadlines, so it's planned around and reminded |
| "Every Monday at 9 I have a linear algebra lab" | puts the class in your timetable (55 minutes unless you say the end; only for a subject you have) |
| "By POTA I mean Physics of the Atmosphere", "LA is short for linear algebra", "I call stochastic calculus stoch" | gives that subject the short name, so "POTA quiz friday" lands on it (only your subjects; never a name another one has) |
| "Every Tuesday and Thursday at 7pm I go to the gym", "I work a shift every weekend from 9 to 5" | adds it to your [commitments](classes-and-timetable.md#commitments-gym-shifts-standups) (an hour unless you say the end), so calls wait for it; turns Commitments on if it was off |

It only acts on what you say about yourself: "my friend got a project", "I didn't get it" or "maybe I'll ask" set
nothing up, and a line is looked at once even when it reaches both the chat and the journal. It works by rules on this
computer, with no AI. It never sets alarms, places calls, sends anything or attaches code (`/repos add` does that).

`/inferred` lists what was set up, newest first; `/inferred undo <id>` (or the Undo button) takes one back. Turn it off
with `infer.on`, or a part with `infer.projects`, `infer.meetings`, `infer.classes`, `infer.aliases`, `infer.commitments`.

## Dreaming

Turn on **Dreaming** (Features) and Kurooto's night comes to you as one message in the morning (`dreaming.when`, 07:30
by default) instead of several:

- **While you slept:** how much of your books was read into your notes (new concept notes, links), new books taken in,
  broken links tidied, handwritten notes linked, lessons the calls learned (`/lessons`), skills and facts learned
  (`/learned`), things set up from what you said (`/inferred`).
- **Loose ends:** your own open doubts from the last two weeks (the Doubts of your handwritten notes), notes nothing
  links to yet, links that point at notes that don't exist, tasks past due, AI requests that failed overnight.
- **The self-check** (`dreaming.self_check`, on): with Wrong button and test cases on, it replays your test cases and
  names any that went right yesterday but go wrong now (after an update or a settings change), and counts the requests
  it didn't understand and the Wrong taps since the last message (the Sunday look back shows them).

Nothing new runs for it: it reads Kurooto's own log and your notes, so it uses no AI and nothing leaves the computer.
A quiet night with no loose ends sends nothing. `/dream` shows the same any time. With it on, the concept graph's own
morning line comes inside it. `dreaming.loose_ends` = false leaves the loose ends out.
