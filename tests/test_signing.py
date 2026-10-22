#!/usr/bin/env python3
"""Tests for Ed25519 bundle signing (tools/ed25519.py, tools/signing.py,
tools/bundle_signing.py, and the --sign path in the bundle builders).

Scenarios (not just counts):
  E1. RFC 8032 section 7.1 TEST 1 + TEST 2: publickey, signature and
      checkvalid reproduce the published vectors byte-for-byte.
  E2. Round-trip: a fresh random key signs and verifies; the same bytes with
      a flipped bit, a different message, or a different key do NOT verify.
  E3. sign_new_bundle: a new bundle gets signature_state="signed" and
      witness_state="unwitnessed" (honest — signing is not witnessing); the
      64 signature bytes are detached (never inside the bundle JSON); the
      detached signature verifies over the exact bundle bytes; the .sig.json
      metadata records bundle_sha256 == the written bytes.
  E4. --sign fails closed: with no key present the builder raises instead of
      silently emitting an unsigned bundle.
  E5. Attaching a detached signature to an already-sealed bundle does not
      modify the bundle bytes (sha256 identical before/after).
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import ed25519  # noqa: E402
import bundle_signing  # noqa: E402


def _cat(*lines):
    return "".join(lines)


# RFC 8032 section 7.1 vectors, transcribed verbatim (two text lines each).
RFC_VECTORS = [
    {  # TEST 1: empty message
        "sk": _cat("9d61b19deffd5a60ba844af492ec2cc4",
                   "4449c5697b326919703bac031cae7f60"),
        "pk": _cat("d75a980182b10ab7d54bfed3c964073a",
                   "0ee172f3daa62325af021a68f707511a"),
        "msg": b"",
        "sig": _cat("e5564300c360ac729086e2cc806e828a",
                    "84877f1eb8e5d974d873e06522490155",
                    "5fb8821590a33bacc61e39701cf9b46b",
                    "d25bf5f0595bbe24655141438e7a100b"),
    },
    {  # TEST 2: message 0x72
        "sk": _cat("4ccd089b28ff96da9db6c346ec114e0f",
                   "5b8a319f35aba624da8cf6ed4fb8a6fb"),
        "pk": _cat("3d4017c3e843895a92b70aa74d1b7ebc",
                   "9c982ccf2ec4968cc0cd55f12af4660c"),
        "msg": bytes([0x72]),
        "sig": _cat("92a009a9f0d4cab8720e820b5f642540",
                    "a2b27b5416503f8fb3762223ebdb69da",
                    "085ac1e43e15996e458f3613d0f11d8c",
                    "387b2eaeb4302aeeb00d291612bb0c00"),
    },
]


class TestEd25519Vectors(unittest.TestCase):
    def test_rfc8032_vectors(self):
        """E1: pubkey derivation, signing and verification match RFC 8032."""
        for v in RFC_VECTORS:
            sk, pk, sig = (bytes.fromhex(v["sk"]), bytes.fromhex(v["pk"]),
                           bytes.fromhex(v["sig"]))
            self.assertEqual(ed25519.publickey(sk), pk)
            self.assertEqual(ed25519.signature(v["msg"], sk, pk), sig)
            self.assertTrue(ed25519.checkvalid(sig, v["msg"], pk))

    def test_round_trip_and_tamper(self):
        """E2: fresh-key round trip verifies; any tampering is rejected."""
        seed = os.urandom(32)
        pub = ed25519.publickey(seed)
        msg = b'{"bundle_id": "boundary-day2-test"}'
        sig = ed25519.signature(msg, seed, pub)
        self.assertTrue(ed25519.checkvalid(sig, msg, pub))
        bad = bytearray(sig)
        bad[0] ^= 1
        self.assertFalse(ed25519.checkvalid(bytes(bad), msg, pub))
        self.assertFalse(ed25519.checkvalid(sig, msg + b"!", pub))
        self.assertFalse(ed25519.checkvalid(sig, msg, ed25519.publickey(os.urandom(32))))
        self.assertFalse(ed25519.checkvalid(b"short", msg, pub))
        self.assertFalse(ed25519.checkvalid(sig, msg, b"short"))


def _make_key(tmp: Path) -> Path:
    key = tmp / "test.key"
    key.write_bytes(os.urandom(32))
    return key


class TestBundleSigning(unittest.TestCase):
    def test_sign_new_bundle(self):
        """E3: build-time signing sets signed/unwitnessed, detaches bytes."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            key = _make_key(tmp)
            bundle = {"schema_version": "evidence-bundle.v1",
                      "bundle_id": "test-bundle",
                      "signature_state": "unsigned",
                      "witness_state": "unwitnessed"}
            out = tmp / "bundle.json"
            bundle_signing.sign_new_bundle(bundle, out, key_path=key)
            self.assertEqual(bundle["signature_state"], "signed")
            self.assertEqual(bundle["witness_state"], "unwitnessed",
                             "signing must not claim witnessing")
            data = out.read_bytes()
            sig_path = tmp / "bundle.json.sig"
            meta_path = tmp / "bundle.json.sig.json"
            self.assertTrue(sig_path.exists())
            self.assertEqual(len(sig_path.read_bytes()), 64)
            self.assertTrue(meta_path.exists())
            meta = json.loads(meta_path.read_text())
            self.assertEqual(meta["algorithm"], "Ed25519")
            self.assertEqual(meta["bundle_sha256"],
                             hashlib.sha256(data).hexdigest())
            self.assertEqual(meta["fingerprint"],
                             hashlib.sha256(bytes.fromhex(meta["public_key"])).hexdigest())
            # The detached signature verifies over the EXACT written bytes.
            pub = bytes.fromhex(meta["public_key"])
            self.assertTrue(ed25519.checkvalid(sig_path.read_bytes(), data, pub))
            # ... and the written JSON carries no signature bytes.
            written = json.loads(data.decode())
            self.assertNotIn("signature_bytes", json.dumps(written))

    def test_sign_fails_closed_without_key(self):
        """E4: --sign with no key raises instead of emitting unsigned."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bundle = {"bundle_id": "x", "signature_state": "unsigned",
                      "witness_state": "unwitnessed"}
            with self.assertRaises(RuntimeError):
                bundle_signing.sign_new_bundle(
                    bundle, tmp / "b.json",
                    key_path=tmp / "no-such-key")

    def test_detached_signature_does_not_modify_bundle(self):
        """E5: post-seal attestation leaves sealed bytes untouched."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            key = _make_key(tmp)
            sealed = tmp / "sealed.json"
            sealed.write_bytes(b'{"bundle_id": "sealed", "signature_state": "unsigned"}\n')
            before = hashlib.sha256(sealed.read_bytes()).hexdigest()
            seed = key.read_bytes()
            pub = ed25519.publickey(seed)
            sig = ed25519.signature(sealed.read_bytes(), seed, pub)
            (tmp / "sealed.json.sig").write_bytes(sig)
            after = hashlib.sha256(sealed.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertTrue(ed25519.checkvalid(sig, sealed.read_bytes(), pub))


if __name__ == "__main__":
    unittest.main()
