# Skills and routines

A **skill** is a ready-made set of instructions for your AI, run with one command: `/journal my day` saves your day
into today's note, `/pack linear algebra midterm` builds a revision PDF. A **routine** runs a skill, a command or a
request on a schedule (`/every monday 9:00 /journal plan my week`). You can write your own skills, copy and change
the ones Kurooto ships, and use them in other AI programs too.

- [Turn it on](#turn-it-on)
- [Running a skill](#running-a-skill)
- [The skills that come with Kurooto](#the-skills-that-come-with-kurooto)
- [Revision packs (/pack)](#revision-packs-pack)
- [Listing and changing skills](#listing-and-changing-skills)
- [Your own skills (/newskill)](#your-own-skills-newskill)
- [Prompts that are skills](#prompts-that-are-skills)
- [Routines (/every)](#routines-every)
- [The rules every skill follows](#the-rules-every-skill-follows)
- [Sending you files](#sending-you-files)
- [Skills in agy, Claude Code and other agent programs](#skills-in-agy-claude-code-and-other-agent-programs)
- [Settings, privacy, turning it off](#settings-privacy-turning-it-off)

---

## Turn it on

Dashboard → Features → **Skills**. It needs **Chat** (skills are requests to the AI you picked). With Skills off,
typing `/journal` says "Skills is off: Features → Skills → Turn on" instead of sending it to the AI.

---

## Running a skill

**From Telegram.** Type `/<skill>` and what it's about, in one message:

```
/journal finished the problem set, stuck on question 4, read two papers for the reading group
```

- **Files go along**: send photos, PDFs or slides with the command as the caption (`/study-log` with your slides).
- **The answer comes back as a reply.** Answers longer than 7,000 characters come as the first part plus the full
  answer as a file.
- **Reply to the answer to carry on**: answer the questions it asked, or ask for a change ("make the plan lighter
  after 4pm"). Your reply runs the same skill again, with its previous answer attached.
- **Line breaks are fine**: `/journal` on the first line and your text below it works.
- **The "/" menu** lists your skills. Telegram's menu can't show a dash, so a skill with one shows with `_`:
  `/term_setup` runs term-setup, `/study_log` runs study-log. Both spellings work when typed.
- A **command of the same name wins**: a skill can't take a name a feature's command already uses (`/pack`, `/note`,
  `/quiz`...). `/skills <name>` says when that's the case.

**Effort.** Each skill says how hard the AI should think (low, medium or high), so a quick `/goodnight` stays quick
and `/assignment` gets the strongest model.

**What you get back.** "On it." at once, then the answer as a reply, labelled with the AI and effort that answered,
e.g. `[Gemini key · medium] /journal finished the problem set`.

---

## The skills that come with Kurooto

You type these:

| Skill | What it does | What to type after it |
|---|---|---|
| `/journal` | Saves your words, verbatim, in today's daily note under `## Journal (HH:MM)`; links the notes you mention (each with a reason); adds a line to a project's log if you worked on one; files new ideas in `inbox/`; ticks tasks you finished and adds new ones (with a due date they reach Deadlines). Name a date to journal another day. | your day, in your own words |
| `/study-log` | One lecture note per class (`<subject>/<date>-<topic>.md`) from your slides and notes, linked from the subject's course page and today's daily note. | which classes you had, plus your notes; send slides or photos with it |
| `/add-to-notes` | Files anything (a PDF, slides, a photo of notes, a document, a link) where it belongs, as a source note with links. A link sent on its own runs this too. | a link, or what the files are |
| `/assignment` | Works through an assignment or problem set: every question copied verbatim, complete worked solutions in your course's notation, a confidence (high, medium, low) for each, saved as `<subject>/<due date>-<name>-solutions` with a LaTeX copy. It links it from the course page's tasks (without ticking them). Check the solutions and follow your course's rules on AI help. | which assignment; send the sheet, or name the subject and which one |
| `/connect-notes` | Finds real connections between notes and adds them as links under `## Related`, each with its reason (at most 5 new links per note). Without a topic it starts from notes nothing links to. It may propose an overview note; reply "yes, make it" to have it made. | a note, folder or topic (or nothing) |
| `/term-setup` | Sets up or updates a term from what you say and your academic calendar: key dates, course pages, a week-by-week plan, and a term note ([Classes and timetable](classes-and-timetable.md)). It asks what it can't find; reply to answer. | your subjects and plans; send the academic calendar with it |
| `/exam-prep` | Brings a subject's exam prep up to date from your own class notes, Classroom materials and your books, in the mix you chose, every point cited ([Books and study](books-and-study.md)). | a subject, and optionally which exam or topics |
| `/goodnight` | Sets the wake-up alarm (with Morning alarm on) and writes anything for tomorrow under `## From last night` in tomorrow's daily note. It asks for the time if you didn't give one, and keeps it short: no bedtime summaries. | when you'll wake up, and anything for tomorrow |
| `/morning` | Today's plan in the daily note under `## Plan for today`: Top 3, time blocks around your classes, a line before each class, smaller tasks if there's time. It also acts on your answers: classes you're skipping, when to call you, reminders, blocks in your Agent plan calendar (when those features are on). | your answers to the morning questions, or nothing |
| `/morning-prep` | Drafts today's plan before you wake, with the questions only you can answer. The Morning alarm runs it for you 20 minutes before the alarm; you can run it yourself too. | anything extra to plan around (optional) |
| `/pack` (also `/revision-pack`) | A revision pack as a PDF. See [below](#revision-packs-pack). | a subject, and what it's for |
| `/classroom-digest` | Files new Google Classroom posts for one course into your notes. Classroom → notes runs it by itself after each check ([Google](google.md)); `/classnotes` checks now. | (Kurooto gives it a batch) |
| `/mail-digest` | Turns a batch of new mail into the digest. Mail digest runs it by itself twice a day ([Google](google.md)); `/mail` checks now. | (Kurooto gives it a batch) |

These two are run only by their features and can't be typed:

| Skill | Run by |
|---|---|
| `hint` | `/hint`, the [Hint ladder](books-and-study.md) |
| `retro` | the [Nightly look back](teaching-kurooto.md) |

Copy either one into your skills folder (`/skills copy hint`) to change how it works.

Related commands that aren't skills: `/studypack <subject> [what it's for]` sends a zip of a subject's notes and
course files with a prompt for another AI ([Books and study](books-and-study.md)); `/note` saves a quick note
([Notes](notes-and-concept-graph.md#quick-notes-and-prompts)).

---

## Revision packs (/pack)

**What it does.** `/pack linear algebra midterm friday` reads that subject's notes (course page, exam prep, lecture
notes, solutions) and builds a 2 to 6 page pack: what's on it, definitions, theorems with their hypotheses, formulas,
worked problems, pitfalls, and a self-test with answers. It's sent to you on Telegram and saved:
- `<subject>/revision-pack-<date>.tex` and `.pdf` in your notes (in your files folder when `files.folder` is set);
- `revision-packs/` when the subject has no folder;
- linked from today's daily note (under `## Added`) and from the course page (under `## Revision packs`).

The subject is found from the first words: a subject's name or short name from Subjects, or a folder in your notes.
The rest says what it's for; without it, the pack is for the next quiz or exam.

**Making the PDF.** Kurooto uses **Tectonic** (a small LaTeX program) if it's installed, else LaTeX already on your
computer (`latexmk` or `pdflatex`, e.g. TeX Live, MiKTeX or MacTeX). With neither:
- the pack comes as a `.tex` file, and a message asks **Install Tectonic** / **Not now**;
- **Install Tectonic** downloads it (about 25 MB, from Tectonic's official releases) and then makes the PDF of the
  pack that was waiting. The first PDF takes a few minutes while it fetches about 50 MB of LaTeX packages into
  Kurooto's cache; later ones take seconds;
- **Not now**: packs come as LaTeX, and it asks again after 30 days at the earliest.

If the LaTeX doesn't compile, the AI gets one try to fix it. If that fails too, you get the `.tex` with the first
error line, and it stays in your notes.

**Packs before exams.** With Deadlines on, the evening before a quiz or exam that has a subject (12 to 36 hours
before it, not before 16:00), Kurooto asks once per quiz or exam: "Linear Algebra midterm is tomorrow 10:00. A
revision pack for it tonight?" with **Build it** / **No thanks**. Build it makes the pack (it comes in a few minutes);
No thanks drops it. `skills.auto_pack`:
- `ask` (default): the question above;
- `auto`: builds it without asking (it comes like a `/pack`);
- `off`: never offers.

This offer counts as a message that came by itself ([Messages it sends](messages-it-sends.md)): its **Less of this →
Stop** sets `skills.auto_pack` to `off`.

---

## Listing and changing skills

| Command | What it does |
|---|---|
| `/skills` | Every skill you can run, Kurooto's first, then yours (marked "(yours)") and your add-ons' ("(add-on)"), each with what to type after it |
| `/skills journal` | One skill: what it does, its effort, and where it comes from |
| `/skills copy journal` | Makes your own copy in `kurooto/skills/journal/SKILL.md` in your notes, to edit there |

**Your copy wins.** A skill in your skills folder with the same name as Kurooto's replaces Kurooto's for you; delete
your copy to go back. Updates replace Kurooto's own skills, never your copies.

**Where skills come from**, later ones replacing earlier ones with the same name:
1. the skills that come with Kurooto;
2. your add-ons' skills and prompts ([Add-ons](add-ons.md));
3. prompts in your prompt library marked as skills ([below](#prompts-that-are-skills));
4. your own skills folder (`kurooto/skills/<name>/SKILL.md`, or `master/skills/` in the zettelkasten layout).

**What a skill file looks like.** Markdown with a short header, then the instructions to the AI. `$ARGUMENTS` is
replaced by what you typed after the command (if it's missing, what you typed is added at the end):

```
---
name: weekly-review
description: Turn this week's daily notes into a short review.
effort: medium
args: anything to focus on
---
1. Read this week's daily notes (journal/<YYYY-MM-DD>).
2. Write a note journal/<date>-week-review with what went well, what didn't, and next week's top 3.
Focus: $ARGUMENTS
```

A name is lowercase letters, digits and dashes, 2 to 40 characters.

---

## Your own skills (/newskill)

`/newskill <what it should do>`, for example `/newskill every Sunday, turn my week's daily notes into a short review`.

1. Kurooto says "Writing it; you'll see the whole skill before anything is saved."
2. The AI writes the skill file, and Kurooto sends it to you in full with **Save** and **Discard**.
3. **Save** puts it in `kurooto/skills/<name>/SKILL.md` and tells you how to try it ("Saved. Try it: /weekly-review
   ..."). **Discard** throws it away. Nothing is saved without your tap.

If the name is taken (by a command or another skill), it gets a free one (`weekly-review-2`). If the AI's answer
isn't a usable skill, you're told to try again with more detail. New skills may use only the AI's tools; they're
told never to run shell commands, delete or reword your text, or send anything to anyone else. Edit the file in your
notes any time.

---

## Prompts that are skills

A prompt in your prompt library (`prompts/*.md`, see [Quick notes and prompts](notes-and-concept-graph.md#quick-notes-and-prompts))
becomes a skill when its header says so:

```
---
title: Summarise a paper
skill: true
---
Summarise this paper in 5 bullets for a first-year student: $ARGUMENTS
```

`skill: true` names it after `name:` or the file; `skill: paper-summary` names it outright. `/prompts` marks these
"(also /name)".

---

## Routines (/every)

**What it does.** Runs a skill, a command, or a request for the AI on a schedule.

**From Telegram.**

| Example | What runs |
|---|---|
| `/every monday 9:00 /journal plan my week` | a skill |
| `/every weekdays 7:30 /morning-prep` | a skill on Monday to Friday |
| `/every friday 18:00 /week` | any command |
| `/every daily 21:00 how did today go?` | a request for the AI |
| `/every mon,thu 8pm /quizstatus` | on several days |

**The day part:** `daily` (or `day`), `weekdays`, `weekends`, a day (`monday`, `mon`), or several (`mon,thu`,
`mon and thu`). **The time:** `9:00`, `21:30`, `9`, `8pm`, `7.30am`. "at" between them is fine.

**In plain English**: "every friday at 6pm send me a summary of my week", "every weekday at 7 plan my day". It has to
be a request (send, remind, tell, give, make, run, plan, summarise, check, quiz, review, prepare, draft...) or a
`/command`; "every monday at 9 I have a lab" is a fact, not a routine, so it isn't taken as one.

**`/routines`** lists them, each as its own message with a **Cancel** button ("Cancelled." or "Already gone.").

**When it runs.**
- The result comes as a message starting with the routine's label, e.g. "Mon at 09:00: /journal plan my week".
- Routines run in the background lane, so they never hold up your own requests.
- One that came due while the computer was off or asleep runs **once** when it's back, if that's still one of its
  days.

**Limits.** At most 30 routines. A routine can't set up routines (`/every ... /every` is refused). A `/command` that
doesn't exist is refused when you set it up ("There's no /x command or skill").

**Settings and storage.** Routines live in Kurooto's data folder (`skills/routines.json`), are kept in Profile sync,
and start again when you turn Skills back on.

---

## The rules every skill follows

Every skill request carries these rules (yours and add-ons' too):

- It only **creates notes or adds to them**: never deletes, reorders or rewords what you wrote. Your own words go in
  verbatim.
- **Every link it adds carries a short reason**, and never points at a note that doesn't exist.
- It keeps **health and medical details, money, passwords and other people's private details** out of your notes,
  and says what it left out.
- It **sends nothing to anyone but you**: no messages, mail or sharing, no spending, no deleting.
- It doesn't run shell commands or write programs. If a step needs a tool the AI doesn't have (a feature that's off),
  it skips that step and says so in one line.
- Its answer is short and says what it did and where.

---

## Sending you files

With Skills on, the AI can send you files, on Telegram, in Chat and on calls ("send me my linear algebra pack",
"send me everything about the statistics quiz"):
- one or two files come as they are; more come as one zip;
- only files from your notes folder, your files folder, the course files folder and Kurooto's Classroom copies;
  nothing from anywhere else;
- up to Telegram's **50 MB**. With [Drive upload](google.md) on, anything bigger goes to your Google Drive and you get
  a link instead (a temporary upload, deleted after `drive_upload.temp_days`, 7, unless you move it out of the
  Kurooto folder). Without it, you're told the file is too big;
- during focus time, a file waits until focus ends.

The AI is told always to send files this way and never to answer with file paths.

---

## Skills in agy, Claude Code and other agent programs

**What it does.** Copies every skill you can run here (Kurooto's, your add-ons', your own, and prompts marked as
skills) into the skills folder of the agent programs you use, so `/journal my day` typed in agy runs the same
instructions as on Telegram. Each copy says where your notes folder is and carries the same rules.

**From a terminal.**

| Command | What it does |
|---|---|
| `kurooto export-skills on` | Into agy (`~/.gemini/antigravity-cli/skills`) |
| `kurooto export-skills on --to agy,agents` | Also `~/.agents/skills` (GitHub Copilot CLI and other programs that read it) |
| `kurooto export-skills on --to claude` | Into Claude Code (`~/.claude/skills`), only when you ask for it |
| `kurooto export-skills status` | Lists the copies |
| `kurooto export-skills off` | Removes every copy Kurooto made |

**How it stays tidy.**
- Kurooto only changes or removes the copies it made (each carries a `.kurooto-skill` marker).
- If you have a skill of your own with the same name in that program, yours stays and Kurooto's goes in as
  `kurooto-<name>`.
- A copy you edit by hand is yours from then on.
- They're brought up to date when Kurooto starts (so after every update) and every hour; copies of skills that are
  gone are removed.
- `agents.prefix` (e.g. `k-`) puts a prefix on all of them: `/k-journal`.

**Settings.** `agents.export` (where: `agy`, `agents`, `claude`; empty = off) and `agents.prefix`.

**Turn it off.** `kurooto export-skills off` (or empty `agents.export`). `kurooto uninstall` also removes the copies.
Your own skills in those programs stay.

---

## Settings, privacy, turning it off

**Settings that matter** (Dashboard → Settings → skills):

| Setting | Default | Effect |
|---|---|---|
| `skills.auto_pack` | `ask` | Revision packs before exams: `ask`, `auto` or `off` |
| `skills.auto_pack_after` | `16:00` | Not offered before this time of day |
| `agents.export` | `[]` | Agent programs your skills are copied into (set by `kurooto export-skills`, or Settings → Skills in other AI programs) |
| `agents.prefix` | empty | Prefix for the copied skills' names |

**What leaves your computer.** What you send with a skill (text and files) and the notes it reads go to the AI you
picked. Your own skills, routines and packs are files on your computer.

**Turn it off.** Features → Skills → Turn off. Your own skills, routines and packs stay; routines start again when you
turn it back on. Packs already made stay where they are; `skills.auto_pack` = `off` stops the evening offers.
