# skills: what to merge into the docs

## MANUAL: new feature sections (put them after "Files into notes")

### Skills
Ready-made instructions for your AI, one command each. Type `/<skill>` and what it's about; the answer comes back as
a reply, and you can **reply to that answer** to carry on (answer its questions, ask for a change). Files you send
with the command (as the caption) go along. `/skills` lists them all; `/skills journal` shows one.

| Skill | What it does |
|---|---|
| `/journal <your day>` | Saves your words, as you wrote them, in today's daily note (`journal/YYYY-MM-DD.md`), and links the notes you mention, ticks tasks you finished, files new ideas in `inbox/`. |
| `/study-log <classes and notes>` | One lecture note per class (`<subject>/YYYY-MM-DD-<topic>.md`) from your slides and notes, linked from the subject's course page and today's daily note. |
| `/add-to-notes <link or files>` | Files anything (PDF, slides, photo of notes, a link) where it belongs, as a source note with links. A link sent on its own is filed this way too. |
| `/assignment <which one>` | Worked solutions in your course's notation, a confidence for each question, saved as a note. Check them and follow your course's rules on AI help. |
| `/connect-notes [topic]` | Finds real connections between notes and adds them as links, each with its reason. |
| `/term-setup <subjects, plans>` | Sets up a term from what you say and your academic calendar: key dates, course pages, a week-by-week plan; it asks what it can't find (reply to answer). |
| `/goodnight <wake-up time>` | Sets the alarm (with Morning alarm on) and notes anything for tomorrow. |
| `/morning [answers]` | Today's plan, time-blocked, with your top 3. |
| `/morning-prep` | Drafts today's plan before you wake (other features run it for you). |
| `/pack <subject> [what for]` | A revision pack as a PDF (see below). |

**Your own skills.** `/newskill <what it should do>`: the AI writes a skill and sends it to you in full; **Save** puts
it in your notes (`kurooto/skills/<name>/SKILL.md`), **Discard** throws it away. Nothing is saved without your tap.
To change a skill that comes with Kurooto, `/skills copy journal` makes your own copy in that folder; edit it there
(your copy replaces Kurooto's for you; delete your copy to go back). A prompt in your prompt library with
`skill: true` in its header is a skill too.

**On a schedule.** `/every monday 9:00 /journal plan my week`, `/every weekdays 7:30 /morning-prep`,
`/every daily 21:00 how did today go?` (a request for the AI), or any command (`/every friday 18:00 /week`). Days:
`daily`, `weekdays`, `weekends`, a day, or several (`mon,thu`). Plain English works for requests: "every friday at
6pm send me a summary of my week". `/routines` lists them, each with a **Cancel** button. One that came due while the
computer was off runs once when it's back (if that's still one of its days).

