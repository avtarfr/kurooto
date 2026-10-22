# Requested

Bugs and features people have asked for, in one list. Done ones are struck through with the version that has them;
the rest are open. (Ideas nobody has asked for yet are in [ROADMAP.md](ROADMAP.md).)

To ask for something: open an issue on GitHub, or tell your own Kurooto on Telegram: "add to the requested list: …".

## Open
- **Common features directly usable from the dashboard and the phone app**, not only through chat: write a journal
  entry, set or skip an alarm, add a reminder or deadline, tick what's done, start a check-in, ask something. Being
  ideated now (dashboard and Android app together).
- **Mail about exams is read at once and turned into a schedule** (dates, rooms, what to prepare), not only digested.
- **PDF, Word and PowerPoint to Markdown** with Microsoft's MarkItDown for books and Classroom files (needs a pip
  install, so it asks first).
- **Mail digest formatting**: shorter, grouped by what needs you.
- **Preview the organic blobs in the phone app**, as in the dashboard.
- **A better-looking phone app (Material design)**: Material 3 look and components (colour from the wallpaper on
  Android 12+, proper app bar, cards, bottom navigation), still one small APK that works on Android 6.
- **A legend for the dashboard's organic view**: what each blob, line, pulse and ring means, on the page itself (a
  hover card already explains a cell; a "?" key should explain the whole picture).
- **Make the UI more intuitive**, and keep improving the setup wizard's elements.
- **Wiki-level documentation**: one full read equips someone to develop Kurooto and fix bugs without an agent
  (the manual covers use; the developer side is thin).
- **Use GBrain more**: weekly checkup and contradiction reports in chat, entity and timeline pages for courses,
  queries during calls.
- **Local model on the graphics card without spilling onto the processor**: one model at a time and a size that fits.
- **Make more add-ons public** (the generic ones: backups, desktop helpers, habits, handwriting).
- **Allow safe scripts for agents**: a way to allow named scripts (not a bare `python3`, which is a shell).
- **Check that every button works after a restart** (buttons on older messages once did nothing).

## Done
- ~~A free Gemini key tries the next model of the family when one's daily limit is used up~~ (0.5.7)
- ~~Goodnight sets the wake-up alarm (it already did: /goodnight)~~ (0.5.4)
- ~~Renaming the assistant renames the Telegram bot and says so~~ (0.5.7)
- ~~A guide for AI agents to everything Kurooto, generated from the code (agent-guide.md in the reserve, and the settings guide)~~ (0.5.7)
- ~~Tools installed in ~/.local/bin are found after a reboot ("restic couldn't start")~~ (0.5.7)
- ~~The phone-app QR code always serves the latest app~~ (0.5.7)
- ~~State as Markdown an AI can open: alarms, deadlines, calendar, settings, add-ons and a guide to what it may do~~ (0.5.7)
- ~~Space keeper: old backups and leftovers cleaned off, so Kurooto never takes too much space (`/space`)~~ (0.5.7)
- ~~Every concept of a book integrated with the others in your notes, with good Obsidian links: reasons, relations, no vague links~~ (0.5.6)
- ~~Weaker model for bulk, stronger second look; agy and Claude Code together~~ (0.5.6)
- ~~Messages when Kurooto goes offline and comes back online~~ (0.3.0)
- ~~The setup wizard fills the whole window on desktops~~ (0.3.0)
- ~~Bring every feature of the earlier private version into the public app~~ (0.5.0)
- ~~A terminal like the author's, on every system: your AI's program, a shell, Kurooto chat, the log, a system monitor~~
  (0.4.0, 0.5.0)
- ~~Going offline also on network drops~~ (0.3.0)
- ~~A call fallback using the phone's own speech when Gemini Live is down~~ (0.5.1)
- ~~Links open in your default browser~~ (0.5.1)
- ~~Show and hide panes, search in Settings and Features, hide features~~ (0.5.1)
- ~~Metered-connection toggle~~ (0.5.1)
- ~~An AI request never gets stuck: cancel, watchdog, one at a time~~ (0.5.1)
- ~~Requests to agy no longer fall back to the free Gemini key, which ran out~~ (0.5.1)
- ~~"Call me now" and "due today" understood (weekday bug)~~ (0.5.1)
- ~~Phone rings through the laptop's own push, not only the Cloudflare call line~~ (0.5.1)
- ~~Ringtone picker lists ringtones; calls heads-up with the system ringtone; no crash on some phones~~ (0.5.4)
- ~~`kurooto sync` shows its status~~ (0.5.3)
- ~~Revision packs as PDF on every computer (the computer's own LaTeX when Tectonic isn't there); the Install button~~
  (0.5.5)
- ~~"Send me the files" sends the files, not their paths; several files as one zip~~ (0.5.5)
- ~~A study pack for another AI: notes, course files and a prompt in one zip (`/studypack`)~~ (0.5.5)
- ~~"Do I have any alarms?" answered at once~~ (0.5.5)
- ~~Classroom sync finds everything instead of needing repeated syncs~~ (0.5.5)
- ~~Home and research hubs, so notes aren't separate islands~~ (0.5.5)
- ~~A settings guide~~ (0.5.5, `docs/SETTINGS_GUIDE.md`)
- ~~Books in any folder depth, read on battery when forced, indexed in their own GBrain source~~ (0.5.5)
- ~~Claude Code as a full brain with the same reach as agy; `kurooto open` and the terminal use your own AI program~~
  (0.5.6)
- ~~Drop Codex~~ (0.5.6)
