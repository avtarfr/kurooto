# Research

For anyone who reads papers or writes code for a project: a digest of new papers in your fields, a note per project
that keeps up with your code, a log of experiment runs, and a message when a long job finishes.

- [Turn it on](#turn-it-on)
- [The papers digest](#the-papers-digest)
- [Projects and their logs](#projects-and-their-logs)
- [Quiet projects](#quiet-projects)
- [Experiment runs (kurooto runlog)](#experiment-runs-kurooto-runlog)
- [Long jobs (kurooto watch)](#long-jobs-kurooto-watch)
- [Research time in the study tracker](#research-time-in-the-study-tracker)
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

## Experiment runs (kurooto runlog)

**What it does.** Logs a training or simulation run into the project's notes, with the code's exact state, so you
can always tell which code produced which numbers. It works from any terminal, without Kurooto running.

```
kurooto runlog start my-model --name lr-sweep --config '{"lr": 0.001}'
kurooto runlog metric loss=0.31 acc=0.88 --step 100
kurooto runlog note "diverged after step 800"
kurooto runlog end                  # or: --status failed / --status interrupted
kurooto runlog ls                   # the runs so far (ls my-model: one project's)
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

---

## What leaves your computer, and turning it off

**What leaves.** Your fields, keywords and searches go to the sources you pick (arXiv, bioRxiv, medRxiv, PubMed, the
feeds), all public; never your notes. With Chat on and the AI picking, the papers' titles and summaries and what you
work on go to the AI you picked. Commit messages and runs stay on this computer. `kurooto watch` messages go through
Telegram like any message.

**Turn it off.** Features → Research → Turn off: no digests, logs or questions. Project notes and log lines stay.
`research.save_note` = `false` stops the digest notes; take a search out of `research.feeds` to drop it; empty
`research.repo_runs` stops reading runs (lines already in your notes stay).
