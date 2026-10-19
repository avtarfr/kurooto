# Changelog

## 0.1.6 (2026-10-20)
- Setting up local AI models on Linux could get Kurooto killed for running out of memory: Ollama's download was
  unpacked in memory. It's now unpacked straight from disk, and the space check counts Ollama's real size.
- Setup: click anywhere on a feature card to tick it, and the boxes are bigger.
- A request to the AI could now and then vanish or fail when the setup page or the dashboard checked on it at the
  same moment (mostly on Windows).
- `kurooto start` works on computers where systemd's user session doesn't (WSL, containers).

## 0.1.5 (2026-10-20)
Everything since 0.1.1, in one update.
- **`kurooto stop` didn't stay stopped** on Linux and macOS (the background service restarted it 10 seconds later),
  and `kurooto start` / `on` could start a second copy beside it: both now go through the service manager.
- **`kurooto` was an "unknown command"** on computers that already had uv: Kurooto now puts its folder on the PATH
  (your user PATH on Windows, fish, bash and zsh) when it installs and whenever it starts, and the installer says
  how to use it in the terminal you installed from.
- **Telegram setup could wait forever** after pressing Start: the page now says why (another program using the bot,
  a webhook, a revoked token, an expired link, no internet), offers the fix, and always shows the message to send by
  hand. Running setup again while Telegram is on no longer swallows the Start message.
- **"Build my profile" failed with agy**: text-only work now tells agy to answer with text only.
- **agy and a Gemini key back each other up**: if one can't do something (refused, limit reached, signed out,
  failed), the other answers, and a line at the end says which. Without a Gemini key, the message says what to do.
- Long requests reach agy through a file, so profile builds work on Windows too.
- About you: the profile is editable right after **Build my profile**, on the setup page, with a preview of the
  In-brief part that goes along with every AI request; saving keeps the previous version. Building again asks first if
  you've edited it, and never replaces an edit made while it was building. `/aboutme` shows the In-brief part.
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
