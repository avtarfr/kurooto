# Updates, backups and moving

Kurooto updates itself at night, can make a daily backup zip, can keep your whole setup encrypted in your own GitHub
repository, and cleans up after itself. This page covers all of that, plus moving to a new computer and uninstalling.

- [Updates](#updates)
- [Backups](#backups)
- [Putting a backup back (restore)](#putting-a-backup-back-restore)
- [Profile sync](#profile-sync)
- [Moving to a new computer](#moving-to-a-new-computer)
- [Space keeper](#space-keeper)
- [Uninstall](#uninstall)

---

## Updates

**What it does.** Kurooto looks for a new version every 6 hours. By default it downloads a new version when it finds
one and switches to it during the night, between 03:00 and 05:00, at a random moment in that window. You don't have to
do anything.

**Safety rules it always follows:**

- **Every release is signed.** Kurooto refuses anything unsigned, older than what you have, or changed on the way.
- **Withdrawn versions are never installed.** When a release turns out to be broken, its maintainer puts it on a
  signed "yank list". Kurooto never installs a version on that list: not when it finds it, not when it already
  downloaded it for tonight, and not with `kurooto update --now`. It keeps the last list it read, so a withdrawn
  version stays refused while the release site can't be reached. A list that isn't signed, or is older than one it
  has seen, stops the update instead. The yank list can't be turned off.
- **It waits for a quiet moment.** At switch time, if the AI is working on a request or you're on a call, it tries
  again 20 minutes later.
- **It undoes a bad update by itself.** A new version is "on trial" for its first five minutes. If it crashes three
  times in that time, Kurooto goes back to the version before, remembers the bad one and never offers it again. You get
  a message: "Kurooto X didn't start properly, so I went back to Y. It won't be installed again; a later version
  will be."
- **Old versions are kept for going back.** The version you run, the one before, and one more stay installed; older
  ones are deleted.

After a successful update (five minutes in, once the trial is over) you get one line: "Kurooto updated to X." An
update's restart doesn't send a "going offline" message.

**Choose how updates happen** (Dashboard → Settings → updates):

| Setting | Default | What it does |
|---|---|---|
| `updates.mode` | `night` | `night`: download when found, switch during the night window. `ask`: Telegram asks you first. `off`: never update by itself (it still notes that a version is available) |
| `updates.window` | `["03:00", "05:00"]` | the hours the night switch may happen |
| `updates.channel` | `stable` | `stable`, or `beta` for earlier test releases |
| `updates.staged` | `false` | wait before installing a new version (below) |
| `updates.wait_hours` | `48` | with `staged` on: how long a new version must have been out first |
| `updates.exam_hold` | `true` | with `staged` on: nothing installs during an exam period or within a day of a quiz or exam |

**The ask mode's buttons.** With `updates.mode` = `ask`, a Telegram message says "Kurooto X is available" with the
release notes and three buttons:

| Button | What happens |
|---|---|
| **Update** | Downloads it now and restarts on it ("I'll be back in a minute") |
| **Later** | Nothing now; you're asked again at a later check (checks run every 6 hours) |
| **Skip this version** | That version is never offered again; the next one will be |

**Staged updates** (off until you set `updates.staged` = `true`). A new version waits until it has been out
`updates.wait_hours` (48 hours), so a broken release is usually withdrawn before it reaches you. With
`updates.exam_hold` on, nothing installs during your exams: an exam period from your term dates (`/term exams ...`, see
[Classes and timetable](classes-and-timetable.md)) or a quiz or exam within a day on your deadline list. A release the
maintainer signed as **critical** (a security fix) skips both waits. While a version waits, the dashboard's update badge
says "waiting" (point at it to see why).

**Exam season's hold.** If you turned on the optional [Exam season](quiz-and-exams.md) feature and its "Hold
non-critical updates" part is on, updates wait until your exams are over. This only happens when you turned Exam
season on yourself; it's off by default and in no preset. Critical releases still install.

**From a terminal:**

| Command | What it does |
|---|---|
| `kurooto update` | says whether a newer version is available (or which version was withdrawn) |
| `kurooto update --now` | installs the newest version right away and restarts on it. It ignores the night window, staged waiting and holds, but never installs a withdrawn version |
| `kurooto --version` | the version you run |

**The beta channel** is for testers. Install with `KUROOTO_CHANNEL=beta` in front of the install line (see
[Getting started](getting-started.md)); the install then keeps following beta. To go back: Settings →
`updates.channel` = `stable`. You get the next stable release once it's newer than the beta you have.

**What else updates:**

- **Your call line** (with [Phone calls](calls.md) on) is redeployed after Kurooto updates, when its code changed or
  the release brings a new Android app (downloaded after the update and checked against the signed release, so the
  line hands out the app that goes with your version). This happens in the background at 05:10. If it fails you get "Your call line couldn't be updated: ..." and calls keep
  working on the old version; Features → Phone calls → Set up tries again. With `updates.mode` = `off`, the line isn't
  updated either.
- **The Android app** checks for a new version each time you open it (at most every 2 minutes) and shows an **Update**
  button that opens the download. See [Phone app](phone-app.md).
- **The iPhone Home Screen app** updates itself.

**Limits and edge cases.**

- A copy of Kurooto not installed with the official installer can't update itself; `kurooto update` says so.
- If the update can't be prepared (no internet, not enough room), you get "Couldn't prepare Kurooto X: ... I'll try
  again later."
- On a laptop asleep during the night window, the switch happens when it can (up to six hours late), or the next night.

**What leaves your computer.** Only requests to Kurooto's public release site to fetch the release list, the yank list
and the files. Nothing about you is sent.

**Turn it off / undo.** `updates.mode` = `off`. To go back to an earlier version by hand, run the install line again
(it repairs or reinstalls); the automatic rollback above covers the usual case. `updates.staged` = `false` installs new
versions as soon as they're found.

---

## Backups

**What it does.** Once a day, a zip of Kurooto's settings, data and state goes into a folder you pick: a folder on an
external drive, or one your computer already syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox), so the
zip goes there too. Zips are named `kurooto-backup-<date>-<time>.zip`.

**Turn it on.** Dashboard → Features → Backups → paste the folder's full path. The card lists cloud folders and drives
it found on this computer. The folder must:

- already exist (make it first, or plug the drive in),
- be a full path (starting from the drive),
- be outside your notes folder,
- be writable by Kurooto.

**What's in a zip:**

| Always | Only if you turn it on |
|---|---|
| Your settings and which features are on | `backups.notes`: your notes folder (without `.git`, `.trash`, `.obsidian` and `node_modules`). Turn it on if your notes aren't synced anywhere else |
| Kurooto's data, including the notes brain's index (`backups.index` off leaves the index out) | `backups.secrets`: your passwords and keys (bot token, API keys, sign-ins). **Anyone with the zip can then use them**, so only for a folder that's yours alone |
| Its state: check-ins, deadlines, AI requests and answers, the schedule | `backups.confidential_mail`: confidential mail summarised on this computer by the Mail digest's local mode |
| | `backups.memory`: the [memory ledger](privacy.md#the-memory-ledger) (gists, threads, what's read from your notes). It stays encrypted in the zip and opens only where its key is; on another computer only with `backups.secrets` too |

**Never in a zip:** your test cases from the Wrong button (they hold what you typed), logs, locks, and a few files that
only mean something to the running program. The zip **isn't encrypted**.

**When it runs.** At 03:30 (`backups.when`). On a laptop on battery it waits for the charger (see
[Your computer](your-computer.md#on-battery)). If a day went by without a backup (the drive was unplugged, the laptop
was off), it makes one within the hour once it can. A scheduled run is skipped if a backup succeeded in the last 12
hours.

**From Telegram:**

| Command | What it does |
|---|---|
| `/backup` | makes a backup now (also on battery); you get a message when it's done, with the file and its size |
| `/backups` | the last 10 backups in your folder, their sizes, what they include and how many are kept |

**From a terminal:** `kurooto backup` makes one now; `kurooto backup --to <folder>` makes a one-off copy in another
folder (handy before reinstalling). A one-off copy never removes older zips.

**Settings that matter** (Dashboard → Settings → backups):

| Setting | Default | What it does |
|---|---|---|
| `backups.folder` | empty | where the zips go |
| `backups.when` | `daily 03:30` | when the daily backup runs |
| `backups.keep` | `7` | how many zips to keep; Kurooto removes only its own older zips, never anything else in the folder |
| `backups.notes` | `false` | include your notes folder |
| `backups.secrets` | `false` | include passwords and keys |
| `backups.index` | `true` | include the notes brain's index (big, but slow to rebuild) |
| `backups.confidential_mail` | `false` | include locally summarised confidential mail |
| `backups.memory` | `false` | include the memory ledger (encrypted; restoring it elsewhere needs `backups.secrets`) |

With the [Space keeper](#space-keeper) on, zips also go when together they pass `space.backups_max_gb` (3 GB) or are
older than `space.backups_max_age_days` (off). The newest zip is never removed.

**Limits and edge cases.**

- An unplugged drive is normal for a day or two: `kurooto doctor` only notes it. After 3 days without a backup you get
  "Backup didn't work: the backup folder isn't there ...", at most once a day.
- Files another program holds open are skipped; the result says how many couldn't be read.
- Only one backup runs at a time ("a backup is already running").
- "Not enough room in the backup folder": free space there, lower `backups.keep`, or turn `backups.index` off.

**Messages it sends by itself.** "Backup didn't work: ..." (at most once a day; reason `backups.failed`). A successful
nightly backup sends nothing. See [Messages it sends](messages-it-sends.md).

**What leaves your computer.** The zip goes only to the folder you pick. If that folder syncs to a cloud, it goes
there too.

**Turn it off.** Features → Backups → Turn off. The zips already made stay where they are.

---

## Putting a backup back (restore)

`kurooto restore <zip>` puts a backup back. It is a terminal command; there's no Telegram command for it, since
Kurooto has to stop.

What it does, in order:

1. Shows what's in the zip (when it was made, with which version, how many files, whether it has notes and keys) and
   asks "Restore it? [y/N]".
2. Stops Kurooto the normal way (so Notes sync sends up what's left first). If it hasn't stopped after 90 seconds, it
   is stopped.
3. Keeps a copy of how things are now, in Kurooto's data folder under `restore-safety/` (the last two are kept). If it
   can't make that copy, nothing changes.
4. Replaces Kurooto's settings, data and state with the backup's, and its passwords and keys if the zip has them.
5. **Adds your notes, never overwrites them.** A note that's missing comes back. A note that's the same is left. A note
   that's different now is kept as it is, and the backup's copy goes into `restored-<date>/` in your notes folder for
   you to compare.
6. Starts Kurooto again.

| Flag | What it does |
|---|---|
| `--yes` | doesn't ask first |
| `--no-notes` | leaves your notes folder alone |
| `--no-start` | doesn't start Kurooto afterwards (`kurooto start` later) |

**Edge cases.**

- Restoring onto another kind of computer (Windows to Mac, say) works. If the backup's notes folder doesn't exist
  here, the default notes folder is used.
- Without keys in the zip, sign in again where Kurooto asks (AI, Telegram token, Google).
- If a restore goes wrong: `kurooto restore <the zip in restore-safety/>` puts things back as they were before it.
- "Nothing was restored: ... is still open in another program": Kurooto (or something else) still has a database open.
  Stop it and try again; nothing was changed.

---

## Profile sync

**What it does.** Your Kurooto setup, kept **encrypted** in your own private GitHub repository, so a new computer (or a
reinstall) is ready in a minute instead of an evening.

**What's saved:**

- everything you changed in Settings, and which features are on;
- your passwords and keys: bot token, API keys, the Google sign-in, your call line's keys and its Cloudflare sign-in
  (so the same call line and the same paired phones keep working);
- state worth keeping: deadlines, recurring quiz state, quiz progress, routines, what the nightly look back has
  observed, the Agent plan calendar, Classroom's "already seen" lists, and reminders, calls and the alarm you've
  scheduled.

**Not saved:** your notes (Notes sync keeps those), AI request history, call transcripts, the reports you added in
About you, confidential mail summaries, caches and logs, and this computer's own dashboard key. Folder settings (notes
folder, backup folder, add-ons folder, files folder) are only kept where that folder exists on the new computer.

**Turn it on.** Features → Profile sync. Needs Git (Notes sync's Set up installs it).

1. Leave the repository and token empty to use the repository Notes sync uses. The profile goes on a branch of its
   own, `kurooto-profile`, so your notes folder never sees it. Or give another private repository (`owner/name`) and a
   fine-grained token for it with Contents: Read and write.
2. Pick a **passphrase** of a few words, at least 10 characters. You need it on a new computer. It's never stored
   anywhere; this computer keeps only the unlocked key in its keychain so it can save by itself.

If you forget the passphrase, the profile can't be opened. Your notes are still fine: delete the `kurooto-profile`
branch on GitHub (or use another repository) and set up Profile sync again with a new passphrase.

**When it saves.** Once a day at 04:40 (`profile.when`), and 10 minutes after you change a setting or turn a feature on
or off (`profile.after_changes`; a burst of changes makes one save). A profile is small, so it also runs on battery.
If nothing changed, nothing is sent.

**From Telegram:**

| Command | What it does |
|---|---|
| `/profile` | where it's saved, when it was last saved, and how many settings, features, keys, saved items and scheduled things it holds |
| `/profile save` | saves now, also over a profile another computer saved (the old one stays in the branch's history) |

**From a terminal:**

| Command | What it does |
|---|---|
| `kurooto profile status` | the same as `/profile` |
| `kurooto profile save` | saves now; the first time it asks for the repository and a passphrase. `--replace` saves over a profile another computer saved |
| `kurooto profile restore` | brings your profile to this computer (below) |

**Two computers.** If another computer saved the profile since this one last did, this one doesn't overwrite it. It
tells you (at most once a week), `/profile` and `kurooto doctor` say so. Restore it here (`kurooto profile restore`),
or save over it (`/profile save`).

**Messages it sends by itself.** "Profile sync didn't work: ..." (at most once a day), and "another computer saved
your profile since this one did" (at most once a week). Both use the reason `profile.failed`.

**What leaves your computer.** Your settings, keys and saved state go to your own private GitHub repository,
encrypted with your passphrase. Your notes and AI history aren't in it.

**Turn it off.** Features → Profile sync → Turn off. What's in the repository stays there; delete the
`kurooto-profile` branch on GitHub to remove it.

---

## Moving to a new computer

**With Profile sync on** (on the old computer):

1. On the old computer, if it still works: `/profile save` (or wait for the daily save), then **turn Kurooto off
   there** with `kurooto off`. Two computers can't share one Telegram bot or one call line: the second one gets
   "Another program is reading this bot's messages".
2. Install Kurooto on the new computer (see [Getting started](getting-started.md)). On the setup page's first step,
   press **I've used Kurooto before** and give the repository (`owner/name`), a token for it (lost it? make a new
   fine-grained token for that repository with Contents: Read and write) and your passphrase.
3. Kurooto restores your settings, keys and saved items, turns on every feature that's ready, and, with Notes sync,
   brings your notes back. It lists what's left to do here. **Continue** walks you through it: sign your AI in again
   (agy and Claude Code keep their sign-ins on the computer they ran on), install what features need (Git, the notes
   brain, local AI models), and pick folders that were on the old computer (backup folder, add-ons folder).

**From a terminal instead:** `kurooto profile restore --repo owner/name`. It asks for the token and passphrase without
showing them, stops Kurooto, restores, offers to set up what's left, and starts it again. `--yes` doesn't ask first;
`--no-start` doesn't start Kurooto afterwards. For scripts, the passphrase can come from the environment variable
`KUROOTO_PROFILE_PASSPHRASE`.

Before restoring, Kurooto keeps a copy of the settings it replaces in its data folder, `profile/before-restore-<date>/`
(the last three). A restore never changes your notes; with Notes sync on and no notes on this computer yet, it brings
them down from your repository.

**Without Profile sync**, use a backup: on the old computer `kurooto backup --to <a USB stick or cloud folder>` (turn
on `backups.secrets` first if you want your keys to move too), then on the new one `kurooto restore <zip>`.

**After moving:** paired phones keep working if the call line's keys moved (Profile sync, or a backup with keys).
Otherwise pair them again (see [Phone app](phone-app.md)).

---

## Space keeper

**What it does.** Cleans off what Kurooto itself piles up, weekly and on request, so it never takes too much room.
**Only Kurooto's own leftovers ever go**, never your notes, files or books.

| What | When it goes | Setting |
|---|---|---|
| Backup zips | more than `backups.keep`; together over `space.backups_max_gb` (3 GB); older than `space.backups_max_age_days` (off). Oldest first; the newest is never removed | `space.backups_max_gb`, `space.backups_max_age_days` |
| Installer downloads, study-pack zips, zips made to send you files, cut-off downloads | older than `space.cache_days` (14) | `space.cache_days` |
| Log files | a log bigger than `space.log_mb` (20 MB) is cut to its newest part | `space.log_mb` |
| Finished AI requests | older than `space.jobs_days` (60) | `space.jobs_days` |
| The search index of past requests, calls and chats ([Learns from its own work](teaching-kurooto.md#learns-from-its-own-work)) | what it holds from more than `space.jobs_days` (60) ago | `space.jobs_days` |
| The concept graph's before-copies and unfinished work files | older than `space.undo_days` (30) | `space.undo_days` |
| Help bundles and restore leftovers | older than `space.cache_days` | |
| Old program versions | beyond the ones kept for going back | |

**Turn it on.** Dashboard → Features → Space keeper. It cleans by itself on Sundays at 04:30 (`space.when`).

**From Telegram:**

| Command | What it does |
|---|---|
| `/space` | how much room each part of Kurooto takes (program versions, downloads and caches, state and logs, its data, backup zips) and what would go |
| `/space clean` | does it now and says how much it freed |

**From a terminal:** `kurooto space` (what would go) and `kurooto space --clean` (do it).

**Messages it sends by itself.** A weekly clean that frees 50 MB or more sends one line ("Space keeper: cleaned off
... of old backups and leftovers"). Smaller tidying is silent.

**Low disk warning.** The feature's health line warns when the disk Kurooto uses has under 2 GB free ("Only ... is free
on the disk Kurooto uses"); `kurooto doctor` and `/health` show it.

**What leaves your computer.** Nothing.

**Turn it off / undo.** Features → Space keeper → Turn off. A removed backup or download can't be recovered (downloads
are made again when needed; the next backup replaces old ones).

---

## Uninstall

**Plain uninstall:** `kurooto uninstall`. It stops Kurooto and removes the program, its settings, data, state, caches
and logs, start-at-sign-in, the app-menu entries, and the copies of your skills it put in agy and other agent programs
(skills you made there yourself stay). On Windows you can also use Settings → Apps → Kurooto.

| Flag | What it does |
|---|---|
| `--keep-data` | keeps your settings and data (for reinstalling later) |
| `--revoke` | first takes back what Kurooto set up on your accounts (below) |

Want a copy first? `kurooto backup --to <folder>`.

**Leaving for good: `kurooto uninstall --revoke`.** While its keys are still on this computer, it first:

| What | What happens |
|---|---|
| Your call line | deleted from your Cloudflare account, with its keys and stored data, then Kurooto's Cloudflare sign-in is signed out. If that sign-in expired (or is for another account), it prints the steps instead: Cloudflare dashboard → Workers & Pages → the `kurooto-...` worker → Settings → Delete |
| Google | each signed-in Google account's access is revoked (Kurooto drops off your Google account's third-party connections) |
| Telegram | your bot's webhook and the messages waiting for Kurooto are dropped, and the command menu Kurooto set is removed. The bot stays yours (`/deletebot` to @BotFather deletes it) |
| Left for you, with links | delete the GitHub token(s) you made for Kurooto, the Gemini key if you made it only for Kurooto, the Google client's Cloud project, and Profile sync's branch |
| Keychain | Kurooto's keys are removed from your system's keychain (also with `--keep-data`; a plain uninstall leaves them there) |

Each line says `ok`, `FAIL` (with what to do yourself) or `--` (nothing was set up). If the revoke step can't run,
nothing is removed and it says so; `kurooto uninstall` without `--revoke` removes Kurooto anyway.

**What always stays:**

- **Your notes folder is never deleted.**
- Backup zips in the folder you picked, and your add-ons folder.
- Programs installed system-wide (agy, Ollama on Windows and macOS, Telegram Desktop), and uv and Python (harmless,
  and other tools may use them). Things Kurooto installed into its own folder (Node.js, MinGit, Ollama on Linux,
  Tectonic, kitty and fish for Kurooto Terminal) go with it.
- Without `--revoke`: your call line stays on your Cloudflare account until you delete it there (paired phones stop
  working once it's gone); the Google client stays in Google Cloud; the Agent plan calendar stays in Google Calendar;
  your notes repository stays yours (delete its `kurooto-profile` branch if you used Profile sync).

**Undo.** None: install again and set up again (sign in to Google, paste your bot's token, Phone calls → Set up makes
a new call line, pair your phones).

**What leaves your computer.** With `--revoke`: Cloudflare gets the request to delete your line, Google the sign-in
being revoked, Telegram the requests to clear the bot.
