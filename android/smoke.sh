#!/bin/sh
# Smoke test on an emulator (CI: .github/workflows/android-emulator.yml): install, open the app, open a pairing link,
# and fail on any crash. Every step has a time limit, so a stuck emulator fails the test instead of hanging it.
# Usage: android/smoke.sh path/to/kurooto.apk
set -eu
APK=$1
PKG=io.github.avtarfr.kurooto
t() { timeout "$@"; }
t 30 adb logcat -c || true
t 180 adb install -r "$APK"
t 60 adb shell am start -n "$PKG/.MainActivity"
sleep 6
t 20 adb shell pidof "$PKG" >/dev/null || { echo "the app isn't running after launch"; t 30 adb logcat -d | tail -200; exit 1; }
SDK=$(t 20 adb shell getprop ro.build.version.sdk | tr -d '\r')
SHOTS=${SHOTS:-shots}
mkdir -p "$SHOTS"
shot() { t 30 adb exec-out screencap -p > "$SHOTS/api$SDK-$1.png" || true; }  # for a look at each screen (CI keeps them)
shot home
# a pairing link with a code nobody issued: the app must show an error, not crash
t 60 adb shell am start -a android.intent.action.VIEW -d "'kurooto://pair?c=NOTACODE&u=https://example.com'"
sleep 10
shot pair
t 20 adb shell input keyevent KEYCODE_BACK || true
t 60 adb shell am start -n "$PKG/.MainActivity"
sleep 4
# only Kurooto's own crashes count (old emulators' System UI sometimes crashes while booting)
if t 60 adb logcat -d -b crash -b main | grep -A 1 "FATAL EXCEPTION" | grep -q "Process: $PKG"; then
  echo "crash:"; t 60 adb logcat -d -b crash -b main | grep -A 30 "Process: $PKG"; exit 1
fi
if [ "$SDK" -ge 29 ]; then  # the dark theme too
  t 30 adb shell cmd uimode night yes || true
  t 60 adb shell am start -S -n "$PKG/.MainActivity" || true
  sleep 5
  shot home-dark
fi
echo "ok on API $SDK"
