#!/usr/bin/env python3
"""Shared Ed25519 bundle-signing helper for the evidence bundle builders.

Used by tools/build_evidence_bundle.py and tools/build_protected_bundle.py
when invoked with --sign.

Semantics (honest states):
  - signature_state="signed" is set ONLY at build time, when the project
    signing key was present and the exact bundle bytes were signed.
  - witness_state is ALWAYS "unwitnessed" here — signing is not witnessing.
  - Signatures are DETACHED: the 64 raw bytes live in <bundle>.sig next to
    the bundle, with metadata in <bundle>.sig.json. Bundle bytes are never
    rewritten to carry a signature.

Key resolution: $FINEPRINT_SIGNING_KEY, else ~/.fineprint/ed25519.key.
The private key lives OUTSIDE all repos (never printed, never committed).
Stdlib only.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import ed25519  # noqa: E402

DEFAULT_KEY = Path(os.environ.get(
    "FINEPRINT_SIGNING_KEY",
    str(Path.home() / ".fineprint" / "ed25519.key"),
))


def fingerprint(pubkey: bytes) -> str:
    return hashlib.sha256(pubkey).hexdigest()


def resolve_key() -> Path:
    if not DEFAULT_KEY.exists():
        raise RuntimeError(
            f"--sign requested but no signing key at {DEFAULT_KEY} "
            "(set $FINEPRINT_SIGNING_KEY or run tools/signing.py gen-key); "
            "refusing to silently emit an unsigned bundle"
        )
    return DEFAULT_KEY


def sign_new_bundle(bundle: dict, out_path: Path, key_path: Path = None) -> dict:
    """Sign a freshly built bundle dict and write it + detached signature.

    Mutates bundle: sets signature_state="signed" and adds the "signature"
    metadata block (no signature bytes inside the bundle itself). Serializes
    the bundle, signs the EXACT bytes written to out_path, and writes
    <out_path>.sig (raw 64 bytes) + <out_path>.sig.json (metadata, including
    bundle_sha256). Returns the bundle dict.
    """
    key_path = key_path or resolve_key()
    if not key_path.exists():
        raise RuntimeError(
            f"--sign requested but no signing key at {key_path}; refusing to "
            "silently emit an unsigned bundle"
        )
    seed = key_path.read_bytes()
    if len(seed) != 32:
        raise RuntimeError(f"signing key {key_path} is not a 32-byte seed")
    pub = ed25519.publickey(seed)

    bundle["signature_state"] = "signed"
    bundle["witness_state"] = "unwitnessed"
    sig_file_name = out_path.name + ".sig"
    bundle["signature"] = {
        "algorithm": "Ed25519",
        "public_key": pub.hex(),
        "fingerprint": fingerprint(pub),
        "signed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "detached_signature_file": sig_file_name,
    }

    data = (json.dumps(bundle, indent=2) + "\n").encode("utf-8")
    sig = ed25519.signature(data, seed, pub)

    out_path.write_bytes(data)
    sig_path = out_path.with_suffix(out_path.suffix + ".sig")
    sig_path.write_bytes(sig)
    meta = {
        **bundle["signature"],
        "bundle_file": out_path.name,
        "bundle_sha256": hashlib.sha256(data).hexdigest(),
        "signer": "fineprint-project-key",
        "note": ("Detached Ed25519 signature over the EXACT bundle bytes, "
                 "produced at build time. The bundle file was not modified "
                 "after signing."),
    }
    sig_meta_path = out_path.with_suffix(out_path.suffix + ".sig.json")
    sig_meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"bundle signed: fingerprint {fingerprint(pub)} "
          f"(detached: {sig_file_name})")
    return bundle
