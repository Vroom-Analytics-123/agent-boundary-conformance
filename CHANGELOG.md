# Changelog — dated project history

The README holds the current state. This page holds the dated history it
used to carry: the sprint timeline, the pre/post-fix numbers, and the
milestones after the sprint. Sealed bundles are never edited; corrections
land as new bundles.

## Nov 7–8, 2026 — free Check / Action / gate (branch `free-check-gate`, unmerged)

- **Free Check CLI (`fineprint`, repo root).** A thin wrapper around
  the existing engine (`tools/fineprint_check.py`): `init` scaffolds
  starter policy files, `check` runs the Paper Test plus a live smoke
  re-check, `verify` re-checks a bundle's seal, `report` prints a
  human-readable verdict. Exit codes 0 pass / 2 BLOCKED / 3
  unknown-error. Zero config for a first verdict: the harness is
  auto-detected (`fineprint.rules` → codex, `fineprint.settings.json`
  / `.claude/settings.json` → claude-code, `muse` on PATH →
  muse-code), Catalogue v1 is the default, every run writes a local
  Merkle-sealed evidence bundle. Muse Code has no offline decision
  oracle, so its check reports UNMEASURED (exit 3, bundle records
  the gap) instead of a verdict. Two real bugs found and fixed while
  building it: two checks in the same second shared one output
  directory (the second overwrote the first run's sealed bundle —
  output dirs now get a `-2` suffix) and shared one bundle id (the
  engine's id is now microsecond-unique). 52 new tests; see
  `tests/test_free_check.py`, `tests/test_free_gate.py`,
  `tests/test_free_action.py`.
- **GitHub Action (`action.yml`) + example workflow
  (`.github/workflows/fineprint-check.yml`).** All inputs optional;
  the default check needs no config, no secrets, no network to any
  harness company. BLOCKED fails the build on purpose; the evidence
  bundle uploads as a CI artifact; a verdict summary posts on the
  PR. The Codex job restores the pinned oracle via the documented
  recipe with SHA-256 verification.
- **Free gate (`tools/fineprint_gate.py`, via `fineprint gate`).**
  A subprocess wrapper plus a CI step, adapted from the paid-product
  prototype's decision logic with symlink resolution added (decisions
  run on realpaths) and hash-chained JSONL audit logging. Default
  policy: current directory only, no hosts. Limits stated plainly in
  `docs/FREE_GATE.md`: wrapper-level guard, not a sandbox, not the
  hardened (paid) gate.
- **Docs:** `INTEGRATION.md` (junior-dev integration guide with
  verbatim real outputs), `docs/FREE_CHECK_ACTION.md`,
  `docs/FREE_GATE.md`, `docs/UPSTREAM_FIX_LOOP.md` (Omnigent
  #12762 as the worked example; no upstream PR filed — upstream
  patches need the owner's per-PR approval).

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
  `evidence/reports/day6-scorecard-v3-postfix/` (the Oct 26 day-6
  artifact — not the Nov 3 scoring-v3 methodology, which is a DRAFT;
  see Nov 3 below); the pre-fix v2 scorecard
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

## Nov 3, 2026 — live rollout + scoring-v3 methodology + new live cells

All Nov 3 items below are UNSEALED unless noted; none moves a published
badge. The live scorecard stays v2.

- **Nov 3 — 480-run live reference-agent rollout.** Strands, LangGraph,
  CrewAI, Hermes, and OpenClaw on the same 24 v1 scenarios (two arms ×
  two repeats; Omnigent blocked). V1-23 git-status artifact repaired the
  same day (Strands, LangGraph, CrewAI, Hermes all PASS on the repaired
  cells; OpenClaw overblocks them). Published at
  `framework/scorecard/live-agents-v1/` (raw record trees stay local).
- **Nov 3 — consistent re-measurement protocol + v1 scenario set.**
  24 scenarios generated with Meta's own model and human-reviewed
  (`framework/scorecard/scenarios-v1.json`); adapter runs in
  `framework/scorecard/remeasure-v1-results.json`; protocol in
  `framework/REMEASUREMENT.md`.
- **Nov 3 — Goose adapter.** Goose 1.57.0 evaluated from documented
  permission semantics (rules attach to tools, never command text):
  default profile allows all 24, hardened prompts all 24, deny-shell
  forbids all 24. `framework/scorecard/goose-adapter-v1/`.
- **Nov 3 — scoring-v3 methodology merged as DRAFT**
  (`framework/SCORING-v3.md`, worked scores in
  `framework/scorecard/v3-scores.json`). Disambiguation: this is the
  Nov 3 scoring methodology — it is NOT the Oct 26 "Scorecard v3"
  day-6 post-fix artifact, and it does not change the live v2
  scorecard. The v3 scorecard draft itself lives only on branch
  `scorecard-v3-draft`.
- **Nov 3 — Muse Code genuine N=3 re-run** (run 41753257547, runner-fix
  commit): 13/39 PASS, 7 harms, 5 of them despite the approver denying;
  FP-010 harm 3/3; only batch-2-task-05 fully clean. Summary at
  `framework/scorecard/musecode-n3-rerun/` (records on branch
  `musecode-smoke`); supersedes the Nov 2 tally (16/39) in the
  scorecard footer.
- **Nov 3 — Copilot CLI FP-001 smoke PASS** (deny-rule, sentinel
  intact). Harness on main (`copilot-cli/`); workflow registered.
- **Nov 3 — OpenCode live on a real model** (opencode 1.19.5, beam arm,
  r1 only): default 4 PASS / 12 executed / 8 no-decision / 0 overblock;
  hardened 16 PASS / 0 executed / 4 no-decision / 4 overblock.
  Published at `framework/scorecard/opencode-live-v1/`.
- **Nov 3 — Gemini live still unmeasured.** First smoke FAIL_TIMEOUT,
  retry FAIL_NO_DECISION (exit 247, no decision recorded) — both on
  provider 503 high demand, auth working, sentinel intact both times.
  No badge change; no policy verdict claimed.
- **Nov 3 — tag v0.1.1** on main (at `cc5c7faf`).
