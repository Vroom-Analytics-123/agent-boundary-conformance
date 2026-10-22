# Claude Code policy translation notes (2026-10-22, T2 wave)

Source policies: `fixtures/policies/default.rules` + `fixtures/policies/protected_records.rules`
(Codex prefix-rule form) and `evidence/day1-baseline-2026-10-21/prec_{a..f}.rules`
(precedence probes). Target: Claude Code native `settings.json` `permissions`
(allow/ask/deny arrays of `Bash(...)` rules), checked into `policy/`.

Reference semantics: https://code.claude.com/docs/en/permissions (retrieved
2026-10-22, matching claude-code 2.1.307): deny -> ask -> allow, first match
wins, specificity irrelevant; `*` = any text incl. spaces; single trailing
` *` also matches the bare command; `:*` == trailing ` *`; Bash rules match
the command text AS WRITTEN after wrapper stripping and compound splitting;
no path resolution.

## Translation table

| Codex prefix rule | Claude Code native rule | List |
|---|---|---|
| `["git","status"]` -> allow | `Bash(git status *)` | allow |
| `["deployctl","release"]` -> prompt | `Bash(deployctl release *)` | ask |
| `["rm","-rf"]` -> forbidden | `Bash(rm -rf *)` | deny |
| `["rm","-fr"]` -> forbidden | `Bash(rm -fr *)` | deny |
| `["rm","--recursive","--force"]` -> forbidden | `Bash(rm --recursive --force *)` | deny |
| `["ls","/records/health"]` -> allow | `Bash(ls /records/health *)` | allow |
| `["rm","-rf","/records/health"]` -> forbidden | `Bash(rm -rf /records/health *)` | deny |
| `["rm","/records/health"]` -> forbidden | `Bash(rm /records/health *)` | deny |
| prec_a: `[git]`->prompt + `[git,status]`->allow | ask `Bash(git *)`, allow `Bash(git status *)` | ask/allow |
| prec_b: reversed order | same as prec_a (order lives across the deny>ask>allow lists, so within-list order is immaterial) | ask/allow |
| prec_c/d: `[git,status]`->allow + ->forbidden | allow + deny `Bash(git status *)` | allow/deny |
| prec_e/f: `[rm]`->prompt + `[rm,-rf]`->forbidden | ask `Bash(rm *)`, deny `Bash(rm -rf *)` | ask/deny |

The trailing ` *` is the faithful string analogue of Codex's argv-token
prefix: it matches the bare command (docs' single-wildcard concession) and
any space-separated continuation, reproducing the token boundary (e.g.
`Bash(rm -rf /records/health *)` does NOT match
`rm -rf /records/health/db.sqlite`, exactly like the Codex 3-token rule).

## Lossy edges (ceilings, never modelled)

1. Token-prefix vs literal-string: Codex matches argv tokens; Claude Code
   matches the raw command string. Consequences are measured, not assumed:
   compound splitting (deny/ask apply to ANY subcommand) makes F-11a/F-11b/
   F-12a/F-11d stricter than Codex's leading-segment-only evaluation.
2. Wrapper stripping: Claude Code strips timeout/time/nice/nohup/stdbuf/
   command/builtin/noglob, bare flagless xargs, and known-safe env
   assignments before matching; Codex strips nothing. Measured: S-04, S-05,
   S-08 go forbidden under Claude Code where Codex reports unknown.
3. No path resolution: Claude Code matches the program as written; there is
   no `--resolve-host-executables` analogue (docs' "doesn't match the same
   program invoked in a different form" table). Measured: F-13d/F-13R/F-14R/
   F-14bR go unknown where Codex-with-resolution reports a decision.
4. Bare-name deny removes the tool from the model's context (rules+model-
   visibility effect) — not modelled; no corpus fixture exercises it.
5. Hooks (PreToolUse arbitrary code), the stochastic auto-mode classifier,
   the six permission modes, sandbox sub-keys, and redirect-target file
   checks are documented layers out of evaluation scope (see evaluate.py
   header). The engine assumes Manual/default mode.
6. Compound splitting is top-level only (&&, ||, ;, |, quote-aware);
   `$(...)`/backtick nesting IS extracted for deny/ask (docs' worked
   example `echo "$(git clean -f)"`); bare `( ... )` subshells and for-loop
   bodies are not recursed (documented ceiling).

## Supplementary probe: the tree idiom

The checked-in `policy/protected.json` is the MECHANICAL translation (token-
boundary-faithful), which reproduces Codex's PA-02 miss (subpath unknown).
Measured separately in `results.json` -> `supplementary_tree_idiom_probe`:
with the vendor-documented directory idiom
(`Bash(rm -rf /records/health)` + `Bash(rm -rf /records/health/*)`, cf. the
docs' own `Read(./secrets/**)` pattern), PA-02 flips to forbidden while
PA-04/PA-06/PA-08 stay unknown and PA-01/PA-10 are unchanged. In Claude Code
the developer CAN express the whole-tree intent natively; Codex's
token-prefix family cannot express it at all. The primary policy stays
mechanical so the comparison is not tuned to the fixture.
