#!/usr/bin/env python3
"""Amp T2 config-evaluation engine (documented semantics ONLY).

Models ONLY what the vendor documents about `amp.permissions` — the point of
the T2-fidelity study is to measure how much a documentation-faithful
evaluation reproduces the T1 oracle. Anything observed empirically but never
documented is a DELIBERATE CEILING here, not a bug.

Documented semantics modelled (sources cited per rule):
  D1. `amp.permissions` is an ordered list of entries; the FIRST matching
      entry wins. (Vendor announcement "Tool-Level Permissions",
      ampcode.com/news/tool-level-permissions, 2025-08-07 — DOC.)
  D2. Entry actions: allow | reject | ask | delegate. (Same announcement — DOC.)
  D3. A built-in permission list acts as the no-match fallback. The built-in
      list is NOT published — a documentation-faithful evaluator cannot
      enumerate it, so built-in-only decisions serialize as unknown here.
      (Announcement: "a built-in permission list as no-match fallback" — DOC
      for the existence, not the content.)
  D4. Rule shape: entries carry a `tool` (globs supported — the announcement's
      entries imply pattern matching; the spike recorded tool:"Bash" exact
      and "mcp__playwright__*" glob examples) and per-argument `matches`.
      (Shape documented in broad strokes by the announcement; the exact
      `matches.cmd` grammar is NOT in the published settings schema.)

Deliberately NOT modelled (documented ceilings, recorded not simulated):
  C1. The `matches.cmd` glob-vs-regex grammar: the published schema does not
      document it. This evaluator interprets `*`-patterns as globs matched
      against the command string as written (the announcement's entries are
      pattern-like); regex-delimited patterns ("/.../") are NOT interpreted
      (they never match here) — regex semantics are undocumented.
  C2. The built-in permission ruleset (content unpublished): any case the
      oracle decides via a built-in rule is unknown to this evaluator.
  C3. Tool-name glob subtleties beyond `*`; `delegate --to` semantics;
      workspace-vs-user settings layering; `--context` dimensions.

No-match -> unknown (INV-005), with layer attribution. This evaluator never
interrogates the oracle; every result is evidence class
"T2-evaluation (never interrogated)". Stdlib only.
"""

import fnmatch
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

DOC_SOURCES = [
    "https://ampcode.com/news/tool-level-permissions (2025-08-07): entries with actions allow/reject/ask/delegate, first matching entry wins, built-in permission list as no-match fallback",
    "published CLI settings surface: amp.permissions array in settings JSON",
]

POLICY_MAP = {
    "fixtures/policies/default.rules": REPO / "adapters" / "amp" / "policy" / "corpus.json",
    "fixtures/policies/protected_records.rules": REPO / "adapters" / "amp" / "policy" / "protected.json",
}
for _sfx in ("a", "b", "c", "d", "e", "f"):
    POLICY_MAP[f"evidence/day1-baseline-2026-10-21/prec_{_sfx}.rules"] = (
        REPO / "adapters" / "amp" / "policy" / f"prec_{_sfx}.json")

ACTION_MAP = {"allow": "allow", "ask": "prompt", "reject": "forbidden",
              "delegate": "unmapped"}

ATTRIBUTION = ("no documented-semantics decision; a documentation-faithful "
               "evaluation cannot say (built-in rules unpublished, "
               "matches.cmd grammar undocumented)")


def tool_matches(pattern, tool):
    # D4: tool globs; '*' is the only documented-by-example wildcard.
    return fnmatch.fnmatchcase(tool, pattern)


def cmd_matches(pattern, cmd):
    # D1/D4, ceilings C1: '*' patterns are globs against the command string
    # as written; regex-delimited patterns are not interpreted (undocumented).
    if len(pattern) >= 2 and pattern.startswith("/") and pattern.endswith("/"):
        return False  # C1 ceiling: regex semantics undocumented
    return fnmatch.fnmatchcase(cmd, pattern)


def evaluate(cmd_str, policy_path, tool="Bash"):
    """Return (decision, matched_rule_or_None, note)."""
    policy = json.loads(Path(policy_path).read_text())
    rules = policy.get("amp.permissions", [])
    for i, rule in enumerate(rules):
        if not tool_matches(rule.get("tool", ""), tool):
            continue
        matchers = (rule.get("matches") or {}).get("cmd", [])
        if any(cmd_matches(p, cmd_str) for p in matchers):
            action = rule.get("action")
            return ACTION_MAP.get(action, "unknown"), {"index": i, "rule": rule}, \
                f"first matching user rule (index {i})"
    return "unknown", None, "no documented user rule matched (C2: built-in fallback not enumerable)"


def main():
    fixtures_doc = json.loads((REPO / "fixtures" / "fixtures.json").read_text())
    cases = [("corpus", f) for f in fixtures_doc["fixtures"]]
    prot_pub = json.loads((REPO / "fixtures" / "protected_records_public.json").read_text())
    cases += [("protected-public", f) for f in prot_pub["fixtures"]]
    prot_ho = REPO / "fixtures" / "protected_records_heldout.json"
    if prot_ho.exists():
        cases += [("protected-heldout", f)
                  for f in json.loads(prot_ho.read_text())["fixtures"]]
    rows = []
    for family, f in cases:
        cmd_str = " ".join(f["argv"])
        decision, matched, note = evaluate(cmd_str, POLICY_MAP[f["rules"]])
        rows.append({
            "family": family, "fixture_id": f["id"], "argv": f["argv"],
            "command_string": cmd_str, "policy_file": str(POLICY_MAP[f["rules"]].relative_to(REPO)),
            "t2_decision": decision, "t2_note": note,
            "layer_attribution": ATTRIBUTION if decision == "unknown" else None,
        })
    json.dump(rows, sys.stdout, indent=2)


if __name__ == "__main__":
    sys.exit(main())
