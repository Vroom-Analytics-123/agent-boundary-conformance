# Implementation Design — Agent Boundary Conformance Tester (v1, 2026-10-20)

## Language decision: Rust — for concrete reasons, not vibes
1. **The first harness is Rust.** Codex is `codex-rs`; `execpolicy` is a Rust crate in the open-source openai/codex repo, and its rules are Starlark evaluated by the Rust `starlark` crate. A Rust implementation speaks the harness's native language: same ecosystem, potential to embed the actual policy crate later, zero impedance mismatch on the semantics we must mirror exactly.
2. **Determinism is the product.** The tool's entire claim is reproducible evidence. Rust gives a single static binary, no runtime/version drift on user machines, and strict typing for verdict semantics (an `Unknown` that can never silently coerce to `Allow` can be an enum the compiler enforces).
3. **CI distribution.** One binary, no interpreter, trivially cached in GitHub Actions — the channel the tool spreads through.
Costs accepted: slower iteration than Python/TS; mitigated by keeping v1 small and shelling out to the pinned `codex` binary rather than reimplementing policy evaluation.

## Architecture (v1, week 1)
```
boundary-conformance (Rust workspace, single binary crate for v1)
├─ invariants   Parse security/invariants.yaml (serde_yaml) into typed structs.
│               schema_version: boundary.v0. Validation errors are hard failures —
│               a malformed invariant file must never produce a green report.
├─ fixtures     Case loader: argv, pinned config (rules files, resolution flag,
│               host_executable entries), expected decision set.
├─ oracle       trait DecisionOracle { fn decide(&self, case) -> NativeDecision }
│   └─ codex    Shells to the PINNED codex binary:
│               `codex execpolicy check --rules <f> [--resolve-host-executables] -- <argv>`
│               Captures raw stdout JSON verbatim (it IS the evidence), plus
│               codex --version. Never reimplements prefix matching in v1 —
│               semantics identical by construction.
├─ verdict      Normalizer: native output -> Pass / Fail / Unknown(+layer attribution).
│               No-match => Unknown, always. Strictest-wins is the harness's job;
│               we only compare its final decision against the invariant's expected set.
├─ evidence     Bundle writer: JSON { tool version, harness version, policy file
│               SHA-256, pinned config, raw native output per case, verdict,
│               evidence class }. Hash-chained per run so a report can be
│               re-verified against the repo alone.
└─ report       Standalone HTML rendered from the evidence bundle (no server,
                no JS dependencies) + the JSON itself. CI mode = exit code
                (0 pass / 1 fail / 2 unknowns-present, configurable) — added
                Day 6 only if the suite is stable.
```
Crates (all standard, boring, maintained): `clap` (CLI), `serde`/`serde_json`/`serde_yaml`, `sha2`, `anyhow`/`thiserror`. That's the whole dependency story for v1 — deliberately.

## The runtime probe (Day 3–4 experiment, separate evidence type)
Decision checks say what the rules layer *decides*; they don't observe the approval/sandbox layers. The probe runs `codex exec` in a throwaway directory with **pinned** `approval_policy` + `sandbox_mode`, a synthetic target file, and records: was approval requested, was the command executed, did the synthetic effect occur. Output is labelled `runtime-probe` evidence — never merged with decision evidence. This is how the wrapped-command question gets an honest empirical answer instead of rhetoric.

