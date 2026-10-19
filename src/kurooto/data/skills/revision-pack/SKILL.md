---
name: revision-pack
description: A revision pack for a subject's next quiz or exam, as a PDF from your notes: definitions, theorems, formulas, worked problems, pitfalls and a self-test with answers.
effort: high
args: a subject, and which quiz or exam it's for
output: latex
---

Build a revision pack: $ARGUMENTS

1. **Scope.** Work out what this assessment covers: the subject's course page `<subject>/course` (`## Exams`, the
   lecture notes since the last quiz or exam, any syllabus), its `<subject>/exam-prep`, and what's due soon. If the
   scope is unclear, cover the material since the previous assessment and say so on page 1.
2. **Gather** with search_notes and read_note: `<subject>/exam-prep` (must know, typical questions, gaps, key ideas),
   the lecture notes in scope and the concept notes they link, recent solutions notes (`*-solutions`), and weak
   topics from quiz results if you have a quiz tool.
3. **Write LaTeX**: one complete document.
   - Format: `\documentclass[10pt]{article}`, `geometry` with 1.6cm margins, `amsmath`, `amssymb`, `amsthm`,
     `enumitem`, compact spacing. Two columns only if it really helps. Standard packages only: no shell escape, no
     external files or images.
   - Length: as long as the material needs, usually 2 to 6 pages; dense, no padding, no repetition.
   - Sections:
     1. **What's on it**: the assessment, its date and scope, in 3 lines.
     2. **Definitions**: precise, in the course's notation.
     3. **Theorems**: the exact statement with all hypotheses; a one-line proof idea; a counterexample when a
        hypothesis is dropped, if the course uses one.
     4. **Formulas and facts** to have at your fingertips.
     5. **Typical problems**: 3 to 6, each with the key step and a short worked solution.
     6. **Pitfalls**: the mistakes worth avoiding, and the weak topics.
     7. **Self-test**: 6 to 12 questions, with the answers on the last page.
   - Cite the source note for each block in small text, e.g. `\textit{(from lecture 2026-10-12)}`.
   - Only material from their notes and standard facts of the subject; nothing invented.
4. **Answer** with the whole document in one ```latex block (from `\documentclass` to `\end{document}`), then one
   line saying what it covers. Don't create files yourself: Kurooto saves the .tex in their notes, compiles the PDF
   and sends it to them.
