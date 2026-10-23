# OpenClaw — Testability Assessment (2026-10-22)

*Design-stage spike only: no measurement run, no corpus evaluation, no
results.json. No account created, no login performed, nothing installed,
nothing published, no outreach, no commits. Assessment date: 2026-10-22.*

## Identity — referent pinned, with collisions recorded

**PINNED.** In this programme "OpenClaw" (harness key `openclaw`) means
exactly one project:

- **OpenClaw — `github.com/openclaw/openclaw`** (DOC/REPRO: the project's
  own GitHub repository, read directly 2026-10-22): "an open-source AI
  assistant that runs on your own computer and meets you in the channels
  you already use"; one **Gateway** runs it as a personal assistant;
  "Models and agent harnesses (Claude, Codex, local models) are plugins
  you can swap"; stewarded by the OpenClaw Foundation; built by Peter
  Steinberger and the community for "Molty"; MIT licence; repository
  created 2025-11-24; config at `~/.openclaw/openclaw.json`; CLI binary
  `openclaw` (`openclaw onboard`, `openclaw gateway`, `openclaw acp`).
- Its own docs (DOC: docs.openclaw.ai, the vendor docs site linked from
  the repository README) describe it as a "self-hosted gateway" that
  connects chat apps "to AI coding agents like Pi" and as "Agent-native:
  built for coding agents with tool use, sessions, memory, and
  multi-agent routing." It is **not itself a coding agent**: it is a
  personal-assistant gateway / runtime whose *own* native tools
  (`exec`, `read`, `write`, `edit`, `apply_patch`, browser, messaging)
  execute on the host, and which can additionally host or drive coding
  harnesses as plugins. **The surface assessed below is OpenClaw's own
  native tool/exec boundary — never the boundary of a harness it hosts**
  (a hosted Claude Code / Codex session keeps that harness's own
  boundary, already covered by its own adapter).
- **Independent cross-check (the Omnigent test):** the Omnigent
  meta-harness catalogue (DOC for Omnigent: `github.com/omnigent-ai/omnigent`,
  `docs/openclaw.md`, read directly) has an "OpenClaw integration" guide
  that refers to this same project and no other: it imports "coding
  agents registered in OpenClaw/acpx" from `~/.acpx/config.json` or
  `~/.openclaw/openclaw.json`, and drives "a live OpenClaw Gateway
  session" via `openclaw acp … --token-file …` — the same config path,
  the same CLI, the same Gateway as the pinned repo. Two independent
  primary sources converge on one referent.

**Same-name / near-name candidates considered and excluded:**

1. **OpenClaw, the Captain Claw engine** (THIRD-PARTY: multiple
   independent descriptions agree) — an open-source C++/SDL2
   reimplementation of the 1997 *Captain Claw* platformer engine
   (attributed to the `pjasicek` GitHub account; the player supplies the
   original game assets). Same exact name, older project, **not an
   agent, not a framework for agents, no tool/exec policy surface**.
   Excluded by category: the founder named OpenClaw "among popular
   agents/frameworks."
2. **PyPI `openclaw`** (primary package page as surfaced in search; the
   page itself returned a client challenge on direct fetch) — an
   installer for the unrelated **CMDOP** CLI which states in its own
   text: *"Not affiliated with the OpenClaw project. If you are looking
   for github.com/openclaw/openclaw, that is a different project."*
   A name collision on the package index that itself points back to
   the pinned referent. Excluded.
3. **OneClaw** (THIRD-PARTY) — a separate commercial managed-hosting
   service for OpenClaw whose own site disclaims affiliation with the
   OpenClaw project. A service built *around* the pinned referent, not
   a rival referent. Excluded.
4. **`captain-claw`** (DOC: `github.com/kstevica/captain-claw`, GitHub
   listing read in search) — a distinct self-hosted agent-orchestration
   framework whose skills are merely "OpenClaw-compatible." Near-name,
   different name, different project. Excluded.
5. **Search noise, not a candidate:** at least one third-party article
   describes "OpenClaw" as a web-crawling / RAG data-ingestion
   framework. No primary source (repo, docs, package) for such a
   project was located; the article itself flags its description as an
   assumption. Recorded as evidence that the name attracts
   confabulation — and as a reason this identity section exists — but
   with no primary source it is not a candidate referent.

