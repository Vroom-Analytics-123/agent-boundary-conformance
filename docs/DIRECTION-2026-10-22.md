# Founder direction — 2026-10-22 (~18:15 PDT)

> **Supersession note — 2026-10-22 (~18:29 PDT, the founder's third and
> controlling iteration).** §2 ("Grades = strength of evidence") below is
> SUPERSEDED and is preserved as the record of the earlier iteration, not
> rewritten. Grades and T1/T2/T3 ranking labels are abolished: ease of
> measurement never makes a harness better or worse. What the grades actually
> were is provenance of the Layer-1 (Decision-layer) measurement only — now
> named, unranked: **vendor-confirmed** (the vendor's own checker answers:
> Codex, Amp), **reconstructed** (evaluated from documented semantics:
> Claude Code, Cursor, Gemini CLI, OpenCode; Copilot
> reconstructed-from-configuration, account-walled), **no paper surface**
> (Pi, Muse Code). The scoring rule in §3 stands in substance — layer
> outcomes first, a failed layer dominates — with the measurement route
> annotating confidence in the Decision-layer finding, never ranking
> harnesses. The layers are named **Decision · Approval · Effect** (adopted
> by the founder's tap ~18:38 PDT): Decision (Layer 1) = what the rules
> decide; Approval (Layer 2) = the approval moment; Effect (Layer 3) = what
> actually happens — ground truth, the most important layer.

Founder: Anish Kumar. Recorded verbatim-intent, paraphrase-faithful, by
avan. This is a direction log: it adopts no measured claim, changes no
schema, touches no sealed bundle. The naming candidates below were
PENDING the founder's tap at recording time; the founder tapped
**Cross-Examination** (~18:17 PDT the same evening, chosen over
Triangulation and Layercheck), and the adoption is recorded below.

## 1. Layer primacy — cross-layer checking is the core method

What makes FinePrint powerful is checking ALL layers AND checking them
AGAINST EACH OTHER (founder-adopted layer names, 2026-10-22 ~18:38 PDT):

- **Stated intent** — what the developer declared (invariant / policy)
- **Decision** (was "Layer 1") — what the harness's rules decide about a command
- **Approval** (was "Layer 2") — the approval moment: a human or classifier is asked
- **Effect** (was "Layer 3") — what actually happens when it runs; ground truth, the most important layer. The Live Test is the main event; paper findings are provisional until the Live Test confirms or refutes them

The power is in the comparison: intent vs. decision vs. effect, each pair
checked against the other. This cross-layer checking is the core method
of the framework — not an add-on, not a report section. Everything the
framework measures should serve it.

**Naming (ADOPTED by the founder's tap, 2026-10-22 ~18:17 PDT):** the
cross-layer check is called **Cross-Examination** — chosen over the other
candidates, Triangulation and Layercheck.

Cross-Examination — the method's core move: for each invariant, the
declared intent, the policy engine's decision, and the observed effect are
examined against each other; a disagreement between any two is a finding.

## 2. Grades = strength of evidence

Founder-endorsed framing, adopted as clarifying: grades are strength of
evidence. Harnesses that offer more evidence ARE better and are graded as
such:

- **Grade A · Oracle** — the harness ships a native offline decision oracle
- **Grade B · Manual** — decisions are computed from documented policy semantics
- **Grade C · None** — no decision interface exists to evaluate

The grade names the evidence class behind every finding. It is not merely
taxonomic — it is the honest statement of what the measurement rests on.

## 3. Scoring rule — LAYER FAILURE DOMINATES (new, the founder's rule)

The verdict's impact ordering is:

1. **Layer outcomes first** — if a layer fails, that is the most impactful outcome.
2. **Evidence strength second** — the grade is confidence in the finding, never a substitute for the finding.

Consequence: a result with WEAK evidence but working layers ranks BETTER
than a result with STRONG evidence and a failed layer.

**Scorecard v-next implementation note:** findings must be sorted/weighted
by layer outcome first; the evidence grade annotates confidence. The
current scorecard does not yet implement this ordering — record it as a
required v-next change, not as current behavior.

## 4. Catalogue transferability — first-class design goal

Founder-endorsed enthusiastically: the invariant catalogue must be easily
transferable across coding agents/harnesses. The mechanism is per-harness
translations in catalogue entries, built on the per-harness knowledge the
measurement program accumulates. Transferability is a design goal of the
catalogue on par with honesty of measurement — see the dated note in the
`docs/catalogue/CATALOGUE.md` design rules.

---
*Recorded 2026-10-22 by avan from the founder's direction (~18:15 PDT).
Documentation of direction only: no measured claim, sealed bundle, or
schema changed in this pass.*

## Adoption note — measurement-layer names Decision · Approval · Effect (2026-10-22 ~18:38 PDT)

Adopted by the founder's tap + message, 2026-10-22 ~18:38 PDT: the three
measurement layers are named **Decision · Approval · Effect**, presented
in that order.

- **Decision** (was "Layer 1"): what the harness's rules decide about a
  command. The paper test measures this layer.
- **Approval** (was "Layer 2"): the approval moment — a human or
  classifier is asked.
- **Effect** (was "Layer 3"): what actually happens when the command
  runs. Effect is GROUND TRUTH and the most important layer; the Live
  Test is the main event; paper findings are provisional until the Live
  Test confirms or refutes them.

Decision-measurement confidence (adopted in the same direction): the
Decision layer is measured through different routes — vendor-confirmed
(the harness ships a native offline decision oracle) / reconstructed
(decisions computed from documented policy semantics) / no paper surface
(no decision interface exists to evaluate). The number of INDEPENDENT
routes that agree is the CONFIDENCE in OUR Decision verdict: two routes
cross-checked and agreeing = high confidence; one route = lower
confidence; no route = the Decision layer is unreadable for that
harness, and the Live Test is the only measurement. Confidence attaches
to our measurement, never to the harness — it is NOT a grade, ranking,
or score of any harness.
