# The Boundary Measurement Framework

*Status: adopted Oct 21, 2026 at the founder's direction — the project is a
framework with adapters, not a single-harness tool. The framework is the
durable asset: it must be valuable on its own, with zero adapters, because
its schemas, protocol, and evidence format are what other tools, vendors,
and standards bodies can adopt.*

## Where this fits (cross-links)

- The plain-language foundation and the building-inspector metaphor: [docs/EXPLAINER.md](docs/EXPLAINER.md)
- The living status page (verdict NARROW, objectives, what's waiting on the founder): [docs/DASHBOARD.md](docs/DASHBOARD.md)
- The measurement-route assignments with the evidence behind each harness: [docs/MEASUREMENT_ROUTES.md](docs/MEASUREMENT_ROUTES.md) — the route-matrix graphic is [docs/assets/measurement_routes.png](docs/assets/measurement_routes.png)
- The evidence the routes are measured against: [evidence/](evidence/) — sealed bundles under `evidence/day*-2026-10-*`, daily briefs in [docs/daily/](docs/daily/)
- The narrowed novelty claim this framework supports: [docs/SCIENTIFIC_REVIEW_ADDENDUM.md](docs/SCIENTIFIC_REVIEW_ADDENDUM.md)
- The founder's direction log, 2026-10-22 — layer primacy (cross-layer checking as the core method), the layer-failure-dominates scoring rule, catalogue transferability as a first-class design goal: [docs/DIRECTION-2026-10-22.md](docs/DIRECTION-2026-10-22.md) — the cross-layer check is named **Cross-Examination** (founder's tap, 2026-10-22 — chosen over Triangulation / Layercheck). **Model correction (founder, ~18:29 PDT the same day, controlling):** grades/tiers are abolished as harness rankings — ease of measurement never makes a harness better or worse. What the grades actually were is provenance of the Decision-layer measurement only, now named unranked: vendor-confirmed / reconstructed / no paper surface. Effect (what actually happens) is ground truth and the most important layer.

## The three measurement layers (founder-adopted names, 2026-10-22)

Every finding names its layer. The names were adopted by the founder's
tap on 2026-10-22 (~18:38 PDT). Everything the framework measures serves
one comparison — **Cross-Examination**: for each invariant, the declared
intent, the Decision layer's ruling, and the Effect layer's observed
outcome are examined against each other; a disagreement between any two
is a finding.

- **Decision** (Layer 1) — what the harness's rules decide about a
  command: allow, prompt/ask, forbidden, or no decision. The **PAPER
  TEST** measures this layer, without running anything.
- **Approval** (Layer 2) — the approval moment: a human or classifier
  is asked — the gate between the rules' decision and the run.
- **Effect** (Layer 3) — what actually happens when the command runs:
  sandbox confinement plus the observed outcome. **Effect is ground
  truth and the most important layer.** The **LIVE TEST** is the main
  event; paper findings are provisional until the Live Test confirms or
  refutes them. Cross-Examination compares the layers against each other,
  with Effect as the reference standard when it exists.

A result at one layer is never reported as a result about the whole system.

## Decision-layer measurement — routes and confidence (founder-adopted, 2026-10-22)

The Decision layer is measured through different routes:

- **vendor-confirmed** — the harness ships a native offline decision oracle;
- **reconstructed** — decisions are computed from documented policy semantics;
- **no paper surface** — no decision interface exists to evaluate.

The number of INDEPENDENT routes that agree is the CONFIDENCE in OUR
Decision verdict: two routes cross-checked and agreeing = high confidence;
one route = lower confidence; no route = the Decision layer is unreadable
for that harness, and the Live Test is the only measurement. Confidence
attaches to our measurement, never to the harness — it is NOT a grade,
ranking, or score of any harness.

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
- **Measurement route** — how the Decision-layer verdict was obtained (see routes
  below): `vendor-confirmed`, `reconstructed`, or `no paper surface`. An
  adapter may never re-implement the harness's matching logic and present
  the result as the harness's decision; where decisions are computed from
  documented semantics instead of the vendor's own checker, the evidence
  class drops accordingly and the report says so.
