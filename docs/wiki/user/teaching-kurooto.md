# Teaching Kurooto about you

Kurooto gets better at helping you in five ways, and you can see and change every one of them:

| What | What it keeps | Where | Goes along with |
|---|---|---|---|
| [About you](#about-you-your-profile) | a profile built from what your other AI accounts know about you | `about-me/profile.md` in your notes | every AI request (its **In brief** part only, up to 2,500 characters) |
| [Remember](#remember) | how you like to be helped, in your words | `about-me/how-to-help-me.md` in your notes | every AI request (a short version, up to 1,500 characters) |
| [Nightly look back](#nightly-look-back) | suggestions you approve: settings, lines for the note above, skill changes, ideas | your settings, that note, your skills, `kurooto/ideas.md` | |
| [Wrong button and test cases](#wrong-button-and-test-cases) | requests it got wrong, and your words for things | Kurooto's state folder | instant requests on Telegram |
| [Call lessons](#call-lessons) | how calls could go better | Kurooto's state folder | every call |

Nothing changes without your say: the look back asks before every change, taught phrasings need your tap, and the
two notes are yours to edit (your edits win). Paths are the default notes layout's; in the zettelkasten layout the
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
  back").

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
is told them. `/lessons` lists them; `/lessons forget 2` removes the second. Details are in [calls.md](calls.md).

---

## Messages these features send by themselves

Each has **Why?** and **Less of this** on Telegram ([messages-it-sends.md](messages-it-sends.md)).

| Message | Why it came | Less of this |
|---|---|---|
| "Suggestion: ..." with Apply / Observe longer / No | the nightly look back (`retro.when`) | Stop; Fewer makes it weekly |
| "What I found about ..." | a watch you or the look back started ended | (an answer to what you asked) |
| "Look back: phrasings that came up most..." | the monthly review of cases (`cases.review_days`) | Fewer makes it half as often |
| "What I fixed and learned looking back at a call" | the call look back (`calls.review`) | |

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
| "1 phrasing you taught no longer works" | The request it stood for changed or its feature is off. `/cases`: Unlearn it, then teach it again with `/wrong <words>`. |
