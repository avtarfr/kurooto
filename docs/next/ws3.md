# ws3: rhythm and machine (parity rows F8, F9, F10, N11, G13, N15, J3)

The check-in day runs from 05:00, the night check-in waits for the morning when you've gone to bed, the computer can
stay awake until the alarm and (on the charger, Linux) with the lid closed, the study tracker no longer counts idle or
lock-screen time and has a Research category, Kurooto can start from boot on Linux, and Notes sync never loses an edit
made elsewhere.

## MANUAL

### Check-ins (add after the "By call" list, before *Settings*)

- **The check-in day runs from 05:00 to 05:00** (`checkins.day_starts`). A night check-in at 00:30, or one you push
  past midnight ("push the night check-in by 30 min" at 23:50), is still that evening's: it rings at 00:20 and its
  journal and study logs go to the evening's day. Still up at 1 am, "move the evening check-in to 21:00" means the
  coming evening, and "skip the night check-in" skips the coming night's once tonight's is over. Set it to `00:00`
  for calendar days.
- **Gone to bed:** with check-ins by call and the alarm set, the night check-in doesn't ring once it's past your
  bedtime (`alarm.bedtime`), or within 3 hours of you setting the alarm yourself. It moves to your wake-up call, and
  a message says so with **Call me now** and **Skip**. A night check-in you moved after setting the alarm still
  rings. `checkins.asleep_defers` (default on) turns this off.

*Settings (add):* `checkins.day_starts` (default `05:00`), `checkins.asleep_defers` (default on).
*Undo:* `checkins.day_starts` = `00:00` (calendar days, as before 0.3.0); `checkins.asleep_defers` off (the night
check-in always rings).

### Morning alarm (add a bullet)

- **Keep this computer awake until the alarm** (`alarm.keep_awake`, off until you turn it on): from 12 hours before
  the alarm until 15 minutes after it rings (or until you answer), this computer doesn't go to sleep by itself, so
  the day's plan is drafted 20 minutes before the alarm even if it would have slept overnight. Linux: it keeps running
  with the lid closed too. macOS: a closed lid still sleeps a Mac (unless an external display is attached). Windows:
  the lid follows Power Options. On battery, setting the alarm reminds you to plug in. The hold ends by itself, even
  if Kurooto stops; the screen can still turn off.

*Settings (add):* `alarm.keep_awake`.
*Undo:* `alarm.keep_awake` off; it lets go at once.

### Stay awake on charger (replace the section)

While your computer is plugged in, it doesn't go to sleep by itself, so Kurooto keeps answering; on battery it sleeps
as usual. The screen can still turn off.

- **Lid closed (Linux):** turn on `awake.lid` and it keeps running with the lid closed while plugged in (it holds the
  lid switch through systemd-inhibit). If your system doesn't let a background program hold the lid switch, it holds
  the rest and its line in `kurooto doctor` says so.
- **Windows and macOS** can't be changed by an app here. Windows: Control Panel → Power Options → "Choose what closing
  the lid does" → "Do nothing" when plugged in. macOS: only with an external display.
- The hold ends when Kurooto stops, even if it crashes.

*Settings:* `awake.lid` (default off).
*Undo:* `awake.lid` off, or turn the feature off; the computer sleeps as usual at once.

### Study tracker (replace "counts while you're active" and add bullets)

A window counts while you're at the computer: not idle for 5 minutes (`study.idle_min`) and the screen not locked.

