# The dashboard

The dashboard is a page on your own computer at **http://127.0.0.1:8770**. It shows what Kurooto is doing, lets you
turn features on and off, change settings, pair a phone, and do everyday things (reminders, deadlines, the alarm, your
journal) without Telegram. `kurooto open` opens it in your browser.

This page covers the dashboard, the morning page, the colours, `kurooto top` (the same board in a terminal) and the
two terminal features. For talking to Kurooto in general see [talking-to-kurooto.md](talking-to-kurooto.md).

- [Opening it](#opening-it)
- [Two designs: new and classic](#two-designs-new-and-classic)
- [Two layouts: dense and roomy](#two-layouts-dense-and-roomy)
- [The board (dense layout)](#the-board-dense-layout)
- [Study mode](#study-mode)
- [Ctrl+K: do anything from anywhere](#ctrlk-do-anything-from-anywhere)
- [The pages](#the-pages)
- [Search, hiding features, bigger panes](#search-hiding-features-bigger-panes)
- [Links to other sites](#links-to-other-sites)
- [The morning page](#the-morning-page)
- [Colours](#colours)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [kurooto top: the board in a terminal](#kurooto-top-the-board-in-a-terminal)
- [Terminals (in the dashboard)](#terminals-in-the-dashboard)
- [Kurooto Terminal (a window of its own)](#kurooto-terminal-a-window-of-its-own)
- [When something looks wrong](#when-something-looks-wrong)

---

## Opening it

- Go to `http://127.0.0.1:8770` in any browser, or run `kurooto open` (it prints the address too). `127.0.0.1` means
  "this computer".
- If another program already uses port 8770, Kurooto takes the next free one (it tries 30 in a row). `kurooto paths`
  shows the state folder; `web.json` there says which port is in use. You can pick the starting port with the
  `web.port` setting (default `8770`; Settings → Dashboard, then restart Kurooto).
- The **setup** link in the top bar goes back to the setup page (`/setup`), for example to add more AI accounts to
  [About you](teaching-kurooto.md) or to restore a profile. While setup steps you skipped are waiting, it says
  **finish setup (N)** and opens the first of them.
- If Kurooto isn't running, the page can't load. Start it from your app menu (**Kurooto**) or with `kurooto on`.
- Leaving it open costs little: while the dashboard is in a background tab or a minimised window, Kurooto stops
  reading the computer and your notes for it, and catches up the moment you look again.

**Who can open it.** Only this computer: the page listens on 127.0.0.1 only. Every request needs a key that only the
page Kurooto serves gets, requests from other websites are refused, and the page loads nothing from the internet. On
Linux, where several people can be signed in at once, it also checks that the page and every request come from your
own user account, and refuses them when it can't tell.

## Two designs: new and classic

| Design | Looks |
|---|---|
| **new** (default since 0.5.19) | set in a sans-serif typeface (Public Sans, which comes with Kurooto: nothing is fetched from the internet), with figures that keep their width as they change; monospace only for the terminals, code and file paths. Rounded panes with their name and figures on a header line, a top bar with the name, a status line, **study**, **panes ▾** and the design button; thin-line graphs and bars in the palette's colours |
| **classic** | the look of 0.5.18 and earlier: everything in monospace, thin borders with each pane's name set into its top line, dotted graphs |

Both have the same panes, pages, keys, search and data, and both follow the palette ([Colours](#colours)).

**Switch:** the **classic look** button in the top bar (in classic: **panes ▾** → **new look**, or the top bar in the
roomy layout), or Dashboard → Settings → Look → `look.design`. It changes at once, without a reload, and every browser
gets it (it's a setting). *Undo:* switch back the same way.

## Two layouts: dense and roomy

| Layout | What it is | When you get it |
|---|---|---|
| **dense** (default) | one full-screen board; the pages open over the whole board | windows at least 1280 px wide and 600 px tall |
| **roomy** | the earlier layout: bigger panes and type, with the pages as tabs below | narrower windows get it by themselves; `look.layout` = `roomy` keeps it everywhere |

Both have the same pages, the same Alt keys, the same search and the same way of hiding features.

**Setting:** `look.layout` (`dense` or `roomy`), Dashboard → Settings → Look. The change shows at once.

## The board (dense layout)

Four panes: **STATUS** down the left, **SYSTEMS** and **NOTES** on top, **TERMINAL** below. A top bar shows Kurooto's
name and version, a short status line ("12 features on · 0 AI requests running · cpu 7%"), a **needs a look** badge
when something isn't working, an **update** badge when a new version is ready, and the **setup** link (the new design;
classic shows it only in the roomy layout and keeps **study** and **panes ▾** in the board's top-right corner).

### The being (the board since 0.8.9)

The board shows Kurooto as one body, drawn from what it's really doing; the panes below are still a click away (the
**panes ▾** menu: **board** being, three or classic, or any one pane filling the board, with Esc back to the being).

- **The mind** (the brain): each kind of work sparks in its own region: AI requests in the prefrontal cortex, plans
  beside it, what may reach you in the orbitofrontal cortex, speaking in Broca's area, memory in the hippocampus, and so on
  (the colours' key is top left). Click the brain to open it; click a region for its Brain parts (each with its switch)
  and the features that live there.
- **The heart** beats faster the busier Kurooto has been in the last ten minutes. Its parts: the pacemaker (what runs
  next), the ventricles (AI requests running), the atria (answers), the aorta (the call line), the coronaries (upkeep:
  backups, updates, sync). Blood carries work out to the organ doing it and back when it reports.
- **The senses**: the eye (your screen and activity), the coil (this computer: click it for every core, memory, swap,
  graphics, disks, battery and temperatures, live), the cilia (your phone in your hand), the cochlea (hearing: the call
  line and Voice), the canals (your phone's motion).
- **Memory** is your notes, in the NOTES map's neighbourhoods and colours, laid out by their links (the ones through a
  "Seen in" or a reading list too, a little fainter). Point at a note for its title; click it for a preview and **open it**.
- **Points of light** are the features, on the organ that does their work; they flare when the feature does something.
  Click one for its switch and all its settings, editable right there.

**Turning it:** drag an organ to turn it (a sense on its own); dragging empty space doesn't move anything. Wheel zooms,
right-drag pans. **Every part focuses:** click a region, a heart part, a sense, a neighbourhood, a note or a feature and the
view flies to it; it stays solid, glowing in its colour with a fine ring round it, and the rest of its organ turns to faint
glass so nothing hides it; Esc (or a click on empty space) goes back one level. **The brain's views** (top of the board
while the brain is open): **Solid** (the default), **Cutaway** (the top lifts off to show the inside) and **X-ray** (the
cortex as glass, the thalamus, hippocampus, caudate and corpus callosum inside). **H** (or **hints** top right)
hides the hints: the lines under each name, the help line and the colours' key (`look.being_hints`). **Mute** stops Voice
hearing and speaking. `look.being_theme`: `void` (white light on black) or `theme` (the page's palette).

**The talk box** (bottom right, on every board; **Alt+K**): type to Kurooto as on Telegram; the answer prints in it.
Turn it off with `look.talk_box`.

### STATUS: this computer

A monitor like the program btop, the same as [`kurooto top`](#kurooto-top-the-board-in-a-terminal):

- **Header:** the date and time, how long the computer has been up, today's event count, the battery (percent, time
  left, watts) or "ac", Kurooto's mode ("saving battery" or "paused …"), the update and health badges, and three
  buttons: **pause 1h** (or **resume** while paused), **off** and **setup**.
- **CPU:** a history graph, every core with its own little graph, speed, load, temperatures and fans (where the
  computer reports them).
- **MEM:** used, cached, available, swap. **GPU:** use, its memory, temperature, power and a graph (needs NVIDIA's
  `nvidia-smi`, or an AMD card on Linux; a sleeping laptop graphics card isn't woken to ask).
- **NET:** download above the line, upload below, and totals. **DISKS:** how full, reads and writes per second.
- **PROCESSES:** the busiest programs. Click **cpu** or **mem** in the header to sort (this browser remembers it).
  Kurooto's own processes are marked ✦ (a dot in the new design).
- **STUDY TODAY:** minutes per subject, with the [Study tracker](books-and-study.md) on.
- **PROJECTS:** your git folders with each one's last commit, what isn't pushed yet and what's changed. List the
  folders in `look.projects` (default empty: the repositories you gave [Research](research.md)).

**pause 1h** pauses Kurooto for an hour (Telegram still answers and keeps what you send; see
[your-computer.md](your-computer.md)). **off** asks first, then turns Kurooto off completely: it stops, won't start at
sign-in, and your call line stops placing scheduled calls until you open Kurooto from your app menu or run
`kurooto on`. The page then only says that Kurooto is off.

### SYSTEMS: the features as living cells

Each feature that's on is a round cell around a beating core labelled with your assistant's name. Pulses run along
the lines between the core and the cells as messages, reminders and AI answers come and go. The hours of the day run
around the ring.

- **A cell's words** sit just outside it: its name and its figures. A feature that runs programs of its own shows
  their cpu and memory ("running · 2.1% · 140M"); one whose programs aren't running turns grey and dashed ("not
  running"); one whose programs only run now and then says "idle". Other features say what they did last ("last 4m
  ago") and when they run next ("next in 2h").
- **Hover over a cell** for its card: events in the last 2 minutes, its processes (cpu, memory, threads, uptime), the
  last event and the next scheduled time. Its nerve lights up and it swells a little. On a very crowded ring a few
  labels may hide; the card always works.
- **In the new design (0.5.21)** SYSTEMS is the largest pane on the board and looks alive: the core is a soft membrane
  with rims that each heartbeat runs out through, every feature is a small neuron whose branches grow with how busy it
  was over the last two minutes (oldest to newest, clockwise), and the nerves are tapered fibres, thick at the core
  and fine at the cell, that flash where a pulse arrives. Classic keeps its round cells and plain lines.

**Using it (both designs, new in 0.5.21):**

| To | Do |
|---|---|
| See what a feature is doing | point at its cell |
| Open its menu | click its cell, or Tab to it and press **Enter** (arrow keys move round the ring; **Esc** closes) |
| Send a pulse to it and back | **ping** in its menu (nothing happens to the feature: it only shows the motion) |
| Sync just that feature | **sync now** in its menu (notes sync, Classroom, calendar, research, the notes brain, backups) |
| Stop it messaging you, but keep it working | **quiet** in its menu; **undo** brings its messages back (it's the same as Calm's "Less of this") |
| Change its settings | **settings** in its menu: the Features page opens with its card |
| See everything it did | **activity** in its menu: the Activity page shows only that feature (**show everything** goes back) |
| Do something (Ctrl+K) | click the core |
| Turn the ring, zoom in | drag anywhere on the pane; scroll on it (dense layout). Both spring back when you let go |

With "reduce motion" set on your computer the cells and the core hold still (pulses still show what happens), and the
turn and zoom don't spring. A screen reader finds the features as a list of buttons, one per cell, each saying what
the cell shows.
- The pane's top line says how many features are on, how many aren't running, Kurooto's own cpu and memory, and
  whether the call line is linked.

**The four corner panels:**

| Corner | Shows |
|---|---|
| top left: **events** | the last five things that happened (newest first; fresh ones are bright) |
| top right: **your AI** | requests running or waiting (title, effort, how long, status), the last few finished ones, the local models loaded and their memory, and how many things are scheduled with the next one |
| bottom left: **today** | classes, calendar events, check-ins and calls still to come today ("now" when one is on), focus time and no-call holds |
| bottom right: **due** | what's due and how soon; overdue ones in red, ones under 24 hours in a warmer colour; "deadlines are off" when the feature is off |

**Folded panels and legends (new in 0.5.8).** To keep the board calm, the four corner panels, the NOTES legend and
the NOTES recent list are folded to their first line, with a count of what's hidden (`▸ 4`). Point at one and it
opens while the pointer is over it. Press **L** to open all of them (or fold them all again). This browser remembers
your choice; another browser starts folded.

### NOTES: a map of your notes

Every note in your notes folder is a dot; links between notes are lines. Notes are grouped into coloured
neighbourhoods by folder: each `sources/<subject>/` folder is one (in the kurooto notes layout, each subject folder
with a `course.md`), each research project (`projects/<name>/` or `research/<name>/`) is one, the other maps and hubs
are the hub ("Maps & hubs"), and any other note joins the neighbourhood most of its links go to (or "Other Notes").
Grouping works best with the zettelkasten notes layout (see [notes-and-concept-graph.md](notes-and-concept-graph.md)).

**Names on the map (new in 0.5.19).** At the usual zoom the map names its regions, the way a map names places: each
course by its course page's title ("MTH201 Linear Algebra") and each research project by its index note's title, in
the region's colour at the middle of its notes. A note's own name shows when you point at it, find it, light the
recent ones (**R**) or zoom in; zoomed in, course pages, hubs and projects are named first, then notes that link
across courses, then the best-linked. A book's index note (`<subject>/books/<book>`) is drawn small and named last:
once the [concept graph](notes-and-concept-graph.md) reads a book, hundreds of notes link to it from their "Seen in"
lines, and before 0.5.19 it took every label and the map read as a list of book titles. The region names step back
while you point at or search for a note.

**Pointing at a note (0.6.1).** The note and the notes it links to (or that link to it) light up in full colour with
their names raised above everything else, placed so they never overlap (up to 24 neighbours' names, the course
pages, hubs and links you made first); everything else dims and the region names step aside. It eases in over
about a tenth of a second (at once with reduced motion). The keyboard does the same: **Tab** to the map, then the
**arrow keys** move to the linked note in that direction (or the nearest note that way), **Enter** opens it, **Esc**
lets go.

**"Seen in" links don't make hubs (0.6.1).** The links Kurooto writes to say where a concept was read (a concept
note's "Seen in", a book's or class note's "Concepts in ..." list, a course page's "From the books") are still drawn,
but they don't make a dot bigger or get its name shown first: a lecture note or a class post that many concepts were
read from stays a normal-sized dot. Its card says how many such links it has: "3 links (+152 from reading)".

**Research on the map (new in 0.5.21).** A research project's region is its folder's notes, the notes its index links
to, and the topics its line in the research hub (`maps/research.md`, or your layout's research hub) links to, together
with the lines indented under it. It's always named, however few notes its folder has: by its index note's title, or
the hub's line for it ("L96 parameterization" in `- [[projects/l96/index|L96 parameterization]]: ...`). Research
regions and their names are in the accent colour, their names a little bolder. Concept notes (`zettel/`) and any
other note outside a course or project folder join the region most of their links come from, a course or a project
(a tie goes to the course), so the cloud of concept notes splits into named topics; a note with no such links stays
unnamed ("Other Notes").

| To | Do |
|---|---|
| See a note's details | point at it: title, path, links, words, when it was edited |
| Walk the map with the keyboard | Tab to it, then the arrow keys; Enter opens the note, Esc lets go |
| Pin a note's card with its first lines | click it (click empty space to let go) |
| Open a note | double-click it (your default app for Markdown, or your own program: `notes.open_with`) |
| Zoom / move around | mouse wheel / drag empty space |
| Move a note | drag it |
| Find a note by name | `/` or **Alt+/** (or Ctrl+K → `find`), type, **Enter** jumps to the first match, **Esc** closes |
| Highlight notes edited in the last day | **R** (again, or a click on the "Recent" line it shows, turns it off). Notes edited in the last hour get a brighter ring |

The pane's top line counts notes, links and neighbourhoods. The legend (top right) lists the neighbourhoods with
their counts; the bottom-left list shows the notes you edited last. Both are folded until you point at them or press
**L**.

**Opening notes in your own program:** Dashboard → Settings → Notes → `notes.open_with`, for example
`kitty nvim {path}`, `code {path}` or `kurooto term -e nvim {path}`. `{path}` is the note (one argument even with
spaces), `{folder}` your notes folder; without `{path}` the note goes at the end. It runs as a program with
arguments, never through a shell, and the program must open its own window. If the program isn't there, the default
app opens the note. Empty (the default) uses your default app.

### TERMINAL: plain English right in the page

The bottom pane's border holds its tabs. With the [Terminals](#terminals-in-the-dashboard) feature on, there are real
terminals for your AI's own program (agy or Claude Code, one tab for each that's installed), a shell and Kurooto's
log. Without it, there's a **+ terminals** tab that explains the feature.

The tab named after your assistant (**kurooto**) is always there: type to Kurooto as on Telegram. Quick requests
("push the evening check-in by 30 min", "what's due this week?", "no calls till 6") answer at once; anything bigger goes
to your AI, and its answer prints here, not on Telegram. Its own words:

| Type | Does |
|---|---|
| `help` | a short list of what works here |
| `check` | whether every feature that's on is working (✓ or ✗ with why) |
| `jobs` | your AI's latest requests |
| `clear` or **Ctrl+L** | a clean screen |
| **↑** / **↓** | what you typed before |

An answer that takes longer than 30 minutes stops being waited for here; see it in the **AI jobs** page.

The pane's header (classic: its border) also lists the pages (today, activity, jobs, schedule, features, phone, research, you, settings),
each with its key letter underlined, and a reminder of the keys.

## Study mode

A calm board for studying: only your notes and the things that help you study. Everything else (STATUS, SYSTEMS,
the terminal, the panes menu) waits, untouched, and comes back exactly as it was when you leave.

**Switch it on or off:** **study** in the top bar (classic design: the board's top-right corner; it reads **leave
study** while it's on), **Alt+M**, Ctrl+K → `study on` / `study off`, or from Telegram or the kurooto tab
`/study mode on` / `/study mode off` (plain words work too: "study mode", "leave study mode"). The page follows at
once wherever you switch it. It stays on across reloads and in every browser (the setting `look.study_mode`).

What it shows:

- **NOTES**, large on the left: the map, with the chosen subject's notes lit and fitted to the pane. The note you
  pick from the list is centred with its first lines; double-click opens it.
- **STUDY**, on the right:
  - **Timer:** pick a subject, then **start**. A focus (25 minutes, `study.focus_min`) is focus time: calls and
    messages that can wait are held until it ends, and its minutes are logged to that subject in the
    [Study tracker](books-and-study.md#study-tracker). Then a break (5 minutes, `study.break_min`); after it the next
    focus waits for you. **pause** keeps what's left (the minutes so far are logged), **resume** goes on, **reset**
    ends it. The digits show in the tab's title while it runs. It keeps time with the page closed, and Telegram says
    when a focus or a break ends.
  - **then leave Study mode:** tick it and Study mode ends when the focus ends, instead of a break
    (`study.timer_ends_mode`).
  - **Today:** minutes per subject.
  - **Due:** quizzes and exams (marked *exam*) and tasks in the next two weeks, and what's time to start
    ([Start-by dates](reminders-and-deadlines.md)).
  - **Recall:** with [Quiz](quiz-and-exams.md) on, up to three cards due for the subject from its exam-prep notes;
    click one to see it. `/quiz <subject>` practises them.
  - **Notes:** the subject's course page, exam prep, doubts and class log, then its lecture and concept notes, newest
    first (wherever your notes layout keeps them).

| Setting | Default | Effect |
|---|---|---|
| `look.study_mode` | off | the board is in Study mode |
| `study.focus_min` | `25` | minutes of focus |
| `study.break_min` | `5` | minutes of break |
| `study.timer_ends_mode` | off | Study mode ends with the focus |

The timer needs the Study tracker (and Subjects); without it, Study mode still shows your notes and what's due. A
focus never shortens a `/focus` of yours that lasts longer. `/study stop` (or "done studying") during a focus ends the
timer and logs the time. *Undo:* leave Study mode; reset the timer.

## Ctrl+K: do anything from anywhere

**Ctrl+K** (⌘K on a Mac) opens one line at the top of the board, from wherever you are (except inside a terminal,
where Ctrl+K belongs to the shell). Press it again, **Esc**, or click outside to close it.

| Type | Does | Example |
|---|---|---|
| `ask …` (or anything that isn't a verb) | sends it to Kurooto as if typed on Telegram | `what's due this week?` |
| `journal …` (or `j …`) | adds a line to today's journal | `j finished the lab report` |
| `note …` (or `. …`) | adds a line to today's inbox note | `. look up Sylow theorems` |
| `remind <when> <what>` (or `! …`) | sets a reminder; the time comes first | `remind 18:30 call mum`, `! in 20m tea` |
| `due <what> <when>` | adds a deadline; the time comes last | `due essay draft fri 17:00` |
| `alarm <time>` | sets the wake-up alarm | `alarm 7:30`, `alarm tomorrow 6:45` |
| `alarm skip [day]` | skips a morning (tomorrow if you name none) | `alarm skip friday` |
| `alarm off` | turns off the next alarm | |
| `alarm daily <time>` / `alarm daily off` | sets or turns off the daily alarm | `alarm daily 7:00` |
| `find <name>` | finds a note on the NOTES map | `find eigenvalues` |
| `open <page>` | opens a page: today, activity, jobs, schedule, features, phone, research, about, settings (the start of a name is enough) | `open set` |
| `study on` / `study off` | [Study mode](#study-mode) | `study on` |

How it behaves:

- As you type, a list shows what Enter would do. **↑ / ↓** pick a line, **Enter** does it, **Tab** puts the
  highlighted verb in front of what you typed.
- A bare word is completed first: `re` then Enter gives `remind `, with a hint of what to type. With something after
  the verb, Enter runs it and the line clears for the next one.
- What happened shows under the line ("Reminder set for 18:30", or why not). For an `ask` that goes to your AI, the
  answer arrives there too, with which AI answered, its effort and how long it took. It waits up to about 20 minutes;
  after that, look in the AI jobs page.
- Times for `remind`: `18:30`, `6pm`, `in 20m`, `in 2 hours`, `tomorrow`, `tomorrow 9am`, `friday 9:00`. Times for
  `due`: a weekday with a time (`fri 17:00`), `tomorrow` (with or without a time), a date (`2026-11-02`, or
  `2026-11-02 17:00`) or `in 3 days`.
- Every action is exactly the one the Telegram command and the AI's tool do, so they never disagree. A feature that's
  off says "… is off: turn it on in Features". The alarm needs [Phone calls](calls.md).

## The pages

In the dense layout the pages open over the whole board: **Alt** plus the page's underlined letter, a click on its
name in the TERMINAL pane's border, or Ctrl+K → `open`. **Esc** (or **esc back**, or a click on the page's name) goes
back to the board. In the roomy layout they're tabs under the panes.

| Page | Key | What it's for |
|---|---|---|
| Today | Alt+T | the day, with buttons |
| Activity | Alt+A | what happened, newest first (the last 80 events: names, counts and times, never message text) |
| AI jobs | Alt+J | AI requests: when, what, effort, how long, result, and **Cancel** on running or waiting ones |
| Schedule | Alt+C | everything scheduled: reminders, check-ins, calls, syncs, digests |
| Features | Alt+F | turn features on and off, set them up |
| Phone | Alt+P | your call line, pairing a phone, a test ring |
| Research | Alt+R | paper sources, the digest, project repositories |
| About you | Alt+Y | your persona card and your profile, to read and edit |
| Settings | Alt+S | every setting you can change here |

A link to `/#about` (what `/aboutme` on Telegram sends) opens the About you page directly; any page name works the
same way (`/#settings`).

### Today (Alt+T)

The day, and the everyday things done right there.

- **One box for anything** at the top. Plain words go to Kurooto as if typed on Telegram (an AI answer shows which AI
  gave it and how long it took). `j …` adds a journal line, `. …` a line to today's inbox note, `! 18:30 call mum` a
  reminder (`! in 20m tea`, `! tomorrow 9am gym`; the time comes first). Press Enter or **↵**.
- **Alarm** (needs the Morning alarm): what's set, a box to set one ("7:30", "tomorrow 6:45"), **skip tomorrow**,
  **turn this one off**, and **daily alarm…** / **change daily** (asks for a time, or `off`).
- **Classes:** today's classes, "(skipping)" on ones you skip.
- **Due:** the next three weeks; **done** ticks one off (and the `- [ ]` box in your notes when it came from one),
  **new date** asks for a date ("tomorrow 23:59"). An add box takes "essay draft fri 17:00" (when it's due goes last).
- **Reminders:** each with **+10 min** and **cancel**.
- **Check-ins:** today's, with **+30 min** and **skip** while they're still to come.
- **Waiting for you:** open questions, with a button per answer and **answer…** for your own words.
- **Journal:** today's entries and a box; **save** (or Ctrl+Enter) adds a "Journal HH:MM" section to today's daily
  note. It also says how many lines went into the inbox note today.

A part whose feature is off says so with a link to Features. Every button does exactly what the command or the AI's
tool does.

**Where things go:** journal lines go into today's daily note (`journal/<date>.md`, or `dailies/<date>.md` in the
zettelkasten layout). `.` lines go into one inbox note per day, `inbox/<date>-captured.md`, one timed line each. This
differs from `/note` on Telegram, which makes a new note per thought.

### Activity, AI jobs, Schedule

- **Activity** lists the last 80 events as they happen. Events never hold what you typed, only names, counts and
  times.
- **AI jobs** lists requests with **Cancel** on running and waiting ones (a running agent program is stopped with what
  it started). The same as `/jobs` on Telegram.
- **Schedule** lists what's coming with its time.

### Features (Alt+F)

A card for every feature: what it does, what leaves your computer (in a different colour) and a button. The features
that are on come first; the count beside the search box says how many are on. Telegram, which connects on the setup
page, has **Connect on the setup page** while it isn't connected.

| Button or part | Does |
|---|---|
| **Turn on** | turns it on (a feature that needs another one says which, e.g. "Skills needs Chat first") |
| **Turn off** | turns it off at once; its data stays. A feature others need says "turn off X first" |
| **Set up** | installs or connects what it needs, with a progress log; the result (✓ or ✗) stays on the card. Links in the log (such as Cloudflare's sign-in) are clickable |
| A form on the card | the detail it needs: a calendar link, a repository and token, a folder, Google's client file (paste it or pick the file), then **Save**. **Copy** buttons copy values for Google's setup pages |
| **Open Google sign-in** | appears after Save for Google features; sign in, and the card turns on by itself (it watches for up to 15 minutes) |
| Switches on a card | a feature's own parts, e.g. [Exam season](quiz-and-exams.md)'s parts |
| **hide** / **unhide** | takes an off feature off this page (see [hiding features](#hiding-features)) |
| **Finish setting up** box | at the top: the setup steps you skipped for now, each a link back to its step on the setup page (see [getting-started.md](getting-started.md#the-setup-wizard-step-by-step)); a step leaves the box once it's done |
| **Needs a look** box | at the top: what isn't working, with a **Fix** button where Kurooto can fix it (see [your-computer.md](your-computer.md)) |

The Phone calls card also lists its three steps (a Gemini key, a Cloudflare account, pairing) and has a box for the
Gemini key. The Mail digest card links the **Confidential mail** page (mail summarised on this computer; see
[google.md](google.md)). Features from [your add-ons](add-ons.md) are listed separately at the bottom, under "Your
add-ons".

### Phone (Alt+P)

Needs [Phone calls](calls.md) on. It shows your call line's address and whether this computer is connected to it.

- **Pair a phone:** a QR code to scan with the phone. The page that opens offers the Android app or Add to Home Screen
  (iPhone), then pairing. The code works for 15 minutes; the page also shows the code and a link. `/phone` on
  Telegram does the same.
- **Ring my phone (test):** rings every paired phone (only while connected).
- **Paired phones:** name, kind, whether notifications are on, for an Android phone whether it's **connected**
  straight to your call line (0.7.0; when it isn't, ntfy.sh carries its messages), when it was paired, and **Remove**.
- **On the phone:** **Show Systems and the Notes map in the Android app** (0.7.0, off at first): this board's SYSTEMS
  and NOTES map in the app, sealed for each phone (see [phone-app.md](phone-app.md#systems-and-the-notes-map-on-the-phone)).
  Turning it off drops your call line's copies.
- **ntfy.sh (the fallback):** how many rings or messages ntfy refused this week. ntfy limits each internet address and
  counts a free account the same way, so only a paid ntfy plan's token helps; paste one here if you have it (**Remove**
  goes back to none; your call line is updated with it by itself). With the app connected you don't need it.

Details are in [phone-app.md](phone-app.md).

### Research (Alt+R)

What you work on, your paper sources (quick picks, arXiv fields, bioRxiv, medRxiv, PubMed, any journal's feed, with
keywords and a **Preview**), the digest's schedule and size, **Send a digest now**, and the code repositories whose
commits go into your project notes. All of it is explained in [research.md](research.md).

### About you (Alt+Y)

First your **persona card**: what to call you, tone, length and things to avoid, with **Save card** and a preview of
exactly what goes along with every AI request and call. It starts empty; a part that would give Kurooto feelings, a
backstory or "I missed you" is left out when you save, and the page says which
([teaching-kurooto.md](teaching-kurooto.md#your-persona-card)). Then your profile (`about-me/profile.md` in your notes), in an editor: **Save** keeps the previous version beside it
(`profile-<date>.md`), **Revert** goes back to what's saved, and **Preview In brief** shows exactly the part that goes
along with every AI request (the section under `## In brief`; a warning shows when there is none). With no profile
yet, the page links to the setup page's About you step. See [teaching-kurooto.md](teaching-kurooto.md).

### Settings (Alt+S)

Settings are grouped by section. The page shows the core sections (you, notifications, availability, updates, AI,
questions, look, power, notes, files, AI limits (`quota`), health checks, AI jobs, sources for answers, skills in other
AI programs (`agents`), this computer (`hardware`), the dashboard's port (`web`), and **Starting**) and the sections of
each feature that's **on**. A feature's settings appear once you turn it on.

- **Change one:** tick a box, pick from a list, or type a value and leave the box (Tab or click elsewhere). It saves at
  once and says "Saved." right under that setting. A setting that takes one of a few values (your AI, its fallback,
  `brain.classify`, `updates.mode`, `updates.channel`, `power.on_battery`, the layouts) is a list to pick from. Lists
  and groups (like `["status"]` or `{"night": "23:15"}`) are shown whole in a box of several lines and typed as JSON;
  if what you typed isn't valid, it says so under the setting and saves nothing.
- **What a setting does:** the line under each setting says it in a sentence (hovering its name shows the same). Click
  that line for its whole entry: what it does, its values and default, when you'd change it, what it costs or sends
  outward, and what it depends on, with a link to it in the [settings guide](settings-guide.md). The search box looks
  through those entries too, so "battery" finds `power.on_battery`, and an entry that matched opens by itself.
  `look.settings_guide` off hides those lines (and the search keeps to the settings themselves).
- **Go back to a default:** type the default value back (every default is in the
  [settings guide](settings-guide.md)), or delete that line from `settings.json`.
- **Starting** has its own choice (when you log in, or on Linux when the computer starts) and says what it did.
- **Settings not on the page** (the features that are on, which the Features page changes, and Telegram's pairing:
  `telegram.chat_id`, `telegram.allowed_users`, `telegram.api_base`) are in `settings.json` in Kurooto's settings
  folder (`kurooto paths` → config), like every other setting. It holds only what you changed; a dotted name like
  `brain.main` is `{"brain": {"main": "…"}}`. Restart Kurooto after editing the file by hand (`kurooto stop`, then
  `kurooto start`).
- Secrets (keys, tokens) are never on this page or in `settings.json`.

## Search, hiding features, bigger panes

### Search

Features and Settings each have a search box at the top. Press **/** or **Ctrl+F** while the page is open (Ctrl+F a
second time is the browser's own find). It filters as you type, ignoring case; every word has to be found somewhere.

- Features are found by name, description, privacy line and their settings. A card found only by a setting says which
  ("its settings: deadlines.ping_h").
- Settings are found by section, name, help text and current value.
- The words found are marked, with a count ("3 of 41 features"), or "nothing matches".
- **Esc** empties the box.

### Hiding features

A feature that's off has **hide** on its card: it leaves the Features page and nothing else changes (Telegram, the
setup page and everything else still know it; it stays off). A feature that's on always shows. **Show hidden (N)** at
the bottom lists hidden ones with **Unhide**, and a search still finds them, marked *hidden*. Turning a hidden feature
on from a search unhides it.

**Setting:** `look.hidden_features` (default `[]`). *Undo:* Unhide, or empty the list.

### Bigger panes and the panes menu (dense layout)

- **Fill the board with one pane:** click its name (⤢) or double-click its border. **Esc** or its name again brings
  the others back.
- **panes ▾**, in the top bar (classic: the board's top-right corner), hides STATUS, SYSTEMS, NOTES or TERMINAL (one always stays) and the
  others take the room. It also lists the pages with their keys, and **show them all**.
- What's hidden is the setting `look.panes` (e.g. `["status"]`), so every browser shows the same.
  *Undo:* panes → show them all, or empty `look.panes`.
- Only what's on screen is drawn, so a hidden pane costs nothing.

## Links to other sites

Links to other sites (Google sign-in, a token page, Cloudflare, AI Studio, the guides) open in this computer's default
browser, even when the dashboard is in another browser's app window. Kurooto's own pages stay where they are, and
Ctrl-, Shift-, Alt- or ⌘-click still opens a link in the browser you're in. If the default browser can't be reached,
the link opens here. On Linux and macOS a `$BROWSER` you've set is used.

**Setting:** `look.links_in`: `default` (the default browser) or `here` (the browser showing the page).

## The morning page

`http://127.0.0.1:8770/morning` shows today's plan from your daily note ("## Plan for today"), with your classes
(skipped ones marked), calendar, what's due soon, **Time to start** (from [Start-by dates](reminders-and-deadlines.md)),
check-ins, open questions, the next alarm and today's study hours. **Open today's note** opens the note itself. It is
read-only and refreshes every 5 minutes.

The [Morning alarm](calls.md) opens it in your browser when it rings, if this computer is awake (`alarm.open_page`,
default on). Without a plan yet it says so: with Chat on and the alarm set, one is drafted 20 minutes before the alarm.

## The Proposals page

`http://127.0.0.1:8770/proposals` (the **proposals** link at the top of the dashboard, and on the Help with your
project card) lists every change the AI proposed and is waiting for your OK: its title and summary, the files, whether
its checks passed, and the whole diff, coloured (added lines green, removed red). A proposal that deletes files says so
in red at the top. **Apply**, **Discard**, and **Change** with a box for what you want different; applied ones keep an
**Undo**. With Help with your project on, a box at the top asks the AI to work on one of your projects (those you let
it help with). [Projects and proposals](proposals.md) has the details.

## Colours

Kurooto's pages (setup, dashboard, morning page, and the terminal colours) come in three palettes of its own, and
in well-known named themes:

| Palette | Looks |
|---|---|
| **kuro** (default) | deep greens |
| **rose** | the pinks of earlier versions |
| **system** | this computer's own accent colour and light or dark mode, followed as they change (within half a minute, without reloading) |
| a named theme | Catppuccin, Tokyo Night, Rosé Pine, Gruvbox, Nord, Dracula, Everforest, Kanagawa or Solarized, in the project's own colours |

Where **system** looks, best first: on Linux, Material You colours made from your wallpaper by matugen, then pywal,
then KDE's accent colour, GNOME's (47 or later) and your GTK theme's; on Windows the accent colour and app mode
(Settings → Personalization → Colors); on macOS the accent colour and appearance. When nothing is found, the pages look
like kuro until something is. Dashboard → Settings → Look says what was found.

**Your own colours file:** `look.theme_file` = the full path of a kitty theme (lines like `background #1a1110`) or a
matugen or pywal `colors.json`. It's used instead of the desktop's colours and switches the palette to system.

Text always stays readable: a colour that would be hard to read on its background is made lighter or darker until it
passes the WCAG AA contrast level (4.5:1). The dashboard is always dark; the setup and morning pages follow light or
dark mode. Your call line's pages on the phone stay green.

### Named themes

Each theme is a family with a dark flavour and a light one. The dashboard and the terminals are always dark, so they
use the dark flavour you pick; the setup and morning pages use the family's light flavour when your browser is in
light mode. Pick one on the setup page's **Colours** (under "Or a named theme", with a few of its colours) or in
**Settings → Look → `look.palette`** (the dots under it show the dashboard's colours and the light pages').

| `look.palette` | Dashboard and terminals | Light pages |
|---|---|---|
| `catppuccin-mocha`, `catppuccin-macchiato`, `catppuccin-frappe` | Catppuccin Mocha, Macchiato or Frappé | Catppuccin Latte |
| `tokyonight-night`, `tokyonight-storm`, `tokyonight-moon` | Tokyo Night, Tokyo Night Storm or Moon | Tokyo Night Day |
| `rose-pine`, `rose-pine-moon` | Rosé Pine or Rosé Pine Moon | Rosé Pine Dawn |
| `gruvbox` | Gruvbox Dark | Gruvbox Light |
| `nord` | Nord | Nord Light (Nord's own colours as Nord describes them for light designs: Snow Storm backgrounds, Polar Night text) |
| `dracula` | Dracula | Alucard |
| `everforest` | Everforest Dark (medium) | Everforest Light (medium) |
| `kanagawa-wave`, `kanagawa-dragon` | Kanagawa Wave or Dragon | Kanagawa Lotus |
| `solarized` | Solarized Dark | Solarized Light |

The colours are the projects' own, exactly as they publish them. Kurooto still keeps text readable: where a theme's
colour is too faint to read as text on its background (common in light flavours, and in Solarized and Nord), that
colour is made a little darker or lighter, keeping its hue, until it passes 4.5:1; backgrounds and lines are never
changed. The developer notes ([core.md](../dev/core.md#colours-palettes-and-named-themes-corepalettepy-corethemespy))
list every colour that moved.

Credits (the palettes, under their own licences; Kurooto copies only the colour values):

| Theme | By | Source | Licence |
|---|---|---|---|
| Catppuccin | the Catppuccin org | [catppuccin/palette](https://github.com/catppuccin/palette) | MIT |
| Tokyo Night | folke (from enkia's Tokyo Night) | [folke/tokyonight.nvim](https://github.com/folke/tokyonight.nvim) | Apache-2.0 |
| Rosé Pine | the Rosé Pine org | [rose-pine/palette](https://github.com/rose-pine/palette) | MIT |
| Gruvbox | morhetz | [morhetz/gruvbox](https://github.com/morhetz/gruvbox) | MIT/X11 |
| Nord | Sven Greb | [nordtheme/nord](https://github.com/nordtheme/nord) | MIT |
| Dracula | the Dracula Theme org | [dracula/dracula-theme](https://github.com/dracula/dracula-theme) | MIT |
| Everforest | sainnhe | [sainnhe/everforest](https://github.com/sainnhe/everforest) | MIT |
| Kanagawa | rebelot | [rebelot/kanagawa.nvim](https://github.com/rebelot/kanagawa.nvim) | MIT |
| Solarized | Ethan Schoonover | [ethanschoonover.com/solarized](https://ethanschoonover.com/solarized) ([altercation/solarized](https://github.com/altercation/solarized)) | MIT |

| Setting | Default | Effect |
|---|---|---|
| `look.palette` | `kuro` | `kuro`, `rose`, `system` or a named theme (above); the dashboard reloads to take it |
| `look.theme_file` | empty | a colours file to use instead of the desktop's |

Also on the setup page's "Your computer" step (**Colours**). *Leaves your computer:* nothing.

## Keyboard shortcuts

Shortcuts don't fire while you type in a box, and inside a terminal the terminal keeps its own keys (Alt+F is a word
forward in a shell, Ctrl+K is the shell's). On a Mac, Option+letter in a text box types a character instead of opening
a page.

| Keys | Does | Where |
|---|---|---|
| **Ctrl+K** / ⌘K | open or close the do-anything line | anywhere outside a terminal |
| ↑ ↓, Tab, Enter, Esc | pick, complete, run, close (in the Ctrl+K line) | Ctrl+K |
| **Alt+T** | Today | |
| **Alt+A** | Activity | |
| **Alt+J** | AI jobs | |
| **Alt+C** | Schedule | |
| **Alt+F** | Features | |
| **Alt+P** | Phone | |
| **Alt+R** | Research | |
| **Alt+Y** | About you | |
| **Alt+S** | Settings | |
| the same Alt key again | closes that page | dense layout |
| **Esc** | closes the panes menu, then the open page, then gives back the panes when one fills the board | dense layout |
| **Alt+M** | Study mode on or off | anywhere outside a terminal |
| **Alt+1** … **Alt+9** | switch the terminal pane's tabs (roomy: the Terminals tab's) | not in Study mode |
| **Alt+/** or **/** | find a note on the NOTES map (Enter jumps, Esc closes) | `/` only outside Features and Settings |
| **/** or **Ctrl+F** | the search box | Features and Settings pages |
| **Esc** | empties the search box | Features and Settings |
| **L** | open or fold every corner panel and legend | the board |
| **R** | highlight notes edited in the last day (Recent) | the board, while the NOTES map is showing (not while you type in a box) |
| **Enter** | send | the kurooto chat tab, the Today box |
| **↑ / ↓** | earlier lines you typed | the kurooto chat tab |
| **Ctrl+L** | clear the chat tab | the kurooto chat tab |
| **Ctrl+Enter** (⌘Enter) | save the journal entry | Today page |
| click a pane's name, or double-click its border | fill the board with it; again (or Esc) to go back | dense layout |

## kurooto top: the board in a terminal

`kurooto top` shows the same board in any terminal (Windows 10 and later, macOS, Linux), laid out like btop: this
computer (processor history and every core, speed, load, temperatures and fans, memory and swap, the graphics card,
network down and up graphs, disks, the battery, the busiest processes) beside Kurooto (running or not, the battery
mode, the call line and its heartbeat, Kurooto's own process and the features' programs, today, what's due, AI
requests, what's next, study today, projects, recent events), with lights for Kurooto, Telegram and the call line,
today's event count and a trace that beats with each event.

| Key | Does |
|---|---|
| `q` (or Esc, Ctrl+C) | quit |
| `r` | refresh now |
| `c` | sort processes by cpu |
| `m` | sort processes by memory |

- `kurooto top --once` prints one screen and exits (for scripts, or a terminal that can't redraw).
- Its colours are your palette, in true colour where the terminal has it. `NO_COLOR=1 kurooto top` turns colours off.
- What a computer can't tell is left out: most Windows and Mac computers give no temperatures or fans; live
  graphics-card figures need `nvidia-smi` (or an AMD card on Linux).
- It only reads, so it's safe to run while Kurooto is busy.

`kurooto logs` shows the end of Kurooto's log (`-n 200` for more lines); `kurooto logs -f` keeps following it
(Ctrl+C stops).

## Terminals (in the dashboard)

**What it does.** Real terminals inside the dashboard: your AI's own program (agy or Claude Code, started in your notes
folder as you'd run it yourself; one tab for each that's installed, the one you use first), your usual shell
(PowerShell on Windows), `kurooto ask` (plain English, like Telegram) and Kurooto's log.

**Turn it on:** Dashboard → Features → Terminals → Turn on. **Only turn this on if you're the only person who uses
this computer:** anyone who can open your dashboard can type into these terminals.

**Using them.** In the dense layout they're tabs in the TERMINAL pane's border; in roomy, a **Terminals** tab.
**Alt+1**, **Alt+2** … switch between them. Each starts the first time you open it. They keep running when you close the
page and show where they were when you open it again. One that ended starts again when you press a key in it, or with
**restart** (ends the program in that terminal and starts it again).

**Limits.** On Linux a terminal request from another user account is refused on purpose, and if the computer can't tell
who is connecting (no `/proc/net/tcp`), terminals refuse everyone. What you type into your AI program's terminal goes
to that program's service, as when you run it yourself.

**What leaves your computer:** nothing by itself.

**Turn it off:** Features → Terminals → Turn off (the terminals end).

## Kurooto Terminal (a window of its own)

**What it does.** Kurooto in a real terminal window of its own, laid out like the dashboard's terminals: a tab each for
your AI's own program (agy or Claude Code, started in your notes folder; whichever is installed if your AI is an API
key), your shell, Kurooto chat (`kurooto ask`, with a `kurooto ❯` prompt; type plain English as on Telegram) and
Kurooto's log, with `kurooto top` as a column on the left of the first tab. Everything is in Kurooto's colours.

**Turn it on:** Dashboard → Features → Kurooto Terminal. It then appears in your app menu (Start menu, Launchpad,
your Linux launcher) as **Kurooto Terminal**. If there's no terminal program at all, **Set up** gets one.

**Open it:**

| Command | Does |
|---|---|
| `kurooto term` | the whole window |
| `kurooto term --shell` | just your shell in Kurooto's colours (also **Kurooto Shell** in the Linux app menu, and Windows Terminal's **Kurooto** profile) |
| `kurooto term -e CMD` | one window in Kurooto's colours running CMD |
| `kurooto term --print` | shows what it would open, opens nothing |
| `kurooto term --install` | gets kitty and fish into Kurooto's own folder |
| `kurooto term --default on/off/status` | make it your default terminal, undo, or say whether it is |

**Per system:**

| | What it uses |
|---|---|
| Linux, macOS | **kitty**: yours if you have it, otherwise `kurooto term` offers once to get the official kitty into Kurooto's folder (about 45 MB, no admin, checksum checked). Tabs switch with Alt+1 to Alt+9 on Linux, Cmd+1 to Cmd+9 on a Mac. Your own `kitty.conf` is read first and never changed. Without kitty, each tab opens in a window of your usual terminal. |
| Windows | **Windows Terminal** (built into Windows 11; free in the Microsoft Store for Windows 10). Turning the feature on adds Kurooto's profiles and colour scheme (no admin); chat, top, logs and your AI appear in Windows Terminal's new-tab menu. Without Windows Terminal, each tab opens in a console window. |
| The shell | **fish** if you have it; otherwise `kurooto term` offers once to get the official fish into Kurooto's folder (Linux 3 MB; Mac the 17 MB fish app, not installed system-wide). If you say no, your own shell (PowerShell on Windows). |

**Settings that matter** (Dashboard → Settings → Kurooto Terminal, once it's on):

| Setting | Default | Effect |
|---|---|---|
| `terminal.tabs` | `["agent", "shell", "chat", "logs"]` | the tabs, in order; `top` can be one too |
| `terminal.top` | `left` | `left`: a column beside the first tab; `tab`: a tab of its own; `off` |
| `terminal.shell` | `auto` | fish if you have it, else yours; or a program such as `zsh` or `pwsh` |
| `terminal.font_size` | `11` | the font size |
| `terminal.kitty` | on | Linux and macOS: off uses your usual terminal, a window per tab |
| `terminal.default` | off | make Kurooto Terminal your default terminal |
| `terminal.default_opens` | `shell` | what "open a terminal" gives while it's your default: `shell` or `layout` (the whole window); `kurooto term` always opens the whole window |

**Your default terminal** (off unless you turn it on):

| | What changes | Undo |
|---|---|---|
| Linux | Kurooto Shell (or Kurooto Terminal with `default_opens` = `layout`) goes first in `~/.config/xdg-terminals.list`, which newer GNOME and many window managers use for "open a terminal". Your keys and window manager config aren't touched: bind a key to `kurooto term --shell` yourself. | `terminal.default` off or `kurooto term --default off`: the list goes back exactly as it was (or just Kurooto's line comes out if you've changed the list since) |
| Windows | Windows Terminal's default profile becomes **Kurooto** (a backup of its `settings.json` is taken first) | the same: `settings.json` goes back from the backup, or just the default profile if you changed other things since |
| macOS | nothing to change: keep Kurooto Terminal (in your Applications folder) in the Dock | nothing to undo |

Backups of anything Kurooto changed are in the state folder under `terminal/backups`.

**What leaves your computer:** nothing.

**Turn it off:** Features → Kurooto Terminal → Turn off. The app-menu entries and Windows Terminal profiles are
removed and "default terminal" is undone. kitty or fish that Kurooto got stay in its folder until `kurooto uninstall`.

## When something looks wrong

| What you see | What to do |
|---|---|
| The page won't open | Is Kurooto running? Start it from the app menu or `kurooto on`, then `kurooto open`. If the port moved, `web.json` in the state folder says which one. |
| "reconnecting…" in a pane's top line | Kurooto stopped or is restarting; the page reconnects by itself. |
| "Kurooto didn't answer (is it running?)" on Today or Ctrl+K | the same: start it, then try again. |
| A feature's settings aren't on the Settings page | Turn the feature on first; its section then appears. |
| "That isn't valid; it wasn't saved" | A list or group must be valid JSON, e.g. `["pe"]` or `{"night": "23:15"}`. |
| "needs a look" badge | Click it (or open Features): the Needs a look box says what, with a Fix button where Kurooto can fix it. |
| Corner panels show only one line each | They're folded on purpose (0.5.8): point at one, or press **L** to open them all. |
| Ctrl+K does nothing | The cursor is inside a terminal (Ctrl+K belongs to the shell there): click the board first. |
| An Alt key types a character on a Mac | You're in a text box: click outside it first. |
| The NOTES map shows everything as "Other Notes" | Neighbourhoods come from `sources/<subject>/`, `maps/` and `projects/` folders (the zettelkasten layout); with other folders, notes join by their links. |
| Double-clicking a note opens the wrong program | Set `notes.open_with` (e.g. `code {path}`), or empty it for the default app. |
| The system palette doesn't use my colours | Settings → Look says what was found; changes show within half a minute. Point `look.theme_file` at a kitty theme or a matugen or pywal `colors.json`. |
| The Terminals tab says it's off, or a terminal won't type | Features → Terminals → Turn on. On Linux, a terminal from another user account is refused on purpose. |
| Kurooto Terminal opens separate windows instead of tabs | kitty (Linux, macOS) or Windows Terminal isn't there: `kurooto term --install`, or Windows Terminal from the Microsoft Store. `kurooto term --print` says what it found. |
| "kitty didn't start" | kitty needs a graphics driver with OpenGL 3.3 (some virtual machines lack it): set `terminal.kitty` off. kitty's own message is in `terminal/kitty.log` in the state folder. |
| Kurooto Terminal's tabs or colours look old in Windows Terminal | Close every Windows Terminal window and open it again. |

## What the board shows (?)

Press `?` anywhere on the board (not while typing) for a card that explains it: the beating core is Kurooto itself
(faster when busier); each cell is a feature that's on, breathing faster when busy and flashing when something
happens; a dot along a nerve is something arriving (into the core) or Kurooto acting (out to a cell); a ripple is news
for no one feature; a grey dashed cell isn't running. In NOTES each dot is a note (bigger with more links), lines are
links and colours are neighbourhoods (one per course or subject folder). It also says what Study mode is. `?` again
or Esc closes it.

**Processor numbers (0.5.21).** Every processor figure on the board is a share of the whole machine, over a steady window: the CPU total, each process in Processes, "kurooto" in the SYSTEMS header (Kurooto and every program it started: the AI reading your books, the call server, your terminals) and each feature cell's. 100% would be every core busy, so they add up and never pass 100%.
