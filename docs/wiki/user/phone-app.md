# Your phone

Your phone is where Kurooto's calls ring, and a second place to answer its questions. Android gets a real app that
rings like a phone call; an iPhone gets a web app on its Home Screen. Both need [Phone calls](calls.md) set up first:
the app comes from your own call line.

The phone app adds calls, the wake-up alarm, questions with answer buttons, and a chat with Kurooto that works like
Telegram. On Android it also shows your day (Today) and rings the wake-up alarm on the phone itself, even with your
computer and call line out of reach. It can replace Telegram entirely: see [Using the app instead of Telegram](#using-the-app-instead-of-telegram).

- [Pair a phone](#pair-a-phone)
- [Android](#android)
- [Bedside mode (Android)](#bedside-mode-android)
- [iPhone](#iphone)
- [Tell Kurooto: Siri and Back Tap (iPhone)](#tell-kurooto-siri-and-back-tap-iphone)
- [Any browser](#any-browser)
- [What reaches the phone](#what-reaches-the-phone)
- [Answering questions on the phone](#answering-questions-on-the-phone)
- [Today on the phone](#today-on-the-phone)
- [The wake-up alarm on the phone](#the-wake-up-alarm-on-the-phone)
- [Done and Snooze on notifications](#done-and-snooze-on-notifications)
- [Chat with Kurooto in the app](#chat-with-kurooto-in-the-app)
- [Using the app instead of Telegram](#using-the-app-instead-of-telegram)
- [Files from your computer](#files-from-your-computer)
- [Sharing files to your notes](#sharing-files-to-your-notes)
- [Widgets, Quick note and the tile](#widgets-quick-note-and-the-tile)
- [When your computer is off](#when-your-computer-is-off)
- [Managing paired phones](#managing-paired-phones)
- [A lost phone, or keys that got out](#a-lost-phone-or-keys-that-got-out)
- [What leaves your computer](#what-leaves-your-computer)

---

## Pair a phone

1. On your computer: Dashboard → **Phone** → **Pair a phone**. A QR code appears. Or send `/phone` to your bot and
   tap **Pair this phone** on the phone itself.
2. Scan the QR code with your phone's camera (or open the link). The pairing code works for 15 minutes.
3. Follow the page for your phone (below).

Each time a device pairs, Kurooto tells you on Telegram: "A device was paired with your call line: <name> (<kind>).
If that wasn't you, remove it with /phones." This message always comes; it's never held or stopped.

## Android

**What you get.** The Kurooto app rings like a real phone call (full screen, even on the lock screen), uses the
earpiece with the screen off at your ear, rings wake-up calls on the alarm volume (so they ring on silent), shows
Kurooto's questions and approvals with a Reply box, and lets you share files into your notes. It works from Android 6.

From 0.7.0 the app opens on four tabs: **Today**, **Inbox**, **Views** and **Phone**, and its icon is Kurooto's mark,
a moth (a themed icon on Android 13 and up, if your launcher uses them).

**Switches** (Phone tab, 0.7.2): **Connect straight to your call line** (on; off: calls and messages come through
ntfy.sh only, as before 0.7.0) and **Moving background** (on; off: a still picture, as with Android's "Remove
animations"). Views is off until you turn it on in the dashboard → Phone.

**Install and pair.**
1. On the pairing page, tap **Download the app**, open the downloaded file and tap **Install**.
   - "For your security, your phone isn't allowed to install unknown apps": tap Settings and allow it for your
     browser. Kurooto isn't on the Play Store.
   - Play Protect warns: tap "More details" → "Install anyway".
2. Back on the page, tap **Pair the app**. The app opens, pairs ("Paired. You're all set.") and shows a checklist.
   You can also paste the pairing link into the app.
3. Fix every item on the **Checklist** until each has a tick:

| Checklist item | Why |
|---|---|
| Notifications | Calls, questions and wake-up alarms arrive as notifications. |
| Microphone | For calls. |
| Full-screen calls (ring on the lock screen) | Android 14 and newer ask for this separately. |
| Alarms at the exact time (the wake-up alarm on this phone) | Android 12 and newer: lets the phone's own copy of the wake-up alarm ring at its minute. Without it, it may ring a few minutes late. |
| Battery: unrestricted (keeps listening) | Without it Android stops the app in the background and calls don't ring. |

   On Samsung, Xiaomi, Oppo, Vivo, OnePlus and Huawei phones, also take Kurooto off any "sleeping apps" or "deep
   sleep" list in Settings → Battery, or calls may not ring.
4. Test it: Dashboard → Phone → **Ring my phone (test)**. The Phone tab says **connected** beside the phone once the
   app is connected straight to your call line (below).

**How calls reach the phone (0.7.0).** The app keeps its own connection to your call line, so calls, messages, the
chat and Today come straight from there. [ntfy.sh](https://ntfy.sh) is only the fallback: for a moment when the
phone isn't connected (asleep a long time, no signal, just restarted), and as a second copy of every ring; the app
rings once whichever copy comes first. ntfy limits each internet address, and on a campus or office network that
address is shared, so ntfy can refuse ("429"); a free ntfy account doesn't change that (ntfy counts it by address
too). With the app connected it doesn't matter. The connection is light: the app says it's there about once a minute
while the phone is awake and every few minutes while it sleeps, and nothing in between. **This phone** at the bottom
of the app's screen says whether it's connected right now.

**The app's screen** (0.7.0) has four tabs, in the bar at the bottom:

- **Today**: the date, big, then **Call** and **Chat**, then your day (see [Today on the phone](#today-on-the-phone)):
  the alarm, classes and events, what's due, reminders, open threads, and a button when a newer app is out.
- **Inbox** (a number on it says how much waits): check-ins and quiz questions, answered right on their card (see
  [Check-in and quiz cards](#check-in-and-quiz-cards)); open questions, approvals and messages (tap one to answer it);
  and what's **waiting for your computer** (things you sent while it was off).
- **Views**: your computer's **Systems** and **Notes map** (see [Systems and the Notes map on the
  phone](#systems-and-the-notes-map-on-the-phone)); the two buttons at the top switch between them.
- **Phone**: the **Checklist** (a tick for each thing that's set up, **Fix** beside the rest), **Location reminders**
  (Places, see [Location reminders](#location-reminders)), the **Ringtones** (**Call ringtone** and **Wake-up alarm
  tone**, each showing the tone it's set to; tap to change it. The alarm tone plays on the alarm volume), **Bedside
  mode** ([below](#bedside-mode-android)), and **This phone** (what it's paired with, the app's version, and **Unpair
  this phone**, which asks first).

Pull a tab down to look again; the app also looks each time you open it. Back on Inbox or Phone goes to Today. It
starts listening again by itself after the phone restarts or the app updates ("Listening for calls" stays as a quiet
notification).

**Its look** follows the phone: light or dark as the phone is set, and on Android 12 and newer in your wallpaper's
colours (Material You). Older phones get Kurooto's own greens. The main screen is Material 3 Expressive (Android 16's
style: rounded groups of rows, large buttons that change shape as you press them, big titles that fold away as you
scroll). The ringing screen is always dark, like the call itself; the other screens keep their cards and rounded
buttons, and the chat has a bar at the top with a back arrow. Behind the main screen is a living background in the
same colours, as the dashboard's SYSTEMS view draws Kurooto: a cell with soft rims and a nucleus that breathes slowly,
fine nerves drifting out of it, and a sky tinted by the hour (cooler at night, warmer at dawn and dusk). The cell
crosses the top of the screen with the day, like the sun on the website. It's strongest on Today, faint on Inbox and
Phone, stops when the app isn't on screen, and holds still with **Remove animations** on (Settings → Accessibility);
on Android 11 and older it's a still picture. The app's icon is the call line's: a white handset in a green circle (on Android 13 and newer it follows
themed icons if you use them).

**A ringing call** shows **Answer**, **Decline** and **Later** (**Snooze** for the wake-up alarm). On Android 12 and
newer the notification looks like the phone's own incoming calls (a red Decline, a green Answer). What each does is in
[Calls: Kurooto calling you](calls.md#kurooto-calling-you).

**Speech on the phone.** For calls that go turn by turn (when Google's live voice is down, or by choice with
`calls.voice_mode` = `phone`), the app uses Android's own speech recognizer and voice. On Android 13 and newer it
recognises speech on the phone itself when your language is downloaded for on-device recognition (in the phone's
language or speech settings; the place differs by phone). Then your voice never leaves the phone.

**Updates.** The app checks for a new version when you open it (at most every 2 minutes) and shows an **Update
available** button that opens the download. Install it over the old one; you stay paired. The pairing page always
offers the newest app. Every app is signed with Kurooto's release key and listed in the signed release it belongs to.
After your computer updates Kurooto, it also downloads the app that goes with the new version (with Phone calls on),
checks it against that signed list, and your call line is updated with it a minute later (never during a call; if
it's offline it tries again every 30 minutes, and you get a message only if it fails twice), so the pairing page
hands out the app that goes with your version. The pairing page shows the app's version next to "Download the app",
so an old one is easy to spot.

**Without the app.** The pairing page also offers "Use this page as an app instead". It works, but rings less
reliably.

## Bedside mode (Android)

An old Android phone on a charger by your bed, as a dock. It shows:

- a big **clock** and the date;
- the **next alarm**: Kurooto's wake-up call ("Wake-up call 06:30"), or the phone's own alarm if that comes first;
- the **calls due next** (a check-in, a reminder call; up to three) and how many things are **waiting for you**;
- one big **Talk to Kurooto** button: one tap starts a voice call with Kurooto, the same call screen as the app's
  **Call** button. **Chat** and **Close** are the small buttons below it.

**Open it** from the app's **Phone** tab: **Bedside mode** → **Open bedside mode**.

**On the lock screen.** It shows over the lock screen, so the dock can stay locked: **Talk** works without unlocking.
**Chat** and "waiting for you" ask you to unlock first. With a PIN, pattern or fingerprint lock, the calls' reasons
show as "a call (unlock to see)" until you unlock; the times and the wake-up call still show.

**Brightness by the hour.** By day the phone's own brightness; from 20:00 lower, from 22:00 to 06:00 as dim as the
screen goes, in a warm red-orange with no blue; 06:00 a little brighter. Tap anywhere to brighten it for 15 seconds.

**Calls and the alarm ring there.** A call from Kurooto or the wake-up call opens full screen over bedside mode (on
the alarm volume, as always); after the call you're back at the clock. Keep the app listening (the checklist's
**Battery: unrestricted**) or nothing rings.

**Settings** (the app's **Phone** tab, under **Bedside mode**):

| Setting | Default | What it does |
|---|---|---|
| Open by itself while charging | Off | Pick the hours (say 22:00 to 07:00). Plugging the phone in during them, or the hours starting while it charges, opens bedside mode; unplugging closes it if it opened by itself. On Android 10 and newer it opens through a full-screen notification: by itself with the screen off, as a notice to tap while you use the phone. |
| Keep the screen on while charging | On | Off: the screen times out as usual (bedside mode is still there when you wake it). |

What's coming is read from your call line every 5 minutes: the calls your computer has booked for the next day,
so it works with the computer asleep. Reminders, deadlines and classes aren't on it (see
[What it can't do yet](what-it-cant-do-yet.md#android)). Nothing new leaves your computer for it.

## iPhone

**What you get.** Kurooto as a web app on your Home Screen (iOS 16.4 or newer): calls arrive as notifications you tap
to answer, and questions and approvals show in **Waiting for you** with the same buttons and a box to type in.

**Install and pair.**
1. Open the pairing link in **Safari** (not another browser).
2. Tap the Share button → **Add to Home Screen** → **Add**.
3. Open **Kurooto from the Home Screen** (not from Safari). It finishes pairing there.
4. Tap **Turn on notifications** and allow them.

**Tell Kurooto.** Right after pairing, the page shows how to make a Siri Shortcut: see
[below](#tell-kurooto-siri-and-back-tap-iphone).

**What doesn't work on iPhone.** Calls can't ring like a phone call, ring on silent, or show on the lock screen as a
call: they're notifications you tap. Reminders with the lid shut don't reach an iPhone. If you need those, rely on
Telegram reminders or use an Android phone. The iPhone app updates itself.

**Speech.** Turn-by-turn calls use Safari's speech; Safari asks you to allow dictation. Answers are read aloud only
where the browser has a voice.

## Tell Kurooto: Siri and Back Tap (iPhone)

A Shortcut that sends what you say to Kurooto, as if you'd typed it in the chat, and reads you the answer: "Hey Siri,
Tell Kurooto", or a double tap on the back of the iPhone.

Apple doesn't let a web page make a Shortcut file, so you build it once, by hand. The recipe comes right after pairing
(in the Home Screen app), and any time under **Settings** in the Home Screen app (or `<your call line>/settings`). Your
link is filled in: copy it with **Copy the link**, or scan its QR code on another Apple device.

1. Open the **Shortcuts** app, tap **+**, and name the shortcut **Tell Kurooto** (the name is what you say to Siri).
2. Add the action **Dictate Text**.
3. Add **Get Contents of URL** and paste your link. Tap the arrow: Method **POST**, Request Body **JSON**, add a
   **Text** field with key `text` and, as its value, **Dictated Text**.
4. Add **Speak Text** (or Show Result) with **Contents of URL**.
5. Tap **Done**, run it once, and tap **Always Allow** when it asks to connect to your call line.

Then: **Siri**: "Hey Siri, Tell Kurooto", then what you want. **Back Tap**: Settings → Accessibility → Touch → Back Tap
→ Double Tap (or Triple Tap) → Tell Kurooto. On an iPhone with an Action button: Settings → Action Button → Shortcut →
Tell Kurooto.

**What it does.** Your words go to your computer like a chat message from that iPhone: commands, "remind me at 9 to
...", questions for your AI. Kurooto's first answer is read out ("On it." for longer jobs) and the full answer comes in
the chat with a notification. With the computer off: "Your computer is off: this waits on your call line ...", and it
goes through when the computer is back.

| You hear | Means |
|---|---|
| This Tell Kurooto link was revoked or is wrong. | It was revoked, replaced by a new link, or the iPhone was unpaired. Make a new link in Settings and paste it into the Shortcut. |
| I heard nothing to send. | Dictation caught nothing. Try again. |
| Your computer is off: this waits on your call line ... | It's kept and goes to the computer when it's back. |

**Keep the link to yourself.** Anyone with it can send Kurooto messages as that iPhone (only messages: it can't read
anything, answer questions or call). Each iPhone has one link at a time.

**Revoke it:**
- on your computer: dashboard → **Phone** → **Tell Kurooto (iPhone Shortcut)** lists each link (phone, when made, last
  used) with **Revoke**; the Shortcut stops working at once and the phone stays paired;
- on the iPhone: Settings → **New link** (the old one stops working; paste the new one into the Shortcut) or **Remove**;
- unpairing the iPhone (dashboard, `/unpair`) ends its link too, and so does `kurooto rotate`.

Each time a link is made, Kurooto tells you ("A Tell Kurooto link was made on iPhone ..."); this message always comes.

## Any browser

- `/call` on Telegram gives a link that calls Kurooto from any phone or browser, for 2 hours.
- The pairing page has **Pair this browser**: that browser can then start calls and show Kurooto's notifications
  (calls, questions, approvals).
- Turn-by-turn calls in a browser need Chrome (or Safari with dictation allowed).

## What reaches the phone

Calls always ring your paired phones. Besides calls, the phone gets what `notify.app_kinds` lists (Dashboard →
Settings → notify):

| Setting | Default | Effect |
|---|---|---|
| `notify.app_kinds` | `["call", "question", "approval"]` | Kinds of message that also go to the phone app. Add `"reminder"`, `"deadline"`, `"result"` or `"info"` to get those there too. Remove `"question"` and `"approval"` to keep them on Telegram only. |
| `notify.app_chat` | `false` | Kurooto's own messages (reminders, results, info: everything not in `notify.app_kinds`) also show in the app's chat. Turn it on where Telegram is blocked. |

Everything that goes to the phone still goes to Telegram as well. The phone's list keeps at most 40 items; a message
that isn't a question stays on it for a day.

**Questions come from any feature**: a check-in, after-class notes, a quiz, an exam-eve question, a suggestion from
the nightly look back, a reply draft to approve, your own scripts (`kurooto ask-me`).

## Answering questions on the phone

**Android.** A notification with **Reply** (type the answer right in the notification; on Android 6 it opens a small
answer window), the question's choices, **Approve / Deny** for approvals, **Later** (ask me on the next call), or the
message's own buttons. Tap the notification for every option. The app's **Inbox** tab lists what's waiting for you
(check-ins and quiz questions as [cards](#check-in-and-quiz-cards) you answer right there).

**+1 on a deadline.** With `"deadline"` in `notify.app_kinds`, a deadline with parts still to do comes with **+1**,
**Done** and **Snooze 3 h** (Android shows three buttons; tap the notification for the rest, **Reply** and **Not mine**
among them). **+1** counts one more part done and the notification stays, showing "Problem set 3: 5/7, 2 to go...",
so you can tap it after each question. In the app's chat, **+1** is under the message, and on the chat's notification
too. **Reply** with `4/7` or `done` works as well
([reminders-and-deadlines.md](reminders-and-deadlines.md#problem-set-progress)).

**iPhone.** A notification; tap it to open **Waiting for you** in the Home Screen app, with the same buttons and a box
to type in.

**How answers work.**
- The first answer counts, wherever you give it: a button or reply on Telegram, the phone, or a call. The others go
  away.
- If your computer is off, your answer waits on your call line and is used as soon as the computer is back ("Your
  answer from the phone: ...").
- Your answer is sealed (Android) or sent over an encrypted connection (iPhone), and can be used once.

| What you see | Means |
|---|---|
| Not sent: tap to try again | The phone was offline or the call line didn't answer. Tap to try again, or answer on Telegram. |
| That answer is too old (or this phone's clock is off). Try again. | An answer must reach the call line within 10 minutes of being sent. Set the phone's clock to automatic, then answer again. |
| That's no longer open | It was answered somewhere else (Telegram, a call, another phone) or it expired. Nothing to do. |
| That answer couldn't be opened here. Pair the phone again. | The phone's keys don't match any more (after `kurooto rotate`, say). Pair again. |
| This phone was unpaired. Pair it again from your computer. | It was removed with `/unpair` or the dashboard. |

## Check-in and quiz cards

On the **Inbox** tab, the evening (or midday, night) check-in and quiz questions are cards you answer in place:

- **Check-in:** the question (and, in the evening, what today's records show you did), a box for how it went, **Send**,
  and its buttons (**In 30 min**, **Not tonight** or **Skip today**, **Tomorrow morning** for the night one). Your
  answer goes into your journal, as a reply on Telegram does.
- **Quiz:** the question and a box for your answer. With Chat on, your AI grades it and the reply says the key idea;
  without it, the next card shows what the note says with **Forgot**, **Hard**, **Good** and **Easy**. Link recall
  cards work the same way.

With your computer asleep, the answer waits on your call line ("Saved. Your computer gets it when it is back on.")
and is used when it's back; the quiz's grading card comes then. What you typed but didn't send stays in the box
while the app is open. The cards need Kurooto 0.6.0 on the computer too (older ones still show these questions as
plain cards that open the answer window).

## Location reminders

"Remind me when I reach the library to return the book." Off by default. In the app: **Location reminders → Places →
Turn on location reminders**. The battery cost is said first, and the app asks to use the phone's location only then
(and, on Android 10 and newer, "Allow all the time" so reminders come with the app closed).

- **Save a place:** stand there, type a name, **Save this place** (no map; it takes up to 30 seconds to find where the
  phone is). A place counts within 150 m.
- **Reminders:** say it on Telegram or in the chat (turn on Settings → Reminders → places on the computer too), or
  type one under the place: once, or every time you arrive.
- **Waiting for a place:** a reminder for a name you haven't saved yet; tap "I'm here: save it as ..." when you're
  there.
- **Turn off:** the button at the bottom of Places. Your places and reminders stay on the phone; nothing is watched.

Where your places are never leaves the phone. Details: [reminders-and-deadlines.md](reminders-and-deadlines.md#at-a-place-location-reminders).

## Today on the phone

Android, 0.6.0. The app's **Today** tab shows, under **Call** and **Chat**, the main parts of the dashboard's Today
page, as your computer last sent them. If the copy is from an earlier day, it says which.

- **When it's from:** "As of 14:05" (when your call line got it), and "your computer is off" when it is. It shows
  with the computer asleep or off, and with no internet on the phone (the copy the app last fetched).
- **Alarm:** the next one, the daily alarm, and **Ring on this phone too** (see below).
- **Classes and events:** today's classes (a class you're skipping says so) and your calendar, in time order (all-day
  events first). Something that began the night before shows when it ends: "until 06:00  Busy".
- **Due:** what's due, soonest first, with parts done ("4/7 · due tomorrow", and a wavy bar). Tap one for **+1** and **Done**: the same
  as those buttons on the deadline's Telegram message. With the computer off, the tap waits on your call line and
  counts when it's back; "Waiting for your computer" lists it meanwhile. Quizzes and exams have no buttons.
- **Reminders** and **open threads** (what you're in the middle of, with memory threads on).
- How many questions wait for you; tap the line to go to **Inbox**.

Your computer sends a new list within seconds of a change on it (a deadline done on Telegram, an alarm set) and looks
for changes every 5 minutes; the phone fetches it when it's told, when you open the app, and when it reconnects. Turn it off with `calls.today` (Dashboard → Settings → calls): the app then says "Turned off
on your computer" and no alarm is set on the phone from it.

**"Nothing here yet"** means your call line has no copy for this phone yet. The app gives the call line its key
after pairing, and the list follows within a minute or two while your computer is on. If that send failed (no
internet just then), opening the app tries again (0.6.1; on 0.6.0, swipe the app away and open it again).

**iPhone and browsers** don't get Today: it's sealed with a key only the Android app has.

## Systems and the Notes map on the phone

Android, 0.7.0, off until you turn it on: dashboard → **Phone** → **Show Systems and the Notes map in the Android app**
(the setting `calls.views`). Then the app's **Views** tab shows them: **Systems** and **Notes map** at its top switch
between the two, and it opens on the one you looked at last.
They're the dashboard's own drawings, drawn on the phone by the same code, in the app's colours (light or dark).

- **Systems:** the beating core and your features round it, as on the dashboard. **Tap a feature** for its card: how
  busy it was in the last 2 minutes, its program (cpu, memory, uptime), when it last did something and runs next, and
  what needs a look, if anything. Tap the core for Kurooto's own card and what needs a look. Drag to turn the ring and
  pinch to zoom; both spring back. While it's open it's live: the app tells your computer every 20 seconds, and your
  computer sends a fresh copy every few seconds until the app stops asking.
- **Notes map:** your notes and their links, coloured by course and project, with the regions' names. **Drag** to move
  the map, **pinch** to zoom, **tap a note** for its card (its title, where it is, links, words, when it changed);
  tap the empty map to fit it again. Your computer sends it when your notes change (at most every few minutes) and
  once an hour anyway. It holds up to 5,000 notes and 20,000 links (the best-linked first; a book's "Seen in" links
  are the first links left out); set `calls.views_notes` and `calls.views_links` lower if the map is slow on an old
  phone. A folder too big for your call line is cut just enough to fit, and the map says how many were left out.
- **Read-only:** nothing on these screens changes anything. Notes' contents never reach the phone.
- **When it's from:** "live" while your computer is sending Systems, else "as of 14:05". With your computer asleep
  the last copy shows with "your computer is asleep"; with no internet, "can't reach your call line".

**"Nothing here yet"**: the switch is off on your computer, the computer hasn't been on since you turned it on, or
your call line is older than 0.7.0 (it's updated at 05:10). **"This phone's web view is too old"**: update Android
System WebView (or Chrome) from the Play Store; the drawings need version 58 or newer.

**iPhone and browsers** don't get them: they're sealed with a key only the Android app has.

## The wake-up alarm on the phone

Android, 0.6.0. Every alarm you set (and the next daily one) is also set on the phone with Android's own alarm clock:
it shows in the status bar, survives deep sleep, and rings full screen on the alarm volume **even if your computer is
off and your call line or the internet can't be reached**. It rings like the wake-up call, with **Stop** and
**Snooze**.

- **One alarm, not two.** The call from your call line comes too. Whichever rings first is the one you hear; the other
  joins it (the call adds **Answer** to the alarm's screen). The first **Stop**, **Snooze** or **Answer** counts for
  both: Stop turns the call down (as Decline does), Snooze snoozes it (`alarm.snooze_min`, 10 minutes, on the phone as
  well), Answer starts the wake-up call. A call that comes after you stopped the phone's alarm doesn't ring.
- **Only your own alarms.** The phone copies what your computer has: alarms you set yourself, by message, command,
  call or a button you tapped. The app never sets one of its own; the AI can't set one without your tap either.
- **Ring on this phone too** (Today's alarm group, **On** / **Off**): tap to turn the phone's copy off or on. Off, only the call rings.
- **Android 12 and newer** asks for exact alarms: the checklist's **Alarms at the exact time** and Today's **Allow
  exact alarms** open the setting. On Android 13 and newer the app has it from the start. Without it the alarm is set
  as close as Android allows, which can be a few minutes late in deep sleep, and Today says so.
- **What it needs from your computer:** the list of alarms, sent with Today. An alarm you set or cancel while the phone
  is offline reaches it when it's online again. The daily alarm is sent one morning at a time: the phone always has
  the next one, and the one after once your computer has been awake after the next rings.
- Alarms less than 5 minutes apart ring on the phone as one.

## Done and Snooze on notifications

With `"reminder"` or `"deadline"` in `notify.app_kinds` (Dashboard → Settings → notify), their notifications carry the
buttons Telegram shows, so you can deal with them from the notification shade:

| Notification | Buttons | What they do |
|---|---|---|
| A reminder | **Done**, **+10 min**, **+1 h** | Done takes it down here and on your other phones; +10 min and +1 h remind you again then (as on Telegram) |
| A deadline | **+1** (with parts to do), **Done**, **Snooze 3 h** | as on Telegram: one more part, done, ask again in 3 hours |
| A reminder sent with the lid shut | **Done**, **+10 min**, **+1 h** | kept on this phone: it shows the reminder again then (your computer is asleep) |

The chat's notification gets the same buttons when a reminder or deadline comes to the chat (`notify.app_chat`, or no
Telegram). Tapping the notification still opens every option (Reply, Not mine...). With the computer off, a tap waits
on your call line and is done when it's back, in order.

## Chat with Kurooto in the app

**Android:** tap **Chat** on the app's **Today** tab. Type as you would on Telegram: a question, "remind me
at 9 to call Dr Sam Okafor", a /command. It's handled exactly like a Telegram message: the same commands, plain-English
requests and, with Chat on, your AI. The answer comes back in the chat ("On it." first, then the AI's answer when it's
done), and as a notification when the chat isn't open. Buttons under an answer work as on Telegram. **Reply** under a
message that takes one (a reminder, a check-in) answers it. Answers to what you wrote in the app come back to the app
only, not to Telegram.

**iPhone (and any paired browser):** open Kurooto from the Home Screen and tap **Chat** (or open `<your call
line>/talk`). It works like the Android chat: buttons, **Reply**, and "Waiting for your computer" while it's off. A
notification for a chat message opens the chat. The page keeps its own copy of the chat in the browser and looks for
new messages every few seconds while it's open.

**Kurooto's own messages in the chat.** With `notify.app_chat` on (Dashboard → Settings → notify), reminders,
results and other messages also show in the chat, besides Telegram. Without Telegram they always do. Questions and
approvals stay under **Waiting for you**, with their answer buttons.

**What you see under your message:**

| Under your message | Means |
|---|---|
| Sending… | On its way to your call line. |
| Waiting for your computer | Your computer is off. It waits on your call line and goes to the computer when it's back; then this goes away and the answer comes. |
| Not sent: tap to try again | The phone was offline, or your call line refused it (the reason is in brackets). Tap the message to send it again. |

## Using the app instead of Telegram

Telegram is optional (0.5.18). In setup, on the **Chat** step, pick **The Kurooto phone app instead**. It needs
[Phone calls](calls.md) (a free Gemini key and your call line on a free Cloudflare account; the Features step sets it
up), then you pair your phone right there or after **Finish setup**. Already set up with Telegram? Turn Telegram off
in Features: as long as Phone calls is on, everything moves to the app.

Without Telegram:

- Everything Kurooto says comes to the app's chat: reminders, check-ins, the morning message, what's due, your AI's
  answers, "after the call" notes, with their buttons (Snooze, Done, Why?, Less of this...). Questions and approvals
  come as notifications with answer buttons and under **Waiting for you**.
- `/pause`, `/resume`, `/status`, `/focus`, `/hold` and `/calls` work in the chat, and `/help` lists them with
  everything else, the same index as on Telegram; links in messages (each `/help` group's wiki page) open with a tap.
- Features that send you things (Reminders, Check-ins, Deadlines, Weekly summary...) turn on with the app instead of
  Telegram. Voice notes and Files into notes still need Telegram (they're about what you send the bot; share files
  to the app instead).
- A file Kurooto would have sent on Telegram (a long answer, `kurooto send`, a file your AI sends you) comes as a link:
  see [Files from your computer](#files-from-your-computer).
- `kurooto doctor` says "talks to you: in the phone app's chat" and doesn't count the missing bot as a problem.

What Telegram still does better: voice messages, sending files straight from Telegram's own share sheet on any
device, and a desktop app. You can add Telegram later (Features → Telegram); then both work, and the chat gets
Kurooto's own messages only with `notify.app_chat` on.

## Files from your computer

The chat doesn't carry files, so where Telegram would get a document, the chat gets a button that opens a link:

1. **Google Drive**, with [Drive upload](google.md) on: the file goes to the Kurooto folder in your Drive and **Open
   in Drive** opens it. It's deleted from your Drive after `drive_upload.temp_days` (7) days; move it out of the folder
   to keep it.
2. Otherwise **your call line** keeps a sealed copy for a day (files up to 10 MB). **Open** shows it in the phone's
   browser, with **Save** (and the text itself for a text file). The key that opens it is made on your computer and is
   only in the link, never stored on its own; after a day the copy is deleted and the link says "This file is gone".
3. If neither works (the call line isn't connected, or the file is bigger), the chat says the file stays on your
   computer, with its path.

## Sharing files to your notes

**Android:** in any app, Share → **Share to Kurooto** (one file or several). Each goes into your notes' `inbox/` (or
your files folder's, if you set one). With Chat on, the AI files it where it belongs and tells you where; without
Chat you get "Got <file> from your phone: saved to ...". Files can be up to 50 MB each. A small window shows the progress, then
"Sent." in green or what went wrong in red, and closes by itself. With the computer off, a file up to 20 MB waits on
your call line (below). Then ask about it in the chat: "summarise the PDF I just sent" works for
files shared in the last two hours (your AI is told their names and where they are).

**A photo of a notice or a timetable:** share it, then say "dates from that photo" (or `/dates`) in the app's chat.
Your AI reads it and its dates come back with an **Add** button each; nothing is added until you tap
([reminders-and-deadlines.md](reminders-and-deadlines.md#photo-to-dates)).

## Widgets, Quick note and the tile

Android only. None of these need setting up beyond pairing; each opens the app's own screens.

| What | Where to add it | What it does |
|---|---|---|
| **Talk to Kurooto** widget (1x1) | Home screen: long-press an empty spot → Widgets → Kurooto | One tap opens the chat with the keyboard up, ready to type (use your keyboard's microphone to speak). |
| **Talk, and what's waiting** widget (2x1) | The same list | The same Talk button, and beside it the newest question or message waiting for you ("2 waiting: ..."), or "Nothing waiting for you". Tap the text to open the app. |
| **Quick note** shortcut (Android 7.1+) | Long-press Kurooto's app icon; drag it out to make its own icon | A small box: type a note, tap **Save to notes**. |
| **Quick note** tile (Android 7+) | Pull down Quick Settings → the pencil (edit) → drag **Quick note** in | The same box. On a locked phone it asks you to unlock first. |

**Where a quick note goes.** Into your notes' `inbox/` on your computer as `<date>-quick-note.md`, the same way a
shared file does: with Chat on, the AI files it where it belongs and tells you where; without Chat you get "Got
quick-note.md from your phone: saved to ...". With the computer off the note waits on your call line and goes to the
inbox when the computer is back ("Your computer is off: the note waits on your call line ..."). If it couldn't be sent
(no internet), it stays in the box, also after you close it, until you tap **Save to notes** again.

**What the 2x1 widget shows** is the newest of what the app's **Inbox** tab lists. It looks again every 30 minutes,
when a question arrives or is answered, and each time you open the app. It shows the message's text on your home
screen, like a notification would. Use the 1x1 widget if you'd rather not.

Android 6 has the widgets but no shortcut or tile (those came with Android 7). Removing a widget or the tile is the
undo: nothing else changes.

## When your computer is off

What you do on the phone while your computer sleeps isn't lost: chat messages, button taps, answers to questions
and shared files wait on your call line (the "phone outbox") and go to the computer when it's back, in the order you
sent them, each once.

- The chat shows **Waiting for your computer** under each one; the app's **Inbox** tab lists what's waiting.
- **+1** taps on a deadline count one each, in order: three taps while the laptop sleeps are three parts done when
  it's back. The notification says the tap is waiting and keeps its **+1**. **Done** and **+1** on Today wait the
  same way.
- **Today** shows the copy your computer last sent ("As of ..."), and the wake-up alarm rings on the phone by itself.
- When the computer takes one, the phone hears it: the chat's mark goes away and the answer comes, and for an answer
  or a file you get a quiet "Reached your computer" notification.
- The call line holds at most 100 things and 20 MB of files. When it's full: "Your call line is holding as much as it
  can for your computer." Wait till the computer is back, or use Telegram.
- Sharing a file with the computer off needs this version of the app (it shares with the phone's own key; older ones
  asked the computer first).

## Managing paired phones

| Where | How |
|---|---|
| Telegram | `/phones` lists paired phones with their id, kind, whether notifications are on, and since when. `/unpair <id>` removes one (ids are 8 characters from `/phones`). |
| Dashboard → Phone | Your call line's address and whether it's connected; **Pair a phone**; **Ring my phone (test)** (only while connected); the list of phones with **Remove**; the iPhones' Tell Kurooto links with **Revoke**. |
| Android app | **Unpair this phone** unpairs it on the phone; also remove it on your computer (the dashboard's Phone tab, or `/phones`). |

## A lost phone, or keys that got out

Run `kurooto rotate` on your computer. Use it when a paired phone is lost or stolen, or a backup zip with your keys
(`backups.secrets`) or a diagnostics file got out.

**What it replaces:** this computer's key to the call line, the key that signs call links (links sent before stop
working), the phone notification key and channel (Android) and the Web Push keys (iPhone).

**What happens:** it asks first (`--yes` skips that), redeploys your call line with the new keys (a minute or two;
same address), and the line forgets every paired phone, every call link it made, every Tell Kurooto link and open
pairing codes. If the deploy
fails, the old keys are put back and nothing changed. With Kurooto running it then prints a pairing link and QR code.

**Pair again:**
- *Android:* in the app tap **Unpair this phone**, then open the new link on the phone (or scan the code).
- *iPhone:* delete Kurooto from the Home Screen, open the link in Safari and add it to the Home Screen again.
- Another phone: `/phone` on Telegram, or Dashboard → Phone → **Pair a phone**.

It also lists the keys only you can replace: your bot's token (@BotFather's `/revoke`), Google's access
(myaccount.google.com/connections), the GitHub token for your notes, and your Gemini key. Replace the Gemini key
*before* `kurooto rotate`, so the redeploy takes the new one to your call line. A lost phone signed in to Telegram:
end that session from another device (Telegram → Settings → Devices). With Profile sync on, run
`kurooto profile save` afterwards.

There's no undo: the old keys are gone. A phone you don't pair again can't call or be called.

## What leaves your computer

- Questions and messages for the phone go from your computer to your call line (your Cloudflare account) to your phone.
  Android gets them on its own connection to your call line, and through ntfy.sh only when it isn't connected (and a
  second copy of each ring; anonymously, or as your ntfy account with `kurooto ntfy-token`), encrypted the same way
  either way, with a key your phones, your computer and your call line hold (ntfy can't read them); an iPhone gets
  an empty Web Push and then fetches what's waiting from your call line. Your call line keeps the last 60 of these
  sealed messages for 6 hours, so a phone that reconnects gets what it missed.
- Your call line keeps a copy of what's open (at most 40 items, each gone after a day or once it's dealt with) so the
  phone can list it while the computer is off.
- The chat: what you type goes from the phone through your call line to your computer, sealed on Android with the key
  your phones, your computer and your call line hold, and over an encrypted connection from an iPhone. Kurooto's
  answers go back like questions do. Your call line keeps the chat's last 50 messages, each for at most 3 days, so a
  phone can catch up while the computer is off.
- Files you share and quick notes go from the phone through your call line to your computer.
- The 2x1 widget asks your call line what's waiting (as the app's Inbox tab does); nothing else leaves the phone for
  the widgets or the tile.
- Tell Kurooto (the iPhone Shortcut): what you say goes, as text, from the iPhone (Apple's dictation) through your call
  line to your computer, like a chat message. The call line keeps a hash of each link (not the link), the phone it
  belongs to, and when it was made and last used.
- Bedside mode reads from your call line the calls already booked there (times and reasons) and how many things are
  waiting; nothing new goes there.
- Files from your computer for the chat (where Telegram would get a document): with Drive upload on, to your own Google
  Drive; otherwise a copy on your call line for a day, encrypted on your computer. The key is only in the link, which
  travels inside the chat message, so the copy is as private as the chat itself; ntfy never sees either.
- While your computer is off, what you send from the phone waits on your call line until the computer takes it (then
  it's deleted there): chat messages and answers as sent (sealed from Android), files as they are. A day's record of
  what went through (ids and short notes, no text you typed) stays so the phone can show it.
- Today (Android): the day's list (classes, events, what's due, reminders, alarm times, open threads) goes to your call
  line sealed for each Android phone with a key only that phone has; your call line keeps one copy per phone and can't
  read it, and nudges the phone through ntfy (with nothing in the nudge) when it changed.
- Systems and the Notes map (Android, only with `calls.views` on): your notes' titles, where they are in your notes
  folder and which link to which (never what they say), and each feature's state and health lines. Each copy is
  sealed on your computer, and its key sealed for each Android phone with a key only that phone has; your call line
  keeps the newest of each and can't read them. Systems goes only while you're looking at it. Turning it off drops the
  call line's copies.
- Call audio: see [Calls: what leaves your computer](calls.md#what-leaves-your-computer).

**Turn it off.** Unpair the phone (above). To stop questions reaching the phone but keep calls, take `"question"` and
`"approval"` out of `notify.app_kinds`.
