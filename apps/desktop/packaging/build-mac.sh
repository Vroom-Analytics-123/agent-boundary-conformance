#!/usr/bin/env bash
# Build the macOS .app + .dmg. Run from apps/desktop.
#   bash packaging/build-mac.sh
# The .app is built with electron-packager (prebuilt darwin binaries),
# which works on Linux. The .dmg needs hdiutil (macOS) — on a Linux
# machine without it, the script builds the .app, verifies it, and
# says so plainly instead of faking a .dmg. The CI workflow
# (.github/workflows/desktop.yml) runs this script on macos-latest,
# where hdiutil exists and the .dmg is produced.
# The result is UNSIGNED — signing and notarization need an Apple
# Developer account (see README).
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="FinePrint"
OUT="dist"

echo "== packaging macOS .app =="
# No --icon: there is no .icns asset yet (see README "needs a real
# Mac/Windows machine" — a proper app icon is still to be made).
npx electron-packager . "$APP_NAME" \
  --platform=darwin --arch=x64 \
  --out="$OUT" --overwrite \
  --app-version=0.1.0 \
  --app-bundle-id=com.vroomanalytics.fineprint

APP_PATH="$OUT/$APP_NAME-darwin-x64/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: $APP_PATH was not created" >&2
  exit 1
fi
echo "built: $APP_PATH"
ls -la "$APP_PATH/Contents/MacOS/" | head -5
python3 -c "import plistlib; d=plistlib.load(open('$APP_PATH/Contents/Info.plist','rb')); print({k: d[k] for k in ('CFBundleName','CFBundleExecutable','CFBundleIdentifier') if k in d})"
# Sanity: the packaged app must contain the Electron binary and our code.
test -x "$APP_PATH/Contents/MacOS/$APP_NAME" || { echo "ERROR: no app binary in the bundle" >&2; exit 1; }
test -f "$APP_PATH/Contents/Resources/app/main.js" || { echo "ERROR: main.js missing from the bundle" >&2; exit 1; }
echo ".app verified: binary + main.js present."

DMG="$OUT/$APP_NAME-0.1.0-mac.dmg"
echo "== building .dmg: $DMG =="
if command -v hdiutil >/dev/null 2>&1; then
  hdiutil create -volname "$APP_NAME" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG"
  ls -la "$DMG"
  echo "done."
else
  echo "NO .dmg BUILT: hdiutil is macOS-only and is not available here."
  echo "The .app is built and verified at $APP_PATH."
  echo "Run this script on a Mac, or let the CI workflow (macos-latest) produce the .dmg."
  exit 0
fi
