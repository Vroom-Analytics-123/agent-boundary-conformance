"""Tests for the free wall — antivirus-for-agents default + opt-in confinement.

TDD: the default policy is a PROTECTIVE DENYLIST (blocks known-dangerous
patterns from Catalogue v1 + our discovered issues; normal work anywhere
is allowed by default). Folder confinement (allowlist to certain folders)
is OPT-IN via `--confine` / policy "mode": "confine".

The tripwire keeps its deny posture for what it scans; the wall is the
enforcement. A command that bypasses argv scanning (a script that reads
a protected file without naming it) must still be denied by the wall.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

CLI = [sys.executable, str(REPO / "fineprint")]


def run_cli(args, cwd, env=None, timeout=120):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(CLI + args, cwd=str(cwd), env=full_env,
                          capture_output=True, text=True, timeout=timeout)


def write_script(path, body):
    Path(path).write_text(body)


class WallTestCase(unittest.TestCase):
    """A temp home (with a fake SSH key + .env) and a temp project dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.proj = Path(self.tmp.name) / "proj"
        (self.home / ".ssh").mkdir(parents=True)
        (self.home / ".ssh" / "id_rsa").write_text("FAKE-PRIVATE-KEY-123\n")
        (self.home / ".env").write_text("AWS_SECRET=FAKESECRET\n")
        (self.home / "normal.txt").write_text("just a normal file\n")
        self.proj.mkdir(parents=True)
        (self.proj / "notes.txt").write_text("hello\n")
        self.env = {"HOME": str(self.home)}

    def tearDown(self):
        self.tmp.cleanup()


