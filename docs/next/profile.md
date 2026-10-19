# profile: docs to merge (MANUAL, Troubleshooting, CHANGELOG, PRIVACY, AGENTS)

## MANUAL: new and changed sections

### The setup wizard (changed: add after the numbered list)
**Used Kurooto before?** The first page has **I've used Kurooto before**: give your private repository, a token for it
and your profile's passphrase, and your setup comes back (see [Moving to a new computer](#moving-to-a-new-computer)).
The steps after it are then filled in from your profile; they help with what can't move by itself (signing your AI in
again, installing what a feature needs).

### Profile sync (new, under Features, after Notes sync)
Your Kurooto setup, kept **encrypted** in your own private GitHub repository, so a new computer (or a reinstall) is set
up again in a minute instead of an evening.

**What's saved:** everything you changed in Settings and which features you have on; your passwords and keys (bot
token, API keys, the Google sign-in, your call line's keys and its Cloudflare sign-in, so the same call line and the
same paired phones keep working); and the state worth keeping: deadlines, quiz progress, routines, what the nightly
look back has observed, the Agent plan calendar, Classroom's "already seen" lists, and reminders, calls and the alarm
you've scheduled. **Not saved:** your notes (Notes sync keeps those; your how-to-help-me and recurring quizzes live in
your notes anyway), AI request history, call transcripts, the reports you added in About you, caches and logs.

**Set up:** Features → Profile sync. Leave the repository and token empty to use the repository Notes sync uses (the
profile goes on a branch of its own, `kurooto-profile`, so your notes folder never sees it), or give another private
repository and a token for it, made the same way as for Notes sync. Then pick a **passphrase** of a few words. You need
it on a new computer; it's never stored anywhere, and if you forget it the profile can't be opened (your notes are
still fine: start again with a new passphrase).

**When:** once a day (04:40, `profile.when`), and ten minutes after you change a setting in the dashboard or turn a
feature on or off (`profile.after_changes`; several changes in a row make one save). A profile is small, so it also
runs on battery. Nothing changed: nothing is sent. `/profile` shows what's saved; `/profile save` saves now.