**Identity confidence:** the pin rests on two independent primary
sources (the project's own repo/docs, and Omnigent's integration doc)
agreeing on repo, CLI, config path, and Gateway. That is a pin, not a
guess. The residual ambiguity is historical (the project was previously
named Clawdbot, then Moltbot — THIRD-PARTY, consistently reported;
earliest form "Warelay") and onomastic (candidates 1–4 above), not
referential: no second *agent/framework* project bearing the exact name
was found.

## Surface assessed

- **Product:** OpenClaw (pinned above) — Gateway + native tools, CLI
  `openclaw`, npm package `openclaw` (install route in the repo README:
  `npm install -g openclaw@latest`, or the `openclaw.ai` installer).
- **Version pinned:** no binary was installed (hard rule), so no
  version string is claimed. The assessed surface is pinned to the
  vendor docs at docs.openclaw.ai and the repository `main` commit
  `1f49237c16f65a6bb87c2a4d88dde5546455ae4f`, both read 2026-10-22.
  Any version number in third-party write-ups (e.g. v2026.10.x) is
  **not asserted** here.
- **Docs consulted (official, fetched 2026-10-22):** repository README;
  docs.openclaw.ai home; "Security" (`/gateway/security`); "Sandboxing"
  (`/gateway/sandboxing`); "Tools and plugins" (`/tools`).
- **Not done:** no install, no `--help` reproduction, no config
  validated, no Gateway run. Every negative below is a DOC negative,
  not a REPRO negative — the CLI surface was not exhaustively
  reproduced, and that limitation is carried in the confidence.

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO (on DOC evidence)**

- No per-command check/evaluate/test entrypoint is documented in the
  primary sources read. There is no documented analogue of
  `codex execpolicy check` or `amp permissions test` — nothing that
  takes a hypothetical command plus a policy and returns the harness's
  own decision offline. (DOC: tools, security, and sandboxing docs.)
- The documented inspectors are **inspectors, not evaluators**:
  `openclaw security audit [--deep|--fix|--json]` audits a *config*
  for footguns (DOC: security guide); `openclaw sandbox explain`
  reports the *effective* sandbox mode, scope, workspace access, and
  effective sandbox tool allow/deny for a session/agent (DOC:
  sandboxing guide). Neither evaluates a command.
- `openclaw approvals get` and `openclaw exec-policy show` are
  reported by third-party summaries of the vendor docs as showing the
  requested policy, the host approvals file, and the effective merged
  result (THIRD-PARTY). Even as reported, they display *policy state*;
  no hypothetical-command evaluation mode is reported for them.
- Because no install was permitted, this negative is not backed by a
  binary/CLI reproduction. It is recorded as **unknown-with-reason at
  REPRO level, NO at DOC level**: if a pinned install later surfaces a
  checker, this answer must be revised — that is open question 1.

### (b) Documented semantics precise enough for an honest reconstructed route? — **YES, narrowly — at tool and binary granularity only**

The paper surface is real but coarse. What is documented precisely:

**1. Tool policy (DOC: "Tools and plugins").** `tools.allow` /
`tools.deny` in `openclaw.json` control which tools an agent can call;
**deny always wins over allow**. `tools.profile` sets a base allowlist
(`full` / `coding` / `messaging` / `minimal`, with the profile contents
tabulated) before allow/deny apply; `group:*` shorthands
(`group:runtime` = `exec, process, code_execution`; `group:fs` =
`read, write, edit, apply_patch`; `group:web`, `group:messaging`, …)
are enumerated; `tools.byProvider` restricts tools per provider;
per-agent overrides live at `agents.list[].tools.*`. OpenClaw **fails
closed when an explicit allowlist resolves to no callable tools** (the
run stops before the model call). Granularity is the *tool*, never the
tool's arguments.

