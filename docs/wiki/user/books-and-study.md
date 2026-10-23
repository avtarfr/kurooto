# Books and study

Your textbooks read into text your AI can cite by page, a say in how much books, class material and your own notes
count when the AI writes notes, a study-time tracker, study packs to take a subject to another AI, and handwritten
pages written out as notes; your drafts checked before you hand them in, and a course's notes as one PDF.

- [Books and PDFs](#books-and-pdfs)
- [The source mix](#the-source-mix)
- [Study tracker](#study-tracker)
- [Study packs](#study-packs)
- [Handwritten notes](#handwritten-notes)
- [Check my draft](#check-my-draft)
- [Course notes as one PDF](#course-notes-as-one-pdf)

---

## Books and PDFs

**What it does.** Keeps your reference books and other PDFs per subject, reads them at night into text with page
numbers, writes an index note for each book in your notes, and lets your AI use the right pages (and cite them, "book:
Linear Algebra, p. 123") when it writes course notes, exam prep, revision packs and study packs.

**Turn it on.** Dashboard → Features → Books and PDFs.

**Adding a book**, three ways:
- **Telegram:** send the PDF with a caption like `book for linear algebra`, `textbook for stats` or
  `linear algebra textbook`. It's moved out of your notes' inbox into that subject's books folder. Telegram lets bots
  fetch files only up to **20 MB**: put bigger books in the folder. Only PDFs are taken ("Books must be PDFs").
- **The dashboard:** Features → Books and PDFs: give the PDF's place on this computer and its subject (a copy is
  made).
- **The folder:** drop PDFs into the subject's books folder, in any subfolder; `.pdf` in any case. `/books folder
  linear algebra` says where it is (and makes it).

Books are never kept inside your notes folder. They go to `<files folder>/<subject>/books/` when you've set a
[files folder](notes-and-concept-graph.md), else to Kurooto's data folder (`books/<subject>/`); `books.folder` picks your
own place (a folder per subject inside it). Files over 400 MB are left alone.

**Reading.** At 01:00, on the charger, Kurooto reads every new book page by page and picks the best way for each page:
1. the PDF's own text, when the page has a real text layer (Poppler's `pdftotext` if it's installed, else Kurooto's
   built-in reader);
2. a scanned page: **Tesseract** OCR, if installed (`/books setup` installs it). Tesseract writes plain text, so
   equations come out garbled;
3. without Tesseract, or for pages full of maths whose text came out in pieces: a **vision model** on this computer
   (Local AI models, on graphics cards of 8 GB or more), which writes the maths in LaTeX;
4. **Gemini** with your key, only if you turn on `books.gemini`: pictures of pages nothing on this computer could read
   go to Google. Books may be copyrighted, so this is off by default.

It stops at 07:00, when you unplug, or with `/books stop`, and carries on the next night from the page where it
stopped. Pages no reader could handle wait, and are read once a reader is there. Encrypted PDFs need Poppler's PDF
tools: `poppler-utils` from your package manager on Linux, `brew install poppler` on a Mac, or
poppler.freedesktop.org on Windows. When a book is done you get one message: "Read "Linear Algebra" (412 pages: 398 by
text layer, 14 by Tesseract). Its chapters are in …".

**What it makes:**
- the text with page markers (`## [p. 123]`) in Kurooto's data folder (`book-text/<subject>/<book>/text.md`), outside
  your notes;
- an index note in your notes, `<subject>/books/<book>.md`: the title, the chapters with their pages (from the PDF's
  bookmarks, or "Chapter 3 …" headings), how each page was read, and links to the original. Kurooto writes only
  between its two markers; your own notes around them stay;
- with the [Notes brain](notes-and-concept-graph.md) on, the text in the brain too, so `/notes` finds book pages;
- with the [Concept graph](notes-and-concept-graph.md) on, the book's concepts woven into your notes.

Page numbers are the PDF's own (p. 1 is the first page of the file, often the cover).

**From Telegram.**

| Command | What it does |
|---|---|
| `/books` | your books per subject and how far reading got ("not started", "120 of 412 pages read", "read (412 pages, 3 waiting for a reader)") |
| `/books read now` (or `/books now`) | starts reading now. On battery it waits for the charger instead. |
| `/books read force` | reads now even on battery (until 07:00 or `/books stop`) |
| `/books stop` | stops after the current page; it carries on tonight |
| `/books folder` | where books go |
| `/books folder linear algebra` | that subject's folder (made if missing) |
| `/books mix …` | the source mix (below) |
| `/books setup` | installs Tesseract for scanned pages; a message says when it's done |

**Settings that matter** (Dashboard → Settings → Books and PDFs)

| Setting | Default | Effect |
|---|---|---|
| `books.at` | `daily 01:00` | when the night's reading starts |
| `books.until` | `07:00` | when it stops |
| `books.ocr` | `auto` | who reads scanned pages: `auto` (Tesseract, else the vision model), `tesseract`, `vision`, `off` |
| `books.ocr_lang` | `eng` | Tesseract's languages, e.g. `eng+deu` (each needs its language data installed) |
| `books.latex` | `maths` | when the vision model reads a page for LaTeX: `maths` (pages whose maths came out in pieces), `all`, `never` |
| `books.gemini` | off | on: unreadable pages go to Gemini as pictures |
| `books.dpi` | 200 | how sharp the page pictures for OCR are |
| `books.brain` | on | index the text into the notes brain |
| `books.max_mb` | 400 | bigger PDFs are left alone |
| `books.folder` | empty | your own books folder (a folder per subject in it) |

For tinkerers: `books.after_read` runs a command of yours after each book (with its subject and id added), and
`books.brain_source` puts the text into a GBrain source you name.

**What leaves your computer.** Nothing while reading, unless you turn on `books.gemini` (page pictures to Google).
Excerpts of your books go to your AI when it writes your notes.

**Turn it off / undo.** Features → Books and PDFs → Turn off: reading stops after the current page; books, their text
and the index notes stay. To remove a book, delete its PDF from its folder; its index note and its text are then yours
to delete (Kurooto never deletes them). Tesseract installed by `/books setup` is removed like any program (winget on
Windows, Homebrew on a Mac, your package manager on Linux).

## The source mix

When your AI writes course notes (`/study-log`, Classroom → notes, `/exam-prep`, `/pack`, `/add-to-notes`), it asks
for a subject's material from three sources:
- **book**: the pages of your books on the topic;
- **classroom**: Classroom posts and the files Classroom → notes downloaded;
- **own**: notes you wrote yourself (not the AI), the class log, and the "My notes" part of lecture notes.

Only the sources a subject has are used, and their shares grow to fill the room the others leave. The notes cite each
part: (book: Linear Algebra, p. 123), (Classroom: Problem set 3), (your notes: [[linear-algebra/2026-10-12-eigen]]).
Your own words are quoted, never reworded.

| Command | What it does |
|---|---|
| `/books mix linear algebra` | shows the subject's mix |
| `/books mix linear algebra book 30 classroom 30 own 40` | shares (any numbers; they're scaled) |
| `/books mix linear algebra prefer own book classroom` | an order instead: the first counts most (3:2:1) |
| `/books mix linear algebra reset` | back to the general mix |
| `/exam-prep linear algebra` | brings that subject's exam-prep note up to date from all three sources (also without Classroom); the [Quiz](quiz-and-exams.md#quiz) asks from it |

**Settings** (Settings → Sources for answers)

| Setting | Default | Effect |
|---|---|---|
| `sources.mix` | book 0.3, classroom 0.3, own 0.4 | the general shares |
| `sources.prefer` | `[]` | an order instead of shares, e.g. `["own", "book", "classroom"]` |
| `sources.cap` | book 12000, classroom 10000, own 12000 | characters at most from each source |
| `sources.budget` | 24000 | characters in all, per request |
| `sources.subjects` | `{}` | per-subject mixes (what `/books mix` sets) |

**Undo.** `/books mix <subject> reset`; reset `sources.mix` in Settings for the general one.

## Study tracker

**What it does.** Counts how long you spend on each subject from the window you're working in, and what you log by
hand. A window whose title names a subject (its name or a short name: a PDF called `linear-algebra-week3.pdf`, a note
in that subject's folder) counts while you're at the computer: not idle for 5 minutes and the screen not locked. Only
minutes per subject are kept, never window titles.

**Turn it on.** Features → Study tracker (needs Subjects). Works on Windows, macOS (it asks once for permission to see
window titles; say no and it can only log by hand) and Linux on X11, Hyprland or Sway. Other Linux desktops can only
log by hand.

**From Telegram.**

| You send | What happens |
|---|---|
| `/study` | today's hours per subject, and a session if one is running |
| `/study week` | the last 7 days |
| `/study la 50` | starts a 50-minute session away from the computer (library, paper); it ends by itself with "Session done. Linear Algebra: 50 min logged. Take a break." |
| `/study la` | starts an open session |
| `/study stop` | ends the session and logs it |
| `/study mode on` / `/study mode off` | the dashboard's [Study mode](dashboard.md#study-mode) |
| `/studied 2h linear algebra`, `/studied 90m stats` | logs time afterwards |
| "starting linear algebra for 50 min", "I'm studying stats" | starts a session |
| "done studying" | ends it |
| "studied stats for an hour" | logs it |
| "how much did I study today?" | today's hours |

While a session runs, the window doesn't count (no double counting). A timed session counts at most the time you
planned. A session that runs past midnight goes to the day it started. Starting a new session ends the old one first.
You can also tell the evening check-in call what you studied.

**In your notes.** At 23:45 the day's hours go into your daily note as "## Study hours", with how much was away from
the computer. If the computer was asleep then, it's written for that day when it wakes.

**How it tells you're away.** Windows and macOS from the system's last-input time; Linux from your desktop (X11, GNOME,
KDE, logind's idle hint). On Hyprland, Sway and other Wayland desktops without an idle API it watches for change
instead (keyboard and touchpad activity, the cursor on Hyprland, the focused window; nothing you type is read). A
locked screen never counts. `kurooto doctor` says which way this computer uses.

**Your idle tool can tell it** (more exact on Wayland): `kurooto idle away` when you go idle, `kurooto idle back` when
you're back. For hypridle (`~/.config/hypr/hypridle.conf`):

```
listener {
    timeout = 300
    on-timeout = kurooto idle away
    on-resume = kurooto idle back
}
```

For swayidle: `swayidle timeout 300 'kurooto idle away' resume 'kurooto idle back'`.

**Research time.** A window naming one of `study.research_paths` (words, or folders matched by name) counts as
**Research**; with [Research](research.md) on, its projects and repository folders count too.

**On the dashboard.** The STATUS pane shows "study today"; `kurooto top` too. The weekly summary and the Sunday review
call include study hours. [Study mode](dashboard.md#study-mode) (Alt+M, `/study mode on`) keeps only your notes and a
focus and break timer: a focus holds calls and messages and logs its minutes here.

**Settings that matter** (Dashboard → Settings → Study tracker)

| Setting | Default | Effect |
|---|---|---|
| `study.idle_min` | 5 | minutes without input before you count as away |
| `study.daily_note` | `23:45` | when the day's hours go into the daily note; empty: never |
| `study.research_paths` | `[]` | words or folders that count as Research |
| `study.keywords` | `{}` | extra words per subject, e.g. `{"linear-algebra": ["matrix", "eigen"]}` |
| `study.focus_min` / `study.break_min` | 25 / 5 | Study mode's timer: minutes of focus, then of break |
| `study.timer_ends_mode` | off | Study mode ends when a focus ends, instead of a break |

**What leaves your computer.** Nothing. Window titles are read here and thrown away.

**Turn it off / undo.** Features → Study tracker → Turn off. Empty `study.research_paths`; remove the idle hook lines
(and run `kurooto idle back` once, or counting stays paused).

## Study packs

**What it does.** Bundles one subject's notes and course material into a zip with a ready-made prompt, so you can hand
it to another AI (any chat AI that takes file uploads) and ask it for deeper study notes. Nothing here uses your own
AI: Kurooto only collects files and fills in the prompt.

**What goes in.** The subject's folders and course map, and other notes that link to them. A note kept in another
course's or project's folder doesn't come along just because it links this course (0.6.1: a project's book note
that mentioned the course did); with a topic, it comes if it's about the topic.

**Turn it on.** It's part of Skills: Features → Skills.

**From Telegram.** `/studypack linear algebra` for everything, or add what it's for: `/studypack la quiz on thursday`.
Naming a topic narrows the pack to it: `/studypack la quiz on eigenvalues` (or an aim that names
one, such as `/studypack la eigenvalues`; several: `on eigenvalues, diagonalisation`) takes only the class files that
mention it, the pages of each book about it (as text, with a page either side, up to 150 pages per book) and the notes
about it, including what the notes brain finds. Class material and books are told apart by length, because
professors post books on Classroom too: over 80 pages, or a title with "Ch 8", "edition" or a download site's name,
is a book; 40 pages or less, or a lecture, notes, slides, cheat sheet, quiz, assignment or exam paper, is class
material. Class material always comes first: in the zip (`class/`, then `books/`, then `notes/`) and in the prompt,
which tells the other AI to follow the class where a book disagrees. **A whole book never goes in**: it would flood
the other AI's context. Without a topic, books are only listed in `INDEX.md`; name a topic to get their pages. A book
Books hasn't read yet can't be cut to its pages, so it stays out too. The AI can do the same when you ask in plain
words ("send me everything on thermodynamics for my POTA quiz").

Which pages of a book go in, in order: first the readings your class material cites ("Reference: Salby Chapter 2",
"Wallace and Hobbs Chapter 3 Section 3.2, 3.3"), then whole chapters and sections whose titles name the topic (from
the book's own bookmarks), then other pages that mention it, those mentioning it most first. All the books together
keep to 250 pages, about what another AI can hold at once; `INDEX.md` lists what didn't fit. Lecture files Books hasn't
read are judged by Classroom's text of them, and a file that's both in Classroom and in your books folder goes in once.

**Your own prompt.** `/studypack prompt` puts the prompt every pack gives the other AI into your notes
(`kurooto/study-pack-prompt.md`) to edit; `{name}`, `{topics}`, `{aim}` and the other words listed at its top are
filled in for each pack. `/studypack prompt reset` brings Kurooto's back. The subject can be its name or a short name; your
AI can make one for you too ("make me a study pack for statistics").

**What's in the zip:**

| Folder or file | What |
|---|---|
| `class/` | what the class gave out: lecture slides and notes, cheat sheets, problem sets, exam papers |
| `books/` | books for the course (whole, or with a topic only its pages, as text) |
| `notes/` | your notes for the subject, and any note that links to them |
| `PROMPT.md` | what to say to the other AI, with the aim you gave |
| `INDEX.md` | every file in the pack, and what was left out and why |

Class material and books are told apart by length, since books are often posted to Classroom too: over 80 pages, or a
title that says "edition", "Ch 8" and the like, is a book; 40 pages or less, or a lecture, slides, notes, quiz,
assignment or exam paper, is class material.

**What comes to Telegram.** The zip ("Study pack: Linear Algebra. Upload it to your AI and paste the prompt below."),
then **the prompt as its own message**, ready to copy and paste (it's also `PROMPT.md` in the zip), and a line saying
how many notes and files went in.

**Size limits.** Telegram takes files up to 50 MB.
- With [Drive upload](google.md) on, nothing is left out: a pack over 50 MB goes to your Google Drive and you get a
  link. That upload is temporary: it's deleted from your Drive after `drive_upload.temp_days` (7) days, unless you move
  it out of the Kurooto folder in Drive first.
- Without it, the zip is kept under 50 MB (notes first, then class material, newest first, then books); what didn't fit
  is listed in `INDEX.md` and the reply says how many files were left out.
- Notes over 400 KB and files over 40 MB are always left out; hidden files and folders never go in.

**What leaves your computer.** Only what you choose to upload to the other AI yourself. With Drive upload, a pack over
50 MB goes to your own Google Drive. The zip is kept in Kurooto's cache, which the
[Space keeper](updates-and-backups.md) clears after 14 days.

**Turn it off.** Turn off Skills, or just don't use `/studypack`.

## Handwritten notes

**What it does.** Drop a PDF or photo of handwritten pages into a folder and Kurooto writes it out as a Markdown note
with the maths in LaTeX, saved in `handwritten/` in your notes, linked to the original.

**Turn it on.** Features → Handwritten notes. By default the folder is `handwritten-inbox` in your notes (or in your
files folder); point `handwritten.folder` at a folder your tablet's notes app syncs to (Google Drive, OneDrive,
Dropbox). Photos (`.png`, `.jpg`, `.jpeg`, `.webp`, `.heic`) and PDFs work.

**Who reads the pages.**
- **This computer**, with Local AI models on: the vision model on 12 GB graphics cards, or the helper model on 8 GB
  cards; `handwritten.local_model` names another Ollama model that reads pictures. Nothing leaves your computer then.
  Photos are read right away. PDFs are read page by page **at night on the charger** (`handwritten.pdf_hours`,
  23:00 to 07:00), each page kept as it's done, so unplugging or the morning only pauses it. You get one message when
  a PDF is waiting for the night ("Got notes.pdf (12 pages). I'll write it out … at night; /handwritten starts it
  now."). It waits while the graphics card is busy with something else, and writes out up to 60 pages per PDF.
  Drawing a tablet's PDF pages as pictures needs Poppler's PDF tools (scanned PDFs don't).
- **Gemini**, with your key, when there's no model here. `handwritten.cloud` = `false` keeps everything on your
  computer: pages then wait for a model here.

It looks in the folder every 15 minutes. When pages are written out you get "Written out: …"; a file that fails gets a
message saying why.

**Your own notes in it.** Kurooto's part of the note sits between `<!-- kurooto:handwritten -->` markers. When you
change the original on your tablet, the same note is written again between the markers; what you wrote around them
stays. Machine transcriptions aren't checked: look at the original for anything that matters.

**Linked like any other note.** Once a note is written out, one request to your AI (the concept graph's second-look AI
when that's on, else your main AI) links it into the rest of your notes, and you get one line: "Linked your
handwritten notes 'Phase change thermodynamics' to POTA lecture 20 and 9 concepts".
- **A real title.** When the heading is still the scan's file name ("21 October 2026_261021_105812"), it becomes a
  title from what's written, and the old name stays as an alias. A heading you changed, or anything you wrote above
  the transcription, is left alone.
- **The subject and the lecture.** Kurooto looks at when the pages were written (the PDF's own dates, a time stamp in
  the file's name, else the file's time) and at your timetable: written during a class, or later that day, the notes
  belong to that class. Otherwise the AI picks the subject from what the pages say, against your subjects' course
  pages. The note's header gets the subject's tag and `course: <slug>`.
- **`## Links`** right after the transcription's closing marker, in a block of Kurooto's own
  (`<!-- kurooto:linked -->`): that day's lecture note, the course page and the concept notes the pages cover, each
  as `- [[path]]: reason`. The candidates come from the concept graph's own search (no AI); the AI picks the ones that
  really relate and says why. A link to a note that doesn't exist, or with a vague reason, is never written.
- **`## Doubts`**: lines you marked `DOUBT: …` or `???`, with their page, so you find them before the next class.
- **The course page** lists the note under its lecture (or under "Handwritten notes" when no lecture matched), in a
  `<!-- kurooto:handwritten-notes -->` block. Your own text there isn't touched.

Notes written out before 0.5.8 get the same with `/handwritten link` (once: a note that has a Links section is
skipped, so running it again changes nothing). Every change keeps a before-copy; `/handwritten undo` puts the last
linking back (a file you edited since is left as it is).

**Into the concept graph (opt-in).** Add `"handwritten"` to `integrate.sources` (or tick "Read your handwritten notes"
on the Concept graph card) and each linked note is then read into the
[concept graph](notes-and-concept-graph.md#concept-graph) like a book: its concepts become notes (or lines on the ones
you have) whose "Seen in" points back at the handwritten note. Each note is read once; a page you change on your
tablet is read again. Notes with no subject are left out.

**From Telegram.**

| Command | What it does |
|---|---|
| `/handwritten` | writes out what's waiting now (PDFs too, without waiting for the night) |
| `/handwritten status` | how far it got, and files it couldn't do |
| `/handwritten retry` | tries the files that failed again |
| `/handwritten link` | links every written-out note that has no Links section yet (one message when they're done) |
| `/handwritten undo` | takes back the last linking (the note and the course page as they were) |

**Settings that matter** (Dashboard → Settings → Handwritten notes)

| Setting | Default | Effect |
|---|---|---|
| `handwritten.folder` | empty (`handwritten-inbox`) | where scans land |
| `handwritten.into` | empty (`handwritten/`) | where the notes go, inside your notes |
| `handwritten.local` | on | a model on this computer reads pages when there is one |
| `handwritten.local_model` | empty | your own Ollama model that reads pictures |
| `handwritten.cloud` | on | with no model here, Gemini reads them; off: they wait |
| `handwritten.pdf_hours` | `23:00-07:00` | when PDFs are read here (on the charger); empty: any time |
| `handwritten.max_pages` | 60 | pages written out per PDF |
| `handwritten.keep_original` | `copy` | `copy` (next to the note, or in your files folder) or `link` (leave it where it is) |
| `handwritten.dpi` | 110 | how sharp the page pictures are |
| `handwritten.link` | on | link each written-out note to its lecture, course page and concept notes (one AI request) |

**What leaves your computer.** Nothing when a model here reads the pages. Otherwise the pages go to Google (Gemini, your
key); on the free tier Google may use them to improve its products. For the linking, the written-out text, the titles
and opening lines of the notes it may relate to, and your subjects' names go to the AI you picked, like any request
(nothing leaves when that's a model on this computer; `handwritten.link` = `false`: no linking).

**Turn it off / undo.** Features → Handwritten notes → Turn off; the notes and copies stay. `handwritten.local` =
`false` sends everything to Gemini instead. `/handwritten undo` takes back the last linking; `handwritten.link` =
`false` stops linking.

## Check my draft

**What it does.** Before you hand something in, send it with "check this": a photo of a proof, a PDF, a `.tex`
derivation, an essay (`.md`, `.txt`, `.docx`), accounts working or a code file. Your AI marks what to look at, each
comment pointing at a line (`L12-14`) or a place on the page (`p2, the second displayed equation`):

- **gap**: a step is missing;
- **unclear**: a step can't be followed as written;
- **error**: something is false, miscalculated, or doesn't compile or run;
- **needs a reason**: a true claim that needs a justification it doesn't give.

It **never rewrites your work or gives a solution**: a comment that would hand over the fix ("replace it with...",
"the correct answer is...") is left out, and the message says how many were. An answer that doesn't come as comments is
never passed on.

**Turn it on.** It's part of the Research add-on: Features → Research add-on (it's on only when you turn it on).

**How to send it.**

| Where | How |
|---|---|
| Telegram | the file or photo with `check this` as its caption (or `check my proof for la`, `/check la the induction step`); or `check this` within 15 minutes of sending the file (`drafts.recent_minutes`) |
| The phone app | share the file with the note `check this`; or type `check this` in the chat just after sharing it |
| The dashboard | Study pane → COURSE → paste the file's path and **check**; or in the dashboard's chat `/check la ~/proof.tex` |

**Which course.** Named in the message ("for la", `/check la`), in the file's name or its folder, the class going on or
just over, or your only subject. When it can't tell, it asks once with your courses as buttons (and "Not for a
course").

**The course's AI policy.** Each course has one: **allowed**, **hints** or **off** (`/subject policy la hints`, or the
AI help box in the dashboard's Study pane). With **hints**, a comment only says where the problem is and what kind it
is, never how to fix it. With **off**, nothing is checked for that course and nothing goes to the AI. Not set counts
as allowed (the message reminds you to set it). The [Hint ladder](quiz-and-exams.md) goes by the same setting.

**Notes.** When the draft is lecture or class notes (a note of yours, or what the AI says are notes), the comments also
go into the matching lecture note, in a Kurooto block (`<!-- kurooto:draft-check -->`); your own text there never
changes, and checking again replaces the block (`drafts.note_block`).

**Limits.** A text file (up to 60,000 characters) goes in numbered line by line, so any AI can name lines. Photos and
PDFs need an AI that opens files itself (agy or Claude Code). At most 15 comments (`drafts.max_comments`).

| Setting | Default | Effect |
|---|---|---|
| `drafts.max_comments` | 15 | comments on one draft at most |
| `drafts.note_block` | on | notes that were checked: the comments also go in the matching lecture note |
| `drafts.recent_minutes` | 15 | "check this" after sending a file checks that file if it came this recently |

**What leaves your computer.** The draft and the course notes the AI reads go to the AI you picked.

**Turn it off / undo.** Features → Research add-on → Turn off. Delete a `kurooto:draft-check` block from a note if
you don't want it there.

## Course notes as one PDF

**What it does.** `/notes pdf la` makes one PDF of a course's notes: its course page, its lecture notes in date order,
and the concept notes they link (by `[[link]]`), each a section, with a table of contents. Your Markdown becomes LaTeX
(headings, lists, tables, code, links, and your maths as you wrote it) through a template, and Tectonic (or the LaTeX
already on your computer) makes the PDF. No AI is used and nothing in your notes changes.

**Where it comes.** Like other files: on Telegram, or a link in the phone app's chat. The `.tex` and the PDF are kept
where revision packs go (`<course>/course-notes-<course>.tex` in your notes); a file of yours with that name is never
written over. From the dashboard: Study pane → COURSE → **notes → pdf**.

**When the maths doesn't compile** (a macro of your own, say), the PDF is made again with the maths shown as written,
and the message says so. Images are named, not drawn.

**Your own template.** `/notes pdf template` puts a copy of the LaTeX template beside your study pack prompt
(`kurooto/course-notes-template.tex`) to edit; `%%COURSE%%`, `%%DATE%%` and `%%BODY%%` are filled in. Delete it to
go back to Kurooto's.

**No LaTeX here.** You get the `.tex`, and (with Skills on) a button to install Tectonic, a small LaTeX engine (about
25 MB, plus about 50 MB of LaTeX packages fetched the first time); the PDF follows once it's installed.

**What leaves your computer.** Nothing from Kurooto. Tectonic downloads the LaTeX packages it lacks (from github.com and
its own servers) the first time.
