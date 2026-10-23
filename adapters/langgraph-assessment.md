# LangGraph — Testability Assessment (2026-10-22)

*Design-stage spike only: NO measurement run, no corpus evaluation, no
results.json. No account created, no login performed, no package installed,
no live agent run, nothing published, no outreach, no commits. This is a
FRAMEWORK target: there is no harness binary and no declarative policy
oracle — the dossier's core is the instrumented-reference-agent design in
the dedicated section below.*

**Naming note (explicit):** this assesses **LangGraph** — the open-source
low-level orchestration framework/runtime (`github.com/langchain-ai/langgraph`,
PyPI `langgraph`) — **plus the LangChain agent stack built on it**
(LangChain's `create_agent`, whose runtime is LangGraph), because the
human-in-the-loop approval machinery an evaluator would actually use ships
in that stack. It is NOT LangSmith Deployment / LangGraph Platform / Studio
(the hosted deployment + IDE surface; noted separately below, never the
canonical surface), and NOT Deep Agents (a higher-level harness built on
LangGraph).

## Surface assessed

- **Product:** LangGraph (Python) — "a low-level orchestration framework
  and runtime for building, managing, and deploying long-running, stateful
  agents" (DOC: LangGraph overview, docs.langchain.com). LangChain is "the
  agent framework"; LangGraph is "the orchestration runtime: durable
  execution, streaming, human-in-the-loop, and persistence" (DOC: overview,
  "how LangChain products fit together").
- **Version pinned (design-stage, from primary metadata only — nothing
  installed or run on this machine):** `langgraph` **1.2.16** (DOC/REPRO:
  PyPI project JSON, `release_url https://pypi.org/project/langgraph/1.2.16/`,
  `requires_python >=3.10`, MIT). LangGraph v1 "is a stability-focused
  release for the agent runtime. It keeps the core graph APIs and execution
  model unchanged" and deprecates the LangGraph `create_react_agent`
  prebuilt in favour of LangChain's `create_agent` (DOC: "What's new in
  LangGraph v1"). LangChain-side version floors cited below are the docs'
  own: the HITL `when` predicate "Requires `langchain>=1.3.3`" and
  `interrupt_mode="per_call"` "requires `langchain>=1.4.6`" (DOC: HITL).
- **Docs home (verified):** the repo README's Documentation section points
  to **docs.langchain.com** ("Comprehensive documentation, including
  conceptual overviews and guides") and **reference.langchain.com/python/langgraph**
  (API reference) (DOC: github.com/langchain-ai/langgraph README, retrieved
  2026-10-22). The older `langchain-ai.github.io/langgraph` home is
  superseded by docs.langchain.com for the current docs; it is not cited
  as a source here.
- **Sources consulted (all primary, retrieved 2026-10-22):** repo README;
  PyPI `langgraph` project JSON; docs.langchain.com — LangGraph overview,
  Interrupts, Persistence, Checkpointers, LangChain Human-in-the-loop,
  Custom middleware, Tools, "What's new in LangGraph v1", LangChain v1
  release notes (middleware list); reference.langchain.com middleware
  index (class list). Full log at the end.

## Spike answers

### (a) Deterministic, offline decision oracle? — **NO**

- There is nothing to interrogate. LangGraph ships **no declarative
  policy surface at all**: no policy file format, no allow/ask/deny rule
  language, no permission config, and therefore no check/evaluate/dry-run
  entrypoint that could answer "what does this policy decide for this
  command" (DOC: the full documented surface is graphs, nodes, edges,
  state, checkpointers, stores, interrupts, streaming — overview /
  persistence / checkpointers pages contain no policy or permission
  construct).
- What a CLI-only harness calls a "decision" is, here, two different
  things, neither of them an oracle: (i) the **model's** tool choice at
  runtime (stochastic, provider-side, not a policy function), and (ii)
  whatever the **application code the owner wrote** does — graph routing,
  middleware hooks, `interrupt_on` configuration, tool bodies. Both are
  *program behaviour*, not a vendor decision surface.
- Determinism demo is N/A: there is no decision function to replay.

### (b) Documented semantics precise enough for an honest reconstructed route? — **NO for the Decision layer; YES for a narrower Approval-configured analog**

