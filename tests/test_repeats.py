"""Tests for --repeats in tools/fineprint_check.py and the additive
check-run-bundle.v1 fields (non_attempt_attribution, repeats,
repeat_summary, run.repeats).

TDD: these tests were written before the implementation. They use a
scripted stub adapter — no oracle calls — plus one sealed old bundle
from evidence/ for the backward-compatibility check.
"""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import check_bundle as CB  # noqa: E402
import check_scorecard as CS  # noqa: E402
import fineprint_check as FC  # noqa: E402

OLD_BUNDLE = REPO / "evidence" / "demo-check-2026-10-22" / "codex-core" / "bundle.json"
SCHEMA_PATH = REPO / "schemas" / "check_run_bundle.v1.schema.json"


def stub_entry(eid="FP-T-R"):
    return {"id": eid, "name": "t", "source_layer": "core",
            "private": False, "expectation_basis": "measured",
            "probe_families": [{"family": "direct",
                                "probes": [["rm", "-rf", "/tmp/x"]],
                                "expected": ["forbidden"]}]}


def probe_result(actual="forbidden", matched_rules=None, note="",
                 observed_effect=None, raw=""):
    r = {"actual": actual,
         "matched_rules": {} if matched_rules is None else matched_rules,
         "raw": raw, "note": note, "layer": "rules-layer", "error": None}
    if observed_effect is not None:
        r["observed_effect"] = observed_effect
    return r


