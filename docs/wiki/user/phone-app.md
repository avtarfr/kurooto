# Your phone

Your phone is where Kurooto's calls ring, and a second place to answer its questions. Android gets a real app that
rings like a phone call; an iPhone gets a web app on its Home Screen. Both need [Phone calls](calls.md) set up first:
the app comes from your own call line.

The phone app adds calls, the wake-up alarm, questions with answer buttons, and a chat with Kurooto that works like
Telegram. It can replace Telegram entirely: see [Using the app instead of Telegram](#using-the-app-instead-of-telegram).

- [Pair a phone](#pair-a-phone)
- [Android](#android)
- [iPhone](#iphone)
- [Any browser](#any-browser)
- [What reaches the phone](#what-reaches-the-phone)
- [Answering questions on the phone](#answering-questions-on-the-phone)
- [Chat with Kurooto in the app](#chat-with-kurooto-in-the-app)
- [Using the app instead of Telegram](#using-the-app-instead-of-telegram)
- [Files from your computer](#files-from-your-computer)
- [Sharing files to your notes](#sharing-files-to-your-notes)
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
| Battery: unrestricted (keeps listening) | Without it Android stops the app in the background and calls don't ring. |

   On Samsung, Xiaomi, Oppo, Vivo, OnePlus and Huawei phones, also take Kurooto off any "sleeping apps" or "deep
   sleep" list in Settings → Battery, or calls may not ring.
4. Test it: Dashboard → Phone → **Ring my phone (test)**.

**The app's screen** shows what it's paired with, the checklist, **Waiting for you** (open questions and approvals),
a **Call** button, **Chat with Kurooto**, what's **waiting for your computer** (things you sent while it was off),
the ringtone pickers (**Call ringtone** and **Wake-up alarm tone**; the alarm tone plays on the
alarm volume), and **Unpair this phone**. It starts listening again by itself after the phone restarts or the app
updates ("Listening for calls" stays as a quiet notification).

**A ringing call** shows **Answer**, **Decline** and **Later** (**Snooze** for the wake-up alarm). What each does is in
[Calls: Kurooto calling you](calls.md#kurooto-calling-you).

**Speech on the phone.** For calls that go turn by turn (when Google's live voice is down, or by choice with
`calls.voice_mode` = `phone`), the app uses Android's own speech recognizer and voice. On Android 13 and newer it
recognises speech on the phone itself when your language is downloaded for on-device recognition (in the phone's
language or speech settings; the place differs by phone). Then your voice never leaves the phone.

**Updates.** The app checks for a new version when you open it (at most every 2 minutes) and shows an **Update
available** button that opens the download. Install it over the old one; you stay paired. The pairing page always
offers the newest app.

**Without the app.** The pairing page also offers "Use this page as an app instead". It works, but rings less
reliably.

## iPhone

**What you get.** Kurooto as a web app on your Home Screen (iOS 16.4 or newer): calls arrive as notifications you tap
to answer, and questions and approvals show in **Waiting for you** with the same buttons and a box to type in.

**Install and pair.**
1. Open the pairing link in **Safari** (not another browser).
2. Tap the Share button → **Add to Home Screen** → **Add**.
3. Open **Kurooto from the Home Screen** (not from Safari). It finishes pairing there.
4. Tap **Turn on notifications** and allow them.

**What doesn't work on iPhone.** Calls can't ring like a phone call, ring on silent, or show on the lock screen as a
call: they're notifications you tap. Reminders with the lid shut don't reach an iPhone. If you need those, rely on
Telegram reminders or use an Android phone. The iPhone app updates itself.

**Speech.** Turn-by-turn calls use Safari's speech; Safari asks you to allow dictation. Answers are read aloud only
where the browser has a voice.

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
message's own buttons. Tap the notification for every option. The app's main screen lists what's **Waiting for you**.

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

## Chat with Kurooto in the app

**Android:** tap **Chat with Kurooto** on the app's main screen. Type as you would on Telegram: a question, "remind me
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

Telegram is optional (0.5.19). In setup, on the **Chat** step, pick **The Kurooto phone app instead**. It needs
[Phone calls](calls.md) (a free Gemini key and your call line on a free Cloudflare account; the Features step sets it
up), then you pair your phone right there or after **Finish setup**. Already set up with Telegram? Turn Telegram off
in Features: as long as Phone calls is on, everything moves to the app.

Without Telegram:

- Everything Kurooto says comes to the app's chat: reminders, check-ins, the morning message, what's due, your AI's
  answers, "after the call" notes, with their buttons (Snooze, Done, Why?, Less of this...). Questions and approvals
  come as notifications with answer buttons and under **Waiting for you**.
- `/pause`, `/resume`, `/status`, `/focus`, `/hold` and `/calls` work in the chat, and `/help` lists them.
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
Chat you get "Got <file> from your phone: saved to ...". Files can be up to 50 MB each. With the computer off, a file
up to 20 MB waits on your call line (below). Then ask about it in the chat: "summarise the PDF I just sent" works for
files shared in the last two hours (your AI is told their names and where they are).

## When your computer is off

What you do on the phone while your computer sleeps isn't lost: chat messages, button taps, answers to questions
and shared files wait on your call line (the "phone outbox") and go to the computer when it's back, in the order you
sent them, each once.

- The chat shows **Waiting for your computer** under each one; the app's main screen lists what's waiting.
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
| Dashboard → Phone | Your call line's address and whether it's connected; **Pair a phone**; **Ring my phone (test)** (only while connected); the list of phones with **Remove**. |
| Android app | **Unpair this phone** unpairs it on the phone; also remove it on your computer (the dashboard's Phone tab, or `/phones`). |

## A lost phone, or keys that got out

Run `kurooto rotate` on your computer. Use it when a paired phone is lost or stolen, or a backup zip with your keys
(`backups.secrets`) or a diagnostics file got out.

**What it replaces:** this computer's key to the call line, the key that signs call links (links sent before stop
working), the phone notification key and channel (Android) and the Web Push keys (iPhone).

**What happens:** it asks first (`--yes` skips that), redeploys your call line with the new keys (a minute or two;
same address), and the line forgets every paired phone, every call link it made and open pairing codes. If the deploy
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
  Android gets them through ntfy.sh (as your ntfy account with `kurooto ntfy-token`, else anonymously), encrypted
  with a key your phones, your computer and your call line hold (ntfy
  can't read them); an iPhone gets an empty Web Push and then fetches what's waiting from your call line.
- Your call line keeps a copy of what's open (at most 40 items, each gone after a day or once it's dealt with) so the
  phone can list it while the computer is off.
- The chat: what you type goes from the phone through your call line to your computer, sealed on Android with the key
  your phones, your computer and your call line hold, and over an encrypted connection from an iPhone. Kurooto's
  answers go back like questions do. Your call line keeps the chat's last 50 messages, each for at most 3 days, so a
  phone can catch up while the computer is off.
- Files you share go from the phone through your call line to your computer.
- Files from your computer for the chat (where Telegram would get a document): with Drive upload on, to your own Google
  Drive; otherwise a copy on your call line for a day, encrypted on your computer. The key is only in the link, which
  travels inside the chat message, so the copy is as private as the chat itself; ntfy never sees either.
- While your computer is off, what you send from the phone waits on your call line until the computer takes it (then
  it's deleted there): chat messages and answers as sent (sealed from Android), files as they are. A day's record of
  what went through (ids and short notes, no text you typed) stays so the phone can show it.
- Call audio: see [Calls: what leaves your computer](calls.md#what-leaves-your-computer).

**Turn it off.** Unpair the phone (above). To stop questions reaching the phone but keep calls, take `"question"` and
`"approval"` out of `notify.app_kinds`.
