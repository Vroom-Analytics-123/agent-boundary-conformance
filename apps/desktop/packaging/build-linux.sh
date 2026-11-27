#!/usr/bin/env bash
# Build the Linux app: the unpacked app plus the installers.
#   bash packaging/build-linux.sh
# The unpacked Linux app is built with electron-packager (prebuilt
# linux binaries). The installers — an AppImage and a .deb — are built
# with electron-builder, natively on Linux (no Wine, no macOS tooling).
# Both installers are UNSIGNED — these formats carry no signing
# identity the way .dmg/.exe do, and none is configured. The .deb
# metadata (maintainer, description) comes from package.json (author,
# description). The CI workflow (.github/workflows/desktop.yml) runs
# this script on ubuntu-latest.
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="FinePrint"
OUT="dist"

echo "== packaging Linux app (unpacked) =="
# Icon: assets/fineprint.png (made by packaging/make-icon.py).
npx electron-packager . "$APP_NAME" \
  --platform=linux --arch=x64 \
  --out="$OUT" --overwrite \
  --app-version=0.1.0 \
  --icon=assets/fineprint.png \
  --ignore=^/dist/

APP_DIR="$OUT/$APP_NAME-linux-x64"
if [ ! -x "$APP_DIR/$APP_NAME" ]; then
  echo "ERROR: $APP_DIR/$APP_NAME was not created" >&2
  exit 1
fi
echo "built: $APP_DIR/$APP_NAME"
test -f "$APP_DIR/resources/app/main.js" || { echo "ERROR: main.js missing from the bundle" >&2; exit 1; }
echo "Linux app verified: binary + main.js present."

echo "== AppImage + .deb installers =="
npx electron-builder --linux AppImage deb --publish never
# The installers land at the top of dist/ (the unpacked app lives in a
# subdirectory, so these globs only match the installers).
APPIMAGE="$(ls dist/*.AppImage 2>/dev/null | head -n 1 || true)"
DEB="$(ls dist/*.deb 2>/dev/null | head -n 1 || true)"
if [ -z "$APPIMAGE" ]; then
  echo "ERROR: electron-builder produced no AppImage in dist/" >&2
  exit 1
fi
if [ -z "$DEB" ]; then
  echo "ERROR: electron-builder produced no .deb in dist/" >&2
  exit 1
fi
echo "built AppImage: $APPIMAGE"
echo "built .deb: $DEB"
ls -la "$APPIMAGE" "$DEB"
echo "done."
