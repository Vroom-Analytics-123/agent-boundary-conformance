"""Tests for tools/fineprint_check.py (the Catalogue Commons check runner).

Covers: per-invariant dual-verdict adjudication, bundle seal/verify
round-trips (including tamper detection), the --baseline diff semantics,
and the deployment-gate exit-code contract. One CLI end-to-end test runs
three real probes against the pinned codex oracle (--only FP-016); the
rest is synthetic (no oracle calls).
"""

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import catalogue_loader as CL  # noqa: E402
import check_bundle as CB  # noqa: E402
import check_scorecard as CS  # noqa: E402
import fineprint_check as FC  # noqa: E402


def entry(direction="restrictive", eid="FP-T-001", status="MEASURED"):
    return {"id": eid, "name": "t", "intent_direction": direction,
            "source_layer": "core", "private": False,
            "expectation_basis": "measured", "measurement_status": status}


def finding(pid, iid, actual, expected, direction="restrictive"):
    return {"probe_id": pid, "invariant_id": iid, "probe_family": "direct",
            "argv": ["rm", "-rf", "/tmp/x"], "parameter_bindings": {},
            "expected_decision": expected, "actual_decision": actual,
            "verdict": ("pass" if actual == expected else "fail"),
            "layer": "rules-layer",
            "layer_attribution": ("no rules-layer decision; runtime outcome "
                                  "depends on approval policy + sandbox "
                                  "under the pinned configuration")
            if actual == "unknown" else "",
            "evidence_class": "REPRO", "matched_rules": 0,
            "engine_note": "", "raw_native_output": "",
            "source_layer": "core", "private": False,
            "expectation_basis": "measured"}


class TestAdjudication(unittest.TestCase):
    def test_restrictive_all_forbidden_satisfied(self):
        e = entry()
        fs = [finding("p0", e["id"], "forbidden", "forbidden"),
              finding("p1", e["id"], "prompt", "prompt")]
        r = CS.adjudicate(e, fs)
        self.assertEqual(r["measurement_validity"], "PASS")
        self.assertEqual(r["intent_coverage"], "SATISFIED")

    def test_unknown_is_never_a_passed_invariant(self):
        # Correctly reported unknown: measurement PASS, intent UNRESOLVED.
        e = entry()
        fs = [finding("p0", e["id"], "unknown", "unknown")]
        r = CS.adjudicate(e, fs)
        self.assertEqual(r["measurement_validity"], "PASS")
        self.assertEqual(r["intent_coverage"], "UNRESOLVED")

    def test_allow_on_restrictive_not_satisfied(self):
        e = entry()
        fs = [finding("p0", e["id"], "allow", "forbidden")]
        r = CS.adjudicate(e, fs)
        self.assertEqual(r["measurement_validity"], "FAIL")
        self.assertEqual(r["intent_coverage"], "NOT_SATISFIED")

    def test_guard_is_not_applicable(self):
        e = entry(direction="guard", eid="FP-T-G")
        fs = [finding("p0", e["id"], "forbidden", "forbidden")]
        r = CS.adjudicate(e, fs)
        self.assertEqual(r["intent_coverage"], "NOT_APPLICABLE")

    def test_permissive(self):
        e = entry(direction="permissive", eid="FP-T-P")
        r = CS.adjudicate(e, [finding("p0", e["id"], "allow", "allow")])
        self.assertEqual(r["intent_coverage"], "SATISFIED")
        r2 = CS.adjudicate(e, [finding("p0", e["id"], "prompt", "allow")])
        self.assertEqual(r2["intent_coverage"], "NOT_SATISFIED")

    def test_probe_error_is_not_reproduced(self):
        e = entry()
        f = finding("p0", e["id"], "error", "forbidden")
        f["verdict"] = "not_run"
        r = CS.adjudicate(e, [f])
        self.assertEqual(r["measurement_validity"], "NOT_REPRODUCED")
        self.assertEqual(r["intent_coverage"], "UNRESOLVED")

    def test_more_protective_than_expected_still_satisfies_intent(self):
        # Oracle forbids where the pack expected unknown: measurement FAIL
        # (expectation mismatch) but the protective intent IS established.
        e = entry()
        fs = [finding("p0", e["id"], "forbidden", "unknown")]
        r = CS.adjudicate(e, fs)
        self.assertEqual(r["measurement_validity"], "FAIL")
        self.assertEqual(r["intent_coverage"], "SATISFIED")