- **Layer vocabulary** — every finding names its layer, in the framework's
  three-layer model: **Decision** (Layer 1) = what the rules decide (machine
  label `rules`: the declarative policy engine); **Approval** (Layer 2) = the
  approval moment (machine label `approval`: the human/classifier gate);
  **Effect** (Layer 3) = what actually happens (machine labels `sandbox` +
  `effect`: OS-level confinement and the observed runtime outcome — the
  ground-truth layer; sandbox confinement is part of what observably happens
  when a command runs). The machine labels `rules` / `approval` / `sandbox` /
  `effect` are never renamed.
  Unknowns carry mandatory layer attribution (INV-004, Option A).
- **Evidence emission** — findings in the bundle format, unknowns
  serialized as unknown, never as allow (INV-005).

## Measurement routes — provenance of the Decision-layer measurement

**Founder model correction (2026-10-22 ~18:29 PDT, controlling).** Grades and
tiers are abolished as attributes or rankings of harnesses: ease of
measurement never makes a harness better or worse. What the grades actually
were is **provenance of the Decision-layer measurement only** — the distinction
lives entirely inside the Decision layer (the policy-decision layer). It says how a
Decision-layer verdict was obtained, nothing about the Approval or Effect layers, and nothing about
harness quality. The labels are unranked and descriptive:

| Route | Meaning | Evidence class |
|---|---|---|
| **vendor-confirmed** | The vendor's own checker answers: decisions obtained from the harness's shipped offline decision surface (e.g. `codex execpolicy check`, `amp permissions test`), deterministic. | REPRO |
| **reconstructed** | Evaluated from the vendor's documented semantics (the vendor ships no decision checker); labelled as evaluation, not interrogation. | DOC + INFERENCE |
| **no paper surface** | No rule surface exists to evaluate. The adapter records the policy surface, its defaults, and the absence of a decision route. No verdicts are issued. | DOC |

A no-paper-surface result is a publishable finding, not a failure of the
framework: "this harness offers its users no way to ask what their policy
decides" is exactly the kind of fact the Boundary Index exists to record.
The route is a machine field on every adapter manifest (`measurement_route`).

FinePrint runs two tests. The **PAPER TEST** asks the offline question:
*what does the harness's rulebook decide for this command, without running
anything?* — it measures the Decision layer, and every paper-test finding carries its
measurement route. The **LIVE TEST** asks the online question: *what
observably happens when it runs?* — it measures the Effect layer (ground truth). The
paper test is the measured side today (two vendor-confirmed routes: Codex,
Amp); the live test's pilot is pre-registered
(`docs/effect-pilot/PREREGISTRATION.md`) and its execution is blocked on
authentication, so observed effect stays NOT_TESTED until it runs.

**Cross-Examination** — the method's core move: for each invariant, the
declared intent, the Decision layer's ruling (what the harness's policy
engine decides), and the Effect layer's observed outcome (what observably
happens) are examined against each other; a disagreement between any two
is a finding. The name was adopted by the founder's tap on 2026-10-22
(chosen over Triangulation and Layercheck). The invariant schema states the
declared intent; the paper test measures the Decision layer; the live test
measures the Effect layer. Every finding names the two that disagreed and
the layer where the disagreement was measured.

## The five target harnesses

Priority order is methodological (cleanest decision surface first), then
adoption (config-corpus prevalence from *Scanning the Harness*, 3,171
public repos, THIRD-PARTY):

