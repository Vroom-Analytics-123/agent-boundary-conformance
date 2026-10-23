# Omnigent — Testability Assessment (2026-10-22)

*Design-stage dossier — survey assessment only. NO measurement run: no
corpus evaluation, no results.json, no install, no live agent run, no
account created, no login performed, nothing published, no outreach, no
commits. Every verdict-shaped statement below is a route assignment or a
documented-semantics reading, never a measurement.*

**Naming / scope note (explicit):** this assesses **Omnigent** — the
open-source (Apache-2.0) **meta-harness** from the Databricks AI team /
Neon contributors, repo `github.com/omnigent-ai/omnigent`, site
`omnigent.ai`. Omnigent is not a harness in the same sense as the rest of
the programme's set: it sits **above** Claude Code, Codex, Cursor,
OpenCode, Hermes, Pi and custom YAML agents and orchestrates them, with
its own policy layer on top. That two-level structure is assessed as
such throughout — an Omnigent Decision is a decision *about an
underlying harness's action*, taken at the meta-harness layer. It is NOT
any single underlying harness, and nothing here measures one.

## Surface assessed

- **Product:** Omnigent — open-source AI agent framework and
  meta-harness (REPRO: repo README, `github.com/omnigent-ai/omnigent`).
  Harnesses orchestrated (DOC/REPRO, README): Claude Code, Codex,
  Cursor, OpenCode, Hermes, Pi, Copilot, Antigravity, plus custom agents
  defined in YAML; executor harness ids include `claude-sdk`,
  `claude-native`, `codex`, `codex-native`, `cursor`, `cursor-native`,
  `hermes`, `opencode`, `pi`, `pi-native`, `openai-agents`.
- **Version / pin:** `omnigent` **0.19.1** — PyPI release files
  (`omnigent-0.19.1.tar.gz`, wheel) uploaded **2026-10-21** (DOC: PyPI
  project page release listing). The vendor docs site and the repo
  documentation were consulted at repo `main`, current commit
  `29732f8be9aec1f209f89afedb02eccde07708c6` (REPRO: repo page) — **main
  may be ahead of the 0.19.1 release**, and the custom-policies doc
  itself records a behaviour change "starting in 0.19.0", so the pin is
  load-bearing. The project self-describes as **alpha** (REPRO: README
  status badge).
- **Sources consulted (all retrieved 2026-10-22, primary only):**
  omnigent.ai "Contextual Policies" (policy overview), "Builtin
  Policies", "Custom Policies", "Install" quickstart; GitHub repo
  README; repo `docs/POLICIES.md` (the in-repo policy guide, read in
  full); PyPI `omnigent` project page (release listing). Third-party
  summaries were used only to *locate* these primary sources, never as
  evidence; where a load-bearing claim rests on a third party it is
  tagged (THIRD-PARTY) and treated as unverified.

## Method / no-run note

Unlike the Copilot and Muse Code spikes, **no binary was installed or
executed in this spike** — the wave's hard rules (no live agent runs, no
accounts, no logins) plus the design-stage framing keep this a
documentary survey. Consequence, stated plainly: spike answer (a) below
is a **DOC-scope NO** — no oracle entrypoint exists in any documented
CLI, REST, or config surface consulted — not a binary-inspection NO of
the kind the Copilot spike produced. A pinned-install `--help` / package
inspection is the named step that would harden it (see Open questions).

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO** (DOC-scope)

- No `check` / `evaluate` / `test` / `dry-run` policy entrypoint appears
  in any primary surface consulted: the repo README's full command
  surface (`omnigent run`, `server`, `host`, `start`, `stop`, `attach`,
  `login`, `setup`, `config set`, `sandbox create|connect`, `upgrade`,
  `uninstall`, per-harness launchers) contains no policy-decision
  command (REPRO: README, read in full); the policy docs describe
  exactly three ways policies are *applied* — chat (`sys_add_policy`),
  YAML declaration, REST management — and none that *queries* a decision
  (DOC: policy overview; REPRO: `docs/POLICIES.md`).
