# CrewAI — Testability Assessment (2026-10-22)

*Design-stage spike only: no measurement run, no corpus evaluation, no
results.json. No account created, no login performed, no install, no live
run, nothing published, no outreach, no commits. This assessment designs
the instrumented-reference-agent measurement for a later, separately
authorized live wave; it reports NO conformance verdicts.*

**Naming note (explicit):** this assesses **CrewAI the open-source Python
framework** (`crewAIInc/crewAI`, PyPI `crewai` + `crewai-tools`) — role /
goal / backstory agents, Tasks, Crews, and Flows, run in the user's own
Python process. It is NOT CrewAI's hosted commercial platform (CrewAI AMP,
formerly "CrewAI Enterprise"), a different surface with its own console,
RBAC, and hosted HITL routing. Platform features are noted separately,
only where official docs establish them, and are never attributed to the
OSS framework.

## Surface assessed

- **Product:** CrewAI OSS framework — `crewai` (agents / tasks / crews /
  flows runtime) + `crewai-tools` (tool library, incl.
  `CodeInterpreterTool`, file tools, scraping/search tools)
- **Version pinned for this spike:** **1.15.28** — latest release on the
  official repo at retrieval (DOC/REPRO: github.com/crewAIInc/crewAI
  release "Release 1.15.28"; release notes reference AMP deploy behaviour
  and "preserve native tool aborts and post-hook cache identity").
  Framework versioning matters: the hook system, Flow `@human_feedback`
  (1.8.0+), and guardrail surface have all moved across 1.x; every claim
  below is pinned to the 1.15.x docs snapshots cited.
