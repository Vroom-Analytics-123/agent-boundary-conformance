# Recording the demo GIF

The demo GIF (`assets/fineprint-app-demo.gif`, embedded in the branch
README) is a screen recording of the real app running a real flow —
nothing is faked. The app has a scripted demo mode for exactly this:

```
electron . --demo
```

## What the demo does

With `--demo`, the app creates a throwaway folder (in the OS temp
dir) containing `work/note.txt`, `work/records.txt` (a FAKE protected
records file) and `secret/keys.txt` (a FAKE secret), then the renderer
drives the real UI with real clicks, at a reasonable pace:

1. Home — definitions card (`v2026-11-07`, 11 rules) + empty feed.
2. Check my setup — runs `fineprint check` in the demo folder.
3. The Wall — picks Codex, picks the demo folder, runs
   `cat <demo>/work/records.txt` inside the wall. The tripwire denies
   it (`DENY-RECORDS`, exit 2) before anything runs. The verdict
   banner, the audit log, the feed entry (with the rule and the
   "this will always be blocked" line), and the OS notification are
   all real.
4. Home — the feed shows the blocked item.
5. Settings — the definitions status.

The flow ends by setting `document.title` to
`FinePrint demo — done`, so a recording script knows when to stop.
The demo uses the CLI at `FINEPRINT_CLI` when set, else the
configured one. It never touches the user's real folders.

## Recording on a real Mac or Windows machine

```sh
cd apps/desktop
npm install
FINEPRINT_CLI=/path/to/fineprint npm start -- --demo   # or: electron . --demo
# Record the window with your OS screen recorder (QuickTime on macOS,
# Xbox Game Bar on Windows), ~1280x800, until the title says done.
# Convert to GIF, ~960px wide, ~10fps:
ffmpeg -i demo.mov -vf "fps=10,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse" assets/fineprint-app-demo.gif
```

## Recording in a Linux container (Xvfb)

```sh
# Prerequisites: xvfb, ffmpeg, and the Electron dependencies.
sudo apt-get install -y xvfb ffmpeg
cd apps/desktop
npm install
# Start the virtual display and the app under it:
Xvfb :99 -screen 0 1280x800x24 &
export DISPLAY=:99
FINEPRINT_CLI=/path/to/fineprint timeout 90 \
  ffmpeg -y -f x11grab -video_size 1280x800 -framerate 10 -i :99 \
  -i /dev/null -f lavfi -i anullsrc \
  /tmp/fineprint-demo.mp4 &
# (start the capture first, then the app in the same display)
FINEPRINT_CLI=/path/to/fineprint npx electron . --demo
# Wait for the window title to say "FinePrint demo — done", stop the
# capture, then convert to GIF as above.
```

A cleaner scripted version is `packaging/record-demo.sh` (starts Xvfb,
launches the app under it, captures with ffmpeg, converts to GIF, and
checks the demo finished). Run it from `apps/desktop`.

## What was verified where

- In-container (this repo's Linux container): the full unit +
  integration suite passes (see README), including the real-CLI
  integration tests. GUI rendering, the demo GIF capture, and the
  OS-notification rendering were attempted here — see the README's
  "What needs a real Mac/Windows machine" section for the honest
  status. If the GIF could not be recorded in-container, the steps
  above are what to run on a real machine — do not substitute a
  mock-up for the recording.