- The documented REST surface is runtime **management**, not evaluation:
  `POST|GET|PATCH|DELETE /v1/policies` and `GET /v1/policy-registry`
  (create/list/update/remove server-wide policies; list the discoverable
  registry with parameter schemas) — no evaluate/test endpoint is
  documented (DOC: policy overview REST table; REPRO: `docs/POLICIES.md`
  appendix).
- Two structural reasons a vendor-confirmed route cannot be read off
  this surface even in principle (INFERENCE on DOC+REPRO): **(1)
  statefulness** — a policy verdict is a function of the event *plus*
  accumulated session state (tool-call counts, spend, risk score,
  labels, read-history), so "(policy, command) → verdict" is undefined
  without a specified session state; **(2) stochastic evaluators** —
  several builtins decide via a server LLM (`prompt_policy`,
  `intent_based_authorization`, `detect_task_switch`,
  `deny_trivial_to_expensive_model`), which is not a deterministic
  function of config. A future adapter could *execute* vendor code
  (import builtin handlers, feed synthetic `PolicyEvent`s with a
  declared session state) — that would still be a **reconstructed**
  route (our harness drives it), never vendor-confirmed, because no
  vendor entrypoint takes (policy, command) and returns the harness's
  own verdict.
- Determinism demo is N/A: there is no decision function to replay.

### (b) Documented semantics precise enough for an honest reconstructed route? — **YES, for a named subset**

The Decision-layer semantics are specified in two primary sources that
agree on the core (DOC: policy overview + builtin/custom policy pages;
REPRO: `docs/POLICIES.md`):

- **Verdict vocabulary:** every policy returns **ALLOW**, **ASK**, or
  **DENY**, or abstains (`None`). Abstain is documented as equivalent to
  ALLOW for aggregation ("Returning `None` is treated as abstain
  (equivalent to `{"result": "ALLOW"}`)" — DOC: Custom Policies
  reference).
- **Aggregation:** "If any policy returns a DENY decision, the action is
  blocked; otherwise, if any policy returns an ASK decision, the action
  waits for your approval; otherwise, it proceeds" (DOC: overview).
  Repo form: policies are evaluated in declaration order and "a DENY
  from any policy short-circuits the rest" (REPRO: `docs/POLICIES.md`).
- **Stacking / precedence across levels:** three levels, all enforced
  simultaneously, evaluated **session → Omnigent config (agent) →
  server-wide** (session first, server last) (DOC: overview level
  table; REPRO: `docs/POLICIES.md` trust model). Note the trap: the
  README's phrase "the stricter session rules checked first" describes
  *evaluation order*, not a precedence operator — a session ALLOW does
  not override a later server DENY, because any DENY blocks (INFERENCE
  on DOC+REPRO).
- **Event model (the phases):** policies receive a `PolicyEvent` at
  four documented event types — `request`, `tool_call`, `tool_result`,
  `response` — with a fully tabulated schema (`type`, `target`,
  `data{name, arguments}`, `context{actor, usage, model, harness,
  labels}`, `session_state`, `request_data`) and a tabulated
  `PolicyResponse` schema (`result`, `reason`, `data` replacement
  payload, `state_updates`, `set_labels`) (DOC: Custom Policies
  reference; REPRO: `docs/POLICIES.md` event/response examples).
- **Authoring forms:** (i) YAML `policies:` blocks naming builtin or
  custom Python handlers (`type: function`, `handler: <dotted path>`,
  `factory_params:`; server-wide form `function: {path, arguments}`);
  (ii) **CEL** via the `cel_policy` builtin — a non-Turing-complete
  expression over the event, returning ALLOW/ASK/DENY plus optional
  `state_updates`; (iii) **custom Python policies** (plain callables or
  factories) registered via `policy_modules` + a `POLICY_REGISTRY`
  export; (iv) **plain-language assembly** — in chat, the user describes
  a rule, the agent picks a policy from the registry, configures it,
  and asks for approval before it takes effect (DOC: overview). Only
  (i)–(iii) are evaluatable surfaces; (iv) is an authoring convenience
  whose *output* is one of (i)–(iii).
