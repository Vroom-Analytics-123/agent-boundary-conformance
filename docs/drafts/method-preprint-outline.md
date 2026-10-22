# DRAFT — Method preprint outline (DO NOT POST without founder approval)

> Status: **outline only**. No paper has been written or posted. Built from
> `docs/EXPLAINER.md` (canonical method text) and `docs/LIMITATIONS.md`
> (what the evidence does NOT support). Every section below must keep the
> evidence classes (DOC / REPRO / THIRD-PARTY / INFERENCE / HYPOTHESIS) and
> the limitations on its face — a conformance paper that hides its own
> coverage gaps has no standing.

## Working title options

1. *FinePrint: measuring what a coding agent's policy engine actually
   decides — a pinned-oracle conformance method with sealed evidence*
2. *Policy text is not policy effect: pre-registered conformance testing of
   declarative agent policy engines*
3. *From rulebook to ruling: a repeatable protocol for intent-vs-decision
   divergence in AI coding agents*

## Abstract (sketch, ~150 words)

Developers write declarative policies for AI coding agents ("`rm -rf` →
forbidden") but cannot tell, by reading the rulebook, which commands the
policy engine will actually decide — and which it will silently decline to
rule on. We present a conformance method: asset-specific invariants, a
three-layer decision model (rules / approval / sandbox), a pinned native
oracle (the harness's own policy checker at a fixed version), a
pre-registered probe corpus with a held-out split, Merkle-sealed evidence
bundles with negative controls, and a dual verdict that keeps *measurement
validity* separate from *intent coverage*. Applied to Codex's `execpolicy`
(`codex-cli 0.149.0`), 41 probes against a three-rule sample policy show
literal-token matching gaps (spelling variants undecided), opaque shell
wrappers, and sound most-restrictive precedence — with 22/41 probes returning
*unknown* (no rules-layer decision), a corpus property, not a field rate. All
artifacts, including a one-command replication kit, are archived for
independent replay.

## Section outline

1. **Introduction** — agents act, not just talk; the policy is the
   deterministic fence around a probabilistic worker; "good" is
   owner-contextual, so the vendor cannot ship complete defaults; defaults
   change silently between versions. Conformance = does the system behave
   the way it was specified to behave (building-inspector metaphor;
   IAEA/arms-control register for safety audiences).
2. **The decision-coverage gap** — policy text vs. policy effect; an unmatched
   rule is a *decision-coverage gap*, never a "bypass" (terminology section;
   this distinction is load-bearing for credibility).
3. **Method**
   - 3.1 Asset-specific invariants (INV-001..INV-005; protective intent vs.
     measurement expectation; INV-004 Option A: explicit unknown with layer
     attribution; INV-005: no-match is never allow).
   - 3.2 The layer model (rules / approval-policy / sandbox-effect; a result
     at one layer is never reported as a result about the whole system).
   - 3.3 The pinned native oracle (the harness's own checker, version-pinned,
     SHA-256-verified; the judge is the harness itself — no reimplementation).
   - 3.4 Pre-registration (hypothesis locked before the confirmation run;
     Day-1 exploratory → Day-2 pre-registered confirmation, stated honestly).
   - 3.5 Sealed evidence (Merkle roots, inclusion proofs, negative controls
     that must fail, detached Ed25519 signatures; unsigned/unwitnessed as
     honest first-class states).
   - 3.6 The dual verdict (measurement validity PASS/FAIL/NOT_REPRODUCED ⊥
     intent coverage SATISFIED/.../UNRESOLVED; a correct unknown is a
     successful measurement, never a satisfied intent).
   - 3.7 Replication kit (one-command PASS/DIFF; self-test protocol).
4. **Measurement** — corpus design (41 synthetic probes weighted toward
   variants/wrappers + 11-case protected family + held-out split);
   pre-fix results (allow 6 / prompt 4 / forbidden 9 / unknown 22);
   post-fix results (two spelling-variant cells → forbidden; wrappers stay
   unknown per INV-004); six byte-identical reruns; precedence 6/6.
5. **Baselines** — harness-eval and agent-security-harness cannot express the
   fixture form (verified interface facts at pinned versions); Snyk Agent
   Scan not tested (blocked on founder token — stated, not worked around);
   the gap is narrow and real: nothing else does intent→native-decision
   conformance on this corpus.
6. **Limitations** (full section, not an appendix) — single measured harness
   (Codex T1; T2 harnesses unmeasured); synthetic corpus (the 54%→49% unknown
   share is a weighting artifact); rules-layer only (effect-closure pilot
   blocked on auth — reported, not hidden); modest absolute novelty.
7. **Related work** — GuardFall (Adversa AI, Jun 2026: measured guard-vs-shell
   divergence on open-source agents — ends any "first to measure" claim);
   openai/codex#44964 and #30868 (third-party reports of shell-wrapper
   brittleness, not reproduced by us); the surviving claim: the *pinned
   native declarative policy engine vs. declared invariants* protocol with
   unknowns attributed, signed evidence, and cross-version regression.
8. **Conclusion** — the method, the replication artifact, and the open gates
   (T2→T1 promotion, real-policy corpus-v2, runtime effect layer).

## Target venues (to decide with founder)

- Workshop: e.g. an AI-evaluation / agent-safety workshop (short paper).
- Preprint server only (arXiv cs.SE / cs.CR) if venue timing conflicts with
  grant deadlines — never both submitted simultaneously without disclosure.

## What must happen before writing

- [ ] Founder approves the narrowed novelty claim (protocol, not discovery)
- [ ] Corpus-v2 adoption decision (real-policy fixtures would strengthen §4)
- [ ] At least one T2→T1 promotion *or* an explicit single-harness framing
       decision for the paper's claims
- [ ] Author list, affiliations, license confirmed (same checklist as Zenodo)
