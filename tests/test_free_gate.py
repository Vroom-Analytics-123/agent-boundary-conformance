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


class TestExfil(unittest.TestCase):
    """F2: DENY-EXFIL is a synthetic tripwire rule, declared in the
    definitions module and printed by `gate definitions` — never a
    rule id that lives nowhere. The pack stays 11 rules, v2026-11-07
    (the app's real-CLI tests pin both)."""

    def test_cp_protected_file_denied_exfil(self):
        import fineprint_definitions as D
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / ".env"
            secret.write_text("AWS_SECRET=x\n")
            g = FG.Gate(FG.Policy((".",), (), mode="deny"))
            d = g.check_command(["cp", str(secret), "/tmp/x"])
            self.assertFalse(d.allowed, d.reason)
            self.assertEqual(d.rule, D.DENY_EXFIL_ID)

    def test_exfil_rule_id_is_declared(self):
        import fineprint_definitions as D
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / ".env"
            secret.write_text("AWS_SECRET=x\n")
            g = FG.Gate(FG.Policy((".",), (), mode="deny"))
            d = g.check_command(["cp", str(secret), "/tmp/x"])
            declared = [r["id"] for r in D.SYNTHETIC_RULES]
            self.assertIn(d.rule, declared)

    def test_cp_normal_file_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            normal = Path(tmp) / "notes.txt"
            normal.write_text("hi\n")
            g = FG.Gate(FG.Policy((".",), (), mode="deny"))
            d = g.check_command(["cp", str(normal), "/tmp/x"])
            self.assertTrue(d.allowed, d.reason)

    def test_gate_definitions_prints_synthetic_exfil(self):
        proc = subprocess.run(
            [sys.executable, str(FINEPRINT), "gate", "definitions"],
            capture_output=True, text=True, cwd=tempfile.gettempdir())
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("DENY-EXFIL", proc.stdout)
        self.assertIn("synthetic", proc.stdout.lower())
        self.assertIn("rules: 11", proc.stdout)
        self.assertIn("v2026-11-07", proc.stdout)