def synthetic_bundle(label, rows):
    """rows: [(invariant_id, direction, [(probe_id, actual, expected), ...])]"""
    findings, results = [], []
    for iid, direction, probes in rows:
        e = entry(direction, iid)
        fs = [finding(pid, iid, actual, expected, direction)
              for pid, actual, expected in probes]
        findings.extend(fs)
        results.append(CS.adjudicate(e, fs))
    run_spec = {"harness": "synthetic", "measurement_route": "synthetic-test",
                "adapter_version_detail": "test", "evidence_class": "TEST",
                "policy": {"path": "p", "sha256": "0" * 64, "kind": "test"},
                "pack": {"core": {"path": "c", "sha256": "0" * 64,
                                  "catalogue_version": "t", "entries": 1},
                         "domain_packs": [],
                         "org_overlay": {"present": False, "entries": 0},
                         "composition_sha256": "0" * 64, "total_entries": 1},
                "parameter_bindings_sha256": "0" * 64, "probe_count": 1}
    return CB.seal_check_bundle(
        label=label, run_spec=run_spec, findings=findings,
        invariant_results=results,
        claim_scope={"note": "t", "measured_invariants": 1,
                     "measured_satisfied": 0, "measured_unresolved": 0,
                     "measured_not_satisfied": 0, "exploratory_invariants": 0},
        privacy={"public_mode": False, "org_entries_included": False,
                 "org_entries": 0})


class TestSealVerify(unittest.TestCase):
    def test_roundtrip_verifies(self):
        b = synthetic_bundle("t", [("FP-T-001", "restrictive",
                                    [("FP-T-001/direct/p0", "forbidden",
                                      "forbidden")])])
        self.assertEqual(b["status"], "valid")
        self.assertEqual(CB.verify_check_bundle(b), [])

    def test_tamper_detected(self):
        b = synthetic_bundle("t", [("FP-T-001", "restrictive",
                                    [("FP-T-001/direct/p0", "forbidden",
                                      "forbidden")])])
        b["findings"][0]["actual_decision"] = "allow"
        problems = CB.verify_check_bundle(b)
        self.assertTrue(problems, "tampered bundle must not verify")

    def test_inv005_violation_marks_broken(self):
        b = synthetic_bundle("t", [("FP-T-001", "restrictive",
                                    [("FP-T-001/direct/p0", "unknown",
                                      "unknown")])])
        f = b["findings"][0]
        f["actual_decision"] = "allow"
        f["verdict"] = "fail"
        f["raw_native_output"] = '{"matchedRules": []}'
        f["layer_attribution"] = ""
        resealed = CB.seal_check_bundle(
            label="t2", run_spec=b["run"], findings=b["findings"],
            invariant_results=b["invariant_results"],
            claim_scope=b["claim_scope"], privacy=b["privacy"])
        self.assertEqual(resealed["status"], "broken")
        self.assertTrue(any("INV-005" in p
                            for p in resealed.get("problems", [])))


