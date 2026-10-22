# Muse Code — Testability Assessment (2026-10-22)

*Assessment only: no corpus evaluation, no results.json. No account was
created, no login performed, nothing published, no outreach.*

**Naming note:** the wave brief titles this wave "Copilot" and names this
file `adapters/copilot-assessment.md`, but the assessment instructions
explicitly direct: *"for Muse (the CLI / coding-agent surface, NOT the IDE
autocomplete product; be explicit about which surface you assess)."* This
document assesses **Muse** per that instruction. It is NOT GitHub Copilot
(the IDE autocomplete product) and NOT the Muse personal agent (muse.ai /
Meta's Secure-VM assistant) — those are different products with different
surfaces. The filename is kept as directed; rename if the wave title was
meant literally.

## Surface assessed

- **Product:** Muse Code — Meta's terminal coding agent, CLI binary `muse`
- **Version under test:** `Muse Code 1.4.11 (1.4.11-R6667.1)`, channel
  `muse-stable`, binary sha256 `6fda12a6a4f23652…` (385 MB x86-64 Linux)
- **Install route (official):** `curl -fsSL https://dev.meta.ai/install.sh | bash`
  → downloads launcher `https://api.meta.ai/muse-launcher.sh` → resolves
  channel manifest at `https://api.meta.ai/muse-code/channels/muse-stable`
  → downloads `muse-x86-linux` from `lookaside.facebook.com`
- **Docs consulted:** musecodes.io/docs (official docs, read 2026-10-22);
  Meta bug-bounty article "Muse Code for Security Research"
  (bugbounty.meta.com; written against Muse Code 1.1.1, includes
  settings.json/approval documentation); binary's own `--help` and
  `muse schema generate-json-schema --experimental` (offline, exact for
  this build)

## Install attempt outcome

**Succeeded without any account.** Installation is not auth-walled: the
launcher resolved the channel manifest and downloaded the binary with no
credentials (no 401/403; the launcher's auth path exists for Meta-employee
gating but was not triggered). Incidental environment friction only:
`/tmp` (512 MB tmpfs) was full from other waves' scratch, so the binary
download failed with curl error 23 until the install was redirected to
workspace scratch (`MUSE_INSTALL_DIR`, `MUSE_NO_MODIFY_PATH=1`); no user
shell profiles were modified. All inspection was read-only: `--help`,
subcommand help, `schema` export, `config validate`, and one
`--provider echo` run in a scratch dir. **The auth wall appears one step
later:** Meta's own docs state *"You need a Muse Code account before any
of this works"* — first interactive run opens a browser sign-in at
dev.meta.ai (Meta developer account), or `MODEL_API_KEY`/`META_API_KEY`
for headless use. Per the hard limits, no login was attempted, so **no
live policy decision was ever observed.**

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO**

- The real 1.4.11 subcommand surface is: `resume exec config export trace
  model-profile skills voice plugins sandbox schema serve session-message
  mcp auth login logout init`. **No check/evaluate/dry-run/policy-decision
  entrypoint exists** (REPRO, `--help`).
- The MSP wire schema (exported offline from the binary) exposes
  `approval/decide` and `approval/listPending`, but these operate on **live
  pending approvals inside an authenticated session** — deciding an actual
  approval interactively, not evaluating a hypothetical command offline.
  `session/setApprovalMode` and `session/setPermissionProfile` are
  explicitly *"select, never create"* (schema descriptions).
- The approval pipeline is stochastic/interactive by design: schema type
  `ReviewerAuthority = autoReview | human | none`; CLI flag
  `--approval-judge <off|on>` is documented as *"LLM approval judge for
  Prompt-bound calls (default: on)"*; `ApprovalDecision` includes
  `timedOut`/`abort`; shell subjects carry per-stage `ApprovalStage` with
  `ShellPrefixSuggestion` (argv-prefix grammar) — i.e. even the
  deterministic-looking prefix layer feeds an LLM reviewer and/or a human.
- `muse exec --provider echo` runs fully offline with no account (REPRO),
  but the echo provider never makes tool calls, so no policy decision is
  exercised; a two-run determinism test has no oracle to test against.

### (b) Documented semantics precise enough for honest T2? — **NO**

- **No declarative per-command rule format is vendor-documented.**
  Permission profiles are a preconfigured native catalog: the schema
  (`PermissionProfileRow`) describes list/select only, and the binary
  carries *"only built-in ids enter the managed permission-profile map"* —
  there is no documented allowlist/denylist command-rule syntax to
  reimplement, no matching-semantics table (prefix? glob? literal?), no
  precedence rules, no worked examples.
- The closest documented construct is the **4-axis permission model**
  (from the binary's own experimental schema): approval
  (`onRequest|promptUnmatched|allowAll`), filesystem
  (`sandboxed|unrestricted`), network (`restricted|off|enabled`), reviewer
  (`autoReview|human|none`); `ApprovalMode` is a **closed** enum
  (`allowAll|promptUnmatched|onRequest|denyUnmatched`). These are *modes*,
  selected from a closed catalog — the five framework invariants cannot be
  translated into them.
- `muse config validate --plane policy --file` validates enterprise
  managed-settings documents offline without auth (REPRO), but it only
  **validates the document, never evaluates a command**; probed with
  guessed keys (`approval_mode`, `permissions.shell.deny`, `bogus_key`),
  all were rejected as `unknown_member` — the accepted schema is
  undocumented and is not a command-permission rule set.
- A custom profile format exists in the binary (`PermissionFormatV1`,
  `"denied by permission profile rule"` strings) but is **not publicly
  documented** — its rule fields and matching semantics are unknown.
- Third-party guides claim `config.json` keys like
  `file_write/shell_execute/file_read = ask|auto`, sandbox
  `allowed_commands`, and `deny_paths`; these are **unverified
  third-party claims** that do not appear in the 1.4.11 CLI help or the
  exported schema, and the enterprise validator rejects such shapes.
- Hooks (`PreToolUse`, `PermissionRequest` — 12 lifecycle events present
  in the binary; Meta's docs confirm both are blocking) are **arbitrary
  user code**, not a declarative policy surface; the block wire contract
  is not vendor-documented for this product.

### (c) Surface record (T3)

- **Policy surface:** 4-axis permission model (approval / filesystem /
  network / reviewer authority); named permission profiles
  (select-never-create); approval modes incl. `promptUnmatched` /
  `denyUnmatched` (the only named no-match behavior, at mode level, not
  per-command); LLM auto-reviewer + human-in-the-loop approvals; OS
  sandbox (Seatbelt macOS / bubblewrap Linux, write access to workspace +
  tmp, rest read-only); hooks `PreToolUse`/`PermissionRequest`;
  `AGENTS.md` rules loaded on workspace trust.
- **Defaults:** approval prompts and the OS sandbox are **ON by default**
  (CLI help: *"Safety (approval and the sandbox are ON by default)"*;
  default approval mode `on-request`); compound shell commands are
  reviewed stage-by-stage; MCP servers and hook commands run **outside**
  the sandbox (per vendor docs).
- **Decision oracle:** none exists — no offline, deterministic way to ask
  "what does this policy decide for this command." **No verdicts are
  issued.**

## Recommended tier

| Harness | Tier | Oracle type | One-line evidence |
|---|---|---|---|
| Muse Code (Meta, `muse` 1.4.11) | **T3** | none | Real binary inspected (REPRO): no check/evaluate subcommand; profiles are select-never-create with an undocumented rule format; approvals route through an LLM reviewer (default on) and human prompts — no deterministic offline decision interface exists. (DOC+REPRO) |

**Tier: T3 — Surface survey.** No honest T2 route exists today: there is
no documented command-rule format to reimplement, and the would-be oracle
would have to reproduce an LLM reviewer's judgment, which is not a
deterministic function of config.

## Open questions (what would resolve them)

1. **Documented `PermissionFormatV1` / custom-profile rule schema** — would
   turn the select-not-create catalog into an evaluatable rule set.
   (Vendor action: publish the schema.)
2. **A `muse policy check`-style offline entrypoint** — the T3→T1
   promotion condition, same as every other harness.
3. **Semantics of the shell argv-prefix grammar** (`ShellPrefixSuggestion`:
   prefix vs literal, precedence across stages, no-match within the
   grammar) — currently visible only as struct names in the binary.
4. **The `hooks.json` block wire contract** (how PreToolUse/PermissionRequest
   signals deny) — undocumented by the vendor; third parties guess by
   analogy to other products.

## Blockers

- **Account wall for any live decision:** observing even one real approval
  decision requires a Meta developer account (dev.meta.ai sign-in or
  `MODEL_API_KEY`) — forbidden by this wave's hard limits. Everything
  above the wall was verified without login; nothing below it was touched.
- **Stochastic reviewer in the decision path:** the LLM approval judge is
  on by default and profiles select reviewer authority
  (`autoReview|human|none`) — even with an account, per-command decisions
  would not be deterministic, so an oracle-style replay (Codex T1) is not
  achievable on the current architecture.
- **No declarative rule format:** without a documented allow/deny command
  syntax, a T2 reimplementation has nothing to reimplement — inventing
  rule semantics from binary struct names would be fabrication, not
  evaluation.

## Evidence log

- Official installer: `curl -fsSL https://dev.meta.ai/install.sh` (9,314
  bytes, audited before running); supports `MUSE_INSTALL_DIR` and
  `MUSE_NO_MODIFY_PATH=1`.
- `muse --version` → `Muse Code 1.4.11 (1.4.11-R6667.1)`; channel manifest
  `https://api.meta.ai/muse-code/channels/muse-stable`; artifact
  `https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.11-R6667.1&file=muse-x86-linux`.
- REPRO (no auth): full `--help`; `exec --help`; `config --help`;
  `sandbox --help`; `init --help`; `schema generate-json-schema`
  (stable: 368 defs; experimental: 465 defs); `config validate --plane
  policy|defaults` (accepts `{"schema_version":1,"settings":{}}`;
  rejects unknown settings members and `schema_version: 2`);
  `exec --provider echo --json` (runs offline, emits MSP event stream).
- Binary strings: hook event names (`PreToolUse`, `PermissionRequest`,
  `PostToolUse`, `SessionStart`, …); `ApprovalRequirementResolution`
  enum; `PermissionFormatV1`; `"denied by permission profile rule"`;
  *"only built-in ids enter the managed permission-profile map"*.
- Vendor docs: musecodes.io/docs (install, auth, sandbox defaults);
  bugbounty.meta.com "Muse Code for Security Research"
  (`~/.config/muse/settings.json`, `schema_version: 1`, approval layer,
  *"You need a Muse Code account before any of this works"*).
- Scratch (install dir, schema exports, echo-test session, plane probes)
  was wiped after the spike; all findings recorded here first.
