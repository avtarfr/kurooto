# google: notes for 0.2.0 (MANUAL, Troubleshooting, CHANGELOG, PRIVACY)

New module classes to register in `modules/catalog.py`, after `Google` (each `requires` Google):

| class | id | file |
|---|---|---|
| `ClassroomNotes` | `classroom_notes` | `src/kurooto/modules/google_classroom.py` |
| `MailDigest` | `mail_digest` | `src/kurooto/modules/google_mail.py` |
| `ReplyDrafts` | `reply_drafts` (requires `google`, `mail_digest`) | `src/kurooto/modules/google_mail.py` |
| `AgentPlan` | `agent_plan` | `src/kurooto/modules/google_plan.py` |

Also add the four ids to `MODULE_ORDER` in `web/api.py`, right after `"google"` (test_dashboard checks both lists
match): `"classroom_notes", "mail_digest", "reply_drafts", "agent_plan"`. Checked locally: with both registered, the
full suite passes.

Shipped skills: `src/kurooto/data/skills/classroom-digest/SKILL.md`, `src/kurooto/data/skills/mail-digest/SKILL.md`.
`/sync all` (home's syncall) calls `Google.sync_now()`, which runs Classroom, Classroom → notes and the mail digest.

---

## MANUAL: replace the "Google (Classroom, Gmail drafts)" section's last paragraph, then add the sections below

(Keep the existing section; replace its last paragraph, "Gmail drafts are off by default ...", with this.)

Gmail drafts are off by default (Settings → `google.gmail_drafts`; then sign in again). School accounts sometimes
block unverified apps; then use the Calendar feature's iCal link for your timetable instead.

**More Google features** build on this sign-in: Classroom → notes, Mail digest, Email reply drafts and the Agent plan
calendar. Each is off until you set it up, and each needs one more permission from Google. To set one up, turn on its
API in your Google Cloud project (its card links the page), press **Save** on its card, and sign in with Google again.
Google lists what it's asking for; it also shows the "Google hasn't verified this app" screen again (Advanced → Go to
(your project)). When you're back, the feature turns on by itself. If you untick a permission on Google's screen,
that feature stays off and everything else keeps working. Google may say a permission is "restricted" or "sensitive":
that's Google's label for mail and Drive access, and it's fine for your own client (the warning is about apps other
people publish).

What each one asks Google for, in plain words:

| Feature | Google's permission | What Kurooto does with it |
|---|---|---|
| Classroom → notes | See your Classroom course materials; see and download your Google Drive files (read-only) | Reads materials, coursework and announcements, and opens only the Drive files attached to or linked from a post. Changes nothing. |
| Mail digest | Read your email (read-only) | Reads only the mail you choose for the digest; the rest it counts by its sender, subject and labels, on your computer. Can't send, delete or mark anything. |
| Email reply drafts | Manage drafts and send email | Writes reply drafts to mail in your digest; sends one only when you tap Send. |
| Agent plan calendar | Make secondary calendars and manage their events | Makes one calendar of its own, "Agent plan", and writes only there. It can't see or change your other calendars. |

### Classroom → notes
Three times a day (07:00, 13:00, 19:00) Kurooto reads what's new in your Google Classroom courses: materials,
coursework, announcements, and the files your teachers attach or link from Drive. The AI files each course into your
notes, in the course's folder (`linear-algebra/`; Kurooto uses the matching subject from Subjects when you have one):
- a note per lecture or problem set (`linear-algebra/2026-10-20-eigenvalues.md`): what it covers, the teacher's post,
  the files and links to your related notes;
- the course page `linear-algebra/course.md`: lecture notes in order, coursework under Tasks, exams and announcements;
- an always-current `linear-algebra/exam-prep.md`: next assessment, what's covered so far, must-know facts (which Quiz
  asks you), typical questions and gaps. Kurooto rewrites only the part between its two markers; anything you write
  above or below them stays as you wrote it.
Assignment due dates already reach Deadlines through the Google feature; dates in posts (a midterm, a moved quiz) are
added too. Files are kept in Kurooto's own data folder, not your notes: Word and PowerPoint files and Google Docs,
Slides and Sheets are read as text; PDFs are read when `pdftotext` (Poppler) is installed, or by an AI that can open
files (agy). Videos and images are linked, not downloaded. The first check goes back 60 days.

