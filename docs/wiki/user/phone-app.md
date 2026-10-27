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

**On another call?** From 0.7.3 the app doesn't ring over a call: if your phone is already in one (a phone call,
WhatsApp, Meet, or one of Kurooto's own), a quiet note says Kurooto called and the call rings again after its usual
wait. A wake-up alarm still rings. Your computer also won't start one of Kurooto's calls while another is going on or
ringing: the second waits.

From 0.8.10 the app opens on **Chat**, with four more panes beside it: **Today**, **Alarms**, **Views** and
**Settings** (see [The app's panes](#the-apps-panes-0810)). Its icon is Kurooto's mark, a moth (a themed icon on Android
13 and up, if your launcher uses them).

**Switches** (0.7.2; since 0.8.10 in **Settings → Calls** and **Settings → Look**): **Connect straight to your call line** (on; off: calls and messages come through
ntfy.sh only, as before 0.7.0) and **Moving background** (on; off: a still picture, as with Android's "Remove
animations"). Since 0.7.5 two more: **Vivid colours** (on: a fuller, more colourful scheme in your wallpaper's own colours (0.8.10: before, it could turn
them into other hues), with tinted cards; off: Android's own quieter colours) and **Floating bar** (on: the panes are a rounded bar floating over the page, the
open one in a filled pill; off: the bar sits on the bottom edge as before). Views is off until you turn it on in the dashboard → Phone.
Since 0.8.7: **New call screen** (on: the ringing screen and the call in the new style, below; off: the call screen from before
0.8.7, kept while the new one gets used for real calls).

**The smaller screens** match (0.8.10, the Rail look): the question you answer from a notification, Quick note, Share to Kurooto and the pairing window are rounded sheets floating at the bottom of the screen over a dimmed background. They slide up when they open; to close one, tap outside, drag it down by its handle (or fling it), or swipe back (on Android 14 and newer the sheet shrinks as you swipe, and you can change your mind). The question shows Kurooto's message as a chat bubble, its choices as round buttons and a box with a round Send; Share to Kurooto lists what's going with each file's kind (PDF, PNG, LINK...), its size, and a tick when it's sent (a clock while it waits for your computer). **Places** is a page of rounded cards: each place's pin in a shape of its own colour, its reminders as pills you can remove, a box with a round Add, and **Every time I arrive** as a chip. With **Remove animations** on, nothing slides.

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

### The app's panes (0.8.10)

The app opens on **Chat**. The other panes are in a bar floating at the bottom (icons with their names, the open one
in a filled pill); in Chat the same five icons sit upright at the foot of the chat's rail, and moving to another pane
the rail slides away to the left while the upright icons stretch out into the bar (back to Chat, the other way). The
Chat icon's number counts unread messages and what's waiting for you. Back from any pane goes to Chat (swipe slowly
from the edge on Android 14 and newer and the move follows your thumb); back from Chat leaves the app.
In **Views**, **Brain**, **Heart**, **Senses** and **Memory** sit in a row of buttons at the top, with **More** (⋮)
for Systems, the Notes map and the Brain console (see [The being on the phone](#the-being-on-the-phone)).

- **Chat:** your conversations with Kurooto (see [Chat with Kurooto in the app](#chat-with-kurooto-in-the-app)). The
  **call button** is here, at the top: it's the only place the app starts a call. A bar at the top, "2 waiting for you",
  opens what's waiting (questions, approvals, check-in and quiz cards, and what waits for your computer) in a sheet,
  answered right there. Drag the sheet down or go back to close it.
- **Today:** the date, big; the class you're in now as a large card with a ring of the time left (or what's next, or
  that the day's done); **Waiting** and **Due soon** as two cards with their counts (tap: down to that part of the page);
  **The day** as a strip of today's classes and events with a line at now (gone-by ones dimmed, skipped ones grey);
  **Asked you** (what's waiting, answered in place); **Next** and **Alarm** (tap: Alarms); then **Due**, **Reminders**
  and **Open threads**. See [Today on the phone](#today-on-the-phone).
- **Alarms:** the next wake-up alarm from your computer as a big card (its time, day and reason, its tone, and the
  **Ring on this phone too** switch), the later ones as big numbers two to a row, **Ringtones** (tap the call ringtone or
  the alarm tone to change it) and **Bedside** (tap: bedside mode). Alarms are set on your computer.
- **Views:** the being's organs, one page each, and your computer's **Systems** and **Notes map** (see [Systems and the
  Notes map on the phone](#systems-and-the-notes-map-on-the-phone)).
- **Settings:** every setting the app has, in groups, under a search field that finds any of them by name (a ringtone
  takes you to Alarms). Tap a group and it opens out of its tile; back folds it in again.

**Where each setting went** (from the Phone tab and the other tabs before 0.8.10):

| Setting | Now |
|---|---|
| Colours: Material You or **Apricot and plum** (new), **Vivid colours**, **Floating bar**, **Moving background** | Settings → Look |
| The app's notifications and each kind of notification (opens Android's page for it) | Settings → Notifications |
| The chat's own settings | Settings → Chat |
| **New call screen**, **Connect straight to your call line**, Microphone, Full-screen calls | Settings → Calls |
| Location reminders (Places) | Settings → Places |
| Senses | Settings → Senses |
| Open bedside mode, **Open by itself while charging**, **Keep the screen on while charging** | Settings → Bedside |
| The checklist (battery, exact alarms...), what it's paired with, **Unpair this phone**, the app's version and **Update available** | Settings → This phone |
| Call ringtone, wake-up alarm tone, **Ring on this phone too**, Allow exact alarms | Alarms |
| Inbox | the "waiting for you" bar in Chat (a sheet), and Today's **Asked you** |
| Today's **Call** and **Chat** buttons | gone: calls start from Chat's call button |

Kurooto's own settings (what it does, when, with which AI) stay on your computer's dashboard; Settings says so at the
bottom. **Apricot and plum** is the app's own palette (apricot and plum on near-black, or on warm paper with the phone
in light mode); the call, bedside and small screens keep Material You for now.

Pull Today or Alarms down to look again; the app also looks each time you open it. A notification or widget can open
another pane (what's waiting opens Chat with its sheet; the alarm in the status bar opens Alarms). It starts listening
again by itself after the phone restarts or the app updates ("Listening for calls" stays as a quiet notification).

**Its look** follows the phone: light or dark as the phone is set, and on Android 12 and newer in your wallpaper's
colours (Material You). Older phones get Kurooto's own greens. **Colours (0.8.10):** Material You stays the default; you can pick the app's own **Apricot** palette instead, apricot and plum on near-black (on warm cream when the phone is in light mode), or **Kuro** (the dashboard's olive). **Vivid colours** still tints the cards and rows. The main screen is Material 3 Expressive (Android 16's
style: rounded groups of rows, large buttons that change shape as you press them, big titles that fold away as you
scroll). The ringing screen is always dark, like the call itself; the other screens keep their cards and rounded
buttons, and the chat has a bar at the top with a back arrow. Behind the main screen is a living background in the
same colours, as the dashboard's SYSTEMS view draws Kurooto: a cell with soft rims and a nucleus that breathes slowly,
fine nerves drifting out of it, and a sky tinted by the hour (cooler at night, warmer at dawn and dusk). The cell
crosses the top of the screen with the day, like the sun on the website. It's strongest on Today, faint on the other panes,
stops when the app isn't on screen, and holds still with **Remove animations** on (Settings → Accessibility);
on Android 11 and older it's a still picture. The app's icon is the call line's: a white handset in a green circle (on Android 13 and newer it follows
themed icons if you use them).

**A ringing call** shows **Answer**, **Decline** and **Later** (**Snooze** for the wake-up alarm). Since 0.8.7 the ringing
screen matches the rest of the app: dark, over Kurooto's sky in your colours (the **Vivid colours** switch), a slowly turning badge
(still with **Remove animations**), who's calling and why, and the three as big rounded buttons in a bar floating at the bottom.
Answered, the call page fills the screen as before. The **New call screen** switch brings back the old one. On Android 12 and
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

**Open it** from the app's **Alarms** pane (the **Bedside** card) or **Settings → Bedside → Open bedside mode**.

**Its look (0.8.7).** Always on black. The calls due next sit in a faint floating card, "waiting for you" is a small pill
(tap it for what's waiting, in Chat), **Talk** is a big rounded button with a handset that changes shape as you press it, and **Chat** and
**Close** share a small floating bar at the bottom. By day the Talk button and the cards take the app's colours (Vivid or
Calm); from 20:00 to 07:00 everything turns the warm, dim red-orange below.

**On the lock screen.** It shows over the lock screen, so the dock can stay locked: **Talk** works without unlocking.
**Chat** and "waiting for you" ask you to unlock first. With a PIN, pattern or fingerprint lock, the calls' reasons
show as "a call (unlock to see)" until you unlock; the times and the wake-up call still show.

**Brightness by the hour.** By day the phone's own brightness; from 20:00 lower, from 22:00 to 06:00 as dim as the
screen goes, in a warm red-orange with no blue; 06:00 a little brighter. Tap anywhere to brighten it for 15 seconds.

**Calls and the alarm ring there.** A call from Kurooto or the wake-up call opens full screen over bedside mode (on
the alarm volume, as always); after the call you're back at the clock. Keep the app listening (the checklist's
**Battery: unrestricted**) or nothing rings.

**Settings** (the app's **Settings → Bedside**):

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
message's own buttons. Tap the notification for every option. The "waiting for you" bar at the top of the app's Chat (and **Asked you** on Today) lists what's waiting for you
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

In what's waiting (Chat's "waiting for you" sheet, or Today's **Asked you**), the evening (or midday, night) check-in and quiz questions are cards you answer in place:

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

"Remind me when I reach the library to return the book." Off by default. In the app: **Settings → Places → Places →
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

Android, 0.6.0 (0.8.10: cards). The app's **Today** pane shows the main parts of the dashboard's Today page, as your
computer last sent them, as cards (see [The app's panes](#the-apps-panes-0810)). If the copy is from an earlier day, it says which.

- **When it's from:** "As of 14:05" (when your call line got it), and "your computer is off" when it is. It shows
  with the computer asleep or off, and with no internet on the phone (the copy the app last fetched).
- **Now:** the class you're in, until when, with a ring of the time left; between classes, what's next and how long until.
- **Alarm:** the next one (tap it for the Alarms pane, where **Ring on this phone too** is; see below).
- **The day:** today's classes and your calendar on one strip, by the hour, with their names and times under it (a class
  you're skipping says so). Events without an end are shown an hour long.
- **Due:** what's due, soonest first, with parts done ("4/7 · due tomorrow", and a wavy bar). Tap one for **+1** and **Done**: the same
  as those buttons on the deadline's Telegram message. With the computer off, the tap waits on your call line and
  counts when it's back; "Waiting for your computer" lists it meanwhile. Quizzes and exams have no buttons.
- **Reminders** and **open threads** (what you're in the middle of, with memory threads on).
- **Waiting** (how many things wait for you) and **Asked you**, where you answer them.

Your computer sends a new list within seconds of a change on it (a deadline done on Telegram, an alarm set) and looks
for changes every 5 minutes; the phone fetches it when it's told, when you open the app, and when it reconnects. Turn it off with `calls.today` (Dashboard → Settings → calls): the app then says "Turned off
on your computer" and no alarm is set on the phone from it.

**"Nothing here yet"** means your call line has no copy for this phone yet. The app gives the call line its key
after pairing, and the list follows within a minute or two while your computer is on. If that send failed (no
internet just then), opening the app tries again (0.6.1; on 0.6.0, swipe the app away and open it again).

**iPhone and browsers** don't get Today: it's sealed with a key only the Android app has.

## The being on the phone

Android, 0.8.10, with Systems and the Notes map turned on (`calls.views`, below): **Views** shows the dashboard's being
as four pages, **Brain**, **Heart**, **Senses** and **Memory**, picked in the row at the top. Each page is that one
organ, drawn by the dashboard's own code (the same anatomy, shaders, tints and glow), filling the screen, with none of
the dashboard's words over it. Views opens on the page you looked at last.

- **Turn and zoom:** drag anywhere with one finger to turn the organ; pinch to zoom in as close as a single note; two
  fingers move it. A flick keeps it turning a little (not with Android's Remove animations on).
- **Its parts are listed under it**, each with what it's doing now: the brain's thirteen regions (sparks lately,
  features on), the heart's five parts (its rate, AI requests running and answered, the call line, upkeep), the five
  senses (Voice's state, your phone's motion, this computer's processor and heat), your notes' neighbourhoods.
- **Tap a part**, in the list or on the drawing: it's focused in both, as a click on the dashboard does. The drawing
  zooms to it, lights it with its ring and turns the rest to glass; the list opens it in full: what it's doing now,
  its Brain parts and features with their switches, its settings (the yes-or-no ones as switches), a neighbourhood's
  best-linked notes, a note's first lines. Tap a feature's name for the feature itself. Tap the part again, or
  **Back**, for the whole organ; Back again leaves Views. On **Brain**, **Solid · Cutaway · X-ray**; on **Memory**,
  **Features** lists its features.
- **Switches work from the phone**, sealed to your computer over your call line and checked there as on the dashboard
  (below). Other settings are shown there; change them on the dashboard, or in the whole being (next).

**The whole being in one drawing**, as before 0.8.10's organ pages, with the dashboard's panels as a sheet: switch off
**Settings → Look → Organ pages in Views** (`app.viewsOrgans`). Views then has **Being**, **Brain**, **Systems** and
**Notes** at its top, and Being works like this:

- **Turn and zoom:** drag an organ with one finger to turn it (on empty space, the whole view turns); pinch to zoom;
  two fingers move the view. A flick keeps turning a little.
- **Tap a part to look into it**, as a click does on the dashboard: an organ (the mind, the heart, the senses, your
  notes), then a part of it (a brain region, a heart part, a sense, a neighbourhood of notes, a note, a feature's point
  of light). The camera flies to it, it lights up and the rest turns to glass. **Back** goes up one level (a part, its
  organ, the whole body) before it leaves Views. On the brain, **Solid · Cutaway · X-ray** under the title.
- **The panel** opens as a sheet from the bottom, half height: drag its handle up for the whole of it, down to close
  it, or tap ×. It has what the dashboard's panel has: the Brain's parts there with their switches, the features there
  (each with its own switch and settings), the AI requests running and answered, what runs next, the call line, the
  coil's bars (this computer's processor, memory, graphics, disks, battery), Voice's state, a neighbourhood's best
  linked notes, and a note's preview.
- **Switches and settings work from the phone**: a change goes to your computer sealed for it over your call line and
  is checked there exactly as on the dashboard; the switch moves when your computer says it's done, or the panel says
  why not. With your computer off it says "your computer is off: try again when it's on" (nothing waits to happen
  later). **Mute** (top right) mutes Voice on your computer; **Hints** shows or hides the hints, as H does there.
- **A note's preview** is asked for when you tap the note, sealed for this phone alone; the copy the being draws
  from has notes' titles and links, never what they say.
- It's live while it's open, like Systems (a fresh copy every few seconds); with your computer asleep it shows the
  last one, "as of" its time.

**"This phone can't draw the being"**: it needs WebGL 2 and Android System WebView 80 or newer; update the WebView (or
Chrome) from the Play Store. Views shows Systems instead. **"Your computer isn't sending the being"**: update Kurooto
there, or turn `calls.views_being` back on. **More → Brain console** (**Brain** with the whole being) shows the Brain
console when this app has it; until then it says it comes with this update.

## Systems and the Notes map on the phone

Android, 0.7.0, off until you turn it on: dashboard → **Phone** → **Show Systems and the Notes map in the Android app**
(the setting `calls.views`). Then the app's **Views** pane shows them: **Being**, **Brain**, **Systems** and **Notes** at its
top switch between them (with the organ pages: **More**, ⋮), and it opens on the one you looked at last.
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
- **Read-only:** nothing on these two screens changes anything (the being's panels can, above). Notes' contents never
  reach the phone.
- **When it's from:** "live" while your computer is sending Systems, else "as of 14:05". With your computer asleep
  the last copy shows with "your computer is asleep"; with no internet, "can't reach your call line".

**"Nothing here yet"**: the switch is off on your computer, the computer hasn't been on since you turned it on, or
your call line is older than 0.7.0 (it's updated at 05:10). **"This phone's web view is too old"**: update Android
System WebView (or Chrome) from the Play Store; the drawings need version 58 or newer.

**iPhone and browsers** don't get them: they're sealed with a key only the Android app has.

**The Brain** (0.8.10, with Brain on and `calls.views_brain`, on by default): the dashboard's Brain console on the phone, read-only:
what it's thinking, the decisions it made with their reasons and evidence, the timeline by part and day, its beliefs,
experiments, skills, plans, its model of you, the senses as counts, what it forgot, its stops and limits, and the journal's and
story's headings, with a search over all of it. Your computer sends it only while you have it open (every few seconds), sealed
like Systems; the last copy stays for when your computer is asleep. Nothing about money or health is in it. See
[Brain → The Brain console](mind.md#the-brain-console-dashboard-and-phone).

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
- **Ring on this phone too** (the switch on the Alarms pane's big card): turn the phone's copy off or on. Off, only the call rings.
- **Android 12 and newer** asks for exact alarms: **Settings → This phone**'s **Alarms at the exact time** and the Alarms
  pane's **Allow exact alarms** open the setting. On Android 13 and newer the app has it from the start. Without it the
  alarm is set as close as Android allows, which can be a few minutes late in deep sleep, and the Alarms pane says so.
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

**Android:** the app opens on **Chat** (0.8.10). Type as you would on Telegram: a question, "remind me
at 9 to call Dr Sam Okafor", a /command. It's handled exactly like a Telegram message: the same commands, plain-English
requests and, with Chat on, your AI. The answer comes back in the chat ("On it." first, then the AI's answer when it's
done; "Kurooto is working…" shows under the chat's name meanwhile), and as a notification when that chat isn't open.
Buttons under an answer work as on Telegram. Answers to what you wrote in the app come back to the app only, not to
Telegram.

**Chats (sessions).** Down the left edge is a rail of shapes, one per chat, each its own shape and colour, with a
number for what you haven't read. The top one is **Kurooto**: its own messages (reminders, results, what it found) land
there, and it can't be deleted. Every other chat is a separate conversation with your AI that remembers what was said
in it for as long as the chat lives, like an AI web app (Telegram's chat only keeps the last two hours). Tap a shape to
switch; **+** starts a new chat (it's named after its first words). Drag the rail to the right, or tap the chat you're
in, to pull open the list: names, last lines, the time, **Search** (chats and the messages in them), what's **waiting
for you**, **New chat**, and the chats under **Pinned**, **Recent** and **Archived**. Hold a chat there to rename, pin,
archive (on this phone) or delete it (**Undo** for a few seconds). The bar to the other screens sits at the rail's foot.
The **call button** at the top of a chat (and of the list) calls Kurooto, as Today's Call did.

**In a conversation:**

- **Reply:** swipe a message to the right, or hold it → **Reply**. The box shows what you're replying to; Kurooto gets
  that message as context, and your message shows it quoted (tap the quote to jump to it).
- **Hold a message** for **Copy**, **Share**, **Pin** (a bar at the top shows the newest pinned one; tap it to go
  there), **Edit** (your own, for 15 minutes: it's marked "edited", and Kurooto isn't asked again), **Delete** (on this
  phone, or everywhere for yours) and **Select** (several at once, to copy or share together).
- **Files:** **+** in the box opens Photo or video, Camera, File and Voice note. **Hold the mic** to record a voice note;
  slide left to cancel, let go to send. Files are up to 10 MB (a bigger one says so before anything is sent). Photos
  from Kurooto show in the chat (tap: full screen, Share, Save); other files show as a card with their name and size
  (tap: the app fetches it, opens it on the phone, and hands it to the app for that kind of file); voice notes and audio
  play in place. A file from Kurooto stays on your call line for a day.
- **Commands:** type `/` for the list of commands, with a line about each (it comes from your computer).
- Long answers show their start and **Show more**; bold, italic, code, lists and links show as Kurooto writes them.
- When you've scrolled up, a round button at the bottom right takes you back to the newest, with how many came since.

**Notifications:** one per chat, with Kurooto's unread messages in it. **Reply** writes back from the notification
(Android 7+), **Mark read** clears it, and a reminder's **Done** or **Snooze** are there as before. Tapping it opens
that chat.

**Chat settings on this phone** (Settings → Chat): message notifications, reply from the notification, swipe to reply,
formatting, folding long answers, loading photos by themselves, the command list, Enter sends, and haptics. Each is a
switch; all but Enter sends are on.

**iPhone (and any paired browser):** open Kurooto from the Home Screen and tap **Chat** (or open `<your call
line>/talk`). It works like the Android chat: buttons, **Reply**, and "Waiting for your computer" while it's off. A
notification for a chat message opens the chat. The page keeps its own copy of the chat in the browser and looks for
new messages every few seconds while it's open.

**Separate chats (0.8.10).** Besides the chat with Kurooto itself (always there, first in the list, where its
reminders and results land), you can start as many chats as you like, as in an AI chat app: each is its own
conversation with your AI and remembers everything said in it for as long as it exists (Kurooto's own chat and
Telegram keep the old short memory: the last few turns from the last two hours). A new chat is named after the first
words you write in it; set `calls.chat_titles` to `ai` (Dashboard → Settings → calls) to have your AI give it a short
title after its first answer. Rename, pin or delete a chat by long-pressing it; deleting it forgets what was said in
it (files you sent in it stay in your notes' inbox). `/new` in a chat starts just that chat over. Typing `/` lists
the commands, the same ones as Telegram's menu. While your AI works on something for a chat, it says
"Kurooto is working…".

**Replies, edits and pins.** Swipe a message right (or long-press → Reply) to reply to it: your AI gets the message
you replied to along with yours, so "why the second one?" makes sense. A reply to a reminder or a check-in still
answers it, as before. Long-press one of your messages to edit it (for 15 minutes; Kurooto isn't asked again) or delete
it everywhere; pin any message to keep it at the top of the chat.

**Files both ways.** Attach a photo, a file or a voice note to a message: it goes up to your computer first (into
your notes' inbox), then the message names it, so "what's in this?" works in the chat you sent it in. A voice note is
written out when Voice notes is on. Files from your computer show in the chat itself (a photo as a picture, other files
as a card you can open), see [Files from your computer](#files-from-your-computer).

**Turn these off:** Dashboard → Settings → calls: `chat_sessions` (one chat again; your chats come back when you turn
it on), `chat_files_inline`, `chat_edit`. Each stops at once and leaves the rest of the chat as it was.

**Kurooto's own messages in the chat.** With `notify.app_chat` on (Dashboard → Settings → notify), reminders,
results and other messages also show in the chat, besides Telegram. Without Telegram they always do. Questions and
approvals stay under **Waiting for you**, with their answer buttons.

**What you see under your message:**

| Under your message | Means |
|---|---|
| A clock | Sending: on its way to your call line. |
| One tick, "Waiting for your computer" | Your computer is off. It waits on your call line and goes to the computer when it's back; then this goes away and the answer comes. |
| Two ticks | Your computer has it. |
| Two coloured ticks | Kurooto has answered it. |
| "Not sent: tap to try again" | The phone was offline, or your call line refused it (the reason is in brackets). Tap the message to send it again. |

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

Where Telegram would get a document, the chat gets the file (0.8.10: the app shows it in place and opens it itself;
older app versions get a button that opens a link):

1. **Google Drive**, with [Drive upload](google.md) on: the file goes to the Kurooto folder in your Drive and **Open
   in Drive** opens it. It's deleted from your Drive after `drive_upload.temp_days` (7) days; move it out of the folder
   to keep it.
2. Otherwise **your call line** keeps a sealed copy for a day (files up to 10 MB). The app downloads and opens it
   itself; with `calls.chat_files_inline` off, or in an older app, **Open** shows it in the phone's browser, with
   **Save** (and the text itself for a text file). The key that opens it is made on your computer and is only in the
   link, never stored on its own; after a day the copy is deleted and the link says "This file is gone".
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
| **Talk to Kurooto** widget (1x1) | Home screen: long-press an empty spot → Widgets → Kurooto | One tap opens the app on Chat with the keyboard up, ready to type (use your keyboard's microphone to speak). |
| **Talk, and what's waiting** widget (2x1) | The same list | The same Talk button, and beside it the newest question or message waiting for you ("2 waiting: ..."), or "Nothing waiting for you". Tap the text to open the app. |
| **Quick note** shortcut (Android 7.1+) | Long-press Kurooto's app icon; drag it out to make its own icon | A small box: type a note, tap **Save to notes**. |
| **Quick note** tile (Android 7+) | Pull down Quick Settings → the pencil (edit) → drag **Quick note** in | The same box. On a locked phone it asks you to unlock first. |

**Where a quick note goes.** Into your notes' `inbox/` on your computer as `<date>-quick-note.md`, the same way a
shared file does: with Chat on, the AI files it where it belongs and tells you where; without Chat you get "Got
quick-note.md from your phone: saved to ...". With the computer off the note waits on your call line and goes to the
inbox when the computer is back ("Your computer is off: the note waits on your call line ..."). If it couldn't be sent
(no internet), it stays in the box, also after you close it, until you tap **Save to notes** again.

**What the 2x1 widget shows** is the newest of what's waiting for you in the app (Chat's "waiting for you" bar). It looks again every 30 minutes,
when a question arrives or is answered, and each time you open the app. It shows the message's text on your home
screen, like a notification would. Use the 1x1 widget if you'd rather not.

Android 6 has the widgets but no shortcut or tile (those came with Android 7). Removing a widget or the tile is the
undo: nothing else changes.

## When your computer is off

What you do on the phone while your computer sleeps isn't lost: chat messages, button taps, answers to questions
and shared files wait on your call line (the "phone outbox") and go to the computer when it's back, in the order you
sent them, each once.

- The chat shows **Waiting for your computer** under each one; Chat's "waiting for you" sheet lists what's waiting.
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
  phone can catch up while the computer is off. With separate chats (0.8.10) it keeps the last 50 of each chat, and
  the list of your chats (each one's name, its last line and when it changed) with the list of commands, until you
  delete the chat. "Kurooto is working…" goes only to a phone connected to your call line and isn't kept.
- The Views tab's being (0.8.10): changing a setting, turning a feature on or off and reading a note's text go from
  the Android app to your computer sealed, and only while the computer is on (nothing waits on the call line). The
  answer, a note's text included, comes back sealed for that phone alone, so your call line can't read it.
- Files you share and quick notes go from the phone through your call line to your computer.
- The 2x1 widget asks your call line what's waiting (as the app's "waiting for you" bar does); nothing else leaves the phone for
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
