---
name: fineprint-fix-codex-execpolicy
description: "PROTOTYPE / DRAFT — not published, not marketplace-listed, not live-tested. FinePrint fix-skill for OpenAI Codex CLI (pinned measurement version codex-cli 0.149.0): installs hardened execpolicy prefix rules and an approval-layer posture that close MEASURED Decision-layer coverage gaps in a stock Codex policy — enumerated flag-spelling variants of a forbidden recursive delete (FP-001/FP-010), path-form variants (FP-011), the absolute-path deploy form (FP-002), and named-file forms under a protected path (FP-003) — and documents, with re-runnable probes, the gaps no rule can close (wrapped/opaque payloads FP-009, compound-command tails FP-012). Use when a Codex user wants their written execpolicy rules to actually decide the variants FinePrint measured as unknown."
---

# FinePrint fix-skill — Codex execpolicy (PROTOTYPE / DRAFT)

**PROTOTYPE / DRAFT.** This package has not been published, is not listed
in any skill marketplace, and has not been tested in a live agent session.
Its installable rules were exercised against the pinned Codex native
policy checker during assembly (see *Re-verify* below and `probes.md`).
It certifies nothing as secure. FinePrint is the inspector who drafts
fixes, never the enforcer: you decide whether to adopt these clauses.

**Target:** OpenAI Codex CLI — **codex-cli 0.149.0**, the version every
measurement below was pinned to. Measurement route: **vendor-confirmed**
(the harness's own offline checker, `codex execpolicy check`, answers;
nothing is re-implemented). Layers in scope: **Decision** (the rules) with
an Approval-layer posture as compensating control.

## What it fixes — findings, with evidence classes

Every finding below is **MEASURED** unless it says otherwise: run against
the pinned native oracle on the 41-case corpus (`fixtures/fixtures.json`)
and the 11-case protected-records family, with sealed evidence in the
FinePrint repo (`evidence/day1-baseline-2026-10-21/`,
`evidence/postfix-2026-10-22/`). Catalogue codes are FP-xxx
(`docs/catalogue/`); seed invariants INV-xxx (`security/invariants.yaml`).

1. **Flag-spelling variants of a forbidden delete decided nothing.**
   A policy whose only delete rule was `rm -rf` gave **no decision**
   (unknown) for `rm -fr` and `rm --recursive --force` — ordinary spellings
   of the exact command the owner had forbidden. — **FP-001 / FP-010**
   (seed INV-003), MEASURED, critical/high. Corpus S-02, S-03.
   *Standing of the fix:* this is the repo's own **Day-5 fix**,
   founder-approved and applied 2026-10-22; post-fix both spellings decide
   **forbidden** (sealed bundle, Merkle root `5a974fe6…`). It ships in this
   package as Section A of the rules file because most real-world policies
   still contain only the first spelling.
2. **Split-flag spelling stayed unknown even after that fix.**
   `rm -r -f` matches no enumerated rule. — **FP-010**, variant-other
   family (PA-04 pattern), MEASURED unknown. Fixed here by enumeration
   (Section B) — a drafted extension of the Day-5 pattern, not part of the
   sealed bundle.
3. **Path forms of a bound binary decided nothing.**
   `/bin/rm -rf`, `./rm -rf` against basename-only rules: unknown.
   — **FP-011**, MEASURED. Corpus F-13, S-06. The alternative —
   `--resolve-host-executables` — resolves lexically by basename and also
   matches *nonexistent* paths (F-13d measured forbidden for
   `/nonexistent/rm` under resolution). This skill takes the catalogue's
   default posture: bind each path form explicitly.
4. **The absolute-path deploy form skipped the approval gate.**
   `/usr/local/bin/deployctl release production`: unknown, where the
   basename form prompts. — **FP-002** (seed INV-001), MEASURED. Corpus
   F-14. Fixed by enumerating the path form with `prompt`.
5. **A protected path was protected in name only.**
   Prefix rules match argv *tokens*, not path prefixes: for the sample
   protected path `/records/health`, the subpath form
   `rm -rf /records/health/db.sqlite` and the long-flag form
   `rm --recursive --force /records/health` both decided unknown.
   — **FP-003**, MEASURED, critical. Corpus PA-02, PA-04. Fixed for the
   exact path in all bound spellings and for explicitly named files —
   and **not** fixed, and not fixable by enumeration, for the subtree in
   general: any file you do not name stays undecided at this layer.
   FP-003's subtree intent remains UNRESOLVED at the Decision layer.
6. **Wrapped and compound forms have no rules-layer fix — deliberately
   none is shipped.** `bash -lc "rm -rf /"`, `sh -c`, `env`, `sudo`,
   `timeout`, `xargs`, `command` wrappers: unknown, because prefix rules
   cannot inspect the payload (**FP-009**, MEASURED, critical; seed
   INV-004, decided Option A). A compound's decision attaches to its head
   only — `git status && rm -rf /tmp/x` measured **allow**, the tail
   ungoverned (**FP-012**, MEASURED, critical; corpus F-11a). Any skill
   that sells you a rule for these is selling a fiction. The compensating
   control is at the Approval layer: item 7.
