# GitHub Copilot CLI — Testability Assessment (2026-10-22)

*Assessment only: no corpus evaluation, no results.json. No account created,
no login performed, nothing published, no outreach, no commits.*

**Naming note (explicit):** this assesses **GitHub Copilot CLI** — GitHub's
agentic terminal coding assistant (`copilot`, npm `@github/copilot`). It is
NOT the IDE inline-suggestion autocomplete product (same brand, different
surface), NOT the VS Code "agent mode," and NOT Meta's Muse Code
(`adapters/muse-code-assessment.md` covers that — a different product).

## Surface assessed

- **Product:** GitHub Copilot CLI 1.0.103 — `copilot version` →
  `GitHub Copilot CLI 1.0.103` ("You are running the latest version")
- **Packages:** `@github/copilot@1.0.103` (npm registry metadata, public —
  install is NOT auth-walled); native binary `@github/copilot-linux-x64@1.0.103`
  (190 MB x86-64 Linux), loaded via `npm-loader.js`
- **Install route (official):** `npm install -g @github/copilot` (also
  WinGet `GitHub.Copilot`, Homebrew `copilot-cli`, `gh.io/copilot-install`
  script); repo `github.com/github/copilot-cli`
- **Docs consulted (fetched 2026-10-22):** docs.github.com "Installing
  Copilot CLI," "Allowing and denying tool use," "GitHub Copilot CLI
  configuration directory" (`#permissions-configjson` anchor + Managed
  settings), github.com/github/copilot-cli README
- **Binary inspection (offline, read-only, scratch `COPILOT_HOME`):**
  `--help`, `help`, `version`, `help permissions`, `help config`,
  `config --list --json`, `sandbox --help`, `config --help`; binary strings
  grep for oracle-like entrypoints

## Install attempt outcome

**Install succeeded with no account.** `npm install --prefix <scratch>
@github/copilot@1.0.103` completed (13 s, 3 packages) with no credentials.
**The auth wall is one step later, at first launch / any session:**
prerequisite is an *active GitHub Copilot subscription*; on first launch
the CLI prompts `/login` (GitHub OAuth device flow), or auth via a
fine-grained PAT with the "Copilot Requests" permission, or
`COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` env precedence
(third-party doc corroborates the env order). Per the hard limits, no login
was attempted, so **no live policy decision was ever observed.** All
inspection below the wall was verified without login; nothing above it was
touched.

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO**

- Full subcommand surface (REPRO, `--help`/`help`): `app login help init
  config update version workflow sessions memories plugin mcp skill
  instruction lsp sandbox completion`. **No check/evaluate/dry-run/policy
  entrypoint.** `sandbox` has only a `ca` (credential-proxy CA) subcommand;
  `config` is settings inspection/editing only (`config --list --json`
  → `{}` exit 0 on a fresh scratch HOME, no login).
- Binary strings grep (190 MB native binary): no hits for "permissions
  test", "policy check", "dry-run", "dry_run", "what-if", "policy test"
  (only Node/V8-internal "Evaluate" symbols). There is no
  `amp permissions test` analogue.
- `copilot help <topic>` topics are docs, not evaluators. Determinism demo
  is N/A: there is no decision function to replay.

### (b) Documented semantics precise enough for honest T2? — **YES**

The surface is declarative and the semantics are specified row-by-row in
both vendor docs and the binary's own help. Four rule surfaces, three of
them user-authorable:

**1. Per-session CLI flags — `--allow-tool` / `--deny-tool`**
(DOC: "Allowing and denying tool use"; REPRO: `copilot help permissions`).
Pattern form `kind(argument)`:

- `shell(command)` — exact match against the command *name*; approval is
  performed on a **first-level subcommand basis** (`git push`, `gh pr
  create`). Suffix `:*` matches prefixes on the command **stem**:
  `shell(git:*)` matches `git push` but NOT `gitea`. Omitting the command
  matches all shell commands.
- `write(path?)` — file create/modify tools, *excluding shell invocations*.
  Relative path matches by **trailing path components** (`write(.env)`
  matches `.env` in any directory); absolute path scopes to one location.
  Omitting the path matches all writes.
- `<mcp-server-name>(tool-name?)` — exact match of a tool on a named MCP
  server, or all tools on the server if omitted.
- `url(domain-or-url?)` — URL requests (shell + web-fetch tools).
  Protocol-aware: exact URLs, `protocol://domain`, wildcard subdomains
  (`url(https://*.github.com)`); bare domains default to `https://`.

