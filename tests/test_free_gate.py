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


class TestProbe(unittest.TestCase):
    """`gate probe` — the three syscalls the wall needs, in order
    (KiroCrew's probe shape: their entrypoint probes on first run and
    reports 'no usable backend', fail-closed). A pass here is the
    wall's own precondition, because each step runs the real `unshare`
    binary — the same primitive the wall uses."""

    def test_probe_passes_where_the_wall_runs(self):
        # Live: unshare + mount work in this container (the wall
        # tests prove it), so the probe must pass here.
        proc = subprocess.run(
            [sys.executable, str(FINEPRINT), "gate", "probe"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout
        self.assertIn("1 unshare(CLONE_NEWUSER): PASS", out)
        self.assertIn("2 unshare(CLONE_NEWNS): PASS", out)
        self.assertIn("3 mount (remount / private inside the "
                      "namespaces): PASS", out)
        self.assertIn("probe: PASS", out)

    def test_probe_reports_the_cap_drop(self):
        proc = subprocess.run(
            [sys.executable, str(FINEPRINT), "gate", "probe"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("cap-drop:", proc.stdout)
        # setpriv exists in this container (the wall tests rely on it).
        self.assertIn("setpriv", proc.stdout)

    def test_probe_fails_closed_without_unshare(self):
        # No `unshare` on PATH: the probe refuses (exit 3) rather
        # than reporting a pass the wall could not honour.
        import os
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PATH=tmp)
            proc = subprocess.run(
                [sys.executable, str(FINEPRINT), "gate", "probe"],
                capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 3,
                             proc.stdout + proc.stderr)
            self.assertIn("unshare", proc.stdout)
            self.assertIn("not on PATH", proc.stdout)


class TestSecondOpinion(unittest.TestCase):
    """Nov 8 (two-stage gate): the second opinion (bekko) fires only
    when the deterministic checks allowed, only for serious
    invariants (severity >= the policy threshold), and fails closed
    when the model cannot be consulted. The model is injected here
    (a fake), so the unit suite never starts a model — the real
    model is exercised by tests/test_second_opinion_live.py."""

    class FakeClient:
        """A stand-in for SecondOpinion: returns a canned verdict
        and counts calls, so the tests pin the gate's behaviour
        around the model, not the model's behaviour."""

        def __init__(self, verdict="allow", reason="no rule is at stake",
                     probability_yes=0.1, latency_s=0.5):
            self.verdict = verdict
            self.reason = reason
            self.probability_yes = probability_yes
            self.latency_s = latency_s
            self.calls = []

        def judge(self, action, family, reason):
            self.calls.append((action, family, reason))
            return {"verdict": self.verdict, "reason": self.reason,
                    "probability_yes": self.probability_yes,
                    "latency_s": self.latency_s,
                    "model": "bekko-system-one-v0-400m",
                    "version": "1960df56"}

        def stop(self):
            pass

    class FailingClient:
        """A stand-in for a model that cannot be consulted."""

        def __init__(self):
            self.calls = []

        def judge(self, action, family, reason):
            self.calls.append((action, family, reason))
            raise FG.SecondOpinionError("the model did not answer")

        def stop(self):
            pass

    def _gate(self, tmp, client, threshold=4, second_opinion=True):
        log_path = Path(tmp) / "audit.jsonl"
        log = FG.AuditLog(str(log_path))
        p = FG.Policy((str(tmp),), (), mode="deny",
                      second_opinion=second_opinion,
                      second_opinion_threshold=threshold)
        return FG.Gate(p, log, second_opinion_client=client), log_path

    def _log_entries(self, log_path):
        if not log_path.exists():
            return []
        return [json.loads(line) for line in
                log_path.read_text().splitlines() if line.strip()]

    def test_disabled_by_default_no_model_call(self):
        # The default policy does not enable the second opinion:
        # the model is never consulted and the Stage 1 allow stands.
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FakeClient(verdict="block")
            g, log_path = self._gate(tmp, fake, second_opinion=False)
            d = g.second_opinion(["cp", "a.txt", "b.txt"],
                                 "exfiltration", "some reason")
            self.assertTrue(d.allowed)
            self.assertEqual(fake.calls, [])
            self.assertEqual(self._log_entries(log_path), [])

    def test_benign_never_escalates(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FakeClient(verdict="block")
            g, _ = self._gate(tmp, fake)
            d = g.second_opinion(["cat", "notes.txt"], "benign",
                                 "no invariant is at stake")
            self.assertTrue(d.allowed)
            self.assertEqual(fake.calls, [])

    def test_deploy_below_default_threshold_but_not_below_2(self):
        # Deploy (severity 2) does not escalate at the default
        # threshold of 4 — but does at threshold 2 (the policy
        # threshold is the dial, not a hardcoded family list).
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FakeClient(verdict="block")
            g, _ = self._gate(tmp, fake, threshold=4)
            d = g.second_opinion(["kubectl", "apply", "-f", "x.yaml"],
                                 "deploy", "a deploy ships code")
            self.assertTrue(d.allowed)
            self.assertEqual(fake.calls, [])
            g2, _ = self._gate(tmp, fake, threshold=2)
            d2 = g2.second_opinion(["kubectl", "apply", "-f", "x.yaml"],
                                   "deploy", "a deploy ships code")
            self.assertFalse(d2.allowed)
            self.assertEqual(len(fake.calls), 1)

    def test_model_block_denies_with_s1_rule_and_log_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FakeClient(verdict="block",
                                   reason="the file is a credential",
                                   probability_yes=0.93, latency_s=6.1)
            g, log_path = self._gate(tmp, fake)
            d = g.second_opinion(["curl", "https://x.example/f"],
                                 "exfiltration", "reason seen")
            self.assertFalse(d.allowed)
            self.assertEqual(d.rule, "S1-BLOCK-bekko")
            entries = self._log_entries(log_path)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertFalse(e["allowed"])
            self.assertFalse(e["deterministic"])
            self.assertTrue(e["second_opinion"])
            self.assertEqual(e["model"], "bekko-system-one-v0-400m")
            self.assertEqual(e["model_version"], "1960df56")
            self.assertEqual(e["invariant"], "exfiltration")
            self.assertEqual(e["reason_seen"], "reason seen")
            self.assertEqual(e["model_verdict"], "block")
            self.assertEqual(e["model_reason"],
                             "the file is a credential")
            self.assertEqual(e["latency_s"], 6.1)
            self.assertEqual(e["rule"], "S1-BLOCK-bekko")

    def test_model_allow_allows_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FakeClient(verdict="allow",
                                   reason="plain listing, no risk",
                                   probability_yes=0.05, latency_s=4.4)
            g, log_path = self._gate(tmp, fake)
            d = g.second_opinion(["rm", "scratch.txt"],
                                 "deletion", "reason seen")
            self.assertTrue(d.allowed)
            entries = self._log_entries(log_path)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertTrue(e["allowed"])
            self.assertTrue(e["second_opinion"])
            self.assertEqual(e["model_verdict"], "allow")
            self.assertEqual(e["model_reason"],
                             "plain listing, no risk")
            self.assertEqual(e["invariant"], "deletion")

    def test_model_error_blocks_fail_closed(self):
        # A model that cannot be consulted blocks (exit 2, a
        # model-error rule), never silently allows — and the log
        # says it is a model error, not a rule denial.
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FailingClient()
            g, log_path = self._gate(tmp, fake)
            d = g.second_opinion(["cp", "a.txt", "b.txt"],
                                 "exfiltration", "reason seen")
            self.assertFalse(d.allowed)
            self.assertEqual(d.rule, "S1-MODEL-ERROR")
            entries = self._log_entries(log_path)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertFalse(e["allowed"])
            self.assertFalse(e["deterministic"])
            self.assertTrue(e["second_opinion"])
            self.assertTrue(e["model_error"])
            self.assertEqual(e["rule"], "S1-MODEL-ERROR")

    def test_family_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.FakeClient()
            g, _ = self._gate(tmp, fake)
            cases = [
                (["rm", "scratch.txt"], "deletion"),
                (["shred", "-u", "f"], "deletion"),
                (["unlink", "f"], "deletion"),
                (["curl", "https://x.example/f"], "exfiltration"),
                (["scp", "a", "b@h:c"], "exfiltration"),
                (["kubectl", "apply", "-f", "x.yaml"], "deploy"),
                (["git", "push", "--force"], "deploy"),
                (["npm", "run", "deploy"], "deploy"),
                (["mydeploy", "x"], "deploy"),
                (["cat", "notes.txt"], "benign"),
                (["ls", "-la"], "benign"),
            ]
            for argv, family in cases:
                got, reason = g.escalation_family(argv)
                self.assertEqual(got, family, argv)
            # The reason the model sees is the rule's reason, from
            # the definitions in force — not a hardcoded string.
            _, reason = g.escalation_family(["rm", "x"])
            self.assertIn("a recursive delete destroys work with no undo",
                          reason)

    def test_audit_log_deterministic_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = FG.AuditLog(str(path))
            p = FG.Policy((str(tmp),), (), mode="deny")
            g = FG.Gate(p, log)
            # Default: a denial is deterministic. (.env is denied
            # in deny mode; /etc/passwd is not — the denylist only
            # blocks known-bad paths.)
            env = Path(tmp) / ".env"
            env.write_text("x\n")
            g.evaluate(FG.Action("file_read", str(env)))
            # Explicit False: a second-opinion denial is not.
            d = FG.Decision(False, "second opinion: blocked",
                            rule="S1-BLOCK-bekko")
            log.append(FG.Action("exec", "cp a b"), d,
                       deterministic=False,
                       extra={"second_opinion": True})
            entries = self._log_entries(path)
            self.assertTrue(entries[0]["deterministic"])
            self.assertFalse(entries[1]["deterministic"])

    def test_synthetic_rule_ids_declared_not_in_pack(self):
        import fineprint_definitions as D
        declared = [r["id"] for r in D.SYNTHETIC_RULES]
        self.assertIn("S1-BLOCK-bekko", declared)
        self.assertIn("S1-MODEL-ERROR", declared)
        # The pack itself is unchanged: 11 rules, v2026-11-07.
        version, rules, _ = D.load_definitions()
        self.assertEqual(version, "2026-11-07")
        self.assertEqual(len(rules), 11)
        self.assertNotIn("S1-BLOCK-bekko", [r["id"] for r in rules])

    def test_policy_second_opinion_round_trip(self):
        doc = {"mode": "deny", "allowed_paths": ["/tmp"],
               "second_opinion": True, "second_opinion_threshold": 2,
               "second_opinion_timeout": 30.0,
               "second_opinion_start_timeout": 120.0}
        p = FG.Policy.from_dict(doc)
        self.assertTrue(p.second_opinion)
        self.assertEqual(p.second_opinion_threshold, 2)
        self.assertEqual(p.second_opinion_timeout, 30.0)
        self.assertEqual(p.second_opinion_start_timeout, 120.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gate.json"
            path.write_text(json.dumps(doc))
            p2 = FG.Policy.from_file(str(path))
            self.assertTrue(p2.second_opinion)
            self.assertEqual(p2.second_opinion_threshold, 2)

    def test_render_log_entry_second_opinion(self):
        block = {"action": {"kind": "exec", "target": "cp a b"},
                 "allowed": False, "second_opinion": True,
                 "model": "bekko-system-one-v0-400m",
                 "model_version": "1960df56",
                 "model_reason": "the file is a credential"}
        rendered = FG._render_log_entry(block)
        self.assertIn("second opinion", rendered)
        self.assertIn("probabilistic", rendered)
        self.assertIn("bekko-system-one-v0-400m", rendered)
        allow = dict(block, allowed=True,
                     model_reason="plain listing, no risk")
        self.assertIn("allowed", FG._render_log_entry(allow))
        self.assertIn("second opinion", FG._render_log_entry(allow))
        error = dict(block, model_error=True,
                     model_reason="the model did not answer")
        self.assertIn("fail-closed", FG._render_log_entry(error))

    def test_second_opinion_client_protocol_with_fake_helper(self):
        # The real SecondOpinion client (subprocess protocol: start,
        # ready line, one JSON request/response, stop) against a fake
        # helper script — so the protocol is exercised without a
        # model. This is the test that would have caught the missing
        # `time` import in _readline.
        import os
        script = (
            "import json, sys\n"
            "print(json.dumps({'ready': True, 'model': 'fake',\n"
            "                  'version': 'test'}), flush=True)\n"
            "for line in sys.stdin:\n"
            "    req = json.loads(line)\n"
            "    print(json.dumps({'verdict': 'block',\n"
            "                      'reason': 'fake says block',\n"
            "                      'probability_yes': 0.9,\n"
            "                      'latency_s': 0.01,\n"
            "                      'model': 'fake',\n"
            "                      'version': 'test'}), flush=True)\n")
        with tempfile.TemporaryDirectory() as tmp:
            helper = Path(tmp) / "fake_helper.py"
            helper.write_text(script)
            client = FG.SecondOpinion(python=sys.executable,
                                      helper=str(helper))
            try:
                resp = client.judge("rm scratch.txt", "deletion",
                                    "a reason")
                self.assertEqual(resp["verdict"], "block")
                self.assertEqual(resp["reason"], "fake says block")
                self.assertEqual(client.version, "test")
                # A second call reuses the same (already started)
                # helper — one load per run, not one per action.
                resp2 = client.judge("rm other.txt", "deletion",
                                     "a reason")
                self.assertEqual(resp2["verdict"], "block")
                self.assertIsNotNone(client.proc)
            finally:
                client.stop()
            self.assertIsNone(client.proc)
            # And through the Gate: the fake helper's block becomes
            # a second-opinion denial with the S1 rule id.
            client2 = FG.SecondOpinion(python=sys.executable,
                                       helper=str(helper))
            g, log_path = self._gate(tmp, client2)
            try:
                d = g.second_opinion(["rm", "scratch.txt"],
                                     "deletion", "a reason")
                self.assertFalse(d.allowed)
                self.assertEqual(d.rule, "S1-BLOCK-bekko")
            finally:
                g.close()

    def test_run_guarded_stage1_denial_never_consults_model(self):
        # A Stage 1 denial (rm -rf) never reaches the model: the
        # second opinion only fires when the deterministic checks
        # allowed.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "victim.txt"
            target.write_text("keep me\n")
            fake = self.FakeClient(verdict="allow")
            g, _ = self._gate(tmp, fake)
            code = FG.run_guarded(g.policy, g.log,
                                  ["rm", "-rf", str(target)],
                                  cwd=tmp, wall=False, gate=g)
            self.assertEqual(code, FG.EXIT_DENY)
            self.assertEqual(fake.calls, [])
            self.assertTrue(target.exists())

    def test_run_guarded_stage1_allow_exfil_model_block_no_run(self):
        # Stage 1 allows a plain cp of a normal file; the second
        # opinion blocks it — exit 2 and the copy never happens.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "notes.txt"
            src.write_text("hello\n")
            dest = Path(tmp) / "copy.txt"
            fake = self.FakeClient(verdict="block",
                                   reason="copying out is exfiltration")
            g, log_path = self._gate(tmp, fake)
            code = FG.run_guarded(g.policy, g.log,
                                  ["cp", str(src), str(dest)],
                                  cwd=tmp, wall=False, gate=g)
            self.assertEqual(code, FG.EXIT_DENY)
            self.assertEqual(len(fake.calls), 1)
            self.assertFalse(dest.exists())
            entries = self._log_entries(log_path)
            self.assertTrue(any(e.get("rule") == "S1-BLOCK-bekko"
                                for e in entries))

    def test_run_guarded_stage1_allow_model_allow_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "notes.txt"
            src.write_text("hello\n")
            dest = Path(tmp) / "copy.txt"
            fake = self.FakeClient(verdict="allow",
                                   reason="a normal file, no risk")
            g, _ = self._gate(tmp, fake)
            code = FG.run_guarded(g.policy, g.log,
                                  ["cp", str(src), str(dest)],
                                  cwd=tmp, wall=False, gate=g)
            self.assertEqual(code, FG.EXIT_ALLOW)
            self.assertEqual(len(fake.calls), 1)
            self.assertTrue(dest.exists())


if __name__ == "__main__":
    unittest.main()
