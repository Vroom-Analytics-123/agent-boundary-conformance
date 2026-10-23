# Extending FinePrint — how to add a harness or framework target

*Contributor guide, 2026-10-22. Worked examples are the six Wave A targets
(Omnigent, Hermes Agent, OpenClaw, LangGraph, Strands Agents, CrewAI),
added design-stage the day this guide was written.*

## The model you are extending

FinePrint measures whether an agent's **enforced** limits match its
**stated** limits, across three layers:

- **Decision** — what the target's rules decide about an action.
- **Approval** — the approval moment: a human or classifier is asked.
- **Effect** — what actually happens when the action runs. **Ground truth.**

Every layer is measured through **routes** — independent ways of obtaining
that layer's answer (`docs/MEASUREMENT_MODEL.md` is the doctrine of
record). **Confidence = the number of independent routes that agree**, and
it attaches to *our verdict*, never to the target. Routes are unranked:
ease of measurement never makes a target better or worse.

The Decision-layer route vocabulary (used everywhere, including the
catalogue):

| Route | Meaning |
|---|---|
| **vendor-confirmed** | The vendor's own checker answers, offline and deterministically, at a pinned version. |
| **reconstructed** | We compute the decision from documented semantics. Labelled *evaluation*, never *interrogation*. |
| **no paper surface** | No decision interface exists to read. The surface and its defaults are recorded; **no verdicts are issued**. Frameworks usually land here — their coverage path is a live instrumented reference agent, not a paper route. |

**Honesty rails (non-negotiable):**

1. Nothing is `MEASURED` until a measurement actually ran, at a pinned
   version, with evidence. Design-stage work is labelled design-stage.
2. An unmatched action is **unknown**, never allow. Unknowns carry layer
   attribution.
3. Claims carry an evidence class — `DOC` (vendor docs), `REPRO` (directly
   inspected/reproduced), `THIRD-PARTY` (credible secondary), `INFERENCE`
   (our reasoning) — and anything primary sources cannot establish is
   recorded as unknown with the reason. Never fill a gap with plausible
   text.

## The five artefacts of a target

Adding a target produces, in order:

1. **Route dossier** — `adapters/<key>-assessment.md` (the survey).
2. **Adapter manifest** — `adapters/<key>.manifest.json` (the machine-
   readable surface record).
3. **Catalogue translations** — `docs/catalogue/translations-draft/<key>.json`
   (draft per-invariant translations; merged into the generated catalogue).
4. **Route assignment** — a row in `docs/MEASUREMENT_ROUTES.md`.
5. **Later, when measured:** an executable adapter under `adapters/<key>/`
   plus sealed evidence under `evidence/`. Not part of a design-stage add.

`<key>` is the target's snake_case catalogue key (`claude_code`,
`langgraph`, …). Display names live in the fragment's `display` field.

## Step 0 — Pin the identity before anything else

Names collide. Before assessing anything, establish *which* product the
name refers to, from primary sources, and record the rejected candidates.

