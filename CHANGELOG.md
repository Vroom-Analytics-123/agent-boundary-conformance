# Changelog — dated project history

The README holds the current state. This page holds the dated history it
used to carry: the sprint timeline, the pre/post-fix numbers, and the
milestones after the sprint. Sealed bundles are never edited; corrections
land as new bundles.

## Oct 20–22, 2026 — the sprint

- **Oct 21 — Day-1 baseline (exploratory).** 41 probe commands replayed
  against Codex's own policy checker (pinned codex-cli 0.149.0). Six
  independent runs agree byte-identically on the native decisions.
  Frozen raw outputs: `evidence/day1-baseline-2026-10-21/`.
- **Oct 21 — Day-2 pre-registered confirmation.** The explored hypothesis
  was confirmed under a hash-locked pre-registration (corpus, thresholds,
  inclusion rules; held-out corpus by stratified alternation), not
  discovered there. See `docs/preregistration/`.
- **Oct 22 — Day-5 fix, founder-approved and applied.** Two spelling
  variants of a forbidden command (`rm -fr`, `rm --recursive --force`)
  now decide **forbidden** instead of unknown, via two added `prefix_rule`
  lines. Wrapped/disguised forms stay unknown per INV-004 Option A.
- **Oct 22 — post-fix evidence sealed.** `evidence/postfix-2026-10-22/`:
  `bundle.json` (41-case corpus, Merkle root `5a974fe6…`) +
  `bundle-protected.json` (11-case family, Merkle root `29768240…`),
  both verifying clean, with detached Ed25519 post-seal attestations
  (sealed before signing existed, so `signature_state` honestly remains
  `unsigned`). Boundary Scorecard v3 POST-FIX at
  `evidence/reports/day6-scorecard-v3-postfix/`; the pre-fix v2 scorecard
  is kept alongside as history at `evidence/reports/day6-scorecard/`.
- **Oct 22 — Amp recognized as a second vendor-confirmed route.** Amp's
  shipped native offline decision oracle (`amp permissions test`, pinned
  0.0.1792680614-g8973a3) answers deterministically; sealed at
  `evidence/amp-2026-10-22/` (Merkle root `cb6eccf0…`, Ed25519-signed).
- **Oct 22 — Wave A expansion (founder-directed).** Six further targets —
  Omnigent, Hermes Agent, OpenClaw, LangGraph, Strands Agents, CrewAI —
  carry design-stage route dossiers and draft catalogue translations.
  All **UNMEASURED**.

## Pre-fix → post-fix numbers

| | allow | prompt | forbidden | unknown |
|---|---|---|---|---|
| Pre-fix (Day-1 baseline) | 6 | 4 | 9 | 22 |
| Post-fix (Oct 22) | 6 | 4 | 11 | 20 |

Post-fix measurement validity 40/41 (the single FAIL is S-02's
bookkeeping artifact: a held-out case whose expectation was frozen — its
native decision was reproduced exactly). Post-fix intent coverage: 12
satisfied · 21 unresolved · 8 not applicable, of 41 — a separate
denominator from measurement validity. Protected-records family: measurement
11/11 PASS, intent 3 satisfied · 8 unresolved, of 11. Negative controls:
4/4 stay healthy. The corpus is deliberately weighted toward tricky
variants — 54% unknown is a property of this probe set, never a real-world
rate.

## Oct 27, 2026 — verdict

**Verdict: NARROW** (see `docs/daily/2026-10-27.md`): the method is proven
on Codex evidence; a public multi-harness Index is not earned on the
current evidence. The repo stands as the method, limitations on its face
(see `docs/LIMITATIONS.md`).

## Oct 29–30, 2026 — public release + first live model integration

- **Oct 29 — repo flipped public under Apache-2.0** (LICENSE commit;
  copyright 2026 Anish Kumar), after a pre-flip audit. The program repo
  stays private.
- **Oct 30 — Nebius × NVIDIA integration.** Nemotron-3-Super on Nebius
  Token Factory proposes adversarial scenario variants
  (`tools/nemotron_scenarios.py`); the pinned codex execpolicy oracle
  returns the Decision verdict; the demo script
  (`tools/run_nemotron_demo.py`) adds the Effect observation in a
  throwaway sandbox. The Oct 30 live run (FP-001/002/003, 6 proposals):
  1 prompt verdict matching the model's prediction, 5 unknowns; token
  usage 3,576 total (439 prompt, 3,137 completion of which 2,515
  reasoning); sentinel intact. Evidence at
  `evidence/nebius-2026-10-30/demo-evidence.json`; write-up at
  `docs/NEBIUS_INTEGRATION.md`. The model is the scenario generator,
  never the judge.
