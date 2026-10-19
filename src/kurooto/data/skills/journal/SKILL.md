---
name: journal
description: Save what you did, thought and plan into today's daily note, in your own words, linked to the notes you mention.
effort: medium
args: your day, in your own words (name a date to journal another day)
---

A journal entry. Their words: $ARGUMENTS

The date is today, unless they name another day.

1. **Daily note** `journal/<YYYY-MM-DD>` (if it doesn't exist, create it with the first line `# YYYY-MM-DD`). Add a
   section `## Journal (HH:MM)` with their text **verbatim**: fix only obvious typos; keep their voice, their
   language and any mix of languages.
2. **Links.** After the journal text, under `## Links`, one line for each thing they mention that has a note (a
   subject's course page, a lecture, a project in `research/`, an idea), with the reason:
   `- [[linear-algebra/course]]: worked through the problem set`. Find the notes with search_notes and list_notes.
3. **Project logs.** If they worked on a project that has a note (in `research/` or elsewhere), add a line under that
   note's `## Log` section: `- **YYYY-MM-DD** | journal — <what happened, in one line>`, linking back to the daily
   note.
4. **Ideas.** Each new idea or question worth keeping becomes a short note `inbox/<idea-slug>`: the idea in their
   words, and a link back to the daily note. Link each one from the daily note's `## Links`.
5. **Tasks.** Things they finished: tick them (tick_task) where they already exist as `- [ ]` lines. New things to
   do: `- [ ] <what>` under `## Tasks` on the subject's course page `<subject>/course`, or in the daily note when
   there's no subject. With a due date, write `- [ ] <what> (YYYY-MM-DD HH:MM)` so Deadlines keeps track of it.
6. If they describe a class and send material, suggest `/study-log` for it instead of summarising the class here.

Reply in a few lines: what was saved, the links added, tasks ticked or added, ideas filed, and anything you left out
for privacy.
