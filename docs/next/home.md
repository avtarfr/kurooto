# home: docs to merge (MANUAL, Troubleshooting, CHANGELOG, PRIVACY, AGENTS)

## MANUAL: new and changed sections

### Backups (new, under Features)
Once a day, a zip of Kurooto's settings, data and state in a folder you pick: a folder on an external drive, or one
your computer already syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox), so the zip goes there too. The
last 7 are kept (`backups.keep`); Kurooto removes only its own older zips (`kurooto-backup-<date>-<time>.zip`), never
anything else in that folder.

**Set up:** Features → Backups → paste the folder's full path (the card lists cloud folders and drives it found on this
computer). It runs at 03:30 (`backups.when`); on a laptop it waits for the charger, and if a day went by without one
(the drive was unplugged, the laptop was off) it makes one within the hour once it can. `/backup` makes one now,
`/backups` lists them. From a terminal: `kurooto backup`, or `kurooto backup --to <folder>` for a one-off copy
somewhere else (handy before reinstalling).

**What's in it:** your settings, Kurooto's data (including the notes brain's index; `backups.index` off leaves it out:
smaller, but it has to be rebuilt) and its state (check-ins, deadlines, AI requests and answers, the schedule).
**Not in it, unless you turn them on in Settings:**
- `backups.notes`: your notes folder too (without `.git`). Turn it on if your notes aren't synced anywhere else.
- `backups.secrets`: your passwords and keys (bot token, API keys, sign-ins). Then **anyone with the zip can use
  them**: only for a folder that's yours alone. Without them, after a restore you sign in again where Kurooto asks.

The zip isn't encrypted.

**Putting one back:** `kurooto restore <zip>`. It shows what's in the zip and asks first; then it stops Kurooto, keeps a
copy of how things were (in Kurooto's data folder, `restore-safety/`), puts the backup's settings and data back, and
starts Kurooto again. Your notes are never overwritten: a note that's missing comes back; a note that's different now
is kept as it is, and the backup's copy goes into `restored-<date>/` in your notes folder. `--no-notes` leaves the
notes folder alone; `--no-start` doesn't start Kurooto afterwards; `--yes` doesn't ask. Restoring onto another kind of
computer (Windows ↔ Mac) works; the notes folder becomes this computer's default.

**Turn it off:** Features → Backups → Turn off. The zips already made stay where they are.

### Sync everything (new, under Features or "Telegram")
`/sync all` or "sync everything" on Telegram, or `kurooto sync` in a terminal, runs every sync that's on, one after
another: your notes with your repository, Google Classroom, your calendars, research project logs, your notes again
(to send up what the others just wrote), then the notes brain's index. A feature that's off is left out. It runs in
the background and you get one line each when it's done, e.g. `Calendar: ok, 23 events`. With Notes sync off, plain
`/sync` does the same.

### Notes sync (changed: add to the section)
Besides every 10 minutes: what an AI request writes in your notes is sent up about two minutes after it finishes (one
push for a burst of requests; `notes_sync.after_jobs`, 0 turns it off), and whatever is left goes up when Kurooto
stops (a shutdown, an update), unless it's paused. `/sync all` syncs everything (see Sync everything).

### Research (changed: replace the "Project logs" paragraph)
**Projects:** each project has a note in your notes, `research/<project>/index.md`, and `research/index.md` lists
them all. Add your code repositories on the Research tab or with `/repos add ~/code/my-model`; a repository's project
is its folder's name, or name it: `/repos add ~/code/model_v2 as Climate model` (several repositories can share a
project; `research.projects` in Settings holds the mapping). Every night each day's new commits become one line under
`## Log` in the project's note, e.g. `- **2026-10-20** | git:my-model — 3 commits: …`. Kurooto only adds lines: your own
text in these notes is never changed. (Logs from 0.1.0 in `research/<repository>-log.md` are left as they are.)

**Quiet projects:** when a project has had no commits for 4 days (`research.idle_days`; 0 never asks), Kurooto asks
once, at 18:00, what's up: **Busy**, **Working off-git**, **Remind me tomorrow** (a reminder comes the next day at
18:00) or **Pausing it**. The answer goes into the project's log. It asks again only after the next quiet stretch.

**Experiment runs (`kurooto runlog`):** log a training or simulation run into the project's notes, with the code's
exact state:
```
kurooto runlog start my-model --name lr-sweep --config '{"lr": 0.001}'
kurooto runlog metric loss=0.31 acc=0.88 --step 100
kurooto runlog note "diverged after step 800"
kurooto runlog end            # or --status failed
kurooto runlog ls
```
Each run is a folder `research/<project>/runs/<date>-<time>-<name>/` with `run.md` (what it was and how it went),
`config.json`, `meta.json` (git commit, branch, whether there were uncommitted changes), `diff.patch` (those changes,
so the exact code can be recovered), `metrics.jsonl` and `notes.md`; a row in `runs/index.csv`; and a line in the
project's log when it ends. The commands find the run from `--run <id>`, else `$KUROOTO_RUN`, else the one you started
last. It works without Kurooto running.

**Long jobs (`kurooto watch`):** `kurooto watch -- python train.py --epochs 50` runs the command (its output still shows
in your terminal) and messages you when it ends: done or failed, the exit code, how long it took and its last 10 lines
(`--lines 0` sends none). `--log my-model` also logs it as a run of that project (the job gets `$KUROOTO_RUN`, so it
can add metrics). If Kurooto isn't running, it shows on this computer only.

