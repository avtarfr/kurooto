# Notes and the concept graph

Kurooto keeps everything it writes for you in one folder of plain Markdown files: your **notes folder**. You can
open it in any editor, or as an Obsidian vault. This page covers that folder and the features that work on it:
saving files and quick notes, searching by meaning, syncing to GitHub, and the concept graph that weaves books into
linked notes.

- [Your notes folder](#your-notes-folder)
- [Where each kind of note goes (layouts)](#where-each-kind-of-note-goes-layouts)
- [The files folder: keeping photos and PDFs out of your notes](#the-files-folder-keeping-photos-and-pdfs-out-of-your-notes)
- [Home and hub notes](#home-and-hub-notes)
- [What Kurooto never does to your text](#what-kurooto-never-does-to-your-text)
- [Files into notes](#files-into-notes)
- [Quick notes and prompts](#quick-notes-and-prompts)
- [Notes brain (search by meaning)](#notes-brain-search-by-meaning)
- [Notes sync (GitHub)](#notes-sync-github)
- [Sync everything](#sync-everything)
- [Concept graph](#concept-graph)

Skills that write notes for you (`/journal`, `/study-log`, `/add-to-notes` and the rest) are on
[Skills and routines](skills-and-routines.md). Books and handwritten pages are on [Books and study](books-and-study.md).

---

## Your notes folder

**What it is.** A normal folder of Markdown (`.md`) files. Links between notes are `[[wikilinks]]`, the same kind
Obsidian, Logseq and many other note apps use. Nothing is stored in a database you can't read: if you stop using
Kurooto, the notes stay exactly as they are.

**Where it is by default.**

| Computer | Notes folder |
|---|---|
| Windows | `Documents\Kurooto` |
| macOS | `~/Documents/Kurooto` |
| Linux | `~/Documents/Kurooto`, or `~/Kurooto` if you have no `Documents` folder |

To use another folder (an existing Obsidian vault, say), set **Dashboard → Settings → you → `you.workspace`** to its
full path. Empty means the default above.

**Using it with Obsidian.** Open the notes folder as a vault ("Open folder as vault"). Everything works both ways:
notes you write in Obsidian are read by Kurooto (search, deadlines from `- [ ]` tasks, the term note, and so on), and
notes Kurooto writes show up in Obsidian. With [Notes sync](#notes-sync-github) on, Obsidian's per-device window
layout files (`.obsidian/workspace*.json`) are left out of the repository so two devices don't fight over them.

**Opening a note from the dashboard.** The dashboard's NOTES map opens a note on double-click; see
[Dashboard](dashboard.md) for `notes.open_with`.

---

## Where each kind of note goes (layouts)

**What it does.** Kurooto knows two ways to arrange a notes folder. Pick one in **Dashboard → Settings → notes →
`notes.layout`**: `kurooto` (the default) or `zettelkasten`. The AI is told which one you use, and skills written for
the default layout are translated to yours when they run (yours included).

| What | `kurooto` (default) | `zettelkasten` |
|---|---|---|
| Daily note (journal, plans, check-ins, study hours) | `journal/<date>.md` | `dailies/<date>.md` |
| Your profile, how to help you, not-interested topics | `about-me/` | `master/` |
| Recurring quizzes | `kurooto/recurring.md` | `master/recurring-assessments.md` |
| Ideas from the nightly look back | `kurooto/ideas.md` | `master/ideas.md` |
| Your own skills | `kurooto/skills/` | `master/skills/` |
| Home note | `index.md` | `maps/index.md` |
| A subject's course page | `<subject>/course.md` | `maps/courses/<subject>.md` |
| Lecture notes, exam prep, class log, doubts | `<subject>/` | `sources/<subject>/` |
| Concept notes (one idea each) | `<subject>/<idea>.md` | `zettel/<idea>.md` |
| Research hub, projects and runs | `research/index.md`, `research/<project>/` | `maps/research.md`, `projects/<project>/` |
| Mail digests | `mail/<date>-<time>.md` | `digests/mail-<date>-<time>.md` |
| Quick notes, prompts, handwritten notes | `inbox/`, `prompts/`, `handwritten/` | the same |

**Note headers.** A note Kurooto or the AI writes starts with a short header ("frontmatter"):
- `kurooto` layout: `made_by` (your assistant's name) and `date`.
- `zettelkasten` layout: `id` (the note's path), `aliases`, `tags` and `trust_tier: agent_written`. Your daily note and
  your quick notes don't get `trust_tier`, because they're your own words.

**Your own places (`notes.paths`).** Put any kind of note somewhere else, for example
`{"daily": "diary/{date}.md", "ideas": "plans/ideas.md"}`.

| Kinds you can move | Parts you can use in braces |
|---|---|
| `daily`, `profile`, `how_to_help`, `not_interested`, `recurring`, `ideas`, `skills`, `prompts`, `inbox`, `note`, `subject`, `course`, `class_log`, `lecture`, `concept`, `exam_prep`, `doubts`, `home`, `research`, `project`, `runs`, `handwritten`, `mail` | `{date}`, `{time}`, `{subject}`, `{project}`, `{slug}` |

A place that doesn't work (a part that kind doesn't have, or `..`) falls back to the layout's own, and `/health` says
so.

**Limits and edge cases.**
- Changing the layout or a place affects **new** notes only. Nothing is moved. Move existing notes yourself if you
  want them in the new places; Kurooto then finds them there.

**Undo.** Set `notes.layout` back to `kurooto` and empty `notes.paths`. What was written meanwhile stays where it was.

---

## The files folder: keeping photos and PDFs out of your notes

**What it does.** By default, photos, PDFs and other files you send go inside your notes folder. If you'd rather keep
big files out of your notes (and out of their Git history), set **Dashboard → Settings → files → `files.folder`** to a
folder outside your notes, for example `Documents/Kurooto files` or a folder your cloud drive syncs.

With it set, these go there instead:

| What | Folder inside `files.folder` |
|---|---|
| Photos, PDFs and documents you send (Telegram, the phone app) | `inbox/` |
| After-class photos and files | `<subject>/` |
| Revision packs (LaTeX and PDF) | `<subject>/` |
| Other LaTeX documents skills make | `inbox/` |
| Originals of handwritten pages | `handwritten/` |
| New handwritten scans to read | `handwritten-inbox/` (unless you already have that folder in your notes, or set `handwritten.folder`) |
| Classroom's downloaded course files | `<subject>/` |
| A research project's files | `<project>/` |

Without it (the default), those files stay inside your notes: `inbox/`, `<subject>/files/`, `research/<project>/files/`
in the `kurooto` layout, or under `attachments/` in the `zettelkasten` layout. Classroom's downloads then stay in
Kurooto's own data folder.

**How notes link to the files** (`files.links`): `relative` (a normal relative link; images show inside the note) or
`file` (a `file://` link). Empty means the layout's own choice: `relative` for `kurooto`, `file` for `zettelkasten`.

**Limits and edge cases.**
- A `files.folder` inside your notes folder changes nothing (files still go into the notes), and `/health` says so.
- Notes sync and Backups don't include the files folder. Pick one your cloud drive syncs, or back it up yourself.
- Changing it affects new files only; nothing is moved.

**Undo.** Empty `files.folder`.

---

## Home and hub notes

So your notes don't end up as separate islands, Kurooto keeps two hub notes:
- **Home** (`index.md`, or `maps/index.md` in the zettelkasten layout): a "Hubs" list (the research hub) and a
  "Courses" list (each subject's course page).
- **Research hub** (`research/index.md` or `maps/research.md`): your projects, and what you work on if you told the
  Research feature.

Each course page gets one line at its end linking back to Home and Research. Kurooto only ever adds lines here, and a
line that's already there isn't added twice. They're brought up to date after a book has been read; the research
hub is also made when your first project gets a log line.

---

## What Kurooto never does to your text

These rules hold for Kurooto itself, for every skill and for the AI's tools:

- **It adds; it doesn't reword or delete.** New notes and new lines, yes. Your existing sentences stay as you wrote
  them, and your own words go in verbatim (only obvious typos fixed).
- **Its own parts are marked.** Where Kurooto keeps a part of a note up to date (a book's chapter list, a concept's
  "Seen in" list, exam prep, a handwritten transcription), that part sits between markers like
  `<!-- kurooto:seen -->` and `<!-- /kurooto:seen -->`. Only what's between them is ever replaced. Write anything you
  like above or below.
- **Editing only when you ask.** The AI changes existing text only with its `edit_note` tool, when you asked it to,
  one exact passage at a time. Before each edit the previous version is saved in Kurooto's state folder,
  `note-history/`, the last 20 versions per note. With Notes sync on, your repository's history has every version too.
- **Text files only.** The AI writes only text files (`.md`, `.txt`, `.tex`, `.bib`, `.csv`, `.json`, `.yaml`, ...).
- **No private details.** Skills keep health and medical details, money, passwords and other people's private
  details out of your notes, and say what they left out.

What the AI may read and write on your computer is on [AI brains](ai-brains.md).

---

## Files into notes

**What it does.** Send a photo, PDF, document, video or audio file to your bot and it's saved in your notes. With
Chat on, the AI then files it properly: a note in the right place that says what the file is and links to it.

**Turn it on.** Dashboard → Features → **Files into notes**. Needs Telegram. Filing by the AI needs **Chat**.

**From Telegram.**
- Send the file. It's saved as `<date>-<time>-<name>` in your inbox (`inbox/` in your notes, or in your files folder
  when `files.folder` is set).
- Without Chat: the reply is "Saved to inbox/…". Nothing else happens.
- With Chat: the reply is "Saved; filing it into your notes…", then a one-line answer saying where it went. The
  caption tells the AI what the file is for ("slides from today's Linear Algebra lecture").
- With Skills on, a **link sent on its own** (with at most a few words around it, not a question) is filed the same
  way, by the `/add-to-notes` skill: "https://example.com/paper.pdf for statistics".

**Which feature takes a file.** A file is checked in this order, and the first match wins:

| What you send | What happens |
|---|---|
| A caption that starts with a command (`/note`, `/hint la`, `/journal`, `/study-log`...) | That command or skill gets the file |
| A PDF with a caption like `book for linear algebra` (Books and PDFs on) | It becomes a book for that subject ([Books and study](books-and-study.md)) |
| A `.kurooto-course` file | A class pack to review ([Classes and timetable](classes-and-timetable.md)) |
| A voice message | Written out and handled like typed text ([Talking to Kurooto](talking-to-kurooto.md)) |
| Anything else | Files into notes, as above |

**On the phone.** The Android app's share menu sends files to your notes too ([Phone app](phone-app.md)).

**Limits and edge cases.**
- Telegram lets bots download files up to **20 MB**. A bigger file gets "Couldn't get that file: Telegram only lets
  bots download files up to 20 MB". Copy it into the folder yourself instead.
- With `files.folder` set, the AI is told never to copy the file into the notes folder; it links to it where it is.
- With Files into notes off, a file you send is still saved in the inbox, but nobody files it.

**What leaves your computer.** The file travels through Telegram to your computer. With Chat on, the AI you picked
reads it to file it.

**Turn it off.** Features → Files into notes → Turn off. Saved files and notes stay.

---

## Quick notes and prompts

**What it does.** `/note` saves a thought straight into your inbox, word for word. The prompt library keeps prompts
you reuse, ready to copy. No AI is involved.

**Turn it on.** Features → **Quick notes and prompts**. Needs Telegram.

**From Telegram.**

| Command | What it does |
|---|---|
| `/note buy graph paper` | Saves `inbox/<date>-<first words>.md` with your text as written. Never overwrites: a second note with the same name gets `-2`. |
| A photo or file with `/note` (and optional text) as its caption | The note links the file. |
| `/prompts` | Lists the prompts in your `prompts/` folder (subfolders allowed; a `README.md` is skipped), and your add-ons' prompts as `add-ons/<name>`. A prompt that's also a skill shows "(also /name)". |
| `/prompt <name>` | Sends that prompt back so you can copy it. Matches the name, file name or title in any case, or a unique part of one. Several matches: it lists them. |
| `/prompt save <name>` with the prompt on the next lines | Adds `prompts/<name>.md`. |

Example of saving a prompt:

```
/prompt save summarise
Summarise this in 5 bullet points, keeping every number.
```

A prompt whose header has `skill: true` (or `skill: <name>`) is also a skill you can run as a command; see
[Skills and routines](skills-and-routines.md#prompts-that-are-skills).

**From a terminal.** `kurooto note "an idea"` saves a quick note the same way; pipe text in with
`some-command | kurooto note --title "output"`. It works even when Kurooto isn't running.

**What leaves your computer.** Nothing.

**Turn it off.** Features → Quick notes and prompts → Turn off. Notes and prompts stay.

---

## Notes brain (search by meaning)

**What it does.** Builds an index of your notes so you can search them by meaning, not just exact words
(`/notes what is a compact space`), and gives your AI a memory of them: it uses the same search when it answers you,
on calls too. Kurooto installs [GBrain](https://github.com/garrytan/gbrain) for this and keeps its index in
Kurooto's own data folder.

**Turn it on.** Features → **Notes brain (GBrain)** → Set up. It installs Bun and GBrain (about **0.5 GB**, which is
why it isn't in the Starter set), creates the brain and reads your notes into it once.

**How the index is made** (`gbrain.embeddings`, default `auto`):

| Mode | When `auto` picks it | Where note text goes |
|---|---|---|
| `ollama` | Computers with a graphics card or Apple Silicon (a small model on this computer) | Stays on your computer |
| `gemini` | Computers without one, when you have a Gemini key | Note text goes to Google to make the index |
| `off` | No graphics card and no Gemini key | Keyword search only; nothing leaves |

**From Telegram.**
- `/notes <what you're looking for>`: the best matches from your notes.
- `/timeline <note>`: a note's dated log, oldest first, e.g. `/timeline research/reading-group`.
- Ask your AI in plain words ("what did I write about eigenvalues?", "when did I last work on the reading group?"):
  with Chat on, it searches the brain itself.

**Timelines** (`gbrain.timelines`, on). Every night, dated log lines in your notes, written like
`- **2026-10-19** | source — what happened`, become that note's timeline. Kurooto's own skills and features write
their log lines this way (journal, research project logs). No AI is involved and nothing leaves your computer.

**Nightly upkeep** (`gbrain.upkeep`, off). GBrain's maintenance at 03:00 with light steps only: backlinks, facts,
the index and orphaned pages (timelines are part of it when it's on). Steps that would rewrite your note files or
call an AI model are left out. It's heavy, so on a laptop it waits for the charger. If it fails you get one message
("The notes brain's nightly upkeep didn't finish ... Search still works"), with where its log is, and not again
until it has worked once. Logs are kept two weeks.

**Choosing the upkeep's steps** (`gbrain.upkeep_steps`). Empty means the light steps above. You can list GBrain's
own phase names instead, for example `["lint", "backlinks", "sync", "extract", "extract_facts", "consolidate",
"embed", "orphans"]`. Know what you add: `lint` and the repair steps rewrite note files, and `consolidate`,
`synthesize` or `edge_contradictions` call the AI model GBrain is set up with (on a paid key, they spend money).
Kurooto never runs `purge` (it deletes pages for good), and unknown names are skipped. *Undo:* empty the list.

**Weekly checkup** (`gbrain.checkup`, off). GBrain's own advisor, Sundays at 19:30. You get a message only when
something is a warning or worse, listing up to 8 findings, with buttons:
- **Ignore these**: adds them to `gbrain.checkup_ignore`, so the checkup doesn't mention them again.
- **Update the brain** (only when the brain needs a schema update, and only for Kurooto's own brain): runs GBrain's
  update. "The brain is busy" means try again later.

A button on an old checkup says "That checkup is old; the next one comes on Sunday."

**Your own GBrain.** If you already run GBrain yourself, Kurooto can use that brain instead of making its own:

| Setting | Set it to |
|---|---|
| `gbrain.managed` | `false` |
| `gbrain.exe` | your gbrain program (empty: the one on your PATH) |
| `gbrain.home` | its `GBRAIN_HOME` folder (empty: GBrain's default) |
| `gbrain.source` | the GBrain source that is your notes folder (optional) |

Then press Set up; it only checks that your brain answers. From then on Kurooto searches it, adds pages through
gbrain's own commands (books, for example), runs the nightly steps you turned on, and, if you named `gbrain.source`,
runs `gbrain sync` and `gbrain embed --stale` for that source every 15 minutes. It never creates, migrates, upgrades
or reconfigures your brain, and doesn't back it up. With `gbrain.agy_mcp` on, agy is also offered your brain's own
MCP tools (asked first, with Approve / Deny); `gbrain.mcp_surface` (`full`, `starter`, `verbs`) picks how many.

**Settings that matter** (Dashboard → Settings → gbrain):

| Setting | Default | Effect |
|---|---|---|
| `gbrain.embeddings` | `auto` | How the index is made: `auto`, `ollama`, `gemini`, `off` |
| `gbrain.sync` | `every 15m` | How often your notes are read into the brain |
| `gbrain.timelines` | on | Nightly timelines from dated log lines |
| `gbrain.upkeep` | off | Nightly upkeep (light steps) |
| `gbrain.nightly` | `daily 03:00` | When timelines and upkeep run |
| `gbrain.upkeep_steps` | `[]` | The upkeep's steps; empty = the light ones |
| `gbrain.checkup` | off | The weekly checkup |
| `gbrain.checkup_when` | `weekly sun 19:30` | When it runs |
| `gbrain.checkup_ignore` | a list | Findings the checkup leaves out |
| `gbrain.managed` | on | Off: use your own GBrain |

**Limits and edge cases.**
- "The notes brain is busy with its upkeep; try again in a while": the upkeep or a sync is using it.
- "Nothing in your notes about that": no match.
- Kurooto pins GBrain's version and turns off GBrain's own update check.
- On battery (in the default saver mode) the 15-minute re-reading, timelines and upkeep wait for the charger; `/notes`
  still works on what's indexed.

**What leaves your computer.** Nothing with a graphics card or Apple Silicon. In `gemini` mode, note text goes to
Google (your key) to make the index; on Google's free tier, Google may use it to improve its products.

**Turn it off / undo.** Features → Notes brain → Turn off. The index stays in Kurooto's data folder; your notes are
untouched. For your own GBrain: set `gbrain.managed` back to `true`; `agy mcp remove gbrain` takes its tools away from
agy.

---

## Notes sync (GitHub)

**What it does.** Keeps your notes folder in your own **private** GitHub repository. Every change is kept in its
history (so nothing written is ever lost), and edits made elsewhere (another computer, GitHub's website, a phone app
that syncs with the repository) come in too. With Phone calls on, your call line can read whole notes from the
repository while your computer is off.

**Turn it on (about 5 minutes).**
1. [Make a repository](https://github.com/new): any name, **Private**, nothing ticked.
2. [Make a fine-grained token](https://github.com/settings/personal-access-tokens/new): Repository access → Only select
   repositories → that one; Permissions → Contents → **Read and write**.
3. Features → **Notes sync**: paste the repository as `owner/name` and the token, press Save.

Git is installed for you if it's missing (MinGit on Windows; on a Mac, Apple's installer opens: click Install, then
press Set up again). Kurooto checks the repository first and refuses:
- a **public** repository ("anyone could read your notes");
- a token that can only read ("it needs Contents: Read and write");
- a repository the token can't see (pick it under Repository access).

**When it syncs.**
- Every 10 minutes (`notes_sync.every`).
- About 2 minutes after an AI request finishes, so what it wrote goes up soon (`notes_sync.after_jobs`; one push for
  a burst of requests; 0 waits for the timer).
- When Kurooto stops (a shutdown, an update), quickly, unless Kurooto is paused.
- When you ask: `/sync`.

Each sync saves what changed here (one commit, "notes: <date time>"), takes in what changed elsewhere, then sends
it up.

**A notes folder that's already a Git repository.** Its `origin` is used as it is when it's the same repository
(HTTPS or SSH). An `origin` that points at another repository is left alone, and Kurooto adds a remote of its own
called `kurooto`. A `.gitignore` is written if there's none (system junk files, Obsidian's workspace files,
half-downloaded files).

**When a note changed in two places at once** (`notes_sync.on_conflict`):
- `keep both` (default): the note keeps the version from elsewhere, and this computer's version goes beside it as
  `<note> (conflict, this computer, <date time>).md`. You get a message naming both. Merge them when you like and
  delete the copy. A note deleted on one side and changed on the other is kept, changed. Notes changed on one side
  only merge as usual.
- `stop`: sync stops, changes nothing, and tells you (at most every 6 hours) until you've sorted it out yourself in
  the notes folder (`git pull --rebase`, fix the files, `git add`, `git rebase --continue`). It never forces anything.

A merge or rebase left half done in the notes folder is left alone; sync waits until it's finished. A notes folder
that's not on a branch ("detached HEAD") also stops sync until you check your branch out again.

**From Telegram.** `/sync` syncs your notes now ("Notes synced." or "Couldn't sync: <why>"). `/sync all` syncs
everything ([below](#sync-everything)).

**Settings that matter** (Dashboard → Settings → notes_sync):

| Setting | Default | Effect |
|---|---|---|
| `notes_sync.every` | `every 10m` | How often it syncs |
| `notes_sync.after_jobs` | `2` | Minutes after an AI request before its notes go up; 0 = wait for the timer |
| `notes_sync.on_conflict` | `keep both` | `keep both` or `stop` |
| `notes_sync.share_with_calls` | on | Your call line may read notes from the repository while the computer is off |
| `notes_sync.branch` | `main` | Filled in from the repository |

**Messages it sends by itself.** "Notes sync: N note(s) changed here and elsewhere at once..." (a clash kept as
copies), and "Notes sync: <problem>." at most every 6 hours while something is wrong (can't reach the repository,
can't push, unfinished merge).

**Limits and edge cases.**
- On battery (saver mode) the 10-minute sync waits for the charger. `/sync` works any time.
- The files folder (`files.folder`) isn't synced.
- `/health` warns when the GitHub token expires within 10 days (GitHub also emails you 7 days before).
- Two computers can sync the same notes repository; conflicts are handled as above.

**What leaves your computer.** Your notes, to your own private GitHub repository. With Phone calls on, your call line
can read them from there.

**Turn it off / undo.** Features → Notes sync → Turn off. The repository and its history stay on GitHub; delete the
repository there if you want them gone. `notes_sync.on_conflict` = `stop` undoes the keep-both behaviour. Conflict
copies are ordinary notes: delete them once merged.

---

## Sync everything

**What it does.** Runs every sync that's on, one after another, in the background, then sends one line per feature,
for example "Calendar: ok, 23 events". The order:

1. your notes (to take in what changed elsewhere),
2. Google: Classroom, Classroom → notes and the mail digest,
3. your calendars,
4. research project logs,
5. the notes brain's index,
6. a backup (with Backups on; skipped, not failed, when the backup folder isn't there, e.g. the drive is unplugged),
7. your notes again (to send up what the others just wrote).

A feature that's off is left out. Only one runs at a time: "A sync is already running; you'll get its summary."

**From Telegram.** `/sync all`, `/sync everything`, or in plain words "sync everything", "sync it all", "sync all the
things". With Notes sync off, plain `/sync` does the same.

**From a terminal** (Kurooto running):

| Command | What it does |
|---|---|
| `kurooto sync` | Runs it and waits, then prints the summary |
| `kurooto sync --no-wait` | Starts it and returns; the summary comes as a message |
| `kurooto sync --status` | Whether one is running and how the last one went (works with Kurooto stopped) |

---

## Concept graph

**What it does.** When a book has been read (see [Books and study](books-and-study.md)), its concepts are woven into
your notes:
- a **concept note** for each new concept (its definition, formulas, links, and where it came from);
- **typed links** to notes you already have, each with a relation and a one-sentence reason, e.g.
  `- special-case-of:: [[linear-algebra/eigenvalues]] — the diagonal case of the spectral theorem`;
- a **"Seen in"** list on each concept: the book and pages, plus "Added from the books" lines for what an existing
  note lacked;
- in the **book's own note**, which concepts each stretch of pages introduces;
- on the subject's **course page**, a "From the books" list of the concepts its books introduced.

Your own text is never changed. Kurooto adds lines and keeps its parts between `<!-- kurooto:... -->` markers; a write
that would touch anything else is refused.

The relation words are: `needs`, `generalises`, `special-case-of`, `example-of`, `contrasts-with`, `equivalent-to`,
`part-of`, `used-in`.

**Turn it on.** Features → **Concept graph**. Needs **Books and PDFs** on (and at least one book read). It works best
with an agent program (agy or Claude Code) installed; see "Which AI" below.

**How one batch goes.**
1. The book is cut into batches of about 12 pages (3 to 20) that follow its sections: the PDF's bookmarks, numbered
   headings, the running headers at the top of pages, or "Chapter 3 ..." lines. A margin note such as "Section 9.1"
   is never taken for a heading. (A book the graph began before 0.5.8 keeps the batches it began with.) A batch waits
   until its pages are read; a page the reader skipped (waiting for OCR, say) doesn't hold it back once the book's
   reading is over.
2. On this computer, without an AI, Kurooto finds the few existing notes that may be related: matching names and
   aliases, keyword ranking, the notes those link to, and, where there's a model for it, meaning (Ollama's
   nomic-embed-text, or your Gemini key). With a helper model on this computer, a **reranker** then orders them by
   how likely each belongs with the new concept (no extra download, no AI requests).
3. One AI request is shown the pages and those notes only, and answers with the concepts the pages develop, how each
   relates to your notes, and what an existing note lacks.
4. Plain checks run on the answer, without trusting the AI's opinion of itself:
   - the quote it gives must really be in those pages;
   - a link's reason must say something specific ("related to", "see also", "connected" are refused);
   - a link must point at a note that exists, or one made in the same batch;
   - "this is your existing note X" needs the names or the meaning to agree;
   - only the relation words above; two notes can't each generalise the other;
   - a concept with the same name as an existing note is never made a second time.
5. Anything doubtful goes to a **second look** by the other AI program (or the same one, told to be strict), and is
   dropped unless that confirms it; "this is your existing note X" that isn't confirmed becomes a note of its own and
   leaves X alone. There's no queue for you to review.
6. What's left is written and, if your notes are a Git repository, **committed: one commit per batch**, so
   `git revert <commit>` undoes exactly that batch.

**When it runs.**
- Each night from 01:30 (`integrate.at`), batch after batch, and right after a book has been read.
- Every 3 hours it carries on if something was waiting (a limit that has reset). When the AI was at its limit or
  signed out, it tries again after 20 minutes. A batch that fails 3 times is marked failed.
- At most `integrate.per_night` (300) batches a day, so it can't use all of your AI's day.
- Books with the fewest pages go first (`integrate.order`), so the most books get done soonest; list subjects to do
  first in `integrate.first`.
- Effort: the small, quick model by default; the next one up for a batch that failed before, or for a book whose
  recent batches needed many second looks.

**The daily second pass ("garden")**, at 06:20 (`integrate.garden`): the notes the reading touched, then notes that
nothing links to, are checked once more against everything that's there now (up to 40 a day,
`integrate.garden_per_day`). It also takes out links Kurooto wrote to notes that don't exist any more (a concept
dropped after a second look, or a note you deleted). Your own links are never touched.

**The morning line** (`integrate.summary`), at 07:10 when anything happened: "Concept graph: 14 batches, +22 concept
notes, +61 links, 9 notes updated; 30 AI requests (about $0.40 at API prices); 5 doubtful, 2 dropped after a second
look." The cost is what the requests would cost at API prices; a subscription plan isn't billed per request (its own
limit is what runs out).

**From Telegram.**

| Command | What it does |
|---|---|
| `/graph` | The state: batches done, waiting and failed; which AI does the bulk work and the second look; today's AI requests and cost; and the quality numbers below |
| `/graph now` | Starts the next batch now ("Started.", or "Nothing to start" and why) |
| `/graph stop` | Starts no new batches until the next night's start ("Stopped: no new batches until its usual start, Thu 01:30"); it holds through a restart, and `/graph now` goes on sooner |

The quality numbers in `/graph`: how many concepts and links, **broken** links, notes with **no links in**, links
with a **vague reason**, and the share of all links that go to the three busiest notes (a high share means a few hub
notes swallow everything).

**Which AI** (`integrate.roles`, e.g. `{"bulk": "agy", "check": "claude"}`). Empty (the default) chooses for you:
- agy and Claude Code both installed: they split the work (bulk and second look) and run side by side;
- one of them: it does both;
- neither: your main AI does both. With a free Gemini key's daily limit that's slow: set `integrate.per_night` low and
  `integrate.first` to your current subjects.

Without a graphics card nothing changes except that the meaning-based matching comes from your Gemini key or is
skipped.

**Settings that matter** (Dashboard → Settings → integrate):

| Setting | Default | Effect |
|---|---|---|
| `integrate.at` | `daily 01:30` | When the night's work starts |
| `integrate.roles` | `{"bulk": "", "check": ""}` | The AI for the bulk work and the second look; empty = chosen for you |
| `integrate.batch_pages` | `12` | About how many pages per request |
| `integrate.per_night` | `300` | The most batches in a day |
| `integrate.first` | `[]` | Subjects to do first, e.g. `["linear-algebra"]` |
| `integrate.order` | `smallest` | Which books first: `smallest` or `name` |
| `integrate.garden` | on | The daily second pass |
| `integrate.garden_per_day` | `40` | The most notes in that pass |
| `integrate.embeddings` | `auto` | Meaning-based matching: `auto`, `ollama`, `gemini`, `off` |
| `integrate.rerank` | `auto` | The local reranker: `auto` or `off` |
| `integrate.rerank_model` | empty | Another Ollama model for it (empty: this computer's helper model) |
| `integrate.commit` | on | One Git commit per batch, when your notes are a repository |
| `integrate.summary` | on | The morning line |

**Limits and edge cases.**
- It's heavy work: on battery (saver mode) it waits for the charger.
- After `/graph stop`, a batch already sent still finishes, but nothing new starts (not the retries either) until the
  next night's start (`integrate.at`). To stop it for longer, turn the feature off.
- Page numbers are the PDF's own (page 1 is the first page of the file, often the cover).

**What leaves your computer.** A few pages of a book's text at a time, and the titles and opening lines of the related
notes, go to the AI you picked, like any request. The matching, the checks and the reranker run on this computer.

**Turn it off / undo.**
- Features → Concept graph → Turn off stops it. Notes already written stay.
- `git revert <commit>` undoes one batch (each batch is one commit, named like
  `books: <title> pp. 41-52 (+3 notes, +7 links, 2 updated)`).
- Each batch also keeps a before-copy of every file it changed in Kurooto's state folder, `integrate/undo/` (the last
  60 batches; the [Space keeper](updates-and-backups.md) removes copies older than 30 days).
