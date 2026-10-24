# Settings guide

Every setting Kurooto has, what it does and its default. This file is written by `tools/gen_settings_guide.py` from the
code, so it is complete; the notes on the left come from the comment beside each setting in the source.

## Where settings live, and how to change one

- **The dashboard:** Settings (Alt+S), grouped by feature, with a search box: the core sections (you, notify,
  availability, updates, brain, ask, look, power, notes, files) and the features that are on. Changes apply at once;
  most are read again the next time they're used. A few are read only when Kurooto starts (such as `web.port`): for
  those, restart it with `kurooto stop`, then `kurooto start`. The other core sections (such as `quota`, `health`
  and `sources`) aren't on that page yet: change them in the file.
- **The file:** `settings.json` in Kurooto's config folder (Linux `~/.config/kurooto`, macOS
  `~/Library/Application Support/Kurooto/config`, Windows `%LOCALAPPDATA%\Kurooto\config`). It holds only what you changed; delete a
  line to go back to the default. A dotted name such as `brain.main` is the key `main` inside `brain`:
  `{"brain": {"main": "agy"}}`.
- **The terminal:** `kurooto doctor` says what's wrong with the settings that matter.
- Secrets (keys, tokens) are never in `settings.json`: they're in the system keyring or `secrets.json` beside it.

## How an AI is allowed to act (permissions)

Requests run by an agent program (agy, Claude Code) are unattended, so what they may do is decided in advance:

| | agy | Claude Code (from 0.5.6) |
|---|---|---|
| Kurooto's tools (reminders, notes, calls, files) | allowed in agy's own settings, once | given for each request |
| Your own GBrain's tools (`gbrain.agy_mcp` on) | allowed in agy's own settings | given for each request |
| Read | notes, course files, Classroom and mail copies, Documents, Downloads, Screenshots | the same |
| Write | notes folder, course files folder, your add-ons' skills | the same |
| Harmless commands | `cat cd date echo file grep head jq ls mkdir pdftotext pwd stat tail tree uniq wc which` | the same |
| Web pages | yes | yes |
| `kurooto` itself | never | never |
| Where it's kept | agy's `settings.json` (a backup is taken; your own rules stay) | nowhere: nothing is saved in Claude Code's settings |

Codex is no longer offered (0.5.6): a setting that names it is cleared.

A request that tries anything else is refused, and the answer says what was refused. To widen what agy may do, add a
rule to `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` yourself; Kurooto never removes rules it
didn't write. Add-ons run as you, with your own permissions; turn on only ones you wrote or read.

## Add-ons

A Python file in the add-ons folder (`overlay.path`, shown in Settings → Add-ons) that defines a `Module` subclass is loaded
when Kurooto starts, once "Your add-ons" is on. It gets the same settings, features and dashboard cell as a built-in
feature. Add-ons are yours: they aren't part of updates and aren't published.

Add-ons by link (`kurooto addons add <git url>`, Features → Add-ons by link) come from someone else's repository at a
pinned commit, after you've read their card; `addons.on` turns them all off. Their settings are listed in each one's
README, and appear in Settings once their feature is on. Official add-ons (`kurooto addons official`) are add-ons by
link from Kurooto's own list, each at the commit it pins; `addons.official_updates` says when a newer one comes.

## Every setting


### `addons`

| Setting | Default | What it does |
|---|---|---|
| `addons.official_updates` | `true` | say once when Kurooto brings a newer official add-on you have; never updated alone |
| `addons.on` | `true` | load the add-ons you added by link (kurooto addons add); False: none load from the next start |

### `agent_plan`

| Setting | Default | What it does |
|---|---|---|
| `agent_plan.name` | `"Agent plan"` | the name of the plan your AI subscription is on, shown in usage lines |
| `agent_plan.remind_min` | `5` | minutes before a plan's usage window ends to remind you |

### `agents`

| Setting | Default | What it does |
|---|---|---|
| `agents.export` | `[]` | where your skills go as slash commands: "agy", "agents" (Copilot CLI and others), "claude" |
| `agents.prefix` | `""` | put before every exported skill's name, e.g. "k-" for /k-journal |
| `agents.scripts` | `[]` |  |

### `alarm`

| Setting | Default | What it does |
|---|---|---|
| `alarm.bedtime` | `null` | "23:00": with the alarm set, no calls from then until it rings; None = the night's start |
| `alarm.daily` | `null` | "07:00" rings every day (on the days below) unless you set another time; None = off |
| `alarm.days` | `["mon", "tue", "wed", "thu", "fri", "sat", "sun"]` | the days the daily alarm rings |
| `alarm.keep_awake` | `false` | keep this computer awake until the alarm (Linux: lid closed too), so the plan is drafted |
| `alarm.notes` | `true` | after the wake-up call: today's plan (with Chat on) or what you said, in the daily note |
| `alarm.open_page` | `true` | at the alarm, open the morning page on this computer if it's awake |
| `alarm.prep_min` | `20` | with Chat on: the AI drafts the day's plan this long before the alarm; 0 = don't |
| `alarm.reason` | `"Wake-up call"` | what the wake-up call says it's for |
| `alarm.retries` | `2` | how many more times it rings if you don't answer |
| `alarm.snooze_min` | `10` | minutes a snoozed alarm waits |
| `alarm.suggest` | `true` | before your usual bedtime with no alarm set: one message suggesting your usual time |

### `ask`

| Setting | Default | What it does |
|---|---|---|
| `ask.expire_hours` | `48` | an unanswered question expires after this long, unless its asker said otherwise |
| `ask.keep_days` | `0` | answered and expired questions are forgotten after this many days (0: privacy.keep_days) |

### `autostart`

| Setting | Default | What it does |
|---|---|---|
| `autostart.when` | `"login"` | login \| boot (Linux with systemd: before anyone logs in) |

### `availability`

| Setting | Default | What it does |
|---|---|---|
| `availability.absence_days` | `2` | nothing from you this many days: one gentle message (0: never) |
| `availability.focus_keyword` | `"#focus"` | a calendar event with this in its title holds messages and calls (focus) |
| `availability.learn_morning` | `true` | the check-in day, morning message and "Time to start" follow them (not ones you set) |
| `availability.learn_night` | `true` | move the night hours to when you're usually quiet (not ones you set), with Undo |
| `availability.night.alarm_only` | `false` | hold calls at night only when a wake-up alarm is set |
| `availability.night.enabled` | `true` | no calls during the night hours |
| `availability.night.from` | `"23:30"` | when the night hours start |
| `availability.night.to` | `"07:00"` | when the night hours end |
| `availability.nocall_calendar` | `"no call"` | every event in a calendar whose name contains this holds calls |
| `availability.nocall_keyword` | `"#nocall"` | a calendar event with this in its title means no calls during it |

### `awake`

| Setting | Default | What it does |
|---|---|---|
| `awake.lid` | `false` | Linux: also keep running with the lid closed while plugged in |

### `backups`

