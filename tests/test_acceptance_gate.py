"""Unit tests for tools/acceptance_gate.py — the campaign's gate
adapter (find the gate, build the gated argv, parse the audit log).

The gate itself lives in the fineprint checkout (branch free-wall);
these tests use a fake checkout (a directory with a gate script +
a wall module) where the test needs files, and the real checkout
only when FINEPRINT_CHECKOUT is set (the live gate tests are
skipped otherwise — the dry-run is the end-to-end gate test).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import acceptance_gate as AG  # noqa: E402


def _fake_checkout(tmp):
    """A directory that looks like a fineprint checkout (a gate
    script + a wall module, both inert)."""
    d = Path(tmp) / "fake-fineprint"
    (d / "tools").mkdir(parents=True)
    (d / "tools" / "fineprint_gate.py").write_text(
        "#!/usr/bin/env python3\nprint('fake gate')\n")
    (d / "tools" / "fineprint_wall.py").write_text(
        "# fake wall module\n")
    return d


class TestFindGate(unittest.TestCase):
    def test_missing_checkout(self):
        with self.assertRaises(AG.GateError):
            AG.find_gate("/nonexistent/checkout")

    def test_no_gate_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "empty"
            d.mkdir()
            with self.assertRaises(AG.GateError) as ctx:
                AG.find_gate(d)
            self.assertIn("no gate script", str(ctx.exception))

    def test_no_wall_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "no-wall"
            (d / "tools").mkdir(parents=True)
            (d / "tools" / "fineprint_gate.py").write_text("# gate\n")
            with self.assertRaises(AG.GateError) as ctx:
                AG.find_gate(d)
            self.assertIn("no wall module", str(ctx.exception))

    def test_fake_checkout_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _fake_checkout(tmp)
            found = AG.find_gate(d)
            self.assertEqual(found["gate"],
                             d / "tools" / "fineprint_gate.py")
            self.assertEqual(found["wall"],
                             d / "tools" / "fineprint_wall.py")
            self.assertIsNone(found["head"])  # not a git checkout

    def test_real_checkout_head(self):
        checkout = os.environ.get("FINEPRINT_CHECKOUT")
        if not checkout or not Path(checkout).exists():
            self.skipTest("FINEPRINT_CHECKOUT not set")
        found = AG.find_gate(checkout)
        self.assertIsNotNone(found["head"])
        self.assertEqual(len(found["head"]), 40)


class TestGateArgv(unittest.TestCase):
    def setUp(self):
        self.gate = Path("/fake/fineprint_gate.py")
        self.policy = Path("/tmp/policy.json")
        self.log = Path("/tmp/audit.jsonl")

    def test_deny_mode(self):
        argv = AG.gate_argv(
            self.gate, mode="deny", policy_path=self.policy,
            log_path=self.log, agent_argv=["agent", "-p", "hi"])
        self.assertEqual(argv[-4:], ["--", "agent", "-p", "hi"])
        self.assertIn("--policy", argv)
        self.assertIn("--log", argv)
        self.assertNotIn("--confine", argv)
        self.assertNotIn("--no-wall", argv)

    def test_confine_mode_adds_confine(self):
        argv = AG.gate_argv(
            self.gate, mode="confine", policy_path=self.policy,
            log_path=self.log, agent_argv=["agent"])
        self.assertIn("--confine", argv)
        self.assertNotIn("--no-wall", argv)

    def test_no_wall_never_added(self):
        # The proof must never run tripwire-only: --no-wall must not
        # appear in any argv this helper builds, in either mode.
        for mode in ("deny", "confine"):
            argv = AG.gate_argv(
                self.gate, mode=mode, policy_path=self.policy,
                log_path=self.log, agent_argv=["agent"])
            self.assertNotIn("--no-wall", argv,
                             f"--no-wall in {mode} argv")

    def test_empty_agent_argv(self):
        with self.assertRaises(ValueError):
            AG.gate_argv(self.gate, mode="deny",
                         policy_path=self.policy, log_path=self.log,
                         agent_argv=[])

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            AG.gate_argv(self.gate, mode="jail",
                         policy_path=self.policy, log_path=self.log,
                         agent_argv=["agent"])


class TestParseDefinitions(unittest.TestCase):
    def test_valid(self):
        version, count = AG.parse_definitions_output(
            "definitions: v2026-11-07 (built-in)\nrules: 11\n")
        self.assertEqual(version, "2026-11-07")
        self.assertEqual(count, 11)

    def test_missing_version(self):
        with self.assertRaises(AG.GateError):
            AG.parse_definitions_output("rules: 11\n")

    def test_missing_count(self):
        with self.assertRaises(AG.GateError):
            AG.parse_definitions_output(
                "definitions: v2026-11-07 (built-in)\n")

    def test_garbage(self):
        with self.assertRaises(AG.GateError):
            AG.parse_definitions_output("not a definitions output\n")


class TestReadGateLog(unittest.TestCase):
    def _write_log(self, path, entries):
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_missing_file(self):
        out = AG.read_gate_log(Path("/nonexistent/audit.jsonl"))
        self.assertEqual(out["denials"], [])
        self.assertIsNone(out["wall_start"])
        self.assertTrue(out["problems"])
        self.assertTrue(out["chain_problems"])

    def test_wall_start_and_denials(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            self._write_log(log, [
                {"event": "WALL_START", "definitions":
                 "v2026-11-07 (built-in)",
                 "hidden_paths": ["/tmp/x/protected"],
                 "egress": "shared (no hosts denied)",
                 "hash": "0" * 64, "prev_hash": "0" * 64},
                {"allowed": False, "rule": "DENY-DELETE",
                 "deterministic": True,
                 "hash": "1" * 64, "prev_hash": "0" * 64},
            ])
            out = AG.read_gate_log(log)
            self.assertIsNotNone(out["wall_start"])
            self.assertEqual(len(out["denials"]), 1)
            self.assertEqual(out["denials"][0]["rule"], "DENY-DELETE")
            self.assertEqual(
                AG.wall_hidden_paths(out["wall_start"]),
                ["/tmp/x/protected"])
            self.assertEqual(
                AG.wall_definitions(out["wall_start"]),
                "v2026-11-07 (built-in)")

    def test_broken_chain_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            self._write_log(log, [
                {"event": "WALL_START", "hash": "aa" * 32,
                 "prev_hash": "0" * 64},
                {"event": "WALL_END", "hash": "bb" * 32,
                 "prev_hash": "cc" * 32},  # wrong prev_hash
            ])
            out = AG.read_gate_log(log)
            self.assertTrue(out["chain_problems"])

    def test_unparseable_line_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            log.write_text('{"event": "WALL_START"}\nnot json\n')
            out = AG.read_gate_log(log)
            self.assertTrue(out["problems"])
            self.assertIsNotNone(out["wall_start"])


class TestRunGateReal(unittest.TestCase):
    """The real gate, when FINEPRINT_CHECKOUT is set. The dry-run
    is the end-to-end test; these are the smoke checks."""

    def test_probe_and_definitions(self):
        checkout = os.environ.get("FINEPRINT_CHECKOUT")
        if not checkout or not Path(checkout).exists():
            self.skipTest("FINEPRINT_CHECKOUT not set")
        gate = AG.find_gate(checkout)["gate"]
        code, out, err = AG.run_gate(gate, ["probe"])
        self.assertEqual(code, 0, out + err)
        code, out, err = AG.run_gate(gate, ["definitions"])
        self.assertEqual(code, 0, out + err)
        version, count = AG.parse_definitions_output(out)
        self.assertEqual(count, 11)


if __name__ == "__main__":
    unittest.main()
