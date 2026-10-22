# The Boundary Measurement Framework

*Status: adopted Oct 21, 2026 at the founder's direction — the project is a
framework with adapters, not a single-harness tool. The framework is the
durable asset: it must be valuable on its own, with zero adapters, because
its schemas, protocol, and evidence format are what other tools, vendors,
and standards bodies can adopt.*

## Where this fits (cross-links)

- The plain-language foundation and the building-inspector metaphor: [docs/EXPLAINER.md](docs/EXPLAINER.md)
- The living status page (verdict NARROW, objectives, what's waiting on the founder): [docs/DASHBOARD.md](docs/DASHBOARD.md)
- The tier assignments with the evidence behind each harness: [docs/HARNESS_TIERS.md](docs/HARNESS_TIERS.md) — the five-harness graphic is [docs/assets/tier_matrix.png](docs/assets/tier_matrix.png)
- The evidence the tiers are measured against: [evidence/](evidence/) — sealed bundles under `evidence/day*-2026-10-*`, daily briefs in [docs/daily/](docs/daily/)
- The narrowed novelty claim this framework supports: [docs/SCIENTIFIC_REVIEW_ADDENDUM.md](docs/SCIENTIFIC_REVIEW_ADDENDUM.md)

## What the framework is

Four artifacts, all harness-neutral:

1. **Invariant schema** (`schemas/`, v1) — how a developer states intent
   independent of any vendor's config syntax: a command (or command class),
   an asset, an expected decision set, and a layer. Invariants outlive any
   harness version.
2. **Adapter contract** (this document) — how a harness is connected:
   what an adapter must declare, how it obtains decisions, how it labels
   layers, and what evidence it must emit.
3. **Evidence bundle format** (`docs/VERIFIABLE_EVIDENCE_ARCHITECTURE.md`) —
   hash-stamped, Merkle-rooted findings with harness version + pinned
   configuration + corpus-version hash, so any third party can replay a
   measurement and check it byte-for-byte.
4. **Conformance protocol** — pre-registration of corpus and expectations
   before a run (a pre-registered *confirmation* of the explored hypothesis,
   not initial discovery); public / held-out corpus split; negative controls
   in every run (a run that passes its negative controls is broken);
   two-sided verdicts (over-blocking legitimate work is a failure, not a
   safety win); dual-verdict judgments per fixture — measurement validity vs
   intent coverage, orthogonal, separate denominators, three labelled unknown
   kinds (`schemas/finding.v2.schema.json`, `tools/dual_verdict.py`);
   minimized counterexamples in public reports; vendor embargo with
   published responses.

## The adapter contract

An adapter MUST declare, in a machine-readable manifest:

- **Harness + version pinning** — exact binary/config versions measured.
- **Policy ingestion** — the native config surface it reads
  (e.g. Codex `.rules`, Claude `settings.json` permissions).
- **Oracle type** — how decisions are obtained (see tiers below). An
  adapter may never re-implement the harness's matching logic and present
  the result as the harness's decision; where decisions are computed from
  documented semantics instead of the native binary, the evidence class
  drops accordingly and the report says so.
- **Layer vocabulary** — every finding names its layer:
  `rules` (declarative policy), `approval` (human/classifier gate),
  `sandbox` (OS-level confinement), `effect` (observed outcome).
  Unknowns carry mandatory layer attribution (INV-004, Option A).
- **Evidence emission** — findings in the bundle format, unknowns
  serialized as unknown, never as allow (INV-005).

## Support tiers — what "supported" honestly means

| Tier | Meaning | Evidence class |
|---|---|---|
| **T1 — Native oracle** | Decisions obtained from the harness's own checker/evaluator, offline and deterministic. | REPRO |
| **T2 — Config evaluation** | Decisions computed from the harness's documented policy semantics (no native offline oracle exists); labelled as evaluation, not interrogation. | DOC + INFERENCE |
| **T3 — Surface survey** | No decision interface exists to evaluate. The adapter records the policy surface, its defaults, and the absence of a decision oracle. No verdicts are issued. | DOC |

A T3 result is a publishable finding, not a failure of the framework:
"this harness offers its users no way to ask what their policy decides"
is exactly the kind of fact the Boundary Index exists to record.

## The five target harnesses

Priority order is methodological (cleanest decision surface first), then
adoption (config-corpus prevalence from *Scanning the Harness*, 3,171
public repos, THIRD-PARTY):

| # | Harness | Policy surface (as researched) | Corpus repos | Status |
|---|---|---|---|---|
| 1 | **Codex** (OpenAI) | `execpolicy` `.rules`, prefix rules, `execpolicy check` CLI | 212 | **T1 adapter done** (v0, pinned 0.149.0) |
| 2 | **Claude Code** (Anthropic) | `settings.json` permissions allow/ask/deny, PreToolUse hooks, Bash sandbox; auto-mode classifier (stochastic layer) | 1,887 | Feasibility spike — oracle type to establish |
| 3 | **Cursor** (Anysphere) | IDE/CLI permission settings, rules files | 315 | Survey + spike |
| 4 | **Gemini CLI** (Google) | Settings/policy config, sandbox flags (off by default per research) | 273 | Survey + spike |
| 5 | **OpenCode** (open source) | `opencode.json` per-tool permissions (allow/ask/deny) | 142 | Survey + spike |

GitHub Copilot is a candidate sixth: large installed base, least
declarative surface; expected T2/T3. It joins when the five are tiered.

**Spike question for every harness, in order:** (a) Is there a deterministic,
offline way to obtain the harness's own decision for a command under a given
policy? (b) If not, are the semantics documented precisely enough for T2?
(c) If neither, it is T3 — record and move on. No harness gets verdicts its
surface cannot support.

## What does not change

- The Day-7 kill criterion stands, evaluated on the Codex T1 evidence and
  the same-corpus baselines. Framework breadth does not dilute it.
- Scope discipline (per `docs/SCIENTIFIC_REVIEW_ADDENDUM.md`): general
  agent frameworks, MCP gateways, and model APIs are not coding-harness
  policy surfaces and stay out of this framework.
- Claims discipline: a harness is described by its tier, never as
  generically "supported." Cross-harness statements in public material
  must name the tier mix behind them.

## Surveyed field (2026-10-21 field survey — appended, core definitions above unchanged)

Source: `~/workspace/research_notes/harness-field-survey-2026-10-21.md`
(web search + page-text fetch only; identities verified against primary
sources where reachable). Evidence classes follow the project scheme
(DOC / REPRO / THIRD-PARTY / INFERENCE / HYPOTHESIS). Adoption figures are
THIRD-PARTY unless noted. Nothing here changes the Day-7 kill criterion
(Codex T1 evidence) or the tier definitions above.

### Surveyed-field table (harness → tier evidence → oracle status)

| Harness | Tier evidence | Oracle status |
|---|---|---|
| **Amp** (Amp Inc.; ex-Sourcegraph) | ADAPTER-CANDIDATE — top pick. `amp.permissions`: tool glob + arg matches, action allow/reject/ask/delegate, `delegate --to` helper by exit code | **Candidate T1**: ships `amp permissions test` — the only execpolicy-check analogue found anywhere in the survey. Spike would confirm offline evaluation (DOC+THIRD-PARTY) |
| **Zed Agent** (Zed Industries, open source) | ADAPTER-CANDIDATE. `agent.tool_permissions`: default allow/confirm/deny + per-tool regex `always_allow`/`always_confirm`/`always_deny` (deny binds even when default is allow); documented deterministic semantics; evaluator inspectable in source | T2 (no CLI oracle shipped; T2 config evaluation straightforward; T1-via-source spike conceivable) (DOC) |
| **Warp** (commercial terminal+agent) | ADAPTER-CANDIDATE. `settings.toml` regex `agent_mode_command_execution_allowlist`/`_denylist`; **denylist takes precedence** over allowlist and "Agent decides"; shipped defaults published | T2 (closed source; regex-vs-command-string + precedence fully documented) (DOC) |
| **Goose** (Block → Agentic AI Foundation, Apache-2.0) | ADAPTER-CANDIDATE. YAML config: `GOOSE_MODE` + per-tool `AlwaysAllow`/`AskBefore`/`NeverAllow`; extension allowlist gates MCP installs | T2 at tool granularity (command-argument granularity not expressed) (DOC) |
| **Crush** (Charmbracelet, open source) | ADAPTER-CANDIDATE. `crush.json` `allowedTools`: `toolName` and `toolName:action` (e.g. `bash:execute`); dedicated permission service; crispest config semantics in the open-source CLI tier | T2 (DOC) |
| **Roo Code** (VS Code, Cline-fork family) | ADAPTER-CANDIDATE (last of the six — mode-scoped settings semantics need a spike). Per-Mode settings: command allow/deny lists, per-mode tool & MCP permissions | T2 (DOC) |
| **Pi** (earendil-works/pi, MIT; 116,973 stars platform data 2026-10-21) | T3 headline: README states **no built-in permission system at all** — boundary is "whatever the launching process could do" | None by design; future adapters would measure extension/container layer, not a Pi policy engine (DOC) |
| **OpenClaw** (openclaw/openclaw, MIT; 392,702 stars platform data) | T3: general personal-agent platform; declarative per-agent `tools.allow`/`tools.deny` + sandbox modes; coding delegated via ACP to Pi/Claude Code/Codex/OpenCode/Gemini — the harnesses already in our corpus | None for command decisions (tool-gating layer is a plausible future T2-style config-evaluation target) (DOC/THIRD-PARTY) |
| **Hermes Agent** (NousResearch, MIT; 255,955 stars platform data) | T3: general-purpose agent runtime; coarse toolset enable/disable + 7 terminal backends; no per-command declarative policy | None documented (DOC) |
| **Aider** (Aider-AI, Apache-2.0) | T3: confirmation prompts + config flags; `--yes-always`; **auto-commits ON by default** (the field-map note). Activity caveat: latest tag v0.86.0 (Aug 2025), last pushed May 2026 (THIRD-PARTY) | None (no rule language, no oracle) |
| **Cline** (Apache-2.0; 5M+ installs THIRD-PARTY) | T3 (borderline): Auto Approve per-category toggles over an internal safe/requires-approval classifier — a heuristic, not a developer-authored rule file | None offline |
| **Continue** (continuedev, Apache-2.0) | T3: per-tool policies (Automatic/Ask); Plan mode read-only. **Status caveat: repo now read-only, unmaintained**, final 2.0.0 (THIRD-PARTY). Survey for the historical record only — do not build an adapter | None |
| **Windsurf** (proprietary IDE agent) | T3: terminal auto-execution levels Disabled / Allowlist Only / Auto (AI-judged) / Turbo (denylist); org-admin caps. "Auto" is model-judged — stochastic decision layer, Phase-2 methodology territory | None offline |
| **Amazon Q Developer CLI** (AWS, open source) | T3: tool-granularity trust (trusted/per-request); persisted only via custom-agent JSON `allowedTools` | No command-pattern rules, no oracle |
| **JetBrains Junie** | T3: approval prompts + all-or-nothing "Brave mode" + dynamic allowlist; `.junie/guidelines.md` is instruction, not policy | None (closed source) |
| **Kiro** (AWS) | T3, **most likely promotion candidate in this tier**: capability-based permissions evaluating every read/command/MCP call; consent decisions persist as workspace/global rules — but rule grammar/evaluator not publicly documented enough for T2 today | None evaluatable today |
| **Void** (open-source VS Code fork) | T3: per-tool approval prompts + auto-approve; no declarative rule language in primary sources | None |
| **Trae** (ByteDance; IDE + open-source trae-agent) | T3: SOLO mode autonomous by design; no declarative permission policy located in primary sources — the documentation gap is itself the finding | None located |
| **Qwen Code** (Alibaba; Gemini CLI fork family) | T3: `tools.approvalMode` incl. LLM-classifier "Auto" — stochastic decision layer | None |
| **Kilo Code** (Cline/Roo fork family, MIT) | T3: fork-family auto-approve surface; nothing independently declarative beyond Roo Code's (if the family gets one adapter, Roo Code is the target) | None |

### Out of scope (surveyed, excluded with reason)

- **OmniAgent** — name collision across ≥5 unrelated projects; no single system with verifiable significant adoption. OUT. (Reopen only with a disambiguating repo URL.)
- **Hermes (models)** — Nous Research model family: a model is the engine other harnesses run; no permission surface. OUT.
- **Sourcegraph Cody** — Free/Pro discontinued 2025-07-23; individuals directed to Amp. Superseded by Amp. OUT.
- **PearAI** — VS Code fork bundling Continue + Aider; its policy surface IS Continue's. Measure the upstream. OUT.

### Adapter-candidate #6 and the bench/wave lists

- **Candidate adapter #6: Amp.** It displaces the "Copilot as candidate sixth"
  placeholder in *priority* (not in scope): Amp is the only vendor besides
  OpenAI with a shipped permission *test* command, making a T1 spike the
  obvious next adapter bet. GitHub Copilot remains a candidate, but with the
  least declarative surface of the set.
- **T2 bench (ranked):** Amp (spike for T1) → Zed → Warp → Goose → Crush → Roo Code.
- **T3 wave:** Pi, OpenClaw, Hermes Agent, Aider, Cline, Continue, Windsurf,
  Amazon Q Developer CLI, JetBrains Junie, Kiro (promotion candidate),
  Void, Trae, Qwen Code, Kilo Code.
- **Watch list (stochastic/heuristic decision layers — Phase-2 methodology):**
  Kiro's rule grammar if documented, Cline's internal classifier, Windsurf's
  AI-judged "Auto" level, Qwen Code's LLM-classifier approval mode.

### What the survey does to the coverage story

1. The four named systems were a real coverage hole, but three are field-map
   entries, not missing adapters: Pi proves a top harness can ship with no
   permission system at all; OpenClaw and Hermes Agent delegate coding to ACP
   harnesses already in our corpus — the delegation pattern *strengthens* the
   framework's premise that the harness policy layer is where coding-agent
   boundaries actually live.
2. The real adapter gaps were elsewhere: the T2 bench above, led by Amp.
3. Star counts (Pi 116,973; Hermes Agent 255,955; OpenClaw 392,702) are from
   GitHub repo pages fetched 2026-10-21; they measure attention, not deployed
   usage, and are used only as "meaningful adoption" triage signals.