- **Decision layer: NO.** A reconstructed route needs documented
  *matching semantics* — a rule format, a matcher, precedence, a no-match
  default — to reimplement. LangGraph documents none, because there is no
  rule engine to document. An evaluator who "reconstructed" a Decision
  verdict here would be inventing the policy language, the matcher, and
  the verdict — fabrication, not evaluation. This is the honest (c)
  answer for Decision, given in full below.
- **Approval layer: a bounded YES, and it is not a Decision route.** The
  HITL machinery's *configured* behaviour is documented precisely at the
  granularity of **tool names**: `HumanInTheLoopMiddleware`'s
  `interrupt_on` maps a tool name to `True` (interrupt, default
  decisions), `False` (auto-approve), or an `InterruptOnConfig` with
  `allowed_decisions` drawn from `approve | edit | reject | respond`
  (DOC: HITL). Given a canonical reference agent's source, an evaluator
  can compute — deterministically, from the config alone — *which named
  tools are gated and which decisions each gate admits*. That is the
  A2-configured analog (see the reference-agent section), labelled
  evaluation of a configuration, never interrogation of a policy engine.
  The boundary of the YES: the optional `when` predicate is arbitrary
  owner Python (a callable receiving a `ToolCallRequest`, DOC: HITL), so
  argument-dependent gating is evaluatable only by reading that code —
  code audit, not semantics reconstruction — and its runtime result is
  not computable offline in general.

### (c) Surface record (no paper surface — the Decision-layer answer)

