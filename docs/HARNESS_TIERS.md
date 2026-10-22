# Harness Tier Assignments — Agent Boundary Conformance (Day 4, 2026-10-21)

*Status: draft for the record. Nothing published. Per `docs/FRAMEWORK.md`, a
harness is described by its tier, never as generically "supported."*

## Question order (answered for every harness)

(a) Is there a deterministic, offline way to obtain the harness's OWN decision
for a command under a given policy? (b) If not, are the semantics documented
precisely enough for an honest T2 config-evaluation adapter — one that
computes decisions from documented semantics and labels them *evaluation*,
never *interrogation*? (c) If neither, the harness is T3: record the surface,
its defaults, and the absence of a decision oracle; issue NO verdicts.

Revision-2 semantics hold throughout: an unmatched command is "no decision,"
never a bypass/evasion/hole; unmatched serializes as **unknown**, never allow.

## Assignments

| Harness | Tier | Oracle type | One-line evidence |
|---|---|---|---|
| Codex (codex-cli 0.149.0) | **T1** | native-offline | `codex execpolicy check` returns the harness's own rules-layer decision offline and deterministically; 41-case corpus replays byte-identically across 4 independent runs (REPRO). Manifest: `adapters/codex.v0.manifest.json`. |
| Claude Code (@anthropic-ai/claude-code@2.1.307) | **T2** | config-evaluation | No native offline decision oracle exists, but allow/ask/deny matching semantics (deny→ask→allow first-match-wins, wildcard table, deny-always-wins) are documented precisely enough to compute evaluations — labelled evaluation, never interrogation. (INFERENCE on DOC+REPRO). Manifest: `adapters/claude-code.manifest.json`. |
| Cursor (CLI via cursor.com/install; docs pinned 2026-10-21) | **T2** | config-evaluation | Permission tokens, first-token+glob matching, and deny-precedence are documented precisely enough for evaluation in Allowlist mode; the default Auto-review mode's classifier is stochastic and staff-confirmed to drop hook asks, so it cannot be an oracle. (INFERENCE on DOC+THIRD-PARTY). Manifest: `adapters/cursor.manifest.json`. |
| Gemini CLI (@google/gemini-cli@0.65.0) | **T2** | config-evaluation | Locally reproduced `--help` proves no decision oracle exists, while the TOML policy engine (prefix/regex/argsPattern, priority tiers, mode scoping, documented precedence) is specified precisely enough to evaluate — labelled evaluation. (INFERENCE on REPRO+DOC). Manifest: `adapters/gemini-cli.manifest.json`. |
| OpenCode (opencode-ai@1.19.3; 1.x semantics pinned) | **T2** | config-evaluation | No offline oracle exists, but the permission object semantics (last-match-wins wildcards, per-agent merge precedence, documented defaults) are fully specified for 1.x — evaluatable, with the 1.x/2.x schema break as a hard version pin. (INFERENCE on DOC+REPRO). Manifest: `adapters/opencode.manifest.json`. |
| GitHub Copilot CLI (@github/copilot@1.0.103) | **T2-config** | config-evaluation | Install is not auth-walled but every live evaluation route sits behind `/login` (account/subscription wall, named). Offline binary inspection found no oracle-like entrypoint; semantics evaluatable from docs only. Assessment: `adapters/copilot-assessment.md`. |
| Muse Code — Meta (muse-stable 1.4.11; terminal coding agent) | **T3** | none located | No deterministic offline decision oracle in the CLI surface or official docs; surface and defaults recorded, no verdicts. Assessment: `adapters/muse-code-assessment.md`. (Bonus assessment outside the wave's original list; this is the `muse` terminal agent, not the Muse personal assistant.) |

**Revision — empirical wave (2026-10-22):** the five T2 harnesses were measured
through their best honest routes (no account/login anywhere). Claude Code
2.1.307 (85/85 doc-cited engine tests; 21 public + 6 protected cases),
Cursor 2026.10.19-6bbf2c4 (38/38 tests; 27 public cases; Allowlist mode only —
default Auto-review unevaluatable), Gemini CLI 0.65.0 (33/33 tests; 21 public +
6 protected; `--debug-policy` refuted at the pinned version), OpenCode 1.19.3
(43/43 tests; 27 public cases; last-match-wins demonstrated empirically — 3
order flips of 27). Each result is labelled T2-evaluation (never interrogated);
full evidence in `adapters/<harness>/` and the consolidated report at
`docs/harness-testing-2026-10-22.md`. **No harness changed tiers.** The evidence
*behind* each T2 assignment upgraded from documented-semantics to
measured-evaluation; the tier definitions and the T2→T1 promotion condition
(native offline decision entrypoint at a pinned version) are unchanged. Muse
Code is the first harness to land at T3 since Pi — the "no harness landed T3"
line above is superseded. Amp's T1 candidacy is a separate spike (awaiting the
founder's decision); it is not part of this revision.

Muse Code is the first harness to land at T3 since the Day-1 survey (Pi):
the "no harness landed T3" claim from 2026-10-21 was superseded by the
2026-10-22 empirical wave. T2 remains the ceiling until a vendor ships a
deterministic offline "evaluate this command against this policy" entrypoint
— the `codex execpolicy check` equivalent — at a pinned version. That is the
stated T2→T1 promotion condition for the T2 set (Amp's promotion is a separate
spike result awaiting the founder's decision, not an automatic consequence of
this wave).

## Evidence behind each assignment

### Codex — T1 (done Day 1–4)
- Native oracle: `codex execpolicy check --rules <file> [--resolve-host-executables] -- <argv...>` → JSON `{matchedRules[], decision?}` (REPRO, codex-cli 0.149.0).
- 41-case corpus + 11-case protected family replay byte-identically across 4 independent runs; negative controls 4/4 healthy; Merkle-sealed bundles.
- ENV DRIFT NOTE (Day 4): the environment replaced the pinned binary (0.149.0, sha256 `bbc3341e…`) with 0.164.0-alpha.9 AFTER the Day-4 run; all oracle data was collected on the pinned binary. Sealed bundles remain valid evidence of their pinned runs; on-disk re-verification is blocked until a pinned binary is restored. No vendored copy of 0.149.0 was kept — the pin checklist gains a binary-vendoring step.

### Claude Code — T2 (deepest spike)
- (a) NO: CLI subcommands (`daemon`, `doctor`, `import`, `logs`, `mcp`, `plugin`, `config`, `memory`, `session`, `auth`, `agents`, `attach`, `auto-mode`, `update`, `gateway`, `remote-control`) include no check/evaluate/dry-run. `doctor` is install/settings diagnostics; `auto-mode config` prints classifier rules (config inspection, not a per-command oracle). npm package's `sdk-tools.d.ts` exports only tool I/O schema types — no permission-check API (REPRO, read-only inspection).
- (b) YES: deny→ask→allow, first match wins, specificity irrelevant; wildcard table documented row-by-row; `Bash(git push *)` matches the command *as written* only — the docs themselves say such a rule "isn't a security boundary around the program" and point to the sandbox. Ceilings: stochastic auto-mode classifier (documented as a layer, never tested as an oracle in week 1), PreToolUse hooks (arbitrary user code), six permission modes, unconfirmed sandbox sub-keys (not asserted).
- Key quirk: literal-string Bash matching means an invariant "git push is blocked" that ignores flag-reordering is a false pass — a T2 adapter must model literal semantics.

### Cursor — T2
- (a) NO: documented CLI surface (`-p/--print`, `--force`, `--yolo`, `--mode=plan|ask`, `--approve-mcps`, `--workspace`, `--resume`, `mcp`, `generate-rule`, `ls`, `update`) has no check/evaluate subcommand. The npm package named `cursor-agent@1.0.3` is an unrelated third-party package (per its package.json), not the Cursor CLI — recorded so nobody else trips on it.
- (b) YES, in **Allowlist mode**: tokens `Shell(commandBase)` (first-token semantics), `Read`/`Write`/`WebFetch`/`Mcp`, glob vocabulary, deny takes precedence over allow. NOT in default Auto-review mode: classifier stochastic, and per Cursor staff (forum 2026-10-05) a hook's "ask" answer is silently dropped when the classifier deems the command safe — "deny" still enforced. The T2 adapter is honest only against Allowlist semantics; Auto-review verdicts labelled unevaluatable.
- Key quirk: in Auto-review (the recommended mode), an explicit `ask` can evaporate via silent classifier approval.

### Gemini CLI — T2
- (a) NO: locally reproduced `--help` on 0.65.0 shows no check/evaluate subcommand (commands: `mcp`, `extensions`, `skills`, `hooks`, `gemma`, `[query..]`). A third-party skill claims `--debug-policy`; the string is absent from the 0.65.0 bundle — claim unverified, not asserted.
- (b) YES: TOML policy engine (`commandPrefix`/`commandRegex`/`argsPattern`, `decision = allow|deny|ask_user`, tier Admin > User > Default regardless of priority, `modes` scoping, `interactive`); `confirmationRequired` takes precedence over `allowed`+`core`; shell validation splits chains and validates each part, blocklist first. Ceilings: stochastic Conseca LLM layer, folderTrust default DOC-vs-DOC conflict (assert neither), deprecated keys in version churn (`tools.exclude`, `--allowed-tools`), runtime mode flags (`--yolo` CLI-flag-only), MCP/extension surface.
- Key quirk: YOLO cannot be enabled from `settings.json` (CLI flag only), but TOML rules can be scoped `modes = ["yolo"]` to re-impose `ask_user`/`deny` inside YOLO — the mode dimension is part of the decision function.

### OpenCode — T2
- (a) NO: command surface (`run`, `mini`, `session`, `auth`, `models`, `mcp`, `plugin`, `service`, `serve`, `pair`, `api`, `reload`, `stats`, `acp`, `debug`, …) has no check/evaluate; `debug config` shows resolved config only.
- (b) YES, at **1.x**: permission object with simple wildcards, **last matching rule wins** (order-dependent — the sharpest contrast with Claude/Cursor deny-first), per-agent overrides merged with agent rules taking precedence, documented defaults. Ceilings: 1.x/2.x schema break (adapter pins 1.x; 2.x is an ordered `permissions` list — needs a separate pass), unspecified "parsed commands" normalization, session-state `always` approvals, runtime `--auto`.
- Key quirk: last-match-wins + permissive defaults — `{"shell": {"*": "ask", "git *": "allow"}}` behaves oppositely if the lines are swapped, and a fresh install allows nearly everything. The *absence* of config is decision-relevant.

## Cross-cutting findings (method-level, not per-harness)

1. **Precedence is not uniform** — the framework's sharpest inter-harness difference: Claude = deny→ask→allow fixed order; Cursor = deny over allow; Gemini = Admin tier > User tier > Default tier, then priority; OpenCode = last match wins. A shared invariant schema must not assume a common precedence operator. No T2 adapter may "re-implement the harness's matching logic and present the result as the harness's decision" — each manifest sets `reimplements_matching: true` and labels output evaluation.
2. **No-match defaults are ask-like everywhere**: Claude → ask; OpenCode (non-auto) → ask; Gemini → confirmation dialog; Cursor → prompt. Every manifest maps harness no-match to framework unknown — never allow (INV-005). No claim rests on an unmatched rule.
3. **No adapter masquerades as a decision oracle it is not**: all four manifests declare `oracle.type: config-evaluation` and the manifests' evidence classes are DOC+REPRO/DOC+THIRD-PARTY/INFERENCE — never REPRO-alone for decisions.
4. **Install state**: none of the four CLIs were installed on this machine (only codex). Claude/Cursor/OpenCode CLIs were never executed; Gemini CLI's 0.65.0 bundle was executed read-only in a scratch dir (`--help`, `--version`, bundle grep) with no session launched and no repo touched. No MCP servers, hooks, or repo code were executed. `/tmp` scratch dirs were wiped by the environment after the spike; all findings were recorded first.

## Open questions (what would resolve them)

- Claude Code: official enumeration of `sandbox` settings sub-keys; binary pin via a local pinned install.
- Cursor: real CLI install at a pinned version for a read-only (a)-spike; documented IDE-settings↔CLI-token mapping; offline decision entrypoint (T2→T1 condition).
- Gemini CLI: verification (or refutation) of the `--debug-policy` flag at a pinned version; vendor resolution of the folderTrust default conflict.
- OpenCode: 2.x `permissions` semantics at a pinned 2.x version; documentation of the command-parsing step.
- Codex: vendored copy of the pinned 0.149.0 binary (see env drift note above); runtime-probe design for the approval+sandbox layers.