**2. Exec approvals (DOC in part; file details THIRD-PARTY).** Host
`exec` has a security/ask pair: the security guide's hardened baseline
sets `tools.exec: { security: "deny", ask: "always" }`, and states the
product default for trusted single-operator setups is
`security="full"`, `ask="off"` — host exec allowed with no prompts
(DOC). The ask vocabulary (`off` / `on-miss` / `always`) and
`askFallback`, the host-local file `~/.openclaw/exec-approvals.json`
(per-agent allowlists of binary-path patterns; an approval prompt
offers allow-once / allow-always, and allow-always persists the
pattern), and the precedence rule — **the effective policy is the
stricter of the `tools.exec.*` config and the host-local approvals
file** — come from third-party summaries of the vendor exec-approvals
docs (THIRD-PARTY), corroborated in part by the official security
guide (exec approvals as "allowlist + ask"; a per-node exec approvals
file, `exec.approvals.node.*`; macOS "Settings → Exec approvals
(security + ask + allowlist)"). The decisive granularity fact, also
from those summaries and consistent with the official guide's warning
below: **an allowlist entry matches a resolved binary, and allowing a
binary allows all of its subcommands/arguments** (allowlisting `git`
allows `git push`). There is no documented argument-pattern deny rule
for `exec`.

**3. Sandbox (DOC: "Sandboxing").** `agents.defaults.sandbox.mode`
(`off` / `non-main` / `all`), `.scope` (`agent` / `session` / `shared`),
`.backend` (`docker` default, `ssh`, `openshell`),
`.workspaceAccess` (`none` default / `ro` / `rw`); Docker sandboxes run
with **no network by default**; global and per-agent Docker binds
merge. Tool allow/deny still applies *before* sandbox rules, and
`tools.elevated` is an explicit escape hatch that runs `exec` outside
the sandbox.

**Ceilings capping this at reconstructed, low confidence:**

1. **Granularity.** The Decision surface decides *tools* and
   *binaries*, not argv. Most catalogue invariants are argument-shaped
   (`rm -rf`, `git push --force`, `DROP DATABASE` inside `-c`); on
   this surface they are expressible only by denying/prompting the
   whole binary or tool, or not at all. An honest adapter must return
   **unknown** for the argument-level question, never a verdict
   borrowed from the binary-level answer.
2. **Two documented generations of the exec surface.** The official
   security guide (read directly) uses `tools.exec.security` +
   `tools.exec.ask`; community-mirrored current docs and multiple
   third-party write-ups describe a unified `tools.exec.mode`
   (`full` default / `auto` / `ask` / `allowlist` / `deny`), with
   `auto` delegating non-allowlisted commands to an **automatic
   reviewer** that "allows, denies or asks." Which generation a given
   pinned version implements is **unknown** from the sources read and
   must be resolved before any adapter code is written (open
   question 2). The `auto` reviewer, in either generation's terms, is
   a stochastic Approval-layer mechanism, never a Decision oracle.
3. **Interpreter opacity, vendor-acknowledged.** "Exec approvals bind
   exact request context and best-effort direct local file operands;
   they do not semantically model every runtime/interpreter loader
   path" (DOC: security guide). Wrapped/script forms are therefore
   unknown at this layer by the vendor's own statement.
4. **Compound-command semantics not established in primary sources.**
   How `&&`/`;`/`|` chains are split and matched against the binary
   allowlist is claimed by third parties (every segment must pass;
   control operators always prompt) but was **not** found in the
   official pages read — recorded as unknown, not asserted.
5. **Scope bleed.** Plugin tools, MCP tools, skills, and hosted
   coding-harness plugins execute under their own surfaces; none of
   that is evaluatable from the docs read, and none of it is claimed.

### (c) Surface record — N/A for the route (harness is reconstructed), defaults recorded anyway

- **Defaults (DOC):** sandbox **off** (tools run on the host for the
  main session); host exec `security="full"`, `ask="off"` (no approval
  prompts); DM policy `pairing`; the Gateway is the control plane and
  policy surface; "any allowed sender can induce tool calls within the
  agent's policy" on a shared agent.
- **No-match mapping:** there is no single no-match rule — it depends
  on the configured mode (allowlist-mode no-match ≈ silent deny;
  ask-mode no-match ≈ prompt; full-mode has no match concept at all).
  A reconstructed adapter must model the *configured* mode explicitly
  and serialize anything it cannot compute as **unknown, never allow**
  (INV-005).

## Decision surface

Tool allow/deny (deny-wins, profiles, groups, per-provider and
per-agent overrides, fail-closed empty allowlist) plus the exec
security/ask (or unified-mode) pair plus the host-local binary
allowlist in `~/.openclaw/exec-approvals.json`, with stricter-of-two
precedence between gateway config and host file. Decisions are
deterministic functions of config at tool/binary granularity — and
only there. No vendor checker exists to cross-check a reconstruction
against (no D1, no D3), so Decision confidence is one-route: **low**.

## Approval machinery

Exec approvals are the Approval surface: ask modes (`off` / `on-miss` /
`always`, or unified `ask`/`auto`), prompts delivered in the Control UI
or the originating channel with allow-once / allow-always / deny
(THIRD-PARTY for the delivery details; DOC for the ask machinery's
existence and defaults), `askFallback` for the no-UI case, and the
`auto` mode's automatic reviewer (stochastic; an Approval-layer
mechanism, never tested as an oracle). Elevated mode
(`/elevated on|ask|full|off`, gated by `tools.elevated.enabled` and
sender allowlists) modulates whether sandboxed `exec` escapes to the
host and whether approvals still apply. Gateway/node pairing approvals
and DM pairing are *trigger* authorization, a different surface,
recorded here only to keep them out of the Approval verdict.

