# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Three audiences, in this order of priority, and the landing page lets each choose itself:

1. **Research students** (the primary one): university students who juggle classes, problem sets, exams, a
   research project with a supervisor, books and notes, often on irregular hours. They want one assistant that keeps
   all of it and reaches them by phone.
2. **People organising their lives**: anyone with work shifts, commitments, deadlines and a notes folder, who wants
   reminders, check-ins and a plan for the day without handing their life to a cloud service.
3. **Tinkerers and developers**: people who like self-hosted tools, pick their own AI (agy, Claude Code, a Gemini key,
   local models), read the developer wiki and want to extend it (add-ons, skills).

Visitors arrive from a link a friend sent, GitHub, or the author's own site. Most have never installed anything from a
terminal line; tinkerers have.

## Product Purpose

Kurooto is a personal assistant that runs on the user's own computer (Windows, macOS, Linux; no admin rights, no
cost to run), talks to them on Telegram and in its own phone app, calls their phone by voice, and uses the AI they
choose. Every feature is opt-in. It learns how the user's days actually go (the hours they answer, what they say,
what they ignore) and fits itself to them, with a line saying what it did and an Undo for every change.

Success for the landing page: a visitor understands how Kurooto works and fits a day, installs the beta on their own
PC willing to experiment and report what breaks, and stars the GitHub repository if they like it.

## Positioning

It lives on the user's own computer and their own free accounts (a call line on their own Cloudflare account, their
own Telegram bot, their own notes folder), never on a company's server; it learns from the user's own days with
plain rules first and shows its working (a receipt under every AI answer, an Undo under every change); and it calls
the user's phone like a person would, including a wake-up call that plans the day.

## Operating Context

Installed with one pasted line per OS; a setup page in the browser walks through the rest (AI brain, Telegram bot,
features, phone pairing by QR). Lives as a background daemon with a dashboard at 127.0.0.1:8770, a terminal view
(`kurooto top`), Telegram, the Android app (Android 6+), and an iPhone web app. Updates itself at night from signed
releases on a stable or beta channel and rolls back if an update crashes.

## Capabilities and Constraints

- Beta channel: every version the day it's signed. Stable: older and steadier. The landing page leads with the beta.
- The beta has been used daily on one Linux laptop and tested automatically on Windows, macOS and Linux CI runners;
  it has not been tried on many real PCs. The page must say so plainly.
- Needs a Telegram account; a Google account or a free Gemini key for calls and the default AI; a free Cloudflare
  account for phone calls.
- Features: Telegram assistant in plain English, reminders, check-ins, deadlines and Start-by dates, subjects and
  timetable, missed-class catch-up, reschedule my day, quizzes and link recall cards, revision plan, books read into a
  concept graph of notes, notes search, Dreaming (one morning message about what the night did), voice calls and a
  wake-up alarm, phone app with chat, calendar and Google Classroom, research digests, run receipts, /fixme, keep or
  drop, forgetting when the user chooses, an egress ledger.
- Every feature off until turned on; each says what it needs and what leaves the computer.

## Brand Commitments

- Name: Kurooto (玄, kuro: the dark, nearly black green). The colour scheme is fixed: near-black greens (#0B0F0A,
  #10150E, #151B12), moss accent (#6B8A42, text #A6C07A), warm off-white text (#F2EEE8); light theme #F4F2EC ground
  with #3F5626 accent. Everything else about the look is open.
- Voice: plain, short, honest about limits; no hype, no emojis. Never describe the product as mimicking a human; show
  the behaviour instead.
- Apache-2.0; author credit in the footer; links to the GitHub repository and the author's site avtarfr.github.io.

## Evidence on Hand

- Real screenshots with made-up demo data ("Sam", a student) in docs/media (installer/media when building): dashboard
  (dark, system colours), kurooto top, dashboard terminal, setup steps (welcome, AI, about you, features, your
  computer, phone), morning page (dark/light), chat examples, phone call page, phone inbox, phone pairing, research
  tab, and a looping video of the dashboard's Systems view (systems-loop.mp4, poster).
- Real numbers: 1571 automated tests in the latest suite; three OSes; Android 6 and newer.
- No testimonials, users, press or download counts exist; none may be invented.

## Product Principles

1. The user's own computer and accounts, never a middleman.
2. Learn from how the user's days really go; say what changed and offer Undo.
3. Quiet by default: every feature opt-in, a daily limit on messages it starts.
4. Show the working: receipts, /fixme, an honest beta note.
5. Invite experiment: the beta is for people willing to try things and report what breaks.
