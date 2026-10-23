# Troubleshooting

Find what you see in the left column; the right column says what to do. Start with these three, which answer most
problems:

1. **`/health`** on Telegram: what isn't working, with **Fix** buttons (`/health now` also checks online services).
2. **`kurooto doctor`** in a terminal: every check, one line each; `kurooto doctor --fix <id>` runs a fix.
3. **`/why`** when a message surprised you, and **`/calm`** when one didn't come.

Still stuck? `kurooto doctor --bundle` makes a zip for someone helping you, with secrets, names, addresses and folders
blanked out and none of your messages or notes. Look inside, then send it yourself. See
[Your computer](your-computer.md).

**Contents:** [Setup and Telegram](#setup-and-telegram) · [The AI](#the-ai) · [Messages](#messages) ·
[Reminders, deadlines and check-ins](#reminders-deadlines-and-check-ins) · [Calls and the alarm](#calls-and-the-alarm) ·
[The phone app](#the-phone-app) · [Classes and study](#classes-and-study) · [Notes, skills and research](#notes-skills-and-research) ·
[Google](#google) · [Dashboard and terminal](#dashboard-and-terminal) · [Your computer](#your-computer) ·
[Updates, backups and moving](#updates-backups-and-moving)

## Setup and Telegram

| What you see | What to do |
|---|---|
| The setup page didn't open | Run `kurooto open`, or go to `http://127.0.0.1:8770/setup`. If another program uses that port, Kurooto picks the next one (`kurooto paths` → `web.json` in the state folder names it). |
| The setup page says "Kurooto isn't answering" | It stopped or is restarting: start it from your app menu or with `kurooto on`, then press the button again. What you typed stays. |
| The setup page says it's out of date | Reload the page. |
| Not enough space | The wizard says what needs it. Free some space, or pick fewer features. |
| "That doesn't look like a bot token" | Copy the whole token from BotFather's message (it looks like `123456789:AAH…`). |
| Telegram didn't accept the token | Copy it again, or send `/token` to @BotFather to see it. |
| "That token was revoked" | Get the new token from @BotFather and paste it on the setup page. Messages to you start again as soon as it works; no restart needed. |
| "Got a /start without the code" | Send the whole `/start …` message the setup page shows, not just Start. |
| "This link expired" | Pairing links last an hour: press **Get a new link**. |
| "This bot is connected to a web address (a webhook)" | Press **Disconnect it** on the setup page. |
| "Another program is reading this bot's messages" | Another Kurooto (an old computer?) uses the same bot: `kurooto off` there, or make a new bot. |
| The bot doesn't answer | `kurooto doctor`. Is Kurooto running, or turned off (`kurooto on`)? Is the computer asleep (see [Stay awake on charger](your-computer.md))? |
| The bot says it's paused | `/resume`. Or it's on battery with `power.on_battery` = `pause`: plug in, or choose `saver`. |
| Two computers both answer, or the bot misses messages after moving | Turn Kurooto off on the old computer: `kurooto off`. |
| "X is off: Features → X → Turn on" | That command belongs to a feature that's off. Turn it on on the dashboard's Features page. |
| "I can't answer free text yet" | Turn on **Chat** (Features). |
| "that button is from a feature that's off now" | Turn the feature back on, or ignore the old message. |
| Telegram's "/" menu is out of date | It updates within a minute of a feature going on or off, and every 15 minutes for skills. Turning `telegram.menu` off and on sets it again. |
| "Voice notes are off" | Turn on Voice notes (Features); it needs a Gemini key. |
| "Couldn't get that file" (a big file) | Telegram lets bots fetch files up to 20 MB. Put the file into your notes or files folder yourself. |
| "… Telegram takes files up to 50 MB" when Kurooto sends you something | Turn on [Drive upload](google.md): bigger files then come as a Google Drive link. |

## The AI

| What you see | What to do |
|---|---|
| The AI test fails on the setup page | The panel says why. A Gemini key starts with `AIza`; agy and Claude Code need their sign-in window again; Ollama needs `ollama serve` running; another service's address usually ends in `/v1`. |
| "… isn't signed in any more" | Setup page → AI → sign in again → Test it. |
| "It's at its usage limit" | Free tiers have daily limits: wait, or set a fallback brain (`brain.fallback`). `/usage` shows how often it happens. |
| "Google's free limit for today is used up" | It comes back at the time the message says. Set a fallback brain meanwhile; calls and reminders still work. |
| The Classroom digest, the look back or a research digest didn't come | Past 70% of a known free limit, background work waits for the reset. `/usage` says how many requests wait. Raise `quota.background_pct` or set `quota.on` to `false` (in `settings.json`). |
| "The AI stopped without an answer" | Rephrase it, or do that part yourself. |
| "No answer in time" | Start the message with `low:`, or split the request. |
| "It got stuck" | Send it again. A request with no progress for `jobs.stuck_min` (10) minutes is stopped. |
| The AI said it did something but nothing happened | Tell it so; check `/jobs`. A small local model may not support tools and answers without them. |
| The setup page says agy "can't use Kurooto's tools yet" | agy's settings file isn't plain JSON, or `agy mcp add` failed. Add `mcp(kurooto/*)` to `permissions.allow` in agy's `settings.json` yourself, then Test again. |
| An agent program says Kurooto's tools aren't running | Kurooto is off or restarting: `kurooto on`, then ask again. |
| Building my profile failed | It's a big request: if the AI hit a limit, try again later or with a stronger AI (`brain.main`). |
| "There's no ## In brief section" | Add that heading to your profile with a few lines about you; without it nothing goes along with AI requests. |

## Messages

| What you see | What to do |
|---|---|
| A message came only in the evening bundle, or not at all | More than `notify.calm.messages` (6) came by themselves that day, it's exam season, or you chose Fewer, Another time or Stop for that kind. `/why` on the next one says which; `/calm` lists what's turned down, with buttons to start it again. `/calm off` brings back the old behaviour. |
| A check-in or deadline call came as a message instead | The day's one call that comes by itself (`notify.calm.calls`) had come already. `/calm calls 2` allows two. |
| "Back online" every morning | Your laptop sleeps at night. Raise `notify.presence.after_min` past your night, or set `notify.presence.on` to `false`. |
| No "going offline" when the laptop sleeps | That message comes from your call line: it needs Phone calls set up and your OK for it to use Telegram (`notify.presence.line_telegram`), or add `"app"` to `notify.presence.channels`. |
| "needs a look" on the dashboard, or in the weekly summary | `/health` (or the Features page) says what, with a Fix button where Kurooto can fix it. A sign-in that ended needs you; the line says where. |
| "That question expired" | It waited longer than `ask.expire_hours` (48); nothing was done. The asker asks again if it still matters. |
| I tapped a button and nothing happened | It may have been answered elsewhere (on a call, in the app): `/q` shows what's still open. |

## Reminders, deadlines and check-ins

| What you see | What to do |
|---|---|
| A reminder came marked "late: the computer was asleep" | Keep the computer awake on the charger, or turn on [Reminders with the lid shut](calls.md#reminders-with-the-lid-shut) (Android). |
| `/remind 9 call mum` came 9 minutes later | A bare number means minutes. Write `9:00`, `9am` or `21:00`. |
| "When should I remind you?" | The only time you gave was about the past ("since I didn't wake up at 12"); say the time you want. |
| "Reminder (late: Reminders was off)" | It was due while the feature was off; it's kept and comes when you turn it back on. |
| A deadline shows up twice | They didn't look like the same thing (different dates or numbers in the title). Tap **Not mine** on one. |
| A calendar event became a deadline by mistake | **Not mine** on it, or `/ignore` a word in its title; `deadlines.from_calendar` off stops calendar deadlines. |
| A task in my notes isn't on the list | It needs a date on an unticked task line: `- [ ] Essay draft (2026-11-02 17:00)`. |
| Done didn't tick the box in my notes | The line changed since Kurooto read it (it's re-read every hour); tick it yourself. |
| No call six hours before a deadline | Is Phone calls on and set up? A class, `/hold`, focus or the night until shortly before the deadline means a message instead. |
| A recurring quiz is on the wrong week | Put a date it really happens on in the "Next" column of `kurooto/recurring.md`. |
| `/exam` says exam mode is off | `deadlines.exam_mode_days` is 0; set it to 14. |
| Start-by dates come too early or too late | Tap the right size on a deadline (`/startby`). If they're all off, change `startby.share` or `startby.window`. |
| No night check-in | It's off until you give it a time: `checkins.times`, e.g. `{"night": "23:15"}`. |
| A night check-in I didn't want | Empty its time in `checkins.times`, or `/checkin night skip` for today. |
| The night check-in didn't ring | The alarm was set and it was past your bedtime, so it moved to the wake-up call (a message said so). `checkins.asleep_defers` off makes it always ring. |
| "skip Friday's check-in" went to the AI | Only today, tomorrow, the day after and weekday names are understood instantly; dates and "next week" go to the AI. |
| "I missed your evening check-in" | The computer was off for more than two hours at check-in time. Reply to it anyway. |
| My check-in reply wasn't saved | Reply to the check-in message itself (Telegram's Reply), and check `checkins.journal` is on. |
| No Sunday review call | `weekly.call` is off, Phone calls isn't set up, or the computer was off well past the time. |
| The first-week quests stopped | `/quests` says why: you said stop, or a day's quest was left alone (they stop rather than nag). |

## Calls and the alarm

| What you see | What to do |
|---|---|
| "Not connected to your call line", or "I tried to call you, but your call line isn't connected" | Is the computer online? It reconnects by itself within a minute. Still not: Features → Phone calls → Set up. |
| Cloudflare sign-in didn't finish | Press Set up again; the sign-in link is also in the progress log. |
| "Your call line couldn't be updated" | Calls keep working on the old version. Features → Phone calls → Set up tries again. |
| "Held a call until …" | A class, `/hold`, focus, a calendar event, the night or an exam was on; it rings by itself when that ends. `/calls` lifts a hold. Too many events hold calls? Set `calendar.nocall_events` to `tagged`. |
| A call rang three times | It wasn't answered: repeats at +3 and +6 minutes. Answer, tap **Later**, or set `calls.realert_min` to `[]`. |
| A call keeps cutting itself off on the loudspeaker | Use the earpiece or earphones, or move the mic gate slider to the right. |
| A call says "Reconnecting…" and then goes turn by turn | Google's live voice was down (`kurooto doctor`: "Phone calls: voice service"). Nothing to do; next time it tries Live again. |
| A call went to Telegram instead | Your phone couldn't turn speech into text, or the microphone wasn't allowed. Update the Android app and allow the microphone; in a browser, use Chrome. |
| Turn by turn stops listening | The screen went off or you switched apps: tap **Talk**. |
| Turn-by-turn answers are slow | Each turn waits for recognition, the AI and the voice. With `calls.turn_brain` = `local` on a slow computer, use `gemini`. |
| A call forgot something I told it last time | Look at `/lessons`: lessons are kept from the look back after each call. A wrong one: `/lessons forget N`. |
| "Your alarm … might not ring" | Set your phone's own alarm for tonight. Then check Phone calls is set up and linked (`kurooto doctor`) and a phone is paired. The Fix button reconnects or plans the alarm again. |
| No plan before my alarm | It needs Chat on and `alarm.prep_min` above 0, with the computer awake 20 minutes before. Turn on `alarm.keep_awake` and plug in overnight. |
| The morning page didn't open | It opens only if the computer is awake with a screen at alarm time. Open `http://127.0.0.1:8770/morning` yourself. |
| "I'm awake" went to the AI | It works with the Morning alarm feature on. |
| A reminder didn't reach my phone while the lid was shut | `kurooto doctor`: the "Reminders with the lid shut" line. "No phone can open them yet": update the Android app and open it once. Check the app's checklist. On a Mac, reminders set in the last seconds before closing the lid wait until it wakes. |

## The phone app

| What you see | What to do |
|---|---|
| The phone didn't ring, and `/status` or the log shows "429 Too Many Requests" from ntfy | ntfy.sh limits each internet address, and you share yours (a campus, and your call line's Cloudflare one). Make a free ntfy.sh account, then `kurooto ntfy-token`: ntfy then counts your account instead. |
| The phone doesn't ring | Is every item on the app's checklist ticked? **Battery: unrestricted**, and Kurooto off any "sleeping apps" list (Samsung, Xiaomi, Oppo, Vivo, OnePlus, Huawei). Then dashboard → Phone → **Ring my phone**. |
| Android won't install the app | Allow installing unknown apps for your browser when asked; for Play Protect, "More details" → "Install anyway". |
| iPhone gets no notifications | Open Kurooto from the Home Screen (not Safari), turn notifications on in it, iOS 16.4 or newer, and Settings → Notifications → Kurooto. |
| Questions don't show on the phone | Is `question` in `notify.app_kinds`? On Android, is the "Questions and approvals" notification category on? Is the computer connected to your call line? |
| "Not sent: tap to try again" | The phone was offline or the call line didn't answer. Tap to retry, or answer on Telegram. |
| "That answer is too old (or this phone's clock is off)" | Set the phone's clock to automatic, then answer again. |
| "That's no longer open" | It was answered somewhere else or expired. Nothing to do. |
| "That answer couldn't be opened here. Pair the phone again." | Pair the phone again (for example after `kurooto rotate`). |
| A device paired that wasn't me | `/phones`, then `/unpair <id>`. If a phone was lost, run `kurooto rotate`. |

## Classes and study

| What you see | What to do |
|---|---|
| I can't remove a class with `/class remove mon 09:00` | It says the class comes from your term note or a class pack: change it there. |
| `/term` says "Term note …: not found" | The path is relative to your notes folder (`terms/2026-autumn`, `maps/semester-*`); `/term note <path>` again, or `/term note off`. |
| A class or date from the term note is missing | Check the table headings ("Weekly timetable", "Key dates"), times like `09:00-09:55` and dates like `2026-11-12`; `/term` says how many it read. |
| No after-class question | The class was skipped, it's a holiday or exam period, the term is over, the subject is left out in `capture.subjects` / `capture.skip_subjects`, or a class-calendar event names none of your subjects. |
| A class pack "isn't a class pack I can use" | The message says why (a field the format doesn't have, or text that looks personal). Ask whoever made it to fix it; `kurooto classpack check FILE` checks a file. |
| "That's a class pack. Turn on Class packs" | Turn the feature on and send the file again. |
| `/quiz` says there's no material | Add an exam-prep or quiz note with a `## Must know` list to the subject's folder. |
| A revision pack comes as a `.tex` file | No LaTeX program: tap **Install Tectonic** in the message (asked again 30 days after **Not now**), or install TeX Live, MiKTeX or MacTeX. |
| The first PDF takes minutes | Tectonic fetches about 50 MB of LaTeX packages once; later packs take seconds. |
| "it didn't compile" | The `.tex` is in your notes. `/pack` again, or reply with what to change. |
| A hint photo wasn't read | Photos need an AI that opens files (agy or Claude Code). Type the problem instead. |
| No hints at all for a subject | Its course note's "AI policy" line says no AI help. Change that line. |
| A book stays "not started" or "waiting for a reader" | Reading happens at night on the charger (`/books read now`, or `/books read force` on battery). Scanned pages need Tesseract (`/books setup`) or a vision model; encrypted PDFs need Poppler. `/books` says which. |
| A book sent on Telegram wasn't added | Telegram lets bots fetch files up to 20 MB: drop bigger books into the folder (`/books folder <subject>`). The caption must say `book for <subject>`. |
| A study pack is missing files | It was over 50 MB without Drive upload. `INDEX.md` in the zip lists what was left out; turn on Drive upload. |
| A Drive link from a study pack stopped working | Temporary uploads are deleted after `drive_upload.temp_days` (7). Download what you want to keep, or move it out of the Kurooto folder in Drive before then. |
| Study time counts while I'm away (Wayland) | Add the idle hook (`kurooto idle away` / `back`; see [Books and study](books-and-study.md)). `kurooto doctor` shows what it uses now. |
| Study time stopped counting | A `kurooto idle away` without its `back`: run `kurooto idle back`. |
| A handwritten PDF isn't written out | PDFs read on this computer wait for the night on the charger, and while the graphics card is busy. `/handwritten` starts it now; "can't be drawn": install Poppler's PDF tools. |
| A handwritten note has no Links section | Linking needs an AI (AI brain) and `handwritten.link` on; when the AI's answer was unusable nothing is written. `/handwritten link` tries every note without one again; `/handwritten undo` takes back the last linking. |

## Notes, skills and research

| What you see | What to do |
|---|---|
| Notes appear in the wrong folders | Check `notes.layout` and `notes.paths` (Settings → notes). Existing notes aren't moved when you change the layout. |
| Photos and PDFs still land in my notes | Set `files.folder` to a folder outside your notes folder (one inside changes nothing). |
| Notes sync refuses the repository | It must be private, and the token needs Contents: Read and write for that repository (Repository access → Only select repositories). |
| A note named "(conflict, this computer, …)" appeared | The note changed here and elsewhere at once; both versions are kept. Merge them, then delete the copy. |
| Notes sync: "a note was changed here and elsewhere at once" | `notes_sync.on_conflict` is `stop`. Merge it in the notes folder as the message says, or set it to `keep both`. |
| Notes sync: "a merge or rebase is unfinished" | Finish it in the notes folder (`git status` says how); sync goes on by itself. |
| "A sync is already running" | Wait for its summary. |
| `/notes` or `/timeline` says the brain is busy | The nightly upkeep or a sync is using it; try again in a while. |
| Notes brain: "can't find your gbrain" or "your brain's folder isn't there" | Your own GBrain: set `gbrain.exe` and `gbrain.home`, or set `gbrain.managed` back to `true`. |
| The nightly upkeep didn't finish | Search still works. Its log is in the state folder (`gbrain/upkeep-<date>.log`); it tries again the next night. |
| `/journal` (or another skill) goes to Chat as plain text | Turn on **Skills** (Features). `/skills` lists the names. |
| A skill name can't be typed | A command with the same name wins; `/skills <name>` says so. |
| `/every` refused | The command or skill doesn't exist, you already have 30 routines, or it contains `/every`. |
| A routine didn't run | It runs when the computer is on; one missed while it was off runs once when it's back (if that's still one of its days). `/routines` shows what's set. |
| "I'd rather not keep that" after `/remember` | It looked like a health, money or password detail. Keep it in your own notes instead. |
| The look back never suggests anything | Most days that's right. `/lookback` shows when it last ran; on a laptop it waits for the charger; `/lookback now` runs one. |
| A skill change says "nothing changed" | The AI's version was the same, or it broke the skill's header; it's never saved then. |
| "Saved as a test case, but not learned" | Teaching it would break another test case, or it's a request that sends, calls or deletes. |
| "1 phrasing you taught no longer works" | `/cases`: Unlearn it, then teach it again with `/wrong <words>`. |
| Research: "repository folder missing" | You moved or deleted it: `/repos remove <folder>`, then `/repos add <new folder>`. |
| Research: "isn't a git repository (no commits to follow)" | Only a note. `git init` the folder to follow it, or `/repos remove` it. |
| An arXiv search is refused | An unclosed bracket or quote in the query. |
| No papers digest arrived | No new papers that week (it only says so when a source failed), or on battery it waits for the charger. |
| `kurooto watch` says "only shown on this computer" | Kurooto wasn't running: `kurooto start`. |

## Google

| What you see | What to do |
|---|---|
| "Access blocked: Kurooto has not completed the Google verification process" | The app is still in Testing: publish it (Audience → Publish app). See [Google](google.md). |
| "Access blocked" by your school, or "Error 400: admin_policy_enforced" | Your school's account doesn't allow unverified apps. Use a personal account; for your timetable, use the Calendar feature's iCal link instead. |
| "Error 400: redirect_uri_mismatch" | The client isn't a Desktop app: make a Desktop app client and paste that file. |
| "Error 401: invalid_client" or "deleted_client" | Download a new client file (Add secret, or a new client) and paste it. |
| Kurooto asks you to sign in to Google every week | The app is still in Testing: publish it, then sign in once more. |
| "Google: sign-in expired" | Features → Google → Save (signs in again). |
| A Google feature stays off after signing in ("access_denied") | You pressed Cancel or unticked its permission: Save on its card again and leave the box ticked. Is its API on in your Google Cloud project? |
| "… has not been used in project … or it is disabled" | Turn that API on in your Google Cloud project, wait a minute, try again. |
| The page after signing in "can't be reached" (127.0.0.1) | Sign in on the computer Kurooto runs on. |
| Google's screen says "Something went wrong" | Try a private window signed in to one Google account only. |
| "Mail digest is paused: needs Google's OK" (or another Google feature) | Features → that feature → Save, then sign in and leave its permission ticked. |
| "That's the same Google account as your main one" | Save on the card again and pick the other account in Google's chooser. |
| A feature says it needs your school Google account | Its account's sign-in is missing or expired: Save on its card and pick that account. `/google` shows which account each feature uses. |
| The mail digest says it only counted my mail | It reads only what you chose: `/mail read @school.example` or `/mail read label:Name`. Mail marked confidential is always only counted (unless you choose local summaries). |
| "Confidential mail is only counted for now" | Local summaries need Local AI models on and ready (on a laptop they run on the charger). |
| The mail digest wasn't emailed | It mentioned confidential material (a note said so), or the sending account's address isn't known: Save on Mail digest by email and sign in again. |
| `/draft` says drafts are off | Turn on `google.gmail_drafts`, enable the Gmail API and sign in again. |
| Classroom notes say a PDF wasn't read | Install Poppler (`pdftotext`), or use agy or Claude Code as your AI. |
| Classroom notes went to the wrong folder | `classroom_notes.folders`: `{"Exact course name": "folder-name"}`. |

## Dashboard and terminal

| What you see | What to do |
|---|---|
| The dashboard won't open | `kurooto open`, or `http://127.0.0.1:8770`; the port may have moved (`kurooto paths` → `web.json`). It opens only on the computer Kurooto runs on. |
| The NOTES map is empty, but its top line counts notes | Update to 0.5.11 or later: a note with hundreds of links threw the map off the screen. Reload the dashboard after updating. |
| A setting isn't on the Settings page | A feature's settings appear once it's on. Telegram's pairing (`telegram.chat_id` and the like) is set by pairing, not on the page. |
| The Terminals tab says it's off, or a terminal won't type | Features → Terminals → Turn on. On Linux, a terminal from another user account is refused on purpose. |
| Kurooto Terminal opens separate windows instead of tabs | kitty (Linux, macOS) or Windows Terminal isn't there: `kurooto term --install`, or Windows Terminal from the Microsoft Store. `kurooto term --print` says what it found. |
| "kitty didn't start" | kitty needs OpenGL 3.3 (some virtual machines lack it); set `terminal.kitty` off to use your usual terminal. |
| Kurooto Terminal looks old in Windows Terminal | Close every Windows Terminal window and open it again. |
| The system palette doesn't use my colours | Settings → Look shows what Kurooto found; changes show within half a minute. Point `look.theme_file` at a kitty theme or a matugen or pywal `colors.json`. |
| Your add-ons: a problem in `kurooto doctor` | `/addons` shows which file and the error. Fix it, then restart Kurooto (`kurooto stop`, `kurooto start`). |

## Your computer

| What you see | What to do |
|---|---|
| Something only happens when I plug in | That's the battery saver. Set `power.on_battery` to `normal` to keep everything running. |
| The laptop still sleeps with the lid closed on the charger (Linux) | Turn on `awake.lid`. If your system refuses the lid hold to background programs (doctor says so), allow it in polkit or set `HandleLidSwitchExternalPower=ignore` in logind.conf. |
| `kurooto autostart boot`: "Linux didn't allow that from here" | Run `loginctl enable-linger` in a terminal, then `kurooto autostart boot` again. |
| `kurooto ask`, `call`, `send`, `ask-me` or `ask-approval` say Kurooto isn't running | `kurooto on`, then try again. `--timeout` is in minutes. |
| A low-disk warning | `/space clean` removes Kurooto's own old files; free space elsewhere too. |

## Updates, backups and moving

| What you see | What to do |
|---|---|
| `kurooto update` says it can't update itself | Run the install line again (see [Getting started](getting-started.md)); it repairs and updates. |
| "Couldn't prepare Kurooto …" | It tries again later. |
| Kurooto went back to the previous version | The new one crashed three times in its first five minutes; you were told on Telegram. It won't offer that version again. |
| Backups: "the backup folder isn't there" | Plug the drive in or sign in to the cloud app; the next backup comes within the hour. |
| Backups: "not enough room in the backup folder" | Free space there, lower `backups.keep`, or turn `backups.index` off. |
| A restore went wrong | `kurooto restore` the zip in `restore-safety/` (in the data folder) puts things back as they were. |
| Restore says a file is still open in another program | Stop Kurooto (`kurooto stop`) and try again. |
| Restore: "That passphrase doesn't open this profile" | It's the passphrase you picked for Profile sync, not your GitHub password. Nothing was changed. |
| Restore: "…was changed or damaged, so it can't be trusted" | A file on the `kurooto-profile` branch was edited outside Kurooto. Revert that edit on GitHub, then restore again. |
| Profile sync: "another computer saved your profile since this one did" | Restore it here (`kurooto profile restore`), or `/profile save` to make this computer's the one. |
| Kurooto asks Update / Later every few hours | `updates.mode` is `ask`, and Later only puts it off until the next check. Tap Update or **Skip this version**, or set `updates.mode` to `night`. |