| Setting | Default | What it does |
|---|---|---|
| `backups.confidential_mail` | `false` | also confidential mail summarised on this computer (Mail digest's local mode) |
| `backups.folder` | `""` | where the zips go: an external drive or a cloud-synced folder |
| `backups.index` | `true` | also the notes brain's index (big, but slow to rebuild) |
| `backups.keep` | `7` | how many zips to keep |
| `backups.memory` | `false` | also the memory ledger (encrypted: it opens only where its key is, see backups.secrets) |
| `backups.notes` | `false` | also your notes folder |
| `backups.secrets` | `false` | also passwords and keys (bot token, API keys, sign-ins): anyone with the zip can use them |
| `backups.when` | `"daily 03:30"` | when the automatic backup runs |

### `books`

| Setting | Default | What it does |
|---|---|---|
| `books.after_read` | `[]` | your command, run after each book is read, with its subject and id added: ["prog", "-x"] |
| `books.at` | `"daily 01:00"` | when the night's reading starts |
| `books.brain` | `true` | index the text into the notes brain when it's on |
| `books.brain_source` | `""` | an existing gbrain source (`gbrain sources list`) for the chunks; "" = the default one |
| `books.dpi` | `200` | how sharp the page pictures are for OCR |
| `books.folder` | `""` | your own folder for books, a subfolder per subject; empty: files.folder, else Kurooto's |
| `books.gemini` | `false` | True: pages nothing on this computer can read go to Gemini (your key) as pictures |
| `books.gemini_model` | `"gemini-flash-latest"` | the Gemini model that reads scanned book pages when it's chosen |
| `books.latex` | `"maths"` | vision reads for LaTeX: maths (pages whose maths came out in pieces) \| all \| never |
| `books.max_mb` | `400` | bigger files are left alone |
| `books.ocr` | `"auto"` | who reads scanned pages: auto (Tesseract, else the vision model) \| tesseract \| vision \| off |
| `books.ocr_lang` | `"eng"` | Tesseract's languages, e.g. "eng+deu" (each needs its language data installed) |
| `books.until` | `"07:00"` | when it stops (it carries on the next night) |

### `brain`

| Setting | Default | What it does |
|---|---|---|
| `brain.agy.io_mode` | `"pipe"` | how Kurooto talks to agy: pipe, or a pseudo-terminal where pipes give no output |
| `brain.base_urls` | `{}` | per brain, to override a preset's address |
| `brain.classify` | `"rules"` | who judges how hard a request is: rules, main (your AI) or ollama |
| `brain.claude_accounts` | `{}` | extra Claude accounts, each its own AI "claude:<key>": {"work": {"name": "Work"}} |
| `brain.effort_map` | `{}` | tuned while dreaming: {"low": "medium"} runs your requests rated low at medium effort |
| `brain.fallback` | `""` | the AI that takes over when the main one can't answer, or a list of them in order; empty: at a limit (brain.fallback_on), the other agent program, then a Gemini key |
| `brain.fallback_first` | `[]` | tuned while dreaming: effort levels ("high") at which your first fallback AI goes first |
| `brain.fallback_on` | `["rate_limited"]` | what hands a request to the next AI: rate_limited, auth, timeout |
| `brain.main` | `""` | the AI that handles requests: agy, claude, gemini, ollama or custom, or an extra Claude account (claude:<name>) |
| `brain.models` | `{}` | per brain: {"custom": {"low": ..., "medium": ..., "high": ...}} |
| `brain.timeout_min.high` | `30` | minutes a hard request may run before it's stopped |
| `brain.timeout_min.low` | `10` | minutes a quick request may run before it's stopped |
| `brain.timeout_min.medium` | `15` | minutes a normal request may run before it's stopped |

### `calendar`

| Setting | Default | What it does |
|---|---|---|
| `calendar.class_calendars` | `[]` | names (any part, any case) of calendars whose events are classes, e.g. ["Timetable"] |
| `calendar.days` | `14` | how many days ahead Kurooto reads your calendar |
| `calendar.holiday_calendars` | `[]` | names of calendars whose all-day events are holidays (no classes), e.g. ["Holidays"] |
| `calendar.mask_private` | `true` | private events: "Busy (private)", nothing else kept |
| `calendar.no_calls_in_events` | `true` | no calls while a calendar event is on |
| `calendar.nocall_events` | `"all"` | "all": every timed event holds calls; "tagged": #nocall ones, "no call" calendars |
| `calendar.private_keyword` | `"#private"` | an event with this in its title is never shown or read aloud |
| `calendar.refresh` | `"every 15m"` | how often the calendar is read again |
| `calendar.remind_min` | `0` | minutes before an event to remind you (0: off) |
| `calendar.shared_offer` | `true` | a subscribed calendar's deadlines and exams offered with an Add button each |

### `calls`

| Setting | Default | What it does |
|---|---|---|
| `calls.later_min` | `30` | "Later" on a ringing call calls back after this long |
| `calls.lessons_max` | `12` | the most lessons every call is told; a new one that says the same replaces the old |
| `calls.live_model` | `"gemini-3.8-live"` | the Gemini Live voice model for calls |
| `calls.live_models` | `["gemini-3.1-flash-live-preview", "gemini-2.5-flash-nativ…` | other Live models to try, in order, when the first one is down |
| `calls.notes_repo` | `""` | owner/repo of your notes on GitHub (Notes sync), so calls can read notes while off |
| `calls.ntfy_server` | `"https://ntfy.sh"` | the push server the phone app listens to (change only if you run your own) |
| `calls.persona` | `""` | extra words on how to talk on calls, e.g. "be brief and a bit cheeky" |
| `calls.realert_min` | `[3, 6]` | a call you didn't answer rings again this many minutes after the first; [] = once |
| `calls.review` | `true` | after every call, an AI request looks back at it: does what slipped through, keeps lessons |
| `calls.review_brain` | `""` | which AI does the look back ("" = your main one) |
| `calls.review_effort` | `"high"` | how hard that look back thinks (low, medium, high) |
| `calls.ring_s` | `60` | how long a call rings before it counts as missed (a wake-up call rings 5 minutes) |
| `calls.text_model` | `"gemini-flash-latest"` | the Gemini model for turn-by-turn calls (here, or on your call line) |
| `calls.today` | `true` | the Android app's Today screen and its copy of your alarm, sealed for each phone (today.py) |
| `calls.turn_brain` | `"gemini"` | answers turn-by-turn calls here: "gemini" (your key) or "local" (Local AI models) |
| `calls.views` | `false` | Systems and the Notes map on the Android app (notes' titles, features' health; views.py) |
| `calls.views_links` | `20000` | the most links on it (a book's "Seen in" links go first) |
| `calls.views_notes` | `5000` | most notes on the phone's Notes map (best linked first); lower it on a slow phone |
| `calls.voice` | `""` | a Gemini Live voice name (e.g. "Kore"); empty = Google's default |
| `calls.voice_by_kind` | `{}` | a voice per kind of call, e.g. {"alarm": "Puck"} |
| `calls.voice_by_model` | `{}` | a voice per Live model |
| `calls.voice_mode` | `"auto"` | how calls talk: auto uses Gemini Live and your phone's own speech if Live is down |
| `calls.worker.name` | `""` | your call line's name on Cloudflare (set when it's deployed) |
| `calls.worker.url` | `""` | your call line's address (set when it's deployed) |
| `calls.worker.version` | `""` | the version of the call line that's deployed (set by Kurooto) |

### `capture`

| Setting | Default | What it does |
|---|---|---|
| `capture.delay_min` | `2` | minutes after a class ends before it asks what happened |
| `capture.skip_subjects` | `[]` | never ask after these |
| `capture.study_log` | `true` | with Chat on, the AI writes one |
| `capture.subjects` | `[]` | ask only after these subjects' classes; empty: every subject |

### `cases`

| Setting | Default | What it does |
|---|---|---|
| `cases.button` | `true` | a Wrong button under replies to plain-English requests (/wrong works either way) |
| `cases.fallthroughs` | `true` | keep short requests no instant request understood (they went to the AI) |
| `cases.keep_days` | `0` | cases you didn't make test cases are forgotten after this many days (0: privacy.keep_days) |
| `cases.learn` | `true` | a test case may teach its phrasing (only if every test case that passed still passes) |
| `cases.learn_rephrased` | `true` | the same not-understood phrasing, twice followed by the same request: learn it |
| `cases.review` | `"weekly sun 19:00"` | when the look back may show the phrasings that came up most... |
| `cases.review_days` | `28` | ...at most this often (about once a month) |
| `cases.review_max` | `5` | phrasings in one look back |

### `checkins`

