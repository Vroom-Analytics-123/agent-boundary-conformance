"""Tests for tools/build_scorecard.py (Boundary Scorecard, Day 6).

The scorecard builder is a deterministic function of committed inputs (no
oracle calls): the sealed Day-6 evidence bundle, the sealed protected-records
bundle, and the five adapter manifests. These tests pin its structural
invariants and its determinism so CI can re-issue the "third party can rerun
the report from the repo alone" check offline.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "evidence" / "day6-2026-10-26" / "bundle.json"
FAMILY_BUNDLE = REPO / "evidence" / "day3-2026-10-21" / "bundle-protected.json"


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
        cls.tier_matrix = json.loads((cls.tmp / "tier-matrix.json").read_text())

    def test_schema_versions(self):
        self.assertEqual(self.scorecard["schema_version"], "scorecard.v1")
        self.assertEqual(self.tier_matrix["schema_version"], "tier-matrix.v1")

    def test_pre_fix_labelled(self):
        # The Day-5 fix is NOT applied; the scorecard must say so on its face.
        fs = self.scorecard["fix_status"]
        self.assertFalse(fs["applied"])
        self.assertEqual(fs["label"], "PRE-FIX EVIDENCE")

    def test_corpus_headline_numbers(self):
        c = self.scorecard["codex_t1"]["corpus"]
        self.assertEqual(c["fixtures"], 41)
        self.assertEqual(c["pass"], 41)
        self.assertEqual(c["fail"], 0)
        self.assertEqual(c["unknowns"]["count"], 22)
        self.assertEqual(c["decision_counts"],
                         {"allow": 6, "forbidden": 9, "prompt": 4, "unknown": 22})

    def test_family_numbers(self):
        f = self.scorecard["protected_records_family"]
        self.assertEqual(f["fixtures"], 11)
        self.assertEqual(f["pass"], 11)
        self.assertEqual(f["fail"], 0)

    def test_tier_matrix_five_harnesses(self):
        rows = self.scorecard["five_harness_tier_matrix"]
        self.assertEqual(len(rows), 5)
        by_harness = {r["harness"]: r for r in rows}
        self.assertEqual(by_harness["codex"]["tier"], "T1")
        self.assertEqual(by_harness["codex"]["evidence_class"], "REPRO")
        for h in ("claude-code", "cursor", "gemini-cli", "opencode"):
            self.assertEqual(by_harness[h]["tier"], "T2")
            # No T2 harness may claim measured verdicts.
            self.assertIn("no decision oracle exists",
                          by_harness[h]["measured_verdicts"].lower())
        # tier-matrix.json agrees with the scorecard's matrix.
        self.assertEqual([r["harness"] for r in self.tier_matrix["harnesses"]],
                         [r["harness"] for r in rows])

    def test_negative_controls(self):
        nc = self.scorecard["negative_controls"]
        self.assertEqual(nc["count"], 4)
        self.assertTrue(nc["all_healthy"])

    def test_semantics_present(self):
        sem = self.scorecard["semantics"]
        self.assertIn("bypass", sem["unknown"])
        self.assertIn("layer_attribution", sem)

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
