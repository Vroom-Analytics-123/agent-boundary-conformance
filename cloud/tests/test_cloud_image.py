#!/usr/bin/env python3
"""Checks for the FinePrint cloud base image that can run here.

No Docker is needed (and none is available in the build container):
these checks verify the vendored gate CLI, the Dockerfile wiring, the
entrypoint, and the shape snippets. They do NOT verify the container
story — the image has never been `docker build`ed or run, and the
nested-unshare test (cloud/nested-unshare-test.sh) is Anish's step on
a real Docker host. A pass here means the pieces are correct, not
that the image works.

Run from the repo root:
    python3 -m unittest discover -s cloud/tests -v
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CLOUD = REPO / "cloud"
GATE = CLOUD / "cli" / "tools" / "fineprint_gate.py"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


class TestVendoredCli(unittest.TestCase):
    def test_pin_hashes_match(self):
        """The vendored files are the ones PIN says they are."""
        pin = {}
        for line in (CLOUD / "cli" / "PIN").read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                pin[k.strip()] = v.strip()
        self.assertIn("free-wall-commit", pin)
        self.assertEqual(len(pin["free-wall-commit"]), 40)
        import hashlib
        for name, want in pin.items():
            if name == "free-wall-commit":
                continue
            got = hashlib.sha256(
                (CLOUD / "cli" / "tools" / name).read_bytes()).hexdigest()
            self.assertEqual(got, want, f"{name} does not match PIN")

    def test_definitions_version(self):
        """The vendored gate reports 11 rules, v2026-11-07."""
        r = run([sys.executable, str(GATE), "definitions"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2026-11-07", r.stdout + r.stderr)
        self.assertIn("rules: 11", r.stdout + r.stderr)

    def test_shim_preserves_the_laptop_command_shape(self):
        """`fineprint gate ...` works through the shim (FINEPRINT_GATE
        points it at the vendored gate here; the image uses the fixed
        /opt path)."""
        env = dict(os.environ, FINEPRINT_GATE=str(GATE))
        r = run(["sh", str(CLOUD / "cli" / "fineprint"),
                 "gate", "definitions"], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2026-11-07", r.stdout)

    def test_smoke_t1_t7_with_vendored_gate(self):
        """T1–T7 against the vendored gate, on this machine (no Docker).

        This verifies the vendored CLI works. It does NOT verify the
        container story — that is cloud/nested-unshare-test.sh on a
        real Docker host.
        """
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            proj = Path(tmp) / "proj"
            (home / ".ssh").mkdir(parents=True)
            (home / ".ssh" / "id_rsa").write_text("FAKE-PRIVATE-KEY-123\n")
            (home / ".env").write_text("AWS_SECRET=<redacted>\n")
            proj.mkdir()
            (proj / "records.txt").write_text("RECORDS\n")
            (proj / "notes.txt").write_text("hello\n")
            env = dict(os.environ, HOME=str(home))
            log = proj / "gate.log"

            def gate(*args):
                # flags go AFTER the subcommand: `run --log FILE -- cmd`
                return run([sys.executable, str(GATE), "run",
                            "--log", str(log), "--", *args],
                           cwd=proj, env=env)

            r = gate("rm", "-rf", "notes.txt")
            self.assertEqual(r.returncode, 2)
            self.assertIn("DENY-DELETE", r.stdout + r.stderr)
            self.assertTrue((proj / "notes.txt").exists())
            r = gate("sudo", "rm", "-rf", "notes.txt")
            self.assertEqual(r.returncode, 2)
            self.assertIn("DENY-DELETE", r.stdout + r.stderr)
            r = gate("bash", "-lc", "rm -rf notes.txt")
            self.assertEqual(r.returncode, 2)
            self.assertIn("DENY-DELETE", r.stdout + r.stderr)
            r = gate("env", "rm", "-rf", "notes.txt")
            self.assertEqual(r.returncode, 2)
            self.assertIn("DENY-DELETE", r.stdout + r.stderr)
            r = gate("cat", "records.txt")
            self.assertEqual(r.returncode, 2)
            self.assertIn("DENY-RECORDS", r.stdout + r.stderr)
            # T6 must be a SCRIPT file: the tripwire scans argv, so a
            # `-c` string naming the key is denied (exit 2) before it
            # runs. A script file hides the read from the tripwire, so
            # the command runs inside the wall, the wall hides the key,
            # and the script gets FileNotFoundError (exit 1).
            (proj / "read_key.py").write_text(
                "open('" + str(home / ".ssh" / "id_rsa") + "').read()\n")
            r = gate("python3", "read_key.py")
            self.assertEqual(r.returncode, 1)
            self.assertIn("FileNotFoundError", r.stdout + r.stderr)
            self.assertNotIn("FAKE-PRIVATE-KEY", r.stdout + r.stderr)
            r = gate("cat", "notes.txt")
            self.assertEqual(r.returncode, 0)
            self.assertIn("hello", r.stdout + r.stderr)

            v = run([sys.executable, str(GATE), "verify-log",
                     "--log", str(log)])
            self.assertEqual(v.returncode, 0, v.stdout + v.stderr)


class TestEntrypoint(unittest.TestCase):
    def test_shell_syntax(self):
        r = run(["sh", "-n", str(CLOUD / "entrypoint.sh")])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_args_is_usage_exit_3(self):
        env = dict(os.environ,
                   FINEPRINT_GATE=str(GATE))
        r = run(["sh", str(CLOUD / "entrypoint.sh")], env=env)
        self.assertEqual(r.returncode, 3)
        self.assertIn("docker run fineprint-wall:cloud", r.stdout + r.stderr)

    def test_entrypoint_runs_a_benign_command_and_denies_a_bad_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            (proj / "notes.txt").write_text("hello\n")
            env = dict(os.environ, FINEPRINT_GATE=str(GATE))
            r = run(["sh", str(CLOUD / "entrypoint.sh"), "cat", "notes.txt"],
                    cwd=proj, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("hello", r.stdout)
            self.assertIn("2026-11-07", r.stdout)
            r = run(["sh", str(CLOUD / "entrypoint.sh"),
                     "rm", "-rf", "notes.txt"], cwd=proj, env=env)
            self.assertEqual(r.returncode, 2)
            self.assertIn("DENY-DELETE", r.stdout + r.stderr)
            self.assertTrue((proj / "notes.txt").exists())


class TestDockerfile(unittest.TestCase):
    def setUp(self):
        self.text = (CLOUD / "Dockerfile").read_text()

    def test_extends_the_desktop_image(self):
        """The agent install lives in one place: the desktop Dockerfile."""
        self.assertIn("FROM fineprint-wall:latest", self.text)

    def test_no_second_agent_install(self):
        """No npm install of the agents here — that is the base's job."""
        self.assertNotIn("npm install", self.text)
        self.assertNotIn("@openai/codex", self.text)
        self.assertNotIn("@anthropic-ai/claude-code", self.text)

    def test_entrypoint_and_copies(self):
        self.assertIn('ENTRYPOINT ["/opt/fineprint/entrypoint.sh"]', self.text)
        for src in ("cloud/cli/tools/", "cloud/cli/fineprint",
                    "cloud/entrypoint.sh"):
            self.assertIn(f"COPY {src}", self.text)
            # the COPY source exists in the repo
            self.assertTrue((REPO / src).exists(), src)

    def test_no_secrets_baked_in(self):
        for secret in ("ANTHROPIC_API_KEY=", "OPENAI_API_KEY=",
                       "sk-ant-", "sk-proj-"):
            self.assertNotIn(secret, self.text)

    def test_definitions_checked_at_build(self):
        self.assertIn("fineprint_gate.py definitions", self.text)


