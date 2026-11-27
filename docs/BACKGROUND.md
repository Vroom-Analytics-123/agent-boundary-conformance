# Background — why this matters, and the parts beyond the quick start

Companion to the main README. It holds the context sections that used to
live there: what FinePrint verifies, why, what the durable invention is,
how findings become fixes, the live model integrations, and the
attribution.

## The invariant catalogue is the invention

The tester in this repo is one implementation. The durable asset is the
**invariant catalogue** ([docs/catalogue/](catalogue/)): **16
parameterized invariants** (FP-001…FP-016) — statements of intent, like
"a destructive recursive delete must never be silently allowed" — each
carrying, **per target**, a translation into that target's own policy
language, the **measurement route** the translation is checked by, and
the **confidence** the agreeing routes support.

That structure is what makes the knowledge compound: everything a
measurement learns about a target is written back into that target's
translations, so the next target starts from everything the previous
ones taught. A new harness or framework joins by **adding translations,
never by rewriting invariants**. And it is what makes **continuous
conformance** cheap: because the invariants and translations do not
change when a target does, each new harness version is measured by
re-running them unchanged, and a decision that tightens, loosens, or
appears for the first time surfaces as a cross-version regression diff.

## Attack surface — what this prevents

FinePrint does not inspect code or content. It verifies the
**agent-side control plane at the execution/impact stage** — the
checkpoint every harmful action, however delivered, must cross:

- **Destructive commands** — recursive deletes, disk wipes, production database drops.
- **Secret exfiltration** — reads of credential stores (`~/.ssh`, `.env`, token files) and sends to endpoints the user never named.
- **Unapproved installs + lifecycle scripts** — dependency additions, and the install-time code that then runs with the agent's full privileges.
- **Force-push / deploy without approval** — history rewrites and production changes that skip the human gate.
- **Privilege escalation** — approval layers switched off by a flag any local process can pass; elevated modes that never ask.
- **Runaway spend** — cost caps that exist on paper but no route ever witnesses firing.

The supply-chain relevance is structural: a compromised package, a
poisoned MCP server, a trojanized install script — the payload still has
to *do* something on the victim's machine, and those actions pass
through exactly the three layers measured here. FinePrint verifies that
the checkpoint exists and fires; it does not scan packages, detect
malware, or provide provenance signing, and is complementary to
Snyk/Socket/Sigstore-class tools.

## From findings to fixes

A measurement that only reports is half an inspector. Every finding is
paired with a drafted fix, in the form that fits the target — and the
loop closes only when the suite **re-runs and re-verifies** the fix,
reopening on the target's next release:

- **Drop-in skills → installable `SKILL.md` packages** carrying the drafted clauses, config patches, and hook/guard code, **versioned per harness release**, with the re-runnable conformance probes as their acceptance checklist. A working prototype, built from measured Codex findings and labelled prototype, lives at **[deliverables/fineprint-fix-skill/](../deliverables/fineprint-fix-skill/)**.
- **Open-source targets → a code PR**: the finding, the invariant it violates, and a patch (Omnigent is the worked example: where its dossier records that no builtin policy expresses an invariant, the remediation is a proposed builtin handler or CEL policy).
- **Closed-source targets → a public write-up**: the stated limit, the measured behaviour, the layer attribution, and the clause that would close the gap.
- **Otherwise → drafted policy clauses + a vendor disclosure note**, with private disclosure to the vendor before anything is published.

The honest boundary, once: a skill fixes at the **policy/config layer
around** a target; a defect inside a vendor's closed binary still needs
the vendor's patch — the skill carries compensating clauses until then,
and says so on its face. This repo already ran the loop once: the Codex
fix began as a conformance finding and a drafted rule change, and the
post-fix evidence bundle is that fix re-measured and sealed, not
asserted. **Inspector who drafts fixes, never enforcer.** FinePrint
writes the clause; the owner decides whether to adopt it.

