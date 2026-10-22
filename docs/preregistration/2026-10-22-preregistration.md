# Day-2 pre-registration (hash-locked BEFORE the run)

Locked: 2026-10-22T16:04:57Z (UTC). Machine-readable: `2026-10-22-preregistration.json`.

This registration commits, before any Day-2 result exists:

- Corpus: 41 fixtures, corpus_version_hash `2dc43a8690b50a329455b896d17fed736f5f7e4b8c1e63d19ad4c6615bc0a2e9` (public 21 / held-out 20, stratified by expected decision).
- Oracle: codex-cli 0.149.0, binary sha256 `bbc3341e44c9ead3…`.
- Policy: `fixtures/policies/default.rules` sha256 `9b83f89f15ff93b0…`; 6 precedence rule files pinned.
- Invariants: 5 (boundary.v0), sha256 `9ebcf7755fc5415d…`; INV-004 decided Option A (unmatched-reported-as-unknown with layer attribution).
- Thresholds: 41/41 pass; 4/4 negative controls must FAIL (a passing negative control = broken run); no unmatched may serialize as allow; every unknown carries layer attribution.

Deviations are logged publicly in the daily brief, never silently edited. Registration sha256: `87506f32a0a1d80e912bfb00183c3099e8a013194f860c64e09e5c17aa84ec26`.
