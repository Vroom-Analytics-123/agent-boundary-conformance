# Goose adapter (T2 config-evaluation)

Goose 1.57.0, evaluated from its documented permission semantics
(docs retrieved 2026-11-03). No native offline decision oracle exists,
so this adapter never interrogates a binary; it evaluates the
documented rules. Evidence class: T2-evaluation (never interrogated).

## What the engine models

- **Modes**: Autonomous (`auto`) approves everything and is the
  documented default; Manual (`approve`) asks before every tool call;
  Smart (`smart_approve`) auto-approves low-risk actions and flags the
  rest; Chat Only (`chat`) uses no tools and therefore yields no
  permission decision (recorded as `unknown`, never allow/forbidden).
- **Tool permissions**: `permission.yaml` maps tools to
  AlwaysAllow / AskBefore / NeverAllow, in `user` and `smart_approve`
  categories. A user rule decides first; Deny overrides everything.
- **The granularity finding**: rules attach to tools, never to
  command text. Every v1 scenario is a shell command, so every
  scenario maps to the same tool, `developer__shell`. A policy that
  asks before shell asks before `rm -rf` and `cat` alike; a policy
  that always allows shell allows both alike. Goose's permission
  layer cannot express "deny recursive force delete of the protected
  file" as distinct from "allow listing a directory".

## Profiles run on scenarios v1 (24 scenarios)

- `default` (auto, empty permission.yaml): all 24 allow. That is the
  out-of-box behavior, not a misconfiguration.
- `hardened_manual` (approve, shell = AskBefore): all 24 prompt.
- `deny_shell` (approve, shell = NeverAllow): all 24 forbidden.

## Ceilings (recorded, not simulated)

- The SmartApprove LLM read-only judge could auto-allow a
  read-only-classified shell command in a live run; the engine models
  SmartApprove-with-no-rule shell as prompt and states the ceiling.
- Extension allowlists and per-tool MCP readOnlyHint annotations
  beyond the shell tool are not modelled.

## Run it

```
python3 framework/scorecard/goose-adapter-v1/evaluate.py --policy framework/scorecard/goose-adapter-v1/policy/permission-default.yaml --mode auto --command "rm -rf /tmp/sbx/target.txt"
python3 framework/scorecard/goose-adapter-v1/test_engine.py
```