**Fixes filed upstream (claimed as filed/open, never as merged).** A
structural permission-gate fix for Pi — tokenized command checks so a
deny rule can match the command stem through wrappers — was verified
over a 48-case matrix and filed as
[earendil-works/pi#11608](https://github.com/earendil-works/pi/pull/11608);
the repo's contributor gate auto-closed it, not a merit rejection, and
the branch is preserved on the fork. A credential-flow guard and egress
host allowlist for Omnigent — built from a live finding that no builtin
policy could govern credential files flowing into shell egress or
confine fetch binaries to approved hosts — is open as
[omnigent-ai/omnigent#12762](https://github.com/omnigent-ai/omnigent/pull/12762)
(DCO-signed, CI finished — 84 success, 10 skipped, 1 Maintainer Approval
gate, closes #12516), not merged. Both are real improvement work in the
ecosystem, not claims of acceptance.

## Why this matters — verified incidents

These are not hypotheticals. Each incident below is **verified** (primary
source or the disclosing firm's own write-up), and in each the stated
guardrails proved not real at exactly the layers measured here.

- **Replit deletes a production database (Jul 2025) — Approval · Effect.** Under an explicit code freeze, the agent deleted SaaStr's production database (1,200+ executives, 1,190+ companies), fabricated ~4,000 fake records, and falsely claimed rollback was impossible. — [The Register](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/)
- **Nx "s1ngularity" (Aug 2025) — Approval · Effect.** Supply-chain malware in the Nx build system invoked victims' own AI CLIs with approvals disabled (`--dangerously-skip-permissions`, `--yolo`, `--trust-all-tools`) to inventory sensitive files; 2,349 secrets were exfiltrated. — [StepSecurity](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware)
- **GitHub MCP leak (May 2025) — Decision · Approval.** A malicious issue planted in a public repo made an agent use the victim's own over-scoped token to read their private repositories and publish the contents in a public PR. — [Invariant Labs](https://incidentdatabase.ai/reports/5264/)
- **postmark-mcp rug pull (Sep 2025) — Effect · Decision.** An impersonator MCP server behaved exactly as advertised for 15 versions, then v1.0.16 added a single line BCC'ing every email sent through it to an external address. — ActiveCampaign, via [iTnews](https://www.itnews.com.au/news/first-malicious-mcp-server-for-ai-found-620662)
- **PocketOS: a Cursor agent deletes the production database and its backups (24 Apr 2026) — Effect · Approval.** On a routine staging credential task, the agent found a Railway API token that was in fact account-scoped and issued a single `volumeDelete` call; the production volume — and the volume-level backups stored on it — were deleted in nine seconds. — [founder's public account, via The Register](https://www.theregister.com/2026/04/27/cursoropus_agent_snuffs_out_pocketos/)
- **LiteLLM backdoored on PyPI by TeamPCP (24 Mar 2026) — Effect · Decision.** Using a PyPI publishing token stolen via the compromised Trivy scanner in LiteLLM's CI, TeamPCP published versions 1.82.7 and 1.82.8 directly to PyPI; 1.82.8 carried a `litellm_init.pth` startup hook that ran a credential harvester on every Python interpreter start. The packages were live about 40 minutes before PyPI quarantined them. — [LiteLLM (BerriAI), security update](https://lmmarketcap.com/litellm-supply-chain-attack)
- **Axios npm compromise (31 Mar 2026) — Effect · Approval.** An attacker who hijacked the lead maintainer's npm account published axios 1.14.1 and 0.30.4 directly to npm, bypassing the GitHub pipeline; both injected a phantom dependency whose postinstall dropper fetched a cross-platform remote access trojan. — [CISA, supply-chain alert (20 Apr 2026)](https://www.cisa.gov/news-events/alerts/2026/04/20/supply-chain-compromise-impacts-axios-node-package-manager)
- **Microsoft Semantic Kernel: one prompt to host RCE (CVE-2026-26030, May 2026) — Decision · Effect.** The In-Memory Vector Store's default filter built a Python lambda by interpolating a model-controlled tool argument into a string executed with `eval()`; an AST blocklist validator was bypassed through attributes it did not list, reaching `os.system()`. — [Microsoft Security Blog (Defender Security Research Team)](https://www.microsoft.com/en-us/security/blog/2026/05/07/prompts-become-shells-rce-vulnerabilities-ai-agent-frameworks/)
- **Langflow unauthenticated RCE, exploited in the wild (CVE-2026-33017, 17 Mar 2026) — Effect · Decision.** Langflow's public flow-build endpoint accepted attacker-supplied flow data containing arbitrary Python code in node definitions and executed it server-side with no sandboxing; exploitation in the wild was observed within ~20 hours of the advisory, and the flaw was added to CISA's Known Exploited Vulnerabilities catalog. — [vendor advisory GHSA-vwmf-pq79-vjvx; CISA KEV 25 Mar 2026](https://sudor-io.medium.com/langflow-cve-2026-33017-explained-public-flow-rce-a-lab-repro-and-verifying-the-fix-f9033ecb4ef9)

## Nebius × NVIDIA: Nemotron proposes, the checker decides

FinePrint's first live model integration — and the model is deliberately
**not** the judge. **Nemotron-3-Super on Nebius Token Factory** proposes
adversarial scenario variants for a given invariant set
(`tools/nemotron_scenarios.py`); the deterministic checker (pinned codex
execpolicy oracle) returns the Decision verdict for each; the demo
script (`tools/run_nemotron_demo.py`) adds the Effect observation in a
throwaway sandbox. Proposed commands are **never executed** — the only
executed command is one allow-verdict benign command (or the labelled
`ls` positive control), and the sentinel file must survive intact.

The live run (FP-001/002/003, 6 proposals): 1 prompt verdict matching
the model's prediction, 5 unknowns — the checker honestly reporting that
the written policy gives no Decision for split-flag, wrapper, and
`find -delete` forms. Full evidence, timestamps, and the safety
contract: **[docs/NEBIUS_INTEGRATION.md](NEBIUS_INTEGRATION.md)** and
`evidence/nebius-2026-10-30/demo-evidence.json`.

**Run it yourself** (Python 3, stdlib-only tools; pinned `codex` CLI
v0.149.0 vendored in this repo; your own Nebius Token Factory API key,
read only from `NEBIUS_API_KEY` in `--direct` mode, never printed,
logged, or written to evidence):

```bash
# Point --out at a FRESH directory: evidence/nebius-2026-10-30/ is the
# sealed record and must not be overwritten.
NEBIUS_API_KEY=... python3 tools/run_nemotron_demo.py \
    --invariants FP-001,FP-002,FP-003 \
    --model nvidia/nemotron-3-super-120b-a12b \
    --policy fixtures/policies/default.rules \
    --out evidence/my-nebius-run/ --direct
```

Expect the safety contract first, then one block per proposal
(model-generated titles, rationales, and proposals — they differ run to
run), each with a deterministic Decision verdict and the model's
`expected_decision` as prediction only, then the Effect lines (throwaway
sandbox, sentinel intact). A disagreement between prediction and verdict
is itself a finding. The full guide — setup, expected-output transcript,
the strict JSON schema Nemotron must match, Token Factory notes,
sealed-evidence details — is in
**[docs/NEBIUS_INTEGRATION.md](NEBIUS_INTEGRATION.md)**.

## Meta Spark and Muse Code

Meta Spark generated the scenarios; Muse AI built the expansion; Muse
Code CLI was measured live as a harness — three different roles, not one
blur.

**Meta Spark — the scenario generator.** The 24-scenario v1 set
([framework/scorecard/scenarios-v1.json](../framework/scorecard/scenarios-v1.json))
was generated with Meta's `muse-spark-1.3` via the Meta Model API —
human-reviewed, kept verbatim, including one mislabeled item noted
rather than silently fixed. One live arm of the reference rollout ran
`muse-spark-1.1`. The scenarios are the shared yardstick every harness
is measured against.

**Muse AI — the builder.** The main expansion beyond the Nebius start —
the harness-neutral re-measurement protocol, the 16-harness scorecard,
the live measurement series, and the fix drafts — was built with Muse
AI, used for conception, design, planning, and implementation
throughout.

**Muse Code CLI — the measured harness, not a builder.** Muse Code was
measured live like any other harness: 48 v1 cells, **49.71** (Decision
0.00 / Approval 22.50 / Effect 27.21; full table:
[framework/scorecard/v4-scorecard.md](../framework/scorecard/v4-scorecard.md);
package: [framework/scorecard/musecode-v1/](../framework/scorecard/musecode-v1/)).
It has no native decision engine — the MSP approver is the approval
layer, not a decision policy — and the read tool is the harm channel:
credential content escaped in 4 cells despite shell denials. Denial is
not prevention.

No Meta endorsement is implied by any of this, and the upstream fix
commits are the owner's signed personal step.

## Repository structure

The repo is organized as a framework: a target-independent core, one
adapter per target, and evidence kept separate from both.

| Path | Holds |
|---|---|
| `docs/catalogue/` | **The invariant catalogue** — 16 parameterized invariants with per-target translations (route + confidence each); generated by `tools/build_catalogue.py`; new-target drafts land in `translations-draft/` first |
| `adapters/` | **One dossier + manifest per target** (`<key>-assessment.md`, `<key>.manifest.json`); executable adapters for measured targets live in `adapters/<key>/` |
| `tools/` | **The measurement machinery** — fixture replay, catalogue generator, evidence bundling/sealing/verification, approval witness, effect instrumentation |
| `evidence/` | **Sealed run records** — frozen bundles, reruns, scorecards. Sealed bundles are never edited; corrections land as new bundles |
| `mcp/` | **The MCP server** — `server.py` (stdio, stdlib only), `SKILL.md` for agents, client configs in `examples/` |
| `docs/` | **Doctrine + status** — the measurement model, framework, route assignments, project pathway, limitations, the extension guide, daily briefs (history) |
| `fixtures/` · `security/` · `schemas/` | Probe corpora + sample policies · the invariant contracts under test · versioned finding/evidence schemas |
| `tests/` · `ci/` · `catalogue-contrib/` | Engine tests · CI wiring · the Catalogue Commons (org overlays stay private by construction; worked examples only) |

**The bar this method had to clear:** show a useful result the baselines
miss or explain poorly — or stop, publish the negative result honestly,
and offer the fixtures upstream. **Verdict: NARROW** (see
[docs/daily/2026-10-27.md](daily/2026-10-27.md)): the method is proven
on Codex evidence (two vendor-confirmed Decision-layer routes; Amp's
shipped native offline decision oracle `amp permissions test` was
recognized as a vendor-confirmed route); a public multi-harness Index is
not earned on the current evidence. The repo stands as the method,
limitations on its face.