## Effect surface

Where execution lands: host by default; Docker/SSH/OpenShell sandbox
backends when enabled (workspace access `none`/`ro`/`rw`, Docker
network `none` by default, bind mounts merged); `tools.elevated` as
the documented escape hatch; node hosts as a remote execution surface
paired to the Gateway. `openclaw sandbox explain` is the documented
inspector for effective Effect-layer configuration. None of this was
observed live: the Effect layer here is a *documented configuration
surface*, not a measured outcome.

## Per-layer route table

| Layer | Route | Confidence | Basis |
|---|---|---|---|
| Decision | reconstructed | low | No vendor checker documented (a: NO, DOC-level). Tool allow/deny deny-wins, profiles/groups, and sandbox config are documented precisely (DOC); exec allowlist file, stricter-of-two precedence, and binary-path matching are THIRD-PARTY summaries of vendor docs, partly corroborated by the official security guide. One route only, no cross-check (no D1/D3); granularity is tool/binary, never argv. (INFERENCE on DOC+THIRD-PARTY) |
| Approval | A1 Promised — applicable (a Decision of prompt under `ask`/`on-miss` owes an ask; an expectation, not a measurement). A2 Configured — applicable (exec security/ask or mode, elevated gates, read from `openclaw.json` + host `exec-approvals.json`). A3 Witnessed live (KEYSTONE) — **not done**. A4 Recorded — unknown (no transcript/approval-record format established in the primary sources read) | low | A1/A2 rest on the same DOC+THIRD-PARTY base as Decision; A3 has no evidence; per the measurement model, confidence attaches to our measurement, and no Approval measurement exists. |
| Effect | E1 Sentinel state — applicable in principle under a contained run, not run. E2 Sandbox diff — applicable in principle (sandbox backends + workspace sync are documented), not run. E3 System trace — not established. E4 Agent self-report — available in principle, weakest route, never sufficient alone, not used | low | Documented Effect *configuration* only (DOC: sandboxing guide). No live change has been observed; the Effect keystone has no evidence. |

## LIVE-UNLOCK line

LIVE-UNLOCK: one contained live run of a pinned OpenClaw Gateway (install permitted, model credential supplied by the owner) in tools.exec.mode="ask" with sandbox mode "all", in which a sentinel command is (i) witnessed pausing for approval (route A3, the Approval keystone) and (ii) observed changing sentinel state only after approval (routes E1/E2, the Effect keystone) — that single run unlocks the Approval and Effect layers; until then both layers are design-stage only and no verdict attaches to them.

## Open questions (what would resolve them)

1. **Does a pinned install expose any check/evaluate entrypoint?**
   A read-only (a)-spike against a pinned `openclaw` CLI (`--help` and
   subcommand help for `approvals`, `exec-policy`, `sandbox`,
   `security`) would convert the DOC-level NO into a REPRO-level
   answer, in either direction.
2. **Which exec-policy generation is current at a pinned version?**
   `tools.exec.security`+`ask` (official security guide, read
   directly) vs unified `tools.exec.mode` incl. the `auto` automatic
   reviewer (community-mirrored docs + third-party). Resolved by the
   pinned version's own configuration reference / `config schema`
   output — an adapter written before this is resolved would encode
   the wrong surface.
3. **Allowlist matching semantics, vendor-stated.** Resolved-binary
   path patterns, case handling, basename handling, and whether
   "always allow" persists an exact command-in-directory or a binary
   pattern are currently THIRD-PARTY. The vendor exec-approvals page
   at the pinned version resolves them.
4. **Compound-command semantics.** Whether chains are split per
   segment and how segments are matched is unestablished in primary
   sources; vendor documentation or a pinned live probe resolves it.
