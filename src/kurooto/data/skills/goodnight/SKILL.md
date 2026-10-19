---
name: goodnight
description: End the day: sets the wake-up alarm and notes anything for tomorrow, without a long summary.
effort: low
args: when you'll wake up, and anything for tomorrow
---

They're going to sleep. What they said: $ARGUMENTS

1. **Wake-up time.** Take it from what they said ("7:30", "6:45 tomorrow", "in 7 hours"). If they didn't give one,
   don't guess: ask for it in your reply.
2. **Set the alarm** with set_alarm and pass on exactly what it says. Without that tool, tell them the Alarm feature
   is off (they can turn it on in Settings).
3. **Tomorrow.** If they mentioned anything for tomorrow (a moved class, a meeting, the one thing that must get done,
   something to remember), add it in their words under `## From last night` in tomorrow's daily note
   `journal/<tomorrow's date>` (create it with the first line `# YYYY-MM-DD` if it's missing). If they didn't
   mention anything, ask in one line, only if their notes don't already say: anything fixed tomorrow, and the one
   thing that must get done? (They answer by replying.)
4. If today's daily note has no journal entry yet, offer /journal in one short line.
5. Close in one line with the alarm time. No summaries at bedtime.

Don't write sleep or health details into the notes.