**Two computers:** if another computer saved the profile since this one last did, this one doesn't overwrite it; it
tells you once, and `kurooto doctor` says so. Restore it here (`kurooto profile restore`), or save over it
(`/profile save`; the old one stays in the branch's history).

**Turn it off:** Features → Profile sync → Turn off. What's in the repository stays there; delete the
`kurooto-profile` branch on GitHub to remove it.

### Moving to a new computer (new section, after "Updates and going back")
With Profile sync on (on the old computer):

1. On the old computer, if it still works: `/profile save` (or just wait for the daily save), then **turn Kurooto off
   there** (`kurooto off`): two computers can't share one Telegram bot or one call line.
2. Install Kurooto on the new computer. On the setup page's first step, press **I've used Kurooto before**, and give:
   the repository (`owner/name`), a token for it (lost it? make a new fine-grained token for that repository with
   Contents: Read and write), and your passphrase.
3. Kurooto restores your settings, keys and saved items, turns on every feature that's ready, and, with Notes sync,
   brings your notes back. It lists what's left to do here, then **Continue** walks you through it: sign your AI in
   again (agy, Codex and Claude Code keep their sign-ins on the computer they ran on), install what features need
   (Git, the notes brain, local AI models: Done installs them), and pick folders that were on the old computer
   (backup folder, add-ons folder).

From a terminal instead: `kurooto profile restore --repo owner/name` (it asks for the token and passphrase without
showing them, stops Kurooto, restores, offers to set up what's left, and starts it again). Before restoring, Kurooto
keeps a copy of the settings it replaces in its data folder (`profile/before-restore-<date>/`). Your notes folder is
never touched by a restore.

`kurooto profile status` says what's saved and when; `kurooto profile save` saves now (the first time, it asks for the
repository and a passphrase). Without Profile sync, a backup zip works too (`kurooto restore <zip>`, see Backups).

### Your add-ons (new, under Features, last)
Your own extra features, skills and prompts, from a folder of yours: for example a private repository you cloned, so
you can keep things for yourself while running the normal Kurooto. Turn on **Your add-ons** and paste the folder's full
path. The folder may have:

| | What it does |
|---|---|
| `modules/*.py` | extra features: classes based on Kurooto's `Module` (see `src/kurooto/modules/base.py`). They're listed in the dashboard's Features tab under **Your add-ons**, each off until you turn it on. Files starting with `_` are helpers they can import (`from kurooto_addons import _helpers`). |
| `skills/<name>/SKILL.md` | extra skills, written like Kurooto's own; a skill of the same name in your notes (`kurooto/skills/`) still wins |
| `prompts/*.md` | extra prompts; `/prompts` lists them as `add-ons/<name>` |
| `settings.json` | default settings laid under yours, e.g. `{"checkins": {"evening": "21:30"}}`; what you set yourself still wins (it can't turn features on) |

**This runs your own code:** the Python files run inside Kurooto with its access to this computer. Only use add-ons you
wrote or trust. `overlay.code` off keeps the skills, prompts and settings and skips the Python. A broken add-on never
stops Kurooto: a file that fails to load is skipped, and an add-on that fails while running is cut off from that one
request; both are logged and shown by `/addons` and `kurooto doctor`. The folder can't be inside Kurooto's own folders,
and updates never change it. Turning the feature off unloads the add-ons; restart Kurooto after editing their code.

## Troubleshooting rows

| What you see | What to do |
|---|---|
| Restore: "That passphrase doesn't open this profile" | It's the passphrase you picked when you turned on Profile sync (not your GitHub password). Try again; nothing was changed. |
| Restore: "…was changed or damaged, so it can't be trusted" | A file on the `kurooto-profile` branch was edited outside Kurooto. Nothing was changed here. On GitHub, open the branch's history and revert the last edit, then restore again. |
| Profile sync: "another computer saved your profile since this one did" | You restored or used Kurooto elsewhere. Restore it here (`kurooto profile restore`), or `/profile save` to make this computer's the one. |
| Two computers both answer, or the bot misses messages after moving | Turn Kurooto off on the old computer: `kurooto off`. |
| Your add-ons: a problem in `kurooto doctor` | `/addons` shows which file and the error. Fix it, then restart Kurooto (`kurooto stop`, `kurooto start`). |

## CHANGELOG lines (0.2.0)
- Profile sync (new, off by default): your settings, passwords and keys and the state worth keeping (deadlines, quiz
  progress, routines, observations, your call line's keys), encrypted with a passphrase only you know (scrypt and
  AES-GCM), in your own private GitHub repository, on its own branch. Saved daily and soon after you change a setting.
- Moving to a new computer: "I've used Kurooto before" on the setup page, or `kurooto profile restore`, brings it all
  back and walks you through what can't move (your AI's sign-in, programs to install). `kurooto profile save|status`.
- Your add-ons (new, off by default): your own features, skills, prompts and default settings from a folder of yours,
  listed under "Your add-ons"; a broken one never stops Kurooto and shows up in `kurooto doctor`.

## PRIVACY rows

The "Always" table:

| Feature | What leaves | Where to |
|---|---|---|
| Profile sync | your settings, passwords and keys, and saved state (deadlines, quiz progress, routines, observations, scheduled reminders and calls), all encrypted with your passphrase before they leave; in plain text only when it was saved, Kurooto's version, the kind of computer and a random id for it | your own private GitHub repository (the one Notes sync uses, or another you pick) |
| Your add-ons | nothing by the feature itself; your add-ons' own code can do anything Kurooto can, so they send whatever they're written to send | wherever your add-ons send it |

Under "Secrets", add: with Profile sync on, your keys also go to your repository, encrypted with your passphrase
(AES-GCM, with a key from scrypt). The passphrase is never stored; this computer keeps the profile's data key in its
keychain, like your other keys, so it can save on its own. Never in the profile: this computer's dashboard key, and the
reports you added in About you.

## AGENTS.md: rows for the Commands table

| Command | What it does | Safe to run? |
|---|---|---|
| `kurooto profile status` | what the encrypted profile holds and when it was saved | yes |
| `kurooto profile save` | saves the profile now (the first time it asks for a repository and a passphrase) | yes, when set up; never type a passphrase for them |
| `kurooto profile restore` | replaces Kurooto's settings, keys and saved state with the profile's (keeps a copy of the settings first) | **ask first**; it needs their passphrase, which only they type |

## For the coordinator
- **Register** in `modules/catalog.py`: `from kurooto.modules.profile import Profile` (after `Backups` in CATALOG) and
  `from kurooto.modules.overlay import AddOns` (last). In `web/api.py` `MODULE_ORDER`: `"profile"` after `"backups"`,
  `"overlay"` at the end. My tests add both to the catalog themselves until then (`tests/unit/test_profile.py`, fixture
  `registered`), so they pass either way.
- `backups.SKIP_STATE` gets `"profile.json"` (it holds this computer's random id): done by home on `w/home` (385925e).
- Shared files I touched, each in one place: `app.py` (3 lines after the catalog loop: `overlay.load(self)`),
  `core/config.py` (`set_layer()` and `Settings.all()` lays the add-ons' defaults between the registered ones and
  yours), `cli.py` (a `profile` block before the `ask`/`call` block, plus `profile_parsers(sub)` and one dispatch line
  in `main()`, and a docstring line), `web/api.py` (`profile` GET and `profile/…` POST hooks; `_modules()` lists
  add-ons after `MODULE_ORDER` with `"addon": true`), `modules/skills.py` (`all_skills()` loads add-on skills and
  prompts, `/skills` marks them "(add-on)"), `modules/library.py` (`prompts(workspace, extra)`), `web/static/setup.html`
  + `setup.js` (the restore page), `web/static/home.js` (Features tab groups "Your add-ons"), `web/static/style.css`
  (two lines), `diagnostics.py` (two names in `KNOWN_SECRETS`).
- New settings: `profile.{repo, branch, remote, after_changes, when}`, `overlay.{path, code}`. New secrets:
  `profile.token` and `profile.key` (the cached data key), added to `diagnostics.KNOWN_SECRETS` (so the doctor bundle
  blanks them; the profile itself never carries `profile.key` or `web.token`). The profile carries every secret named in
  `KNOWN_SECRETS` (the keychain can't be listed), so **any secret another branch adds must be in `KNOWN_SECRETS`** to
  move to a new computer. New events: `profile_saved`, `profile_save`, `profile_failed`, `profile_restored`,
  `addon_failed`.
