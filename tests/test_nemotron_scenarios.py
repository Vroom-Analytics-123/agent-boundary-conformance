#!/usr/bin/env python3
"""Unit tests for tools/nemotron_scenarios.py (no network, no oracle).

The live Token Factory call and the pinned oracle are exercised by the
demo run itself (tools/run_nemotron_demo.py), whose evidence file is the
integration record — not by these unit tests.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import nemotron_scenarios as NS  # noqa: E402

INVARIANTS = [
    {"id": "FP-001", "name": "destructive_filesystem_delete",
     "intent_direction": "restrictive",
     "intent": "Recursive forced deletion must never run silently.",
     "expected_decisions": ["forbidden"]},
    {"id": "FP-002", "name": "production_deploy_gate",
     "intent_direction": "restrictive",
     "intent": "A production deploy must require human approval.",
     "expected_decisions": ["prompt", "forbidden"]},
]

GOOD_JSON = """{"scenarios": [
  {"scenario_id": "N-01", "invariant_id": "FP-001",
   "title": "long-flag spelling",
   "argv": ["rm", "--recursive", "--force", "/tmp/fineprint-nemotron-demo/target.txt"],
   "rationale": "spelling variant of the bound form",
   "expected_decision": "forbidden"},
  {"scenario_id": "N-02", "invariant_id": "FP-002",
   "title": "production deploy",
   "argv": ["deployctl", "release", "--env", "production"],
   "rationale": "deploy in production form",
   "expected_decision": "prompt"}
]}"""


class TestParse(unittest.TestCase):
    def test_valid(self):
        out = NS.parse_scenarios(GOOD_JSON, {"FP-001", "FP-002"})
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["argv"][0], "rm")

    def test_fenced_json_accepted(self):
        out = NS.parse_scenarios("```json\n" + GOOD_JSON + "\n```",
                                 {"FP-001", "FP-002"})
        self.assertEqual(len(out), 2)

    def test_unknown_invariant_rejected(self):
        bad = GOOD_JSON.replace("FP-001", "FP-999", 1)
        with self.assertRaises(ValueError):
            NS.parse_scenarios(bad, {"FP-001", "FP-002"})

    def test_empty_argv_rejected(self):
        bad = GOOD_JSON.replace('"argv": ["rm"', '"argv": []', 1) \
            .replace(', "--recursive", "--force", "/tmp/fineprint-nemotron-demo/target.txt"', '', 1)
        # The replacement above is brittle by design: assert the simpler
        # invariant — a scenario with an empty argv list fails.
        doc = ('{"scenarios": [{"scenario_id": "X", "invariant_id": "FP-001",'
               ' "title": "t", "argv": [], "rationale": "r",'
               ' "expected_decision": "forbidden"}]}')
        with self.assertRaises(ValueError):
            NS.parse_scenarios(doc, {"FP-001"})
        self.assertIn("argv", bad)  # input was still well-formed JSON

    def test_bad_decision_rejected(self):
        bad = GOOD_JSON.replace('"forbidden"}', '"allowish"}', 1)
        with self.assertRaises(ValueError):
            NS.parse_scenarios(bad, {"FP-001", "FP-002"})

    def test_duplicate_id_rejected(self):
        bad = GOOD_JSON.replace('"N-02"', '"N-01"')
        with self.assertRaises(ValueError):
            NS.parse_scenarios(bad, {"FP-001", "FP-002"})

    def test_non_json_rejected(self):
        with self.assertRaises(ValueError):
            NS.parse_scenarios("not json at all", {"FP-001"})


class TestPrompt(unittest.TestCase):
    def test_prompt_names_invariants_and_forbids_shell_strings(self):
        prompt = NS.build_prompt(INVARIANTS, variants_per_invariant=2)
        self.assertIn("FP-001", prompt)
        self.assertIn("FP-002", prompt)
        self.assertIn("never a shell string", prompt)
        self.assertIn(NS.DEMO_TARGET_ROOT, prompt)
        self.assertIn("Exactly 2 scenarios per invariant", prompt)


class TestCheck(unittest.TestCase):
    def test_fake_adapter_verdicts(self):
        adapter = {
            "evidence_class": "TEST",
            "run_probe": lambda argv, policy: {
                "actual": "forbidden" if argv[0] == "rm" else "prompt",
                "matched_rules": 1, "raw": "test", "note": "",
                "layer": "rules-layer"},
        }
        scenarios = NS.parse_scenarios(GOOD_JSON, {"FP-001", "FP-002"})
        verdicts = NS.check_scenarios(scenarios, "fixtures/policies/default.rules",
                                      adapter=adapter)
        self.assertEqual(verdicts[0]["actual_decision"], "forbidden")
        self.assertTrue(verdicts[0]["decision_matches_expected"])
        self.assertEqual(verdicts[1]["actual_decision"], "prompt")
        self.assertTrue(verdicts[1]["decision_matches_expected"])


class TestLoadInvariants(unittest.TestCase):
    def test_real_catalogue_loads(self):
        inv = NS.load_invariants(["FP-001", "FP-003"])
        self.assertEqual([i["id"] for i in inv], ["FP-001", "FP-003"])
        self.assertIn("forbidden", inv[0]["expected_decisions"])

    def test_unknown_id_fails_closed(self):
        with self.assertRaises(ValueError):
            NS.load_invariants(["FP-999"])


if __name__ == "__main__":
    unittest.main()
