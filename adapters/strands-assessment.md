# Strands Agents — Testability Assessment (2026-10-22)

*Assessment only: design-stage spike for the Wave A expansion. No corpus
evaluation, no results.json, NO measurement run. No account created, no
login performed, no install, nothing published, no outreach, no commits.*

**Naming note (explicit):** this assesses **Strands Agents** — the
open-source agent SDK from AWS (`strands-agents` on PyPI; source repo
`github.com/strands-agents/sdk-python`, which now redirects to the
`strands-agents/harness-sdk` monorepo where the Python SDK lives under
`strands-py/`). It is NOT Amazon Bedrock Agents (the hosted AWS service),
NOT AgentCore Runtime (a deployment target Strands can run on), and NOT
the separate `strands-agents/tools` community tools package except where
that package's tools are assessed as the Effect surface (marked as such).

**Headline:** Strands has **no declarative policy oracle and no native
per-command policy surface in the SDK core**. There is no config file of
allow/ask/deny rules for tool calls and no offline checker. What exists
is a **code-level gate**: lifecycle hooks and a typed interventions layer
that run in-process, in the agent's own Python process, immediately
before tool execution. The honest FinePrint target is therefore not a
policy file but an **instrumented reference agent** — a canonical minimal
agent whose hook code *is* the policy — measured at the Approval and
Effect layers. Decision-layer route: **no paper surface**.

## Surface assessed

- **Product:** Strands Agents SDK for Python — `strands-agents` **1.62.0**
  on PyPI (release files uploaded 2026-10-21) (DOC: PyPI project page).
  Python 3.10+ required (DOC: PyPI / repo README).
- **Repos (primary, read 2026-10-22):**
  - `github.com/strands-agents/sdk-python` → redirects to
    `github.com/strands-agents/harness-sdk` (monorepo: `strands-py/` =
    Python SDK, `strands-ts/`, `harness-py/`, `site/` = source of
    strandsagents.com). HEAD at retrieval: commit `8916c9fa…` (REPRO:
    GitHub repo page).
  - `github.com/strands-agents/tools` (community tools package
    `strands-agents-tools`). HEAD at retrieval: commit `4e9d5ea4…`
    (REPRO: GitHub repo page). The tools package's exact current PyPI
    version was **not established** from the pages read — recorded as
    unknown, not guessed.
- **Canonical docs home (verified from the repo README):**
  **strandsagents.com** — the repo links "Documentation ◆
  strandsagents.com" and the docs site source lives in the monorepo's
  `site/` directory (REPRO). AWS's own docs.aws.amazon.com carries
  Bedrock / AgentCore / Guardrails service documentation; the SDK's
  behaviour is documented at strandsagents.com, which is the primary
  source used here.
- **Docs consulted (all strandsagents.com, retrieved 2026-10-22):**
  Hooks; Hook events (reference); Interrupts; Interventions;
  Human in the loop; Cedar Authorization; Amazon Bedrock (model
  provider, incl. Guardrails); Model Providers.
- **No binary/package inspection:** nothing was installed (hard limit);
  unlike the CLI harnesses there is no CLI surface to `--help`. All
  claims below are DOC (official docs / official repo / PyPI) unless
  tagged otherwise.

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO**

- Strands is a library, not a CLI harness. There is no binary, no
  `check` / `evaluate` / `dry-run` entrypoint, and no policy file format
  whose decision for a command could be queried offline (DOC: full docs
  surface above; the SDK's decision-relevant surfaces are hooks,
  interventions, and model config — all runtime code).
- The thing that decides whether a tool call proceeds is **user Python
  code executing inside the agent loop** (a hook callback setting
  `event.cancel_tool`, or an intervention handler returning `Deny` /
  `Confirm` / `Proceed`) (DOC: Hooks; Interventions). Arbitrary Python
  has no offline decision function to interrogate: the same input can
  branch on time, randomness, network, or mutable state.
