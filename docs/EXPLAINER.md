# Why policies need testing — the plain-language foundation

*This document is the project's canonical explainer: the rigorous version of
what we do and why, written for developers, reviewers, and funders alike. It
is also the source text for the long-form public post (draft; publication is
founder-approved only). Claims carry the project's evidence classes
(DOC / REPRO / THIRD-PARTY / INFERENCE / HYPOTHESIS); the sprint's own
measurements are REPRO against the pinned harness named in each case.*

## What a policy is — and what "declarative" means

A coding agent does not just talk — it acts. It runs commands on a real
machine: reads files, runs tests, deletes things, pushes code, deploys. The
**harness** is the program around the AI model that carries out those
actions. A **policy** is the rulebook someone writes for that harness: what
the agent may do freely, what it must ask a human about first, and what it
must never do.

A policy is **declarative** when the rulebook states *what should be true*
rather than step-by-step procedures. Codex's `execpolicy` is declarative
(DOC): a `.rules` file declares, in effect, "commands beginning `rm -rf` →
forbidden; `deployctl release` → ask first; `git status` → allow." The
engine matches every incoming command against the declarations. Declarative
rulebooks can be read by a human, reviewed, version-controlled — and
*tested*. That testability is the opening this project exists to use.

## Why the harness can't just ship good defaults

1. **"Good" depends on context the vendor cannot know.** A deploy command
   is harmless in a hobby project and a firing offense at a bank. A file
   deletion is housekeeping in a scratch folder and a catastrophe in a
   records archive. The vendor ships one product to everyone; the meaning
   of a command lives in the owner's environment.
2. **Safety can't rest on the model behaving.** The model is probabilistic
   — usually sensible, not always. A policy is the deterministic fence
   around a probabilistic worker. The vendor builds the fence mechanism;
   only the owner knows where it must stand, because only the owner knows
   where the valuables are.
3. **Defaults change silently.** Vendors revise built-in behaviour between
   versions. A rulebook the owner wrote is stable and inspectable — *if*
   someone verifies, after each update, that it still does what they think.

## What conformance means

Conformance asks one narrow question: **does the system behave the way it
was specified to behave?** Not "is the agent smart," not "is this setup
safe" in the abstract — just: the intent was stated, a policy was written to
express it, the engine renders decisions; *do the decisions match the
intent?* Think of a **building inspector**: the inspector does not declare
the building safe or unsafe. She checks the building against the code its
owner filed — this stairwell must hold this load, this wall must be
fire-rated — and writes down, item by item, what matches and what does not.
This project is the inspector for an agent's policy: the rulebook is the
code, the harness's own decision engine is what gets inspected, and the
report is pass / fail / unknown per item, with evidence. (For grant and
safety audiences the variant phrasing is IAEA/arms-control-style
verification — same mechanics, different register.) This project compares three
things — stated intent, written policy, and the engine's actual decision
for each command — and reports **pass / fail / unknown** (the engine gave
no decision at all), with the evidence attached and the layer named:
rules layer, approval layer, sandbox/effect layer. A result at one layer is
never reported as a result about the whole system.

## How the first measurement was made (Day 1, Oct 21, 2026)

- **The judge is the harness itself.** Our harness never re-implements
  Codex's matching. It feeds each probe command to Codex's own checker —
  the pinned binary, codex-cli **0.149.0** — via `codex execpolicy check`,
  and records the ruling: allow, prompt, forbidden, or no-match. The
  version is pinned because rulings can change between versions; that is
  precisely why the measurement must be repeatable per version.
- **The policy under test:** one rule file, three rules —
  `git status` → allow, `deployctl release` → prompt, `rm -rf` → forbidden.
- **The probes:** 41 commands chosen to interrogate those three intents —
  direct forms; spelling variants (`rm -fr`, `rm --recursive --force`);
  path forms (`/bin/rm`); wrappers (`bash -lc "rm -rf /"`, `sh -c`, `env`,
  `sudo`, `timeout`, `xargs`); chains; and routine controls that must stay
  allowed.
