# Corpus realism mining — 2026-10-22

**Purpose:** answer the grant-reviewer's "is your corpus real?" question with
measured evidence, not assertions. We mined public sources for real-world
Codex `execpolicy` `.rules` files, extracted command patterns **with sources**,
and ran every candidate through the pinned oracle. Every decision below is
**REPRO** (measured on `codex-cli 0.149.0`, sha256
`bbc3341e…672827`, via `tools/pin.py`) — no expectation was hand-asserted.

**Boundary conditions (non-negotiable):** the sealed Day-2 41-case corpus and
the held-out split were NOT altered. Candidates live in
`docs/realism/` (rules + `corpus-v2-candidates.json`) — additive only, outside
`fixtures/`. Nothing here is adopted until the proposal at the end is
owner-approved.

## Mining result

| # | Source (fetched 2026-10-22) | Kind | Real-world confidence | Commands | Decisions |
|---|---|---|---|---|---|
| rr-01 | azukiazusa.dev — Codex sandbox/agent-authorization blog | blog | medium | 5 | allow 3, unknown 2 |
| rr-02 | iflow.bot — Codex-on-MacBook guide | blog | medium | 6 | prompt 4, unknown 2 |
| rr-03 | computingforgeeks.com — Codex CLI cheat sheet | blog | medium | 5 | forbidden 2, prompt 1, unknown 2 |
| rr-04 | dev.to/nlsmdn — single-source-of-truth permissions (real user's **generated, live** ruleset) | blog | **high** | 8 | allow 3, forbidden 3, prompt 1, unknown 1 |
| rr-05 | codex.danielvaughan.com — team.rules example | blog | medium | 8 | allow 5, forbidden 2, unknown 1 |
| rr-06 | thinkingraven.com — agent-capabilities-2026 research report | docs | medium | 5 | allow 2, unknown 3 |

**Totals: 6 candidates from 6 distinct sources, 37 commands, all parsed —
allow 13, prompt 6, forbidden 7, unknown 11.**
7 further sources were examined and honestly rejected (GitHub raw/blob fetch
failures, DeepWiki 429s, threads with no rule snippet, docs mirrors with no
rendered code) — see the raw mining log. No padding: 6 candidates is what the
fetchable web actually yielded; every one cites a URL that was fetched.

**Independent confirmation:** all 37 commands were re-run through the pinned
oracle a second time (2026-10-22, separate process) — **37/37 decisions
identical**, including matched-rules counts.

## Measured decisions (REPRO)

Per-candidate tables live in `docs/realism/corpus-v2-candidates.json`. Two
findings deserve highlighting — both are realism gold a synthetic corpus
would not invent:

1. **Strictest-wins is real (rr-05):** `npm run deploy` matches TWO rules
   (`["npm",["test","run","ci"]] → allow` and
   `["npm","run",["deploy","publish"]] → forbidden`) and the oracle returns
   **forbidden**. Decision-priority behavior confirmed on a real-world-shaped
   policy, not a lab construction.
2. **Real-world over-permissiveness (rr-05):** `npm run deploy:production`
   matches only the `["npm",["test","run","ci"]]` allow-prefix and returns
   **allow** — the exact class of prefix-rule over-allow a conformance tool
   should catch. (Not a verdict on the author's intent; the rule is
   illustrative. The *pattern* — deploy-suffixed scripts slipping an
   allow-prefix — is the realistic shape.)

Other notable shapes: rr-02's **alternation-list pattern syntax**
(`[["npm","pnpm","yarn","bun"],"install"] → prompt`) exercises a Starlark
pattern form absent from the synthetic corpus; rr-04 is a genuine deployed
ruleset (allow `git status/log/diff`, forbid `git push` / `reset --hard` /
`clean -fd`, prompt `heroku`); rr-03 shows the cheat-sheet author's
deliberate `rm -rf → prompt` (not forbidden) rationale — agents need to clean
build dirs — a real policy judgment, not a lab default.

## Corpus-v2 ADOPTION PROPOSAL (for owner decision)

**Thesis:** corpus-v2 is an *additive, separately-versioned* real-world
fixture family. It does not touch the sealed Day-2 corpus, the held-out
split, or any sealed bundle. Adopting it means: new corpus version hash, new
pre-registration, new sealed bundle — the same machinery, a new artifact.

**Admission criteria** (all must hold per candidate):
1. **Provenance:** a fetchable source URL, archived with the candidate.
   Confidence `high` (deployed ruleset) preferred; `medium` (documented
   recommendation) admissible with the label visible; nothing below `medium`.
2. **REPRO decisions:** measured on the pinned oracle through `tools/pin.py`
   (fail-closed). No hand-asserted expectations — the candidate file carries
   decisions only.
3. **Owner-set expectations:** before a candidate becomes a *fixture* (with
   an `expected` field), the owner reviews each command against the governing
   invariant and sets the expectation explicitly. The miner never sets it.
4. **Held-out hygiene:** candidates are screened against the held-out split
   (by hash, not by content — the split content stays sealed). Near-duplicates
   of held-out cases are rejected to protect the split's independence.
5. **Redistribution:** short attributed snippets only; link the source.

**Proposed first tranche** (pending owner review):
- **rr-04 first** — the only `high`-confidence deployed ruleset; maps cleanly
  onto INV-001..INV-003 shapes (read-only git allows, destructive git forbids).
- **rr-05's deploy pair** (`npm run deploy` → forbidden / `npm run
  deploy:production` → allow) as a variant/wrapped probe pair for the
  over-permissiveness class — but only with an explicit owner decision on
  whether `deploy:production → allow` is *intended* by a hypothetical policy
  author (intent coverage is separate from the REPRO measurement).
- **rr-02's alternation syntax** as syntax-coverage (pattern-form breadth),
  not as an invariant probe.
- **Defer rr-01/rr-03/rr-06** to a second tranche: rr-01 largely mirrors the
  official docs example (low marginal information), rr-03 is docs-style
  rather than deployed, rr-06's single-rule shape is thin.

**What "adopted" concretely means:** a new `fixtures/corpus_v2.json` (or
`corpus_realism.json`) with owner-set expectations, a new corpus version hash
in a fresh pre-registration, a fresh sealed bundle on the pinned oracle — and
the Day-2 bundle remains the published pre-fix/post-fix evidence, untouched.
The dual-verdict discipline applies unchanged: a REPRO `unknown` is a
successful measurement, never a passed invariant.

**Open question for the owner:** should corpus-v2 expectations be set per
*invariant* (mapping each candidate command to INV-001..INV-005) or per
*policy-author intent* (what the source's author plausibly meant)? The two
disagree on rr-05's `deploy:production` case, and the choice changes the
fixture file. Recommend deciding this before the first tranche is built.
