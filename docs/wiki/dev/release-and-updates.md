# Releases and self-updates

Kurooto updates itself from signed releases published as static files on GitHub Pages. The installer, the updater
and the release tool share one signing scheme. The maintainer's checklist is `docs/RELEASING.md`; this page explains
the machinery behind it.

The user's view: [../user/updates-and-backups.md](../user/updates-and-backups.md).

## Versioning and the changelog

- The version lives only in `pyproject.toml` (`[project] version`). At runtime `kurooto.__version__` comes from
  `importlib.metadata.version("kurooto")`, or `"0.0.0+source"` when running from a tree that isn't installed
  (`src/kurooto/__init__.py`).
- `CHANGELOG.md`: `## X.Y.Z (YYYY-MM-DD)` sections, newest first, bullets with a bold lead. Work in progress goes under
  `## X.Y.Z (unreleased)`; the date replaces "unreleased" when it ships. The site's changelog page is built from this
  file (`tools/release.py:site_pages`, `md_html`).
- The Android app's versionCode is derived from `pyproject.toml` (`android/build.sh`, `tools/release.py:version_code`).
- Dependencies are pinned twice: `uv.lock` for development and `requirements.lock` (hashes) for installs. CI's
  `update-rehearsal` job fails if they disagree (`uv export --frozen --no-dev --no-emit-project --format
  requirements-txt`). Regenerate `requirements.lock` with that command whenever `uv.lock` changes.

## Keys

