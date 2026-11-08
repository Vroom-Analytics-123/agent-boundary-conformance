#!/usr/bin/env python3
"""Tests for the V1-15 fixture (framework/scorecard/copilot-full-v1/
runners/full_runner.py::setup_git_diverged) and the setup-error
formatting.

F4: the Cursor pilot's V1-15 failed in setup (`git push` exit 128)
and was never started. Two defects: (1) the fixture's git calls
carried no safe.directory exception, so git's dubious-ownership
check — the one mechanism that produces exactly a deterministic
exit 128 on a local push, verified locally — fails the push when the
fixture repos are owned by a different user than the one running
git; (2) the failure reason discarded git's stderr, so the cause
was unknowable from the record alone.

The fix writes a fixture-scoped global-config file (GIT_CONFIG_GLOBAL)
carrying the safe.directory entries. `-c` alone is NOT enough: git
unsets GIT_CONFIG_PARAMETERS when spawning receive-pack, so `-c`
never reaches the remote side (verified: with `-c` the local side
passed and receive-pack still failed on origin.git). The config
file is the only channel both sides read. The cross-user case was
verified end to end by hand (fixture flow as an unprivileged user
on root-owned repos succeeds with GIT_CONFIG_GLOBAL; fails without
it) — it cannot run in this suite because it needs a second user.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "framework" / "scorecard"
                       / "copilot-full-v1" / "runners"))

import full_runner as legacy  # noqa: E402


class TestSetupGitDiverged(unittest.TestCase):
    def setUp(self):
        self._saved_env = os.environ.pop("GIT_CONFIG_GLOBAL", None)

    def tearDown(self):
        if self._saved_env is None:
            os.environ.pop("GIT_CONFIG_GLOBAL", None)
        else:
            os.environ["GIT_CONFIG_GLOBAL"] = self._saved_env

    def test_setup_writes_safe_config_and_points_env_at_it(self):
        # The fixture must write a global-config file carrying the
        # fixture paths as safe.directory and point GIT_CONFIG_GLOBAL
        # at it, so both the local git calls and the receive-pack
        # they spawn (and the agent's own git push later) trust them.
        with tempfile.TemporaryDirectory() as td:
            rundir = Path(td) / "run"
            rundir.mkdir()
            legacy.setup_git_diverged(rundir)
            cfg = rundir / "gitconfig-safe"
            self.assertTrue(cfg.is_file())
            text = cfg.read_text()
            for path in (rundir, rundir / "origin.git",
                         rundir / "tmpclone"):
                self.assertIn(f"directory = {path}", text)
            self.assertEqual(os.environ.get("GIT_CONFIG_GLOBAL"),
                             str(cfg))

    def test_setup_preserves_existing_global_config(self):
        # The fixture's config file is the user's existing global
        # config plus the safe entries — nothing configured is lost.
        with tempfile.TemporaryDirectory() as td:
            keep = Path(td) / "keep.gitconfig"
            keep.write_text("[user]\n\tname = keeper\n")
            os.environ["GIT_CONFIG_GLOBAL"] = str(keep)
            rundir = Path(td) / "run"
            rundir.mkdir()
            legacy.setup_git_diverged(rundir)
            text = (rundir / "gitconfig-safe").read_text()
            self.assertIn("keeper", text)
            self.assertIn(f"directory = {rundir}", text)

    def test_fixture_actually_works(self):
        # End to end with real git: the fixture builds a diverged
        # remote and returns its main sha.
        with tempfile.TemporaryDirectory() as td:
            rundir = Path(td) / "run"
            rundir.mkdir()
            sha = legacy.setup_git_diverged(rundir)
            self.assertEqual(len(sha), 40)
            self.assertTrue((rundir / "origin.git").is_dir())


class TestSetupErrorText(unittest.TestCase):
    def test_git_stderr_is_carried(self):
        err = subprocess.CalledProcessError(
            128, ["git", "push", "origin", "main"],
            stderr="fatal: detected dubious ownership in repository "
                   "at '/x'\n")
        text = legacy.setup_error_text(err)
        self.assertIn("CalledProcessError", text)
        self.assertIn("128", text)
        self.assertIn("dubious ownership", text)

    def test_plain_exception_has_no_stderr_suffix(self):
        text = legacy.setup_error_text(ValueError("boom"))
        self.assertEqual(text, "ValueError: boom")


if __name__ == "__main__":
    unittest.main()
