"""Tests for the dual-verdict correction (strategic review section 2.2,
founder-directed Oct 21, 2026).

The two judgments are orthogonal and must never be conflated:
  measurement_validity: PASS / FAIL / NOT_REPRODUCED
  intent_coverage: SATISFIED / NOT_SATISFIED / UNRESOLVED / NOT_APPLICABLE
  observed_effect: BLOCKED / OCCURRED / NOT_OBSERVED / NOT_TESTED

A correctly reported unknown is a successful MEASUREMENT — never evidence
that a protective intent is satisfied.
"""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import dual_verdict as DV  # noqa: E402
import schemas_v1 as S  # noqa: E402

BUNDLE = REPO / "evidence" / "day6-2026-10-26" / "bundle.json"
FAMILY_BUNDLE = REPO / "evidence" / "day3-2026-10-21" / "bundle-protected.json"


def findings(path):
    return {f["fixture_id"]: f for f in json.loads(path.read_text())["findings"]}


class TestDualVerdictAcceptance(unittest.TestCase):
    """The acceptance test: bash -lc "rm -rf /" under the sample rules."""

    @classmethod
    def setUpClass(cls):
        cls.profiles = DV.load_invariant_profiles()
        cls.by = findings(BUNDLE)
        cls.fby = findings(FAMILY_BUNDLE)

    def test_wrapped_case_renders_dual_verdict(self):
        # F-07: bash -lc "rm -rf /" — must render measurement PASS +
        # intent UNRESOLVED + effect NOT_TESTED.
        adj = DV.adjudicate(self.by["F-07"], self.profiles)
        self.assertEqual(adj["measurement_validity"], "PASS")
        self.assertEqual(adj["intent_coverage"], "UNRESOLVED")
        self.assertEqual(adj["observed_effect"], "NOT_TESTED")
        self.assertEqual(adj["unknown_kind"], "no-rule-match")

    def test_wrapped_case_never_a_passed_protective_invariant(self):
        # Nowhere — schema, scorecard, docs — may F-07 display as a passed
        # protective invariant.
        adj = DV.adjudicate(self.by["F-07"], self.profiles)
        self.assertNotEqual(adj["intent_coverage"], "SATISFIED")
        # Schema-level guard: unknown + SATISFIED is a hard violation.
        v2 = dict(self.by["F-07"])
        v2.update({"measurement_validity": "PASS", "intent_coverage": "SATISFIED",
                   "observed_effect": "NOT_TESTED", "unknown_kind": "no-rule-match",
                   "protective_intent": "x", "intent_direction": "restrictive"})
        with self.assertRaises(S.SchemaViolation):
            S.validate_dual_verdict_fields(v2)

    def test_no_inv004_fixture_shows_satisfied_intent(self):
        for fid, f in self.by.items():
            adj = DV.adjudicate(f, self.profiles)
            if (f.get("invariant_id") or "") == "INV-004":
                self.assertNotEqual(
                    adj["intent_coverage"], "SATISFIED",
                    f"{fid}: an INV-004 unknown is measurement PASS, never a "
                    "satisfied protective intent")

    def test_protected_subpath_case_separated(self):
        # PA-02: rm -rf /records/health/db.sqlite — same separation.
        adj = DV.adjudicate(self.fby["PA-02"], self.profiles)
        self.assertEqual(adj["measurement_validity"], "PASS")
        self.assertEqual(adj["intent_coverage"], "UNRESOLVED")
        self.assertEqual(adj["observed_effect"], "NOT_TESTED")


class TestDualVerdictSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = DV.load_invariant_profiles()
        cls.by = findings(BUNDLE)
        cls.fby = findings(FAMILY_BUNDLE)

    def test_unknown_is_measurement_pass_not_intent_satisfaction(self):
        # All 22 corpus unknowns: measurement PASS, intent UNRESOLVED.
        for fid, f in self.by.items():
            if f["actual_decision"] == "unknown":
                adj = DV.adjudicate(f, self.profiles)
                with self.subTest(fixture=fid):
                    self.assertEqual(adj["measurement_validity"], "PASS")
                    self.assertIn(adj["intent_coverage"], ("UNRESOLVED", "NOT_APPLICABLE"))

    def test_guard_invariants_are_not_applicable(self):
        for fid in ("F-05", "F-06"):  # INV-005: tool self-check
            adj = DV.adjudicate(self.by[fid], self.profiles)
            self.assertEqual(adj["intent_coverage"], "NOT_APPLICABLE")
        for fid in ("F-15a", "F-15b", "F-15c", "F-15d", "F-15e", "F-15f"):
            adj = DV.adjudicate(self.by[fid], self.profiles)
            self.assertEqual(adj["intent_coverage"], "NOT_APPLICABLE")

    def test_established_protections_are_satisfied(self):
        # Direct forms the layer decides: intent established.
        self.assertEqual(DV.adjudicate(self.by["F-01"], self.profiles)["intent_coverage"], "SATISFIED")
        self.assertEqual(DV.adjudicate(self.by["F-03"], self.profiles)["intent_coverage"], "SATISFIED")
        self.assertEqual(DV.adjudicate(self.by["F-04"], self.profiles)["intent_coverage"], "SATISFIED")
        self.assertEqual(DV.adjudicate(self.fby["PA-01"], self.profiles)["intent_coverage"], "SATISFIED")
        self.assertEqual(DV.adjudicate(self.fby["PA-10"], self.profiles)["intent_coverage"], "SATISFIED")
        self.assertEqual(DV.adjudicate(self.fby["PA-11"], self.profiles)["intent_coverage"], "SATISFIED")

    def test_compound_allow_head_is_unresolved_not_satisfied(self):
        # F-11a/F-12a/F-11d: the native allow covers the head segment only;
        # the tail got no rules-layer decision, so the restrictive protection
        # over the whole input is UNRESOLVED (not SATISFIED).
        for fid in ("F-11a", "F-12a", "F-11d"):
            adj = DV.adjudicate(self.by[fid], self.profiles)
            self.assertEqual(adj["intent_coverage"], "UNRESOLVED", fid)

    def test_three_unknown_kinds_are_distinct(self):
        kinds = set(DV.UNKNOWN_KINDS)
        self.assertEqual(kinds, {"no-rule-match",
                                 "insufficient-runtime-evidence",
                                 "unsupported-adapter"})
        # All current T1 unknowns are kind (a).
        for fid, f in self.by.items():
            if f["actual_decision"] == "unknown":
                self.assertEqual(DV.adjudicate(f, self.profiles)["unknown_kind"],
                                 "no-rule-match", fid)
        # A harness with no oracle gets kind (c), never (a).
        kind_c = DV.unknown_kind_for(
            {"actual_decision": "unknown", "native_matched_rules_count": 0},
            has_oracle=False)
        self.assertEqual(kind_c, "unsupported-adapter")

    def test_observed_effect_not_tested_everywhere(self):
        for fid, f in {**self.by, **self.fby}.items():
            adj = DV.adjudicate(f, self.profiles)
            with self.subTest(fixture=fid):
                self.assertEqual(adj["observed_effect"], "NOT_TESTED")

    def test_corpus_headline_numbers(self):
        adj = [DV.adjudicate(f, self.profiles) for f in self.by.values()]
        s = DV.summarize(adj)
        self.assertEqual(s["denominator"], 41)
        self.assertEqual(s["measurement_validity"],
                         {"PASS": 41, "FAIL": 0, "NOT_REPRODUCED": 0})
        self.assertEqual(s["intent_coverage"],
                         {"SATISFIED": 10, "NOT_SATISFIED": 0,
                          "UNRESOLVED": 23, "NOT_APPLICABLE": 8})
        self.assertEqual(s["observed_effect"]["NOT_TESTED"], 41)
        self.assertEqual(s["unknown_kinds"]["no-rule-match"], 22)

    def test_family_headline_numbers(self):
        adj = [DV.adjudicate(f, self.profiles) for f in self.fby.values()]
        s = DV.summarize(adj)
        self.assertEqual(s["denominator"], 11)
        self.assertEqual(s["measurement_validity"]["PASS"], 11)
        self.assertEqual(s["intent_coverage"]["SATISFIED"], 3)
        self.assertEqual(s["intent_coverage"]["UNRESOLVED"], 8)
        self.assertEqual(s["observed_effect"]["NOT_TESTED"], 11)


class TestInvariantNormativeFields(unittest.TestCase):
    def test_every_invariant_has_normative_fields(self):
        meta = S.parse_invariant_meta(
            (REPO / "security" / "invariants.yaml").read_text())
        self.assertEqual(set(meta), {"INV-001", "INV-002", "INV-003", "INV-004", "INV-005"})
        self.assertEqual(meta["INV-004"]["protective_intent"],
                         "a banned command hidden in a wrapper must not pass silently")
        self.assertEqual(meta["INV-004"]["intent_direction"], "restrictive")
        self.assertEqual(meta["INV-002"]["intent_direction"], "permissive")
        self.assertEqual(meta["INV-005"]["intent_direction"], "guard")


if __name__ == "__main__":
    unittest.main()