- The one declarative exception is partial and is **not** an oracle:
  the vended **Cedar Authorization** intervention evaluates real Cedar
  policies (`permit(...)` / default-deny) before each tool call (DOC:
  Cedar Authorization). But the Strands-level decision is the
  *composition* — Cedar policy + `principal_resolver` and
  `context_enricher` (Python lambdas) + handler ordering + any other
  hooks — and no offline checker for that composition is documented or
  shipped. Cedar is recorded below as a substitute surface, not a route.

### (b) Documented semantics precise enough for an honest reconstructed route? — **NO** (for the harness's Decision)

- A reconstructed route computes decisions from documented semantics of
  a *rule surface*. Strands' gate is not a rule surface: hook callbacks
  are arbitrary Python; the docs specify the *event contract* precisely
  (which properties are mutable, when events fire, ordering) but cannot
  specify what any given policy hook will decide (DOC: Hook events).
  Re-implementing "the matching logic" would mean re-implementing the
  owner's Python — there is nothing to reconstruct.
- What *is* documented precisely, and is used by this spike: the event
  contract (`BeforeToolCallEvent.cancel_tool` / `selected_tool` /
  `tool_use` mutation; `BeforeToolsEvent.cancel`), intervention action
  semantics and precedence (deny > confirm > guide > transform >
  proceed; registration order; `Deny` short-circuits), interrupt/resume
  mechanics, HITL handler configuration, guardrail config keys, and the
  tools' consent environment variables. These make the **Approval-layer
  configured route (A2)** and a reference-agent design honest — they do
  not make a Decision-layer paper route.

### (c) Surface record — **YES: no paper surface**

- **Surface:** Python SDK (`Agent`, `hooks=[HookProvider…]`,
  `interventions=[InterventionHandler…]`, `model=BedrockModel(...)` by
  default). No policy config file exists in the core SDK.
