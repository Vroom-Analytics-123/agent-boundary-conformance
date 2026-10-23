# Founder direction — 2026-10-22 (~18:15 PDT)

Founder: Anish Kumar. Recorded verbatim-intent, paraphrase-faithful, by
avan. This is a direction log: it adopts no measured claim, changes no
schema, touches no sealed bundle. The naming candidates below are
PENDING the founder's tap and MUST NOT be adopted unilaterally in living
docs.

## 1. Layer primacy — cross-layer checking is the core method

What makes FinePrint powerful is checking ALL layers AND checking them
AGAINST EACH OTHER:

- **Stated intent** — what the developer declared (invariant / policy)
- **Native policy decision** — what the harness's own decision surface says
- **Observed effect** — what actually happens when it runs

The power is in the comparison: intent vs. decision vs. effect, each pair
checked against the other. This cross-layer checking is the core method
of the framework — not an add-on, not a report section. Everything the
framework measures should serve it.

**Naming (CANDIDATES PENDING the founder's tap — do not adopt unilaterally):**

- Cross-Examination
- Triangulation
- Layercheck

A naming-decision placeholder in living docs may list these candidates.
None of them is the adopted term until the founder taps one.

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
