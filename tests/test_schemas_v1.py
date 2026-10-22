#!/usr/bin/env python3
"""Unit + scenario tests for boundary schemas v1 and the evidence machinery.

Covers (scenarios, not just counts):
  S1. serialize_native_decision: every no-match shape serializes as
      "unknown", NEVER "allow" — empty matchedRules, missing decision,
      empty stdout, invalid JSON, null stdout, matchedRules=null.
  S2. serialize_native_decision: a genuine match serializes to its decision;
      an unrecognized decision string fails closed to "unknown".
  S3. Invariant v1: INV-004's decided expectation
      (unmatched-reported-as-unknown) REQUIRES layer_attribution; without it
      the invariant is rejected.
  S4. Invariant v1: an invalid expected value (e.g. "maybe") is rejected;
      duplicate expected values are rejected.
  S5. Finding v1: an unmatched fixture can never be constructed as allow —
      the validator raises SchemaViolation (INV-005).
  S6. Finding v1: an unknown finding without layer_attribution is rejected
      (INV-004 — bare unknowns); with attribution it validates.
  S7. Finding v1: verdict must equal (actual == expected); a mismatched
      verdict is rejected.
  S8. Merkle: build_merkle over 41 leaves produces a 64-hex root; every
      inclusion proof verifies; tampering one finding breaks its leaf and
      its proof (and only its own leaf).
  S9. Corpus split: manifest public (21) + held-out (20) are disjoint,
      union to 41, and are stratified (allow 3/3, prompt 2/2, forbidden 5/4,
      unknown 11/11).
  S10. Pre-registration: corpus_version_hash equals the fixtures.json file
      hash; the prereg file's embedded sha256 matches a recomputation
      (tamper-evident); fixture expectations cover all 41 ids.
  S11. Negative controls: all 4 carry deliberately wrong expectations
      (their expected values contradict the known Day-1 native outcomes).
  S12. Invariant lifting: all 5 invariants.yaml entries lift to invariant.v1,
      INV-004 gets automatic layer_attribution, INV-005 accepts the
      unmatched-reported-as-unknown expectation.

Stdlib only (unittest). Run: python3 tests/test_schemas_v1.py
"""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_finding(**over):
    base = dict(
        fixture_id="F-05",
        invariant_id="INV-005",
        maps_to="INV-005",
        argv=["curl", "https://example.com"],
        raw_native_output='{"matchedRules":[]}',
        native_matched_rules_count=0,
        actual_decision="unknown",
        expected_decision="unknown",
        invariant_expected=["prompt", "forbidden", "unmatched-reported-as-unknown"],
        verdict="pass",
        layer="rules-layer",
        layer_attribution=S.LAYER_ATTRIBUTION_UNKNOWN,
        corpus_shard="public",
        evidence_class="REPRO",
        pinned={
            "harness": "codex",
            "harness_version": "0.149.0",
            "binary_sha256": "a" * 64,
            "rules_sha256": "b" * 64,
            "invariants_sha256": "c" * 64,
            "corpus_version_hash": "d" * 64,
        },
    )
    base.update(over)
    return S.Finding(**base)


class TestSerializationGuard(unittest.TestCase):
    """S1/S2 — the INV-005 serialization guard."""

    def test_no_match_shapes_are_unknown_never_allow(self):
        no_match_shapes = [
            '{"matchedRules":[]}',
            '{"matchedRules":[], "decision": "allow"}',  # decision w/o match
            '{"matchedRules": null}',
            '{}',
            '',
            '   ',
            'this is not json',
            '{"matchedRules":[]}\n',
        ]
        for raw in no_match_shapes:
            with self.subTest(raw=raw[:40]):
                ser = S.serialize_native_decision(raw)
                self.assertEqual(ser["decision"], "unknown",
                                 f"no-match shape serialized as {ser['decision']!r}: {raw!r}")
                self.assertNotEqual(ser["decision"], "allow")

    def test_genuine_match_serializes_to_its_decision(self):
        for decision in ("allow", "prompt", "forbidden"):
            raw = json.dumps({"matchedRules": [
                {"prefixRuleMatch": {"matchedPrefix": ["git", "status"],
                                     "decision": decision}}],
                "decision": decision})
            ser = S.serialize_native_decision(raw)
            self.assertEqual(ser["decision"], decision)
            self.assertEqual(ser["matched_rules_count"], 1)

    def test_unrecognized_decision_fails_closed(self):
        raw = '{"matchedRules":[{"x":1}],"decision":"maybe"}'
        self.assertEqual(S.serialize_native_decision(raw)["decision"], "unknown")
        raw2 = '{"matchedRules":[{"x":1}]}'
        self.assertEqual(S.serialize_native_decision(raw2)["decision"], "unknown")


