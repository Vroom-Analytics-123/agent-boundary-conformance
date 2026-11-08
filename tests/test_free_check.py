"""Tests for the free Check CLI (`fineprint`, repo root).

TDD: these tests were written BEFORE the CLI existed. They cover the
contract in the free-tier brief: init scaffolds, check exit codes
(0 pass / 2 BLOCKED / 3 unknown-error), bundle seal + verify round-trip,
the muse-code no-decision-source path, the smoke step, and the
fresh-tree end-to-end (clone -> check a real harness config -> BLOCKED
on a violating policy -> gate denies a disallowed read).

Stdlib only (unittest under pytest, like the rest of tests/).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FINEPRINT = REPO / "fineprint"
sys.path.insert(0, str(REPO / "tools"))
import check_bundle as CB  # noqa: E402

CODE_X_POLICY = REPO / "fixtures" / "policies" / "default.rules"
CLAUDE_POLICY = REPO / "adapters" / "claude-code" / "policy" / "settings.json"
DEMO_BINDINGS = REPO / "evidence" / "demo-check-2026-10-22" / "bindings.json"

VIOLATING_RULES = """prefix_rule(pattern=["git", "status"], decision="allow")
prefix_rule(pattern=["rm", "-rf"], decision="allow")
prefix_rule(pattern=["rm", "-fr"], decision="allow")
prefix_rule(pattern=["rm", "--recursive", "--force"], decision="allow")
"""


def run_cli(*args, cwd=None, timeout=300):
    return subprocess.run([sys.executable, str(FINEPRINT), *args],
                          capture_output=True, text=True, cwd=cwd,
                          timeout=timeout)


class TestHelp(unittest.TestCase):
    def test_help_lists_subcommands(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for sub in ("init", "check", "verify", "report", "gate", "harnesses"):
            self.assertIn(sub, proc.stdout)

    def test_harnesses_lists_three(self):
        proc = run_cli("harnesses")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in ("codex", "claude-code", "muse-code"):
            self.assertIn(name, proc.stdout)


class TestInit(unittest.TestCase):
    def test_init_codex_scaffolds_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", "--harness", "codex", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rules = Path(tmp) / "fineprint.rules"
            self.assertTrue(rules.exists())
            self.assertIn("prefix_rule", rules.read_text())
            self.assertIn("check", proc.stdout)

    def test_init_claude_scaffolds_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", "--harness", "claude-code", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            settings = Path(tmp) / "fineprint.settings.json"
            self.assertTrue(settings.exists())
            doc = json.loads(settings.read_text())
            self.assertIn("permissions", doc)

    def test_init_muse_code_writes_note_not_policy(self):
        # Muse Code has no local policy file to scaffold (see
        # adapters/muse-code-assessment.md). init must say so plainly and
        # point at the live smoke route, never invent a policy file.
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", "--harness", "muse-code", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            note = Path(tmp) / "fineprint-muse-code.json"
            self.assertTrue(note.exists())
            doc = json.loads(note.read_text())
            self.assertIn("no local policy file", json.dumps(doc).lower()
                          + proc.stdout.lower())
            self.assertIn("smoke", proc.stdout.lower())

    def test_init_rules_scaffolds_diy_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", "--rules", "my-rules.json", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            pack = Path(tmp) / "my-rules.json"
            self.assertTrue(pack.exists())
            entries = json.loads(pack.read_text())["entries"]
            self.assertTrue(entries)
            self.assertEqual(entries[0]["measurement_status"], "UNMEASURED")
            self.assertTrue(entries[0]["probe_families"])

    def test_init_gate_scaffolds_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", "--gate", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            policy = Path(tmp) / "fineprint-gate.json"
            self.assertTrue(policy.exists())
            doc = json.loads(policy.read_text())
            self.assertIn("allowed_paths", doc)
            self.assertIn("allowed_hosts", doc)


class TestCheck(unittest.TestCase):
    def test_check_claude_fp001_exit_0_and_bundle_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ev"
            proc = run_cli("check", "--harness", "claude-code",
                           "--policy", str(CLAUDE_POLICY),
                           "--only", "FP-001", "--out", str(out),
                           "--no-smoke", cwd=tmp)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")
            bundle = json.loads((out / "bundle.json").read_text())
            self.assertEqual(bundle["schema_version"], "check-run-bundle.v1")
            self.assertEqual(CB.verify_check_bundle(bundle), [])

    def test_check_codex_violating_policy_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "violating.rules"
            bad.write_text(VIOLATING_RULES)
            proc = run_cli("check", "--harness", "codex",
                           "--policy", str(bad),
                           "--only", "FP-001", "--out", str(Path(tmp) / "ev"),
                           "--no-smoke", cwd=tmp)
            self.assertEqual(proc.returncode, 2,
                             f"{proc.stdout}\n{proc.stderr}")
            self.assertIn("BLOCKED", proc.stdout)
            self.assertIn("FP-001", proc.stdout)

    def test_check_baseline_regression_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bad = tmp / "violating.rules"
            bad.write_text(VIOLATING_RULES)
            base = tmp / "base"
            proc1 = run_cli("check", "--harness", "codex",
                            "--policy", str(CODE_X_POLICY),
                            "--only", "FP-001", "--out", str(base),
                            "--no-smoke", cwd=tmp)
            self.assertEqual(proc1.returncode, 0,
                             f"{proc1.stdout}\n{proc1.stderr}")
            proc2 = run_cli("check", "--harness", "codex",
                            "--policy", str(bad),
                            "--only", "FP-001", "--out", str(tmp / "fresh"),
                            "--baseline", str(base / "bundle.json"),
                            "--no-smoke", cwd=tmp)
            self.assertEqual(proc2.returncode, 2,
                             f"{proc2.stdout}\n{proc2.stderr}")
            diff = json.loads((tmp / "fresh" / "baseline-diff.json")
                              .read_text())
            self.assertGreaterEqual(diff["regression_count"], 1)

    def test_check_muse_code_exit_3_unmeasured(self):
        # No offline decision oracle exists for Muse Code. The CLI must
        # report UNMEASURED (exit 3), never a fabricated verdict.
        with tempfile.TemporaryDirectory() as tmp:
            run_cli("init", "--harness", "muse-code", cwd=tmp)
            out = Path(tmp) / "ev"
            proc = run_cli("check", "--harness", "muse-code",
                           "--policy", str(Path(tmp) / "fineprint-muse-code.json"),
                           "--only", "FP-001", "--out", str(out),
                           "--no-smoke", cwd=tmp)
            self.assertEqual(proc.returncode, 3,
                             f"{proc.stdout}\n{proc.stderr}")
            self.assertIn("no decision source", proc.stdout.lower())
            bundle = json.loads((out / "bundle.json").read_text())
            self.assertEqual(CB.verify_check_bundle(bundle), [])
            # Every probe carries the unsupported-adapter attribution.
            self.assertIn("unsupported-adapter",
                          json.dumps(bundle["invariant_results"]))
            self.assertEqual(
                bundle["claim_scope"]["measured_satisfied"], 0)

    def test_check_unknown_harness_exit_3(self):
        proc = run_cli("check", "--harness", "nosuch",
                       "--policy", str(CODE_X_POLICY))
        self.assertEqual(proc.returncode, 3)

    def test_check_missing_policy_exit_3(self):
        proc = run_cli("check", "--harness", "codex",
                       "--policy", "/nonexistent/fineprint.rules")
        self.assertEqual(proc.returncode, 3)

    def test_smoke_runs_by_default_and_can_be_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ev"
            proc = run_cli("check", "--harness", "claude-code",
                           "--policy", str(CLAUDE_POLICY),
                           "--only", "FP-001", "--out", str(out), cwd=tmp)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")
            self.assertIn("smoke:", proc.stdout.lower())
            self.assertTrue((out / "smoke" / "bundle.json").exists())
            out2 = Path(tmp) / "ev2"
            proc2 = run_cli("check", "--harness", "claude-code",
                            "--policy", str(CLAUDE_POLICY),
                            "--only", "FP-001", "--out", str(out2),
                            "--no-smoke", cwd=tmp)
            self.assertEqual(proc2.returncode, 0)
            self.assertNotIn("smoke:", proc2.stdout.lower())


class TestZeroConfig(unittest.TestCase):
    """Simplicity acceptance: one command, zero config, first verdict.

    A junior developer on day one gets a verdict with a bundle in five
    minutes, one command, no config."""

    def test_two_runs_in_same_second_do_not_share_an_out_dir(self):
        # Regression: two checks in the same second used to write into
        # the same check-<ts> directory, the second overwriting the
        # first run's sealed bundle. Each run must get its own dir.
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "repo"
            tree.mkdir()
            shutil.copy(REPO / "fineprint", tree / "fineprint")
            for rel in ("tools", "fixtures", "adapters", "docs/catalogue",
                        "evidence/demo-check-2026-10-22"):
                shutil.copytree(REPO / rel, tree / rel,
                                ignore=shutil.ignore_patterns("codex"))
            shutil.copy(REPO / "adapters/claude-code/policy/settings.json",
                        tree / "fineprint.settings.json")
            env = dict(os.environ)
            env["PATH"] = f"{REPO}:{env.get('PATH', '')}"
            for _ in range(2):
                proc = subprocess.run(
                    ["python3", "fineprint", "check", "--no-smoke"],
                    cwd=tree, env=env, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stdout)
            dirs = sorted((tree / "fineprint-evidence").glob("check-*"))
            self.assertEqual(len(dirs), 2, [d.name for d in dirs])
            self.assertTrue(all((d / "bundle.json").is_file() for d in dirs))
            ids = {json.loads((d / "bundle.json").read_text())["bundle_id"]
                   for d in dirs}
            self.assertEqual(len(ids), 2)

    def test_check_zero_config_in_repo_clone(self):
        # Fresh clone -> ./fineprint check (no args) -> verdict + bundle.
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "repo"
            tree.mkdir()
            shutil.copy(REPO / "fineprint", tree / "fineprint")
            for rel in ("tools", "fixtures", "adapters", "docs/catalogue",
                        "evidence/demo-check-2026-10-22"):
                # A real clone has no vendored oracle binary (git-ignored,
                # 258 MB; restored separately). Exclude it so the copy
                # fits the 512 MB /tmp.
                shutil.copytree(REPO / rel, tree / rel,
                                ignore=shutil.ignore_patterns("codex"))
            proc = subprocess.run(
                [sys.executable, str(tree / "fineprint"), "check"],
                capture_output=True, text=True, cwd=tree, timeout=300)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")
            bundles = list((tree / "fineprint-evidence").glob(
                "check-*/bundle.json"))
            self.assertEqual(len(bundles), 1, bundles)
            bundle = json.loads(bundles[0].read_text())
            self.assertEqual(CB.verify_check_bundle(bundle), [])
            self.assertIn("auto-detected", proc.stdout.lower())

    def test_check_zero_config_empty_dir_points_at_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("check", cwd=tmp)
            self.assertEqual(proc.returncode, 3)
            self.assertIn("fineprint init", proc.stdout)

    def test_check_detects_dot_claude_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_dir = Path(tmp) / ".claude"
            settings_dir.mkdir()
            shutil.copy(CLAUDE_POLICY, settings_dir / "settings.json")
            proc = run_cli("check", cwd=tmp)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")
            self.assertIn("claude-code", proc.stdout)

    def test_init_then_check_two_command_flow(self):
        # No harness config at all: init (one command, no flags) then
        # check (one command, no flags) -> verdict + bundle.
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = run_cli("check", cwd=tmp)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")
            bundles = list((Path(tmp) / "fineprint-evidence").glob(
                "check-*/bundle.json"))
            self.assertEqual(len(bundles), 1, bundles)
            self.assertEqual(CB.verify_check_bundle(
                json.loads(bundles[0].read_text())), [])

    def test_starter_rules_pass_their_own_check(self):
        # The scaffolded policy must pass FP-016 (the benign read
        # control): a starter that fails its own check teaches the
        # wrong lesson.
        with tempfile.TemporaryDirectory() as tmp:
            run_cli("init", "--harness", "codex", cwd=tmp)
            self.assertIn("/records/health",
                          (Path(tmp) / "fineprint.rules").read_text())
            proc = run_cli("check", "--harness", "codex",
                           "--only", "FP-016", "--no-smoke", cwd=tmp)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")

    def test_init_bare_scaffolds_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli("init", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for name in ("fineprint.rules", "fineprint.settings.json",
                         "fineprint-muse-code.json", "fineprint-gate.json"):
                self.assertTrue((Path(tmp) / name).exists(), name)


class TestVerifyReport(unittest.TestCase):
    def _checked_bundle(self, tmp):
        out = Path(tmp) / "ev"
        proc = run_cli("check", "--harness", "claude-code",
                       "--policy", str(CLAUDE_POLICY),
                       "--only", "FP-001", "--out", str(out),
                       "--no-smoke", cwd=tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return out / "bundle.json"

    def test_verify_valid_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._checked_bundle(tmp)
            proc = run_cli("verify", str(bundle))
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("valid", proc.stdout.lower())

    def test_verify_tampered_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._checked_bundle(tmp)
            doc = json.loads(bundle.read_text())
            doc["findings"][0]["actual_decision"] = "allow"
            bad = Path(tmp) / "tampered.json"
            bad.write_text(json.dumps(doc))
            proc = run_cli("verify", str(bad))
            self.assertEqual(proc.returncode, 2, proc.stdout)

    def test_report_renders_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._checked_bundle(tmp)
            proc = run_cli("report", str(bundle))
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("FP-001", proc.stdout)
            self.assertIn("bundle", proc.stdout.lower())


class TestFreshTreeEndToEnd(unittest.TestCase):
    """Simulated fresh clone: only the files a clone would contain,
    no repo-root cwd. init -> check a real harness config -> BLOCKED
    on a violating policy -> gate denies a disallowed read."""

    def test_fresh_tree_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "repo"
            tree.mkdir()
            for rel in ("fineprint",):
                shutil.copy(REPO / rel, tree / rel)
            for rel in ("tools", "fixtures", "adapters", "docs/catalogue",
                        "evidence/demo-check-2026-10-22"):
                # A real clone has no vendored oracle binary (git-ignored,
                # 258 MB; restored separately). Exclude it so the copy
                # fits the 512 MB /tmp.
                shutil.copytree(REPO / rel, tree / rel,
                                ignore=shutil.ignore_patterns("codex"))
            work = Path(tmp) / "work"
            work.mkdir()
            cli = [sys.executable, str(tree / "fineprint")]
            # install: stdlib only, nothing to install.
            proc = subprocess.run(cli + ["--help"], capture_output=True,
                                  text=True, cwd=work)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = subprocess.run(cli + ["init", "--harness", "claude-code"],
                                  capture_output=True, text=True, cwd=work)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = subprocess.run(
                cli + ["init", "--gate"], capture_output=True, text=True,
                cwd=work)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # check a real harness config (the scaffolded settings file).
            proc = subprocess.run(
                cli + ["check", "--harness", "claude-code",
                       "--only", "FP-001", "--no-smoke"],
                capture_output=True, text=True, cwd=work)
            self.assertEqual(proc.returncode, 0,
                             f"{proc.stdout}\n{proc.stderr}")
            # BLOCKED on a violating policy (codex needs the oracle;
            # the vendored binary is part of the tree only when restored
            # — this step uses the claude-code adapter with a violating
            # settings file instead: allow everything).
            bad_settings = json.loads(
                (work / "fineprint.settings.json").read_text())
            bad_settings["permissions"] = {"allow": ["Bash(*)"]}
            bad_path = work / "bad.settings.json"
            bad_path.write_text(json.dumps(bad_settings))
            proc = subprocess.run(
                cli + ["check", "--harness", "claude-code",
                       "--policy", str(bad_path),
                       "--only", "FP-001", "--no-smoke"],
                capture_output=True, text=True, cwd=work)
            self.assertEqual(proc.returncode, 2,
                             f"{proc.stdout}\n{proc.stderr}")
            self.assertIn("BLOCKED", proc.stdout)
            # gate denies a disallowed read (a protected file — the
            # denylist default; confinement would deny /etc/passwd).
            secret = work / ".env"
            secret.write_text("AWS_SECRET=x\n")
            proc = subprocess.run(
                cli + ["gate", "check", "--file", str(secret),
                       "--policy", str(work / "fineprint-gate.json")],
                capture_output=True, text=True, cwd=work)
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("deny", proc.stdout.lower() + proc.stderr.lower())
            self.assertIn("DENY-CRED-ENV", proc.stdout)


if __name__ == "__main__":
    unittest.main()
