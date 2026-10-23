# Requested

Bugs and features people have asked for, in one list. Done ones are struck through with the version that has them;
the rest are open. (Ideas nobody has asked for yet are in [ROADMAP.md](ROADMAP.md).)

To ask for something: open an issue on GitHub, or tell your own Kurooto on Telegram: "add to the requested list: …".

## Open
## Always
Standing plans, never struck through.
- **The site keeps up with every release**: the landing page, changelog, both wikis, the feature list and screenshots
  are updated with each version, so what the site says is what Kurooto does.
- **Kurooto knows itself**: every feature, command and setting is in `/help` and the wikis the day it ships.

## Open
- **Common features directly usable from the phone app** (and the rest of the dashboard plan:
  check-in and quiz cards): the dashboard's Today page (0.5.7) and Ctrl+K (0.5.8) are done; the app's Today screen,
  local alarm and notification buttons are planned for 0.6.0.
- **A /help that lists everything** on Telegram and in the app's chat: every command and request it understands, in
  groups, with a link to the user wiki for the rest.
- **Dreaming** (0.5.9 has the morning message of the night's work and the loose ends; still to come: consolidating
  memory and spotting contradictions across notes): while you sleep and the laptop is idle, Kurooto goes over the day (chats, calls, AI requests, notes,
  your journal), consolidates what it learned into memory and your profile, spots contradictions and loose ends, and
  tells you in the morning what it tidied.
- **Dream RSI (self-improvement while dreaming)** (0.5.9 has the first part: each morning it replays your test cases
  and names any that went wrong since yesterday; 0.5.10 learns a phrasing you twice said again in other words, gated
  by the same replay): the same night pass also looks at what went wrong (failed or
  retried requests, your corrections, call lessons, answers that claimed what they didn't do), changes its own
  prompts, skills and quiet settings to fix it, and keeps a change only if replaying the past cases goes better;
  each change is listed with Undo. It improves the way it improves: the checks themselves are revised the same way.
- **Preview the organic blobs in the phone app**, as in the dashboard.
- **A better-looking phone app (Material design)**: Material 3 look and components (colour from the wallpaper on
  Android 12+, proper app bar, cards, bottom navigation), still one small APK that works on Android 6.
- **Make the UI more intuitive**, and keep improving the setup wizard's elements.
- **Wiki-level documentation**: a user wiki and a developer wiki (for people and for AI agents), each a page on
  the site, covering every nook and cranny; one full read equips someone to use, develop and fix Kurooto (being
  written for 0.5.8).
- **Use GBrain more**: weekly checkup and contradiction reports in chat, entity and timeline pages for courses,
  queries during calls.
- **Make more add-ons public** (the generic ones: backups, desktop helpers, habits, handwriting). (0.5.22: all four
  are ready in `addons/` with manifests, tests and READMEs, to add by link; left: publishing each as its own
  repository)

## Done
- ~~**Set up from what it sees, not from settings**: one pass over chat and the journal creates projects with whoever
  they're with ("got a project under Prof X": the project, its supervisor, and meetings from then on), classes from
  "every Monday at 9 I have a lab", routines, a deadline's course, subject aliases; one line to say so, and
  `/inferred` to undo. Alarms, calls and anything outward still need a tap.~~ (0.5.9 to 0.5.20: projects, meetings,
  classes, commitments, recurring quizzes, short names; a deadline's course from its title. 0.5.22: a thesis or
  dissertation, "my supervisor is Dr X", the person before "project", "on Mondays", "I've got", "I go running every
  morning"; a call with someone is never a routine. Rules alone are enough: no AI pass, nothing leaves the computer)
- ~~Local model on the graphics card without spilling onto the processor~~ (0.5.9: spilled models are unloaded and
  reload fully on the card; one too big is told once; `/models` shows the share)
- ~~Allow safe scripts for agents: named scripts, not a bare `python3`~~ (0.5.8: `agents.scripts`, full paths;
  shells and interpreters refused)
- ~~Check that every button works after a restart~~ (0.5.8: every button's prefix has a handler, checked by a test;
  one from a feature that's off says so)
- ~~Mail digest formatting: shorter, grouped by what needs you~~ (0.5.8: Needs you, Dates, Courses, Worth knowing; about 15 lines)
- ~~Mail about exams is read at once and turned into a schedule~~ (0.5.8: each exam of your subjects becomes a deadline with its time and room; details in the course note)
- ~~A legend for the dashboard's organic view~~ (0.5.8: press ? on the board)
- ~~Handwritten notes linked like any note~~ (0.5.8): a title from what's written, the subject and the lecture it
  was written in, links to the course page and the concepts on it, and its doubts kept findable (`/handwritten link`
  for older ones).
- ~~Learns from its own work, like Hermes Agent: after a request that took many steps, how it did it is saved as a
  skill; a skill improves when you correct its result; it searches its memory of past requests and calls; it suggests
  what's worth remembering~~ (0.5.8, the optional "Learns from its own work": `/history`, `/learned`; the design only,
  none of Hermes Agent's code)
- ~~PDF, Word and PowerPoint to Markdown with MarkItDown~~ (dropped: Books already reads PDFs page by page, with
  OCR for scans, and Classroom keeps text of Office files; the slow part of reading is the AI, not the conversion)
- ~~Drop attendance tracking entirely~~ (0.5.8; skipping a class still works). Exam season becomes an add-on, off by
  default (0.5.8).
- ~~After every call, a stronger model reads the transcript, does what slipped through and improves later calls~~
  (0.5.8, `/lessons`)
- ~~Study packs for one topic, with class material ahead of books~~ (0.5.8, `/studypack pota quiz on thermodynamics`)
- ~~Chat context polluted by other requests' answers~~ (0.5.8)
- ~~A Today page in the dashboard: alarm, due, reminders, check-ins, questions and journal with buttons, and one box for anything~~ (0.5.7)
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
