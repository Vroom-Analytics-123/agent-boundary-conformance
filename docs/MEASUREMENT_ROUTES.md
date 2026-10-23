# Harness Measurement-Route Assignments — Agent Boundary Conformance (Day 4, 2026-10-21)

*Status: draft for the record. Nothing published. Per `docs/FRAMEWORK.md`, a
harness is described by its measurement route, never as generically
"supported."*

**Founder model correction (2026-10-22 ~18:29 PDT, controlling).** Grades and
T1/T2/T3 ranking labels are abolished: ease of measurement never makes a
harness better or worse. The assignments below use the unranked,
descriptive **measurement routes** — provenance of the Decision-layer measurement
only: **vendor-confirmed** (the vendor's own checker answers),
**reconstructed** (evaluated from the vendor's documented semantics),
**no paper surface** (no rule surface exists to evaluate). Every adapter
manifest carries the machine field `measurement_route`. The dated revision
paragraphs beneath are the historical record — their tier labels are
superseded by this correction; the measured facts stand.

The framework is the three layers (`docs/FRAMEWORK.md`): **Decision**
(Layer 1) = what the rules decide (the paper test measures this — the
routes below are provenance of Decision-layer results); **Approval**
(Layer 2) = the approval moment; **Effect** (Layer 3) = what actually
happens (observed effect — ground truth, the most important layer). The
offline side is the **PAPER TEST**; the online side is the **LIVE TEST**.

## Question order (answered for every harness)

(a) Is there a deterministic, offline way to obtain the harness's OWN decision
for a command under a given policy — a vendor-confirmed route? (b) If not,
are the semantics documented precisely enough for an honest
reconstructed-route adapter — one that computes decisions from documented
semantics and labels them *evaluation*, never *interrogation*? (c) If
neither, the harness has no paper surface: record the surface, its defaults,
and the absence of a decision route; issue NO verdicts.

Revision-2 semantics hold throughout: an unmatched command is "no decision,"
never a bypass/evasion/hole; unmatched serializes as **unknown**, never allow.

## Assignments

| Harness | Measurement route | Oracle type | One-line evidence |
|---|---|---|---|
| Codex (codex-cli 0.149.0) | **vendor-confirmed** | native-offline | `codex execpolicy check` returns the harness's own Decision-layer decision offline and deterministically; 41-case corpus replays byte-identically across 4 independent runs (REPRO). Manifest: `adapters/codex.v0.manifest.json`. |
| Amp (`amp` 0.0.1792680614-g8973a3) | **vendor-confirmed** | native-offline | `amp permissions test --json` returns the harness's own permission-engine decision offline and deterministically (no auth); full 41-case corpus + protected family replayed byte-identically in the recognition run (REPRO). Manifest: `adapters/amp.manifest.json`. First-match-wins, user rules precede built-ins; no-match → unknown (INV-005). |
| Claude Code (@anthropic-ai/claude-code@2.1.307) | **reconstructed** | config-evaluation | The vendor ships no decision checker, but allow/ask/deny matching semantics (deny→ask→allow first-match-wins, wildcard table, deny-always-wins) are documented precisely enough to compute evaluations — labelled evaluation, never interrogation. (INFERENCE on DOC+REPRO). Manifest: `adapters/claude-code.manifest.json`. |
| Cursor (CLI via cursor.com/install; docs pinned 2026-10-21) | **reconstructed** | config-evaluation | Permission tokens, first-token+glob matching, and deny-precedence are documented precisely enough for evaluation in Allowlist mode; the default Auto-review mode's classifier is stochastic and staff-confirmed to drop hook asks, so it cannot be a checker. (INFERENCE on DOC+THIRD-PARTY). Manifest: `adapters/cursor.manifest.json`. |
| Gemini CLI (@google/gemini-cli@0.65.0) | **reconstructed** | config-evaluation | Locally reproduced `--help` proves no decision checker exists, while the TOML policy engine (prefix/regex/argsPattern, priority tiers, mode scoping, documented precedence) is specified precisely enough to evaluate — labelled evaluation. (INFERENCE on REPRO+DOC). Manifest: `adapters/gemini-cli.manifest.json`. |
| OpenCode (opencode-ai@1.19.3; 1.x semantics pinned) | **reconstructed** | config-evaluation | No offline checker exists, but the permission object semantics (last-match-wins wildcards, per-agent merge precedence, documented defaults) are fully specified for 1.x — evaluatable, with the 1.x/2.x schema break as a hard version pin. (INFERENCE on DOC+REPRO). Manifest: `adapters/opencode.manifest.json`. |
| GitHub Copilot CLI (@github/copilot@1.0.103) | **reconstructed** (from configuration; account-walled) | config-evaluation | Install is not auth-walled but every live evaluation route sits behind `/login` (account/subscription wall, named). Offline binary inspection found no checker-like entrypoint; semantics evaluatable from docs only. Assessment: `adapters/copilot-assessment.md`. |
| Muse Code — Meta (muse-stable 1.4.11; terminal coding agent) | **no paper surface** | none located | No deterministic offline decision checker in the CLI surface or official docs; surface and defaults recorded, no verdicts. Assessment: `adapters/muse-code-assessment.md`. (Bonus assessment outside the wave's original list; this is the `muse` terminal agent, not the Muse personal assistant.) |
| Omnigent (0.19.1; meta-harness) | **reconstructed** (design-stage, Wave A) | config-evaluation | Stateful policy engine — ALLOW/ASK/DENY over request/tool_call/tool_result/response events, YAML/CEL/Python policies, session → agent → server stacking, any-DENY blocks — documented precisely enough to evaluate on paper; no offline oracle in any documented CLI/REST surface (DOC-scope negative; no binary installed). NOT measured. Assessment: `adapters/omnigent-assessment.md`; manifest: `adapters/omnigent.manifest.json`. |
| Hermes Agent — Nous Research (version unpinned; docs describe post-v0.21 behaviour) | **reconstructed** (design-stage, Wave A) | config-evaluation | Identity pinned from Omnigent's own launcher text ("Hermes Agent (Nous Research)"). Deterministic Decision core — hardline blocklist, `approvals.deny` globs with compound splitting, protected-path denylist — documented across three agreeing vendor docs; the default `smart` mode routes flagged commands to a stochastic guardian LLM (unevaluatable subset). NOT measured. Assessment: `adapters/hermes-assessment.md`; manifest: `adapters/hermes.manifest.json`. |
| OpenClaw (github.com/openclaw/openclaw; gateway/runtime — own native exec boundary assessed) | **reconstructed** (design-stage, Wave A) | config-evaluation | Identity pinned via the project repo + Omnigent's `docs/openclaw.md`; same-name candidates excluded with evidence. `tools.allow`/`tools.deny` (deny always wins) + exec-approvals allowlist documented, but granularity is tool/binary, never argv; no vendor checker. NOT measured. Assessment: `adapters/openclaw-assessment.md`; manifest: `adapters/openclaw.manifest.json`. |
| LangGraph (langgraph 1.2.16; framework) | **no paper surface** (design-stage, Wave A) | none — framework runtime | No declarative policy surface exists; Decision lives in user code, so a reconstruction would invent the policy language. Approval is real and pre-execution (`interrupt()` + checkpointer; LangChain `HumanInTheLoopMiddleware`). Coverage path = instrumented reference agent (dossier §reference-agent). NOT measured. Assessment: `adapters/langgraph-assessment.md`; manifest: `adapters/langgraph.manifest.json`. |
| Strands Agents (strands-agents 1.62.0; framework) | **no paper surface** (design-stage, Wave A) | none — framework runtime | No CLI, policy file, or checker; the gate is in-process Python (`BeforeToolCallEvent` hooks; typed interventions Proceed/Deny/Guide/Confirm/Transform) — arbitrary code is not reconstructable. Bedrock Guardrails screen model inputs/outputs only, never tool actions. Approval exists as interrupts + a vended HITL handler. Coverage path = instrumented reference agent. NOT measured. Assessment: `adapters/strands-assessment.md`; manifest: `adapters/strands.manifest.json`. |
| CrewAI (1.15.28; framework) | **no paper surface** (design-stage, Wave A) | none — framework runtime | No declarative surface; the only pre-execution control is author-written `PRE_TOOL_CALL` hooks, and hook exceptions other than `HookAborted` are swallowed (fail-open). Task `human_input` is post-effect output review, not action approval; task guardrails are output-side only. Coverage path = instrumented reference crew. NOT measured. Assessment: `adapters/crewai-assessment.md`; manifest: `adapters/crewai.manifest.json`. |

**Revision — empirical wave (2026-10-22):** the five T2 harnesses were measured
through their best honest routes (no account/login anywhere). Claude Code
2.1.307 (85/85 doc-cited engine tests; 21 public + 6 protected cases),
Cursor 2026.10.19-6bbf2c4 (38/38 tests; 27 public cases; Allowlist mode only —
default Auto-review unevaluatable), Gemini CLI 0.65.0 (33/33 tests; 21 public +
6 protected; `--debug-policy` refuted at the pinned version), OpenCode 1.19.3
(43/43 tests; 27 public cases; last-match-wins demonstrated empirically — 3
order flips of 27). Each result is labelled T2-evaluation (never interrogated);
full evidence in `adapters/<harness>/` and the consolidated report at
`docs/harness-testing-2026-10-22.md`. **No harness changed tiers.** The evidence
*behind* each T2 assignment upgraded from documented-semantics to
measured-evaluation; the tier definitions and the T2→T1 promotion condition
(native offline decision entrypoint at a pinned version) are unchanged. Muse
Code is the first harness to land at T3 since Pi — the "no harness landed T3"
line above is superseded. Amp's T1 candidacy is a separate spike (awaiting the
founder's decision); it is not part of this revision.

Muse Code is the first harness to land at T3 since the Day-1 survey (Pi):
the "no harness landed T3" claim from 2026-10-21 was superseded by the
2026-10-22 empirical wave. T2 remains the ceiling until a vendor ships a
deterministic offline "evaluate this command against this policy" entrypoint
— the `codex execpolicy check` equivalent — at a pinned version. That is the
stated T2→T1 promotion condition for the T2 set.

**Revision — Amp promotion (2026-10-22):** the founder approved Amp's T1
promotion (decision: "do T1, T2 and T3 for all harnesses wherever possible").
`adapters/amp.manifest.json` is now **active** (T1, oracle type
native-offline), and the full 41-case corpus + protected family were run
through the Amp oracle at the pinned version
`0.0.1792680614-g8973a3` (sha256
`89304a6e5bc739807062433a28bba5a98dc8dfbae05d8674df06a465103c8f3f`),
sealed in `evidence/amp-2026-10-22/bundle.json`. This satisfies the
T2→T1 promotion condition stated above — a vendor-shipped deterministic
offline "evaluate this command against this policy" entrypoint at a pinned
version. FinePrint is now a **two-oracle method** (Codex execpolicy +
Amp permissions test). The spike's REPRO record stands
(`docs/amp-spike-2026-10-22.md`); the "awaiting the founder's decision" line
in the wave revision above is superseded.

**Revision — Wave A expansion spikes (2026-10-22, founder-directed):** six
design-stage dossiers were added. On the harness/meta-harness surface:
Omnigent (a meta-harness with its own policy engine — the governance layer
is itself a measurement target), Hermes Agent, and OpenClaw (both
identities pinned from primary sources, rival candidates excluded with
evidence; OpenClaw's scope caveat: a gateway/runtime, its own native
tool/exec boundary assessed). On the framework surface: LangGraph, Strands
Agents, and CrewAI — none has a declarative policy surface, so each
dossier's coverage path is an instrumented reference agent measured live,
not a paper route. **Nothing in this revision is a measurement:** every new
target is UNMEASURED, its catalogue translations are standalone drafts in
`docs/catalogue/translations-draft/` (merging into the generated catalogue
awaits the generator naming alignment recorded in commit `fa41cd8`), and
its route assignment is a paper assignment from vendor documentation.
Live Approval/Effect routes for all six remain blocked on the credentials
in each dossier's LIVE-UNLOCK line (Wave B).

## Evidence behind each assignment

### Codex — vendor-confirmed (done Day 1–4)
- Native oracle: `codex execpolicy check --rules <file> [--resolve-host-executables] -- <argv...>` → JSON `{matchedRules[], decision?}` (REPRO, codex-cli 0.149.0).
- 41-case corpus + 11-case protected family replay byte-identically across 4 independent runs; negative controls 4/4 healthy; Merkle-sealed bundles.
- ENV DRIFT NOTE (Day 4): the environment replaced the pinned binary (0.149.0, sha256 `bbc3341e…`) with 0.164.0-alpha.9 AFTER the Day-4 run; all oracle data was collected on the pinned binary. Sealed bundles remain valid evidence of their pinned runs; on-disk re-verification is blocked until a pinned binary is restored. No vendored copy of 0.149.0 was kept — the pin checklist gains a binary-vendoring step.
- **Revision — vendored binary restored (2026-10-22):** the Day-5 run restored and sha256-verified codex-cli 0.149.0 (`bbc3341e…`) at `tools/vendor/codex/0.149.0/` (binary git-ignored on disk; `VENDORED.md` + recipe committed). On-disk re-verification of the pinned bundles is unblocked; the Day-4 note above stands as the record of the drift when it happened.

### Claude Code — reconstructed (deepest spike)
- (a) NO: CLI subcommands (`daemon`, `doctor`, `import`, `logs`, `mcp`, `plugin`, `config`, `memory`, `session`, `auth`, `agents`, `attach`, `auto-mode`, `update`, `gateway`, `remote-control`) include no check/evaluate/dry-run. `doctor` is install/settings diagnostics; `auto-mode config` prints classifier rules (config inspection, not a per-command oracle). npm package's `sdk-tools.d.ts` exports only tool I/O schema types — no permission-check API (REPRO, read-only inspection).
- (b) YES: deny→ask→allow, first match wins, specificity irrelevant; wildcard table documented row-by-row; `Bash(git push *)` matches the command *as written* only — the docs themselves say such a rule "isn't a security boundary around the program" and point to the sandbox. Ceilings: stochastic auto-mode classifier (documented as an Approval-layer mechanism, never tested as an oracle in week 1), PreToolUse hooks (arbitrary user code), six permission modes, unconfirmed sandbox sub-keys (not asserted).
- Key quirk: literal-string Bash matching means an invariant "git push is blocked" that ignores flag-reordering is a false pass — a reconstructed-route adapter must model literal semantics.

### Cursor — reconstructed
- (a) NO: documented CLI surface (`-p/--print`, `--force`, `--yolo`, `--mode=plan|ask`, `--approve-mcps`, `--workspace`, `--resume`, `mcp`, `generate-rule`, `ls`, `update`) has no check/evaluate subcommand. The npm package named `cursor-agent@1.0.3` is an unrelated third-party package (per its package.json), not the Cursor CLI — recorded so nobody else trips on it.
- (b) YES, in **Allowlist mode**: tokens `Shell(commandBase)` (first-token semantics), `Read`/`Write`/`WebFetch`/`Mcp`, glob vocabulary, deny takes precedence over allow. NOT in default Auto-review mode: classifier stochastic, and per Cursor staff (forum 2026-10-05) a hook's "ask" answer is silently dropped when the classifier deems the command safe — "deny" still enforced. The reconstructed-route adapter is honest only against Allowlist semantics; Auto-review verdicts labelled unevaluatable.
- Key quirk: in Auto-review (the recommended mode), an explicit `ask` can evaporate via silent classifier approval.

### Gemini CLI — reconstructed
- (a) NO: locally reproduced `--help` on 0.65.0 shows no check/evaluate subcommand (commands: `mcp`, `extensions`, `skills`, `hooks`, `gemma`, `[query..]`). A third-party skill claims `--debug-policy`; the string is absent from the 0.65.0 bundle — claim unverified, not asserted.
- (b) YES: TOML policy engine (`commandPrefix`/`commandRegex`/`argsPattern`, `decision = allow|deny|ask_user`, tier Admin > User > Default regardless of priority, `modes` scoping, `interactive`); `confirmationRequired` takes precedence over `allowed`+`core`; shell validation splits chains and validates each part, blocklist first. Ceilings: stochastic Conseca LLM (an Approval-layer mechanism), folderTrust default DOC-vs-DOC conflict (assert neither), deprecated keys in version churn (`tools.exclude`, `--allowed-tools`), runtime mode flags (`--yolo` CLI-flag-only), MCP/extension surface.
- Key quirk: YOLO cannot be enabled from `settings.json` (CLI flag only), but TOML rules can be scoped `modes = ["yolo"]` to re-impose `ask_user`/`deny` inside YOLO — the mode dimension is part of the decision function.

### OpenCode — reconstructed
- (a) NO: command surface (`run`, `mini`, `session`, `auth`, `models`, `mcp`, `plugin`, `service`, `serve`, `pair`, `api`, `reload`, `stats`, `acp`, `debug`, …) has no check/evaluate; `debug config` shows resolved config only.
- (b) YES, at **1.x**: permission object with simple wildcards, **last matching rule wins** (order-dependent — the sharpest contrast with Claude/Cursor deny-first), per-agent overrides merged with agent rules taking precedence, documented defaults. Ceilings: 1.x/2.x schema break (adapter pins 1.x; 2.x is an ordered `permissions` list — needs a separate pass), unspecified "parsed commands" normalization, session-state `always` approvals, runtime `--auto`.
- Key quirk: last-match-wins + permissive defaults — `{"shell": {"*": "ask", "git *": "allow"}}` behaves oppositely if the lines are swapped, and a fresh install allows nearly everything. The *absence* of config is decision-relevant.

### Amp — vendor-confirmed (recognized 2026-10-22, founder decision)
- Native oracle: `amp permissions test --json <Tool> --cmd "..." [--settings-file <policy.json>]` → JSON `{tool, arguments, action, matchedEntry?, matchIndex?, source?}` (REPRO, pinned binary 0.0.1792680614-g8973a3, sha256 `89304a6e5bc739807062433a28bba5a98dc8dfbae05d8674df06a465103c8f3f`; vendored at `tools/vendor/amp/0.0.1792680614-g8973a3/`, git-ignored).
- 13 corpus-derived spike probes byte-identical across 2 runs; full 41-case corpus + protected family replayed byte-identically across 2 runs in the promotion run; Merkle-sealed bundle at `evidence/amp-2026-10-22/`.
- ENV note: the pinned binary is vendored on disk with a recorded hash, so the sealed bundle remains re-verifiable here (unlike the Codex pin, which was replaced post-run).
- Built-in permission ruleset is version-pinned but not vendor-published; only observable via `test` matchedEntry echoes (open question in the manifest).

## Cross-cutting findings (method-level, not per-harness)

1. **Precedence is not uniform** — the framework's sharpest inter-harness difference: Claude = deny→ask→allow fixed order; Cursor = deny over allow; Gemini = Admin tier > User tier > Default tier, then priority; OpenCode = last match wins. A shared invariant schema must not assume a common precedence operator. No reconstructed-route adapter may "re-implement the harness's matching logic and present the result as the harness's decision" — each manifest sets `reimplements_matching: true` and labels output evaluation.
2. **No-match defaults are ask-like everywhere**: Claude → ask; OpenCode (non-auto) → ask; Gemini → confirmation dialog; Cursor → prompt. Every manifest maps harness no-match to framework unknown — never allow (INV-005). No claim rests on an unmatched rule.
3. **No adapter masquerades as a decision checker it is not**: all four manifests declare `oracle.type: config-evaluation` and the manifests' evidence classes are DOC+REPRO/DOC+THIRD-PARTY/INFERENCE — never REPRO-alone for decisions.
4. **Install state**: none of the four CLIs were installed on this machine (only codex). Claude/Cursor/OpenCode CLIs were never executed; Gemini CLI's 0.65.0 bundle was executed read-only in a scratch dir (`--help`, `--version`, bundle grep) with no session launched and no repo touched. No MCP servers, hooks, or repo code were executed. `/tmp` scratch dirs were wiped by the environment after the spike; all findings were recorded first.

## Open questions (what would resolve them)

- Claude Code: official enumeration of `sandbox` settings sub-keys; binary pin via a local pinned install.
- Cursor: real CLI install at a pinned version for a read-only (a)-spike; documented IDE-settings↔CLI-token mapping; a vendor-shipped offline decision entrypoint (the reconstructed→vendor-confirmed route condition).
- Gemini CLI: verification (or refutation) of the `--debug-policy` flag at a pinned version; vendor resolution of the folderTrust default conflict.
- OpenCode: 2.x `permissions` semantics at a pinned 2.x version; documentation of the command-parsing step.
- Codex: vendored copy of the pinned 0.149.0 binary (see env drift note above); runtime-probe design for the Approval layer + the Effect layer (sandbox/effect).
