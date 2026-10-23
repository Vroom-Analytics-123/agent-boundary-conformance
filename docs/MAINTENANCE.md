# Maintenance checklist — landing discipline for every work item

*Standing rule (founder direction, 2026-10-22): the dashboard and the GitHub
repository are kept up to date, and outdated information is removed in
follow-up commits — never by rewriting history.*

Every work item that lands in this repo MUST complete all four steps below
before it is committed. They are cheap; skipping them is how living docs rot.

## 1. Refresh the dashboard's state claims (`docs/DASHBOARD.md`)

- Bump the "Last updated" line to the landing date/time.
- Update every state claim your change touched: verdict language, route
  assignments, evidence locations (bundle paths + Merkle roots), scorecard
  version, grants/publish-queue status, the "Waiting on Anish" list.
- A claim that was true yesterday and is false today is a stale claim, not a
  typo: fix it in the open (see step 2), never silently.

## 2. Sweep the living docs for claims your change just made stale

- **Living docs** (must stay true): `README.md`, `docs/EXPLAINER.md`,
  `docs/FRAMEWORK.md`, `docs/DASHBOARD.md`, `docs/MEASUREMENT_ROUTES.md`,
  `docs/catalogue/CATALOGUE.md`, `docs/LIMITATIONS.md`, `docs/SIGNING.md`,
  `docs/COMPETITOR_BASELINES.md`, `docs/COMPETITIVE_EVIDENCE_MATRIX.md`,
  `docs/METHODOLOGY_AND_GOVERNANCE.md`, `docs/VERIFIABLE_EVIDENCE_ARCHITECTURE.md`,
  `docs/BOUNDARY_MEASUREMENT_FIELD.md`, `docs/IMPLEMENTATION_DESIGN.md`,
  `docs/WEEK1_BUILD_SPEC.md`, `docs/PIN_CHECKLIST.md`,
  `docs/CATCH_UP_READING.md`, `docs/SCIENTIFIC_REVIEW_ADDENDUM.md`, and the
  program repo's `README.md` + `grants/` drafts.
- **Historical docs** (records — never edit): dated daily briefs
  (`docs/daily/`), dated result docs (`docs/baselines/`,
  `docs/preregistration/`, `docs/effect-pilot/`, `docs/harness-testing-*.md`,
  `docs/amp-spike-*.md`, `docs/corpus-realism-*.md`), sealed bundles and
  evidence (`evidence/`, except appending new sealed runs), `docs/drafts/`.
- Known stale families to hunt on every landing: retired names (EffectGap,
  Bouncer); "one harness / one oracle" claims (superseded the day Amp was
  promoted); "pre-fix" presented as current (post-fix bundle sealed
  2026-10-22); "unsigned" presented as current (detached Ed25519 post-seal
  attestations exist — see `docs/SIGNING.md`); tier/grade ranking language anywhere (superseded
  2026-10-22 by the founder's model correction — grades/tiers abolished,
  routes are provenance of the Layer-1 measurement only); route claims
  superseded by a measured wave or a route recognition; sprint day-labels presented as current state
  (execution is continuous, not day-gated); baseline/Snyk cells misstated;
  funding-register rows superseded by later drafts.
- For each stale claim: fix the text or delete the passage in a follow-up
  commit. Quote the old and new text in the commit message when the claim
  mattered.

## 3. Verify push tree-match

- Commit with author `avan`, in clearly separated commits (one concern per
  commit: naming / stale-fixes / cleanup / the work itself).
- Push via `tools/`' mirror flow (`git_mirror_push.py` against
  `Vroom-Analytics-123/agent-boundary-conformance`); the API-scoped
  credential cannot do git-over-HTTPS.
- After pushing, verify the remote tree matches the local tree (the mirror
  script asserts tree SHAs). On mismatch: leave the local tree as-is and
  report — never force-push, never rewrite history to "fix" the remote.

## 4. Record the dated addendum — never silently rewrite history

- Dated revision paragraphs ("**Revision — … (2026-10-22):**") are the
  mechanism: append a new dated paragraph that states what changed and what
  it supersedes. Do not edit the superseded paragraph's claims — its
  datedness is the record.
- Living sections (dashboard status, README status line, route tables' current
  rows) get updated in place AND get a dated addendum entry when the change
  is material (route recognition, verdict, sealed evidence).
- Generated files (`docs/catalogue/CATALOGUE.md`, `docs/catalogue/catalogue.json`)
  are regenerated from their generator (`tools/build_catalogue.py`) — never
  hand-edited, or the next regeneration silently reverts the fix.

## Naming discipline (founder model correction, 2026-10-22 ~18:29 PDT — controlling)

User-facing text uses the plain names: the **PAPER TEST** (offline decision,
measures the Decision layer = Layer 1) and the **LIVE TEST** (online effect,
measures the Effect layer = Layer 3, ground truth). Grades and T1/T2/T3 are
**abolished** as rankings — they survive nowhere in living docs, schemas, or
manifests except inside dated historical records (untouched). The unranked,
descriptive **measurement routes** — provenance of the Layer-1 measurement
only — are: **vendor-confirmed** (the vendor's own checker answers),
**reconstructed** (evaluated from the vendor's documented semantics),
**no paper surface** (no rule surface exists to evaluate). Machine field:
`measurement_route` on every adapter manifest. When a work item changes a
route assignment, the naming pass in step 2 covers every living doc — the
correction note at the top of `docs/MEASUREMENT_ROUTES.md` maps the old
labels to the corrected model. The three layers (Decision · Approval ·
Effect, adopted by the founder's tap 2026-10-22) are defined up front in
`docs/FRAMEWORK.md`, `docs/EXPLAINER.md`, and
`docs/BOUNDARY_MEASUREMENT_FIELD.md` — never only at the end.