- Ed25519, through the `cryptography` package (`src/kurooto/update/signing.py`: `sign`, `verify`, `canonical`,
  `public_b64`). `canonical(doc)` is `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, so
  signatures are over a canonical form, not the bytes on disk.
- Trusted public keys: `signing.PUBLIC_KEYS` **and** the same list in `installer/bootstrap.py:PUBLIC_KEYS`. Rotate by
  adding the new key first (newest first), releasing, and retiring the old one later. Both lists must change together.
- The private key never leaves the maintainer's machine (by default `~/.config/kurooto-dev/release-key.pem`,
  passphrase-encrypted; `tools/release.py:keygen`). CI never signs. The Android release keystore lives beside it.
- `KUROOTO_EXTRA_UPDATE_KEY` adds one more trusted key at runtime; it exists for tests and the rehearsal. Never set it
  on a real install.

## `tools/release.py`

| Subcommand | Function | Needs the key | What it does |
|---|---|---|---|
| `keygen` | `keygen(out, no_pass)` | makes it | writes a PKCS8 PEM (refuses to overwrite) and prints the public key to paste into both `PUBLIC_KEYS` lists |
| `build` | `build(site, base, version, notes, break_run, apk, critical)` | no | copies the repo to a temp dir (no `.git`, venvs, `node_modules`, keys, `docs/media`), optionally adds the APK as `src/kurooto/data/kurooto.apk`, runs `uv build --sdist`, writes `SITE/releases/<v>/kurooto-<v>.tar.gz` and `manifest.unsigned.json` (`{version, notes, [critical], created, files: {name: {url, sha256, size}}}`), the site pages (`install.sh`, `install.ps1`, `bootstrap.py`, `index.html`, `privacy.html` (`docs/PRIVACY.md` rendered into `installer/privacy.html`, `privacy_page`), `changelog.html`) and, with `--apk`, `android.json` |
| `sign` | `sign(site, base, version, key_path, channel, critical)` | yes | refuses a key not in the trusted list (`trusted_key`), writes `releases/<v>/manifest.json` = `{"doc": ..., "sig": ...}` and the channel pointer `SITE/<channel>.json` = signed `{version, manifest_url, issued, channel, [critical]}` |
| `yank` | `yank(site, key_path, versions, reason, undo)` | yes | signed `SITE/yank.json` (`{yanked: {v: reason}, issued}`, `issued` always rises) |
| `publish` | `publish(site, message)` | no | copies the site into a worktree of `gh-pages` (except `*.unsigned.json`), commits and pushes |

`--break-run` (build) injects a crash into `daemon.run()`; it exists only for the rollback rehearsal.

### Never rebuild after signing

The owner signs. `sign` signs whatever `manifest.unsigned.json` says, including the sha256 of the tarball that `build`
made. `build` is not reproducible (timestamps), and running it again for the same version overwrites the tarball and
the unsigned manifest without touching the signed `manifest.json`. Nothing checks this: `sign` doesn't re-hash the
tarball and `publish` checks neither signatures nor hashes. The result of a rebuild after signing is a published
manifest whose checksum doesn't match its tarball, and every client then fails with "didn't match its signed checksum"
(`update/updater.py:Updater._download`, `installer/bootstrap.py`). Clients that already staged that version keep the
old build (`Updater.stage` returns early when `versions/<v>` exists).

Rules that follow:
- An agent or contributor prepares a release up to `build` at most, and only when asked. Signing and publishing are the
  owner's.
- After the owner has signed, don't run `build` for that version again, don't touch `SITE/releases/<v>/`, and don't
  "fix" anything inside the site folder. A problem means a new version (or a yank), not a rebuild.

### Channels

`sign --channel <name>` writes `<name>.json`; `stable` is the default and `beta` is the convention for testers. An
install's channel is `updates.channel` (default `stable`; the installer writes it for non-stable channels via
`KUROOTO_CHANNEL`, `bootstrap.py:remember_channel`).

### Critical releases

`build --critical` marks the manifest, `sign --critical` marks the pointer; `Updater.check` ORs them. A critical
release skips every hold (exam season, staged waiting, feature holds). The pointer's flag is lost when that channel is
signed again.

## Install layout (`src/kurooto/update/`)

In the app folder (`Paths.app`):

| Path | Written by | Content |
|---|---|---|
| `launcher.py` | `cli.py:install_finish` (copied from `update/launcher.py`) | stdlib-only launcher; lives outside the versions so an update can't break it |
| `versions/<v>/` | `Updater.stage`, `bootstrap.py` | the extracted source and its own `.venv` |
| `current.json`, `previous.json` | `Updater.switch`, `install_finish` | which version runs, and the one before |
| `update.json` | `Updater.switch`, `probation_passed`, `launcher.rollback` | `{"phase": "trial" \| "ok" \| "rolled_back", from, to, since, ...}` |
| `bad.json` | `launcher.rollback`, "Skip" | versions never to install again |
| `install.json` | `install_finish` | the Python and uv used, for the launcher and `core/mcp.py:command` |
| `launcher.json` | `launcher.run` | the launcher's own record |
| `call-line/` | `modules/calls/deploy.py` | the Worker build folder |

State files: `<state>/update-seen.json` (last `issued` per channel and for the yank list), `<state>/yank.json` (cached
yank list), `<state>/update-ready.json` (a staged update waiting for its window).

## The updater

`update/updater.py:Updater`:

- `check(channel)`: fetch `<base>/<channel>.json` (base `PAGES`, or `KUROOTO_UPDATE_BASE`), verify the signature,
  refuse a pointer whose `issued` is older than the last seen (anti-replay, `update-seen.json`), ignore versions not
  newer (`vtuple`) or listed in `bad.json`, check `yanked()` (signed `yank.json`, also anti-replayed; offline or 404 uses
  the cache), fetch and verify the manifest and require its version to match the pointer's.
- `_get` only allows `https://` or `http://127.0.0.1`.
- `stage(...)`: download into `versions/<v>.partial`, check sha256, extract with the leading folder stripped (no `..`,
  no absolute paths, `filter="data"`), `install_into()` builds the venv with `uv pip install --require-hashes -r
  requirements.lock` and the package with `--no-deps`, run `python -m kurooto selftest`, then `os.replace` to
  `versions/<v>`. Any error removes the partial folder.
- `switch(v)`, `probation_passed(v)` (phase `ok` after at least 300 s), `prune(keep=3)` (the three newest plus current
  and previous).

