# What leaves your computer

Kurooto runs on your computer, and every feature is off until you turn it on. This page lists, per feature, exactly
what goes where. **Nothing is ever sent to Kurooto's author** (no analytics, no crash reports, no "phone home"). The
only things Kurooto fetches from its own release page are updates and the list of withdrawn versions, both checked
against a signature.

Everything below goes to services you chose, under your own accounts.

The screenshots in the README and on the website are of a demo with made-up data ("Sam") and stand-in services; none
of them shows anyone's real notes, chats or accounts. The pages' colours (`look.palette`) are a setting on this
computer only.

## Always (when the feature is on)

| Feature | What leaves | Where to |
|---|---|---|
| Telegram | your messages to the bot and its replies; files you send it | Telegram (to your own bot) |
| Questions and approvals | the question or approval, wherever Kurooto reaches you; open ones are also in the brief your call line keeps (see Phone calls) | Telegram (your own bot) and your paired phones; desktop notifications stay on this computer |
| Chat with your AI | what you ask; notes the AI reads to answer; what its tools return (a note's text, your reminders or deadlines); the short "In brief" part of your profile and your how-to-help-me note | the AI service you picked (Google for agy/Gemini, Anthropic for Claude Code, the service you entered for a custom one, or nothing for local models) |
| Files into notes | with Chat on, the files you send, for the AI to file them | the AI service you picked |
| Setup page: Try it now | what you type in the box that isn't an instant request (a reminder, a command), like a Chat message; nothing goes to Telegram or your phone | the AI service you picked |
| Skills | what you send with a skill and the notes it reads; for `/newskill`, your description and the names of your tools and skills | the AI service you picked |
| Hint ladder | the problem (its photo or text), the course's AI-policy line and the notes the AI reads to find the lecture note; with "no AI help" in that line, nothing | the AI service you picked |
| Skills: revision packs | Tectonic (if you install it) downloads LaTeX packages; nothing of yours is sent | Tectonic's package server (public) |
| Study packs (`/studypack`) | nothing to your AI: Kurooto collects the files on this computer and fills in a prompt. With a topic, it finds each book's pages on it in the text Books extracted, on this computer. The zip and the prompt come to your own Telegram; you decide which other AI to give them to | Telegram (your own bot); with Drive upload on, a pack over 50 MB goes to your own Drive, deleted after `drive_upload.temp_days` |
| Skills: packs before exams (`skills.auto_pack`) | the same as `/pack`: the subject's notes the AI reads to write the pack; with `ask` (the default) only after you tap Build it | the AI service you picked |
| Sending files (`kurooto send`, the AI's send-file tool) | the file | Telegram (to your own bot) |
| Class packs | a pack you make: the section's courses, timetable, term dates, quizzes and exams, never names, keys, notes or skills; you decide whom to forward it to. Importing one sends nothing | Telegram (to your own bot) |
| Check-ins | nothing; with Check-ins by call and Chat on: what you said on the check-in call (after the evening debrief, both sides of it), for the AI to write your journal and study logs | the AI service you picked |
| Quiz | nothing; with Chat on: the question from your notes and your answer, for the AI to grade | the AI service you picked |
| Weekly summary | nothing; with the Sunday review call and Chat on: the call's transcript, to write the weekly review | the AI service you picked |
| After-class notes | nothing; with Chat on: your answer and the photos and files you sent with it, for the AI to write a study log | the AI service you picked |
| Notes brain (GBrain) | nothing on computers with a graphics card or Apple Silicon (the index is made locally); on others, note text, to make the index. The nightly upkeep and timelines add nothing: the upkeep's index step sends note text to Google only if your index already uses Gemini. Kurooto turns off GBrain's own update check, so GBrain makes no calls to its release page | Google (Gemini, your key), unless you chose keyword-only |
| Notes brain: your own GBrain (`gbrain.managed` = `false`) | nothing by Kurooto: it runs your gbrain program, which uses the embedding and AI models *your* brain is set up with (also for the upkeep steps you add, such as contradictions). With `gbrain.agy_mcp` and your approval, agy can use your brain's tools, so what it reads there goes to Google like the rest of agy's work | whatever your own brain is set up to use; Google (agy) with `gbrain.agy_mcp` |
| Remember | your how-to-help-me note (`about-me/how-to-help-me.md`) goes along with every AI request, like the profile's "In brief" part; health, money and password details are refused, never stored | the AI service you picked |
| Nightly look back | what happened (events: what you answered, moved, skipped, and when), Kurooto's questions and your answers, today's call transcripts and journal (each can be left out), your how-to-help-me note and the values of the settings it may change; for a skill change you approved, that skill's text | the AI service you picked |
| Learns from its own work (optional) | its search index of past requests, calls and chats is built and kept on this computer; when the AI searches it, the passages it finds go to that AI with the request; to learn a skill, the finished request, its answer and the steps it took; to learn a lesson, your correction and the skill; with the nightly look back, the day's requests, to pick out facts you stated (never health, money, passwords or other people's details) | the AI that takes second looks (`learning.brain`), else the AI service you picked |
| Phone calls | call audio and what's said on calls; the call setup (your name, the assistant's name, which tools exist); for calls while the computer is off: a short brief (what's due, today's classes and check-ins, open questions, quiz questions, the alarm), the steps for check-in, wake-up and Sunday review calls with what they need (today's plan from your daily note, today's classes, study hours counted, the week's numbers), and your notes' titles, headings and first lines | Google (Gemini Live, your key); your own Cloudflare account (your call line) |
| Phone calls: the look back after every call (`calls.review`, on; off stops it) | the call's transcript and its tool log (each tool it used, with what it was given and returned), for an AI request that does what slipped through and writes lessons for later calls; the lessons then go with every call's setup | the AI service you picked (or `calls.review_brain`); the lessons to your call line and Google (Gemini Live), like the rest of the call setup |
| Phone calls: transcripts while the computer is off | the call's transcript, held by your call line until your computer is back (at most the last 200 waiting items), then passed to it | your own Cloudflare account (your call line) |
| Phone calls: turn by turn (`calls.voice_mode` `phone`, or when Gemini Live is down) | your speech, to your phone's speech recognizer: on Android 13+ with your language downloaded it's recognised on the phone and stays there; otherwise your phone's speech service (usually Google's; Apple's on iPhone; Chrome sends it to Google). The text of each turn, the call's instructions and its tools' answers | the speech service your phone uses; Google (Gemini, your key) from your computer or your call line, or the model on your computer (`calls.turn_brain` = `local`): never an agent program |
| Phone calls: text on Telegram (no speech recognition or microphone) | the call's conversation, as messages | Telegram (your own bot) and the AI service you picked, like your other messages |
| Phone calls: how Live failed | which Live model failed, Google's error code, and what the call did instead, counted for `kurooto doctor` | your call line passes it to your computer; it stays there |
| Phone calls: ringing and messages | "a call is ringing" messages, and the questions, approvals and messages you choose for the phone (`notify.app_kinds`), encrypted with a key only your paired Android phones, your computer and your call line hold (ntfy can't read them) | ntfy.sh (Android; with `kurooto ntfy-token`, as your ntfy account: the token is kept on this computer and your call line) or Apple/Google push services (web app; the push itself is empty) |
| Phone calls: what's waiting | the text of open questions, approvals and messages sent to your phones (at most 40; a message is gone after a day, a question or approval once it's answered or expires), so the iPhone app can list them | your own Cloudflare account (your call line) |
| Going offline and coming back (on by default) | the "going offline", "back online" and "network was down" messages, and messages kept while the network was down | Telegram (your own bot); with Phone calls, the phone app through your call line |
| Going offline + Phone calls | your night and focus hours for the next day and the message's wording, so your call line can say "offline since 22:10" while this computer can't; only after you approve (asked once): your Telegram bot's token and your chat id, kept in your call line's storage and deleted there when you set `notify.presence.line_telegram` to `false` or turn the feature off | your own Cloudflare account (your call line), which then sends to Telegram or your phones |
| Morning alarm | the alarm time; with Chat on, the AI reads your notes before the alarm to draft the day's plan, and the wake-up call's transcript to settle it | your call line; the AI service you picked |
| Exam season | nothing; with Phone calls on, the leave-by alarm (its time, the exam and what you said about the venue), so your call line can ring it while this computer sleeps, and the exam in the brief of calls that day and the day before | your own Cloudflare account (your call line); Google (Gemini Live) on the call |
| Reminders with the lid shut | for the next day: each reminder and a morning line (the day's first class and what's due), as a time, an id and, for each paired Android phone, a copy sealed with a key only that phone has (your call line can't read them); each phone's public key. When this computer is asleep at an item's time, its sealed copy goes out through ntfy. Your Telegram bot's token isn't used | your own Cloudflare account (your call line); ntfy.sh, still sealed |
| Voice notes | the recordings | Google (Gemini, your key) |
| Calendar | nothing leaves; Kurooto reads your calendar's private link (or Google Calendar). Event descriptions are read only for `#nocall`, `#focus` and `#private` and aren't kept. Events marked private are kept and told only as "Busy (private)": their title and place go nowhere, not even to your AI | (read from Google/Outlook/Apple) |
| Notes sync | your whole notes folder; conflict copies (when a note changed here and elsewhere at once) are ordinary notes and go too | your own private GitHub repository |
| Notes sync + Phone calls | read access to that repository, so calls can read notes while the computer is off | your call line (its secret store) |
| Backups | a zip of Kurooto's settings, data and state (AI requests and answers, check-ins, deadlines, your profile reports); your notes and your keys only if you turn them on. Not encrypted | only the folder you pick; if your computer syncs that folder to a cloud (Google Drive, OneDrive, iCloud, Dropbox), that cloud |
| Profile sync | your settings, passwords and keys, and saved state (deadlines, quiz progress, routines, observations, scheduled reminders and calls), all encrypted with your passphrase before they leave; in plain text only when it was saved, Kurooto's version, the kind of computer and a random id for it | your own private GitHub repository (the one Notes sync uses, or another you pick) |
| Google | Kurooto reads Classroom and, with Gmail drafts on, writes drafts in your Gmail; nothing is sent from your Gmail without your tap | Google, with your own client and sign-in |
| Classroom → notes | Classroom posts and the text of their attached files, to write the notes | the AI service you picked; read from Google with your own client |
| Mail digest | the text of the mail you chose for the digest (senders, domains and labels you named; on a school or work account, your own domain; with a Gmail search set in `mail_digest.query`, the mail it matches, where personal mail is only counted by the AI, never summarised). Other mail, mail marked confidential (in its subject, anywhere in its text including standard confidentiality footers, or its labels) and your never-read list: nothing, they're only counted on your computer. Work or school mail may be covered by your institution's email policy; Kurooto never summarises mail marked confidential with the AI you picked | the AI service you picked; read from Gmail with your own client |
| Mail digest, confidential mail in local mode (opt-in, `mail_digest.confidential` = `local`) | nothing: a model on this computer (Ollama, 127.0.0.1) summarises it; the summary stays in Kurooto's data folder (`mail/confidential/`, readable only by your user account), out of your notes, Telegram (a count only), Profile sync and Backups (unless `backups.confidential_mail`) | stays on this computer |
| Email reply drafts | the draft reply, written into your Gmail Drafts; sent only when you tap Send | Google (your Gmail) |
| Agent plan calendar | the time blocks (title and time), in Kurooto's own calendar | Google (your Google Calendar) |
| Dreaming | nothing: it reads Kurooto's own log and your notes | stays on this computer |
| Handwritten notes | nothing when a model on this computer reads them (Local models: the vision model on 12 GB graphics cards, the helper model on 8 GB ones, or `handwritten.local_model`); otherwise the scans and photos, unless you turn that off (`handwritten.cloud` = `false`: they wait for a model here). Linking a written-out note to your other notes (`handwritten.link`, on): the note's text, the titles and opening lines of the notes it may relate to, your subjects' names and the opening of their course pages, and when it was written | Google (Gemini, your key) only when no model here reads them; the linking to the AI service you picked (the concept graph's second-look AI when that's on) |
| Books and PDFs | nothing while reading: the PDF's text, Tesseract and a local vision model all work on this computer, and the books, their text and the index notes stay here (the books outside your notes). Only with `books.gemini` on (off by default; books may be copyrighted): pictures of the pages nothing on this computer could read. When the AI writes your notes: excerpts of your books (the pages on the topic), Classroom materials and your notes, in the mix you chose (`course_sources`) | Google (Gemini, your key) only with `books.gemini`; the excerpts to the AI service you picked |
| Books and PDFs: setting up | installing Tesseract (`/books setup`) downloads it from winget (Windows) or Homebrew (macOS); on Linux it only opens the install page. Nothing of yours is sent | Microsoft's winget sources or Homebrew |
| Google Calendar | nothing leaves; Kurooto reads your own calendars (read-only). Other people's calendars shared with you are left out | (read from Google) |
| Mail digest by email | each mail digest's text, sent from your Gmail to your own address only (never another recipient); not sent if it mentions confidential material | Google (your Gmail, to yourself) |
| Drive upload | the files you send yourself, into a Kurooto folder in your Drive; nothing is shared | Google (your Drive) |
| About you | the reports you add stay on this computer (Kurooto's data folder, not synced); building the profile sends them to the AI you picked, and its short "In brief" part goes along with every AI request | the AI service you picked |
| Research | your fields, keywords and searches, arXiv searches you wrote in arXiv's own words included (never your notes). Runs kept in your repositories (`runs/index.csv`) and `research.save_note` stay on your computer | the sources you pick: arXiv, bioRxiv/medRxiv, PubMed, feeds (all public) |
| Research: "Remind me tomorrow" by call (Phone calls on) | the project's name, as the call's reason | your call line (Cloudflare, Gemini Live), like any call |
| Research: `kurooto watch` | the command's name, exit code, duration and last lines (`--lines 0`: none) | Telegram (your own bot), like any message |
| Terminals | nothing by themselves (see [Your own code and terminals](#your-own-code-and-terminals)) | stays on your computer |
| Kurooto Terminal | nothing by itself; getting kitty or fish (only when you say yes) downloads them from their official GitHub releases. What you type to your AI's program goes to its service, as when you run it yourself | stays on your computer |
| Your add-ons | nothing by the feature itself; your add-ons' own code can do anything Kurooto can, so they send whatever they're written to send | wherever your add-ons send it |
| Study tracker: telling you're away | nothing: the idle check reads input interrupt counts (`/proc/interrupts`), the cursor position (Hyprland) and whether a screen locker runs; never what you type, and none of it is kept | stays on your computer |
| Calm by default (on by default) | nothing: what's recorded about each message that came by itself (when, why, the setting, what it was about, its first 300 characters (only `privacy.keep_days`, 30), whether you tapped or answered it) stays in `calm.db` in Kurooto's state folder for 45 days, and a message waiting for the evening bundle is kept in full until it's sent. It goes into Backups like the rest of the state folder, never into Profile sync; `notify.calm.on` = `false` records nothing | stays on your computer |
| Wrong button and test cases | nothing: what you typed, what Kurooto did and a snapshot of the settings that decided it stay in Kurooto's state folder (`cases/`), never in Backups, Profile sync or `kurooto doctor --bundle`; cases you didn't review are forgotten after `privacy.keep_days` (30). The monthly look back shows phrasings back to you on Telegram, where they came from. `kurooto cases export` writes a file on this computer; sharing it is up to you | stays on your computer |
| Local AI models, Reminders, Deadlines (with recurring quizzes, the not-interested list, exam mode and start-by dates), Subjects, Doubt queue, First-week quests, Study tracker (and its daily note section), Quick notes and prompts, Stay awake on charger, Sync everything (each sync sends what its own feature sends), `kurooto top`, `kurooto runlog`, notes brain timelines and weekly checkup | nothing | stays on your computer |

## Where requests go

Every request Kurooto makes on the internet goes through one place that counts it (the host, the feature, how many
requests and bytes, per day) and checks it against this list. `/egress` shows the last 7 days. Only counts are kept
(`egress.json` in Kurooto's state folder, 30 days), never what was sent.

| Host | What reaches it |
|---|---|
| `api.telegram.org` | Telegram |
| `generativelanguage.googleapis.com` | Gemini, with your key (chat, voice notes, handwritten notes, books, the notes index, checking the key) |
| `oauth2.googleapis.com` | Google sign-in, and taking it back (`kurooto uninstall --revoke`) |
| `classroom.googleapis.com` | Google Classroom |
| `gmail.googleapis.com` | Gmail (mail digest, drafts) |
| `www.googleapis.com` | Google Drive and Google Calendar |
| `api.github.com` | Notes sync and Profile sync (checking your repository) |
| `github.com` | downloading Git (Windows), Tectonic, kitty and fish |
| `api.cloudflare.com` | Phone calls: setting up your call line |
| `.workers.dev` | Phone calls: your call line (any address under it) |
| `ntfy.sh` | Phone calls: ringing your phone |
| `nodejs.org` | Phone calls: downloading Node.js to set up the call line |
| `ollama.com` | Local AI models: downloading Ollama |
| `registry.ollama.ai` | Local AI models: how big a model is, before you download it |
| `export.arxiv.org` | Research (arXiv) |
| `api.biorxiv.org` | Research (bioRxiv, medRxiv) |
| `eutils.ncbi.nlm.nih.gov` | Research (PubMed) |
| `avtarfr.github.io` | Updates and the list of withdrawn versions |

**Addresses you gave are yours** and always allowed: your calendar's private link, the feeds you added to Research,
the AI service you entered (a custom OpenAI-compatible one), your call line and your own ntfy server, and the public
pages your AI reads for a request (its web reading tool). This computer (`127.0.0.1`) is always allowed and never
counted: nothing leaves.

**Programs that go online by themselves** are counted as "handed to" them, with the feature; Kurooto doesn't look
into what they send: git (Notes sync and Profile sync), npm and wrangler (setting up your call line), agy and Claude
Code (AI requests), Ollama (downloading a model), GBrain (making the index with Gemini, or your own brain's models),
Tectonic (LaTeX packages), and installers (winget, Homebrew, Flatpak, npm, Bun, a vendor's install script). Where they
send it is in the tables above.

**Enforcing it** (`privacy.egress`): `record` (the default) counts everything and marks a host that isn't on the list
"not on the list" without stopping it, because an add-on or an address changed in settings can reach hosts this list
can't know of. `enforce` refuses those: the feature fails with a message naming the host. To allow one, add it to
`privacy.allow_hosts` (`["feeds.example.org"]`; `".example.org"` allows every host under it). `off` checks and counts
nothing. Your add-ons' own code is covered only when it makes its requests through Kurooto's (`core/egress.py`).

## Free tiers and terms

**A free Gemini API key** (Google AI Studio's free tier):
- Google may use what you send and what it answers to improve its products, and human reviewers may read it.
- You must be 18 or older.
- In the EEA, the UK and Switzerland you need a paid key (billing turned on).
- Phone calls and voice notes always go through Gemini, whichever AI answers your messages (a call turn by turn can
  use the model on your computer instead: `calls.turn_brain` = `local`).

If you don't want that, use a paid key: on paid tiers Google doesn't use what you send to improve its products. Or
keep those features off, or use local models where offered.

**Antigravity (agy):** Kurooto runs Google's official agy program on your computer, signed in as you, and never touches
its sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is some risk to
your Google account. For tools like Kurooto, Google recommends a Gemini API key.

Every other AI service you pick (Claude Code, a custom OpenAI-compatible one) works under its own terms and your
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
| Mail digest | read your email (read-only) | reads only the mail you choose for the digest (rules, your own domain, or your Gmail search); the rest it counts by its sender, subject and labels, on your computer. Can't send, delete or mark anything |
| Agent plan calendar | make secondary calendars and manage their events | makes one calendar of its own, "Agent plan", and writes only there; it can't see or change your other calendars |
| Google Calendar | see your calendars (read-only) | reads your own calendars and the ones you subscribed to, the next two weeks; calendars other people share with you are left out. Changes nothing |
| Mail digest by email | send email on your behalf; see your email address | sends each mail digest to that account's own address and to no one else. Can't read your mail |
| Drive upload | see, edit, create and delete only the Drive files it uses | makes one folder, "Kurooto", and uploads the files you send yourself there. Can't see your other files; shares nothing |
| Every account (from 0.5.1; before, any but the first) | see your email address | to show which account is which ("school: sam@school.example") |

**Several accounts.** Each Google account you add signs in on its own and is asked only for the permissions of the
features you give it (`/google` lists them). Its sign-in is kept in this computer's keychain like the first one's;
`/google forget <name>` removes it from this computer.

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
in the state folder (`ask/<id>.json`), deleted `privacy.keep_days` (30) after they're answered or expire
(`ask.keep_days` when you set one). The events log records when and where you answered, not what.

## How long it's kept

What Kurooto keeps of your conversations on this computer is forgotten after `privacy.keep_days` (30 days; 0 keeps
it until you forget it), every night: call transcripts and calls that went on as text, AI requests and their answers
(the time, AI and effort stay, without the words), Chat's recent turns, answered questions, Wrong-button cases you
didn't make test cases, the words of messages that came by themselves, the search index of past requests, and log
lines. `/forget 7d` forgets the last 7 days now; `/forget all` forgets everything, after a confirm button. Your notes
folder is never touched (a voice note's recording is saved there, so it stays), nor the event log, which holds times,
counts and names but never what you typed or what was answered. Your call line holds a call's transcript only while
the computer is off and hands it over when it's back. Backup zips you made before keep what they had.

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

- **Starting at boot** (Linux, opt-in: `kurooto autostart boot` or Settings → Starting): your keychain is locked
  until you log in, so Kurooto's keys are kept in its owner-only settings file (`secrets.json`, readable only by your
  account) instead. `kurooto autostart login` moves them back.
- **Backups:** with `backups.secrets` on, your keys are copied into each backup zip (`secrets.json`), in plain text;
  anyone who gets the zip can use them. Off by default.
- **Your call line and Telegram:** if you approve "going offline" messages from your call line (asked once), your
  Telegram bot's token and your chat id go to your call line on your own Cloudflare account, beside your Gemini key.
  With them the line can send messages as your bot (it only sends "Kurooto has been offline since ..."). Set
  `notify.presence.line_telegram` to `false` and they're deleted there at the next sync.
- **Profile sync:** your keys also go to your repository, encrypted with your passphrase (AES-GCM, with a key from
  scrypt). The passphrase is never stored; this computer keeps the profile's data key in its keychain, like your other
  keys, so it can save on its own. Never in the profile: this computer's dashboard key, and the reports you added in
  About you.

## Your phone

The Android app keeps its pairing (the call line's address, its device key, the ring messages' key) in its private
storage. Nothing personal is built into the app. The iPhone web app keeps its device key in Safari's storage for the
Home Screen app. Unpair a phone with `/phones` → `/unpair`, or on the dashboard's Phone tab. A lost phone holds that
pairing and the ring messages' key: `kurooto rotate` gives your call line new keys (they go to your own Cloudflare
account, as on every setup), and the line then forgets every phone paired before, so the lost one can't call, be
called or read new messages.

Answers from the Android app are sealed with the same key as the ring messages. That key keeps them from ntfy, not
from your call line: the line holds it too (it seals the ring messages and gives it to each Android phone when it
pairs), so your call line, on your own Cloudflare account, could read them. Only what Reminders with the lid shut
hands over is sealed with keys that only your phones hold. The iPhone app's answers travel over HTTPS with its device
key. Each answer can be used once (it carries a random number and the time it was sent).

## Removing it all

`kurooto uninstall` removes Kurooto's settings and data from your computer (your notes folder is kept). Your call
line, Google client, notes repository and the `kurooto-profile` branch are on your own accounts, and backup zips are
in the folder you picked: delete them there (see the manual's Uninstall).

`kurooto uninstall --revoke` first takes back Kurooto's access, which means asking each service: Cloudflare to delete
your call line (with its keys and stored data, the Telegram token and chat id it may hold included) and then to sign
Kurooto out; Google's revoke endpoint, sent each sign-in's token, which is how a token is revoked; Telegram to drop your
bot's webhook, waiting messages and command menu. Nothing else is sent. It then removes Kurooto's keys from your
system's keychain. The GitHub token, the Gemini key, the bot itself and the Google client are yours to delete; it
prints where.
