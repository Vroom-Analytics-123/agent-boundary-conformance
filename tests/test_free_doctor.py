"""Tests for `fineprint doctor` — the environment diagnostic.

Doctor is diagnostic only: it reports, by name, whether the policy
file, the pinned oracle, and the wall's preconditions are present, with
the remedy for each gap. It changes nothing and checks nothing (that
is `check`'s job). The contract pinned here: exit 0 unless something
is actually broken (a restored oracle failing its pin, python too
old); a MISSING line is a gap with a remedy, not a failure — the same
hosted-CI honesty as the wall tests' skip convention.

Stdlib only (unittest under pytest).
"""

import contextlib
import functools
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FINEPRINT = REPO / "fineprint"
sys.path.insert(0, str(REPO / "tools"))
import pin  # noqa: E402


def run_doctor(cwd):
    proc = subprocess.run([sys.executable, str(FINEPRINT), "doctor"],
                          capture_output=True, text=True, cwd=cwd)
    return proc.returncode, proc.stdout


class TestDoctor(unittest.TestCase):
    def test_exit_zero_and_names_every_gap_in_an_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_doctor(tmp)
            self.assertEqual(code, 0)
            self.assertIn("python   OK", out)
            self.assertIn("policy   NONE", out)
            self.assertIn("`fineprint init`", out)
            self.assertIn("oracle   OK", out)
            self.assertIn("wall", out)
            self.assertIn("nothing broken", out)

    def test_policy_found_line_names_the_harness_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "fineprint.settings.json").write_text("{}\n")
            code, out = run_doctor(tmp)
            self.assertEqual(code, 0)
            self.assertIn("policy   FOUND    claude-code: "
                          "fineprint.settings.json", out)

    def test_wall_missing_when_user_namespaces_unavailable(self):
        # Same trick as the wall tests' simulated no-unshare runner:
        # a PATH with no `unshare` must read as wall MISSING, and the
        # exit stays 0 — a gap with a remedy, not a failure.
        empty = tempfile.mkdtemp()
        env = dict(os.environ)
        env["PATH"] = empty
        proc = subprocess.run([sys.executable, str(FINEPRINT), "doctor"],
                              capture_output=True, text=True,
                              cwd=tempfile.mkdtemp(), env=env)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("wall     MISSING", out := proc.stdout)
        self.assertIn("`fineprint gate probe`", out)

    def test_oracle_pin_mismatch_fails_closed_with_exit_3(self):
        # A restored-but-wrong oracle is the one thing that must fail:
        # the pin is the gate, and doctor reports it, exit 3.
        bad = tempfile.mkdtemp()
        fake = Path(bad) / "codex"
        fake.write_bytes(b"not the pinned oracle")
        original_vendored, original_host = pin.VENDORED_CODEX, pin.HOST_CODEX
        pin.VENDORED_CODEX = fake
        pin.HOST_CODEX = Path(bad) / "absent"
        try:
            import importlib.machinery
            import importlib.util
            loader = importlib.machinery.SourceFileLoader(
                "fineprint_cli", str(FINEPRINT))
            spec = importlib.util.spec_from_file_location(
                "fineprint_cli", FINEPRINT, loader=loader)
            fineprint = importlib.util.module_from_spec(spec)
            loader.exec_module(fineprint)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = fineprint.cmd_doctor({})
            self.assertEqual(code, fineprint.EXIT_UNKNOWN)
            self.assertIn("oracle   FAIL", buf.getvalue())
            self.assertIn("fails its pin", buf.getvalue())
        finally:
            pin.VENDORED_CODEX, pin.HOST_CODEX = original_vendored, original_host

    def test_help_lists_doctor(self):
        proc = subprocess.run([sys.executable, str(FINEPRINT), "--help"],
                              capture_output=True, text=True)
        self.assertIn("fineprint doctor", proc.stdout)


if __name__ == "__main__":
    unittest.main()