# Cursor (Allowlist mode) — T2 evaluation test log (2026-10-22)

Harness: cursor | Version under test: **2026.10.19-6bbf2c4** | Route: **(b) T2 config-evaluation**
Scope: Allowlist mode ONLY. Default Auto-review mode is unevaluatable
(stochastic classifier) — no verdicts emitted for it, ever.

## 1. Version establishment

- Official route `curl https://cursor.com/install` (still current per docs and
  third-party guides). Fetched the installer script 2026-10-22: it pinned and
  downloaded `https://downloads.cursor.com/lab/2026.10.19-6bbf2c4/linux/x64/agent-cli-package.tar.gz`.
- Installed workspace-locally with `HOME` pointed at a scratch dir (no login,
  no account; installer performs no auth). Read-only inspection only:
  `--version` → `2026.10.19-6bbf2c4`; `--help` printed the full CLI surface.
- npm trap avoided: the npm package `cursor-agent@1.0.3` is an unrelated
  third-party package (already recorded in the manifest).
- Note: `/tmp` here is a 512M tmpfs — the ~560M extracted bundle does not fit;
  install ran on the home-disk scratch dir instead, then was cleaned up.

## 2. Spike (a) re-run: no native decision oracle — CONFIRMED at 2026.10.19-6bbf2c4

