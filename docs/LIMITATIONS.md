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
  (Post-fix, 2026-10-22: 20-of-41 unknown — S-02/S-03 now decide forbidden.
  The weighting caveat is unchanged.)
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

### Addendum (2026-10-22) — the Day-5 fix is now APPLIED; post-fix evidence sealed

The founder approved the fix ("Start the evidence upgrades", Oct 22, 2026).
What changed, all on the pinned oracle (codex-cli 0.149.0, sha256 `bbc3341e…`,
vendored):

- `fixtures/policies/default.rules` gained the two forbidden prefix rules
  (sha256 `9b83f89f…`); corpus expectations re-locked BEFORE the after-run
  (pre-registration `docs/preregistration/2026-10-22-preregistration.json`,
  corpus `2dc43a86…`).
- **Post-fix sealed bundle:** `evidence/postfix-2026-10-22/bundle.json`
  (Merkle root `5a974fe6…`, status valid, signature/witness unsigned/unwitnessed)
  and `evidence/postfix-2026-10-22/bundle-protected.json` (Merkle root
  `29768240…`). Prior sealed bundles are untouched.
- **Post-fix scorecard v3:** `evidence/reports/day6-scorecard-v3-postfix/`,
  labelled POST-FIX, alongside (not replacing) the pre-fix v2.
- Results, actuals: S-02/S-03 flipped unknown → forbidden (the two intended
  cells); the other 39 cells byte-identical; protected family 11/11 pass
  unchanged; wrapped forms stay unknown per INV-004 Option A; negative
  controls healthy (4/4 and 2/2 fail as designed).
- **Held-out bookkeeping (read before citing):** S-02 sits in the held-out
  shard, whose content is untouched by policy — its pre-registered expectation
  was deliberately frozen at "unknown", so its runner verdict reads "fail"
  while its actual decision (forbidden) is verifier-confirmed and its
  intent_coverage moved UNRESOLVED → SATISFIED. That is an independent
  held-out confirmation of the fix with zero retuning, not a regression.
- Dual verdicts: intent SATISFIED 10 → 12, UNRESOLVED 23 → 21; measurement
  PASS 41 → 40 with the single S-02 bookkeeping FAIL described above.

Cite post-fix numbers from the post-fix bundle/scorecard, pre-fix numbers
from the pre-fix bundle/scorecard v2 — never mix them.

## 4. Rules layer only — no runtime verdicts

