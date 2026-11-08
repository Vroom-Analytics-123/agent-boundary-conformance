#!/usr/bin/env bash
# Record the demo GIF: virtual display + screen capture of the real app
# running the scripted demo flow (renderer/demo.js, --demo).
# Run from apps/desktop: bash packaging/record-demo.sh
# Requires: Xvfb, ffmpeg, npm install done, a `fineprint` CLI.
#   FINEPRINT_CLI=/path/to/fineprint bash packaging/record-demo.sh
# Output: assets/fineprint-app-demo.gif (960px wide, 10fps).
# The script waits for the window title to say "FinePrint demo — done".
set -euo pipefail
cd "$(dirname "$0")/.."

CLI="${FINEPRINT_CLI:-}"
if [ -z "$CLI" ]; then
  echo "Set FINEPRINT_CLI to the fineprint CLI to record against." >&2
  echo "Example: FINEPRINT_CLI=~/workspace/fineprint-free-check/fineprint bash packaging/record-demo.sh" >&2
  exit 1
fi
command -v Xvfb >/dev/null 2>&1 || { echo "Xvfb not found (apt install xvfb)" >&2; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg not found (apt install ffmpeg)" >&2; exit 1; }

DISPLAY_NUM=99
export DISPLAY=":$DISPLAY_NUM"
MARKER="$(mktemp /tmp/fineprint-demo-done-XXXXXX)"
rm -f "$MARKER"
export FINEPRINT_DEMO_MARKER="$MARKER"
MP4="$(mktemp /tmp/fineprint-demo-XXXXXX.mp4)"
GIF="assets/fineprint-app-demo.gif"
mkdir -p assets

# Electron refuses to run as root without --no-sandbox (container/CI
# only; a real Mac/Windows install does not need it).
ELECTRON_FLAGS=""
if [ "$(uname -s)" = "Linux" ]; then ELECTRON_FLAGS="--no-sandbox"; fi

cleanup() {
  kill "$XVFB_PID" 2>/dev/null || true
  kill "$FF_PID" 2>/dev/null || true
  kill "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "== starting Xvfb on $DISPLAY =="
Xvfb ":$DISPLAY_NUM" -screen 0 1280x800x24 &
XVFB_PID=$!
sleep 2

echo "== starting capture -> $MP4 =="
# -preset ultrafast: the container has ~1.5 shared CPUs and Electron
# takes most of them, so the default x264 preset (rc-lookahead ~40
# frames) encodes slower than realtime and muxes nothing for a long
# time — a recording came back a 48-byte file with no frames.
# ultrafast has almost no lookahead, so packets flow promptly.
# Quality does not matter: the GIF step palette-reduces to 256
# colours anyway.
ffmpeg -y -loglevel error -f x11grab -video_size 1280x800 -framerate 10 -i "$DISPLAY" -c:v libx264 -preset ultrafast -pix_fmt yuv420p "$MP4" &
FF_PID=$!
sleep 1

echo "== starting the app in demo mode =="
# A fresh user-data dir per recording so the feed starts empty and the
# demo reads as a first run (otherwise yesterday's feed entries show up
# in frame 1).
USER_DATA_DIR="$(mktemp -d /tmp/fineprint-demo-userdata-XXXXXX)"
FINEPRINT_CLI="$CLI" npx electron . --demo $ELECTRON_FLAGS --user-data-dir="$USER_DATA_DIR" > /tmp/fineprint-demo-app.log 2>&1 &
APP_PID=$!

echo "== waiting for the demo to finish (marker: $MARKER) =="
# The demo takes ~35-45s. The renderer calls fp:demo-done when the
# flow ends, which writes the marker file.
for i in $(seq 1 120); do
  if [ -f "$MARKER" ]; then
    echo "demo finished after ~${i}s"
    break
  fi
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "WARNING: the app exited before the demo finished; check /tmp/fineprint-demo-app.log" >&2
    break
  fi
  sleep 1
done
sleep 2
kill "$APP_PID" 2>/dev/null || true
sleep 1
kill "$FF_PID" 2>/dev/null || true
# Wait for ffmpeg to exit before converting: SIGTERM makes it write
# the moov atom, and converting a still-open file fails with
# "moov atom not found". A fixed sleep is not enough on a slow box.
for i in $(seq 1 30); do
  kill -0 "$FF_PID" 2>/dev/null || break
  sleep 1
done
sleep 1

if [ ! -s "$MP4" ]; then
  echo "ERROR: no capture was recorded ($MP4 is empty)" >&2
  exit 1
fi
echo "== converting to GIF: $GIF =="
# -ss 3 skips the first ~3s while the window is still opening (black
# frames) so the GIF starts on the app itself.
ffmpeg -y -loglevel error -ss 3 -i "$MP4" \
  -vf "fps=10,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse" \
  "$GIF"
ls -la "$GIF"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$GIF"
echo "done. Review $GIF before committing it."
