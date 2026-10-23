# Conventions

## Definition of done

A standing rule from the owner: **no change to Kurooto is done until all of these match the code, updated in the same
commit as the change**:

1. the user wiki, `docs/wiki/user/` (the page for the feature, plus `commands.md`, `messages-it-sends.md`,
   `privacy.md`, `troubleshooting.md` or `glossary.md` when they're affected);
2. this developer wiki, `docs/wiki/dev/` (the area's page, and its known problems when you fix or find one);
3. `/help`: the command list Telegram and the phone app's chat show (`core/commands.py`: each module's `commands()`
   help text, `CORE`, the group in `GROUPS`, each request's `examples`), and the `/` menu;
4. `CHANGELOG.md`, a line under the unreleased version;
5. the site pages `tools/release.py` publishes (`site_pages`: the landing page from `installer/index.html`, the privacy
   page (`docs/PRIVACY.md` rendered into `installer/privacy.html` between its `PRIVACY:START`/`PRIVACY:END` markers),
   the changelog page from `CHANGELOG.md`, the install scripts).

Also, when they apply: `docs/MANUAL.md` (with the Undo), `docs/PRIVACY.md`, `docs/SETTINGS_GUIDE.md` (regenerated with
`tools/gen_settings_guide.py`), tests.

## Code style

- Python 3.12+, `from __future__ import annotations` at the top of every module, type hints on public functions.
- Ruff is the formatter and linter (`pyproject.toml [tool.ruff]`): line length 120, rules `E F W I B UP S`
  (bandit-style security checks), with `S101` (assert), `S110` (deliberate best-effort `except: pass`), `S603`/`S607`
  (subprocess) ignored. SQL built from constant column lists is allowed in `core/scheduler.py` and `core/jobs.py` only
  (`S608`); values are always bound. Tests may use fake secrets and temp paths (`S105`, `S106`, `S108`, `S310`). CI runs
  `ruff check` and `ruff format --check`; run both before pushing.
- Standard library first. The dependency list (`pyproject.toml [project] dependencies`) is short on purpose:
  `cryptography`, `filelock`, `keyring`, `psutil`, `ptyprocess`/`pywinpty`, `python-dateutil`, `segno`, `tzdata`,
  `websockets`, `zstandard` (Linux). HTTP is `urllib.request`, always through `core/egress.py:urlopen` for an
  internet address (see Privacy rules); the web server is `http.server`. Adding a dependency
  means updating `uv.lock` **and** `requirements.lock` (CI compares them) and is a decision for the owner.
- No new subprocess calls through `subprocess` directly: use `core/proc.py:run` (no console windows, UTF-8, tree kill,
  `.cmd` shims). No new JSON writes with `write_text`: use `core/state.py:jsave`. No notes writes outside
  `core/tools.py:write_note_file`. No paths built by hand: `core/paths.py` and `core/layout.py`.
- Every text read or write passes `encoding="utf-8"`.
- A failure in one feature must not stop the others: catch at the boundary, emit an event (`<area>_failed` with a short
  error), and carry on. Background loops back off; scheduled actions let the scheduler record the error.
- Front end: plain JavaScript with `"use strict"`, no build step, no inline scripts (the CSP forbids them), every file
  must pass `node --check`.

## Comments and messages

- Comments and docstrings are plain English sentences that say why, written for someone who doesn't know the code.
  Module docstrings open with what the file is for in one line, then the details (look at `core/scheduler.py` or
  `core/jobs.py`). Many comments name the related file (`(core/calm.py)`), which keeps cross-references greppable; keep
  doing that.
- Messages to the user are short, plain and concrete: what happened, what to do, where (Settings → AI → Test). No
  jargon ("401", "exception") in what the user sees; put details in `Result.detail`, events and the log. No exclamation
  marks, no emojis.
- Say what Kurooto did, never claim something it didn't do. The AI is told the same (`providers/context.py`).
- Commit messages describe the user-visible change in a sentence, like the existing history.

## Diffs

- Minimal and surgical: change what the task needs, don't reformat or rename unrelated code, don't reorder imports by
  hand (ruff does it).
- Every change meets the [definition of done](#definition-of-done) above: user wiki, developer wiki, `/help`,
  `CHANGELOG.md` and the published site pages, in the same commit.
- Behaviour that installs, deletes, signs in or sends must stay opt-in and ask first.

## Privacy rules

- Nothing leaves the computer unless a feature the user turned on says so in its `privacy` text and in
  `docs/PRIVACY.md`. A new outward call (a host, an API, a cloud service) needs: the module's `privacy` string, a
  `docs/PRIVACY.md` entry, a setting to turn it off where it isn't the feature's whole point, and the owner's OK.
- Every request on the internet goes through `core/egress.py`: `egress.urlopen(req, "<feature>", timeout=...)` in place
  of `urllib.request.urlopen` (`own=True` only for an address the user gave), `egress.allow(url, feature)` before
  another kind of connection, `egress.handed("<program>", "<feature>")` before starting a program that goes online by
  itself. A new built-in host goes into `egress.HOSTS` and PRIVACY.md's "Where requests go" table together (a test
  compares them); without it, `privacy.egress` `enforce` refuses the request. Details:
  [core.md](core.md#egress-every-request-on-the-internet).
- Kurooto never sends mail or messages to anyone but its owner on its own. Drafts wait for an explicit Send.
- Secrets live in `app.secrets` only, never in settings, events, logs, notes, the reserve or the diagnostics bundle. New
  secret names go into `diagnostics.py:KNOWN_SECRETS`. Pass tokens to child programs through environment variables or
  files, never argv (see `modules/notes_sync.py`'s `GIT_CONFIG_*`).
- Events and logs carry ids, counts and short errors, not what the user wrote or what the AI answered.
- The user's notes are theirs: add, never reword or remove their text. The concept graph's guard
  (`core/graphwrite.py:guarded`) is the model for "only Kurooto's own blocks change".
- State files are owner-only on POSIX (`jsave` mode 0600, `owner_only` for databases).

## The privacy scanner (`tools/privacy_scan.py`)

Three layers, run on staged changes (pre-commit), on commits being pushed (pre-push), and on the whole tree and history
in CI:

1. Patterns: Telegram bot tokens, Google, OpenAI, Anthropic, GitHub, Slack, Hugging Face and NVIDIA keys, private
   keys, JWTs, secret assignments, **email addresses**, **phone numbers**, private IPs, `*.workers.dev` hosts,
   **home folders** (`/home/<name>`, `/Users/<name>`, `C:\Users\<name>`). Safe forms are allowed (`SAFE`): GitHub
   noreply addresses, `example.com`, placeholder home folders such as `/home/you`. Paths listed in
   `tools/privacy_allow.txt` skip this layer (test vectors).
2. A personal denylist never committed: `KUROOTO_DENYLIST` (CI secret `PRIVACY_DENYLIST`) and
   `~/.config/kurooto-dev/denylist.txt` (or `KUROOTO_DENYLIST_FILE`): terms, `re:` regexes, `@file:` secrets files,
   `allow:` contexts.
3. Author and committer identities must be GitHub noreply addresses (the pre-commit hook checks `user.email` too).

Findings print `path:line` and the kind, never the matched value. Install the hooks once with
`git config core.hooksPath tools/hooks`; `gitleaks` runs too when installed.

## Never commit

- Secrets of any kind, `.dev.vars`, keystores (`*.keystore`, `*.jks`), PEM files, the release key.
- Real names, emails, phone numbers, chat ids, Telegram usernames, Worker hostnames, paths from anyone's machine.
- Real user data: settings, events, transcripts, notes, diagnostics bundles, `cases` exports.
- Build output: `src/kurooto/data/kurooto.apk` (git-ignored; only older packages carried it, releases now name the
  app in their signed manifest),
  `src/kurooto/data/worker/public/app.js` (bundled at deploy), `node_modules/`, `.wrangler/`, `dist/`, `build/`,
  the release site folder.
- Generated docs out of date: regenerate `docs/SETTINGS_GUIDE.md` instead of editing it by hand.