5. **Host-allowlist expressiveness for egress.** Whether any
   documented surface can bind *destinations* (not just binaries) for
   `web_fetch`/HTTP tools, beyond sandbox network `none`. Not found
   in the sources read.
6. **Approval records (route A4).** Whether approvals and their
   outcomes are persisted in a readable transcript/log format.
   Unknown from the sources read.

## Blockers

- **No-install / no-live-run rule of this spike:** no binary pin, no
  REPRO CLI surface, no A3/E1/E2 evidence. The live-unlock run above
  is the unblock, and it needs an owner-supplied model credential.
- **Stochastic reviewer in `auto` mode:** if the pinned version's
  default or recommended mode routes non-allowlisted commands through
  an automatic reviewer, those decisions are not a deterministic
  function of config and are unevaluatable — the honest evaluation
  target is the deterministic modes (`ask` / `allowlist` / `deny` /
  `full`) plus tool policy.
- **Binary granularity:** argument-shaped invariants cannot be
  established at the Decision layer on this surface; translations
  that pretend otherwise would be fabrication. The draft translations
  (`docs/catalogue/translations-draft/openclaw.json`) encode this
  ceiling per entry.

## Evidence log

- DOC (fetched 2026-10-22): github.com/openclaw/openclaw — README
  ("Your assistant, on your devices, in your chats"; Gateway; harnesses
  as plugins; Foundation stewardship; Peter Steinberger / Molty;
  `npm install -g openclaw@latest`; `openclaw onboard --install-daemon`;
  "Tools run on the host for the main session unless you configure
  sandboxing"), repo metadata (MIT, created 2025-11-24, main commit
  `1f49237c16f65a6bb87c2a4d88dde5546455ae4f`).
- DOC (fetched 2026-10-22): docs.openclaw.ai — home (self-hosted
  gateway; "AI coding agents like Pi"; "built for coding agents";
  config at `~/.openclaw/openclaw.json`); `/gateway/security`
  (personal-assistant trust model; default host exec `security="full"`,
  `ask="off"`; hardened baseline `tools.exec: {security:"deny",
  ask:"always"}` + `tools.deny` + `fs.workspaceOnly`; exec approvals
  "bind exact request context… do not semantically model every
  runtime/interpreter loader path"; `openclaw security audit`;
  per-node exec approvals file); `/gateway/sandboxing` (modes, scope,
  backends, workspaceAccess, Docker network none by default, binds
  merge, tool policy before sandbox, elevated escape hatch,
  `openclaw sandbox explain`); `/tools` (allow/deny deny-wins,
  profiles tabulated, groups enumerated, byProvider, fail-closed
  empty allowlist, tool inventory).
- DOC for the cross-check (fetched 2026-10-22):
  github.com/omnigent-ai/omnigent, `docs/openclaw.md` — "Import coding
  agents" from `~/.openclaw/openclaw.json` / `~/.acpx/config.json`;
  "Drive the OpenClaw Gateway" via `openclaw acp`; "OpenClaw still has
  its own native tools (for example, shell and filesystem tools)";
  integration "validated end-to-end against a live OpenClaw Gateway"
  (Omnigent's claim about its own integration, not a measurement by
  this programme).
- THIRD-PARTY (read 2026-10-22, used only where tagged): exec-approvals
  file format and stricter-of-two precedence, allowlist binary-path
  glob details, allow-once/allow-always persistence, `openclaw
  approvals get` / `openclaw exec-policy show` as policy inspectors,
  unified `tools.exec.mode` table incl. `auto` automatic reviewer
  (openclawplaybook.ai, dev.to, clawdocs.org community mirror,
  websprint.dev, yu-wenhao.com) — mutually consistent, partly
  corroborated by the official security guide, **not** treated as DOC.
- THIRD-PARTY identity exclusions (read 2026-10-22): Captain Claw
  engine descriptions (webpronews.com, galaxywing.com); OneClaw
  disclaimer as reported (triumphoid.com); rename history
  Warelay → Clawdbot → Moltbot → OpenClaw (multiple, consistent).
- Primary-source attempt that failed: pypi.org/project/openclaw
  returned a client challenge on direct fetch; its disclaimer text
  ("Not affiliated with the OpenClaw project… github.com/openclaw/
  openclaw… is a different project"; CMDOP installer) is recorded
  from the search-result rendering of that page, and is tagged
  accordingly in the identity section.
- No install, no login, no live run, no repo code executed. Nothing
  in this assessment is a measurement.
