"""Tests for signed definition packs (tools/fineprint_definitions.py).

A definitions pack is a versioned JSON file of denylist rules, signed
with the maintainers' Ed25519 key (the public key published in
docs/SIGNING.md). The wall verifies the signature before applying a
pack and never applies an unverified one. The built-in rules are v1;
a pack replaces them when it verifies.
"""

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))


def make_keypair():
    import ed25519
    sk = os.urandom(32)
    pk = ed25519.publickey(sk)
    return sk, pk


def canonical(version, rules):
    return json.dumps({"version": version, "rules": rules},
                      sort_keys=True, separators=(",", ":")).encode()


def sign_pack(sk, pk, version, rules):
    import ed25519
    sig = ed25519.signature(canonical(version, rules), sk, pk)
    return {"version": version, "rules": rules,
            "signature": base64.b64encode(sig).decode()}


class TestDefinitions(unittest.TestCase):
    def test_builtin_version_and_rules(self):
        import fineprint_definitions as D
        version, rules, source = D.load_definitions()
        self.assertEqual(version, D.BUILTIN_VERSION)
        self.assertEqual(source, "built-in")
        ids = [r["id"] for r in rules]
        for wanted in ("DENY-CRED-SSH", "DENY-CRED-ENV", "DENY-RECORDS",
                       "DENY-DELETE", "DENY-UNLINK", "DENY-DEPLOY"):
            self.assertIn(wanted, ids)

    def test_signed_pack_applies(self):
        import fineprint_definitions as D
        sk, pk = make_keypair()
        rules = [{"id": "DENY-TEST", "kind": "path",
                  "patterns": ["**/test-secret.txt"],
                  "description": "test rule"}]
        pack = sign_pack(sk, pk, "2099-01-01", rules)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fineprint-definitions.json"
            path.write_text(json.dumps(pack))
            version, loaded, source = D.load_definitions(
                public_key=pk, search_paths=[Path(tmp)])
            self.assertEqual(version, "2099-01-01")
            self.assertEqual([r["id"] for r in loaded], ["DENY-TEST"])
            self.assertEqual(source, str(path))

    def test_tampered_pack_rejected(self):
        import fineprint_definitions as D
        sk, pk = make_keypair()
        rules = [{"id": "DENY-TEST", "kind": "path",
                  "patterns": ["**/test-secret.txt"],
                  "description": "test rule"}]
        pack = sign_pack(sk, pk, "2099-01-01", rules)
        pack["rules"][0]["patterns"] = ["**/everything.txt"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fineprint-definitions.json"
            path.write_text(json.dumps(pack))
            with self.assertRaises(D.DefinitionsError):
                D.load_definitions(public_key=pk, search_paths=[Path(tmp)])

    def test_unsigned_pack_rejected(self):
        import fineprint_definitions as D
        sk, pk = make_keypair()
        pack = {"version": "2099-01-01",
                "rules": [{"id": "DENY-TEST", "kind": "path",
                           "patterns": ["**/test-secret.txt"],
                           "description": "test rule"}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fineprint-definitions.json"
            path.write_text(json.dumps(pack))
            with self.assertRaises(D.DefinitionsError):
                D.load_definitions(public_key=pk, search_paths=[Path(tmp)])

    def test_wrong_key_rejected(self):
        import fineprint_definitions as D
        sk, pk = make_keypair()
        _, other_pk = make_keypair()
        rules = [{"id": "DENY-TEST", "kind": "path",
                  "patterns": ["**/test-secret.txt"],
                  "description": "test rule"}]
        pack = sign_pack(sk, pk, "2099-01-01", rules)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fineprint-definitions.json"
            path.write_text(json.dumps(pack))
            with self.assertRaises(D.DefinitionsError):
                D.load_definitions(public_key=other_pk,
                                   search_paths=[Path(tmp)])

    def test_unverified_pack_refuses_run(self):
        import fineprint_definitions as D
        pack = {"version": "2099-01-01",
                "rules": [{"id": "DENY-TEST", "kind": "path",
                           "patterns": ["**/test-secret.txt"],
                           "description": "test rule"}]}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "fineprint-definitions.json").write_text(
                json.dumps(pack))
            # The CLI refuses to run (exit 3) instead of applying an
            # unverified pack or silently using stale rules.
            import subprocess
            r = subprocess.run(
                [sys.executable, str(REPO / "fineprint"), "gate", "run",
                 "--", "echo", "hi"],
                cwd=tmp, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 3)
            self.assertIn("definition", (r.stdout + r.stderr).lower())

    def test_gate_definitions_reports_version(self):
        import subprocess
        r = subprocess.run(
            [sys.executable, str(REPO / "fineprint"), "gate", "definitions"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertIn("definitions", r.stdout.lower())
        self.assertIn("DENY-CRED-SSH", r.stdout)


if __name__ == "__main__":
    unittest.main()
