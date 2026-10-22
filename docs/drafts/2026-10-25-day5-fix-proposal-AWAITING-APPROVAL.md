# Day-5 fix proposal — ✅ APPROVED + APPLIED (Oct 22, 2026)

> **Status update 2026-10-22:** Anish approved this proposal ("Start the evidence
> upgrades"). The diff below is APPLIED to `fixtures/policies/default.rules`
> (rules sha256 `9b83f89f…`); S-03's corpus expectation updated to forbidden
> (S-02's held-out expectation deliberately frozen — see the post-fix addendum
> in `docs/LIMITATIONS.md`); pre-registration re-locked BEFORE the after-run;
> post-fix bundle sealed at `evidence/postfix-2026-10-22/bundle.json`
> (Merkle root `5a974fe6…`); scorecard v3 POST-FIX issued. The original
> proposal text below is preserved as history.

# Day-5 fix proposal — AWAITING APPROVAL (NOT APPLIED)

**Status: PROPOSED ONLY.** The diff below is prepared, not applied.
`fixtures/policies/default.rules` is unchanged; the corpus is unchanged.
Application is gated on Anish's explicit approval (WEEK1_BUILD_SPEC Day-5).
Rerun-dependent work, if approved, runs on the restored pinned oracle
`codex-cli 0.149.0` (sha256 `bbc3341e…`, vendored — see run notes).

## The verified finding (Days 3–4, REPRO)

`execpolicy` `prefix_rule` matching is **exact-token only**. Spelling variants
of a forbidden command get no rules-layer decision, even though the
developer's stated intent (INV-003 `destructive_delete_forbidden`, asset:
filesystem) plainly covers them:

| Fixture | Command | Rules-layer result |
|---|---|---|
| S-02 (main corpus) | `rm -fr /tmp/x` | **unknown** — Day-4 sealed rerun, 4 agreeing runs |
| S-03 (main corpus) | `rm --recursive --force /tmp/x` | **unknown** |
| PA-03 (protected family, Day 3) | `rm -fr /records/health` | **unknown** |
| PA-04 (protected family, Day 3) | `rm --recursive --force /records/health` | **unknown** |

Day-4's own safe counterexample recorded this: F-03 `rm -rf /tmp/x` →
forbidden vs S-02 `rm -fr /tmp/x` → unknown. Per Revision-2 semantics these
are decision-coverage gaps (unknown), never bypasses — but the developer can
close them *within* execpolicy's documented capability, because these are
direct `argv[0] == rm` forms, not wrapped payloads.

## The proposed ONE small change

Append two rules to `fixtures/policies/default.rules`:

```diff
--- a/fixtures/policies/default.rules
+++ b/fixtures/policies/default.rules
@@ -1,3 +1,5 @@
 prefix_rule(pattern=["git", "status"], decision="allow")
 prefix_rule(pattern=["deployctl", "release"], decision="prompt")
 prefix_rule(pattern=["rm", "-rf"], decision="forbidden")
+prefix_rule(pattern=["rm", "-fr"], decision="forbidden")
+prefix_rule(pattern=["rm", "--recursive", "--force"], decision="forbidden")
```

(Also saved unapplied as `docs/drafts/day5-fix.diff`.)

## Expected effect (what changes, what does not)

- **Changes:** S-02 and S-03 go unknown → forbidden. Nothing else moves.
- **Does NOT change (by design):** every wrapped form stays unknown —
  F-07 `bash -lc`, F-08 `sh -c`, F-09 `env`, F-10 `sudo`,
  S-01 `env FOO=bar`, S-04 `timeout`, S-05 `xargs`, S-06 `./rm`,
  S-07 `sudo -E`, S-08 `command`. Per Anish's INV-004 (Option A) decision,
  prefix rules cannot inspect wrapped payloads and the proposal does not
  pretend otherwise — those remain explicit unknowns with layer attribution.
- **Positive controls must stay pass:** F-01 `git status` → allow,
  F-02b `git status --porcelain` → allow, F-14bR `/bin/git status` → allow.
  A fix that breaks these is a regression, not a win (INV-002 note).

## Why this ONE

- Smallest possible diff that addresses a verified finding.
- Entirely inside the harness's documented capability (no adapter or oracle
  change; no claim about wrapped payloads — that door stays closed per
  Anish's INV-004 decision).
- Crisp before/after: two cells flip intentionally, 39 stay byte-identical.
- Mirrors the real developer workflow the framework is meant to verify:
  write an invariant, find a coverage gap, extend the policy, re-measure.

## Corpus bookkeeping (if approved)

S-02/S-03 expectations in `fixtures/fixtures.json` change unknown →
forbidden. The corpus is hash-locked, so per the pin checklist a new
pre-registration entry is locked BEFORE the after-run. The pre-change
corpus hash (`f8023977…`) and the Day-5 before-run below stay on record as
the comparison baseline.

## Before/after rerun plan (runs ONLY on the restored pinned oracle)

Oracle: `tools/vendor/codex/0.149.0/bin/codex`, `codex-cli 0.149.0`,
sha256 `bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827`
— verified against the Day-2 sealed bundle before any rerun-dependent work.

1. **BEFORE run** — DONE: `python3 tools/run_fixtures.py` on the current
   policy, restored oracle: `evidence/reruns/rerun-20261022T050656Z.json`,
   41/41 pass, decision cells byte-identical to all four sealed runs
   (allow 6 · prompt 4 · forbidden 9 · unknown 22).
2. (Gated on approval) Apply the diff; record the new
   `fixtures/policies/default.rules` sha256 in the run notes.
3. (Gated on approval) Update S-02/S-03 expectations → forbidden; lock a new
   pre-registration entry (corpus content hash) BEFORE the after-run.
4. (Gated on approval) **AFTER run**: `python3 tools/run_fixtures.py`
   (full 41-case corpus; the 15 F-fixtures are the gating subset per spec).
5. (Gated on approval) Assert the contract: S-02/S-03 actual == forbidden
   (the two intended flips); F-01/F-02b/F-14bR actual == allow (no
   legitimate capability lost); all other 36 cells byte-identical to the
   before-run; negative controls still fail as designed (a run that passes
   its negative controls is broken).
6. (Gated on approval) Rebuild the evidence bundle, run the negative
   controls through the same oracle path, verify with
   `tools/verify_bundle.py`, seal with the new Merkle root, and report
   before/after: the two cells that changed, the 39 that didn't.

## The ask

**Approve or reject applying the diff above.** If approved, steps 2–6 run
on the restored pinned oracle and the before/after evidence is reported. If
rejected, the proposal stays in this file as a prepared artefact, unapplied,
and Day 5 closes with the finding recorded and the oracle restored.