class ScriptedAdapter:
    """Adapter stub: run_probe consumes scripted results in call order."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run_probe(self, argv, policy):
        self.calls.append(list(argv))
        return self.results.pop(0)

    def as_dict(self):
        return {"run_probe": self.run_probe, "evidence_class": "TEST"}


def run_stub(results, repeats=3):
    entries = [stub_entry()]
    bindings, _ = FC.load_bindings(None, entries)
    stub = ScriptedAdapter(results)
    findings = FC.run_pack(entries, bindings, stub.as_dict(), "policy",
                           repeats=repeats)
    return findings, stub


class TestRepeatsInRunner(unittest.TestCase):
    def test_three_deterministic_repeats(self):
        findings, stub = run_stub(
            [probe_result("forbidden")] * 3, repeats=3)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(len(stub.calls), 3)
        self.assertEqual(len(f["repeats"]), 3)
        self.assertEqual([r["repeat_index"] for r in f["repeats"]],
                         [1, 2, 3])
        self.assertEqual(f["repeat_summary"],
                         {"n": 3, "outcomes": {"forbidden": 3},
                          "agreement": "unanimous",
                          "modal_decision": "forbidden"})
        # Top-level fields are repeat 1 (the primary repeat).
        self.assertEqual(f["actual_decision"], "forbidden")
        self.assertEqual(f["verdict"], "pass")

    def test_split_repeats_record_variance(self):
        findings, _ = run_stub(
            [probe_result("forbidden"), probe_result("allow"),
             probe_result("forbidden")], repeats=3)
        f = findings[0]
        self.assertEqual(f["repeat_summary"]["agreement"], "split")
        self.assertEqual(f["repeat_summary"]["outcomes"],
                         {"forbidden": 2, "allow": 1})
        self.assertEqual(f["repeat_summary"]["modal_decision"], "forbidden")
        # Top level is repeat 1, not the modal outcome.
        self.assertEqual(f["actual_decision"], "forbidden")
        self.assertEqual(f["verdict"], "pass")
        self.assertEqual(f["repeats"][1]["actual_decision"], "allow")
        self.assertEqual(f["repeats"][1]["verdict"], "fail")

    def test_repeats_one_behaves_like_the_old_single_run(self):
        findings, _ = run_stub([probe_result("forbidden")], repeats=1)
        f = findings[0]
        self.assertEqual(len(f["repeats"]), 1)
        self.assertEqual(f["repeat_summary"]["agreement"], "unanimous")
        self.assertEqual(f["actual_decision"], "forbidden")
        self.assertEqual(f["verdict"], "pass")

    def test_repeats_flag_validation(self):
        with self.assertRaises(SystemExit):
            FC.parse_args(["--repeats", "0"])
        with self.assertRaises(SystemExit):
            FC.parse_args(["--repeats", "-2"])
        with self.assertRaises(SystemExit):
            FC.parse_args(["--repeats", "abc"])

    def test_parse_args_default_is_three(self):
        self.assertEqual(FC.parse_args([])["repeats"], 3)

    def test_run_pack_rejects_zero_repeats(self):
        entries = [stub_entry()]
        bindings, _ = FC.load_bindings(None, entries)
        stub = ScriptedAdapter([])
        with self.assertRaises(ValueError):
            FC.run_pack(entries, bindings, stub.as_dict(), "policy",
                        repeats=0)


class TestAttributionInRunner(unittest.TestCase):
    def test_deny_with_observed_effect_is_attributed(self):
        findings, _ = run_stub(
            [probe_result("forbidden",
                          matched_rules={"rm -rf /tmp/x": {
                              "Bash(rm -rf /tmp/x)": ["rm -rf /tmp/x"]}},
                          observed_effect="NOT_OBSERVED")] * 3, repeats=3)
        f = findings[0]
        self.assertEqual(f["non_attempt_attribution"], "denied_by_rule")
        self.assertEqual(f["attribution_rule_id"], "Bash(rm -rf /tmp/x)")
        self.assertEqual(f["repeats"][0]["non_attempt_attribution"],
                         "denied_by_rule")

    def test_no_observed_effect_means_no_attribution(self):
        # Check-run adapters never observe an effect: the runner must not
        # invent an attribution.
        findings, _ = run_stub([probe_result("forbidden")] * 3, repeats=3)
        f = findings[0]
        self.assertNotIn("non_attempt_attribution", f)
        self.assertNotIn("attribution_rule_id", f)
        self.assertNotIn("non_attempt_attribution", f["repeats"][0])

    def test_not_attempted_wired_through(self):
        findings, _ = run_stub(
            [probe_result("allow", observed_effect="NOT_OBSERVED")] * 3,
            repeats=3)
        f = findings[0]
        self.assertEqual(f["non_attempt_attribution"], "not_attempted")
        self.assertIsNone(f["attribution_rule_id"])

    def test_no_decision_wired_through(self):
        findings, _ = run_stub(
            [probe_result("unknown", observed_effect="NOT_OBSERVED")] * 3,
            repeats=3)
        self.assertEqual(findings[0]["non_attempt_attribution"],
                         "no_decision")


class TestBundleShapeAndBackCompat(unittest.TestCase):
    def _seal(self, findings):
        entries = [stub_entry()]
        results = [CS.adjudicate(
            {"id": "FP-T-R", "name": "t", "intent_direction": "restrictive",
             "source_layer": "core", "private": False,
             "expectation_basis": "measured",
             "measurement_status": "MEASURED"},
            findings)]
        run_spec = {
            "harness": "synthetic", "measurement_route": "synthetic-test",
            "adapter_version_detail": "test", "evidence_class": "TEST",
            "policy": {"path": "p", "sha256": "0" * 64, "kind": "test"},
            "pack": {"core": {"path": "c", "sha256": "0" * 64,
                              "catalogue_version": "t", "entries": 1},
                     "domain_packs": [],
                     "org_overlay": {"present": False, "entries": 0},
                     "composition_sha256": "0" * 64, "total_entries": 1},
            "parameter_bindings_sha256": "0" * 64, "probe_count": 1,
            "repeats": 3}
        return CB.seal_check_bundle(
            label="t", run_spec=run_spec, findings=findings,
            invariant_results=results,
            claim_scope={"note": "t", "measured_invariants": 1,
                         "measured_satisfied": 0, "measured_unresolved": 0,
                         "measured_not_satisfied": 0,
                         "exploratory_invariants": 0},
            privacy={"public_mode": False, "org_entries_included": False,
                     "org_entries": 0})

    def test_old_bundle_without_new_fields_still_verifies(self):
        old = json.loads(OLD_BUNDLE.read_text())
        self.assertNotIn("non_attempt_attribution", old["findings"][0])
        self.assertNotIn("repeats", old["findings"][0])
        self.assertNotIn("repeats", old["run"])
        self.assertEqual(CB.verify_check_bundle(old), [])

    def test_new_fields_are_optional_in_the_json_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text())
        props = schema["properties"]["findings"]["items"]["properties"]
        for field in ("non_attempt_attribution", "attribution_rule_id",
                      "repeats", "repeat_summary"):
            self.assertIn(field, props, field)
        required = schema["properties"]["findings"]["items"]["required"]
        for field in ("non_attempt_attribution", "attribution_rule_id",
                      "repeats", "repeat_summary"):
            self.assertNotIn(field, required, field)
        run_props = schema["properties"]["run"]["properties"]
        self.assertIn("repeats", run_props)
        self.assertNotIn("repeats",
                         schema["properties"]["run"]["required"])

    def test_new_bundle_with_repeats_and_attribution_verifies(self):
        findings, _ = run_stub(
            [probe_result("forbidden",
                          matched_rules={"rm -rf /tmp/x": {
                              "Bash(rm -rf /tmp/x)": ["rm -rf /tmp/x"]}},
                          observed_effect="NOT_OBSERVED")] * 3, repeats=3)
        bundle = self._seal(findings)
        self.assertEqual(bundle["status"], "valid")
        self.assertEqual(CB.verify_check_bundle(bundle), [])

    def test_bogus_attribution_value_is_rejected(self):
        findings, _ = run_stub([probe_result("forbidden")] * 3, repeats=3)
        findings[0]["non_attempt_attribution"] = "maybe"
        bundle = self._seal(findings)
        self.assertEqual(bundle["status"], "broken")
        self.assertTrue(any("non_attempt_attribution" in p
                            for p in bundle.get("problems", [])))
        self.assertTrue(CB.verify_check_bundle(bundle))

    def test_repeat_summary_arithmetic_is_checked(self):
        findings, _ = run_stub([probe_result("forbidden")] * 3, repeats=3)
        findings[0]["repeat_summary"]["outcomes"] = {"forbidden": 2}
        bundle = self._seal(findings)
        self.assertEqual(bundle["status"], "broken")
        self.assertTrue(CB.verify_check_bundle(bundle))


if __name__ == "__main__":
    unittest.main()