Precedence (DOC + binary help, both): **deny always wins over allow** —
"even `--allow-all-tools`"; DOC adds deny beats saved approvals in
`permissions-config.json`. No order-dependence is documented (union/deny-
first, unlike OpenCode's last-match-wins).

**2. Tool-availability filter — `--available-tools` / `--excluded-tools`**
Restrict which tools the *model can see*. If both are given, the
allowlist wins and the denylist is ignored. A tool outside the available
set "won't be able to use it at all, even if you specify it with
`--allow-tool`." (Model-visibility layer + invocation denial; the docs
frame availability as distinct from approval.)

**3. Saved approvals — `~/.copilot/permissions-config.json`**
Full vendor schema (DOC, with worked pattern table): `locations` keyed by
absolute path (git root, or normalized cwd; worktree→main-root). Approval
kinds: `commands` (`commandIdentifiers`), `read`, `write`, `mcp`
(`serverName`+`toolName`, `null` = all tools), `mcp-sampling`, `memory`,
`custom-tool` (exact name), `extension-management`, `extension-permission-
access`. **Matching: literal strings; no regex, no general globs** — the
ONLY wildcard is a trailing `:*` in shell `commandIdentifiers`, matching
the stem alone or stem + space + more text (`git:*` matches `git`, `git
status`, `git push`; NOT `gitea`; `git*` matches nothing special).
Explicitly does NOT support: deny rules, ask rules, default modes, URL
rules, tool filtering, repository-local shared policy (use CLI flags or
managed settings for those).

