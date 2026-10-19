# learning: docs to merge (0.2.0)

Modules: `Retro` (upgraded, `kurooto.modules.retro`), `Remember` (NEW, `kurooto.modules.remember`, id `remember`),
`GBrain` (upgraded). Register `Remember` in the catalog (suggested place: right before `Retro`) and add `"remember"`
to `web/api.py` MODULE_ORDER (before `"retro"`).

## MANUAL: Features

### Remember
Tell Kurooto how you like to be helped and it keeps it: `/remember I hate calls before 8`, or just say "remember that
I like a plan before 9" (on Telegram or on a call). It goes into your notes, in `about-me/how-to-help-me.md`, under
"You told me". That note is yours: read it, edit it, add your own lines. Kurooto never rewords or removes a line, and
what you write there wins. A short version of it goes along with every AI request Kurooto makes, next to the "In
brief" part of your profile. `/remember` on its own shows what it keeps.

It won't keep health, money or password details (they'd travel with every AI request); it says so and keeps nothing.
"Remember to buy milk" is a reminder, not this: use Reminders for that.

**Turn it off:** Features → Remember. The note stays in your notes; delete or edit it as you like. While the note
exists, AI requests still read it; delete the note to stop that.

### Nightly look back
Once a day (23:50) the AI looks at how the day went and suggests at most three small improvements, each with the
evidence behind it. It reads:
- what happened: the questions Kurooto asked you and your answers (and how fast, on which channel), check-ins you
  moved or skipped, calls you answered or missed, after-class prompts, deadlines, AI requests, study sessions;
- today's call transcripts and journal (both can be left out: `retro.transcripts`, `retro.journal`);
- your how-to-help-me note and the settings it may change.

A suggestion can be:
- **a setting**: a better check-in time, quiet hours, deadline nudges, quiz length, the after-class delay;
- **a line for your how-to-help-me note** (under "Learned in the nightly look back");
- **something to watch** for a while before deciding anything;
- **a change to one of your skills**: after you tap Apply, the AI writes the change and you see exactly what changes
  (lines removed and added) with **Save** / **Discard**. Saving writes your own copy of the skill in
  `kurooto/skills/<name>/SKILL.md` and keeps the old version in Kurooto's data folder (`backups/skills`). If you edited
  the skill in the meantime, nothing is saved;
- **an idea**: something new Kurooto could do for you, added to `kurooto/ideas.md` in your notes.

Answer each with **Apply**, **Observe longer** or **No** (buttons, a reply, or on your next call; **Later** keeps it
for the call). Apply does it at once; nothing changes without your tap. **No** drops that idea (however it's worded
next time) for 30 days. **Observe longer** watches it for a week first (reply "observe 14" for 14 days); when the
watching ends, the next look back tells you what it found.