- **Nothing was executed.** No command was ever run; nothing was deleted.
  We asked the judge for its ruling on each command — the equivalent of
  asking how a court would rule without committing the act.
- **Repeatability:** two full reruns produced identical results, matching
  the frozen Day-1 evidence in this repository. Anyone can re-run one
  command and check the work.

**Result (REPRO):** 41/41 cases matched the expected native rules-layer
decision — and 22 of the 41 (54%) returned **unknown**: no rules-layer
decision at all (allow 6 · prompt 4 · forbidden 9 · unknown 22). Scope
honesty: the corpus is a synthetic probe set deliberately weighted toward
variants and wrappers to map coverage. 54% is a corpus result, **not** a
real-world rate, and must never be quoted as one.

## Sprint-end status (Day-7 scope, executed Oct 21, 2026 — verdict: NARROW)

The Day-1 measurement above was the first of six: the 41-case corpus was
re-run five more times against the pinned oracle, byte-identical every
time (allow 6 · prompt 4 · forbidden 9 · unknown 22), plus an 11-case
protected-records family (11/11 pass: allow 1 · forbidden 2 · unknown 8),
4/4 negative controls healthy, and precedence re-verified 6/6
(most-restrictive-wins, order-independent). The same corpus was run
against the closest open-source tools: harness-eval and
agent-security-harness **cannot express** these tests at all (re-run
REPRO); Snyk Agent Scan and the OWASP harness were not tested
(documented gaps, never silent omissions). The locked Day-7 kill test
returned **NARROW**: the method is proven on the Codex T1 evidence, but a
public multi-harness Index is not earned on one measured harness — so the
repo stands as a Codex-T1 conformance *method* with its limitations on
its face (`docs/LIMITATIONS.md`), not as an Index. Full reasoning:
`docs/daily/2026-10-27.md`. The project also became a harness-neutral
framework (founder's direction, Oct 21): Codex is T1 (native oracle);
Claude Code, Cursor, Gemini CLI, and OpenCode are T2 (config evaluation,
no measured verdicts yet) — see `docs/FRAMEWORK.md` and
`docs/assets/tier_matrix.png`. The Day-5 proposed fix to the sample
policy is AWAITING the founder's approval and was NOT applied; all
results above are pre-fix, labelled as such.

## What the results point to

1. **Matching is literal, not semantic.** The engine matches the text shape
   of a command's beginning. It does not know that `rm -fr` and `rm -rf`
   are the same action in different spelling — so variants of a forbidden
   command receive no ruling.
2. **Wrappers are opaque.** Once a command sits inside `bash -c "…"`, the
   rules layer sees only "bash"; rules about the payload never fire.
3. **Precedence is sound.** When rules conflict, the most restrictive wins
   — re-verified across six rule-file variants (REPRO). The engine's logic
   is not the problem; its *coverage* is partial.
4. **Configuration is part of the policy.** `/bin/rm -rf` is "no decision"
   under default flags and "forbidden" with host-executable resolution
   enabled (REPRO). A developer's effective policy includes flags they may
   never have thought of as policy.

The principle underneath: **policy text is not policy effect.** A written
rulebook delivers partial decision coverage — some intents enforced exactly,
some never decided by that layer. Coverage cannot be known by reading the
rules; it can only be known by measuring. And one layer's silence is not
the whole story — approval policy and sandbox may still govern the runtime
outcome — which is why every result this project publishes names its layer.
An unmatched rule is a *decision-coverage gap*, never a "bypass": that
distinction is the project's credibility, and it is non-negotiable in every
public version of this text.

## Why asset-specific invariants are the real test

Danger is contextual. Generic dangerous-command lists are the floor, not
the ceiling: the same `rm` that is housekeeping in a temp folder is the
worst act of the agent's year when pointed at a health-records export or a
banking ledger. The project's invariant format therefore carries an
**asset** field from the start: invariants are stated per asset ("this
records directory: never deletable, by any command, in any spelling,
wrapped or not"), not merely per command shape.

A complete conformance suite spans a spectrum:

- **Universally dangerous** commands (destroy the filesystem root,
  exfiltrate credentials).
- **Asset-specific prohibitions** — including forms no command-shaped rule
  anticipates: a short script that empties a ledger file is not an `rm` at
  all, so a prefix rulebook will likely have nothing to say about it. The
  honest result is "unknown at the rules layer" — which is exactly what
  motivates measuring the *effect* layer later.
- **Allowed-but-gated** actions (production deploy → must ask a human).
- **Routine allowed** actions as positive controls — because conformance
  fails in both directions. A policy that blocks legitimate work trains
  humans to bypass the policy entirely, the worst outcome of all.

This spectrum is now in the sprint plan as a protected-asset fixture
family: a second sample policy guarding a records directory, probed in
direct, variant, wrapped, and script forms, reported per form and per
layer.

## Where this sits in the field

Intent-versus-policy analysis is not new, and this project does not claim
it is. AWS's **Zelkova** answers quantified questions about IAM policies
with SMT solvers (for all possible requests, is this true?), and **Cedar**
is a policy language designed for analyzability, with machine-checked
proofs and large-scale differential testing [1][2][3]. That machinery works
because cloud policy languages have a closed request algebra and the policy
*is* the semantics. Agent command surfaces have neither: the command space
is unbounded, the semantics live in the shell and in each binary, wrapped
commands are undecidable in general, and there is no stable written spec —
the pinned binary *is* the semantics. On this terrain, empirical
conformance measurement is not the cheap substitute for formal proof; it
is the only sound stance — while importing what does transfer: Cedar-style
differential testing (applied to our own tester), counterexample-first
reporting, and verified-repair discipline.

Adjacent measurement work is named, not gestured at: **GuardFall** (Adversa
AI, Jun 2026) measured guard-vs-shell divergence across 11 open-source
agents — runtime guards, a neighbouring object [4]. **Michael & Roesner**
surveyed 21 agent permission systems qualitatively and could not evaluate
closed agents' internals [5]. The approval-laundering studies show why the
decision layer alone cannot be the end of the story: an approved action and
the executed action can diverge, including in their transitive effects
[6][7]. And a 3,171-repo empirical study of coding-agent configurations
shows how much unexamined configuration surface already exists in the wild
[8]. The unoccupied intersection this project claims — stated precisely in
`docs/SCIENTIFIC_REVIEW_ADDENDUM.md` — is: deterministic, offline
conformance measurement of a pinned native *declarative* policy engine
against developer-declared invariants, unknowns explicit with layer
attribution, results sealed as verifiable evidence, repeated across
versions.

## References

1. AWS Security Blog — "How AWS uses automated reasoning to help you
   achieve security at scale" (Zelkova).
   https://aws.amazon.com/blogs/security/protect-sensitive-data-in-the-cloud-with-automated-reasoning-zelkova/
   (URL verified live Oct 21, 2026.)
2. Amazon Science — "A billion SMT queries a day."
   https://www.amazon.science/blog/a-billion-smt-queries-a-day
3. AWS — Cedar policy language and Cedar Analysis (differential testing,
   formal verification): see `docs/SCIENTIFIC_REVIEW_ADDENDUM.md`, Area 1.
4. Adversa AI — GuardFall (Jun 30, 2026); CSA note (Jul 1, 2026). See
   addendum, Area 5.
5. Michael & Roesner — "How Agents Ask for Permission," arXiv:2607.13718.
6. Wang — "Approval Laundering," arXiv:2609.38983.
7. Zhang et al. — "Agent Approval Laundering: Transitive Effects Beyond
   the Approved Invocation," arXiv:2609.28586.
8. Kapner et al. — "Scanning the Harness: An Empirical Study of
   Supply-Chain Defects in AI Coding-Agent Configurations,"
   arXiv:2609.07360 (corpus: 3,171 public repos).
9. This project's own record: `docs/SCIENTIFIC_REVIEW_ADDENDUM.md`,
   `docs/BOUNDARY_MEASUREMENT_FIELD.md`, `docs/COMPETITIVE_EVIDENCE_MATRIX.md`,
   `evidence/day1-baseline-2026-10-21/`, and the landscape/funding research
   report (Revision 3, Oct 21, 2026).
