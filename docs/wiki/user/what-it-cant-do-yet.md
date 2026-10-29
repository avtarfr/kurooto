# What it can't do yet

Kurooto is young software, made by one person and tried by a few friends. This page says plainly what doesn't work,
or works only partly, so you know before you rely on it. Ideas that aren't built are in
[ROADMAP.md](../../ROADMAP.md); what people have asked for is in [REQUESTED.md](../../REQUESTED.md).

- [Tested on few computers](#tested-on-few-computers)
- [Your computer has to be on](#your-computer-has-to-be-on)
- [iPhone](#iphone)
- [Android](#android)
- [Phone calls and voice](#phone-calls-and-voice)
- [The AI](#the-ai)
- [Talking to it](#talking-to-it)
- [Planned, not built](#planned-not-built)
- [Telling us](#telling-us)

## Tested on few computers

Every release passes the automated tests on Windows, macOS and Linux, and a fresh install on a real computer before
friends get it. That's still only a handful of real machines. Laptops, antivirus programs, company-managed computers,
unusual Linux desktops and phones nobody has tried yet will turn up problems. If setup gets stuck, `kurooto doctor
--bundle` makes a zip (nothing is sent) that says where; see [Telling us](#telling-us).

## Your computer has to be on

Kurooto runs on your computer, not on a server. While the computer is off or asleep:

- it doesn't answer Telegram (messages wait about a day and are handled when it's back);
- AI requests, syncs, digests and check-ins wait;
- only what lives on your call line keeps working: calls you scheduled, the wake-up alarm, questions in the phone app,
  and, on Android, [reminders with the lid shut](calls.md) and the app's [Today](phone-app.md#today-on-the-phone) as
  the computer last sent it. Done or +1 tapped there waits for the computer.

One Telegram bot and one call line belong to one computer at a time: running Kurooto on two computers with the same bot
doesn't work. Move with [Profile sync](updates-and-backups.md) and turn the old one off.

## iPhone

The iPhone gets a web app on the Home Screen (iOS 16.4 or newer), not an app from the App Store. On iPhone:

- **calls are notifications you tap**: they can't ring like a phone call, ring on silent, or show on the lock screen as
  a call;
- **reminders with the lid shut don't reach an iPhone**, nor does the Android app's Today screen, and the wake-up alarm
  isn't set on the iPhone itself;
- the "Tell Kurooto" Shortcut is built by hand from a five-step recipe: Apple doesn't let a web page make a Shortcut
  file. It reads out Kurooto's first answer only ("On it." for longer jobs); the rest comes in the chat.

If you need calls that really ring, use an Android phone. See [Phone app](phone-app.md#iphone).

## Android

- The app isn't on the Play Store: it's installed from your own computer's pairing page, Android asks you to allow
  that, and Play Protect may warn first.
- The home screen widgets show what's waiting for you, not what's due (that's Today, in the app).
- Today, the phone's own copy of the wake-up alarm and Done / Snooze on notifications (0.6.0) are new and haven't been
  tried on many real phones yet. The phone's alarm knows only the alarms your computer last sent: one you set while the
  phone was offline reaches it when it's back online, and alarms less than 5 minutes apart ring on the phone as one.
- Today's list is read-only apart from Done and +1 on what's due (check-ins and quiz questions are cards under
  Waiting for you); the rest of the dashboard is still on the computer.
- Phone makers that close background apps hard can still delay rings; the app's checklist says what to change, but not
  every phone has been tried.
- Bedside mode shows the calls due in the next day and (0.9.0) today's reminders and deadlines from the Today list,
  not classes. On
  Android 10 and newer, "open by itself while charging" is a full-screen notification: with the phone in use it only
  shows a notice to tap. How dim "very dim" is depends on the phone's screen.

## Phone calls and voice

- Calls need a free Gemini API key and a free Cloudflare account, **even if another AI answers your messages**: the
  voice on calls is Gemini Live. Voice notes go through Gemini too.
- On Gemini's free tier, Google may use what you send to improve its products, and people may read it. In the EEA, the
  UK and Switzerland you need a paid key. See [Privacy](privacy.md).
- **Voice ID** knows whose voice it is, not whether it's live: a good recording or a cloned voice of you can pass (the
  AI's guarded actions still ask for your tap). It can't tell two voices apart inside one turn (overlapping speech is
  judged as a whole, usually "not sure"). A close relative may pass at normal strictness. See
  [Voice ID](voice.md#honest-limits).

## Face presence

- **It's not a lock, and can't be one with an ordinary webcam:** a photo or video of you on a phone will usually pass,
  and so can a lookalike. There's no liveness check (that needs a depth or infrared camera, or asking you to blink or
  turn your head); an RGB liveness model (MiniFASNet) exists, but its accuracy on ordinary webcams is unproven. A face
  match therefore never approves or unlocks anything.
- **Face and voice aren't combined:** Face presence and Voice ID each decide on their own; fusing them is a later step
  with its own switch.
- **Infrared (Windows Hello) cameras** aren't used: they're skipped, and a grey picture recognises you poorly.
- **The made-up impostor faces** that calibrate the threshold aren't shipped yet; until then it uses OpenCV's published
  threshold plus a margin.
- Tested with fakes only so far: no real camera or face has been tried yet, and the quality limits are first guesses.

## The AI

- The free AI options have small daily limits; heavy use runs out, and requests wait or go to your fallback AI.
- Local models (Ollama) are private and offline but much weaker, and need a good graphics card; without one, only
  the offline helper's quick decisions run here, and only if its speed test passes.
- Antigravity (agy) is Google's own program signed in as you; Google's answers differ on whether other tools may start
  it unattended, so there's some risk to that Google account. See [AI models](ai-brains.md).
- The AI can be wrong. Kurooto never sends anything outward (mail, messages) without your tap, but check what it
  writes into your notes.

## Talking to it

- Its pages, messages and commands are in English. Calls follow the languages Gemini Live speaks.
- Without Telegram, the phone app's chat can't carry files: they come as links (your Google Drive, or a sealed copy on
  your call line for a day).
- Telegram takes files up to 50 MB.
- It's for one person. The bot answers only you; there are no shared accounts or teams. Friends in one course share
  deadlines through a calendar one of them keeps, subscribed by its link ([shared class
  calendars](classes-and-timetable.md#shared-class-calendars)), not through Kurooto.
- It has no email address of its own: mail goes in through your own Gmail (+kurooto, or a label: [Email
  in](google.md#email-in)). A Cloudflare Email Worker for your own domain isn't built.
- No program may take a key for itself on Wayland, and Kurooto doesn't grab keys anywhere: the [Quick ask
  hotkey](talking-to-kurooto.md#quick-ask-a-hotkey) is set in your system's keyboard settings.

## Planned, not built

From [REQUESTED.md](../../REQUESTED.md) and [ROADMAP.md](../../ROADMAP.md), among others:

- the phone app's Today screen, a local alarm and notification buttons (planned for 0.6.0).

(A small local model for laptops without a graphics card, and quick answers while the internet is down, came in
0.6.0: [the offline helper](your-computer.md#the-offline-helper).)

## Telling us

Found something that doesn't work? Open an issue on GitHub (**Something doesn't work**): it asks for your Kurooto
version, your system and the zip from `kurooto doctor --bundle`. That zip is saved on your computer, has secrets, names
and addresses blanked out and never your messages or notes, and includes how long each setup step took, which shows
where setup stalls. Look inside it before you attach it.

Want something it doesn't do? Check [REQUESTED.md](../../REQUESTED.md) first, then open **An idea or a request**, or
tell your own Kurooto: "add to the requested list: …".
