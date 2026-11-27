#!/usr/bin/env bash
# Headless GUI smoke test: launch the app under Xvfb, screenshot the
# window, and check the window actually rendered (non-blank pixels).
# Run from apps/desktop: bash packaging/smoke-test.sh [shot.png]
# Requires: Xvfb, ffmpeg, npm install done.
#   FINEPRINT_CLI=/path/to/fineprint bash packaging/smoke-test.sh
# Passes when: the app process stays up for 12s and the screenshot
# has more than 1000 distinct colors (a real rendered UI, not a black
# or blank screen). Exit 0 = pass, 1 = fail.
set -euo pipefail
cd "$(dirname "$0")/.."

SHOT="${1:-/tmp/fineprint-smoke.png}"
DISPLAY_NUM="${SMOKE_DISPLAY:-98}"
export DISPLAY=":$DISPLAY_NUM"
CLI="${FINEPRINT_CLI:-tests/stub-cli/fineprint}"

command -v Xvfb >/dev/null 2>&1 || { echo "FAIL: Xvfb not found" >&2; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "FAIL: ffmpeg not found" >&2; exit 1; }

# Electron refuses to run as root without --no-sandbox (container/CI
# only; a real Mac/Windows install does not need it).
ELECTRON_FLAGS=""
if [ "$(uname -s)" = "Linux" ]; then ELECTRON_FLAGS="--no-sandbox"; fi

Xvfb ":$DISPLAY_NUM" -screen 0 1280x800x24 > /tmp/fineprint-xvfb.log 2>&1 &
XVFB_PID=$!
cleanup() {
  kill "$APP_PID" 2>/dev/null || true
  kill "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT
sleep 2

FINEPRINT_CLI="$CLI" timeout 30 npx electron . $ELECTRON_FLAGS > /tmp/fineprint-smoke-app.log 2>&1 &
APP_PID=$!
sleep 12
ffmpeg -y -loglevel error -f x11grab -video_size 1280x800 -i "$DISPLAY" -frames:v 1 "$SHOT"

if ! kill -0 "$APP_PID" 2>/dev/null; then
  echo "FAIL: the app exited within 12s; see /tmp/fineprint-smoke-app.log" >&2
  grep -iE "error|threw" /tmp/fineprint-smoke-app.log | grep -v "bus.cc\|viz_main\|gpu_process\|zygote\|network_service" | head -5 || true
  exit 1
fi

python3 - "$SHOT" <<'EOF'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB')
colors = im.getcolors(maxcolors=1000000)
n = len(colors) if colors else 1000001
print(f"screenshot: {im.size}, distinct colors: {n if colors else '>1M'}")
sys.exit(0 if n > 1000 else 1)
EOF

echo "PASS: app stayed up and rendered a real window (screenshot: $SHOT)"
