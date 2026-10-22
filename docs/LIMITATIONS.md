# Limitations — read before citing any result (Day-7, 2026-10-27)

Every claim in this repo carries an evidence class (DOC / REPRO / THIRD-PARTY /
INFERENCE / HYPOTHESIS) and a pinned configuration (harness version + rules files +
resolution flag). This page lists what the week-1 evidence does NOT support.
It is part of the repo on purpose: a conformance project that hides its own
coverage gaps has no standing to report anyone else's.

## 1. Single-harness evidence (Codex T1 only)

- Measured verdicts exist for exactly one harness: Codex (`codex-cli 0.149.0`,
  vendored pinned binary, sha256 `bbc3341e…`). REPRO, six agreeing runs.
- Claude Code, Cursor, Gemini CLI, OpenCode are **T2 (config-evaluation)**:
  no decision oracle exists, **no verdicts were measured** — their manifests
  say so explicitly. Nothing in this repo may be read as a verdict about
  any of them.
- The "public Index" concept is therefore unproven: an index needs ≥2 measured
  harnesses. The next evidence gate is a T2→T1 promotion (Amp is the leading
  candidate — the only vendor besides OpenAI with a shipped permission-test
  command), not more Codex runs.

## 2. Synthetic corpus — the 54% unknown rate is a corpus artifact

- The 41-case corpus is a **synthetic probe set deliberately weighted toward
  variant/wrapped forms** (spelling variants, shell wrappers, compound inputs).
  The 22-of-41 unknown share is a property of that weighting, **not** a
  real-world usage rate. Quoting "54% of commands get no rules-layer decision"
  without this sentence is misuse.
- 20 of the 41 cases are held out (only their sha256 is committed) so tuning
  to the public shard is detectable — but the corpus is still 41 cases, one
  policy file, one pinned version. It is a probe set, not a benchmark.

## 3. Pre-fix evidence — the Day-5 fix is NOT applied

- All sealed bundles and the Day-6 scorecard are **pre-fix**: the Day-5 fix
  diff (`docs/drafts/day5-fix.diff`, +2 prefix rules for `rm -fr` and
  `rm --recursive --force`) is AWAITING the founder's approval and was not
  applied. The scorecard says so on its face (`fix_status.applied: false`).
- Do not cite this repo's numbers as "the fixed policy" — cite them as the
  pre-fix baseline they are.

## 4. Rules layer only — no runtime verdicts

- Every finding is a **rules-layer** outcome (`codex execpolicy check`).
  Unmatched serializes as **unknown with layer attribution** ("no rules-layer
  decision; runtime outcome depends on approval policy + sandbox under the
  pinned configuration") — never allow, never a bypass/evasion/hole.
- No runtime probe under a pinned approval policy + sandbox mode was run in
  week 1. Nothing here says what any command would actually do when executed.

## 5. Baseline comparison — honest scope

- Re-verified Day 7 at pinned versions: harness-eval 8.0.1 (92 rules, 0 mention
  `execpolicy`, no argv/policy input) and agent-security-harness 4.28.1 (zero
  `execpolicy` / `codex` occurrences in its modules) **cannot express** the
  fixture form. That is a verified interface fact, not a claim that those
  tools are bad at their own jobs (setup lint; live-agent/protocol behaviour).
- Snyk Agent Scan 0.6.9 is **not tested** (hard-blocked without a `SNYK_TOKEN`
  from the founder's own account — flagged, never worked around). Its shipped
  Codex integration is MCP/skill *discovery*, not execpolicy evaluation (zero
  `execpolicy` occurrences in its package). The "cannot express" expectation
  for Snyk is INFERENCE from interface evidence, recorded only after an
  actual run per protocol — the matrix cells stay "not tested".
- OWASP Agent Security Regression Harness: concept review only (THIRD-PARTY),
  not tested.
- The comparison is therefore asymmetric by design: the baselines were never
  built to consume rules + argv. The gap finding is "nothing else does
  intent→native-decision conformance on this corpus" — a real, narrow gap,
  not a defeat of competitors at their own game.

## 6. Absolute novelty is modest

- The headline findings (literal-token spelling gaps S-02/S-03; most-restrictive
  precedence F-15; head-only compound evaluation N1; lexical basename resolution
  F-13d/F-14) are **documented engine semantics made visible**, not surprising
  discoveries. The contribution is the *method* — pre-registered corpus,
  pinned oracle, sealed Merkle bundles, negative controls, schema-enforced
  unknown semantics — applied to intent-vs-decision divergence, which no
  baseline in the set performs.
- The surviving novelty claim (scientific review, Oct 21): pinned native
  declarative policy engine interrogated against declared invariants, unknowns
  attributed by layer, signed evidence, cross-version — narrowed after GuardFall
  (Adversa AI, Jun 2026) ended the "first to measure guard-vs-shell divergence"
  claim. Cite the narrowed claim, not the broad one.
- Upstream prior art narrows it further: two third-party Codex issue reports,
  read directly from GitHub and **not reproduced by us** (THIRD-PARTY), document
  the same shell-wrapper brittleness class before our measurements —
  openai/codex#44964 (Sep 2026: managed `prompt`/`forbidden` rules on `rm`
  silently not firing for non-trivial or nested shell scripts, with
  author-reported actual deletions in that environment) and openai/codex#30868
  (Jul 2026: `prefix_rule` cannot express stable shell-wrapped test-command
  prefixes, pushing users toward overbroad `["/bin/zsh", "-lc"]` allows).
  See `docs/COMPETITOR_BASELINES.md` §7 for what each actually claims. Our
  contribution claim is therefore the rigorous, repeatable, versioned
  **measurement protocol** — developer-owned intent + explicit layer model +
  pinned native-oracle tests + portable evidence + independent replay +
  version-to-version regression — never the discovery of shell-wrapper
  brittleness itself.

## 7. Signatures and witnessing are honest placeholders

- Sealed bundles record `signature_state: "unsigned"` and
  `witness_state: "unwitnessed"` as first-class states, not silent gaps.
  Tamper-evidence today is Merkle-root + pre-registration hash-locking only.

## 8. What would change these limitations

| Limitation | Evidence that would lift it |
|---|---|
| Single harness | A T2→T1 promotion: vendor ships a deterministic offline policy-evaluation entrypoint at a pinned version; corpus rerun sealed |
| Corpus artifact | A second corpus sampled from real policy files / observed command traffic, pre-registered before running |
| Pre-fix | Founder approves the Day-5 diff → apply, re-lock, rerun 41 cases, re-seal, re-issue scorecard |
| Rules-layer only | Runtime probes under pinned approval_policy + sandbox_mode, labelled as layer-2 evidence |
| Snyk not tested | Founder supplies a token from his own account (or explicitly deprioritizes Snyk) |
| Unsigned/unwitnessed | Key-based bundle signatures + independent witness re-runs |
