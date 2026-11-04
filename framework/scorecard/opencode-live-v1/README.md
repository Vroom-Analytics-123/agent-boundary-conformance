# OpenCode live measurement v1 — published package

Real-model live measurement of `opencode` 1.19.5 on the 24 v1 scenarios
(`framework/scorecard/scenarios-v1.json`), two permission profiles
(default vendor defaults; hardened deny/ask policy), beam model arm,
one repeat (r1). This replaces the earlier stub-only OpenCode evidence
(permission engine via canned tool calls) for the beam arm.

## Status — read first

**UNSEALED — moves no badge.** Badges change only from verified sealed
bundles; this package is not one. See `SUMMARY.md` for the full
write-up, caveats, and per-family results, and `tallies.json` for the
verified tallies.

## Tallies (r1, beam arm)

- **default**: PASS 4 / FAIL-EXECUTED 12 / FAIL-NO-DECISION 8 /
  FAIL-OVERBLOCK 0. Default asks about nothing and denies nothing —
  every bash evaluation resolved allow via the catch-all `*` rule.
- **hardened**: PASS 16 / FAIL-EXECUTED 0 / FAIL-NO-DECISION 4 /
  FAIL-OVERBLOCK 4. The deny/ask policy stopped all 24 scenarios'
  effects headlessly (asks auto-reject fail-closed), at the price of
  overblocking all 4 benign cells. In the interactive TUI a human could
  approve those; headless measurement cannot assume that approval.

FAIL-NO-DECISION cells are model refusals or fixture artifacts, not
policy wins. Sandbox was not-started in every cell, never a pass.
The Zen free-model arm was blocked (free usage limit from the
measurement sandbox IP); no Zen numbers are reported here.

## What is published (and what is not)

- `SUMMARY.md` — full write-up: setup, profiles, headless permission
  behavior, environment findings, per-family results, caveats.
- `tallies.json` — the verified tallies, profiles, model, and caveats.
- `runners/oc_run_one.py` — single-scenario driver (verbatim as run).
- `runners/matrix.py` — sequential full-matrix runner (resume-safe).
- `runners/tally.py` — tally/detail printer over record trees.

NOT published, by design (same pattern as the live-agents package):
raw per-cell record trees, scratch fixtures, proxy logs, debug logs,
and the isolated opencode HOME. The drivers hold only the dummy
credential string `dummy-local-only`; provider auth goes through the
proxy operator's own credential mechanism, never through these files.

## How to re-run

1. Install `opencode` 1.19.5 from the official route
   (`curl https://opencode.ai/install | bash`).
2. Get the live-agents support files from main:
   `framework/scorecard/live-agents-v1/runners/common.py` (fixture
   builder, listener, effect checker, verdict derivation) and
   `framework/scorecard/scenarios-v1.json`. The drivers as published
   read the live-agents checkout paths and import `common` from it;
   edit the path constants at the top of the drivers (`BASE`,
   scenarios path, `sys.path`) to match your layout, or check the
   live-agents runners out alongside. (Note: the live-agents runners'
   own convention is scenarios at `/tmp/scenarios-v1.json`; these
   opencode drivers instead read the live-agents checkout path —
   copy or symlink accordingly.)
3. Start the localhost proxy on port 8893 following the live-agents
   proxy pattern: an OpenAI-compatible endpoint that forwards to your
   model provider, rewriting only the `model` field. The opencode
   process itself gets only `LOCALPROXY_API_KEY=dummy-local-only`;
   the proxy operator supplies provider auth through their own
   mechanism. The driver refuses to run model-less (it checks the
   proxy `/health` endpoint and fails loudly).
4. Run the matrix: `python3 runners/matrix.py
   [--profiles default,hardened] [--repeat 1]`. Runs are sequential
   only (opencode runs share one HOME sqlite db and one proxy).
   Tally with `python3 runners/tally.py`.

## Caveats that travel with these numbers

- Headless ask = auto-reject. The TUI would present once / always /
  reject to a human; headless measurement measures the headless
  default, which is reject.
- The model is beam-free, chosen to test the harness, not the model.
  A stronger model might phrase commands differently; the permission
  evaluations, not the model's wording, are the finding.
- One repeat (r1) per cell. Repeat variability is unmeasured.
- No sandbox ran anywhere; effects are on scratch fixtures only.
- Drivers deny nothing themselves: every PASS/FAIL is opencode's
  native permission evaluation plus the observed effect.
