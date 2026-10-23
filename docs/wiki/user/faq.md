# FAQ

Short answers, with a link to the full story. Something not working? See [Troubleshooting](troubleshooting.md).

## Before you install

**What is Kurooto, in one line?**
A personal assistant that runs on your own computer, talks to you through your own Telegram bot, and can ring your
phone. See the [front page](index.md).

**Does it cost anything?**
No, unless you choose a paid plan: a paid Gemini key, or an AI plan you already pay for (Claude Code needs a paid
Claude plan). Telegram, Cloudflare (for calls), GitHub (for Notes sync), Google Cloud (for Google features) and the
Gemini free tier are used within their free plans.

**Do I need a powerful computer or a graphics card?**
No. Without a graphics card the AI runs in the cloud and everything works; only the optional local models need a
graphics card or an Apple Silicon Mac. About 1 GB of disk for Kurooto itself, plus what the features you pick need (the
wizard shows the total). See [Your computer](your-computer.md).

**Which computers?**
Windows 10 or 11, macOS 12 or newer, and Linux. No admin password is needed. See [Getting started](getting-started.md).

**Do I have to be a student?**
No. The study features (subjects, timetable, quizzes, books) are off until you turn them on. Reminders, check-ins,
the journal, notes, calls, the alarm, research digests and Google features are for anyone.

**Do I need to know how to code?**
No. Everything is done through Telegram, the dashboard and the setup page. The terminal commands and
[add-ons](add-ons.md) are optional.

**Which AI should I pick?**
The setup page marks **Antigravity (agy)** with ★: it's free with a Google account and has higher limits than a free
key. A **Gemini API key** is the simplest, it's what Google recommends for tools like this, and phone calls, voice notes
and the alarm need one anyway; its free tier runs out quickly, so set the other as a fallback. See
[AI brains](ai-brains.md).

## Everyday use

**Do I have to learn commands?**
No. Plain English works for most things ("remind me at 9 to call mum", "what's due this week?", "wake me at 6:45").
Commands are there when you prefer them; type `/` in the chat for a menu. See [Commands](commands.md).

**Why didn't it understand me?**
Short everyday requests are understood instantly; anything else goes to your AI, which needs the Chat feature on. If
Kurooto got it wrong, tap **Wrong** and teach it your words. See [Teaching Kurooto](teaching-kurooto.md).

**Can someone else talk to my bot?**
No. It answers only the Telegram account that tapped the pairing link; everyone else is ignored.