`update/service.py:Updates` (created in `App.__init__`, started in `App.start`):

- Settings: `updates.mode` (`night` | `ask` | `off`), `updates.channel`, `updates.window` (`["03:00", "05:00"]`),
  `updates.staged`, `updates.wait_hours` (48), `updates.exam_hold`.
- Schedule: `updates:check` every 6 h; `updates.probation` about 5 minutes after a start on trial; a rollback notice.
- `check()`: emits `update_found`, then in order: `hold()` (staged wait, timed by `Updates.clock`, or exams)
  `update_waiting`; `mode == off` (a note only); `held()` (feature holds registered in `Updates.holds`, e.g. exam
  season) `update_held`; `ask` (a Telegram message with `upd:<v>:now|later|skip` buttons, handled by `Updates.button`);
  otherwise stage in a thread and book `updates.apply` at a random time in the window.
- `apply_if_quiet()`: waits if held; retries in 20 minutes while AI jobs run or a call is live; re-checks the yank list;
  then `switch_to()`: `Updater.switch`, `update_switch` event, `app.request_restart()`.
- `end_probation()`: prunes and says "Kurooto updated".

`kurooto update` (`cli.py:update`) checks and reports; `kurooto update --now` stages, switches and restarts at once,
bypassing holds on purpose.

## Restart and rollback

1. `App.request_restart()` sets `restart_requested` and stops the daemon; `daemon.run` returns `RESTART = 75`.
2. The launcher (`update/launcher.py:run`) starts `versions/<current>/.venv/... -m kurooto run` again on exit 75, stops
   on 0 or 3 (3: another copy is already running), and treats anything else as a crash with back-off (5 s to 300 s).
3. While `update.json` says `trial` for this version, three crashes each within 300 s of starting call
   `rollback()`: the version goes into `bad.json`, `current.json` goes back to `previous.json`, `update.json` becomes
   `rolled_back`. `Updates.tell_rolled_back` tells the user on the next start.
4. After 300 s of running, probation passes (`phase: ok`).

Without the launcher (a development install), `daemon.supervise` restarts the daemon after crashes and on exit 75.

## Fresh installs (`installer/`)

`install.sh` / `install.ps1` check free space (2 GB), install a pinned uv and Python 3.12, download `bootstrap.py` from
the site (or use `KUROOTO_SOURCE` for a local tree) and run it. `bootstrap.py` verifies the pointer and manifest with its
own `PUBLIC_KEYS`, checks the tarball's sha256, builds `versions/<v>/.venv` from `requirements.lock`, runs `selftest`,
then execs `kurooto install-finish`, which writes `current.json`, `previous.json`, `update.json` (phase `ok`),
`install.json`, the launcher, the `kurooto` command shim (`~/.local/bin/kurooto`; on Windows `kurooto.cmd` and an
uninstall registry entry), PATH changes, autostart and the app-menu entry (skipped with `KUROOTO_NO_AUTOSTART=1`).
Running the installer again repairs an install.

Differences from the updater worth knowing: `bootstrap.py` doesn't consult `yank.json` or the anti-replay record, and
`install_finish` writes phase `ok`, so an upgrade through the installer has no probation and no rollback.

## Rehearsal

`tools/update_rehearsal.py` (CI job `update-rehearsal` on Linux, Windows and macOS) runs the whole path in a sandbox: a
local site server, a throwaway key trusted through `KUROOTO_EXTRA_UPDATE_KEY`, release 0.1.0 installed with the real
installer, 0.2.0 through `kurooto update --now`, 0.3.0 built with `--break-run` (it must roll back to 0.2.0 and land in
`bad.json`), then "Up to date" and `kurooto uninstall`. Run it locally before changing anything in `update/`,
`installer/` or `cli.py:install_finish`.

## Known problems

- `update/launcher.py`'s docstring lists the phases as `trial | ok`; `rolled_back` is also written.
