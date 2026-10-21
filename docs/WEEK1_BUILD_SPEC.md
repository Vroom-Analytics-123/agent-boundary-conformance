# Week-One Build Specification — Agent Boundary Conformance (v1, 2026-10-20, revision-2 scope)

**One-sentence purpose:** Prove that independent security invariants can reveal an actionable discrepancy between a developer's stated intention and a native harness decision — with clear limits and legitimate-action controls. Nothing more is promised in week 1.

## Scope (narrowed)
- **Harness:** Codex only (`codex-cli 0.149.0`, pinned). Claude Code = Day-4 feasibility spike only; if no safe, repeatable native testing surface exists, the gap is documented as `unknown` — no static adapter masquerading as a decision oracle.
- **Layers kept separate in every output:** (1) rules-layer decision (`execpolicy check`), (2) approval-policy outcome (only where a runtime probe actually ran, under pinned `approval_policy` + `sandbox_mode`), (3) observed effect (not in week-1 scope except a designed experiment, clearly labelled).
- **Exclusions:** no Laconic/petgraph/Jev/MCTS, no generic tool-content scanning, no automated merging of fixes, no SaaS backend, no cross-harness Index, no polished UI. CI only if the test suite is stable by Day 6.

## Interfaces & commands
- Invariants: `security/invariants.yaml` (`schema_version: boundary.v0`) — 5 invariants, frozen after Anish's Day-1 review (INV-004 expectation is his open decision).
- Policy under test: `fixtures/policies/default.rules` (Starlark `prefix_rule`).
- Native oracle: `codex execpolicy check --rules <file> [--resolve-host-executables] -- <argv…>` → JSON `{matchedRules[], decision?}`. No match = `matchedRules: []`, decision omitted (DOC).
- Pinned configuration recorded with every run: codex version, rules files, resolution flag on/off, `host_executable()` entries; runtime probes additionally pin approval policy + sandbox mode + working directory.

## Fixtures
F-01…F-15 as defined in `docs/DAY1_BASELINE_PLAN.md`: positive controls (legitimate actions that must stay allowed), negative controls, no-match cases, wrapped forms (decision-coverage family), path forms (run with resolution OFF and ON), precedence/overlap cases.

## Day plan & acceptance criteria
| Day | Work | Acceptance criterion |
|---|---|---|
| 1 (Oct 21) | Freeze 5 invariants + threat model; run reference tools on the same fixtures | `docs/COMPETITOR_BASELINES.md` + evaluation protocol written; matrix cells for unrun tools say "not tested" |
| 2 (Oct 22) | Minimal versioned schemas: invariant, finding, evidence | Fixture parser runs; pass/fail/unknown semantics honest (unmatched can never serialize as allow — INV-005) |
| 3 (Oct 23) | Codex decision adapter, version + config pinned | Replayable expected-vs-actual decision tests for all 15 fixtures |
| 4 (Oct 24) | Positive/negative controls, precedence tests, safe counterexamples; Claude feasibility spike | No claim rests solely on an unmatched rule; Claude outcome is an adapter or a documented `unknown` |
| 5 (Oct 25) | Propose ONE small reviewed policy/config change; rerun | Before/after evidence; no intended legitimate capability lost (positive controls still pass). **Fix diff needs Anish's approval before applying** |
| 6 (Oct 26) | Export JSON + readable standalone HTML report; CI only if stable | A third party can rerun the report from the repo alone |
| 7 (Oct 27) | Same-corpus comparison vs baselines; publish limitations | Written **go / narrow / stop** verdict supported by evidence |

## Semantics (non-negotiable)
- `unmatched` → reported as **unknown**, with layer attribution: "no rules-layer decision; runtime outcome depends on approval policy + sandbox under the pinned configuration."
- Never use "bypass / evasion / hole" for a rules-layer non-decision. Never call a decision a "secure" verdict. A model refusal, a policy-check result, and a prevented effect are different evidence types.
- Every claim carries an evidence class: DOC / REPRO / THIRD-PARTY / INFERENCE / HYPOTHESIS.

## Stop / pivot criterion (locked)
Continue to a public Index only if the sprint reproduces a useful discrepancy, or establishes a concrete repeatable coverage gap, that the closest open-source tools do not adequately expose on the same corpus. A negative result is acceptable research output — publish it honestly, offer fixtures/adapter upstream, and stop. It is not evidence of a commercial product.
