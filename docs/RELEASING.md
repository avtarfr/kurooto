# Releasing (for the maintainer)

Everything here runs on the maintainer's laptop. The signing keys never go to CI or GitHub.

## Once
1. **Update key** (signs what the installer and updater trust):
   `uv run tools/release.py keygen` (asks for a passphrase) → `~/.config/kurooto-dev/release-key.pem`.
   Put the printed public key in `PUBLIC_KEYS` in `src/kurooto/update/signing.py` and `installer/bootstrap.py`,
   commit. Back the key file up offline (and the passphrase somewhere else). Losing it means users can't update
   without reinstalling; leaking it means someone could sign releases (add a new key, release, then retire the old).
2. **Android key** (phones only accept updates signed with the same key):
   `keytool -genkeypair -keystore ~/.config/kurooto-dev/android-release.keystore -alias kurooto -keyalg RSA
   -keysize 3072 -validity 10000 -dname "CN=Kurooto"`. Back it up offline too.
3. **GitHub Pages:** Pages needs a public repository on the free plan. After making it public: Settings → Pages →
   Deploy from a branch → `gh-pages` / root. The site is then at `https://avtarfr.github.io/kurooto/`.

## Going public (done, 2026-10-19)
The repository went public starting from one fresh commit of the tree (noreply author); the private development
history before it is kept offline by the maintainer. Secret scanning and push protection are on, and the privacy
scanner's denylist is the `PRIVACY_DENYLIST` Actions secret (terms only).

## Each release
```sh
# 1. version and changelog
#    pyproject.toml: version = "0.1.0"; CHANGELOG.md: the release's notes; known problems found since the last
#    release go in src/kurooto/data/known_issues.json (/fixme reads it; see below); commit, tag v0.1.0, push; CI green.
# 2. the Android app, release-signed
KUROOTO_KEYSTORE=~/.config/kurooto-dev/android-release.keystore KUROOTO_KEYSTORE_PASS=… \
  ANDROID_HOME=/path/to/sdk android/build.sh
# 3. build and sign the release
uv run tools/release.py build --site ~/kurooto-site --base https://avtarfr.github.io/kurooto \
  --apk android/build/kurooto.apk --notes "…"
uv run tools/release.py sign --site ~/kurooto-site --base https://avtarfr.github.io/kurooto \
  --version 0.1.0 --key ~/.config/kurooto-dev/release-key.pem --channel stable
# 4. publish
uv run tools/release.py publish --site ~/kurooto-site --message "release 0.1.0"
```
Try a release on the `beta` channel first (`--channel beta`; testers set `updates.channel` to `beta`).
A tester installs straight from beta with `KUROOTO_CHANNEL=beta` in front of the installer
(`curl -LsSf https://avtarfr.github.io/kurooto/install.sh | KUROOTO_CHANNEL=beta sh`; on Windows
`$env:KUROOTO_CHANNEL = 'beta'` first): the installers pass `--channel beta` to `bootstrap.py`, which installs what
`beta.json` names and saves `updates.channel` = `beta` in the new install's settings (`settings.json` in its config
folder, made if there's none), so it keeps following beta. Sign the first beta before telling testers, or there's no
`beta.json` to install from.
Exam season holds every update back during its users' exams, and staged updates (`updates.staged`) wait 48 hours
and for exams to end. A release marked critical skips every one of those holds: `build --critical` marks it in its
signed manifest, `sign --critical` in the signed channel pointer, and installs treat either the same way (one is
enough). The pointer's mark goes when that channel is signed again without it; the manifest's stays with the
version. Only for fixes that can't wait.

**Never rebuild after the owner has signed: the tarball must stay byte-identical to the signed one.** `sign` signs
what `manifest.unsigned.json` says, including the tarball's sha256 and size. `build` isn't reproducible (file times
in the archive, the manifest's `created`), and running it again for the same version overwrites the tarball and the
unsigned manifest but not the signed `manifest.json`. Nothing catches it: `sign` doesn't hash the tarball again and
`publish` checks neither signatures nor hashes. Published, every install and update of that version then fails with
"didn't match its signed checksum", while installs that already downloaded the old build keep it. So an agent or
contributor goes no further than `build`, and only when asked; signing and publishing are the owner's. After the
owner has signed, don't run `build` for that version again or touch anything in `SITE/releases/<v>/`: a problem
means a new version (or a yank), never a rebuild.

`build` also writes the site's own pages: the installers and landing page from `installer/`, and `privacy.html`,
made from `docs/PRIVACY.md` inside `installer/privacy.html` (between its `PRIVACY:START` and `PRIVACY:END` markers).
Google's sign-in setup links to that page, so publish the site whenever PRIVACY.md changes.

## Known issues (`/fixme`)
`src/kurooto/data/known_issues.json` ships inside each signed release, so its signature covers it. `/fixme` and
`kurooto fixme` match it by rules (no AI): an entry shows when the running version is in its `versions` and one of
its `checks` fails, its `symptom` pattern matches a failing check's line or what was typed, or all words of one of
its `keywords` were typed (no rule at all: everyone on those versions sees it). A newer release that's already
downloaded and waiting for the night lends its list to the version still running, so add the problems of older
versions there with `versions` like `">=0.5.14,<0.5.16"` and a `fix` that says to update (`"action": "update"`), or
`"action": "fix:<check id>"` for a health check's Fix. The fields and how to add one are in
`docs/wiki/dev/debugging.md`. A release that's broken for everyone is a yank instead.

## Withdrawing a release (yank)
A release that turns out broken goes on the signed yank list; installs then never update to it, even ones that
already downloaded it for the night:
```sh
uv run tools/release.py yank --site ~/kurooto-site --key ~/.config/kurooto-dev/release-key.pem 0.2.1 \
  --reason "loses reminders after a restart"
uv run tools/release.py publish --site ~/kurooto-site --message "yank 0.2.1"
```
`--undo` takes a version off the list again. A channel pointer that still names a yanked version keeps it refused,
so sign a fixed version on that channel (the command warns). A security fix: `--critical` (on `build` or `sign`, see
above), so installs don't wait their 48 hours, for exams to end, or for Exam season.

## Checks before publishing
- `uv run pytest`, CI green on all three systems (including the update rehearsal and the call line).
- `python3 tools/privacy_scan.py --tree` and `--history` clean.
- Install from the new site on a fresh machine or VM; `kurooto doctor`; update from the previous release.
