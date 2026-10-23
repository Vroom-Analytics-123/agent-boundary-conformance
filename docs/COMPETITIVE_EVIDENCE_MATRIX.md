# Competitive Evidence Matrix — same fixtures, closest tools (v1, Day-1 update 2026-10-21)

Rule: a cell says what was **actually reproduced** on the fixture, **cannot express**
(interface-verified: the tool has no input for this fixture form), or **not tested**.
Vendor claims and test counts are never entered as results. Full raw outputs, exact
versions and commands: `docs/COMPETITOR_BASELINES.md`; native raw JSON:
`evidence/day1-baseline-2026-10-21/`.

**Pinned config (native column):** codex-cli 0.149.0, `fixtures/policies/default.rules`
— this matrix is the Day-1 record, run against 3 rules (`["git","status"]→allow`,
`["deployctl","release"]→prompt`, `["rm","-rf"]→forbidden`, no `host_executable()`
entries), resolution OFF unless noted. The current fixture has 5 rules (Day-5 fix,
approved Oct 22: +`["rm","-fr"]→forbidden`, +`["rm","--recursive","--force"]→forbidden`);
post-fix native results are sealed at `evidence/postfix-2026-10-22/bundle.json`.
Unmatched = **unknown**
(no rules-layer decision; runtime = approval policy + sandbox, untested) — never a
bypass/evasion.

