#!/usr/bin/env python3
"""Goose T2 config-evaluation engine.

Implements the DOCUMENTED permission semantics of Goose (1.57.0,
docs retrieved 2026-11-03, goose-docs.ai) against a permission.yaml
plus a permission mode. This is a labelled reimplementation of the
vendor's documented semantics -- it NEVER interrogates a native
oracle (Goose has no offline decision-check subcommand). Every result
it produces is evidence class "T2-evaluation (never interrogated)".

Documented semantics modelled:
  1. Modes (goose-docs.ai, permission-modes page): Autonomous (auto)
     approves everything without approval and IS THE DEFAULT
     ("Autonomous Mode is applied by default"); Manual Approval
     (approve) asks before every tool call; Smart Approval
     (smart_approve) auto-approves low-risk actions and flags the
     rest, and supports granular tool permissions; Chat Only (chat)
     uses no tools at all.
  2. Tool permissions (goose-docs.ai, tool-permissions page): each
     tool in an extension carries one of AlwaysAllow / AskBefore /
     NeverAllow. They are configured in Manual or Smart mode and
     override the mode default for that tool. permission.yaml maps
     tool -> level in two categories (user, smart_approve).
  3. Evaluation order (source-read from the vendor repo, recorded
     not re-verified here): a user permission rule decides first;
     in SmartApprove, an MCP readOnlyHint auto-allow and then an LLM
     read-only judge apply when no user rule exists; Deny overrides
     everything (Deny > RequireApproval > Allow).
  4. Granularity ceiling (the finding, not a modelling choice):
     Goose permission rules attach to TOOLS, never to command text.
     Every v1 scenario is a shell command, so every scenario maps to
     the same tool, developer__shell (Developer extension). The
     engine therefore cannot distinguish `rm -rf` from `cat` -- a
     policy that asks before shell asks before both, and a policy
     that always allows shell allows both. Tool granularity is
     recorded in every result's notes.

Deliberately NOT modelled (T2 ceilings, recorded not simulated):
  - The SmartApprove LLM read-only judge: a real run could
    auto-allow a shell command the judge classifies read-only
    (e.g. plain `ls`). Modelled as prompt (the documented-default
    side for write-capable shell use); benign rows may read allow
    in a live run. This ceiling is stated, not hidden.
  - Extension allowlists, MCP readOnlyHint annotations per tool
    beyond the shell tool, and per-session mode changes.
  - Chat mode produces no permission decision at all (tools are
    skipped); it serializes as `unknown` with a layer note, NEVER
    as allow or forbidden.
"""

import argparse
import json
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

TOOL_FOR_SHELL = "developer__shell"
LEVELS = {"always_allow": "allow", "ask_before": "prompt", "never_allow": "forbidden"}
MODES = ("auto", "approve", "smart_approve", "chat")


def load_policy(path):
    """Parse permission.yaml into {category: {tool: level}}."""
    if yaml is None:
        raise SystemExit("PyYAML is required (pip install pyyaml)")
    with open(path) as fh:
        doc = yaml.safe_load(fh) or {}
    out = {}
    for category in ("user", "smart_approve"):
        section = doc.get(category) or {}
        mapping = {}
        for key, decision in (("always_allow", "allow"),
                              ("ask_before", "prompt"),
                              ("never_allow", "forbidden")):
            for tool in section.get(key) or []:
                mapping[str(tool)] = decision
        out[category] = mapping
    return out


def evaluate(command, policy, mode):
    """Decide one shell command under (policy, mode)."""
    tool = TOOL_FOR_SHELL
    if mode == "chat":
        return {
            "decision": "unknown",
            "tool": tool,
            "matched_rule": None,
            "layer": "mode",
            "note": ("Chat Only mode: no tool use, so no permission "
                     "decision exists for this command. Recorded as "
                     "unknown, never as allow or forbidden."),
        }
    user_rule = policy.get("user", {}).get(tool)
    smart_rule = policy.get("smart_approve", {}).get(tool)
    # Deny overrides everything, in every mode.
    if user_rule == "forbidden" or (mode == "smart_approve"
                                    and smart_rule == "forbidden"):
        return {"decision": "forbidden", "tool": tool,
                "matched_rule": "never_allow:" + tool, "layer": "tool-rule",
                "note": "User NeverAllow rule; Deny overrides mode."}
    if mode == "auto":
        return {"decision": "allow", "tool": tool,
                "matched_rule": None, "layer": "mode",
                "note": ("Autonomous mode (the documented default) "
                         "approves without approval; no NeverAllow "
                         "rule blocks this tool.")}
    if mode == "approve":
        if user_rule:
            return {"decision": user_rule, "tool": tool,
                    "matched_rule": {"allow": "always_allow",
                                     "prompt": "ask_before"}.get(user_rule, "") + ":" + tool,
                    "layer": "tool-rule",
                    "note": "Manual mode: user tool rule decides."}
        return {"decision": "prompt", "tool": tool,
                "matched_rule": None, "layer": "mode",
                "note": ("Manual mode asks before every tool call; "
                         "no user rule exists for this tool.")}
    # smart_approve
    if user_rule:
        return {"decision": user_rule, "tool": tool,
                "matched_rule": {"allow": "always_allow",
                                 "prompt": "ask_before"}.get(user_rule, "") + ":" + tool,
                "layer": "tool-rule",
                "note": "SmartApprove: user tool rule decides first."}
    if smart_rule:
        return {"decision": smart_rule, "tool": tool,
                "matched_rule": {"allow": "always_allow",
                                 "prompt": "ask_before"}.get(smart_rule, "") + ":" + tool,
                "layer": "tool-rule",
                "note": "SmartApprove: smart_approve-category rule decides."}
    return {"decision": "prompt", "tool": tool,
            "matched_rule": None, "layer": "mode",
            "note": ("SmartApprove with no rule for this tool: shell "
                     "is write-capable, so it is flagged for approval. "
                     "CEILING: the LLM read-only judge could auto-allow "
                     "a read-only-classified shell command in a live run; "
                     "modelled as prompt.")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--mode", required=True, choices=list(MODES))
    ap.add_argument("--command", required=True)
    args = ap.parse_args()
    policy = load_policy(args.policy)
    result = evaluate(args.command, policy, args.mode)
    result["command"] = args.command
    result["mode"] = args.mode
    result["evidence_class"] = "T2-evaluation (never interrogated)"
    result["granularity"] = ("tool-level only: every shell command "
                             "maps to developer__shell; argv is not "
                             "distinguished by the policy layer")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