`--help` surface (full): `persist`, `install-shell-integration`,
`uninstall-shell-integration`, `login`, `logout`, `mcp`, `plugin`, `worker`,
`status|whoami`, `models`, `team`, `bedrock`, `about`, `update`, `create-chat`,
`generate-rule|rule`, `agent [prompt...]`, `ls`, `resume`, `help`; flags
`-p/--print`, `--force`/`--yolo` ("Force allow commands unless explicitly
denied"), `--mode=plan|ask`, `--auto-review` ("a server classifier auto-runs
safe tool calls and prompts for the rest"), `--sandbox`, `--approve-mcps`,
`--trust`, `--workspace`, `--resume`. **No check/evaluate/assess subcommand.**
Determinism demo N/A (no oracle). Route (b) applies.

Bundle corroboration (read-only grep of the shipped artifact):
- Token syntax confirmed live in the bundle: `Shell(${t})` / `Mcp(${t})`
  construction strings, and an allowlist prompt `"Add ${notAllowedCommands
  ... Shell(${e})} to allowlist?"` — the docs' token surface is real, not
  aspirational.
- The matching implementation itself was not recoverable from client strings
  (minified; likely server-side), so the T2 reimplementation rests on the
  docs — labelled honestly as evaluation, never interrogation.

## 3. Docs pin (retrieved 2026-10-22, confirms the 2026-10-21 pin)

`https://cursor.com/docs/cli/reference/permissions` — verbatim semantics
implemented:
- `Shell(commandBase)`: "The `commandBase` is the first token in the command
  line." Globs; optional `command:args` syntax ("match both command and
  arguments with globs", e.g. `Shell(curl:*)`).
- `Read`/`Write(pathOrGlob)`; `WebFetch(domainOrPattern)` ("Without an
  allowlist entry, each fetch prompts for approval"); `Mcp(server:tool)`.
- Glob wildcards `**`, `*`, `?`; "Deny rules take precedence over allow rules";
  no-match → prompt.

## 4. Translation (policy/allowlist.json, protected.json, prec_a..f.json)

Codex prefix rules → Cursor Shell tokens (1:1, rule-by-rule):
- `[git,status]→allow` → `Shell(git:status*)` (narrow args-glob, NOT bare
  `Shell(git)`, so `git log` stays unmatched like the Codex prefix rule).
- `[deployctl,release]→prompt` → **dropped**: `prompt` has no Allowlist verb.
  No-match → interactive prompt, reported `unknown` at T2 with layer
  attribution. Recorded as untranslatable, never forced into allow/deny.
- `[rm,-rf]→forbidden` → `Shell(rm:-rf*)`; `[rm,-fr]` → `Shell(rm:-fr*)`;
  `[rm,--recursive,--force]` → `Shell(rm:--recursive --force*)` (Day-5 rules).
- protected_records.rules: `Shell(ls:/records/health)` allow;
  `Shell(rm:-rf /records/health)` + `Shell(rm:/records/health)` deny (exact
  args-glob so the subpath PA-02 stays unmatched, mirroring Codex token
  semantics; the safer glob-subpath alternative is documented in the policy
  file as the rejected option).
- prec_a..f.json: prompt rules dropped (→ allow-only or deny-only policies);
  deny listed in both orders per fixture.

Translation assumptions (ceilings, recorded in evaluate.py A1–A4):
- argv → command line = tokens joined with single spaces; first token =
  argv[0]; args = remainder, leading whitespace stripped. No shell-quoting
  reconstruction. String-glob vs token-prefix divergence is real
  (e.g. `git statusX` would match `status*` but not the Codex prefix).
- No executable-resolution concept in Cursor docs: `/bin/rm` matched as
  given → unknown where Codex (resolve) decides.
- Glob flavor: `*` crosses `/` for Shell args/domains/Mcp (required by docs'
  own `Shell(curl:*)` example against URLs); minimatch path semantics
  (`**/` = zero or more segments) for Read/Write paths.

## 5. Engine + tests

- `evaluate.py`: deterministic, pure functions; deny wins; no-match → unknown
  (layer attribution), never allow.
- `test_engine.py`: **38/38 pass**. Every worked example in the permissions
  doc is covered (Shell: ls, git, npm, curl:*, rm; Read: src/**/*.ts,
  **/*.md, .env*, /etc/passwd; Write: src/**, package.json, **/*.key,
  **/.env*; WebFetch: docs.github.com, *.example.com, *; Mcp: datadog:*,
  *:search, *:*; glob `**/*/​?`; WebFetch no-match→prompt) + precedence
  probes (conflicting allow/deny, allow-first AND deny-first orders) +
  no-match→unknown guard (INV-005) + a path-form/no-resolution case +
  invariant pins against the actual policy fixture.

## 6. Evaluation results

- 41 corpus cases (21 public + 20 held-out) + 11 protected-family cases
  (6 public + 5 held-out) through the translated policies.
- Public: **24/27 expected-match**. Protected family public: 6/6 match.
- Held-out: **20/25 expected-match** (per-case detail in gitignored
  `results_heldout.local.json`; only aggregates + shard sha256 in results.json).

### Headline divergences from the Codex T1 baseline
1. **Prompt is untranslatable** (F-04, F-14R, F-15a, F-15b): Cursor Allowlist
   config has no prompt verb. F-04/F-14R → unknown (interactive prompt,
   unobserved at T2); F-15a/b → **allow** — the Codex prompt rule evaporates
   and the narrower allow rule stands alone, where Codex's
   most-restrictive-wins gives prompt. First-token Shell semantics are not
   the cause here; the missing decision verb is.
2. **No executable resolution** (F-13d, F-13R, F-14bR): `/bin/rm`,
   `/nonexistent/rm`, `/bin/git` → unknown; Codex (--resolve) decides
   (forbidden/forbidden/allow). Cursor docs describe no resolution analogue.
3. **S-02**: engine forbidden == Codex post-fix actual (forbidden); the frozen
   fixture expected (unknown) is the Day-5 held-out bookkeeping artifact.
   **S-03**: engine forbidden; `codex_day2_actual=unknown` in results.json is
   the PRE-fix run — post-fix Codex actual is forbidden (recorded).

## 7. Tier assessment

T2 (config-evaluation) CONFIRMED and now strengthened: the real binary
(version-pinned) ships the documented token surface, and the matching
semantics are pinned to freshly re-retrieved vendor docs with a unit-tested
reimplementation. No change to the T2 claim; scope remains Allowlist mode
only. T2→T1 promotion condition unchanged: Cursor ships a deterministic
offline evaluation entrypoint.

## 8. Blockers

- No oracle subcommand at 2026.10.19-6bbf2c4 (native interrogation blocked by
  vendor, not by us).
- Auto-review mode unevaluatable by construction (stochastic classifier).
- No account/login was created or used; install + inspection were read-only.