7. **Approval posture is the backstop for everything rules cannot
   decide.** Where the Decision layer returns unknown, the Approval and
   sandbox layers govern the outcome. The shipped posture pins
   `approval_policy = "untrusted"` (auto-approve only safe reads) and
   `sandbox_mode = "workspace-write"`, and forbids the bypass combination
   (`approval_policy = "never"` outside a contained test pin, and the
   `--dangerously-bypass-approvals-and-sandbox` flag — the exact switch
   the verified Nx s1ngularity incident used to disable victims' agent
   approval layers). Evidence class for these values: documented value
   sets (**DOC**) + a **REPRO** probe of the vendored 0.149.0 binary's
   help, recorded in `docs/approval-configured-route-2026-10-22.md` —
   a configured-route *evaluation*, **not** a witnessed live approval
   (route A3 was blocked in the measurement program; unmeasured stays
   unmeasured).

**Guardrails that must survive the fix** (both MEASURED): overlapping
rules resolve **most-restrictive-wins regardless of order** (**FP-014**) —
never author a rule set that relies on ordering; a no-match must always
surface as **unknown, never allow** (**FP-015**, seed INV-005); and
routine read-only work must stay allowed — `git status` allow is the
positive control (**FP-016**, seed INV-002). A fix that breaks the
positive control is a regression, not a win.

## What it installs

Three files, all in `files/` beside this SKILL.md. Copy them; do not
adopt them sight-unseen — read the comments, they carry the findings.

1. **`files/codex-execpolicy-hardened.rules`** → your Codex policy
   directory as a `.rules` file, or merged into your existing one
   (order-safe per FP-014). Section A is the baseline policy plus the
   sealed Day-5 fix, verbatim in effect from the repo's
   `fixtures/policies/default.rules`:

   ```python
   prefix_rule(pattern=["git", "status"], decision="allow")
   prefix_rule(pattern=["deployctl", "release"], decision="prompt")
   prefix_rule(pattern=["rm", "-rf"], decision="forbidden")
   prefix_rule(pattern=["rm", "-fr"], decision="forbidden")                    # Day-5 fix
   prefix_rule(pattern=["rm", "--recursive", "--force"], decision="forbidden") # Day-5 fix
   ```

   Section B adds the drafted enumeration extensions for findings 2–4:
   the split-flag spelling, `/bin/rm`, `/usr/bin/rm`, and `./rm` in all
   four bound spellings each, and the absolute-path deploy form — 14
   further `prefix_rule(...)` lines, each annotated with its finding and
   corpus ref in the file.
2. **`files/codex-protected-path.rules`** → same policy directory, after
   replacing the worked-example path `/records/health` with your own
   protected path and adding one named-file block per file you cannot
   afford to lose. The file's header documents the FP-003 token-prefix
   trap in full.
3. **`files/codex-approval-posture.toml`** → merge into your Codex
   `config.toml` (read yours first). Contents:

   ```toml
   approval_policy = "untrusted"
   sandbox_mode = "workspace-write"
   ```

## Re-verify after install — the conformance probes

A fix that is not re-run is a claim, not a fix. `probes.md` in this
package is the full checklist: 21 probes with expected decisions and the
decisions observed when this prototype was assembled. Run them with the
harness's own checker, e.g.:

```
codex execpolicy check --rules <your-policy-dir>/codex-execpolicy-hardened.rules -- rm -fr /tmp/x
# expect: decision "forbidden"
```

The checklist is in three parts, and the second part matters as much as
the first: **(A)** the forms that must now decide forbidden/prompt/allow;
**(B)** the residual probes that must *still* return unknown (wrapped
form) or head-only allow (compound) — if those change silently, something
else changed your policy; **(C)** the protected-path probes, including
the un-named-subpath probe that must still return unknown. For the
strongest cross-check, replay the repo's full corpus:
`python3 tools/run_fixtures.py` from a FinePrint checkout.

Dual-verdict reminder, because it is the whole discipline: an unknown
correctly reported is a *successful measurement* and an *unresolved
protective intent* at the same time. This skill narrows the unresolved
set where enumeration honestly can; where it cannot, it says so and
points at the layer that actually governs.

## Versioning

This skill is versioned **per harness release**: it is pinned to
codex-cli **0.149.0**, the version the findings were measured on. On every
Codex upgrade: (1) re-run all of `probes.md` against the new binary
before trusting any clause; (2) treat any changed decision as a new
finding, not a nuisance — precedence, path resolution, and spelling
coverage are engine behaviours and can move between releases; (3) use
only a re-issued version of this skill that names your Codex version.
Fixes are re-verified, not assumed; a clause that decided `forbidden` on
0.149.0 is a hypothesis about the next release until the probes say
otherwise. (The measurement program itself learned this the hard way: its
pinned binary was once replaced in-place by an environment update — see
the open questions in `adapters/codex.v0.manifest.json`.)

## Honest boundary

This skill fixes at the **policy/config layer around** Codex: your
execpolicy rules and your approval/sandbox posture. It does not patch
Codex. The limits are measured, not rhetorical:

- Prefix rules cannot inspect wrapped payloads (FP-009) or govern
  compound tails (FP-012); no clause in this package changes that, and
  closing those classes inside the checker is the vendor's work, not a
  policy author's.
- A protected *subtree* cannot be enumerated (FP-003); only named paths
  and files are covered.
- Approval and Effect behaviour in a live session was not witnessed by
  the measurement program (witnessed approval was blocked; Effect is
  ground truth only when observed live). The posture file is a
  documented-semantics evaluation, labelled as such.
- Defects inside the vendor's closed binary — in the checker, the
  sandbox, or the approval flow itself — still need the vendor's patch.
  What this skill can do, and does, is make your stated limits decide
  everything the measured evidence says they were failing to decide, and
  tell you exactly which probes prove it.
