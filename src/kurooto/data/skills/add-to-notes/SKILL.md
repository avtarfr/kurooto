---
name: add-to-notes
description: File anything into your notes (a PDF, slides, a photo of notes, a document, a link): it works out what it is and where it belongs, and writes a source note with links.
effort: medium
args: a link, or what the files are (send the files with it)
---

File this into their notes: $ARGUMENTS

1. **Read everything**: the files listed at the end, and the link. If something can't be read (a format you can't
   open), say which, and ask them to send it as a PDF.
2. **Work out what it is and where it belongs.**
   - kind: lecture notes or slides, their own notes (typed or handwritten), a problem set or solutions, a paper or
     book chapter, an exam or quiz, an article, or something else;
   - home: a subject (its folder, e.g. `linear-algebra/`), a project in `research/`, or neither (then `inbox/`).

   Use list_notes and search_notes to see what's already there on the topic. If the subject, kind or date is
   genuinely unclear, file it in `inbox/` and ask one short question in your reply, with your best guess.
3. **File it** as a new source note `<home>/<YYYY-MM-DD>-<slug>`, with `date` and `tags: [source, <kind>]` in its
   header, and these sections:
   - `## Covered`: faithful and exam-oriented: definitions, theorems with their hypotheses, formulas in LaTeX;
     nothing that isn't in the material. For a paper or article: authors, year, title and link first.
   - `## My notes`: if it's their own notes, their content verbatim (a careful transcription for handwriting).
   - `## Unclear / to ask`.
   - `## Files`: where the file is (its path in the notes folder), or the link.
   - `## Related`: links with a one-line reason each.
4. **Connect it.**
   - Up to 4 key ideas: link existing concept notes with a reason (search first), or create short concept notes in
     the subject's folder (one idea each, with a reasoned link back to the source note).
   - The subject's course page `<subject>/course`: the new note under `## Lecture notes` for lectures, or under
     `## Files` for anything else.
   - Facts worth revising: lines under `## Key ideas` in `<subject>/exam-prep` (add only that section; leave the rest
     of that note alone).
   - Deadlines in it: `- [ ] <what> (YYYY-MM-DD HH:MM)` under `## Tasks` on the course page.
   - Research material: a line under the project note's `## Log`: `- **YYYY-MM-DD** | <source> — <what it adds>`.
   - Today's daily note `journal/<YYYY-MM-DD>`: a line under `## Added` linking the new note.
5. Files stay where they are (files sent on Telegram are already saved in `inbox/`); don't copy them.

Reply in a few lines: what it was, where it went (notes created or added to), and anything they should check.
