# The Boundary Measurement Framework

*Status: adopted Oct 21, 2026 at the founder's direction — the project is a
framework with adapters, not a single-harness tool. The framework is the
durable asset: it must be valuable on its own, with zero adapters, because
its schemas, protocol, and evidence format are what other tools, vendors,
and standards bodies can adopt.*

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
   before a run; public / held-out corpus split; negative controls in every
   run (a run that passes its negative controls is broken); two-sided
   verdicts (over-blocking legitimate work is a failure, not a safety win);
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
