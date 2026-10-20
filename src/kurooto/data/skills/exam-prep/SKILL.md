---
name: exam-prep
description: Bring a subject's exam prep up to date from everything there is: your own class notes, Classroom materials and your books, in the mix you chose, every point cited.
effort: high
args: a subject, and optionally which exam or which topics
---

Bring the exam prep up to date for: $ARGUMENTS

1. **The subject.** Find its notes folder with list_notes and search_notes (short names like "LA" usually match a
   folder or a course page's title). Read `<subject>/course` (`## Exams`, `## Lecture notes`) and `<subject>/exam-prep`
   if they exist. If the subject is unclear, say so and stop.
2. **Scope.** The exam they name, else the next one under `## Exams`, else everything covered so far. Make a list of
   its main topics from the course page's lecture notes (at most 8).
3. **Sources.** With the course_sources tool, call it for the subject and each main topic (at most 6 calls). It
   returns their own notes, Classroom materials and their books (by page), in the shares they chose, each part
   labelled with how to cite it. Use the sources in about those shares. Their own notes and the class come first:
   where a book differs (notation, a definition's conditions), follow the class and give the book's version with its
   page. With read_book you may read a few more pages around a cited one (a theorem's full statement, an example).
   Without course_sources, read the lecture notes and their notes on each topic yourself.
4. **Write it** with update_exam_prep (subject = the notes folder), in these sections:
   - `## Next assessment`: what and when, or "not announced yet".
   - `## Covered so far`: the lecture notes in order, one line each with the main topic, as links.
   - `## Must know`: one bullet each, a definition or result stated exactly with all its conditions, then its source
     in brackets: (book: <title>, p. 123), (Classroom: <post>), (your notes: [[<note>]]). The quiz asks these one by
     one, so each bullet stands on its own.
   - `## Typical questions`: problem types from coursework, examples and the book's exercises, each with where to
     practise (a note, or book pages).
   - `## Gaps`: topics in scope with no notes yet, places where the sources disagree, anything unclear.

   Only material from the sources and standard facts of the subject; nothing invented. Without update_exam_prep,
   add the same sections under a new heading `## Exam prep (YYYY-MM-DD)` at the end of `<subject>/exam-prep` with
   add_to_note (create the note with write_note if it's missing).

Reply in a few lines: the assessment and its date if known, how many must-know points, which sources you used (and
their shares), and the gaps.
