# rehearsal: fixes from the 0.1.5 -> 0.2.0 upgrade rehearsal and a fresh-install walkthrough

Found by installing the real 0.1.5 from the live site in a sealed sandbox, giving it a realistic setup, updating it to
a locally signed 0.2.0 with `kurooto update --now`, rolling back, and walking a fresh 0.2.0 install through the setup
page's API with a fake Telegram and a fake Gemini-key AI.

## CHANGELOG
- Setup page: the "When this laptop is on battery" choice is saved again (it was refused), and Settings can change it.
- The dashboard keeps its address after a quick restart or an update, instead of moving to the next port while the
  old one is still closing (macOS and Linux).
- `kurooto stop` stops Kurooto the normal way first (Notes sync sends up what's left), then forces what's left.
- After `kurooto update --now`, or after an update was rolled back, the dashboard no longer says "update ready".
- When an update keeps crashing and Kurooto goes back to the version before, you get one message saying so.
- The 05:10 call-line update after an update never opens a Cloudflare sign-in page by itself; if the sign-in has
  expired, you get a message instead (calls keep working on the old version).
- "Overdue?" messages no longer say "Overdue?" twice.
- Kurooto's job and schedule databases are readable by your account only, like its other state files.
- The installer starts Kurooto without the installer's temporary Python environment on its PATH.
- Tests and rehearsals (KUROOTO_NO_AUTOSTART=1) never change start-at-sign-in, also from the setup page or `off`.

## Troubleshooting
Nothing new.

## PRIVACY
- jobs.db and schedule.db (what you asked the AI, your reminders) are now owner-only (0600) on macOS and Linux.
