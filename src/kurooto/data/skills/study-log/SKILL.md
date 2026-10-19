---
name: study-log
description: Turn a day of classes into notes: one lecture note per class from the slides and your own notes, linked to the subject and today's daily note.
effort: high
args: which classes you had, plus your notes (send slides or photos with it)
---

Log classes into their notes. What they gave you: $ARGUMENTS

The date is today, unless they name another day. Files they sent are listed at the end, if any.

Each subject has a folder named by its slug (e.g. `linear-algebra/`) with a course page `<subject>/course`. Short
names they use ("LA", "stats") usually match a folder or a course page's title; find them with list_notes and
search_notes. If a subject has no folder yet, create its course page `<subject>/course` with the first line
`# <Subject name>`.

For each class:

1. **Read everything given for it**: the slides and photos they sent, their typed notes, and handwritten notes in
   `handwritten/` they mention. If a file can't be read, or it's unclear which subject a class is, say so instead of
   guessing.
2. **Lecture note** `<subject>/<YYYY-MM-DD>-<topic-slug>` (a new note), with `date: YYYY-MM-DD` and
   `tags: [lecture]` in its header, and these sections:
   - `## Covered`: what the class covered, faithfully: definitions, theorems with all their hypotheses, formulas in
     LaTeX (`$…$`, `$$…$$`). Nothing that isn't in what they gave you.
   - `## My notes`: their own notes, verbatim.
   - `## Unclear / to ask`: open questions from their notes, or gaps in the material.
   - `## Files`: the files' paths in the notes folder.
   - `## Related`: links with a reason each (the course page, the previous lecture, concept notes).
3. **Concepts.** For up to 3 key ideas, search_notes for an existing note first. If there is one, add a line under
   its `## Links` pointing to the new lecture note, with the reason. If not, create a short concept note
   `<subject>/<concept-slug>`: the idea in plain words, `## Links` with at least one reasoned link, and the last line
   `Source: [[<the lecture note>]]`. Look for links to other subjects and to `research/`: those cross-links are the
   point.
4. **Course page.** Add the lecture under `## Lecture notes` on `<subject>/course`:
   `- [[<subject>/<YYYY-MM-DD>-<topic-slug>]]: <topic, one line>`. Homework or deadlines they mention go under
   `## Tasks` as `- [ ] <what> (YYYY-MM-DD HH:MM)`.

Then the daily note `journal/<YYYY-MM-DD>` (create it with the first line `# YYYY-MM-DD` if it's missing): one line
per class under `## Studied`, linking its lecture note.

Don't copy files into the notes; link them where they are.

Reply with one line per class: the lecture note, concept notes created or linked, tasks added.