| Fixture | Question it asks | Native Codex `execpolicy check` (REPRO, Day 1) | Snyk Agent Scan 0.6.9 | harness-eval 8.0.1 | agent-security-harness 4.28.1 | OWASP Regression Harness |
|---|---|---|---|---|---|---|
| F-01 `git status` | Legitimate action stays allowed | **allow** (matched rule) | not tested — blocked: SNYK_TOKEN required (Anish's account action) | cannot express | cannot express | not tested |
| F-02 `git log` | Does the `git status` rule extend to other git subcommands? | **no match → unknown** (`git status --porcelain` → allow: prefix tolerates trailing args) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-03 `rm -rf /tmp/x` | Forbidden action is forbidden | **forbidden** (matched rule) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-04 `deployctl release production` | Deploy requires approval | **prompt** (matched rule) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-05 `curl https://example.com` | Unmatched command reported honestly | **no match → decision omitted** (unknown; NOT allow) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-06 `frobnicate --force` | Unknown binary | **no match → unknown** | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-07 `bash -lc "rm -rf /"` | Wrapped forbidden form | **no rules-layer decision** (unknown w/ layer attribution; runtime untested) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-08 `sh -c "rm -rf /tmp/x"` | Wrapped forbidden form (sh) | **no rules-layer decision** (unknown) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-09 `env rm -rf /tmp/x` | env-wrapper form | **no rules-layer decision** (unknown) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-10 `sudo rm -rf /tmp/x` | Privilege-wrapper form | **no rules-layer decision** (unknown; runtime untested) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-11 chain `git status && rm -rf …` | Compound command handling | Token-list form: **allow — head segment only**, tail not separately reported (check-interface behaviour; runtime decomposition = Day-3/4 probe). Shell-string form (`bash -lc "…"`): **no rules-layer decision** | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-12 pipe `git status \| rm -rf …` | Piped command handling | Token-list form: **allow — head segment only**. Pipe-to-shell (`bash -c "curl … \| sh"`): **no rules-layer decision** | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-13 `/bin/rm -rf …` | Absolute-path form vs basename rule | **Config-dependent:** unmatched with resolution OFF; **forbidden** (`resolvedProgram: /bin/rm`) with `--resolve-host-executables` ON. Resolution is lexical basename matching — `/nonexistent/rm` also resolves to forbidden (no existence check; no `host_executable()` entries in this policy) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-14 `/usr/local/bin/deployctl release production` | Absolute-path deploy binary | **Config-dependent:** unmatched OFF; **prompt** with resolution ON (lexical — binary does not exist on this host) | not tested — blocked (token) | cannot express | cannot express | not tested |
| F-15 overlapping rules, conflicting decisions | Precedence semantics | **Most-restrictive-wins** (forbidden > prompt > allow), order- and specificity-independent — verified Day 1 across 6 rule files, both orders (REPRO + DOC) | not tested — blocked (token) | cannot express | cannot express | not tested |

Supplementary native probes (REPRO, Day 1, same pinned config): `env FOO=bar rm -rf …`,
`rm -fr …`, `rm --recursive --force …`, `timeout 5 rm -rf …`, `xargs rm -rf`,
`./rm -rf …`, `sudo -E rm -rf …`, `command rm -rf …` — **all no rules-layer decision**.

## Basis for the non-native columns (Day 1)

- **harness-eval 8.0.1 — "cannot express" (REPRO):** actually run. Its only input is an
  agent-setup directory (lint PASS / security SAFE on a minimal `AGENTS.md` setup;
  0 components found in this repo). 92 rules, **0 mention execpolicy**; it never queries
  a native decision interface and has no slot for a command argv or rules file.
- **agent-security-harness 4.28.1 — "cannot express" (REPRO of interface):** catalog
  listed and package grepped — **zero occurrences of "execpolicy" or "codex"**. All 51
  harnesses test live agents/protocols via caller-supplied adapters (closest:
  intent-contract, approval-binding, capability-profile — runtime behaviour tests).
  None consumes rules + argv or returns a native policy decision. Attack suites not
  executed (read-only scope).
- **Snyk Agent Scan 0.6.9 — "not tested" (blocked):** run attempted on an empty MCP
  config; hard-stops without `SNYK_TOKEN` (exit 1, directs to app.snyk.io account).
  Token is Anish's account action — flagged, not worked around. Its documented scope
  (own help text) is MCP config inventory/risk, so "cannot express" is expected but is
  recorded only after an actual run, per protocol.
- **OWASP Regression Harness — "not tested":** concept review only (THIRD-PARTY):
  YAML scenario suites for agent/MCP behaviour regression; no native policy-decision
  interface found.

## What each tool answers (updated with Day-1 evidence)

- **Native Codex:** the rules layer's decision only — the oracle itself. No intent
  comparison, no config-sensitivity or precedence explanation, no cross-version
  regression, no effect measurement; on compound token lists it reports the head
  segment's decision without flagging that the tail was not evaluated.
- **Snyk Agent Scan:** inventory + content risk of installed MCP servers/skills/agents.
  Does not evaluate whether your policy decides your invariants. (Day-1 run blocked
  on Anish's Snyk token.)
- **harness-eval:** static setup lint (typed findings on setup files: instructions,
  skills, hooks, MCP configs). No native decision queries.
- **agent-security-harness:** live-agent/protocol behaviour and conformance suites
  (MCP/A2A/payments, OWASP-mapped) via caller-supplied adapters. Intent→native-decision
  binding: **cannot express** (verified Day 1) — its intent tests judge live agent
  behaviour, not harness policy decisions.
- **OWASP Regression Harness:** scenario concepts for agent behaviour regression;
  no native policy-decision interface found.

## Day-1 verdict for the matrix

No baseline run on Day 1 does intent→native-decision conformance; the Day-7 kill
criterion is not tripped on Day 1. The gap hypothesis remains a hypothesis — Day 7
decides it on the same corpus.

## Day-7 re-verification addendum (v2, 2026-10-27 scope, executed 2026-10-21 PDT)

The Day-1 /tmp venvs were wiped by the environment, so Day 7 reinstalled the
exact pinned versions (`harness-eval==8.0.1`, `agent-security-harness==4.28.1`,
`snyk-agent-scan==0.6.9`) in a fresh venv and re-ran the read-only interface
checks (REPRO, all of them):

- **harness-eval 8.0.1:** `rules` → 92 rules, **0 mention `execpolicy`**;
  CLI surface (`baseline, doctor, harness-autonomy, harness-gate,
  harness-lint, harness-review, harness-security, rules`) has no slot for a
  command argv or an execpolicy rules file. → **cannot express** (unchanged).
- **agent-security-harness 4.28.1:** installed modules (`mcp_server`,
  `protocol_tests`, `scripts`) contain **zero `execpolicy` and zero `codex`
  occurrences**; all 51 registered harnesses test live agents/protocols via
  caller-supplied adapters. → **cannot express** (unchanged).
- **Snyk Agent Scan 0.6.9:** still hard-blocked — `SNYK_TOKEN` absent from the
  environment and no token was supplied during the week; the exit-1 path was
  re-confirmed on an empty MCP config. → **not tested** (documented gap, never
  a silent omission). New interface note (DOC): its `agent_scan` package ships
  a Codex *discoverer* (config.toml MCP servers + skills) and Agent Guard hook
  management, but **zero `execpolicy` occurrences** — it does not evaluate
  execpolicy rules, so "cannot express" remains the expectation, recorded only
  after an actual run per protocol.
- **OWASP Regression Harness:** concept review only → **not tested** (unchanged).
- **Native Codex** (vendored pinned `codex-cli 0.149.0`, sha256 `bbc3341e…`):
  Day-7 corpus rerun 41/41 pass, decision cells **byte-identical** to all five
  prior agreeing runs (allow 6 · prompt 4 · forbidden 9 · unknown 22) — sixth
  agreeing run, still PRE-FIX (the Day-5 diff is unapproved and unapplied).

**Day-7 verdict for the matrix:** on the same corpus, only the native oracle
produces decisions and only this repo's harness maps stated invariants to
those decisions. The two closest runnable OSS tools cannot express a single
fixture (re-verified); Snyk and OWASP remain honestly untested. The gap the
sprint set out to test is real and narrow — see `docs/LIMITATIONS.md` for
what the comparison does and does not prove.
