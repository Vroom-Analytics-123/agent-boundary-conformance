#!/usr/bin/env python3
"""Boundary schemas v1 — dataclasses, validation, and serialization guards.

Stdlib only. Implements the non-negotiable semantics from
docs/WEEK1_BUILD_SPEC.md in code, around the v0 runner's existing I/O:

  INV-005: a native no-match (matchedRules empty / decision omitted) MUST
           serialize as "unknown". It can NEVER serialize as "allow".
  INV-004: (decided by Anish Oct 21, 2026 — Option A) an unknown finding
           MUST carry layer_attribution; a bare unknown or an allow is
           rejected by the validator.
  INV-005 (self-test): the invariant for no-match commands must accept
           unmatched-reported-as-unknown and must never permit a silent
           allow normalization.

Schema versions: invariant.v1 / finding.v1 / evidence-bundle.v1.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SCHEMA_INVARIANT = "invariant.v1"
SCHEMA_FINDING = "finding.v1"
SCHEMA_BUNDLE = "evidence-bundle.v1"

DECISIONS = ("allow", "prompt", "forbidden", "unknown")
INVARIANT_EXPECTED = ("allow", "prompt", "forbidden", "unmatched-reported-as-unknown")
EVIDENCE_CLASSES = ("DOC", "REPRO", "THIRD-PARTY", "INFERENCE", "HYPOTHESIS")

LAYER_ATTRIBUTION_UNKNOWN = (
    "no rules-layer decision; runtime outcome depends on approval policy "
    "+ sandbox under the pinned configuration."
)

INV_ID_RE = re.compile(r"^INV-[0-9]{3}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class SchemaViolation(ValueError):
    """Raised when a value cannot be serialized under boundary schemas v1."""


def canonical_json(obj: Any) -> str:    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# INV-005: native-output -> decision serialization (the load-bearing guard)
# ---------------------------------------------------------------------------

def serialize_native_decision(raw_stdout: str) -> Dict[str, Any]:
    """Serialize one native `codex execpolicy check` stdout to a decision.

    Returns {"decision": ..., "matched_rules_count": int}.

    INV-005: a no-match (matchedRules empty, decision omitted, empty or
    unparseable stdout) serializes as "unknown" and NEVER as "allow".
    A non-empty matchedRules set with a recognized decision returns that
    decision; anything else falls back to "unknown" (fail closed).
    """
    matched: List[Any] = []
    decision: Optional[str] = None
    text = (raw_stdout or "").strip()
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                m = parsed.get("matchedRules")
                matched = m if isinstance(m, list) else []
                d = parsed.get("decision")
                decision = d if isinstance(d, str) else None
        except json.JSONDecodeError:
            matched, decision = [], None
    if matched and decision in ("allow", "prompt", "forbidden"):
        return {"decision": decision, "matched_rules_count": len(matched)}
    # INV-005: no rules-layer decision -> unknown. Never allow.
    return {"decision": "unknown", "matched_rules_count": len(matched)}


# ---------------------------------------------------------------------------
# Invariant v1
# ---------------------------------------------------------------------------

@dataclass
class Invariant:
    schema_version: str = SCHEMA_INVARIANT
    id: str = ""
    name: str = ""
    kind: str = "native_command_decision"
    command: List[str] = field(default_factory=list)
    expected: List[str] = field(default_factory=list)
    asset: str = ""
    note: str = ""
    layer_attribution: Optional[str] = None
    evidence_class: Optional[str] = None

    def validate(self) -> None:
        if self.schema_version != SCHEMA_INVARIANT:
            raise SchemaViolation(f"bad schema_version: {self.schema_version!r}")
        if not INV_ID_RE.match(self.id):
            raise SchemaViolation(f"bad invariant id: {self.id!r}")
        if not NAME_RE.match(self.name):
            raise SchemaViolation(f"bad invariant name: {self.name!r}")
        if self.kind != "native_command_decision":
            raise SchemaViolation(f"unsupported kind: {self.kind!r}")
        if not self.command or not all(isinstance(c, str) and c for c in self.command):
            raise SchemaViolation(f"bad command: {self.command!r}")
        if not self.expected or len(set(self.expected)) != len(self.expected):
            raise SchemaViolation(f"expected must be a non-empty unique list: {self.expected!r}")
        for e in self.expected:
            if e not in INVARIANT_EXPECTED:
                raise SchemaViolation(f"bad expected value: {e!r}")
        if not self.asset:
            raise SchemaViolation("asset is required")
        # INV-004: decided expectation requires layer attribution.
        if "unmatched-reported-as-unknown" in self.expected:
            if not self.layer_attribution or len(self.layer_attribution) < 20:
                raise SchemaViolation(
                    f"{self.id}: expected 'unmatched-reported-as-unknown' "
                    "requires layer_attribution (INV-004, decided Option A)"
                )
        if self.evidence_class and self.evidence_class not in EVIDENCE_CLASSES:
            raise SchemaViolation(f"bad evidence_class: {self.evidence_class!r}")

    @classmethod
    def from_yaml_v0_dict(cls, d: Dict[str, Any]) -> "Invariant":
        """Lift a security/invariants.yaml (boundary.v0) entry into invariant.v1."""
        inv = cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            kind=d.get("kind", "native_command_decision"),
            command=list(d.get("command", [])),
            expected=list(d.get("expected", [])),
            asset=d.get("asset", ""),
            note=d.get("note", ""),
            evidence_class=d.get("evidence_class"),
        )
        if "unmatched-reported-as-unknown" in inv.expected:
            inv.layer_attribution = LAYER_ATTRIBUTION_UNKNOWN
        inv.validate()
        return inv


# ---------------------------------------------------------------------------
# Finding v1
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    schema_version: str = SCHEMA_FINDING
    fixture_id: str = ""
    invariant_id: str = ""
    maps_to: str = ""
    argv: List[str] = field(default_factory=list)
    raw_native_output: str = ""
    native_matched_rules_count: int = 0
    actual_decision: str = ""
    expected_decision: str = ""
    invariant_expected: List[str] = field(default_factory=list)
    verdict: str = ""
    layer: str = "rules-layer"
    layer_attribution: Optional[str] = None
    corpus_shard: Optional[str] = None
    evidence_class: str = "REPRO"
    pinned: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.schema_version != SCHEMA_FINDING:
            raise SchemaViolation(f"bad schema_version: {self.schema_version!r}")
        if not self.fixture_id:
            raise SchemaViolation("fixture_id is required")
        if not self.invariant_id:
            raise SchemaViolation("invariant_id is required")
        if self.actual_decision not in DECISIONS:
            raise SchemaViolation(f"bad actual_decision: {self.actual_decision!r}")
        if self.expected_decision not in DECISIONS:
            raise SchemaViolation(f"bad expected_decision: {self.expected_decision!r}")
        if self.verdict not in ("pass", "fail"):
            raise SchemaViolation(f"bad verdict: {self.verdict!r}")
        if self.layer != "rules-layer":
            raise SchemaViolation(f"findings are rules-layer only: {self.layer!r}")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise SchemaViolation(f"bad evidence_class: {self.evidence_class!r}")
        if self.corpus_shard and self.corpus_shard not in ("public", "held-out"):
            raise SchemaViolation(f"bad corpus_shard: {self.corpus_shard!r}")
        # INV-005: a finding whose raw output shows no match can never be allow.
        ser = serialize_native_decision(self.raw_native_output)
        if ser["decision"] == "unknown" and self.actual_decision == "allow":
            raise SchemaViolation(
                f"{self.fixture_id}: INV-005 violation — no-match native output "
                "serialized as allow"
            )
        # INV-004: unknown findings must carry layer attribution.
        if self.actual_decision == "unknown":
            if not self.layer_attribution or len(self.layer_attribution) < 20:
                raise SchemaViolation(
                    f"{self.fixture_id}: unknown finding without layer_attribution "
                    "(INV-004 — bare unknowns are rejected)"
                )
        # Verdict must be consistent with actual vs expected.
        want = "pass" if self.actual_decision == self.expected_decision else "fail"
        if self.verdict != want:
            raise SchemaViolation(
                f"{self.fixture_id}: verdict {self.verdict!r} inconsistent with "
                f"actual={self.actual_decision!r} expected={self.expected_decision!r}"
            )
        for key in ("harness", "harness_version", "binary_sha256",
                    "rules_sha256", "invariants_sha256", "corpus_version_hash"):
            if key not in self.pinned:
                raise SchemaViolation(f"pinned.{key} is required")
        if self.pinned.get("harness") != "codex":
            raise SchemaViolation("pinned.harness must be 'codex'")
        if self.pinned.get("harness_version") != "0.149.0":
            raise SchemaViolation("pinned.harness_version must be '0.149.0'")
        for hk in ("binary_sha256", "rules_sha256", "invariants_sha256",
                   "corpus_version_hash"):
            if not HEX64_RE.match(self.pinned.get(hk, "")):
                raise SchemaViolation(f"pinned.{hk} must be a sha256 hex digest")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        d = asdict(self)
        # Drop empty optionals for a clean wire form.
        return {k: v for k, v in d.items() if v not in (None, "", [])}


# ---------------------------------------------------------------------------
# Merkle tree (RFC-6962-style, per the evidence architecture doc)
# ---------------------------------------------------------------------------

def build_merkle(leaf_hexes: List[str]):
    """Canonical Merkle builder. Returns (root_hex, proofs_per_leaf)."""
    if not leaf_hexes:
        raise SchemaViolation("cannot build a Merkle tree over zero leaves")
    nodes = [bytes.fromhex(h) for h in leaf_hexes]
    proofs: List[List[Dict[str, str]]] = [[] for _ in nodes]
    # index map: current-level position -> list of original leaf indices
    owners: List[List[int]] = [[i] for i in range(len(nodes))]
    while len(nodes) > 1:
        if len(nodes) % 2 == 1:
            # Duplicate the odd node (RFC-6962 style). The duplicate is a
            # structural copy only: it owns no real leaves, so it contributes
            # no proof steps — the real leaf acts as the left child and gets
            # exactly one sibling step (itself, direction "right").
            nodes.append(nodes[-1])
            owners.append([])
        nxt, nxt_owners = [], []
        for i in range(0, len(nodes), 2):
            left, right = nodes[i], nodes[i + 1]
            parent = hashlib.sha256(b"\x01" + left + right).digest()
            for li in owners[i]:
                proofs[li].append({"sibling": right.hex(), "direction": "right"})
            for ri in owners[i + 1]:
                proofs[ri].append({"sibling": left.hex(), "direction": "left"})
            nxt.append(parent)
            nxt_owners.append(owners[i] + owners[i + 1])
        nodes, owners = nxt, nxt_owners
    return nodes[0].hex(), proofs


def leaf_hash_for_finding(finding_dict: Dict[str, Any]) -> str:
    return sha256_hex(b"\x00" + canonical_json(finding_dict).encode("utf-8"))


def verify_inclusion(leaf_hex: str, proof: List[Dict[str, str]], root_hex: str) -> bool:
    cur = bytes.fromhex(leaf_hex)
    for step in proof:
        sib = bytes.fromhex(step["sibling"])
        if step["direction"] == "right":
            cur = hashlib.sha256(b"\x01" + cur + sib).digest()
        elif step["direction"] == "left":
            cur = hashlib.sha256(b"\x01" + sib + cur).digest()
        else:
            return False
    return cur.hex() == root_hex


# ---------------------------------------------------------------------------
# Minimal parser for security/invariants.yaml (boundary.v0 exact shape)
# ---------------------------------------------------------------------------

def parse_invariants_yaml(text):
    """Parse the pinned invariants.yaml's exact shape.

    Returns (schema_version, [(id, expected_list), ...]).
    Raises SchemaViolation on anything it does not recognize.
    """
    schema_version = None
    invariants = []
    current = None
    in_invariants = False
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "invariants:":
            in_invariants = True
            continue
        if not in_invariants:
            if stripped.startswith("schema_version:"):
                schema_version = stripped.split(":", 1)[1].strip()
            continue
        m = re.match(r"^\s{2}-\s+id:\s+(\S+)\s*$", line)
        if m:
            current = {"id": m.group(1), "expected": None}
            invariants.append(current)
            continue
        if current is not None:
            m2 = re.match(r"^\s{4}expected:\s+\[(.*)\]\s*$", line)
            if m2:
                items = [x.strip().strip('"') for x in m2.group(1).split(",") if x.strip()]
                current["expected"] = items
    if schema_version != "boundary.v0":
        raise SchemaViolation(f"unexpected invariants schema_version: {schema_version}")
    if len(invariants) != 5:
        raise SchemaViolation(f"expected 5 invariants, got {len(invariants)}")
    for inv in invariants:
        if inv["expected"] is None or not inv["expected"]:
            raise SchemaViolation(f"invariant {inv['id']} has no expected list")
    return schema_version, [(i["id"], i["expected"]) for i in invariants]


INVARIANT_DIRECTIONS = ("restrictive", "permissive", "guard")


def parse_invariant_meta(text):
    """Parse the dual-verdict normative fields of security/invariants.yaml.

    Returns {invariant_id: {"protective_intent": str, "intent_direction": str}}.
    intent_direction must be one of restrictive / permissive / guard.
    protective_intent is required: an invariant without a stated normative
    expectation cannot receive an intent_coverage judgment.

    (Separate from parse_invariants_yaml so existing sealed-evidence tooling
    keeps its exact-shape contract untouched.)
    """
    meta = {}
    current = None
    in_invariants = False
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "invariants:":
            in_invariants = True
            continue
        if not in_invariants:
            continue
        m = re.match(r"^\s{2}-\s+id:\s+(\S+)\s*$", line)
        if m:
            current = {"id": m.group(1), "protective_intent": None,
                       "intent_direction": None}
            meta[current["id"]] = current
            continue
        if current is not None:
            m2 = re.match(r"^\s{4}protective_intent:\s+\"(.*)\"\s*$", line)
            if m2:
                current["protective_intent"] = m2.group(1)
                continue
            m3 = re.match(r"^\s{4}intent_direction:\s+(\S+)\s*$", line)
            if m3:
                current["intent_direction"] = m3.group(1)
    for inv_id, m in meta.items():
        if not m["protective_intent"]:
            raise SchemaViolation(f"invariant {inv_id} has no protective_intent")
        if m["intent_direction"] not in INVARIANT_DIRECTIONS:
            raise SchemaViolation(
                f"invariant {inv_id} has bad intent_direction: "
                f"{m['intent_direction']!r} (want one of {INVARIANT_DIRECTIONS})")
    return meta


# ---------------------------------------------------------------------------
# finding.v2 — dual-verdict field validation (strategic review section 2.2)
# ---------------------------------------------------------------------------

MEASUREMENT_VALIDITY = ("PASS", "FAIL", "NOT_REPRODUCED")
INTENT_COVERAGE = ("SATISFIED", "NOT_SATISFIED", "UNRESOLVED", "NOT_APPLICABLE")
OBSERVED_EFFECT = ("BLOCKED", "OCCURRED", "NOT_OBSERVED", "NOT_TESTED")
UNKNOWN_KINDS = ("no-rule-match", "insufficient-runtime-evidence",
                 "unsupported-adapter")


def validate_dual_verdict_fields(d):
    """Validate the finding.v2 dual-verdict extension fields on a dict.

    Raises SchemaViolation on any violation. The three unknown kinds must
    stay distinct: unknown_kind is required iff actual_decision is unknown.
    """
    mv = d.get("measurement_validity")
    if mv not in MEASUREMENT_VALIDITY:
        raise SchemaViolation(f"bad measurement_validity: {mv!r}")
    ic = d.get("intent_coverage")
    if ic not in INTENT_COVERAGE:
        raise SchemaViolation(f"bad intent_coverage: {ic!r}")
    oe = d.get("observed_effect")
    if oe not in OBSERVED_EFFECT:
        raise SchemaViolation(f"bad observed_effect: {oe!r}")
    if d.get("intent_direction") not in INVARIANT_DIRECTIONS:
        raise SchemaViolation(f"bad intent_direction: {d.get('intent_direction')!r}")
    if not d.get("protective_intent"):
        raise SchemaViolation("protective_intent is required on a v2 finding")
    uk = d.get("unknown_kind")
    if d.get("actual_decision") == "unknown":
        if uk not in UNKNOWN_KINDS:
            raise SchemaViolation(
                f"unknown finding requires a labelled unknown_kind "
                f"(one of {UNKNOWN_KINDS}), got {uk!r}")
    elif uk is not None:
        raise SchemaViolation(
            f"unknown_kind must be absent when actual_decision is "
            f"{d.get('actual_decision')!r}, got {uk!r}")
    # Non-conflation guard: a correctly reported unknown is a successful
    # measurement, never a satisfied protective intent.
    if d.get("actual_decision") == "unknown" and ic == "SATISFIED":
        raise SchemaViolation(
            "unknown actual_decision with intent_coverage SATISFIED: a "
            "correctly reported unknown is measurement PASS, never a "
            "satisfied protective intent")