class TestUnwrapWrappers(unittest.TestCase):
    """F1: the tripwire must unwrap wrappers (sudo, env, bash -lc,
    sh -c and equivalents) and re-check the inner command against
    the denylist. Before F1, `bash -lc "rm -rf …"` and `env rm -rf …`
    deleted the target through the wall, and `sudo rm -rf …` survived
    only because sudo itself broke inside the user namespace."""

    def _gate(self):
        return FG.Gate(FG.Policy((".",), (), mode="deny"))

    def _deny(self, argv):
        d = self._gate().check_command(argv)
        return d

    def test_plain_rm_still_denied(self):
        d = self._deny(["rm", "-rf", "target.txt"])
        self.assertFalse(d.allowed)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_sudo_rm_denied(self):
        d = self._deny(["sudo", "rm", "-rf", "target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_sudo_with_user_flag_denied(self):
        d = self._deny(["sudo", "-u", "root", "rm", "-rf", "target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_env_rm_denied(self):
        d = self._deny(["env", "rm", "-rf", "target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_env_with_assignment_denied(self):
        d = self._deny(["env", "FOO=bar", "rm", "-rf", "target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_bash_lc_rm_denied(self):
        d = self._deny(["bash", "-lc", "rm -rf target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_sh_c_rm_denied(self):
        d = self._deny(["sh", "-c", "rm -rf target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_bash_c_second_command_denied(self):
        # A dangerous command after a benign one in the same -c string.
        d = self._deny(["bash", "-c", "echo hi; rm -rf target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_bash_c_and_chain_denied(self):
        d = self._deny(["bash", "-c", "echo hi && rm -rf target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_bash_c_unlink_denied(self):
        d = self._deny(["bash", "-c", "unlink target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-UNLINK")

    def test_bash_c_subshell_rm_denied(self):
        # A delete hidden in a command substitution still executes.
        d = self._deny(["bash", "-c", "echo $(rm -rf target.txt)"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_nested_wrappers_denied(self):
        d = self._deny(["sudo", "env", "bash", "-c", "rm -rf target.txt"])
        self.assertFalse(d.allowed, d.reason)
        self.assertEqual(d.rule, "DENY-DELETE")

    def test_bash_c_benign_allowed(self):
        d = self._deny(["bash", "-c", "echo hello"])
        self.assertTrue(d.allowed, d.reason)

    def test_sudo_benign_allowed(self):
        d = self._deny(["sudo", "echo", "hello"])
        self.assertTrue(d.allowed, d.reason)

    def test_unwrap_plain_unchanged(self):
        self.assertEqual(FG.unwrap_argv(["rm", "-rf", "x"]),
                         [["rm", "-rf", "x"]])

    def test_unwrap_bash_lc(self):
        self.assertEqual(
            FG.unwrap_argv(["bash", "-lc", "rm -rf target.txt"]),
            [["rm", "-rf", "target.txt"]])

    def test_unwrapped_env_path_is_scanned(self):
        # `bash -c "cat /tmp/x/.env"`: the unwrapped tokens must reach
        # the path scan, so the credential rule fires.
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / ".env"
            secret.write_text("AWS_SECRET=x\n")
            g = self._gate()
            inner = FG.unwrap_argv(
                ["bash", "-c", f"cat {secret}"])[0]
            denied = [g.evaluate(a) for a in FG.scan_argv(inner)]
            self.assertTrue(any(not d.allowed for d in denied))
            self.assertEqual(
                next(d.rule for d in denied if not d.allowed),
                "DENY-CRED-ENV")


class TestGateRunWrappers(unittest.TestCase):
    """End to end: the wrapped deletes must exit 2 at the tripwire
    and the target file must survive (smoke test T2–T4)."""

    def _run_wrapped(self, tmp, argv):
        target = Path(tmp) / "target.txt"
        target.write_text("do not delete\n")
        proc = subprocess.run(
            [sys.executable, str(FINEPRINT), "gate", "run",
             "--log", str(Path(tmp) / "audit.jsonl"),
             "--no-wall", "--"] + argv,
            capture_output=True, text=True, cwd=tmp)
        return proc, target

    def test_sudo_rm_exit_2_file_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, target = self._run_wrapped(
                tmp, ["sudo", "rm", "-rf", "target.txt"])
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("DENY-DELETE", proc.stdout)
            self.assertTrue(target.exists())

    def test_bash_lc_rm_exit_2_file_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, target = self._run_wrapped(
                tmp, ["bash", "-lc", "rm -rf target.txt"])
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("DENY-DELETE", proc.stdout)
            self.assertTrue(target.exists())

    def test_env_rm_exit_2_file_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, target = self._run_wrapped(
                tmp, ["env", "rm", "-rf", "target.txt"])
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("DENY-DELETE", proc.stdout)
            self.assertTrue(target.exists())


class TestGateLogSummary(unittest.TestCase):
    """`gate log --summary`: the boundaries-under-test view — which
    rules fire most, which agents keep testing them. A view on the
    existing audit log, not new measurement."""

    def _log_with_denials(self, tmp):
        path = Path(tmp) / "audit.jsonl"
        log = FG.AuditLog(str(path))
        p = policy_for(tmp)
        g = FG.Gate(p, log)
        # 3 denials by DENY-CRED-ENV, 1 by DENY-DELETE, 1 allow.
        # The .env rule matches a file NAMED .env (**/.env), so each
        # denial needs its own directory.
        for name in ("a", "b", "c"):
            sub = Path(tmp) / name
            sub.mkdir()
            target = sub / ".env"
            target.write_text("x\n")
            g.evaluate(FG.Action("file_read", str(target)))
        target = Path(tmp) / "target.txt"
        target.write_text("x\n")
        g.check_command(["rm", "-rf", str(target)])
        g.evaluate(FG.Action("file_read", str(Path(tmp) / "notes.txt")))
        return path

    def test_summary_counts_denials_by_rule_most_blocked_first(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            path = self._log_with_denials(tmp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(FG.cmd_log(str(path), summary=True), 0)
            out = buf.getvalue()
            self.assertIn("denials: 4", out)
            self.assertIn("DENY-CRED-ENV", out)
            self.assertIn("DENY-DELETE", out)
            # Most-blocked first: the .env rule (3) before rm (1).
            self.assertLess(out.index("DENY-CRED-ENV"),
                            out.index("DENY-DELETE"))

    def test_summarize_log_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._log_with_denials(tmp)
            entries = [json.loads(l) for l in
                       path.read_text().splitlines() if l.strip()]
            s = FG.summarize_log_entries(entries)
            self.assertEqual(s["total"], 5)
            self.assertEqual(s["denied"], 4)
            self.assertEqual(s["allowed"], 1)
            self.assertEqual(s["by_rule"],
                             [("DENY-CRED-ENV", 3), ("DENY-DELETE", 1)])
            self.assertEqual(s["by_agent"], [])
            self.assertEqual(s["canary"], {"held": 0, "failed": 0})

    def test_summary_counts_by_agent_when_the_log_carries_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = FG.AuditLog(str(path))
            for agent in ("codex", "codex", "claude"):
                target = Path(tmp) / f"{agent}.env"
                target.write_text("x\n")
                log.append(FG.Action("file_read", str(target)),
                           FG.Decision(False, "denied", rule="DENY-CRED-ENV"),
                           note="test", extra={"agent": agent})
            entries = [json.loads(l) for l in
                       path.read_text().splitlines() if l.strip()]
            s = FG.summarize_log_entries(entries)
            self.assertEqual(s["by_agent"],
                             [("codex", 2), ("claude", 1)])

    def test_summary_counts_canary_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = FG.AuditLog(str(path))
            log.append(FG.Action("canary", "FINEPRINT-CANARY-aaa"),
                       FG.Decision(True, "held"), note="canary check",
                       event="CANARY",
                       extra={"marker": "FINEPRINT-CANARY-aaa",
                              "reached": False, "routes": [],
                              "verdict": "HELD"})
            log.append(FG.Action("canary", "FINEPRINT-CANARY-bbb"),
                       FG.Decision(False, "failed"), note="canary check",
                       event="CANARY",
                       extra={"marker": "FINEPRINT-CANARY-bbb",
                              "reached": True, "routes": ["stdout"],
                              "verdict": "FAILED"})
            entries = [json.loads(l) for l in
                       path.read_text().splitlines() if l.strip()]
            s = FG.summarize_log_entries(entries)
            self.assertEqual(s["canary"], {"held": 1, "failed": 1})
            # A failed canary is a boundary failure, not a denial.
            self.assertEqual(s["denied"], 0)

    def test_summary_on_an_empty_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text("")
            s = FG.summarize_log_entries([])
            self.assertEqual(s["total"], 0)
            self.assertEqual(s["denied"], 0)
            self.assertEqual(s["by_rule"], [])
            self.assertEqual(s["by_agent"], [])
            self.assertEqual(s["canary"], {"held": 0, "failed": 0})
            self.assertEqual(FG.cmd_log(str(path), summary=True), 0)

    def test_summary_via_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._log_with_denials(tmp)
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "log",
                 "--log", str(path), "--summary"],
                cwd=tmp, capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("DENY-CRED-ENV", proc.stdout)
            self.assertIn("3", proc.stdout)
            self.assertIn("DENY-DELETE", proc.stdout)
            self.assertIn("no agent recorded", proc.stdout)
            # The per-entry lines are NOT printed in summary mode.
            self.assertNotIn("tried", proc.stdout)


class TestRuleReasons(unittest.TestCase):
    """Nov 8 (Reddit): every rule carries a reason — why it is
    restricted — and the reason is surfaced to the agent in the
    deny message and in `gate check` output, not just in the
    definitions list."""

    def test_command_deny_carries_the_rule_reason(self):
        p = FG.Policy((), (), mode="deny")
        g = FG.Gate(p, None)
        d = g.check_command(["rm", "-rf", "target.txt"])
        self.assertFalse(d.allowed)
        self.assertEqual(d.rule, "DENY-DELETE")
        self.assertIn("a recursive delete destroys work with no undo",
                      d.reason)

    def test_path_deny_carries_the_rule_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("x\n")
            p = policy_for(tmp)
            g = FG.Gate(p, None)
            d = g.evaluate(FG.Action("file_read", str(env)))
            self.assertFalse(d.allowed)
            self.assertEqual(d.rule, "DENY-CRED-ENV")
            self.assertIn(".env files hold app secrets and API keys",
                          d.reason)

    def test_gate_check_prints_the_rule_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("x\n")
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "check",
                 "--file", str(env)],
                cwd=tmp, capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("DENY-CRED-ENV", proc.stdout)
            self.assertIn(".env files hold app secrets", proc.stdout)

    def test_policy_reason_round_trip(self):
        doc = {"mode": "deny",
               "reason": "we keep prod keys out of the agent's reach"}
        p = FG.Policy.from_dict(doc)
        self.assertEqual(p.reason,
                         "we keep prod keys out of the agent's reach")
        self.assertEqual(FG.Policy.from_dict({"mode": "deny"}).reason, "")


class TestWallModuleMissing(unittest.TestCase):
    """Item 4 (test-harness coupling): the wall module is what makes
    this branch free-wall. If it is missing (a checkout on
    free-check-gate, or a partial install), run_guarded must refuse
    with a clear message naming the missing module and the branch —
    not a traceback, and not a misleading "command not found"."""

    def test_run_guarded_without_the_wall_module_refuses_clearly(self):
        import contextlib
        import io
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            policy = policy_for(tmp)
            (Path(tmp) / "note.txt").write_text("hello\n")
            out = io.StringIO()
            with mock.patch.dict(sys.modules, {"fineprint_wall": None}):
                with contextlib.redirect_stdout(out):
                    code = FG.run_guarded(
                        policy, None, ["cat", str(Path(tmp) / "note.txt")],
                        cwd=tmp)
            self.assertEqual(code, FG.EXIT_ERROR)
            self.assertIn("fineprint_wall", out.getvalue())
            self.assertIn("free-wall", out.getvalue())


if __name__ == "__main__":
    unittest.main()
