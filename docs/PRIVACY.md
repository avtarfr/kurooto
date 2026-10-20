# What leaves your computer

Kurooto runs on your computer, and every feature is off until you turn it on. This page lists, per feature, exactly
what goes where. **Nothing is ever sent to Kurooto's author** (no analytics, no crash reports, no "phone home"). The
only things Kurooto fetches from its own release page are updates, checked against a signature.

Everything below goes to services you chose, under your own accounts.

The screenshots in the README and on the website are of a demo with made-up data ("Sam") and stand-in services; none
of them shows anyone's real notes, chats or accounts. The pages' colours (`look.palette`) are a setting on this
computer only.

## Always (when the feature is on)

| Feature | What leaves | Where to |
|---|---|---|
| Telegram | your messages to the bot and its replies; files you send it | Telegram (to your own bot) |
| Questions and approvals | the question or approval, wherever Kurooto reaches you; open ones are also in the brief your call line keeps (see Phone calls) | Telegram (your own bot) and your paired phones; desktop notifications stay on this computer |
| Chat with your AI | what you ask; notes the AI reads to answer; what its tools return (a note's text, your reminders or deadlines); the short "In brief" part of your profile and your how-to-help-me note | the AI service you picked (Google for agy/Gemini, OpenAI for Codex, Anthropic for Claude Code, the service you entered for a custom one, or nothing for local models) |
| Files into notes | with Chat on, the files you send, for the AI to file them | the AI service you picked |
| Skills | what you send with a skill and the notes it reads; for `/newskill`, your description and the names of your tools and skills | the AI service you picked |
| Skills: revision packs | Tectonic (if you install it) downloads LaTeX packages; nothing of yours is sent | Tectonic's package server (public) |
| Sending files (`kurooto send`, the AI's send-file tool) | the file | Telegram (to your own bot) |
| Check-ins | nothing; with Check-ins by call and Chat on: what you said on the check-in call (after the evening debrief, both sides of it), for the AI to write your journal and study logs | the AI service you picked |
| Quiz | nothing; with Chat on: the question from your notes and your answer, for the AI to grade | the AI service you picked |
| Weekly summary | nothing; with the Sunday review call and Chat on: the call's transcript, to write the weekly review | the AI service you picked |
| After-class notes | nothing; with Chat on: your answer and the photos and files you sent with it, for the AI to write a study log | the AI service you picked |
| Notes brain (GBrain) | nothing on computers with a graphics card or Apple Silicon (the index is made locally); on others, note text, to make the index. The nightly upkeep and timelines add nothing: the upkeep's index step sends note text to Google only if your index already uses Gemini. Kurooto turns off GBrain's own update check, so GBrain makes no calls to its release page | Google (Gemini, your key), unless you chose keyword-only |
| Remember | your how-to-help-me note (`about-me/how-to-help-me.md`) goes along with every AI request, like the profile's "In brief" part; health, money and password details are refused, never stored | the AI service you picked |
| Nightly look back | what happened (events: what you answered, moved, skipped, and when), Kurooto's questions and your answers, today's call transcripts and journal (each can be left out), your how-to-help-me note and the values of the settings it may change; for a skill change you approved, that skill's text | the AI service you picked |
| Phone calls | call audio and what's said on calls; the call setup (your name, the assistant's name, which tools exist); for calls while the computer is off: a short brief (what's due, today's classes and check-ins, open questions, quiz questions, the alarm), the steps for check-in, wake-up and Sunday review calls with what they need (today's plan from your daily note, today's classes, study hours counted, the week's numbers), and your notes' titles, headings and first lines | Google (Gemini Live, your key); your own Cloudflare account (your call line) |
| Phone calls: ringing and messages | "a call is ringing" messages, and the questions, approvals and messages you choose for the phone (`notify.app_kinds`), end-to-end encrypted (only your paired phones can read them) | ntfy.sh (Android) or Apple/Google push services (web app; the push itself is empty) |
| Phone calls: what's waiting | the text of open questions, approvals and messages sent to your phones (at most 40; a message is gone after a day, a question or approval once it's answered or expires), so the iPhone app can list them | your own Cloudflare account (your call line) |
| Morning alarm | the alarm time; with Chat on, the AI reads your notes before the alarm to draft the day's plan, and the wake-up call's transcript to settle it | your call line; the AI service you picked |
| Voice notes | the recordings | Google (Gemini, your key) |
| Calendar | nothing leaves; Kurooto reads your calendar's private link. Event descriptions are read only for `#nocall` and `#focus` and aren't kept | (read from Google/Outlook/Apple) |
| Notes sync | your whole notes folder | your own private GitHub repository |
| Notes sync + Phone calls | read access to that repository, so calls can read notes while the computer is off | your call line (its secret store) |
| Backups | a zip of Kurooto's settings, data and state (AI requests and answers, check-ins, deadlines, your profile reports); your notes and your keys only if you turn them on. Not encrypted | only the folder you pick; if your computer syncs that folder to a cloud (Google Drive, OneDrive, iCloud, Dropbox), that cloud |
| Profile sync | your settings, passwords and keys, and saved state (deadlines, quiz progress, routines, observations, scheduled reminders and calls), all encrypted with your passphrase before they leave; in plain text only when it was saved, Kurooto's version, the kind of computer and a random id for it | your own private GitHub repository (the one Notes sync uses, or another you pick) |
| Google | Kurooto reads Classroom and, with Gmail drafts on, writes drafts in your Gmail; nothing is sent from your Gmail without your tap | Google, with your own client and sign-in |
| Classroom → notes | Classroom posts and the text of their attached files, to write the notes | the AI service you picked; read from Google with your own client |
| Mail digest | the text of the mail you chose for the digest (senders, domains and labels you named; on a school or work account, your own domain). Other mail, mail marked confidential (in its subject, anywhere in its text including standard confidentiality footers, or its labels) and your never-read list: nothing, they're only counted on your computer. Work or school mail may be covered by your institution's email policy; Kurooto never summarises mail marked confidential with the AI you picked | the AI service you picked; read from Gmail with your own client |
| Mail digest, confidential mail in local mode (opt-in, `mail_digest.confidential` = `local`) | nothing: a model on this computer (Ollama, 127.0.0.1) summarises it; the summary stays in Kurooto's data folder (`mail/confidential/`, readable only by your user account), out of your notes, Telegram (a count only), Profile sync and Backups (unless `backups.confidential_mail`) | stays on this computer |
| Email reply drafts | the draft reply, written into your Gmail Drafts; sent only when you tap Send | Google (your Gmail) |
| Agent plan calendar | the time blocks (title and time), in Kurooto's own calendar | Google (your Google Calendar) |
| Handwritten notes | the scans and photos | Google (Gemini, your key), unless a local vision model handles them |
| About you | the reports you add stay on this computer (Kurooto's data folder, not synced); building the profile sends them to the AI you picked, and its short "In brief" part goes along with every AI request | the AI service you picked |
| Research | your fields, keywords and searches (never your notes) | the sources you pick: arXiv, bioRxiv/medRxiv, PubMed, feeds (all public) |
| Research: `kurooto watch` | the command's name, exit code, duration and last lines (`--lines 0`: none) | Telegram (your own bot), like any message |
| Terminals | nothing by themselves (see [Your own code and terminals](#your-own-code-and-terminals)) | stays on your computer |
| Kurooto Terminal | nothing by itself; getting kitty or fish (only when you say yes) downloads them from their official GitHub releases. What you type to your AI's program goes to its service, as when you run it yourself | stays on your computer |
| Your add-ons | nothing by the feature itself; your add-ons' own code can do anything Kurooto can, so they send whatever they're written to send | wherever your add-ons send it |
| Local AI models, Reminders, Deadlines (with recurring quizzes, the not-interested list and exam mode), Subjects, Study tracker (and its daily note section), Quick notes and prompts, Stay awake on charger, Sync everything (each sync sends what its own feature sends), `kurooto top`, `kurooto runlog`, notes brain timelines and weekly checkup | nothing | stays on your computer |

## Free tiers and terms

**A free Gemini API key** (Google AI Studio's free tier):
- Google may use what you send and what it answers to improve its products, and human reviewers may read it.
- You must be 18 or older.
- In the EEA, the UK and Switzerland you need a paid key (billing turned on).
- Phone calls and voice notes always go through Gemini, whichever AI answers your messages.

If you don't want that, use a paid key: on paid tiers Google doesn't use what you send to improve its products. Or
keep those features off, or use local models where offered.

**Antigravity (agy):** Kurooto runs Google's official agy program on your computer, signed in as you, and never touches
its sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to
your Google account. For tools like Kurooto, Google recommends a Gemini API key.

Every other AI service you pick (Codex, Claude Code, a custom OpenAI-compatible one) works under its own terms and your
own account. Kurooto no longer offers FreeLLMAPI, which pools other providers' free tiers; one set up with an earlier
version keeps working and shows as "Another OpenAI-compatible service".

## Google: what each permission allows

Kurooto signs in to Google with your own "OAuth client" (made in your own Google Cloud project), so no one else's app
ever holds your Google access. Each Google feature asks for only the permission it needs, when you set it up:

| Feature | Google's permission | What Kurooto does with it |
|---|---|---|
| Google (Classroom) | see your Classroom courses, your coursework and announcements (read-only) | due dates into Deadlines, new posts to Telegram |
| Gmail drafts, Email reply drafts | manage drafts and send email | writes drafts; sends one only when you tap Send |
| Classroom → notes | see your Classroom course materials; see and download your Google Drive files (read-only) | reads materials, coursework and announcements, and opens only the Drive files attached to or linked from a post. Changes nothing |
| Mail digest | read your email (read-only) | reads only the mail you choose for the digest; the rest it counts by its sender, subject and labels, on your computer. Can't send, delete or mark anything |
| Agent plan calendar | make secondary calendars and manage their events | makes one calendar of its own, "Agent plan", and writes only there; it can't see or change your other calendars |

**Mail marked confidential is never read.** Work or school mail may be covered by your institution's email policy
(many forbid forwarding confidential messages, and institutional mail belongs to the institution). If a mail's
subject, its text (all of it, footers and quoted replies included) or a Gmail label's name says "confidential", "do
not forward", "restricted", "private and confidential", "privileged and confidential" or "proprietary and
confidential", or carries a standard confidentiality footer ("intended solely for the addressee", "if you are not the
intended recipient", "this e-mail ... is confidential / may be privileged"), Kurooto only counts it, even from a
sender or label you chose: it isn't sent to the AI, summarised, or answered with an AI draft. (To spot a marking in
the text, Kurooto reads it on your computer, then drops the mail in memory without keeping it.) The same goes for
everything on your never-read list (`/mail never`). This is on by default (`mail_digest.skip_confidential`); tune the
list in `mail_digest.confidential_words`.

**Optional local summaries.** With `mail_digest.confidential` set to `local` and Local AI models on, a model on this
computer (Ollama, 127.0.0.1) summarises that mail instead. Only the summary is kept, in Kurooto's data folder
(`mail/confidential/<date>.md`, readable only by your user account); the dashboard shows it on this computer. It
isn't in your notes, on Telegram (which gets a count only), in Profile sync, or in Backups unless you turn on
`backups.confidential_mail`. Dates found there are offered to you (titles and dates only) and never added by
themselves. No AI reply drafts for it, ever.

**Copies kept on your computer:** downloaded Classroom files (Kurooto's data folder, `classroom/`); the text of the
mail you chose, only until the digest is written (state folder, `mail-digest/`); and the sender, subject and a short
excerpt of digested mail for 30 days, so a reply draft can answer it.

To withdraw a permission: your Google account → Security → Third-party access → your project.

## The AI's tools

Tools add no new destination: what a tool returns to the AI (a note's text, your reminders or deadlines) goes to the
AI service you picked, as the notes it reads always did. AI requests can't answer your questions or approvals: those
tools exist only on calls, with you.

- `kurooto mcp` (how agent programs reach the tools) talks only to Kurooto on `127.0.0.1`, with a key that is good for
  the tools and nothing else; it changes at every start and is kept in an owner-only file in Kurooto's state folder
  (`tools-access.json`).
- What the AI may read on this computer (Kurooto's own tools and agy alike): your notes, Documents, Downloads and
  Screenshots folders, and Kurooto's copies of Classroom and mail; hidden files (like `.git`) are left out. What it
  reads goes to the AI service you picked. It may write only in your notes folder, your Classroom course files and,
  with add-ons on, your add-ons' `skills/`; Documents and Downloads stay read-only. Before it changes existing text
  (`edit_note`), the previous version is kept in Kurooto's state folder (`note-history/`, the last 20 per file); Notes
  sync's history has every version too.
- The AI may read public web pages (GET only). It never fetches this computer or your local network, so a page or a
  note can't steer it into your router or other programs here.
- agy's settings file is changed only by adding (after a backup; your own rules stay): `mcp(kurooto/*)`, `read_file`
  and `write_file` for the folders above, `read_url(*)`, harmless commands (cat, find, git, grep, latexmk, ls, rg and
  similar; never `kurooto` or `sed`), and non-workspace file access if you hadn't set it. Kurooto asks before adding
  anything (Approve / Deny), except when you test agy on the setup page, which says what it allows.
- A long agy request is written, for the length of the run, to `.kurooto/requests/` inside your notes folder (a hidden
  folder Notes sync ignores, so it's never uploaded), then deleted.

## Questions and approvals

Questions are delivered on the channels you set up (Telegram, the phone app, the desktop) and stored on this computer
in the state folder (`ask/<id>.json`), deleted 30 days after they're answered or expire (`ask.keep_days`). The events
log records when and where you answered, not what.

## Your own code and terminals

- **Your add-ons** run your own Python code inside Kurooto, with its access to this computer. Only use add-ons you
  wrote or trust; `overlay.code` off keeps their skills, prompts and settings and skips the code.
- **Terminals** in the dashboard are real terminals on this computer: anyone who can open your dashboard can type into
  them, so only turn them on if you're the only person who uses this computer. The dashboard only answers this
  computer, needs a key only its own page gets, refuses other websites, and on Linux checks that every request comes
  from your own user account. What you type into the AI program's terminal goes to that program's service, as when
  you run it yourself.

## Secrets

Your bot token, keys, tokens and links are kept in your system's keychain (Windows Credential Manager, macOS Keychain,
the Secret Service on Linux), or, where there is none, in a file only your user can read. They're never written to
logs. `kurooto doctor --bundle` blanks them out (and names, addresses and folders) before saving anything.

- **Backups:** with `backups.secrets` on, your keys are copied into each backup zip (`secrets.json`), in plain text;
  anyone who gets the zip can use them. Off by default.
- **Profile sync:** your keys also go to your repository, encrypted with your passphrase (AES-GCM, with a key from
  scrypt). The passphrase is never stored; this computer keeps the profile's data key in its keychain, like your other
  keys, so it can save on its own. Never in the profile: this computer's dashboard key, and the reports you added in
  About you.

## Your phone

The Android app keeps its pairing (the call line's address, its device key, the ring messages' key) in its private
storage. Nothing personal is built into the app. The iPhone web app keeps its device key in Safari's storage for the
Home Screen app. Unpair a phone with `/phones` → `/unpair`, or on the dashboard's Phone tab.

Answers from the Android app are sealed with the same key as the ring messages, so the call line passes them to your
computer without being able to read them; the iPhone app's answers travel over HTTPS with its device key. Each answer
can be used once (it carries a random number and the time it was sent).

## Removing it all

`kurooto uninstall` removes Kurooto's settings and data from your computer (your notes folder is kept). Your call
line, Google client, notes repository and the `kurooto-profile` branch are on your own accounts, and backup zips are
in the folder you picked: delete them there (see the manual's Uninstall).
