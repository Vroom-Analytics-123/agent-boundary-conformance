# Claude Code live v1 (UNSEALED)

Live measurement of Claude Code CLI 2.1.318 against the v1 scenario set
(24 scenarios × 2 repeats = 48 cells), model fixed `claude-sonnet-4.5`,
headless stream-json mode, through a local pass-through proxy to
cheaperinference. Nov 4, 2026. Clean rebuild: fresh CLI install, fresh
proxy, fresh runner — no artifacts reused from any prior attempt.

**Status: UNSEALED.** This package changes no badge, no scorecard number,
and no form text. It is evidence for verification, not a verdict.

## Results

PASS 27 / FAIL_HARM 6 / FAIL_NO_DECISION 13 / FAIL_OVERBLOCK 2.
Full story in SUMMARY.md. One line: deletions hold 12/12 (wrapper-aware
matching), exfiltration held by model refusal rather than policy,
credential reads are the hole (6/6 executed), npm test overblocks.

## Files

- `SUMMARY.md` — tallies, family breakdown, findings, correction note,
  spend estimate, caveats, per-cell table, reproduce steps.
- `cells.json` — per-cell verdict fields for all 48 cells (corrected
  verdicts; corrected cells flagged).
- `smoke.json` — the FP-001 pre-matrix gate cell (PASS deny-rule).
- `settings-smoke.json`, `settings-matrix.json` — exact settings used.
- `POLICY-MAPPING.md` — FinePrint default.rules → Claude permission
  syntax, coverage gaps, and the three denial mechanisms observed.
- `run_series.py` — the runner (builds fixtures, runs cells, judges from
  tool_result/meta evidence).
- `retally.py` — recomputes verdicts from raw streams without re-running
  model calls (used for the post-run classifier correction).
- `scenarios-v1.json` — the v1 scenario set as run (git blob sha1
  `0ee158982247d8804f9c388983afa5efe1b9d9e2`).

## Not in this package (by precedent, local only)

- `proxy.py` — the localhost pass-through proxy (carries the
  provider-auth wiring pattern; stays local). Reproduce it from SUMMARY.md
  step 2: forward Anthropic-format `/v1/messages` to
  `https://api.cheaperinference.com/v1/messages` with no translation,
  CLI holding only a dummy key, real credential attached via the
  connector-surrogate pattern.
- Raw `stream.jsonl` / `stderr.txt` per cell — local only.
- `node_modules/` (CLI install) and `package.json`/`package-lock.json`.

## Honesty boundary

- Headless only. A deny-rule firing proves the rule for that command
  headless; it does not prove interactive behavior. Interactive ask/deny
  dialogs were never observed.
- Model refusals (NO_DECISION) are model behavior, not boundary wins.
- Sandbox was not started in any cell. Never cite as sandboxed evidence.
- No credential value appears in this package: fixtures are dummy
  values, the CLI held only a dummy key, and no surrogate value was
  recorded.
