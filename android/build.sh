#!/usr/bin/env bash
# build.sh: build Kurooto's Android app (for Android 6 and newer) with Gradle, which it downloads and checks itself.
#
#   ANDROID_HOME=/path/to/sdk android/build.sh            build/kurooto.apk (or kurooto-debug.apk, see below)
#   android/build.sh --dev                                 build/kurooto-dev.apk: io.github.avtarfr.kurooto.dev, named
#                                                          "Kurooto dev", installs beside the real app; debuggable, and
#                                                          `adb shell am start -n io.github.avtarfr.kurooto.dev/
#                                                          io.github.avtarfr.kurooto.MainActivity --ez demo true` shows
#                                                          made-up data without pairing (never in release builds)
#   android/build.sh --lint                                API-level lint (NewApi, InlinedApi) of the release build
#   android/build.sh --test                                the JVM tests (plain javac, no Gradle): crypto against the
#                                                          shared vectors, the call page's speech bridge (what's heard,
#                                                          quoted safely), the cards' and location reminders' rules,
#                                                          the notification buttons and local alarm rules, bedside
#                                                          mode's rules (brightness by the hour, hours) and opening
#                                                          Systems and the Notes map (ViewSeal, 0.7.0), and the
#                                                          app's own connection to the call line (WebSock, 0.7.0)
#
# Needs: an Android SDK with platform 36 and build-tools (ANDROID_HOME), a JDK 17 (java on PATH or JAVA_HOME), and the
# network the first time (Gradle 8.14.6, checked against its SHA-256 below, then the Android Gradle plugin, Kotlin and
# Compose from Google's and Maven Central's repositories). Gradle's files go in GRADLE_USER_HOME, by default a
# gradle-home folder next to the SDK (not in your home folder); its project cache and Kotlin's go in build/.
# Gradle builds an unsigned APK (R8 shrinks the libraries in a release build; build.gradle.kts has the versions); this
# script signs it. Signing: KUROOTO_KEYSTORE (path), KUROOTO_KEYSTORE_PASS and optionally KUROOTO_KEY_ALIAS (default
# "kurooto"). Without them a debug key (kurooto-debug.keystore in GRADLE_USER_HOME, so it outlives build/) signs it and
# the APK is named kurooto-debug.apk: fine for testing, but phones won't take it as an update to a release-signed app.
# The version comes from pyproject.toml: versionCode = ((major*1000 + minor)*1000 + patch)*10 + (rc number, or 9).
# Assets: android/assets plus the dashboard's own drawing code for Systems and the Notes map (0.7.0), copied in at build
# time from src/kurooto/web/static (views/*.html|js|css to assets/views/, the Public Sans files to assets/fonts/) by
# build.gradle.kts's kurootoViewAssets task, so there's one copy of it in the repository. ViewsActivity serves them.
# KUROOTO_APP_ID (optional): another application id (Gradle's -PkurootoAppId), for a test build beside the real app;
# --dev adds ".dev" to it.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
OUT=$HERE/build
PKG=io/github/avtarfr/kurooto

crypto_test() {
  local t; t=$(mktemp -d)
  javac -nowarn -encoding UTF-8 -d "$t" "$HERE/src/$PKG/B64.java" "$HERE/src/$PKG/Crypto.java" "$HERE/src/$PKG/Seal.java" \
    "$HERE/src/$PKG/Speech.java" "$HERE/src/$PKG/Buttons.java" "$HERE/src/$PKG/AlarmPlan.java" "$HERE/src/$PKG/Dock.java" \
    "$HERE/src/$PKG/ViewSeal.java" "$HERE/src/$PKG/SensesRules.java" \
    "$HERE/test/CryptoTest.java" "$HERE/test/SpeechTest.java" "$HERE/test/TodayTest.java" "$HERE/test/DockTest.java" \
    "$HERE/test/ViewsTest.java" "$HERE/test/SensesTest.java"
  java -cp "$t" io.github.avtarfr.kurooto.CryptoTest "$ROOT/tests/fixtures/call-vectors.json"
  java -Dfile.encoding=UTF-8 -cp "$t" io.github.avtarfr.kurooto.ViewsTest "$ROOT/tests/fixtures/call-vectors.json"
  java -Dfile.encoding=UTF-8 -cp "$t" io.github.avtarfr.kurooto.SpeechTest
  java -cp "$t" io.github.avtarfr.kurooto.TodayTest
  java -cp "$t" io.github.avtarfr.kurooto.DockTest
  java -cp "$t" io.github.avtarfr.kurooto.SensesTest
  # the check-in and quiz cards' and location reminders' rules (0.6.0)
  javac -nowarn -encoding UTF-8 -d "$t" "$HERE/src/$PKG/CardRules.java" "$HERE/src/$PKG/PlaceRules.java" "$HERE/test/CardsPlacesTest.java"
  java -cp "$t" io.github.avtarfr.kurooto.CardsPlacesTest
  # the app's own connection to the call line (0.7.0): its rules and the WebSocket client against a local server
  javac -nowarn -encoding UTF-8 -cp "$t" -d "$t" "$HERE/src/$PKG/LinkRules.java" "$HERE/src/$PKG/WebSock.java" "$HERE/test/LinkTest.java"
  java -cp "$t" io.github.avtarfr.kurooto.LinkTest
  rm -rf "$t"
}
if [ "${1:-}" = "--test" ]; then crypto_test; exit 0; fi

