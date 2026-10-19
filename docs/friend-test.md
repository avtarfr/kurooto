# Friend test: the guided session

For whoever runs a first-time install with a friend, sitting next to them or on a video call. The friend does
everything themselves; you only watch, note times and say where to click when they're stuck. Two sessions, about 30
and 45 minutes.

## Before the session
- Make sure the friend has: their laptop (charger in), their phone with Telegram installed and signed in, and their
  Google account password at hand.
- A notes file for you: a table with *step*, *start*, *end*, *stuck on*, *what they said*.
- Have `docs/MANUAL.md` open to point at sections.

## Session 1: install, AI, Telegram (target: a reply from their bot within 15 minutes)
| # | Step | Expect | Note |
|---|---|---|---|
| 1 | Paste the install line (Windows: PowerShell) | "Free space: … Fine", then the setup page opens | time from paste to page |
| 2 | Wizard: You | name, time zone pre-filled | |
| 3 | Wizard: Your computer | the hardware read correctly (e.g. a 4 GB graphics card → small-gpu) | did they understand the ★ |
| 4 | Wizard: AI → agy ★ → Install → sign in → Test | "Working: it answered in N s" | sign-in friction; how long Test took |
| 5 | Wizard: Features → Starter | storage total shown | |
| 6 | Wizard: Telegram (@BotFather → token → link → Start) | "Telegram is connected" | the most likely place to get stuck |
| 7 | Done → `/help` in Telegram | the command list | **stop the clock** |
| 8 | Try: "remind me in 2 minutes to stretch" | a reminder 2 minutes later | |
| 9 | Try: a question for the AI | "On it.", then an answer | |
| 10 | `kurooto doctor` | all ok | |

If anything blocks for more than 3 minutes: `kurooto doctor --bundle`, save the zip, move on.

## Session 2: calls and phone
| # | Step | Expect |
|---|---|---|
| 1 | Gemini key (aistudio.google.com/apikey) into the Features step | "Gemini key saved" |
| 2 | Features → Phone calls → Set up | packages, then Cloudflare sign-in in the browser, then "Your call line is live" |
| 3 | Pair the phone: dashboard → Phone → Pair → scan the QR | Android: download, install (unknown apps, Play Protect), Pair the app |
| 4 | The app's checklist → fix every ✗ (battery!) | all ✓ |
| 5 | Dashboard → Ring my phone | it rings like a call; answer; say hello |
| 6 | On the call: "what's due this week?", "remind me at 9 to call home" | it answers from Deadlines; a reminder appears |
| 7 | Hang up; "call me in 3 minutes about stretching" on Telegram | a call 3 minutes later |
| 8 | Optional: Morning alarm (/alarm in 5 minutes), Stay awake on charger | the alarm rings on the alarm volume |
| 9 | Optional: Google (Calendar link first; Classroom only if they want it) | /today shows their events |

## Afterwards
- Write down every place they hesitated, with the time it cost, and what would have helped.
- Collect any diagnostics zips (they send them; nothing is sent automatically).
- A week later: did the night-time update happen? (`kurooto --version`, the Telegram notice.) Any crashes or rollbacks?