- **Canonical homes (verified from the repo):** code
  github.com/crewAIInc/crewAI (DOC: repo README — "The site at
  docs.crewai.com is published from `docs/`"); docs **docs.crewai.com**
  (versioned snapshots, e.g. `/v1.15.28/en/...`, `/v1.15.17/en/...`,
  `/v1.15.10/en/...` — the version in each cited URL is the snapshot
  actually read).
- **Docs consulted (fetched 2026-10-22, all DOC unless noted):**
  "Human Input on Execution" (v1.15.17), "Tool Call Hooks" (v1.15.10),
  "Execution Hooks" (v1.15.18), "LLM Call Hooks" (v1.15.15), "Human
  Feedback in Flows" (v1.15.28), "Connect to any LLM" / LLM connections
  (v1.15.28), "Coding Agents" (v1.15.28), Tasks concepts material via
  `docs.crewai.com/llms-full.txt` (task guardrails), `CodeInterpreterTool`
  tool page (via the repo's `docs/en/tools/ai-ml/codeinterpretertool.mdx`),
  Crews concepts (CrewOutput, v1.15.18), GitHub release 1.15.28.
- **No binary/package inspection:** per the spike's hard limits nothing
  was installed or executed; unlike the CLI harnesses there is no binary
  to inspect — CrewAI is a library imported into the user's own program.
  Every behavioural claim below is DOC (official docs / repo), labelled
  as such; nothing is REPRO.

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO**

- CrewAI has **no declarative policy surface at all**: no policy file, no
  allow/ask/deny rule language, no permissions config that a checker could
  evaluate (DOC: full docs surface consulted — agents / tasks / crews /
  flows / hooks / tools; no policy artifact appears anywhere). There is
  therefore nothing for a `codex execpolicy check` or `amp permissions
  test` analogue to read, and no such entrypoint exists.
- What decides about a tool action before it runs is **imperative Python
  code the program author writes** — tool-call hooks (below). Arbitrary
  user code is not interrogable offline: its decision for a given call
  depends on the hook body, runtime state, and the model-chosen tool
  input, none of which a paper test can evaluate. (Same ceiling the
  Claude Code assessment records for PreToolUse hooks.)
- Consequence, stated plainly: **the Decision layer is unreadable by the
  paper routes (D1/D2). Route: no paper surface.** Any Decision-layer
  statement about CrewAI can only come from a live, instrumented run
  (the reference-agent design below), never from an offline evaluation.

### (b) Documented semantics precise enough for an honest reconstructed route? — **NO** (for Decision)

- A reconstructed route needs a documented *rule-matching* semantics to
  evaluate. CrewAI documents no rule language, no matching, no precedence
  operator, and no no-match default for tool actions — because there are
  no rules. The documented semantics that DO exist are runtime mechanics
  (hook chain order, block behaviour, guardrail retry loop, human-input
  timing), which specify how a live run behaves, not what a policy
  decides. Evaluating them offline would mean re-implementing the
  author's hook code and presenting the result as the framework's
  decision — exactly what this program forbids.
- What the docs DO pin precisely enough to *design* a live measurement
  (not to evaluate one): hook interception points and fail-open
  behaviour, `human_input` timing, guardrail signature and retry bound,
  `@human_feedback` pause/resume, tool execution locality, and the event
  / output records a run leaves behind. Those are the inputs to the
  instrumented-reference-agent design in this dossier.

### (c) Surface record — the "no paper surface" record

- **Surface:** a Python library. An `Agent` (role / goal / backstory,
  `tools=[...]`, `llm`, `allow_code_execution`, `allow_delegation`,
  `max_iter`, …), a `Task` (description, expected_output, agent,
  optional `tools`, `guardrail` / `guardrails`, `guardrail_max_retries`,
  `human_input`, `callback`, `output_file`, `output_pydantic` /
  `output_json`), a `Crew` (agents, tasks, `Process.sequential` or
  `Process.hierarchical`, `kickoff()`), and optionally a `Flow`
  (`@start` / `@listen` / `@router`, `@human_feedback`) wrapping crews in
  deterministic Python control flow (DOC).
- **Defaults that matter:** with no hooks registered, **no tool call is
  gated by anything** — the model chooses a tool from the agent's
  assigned set and the framework executes it. There is no default ask,
  no default deny, and no no-match concept: silence is not a decision,
  it is the absence of machinery. Framework mapping: every un-hooked
  action is **unknown at the Decision layer** (INV-005 discipline —
  never allow), governable only at the Effect layer.
- **The only scoping that exists by default is tool assignment:**
  `Agent(tools=[...])`, narrowed per-task by `Task(tools=[...])` which
  overrides the agent's set for that task (DOC). This is *scoping* —
  which tools the model can see — not a policy decision about an action:
  it has no per-call verdict, no argument inspection, no ask state. It
  is recorded here as model-visibility, never as a Decision-layer rule.
- **No verdicts are issued.** This spike records the surface, its
  defaults, and the absence of a decision route, per the (c) discipline.

## Decision surface — what, if anything, decides about a tool action before it runs

**Short answer: nothing declarative; optionally, author-written hook code.**

1. **Tool-call hooks — the one real action-side control (DOC).** Hooks run
   at `PRE_TOOL_CALL` (before every tool execution) and `POST_TOOL_CALL`
   (after, with results set), written with the unified `@on` decorator;
   the legacy `@before_tool_call` / `@after_tool_call` decorators register
   on the same engine in one ordered chain. A pre-hook receives
   `ToolCallHookContext` (`tool_name`, mutable `tool_input`, `tool`,
   `agent`, `task`, `crew`) and can inspect/modify inputs and **block**:
   legacy style `return False`, `@on` style raise `HookAborted(reason,
   source)`. When blocked, *"the tool does not run and the agent receives
   `"Tool execution blocked by hook. Tool: <name>"` as the result — the
   run continues"*; `POST_TOOL_CALL` hooks still fire on blocked calls.
   Registration: global (`register_before_tool_call_hook(...)` /
   decorators, with `tools=` / `agents=` filters), or crew-scoped inside
   a `@CrewBase` class. The docs' own use-case list includes "Safety
   Guardrails" and "Human Approval Gate" — action-side control is a
   documented, intended use.
2. **Composition semantics (DOC, Execution Hooks):** multiple hooks on a
   point run in **registration order**, globals first, then
   execution-scoped; the (possibly mutated) payload flows hook to hook;
   `HookAborted` propagates and stops the chain. **Critical ceiling:**
   *"Any other exception raised by a hook is swallowed (fail-open) so a
   single buggy hook can't crash a run"* — a hook that errors does NOT
   block the call. Any measurement of a hook-carried invariant must
   therefore treat hook-code correctness as part of the system under
   test, and a hook exception during a live run is a finding, not noise.
3. **What hooks are not:** they are not a policy. There is no rule file
   to audit as data, no precedence between "rules" (only code order), no
   way to ask the framework what it *would* decide, and no guarantee a
   given crew registers any hook at all. The Decision a hook makes is a
   property of *that program*, not of CrewAI.
4. **LLM-call hooks (DOC)** intercept at `PRE_MODEL_CALL` /
   `POST_MODEL_CALL` with the same machinery (blocking a model call
   raises inside the executor). They govern model calls, not tool
   actions; recorded for completeness, not a Decision surface for tool
   use.
5. **Task guardrails are NOT a Decision surface** — they validate task
   *outputs* after execution (next-but-one section). Dressing them up as
   action-side policy would be a category error, and this assessment
   does not.
6. **No permission / allowlist concept exists** beyond tool assignment
   (above) and hook `tools=` filters (which select which calls a hook
   sees, not whether they may run). (DOC; absence verified across the
   consulted surface — stated as "none found in the official docs read
   for this spike," not as a proof about every page.)

## Approval machinery

CrewAI has **three** distinct human-ask points. They differ in the one
way that matters for Layer 2: *when* the human is asked relative to the
effect.

### 1. Task-level `human_input` — post-execution output review (DOC)

- `Task(..., human_input=True)`: *"set the `human_input` flag in the task
  definition. When enabled, the agent prompts the user for input **before
  delivering its final answer**. This input can provide extra context,
  clarify ambiguities, or **validate the agent's output**."*
- **Timing finding, stated plainly: this is a review of a task's OUTPUT
  after the task — including every tool call the agent made to produce
  it — has already executed.** Tool effects (file writes, code execution,
  API calls) are already in the world when the human is asked. The human
  can add context / corrections that shape the final answer (and, in a
  sequential crew, downstream tasks), but cannot pre-approve, veto, or
  undo the tool actions that already ran. **`human_input` is not
  pre-execution approval of a tool action, and no CrewAI doc claims it
  is.** Any mapping of `human_input` to an Approval-layer "ask before
  the action" would be false.
- Mechanics (DOC): console prompt at task completion; the response is
  free-form input folded into the task's result before it is delivered
  downstream. What the human *cannot* do at this point: block a specific
  tool call, edit tool arguments, or roll back effects. (A webhook-based
  variant for crews — task pauses in a "Pending Human Input" state until
  feedback is submitted via callback — is described in the platform HITL
  guide; same post-task timing, different transport. Platform section
  below.)

### 2. Flow `@human_feedback` — a step boundary gate (DOC, 1.8.0+)

- `@human_feedback(message=..., emit=[...], llm=..., default_outcome=...,
  provider=...)` on a Flow method: the method executes, its output is
  presented, execution **pauses**, feedback is collected, and with `emit`
  an LLM collapses the free-form feedback into one of the named outcomes
  which routes to matching `@listen` handlers (approve / reject / revise
  loops are the documented pattern). Feedback is recorded:
  `flow.last_human_feedback`, `flow.human_feedback_history`. Async /
  non-blocking providers (Slack, webhooks, custom
  `HumanFeedbackProvider`) make `kickoff()` return `HumanFeedbackPending`
  and resume later via `resume()` / `from_pending()`, with state
  persisted (SQLite by default).
- **Timing:** this DOES gate what happens *next* — a Flow can place the
  decorator on a step that precedes a side-effecting step, so the human
  approves before the effect step runs. But the gate is at **Flow-step
  granularity, placed by the program author**, not at tool-action
  granularity: inside the preceding crew run, tool calls already
  executed ungated; inside the following step, they will again. It is a
  workflow checkpoint, not a per-action approval.

### 3. Hook `request_human_input` — the only true pre-action ask (DOC)

- `ToolCallHookContext.request_human_input(prompt, default_message)`
  (also on the LLM-call context): *"pauses live console updates and
  collects input from the terminal — useful for approval gates."*
  Called inside a `PRE_TOOL_CALL` hook, this is the **only documented
  mechanism that asks a human about a specific tool action before that
  action runs** — and it exists only if the author writes a hook that
  calls it and blocks on a negative answer. It is console-terminal input
  in the OSS framework (no routing, no timeout policy, no record format
  of its own); anything richer is the author's code or the platform's.

### Approval-layer summary

| Ask point | Asked when | Can it stop the specific action? | Authored as |
|---|---|---|---|
| `Task(human_input=True)` | After the task's tool calls ran, before the final answer is delivered | **No** — effects already happened | Task flag |
| Flow `@human_feedback` | After a Flow step, before routed next steps | Steps only, not tool actions inside a step | Decorator on a Flow method |
| Hook `request_human_input` in `PRE_TOOL_CALL` | Before that tool call runs | Yes — if the hook blocks on the answer | Imperative hook code |

## Task guardrails — output-side validation (kept distinct, per the brief)

(DOC, Tasks concepts / `llms-full.txt`.) A task guardrail is a callable
`fn(result: TaskOutput) -> Tuple[bool, Any]` attached via
`Task(guardrail=fn)` (plural `guardrails=[...]` also exists in current
versions; `LLMGuardrail` / `HallucinationGuardrail` are LLM-backed
variants). It runs **after the agent produces the task output**: on
`(True, result)` the (possibly transformed) result is accepted; on
`(False, error)` the error is fed back to the agent and the task retries,
bounded by `guardrail_max_retries` (default 3 in the Tasks docs). Two
consequences the measurement design must respect: (1) a guardrail
**cannot prevent a tool effect** — by the time it sees anything, the
task's tools have run; it validates text, not actions. (2) **Retries
re-run the task**, so a guardrail-rejected attempt may repeat tool side
effects (no per-tool-call completion record is documented) — an Effect-
layer hazard the reference-agent containment must assume by default.

## Effect surface — where tool actions actually land

- **In-process by default (DOC/INFERENCE on DOC).** CrewAI is a library;
  `crewai-tools` tools execute as Python calls in the user's own process
  and environment, with that process's filesystem, network, and
  credential access. File tools (`FileReadTool`, `FileWriterTool`,
  `DirectoryReadTool`, …) operate on the local filesystem; search /
  scraping tools call their external APIs directly. There is no
  framework sandbox around ordinary tools, and no OS-level confinement
  layer in the OSS framework's documented surface.
- **`CodeInterpreterTool` sandboxing reality (DOC, tool page):** three
  execution strategies, selected at runtime and logged to STDOUT —
  (1) **Docker container (recommended, primary):** code runs in an
  isolated Docker container, *"ensuring safety regardless of its
  content"* — requires Docker installed and running; (2) **restricted
  Python "sandbox" environment** if Docker is unavailable — *"very
  limited, with strict restrictions on many modules and built-in
  functions"* (an in-process restricted interpreter, not an OS sandbox);
  (3) **unsafe mode** (`CodeInterpreterTool(unsafe_mode=True)`,
  "NOT RECOMMENDED FOR PRODUCTION"): unrestricted execution, *"including
  dangerous calls to `sys, os..`"* — i.e. full host-process authority.
  Which strategy a given run used is an empirical question (the tool logs
  it); a measurement must record it, never assume Docker.
- **`allow_code_execution=True` on an Agent** *"automatically adds the
  CodeInterpreterTool"* (DOC) — code execution is one flag away from any
  agent, with the sandboxing reality above.
- **No generic shell tool was found** in the official `crewai-tools`
  surface consulted: arbitrary command execution arrives via
  `CodeInterpreterTool` (Python payloads, which can themselves invoke
  `os`/`subprocess` in unsafe mode), via author-written custom tools
  (`BaseTool` subclass or `@tool` decorator — arbitrary Python by
  definition), or via MCP servers attached through `MCPServerAdapter`
  (stdio/SSE). For the catalogue's command-shaped invariants, the
  "command" in CrewAI is therefore a *tool call with a payload*, and the
  reference agent below is built accordingly.
- **Delegation widens the effect surface:** `allow_delegation=True` gives
  an agent collaboration tools to hand work to other agents (DOC) — an
  action chosen by a model, governed by no rule; recorded as part of the
  Effect surface, not a control.

## Platform note — CrewAI AMP / Enterprise (separate surface, DOC only)

Official Enterprise docs (fetched via the repo's docs tree) establish,
for the **hosted platform only**: an email-first HITL system for Flow
`@human_feedback` (responders reply by email, no login; dashboard
review; routing to specific emails by method pattern or flow state;
automatic fallback responses on timeout / SLA), a webhook-based HITL
approach for crews (task enters "Pending Human Input" until feedback is
submitted), plus console-side governance claims on crewai.com (RBAC,
audit trails, tracing). **None of this is in the OSS framework's
documented surface, none of it changes the OSS timing findings above
(the platform HITL wraps the same post-task / step-boundary pauses), and
none of it is assessed further here.** The canonical target of this
spike is the OSS framework.

## INSTRUMENTED REFERENCE AGENT — the measurement design

Since there is no paper surface, the only honest measurement is a live
one against a **canonical minimal crew that we author and instrument** —
the framework analogue of pinning a config. The crew definition *is* the
pinned artifact: version-pinned framework, fixed code, fixed tools, so a
later run's findings attach to (framework version × this crew × this
hook set × this model), never to "CrewAI" in general.

### The canonical minimal crew (design; NOT built or run in this spike)

- One `Agent` (sequential `Crew`, one `Task`) whose task instruction
  directs it to carry out the case action. The agent is given exactly
  the dangerous tools in scope, each a thin, logged wrapper around a
  real `crewai-tools` primitive so the case's effect is real but
  contained:
  - `CodeInterpreterTool` — the arbitrary-code / delete / egress carrier
    (its `code` input is where `rm`-shaped, deploy-shaped, and
    fetch-shaped payloads actually arrive in this framework);
  - `FileWriterTool` / `FileReadTool` — direct local-filesystem effects
    (protected-path and credential-read cases);
  - one author-defined custom tool standing in for the catalogue's
    named binaries (`<deploy_bin> <action_args> <environment>`,
    `<db_cli> -c "<destructive_verb> <database_name>"`) that logs its
    argv-shaped input and performs only the contained sandbox effect —
    because CrewAI has no shell, the corpus's command forms translate
    to *tool-call forms*, and the translation is part of the design
    record, not a silent substitution.
- The task carries `human_input` OFF by default (it cannot gate
  anything; a variant run with it ON exists only to demonstrate the
  post-effect timing empirically). No guardrail on the measurement task
  (guardrails would add retry-repeated effects); a separate variant may
  add one to measure the retry-repetition hazard.
- Containment is the approval-effect protocol's §3 verbatim: fresh
  sandbox sibling directory outside the tracked tree, job-created
  sentinel assets only, no network beyond the model route, no real
  credentials, any uncontainable case skipped and recorded.

### Where DECISION is observed

- **There is no Decision to observe in the framework.** What is observed
  instead, as the A2-configured analog: a **static audit of the crew
  source** — which tools are assigned (scoping), whether any
  `PRE_TOOL_CALL` hook is registered, its filters, and its code path for
  the case's tool/input. The audit yields a *configured expectation*
  (`hook-would-block | hook-would-ask | no-hook — ungated`), labelled
  evaluation of our own reference program, never a framework verdict.
- **Limits, stated once and binding:** the expectation is only as good
  as the hook code we wrote; hook fail-open (non-`HookAborted`
  exceptions swallowed) means "hook-would-block" can silently degrade
  at runtime; model-chosen tool inputs are stochastic, so the audited
  path may not be the path taken. Decision confidence can therefore
  never exceed what the live routes corroborate.

### Where APPROVAL is observed

- **A3-analog (witnessed live):** the run's own records showing an ask
  actually pausing execution. Two ask points are witnessable in the
  reference design: (i) a `PRE_TOOL_CALL` hook calling
  `request_human_input` before a gated tool call — the only true
  pre-action ask, present only in the hook-carrying variant of the crew;
  (ii) the `human_input` pause — witnessed, but recorded with its honest
  timing: **the pause occurs after the task's tool effects, so as
  Approval evidence it witnesses a post-effect review, not an approval
  of the action.** A run that reports (ii) as if it were (i) would be
  a false Approval claim; the witness record must carry the timing.
  Non-interactive construction per protocol: the keystone is the
  machinery's pause appearing in the run record, not a human clicking.
- **A4-analog (recorded):** `CrewOutput` (`raw`, `tasks_output`,
  `token_usage`) returned by `kickoff()`; the framework event bus
  (`CrewAIEventsBus`) tool-usage / task events and hook telemetry
  (`HookDispatchedEvent` carries abort reason/source); console /
  verbose logs; Flow runs additionally leave `human_feedback_history`.
  These are the artifacts a witness driver would hash-pin. (Event-bus
  specifics beyond the hook-telemetry and CrewOutput records are DOC-
  level here; exact event schemas are an open question below.)

### Where EFFECT is observed

- **Direct transfer:** `tools/effect_instrument.py` applies unchanged
  in shape — the job creates the sentinel assets (`t01/target.txt` …
  `protected/sub/target.txt`) inside the per-harness sandbox, snapshots
  before/after (E1 sentinel state, E2 sandbox diff), and scans outside
  the sandbox for attributable changes. The instrument's discipline
  transfers verbatim: its output is instrumentation validation, and a
  harness Effect claim comes only from the agent run inside the same
  sandbox design.
- **What adapts:** (1) case commands become **case prompts** — the agent
  is instructed to perform the action with its assigned tools (the
  protocol's live-case form: "perform exactly this action and nothing
  else"); whether the model complies, and via which tool/payload, is
  itself recorded (a refusal or a different tool choice is a result,
  not a failed run — but it is an *agent* result, attributed to the
  pinned model + crew, per the config-pinning caveat). (2) For
  `CodeInterpreterTool` cases the run record must include **which
  execution strategy the tool selected** (Docker / restricted sandbox /
  unsafe — it logs this to STDOUT), because the same payload has three
  different effect envelopes; a Docker-contained delete that never
  touches the host sandbox is "contained by the tool's sandbox," a
  different finding from "blocked by a hook." (3) Guardrail-retry
  variants must diff *per attempt* where possible, since retries can
  repeat effects.
- **E3/E4:** OS-level tracing (E3) is route-proposed program-wide and
  unchanged here; the agent's self-report (E4 — its final answer and
  `CrewOutput.raw`) is collected but never sufficient alone, per the
  model.

### What remains UNOBSERVABLE (by these methods)

- Any Decision-layer verdict: there is no decision to read, on paper or
  live — only configured expectations (our code) vs witnessed behaviour.
- Whether a hook *would have* blocked an input the model never produced.
- Effects inside a Docker container that never mount the sandbox
  (observable only as "no host effect," with the strategy log as the
  attribution).
- The model's reasons for choosing/refusing a tool (self-report is E4,
  weakest route).
- Anything about crews other than the pinned reference crew — other
  authors' hooks, tools, and flows are other programs, other
  measurements.

### Per-layer route table

| Layer | Route | Confidence | Basis |
|---|---|---|---|
| Decision | **no paper surface** — no D1 (no vendor checker), no D2 (no documented rule semantics to reconstruct); live substitute = source audit of the pinned reference crew (A2-configured analog) | low | No declarative policy surface exists in the official docs/repo surface consulted (DOC); the only pre-execution control is arbitrary author code (hooks), unevaluatable offline |
| Approval | A2 configured (hook registration + `human_input` / `@human_feedback` configuration, from docs + crew source); A3 witnessed-live and A4 recorded = PROPOSED in this design, no evidence yet | low | One route designed (A2-analog), keystone (A3) not run; `human_input` timing is DOC-established but witnesses only a post-effect review |
| Effect | E1 sentinel state + E2 sandbox diff (protocol-locked program-wide; instrument validated as instrumentation, not as a harness measurement); E4 self-report collected, never sufficient | low | Routes transfer by design; no CrewAI run has executed under them — zero live evidence exists |

Confidence attaches to OUR measurement, per the model; "low" throughout
because at most one route is even designed per layer and no live route
has run. Nothing here is "medium": no second independent route agrees
with anything yet.

## LIVE-UNLOCK line

> **LIVE-UNLOCK: a live reference-agent run needs exactly one LLM credential for the pinned model route — by default an `OPENAI_API_KEY` (CrewAI's default provider route is OpenAI when no `llm` is configured), or the key for whichever single provider the pinned crew configures instead (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, Azure / Bedrock credentials, etc. — native SDK routes for OpenAI, Anthropic, Google Gemini, Azure, AWS Bedrock; all other providers via LiteLLM with that provider's key). A no-cloud-key route is documented: a local model via Ollama (`LLM(model="ollama/<model>", base_url="http://localhost:11434")`) needs no API key, only a locally running Ollama with the model pulled. Tool-side keys are needed only for tools that call keyed APIs (e.g. `SERPER_API_KEY` for SerperDevTool) — the reference crew's contained tools (CodeInterpreterTool, file tools, custom sandbox tool) need none; CodeInterpreterTool's Docker strategy additionally needs Docker installed and running, or the run falls back to the restricted sandbox and that fallback is part of the record.**

## Open questions (what would resolve them)

1. **Hook coverage completeness** — do `PRE_TOOL_CALL` hooks fire for
   *every* tool path (custom tools, MCP-adapter tools, delegation
   tools, the automatically added `CodeInterpreterTool`)? Docs say
   "before every tool execution" for agent tool calls; MCP/delegation
   coverage is not explicitly established in the pages read. Resolved
   by: an official docs statement, or a live probe per tool path.
2. **Exact event/record schemas** for the A4 route — the
   `CrewAIEventsBus` event taxonomy and payloads (tool-usage events,
   hook dispatch events) at the pinned version. Resolved by: the
   official event-listener docs at the pin, read in full before any
   witness driver is written.
3. **CodeInterpreterTool strategy selection** — the precise fallback
   order and whether the strategy can be pinned by configuration (vs
   environment-dependent). Resolved by: the tool's repo source/docs at
   the pin.
4. **`human_input` in non-interactive runs** — behaviour when no TTY is
   attached (block, skip, default?) is not established in the page read;
   the witness design depends on it. Resolved by: docs or a contained
   probe.
5. **Guardrail plural surface** — `guardrail` vs `guardrails=[...]`
   composition (order, short-circuit) at the pin. Resolved by: the
   Tasks concepts page at the pinned snapshot, read in full.
6. **Crew (non-Flow) webhook HITL in OSS** — whether the webhook-based
   crew HITL described in the platform guide exists in the OSS framework
   or is platform-provided. Resolved by: an OSS docs page or repo source
   reference; until then it is recorded as platform-only.

## Blockers

- **Auth wall for the keystone routes:** A3/E1/E2 need a live run; a
  live run needs an LLM credential (or a local Ollama setup) — none is
  available to this spike, and none was sought (hard limits). Blocked
  is the valid outcome; the design above is written so the first
  unblocked run needs no further design work.
- **No paper route exists to fall back on:** unlike the CLI harnesses,
  there is no offline evaluation to ship in the meantime — Decision
  stays unreadable until a live run happens. This is a property of the
  target, not a gap in effort.
- **Stochastic subject:** tool choice and tool inputs are model-chosen;
  per-case results attach to the pinned (version × crew × hooks ×
  model) tuple and do not generalize beyond it.

## Evidence log

- DOC (fetched 2026-10-22): docs.crewai.com "Human Input on Execution"
  (v1.15.17) — *"set the `human_input` flag in the task definition. When
  enabled, the agent prompts the user for input before delivering its
  final answer… validate the agent's output."*
- DOC (fetched 2026-10-22): docs.crewai.com "Tool Call Hooks" (v1.15.10)
  — `PRE_TOOL_CALL` / `POST_TOOL_CALL` points, `@on` + legacy
  `@before_tool_call` / `@after_tool_call` on one ordered chain, block
  semantics (*"the tool does not run"*; agent receives "Tool execution
  blocked by hook"), `ToolCallHookContext` incl. `request_human_input`
  ("useful for approval gates"), registration (global / crew-scoped,
  `tools=` / `agents=` filters), use cases "Safety Guardrails" / "Human
  Approval Gate," best practice "Abort loudly — … any other exception is
  swallowed (fail-open)."
- DOC (fetched 2026-10-22): docs.crewai.com "Execution Hooks" (v1.15.18)
  — composition: registration order, globals first; `HookAborted`
  propagates; other exceptions swallowed (fail-open); boundary / step /
  model / tool points table.
- DOC (fetched 2026-10-22): docs.crewai.com "Human Feedback in Flows"
  (v1.15.28) — `@human_feedback` parameters (`message`, `emit`, `llm`,
  `default_outcome`, `provider`, `learn`…), pause → feedback →
  `HumanFeedbackResult` routing, `last_human_feedback` /
  `human_feedback_history`, async providers, `HumanFeedbackPending` +
  `resume()`, SQLite persistence default.
- DOC (fetched 2026-10-22): docs.crewai.com "Connect to any LLM"
  (v1.15.28) — native SDK providers (OpenAI, Anthropic, Google Gemini,
  Azure, AWS Bedrock), LiteLLM fallback (incl. Ollama), `LLM` class
  parameters (`model`, `base_url`, `api_key`, …), "Using Local Models
  with Ollama"; LLMs concepts page — Ollama local route
  (`ollama run llama3`).
- DOC (fetched 2026-10-22): docs.crewai.com "Coding Agents" (v1.15.28) —
  `allow_code_execution=True` enables agent code execution; requires
  `crewai_tools`.
- DOC (fetched 2026-10-22): repo docs source
  `docs/en/tools/ai-ml/codeinterpretertool.mdx` (via glama.ai mirror of
  crewAIInc/crewAI) — Docker container (recommended) / restricted Python
  sandbox fallback / `unsafe_mode=True` ("NOT RECOMMENDED FOR
  PRODUCTION", `os.system` example), strategy logged to STDOUT,
  `allow_code_execution=True` "automatically adds the
  CodeInterpreterTool."
- DOC (fetched 2026-10-22): docs.crewai.com Tasks guardrail material via
  `llms-full.txt` + concepts summaries — guardrail signature
  `(result: TaskOutput) -> Tuple[bool, Any]`, attached as
  `Task(guardrail=...)`, `(False, error)` → error fed back → retry until
  pass or `guardrail_max_retries`; best-practices page: "Use Task
  Guardrails to validate task outputs before they are accepted."
- DOC (fetched 2026-10-22): docs.crewai.com "Crews" (v1.15.18) —
  `CrewOutput` attributes (`raw`, `pydantic`, `json_dict`,
  `tasks_output`, `token_usage`).
- DOC (fetched 2026-10-22): repo `docs/en/enterprise/guides/
  human-in-the-loop.mdx` (via glama.ai mirror of crewAIInc/crewAI) —
  platform HITL: Flow-based `@human_feedback` (1.8.0+) with Enterprise
  email-first system, routing, auto-response fallback; webhook-based
  approach (all versions), task "Pending Human Input" state. Recorded
  as PLATFORM surface only.
- REPRO/DOC (fetched 2026-10-22): github.com/crewAIInc/crewAI release
  1.15.28 page — version pin; repo README via search index — docs
  published from `docs/` to docs.crewai.com, directory-based versioning.
- NOT DONE (by design): no install, no import, no run, no account, no
  login. No hook, guardrail, or human-input behaviour was executed;
  every behavioural claim above is DOC and is labelled as such.
