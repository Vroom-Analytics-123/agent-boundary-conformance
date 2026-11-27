#!/usr/bin/env python3
"""Tests for the per-harness live manifests (adapters/*.live.yaml).

Every live harness must have a manifest; every manifest must parse
with the framework's stdlib-only YAML-subset reader, carry the
required fields, use only the agreed status vocabulary, and either
pin a concrete value or say UNKNOWN with what would settle it —
never a guessed pin. Referenced proxy scripts and workflows must
exist in the repo.

Stdlib only (unittest). Run: python3 tests/test_live_manifests.py
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import live_yaml as LY  # noqa: E402

ADAPTERS = REPO / "adapters"

# The 14 live-basis harnesses from the Nov 4 scorecard, plus the two
# documented non-live rows (cursor: blocked; pi: not applicable).
EXPECTED = {
    "amp", "openclaw", "claude-code", "muse-code", "hermes",
    "omnigent", "gemini-cli", "codex", "copilot-cli", "opencode",
    "goose", "strands", "langgraph", "crewai", "cursor", "pi",
}
LIVE = EXPECTED - {"cursor", "pi"}
STATUSES = {"live", "blocked", "not_applicable"}
SANDBOX_MODES = {"not-started", "none", "container", "unknown"}


def all_manifests():
    return sorted(ADAPTERS.glob("*.live.yaml"))


class TestManifestCoverage(unittest.TestCase):
    def test_every_expected_harness_has_a_manifest(self):
        have = {p.name[:-len(".live.yaml")] for p in all_manifests()}
        self.assertEqual(have, EXPECTED)

    def test_no_extra_manifests(self):
        have = {p.name[:-len(".live.yaml")] for p in all_manifests()}
        self.assertEqual(have - EXPECTED, set())


class TestManifestShape(unittest.TestCase):
    REQUIRED_TOP = {"harness", "display_name", "status", "driver",
                    "binary", "auth", "model", "sandbox", "workflow",
                    "scenario_set", "repeats_default", "evidence",
                    "caveats"}

    def test_all_manifests_parse_and_carry_required_fields(self):
        for p in all_manifests():
            with self.subTest(manifest=p.name):
                m = LY.parse_yaml(p.read_text())
                self.assertEqual(set(m.keys()) & self.REQUIRED_TOP,
                                 self.REQUIRED_TOP)
                self.assertEqual(m["harness"], p.name[:-len(".live.yaml")])
                self.assertIn(m["status"], STATUSES)
                self.assertIn(m["sandbox"]["mode"], SANDBOX_MODES)

    def test_live_harnesses_have_concrete_or_unknown_pins(self):
        for p in all_manifests():
            m = LY.parse_yaml(p.read_text())
            if m["status"] != "live":
                continue
            with self.subTest(manifest=p.name):
                b = m["binary"]
                self.assertIn("version_pin", b)
                self.assertIn("install_recipe", b)
                # A pin is either concrete or explicitly UNKNOWN with
                # a settle note; a bare null is a missing pin.
                if b["version_pin"] == "UNKNOWN":
                    self.assertTrue(b.get("unknown_settled_by"),
                                    "UNKNOWN pin needs a settle note")
                if m["model"].get("pinned") == "UNKNOWN":
                    self.assertTrue(m["model"].get("unknown_settled_by"),
                                    "UNKNOWN model needs a settle note")

    def test_referenced_proxy_scripts_exist(self):
        for p in all_manifests():
            m = LY.parse_yaml(p.read_text())
            proxy = m.get("proxy")
            if proxy:
                with self.subTest(manifest=p.name):
                    self.assertTrue(
                        (REPO / proxy["script"]).exists(),
                        f"proxy script missing: {proxy['script']}")

    def test_referenced_workflows_exist_or_are_noted_pending(self):
        for p in all_manifests():
            m = LY.parse_yaml(p.read_text())
            wf = m.get("workflow")
            if wf and wf != "UNKNOWN":
                with self.subTest(manifest=p.name):
                    self.assertTrue(
                        (REPO / wf).exists(),
                        f"workflow missing: {wf}")

    def test_copilot_manifest_is_the_pilot_ready_one(self):
        m = LY.parse_yaml(
            (ADAPTERS / "copilot-cli.live.yaml").read_text())
        self.assertEqual(m["status"], "live")
        self.assertEqual(m["driver"], "copilot")
        self.assertEqual(m["binary"]["version_pin"], "1.0.105")
        self.assertEqual(m["auth"]["secret_name"],
                         "COPILOT_GITHUB_TOKEN")
        self.assertEqual(m["repeats_default"], 2)

    def test_cursor_and_pi_carry_their_blockers(self):
        cursor = LY.parse_yaml(
            (ADAPTERS / "cursor.live.yaml").read_text())
        # Cursor went live 2026-11-08 when CURSOR_API_KEY landed in
        # repo secrets (verified by name only); it is the second
        # driver on the framework after Copilot.
        self.assertEqual(cursor["status"], "live")
        self.assertEqual(cursor["driver"], "cursor")
        self.assertIn("CURSOR_API_KEY", cursor["auth"]["secret_name"])
        self.assertEqual(cursor["binary"]["version_pin"], "UNKNOWN")
        self.assertTrue(cursor["binary"].get("unknown_settled_by"))
        pi = LY.parse_yaml((ADAPTERS / "pi.live.yaml").read_text())
        self.assertEqual(pi["status"], "not_applicable")
        self.assertIsNone(pi["driver"])


class TestYamlSubsetReader(unittest.TestCase):
    def test_maps_lists_scalars(self):
        got = LY.parse_yaml("""
harness: x
nested:
  a: 1
  b: "quoted"
  c: true
  d: null
items:
  - one
  - two
""")
        self.assertEqual(got, {
            "harness": "x",
            "nested": {"a": 1, "b": "quoted", "c": True, "d": None},
            "items": ["one", "two"]})

    def test_comments_and_blank_lines_ignored(self):
        self.assertEqual(LY.parse_yaml("# hi\n\na: 1 # trailing\n"),
                         {"a": 1})

    def test_bad_indentation_fails(self):
        with self.assertRaises(ValueError):
            LY.parse_yaml("a:\n   b: 1\n  c: 2\n")


if __name__ == "__main__":
    unittest.main()