## Where the fancy pieces actually belong (and when)
- **petgraph** (the standard Rust graph library): NOT in v1. Its real job arrives with effect-level verification: model an approved invocation and its transitive effects (file writes, spawned processes, network calls, installed hooks) as a directed graph and compute the effect *closure* — which is precisely the formalism of the Transitive Effects paper (Zhang et al.). Reachability/closure over that graph is a petgraph-shaped problem. Using it in week 1 would be decoration.
- **Jev** (TypeSafe's decision-model API — a hosted "System One" judgment model returning Choice/Score/probability): a *rented judgment API* with a large integration ecosystem (LangChain, Pydantic AI, Vercel AI SDK, a Rust SDK via Rig). For AnswerGraph's evidence/challengeability layer it may be a reasonable component. For THIS tool it is disqualified from verdicts: an LLM-judgment call inside the measurement path destroys determinism — the one property the product sells. At most, an optional, clearly-labelled assistant for *drafting* invariants a human then approves. And "we use Jev" is not a moat — anyone can call the same API.
- **Laconic** (`github.com/smhanov/laconic`, verified 2026-10-20 from the repo Anish supplied): a tiny **Go** library for research agents optimized for small-context/cheap models — two strategies, Scratchpad (rolling compressed summary) and Graph Reader (traverses a graph of search queries, extracts *atomic facts tagged with source URLs* into a deduplicated notebook; inspired by the GraphReader paper). ~260 stars, MIT, stdlib-only. Relevance: the Graph Reader fact-notebook is a genuinely good reference pattern for **AnswerGraph's** evidence layer (atomic facts + provenance + dedup). It has no role in this tester: wrong language (Go vs the Rust core), wrong job (LLM research orchestration vs deterministic policy decisions). Earlier "could not identify" note corrected — the miss was searching for it as a Rust crate.
- **MCTS**: no role anywhere in v1; search over policy-fix candidates is a research idea, not an engineering need.

## Design principles inherited from prior art (the "backed by latest work" map)
| Decision | Backed by |
|---|---|
| Test intent against native decisions; don't build a new policy engine | conftest/OPA policy-testing tradition; Cedar's analyzable-authorization philosophy |
| Keep decision / approval / effect as separate evidence types | OpenAI approvals docs (three real layers); Day-0 Correction Addendum |
| Effect closure as the stage-2 research target | Zhang et al., Approval Laundering + Transitive Effects (arXiv 2609.38983 / 2609.28586) |
| Corpus method, defect/fixture taxonomy, public replayable artefacts | Kapner et al., Scanning the Harness (arXiv 2609.07360; 3,171-repo corpus) |
| Evidence bundle as interchange-ready JSON (SARIF export later) | SARIF standard practice in static-analysis tooling |
| Independent, cross-vendor stance as the defensible layer | Landscape analysis: vendors ship enforcement for their own harness (Microsoft AGT, Codex profiles); none publishes cross-harness divergence |

## Explicit non-goals for v1
No LLM anywhere in the verdict path. No graph library. No SaaS. No auto-merge of fixes (Day 5 = one human-approved diff). No Claude adapter beyond the Day-4 feasibility spike. If it doesn't make the Codex evidence more trustworthy, it waits.

## Addendum v1.1 (2026-10-22) — two-oracle method; measured B · Manual adapters

v1 above is the 2026-10-20 record; what follows supersedes its single-oracle
framing. Execution is continuous (no longer day-gated).

- **Second oracle: Amp.** The `oracle` trait gains an `amp` implementor:
  shells to the pinned `amp` binary (`0.0.1792680614-g8973a3`,
  `tools/vendor/amp/…`, git-ignored) via `amp permissions test --json
  <Tool> --cmd "…" [--settings-file <policy.json>]`; captures raw stdout JSON
  verbatim as evidence. Native action vocabulary (`allow`/`ask`/`reject`/
  `delegate`/no-match) normalizes to the framework's allow/prompt/forbidden/
  unknown per INV-005 (no-match → unknown, never allow). Promoted to paper
  grade **A · Oracle** by founder decision 2026-10-22; sealed
  `evidence/amp-2026-10-22/bundle.json` (Merkle `cb6eccf0…`, Ed25519-signed).
  Adapter contract: `adapters/amp.manifest.json` (active).
- **Measured B · Manual adapters.** The 2026-10-22 all-harness wave measured
  the config-evaluation adapters for Claude Code, Cursor, Gemini CLI, and
  OpenCode (doc-cited engine tests: 85/85, 38/38, 33/33, 43/43) — labelled
  evaluation, never interrogation; manifests declare
  `oracle.type: config-evaluation`. Muse Code assessed **C · No paper**; GitHub
  Copilot CLI assessed B · Manual-config (account wall at `/login`).
- The v1 non-goals stand, updated: no adapter re-implements a harness's
  matching logic and presents the result as the harness's decision
  (framework invariant, enforced per manifest).
