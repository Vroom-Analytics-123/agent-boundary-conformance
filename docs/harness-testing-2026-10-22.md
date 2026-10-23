> **Supersession note — 2026-10-22 (founder model correction):** this is a dated record; its measured facts stand, but its Grade A/B/C and T1/T2/T3 ranking language is superseded. Grades/tiers are abolished as harness rankings — ease of measurement never makes a harness better or worse. The labels were provenance of the Layer-1 measurement only, now named unranked: 'vendor-confirmed' (the vendor's own checker answers: Codex, Amp), 'reconstructed' (evaluated from documented semantics: Claude Code, Cursor, Gemini CLI, OpenCode; Copilot reconstructed-from-configuration, account-walled), 'no paper surface' (Pi, Muse Code). The framework is the three layers — Layer 1 = what the rules decide, Layer 2 = the approval moment, Layer 3 = what actually happens (observed effect, ground truth, the most important layer). See `docs/FRAMEWORK.md`.

# All-harness empirical testing wave — 2026-10-22

*Founder direction: test all the harnesses at honest tiers, continuously (no date gating).
Status: per-harness evidence landed; consolidated here. Nothing published.*

## What this wave changed

The M5 (Day-4) tiering was documentation-based for the four non-Codex harnesses.
This wave executed the corpus against each harness through the **best honest route
available without any account or login**: a native oracle if one was found, otherwise
a labelled T2 config-evaluation engine unit-tested against every worked example in
the vendor's own documentation. Every non-Codex result is labelled
**T2-evaluation (never interrogated)**. No harness changed tiers on the basis of
this wave alone — the evidence *behind* each assignment upgraded from
documented-semantics to measured-evaluation. (Amp's T1 candidacy is a separate
spike, awaiting a founder decision; see `docs/amp-spike-2026-10-22.md`.)

Evidence classes follow the project scheme (DOC / REPRO / THIRD-PARTY /
INFERENCE / HYPOTHESIS). Raw per-harness evidence lives in
`adapters/<harness>/` (evaluate.py, TEST_LOG.md, results.json, policy/).

## Per-harness results

### Codex — T1 (already done, unchanged)
- Pinned oracle: `codex-cli 0.149.0` (vendored; sha256 `bbc3341e…`, fail-closed).
- Post-fix corpus (Evidence Upgrade A): 6 allow / 4 prompt / **11 forbidden** / 20 unknown (S-02, S-03 flipped unknown→forbidden by the two `prefix_rule` lines); measurement 40/41 PASS (single held-out bookkeeping artifact, disclosed); intent SATISFIED 10→12.
- Reference against which all other harnesses' divergences are stated.

### Claude Code — T2 (config-evaluation, measured)
- Version under test: `2.1.307`. Route: T2 (no native offline oracle exists at this version — CLI subcommands re-verified).
- Engine: `adapters/claude-code/evaluate.py`, **85/85 doc-cited tests pass** (every wildcard-table row and precedence example from the vendor docs).
- Corpus: 21 public per-case + 6 protected-asset cases; held-out 20 cases aggregated (allow 2 / unknown 10 / forbidden 6 / prompt 2).
- **13 headline divergences from Codex**: stricter compound-command handling, no host-executable path resolution, a built-in read-only set. Literal-string Bash matching confirmed — an invariant like "git push is blocked" that ignores flag reordering is a false pass under Claude's semantics (vendor docs themselves say such a rule "isn't a security boundary").

### Cursor — T2 (config-evaluation, measured, **Allowlist mode only**)
- Version under test: `2026.10.19-6bbf2c4`. Route: T2. Engine: 38/38 unit tests pass (every worked example in the permissions docs + precedence probes + no-match default).
- Corpus: 27 public cases + held-out aggregates. Default Auto-review mode is unevaluatable (stochastic classifier) — no verdicts emitted for it; scope stated up front.
- Headline divergence: **no prompt verb exists in Allowlist config** — F-15a/F-15b evaluate to *allow* under Cursor where Codex says *prompt*. A developer porting a "prompt on deploy" invariant to Cursor would silently get "allow". (INFERENCE on the mapping; measured evaluation.)

### Gemini CLI — T2 (config-evaluation, measured)
- Version under test: `0.65.0`. Route: T2. Engine: 33/33 tests pass.
- Corpus: 21 public + 6 protected-asset cases + held-out aggregates.
- **`--debug-policy` refuted at the pinned version**: the string is absent from the full 0.65.0 bundle — the third-party claim is not asserted.
- Headline divergence: **chain-splitting is protective where Codex is permissive** — F-11a evaluates *forbidden* under Gemini's per-segment validation where Codex allows. Precedence follows tier order (Admin > User > Default), matching the documented semantics the engine was built from.

### OpenCode — T2 (config-evaluation, measured, 1.x pinned)
- Version under test: `1.19.3` (baseline npm package; 1.x permission-object semantics). Route: T2. Engine: **43/43 tests pass** (`test_engine.py`).
- Corpus: 27 public cases + held-out aggregates (held-out results git-ignored).
- **Last-match-wins confirmed empirically**: order-swapping the policy flips 3 of 27 decisions (F-15a, F-15d, F-15f) — the sharpest contrast with Claude/Cursor deny-first. F-13d: unknown under OpenCode vs forbidden under Codex, because host-executable resolution is a Codex-layer concept with no OpenCode 1.x equivalent (evaluated on the literal command string; layer-coverage gap, not verdict-semantics difference).
- Ceilings kept: 2.x schema break (separate pass needed), undocumented command-parsing normalization, fresh-install near-total permissiveness (absence of config is decision-relevant).

### GitHub Copilot CLI — T2-config assessment (account wall)
- Version under test: `1.0.103` (installed via npm; install is NOT auth-walled). Offline binary inspection (read-only, scratch `COPILOT_HOME`) found no oracle-like entrypoint.
- **Account/subscription wall at `/login`** named as the blocker for any live evaluation; docs consulted and assessment recorded at `adapters/copilot-assessment.md`. No verdicts emitted. Tier assignment: T2-config (documented semantics evaluatable), ceilings stated.

### Meta Muse Code — T3 assessment (bonus, out of scope of the wave's original list)
- Version under test: `1.4.11` (muse-stable channel; binary inspected, read-only). No deterministic offline decision oracle located in the CLI surface or official docs.
- Tier: T3 — surface recorded, defaults recorded, **no verdicts**. Recorded at `adapters/muse-code-assessment.md`.
- Naming note: this is Meta's *terminal coding agent* (`muse` binary), not the Muse personal assistant — different products, different surfaces.

## Cross-cutting findings (new, measured)

1. **Precedence confirmed non-uniform, now measured**: Claude deny→ask→allow (fixed order) · Cursor deny-over-allow · Gemini tier-ordered · OpenCode last-match-wins (order flips demonstrated: 3/27) · Codex most-restrictive-wins (both rule orders, 6/6). A shared invariant schema must never assume a common precedence operator — this was an INFERENCE on DOC at M5; it is now MEASURED on T2 engines.
2. **Prompt is not portable**: Cursor's Allowlist vocabulary has no prompt verb; porting a prompt-expecting invariant there silently degrades to allow. The catalogue marks per-harness translation confidence accordingly.
3. **Chain-splitting cuts both ways**: Gemini's per-segment validation is protective (F-11a) where Codex's head-only compound handling is permissive (N1) — protective gaps and permissive gaps live in different harnesses, so "which harness is safer" is not a well-formed question; only per-invariant, per-harness conformance is.
4. **Account walls are the binding constraint on live testing**, not technical oracle absence: Copilot's evaluation route is documented but every live probe needs `/login`. FinePrint's method works up to the wall; the wall itself is a publishable field finding.

## What this wave does NOT change

- No T1 promotions except via the separate Amp spike (awaiting founder decision).
- No harness is certified safe; no verdicts for T3 surfaces; negative results remain publishable.
- The Day-7 kill criterion still rests on Codex T1 evidence; this wave's evidence strengthens the *program*, not the verdict.
