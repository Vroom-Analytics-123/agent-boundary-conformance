# FinePrint skill — measure an agent's boundaries before you trust them

Use the FinePrint MCP tools when a task touches an agent's enforced limits:
before running a destructive or privileged command, when asked whether an
agent's rules actually cover an operation, or when writing or changing a
policy. The tools measure; they never execute, never certify, and never
declare anything "secure."

## Tools

- `check_command` — Decision-layer verdict for one command against a policy.
  Give it the exact command. It evaluates the head segment of compounds and
  returns `forbidden`, `prompt`, `allow`, or `unknown`, with the matched rule.
- `list_invariants` — the 16 catalogue invariants (FP-001…FP-016): the
  protection statements a policy is measured against.
- `measurement_routes` — per-harness measurement route and provenance.
  Routes are unranked: vendor-confirmed, reconstructed, no paper surface.
  Ease of measurement never makes a harness better or worse.
- `run_check` — a full sealed conformance check. Returns the scorecard and
  the sealed bundle path. Slow (a full corpus run); pass `only` with
  comma-separated invariant ids to scope it.

## Rules you must not break

1. **Unknown is never allow.** A no-match means the Decision layer gives no
   decision; approval prompts and the sandbox still govern what happens.
   Never call an unknown a bypass, an evasion, or a hole.
2. **Reconstructed is evaluation, never interrogation.** Results from
   documented semantics describe the paper surface; they are not live
   measurements of a running harness.
3. **Nothing here executes.** `check_command` evaluates text. If you need
   to know what actually happens, that is the Effect layer, and it needs a
   live run with its own evidence — say so, don't infer it.
4. **Cite the route, not a grade.** "Codex, vendor-confirmed" is a claim.
   "Codex is supported" is not — never describe a harness that way.
5. **Fail closed.** A command you cannot parse, a policy with no matching
   rule, an invariant with an undeclared parameter: report unknown or
   refuse, never invent a verdict or a binding.
