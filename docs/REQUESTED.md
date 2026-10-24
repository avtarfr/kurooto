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
- ~~**A notes sorter**~~ (0.7.4: Features → Notes sorter; see Notes sorter in the user wiki): notes dropped in a scratch folder are moved by Kurooto into the right zettelkasten or
  Kurooto-style folders, with Undo, a limit a night and never overwriting; it needs a permission to move files in your notes,
  which will be a switch, off until you turn it on.
- **Chat sessions in the phone app**: each chat a session with its own memory and context; a new chat starts fresh.
- **Uninstall what a feature brought** (planned for 0.9.0): turning a feature off, or a hardware setting that stops
  using a model, offers to remove what it installed (Ollama models, programs like Node or GBrain) with its size, never
  without a tap and never what was there before Kurooto; an install receipt, `kurooto installed` and `kurooto remove`,
  and `kurooto uninstall` that follows the receipt. Today turning a feature off keeps everything it installed.
- ~~**Common features directly usable from the phone app** (and the rest of the dashboard plan:
  ~~check-in and quiz cards~~ (0.6.0: answered on the app's main screen with an answer box and their buttons, through
  the phone outbox while the laptop sleeps)): the dashboard's Today page (0.5.7) and Ctrl+K (0.5.8) are done;
  ~~the app's Today screen, local alarm and notification buttons~~ (0.6.0: Today on the app's first screen with
  Done / +1 on what's due, the wake-up alarm also set on the phone, Done and Snooze on reminder and deadline
  notifications).~~ (0.6.1: nothing left outside the Compose app: its bottom navigation between Today, Inbox and
  Phone is on its own branch; links in the app's chat open with a tap)
- ~~**A /help that lists everything** on Telegram and in the app's chat: every command and request it understands, in
  groups, with a link to the user wiki for the rest.~~ (0.6.1: the requests Kurooto understands by itself ("did I
  finish that thing?", "when did I last talk to ...", "sync everything", "I got a project under ...", "about the
  meeting with ...: ...") in their groups' "Just say"; a test that every command, every feature's request and each of
  those is in /help and understood; the app's chat gets the same index, its wiki links tappable)
- ~~**Dreaming** (0.5.9 has the morning message of the night's work and the loose ends; ~~consolidating memory and
  spotting contradictions across notes~~ (0.6.0: duplicate gists and how-to-help-me lines, and lines that disagree
  across how-to-help-me lines, notes, deadlines and GBrain's contradictions report, in the morning message with
  Keep A / Keep B / Both true; nothing changes until a tap); still to come: folding what it learned into your profile
  note): while you sleep and the laptop is idle, Kurooto goes over the day (chats, calls, AI requests, notes,
  your journal), consolidates what it learned into memory and your profile, spots contradictions and loose ends, and
  tells you in the morning what it tidied.~~ (0.6.1: "For your profile" in the morning message: lasting facts and
  how-to-help lines from your chats, calls, requests and journal, by rules with an optional second look
  (`dreaming.fold`, `fold_ai`), each with Keep / Not that; a Keep writes your words with where they came from into
  Kurooto's own block of your profile or your how-to-help-me note, with Undo; never health, money or other people)
- ~~**Dream RSI (self-improvement while dreaming)** (0.5.9 has the first part: each morning it replays your test cases
  and names any that went wrong since yesterday; 0.5.10 learns a phrasing you twice said again in other words, gated
  by the same replay): the same night pass also looks at what went wrong (failed or
  retried requests, your corrections, call lessons, answers that claimed what they didn't do), changes its own
  prompts, skills and quiet settings to fix it, and keeps a change only if replaying the past cases goes better;
  each change is listed with Undo. It improves the way it improves: the checks themselves are revised the same way.~~
  (0.6.0: the night pass also tunes effort, AI order and Start-by sizes by replay, one change a night with Undo; a
  skill that keeps going wrong gets a proposed fix gated by the AI's replay of those cases and your test cases, Apply
  or No, `dreaming.propose_prompts`; each change's outcome is kept and a kind you undid needs a clearer win) (0.7.0:
  that fix is a proposal with its diff, Apply / Change / Discard, Change reworking it in a scratch folder)
- ~~**Set up from what it sees, not from settings** (0.5.9 has projects with their supervisor, meetings, classes,
  commitments like the gym or a shift, a mail deadline's course and subjects' short names): one pass over chat and the journal (rules first, the AI only on a
  hit) creates projects with whoever they're with ("got a project under Prof X": the project, its supervisor, and
  meetings from then on), classes from "every Monday at 9 I have a lab", routines, a deadline's course, subject
  aliases; one line to say so, and `/inferred` to undo. Alarms, calls and anything outward still need a tap.~~
  (0.6.1: `infer.sweep`, once over the last 30 days when first on, then nightly on what's new: your chats and your
  journal and daily notes as they are in your notes folder; a line the rules can't read but that looks like one gets
  restated by the model on this computer (`infer.sweep_ai`) and kept only if it adds nothing the line doesn't say; one
  line with Undo all, `/inferred scan`)
- ~~**Preview the organic blobs in the phone app**, as in the dashboard.~~ (0.6.0: behind the main screen, in the
  palette or Material You's accents, still with "Remove animations" or battery saver) (0.7.0: a living background in
  the SYSTEMS view's language, a breathing cell and drifting nerves, tinted by the hour, a GPU shader on Android 13+)
- ~~**A better-looking phone app (Material design)**: Material 3 look and components (colour from the wallpaper on
  Android 12+, proper app bar, cards, bottom navigation), still one small APK that works on Android 6.~~ (0.6.0: the
  0.5.16 look carried through the chat, with a top app bar, and the widgets; bottom navigation waits for the Today
  screen) (0.7.0: the main screen in Jetpack Compose with Material 3 Expressive and a bottom navigation bar, Today,
  Inbox, Views (Systems and the Notes map) and Phone; still Android 6+, about 1.4 MB; the other screens stay framework
  views for now)
- ~~**Make the UI more intuitive**, and keep improving the setup wizard's elements. (0.6.0: settings with a few values are lists, JSON
  settings shown whole, "Saved" under the setting changed, features that are on first, the setup page's features step
  shows your picks first with the rest folded, Telegram's card links to its setup step; Claude Code is named "Claude
  Code" everywhere)~~ (0.6.1: walked as a new user in a browser; a new, empty notes folder no longer opens the layout
  editor (it's folded under "Change where each kind of note goes"), the daily message limit comes after the
  features, the hint beside Next has its own line on phones, the channel shown is the one picked, and the current
  step stays readable after a tap on phones)
- **Wiki-level documentation**: a user wiki and a developer wiki (for people and for AI agents), each a page on
  the site, covering every nook and cranny; one full read equips someone to use, develop and fix Kurooto (being
  written for 0.5.8).
- ~~**Use GBrain more**: weekly checkup and contradiction reports in chat, entity and timeline pages for courses,
  queries during calls.~~ (0.6.0: `gbrain.checkup_line`, one weekly line from its doctor; its contradictions report
  in Dreaming's morning section; `gbrain.course_pages`, each course page's key concepts and dated timeline; on calls
  search_notes searches by meaning and note_timeline reads a course's or a note's timeline)
- ~~**Make more add-ons public** (the generic ones: backups, desktop helpers, habits, handwriting).~~ (0.6.0: all four
  are ready in `addons/` with manifests, tests and READMEs, to add by link; 0.6.1: each published as its own
  repository and offered as an official add-on, pinned to its commit: Features → Official add-ons → Add,
  `/addons official`, `kurooto addons add <name>`)

## Done
- ~~**Set up from what it sees, not from settings**: one pass over chat and the journal creates projects with whoever
  they're with ("got a project under Prof X": the project, its supervisor, and meetings from then on), classes from
  "every Monday at 9 I have a lab", routines, a deadline's course, subject aliases; one line to say so, and
  `/inferred` to undo. Alarms, calls and anything outward still need a tap.~~ (0.5.9 to 0.5.20: projects, meetings,
  classes, commitments, recurring quizzes, short names; a deadline's course from its title. 0.6.0: a thesis or
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
