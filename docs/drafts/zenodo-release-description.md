# DRAFT — Zenodo release description (DO NOT DEPOSIT without founder approval)

> Status: **draft only**. Nothing has been deposited, posted, or minted. This
> file is the release-notes text prepared for a future DOI deposit of the
> FinePrint (Agent Boundary Conformance) evidence release. Deposit requires
> the founder's explicit per-item approval (license choice, author list, and
> release scope are still open).

---

## Title (proposed)

**FinePrint: a pinned-oracle conformance method for coding-agent policy
engines — sealed evidence bundles, corpus, and replication kit**

## Version / date

`v0.1.0-pre` — <TBD: date of deposit>

## Description (for the Zenodo record)

This release archives the measurement artifacts of FinePrint, a local-first,
open-source conformance tester that maps a developer's security invariants to
the decisions a coding agent's *native* policy engine actually renders —
pass / fail / unknown, with evidence.

**What is in this deposit:**

- **The probe corpus** (`fixtures/`): a 41-case synthetic probe set
  interrogating one sample policy (three rules: `git status` → allow,
  `deployctl release` → prompt, `rm -rf` → forbidden) — direct forms,
  spelling variants, path forms, shell wrappers, chains, and routine
  positive controls — plus an 11-case protected-records family. 20 of the 41
  cases are held out (only their SHA-256 hashes are published) so tuning to
  the public shard is detectable. The corpus is deliberately weighted toward
  variant/wrapped forms to map decision coverage; the unknown share is a
  corpus property, not a real-world rate.
- **The pinned oracle recipe** (`tools/vendor/codex/0.149.0/VENDORED.md`):
  the exact `codex-cli 0.149.0` binary is identified by SHA-256
  (`bbc3341e…672827`) with a byte-reproducible `npm pack` fetch recipe. The
  binary itself is not deposited (258 MB); the recipe + hash reproduce it.
- **Sealed evidence bundles** (`evidence/`): Merkle-sealed
  (SHA-256, RFC-6962-style), pre-registered, negative-controlled bundles —
  the pre-fix Day-2 bundle and the post-fix bundle (Day-5 fix: two forbidden
  prefix rules for `rm -fr` / `rm --recursive --force`), each with inclusion
  proofs per finding and detached Ed25519 signatures (public key and
  fingerprint in `docs/SIGNING.md`).
- **The replication kit** (`tools/replicate.sh`, `REPLICATION.md`): one
  command that fetches the pinned oracle, reruns the corpus, rebuilds the
  bundle, and compares Merkle roots against the published expectations with
  a plain PASS/DIFF verdict. Self-tested from a pristine checkout (result
  recorded in `REPLICATION.md`).
- **Method and limitations** (`docs/EXPLAINER.md`, `docs/LIMITATIONS.md`):
  the plain-language method, the layer model (rules / approval / sandbox),
  the dual-verdict discipline (measurement validity vs. intent coverage),
  and a limitations page that states what the evidence does NOT support.

**Key results (REPRO, pinned `codex-cli 0.149.0`):** pre-fix, 22 of 41 probes
returned *unknown* (no rules-layer decision; never normalized to allow);
post-fix, the two intended spelling-variant cells flip to forbidden while
wrapped forms stay unknown per the decided invariant semantics (INV-004
Option A). Closest open-source baselines (harness-eval, agent-security-harness)
cannot express the fixture form (verified interface fact at pinned versions).

**What this is not:** a benchmark, a multi-harness index (single measured
harness: Codex T1), a runtime safety certification, or a vulnerability
disclosure. Every claim carries an evidence class and a pinned configuration;
read `docs/LIMITATIONS.md` before citing any number.

## Creators

<TBD — founder to confirm author list and affiliations>

## License

<TBD — founder to choose before deposit; no license file is committed yet>

## Related identifiers / references

- Method preprint outline: `docs/drafts/method-preprint-outline.md` (in-repo draft)
- Upstream prior art discussed in `docs/LIMITATIONS.md` §6 (GuardFall/Adversa AI;
  openai/codex issues #44964, #30868 — third-party, not reproduced)

## Pre-deposit checklist (all must be ticked by the founder)

- [ ] License chosen and `LICENSE` committed
- [ ] Author list + affiliations confirmed
- [ ] Release scope confirmed (which bundles: pre-fix and/or post-fix)
- [ ] Public key fingerprint re-verified against `docs/SIGNING.md`
- [ ] `REPLICATION.md` self-test result is current for the deposited tree
