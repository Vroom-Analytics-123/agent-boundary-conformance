# Day-2 pre-registration (hash-locked BEFORE the run)

Locked: 2026-10-22T00:30:03Z (UTC). Machine-readable: `2026-10-22-preregistration.json`.

This registration commits, before any Day-2 result exists:

- Corpus: 41 fixtures, corpus_version_hash `f802397753dd933ee089105f304d5e70e61501402d7e5267d5922290c9ffa8bc` (public 21 / held-out 20, stratified by expected decision).
- Oracle: codex-cli 0.149.0, binary sha256 `bbc3341e44c9ead3…`.
- Policy: `fixtures/policies/default.rules` sha256 `f9e801ed632f4df2…`; 6 precedence rule files pinned.
- Invariants: 5 (boundary.v0), sha256 `aa4fcb9f4271ff1b…`; INV-004 decided Option A (unmatched-reported-as-unknown with layer attribution).
- Thresholds: 41/41 pass; 4/4 negative controls must FAIL (a passing negative control = broken run); no unmatched may serialize as allow; every unknown carries layer attribution.

Deviations are logged publicly in the daily brief, never silently edited. Registration sha256: `8ea9eac32fde3fb04d375dcbd27a292502a42f981da4cd6ffa1a820e5e931bd6`.