| # | Harness | Policy surface (as researched) | Corpus repos | Status |
|---|---|---|---|---|
| 1 | **Codex** (OpenAI) | `execpolicy` `.rules`, prefix rules, `execpolicy check` CLI | 212 | **vendor-confirmed** adapter done (v0, pinned 0.149.0) |
| 2 | **Claude Code** (Anthropic) | `settings.json` permissions allow/ask/deny, PreToolUse hooks, Bash sandbox; auto-mode classifier (stochastic Approval-layer mechanism) | 1,887 | Measured **reconstructed** (Oct 22 wave) |
| 3 | **Cursor** (Anysphere) | IDE/CLI permission settings, rules files | 315 | Measured **reconstructed** (Oct 22 wave) |
| 4 | **Gemini CLI** (Google) | Settings/policy config, sandbox flags (off by default per research) | 273 | Measured **reconstructed** (Oct 22 wave) |
| 5 | **OpenCode** (open source) | `opencode.json` per-tool permissions (allow/ask/deny) | 142 | Measured **reconstructed** (Oct 22 wave) |

GitHub Copilot CLI was assessed 2026-10-22: **reconstructed** (from
configuration; account-walled) — install is not auth-walled but every live
evaluation route sits behind the account/subscription wall at `/login` (the
wall, not the semantics, is the binding constraint); offline binary
inspection found no checker-like entrypoint. Assessment:
`adapters/copilot-assessment.md`.

**Spike question for every harness, in order:** (a) Is there a deterministic,
offline way to obtain the harness's own decision for a command under a given
policy — a vendor-confirmed route? (b) If not, are the semantics documented
precisely enough for an honest reconstructed-route adapter — one that
computes decisions from documented semantics and labels them *evaluation*,
never *interrogation*? (c) If neither, the harness has no paper surface:
record the surface, its defaults, and the absence of a decision route; issue
NO verdicts. No harness gets verdicts its surface cannot support.

## What does not change

- The Day-7 kill criterion was evaluated on the Codex evidence and
  the same-corpus baselines (verdict NARROW, delivered Oct 21); the evidence
  basis now extends to Amp's vendor-confirmed route (recognized Oct 22: Amp
  ships its own offline decision checker, verified that day). Framework
  breadth does not dilute it.
- Scope discipline (per `docs/SCIENTIFIC_REVIEW_ADDENDUM.md`): general
  agent frameworks, MCP gateways, and model APIs are not coding-harness
  policy surfaces and stay out of this framework.
- Claims discipline: a harness is described by its measurement route, never
  as generically "supported." Cross-harness statements in public material
  must name the route mix behind them.

## Surveyed field (2026-10-21 field survey — appended, core definitions above unchanged)

Source: `~/workspace/research_notes/harness-field-survey-2026-10-21.md`
(web search + page-text fetch only; identities verified against primary
sources where reachable). Evidence classes follow the project scheme
(DOC / REPRO / THIRD-PARTY / INFERENCE / HYPOTHESIS). Adoption figures are
THIRD-PARTY unless noted. Nothing here changes the Day-7 kill criterion
(Codex vendor-confirmed evidence) or the route definitions above.

### Surveyed-field table (harness → route evidence → decision-route status)

