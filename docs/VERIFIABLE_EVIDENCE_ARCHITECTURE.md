# Verifiable Evidence Architecture — the technical core that makes this a big deal (v1, 2026-10-21)

Design principle: the tester's verdicts are only as valuable as their *provability*. Anyone can print "FAIL." Our results must be independently verifiable, tamper-evident, replayable, and anchored in time — without trusting us. This document defines that core, what is genuinely novel about it, and what deliberately is NOT in it (no token, no proprietary chain — see §5).

## 1. Event-sourced evidence core (the database/structure)
Every run is an **append-only event stream**, never mutable rows:
`InvariantDeclared → PolicyPinned(hash) → DecisionObserved(raw native output) → EffectObserved (probe stage) → VerdictAdjudicated → BundleSealed`.
- The materialized report is a *projection* of the stream — delete it and replay to byte-identical state (same determinism discipline as AnswerGraph's event core; shared semantics, separate repos).
- Storage v1: SQLite append-only tables (local-first). Later: the same event schema feeds the hosted evidence store unchanged.
- This buys: time-travel diffing (replay one policy across harness versions and diff the projections), forkable corpora (researchers branch fixture sets like git), and audit-grade reconstruction of "what exactly was known when this verdict was issued."

## 2. Merkle-rooted, signed, transparency-logged bundles (the cryptography)
- Each run's evidence bundle is hashed into a **Merkle tree** (RFC 6962-style leaf/node hashing — the Certificate Transparency construction); the bundle carries its root + inclusion proofs for every fixture result.
- Bundles are **signed (Ed25519)** by the runner; verification is offline and third-party: anyone can check that a result existed, unaltered, in a specific run.
- Roots are periodically anchored to a **public transparency log** — Sigstore/Rekor-compatible in approach (keyless signing + public append-only log), with optional OpenTimestamps-style public-chain anchoring of the root hash purely as a timestamp proof. Anchoring a hash is not "a crypto product"; it's a notary stamp.
- **The flywheel this creates:** every CI run anywhere can anchor its root into the public log. The log becomes the canonical, growing record of agent-permission decisions across versions and vendors — the Index stops being "our blog" and becomes *the ledger of record* others cite and build on. A transparency log is one of the few structures that genuinely gets more defensible with scale.

## 3. Divergence mining — minimal-counterexample search (the algorithm)
Hand-writing 15 fixtures proves a point; it doesn't scale and it isn't research. The research-grade engine:
- **Property-based generation** over the command/policy space (argv grammars, wrapper transforms, path forms, flag/config variation) searching for inputs where *stated intent ≠ native decision* — then **automatic counterexample minimization** (delta-debugging / shrinking, the QuickCheck/Hypothesis tradition): reduce a found divergence to the smallest command + config that still reproduces it.
- Output: minimal, human-readable divergence cases ("`rm -rf` is forbidden; `env rm -rf` receives no decision under this exact config") that drop straight into the corpus as fixtures.
- Why it's fundable and demo-able: it's a real open problem (nobody is fuzzing policy surfaces against intent), every find is a citable artefact, and the minimizer is what makes findings legible to humans and grant reviewers instead of fuzz noise.
- Sequencing: NOT week 1 (hand corpus first, to validate the semantics the fuzzer will search against). Phase 1–2 research track; the corpus design (EG-3/EG-5) anticipates it.

## 4. Effect closure (the graph algorithm, stage 2)
When effect observation lands: model invocations and their transitive effects (writes, spawns, network, hooks) as a directed graph; compute the **effect closure** per approved action (petgraph reachability) and compare closure vs the approval record — the operational form of the Transitive Effects paper's formalism. Divergence at this layer = CONTRADICTED candidates in EffectGap semantics.

## 5. Explicit non-goals (credibility protection)
- **No token, no proprietary blockchain, no consensus network.** They add no verification property that Merkle trees + signatures + an existing public log don't already provide, and they tax credibility with AI-safety funders and enterprise buyers alike.
- **No "trust us" server.** The hosted product sells retention, signing keys management, diff alerting, and support — never exclusive ability to verify. Verification stays free and offline forever; that's what makes the evidence admissible-grade.
- **No novelty overclaim:** transparency logs (CT, Rekor), event sourcing, and property-based testing are proven, borrowed machinery. The novel composition is applying them to *agent permission decisions vs stated intent*, plus the divergence-mining search and the public corpus that accumulates on top.

## 6. What this changes in the existing plan
- Week 1: only the parts already specced (hash-stamped bundles, event-shaped evidence). No schedule change.
- Phase 1: public anchoring of the launch corpus root + verification tooling shipped with the Scorecard (a skeptic can verify our launch stat — that's the press hook).
- Phase 2: divergence-mining prototype (grant-fundable research: BlueDot/TAIF narratives), hosted evidence store on the same event schema.
- Grant language addition: "public, verifiable measurement infrastructure" — every number we publish carries its own proof.
- VC language addition: "the transparency log for agent permissions" — a record that compounds with every anchored run and that platforms cannot credibly operate against themselves.


## 7. Improvements adopted (v1.1, 2026-10-21 — after backing review)
1. **Anchor, don't operate (at first).** Operating our own log from day one makes us the trust bottleneck we criticize. Phase 1 anchors corpus roots into *existing* public infrastructure where feasible and adds **independent witness cosigning** (Sigsum-style): witnesses countersign tree heads, so the log cannot silently fork or rewrite history. Our own operated log becomes a Phase-3 question, decided by volume, not ego.
2. **Keyless signing for CI runs.** Follow the Fulcio pattern that npm/PyPI provenance uses in production today: short-lived certificates from OIDC identity, no long-lived user keys. A developer's CI signs its conformance bundle the way it already signs packages.
3. **Interop over isolation.** Bundles emit **in-toto attestation format** and the reporter adds **SARIF export**, so evidence plugs into the existing supply-chain tooling (GitHub artifact attestations, SLSA verifiers) instead of demanding a new ecosystem. Distribution beats purity.
4. **Coverage-guided divergence mining.** The fuzzer's feedback signal is decision-surface coverage (which rules matched, which config branches were exercised) — borrow the coverage-guided fuzzing lesson (AFL lineage) rather than blind generation; minimization stays delta-debugging (Zeller) / shrinking (QuickCheck/Hypothesis).
5. **Replication bounties (Phase 2).** Small paid bounties for independent replications of Index numbers. Credibility is the product; buying verification is cheaper than buying marketing.
