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


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: verify_bundle.py <bundle.json>")
    bundle = json.loads(Path(sys.argv[1]).read_text())
    problems = []

    if bundle.get("schema_version") != S.SCHEMA_BUNDLE:
        problems.append(f"bad schema_version: {bundle.get('schema_version')!r}")

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
        ser = S.serialize_native_decision(f.get("raw_native_output", ""))
        if ser["decision"] == "unknown" and f.get("actual_decision") == "allow":
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
    if prereg_path.exists():
        pr = json.loads(prereg_path.read_text())
        if pr.get("preregistration_sha256") != prereg.get("sha256"):
            problems.append("pre-registration hash in bundle != hash in prereg file")
    pinned = bundle.get("pinned", {})
    corpus_now = sha256_file(REPO / "fixtures" / "fixtures.json")
    if corpus_now != bundle.get("corpus", {}).get("corpus_version_hash"):
        problems.append("corpus file on disk != bundle corpus_version_hash")
    if pinned.get("binary_sha256") != sha256_file(Path(pinned.get("binary_path", ""))):
        problems.append("codex binary on disk != pinned binary_sha256")
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
