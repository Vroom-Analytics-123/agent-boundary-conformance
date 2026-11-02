"""Pinned-binary path resolution: machine-specific absolute paths must
resolve to this checkout's vendored binary when the pinned path is absent
(the CI failure: bundles pin /home/hatch/... paths that exist nowhere else)."""

import hashlib
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import verify_bundle as VB  # noqa: E402


class TestResolvePinnedBinary(unittest.TestCase):
    def test_vendored_tail_resolves_to_checkout(self):
        got = VB.resolve_pinned_binary(
            "/nonexistent/machine/tools/vendor/codex/0.149.0/bin/codex")
        self.assertEqual(
            got, REPO / "tools/vendor/codex/0.149.0/bin/codex")

    def test_resolved_binary_matches_pinned_sha(self):
        bundle = json.loads(
            (REPO / "evidence/day6-2026-10-26/bundle.json").read_text())
        pinned = bundle["pinned"]
        resolved = VB.resolve_pinned_binary(pinned["binary_path"])
        self.assertTrue(resolved.exists())
        self.assertEqual(VB.sha256_file(resolved), pinned["binary_sha256"])

    def test_relative_path_goes_under_repo(self):
        self.assertEqual(
            VB.resolve_pinned_binary("tools/vendor/codex/0.149.0/bin/codex"),
            REPO / "tools/vendor/codex/0.149.0/bin/codex")

    def test_existing_absolute_path_unchanged(self):
        real = REPO / "tools/vendor/codex/0.149.0/bin/codex"
        self.assertEqual(VB.resolve_pinned_binary(str(real)), real)

    def test_nonvendored_missing_path_returned_as_is(self):
        self.assertEqual(
            VB.resolve_pinned_binary("/opt/hatch-image/bin/codex"),
            Path("/opt/hatch-image/bin/codex"))


if __name__ == "__main__":
    unittest.main()
