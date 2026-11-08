#!/usr/bin/env bash
# Record the second-opinion demo GIF: virtual display + screen capture
# of the real app showing the Home feed seeded from a RECORDED real
# gate log (assets/demo-second-opinion-log.jsonl — entries the real
# gate wrote with the real bekko model; see apps/desktop/main.js
# --demo-s1 and docs/RECORDING.md). It is a replay, not a live model
# run: the model takes ~2 minutes to load, so a live run cannot be
# the demo. The feed rendering is the same code path as a live run.
# Run from apps/desktop: bash packaging/record-demo-s1.sh
# Requires: Xvfb, ffmpeg, npm install done.
#   FINEPRINT_CLI=/path/to/fineprint bash packaging/record-demo-s1.sh
# (the CLI is optional here — the feed is seeded, not run — but when
# given, the definitions card shows the CLI's version in force;
# otherwise it shows the built-in v2026-11-07 pack.)
# Output: assets/fineprint-app-demo-second-opinion.gif (960px wide, 10fps).
# The script waits for the window title to say "FinePrint demo — done".
set -euo pipefail
cd "$(dirname "$0")/.."

CLI="${FINEPRINT_CLI:-}"
if [ -n "$CLI" ]; then
  echo "CLI: $CLI (definitions card)"
else
  echo "No FINEPRINT_CLI — the definitions card shows the built-in pack."
fi
command -v Xvfb >/dev/null 2>&1 || { echo "Xvfb not found (apt install xvfb)" >&2; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg not found (apt install ffmpeg)" >&2; exit 1; }
[ -f assets/demo-second-opinion-log.jsonl ] || { echo "assets/demo-second-opinion-log.jsonl is missing — regenerate it (see docs/RECORDING.md)" >&2; exit 1; }

DISPLAY_NUM=99
export DISPLAY=":$DISPLAY_NUM"
MARKER="$(mktemp /tmp/fineprint-demo-s1-done-XXXXXX)"
rm -f "$MARKER"
export FINEPRINT_DEMO_MARKER="$MARKER"
MP4="$(mktemp /tmp/fineprint-demo-s1-XXXXXX.mp4)"
GIF="assets/fineprint-app-demo-second-opinion.gif"
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
# time — the first recording came back a 48-byte file with no frames.
# ultrafast has almost no lookahead, so packets flow promptly and the
# file is usable even if the run is cut short. Quality does not
# matter: the GIF step palette-reduces to 256 colours anyway.
ffmpeg -y -loglevel error -f x11grab -video_size 1280x800 -framerate 10 -i "$DISPLAY" -c:v libx264 -preset ultrafast -pix_fmt yuv420p "$MP4" &
FF_PID=$!
sleep 1

echo "== starting the app in demo-s1 mode =="
# A fresh user-data dir per recording so the feed starts empty and the
# demo reads as a first run (otherwise yesterday's feed entries show up
# in frame 1).
USER_DATA_DIR="$(mktemp -d /tmp/fineprint-demo-s1-userdata-XXXXXX)"
if [ -n "$CLI" ]; then
  FINEPRINT_CLI="$CLI" npx electron . --demo-s1 $ELECTRON_FLAGS --user-data-dir="$USER_DATA_DIR" > /tmp/fineprint-demo-s1-app.log 2>&1 &
else
  npx electron . --demo-s1 $ELECTRON_FLAGS --user-data-dir="$USER_DATA_DIR" > /tmp/fineprint-demo-s1-app.log 2>&1 &
fi
APP_PID=$!

echo "== waiting for the demo to finish (marker: $MARKER) =="
# The demo holds the feed for ~15s, so the whole recording is ~25s.
for i in $(seq 1 120); do
  if [ -f "$MARKER" ]; then
    echo "demo finished after ~${i}s"
    break
  fi
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "WARNING: the app exited before the demo finished; check /tmp/fineprint-demo-s1-app.log" >&2
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
# -ss 12 skips the window opening: under Xvfb Electron takes ~13–17 s
# to paint on this box (it varied run to run), so the -ss 3 the main
# demo uses leaves black frames at the start here. The skip is
# startup-dependent — check the first frames of the GIF after
# recording; if they are black, raise it, and if the top of the feed
# is cut, lower it.
ffmpeg -y -loglevel error -ss 12 -i "$MP4" \
  -vf "fps=10,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse" \
  "$GIF"
ls -la "$GIF"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$GIF"
echo "done. Review $GIF before committing it."
