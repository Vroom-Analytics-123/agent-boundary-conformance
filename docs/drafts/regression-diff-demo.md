# DRAFT — Agent Boundary Regression Check demo (DO NOT PUBLISH without founder approval)

> Status: **demo only**. This report demonstrates the *mechanism* of the
> version-diff wedge: the same corpus + the same policy, two harness versions,
> one list of decisions that changed. Every decision below is **REPRO**
> (measured through each build's own `execpolicy check`, never asserted).
> Nothing here is a claim about either Codex version's safety.

## Setup

| | A (pinned) | B (newer) |
|---|---|---|
| Build | `codex-cli 0.149.0` | `codex-cli 0.163.0` |
| Source | vendored, SHA-256 `bbc3341e…672827` (pin-verified via `tools/pin.py`) | `npm pack @openai/codex@0.163.0-linux-x64`, SHA-256 `399ff69c…c4215` (same upstream channel) |
| Corpus | post-fix 41-case corpus (`fixtures/fixtures.json`, corpus `2dc43a86…`) | same |
| Policy | post-fix `fixtures/policies/default.rules` (`9b83f89f…`) | same |
| Runner | `tools/diff_codex_versions.py` (new; stdlib only) | — |

Raw per-fixture JSON: `docs/drafts/regression-diff-0.149.0-vs-0.163.0.json`
(41 rows; each row carries both REPRO decisions, matched-rule counts, and an
`evidence_class: "REPRO"` label).

## Result

**0 of 41 decisions changed. 0 unparseable native outputs.**

| Decision | 0.149.0 (REPRO) | 0.163.0 (REPRO) |
|---|---|---|
| allow | 6 | 6 |
| prompt | 4 | 4 |
| forbidden | 11 | 11 |
| unknown | 20 | 20 |

## Honest reading

1. **The mechanism works.** Both builds answered all 41 probes through the
   same `execpolicy check` interface with parseable native output; the
   differ found no drift to report, and reports that plainly. A version-diff
   that cries wolf on format noise would be useless — this one is quiet
   because the engines agreed, not because it failed to look.
2. **The finding is stability, not coverage.** Fourteen minor versions apart
   (0.149.0 → 0.163.0), the policy engine's rulings on this corpus+policy are
   identical. That is evidence *for* the pinning discipline (a pinned version
   is a stable measurement basis), and it is the happy path for the
   regression-check wedge: when a future version DOES move a decision, this
   report names the exact fixture.
3. **What this does not show.** A 0/41 diff on one corpus does not prove the
   engines are identical — only that they agree on these 41 probes under this
   policy. A corpus weighted toward version-sensitive shapes (new pattern
   syntax, changed precedence) would be a stronger tripwire; corpus-v2
   (see `docs/corpus-realism-2026-10-22.md`) is the natural place to add it.
4. **Scope.** `execpolicy check` output format was stable across the two
   builds (same JSON shape; no `unparseable-native-output` cases). CLI flag
   compatibility was not exhaustively probed — only the check path this
   project uses.

## How to rerun

```bash
python3 tools/diff_codex_versions.py \
  tools/vendor/codex/0.149.0/bin/codex \
  /path/to/other/codex \
  --out docs/drafts/regression-diff-<a>-vs-<b>.json
```

Any legitimately obtainable build works; decisions are always REPRO-labelled
and unparseable native output is reported, never silently dropped.