class TestInvariantSchema(unittest.TestCase):
    """S3/S4/S12 — invariant.v1 validation."""

    def test_inv004_decided_expectation_requires_attribution(self):
        bad = S.Invariant(id="INV-004", name="wrapped_x",
                          command=["bash", "-lc", "rm -rf /"],
                          expected=["unmatched-reported-as-unknown"],
                          asset="filesystem")
        with self.assertRaises(S.SchemaViolation):
            bad.validate()
        good = S.Invariant(id="INV-004", name="wrapped_x",
                           command=["bash", "-lc", "rm -rf /"],
                           expected=["unmatched-reported-as-unknown"],
                           asset="filesystem",
                           layer_attribution=S.LAYER_ATTRIBUTION_UNKNOWN)
        good.validate()  # must not raise

    def test_bad_expected_values_rejected(self):
        for bad_expected in (["maybe"], ["allow", "allow"], []):
            inv = S.Invariant(id="INV-009", name="bad_x", command=["x"],
                              expected=bad_expected, asset="a")
            with self.subTest(expected=bad_expected):
                with self.assertRaises(S.SchemaViolation):
                    inv.validate()

    def test_all_five_invariants_lift(self):
        sv, invs = S.parse_invariants_yaml(
            (REPO / "security" / "invariants.yaml").read_text())
        self.assertEqual(sv, "boundary.v0")
        self.assertEqual(len(invs), 5)
        ids = [i for i, _ in invs]
        self.assertEqual(ids, ["INV-001", "INV-002", "INV-003", "INV-004", "INV-005"])
        for iid, expected in invs:
            lifted = S.Invariant.from_yaml_v0_dict(
                {"id": iid, "name": "n_" + iid.lower().replace("-", "_"),
                 "command": ["x"], "expected": expected, "asset": "a"})
            lifted.validate()
        inv004 = dict(invs)["INV-004"]
        self.assertIn("unmatched-reported-as-unknown", inv004)
        lifted004 = S.Invariant.from_yaml_v0_dict(
            {"id": "INV-004", "name": "wrapped", "command": ["bash", "-lc", "x"],
             "expected": inv004, "asset": "filesystem"})
        self.assertTrue(lifted004.layer_attribution)


class TestFindingSchema(unittest.TestCase):
    """S5/S6/S7 — finding.v1 validation."""

    def test_unmatched_cannot_serialize_as_allow(self):
        with self.assertRaises(S.SchemaViolation):
            make_finding(actual_decision="allow",
                         expected_decision="allow",
                         verdict="pass").to_dict()

    def test_unknown_requires_layer_attribution(self):
        with self.assertRaises(S.SchemaViolation):
            make_finding(layer_attribution=None).to_dict()
        d = make_finding().to_dict()  # must not raise
        self.assertIn("layer_attribution", d)

    def test_verdict_must_match_actual_vs_expected(self):
        with self.assertRaises(S.SchemaViolation):
            make_finding(actual_decision="unknown", expected_decision="allow",
                         verdict="pass").to_dict()
        make_finding(actual_decision="unknown", expected_decision="allow",
                     verdict="fail").to_dict()  # must not raise

    def test_decided_finding_validates(self):
        raw = json.dumps({
            "matchedRules": [{"prefixRuleMatch":
                              {"matchedPrefix": ["git", "status"],
                               "decision": "allow"}}],
            "decision": "allow"})
        d = make_finding(fixture_id="F-01", invariant_id="INV-002",
                         argv=["git", "status"],
                         raw_native_output=raw,
                         native_matched_rules_count=1,
                         actual_decision="allow", expected_decision="allow",
                         invariant_expected=["allow"], verdict="pass",
                         layer_attribution=None, corpus_shard="public").to_dict()
        self.assertEqual(d["actual_decision"], "allow")


