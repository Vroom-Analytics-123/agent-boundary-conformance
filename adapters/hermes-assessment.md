# Hermes — Testability Assessment (2026-10-22)

*Assessment only: no corpus evaluation, no results.json. Design-stage spike
(Wave A expansion) — NO measurement run. No account created, no login
performed, no install performed, nothing published, no outreach, no
commits.*

**Naming note (explicit):** this assesses **Hermes Agent** — Nous
Research's self-improving AI agent (`hermes` CLI, repo
`github.com/NousResearch/hermes-agent`, docs
`hermes-agent.nousresearch.com`). It is NOT the Hermes LLM/model family
from Nous Research (models, not a harness), NOT Hermes IDE
(`hermes-hq/hermes-ide`, a shell wrapper), NOT the "HERMES" modular
dev-primitives research harness (Jin et al., arXiv:2610.07832), and NOT
Hermès the luxury house. See the IDENTITY section for the full trail and
the rejected candidates.

## IDENTITY — what "Hermes" refers to

**Finding: PINNED.** In Omnigent, "Hermes" is **Hermes Agent (Nous
Research)**.

Evidence (primary sources only):

1. **Omnigent's own README glosses the name in-line** (DOC, Omnigent
   repo `github.com/omnigent-ai/omnigent`, README §"Start your first
   agent", retrieved 2026-10-22):
   `omnigent hermes                      # Hermes Agent (Nous Research)`
   — listed in the same launcher block as `omnigent claude` (Claude
   Code), `omnigent codex`, `omnigent cursor`, `omnigent opencode`,
   `omnigent pi`, `omnigent copilot`.
2. **Omnigent's agent-YAML harness vocabulary** (DOC, same README,
   "Write your own agent"): `executor.harness` accepts `hermes` and
   `hermes-native`, in the same enum as `claude-native`, `codex-native`,
   `cursor-native`, `pi-native` — i.e. Hermes is an external harness
   with both an SDK-style route (`hermes`) and a native-CLI route
   (`hermes-native`), exactly paralleling the other wrapped products.
3. **Omnigent's native-terminal wrapper list** (DOC, same README,
   prerequisites): the `omnigent <harness>` tmux wrappers are
   (`claude`, `codex`, `cursor`, `devin`, `hermes`, `kiro`, `pi`) —
   `omnigent hermes` wraps a native `hermes` terminal CLI. Hermes Agent
   is the only candidate that ships a `hermes` CLI (DOC: its README's
   quick install ends with `hermes  # start chatting!`).
4. **The upstream project matches on every checkable property** (DOC,
   NousResearch/hermes-agent README, retrieved 2026-10-22): built by
   Nous Research; binary/CLI named `hermes`; a terminal + messaging
   gateway agent with a full native toolset (terminal, files, web,
   code execution) — i.e. a harness Omnigent can orchestrate, not a
   model. An independent source-code study of harnesses (THIRD-PARTY,
   arXiv:2609.00006) likewise pairs "Hermes — Nous Research" with
   Omnigent as the meta-harness above it, corroborating the pairing.

**Confidence in the identification: high for identity purposes** (this
is an identification claim, not a measurement-confidence claim — the
measurement-confidence rule in `docs/MEASUREMENT_MODEL.md` caps
*measurement* confidence, and no measurement confidence in this dossier
exceeds medium). The pin rests on Omnigent's own explicit parenthetical
gloss, not on inference from the bare name.

**Candidates considered and rejected:**

- **Hermes models (Nous Research Hermes LLM family)** — same lab, and
  the strongest distractor. Rejected: a model has no CLI for
  `omnigent hermes` to wrap in a tmux terminal, does not appear in a
  harness enum alongside `claude-native`/`codex-native`, and Omnigent's
  gloss says "Hermes **Agent**". (DOC)
- **Hermes IDE (`hermes-hq/hermes-ide`)** — an AI shell wrapper for
  terminals (THIRD-PARTY descriptions). Rejected: no connection to
  Omnigent or Nous Research anywhere in Omnigent's primary sources;
  Omnigent's gloss names Nous Research explicitly. (DOC)
- **"HERMES" modular dev-primitives harness (Jin et al.,
  arXiv:2610.07832, Oct 2026)** (THIRD-PARTY) — a research orchestration
  harness reporting SWE-Refactor-Bench gains. Rejected: no link from
  Omnigent's repo/docs to it; Omnigent's gloss contradicts it.
