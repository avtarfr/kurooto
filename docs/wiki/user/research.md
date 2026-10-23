# Research

For anyone who reads papers or writes code for a project: a digest of new papers in your fields, a note per project
that keeps up with your code, a log of experiment runs, and a message when a long job finishes.

- [Turn it on](#turn-it-on)
- [The papers digest](#the-papers-digest)
- [Projects and their logs](#projects-and-their-logs)
- [Quiet projects](#quiet-projects)
- [Meetings with someone: briefs, minutes and action items](#meetings-with-someone-briefs-minutes-and-action-items)
- [Experiment runs (kurooto runlog)](#experiment-runs-kurooto-runlog)
- [Long jobs (kurooto watch)](#long-jobs-kurooto-watch)
- [Research time in the study tracker](#research-time-in-the-study-tracker)
- [The Research add-on: run compare and the LaTeX tracker](#the-research-add-on-run-compare-and-the-latex-tracker)
- [Settings](#settings)
- [What leaves your computer, and turning it off](#what-leaves-your-computer-and-turning-it-off)

---

## Turn it on

Dashboard → Features → **Research**. Its card asks for "What I work on" (a sentence or two) and a few keywords to
start with; then pick your fields and sources on the dashboard's **Research** tab. It needs at least one source or
one repository before it counts as ready. Nothing to install. With **Chat** on, the AI picks the papers that matter to
you and says why.

---

## The papers digest

**What it does.** New papers from the sources you choose, as one message, weekly by default (Monday 08:00).

**On the dashboard: the Research tab** (Alt+R).
1. **What I work on**: a sentence or two ("graph neural networks for molecules"). With Chat on, the AI uses it, and
   your notes, to pick the most relevant papers and say in one line why each matters to you.
2. **Your sources**, each with a **remove** button. Start from a **quick pick** (machine learning, language models
   and NLP, computer vision, robotics, security and privacy, algorithms, probability and statistics, quantum physics,
   astrophysics, materials, earth and climate, economics, quantitative finance, neuroscience, genomics, ecology and
   evolution, epidemiology, psychology and psychiatry), or **add a source**:

   | Source | What you pick |
   |---|---|
   | **arXiv** | any of its 155 fields (maths, physics, computer science, statistics, quantitative biology and finance, economics, electrical engineering); type in the box to find one ("number theory", "galaxies") |
   | **bioRxiv** | biology preprints, by subject area (neuroscience, genomics, ecology...) |
   | **medRxiv** | medical preprints, by subject area (epidemiology, oncology, psychiatry...) |
   | **PubMed** | published biomedical papers for a search; PubMed's own search words work (`sleep AND adolescents`) |
   | **A feed** | any journal's or blog's RSS or Atom address (`https://...`); most journals have one |

   Add **keywords** to any source (except PubMed, whose search already narrows it) to keep only papers that mention
   one of them in the title or abstract. **Preview** shows what a source would find this week (the first 10, and how
   many) before you **Add** it.
3. **The digest**: weekly (which day) or daily, at what time, up to how many papers (1 to 30), and whether **the AI
   picks and says why**. **Save** keeps it; **Send a digest now** tries it at once ("Looking now; the digest comes on
   Telegram in a minute or two").

**From Telegram.**

| Command | What it does |
|---|---|
| `/papers` | The digest now ("N new papers found."; the digest itself follows) |
| `/feeds` | Your sources and when the digest comes (change them on the Research tab) |
| `/topics` | Your quick keywords searched across all of arXiv |
| `/topics add graph neural networks` | Adds one |
| `/topics remove graph neural networks` | Takes one off |
| `/zotero` | How papers go into Zotero now (the app, or the web API), and how many went in |
| `/zotero key <key>` | Keeps your Zotero web API key (`/zotero key off` removes it) |
| `/zotero 3` | Puts paper 3 of the last digest into Zotero (the number on its button) |
| `/zotero links` | Links your reading notes to the Zotero items of the papers they cite, now |

**What a digest looks like.**
- With **Chat on** and more new papers than your limit: the AI's pick of the most relevant, each with its title, link
  and one line on why it matters to you, then one line listing others worth a glance.
- Otherwise: the newest papers as they are (title, first authors, link), and "...and N more."
- A paper is sent only once: a paper you've had before never comes again, from any source.
- A source that couldn't be reached is named at the end ("Couldn't reach: ...").
- No new papers: nothing comes, unless a source failed, in which case you get "No new papers this time" with which one
  failed.

**A copy in your notes** (`research.save_note`, off). On: each digest is also kept as `inbox/papers-<date>.md`, every
new paper grouped by source with its first lines, and the message says where. A second digest the same day adds to
the same note. Keep what matters as a note of its own; the digest note is yours to delete.

**arXiv in its own words.** A source in `research.feeds` (Dashboard → Settings → research) can be a search written
the way arXiv's API takes it, with a name that heads its part of the digest:

```json
{"type": "arxiv", "name": "Molecules", "query": "abs:\"graph neural network\" AND (abs:molecule OR abs:protein)"}
```

`ti:` searches titles, `abs:` abstracts, `all:` everything, `cat:` a category; combine with `AND`, `OR`, `ANDNOT` and
brackets, and add `"categories"` to narrow it. A search with an unclosed bracket or quote is refused. Kurooto asks
arXiv once every 3 seconds, as arXiv asks, so several arXiv sources take a little longer.

**Limits.** Up to 30 sources, 20 keywords per source, 30 arXiv fields per source. Each digest looks back 7 days
(`research.window_days`). On battery (saver mode) the scheduled digest waits for the charger. A paper counts as sent
once its digest reaches you: if the AI's pick fails, those papers come again in the next digest (while they're still
in its window).

### Zotero

**What it does.** Each paper in the digest comes with a **Zotero** button: one tap puts it in your Zotero library
(title, authors, abstract, date, link, arXiv id or DOI), and a second tap doesn't add it twice. Your reading notes that
link the paper (its arXiv, bioRxiv, medRxiv, PubMed or feed link) get a Kurooto block with a `zotero://select` link
that opens the item in Zotero, at once and in a nightly pass; nothing of yours in the note changes.

**Two ways in** (`research.zotero`, `auto`):
- **The Zotero app** on this computer, when it's running: through its connector at `127.0.0.1:23119`, as the browser
  extension does. Nothing leaves your computer from Kurooto. For notes to link the item, turn on Zotero's local API
  (Zotero 7: Settings → Advanced → "Allow other applications on this computer to communicate with Zotero").
- **Zotero's web API** with a key: make one at zotero.org/settings/keys with library and write access, then
  `/zotero key <key>` (or Research's setup form on the dashboard). It's kept with your other secrets, never in
  settings.

`auto` uses the app when it's running, else the web API when there's a key; `app` or `web` only that one; `off` no
buttons. Without either, the digest has no Zotero buttons.

---

## Projects and their logs

**What it does.** Each research project gets a note in your notes, `research/<project>/index.md`
(`projects/<project>/index.md` in the zettelkasten layout), and the research hub `research/index.md` lists them all.
Every night at 23:30 (`research.log_when`), each day's new commits in your code repositories become one line under
`## Log` in their project's note:

```
- **2026-10-20** | git:my-model — 3 commits: fix the loss; add the sweep; tidy plots
```

At most three commit messages are shown per day, then "+N more". Kurooto only reads your repositories (it never
changes them), and in your notes it only adds lines: your own text is never changed. The first time, only the last
day's commits are logged.

**Adding repositories.**

| Where | How |
|---|---|
| Dashboard → Research tab → Projects | type the folder, **Add**; **remove** takes one off |
| Telegram | `/repos add ~/code/my-model` |
| Telegram, naming the project | `/repos add ~/code/model_v2 as Climate model` (several repositories can share one project) |
| Telegram | `/repos remove ~/code/my-model`; `/repos` alone lists them with their project |

A repository's project is its folder's name unless you name it; the mapping is the setting `research.projects`. The
folder has to be a Git repository when you add it ("That folder isn't a git repository"). A folder that was added
and isn't a Git repository yet (only a proposal, say) stays a project with no commits to follow: `kurooto doctor` notes
it ("isn't a git repository (no commits to follow)"), which isn't a problem; `git init` it to follow it.

**Logs from 0.1.0** in `research/<repository>-log.md` are left as they are.

`/sync all` also brings the project logs up to date ([Sync everything](notes-and-concept-graph.md#sync-everything)).

---

## Quiet projects

When a project has had no commits or runs for 4 days (`research.idle_days`), Kurooto asks once, at 18:00 (never in
your night hours): "No commits to my-model for 5 days. What's the plan?" with these buttons:

| Button | What happens |
|---|---|
| **Busy** | Noted in the project's log |
| **Working off-git** | Noted in the project's log |
| **Remind me tomorrow** | With Phone calls on, a call tomorrow at 18:00 about it (a missed call becomes a message); otherwise a message then. `research.remind_by_call` = `false` always makes it a message |
| **Pausing it** | Noted; it won't ask again until there are new commits |

You can also reply in your own words; whatever you answer goes into the project's log as
`- **<date>** | you — <your answer>`. It asks again only after the next quiet stretch. Unanswered, the question
expires after 3 days. Like any question, you can answer it on the phone app or on a call.

`research.idle_days` = 0 never asks. **Less of this** on the message offers **Fewer** (asks half as often) and
**Stop** ([Messages it sends](messages-it-sends.md)).

---

## Meetings with someone: briefs, minutes and action items

Any meeting you have with someone a project note is **With**, whatever they are to you (supervisor, guide, manager,
coach): the project note keeps the meeting's lines, a brief comes the evening before, and what you send after it becomes
minutes.

**Setting it up, by saying it** (in the chat or your journal; one line back with Undo, `/inferred` lists them):

| You say | Kurooto |
|---|---|
| "I got a project under Prof Lena Ortiz on glacier flow" | starts the note *Glacier flow* with "With: Prof Lena Ortiz (supervisor)" |
| "I meet my manager Mira Castell every Monday at 10 about onboarding" | puts "With: Mira Castell (manager)" and "Meets: every Mon 10:00" in the project note *Onboarding* (made if missing; without a topic, *Meetings with Mira Castell*) |
| "We meet my guide Dr Okafor every Tuesday at 4" | the weekly time for the project that's With Okafor already ("I have a weekly call with ... on Fridays at 5" works too) |
| "Met Okafor today, we fixed the drift" | a dated line under the note's Meetings, and "Last met: <date>" |
| "I have a meeting with Ortiz on Friday at 4" | a "Meeting: Prof Lena Ortiz" deadline, for a one-off meeting |

Someone unknown with no role or title ("I meet Sam every Friday") sets nothing up. The role is your own word, from "my
<role>"; you can change it in the note.

**In the project note**, these lines live in Kurooto's own block, the only part of the note it rewrites:

```
<!-- kurooto:meeting -->
With: Mira Castell (manager)
Last met: 2026-10-19
Meets: every Mon 10:00
<!-- /kurooto:meeting -->
```

A note from before 0.5.20 keeps its own "With:" and "Last met:" lines (they're yours now, and never changed); the block
goes under them, and the newest "Last met" date in the note is the one that counts.

**The evening before** (20:00, `deadlines.meeting_brief`), for a weekly meeting or a "Meeting:" deadline, a **meeting
brief**: what the project's Log has since you last met, its open "## Next steps", the last Meetings line and the last
minutes' first points. Once per meeting.

**After the meeting** (needs Chat on: your AI writes the minutes, in one request), any of these becomes minutes:

- a voice note sent within 3 hours of the meeting's start (`meetings.after_h`);
- a typed note of 20 words or more sent then, which nothing else (a reminder, a /command) answers;
- a message that starts "about the meeting with Okafor:", "notes from today's meeting:" (any time; a colon or dash
  after it).

The reply says which meeting it took it for, with **Not about the meeting**: that takes the minutes out of the note and
sends your message to your AI as a plain message. The minutes go under the note's `## Meetings`, in a block for that
day (a second note the same day is added to the same minutes):

```
<!-- kurooto:minutes-2026-10-19 -->
**Minutes, Mon 19 Oct 2026, with Mira Castell**
- Went through the onboarding plan
Decisions:
- Start with the support queue
Action items:
- Write the access request (by 2026-10-21)
<!-- /kurooto:minutes-2026-10-19 -->
```

If your AI can't answer, your notes go into that block as you sent them, so nothing is lost. "Last met" moves to the
meeting's day.

**Action items.** They're added as `- [ ]` lines in Kurooto's block under `## Next steps` (made if missing; tick or
edit them there, they're kept as you leave them), and come back as buttons, on Telegram and in the phone app's chat:

| Button | What happens |
|---|---|
| **Add 1: ...** | that item becomes a deadline: on the date said in the meeting (17:00), else at your next meeting with them, else a week on. Nothing is added without this tap |
| **None** | no deadlines; the items stay under Next steps |
| **Later** | they come back the next evening, with the briefs |

Four items get buttons at a time (the rest are in the note). `meetings.minutes` = `false` turns minutes off;
`meetings.after_h` sets the window after a meeting.

---

## Experiment runs (kurooto runlog)

**What it does.** Logs a training or simulation run into the project's notes, with the code's exact state, so you
can always tell which code produced which numbers. It works from any terminal, without Kurooto running.

```
kurooto runlog start my-model --name lr-sweep --config '{"lr": 0.001}'
kurooto runlog metric loss=0.31 acc=0.88 --step 100
kurooto runlog note "diverged after step 800"
kurooto runlog end                  # or: --status failed / --status interrupted
kurooto runlog ls                   # the runs so far (ls my-model: one project's)
kurooto runlog diff A B             # two runs side by side, into the notes (the Research add-on)
```

| Command | Options |
|---|---|
| `start <project>` | `--name` (default: the repository's name), `--config` (a JSON object), `--repo` (the code's folder; default: where you are). Prints the run's id |
| `metric k=v ...` | `--step N`, `--run ID` |
| `note TEXT` | `--run ID` |
| `end` | `--status ok|failed|interrupted` (default `ok`), `--run ID` |
| `ls [project]` | |

Without `--run`, the commands use `$KUROOTO_RUN`, else the run you started last on this computer.

**What it writes.** A folder `research/<project>/runs/<YYYYmmdd-HHMMSS>-<name>/` in your notes with:

| File | What's in it |
|---|---|
| `run.md` | what it was (folder, Git commit and branch, config) and, at the end, how it went |
| `config.json` | the config you gave |
| `meta.json` | Git commit, branch, whether there were uncommitted changes, start, end, duration, status |
| `diff.patch` | the uncommitted changes at the start (up to 2 MB), so the exact code can be recovered |
| `metrics.jsonl` | one line per `metric` |
| `notes.md` | your notes |

Plus a row in `runs/index.csv`, and a line in the project's Log when it ends.

**From Python.** A run is a `with` block:

```python
from kurooto.runlog import Run

with Run("lr-sweep", config={"lr": 1e-3}, project="my-model") as run:
    for step in range(n_steps):
        run.log(step=step, loss=loss)
    run.note("diverged after step 800")
```

It ends as `ok`, `failed` (an exception: its traceback goes into the run's files, and the exception still stops your
script) or `interrupted` (Ctrl+C). With `project=` (or `$KUROOTO_PROJECT`) the run goes into your notes as above.

**Runs kept in your repository.** Without a project, the run stays with your code: a `runs/` folder where the script
starts (`$RUNLOG_DIR` to put it elsewhere), with the same files plus the host, Python version and command line, and a
row in `runs/index.csv`. For repositories you added with `/repos add`, Research reads that file every night, and each
new run becomes a line in the project's Log:

```
- **2026-10-20** | run:my-model/20261020-101500-lr-sweep — ok after 41m10s (step=900, loss=0.12)
```

The first time, only the last 30 days' runs. `research.repo_runs` is the folder's name (`runs`; empty: don't read
them).

---

## Long jobs (kurooto watch)

**What it does.** Runs a command and messages you when it ends.

```
kurooto watch -- python train.py --epochs 50
kurooto watch --lines 0 -- make all
kurooto watch --log my-model -- python fit.py
```

- Its output still shows in your terminal as it runs.
- When it ends you get "Job finished": done, failed or stopped, the exit code, how long it took and its last 10 lines
  (`--lines N`; `--lines 0` sends none). Colours and progress-bar redraws are cleaned out of those lines.
- A job that **failed** is sent as urgent, so it gets through focus time.
- `--log <project>` also logs it as a run of that project; the job gets `$KUROOTO_RUN`, so it can add metrics with
  `kurooto runlog metric`.
- If Kurooto isn't running, the message shows on this computer only.
- Every watched job is listed in `watch.log` in Kurooto's state folder (time, exit code, duration, folder, command).

---

## Research time in the study tracker

With the [Study tracker](books-and-study.md) on, a window that names one of `study.research_paths` (words, or folders
matched by their name, e.g. `~/code/my-model`) counts as **Research**; with Research on, its projects' names and
repository folders count too.

---

## The Research add-on: run compare and the LaTeX tracker

**What it is.** The narrower research tools, kept out of the everyday student features in one bundle: **run compare**
and the **LaTeX writing tracker**, plus the concept graph's **notation crosswalk** (a Notation table when two sources
write a concept differently), and **Check my draft** ([books-and-study.md](books-and-study.md#check-my-draft)). It's
off until you turn it on, and it doesn't need the papers digest (the Research feature) to be on.

**Turn it on:** Dashboard → Features → under **Add-ons**, **Research add-on** → **Turn on**. That one switch turns the
whole group on. Its card then has a switch for each part (Run compare, LaTeX tracker, Notation crosswalk, and each research tool in
the bundle); a part you switch off stays off the next time you turn the add-on on. **Turn off** turns the whole group off;
your notes and files stay as they are.

### Run compare

**What it does.** Puts two experiment runs (logged with `kurooto runlog`, `kurooto watch --log` or
`kurooto.runlog.Run`) side by side, and writes the comparison into the project's notes:

- **Config:** each key that differs (nested keys as `opt.lr`), and keys only one run has ("(not set)").
- **Code:** the diff between the two runs' git commits (`git diff`, read-only: nothing is checked out or changed in
  your repository), how many commits apart they are, and whether either run had uncommitted changes (its
  `diff.patch`).
- **Metrics:** each metric's last and lowest value in both runs, and the change (with the percentage).
- **Curves:** each metric over the steps, both runs on one plot, as a picture when Kurooto's Python has matplotlib;
  otherwise a sparkline per run (`loss A ▇▆▅▃▂▁ 1 → 0.2`), on one scale so the two compare at a glance.

| Where | How |
|---|---|
| Telegram or the phone app | `/runs`: the ten most recent runs, numbered |
| | `/runs compare 2 1`: those two (by number in `/runs`, or by id, or a unique piece of an id) |
| | `/runs compare`: the last two runs of the newest run's project |
| A terminal | `kurooto runlog diff 20261020-101500-lr-sweep 20261021-090000-lr-sweep` (pieces of the ids work too) |

The answer is one line ("2 config changes (lr 0.001 → 0.01); my-model: 3f2a… → 9c1d… (2 commits after A), 1 file
changed; loss 0.31 → 0.12 (-61%)") and where the comparison is. In your notes:

- `research/<project>/runs/compare/<A>--<B>.md`: the whole comparison (and `<A>--<B>.png` beside it with matplotlib).
- In the project's note, a block **Runs compared** with the last ten comparisons, newest first, each linked.

Kurooto writes only inside its own marked blocks (`<!-- kurooto:run-compare -->`); comparing the same two runs again
replaces that block, and your own text in these notes is never changed. Runs kept in a repository's `runs/` folder
(of a repository you added with `/repos add`) can be compared too; their comparison goes to that repository's project.

### The LaTeX writing tracker

**What it does.** Every night it builds the LaTeX documents you attached and keeps what each build found:

- **errors**, with the line they're on;
- **undefined references** (`\ref` to a label that isn't there);
- **missing citations** (`\cite` keys your `.bib` doesn't have);
- **words written**: today's word count less yesterday's. The count is an estimate, like texcount's: the prose of the
  document and the files it takes in with `\input`, `\include` or `\subfile`, without the preamble, comments, maths
  or commands.

In the morning, one line comes **only when something broke or you wrote something**, e.g. "LaTeX: thesis: 1 error:
Undefined control sequence. (line 12); missing citation smith2020; +412 words. (/latex for the rest)". Quiet nights
send nothing.

**Attaching a document** (you have to type it; Kurooto never looks for LaTeX on your disk):

| Command | What it does |
|---|---|
| `/latex add ~/papers/thesis` | Follows the document in that folder (the `.tex` with `\documentclass`; with several it picks `main.tex`, `thesis.tex` or `paper.tex`, or asks you to name it) |
| `/latex add ~/papers/thesis chapter-draft.tex` | Follows that file |
| `/latex` | Each document's last build: errors, undefined references, missing citations, words and the change |
| `/latex build` | Builds them now; the result comes as a message |
| `/latex remove ~/papers/thesis` | Stops following it (your files stay as they were) |
| `/latex install` | Installs Tectonic when there's no LaTeX on this computer |

**How it builds.** With **Tectonic** (the small LaTeX program revision packs use) in its safe mode, without shell
escape; without Tectonic, with your computer's own LaTeX (`latexmk` or `pdflatex`, shell escape off). The build goes to
Kurooto's own cache folder: no `.aux`, `.log` or `.pdf` appears in your folder. A build that takes over 15 minutes
(`research_addon.latex_timeout_min`) is stopped and counts as an error. On battery, the nightly build (and its morning
line) waits for the charger.

**A BibTeX entry for a missing citation.** Under the morning line (or after `/latex`), **BibTeX for smith2020**
asks your AI which work the key most likely is, from the key and the sentence it's cited in. The suggestion comes as
a message with **Add to refs.bib** and **Discard**: nothing is written until you tap **Add**, and then the entry goes at
the end of the `.bib` the document names (`\bibliography` or `\addbibresource`), with a comment saying your AI
suggested it, so check it against the paper. A key that's in the `.bib` already is never added twice. This needs
**Chat** on.

---

## Settings

Dashboard → Settings → research (most of these are also on the Research tab):

| Setting | Default | Effect |
|---|---|---|
| `research.about` | empty | What you work on; the AI uses it to pick papers |
| `research.feeds` | `[]` | Your sources |
| `research.topics` | `[]` | Quick keywords searched across all of arXiv (`/topics`) |
| `research.papers` | `weekly mon 08:00` | When the digest comes: `daily HH:MM` or `weekly <day> HH:MM` |
| `research.max_papers` | `8` | Papers per digest (1 to 30) |
| `research.rank` | on | With Chat on, the AI picks and says why; off: the newest as they are |
| `research.window_days` | `7` | How far back each digest looks |
| `research.save_note` | off | Also keep each digest as `inbox/papers-<date>.md` |
| `research.repos` | `[]` | Your code repositories |
| `research.projects` | `{}` | Repository folder → project name |
| `research.log_when` | `daily 23:30` | When commits and runs become log lines |
| `research.idle_days` | `4` | Days without commits before the quiet-project question; 0 = never |
| `research.idle_when` | `daily 18:00` | When that's checked |
| `research.remind_by_call` | on | "Remind me tomorrow" is a call (with Phone calls on) |
| `research.repo_runs` | `runs` | The folder in each repository where scripts keep their runs; empty = don't read |
| `research.zotero` | `auto` | Papers into Zotero with one tap: `auto`, `app`, `web`, `off` ([Zotero](#zotero)) |
| `research.zotero_links` | on | Notes that link a paper you put in Zotero get a link to its Zotero item |
| `research_addon.run_compare` | on | Run compare (a part of the Research add-on; its card switches it) |
| `research_addon.latex` | on | The LaTeX tracker (a part of the Research add-on) |
| `research_addon.latex_repos` | `[]` | The documents you attached with `/latex add` |
| `research_addon.latex_when` | `daily 03:30` | When the nightly LaTeX build runs |
| `research_addon.latex_morning` | `daily 08:00` | When the morning line comes (only when a build broke or you wrote) |
| `research_addon.latex_timeout_min` | `15` | A build that takes longer is stopped and counts as an error |
| `research_addon.members_off` | `[]` | Research tools in the bundle you switched off on its card |
| `meetings.minutes` | on | Notes you send after a meeting become minutes through your AI ([Meetings](#meetings-with-someone-briefs-minutes-and-action-items)) |
| `meetings.after_h` | `3` | Hours after a meeting's start that a voice note or a long typed note counts as notes from it |

---

## What leaves your computer, and turning it off

**What leaves.** Your fields, keywords and searches go to the sources you pick (arXiv, bioRxiv, medRxiv, PubMed, the
feeds), all public; never your notes. With Chat on and the AI picking, the papers' titles and summaries and what you
work on go to the AI you picked. Notes you send after a meeting go to the AI you picked, to be written up as minutes
(a voice note goes to Google first to be written out, as any voice note does). Commit messages and runs stay on this
computer. `kurooto watch` messages go through
Telegram like any message. A paper you tap into Zotero goes to the Zotero app on this computer, or, with your key, to
Zotero's web API (`api.zotero.org`): only its public details. The Research add-on: run comparisons and LaTeX builds
stay on this computer; Tectonic fetches LaTeX packages it lacks from its public server (nothing of yours is sent); a
BibTeX suggestion, only when you tap for one, sends the citation key and the sentence it's in to the AI you picked.

**Turn it off.** Features → Research → Turn off: no digests, logs or questions. Project notes and log lines stay.
`research.save_note` = `false` stops the digest notes; take a search out of `research.feeds` to drop it; empty
`research.repo_runs` stops reading runs (lines already in your notes stay). `research.zotero` = `off` drops the Zotero
buttons, `/zotero key off` removes the key; delete a `kurooto:zotero` block from a note if you don't want it. The
Research add-on: Features → Research add-on → **Turn off** (or a part's switch on its card); comparisons in your notes
and entries you added to a `.bib` stay.