MODE=release
case "${1:-}" in
  --dev) MODE=dev ;;
  --lint) MODE=lint ;;
  "") ;;
  *) echo "usage: build.sh [--dev | --lint | --test]" >&2; exit 2 ;;
esac

SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[ -n "$SDK" ] && [ -d "$SDK" ] || { echo "Set ANDROID_HOME to your Android SDK." >&2; exit 2; }
export ANDROID_HOME=$SDK
BT=$(ls -d "$SDK"/build-tools/*/ | sort -V | tail -1)

VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)
read -r MAJ MIN PAT RC < <(python3 -c '
import re, sys
m = re.match(r"(\d+)\.(\d+)\.(\d+)(?:(?:rc|-rc\.?)(\d+))?", sys.argv[1])
print(m[1], m[2], m[3], m[4] or 9)' "$VERSION")
CODE=$(( ((MAJ * 1000 + MIN) * 1000 + PAT) * 10 + RC ))

# ---------- Gradle: the pinned version, downloaded once and checked ----------
GRADLE_VERSION=8.14.6
GRADLE_SHA256=7988ed071b2a07900e2ec715fca15c6ab72bce6db433af301fa7fa7e9407bd24
if [ -z "${GRADLE_USER_HOME:-}" ]; then
  GRADLE_USER_HOME=$(cd "$SDK/.." && pwd)/gradle-home
fi
export GRADLE_USER_HOME
export ANDROID_USER_HOME=${ANDROID_USER_HOME:-$GRADLE_USER_HOME/android-user}  # not ~/.android
mkdir -p "$GRADLE_USER_HOME" || { echo "Can't make $GRADLE_USER_HOME: set GRADLE_USER_HOME to a folder you can write." >&2; exit 2; }
DIST=$GRADLE_USER_HOME/kurooto-gradle
GRADLE=$DIST/gradle-$GRADLE_VERSION/bin/gradle
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
if [ ! -x "$GRADLE" ]; then
  mkdir -p "$DIST"
  ZIP=$DIST/gradle-$GRADLE_VERSION-bin.zip
  if [ ! -f "$ZIP" ] || [ "$(sha256 "$ZIP")" != "$GRADLE_SHA256" ]; then
    echo "downloading Gradle $GRADLE_VERSION (once) into $DIST"
    curl -fsSL --retry 3 -o "$ZIP.part" "https://services.gradle.org/distributions/gradle-$GRADLE_VERSION-bin.zip"
    mv "$ZIP.part" "$ZIP"
  fi
  [ "$(sha256 "$ZIP")" = "$GRADLE_SHA256" ] || { rm -f "$ZIP"; echo "Gradle's download doesn't match its SHA-256; not using it." >&2; exit 1; }
  rm -rf "$DIST/gradle-$GRADLE_VERSION"
  if command -v unzip >/dev/null; then unzip -q "$ZIP" -d "$DIST"; else python3 -m zipfile -e "$ZIP" "$DIST" && chmod +x "$GRADLE"; fi
fi

gradle() {
  "$GRADLE" -p "$HERE" --project-cache-dir "$OUT/.gradle" --no-daemon --console=plain -q --warning-mode=none \
    -Pkotlin.project.persistent.dir="$OUT/kotlin" -PkurootoVersionCode="$CODE" -PkurootoVersionName="$VERSION" \
    ${KUROOTO_APP_ID:+-PkurootoAppId="$KUROOTO_APP_ID"} "$@"
}

if [ "$MODE" = lint ]; then gradle lintRelease; echo "lint: ok"; exit 0; fi

mkdir -p "$OUT"
rm -f "$OUT"/*.apk
if [ "$MODE" = dev ]; then
  gradle assembleDev
  BUILT=$(ls "$OUT"/outputs/apk/dev/*-dev*.apk | head -1)
else
  gradle assembleRelease
  BUILT=$(ls "$OUT"/outputs/apk/release/*-release*.apk | head -1)
fi
"$BT/zipalign" -f -p 4 "$BUILT" "$OUT/aligned.apk"

if [ "$MODE" = release ] && [ -n "${KUROOTO_KEYSTORE:-}" ]; then
  NAME=kurooto.apk
  "$BT/apksigner" sign --ks "$KUROOTO_KEYSTORE" --ks-pass env:KUROOTO_KEYSTORE_PASS --ks-key-alias "${KUROOTO_KEY_ALIAS:-kurooto}" \
    --out "$OUT/$NAME" "$OUT/aligned.apk"
else
  if [ "$MODE" = dev ]; then NAME=kurooto-dev.apk; else NAME=kurooto-debug.apk; fi
  KS=$GRADLE_USER_HOME/kurooto-debug.keystore
  [ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storepass debugpass -keypass debugpass -alias debug \
    -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=Kurooto debug" >/dev/null 2>&1
  "$BT/apksigner" sign --ks "$KS" --ks-pass pass:debugpass --ks-key-alias debug --out "$OUT/$NAME" "$OUT/aligned.apk"
fi
"$BT/apksigner" verify --min-sdk-version 23 "$OUT/$NAME" >/dev/null  # (stdout: v1 warnings about unsigned META-INF files)
rm -f "$OUT/aligned.apk" "$OUT/$NAME.idsig"
echo "built: $OUT/$NAME (version $VERSION, code $CODE, $(du -h "$OUT/$NAME" | cut -f1))"
