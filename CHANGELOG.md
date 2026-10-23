# Changelog

## 0.5.8 (unreleased)

- **A calmer board**: the corner panels of SYSTEMS (events, your AI, today, due) and the NOTES legend and recent list
  are folded to their first line (with how much more there is); one opens while the pointer is over it, and `L` opens
  or folds them all (remembered in this browser).
- **Ctrl+K from anywhere on the board**: one line for `ask`, `journal`, `note`, `remind 18:30 call mum`,
  `due essay fri 17:00`, `alarm 7:30` (or `skip`, `off`), `find` a note and `open` a page, plus the Today box's `j`,
  `.` and `!`. A bare word is completed, the result shows under the line, and an AI's answer arrives there too.

- **Study packs: the prompt comes on its own**, as a message next to the zip, ready to copy (it's still in the zip).
- **Anything over Telegram's 50 MB comes as a Google Drive link** (with Drive upload on): study packs leave nothing
  out, several files sent at once aren't refused, and those uploads are deleted from your Drive after
  `drive_upload.temp_days` (7) unless you move them out of the Kurooto folder.
- **Attendance and standing is gone**, and class packs no longer carry attendance rules: `/skip` still works (without
  the warning), and class packs made earlier still import.

- **The concept graph's own schedule works again**: its nightly start, 3-hourly retry, daily garden and morning
  summary (and the Space keeper's weekly clean, and expiring temporary Drive uploads) failed on every run; only
  `/graph now` and carrying on after a batch worked. A test now checks every scheduled job.
- **`/help` knows all of Kurooto**: every command and plain-word request of the features you have on, grouped by
  feature, the features that are off, and a link to the user wiki; `/help <word>` finds a command or feature, on or off.
- **Two wikis**: a user wiki (every feature, command, setting, message and fix, in plain words) and a developer wiki
  for people and AI agents (architecture, every subsystem, how to add a feature, tests, releases), in `docs/wiki/`.
- **Exam season is an add-on**: listed apart under Features, off until you turn it on, and in no preset ("Everything"
  leaves it out). If it was on, it stays on.
- **Study packs pick a book's pages like a student would**: first the readings the class itself cites ("Reference:
  Salby Chapter 2, Wallace and Hobbs Chapter 3 Section 3.2"), then whole chapters and sections whose titles name the
  topic (from the book's bookmarks), then other pages about it; all the books together keep to 250 pages, what another
  AI can hold. Lecture files Books hasn't read count too (Classroom's text of them), and a file that's both in Classroom and
  in your books folder goes in once.
- **Edit what study packs ask for**: `/studypack prompt` makes the prompt a note of yours (`kurooto/study-pack-prompt.md`)
  with `{name}`, `{topics}` and `{aim}` filled in; every pack uses it; `/studypack prompt reset` puts Kurooto's back.
- **Study packs never hold a whole book**: it would flood the other AI's context; name a topic to get a book's pages.
- **Study packs for one topic, class first**: `/studypack pota quiz on thermodynamics` (or the AI's study_pack tool with
  `topics`) takes only what's about it: class files that mention it, the pages of each book that do (as text, with the
  page numbers), and the notes about it, including what the notes brain finds. Class material and books are told apart
  by length (class notes are short; over 80 pages, or "Ch 8", "edition", a download site in the title, is a book),
  since professors post books on Classroom too, and class material always comes first: in the zip (`class/`, then
  `books/`, then `notes/`) and in the prompt, which says to follow the class where a book disagrees. Packs now also
  hold what Books has read for the subject.
- **Calls look back**: after every call a stronger AI request (`calls.review_effort`, high) reads the transcript and the
  tools the call used, does what slipped through (a reminder it misheard, a note it promised), lists what needs you,
  and keeps up to `calls.lessons_max` (12) lessons that every later call is told. `/lessons` lists them;
  `/lessons forget 2` removes one. One message only when it fixed or learned something; `calls.review` off stops it.
- **Chat remembers only the chat**: a digest's or research run's answer no longer turns up as "you said" in the
  context of your next message.

## 0.5.7 (2026-10-23)

- **Today page in the dashboard (Alt+T)**: one box for anything (plain words to Kurooto, `j` journal, `.` note, `!` a
  reminder), and the day with buttons: set or skip the alarm, tick or move what's due, snooze or cancel reminders,
  move or skip check-ins, answer open questions, write the journal. Every button is the same action as the command
  and the AI's tool (`/api/act`).

- **Space keeper**: cleans off Kurooto's own old backups (past a total size or age, never the newest), downloads and made
  zips, big logs, old finished AI requests and the concept graph's old before-copies, weekly and on request (`/space`,
  `kurooto space [--clean]`). Only Kurooto's own leftovers are touched.
- **The reserve**: Markdown copies of alarms, deadlines, the calendar, settings (never secrets), add-ons and one guide to
  what an AI program may do, in `<state>/reserve/`, so a request can just open a file (`kurooto reserve`). The AI is told
  to read them instead of running commands.
- **The phone app's QR page always offers the newest app** (it read the copy it was set up with, which only got older).
- **Tools you installed yourself are found at boot** (`~/.local/bin`, `~/.cargo/bin`, Homebrew are put on PATH when
  the service starts with a short one): "restic couldn't start: No such file" after a reboot.
- **A free Gemini key goes further**: when one model's daily free limit is used up, the next of the Flash family
  answers (the answer says which).
- **Renaming your assistant** renames the Telegram bot too and says so once.
- **Concept graph fixes**: a concept dropped after a second look is no longer linked from the notes of the same
  batch (it left broken links); the daily pass takes out Kurooto's own links to notes that don't exist; a run paused
  by a signed-out or limited AI tries again in 20 minutes instead of 3 hours.
- **Concept graph**: cost and request counts (`/graph`), effort goes up for books that need many second looks.