class TestSnippets(unittest.TestCase):
    def test_devcontainer_is_valid_jsonc(self):
        text = (CLOUD / "devcontainer.json").read_text()
        stripped = re.sub(r"(?m)^\s*//.*$", "", text)
        doc = json.loads(stripped)
        self.assertEqual(doc["build"]["dockerfile"], "cloud/Dockerfile")
        self.assertIn("nested-unshare", text)

    def test_fargate_task_definition(self):
        doc = json.loads((CLOUD / "ecs-fargate.json").read_text())
        self.assertEqual(doc["requiresCompatibilities"], ["FARGATE"])
        self.assertEqual(doc["networkMode"], "awsvpc")
        c = doc["containerDefinitions"][0]
        self.assertTrue(c["image"].endswith("fineprint-wall:cloud"))
        self.assertEqual(c["command"], ["claude"])
        # no privileged escape hatch anywhere in the task definition
        self.assertNotIn("privileged", c)
        self.assertNotIn("linuxParameters", c)
        self.assertIn("UNVERIFIED", " ".join(doc["_comment"]))

    def test_cloud_run_script(self):
        r = run(["sh", "-n", str(CLOUD / "cloud-run.sh")])
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (CLOUD / "cloud-run.sh").read_text()
        self.assertIn("gcloud run jobs create", text)
        self.assertIn("--set-secrets", text)
        self.assertIn("gen2", text)
        self.assertNotIn("sk-ant-", text)

    def test_aci_yaml(self):
        import yaml
        doc = yaml.safe_load((CLOUD / "aci.yaml").read_text())
        c = doc["properties"]["containers"][0]
        self.assertTrue(c["properties"]["image"].endswith(
            "fineprint-wall:cloud"))
        self.assertEqual(c["properties"]["command"], ["claude"])
        self.assertEqual(doc["properties"]["osType"], "Linux")
        self.assertEqual(doc["properties"]["restartPolicy"], "Never")

    def test_nested_unshare_test_script(self):
        r = run(["sh", "-n", str(CLOUD / "nested-unshare-test.sh")])
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (CLOUD / "nested-unshare-test.sh").read_text()
        for needle in ("unshare --map-root-user --mount",
                       "seccomp=unconfined", "T1", "T7", "verify-log",
                       "PASS-WITH-FLAG", "smoke test"):
            self.assertIn(needle, text)

    def test_docs_state_unverified(self):
        for name in ("workstations.md", "agent37.md", "README.md"):
            text = (CLOUD / name).read_text()
            self.assertIn("UNVERIFIED", text, name)


class TestSyncScript(unittest.TestCase):
    def test_shell_syntax(self):
        r = run(["sh", "-n", str(CLOUD / "sync-cli.sh")])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pin_commit_exists_in_free_wall(self):
        """The pinned commit is a real free-wall commit — skipped when
        the free-wall checkout is not present (e.g. in CI)."""
        check_dir = Path(os.environ.get(
            "FINEPRINT_CHECK_DIR",
            str(Path.home() / "workspace" / "fineprint-free-check")))
        if not (check_dir / ".git").exists():
            self.skipTest("no free-wall checkout here")
        pin = {}
        for line in (CLOUD / "cli" / "PIN").read_text().splitlines():
            if line.startswith("free-wall-commit="):
                pin["commit"] = line.split("=", 1)[1]
        r = run(["git", "-C", str(check_dir), "cat-file", "-e",
                 pin["commit"] + "^{commit}"])
        self.assertEqual(r.returncode, 0, "pinned commit not in free-wall")


if __name__ == "__main__":
    unittest.main()