| Setting | Default | What it does |
|---|---|---|
| `checkins.ai_notes` | `true` | with Chat on: after a check-in call, the AI writes your journal and study logs |
| `checkins.asleep_defers` | `true` | by call, alarm set and you've gone to bed: the night check-in waits for the morning |
| `checkins.by_call` | `false` | with Phone calls on: the check-in is a call (a missed call falls back to Telegram) |
| `checkins.day_starts` | `"05:00"` | a check-in day runs from here to here: a night check-in at 00:30 is the evening's |
| `checkins.journal` | `true` | add each check-in's answer to your journal |
| `checkins.learn_times` | `true` | a check-in you keep moving or answering late moves to when you do it (with Undo) |
| `checkins.questions.evening` | `"How did today go? What got done, and what slipped?"` | the evening check-in's question |
| `checkins.questions.midday` | `"How's the morning been? Anything to re-plan for the afte…` | the midday check-in's question |
| `checkins.questions.night` | `"Before bed: anything else for your journal? What's first…` | the night check-in's question |
| `checkins.reflect` | `true` | the evening check-in lists up to 3 things today's records show you did, asks about tomorrow |
| `checkins.times.evening` | `"22:00"` | the evening check-in, the day in review (None: off) |
| `checkins.times.midday` | `null` | the midday check-in (None: off; e.g. "13:00") |
| `checkins.times.night` | `null` | the night check-in before bed (None: off; e.g. "23:15") |

### `classroom_notes`

| Setting | Default | What it does |
|---|---|---|
| `classroom_notes.at` | `"daily 07:00,13:00,19:00"` | when new Classroom posts are fetched |
| `classroom_notes.backfill_days` | `60` | posts older than this (and not edited since) are left alone; a longer window finds them |
| `classroom_notes.files` | `true` | download the Drive files attached to posts and read their text |
| `classroom_notes.folders` | `{}` | a course's exact name -> the notes folder you want it in (otherwise Kurooto picks one) |
| `classroom_notes.max_file_mb` | `30` | Classroom files bigger than this (MB) aren't downloaded |
| `classroom_notes.skip` | `[]` | courses to leave out: words from their names |

### `commitments`

| Setting | Default | What it does |
|---|---|---|
| `commitments.hooks` | `[]` | {"word": "gym", "hold": "calls" or "all", "minutes": 90}: "gym" alone starts that hold |
| `commitments.items` | `[]` | {"name": "gym", "days": ["mon", "wed"], "start": "18:00", "end": "19:00", "calls": true} |
| `commitments.no_calls` | `true` | no calls during a commitment (each one can opt out: /busy calls gym off) |

### `date_offers`

| Setting | Default | What it does |
|---|---|---|
| `date_offers.remind_min` | `60` | an event you tap Add on (a photo, mail, a shared calendar): reminded this long before |

### `deadlines`

| Setting | Default | What it does |
|---|---|---|
| `deadlines.call` | `true` | with Phone calls on, the six-hour nudge is a call (a message when no call fits before it) |
| `deadlines.exam_mode_days` | `14` | exam mode starts this many days before a quiz or exam (0: never) |
| `deadlines.from_calendar` | `true` | calendar events that look like deadlines or exams (with Calendar on) |
| `deadlines.from_photos` | `true` | Photo to dates: a photo with "dates" as its caption, its dates as buttons |
| `deadlines.from_term_note` | `true` | quizzes, exams and deadlines from the term note's key dates (Subjects: /term note) |
| `deadlines.horizon_days` | `30` | recurring quizzes become dated deadlines this far ahead |
| `deadlines.max_files` | `3000` | the most notes read when looking for deadlines |
| `deadlines.meeting_brief` | `"daily 20:00"` | the evening before a meeting with a project's person: a brief ("": off) |
| `deadlines.overdue_check` | `true` | after the due time: "Overdue?" with Done / New date / Drop |
| `deadlines.ping_h` | `24` | hours before the due time for a deadline's first nudge (one message; closer than urgent_h it's urgent) |
| `deadlines.plan_h` | `72` | "due soon": what's due this many hours ahead goes into the morning plan, /status and calls |
| `deadlines.recurring` | `true` | recurring quizzes from kurooto/recurring.md |
| `deadlines.scan_notes` | `true` | also find deadlines written in your notes |
| `deadlines.tick_notes` | `true` | Done ticks the "- [ ]" line in your notes when the deadline came from one |
| `deadlines.urgent_h` | `6` | a deadline closer than this many hours is urgent |

### `doubts`

| Setting | Default | What it does |
|---|---|---|
| `doubts.before_min` | `30` | open doubts come this long before the subject's next class |
| `doubts.recent_h` | `3` | a doubt naming no subject is for the class that's on, or ended this many hours ago |

### `drafts`

| Setting | Default | What it does |
|---|---|---|
| `drafts.max_comments` | `15` | at most this many comments on one draft |
| `drafts.note_block` | `true` | notes that are checked: the comments also go in a block in the matching lecture note |
| `drafts.recent_minutes` | `15` | "check this" after you sent a file checks that file if it came this recently |

### `dreaming`

