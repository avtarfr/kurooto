# Changelog

## 0.1.3 (2026-10-20)
- Telegram setup: if pressing Start doesn't connect, the page now says why (another program using the bot, a
  webhook, a revoked token, an expired link, no internet) and offers the fix, and it always shows the message to send
  by hand. Running setup again while Telegram is on no longer swallows the Start message.

## 0.1.2 (2026-10-20)
- "Build my profile" and other text-only work no longer fail with agy: it's told to answer with text only.
- If agy can't do something unattended (or fails), a saved Gemini key answers instead, and the other way round when
  you've set up both. A line at the end says which AI answered.
- Without a Gemini key, the message says exactly what to do instead of a vague refusal.
- Long requests reach agy through a file, so profile builds work on Windows too.
- The setup page recommends the Gemini key first (★); agy is second, with a plain note about it.

## 0.1.1 (2026-10-20)
Fixes, delivered as the first automatic update.
- A check-in call that comes due during a class, a hold, focus or the night now waits until the block ends, or comes
  as a message if that's too late for today.
- What you say on a check-in call reaches your journal again.
- Checking Kurooto (`kurooto doctor`) while the AI is working no longer makes that request run a second time.
- A landing page at avtarfr.github.io/kurooto.

## 0.1.0 (2026-10-19)
The first release, for friends.
- One-line install on Windows, macOS and Linux (per user, no admin), signed releases, a setup wizard that reads the
  computer and recommends settings, and installs what each feature needs (with a storage check).
- AI brains: Antigravity (agy), Gemini key, ChatGPT/Codex, FreeLLMAPI, Ollama, any OpenAI-compatible service, and
  Claude Code (Advanced); a fallback brain; effort picked per request.
- Features (all opt-in): Telegram, Chat, Reminders, Check-ins (by message or call), Deadlines, Subjects and timetable,
  Quiz, Weekly summary, Files into notes, Notes brain (GBrain), Local AI models, After-class notes, Nightly look back,
  Phone calls (your own call line; Android app; iPhone web app), Morning alarm, Voice notes, Stay awake on charger,
  Calendar, Notes sync, Google (Classroom, Gmail drafts), Handwritten notes, Study tracker, Research (a digest of new
  papers from arXiv's 155 fields, bioRxiv, medRxiv, PubMed and any feed, with its own dashboard tab).
- About you: prompts to run in all your other AI accounts, their reports brought into Kurooto, and a profile built
  from them that every AI request starts from.
- A local dashboard; `kurooto doctor` and a redacted diagnostics bundle.
- Laptops: a battery saver (Telegram keeps working; heavy work waits for the charger and runs when plugged in),
  `/pause` and `/resume`, and `kurooto off` / `on` (with a Kurooto entry in the app menu to turn it back on).
- Automatic, signed updates with rollback.