**4. Managed `permissions` deny/ask/allow rule arrays** (DOC, "Managed
permission rules" — MDM/server admin surface). Rule families:

- `Bash(...)` / `Shell(...)` — `<command> *` = prefix, otherwise exact
  text (e.g. `Shell(git push *)`, `Shell(rm -rf *)`); `PowerShell(...)`
  same.
- `Read(...)` / `Edit(...)` / `Write(...)` — path globs; `/` = workspace
  root, `~/` = home, `./` = cwd. Also covers shell-redirection writes
  (`>`, `>>`, `>|`, `&>`, `&>>`, PowerShell forms, `sed -i` family); if the
  target can't be resolved ahead of time (e.g. from a variable), the
  command falls back to the shell rules.
- `Domain(...)` — URL hostnames, "matched like URL rules."

Precedence: **deny > ask > allow**, fixed. `deny` and `ask` are **unioned**
across managed sources (server, MDM); `allow` is an **intersection** —
every source declaring an `allow` list must admit the operation. **No-match
default: ask** — "When any of deny, ask, or allow is set, an operation
that matches none of them defaults to `ask` rather than falling through
silently." Managed values set floors user settings cannot relax
(`sandbox`, `permissions.disableBypassPermissionsMode` = fail-closed
`"disable"` on unrecognized values; account switches cannot override).

**No-match defaults overall:** default permission mode is `manual` (binary
`help config`, REPRO): *write and command requests are prompted; read-only
requests are auto-approved.* DOC: read-only operations (search, reads,
read-only shell) auto-allowed; destructive shell, edits, URLs require
explicit approval. Path gate: cwd + subdirs + temp dir by default
(`--allow-all-paths`, `--disallow-temp-dir`). → framework mapping:
no-match ≈ prompt ⇒ **unknown**, never allow (INV-005).

**CORRECTION to FRAMEWORK.md:** the survey note calls Copilot "the least
declarative surface of the set." For the **CLI** surface that is wrong:
deny-always-wins precedence, stem-prefix shell matching with worked
examples, literal-plus-`:*` saved-approval matching, and a documented
deny/ask/allow precedence + ask-by-default rule language are **at least as
declarative as the other T2 harnesses** (the note likely described the
IDE autocomplete product, not the CLI). The managed rule-array format is
the richest of the set; its ceiling is that it is admin-authored only —
it does not appear in the user `settings.json` reference (verified:
`copilot help config`, 262 lines, no `permissions` deny/ask/allow keys).

**Ceilings capping at T2 (gaps, all recorded):**

1. No offline oracle — everything above is DOC (+REPRO of the help text),
   never interrogation.
2. The `permissions` deny/ask/allow array format is documented under
   **managed settings only**; a T2 adapter evaluating it ingests
   admin-authored policy, not something an ordinary user writes in
   `settings.json`.
3. "Read-only shell command" auto-allow classifier is a built-in
   heuristic — which commands count as read-only is **not documented**.
4. Compound commands: how `cmd1 && cmd2` (or `;`, `|`) chains are split
   and matched by shell rules is **not documented** (contrast Gemini's
   documented chain-splitting).
5. Args beyond the first-level subcommand stem (`git push --force origin
   main` vs `shell(git push)`) — "first-level subcommand basis" implies
   stem matching, but exact normalization is unstated.
6. URL "domain patterns" grammar for `Domain(...)` ("matched like URL
   rules") is less precise than the flag-level `url()` spec.
7. Stochastic layers, vendor-acknowledged: `defaultPermissionMode:
   "assisted"` = "a probabilistic LLM review"; the binary's own help says
   it **"is not a security boundary and may approve dangerous or
   unintended actions."** Autopilot mode, `/permissions assisted`,
   model-chosen tool invocation (availability filters are
   model-visibility, not verdicts).
8. Version churn: `autoUpdate` defaults true; the pin is load-bearing.
   The binary's own help notes the flag permission surface "will be
   extended in the very near future to support wildcard matching and
   other richer functionality" — explicitly under construction.

### (c) Surface record — N/A (harness is T2, not T3)

## Recommended tier

| Harness | Tier | Oracle type | One-line evidence |
|---|---|---|---|
| GitHub Copilot CLI (`@github/copilot` 1.0.103) | **T2** | config-evaluation | No check/evaluate subcommand (REPRO: full subcommand list + binary strings grep), but deny-always-wins precedence, stem-prefix shell patterns, literal-plus-`:*` saved approvals, and managed deny/ask/allow arrays with an ask-by-default rule are documented precisely enough to evaluate — labelled evaluation, never interrogation. (INFERENCE on DOC+REPRO) |

**Tier: T2 — Config evaluation.** An honest adapter evaluates the
deny-first rule engine (flags + `permissions-config.json` + URL lists +
managed arrays) against the five invariants in the shared vocabulary,
labels every result evaluation, and treats stochastic layers (assisted
mode, Autopilot, model tool-choice) as unevaluatable — unknown with layer
attribution, never a verdict.

## Open questions (what would resolve them)

1. **Live decision probe behind the wall** — one authenticated run asking
   "what does this policy decide for this command" would confirm the DOC
   semantics against the runtime. Blocked by the login/subscription wall
   (hard limit). T2→T1 condition stays: a shipped offline evaluator.
2. **Read-only shell classifier** — vendor documentation of which shell
   commands count as "read-only" for auto-approval.
3. **Chain/splitting semantics** for `&&`/`;`/`|` in shell rule matching.
4. **Managed `permissions` in user settings** — confirmation (or denial)
   that deny/ask/allow arrays are truly managed-only; currently inferred
   from their absence in `copilot help config`.
5. **Pin hazard** — `autoUpdate` default true; adapter must pin
   1.0.103 and re-verify the flag surface each version (the binary itself
   warns richer wildcard matching is coming).

## Blockers

- **Account + subscription wall for any live decision:** GitHub login and
  an active Copilot subscription are required for any session; no live
  approval was (or could be) observed under the hard limits.
- **Stochastic "assisted" permission mode:** probabilistic LLM reviewer in
  the decision path, vendor-stated "not a security boundary" — the honest
  evaluation target is `manual` mode + the deny-first rule engine only.
- **Richest rule format is admin-only:** the deny/ask/allow arrays live in
  MDM/server managed settings; ordinary users author per-session flags,
  saved allow-only approvals, and URL lists.

## Evidence log

- `npm view @github/copilot` → `1.0.103`,
  `dist.tarball https://registry.npmjs.org/@github/copilot/-/copilot-1.0.103.tgz`
  (public; no auth). Installed workspace-locally (not `-g`);
  native `@github/copilot-linux-x64@1.0.103` (190 MB).
- REPRO (offline, scratch `COPILOT_HOME`, no login): `copilot --help`,
  `copilot help` (16 subcommands: app login help init config update
  version workflow sessions memories plugin mcp skill instruction lsp
  sandbox completion), `copilot version` → `GitHub Copilot CLI 1.0.103`,
  `copilot help permissions` (full pattern semantics incl. stem matching,
  deny-always-wins, protocol-aware URL patterns), `copilot help config`
  (262 lines: `defaultPermissionMode` manual/assisted/allow-all,
  `allowedUrls`/`deniedUrls`, `trustedFolders`), `copilot config --list
  --json` → `{}` exit 0, `copilot sandbox --help` (only `ca` subcommand),
  binary strings grep: no check/evaluate/dry-run/policy-test entrypoint.
- DOC (fetched 2026-10-22): docs.github.com "Allowing and denying tool
  use" (deny-always-wins incl. over `--allow-all`; `--available-tools` /
  `--excluded-tools` allowlist-wins; per-kind examples), "GitHub Copilot
  CLI configuration directory" (full `permissions-config.json` schema,
  literal-plus-`:*` matching table, settings precedence
  built-in < MDM < user < repo < local < env < flags; Managed permission
  rules: deny/ask/allow arrays, family table, union/intersection
  precedence, ask-by-default, managed floors), "Installing Copilot CLI"
  (subscription prerequisite, `/login`, PAT "Copilot Requests"),
  github.com/github/copilot-cli (install routes).
- Scratch (npm prefix, `COPILOT_HOME`, cache) wiped after the spike; all
  findings recorded here first.
