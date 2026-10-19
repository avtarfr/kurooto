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
#    pyproject.toml: version = "0.1.0"; CHANGELOG.md: the release's notes; commit, tag v0.1.0, push; CI green.
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

## Checks before publishing
- `uv run pytest`, CI green on all three systems (including the update rehearsal and the call line).
- `python3 tools/privacy_scan.py --tree` and `--history` clean.
- Install from the new site on a fresh machine or VM; `kurooto doctor`; update from the previous release.
