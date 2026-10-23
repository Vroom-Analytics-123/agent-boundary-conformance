# FIX DRAFT — Strands Agents: guardrail scope + a canonical tool-action gate

**Status: DRAFT — not sent, not filed, no upstream claim made.**
**Target:** Strands Agents SDK (`strands-agents` 1.62.0; docs at strandsagents.com).
**Source findings:** `adapters/strands-assessment.md` (2026-10-22 dossier) and the
Stage 1c live campaign, 2026-10-23 (`evidence/live-campaign-2026-10-23/strands/`).

---

## Finding 1 — "Guardrails" in Strands screen model text, never tool actions

A reader of the Strands documentation can reasonably come away believing that
attaching a guardrail protects what an agent *does*. It does not:

- Guardrails attach to the **model** — `BedrockModel(guardrail_id=...,
  guardrail_version=...)` — and evaluate **model input and model output
  content** against content/topic/word/PII policies, redacting on intervention.
- They exist only on the Bedrock provider path. Other providers (e.g.
  `OpenAIModel`) have no guardrail configuration at all.
- No guardrail ever sees a tool call as an action to permit or deny. A
  guardrail can redact a prompt that *mentions* `rm -rf`; it cannot stop the
  `shell` tool from running it, gate a deploy, or express any per-command
  policy.

**Proposed documentation fix:** in the model-provider / guardrails
documentation, add a scope note in these terms:

> Guardrails screen the conversation (model inputs and outputs). They do not
> inspect, approve, or block tool calls. To gate tool execution — destructive
> shell commands, deploys, writes to protected paths — register a
> `BeforeToolCallEvent` hook or an intervention handler; see the canonical
> pattern below.

## Finding 2 — No canonical single-gate pattern is documented

Strands' tool-action gate is owner Python code (a `BeforeToolCallEvent` hook
setting `event.cancel_tool`, or `event.interrupt(...)` for an approval pause;
or an intervention handler returning `Deny`/`Confirm`). The mechanisms are
documented individually, but no canonical, minimal, auditable pattern is
published — so every team invents its own, and multi-hook setups inherit
last-write-wins semantics with no stated precedence.

**Proposed documentation/patch:** publish the single-hook canonical form as
the reference pattern for tool-action policy:

```python
from strands import Agent
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

class PolicyHook(HookProvider):
    """The policy. One hook, three outcomes, nothing else decides."""
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self.decide)

    def decide(self, event: BeforeToolCallEvent) -> None:
        # Inspect event.tool_use["name"] and event.tool_use["input"].
        # DENY (hard veto, no ask):
        #     event.cancel_tool = "<reason>"
        # ASK (pause before execution; tool runs only on approval):
        #     approval = event.interrupt("<name>", reason={...})
        #     if str(approval).strip().lower() not in ("y", "yes"):
        #         event.cancel_tool = "User denied"
        # ALLOW: return without touching the event.
        ...

agent = Agent(tools=[...], hooks=[PolicyHook()], model=...)
```

Design rules that make this form auditable (proposed for the docs):

1. **Exactly one policy hook** in the measured/intended configuration — no
   second hook, no intervention, and no tool-internal consent prompt active
   at the same time (legacy tools' consent prompts are controlled by
   `BYPASS_TOOL_CONSENT` / `STRANDS_NON_INTERACTIVE`; pin them OFF or the
   system has two approval authors).
2. The hook is **pure and total** over `(tool_name, tool_input)` — no I/O,
   no randomness, no clock — so its decisions can be read off the source.
3. State the precedence explicitly: hard vetoes (protected paths) are checked
   before approval interrupts; approval interrupts before fall-through.

**Live evidence this pattern works as documented** (Stage 1c, 2026-10-23,
`gpt-4o-mini` via an OpenAI-compatible route, `strands-agents` 1.62.0): the
reference agent above held every destructive case at a witnessed
pre-execution interrupt (sentinel intact at the pause), vetoed the
protected-path case with no interrupt, let benign controls run unimpeded,
and — with the driver approving one designated case — executed the deletion,
showing the hook is the only barrier. Full records:
`evidence/live-campaign-2026-10-23/strands/RESULTS.md`.

## Open question — Cedar Authorization as an offline-checkable surface

The vended `CedarAuthorization` intervention evaluates real Cedar policies
(default-deny; Action = tool name; `context.input` = tool arguments) before
each tool call. That is the closest Strands comes to a declarative policy
surface — but the evaluated decision composes the Cedar policy with Python
`principal_resolver` / `context_enricher` lambdas and handler ordering, and
no offline "what does this agent decide for this call" checker is shipped
for the composition.

**Open question for the maintainers (not a claim):** would a Cedar-only
configuration (no custom resolvers/enrichers) be a supported, documented
subset whose decisions can be checked offline with Cedar's own engine? If
so, documenting that subset would give Strands agents a verifiable policy
surface without changing the SDK's code-level gate design. Until answered,
this is recorded as an open question — no Cedar route was built or measured
in the Stage 1c campaign.

---

*Draft prepared by the FinePrint campaign, 2026-10-23. Draft only: no
filing, submission, or outreach has been made with this document.*
