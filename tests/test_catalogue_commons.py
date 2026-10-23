"""Tests for the Catalogue Commons: contribution validation (the executable
enforcement of catalogue-contrib/contrib.v1.schema.json), three-layer pack
composition, and the org-overlay privacy property.

Conventions: pytest-style like the rest of tests/ (plain asserts; the file
also runs under unittest). No oracle calls — composition and validation are
pure.
"""

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import catalogue_loader as CL  # noqa: E402

EXAMPLES = REPO / "catalogue-contrib" / "examples"
COMMUNITY = EXAMPLES / "community" / "FP-COMM-001-privilege-escalation-gate.json"
ORG = EXAMPLES / "org-overlay" / "ORG-ACME-001-staging-db-drop-block.json"


def load_example(p):
    return json.loads(Path(p).read_text())


class TestContribValidation(unittest.TestCase):
    def test_worked_examples_valid(self):
        for p in (COMMUNITY, ORG):
            entry = load_example(p)
            errors = CL.validate_contrib(entry)
            self.assertEqual(errors, [], f"{p} should validate: {errors}")

    def test_review_bar_no_probes(self):
        entry = load_example(COMMUNITY)
        entry["probe_families"] = []
        errors = CL.validate_contrib(entry)
        self.assertTrue(any("probes" in e for e in errors),
                        f"expected a probes error, got {errors}")

    def test_review_bar_provenance_required(self):
        entry = load_example(COMMUNITY)
        del entry["provenance"]
        errors = CL.validate_contrib(entry)
        self.assertTrue(any("provenance" in e for e in errors))

    def test_measured_before_claimed(self):
        # A contribution cannot self-declare MEASURED without measured
        # provenance + evidence refs.
        entry = load_example(COMMUNITY)
        entry["measurement_status"] = "MEASURED"
        errors = CL.validate_contrib(entry)
        self.assertTrue(errors, "MEASURED without measured provenance "
                                "must be rejected")

    def test_undeclared_slot_rejected(self):
        entry = load_example(COMMUNITY)
        entry["probe_families"][0]["probes"][0] = ["<escalation_bin>",
                                                  "<nope>"]
        errors = CL.validate_contrib(entry)
        self.assertTrue(any("<nope>" in e for e in errors),
                        f"expected undeclared-slot error, got {errors}")

    def test_org_overlay_must_be_private(self):
        entry = load_example(ORG)
        entry["private"] = False
        errors = CL.validate_contrib(entry)
        self.assertTrue(any("private" in e for e in errors))

    def test_community_must_not_be_private(self):
        entry = load_example(COMMUNITY)
        entry["private"] = True
        errors = CL.validate_contrib(entry)
        self.assertTrue(any("private" in e for e in errors))

    def test_id_lane_rules(self):
        entry = load_example(COMMUNITY)
        entry["id"] = "ORG-X-001"
        errors = CL.validate_contrib(entry)
        self.assertTrue(any("FP-" in e for e in errors))
        entry2 = load_example(ORG)
        entry2["id"] = "FP-COMM-999"
        errors2 = CL.validate_contrib(entry2)
        self.assertTrue(any("ORG-" in e for e in errors2))

    def test_cli_validate_contrib(self):
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(REPO / "tools" / "catalogue_loader.py"),
             "--validate-contrib", str(COMMUNITY), str(ORG)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestComposition(unittest.TestCase):
    def setUp(self):
        self.core, _ = CL.load_core()
        self.org_entry = load_example(ORG)

    def test_core_loads_16(self):
        self.assertEqual(len(self.core), 16)
        self.assertTrue(all(e["id"].startswith("FP-") for e in self.core))

    def test_compose_core_only(self):
        entries, report = CL.compose(self.core)
        self.assertEqual(len(entries), 16)
        self.assertEqual(report["core"], 16)
        self.assertTrue(all(e["source_layer"] == "core" for e in entries))
        self.assertTrue(all(e["private"] is False for e in entries))

    def test_compose_with_org_overlay(self):
        entries, report = CL.compose(self.core,
                                     org_overlay=("org.json", [self.org_entry]))
        self.assertEqual(len(entries), 17)
        org = [e for e in entries if e["source_layer"] == "org"]
        self.assertEqual(len(org), 1)
        self.assertTrue(org[0]["private"])
        self.assertEqual(report["org"]["entries"], 1)

    def test_org_override_wins_and_stays_private(self):
        override = deepcopy(self.org_entry)
        override["id"] = "FP-001"  # intentional override of a core id
        entries, report = CL.compose(self.core,
                                     org_overlay=("org.json", [override]))
        self.assertEqual(len(entries), 16)  # no growth: replaced
        fp1 = [e for e in entries if e["id"] == "FP-001"][0]
        self.assertEqual(fp1["source_layer"], "org")
        self.assertTrue(fp1["private"])
        self.assertEqual(report["overrides"][0]["id"], "FP-001")

    def test_duplicate_domain_ids_rejected(self):
        pack_a = [deepcopy(self.org_entry)]
        pack_a[0]["id"] = "FP-DOM-001"
        pack_a[0]["private"] = False
        pack_a[0]["contribution_kind"] = "community"
        pack_b = [deepcopy(pack_a[0])]
        with self.assertRaises(CL.ContribViolation):
            CL.compose(self.core,
                       domain_packs=[("a.json", pack_a), ("b.json", pack_b)])

    def test_strip_private(self):
        entries, _ = CL.compose(self.core,
                                org_overlay=("org.json", [self.org_entry]))
        public = CL.strip_private(entries)
        self.assertEqual(len(public), 16)
        self.assertTrue(all(not e["private"] for e in public))