- **How it tells you're away:** Windows and macOS from the system's last-input time; Linux from your desktop (X11,
  GNOME, KDE, logind's idle hint). On Hyprland, Sway and other Wayland desktops without an idle API it watches for
  change instead (keyboard and touchpad activity, the cursor on Hyprland, the focused window; nothing you type is
  read). A locked screen never counts (hyprlock, swaylock and other lockers, or your desktop's lock).
- **Your idle tool can tell it** (more exact on Wayland): `kurooto idle away` when you go idle, `kurooto idle back`
  when you're back. hypridle, in `~/.config/hypr/hypridle.conf`:
  ```
  listener {
      timeout = 300
      on-timeout = kurooto idle away
      on-resume = kurooto idle back
  }
  ```
  swayidle: `swayidle timeout 300 'kurooto idle away' resume 'kurooto idle back'`.
- **Research:** a window naming one of `study.research_paths` (words, or folders matched by their name, e.g.
  `~/code/flow-model`) counts as **Research**; with Research on, its projects and repository folders count too.
- `kurooto doctor` says how this computer tells you're away.

*Settings (add):* `study.research_paths` (default empty).
*Undo:* empty `study.research_paths`; remove the idle hook lines (and run `kurooto idle back` once).

### Notes sync (replace the clash paragraph)

**When a note changed in two places at once** (say, your phone and this computer), nothing is lost:

- `notes_sync.on_conflict` = `keep both` (the default): the note keeps the version from elsewhere, and this
  computer's goes beside it as `<note> (conflict, this computer, <date time>).md`. You get a message naming both;
  merge them when you like and delete the copy. Notes changed on one side only merge as usual. A note deleted on one
  side and changed on the other is kept, changed.
- `stop`: sync stops, changes nothing, and tells you (at most every 6 hours) until you've sorted it out yourself in
  the notes folder (`git pull --rebase`, fix the files it lists, `git add`, `git rebase --continue`). It never forces
  anything.
- A merge or rebase left half done in the notes folder (you, sorting one out) is left alone: sync waits until it's
  finished.

**A notes folder that's already a Git repository** keeps its remote: an `origin` that's the same repository (over
HTTPS or SSH) is used as it is; an `origin` that's another repository is left alone and Kurooto adds a remote of its
own (`kurooto`).

*Settings (add):* `notes_sync.on_conflict` (`keep both` | `stop`).
*Undo:* `notes_sync.on_conflict` = `stop`. Conflict copies are ordinary notes: delete them once merged.

### Starting at boot (new section under "Taking your laptop with you", or after "Updates and going back")

Kurooto starts when you log in. On Linux (with systemd) it can start when the computer does, before anyone logs in, so
Telegram and calls work after a power cut or a remote reboot:

- `kurooto autostart boot` turns on lingering for your account (`loginctl enable-linger`; it may ask for your
  password, or say to run that command yourself). Your keychain stays locked until you log in, so Kurooto's keys move
  to its owner-only settings file (`secrets.json`, readable only by your account).
- `kurooto autostart login` goes back: lingering is turned off again only if Kurooto turned it on (if something else
  did, it says so and leaves it), and the keys go back to the keychain.
- `kurooto autostart status` shows which. The setting is `autostart.when`.
- Windows and macOS start Kurooto at sign-in only: starting before would need admin rights (and on Windows your
  password kept in a scheduled task). On a Mac that restarts by itself, automatic login brings Kurooto back.
- If your home folder is encrypted and only unlocked at login, starting at boot can't reach Kurooto's files.

*Undo:* `kurooto autostart login` (or `kurooto uninstall`, which also turns off the lingering Kurooto turned on).

### From a terminal or a script (add rows)

| `kurooto autostart boot\|login\|status` | start before anyone logs in (Linux), or at login; which one |
| `kurooto idle away\|back` | for your idle tool: you've stepped away / you're back (the study tracker) |

## Troubleshooting (add rows)

| What you see | Why, and what to do |
|---|---|
| The laptop still sleeps with the lid closed on the charger (Linux) | `awake.lid` is off, or your system refuses the lid hold to background programs (doctor says so). Allow it in polkit (`org.freedesktop.login1.inhibit-handle-lid-switch`) or set `HandleLidSwitchExternalPower=ignore` in logind.conf. |
| The morning plan wasn't drafted (the computer slept) | Turn on `alarm.keep_awake`, and plug in overnight. |
| Study time counts while I'm away (Wayland) | Add the hypridle or swayidle hook (`kurooto idle away` / `back`). `kurooto doctor` shows what it uses now. |
| Study time stopped counting | A `kurooto idle away` without its `back`: run `kurooto idle back`. |
| A file named "(conflict, this computer, …)" appeared in my notes | The note changed here and elsewhere at once: both versions are kept. Merge them, then delete the copy. |
| Notes sync: "a merge or rebase is unfinished" | Finish it in the notes folder (`git status` says how); sync goes on by itself. |
| `kurooto autostart boot`: "Linux didn't allow that from here" | Run `loginctl enable-linger` in a terminal (it may ask for your password), then `kurooto autostart boot`. |
| The night check-in didn't ring | The alarm was set and it was past your bedtime: it moved to the wake-up call (the message says so). `checkins.asleep_defers` off makes it always ring. |

For AGENTS.md's doctor table: the `Notes sync FAIL` row's fix becomes "a clash: in `stop` mode merge it in the notes
folder (`git pull --rebase`), or set `notes_sync.on_conflict` to `keep both`; an unfinished merge: finish it".

## CHANGELOG

## 0.3.0 (unreleased)
- Check-ins: a check-in day runs from 05:00 to 05:00 (`checkins.day_starts`), so a night check-in after midnight, or
  one pushed past it, stays the evening's (it used to move to the morning); its journal goes to the evening's day.
- Check-ins by call: with the alarm set and past your bedtime (or the alarm just set by you), the night check-in
  doesn't ring; it moves to the wake-up call, with Call me now and Skip on Telegram (`checkins.asleep_defers`).
- Morning alarm: `alarm.keep_awake` keeps this computer awake from 12 hours before the alarm until it rings (Linux:
  lid closed too; macOS caffeinate; Windows), so the morning plan is drafted on time. Off until you turn it on.
- Stay awake on charger: `awake.lid` keeps a Linux laptop running with its lid closed while plugged in. Off until you
  turn it on. The hold now ends when Kurooto stops, even after a crash.
- Study tracker: idle time is detected on Wayland (GNOME, KDE, logind, and a watch for change on Hyprland and Sway),
  locked screens never count, `kurooto idle away|back` for hypridle and swayidle, and a Research category
  (`study.research_paths`, plus Research's projects).
- Linux: `kurooto autostart boot` starts Kurooto when the computer starts, before anyone logs in (lingering; keys kept
  in the owner-only settings file); `kurooto autostart login` goes back.
- Notes sync: a note changed here and elsewhere at once keeps both versions (the other device's in the note, this
  computer's as a "conflict" copy beside it) instead of this computer's winning; `notes_sync.on_conflict = stop`
  stops and asks you instead. A half-finished merge is left alone, and an existing `origin` (e.g. over SSH) is kept.

## PRIVACY
- Starting at boot (Linux, opt-in): Kurooto's keys are kept in its owner-only settings file instead of the keychain,
  since the keychain is locked until you log in. `kurooto autostart login` moves them back.
- The study tracker's idle check reads input interrupt counts (`/proc/interrupts`), the cursor position (Hyprland)
  and whether a screen locker runs; never what you type, and none of it is kept.
- Notes sync conflict copies are ordinary notes and go to your private repository like any other.
