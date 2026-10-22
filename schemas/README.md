# Boundary schemas v1 (Day 2, 2026-10-22)

Minimal versioned schemas formalized around the v0 runner's existing
input/output (`tools/run_fixtures.py`, `fixtures/fixtures.json`). They
describe what the runner already emits; they do not change runner behavior.
Revision-2 semantics are enforced at the serialization layer, in code
(`tools/schemas_v1.py`), with tests in `tests/test_schemas_v1.py`.

## Schema versions

| Schema | `schema_version` | What it describes |
|---|---|---|
| invariant | `invariant.v1` | A developer's stated security expectation (`security/invariants.yaml` v0 fields, versioned) |
| finding | `finding.v1` | One fixture's native decision vs its invariant: pass/fail/unknown + layer attribution |
| evidence-bundle | `evidence-bundle.v1` | A sealed run: findings, Merkle root, pinned hashes, negative-control outcome |

## Non-negotiable rules encoded (INV-005, INV-004)

1. **An unmatched fixture can never serialize as `allow`.** A native
   no-match (`matchedRules: []`, decision omitted) serializes as
   `unknown`, never `allow`. `tools/schemas_v1.py::serialize_native_decision`
   implements this; the test suite proves it across malformed inputs.
2. **INV-004 is decided (Anish, Oct 21): Option A.** A wrapped form with no
   rules-layer decision carries expected `unmatched-reported-as-unknown`
   WITH mandatory `layer_attribution`:
   "no rules-layer decision; runtime outcome depends on approval policy +
   sandbox under the pinned configuration." A finding that would serialize
   as bare `unknown` (no attribution) or as `allow` is rejected by the
   schema validator.
3. **Every claim carries an evidence class**: DOC / REPRO / THIRD-PARTY /
   INFERENCE / HYPOTHESIS, plus harness version and pinned configuration.

## Corpus split (scientific-review §e)

`fixtures/corpus_manifest.json` splits the 41-case corpus into a public
half (21) and a held-out half (20), stratified by expected decision
(allow 3/3, prompt 2/2, forbidden 5/4, unknown 11/11). The held-out shard
content is intentionally NOT committed (see `fixtures/HELDOUT_POLICY.md`);
only its SHA-256 is recorded in the manifest, the pre-registration, and
every evidence bundle. The Day-2 run executes all 41; findings are tagged
with their shard so public/held-out pass rates are reported separately.

## Pre-registration (scientific-review §e)

`docs/preregistration/2026-10-22-preregistration.json` hash-locks the
fixture corpus, expectations, thresholds, and inclusion rules BEFORE the
Day-2 run (committed in a separate commit prior to the run commit).
The evidence bundle re-verifies the corpus hash against the pre-registration;
any drift marks the bundle invalid.

## Hash-stamped bundles (evidence architecture §1–2, week-1 scope)

`tools/build_evidence_bundle.py` seals a run into
`evidence/day2-2026-10-22/bundle.json`: per-finding leaf hashes, an
RFC-6962-style Merkle root, inclusion proofs, and pinned hashes (binary,
rules, invariants, corpus, pre-registration). `tools/verify_bundle.py`
re-verifies offline. Signing/witnessing are explicitly NOT claimed in
week 1: the bundle records `signature_state: "unsigned"` and
`witness_state: "unwitnessed"` as first-class states (per the scientific
review, Area 4 — better an honest "unwitnessed" than a quiet pass).

## Negative controls (scientific-review §e)

`fixtures/negative_controls.json` holds 4 deliberately wrong expectations.
The bundle runs them through the same oracle path: a control is
*healthy* only when it FAILS (actual != expected). If any negative
control passes, the bundle status is `broken` and the run must be
reported as such.