class TestPrivacyProperty(unittest.TestCase):
    """Org entries never appear in any emitted public artifact."""

    def setUp(self):
        core, _ = CL.load_core()
        org_entry = load_example(ORG)
        self.entries, _ = CL.compose(core,
                                     org_overlay=("org.json", [org_entry]))

    def test_public_artifact_text_has_no_private_ids(self):
        public = CL.strip_private(self.entries)
        text = json.dumps(public)
        hits = CL.public_text_contains_private(self.entries, text)
        self.assertEqual(hits, [])

    def test_full_artifact_text_does_name_them(self):
        # Sanity: the check itself is capable of finding the ids when they
        # ARE present (so the empty result above is meaningful).
        text = json.dumps(self.entries)
        hits = CL.public_text_contains_private(self.entries, text)
        self.assertEqual(hits, ["ORG-ACME-001"])

    def test_public_only_run_emits_no_private_content(self):
        """End-to-end: fineprint_check --public-only with an org overlay."""
        import subprocess
        overlay = {"entries": [load_example(ORG)]}
        with tempfile.TemporaryDirectory(prefix="commons-priv-") as tmp:
            tmp = Path(tmp)
            ov_path = tmp / "overlay.json"
            ov_path.write_text(json.dumps(overlay))
            out = tmp / "out"
            cmd = [sys.executable,
                   str(REPO / "tools" / "fineprint_check.py"),
                   "--harness", "codex",
                   "--policy", str(REPO / "fixtures" / "policies"
                                   / "default.rules"),
                   "--bindings", str(REPO / "evidence" / "demo-check-2026-10-22"
                                      / "bindings.json"),
                   "--org-overlay", str(ov_path),
                   "--only", "FP-016,ORG-ACME-001",
                   "--public-only",
                   "--out", str(out),
                   "--label", "privacy-test"]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=300)
            self.assertEqual(proc.returncode, 0,
                             f"run failed:\n{proc.stdout}\n{proc.stderr}")
            for artifact in ("bundle.json", "scorecard.json",
                             "scorecard.html"):
                text = (out / artifact).read_text()
                self.assertNotIn("ORG-ACME-001", text,
                                 f"{artifact} leaks the org entry id")
                self.assertNotIn("staging-db-drop", text,
                                 f"{artifact} leaks org content")
            bundle = json.loads((out / "bundle.json").read_text())
            self.assertTrue(bundle["privacy"]["public_mode"])
            self.assertFalse(bundle["privacy"]["org_entries_included"])
            self.assertEqual(bundle["privacy"]["org_entries"], 1)
            # The bundle still records THAT an overlay was present (count
            # only — never path or content).
            self.assertTrue(bundle["run"]["pack"]["org_overlay"]["present"])


if __name__ == "__main__":
    unittest.main()
