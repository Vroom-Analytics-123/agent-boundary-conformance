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
  nothing at all. Measured.
- **Approval.** Does a human gate intervene before a risky action runs?
  Untested so far — no approval prompt has been observed by any route.
- **Effect.** What actually happened when a command ran? Untested so
  far — no scenario command was executed.

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

Measured November 1, 2026: Codex 0.149.0 through a vendor-confirmed
oracle, Claude Code 2.1.307 reconstructed from documented semantics.

![Layers by dimensions](visuals/layers-x-dimensions.svg)

## How to read a scorecard

![Sample scorecard](visuals/scorecard.svg)

- **Badges, not scores.** HOLDS, PARTIAL, DIVERGES, GAP. One number
  would average away exactly the trade-offs that matter.
- **Every measured cell cites evidence** — a bundle Merkle prefix.
- **NOT MEASURED is a hole, not a zero.** Grey cells are gaps in our
  knowledge, shown as holes.
- **ILLUSTRATIVE is invented for display.** Never quote it as a result.
- **`*` means reconstructed** — decision-equivalents, not native
  verdicts.
- **GAP is worse than a bad verdict.** `unknown` means no rules-layer
  decision at all — never protection, never allow.

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

Measured November 1, 2026, on 24 scenarios across 11 invariants:

- **Codex CLI 0.149.0** (vendor-confirmed oracle): 9 MEASURED /
  15 PARTIAL scenarios.
- **Claude Code 2.1.307** (reconstructed semantics): 12 MEASURED /
  12 PARTIAL scenarios.
- **Approval and Effect:** UNTESTABLE on every row, both targets.

## What comes next

More harnesses, measured the same way. More versions, so drift becomes
real instead of illustrative. Approval and Effect measurement, once an
approver can answer prompts without a human in the loop. The framework
grows by adding rows and versions — never by loosening what counts as
evidence.

## Honesty rules (non-negotiable)

1. No finding without a bundle. No bundle, no claim.
2. Partial findings are reported, never promoted.
3. `unknown` is a coverage gap, never protection and never allow.
4. No invented scores. An invented number presented as measured kills
   the project's credibility.
5. Rankings are dated and versioned. A ranking without a version is a
   story.