- **Defaults:** with no policy opining, the action **proceeds** — the
  opposite default from most of the programme's harnesses. The only
  exceptions are two always-on, non-removable approval guards appended
  to every session (see Approval machinery). → Framework mapping: a
  no-opinion outcome is **not** an explicit ALLOW decision; an adapter
  must serialize "no policy matched/opined" as **unknown** (INV-005),
  never as allow.
- **Named builtins with documented parameters** relevant to the
  catalogue: `ask_on_os_tools`, `blast_radius` (shell classification:
  safe / risky→ASK-or-DENY / catastrophic→always DENY, e.g. `rm -rf /`,
  force-push; `gate_pushes` default true), `github_policy`
  (`write_repos`, `write_branches`, destructive ops denied by default,
  force-push denied by default incl. bundled `-f` flags and `+refspec`),
  `block_working_dir_changes` (parses chained/wrapped commands),
  `worktree_guard`, `read_only_os`, `enforce_sandbox`, `max_tool_calls_per_session`,
  `cost_budget` / `user_daily_cost_budget` / `user_period_cost_budget`
  (ASK at soft thresholds, downgrade-gate DENY at the hard limit),
  `deny_pii_in_llm_request`, `gdrive_policy` (incl. Bell-LaPadula
  no-write-down), `gmail_policy`, `gcalendar_policy`, `risk_score_policy`,
  `detect_loop`, `detect_thrashing`, `block_skills`, `spawn_bounds`
  (DOC: Builtin Policies; REPRO: `docs/POLICIES.md`).

**Ceilings capping the reconstructed route (gaps, all recorded):**

1. **No offline oracle** — everything above is DOC+REPRO of documents,
   never interrogation; and per (a), answer (a) is DOC-scope only.
2. **State dependence** — verdicts for stateful builtins are only
   evaluatable against an explicitly constructed session state; a
   reconstructed adapter must declare the state it assumes (fresh
   session is the honest default) or its verdicts are unfalsifiable.
3. **`blast_radius` classification table is not published** — the docs
   give the three tiers and examples (`rm -rf /`, force-push) but not
   the full classification rules, so per-command verdicts from this
   builtin are **not** reconstructible from docs alone.
4. **CEL return-contract inconsistency in the vendor's own docs** —
   the Builtin Policies page says a `cel_policy` expression returns a
   map with a `result` key and that a non-map return *abstains*; the
   Custom Policies page says "Return `true` to deny the action" and its
   first examples are boolean expressions. The two pages also give two
   different handler paths (`omnigent.policies.builtins.cel.cel_policy`
   vs `omnigent.policies.builtins.safety.cel_policy`). Until the vendor
   resolves this, CEL translations are drafted against the map form
   (the more fully specified of the two) and the inconsistency is
   carried as an open question.
5. **LLM evaluators are stochastic and partly fail-open** —
   `prompt_policy` interprets a model's reply as ALLOW/ASK/DENY;
   `intent_based_authorization` "fails open when none [no `llm:` config]
   is available"; `detect_task_switch` likewise fails open. These are
   unevaluatable as Decision oracles — unknown with layer attribution.
6. **Per-domain shell parsers, not a general compound semantics** —
   `github_policy` and `block_working_dir_changes` document segment-wise
   parsing for *their* domains (comments, here-documents, substitutions
   are "not classified"; unsupported syntax adds an ASK). No general
   documented semantics exists for how arbitrary compound/wrapped
   commands are seen by arbitrary policies — a policy receives the
   whole command string as one `tool_call` event.