**Revision packs.** `/pack linear algebra midterm friday` reads that subject's notes (course page, exam prep, lecture
notes, solutions) and builds a 2–6 page pack: what's on it, definitions, theorems with their hypotheses, formulas,
worked problems, pitfalls and a self-test with answers. It's saved in your notes (`<subject>/revision-pack-<date>.tex`
and `.pdf`) and sent to Telegram. PDFs need **Tectonic**, a small LaTeX engine: the first pack without it comes as a
`.tex` file with an **Install Tectonic** button (about 25 MB, from Tectonic's official releases; the first PDF then
takes a few minutes while it fetches about 50 MB of LaTeX packages into Kurooto's cache). If a pack doesn't compile,
the AI gets one try to fix it; otherwise you get the `.tex`.

*Needs:* Chat. *Settings:* none. *Leaves your computer:* what you send with a skill, and the notes it reads, go to the
AI you picked. *Turn it off:* Features → Skills; your own skills, routines and packs stay (routines start again when
you turn it back on).

The rules every skill follows: it only creates notes or adds to them (never rewords or deletes your text), puts your
own words in verbatim, gives every link a reason, keeps health, money and other people's private details out of your
notes, and sends nothing to anyone but you.

### Quick notes and prompts
`/note <text>` saves it straight into your notes' inbox (`inbox/YYYY-MM-DD-<first words>.md`), as written; a photo or
file with `/note` as its caption is linked from the note. From a terminal: `kurooto note "an idea"` (or pipe text in:
`some-command | kurooto note --title "output"`); this works even when Kurooto isn't running.
Your prompt library is the `prompts/` folder in your notes (Markdown files, subfolders allowed): `/prompts` lists it,
`/prompt <name>` sends one back to copy, `/prompt save <name>` with the prompt on the next lines adds one.
*Needs:* Telegram. *Leaves your computer:* nothing (no AI involved). *Turn it off:* Features → Quick notes and
prompts.

### Files to you (add to "Other programs can message you")
`kurooto send report.pdf --caption "This week's numbers"` sends a file from this computer to your Telegram (up to
50 MB). It needs Kurooto running and Telegram set up (exit code 2 when it isn't running). With Skills on, the AI can
send you files from your notes folder too ("send me my linear algebra pack"), on calls as well; it can't send files
from anywhere else.

## Troubleshooting rows
| What you see | What to do |
|---|---|
| `/journal` (or another skill) goes to Chat as plain text | Turn on **Skills** (Features). `/skills` lists the names. |
| A revision pack comes as a `.tex` file | Tectonic isn't installed: tap **Install Tectonic** under the pack (or send `/pack` again and tap it). |
| The first PDF takes minutes | Tectonic fetches the LaTeX packages it needs once (about 50 MB); later packs take seconds. |
| "it didn't compile" | The AI's LaTeX had an error it couldn't fix; the `.tex` is in your notes. `/pack` again, or reply with what to change. |
| A routine didn't run | It runs when the computer is on; one missed while it was off runs once when it's back (if that's still one of its days). `/routines` shows what's set. |
| `kurooto send` says it isn't running | `kurooto on`, then try again. |

## CHANGELOG lines (0.2.0)
- Skills: `/journal`, `/study-log`, `/add-to-notes`, `/assignment`, `/connect-notes`, `/term-setup`, `/goodnight`,
  `/morning`, `/morning-prep`, and `/skills` to list them; reply to a skill's answer to carry on. A link sent on its
  own is filed into your notes.
- Your own skills: `/newskill` (the AI writes one; you see it in full and tap Save), `/skills copy <name>` to change a
  shipped one, and prompts marked `skill: true`.
- Routines: run any skill, command or request on a schedule (`/every monday 9:00 /journal plan my week`,
  "every friday at 6pm ..."), `/routines` with Cancel buttons.
- Revision packs: `/pack <subject>` builds a PDF from your notes (with Tectonic, an optional LaTeX engine Kurooto can
  install for you).
- Quick notes and prompts: `/note`, `kurooto note`, `/prompts`, `/prompt`, `/prompt save`.
- `kurooto send FILE`: a file from this computer to your Telegram; the AI can send you files from your notes.

## PRIVACY rows (the "Always" table)
| Feature | What leaves | Where to |
|---|---|---|
| Skills | what you send with a skill and the notes it reads; for `/newskill`, your description and the names of your tools and skills | the AI service you picked |
| Skills: revision packs | Tectonic (if you install it) downloads LaTeX packages; nothing of yours is sent | Tectonic's package server (public) |
| Quick notes and prompts | nothing | stays on your computer |
| `kurooto send` / the send_file tool | the file | Telegram (to your own bot) |

Add "Quick notes and prompts" to the "nothing leaves" row.

## For the coordinator
- Register in catalog.py: `from kurooto.modules.skills import Skills` and `from kurooto.modules.library import Library`
  (Skills after Files; Library after Skills), and add "skills", "library" to `MODULE_ORDER` in web/api.py (the
  dashboard only shows modules listed there).
- Suggestion (not done, files.py isn't mine): with Skills on, `Files.take_files` could run the add-to-notes skill
  (`app.modules["skills"].run("add-to-notes", caption, reply_to=..., files=msg.files)`) so photos and PDFs are filed
  the same way as links.
