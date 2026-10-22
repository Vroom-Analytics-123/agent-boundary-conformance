#!/usr/bin/env python3
"""FinePrint bundle signing CLI (Ed25519, stdlib only via tools/ed25519.py).

Commands:
  gen-key [--key PATH]            Generate the project signing key.
  sign-bundle --bundle PATH [--key PATH]
                                 Attach a DETACHED Ed25519 signature to an
                                 existing bundle: writes PATH.sig (raw 64
                                 bytes) + PATH.sig.json (metadata). The bundle
                                 bytes are NEVER modified.
  verify-bundle --bundle PATH [--sig PATH] --pubkey HEX
                                 Verify a detached signature.

Key location: the PRIVATE key lives OUTSIDE all repos. Default
~/.fineprint/ed25519.key (override with $FINEPRINT_SIGNING_KEY). The key file
is written chmod 600. The private key is NEVER printed, NEVER committed, and
NEVER included in any output file. Only the public key + fingerprint are
published (docs/SIGNING.md).
Stdlib only.
"""

import argparse
import hashlib
import json
import os
import stat
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
    """Public-key fingerprint: SHA256 over the raw 32-byte public key, hex."""
    return hashlib.sha256(pubkey).hexdigest()


def gen_key(key_path: Path) -> Path:
    seed = os.urandom(32)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(seed)
    # Belt and braces: ensure 0600 even if the umask path differed.
    os.chmod(key_path, 0o600)
    pub = ed25519.publickey(seed)
    print(f"key written: {key_path} (mode {oct(stat.S_IMODE(os.stat(key_path).st_mode))})")
    print(f"public key:  {pub.hex()}")
    print(f"fingerprint: {fingerprint(pub)}")
    print("private key is NOT printed and must never be committed or shared.")
    return key_path


def load_seed(key_path: Path) -> bytes:
    data = key_path.read_bytes()
    if len(data) != 32:
        raise SystemExit(f"key file {key_path} is not a 32-byte seed "
                         f"(got {len(data)} bytes); refusing to use it")
    return data


def sign_bundle(bundle_path: Path, key_path: Path) -> Path:
    seed = load_seed(key_path)
    pub = ed25519.publickey(seed)
    data = bundle_path.read_bytes()
    sig = ed25519.signature(data, seed, pub)
    sig_path = bundle_path.with_suffix(bundle_path.suffix + ".sig")
    sig_path.write_bytes(sig)
    meta = {
        "algorithm": "Ed25519",
        "public_key": pub.hex(),
        "fingerprint": fingerprint(pub),
        "signed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bundle_file": bundle_path.name,
        "bundle_sha256": hashlib.sha256(data).hexdigest(),
        "detached_signature_file": sig_path.name,
        "signer": "fineprint-project-key",
        "note": ("Detached signature over the EXACT bundle bytes. The bundle "
                 "file itself was not modified."),
    }
    meta_path = bundle_path.with_suffix(bundle_path.suffix + ".sig.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"signed: {bundle_path.name}")
    print(f"  signature: {sig_path.name} (64 bytes, detached)")
    print(f"  metadata:  {meta_path.name}")
    print(f"  fingerprint: {meta['fingerprint']}")
    return sig_path


def verify_bundle(bundle_path: Path, sig_path: Path, pubkey_hex: str) -> bool:
    try:
        pub = bytes.fromhex(pubkey_hex)
    except ValueError:
        raise SystemExit("public key is not valid hex")
    if len(pub) != 32:
        raise SystemExit("public key must be 32 bytes (64 hex chars)")
    data = bundle_path.read_bytes()
    sig = sig_path.read_bytes()
    if len(sig) != 64:
        print(f"INVALID: signature file {sig_path.name} is {len(sig)} bytes, not 64")
        return False
    ok = ed25519.checkvalid(sig, data, pub)
    print(f"bundle: {bundle_path.name}")
    print(f"fingerprint: {fingerprint(pub)}")
    print("SIGNATURE VALID" if ok else "SIGNATURE INVALID")
    return ok


def main():
    ap = argparse.ArgumentParser(description="FinePrint Ed25519 bundle signing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen-key", help="generate the project signing key")
    g.add_argument("--key", default=str(DEFAULT_KEY))
    s = sub.add_parser("sign-bundle", help="attach a detached signature to a bundle")
    s.add_argument("--bundle", required=True)
    s.add_argument("--key", default=str(DEFAULT_KEY))
    v = sub.add_parser("verify-bundle", help="verify a detached bundle signature")
    v.add_argument("--bundle", required=True)
    v.add_argument("--sig", default=None)
    v.add_argument("--pubkey", required=True, help="64-hex-char Ed25519 public key")
    args = ap.parse_args()

    if args.cmd == "gen-key":
        key_path = Path(args.key)
        if key_path.exists():
            raise SystemExit(f"refusing to overwrite existing key: {key_path}")
        gen_key(key_path)
    elif args.cmd == "sign-bundle":
        bundle_path = Path(args.bundle)
        if not bundle_path.exists():
            raise SystemExit(f"bundle not found: {bundle_path}")
        key_path = Path(args.key)
        if not key_path.exists():
            raise SystemExit(f"signing key not found: {key_path} "
                             f"(set $FINEPRINT_SIGNING_KEY or run gen-key)")
        sign_bundle(bundle_path, key_path)
    elif args.cmd == "verify-bundle":
        bundle_path = Path(args.bundle)
        sig_path = Path(args.sig) if args.sig else bundle_path.with_suffix(
            bundle_path.suffix + ".sig")
        if not sig_path.exists():
            raise SystemExit(f"signature file not found: {sig_path}")
        ok = verify_bundle(bundle_path, sig_path, args.pubkey)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
