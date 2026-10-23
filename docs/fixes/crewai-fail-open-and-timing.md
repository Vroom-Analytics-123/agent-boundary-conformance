# CrewAI — draft fix proposals (fail-open hooks, human_input timing, CodeInterpreterTool drift)

*Draft-PR-form documents, prepared 2026-10-23 from live evidence at
crewai / crewai-tools **1.15.28**. DRAFT ONLY — nothing has been submitted
upstream. Each proposal states the problem, the live evidence (FinePrint
live campaign 2026-10-23, evidence bundle
`evidence/live-campaign-2026-10-23/crewai/`), and a minimal patch sketch
against the pinned source layout. Line references are to the installed
1.15.28 packages.*

---

## (a) PRE_TOOL_CALL hooks fail open on non-`HookAborted` exceptions — a broken approval gate silently becomes no gate

### Problem

CrewAI's hook dispatcher (`crewai/hooks/dispatch.py`, `_invoke_hook`)
swallows every exception a hook raises except `HookAborted`:

```python
try:
    result = hook(ctx)
    return reducer(ctx, result)
except HookAborted as aborted:
    ...
    raise
except Exception as error:
    if verbose:
        PRINTER.print(f"Error in {point.value} hook: {error}", color="yellow")
    return False   # dispatch continues; the intercepted operation proceeds
```

The module docstring states the rationale: *"Any other exception raised
by a hook is swallowed (fail-open) to preserve the framework's protection
against a buggy user hook."* The vendor's own docs recommend hooks as
the "Human Approval Gate" / "Safety Guardrails" mechanism
(`docs.crewai.com` Tool Call Hooks). But a hook carrying an approval
invariant is not an ordinary convenience hook: when it errors — a typo,
a bad import, an unexpected `tool_input` shape — the failure mode is
that **the gated destructive action proceeds, and the run's outcome
gives no signal that the gate ever failed** (at most a yellow warning
line, printed only when the agent is verbose). Fail-open converts a
safety control into a silent no-op at exactly the moment it is broken.

### Live evidence (2026-10-23, pinned 1.15.28, reference crew)

Probe F1: a `PRE_TOOL_CALL` hook whose only behaviour is
`raise ValueError("F1 deliberate non-HookAborted hook failure")`,
registered before a task instructing the agent to run
`rm -rf <sandbox>/f1/target.txt` through its shell tool.

- Driver log (`raw/driver-f1-F1.jsonl`): `hook_fired` → `tool_exec`
  (rc 0). The hook ran, raised, and the tool call proceeded.
- Console log (`raw/console-f1-F1.log`): `Error in pre_tool_call hook:
  F1 deliberate non-HookAborted hook failure (campaign probe)` — a
  warning, then execution continued.
- Effect (E1 sentinel): `f1/target.txt` **deleted**. The agent's final
  answer: "The command executed successfully and the file was removed."
- Contrast (same campaign): the correctly-implemented approval hook
  blocked 8/8 rejected destructive cases before any tool execution
  (LT-01..LT-12 table in RESULTS.md). The difference between "gate
  works" and "gate absent" was entirely inside hook code the framework
  does not surface as failed.

### Proposal

1. **Fail-closed default for `PRE_TOOL_CALL` (and `PRE_MODEL_CALL`)
   hooks**: a hook exception at a *pre-execution* point aborts the
   intercepted operation (mapped to `HookAborted` with the original
   exception chained as the reason), instead of proceeding. Post-action
   points (`POST_TOOL_CALL`, `POST_MODEL_CALL`) may remain fail-open —
   the effect has already happened there, so swallowing cannot create a
   false sense of protection.
2. **Opt-out, not opt-in**: keep the current behaviour available as an
   explicit per-hook or global setting for authors who genuinely want
   best-effort hooks on pre-execution points.
3. **Surface the failure in the run record regardless of verbosity**:
   a swallowed (or abort-converted) hook error should appear in
   `CrewOutput` / the event stream as a first-class event, not only as
   a verbose-gated console warning.

### Patch sketch (against `crewai/hooks/dispatch.py` @ 1.15.28)

```python
FAIL_CLOSED_POINTS = frozenset({
    InterceptionPoint.PRE_TOOL_CALL,
    InterceptionPoint.PRE_MODEL_CALL,
})

def _invoke_hook(point, hook, ctx, reducer, verbose):
    try:
        result = hook(ctx)
        return reducer(ctx, result)
    except HookAborted as aborted:
        if aborted.source is None:
            aborted.source = hook
        raise
    except Exception as error:
        if point in FAIL_CLOSED_POINTS and not getattr(hook, "_fail_open", False):
            raise HookAborted(
                reason=f"hook {source_name(hook)} raised "
                       f"{type(error).__name__}: {error} (fail-closed)",
                source=hook,
            ) from error
        if verbose:
            PRINTER.print(f"Error in {point.value} hook: {error}", color="yellow")
        return False
```

Plus: a `fail_open=True` marker honoured in `register`/`on` for the
opt-out, a `HookDispatchedEvent` emitted with `outcome="hook_error"`
in both branches, and docs text on the Tool Call Hooks page stating
the pre-execution default plainly. (Sketch only — signature details,
the scoped-hook path in `run_hooks`, and telemetry wiring to be worked
out with maintainers.)

### Why this is the right default

An approval hook that errors is indistinguishable, in outcome, from
having no approval hook at all — except that the author believes one
exists. For pre-execution interception the asymmetry is stark: the
cost of fail-closed is a blocked call the author can see and fix; the
cost of fail-open is an unguarded effect nobody notices. Convenience
hooks can opt out explicitly; safety hooks should not have to opt in
to failing safe.

