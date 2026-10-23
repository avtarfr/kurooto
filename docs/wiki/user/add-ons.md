# Add-ons, scripts and other programs

**This page is optional.** Everything Kurooto does for you works without it. Read on if you want to add your own
features, have your own scripts message you or ask you things, or let other AI programs use Kurooto. Some of it needs
a terminal; none of it needs you to be a programmer, except writing a Python add-on feature.

- [Your add-ons (your own features, skills and prompts)](#your-add-ons)
- [Add-ons by link (someone else's, from a git address)](#add-ons-by-link)
- [Official add-ons (published with Kurooto, one tap to add)](#official-add-ons)
- [Night performance (the highest performance mode during the night's work)](#night-performance)
- [Scripts and programs talking to Kurooto](#scripts-and-programs-talking-to-kurooto)
  - [kurooto notify](#kurooto-notify-send-yourself-a-message) ·
    [kurooto send](#kurooto-send-send-yourself-a-file) · [kurooto note](#kurooto-note-a-quick-note) ·
    [kurooto ask](#kurooto-ask-plain-english-in-a-terminal) · [kurooto ask-me](#kurooto-ask-me-ask-yourself-a-question) ·
    [kurooto ask-approval](#kurooto-ask-approval-a-yes-or-no-before-a-script-acts) ·
    [kurooto call](#kurooto-call-ring-your-phone) · [kurooto watch](#kurooto-watch-a-message-when-a-long-job-ends)
- [Kurooto's tools in other AI programs (kurooto mcp)](#kurootos-tools-in-other-ai-programs-kurooto-mcp)
- [Your skills in other AI programs](#your-skills-in-other-ai-programs)
- [The reserve: Kurooto's state as files for AI programs](#the-reserve-kurootos-state-as-files-for-ai-programs)
- [When something looks wrong](#when-something-looks-wrong)

All of these commands need Kurooto running (`kurooto on`), except `kurooto addons`, `kurooto note`, `kurooto watch` (which then only
shows its message on this computer) and `kurooto reserve`. Every command is also listed in [commands.md](commands.md).

---

## Your add-ons

(Not to be confused with the **add-ons that come with Kurooto**, listed apart on the Features page and off until you
turn them on: Exam season, Learns from its own work, and the **Research add-on**, one switch for a group of research
tools: [Research](research.md#the-research-add-on-run-compare-and-the-latex-tracker).)

**What it does.** Lays a folder of yours over Kurooto: extra features, skills and prompts, and default settings. For
example a private repository you cloned, so you can keep things for yourself while running the normal Kurooto.
Updates never change this folder.

**Turn it on:** Dashboard → Features → **Your add-ons** → **Set up**, paste the folder's full path, Save, then Turn on.
The folder can't be inside Kurooto's own folders (updates replace those).

**What the folder may hold:**

| | What it does |
|---|---|
| `modules/*.py` | extra features (Python classes based on Kurooto's `Module`, see `src/kurooto/modules/base.py`). They appear on the Features page under **Your add-ons**, each off until you turn it on. Files starting with `_` are helpers the others can import (`from kurooto_addons import _helpers`). |
| `skills/<name>/SKILL.md` | extra [skills](skills-and-routines.md), written like Kurooto's own. A skill of the same name in your notes (`kurooto/skills/`) still wins. |
| `prompts/*.md` | extra prompts; `/prompts` lists them as `add-ons/<name>` |
| `settings.json` | default settings laid under yours, e.g. `{"checkins": {"times": {"evening": "21:30"}}}`. What you set yourself still wins. It can't turn features on, move the add-ons folder or touch Profile sync. |

**This runs your own code.** The Python files run inside Kurooto with its access to this computer. Only use add-ons
you wrote or trust. `overlay.code` off keeps the skills, prompts and settings and skips the Python.

**When an add-on breaks.** It never stops Kurooto: a file that fails to load is skipped, and an add-on that fails
while running is cut off from that one request. Both are logged and shown by `/addons` on Telegram and by
`kurooto doctor`. **Restart Kurooto after editing an add-on's code** (`kurooto stop`, then `kurooto start`).

**From Telegram:** `/addons` lists your add-ons: where they come from, each feature with whether it's on, whether
there are skills, prompts and settings, and the last problems.

**What an add-on feature can do** (for people writing one; details at the top of `src/kurooto/core/overlay.py`):
everything a built-in feature can (commands, buttons, plain-English requests, tools for the AI and calls, settings, a
health check), plus:

- `processes = ("my-bot", "bots/reply.js")`: programs that are its own work (a name, or a piece of the command line).
  Its dashboard cell and its line in `kurooto top` then show their cpu, memory, uptime and threads, and turn grey
  ("not running") when none runs. `processes_intermittent = True` for programs that only run now and then: with none
  running the cell says "idle", not grey.
- `classify_intent(text, intents)`: picks which plain-English request a message is, before Kurooto's own patterns
  (for example a small local model that knows how you talk). Kurooto only uses an answer that names a request that's
  on, is at least 60% sure, and comes within 2 seconds (`classify_timeout` on the class, up to 10). Anything else falls
  through to the usual patterns. Long messages and several requests in one still go to the AI.
- `status_lines()`: extra lines at the end of `/status`.
- `doctor_checks()`: extra lines for `kurooto doctor`, each `(name, ok, detail)`; a failing one counts as a problem.

**Settings that matter** (Dashboard → Settings → Your add-ons):

| Setting | Default | Effect |
|---|---|---|
| `overlay.path` | empty | your add-ons folder (full path) |
| `overlay.code` | on | also run the Python in `modules/`; off keeps only skills, prompts and settings |

**What leaves your computer:** nothing by this feature itself. Your own code may do anything you wrote it to do.

**Turn it off:** Features → Your add-ons → Turn off. The add-ons are unloaded; the folder stays as it is.
`kurooto uninstall` never touches it either.

---

## Add-ons by link

**What it does.** Adds an add-on someone published as a git repository: `kurooto addons add <git address>`, or
Dashboard → Features → **Add-ons by link** → paste the address → **Look at it**. You see its **card** first, and
nothing is added until you say yes.

```
kurooto addons add https://example.org/someone/kurooto-habits.git --ref v1.0.0
```

**The card** says, from the add-on's manifest (`kurooto-addon.json`) and its files:

| Line | Means |
|---|---|
| From … at `<commit>` | the git address and the one commit it's pinned to: a tag, a commit or a branch's newest commit, kept as that commit's id. It never moves by itself; `kurooto addons update` moves it, after you've seen what changes. |
| Adds | its features, commands, jobs (`feature:name`, with when), AI tools, skills and prompts |
| May reach | the hosts on the internet its code may connect to, or "nothing on the internet" |
| May start | the programs it may start; "goes online by itself" means that program reaches the internet itself and Kurooto can't see what it sends |
| Sees each of your messages first | only when it asks to (`"classify": true`) |
| Runs code | **YES** when it has Python files: they run inside Kurooto with its access to this computer. Only add it if you trust whoever wrote it. On the dashboard you tick "I trust this code" before **Add**. |

**Held to its card.** Kurooto loads it only while its files are exactly the ones you agreed to (a changed file and it
doesn't load; `kurooto doctor` and `/addons` say why). A feature, command, AI tool or job that isn't on the card is
left out. Its code may connect only to the hosts on the card and start only the programs on the card: anything else
is refused (`/egress` lists what was blocked, as "add-on <name>"), whatever `privacy.egress` says. That's a fence,
not a sandbox: code you agreed to runs with Kurooto's access, and code written to get around a fence can. The card
and your yes are what keeps you safe.

**After adding.** Its features are listed under Features → **Add-ons by link**, each off until you turn it on. Its
skills and prompts work like your own add-ons' (the AI never writes into its folder).

**Update:** `kurooto addons update <name>` (or **Check for update** on the dashboard) fetches the newest commit of
what you pinned (`--ref` moves to another tag), shows what changes (files added, removed and changed with their
lines, and anything new on its card: hosts, programs, commands, code), then its card again, and asks again.

**Remove:** `kurooto addons remove <name>` (or **Remove**). It's moved aside, not deleted: `kurooto addons undo
<name>` (or **Undo**) puts it back, with its features as they were. Undo after an update puts the version before it
back. The last 3 of each are kept.

**Commands:** `kurooto addons` lists them; `kurooto addons show <name>` shows a card again. `--yes` adds or updates
without asking (after printing the card), for when you've read it. A running Kurooto loads the change at once.

**Settings:** `addons.on` (default on): off, none of them load; they stay where they are.

**What leaves your computer:** git fetches the add-on from the address you gave (counted as handed to git); after
that, only what its card says, and what the programs it may start send by themselves.

**Ready to add:** the [official add-ons](#official-add-ons) below.

**Writing one** (for developers): [modules.md in the developer wiki](../dev/modules.md#add-ons-by-link-coreaddonspy-corefencepy).

---

## Official add-ons

**What they are.** Add-ons published with Kurooto, each a public repository of its own. Kurooto carries a list of
them (inside Kurooto itself, so each release's signature covers it), each pinned to one commit.

| Add-on | Name | What it does | Needs | Repository |
|---|---|---|---|---|
| Machine backups (restic) | `restic-backups` | backs up the folders you name with restic on a schedule, thins out old snapshots, checks the repository | restic, and a restic repository | [kurooto-restic-backups](https://github.com/avtarfr/kurooto-restic-backups) |
| Desktop helpers | `desktop-helpers` | at the alarm, rings your phone through KDE Connect and wakes the screen; pings the phone for the kinds of messages you pick; `/findphone` | KDE Connect paired with your phone, or a Hyprland, Sway or X11 session | [kurooto-desktop-helpers](https://github.com/avtarfr/kurooto-desktop-helpers) |
| Your command words | `habits` | your own short words for commands and requests: `/j had a good day` for `/journal had a good day` | nothing | [kurooto-command-words](https://github.com/avtarfr/kurooto-command-words) |
| Handwriting from the cloud | `handwriting-pull` | copies new handwritten pages from a cloud folder with rclone every 2 hours, skipping metered connections | rclone set up with your cloud, and Handwritten notes on | [kurooto-handwriting-pull](https://github.com/avtarfr/kurooto-handwriting-pull) |

**What "Official" means.** In Kurooto's list and at the commit it pins (each one's `v1.0.0` for now). One you add
from the list, or by hand from the same address at that commit, gets the **Official** badge. The same add-on at another
commit, or from a copy of its repository somewhere else (a fork), doesn't. Official doesn't mean a sandbox: these run
Python inside Kurooto like any add-on by link, held to their cards.

**Add one:**

- Dashboard → Features → **Official add-ons** → **Add**: its card shows, tick "I trust this code", then **Add**.
- Telegram: `/addons official` (or `/addons`) lists them with an **Add** button under each. Tapping it sends the card
  as a message, with **Add, I trust its code** and **Don't**. Only the second tap adds it.
- A terminal: `kurooto addons official` lists them; `kurooto addons add habits` (its name, or its repository's:
  `command-words`) shows the card and asks. `--ref` isn't taken with a name: to pick another commit, give the address
  (it isn't marked official then).

After adding, it's an ordinary add-on by link: its feature is off until you turn it on (Features), and **Remove** and
**Undo** work as above.

**Updates come with Kurooto.** When a newer Kurooto pins a newer commit of one you have, a message says so once, with
a **Look** button, and **Update to vX** shows on the dashboard and under `/addons` (`kurooto addons` says so too).
Looking shows what changes and its card again; only **Update** (or yes in a terminal) updates it. Nothing updates by
itself. `addons.official_updates` off: no message (the buttons stay).

**What leaves your computer:** git fetches the add-on from github.com when you add or update one (counted in
`/egress` as handed to git). None of the four reaches a host on the internet itself; restic and rclone, which they may
start, reach your own backup repository and cloud.

---

## Night performance

**What it does.** Reading books into your notes at night keeps a laptop busy for hours, and it heats up. This add-on
switches the computer to its highest performance power mode while Kurooto's heavy night work runs (which on most
laptops also runs the fans harder), and back to exactly the mode it found when the work is done. It's an add-on by
link, made with Kurooto (not in the official list yet):

```
kurooto addons add https://github.com/avtarfr/kurooto-night-performance --ref v1.0.0
```

Then turn on **Night performance** (Features) and send `/perf`: it says what it found, the mode now and tonight's
reading window, with a **Test** button that switches and puts back at once.

**When it switches:** inside tonight's reading window (from the night's start until you usually wake), while the
night's AI work runs, on the charger, and only when you're away from the computer (no input for 10 minutes, or the
screen locked). Back 10 minutes after the work ends, at the end of the window, when you come back to the computer,
or when the laptop goes on battery. Kurooto stopping puts it back; after a crash, the next start does.

**How, by itself (no password, no root):**

| System | What it uses |
|---|---|
| Linux | a Lenovo Legion or LOQ with the add-on's helper installed (custom profile, fans at full speed); power-profiles-daemon (`powerprofilesctl`); tuned (`tuned-adm`); asusctl (ASUS laptops) |
| Windows | the Ultimate Performance or High performance power plan, else the Best performance power mode (`powercfg`) |
| macOS | nothing: Low Power Mode changes only as root, so enter your own commands |

**Your own commands**, where it can't find a way (Features → Night performance → Set up, or the settings
`night_performance.on_command` / `off_command`): one program each, run without a shell, and only a program its card
names; `sudo` always runs with `-n`, so nothing ever waits for a password (a command that needs root needs a sudo rule
for exactly that line). Commands set anywhere but Set up run only after you tap **Allow** under `/perf`. The off
command has to put back what was there; Kurooto runs it and nothing else.

**Lenovo Legion and LOQ on Linux** (the `legion_laptop` driver): the custom profile and the full-speed fans need root,
so the add-on brings a small helper and installs it with one command, which `/perf` shows with the right folder:
`sudo bash <the add-on's folder>/legion/install.sh`. It adds a sudo rule for only that helper's on, off and status
lines; after that the add-on uses it by itself. The add-on's README has the details and the Undo line.

**If it can't switch** at night, the morning message (Dreaming) has one line about it, and `/perf` the reason.

**Settings that matter:** `night_performance.on` (off: never switches), `away_min` (10), `settle_min` (10),
`legion_profile` (`custom` or `performance`), `legion_max_fan` (on).

**What leaves your computer:** nothing.

---

## Scripts and programs talking to Kurooto

Scripts and other programs on your computer can reach you through Kurooto: on Telegram, the phone app or the desktop,
however you set it up.

### kurooto notify: send yourself a message

```
kurooto notify --title "Backup" "The backup finished."
```

| Option | Does |
|---|---|
| `--title T` | a title above the text |
| `--kind K` | what it is: `info` (default), `result`, `reminder`, `deadline`, `question`, `approval`. This decides where it shows (Settings → `notify.app_kinds` says which kinds also go to the phone app) |
| `--urgent` | gets through [focus](talking-to-kurooto.md) (so does `--kind approval`) |
| `--button "Label=WHAT"` | a button, one row each, up to 8. WHAT is a web address, or `prefix:ref:action` for a feature (or an add-on of yours) that handles that prefix |
| `--click URL` | an **Open** button for a link |
| `--print-id` | prints the Telegram message's id |
| `--reply-to ID` | sends this message as a reply to an earlier one (an id from `--print-id`) |

Exit code 0 when sent. If Kurooto isn't running, the message only shows on this computer and the command exits with 2.

### kurooto send: send yourself a file

```
kurooto send report.pdf --caption "This week's numbers"
kurooto send lecture.mp4 --to drive
```

- Sends a file from this computer to your Telegram. Telegram takes files up to **50 MB**.
- `--to drive` puts it in the **Kurooto** folder of your Google Drive instead and sends you the link (needs
  [Drive upload](google.md)). Those files stay until you delete them.
- A file over 50 MB goes to Drive by itself when Drive upload is on (`drive_upload.big_files`, default on), as a
  **temporary** link: it's deleted from your Drive after `drive_upload.temp_days` (default 7) unless you move it out of
  the Kurooto folder. With Drive upload off, a file over 50 MB is refused with a message saying so.
- Empty files are refused. While you're in focus time, the file comes when focus ends.
- Exit code 2 when Kurooto isn't running (nothing was sent).

With Skills on, the AI can also send you files from your notes folder ("send me my linear algebra pack"), on calls as
well; more than two files come as one zip. It can't send files from anywhere else.

### kurooto note: a quick note

```
kurooto note "an idea for the project"
some-command | kurooto note --title "output"
```

Saves the text (or what's piped in) as a new note in your notes' inbox, as written. It works even when Kurooto isn't
running, and prints where it saved the note. Same as `/note` on Telegram.

### kurooto ask: plain English in a terminal

```
kurooto ask "what's due this week?"
kurooto ask
```

- With text: handled exactly like a Telegram message. Quick things (reminders, holds, what's due, `/commands`) answer
  at once; anything bigger goes to your AI and its answer prints here, not on Telegram.
- Alone: opens a prompt where you type one request after another (history with ↑ / ↓ where your system supports it).
  Answers to bigger requests print above the prompt when they're ready. `clear` clears the screen; Ctrl+D leaves.
- In that prompt, `!command` runs a shell command right there, after showing it. A line that looks like a shell
  command typed without the `!` (`systemctl …`, `kurooto status`) is never sent to Kurooto or the AI: you're told
  to run it in a shell or prefix it with `!`. A one-off `kurooto ask "!…"` is refused the same way.
- `--no-wait` prints the request's id instead of waiting; `kurooto ask --job <id>` waits for its answer later.
- `--timeout N` minutes to wait (default 60). No answer in time: it says the request is still going (exit 2).

### kurooto ask-me: ask yourself a question

```
kurooto ask-me "Which folder should the photos go in?" --choices "camera|screenshots"
```

The question reaches you like any of Kurooto's [questions](talking-to-kurooto.md): buttons on Telegram, the phone
app, or your next call. The first answer anywhere counts.

| Option | Does |
|---|---|
| (none) | prints the question's id and returns |
| `--choices "a\|b\|c"` | answers offered as buttons |
| `--wait` | waits and prints your answer; no answer in time prints `timeout` (exit 2) and closes the question |
| `--timeout N` | minutes to wait (default 30) |
| `--expires 6h` | how long it stays open: `30m`, `6h`, `2d` (default 2 days) |
| `--title T` | a label instead of "Question" |
| `--pending` | lists the questions still open (`--json` for programs) |
| `--id ID --wait` | waits for the answer to a question asked earlier (a timeout leaves it open) |
| `--then "CMD"` | runs a command with your answer once it comes (below) |

**`--then`, a follow-up command:**

```
kurooto ask-me "Log today's study?" --choices "yes|no" --then "my-logger --answer {answer} --question {id}"
```

`{answer}` and `{id}` are filled in. Without `--wait`, a copy waits in the background (until the question expires;
it outlives the terminal) and the id prints now. With `--wait`, it waits here, prints the answer, runs the command and
exits with its exit code. The command runs as a program with its arguments, never through a shell, so an answer like
`a; rm -rf ~` is just text in one argument; quotes keep spaces together, or give a JSON list
(`--then '["my-logger", "{answer}"]'`). Only this terminal command can attach a follow-up: nothing from Telegram, a call
or the AI can. A follow-up that fails messages you; its output is in `ask-then.log` in the logs folder.

If Kurooto isn't running, `ask-me` exits with 2 and nobody is asked.

### kurooto ask-approval: a yes or no before a script acts

```
kurooto ask-approval "Delete last month's build folders?" --timeout 30
```

Waits for **Approve** / **Deny** (a reply of "yes", "ok", "no" or "cancel" counts too). It prints `yes`, `no` or
`timeout` and exits with **0**, **1** or **2**. `--timeout` is in minutes (default 30). If Kurooto isn't running it
exits with 2. Use it in scripts before anything that needs your OK; nothing is ever approved for you.

### kurooto call: ring your phone

```
kurooto call "the backup finished"
kurooto call --at 17:30 "leave for the station"
```

Needs [Phone calls](calls.md).

| Option | Does |
|---|---|
| (none) | calls now, but waits out your no-call rules (classes, `/hold`, focus, the night) and calls when they end |
| `--at WHEN` | calls later: `17:30`, `"in 20 min"`, `"tomorrow 7:00"` |
| `--force` | rings now despite the no-call rules |
| `--alarm` | rings as a wake-up alarm (no-call rules don't apply) |
| `--list` | the calls booked for later, with their keys |
| `--cancel KEY` | takes a booked call off (your call line forgets it too) |

Nothing ever rings while you're already on a call. Check-ins and the alarm have their own commands (`/checkins`,
`/alarm`). Exit code 1 when Kurooto isn't running.

### kurooto watch: a message when a long job ends

```
kurooto watch -- python train.py --epochs 50
```

Runs the command (its output still shows in your terminal) and messages you when it ends: done, failed or stopped, the
exit code, how long it took and its last 10 lines. `--lines 0` sends no lines; `--log my-project` also logs it as an
experiment run of that research project (see [research.md](research.md)). If Kurooto isn't running, the message shows
on this computer only. Every watched job is listed in `watch.log` in the state folder.

---

## Kurooto's tools in other AI programs (kurooto mcp)

`kurooto mcp` is a small MCP server (MCP: the standard way AI programs plug in tools). Add it to any MCP client and
that program can use Kurooto's tools: reminders, calls, deadlines, notes and more, depending on the features you have
on. Each tool call goes to the running Kurooto, so it does exactly what it does on a call or in Chat.

- agy and Claude Code as your [AI brain](ai-brains.md) get these tools automatically (agy after you approve it once;
  Claude Code for each request only, nothing saved in its settings).
- For your own agent sessions, add the command `kurooto mcp` as an MCP server in that program's settings.
- While Kurooto isn't running, the tools still list, but calling one says Kurooto isn't running.
- The tools are told: your notes are yours (add to them, never reword or remove your text), and only say something
  was done when the tool says so.

---

## Your skills in other AI programs

`kurooto export-skills on` puts your skills into agy (and, with `--to`, other agent programs), so `/journal my day`
typed there runs the same instructions. See [skills-and-routines.md](skills-and-routines.md).

---

## The reserve: Kurooto's state as files for AI programs

An AI program that only has to read a file can't fail on a permission it doesn't have, so Kurooto keeps plain Markdown
copies of its own state in the **reserve** folder (`reserve/` in Kurooto's state folder; `kurooto paths` shows where):

| File | Holds |
|---|---|
| `alarm.md` | the next alarm and the daily one |
| `deadlines.md` | what's due, nearest first |
| `calendar.md` | the next two weeks of events |
| `settings.md` | every setting that differs from its default, and which features are on (never a secret) |
| `addons.md` | your add-ons and whether each loaded |
| `agent-guide.md` | what an AI program may read, write and run here, its tools by name, the chat commands |

They're rewritten every 10 minutes and when something changes (only when their text changed). `kurooto reserve`
writes them now. AI programs may read this folder, never write to it, and Kurooto never reads it back.

*Leaves your computer:* nothing by itself; an AI program that reads these files sends what it reads to its own service.

---

## When something looks wrong

| What you see | What to do |
|---|---|
| `kurooto ask`, `call`, `send`, `ask-me` or `ask-approval` say Kurooto isn't running | `kurooto on`, then try again. `--timeout` is in minutes. |
| `kurooto notify` exits with 2 | Kurooto wasn't running: the message only showed on this computer. |
| `kurooto send`: "Telegram takes files up to 50 MB" | Turn on Drive upload (Features) to get big files as a Drive link, or send something smaller. |
| A file sent during focus didn't arrive | It comes when focus ends (`/focus off` ends it now). |
| `kurooto ask` says "that's a shell command" | Run it in a shell, or in the `kurooto ask` prompt start it with `!`. |
| `kurooto ask-me --then` didn't run my command | The question may have expired unanswered. A failed follow-up messages you; see `ask-then.log` in the logs folder. |
| `kurooto watch` says "only shown on this computer" | Kurooto wasn't running: `kurooto start`. |
| An agent program says Kurooto's tools aren't running | Kurooto is off or restarting: `kurooto on`, then ask again. |
| Your add-ons: a problem in `kurooto doctor` | `/addons` shows which file and the error. Fix it, then restart Kurooto (`kurooto stop`, `kurooto start`). |
| An add-on change doesn't show | Restart Kurooto after editing add-on code. |
| "the add-ons folder can't be inside Kurooto's own folders" | Move it elsewhere (for example `~/code/my-addons`) and give the new path. |
| An add-on by link "didn't load: its files changed since you agreed to its card" | Something edited its folder. `kurooto addons update <name>` brings it back to a commit you agree to (or remove it and add it again). |
| An add-on by link "needs Kurooto X or newer" | Update Kurooto (`kurooto update --now`); it loads at the next start. |
| "The add-on X may only reach the hosts on its card" | Its code asked for a host it didn't declare: it's refused on purpose. Tell its author; a newer version that declares it shows the host when you update. |
| "may only start the programs on its card" | The same for a program. |
| `kurooto addons add`: "couldn't clone it" | Check the address; a private repository needs your git sign-in set up (Kurooto never asks for a password). |
| An add-on isn't marked **Official** | It came from another address (a fork) or is at another commit than the one Kurooto lists. Remove it, then Add it from Official add-ons (or `kurooto addons add <name>`). |