- **GPU reranker for the concept graph**: on a computer with a helper model (an 8 GB card, an Apple Silicon Mac, a
  4 GB card's small helper), the local model judges which of your notes belong with a new concept, from its own
  yes/no probabilities, instead of relying on words and vectors alone. No extra download, no AI requests; where there
  is no helper model nothing changes (`integrate.rerank`, `integrate.rerank_model`).
- **Go past what your hardware suggests, and have Kurooto install it** (`hardware.force_profile`,
  `hardware.extra_models`, `hardware.extra_prereqs`; `kurooto hardware --profile big-gpu-12 --add gemma4:12b
  --install`; the same on the setup page's computer step): Kurooto says plainly what you're going past ("this model is
  bigger than your graphics memory: part of it runs on the processor"), never refuses, checks the disk, then installs
  Ollama, the models and the programs you asked for.

## 0.5.6 (2026-10-23)

- **Concept graph** (Features → Concept graph): when a book has been read, its concepts are woven into your notes: new
  concept notes, links with the relation and a specific reason, "Seen in" lists with pages, and a list of what each
  stretch of a book introduces. Checks that don't trust the AI's own opinion (the quote must be in the pages, no vague
  reasons, no links to nothing, no second note for a name you have) decide what's written; doubtful items get a second
  look by the other AI program or are dropped; nothing is queued for you. Your own text is never changed, one git commit
  per batch. agy and Claude Code can split the work and run side by side (`integrate.roles`). Daily second pass over
  what the reading touched. `/graph` for the state and quality numbers.
- **Book sections found properly**: a margin note like "Section 9.1" is no longer taken for a chapter heading (it made
  every chapter a list of other chapters' sections); batches follow numbered headings and running headers.
- **Less vision work when reading books**: a maths page is read again as a picture only when its text layer broke the
  equations into pieces (`books.latex`).

- **Claude Code as a full brain**: a request run by Claude Code gets the same reach as one run by agy: Kurooto's tools
  and your own GBrain's, writing in your notes, course files and add-ons' skills, reading your Documents and
  Downloads, web pages, and harmless commands, all given for that request only (nothing saved in Claude Code's own
  settings, and none of its hooks, project files or history used). Anything else is refused, so a request can't hang
  on a prompt; a refusal says what was refused. Usage limits say when they reset.
- **`kurooto export-skills on --to claude`**: your skills as /commands in Claude Code (only when you ask).
- **Nothing is agy-only**: agent programs share one interface, so the job queue, the setup test, the hand-over to an
  agent program that has worked here, and the terminal's AI tab behave the same for agy and Claude Code.
- **Codex is gone**: it was never fully supported. A setting that names it is cleared, and the next request says to
  choose another AI in Settings → AI.
- **docs/REQUESTED.md**: what people asked for, open and struck through when done.

## 0.5.5 (2026-10-23)

- **PDFs without Tectonic**: a revision pack is built with the computer's own LaTeX (latexmk or pdflatex) when Tectonic
  isn't installed; the LaTeX file is only sent when there's no engine at all.
- **Files, not paths**: `send_files` sends several files (more than two as one zip), `study_pack` sends a subject's notes
  and course files with a prompt for another AI, and `/studypack <subject> <what it's for>` does the same from chat.
  The AI is told to send files, never answer with `file://` paths.
- **Alarm questions** ("do I have any alarms?", "when is my alarm?") are answered at once from local state, with a
  `get_alarm` tool and an `alarm.md` copy for programs that read files.
- **Classroom**: the backfill window always applies and counts edits; posts it left out aren't marked as seen, so a
  longer window finds them (no more syncing again and again).
- **Hubs**: a home note and a research hub exist from the start, list your courses, and course pages link back, so notes
  aren't separate islands; kept current after Classroom filing and book reading.
- **Books**: found in folders at any depth (`.pdf` in any case), `/books read force` on battery, `books.after_read` runs
  your own command after each book, `books.brain_source` indexes chunks in a GBrain source you name.
- **Dashboard notes graph**: neighborhoods come from your own folders; the graph has a Recent toggle.
- **docs/SETTINGS_GUIDE.md**: every setting, written from the code and checked by CI.

## 0.5.4 (2026-10-21)

- **Android ringtone & heads-up banner fix**: Replaced old `calls` channel with `calls_v2` using system default ringtone and `PRIORITY_MAX` heads-up notification priority; guarded against OEM `SecurityException` on ringtone queries.
- **Android update banner**: Shortened update check throttle to 2 minutes on resume and automatically dismiss the update banner once updated.
- **Sync status API fix**: Added POST handler for `/api/sync/status` and state-file fallback in CLI so `kurooto sync` polls and waits smoothly without false aborts.
- **Cross-platform time zone canonicalization**: Fixed casing lookup in `canonical()` so case-insensitive file systems (macOS/Windows) resolve zone aliases properly.
- **Scrapped legacy `oldphone` bridge**: Completely decommissioned and scrubbed legacy `oldphone` module.

## 0.5.2 (2026-10-21)

- **Setup wizard profile restore fix**: Restoring an existing profile archive in setup now seeds and retains restored feature choices instead of wiping selection.
- **Call line & wake intent disambiguation**: Ordered `call_when` ("call me, I didn't wake up at 12") before general `call_now` pattern to prevent misinterpreting past statements as immediate ringing requests.
- **Call invocation resilience**: Fixed `why` and `due` keyword compatibility in `calls.ring()` call-chain when wrapped by legacy bridges.
- **CI & unit test fixes**: Updated brain recommendation assertions to match `agy` first recommendation, aligned call line test isolation with per-test workspace settings, and fixed ruff formatting checks in CI workflows.

## 0.5.1 (2026-10-20)

- **Gemini free-tier key rollover disabled**: Requests using CLI brains (`agy`) no longer roll over to the free Gemini API key on error, preventing unintended rate-limit exhaustion.
- **AGY recommended brain**: Recommended in settings/setup over raw Gemini API keys; includes warning on free-tier 20 req/day limits.
- **Direct laptop ntfy ringing**: Calls and wake-ups publish sealed encrypted payloads directly to ntfy from the laptop as well, ensuring ringing works reliably even when Cloudflare Worker egress blocks ntfy.sh.
- **Telegram multi-turn memory**: Chat maintains recent turns within 2 hours; supports `/new` and `/clear` to start fresh conversations.
- **Classroom to Git migration & unhardcoded paths**: Classroom files organized cleanly under Vault; `send_file` tool supports classroom folder dynamically without hardcoding paths.
- **Study pack generation**: `/studypack <subject>` bundles materials into a zip for external LLMs.
- **Calls when Google's live voice is down** (Gemini Live answering "503 UNAVAILABLE" made calls fail to start, or hang up)
- Live again first: a start Google refuses for now (503, 429, UNAVAILABLE) is tried after about 1 s and 3 s, each time
  with the next model in `calls.live_models` (new, after `calls.live_model`; by default
  `gemini-3.1-flash-live-preview` and `gemini-2.5-flash-native-audio-latest`). Those models get a session any Live
  model takes (tools that wait, a prebuilt voice or Google's default; `calls.voice_by_model` picks one per model).
  "Reconnecting…" shows meanwhile. A drop in the middle of a call is tried again once.
- Then turn by turn with the phone's own speech: the Android app uses Android's speech recognizer and voice, the call
  page the browser's (Chrome). Same call: its instructions, the check-in's or wake-up's script and the same tools.
  Each turn is answered by your computer (your Gemini key, or the model on your computer with `calls.turn_brain` =
  `local`; never an agent program), or by Gemini on your call line while the computer is off or slow.
- Then text on Telegram, when the phone has no speech recognition or microphone: the same call as messages (a
  check-in stays a check-in); what you type is part of it until **End the call** or 20 quiet minutes. With the
  computer off, it starts when the computer is back.
- Whichever way the call went, its transcript feeds your journal and study logs as before.
- `kurooto doctor`: "Phone calls: voice service" counts Live's failures this week, the retries that worked and the
  calls that went on another way (also in the call status the dashboard reads), and names a model in your list that
  Google says no longer exists.

**Calls by your phone's own speech, by choice** (`calls.voice_mode`: `auto`, the default, `live` or `phone`)
- `phone`: calls go turn by turn with your phone's speech every time, not Live; on Android 13+ with your language
  downloaded, speech is recognised on the phone and the audio stays there. `calls.voice_by_kind` sets it per kind of
  call (e.g. the alarm on `phone`, the evening debrief on `live`). The screen stays on during such a call (phones stop
  listening when it goes off). The manual compares the two (feel, latency, languages, privacy, outages).
- The Android app needs this version for turn by turn; older apps go to Telegram instead.

**Calm by default** (on; `notify.calm.on` = `false` restores the old behaviour exactly)
- Every message that comes by itself records why: the feature, what for, the setting that controls it and what it was
  about. On Telegram it has **Why?** (answered from those records; "No reason recorded" when a script or add-on
  didn't say, never a guess) and **Less of this**: Stop / Fewer / Another time, each changing one setting (the
  feature's own where it has one), with Undo. The phone app, the desktop and calls get the plain message.
- A daily limit: 6 messages and 1 call that come by themselves (`notify.calm.messages`, `notify.calm.calls`). The rest
  waits for one evening bundle at 20:00 (`notify.calm.evening_at`), numbered, with each item's buttons; a call past
  the limit becomes a message (check-ins) or a Call now link in the bundle.
- Never held and never stoppable: the alarm, approvals, your own reminders, a deadline under 12 hours away, anything
  urgent. Answers to what you asked aren't counted.
- Exam season gains a part, on by default: during the period only deadlines, quizzes and the alarm come by day; the
  rest waits for the evening.
- Once a month: "you answered 1 of 19 after-class questions: turn them off?" (Apply / No), only for questions.
- `/calm` (today's count, what's waiting and turned down; `/calm 8`, `/calm calls 2`, `/calm evening 21:00`,
  `/calm off`) and `/why` (the last one). For add-ons: `app.notify(..., why=, setting=, about=)`, `app.ask.ask(...,
  why=)`, `calls.ring/place/schedule(..., why=)` and `jobs.submit(..., why=)` carry the reason.
- **"I'm awake"** (or "I just woke up", "I'm up", even with "call me if you need to …") rings the morning call now,
  planned from the current time, with the morning page opened here. With the Morning alarm on, it's a normal call,
  not the alarm: no snooze and no repeat rings, and an alarm still set for later is mentioned.
- **A time about the past, or about something that didn't happen** ("since I didn't wake up at 12", "as I said I
  would", "was supposed to at 9") is never used as the time of a call, reminder or check-in. Before, "… call me if you
  need to, I didn't wake up at 12" could book a call for 12:00 the next day. If that's the only time in a call or
  reminder request, Kurooto asks when instead of booking.
- "call me at 5" means five o'clock (17:00 when said in the afternoon), not five minutes from now.
- **"cancel that call" / "cancel the 12:00 call"** cancels the booked call it means, or lists the booked calls with a
  Cancel button and their keys. A bare "call" no longer counts as the evening check-in, so "cancel that call" can't
  skip it.
- **`kurooto ask`:** "!command" runs a shell command right there, after echoing it. A line typed as a shell command
  without the "!" ("call-me --cancel …", "systemctl …", "kurooto status") gets "that's a shell command: run it in a
  shell tab, or prefix it with !" and is never sent to Kurooto or the AI.
- Tests no longer see or change a Kurooto installed on the computer that runs them: every test gets a pretend home
  (HOME, the XDG folders, APPDATA, LOCALAPPDATA, KUROOTO_HOME) and no keychain, `loginctl`, `systemctl`, `launchctl`
  and `kurooto` are refusing stand-ins, the running dashboard's port is out of reach, and a test that writes to or
  deletes anything in the real install, its systemd unit, autostart or app-menu entries or ~/.gemini fails.
  Autostart and the app-menu entries made for a given home now take every path from it, the app folder included.
- Time zones are compared by what they mean, not by name: an old name and today's (`Europe/Kiev` and
  `Europe/Kyiv`) are one zone for `kurooto doctor` and your call line, and a zone is saved under today's name (the
  setup page's picker offers those; one saved under an old name is renamed at start).
- Research: a project folder that isn't a git repository yet is a project with no commits to follow; doctor says so
  as a note ("isn't a git repository (no commits to follow): `git init` it, or /repos remove it") instead of
  "repository folder missing", and the Research tab can keep or remove it again.
- Reminders: "remind me at 6 pm: …" no longer keeps the colon ("at 18:00: : …"); a ":", "-", "to", "that" or "about"
  left at the start of the text goes, and `/remind 21:30 - …` too.
- Google: a permission Google grants under its older name (Classroom coursework as
  `classroom.student-submissions.me.readonly`) counts as the one asked for. Every sign-in said "Some boxes weren't
  ticked: your Classroom coursework", and Classroom → notes never turned on.
- Google: which account is which. Every account (main too) is asked for its address; `/google` and the Google card
  list each account with it, the sign-in page names the account it saved ("Signed in with Google as … (main)"), and a
  feature's account box shows the address of the account in use.
- Installers: `KUROOTO_CHANNEL=beta` installs from the beta channel, and the install keeps following it
  (`updates.channel` is saved in its settings).
**The dense dashboard makes room**
- Any pane fills the board: click its name (⤢) or double-click its border; Esc or the name again brings the others
  back.
- A **panes** menu in the board's top-right corner hides STATUS, SYSTEMS, NOTES or TERMINAL (one always stays) and
  the others take the room. It's the setting `look.panes`, so every browser shows the same.
- The pages (Features, Settings, Phone, Research, You, Schedule, Jobs, Activity) open over the whole board instead of
  the short terminal pane. Alt and the underlined letter opens one (Alt+F features, Alt+S settings…), Esc goes back;
  a terminal keeps its own Alt keys.
- Features and Settings have a search box (`/` or Ctrl+F, Esc empties it): it filters as you type, marks the words
  it found and counts what's left; a feature is found by its settings too.
- A feature that's off can be hidden from the Features page (`look.hidden_features`); Show hidden (N) at the bottom
  brings it back, and a search still finds it. Only the page changes.
- Links to other sites in Kurooto's pages (Google sign-in, token pages, guides) open in your default browser, also
  when the dashboard runs in another browser's app window. `look.links_in = here` keeps them in the page's browser.
**A stuck AI request no longer holds up the queue**
- Fixed: an automatic revision pack stayed "running" for 20+ minutes and everything you sent after it waited. agy
  stopped (its tool permission was still being asked), your Gemini key took over, and its next request never came
  back when the network dropped behind a login page: one request could wait the job's whole time (30 min for high
  effort), and a connection cut mid-answer could stop the queue for good. A request to a service on the internet now
  waits at most 3/5/10 minutes (low/medium/high), any failure there is a plain failure, and a mistake inside a job
  fails that job instead of stopping the queue. Which AI is working on a request shows while it runs.
- Two lanes: your own requests and background work (automatic packs, routines, the morning plan, digests) run side
  by side, so your request never waits behind background work.
- A watchdog ends a request with no AI at work and no program running for `jobs.stuck_min` minutes (10), or one still
  going past its time limit plus a grace, as failed, with a plain message.
- Cancel: `/jobs` shows what's running and waiting with Cancel buttons (and `/jobs cancel <id|all>`); `kurooto jobs`
  and `kurooto jobs --cancel ID|all`; a Cancel button on the dashboard's AI jobs page. Cancelling a running request
  stops its program and everything it started.

**Stopping is quick and leaves nothing behind**
- Fixed: restarting Kurooto could take 90 s because a program it had started ignored the stop. When Kurooto stops,
  every program it started (terminals and what runs in them, an AI request's agent program and its helpers, your
  GBrain's server, Ollama if Kurooto started it, add-ons' programs) is asked to stop and killed after 5 s if it's
  still there; programs that left a terminal's or agent program's session behind are found too. Programs it opened
  for you (an editor, a browser, a terminal window) stay open. Running AI requests stop where they are and run again
  at the next start.
- The launcher passes a stop on to Kurooto and waits for it. The systemd unit gets `TimeoutStopSec=20` and
  `KillMode=mixed` (an existing unit gets them at the next starts, once the new launcher runs), the macOS LaunchAgent
  `ExitTimeOut` 20.

**Fixes**
- `kurooto doctor` and the health checks said "your call line doesn't answer" while calls rang: Cloudflare turns
  Python's default user agent away ("error code: 1010"), so the check now says it's Kurooto.
- Practice quizzes: a quiz file without all its parts (brought over by an import) no longer breaks quizzes and the
  quiz part of a call's brief; one part of a call's brief failing never stops the rest.

**Google turns on when you sign in**
- Signing in on the Google card turns Google on (and the Google features you set up that Google has OK'd), also when
  an import left it off.

**Commands of features that are off**
- A /command of a feature that's off answers "Google is off: Features → Google → Turn on" (a skill while Skills is off
  the same) instead of going to the AI. `/jobs`, `/status` and `/help` answer whichever features are on.

## 0.5.0 (2026-10-20)
Includes everything planned for 0.4.0 (below), which wasn't released on its own.


**Kurooto keeps itself working** (on by default; `health.on`)
- Every feature that's on has one health check: how often it should work (Classroom within 26 h, Calendar 12, Notes
  sync and the Notes brain 24, Backups and Profile sync 72) and/or a read-only probe (a Google sign-in, GitHub notes
  token or Cloudflare login that ended or ends soon, a Telegram bot that stopped answering, the link to your call line,
  tonight's alarm, messages stuck in a queue). Only awake, unpaused hours count: sleep, shutdowns, network outages and
  pauses (and battery saver, for work that waits for the charger) are taken out first, so a shut lid is never a
  failed sync.
- A daily pass (`health.when`, 21:00) that's silent unless something is wrong. Tonight's alarm might not ring: a
  message now ("set your phone's own alarm too"). A problem that could make you miss a deadline or exam in the next
  48 h: one message now with a Fix button. Anything else: a "Needs a look" part in the weekly summary (or one Sunday
  message with the summary off). Each problem is told once.
- Five fixes, only of Kurooto's own state: sync now, put timers back, reconnect, set the alarm again (the daily alarm
  is otherwise planned at midnight, which a sleeping laptop misses), send stuck messages. The safe ones run before
  you're told (`health.auto_fix`); after a Fix tap you hear whether it worked.
- `/health` on Telegram, a "needs a look" badge and Fix buttons on the dashboard (Features), `working: ...` lines in
  `kurooto doctor`, and `kurooto doctor --fix <id>`. Add-ons can give their own check (`health_check()`).
- Going offline and coming back now keeps the offline periods of the last 15 days (for the checks above). Google's
  sign-in keeps when Google says it ends.
**Free-tier reserve** (on; nothing waits until a limit is known)
- Kurooto counts AI requests per free limit (each model of your Gemini key, agy, another service) and learns each
  limit and when it resets from Google's "limit reached" answers, instead of a table that goes stale. agy's count comes
  from its own logs, so the runs you type count too.
- Past 70% of a day's known limit (`quota.background_pct`), background work waits in the queue and runs after the
  reset: the Classroom digest, the nightly look back, skill changes, research digests, book and handwritten pages read
  by Gemini. The "how hard is this" question moves to the model on this computer, or the rules. Calls, voice notes,
  the morning plan and your own requests keep the rest; nothing is dropped. `quota.local` = `background` moves
  background work to the model on this computer instead of waiting.
- A used-up limit is one plain line: "Google's free limit for today is used up, resets at 12:30; your calls and alarm
  still work." Your own requests try it last, after the fallback brain.
- `/usage`, `kurooto usage` and the usage API show today's limits, what's used of them, and the requests waiting.
- A daily limit no longer waits a minute and asks again before the fallback; handwritten files that hit a limit are
  tried again later instead of being written off.
**Reminders with the lid shut** (new; off until you turn it on; needs Phone calls and the Android app)
- When your computer is asleep or off, your Android phone still gets your reminders at their time, and a morning
  line with the day's first class and what's due (with that morning's alarm, else at 07:30). Your call line holds the
  next day's items sealed for each phone with a key only that phone has: it keeps times and ids, never the text, and
  your Telegram bot's token stays on your computer.
- Whichever side is awake at an item's time says it, once: your computer claims it from the call line and says it on
  Telegram as usual, or the call line sends it to the phone and your computer, awake again, doesn't repeat it. A send
  the call line couldn't make comes back to your computer.
- The batch goes when your reminders change, every 10 minutes, and as the computer goes to sleep (Linux and Windows).
- The Android app makes its own key the first time it runs and gives your call line the public half; a sealed
  reminder shows as a normal notification. Your call line updates itself overnight (or Phone calls → Set up).

**Exam season** (new; off until you turn it on, and nothing happens without exam dates)
- One card for the whole exam period (the exam periods in Subjects and the exams on your deadline list, from the day
  before the first to the end of the last), told once when it starts. Every part has its own switch on the card,
  with `/examseason` or in Settings.
- Non-critical updates wait until the exams are over; a release marked critical in its signed manifest still installs
  (`tools/release.py build --critical`).
- Every night of the period (21:30), the alarm check from "Kurooto keeps itself working" runs (and the call line's,
  when a leave-by call is set), with its safe fix first: "set your phone's own alarm too" if it might not ring.
- The evening before each exam, one question: where is it, which seat, calculator, ID card (and when, if unknown).
  An alarm to leave on time follows (45 minutes before, or "leave 8:10"): a call that rings like the wake-up alarm,
  or an urgent message without Phone calls.
- Half an hour after each exam, a two-minute debrief, saved as you said it under "Exam debriefs" in the subject's
  course note. No calls during an exam.
- The quiz call before an exam is off unless you pick it for that exam; exam mode's daily practice only calls for the
  exams you picked.
- For add-ons: `Module.card()` and `card_action()` put lines and switches on a feature's dashboard card;
  `app.updates.holds` lets a feature hold back non-critical updates.
**Leave cleanly** (new; only when you run it)
- `kurooto uninstall --revoke` first takes back what Kurooto set up on your accounts: deletes your call line from
  Cloudflare with its keys and stored data (through Kurooto's own Cloudflare sign-in, then signs that out; if it has
  expired, it prints the dashboard steps), revokes each Google account's access at Google's revoke endpoint, and
  clears your bot's webhook, waiting messages and command menu. It links what's left for you (the GitHub token page,
  the Gemini key, `/deletebot`), then removes Kurooto's keys from the keychain, which a plain uninstall left there.
- `kurooto rotate`, for a lost phone or a backup with your keys that got out: new keys for your call line (this
  computer's key to it, the key that signs call links, the phone notification key and channel, the Web Push keys),
  deployed to the same address; the old keys come back if the deploy fails. The call line then forgets every paired
  phone, its call links and open pairing codes, and the running Kurooto prints a pairing link and QR code to pair your
  phones again. The keys only you can replace come from the health checks' credential list.
- The call line forgets its paired phones, call links and pairing codes whenever its call-link key changes (after an
  update it only notes the key, so nothing is unpaired).

**Wrong button and test cases** (new; off until you turn it on)
- A Wrong button under replies to plain-English requests and under the AI's answers, and `/wrong` right after a
  reply: the request is kept as a case with what Kurooto did, the time and the settings that decided it. Short
  requests nothing understood (they went to the AI) are kept too; long ones and anything about health, money or
  passwords never are.
- Once a month the look back shows the phrasings that came up most, each with "Make it a test case". Say what you
  meant in words Kurooto understands ("what's due"), or "the AI": it becomes a test case and the phrasing is taught,
  only if every test case that passed still passes. Requests that send, delete, call, ring or approve are never
  learned this way. `/wrong <what you meant>` teaches at once; `/cases` lists what you taught, with Unlearn.
- `kurooto cases` lists them, `kurooto cases check` runs them, `kurooto cases export` writes a pytest file that
  replays each request at its own time and settings. All of it stays on this computer: not in backups, Profile sync
  or the diagnostics zip; cases not reviewed are forgotten after 30 days.

**Start-by dates and crunch weeks** (new; off until you turn it on)
- Each deadline gets a size from what it is (a problem set an evening, a report 2-3 days, a quiz 2 h, an exam what
  you set for its subject; a subject's first exam asks once), corrected with one tap. Working back from your free
  time (each day's window less classes and calendar events, and a share of the rest), each gets a start-by date;
  later deadlines push earlier ones back.
- From its start-by date the morning plan raises it (the morning page, the wake-up call, the plan drafted before the
  alarm), with one "Time to start" message on the day for the big ones.
- The Sunday summary flags crunch weeks: "week of 9 Nov: about 14 h of work, about 9 h free". `/startby`, "when
  should I start the lab report?", "any crunch weeks coming?". An estimate, local arithmetic only, no AI.
**Class packs** (new; off until you turn it on)
- `/classpack export` turns your section's setup into one small `.kurooto-course` file: subjects, timetable (lab
  batches and electives), term and exam dates, holidays, recurring quizzes, dated exams and each course's attendance
  rule (75%, labs counted separately, unless it says otherwise). From your setup, or from one term note alone
  (`/classpack export from terms/section-b`): the term note gains optional Type and Batch columns, and Recurring
  quizzes and Attendance tables. The maker gives the day it was checked against the official timetable before the
  file is made; it's stamped in the pack and the file comes to their Telegram to forward.
- A strict format: names, keys, notes, skills, links, contact details and skips have no place in it, and a file with
  any of them is refused whole, with the reason. `kurooto classpack check FILE` checks one.
- Send a pack to your bot: a review (when it was checked, what it means for you), tick your electives and lab batch,
  change any rule ("la 80", "la labs together", "la quiz off"), Import. It sits under your own setup (yours wins),
  writes nothing into your notes, and its quizzes and exams reach Deadlines. Attendance rules are kept per course for
  an attendance feature to read.
- Importing again after a reshuffle lists what changes for you first and keeps your choices. `/classpack`,
  `/classpack set`, `/classpack remove`, `/classpack undo`; `kurooto classpack export|import`.
**Attendance and standing** (new; off until you turn it on)
- `/attendance`: each course's attendance against its rule (75% unless you set another; labs counted on their own),
  with how many more classes you can miss: "Linear Algebra 82% (23/28), you can miss 3 more this term". Every class on
  your timetable counts as attended unless you `/skip` it; holidays, exam periods and the days after the last day of
  classes don't count. Everything is labelled an estimate.
- `/attendance set la 23/30` corrects drift from the official register; `/attendance rule la 80`, `/attendance rule
  labs 100`, `/attendance lab thu 14:00` (a slot that's a lab), `/attendance since 2026-08-03`.
- `/skip` asks first (Skip anyway / Don't skip) when a skip would leave a course under its rule; `/skip la anyway`
  doesn't ask. Calls tell you before marking such a skip. "can I skip LA on Friday?" answers without marking it.
- One line in the Sunday summary.
- `/standing` adds marks, after a "Set up marks?" question: weightage (`/marks la weights midsem 30, endsem 70`),
  scores (`/marks la midsem 21/30`) and grade lines (`/marks grades A 85, B 70`) give what you'd need on what's left
  for each grade, also an estimate.
**Staged updates and withdrawn versions**
- A version its maintainer withdrew (the signed yank list on the release site, `tools/release.py yank`) is never
  installed: not when found, not when it was already downloaded for the night, and not with `kurooto update --now`.
  The last list read is kept, so it stays refused while the site can't be reached.
- `updates.staged` (off until you turn it on): a new version installs only once it has been out 48 hours
  (`updates.wait_hours`), and never in an exam period or within a day of a quiz or exam (`updates.exam_hold`). A
  release signed as critical (`tools/release.py sign --critical`) skips both.
**First-week quests** (new; off until you turn it on)
- For the first seven days, one short message a day with one thing to try, each leaving something real (tomorrow's
  classes, a deadline, a reminder, a doubt, a quiz, a study session, a check-in answer, a journal entry). Only for
  features that are on and pass their checks, and never one already done. Replying with the thing does it.
- Skip this one moves on; Stop these, or a day's quest left alone, stops them for good. `/quests`, `/quests stop`.
**Doubt queue** (new; off until you turn it on; needs Subjects)
- `/doubt la <the doubt>`, or "I have a doubt about eigenvalues", adds a line to the subject's doubts note
  (`<subject>/doubts.md`, a new `doubts` kind in the notes layout). The subject is the one named, else the class on now
  or just ended, else buttons ask.
- Half an hour before the subject's next class (`doubts.before_min`), its open doubts arrive with a Tick button each
  that ticks it in the note. `/doubts [subject]`. No AI answers.
**Try it on the setup page**
- Once your AI passes its test, the setup page's AI step shows a chat box. What you type goes through the same handler
  as a Telegram message, before Telegram is set up: "remind me in 2 minutes to stretch" pops up on this computer, and
  questions go to your AI with the answer shown in the box. Nothing goes to Telegram or your phone.
**Hint ladder** (new; off until you turn it on; needs Subjects)
- A problem photo with `/hint la` (or the problem typed after it): the idea first, then the setup and the key step one
  tap at a time; the full solution only when asked. Each step names the lecture note the problem belongs to.
- The course's AI policy is asked the first time per subject and kept as an `AI policy: ...` line in its course note;
  "no full solutions" ends at the key step, "no AI help" sends nothing to the AI. The shipped `hint` skill writes the
  ladder (yours replaces it); an answer that isn't in steps is never passed on.

## 0.4.0 (part of 0.5.0)

**Books and PDFs** (new; off until you turn it on)
- Reference books and PDFs per subject: send one on Telegram with "book for <subject>", add it on the dashboard, or
  drop it in the subject's books folder. Books live outside your notes (`files.folder`, or Kurooto's data folder).
- Read at night on the charger, page by page, the best way for each page: the PDF's own text (Poppler, or Kurooto's
  built-in reader), Tesseract OCR for scanned pages, or a local vision model that writes the maths in LaTeX. Gemini
  only if you turn on `books.gemini`. It stops at 07:00 or when you unplug and carries on the next night.
- Each book gets an index note in your notes (`<subject>/books/<book>.md`: chapters with their pages); its text, with
  page markers, stays in Kurooto's data folder, and goes into the Notes brain when that's on.
- `/books` (per subject, how far reading got), `/books read now`, `/books stop`, `/books folder`, `/books setup`.
- Tesseract and Poppler join the things Kurooto can help install (winget for your user on Windows, Homebrew on a Mac;
  on Linux your package manager, which Kurooto never runs for you).

**Notes from every source**
- The source mix: how much books, Classroom materials and your own class notes each count when the AI writes notes,
  per subject (`/books mix <subject> book 30 classroom 30 own 40`, or an order: `prefer own book classroom`). Only the
  sources a subject has are used; the shares grow to fill the gap.
- `/study-log`, Classroom → notes, `/pack`, `/add-to-notes` and the new `/exam-prep` draw on all three through the AI's
  `course_sources` tool and cite where each part came from: (book: <title>, p. 123), (Classroom: <post>),
  (your notes: [[<note>]]). Your own words are quoted, never reworded.
- `/exam-prep <subject>`: brings a subject's exam prep up to date from everything there is, also without Classroom.

**Handwriting on an 8 GB graphics card**
- Handwritten notes are read by a model on your computer whenever there is one: the 12 GB vision model, or now the
  8 GB helper model (gemma4:e4b reads handwriting), or one you name (`handwritten.local_model`). PDFs too, not only
  photos: page by page with the maths in LaTeX, at night on the charger (`handwritten.pdf_hours`), resuming from the
  next page after an unplug or the morning, and waiting while the graphics card is busy. Gemini only when no model
  here can read them; `handwritten.cloud` = `false` never sends them.
- A changed original updates the same note between `kurooto:handwritten` markers and keeps what you wrote around it.
  `handwritten.keep_original` = `link` links to the original where it is instead of copying it. `/handwritten status`,
  `/handwritten retry`.

**Research**
- arXiv sources in arXiv's own search words (`{"type": "arxiv", "name": …, "query": "abs:… AND (…)"}`), each named
  in the digest; arXiv requests three seconds apart. `research.save_note` keeps each digest as `inbox/papers-<date>.md`.
- Runs a script keeps in its repository (`runs/index.csv`) get a line in the project's log every night
  (`research.repo_runs`). `from kurooto.runlog import Run`: `with Run("name", config=…) as run: run.log(step=…, x=…)`,
  into your notes with a project, else into the repository's `runs/`; failed and interrupted runs keep their error.
- Run links in project notes follow your notes layout. "Remind me tomorrow" for a quiet project is a call at 18:00
  when Phone calls is on (`research.remind_by_call`).

**Revision packs before exams**
- The evening before a quiz or exam with a subject, Kurooto offers a revision pack (**Build it** / **No thanks**), or
  builds it by itself with `skills.auto_pack` = `auto` (`off`: never).

**Your own GBrain**
- `gbrain.managed` = `false` uses a GBrain you already run (Postgres or PGLite; `gbrain.exe`, `gbrain.home`) instead
  of Kurooto's own: Kurooto only searches it, adds pages through gbrain's commands, keeps your notes' source in step
  (`gbrain.source`) and runs the nightly steps you choose. It never inits, migrates or reconfigures that brain.
- `gbrain.upkeep_steps`: choose the nightly upkeep's steps (GBrain's phase names; `purge` is never run).
- `gbrain.agy_mcp`: after your approval, agy gets your brain's own MCP server ("gbrain", `mcp(gbrain/*)`), keeping an
  existing registration and your own allow-list picks.
**Google**
- **Several Google accounts** (a personal one and a school one, say): each feature uses the account you choose on its
  card (a new name signs that account in) or with `/google use <feature> <account>`; each account is asked only for
  what its features need. `/google` lists them; `/google forget <name>` removes one.
- **Google Calendar**: Calendar can read your Google calendars through Google's Calendar API, from one account or
  several, for accounts without a secret iCal address. Other people's shared calendars are left out.
- **Private events are "Busy (private)"** wherever Kurooto shows or tells them (Google's Private visibility,
  `CLASS:PRIVATE` in iCal, or `#private`); their title and place aren't kept (`calendar.mask_private`).
- **Class calendars**: `/cal classes Timetable` makes that calendar's events classes (no calls, in your day's classes,
  the after-class question when the title names a subject).
- **Mail digest by email**: each digest also comes to your own inbox, sent from the account you choose, only ever to
  that account's own address; held back if it mentions confidential material.
- **Drive upload**: `kurooto send FILE --to drive` (and the AI's send_file) puts a file in a Kurooto folder in your
  Drive and sends the link; files over Telegram's 50 MB go there by themselves. It sees only files it made.
- The Agent plan calendar can live on another account (`/google use plan personal`).

**Four settings for doing it your way** (defaults unchanged)
- `availability.night.alarm_only`: only a night with the alarm set holds calls (bedtime to the alarm); with no alarm,
  nothing holds them overnight. Off by default: the fixed night hours (23:30 to 07:00) still hold calls without one.
- `deadlines.plan_h` (72): how far ahead "due soon" looks, for the wake-up call's plan, the morning page, the call
  brief, `/status` and "what's due soon?".
- After-class notes for some subjects only: `capture.subjects` (ask only after these; empty: all) and
  `capture.skip_subjects` (never after these), by short name, full name or alias.
- Mail digest by Gmail search: `/mail query -category:promotions -category:social` (`mail_digest.query`, empty by
  default) reads the mail a Gmail search matches. Your never-read list, the not-interested list and the confidential
  check still come first, and personal mail among it is only counted, never summarised. `/mail query off` clears it.

**Your term note, read live**
- `/term note terms/2026-autumn` (`subjects.term_note`): Kurooto reads your timetable, holidays, exam periods, last day
  of classes and a key-dates table from one note, again whenever it changes. Its classes and subjects join yours (a
  code next to a subject becomes a short name), and its quizzes and exams, plus deadlines that name a subject, reach
  Deadlines, kept once with the same thing from your notes, calendar or Classroom. A pattern (`maps/semester-*`)
  follows the current term's note; `auto` is `terms/*`, or `maps/semester-*` in the zettelkasten layout. The format
  is in the manual; `/term-setup` writes notes in it. `/term note off` undoes it; your note is never changed.

**Smaller things**
- The recurring-quizzes table skips any header row ("Course" instead of "Subject", or the row above `| :--- |`), so
  a renamed header no longer asks "which day?".
- With `quiz.by_call` and Phone calls on, `/quiz` and "quiz me" ring you straight away ("here" keeps it on Telegram).
- The dashboard's notes map opens a note with your own program: `notes.open_with`, e.g. `kitty nvim {path}` (no
  shell; the default app when it's empty or the program is missing).
- `kurooto ask-me "…" --then "CMD {answer}"` runs a command with your answer once it comes ({answer}, {id}), in the
  background or with `--wait`; never through a shell, and only from a terminal or script.
- Telegram's "/" menu lists the commands of the features you have on and your skills, kept up to date
  (`telegram.menu`); `/term_setup` style names run the skill with dashes.
- Add-ons: `processes_intermittent = True` on a feature whose programs only run now and then (a backup run, a nightly
  job): its dashboard cell and `kurooto top` line say "idle" instead of a grey "not running", and "running" with the
  figures while one runs.

## 0.3.0 (2026-10-20)
The [manual](docs/MANUAL.md) has the detail.

**Kurooto Terminal**
- `kurooto term` (off until you turn it on): your AI's program, your shell, Kurooto chat and its log in a terminal
  window of its own, with `kurooto top` beside them, in Kurooto's colours. kitty on Linux and macOS (yours, or the
  official kitty in Kurooto's folder, no admin), Windows Terminal on Windows (Kurooto's profiles and colour scheme as
  a fragment, no admin); fish when you have it (or the official fish in Kurooto's folder).
- An app-menu entry, and `kurooto term --shell` for just your shell in Kurooto's colours.
- An opt-in "make Kurooto my default terminal", with a clear undo: opening a terminal then gives you that themed shell
  (`terminal.default_opens`: `layout` for the whole window).
- `kurooto ask` gets the chat tab's look: the spaced name, examples and a `kurooto ❯` prompt.

**Dashboard and `kurooto top`**
- A new **dense** layout, the default on screens 1280 px wide or more: one full-screen board with each pane's name in
  its border.
  - STATUS is a btop-like monitor: history graphs, every core, a memory breakdown, the graphics card, network, disks,
    processes with Kurooto's own marked, study today and projects.
  - SYSTEMS has today, what's due, the AI's corner and recent events round the cells, the hours on the ring, and each
    feature's own programs on its cell. The cells' words sit outside them and never overlap, however many features
    are on: a crowded ring becomes two, and labels move a little (with a hairline to their cell) or shorten.
  - NOTES shows folders and recent edits.
  - The terminal below has its tabs and every other page in its border, and a **kurooto** tab for plain English
    without the Terminals feature.
  - `look.layout = roomy` keeps the earlier layout, which narrower windows get by themselves. `look.projects` lists
    the git folders the board follows.
- Settings shows a list to choose from, with a line of help, where a setting has fixed choices (the palette, the
  dashboard's layout, the notes layout).
- Settings → Starting: start Kurooto when you log in, or (Linux) when the computer starts. Windows and macOS show that
  they start at sign-in.
- `kurooto top` is laid out like btop, with the same figures as the dashboard: history graphs, every core, speed,
  temperatures and fans where the computer has them, memory and swap, the graphics card, network, disks, battery,
  processes (sort with `c` / `m`), and Kurooto's features, call line, today, what's due, study and projects.

**Colours**
- A third palette, **system**: Kurooto's pages take this computer's own accent colour and light or dark mode, and
  follow them when they change. It reads Material You colours from matugen (end-4's Hyprland setup and others), pywal,
  KDE, GNOME 47+ and GTK on Linux, and the accent colour on Windows and macOS. The setup page recommends it when it
  finds your colours (step 2, Colours); Settings → Look → `look.palette` changes it. Text is always made readable
  (WCAG AA). When nothing is found, it looks like kuro.
- `look.theme_file`: a kitty theme or a matugen or pywal `colors.json` of your own, used instead of the desktop's.
- The rose palette's light version: its pink and coloured text is darker, so it's readable on the light background.

**Setup page**
- Each step says what it's for and what happens if you skip it; a step you passed but haven't finished shows "!".
- Words like API key, token, repository, iCal, Cloudflare, GBrain or agy have a one-line explanation: tap the dotted
  word.
- The time zone is picked from a list as you type; a name it doesn't know is caught before you go on.
- AI step: one **Save and test** button for a key, progress while it tests, and what to do when a test fails (for
  each kind of AI). Sign-in windows report back on the page instead of a pop-up.
- Telegram step: an empty or wrong token says what to paste.
- Done step: what's ready and what isn't (with a link back to it), progress for each feature being set up, and next
  steps with an **Open the dashboard** button.
- If Kurooto stops answering, a bar at the top says how to start it again; it goes away by itself.

**Going offline and coming back**
- Kurooto says "going offline (shutting down)" before a clean stop (stop, off, signing out, shutting down; never for
  an update's restart), and "back online (offline since 22:10, 7 h)" after a start, a wake from sleep or a network
  outage ("the network was down from 14:02 to 14:31"), with what it caught up on. Telegram messages that couldn't go
  out while the network was down follow, marked as delayed.
- Nothing for under 10 minutes away; sleeps close together give one message; at night it waits for the morning.
  Settings: `notify.presence`.
- With Phone calls, your call line says "offline since ..." when the computer can't (sleep, a crash, a lost network):
  on the phone app, and on Telegram if you approve giving it your bot's token (asked once). Without a call line there's
  no message for those.

**Check-ins and the computer**
- A check-in day runs from 05:00 to 05:00 (`checkins.day_starts`), so a night check-in after midnight, or one pushed
  past it, stays the evening's (it used to move to the morning), and its journal goes to the evening's day.
- Check-ins by call: with the alarm set and past your bedtime (or the alarm just set by you), the night check-in
  doesn't ring; it moves to the wake-up call, with **Call me now** and **Skip** on Telegram
  (`checkins.asleep_defers`).
- Morning alarm: `alarm.keep_awake` keeps this computer awake from 12 hours before the alarm until it rings (Linux:
  lid closed too; macOS through caffeinate; Windows), so the morning plan is drafted on time. Off until you turn it on.
- Morning alarm: the daily alarm rings even if this computer slept all night. The next one goes to your call line
  as soon as the last one has rung (and at start, and after the computer wakes), instead of only at 00:02.
- Morning alarm: "no alarm tomorrow", "cancel Friday's alarm" or `/alarm skip friday` skips one day and the daily
  alarm comes back after it; "cancel my alarm" skips the morning that's set instead of the daily alarm coming back
  at midnight; "turn my daily alarm off" (`/alarm daily off`) stops it, `/alarm daily 7:00` sets it.
- Stay awake on charger: `awake.lid` keeps a Linux laptop running with its lid closed while plugged in. Off until you
  turn it on. The hold now ends when Kurooto stops, even after a crash.
- Study tracker: it notices you're away on Wayland too (GNOME, KDE, logind, and a watch for change on Hyprland and
  Sway); a locked screen never counts; `kurooto idle away|back` for hypridle and swayidle; and a Research category
  (`study.research_paths`, plus Research's projects).
- Linux: `kurooto autostart boot` (or Settings → Starting) starts Kurooto when the computer starts, before anyone logs
  in (lingering; its keys are kept in the owner-only settings file); `kurooto autostart login` goes back.

**Your notes**
- Notes layout: `notes.layout` picks where Kurooto writes (the `kurooto` layout as before, or `zettelkasten`:
  `dailies/`, `master/`, `sources/<subject>/`, `maps/`, `zettel/`, `projects/`, `digests/`), `notes.paths` puts any
  kind of note where you like, and new notes get that layout's header. The AI, skills and `kurooto note` follow it.
- Files folder: with `files.folder` set, photos, PDFs, revision packs, handwriting originals and Classroom files go to
  a folder outside your notes, linked from them, so they stay out of your notes' history. Unset, nothing changes.
- Revision packs are also linked from the subject's course page.
- Notes sync: a note changed here and elsewhere at once keeps both versions (the other device's in the note, this
  computer's as a "conflict" copy beside it) instead of this computer's winning; `notes_sync.on_conflict = stop`
  stops and asks you instead. A half-finished merge is left alone, and an existing `origin` (e.g. over SSH) is kept.

**From a terminal or a script**
- `kurooto notify` takes buttons (`--button "Label=prefix:ref:action"` or a web address), a link to open (`--click`),
  a reply to an earlier message (`--reply-to`, with `--print-id`), and the kinds `question` and `approval`.
- `kurooto call --list` shows the calls booked for later; `kurooto call --cancel <key>` takes one off.
- `kurooto sync --status` (works with Kurooto stopped) and `kurooto sync --no-wait`; sync everything ends with a
  backup when Backups is on.
- `kurooto ask-me --pending [--json]` and `kurooto ask-me --id <id> --wait`.
- `kurooto usage [days]`: `/usage` in a terminal.

**Skills in agy and other agent programs**
- `kurooto export-skills on` makes your skills (Kurooto's, your add-ons', your own and prompts with `skill: true`)
  slash commands in agy (`--to agy,agents` adds Codex and Copilot CLI). Only Kurooto's own copies are ever changed or
  removed; one of yours with the same name stays, and Kurooto's goes in as `kurooto-<name>`. Kept up to date at start
  and hourly; `kurooto export-skills off` and `kurooto uninstall` remove them.

**Seeing what's going on**
- `/status` also shows today's check-ins, what's due in the next 3 days, the alarm and your last AI requests.
- `/usage` also counts agy itself from its own logs (every run, the ones you type too), with the days it hit its limit.
- `kurooto doctor` asks Telegram whether your bot answers and your call line whether it's up and linked, and no longer
  reports the call line as unlinked just because the check runs outside Kurooto. It also shows your notes layout and
  any problem with its settings (`notes.layout`, `notes.paths`, `files.folder`).
- `/observing` has a **+7 days** button.

**Add-ons**
- An add-on feature can pick which plain-English request a message is before Kurooto's own patterns
  (`classify_intent`, with a 2-second limit and a fall-through), and add lines to `/status` (`status_lines`) and to
  `kurooto doctor` (`doctor_checks`).
- Add-ons can name programs a feature watches (`processes` on the feature): their cpu, memory and uptime show on the
  dashboard and in `kurooto top`, and the cell turns grey when none is running.

## 0.2.1 (2026-10-20)
- Setup page: on a desktop it uses the whole window: the steps sit in a list on the left with what each one is for,
  and feature cards fill four columns instead of a narrow strip. On a phone the steps are numbered dots. Any step can
  be opened from the list, Back and Next stay in view on long steps, and buttons, boxes and cards are tidier, with a
  visible outline when you move through them with the keyboard.
- On laptops whose charger the system names unusually (e.g. ACAD on Linux), Kurooto thought it was on battery while
  plugged in, so battery-saving held back heavy work; it now asks the system directly.
- The confidential-mail page follows your colours (Settings → Look), like the other pages.

## 0.2.0 (2026-10-20)
Many new features, each off until you turn it on. The [manual](docs/MANUAL.md) has the detail.

**Updating from 0.1**
- Nothing new starts by itself: if you set Kurooto up with 0.1, the morning page doesn't open at the alarm, the AI
  doesn't draft a plan before it, deadlines don't ring you six hours before or come from your calendar, an unanswered
  call rings again once (not twice), after-class answers aren't turned into AI study logs, and the nightly look back
  doesn't read your journal or call transcripts, unless you turn them on (or had set them yourself).
- No flood on the first day: deadlines already overdue and research projects already quiet aren't asked about.
- One short "What's new" message after the update, with a link to the manual.
- agy and Kurooto's tools: if you set agy up before, Kurooto asks once (Approve / Deny) before adding itself to agy's
  settings; Deny holds for 30 days. On the setup page, testing agy says it connects the tools.

**Your AI**
- The setup page recommends a **Gemini API key ★** (the simplest, and Google's recommended route for tools like
  Kurooto), then agy, Codex, Claude Code, local models and any OpenAI-compatible service. Existing setups keep the AI
  they chose.
- The setup page says plainly what a free Gemini key means (Google may use and review what you send; 18+; a paid key
  in the EEA, UK and Switzerland) and what using agy through Kurooto means for your Google account.
- FreeLLMAPI is no longer offered; one set up earlier keeps working and shows as "Another OpenAI-compatible service".
- The AI can act, not just answer: every feature's tools (reminders, calls, deadlines, study log, notes, questions to
  you) reach API brains directly and agent programs (agy, Codex, Claude Code) through `kurooto mcp`, a built-in MCP
  server. The notes tools only create, add to and tick; they never change what you wrote.
- `/usage`: AI requests per day per brain over the last week, and usage limits hit.
- Your AI can read your files (notes, Documents, Downloads, Screenshots, Kurooto's Classroom and mail copies) and
  public web pages, write and edit text files in your notes (the previous version is kept), and tell you how your
  syncs are doing (`sync_status`). agy gets the same reach through its allow-list, after you approve it: those
  folders, the web, and harmless commands such as git and latexmk; never `kurooto` itself.

**Questions, approvals and your phone**
- Questions and approvals from features, AI requests and your own scripts, answered anywhere: Telegram buttons or a
  reply, the phone app, or a call; the first answer wins. **Later** keeps one for your next call; `/q` lists the open
  ones. AI requests can ask you a question; your answer starts the follow-up.
- Your phone is a second channel: questions and approvals reach the Android app (Reply box, choices, Approve / Deny,
  Later) and the iPhone Home Screen app ("Waiting for you"), also while the computer is off. `notify.app_kinds` picks
  what else goes there.
- Calls: open questions come up at the start of a call, and approvals that arrive during one are asked there. Nothing
  else rings while you're on a call, and updates wait for it to end.

**Check-ins, mornings and calls**
- The evening check-in call is a debrief (classes, what slipped, open questions, study time, a quiz offer before
  exams); afterwards the AI writes your journal and study logs from what you said.
- A night check-in (off until you give it a time) says goodnight and sets the alarm, or moves to your wake-up call
  with **Tomorrow morning**.
- Unanswered or declined check-in calls become a message with Call me now / Tomorrow morning / Skip; "call me back
  later" keeps it a check-in. Change another day's check-in ("skip Friday's check-in"); `/checkins` has buttons.
- Mornings: the AI drafts your day 20 minutes before the alarm, the wake-up call goes through it, and the morning page
  opens on your computer.
- The night follows your alarm; unanswered calls ring again at +3 and +6 minutes; held calls tell you so and come by
  themselves when the block ends; "call me now".
- Calendar: `#focus` events are focus time; optionally only `#nocall` events hold calls.
- Weekly summary: an optional Sunday review call, written up in your journal.

**Study**
- Deadlines: calendar events that look like deadlines or exams, and recurring quizzes (a table in your notes,
  `/recurring`), join the list; the same thing from two places is kept once.
- Deadlines: the six-hour nudge is a call when Phone calls is on; an "Overdue?" check (Done / New date / Drop); Done
  ticks the box in your notes.
- Not interested (`/ignore`): topics left out of deadlines, and only counted in the mail and Classroom digests.
- Exam mode: on by itself two weeks before a quiz or exam (`/exam`); calls know about it; quizzes come more often.
- Quiz: sessions of several questions, a practice offer the evening before, quizzes by call, quiz check-ins.
- Subjects: term dates and exam periods (`/term`); "skipping LA on Friday".
- After-class notes: answer later on the evening call; photos and files filed next to the class log; an AI study log.
- Study tracker: sessions away from the computer (`/study la 50`, `/study stop`) and a "Study hours" section in your
  daily note.

**Notes and skills**
- Skills: `/journal`, `/study-log`, `/add-to-notes`, `/assignment`, `/connect-notes`, `/term-setup`, `/goodnight`,
  `/morning`, `/morning-prep`; reply to a skill's answer to carry on. A link sent on its own is filed into your notes.
- Your own skills (`/newskill`, `/skills copy`), routines (`/every monday 9:00 /journal plan my week`) and revision
  packs as PDF (`/pack`, with Tectonic, which Kurooto can install for you).
- Quick notes and prompts: `/note`, `kurooto note`, `/prompts`, `/prompt`.
- About you: the profile is editable right after **Build my profile** (setup page, and a new **About you** tab in the
  dashboard), with a preview of the In-brief part that goes along with every AI request; saving keeps the previous
  version. Building again asks first if you've edited it, and never replaces an edit made while it was building.
  `/aboutme` shows the In-brief part.
- Remember: `/remember`, "remember that ...", and on calls; kept in `about-me/how-to-help-me.md`, which you edit and
  which wins. Health, money and passwords are refused.
- Nightly look back: reads your answers, check-ins, call transcripts and journal; suggests settings, how-to-help-me
  lines, things to watch, skill changes (shown before saving) and ideas. Apply / Observe longer / No. `/observe`,
  `/observing`, `/lookback`.
- Notes brain: timelines (`/timeline`), an optional nightly upkeep and a weekly checkup.
- `kurooto send FILE`: a file to your Telegram; the AI can send you files from your notes.

**Google**
- Classroom → notes: new materials, coursework, announcements and attached Drive files filed into your notes by the AI
  (a note per lecture, a course page, an exam-prep note that Quiz uses); dates go into Deadlines.
- Mail digest: twice a day, sorted into Needs action, People, Courses, Opportunities and Admin. It reads only the
  senders, domains and labels you choose; mail marked confidential (anywhere in it, standard confidentiality footers
  included) and your never-read list are only counted, never summarised or answered with an AI draft. Optional local
  mode (`mail_digest.confidential = local`): a local model summarises confidential mail on this computer, kept only
  in Kurooto's data folder (dashboard → Features → Mail digest → Confidential mail); dates found there are offered
  (`/mail confidential`), never added by themselves.
- Email reply drafts with Send / Edit / Discard: nothing is sent without your tap.
- Agent plan calendar: time blocks Kurooto plans with you go into a calendar of its own (`/blocks`).
- Each Google feature asks for its own permission and turns on by itself after the sign-in.
- Setting up Google is beginner-proof: a step-by-step guide in the manual (every screen of Google Auth Platform,
  with links), and the setup card has a numbered summary, copy buttons for the values Google asks for, and a file
  button for the client JSON. The site has a privacy page (made from docs/PRIVACY.md).

**Your setup, kept safe**
- Backups: a daily zip in a folder you pick (an external drive, a cloud-synced folder); `kurooto restore`, which
  never overwrites a note.
- Profile sync: your settings, keys and saved state, encrypted with a passphrase only you know, in your own private
  GitHub repository. Moving to a new computer: "I've used Kurooto before" on the setup page, or
  `kurooto profile restore`.
- Sync everything: `/sync all` or `kurooto sync`. Notes sync also sends notes up after AI requests and when Kurooto
  stops.

**Research and your terminal**
- Research projects: a note per project with a log of each day's commits, a hub note, and a question when a project
  goes quiet.
- `kurooto runlog` (experiment runs with their config, metrics and exact code state), `kurooto watch -- CMD` (a
  message when a long job ends), `kurooto top` (a status board), `kurooto logs`, `kurooto ask` (plain English),
  `kurooto call`, `kurooto ask-me` and `kurooto ask-approval`.
- Terminals in the dashboard (off by default): your AI program, a shell, `kurooto ask` and the log.
- Your add-ons: your own features, skills, prompts and default settings from a folder of yours.
- On Linux, the dashboard only answers your own user account.

**Look**
- Kurooto's pages are deep green now, like the website: the setup page, the dashboard (its drawings too), the morning
  page, and your call line's pages and icon. The old colours stay available: Settings → Look → `look.palette` = `rose`.
- Warnings and errors have their own colours (amber and red), never the accent colour.
- The dashboard's ring gives every feature a short label and its own colour.
- The README and the website show the dashboard, the setup page, the morning page and your phone, from a demo with
  made-up data.

**Fixes**
- The setup page's "When this laptop is on battery" choice was refused; it's saved again, and Settings can change it.
- The dashboard keeps its address after a quick restart or an update (macOS and Linux).
- `kurooto stop` stops Kurooto the normal way first (Notes sync sends up what's left), then forces what's left;
  `kurooto start` says where the page is; `kurooto on` doesn't wait for a service manager that isn't there.
- After `kurooto update --now`, or an update that was rolled back, the dashboard no longer says "update ready"; a
  rollback sends one message saying so.
- The 05:10 call-line update after an update never opens a Cloudflare sign-in page by itself; if the sign-in expired,
  you get a message (calls keep working on the old version).
- A 24-hour time is taken as written: "/checkin midday 04:30" is 04:30, not 16:30.
- /status and `kurooto top` say what's coming in words, not internal names. "Overdue?" isn't said twice.
- The ★ Starter set no longer includes the notes brain (a 0.5 GB download; its card says so). Exam mode's daily
  practice check-in is off unless you give it a time (`quiz.exam_daily`).
- `kurooto doctor` warns when your time zone (Settings → You) isn't this computer's.
- Kurooto's job and schedule databases are readable by your account only, like its other state files; the installer
  starts Kurooto without its own temporary Python environment on the PATH.
- The phone's call page: the "Waiting for you" link no longer grows to fill the screen.
- "skip Friday's check-in" (and "no calls on Friday", "skipping LA on Friday") changed today's instead.
- The phone app only ever got rings; the phone channel is now wired up.
- The notes brain's sync no longer holds up the rest of Kurooto, and GBrain no longer checks for its own updates.
- Long requests to agy no longer fail on Windows' command-line limit.

## 0.1.6 (2026-10-20)
- **Phone calls couldn't be set up at all**: building the call page always failed. Fixed; setup now goes on to the
  Cloudflare sign-in. The Phone calls card lists what's needed in order (a free Gemini key, needed even when agy
  answers your messages; a free Cloudflare account; then pairing your phone, which is where the app comes from) and
  has a **Set up now** button.
- **Google sign-in could seem to do nothing**: the browser blocked the pop-up. There's now always an **Open Google
  sign-in** button, the card notices when you're signed in, and each way it can fail says what to do (including
  boxes left unticked on Google's consent page).
- Setup logs no longer vanish when the page redraws, and a refused setup says why.
- Setting up local AI models on Linux could get Kurooto killed for running out of memory: Ollama's download was
  unpacked in memory. It's now unpacked straight from disk, and the space check counts Ollama's real size.
- Setup: click anywhere on a feature card to tick it, and the boxes are bigger.
- A request to the AI could now and then vanish or fail when the setup page or the dashboard checked on it at the
  same moment (mostly on Windows).
- `kurooto start` works on computers where systemd's user session doesn't (WSL, containers).

## 0.1.5 (2026-10-20)
Everything since 0.1.1, in one update.
- **`kurooto stop` didn't stay stopped** on Linux and macOS (the background service restarted it 10 seconds later),
  and `kurooto start` / `on` could start a second copy beside it: both now go through the service manager.
- **`kurooto` was an "unknown command"** on computers that already had uv: Kurooto now puts its folder on the PATH
  (your user PATH on Windows, fish, bash and zsh) when it installs and whenever it starts, and the installer says
  how to use it in the terminal you installed from.
- **Telegram setup could wait forever** after pressing Start: the page now says why (another program using the bot,
  a webhook, a revoked token, an expired link, no internet), offers the fix, and always shows the message to send by
  hand. Running setup again while Telegram is on no longer swallows the Start message.
- **"Build my profile" failed with agy**: text-only work now tells agy to answer with text only.
- **agy and a Gemini key back each other up**: if one can't do something (refused, limit reached, signed out,
  failed), the other answers, and a line at the end says which. Without a Gemini key, the message says what to do.
- Long requests reach agy through a file, so profile builds work on Windows too.
- About you: the profile is editable right after **Build my profile**, on the setup page, with a preview of the
  In-brief part that goes along with every AI request; saving keeps the previous version. Building again asks first if
  you've edited it, and never replaces an edit made while it was building. `/aboutme` shows the In-brief part.
- The setup page recommends the Gemini key first (★); agy is second, with a plain note about it.

## 0.1.1 (2026-10-20)
Fixes, delivered as the first automatic update.
- A check-in call that comes due during a class, a hold, focus or the night now waits until the block ends, or comes
  as a message if that's too late for today.
- What you say on a check-in call reaches your journal again.
- Checking Kurooto (`kurooto doctor`) while the AI is working no longer makes that request run a second time.
- A landing page at avtarfr.github.io/kurooto.

## 0.1.0 (2026-10-19)
The first release, for friends.
- One-line install on Windows, macOS and Linux (per user, no admin), signed releases, a setup wizard that reads the
  computer and recommends settings, and installs what each feature needs (with a storage check).
- AI brains: Antigravity (agy), Gemini key, ChatGPT/Codex, FreeLLMAPI, Ollama, any OpenAI-compatible service, and
  Claude Code (Advanced); a fallback brain; effort picked per request.
- Features (all opt-in): Telegram, Chat, Reminders, Check-ins (by message or call), Deadlines, Subjects and timetable,
  Quiz, Weekly summary, Files into notes, Notes brain (GBrain), Local AI models, After-class notes, Nightly look back,
  Phone calls (your own call line; Android app; iPhone web app), Morning alarm, Voice notes, Stay awake on charger,
  Calendar, Notes sync, Google (Classroom, Gmail drafts), Handwritten notes, Study tracker, Research (a digest of new
  papers from arXiv's 155 fields, bioRxiv, medRxiv, PubMed and any feed, with its own dashboard tab).
- About you: prompts to run in all your other AI accounts, their reports brought into Kurooto, and a profile built
  from them that every AI request starts from.
- A local dashboard; `kurooto doctor` and a redacted diagnostics bundle.
- Laptops: a battery saver (Telegram keeps working; heavy work waits for the charger and runs when plugged in),
  `/pause` and `/resume`, and `kurooto off` / `on` (with a Kurooto entry in the app menu to turn it back on).
- Automatic, signed updates with rollback.
