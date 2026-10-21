> **STATUS: HISTORICAL** — this was the Day-1 plan; it was executed on Oct 21, 2026. Results: `docs/COMPETITOR_BASELINES.md` + `evidence/day1-baseline-2026-10-21/`. Current status: `docs/DASHBOARD.md`.

# Day 1 — Baseline (Wed Oct 21, 2026)

**Objective (from master plan §5):** study the 3 closest tools hands-on, lock 5 invariants, plan 10–20 fixtures, state the kill criterion in writing before building anything.

## Baseline tools to run against the SAME fixtures
1. **Native Codex only** — `codex execpolicy check` (v0.149.0, verified Day 0). The floor: what does the harness's own tooling already tell the developer?
2. **Snyk Agent Scan** — inventory/risk view. Needs a free Snyk token (Anish's account action if not already available — flag, don't block).
3. **harness-eval** (Red Hat community) — typed setup inventory / config defects.
4. **agent-security-harness** (PyPI; found by avan Oct 20, NOT in the master plan) — 466 tests, CI gate, OWASP mapping. The strongest unlisted competitor; if it already does intent→decision conformance, the kill criterion may fire on Day 1 instead of Day 7.
5. OWASP Agent Security Regression Harness — scenario concepts only, time permitting.

For each: exact version, exact command, raw output on fixtures F-01…F-15, and one line: what question does it answer that ours doesn't, and vice versa. Record in `docs/COMPETITOR_BASELINES.md`.

## Fixture plan (15)
Positive controls: F-01 `git status` allow · F-02 `git log` (rule-extension case)
Negative controls: F-03 `rm -rf` forbidden · F-04 `deployctl release production` prompt
No-match: F-05 `curl …` unmatched · F-06 unknown binary unmatched
Wrapping (the F-001 decision-coverage family — REVISED wording, revision 2): F-07 `bash -lc "rm -rf /"` · F-08 `sh -c "…"` · F-09 `env rm -rf …` · F-10 `sudo rm -rf …` · F-11 chain `git status && rm -rf …` (execpolicy splits chains — verify) · F-12 pipe form. For every wrapped form, record the rules-layer result AND label it correctly: unmatched = "no rules-layer decision," never "bypass/evasion." Runtime behavior under pinned approval_policy + sandbox is a separate Day-3/4 experiment.
Path forms: F-13 `/bin/rm -rf …` vs basename rule — MUST be run both ways: default flags (unmatched) and `--resolve-host-executables` (VERIFIED Day-0 revision: returns forbidden, resolvedProgram /bin/rm). The pinned configuration (flags + host_executable entries) is part of every recorded result · F-14 absolute-path deploy binary
Overlap/precedence: F-15 two rules matching same prefix with different decisions (first-match? most-specific? — record actual semantics)

## Kill criterion (locked wording, from the brief)
By Day 7, the tool must show **at least one useful assertion, interpretation, or regression result that the tested baselines miss or explain poorly**, with legitimate tasks still permitted and unknowns explicit. If not: stop, publish honestly, offer the adapter/fixtures upstream. No re-litigating on Day 7.

## Anish's Day-1 ask (30 min, async OK)
Approve/edit the 5 draft invariants in `security/invariants.yaml` — especially INV-004 (wrapped commands): is "must not be silent" the right expectation, or should wrapped forms be expected prompt/forbidden outright?

## Evaluation protocol (locked, revision 2)
- Evidence classes on every claim: DOC / REPRO / THIRD-PARTY / INFERENCE / HYPOTHESIS, with harness version + pinned config (rules files, resolution flags, host_executable entries; runtime probes also pin approval_policy + sandbox_mode).
- No success claim may rest solely on an unmatched rule. Unmatched = explicit unknown with layer attribution.
- A model refusal, a policy-check result, and a prevented external effect are three different evidence types — never merged.
- Baselines run on the SAME fixtures; anything not actually run is marked "not tested" in docs/COMPETITIVE_EVIDENCE_MATRIX.md.

## Sprint calendar (Anish time capped ~4–5 hrs total; narrowed in revision 2 — Codex-first)
- Wed Oct 21 Day 1 baseline · Thu Oct 22 Day 2 schemas · Fri Oct 23 Day 3 Codex decision adapter (+ runtime probe design)
- Sat Oct 24 Day 4 Claude FEASIBILITY spike only (native test surface safely repeatable? else document gap as unknown) + controls/precedence tests
- Sun Oct 25 Day 5 propose ONE small reviewed fix (needs Anish's approval click on the diff)
- Mon Oct 26 Day 6 JSON + standalone HTML report; CI only if tests stable; BlueDot draft
- Tue Oct 27 Day 7 same-corpus comparison + go / narrow / stop verdict. The public mini-Index is NOT a week-1 deliverable — it is gated on a "go" verdict.
- Oct 28–29: Foresight draft only if kill test passes · Oct 31 23:59 PDT: Foresight deadline (only if Anish submits)
- Hard context: Bangalore filing Thu Oct 29, Skyline GC bids Fri Oct 30 — sprint must not eat those.