class TestBaselineDiff(unittest.TestCase):
    def base(self):
        return synthetic_bundle("base", [
            ("FP-T-001", "restrictive",
             [("FP-T-001/direct/p0", "forbidden", "forbidden")]),
            ("FP-T-002", "restrictive",
             [("FP-T-002/direct/p0", "unknown", "unknown")]),
        ])

    def test_no_change_no_regression(self):
        diff = FC.diff_bundles(self.base(), self.base())
        self.assertEqual(diff["regression_count"], 0)
        self.assertEqual(FC.gate_exit_code(diff), 0)

    def test_coverage_regression_detected(self):
        base = self.base()
        fresh = synthetic_bundle("fresh", [
            ("FP-T-001", "restrictive",
             [("FP-T-001/direct/p0", "allow", "forbidden")]),
            ("FP-T-002", "restrictive",
             [("FP-T-002/direct/p0", "unknown", "unknown")]),
        ])
        diff = FC.diff_bundles(base, fresh)
        kinds = [r["kind"] for r in diff["regressions"]]
        self.assertIn("coverage-regression", kinds)
        self.assertEqual(FC.gate_exit_code(diff), 2)

    def test_decision_flip_without_rank_move_is_regression(self):
        # FP-T-002 was UNRESOLVED (unknown probe); fresh run keeps it
        # UNRESOLVED but one probe flipped forbidden -> allow.
        base = synthetic_bundle("base", [
            ("FP-T-002", "restrictive",
             [("FP-T-002/direct/p0", "forbidden", "forbidden"),
              ("FP-T-002/direct/p1", "unknown", "unknown")]),
        ])
        fresh = synthetic_bundle("fresh", [
            ("FP-T-002", "restrictive",
             [("FP-T-002/direct/p0", "allow", "forbidden"),
              ("FP-T-002/direct/p1", "unknown", "unknown")]),
        ])
        diff = FC.diff_bundles(base, fresh)
        kinds = [r["kind"] for r in diff["regressions"]]
        self.assertIn("decision-flip-regression", kinds)
        self.assertEqual(FC.gate_exit_code(diff), 2)

    def test_improvement_is_not_a_regression(self):
        base = self.base()
        fresh = synthetic_bundle("fresh", [
            ("FP-T-001", "restrictive",
             [("FP-T-001/direct/p0", "forbidden", "forbidden")]),
            ("FP-T-002", "restrictive",
             [("FP-T-002/direct/p0", "forbidden", "unknown")]),
        ])
        diff = FC.diff_bundles(base, fresh)
        self.assertEqual(diff["regression_count"], 0)
        self.assertEqual(len(diff["improvements"]), 1)
        self.assertEqual(FC.gate_exit_code(diff), 0)

    def test_dropped_invariant_is_a_regression(self):
        base = self.base()
        fresh = synthetic_bundle("fresh", [
            ("FP-T-001", "restrictive",
             [("FP-T-001/direct/p0", "forbidden", "forbidden")]),
        ])
        diff = FC.diff_bundles(base, fresh)
        kinds = [r["kind"] for r in diff["regressions"]]
        self.assertIn("dropped-invariant", kinds)
        self.assertEqual(FC.gate_exit_code(diff), 2)


class TestCliEndToEnd(unittest.TestCase):
    def test_codex_three_probes(self):
        """Real oracle, three probes (--only FP-016, permissive)."""
        with tempfile.TemporaryDirectory(prefix="fp-e2e-") as tmp:
            out = Path(tmp) / "out"
            cmd = [sys.executable,
                   str(REPO / "tools" / "fineprint_check.py"),
                   "--harness", "codex",
                   "--policy", str(REPO / "fixtures" / "policies"
                                   / "default.rules"),
                   "--bindings", str(REPO / "evidence" / "demo-check-2026-10-22"
                                      / "bindings.json"),
                   "--only", "FP-016", "--out", str(out),
                   "--label", "e2e-test"]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=300)
            self.assertEqual(proc.returncode, 0,
                             f"run failed:\n{proc.stdout}\n{proc.stderr}")
            for artifact in ("bundle.json", "scorecard.json",
                             "scorecard.html", "bindings.json",
                             "composition.json"):
                self.assertTrue((out / artifact).exists(), artifact)
            bundle = json.loads((out / "bundle.json").read_text())
            self.assertEqual(bundle["schema_version"],
                             "check-run-bundle.v1")
            self.assertEqual(CB.verify_check_bundle(bundle), [])
            self.assertEqual(bundle["run"]["harness"], "codex")
            self.assertEqual(len(bundle["findings"]), 3)
            # Scorecard is deterministic from the bundle: rebuild it.
            CS.build_scorecard(bundle, out / "rebuild", "repro")
            a = json.loads((out / "scorecard.json").read_text())
            b = json.loads((out / "rebuild" / "scorecard.json").read_text())
            for doc in (a, b):
                doc.pop("generated_utc")
                doc["reproducibility"] = "normalized"
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