**Will it send email or messages for me?**
Never by itself. It sends nothing to anyone but you. A reply to an email waits in Gmail until you tap Send; approvals
are never given for you. The alarm and calls work the same way: your AI asks before it sets one
([Never without your tap](talking-to-kurooto.md#never-without-your-tap)).

**It messages me too much. How do I quiet it?**
Tap **Less of this** under a message (Stop, Fewer or Another time), or lower the daily limit with `/calm 4`. At most 6
messages and 1 call a day come by themselves by default; the rest wait for one evening bundle. `/why` says why the last
one came. See [Messages Kurooto sends by itself](messages-it-sends.md).

**How do I stop it calling me at a bad time?**
It never calls during a class on your timetable, a calendar event, the night (23:30 to 07:00 by default, or bedtime to
your alarm), focus or another call. For a while: "no calls for 2 hours" or `/hold 2h`; `/calls` lifts it. See
[Phone calls](calls.md).

**Can I pause it?**
`/pause`, `/pause 2h` or `/pause until 18:00`. Telegram still answers, keeps what you send and does it when you
`/resume`. Your call line still rings scheduled calls, so the alarm works. See
[Talking to Kurooto](talking-to-kurooto.md).

## Your computer

**Does it work when my computer is off or asleep?**
Partly. Telegram messages wait until it's back (Telegram keeps them for about a day). With Phone calls set up, calls
and the wake-up alarm still ring from your call line, and you can answer questions in the phone app. With
**Reminders with the lid shut**, your Android phone gets reminders at their time. Anything else is done when the
computer is back, and Kurooto tells you it's back online. See [Phone calls](calls.md) and
[Messages Kurooto sends by itself](messages-it-sends.md).

**What happens on battery?**
By default (`power.on_battery` = `saver`) Telegram, reminders, check-ins, deadlines, calls and answers keep working;
heavy work (local models, the notes index, backups, book reading, the nightly look back) waits for the charger and runs
the moment you plug in. See [Your computer](your-computer.md).

**Can I use it on two computers?**
One at a time per Telegram bot and call line. Notes sync keeps your notes in step; Profile sync moves your setup to a
new computer. Turn Kurooto off on the old one (`kurooto off`). See [Updates and backups](updates-and-backups.md).

**How do I move to a new computer?**
With Profile sync on: install on the new one and press **I've used Kurooto before** on the setup page. Without it, a
backup zip and `kurooto restore`. See [Updates and backups](updates-and-backups.md).

## Phone

**Android or iPhone?**
Both. Android is best: calls ring like real phone calls, even on silent and on the lock screen. On iPhone, Kurooto is
a Home Screen web app; calls arrive as notifications you tap. See [Phone app](phone-app.md).

**Why isn't the Android app on the Play Store?**
It's installed from your own computer's pairing page. Android asks you to allow installing it; Play Protect may warn
first ("Install anyway"). See [Phone app](phone-app.md).

**I lost my phone.**
Run `kurooto rotate` on your computer: your call line gets new keys and forgets every paired phone. Then pair your
other phones again. See [Phone app](phone-app.md).

## Notes

**Where are my notes?**
In a normal folder, `Documents/Kurooto` by default, as Markdown files. Open it in Obsidian or any editor. See
[Notes and the concept graph](notes-and-concept-graph.md).

**Will Kurooto change what I wrote?**
No. It adds notes and lines, and keeps its own parts between markers. When you ask it to edit a note, it changes one
exact passage and keeps the previous version first.

**Can I keep my notes in sync across devices?**
Yes, with Notes sync and a free private GitHub repository. Edits on two devices at once are both kept.

## Privacy and data

**Does my data go to whoever made Kurooto?**
No. Nothing is ever sent to Kurooto's author. What leaves your computer goes to the services you chose, under your own
accounts. See [Privacy](privacy.md).

**What does the free Gemini tier mean for my data?**
Google may use what you send on the free tier to improve its products, and human reviewers may read it. Use a paid key
if that matters (it's required in the EEA, UK and Switzerland). See [AI brains](ai-brains.md).

**Does it read all my email?**
No. The mail digest reads only the senders, domains or labels you choose; the rest is only counted. Mail marked
confidential never goes to the AI: it's only counted, or, if you opt in (`mail_digest.confidential` = `local`),
summarised by a local model on this computer. See [Google](google.md).

**How do I remove everything?**
`kurooto uninstall --revoke` deletes your call line and takes back Google's and the bot's access first; then delete the
tokens and keys it lists. Your notes folder is never deleted. See [Updates and backups](updates-and-backups.md).

## Updates

**Does it update itself?**
Yes, at night (03:00 to 05:00) by default, only signed releases, and it goes back to the previous version if a new one
keeps crashing. `updates.mode` = `ask` asks first. See [Updates and backups](updates-and-backups.md).

**Can I try new versions early?**
Yes, the beta channel. See [Getting started](getting-started.md).

## Getting help

**Something's wrong. What do I send to the person helping me?**
`kurooto doctor` says what's wrong; `kurooto doctor --bundle` makes a zip with secrets, names, addresses and folders
blanked out and without your messages or notes. Look inside it, then send it yourself. See
[Your computer](your-computer.md) and [Troubleshooting](troubleshooting.md).

**Where's the code?**
On GitHub, under the Apache-2.0 licence. The README links it.