| Harness | Route evidence | Decision-route status |
|---|---|---|
| **Amp** (Amp Inc.; ex-Sourcegraph) | **vendor-confirmed** (recognized 2026-10-22, founder decision). `amp.permissions`: tool glob + arg matches, action allow/reject/ask/delegate, `delegate --to` helper by exit code | **vendor-confirmed:** `amp permissions test` is a deterministic offline native decision oracle — 13/13 spike probes REPRO'd byte-identically across two runs (verified offline with invalid server URL); full 41-case corpus + protected family replayed byte-identically in the promotion run (pinned `0.0.1792680614-g8973a3`, sealed `evidence/amp-2026-10-22/`). First-match-wins precedence, user rules precede built-ins; no-match → unknown (INV-005). See `docs/amp-spike-2026-10-22.md` (REPRO) and `adapters/amp.manifest.json` (active) |
| **Zed Agent** (Zed Industries, open source) | ADAPTER-CANDIDATE. `agent.tool_permissions`: default allow/confirm/deny + per-tool regex `always_allow`/`always_confirm`/`always_deny` (deny binds even when default is allow); documented deterministic semantics; evaluator inspectable in source | reconstructed (no CLI checker shipped; documented-semantics evaluation straightforward; vendor-confirmed-via-source spike conceivable) (DOC) |
| **Warp** (commercial terminal+agent) | ADAPTER-CANDIDATE. `settings.toml` regex `agent_mode_command_execution_allowlist`/`_denylist`; **denylist takes precedence** over allowlist and "Agent decides"; shipped defaults published | reconstructed (closed source; regex-vs-command-string + precedence fully documented) (DOC) |
| **Goose** (Block → Agentic AI Foundation, Apache-2.0) | ADAPTER-CANDIDATE. YAML config: `GOOSE_MODE` + per-tool `AlwaysAllow`/`AskBefore`/`NeverAllow`; extension allowlist gates MCP installs | reconstructed at tool granularity (command-argument granularity not expressed) (DOC) |
| **Crush** (Charmbracelet, open source) | ADAPTER-CANDIDATE. `crush.json` `allowedTools`: `toolName` and `toolName:action` (e.g. `bash:execute`); dedicated permission service; crispest config semantics in the open-source CLI set | reconstructed (DOC) |
| **Roo Code** (VS Code, Cline-fork family) | ADAPTER-CANDIDATE (last of the six — mode-scoped settings semantics need a spike). Per-Mode settings: command allow/deny lists, per-mode tool & MCP permissions | reconstructed (DOC) |
| **Pi** (earendil-works/pi, MIT; 116,973 stars platform data 2026-10-21) | no-paper-surface headline: README states **no built-in permission system at all** — boundary is "whatever the launching process could do" | None by design; future adapters would measure extension/container layer, not a Pi policy engine (DOC) |
| **OpenClaw** (openclaw/openclaw, MIT; 392,702 stars platform data) | no paper surface: general personal-agent platform; declarative per-agent `tools.allow`/`tools.deny` + sandbox modes; coding delegated via ACP to Pi/Claude Code/Codex/OpenCode/Gemini — the harnesses already in our corpus | None for command decisions (tool-gating layer is a plausible future reconstructed-route evaluation target) (DOC/THIRD-PARTY) |
| **Hermes Agent** (NousResearch, MIT; 255,955 stars platform data) | no paper surface: general-purpose agent runtime; coarse toolset enable/disable + 7 terminal backends; no per-command declarative policy | None documented (DOC) |
| **Aider** (Aider-AI, Apache-2.0) | no paper surface: confirmation prompts + config flags; `--yes-always`; **auto-commits ON by default** (the field-map note). Activity caveat: latest tag v0.86.0 (Aug 2025), last pushed May 2026 (THIRD-PARTY) | None (no rule language, no oracle) |
| **Cline** (Apache-2.0; 5M+ installs THIRD-PARTY) | no paper surface (borderline): Auto Approve per-category toggles over an internal safe/requires-approval classifier — a heuristic, not a developer-authored rule file | None offline |
| **Continue** (continuedev, Apache-2.0) | no paper surface: per-tool policies (Automatic/Ask); Plan mode read-only. **Status caveat: repo now read-only, unmaintained**, final 2.0.0 (THIRD-PARTY). Survey for the historical record only — do not build an adapter | None |
| **Windsurf** (proprietary IDE agent) | no paper surface: terminal auto-execution levels Disabled / Allowlist Only / Auto (AI-judged) / Turbo (denylist); org-admin caps. "Auto" is model-judged — stochastic decision layer, Phase-2 methodology territory | None offline |
| **Amazon Q Developer CLI** (AWS, open source) | no paper surface: tool-granularity trust (trusted/per-request); persisted only via custom-agent JSON `allowedTools` | No command-pattern rules, no oracle |
| **JetBrains Junie** | no paper surface: approval prompts + all-or-nothing "Brave mode" + dynamic allowlist; `.junie/guidelines.md` is instruction, not policy | None (closed source) |
| **Kiro** (AWS) | no paper surface, **most likely route-change candidate**: capability-based permissions evaluating every read/command/MCP call; consent decisions persist as workspace/global rules — but rule grammar/evaluator not publicly documented enough for a reconstructed route today | None evaluatable today |
| **Void** (open-source VS Code fork) | no paper surface: per-tool approval prompts + auto-approve; no declarative rule language in primary sources | None |
| **Trae** (ByteDance; IDE + open-source trae-agent) | no paper surface: SOLO mode autonomous by design; no declarative permission policy located in primary sources — the documentation gap is itself the finding | None located |
| **Qwen Code** (Alibaba; Gemini CLI fork family) | no paper surface: `tools.approvalMode` incl. LLM-classifier "Auto" — stochastic decision layer | None |
| **Kilo Code** (Cline/Roo fork family, MIT) | no paper surface: fork-family auto-approve surface; nothing independently declarative beyond Roo Code's (if the family gets one adapter, Roo Code is the target) | None |
| **Muse Code** (Meta; terminal coding agent, `muse` binary, 1.4.11) | no paper surface (assessed 2026-10-22): no deterministic offline decision oracle in the CLI surface or official docs; surface and defaults recorded, no verdicts. **Naming caveat:** this is the terminal coding agent, NOT the Muse personal assistant — different products, different surfaces | None located offline (DOC+REPRO) |
| **GitHub Copilot CLI** (@github/copilot 1.0.103) | reconstructed-from-configuration (assessed 2026-10-22): install is not auth-walled; offline binary inspection (read-only, scratch COPILOT_HOME) found no oracle-like entrypoint; **every live evaluation route sits behind an account/subscription wall at `/login`** — the wall, not the semantics, is the binding constraint | reconstructed from documented semantics; no live interrogation without auth (REPRO for the install/inspection; DOC for semantics) |