7. **Version drift** — docs consulted are `main`-branch; the pin is
   0.19.1. Sibling cost policies document opposite `[]` semantics for
   `expensive_models` (repo `docs/POLICIES.md` on `cost_budget`: `[]`
   disables the hard limit; the website's `user_period_cost_budget`
   text: omit or `[]` for a true hard stop) — a documentation trap to
   verify per policy before authoring anything cost-shaped.

### (c) Surface record — N/A (harness is reconstructed, not no-paper-surface)

## Decision surface

Policies intercept **every** action at the meta-harness layer — tool
calls, LLM requests (`request` phase), file operations — and decide in
real time (DOC: overview). What a policy actually *sees*, per the
documented event schema: on `tool_call`, the tool name and its arguments
dict — for Omnigent's own OS tools the documented shapes are
`sys_os_shell` with `arguments.command` (the full command **string**;
REPRO: `docs/POLICIES.md` worked event example, `"command": "rm -rf
/tmp/data"`), `sys_os_read` / `sys_os_write` / `sys_os_edit` with
`arguments.path` (DOC: Custom Policies CEL example). For underlying
harnesses, the one builtin that documents cross-harness coverage is
`blast_radius`: "Covers the shell tool across Omnigent (`sys_os_shell`),
Claude/Codex (`Bash`), Cursor, Pi, Hermes, and Goose" (DOC: Builtin
Policies) — i.e. in runner-relayed sessions, the underlying harness's
shell tool calls surface to Omnigent policies under their native tool
names. MCP tools surface by name prefix (`github_policy` matches
`mcp__github__` / `github__`; the Google policies likewise) (REPRO:
`docs/POLICIES.md`). File edits by underlying harnesses surface as their
own tool calls in relayed sessions; whether a *native TUI wrapper*
session (below) emits the same events is **not established** by the
sources consulted. Post-tool, `tool_result` events and the `response`
phase let policies observe outcomes and gate assistant text before it
is persisted/delivered — but "post-tool policies cannot undo an action
that has already happened" (DOC: overview). There is **no agent-start
policy phase**: the `enforce_sandbox` start probe is a synthetic
`sys_agent_start` tool-call replay whose DENY/ASK verdicts are "logged
and ignored" — only its transform takes effect, and the runner fails
closed (refuses to start) only when a policy cannot be evaluated at all
(REPRO: `docs/POLICIES.md`).

**Two-level governance interplay.** The Omnigent layer is the operative
Decision layer for actions it relays: its verdicts are ALLOW/ASK/DENY
over the underlying harness's tool calls, and its sandbox (below)
confines whatever executes. The underlying harness's *own* native
policy (Claude Code permissions, Codex execpolicy, …) is a second,
independent layer. What the primary sources consulted establish: the
underlying harness still runs (Omnigent orchestrates the real CLIs/SDKs),
and at least the Devin and Kiro native integrations mirror the
*harness's own* `PermissionRequest` approvals into Omnigent's UI (REPRO:
README) — evidence that harness-native approval machinery remains alive
under Omnigent for those integrations. What the sources do **not**
establish: whether Omnigent launches SDK/native harnesses with their
native approvals intact, configured, or bypassed in favour of its own
layer; and whether `tool_call` policy events fire for the tmux/PTY
native-wrapper sessions (`omnigent claude`, `omnigent codex`, …) as
they do for relayed sessions. Both are open questions below — the
honest summary is: **Omnigent's layer observes what its runner relays;
the native layer's posture under Omnigent is undocumented in the
sources consulted** (INFERENCE on DOC+REPRO). A third-party integrator
repo claims a headless seam passes bypass-style flags to Claude/Codex
(THIRD-PARTY — used only to frame the open question, never as evidence).

## Approval machinery

