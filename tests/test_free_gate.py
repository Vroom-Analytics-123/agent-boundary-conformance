"""Tests for the free gate (`tools/fineprint_gate.py` + `fineprint gate`).

TDD: written BEFORE the gate existed. The free gate is a subprocess-wrapper
guard adapted from the paid-product prototype's decision logic, hardened
with realpath (symlink) resolution. It is NOT a sandbox: the tests pin
the decisions it must make (allow/deny, traversal, symlink escape, audit
log + tamper detection, run/don't-run) and the limits live in
docs/FREE_GATE.md.

Stdlib only (unittest under pytest).
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FINEPRINT = REPO / "fineprint"
sys.path.insert(0, str(REPO / "tools"))
import fineprint_gate as FG  # noqa: E402


def policy_for(tmp, hosts=()):
    # Confinement tests: the folder allowlist (opt-in since the
    # default became the protective denylist).
    return FG.Policy(allowed_paths=(str(tmp),), allowed_hosts=tuple(hosts),
                     mode="confine")


class TestDecisions(unittest.TestCase):
    def test_allow_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = policy_for(tmp)
            d = p.decide(FG.Action("file_read", str(Path(tmp) / "a.txt")))
            self.assertTrue(d.allowed)

    def test_deny_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = policy_for(tmp)
            d = p.decide(FG.Action("file_read", "/etc/passwd"))
            self.assertFalse(d.allowed)
            self.assertIn("outside", d.reason)

    def test_deny_dotdot_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = policy_for(tmp)
            target = str(Path(tmp) / "sub" / ".." / ".." / "etc" / "passwd")
            d = p.decide(FG.Action("file_read", target))
            self.assertFalse(d.allowed)
            self.assertIn("traversal", d.reason)

    def test_deny_symlink_escape(self):
        # A symlink inside the allowed dir pointing outside must be denied:
        # the check runs on the resolved (real) path, not the lexical one.
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret")
            scope = Path(tmp) / "scope"
            scope.mkdir()
            link = scope / "escape"
            link.symlink_to(outside)
            p = FG.Policy(allowed_paths=(str(scope),), mode="confine")
            d = p.decide(FG.Action("file_read", str(link)))
            self.assertFalse(d.allowed)
            self.assertIn("outside", d.reason)

    def test_allow_symlink_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = Path(tmp) / "scope"
            scope.mkdir()
            real = scope / "real.txt"
            real.write_text("ok")
            link = scope / "alias"
            link.symlink_to(real)
            p = FG.Policy(allowed_paths=(str(scope),), mode="confine")
            d = p.decide(FG.Action("file_read", str(link)))
            self.assertTrue(d.allowed)

    def test_deny_unknown_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = policy_for(tmp)
            d = p.decide(FG.Action("exec", "rm"))
            self.assertFalse(d.allowed)

    def test_network_allowlist_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = policy_for(tmp, hosts=("pypi.org",))
            self.assertTrue(p.decide(
                FG.Action("network", "PyPI.org")).allowed)
            self.assertFalse(p.decide(
                FG.Action("network", "unapproved.example")).allowed)

    def test_network_url_host_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = policy_for(tmp, hosts=("pypi.org",))
            self.assertTrue(p.decide(FG.Action(
                "network", "https://pypi.org/simple/")).allowed)
            self.assertFalse(p.decide(FG.Action(
                "network", "https://evil.example/x")).allowed)


class TestAuditLog(unittest.TestCase):
    def test_append_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = FG.AuditLog(str(Path(tmp) / "audit.jsonl"))
            p = policy_for(tmp)
            g = FG.Gate(p, log)
            g.evaluate(FG.Action("file_read", str(Path(tmp) / "a")))
            g.evaluate(FG.Action("file_read", "/etc/passwd"))
            self.assertTrue(FG.AuditLog.verify(str(Path(tmp) / "audit.jsonl")))

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = FG.AuditLog(str(path))
            p = policy_for(tmp)
            FG.Gate(p, log).evaluate(
                FG.Action("file_read", str(Path(tmp) / "a")))
            FG.Gate(p, log).evaluate(FG.Action("file_read", "/etc/passwd"))
            lines = path.read_text().splitlines()
            entry = json.loads(lines[0])
            entry["allowed"] = not entry["allowed"]
            lines[0] = json.dumps(entry, sort_keys=True)
            path.write_text("\n".join(lines) + "\n")
            self.assertFalse(FG.AuditLog.verify(str(path)))


class TestGateRun(unittest.TestCase):
    def _policy_file(self, tmp, mode="confine"):
        path = Path(tmp) / "gate.json"
        path.write_text(json.dumps(
            {"mode": mode, "allowed_paths": [str(tmp)],
             "allowed_hosts": []}))
        return str(path)

    def test_run_allows_in_scope_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hello.txt"
            target.write_text("hello gate\n")
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "run",
                 "--policy", self._policy_file(tmp),
                 "--log", str(Path(tmp) / "audit.jsonl"),
                 "--", "cat", str(target)],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("hello gate", proc.stdout)

    def test_run_denies_outside_path_without_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "run",
                 "--policy", self._policy_file(tmp),
                 "--log", str(Path(tmp) / "audit.jsonl"),
                 "--", "cat", "/etc/passwd"],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertNotIn("root:", proc.stdout)
            self.assertIn("deny", (proc.stdout + proc.stderr).lower())

    def test_run_denies_unapproved_host_without_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "run",
                 "--policy", self._policy_file(tmp),
                 "--log", str(Path(tmp) / "audit.jsonl"),
                 "--", "curl", "https://unapproved.example/x"],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("not allowlisted",
                          (proc.stdout + proc.stderr).lower())

    def test_run_passes_through_child_exit_code(self):
        # Deny mode: the `python3 -c` code string is a bare argv token
        # (a file_read) — confinement would deny it, the denylist
        # allows it, and the child's exit code passes through.
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "run",
                 "--policy", self._policy_file(tmp, mode="deny"),
                 "--log", str(Path(tmp) / "audit.jsonl"),
                 "--", sys.executable, "-c", "import sys; sys.exit(7)"],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 7, proc.stdout)

    def test_gate_check_no_policy_uses_default(self):
        # Zero config: no --policy flag -> the protective denylist
        # (normal work anywhere is allowed; a protected file is
        # denied).
        with tempfile.TemporaryDirectory() as tmp:
            inside = Path(tmp) / "hello.txt"
            inside.write_text("hi\n")
            ok = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "check",
                 "--file", str(inside)],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(ok.returncode, 0, ok.stdout)
            secret = Path(tmp) / ".env"
            secret.write_text("AWS_SECRET=x\n")
            bad = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "check",
                 "--file", str(secret)],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(bad.returncode, 2, bad.stdout)
            self.assertIn("DENY-CRED-ENV", bad.stdout)

    def test_gate_run_no_policy_uses_default(self):
        # Zero config: the denylist default allows a normal file and
        # denies a protected one (a .env), without executing it.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hello.txt"
            target.write_text("hello gate\n")
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "run",
                 "--", "cat", str(target)],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("hello gate", proc.stdout)
            secret = Path(tmp) / ".env"
            secret.write_text("AWS_SECRET=x\n")
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "run",
                 "--", "cat", str(secret)],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertNotIn("AWS_SECRET", proc.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            policy = self._policy_file(tmp)
            ok = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "check",
                 "--file", str(Path(tmp) / "hello.txt"),
                 "--policy", policy],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(ok.returncode, 0, ok.stdout)
            bad = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "check",
                 "--file", "/etc/passwd", "--policy", policy],
                capture_output=True, text=True, cwd=tmp)
            self.assertEqual(bad.returncode, 2, bad.stdout)


if __name__ == "__main__":
    unittest.main()
