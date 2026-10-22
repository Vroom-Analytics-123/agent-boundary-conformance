#!/usr/bin/env python3
"""T2 evaluation engine for OpenCode 1.x permission-object semantics.

Evidence class: T2-evaluation (NEVER interrogated). There is no native
check/evaluate oracle at 1.19.3 (spike (a), see TEST_LOG.md); this engine
re-implements the vendor's DOCUMENTED matching semantics from
https://opencode.ai/docs/permissions (retrieved 2026-10-22) and labels every
output accordingly.

Documented 1.x semantics implemented here:
  * permission verbs: allow / ask / deny
  * permission object: global "*", per-tool verb, or per-tool {pattern: verb}
  * pattern wildcards: '*' = zero+ chars, '?' = exactly one char, else literal
  * '~' or '$HOME' at pattern START expands to the home directory
  * LAST matching rule wins (order-dependent; key order of the JSON object)
  * per-agent permission overrides merged with AGENT RULES TAKING PRECEDENCE
  * no pattern match -> no rules-layer decision. The vendor's runtime default
    (most tools allow; doom_loop/external_directory ask) is documented as
    LAYER ATTRIBUTION ONLY; the framework serializes no-match as `unknown`
    with layer attribution, never as allow (INV-005).

Shared vocabulary: allow / prompt (ask) / forbidden (deny) / unknown / unmapped.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

DOC_URL = "https://opencode.ai/docs/permissions"

SHARED = ("allow", "prompt", "forbidden", "unknown", "unmapped")

# OpenCode verb -> shared vocabulary
VERB_TO_SHARED = {"allow": "allow", "ask": "prompt", "deny": "forbidden"}

NO_MATCH_ATTRIBUTION = (
    "no rules-layer match; OpenCode 1.x runtime default per vendor docs is "
    "'allow' for most tools ('ask' for doom_loop/external_directory) — "
    "runtime default NOT measured; serialized as unknown per framework "
    "INV-005 (unmatched-reported-as-unknown, never allow)"
)


# --------------------------------------------------------------------------
# Wildcard matching
# --------------------------------------------------------------------------

def expand_home(pattern: str, home: str) -> str:
    """Expand leading ~ or $HOME per the vendor doc (start of pattern only)."""
    if pattern == "~" or pattern.startswith("~/"):
        return home + pattern[1:]
    if pattern == "$HOME" or pattern.startswith("$HOME/"):
        return home + pattern[5:]
    return pattern


def pattern_to_regex(pattern: str, home: str) -> "re.Pattern":
    """Translate OpenCode 1.x simple wildcards to a full-match regex.

    '*' -> zero or more of any character; '?' -> exactly one character;
    all other characters match literally. Home expansion first.
    """
    expanded = expand_home(pattern, home)
    out = []
    for ch in expanded:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out) + r"\Z", re.DOTALL)


def pattern_matches(pattern: str, text: str, home: str | None = None) -> bool:
    home = home if home is not None else os.path.expanduser("~")
    return pattern_to_regex(pattern, home).match(text) is not None


# --------------------------------------------------------------------------
# Permission evaluation
# --------------------------------------------------------------------------

@dataclass
class EvalResult:
    decision: str                      # shared vocabulary
    matched: list                      # [(match_index, pattern, effect), ...] in config order
    notes: list = field(default_factory=list)


def _verb_decision(verb: str, note: str) -> EvalResult:
    return EvalResult(decision=VERB_TO_SHARED[verb], matched=[], notes=[note])


def _tool_patterns(permission_value, tool: str, home: str):
    """Resolve the ordered [(pattern, effect)] list applicable to `tool`.

    Returns (kind, payload) where kind is one of:
      'verb'      -> payload is the verb string
      'patterns'  -> payload is the ordered list of (pattern, effect)
      'none'      -> payload is None (no rules-layer entry for this tool)
    """
    if isinstance(permission_value, str):
        # "permission": "allow" — applies to everything (doc: set all at once)
        return "verb", permission_value
    if not isinstance(permission_value, dict):
        return "none", None
    entry = permission_value.get(tool, None)
    if isinstance(entry, str):
        return "verb", entry
    if isinstance(entry, dict):
        return "patterns", list(entry.items())
    # fall back to the global "*" tool key (doc: "set permissions globally (with *)")
    star = permission_value.get("*", None)
    if isinstance(star, str):
        return "verb", star
    if isinstance(star, dict):
        # "*" with a pattern object: undocumented; evaluate its patterns as a
        # global fallback. Documented as inference, tested in test_engine.py.
        return "patterns", list(star.items())
    return "none", None


def evaluate_permission(permission, tool: str, command: str,
                        home: str | None = None,
                        agent_permission=None) -> EvalResult:
    """Evaluate one tool call against a 1.x permission config.

    `permission` is the value of the top-level "permission" key (verb or dict).
    `agent_permission` is the agent's "permission" value, merged with the agent
    rules taking precedence (appended after global patterns under
    last-match-wins; a verb replaces the tool entry outright).
    """
    home = home if home is not None else os.path.expanduser("~")
    if agent_permission is not None:
        permission = _merge_agent_permission(permission, agent_permission)

    kind, payload = _tool_patterns(permission, tool, home)
    if kind == "verb":
        return _verb_decision(payload, "global/tool verb %r" % payload)
    if kind == "none":
        return EvalResult(decision="unknown", matched=[],
                          notes=[NO_MATCH_ATTRIBUTION])
    matched = []
    for idx, (pattern, effect) in enumerate(payload):
        if pattern_matches(pattern, command, home):
            matched.append((idx, pattern, effect))
    if not matched:
        return EvalResult(decision="unknown", matched=[],
                          notes=[NO_MATCH_ATTRIBUTION])
    last = matched[-1]
    notes = []
    if len(matched) > 1:
        notes.append(
            "last-match-wins: %d patterns matched; last (index %d, %r -> %s) decides"
            % (len(matched), last[0], last[1], last[2])
        )
    return EvalResult(decision=VERB_TO_SHARED[last[2]], matched=matched,
                      notes=notes)


def _merge_agent_permission(base, agent):
    """Merge per-agent permission config over the global one.

    Vendor doc: "Agent permissions are merged with the global config, and
    agent rules take precedence." Merge mechanics (INFERENCE on that sentence):
    per tool key, an agent verb replaces the entry outright; an agent
    pattern-object is appended AFTER the global patterns so that under
    last-match-wins the agent's matching rule decides.
    """
    if not isinstance(agent, dict):
        return base
    if isinstance(base, str):
        # global verb + agent dict: agent entries refine per tool; the global
        # verb remains the fallback for tools the agent does not mention.
        merged = dict(agent)
        merged.setdefault("__global_verb__", base)
        base_dict = {"*": base}
        base = base_dict
    merged = dict(base) if isinstance(base, dict) else {}
    for tool, agent_entry in agent.items():
        if tool.startswith("__"):
            continue
        base_entry = merged.get(tool, None)
        if isinstance(agent_entry, str):
            merged[tool] = agent_entry  # verb replaces outright
        elif isinstance(agent_entry, dict):
            if isinstance(base_entry, dict):
                combined = dict(base_entry)
                combined.update(agent_entry)  # agent keys appended last
                # preserve true global-then-agent ordering explicitly:
                ordered = list(base_entry.items()) + [
                    (k, v) for k, v in agent_entry.items()
                ]
                merged[tool] = dict(ordered)
            else:
                merged[tool] = dict(agent_entry)
    return merged


# --------------------------------------------------------------------------
# Corpus ingestion helpers
# --------------------------------------------------------------------------

def normalize_command(argv) -> str:
    """EXPLICIT NORMALIZATION ASSUMPTION (T2 ceiling, see policy/README.md).

    OpenCode matches 'parsed commands' but the parsing step is unspecified
    vendor-side. The engine evaluates the literal single-space join of argv.
    """
    return " ".join(argv)


PREFIX_RULE_RE = re.compile(
    r'prefix_rule\(\s*pattern=\[(?P<tokens>.*?)\]\s*,\s*decision="(?P<decision>[a-z]+)"\s*\)'
)
TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def translate_prefix_rules(rules_text: str):
    """Translate codex-style prefix_rule lines to OpenCode shell patterns.

    prefix_rule(pattern=[t1..tn], decision=d) -> ("t1 ... tn*", verb),
    preserving file order. allow->allow, prompt->ask, forbidden->deny.
    """
    out = []
    for m in PREFIX_RULE_RE.finditer(rules_text):
        tokens = TOKEN_RE.findall(m.group("tokens"))
        decision = m.group("decision")
        verb = {"allow": "allow", "prompt": "ask", "forbidden": "deny"}[decision]
        out.append((" ".join(tokens) + "*", verb))
    return out


def shell_permission_config(ordered_pairs):
    """Build a minimal opencode.json dict with a shell pattern object."""
    return {"$schema": "https://opencode.ai/config.json",
            "permission": {"shell": dict(ordered_pairs)}}


# --------------------------------------------------------------------------
# Corpus driver
# --------------------------------------------------------------------------

ADAPTER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(ADAPTER_DIR))


def load_policy(path):
    with open(os.path.join(ADAPTER_DIR, path)) as f:
        return json.load(f)


def policies_for_fixture(rules_ref: str):
    """Return (baseline_cfg, swapped_cfg, baseline_label, swapped_label)."""
    if rules_ref == "fixtures/policies/default.rules":
        return (load_policy("policy/opencode.json"),
                load_policy("policy/policy.order-swapped.json"),
                "policy/opencode.json", "policy/policy.order-swapped.json")
    if rules_ref == "fixtures/policies/protected_records.rules":
        return (load_policy("policy/protected-records.json"),
                load_policy("policy/protected-records.order-swapped.json"),
                "policy/protected-records.json",
                "policy/protected-records.order-swapped.json")
    if "prec_" in rules_ref:
        fname = os.path.basename(rules_ref)
        with open(os.path.join(REPO_DIR, "evidence/day1-baseline-2026-10-21", fname)) as f:
            pairs = translate_prefix_rules(f.read())
        return (shell_permission_config(pairs),
                shell_permission_config(list(reversed(pairs))),
                "translated:" + rules_ref, "translated:" + rules_ref + ":reversed")
    raise ValueError("unknown rules ref: %r" % rules_ref)


def evaluate_fixture(fixture, shard, codex_baseline, home=None):
    argv = fixture["argv"]
    cmd = normalize_command(argv)
    base_cfg, swap_cfg, base_label, swap_label = policies_for_fixture(fixture["rules"])
    r_base = evaluate_permission(base_cfg.get("permission"), "shell", cmd, home=home)
    r_swap = evaluate_permission(swap_cfg.get("permission"), "shell", cmd, home=home)

    def matched_json(r):
        return [{"match_index": i, "pattern": p, "effect": e}
                for (i, p, e) in r.matched]

    notes = []
    if fixture.get("resolve_host_executables"):
        notes.append(
            "resolve_host_executables=true is a Codex-layer concept; OpenCode "
            "1.x has no documented equivalent — evaluated on the LITERAL "
            "command string. Divergences here are layer-coverage gaps, not "
            "verdict-semantics differences."
        )
    notes.extend(r_base.notes)

    fid = fixture["id"]
    expected = fixture.get("expected")
    codex = codex_baseline.get(fid)
    rec = {
        "fixture_id": fid,
        "shard": shard,
        "argv": argv,
        "evaluated_form": cmd,
        "maps_to": fixture.get("maps_to"),
        "policy_baseline": base_label,
        "policy_swapped": swap_label,
        "matched_rules_baseline": matched_json(r_base),
        "decision_baseline": r_base.decision,
        "matched_rules_swapped": matched_json(r_swap),
        "decision_swapped": r_swap.decision,
        "order_flip": r_base.decision != r_swap.decision,
        "fixture_expected": expected,
        "codex_t1_baseline": codex,
        "diverges_from_expected": (expected is not None
                                   and r_base.decision != expected),
        "diverges_from_codex": (codex is not None
                                and r_base.decision != codex),
        "notes": "; ".join(notes) if notes else "",
    }
    return rec


def load_codex_baseline():
    """Codex T1 native decisions (codex execpolicy check 0.149.0).

    From evidence/reruns/rerun-20261022T160502Z.json (41-case corpus, current
    default.rules; R-variants with --resolve-host-executables). No-match
    stdout {"matchedRules":[]} maps to unknown. PA-* from
    fixtures/protected_records_public.json expected values (native rules-layer
    decisions; day-3 bundle 11/11 pass).
    """
    base = {}
    with open(os.path.join(REPO_DIR, "evidence/reruns/rerun-20261022T160502Z.json")) as f:
        for x in json.load(f)["results"]:
            actual = x.get("actual")
            base[x["id"]] = actual if actual else "unknown"
    with open(os.path.join(REPO_DIR, "fixtures/protected_records_public.json")) as f:
        for fx in json.load(f)["fixtures"]:
            base[fx["id"]] = fx["expected"]
    with open(os.path.join(REPO_DIR, "fixtures/protected_records_heldout.json")) as f:
        for fx in json.load(f)["fixtures"]:
            base[fx["id"]] = fx["expected"]
    return base


def run_corpus(home=None):
    """Evaluate all corpus fixtures; returns (public_records, heldout_records)."""
    codex = load_codex_baseline()
    public, heldout = [], []
    with open(os.path.join(REPO_DIR, "fixtures/corpus_public.json")) as f:
        for fx in json.load(f)["fixtures"]:
            public.append(evaluate_fixture(fx, "public", codex, home=home))
    with open(os.path.join(REPO_DIR, "fixtures/corpus_heldout.json")) as f:
        for fx in json.load(f)["fixtures"]:
            heldout.append(evaluate_fixture(fx, "held-out", codex, home=home))
    with open(os.path.join(REPO_DIR, "fixtures/protected_records_public.json")) as f:
        for fx in json.load(f)["fixtures"]:
            public.append(evaluate_fixture(fx, "public-protected", codex, home=home))
    with open(os.path.join(REPO_DIR, "fixtures/protected_records_heldout.json")) as f:
        for fx in json.load(f)["fixtures"]:
            heldout.append(evaluate_fixture(fx, "held-out-protected", codex, home=home))
    return public, heldout


def aggregate(records):
    counts = {}
    for r in records:
        counts[r["decision_baseline"]] = counts.get(r["decision_baseline"], 0) + 1
    return {
        "count": len(records),
        "decision_baseline_counts": counts,
        "order_flips": sum(1 for r in records if r["order_flip"]),
        "flip_ids": [r["fixture_id"] for r in records if r["order_flip"]],
        "diverge_from_expected": sum(1 for r in records if r["diverges_from_expected"]),
        "diverge_from_expected_ids": [r["fixture_id"] for r in records
                                      if r["diverges_from_expected"]],
        "diverge_from_codex": sum(1 for r in records if r["diverges_from_codex"]),
        "diverge_from_codex_ids": [r["fixture_id"] for r in records
                                   if r["diverges_from_codex"]],
    }


if __name__ == "__main__":
    import hashlib
    public, heldout = run_corpus()
    engine_path = os.path.join(ADAPTER_DIR, "evaluate.py")
    with open(engine_path, "rb") as f:
        engine_sha256 = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(REPO_DIR, "fixtures/corpus_manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(REPO_DIR, "fixtures/protected_records_manifest.json")) as f:
        pmanifest = json.load(f)

    results = {
        "harness": "opencode",
        "version_under_test": "1.19.3 (opencode-linux-x64-baseline npm package; "
                              "1.x permission-object semantics pinned)",
        "route": "config-evaluation",
        "evidence_class": "T2-evaluation (never interrogated)",
        "engine": "adapters/opencode/evaluate.py",
        "engine_sha256": engine_sha256,
        "doc_source": DOC_URL + " (vendor doc, retrieved 2026-10-22)",
        "normalization": "evaluated_form = single-space join of argv "
                         "(explicit assumption; vendor 'parsed commands' "
                         "normalization unspecified)",
        "public_cases": public,
        "heldout_summary": {
            "corpus_heldout": {
                "count": 20,
                "aggregates": aggregate([r for r in heldout
                                         if r["shard"] == "held-out"]),
                "shard_sha256": manifest["held_out"]["sha256"],
            },
            "protected_records_heldout": {
                "count": 5,
                "aggregates": aggregate([r for r in heldout
                                         if r["shard"] == "held-out-protected"]),
                "shard_sha256": pmanifest.get("heldout_sha256",
                                              pmanifest.get("held_out", {})
                                              .get("sha256", "see manifest")),
            },
        },
        "order_swap_effect_all_public": aggregate(public),
        "headliner_divergences_from_codex": [
            {"fixture_id": r["fixture_id"],
             "opencode_baseline": r["decision_baseline"],
             "codex_t1": r["codex_t1_baseline"],
             "note": r["notes"][:220]}
            for r in public if r["diverges_from_codex"]
        ],
    }
    with open(os.path.join(ADAPTER_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
        f.write("\n")
    with open(os.path.join(ADAPTER_DIR, "results_heldout.local.json"), "w") as f:
        json.dump({"harness": "opencode", "shard": "held-out",
                   "cases": heldout}, f, indent=2)
        f.write("\n")
    print("public:", len(public), "heldout:", len(heldout))
    print("public aggregate:", json.dumps(aggregate(public)))
    print("engine_sha256:", engine_sha256)
