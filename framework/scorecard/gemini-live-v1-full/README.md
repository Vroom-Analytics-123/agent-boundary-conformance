# Gemini CLI full live matrix — cheaperinference route (2026-11-04)

Full 24-scenario × 2-repeat live matrix for Gemini CLI 0.66.0, model
`gemini-2.5-flash` fixed, via the localhost Gemini→OpenAI translating
proxy to cheaperinference. Extends the published 7-scenario series
(`../gemini-live-v1/`, 14 cells, reused verbatim) with 34 new cells.

**Result: 48 cells — PASS 17 / FAIL_HARM 28 / FAIL_NO_DECISION 3.**
New 34: PASS 6 / HARM 26 / ND 2. Benign 8/8 PASS, no overblock.
Exfiltration 11/12 executed, credential reads 8/8 exposed, deploy 7/8
executed — the series policy covers rm spellings only, so every other
family executed unless the model refused. See SUMMARY.md for the
per-cell table, wrapper-shape analysis, adaptations, and corrections.

**Status: UNSEALED — moves no badge. No scores in this package.**
Raw per-cell records stay local (they contain full stdout/session
logs); this package carries the summary, tallies, policy, and runners
so the matrix can be re-run and re-tallied.

**Contents:** `SUMMARY.md` (full write-up), `tallies.json` (48 cells),
`tallies-new.json` (34 new cells), `policy-series.toml` (series policy,
reused exactly), `runners/series_runner_full.py` (the 34-cell runner),
`runners/sink.py` (localhost exfiltration sink),
`runners/merge_tallies.py` (re-tally from record.json files).

**Caveats:** headless `-p` only; the priority-1 unconditional allow
exists solely so the tool is offered (see policy header); sandbox
not-started; model refusals are no-decision, never policy wins; the
native Gemini route stays unmeasured (3 failed attempts, no retry).