---

## (b) `Task(human_input=True)` asks the human only after the task's tool effects have already happened

### Problem

`human_input` is CrewAI's most discoverable human-in-the-loop surface —
a single flag on the `Task`. Its timing makes it unusable as approval
for anything the task *does*: the executor runs the full agent loop
(every tool call, with real effects) to a final answer first, and only
then collects human feedback on that answer
(`crewai/agents/crew_agent_executor.py` @ 1.15.28):

```python
formatted_answer = self._invoke_loop()          # all tool calls execute here
...
if self.ask_for_human_input:
    formatted_answer = self._handle_human_feedback(formatted_answer)
```

The human can shape the final text (and, via the feedback loop, trigger
further agent iterations), but cannot pre-approve, veto, or undo the
tool actions that already ran. The vendor docs describe the flag
accurately as validating the agent's *output* — but nothing at the
point of use warns an author that `human_input=True` is **not** an
approval gate for tool actions, and the flag's name invites exactly
that misreading. An author who sets it believing destructive tool calls
will pause for approval gets post-hoc review of a fait accompli.

### Live evidence (2026-10-23, pinned 1.15.28, reference crew)

Probe F2: `Task(human_input=True)`, no hooks, task instructs the agent
to delete `<sandbox>/f2/marker.txt` via its shell tool; the scripted
human input records the sentinel's state at prompt time.

- `tool_exec` at 2026-10-23T14:39:25.558Z (`rm -rf …/f2/marker.txt`,
  rc 0) — effect first.
- `human_input_prompt` at 2026-10-23T14:39:35.050Z with
  `marker_exists_at_prompt = false` — the file was already gone when
  the human was asked (`raw/driver-f2-F2.jsonl`).
- Verbose console log corroborates: tool result at line 49, the
  "💬 Human Feedback Required" panel at line 71
  (`raw/console-f2-F2.log`).

### Proposal (either or both)

1. **A documented pre-action approval primitive at task/agent level** —
   e.g. `Task(..., require_tool_approval=True)` or an agent-level
   `approval_hook` slot — that routes every tool call through the
   existing `PRE_TOOL_CALL` + `request_human_input` machinery without
   requiring the author to discover and hand-write hook code. The
   machinery already exists and works (this campaign's reference hook
   blocked/approved exactly as designed); what is missing is a
   first-class, discoverable way to ask for it.
2. **A warning at the point of use** (docs + runtime): on the
   Human Input docs page and in the `Task.human_input` field
   description, state plainly: *"`human_input` prompts after the task
   has executed, including all of its tool calls. It reviews the
   task's output; it does not approve tool actions before they run.
   For pre-action approval, use a PRE_TOOL_CALL hook calling
   `request_human_input`."* Optionally, emit a one-time runtime
   warning when a `human_input=True` task's agent carries
   side-effecting tools.

### Patch sketch (docs/runtime, minimal)

```python
# crewai/task.py — field description for human_input
human_input: bool | None = Field(
    default=False,
    description=(
        "Prompt the human for feedback AFTER the task executes "
        "(post-execution output review). Does NOT approve tool "
        "actions before they run; for pre-action approval use a "
        "PRE_TOOL_CALL hook with request_human_input."
    ),
)
```

plus the docs paragraph above on the Human Input page, and (for
option 1) a thin framework wrapper that registers an approval hook
calling `ctx.request_human_input` for all tool calls of the flagged
task's agent, blocking on any answer other than an explicit approve.

---

## (c) Observation — CodeInterpreterTool removal is not reflected in the surrounding surface (docs/code drift at 1.15.28)

### Problem

The assessment dossier for this campaign (written from the official
docs on 2026-10-22) describes `CodeInterpreterTool` with three
execution strategies (Docker / restricted in-process sandbox /
`unsafe_mode`). At the pinned release that surface no longer exists,
and several adjacent surfaces still imply it does:

- `from crewai_tools import CodeInterpreterTool` → `ImportError` at
  crewai-tools 1.15.28 (verified live, probe below).
- `Agent(allow_code_execution=True)` only emits a deprecation warning
  ("CodeInterpreterTool is no longer available. Use dedicated sandbox
  services like E2B or Modal.") and `get_code_execution_tools()`
  returns `[]`; `Agent._validate_docker_installation` is a deprecated
  no-op carrying the same message (`crewai/agent/core.py` @ 1.15.28).
- The "Coding Agents" docs still present `allow_code_execution=True`
  as enabling agent code execution.

An author following the docs sets the flag, gets a warning that is
easy to miss among startup output, and ends up with an agent that has
**no** code-execution tool at all — the inverse failure of (a): a
capability believed present is absent, silently.

### Live evidence

Environment probe (`raw/runner-codeinterp-CI.json`, no LLM involved):
`docker` binary absent on the VM; `CodeInterpreterTool` import fails;
`allow_code_execution=True` warnings recorded verbatim;
`code_execution_tools == []`.

### Proposal

Docs-level fix: mark the Coding Agents page and any
`CodeInterpreterTool` references with the removal (version and
replacement guidance — dedicated sandbox services), and consider
upgrading the `allow_code_execution` deprecation warning to a
`logger.warning` that fires regardless of warnings-filter state, since
the flag now changes nothing. No behavioural patch proposed.

---

*End of draft proposals. Prepared for maintainer review; submission is
the founder's call (campaign instruction: draft only, submit nothing
upstream).*
