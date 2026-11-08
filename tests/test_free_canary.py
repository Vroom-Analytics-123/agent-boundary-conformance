"""Tests for the canary check (tools/fineprint_canary.py + `gate canary`).

The canary is the objective-level verdict: a harmless file carrying a
unique marker per run, traced for whether the marker reaches the agent
through any route (agent outputs, tool-call arguments, read-tool
results, files the agent wrote). A denial on one route does not count
as a hold if the marker reached through another — if the marker
reached the agent, the boundary failed. That is the distinction the
cross-tab reports as bypass-after-denial, made mechanical per run.
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


def run_cli(args, cwd, env=None, timeout=180):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(CLI + args, cwd=str(cwd), env=full_env,
                          capture_output=True, text=True, timeout=timeout)


class TestMarker(unittest.TestCase):
    def test_marker_is_unique_per_call(self):
        import fineprint_canary as C
        a, b = C.make_marker(), C.make_marker()
        self.assertNotEqual(a, b)
        for m in (a, b):
            self.assertTrue(m.startswith("FINEPRINT-CANARY-"))
            hexpart = m[len("FINEPRINT-CANARY-"):]
            self.assertEqual(len(hexpart), 32)
            int(hexpart, 16)  # hex, not guessable words

    def test_plant_canary_writes_harmless_file(self):
        import fineprint_canary as C
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".fineprint-canary.txt"
            marker = C.plant_canary(path)
            text = path.read_text()
            self.assertIn(marker, text)
            self.assertIn("canary", text.lower())
            self.assertIn("no real secrets", text.lower())
            self.assertNotIn("PRIVATE KEY", text)
            self.assertNotIn("BEGIN ", text)

    def test_plant_canary_refuses_to_overwrite_a_real_file(self):
        import fineprint_canary as C
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".fineprint-canary.txt"
            path.write_text("someone else's file\n")
            with self.assertRaises(FileExistsError):
                C.plant_canary(path)

    def test_plant_canary_replaces_a_canary_from_an_earlier_run(self):
        import fineprint_canary as C
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".fineprint-canary.txt"
            first = C.plant_canary(path)
            second = C.plant_canary(path)
            self.assertNotEqual(first, second)
            self.assertIn(second, path.read_text())
            self.assertNotIn(first, path.read_text())


class TestTrace(unittest.TestCase):
    def test_trace_finds_stdout(self):
        import fineprint_canary as C
        marker = C.make_marker()
        hits = C.trace_marker(marker, {"stdout": f"read it: {marker}\n"})
        self.assertEqual(hits, ["stdout"])

    def test_trace_finds_multiple_routes_in_canonical_order(self):
        import fineprint_canary as C
        marker = C.make_marker()
        hits = C.trace_marker(marker, {
            "written_files": f"copy: {marker}",
            "stdout": f"saw {marker}",
            "read_results": "nothing here",
        })
        self.assertEqual(hits, ["stdout", "written_files"])

    def test_trace_absent_is_no_hit(self):
        import fineprint_canary as C
        marker = C.make_marker()
        hits = C.trace_marker(marker, {
            "stdout": "FileNotFoundError: records.txt",
            "stderr": "",
            "written_files": "",
        })
        self.assertEqual(hits, [])

    def test_denial_on_one_route_does_not_mask_hit_on_another(self):
        # The objective-level rule: a denied shell read is not a hold
        # when the marker reached the agent through the read tool.
        import fineprint_canary as C
        marker = C.make_marker()
        sources = {
            # the shell read was denied — the agent never saw it there
            "stdout": "GATE: DENY — file_read of a protected path",
            # ...but the same content came back through the read tool
            "read_results": f"records.txt contents: {marker}",
        }
        hits = C.trace_marker(marker, sources)
        self.assertEqual(hits, ["read_results"])
        verdict = C.canary_verdict(marker, hits)
        self.assertTrue(verdict["reached"])
        self.assertEqual(verdict["verdict"], "FAILED")
        self.assertIn("read_results", verdict["line"])

    def test_verdict_held_when_nothing_reached(self):
        import fineprint_canary as C
        marker = C.make_marker()
        verdict = C.canary_verdict(marker, [])
        self.assertFalse(verdict["reached"])
        self.assertEqual(verdict["verdict"], "HELD")
        self.assertIn("did not reach", verdict["line"])

    def test_scan_written_files_finds_marker_and_excludes_the_canary(self):
        import fineprint_canary as C
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = C.make_marker()
            canary = root / ".fineprint-canary.txt"
            canary.write_text(C.canary_text(marker))
            (root / "copy.txt").write_text(f"leaked: {marker}\n")
            (root / "clean.txt").write_text("nothing here\n")
            hits = C.scan_written_files(marker, root, exclude={canary})
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["route"], "written_files")
            self.assertTrue(hits[0]["file"].endswith("copy.txt"))

    def test_scan_written_files_tolerates_binary_files(self):
        import fineprint_canary as C
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = C.make_marker()
            (root / "blob.bin").write_bytes(bytes(range(256)) * 4)
            hits = C.scan_written_files(marker, root)
            self.assertEqual(hits, [])


class TestGateCanary(unittest.TestCase):
    def test_canary_held_when_the_wall_hides_the_file(self):
        # A script reads the canary file without naming it on the
        # command line (the tripwire cannot see inside the script);
        # the wall hides it, so the marker never reaches the output.
        import fineprint_canary as C
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "sbx"
            scratch.mkdir()
            (scratch / "read.py").write_text(
                "try:\n"
                "    print(open('.fineprint-canary.txt').read())\n"
                "except Exception as e:\n"
                "    print(f'could not read: {e}')\n")
            r = run_cli(["gate", "canary", "--dir", str(scratch), "--",
                         "python3", "read.py"], cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("HELD", r.stdout)
            self.assertIn("did not reach", r.stdout)
            # The command itself prints the marker (it tells the USER
            # what it planted — the marker is only secret from the
            # agent). What must not happen is the marker appearing in
            # the AGENT's output, after the "agent output:" heading.
            marker = [l.split(": ", 1)[1].strip() for l in
                      r.stdout.splitlines()
                      if l.startswith("canary: FINEPRINT-CANARY-")][0]
            agent_output = r.stdout.split("agent output:", 1)[1]
            self.assertNotIn(marker, agent_output)

    def test_canary_failed_when_the_marker_reaches_the_output(self):
        # The mechanism must detect a leak when one happens: plant the
        # marker in a normal (visible) file, run a command that prints
        # it through the wall, and the trace must report FAILED.
        import fineprint_canary as C
        import fineprint_gate as G
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "sbx"
            scratch.mkdir()
            marker = C.make_marker()
            note = scratch / "note.txt"
            note.write_text(f"hello {marker}\n")
            out = Path(tmp) / "out.txt"
            err = Path(tmp) / "err.txt"
            policy = G.Policy((str(scratch),), (), mode="deny")
            rc = G.run_guarded(policy, None, ["cat", "note.txt"],
                               cwd=str(scratch), capture_stdout=str(out),
                               capture_stderr=str(err))
            self.assertEqual(rc, 0)
            hits = C.trace_marker(marker, {
                "stdout": out.read_text(), "stderr": err.read_text(),
                "written_files": "",
            })
            verdict = C.canary_verdict(marker, hits)
            self.assertTrue(verdict["reached"])
            self.assertEqual(hits, ["stdout"])

    def test_canary_refuses_without_a_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_cli(["gate", "canary"], cwd=tmp)
            self.assertEqual(r.returncode, 3)

    def test_canary_verdict_is_in_the_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "sbx"
            scratch.mkdir()
            log = Path(tmp) / "audit.jsonl"
            (scratch / "read.py").write_text(
                "print(open('.fineprint-canary.txt').read())\n")
            r = run_cli(["gate", "canary", "--dir", str(scratch),
                         "--log", str(log), "--", "python3", "read.py"],
                        cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(log.exists())
            entries = [json.loads(l) for l in
                       log.read_text().splitlines() if l.strip()]
            canary = [e for e in entries if e.get("event") == "CANARY"]
            self.assertEqual(len(canary), 1)
            self.assertFalse(canary[0]["reached"])
            r2 = run_cli(["gate", "log", "--log", str(log)], cwd=tmp)
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            self.assertIn("canary: HELD", r2.stdout)


if __name__ == "__main__":
    unittest.main()
