---
name: assignment
description: Work through an assignment or problem set: every question, complete worked solutions in your course's notation, a confidence for each, saved to your notes.
effort: high
args: which assignment (send the sheet, or name the subject and which one)
---

Work through this assignment: $ARGUMENTS

1. **Find it**, in this order: a file or link they gave (listed at the end); a note in the subject's folder with the
   questions (search_notes for "assignment", "homework", "problem set" and the number they named); the `## Tasks` on
   the subject's course page `<subject>/course`. If they didn't say which, take the subject's nearest upcoming due
   date and say which one you picked.
2. **Read every question.** Copy each problem statement verbatim, sub-parts included. If a page is unreadable, say
   which.
3. **Solve it the way the course teaches it.**
   - First read the subject's lecture notes, concept notes and `<subject>/exam-prep` for the definitions, theorems and
     notation the course uses, so the solutions match what's taught. Cite the course result you use.
   - Proofs: complete and rigorous. Check every hypothesis of every theorem you apply; no hand-waving at the hard
     step.
   - Computations: show the working, and check the answer another way (a special case, a limit, units, a rough
     bound).
   - Give each question an honest confidence: high, medium or low. For anything low, say exactly which step is shaky.
4. **Write it down.**
   - A new note `<subject>/<due date or today>-<slug>-solutions`, with `tags: [solutions]` and `due:` in its header.
     Per question, `## Q<n>` with **Problem** (verbatim), **Solution**, **Key idea** (one line: the trick that
     unlocks it) and **Check**. Then `## Related`: the notes you used, each with a reason. Last, `## LaTeX`: the whole
     solution set as one ```latex block (article class with amsmath, amssymb and amsthm; a section per question), so
     they can compile it.
   - On the course page, under `## Tasks`, a line "solutions drafted: [[<the solutions note>]]". Don't tick the
     task: they hand it in themselves.
   - Each key idea worth remembering: a line under `## Key ideas` in `<subject>/exam-prep` (add only that section).
   - A line under `## Added` in today's daily note `journal/<YYYY-MM-DD>`.
5. **Reply** briefly: what the assignment was and when it's due, where the solutions are, and per question the
   confidence and anything to check before handing it in. Add one line reminding them to follow their course's rules
   on AI help.
