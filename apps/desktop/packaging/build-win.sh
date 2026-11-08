#!/usr/bin/env bash
# Build the Windows app. Run from apps/desktop.
#   bash packaging/build-win.sh
# Two artifacts: the unpacked Windows app (FinePrint.exe + resources)
# and the one-click NSIS installer. How each is built depends on the
# machine, because the Windows metadata steps need Wine on Linux:
#
#   native Windows (windows-latest CI) or Linux WITH Wine:
#     unpacked app via electron-packager (version + icon applied with
#     rcedit), NSIS installer via electron-builder.
#   Linux WITHOUT Wine (this container):
#     unpacked app via electron-builder's "dir" target — it writes the
#     exe, then fails its asar-integrity resource update (exit 1) for
#     want of Wine. The exe itself is written before that step, so the
#     script tolerates the exit code and verifies the exe exists. The
#     NSIS installer is NOT built here; the CI workflow
#     (windows-latest) produces it natively.
#
# The result is UNSIGNED either way — code signing needs a Windows
# certificate (see README).
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="FinePrint"
OUT="dist"

is_windows() {
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; *) return 1;; esac
}
has_wine() { command -v wine >/dev/null 2>&1; }

echo "== packaging Windows app (unpacked) =="
# Icon: assets/fineprint.ico (made by packaging/make-icon.py). It is
# applied by electron-packager on Windows / with Wine, and by
# electron-builder's config for the NSIS installer. The Linux-built
# unpacked app (electron-builder dir target) carries the icon from the
# same config.
if is_windows || has_wine; then
  npx electron-packager . "$APP_NAME" \
    --platform=win32 --arch=x64 \
    --out="$OUT" --overwrite \
    --app-version=0.1.0 \
    --icon=assets/fineprint.ico \
    --ignore=^/dist/
  APP_DIR="$OUT/$APP_NAME-win32-x64"
else
  echo "NOTE: no Wine here — building the unpacked app with electron-builder (dir target); the NSIS installer comes from CI."
  # Tolerated exit 1: the exe is written, then the asar-integrity
  # resource update fails for want of Wine. Verified below.
  npx electron-builder --win dir --publish never || true
  APP_DIR="$OUT/win-unpacked"
fi
if [ ! -f "$APP_DIR/$APP_NAME.exe" ]; then
  echo "ERROR: $APP_DIR/$APP_NAME.exe was not created" >&2
  exit 1
fi
echo "built: $APP_DIR/$APP_NAME.exe"
ls -la "$APP_DIR" | head -8
# The app code lives loose (packager: resources/app/main.js) or packed
# (electron-builder: resources/app.asar). Verify one of them, and that
# main.js is inside the asar when packed.
verify_app_code() {
  local dir="$1"
  if [ -f "$dir/resources/app/main.js" ]; then return 0; fi
  local asar="$dir/resources/app.asar"
  if [ -f "$asar" ]; then
    if npx --no-install asar list "$asar" 2>/dev/null | grep -qx "/main.js"; then return 0; fi
    echo "WARNING: could not list $asar contents; checking the file exists only" >&2
    test -s "$asar" && return 0
  fi
  return 1
}
verify_app_code "$APP_DIR" || { echo "ERROR: app code (main.js) missing from the bundle" >&2; exit 1; }
echo "Windows app verified: exe + app code present."

echo "== NSIS installer =="
# electron-builder builds the NSIS installer natively on Windows (no
# Wine needed there — Wine is only the Linux way to run it). On Linux
# without Wine there is no installer here; the CI workflow
# (windows-latest) produces it natively.
if is_windows || has_wine; then
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
