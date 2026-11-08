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
  recipe with SHA-256 verification. The `gate` job runs the free
  gate (and the wall) in CI. The Action is the no-terminal surface:
  add one workflow file in the GitHub web UI, read red/green on the
  PR — see `docs/FREE_CHECK_ACTION.md`.
- **Free gate (`tools/fineprint_gate.py`, via `fineprint gate`).**
  A subprocess wrapper plus a CI step, adapted from the paid-product
  prototype's decision logic with symlink resolution added (decisions
  run on realpaths) and hash-chained JSONL audit logging. Default
  policy (since the wall branch): the protective denylist (antivirus
  for agents) — credential reads, destructive deletes, exfiltration
  of protected files, unapproved deploys, and the measured bypasses
  are blocked; normal work anywhere is allowed. Folder confinement
  is opt-in (`--confine` / policy `"mode": "confine"`). Limits stated
  plainly in `docs/FREE_GATE.md`.
- **Docs:** `INTEGRATION.md` (junior-dev integration guide with
  verbatim real outputs, in funnel order: Check → Action → Wall),
  `docs/FREE_CHECK_ACTION.md` (incl. the non-developer section),
  `docs/FREE_GATE.md`, `docs/UPSTREAM_FIX_LOOP.md` (Omnigent
  #12762 as the worked example; no upstream PR filed — upstream
  patches need the owner's per-PR approval).
- **Demo:** `assets/fineprint-check-demo.gif` (recorded with
  `demo/record-check-demo.sh`) — install → `fineprint check` on a
  harness that breaks a rule → verdict + bundle, plus `fineprint
  gate run` allowing a good command and blocking a bad one.

## Nov 8, 2026 — free wall (branch `free-wall`, from `free-check-gate`, unmerged)

- **Free wall (`tools/fineprint_wall.py`, via `fineprint gate run`).**
  The same command, now enforced by the wall: the agent runs inside
  a sandbox built from the OS `unshare` primitive (user + mount
  namespace; a network namespace in confine mode with no hosts).
  In denylist mode the protected targets are hidden (the wall walks
  the working directory, /tmp, /var/tmp, plus the well-known
  credential locations in $HOME — a protected file in another
  project directory is not hidden unless it is under the working
  directory or /tmp; see `docs/FREE_GATE.md` for the bound) and a
  localhost proxy forwards everything except denied hosts. In
  confine mode everything outside the allowed scope is hidden and
  egress is allowlisted (or none). The tripwire stays the fast
  pre-check; the wall is the enforcement — a script that reads a
  credential without naming it on argv is still denied. CAP_SYS_ADMIN
  is dropped before the agent runs, so it cannot unmount the covers.
  If `unshare` is missing the gate refuses (exit 3) rather than
  silently falling back to the tripwire.
- **Signed definition packs (`tools/fineprint_definitions.py`).**
  The denylist is a versioned pack (built-in v1, `2026-11-07`),
  signed with the maintainers' Ed25519 key (public key in
  `docs/SIGNING.md`, verified with `tools/ed25519.py`). The wall
  verifies the signature before applying a pack and never applies an
  unverified one — a bad or missing signature refuses the run.
  A new pack ships with a FinePrint release; `fineprint gate
  definitions` reports the version in force.
- **Notifications (`fineprint gate log`).** Every blocked attempt is
  a structured, deterministic event in the hash-chained audit log
  (what was tried, which rule stopped it, `deterministic: true`).
  `fineprint gate log --log audit.jsonl` renders it as readable
  notifications: `tried X → blocked by rule Y → will always be
  blocked`. The wall enforces scope (paths/hosts), not intent —
  in-scope misuse is Check's job.
- **Tests:** 12 wall tests + 7 definitions tests (TDD), plus the
  phase-1 gate/check/action tests updated for the denylist default
  (confinement tests now use `--confine` / `"mode": "confine"`).
  Two real bugs found while building it: the denylist walk from `/`
  took ~60s and matched public CA bundles as `*.pem` (the walk is
  now bounded to the working directory + /tmp + the well-known
  credential locations, ~1s, and the .pem rule matches key-named
  files only); and the hidden list passed as one env var exceeded
  the 128KB single-value limit (E2BIG — it is now passed as a file).
- **Demo:** `assets/fineprint-wall-demo.gif` (recorded with
  `demo/record-wall-demo.sh`) — the wall denying a script-read of a
  credential the tripwire would miss, an allowed command passing,
  and the notification/log line.
- **CLI contract (frozen for the desktop-app agent):** `fineprint
  gate run -- CMD` (exit 0 allow/pass-through, 2 deny, 3 error),
  `fineprint gate check --file/--host`, `fineprint init --gate`
  writes the policy file, the policy JSON shape, and the hash-chained
  JSONL audit log shape are unchanged. Additive only: `--confine`,
  `--no-wall`, `gate definitions`, `gate log`, and the wall entries'
  `rule` / `deterministic` / `mode` / `definitions` fields. **The
  default policy changed (flagged): it is now a protective denylist,
  not cwd-only.**

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
