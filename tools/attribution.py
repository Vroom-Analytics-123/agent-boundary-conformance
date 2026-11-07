#!/usr/bin/env python3
"""Per-run non-attempt attribution (Reddit-driven, Nov 7, 2026).

When a scenario produces no effect, record WHY in a field separate from
the verdict:

  denied_by_rule  a rule denied it — the denying rule id is cited
  not_attempted   the agent chose not to attempt it, no rule cited
  no_decision     the harness recorded no decision at all

This resolves the "no-action unattributed" bucket (e.g. 13 of 39 runs in
the Muse Code live matrix landed there) instead of renaming it: the
reason a non-attempt happened is now a first-class, separately recorded
fact.

Non-negotiable: a non-attempt is never a hold. The attribution carries
no intent or satisfaction claim — it is a separate field, and the
scoring layer never reads it. An unknown stays unknown.

Fail-closed rules (the repo's standing discipline):
  * The classifier only runs on records whose effect was OBSERVED and
    did not occur (observed_effect == "NOT_OBSERVED"). When the effect
    was never tested (NOT_TESTED, or the field is absent — the case for
    every check-run finding, where no command is ever executed), or when
    an effect did occur (BLOCKED / OCCURRED), it returns None: the
    attribution field is omitted rather than guessed.
  * The denying rule id is best-effort from the record, never invented:
    denied_by_rule with no citable id records attribution_rule_id None.
  * Out-of-vocabulary inputs raise ValueError.

The three-way split is a function of (decision, effect):
  decision forbidden/prompt + no effect  -> denied_by_rule (rule cited)
  decision allow + no effect            -> not_attempted
  decision unknown/error + no effect    -> no_decision

A "prompt" counts as a rule intervention: the rule, not the agent's free
choice, stands between the action and its effect.

Stdlib only.
"""

import json
import re

_RULE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\(.*\)$")

ATTRIBUTIONS = ("denied_by_rule", "not_attempted", "no_decision")
DECISIONS = ("allow", "prompt", "forbidden", "unknown", "error")
OBSERVED_EFFECTS = ("BLOCKED", "OCCURRED", "NOT_OBSERVED", "NOT_TESTED")

_DENY_DECISIONS = ("forbidden", "prompt")
_NO_DECISION_DECISIONS = ("unknown", "error")


def attribute_non_attempt(*, actual_decision, observed_effect=None,
                          matched_rule_ids=None):
    """Classify one non-attempt record.

    Returns {"non_attempt_attribution", "attribution_rule_id"} or None
    when the record is not a classifiable non-attempt (effect never
    observed, or an effect did occur). Raises ValueError on
    out-of-vocabulary inputs.
    """
    if actual_decision not in DECISIONS:
        raise ValueError(f"bad actual_decision: {actual_decision!r}")
    if observed_effect is not None and observed_effect not in OBSERVED_EFFECTS:
        raise ValueError(f"bad observed_effect: {observed_effect!r}")
    if observed_effect in (None, "NOT_TESTED"):
        # Effect never observed: attributing a non-attempt would be
        # fabrication. Applies to every check-run finding.
        return None
    if observed_effect in ("BLOCKED", "OCCURRED"):
        # Not a non-attempt: there is nothing to attribute.
        return None
    # observed_effect == "NOT_OBSERVED": the effect was tested and did not
    # occur; classify by the recorded decision.
    ids = [r for r in (matched_rule_ids or []) if isinstance(r, str) and r]
    if actual_decision in _DENY_DECISIONS:
        return {"non_attempt_attribution": "denied_by_rule",
                "attribution_rule_id": ids[0] if ids else None}
    if actual_decision == "allow":
        # An allow rule is not a denying rule: no citation.
        return {"non_attempt_attribution": "not_attempted",
                "attribution_rule_id": None}
    # unknown / error: no decision was recorded at all.
    return {"non_attempt_attribution": "no_decision",
            "attribution_rule_id": None}


def _first_rule_string(value):
    """First rule id string inside a matched_rules value, or None.

    Rule ids have Tool(spec) form (e.g. "Bash(rm -rf /tmp/x)"); the
    claude-code shape nests them as inner keys —
    {subcommand: {rule: [subcommands]}} — so a plain depth-first walk
    would return the subcommand instead of the rule. Prefer a
    Tool(spec)-shaped key; otherwise descend.
    """
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for k in value:
            if isinstance(k, str) and _RULE_RE.match(k):
                return k
        for v in value.values():
            got = _first_rule_string(v)
            if got is not None:
                return got
        return None
    if isinstance(value, list):
        for item in value:
            got = _first_rule_string(item)
            if got is not None:
                return got
        return None
    return None


def _rule_id_from_raw_entry(entry):
    """Rule id from one codex-style matchedRules entry, or None."""
    if isinstance(entry, str):
        return entry or None
    if not isinstance(entry, dict):
        return None
    for key in ("rule", "id", "name"):
        if isinstance(entry.get(key), str) and entry[key]:
            return entry[key]
    prefix = (entry.get("prefixRuleMatch") or {}).get("matchedPrefix")
    if isinstance(prefix, list) and prefix and all(
            isinstance(p, str) for p in prefix):
        return " ".join(prefix)
    return None


def first_matched_rule_id(matched_rules, raw=None):
    """Best-effort denying-rule id from an adapter result, or None.

    matched_rules is int (codex: a count only — carries no id) or a
    dict/list of rule ids (reconstructed engines). For codex, the id
    comes from the raw native output's matchedRules entries
    (prefixRuleMatch.matchedPrefix, e.g. "rm -rf"). Never invented:
    anything unparseable yields None.
    """
    got = _first_rule_string(matched_rules)
    if got is not None:
        return got
    if isinstance(matched_rules, int):
        # A count is not an id; fall through to the raw output.
        pass
    elif matched_rules:
        return None
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    entries = parsed.get("matchedRules")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        got = _rule_id_from_raw_entry(entry)
        if got is not None:
            return got
    return None


def summarize_repeats(actual_decisions):
    """Per-scenario agreement/variance across N repeats.

    Returns {"n", "outcomes" (decision -> count, first-seen order),
             "agreement" ("unanimous" | "split"),
             "modal_decision" (most frequent; ties break to the earliest
             repeat)}. Raises ValueError on an empty list or an
    out-of-vocabulary decision.
    """
    decisions = list(actual_decisions)
    if not decisions:
        raise ValueError("cannot summarize zero repeats")
    for d in decisions:
        if d not in DECISIONS:
            raise ValueError(f"bad actual_decision in repeats: {d!r}")
    counts = {}
    first_seen = {}
    for i, d in enumerate(decisions):
        counts[d] = counts.get(d, 0) + 1
        first_seen.setdefault(d, i)
    modal = max(counts, key=lambda d: (counts[d], -first_seen[d]))
    return {
        "n": len(decisions),
        "outcomes": dict(counts),
        "agreement": "unanimous" if len(counts) == 1 else "split",
        "modal_decision": modal,
    }
