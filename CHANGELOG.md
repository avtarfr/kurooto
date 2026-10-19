# Changelog

## 0.2.0 (unreleased)
Many new features, each off until you turn it on. The [manual](docs/MANUAL.md) has the detail.

**Your AI**
- The setup page recommends a **Gemini API key ★** (the simplest, and Google's recommended route for tools like
  Kurooto), then agy, Codex, Claude Code, local models and any OpenAI-compatible service. Existing setups keep the AI
  they chose.
- The setup page says plainly what a free Gemini key means (Google may use and review what you send; 18+; a paid key
  in the EEA, UK and Switzerland) and what using agy through Kurooto means for your Google account.
- FreeLLMAPI is no longer offered; one set up earlier keeps working and shows as "Another OpenAI-compatible service".
- The AI can act, not just answer: every feature's tools (reminders, calls, deadlines, study log, notes, questions to
  you) reach API brains directly and agent programs (agy, Codex, Claude Code) through `kurooto mcp`, a built-in MCP
  server. The notes tools only create, add to and tick; they never change what you wrote.
- `/usage`: AI requests per day per brain over the last week, and usage limits hit.

**Questions, approvals and your phone**
- Questions and approvals from features, AI requests and your own scripts, answered anywhere: Telegram buttons or a
  reply, the phone app, or a call; the first answer wins. **Later** keeps one for your next call; `/q` lists the open
  ones. AI requests can ask you a question; your answer starts the follow-up.
- Your phone is a second channel: questions and approvals reach the Android app (Reply box, choices, Approve / Deny,
  Later) and the iPhone Home Screen app ("Waiting for you"), also while the computer is off. `notify.app_kinds` picks
  what else goes there.
- Calls: open questions come up at the start of a call, and approvals that arrive during one are asked there. Nothing
  else rings while you're on a call, and updates wait for it to end.

**Check-ins, mornings and calls**
- The evening check-in call is a debrief (classes, what slipped, open questions, study time, a quiz offer before
  exams); afterwards the AI writes your journal and study logs from what you said.
- A night check-in (off until you give it a time) says goodnight and sets the alarm, or moves to your wake-up call
  with **Tomorrow morning**.
- Unanswered or declined check-in calls become a message with Call me now / Tomorrow morning / Skip; "call me back
  later" keeps it a check-in. Change another day's check-in ("skip Friday's check-in"); `/checkins` has buttons.
- Mornings: the AI drafts your day 20 minutes before the alarm, the wake-up call goes through it, and the morning page
  opens on your computer.
- The night follows your alarm; unanswered calls ring again at +3 and +6 minutes; held calls tell you so and come by
  themselves when the block ends; "call me now".
- Calendar: `#focus` events are focus time; optionally only `#nocall` events hold calls.
- Weekly summary: an optional Sunday review call, written up in your journal.

**Study**
- Deadlines: calendar events that look like deadlines or exams, and recurring quizzes (a table in your notes,
  `/recurring`), join the list; the same thing from two places is kept once.
- Deadlines: the six-hour nudge is a call when Phone calls is on; an "Overdue?" check (Done / New date / Drop); Done
  ticks the box in your notes.
- Not interested (`/ignore`): topics left out of deadlines, and only counted in the mail and Classroom digests.
- Exam mode: on by itself two weeks before a quiz or exam (`/exam`); calls know about it; quizzes come more often.
- Quiz: sessions of several questions, a practice offer the evening before, quizzes by call, quiz check-ins.
- Subjects: term dates and exam periods (`/term`); "skipping LA on Friday".
- After-class notes: answer later on the evening call; photos and files filed next to the class log; an AI study log.
- Study tracker: sessions away from the computer (`/study la 50`, `/study stop`) and a "Study hours" section in your
  daily note.

**Notes and skills**
- Skills: `/journal`, `/study-log`, `/add-to-notes`, `/assignment`, `/connect-notes`, `/term-setup`, `/goodnight`,
  `/morning`, `/morning-prep`; reply to a skill's answer to carry on. A link sent on its own is filed into your notes.
- Your own skills (`/newskill`, `/skills copy`), routines (`/every monday 9:00 /journal plan my week`) and revision
  packs as PDF (`/pack`, with Tectonic, which Kurooto can install for you).
- Quick notes and prompts: `/note`, `kurooto note`, `/prompts`, `/prompt`.
- About you: the profile is editable right after **Build my profile** (setup page, and a new **About you** tab in the
  dashboard), with a preview of the In-brief part that goes along with every AI request; saving keeps the previous
  version. Building again asks first if you've edited it, and never replaces an edit made while it was building.
  `/aboutme` shows the In-brief part.
- Remember: `/remember`, "remember that ...", and on calls; kept in `about-me/how-to-help-me.md`, which you edit and
  which wins. Health, money and passwords are refused.
- Nightly look back: reads your answers, check-ins, call transcripts and journal; suggests settings, how-to-help-me
  lines, things to watch, skill changes (shown before saving) and ideas. Apply / Observe longer / No. `/observe`,
  `/observing`, `/lookback`.