### Terminals (new, under Features)
Real terminals in the dashboard's **Terminals** tab: the AI program you use (agy, Codex or Claude Code), started in your
notes folder as you'd run it yourself; your usual shell (PowerShell on Windows); `kurooto ask` (plain English, like
Telegram); and Kurooto's log. Alt+1 to Alt+4 switch between them. They keep running when you close the page and show
where they were when you open it again; one that ended starts again when you press a key in it (or **restart**).

**Only turn this on if you're the only person who uses this computer:** anyone who can open your dashboard can type
into these terminals. The dashboard only answers this computer, needs a key only its own page gets, and refuses other
websites; on Linux, Kurooto also checks that each terminal request comes from your own user account and refuses it if
it can't tell.

**Turn it off:** Features → Terminals → Turn off (the terminals end).

### `kurooto top` (new, under "The dashboard" or "Where things are")
`kurooto top` is a status board in any terminal (Windows 10 and later, macOS, Linux): this computer (processor and
each core, memory, graphics card, disks, battery) and Kurooto (running or not, the battery mode, open questions, notes
sync and backup age, the features on, AI requests, what's scheduled next, recent events). `q` quits, `r` refreshes.
`kurooto top --once` prints one screen. It only reads, so it's safe while Kurooto works. `kurooto logs -f` follows
Kurooto's log.

### The dashboard (changed: add to the tab list)
**Terminals** (when the Terminals feature is on).

### Where things are (add rows)
| What | Where |
|---|---|
| Backups | the folder you picked (`backups.folder`); before a restore, a copy of how things were: `restore-safety/` in the data folder |
| Experiment runs | `research/<project>/runs/` in your notes |
| Watched jobs | `watch.log` in the state folder (time, exit code, duration, folder, command) |

## Troubleshooting rows

| What you see | What to do |
|---|---|
| `kurooto doctor`: Backups FAIL "the backup folder isn't there" | Plug the drive in (or sign in to the cloud app); the next backup comes within the hour. A drive that's unplugged for a day or two is only a note. |
| Backups: "not enough room in the backup folder" | Free space there, lower `backups.keep`, or turn `backups.index` off. |
| Restore went wrong | `kurooto restore <the zip in restore-safety/>` puts things back as they were before it. |
| Research: "repository folder missing" | You moved or deleted it: `/repos remove <folder>`, then `/repos add <new folder>`. |
| The Terminals tab says it's off, or a terminal won't type | Features → Terminals → Turn on. On Linux, a terminal from another user account is refused on purpose. |
| `kurooto watch` says "only shown on this computer" | Kurooto wasn't running: `kurooto start`. |

## CHANGELOG lines (0.2.0)
- Backups (new, off by default): a daily zip of Kurooto's settings, data and state (your notes and your keys only if
  you turn them on) in a folder you pick, such as an external drive or a cloud-synced folder; the last 7 kept;
  `/backup`, `kurooto backup`, and `kurooto restore <zip>`, which never overwrites a note. `kurooto doctor` says how old
  the last backup is.
- Sync everything: `/sync all`, "sync everything" or `kurooto sync` runs every sync that's on and reports one line each.
- Notes sync sends notes up about two minutes after each AI request, and when Kurooto stops.
- Research projects: a note per project (`research/<project>/index.md`) with a Log of each day's commits, a hub note
  listing them, `/repos add <folder> as <project>`, and a question when a project has gone quiet for 4 days. Project
  logs no longer go to `research/<repository>-log.md` (old ones are kept).
- `kurooto runlog`: experiment runs logged into your notes with their config, metrics and the code's exact git state.
- `kurooto watch -- <command>`: a message when a long job ends, with its exit code, duration and last lines.
- `kurooto top`: a status board in any terminal. `kurooto logs [-f]`: Kurooto's log.
- Terminals (new, off by default): your AI program, a shell, `kurooto ask` and the logs as real terminals in the
  dashboard (xterm.js 5.5.0, MIT, included).

## PRIVACY rows (the "Always" table)

| Feature | What leaves | Where to |
|---|---|---|
| Backups | a zip of Kurooto's settings, data and state (AI requests and answers, check-ins, deadlines, your profile reports); your notes and your keys only if you turn them on. Not encrypted | only the folder you pick; if your computer syncs that folder to a cloud (Google Drive, OneDrive, iCloud, Dropbox), that cloud |
| Research: `kurooto watch` | the command's name, exit code, duration and last lines (`--lines 0`: none) | Telegram (your own bot), like any message |
| Terminals, `kurooto top`, `kurooto runlog`, sync everything | nothing new (each sync sends what its own feature sends) | stays on your computer |

And under "Secrets": with `backups.secrets` on, your keys are copied into each backup zip (`secrets.json`), in plain
text; anyone who gets the zip can use them.

## AGENTS.md: rows for the Commands table

| Command | What it does | Safe to run? |
|---|---|---|
| `kurooto top --once` | one screen of the status board (this computer and Kurooto) | yes |
| `kurooto logs [-n N] [-f]` | the end of Kurooto's log (`-f` keeps following) | yes |
| `kurooto sync` | runs every sync that's on and prints one line each | yes |
| `kurooto backup [--to FOLDER]` | makes a backup zip now | yes; ask before `--to` a folder they didn't pick |
| `kurooto restore ZIP` | replaces Kurooto's settings and data with a backup's (keeps a copy first; notes only added) | **ask first** |
| `kurooto runlog …`, `kurooto watch -- CMD` | log experiment runs into their notes; message them when a long job ends | yes, when they asked |

And a `kurooto doctor` row: `Backups FAIL the backup folder isn't there` → the drive is unplugged or the cloud app
signed out; plug in or sign in, then `kurooto backup`.
