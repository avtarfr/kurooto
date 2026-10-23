#!/usr/bin/env bash
# build.sh: build Kurooto's Android app without Gradle (aapt2 + javac + d8 + apksigner), for Android 6 and newer.
#
#   ANDROID_HOME=/path/to/sdk android/build.sh            build/kurooto.apk (or kurooto-debug.apk, see below)
#   android/build.sh --test                                the JVM tests: crypto against the shared vectors, the
#                                                          call page's speech bridge (what's heard, quoted safely),
#                                                          the cards' and location reminders' rules, and the
#                                                          notification buttons and local alarm rules
#                                                          and bedside mode's rules (brightness by the hour, hours)
#                                                          and opening Systems and the Notes map (ViewSeal, 0.7.0)
#
# Needs: an Android SDK (any recent build-tools and platform; the newest installed are used) and a JDK (javac).
# Signing: KUROOTO_KEYSTORE (path), KUROOTO_KEYSTORE_PASS and optionally KUROOTO_KEY_ALIAS (default "kurooto").
# Without them a throwaway debug key is made in build/ and the APK is named kurooto-debug.apk: fine for testing,
# but phones won't take it as an update to a release-signed app.
# The version comes from pyproject.toml: versionCode = ((major*1000 + minor)*1000 + patch)*10 + (rc number, or 9).
# Assets: android/assets plus the dashboard's own drawing code for Systems and the Notes map (0.7.0), copied in at build
# time from src/kurooto/web/static (views/*.html|js|css to assets/views/, the Public Sans files to assets/fonts/), so
# there's one copy of it in the repository. ViewsActivity serves them to its WebView.
# KUROOTO_APP_ID (optional): another application id, for a test build that installs beside the real app.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
OUT=$HERE/build
PKG=io/github/avtarfr/kurooto

crypto_test() {
  local t; t=$(mktemp -d)
  javac -nowarn -encoding UTF-8 -d "$t" "$HERE/src/$PKG/B64.java" "$HERE/src/$PKG/Crypto.java" "$HERE/src/$PKG/Seal.java" \
    "$HERE/src/$PKG/Speech.java" "$HERE/src/$PKG/Buttons.java" "$HERE/src/$PKG/AlarmPlan.java" "$HERE/src/$PKG/Dock.java" \
    "$HERE/src/$PKG/ViewSeal.java" \
    "$HERE/test/CryptoTest.java" "$HERE/test/SpeechTest.java" "$HERE/test/TodayTest.java" "$HERE/test/DockTest.java" \
    "$HERE/test/ViewsTest.java"
  java -cp "$t" io.github.avtarfr.kurooto.CryptoTest "$ROOT/tests/fixtures/call-vectors.json"
  java -Dfile.encoding=UTF-8 -cp "$t" io.github.avtarfr.kurooto.ViewsTest "$ROOT/tests/fixtures/call-vectors.json"
  java -Dfile.encoding=UTF-8 -cp "$t" io.github.avtarfr.kurooto.SpeechTest
  java -cp "$t" io.github.avtarfr.kurooto.TodayTest
  java -cp "$t" io.github.avtarfr.kurooto.DockTest
  # the check-in and quiz cards' and location reminders' rules (0.6.0)
  javac -nowarn -encoding UTF-8 -d "$t" "$HERE/src/$PKG/CardRules.java" "$HERE/src/$PKG/PlaceRules.java" "$HERE/test/CardsPlacesTest.java"
  java -cp "$t" io.github.avtarfr.kurooto.CardsPlacesTest
  rm -rf "$t"
}
if [ "${1:-}" = "--test" ]; then crypto_test; exit 0; fi

SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[ -n "$SDK" ] && [ -d "$SDK" ] || { echo "Set ANDROID_HOME to your Android SDK." >&2; exit 2; }
BT=$(ls -d "$SDK"/build-tools/*/ | sort -V | tail -1)
JAR=$(ls -d "$SDK"/platforms/android-*/ | sort -V | tail -1)android.jar
[ -f "$JAR" ] || { echo "No Android platform in $SDK/platforms." >&2; exit 2; }

VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)
read -r MAJ MIN PAT RC < <(python3 -c '
import re, sys
m = re.match(r"(\d+)\.(\d+)\.(\d+)(?:(?:rc|-rc\.?)(\d+))?", sys.argv[1])
print(m[1], m[2], m[3], m[4] or 9)' "$VERSION")
CODE=$(( ((MAJ * 1000 + MIN) * 1000 + PAT) * 10 + RC ))

rm -rf "$OUT/res" "$OUT/gen" "$OUT/classes" "$OUT/dex" "$OUT/assets" "$OUT"/*.apk
mkdir -p "$OUT"/{res,gen,classes,dex} "$OUT/assets/views" "$OUT/assets/fonts"
STATIC=$ROOT/src/kurooto/web/static
cp -R "$HERE/assets/." "$OUT/assets/"
cp "$STATIC"/views/*.html "$STATIC"/views/*.js "$STATIC"/views/*.css "$OUT/assets/views/"
cp "$STATIC"/fonts/public-sans-latin*.woff2 "$STATIC"/fonts/OFL.txt "$OUT/assets/fonts/"
RENAME=()
[ -n "${KUROOTO_APP_ID:-}" ] && RENAME=(--rename-manifest-package "$KUROOTO_APP_ID")

"$BT/aapt2" compile --dir "$HERE/res" -o "$OUT/res/res.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$JAR" --manifest "$HERE/AndroidManifest.xml" \
  --min-sdk-version 23 --target-sdk-version 35 --version-code "$CODE" --version-name "$VERSION" \
  -A "$OUT/assets" "${RENAME[@]}" --java "$OUT/gen" "$OUT/res/res.zip"
# Java 8 source against android.jar (not the JDK's library), so nothing desktop-only can slip in.
javac -source 8 -target 8 -bootclasspath "$JAR:$BT/core-lambda-stubs.jar" -Xlint:-options -nowarn -encoding UTF-8 -d "$OUT/classes" \
  $(find "$HERE/src" "$OUT/gen" -name '*.java')
"$BT/d8" --min-api 23 --lib "$JAR" --release --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && zip -q -j "$OUT/unsigned.apk" classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

if [ -n "${KUROOTO_KEYSTORE:-}" ]; then
  NAME=kurooto.apk
  "$BT/apksigner" sign --ks "$KUROOTO_KEYSTORE" --ks-pass env:KUROOTO_KEYSTORE_PASS --ks-key-alias "${KUROOTO_KEY_ALIAS:-kurooto}" \
    --out "$OUT/$NAME" "$OUT/aligned.apk"
else
  NAME=kurooto-debug.apk
  KS=$OUT/debug.keystore
  [ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storepass debugpass -keypass debugpass -alias debug \
    -keyalg RSA -keysize 2048 -validity 3650 -dname "CN=Kurooto debug" >/dev/null 2>&1
  "$BT/apksigner" sign --ks "$KS" --ks-pass pass:debugpass --ks-key-alias debug --out "$OUT/$NAME" "$OUT/aligned.apk"
fi
"$BT/apksigner" verify --min-sdk-version 23 "$OUT/$NAME"
rm -f "$OUT/base.apk" "$OUT/unsigned.apk" "$OUT/aligned.apk"
echo "built: $OUT/$NAME (version $VERSION, code $CODE, $(du -h "$OUT/$NAME" | cut -f1))"