| Setting | Default | What it does |
|---|---|---|
| `dreaming.consolidate` | `true` | duplicates and lines that disagree in what it remembers: Keep A / Keep B / Both true |
| `dreaming.consolidate_ai` | `"local"` | a second opinion on near misses: local (this computer), main (your AI), off |
| `dreaming.consolidate_max` | `3` | at most this many in one morning message; the rest wait for the next ones |
| `dreaming.curious` | `true` | a topic you asked about 3+ times this week with no note on it: one line, Make a stub |
| `dreaming.fold` | `true` | offer lasting things you said for your profile in the morning message (Keep / Not that) |
| `dreaming.fold_ai` | `"local"` | a second look at what the rules found: local (this computer), main (your AI), off |
| `dreaming.fold_max` | `3` | at most this many in one morning message; the rest wait for the next ones |
| `dreaming.loose_ends` | `true` | also the loose ends: your open doubts, unlinked notes, broken links, tasks past due |
| `dreaming.never_tune` | `["deadlines.reminder", "deadlines.call", "health.now", "a…` | kinds it never tunes (besides the alarm, your reminders and calls, deadlines under 12 hours) |
| `dreaming.propose_prompts` | `false` | propose a fix to a skill that keeps going wrong (Apply or No; never by itself) |
| `dreaming.resurface` | `true` | one line from the past: a note or quiz subject from 10-30 days ago, or an anniversary |
| `dreaming.self_check` | `true` | replay your test cases each morning and say which ones went wrong since yesterday |
| `dreaming.tune_effort` | `true` | each night, replay your requests and tune the effort they get (one change, Undo) |
| `dreaming.tune_fallbacks` | `true` | each night, replay every try per AI and tune which AI goes first at each effort |
| `dreaming.tune_margin` | `3.0` | how much better (in the replay's score) a change must be than leaving things as they are |
| `dreaming.tune_messages` | `true` | each night, replay the messages it sent you and tune when they come (one change, Undo) |
| `dreaming.tune_sizing` | `true` | each night, compare Start-by's sizes with the time deadlines took and tune them |
| `dreaming.when` | `"daily 07:30"` | when the morning message comes (it covers everything since the last one) |

### `drive_upload`

| Setting | Default | What it does |
|---|---|---|
| `drive_upload.big_files` | `true` | files over Telegram's 50 MB come as a Drive link instead of not at all |
| `drive_upload.folder` | `"Kurooto"` | the Google Drive folder files go to |
| `drive_upload.temp_days` | `7` | those links last this many days, then the file is deleted from your Drive (0: kept) |

### `exam_season`

| Setting | Default | What it does |
|---|---|---|
| `exam_season.alarm_check` | `true` | every night of the period: will tomorrow's alarm ring? |
| `exam_season.block_min` | `60` | one revision block, in minutes (one topic each) |
| `exam_season.budget` | `true` | only deadlines, quizzes and the alarm during the day; the rest waits for the evening bundle |
| `exam_season.debrief` | `true` | after each exam: a two-minute debrief, into the subject's course note |
| `exam_season.eve` | `true` | the evening before each exam: where is it, which seat, calculator, ID card? |
| `exam_season.eve_at` | `"18:00"` | ...asked from this time |
| `exam_season.exam_min` | `180` | how long an exam takes (no calls then; the debrief comes half an hour after) |
| `exam_season.hold_updates` | `true` | non-critical updates wait until the exams are over |
| `exam_season.leave_alarm` | `true` | on the exam day, an alarm to leave (a call with Phone calls on, else a message) |
| `exam_season.leave_min` | `45` | ...this long before the exam starts, unless you say a time ("leave 8:10") |
| `exam_season.night_at` | `"21:30"` | ...checked at this time |
| `exam_season.no_calls` | `true` | no calls during an exam |
| `exam_season.quiz_call_at` | `"19:00"` | the evening before an exam you picked a quiz call for |
| `exam_season.quizzes` | `false` | quizzes and tests outside an exam period count as exams too |
| `exam_season.revision` | `true` | before each exam, its course's topics ranked and laid into your free time (/revise) |
| `exam_season.revision_ask` | `true` | the evening: did you cover today's topics? (counts like a quiz answer) |
| `exam_season.revision_days` | `14` | the revision plan starts this many days before each exam |
| `exam_season.revision_share` | `50` | % of your free time (Start-by's, less commitments) revision blocks may take |

### `files`

| Setting | Default | What it does |
|---|---|---|
| `files.folder` | `""` | a folder for files outside your notes (course files, PDFs); empty: inside the notes |
| `files.links` | `""` | how notes link to files: empty is automatic |

### `gbrain`

| Setting | Default | What it does |
|---|---|---|
| `gbrain.agy_mcp` | `false` | your own GBrain: agy gets its MCP tools too (asked first) |
| `gbrain.checkup` | `false` | weekly checkup; a message only when something needs a look |
| `gbrain.checkup_ignore` | `["backup_", "mcp_", "chronicle", "auto_chronicle", "unins…` | checkup findings starting with these words aren't reported |
| `gbrain.checkup_line` | `true` | once a week, one line on how the notes brain is (its doctor, read only) |
| `gbrain.checkup_when` | `"weekly sun 19:30"` | when the weekly notes-brain checkup runs |
| `gbrain.contradictions` | `true` | its last contradictions report joins Dreaming's morning section (Keep A / Keep B) |
| `gbrain.course_pages` | `true` | nightly: each course page gets its key concepts and a dated timeline (Kurooto's block) |
| `gbrain.embeddings` | `"auto"` | where the notes brain gets its embeddings: auto, ollama, gemini or off |
| `gbrain.exe` | `""` | your own GBrain: your gbrain program; empty: the one on your PATH |
| `gbrain.home` | `""` | your own GBrain: its GBRAIN_HOME; empty: GBrain's default |
| `gbrain.managed` | `true` | Kurooto runs its own brain; False: your own GBrain (gbrain.exe, gbrain.home) |
| `gbrain.mcp_surface` | `"full"` | what that MCP server offers agy: full \| starter \| verbs |
| `gbrain.nightly` | `"daily 03:00"` | when the notes brain's nightly upkeep runs |
| `gbrain.source` | `""` | your own GBrain: the source that is your notes folder, kept in step (empty: you do that) |
| `gbrain.sync` | `"every 15m"` | how often notes are indexed |
| `gbrain.timelines` | `true` | nightly: dated log lines become timelines (no AI, nothing leaves the computer) |
| `gbrain.upkeep` | `false` | nightly upkeep, light steps only (heavy: waits for the charger) |
| `gbrain.upkeep_steps` | `[]` | the upkeep's steps (GBrain's phase names); empty: the light ones (UPKEEP_STEPS) |

### `google`

| Setting | Default | What it does |
|---|---|---|
| `google.accounts` | `["main"]` | your Google accounts by name; "main" is the first one you signed in with |
| `google.agent_calendar` | `false` | Kurooto's own "Agent plan" calendar |
| `google.calendar_read` | `false` | your calendars, read-only (Google Calendar) |
| `google.classroom` | `true` | read Classroom (courses, assignments, announcements) |
| `google.classroom_every` | `"every 3h"` | how often Classroom is checked for deadlines |
| `google.classroom_notes` | `false` | Classroom materials and attached Drive files (read-only) |
| `google.digest_email` | `false` | the mail digest emailed to yourself (send only) |
| `google.drive_upload` | `false` | files you send yourself, into a Kurooto folder in Drive (its own files only) |
| `google.endpoints.auth` | `"https://accounts.google.com/o/oauth2/v2/auth"` | Google's sign-in address (for tests and proxies; leave alone) |
| `google.endpoints.calendar` | `"https://www.googleapis.com/calendar/v3"` | Google Calendar's API address (leave alone) |
| `google.endpoints.classroom` | `"https://classroom.googleapis.com/v1"` | Google Classroom's API address (leave alone) |
| `google.endpoints.drive` | `"https://www.googleapis.com/drive/v3"` | Google Drive's API address (leave alone) |
| `google.endpoints.drive_upload` | `"https://www.googleapis.com/upload/drive/v3"` | Google Drive's upload address (leave alone) |
| `google.endpoints.gmail` | `"https://gmail.googleapis.com/gmail/v1"` | Gmail's API address (leave alone) |
| `google.endpoints.token` | `"https://oauth2.googleapis.com/token"` | noqa: S105 (an address) |
| `google.gmail_drafts` | `false` | save drafts in Gmail (asked for separately: Google calls it a restricted permission) |
| `google.mail_digest` | `false` | read Gmail (read-only) |
| `google.reply_drafts` | `false` | reply drafts in Gmail, sent only when you tap Send |
| `google.use` | `{}` | which signed-in Google account each feature uses (Settings → Google) |

### `google_calendar`

| Setting | Default | What it does |
|---|---|---|
| `google_calendar.skip` | `[]` | calendar names (any part of them, any case) to leave out |

### `handwritten`

| Setting | Default | What it does |
|---|---|---|
| `handwritten.cloud` | `true` | with no model here, Gemini (your key) reads them; False: they wait for a model here |
| `handwritten.dpi` | `110` | how sharp the page pictures are |
| `handwritten.every` | `"every 15m"` | how often the handwritten-notes folder is checked |
| `handwritten.folder` | `""` | where scans land; empty = handwritten-inbox in your notes (or in your files folder) |
| `handwritten.into` | `""` | where the notes go, inside your notes folder; empty = your notes layout's (handwritten/) |
| `handwritten.keep_original` | `"copy"` | copy (next to the note, or in files.folder) \| link (leave it where it is) |
| `handwritten.link` | `true` | link each written-out note to its lecture, course page and concept notes (one AI request) |
| `handwritten.local` | `true` | a model on this computer reads the pages when there is one (photos and PDFs) |
| `handwritten.local_model` | `""` | an Ollama model of your choice that reads pictures; empty: Local models' pick |
| `handwritten.max_pages` | `60` | pages written out per PDF |
| `handwritten.model` | `"gemini-flash-latest"` | the Gemini model that reads handwriting when it's chosen |
| `handwritten.pdf_hours` | `"23:00-07:00"` | when the model here reads PDFs (on the charger); "" any time |

### `hardware`

| Setting | Default | What it does |
|---|---|---|
| `hardware.extra_models` | `[]` | Ollama models of your own to install, e.g. ["gemma4:12b"], past what suits this computer |
| `hardware.extra_prereqs` | `[]` | other programs Kurooto should install for you (their ids, e.g. "tesseract") |
| `hardware.force_profile` | `""` | another setup than detected: light, apple-8, apple, small-gpu, big-gpu, big-gpu-12 |

### `health`

| Setting | Default | What it does |
|---|---|---|
| `health.auto_fix` | `true` | try a safe fix before telling you (never sync: that one waits for your tap) |
| `health.on` | `true` | the daily pass (doctor, the dashboard and /health always check) |
| `health.when` | `"daily 21:00"` | before bedtime: tonight's alarm is checked then |

### `infer`

| Setting | Default | What it does |
|---|---|---|
| `infer.aliases` | `true` | "by POTA I mean Physics of the Atmosphere": a short name for that subject |
| `infer.classes` | `true` | "every Monday at 9 I have a <subject> lab": a class in the timetable |
| `infer.commitments` | `true` | "every Tuesday at 7pm I go to the gym": a commitment (it holds calls like a class) |
| `infer.meetings` | `true` | "met X today": a dated line in that project's Meetings; a meeting ahead: a deadline |
| `infer.on` | `true` | set things up from what you say in the chat and the journal (one line each, with Undo) |
| `infer.projects` | `true` | "I got a project under Prof X": a project note with them, and a Meetings section |
| `infer.quizzes` | `true` | "there's a quiz on Linear Algebra every Monday": a row in the recurring quizzes table |
| `infer.short_names` | `true` | "LA" for Linear Algebra after two messages call it that (it fits only that one) |
| `infer.sweep` | `true` | one pass over your chats and journal: once when first on, then nightly on what's new |
| `infer.sweep_ai` | `"local"` | a line the rules can't read: local (this computer) restates it, main (your AI), off |
| `infer.sweep_days` | `30` | how far back that first pass reads |

### `integrate`

| Setting | Default | What it does |
|---|---|---|
| `integrate.at` | `"daily 01:30"` | when the night's integration starts (it carries on batch after batch) |
| `integrate.batch_pages` | `12` | about this many pages per request |
| `integrate.commit` | `true` | one git commit per batch, when your notes are a repository |
| `integrate.duplicates` | `true` | each morning, up to 3 pairs of look-alike concept notes: Merge / Keep both / Add alias |
| `integrate.embeddings` | `"auto"` | where meaning-based matching comes from: auto \| ollama \| gemini \| off |
| `integrate.first` | `[]` | subjects to do first, e.g. ["deep-learning"] |
| `integrate.garden` | `true` | each day, a second pass over the notes the reading touched and notes nothing links to |
| `integrate.garden_per_day` | `40` | the most notes in that pass |
| `integrate.max_cost_per_night` | `0.5` | an API key: the most a night's reading may cost (USD, as the service reports it) |
| `integrate.notation` | `true` | a Notation table when a second source writes a concept differently (a switch on the card) |
| `integrate.order` | `"smallest"` | which books first: smallest (fewest pages: most books done soonest) \| name |
| `integrate.per_night` | `"auto"` | batches a night: auto (fitted to your AI's plan by itself) or a number (a hard ceiling) |
| `integrate.price_per_mtok.in` | `2.0` | an API key that reports no cost: its USD per million tokens |
| `integrate.price_per_mtok.out` | `8.0` | an API key that reports no cost: its USD per million tokens |
| `integrate.rerank` | `"auto"` | a local model judges which notes belong together (a graphics card helps): auto \| off |
| `integrate.rerank_model` | `""` | which one ("": the helper model of this computer's setup) |
| `integrate.roles.bulk` | `""` | the AI for the bulk work and for the second look ("": chosen for you) |
| `integrate.roles.check` | `""` | the AI for the bulk work and for the second look ("": chosen for you) |
| `integrate.share_pct` | `60` | a subscription's usage window (or a free key's day): the most of it reading takes |
| `integrate.sources` | `["books", "classroom"]` | what's read into the graph: books, classroom (filed files), handwritten |
| `integrate.summary` | `true` | one line each morning about what changed |

### `jobs`

| Setting | Default | What it does |
|---|---|---|
| `jobs.plan_line` | `true` | a short "Searching your notes, then answering" first, when a text answer will take 20 s+ |
| `jobs.receipt` | `true` | a quiet last line under each answer: which AI, effort, time, limit used, what it did |
| `jobs.stuck_min` | `10` | the watchdog: minutes with no AI at work and no program running |

### `keep`

| Setting | Default | What it does |
|---|---|---|
| `keep.ask` | `true` | day 10, then monthly: Keep / Quiet / Off for features you don't use |

### `learning`

| Setting | Default | What it does |
|---|---|---|
| `learning.brain` | `""` | the AI that looks at finished work ("": the concept graph's second-look AI, else your main one) |
| `learning.corrections` | `true` | a skill learns a lesson when you correct its answer |
| `learning.remember` | `true` | the nightly look back keeps facts you stated in your chats and calls (how-to-help note) |
| `learning.remember_max` | `3` | facts kept a night, at most |
| `learning.search` | `true` | a search index of past requests, calls and chats on this computer: /history, search_history |
| `learning.skill_min_steps` | `5` | tool uses a request needs before it's looked at as a possible skill |
| `learning.skills` | `true` | a request that took many steps can become a skill (or improve the one that does it) |

### `lidsafe`

| Setting | Default | What it does |
|---|---|---|
| `lidsafe.hours` | `24` | how far ahead your call line holds things (12 to 24) |
| `lidsafe.morning` | `"07:30"` | the time the lid-shut safeguard looks for in the morning |
| `lidsafe.reminders` | `true` | your reminders |
| `lidsafe.today` | `true` | a morning line on your phone: the day's first class and what's due that day |

### `local_helper`

| Setting | Default | What it does |
|---|---|---|
| `local_helper.hold_h` | `24` | a request waits this many hours for the connection, then says it couldn't run |
| `local_helper.max_s` | `1.5` | its speed test: a one-word answer must come within this many seconds, or it stays off |
| `local_helper.model` | `""` | its Ollama model; empty: the one in ollama_models.toml (cpu-helper, about 1 GB) |
| `local_helper.offer` | `true` | after two weeks, offer it once when the free AI limit runs short or the internet often drops |
| `local_helper.offline` | `true` | with the internet down: quick things answered here, AI requests wait until it's back |
| `local_helper.on` | `false` | the offline helper: a small model on this computer for quick decisions (/helper on sets it up) |
| `local_helper.timeout_s` | `4` | a quick decision waits this long for it, then the rules decide |

### `look`

| Setting | Default | What it does |
|---|---|---|
| `look.design` | `"new"` | the dashboard's design: new, or classic (the monospace look of 0.5.18) |
| `look.hidden_features` | `[]` | features hidden from the Features list (they still run if on) |
| `look.layout` | `"dense"` | dense (everything on one board) or roomy |
| `look.links_in` | `"default"` | where links open: default is your default browser |
| `look.palette` | `"kuro"` | the pages' colours (core/palette.py, themes.py) |
| `look.panes` | `[]` | the dense board's hidden panes: status, systems, notes, terminal (empty: none hidden) |
| `look.projects` | `[]` | folders of git repositories the PROJECTS box shows (empty: Research's repositories) |
| `look.study_mode` | `false` | the dashboard in Study mode: the notes map, the study timer and what's due (Alt+M, /study mode) |
| `look.theme_file` | `""` | the pages' colours (core/palette.py, themes.py) |

### `mail_digest`

| Setting | Default | What it does |
|---|---|---|
| `mail_digest.at` | `"daily 08:00,18:00"` | when mail digests run |
| `mail_digest.confidential` | `"count"` | what to do with confidential mail: count, hide or skip |
| `mail_digest.confidential_words` | `["confidential", "do not forward", "restricted", "private…` | regular expressions, any case; a space matches any run of spaces or line breaks |
| `mail_digest.first_days` | `3` | the first digest looks this far back |
| `mail_digest.local_model` | `""` | which Ollama model reads it; empty: Local AI models' helper model |
| `mail_digest.mail_in` | `false` | Email in: mail to you+kurooto@ (or labelled) filed into notes, dates as buttons |
| `mail_digest.mail_in_anyone` | `false` | True: mail to +kurooto from anyone goes in (a stranger could write into your notes) |
| `mail_digest.mail_in_every` | `"every 10m"` | how often it looks for mail sent in |
| `mail_digest.mail_in_label` | `""` | a Gmail label whose mail goes in too, from anyone (you put it on, or a Gmail filter) |
| `mail_digest.mail_in_senders` | `[]` | your other addresses whose mail to +kurooto goes in (your own address always does) |
| `mail_digest.max_messages` | `200` | per check |
| `mail_digest.never_read` | `[]` | senders, @domains or label:Name the digest never reads, even if chosen above |
| `mail_digest.own_domain` | `true` | on a school or work account, mail from your own domain is read too |
| `mail_digest.query` | `""` | an extra Gmail search the digest is limited to |
| `mail_digest.read` | `[]` | what the digest may read: "label:Courses", "sam@example.org", "@school.example" |
| `mail_digest.save_note` | `true` | a copy of each digest in your notes (mail/<date>-<time>.md, or your notes layout's place) |
| `mail_digest.skip_confidential` | `true` | don't summarise mail marked confidential |

### `meetings`

| Setting | Default | What it does |
|---|---|---|
| `meetings.after_h` | `3` | hours after a meeting's start that a voice note or a long typed note counts as notes from it |
| `meetings.minutes` | `true` | notes you send after a meeting with a project's person become minutes through your AI |

### `memory`

| Setting | Default | What it does |
|---|---|---|
| `memory.budget_tokens` | `600` | at most about this much of what's remembered goes with one AI reply or call |
| `memory.recall` | `true` | AI replies and calls are told the few remembered items your message refers to |
| `memory.thread_days` | `7` | an open thread nobody touched closes by itself after this many days |
| `memory.threads` | `true` | what you say you'll do (in chats and on calls) and tasks you start become open threads |

### `modules`

| Setting | Default | What it does |
|---|---|---|
| `modules.enabled` | `[]` | the features that are on (the Features list changes it) |

### `notes`

| Setting | Default | What it does |
|---|---|---|
| `notes.layout` | `"kurooto"` | how your notes are laid out: kurooto or zettelkasten |
| `notes.links` | `"wiki"` | how Kurooto links notes: "wiki" ([[path\|Name]]) or "markdown" ([Name](path.md), relative) |
| `notes.open_with` | `""` | the program that opens a note from the dashboard; empty: the system's |
| `notes.paths` | `{}` | your own folder for a kind of note, e.g. {"daily": "journal/{date}.md"} |

### `notes_sync`

| Setting | Default | What it does |
|---|---|---|
| `notes_sync.after_jobs` | `2` | minutes after an AI request finishes, its notes are sent up (0: wait for the timer) |
| `notes_sync.api` | `"https://api.github.com"` | the Git host's API address (leave alone) |
| `notes_sync.branch` | `"main"` | the branch your notes sync to |
| `notes_sync.every` | `"every 10m"` | how often notes sync |
| `notes_sync.on_conflict` | `"keep both"` | "keep both": a clashing note keeps both versions; "stop": sync waits for you |
| `notes_sync.remote` | `""` | tests: a local repository instead of GitHub |
| `notes_sync.repo` | `""` | owner/name |
| `notes_sync.share_with_calls` | `true` | your call line may read notes from the repository while this computer is off |

### `notify`

| Setting | Default | What it does |
|---|---|---|
| `notify.app_chat` | `false` | Kurooto's own messages (not app_kinds) also go to the app's chat; always without Telegram |
| `notify.app_kinds` | `["call", "question", "approval"]` | which messages also reach your phone app |
| `notify.calm.calls` | `1` | calls a day that come by themselves (the alarm and calls you asked for don't count) |
| `notify.calm.evening` | `[]` | kinds that always wait for the evening bundle (Less of this → Another time) |
| `notify.calm.evening_at` | `"20:00"` | the evening bundle: what waited today |
| `notify.calm.fewer` | `{}` | kind -> at most this many a day; more wait for the evening (Less of this → Fewer) |
| `notify.calm.habituate` | `{}` | kind -> after this many in a row unanswered, they wait for the evening until you answer |
| `notify.calm.lighter_after` | `true` | after an exam or a heavy day: a lighter next day |
| `notify.calm.messages` | `6` | messages a day that come by themselves; more wait for the evening bundle |
| `notify.calm.monthly` | `true` | once a month: a kind of question you rarely answer, and whether to turn it off |
| `notify.calm.on` | `true` | reasons, Why? and Less of this, the daily limit; off: everything comes as it always did |
| `notify.calm.stopped` | `[]` | kinds stopped with Less of this (when their feature has no setting of its own) |
| `notify.calm.windows` | `{}` | kind -> "10:00-18:00": outside these hours they wait for the evening bundle |
| `notify.desktop` | `true` | show notifications on this computer |
| `notify.desktop_kinds` | `["call", "question", "approval", "deadline", "update"]` | which messages show on this computer |
| `notify.presence.after_min` | `10` | away for less than this: nothing is said |
| `notify.presence.channels` | `["telegram"]` | where: "telegram", "app" (the phone app) |
| `notify.presence.line` | `true` | your call line says so when this computer can't (sleep, a crash, a lost network) |
| `notify.presence.line_telegram` | `null` | may your call line keep your bot's token for that? None: asked once |
| `notify.presence.on` | `true` | say when Kurooto goes offline and when it's back |

### `overlay`

| Setting | Default | What it does |
|---|---|---|
| `overlay.code` | `true` | also run the Python add-ons in its modules/ (False: only skills, prompts and settings) |
| `overlay.path` | `""` | your add-ons folder (full path) |

### `persona`

| Setting | Default | What it does |
|---|---|---|
| `persona.avoid` | `""` | persona card: things to avoid, e.g. "emojis, exclamation marks, motivational lines" |
| `persona.boundaries` | `true` | health, relationship and money decisions: not Kurooto's to make; it points to a person |
| `persona.call_me` | `""` | persona card: what the AI calls you (empty: your name, or nothing) |
| `persona.length` | `""` | persona card: how long answers should be, e.g. "short unless I ask for detail" |
| `persona.register` | `true` | a short message gets a short answer, a voice note a spoken-style one (by length only) |
| `persona.tone` | `""` | persona card: the tone you want, e.g. "plain and direct, no pep talk" |

### `power`

| Setting | Default | What it does |
|---|---|---|
| `power.on_battery` | `"saver"` | saver \| normal \| pause |

### `privacy`

| Setting | Default | What it does |
|---|---|---|
| `privacy.allow_hosts` | `[]` | more hosts Kurooto may reach, e.g. ["feeds.example.org"]; ".example.org" for all of it |
| `privacy.egress` | `"record"` | record (count every request), enforce (also refuse hosts not on the list), off |
| `privacy.gist_days` | `0` | gists go after this many days (0: kept for good, until you /forget all) |
| `privacy.gist_model` | `false` | a model on this computer (Local AI models) adds a sentence to a call's gist |
| `privacy.keep_days` | `0` | transcripts, AI requests and answers, chats and logs go after this many days (0: kept) |
| `privacy.keep_gist` | `true` | as a conversation's words fade, it settles into one line of what it decided (/gists) |

### `profile`

| Setting | Default | What it does |
|---|---|---|
| `profile.after_changes` | `10` | minutes after you change a setting (or turn a feature on or off), it's saved |
| `profile.branch` | `"(computed)"` | the branch your saved profile lives on (set by Kurooto) |
| `profile.remote` | `""` | tests: a local repository instead of GitHub |
| `profile.repo` | `""` | owner/name of a private GitHub repository; empty: the one Notes sync uses |
| `profile.when` | `"daily 04:40"` | when your profile is saved |

### `projects`

| Setting | Default | What it does |
|---|---|---|
| `projects.check_timeout_s` | `300` | a check is stopped after this many seconds |
| `projects.checks` | `{}` | project name -> the command that checks it (its tests, a LaTeX build); none until you set one |
| `projects.effort` | `"high"` | how hard the AI thinks about project work (low, medium, high, auto) |
| `projects.folders` | `{}` | project name -> folder, for more projects of yours (/project add <folder> keeps its own list) |
| `projects.help` | `[]` | the projects the AI may help with (/project help on <name>); none until you say so |

### `proposals`

| Setting | Default | What it does |
|---|---|---|
| `proposals.inline_lines` | `30` | a diff up to this many lines comes inside the message; a longer one as a file |
| `proposals.keep_days` | `7` | a proposal nobody answered goes after this many days, with its scratch folder |
| `proposals.max_files` | `60` | nor one that touches more files than this |
| `proposals.max_kb` | `400` | a bigger change isn't proposed (ask for a smaller part) |
| `proposals.morning` | `"daily 07:30"` | the night's proposals, told then when Dreaming is off (else in Dreaming's message) |
| `proposals.notes_edits` | `true` | a change to text already in your notes becomes a proposal (Apply / Change / Discard) |

### `quests`

| Setting | Default | What it does |
|---|---|---|
| `quests.days` | `7` | how long the first week lasts |
| `quests.when` | `"daily 18:00"` | the day's quest |

### `quiz`

| Setting | Default | What it does |
|---|---|---|
| `quiz.by_call` | `false` | /quiz, "quiz me" and quiz check-ins ring you (with Phone calls on); "here" keeps text |
| `quiz.call_min` | `10` | how long a quiz call is meant to take |
| `quiz.exam_daily` | `""` | in exam mode: a practice check-in every day at this time, e.g. "18:00" (empty: never) |
| `quiz.exam_per_session` | `6` | in exam mode |
| `quiz.links` | `false` | link recall cards from the concept graph's links come by themselves (/card works anyway) |
| `quiz.links_at` | `"daily 11:00,16:00,20:00"` | when one may come (never in a class, focus time or the night) |
| `quiz.links_check` | `false` | a local model (Local AI models) says how close your answer came; never a cloud AI |
| `quiz.links_per_day` | `3` | the most link cards a day (at most 5) |
| `quiz.offer_at` | `"19:00"` | the evening before a quiz or exam: offer practice from this time (empty: never) |
| `quiz.per_session` | `3` | questions per quiz |

### `quota`

| Setting | Default | What it does |
|---|---|---|
| `quota.background_pct` | `70` | the share of an AI's daily free limit background work may use |
| `quota.limits` | `{}` | your own limits per AI, e.g. {"agy": 200} |
| `quota.local` | `"quick"` | what the model on this computer does for the free limit: quick, background or off |
| `quota.on` | `true` | keep part of the free AI limit for what you're waiting on |

### `remember`

| Setting | Default | What it does |
|---|---|---|
| `remember.recheck_days` | `90` | a kept line that hasn't come up in this many days gets one "Still true?" (0: never) |

### `reminders`

| Setting | Default | What it does |
|---|---|---|
| `reminders.places` | `false` | location reminders: "remind me when I reach the library to …" (needs the Android app) |

### `repair`

| Setting | Default | What it does |
|---|---|---|
| `repair.on` | `true` | two close readings of a request: ask which, with both as buttons |

### `reply_drafts`

| Setting | Default | What it does |
|---|---|---|
| `reply_drafts.ask_days` | `3` | days between asking whether drafted replies were useful |
| `reply_drafts.per_day` | `5` | the most reply drafts per day |

### `repo_projects`

| Setting | Default | What it does |
|---|---|---|
| `repo_projects.github_extras` | `true` | with gh signed in: description, topics, open issues and milestones, read through gh |
| `repo_projects.max_mb` | `50` | the most of a cloned repository's files checked out to be read (MB); its history isn't counted |
| `repo_projects.on` | `true` | /project add and "set up my project from github.com/..." set a project up from its repository |
| `repo_projects.refresh` | `true` | nightly, each watched repository's README, docs, releases and milestones are looked at again |
| `repo_projects.refresh_at` | `"daily 04:20"` | when that runs (from Research, so Research has to be on) |

### `research`

| Setting | Default | What it does |
|---|---|---|
| `research.about` | `""` | what you work on, in a sentence or two: the AI uses it to pick |
| `research.endpoints.arxiv` | `"https://export.arxiv.org/api/query"` | arXiv's API address (leave alone) |
| `research.endpoints.biorxiv` | `"https://api.biorxiv.org/details"` | bioRxiv's API address (leave alone) |
| `research.endpoints.pubmed` | `"https://eutils.ncbi.nlm.nih.gov/entrez/eutils"` | PubMed's API address (leave alone) |
| `research.feeds` | `[]` | [{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}, {"type": "rss", "url": ...}, ...] |
| `research.idle_days` | `4` | ask about a project after this many days without commits (0: never) |
| `research.idle_when` | `"daily 18:00"` | when that's checked |
| `research.log_when` | `"daily 23:30"` | when commits are written into your project logs |
| `research.max_papers` | `8` | the most papers in a digest |
| `research.papers` | `"weekly mon 08:00"` | when the digest comes, e.g. "daily 08:00" or "weekly fri 17:00" |
| `research.projects` | `{}` | repository folder -> project name (its notes: research/<project>/); unset: the folder's name |
| `research.rank` | `true` | with Chat on, the AI picks and says why; off: the newest, as they are |
| `research.remind_by_call` | `true` | "Remind me tomorrow" is a call at 18:00 when Phone calls is on |
| `research.repo_runs` | `"runs"` | the folder in each repository where scripts keep their runs (its index.csv); "": none |
| `research.repos` | `[]` | folders of git repositories on this computer |
| `research.save_note` | `false` | also keep each digest as a note in your inbox (inbox/papers-<date>.md) |
| `research.topics` | `[]` | older setting: plain keywords searched across all of arXiv (still works) |
| `research.window_days` | `7` | how far back each digest looks |
| `research.zotero` | `"auto"` |  |
| `research.zotero_links` | `true` | your notes that link a paper you put in Zotero get a link to its Zotero item |

### `research_addon`

| Setting | Default | What it does |
|---|---|---|
| `research_addon.latex` | `true` | the LaTeX tracker: a nightly build of the folders you attach with /latex add |
| `research_addon.latex_morning` | `"daily 08:00"` | the one morning line (only when a build broke or you wrote something) |
| `research_addon.latex_repos` | `[]` | [{"path": folder, "main": "main.tex"}]: only folders you attached with /latex add |
| `research_addon.latex_timeout_min` | `15` | a build that takes longer is stopped and counts as an error |
| `research_addon.latex_when` | `"daily 03:30"` | when the nightly LaTeX build runs |
| `research_addon.members_off` | `[]` | features of the bundle you switched off on its card (they stay off when it's turned on) |
| `research_addon.run_compare` | `true` | Run compare: /runs and `kurooto runlog diff A B` (a part of the Research add-on) |

### `retro`

| Setting | Default | What it does |
|---|---|---|
| `retro.fixes` | `true` | make data fixes it is sure of (two copies of one deadline become one), with Undo |
| `retro.journal` | `true` | read today's journal note |
| `retro.max_proposals` | `3` | the most changes one look back proposes (it runs at retro.when: nightly by default) |
| `retro.no_days` | `30` | how long a "No" keeps that idea away |
| `retro.observe_days` | `7` | how long "Observe longer" (and /observe without a length) watches |
| `retro.routine_weeks` | `3` | on this many different weeks |
| `retro.routines` | `true` | propose a routine it sees in the records (the same thing at the same time, 3+ weeks) |
| `retro.transcripts` | `true` | read today's call transcripts |
| `retro.when` | `"daily 23:50"` | "weekly sun 21:00" looks back over the whole week instead |

### `skills`

| Setting | Default | What it does |
|---|---|---|
| `skills.auto_pack` | `"ask"` | the evening before a quiz or exam: ask (a button) \| auto (build it) \| off |
| `skills.auto_pack_after` | `"16:00"` | not before this time of day, 12 to 36 hours before it |

### `sorter`

| Setting | Default | What it does |
|---|---|---|
| `sorter.ai` | `true` | ask your AI about a note the rules can't place (its first lines go to it); off: rules only |
| `sorter.at` | `"daily 03:30"` | when the nightly pass runs |
| `sorter.folder` | `"inbox"` | the scratch folder, inside your notes: what lands here is sorted |
| `sorter.learn` | `true` | a note you move again after it filed it teaches it |
| `sorter.min_conf` | `0.75` | how sure a guess must be before it's acted on |
| `sorter.per_night` | `20` | the most notes moved in a day |
| `sorter.recheck` | `true` | weekly: a note it moved that now clearly fits another folder moves once more |
| `sorter.settle_min` | `10` | a note touched in the last this-many minutes is left (you may still be writing it) |

### `sources`

| Setting | Default | What it does |
|---|---|---|
| `sources.budget` | `24000` | characters in all |
| `sources.cap.book` | `12000` | characters at most from each source |
| `sources.cap.classroom` | `10000` | characters at most from each source |
| `sources.cap.own` | `12000` | characters at most from each source |
| `sources.mix` | `"(computed)"` | the source mix for books and notes: how much each kind counts in answers |
| `sources.prefer` | `[]` | an order instead of the mix: ["own", "book", "classroom"] |
| `sources.subjects` | `{}` | per subject: {"<slug>": {"mix": {...}} or {"prefer": [...]}, optionally "cap"} |

### `space`

| Setting | Default | What it does |
|---|---|---|
| `space.backups_max_age_days` | `0` | zips older than this go (0: no limit; backups.keep still applies) |
| `space.backups_max_gb` | `3.0` | the most the backup zips may take in total (0: no limit) |
| `space.cache_days` | `14` | downloads, made zips and cut-off downloads older than this go |
| `space.jobs_days` | `60` | finished AI requests older than this are forgotten |
| `space.log_mb` | `20` | a log file bigger than this is cut to its newest part |
| `space.undo_days` | `30` | the concept graph's before-copies and unfinished work files older than this go |
| `space.when` | `"weekly sun 04:30"` | when the Space keeper cleans by itself |

### `startby`

| Setting | Default | What it does |
|---|---|---|
| `startby.ask_exams` | `true` | ask once per subject how long its exams take to prepare for |
| `startby.crunch_weeks` | `4` | the Sunday summary looks this many weeks ahead (0: no crunch weeks) |
| `startby.exam_by_subject` | `{}` | {"linear-algebra": 25}: hours to prepare for that subject's exams (else sizes.exam) |
| `startby.horizon_days` | `35` | deadlines due this far ahead get a start-by date |
| `startby.learn_window` | `true` | once a week, move the window to when you're actually up (unless you set it) |
| `startby.min_gap_min` | `30` | shorter gaps between classes and events don't count |
| `startby.negotiate` | `true` | a reminder that would repeat for a slipping deadline: a reshaped plan instead, once a day |
| `startby.share` | `40` | % of the free time in that window that goes to deadlines |
| `startby.sizes.exam` | `10` | days an exam takes to prepare for |
| `startby.sizes.other` | `2` | days other work takes |
| `startby.sizes.problem_set` | `3` | days a problem set takes |
| `startby.sizes.quiz` | `2` | days a quiz takes to prepare for |
| `startby.sizes.report` | `12` | days a report takes |
| `startby.tell` | `true` | a message on a start-by day (only two days or more before the due date) |
| `startby.when` | `"daily 08:00"` | the day's "Time to start" messages (they wait out quiet hours) |
| `startby.window` | `"09:00-22:00"` | the part of each day free time is counted in |

### `study`

| Setting | Default | What it does |
|---|---|---|
| `study.break_min` | `5` | Study mode's timer: minutes of break after each focus |
| `study.daily_note` | `"23:45"` | the day's hours go into your daily note at this time; None = don't |
| `study.focus_min` | `25` | Study mode's timer: minutes of focus (calls and messages wait; the time is logged) |
| `study.idle_min` | `5` | minutes without activity before study time stops counting |
| `study.keywords` | `{}` | {subject slug: [words]} |
| `study.research_paths` | `[]` | words or folders: a window naming one counts as Research |
| `study.sample_s` | `30` | seconds between looks at the active window |
| `study.timer_ends_mode` | `false` | when a focus ends, Study mode ends too (look.study_mode), instead of a break |

### `subjects`

| Setting | Default | What it does |
|---|---|---|
| `subjects.catch_up` | `true` | a class you missed gets a catch-up task and a lecture note (see the notes above) |
| `subjects.exam_periods` | `[]` | [["2026-12-07", "2026-12-18"], ...]: no classes then (exams instead) |
| `subjects.holidays` | `[]` | ["2026-12-25", ...]: no classes those days |
| `subjects.list` | `[]` | your subjects: name, short names, folder |
| `subjects.margin_min` | `5` | minutes around a class when calls are held |
| `subjects.no_calls_in_class` | `true` | no calls during a class |
| `subjects.term_ends` | `""` | "2026-12-04": the last day of classes; none after it |
| `subjects.term_note` | `""` | the note that holds your term's dates and timetable |
| `subjects.timetable` | `[]` | your weekly classes |

### `telegram`

| Setting | Default | What it does |
|---|---|---|
| `telegram.allowed_users` | `[]` | Telegram accounts that may use the bot (set when you pair) |
| `telegram.api_base` | `"https://api.telegram.org"` | Telegram's API address (leave alone) |
| `telegram.chat_id` | `null` | your chat with the bot (set when you pair) |
| `telegram.menu` | `true` | the bot's "/" menu follows the features you have on |
| `telegram.silent_kinds` | `["call"]` | message kinds sent without a sound |

### `terminal`

| Setting | Default | What it does |
|---|---|---|
| `terminal.default` | `false` | Kurooto Terminal as your default terminal (opt-in; turning it off undoes it) |
| `terminal.default_opens` | `"shell"` | as the default terminal, a launch opens: "shell" (one tab) or "layout" (all) |
| `terminal.font_size` | `11` | the Kurooto Terminal's font size |
| `terminal.kitty` | `true` | Linux and macOS: kitty (yours, or Kurooto's copy); off: your usual terminal, a window a tab |
| `terminal.shell` | `"auto"` | auto: fish if you have it, otherwise your own shell (PowerShell on Windows); or a name |
| `terminal.tabs` | `["agent", "shell", "chat", "logs"]` | in order; agent = your AI's own program, when it's installed |
| `terminal.top` | `"left"` | kurooto top: "left" (a column beside the first tab), "tab" (a tab of its own) or "off" |

### `turnon`

| Setting | Default | What it does |
|---|---|---|
| `turnon.offer` | `true` | a request a feature that's off understands: offer to turn it on |

### `updates`

| Setting | Default | What it does |
|---|---|---|
| `updates.channel` | `"stable"` | stable, or beta for earlier versions |
| `updates.exam_hold` | `true` | with staged on: nothing installs in an exam period or within a day of a quiz or exam |
| `updates.mode` | `"night"` | night (update by itself), ask (Telegram question) or off |
| `updates.staged` | `false` | wait until a release has been out wait_hours, and not during exams (critical ones don't) |
| `updates.wait_hours` | `48` | hours a new version waits before it's installed |
| `updates.window` | `["03:00", "05:00"]` | the hours the automatic update may run |

### `voice_notes`

| Setting | Default | What it does |
|---|---|---|
| `voice_notes.api_base` | `""` | a different address for the voice-note model (empty: Google's) |
| `voice_notes.model` | `"gemini-flash-latest"` | the Gemini model that turns voice notes into text |

### `web`

| Setting | Default | What it does |
|---|---|---|
| `web.port` | `8770` | the dashboard's port on this computer |

### `weekly`

| Setting | Default | What it does |
|---|---|---|
| `weekly.call` | `false` | with Phone calls on: also a Sunday review call after the summary |
| `weekly.people` | `true` | a line about who you met and meet next, only from your project notes' logged meetings |
| `weekly.when` | `"weekly sun 19:00"` | when the week's summary comes ("weekly <day> HH:MM") |

### `you`

| Setting | Default | What it does |
|---|---|---|
| `you.assistant_name` | `"Kurooto"` | the name your assistant goes by in messages |
| `you.language` | `"follow"` | answer in the language you write in |
| `you.name` | `""` | what Kurooto calls you |
| `you.timezone` | `""` | IANA name, e.g. Europe/Berlin; empty = this computer's |
| `you.workspace` | `""` | your notes folder; empty = Documents/Kurooto |
