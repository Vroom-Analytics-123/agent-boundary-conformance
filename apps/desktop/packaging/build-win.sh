#!/usr/bin/env bash
# Build the Windows app. Run from apps/desktop.
#   bash packaging/build-win.sh
# The unpacked Windows app (FinePrint.exe + resources) is built with
# electron-packager (prebuilt win32 binaries) — this works on Linux
# and the output is verified below. The one-click NSIS installer is
# built with electron-builder: natively on Windows (no Wine needed
# there) and via Wine on Linux. Wine is not installed in this
# container, so the installer is NOT built here — the CI workflow
# (.github/workflows/desktop.yml) runs this script on windows-latest,
# where the NSIS installer is produced natively. The result is
# UNSIGNED either way — code signing needs a Windows certificate
# (see README).
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="FinePrint"
OUT="dist"

echo "== packaging Windows app (unpacked) =="
# No --icon: there is no .ico asset yet (a proper app icon is still
# to be made — see README).
npx electron-packager . "$APP_NAME" \
  --platform=win32 --arch=x64 \
  --out="$OUT" --overwrite \
  --app-version=0.1.0

APP_DIR="$OUT/$APP_NAME-win32-x64"
if [ ! -f "$APP_DIR/$APP_NAME.exe" ]; then
  echo "ERROR: $APP_DIR/$APP_NAME.exe was not created" >&2
  exit 1
fi
echo "built: $APP_DIR/$APP_NAME.exe"
ls -la "$APP_DIR" | head -8
test -f "$APP_DIR/resources/app/main.js" || { echo "ERROR: main.js missing from the bundle" >&2; exit 1; }
echo "Windows app verified: exe + main.js present."

echo "== NSIS installer =="
# electron-builder builds the NSIS installer natively on Windows (no
# Wine needed there — Wine is only the Linux way to run it). On Linux
# without Wine there is no installer here; the CI workflow
# (windows-latest) produces it natively. The result is UNSIGNED either
# way — code signing needs a Windows certificate (see README).
is_windows() {
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; *) return 1;; esac
}
if is_windows || command -v wine >/dev/null 2>&1; then
  npx electron-builder --win nsis --publish never
  # The installer lands at the top of dist/ (the unpacked app lives in
  # a subdirectory, so this glob only matches the installer).
  INSTALLER="$(ls dist/*.exe 2>/dev/null | head -n 1 || true)"
  if [ -z "$INSTALLER" ]; then
    echo "ERROR: electron-builder ran but produced no installer in dist/" >&2
    exit 1
  fi
  echo "built NSIS installer: $INSTALLER"
  ls -la "$INSTALLER"
else
  echo "NO NSIS INSTALLER BUILT: electron-builder needs Wine on Linux and it is not installed here."
  echo "The unpacked Windows app above is built and verified."
  echo "The CI workflow (windows-latest) produces the NSIS installer natively."
fi
echo "done."