- Every finding is a **rules-layer** outcome (`codex execpolicy check`).
  Unmatched serializes as **unknown with layer attribution** ("no rules-layer
  decision; runtime outcome depends on approval policy + sandbox under the
  pinned configuration") — never allow, never a bypass/evasion/hole.
- No runtime probe under a pinned approval policy + sandbox mode was run in
  week 1. Nothing here says what any command would actually do when executed.
- 2026-10-22 (Evidence Upgrade C — effect-closure pilot): a pre-registered
  decision→approval→effect pilot (16 cases, pinned `approval_policy=never` +
  `sandbox_mode=workspace-write`, throwaway targets under a job-created
  sandbox, `docs/effect-pilot/PREREGISTRATION.md` locked before any case
  execution) was attempted and **blocked before any case execution**: the
  pinned `codex exec` cannot complete a model turn in this environment
  without authentication (no `~/.codex/auth.json`, no `OPENAI_API_KEY`;
  requests time out). It produced **no Layer-2/3 measurements** — everything
  above stands unchanged. The blocked result, per-case table (16/16 blocked),
  and standalone unsigned evidence are in `docs/effect-pilot/`.

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

## 7. Signatures implemented; witnessing still an honest placeholder

- **Update 2026-10-22 (grant-strengthening pack):** Ed25519 bundle signing is
  now implemented (`tools/ed25519.py` pure-Python, RFC 8032 vectors;
  `tools/signing.py`; `--sign` in both bundle builders; `docs/SIGNING.md`
  publishes the project public key + fingerprint; the private key lives
  outside all repos). New `--sign` bundles get `signature_state="signed"`;
  `witness_state` stays `"unwitnessed"` — signing is not witnessing.
- Sealed bundles record `signature_state: "unsigned"` and
  `witness_state: "unwitnessed"` as first-class states, not silent gaps.
  The two post-fix sealed bundles (sealed before signing existed) carry
  detached post-seal Ed25519 attestations (`.sig` + `.sig.json` alongside;
  bundle bytes untouched, `signature_state` honestly remains `"unsigned"`).
- Tamper-evidence today is Merkle-root + pre-registration hash-locking +
  detached Ed25519 signatures. Independent witness re-runs are still the
  open item (see §9).

## 8. Live (effect) measurement — 2026-10-22 wave: nothing measured; the auth wall is the finding

- **Update 2026-10-22 (paper-vs-live wave, `docs/live-test/`):** the
  founder-directed online evaluation ran its locked protocol across all
  nine harnesses (Codex, Amp, Claude Code, Cursor, Gemini CLI, OpenCode,
  Copilot CLI, Pi, Muse Code) and executed **0 of 12 cases on every
  harness**. The pre-registered runnability gate failed at both routes
  for all nine: no local model provider exists in this environment (no
  Ollama, nothing on 11434/1234, no base URLs), and no vendor offline/demo
  mode genuinely executes tools (Muse Code's `--provider echo` makes no
  tool calls; Amp's `permissions test` is paper-only, `--no-tui` threads
  require login). All thirteen swept API-key names absent; all auth files
  absent. REPRO environment facts — not runtime measurements.
- What WAS live-measured: **blocked-by-auth, 9/9, each with its specific
  missing artifact named** (Codex: OpenAI model auth — pilot-established;
  Amp: `amp login` session; Claude Code: Anthropic key or login; Cursor:
  account login; Gemini CLI: Google key or OAuth; OpenCode: any provider
  credential; Copilot CLI: GitHub login + subscription; Pi: model endpoint
  + key; Muse Code: dev.meta.ai account or MODEL_API_KEY). The 12 locked
  cases and 9 pinned configs stand committed, unexecuted — declared, not
  executed.
- Scope this precisely: **no approval decision, no sandbox enforcement,
  and no observed effect was measured for any harness in this wave.**
  `intent_coverage` at the effect layer is UNRESOLVED everywhere; the
  paper-vs-live agreement classes are `not-evaluated`. The paper side
  (A/B grades) remains the measured evidence; the live side is an honest
  blank, not a pass. Any citation must say "blocked at the runnability
  gate — no live cases executed."
- The unblock is founder-supplied auth per harness (RESULTS.md §6), used
  only for the contained 12 cases under the locked configs — zero
  pre-registration changes needed. Until then this limitation stands.

## 9. What would change these limitations

| Limitation | Evidence that would lift it |
|---|---|
| Single harness | A T2→T1 promotion: vendor ships a deterministic offline policy-evaluation entrypoint at a pinned version; corpus rerun sealed |
| Corpus artifact | A second corpus sampled from real policy files / observed command traffic, pre-registered before running |
| Pre-fix | LIFTED 2026-10-22: founder approved the Day-5 diff → applied, re-locked, reran 41 cases + 11-case family + precedence checks, re-sealed (`evidence/postfix-2026-10-22/`), re-issued scorecard v3 POST-FIX |
| Rules-layer only | 2026-10-22: first live wave pre-registered + run — 9/9 harnesses blocked-by-auth at the runnability gate (no local model provider, no executing offline mode); 12 cases + 9 pinned configs locked and committed unexecuted in `docs/live-test/`; unblock = founder-supplied auth per harness. Live layer still UNRESOLVED. |
| Snyk not tested | Founder supplies a token from his own account (or explicitly deprioritizes Snyk) |
| Unwitnessed | Independent witness re-runs (signing done 2026-10-22; see docs/SIGNING.md) |
