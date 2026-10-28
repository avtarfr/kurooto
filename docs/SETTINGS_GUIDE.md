# Settings guide (the table)

Every setting Kurooto has, its default and what it does, in one table. This file is written by
`tools/gen_settings_guide.py` from the code, so it is complete. Each setting's full entry (what it does, its values,
when you'd change it, what it costs or sends, what it depends on) is in the user wiki's
[Settings guide](wiki/user/settings-guide.md), grouped by feature; the link after each line goes there.

## Where settings live, and how to change one

- **The dashboard:** Settings (Alt+S), grouped by feature, with a search box: the core sections (you, notify,
  availability, updates, brain, ask, look, power, notes, files) and the features that are on. Each setting shows what
  it does under its name; click that line for its whole guide entry. Changes apply at once; most are read again the
  next time they're used. A few are read only when Kurooto starts (such as `web.port`): for those, restart it with
  `kurooto stop`, then `kurooto start`. The other core sections (such as `health` and `sources`) aren't on that page
  yet: change them in the file.
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
| `addons.official_updates` | `true` | Say once when a newer version of an official add-on you have is out; it's never updated by itself. ([guide](wiki/user/settings-guide.md#addonsofficialupdates)) |
| `addons.on` | `true` | Load the add-ons you added by link (`kurooto addons add`); off, none load from the next start. ([guide](wiki/user/settings-guide.md#addonson)) |

### `agent_plan`

| Setting | Default | What it does |
|---|---|---|
| `agent_plan.name` | `"Agent plan"` | The name of Kurooto's own calendar for the time blocks it plans with you. ([guide](wiki/user/settings-guide.md#agentplanname)) |
| `agent_plan.remind_min` | `5` | Minutes before each planned block for Google's pop-up reminder; 0: none. ([guide](wiki/user/settings-guide.md#agentplanremindmin)) |

### `agents`

| Setting | Default | What it does |
|---|---|---|
| `agents.export` | `[]` | Which other AI programs get your skills as slash commands, so /journal works there too. ([guide](wiki/user/settings-guide.md#agentsexport)) |
| `agents.prefix` | `""` | A prefix put before every skill copied into your other AI programs, e.g. `k-` for /k-journal. ([guide](wiki/user/settings-guide.md#agentsprefix)) |
| `agents.scripts` | `[]` | Scripts of your own the AI programs may run during a request (full paths). ([guide](wiki/user/settings-guide.md#agentsscripts)) |

### `alarm`

| Setting | Default | What it does |
|---|---|---|
| `alarm.bedtime` | `null` | With an alarm set, no calls from this time until it rings; none uses the night hours' start. ([guide](wiki/user/settings-guide.md#alarmbedtime)) |
| `alarm.daily` | `null` | A wake-up time that rings every day (on the days below) unless you set another for that morning. ([guide](wiki/user/settings-guide.md#alarmdaily)) |
| `alarm.days` | `["mon", "tue", "wed", "thu", "fri", "sat", "sun"]` | The days the daily alarm rings. ([guide](wiki/user/settings-guide.md#alarmdays)) |
| `alarm.keep_awake` | `false` | Keep this computer awake before the alarm so the day's plan is drafted in time. ([guide](wiki/user/settings-guide.md#alarmkeepawake)) |
| `alarm.notes` | `true` | After the wake-up call, today's plan (or what you said on the call) goes into your daily note. ([guide](wiki/user/settings-guide.md#alarmnotes)) |
| `alarm.open_page` | `true` | When the alarm rings, the morning page opens on this computer (if it's awake). ([guide](wiki/user/settings-guide.md#alarmopenpage)) |
| `alarm.prep_min` | `20` | Minutes before the alarm that your AI drafts the day's plan into today's daily note. ([guide](wiki/user/settings-guide.md#alarmprepmin)) |
| `alarm.reason` | `"Wake-up call"` | What the wake-up call says it's for. ([guide](wiki/user/settings-guide.md#alarmreason)) |
| `alarm.retries` | `2` | How many more times the alarm rings if you don't answer (5 minutes apart). ([guide](wiki/user/settings-guide.md#alarmretries)) |
| `alarm.skip_if_up` | `true` | Up before the alarm: one question, skip the ring? It rings as set unless you tap Skip. ([guide](wiki/user/settings-guide.md#alarmskipifup)) |
| `alarm.sleep_aware` | `true` | Up late before a free morning: one offer of a later ring; after a short night the wake-up call keeps it brief. ([guide](wiki/user/settings-guide.md#alarmsleepaware)) |
| `alarm.snooze_min` | `10` | Minutes a snoozed alarm waits before it rings again. ([guide](wiki/user/settings-guide.md#alarmsnoozemin)) |
| `alarm.suggest` | `true` | Before your usual bedtime with no alarm set, one message offering your usual wake-up time. ([guide](wiki/user/settings-guide.md#alarmsuggest)) |

### `ask`

| Setting | Default | What it does |
|---|---|---|
| `ask.expire_hours` | `48` | Hours an unanswered question stays open before it expires (unless its asker set another time). ([guide](wiki/user/settings-guide.md#askexpirehours)) |
| `ask.keep_days` | `0` | Days answered and expired questions are kept before they're forgotten. ([guide](wiki/user/settings-guide.md#askkeepdays)) |

### `autostart`

| Setting | Default | What it does |
|---|---|---|
| `autostart.when` | `"login"` | When Kurooto starts: when you log in, or (Linux with systemd) when the computer starts, before anyone logs in. ([guide](wiki/user/settings-guide.md#autostartwhen)) |

### `availability`

| Setting | Default | What it does |
|---|---|---|
| `availability.absence_days` | `2` | After this many days with nothing from you, one gentle "all good?" message. ([guide](wiki/user/settings-guide.md#availabilityabsencedays)) |
| `availability.focus_keyword` | `"#focus"` | A calendar event with this word in its title is focus time: messages and calls wait. ([guide](wiki/user/settings-guide.md#availabilityfocuskeyword)) |
| `availability.learn_morning` | `true` | The check-in day, the morning message and "Time to start" follow your learned hours. ([guide](wiki/user/settings-guide.md#availabilitylearnmorning)) |
| `availability.learn_night` | `true` | Move the night hours to when you're actually quiet, learned from three weeks of your activity, with Undo. ([guide](wiki/user/settings-guide.md#availabilitylearnnight)) |
| `availability.night.alarm_only` | `false` | Hold calls at night only on nights you've set a wake-up alarm. ([guide](wiki/user/settings-guide.md#availabilitynightalarmonly)) |
| `availability.night.enabled` | `true` | No calls during the night hours. ([guide](wiki/user/settings-guide.md#availabilitynightenabled)) |
| `availability.night.from` | `"23:30"` | When the night hours start. ([guide](wiki/user/settings-guide.md#availabilitynightfrom)) |
| `availability.night.to` | `"07:00"` | When the night hours end. ([guide](wiki/user/settings-guide.md#availabilitynightto)) |
| `availability.nocall_calendar` | `"no call"` | Part of a calendar's name: every event in such a calendar holds calls. ([guide](wiki/user/settings-guide.md#availabilitynocallcalendar)) |
| `availability.nocall_keyword` | `"#nocall"` | A calendar event with this word in its title holds calls while it's on. ([guide](wiki/user/settings-guide.md#availabilitynocallkeyword)) |

### `awake`

| Setting | Default | What it does |
|---|---|---|
| `awake.lid` | `false` | Linux: keep running with the lid closed while plugged in. ([guide](wiki/user/settings-guide.md#awakelid)) |

### `backups`

| Setting | Default | What it does |
|---|---|---|
| `backups.confidential_mail` | `false` | Include confidential mail summarised on this computer (the Mail digest's local mode). ([guide](wiki/user/settings-guide.md#backupsconfidentialmail)) |
| `backups.folder` | `""` | Where the backup zips go: an external drive or a cloud-synced folder. ([guide](wiki/user/settings-guide.md#backupsfolder)) |
| `backups.index` | `true` | Include the notes brain's index (big, but slow to rebuild). ([guide](wiki/user/settings-guide.md#backupsindex)) |
| `backups.keep` | `7` | How many backup zips to keep; Kurooto removes only its own older zips. ([guide](wiki/user/settings-guide.md#backupskeep)) |
| `backups.memory` | `false` | Include the memory ledger (encrypted: it opens only where its key is). ([guide](wiki/user/settings-guide.md#backupsmemory)) |
| `backups.notes` | `false` | Include your notes folder in the backup. ([guide](wiki/user/settings-guide.md#backupsnotes)) |
| `backups.secrets` | `false` | Include passwords and keys (bot token, API keys, sign-ins): anyone with the zip can use them. ([guide](wiki/user/settings-guide.md#backupssecrets)) |
| `backups.when` | `"daily 03:30"` | When the automatic backup runs. ([guide](wiki/user/settings-guide.md#backupswhen)) |

### `books`

| Setting | Default | What it does |
|---|---|---|
| `books.after_read` | `[]` | A command of yours run after each book is read, with its subject and id added. ([guide](wiki/user/settings-guide.md#booksafterread)) |
| `books.at` | `"daily 01:00"` | When the night's book reading begins (on the charger). ([guide](wiki/user/settings-guide.md#booksat)) |
| `books.brain` | `true` | Index each book's text into the notes brain, so search by meaning finds it. ([guide](wiki/user/settings-guide.md#booksbrain)) |
| `books.brain_source` | `""` | Which notes-brain source the book text goes into; empty is the default one. ([guide](wiki/user/settings-guide.md#booksbrainsource)) |
| `books.dpi` | `200` | How sharp the page pictures are for reading scanned pages. ([guide](wiki/user/settings-guide.md#booksdpi)) |
| `books.duplicates` | `true` | A book that's the same file as one already read is linked to it, not read again. ([guide](wiki/user/settings-guide.md#booksduplicates)) |
| `books.folder` | `""` | Your own folder for books, with a subfolder per subject. ([guide](wiki/user/settings-guide.md#booksfolder)) |
| `books.gemini` | `false` | Pages nothing on this computer can read go to Google's Gemini as pictures. ([guide](wiki/user/settings-guide.md#booksgemini)) |
| `books.gemini_model` | `"gemini-flash-latest"` | Which Gemini model reads scanned book pages, when `books.gemini` is on. ([guide](wiki/user/settings-guide.md#booksgeminimodel)) |
| `books.latex` | `"maths"` | Which pages the vision model reads for LaTeX: only ones whose maths came out in pieces, all, or never. ([guide](wiki/user/settings-guide.md#bookslatex)) |
| `books.max_mb` | `400` | PDFs bigger than this (MB) are left alone. ([guide](wiki/user/settings-guide.md#booksmaxmb)) |
| `books.ocr` | `"auto"` | Who reads scanned pages: Tesseract, a vision model on this computer, either, or nobody. ([guide](wiki/user/settings-guide.md#booksocr)) |
| `books.ocr_lang` | `"eng"` | Tesseract's languages for scanned pages, e.g. `eng+deu`. ([guide](wiki/user/settings-guide.md#booksocrlang)) |
| `books.until` | `"07:00"` | When the night's reading stops; it carries on the next night from that page. ([guide](wiki/user/settings-guide.md#booksuntil)) |

### `brain`

| Setting | Default | What it does |
|---|---|---|
| `brain.agy.io_mode` | `"pipe"` | How Kurooto talks to the agy program: through a pipe, or a pseudo-terminal. ([guide](wiki/user/settings-guide.md#brainagyiomode)) |
| `brain.base_urls` | `{}` | Another address for an AI's service, in place of its preset. ([guide](wiki/user/settings-guide.md#brainbaseurls)) |
| `brain.classify` | `"rules"` | Who decides how hard a request is (and so how much effort it gets). ([guide](wiki/user/settings-guide.md#brainclassify)) |
| `brain.claude.session` | `true` | Keep Claude Code running between turns of a conversation, so each message doesn't start it again. ([guide](wiki/user/settings-guide.md#brainclaudesession)) |
| `brain.claude.session_idle_min` | `10` | Minutes a kept Claude Code waits for your next message before it closes. ([guide](wiki/user/settings-guide.md#brainclaudesessionidlemin)) |
| `brain.claude_accounts` | `{}` | Your extra Claude accounts, each its own AI you can pick (`claude:<name>`). ([guide](wiki/user/settings-guide.md#brainclaudeaccounts)) |
| `brain.effort_map` | `{}` | Effort changes Dreaming learned for your requests, e.g. low ones run at medium. ([guide](wiki/user/settings-guide.md#braineffortmap)) |
| `brain.fallback` | `""` | Which AI takes over when your main one can't answer, in order. ([guide](wiki/user/settings-guide.md#brainfallback)) |
| `brain.fallback_first` | `[]` | Effort levels at which your first stand-in AI is tried before the main one (learned by Dreaming). ([guide](wiki/user/settings-guide.md#brainfallbackfirst)) |
| `brain.fallback_on` | `["rate_limited"]` | What makes a request move on to the stand-in AI: a limit, a sign-in problem or a timeout. ([guide](wiki/user/settings-guide.md#brainfallbackon)) |
| `brain.main` | `""` | The AI that answers your requests and does the bigger tasks. ([guide](wiki/user/settings-guide.md#brainmain)) |
| `brain.models` | `{}` | Which model each AI uses at each effort level, where you want other than its preset. ([guide](wiki/user/settings-guide.md#brainmodels)) |
| `brain.timeout_min.high` | `30` | Minutes a hard request may run before it's stopped. ([guide](wiki/user/settings-guide.md#braintimeoutminhigh)) |
| `brain.timeout_min.low` | `10` | Minutes a quick request may run before it's stopped. ([guide](wiki/user/settings-guide.md#braintimeoutminlow)) |
| `brain.timeout_min.medium` | `15` | Minutes a normal request may run before it's stopped. ([guide](wiki/user/settings-guide.md#braintimeoutminmedium)) |

### `calendar`

| Setting | Default | What it does |
|---|---|---|
| `calendar.class_calendars` | `[]` | Calendars whose events are classes: they hold calls and get the after-class question. ([guide](wiki/user/settings-guide.md#calendarclasscalendars)) |
| `calendar.days` | `14` | How many days ahead Kurooto reads your calendar. ([guide](wiki/user/settings-guide.md#calendardays)) |
| `calendar.holiday_calendars` | `[]` | Calendars whose all-day events are holidays (no classes). ([guide](wiki/user/settings-guide.md#calendarholidaycalendars)) |
| `calendar.mask_private` | `true` | Private events show only as "Busy (private)": no title, place or description kept. ([guide](wiki/user/settings-guide.md#calendarmaskprivate)) |
| `calendar.no_calls_in_events` | `true` | No calls while a calendar event is on. ([guide](wiki/user/settings-guide.md#calendarnocallsinevents)) |
| `calendar.nocall_events` | `"all"` | Which events hold calls: every timed one, or only those you tagged. ([guide](wiki/user/settings-guide.md#calendarnocallevents)) |
| `calendar.private_keyword` | `"#private"` | An event with this word in its title or description is private. ([guide](wiki/user/settings-guide.md#calendarprivatekeyword)) |
| `calendar.refresh` | `"every 15m"` | How often the calendar is read again. ([guide](wiki/user/settings-guide.md#calendarrefresh)) |
| `calendar.remind_min` | `0` | Minutes before each timed event for a reminder; 0 is off. ([guide](wiki/user/settings-guide.md#calendarremindmin)) |
| `calendar.shared_offer` | `true` | A subscribed calendar's deadlines and exams are offered with an Add button each. ([guide](wiki/user/settings-guide.md#calendarsharedoffer)) |

### `calls`

| Setting | Default | What it does |
|---|---|---|
| `calls.chat_edit` | `true` | Edit your own messages in the app's chat for 15 minutes after sending. ([guide](wiki/user/settings-guide.md#callschatedit)) |
| `calls.chat_files_inline` | `true` | Files in the app's chat show inline and open in the app. ([guide](wiki/user/settings-guide.md#callschatfilesinline)) |
| `calls.chat_sessions` | `true` | Separate chats in the phone app, each its own conversation whose context carries over. ([guide](wiki/user/settings-guide.md#callschatsessions)) |
| `calls.chat_titles` | `"first words"` | How a new chat gets its title: its first words, or a short title from your AI. ([guide](wiki/user/settings-guide.md#callschattitles)) |
| `calls.later_min` | `30` | Minutes until it calls back after you tap Later on a ringing call. ([guide](wiki/user/settings-guide.md#callslatermin)) |
| `calls.lessons_max` | `12` | How many lessons from past calls every call is told; a repeat replaces the older one. ([guide](wiki/user/settings-guide.md#callslessonsmax)) |
| `calls.live_model` | `"gemini-3.8-live"` | The Gemini Live model calls try first. ([guide](wiki/user/settings-guide.md#callslivemodel)) |
| `calls.live_models` | `["gemini-3.1-flash-live-preview", "gemini-2.5-flash-nativ…` | Other Live models to try, in order, when the first one is down. ([guide](wiki/user/settings-guide.md#callslivemodels)) |
| `calls.notes_repo` | `""` | Your notes' repository on GitHub, so calls can read whole notes while this computer is off. ([guide](wiki/user/settings-guide.md#callsnotesrepo)) |
| `calls.ntfy_server` | `"https://ntfy.sh"` | The push server the phone app listens on. Change it only if you run your own. ([guide](wiki/user/settings-guide.md#callsntfyserver)) |
| `calls.persona` | `""` | Your own words on how calls should sound, such as "be brief and a bit cheeky". ([guide](wiki/user/settings-guide.md#callspersona)) |
| `calls.realert_min` | `[3, 6]` | Minutes after the first ring that an unanswered call rings again. ([guide](wiki/user/settings-guide.md#callsrealertmin)) |
| `calls.review` | `true` | After every call, an AI request looks back at it: does what slipped through and keeps lessons. ([guide](wiki/user/settings-guide.md#callsreview)) |
| `calls.review_brain` | `""` | Which AI does the look back after a call; empty is your main one. ([guide](wiki/user/settings-guide.md#callsreviewbrain)) |
| `calls.review_effort` | `"high"` | How hard the look back after a call thinks. ([guide](wiki/user/settings-guide.md#callsrevieweffort)) |
| `calls.ring_s` | `60` | Seconds a call rings before it counts as missed (a wake-up call rings 5 minutes). ([guide](wiki/user/settings-guide.md#callsrings)) |
| `calls.text_model` | `"gemini-flash-latest"` | The Gemini model that answers turn-by-turn calls (here, or on your call line while the computer is off). ([guide](wiki/user/settings-guide.md#callstextmodel)) |
| `calls.today` | `true` | Your phone app's Today screen and its copy of your alarm, kept up to date from this computer. ([guide](wiki/user/settings-guide.md#callstoday)) |
| `calls.turn_brain` | `"gemini"` | Who answers turn-by-turn calls on your computer: Gemini with your key, or a local model. ([guide](wiki/user/settings-guide.md#callsturnbrain)) |
| `calls.views` | `false` | Systems and the Notes map in the phone app: your notes' titles and links, and each feature's health. ([guide](wiki/user/settings-guide.md#callsviews)) |
| `calls.views_being` | `true` | Show the being in the phone app's Views: the dashboard's own body of Kurooto, drawn on the phone from a sealed copy. ([guide](wiki/user/settings-guide.md#callsviewsbeing)) |
| `calls.views_brain` | `true` | Show the Brain console in the phone app's Views (the Brain choice), sealed for your phone like Systems and the Notes map. ([guide](wiki/user/settings-guide.md#callsviewsbrain)) |
| `calls.views_links` | `20000` | The most links on the phone's Notes map (a book's "Seen in" links go first). ([guide](wiki/user/settings-guide.md#callsviewslinks)) |
| `calls.views_notes` | `5000` | The most notes on the phone's Notes map (best linked first). ([guide](wiki/user/settings-guide.md#callsviewsnotes)) |
| `calls.voice` | `""` | Which Gemini Live voice calls speak in; empty is Google's default. ([guide](wiki/user/settings-guide.md#callsvoice)) |
| `calls.voice_by_kind` | `{}` | The voice mode for one kind of call, e.g. the alarm always on the phone's speech. ([guide](wiki/user/settings-guide.md#callsvoicebykind)) |
| `calls.voice_by_model` | `{}` | A voice for each Live model, where a model doesn't know the one in `calls.voice`. ([guide](wiki/user/settings-guide.md#callsvoicebymodel)) |
| `calls.voice_mode` | `"auto"` | How calls listen and speak: Gemini Live, your phone's own speech turn by turn, or Live with the phone as backup. ([guide](wiki/user/settings-guide.md#callsvoicemode)) |
| `calls.worker.name` | `""` | Your call line's name on Cloudflare (set when it's deployed). ([guide](wiki/user/settings-guide.md#callsworkername)) |
| `calls.worker.url` | `""` | Your call line's address (set when it's deployed). ([guide](wiki/user/settings-guide.md#callsworkerurl)) |
| `calls.worker.version` | `""` | The version of your call line that's deployed (set by Kurooto). ([guide](wiki/user/settings-guide.md#callsworkerversion)) |

### `capture`

| Setting | Default | What it does |
|---|---|---|
| `capture.delay_min` | `2` | Minutes after a class ends before it asks what happened in it. ([guide](wiki/user/settings-guide.md#capturedelaymin)) |
| `capture.skip_subjects` | `[]` | Never ask after these subjects' classes. ([guide](wiki/user/settings-guide.md#captureskipsubjects)) |
| `capture.study_log` | `true` | Your AI turns your after-class answer into a lecture note. ([guide](wiki/user/settings-guide.md#capturestudylog)) |
| `capture.subjects` | `[]` | Ask only after these subjects' classes; empty asks after every subject. ([guide](wiki/user/settings-guide.md#capturesubjects)) |

### `cases`

| Setting | Default | What it does |
|---|---|---|
| `cases.button` | `true` | A Wrong button under replies to plain-English requests (`/wrong` works either way). ([guide](wiki/user/settings-guide.md#casesbutton)) |
| `cases.fallthroughs` | `true` | Keep short requests no instant request understood, to learn from later. ([guide](wiki/user/settings-guide.md#casesfallthroughs)) |
| `cases.keep_days` | `0` | Cases you didn't make test cases are forgotten after this many days (0: `privacy.keep_days`, else 30). ([guide](wiki/user/settings-guide.md#caseskeepdays)) |
| `cases.learn` | `true` | A test case may teach its phrasing, but only if every test case that passed still passes. ([guide](wiki/user/settings-guide.md#caseslearn)) |
| `cases.learn_rephrased` | `true` | The same not-understood phrasing twice followed by the same request: it's learned. ([guide](wiki/user/settings-guide.md#caseslearnrephrased)) |
| `cases.review` | `"weekly sun 19:00"` | When the monthly list of most common not-understood phrasings may come. ([guide](wiki/user/settings-guide.md#casesreview)) |
| `cases.review_days` | `28` | Days at least between two such lists. ([guide](wiki/user/settings-guide.md#casesreviewdays)) |
| `cases.review_max` | `5` | Phrasings in one list. ([guide](wiki/user/settings-guide.md#casesreviewmax)) |

### `checkins`

| Setting | Default | What it does |
|---|---|---|
| `checkins.ai_notes` | `true` | After a check-in call, your AI writes your journal and study logs from what you said. ([guide](wiki/user/settings-guide.md#checkinsainotes)) |
| `checkins.asleep_defers` | `true` | With check-ins by call and an alarm set, the night check-in waits for the morning once you've gone to bed. ([guide](wiki/user/settings-guide.md#checkinsasleepdefers)) |
| `checkins.by_call` | `false` | Check-ins come as a call (a missed call falls back to Telegram). ([guide](wiki/user/settings-guide.md#checkinsbycall)) |
| `checkins.day_starts` | `"05:00"` | When a check-in day begins, so a night check-in at 00:30 still counts for the evening before. ([guide](wiki/user/settings-guide.md#checkinsdaystarts)) |
| `checkins.journal` | `true` | Each check-in's answer goes into your journal. ([guide](wiki/user/settings-guide.md#checkinsjournal)) |
| `checkins.learn_times` | `true` | A check-in you keep moving or answering late moves to when you actually do it, with Undo. ([guide](wiki/user/settings-guide.md#checkinslearntimes)) |
| `checkins.questions.evening` | `"How did today go? What got done, and what slipped?"` | What the evening check-in asks. ([guide](wiki/user/settings-guide.md#checkinsquestionsevening)) |
| `checkins.questions.midday` | `"How's the morning been? Anything to re-plan for the afte…` | What the midday check-in asks. ([guide](wiki/user/settings-guide.md#checkinsquestionsmidday)) |
| `checkins.questions.night` | `"Before bed: anything else for your journal? What's first…` | What the night check-in asks. ([guide](wiki/user/settings-guide.md#checkinsquestionsnight)) |
| `checkins.reflect` | `true` | The evening check-in lists up to three things today's records show you did, and asks what's first tomorrow. ([guide](wiki/user/settings-guide.md#checkinsreflect)) |
| `checkins.times.evening` | `"22:00"` | When the evening check-in comes: the day in review. ([guide](wiki/user/settings-guide.md#checkinstimesevening)) |
| `checkins.times.midday` | `null` | When the midday check-in comes (off unless you set a time). ([guide](wiki/user/settings-guide.md#checkinstimesmidday)) |
| `checkins.times.night` | `null` | When the night check-in comes, just before bed (off unless you set a time). ([guide](wiki/user/settings-guide.md#checkinstimesnight)) |

### `classroom_notes`

| Setting | Default | What it does |
|---|---|---|
| `classroom_notes.at` | `"daily 07:00,13:00,19:00"` | When new Classroom posts are fetched into your notes. ([guide](wiki/user/settings-guide.md#classroomnotesat)) |
| `classroom_notes.backfill_days` | `60` | How far back (days) it looks; older posts not edited since are left alone. ([guide](wiki/user/settings-guide.md#classroomnotesbackfilldays)) |
| `classroom_notes.files` | `true` | Download the Drive files attached to posts and read their text into your notes. ([guide](wiki/user/settings-guide.md#classroomnotesfiles)) |
| `classroom_notes.folders` | `{}` | Which notes folder each course goes into, where Kurooto's own pick is wrong. ([guide](wiki/user/settings-guide.md#classroomnotesfolders)) |
| `classroom_notes.max_file_mb` | `30` | Attached files bigger than this (MB) are only linked, not downloaded. ([guide](wiki/user/settings-guide.md#classroomnotesmaxfilemb)) |
| `classroom_notes.skip` | `[]` | Courses to leave out, by words from their names (`/classnotes skip` fills it). ([guide](wiki/user/settings-guide.md#classroomnotesskip)) |

### `commitments`

| Setting | Default | What it does |
|---|---|---|
| `commitments.hooks` | `[]` | Words of yours that start a hold: "gym" alone holds calls for 90 minutes. ([guide](wiki/user/settings-guide.md#commitmentshooks)) |
| `commitments.items` | `[]` | Your regular commitments (the gym, a shift, a standup), each on its days and hours. ([guide](wiki/user/settings-guide.md#commitmentsitems)) |
| `commitments.no_calls` | `true` | No calls while a commitment is on. ([guide](wiki/user/settings-guide.md#commitmentsnocalls)) |

### `date_offers`

| Setting | Default | What it does |
|---|---|---|
| `date_offers.remind_min` | `60` | An event you tap Add on (from a photo, mail or a shared calendar) is reminded this long before. ([guide](wiki/user/settings-guide.md#dateoffersremindmin)) |

### `deadlines`

| Setting | Default | What it does |
|---|---|---|
| `deadlines.call` | `true` | The urgent nudge is a call, when Phone calls is on (a message when no call fits before it). ([guide](wiki/user/settings-guide.md#deadlinescall)) |
| `deadlines.exam_mode_days` | `14` | Days before a quiz or exam that exam mode starts (more practice, revision); 0 turns it off. ([guide](wiki/user/settings-guide.md#deadlinesexammodedays)) |
| `deadlines.from_calendar` | `true` | Calendar events that look like deadlines or exams join the deadline list. ([guide](wiki/user/settings-guide.md#deadlinesfromcalendar)) |
| `deadlines.from_photos` | `true` | Send a photo with the caption "dates" and its dates come back as buttons to add. ([guide](wiki/user/settings-guide.md#deadlinesfromphotos)) |
| `deadlines.from_term_note` | `true` | The term note's quizzes, exams and deadlines join the deadline list. ([guide](wiki/user/settings-guide.md#deadlinesfromtermnote)) |
| `deadlines.horizon_days` | `30` | How far ahead recurring quizzes become dated deadlines, in days. ([guide](wiki/user/settings-guide.md#deadlineshorizondays)) |
| `deadlines.max_files` | `3000` | The most notes read when looking for deadlines (notes over 1 MB are skipped). ([guide](wiki/user/settings-guide.md#deadlinesmaxfiles)) |
| `deadlines.meeting_brief` | `"daily 20:00"` | The evening before a meeting with a project's person: a short brief of where things stand. ([guide](wiki/user/settings-guide.md#deadlinesmeetingbrief)) |
| `deadlines.overdue_check` | `true` | After a deadline's due time: "Overdue?" with Done / New date / Drop. ([guide](wiki/user/settings-guide.md#deadlinesoverduecheck)) |
| `deadlines.ping_h` | `24` | Hours before a deadline that its first nudge comes (one message, with Done / Not mine / Snooze). ([guide](wiki/user/settings-guide.md#deadlinespingh)) |
| `deadlines.plan_h` | `72` | How far ahead "due soon" looks, in hours: the morning plan, /status and calls. ([guide](wiki/user/settings-guide.md#deadlinesplanh)) |
| `deadlines.recurring` | `true` | Recurring quizzes (from kurooto/recurring.md in your notes) become dated deadlines. ([guide](wiki/user/settings-guide.md#deadlinesrecurring)) |
| `deadlines.scan_notes` | `true` | Find deadlines in your notes: dated `- [ ]` tasks. ([guide](wiki/user/settings-guide.md#deadlinesscannotes)) |
| `deadlines.skip_notes` | `[]` | Notes or folders the deadline scan leaves alone. ([guide](wiki/user/settings-guide.md#deadlinesskipnotes)) |
| `deadlines.tick_notes` | `true` | Done ticks the `- [ ]` line in your notes when the deadline came from one. ([guide](wiki/user/settings-guide.md#deadlinesticknotes)) |
| `deadlines.urgent_h` | `6` | Hours before a deadline that it's urgent: a call (with Phone calls) or an urgent message. ([guide](wiki/user/settings-guide.md#deadlinesurgenth)) |

### `doubts`

| Setting | Default | What it does |
|---|---|---|
| `doubts.before_min` | `30` | Open doubts for a subject come this many minutes before its next class. ([guide](wiki/user/settings-guide.md#doubtsbeforemin)) |
| `doubts.recent_h` | `3` | A doubt that names no subject is filed under the class that's on, or ended this many hours ago. ([guide](wiki/user/settings-guide.md#doubtsrecenth)) |

### `drafts`

| Setting | Default | What it does |
|---|---|---|
| `drafts.max_comments` | `15` | The most comments "Check my draft" puts on one draft. ([guide](wiki/user/settings-guide.md#draftsmaxcomments)) |
| `drafts.note_block` | `true` | For checked notes, the comments also go into a block in the matching lecture note. ([guide](wiki/user/settings-guide.md#draftsnoteblock)) |
| `drafts.recent_minutes` | `15` | "Check this" right after you sent a file checks that file, if it came this recently (minutes). ([guide](wiki/user/settings-guide.md#draftsrecentminutes)) |

### `dreaming`

| Setting | Default | What it does |
|---|---|---|
| `dreaming.consolidate` | `true` | Ask about things it remembers twice or that disagree: Keep A / Keep B / Both true. ([guide](wiki/user/settings-guide.md#dreamingconsolidate)) |
| `dreaming.consolidate_ai` | `"local"` | A second opinion on near misses: a model here, your AI, or none. ([guide](wiki/user/settings-guide.md#dreamingconsolidateai)) |
| `dreaming.consolidate_max` | `3` | The most such questions in one morning message; the rest wait. ([guide](wiki/user/settings-guide.md#dreamingconsolidatemax)) |
| `dreaming.curious` | `true` | Mention a topic you asked about 3+ times this week that has no note, with Make a stub. ([guide](wiki/user/settings-guide.md#dreamingcurious)) |
| `dreaming.fold` | `true` | In the morning message, offer lasting things you said for your profile (Keep / Not that). ([guide](wiki/user/settings-guide.md#dreamingfold)) |
| `dreaming.fold_ai` | `"local"` | A second look at what the rules found for your profile: a model here, your AI, or none. ([guide](wiki/user/settings-guide.md#dreamingfoldai)) |
| `dreaming.fold_max` | `3` | The most profile suggestions in one morning message. ([guide](wiki/user/settings-guide.md#dreamingfoldmax)) |
| `dreaming.loose_ends` | `true` | The morning message also lists loose ends: open doubts, unlinked notes, broken links, tasks past due. ([guide](wiki/user/settings-guide.md#dreaminglooseends)) |
| `dreaming.never_tune` | `["deadlines.reminder", "deadlines.call", "health.now", "a…` | Kinds of message it never tunes (besides the alarm, your reminders and calls, deadlines under 12 hours). ([guide](wiki/user/settings-guide.md#dreamingnevertune)) |
| `dreaming.propose_prompts` | `false` | Offer a fix for a skill that keeps going wrong, as a proposal you apply or not. ([guide](wiki/user/settings-guide.md#dreamingproposeprompts)) |
| `dreaming.resurface` | `true` | Bring back one thing from the past: a note or quiz subject from 10-30 days ago, or an anniversary. ([guide](wiki/user/settings-guide.md#dreamingresurface)) |
| `dreaming.self_check` | `true` | Each morning, replay your test cases and say which ones went wrong since yesterday. ([guide](wiki/user/settings-guide.md#dreamingselfcheck)) |
| `dreaming.tune_effort` | `true` | Each night, replay your requests and tune the effort they get (one change, with Undo). ([guide](wiki/user/settings-guide.md#dreamingtuneeffort)) |
| `dreaming.tune_fallbacks` | `true` | Each night, check which AI did best at each effort and let that one go first (with Undo). ([guide](wiki/user/settings-guide.md#dreamingtunefallbacks)) |
| `dreaming.tune_margin` | `3.0` | How much better a change must score in the replay than leaving things as they are. ([guide](wiki/user/settings-guide.md#dreamingtunemargin)) |
| `dreaming.tune_messages` | `true` | Each night, replay the messages it sent you and tune when they come (one change, with Undo). ([guide](wiki/user/settings-guide.md#dreamingtunemessages)) |
| `dreaming.tune_sizing` | `true` | Each night, adjust Start-by's sizes to how long your deadlines really took. ([guide](wiki/user/settings-guide.md#dreamingtunesizing)) |
| `dreaming.when` | `"daily 07:30"` | When the morning message comes ("While you slept"), covering everything since the last one. ([guide](wiki/user/settings-guide.md#dreamingwhen)) |

### `drive_upload`

| Setting | Default | What it does |
|---|---|---|
| `drive_upload.big_files` | `true` | A file too big for Telegram (over 50 MB) comes as a Drive link instead of failing. ([guide](wiki/user/settings-guide.md#driveuploadbigfiles)) |
| `drive_upload.folder` | `"Kurooto"` | The Google Drive folder files go to. ([guide](wiki/user/settings-guide.md#driveuploadfolder)) |
| `drive_upload.temp_days` | `7` | Days a too-big-for-Telegram upload is kept in your Drive before it's deleted; 0 keeps them. ([guide](wiki/user/settings-guide.md#driveuploadtempdays)) |

### `exam_season`

| Setting | Default | What it does |
|---|---|---|
| `exam_season.alarm_check` | `true` | Every night of the exam period: will tomorrow's alarm ring? ([guide](wiki/user/settings-guide.md#examseasonalarmcheck)) |
| `exam_season.block_min` | `60` | Minutes in one revision block (one topic each). ([guide](wiki/user/settings-guide.md#examseasonblockmin)) |
| `exam_season.budget` | `true` | During exams, only deadlines, quizzes and the alarm come in the day; the rest waits for the evening. ([guide](wiki/user/settings-guide.md#examseasonbudget)) |
| `exam_season.debrief` | `true` | After each exam, a two-minute debrief that goes into the subject's course note. ([guide](wiki/user/settings-guide.md#examseasondebrief)) |
| `exam_season.eve` | `true` | The evening before an exam, a checklist: where it is, your seat, calculator, ID card. ([guide](wiki/user/settings-guide.md#examseasoneve)) |
| `exam_season.eve_at` | `"18:00"` | When the evening-before question can come. ([guide](wiki/user/settings-guide.md#examseasoneveat)) |
| `exam_season.exam_min` | `180` | How long an exam lasts, in minutes (no calls then; the debrief comes half an hour after). ([guide](wiki/user/settings-guide.md#examseasonexammin)) |
| `exam_season.hold_updates` | `true` | During exams, updates that aren't critical wait until the exams are over. ([guide](wiki/user/settings-guide.md#examseasonholdupdates)) |
| `exam_season.leave_alarm` | `true` | On an exam day, an alarm to leave (a call with Phone calls, else a message). ([guide](wiki/user/settings-guide.md#examseasonleavealarm)) |
| `exam_season.leave_min` | `45` | Minutes before the exam the leave alarm goes, unless you say a time ("leave 8:10"). ([guide](wiki/user/settings-guide.md#examseasonleavemin)) |
| `exam_season.night_at` | `"21:30"` | When the nightly alarm check runs. ([guide](wiki/user/settings-guide.md#examseasonnightat)) |
| `exam_season.no_calls` | `true` | Hold every call while an exam is on. ([guide](wiki/user/settings-guide.md#examseasonnocalls)) |
| `exam_season.quiz_call_at` | `"19:00"` | When a quiz call you picked rings the evening before an exam. ([guide](wiki/user/settings-guide.md#examseasonquizcallat)) |
| `exam_season.quizzes` | `false` | Treat quizzes and tests outside an exam period as exams too. ([guide](wiki/user/settings-guide.md#examseasonquizzes)) |
| `exam_season.revision` | `true` | A revision plan before each exam: its topics ranked and fitted into your free time (/revise). ([guide](wiki/user/settings-guide.md#examseasonrevision)) |
| `exam_season.revision_ask` | `true` | Each evening: did you cover today's revision topics? (Counts like a quiz answer.) ([guide](wiki/user/settings-guide.md#examseasonrevisionask)) |
| `exam_season.revision_days` | `14` | Days before each exam that the revision plan starts. ([guide](wiki/user/settings-guide.md#examseasonrevisiondays)) |
| `exam_season.revision_share` | `50` | The share of your free time (in %) revision blocks may take. ([guide](wiki/user/settings-guide.md#examseasonrevisionshare)) |

### `face`

| Setting | Default | What it does |
|---|---|---|
| `face.addons.hold` | `true` | Let an add-on keep the camera looking while you type (never past a pause, the night, a call or a switch). ([guide](wiki/user/settings-guide.md#faceaddonshold)) |
| `face.addons.watch` | `true` | Let an add-on see who's in view: each face's place, size and numbers, in memory only, never a picture. ([guide](wiki/user/settings-guide.md#faceaddonswatch)) |
| `face.away.after_min` | `5` | No sign of you (your face or the keyboard) this long means you've left, in minutes. ([guide](wiki/user/settings-guide.md#faceawayaftermin)) |
| `face.away.hold_calls` | `false` | While you're away, calls Kurooto would start by itself wait for you (up to the longest wait below). ([guide](wiki/user/settings-guide.md#faceawayholdcalls)) |
| `face.away.hold_desktop` | `false` | Hold desktop pop-ups and spoken answers until you're back at the desk. ([guide](wiki/user/settings-guide.md#faceawayholddesktop)) |
| `face.away.hold_max_min` | `60` | The longest a call waits while you're away, in minutes. ([guide](wiki/user/settings-guide.md#faceawayholdmaxmin)) |
| `face.away.on` | `false` | Notice when you leave the desk and come back. ([guide](wiki/user/settings-guide.md#faceawayon)) |
| `face.breaks` | `true` | Leaving, looking up at the camera and standing up are natural breaks for Brain's door. ([guide](wiki/user/settings-guide.md#facebreaks)) |
| `face.camera.device` | `""` | The camera to use: empty for the first ordinary one (infrared ones are skipped), or a number or part of its name. ([guide](wiki/user/settings-guide.md#facecameradevice)) |
| `face.camera.height` | `480` | The picture height asked of the camera. ([guide](wiki/user/settings-guide.md#facecameraheight)) |
| `face.camera.width` | `640` | The picture width asked of the camera (it may give another). ([guide](wiki/user/settings-guide.md#facecamerawidth)) |
| `face.greet.after_absent_min` | `20` | Greet you only after you've been away at least this long, in minutes. ([guide](wiki/user/settings-guide.md#facegreetafterabsentmin)) |
| `face.greet.gap_min` | `60` | The fewest minutes between two greetings. ([guide](wiki/user/settings-guide.md#facegreetgapmin)) |
| `face.greet.listen_s` | `12` | How long that conversation stays open with nothing said, in seconds. ([guide](wiki/user/settings-guide.md#facegreetlistens)) |
| `face.greet.on` | `true` | Greet you by voice when you arrive at the desk. ([guide](wiki/user/settings-guide.md#facegreeton)) |
| `face.greet.per_day` | `3` | A daily cap on greetings. ([guide](wiki/user/settings-guide.md#facegreetperday)) |
| `face.greet.say` | `["next", "waiting", "deadline", "answers"]` | What the greeting tells you: what's next today, what's waiting, deadlines in 24 h, what was held while you were away. ([guide](wiki/user/settings-guide.md#facegreetsay)) |
| `face.greet.talk` | `true` | After the greeting, listen for a reply without its name being said. ([guide](wiki/user/settings-guide.md#facegreettalk)) |
| `face.greet.with_others` | `"skip"` | When someone else is in view too: skip the greeting, say just "Welcome back.", or the full greeting. ([guide](wiki/user/settings-guide.md#facegreetwithothers)) |
| `face.learn.every_h` | `6` | At most one new sample this often, in hours. ([guide](wiki/user/settings-guide.md#facelearneveryh)) |
| `face.learn.margin` | `0.08` | How far above your threshold a frame's score must be before it may refine your template. ([guide](wiki/user/settings-guide.md#facelearnmargin)) |
| `face.learn.max` | `30` | At most this many learned samples (the oldest goes first); the enrolled ones are never replaced. ([guide](wiki/user/settings-guide.md#facelearnmax)) |
| `face.learn.on` | `false` | Slowly refine your face template from times it was very sure it was you (never unsure ones), with Undo. ([guide](wiki/user/settings-guide.md#facelearnon)) |
| `face.recognise.frames` | `3` | Recognised in this many of the last 4 frames means you're here. ([guide](wiki/user/settings-guide.md#facerecogniseframes)) |
| `face.recognise.min_face_px` | `60` | Faces smaller than this many pixels are ignored: too far away to judge. ([guide](wiki/user/settings-guide.md#facerecogniseminfacepx)) |
| `face.recognise.strictness` | `"normal"` | How rarely a stranger may pass: loose (1 in 100 frames), normal (1 in 1,000) or strict (1 in 10,000). ([guide](wiki/user/settings-guide.md#facerecognisestrictness)) |
| `face.recognise.threshold` | `0.0` | 0 uses the calibrated threshold; a score from 0 to 1 overrides it (never below 0.363). ([guide](wiki/user/settings-guide.md#facerecognisethreshold)) |
| `face.track.fps` | `10` | How many times a second it looks for faces while following them (1 to 15). ([guide](wiki/user/settings-guide.md#facetrackfps)) |
| `face.track.on` | `true` | While the camera is open, follow every face in view (where it is and how much it moves) for the being's eye. ([guide](wiki/user/settings-guide.md#facetrackon)) |
| `face.watch.fps` | `1.0` | How many pictures a second it checks while waiting for you (0.2 to 2). ([guide](wiki/user/settings-guide.md#facewatchfps)) |
| `face.watch.fps_battery` | `0.33` | Frames a second while the computer is on battery. ([guide](wiki/user/settings-guide.md#facewatchfpsbattery)) |
| `face.watch.idle_s` | `60` | Seconds with no keyboard or mouse before the camera looks; while you type it doesn't need to. ([guide](wiki/user/settings-guide.md#facewatchidles)) |
| `face.watch.look_fps` | `5.0` | While Voice listens for a look (voice.listen.look_to_talk), the camera checks at least this many pictures a second. ([guide](wiki/user/settings-guide.md#facewatchlookfps)) |
| `face.watch.night` | `false` | Also look during the night hours (Availability's night); off pauses it at night. ([guide](wiki/user/settings-guide.md#facewatchnight)) |
| `face.watch.when_locked` | `false` | Also look while the screen is locked; off pauses it while locked. ([guide](wiki/user/settings-guide.md#facewatchwhenlocked)) |

### `files`

| Setting | Default | What it does |
|---|---|---|
| `files.folder` | `""` | A folder for files outside your notes (course files, PDFs); empty keeps them inside the notes. ([guide](wiki/user/settings-guide.md#filesfolder)) |
| `files.links` | `""` | How notes link to files outside the notes folder. ([guide](wiki/user/settings-guide.md#fileslinks)) |

### `finder`

| Setting | Default | What it does |
|---|---|---|
| `finder.folders` | `[]` | The folders Find files indexes and searches (`/find add <folder>` adds one). ([guide](wiki/user/settings-guide.md#finderfolders)) |
| `finder.max_files` | `60000` | The most files Find files indexes. ([guide](wiki/user/settings-guide.md#findermaxfiles)) |
| `finder.read_mb` | `20` | Files bigger than this (MB) have their name indexed but not their text. ([guide](wiki/user/settings-guide.md#finderreadmb)) |

### `gbrain`

| Setting | Default | What it does |
|---|---|---|
| `gbrain.agy_mcp` | `false` | Your own GBrain: agy gets its MCP tools too (you're asked first). ([guide](wiki/user/settings-guide.md#gbrainagymcp)) |
| `gbrain.checkup` | `false` | A weekly checkup of the brain; a message only when something needs a look. ([guide](wiki/user/settings-guide.md#gbraincheckup)) |
| `gbrain.checkup_ignore` | `["backup_", "mcp_", "chronicle", "auto_chronicle", "unins…` | Checkup findings starting with these words aren't reported. ([guide](wiki/user/settings-guide.md#gbraincheckupignore)) |
| `gbrain.checkup_line` | `true` | Once a week, one line on how the notes brain is (read only). ([guide](wiki/user/settings-guide.md#gbraincheckupline)) |
| `gbrain.checkup_when` | `"weekly sun 19:30"` | When the weekly checkup runs. ([guide](wiki/user/settings-guide.md#gbraincheckupwhen)) |
| `gbrain.contradictions` | `true` | The brain's last contradictions report joins Dreaming's morning section, with Keep A / Keep B. ([guide](wiki/user/settings-guide.md#gbraincontradictions)) |
| `gbrain.course_pages` | `true` | Nightly, each course page gets its key concepts and a dated timeline, in Kurooto's own block. ([guide](wiki/user/settings-guide.md#gbraincoursepages)) |
| `gbrain.embeddings` | `"auto"` | How the notes brain makes its search-by-meaning index: a model here, Google's, or keywords only. ([guide](wiki/user/settings-guide.md#gbrainembeddings)) |
| `gbrain.exe` | `""` | Your own GBrain: your gbrain program; empty uses the one on your PATH. ([guide](wiki/user/settings-guide.md#gbrainexe)) |
| `gbrain.home` | `""` | Your own GBrain: its GBRAIN_HOME folder; empty uses GBrain's default. ([guide](wiki/user/settings-guide.md#gbrainhome)) |
| `gbrain.managed` | `true` | Kurooto runs its own notes brain; off, it uses a GBrain you already run. ([guide](wiki/user/settings-guide.md#gbrainmanaged)) |
| `gbrain.mcp_surface` | `"full"` | What your brain's MCP server offers agy: everything, a starter set, or only verbs. ([guide](wiki/user/settings-guide.md#gbrainmcpsurface)) |
| `gbrain.nightly` | `"daily 03:00"` | When the brain's nightly timelines and upkeep run. ([guide](wiki/user/settings-guide.md#gbrainnightly)) |
| `gbrain.source` | `""` | Your own GBrain: the source that is your notes folder, kept in step every 15 minutes. ([guide](wiki/user/settings-guide.md#gbrainsource)) |
| `gbrain.sync` | `"every 15m"` | How often your notes are read into the notes brain. ([guide](wiki/user/settings-guide.md#gbrainsync)) |
| `gbrain.timelines` | `true` | Nightly, dated log lines in your notes become each note's timeline (`/timeline <note>`). ([guide](wiki/user/settings-guide.md#gbraintimelines)) |
| `gbrain.upkeep` | `false` | Nightly upkeep of the brain (links, facts, the index), light steps only; waits for the charger. ([guide](wiki/user/settings-guide.md#gbrainupkeep)) |
| `gbrain.upkeep_steps` | `[]` | Which upkeep steps run (GBrain's own phase names); empty: the light ones. ([guide](wiki/user/settings-guide.md#gbrainupkeepsteps)) |

### `google`

| Setting | Default | What it does |
|---|---|---|
| `google.accounts` | `["main"]` | The names of your signed-in Google accounts; "main" is the one you signed in with first. ([guide](wiki/user/settings-guide.md#googleaccounts)) |
| `google.agent_calendar` | `false` | Permission for Kurooto's own "Agent plan" calendar (it can't see your others). ([guide](wiki/user/settings-guide.md#googleagentcalendar)) |
| `google.calendar_read` | `false` | Permission to read your calendars (Google Calendar), read-only. ([guide](wiki/user/settings-guide.md#googlecalendarread)) |
| `google.classroom` | `true` | Read Classroom: courses, assignments and announcements, for deadlines. ([guide](wiki/user/settings-guide.md#googleclassroom)) |
| `google.classroom_every` | `"every 3h"` | How often Classroom is checked for new deadlines. ([guide](wiki/user/settings-guide.md#googleclassroomevery)) |
| `google.classroom_notes` | `false` | Permission for Classroom → notes: materials and attached Drive files, read-only. ([guide](wiki/user/settings-guide.md#googleclassroomnotes)) |
| `google.digest_email` | `false` | Permission to send the mail digest to your own inbox (send only). ([guide](wiki/user/settings-guide.md#googledigestemail)) |
| `google.drive_upload` | `false` | Permission to put files you send yourself into a Kurooto folder in Drive (its own files only). ([guide](wiki/user/settings-guide.md#googledriveupload)) |
| `google.endpoints.auth` | `"https://accounts.google.com/o/oauth2/v2/auth"` | Google's sign-in address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointsauth)) |
| `google.endpoints.calendar` | `"https://www.googleapis.com/calendar/v3"` | Google Calendar's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointscalendar)) |
| `google.endpoints.classroom` | `"https://classroom.googleapis.com/v1"` | Google Classroom's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointsclassroom)) |
| `google.endpoints.drive` | `"https://www.googleapis.com/drive/v3"` | Google Drive's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointsdrive)) |
| `google.endpoints.drive_upload` | `"https://www.googleapis.com/upload/drive/v3"` | Google Drive's upload address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointsdriveupload)) |
| `google.endpoints.gmail` | `"https://gmail.googleapis.com/gmail/v1"` | Gmail's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointsgmail)) |
| `google.endpoints.token` | `"https://oauth2.googleapis.com/token"` | Google's token address. Leave it alone. ([guide](wiki/user/settings-guide.md#googleendpointstoken)) |
| `google.gmail_drafts` | `false` | Allow `/draft` to save drafts in your Gmail (one more sign-in: Google calls it a restricted permission). ([guide](wiki/user/settings-guide.md#googlegmaildrafts)) |
| `google.mail_digest` | `false` | Permission for the mail digest: read Gmail, read-only. ([guide](wiki/user/settings-guide.md#googlemaildigest)) |
| `google.reply_drafts` | `false` | Permission for reply drafts in Gmail, sent only when you tap Send. ([guide](wiki/user/settings-guide.md#googlereplydrafts)) |
| `google.use` | `{}` | Which of your Google accounts each feature uses; unset means main. ([guide](wiki/user/settings-guide.md#googleuse)) |

### `google_calendar`

| Setting | Default | What it does |
|---|---|---|
| `google_calendar.skip` | `[]` | Google calendars to leave out, by any part of their name. ([guide](wiki/user/settings-guide.md#googlecalendarskip)) |

### `handwritten`

| Setting | Default | What it does |
|---|---|---|
| `handwritten.cloud` | `true` | With no model on this computer, Gemini reads the pages; off, they wait for a model here. ([guide](wiki/user/settings-guide.md#handwrittencloud)) |
| `handwritten.dpi` | `110` | How sharp the pictures of handwritten pages are when they're read. ([guide](wiki/user/settings-guide.md#handwrittendpi)) |
| `handwritten.every` | `"every 15m"` | How often the handwritten-notes folder is checked for new scans. ([guide](wiki/user/settings-guide.md#handwrittenevery)) |
| `handwritten.folder` | `""` | Where scans of handwritten pages land to be read. ([guide](wiki/user/settings-guide.md#handwrittenfolder)) |
| `handwritten.into` | `""` | Where the written-out notes go, inside your notes folder. ([guide](wiki/user/settings-guide.md#handwritteninto)) |
| `handwritten.keep_original` | `"copy"` | Keep a copy of the scan next to the note, or link to where it already is. ([guide](wiki/user/settings-guide.md#handwrittenkeeporiginal)) |
| `handwritten.link` | `true` | Link each written-out note to its lecture, course page and concept notes. ([guide](wiki/user/settings-guide.md#handwrittenlink)) |
| `handwritten.local` | `true` | A model on this computer reads the pages when there is one. ([guide](wiki/user/settings-guide.md#handwrittenlocal)) |
| `handwritten.local_model` | `""` | An Ollama model of your choice that reads pictures; empty uses Local AI models' pick. ([guide](wiki/user/settings-guide.md#handwrittenlocalmodel)) |
| `handwritten.max_pages` | `60` | The most pages written out per PDF. ([guide](wiki/user/settings-guide.md#handwrittenmaxpages)) |
| `handwritten.model` | `"gemini-flash-latest"` | Which Gemini model reads handwriting when it's used. ([guide](wiki/user/settings-guide.md#handwrittenmodel)) |
| `handwritten.pdf_hours` | `"23:00-07:00"` | When the model on this computer reads PDFs (on the charger); empty: any time. ([guide](wiki/user/settings-guide.md#handwrittenpdfhours)) |

### `hardware`

| Setting | Default | What it does |
|---|---|---|
| `hardware.extra_models` | `[]` | Ollama models of your own to install, past what suits this computer. ([guide](wiki/user/settings-guide.md#hardwareextramodels)) |
| `hardware.extra_prereqs` | `[]` | Other programs Kurooto should install for you, by id. ([guide](wiki/user/settings-guide.md#hardwareextraprereqs)) |
| `hardware.force_profile` | `""` | Use another hardware profile's models than the one detected for this computer. ([guide](wiki/user/settings-guide.md#hardwareforceprofile)) |

### `health`

| Setting | Default | What it does |
|---|---|---|
| `health.auto_fix` | `true` | Try a safe fix before telling you (never a sync: that one waits for your tap). ([guide](wiki/user/settings-guide.md#healthautofix)) |
| `health.on` | `true` | The daily health pass: it checks what matters and tells you only when something needs you. ([guide](wiki/user/settings-guide.md#healthon)) |
| `health.when` | `"daily 21:00"` | When the daily health pass runs; tonight's alarm is checked then. ([guide](wiki/user/settings-guide.md#healthwhen)) |

### `infer`

| Setting | Default | What it does |
|---|---|---|
| `infer.aliases` | `true` | "By POTA I mean Physics of the Atmosphere" gives that subject a short name. ([guide](wiki/user/settings-guide.md#inferaliases)) |
| `infer.classes` | `true` | "Every Monday at 9 I have a <subject> lab" adds a class to your timetable. ([guide](wiki/user/settings-guide.md#inferclasses)) |
| `infer.commitments` | `true` | "Every Tuesday at 7pm I go to the gym" adds a commitment (it holds calls like a class). ([guide](wiki/user/settings-guide.md#infercommitments)) |
| `infer.meetings` | `true` | "Met X today" adds a dated line to that project's Meetings; a meeting ahead becomes a deadline. ([guide](wiki/user/settings-guide.md#infermeetings)) |
| `infer.on` | `true` | Set things up from what you say in the chat and the journal ("every Monday at 9 I have a lab"), each with Undo. ([guide](wiki/user/settings-guide.md#inferon)) |
| `infer.projects` | `true` | "I got a project under Prof X" makes a project note with them and a Meetings section. ([guide](wiki/user/settings-guide.md#inferprojects)) |
| `infer.quizzes` | `true` | "There's a quiz on Linear Algebra every Monday" adds a row to the recurring quizzes table. ([guide](wiki/user/settings-guide.md#inferquizzes)) |
| `infer.short_names` | `true` | "LA" becomes Linear Algebra's short name after two messages use it (when it fits only that subject). ([guide](wiki/user/settings-guide.md#infershortnames)) |
| `infer.sweep` | `true` | One pass over your chats and journal for such sentences: once when first on, then nightly on what's new. ([guide](wiki/user/settings-guide.md#infersweep)) |
| `infer.sweep_ai` | `"local"` | A line the rules can't read: a model here restates it, your AI does, or it's skipped. ([guide](wiki/user/settings-guide.md#infersweepai)) |
| `infer.sweep_days` | `30` | How far back (days) the first pass over your chats and journal reads. ([guide](wiki/user/settings-guide.md#infersweepdays)) |

### `integrate`

| Setting | Default | What it does |
|---|---|---|
| `integrate.at` | `"daily 01:30"` | When the night's reading starts (it carries on batch after batch). ([guide](wiki/user/settings-guide.md#integrateat)) |
| `integrate.auto_merge` | `true` | Look-alike concept notes that are clearly one concept merge by themselves (Undo in the morning line). ([guide](wiki/user/settings-guide.md#integrateautomerge)) |
| `integrate.auto_merge_min` | `0.97` | How alike two notes must be (0.92 to 1) to merge without asking. ([guide](wiki/user/settings-guide.md#integrateautomergemin)) |
| `integrate.batch_pages` | `12` | About how many pages go into one request. ([guide](wiki/user/settings-guide.md#integratebatchpages)) |
| `integrate.commit` | `true` | One git commit per batch, when your notes folder is a repository. ([guide](wiki/user/settings-guide.md#integratecommit)) |
| `integrate.duplicates` | `true` | Each morning, up to three pairs of look-alike concept notes: Merge / Keep both / Add alias. ([guide](wiki/user/settings-guide.md#integrateduplicates)) |
| `integrate.duplicates_all` | `true` | Each morning, also ask about notes of any kind that are copies of each other, old ones included. ([guide](wiki/user/settings-guide.md#integrateduplicatesall)) |
| `integrate.duplicates_per_day` | `3` | How many pairs of copied notes it asks about in a day, at most. ([guide](wiki/user/settings-guide.md#integrateduplicatesperday)) |
| `integrate.embeddings` | `"auto"` | How related notes are found by meaning: a model here, Google's, or not at all. ([guide](wiki/user/settings-guide.md#integrateembeddings)) |
| `integrate.first` | `[]` | Subjects to read first. ([guide](wiki/user/settings-guide.md#integratefirst)) |
| `integrate.garden` | `true` | A daily second pass that links the notes the reading touched and notes nothing links to yet. ([guide](wiki/user/settings-guide.md#integrategarden)) |
| `integrate.garden_at` | `"daily 06:20"` | When the daily second pass runs (`/graph garden` runs it now). ([guide](wiki/user/settings-guide.md#integrategardenat)) |
| `integrate.garden_per_day` | `40` | The most notes in the daily second pass. ([guide](wiki/user/settings-guide.md#integrategardenperday)) |
| `integrate.max_cost_per_night` | `0.5` | With a paid API key: the most a night's reading may cost, in US dollars. ([guide](wiki/user/settings-guide.md#integratemaxcostpernight)) |
| `integrate.notation` | `true` | A Notation table when a second source writes a concept differently. ([guide](wiki/user/settings-guide.md#integratenotation)) |
| `integrate.order` | `"smallest"` | Which books first: the smallest (most books done soonest) or by name. ([guide](wiki/user/settings-guide.md#integrateorder)) |
| `integrate.per_night` | `"auto"` | How many batches a night: fitted to your AI's plan, or a number you set as a hard ceiling. ([guide](wiki/user/settings-guide.md#integratepernight)) |
| `integrate.price_per_mtok.in` | `2.0` | An API key that reports no cost: its price per million input tokens (USD), for the estimate. ([guide](wiki/user/settings-guide.md#integratepricepermtokin)) |
| `integrate.price_per_mtok.out` | `8.0` | An API key that reports no cost: its price per million output tokens (USD), for the estimate. ([guide](wiki/user/settings-guide.md#integratepricepermtokout)) |
| `integrate.rerank` | `"auto"` | A local model judges which notes belong together (a graphics card helps). ([guide](wiki/user/settings-guide.md#integratererank)) |
| `integrate.rerank_model` | `""` | Which local model does that judging; empty uses this computer's helper model. ([guide](wiki/user/settings-guide.md#integratererankmodel)) |
| `integrate.roles.bulk` | `""` | The AI that does the bulk reading; empty is chosen for you. ([guide](wiki/user/settings-guide.md#integraterolesbulk)) |
| `integrate.roles.check` | `""` | The AI that takes the second look at doubtful answers; empty is chosen for you. ([guide](wiki/user/settings-guide.md#integraterolescheck)) |
| `integrate.share_pct` | `60` | The most of a subscription's usage window (or a free key's day) the reading may take, in %. ([guide](wiki/user/settings-guide.md#integratesharepct)) |
| `integrate.sources` | `["books", "classroom", "reference"]` | What's read into the graph: books, Classroom files, handwritten notes, repositories, reference files. ([guide](wiki/user/settings-guide.md#integratesources)) |
| `integrate.summary` | `true` | One line each morning about what the reading changed. ([guide](wiki/user/settings-guide.md#integratesummary)) |

### `jobs`

| Setting | Default | What it does |
|---|---|---|
| `jobs.header` | `true` | A first line on each answer naming the AI and repeating what you asked. ([guide](wiki/user/settings-guide.md#jobsheader)) |
| `jobs.plan_line` | `true` | Before a long answer, one short line saying what it's about to do and roughly how long. ([guide](wiki/user/settings-guide.md#jobsplanline)) |
| `jobs.receipt` | `true` | One quiet line under each answer: which AI, effort, time, limit used and what it did. ([guide](wiki/user/settings-guide.md#jobsreceipt)) |
| `jobs.stuck_min` | `10` | Minutes a request may sit with no AI at work and no program running before the watchdog stops it. ([guide](wiki/user/settings-guide.md#jobsstuckmin)) |

### `keep`

| Setting | Default | What it does |
|---|---|---|
| `keep.ask` | `true` | On day 10, then at most monthly: Keep / Quiet / Off for features you don't use. ([guide](wiki/user/settings-guide.md#keepask)) |

### `learning`

| Setting | Default | What it does |
|---|---|---|
| `learning.brain` | `""` | The AI that looks at finished work; empty uses the concept graph's second-look AI, else your main one. ([guide](wiki/user/settings-guide.md#learningbrain)) |
| `learning.corrections` | `true` | When you correct a skill's answer, the skill keeps it as a lesson. ([guide](wiki/user/settings-guide.md#learningcorrections)) |
| `learning.remember` | `true` | The nightly look back keeps facts you stated in your chats and calls in your how-to-help-me note. ([guide](wiki/user/settings-guide.md#learningremember)) |
| `learning.remember_max` | `3` | The most facts kept in a night. ([guide](wiki/user/settings-guide.md#learningremembermax)) |
| `learning.search` | `true` | A search index of past requests, calls and chats on this computer: `/history`, and the AI's search_history. ([guide](wiki/user/settings-guide.md#learningsearch)) |
| `learning.skill_min_steps` | `5` | How many tool uses a request needs before it's considered for a new skill. ([guide](wiki/user/settings-guide.md#learningskillminsteps)) |
| `learning.skills` | `true` | A request that took many steps can become a skill, or improve the one that does it. ([guide](wiki/user/settings-guide.md#learningskills)) |

### `lidsafe`

| Setting | Default | What it does |
|---|---|---|
| `lidsafe.hours` | `24` | How far ahead your call line holds reminders and the morning line, in hours. ([guide](wiki/user/settings-guide.md#lidsafehours)) |
| `lidsafe.morning` | `"07:30"` | When the morning line comes if no wake-up alarm is set. ([guide](wiki/user/settings-guide.md#lidsafemorning)) |
| `lidsafe.reminders` | `true` | Your reminders still reach the phone while this computer is asleep or off. ([guide](wiki/user/settings-guide.md#lidsafereminders)) |
| `lidsafe.today` | `true` | A morning line on your phone with the day's first class and what's due, even with the lid shut. ([guide](wiki/user/settings-guide.md#lidsafetoday)) |

### `local_helper`

| Setting | Default | What it does |
|---|---|---|
| `local_helper.hold_h` | `24` | Hours a request waits for the internet before it gives up and says so. ([guide](wiki/user/settings-guide.md#localhelperholdh)) |
| `local_helper.max_s` | `1.5` | How fast the helper must answer in its speed test (seconds), or it stays off. ([guide](wiki/user/settings-guide.md#localhelpermaxs)) |
| `local_helper.model` | `""` | Which Ollama model the offline helper uses; empty picks the standard small one. ([guide](wiki/user/settings-guide.md#localhelpermodel)) |
| `local_helper.offer` | `true` | Offer the offline helper once if your free limit keeps running short or the internet often drops. ([guide](wiki/user/settings-guide.md#localhelperoffer)) |
| `local_helper.offline` | `true` | With the internet down: quick things answered here, AI requests wait in the queue until it's back. ([guide](wiki/user/settings-guide.md#localhelperoffline)) |
| `local_helper.on` | `false` | A small model on this computer (about 1 GB) for quick decisions and as a stand-in while the internet is down. ([guide](wiki/user/settings-guide.md#localhelperon)) |
| `local_helper.timeout_s` | `4` | Seconds a quick decision waits for the helper before the rules decide instead. ([guide](wiki/user/settings-guide.md#localhelpertimeouts)) |

### `look`

| Setting | Default | What it does |
|---|---|---|
| `look.being_hints` | `true` | The being's hints: what to click and what each part is (H on the board toggles them). ([guide](wiki/user/settings-guide.md#lookbeinghints)) |
| `look.being_live_waveform` | `true` | The being's YOU lane live: a trace of the microphone's loudness as you speak, the last six seconds. ([guide](wiki/user/settings-guide.md#lookbeinglivewaveform)) |
| `look.being_mood` | `true` | Brain's own mood in the drawing: the fluid's tint and the heart's beat; its pupil and pulse show the three knobs. ([guide](wiki/user/settings-guide.md#lookbeingmood)) |
| `look.being_resting_sparks` | `true` | The being's resting sparks: a low trickle in the brain from what Kurooto does all the time. ([guide](wiki/user/settings-guide.md#lookbeingrestingsparks)) |
| `look.being_status` | `true` | The being as a glance: eyes shut in focus or asleep, the held count by the heart, a glow on the deadline it's uneasy about. ([guide](wiki/user/settings-guide.md#lookbeingstatus)) |
| `look.being_theme` | `"void"` | The being's colours: white light on black, or the page's palette. ([guide](wiki/user/settings-guide.md#lookbeingtheme)) |
| `look.board` | `"being"` | The board: Kurooto as one living body (being), three panes on top (three), or STATUS on the left (classic). ([guide](wiki/user/settings-guide.md#lookboard)) |
| `look.brain_monitor` | `"shown"` | BRAIN's part monitor: shown beside the model, or in a drawer behind a tab. ([guide](wiki/user/settings-guide.md#lookbrainmonitor)) |
| `look.chat_page` | `true` | The Chat page (Alt+H): the phone app's chat on the dashboard, live, with its buttons, and a box to write in it. ([guide](wiki/user/settings-guide.md#lookchatpage)) |
| `look.design` | `"new"` | The dashboard's design: new (sans-serif, rounded panes) or classic (the monospace look of 0.5.18). ([guide](wiki/user/settings-guide.md#lookdesign)) |
| `look.hidden_features` | `[]` | Features hidden from the Features list (they still run if they're on). ([guide](wiki/user/settings-guide.md#lookhiddenfeatures)) |
| `look.layout` | `"dense"` | Dense (everything on one full-screen board) or roomy (bigger panes and type). ([guide](wiki/user/settings-guide.md#looklayout)) |
| `look.links_in` | `"default"` | Where links to other sites open: this computer's default browser, or the browser showing the dashboard. ([guide](wiki/user/settings-guide.md#looklinksin)) |
| `look.palette` | `"kuro"` | The colours of Kurooto's pages and terminals: its own palettes, your desktop's, or a named theme. ([guide](wiki/user/settings-guide.md#lookpalette)) |
| `look.panes` | `[]` | Panes hidden from the dense board: status, systems, notes, terminal. ([guide](wiki/user/settings-guide.md#lookpanes)) |
| `look.projects` | `[]` | Folders of git repositories the PROJECTS box shows; empty uses Research's repositories. ([guide](wiki/user/settings-guide.md#lookprojects)) |
| `look.settings_guide` | `true` | On the Settings page, a line under each setting that says what it does and opens its whole guide entry. ([guide](wiki/user/settings-guide.md#looksettingsguide)) |
| `look.study_mode` | `false` | The dashboard in Study mode: the notes map, the study timer and what's due (Alt+M, `/study mode`). ([guide](wiki/user/settings-guide.md#lookstudymode)) |
| `look.talk_box` | `true` | A small box over the board to talk to Kurooto in plain English (Alt+K). ([guide](wiki/user/settings-guide.md#looktalkbox)) |
| `look.theme_file` | `""` | A colours file of your own (a kitty theme, or matugen or pywal JSON) instead of the desktop's. ([guide](wiki/user/settings-guide.md#lookthemefile)) |

### `mail_digest`

| Setting | Default | What it does |
|---|---|---|
| `mail_digest.at` | `"daily 08:00,18:00"` | When the mail digest checks your Gmail. ([guide](wiki/user/settings-guide.md#maildigestat)) |
| `mail_digest.confidential` | `"count"` | What happens to confidential mail: only counted, or summarised by a model on this computer. ([guide](wiki/user/settings-guide.md#maildigestconfidential)) |
| `mail_digest.confidential_words` | `["confidential", "do not forward", "restricted", "private…` | The markings that make a mail confidential (in its subject, text or a label). ([guide](wiki/user/settings-guide.md#maildigestconfidentialwords)) |
| `mail_digest.first_days` | `3` | How far back (days) the first digest looks. ([guide](wiki/user/settings-guide.md#maildigestfirstdays)) |
| `mail_digest.local_model` | `""` | Which Ollama model summarises confidential mail; empty uses Local AI models' helper. ([guide](wiki/user/settings-guide.md#maildigestlocalmodel)) |
| `mail_digest.mail_in` | `false` | Email in: mail you forward to you+kurooto@ (or label) is filed into your notes, its dates as buttons. ([guide](wiki/user/settings-guide.md#maildigestmailin)) |
| `mail_digest.mail_in_anyone` | `false` | Mail to +kurooto from anyone goes in. A stranger could then write into your notes. ([guide](wiki/user/settings-guide.md#maildigestmailinanyone)) |
| `mail_digest.mail_in_every` | `"every 10m"` | How often Gmail is checked for mail you sent in. ([guide](wiki/user/settings-guide.md#maildigestmailinevery)) |
| `mail_digest.mail_in_label` | `""` | A Gmail label whose mail goes into your notes too, from anyone. ([guide](wiki/user/settings-guide.md#maildigestmailinlabel)) |
| `mail_digest.mail_in_senders` | `[]` | Your other email addresses that may send mail into your notes (your own always can). ([guide](wiki/user/settings-guide.md#maildigestmailinsenders)) |
| `mail_digest.max_messages` | `200` | The most mails looked at per check. ([guide](wiki/user/settings-guide.md#maildigestmaxmessages)) |
| `mail_digest.never_read` | `[]` | Senders, @domains or labels the digest never reads, even if chosen elsewhere. ([guide](wiki/user/settings-guide.md#maildigestneverread)) |
| `mail_digest.own_domain` | `true` | On a school or work account, mail from your own organisation's domain is read too. ([guide](wiki/user/settings-guide.md#maildigestowndomain)) |
| `mail_digest.query` | `""` | A Gmail search: mail it matches is read too, e.g. everything but Promotions and Social. ([guide](wiki/user/settings-guide.md#maildigestquery)) |
| `mail_digest.read` | `[]` | What the AI may read for the digest: senders, @domains or Gmail labels you chose. ([guide](wiki/user/settings-guide.md#maildigestread)) |
| `mail_digest.save_note` | `true` | A copy of each digest goes into your notes (mail/). ([guide](wiki/user/settings-guide.md#maildigestsavenote)) |
| `mail_digest.skip_confidential` | `true` | Mail marked confidential is only counted: never read by the AI, summarised or answered. ([guide](wiki/user/settings-guide.md#maildigestskipconfidential)) |

### `meetings`

| Setting | Default | What it does |
|---|---|---|
| `meetings.after_h` | `3` | Hours after a meeting's start that a voice note or long note counts as notes from it. ([guide](wiki/user/settings-guide.md#meetingsafterh)) |
| `meetings.minutes` | `true` | Notes you send after a meeting with a project's person become minutes, through your AI. ([guide](wiki/user/settings-guide.md#meetingsminutes)) |

### `memory`

| Setting | Default | What it does |
|---|---|---|
| `memory.budget_tokens` | `600` | At most about this much of what's remembered goes with one reply or call (about 4 characters a token). ([guide](wiki/user/settings-guide.md#memorybudgettokens)) |
| `memory.recall` | `true` | Replies and calls are told the few remembered items your message refers to ("as we said on the call"). ([guide](wiki/user/settings-guide.md#memoryrecall)) |
| `memory.thread_days` | `7` | Days an untouched open thread waits before it closes by itself. ([guide](wiki/user/settings-guide.md#memorythreaddays)) |
| `memory.threads` | `true` | What you say you'll do, and tasks you start, become open threads ("did I finish that thing?"). ([guide](wiki/user/settings-guide.md#memorythreads)) |

### `mind`

| Setting | Default | What it does |
|---|---|---|
| `mind.act.more` | `true` | Its trust decides study blocks, reshaped plans, revision packs and keeping its night's cards and lines. ([guide](wiki/user/settings-guide.md#mindactmore)) |
| `mind.anchor_every` | `1000` | How often (in records) Brain notes where its log has got to, besides once a day. ([guide](wiki/user/settings-guide.md#mindanchorevery)) |
| `mind.attention.on` | `true` | A model of its own attention: "what are you thinking about?" is answered from it. ([guide](wiki/user/settings-guide.md#mindattentionon)) |
| `mind.autonomy.enforce` | `false` | Make its trust verdicts bind: it asks first for what it isn't trusted with. ([guide](wiki/user/settings-guide.md#mindautonomyenforce)) |
| `mind.autonomy.on` | `true` | Brain learns from your reactions how far it may act on its own, per class of action (shadow first). ([guide](wiki/user/settings-guide.md#mindautonomyon)) |
| `mind.autonomy.shadow_days` | `21` | Days its trust verdicts are only counted and shown, not used. ([guide](wiki/user/settings-guide.md#mindautonomyshadowdays)) |
| `mind.autonomy.thresholds` | `{}` | Your own trust bars per class of action, over the defaults. ([guide](wiki/user/settings-guide.md#mindautonomythresholds)) |
| `mind.backfill.calls` | `true` | Read past calls (answered or missed, who placed them, how long), never what was said. ([guide](wiki/user/settings-guide.md#mindbackfillcalls)) |
| `mind.backfill.checkins` | `true` | Read which check-ins were asked, answered or skipped each day, never what you said. ([guide](wiki/user/settings-guide.md#mindbackfillcheckins)) |
| `mind.backfill.deadlines` | `true` | Read when past deadlines were due and done (no titles). ([guide](wiki/user/settings-guide.md#mindbackfilldeadlines)) |
| `mind.backfill.events` | `true` | Read Kurooto's own event history: what happened and when. ([guide](wiki/user/settings-guide.md#mindbackfillevents)) |
| `mind.backfill.jobs` | `true` | Read the AI request history: effort, whether it worked, how long (never the words). ([guide](wiki/user/settings-guide.md#mindbackfilljobs)) |
| `mind.backfill.learning` | `true` | Read how many requests and calls a day were indexed (chats left out). ([guide](wiki/user/settings-guide.md#mindbackfilllearning)) |
| `mind.backfill.on` | `false` | Brain reads what Kurooto kept before it was on, once (`/mind backfill`); off until you turn it on. ([guide](wiki/user/settings-guide.md#mindbackfillon)) |
| `mind.backfill.quiz` | `true` | Read your quiz record per day and subject (asked, right, wrong), never the questions. ([guide](wiki/user/settings-guide.md#mindbackfillquiz)) |
| `mind.backfill.study` | `true` | Read the study tracker's time per day, for your real pace in week plans. ([guide](wiki/user/settings-guide.md#mindbackfillstudy)) |
| `mind.beliefs.on` | `true` | Keep where each belief came from (said, saw, inferred, imagined) and how sure it is. ([guide](wiki/user/settings-guide.md#mindbeliefson)) |
| `mind.budget.on` | `true` | The body budget: a few things about Kurooto's own state it tries to keep level, and its drive. ([guide](wiki/user/settings-guide.md#mindbudgeton)) |
| `mind.checkins.surprise` | `true` | The next check-in comes early when the day departs strongly from Brain's forecast. ([guide](wiki/user/settings-guide.md#mindcheckinssurprise)) |
| `mind.console.on` | `true` | The Brain console: a dashboard page (Alt+O) and the phone's Brain view showing what the Brain decided and why. ([guide](wiki/user/settings-guide.md#mindconsoleon)) |
| `mind.context.on` | `true` | Every AI request gets Brain's hints: concepts you're shaky on, and what's on its mind. ([guide](wiki/user/settings-guide.md#mindcontexton)) |
| `mind.dream.cards` | `true` | Each night, 1 to 3 quiz cards for concepts you studied that day that are on your frontier, kept by a tap. ([guide](wiki/user/settings-guide.md#minddreamcards)) |
| `mind.dream.cards_max` | `3` | The most dream cards a night (1 to 3). ([guide](wiki/user/settings-guide.md#minddreamcardsmax)) |
| `mind.dream.lessons` | `true` | Each night, 1 to 3 lines for your how-to-help-me note from the day's outcomes, written only when you tap Keep. ([guide](wiki/user/settings-guide.md#minddreamlessons)) |
| `mind.dream.on` | `true` | Brain goes over the day at night and brings cards, how-to-help lines and a voice line to the morning message. ([guide](wiki/user/settings-guide.md#minddreamon)) |
| `mind.dream.voice` | `true` | One morning line on what the nightly voice learning saw: turns it learned from and any misfire pattern. ([guide](wiki/user/settings-guide.md#minddreamvoice)) |
| `mind.expect.on` | `true` | Each message Kurooto starts says what it expects (a reply, or done within 2 hours), and what came of it is recorded. ([guide](wiki/user/settings-guide.md#mindexpecton)) |
| `mind.feelings.empathy` | `true` | Concern for what it looks after (deadlines, projects, its machine): it notices sooner, speaks more gently. ([guide](wiki/user/settings-guide.md#mindfeelingsempathy)) |
| `mind.feelings.express` | `true` | Brain may say a feeling about something open, through the gate, at most 3 times a week unasked. ([guide](wiki/user/settings-guide.md#mindfeelingsexpress)) |
| `mind.feelings.mood` | `true` | Its mood shapes it: low, it does less unasked, asks first, says less; high, a little bolder. ([guide](wiki/user/settings-guide.md#mindfeelingsmood)) |
| `mind.feelings.on` | `true` | Brain's states about specific things (uneasy, relieved…) and what they make it do inwardly. ([guide](wiki/user/settings-guide.md#mindfeelingson)) |
| `mind.feelings.vocal` | `false` | Let Brain say unasked that it's excited or worried, when it has strong evidence. ([guide](wiki/user/settings-guide.md#mindfeelingsvocal)) |
| `mind.finetune.base` | `""` | The local model's name in Ollama to build the adapter into; empty is the helper model. ([guide](wiki/user/settings-guide.md#mindfinetunebase)) |
| `mind.finetune.base_hf` | `""` | The Hugging Face name of the base model, which the trainer loads. ([guide](wiki/user/settings-guide.md#mindfinetunebasehf)) |
| `mind.finetune.day` | `"sun"` | The night of the week it trains. ([guide](wiki/user/settings-guide.md#mindfinetuneday)) |
| `mind.finetune.min_examples` | `30` | With fewer checked examples than this, it skips the week. ([guide](wiki/user/settings-guide.md#mindfinetuneminexamples)) |
| `mind.finetune.on` | `false` | A weekly local fine-tune of the model on this computer, from checked examples only. ([guide](wiki/user/settings-guide.md#mindfinetuneon)) |
| `mind.finetune.practice` | `true` | Include the harness' practice tasks in training. ([guide](wiki/user/settings-guide.md#mindfinetunepractice)) |
| `mind.finetune.probe_words` | `5` | Words of a forgotten prompt kept to check a new adapter forgot it (3 or more). ([guide](wiki/user/settings-guide.md#mindfinetuneprobewords)) |
| `mind.forecast.holdout` | `0.1` | The share of days a planned action is held back on purpose, to measure what it does. ([guide](wiki/user/settings-guide.md#mindforecastholdout)) |
| `mind.forecast.on` | `true` | Each evening at 21:00, what Brain expects of tomorrow, scored the next evening. ([guide](wiki/user/settings-guide.md#mindforecaston)) |
| `mind.forget.half_lives.default` | `60` | Days for a remembered item to fade to half, when its kind has no own setting. ([guide](wiki/user/settings-guide.md#mindforgethalflivesdefault)) |
| `mind.forget.half_lives.fact` | `90` | Days for a fact about you to fade to half. ([guide](wiki/user/settings-guide.md#mindforgethalflivesfact)) |
| `mind.forget.half_lives.gist` | `30` | Days for a conversation's gist to fade to half. ([guide](wiki/user/settings-guide.md#mindforgethalflivesgist)) |
| `mind.forget.half_lives.project` | `180` | Days for a project fact to fade to half. ([guide](wiki/user/settings-guide.md#mindforgethalflivesproject)) |
| `mind.forget.misses_weeks` | `6` | After this many weeks, a past miss is no longer brought up. ([guide](wiki/user/settings-guide.md#mindforgetmissesweeks)) |
| `mind.forget.on` | `true` | Old things fade from use, old misses stop coming up, and `/forget` goes everywhere Brain kept something. ([guide](wiki/user/settings-guide.md#mindforgeton)) |
| `mind.gate.feelings_per_week` | `3` | How often Brain may say how it feels about something unasked, per week. ([guide](wiki/user/settings-guide.md#mindgatefeelingsperweek)) |
| `mind.gate.max_per_day` | `12` | Messages a day that may come by themselves (Calm's limit applies too: the smaller wins). ([guide](wiki/user/settings-guide.md#mindgatemaxperday)) |
| `mind.gate.max_per_hour` | `3` | Messages an hour that may come by themselves. ([guide](wiki/user/settings-guide.md#mindgatemaxperhour)) |
| `mind.gate.on` | `true` | Brain's gate on everything Kurooto sends by itself: only ever quieter, honest feelings, a shared pool of small touches. ([guide](wiki/user/settings-guide.md#mindgateon)) |
| `mind.gate.touches_per_day` | `3` | Small human touches a day in all (an absence note, a lighter-day line, a feeling). ([guide](wiki/user/settings-guide.md#mindgatetouchesperday)) |
| `mind.hardened` | `false` | The scorekeeper runs as its own system user, so not even a program running as you can change the log. ([guide](wiki/user/settings-guide.md#mindhardened)) |
| `mind.harness.on` | `true` | Nightly on the charger: how it does on tasks it has never seen, and checks of Brain's own promises. ([guide](wiki/user/settings-guide.md#mindharnesson)) |
| `mind.harness.rotate_days` | `30` | The hidden tasks are made new this often (days), so old ones can't be memorised. ([guide](wiki/user/settings-guide.md#mindharnessrotatedays)) |
| `mind.heartbeat.on` | `true` | When this computer is down, your call line also says what the next 12 hours have no guarantee for. ([guide](wiki/user/settings-guide.md#mindheartbeaton)) |
| `mind.improve.on` | `true` | Brain improving itself through gated proposals: nothing changes without the hidden harness and your say-so. ([guide](wiki/user/settings-guide.md#mindimproveon)) |
| `mind.journal.in_notes` | `false` | Also keep Brain's journal as a block in a note of yours. ([guide](wiki/user/settings-guide.md#mindjournalinnotes)) |
| `mind.journal.in_notes_file` | `"Kurooto journal.md"` | The journal note's file name (`.md` is added if missing). ([guide](wiki/user/settings-guide.md#mindjournalinnotesfile)) |
| `mind.journal.in_notes_folder` | `""` | The folder inside your notes the journal note goes in; empty is the top. ([guide](wiki/user/settings-guide.md#mindjournalinnotesfolder)) |
| `mind.journal.on` | `true` | A daily journal of Brain's own states, reasons and mistakes, every line checked against its log. ([guide](wiki/user/settings-guide.md#mindjournalon)) |
| `mind.knobs.on` | `true` | Three knobs: its mood sets how much it explores, arousal how soon it speaks up, calibration whether it asks first. ([guide](wiki/user/settings-guide.md#mindknobson)) |
| `mind.lab.gpu` | `false` | Let lab runs use the graphics card (off: CPU only). ([guide](wiki/user/settings-guide.md#mindlabgpu)) |
| `mind.lab.gpu_hours_per_night` | `2` | The most graphics-card hours the lab uses in a night. ([guide](wiki/user/settings-guide.md#mindlabgpuhourspernight)) |
| `mind.lab.in_repo` | `false` | Keep a project's lab protocol in its `.kurooto` folder (off: in Kurooto's own state). ([guide](wiki/user/settings-guide.md#mindlabinrepo)) |
| `mind.lab.max_per_night` | `40` | The most configurations in one night's batch. ([guide](wiki/user/settings-guide.md#mindlabmaxpernight)) |
| `mind.lab.on` | `true` | Overnight pre-registered experiments on the projects you list (Linux and macOS, in a sandbox). ([guide](wiki/user/settings-guide.md#mindlabon)) |
| `mind.lab.projects` | `[]` | Folders (or repository projects' names) the lab may run experiments on. ([guide](wiki/user/settings-guide.md#mindlabprojects)) |
| `mind.lab.run_wall_s` | `1800` | Seconds one lab run may take before it's stopped. ([guide](wiki/user/settings-guide.md#mindlabrunwalls)) |
| `mind.lab.seed` | `0` | A fixed seed for the sampled configurations; 0 draws a new sample each day. ([guide](wiki/user/settings-guide.md#mindlabseed)) |
| `mind.pest.on` | `true` | Learn for each kind of unprompted message whether it's welcome; send one only when it likely is. ([guide](wiki/user/settings-guide.md#mindpeston)) |
| `mind.plans.on` | `true` | Plans over weeks: which milestones are at risk, from simulated futures. A suggestion, never a push. ([guide](wiki/user/settings-guide.md#mindplanson)) |
| `mind.plans.rollouts` | `1000` | How many simulated futures a plan runs. ([guide](wiki/user/settings-guide.md#mindplansrollouts)) |
| `mind.plans.weeks` | `6` | How far ahead (weeks) the simulated futures look. ([guide](wiki/user/settings-guide.md#mindplansweeks)) |
| `mind.play.minutes_per_night` | `20` | Minutes of play a night, on the charger only. ([guide](wiki/user/settings-guide.md#mindplayminutespernight)) |
| `mind.play.on` | `false` | A little nightly time to explore its own questions on your topics (off until you turn it on). ([guide](wiki/user/settings-guide.md#mindplayon)) |
| `mind.precedents.on` | `false` | Judgement calls between your values are asked once, then followed (off until you turn it on). ([guide](wiki/user/settings-guide.md#mindprecedentson)) |
| `mind.precedents.threshold` | `0.75` | How alike two situations must be (0 to 1) for a precedent to be followed. ([guide](wiki/user/settings-guide.md#mindprecedentsthreshold)) |
| `mind.presence_forecast.busy_hint` | `true` | An add-on's usual busy hours (times only) show as a hint on /mind and Start-by messages. ([guide](wiki/user/settings-guide.md#mindpresenceforecastbusyhint)) |
| `mind.presence_forecast.on` | `true` | Forecast, hour by hour for the next six hours, when you'll be at your desk and free; scored against what the senses then show. ([guide](wiki/user/settings-guide.md#mindpresenceforecaston)) |
| `mind.presence_forecast.prefer` | `true` | Check-ins and calls Kurooto places by itself prefer an hour you're likely free. ([guide](wiki/user/settings-guide.md#mindpresenceforecastprefer)) |
| `mind.presence_forecast.reachable` | `true` | Check-ins and calls Kurooto places by itself go by whether you're reachable: at the desk or on your phone. ([guide](wiki/user/settings-guide.md#mindpresenceforecastreachable)) |
| `mind.presence_forecast.visitors` | `false` | An add-on's usual busy hours also lower the forecast there a little (never a block). ([guide](wiki/user/settings-guide.md#mindpresenceforecastvisitors)) |
| `mind.presence_forecast.within_min` | `60` | How far (minutes) a check-in or a call may move to a likelier hour. ([guide](wiki/user/settings-guide.md#mindpresenceforecastwithinmin)) |
| `mind.promises.on` | `true` | Its own promises ("I'll check back at 6") are noticed, kept, or owned up to first. ([guide](wiki/user/settings-guide.md#mindpromiseson)) |
| `mind.read.asks_per_week` | `2` | How many times a week, at most, it may ask whether the week felt heavier than usual. ([guide](wiki/user/settings-guide.md#mindreadasksperweek)) |
| `mind.read.on` | `true` | Brain's read of how you're doing, from numbers about your days; in shadow mode it only watches. ([guide](wiki/user/settings-guide.md#mindreadon)) |
| `mind.register.on` | `true` | One temperament: its mood and arousal set how long its unprompted words are, its call openers and Voice's pace. ([guide](wiki/user/settings-guide.md#mindregisteron)) |
| `mind.register.templates` | `true` | Its ready-made unprompted messages keep the register's 2, 3 or 4 sentences too, not only what the AI writes. ([guide](wiki/user/settings-guide.md#mindregistertemplates)) |
| `mind.senses.activity` | `false` | The activity stream: the app in front, hashed window titles, saves and commits (never keystrokes, the screen or URLs). ([guide](wiki/user/settings-guide.md#mindsensesactivity)) |
| `mind.senses.intero` | `true` | Its own machine's state every minute: temperatures, memory, battery, disk, AI limits. ([guide](wiki/user/settings-guide.md#mindsensesintero)) |
| `mind.senses.phone` | `"(computed)"` | Each of your phone's sensors, off until you switch it on (here and in the phone app). ([guide](wiki/user/settings-guide.md#mindsensesphone)) |
| `mind.skills.from_demos` | `false` | Also offer skills from what you do over and over (asked once). ([guide](wiki/user/settings-guide.md#mindskillsfromdemos)) |
| `mind.skills.on` | `true` | Solved tasks become tested, reusable skills; each new one starts out asking first. ([guide](wiki/user/settings-guide.md#mindskillson)) |
| `mind.sleep.desk_after_min` | `15` | With desk_holds: how many minutes after you leave the desk its sleep starts. ([guide](wiki/user/settings-guide.md#mindsleepdeskaftermin)) |
| `mind.sleep.desk_holds` | `true` | While you're at this computer, Kurooto doesn't fall asleep: its night starts after you leave. ([guide](wiki/user/settings-guide.md#mindsleepdeskholds)) |
| `mind.sleep.follow_desk` | `true` | Starting a talk at the desk wakes Kurooto, and you at the desk near the night's end is you being up. ([guide](wiki/user/settings-guide.md#mindsleepfollowdesk)) |
| `mind.sleep.follow_external` | `false` | An add-on's reading that you're asleep (a dark, quiet room, you away) starts Kurooto's night there. ([guide](wiki/user/settings-guide.md#mindsleepfollowexternal)) |
| `mind.sleep.follow_owner` | `true` | Its sleep follows yours: bedtime to the alarm, refined by your phone (screen off, dark, charging; first use). ([guide](wiki/user/settings-guide.md#mindsleepfollowowner)) |
| `mind.sleep.on` | `true` | Kurooto sleeps in your sleep window: nothing it starts by itself is sent or said aloud until morning. ([guide](wiki/user/settings-guide.md#mindsleepon)) |
| `mind.sleep.senses_off` | `true` | Asleep, Kurooto's camera and microphone are off: Face presence pauses and Voice stops listening. ([guide](wiki/user/settings-guide.md#mindsleepsensesoff)) |
| `mind.sleep.wake_minutes` | `20` | Woken by its name or a message at night, it dozes off again after this many quiet minutes. ([guide](wiki/user/settings-guide.md#mindsleepwakeminutes)) |
| `mind.sleep.window` | `""` | Set Kurooto's sleep by hand, like 00:30-08:00 (empty: follow your night). ([guide](wiki/user/settings-guide.md#mindsleepwindow)) |
| `mind.status.on` | `true` | One status stream: focus, asleep, messages held, the one thing it's uneasy about, its own mood and arousal. ([guide](wiki/user/settings-guide.md#mindstatuson)) |
| `mind.stimulation.addons` | `true` | Let an add-on feed another device's sensors into its body (light, motion, battery, loudness...). ([guide](wiki/user/settings-guide.md#mindstimulationaddons)) |
| `mind.stimulation.jolt` | `true` | Something sudden (a pickup, something close, a loud room) is felt at once: a jolt, and a fresh look at its mind. ([guide](wiki/user/settings-guide.md#mindstimulationjolt)) |
| `mind.stimulation.on` | `true` | Its senses felt as a body (heat, load, touch), for its feelings and the dashboard. ([guide](wiki/user/settings-guide.md#mindstimulationon)) |
| `mind.story.on` | `true` | One life story every part of Kurooto reads first: a fixed core, then its recent weeks. ([guide](wiki/user/settings-guide.md#mindstoryon)) |
| `mind.story.tokens` | `800` | The life story's summary is at most this many tokens (about 4 characters each). ([guide](wiki/user/settings-guide.md#mindstorytokens)) |
| `mind.study_push.horizon_days` | `7` | How far ahead a deadline can be for Brain to be uneasy about it. ([guide](wiki/user/settings-guide.md#mindstudypushhorizondays)) |
| `mind.study_push.minutes` | `25` | How long a study stretch the morning line offers. ([guide](wiki/user/settings-guide.md#mindstudypushminutes)) |
| `mind.study_push.on` | `true` | One morning line about the subject Brain is most uneasy about (due date, minutes logged, cards due), with Yes and Later. ([guide](wiki/user/settings-guide.md#mindstudypushon)) |
| `mind.study_push.when` | `"daily 07:55"` | When the morning line comes. ([guide](wiki/user/settings-guide.md#mindstudypushwhen)) |
| `mind.talk.met` | `true` | An add-on's chat with someone in the room is a smaller reward for Brain (at most 0.05 a day, 6 meetings). ([guide](wiki/user/settings-guide.md#mindtalkmet)) |
| `mind.talk.on` | `true` | Being talked to is a small reward for Brain (at most 0.2 a day; nothing for answers to its own pings). ([guide](wiki/user/settings-guide.md#mindtalkon)) |
| `mind.tom.attention` | `false` | Hold a message (at most 15 minutes) while you're deep in one project. ([guide](wiki/user/settings-guide.md#mindtomattention)) |
| `mind.tom.false_beliefs` | `true` | When something you were told turns out wrong, tell you once, with the evidence. ([guide](wiki/user/settings-guide.md#mindtomfalsebeliefs)) |
| `mind.tom.on` | `true` | A model of what you know, believe, want and prefer, each row with its source (`/model`). ([guide](wiki/user/settings-guide.md#mindtomon)) |
| `mind.tone.on` | `false` | Tag each message you write with one word (calm, tired…), using the model on this computer only. ([guide](wiki/user/settings-guide.md#mindtoneon)) |
| `mind.values.on` | `true` | Brain learns which kinds of things help (values), never affecting a choice in the shadow days. ([guide](wiki/user/settings-guide.md#mindvalueson)) |
| `mind.values.shadow_days` | `21` | Days learned values are only counted, never used for a choice. ([guide](wiki/user/settings-guide.md#mindvaluesshadowdays)) |
| `mind.why.on` | `true` | "Why this?" under a message Kurooto started says what Brain's gate and door did with it, what it expected, and how many it has sent today. ([guide](wiki/user/settings-guide.md#mindwhyon)) |
| `mind.workspace.arbiter` | `true` | One door for everything Kurooto says by itself: each message bids, and only winners are sent. ([guide](wiki/user/settings-guide.md#mindworkspacearbiter)) |
| `mind.workspace.break_after_min` | `25` | Minutes in one window before switching to another counts as a natural break. ([guide](wiki/user/settings-guide.md#mindworkspacebreakaftermin)) |
| `mind.workspace.breaks` | `true` | A winner that isn't urgent waits for a natural break: a window switch after a long stretch, a phone pickup, a session ending. ([guide](wiki/user/settings-guide.md#mindworkspacebreaks)) |
| `mind.workspace.capacity` | `3` | How many things can be on Brain's mind at once (1 to 3). ([guide](wiki/user/settings-guide.md#mindworkspacecapacity)) |
| `mind.workspace.cycle_s` | `30` | The least gap in seconds between two cycles (events poke it sooner). ([guide](wiki/user/settings-guide.md#mindworkspacecycles)) |
| `mind.workspace.fold_h` | `6` | Hours a message may keep losing at the door before it goes into the evening bundle instead. ([guide](wiki/user/settings-guide.md#mindworkspacefoldh)) |
| `mind.workspace.max_hold_min` | `90` | The longest a winner waits for a break, in minutes (unless Kurooto is asleep). ([guide](wiki/user/settings-guide.md#mindworkspacemaxholdmin)) |
| `mind.workspace.on` | `true` | A small "now" stage that parts compete to enter; only what wins may start a message or act on its own. ([guide](wiki/user/settings-guide.md#mindworkspaceon)) |
| `mind.yield.on` | `true` | The Brain's heavy work waits while your jobs use the graphics card, during a call, on battery or when hot. ([guide](wiki/user/settings-guide.md#mindyieldon)) |
| `mind.yield.prefer_sleep` | `true` | The Brain's nightly work also waits for Kurooto to be asleep (until that night's window ends). ([guide](wiki/user/settings-guide.md#mindyieldprefersleep)) |

### `modules`

| Setting | Default | What it does |
|---|---|---|
| `modules.enabled` | `[]` | The features that are on. The Features page changes it. ([guide](wiki/user/settings-guide.md#modulesenabled)) |

### `notes`

| Setting | Default | What it does |
|---|---|---|
| `notes.layout` | `"kurooto"` | How your notes folder is laid out: Kurooto's folders, or a Zettelkasten. ([guide](wiki/user/settings-guide.md#noteslayout)) |
| `notes.links` | `"wiki"` | How Kurooto links notes: `[[wikilinks]]` or Markdown links. ([guide](wiki/user/settings-guide.md#noteslinks)) |
| `notes.open_with` | `""` | The program that opens a note from the dashboard; empty uses the system's. ([guide](wiki/user/settings-guide.md#notesopenwith)) |
| `notes.paths` | `{}` | Your own place for a kind of note, over the layout's. ([guide](wiki/user/settings-guide.md#notespaths)) |

### `notes_sync`

| Setting | Default | What it does |
|---|---|---|
| `notes_sync.after_jobs` | `2` | Minutes after an AI request finishes that the notes it wrote go up; 0 waits for the timer. ([guide](wiki/user/settings-guide.md#notessyncafterjobs)) |
| `notes_sync.api` | `"https://api.github.com"` | The Git host's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#notessyncapi)) |
| `notes_sync.branch` | `"main"` | The branch your notes sync to (filled in from the repository). ([guide](wiki/user/settings-guide.md#notessyncbranch)) |
| `notes_sync.every` | `"every 10m"` | How often your notes sync. ([guide](wiki/user/settings-guide.md#notessyncevery)) |
| `notes_sync.on_conflict` | `"keep both"` | When a note changed in two places at once: keep both versions, or stop and wait for you. ([guide](wiki/user/settings-guide.md#notessynconconflict)) |
| `notes_sync.remote` | `""` | For tests only: a local repository instead of GitHub. ([guide](wiki/user/settings-guide.md#notessyncremote)) |
| `notes_sync.repo` | `""` | The private GitHub repository your notes sync to. ([guide](wiki/user/settings-guide.md#notessyncrepo)) |
| `notes_sync.share_with_calls` | `true` | Let your call line read notes from your repository during a call while this computer is off. ([guide](wiki/user/settings-guide.md#notessyncsharewithcalls)) |

### `notify`

| Setting | Default | What it does |
|---|---|---|
| `notify.app_chat` | `false` | Kurooto's own messages also show in the phone app's chat, not just on Telegram. ([guide](wiki/user/settings-guide.md#notifyappchat)) |
| `notify.app_kinds` | `["call", "question", "approval"]` | Which kinds of message also reach your phone app. ([guide](wiki/user/settings-guide.md#notifyappkinds)) |
| `notify.calm.bundle_one` | `false` | Send the evening bundle as one long message instead of one by one. ([guide](wiki/user/settings-guide.md#notifycalmbundleone)) |
| `notify.calm.calls` | `1` | How many calls a day may come by themselves; one past it waits in the evening bundle as a call link. ([guide](wiki/user/settings-guide.md#notifycalmcalls)) |
| `notify.calm.evening` | `[]` | Kinds of message that always wait for the evening bundle. ([guide](wiki/user/settings-guide.md#notifycalmevening)) |
| `notify.calm.evening_at` | `"20:00"` | When the evening bundle comes with everything that waited today. ([guide](wiki/user/settings-guide.md#notifycalmeveningat)) |
| `notify.calm.fewer` | `{}` | Kinds of message limited to a number a day; more wait for the evening. ([guide](wiki/user/settings-guide.md#notifycalmfewer)) |
| `notify.calm.habituate` | `{}` | After this many of a kind go unanswered in a row, they wait for the evening until you answer one. ([guide](wiki/user/settings-guide.md#notifycalmhabituate)) |
| `notify.calm.lighter_after` | `true` | After an exam or a heavy day, the next day's limit is halved. ([guide](wiki/user/settings-guide.md#notifycalmlighterafter)) |
| `notify.calm.messages` | `6` | How many messages a day may come by themselves; the rest wait for the evening bundle. ([guide](wiki/user/settings-guide.md#notifycalmmessages)) |
| `notify.calm.monthly` | `true` | Once a month, it names a kind of question you hardly ever answer and offers to turn it off. ([guide](wiki/user/settings-guide.md#notifycalmmonthly)) |
| `notify.calm.on` | `true` | Calm: each message Kurooto sends by itself says why, has Why? and Less of this, and there's a daily limit. ([guide](wiki/user/settings-guide.md#notifycalmon)) |
| `notify.calm.stopped` | `[]` | Kinds of message you stopped with Less of this → Stop. ([guide](wiki/user/settings-guide.md#notifycalmstopped)) |
| `notify.calm.voice_stops` | `true` | "Stop" said over something Kurooto said aloud by itself is noted; after a few, it offers to stop that kind. ([guide](wiki/user/settings-guide.md#notifycalmvoicestops)) |
| `notify.calm.windows` | `{}` | Hours a kind of message may come in; outside them it waits for the evening bundle. ([guide](wiki/user/settings-guide.md#notifycalmwindows)) |
| `notify.desktop` | `true` | Pop-up notifications on this computer. ([guide](wiki/user/settings-guide.md#notifydesktop)) |
| `notify.desktop_kinds` | `["call", "question", "approval", "deadline", "update"]` | Which kinds of message pop up on this computer. ([guide](wiki/user/settings-guide.md#notifydesktopkinds)) |
| `notify.presence.after_min` | `10` | How long Kurooto must be away before going offline or coming back is worth a message. ([guide](wiki/user/settings-guide.md#notifypresenceaftermin)) |
| `notify.presence.channels` | `["telegram"]` | Where the offline and back-online messages go. ([guide](wiki/user/settings-guide.md#notifypresencechannels)) |
| `notify.presence.line` | `true` | While this computer can't speak (asleep, crashed, offline), your call line tells you so. ([guide](wiki/user/settings-guide.md#notifypresenceline)) |
| `notify.presence.line_telegram` | `null` | Whether your call line may keep your bot's token, so it can tell you on Telegram while the computer is away. ([guide](wiki/user/settings-guide.md#notifypresencelinetelegram)) |
| `notify.presence.on` | `true` | Tell you when Kurooto goes offline, and again when it's back with what it caught up on. ([guide](wiki/user/settings-guide.md#notifypresenceon)) |

### `overlay`

| Setting | Default | What it does |
|---|---|---|
| `overlay.code` | `true` | Also run the Python add-ons in its modules/ folder (off: only skills, prompts and settings). ([guide](wiki/user/settings-guide.md#overlaycode)) |
| `overlay.path` | `""` | The full path of your add-ons folder. ([guide](wiki/user/settings-guide.md#overlaypath)) |

### `persona`

| Setting | Default | What it does |
|---|---|---|
| `persona.avoid` | `""` | Things answers should never have, such as emojis or motivational lines. ([guide](wiki/user/settings-guide.md#personaavoid)) |
| `persona.boundaries` | `true` | Health, relationship and money decisions stay yours: Kurooto names who to ask instead. ([guide](wiki/user/settings-guide.md#personaboundaries)) |
| `persona.call_me` | `""` | What the AI calls you: a nickname, your first name, or nothing. ([guide](wiki/user/settings-guide.md#personacallme)) |
| `persona.length` | `""` | How long answers should be, in your own words. ([guide](wiki/user/settings-guide.md#personalength)) |
| `persona.register` | `true` | A short message gets a short answer, a voice note a spoken-style one. ([guide](wiki/user/settings-guide.md#personaregister)) |
| `persona.tone` | `""` | The tone you want answers in, in your own words. ([guide](wiki/user/settings-guide.md#personatone)) |

### `power`

| Setting | Default | What it does |
|---|---|---|
| `power.on_battery` | `"saver"` | What Kurooto does on battery: put off heavy work, carry on as usual, or pause. ([guide](wiki/user/settings-guide.md#poweronbattery)) |

### `presence`

| Setting | Default | What it does |
|---|---|---|
| `presence.owner_here.dashboard` | `true` | Using the dashboard (buttons, Ctrl+K, journal, capture, Study mode) counts as you at the desk. ([guide](wiki/user/settings-guide.md#presenceownerheredashboard)) |
| `presence.owner_here.face` | `true` | Face presence seeing your face counts as you being here (Brain's sense of your day, the forecast). ([guide](wiki/user/settings-guide.md#presenceownerhereface)) |
| `presence.owner_here.phone` | `true` | Using the phone app (chat, buttons, answers, Today) counts as you being around, not at the desk. ([guide](wiki/user/settings-guide.md#presenceownerherephone)) |
| `presence.owner_here.voice` | `true` | Voice ID calling a voice yours, even talk not to Kurooto, counts as you at the desk. ([guide](wiki/user/settings-guide.md#presenceownerherevoice)) |

### `privacy`

| Setting | Default | What it does |
|---|---|---|
| `privacy.allow_hosts` | `[]` | More hosts Kurooto may reach, besides its list and the addresses you set up yourself. ([guide](wiki/user/settings-guide.md#privacyallowhosts)) |
| `privacy.egress` | `"record"` | Count every request Kurooto makes on the internet, also refuse hosts not on the list, or neither. ([guide](wiki/user/settings-guide.md#privacyegress)) |
| `privacy.gist_days` | `0` | Gists are deleted after this many days; 0 keeps them until you `/forget all`. ([guide](wiki/user/settings-guide.md#privacygistdays)) |
| `privacy.gist_model` | `false` | A model on this computer adds a sentence to a call's gist. ([guide](wiki/user/settings-guide.md#privacygistmodel)) |
| `privacy.keep_days` | `0` | Transcripts, AI requests and answers, chats and logs are deleted after this many days; 0 keeps them. ([guide](wiki/user/settings-guide.md#privacykeepdays)) |
| `privacy.keep_gist` | `true` | As a conversation's words fade, it settles into one line of what it decided (`/gists`). ([guide](wiki/user/settings-guide.md#privacykeepgist)) |

### `profile`

| Setting | Default | What it does |
|---|---|---|
| `profile.after_changes` | `10` | Minutes after you change a setting (or turn a feature on or off) that the profile is saved. ([guide](wiki/user/settings-guide.md#profileafterchanges)) |
| `profile.branch` | `"(computed)"` | The branch your saved profile lives on (set by Kurooto). ([guide](wiki/user/settings-guide.md#profilebranch)) |
| `profile.remote` | `""` | For tests only: a local repository instead of GitHub. ([guide](wiki/user/settings-guide.md#profileremote)) |
| `profile.repo` | `""` | Your private GitHub repository for Profile sync; empty uses the one Notes sync uses. ([guide](wiki/user/settings-guide.md#profilerepo)) |
| `profile.when` | `"daily 04:40"` | When your profile is saved each day. ([guide](wiki/user/settings-guide.md#profilewhen)) |

### `projects`

| Setting | Default | What it does |
|---|---|---|
| `projects.check_timeout_s` | `300` | Seconds a project check may run before it's stopped. ([guide](wiki/user/settings-guide.md#projectschecktimeouts)) |
| `projects.checks` | `{}` | A command that checks a project (its tests, a LaTeX build), run after the AI's changes. ([guide](wiki/user/settings-guide.md#projectschecks)) |
| `projects.effort` | `"high"` | How hard your AI thinks about project work. ([guide](wiki/user/settings-guide.md#projectseffort)) |
| `projects.folders` | `{}` | More project folders of yours, by name. ([guide](wiki/user/settings-guide.md#projectsfolders)) |
| `projects.help` | `[]` | The projects your AI may help with (none until you say so). ([guide](wiki/user/settings-guide.md#projectshelp)) |

### `proposals`

| Setting | Default | What it does |
|---|---|---|
| `proposals.inline_lines` | `30` | A change up to this many lines is shown inside the message; a bigger one comes as a file. ([guide](wiki/user/settings-guide.md#proposalsinlinelines)) |
| `proposals.keep_days` | `7` | Days an unanswered proposal is kept, with its scratch folder. ([guide](wiki/user/settings-guide.md#proposalskeepdays)) |
| `proposals.max_files` | `60` | A change touching more files than this isn't proposed. ([guide](wiki/user/settings-guide.md#proposalsmaxfiles)) |
| `proposals.max_kb` | `400` | A bigger change than this (KB) isn't proposed: ask for a smaller part. ([guide](wiki/user/settings-guide.md#proposalsmaxkb)) |
| `proposals.morning` | `"daily 07:30"` | When the night's proposals are told, if Dreaming is off (else in Dreaming's message). ([guide](wiki/user/settings-guide.md#proposalsmorning)) |
| `proposals.notes_edits` | `true` | A change to text already in your notes comes as a proposal (Apply / Change / Discard). ([guide](wiki/user/settings-guide.md#proposalsnotesedits)) |

### `quests`

| Setting | Default | What it does |
|---|---|---|
| `quests.days` | `7` | How many days the first-week quests run. ([guide](wiki/user/settings-guide.md#questsdays)) |
| `quests.when` | `"daily 18:00"` | When the day's first-week quest comes. ([guide](wiki/user/settings-guide.md#questswhen)) |

### `quiz`

| Setting | Default | What it does |
|---|---|---|
| `quiz.by_call` | `false` | /quiz, "quiz me" and quiz check-ins ring you instead of coming as text. ([guide](wiki/user/settings-guide.md#quizbycall)) |
| `quiz.call_min` | `10` | Minutes a quiz call is meant to take. ([guide](wiki/user/settings-guide.md#quizcallmin)) |
| `quiz.exam_daily` | `""` | In exam mode, a practice check-in every day at this time; empty: never. ([guide](wiki/user/settings-guide.md#quizexamdaily)) |
| `quiz.exam_per_session` | `6` | Questions in one quiz while exam mode is on. ([guide](wiki/user/settings-guide.md#quizexampersession)) |
| `quiz.links` | `false` | Recall cards from the links in your concept graph come by themselves. ([guide](wiki/user/settings-guide.md#quizlinks)) |
| `quiz.links_at` | `"daily 11:00,16:00,20:00"` | When a link card may come (never during a class, focus time or the night). ([guide](wiki/user/settings-guide.md#quizlinksat)) |
| `quiz.links_check` | `false` | A model on this computer says how close your answer to a link card came. ([guide](wiki/user/settings-guide.md#quizlinkscheck)) |
| `quiz.links_per_day` | `3` | The most link cards in a day (at most 5). ([guide](wiki/user/settings-guide.md#quizlinksperday)) |
| `quiz.offer_at` | `"19:00"` | The evening before a quiz or exam, practice is offered from this time; empty: never. ([guide](wiki/user/settings-guide.md#quizofferat)) |
| `quiz.per_session` | `3` | Questions in one quiz. ([guide](wiki/user/settings-guide.md#quizpersession)) |

### `quota`

| Setting | Default | What it does |
|---|---|---|
| `quota.background_pct` | `70` | The share of an AI's daily limit background work may use before it waits for the reset. ([guide](wiki/user/settings-guide.md#quotabackgroundpct)) |
| `quota.limits` | `{}` | Your own daily limits per AI, which win over the ones Kurooto learned. ([guide](wiki/user/settings-guide.md#quotalimits)) |
| `quota.local` | `"quick"` | What a model on this computer takes over to spare the free limit. ([guide](wiki/user/settings-guide.md#quotalocal)) |
| `quota.on` | `true` | Keep part of each AI's free limit for what you're waiting on, so background work never uses it all. ([guide](wiki/user/settings-guide.md#quotaon)) |
| `quota.soft` | `"learned"` | Whether a limit Kurooto only measured makes background work wait, or is just shown. ([guide](wiki/user/settings-guide.md#quotasoft)) |

### `remember`

| Setting | Default | What it does |
|---|---|---|
| `remember.recheck_days` | `90` | A kept line that hasn't come up in this many days gets one "Still true?"; 0: never. ([guide](wiki/user/settings-guide.md#rememberrecheckdays)) |

### `reminders`

| Setting | Default | What it does |
|---|---|---|
| `reminders.places` | `false` | Location reminders: "remind me when I reach the library to …". ([guide](wiki/user/settings-guide.md#remindersplaces)) |

### `repair`

| Setting | Default | What it does |
|---|---|---|
| `repair.on` | `true` | When a short request could mean either of two things, ask which with both as buttons. ([guide](wiki/user/settings-guide.md#repairon)) |

### `reply_drafts`

| Setting | Default | What it does |
|---|---|---|
| `reply_drafts.ask_days` | `3` | Days the Send / Edit / Discard question on a draft stays open. ([guide](wiki/user/settings-guide.md#replydraftsaskdays)) |
| `reply_drafts.per_day` | `5` | The most reply drafts written in a day. ([guide](wiki/user/settings-guide.md#replydraftsperday)) |

### `repo_projects`

| Setting | Default | What it does |
|---|---|---|
| `repo_projects.github_extras` | `true` | With gh signed in: the repository's description, topics, open issues and milestones too. ([guide](wiki/user/settings-guide.md#repoprojectsgithubextras)) |
| `repo_projects.max_mb` | `50` | The most of a cloned repository's files that are checked out to be read, in MB (history isn't counted). ([guide](wiki/user/settings-guide.md#repoprojectsmaxmb)) |
| `repo_projects.on` | `true` | Set a project up from its repository: `/project add` and "set up my project from github.com/…". ([guide](wiki/user/settings-guide.md#repoprojectson)) |
| `repo_projects.refresh` | `true` | Each night, watched repositories are looked at again: README, docs, releases, milestones. ([guide](wiki/user/settings-guide.md#repoprojectsrefresh)) |
| `repo_projects.refresh_at` | `"daily 04:20"` | When the nightly repository refresh runs. ([guide](wiki/user/settings-guide.md#repoprojectsrefreshat)) |

### `research`

| Setting | Default | What it does |
|---|---|---|
| `research.about` | `""` | What you work on, in a sentence or two: the AI uses it to pick papers for you. ([guide](wiki/user/settings-guide.md#researchabout)) |
| `research.endpoints.arxiv` | `"https://export.arxiv.org/api/query"` | arXiv's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#researchendpointsarxiv)) |
| `research.endpoints.biorxiv` | `"https://api.biorxiv.org/details"` | bioRxiv's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#researchendpointsbiorxiv)) |
| `research.endpoints.pubmed` | `"https://eutils.ncbi.nlm.nih.gov/entrez/eutils"` | PubMed's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#researchendpointspubmed)) |
| `research.feeds` | `[]` | Where papers come from: arXiv categories with keywords, RSS feeds, and more. ([guide](wiki/user/settings-guide.md#researchfeeds)) |
| `research.idle_days` | `4` | After this many days without commits, ask about a project; 0: never. ([guide](wiki/user/settings-guide.md#researchidledays)) |
| `research.idle_when` | `"daily 18:00"` | When the quiet-project check runs. ([guide](wiki/user/settings-guide.md#researchidlewhen)) |
| `research.log_when` | `"daily 23:30"` | When the day's commits and runs are written into your project logs. ([guide](wiki/user/settings-guide.md#researchlogwhen)) |
| `research.max_papers` | `8` | The most papers in one digest (1 to 30). ([guide](wiki/user/settings-guide.md#researchmaxpapers)) |
| `research.papers` | `"weekly mon 08:00"` | When the paper digest comes. ([guide](wiki/user/settings-guide.md#researchpapers)) |
| `research.projects` | `{}` | Which project each repository belongs to (its notes go in research/<project>/). ([guide](wiki/user/settings-guide.md#researchprojects)) |
| `research.rank` | `true` | Your AI picks the papers and says why; off, the newest come as they are. ([guide](wiki/user/settings-guide.md#researchrank)) |
| `research.remind_by_call` | `true` | "Remind me tomorrow" on a quiet-project question is a call at 18:00. ([guide](wiki/user/settings-guide.md#researchremindbycall)) |
| `research.repo_runs` | `"runs"` | The folder in each repository where your scripts keep their runs (its index.csv); empty: don't read. ([guide](wiki/user/settings-guide.md#researchreporuns)) |
| `research.repos` | `[]` | Your code repositories on this computer, for project logs and quiet-project questions. ([guide](wiki/user/settings-guide.md#researchrepos)) |
| `research.save_note` | `false` | Keep each paper digest as a note in your inbox too. ([guide](wiki/user/settings-guide.md#researchsavenote)) |
| `research.topics` | `[]` | Old-style keywords searched across all of arXiv; `research.feeds` is the newer way. ([guide](wiki/user/settings-guide.md#researchtopics)) |
| `research.window_days` | `7` | How far back each digest looks, in days. ([guide](wiki/user/settings-guide.md#researchwindowdays)) |
| `research.zotero` | `"auto"` | Put papers into Zotero with one tap: the app here, the web API with your key, or no Zotero buttons. ([guide](wiki/user/settings-guide.md#researchzotero)) |
| `research.zotero_links` | `true` | Notes that link a paper you put in Zotero get a link to its Zotero item. ([guide](wiki/user/settings-guide.md#researchzoterolinks)) |

### `research_addon`

| Setting | Default | What it does |
|---|---|---|
| `research_addon.latex` | `true` | The LaTeX tracker: a nightly build of the documents you attach with `/latex add`. ([guide](wiki/user/settings-guide.md#researchaddonlatex)) |
| `research_addon.latex_morning` | `"daily 08:00"` | When the morning line comes (only when a build broke or you wrote something). ([guide](wiki/user/settings-guide.md#researchaddonlatexmorning)) |
| `research_addon.latex_repos` | `[]` | The LaTeX documents you attached with `/latex add`. ([guide](wiki/user/settings-guide.md#researchaddonlatexrepos)) |
| `research_addon.latex_timeout_min` | `15` | Minutes a build may take before it's stopped and counted as an error. ([guide](wiki/user/settings-guide.md#researchaddonlatextimeoutmin)) |
| `research_addon.latex_when` | `"daily 03:30"` | When your attached LaTeX documents are built each night. ([guide](wiki/user/settings-guide.md#researchaddonlatexwhen)) |
| `research_addon.members_off` | `[]` | Parts of the Research add-on you switched off on its card (they stay off when it's turned on). ([guide](wiki/user/settings-guide.md#researchaddonmembersoff)) |
| `research_addon.run_compare` | `true` | Run compare: `/runs` and `kurooto runlog diff A B` (part of the Research add-on). ([guide](wiki/user/settings-guide.md#researchaddonruncompare)) |

### `retro`

| Setting | Default | What it does |
|---|---|---|
| `retro.fixes` | `true` | Make data fixes it's sure of (two copies of one deadline become one), with Undo. ([guide](wiki/user/settings-guide.md#retrofixes)) |
| `retro.journal` | `true` | The look back reads today's journal note. ([guide](wiki/user/settings-guide.md#retrojournal)) |
| `retro.max_proposals` | `3` | The most changes one look back proposes. ([guide](wiki/user/settings-guide.md#retromaxproposals)) |
| `retro.no_days` | `30` | How long a No keeps an idea away, in days. ([guide](wiki/user/settings-guide.md#retronodays)) |
| `retro.observe_days` | `7` | How long Observe longer (and `/observe` without a length) watches, in days. ([guide](wiki/user/settings-guide.md#retroobservedays)) |
| `retro.routine_weeks` | `3` | On how many different weeks something must happen before it's a routine. ([guide](wiki/user/settings-guide.md#retroroutineweeks)) |
| `retro.routines` | `true` | Propose a routine it sees in your records (the same thing at the same time, 3+ weeks). ([guide](wiki/user/settings-guide.md#retroroutines)) |
| `retro.transcripts` | `true` | The look back reads today's call transcripts. ([guide](wiki/user/settings-guide.md#retrotranscripts)) |
| `retro.when` | `"daily 23:50"` | When the nightly look back runs; `weekly sun 21:00` looks back over the whole week instead. ([guide](wiki/user/settings-guide.md#retrowhen)) |

### `runall`

| Setting | Default | What it does |
|---|---|---|
| `runall.on` | `true` | `/run all` and `kurooto run all`: every nightly process that's on, now, one after another. ([guide](wiki/user/settings-guide.md#runallon)) |

### `skills`

| Setting | Default | What it does |
|---|---|---|
| `skills.auto_pack` | `"ask"` | The evening before a quiz or exam, a revision pack: ask first, build it, or never. ([guide](wiki/user/settings-guide.md#skillsautopack)) |
| `skills.auto_pack_after` | `"16:00"` | Revision packs aren't offered before this time of day (12 to 36 hours before the exam). ([guide](wiki/user/settings-guide.md#skillsautopackafter)) |

### `sorter`

| Setting | Default | What it does |
|---|---|---|
| `sorter.ai` | `true` | Ask your AI about a note the rules can't place; off, rules only. ([guide](wiki/user/settings-guide.md#sorterai)) |
| `sorter.at` | `"daily 03:30"` | When the nightly sorting pass runs (`/sort now` runs one any time). ([guide](wiki/user/settings-guide.md#sorterat)) |
| `sorter.duplicates` | `true` | A note in the scratch folder that copies one you have is asked about, not filed. ([guide](wiki/user/settings-guide.md#sorterduplicates)) |
| `sorter.folder` | `"inbox"` | The scratch folder inside your notes: what lands here is sorted into place. ([guide](wiki/user/settings-guide.md#sorterfolder)) |
| `sorter.learn` | `true` | A note you move again after it was filed teaches the sorter where such notes go. ([guide](wiki/user/settings-guide.md#sorterlearn)) |
| `sorter.min_conf` | `0.75` | How sure a guess must be (0 to 1) before a note is moved; below it, you get Move buttons. ([guide](wiki/user/settings-guide.md#sorterminconf)) |
| `sorter.per_night` | `20` | The most notes the sorter moves in one day. ([guide](wiki/user/settings-guide.md#sorterpernight)) |
| `sorter.read_files` | `false` | Documents dropped in the scratch folder (PDF, Word, slides, text) become notes. ([guide](wiki/user/settings-guide.md#sorterreadfiles)) |
| `sorter.read_mb` | `25` | The biggest file the sorter reads, in MB. ([guide](wiki/user/settings-guide.md#sorterreadmb)) |
| `sorter.recheck` | `true` | Weekly: a note it moved that now clearly fits another folder moves once more (with Undo). ([guide](wiki/user/settings-guide.md#sorterrecheck)) |
| `sorter.settle_min` | `10` | A note touched in the last this-many minutes is left alone (you may still be writing it). ([guide](wiki/user/settings-guide.md#sortersettlemin)) |

### `sources`

| Setting | Default | What it does |
|---|---|---|
| `sources.budget` | `24000` | Characters of notes, books and class material in all, per answer. ([guide](wiki/user/settings-guide.md#sourcesbudget)) |
| `sources.cap.book` | `12000` | The most characters from books in one answer. ([guide](wiki/user/settings-guide.md#sourcescapbook)) |
| `sources.cap.classroom` | `10000` | The most characters from class material in one answer. ([guide](wiki/user/settings-guide.md#sourcescapclassroom)) |
| `sources.cap.own` | `12000` | The most characters from your own notes in one answer. ([guide](wiki/user/settings-guide.md#sourcescapown)) |
| `sources.mix` | `"(computed)"` | How much each kind of source counts in answers: your notes, books, class material. ([guide](wiki/user/settings-guide.md#sourcesmix)) |
| `sources.prefer` | `[]` | An order of sources instead of the mix: the first counts most. ([guide](wiki/user/settings-guide.md#sourcesprefer)) |
| `sources.subjects` | `{}` | A different mix or order for one subject. ([guide](wiki/user/settings-guide.md#sourcessubjects)) |

### `space`

| Setting | Default | What it does |
|---|---|---|
| `space.backups_max_age_days` | `0` | Backup zips older than this (days) go; 0: no limit (`backups.keep` still applies). ([guide](wiki/user/settings-guide.md#spacebackupsmaxagedays)) |
| `space.backups_max_gb` | `3.0` | The most the backup zips may take in all (GB); 0: no limit. The newest is never removed. ([guide](wiki/user/settings-guide.md#spacebackupsmaxgb)) |
| `space.cache_days` | `14` | Downloads, made zips and cut-off downloads older than this (days) go. ([guide](wiki/user/settings-guide.md#spacecachedays)) |
| `space.jobs_days` | `60` | Finished AI requests older than this (days) are forgotten. ([guide](wiki/user/settings-guide.md#spacejobsdays)) |
| `space.log_mb` | `20` | A log file bigger than this (MB) is cut to its newest part. ([guide](wiki/user/settings-guide.md#spacelogmb)) |
| `space.undo_days` | `30` | The concept graph's before-copies and unfinished work files older than this (days) go. ([guide](wiki/user/settings-guide.md#spaceundodays)) |
| `space.when` | `"weekly sun 04:30"` | When the Space keeper clears Kurooto's own leftovers by itself. ([guide](wiki/user/settings-guide.md#spacewhen)) |

### `startby`

| Setting | Default | What it does |
|---|---|---|
| `startby.ask_exams` | `true` | The first time a subject has an exam, ask how long its exams take you to prepare for. ([guide](wiki/user/settings-guide.md#startbyaskexams)) |
| `startby.crunch_weeks` | `4` | Weeks the Sunday summary looks ahead for crunch weeks (more work due than free time); 0: none. ([guide](wiki/user/settings-guide.md#startbycrunchweeks)) |
| `startby.exam_by_subject` | `{}` | Hours to prepare for a subject's exams, where it differs from the usual. ([guide](wiki/user/settings-guide.md#startbyexambysubject)) |
| `startby.horizon_days` | `35` | Deadlines due this far ahead (in days) get a start-by date. ([guide](wiki/user/settings-guide.md#startbyhorizondays)) |
| `startby.learn_window` | `true` | Once a week, move the window to when you're actually up, with one line and Undo. ([guide](wiki/user/settings-guide.md#startbylearnwindow)) |
| `startby.min_gap_min` | `30` | Gaps between classes and events shorter than this (minutes) don't count as free time. ([guide](wiki/user/settings-guide.md#startbymingapmin)) |
| `startby.negotiate` | `true` | A deadline that keeps slipping gets a reshaped plan once a day instead of the same reminder again. ([guide](wiki/user/settings-guide.md#startbynegotiate)) |
| `startby.share` | `40` | The share of your free time (in %) that goes to deadlines; the rest is for everything else. ([guide](wiki/user/settings-guide.md#startbyshare)) |
| `startby.sizes.exam` | `10` | Hours to prepare for an exam, unless its subject has its own. ([guide](wiki/user/settings-guide.md#startbysizesexam)) |
| `startby.sizes.other` | `2` | Hours any other deadline takes. ([guide](wiki/user/settings-guide.md#startbysizesother)) |
| `startby.sizes.problem_set` | `3` | Hours a problem set or homework takes. ([guide](wiki/user/settings-guide.md#startbysizesproblemset)) |
| `startby.sizes.quiz` | `2` | Hours to prepare for a quiz. ([guide](wiki/user/settings-guide.md#startbysizesquiz)) |
| `startby.sizes.report` | `12` | Hours a report, essay, project or presentation takes. ([guide](wiki/user/settings-guide.md#startbysizesreport)) |
| `startby.tell` | `true` | A message on a deadline's start-by day (only when that's two days or more before it's due). ([guide](wiki/user/settings-guide.md#startbytell)) |
| `startby.when` | `"daily 08:00"` | When the day's "Time to start" messages come (they wait out quiet hours). ([guide](wiki/user/settings-guide.md#startbywhen)) |
| `startby.window` | `"09:00-22:00"` | The hours of each day that count as free time for planning deadlines. ([guide](wiki/user/settings-guide.md#startbywindow)) |

### `study`

| Setting | Default | What it does |
|---|---|---|
| `study.break_min` | `5` | Minutes of break the Study mode timer gives after each focus session. ([guide](wiki/user/settings-guide.md#studybreakmin)) |
| `study.daily_note` | `"23:45"` | When the day's study hours go into your daily note; none: never. ([guide](wiki/user/settings-guide.md#studydailynote)) |
| `study.focus_min` | `25` | Study mode's timer: minutes of focus (calls and messages wait, the time is logged). ([guide](wiki/user/settings-guide.md#studyfocusmin)) |
| `study.idle_min` | `5` | Minutes without activity before study time stops counting. ([guide](wiki/user/settings-guide.md#studyidlemin)) |
| `study.keywords` | `{}` | Extra words per subject that count a window for it. ([guide](wiki/user/settings-guide.md#studykeywords)) |
| `study.research_paths` | `[]` | Words or folders whose windows count as Research time. ([guide](wiki/user/settings-guide.md#studyresearchpaths)) |
| `study.sample_s` | `30` | Seconds between looks at the window you're working in. ([guide](wiki/user/settings-guide.md#studysamples)) |
| `study.timer_ends_mode` | `false` | When a focus ends, Study mode ends too, instead of starting a break. ([guide](wiki/user/settings-guide.md#studytimerendsmode)) |

### `studypack`

| Setting | Default | What it does |
|---|---|---|
| `studypack.cited_pages` | `400` | Pages of the readings your class cites ("B&D S2.3") a study pack takes whole, past the usual 250; `0`: off. ([guide](wiki/user/settings-guide.md#studypackcitedpages)) |
| `studypack.extra` | `""` | Your own rules for the other AI, added to the end of every study pack's prompt. ([guide](wiki/user/settings-guide.md#studypackextra)) |
| `studypack.instructions` | `true` | Your own extra lines and a format phrase ("pdf too") go into the study pack's prompt. ([guide](wiki/user/settings-guide.md#studypackinstructions)) |

### `subjects`

| Setting | Default | What it does |
|---|---|---|
| `subjects.catch_up` | `true` | A class you missed gets a catch-up task and a lecture note to fill in. ([guide](wiki/user/settings-guide.md#subjectscatchup)) |
| `subjects.exam_periods` | `[]` | Exam periods: no classes then, exams instead. ([guide](wiki/user/settings-guide.md#subjectsexamperiods)) |
| `subjects.holidays` | `[]` | Days with no classes. ([guide](wiki/user/settings-guide.md#subjectsholidays)) |
| `subjects.list` | `[]` | Your subjects: each one's name, short names and notes folder. ([guide](wiki/user/settings-guide.md#subjectslist)) |
| `subjects.margin_min` | `5` | Minutes around a class when calls already wait (walking in, settling down). ([guide](wiki/user/settings-guide.md#subjectsmarginmin)) |
| `subjects.no_calls_in_class` | `true` | No calls while a class is on. ([guide](wiki/user/settings-guide.md#subjectsnocallsinclass)) |
| `subjects.term_ends` | `""` | The last day of classes; no classes are expected after it. ([guide](wiki/user/settings-guide.md#subjectstermends)) |
| `subjects.term_note` | `""` | The note that holds your term's dates and timetable, read whenever it changes. ([guide](wiki/user/settings-guide.md#subjectstermnote)) |
| `subjects.timetable` | `[]` | Your weekly classes: subject, day, start and end. ([guide](wiki/user/settings-guide.md#subjectstimetable)) |

### `telegram`

| Setting | Default | What it does |
|---|---|---|
| `telegram.allowed_users` | `[]` | The Telegram accounts that may use your bot (set when you pair). ([guide](wiki/user/settings-guide.md#telegramallowedusers)) |
| `telegram.api_base` | `"https://api.telegram.org"` | Telegram's API address. Leave it alone. ([guide](wiki/user/settings-guide.md#telegramapibase)) |
| `telegram.chat_id` | `null` | Your chat with the bot (set when you pair; don't change by hand). ([guide](wiki/user/settings-guide.md#telegramchatid)) |
| `telegram.menu` | `true` | The bot's "/" menu lists the commands of the features you have on. ([guide](wiki/user/settings-guide.md#telegrammenu)) |
| `telegram.silent_kinds` | `["call"]` | Kinds of message sent to Telegram without a sound. ([guide](wiki/user/settings-guide.md#telegramsilentkinds)) |

### `terminal`

| Setting | Default | What it does |
|---|---|---|
| `terminal.default` | `false` | Make Kurooto Terminal your default terminal (turning it off undoes it). ([guide](wiki/user/settings-guide.md#terminaldefault)) |
| `terminal.default_opens` | `"shell"` | As your default terminal, what a launch opens: one shell tab, or the whole window. ([guide](wiki/user/settings-guide.md#terminaldefaultopens)) |
| `terminal.font_size` | `11` | The Kurooto Terminal's font size. ([guide](wiki/user/settings-guide.md#terminalfontsize)) |
| `terminal.kitty` | `true` | Linux and macOS: use kitty (yours, or Kurooto's copy); off uses your usual terminal, a window per tab. ([guide](wiki/user/settings-guide.md#terminalkitty)) |
| `terminal.shell` | `"auto"` | Which shell the terminal runs: fish if you have it, else yours, or one you name. ([guide](wiki/user/settings-guide.md#terminalshell)) |
| `terminal.tabs` | `["agent", "shell", "chat", "logs"]` | The Kurooto Terminal's tabs, in order: your AI's program, your shell, Kurooto chat, the log. ([guide](wiki/user/settings-guide.md#terminaltabs)) |
| `terminal.top` | `"left"` | Where `kurooto top` goes: a column beside the first tab, a tab of its own, or nowhere. ([guide](wiki/user/settings-guide.md#terminaltop)) |

### `turnon`

| Setting | Default | What it does |
|---|---|---|
| `turnon.offer` | `true` | When you ask for something a feature that's off would do, offer to turn it on. ([guide](wiki/user/settings-guide.md#turnonoffer)) |

### `uninstall`

| Setting | Default | What it does |
|---|---|---|
| `uninstall.offer` | `true` | When you turn a feature off, ask whether to remove what Kurooto installed for it (a model, a program), with its size. ([guide](wiki/user/settings-guide.md#uninstalloffer)) |
| `uninstall.with_programs` | `true` | `kurooto uninstall` also removes the programs and models Kurooto installed for you, not only Kurooto itself. ([guide](wiki/user/settings-guide.md#uninstallwithprograms)) |

### `updates`

| Setting | Default | What it does |
|---|---|---|
| `updates.channel` | `"stable"` | Stable releases, or beta for every version the day it's signed. ([guide](wiki/user/settings-guide.md#updateschannel)) |
| `updates.exam_hold` | `true` | Nothing installs in an exam period or within a day of a quiz or exam. ([guide](wiki/user/settings-guide.md#updatesexamhold)) |
| `updates.mode` | `"night"` | How updates happen: by themselves at night, after asking you, or not at all. ([guide](wiki/user/settings-guide.md#updatesmode)) |
| `updates.staged` | `false` | Wait until a release has been out a while (and not during exams) before installing it; critical ones don't wait. ([guide](wiki/user/settings-guide.md#updatesstaged)) |
| `updates.wait_hours` | `48` | Hours a new version must have been out before it's installed. ([guide](wiki/user/settings-guide.md#updateswaithours)) |
| `updates.window` | `["03:00", "05:00"]` | The hours an automatic update may switch versions. ([guide](wiki/user/settings-guide.md#updateswindow)) |

### `voice`

| Setting | Default | What it does |
|---|---|---|
| `voice.addons.chat` | `true` | Let an add-on have Kurooto chat with someone who isn't you, the guest way: no tools, none of your data. ([guide](wiki/user/settings-guide.md#voiceaddonschat)) |
| `voice.addons.listen` | `true` | Let an add-on take one stretch of speech at a time through the microphone (written out here, never sent). ([guide](wiki/user/settings-guide.md#voiceaddonslisten)) |
| `voice.audio.backend` | `"auto"` | How Kurooto plays and records sound: PipeWire's own tools, or the PortAudio library inside Kurooto. ([guide](wiki/user/settings-guide.md#voiceaudiobackend)) |
| `voice.listen.after_speak_s` | `6` | Seconds after it spoke during which a question counts as an answer to it. ([guide](wiki/user/settings-guide.md#voicelistenafterspeaks)) |
| `voice.listen.after_talk` | `true` | When a talk at the desk ends, its text goes where a call's does: transcripts, open threads, a line in the day's note. ([guide](wiki/user/settings-guide.md#voicelistenaftertalk)) |
| `voice.listen.auto_gain` | `true` | Hearing follows the room: speech must stand above its noise, and a quiet voice is evened up. ([guide](wiki/user/settings-guide.md#voicelistenautogain)) |
| `voice.listen.auto_gain_snr_db` | `6` | How far above the room's noise speech must be to count, in dB. ([guide](wiki/user/settings-guide.md#voicelistenautogainsnrdb)) |
| `voice.listen.barge_in` | `true` | Talk over Kurooto while it speaks to stop it: "stop", a new question, or anything you want to say. ([guide](wiki/user/settings-guide.md#voicelistenbargein)) |
| `voice.listen.calls` | `false` | Keep listening while you're on a phone call (off: listening pauses during calls). ([guide](wiki/user/settings-guide.md#voicelistencalls)) |
| `voice.listen.careful_name` | `true` | When someone else may be talking, its name wakes Kurooto only said first, as a call ("Kurooto, what's ..."). ([guide](wiki/user/settings-guide.md#voicelistencarefulname)) |
| `voice.listen.chatter_s` | `60` | Speech here that wasn't to Kurooto (any voice) this many seconds ago makes it careful with its name. ([guide](wiki/user/settings-guide.md#voicelistenchatters)) |
| `voice.listen.close_s` | `8` | Seconds of nothing said to it before the spoken conversation closes. ([guide](wiki/user/settings-guide.md#voicelistencloses)) |
| `voice.listen.conversation_follow_s` | `4` | In conversation mode, a reply to what Kurooto just said counts only this soon after it. ([guide](wiki/user/settings-guide.md#voicelistenconversationfollows)) |
| `voice.listen.conversation_mode` | `true` | While another voice is here, Kurooto stays out of people talking: only its name said to it opens a talk. ([guide](wiki/user/settings-guide.md#voicelistenconversationmode)) |
| `voice.listen.conversation_s` | `60` | Seconds after the other person last spoke before Kurooto stops staying out of the conversation. ([guide](wiki/user/settings-guide.md#voicelistenconversations)) |
| `voice.listen.count_voices` | `false` | Two faces close to the camera plus a voice that isn't yours: people talking to each other, not to Kurooto. ([guide](wiki/user/settings-guide.md#voicelistencountvoices)) |
| `voice.listen.device` | `""` | Which microphone to use; empty is the system's default. ([guide](wiki/user/settings-guide.md#voicelistendevice)) |
| `voice.listen.early` | `true` | Write the words out at your first short pause, so the turn goes on the moment you've finished. ([guide](wiki/user/settings-guide.md#voicelistenearly)) |
| `voice.listen.face_near` | `0.5` | How close counts: a face at least this share of your usual face height at the desk (0.5 is about twice as far). ([guide](wiki/user/settings-guide.md#voicelistenfacenear)) |
| `voice.listen.face_yaw_deg` | `35` | How directly someone must face the camera: turned at most this many degrees away (an estimate). ([guide](wiki/user/settings-guide.md#voicelistenfaceyawdeg)) |
| `voice.listen.fast_brain` | `"same"` | Which AI answers plain chat said aloud: your AI as usual, the model on this computer, or the quickest. ([guide](wiki/user/settings-guide.md#voicelistenfastbrain)) |
| `voice.listen.follow_s` | `20` | After Kurooto answers, what the same voice says this many seconds after counts as said to it, statements too. ([guide](wiki/user/settings-guide.md#voicelistenfollows)) |
| `voice.listen.language` | `""` | The language you speak, e.g. `en` or `hi`; empty works it out each time. ([guide](wiki/user/settings-guide.md#voicelistenlanguage)) |
| `voice.listen.learn_nightly` | `true` | Every night Kurooto learns from how its voice turns went: ones you carried on with, and ones you told off. ([guide](wiki/user/settings-guide.md#voicelistenlearnnightly)) |
| `voice.listen.levels` | `true` | Show the microphone's loudness as a waveform on the dashboard (numbers only). ([guide](wiki/user/settings-guide.md#voicelistenlevels)) |
| `voice.listen.live` | `false` | Your own turns answered by Gemini Live, speech to speech, in about a second. Their sound goes to Google. ([guide](wiki/user/settings-guide.md#voicelistenlive)) |
| `voice.listen.look_anyone` | `true` | Anyone's look opens the conversation, not only yours: a guest looking at it can talk to it too. ([guide](wiki/user/settings-guide.md#voicelistenlookanyone)) |
| `voice.listen.look_away_s` | `3.0` | Looking away this long, before you've said anything, closes it again. ([guide](wiki/user/settings-guide.md#voicelistenlookaways)) |
| `voice.listen.look_dwell_s` | `1.0` | How long you look at the camera before it starts listening: a glance shorter than this doesn't count. ([guide](wiki/user/settings-guide.md#voicelistenlookdwells)) |
| `voice.listen.look_gaze` | `true` | With your eyes calibrated on the Face page, a look counts by your eyes on the camera, not your head's turn. ([guide](wiki/user/settings-guide.md#voicelistenlookgaze)) |
| `voice.listen.look_gaze_dwell_s` | `0.0` | By the eyes: how long your eyes must be on the camera before it starts listening (0: at once). ([guide](wiki/user/settings-guide.md#voicelistenlookgazedwells)) |
| `voice.listen.look_gaze_pitch_deg` | `10` | By the eyes: how close to the camera's lens your gaze must be, up or down (an estimate in degrees). ([guide](wiki/user/settings-guide.md#voicelistenlookgazepitchdeg)) |
| `voice.listen.look_gaze_yaw_deg` | `10` | By the eyes: how close to the camera's lens your gaze must be, left or right (an estimate in degrees). ([guide](wiki/user/settings-guide.md#voicelistenlookgazeyawdeg)) |
| `voice.listen.look_in_company` | `true` | With others here, looking at it and saying its name (even misheard) counts as calling it. ([guide](wiki/user/settings-guide.md#voicelistenlookincompany)) |
| `voice.listen.look_pitch_deg` | `15` | How straight at the camera your head must point, up or down, judged against your face at enrolment. ([guide](wiki/user/settings-guide.md#voicelistenlookpitchdeg)) |
| `voice.listen.look_to_talk` | `true` | Look at the camera for a second and Kurooto starts listening, as if you'd said its name. ([guide](wiki/user/settings-guide.md#voicelistenlooktotalk)) |
| `voice.listen.look_yaw_deg` | `15` | How straight at the camera your head must point, left or right: at most this many degrees (an estimate). ([guide](wiki/user/settings-guide.md#voicelistenlookyawdeg)) |
| `voice.listen.model_judge` | `true` | When the rules can't tell whether you're talking to it, the model on this computer judges. ([guide](wiki/user/settings-guide.md#voicelistenmodeljudge)) |
| `voice.listen.name_variants` | `[]` | More spellings of its name to accept (the common mishearings of Kurooto are built in). ([guide](wiki/user/settings-guide.md#voicelistennamevariants)) |
| `voice.listen.need_face` | `true` | Answer only someone in front of it: a face close to the camera and facing it while they speak. ([guide](wiki/user/settings-guide.md#voicelistenneedface)) |
| `voice.listen.need_face_fallback` | `"voice"` | What happens when the camera can't see (paused, covered, busy, no camera): the voice rules alone, or nothing. ([guide](wiki/user/settings-guide.md#voicelistenneedfacefallback)) |
| `voice.listen.night` | `true` | Keep listening during the night hours. ([guide](wiki/user/settings-guide.md#voicelistennight)) |
| `voice.listen.on` | `false` | Listen through the microphone, all on this computer; only what's said to Kurooto leaves it. ([guide](wiki/user/settings-guide.md#voicelistenon)) |
| `voice.listen.stt_model` | `"base"` | How big the speech-to-text model is: tiny (75 MB), base (145 MB) or small (484 MB, more accurate). ([guide](wiki/user/settings-guide.md#voicelistensttmodel)) |
| `voice.listen.tap_to_talk` | `true` | A tap on an add-on's device (the Body face) opens the conversation, as its name would. ([guide](wiki/user/settings-guide.md#voicelistentaptotalk)) |
| `voice.listen.threshold` | `0.7` | How sure the local model must be (0 to 1) that speech is said to Kurooto. ([guide](wiki/user/settings-guide.md#voicelistenthreshold)) |
| `voice.listen.timing` | `true` | Time each spoken turn from your last word to Kurooto's first sound, as numbers only. ([guide](wiki/user/settings-guide.md#voicelistentiming)) |
| `voice.listen.told_off` | `true` | "Stop", "not you", "never mind" and the like, right after it woke or spoke, stop it at once and close the talk. ([guide](wiki/user/settings-guide.md#voicelistentoldoff)) |
| `voice.listen.wake_threshold` | `0.5` | How sure the wake-word model must be (0 to 1). ([guide](wiki/user/settings-guide.md#voicelistenwakethreshold)) |
| `voice.listen.wake_word` | `""` | A wake-word model of your own (an openWakeWord `.onnx` path); empty: its name wakes it. ([guide](wiki/user/settings-guide.md#voicelistenwakeword)) |
| `voice.listen.warm_brain` | `true` | When listening starts, get your AI's program ready on this computer. ([guide](wiki/user/settings-guide.md#voicelistenwarmbrain)) |
| `voice.listen.warm_up` | `true` | When listening starts, warm the transcriber and the voice, so your first turn isn't the slow one. ([guide](wiki/user/settings-guide.md#voicelistenwarmup)) |
| `voice.mirror_to_chat` | `true` | What Kurooto says aloud by itself also shows in the app's and the dashboard's Chat. ([guide](wiki/user/settings-guide.md#voicemirrortochat)) |
| `voice.speak.ack` | `"tone"` | While your AI thinks, a short soft sound says Kurooto heard you. ([guide](wiki/user/settings-guide.md#voicespeakack)) |
| `voice.speak.engine` | `"kokoro"` | The voice made on this computer: Kokoro (natural, about 0.55 GB), Piper (lighter) or off. ([guide](wiki/user/settings-guide.md#voicespeakengine)) |
| `voice.speak.join_sentences` | `true` | Speak short sentences together, up to about 200 characters at a time, instead of each on its own. ([guide](wiki/user/settings-guide.md#voicespeakjoinsentences)) |
| `voice.speak.max_chars` | `800` | How much of a long answer is read aloud before it says "the rest is on screen". ([guide](wiki/user/settings-guide.md#voicespeakmaxchars)) |
| `voice.speak.numbers_as_words` | `true` | Say numbers as a person would: 21:31 as "nine thirty-one PM", ₹3,000 as "three thousand rupees". ([guide](wiki/user/settings-guide.md#voicespeaknumbersaswords)) |
| `voice.speak.on` | `true` | Kurooto speaks through this computer's speakers. ([guide](wiki/user/settings-guide.md#voicespeakon)) |
| `voice.speak.rate` | `1.0` | How fast it speaks: 1.0 is normal, 0.8 slower, 1.2 faster. ([guide](wiki/user/settings-guide.md#voicespeakrate)) |
| `voice.speak.stop_when_gone` | `false` | Stop reading an answer when Face presence sees you've left the desk; the rest is offered when you're back. ([guide](wiki/user/settings-guide.md#voicespeakstopwhengone)) |
| `voice.speak.stream` | `true` | Speak the answer a sentence at a time while your AI is still writing it. ([guide](wiki/user/settings-guide.md#voicespeakstream)) |
| `voice.speak.voice` | `""` | Which Kokoro voice it speaks in; empty is `af_heart`. ([guide](wiki/user/settings-guide.md#voicespeakvoice)) |
| `voice.speak.what` | `"voice"` | What's read aloud: answers to what you said aloud, every AI answer, or nothing. ([guide](wiki/user/settings-guide.md#voicespeakwhat)) |
| `voice.speaker_id.adapt` | `false` | Improve over time: turns it was very sure were you refine your voice print, slowly and with undo. ([guide](wiki/user/settings-guide.md#voicespeakeridadapt)) |
| `voice.speaker_id.adapt_max` | `40` | At most this many learned turns are kept in your voice print (the oldest are replaced). ([guide](wiki/user/settings-guide.md#voicespeakeridadaptmax)) |
| `voice.speaker_id.adapt_per_day` | `10` | A daily cap on how many of your turns may be added to your voice print. ([guide](wiki/user/settings-guide.md#voicespeakeridadaptperday)) |
| `voice.speaker_id.carry` | `true` | A short reply right after a turn it knew was you counts as you (not when the voice is clearly someone else). ([guide](wiki/user/settings-guide.md#voicespeakeridcarry)) |
| `voice.speaker_id.carry_s` | `15` | The window, in seconds, in which a quick reply after you spoke still counts as you. ([guide](wiki/user/settings-guide.md#voicespeakeridcarrys)) |
| `voice.speaker_id.carry_talk` | `true` | In a talk Voice ID knew you opened, a voice it's only "not sure" of stays you, so history and tools carry. ([guide](wiki/user/settings-guide.md#voicespeakeridcarrytalk)) |
| `voice.speaker_id.face_assist` | `true` | When Voice ID is only "not sure" it's your voice and Face presence sees just your face, it counts as you. ([guide](wiki/user/settings-guide.md#voicespeakeridfaceassist)) |
| `voice.speaker_id.gate` | `true` | Check who's speaking before writing words out: other people not calling Kurooto are never transcribed. ([guide](wiki/user/settings-guide.md#voicespeakeridgate)) |
| `voice.speaker_id.guest_brain` | `"main"` | Who answers other voices: your AI (none of your data, no tools) or the model on this computer. ([guide](wiki/user/settings-guide.md#voicespeakeridguestbrain)) |
| `voice.speaker_id.guest_per_hour` | `20` | At most this many answers to other voices an hour. ([guide](wiki/user/settings-guide.md#voicespeakeridguestperhour)) |
| `voice.speaker_id.margin` | `0.05` | The 'not sure' band just below the threshold, at most 0.2 wide. Not sure always counts as not you. ([guide](wiki/user/settings-guide.md#voicespeakeridmargin)) |
| `voice.speaker_id.min_speech_s` | `1.0` | Speech shorter than this is too short to tell who it is, so it counts as not sure. ([guide](wiki/user/settings-guide.md#voicespeakeridminspeechs)) |
| `voice.speaker_id.mode` | `"owner_only_acts"` | What other voices get: a chat with no actions and none of your data, or just one line saying it only talks with you. ([guide](wiki/user/settings-guide.md#voicespeakeridmode)) |
| `voice.speaker_id.model` | `"campplus-en"` | The speaker model: campplus-en (English, the most accurate) or campplus-multi. Changing it means enrolling again. ([guide](wiki/user/settings-guide.md#voicespeakeridmodel)) |
| `voice.speaker_id.on` | `false` | Voice ID: only your voice can make Kurooto act; others can only chat, with none of your data. Enrol first. ([guide](wiki/user/settings-guide.md#voicespeakeridon)) |
| `voice.speaker_id.spoken_enrol` | `true` | During enrolment Kurooto says each step aloud. Off: the page shows the steps only. ([guide](wiki/user/settings-guide.md#voicespeakeridspokenenrol)) |
| `voice.speaker_id.strictness` | `"normal"` | How sure it must be that it's you: relaxed, normal or strict (strict turns you away more often). ([guide](wiki/user/settings-guide.md#voicespeakeridstrictness)) |
| `voice.speaker_id.tell_guests` | `true` | Once per conversation, tell others they can chat but only you can make Kurooto act. ([guide](wiki/user/settings-guide.md#voicespeakeridtellguests)) |
| `voice.speaker_id.threshold` | `0.0` | 0: worked out from your own samples when you train. A number overrides it, held to 0.30 to 0.95. ([guide](wiki/user/settings-guide.md#voicespeakeridthreshold)) |

### `voice_notes`

| Setting | Default | What it does |
|---|---|---|
| `voice_notes.api_base` | `""` | Another address for the voice-note model; empty is Google's. ([guide](wiki/user/settings-guide.md#voicenotesapibase)) |
| `voice_notes.model` | `"gemini-flash-latest"` | Which Gemini model writes out your voice notes. ([guide](wiki/user/settings-guide.md#voicenotesmodel)) |

### `web`

| Setting | Default | What it does |
|---|---|---|
| `web.port` | `8770` | The dashboard's port on this computer (read when Kurooto starts). ([guide](wiki/user/settings-guide.md#webport)) |

### `weekly`

| Setting | Default | What it does |
|---|---|---|
| `weekly.call` | `false` | A Sunday review call after the summary: the week, what went well, next week's priorities. ([guide](wiki/user/settings-guide.md#weeklycall)) |
| `weekly.people` | `true` | One line about the people in your project notes: who you met this week and who's next. ([guide](wiki/user/settings-guide.md#weeklypeople)) |
| `weekly.when` | `"weekly sun 19:00"` | When the week's summary comes. ([guide](wiki/user/settings-guide.md#weeklywhen)) |

### `you`

| Setting | Default | What it does |
|---|---|---|
| `you.assistant_name` | `"Kurooto"` | The name your assistant goes by in messages, calls and the dashboard. ([guide](wiki/user/settings-guide.md#youassistantname)) |
| `you.language` | `"follow"` | Which language answers come in: the one you wrote in, or always one you name. ([guide](wiki/user/settings-guide.md#youlanguage)) |
| `you.name` | `""` | Your name, as Kurooto uses it in messages and calls. ([guide](wiki/user/settings-guide.md#youname)) |
| `you.timezone` | `""` | Your time zone, for every time Kurooto keeps; empty follows this computer's clock. ([guide](wiki/user/settings-guide.md#youtimezone)) |
| `you.workspace` | `""` | Your notes folder: where Kurooto reads and writes notes, journal and course files. ([guide](wiki/user/settings-guide.md#youworkspace)) |