class TestDenylistDefault(WallTestCase):
    def test_default_policy_is_denylist(self):
        import fineprint_gate as G
        policy, note = G.default_policy()
        self.assertEqual(policy.mode, "deny")
        self.assertIn("denylist", note.lower())

    def test_tripwire_denies_ssh_key_read(self):
        r = run_cli(["gate", "check", "--file",
                     str(self.home / ".ssh" / "id_rsa")],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-CRED-SSH", r.stdout + r.stderr)

    def test_tripwire_denies_env_file(self):
        r = run_cli(["gate", "check", "--file", str(self.home / ".env")],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-CRED-ENV", r.stdout + r.stderr)

    def test_tripwire_denies_records_file(self):
        r = run_cli(["gate", "check", "--file",
                     str(self.proj / "records.txt")],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-RECORDS", r.stdout + r.stderr)

    def test_tripwire_denies_destructive_delete(self):
        r = run_cli(["gate", "run", "--", "rm", "-rf", "notes.txt"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-DELETE", r.stdout + r.stderr)
        self.assertTrue((self.proj / "notes.txt").exists())

    def test_tripwire_denies_unlink_bypass(self):
        r = run_cli(["gate", "run", "--", "unlink", "notes.txt"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-UNLINK", r.stdout + r.stderr)

    def test_tripwire_denies_deploy(self):
        r = run_cli(["gate", "run", "--", "./deploy.sh"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-DEPLOY", r.stdout + r.stderr)

    def test_tripwire_denies_exfil_of_protected_file(self):
        r = run_cli(["gate", "run", "--", "cp",
                     str(self.home / ".ssh" / "id_rsa"), "/tmp/x"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY-EXFIL", r.stdout + r.stderr)

    def test_tripwire_allows_normal_work_anywhere(self):
        # Normal work anywhere is allowed by default — even outside
        # the project directory.
        r = run_cli(["gate", "check", "--file", str(self.home / "normal.txt")],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("ALLOW", r.stdout + r.stderr)
        r = run_cli(["gate", "run", "--", "cat", str(self.home / "normal.txt")],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("just a normal file", r.stdout)

    def test_allowed_command_override(self):
        # A deploy the user explicitly allows is allowed.
        policy = {"mode": "deny", "allowed_commands": ["deploy.sh"]}
        (self.proj / "fineprint-gate.json").write_text(json.dumps(policy))
        (self.proj / "deploy.sh").write_text("#!/bin/sh\necho deployed\n")
        os.chmod(self.proj / "deploy.sh", 0o755)
        r = run_cli(["gate", "run", "--", "./deploy.sh"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("deployed", r.stdout)

    def test_wall_hides_ssh_key_from_script(self):
        # The tripwire sees only `python3 read_ssh.py` — no path on
        # argv — so it allows. The wall must still deny the read.
        import fineprint_gate as G
        actions = G.scan_argv(["python3", "read_ssh.py"])
        gate = G.Gate(G.Policy(mode="deny"))
        self.assertTrue(all(gate.evaluate(a).allowed for a in actions))
        write_script(self.proj / "read_ssh.py",
                     "import os\n"
                     "print(open(os.path.expanduser('~/.ssh/id_rsa')).read())\n")
        r = run_cli(["gate", "run", "--", "python3", "read_ssh.py"],
                    cwd=self.proj, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("FAKE-PRIVATE-KEY-123", r.stdout + r.stderr)

    def test_wall_allows_normal_file_anywhere(self):
        # The denylist default does NOT confine: a script reading a
        # normal file outside the project still works.
        write_script(self.proj / "read_normal.py",
                     "import os\n"
                     "print(open(os.path.expanduser('~/normal.txt')).read())\n")
        r = run_cli(["gate", "run", "--", "python3", "read_normal.py"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("just a normal file", r.stdout)


class TestConfineMode(WallTestCase):
    def test_confine_flag_denies_outside_path(self):
        r = run_cli(["gate", "run", "--confine", "--", "cat", "/etc/passwd"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("DENY", r.stdout + r.stderr)

    def test_confine_policy_file(self):
        (self.proj / "fineprint-gate.json").write_text(json.dumps(
            {"mode": "confine", "allowed_paths": ["."],
             "allowed_hosts": []}))
        r = run_cli(["gate", "run", "--", "cat", "/etc/passwd"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)

    def test_tripwire_misses_script_read_wall_denies_it(self):
        # Confine mode: a script reads ../outside/secret.txt without
        # naming it on argv; the tripwire allows the argv, the wall
        # denies the read. (The scan uses the script's absolute path:
        # a relative token resolves against the test process's cwd,
        # not the project's.)
        import fineprint_gate as G
        actions = G.scan_argv(["python3", str(self.proj / "read_secret.py")])
        gate = G.Gate(G.Policy(mode="confine",
                               allowed_paths=(str(self.proj),)))
        self.assertTrue(all(gate.evaluate(a).allowed for a in actions))
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("TOPSECRET\n")
        write_script(self.proj / "read_secret.py",
                     'print(open("../outside/secret.txt").read())\n')
        r = run_cli(["gate", "run", "--confine", "--",
                     "python3", "read_secret.py"],
                    cwd=self.proj, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("TOPSECRET", r.stdout + r.stderr)

    def test_wall_denies_symlink_escape(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("TOPSECRET\n")
        os.symlink(outside / "secret.txt", self.proj / "link.txt")
        r = run_cli(["gate", "run", "--confine", "--", "cat", "link.txt"],
                    cwd=self.proj, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("TOPSECRET", r.stdout + r.stderr)

    def test_wall_allows_in_scope_command(self):
        r = run_cli(["gate", "run", "--confine", "--", "cat", "notes.txt"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("hello", r.stdout)

    def test_wall_no_wall_flag_runs_tripwire_only(self):
        # --no-wall: the script read SUCCEEDS (denylist default: the
        # file is normal work, and there is no wall to hide it).
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("TOPSECRET\n")
        write_script(self.proj / "read_secret.py",
                     'print(open("../outside/secret.txt").read())\n')
        r = run_cli(["gate", "run", "--no-wall", "--",
                     "python3", "read_secret.py"],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("TOPSECRET", r.stdout)

    def test_unshare_is_available_here(self):
        import fineprint_wall as W
        self.assertIsNotNone(W.find_sandbox_tool())

    def test_wall_refuses_when_tool_missing(self):
        import fineprint_wall as W
        from unittest import mock
        fake_bin = Path(self.tmp.name) / "bin"
        fake_bin.mkdir()
        python = Path(sys.executable)
        os.symlink(python, fake_bin / "python3")
        with mock.patch.dict(os.environ, {"PATH": str(fake_bin)}):
            with self.assertRaises(W.WallUnavailable):
                W.run_walled(GatePolicyConfine(self.proj),
                             ["python3", "-c", "print('ran')"],
                             cwd=self.proj)


def GatePolicyConfine(proj):
    import fineprint_gate as G
    return G.Policy(mode="confine", allowed_paths=(str(proj),))


class TestComputeHidden(unittest.TestCase):
    def test_hides_siblings_not_scope_or_system(self):
        import fineprint_wall as W
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "walltest"
            proj = base / "proj"
            other = base / "other"
            proj.mkdir(parents=True)
            other.mkdir()
            (other / "secret.txt").write_text("x\n")
            hidden = W.compute_hidden([proj])
            paths = [p for p, _ in hidden]
            self.assertIn(other, paths)
            self.assertNotIn(proj, paths)
            for sysdir in ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc",
                           "/proc", "/dev", "/sys"):
                self.assertNotIn(Path(sysdir), paths)

    def test_hides_tmp_when_outside_scope(self):
        import fineprint_wall as W
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "home" / "someone" / "proj"
            base.mkdir(parents=True)
            hidden = W.compute_hidden([base])
            paths = [p for p, _ in hidden]
            self.assertIn(Path("/var"), paths)
            self.assertNotIn(Path("/tmp"), paths)


class TestComputeDeniedHidden(WallTestCase):
    def test_hides_ssh_dir_env_file_and_records(self):
        import fineprint_wall as W
        import fineprint_definitions as D
        rules = D.builtin_rules()
        hidden = W.compute_denied_hidden(rules, roots=[Path(self.tmp.name)])
        paths = [p for p, _ in hidden]
        self.assertIn(self.home / ".ssh", paths)
        self.assertIn(self.home / ".env", paths)
        self.assertNotIn(self.home / "normal.txt", paths)
        self.assertNotIn(self.proj / "notes.txt", paths)

    def test_records_file_hidden(self):
        import fineprint_wall as W
        import fineprint_definitions as D
        (self.proj / "records.txt").write_text("RECORDS\n")
        hidden = W.compute_denied_hidden(D.builtin_rules(),
                                         roots=[Path(self.tmp.name)])
        paths = [p for p, _ in hidden]
        self.assertIn(self.proj / "records.txt", paths)

    def test_skips_dependency_trees(self):
        # A .env inside node_modules is not a user secret and is not
        # covered — this is what keeps the walk fast.
        import fineprint_wall as W
        import fineprint_definitions as D
        nm = self.proj / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / ".env").write_text("x\n")
        hidden = W.compute_denied_hidden(D.builtin_rules(),
                                         roots=[Path(self.tmp.name)])
        paths = [p for p, _ in hidden]
        self.assertNotIn(nm / ".env", paths)

    def test_pem_rule_matches_key_files_not_ca_bundles(self):
        import fineprint_definitions as D
        self.assertEqual(
            D.path_rule("/x/site-packages/certifi/cacert.pem",
                        D.builtin_rules()), None)
        self.assertEqual(
            D.path_rule("/home/u/server-key.pem", D.builtin_rules()),
            "DENY-CRED-PEM")


class TestWallNetwork(WallTestCase):
    def test_wall_denies_network_when_confined_no_hosts(self):
        import http.server
        import threading
        import urllib.request
        server = http.server.HTTPServer(
            ("127.0.0.1", 0),
            http.server.SimpleHTTPRequestHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        # Build the URL inside the child: no "://" literal on argv.
        code = ("import urllib.request,sys\n"
                "print(urllib.request.urlopen("
                "'http'+chr(58)+'//127.0.0.1:'+sys.argv[1]).read()[:10])\n")
        write_script(self.proj / "fetch.py", code)
        r = run_cli(["gate", "run", "--confine", "--",
                     "python3", "fetch.py", str(port)],
                    cwd=self.proj, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        server.shutdown()

    def test_denylist_allows_network_by_default(self):
        # Denylist default: no network namespace, so a normal fetch
        # to a local server works.
        import http.server
        import threading
        server = http.server.HTTPServer(
            ("127.0.0.1", 0),
            http.server.SimpleHTTPRequestHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        code = ("import urllib.request,sys\n"
                "print(urllib.request.urlopen("
                "'http'+chr(58)+'//127.0.0.1:'+sys.argv[1]).read()[:10])\n")
        write_script(self.proj / "fetch.py", code)
        r = run_cli(["gate", "run", "--", "python3", "fetch.py", str(port)],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        server.shutdown()

    def test_wall_proxy_allows_allowlisted_host_denies_other(self):
        # Confine mode with hosts: the proxy forwards the allowlisted
        # host and 403s the other.
        import http.server
        import threading
        servers = {}
        ports = {}
        for host in ("127.0.0.1", "127.0.0.2"):
            s = http.server.HTTPServer(
                (host, 0), http.server.SimpleHTTPRequestHandler)
            threading.Thread(target=s.serve_forever, daemon=True).start()
            servers[host] = s
            ports[host] = s.server_address[1]
        (self.proj / "fineprint-gate.json").write_text(json.dumps(
            {"mode": "confine", "allowed_paths": ["."],
             "allowed_hosts": ["127.0.0.1"]}))
        code = ("import urllib.request,sys\n"
                "host=sys.argv[1]; port=sys.argv[2]\n"
                "print(urllib.request.urlopen("
                "'http'+chr(58)+'//'+host+chr(58)+port).read()[:10])\n")
        write_script(self.proj / "fetch.py", code)
        log = self.proj / "audit.jsonl"
        r = run_cli(["gate", "run", "--confine", "--log", str(log), "--",
                     "python3", "fetch.py", "127.0.0.1",
                     str(ports["127.0.0.1"])],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        r = run_cli(["gate", "run", "--confine", "--log", str(log), "--",
                     "python3", "fetch.py", "127.0.0.2",
                     str(ports["127.0.0.2"])],
                    cwd=self.proj, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        entries = [json.loads(l) for l in log.read_text().splitlines()
                   if l.strip()]
        self.assertTrue(any(
            e.get("event") == "WALL_PROXY_DENY"
            and e.get("action", {}).get("target") == "127.0.0.2"
            for e in entries))
        for s in servers.values():
            s.shutdown()


class TestWallAuditLog(WallTestCase):
    def test_wall_start_and_end_logged_and_chain_verifies(self):
        import fineprint_gate as G
        log = self.proj / "audit.jsonl"
        r = run_cli(["gate", "run", "--confine", "--log", str(log), "--",
                     "cat", "notes.txt"], cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        entries = [json.loads(l) for l in log.read_text().splitlines()
                   if l.strip()]
        self.assertTrue(any(e.get("event") == "WALL_START" for e in entries))
        self.assertTrue(any(e.get("event") == "WALL_END" for e in entries))
        start = next(e for e in entries if e.get("event") == "WALL_START")
        self.assertIn("sandbox_tool", start)
        self.assertIn("allowed_paths", start)
        self.assertIn("definitions", start)
        self.assertTrue(G.AuditLog.verify(str(log)))

    def test_gate_verify_log_command(self):
        log = self.proj / "audit.jsonl"
        r = run_cli(["gate", "run", "--confine", "--log", str(log), "--",
                     "cat", "notes.txt"], cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        r = run_cli(["gate", "verify-log", "--log", str(log)],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("valid", r.stdout)


class TestGateLog(WallTestCase):
    def test_gate_log_renders_denials(self):
        log = self.proj / "audit.jsonl"
        r = run_cli(["gate", "run", "--log", str(log), "--",
                     "rm", "-rf", "notes.txt"], cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        r = run_cli(["gate", "log", "--log", str(log)],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("tried", r.stdout)
        self.assertIn("blocked by rule DENY-DELETE", r.stdout)
        self.assertIn("will always be blocked", r.stdout)

    def test_gate_log_reports_broken_chain(self):
        log = self.proj / "audit.jsonl"
        r = run_cli(["gate", "run", "--log", str(log), "--",
                     "cat", "notes.txt"], cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 0)
        lines = log.read_text().splitlines()
        lines[0] = lines[0].replace("allowed", "denied", 1)
        log.write_text("\n".join(lines) + "\n")
        r = run_cli(["gate", "log", "--log", str(log)],
                    cwd=self.proj, env=self.env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("BROKEN", r.stdout)


if __name__ == "__main__":
    unittest.main()