Worked examples (Wave A): "Hermes" was pinned to **Hermes Agent (Nous
Research)** by Omnigent's own launcher text (`omnigent hermes  # Hermes
Agent (Nous Research)`) — four rival candidates rejected with reasons in
the dossier. "OpenClaw" was pinned to `github.com/openclaw/openclaw`,
corroborated independently by Omnigent's `docs/openclaw.md`; a game-engine
reimplementation, a disclaimed PyPI namesake, and a hosting namesake were
excluded with evidence. If identity cannot be pinned, the dossier says so
explicitly and becomes an ambiguity/surface record — the precedent is
`adapters/muse-code-assessment.md`. Never assess a guessed product.

## Step 1 — Answer the three spike questions

From `docs/MEASUREMENT_ROUTES.md`, in order:

- **(a)** Is there a deterministic, offline way to obtain the target's OWN
  decision — a vendor-confirmed route? (Codex's `codex execpolicy check`
  and Amp's `amp permissions test` are the two positive examples in the
  tree.) A negative answer must state its scope: docs-only, or verified
  against an installed binary?
- **(b)** If not, are the semantics documented precisely enough for an
  honest reconstructed route — precedence, matching, defaults, all
  specified? (Claude Code's deny→ask→allow is the model case.)
- **(c)** If neither, the target has no paper surface: record the surface,
  its defaults, and the absence of a decision route. Issue no verdicts.

Surface-specific notes:

- **Coding-agent harnesses** (Hermes, OpenClaw): expect a config surface;
  check granularity hard — OpenClaw's allowlist is per-binary, never argv,
  and that limit belongs in every translation it touches.
- **Meta-harnesses** (Omnigent): the target's policies govern *other*
  harnesses' actions, so two governance levels exist. Record which level
  your routes observe, and whether the underlying harness's native
  approvals survive (for Omnigent this is an open question, recorded as
  one).
- **Frameworks** (LangGraph, Strands, CrewAI): there is no policy file to
  read — Decision lives in user code. Do not invent a reconstruction: a
  reconstructed verdict would fabricate the policy language itself.
  Assign **no paper surface** and design the reference agent (Step 5).

## Step 2 — Write the route dossier

Template: `adapters/copilot-assessment.md`. Required sections:

- Header: date, and the line that this is design-stage with **no
  measurement run**; a naming/identity note where relevant.
- Surface assessed: product, version pin (or an explicit "unpinned" with
  the reason — Hermes is the example), sources consulted with retrieval
  dates.
- Spike answers (a)/(b)/(c).
- **Decision surface / Approval machinery / Effect surface** — one section
  each. For Approval and Effect, state which routes (A1–A4, E1–E4 in
  `docs/MEASUREMENT_MODEL.md`) are applicable and their status.
- **Per-layer route table**: Layer | route | confidence | basis.
  Confidence: never "high" for design-stage work; "medium" only where
  vendor semantics are documented precisely, with the justification in
  the text (Hermes' deterministic core across three agreeing vendor docs
  is the bar).
- **LIVE-UNLOCK line**: exactly which account, subscription, or API key
  unlocks live Approval/Effect measurement. One line, verbatim-usable —
  it feeds the funding/credential plan. (LangGraph/CrewAI: a single
  provider key or a keyless local model. Strands: AWS + Bedrock access or
  an alternate provider key. Omnigent: no vendor account exists — an
  install plus any one documented model-credential kind.)
- Open questions, each with what would resolve it. Blockers. Evidence log
  listing the primary sources actually fetched.

## Step 3 — Write the adapter manifest

Template: `adapters/claude-code.manifest.json`; schema:
`adapters/manifest.v1.schema.json` (validate before committing). Keep the
shape: `manifest_version`, `harness` (the key), `evidence_class`,
`harness_version_pinned`, `layer_vocabulary` (`covered` / `ambiguous` /
`notes`), `oracle` (`type`, `deterministic_offline`, `invocation`,
`reimplements_matching`), `policy_ingestion` (`surface`, `config_files`,
`decision_verbs`, `defaults`), `sources`, `spike_answers`,
`measurement_route`, `measurement_route_evidence`, `open_questions`.
For frameworks, `oracle.type` is `none` and `policy_ingestion.surface`
states plainly that no declarative surface exists, naming the code-level
substitutes. Where identity was contested, add a top-level `identity`
field (Hermes and OpenClaw manifests carry one).

## Step 4 — Draft the catalogue translations

The catalogue (`docs/catalogue/`, generated by `tools/build_catalogue.py`)
is the transferable asset: a target joins by adding translations to the
existing invariants — never by rewriting them.

Create `docs/catalogue/translations-draft/<key>.json`:

```json
{
  "harness": "<key>",
  "display": "<Display Name>",
  "source_note": "Design-stage draft translations — <spike name/date>. NOT measured; no conformance claim.",
  "entries": {
    "FP-001": {"measurement_route": "...", "confidence": "...",
               "measured": false, "text": "..."},
    "...": "all 16 entries FP-001…FP-016"
  }
}
```

Rules:

- `measured: false` in **every** entry. The generator enforces this: a
  fragment claiming `measured: true` aborts the build.
- Express the invariant in the target's **own mechanism**, reusing the
  entry's parameter slots (`<command_bin>`, `<flag_set>`, `<target_path>`,
  …) from `docs/catalogue/catalogue.json`.
- End every text with the draft disclaimer: *"Draft template from
  documented semantics; NOT measured. Owner must review against the
  target's current docs and a measurement must exist before any
  conformance claim."*
- **No mechanism = say so.** Where the target cannot carry an invariant,
  the text states that plainly with the reason, and the entry's route is
  `no paper surface`. Worked example: 9 of CrewAI's 16 entries have no
  mechanism (its task guardrails validate outputs; they are not action
  policy, and the translations must not dress them up as such). LangGraph
  FP-014/FP-015 likewise: there is no policy layer to hold a precedence
  rule.
- Per-entry route may differ from the target's headline route where the
  mechanism differs (LangGraph carries 8 invariants via its reference-
  agent Approval gate as `reconstructed`, and 8 as `no paper surface`).

Merge: with the fragment in place, run `python3 tools/build_catalogue.py`
and commit the regenerated `catalogue.json` + `CATALOGUE.md` with the
fragment. Verify every entry carries the new key and no non-Codex
translation is marked measured.

## Step 5 — Frameworks: the instrumented reference agent

A framework target's coverage path is a **pinned, evaluator-authored
reference agent** whose run is observed live. The dossier designs it; the
design has four parts (LangGraph's dossier is the worked example):

1. **Canonical configuration.** Minimal agent, framework pinned, fixed
   code, a small dangerous-tool set standing in for the catalogue's
   actions. Findings attach to *(version × config × hooks × model)*,
   never to the framework's name in general.
2. **Where Decision is observed.** Nowhere as a verdict — only as a
   labelled *configured expectation* audited from the pinned source
   (the A2-configured analog). State the limits: any third-party hook or
   tool returns Decision to unobservable.
3. **Where Approval is observed.** At the framework's real pause point,
   pre-execution where it exists — LangGraph's `interrupt()` surfacing in
   the stream with checkpointer state as the record (A3-analog witnessed
   live; A4 = checkpointer history + driver log); Strands' interrupt /
   HITL handler; CrewAI's hook-wired `request_human_input`. **Timing is
   a finding, not a detail:** CrewAI's native `human_input` fires *after*
   the task's tool calls executed — record it as post-effect review,
   never as action approval.
4. **Where Effect is observed.** Wrap the run in
   `tools/effect_instrument.py`'s model — sentinel assets (E1) + sandbox
   diff (E2) under the containment in `docs/approval-effect-protocol.md`
   §3. Adaptations to record: the agent runs in its own process (in-
   process tool execution), cases arrive as prompts rather than argv,
   and containment rests on the outside-sandbox scan.

Also record what remains **unobservable** in the design (model tool-choice
rationale, unregistered capabilities, effects that never touch the
sandbox). An honest unobservable list is part of the deliverable.

## Step 6 — Route assignment row

Add the target's row to the assignments table in
`docs/MEASUREMENT_ROUTES.md`: harness + version, route (marked
design-stage), oracle type, and a one-line evidence summary naming the
dossier and manifest. Add a short revision note when a wave lands, in the
style of the existing revisions — including the sentence that nothing in
the wave is a measurement.

## Promotion: from design-stage to measured

A target's route is *recognized* only when its condition is met:

- **reconstructed → measured-evaluation:** build the evaluator from the
  documented semantics, pin the version, run the corpus, label every
  result evaluation (never interrogation), seal the evidence bundle.
- **→ vendor-confirmed:** only when the vendor ships a deterministic
  offline decision entrypoint at a pinned version, and it replays the
  corpus byte-identically (the Amp precedent, 2026-10-22).
- **Approval/Effect live routes:** follow `docs/approval-effect-protocol.md`
  (pre-registered, hash-locked before any live attempt) and the LIVE-UNLOCK
  credential recorded in the dossier.

## Before you commit — checklist

- [ ] Identity pinned from primary sources, or ambiguity declared.
- [ ] Every load-bearing claim evidence-tagged; unknowns carry reasons.
- [ ] Manifest validates against `adapters/manifest.v1.schema.json`.
- [ ] Fragment: all 16 entries, `measured: false` everywhere, disclaimer
      suffix on every text, no confidence above the justified level.
- [ ] Catalogue regenerated; counts and measured set unchanged.
- [ ] No sealed evidence bundle touched. No history rewritten. Nothing
      published or sent — publication is a founder decision, always.
