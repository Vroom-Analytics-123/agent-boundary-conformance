# The upstream fix loop — measure, fix locally, patch upstream

FinePrint does not stop at measuring a gap. The loop is:

1. **Measure.** Run the check. The bundle is the evidence: which
   rule broke, which probe, what the policy decided, what the rule
   expected. No gap is real until a sealed bundle says so.
2. **Fix the harness code locally.** Reproduce the gap in the
   harness's own code, fix it there, and re-measure with the same
   scenarios. A fix that does not change the measured verdict is not
   a fix — re-run the check and diff against the baseline bundle
   (`fineprint check --baseline <previous bundle.json>`; a
   regression fails the build).
3. **If the harness is open source, submit a patch upstream.**
   Small, modeled on the neighboring code, with the measurement
   attached. **Do not file an upstream PR in this task, and do not
   file one on your own later without the owner's per-PR approval.**
   The patch is the owner's decision each time.

The loop is the product's credibility: a measurement nobody acts on
is a report card; a measurement with a fix is a repair.

## Worked example: Omnigent

**The gap (measured).** Omnigent 0.19.1, 96-cell parity run, sealed
as `omnigent-live` (Nov 4, 2026): deletions held 24/24 by the
`deny_rm` rule, but credential reads executed 13 of 16 — denied 0
of 16 — and deploy, environment, and records reads executed 4 of 4
each. The rule set covered one dangerous verb and left the rest
open. That is the finding the patch fixes.

**The fix (local).** A builtin credential-flow guard plus an egress
host allowlist, added to Omnigent's own rule engine: credential
reads (`.env`, SSH keys, AWS credentials, the protected records
file) denied by default, with an explicit allowlist for hosts the
agent may fetch from. The fix was verified over the same 96-cell
matrix before it was submitted — the local measurement changed, then
the patch went out.

**The patch (upstream).** [`omnigent-ai/omnigent#12762`](https://github.com/omnigent-ai/omnigent/pull/12762),
"Add builtin credential-flow guard and egress host allowlist".
Opened by the owner (his personal step, Nov 3, 2026). One
signed-off commit, 3 files, +610/−0, `Closes #12516`. Status:
**open, not merged** — CI finished 84 success, 10 skipped, 1
failure, and the single failure is the repo's "Maintainer Approval"
gate for fork PRs, not a code failure. Waiting on a maintainer
review; the repo closes stale PRs after 60 days of no activity, and
waiting-on-author items after 7 days (reversible with `/reopen`).

**The claim language.** Say the PR was **created / opened**. Never
say merged, accepted, or landed unless the maintainer actually
merges it. An open PR is a proposal with evidence attached, not a
result.

## The other outcome: Pi

[`earendil-works/pi#11608`](https://github.com/earendil-works/pi/pull/11608)
was **closed, not merged** — auto-closed by the repo's contributor
gate, not rejected on merit. The fix was verified over a 48-case
matrix; the branch is preserved on the fork
(`vroomanalytics123:fineprint-permission-gate`). The lesson: a
closed PR is not always a "no". Read the close reason before
concluding anything, and do not reopen without a maintainer signal.

Openshell cannot take a PR at all — the repo is archived. The fix
is preserved on the fork (`vroomanalytics123/openshell-deepagent`,
branch `fineprint-command-guard`, commit `bee66685…`).

## Rules for the loop

- Measure first, always. A fix without a before-bundle is an
  opinion; a fix with a before/after bundle pair is evidence.
- Keep the patch minimal and modeled on the harness's own code.
  Do not redesign their policy engine in a first PR.
- Attach the measurement: link the sealed bundle (or the repo path
  to it) and state the before/after tallies in the PR body.
- Never claim a merge that did not happen. Never volunteer the
  unmerged status unprompted, but never hide it when asked.
- No upstream PR is filed from this repo's free tier without the
  owner's explicit per-PR approval. The free tier measures and
  documents; the owner decides what goes upstream.