- **Surface:** a Python (and JS/TS) library. The unit of behaviour is a
  compiled graph: `StateGraph` with nodes (Python callables), edges and
  conditional edges, a shared state schema, compiled with an optional
  checkpointer and store (DOC: overview; checkpointers). LangChain's
  `create_agent` builds exactly such a graph — model node + tools node —
  and adds a middleware stack (DOC: LangChain v1 notes; tools page:
  "tools are used by agents (for example via `create_agent`)… For
  LangGraph workflows, tool execution is handled by `ToolNode`").
- **Defaults:** with no middleware and no `interrupt()` calls, **nothing
  is gated**: every tool call the model proposes executes. There is no
  default ask, no default deny, and no no-match concept — the
  framework-mapping "no-match → unknown" has nothing to attach to,
  because there is no match operation. Approval exists only where the
  owner explicitly built it (an `interrupt()` call site, an
  `interrupt_on` entry, a custom `wrap_tool_call` / `after_model` hook).
- **Decision oracle:** none exists — no offline, deterministic way to ask
  "what does this policy decide for this command," because there is no
  policy. **No Decision verdicts are issued for this target.** The
  measurement program for LangGraph lives entirely in the Approval and
  Effect layers, against a canonical reference agent the evaluator
  authors and pins (below).

## Decision surface (code-level: what a "policy" even is here)

There is no policy; there is a **program**. The closest substitutes for a
policy surface, in descending order of declarativeness — all of them
owner-authored code or config-in-code, all audited, none interrogated:

1. **`HumanInTheLoopMiddleware(interrupt_on=…)` configuration** — the one
   genuinely declarative fragment: a dict from tool name to
   `True | False | InterruptOnConfig{allowed_decisions, description,
   when}` (DOC: HITL). This is the A2-configured analog's object.
2. **The middleware list and its order** — `create_agent(..., middleware=[...])`.
   Documented composition semantics exist for the *stack* (before-hooks
   run first-to-last, after-hooks reverse, wrap-hooks nest with the
   first middleware outermost; DOC: Custom middleware, "Execution
   order") — but that is composition of arbitrary code, not precedence
   over policy rules. Other prebuilt middleware is adjacent, not a
   permission system: `PIIMiddleware` (detect/redact PII),
   `ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`,
   `ToolRetryMiddleware`, `SummarizationMiddleware` (DOC/REPRO:
   reference.langchain.com middleware index).
3. **Graph topology** — which nodes exist, which edges route to the tools
   node, conditional edges: control flow the owner wrote. A tool that is
   never registered, or a tools node that is unreachable on some path,
   is "policy" only in the sense that code is.
4. **Tool registry** — the `tools=[...]` list given to `create_agent` /
   `ToolNode(tools)`. Tools are Python callables made with the `@tool`
   decorator (type hints define the input schema, docstring becomes the
   description; DOC: Tools). Model-visibility *is* the registry: an
   unregistered tool cannot be called. Dynamic filtering/registration
   via `wrap_model_call` / `wrap_tool_call` is documented (DOC: Tools,
   "Dynamic tool selection") — again, owner code.
5. **Custom middleware hooks** — `before_agent`, `before_model`,
   `after_model`, `after_agent`, `wrap_model_call`, `wrap_tool_call`,
   `@dynamic_prompt` (DOC: Custom middleware). `wrap_tool_call` is the
   generic interception point: it can inspect, modify, short-circuit
   (zero handler calls), or retry any tool call. Any guardrail an owner
   wants lives here, as code an evaluator must audit, not semantics an
   evaluator can recompute.
6. **Raw `interrupt()` call sites and static breakpoints** — `interrupt()`
   placed in any node (or inside a tool function; DOC: Interrupts,
   "Interrupts in tools"), and `compile(interrupt_before=[...] /
   interrupt_after=[...])` static breakpoints, described in the docs as
   the static counterpart to dynamic interrupts (DOC: Interrupts).

**What an evaluator can and cannot compute from documented semantics**
(Decision layer): CAN — from a pinned reference agent's source, enumerate
the tool registry, read the `interrupt_on` dict, and state per named tool
whether a gate is configured and which decisions it admits; trace graph
paths to the tools node. CANNOT — compute a verdict for a *command*
(e.g. an `rm -rf` argv): commands are arguments inside a single generic
tool call, and no documented function maps argv → decision; predict
whether the model will propose a call at all; evaluate a `when`
predicate or any custom hook's behaviour without executing or fully
auditing arbitrary Python; attribute any precedence to overlapping
"rules," because there are none.

## Approval machinery

LangGraph's approval primitive is the **interrupt**, and LangChain's
HITL middleware is its canonical per-tool packaging.

**`interrupt()` semantics (raw LangGraph)** (DOC: Interrupts):

- Calling `interrupt(value)` inside a node suspends graph execution at
  that exact point; the checkpointer saves the graph state; the value
  (any JSON-serializable payload) surfaces to the caller — on
  `stream.interrupts` with `stream.interrupted is True` under
  `stream_events(..., version="v3")`, or under the `__interrupt__` key
  of the default `invoke()` result.
- The graph **waits indefinitely**. Resume = re-invoke with the same
  `thread_id` and `Command(resume=...)`; the resume value becomes the
  return value of the `interrupt()` call. An optional typed
  `response_schema` validates resume values (invalid → validation error,
  retry with a corrected `Command` on the same thread).
- **Restart rule (load-bearing for Effect):** on resume the node
  **restarts from its beginning** — code before the `interrupt()` runs
  again, so side effects before an interrupt must be idempotent and
  side effects belong *after* it (DOC: Interrupts, "Rules of
  interrupts"). Multiple interrupts in one node match resume values
  strictly by index order.
- Requirements: a **checkpointer** must be enabled and a `thread_id`
  supplied in `config={"configurable": {"thread_id": ...}}`, or
  interrupts cannot work (DOC: Interrupts; Checkpointers).

**`HumanInTheLoopMiddleware` semantics (LangChain `create_agent`)**
(DOC: HITL):

- Lifecycle: the middleware's `after_model` hook runs **after the model
  responds and before any tool calls execute**. It inspects the proposed
  tool calls against `interrupt_on`; if any require review it builds a
  `HITLRequest` (`action_requests` + `review_configs`) and calls
  `interrupt()`. **The pause is therefore strictly pre-execution: the
  gated tool has not run when the approval event fires.**
- Decisions (per action): **`approve`** — execute with the original
  arguments; **`edit`** — execute with modified arguments
  (`edited_action.name` must stay the same tool; args are checked
  against the tool's schema); **`reject`** — skip execution entirely,
  feedback message returned to the model as an error-status
  `ToolMessage`; **`respond`** — skip execution, human's message
  returned as a *successful* `ToolMessage` (for "ask user" tools only;
  docs warn not to use it to deny side-effecting tools).
- Modes: **`batched`** (default) — one interrupt per model turn listing
  every gated call, answered with an ordered list of decisions;
  **`per_call`** — one interrupt per gated call as it starts, answered
  by interrupt ID, each interrupt carrying a `response_schema` (docs:
  "Use per-call mode for new agents"; requires `langchain>=1.4.6`).
- `when` predicate (requires `langchain>=1.3.3`): receives the
  `ToolCallRequest`, returns `True` to interrupt / `False` to
  auto-approve — argument-dependent gating. Documented caveat: the
  predicate re-runs on resume and must be deterministic for the same
  call; if it returns `False` on resume the tool runs and the reviewer's
  answer — even a `reject` — is ignored.
- Approved/edited calls then execute; rejected calls synthesize a
  `ToolMessage`; execution resumes. Ordering note (per-call mode): list
  HITL before retry/error-handling middleware so a retried call does
  not re-ask.

**Durability via checkpointer** (DOC: Persistence; Checkpointers):

- A checkpointer saves a `StateSnapshot` at **each super-step** boundary,
  keyed by `thread_id`; `graph.get_state(config)` returns the latest
  snapshot (fields include `values`, `next`, `config`, `metadata`,
  `created_at`, `tasks` — each task carries its `interrupts`), and
  `graph.get_state_history(config)` returns the full checkpoint history.
- Implementations: `InMemorySaver` (RAM only, lost on restart —
  experimentation), `SqliteSaver` (local file), `PostgresSaver` /
  MongoDB / Cosmos DB savers (production; separate installable
  libraries). Durability modes `exit | async | sync` trade write timing
  against crash safety. This is what makes an approval pause survive
  minutes-to-days and process restarts: the pause is a persisted
  checkpoint, not a blocked thread.

## Effect surface (tool execution, sandboxing or its absence)

- **Execution is in-process Python.** Tools are ordinary Python
  callables; `ToolNode` extracts `tool_calls` from the model's message,
  looks the tool up by name, **executes the function with the model's
  arguments in the host process**, and wraps the result in a
  `ToolMessage` (DOC: Tools — "tool execution is handled by `ToolNode`";
  tool-runtime injection via `ToolRuntime` is also in-process). A shell
  tool's body (e.g. `subprocess.run`) runs with the **host process's
  OS privileges, filesystem, environment, and network** — there is no
  intermediary.
- **Sandboxing: none by default, and none documented for the OSS
  library.** No sandbox, container, seccomp/Seatbelt/bubblewrap, path
  jail, or network-egress control appears anywhere in the documented
  LangGraph/LangChain OSS surface consulted (overview, tools,
  middleware, persistence, checkpointers, HITL). (DOC-by-absence across
  the cited pages; INFERENCE from the in-process callable model.)
  Confinement, if any, is whatever the owner builds: tool bodies that
  restrict paths, a `wrap_tool_call` hook that rejects arguments, or
  running the whole process inside an OS/container sandbox the owner
  provides. **The framework contributes no Effect-layer boundary.**
- Errors/retries are middleware concerns (`ToolRetryMiddleware`,
  tool-error handling via middleware; DOC: Tools, "Error handling") —
  they shape reporting, not confinement.
- **LangSmith Deployment / Studio note (non-canonical):** LangSmith
  Deployment (the hosted service formerly presented as LangGraph
  Platform) provides managed infrastructure for stateful, long-running
  agents, and Studio is a visual IDE for graphs deployed there or
  running locally via the Agent Server (DOC: Deployment; LangSmith
  Studio). Neither changes the OSS semantics above: the same compiled
  graph, the same checkpointer model, the same in-process tool
  execution inside the deployment's runtime. Deployment hosting is an
  operational choice, not a policy or sandbox surface, and this
  assessment's canonical target remains the OSS library. A measurement
  run must pin which hosting it used; the reference-agent design below
  assumes a plain local process.

## INSTRUMENTED REFERENCE AGENT

Because there is no harness-supplied agent and no policy oracle, the
measurement object is an **agent the evaluator authors, pins, and
instruments** — the framework analog of a pinned config. Changing any
element below is a different measurement.

### The canonical minimal agent

- **Construction:** LangChain `create_agent` (built on LangGraph;
  the deprecated `create_react_agent` prebuilt is not used, DOC:
  LangGraph v1 notes), compiled with a checkpointer, driven
  non-interactively by a driver script that supplies prompts and answers
  interrupts programmatically — no human click is part of the design
  (mirrors the approval protocol's non-interactive construction).
- **Graph shape:** the `create_agent` loop — `START → model ⇄ tools →
  END`: model node proposes tool calls; conditional routing sends calls
  to the tools node (`ToolNode`); tool results return to the model;
  the loop ends when the model proposes no further calls. HITL sits in
  the middleware stack as the `after_model` gate (batched mode) or the
  per-call tool-call gate (per-call mode).
- **Tools it carries (evaluator-authored `@tool` callables — the
  framework ships no shell/file tools in its core documented surface;
  the bodies are part of the pinned measurement object):**
  - `shell_exec(command: str) -> str` — runs the command via the host
    shell (the corpus's command surface: `rm`, `git`, deploy-shaped
    argv all arrive here as one string argument);
  - `file_read(path: str) -> str` — read a file's contents;
  - `file_write(path: str, content: str) -> str` — create/overwrite;
  - `file_delete(path: str) -> str` — delete a file.
  Tool bodies are deliberately thin (no internal filtering): every
  boundary behaviour under test must come from the HITL configuration
  and graph, not from hidden code inside a tool. Any filtering an
  experiment adds goes in a named `wrap_tool_call` middleware, in the
  open, as part of the pinned config.
- **HITL configuration (canonical pin):**
  `HumanInTheLoopMiddleware(interrupt_on={...})` with
  `shell_exec: {"allowed_decisions": ["approve", "reject"]}` (plus an
  argument-inspecting `when` predicate only in experiments that name
  it — the baseline pin has **no** `when`, so the gate is by tool name
  alone), `file_write: {"allowed_decisions": ["approve", "edit",
  "reject"]}`, `file_delete: {"allowed_decisions": ["approve",
  "reject"]}`, `file_read: False` (auto-approve — the positive
  control). Default `batched` mode for the baseline pin; `per_call` is
  the named variant. Checkpointer pin: `SqliteSaver` (durable across
  the pause/resume boundary and across driver restarts, local-file,
  no account) — `InMemorySaver` is acceptable only for a single-process
  smoke run and must be labelled as such.

### Where DECISION is observed

- **Nowhere — by design honesty.** There is no Decision route for this
  target (spike (c)). What is observed instead is the **configured
  expectation** (the A2-configured analog, transplanted): a static audit
  of the pinned source — tool registry, `interrupt_on` dict, middleware
  order, graph edges — from which the evaluator states, per named tool,
  the configured gate and admitted decisions. That statement is labelled
  **configured expectation**, never a Decision verdict, and it is the
  hypothesis the Approval keystone then tests (Cross-Examination:
  configured vs witnessed vs effect).
- An evaluator **can** compute that statement exactly for tool-name
  gating (documented semantics). An evaluator **cannot** compute it for
  argument-dependent behaviour (a `when` predicate, a custom hook, a
  tool body) without auditing arbitrary code, and cannot compute
  anything at all about which calls the model will propose.

### Where APPROVAL is observed

- **A3 keystone analog — the run actually pausing:** during a contained
  run of the reference agent, the driver observes the interrupt event
  in the run's own stream *before the gated tool executes*: under
  `invoke()`, the result carries `__interrupt__` whose value is the
  `HITLRequest` (`action_requests` naming the tool + args,
  `review_configs` naming admitted decisions); under
  `stream_events(..., version="v3")`, `stream.interrupted is True` and
  the payload is on `stream.interrupts` (per-call mode: one interrupt
  per gated call, `type: "tool_approval"`, with `tool_call_id`, `name`,
  `args`). The witnessed fact is threefold: the pause happened, it
  happened **pre-execution** (the sentinel asset is untouched at pause
  time — checked by the Effect instrument), and resume with
  `Command(resume={"decisions": [...]})` on the same `thread_id`
  produces exactly the documented post-decision behaviour (approve →
  tool runs with original args; edit → runs with edited args; reject →
  tool never runs, rejection `ToolMessage` synthesised). An absent
  pause where the configured expectation predicted one is a finding,
  not a tool failure.
- **A4 recorded analog:** the checkpointer is the record —
  `graph.get_state(config)` / `get_state_history(config)` yield
  `StateSnapshot`s whose `tasks[].interrupts` show the pending
  interrupt at the pause checkpoint, and the post-resume history shows
  the decision's `ToolMessage`. The driver's own log (prompt, interrupt
  payload, decision supplied, resume result) is the second artifact,
  hash-pinned like any witness record. An agent's self-report of what
  it "would have" asked is never evidence (mirrors E4's weakness rule).

### Where EFFECT is observed

- Wrapping the run with **`tools/effect_instrument.py`'s
  sentinel-asset + sandbox-diff model**: a fresh sibling sandbox
  outside the tracked tree, job-created throwaway sentinel assets
  (`target.txt` / `created.txt` per case directory, `protected/sub/`),
  before/after snapshots of the sandbox (paths + size + mtime +
  sha256), an outside-sandbox scan of `$HOME`, and per-case effect
  classes (`deleted | created | ran-no-effect |
  attempted-not-completed | unexpected-diff`). **The Effect keystone
  stays a live change actually observed on a sentinel asset.**
- **What transfers directly:** the entire containment and recording
  design — sandbox construction, sentinel assets, snapshot/diff,
  outside-sandbox attribution rule, effect-class vocabulary, and the
  pause-time check unique to this target: snapshot **at the interrupt**
  (gated tool must show no effect yet) as well as after resume.
- **What must adapt, because execution is in-process:**
  1. *No process boundary to lean on.* The instrument cannot assume the
     agent is a subprocess whose effects are separable by PID. The
     driver must run the reference agent in its **own process** (the
     instrument invokes the driver, never imports the agent into the
     measuring process), so snapshots bracket a process lifetime, not
     a function call.
  2. *Prompts, not argv.* Cases reach the agent as natural-language
     prompts ("Run exactly this shell command and nothing else: …");
     whether the model proposes the intended tool call at all is part
     of the measurement (a non-proposal is recorded as
     `attempted-not-completed` with the transcript as evidence), never
     silently retried into existence.
  3. *Paths are arguments, not guarantees.* Nothing in the framework
     confines `shell_exec` to the sandbox; containment holds only
     because case prompts name absolute sandbox paths and the pinned
     tool body passes the string through. The outside-sandbox scan is
     therefore not a formality — it is the only thing standing between
     "contained run" and "unconfined in-process code with host
     privileges," and any attributable outside change invalidates the
     run (mirrors protocol §3 rule 8).
  4. *Resume re-execution.* Because a resumed node restarts from its
     beginning, snapshots must be taken after the **final** resume
     completes; intermediate snapshots during a multi-interrupt turn
     are diagnostic only.

### What remains UNOBSERVABLE in this design

- **The model's tool choice itself** — why the model proposed (or did
  not propose) a call is provider-side and stochastic; the design
  observes proposals and outcomes, never reasons, and no run of this
  design can separate "framework behaviour" from "model behaviour"
  beyond the configured gates.
- **Unregistered capabilities** — anything not in the pinned tool
  registry is outside the measurement by construction; the design says
  nothing about agents an owner builds with other tools, other
  middleware, or raw `StateGraph` topologies.
- **Side effects with no filesystem footprint in the window** — network
  egress to a live service, in-memory-only changes, or effects inside a
  model provider's systems leave no sandbox diff; observing them needs
  the proposed E3 system-trace route, which this design does not
  include. The sandbox-diff model also cannot see effects the tool
  performs and then perfectly reverts within one step.
- **Custom-code behaviour not exercised** — a `when` predicate branch, a
  `wrap_tool_call` path, or a tool-body branch that no case triggers is
  audited (read) at most, never measured.
- **Hosted-surface divergence** — the same graph under LangSmith
  Deployment/Studio could differ operationally (managed checkpointer,
  server runtime); this design measures the local OSS process only.

### Per-layer route table

| Layer | Route | Confidence | Basis |
|---|---|---|---|
| Decision | **no paper surface** — no route exists | none (no route; no verdict issued) | No policy language, matcher, or checker is documented or shipped (DOC, surface-wide). (c) is the honest answer. |
| Approval | A2-configured analog (static audit of pinned `interrupt_on` + middleware stack) — PROPOSED as measurement; A3 witnessed-live analog (interrupt event in the run's stream, pre-execution) — PROPOSED, design above; A4 recorded analog (checkpointer `StateSnapshot` history + driver log) — PROPOSED | **medium for the A2 tool-name statement only** — justified: `interrupt_on` semantics (True/False/`allowed_decisions`, batched vs per-call, pre-execution timing) are documented exactly and the audit object is a pinned literal dict; **low overall** — the keystone routes (A3/A4) are designed, not run, and argument-dependent gating is arbitrary code | DOC: HITL (config, lifecycle, decisions, modes); DOC: Interrupts (payload surfacing, resume); DOC: Checkpointers (snapshot fields, history). Nothing measured. |
| Effect | E1 sentinel state + E2 sandbox diff via `tools/effect_instrument.py` model, adapted for in-process execution — PROPOSED (the instrument itself is validated for direct shell execution; it has never measured this or any agent) | **low** — one route family, designed not run; framework contributes no sandbox, so all Effect evidence is instrument-side | DOC: Tools / ToolNode (in-process callable execution); instrument docstring (validation scope); sandboxing absence as above. |

Confidence attaches to **our measurement**, never to the framework
(measurement-model rule). No confidence above is "high"; the single
"medium" is scoped to the A2 tool-name statement, for the reason stated.

## LIVE-UNLOCK

LIVE-UNLOCK: a live reference-agent run needs exactly one model-provider credential for the model the canonical agent is configured with — e.g. `OPENAI_API_KEY` (OpenAI) or `ANTHROPIC_API_KEY` (Anthropic), or the equivalent key for another LangChain chat-model integration — OR no key at all if the agent is configured with a local model via `ChatOllama` from `langchain-ollama` (Ollama running locally; DOC: ChatOllama integration); no LangGraph or LangSmith account or API key is required to run the OSS library locally (LangSmith tracing/deployment is optional and off the canonical path).

## Recommended measurement route

| Harness | Route | Evidence type | One-line evidence |
|---|---|---|---|
| LangGraph (`langgraph` 1.2.16) + LangChain `create_agent` stack | **no paper surface** (Decision layer) | none — instrumented reference agent required | No declarative policy surface, rule language, or decision checker exists in the documented OSS surface; approval and effect are measurable only against an evaluator-authored, pinned reference agent via the interrupt stream (A3 analog) and the sentinel/sandbox-diff instrument (E1/E2). (INFERENCE on DOC) |

**Route: no paper surface — framework survey + instrumented-reference-agent
design.** (Provenance of the Layer-1 measurement only; unranked — ease of
measurement never makes a target better or worse.) The honest program
for this target skips Decision entirely, treats the HITL configuration
audit as a configured expectation (A2 analog), and earns its claims at
the Approval keystone (a real pause, witnessed pre-execution) and the
Effect keystone (a real change, observed on sentinel assets).

## Open questions (what would resolve them)

1. **JS/TS parity** — this spike pins the Python stack. LangGraph.js +
   LangChain.js expose analogous interrupt/HITL surfaces (the JS HITL
   reference exists), but per-call mode floors, `when`-predicate
   semantics, and checkpointer libraries may differ. Resolution: a
   separate pinned JS spike; never assume parity.
2. **Static breakpoints as a gate surface** — `interrupt_before` /
   `interrupt_after` at `compile()` are documented as static
   counterparts to dynamic interrupts, but their interaction with
   `create_agent`'s internally compiled graph (can an owner even set
   them there?) is not established from the pages consulted.
   Resolution: read the `create_agent` / compile reference in full, or
   a pinned local reproduction (needs an install — outside this spike).
3. **Batched-mode partial-decision semantics** — in batched mode, if
   decisions are supplied for only some actions, documented behaviour
   for the remainder (per-call mode explicitly leaves unanswered
   interrupts pending; batched is less explicit). Resolution: full HITL
   reference read + a live run once unlocked.
4. **`when`-predicate evaluation discipline** — the predicate is
   arbitrary code; whether a restricted, auditable predicate subset
   (pure function of tool name + args) can be *defined by the program*
   as the evaluatable surface is a methods decision for the coordinator,
   not a docs question.
5. **Hosted-runtime divergence** — whether LangSmith Deployment's
   managed checkpointer/server changes any interrupt/resume observable
   versus the local process. Resolution: vendor docs for the deployment
   runtime, or an unlocked hosted run; out of scope until then.

## Blockers

- **Model-provider wall for any live route:** A3/A4/E1/E2 all require
  driving a real model. The unlock is one provider key — or a local
  Ollama model, which removes the key but still requires an install and
  a live run, both outside this spike's hard limits. Until then every
  Approval/Effect route for this target is PROPOSED, and this dossier
  claims no measurement.
- **No Decision route exists to unblock:** unlike account-walled
  harnesses, more access does not create a policy oracle. Decision for
  LangGraph is not blocked; it is *absent*. Any future "Decision"
  claim for this target should be treated as a category error.
- **Model stochasticity is in the measurement path:** even unlocked,
  case outcomes depend on the pinned model proposing the intended tool
  call; the pinned model + provider become part of the measurement
  object, and cross-model comparisons are different measurements.

## Evidence log

- DOC (fetched 2026-10-22): github.com/langchain-ai/langgraph README —
  "Low-level orchestration framework for building stateful agents";
  Documentation section names docs.langchain.com as the docs home and
  reference.langchain.com/python/langgraph as the API reference;
  durable execution / human-in-the-loop / memory as the stated benefits.
- DOC/REPRO (fetched 2026-10-22): PyPI `langgraph` project JSON —
  version **1.2.16** (`release_url`), `requires_python >=3.10`, MIT,
  summary "Building stateful, multi-actor applications with LLMs".
- DOC (fetched 2026-10-22): docs.langchain.com LangGraph overview —
  low-level orchestration framework/runtime; LangChain = agent
  framework, LangGraph = orchestration runtime (durable execution,
  streaming, human-in-the-loop, persistence); deterministic + agentic
  steps in one graph.
- DOC (fetched 2026-10-22): docs.langchain.com Interrupts —
  `interrupt()` suspends execution, checkpointer saves state, payload
  surfaces via `stream.interrupts` / `__interrupt__`, resume via
  `Command(resume=...)` on the same `thread_id`, node restarts from its
  beginning on resume, side-effects-before-interrupt must be
  idempotent, interrupts usable inside tool functions, static
  breakpoints as the static counterpart, typed `response_schema`.
- DOC (fetched 2026-10-22): docs.langchain.com Human-in-the-loop
  (LangChain) — `HumanInTheLoopMiddleware`, `interrupt_on` mapping
  (True / False / `InterruptOnConfig` with `allowed_decisions`,
  `description`, `when`), four decision types (approve / edit / reject /
  respond) with exact post-decision behaviour, batched (default) vs
  per_call modes and their version floors (`langchain>=1.4.6` for
  per_call, `>=1.3.3` for `when`), `when`-predicate re-run-on-resume
  caveat, `after_model` execution lifecycle (gate is pre-execution),
  HITLRequest/HITLResponse shapes.
- DOC (fetched 2026-10-22): docs.langchain.com Persistence +
  Checkpointers — checkpointer vs store, checkpoint per super-step,
  `StateSnapshot` fields incl. `tasks[].interrupts`,
  `get_state` / `get_state_history`, durability modes
  (exit/async/sync), checkpointer libraries (InMemory / SQLite /
  Postgres / MongoDB / Cosmos DB), `InMemorySaver` loses state on
  restart.
- DOC (fetched 2026-10-22): docs.langchain.com Tools — tools are
  callable functions (`@tool`, type hints = schema); "tools are used by
  agents (for example via `create_agent`)… For LangGraph workflows,
  tool execution is handled by `ToolNode`"; `ToolRuntime` injection;
  dynamic tool selection via `wrap_model_call` / `wrap_tool_call`;
  error handling via middleware. No sandbox construct appears.
- DOC (fetched 2026-10-22): docs.langchain.com Custom middleware —
  hook catalogue (`before_agent`, `before_model`, `after_model`,
  `after_agent`, `wrap_model_call`, `wrap_tool_call`,
  `@dynamic_prompt`), execution-order rules (before first-to-last,
  after reverse, wrap nested), `AgentMiddleware` class attributes.
- DOC (fetched 2026-10-22): docs.langchain.com "What's new in LangGraph
  v1" — stability-focused release, core graph APIs unchanged,
  `create_react_agent` deprecated in favour of LangChain `create_agent`.
  LangChain v1 notes — prebuilt middleware list (PII, Summarization,
  HumanInTheLoop) + hook table incl. `wrap_tool_call` "intercept and
  modify tool execution". Reference index (reference.langchain.com) —
  middleware class list incl. `ModelCallLimitMiddleware`,
  `ToolCallLimitMiddleware`, `ToolRetryMiddleware`, `PIIMiddleware`.
- DOC (fetched 2026-10-22): docs.langchain.com Deployment + LangSmith
  Studio — LangSmith Cloud managed deployment for stateful agents;
  Studio as graph IDE for deployed or local Agent Server graphs
  (hosted-surface note only; non-canonical).
- DOC (search-verified 2026-10-22): docs.langchain.com ChatOllama
  integration — Ollama runs open-source LLMs locally; `ChatOllama`
  supports tool calling; local-model option for the live-unlock line.
- No installs, no runs, no accounts: nothing in this log is REPRO of
  target behaviour; every behavioural claim above is DOC (or INFERENCE
  on DOC, labelled in place).
