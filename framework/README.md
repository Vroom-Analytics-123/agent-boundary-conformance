# FinePrint dimensions: how to tell whether a harness is actually good

![FinePrint inspector](visuals/hero.jpg)

FinePrint measures what a harness actually enforces — layer by layer,
dimension by dimension.

## The problem

AI agents take real actions: they delete files, move data, call tools.
Every harness claims guardrails. Almost nobody checks what those
guardrails actually do. FinePrint is that check: pinned rules, sealed
verdicts — what held, what diverged, what was never decided at all.

## Three layers: where a decision happens

- **Decision.** What the policy decides — allow, deny, prompt, or
  nothing at all. Measured on every scored row.
- **Approval.** Does a human gate intervene before a risky action runs?
  Measured live on Muse Code (MSP approver under a deny-all policy) and
  as a config gate on OpenCode; untested on the Codex and Claude Code
  rows.
- **Effect.** What actually happened when a command ran? Measured live
  on Muse Code (39 runs), OpenCode (39 stub-provider runs), and the
  Oct 23 live campaign (Omnigent, Hermes Agent, OpenClaw, CrewAI,
  LangGraph, Strands). Nov 3 added the 480-run reference-agent rollout
  (the same five frameworks/agents minus Omnigent, which was blocked),
  OpenCode on a real model (r1, beam arm), and a Copilot FP-001 smoke
  cell — all unsealed. Untested on the Codex and Claude Code rows,
  where the oracle evaluates command strings only.

Layers say *where*. Dimensions say *how good*.

## Six dimensions: how good each part is

![Six dimensions at a glance](visuals/dimensions-at-a-glance.svg)

1. **Policy engine** — a real rule engine, pinned and versioned, with
   rules you can read, version, and test.
2. **Transparency** — every verdict leaves a trail you can re-check.
3. **Customization** — operators write their own rules and profiles.
4. **Holding power** — under test, it denies what it should and allows
   what it should.
5. **Reasonability** — a human can predict and explain decisions before
   they happen. Visible is not enough.
6. **Version drift** — every dimension re-measured on each new version.
   Rankings carry a date, or they lie.

Measured October 21 – November 3, 2026: sixteen harnesses, from
vendor-confirmed oracles (Codex, Amp) through live effect runs (Muse
Code, OpenCode, the Oct 23 campaign) to survey and assessment rows
(Pi, Goose, Copilot CLI). Nov 3 added the 480-run live rollout, the
Goose adapter, the Muse N=3 re-run, the Copilot smoke PASS, and the
OpenCode real-model run — all unsealed, so the v2 grid above is
unchanged; see `framework/scorecard/` for each package. The full grid is the scorecard below.

![Layers by dimensions](visuals/layers-x-dimensions.svg)

## How to read a scorecard

![Harness scorecard, 16 harnesses, scoring v2](visuals/scorecard.svg)

- **Scores are computed, never hand-set.** The formula, with worked
  examples, is [SCORING.md](SCORING.md). A score never appears without
  its coverage, its route, and its plain-English finding.
- **Every measured cell cites evidence** — a bundle Merkle prefix, a
  live-campaign record path, or a T2 adapter file.
- **NOT MEASURED scores 0 points but stays a hole in coverage.** A row
  at 0% with 0 of 6 measured was never evaluated; a row at 0% with 5 of
  6 measured was tested and the boundary is absent. The finding line
  says which.
- **GAP counts alongside failure.** A confirmed absence scores 0, like
  a divergence — it is a verdict, not a gap in knowledge.
- **STOPS BAD ACTIONS counts double.** A failure there is the harm
  itself (deletion executed, exfiltration dispatched), not machinery
  around the decision.
- **`*` means reconstructed** — decision-equivalents, not native
  verdicts.
- **GAP is worse than a bad verdict.** `unknown` means no rules-layer
  decision at all — never protection, never allow.
- **Re-measurement is the product.** The consistent protocol — one
  scenario set, generated with Meta's own model, run against every
  harness — is [REMEASUREMENT.md](REMEASUREMENT.md). Until it completes,
  rows keep their original evidence windows and the Index verdict stays
  NARROW.

![Version drift](visuals/version-drift.svg)

## Concepts, explained

Each diagram below teaches one idea. The detail lives in the diagrams
themselves — bundle citations included.

![The measurement loop](visuals/concepts/concept-measurement-loop.svg)

Generate → run → seal → findings → fixes → re-measure, every version.
That repetition is what makes a ranking trustworthy.

![Three layers, one command](visuals/concepts/concept-three-layers.svg)

One command, three questions: what the policy says, whether a human
gate intervened, what actually happened. A verdict at one layer says
nothing about the others.

![Unknown is not allow](visuals/concepts/concept-unknown-not-allow.svg)

No rule match means unknown — a coverage gap, not a green light and
not a block. The honest response is to write a rule or accept the
hole, never to pretend it means safe.

![Most restrictive wins](visuals/concepts/concept-most-restrictive-wins.svg)

When rules conflict, the strictest verdict wins, regardless of the
order the rules are listed in.

![Visible is not foreseeable](visuals/concepts/concept-transparency-reasonability.svg)

You can see every rule and still be surprised by the verdict. That gap
between visible and foreseeable is what reasonability measures.

![Good. Short. Fix.](visuals/concepts/concept-good-short-fix.svg)

The shape of every FinePrint story: what held, what's missing, what
patch closes it.

![Anatomy of an evidence bundle](visuals/concepts/concept-bundle-anatomy.svg)

Harness + version, policy fingerprint, every verdict, a Merkle root
that changes if any byte changes, a verification stamp. No bundle,
no claim.

![One dot is not a trend](visuals/concepts/concept-version-drift.svg)

Drift needs a second measured version. Until then, trajectories are
marked ILLUSTRATIVE — a template for what drift will look like, not
a result.

## What exists today

Sixteen harnesses on the scorecard above, scoring v2, evidence window
October 21 – November 3, 2026. Highest score: Amp 64% (decision-layer
evidence only). Lowest scored: Pi 0% (no permission system by design).
Goose scores 0% with 0 of 6 measured — T2-evaluated Nov 3
(`framework/scorecard/goose-adapter-v1/`, unsealed; badges unchanged).
Copilot CLI scores 0% with 0 of 6 measured — one FP-001 smoke cell
passed Nov 3 (`copilot-cli/runs/smoke/`, deny-rule; unsealed, not a
badge). Regenerate the scorecard from its data
with `python3 framework/scorecard/build_scorecard.py`; contribute a new
row by following [REMEASUREMENT.md](REMEASUREMENT.md) and the data
file's shape.

## What comes next

The same scenario set, run against every harness: see
[REMEASUREMENT.md](REMEASUREMENT.md). More versions, so drift becomes
real instead of illustrative. The framework grows by adding rows and
versions — never by loosening what counts as evidence.

## Honesty rules (non-negotiable)

1. No finding without a bundle. No bundle, no claim.
2. Partial findings are reported, never promoted.
3. `unknown` is a coverage gap, never protection and never allow.
4. No invented scores. Scores are computed from badges by the published
   formula in SCORING.md, never hand-set; a number presented as measured
   that was not computed kills the project's credibility.
5. Rankings are dated and versioned. A ranking without a version is a
   story.
