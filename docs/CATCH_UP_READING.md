# Catch-Up Reading Plan — Agent Boundary Conformance (for Anish, 2026-10-20)

Goal: after ~4–5 hours total, you can hold your own in any room on this topic. The field is only months old — nobody is years ahead of you. What exists is crowded *around* our spot (scanners, red-teamers, runtime governors) and empty *in* it (intent→decision conformance). Read in this order; each item says what it proves and the sentence it lets you say.

*Note: the "Priority 1/2/3" below are reading-priority levels for this plan only — unrelated to the harness measurement routes (vendor-confirmed / reconstructed / no paper surface), which are unranked.*

## Priority 1 — must read (~2.5 hrs)
1. **Codex execpolicy README + OpenAI "Agent approvals & security" doc** (~30 min)
   The ground truth for our first harness: prefix rules, no-match = decision omitted, strictest-wins, host-executable resolution; approval policies + sandbox as separate layers.
   *Say:* "A policy decision, an approval outcome, and an observed effect are three different things — most tools conflate at least two."
2. **"Scanning the Harness"** (arXiv:2609.07360, ~45 min, skim the tables)
   3,171 public repos of agent config; defect taxonomy; unpinned MCP servers as the sharpest defect class. It audits config *artifacts* — not decisions or effects. That boundary is our opening.
   *Say:* "The corpus work maps what's installed. Nobody's measuring whether the installed policy decides what its author intended."
3. **"Approval Laundering" + "Transitive Effects"** (arXiv:2609.38983 / 2609.28586, ~45 min combined, read abstracts + formalism)
   Approval records name the entry action but omit what it triggers downstream (hooks, writes, network authority). Motivates effect-level checks later — and teaches the vocabulary (closure-bound approval, effect classes).
   *Say:* "Even a perfect approval record is incomplete evidence — the effect closure is where the risk hides."
4. **conftest / OPA policy-testing tradition** (~20 min, conftest docs + one blog post)
   Our lineage: infrastructure learned a decade ago that policies need unit tests and CI regression ("policy as code" needs "policy tests as code"). We are porting that lesson to agent harnesses.
   *Say:* "Terraform and Kubernetes already went through this — agent permissions are just the next policy surface that needs conformance tests."

## Priority 2 — skim so nobody name-drops past you (~1.5 hrs)
5. **harness-eval README + agent-security-harness README** (~20 min) — the closest open-source neighbours; know exactly what they do (static lint; scenario tests) and don't (no native decision queries). If anyone cites the latter's test counts, you know they're self-adjudicated.
6. **Microsoft Agent Governance Toolkit repo** (~20 min) — the most complete native governance stack; enforcement, not independent testing. This is the "platform absorbs the shallow version" scenario in concrete form.
7. **Snyk Agent Scan docs** (~15 min) — inventory/content scanning; distribution is their weapon, not decision testing.
8. **Amp `permissions test` surface** (~25 min) — our second vendor-confirmed Decision-layer route (recognized Oct 22); know what `amp permissions test --json` decides and what it can't see (built-in rules unpublished). **Claude Code permissions/hooks + sandbox docs** (~25 min) — measured at the reconstructed route; auto-mode classifiers are Anthropic betting on smarter runtime decisions instead of deterministic evidence. Know the contrast; it's our best talking point.
9. **AWS Cedar for Bedrock AgentCore blog** (~10 min) — deterministic, analyzable authorization as a design philosophy; the enterprise vocabulary buyers will use.

## Priority 3 — only if a conversation goes there
- OWASP Agentic Top 10 + Regression Harness (scenario world), Promptfoo (red-teaming; now OpenAI's), garak (model probing), SARIF (evidence interchange format), AP2/x402 (the payments second vertical).

## The five sentences that make you sound like you belong (because they're true)
1. "We test the harness's *own* policy machinery against the developer's *stated intent* — we don't scan content and we don't judge model behaviour."
2. "Unmatched doesn't mean allowed, and allowed doesn't mean safe — decision, approval, and effect are separate layers and we report them separately."
3. "The vendor can't verify its own harness credibly — independence is the product."
4. "Our corpus and fixtures are public and replayable; anyone can check our numbers, including the embarrassing ones."
5. "Effect-level verification is the research frontier — the transitive-effects work proves decision-only evidence is incomplete."