class TestMerkle(unittest.TestCase):
    """S8 — Merkle seal and tamper detection."""

    def _leaves(self, n=41):
        findings = []
        for i in range(n):
            f = make_finding(fixture_id=f"F-{i:02d}")
            findings.append(f.to_dict())
        return findings

    def test_root_and_all_proofs_verify(self):
        findings = self._leaves()
        leaf_hashes = [S.leaf_hash_for_finding(f) for f in findings]
        root, proofs = S.build_merkle(leaf_hashes)
        self.assertRegex(root, r"^[0-9a-f]{64}$")
        for lh, proof in zip(leaf_hashes, proofs):
            self.assertTrue(S.verify_inclusion(lh, proof, root))

    def test_tamper_breaks_leaf_and_proof_only(self):
        findings = self._leaves()
        leaf_hashes = [S.leaf_hash_for_finding(f) for f in findings]
        root, proofs = S.build_merkle(leaf_hashes)
        tampered = copy.deepcopy(findings[7])
        tampered["actual_decision"] = "allow"  # what an attacker would want
        tampered_leaf = S.leaf_hash_for_finding(tampered)
        self.assertNotEqual(tampered_leaf, leaf_hashes[7])
        self.assertFalse(S.verify_inclusion(tampered_leaf, proofs[7], root))
        # Untouched findings still verify.
        for i, (lh, proof) in enumerate(zip(leaf_hashes, proofs)):
            if i != 7:
                self.assertTrue(S.verify_inclusion(lh, proof, root))

    def test_deterministic_root(self):
        findings = self._leaves()
        leaf_hashes = [S.leaf_hash_for_finding(f) for f in findings]
        self.assertEqual(S.build_merkle(leaf_hashes)[0],
                         S.build_merkle(leaf_hashes)[0])


class TestCorpusSplitAndPrereg(unittest.TestCase):
    """S9/S10 — corpus split and pre-registration integrity."""

    def test_split_disjoint_union_stratified(self):
        manifest = json.loads((REPO / "fixtures" / "corpus_manifest.json").read_text())
        pub = manifest["public"]["fixture_ids"]
        held = manifest["held_out"]["fixture_ids"]
        self.assertEqual(len(pub), 21)
        self.assertEqual(len(held), 20)
        self.assertEqual(len(set(pub) & set(held)), 0)
        fixtures = {f["id"]: f["expected"] for f in
                    json.loads((REPO / "fixtures" / "fixtures.json").read_text())["fixtures"]}
        self.assertEqual(set(pub) | set(held), set(fixtures))
        counts = {}
        for fid in pub:
            counts.setdefault(fixtures[fid], [0, 0])[0] += 1
        for fid in held:
            counts.setdefault(fixtures[fid], [0, 0])[1] += 1
        self.assertEqual(counts,
                         {"allow": [3, 3], "prompt": [2, 2],
                          "forbidden": [5, 4], "unknown": [11, 11]})

    def test_prereg_hash_locks_corpus(self):
        pr = json.loads(
            (REPO / "docs" / "preregistration" / "2026-10-22-preregistration.json").read_text())
        body = {k: v for k, v in pr.items() if k != "preregistration_sha256"}
        recomputed = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(recomputed, pr["preregistration_sha256"])
        self.assertEqual(pr["corpus"]["corpus_version_hash"],
                         sha256_file(REPO / "fixtures" / "fixtures.json"))
        self.assertEqual(len(pr["expectations"]["fixture_expectations"]), 41)
        self.assertEqual(sum(pr["expectations"]["expected_decision_counts"].values()), 41)


class TestNegativeControls(unittest.TestCase):
    """S11 — negative controls are deliberately wrong."""

    def test_controls_contradict_known_native_outcomes(self):
        doc = json.loads((REPO / "fixtures" / "negative_controls.json").read_text())
        self.assertEqual(len(doc["controls"]), 4)
        # Known Day-1 native outcomes (REPRO, frozen in evidence/): these
        # expectations are wrong on purpose — a healthy run FAILS them.
        known_actual = {
            "NC-01": "unknown",   # curl: no-match
            "NC-02": "unknown",   # bash -lc wrapper: no-match
            "NC-03": "allow",     # git status: allow
            "NC-04": "forbidden",  # rm -rf: forbidden
        }
        for c in doc["controls"]:
            self.assertNotEqual(c["expected"], known_actual[c["control_id"]],
                                f"{c['control_id']} expectation is not deliberately wrong")


if __name__ == "__main__":
    unittest.main(verbosity=2)
