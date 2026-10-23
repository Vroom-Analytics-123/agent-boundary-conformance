#!/usr/bin/env python3
"""Offline verifier for an evidence bundle (evidence-bundle.v1).

Re-verifies, from the bundle file alone plus the pinned source files:
  1. Every finding recomputes to its Merkle leaf; every inclusion proof
     walks to the recorded root; the root matches.
  2. INV-005: no finding whose raw native output is a no-match is allow.
  3. INV-004: every unknown finding carries layer_attribution.
  4. Verdict consistency: verdict == (actual == expected).
  5. Negative controls: all must be healthy (verdict=fail); else broken.
  6. Corpus hash equals the pre-registered corpus hash; pinned file hashes
     match the files on disk.
  7. Bundle status is consistent with the checks above.

Exit 0: bundle valid. Exit 2: bundle broken or verification failed.
Stdlib only.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402
import ed25519  # noqa: E402


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sig_paths(bundle_path: Path):
    return (bundle_path.with_suffix(bundle_path.suffix + ".sig"),
            bundle_path.with_suffix(bundle_path.suffix + ".sig.json"))


def check_detached_signature(bundle_path: Path, bundle: dict, problems: list,
                             strict: bool):
    """Verify a detached Ed25519 signature over the exact bundle bytes.

    strict=True (bundle claims signature_state="signed"): missing/invalid
    signature is a verification problem. strict=False (unsigned bundle with
    a post-seal attestation alongside): only an INVALID signature is a
    problem; a valid one is reported informationally.
    """
    sig_path, meta_path = _sig_paths(bundle_path)
    data = bundle_path.read_bytes()
    if strict:
        sig_block = bundle.get("signature") or {}
        pubkey_hex = sig_block.get("public_key", "")
        try:
            pub = bytes.fromhex(pubkey_hex)
        except ValueError:
            pub = b""
        if len(pub) != 32:
            problems.append("signature_state=signed but bundle has no valid "
                            "public key in its signature block")
            return
        if not sig_path.exists():
            problems.append(f"signature_state=signed but detached signature "
                            f"missing: {sig_path.name}")
            return
        sig = sig_path.read_bytes()
        if len(sig) != 64 or not ed25519.checkvalid(sig, data, pub):
            problems.append("signature_state=signed but detached Ed25519 "
                            "signature is INVALID over the bundle bytes")
            return
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("bundle_sha256") != hashlib.sha256(data).hexdigest():
                problems.append("signature metadata bundle_sha256 != actual "
                                "bundle bytes hash")
                return
            if meta.get("public_key") != pubkey_hex:
                problems.append("signature metadata public_key != bundle "
                                "signature block public_key")
                return
        print(f"signature: VALID (Ed25519, fingerprint "
              f"{hashlib.sha256(pub).hexdigest()[:16]}...)")
    else:
        if not sig_path.exists():
            print("signature_state=unsigned (no detached signature)")
            return
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        pubkey_hex = meta.get("public_key", "")
        try:
            pub = bytes.fromhex(pubkey_hex)
        except ValueError:
            pub = b""
        sig = sig_path.read_bytes()
        if len(pub) != 32 or len(sig) != 64 or not ed25519.checkvalid(sig, data, pub):
            problems.append(f"detached signature alongside unsigned bundle is "
                            f"INVALID: {sig_path.name}")
            return
        print(f"signature: detached post-seal attestation VALID "
              f"(fingerprint {hashlib.sha256(pub).hexdigest()[:16]}...; "
              f"bundle signature_state honestly remains 'unsigned')")


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: verify_bundle.py <bundle.json>")
    bundle = json.loads(Path(sys.argv[1]).read_text())
    problems = []

    if bundle.get("schema_version") != S.SCHEMA_BUNDLE:
        problems.append(f"bad schema_version: {bundle.get('schema_version')!r}")

    # Amp bundles (evidence/amp-2026-10-22/) follow the same structural
    # contract (RFC-6962 Merkle, INV-004/INV-005 enforcement, negative
    # controls, detached signature) with a harness-scoped pinned block.
    is_amp = bundle.get("pinned", {}).get("harness") == "amp"

    def amp_ser(raw):
        """INV-005 serializer for `amp permissions test --json` output:
        genuine no-match (action: null, or unparseable) -> unknown, never
        allow."""
        try:
            parsed = json.loads((raw or "").strip() or "null")
        except (json.JSONDecodeError, AttributeError):
            parsed = None
        action = parsed.get("action") if isinstance(parsed, dict) else None
        mapping = {"allow": "allow", "ask": "prompt", "reject": "forbidden",
                   None: "unknown", "delegate": "unmapped"}
        return mapping.get(action, "unknown")

    findings = bundle.get("findings", [])
    merkle = bundle.get("merkle", {})
    leaves = {l["finding_id"]: l["leaf_hash"] for l in merkle.get("leaves", [])}
    proofs = merkle.get("inclusion_proofs", {})

    # 1. Merkle re-verification.
    for f in findings:
        fid = f["fixture_id"]
        recomputed = S.leaf_hash_for_finding(f)
        recorded = leaves.get(fid)
        if recorded != recomputed:
            problems.append(f"{fid}: leaf hash mismatch "
                            f"(recorded {recorded}, recomputed {recomputed})")
            continue
        if not S.verify_inclusion(recorded, proofs.get(fid, []), merkle.get("root", "")):
            problems.append(f"{fid}: inclusion proof does not reach the root")

    # 2-4. Per-finding semantic checks.
    for f in findings:
        fid = f["fixture_id"]
        if is_amp:
            ser_decision = amp_ser(f.get("raw_native_output", ""))
            no_match = ser_decision == "unknown"
        else:
            ser = S.serialize_native_decision(f.get("raw_native_output", ""))
            ser_decision = ser["decision"]
            no_match = ser_decision == "unknown"
        if no_match and f.get("actual_decision") == "allow":
            problems.append(f"{fid}: INV-005 violation — no-match serialized as allow")
        if f.get("actual_decision") == "unknown" and not f.get("layer_attribution"):
            problems.append(f"{fid}: INV-004 violation — unknown without layer_attribution")
        want = "pass" if f.get("actual_decision") == f.get("expected_decision") else "fail"
        if f.get("verdict") != want:
            problems.append(f"{fid}: verdict {f.get('verdict')!r} inconsistent "
                            f"(actual={f.get('actual_decision')!r} "
                            f"expected={f.get('expected_decision')!r})")

    # 5. Negative controls.
    ncs = bundle.get("negative_controls", {}).get("controls", [])
    for c in ncs:
        if not c.get("healthy"):
            problems.append(f"negative control {c.get('control_id')} PASSED — "
                            "a run that passes its negative controls is broken")

    # 6. Corpus + pinned hashes vs files on disk.
    prereg = bundle.get("preregistration", {})
    prereg_path = REPO / prereg.get("file", "")
    if prereg_path.is_file():
        pr = json.loads(prereg_path.read_text())
        if pr.get("preregistration_sha256") != prereg.get("sha256"):
            problems.append("pre-registration hash in bundle != hash in prereg file")
    pinned = bundle.get("pinned", {})
    # 6a. Corpus check is family-aware: the protected_records family bundle
    # commits to the canonical family corpus hash (merged public + held-out
    # fixture content, sorted by id), not to fixtures/fixtures.json. The
    # verifier previously checked fixtures.json for every bundle, which made
    # every valid family bundle "fail" this check (pre-existing blind spot,
    # found 2026-10-22 during the post-fix re-verification).
    if is_amp:
        # Amp bundle: per-finding family ("corpus" | "protected-public" |
        # "protected-heldout"). Corpus family commits to fixtures/fixtures.json;
        # the protected family commits to the merged public+heldout family hash.
        fams = {f.get("family") for f in findings}
        if any(fm == "corpus" for fm in fams):
            corpus_now = sha256_file(REPO / "fixtures" / "fixtures.json")
            if corpus_now != bundle.get("corpus", {}).get("corpus_version_hash"):
                problems.append("corpus file on disk != bundle corpus_version_hash")
        if any(fm and fm.startswith("protected") for fm in fams):
            pub = json.loads((REPO / "fixtures" / "protected_records_public.json").read_text())
            ho = json.loads((REPO / "fixtures" / "protected_records_heldout.json").read_text())
            merged = sorted(pub["fixtures"] + ho["fixtures"], key=lambda f: f["id"])
            canon = json.dumps(merged, sort_keys=True, separators=(",", ":")).encode()
            if hashlib.sha256(canon).hexdigest() != bundle.get("corpus", {}).get(
                    "family_protected_records", {}).get("merged_sha256"):
                problems.append("protected family on disk != bundle merged hash")
    elif bundle.get("family") == "protected_records":
        pub = json.loads((REPO / "fixtures" / "protected_records_public.json").read_text())
        ho = json.loads((REPO / "fixtures" / "protected_records_heldout.json").read_text())
        merged = sorted(pub["fixtures"] + ho["fixtures"], key=lambda f: f["id"])
        canon = json.dumps(merged, sort_keys=True, separators=(",", ":")).encode()
        corpus_now = hashlib.sha256(canon).hexdigest()
    else:
        corpus_now = sha256_file(REPO / "fixtures" / "fixtures.json")
    if corpus_now != bundle.get("corpus", {}).get("corpus_version_hash"):
        problems.append("corpus file on disk != bundle corpus_version_hash")
    bin_path = Path(pinned.get("binary_path", ""))
    if not bin_path.is_absolute():
        bin_path = REPO / bin_path
    if pinned.get("binary_sha256") != sha256_file(bin_path):
        problems.append(f"{'amp' if is_amp else 'codex'} binary on disk != pinned binary_sha256")
    rules_map = pinned.get("rules_files", {})
    for rel, h in rules_map.items():
        p = REPO / rel
        if p.exists() and sha256_file(p) != h:
            problems.append(f"rules file drift: {rel}")
    if pinned.get("invariants_sha256") != sha256_file(REPO / "security" / "invariants.yaml"):
        problems.append("invariants.yaml on disk != pinned hash")

    # 7. Status consistency.
    declared = bundle.get("status")
    want_status = "broken" if problems else "valid"
    if declared != want_status:
        problems.append(f"declared status {declared!r} but checks say {want_status!r}")

    # 8. Detached Ed25519 signature (docs/SIGNING.md).
    bundle_path = Path(sys.argv[1])
    state = bundle.get("signature_state")
    if state == "signed":
        check_detached_signature(bundle_path, bundle, problems, strict=True)
    elif state == "unsigned":
        check_detached_signature(bundle_path, bundle, problems, strict=False)
    else:
        problems.append(f"bad signature_state: {state!r}")

    n = len(findings)
    passes = sum(1 for f in findings if f.get("verdict") == "pass")
    print(f"bundle {bundle.get('bundle_id')}: {n} findings, "
          f"pass={passes} fail={n - passes}")
    print(f"merkle root: {merkle.get('root')}")
    print(f"negative controls: {len(ncs)} controls, "
          f"healthy={all(c.get('healthy') for c in ncs)}")
    print(f"signature_state={bundle.get('signature_state')} "
          f"witness_state={bundle.get('witness_state')}")
    if problems:
        print(f"VERIFICATION FAILED ({len(problems)} problems):")
        for p in problems:
            print(f"  - {p}")
        return 2
    print(f"VERIFIED: bundle status '{declared}' confirmed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