### Out of scope (surveyed, excluded with reason)

- **OmniAgent** — name collision across ≥5 unrelated projects; no single system with verifiable significant adoption. OUT. (Reopen only with a disambiguating repo URL.)
- **Hermes (models)** — Nous Research model family: a model is the engine other harnesses run; no permission surface. OUT.
- **Sourcegraph Cody** — Free/Pro discontinued 2025-07-23; individuals directed to Amp. Superseded by Amp. OUT.
- **PearAI** — VS Code fork bundling Continue + Aider; its policy surface IS Continue's. Measure the upstream. OUT.

### Adapter-candidate #6 and the bench/wave lists

- **Candidate adapter #6: Amp.** Recognized as **vendor-confirmed** 2026-10-22 (founder
  decision); it displaced the "Copilot as candidate sixth" placeholder in
  *priority* (not in scope): Amp is the only vendor besides OpenAI with a
  shipped permission *test* command, which made the vendor-confirmed spike — and then the
  recognition — the obvious next adapter bet. GitHub Copilot remains a
  candidate, but with the least declarative surface of the set.
- **Reconstructed bench:** Zed → Warp → Goose → Crush → Roo Code (Amp removed
  when its route was recognized as vendor-confirmed).
- **No-paper-surface wave:** Pi, OpenClaw, Hermes Agent, Aider, Cline, Continue, Windsurf,
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
2. The real adapter gaps were elsewhere: the reconstructed bench above (Amp led it until
   its vendor-confirmed recognition).
3. Star counts (Pi 116,973; Hermes Agent 255,955; OpenClaw 392,702) are from
   GitHub repo pages fetched 2026-10-21; they measure attention, not deployed
   usage, and are used only as "meaningful adoption" triage signals.
