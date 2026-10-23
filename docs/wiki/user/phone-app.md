# Your phone

Your phone is where Kurooto's calls ring, and a second place to answer its questions. Android gets a real app that
rings like a phone call; an iPhone gets a web app on its Home Screen. Both need [Phone calls](calls.md) set up first:
the app comes from your own call line.

You still talk to Kurooto mostly on Telegram; the phone app adds calls, the wake-up alarm, and questions with answer
buttons.

- [Pair a phone](#pair-a-phone)
- [Android](#android)
- [iPhone](#iphone)
- [Any browser](#any-browser)
- [What reaches the phone](#what-reaches-the-phone)
- [Answering questions on the phone](#answering-questions-on-the-phone)
- [Sharing files to your notes](#sharing-files-to-your-notes)
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
a **Call** button, the ringtone pickers (**Call ringtone** and **Wake-up alarm tone**; the alarm tone plays on the
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

## Sharing files to your notes

**Android:** in any app, Share → **Share to Kurooto** (one file or several). Each goes into your notes' `inbox/` (or
your files folder's, if you set one). With Chat on, the AI files it where it belongs and tells you where; without
Chat you get "Got <file> from your phone: saved to ...". Files can be up to 50 MB each. The computer has to be on.

## Managing paired phones

| Where | How |
|---|---|
| Telegram | `/phones` lists paired phones with their id, kind, whether notifications are on, and since when. `/unpair <id>` removes one (ids are 8 characters from `/phones`). |
| Dashboard → Phone | Your call line's address and whether it's connected; **Pair a phone**; **Ring my phone (test)** (only while connected); the list of phones with **Remove**. |
| Android app | **Unpair this phone** unpairs it on the phone; also remove it on your computer (Phone tab, or `/phones`). |

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
  Android gets them end-to-end encrypted through ntfy.sh; an iPhone gets an empty Web Push and then fetches what's
  waiting from your call line.
- Your call line keeps a copy of what's open (at most 40 items, each gone after a day or once it's dealt with) so the
  phone can list it while the computer is off.
- Files you share go from the phone through your call line to your computer.
- Call audio: see [Calls: what leaves your computer](calls.md#what-leaves-your-computer).

**Turn it off.** Unpair the phone (above). To stop questions reaching the phone but keep calls, take `"question"` and
`"approval"` out of `notify.app_kinds`.
