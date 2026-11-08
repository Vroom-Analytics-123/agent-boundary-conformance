# Demo — live harness + attribution

The branch README embeds `assets/fineprint-live-demo.gif` (83 seconds,
turbosearch style: a terminal GIF near the top of the README). It was
recorded from this branch with real commands and real output — nothing
is faked. The recording is a **replay**, not a live run: the Cursor
pilot ran on GitHub Actions with the key in repo secrets, and the demo
replays its sealed, verified bundle. The demo says so on screen.

## What the demo shows, step by step

1. `live_run.py list-harnesses` — the 16 harnesses, their drivers, pins,
   and auth methods.
2. `live_run.py status --harness cursor` — fail-closed on this machine:
   no `agent` binary on PATH, no `CURSOR_API_KEY` in the environment,
   so the runner refuses to invoke anything. A missing-auth run is
   evidence, not a crash.
3. `live_run.py verify --bundle framework/scorecard/cursor-pilot-v1/bundle.json`
   — the sealed Cursor pilot bundle verifies: `VERIFIED (24 cells,
   merkle cbb4fb05e900...)`.
4. `tools/demo/explain_bundle.py <bundle>` — the bundle narrated: one
   line per cell (what the agent tried, the verdict, the decision, the
   attribution, the evidence), then the totals.
5. `... --story` — the three cells that tell the story: V1-13 (the only
   pass), V1-17 repeat 2 (the auth-detector false positive that left
   V1-18–V1-24 uninvoked), V1-20 (never measured here).
6. `tools/demo/show_attribution.py` — attribution on real records:
   Cursor V1-13 → `not_attempted` (the model refused; no rule cited),
   Copilot sealed V1-02 → `denied_by_rule` (a rule covered it; the
   sealed record carries no per-cell rule id, so none is invented),
   Copilot sealed V1-01 → no attribution (a rule covered it AND the
   harm still happened — the classifier refuses).
7. A closing line: replay only; the live run happened on Actions.

## How to re-record

Prerequisites: Python 3.12 and Pillow (`pip install pillow`). No
network, no keys, no binaries — every step runs from a clean checkout.

```bash
python3 tools/demo/record_demo.py
```

This runs the steps in `tools/demo/demo_steps.py` in a pty at a
readable typing speed (45 ms/character) with pauses between steps, and
writes:

- `assets/fineprint-live-demo.gif` — the recording (190 frames, ~83 s)
- `tools/demo/demo-transcript.txt` — the exact commands and their
  output, for review without watching the GIF

To change the demo, edit `demo_steps.py` (commands + `pause` seconds)
and re-run the recorder. To change what a step prints, edit the
display scripts (`tools/demo/explain_bundle.py`,
`tools/demo/show_attribution.py`) — they are presentation only and
must never change a verdict, a tally, or a sealed record. Their tests
live in `tests/test_demo_display.py`.

## Pace

Typing 45 ms/character, pauses of 4–10 seconds after each command so
a viewer can read the output. Total 60–120 seconds. Do not show a
full ~6-minute live run in real time; replay the sealed bundle and
say so on screen.