- `/classnotes` checks now (so does `/sync all`); `/classnotes courses` lists your courses and the folder each one
  goes to.
- `/classnotes skip chess` leaves out courses with "chess" in their name; `/classnotes unskip chess` undoes it.
- Posts about a topic on your not-interested list (`/ignore`) are only counted.
- Settings: `classroom_notes.at` (when), `classroom_notes.folders` (a course's exact name → the folder you want),
  `classroom_notes.files` (download attached files), `classroom_notes.max_file_mb` (30), `classroom_notes.backfill_days`.
- If the AI fails, the posts wait and are tried again at the next check; after three failures you get a message.
- *Leaves:* posts and file text go to the AI you picked. *Turn off:* Features → Classroom → notes → Turn off; the notes
  stay. To withdraw Google's permission: your Google account → Security → Third-party access → your project.

### Mail digest
Twice a day (08:00 and 18:00) your new mail, sorted into **Needs action**, **People**, **Courses**,
**Opportunities** and **Admin**, comes to you as one message, with a copy in your notes (`mail/2026-10-20-0800.md`,
linked from that day's journal). Deadlines it finds go into Deadlines; course news goes onto the course page.

**You choose what it may read.** Everything else is only counted, and its text is never downloaded:
- `/mail read @school.example` (a domain), `/mail read sam@example.org` (a sender), `/mail read label:Courses` (a
  Gmail label); `/mail unread ...` takes one off; `/mail rules` lists them.
- On a school or work Google account, mail from your own organisation's domain is read too (setting
  `mail_digest.own_domain`). Personal mail among it (not about study or work) is only counted.
- Promotions, Social and topics on your not-interested list are only counted.
- A personal Gmail account reads nothing until you choose something; the first digest tells you how.

**Confidential mail is never read.** Work or school mail may be covered by your institution's email policy (many
forbid forwarding confidential messages, and institutional mail belongs to the institution). Kurooto never summarises
mail marked confidential: if its subject, its text (all of it, footers and quoted replies too) or a Gmail label's name
says "confidential", "do not forward", "restricted", "private and confidential", "privileged and confidential",
"proprietary and confidential", or has a standard confidentiality footer ("intended solely for the addressee", "if you
are not the intended recipient", "this e-mail and any attachments are confidential / may be privileged"), it's only
counted, even from a sender or label you chose, and it never gets an AI reply draft. Its text is dropped as soon as
it's checked; Kurooto doesn't keep it. Many institutional mails carry such a footer, so expect more mail to be only
counted. Tune the list in `mail_digest.confidential_words` (regular expressions; any case; a space matches any run of
spaces). To
keep a sender, domain or label out of the digest altogether: `/mail never @office.example` (`/mail unnever ...` takes
it off; `/mail rules` lists both lists). This is on by default (`mail_digest.skip_confidential`).

`/mail` checks now (so does `/sync all`). Settings: `mail_digest.at`, `mail_digest.read`, `mail_digest.never_read`,
`mail_digest.own_domain`, `mail_digest.skip_confidential`, `mail_digest.confidential_words`, `mail_digest.save_note`
(the copy in your notes), `mail_digest.first_days` (how far back the first check looks: 3).
*Leaves:* the text of the mail you chose goes to the AI you picked; for the rest, only counts. Nothing is ever sent,
deleted, archived or marked read. *Turn off:* Features → Mail digest → Turn off.

### Email reply drafts
When the mail digest finds mail that needs your reply (a question or request to you), the AI drafts a short reply in
your voice into your Gmail Drafts and sends it to you with **Send / Edit / Discard**. **Nothing is sent unless you
tap Send.** Edit: say what to change ("say I can do 10am"); the AI rewrites the draft and asks again. Discard deletes
just that draft. Unanswered, it stays in your Gmail Drafts (the question expires after 3 days). Replies go only to
the sender of a mail in your digest, never to no-reply addresses or mail marked confidential (or on your never-read
list), at most 5 a day (`reply_drafts.per_day`). Needs the Mail digest. *Turn off:* Features → Email reply drafts → Turn off.

### Agent plan calendar
Kurooto makes a calendar of its own, **Agent plan**, in your Google Calendar, for the time blocks it plans with you:
the morning plan, or "block 2 to 4 for the problem set" on a call. It writes only to that calendar: Google's permission
for it covers only calendars Kurooto makes, so it can't see or change your others. Each block has a 5-minute
reminder (`agent_plan.remind_min`; 0 for none).
- `/blocks` shows today's blocks; `/blocks add 14:00-15:30 problem set 4` adds one; `/blocks clear` removes today's.
- Hide or delete the calendar in Google Calendar any time; Kurooto makes a new one the next time it plans something.
- To see the blocks in Kurooto's own Calendar feature too, add the Agent plan calendar's private iCal link there.
*Turn off:* Features → Agent plan calendar → Turn off (the calendar stays in Google Calendar until you delete it).

## Troubleshooting rows

| What you see | What to do |
|---|---|
| "Mail digest is paused: needs Google's OK" (or another Google feature) | Features → that feature → Save, then sign in with Google and leave its permission ticked. |
| A Google feature didn't turn on after signing in | Did you untick its permission on Google's screen? Save on its card again. Is its API on in your Google Cloud project (the link on its card)? |
| Google says "Access blocked" for a school account | Your school doesn't allow unverified apps for that permission. Use a personal Google account, or ask your school's admin. |
| The mail digest says it only counted my mail | It reads only what you chose: `/mail read @your-school.example` or `/mail read label:Name`. Mail marked confidential is always only counted. |
| Classroom notes say a PDF wasn't read | Install Poppler (`pdftotext`), or use agy as your AI (it opens PDFs itself). |
| Classroom notes went to the wrong folder | Settings → `classroom_notes.folders`: `{"Exact course name": "folder-name"}`. |

## CHANGELOG lines (0.2.0)

- Classroom → notes: three times a day, new Classroom materials, coursework, announcements and attached Drive files
  are filed into your notes by the AI (a note per lecture, a course page, an always-current exam-prep note that Quiz
  uses); dates in posts go into Deadlines; a skip list of courses (`/classnotes`).
- Mail digest: twice a day, new mail sorted into Needs action, People, Courses, Opportunities and Admin, with a copy in
  your notes and deadlines into Deadlines. It reads only the senders, domains and labels you choose (`/mail read`);
  everything else is only counted. Mail marked confidential (including standard confidentiality footers), and anything
  on your never-read list (`/mail never`), is never read, summarised or answered with an AI draft.
- Email reply drafts: the AI drafts replies to mail that needs one into Gmail and asks Send / Edit / Discard; nothing
  is sent without your tap.
- Agent plan calendar: time blocks Kurooto plans with you go into its own calendar in Google Calendar (`/blocks`, and a
  `plan_block` tool for calls and the morning plan); it can't touch your other calendars.
- Google: each new Google feature asks for its own permission when you set it up, and turns on by itself after the
  sign-in; a missing permission pauses only that feature, with a message saying how to fix it.

## PRIVACY rows (add to the "what leaves" table)

| Feature | What leaves your computer | Where to |
|---|---|---|
| Classroom → notes | Classroom posts and the text of their attached files, to write the notes | the AI service you picked; read from Google with your own client |
| Mail digest | the text of the mail you chose for the digest (senders, domains, labels you named; on a school or work account, your own domain). Other mail, mail marked confidential ("confidential", "do not forward", "restricted" or a standard confidentiality footer anywhere in its subject, text or labels) and your never-read list: nothing, they're only counted on your computer. Work or school mail may be covered by your institution's email policy; Kurooto never summarises mail marked confidential | the AI service you picked; read from Gmail with your own client |
| Email reply drafts | the draft reply, written into your Gmail Drafts; sent only when you tap Send | Google (your Gmail) |
| Agent plan calendar | the time blocks (title and time), in Kurooto's own calendar | Google (your Google Calendar) |

Also for PRIVACY.md, under Google: the add-ons' permissions are restricted to what each needs. Mail read access is
read-only; drafts/send access sends only on your tap; the calendar permission covers only the calendar Kurooto makes.
Copies kept on your computer: downloaded Classroom files (Kurooto's data folder, `classroom/`), and, until the digest is
written, the text of the mail you chose (state folder, `mail-digest/`; removed once the digest is done). Kurooto keeps
the sender, subject and a short excerpt of digested mail for 30 days so a reply draft can answer it.
