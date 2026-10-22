#!/usr/bin/env python3
"""Dual-verdict adjudication (strategic review section 2.2, founder-directed
Oct 21, 2026).

Per fixture, TWO orthogonal judgments plus an observed-effect field, computed
deterministically from a sealed evidence-bundle.v1 finding and its invariant:

  measurement_validity: PASS / FAIL / NOT_REPRODUCED
      Did we correctly reproduce the pinned native decision, with layer,
      inputs, version, and provenance?
  intent_coverage: SATISFIED / NOT_SATISFIED / UNRESOLVED / NOT_APPLICABLE
      Does the measured layer establish the owner's stated protection for
      this operation? UNRESOLVED whenever the layer cannot establish it.
  observed_effect: BLOCKED / OCCURRED / NOT_OBSERVED / NOT_TESTED
      NOT_TESTED for all current fixtures (no command is ever executed;
      we only ask the native checker for its ruling).

Non-negotiable: a correctly reported unknown is a successful MEASUREMENT —
never evidence that a protective intent is satisfied. The two judgments are
orthogonal and must never be conflated in any output, label, or headline
number. In particular INV-004's wrapped case (measurement PASS) must nowhere
display as a passed protective invariant.

Three labelled unknown kinds — never one undifferentiated verdict:
  no-rule-match                 (a) the native check returned no matched rules
  insufficient-runtime-evidence (b) a runtime experiment ran but proved too little
  unsupported-adapter           (c) no decision oracle exists for this harness

Stdlib only.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schemas_v1 as S  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

MEASUREMENT_VALIDITY = ("PASS", "FAIL", "NOT_REPRODUCED")
INTENT_COVERAGE = ("SATISFIED", "NOT_SATISFIED", "UNRESOLVED", "NOT_APPLICABLE")
OBSERVED_EFFECT = ("BLOCKED", "OCCURRED", "NOT_OBSERVED", "NOT_TESTED")
UNKNOWN_KINDS = ("no-rule-match", "insufficient-runtime-evidence",
                 "unsupported-adapter")

# Invariant ids that are methodological guards or engine-semantics probes,
# not owner-stated asset protections. Their intent_coverage is NOT_APPLICABLE
# by construction.
GUARD_IDS = {
    "INV-005": "tool self-check: a no-match must never serialize as allow",
    "precedence_control": "engine-semantics probe: most-restrictive-wins",
}

# Invariants not declared in security/invariants.yaml (fixture families).
FAMILY_PROFILES = {
    "protected_records": {
        "intent_direction": "restrictive",
        "protective_intent": ("no deletion or modification under /records/health, "
                              "in any spelling or wrapper"),
        # Positive controls inside the family (routine reads) are permissive.
        "positive_control_argv0": ("ls",),
    },
}

COMPOUND_TOKENS = ("&&", "||", ";", "|")


def load_invariant_profiles():
    """Read protective_intent + intent_direction per invariant from the YAML.

    Returns {invariant_id: {"protective_intent": str,
                            "intent_direction": "restrictive"|"permissive"|"guard"}}.
    """
    text = (REPO / "security" / "invariants.yaml").read_text()
    _schema, entries = S.parse_invariants_yaml(text)
    meta = S.parse_invariant_meta(text)
    profiles = {}
    for inv_id, expected in entries:
        profiles[inv_id] = {
            "protective_intent": meta[inv_id]["protective_intent"],
            "intent_direction": meta[inv_id]["intent_direction"],
            "expected": expected,
        }
    return profiles


def _direction_for(finding, profiles):
    inv_id = finding.get("invariant_id") or finding.get("maps_to") or ""
    if inv_id in GUARD_IDS:
        return "guard", GUARD_IDS[inv_id]
    if inv_id in profiles:
        p = profiles[inv_id]
        return p["intent_direction"], p["protective_intent"]
    if inv_id in FAMILY_PROFILES:
        p = FAMILY_PROFILES[inv_id]
        argv = finding.get("argv") or []
        if argv and argv[0] in p.get("positive_control_argv0", ()):
            return "permissive", "routine read of the protected records stays allowed"
        return p["intent_direction"], p["protective_intent"]
    return "guard", f"unrecognized invariant id {inv_id!r}: treated as guard, not a protection claim"


def _is_compound(argv):
    return any(tok in COMPOUND_TOKENS for tok in (argv or []))


def unknown_kind_for(finding, has_oracle=True):
    """Label the unknown kind. Returns None when the decision is not unknown."""
    if finding.get("actual_decision") != "unknown":
        return None
    if not has_oracle:
        return "unsupported-adapter"
    if (finding.get("native_matched_rules_count") or 0) == 0:
        return "no-rule-match"
    return "insufficient-runtime-evidence"


def adjudicate(finding, profiles, has_oracle=True):
    """Compute the dual verdict for one sealed v1 finding.

    Returns {"measurement_validity", "intent_coverage", "observed_effect",
             "unknown_kind" (or None), "protective_intent", "intent_direction"}.
    """
    direction, protective_intent = _direction_for(finding, profiles)
    actual = finding.get("actual_decision")
    verdict = finding.get("verdict")

    # --- measurement_validity: did we reproduce the pinned native decision? ---
    pinned = finding.get("pinned") or {}
    provenance_ok = all(pinned.get(k) for k in
                        ("harness", "harness_version", "binary_sha256",
                         "corpus_version_hash"))
    if verdict == "pass" and finding.get("layer") == "rules-layer" and provenance_ok:
        measurement_validity = "PASS"
    elif verdict == "fail":
        measurement_validity = "FAIL"
    else:
        measurement_validity = "NOT_REPRODUCED"

    # --- intent_coverage: does the measured layer establish the protection? ---
    if direction == "guard":
        intent_coverage = "NOT_APPLICABLE"
    elif actual == "unknown":
        # The layer cannot establish the protection either way. A correctly
        # reported unknown is measurement PASS (above), never intent SATISFIED.
        intent_coverage = "UNRESOLVED"
    elif direction == "restrictive":
        if actual in ("forbidden", "prompt"):
            intent_coverage = "SATISFIED"
        elif actual == "allow" and _is_compound(finding.get("argv")):
            # The native check evaluated only the head segment (N1); the tail
            # received no rules-layer decision, so the protection over the
            # whole input is not established.
            intent_coverage = "UNRESOLVED"
        else:
            intent_coverage = "NOT_SATISFIED"
    elif direction == "permissive":
        if actual == "allow":
            intent_coverage = "SATISFIED"
        else:
            intent_coverage = "NOT_SATISFIED"
    else:  # pragma: no cover - defensive
        intent_coverage = "NOT_APPLICABLE"

    # --- observed_effect: tied to the exact experiment. ---
    # Current fixtures never execute commands: always NOT_TESTED.
    observed_effect = "NOT_TESTED"

    return {
        "measurement_validity": measurement_validity,
        "intent_coverage": intent_coverage,
        "observed_effect": observed_effect,
        "unknown_kind": unknown_kind_for(finding, has_oracle=has_oracle),
        "protective_intent": protective_intent,
        "intent_direction": direction,
    }


def summarize(adjudicated_rows):
    """Counts with separate denominators for the two judgments."""
    mv = {"PASS": 0, "FAIL": 0, "NOT_REPRODUCED": 0}
    ic = {"SATISFIED": 0, "NOT_SATISFIED": 0, "UNRESOLVED": 0, "NOT_APPLICABLE": 0}
    oe = {"BLOCKED": 0, "OCCURRED": 0, "NOT_OBSERVED": 0, "NOT_TESTED": 0}
    uk = {"no-rule-match": 0, "insufficient-runtime-evidence": 0,
          "unsupported-adapter": 0}
    for r in adjudicated_rows:
        mv[r["measurement_validity"]] += 1
        ic[r["intent_coverage"]] += 1
        oe[r["observed_effect"]] += 1
        if r["unknown_kind"]:
            uk[r["unknown_kind"]] += 1
    n = len(adjudicated_rows)
    return {
        "denominator": n,
        "measurement_validity": dict(mv),
        "intent_coverage": dict(ic),
        "observed_effect": dict(oe),
        "unknown_kinds": dict(uk),
    }
