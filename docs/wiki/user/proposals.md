# Projects and proposals

Kurooto's AI may think, draft and write freely, but only in a scratch folder of its own. Every change it wants to make
to your real files (your notes, a project, one of your skills) comes to you as a **proposal**: a title, a few lines on
what it changed and why, the files and the diff. Nothing of yours changes until you tap **Apply**.

- [Kurooto's scratch folder and proposals](#kurootos-scratch-folder-and-proposals)
- [Apply, Change, Discard and Undo](#apply-change-discard-and-undo)
- [Changes to your notes](#changes-to-your-notes)
- [Help with your project](#help-with-your-project)
- [Checks: tests and builds](#checks-tests-and-builds)
- [What the AI can and can't do here](#what-the-ai-can-and-cant-do-here)
- [Settings](#settings)

---

## Kurooto's scratch folder and proposals

When you ask for a change ("in my thesis add footnotes to chapter 2 citing refs.bib", "tidy my LA notes' headings"),
the AI gets a fresh folder in Kurooto's own data folder (`scratch/<id>`):

- **a project that's a git repository**: a git worktree of it on a new branch (`kurooto/<id>`), from your current
  commit. The AI sees the whole project as it's committed (your uncommitted changes aren't in it). It takes the disk
  space of one checkout of the project, until it's removed;
- **your notes, or a project folder that isn't git**: a mirror that starts empty. A file is copied in the first time
  the AI changes it, and the original as it was then is kept beside it.

For that request the AI may write there and nowhere else. It reads as always (your notes, Documents, Downloads ...),
plus the project. When it's done, Kurooto compares the scratch folder with the original and sends you the proposal:

```
Proposal for thesis: Footnotes in chapter 2 citing refs.bib
Added six footnotes to chapter 2, each citing an entry already in refs.bib; one claim had no source, so it's
marked with a TODO comment instead.
Files (2): chapter2.tex (+14 −6); refs.bib (+0 −0)
Checks passed in 41 s.
Apply makes one commit on your current branch (never a push); Undo reverts it.
```

On Telegram and in the phone app's chat the diff comes inside the message when it's short (`proposals.inline_lines`,
30 lines) and as a file when it's longer. The dashboard's **Proposals** page (`/proposals` in the browser, or the
dashboard's link) shows every waiting proposal with the whole diff, coloured.

A proposal that **deletes files** says so first, before anything else ("It deletes 2 files: ..."), and the dashboard
shows that line in red.

`/proposals` lists what's waiting (and what you applied lately, with Undo); `/proposals 2` shows the second one with
its diff and buttons.

Proposals made by work nobody was waiting for (a fix Dreaming proposes at night) don't come one by one: they're in the
morning message (Dreaming's, or with Dreaming off a short "Waiting for your OK" message at `proposals.morning`), and
Calm's daily limit and reasons apply to it like any message that comes by itself.

---

## Apply, Change, Discard and Undo

| Button | What happens |
|---|---|
| **Apply** | Your notes or a folder: the files are written, and their earlier versions are kept. A git repository: one commit on your current branch, with the title and summary as its message; never a push. |
| **Change** | Kurooto asks what to change; reply in plain words. The AI works again in the same scratch folder and the proposal comes back as a new version. |
| **Discard** | The scratch folder is deleted. Nothing of yours changed. |
| **Undo** (after Apply) | Notes and folders: the earlier versions are put back. A git repository: a revert commit (your history is never rewritten). |

Apply is one of the things that [never happen without your tap](ai-brains.md): the AI, a plain-English guess or a
schedule can't apply anything. Typed, it's `/proposals apply <id>`.

Apply refuses, and says why, when:
- a file it would change **changed since** the proposal was made (you edited it): tap **Change** to have it redone on
  the new version;
- in a git repository, you have **uncommitted changes in the same files** (or untracked files where it would add one):
  commit or stash them, then tap Apply again. Changes in other files are fine and stay as they are;
- the repository is **on no branch** (a detached HEAD) or **mid-merge, rebase or cherry-pick**.

Undo refuses when a file changed again after Apply (it would lose that change); it says where the earlier versions
are kept.

A proposal nobody answers goes after `proposals.keep_days` (7) days, with its scratch folder. Scratch folders are also
removed right after Apply or Discard.

---

## Changes to your notes

Ask in plain words: "tidy my LA notes' headings", "add a summary to this lecture note", "fix the links in my
probability notes". Kurooto runs it in a scratch copy of your notes and sends a proposal; nothing is rewritten before
you tap Apply. (Before 0.7.0 the AI changed the note directly.)

The same holds inside any other AI request: when the AI uses its tool for changing text that's already in a note,
the change goes into a scratch copy and becomes a proposal at the end of the request ("Proposed: the change to ...
waits for your OK"). Adding to a note and making a new note work as before (they never touch your text).

`proposals.notes_edits` = false turns this off (the AI then changes notes directly, keeping each note's previous
version, as in earlier versions).

---

## Help with your project

Dashboard → Features → **Help with your project**, then say which projects the AI may work on: none can until you
turn it on for that one.

Your projects are the folders Kurooto already knows: Research's repositories (`/repos add <folder> [as <project>]`),
the LaTeX documents you attached (`/latex add`, the Research add-on), and folders you add here.

| Command | What it does |
|---|---|
| `/project` | your projects, and which ones the AI helps with |
| `/project add <folder> [as <name>]` | a folder of yours as a project (typed only) |
| `/project help on <name>` / `off` | let the AI work on that project (off for every project at first) |
| `/project help <name> <what to do>` | `/project help thesis add footnotes to chapter 2 citing refs.bib` |
| `/project checks <name> <command>` | run that after the AI's changes (below); `off` stops it; with no command it shows what's set and a suggestion |

On the dashboard, the Proposals page has a box for it (pick the project, say what to do). Plain words work too, once the
project is on: "in my thesis add footnotes to chapter 2 citing refs.bib", "help with my
thesis: fix the failing test", "for my site, write the README's install section".

One request at a time per project; a second one says the first is still running (`/jobs` shows it).

---

## Checks: tests and builds

Off until you set a command per project (`/project checks thesis latexmk -pdf main.tex`,
`/project checks parser python -m pytest -q`). Then, after the AI's changes, Kurooto runs it in the scratch folder
and the proposal says "Checks passed" or "Checks failed" with the reason; the AI can also run it while it works.

A check runs:
- in the scratch folder, never in your project;
- with a time limit (`projects.check_timeout_s`, 300 seconds);
- **with no network**, and able to write only in the scratch folder: inside a sandbox (bubblewrap, `bwrap`, on Linux;
  macOS's own sandbox). Kurooto's settings and your keys folders (`~/.ssh`, `~/.gnupg` ...) are hidden from it.

Where there's no such sandbox (Windows, or Linux without bubblewrap: `sudo apt install bubblewrap`, `sudo pacman -S
bubblewrap`, `sudo dnf install bubblewrap`), checks don't run, and the proposal says so.

A git worktree has only committed files: a check that needs something you don't commit (a virtual environment, a
build folder) should name it by its full path in your project.

---

## What the AI can and can't do here

- It writes only in its scratch folder. A Kurooto tool asked to write anywhere else refuses, and the proposal says
  what it tried ("Refused while it worked: ..."). Claude Code gets permissions for that one run that allow editing
  only the scratch folder. agy's own file permissions are one list for every run, so for agy the scratch folder is
  kept by Kurooto's tools and by running it there; if anything in the original changed while it worked (you, a sync,
  or the AI writing where it shouldn't), the proposal names those files.
- It never pushes, sends or publishes anything, and checks have no network.
- Files of keys and passwords (`.env`, `*.pem`, `*.key`, `id_rsa`, `credentials*.json` ...) are never copied into a
  scratch folder, read through Kurooto's tools there, or part of a proposal. Hidden files are left out of notes
  proposals.
- Nothing is deleted from your files except by a proposal you applied, which said so at the top.
- A proposal is at most `proposals.max_kb` (400 KB of diff) and `proposals.max_files` (60 files): ask for a smaller
  part if it's bigger.

---

## Settings

| Setting | Default | What it does |
|---|---|---|
| `proposals.notes_edits` | `true` | a change to text already in your notes becomes a proposal |
| `proposals.keep_days` | `7` | a proposal nobody answered goes after this many days, with its scratch folder |
| `proposals.max_kb` | `400` | a bigger change isn't proposed |
| `proposals.max_files` | `60` | nor one that touches more files |
| `proposals.inline_lines` | `30` | a diff up to this many lines comes inside the message |
| `proposals.morning` | `daily 07:30` | the night's proposals, when Dreaming is off |
| `projects.folders` | `{}` | your own project folders (`/project add`) |
| `projects.help` | `[]` | the projects the AI may help with |
| `projects.checks` | `{}` | project → its check command |
| `projects.check_timeout_s` | `300` | a check is stopped after this long |
| `projects.effort` | `high` | how hard the AI thinks about project work |