- **An Omnigent-internal agent named "Hermes"** — rejected: the
  `hermes-native` variant and the native-terminal wrapper both denote
  wrapping an external product's own CLI, the same pattern as
  `claude-native`/`codex-native`. (INFERENCE on DOC)

## Surface assessed

- **Product:** Hermes Agent — Nous Research's self-improving AI agent;
  CLI binary `hermes` (plus legacy one-shot runner `hermes-agent`);
  surfaces: interactive CLI/TUI, desktop app, ACP editor integration,
  and a single messaging gateway process (Telegram, Discord, Slack,
  WhatsApp, Signal, Email, and more) (DOC: repo README).
- **Repo:** `github.com/NousResearch/hermes-agent` (public, MIT),
  main at commit `67491b50f7e5ef8be6e591d745b32758aa60c33e` as retrieved
  2026-10-22. **No version is pinned by this spike:** no install was
  performed (hard limit), so there is no binary pin. The vendor docs
  retrieved 2026-10-22 describe post-v0.21 behaviour (DOC: CLI reference
  contrasts current one-shot behaviour with "the pre-0.21 single-query
  behavior"). Third-party trackers report v0.22.4 (2026-10-21) as the
  latest release — recorded as THIRD-PARTY, **not** asserted as a pin.
- **Install route (official, not executed):**
  `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
  (Linux/macOS/WSL2); PowerShell one-liner on native Windows (DOC).
- **Docs consulted (all vendor, fetched 2026-10-22):**
  hermes-agent.nousresearch.com — "Security" (dangerous-command
  approval, hardline blocklist, `approvals.deny`, file-write safety,
  container isolation, backend comparison), "Configuration" (Smart
  Approvals, deny rules, `smart_policy`), "Tools Runtime" (developer
  guide: `DANGEROUS_PATTERNS` approval flow in `tools/approval.py`,
  terminal backends), "CLI Commands Reference" (full top-level command
  table); github.com/NousResearch/hermes-agent README;
  github.com/omnigent-ai/omnigent README (identity trail only).
- **No binary inspection:** unlike the Copilot/Muse spikes, nothing
  was installed or executed in this spike (DOC-only evidence class).
  Every claim below is DOC unless tagged otherwise.

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO**

- The full top-level CLI surface (DOC: CLI Commands Reference) is:
  `chat model moa fallback gateway proxy egress lsp setup whatsapp
  whatsapp-cloud slack auth send peer secrets migrate codex-runtime
  status usage cron pause/resume kanban project webhook hooks doctor
  security dump prompt-size debug backup checkpoints import logs
  config skin console pairing skills bundles curator journey memory
  acp mcp connectors plugins portal tools computer-use pets sessions
  insights claw import-agent dashboard serve desktop profile
  completion update uninstall` (plus `approvals`). **No
  check/evaluate/dry-run/policy-test entrypoint exists.**
- The near-misses are not oracles: `hermes approvals` only *mines
  approval history into allowlist proposals* (`hermes approvals
  suggest [--apply] [--json]`, reading the session DB); `hermes config
  check` checks for missing/stale config options; `hermes doctor`
  diagnoses config/dependencies; `hermes security audit` is an
  on-demand **supply-chain** audit (OSV.dev) of the venv/plugins/MCP
  pins; `hermes prompt-size` runs offline but reports prompt byte
  breakdown, not decisions. None answers "what does this policy decide
  for this command." (DOC)
- The decision function itself lives in-process: `tools/approval.py`'s
  `detect_dangerous_command(command)` (DOC: Tools Runtime). It is an
  internal function, not a shipped evaluation entrypoint — and it is
  only one stage of the decision (see Decision surface): in the
  **default** `smart` mode, a flagged command's outcome is decided by
  an **auxiliary LLM** (auto-approve low-risk / auto-deny risky /
  escalate uncertain), so the harness's own full decision is
  **stochastic by design** in its default configuration. There is no
  deterministic function to replay. Determinism demo is N/A.

### (b) Documented semantics precise enough for an honest reconstructed route? — **YES, for a bounded subset**

The deterministic core is documented with unusual precision across
three agreeing vendor surfaces (Security, Configuration, Tools
Runtime). What is documented precisely enough to evaluate — labelled
evaluation, never interrogation:

**1. Hardline blocklist (always-on floor).** A code-shipped list
(`tools/approval.py::UNRECOVERABLE_BLOCKLIST`) that refuses commands
**regardless of** `--yolo`/`/yolo`, `approvals.mode: off`, cron
`approve` mode, or "allow always"; it trips **before** the approval
layer and has no override flag. Documented pattern table (marked "not
exhaustive" by the vendor): `rm -rf /` and obvious variants,
`rm -rf --no-preserve-root /`, the `:(){ :|:& };:` fork bomb, `mkfs.*`
on a mounted root device, `dd if=/dev/zero of=/dev/sd*`, piping
untrusted URLs to `sh` at the rootfs top level. The floor also fails
closed on unparseable shell quoting ("malformed executable payload").
(DOC: Security)

**2. User deny rules — `approvals.deny`.** A list of **fnmatch globs**
(`*`, `?`, `[...]`), matched **case-insensitively** against the whole
command text *and* individual executable-command candidates; blocks
**unconditionally, before** `--yolo`, `/yolo`, and `mode: off` are
consulted (the user-editable counterpart of the hardline list).
Vendor worked examples: `"git push --force*"`, `"*curl*|*sh*"`,
`"dd if=* of=/dev/*"`. Matching semantics are specified in depth:
patterns run over normalized/deobfuscated variants (quoting tricks
like `git pu""sh --force` do not slip past); quote-aware parsing
exposes commands after assignments, leading redirections, `;`, `&&`,
`||`, pipelines, groups, command substitutions, and
`if`/`then`/`else`/`do`; a named launcher list (`sudo`, `env`,
`command`, `exec`, `nohup`, `setsid`, `time`, `nice`, `timeout`,
`stdbuf`, `ionice`, `chrt`, `taskset`, `chroot`) is unwrapped, with
known option operands skipped; shell `-c` payloads are inspected
**recursively**; executable candidates retain the literal path and
also match by basename (`sudo *` covers `/usr/bin/sudo -n id` and
`./sudo -n id`; a path-specific rule `/usr/bin/sudo *` does **not**
become a rule for every `sudo`). Changes take effect immediately
(mtime-keyed config cache). (DOC: Security + Configuration)

**3. Dangerous-pattern trigger table.** The patterns that trigger the
approval flow (defined in `tools/approval.py`) are tabulated row by
row (~40 rows, DOC: Security "What Triggers Approval"): `rm -r` /
`rm --recursive`; `rm ... /`; `chmod 777/666`, recursive unsafe
`chmod`; `chown -R root`; `mkfs`; `dd if=`; `> /dev/sd`; SQL
`DROP TABLE/DATABASE`, `DELETE FROM` without `WHERE`,
`TRUNCATE TABLE`; `> /etc/`; `systemctl stop/restart/disable/mask`;
`kill -9 -1`; `pkill -9`; fork bombs; `bash -c`/`sh -c`/`zsh -c`/
`ksh -c` (incl. `-lc`); `python -e`/`perl -e`/`ruby -e`/`node -c`;
`curl|wget ... | sh`; process-substitution remote scripts; `tee`,
redirection, `cp`/`mv`/`install`, `sed -i` targeting `/etc/`,
`~/.ssh/`, `~/.hermes/.env`; `xargs rm`; `find -exec rm`/`find
-delete`; hermes/gateway self-kill patterns; docker/podman lifecycle
and daemon-redirect patterns; plus two content-level shapes (a
`curl`/`wget` body carrying a secret-named variable or a credential
file; invisible/bidi Unicode controls in the command). The developer
guide corroborates the mechanism: `DANGEROUS_PATTERNS` is a list of
`(regex, description)` tuples checked by
`detect_dangerous_command(command)` before any terminal command runs
(DOC: Tools Runtime).

**4. Approval modes and context modes.** `approvals.mode` ∈
`smart` (default) | `manual` | `off` (= `HERMES_YOLO_MODE`); `manual`
prompts on every flagged command; approval **timeout defaults to
300 s and expiry denies (fail-closed)**, the expired prompt is
discarded and a timeout is not counted as a denial. Headless contexts
have their own keys, all defaulting to `deny`: `cron_mode`,
`single_query_mode`, `unattended_mode` (each `deny | approve`).
A denial circuit breaker (`approvals.denial_breaker_threshold`,
default 3) escalates repeated smart-mode denials to a hard stop.
(DOC: Security + Configuration)

**5. Permanent/session allowlist — `command_allowlist`.** "Always"
answers persist patterns to `~/.hermes/config.yaml` (exact command
text, shell-style globs like `podman *`, or dangerous-pattern rule
keys like `script execution via heredoc`) and are **silently approved
in all future sessions**; rule keys are honored even on unattended
surfaces under `deny` context modes. Session approvals are tracked
per session (approving "recursive delete" once silences that class
for the session). (DOC: Security + Tools Runtime)

**6. File-write Decision surface (separate from terminal).** Before
`write_file`/`patch` touches disk, a protected-path denylist blocks
writes **with no approval prompt and no chat-UI override**: OS
credential stores (`~/.ssh/`, `~/.aws/`, `~/.kube/`, `/etc/sudoers`,
`~/.netrc`, across every home a write can land in), Hermes secret
stores (`.env`, OAuth files, vault/, pairing/, mcp-tokens/, … under
HERMES_HOME), and Windows NT/device-namespace paths (also read-denied
on every platform). Project `.env*` files are read-denied anywhere
but writable. One documented exception: `~/.ssh/config` writes are
**approval-gated**, not hard-blocked. Optional
`HERMES_WRITE_SAFE_ROOT` hard-blocks `write_file`/`patch` outside
the listed prefixes. The vendor itself marks this
**defense-in-depth, not a hard boundary**: the `terminal` tool runs
as the same OS user and can still reach denied paths via shell.
(DOC: Security)

**7. No-match default (local/ssh backends): execute without a
prompt.** "Before executing any command, Hermes checks it against a
curated list of dangerous patterns. **If a match is found**, the user
must explicitly approve it" (DOC: Security) — an unflagged command on
the `local` (and `ssh`) backend runs with no ask. → Framework mapping:
Hermes no-match is an *execution* default, and per Revision-2
semantics / INV-005 it serializes in our reports as **unknown**,
never as an allow verdict.

**Ceilings capping the reconstructed route (gaps, all recorded):**

1. **Default mode is stochastic.** `smart` (the default) routes every
   flagged command to an auxiliary guardian LLM; `approvals.
   smart_policy` further appends owner text to that LLM's system
   prompt. A reconstructed adapter is honest only for the
   deterministic layers (hardline, `approvals.deny`, protected
   paths) and for `manual`-mode trigger outcomes. Smart-mode outcomes
   are unevaluatable — unknown with layer attribution.
2. **The full regex list is not published.** The trigger table is a
   documentation table, and the hardline table is explicitly "not
   exhaustive"; the exact `DANGEROUS_PATTERNS` /
   `UNRECOVERABLE_BLOCKLIST` regexes live in `tools/approval.py`
   source (not read in this DOC-only spike). Boundary cases may
   diverge from the table.
3. **Vendor-documented normalization limits.** Deny/pattern matching
   "does not resolve arbitrary variables (including GNU `env -S`
   `${NAME}` expansion), aliases, functions, renamed binaries,
   scripts, interpreter programs, or every shell/launcher grammar
   (for example, case-pattern syntax, clustered launcher options…)".
   The vendor's own instruction: "Do not use a basename deny rule as
   a guarantee that a capability cannot be reached by other means."
   (DOC: Security, threat-model note)
4. **Container backends skip the checks.** On `docker`, `modal`,
   `daytona`, `vercel_sandbox` (and the `singularity` plugin)
   backends, dangerous-command checks are **skipped** because "the
   container itself is the security boundary" — so the Decision layer
   is backend-dependent, and any evaluation must be scoped to
   `local`/`ssh` backends. `approvals.deny` is the documented
   exception: it "applies to all terminal backends, including
   isolated containers, before any backend-specific approval
   shortcut." (DOC: Security)
5. **`execute_code` escapes the pattern layer.** Python-level
   file/process operations inside an `execute_code` script never pass
   through the patterns; gateway sessions get one whole-script
   approval instead, while local interactive sessions under
   `manual`/`smart` get **no** whole-script approval for viewer-typed
   turns (only the script's `terminal()` calls ask). (DOC: Security)
6. **Hooks are arbitrary code.** Tool dispatch runs plugin
   `pre_tool_call` / `post_tool_call` hooks (DOC: Tools Runtime
   dispatch flow), and `config.yaml` can declare shell-script hooks
   (`hermes hooks` inspects/approves/removes them; DOC: CLI
   reference). Their effect on a decision is unevaluatable offline,
   as with every other harness's hook surface.
7. **Precedence is only partially ordered in the docs.** Documented:
   hardline and `approvals.deny` run before yolo/off and before the
   approval layer; allowlisted rule keys are honored even under
   unattended `deny` contexts. **Not** explicitly documented: the
   outcome when an `approvals.deny` glob and a `command_allowlist`
   entry both match the same command (the "unconditionally / before
   … consulted" language suggests deny wins — INFERENCE, not
   asserted), and any most-restrictive-wins rule across rule kinds.
8. **Session state is part of the decision function.** Once/session/
   always approvals, the `/yolo` session toggle (persisted with the
   session), and the denial breaker all make the same command decide
   differently across a session's life. An adapter must model the
   configured snapshot it evaluates, never a timeless policy.
9. **Version churn is fast and unpinned here.** Tagged releases ship
   roughly every two weeks (THIRD-PARTY cadence reports); an earlier
   bundled external scanner (Tirith) was **removed** in a later
   release and its `security.tirith_*` settings silently dropped —
   documented proof that this surface changes underfoot (DOC:
   Security). The pin is load-bearing and this spike has none.

### (c) Surface record — N/A (harness is reconstructed, not no-paper-surface)

## Decision surface

What the rules decide about a command, per backend scope
(`local`/`ssh` unless stated):

- **Stage 0 — parse floor:** unparseable shell quoting fails closed
  ("malformed executable payload"); nothing runs. (DOC)
- **Stage 1 — hardline blocklist:** fixed code-shipped patterns →
  **forbidden**, no override, before everything else. (DOC)
- **Stage 2 — `approvals.deny` globs:** owner-authored fnmatch →
  **forbidden** (BLOCKED error, "do not retry or rephrase"); applies
  on all backends incl. containers. (DOC)
- **Stage 3 — allowlist:** `command_allowlist` (exact / glob / rule
  key) and per-session pattern approvals → silently approved. (DOC)
- **Stage 4 — dangerous-pattern detection:** trigger-table match →
  outcome depends on mode: `manual` → **prompt**; `smart`
  (default) → **guardian-LLM decision** (approve once / deny /
  escalate to prompt); `off`/yolo → executes (Stages 1–2 still
  apply). Headless contexts substitute `cron_mode` /
  `single_query_mode` / `unattended_mode` (default `deny` →
  forbidden-in-context). Prompt timeout (300 s default) → **deny**.
  (DOC)
- **Stage 5 — no match:** executes without a prompt (execution
  default; framework-serialized as **unknown**, never allow). (DOC +
  framework rule)
- **Separate tool surface:** `write_file`/`patch` protected-path
  denylist → **forbidden** with no prompt path; `HERMES_WRITE_SAFE_ROOT`
  prefix confinement; `~/.ssh/config` exception → prompt. File-tool
  guards do not bind the terminal tool (vendor-stated). (DOC)
- **Also documented:** a non-overridable supervised-gateway lifecycle
  guard (the terminal tool refuses gateway stop/restart and
  interpreter-image kills even under approval, yolo, or `force=True`);
  website blocklist (`security.website_blocklist`: exact / wildcard-
  subdomain / TLD-wildcard domains) rejecting URLs before web/browser
  tools run; always-on SSRF/private-address guard for URL-capable
  tools (fail-closed on DNS failure); content-level secret-in-command
  and invisible-Unicode flags routed into the normal approval flow.
  (DOC)

## Approval machinery

- **The ask, CLI:** inline dialog — `[o]nce | [s]ession | [a]lways |
  [d]eny`, deny the default choice; the answer's scope (once /
  session-pattern / permanent allowlist) is part of the machinery.
  (DOC)
- **The ask, gateway:** the command details are sent to the messaging
  chat; approve by replying `yes/y/approve/ok/go`, deny by
  `no/n/deny/cancel`; on WhatsApp, native ✅ Approve / ❌ Deny buttons.
  `HERMES_EXEC_ASK=1` is set in gateway runs. The API-server surface
  can also answer via `POST /v1/runs/{id}/approval` where the client
  supports it. (DOC)
- **Who may be asked / who may talk:** gateway user authorization is
  a separate, documented layer — per-platform allowlists, global
  allowlist, DM pairing codes (8-char, 1-hour TTL, rate limits,
  lockout), **default deny when nothing is configured**. (DOC)
- **Configured posture (A2 material):** `approvals.mode`, `timeout`,
  `cron_mode`, `single_query_mode`, `unattended_mode`,
  `mcp_reload_confirm`, `destructive_slash_confirm`,
  `denial_breaker_threshold`, `smart_policy`, `approvals.deny`,
  `command_allowlist`, `--yolo` / `/yolo` / `HERMES_YOLO_MODE=1`.
  (DOC)
- **Recorded posture (A4 material):** executed approved commands are
  recorded in the session DB (`~/.hermes/state.db`) — `hermes
  approvals suggest` mines exactly that record; logs live under
  `~/.hermes/logs/` with secrets auto-redacted. No A4 evidence was
  accessed in this spike. (DOC)

## Effect surface

- **Terminal backends (the effect environment):** `local` (no
  isolation, checks on), `ssh` (remote machine, checks on), `docker`
  / `modal` / `daytona` / `vercel_sandbox` / `singularity` plugin
  (isolated, dangerous-command checks **skipped** — the container is
  the boundary). Docker hardening is documented flag-by-flag
  (`--cap-drop ALL` + minimal adds, `no-new-privileges`, pids-limit
  256, sized tmpfs; resource limits and persistent-vs-ephemeral
  filesystem modes in `terminal:` config). (DOC)
- **Credential hygiene at effect time:** `execute_code` and
  `terminal` strip sensitive env vars from children (name-pattern
  filtering for `execute_code`; explicit Hermes-infrastructure
  blocklist for local terminal; **no host env by default** in
  Docker/SSH/Modal), with skill-declared and config-declared
  passthrough as the only documented openings; MCP subprocesses get
  a safe-vars-only environment (PATH, HOME, USER, LANG, LC_ALL,
  TERM, SHELL, TMPDIR, XDG_*) plus their server-config `env`. (DOC)
- **Checkpoints:** optional pre-destructive-operation filesystem
  snapshots (`checkpoints.enabled`, default false; `hermes chat
  --checkpoints`), with `~/.hermes/checkpoints/` inspectable via
  `hermes checkpoints` — a harness-native before/after record that a
  future Effect route could cross-check, not an Effect measurement.
  (DOC)
- **Self-report caveat:** the vendor warns the model "may still claim
  the edit succeeded" for blocked writes, and ships a
  `display.file_mutation_verifier` footer (default on) to be trusted
  over the assistant's summary — a documented instance of why E4
  (agent self-report) is never sufficient alone. (DOC)
- **No Effect measurement exists.** E1/E2 remain protocol-locked
  design in this program; nothing ran.

## Per-layer route assignment

| Layer | Route | Confidence | Basis |
|---|---|---|---|
| Decision | **reconstructed** (D2; D1 vendor-confirmed: no; D3 cross-check: n/a — no second route to agree) | **medium** | No offline oracle (DOC: full CLI table), but hardline table, `approvals.deny` fnmatch + normalization semantics, the ~40-row trigger table, modes/defaults, and protected-path rules are documented precisely and agree across three vendor surfaces (Security, Configuration, Tools Runtime). Medium — not higher — because: the default `smart` mode is a stochastic guardian LLM (excluded from evaluation), the full regex lists are unpublished ("not exhaustive"), and no binary was inspected. Confidence attaches to OUR verdict about the deterministic subset (`manual` mode + hardline/deny/protected-path layers, local/ssh backends), never to the harness. |
| Approval | A1 Promised: **applicable** (a `manual`-mode flagged Decision owes an ask; in `smart` mode the promise is conditional on guardian escalation) · A2 Configured: **applicable** (full `approvals.*` + allowlist + yolo posture readable from `~/.hermes/config.yaml` / docs) · A3 Witnessed live (KEYSTONE): **not done — blocked** (see LIVE-UNLOCK) · A4 Recorded: **applicable in principle** (session DB + logs; `hermes approvals suggest` mines them; none accessed) | **low** | Only A1 (derived expectation) and A2 (documented configuration) routes exist, and A1 is by doctrine "an expectation, not an Approval measurement." No route has been exercised; the keystone (A3) has not taken place. One agreeing route at most → low. |
| Effect | E1 Sentinel state: **applicable by protocol design, not run** · E2 Sandbox diff: **applicable by protocol design, not run** (docker backend's persistent/ephemeral modes and checkpoints give it purchase) · E3 System trace: **proposed only** · E4 Agent self-report: **applicable but never sufficient alone** (vendor's own file-mutation-verifier warning is the standing caution) | **low** | No live change has been observed (no run of any kind). Zero exercised routes → the layer is unread by measurement; "low" records that the routes are designed and the surface is documented, not that any evidence exists. |

**Route: reconstructed — config evaluation.** (Provenance of the
Layer-1 measurement only; unranked — ease of measurement never makes
a harness better or worse.) An honest adapter evaluates the
deterministic decision stages (hardline → deny globs →
protected paths → `manual`-mode trigger table) against the shared
invariants, labels every result evaluation, scopes every verdict to
the `local`/`ssh` backends and to a named configuration snapshot
(mode, deny list, allowlist, session state), and treats smart-mode
guardian outcomes, hooks, and container-backend execution as
unevaluatable — unknown with layer attribution, never a verdict.

## LIVE-UNLOCK

LIVE-UNLOCK: live Approval (A3) and Effect (E1/E2) measurement requires an installed Hermes Agent (curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash) plus ONE model-provider credential — either a Nous Portal subscription via OAuth (hermes setup --portal / hermes auth add) or a provider API key in ~/.hermes/.env (e.g. OPENROUTER_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY); gateway-mode approval witnessing additionally requires a messaging-platform bot token (e.g. TELEGRAM_BOT_TOKEN) and an allowlisted user ID. The Hermes software itself is MIT-licensed and needs no subscription.

## Open questions (what would resolve them)

1. **Full `DANGEROUS_PATTERNS` / `UNRECOVERABLE_BLOCKLIST` regexes**
   — the docs tabulate categories and mark the hardline list "not
   exhaustive." *Would resolve:* reading `tools/approval.py` in the
   pinned repo source (a repo-source pass, not done in this DOC-only
   spike), or a vendor-published complete list.
2. **A pinned version + binary/source pin** — this spike assessed
   moving docs with no install. *Would resolve:* installing Hermes
   Agent at a tagged release in a scratch dir (an install step,
   outside this spike's hard limits) and re-running the (a)-spike
   read-only (`hermes --help`, CLI table diff).
3. **Deny-vs-allowlist precedence** — what wins when an
   `approvals.deny` glob and a `command_allowlist` entry both match?
   *Would resolve:* vendor documentation of the stage order, or a
   live A3/A4 probe behind the LIVE-UNLOCK.
4. **Whether `detect_dangerous_command` could serve as a partial
   vendor-confirmed route** — it is the vendor's own code, but it is
   an internal function covering only the detection stage, and the
   full decision in default mode is guardian-LLM-mediated.
   *Would resolve:* a program decision on whether importing vendor
   source (unshipped as an entrypoint, version-unpinned) can ever
   count as D1; the standing promotion condition (a shipped offline
   evaluator at a pinned version) says no today.
5. **Smart-mode guardian behaviour** — which auxiliary model reviews,
   with what prompt (beyond owner `smart_policy` appends), and with
   what variance? *Would resolve:* nothing offline — by design an
   Approval-layer stochastic mechanism; document, never evaluate as
   an oracle.
6. **Omnigent-side wiring** — does Omnigent's `hermes` /
   `hermes-native` harness pin or require a specific Hermes Agent
   version, and does it drive the CLI, the ACP server
   (`hermes acp`), or the gateway API? *Would resolve:* reading
   Omnigent's harness implementation for `hermes` in its repo (the
   identity trail in this spike stopped at its README/docs gloss,
   per the spike's primary-source scope for identity).

## Blockers

- **No live decision was (or could be) observed:** any session needs
  an install plus a model-provider credential (LIVE-UNLOCK); this
  spike's hard limits forbade installs, accounts, and logins. All
  findings are DOC.
- **Stochastic default in the decision path:** `approvals.mode:
  smart` is the default and its guardian LLM "is not deterministic"
  in effect — even with an account, a Codex-style vendor-confirmed
  replay is not achievable in the default configuration; the honest
  evaluation target is `manual` mode + the deterministic stages.
- **Backend-dependent Decision layer:** container backends skip
  dangerous-command checks entirely, so no single Decision verdict
  can be stated for "Hermes" without a backend scope.
- **Unpinned surface:** releases ship on a roughly two-week cadence
  and documented features have been removed between releases
  (Tirith); without a version pin, every reconstructed evaluation
  risks evaluating a policy surface that has already moved.

## Evidence log

- DOC (fetched 2026-10-22) — **Identity:** github.com/omnigent-ai/
  omnigent README: harness list ("common orchestration layer over
  Claude Code, Codex, Cursor, OpenCode, Hermes, Pi…"); launcher block
  `omnigent hermes  # Hermes Agent (Nous Research)`; agent-YAML
  harness enum (`hermes`, `hermes-native`, alongside `claude-native`,
  `codex-native`, `cursor-native`, `pi-native`); native tmux wrapper
  list (`claude`, `codex`, `cursor`, `devin`, `hermes`, `kiro`,
  `pi`); `omnigent run` installs "the coding-harness CLIs" via npm/
  Node prerequisites note.
- DOC (fetched 2026-10-22) — github.com/NousResearch/hermes-agent
  README: "The self-improving AI agent built by Nous Research"; MIT;
  CLI `hermes` (chat/model/tools/config/gateway/setup/update/doctor);
  six terminal backends (local, Docker, SSH, Modal, Daytona, Vercel
  Sandbox + Singularity plugin); gateway platforms (Telegram,
  Discord, Slack, WhatsApp, Signal, CLI); Nous Portal OAuth route
  (`hermes setup --portal`); docs index pointing to
  hermes-agent.nousresearch.com. Repo main commit
  `67491b50f7e5ef8be6e591d745b32758aa60c33e` as retrieved.
- DOC (fetched 2026-10-22) — hermes-agent.nousresearch.com "Security":
  eight-layer model; approval modes table + all `approvals.*` keys
  with defaults (timeout 300, cron/single_query/unattended `deny`);
  YOLO three activation routes and its hardline exception; hardline
  blocklist table ("not exhaustive", `UNRECOVERABLE_BLOCKLIST`) +
  malformed-quoting fail-closed; `approvals.deny` full semantics
  (fnmatch, case-insensitive, candidate extraction, launcher list,
  `-c` recursion, basename rule, threat-model limits verbatim);
  approval timeout fail-closed; "What Triggers Approval" table
  (~40 rows); container-bypass note; `execute_code` whole-script
  rules incl. the local-session exemption; CLI approval flow
  (once/session/always/deny); gateway reply vocabulary;
  `command_allowlist` persistence + rule-key honoring on unattended
  surfaces + load-time caveat; `hermes approvals suggest` mining
  rules (destructive classes never proposed, credential masking);
  file-write protected paths (always-blocked table, `.env`
  read-denied, `~/.ssh/config` approval-gated exception,
  `HERMES_WRITE_SAFE_ROOT`, defense-in-depth warning,
  file-mutation verifier); gateway authorization order + pairing;
  Docker hardening flags + resource config; backend comparison table
  (checks skipped on container backends); env-passthrough filtering
  tables; MCP safe-vars; website blocklist; SSRF guard; content-level
  secret/Unicode flags; Tirith removal note.
- DOC (fetched 2026-10-22) — hermes-agent.nousresearch.com
  "Configuration": directory layout (`~/.hermes/config.yaml`, `.env`,
  `auth.json`, sessions/, logs/); config precedence (CLI >
  config.yaml > .env > built-in defaults); Smart Approvals table
  (smart = auxiliary LLM, default; manual; off = YOLO-equivalent);
  denial breaker (default 3); `approvals.deny` examples
  (`git push --force*`, `*curl*|*sh*`); `approvals.smart_policy`
  (appended to guardian LLM system prompt); checkpoints config;
  website-blocklist policy caching.
- DOC (fetched 2026-10-22) — hermes-agent.nousresearch.com "Tools
  Runtime" (developer guide): `DANGEROUS_PATTERNS` approval flow
  (regex/description tuples in `tools/approval.py`,
  `detect_dangerous_command`, CLI prompt vs gateway callback vs
  smart approval, per-session approval state, permanent allowlist
  writes to `command_allowlist`); dispatch flow with plugin
  `pre_tool_call`/`post_tool_call` hooks; terminal backend list;
  process-result receipts under `logs/process-results/` with forced
  redaction.
- DOC (fetched 2026-10-22) — hermes-agent.nousresearch.com "CLI
  Commands Reference": full top-level command table (no
  check/evaluate/dry-run/policy entrypoint); `--yolo` global flag
  ("Bypass dangerous-command approval prompts"); `hermes approvals`
  = "Approval-prompt tools — mine approval history into allowlist
  proposals"; `hermes prompt-size` "Runs offline" (prompt breakdown,
  not decisions); `hermes security audit` = supply-chain (OSV.dev);
  chat `--checkpoints`, `--ignore-user-config`, `--safe-mode` flags.
- THIRD-PARTY (corroboration only, never load-bearing): arXiv
  2609.00006 harness study (Hermes = Nous Research, Python, hybrid
  personal/SWE harness; Omnigent as meta-harness wrapping Hermes);
  release trackers reporting v0.22.x as current (v0.22.4, 2026-10-21)
  — recorded, not asserted as a pin.
- No installs, no executions, no logins, no accounts: this spike is
  DOC-only by design (contrast the Copilot/Muse spikes, which add
  REPRO from offline binary inspection).
