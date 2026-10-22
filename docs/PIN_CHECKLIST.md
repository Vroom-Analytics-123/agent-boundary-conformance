# Pin Checklist — Agent Boundary Conformance

*The discipline that keeps every number replayable. Written Day 5 (2026-10-21)
after the environment replaced the pinned oracle mid-session (Day 4); the
pin system caught it by design.*

Before any oracle work runs — and before any bundle is sealed — ALL of the
following hold. Each run records the pin block in its rerun JSON and each
bundle records it in `pinned.*`.

## The checklist

1. **Harness version pinned.** The exact version string is recorded with
   every run (e.g. `codex-cli 0.149.0`), never "latest".
2. **Oracle binary pinned and vendored.** The binary's sha256 is pinned
   (Day-2 pin: `bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827`).
   A copy of the pinned binary (or a reproducible fetch recipe + verified
   sha256) is vendored at `tools/vendor/<harness>/<version>/` BEFORE any
   oracle work runs. Tooling resolves the oracle through `tools/pin.py`,
   which prefers the vendored copy and fails closed on sha256 mismatch.
   No oracle work may run on an unpinned binary — a binary swap is a stop,
   not a shrug. *(Added Day 5: the Day-4 swap was recoverable only because
   the wrapper's platform tarball turned out to be the distribution channel;
   nothing about that was guaranteed.)*
3. **Policy/config pinned.** The sha256 of every rules file actually used
   (`fixtures/policies/*.rules`) is recorded; rules files are part of the pin.
4. **Corpus pinned.** Fixture corpus hash-locked by content (canonical JSON,
   sorted by id — hash over content is fixed-point safe under stamping;
   never hash over stamped bytes). Corpus changes require a new
   pre-registration entry, locked BEFORE the run.
5. **Invariants pinned.** `security/invariants.yaml` sha256 recorded;
   invariants are frozen after the owner's review.
6. **Resolution flag pinned.** `resolve_host_executables` on/off is part of
   the pin — decisions differ between the two (F-13 vs F-13R).
7. **Runner version pinned.** The tool that produced the run
   (`tools/run_fixtures.py (v0 replay engine)` + corpus fixture count) is
   recorded in the rerun JSON.
8. **Semantic guards checked by the verifier.** The bundle verifier
   (`tools/verify_bundle.py`) must pass: unmatched never serialized as
   allow (INV-005), every unknown carries layer attribution (INV-004),
   negative controls fail as designed, and all pinned hashes match the
   files on disk.

## What "the pin system caught it" looks like (Day 4, real)

The environment replaced `/opt/hatch-image/bin/codex` (0.149.0,
`bbc3341e…`) with 0.164.0-alpha.9 (`38a8634b…`) AFTER the Day-4 run.
`verify_bundle.py` flagged binary drift on re-verification; sealed bundles
remained valid evidence OF THEIR PINNED RUNS. No oracle work ran on the
unpinned binary (week-1 pin discipline held). Day 5 restored 0.149.0 via
the npm platform-tarball channel, vendored it, and added this step.

## Runtime probes (pending)

Approval-policy + sandbox probes additionally pin `approval_policy`,
`sandbox_mode`, and working directory. Not yet run in week 1.
