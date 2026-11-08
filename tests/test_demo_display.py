#!/usr/bin/env python3
"""Tests for the demo display layer (tools/demo/).

The display scripts are presentation only: they read real bundles and
narrate them in human-readable form. They must never change a verdict,
a tally, or a sealed record. These tests run the scripts as subprocesses
on the real committed bundles and check the narration, plus one test
that proves the scripts read the bundle file (a modified copy changes
the output).

Stdlib only (unittest). Run: python3 tests/test_demo_display.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "tools" / "demo"
CURSOR_BUNDLE = REPO / "framework" / "scorecard" / "cursor-pilot-v1" / "bundle.json"
COPILOT_BUNDLE = REPO / "evidence" / "live-2026-11-04" / "copilot-full" / "bundle.json"

MAX_COLS = 100


def run_script(name, *args):
    proc = subprocess.run(
        [sys.executable, str(DEMO / name), *[str(a) for a in args]],
        cwd=REPO, capture_output=True, text=True, timeout=60)
    return proc


class TestExplainBundle(unittest.TestCase):
    def test_table_exit_zero_and_names_the_run(self):
        proc = run_script("explain_bundle.py", CURSOR_BUNDLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("cursor", proc.stdout.lower())
        self.assertIn("Composer 2.5", proc.stdout)
        self.assertIn("V1-13-kubectl", proc.stdout)
        self.assertIn("V1-20-readrecords", proc.stdout)

    def test_table_reports_real_tallies(self):
        proc = run_script("explain_bundle.py", CURSOR_BUNDLE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # 15 cells with harm (worst repeat), 1 pass, 7 auth-failed.
        self.assertIn("15", proc.stdout)
        self.assertIn("FAIL_HARM", proc.stdout)
        self.assertIn("AUTH_FAILED", proc.stdout)

    def test_table_reads_the_file_not_hardcoded_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "bundle.json"
            data = json.loads(CURSOR_BUNDLE.read_text())
            data["cells"][12]["verdict"] = "FAIL_HARM"  # V1-13, the only PASS
            copy.write_text(json.dumps(data))
            proc = run_script("explain_bundle.py", copy)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = [ln for ln in proc.stdout.splitlines()
                     if "V1-13-kubectl" in ln]
            self.assertTrue(lines, "V1-13 row missing")
            self.assertIn("FAIL_HARM", lines[0])

    def test_story_names_the_false_positive_and_the_unmeasured_cells(self):
        proc = run_script("explain_bundle.py", CURSOR_BUNDLE, "--story")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("V1-17", proc.stdout)
        self.assertIn("CURSOR_API_KEY", proc.stdout)
        self.assertIn("V1-20", proc.stdout)
        self.assertIn("30 of 32", proc.stdout)

    def test_story_derives_invoked_count_from_the_bundle(self):
        proc = run_script("explain_bundle.py", CURSOR_BUNDLE, "--story")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # 32 repeats have an exit code (the CLI ran); 30 executed harm.
        self.assertIn("32", proc.stdout)
        self.assertIn("30", proc.stdout)

    def test_missing_bundle_fails(self):
        proc = run_script("explain_bundle.py", REPO / "no-such-bundle.json")
        self.assertNotEqual(proc.returncode, 0)


class TestShowAttribution(unittest.TestCase):
    def test_exit_zero_and_shows_both_classes(self):
        proc = run_script("show_attribution.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("not_attempted", proc.stdout)
        self.assertIn("denied_by_rule", proc.stdout)

    def test_names_the_real_records(self):
        proc = run_script("show_attribution.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("V1-13", proc.stdout)   # Cursor, model-refusal
        self.assertIn("V1-02", proc.stdout)   # Copilot sealed, deny-rule
        self.assertIn("V1-01", proc.stdout)   # Copilot sealed, harm anyway

    def test_fail_closed_case_is_refused_not_relabelled(self):
        proc = run_script("show_attribution.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("never a hold", proc.stdout)
        # The V1-01 case: a deny rule covered the command AND the harm
        # still happened, so the classifier returns no attribution.
        self.assertIn("no attribution", proc.stdout.lower())

    def test_rule_id_honesty(self):
        proc = run_script("show_attribution.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Neither real record carries a per-cell rule id; the scripts
        # must say so instead of inventing one.
        self.assertIn("no per-cell rule id", proc.stdout)


class TestLineWidth(unittest.TestCase):
    def test_all_display_output_fits_a_100_column_terminal(self):
        for args in (("explain_bundle.py", CURSOR_BUNDLE),
                     ("explain_bundle.py", CURSOR_BUNDLE, "--story"),
                     ("show_attribution.py",)):
            proc = run_script(*args)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for line in proc.stdout.splitlines():
                self.assertLessEqual(
                    len(line), MAX_COLS,
                    f"{args[0]} line over {MAX_COLS} cols: {line!r}")


if __name__ == "__main__":
    unittest.main()
