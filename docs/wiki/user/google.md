# Google: Classroom, Gmail, Calendar and Drive

Kurooto can read your Google Classroom, sort your Gmail into a digest, write email drafts, read your Google calendars,
keep a calendar of planned time blocks, and put big files in your Google Drive. All of it uses **your own Google
sign-in through a free Google Cloud project that only you own**. Setting that up takes 10 to 15 minutes, once. Each
Google feature is off until you set it up, and each asks Google for only the permission it needs.

If all you want is your timetable or calendar, you may not need any of this: the [Calendar](classes-and-timetable.md)
feature reads a calendar's private iCal link with no Google project at all.

- [Why your own Google project](#why-your-own-google-project)
- [Setting up your own sign-in, step by step](#setting-up-your-own-sign-in-step-by-step)
- [What each feature asks Google for](#what-each-feature-asks-google-for)
- [Google (Classroom deadlines and posts, Gmail drafts)](#google-classroom-deadlines-and-posts-gmail-drafts)
- [Several Google accounts](#several-google-accounts)
- [Classroom → notes](#classroom--notes)
- [Mail digest](#mail-digest)
- [Email reply drafts](#email-reply-drafts)
- [Mail digest by email](#mail-digest-by-email)
- [Agent plan calendar](#agent-plan-calendar)
- [Google Calendar](#google-calendar)
- [Drive upload](#drive-upload)
- [Taking access away](#taking-access-away)
- [When something goes wrong](#when-something-goes-wrong)

## Why your own Google project

Most apps sign you in to Google through the app maker's own registration, so the maker's servers hold your Google
access. Kurooto doesn't do that. You make your own registration (an "OAuth client", see the
[glossary](glossary.md)) in a free Google Cloud project, and Kurooto on your computer signs in with it. Google sees
your own project asking for your own data, and you say yes or no. Nobody else's server sits in between, and it costs
nothing (no billing account is needed).

The price is a one-time setup and a warning screen from Google ("Google hasn't verified this app") every time you sign
in. That warning is about apps strangers publish; this one is yours.

## Setting up your own sign-in, step by step

You do steps 1 to 6 in a browser, on any computer, with any Google account. Step 7 (signing in) has to happen on the
computer Kurooto runs on, with the account whose Classroom, mail or calendar you want. A personal Google account is
easiest; school accounts sometimes block apps like this (see [When something goes wrong](#when-something-goes-wrong)).

Google renames these screens now and then. If a button has a slightly different name, pick the nearest match: the order
stays the same. The Google card in Kurooto (Dashboard → Features → Google, or the setup wizard) has the same steps,
links to each page, and copy buttons for the values you need to paste.

**1. Create the project.** Open
[console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate).
1. Project name: `Kurooto` (any name works; only you see it). Leave Organization or Location as it is.
2. Press **Create** and wait a few seconds.
3. Check that the project picker at the top of the page shows the new project. Every step below happens inside it.

**2. Turn on the APIs your features use.** An API is a switch that lets your project talk to one Google product. Open
the link for each feature you want, check the project name at the top, and press **Enable**. You can come back for more
later.

| For | API | Link |
|---|---|---|
| Google (Classroom deadlines and posts), Classroom → notes | Google Classroom API | [classroom.googleapis.com](https://console.cloud.google.com/apis/library/classroom.googleapis.com) |
| Gmail drafts, Mail digest, Email reply drafts, Mail digest by email | Gmail API | [gmail.googleapis.com](https://console.cloud.google.com/apis/library/gmail.googleapis.com) |
| Classroom → notes (files attached to posts), Drive upload | Google Drive API | [drive.googleapis.com](https://console.cloud.google.com/apis/library/drive.googleapis.com) |
| Agent plan calendar, Google Calendar | Google Calendar API | [calendar-json.googleapis.com](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) |

**3. Branding: what Google's sign-in screen says about your app.** Open
[Google Auth Platform → Branding](https://console.cloud.google.com/auth/branding). The first time it says "Google Auth
platform not configured yet": press **Get started**. A short form asks four things:
1. App Information: App name `Kurooto`; User support email: your own address. **Next**.
2. Audience: **External** (anyone with a Google account may sign in, which here means you). **Next**.
3. Contact Information: your own email address. **Next**.
4. Finish: tick "I agree to the Google API Services: User Data Policy", **Continue**, then **Create**.

Back on the Branding page, fill in the rest and press **Save** at the bottom:

| Field | What to put |
|---|---|
| App name | `Kurooto` (already there) |
| User support email | your own email (already there) |
| App logo | leave it empty (a logo needs Google's review) |
| Application home page | `https://avtarfr.github.io/kurooto/` |
| Application privacy policy link | `https://avtarfr.github.io/kurooto/privacy.html` |
| Application terms of service link | the home page again, or leave it empty |
| Authorized domains | **Add domain**, then `avtarfr.github.io` |
| Developer contact information | your own email |

Why Kurooto's public pages: Google asks every app that's "in production" for a home page and a privacy policy on an
authorized domain. They describe what Kurooto does with your data. Nothing is sent to that site.

**4. Audience: publish the app.** Open
[Google Auth Platform → Audience](https://console.cloud.google.com/auth/audience). Publishing status says **Testing**:
press **Publish app**, then **Confirm**. It becomes **In production**.

Why this matters: in Testing, Google ends every sign-in after **7 days** (Kurooto would ask you to sign in again every
week), and only accounts listed under Test users can sign in at all. In production your app stays **unverified**,
which is fine for personal use: up to 100 people can ever sign in to an unverified app, and each sees the warning
first. You don't need to submit it for verification; ignore that if Google suggests it. If you made the project with a
school or work account and will only ever sign in with that organisation's accounts, **Internal** works too (no
Publish step, no warning), if Google offers it.

**5. Data access: nothing to do.** The
[Data access](https://console.cloud.google.com/auth/scopes) page lists the permissions ("scopes") an app declares.
Leave it empty: Kurooto asks for each permission when you set a feature up. If you add scopes here, Google may suggest
verification; ignore it.

**6. Clients: make your desktop client.** Open
[Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients).
1. **Create client**.
2. Application type: **Desktop app**. Name: `Kurooto`.
3. **Create**. A window shows the client ID and secret: press **Download JSON** right away. Google shows the secret
   only this once. (Closed it? Open the client, press **Add secret**, and download again.)
4. In Kurooto: Dashboard → Features → Google → paste the file's contents into the box (or press the file button and
   choose the file) → **Save**. The setup wizard's Google card has the same box.

Keep this file to yourself, like a password. On its own it can't read your data (that also takes your sign-in), but it
lets an app present itself as yours. Kurooto keeps it in your computer's keychain. Kurooto refuses a file for a "Web
application" client (it must be a Desktop app) and a file without a client ID and secret.

**7. Sign in.** After Save, Kurooto opens Google's sign-in in your browser.
1. Pick the account whose Classroom, mail or calendar you want.
2. Google says **"Google hasn't verified this app"**. That's your own project, made minutes ago. Press **Advanced**,
   then **Go to Kurooto (unsafe)**. "Unsafe" only means Google hasn't reviewed it.
3. Google lists what Kurooto asks for. Leave every box ticked and press **Continue**.
4. The tab says "Signed in with Google as you@example.com (main)". Close it; the Google card in Kurooto turns on.

**Adding more Google features later.** Each one needs one more permission. Turn on its API (step 2), press **Save** on
its card in Dashboard → Features, and sign in again (step 7). Google lists the new permission and shows the warning
screen again. When you're back, the feature turns on by itself. If you untick its box on Google's screen, that feature
stays off and everything else keeps working. Google may call a permission "restricted" or "sensitive": that's Google's
label for mail and Drive access, and it's fine for your own client.

## What each feature asks Google for

| Feature | Google's permission | What Kurooto does with it |
|---|---|---|
| Google (Classroom deadlines and posts) | see your Classroom courses, your coursework and announcements (read-only) | due dates into Deadlines, new announcements to Telegram. Changes nothing |
| Gmail drafts (part of the Google feature) | manage drafts and send email | writes drafts you asked for with `/draft`; never sends them |
| Classroom → notes | see your Classroom course materials; see and download your Google Drive files (read-only) | reads materials, coursework and announcements, and opens only the Drive files attached to or linked from a post. Changes nothing |
| Mail digest | read your email (read-only) | reads only the mail you choose; the rest it counts by sender, subject and labels, on your computer. Can't send, delete or mark anything |
| Email reply drafts | manage drafts and send email | writes reply drafts to mail in your digest; sends one only when you tap Send |
| Mail digest by email | send email on your behalf; see your email address | emails each digest to that account's own address and nobody else. Can't read your mail |
| Agent plan calendar | make secondary calendars and manage their events | makes one calendar of its own, "Agent plan", and writes only there. Can't see or change your other calendars |
| Google Calendar | see your calendars (read-only) | reads your own calendars and ones you subscribed to, two weeks ahead. Changes nothing |
| Drive upload | see, edit, create and delete only the Drive files it uses | makes one folder, "Kurooto", and uploads there the files you send yourself. Can't see your other files; shares nothing |
| Every account | see your email address | to tell your accounts apart ("school: you@school.example") |

## Google (Classroom deadlines and posts, Gmail drafts)

**What it does.** The base Google feature, which every other Google feature builds on.
- **Classroom deadlines:** every 3 hours it reads your active Classroom courses. Each assignment with a due date (from
  two days ago onward) goes onto your [deadline list](reminders-and-deadlines.md) as "Course: assignment", and is
  marked done there when you hand it in on Classroom (turned in or returned).
- **Classroom announcements:** each new announcement comes to Telegram as "New in Linear Algebra: ..." (the first 400
  characters) with an **Open** button to the post. The very first check only learns what's already there, so you
  don't get a flood of old posts.
- **Posts for missed classes:** each course's posts of the last 30 days (when, title, link) are kept on this computer,
  so the [catch-up for a class you missed](classes-and-timetable.md#catching-up-on-a-class-you-missed) lists what was
  posted that day. Classroom → notes adds materials to them.
- **Gmail drafts** (off by default): `/draft` writes an email draft into your Gmail. Kurooto never sends it; you open
  Gmail, check it and send it yourself.

**Turn it on.** Do the [step-by-step setup](#setting-up-your-own-sign-in-step-by-step) (Classroom API on), then
Dashboard → Features → Google → paste the client file → Save → sign in. For drafts, also turn on the Gmail API, set
`google.gmail_drafts` to `true` (Dashboard → Settings → google), and sign in again (Save on the card).

**From Telegram.**
- `/classroom`: check Classroom now (deadlines and new posts).
- `/draft someone@example.com ask for an extension on problem set 3`: the AI writes the email (needs Chat on) and saves
  it as a draft. You get "Draft saved in Gmail: ... Open Gmail to check it and send it yourself." (also when Kurooto
  restarted while the AI was writing it).
- `/draft someone@example.com | Extension request | Dear ...`: subject and text written by you, saved as it is. No AI.
- `/draft` only exists while `google.gmail_drafts` is on.
- `/sync all` (or "sync everything") also checks Classroom, then Classroom → notes and the mail digest.

**Settings that matter** (Dashboard → Settings → google):

| Setting | Default | Effect |
|---|---|---|
| `google.classroom` | `true` | read Classroom (deadlines and announcements) |
| `google.classroom_every` | `every 3h` | how often Classroom is checked |
| `google.classroom_on_calls` | `false` | a call's brief gets the titles of the last day's Classroom posts (0.9.0; the call's AI reads them) |
| `google.gmail_drafts` | `false` | allow `/draft` (needs one more sign-in) |
| `google.accounts` | `["main"]` | your Google accounts by name ([below](#several-google-accounts)) |
| `google.use` | `{}` | which account each feature uses; unset means main |

**Limits and edge cases.**
- Assignments without a due date, and ones due more than two days ago, aren't added.
- A topic on your not-interested list (`/ignore`) is left off the deadline list like any other deadline.
- "Less of this" on an announcement offers **Fewer** (at most one announcement a day; the rest wait for the evening
  bundle) or Stop. See [messages-it-sends.md](messages-it-sends.md).
- If the sign-in expires or you remove Kurooto's access at Google, you get an urgent message: "Google sign-in expired
  ... the Google features are paused". Sign in again from Dashboard → Features → Google. (A short-lived access key
  that Google refuses is simply renewed; only Google saying the sign-in itself is gone pauses anything.)

**What leaves your computer.** Nothing new: Kurooto reads from Google with your own sign-in. Drafts are written into
your own Gmail. The sign-in tokens stay on your computer: in its keychain, or where there's none (or Kurooto starts at
boot), in a file only your user can read.

**Turn it off.** Dashboard → Features → Google → Turn off. Features that build on it (reply drafts, digest by email)
must be off first.

## Several Google accounts

**What it does.** Lets each Google feature use the account you choose: say the mail digest reads your school account
while Drive upload uses your personal one. The first account you sign in with is **main**; every feature uses main
unless you say otherwise. Each account signs in on its own (same Google Cloud project) and is asked only for what the
features using it need.

**On the dashboard.** Each Google feature's card has a **Which Google account** box. It shows the account in use with
its address. Leave it empty to keep it; type a new name (a short word like `school`) to add that account: Google's page
opens with its account chooser, so pick the right one. Google Calendar can read several at once: `main, school`
(press Save once for each account). Email reply drafts have no box: they always use the mail digest's account.

**From Telegram.**
- `/google`: your accounts, each with its address and what uses it.
- `/google use mail school`: move a feature to another account. The feature names you can use: `classroom`, `drafts`,
  `mail`, `email` (digest by email), `calendar`, `plan` (or `blocks`), `drive`, `classroom_notes`. A new name adds an
  account. If that account hasn't given its OK yet, the feature pauses until you press Save on its card and sign in;
  the reply says so.
- `/google forget school`: forget that account's sign-in on this computer. Its features go back to main. (`main` can't
  be forgotten this way.)

**Limits and edge cases.**
- An account name is one short word: letters, digits and dashes, up to 24 characters.
- Only Google Calendar takes several accounts; every other feature uses one.
- Signing in to the same Google account under two names gets "That's the same Google account as your main one": the
  browser picked the account you were already signed in with. Save again and choose the other account.
- If one account's sign-in expires, only the features using it pause, and the message names them.

**Turn it off / undo.** `/google forget <name>`. To take the access away at Google too, open
myaccount.google.com/connections while signed in to that account.

## Classroom → notes

**What it does.** Three times a day (07:00, 13:00, 19:00) Kurooto reads what's new in your active Classroom courses:
materials, coursework, announcements, and the Drive files your teachers attach or link. The AI then files each course
into your notes, in the course's folder (it uses the matching subject from
[Subjects](classes-and-timetable.md) when there is one, else a folder named after the course):
- a note per lecture or problem set (e.g. `linear-algebra/2026-10-20-eigenvalues.md`): what it covers, the teacher's
  post, the files, and links to your related notes;
- the course page `linear-algebra/course.md`: lecture notes in order, coursework under Tasks, exams and announcements;
- an always-current `linear-algebra/exam-prep.md` with Next assessment, Covered so far, Must know (what
  [Quiz](quiz-and-exams.md) asks you), Typical questions and Gaps. Kurooto rewrites only the part between its two
  markers; anything you write above or below them stays.

Dates in posts (a midterm, a moved quiz) go into Deadlines, on that course; assignment due dates already arrive
through the Google feature. It also keeps your notes' home page linked to your courses, and a class you missed gets
that day's posts in its catch-up.

**Turn it on.** Needs the Google feature. Turn on the Drive API (and the Classroom API) in your project, then Dashboard
→ Features → Classroom → notes → Save → sign in again.

**From Telegram.**
- `/classnotes`: check now and hand anything new to the AI ("Found 4 new item(s) in 2 course(s); the AI is filing
  them..."). `/sync all` does it too.
- `/classnotes courses`: your courses and the notes folder each goes to (or "skipped").
- `/classnotes skip chess`: leave out courses with "chess" in their name. `/classnotes unskip chess` undoes it.

Each check ends in one message, once the AI has filed everything it found, whichever courses it came from:
"Classroom: filed 3 new items from Linear Algebra into linear-algebra/:" and the items by title (the first eight, then
"and N more"). A batch the AI couldn't file is tried again with the next check and is in that check's message.

**Files it reads.**

| File | What happens |
|---|---|
| Word, PowerPoint | read as text |
| Google Docs and Slides | exported as text |
| Google Sheets | exported as CSV |
| PDF | read when `pdftotext` (Poppler) is installed, or by an AI that opens files itself (agy, Claude Code) |
| Text files (.txt, .md, .tex, .csv and similar) | read as they are |
| Videos, audio, images, other Google file types | linked, not downloaded |
| Anything over `classroom_notes.max_file_mb` (30 MB) | linked, not downloaded |

Files are kept in Kurooto's data folder, not your notes (or in your files folder, if you set `files.folder`; see
[notes-and-concept-graph.md](notes-and-concept-graph.md)). The AI reads up to about 60,000 characters of file text per
request and can read more of a file when it needs to.

**Into the concept graph.** With the [Concept graph](notes-and-concept-graph.md#concept-graph) on, each filed file
with real text (slides, handouts, PDFs, solutions: 1,500 characters or more, not a one-line announcement) is then
read into it like a book: new concept notes, links with reasons, and "Seen in" lines pointing at the lecture note the
file was filed into. Each file is read once (the same file filed again isn't read twice; an edited one is). Files
filed before 0.5.19: `/graph backfill classroom`. To leave class files out, take `classroom` out of
`integrate.sources`.

**Settings that matter** (Dashboard → Settings → classroom_notes):

| Setting | Default | Effect |
|---|---|---|
| `classroom_notes.at` | `daily 07:00,13:00,19:00` | when it checks |
| `classroom_notes.skip` | `[]` | courses to leave out (words from their names); `/classnotes skip` fills it |
| `classroom_notes.folders` | `{}` | a course's exact name → the folder you want, e.g. `{"MA101 Linear Algebra (2026)": "linear-algebra"}` |
| `classroom_notes.files` | `true` | download attached files and read their text |
| `classroom_notes.max_file_mb` | `30` | bigger files are only linked |
| `classroom_notes.backfill_days` | `60` | how far back it looks; older posts not edited since are left alone |

**Limits and edge cases.**
- Posts are handed to the AI eight at a time. If the AI fails, the batch waits and is tried again at the next check;
  after three failures you get one message ("the AI couldn't file the new posts ... I'll keep trying").
- Posts about a topic on your not-interested list are only counted, not filed.
- It's heavy work: on a laptop on battery (with the default battery saver) it waits for the charger. Past 70% of a
  free AI limit it waits for the reset. See [your-computer.md](your-computer.md) and [ai-brains.md](ai-brains.md).
- If the Drive or Classroom permission is missing, you get "Classroom → notes is paused: needs Google's OK ..." at most
  once a day until you Save on its card and sign in.

**What leaves your computer.** Post text and the text of attached files go to the AI you picked, to write the notes.
Nothing is changed in Classroom or Drive.

**Turn it off.** Dashboard → Features → Classroom → notes → Turn off. The notes stay.

## Mail digest

**What it does.** Twice a day (08:00 and 18:00) your new Gmail comes to you as one short message (about 15 lines; a
busy check comes in parts, 20 mails each), grouped by what it asks of you: **Needs you** (requests, forms, replies due),
**Dates** (exams, quizzes, deadlines, events, marked "added" when they went into Deadlines), **Courses** (other news
per course) and **Worth knowing** (people, opportunities, office notices, five lines at most); newsletters are only
counted. A copy goes in your notes (`mail/2026-10-20-0800.md`, linked from that day's journal). Mail about exams
becomes your schedule at once: every exam of your subjects in it, or in a schedule attached as a PDF, is a deadline
with its time and room, and the room, syllabus and what to bring go under `## Exams` in the course note. Course news
goes onto the course page. Gmail is only read: nothing is ever sent, deleted, archived or marked
read.

**You choose what it may read.** Everything else is only counted, by sender, subject and labels, on your computer; its
text never goes to the AI. Mail is read when it matches, in this order:

| Order | Rule | Result |
|---|---|---|
| 1 | a topic on your not-interested list | only counted |
| 2 | on your never-read list (`/mail never`) | only counted |
| 3 | marked confidential in its subject or a label | only counted |
| 4 | a sender, domain or label you chose (`/mail read`) | read |
| 5 | matches your Gmail search (`/mail query`) | read (personal mail among it is only counted) |
| 6 | Promotions or Social | only counted |
| 7 | from your own organisation's domain (school or work account) | read (personal mail among it is only counted) |
| 8 | anything else | only counted |

Then, for mail that's read, its whole text (footers and quoted replies too) is checked for confidentiality markings on
your computer; a marked mail is dropped there and only counted. Chats, sent mail, drafts, spam and trash are never
looked at.

A personal Gmail account reads nothing until you choose something; the scheduled digest tells you how, at most once a
day: "Mail digest: 12 new message(s), none from senders or labels you chose, so I only counted them...".

**From Telegram.**
- `/mail`: check now ("Reading 5 new message(s) (12 only counted); the digest comes in a minute.").
- `/mail read @school.example` (a domain), `/mail read someone@example.com` (a sender), `/mail read label:Courses` (a
  Gmail label). `/mail unread ...` takes one off.
- `/mail never @office.example` keeps a sender, domain or label out altogether, even if chosen above. `/mail unnever
  ...` takes it off.
- `/mail query -category:promotions -category:social`: read all mail matching a Gmail search (any Gmail search words
  work: `label:Courses OR from:school.example`, `-category:forums`). `/mail query` shows it; `/mail query off` clears
  it.
- `/mail rules`: what it reads, the never-read list, and whether confidential mail is skipped.
- `/mail confidential`: dates found in confidential mail summarised on this computer (local mode only; below), titles
  and dates only, each with **Add to Deadlines** and **Not needed**.
- `/sync all` also runs the digest.

**Confidential mail is never read by the AI.** School and work mail may fall under your institution's email policy.
If a mail's subject, its text (all of it) or a Gmail label's name says "confidential", "do not forward", "restricted",
"private and confidential", "privileged and confidential", "proprietary and confidential", or carries a standard
footer ("intended solely for the addressee", "if you are not the intended recipient", "this e-mail and any attachments
are confidential / may be privileged"), it's only counted, even from a sender or label you chose, and never gets an AI
reply draft. Many institutional mails carry such a footer, so expect more of your mail to be only counted.

**Optional: confidential mail summarised on this computer.** Set `mail_digest.confidential` to `local` and turn on
[Local AI models](your-computer.md). A model on this computer (Ollama) then reads marked mail instead of leaving it
counted; the AI you picked still never sees it. The summary is kept only in Kurooto's data folder
(`mail/confidential/<date>.md`, readable only by your user account): not in your notes, not on Telegram (which only
says "Confidential (2): summarised on this computer; open the dashboard to read it"), not in Profile sync, and not in
Backups unless you turn on `backups.confidential_mail`. Read it on the dashboard: Features → Mail digest →
**Confidential mail**, which also lists the dates it found with **Add to Deadlines** / **Not needed**. Nothing is added
to Deadlines until you tap. Limits: up to 15 such mails a check, three per request to the local model, each cut to its
first 3,500 characters. Without a ready local model (off, not set up, or resting on battery) marked mail is only
counted and you're told once.

**Settings that matter** (Dashboard → Settings → mail_digest):

| Setting | Default | Effect |
|---|---|---|
| `mail_digest.at` | `daily 08:00,18:00` | when it checks |
| `mail_digest.read` | `[]` | your read rules; `/mail read` fills it |
| `mail_digest.never_read` | `[]` | your never-read list; `/mail never` fills it |
| `mail_digest.own_domain` | `true` | on a school or work account, read mail from your own domain |
| `mail_digest.query` | empty | a Gmail search whose matches are read |
| `mail_digest.first_days` | `3` | how far back the first check looks |
| `mail_digest.on_calls` | `false` | a call's brief gets the last digest's "Needs you" line (0.9.0; the call's AI reads it) |
| `mail_digest.max_messages` | `200` | most mails looked at per check |
| `mail_digest.save_note` | `true` | keep a copy of each digest in your notes |
| `mail_digest.skip_confidential` | `true` | never read mail marked confidential |
| `mail_digest.confidential_words` | the markings above | regular expressions, any case; a space matches any spaces or line breaks |
| `mail_digest.confidential` | `count` | `count` (only counted) or `local` (summarised on this computer) |
| `mail_digest.local_model` | empty | the Ollama model for local summaries; empty: Local AI models' helper |

**Limits and edge cases.**
- If the digest can't be written (the AI failed), you're told after the first and third failure; the mail waits for
  the next check.
- "Less of this" on a digest offers **Fewer** (once a day, at the first time) or Stop (turns the feature off).
- Kurooto keeps the sender, subject and a short excerpt of digested mail for 30 days, so a reply draft can answer it.

**What leaves your computer.** The text of the mail you chose (and, with a query, the mail it matches) goes to the AI
you picked. For everything else, only counts, on your computer.

**Turn it off / undo.** Dashboard → Features → Mail digest → Turn off. `/mail query off` goes back to only your `/mail
read` rules and your own domain.

## Email in

**What it does.** Forward a notice, a receipt or a schedule to Kurooto, and it's filed in your notes with a short
summary, and its dates come back with an **Add** button each. Your call line lives on workers.dev, which can't receive
mail (Cloudflare only routes mail for a domain of your own), so the way in is your own Gmail, with the Mail digest's
read-only access:

- forward it to your own address with `+kurooto` before the @ (`example+kurooto@gmail.com` for example@gmail.com; Gmail delivers it to you as
  usual; on a school account, `you+kurooto@school.example`), or
- put a Gmail label on it (`/mail in label Kurooto`), by hand or with a Gmail filter.

Every ten minutes (`mail_digest.mail_in_every`) Kurooto looks for such mail. Each one goes to the AI you picked, which
writes the note in your notes' inbox (`inbox/2026-10-23-hostel-fee.md`: a summary, a link to open it in Gmail, then
the mail's text) and lists its dates. You get "Email in: Hostel fee, filed in inbox/...", with the dates, if any, each
with **Add** (a deadline or exam goes into Deadlines, an event becomes a reminder), **Add all** and **None of these**.
Nothing goes into Deadlines until you tap. Each mail goes in once.

**Turn it on.** Mail digest must be set up (it's the same Gmail access). Then `/mail in on`. It's off by default.

| You send | What happens |
|---|---|
| `/mail in` | whether it's on, your +kurooto address, and who may send mail in |
| `/mail in on` · `/mail in off` | turn it on (and look now) or off |
| `/mail in label Kurooto` · `/mail in label off` | mail with that Gmail label goes in too, from anyone |
| `/mail in from you@school.example` · `/mail in unfrom ...` | your other address, which forwards to +kurooto, may send mail in |

**Who may put mail in.** Anyone who learns your +kurooto address could mail it, so mail to it goes in only when it's
from your own address or one you listed (`/mail in from`); anything else is never even opened. A label is yours to put
on, so labelled mail goes in from any sender. Your never-read list (`/mail never`) and the confidentiality check still
hold: such mail is only counted, never read. The AI reads the mail as information, never as instructions, with no
tools: it can only write the note's summary and list dates. `mail_digest.mail_in_anyone` lets mail to +kurooto in from
anyone (not recommended).

**With your own domain.** If your domain's mail is on Cloudflare, Cloudflare Email Routing (free) can deliver
`kurooto@your-domain.example` to `example+kurooto@gmail.com`: add the Gmail address as a destination, then a rule for the address.
Mail sent there then arrives "from" whoever sent it, so add those senders with `/mail in from`, or have Gmail label it
(a filter on `to:kurooto@your-domain.example`, label Kurooto). A Cloudflare Email Worker that hands mail straight to your call
line isn't built yet.

**Settings** (Dashboard → Settings → mail_digest): `mail_in` (off), `mail_in_label` (empty), `mail_in_senders` (`[]`),
`mail_in_anyone` (`false`), `mail_in_every` (`every 10m`).

**What leaves your computer.** The text of the mail sent in goes to the AI you picked. The note stays in your notes.

## Email reply drafts

**What it does.** When the mail digest finds mail that needs your reply (a question or request to you), the AI writes a
short reply in your voice into your Gmail Drafts and sends it to you as an approval with three buttons:

| Button | What it does |
|---|---|
| **Send** | sends that draft from your Gmail |
| **Edit** | asks "What should change?"; reply with it ("say I can do 10am") and the AI rewrites the draft, then asks again. Answer "nothing" to keep it as it is |
| **Discard** | deletes just that draft |

**Nothing is sent unless you tap Send.** Unanswered, the draft stays in your Gmail Drafts; the question expires after
3 days. You can answer on Telegram, in the [phone app](phone-app.md) or on a call.

**Turn it on.** Needs Google and the Mail digest. Dashboard → Features → Email reply drafts → Save → sign in (Google
asks to "manage drafts and send email"). It always uses the mail digest's account.

**Settings that matter** (Dashboard → Settings → reply_drafts):

| Setting | Default | Effect |
|---|---|---|
| `reply_drafts.per_day` | `5` | most drafts a day |
| `reply_drafts.ask_days` | `3` | how long the Send / Edit / Discard question stays open |

**Limits and edge cases.**
- Replies go only to the sender of a mail in your digest (or its reply-to address). Never to no-reply addresses,
  never to mail marked confidential (even in local mode), never to mail on your never-read list.
- One open draft per mail.
- If you sent or deleted the draft in Gmail yourself, tapping a button says it isn't there any more.
- If Gmail doesn't take the tap (a hiccup, an expired sign-in), the question is asked again.

**What leaves your computer.** The mail being answered goes to the AI (it was already in the digest); the draft is
written into your Gmail; a reply leaves only when you tap Send.

**Turn it off.** Dashboard → Features → Email reply drafts → Turn off. Drafts already in Gmail stay there.

## Mail digest by email

**What it does.** Each mail digest also comes to your own inbox, sent from your Gmail to yourself, with the subject
"Mail digest, Tue 20 Oct 18:00". With [several accounts](#several-google-accounts) it can send from another account
than the one the digest reads (a personal account while the digest reads a school one). It always goes to the sending
account's own address; there's no way to give it another recipient.

**Turn it on.** Needs Google and the Mail digest. Dashboard → Features → Mail digest by email → Save → sign in (Google
asks to "send email on your behalf" and to see your address).

**Limits and edge cases.**
- A digest that mentions confidential material anywhere (beyond its own "Confidential: 2" count) isn't emailed: you
  get it on Telegram only, and a note saying so.
- If Google didn't tell Kurooto your address, or sending fails, you're told (at most every 6 hours for the same
  reason).

**What leaves your computer.** The digest's text, from your Gmail to your own inbox.

**Turn it off.** Dashboard → Features → Mail digest by email → Turn off.

## Agent plan calendar

**What it does.** Kurooto makes a calendar of its own, **Agent plan**, in your Google Calendar, for the time blocks it
plans with you: the morning plan, or "block 2 to 4 for the problem set" on a call. Each block has a 5-minute reminder.
It writes only to that calendar; Google's permission covers only calendars Kurooto makes, so it can't see or change
your others.

**Turn it on.** Needs Google and the Calendar API. Dashboard → Features → Agent plan calendar → Save → sign in.

**From Telegram.**
- `/blocks`: today's blocks.
- `/blocks add 14:00-15:30 problem set 4` (also `2pm-3:30pm`, `14:00 to 15:30`): add one.
- `/blocks clear`: remove today's blocks (only Kurooto's own).
- `/blocks remove bayesian`, `/blocks remove after 22:00`, `/blocks remove all`: take some blocks out (by title or
  subject, from a time on, or all of tonight's); `/blocks undo` puts them back.
- `/blocks shift [19:00]`, `/blocks shift by 2 hours`: reschedule the day (below); `/blocks undo` puts it back.

**Each block knows what it's for.** A block is tied to the deadline, quiz or exam its title names (from
[Deadlines](reminders-and-deadlines.md)) and to that one's due date when it was planned. A block for something done,
dropped or already over (revision for a quiz that was this morning) isn't planned.

**Reschedule the day.** "Reschedule my day", "I just woke up, reschedule my day", "reschedule my day from 19:00",
"push my day by 2 hours", `/blocks shift [19:00]`, `/blocks shift by 2 hours`, or on a call: today's blocks you
haven't done move to start from now (or the time you give), each as long as it was, with the breaks between them kept
(up to 45 minutes). Starting over takes the blocks you slept through too, and puts what's due soonest first (blocks
tied to nothing keep their places); an order you give on a call ("homework first, then quiz prep") comes before that.
Pushing by some time moves only the ones not over yet, in their order. Blocks for something done, over, or moved past
"due soon" (`deadlines.plan_h`, 3 days) since they were planned are dropped and named ("Dropped, nothing left to do for
them: ..."). A block planned twice keeps its first; one that would end after 03:00 is left out and named, and so is
what's due within a day with no block yet. Tonight's blocks past midnight count too. A block that would overlap a
class you go to, a commitment or a timed event in your calendar goes after it (0.9.0). The new plan also goes in
today's daily note. `/blocks undo` puts them back.

**Planned time is busy.** [Start-by dates](reminders-and-deadlines.md#start-by-dates-and-crunch-weeks) and the
revision plan count your blocks as busy (0.9.0), so they don't plan other work into time you planned. With Google out of
reach they plan as if there were no blocks.

**A deadline that moves** (0.9.0). When a deadline moves (you, a call, or its source, such as a Classroom post with a
new due date), its blocks still ahead get "(moved to Fri 13 Nov)" in their titles and one message asks "remove its 2
plan blocks from your Agent plan calendar?" with **Remove** and **Keep**. Remove takes them out (`/blocks undo` puts them
back); Keep puts their titles back. Nothing is removed without your tap.

**A focus when a block starts** (`agent_plan.start_focus`, on, 0.9.0). With the [Study tracker](books-and-study.md#study-tracker)
on, when a block starts and you're at your desk (Face presence or the computer in use), one message: "Your block
Topology report starts now. Start a 25-minute focus for it?" with **Start 25 min**. Away from your desk: nothing, and
nothing is noted.

**Calls wait for your blocks** (`agent_plan.holds_calls`, off, 0.9.0). Turned on, a call Kurooto places by itself (a
check-in, a nudge) during a block waits until it ends. Calls you asked for and alarms still ring.

**On calls.** Agree to a time on a call ("let's do the problem set from 2 to 4") and the call puts the block in. A
block that would overlap one already planned goes in the first free time after it, and the call says the time it got;
when there's none before 03:00 it isn't planned and the call says so. "Remove those blocks", "clear everything after
10" takes blocks out (with Undo under the message it sends, or "put them back"). Today's blocks are in the call's
brief.

**Settings that matter** (Dashboard → Settings → agent_plan):

| Setting | Default | Effect |
|---|---|---|
| `agent_plan.remind_min` | `5` | Google's pop-up reminder before each block; 0 for none |
| `agent_plan.name` | `Agent plan` | the calendar's name |
| `agent_plan.start_focus` | on | a block starting with you at the desk offers a Study mode focus (0.9.0) |
| `agent_plan.holds_calls` | off | Kurooto's own calls wait for the end of a running block (0.9.0) |

**Limits and edge cases.** A block must end after it starts, be at most 12 hours long, and fall between now and a month
ahead. The same block twice is refused ("Already planned"); so is one for a quiz or exam that's over, or a deadline
that's done. Hide or delete the calendar in Google Calendar any time;
Kurooto makes a new one the next time it plans something. Moving the feature to another account (`/google use plan
personal`) makes a new Agent plan calendar there. To see the blocks in Kurooto's own Calendar too, add the Agent plan
calendar's private iCal link to Calendar.

**What leaves your computer.** Each block's title and time, into your own Google Calendar.

**Turn it off.** Dashboard → Features → Agent plan calendar → Turn off. The calendar stays in Google Calendar until you
delete it there.

## Google Calendar

**What it does.** Lets the [Calendar](classes-and-timetable.md) feature read your Google calendars through Google's
own API instead of private iCal links: for school or work accounts that don't offer a "secret address in iCal format",
and for reading two accounts at once. Everything Calendar does works the same: `/today`, `/cal`, no calls during
events, `#focus` and `#nocall`, event reminders, class calendars, private events as "Busy (private)". It reads two
weeks ahead and is read-only.

**Turn it on.** Needs Google and the Calendar API. Dashboard → Features → Google Calendar → Which Google account
(`main`, `school`, or `main, school`) → Save → sign in (once per account). When Google says yes, Calendar turns on too.

**What it reads.** Your own calendars and ones you subscribed to (a class calendar, holidays). Left out: calendars
other people share with you (a classmate's or a teacher's own calendar: their data), hidden calendars, and Kurooto's
own Agent plan calendar (`/blocks` shows that).

**Settings that matter** (Dashboard → Settings → google_calendar):

| Setting | Default | Effect |
|---|---|---|
| `google_calendar.skip` | `[]` | calendars to leave out, by any part of their name, any case: `["Birthdays"]` |

**Limits and edge cases.** A calendar you also added to Calendar as an iCal link comes twice: leave it out here with
`google_calendar.skip`.

**What leaves your computer.** Nothing; Kurooto only reads from Google.

**Turn it off.** Dashboard → Features → Google Calendar → Turn off. Calendar keeps its iCal links, if you have any.

## Drive upload

**What it does.** Puts files you send yourself into a folder of Kurooto's own in your Google Drive, **Kurooto**, and
sends you the link with an **Open in Drive** button. This is how files bigger than Telegram allows reach you.

**Turn it on.** Needs Google and the Drive API. Dashboard → Features → Drive upload → Save → sign in.

**How files get there.**
- `kurooto send lecture.mp4 --to drive` from a terminal: uploaded and kept.
- Ask your AI to send you a file "to Drive", on Telegram or on a call: uploaded and kept.
- **Anything over Telegram's 50 MB** (a file Kurooto or the AI sends you, a big study pack, several files sent at
  once that together pass the limit) goes there by itself, with `drive_upload.big_files` on. These are **temporary**:
  the message says "It's deleted from your Drive in 7 days". A daily clean-up at 04:10 deletes them when their days are
  up, each with the Google account that uploaded it (switching Drive upload to another account doesn't strand them).
- Big files go up in 8 MB pieces in the background: you first get "Uploading lecture.mp4 (212.4 MB) to your Google
  Drive; the link comes when it's done", then the link.

**Settings that matter** (Dashboard → Settings → drive_upload):

| Setting | Default | Effect |
|---|---|---|
| `drive_upload.folder` | `Kurooto` | the folder's name in your Drive |
| `drive_upload.big_files` | `true` | files over 50 MB come as a Drive link instead of not at all |
| `drive_upload.temp_days` | `7` | days a too-big-for-Telegram upload is kept before it's deleted; 0 keeps them |

**Limits and edge cases.**
- Without Drive upload, a file over 50 MB isn't sent: "Telegram takes files up to 50 MB. Turn on Drive upload..."
- To keep a temporary upload for good, move it out of the Kurooto folder in Drive before its days are up: the clean-up
  checks the folder first and leaves a moved file alone (and forgets it). `drive_upload.temp_days` `0` keeps every
  upload from the start.
- Google's permission covers only files Kurooto makes, so it can't see the rest of your Drive. Nothing is shared: the
  link opens only for you (and whoever you share it with yourself, in Drive).
- If the upload fails (sign-in expired, no space in Drive), you get "Couldn't upload ... to Drive" with the reason.

**What leaves your computer.** The files you send, to your own Drive.

**Turn it off.** Dashboard → Features → Drive upload → Turn off. Files stay in Drive until you delete them.

## Taking access away

- **One feature:** turn it off in Dashboard → Features. Its permission stays granted at Google until you withdraw it.
- **One account on this computer:** `/google forget <name>` (not main).
- **At Google:** [myaccount.google.com/connections](https://myaccount.google.com/connections) → your project (Kurooto)
  → **Delete all connections**. Kurooto then asks you to sign in again.
- **Everything, when leaving:** `kurooto uninstall --revoke` revokes every Google account's sign-in for you (see
  [updates-and-backups.md](updates-and-backups.md)).
- **Delete the client:** Clients page → tick it → **Delete** (restorable for 30 days).
- **Delete the project:** [console.cloud.google.com/iam-admin/settings](https://console.cloud.google.com/iam-admin/settings)
  → **Shut down** → type the project ID. Google deletes it after 30 days.
- Google deletes a client that hasn't been used for six months (it emails you a month before). If that happens, make a
  new one (step 6) and paste it in.
- The Agent plan calendar and the Kurooto folder in Drive stay in your Google account until you delete them.

## When something goes wrong

| What you see | What to do |
|---|---|
| "Access blocked: Kurooto has not completed the Google verification process" | The app is still in Testing and this account isn't a test user: Publish app (step 4). |
| "Access blocked: (your school) has blocked access" or "Error 400: admin_policy_enforced" | Your school's or employer's account doesn't allow unverified apps. Sign in with a personal account. For your timetable, use Calendar's private iCal link instead. Classroom has no way around it: ask your administrator, or leave it off. |
| "Error 400: redirect_uri_mismatch" or "unauthorized_client" | The client isn't a Desktop app. Make a Desktop app client (step 6) and paste that file. |
| "Error 401: invalid_client" or "deleted_client" | The file is from a client that was deleted or whose secret was replaced. Download a new file (Add secret, or a new client) and paste it. |
| "org_internal" | The project only lets its own organisation's accounts in. Use one of those, or set Audience to External. |
| "invalid_grant" | That sign-in code was already used or expired. Start the sign-in again from Kurooto. |
| "That isn't the JSON file Google gave you" / "That client is a Web application" | Paste the Desktop app client's downloaded file, whole. |
| Kurooto asks you to sign in again every week | The app is still in Testing: Publish app (step 4), then sign in once more. |
| A feature stays off after signing in ("access_denied", "Some boxes weren't ticked") | You pressed Cancel or unticked its permission. Press Save on its card and sign in again, leaving the boxes ticked. Check its API is on in your project. |
| An API "has not been used in project ... or it is disabled" | Turn that API on (step 2), wait a minute, try again. |
| The page after signing in "can't be reached" (127.0.0.1) | Sign in on the computer Kurooto runs on: Google sends you back to Kurooto there. |
| Google's screen says "Something went wrong" | Try again in a private window, signed in to one Google account only. |
| "Google sign-in expired ... the Google features are paused" | Dashboard → Features → Google → Save (signs in again). Every 7 days? Publish the app. |
| "Mail digest is paused: needs Google's OK" (or another feature) | Dashboard → Features → that feature → Save, sign in, leave its permission ticked. |
| "That's the same Google account as your main one" | The browser picked the account you were signed in with. Save on the card again and choose the other account in Google's chooser. |
| A feature says it needs your school Google account | That account's sign-in is missing or expired: Features → that feature → Save, pick that account. `/google` shows which account each feature uses. |
| The mail digest says it only counted my mail | It reads only what you chose: `/mail read @your-school.example` or `/mail read label:Name`. Mail marked confidential is always only counted (unless local mode). |
| "Confidential mail is only counted for now" | Local summaries need Local AI models on and ready (on a laptop they run on the charger). |
| The mail digest wasn't emailed | It mentioned confidential material (you got a note), or the sending account's address isn't known: Save on Mail digest by email and sign in again. |
| Classroom notes say a PDF wasn't read | Install Poppler (`pdftotext`), or use agy or Claude Code as your AI. |
| Classroom notes went to the wrong folder | Dashboard → Settings → `classroom_notes.folders`: `{"Exact course name": "folder-name"}`. |
| A Classroom file says "too large: open the link" | It's over `classroom_notes.max_file_mb` (30); raise it if you want it read. |
| A file over 50 MB didn't arrive | Turn on Drive upload; it then comes as a Drive link. |
| `/draft` says Gmail drafts are off | Set `google.gmail_drafts` to `true`, turn on the Gmail API, Save on the Google card and sign in again. |