- **The ASK verdict is the approval primitive:** "the action is paused
  for user approval; approved becomes ALLOW, refused becomes DENY"
  (REPRO: `docs/POLICIES.md`). The policy's `reason` is shown to the
  user on ASK (DOC: Custom Policies, PolicyResponse reference).
- **Transactional state:** `state_updates` from a policy result are
  applied on ALLOW and DENY but **withheld on ASK pending approval** —
  an approval is what commits the policy's state change (DOC: Custom
  Policies).
- **Remembered approvals (scoped, documented):** cost policies ASK only
  the *first* time a soft threshold is crossed — per session
  (`cost_budget`), per user per UTC day (`user_daily_cost_budget`), or
  per user per period (`user_period_cost_budget`, whose checkpoint
  approvals persist across that user's sessions for the period) (DOC:
  Builtin Policies; REPRO: `docs/POLICIES.md`).
- **Two always-on guards** are appended to every session (including
  sub-agent sessions), take no parameters, and cannot be removed:
  `ask_on_add_policy` (ASK before `sys_add_policy` — an agent cannot
  silently install a session policy; this is also the approval step for
  plain-language policy assembly) and `ask_on_scheduled_task_change`
  (ASK before creating/updating scheduled tasks) (DOC: Builtin
  Policies).
- **Approval surfaces:** the web UI (session settings/info panels;
  approval cards — documented at least for Devin's mirrored
  `PermissionRequest` and Kiro's one-time approvals), the embedded
  terminal for native wrappers (Kiro approvals "stay answerable in the
  embedded Terminal"), and chat (REPRO: README; DOC: overview).
- **Not documented in the sources consulted (unknowns, not gaps to
  fill):** any timeout/expiry for a pending ASK; who may approve in a
  shared or co-driven session (owner only? any collaborator?); whether
  an approval can be granted "always" for a class of actions beyond the
  cost-checkpoint memory above; whether approvals are written to a
  retrievable audit record with approver identity (the event schema
  carries `actor.run_as` / `actor.client_id` for the *session's* actor,
  which is suggestive but is not a documented approval log).

## Effect surface

No Effect measurement exists or is claimed; this records what the
surface *would* let a future live protocol observe, and what confines
effects in the meantime.

- **Observation points:** `tool_result` events (policies such as
  `detect_thrashing` and `detect_loop` are built on them) and the
  `response` phase (in runner-relayed sessions policies run before each
  text segment is persisted) give the meta-harness a native record of
  what the underlying harness did and said (DOC: Custom Policies;
  REPRO: `docs/POLICIES.md`). DENY reasons are logged (DOC: Custom
  Policies). This is policy-visible reporting — at best route E4-grade
  evidence about effects, never a substitute for observing the effect
  itself.
- **OS sandbox (the real Effect confinement):** native terminal
  wrappers and the `pi` harness run each agent terminal in an OS
  sandbox — `bubblewrap` (`bwrap`) on Linux, where it is **mandatory**
  (a missing `bwrap` binary makes those terminals fail to start), and
  the built-in `seatbelt` sandbox on macOS; the L7 egress proxy is part
  of the Linux/macOS stack and, like the sandbox, is **not available on
  Windows**, where agents run under a Windows Job Object (process-tree
  containment and resource limits only — no filesystem or network
  isolation) (REPRO: README). `enforce_sandbox` can force a sandbox
  configuration at agent start: `sandbox_type` (`linux_bwrap` /
  `darwin_seatbelt` / `none`), `allow_network`, `write_paths` (incl.
  disposable copy-on-write entries), `read_paths` (DOC: Builtin
  Policies; REPRO: `docs/POLICIES.md`). Agent CLIs are spawned with a
  **deny-by-default environment** — a shared base plus the harness's
  own variable family; another provider's host secret is not inherited
  unless declared via `env_passthrough` (REPRO: `docs/POLICIES.md`).
  Cloud sandboxes (Modal, Daytona, Blaxel, Islo, E2B, Gensee,
  CoreWeave, Kubernetes, OpenShell, Boxlite, microsandbox, Databricks)
  are available per session as managed hosts (REPRO: README).
- **Consequence for measurement:** the sandbox + copy-on-write write
  paths are exactly the containment a live protocol needs — sentinel
  assets (E1) and before/after diffs (E2) are *applicable by design*
  against a sandboxed or cloud-sandbox session. Neither has been run.
  No OS-level trace route (E3) is documented; agent self-report (E4)
  exists via `tool_result`/`response` but is never sufficient alone.

## Per-layer route assignment

Confidence below attaches to **our** measurement (per
`docs/MEASUREMENT_MODEL.md`), never to Omnigent. Nothing was measured;
"medium" appears once, justified in the basis column.

| Layer | Route | Confidence | Basis |
|---|---|---|---|
| Decision | **reconstructed** (D2; D1 vendor-confirmed: none exists; D3 cross-check: N/A until an adapter runs) | **medium** | Verdict vocabulary (ALLOW/ASK/DENY + abstain≡ALLOW), aggregation (any-DENY blocks, else any-ASK pauses), level order (session → agent → server, DENY short-circuits), the full PolicyEvent/PolicyResponse schemas, and the parameters of the catalogue-relevant builtins are documented precisely and consistently across two independent primary surfaces (omnigent.ai policy docs + repo `docs/POLICIES.md`). Capped at medium — never high, nothing measured — by: state dependence of verdicts, the unpublished `blast_radius` classification table, the CEL return-contract inconsistency, stochastic LLM evaluators, and the DOC-scope (not binary-inspected) oracle answer. |
| Approval | A1 promised — applicable (a Decision of ASK owes an ask; derived expectation only, not a measurement). A2 configured — applicable (ASK-bearing policies, thresholds, and the always-on guards are readable from agent YAML / server config / `GET /v1/policies`). A3 witnessed-live (keystone) — **not run** (no live run in this spike). A4 recorded — partially documented (DENY reasons logged; cost-checkpoint approvals remembered per user/period; no documented approval audit record) | **low** | Only documentary routes (A1/A2, plus a partial A4 basis) exist; the keystone A3 has never been witnessed, and A1/A2 are derivations from the same documents, not independent measurements. |
| Effect | No route run. E1 sentinel — applicable by design under the live protocol (sandboxed / copy-on-write / cloud-sandbox containment). E2 sandbox-diff — applicable by design (same containment). E3 trace — proposed only; no Omnigent-native OS trace documented. E4 self-report — available (`tool_result` / `response` phases) but weakest and never sufficient alone | **low** | Zero routes have produced evidence; applicability is a design reading of the documented sandbox, not a measurement. By the model's terms the layer is currently unreadable by our methods. |

## LIVE-UNLOCK

LIVE-UNLOCK: No Omnigent account or Omnigent-issued API key exists to unlock — Omnigent is self-hosted OSS; live Approval (A3) and Effect (E1/E2) measurement unlocks with (1) a self-hosted Omnigent install and server/host (official installer; no vendor account), plus (2) model access for the underlying harness in any one of the four documented credential kinds — a first-party API key (e.g. `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, auto-detected on first run), a Claude Pro/Max or ChatGPT subscription via the official `claude` / `codex` CLIs' own login, an OpenAI-/Anthropic-compatible gateway base URL + key (e.g. OpenRouter, LiteLLM, Ollama, vLLM, Azure), or a Databricks workspace profile — plus (3) for native-wrapper runs, `tmux` and, on Linux, `bubblewrap` (`bwrap`); macOS uses the built-in seatbelt sandbox.

## Recommended measurement route

| Harness | Route | Evidence type | One-line evidence |
|---|---|---|---|
| Omnigent (0.19.1; meta-harness over Claude Code / Codex / Cursor / OpenCode / Hermes / Pi / custom) | **reconstructed** | config-evaluation | No documented check/evaluate/test entrypoint in the CLI or REST surfaces (DOC-scope), but ALLOW/ASK/DENY semantics, aggregation, stacking order, event/response schemas, and builtin parameters are documented precisely enough to evaluate a named subset (deterministic builtins + CEL map-form, fresh-session state) — labelled evaluation, never interrogation. (INFERENCE on DOC+REPRO) |

**Route: reconstructed — config evaluation.** (Provenance of the Layer-1
measurement only; unranked.) An honest adapter evaluates the documented
subset against the catalogue invariants, declares its assumed session
state with every verdict, treats LLM-evaluator policies and the
`blast_radius` internals as unevaluatable — unknown with layer
attribution — and never reports a no-opinion outcome as an Omnigent
ALLOW decision.

## Open questions (what would resolve them)

1. **Binary-level oracle check.** Does the shipped 0.19.1 CLI/package
   expose any policy check/evaluate/test entrypoint absent from the
   docs? *Would resolve:* a pinned install in a scratch dir, inspected
   read-only (`omnigent --help` and subcommand help, package grep for
   evaluate/test entrypoints) — the Copilot/Muse Code spikes' method.
2. **CEL return contract.** Boolean-true-to-deny (Custom Policies page)
   vs map-with-`result`, non-map abstains (Builtin Policies page); and
   handler path `safety.cel_policy` vs `cel.cel_policy`. *Would
   resolve:* the vendor's policy source at the pinned release, or a
   vendor doc fix.
3. **`blast_radius` classification rules.** Which commands fall in the
   safe / risky / catastrophic tiers (beyond `rm -rf /` and
   force-push)? *Would resolve:* the builtin's source at the pinned
   release (repo `omnigent/policies/builtins/…`), read directly.
4. **Native-wrapper policy visibility.** Do `tool_call` policy events
   fire for tmux/PTY native-wrapper sessions (`omnigent claude` /
   `codex` / `cursor` / …) as they do for runner-relayed sessions, and
   through what mechanism (vendor hooks, ACP permission requests,
   terminal scraping)? *Would resolve:* vendor docs on the native
   wrappers' policy path, or a contained live probe (post-unlock).
5. **Underlying harness's native policy posture.** When Omnigent runs
   Claude Code / Codex, are their native approvals and rules intact,
   reconfigured, or bypassed in favour of Omnigent's layer? *Would
   resolve:* vendor documentation of the launch configuration per
   harness, or direct inspection of the spawned CLI arguments at a
   pinned install (read-only).
6. **ASK lifecycle.** Timeout/expiry of a pending ASK; who may approve
   in shared/co-driven sessions; any persistent approval audit record
   (approver, action, timestamp). *Would resolve:* vendor docs on the
   approval flow / session record schema, or a post-unlock live run
   inspected via A4.
7. **ASK short-circuit across levels.** A session-level ASK pauses the
   action — do agent/server policies still evaluate (and can they DENY)
   while it pends, or is evaluation suspended at the first ASK? The
   documented DENY short-circuit does not settle this. *Would resolve:*
   vendor engine documentation or the pinned policy-engine source.
8. **Docs-vs-release drift.** The policy docs were read at `main`
   (commit `29732f8…`); which, if any, of the semantics above differ at
   the 0.19.1 tag (e.g. the cost `[]` discrepancy)? *Would resolve:*
   re-reading `docs/POLICIES.md` and the builtin registry at the
   `v0.19.1` tag before any adapter work.

## Blockers

- **No live measurement was possible under this wave's rules** — no
  install, no credential, no live run; Approval keystone (A3) and both
  Effect routes (E1/E2) are therefore unrun by construction, and the
  live-unlock conditions above are the way out.
- **Stochastic evaluators in the policy set** — LLM-backed policies
  (`prompt_policy`, `intent_based_authorization`, `detect_task_switch`,
  `deny_trivial_to_expensive_model`) can return ASK/DENY and two are
  documented to fail open without a server LLM; any session carrying
  them is only partially evaluatable, deterministically or live.
- **Statefulness** — there is no stateless "(policy, command) →
  verdict" question to ask this product; every future measurement must
  carry its session-state assumptions or it is not reproducible.
- **Alpha, fast-moving surface** — 22 releases / 123 tags since June
  2026 (REPRO: repo page), nightly builds cut from `main` daily (DOC:
  Install page); the 0.19.1 pin and a per-version re-verification of
  the policy surface are mandatory.

## Evidence log

- DOC (fetched 2026-10-22): omnigent.ai "Contextual Policies"
  (`omnigent.ai/docs/policies/overview`) — ALLOW/ASK/DENY + aggregation
  sentence, statefulness rationale, three levels + priority table,
  plain-language assembly + `sys_add_policy` approval, YAML forms for
  agent and server levels, REST management table
  (`POST|GET|PATCH|DELETE /v1/policies`).
- DOC (fetched 2026-10-22): omnigent.ai "Builtin Policies"
  (`omnigent.ai/docs/policies/builtin`) — full builtin registry with
  parameters, incl. `blast_radius` cross-harness shell coverage,
  `github_policy` force-push semantics, `cel_policy` map-form +
  `state_updates`, the two always-on approval guards, cost-policy
  threshold/period semantics.
- DOC (fetched 2026-10-22): omnigent.ai "Custom Policies"
  (`omnigent.ai/docs/policies/custom`) — CEL boolean-form examples,
  Python policy + factory forms, `POLICY_REGISTRY` / `policy_modules`
  registration, the PolicyEvent / EventContext / PolicyResponse /
  StateUpdateEntry references (abstain ≡ ALLOW; `state_updates`
  withheld on ASK; reserved-key policy error → event denied; handler
  registration requirement from 0.19.0).
- DOC (fetched 2026-10-22): omnigent.ai "Install"
  (`omnigent.ai/quickstart/install`) — requirements (Python 3.12+,
  Node 22 LTS, tmux), extras, nightly-build cadence, `omni setup`.
- REPRO (read 2026-10-22): github.com/omnigent-ai/omnigent README —
  meta-harness definition + harness list, credential kinds table (API
  key / subscription via `claude`/`codex` CLIs / gateway / Databricks),
  first-run credential auto-detection, policy stacking summary,
  sandbox facts (mandatory `bwrap` on Linux for native wrappers + `pi`,
  seatbelt on macOS, L7 egress proxy, Windows Job Object degraded
  mode), cloud-sandbox provider list, Devin/Kiro approval mirroring,
  repo metadata (Apache-2.0, alpha, main commit `29732f8…`, 22
  releases, 123 tags).
- REPRO (read 2026-10-22): repo `docs/POLICIES.md` (in full) —
  declaration-order evaluation + DENY short-circuit, level evaluation
  order (session first), policy declaration syntax (both forms),
  `enforce_sandbox` start-probe semantics + fail-closed start,
  deny-by-default agent environment / `env_passthrough`, `cost_budget`
  request+tool_call phases and downgrade-gate semantics, `github_policy`
  shell-segment parsing (unclassified regions, DENY > ASK > ALLOW),
  `block_working_dir_changes` parsing posture, worked PolicyEvent
  example (`sys_os_shell`, `arguments.command`), admin REST API
  appendix incl. `GET /v1/policy-registry`.
- DOC (release listing, 2026-10-22): PyPI `omnigent` — release files
  for **0.19.1** uploaded 2026-10-21 (the version pin).
- THIRD-PARTY (locator only, not evidence): arXiv harness-anatomy study
  and integrator/blog summaries surfaced the policy docs and the
  bypass-flag question; every load-bearing claim above was re-grounded
  in the primary sources listed here or marked unknown.