- Notes brain: timelines (`/timeline`), an optional nightly upkeep and a weekly checkup.
- `kurooto send FILE`: a file to your Telegram; the AI can send you files from your notes.

**Google**
- Classroom → notes: new materials, coursework, announcements and attached Drive files filed into your notes by the AI
  (a note per lecture, a course page, an exam-prep note that Quiz uses); dates go into Deadlines.
- Mail digest: twice a day, sorted into Needs action, People, Courses, Opportunities and Admin. It reads only the
  senders, domains and labels you choose; mail marked confidential (anywhere in it, standard confidentiality footers
  included) and your never-read list are only counted, never summarised or answered with an AI draft. Optional local
  mode (`mail_digest.confidential = local`): a local model summarises confidential mail on this computer, kept only
  in Kurooto's data folder (dashboard → Features → Mail digest → Confidential mail); dates found there are offered
  (`/mail confidential`), never added by themselves.
- Email reply drafts with Send / Edit / Discard: nothing is sent without your tap.
- Agent plan calendar: time blocks Kurooto plans with you go into a calendar of its own (`/blocks`).
- Each Google feature asks for its own permission and turns on by itself after the sign-in.

**Your setup, kept safe**
- Backups: a daily zip in a folder you pick (an external drive, a cloud-synced folder); `kurooto restore`, which
  never overwrites a note.
- Profile sync: your settings, keys and saved state, encrypted with a passphrase only you know, in your own private
  GitHub repository. Moving to a new computer: "I've used Kurooto before" on the setup page, or
  `kurooto profile restore`.
- Sync everything: `/sync all` or `kurooto sync`. Notes sync also sends notes up after AI requests and when Kurooto
  stops.

**Research and your terminal**
- Research projects: a note per project with a log of each day's commits, a hub note, and a question when a project
  goes quiet.
- `kurooto runlog` (experiment runs with their config, metrics and exact code state), `kurooto watch -- CMD` (a
  message when a long job ends), `kurooto top` (a status board), `kurooto logs`, `kurooto ask` (plain English),
  `kurooto call`, `kurooto ask-me` and `kurooto ask-approval`.
- Terminals in the dashboard (off by default): your AI program, a shell, `kurooto ask` and the log.
- Your add-ons: your own features, skills, prompts and default settings from a folder of yours.
- On Linux, the dashboard only answers your own user account.

**Fixes**
- "skip Friday's check-in" (and "no calls on Friday", "skipping LA on Friday") changed today's instead.
- The phone app only ever got rings; the phone channel is now wired up.
- The notes brain's sync no longer holds up the rest of Kurooto, and GBrain no longer checks for its own updates.
- Long requests to agy no longer fail on Windows' command-line limit.

## 0.1.2 (2026-10-20)
- "Build my profile" and other text-only work no longer fail with agy: it's told to answer with text only.
- If agy can't do something unattended (or fails), a saved Gemini key answers instead, and the other way round when
  you've set up both. A line at the end says which AI answered.
- Without a Gemini key, the message says exactly what to do instead of a vague refusal.
- Long requests reach agy through a file, so profile builds work on Windows too.
- The setup page recommends the Gemini key first (★); agy is second, with a plain note about it.

## 0.1.1 (2026-10-20)
Fixes, delivered as the first automatic update.
- A check-in call that comes due during a class, a hold, focus or the night now waits until the block ends, or comes
  as a message if that's too late for today.
- What you say on a check-in call reaches your journal again.
- Checking Kurooto (`kurooto doctor`) while the AI is working no longer makes that request run a second time.
- A landing page at avtarfr.github.io/kurooto.

## 0.1.0 (2026-10-19)
The first release, for friends.
- One-line install on Windows, macOS and Linux (per user, no admin), signed releases, a setup wizard that reads the
  computer and recommends settings, and installs what each feature needs (with a storage check).
- AI brains: Antigravity (agy), Gemini key, ChatGPT/Codex, FreeLLMAPI, Ollama, any OpenAI-compatible service, and
  Claude Code (Advanced); a fallback brain; effort picked per request.
- Features (all opt-in): Telegram, Chat, Reminders, Check-ins (by message or call), Deadlines, Subjects and timetable,
  Quiz, Weekly summary, Files into notes, Notes brain (GBrain), Local AI models, After-class notes, Nightly look back,
  Phone calls (your own call line; Android app; iPhone web app), Morning alarm, Voice notes, Stay awake on charger,
  Calendar, Notes sync, Google (Classroom, Gmail drafts), Handwritten notes, Study tracker, Research (a digest of new
  papers from arXiv's 155 fields, bioRxiv, medRxiv, PubMed and any feed, with its own dashboard tab).
- About you: prompts to run in all your other AI accounts, their reports brought into Kurooto, and a profile built
  from them that every AI request starts from.
- A local dashboard; `kurooto doctor` and a redacted diagnostics bundle.
- Laptops: a battery saver (Telegram keeps working; heavy work waits for the charger and runs when plugged in),
  `/pause` and `/resume`, and `kurooto off` / `on` (with a Kurooto entry in the app menu to turn it back on).
- Automatic, signed updates with rollback.
