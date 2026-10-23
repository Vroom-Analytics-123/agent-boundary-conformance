"""Tests for tools/build_scorecard.py (Boundary Scorecard v3, POST-FIX).

The scorecard builder is a deterministic function of committed inputs (no
oracle calls): the sealed post-fix evidence bundle, the sealed post-fix
protected-records bundle, and the five adapter manifests. These tests pin its
structural invariants and its determinism so CI can re-issue the "third party
can rerun the report from the repo alone" check offline.

v3 (2026-10-22): the Day-5 fix is applied; the builder labels its output
POST-FIX EVIDENCE. The sealed pre-fix v2 scorecard remains committed at
evidence/reports/day6-scorecard/ and is not regenerated here.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "evidence" / "postfix-2026-10-22" / "bundle.json"
FAMILY_BUNDLE = REPO / "evidence" / "postfix-2026-10-22" / "bundle-protected.json"


def build(out_dir):
    cmd = [sys.executable, str(REPO / "tools" / "build_scorecard.py"),
           "--bundle", str(BUNDLE),
           "--family-bundle", str(FAMILY_BUNDLE),
           "--out", str(out_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"build_scorecard failed:\n{proc.stderr}"
    return out_dir


class TestScorecardV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="scorecard-test-"))
        build(cls.tmp)
        cls.scorecard = json.loads((cls.tmp / "scorecard.json").read_text())
        cls.route_matrix = json.loads((cls.tmp / "measurement-routes.json").read_text())

    def test_schema_versions(self):
        self.assertEqual(self.scorecard["schema_version"], "scorecard.v3")
        self.assertEqual(self.route_matrix["schema_version"], "measurement-routes.v1")

    def test_post_fix_labelled(self):
        # The Day-5 fix IS applied (Anish, "Start the evidence upgrades",
        # Oct 22, 2026); the scorecard must say so on its face.
        fs = self.scorecard["fix_status"]
        self.assertTrue(fs["applied"])
        self.assertEqual(fs["label"], "POST-FIX EVIDENCE")

    def test_corpus_headline_numbers(self):
        c = self.scorecard["codex_vendor_confirmed"]["corpus"]
        self.assertEqual(c["fixtures"], 41)
        self.assertEqual(c["pass"], 40)
        self.assertEqual(c["fail"], 1)
        self.assertEqual(c["unknowns"]["count"], 20)
        self.assertEqual(c["decision_counts"],
                         {"allow": 6, "forbidden": 11, "prompt": 4, "unknown": 20})

    def test_family_numbers(self):
        f = self.scorecard["protected_records_family"]
        self.assertEqual(f["fixtures"], 11)
        self.assertEqual(f["pass"], 11)
        self.assertEqual(f["fail"], 0)

    def test_measurement_routes_five_harnesses(self):
        rows = self.scorecard["five_harness_measurement_routes"]
        self.assertEqual(len(rows), 5)
        by_harness = {r["harness"]: r for r in rows}
        self.assertEqual(by_harness["codex"]["measurement_route"], "vendor-confirmed")
        self.assertEqual(by_harness["codex"]["evidence_class"], "REPRO")
        for h in ("claude-code", "cursor", "gemini-cli", "opencode"):
            self.assertEqual(by_harness[h]["measurement_route"], "reconstructed")
            # No reconstructed-route harness may claim measured verdicts.
            self.assertIn("no verdicts measured",
                          by_harness[h]["measured_verdicts"].lower())
        # measurement-routes.json agrees with the scorecard's matrix.
        self.assertEqual([r["harness"] for r in self.route_matrix["harnesses"]],
                         [r["harness"] for r in rows])

    def test_negative_controls(self):
        nc = self.scorecard["negative_controls"]
        self.assertEqual(nc["count"], 4)
        self.assertTrue(nc["all_healthy"])

    def test_semantics_present(self):
        sem = self.scorecard["semantics"]
        self.assertIn("bypass", sem["unknown"])
        self.assertIn("layer_attribution", sem)
        self.assertIn("dual_verdict", sem)
        self.assertIn("preregistration_correction", sem)
        self.assertIn("Day 1 was EXPLORATORY", sem["preregistration_correction"])

    def test_dual_verdict_separate_denominators(self):
        c = self.scorecard["codex_vendor_confirmed"]["corpus"]
        mv = c["measurement_validity"]
        icv = c["intent_coverage"]
        self.assertEqual(mv["denominator"], 41)
        # 40 PASS + 1 FAIL: S-02's measurement FAIL is the documented
        # bookkeeping artifact of its frozen held-out expectation (its native
        # decision, forbidden, was reproduced exactly and is verifier-confirmed).
        self.assertEqual(mv["counts"]["PASS"], 40)
        self.assertEqual(mv["counts"]["FAIL"], 1)
        self.assertEqual(icv["denominator"], 41)
        self.assertEqual(icv["counts"]["SATISFIED"], 12)
        self.assertEqual(icv["counts"]["UNRESOLVED"], 21)
        self.assertEqual(icv["counts"]["NOT_APPLICABLE"], 8)
        self.assertEqual(c["observed_effect"]["counts"]["NOT_TESTED"], 41)
        self.assertEqual(c["unknowns"]["kinds"]["no-rule-match"], 20)
        # Rows carry the finding.v2 extension fields.
        for r in self.scorecard["codex_vendor_confirmed"]["stated_vs_actual"]:
            self.assertIn(r["measurement_validity"], ("PASS", "FAIL", "NOT_REPRODUCED"))
            self.assertIn(r["intent_coverage"],
                          ("SATISFIED", "NOT_SATISFIED", "UNRESOLVED", "NOT_APPLICABLE"))
            self.assertEqual(r["observed_effect"], "NOT_TESTED")
            if r["invariant"] == "INV-004":
                self.assertNotEqual(r["intent_coverage"], "SATISFIED")
        # The S-02 artifact row: FAIL is expectation bookkeeping, SATISFIED is
        # the measured intent outcome — the fix's held-out confirmation.
        s02 = next(r for r in self.scorecard["codex_vendor_confirmed"]["stated_vs_actual"]
                   if r["fixture_id"] == "S-02")
        self.assertEqual(s02["measurement_validity"], "FAIL")
        self.assertEqual(s02["intent_coverage"], "SATISFIED")
        self.assertEqual(s02["actual_decision"], "forbidden")

    def test_acceptance_case_f07(self):
        acc = self.scorecard["codex_vendor_confirmed"]["acceptance_case_f07"]
        self.assertEqual(acc["fixture_id"], "F-07")
        self.assertEqual(acc["measurement_validity"], "PASS")
        self.assertEqual(acc["intent_coverage"], "UNRESOLVED")
        self.assertEqual(acc["observed_effect"], "NOT_TESTED")
        self.assertIn("NEVER displayed as a passed protective invariant",
                      acc["not_a_passed_protective_invariant"])

    def test_family_dual_verdict(self):
        f = self.scorecard["protected_records_family"]
        self.assertEqual(f["measurement_validity"]["counts"]["PASS"], 11)
        self.assertEqual(f["intent_coverage"]["counts"]["SATISFIED"], 3)
        self.assertEqual(f["intent_coverage"]["counts"]["UNRESOLVED"], 8)

    def test_reconstructed_unknown_kind_labelled(self):
        for t in self.scorecard["five_harness_measurement_routes"]:
            if t["measurement_route"] == "reconstructed":
                self.assertEqual(t["unknown_kind"], "unsupported-adapter")
            else:
                self.assertIsNone(t["unknown_kind"])

    def test_no_conflated_headline(self):
        html_text = (self.tmp / "scorecard.html").read_text()
        # The old conflated headline must be gone: 41/41 is a measurement
        # result, never "stated intentions match" phrased as protection.
        self.assertNotIn("stated intentions match", html_text)
        self.assertIn("separate denominators", html_text)
        self.assertIn("Acceptance case F-07", html_text)

    def test_deterministic_regeneration(self):
        other = Path(tempfile.mkdtemp(prefix="scorecard-test-2-"))
        build(other)
        a = json.loads((self.tmp / "scorecard.json").read_text())
        b = json.loads((other / "scorecard.json").read_text())
        # The only allowed differences between two regenerations: the
        # generation timestamp, and the --out path embedded verbatim in
        # reproduce_command (the command is faithful to its invocation).
        for doc in (a, b):
            doc.pop("generated_utc", None)
            doc["reproduce_command"] = doc["reproduce_command"].rsplit(
                " --out ", 1)[0]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
