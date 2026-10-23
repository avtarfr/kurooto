# Roadmap

Ideas that aren't built yet. Nothing here is promised; each one ships as an opt-in feature through the normal
signed updates when it's ready.

## Next
- **Learns from its own work.** In the spirit of Hermes Agent (Nous Research, MIT licence; any code adapted from
  it keeps its copyright and permission notice):
  - after a request that took many steps, Kurooto offers to save how it did it as a skill;
  - it improves a skill when you correct its result;
  - it can search its memory of past requests and calls;
  - now and then it suggests what's worth remembering.

  As everywhere in Kurooto, nothing changes without your tap.
- **Your notes, your layout.** Choose where Kurooto writes: the daily note, subject folders, the inbox, your
  profile. It then fits an existing notes system instead of bringing its own.

## From the ideation panel (2026-10-23)
Seven viewpoints (student, researcher, notes, phone, AI, friends, skeptic) argued these out; the most backed first.
- **Link recall cards.** The concept graph's links become review cards ("how does Itô's lemma relate to
  Fokker–Planck?"), answered in your own words and graded by you (a small local model may check, never the free
  key). A miss points to the book pages. Up to five a day, also as phone notifications, never in class or focus.
  Papers opened from the research digest go through Books into the graph and get the same cards.
- **Revision plan.** When exam season starts, a course's topics are ranked (no note, stub, weak recall, the rest)
  and laid over Start-by's free slots with the pages to read; the evening check-in asks "did you cover X?" and feeds
  the same recall score as the quiz. Plain arithmetic, no AI.
- **Turn on from chat.** A message that needs a feature that's off ("wake me at 7") offers [Turn on] [Not now]; one
  tap turns on it and what it needs, then does the original request.
- **Run receipt.** Every AI answer ends with one grey line built from the tool log, not the answer's words: brain,
  effort, time, share of today's limit, and what it actually did ("did nothing" when it did nothing).
- **/fixme that works when the AI is what broke.** Doctor's symptoms matched by rules to the manual's
  troubleshooting and a signed known-issues list shipped with releases; Fix buttons run `doctor --fix`; your AI only
  explains, if it answers.
- **Keep or drop.** A local count of what you actually use per feature; on day 10, Keep / Quiet / Off per feature,
  then monthly for features unused for 60 days that still run jobs. Never switched off without asking.
- **Egress ledger, enforced.** Every request Kurooto makes goes through one place that records host, feature and
  bytes and blocks hosts not listed in PRIVACY.md; `/egress` shows the week. Requests your AI program makes itself
  show as "handed to agy / Claude Code".
- **Retention.** `privacy.keep_days` (30) expires transcripts, prompts, answers, audio and logs, also the call
  line's queued copies; `/forget 7d`.
- **Problem-set progress.** Deadlines with parts (Q1–7): reply "4/7" or tap +1 on the phone; Start-by plans from
  what's left; the morning says "ps3 4/7, due Fri".
- **Phone outbox.** Captures and taps made while the laptop sleeps wait on the call line and merge on wake; a home
  screen widget and a capture tile (launcher shortcut on Android 6).
- **iPhone Shortcut.** Pairing an iPhone ends with a ready "Tell Kurooto" Shortcut (Siri, Back Tap) with a
  revocable link.
- **CPU micro-helper.** A ~1 GB model for one-word decisions only (effort, intent, yes/no) on laptops without a
  graphics card, enabled only if a speed test passes, offered after week 2 when the free limit is being used up.
- **Notation crosswalk.** When a concept appears in a second source, its notation and conventions are written side
  by side (B_t vs W_t, Fourier 2π), quote-checked like every graph claim.
- **Near-duplicate concepts.** "Wiener process" and "Brownian motion": Merge / Keep both / Add alias.
- **Supervisor meeting brief.** The evening before a tagged meeting, a page from the project log since the last
  one; after it, a voice note becomes minutes, and action items become deadlines on a tap.
- **Run compare.** `kurooto runlog diff A B` and `/runs compare`: config differences, code diff, metrics and loss
  curves side by side, written to the project's notes.
- **LaTeX writing tracker.** Nightly build of your `.tex` repos: errors, undefined references, missing citations
  (BibTeX suggested, you approve), words added.
- **Check my attempt.** A photo of a proof (or a `.tex` derivation) before you submit: gaps marked, nothing
  rewritten; a course's AI policy can turn it off.
- **Missed-class catch-up.** Skipping a class makes a catch-up item with that day's Classroom posts and a note stub.
- **Bedside mode.** An old Android phone as a dock: clock, today, alarm, a talk button.
- **Add-ons by link.** `kurooto addons add <git url>`: a manifest card first, consent for code, pinned to a commit.

## Ideas
- **Offline fallback.** When the internet drops, a small model on your computer answers quick things and queues the
  rest.
- **An email-in address.** Forward a notice or a receipt to your own call line, and it's filed in your notes or
  becomes a deadline.
- **Zotero.** A paper from the research digest goes into Zotero with one tap, and reading notes link to it.
- **Photo → dates.** Share a photo of a notice or a timetable from your phone, and the events and deadlines are
  pulled out.
- **Shared class lists.** Friends in the same course can opt in to share deadlines and exam dates.
- **Quick-ask hotkey.** A small prompt window on the desktop, on every system.
- **Location reminders on Android.** "When I reach the library", without draining the battery.
- **Course notes to PDF.** A LaTeX template for course notes.

What people have asked for, open and done, is in [REQUESTED.md](REQUESTED.md). Have an idea? Open an issue on GitHub.
