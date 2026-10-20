---
name: hint
description: A hint ladder for one problem: the idea, the setup, the key step, and the full solution, shown one at a time by /hint.
effort: medium
args: the subject, then the problem (or send it as a photo with /hint as the caption)
internal: true
---

Make a hint ladder for one problem, for a student working on it themselves. What they gave you: $ARGUMENTS

The problem is in the photo or file listed at the end, or typed above. Kurooto shows your hints one at a time and the
full solution only when they ask for it, so write each step so it gives away no more than its own part.

1. **Read the problem.** Copy nothing into their notes. If you can't read it (a blurry photo, a missing page), reply
   with only `UNREADABLE: <what you couldn't read>`.
2. **Find the lecture note it belongs to**, in the subject's folder `<subject>/` (search_notes, list_notes, read_note):
   the class where its topic was taught. Use the course's definitions and notation from it in every step.
3. **Follow the course's AI policy** given above. If it says no full solutions, write `(not given: the course's AI
   policy)` as the solution. If it says no AI help at all, reply with only `REFUSED: <the policy>`.
4. **Reply in exactly this form** (plain text, maths in LaTeX between `$`), and nothing else:

```
NOTE: <the lecture note's path inside the notes folder, without .md; or none>
IDEA: <one or two sentences: which idea or theorem unlocks it, without applying it>
SETUP: <how to start: what to define, assume or write down first; not the key step>
KEY STEP: <the step where it turns, done in enough detail to finish from there>
SOLUTION: <the complete solution, every step justified>
```

Don't write or change any notes, and don't add anything before or after these lines.