**Steer it:** `/observe whether I study better before noon for 2 weeks` (or say "observe whether ..." / "keep an eye
on ...", or ask on a call). `/observing` lists what's being watched, each with a **Stop** button. When a watch ends you
get a message with what it found. `/lookback` shows the last look back (and what it noticed); `/lookback now` runs one
now.

**Settings** (`retro.*`): `when` (`daily 23:50`; `weekly sun 21:00` looks back over the whole week), `max_proposals`
(3), `observe_days` (7), `no_days` (30), `transcripts` (on), `journal` (on). The look back's instructions are the
`retro` skill: put your own copy in `kurooto/skills/retro/SKILL.md` to change how it thinks (it's not a command).

**Turn it off:** Features → Nightly look back. Waiting suggestions stay answerable for three days.

### Notes brain (GBrain): add after the current text
Three more things, each with its own switch in Settings (`gbrain.*`):
- **Timelines** (on, `gbrain.timelines`): every night, dated log lines in your notes, written like
  `- **2026-10-19** | source — what happened`, become each note's timeline. `/timeline research/reading-group` shows
  one; your AI uses them for "when did I last ...?". Kurooto's own skills write their log lines this way. No AI is
  involved and nothing leaves your computer.
- **Nightly upkeep** (off, `gbrain.upkeep`): GBrain's maintenance cycle at 03:00 (`gbrain.nightly`), light steps
  only: links, facts, timelines, the index, orphaned pages. Steps that would rewrite your note files or call an AI
  model are left out. It's heavy, so on a laptop it waits for the charger. If it fails you're told once (with where
  its log is), not every night.
- **Weekly checkup** (off, `gbrain.checkup`): GBrain's own advisor, Sundays at 19:30 (`gbrain.checkup_when`). You get a
  message only when something is a warning or worse, with **Ignore these** (adds them to `gbrain.checkup_ignore`) and,
  when the brain needs a schema update, **Update the brain**.

## MANUAL: Troubleshooting rows

| What you see | What to do |
|---|---|
| "I'd rather not keep that" after /remember | It looked like a health, money or password detail. Put it in your own notes instead; reword it if it isn't one. |
| The look back never suggests anything | Most days that's right. `/lookback` shows when it last ran and what it noticed; on a laptop it waits for the charger. `/lookback now` runs one. |
| A skill change says "nothing changed" | The AI's version was the same, or it broke the skill's header; it's never saved then. It may suggest it again another night. |
| The nightly upkeep didn't finish | Search still works. Its log is in the state folder (`gbrain/upkeep-<date>.log`); it tries again the next night. Turn it off with `gbrain.upkeep`. |
| /notes or /timeline says the brain is busy | The nightly upkeep (or a sync) is using it; try again in a while. |

## CHANGELOG lines (0.2.0)

- Remember: `/remember`, "remember that ...", and on calls; kept in your notes (`about-me/how-to-help-me.md`, which you
  edit and which wins), and a short version goes along with every AI request. Health, money and passwords are refused.
- Nightly look back: reads your answers to Kurooto's questions, check-in moves and skips, call transcripts and the
  journal; suggests settings, how-to-help-me lines, things to watch, skill changes (shown before saving, with a
  backup) and ideas (`kurooto/ideas.md`). Apply / Observe longer / No; No keeps an idea away for 30 days.
- `/observe`, `/observing` (with Stop), "observe whether ... for 2 weeks", and on calls; a finding when the watch ends.
  `/lookback` shows the last look back; `/lookback now` runs one.
- Notes brain: timelines from dated log lines (`/timeline`, and a tool for the AI); optional nightly upkeep (light
  steps only, on the charger) and a weekly checkup that only speaks up when something needs a look.
- Fix: the notes brain's 15-minute sync no longer holds up the rest of Kurooto while it runs, and skips a turn when the
  brain is busy instead of waiting. GBrain no longer checks for its own updates (Kurooto pins its version).

## PRIVACY notes

Replace the "Nightly look back" row with:

| Nightly look back | what happened (events: what you answered, moved, skipped, and when), Kurooto's questions and your answers, today's call transcripts and journal (each can be left out), your how-to-help-me note and the values of the settings it may change; for a skill change you approved, that skill's text | the AI service you picked |

Add a row:

| Remember | your how-to-help-me note (`about-me/how-to-help-me.md`) goes along with every AI request, like the profile's "In brief" part; health, money and password details are refused, never stored | the AI service you picked |

GBrain row: add "The nightly upkeep and timelines don't add anything: the upkeep's index step sends note text to
Google only if your index already uses Gemini. Kurooto turns off GBrain's own update check, so GBrain makes no calls
to its release page." Add to the "nothing leaves" list: timelines, the weekly checkup.

## For the coordinator

- New events: `remembered(chars, via)`, `remember_refused(what, via)`, `observe_added(id, days, source)`,
  `observe_stopped(id)`, `observe_ended(id, found)`, `retro_proposed(type)`, `retro_answer(type, answer)`,
  `retro_applied(type, key)`, `retro_failed(reason)`, `retro_ran(proposals, findings)`, `skill_edited(name)`,
  `gbrain_timelines(ok, entries)`, `gbrain_upkeep(ok, status, failed, seconds)`, `gbrain_checkup(ok, items)`.
  `web/live.py` EVENT_CELL could map `observe_` → retro and `remember` → remember.
- The call's system instruction (calls `config_template`) doesn't include the profile brief or the how-to-help-me
  note; adding `help_brief(app)` there would let calls follow "remember that ..." too (it goes to Google with the call
  setup, so it needs a PRIVACY line).
