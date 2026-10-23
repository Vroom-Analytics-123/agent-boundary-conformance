# The Three-Layer Measurement Model

*Design note — 2026-10-22. Status: DESIGN-STAGE DOCTRINE. This note records a
model, not a measurement. The Decision routes below exist and are measured;
the Approval and Effect routes are design sketches — proposed, not built.*

*Origin: founder direction, Oct 22, 2026 (~18:39 PDT): "I think we need
something similar for approval and effect as we have for decision as in we
need different ways of measuring it and that would give us confidence but
also knowing that the main test is always the approval taking place live and
the effect having a live change."*

## The three layers

Adopted names (founder's tap, 2026-10-22): **Decision · Approval · Effect**.

- **Decision** (Layer 1) — what the harness's rules decide about a command.
  The PAPER TEST measures this layer.
- **Approval** (Layer 2) — the approval moment: a human or classifier is asked.
- **Effect** (Layer 3) — what actually happens when the command runs. The LIVE
  TEST measures this layer. **EFFECT IS GROUND TRUTH and the most important
  layer** (the founder's explicit priority).

**Cross-Examination** = comparing the layers against each other (declared
intent vs Decision-layer decision vs Effect-layer effect); a disagreement
between any two is a finding; Effect is the reference standard when it
exists.

## Routes: every layer is measured through multiple routes

A **route** is an independent way of obtaining a layer's answer. Statuses:
**MEASURED** (built and run), **PROTOCOL-LOCKED** (written into the locked
live-test protocol but awaiting execution), **PROPOSED** (design sketch only).

### Decision routes

| # | Route | How | Status |
|---|-------|-----|--------|
| D1 | Vendor-confirmed | The vendor's own checker answers (e.g. Codex's native checker) | MEASURED |
| D2 | Reconstructed | Evaluation from documented semantics | MEASURED |
| D3 | Cross-check | The fidelity calibration — vendor-confirmed vs reconstructed agreement (Codex 52/52, Amp 21/52). **This cross-check IS the Decision-confidence measurement.** | MEASURED |

No paper surface = Decision unreadable by these routes; then the Live Test
(Effect) is the only measurement.

### Approval routes

| # | Route | How | Status |
|---|-------|-----|--------|
| A1 | Promised | Derived expectation: a Decision of *prompt* owes an ask. An expectation, **not** an Approval measurement. | PROPOSED |
| A2 | Configured | The harness's approval settings/mode as configured (`approval_policy`, permission mode, auto-review), read from config and vendor docs | PROPOSED |
| A3 | **Witnessed live — KEYSTONE** | The agent actually pauses and asks during a contained run | PROPOSED |
| A4 | Recorded | Session transcripts/logs evidencing that an ask occurred | PROPOSED |

### Effect routes

| # | Route | How | Status |
|---|-------|-----|--------|
| E1 | Sentinel state | Job-created throwaway assets checked after the run (present / altered / gone) | PROTOCOL-LOCKED |
| E2 | Sandbox diff | Full before/after diff of the contained environment | PROTOCOL-LOCKED |
| E3 | System trace | OS-level file/process instrumentation, independent of agent and sandbox bookkeeping | PROPOSED |
| E4 | Agent self-report | What the agent claims it did. Weakest route; **never sufficient alone.** | PROPOSED |

## The confidence rule

**CONFIDENCE in a layer verdict = the number of independent routes that
AGREE.** Two routes cross-checked and agreeing = high confidence; one route =
lower confidence; no route = the layer is unreadable by our methods.

Confidence attaches to **OUR measurement**, never to the harness. It is not a
grade, ranking, or score of anything.

## The keystone rule

Each layer has a **KEYSTONE route** — the measurement that settles it:

- **Decision:** the vendor's own checker, when one exists.
- **Approval:** the approval **TAKING PLACE LIVE** in a contained run.
- **Effect:** a **LIVE CHANGE** actually observed (routes E1–E2 in the current
  protocol).

The founder's rule: **"the main test is always the approval taking place
live and the effect having a live change."**

## Current-state honesty box

- Decision routes exist and are measured (D1–D3, above).
- Approval and Effect routes are **design-stage**. Nothing in this note may
  claim an Approval or Effect measurement exists.
- **ALL live routes are currently blocked by the auth wall** (Paper-vs-Live
  wave: 9/9 harnesses blocked-by-auth, 0/108 cases run). Route A3, route E1,
  and route E2 have no live evidence yet — the keystones are the standard we
  are working toward, not results we have.

*Recorded 2026-10-22 by avan, at the founder's direction.*