- **Defaults (the decision-relevant fact):** with no hook/intervention
  registered, a tool call the model emits **proceeds to execution** —
  hooks and interventions are opt-in additions; the framework's default
  intervention outcome is `Proceed()` (DOC: Interventions — "All methods
  default to `Proceed()`"). There is no no-match state: absence of a gate
  is execution, and per INV-005 our reporter must serialize "no gate
  decided" as **unknown**, never as allow.
- **No verdicts are issued for Strands.** The catalogue translations in
  `docs/catalogue/translations-draft/strands.json` are design-stage
  reference-agent templates, `measured: false` throughout.

## Decision surface

### Hooks as a code-level gate (the closest thing to a Decision mechanism)

- A hook provider subclasses `HookProvider` and registers callbacks via
  `register_hooks(registry: HookRegistry)` →
  `registry.add_callback(BeforeToolCallEvent, fn)`; providers are passed
  as `Agent(hooks=[...])`, or single callbacks via `agent.add_hook(...)`
  (DOC: Hooks). Plugins and the newer interventions layer build on the
  same registry.
- **`BeforeToolCallEvent` fires before a tool is invoked** and exposes
  exactly three mutable properties (DOC: Hook events reference):
  - `cancel_tool` — cancel this tool execution with a message; the tool
    does not run and the model receives the cancellation message as an
    error result it can react to (DOC: Hooks, "Limit Tool Counts").
  - `selected_tool` — replace the tool implementation to be executed
    (DOC: Hooks, "Tool Interception").
  - `tool_use` — modify the tool's input parameters in place before
    execution (DOC: Hooks, "Fixed Tool Arguments" — the example rewrites
    `event.tool_use["input"]`).
  So a hook **can** veto, substitute, and rewrite a tool call before
  execution. It decides with full Python: it sees `event.tool_use["name"]`
  and `event.tool_use["input"]`, plus `event.invocation_state`.
- `BeforeToolsEvent` fires before a batch; its `cancel` cancels **every**
  tool call in the batch (error result for each, batch skipped, no
  per-tool `BeforeToolCallEvent` fires) (DOC: Interrupts).
- **What a hook cannot decide / cannot be:**
  - It cannot be queried offline, enumerated, or diffed like a rule file;
    its decision function is whatever the code does, including
    non-determinism the owner introduces.
  - Hook-vs-hook conflicts on the same event are **last-write-wins on
    mutated properties** with no framework knowledge of *why* (DOC:
    Interventions, "Relationship to Hooks and Plugins" — the stated
    motivation for interventions). Callback ordering is registration
    order for Before events (priority overridable via `order` /
    `HookOrder` presets) (DOC: Hooks).
  - A cancelled call is not a hard stop for the *agent*: the model sees
    the cancellation message and may retry, rephrase, or route around it
    in later turns. The gate is per-call, at the tool boundary.
- **Interventions** (the typed layer over hooks): a handler overrides
  `before_tool_call(event)` and returns `Proceed()` / `Deny(reason)` /
  `Guide(feedback)` / `Confirm(prompt)` / `Transform(apply=fn)` (DOC:
  Interventions). Documented semantics: handlers run in registration
  order; `Deny` short-circuits remaining handlers; precedence **deny >
  confirm > guide > transform > proceed**; each handler declares an
  `on_error` policy (`throw` default / `proceed` / `deny` fail-closed).
  This is the most decision-like documented semantics Strands has — and
  it is still a return value of arbitrary Python code, evaluated live.

### Cedar Authorization (declarative substitute — recorded, not a route)

- `strands.vended_interventions.cedar.CedarAuthorization(policies=...)`
  evaluates Cedar policies before each tool call: Action = tool name,
  `context.input` = tool arguments, `context.session` = invocation
  metadata; **default-deny** (no matching `permit` → denied, feedback to
  the model); fail-closed when the principal cannot be resolved (DOC:
  Cedar Authorization). Policies may be inline strings or `.cedar`
  files; schema validation against tool definitions is offered at
  construction.
- Why this is still not a paper route: the evaluated request is built by
  Python (`principal_resolver`, `context_enricher`), the handler sits in
  an ordered intervention pipeline with other code, and the vendor ships
  no offline "what does this agent decide for this call" checker.
  Whether a *Cedar-only* reference configuration could support a
  reconstructed evaluation (via Cedar's own engine) is an open question
  below — it would evaluate the Cedar policy, not the harness.

### Amazon Bedrock Guardrails — actual scope

- Guardrails attach to the **model**, not to tools:
  `BedrockModel(guardrail_id=..., guardrail_version=...,
  guardrail_trace=..., guardrail_redact_input=True (default),
  guardrail_redact_output=False (default), ...)` (DOC: Amazon Bedrock
  provider page).
- What they screen: **model input and model output content** — Bedrock
  evaluates the conversation input and the model's response against the
  guardrail's content/topic/word/PII policies; on intervention the input
  and/or output is **redacted** with a configurable message (DOC: same).
- What they do **not** do: they never see a tool call as an action to
  permit or deny. A guardrail can redact a prompt that *mentions* a
  command; it cannot forbid `shell` from running it, gate a deploy, or
  express any FP-catalogue invariant. In FinePrint terms guardrails are
  a content filter on the model channel — **not Decision, not Approval**
  for tool execution. (They also exist only on the Bedrock provider
  path.)

## Approval machinery

### What exists natively

1. **Interrupts (the mechanism).** From a hook callback or a tool,
   `event.interrupt(name, reason=...)` / `tool_context.interrupt(...)`
   stops the agent loop **before the tool executes** (for
   `BeforeToolCallEvent` / `BeforeToolsEvent`); the run returns
   `result.stop_reason == "interrupt"` with `result.interrupts` (each:
   `id`, `name`, JSON-serializable `reason`). The caller collects human
   responses and resumes by invoking the agent with
   `[{"interruptResponse": {"interruptId": ..., "response": ...}}]`;
   on resume the hook re-runs, reads the response, and either proceeds
   or sets `event.cancel_tool` (DOC: Interrupts). One interrupt per hook
   callback at a time; names must be unique per event. Interrupts are
   **not** supported in direct tool calls (`agent.tool.x()`).
2. **`HumanInTheLoop` intervention handler (the productized ask).**
   `interventions=[HumanInTheLoop(...)]` pauses before tool execution
   via the `Confirm` action (DOC: Human in the loop). Collection modes:
   interrupt/resume (default), `ask="stdio"` (terminal prompt, blocks
   inline), or a custom `ask` callback (web UI / Slack / async).
   Configuration: `allowed_tools` (bypass list, `"*"` and `"!name"`
   negation), `classifier` (an LLM risk classifier — bool/config/
   custom function), `enable_trust` (a `'t'`/`'trust'` response approves
   and is remembered for the session in `agent.state`), `evaluate`
   (custom approval predicate; default accepts `True` / `"y"` / `"yes"`).
3. **Tools' own consent prompts (legacy tools package).** The
   `strands-agents-tools` `shell`, `file_write`, and `python_repl` tools
   prompt the operator for consent before executing (DOC/REPRO: tools
   repo README env table — `BYPASS_TOOL_CONSENT`, default `false`,
   "All tools that require consent (e.g. shell, file_write,
   python_repl)"; `STRANDS_NON_INTERACTIVE=true` suppresses confirmation
   dialogs for tools with a prompt, e.g. shell, python_repl). This is a
   per-tool terminal prompt inside the tool implementation — separate
   from hooks/interrupts — and it is bypassable by operator-set
   environment variables.

### Where a human ask can occur relative to tool execution

- Hook/intervention/interrupt asks occur **before** execution, at the
  `BeforeToolCallEvent` / batch `BeforeToolsEvent` point — the tool has
  not run while the agent is paused. A tool-internal interrupt occurs
  *inside* the tool's own code, at whatever point the tool raises it
  (the documented pattern raises it before doing the work) (DOC:
  Interrupts, Tools section).
- Tools' consent prompts occur inside the tool invocation, before the
  tool performs its effect (per the tools' documented behaviour).
- There is **no** framework-level "ask" that fires by default: no hook,
  no intervention, no consent-bearing tool → no ask, ever. Approval in
  Strands is entirely **constructed** by the agent's author.

### What must be built from hooks

- Any policy-shaped ask ("ask only for deploys to production", "ask for
  deletes under a protected path") is owner code: a `BeforeToolCallEvent`
  hook matching on tool name + input and calling `event.interrupt(...)`,
  or an `InterventionHandler` returning `Confirm(...)` — the
  `HumanInTheLoop` handler covers the tool-name granularity natively;
  argument-sensitive asks need the classifier or custom code (DOC:
  Human in the loop; Interventions).

## Effect surface

- **Execution reality: in-process, on the host.** The repo's own framing:
  the SDK "runs in your process with no hosted control plane" (REPRO:
  harness-sdk README). Tools are Python callables the agent loop invokes
  in that process, with the host process's privileges, filesystem, and
  network. Custom `@tool` functions, MCP tools, and the community tools
  all execute this way unless a tool itself delegates elsewhere.
- **Built-in/community tools behaviour** (tools repo, current HEAD —
  the package is mid-transition, both rows documented):
  - *Legacy `strands-agents-tools` tools* (`shell`, `file_write`,
    `python_repl`, `editor`, `http_request`, …): marked **deprecated**
    in the current README's tools table; `shell` executes shell
    commands on the host (`agent.tool.shell(command="ls -la")`, single
    command or a sequence), `file_write` writes host files,
    `python_repl` runs Python with "user confirmation for security"
    (DOC/REPRO: tools README). Consent per the env table above.
  - *SDK-native successors:* the migration notes state the SDK's
    `python_repl` "by default … executes on the host with no isolation
    and no confirmation prompt — pass a `sandbox=` to `Agent` (for
    example `DockerSandbox`) if you relied on the consent gate", and
    that the shell is "sandbox-routed" when a sandbox is configured
    (REPRO: tools README, Deprecations). I.e. at the pinned HEAD,
    sandboxing is an **opt-in `Agent(sandbox=...)` routing**, not a
    default property of tool execution. The sandbox implementations
    themselves (DockerSandbox etc.) were not read in depth in this
    spike — their confinement semantics are **unknown** here and must
    not be asserted.
  - `code_interpreter` (Bedrock AgentCore Code Interpreter) is the one
    listed tool whose execution is isolated **by construction** — it
    delegates to an AWS-managed sandbox service ("Execute code in
    isolated sandbox environments", DOC: tools README table) — at the
    price of an AWS account and a service call per execution. It is a
    different tool, not a property of `shell`/`file_write`.
- **No sandbox in the SDK core.** Nothing in the core SDK confines a
  tool: no seccomp/landlock/namespace layer, no path jail, no network
  egress control is documented for ordinary tools. Any claim that a
  Strands agent "runs sandboxed" is a claim about a specific optional
  configuration (AgentCore deployment, `sandbox=` routing, or the
  code-interpreter tool), never about Strands itself.
- **Consequence for FinePrint:** the Effect layer is *directly*
  observable with the existing instrument — a contained run's effects
  land on the real (sandbox-directory) filesystem of the host process,
  which is exactly what sentinel assets + sandbox diff measure. The
  containment burden is entirely ours (protocol §3), because the
  harness provides none by default.

## INSTRUMENTED REFERENCE AGENT

The dossier's core for Strands: since there is no policy surface to
read, FinePrint supplies the policy as a **canonical, minimal,
auditable agent** and measures *that agent's* behaviour at the Approval
and Effect layers. The reference agent is a measurement instrument, not
a claim about Strands agents in the wild.

### Canonical minimal agent

```python
# Design sketch — API shapes per strandsagents.com docs retrieved
# 2026-10-22. NOT run; no measurement exists.
from strands import Agent
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands_tools import shell, file_read, file_write  # legacy tools pkg

class PolicyHook(HookProvider):
    """The policy. One hook, three outcomes, nothing else decides."""
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self.decide)

    def decide(self, event: BeforeToolCallEvent) -> None:
        # ... owner-authored checks over event.tool_use["name"] and
        # event.tool_use["input"] (for shell: input["command"]) ...
        # DENY:  event.cancel_tool = "<reason>"
        # ASK:   approval = event.interrupt("<name>", reason={...})
        #        if approval.lower() != "y":
        #            event.cancel_tool = "User denied"
        # ALLOW: return without touching the event

agent = Agent(
    tools=[shell, file_read, file_write],
    hooks=[PolicyHook()],
    # model: BedrockModel by default; see LIVE-UNLOCK below.
)
```

Design rules for the canonical form: (1) exactly **one** policy hook —
no second hook, no intervention, no tool-consent prompt in the measured
configuration, so every Decision/Approval event has exactly one author;
(2) the hook is **pure and total** over `(tool_name, tool_input)` —
no I/O, no randomness, no clock — so its code can be audited line by
line and its behaviour is a function of the call alone; (3) tool set
fixed to the corpus-analogous surface (`shell` for command cases,
`file_write`/`file_read` for path cases). The `HumanInTheLoop`
intervention is the documented alternative ask-mechanism; a measurement
must pin **one** ask mechanism, never both (the legacy tools' own
consent prompts must likewise be pinned OFF — `BYPASS_TOOL_CONSENT`
state recorded — or the run measures two approval systems at once).

### Where DECISION is observed

- **A2-configured analog: audit of the hook code + agent construction.**
  The "configured decision" for a case is read off the pinned
  `PolicyHook.decide` source and the pinned `Agent(...)` construction
  (tools, hooks, interventions, model) — the same epistemic position as
  A2 for other harnesses (labelled evaluation from config + docs),
  except the "config" is Python source. Every case's configured outcome
  (cancel / interrupt / fall-through) must be derivable from the source
  by a reader; if it isn't, the case is **unknown**, not inferred.
- **Evaluability limits (hard):** arbitrary Python hooks are *not*
  evaluable in general — undecidable, environment-sensitive, and
  order-sensitive across multiple hooks (last-write-wins). The
  reference-agent discipline (single, pure, total hook) is what makes
  *this* agent's Decision layer auditable; it transfers to no other
  Strands agent. Any third-party hook in the loop returns the Decision
  layer to **unobservable** (record as unknown with layer attribution).

### Where APPROVAL is observed

- **A3 keystone analog: the interrupt pause, witnessed live.** Under the
  reference design, an "ask" case is one where `decide` calls
  `event.interrupt(...)`: the run must actually stop with
  `result.stop_reason == "interrupt"` and a matching entry in
  `result.interrupts` **before** the tool executes, and the tool must
  execute only after a resume carrying an approving
  `interruptResponse`, or be cancelled (`cancel_tool`) on a denying one.
  That pause-and-resume record is the Approval keystone for Strands —
  the same standard as protocol A3, with the interrupt record as the
  event stream. **No such run exists; A3 is PROPOSED for Strands.**
- **A4 records (what docs establish — no more):** (i) the `AgentResult`
  itself (`stop_reason`, `interrupts`, `message`) is a retrievable
  run artifact; (ii) a `callback_handler` can be attached to the agent
  (examples pass `callback_handler=None` to silence the default
  printing handler) — a recording callback handler is the natural
  local transcript sink, though its exact event payload is **not**
  specified in the pages read and is recorded as partially unknown;
  (iii) hooks themselves can log every event (the docs' logging-hook
  pattern) — an AfterToolCallEvent/BeforeToolCallEvent logging hook is
  *outside* the measured configuration (design rule 1) but is the
  documented way to produce an independent event log in a witness
  driver; (iv) session managers (`FileSessionManager`, S3) persist
  agent/interrupt state across processes (DOC: Interrupts, Session
  Management); (v) OpenTelemetry tracing is a listed SDK feature
  (DOC: quickstart feature table) — trace backends (e.g. CloudWatch
  under AgentCore) are deployment choices, **not** established here as
  an approval record. A4 for Strands = the driver's own capture of
  `AgentResult` + interrupt/resume exchanges, hash-pinned per protocol
  §6; nothing stronger is claimed.

### Where EFFECT is observed

- **What transfers unchanged:** `tools/effect_instrument.py`'s model —
  job-created sentinel assets (`t01/target.txt` … `protected/sub/…`)
  inside a fresh sibling sandbox directory, full before/after sandbox
  diff, outside-sandbox scan, effect classes (`deleted` / `created` /
  `ran-no-effect` / `attempted-not-completed`). Strands tools execute
  on the host filesystem, so a `shell` case's effect is a real
  filesystem effect in exactly the form the instrument records. The
  instrument remains **instrumentation validation**, not a measurement,
  until an agent run drives it.
- **What adapts:** (1) the driver invokes the reference agent with the
  locked case prompts instead of executing commands directly; (2) the
  approval witness (above) is captured per case alongside the diff;
  (3) the run's working directory / tool-visible paths must be pinned
  to the sandbox (tools resolve paths against the host process cwd —
  the driver must start the agent process with cwd = sandbox and use
  absolute sandbox paths in prompts, per protocol §3); (4) legacy-tool
  consent state and `STRANDS_NON_INTERACTIVE` must be pinned and
  recorded, since a tool-level prompt is an approval event the design
  does not intend.

### What remains UNOBSERVABLE

- The Decision of any Strands agent **other than** the pinned reference
  agent (arbitrary code; nothing to read).
- Whether a *cancelled* call would have produced the effect (the model
  may retry differently; per-call cancellation is not a session-level
  guarantee).
- Model behaviour: which tool calls the model emits for a prompt is
  stochastic and provider-dependent; a live run measures *this run's*
  calls, not a policy property. Cases where the model never emits the
  target call record `NOT_TESTED` for that case, never a pass.
- Anything inside MCP servers or remote tools (their execution is
  outside the host process and outside the sandbox diff).
- Guardrail internals on the Bedrock side (redaction is observable in
  the conversation; the guardrail's policy evaluation is AWS-side and
  opaque beyond `guardrail_trace` output, which was not examined).

### Per-layer route table

| Layer | Route | Confidence | Basis |
|---|---|---|---|
| Decision | no paper surface — no D1 (no vendor checker), no D2 (no rule semantics to reconstruct); A2-analog code audit of the pinned reference hook only | low | Single derived route (source audit), no cross-check exists; attaches to OUR verdict per the measurement model |
| Approval | A2 configured (documented interrupt / HITL / consent machinery + pinned reference config); A3 keystone PROPOSED, not run; A4 = driver-captured AgentResult/interrupt records, format per protocol §6 | low | Documented machinery (DOC) but zero witnessed events; one route family only |
| Effect | E1 sentinel state + E2 sandbox diff (protocol-locked design; instrument validated as instrumentation only); E3/E4 not used | low | Instrument proven on direct execution, never yet on a Strands run; no live evidence |

Confidence is in OUR measurement, never a grade of the harness
(measurement model rule). No layer claims `high`; none claims a second
independent agreeing route, because none has been run.

## LIVE-UNLOCK

**LIVE-UNLOCK: A live run needs exactly one working model route plus a local Python 3.10+ environment with `strands-agents==1.62.0` (and `strands-agents-tools` for the reference tool set) installed. Default route: an AWS account with Amazon Bedrock model access enabled for the default model (Claude Sonnet in us-west-2 per the PyPI quickstart) and AWS credentials configured (boto3 chain: AWS CLI profile, or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY [/ AWS_SESSION_TOKEN], or a Bedrock API key), with IAM bedrock:InvokeModel (+ bedrock:InvokeModelWithResponseStream for streaming). No AWS account is strictly required if another provider is pinned instead: an Anthropic API key (AnthropicModel), an OpenAI API key (OpenAIModel), a Gemini API key (GeminiModel), or a local Ollama host — the pinned provider, model id, and region must be recorded in the run config, because a different model is a different measurement.**

## Open questions

1. **Cedar-only reconstructed evaluation** — if the reference agent's
   only gate were `CedarAuthorization` with no custom resolvers/
   enrichers, could Cedar's own engine serve as a D2-style evaluation
   route for the tool-name/argument subset of the catalogue? Would
   resolve: a pinned experiment comparing Cedar engine verdicts against
   the handler's live behaviour; until then Cedar is a substitute
   surface, not a route.
2. **Sandbox routing semantics** — what `Agent(sandbox=...)`
   (DockerSandbox / SSH) actually confines at the pinned versions, and
   whether `shell` under it still presents the same tool name/input to
   `BeforeToolCallEvent`. Would resolve: reading the SDK's sandbox docs/
   source at the pin + a contained probe run.
3. **Callback-handler record format** — the exact event payload a
   recording `callback_handler` receives (needed to fix the A4 record
   format for Strands). Would resolve: API reference / source read at
   the pin.
4. **Tools-package version pin** — the current `strands-agents-tools`
   PyPI version and the exact consent-prompt behaviour of `shell` /
   `file_write` at that version (the repo is mid-deprecation; behaviour
   differs across the transition). Would resolve: pinning the version
   and reading its tool sources.
5. **Interrupt + concurrency** — documented rules say non-interrupted
   concurrent tools execute while one is paused; how that interacts
   with per-case containment (a paused case's siblings still run) needs
   a protocol note before any live run. Would resolve: a design pass
   against the Interrupts doc's concurrency rules.

## Blockers

- **Model-access wall (the only hard blocker):** every live route —
  A3 witnessed approval, E1/E2 effect — needs a model credential (AWS
  Bedrock access or another provider's API key). None is available to
  this spike; no live run was attempted.
- **No offline Decision route exists to unblock:** unlike the CLI
  harnesses, there is no checker to build; the Decision layer for
  Strands is permanently design-stage except via the reference-agent
  code audit.
- **Tools-package transition:** `shell` / `file_write` / `python_repl`
  are deprecated in the tools repo and their SDK-native successors have
  different consent defaults (none, host execution). The reference
  agent's tool pin must be fixed before any run, or runs across the
  transition are not comparable.

## Evidence log

- DOC (strandsagents.com, retrieved 2026-10-22): Hooks (HookProvider /
  HookRegistry / `add_callback(BeforeToolCallEvent, …)`; `cancel_tool`
  in Limit Tool Counts; `selected_tool` in Tool Interception; `tool_use`
  input mutation in Fixed Tool Arguments; callback ordering / HookOrder);
  Hook events reference (mutable properties per event:
  `BeforeToolCallEvent.cancel_tool / selected_tool / tool_use`,
  `BeforeToolsEvent.cancel`, `AfterToolCallEvent.result / retry`);
  Interrupts (`event.interrupt(name, reason)`; `stop_reason ==
  "interrupt"`; `result.interrupts`; `interruptResponse` resume;
  `cancel_tool` / batch `cancel`; session persistence via
  FileSessionManager + `agent.state`; not supported in direct tool
  calls); Interventions (`InterventionHandler.before_tool_call` →
  Proceed/Deny/Guide/Confirm/Transform; registration order; Deny
  short-circuits; precedence deny > confirm > guide > transform >
  proceed; `on_error` throw/proceed/deny; hooks last-write-wins
  contrast); Human in the loop (`HumanInTheLoop` via `Confirm`;
  interrupt/resume, `ask="stdio"`, custom `ask`; `allowed_tools` with
  `"*"` / `"!name"`; LLM `classifier`; `enable_trust` in `agent.state`;
  `evaluate` default True/"y"/"yes"); Cedar Authorization
  (`CedarAuthorization(policies=...)`; Action = tool name;
  `context.input` = tool arguments; default-deny; fail-closed on
  unresolvable principal; `.cedar` files; schema validation);
  Amazon Bedrock provider (`BedrockModel` is the default provider;
  AWS account + credentials + `bedrock:InvokeModel[WithResponseStream]`
  prerequisites; Guardrails config keys and input/output redaction
  behaviour); Model Providers (Bedrock / OpenAI / Anthropic / Gemini /
  others; `OpenAIModel(client_args={"api_key": ...})` pattern);
  Quickstart feature table (OpenTelemetry integration; session
  managers).
- REPRO (official repos / PyPI, retrieved 2026-10-22):
  `github.com/strands-agents/sdk-python` redirects to
  `strands-agents/harness-sdk` (HEAD `8916c9fa…`); README: "it runs in
  your process with no hosted control plane"; docs home =
  strandsagents.com; `pip install strands-agents strands-agents-tools`;
  PyPI `strands-agents` 1.62.0 (files uploaded 2026-10-21); PyPI note:
  default Bedrock provider needs AWS credentials + model access for
  Claude 4 Sonnet in us-west-2; `github.com/strands-agents/tools`
  (HEAD `4e9d5ea4…`) README: tools table (`shell`, `file_write`,
  `python_repl` marked deprecated; `code_interpreter` = AgentCore
  isolated sandbox), env table (`BYPASS_TOOL_CONSENT` default false —
  shell/file_write/python_repl; `STRANDS_NON_INTERACTIVE` — shell/
  python_repl prompts), deprecation notes (SDK `python_repl`: host
  execution, no isolation, no confirmation prompt by default; optional
  `sandbox=` e.g. DockerSandbox; shell sandbox-routed).
- INFERENCE: the route assignment (no paper surface) and the
  reference-agent design are this spike's inferences on the DOC+REPRO
  record above. Nothing in this assessment is a measurement.
