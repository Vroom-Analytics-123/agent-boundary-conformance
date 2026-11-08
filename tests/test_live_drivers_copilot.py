#!/usr/bin/env python3
"""Tests for tools/live_drivers/copilot.py — the pilot driver.

Covers model extraction from real recorded Copilot stdout (the
Nov 4 smoke log names gpt-6-luna) and a fake-binary replay: a stub
`copilot` that replays the recorded stdout through the legacy
full_runner + the driver, proving the adapter translates legacy
records and extracts the observed model without a live CLI call.

Stdlib only (unittest). Run: python3 tests/test_live_drivers_copilot.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import live_drivers.base as LB  # noqa: E402
import live_drivers.copilot as COP  # noqa: E402
import live_run as LR  # noqa: E402

SMOKE_STDOUT = (REPO / "copilot-cli" / "runs" / "smoke"
                / "copilot-stdout.log")


class TestModelExtraction(unittest.TestCase):
    def test_recorded_stdout_names_gpt_6_luna(self):
        model, source, candidates = COP._extract_model(SMOKE_STDOUT)
        self.assertEqual(model, "gpt-6-luna")
        self.assertEqual(source, "stdout-metrics")
        self.assertEqual(candidates, ["gpt-6-luna"])

    def test_missing_log_is_unobserved(self):
        model, source, candidates = COP._extract_model(
            Path("/nonexistent/copilot-stdout.log"))
        self.assertIsNone(model)
        self.assertEqual(source, "unobserved")
        self.assertEqual(candidates, [])

    def test_multiple_models_are_unobserved_not_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stdout.log"
            p.write_text(
                '{"model": "gpt-6-luna"}\n'
                '{"model": "mai-code-1.1-flash"}\n')
            model, source, candidates = COP._extract_model(p)
            self.assertIsNone(model)
            self.assertEqual(source, "unobserved")
            self.assertEqual(candidates,
                             ["gpt-6-luna", "mai-code-1.1-flash"])

    def test_model_metrics_keys_count_as_observations(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stdout.log"
            p.write_text(
                '{"type": "session.usage_checkpoint", "data": '
                '{"modelMetrics": {"gpt-6-luna": {"requests": '
                '{"count": 4}}}}}\n')
            model, source, _ = COP._extract_model(p)
            self.assertEqual(model, "gpt-6-luna")
            self.assertEqual(source, "stdout-metrics")


class TestFakeBinaryReplay(unittest.TestCase):
    """A stub `copilot` on PATH that replays the recorded Nov 4
    smoke stdout. The legacy runner invokes it, writes its logs,
    and the driver translates the record — no live CLI, no token,
    no network."""

    def test_replay_one_cell_through_driver(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fake_bin = td / "copilot"
            fake_bin.write_text(
                "#!/bin/sh\n"
                f"cat {SMOKE_STDOUT}\n")
            fake_bin.chmod(0o755)
            env_path = f"{td}:{os.environ['PATH']}"
            old_path = os.environ["PATH"]
            os.environ["PATH"] = env_path
            # A dummy token value for the test only: the stub ignores
            # it, and it is never a real secret.
            os.environ["COPILOT_GITHUB_TOKEN"] = "test-only-dummy"
            try:
                driver = LB.load_driver("copilot")
                manifest = LR.load_manifest("copilot-cli")
                ok, reason = driver.check_environment(manifest, {})
                self.assertTrue(ok, reason)
                tasks = driver.cells(manifest, {})
                self.assertEqual(len(tasks), 24)
                task = tasks[0]
                self.assertEqual(task["cell_id"], "V1-01-direct")
                result = driver.run_cell(
                    manifest, {}, task, 1, td / "scratch")
                self.assertIn(result["verdict"], LR.VERDICTS)
                # The replayed stdout names exactly one model.
                self.assertEqual(result["model_observed"], "gpt-6-luna")
                self.assertEqual(result["model_observed_source"],
                                 "stdout-metrics")
                self.assertFalse(result["harm_executed"])
                # The legacy runner wrote its own record + logs.
                self.assertTrue(
                    (td / "scratch" / "record.json").exists())
                self.assertTrue(
                    (td / "scratch" / "copilot-stdout.log").exists())
            finally:
                os.environ["PATH"] = old_path
                os.environ.pop("COPILOT_GITHUB_TOKEN", None)


if __name__ == "__main__":
    unittest.main()
