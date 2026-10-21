# Day-0 smoke test — 2026-10-20 (VERIFIED, avan)

Environment: this VM, `codex-cli 0.149.0` (`/opt/hatch-image/bin/codex`).
Policy file: `fixtures/policies/default.rules`
```
prefix_rule(pattern=["git", "status"], decision="allow")
prefix_rule(pattern=["deployctl", "release"], decision="prompt")
prefix_rule(pattern=["rm", "-rf"], decision="forbidden")
```
Command form: `codex execpolicy check --rules test.rules -- <cmd>`

| # | Command | Raw native output | Normalized |
|---|---|---|---|
| 1 | `git status` | `{"matchedRules":[{"prefixRuleMatch":{"matchedPrefix":["git","status"],"decision":"allow"}}],"decision":"allow"}` | allow |
| 2 | `deployctl release production` | `{"matchedRules":[{"prefixRuleMatch":{"matchedPrefix":["deployctl","release"],"decision":"prompt"}}],"decision":"prompt"}` | prompt |
| 3 | `rm -rf /tmp/x` | `{"matchedRules":[{"prefixRuleMatch":{"matchedPrefix":["rm","-rf"],"decision":"forbidden"}}],"decision":"forbidden"}` | forbidden |
| 4 | `curl https://example.com` | `{"matchedRules":[]}` | **unmatched → unknown** (no-match is NOT allow) |
| 5 | `bash -lc "rm -rf /"` | `{"matchedRules":[]}` | **unmatched → the rules layer issues no decision.** NOT evidence the command would run: at runtime the outcome is governed by the session approval policy + sandbox (see Correction Addendum). The finding is a *decision-coverage* gap: a developer reading only their rules file cannot tell what happens to this command form. |

## Supplementary probes (same session, all VERIFIED)

| # | Command / rules | Raw result | Finding |
|---|---|---|---|
| 6 | `/bin/rm -rf /tmp/x` (basename rule `rm`), default flags | `{"matchedRules":[]}` | Unmatched **only under default flags**. CORRECTED 2026-10-20 (revision 2): re-run with `--resolve-host-executables` → `{"matchedRules":[{... "decision":"forbidden","resolvedProgram":"/bin/rm"}],"decision":"forbidden"}`. Basename fallback exists and is opt-in via flag / `host_executable()` metadata. The Day-0 "path-form evasion family" claim is WITHDRAWN as stated; the accurate finding is that the result is **configuration-dependent**, which a conformance report must state (flags + host_executable entries are part of the tested configuration). |
| 7 | `sudo rm -rf /tmp/x` | `{"matchedRules":[]}` | Unmatched at the rules layer (first token is `sudo`, no rule covers it). Runtime outcome depends on approval policy/sandbox — do NOT describe as "evades" or a bypass. |
| 8 | `bash -lc "git status && rm -rf /tmp/x"` | `{"matchedRules":[]}` | At the rules layer the wrapped string is one opaque token sequence (no rule matches). Whether runtime chain-splitting applies to the inner string is a separate runtime question — Day-3/4 experiment, not a Day-0 claim. |
| 9 | Overlapping rules `[git]→prompt` + `[git,status]→allow`, both file orders | decision: `prompt` in BOTH orders; both rules listed in matchedRules | **Precedence = most-restrictive-wins** (forbidden > prompt > allow), independent of rule order or specificity. |
| 10 | Same prefix `[git,status]→allow` + `[git,status]→forbidden` | decision: `forbidden` | Confirms #9: not first-match, not last-match. A developer assuming firewall-style first-match semantics will misread their own policy — a conformance report must state this explicitly. |

Key facts established:
- The native oracle is real, deterministic, and returns machine-readable JSON. The 1-week build is feasible.
- Finding F-001 (REVISED, revision 2): for wrapped command forms (`bash -lc "…"`), the **rules layer issues no decision**. That is a decision-coverage gap relative to a developer's stated intent ("rm -rf is forbidden"), not a demonstrated bypass. What actually happens at runtime is decided by two further layers (approval policy, sandbox) and must be measured separately under pinned settings before any stronger claim is made.
- Codex `allow` means "run outside the sandbox without prompting" — a policy decision is not an observed effect. Reports must keep these evidence levels separate. No "secure" verdicts, ever.

## Correction Addendum — 2026-10-20 (revision 2, after external review + primary-source recheck)

Three-layer model (use this language everywhere; replaces all "evasion/bypass/hole" wording in Day-0 materials):
1. **Rules layer** (`execpolicy check`): prefix rules decide allow/prompt/forbidden. No match → `matchedRules: []` and `decision` omitted (official execpolicy README, verified 2026-10-20). Effective decision across matches = strictest (forbidden > prompt > allow) — official docs confirm probes #9/#10.
2. **Approval policy layer** (session config): per OpenAI's approvals documentation, commands require approval unless an execution-policy rule allows them (under the trust-derived default); explicit `approval_policy` settings (on-request / never / granular) change what an unmatched or prompt-decided command does. Unmatched ≠ permitted.
3. **Sandbox layer**: OS-enforced sandbox (workspace-write by default) bounds effects even for approved commands; `allow` decisions bypass the sandbox, which is why decision ≠ effect and effect-level checks remain a separate, later research stage.

Also corrected: probe #6 (absolute path) is flag-dependent — with `--resolve-host-executables` the same command returns **forbidden** with `resolvedProgram: /bin/rm` (reproduced 2026-10-20). Any conformance run must record resolution flags and `host_executable()` entries as part of the pinned configuration.

Evidence classes used from revision 2 onward: **DOC** (verified from official documentation) · **REPRO** (reproduced experimentally, with version + config) · **THIRD-PARTY** (reported by others) · **INFERENCE** · **HYPOTHESIS**. Day-0 rows 1–5, 9, 10 = REPRO + DOC. Runtime behavior of wrapped commands under pinned approval/sandbox settings = HYPOTHESIS until the Day-3/4 runtime experiment runs.
