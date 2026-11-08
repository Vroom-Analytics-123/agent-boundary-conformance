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
drives the real UI with real clicks — SLOW, roughly 2-3x a normal
walkthrough pace, pausing after every step so every line, button,
and notification can be read clearly:

1. Home — definitions card (`v2026-11-07`, 11 rules) + empty feed (held ~7s).
2. Check my setup — runs `fineprint check` in the demo folder; the verdict is held ~6s.
3. The Wall — picks Codex, picks the demo folder, runs
   `cat <demo>/work/records.txt` inside the wall. The tripwire denies
   it (`DENY-RECORDS`, exit 2) before anything runs. The verdict
   banner, the audit log, the feed entry (with the rule and the
   "this will always be blocked" line), and the OS notification are
   all real. The block screen is held ~7s.
4. Home — the feed shows the blocked item. This is the final screen,
   held for ten seconds so the blocked entries can be read clearly.

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

## The second-opinion demo (`--demo-s1`)

The second GIF (embedded near the top of the README) shows the Home
feed with second-opinion verdicts: a model block, a model allow, and
a model error (fail-closed), each labelled "second opinion —
probabilistic" with the model name + version + the model's reason,
next to a deterministic `DENY-RECORDS` block (rule + "this will
always be blocked") for contrast, and the summary counting the two
layers separately.

It is a replay, not a live model run, and the README caption says
so: the feed is seeded from `assets/demo-second-opinion-log.jsonl`,
a real hash-chained audit log the real gate wrote with the real
bekko model (model load ~116 s, so a live run cannot be the demo).
The seeding goes through the same code path as a live run
(`audit.parseLogFile` + `feed.itemFromAuditEntry` in `main.js`,
`--demo-s1`), and `tests/test-feed-real-log.js` verifies the same
file's chain and rendering. The log was produced by
`/tmp/make_s1_real_log.py` (not checked in — a scratch script): one
Python process calling the gate's `run_guarded()` with `--no-wall`
(a `cat` of the protected records file for the deterministic block,
an `rm` the model blocked, a `cp` the model allowed, and an `rm`
with a bogus helper python for the fail-closed entry), with
`FINEPRINT_SECOND_OPINION_PYTHON` pointing at the venv that has
torch (`~/workspace/.venvs/s1-eval/bin/python`) and
`HF_HUB_OFFLINE=1`. Regenerate it the same way if the gate's entry
shape ever changes — do not hand-edit the file, or its hash chain
breaks and the test fails on purpose.

```sh
cd apps/desktop
bash packaging/record-demo-s1.sh
# FINEPRINT_CLI=/path/to/fineprint is optional: the feed is seeded,
# not run, but when given, the definitions card shows the CLI's
# version in force; otherwise it shows the built-in v2026-11-07 pack.
```

The script follows the main demo's Xvfb pattern with two fixes
learned while recording it (also applied to `record-demo.sh`):
`-preset ultrafast` on the capture (the default x264 preset encodes
slower than realtime on ~1.5 shared CPUs while Electron runs, and
the first recording came back a 48-byte file with no frames), and
waiting for ffmpeg to exit after SIGTERM before converting (the
moov atom is written on exit; converting a still-open file fails
with "moov atom not found"). The skip is `-ss 12`, not `-ss 3`:
under Xvfb Electron takes ~13 s to paint on this box. Check the
first frames after recording — if they are black, raise the skip;
if the top of the feed is cut, lower it.

## What was verified where

- In-container (this repo's Linux container): the full unit +
  integration suite passes (see README), including the real-CLI
  integration tests. GUI rendering, the demo GIF capture, and the
  OS-notification rendering were attempted here — see the README's
  "What needs a real Mac/Windows machine" section for the honest
  status. If the GIF could not be recorded in-container, the steps
  above are what to run on a real machine — do not substitute a
  mock-up for the recording.
