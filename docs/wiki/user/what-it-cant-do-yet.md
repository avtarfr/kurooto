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
  and, on Android, [reminders with the lid shut](calls.md).

One Telegram bot and one call line belong to one computer at a time: running Kurooto on two computers with the same bot
doesn't work. Move with [Profile sync](updates-and-backups.md) and turn the old one off.

## iPhone

The iPhone gets a web app on the Home Screen (iOS 16.4 or newer), not an app from the App Store. On iPhone:

- **calls are notifications you tap**: they can't ring like a phone call, ring on silent, or show on the lock screen as
  a call;
- **reminders with the lid shut don't reach an iPhone**;
- there's no "Tell Kurooto" Shortcut yet.

If you need calls that really ring, use an Android phone. See [Phone app](phone-app.md#iphone).

## Android

- The app isn't on the Play Store: it's installed from your own computer's pairing page, Android asks you to allow
  that, and Play Protect may warn first.
- It looks plain (no Material design yet), and has no home screen widget or Today screen yet.
- Phone makers that close background apps hard can still delay rings; the app's checklist says what to change, but not
  every phone has been tried.

## Phone calls and voice

- Calls need a free Gemini API key and a free Cloudflare account, **even if another AI answers your messages**: the
  voice on calls is Gemini Live. Voice notes go through Gemini too.
- On Gemini's free tier, Google may use what you send to improve its products, and people may read it. In the EEA, the
  UK and Switzerland you need a paid key. See [Privacy](privacy.md).

## The AI

- The free AI options have small daily limits; heavy use runs out, and requests wait or go to your fallback AI.
- Local models (Ollama) are private and offline but much weaker, and need a good graphics card.
- Antigravity (agy) is Google's own program signed in as you; Google's answers differ on whether other tools may start
  it unattended, so there's some risk to that Google account. See [AI brains](ai-brains.md).
- The AI can be wrong. Kurooto never sends anything outward (mail, messages) without your tap, but check what it
  writes into your notes.

## Talking to it

- Its pages, messages and commands are in English. Calls follow the languages Gemini Live speaks.
- Without Telegram, the phone app's chat can't carry files: they come as links (your Google Drive, or a sealed copy on
  your call line for a day).
- Telegram takes files up to 50 MB.
- It's for one person. The bot answers only you; there are no shared accounts or teams.

## Planned, not built

From [REQUESTED.md](../../REQUESTED.md) and [ROADMAP.md](../../ROADMAP.md), among others:

- the phone app's Today screen, a local alarm and notification buttons (planned for 0.6.0);
- a small local model for laptops without a graphics card;
- answering quick things offline when the internet drops.

## Telling us

Found something that doesn't work? Open an issue on GitHub (**Something doesn't work**): it asks for your Kurooto
version, your system and the zip from `kurooto doctor --bundle`. That zip is saved on your computer, has secrets, names
and addresses blanked out and never your messages or notes, and includes how long each setup step took, which shows
where setup stalls. Look inside it before you attach it.

Want something it doesn't do? Check [REQUESTED.md](../../REQUESTED.md) first, then open **An idea or a request**, or
tell your own Kurooto: "add to the requested list: …".
