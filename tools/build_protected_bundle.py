#!/usr/bin/env python3
"""Build a hash-stamped evidence bundle for the protected-records fixture
family (Day-3, 2026-10-21).

Family-scoped sibling of tools/build_evidence_bundle.py: same discipline
(pre-registration self-hash check, pin verification, finding.v1 lift with
INV-005/INV-004 enforcement, negative controls, Merkle seal), but against
the family pre-registration (docs/preregistration/2026-10-21-protected-records-
preregistration.json) and fixtures/policies/protected_records.rules.

Governing intent note: the family's stated intent lives in the policy file
header + the pre-registration scope, not in security/invariants.yaml
(frozen Day-1). pinned.invariants_sha256 is the unchanged invariants.yaml
hash (it governs runner semantics: INV-004/INV-005); pinned.family_policy_*
carry the family's own governing document.

Usage: python3 tools/build_protected_bundle.py <rerun-json> [--out-dir DIR]
Stdlib only.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402
# Day-5 pin-checklist discipline (2026-10-21): every tool resolves the oracle
# through tools/pin.py, which prefers the sha256-verified vendored copy and
# fails closed on mismatch. The host path /opt/hatch-image/bin/codex was
# swapped to an unpinned build on Day 4 and must never be used directly here.
from pin import codex_binary  # noqa: E402
import bundle_signing  # noqa: E402

CODEX = str(codex_binary())
PINNED_CODEX_VERSION = "0.149.0"
PUB = REPO / "fixtures" / "protected_records_public.json"
HO = REPO / "fixtures" / "protected_records_heldout.json"
RULES = REPO / "fixtures" / "policies" / "protected_records.rules"
NC = REPO / "fixtures" / "protected_records_negative_controls.json"
INVARIANTS = REPO / "security" / "invariants.yaml"
PREREG = REPO / "docs" / "preregistration" / "2026-10-21-protected-records-preregistration.json"
MANIFEST = REPO / "fixtures" / "protected_records_manifest.json"

ATTRIBUTION = S.LAYER_ATTRIBUTION_UNKNOWN


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def family_corpus_hash(pub_path: Path, ho_path: Path) -> str:
    """Content-canonical corpus hash: sha256 over the merged fixture CONTENT
    (sorted by id), not over file bytes. This is stable under stamping the
    hash itself into the shard files (fixed-point safe), and it commits to
    exactly what the runner executes. Must agree with the same helper in the
    family lock script (/tmp/lock_protected_family.py)."""
    pub_doc = json.loads(pub_path.read_text())
    ho_doc = json.loads(ho_path.read_text())
    merged = sorted(pub_doc["fixtures"] + ho_doc["fixtures"],
                    key=lambda f: f["id"])
    canon = json.dumps(merged, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).hexdigest()


def run_oracle(argv, rules_path, resolve):
    cmd = [CODEX, "execpolicy", "check", "--rules", str(REPO / rules_path)]
    if resolve:
        cmd.append("--resolve-host-executables")
    cmd += ["--", *argv]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.stdout.strip()


def load_prereg():
    pr = json.loads(PREREG.read_text())
    body = {k: v for k, v in pr.items() if k != "preregistration_sha256"}
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != pr["preregistration_sha256"]:
        raise S.SchemaViolation("family pre-registration failed its own hash check")
    return pr


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: build_protected_bundle.py <rerun-json> [--out-dir DIR]")
    rerun_path = Path(sys.argv[1])
    out_dir = REPO / "evidence" / "day3-2026-10-21"
    if "--out-dir" in sys.argv:
        out_dir = Path(sys.argv[sys.argv.index("--out-dir") + 1])

    run_doc = json.loads(rerun_path.read_text())
    prereg = load_prereg()
    manifest = json.loads(MANIFEST.read_text())
    nc_doc = json.loads(NC.read_text())

    problems = []

    # --- Pin verification vs family pre-registration ---
    corpus_hash = family_corpus_hash(PUB, HO)
    if corpus_hash != prereg["corpus"]["corpus_version_hash"]:
        problems.append("family corpus drift vs pre-registration")
    if corpus_hash != manifest["corpus_version_hash"]:
        problems.append("family corpus drift vs family manifest")
    if sha256_file(PUB) != manifest["public"]["sha256"]:
        problems.append("public shard drift vs family manifest")
    if sha256_file(HO) != manifest["held_out"]["sha256"]:
        problems.append("held-out shard drift vs family manifest")
    binary_hash = sha256_file(Path(CODEX))
    if binary_hash != prereg["pinned"]["codex_binary_sha256"]:
        problems.append("codex binary drift vs pre-registration")
    rules_hash = sha256_file(RULES)
    if rules_hash != prereg["pinned"]["protected_records_rules_sha256"]:
        problems.append("protected_records.rules drift vs pre-registration")
    invariants_hash = sha256_file(INVARIANTS)
    nc_hash = sha256_file(NC)
    if nc_hash != prereg["negative_controls"]["sha256"]:
        problems.append("family negative_controls drift vs pre-registration")

    detected = run_doc["run"]["codex_version_detected"]
    if PINNED_CODEX_VERSION not in detected:
        problems.append(f"codex version drift: detected {detected!r}")

    pub_doc = json.loads(PUB.read_text())
    ho_doc = json.loads(HO.read_text())
    by_id = {f["id"]: f for f in pub_doc["fixtures"] + ho_doc["fixtures"]}
    shard_of = {fid: "public" for fid in manifest["public"]["fixture_ids"]}
    shard_of.update({fid: "held-out" for fid in manifest["held_out"]["fixture_ids"]})

    # --- Lift runner results into finding.v1 ---
    findings = []
    for r in run_doc["results"]:
        fid = r["id"]
        fx = by_id.get(fid)
        if fx is None:
            problems.append(f"runner result for unknown fixture {fid}")
            continue
        rederived = S.serialize_native_decision(r["raw_stdout"])
        if rederived["decision"] != r["actual"]:
            problems.append(f"{fid}: runner actual={r['actual']!r} but re-derived "
                            f"as {rederived['decision']!r}")
        f = S.Finding(
            fixture_id=fid,
            invariant_id="protected_records",
            maps_to="protected_records",
            argv=list(fx["argv"]),
            raw_native_output=r["raw_stdout"],
            native_matched_rules_count=r.get("matched_rules", 0),
            actual_decision=r["actual"],
            expected_decision=fx["expected"],
            invariant_expected=[],
            verdict=r["verdict"],
            layer="rules-layer",
            layer_attribution=(ATTRIBUTION if r["actual"] == "unknown" else None),
            corpus_shard=shard_of.get(fid),
            evidence_class="REPRO",
            pinned={
                "harness": "codex",
                "harness_version": PINNED_CODEX_VERSION,
                "binary_sha256": binary_hash,
                "rules_sha256": rules_hash,
                "invariants_sha256": invariants_hash,
                "corpus_version_hash": corpus_hash,
            },
        )
        try:
            findings.append(f.to_dict())
        except S.SchemaViolation as e:
            problems.append(f"{fid}: finding rejected: {e}")

    # --- Negative controls ---
    nc_results = []
    for c in nc_doc["controls"]:
        raw = run_oracle(c["argv"], c["rules"], c.get("resolve_host_executables", False))
        ser = S.serialize_native_decision(raw)
        verdict = "pass" if ser["decision"] == c["expected"] else "fail"
        healthy = verdict == "fail"
        if not healthy:
            problems.append(f"negative control {c['control_id']} PASSED — run is BROKEN")
        nc_results.append({
            "control_id": c["control_id"],
            "argv": c["argv"],
            "expected_decision": c["expected"],
            "actual_decision": ser["decision"],
            "control_verdict": verdict,
            "healthy": healthy,
            "purpose": c["purpose"],
        })

    # --- INV-005 sweep ---
    for f in findings:
        ser = S.serialize_native_decision(f["raw_native_output"])
        if ser["decision"] == "unknown" and f["actual_decision"] == "allow":
            problems.append(f"{f['fixture_id']}: INV-005 violation in bundle")

    passes = sum(1 for f in findings if f["verdict"] == "pass")
    fails = len(findings) - passes
    status = "broken" if problems else "valid"

    leaf_hashes = [S.leaf_hash_for_finding(f) for f in findings]
    root, proofs = S.build_merkle(leaf_hashes)

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle_id = f"boundary-day3-protected-{created.replace(':', '').replace('-', '')}"

    bundle = {
        "schema_version": S.SCHEMA_BUNDLE,
        "bundle_id": bundle_id,
        "created_utc": created,
        "status": status,
        "family": "protected_records",
        "governing_intent": "fixtures/policies/protected_records.rules header + "
                            "family pre-registration scope (security/invariants.yaml "
                            "is frozen Day-1 and carries no protected-records entry)",
        "preregistration": {
            "file": "docs/preregistration/2026-10-21-protected-records-preregistration.json",
            "sha256": prereg["preregistration_sha256"],
            "locked_before_run_utc": prereg["locked_before_run_utc"],
        },
        "pinned": {
            "codex_version_pinned": PINNED_CODEX_VERSION,
            "codex_version_detected": detected,
            "binary_path": CODEX,
            "binary_sha256": binary_hash,
            "invariants_sha256": invariants_hash,
            "family_policy_file": "fixtures/policies/protected_records.rules",
            "family_policy_sha256": rules_hash,
            "corpus_version_hash": corpus_hash,
            "preregistration_sha256": prereg["preregistration_sha256"],
        },
        "corpus": {
            "corpus_version_hash": corpus_hash,
            "fixtures_count": len(findings),
            "public_count": manifest["public"]["count"],
            "heldout_count": manifest["held_out"]["count"],
            "public_sha256": manifest["public"]["sha256"],
            "heldout_sha256": manifest["held_out"]["sha256"],
        },
        "verdicts": {"pass": passes, "fail": fails},
        "findings": findings,
        "negative_controls": {
            "controls": nc_results,
            "all_correctly_failed": all(c["healthy"] for c in nc_results),
        },
        "merkle": {
            "leaf_algorithm": "SHA256(0x00 || canonical_json)",
            "node_algorithm": "SHA256(0x01 || left || right)",
            "leaves": [{"finding_id": f["fixture_id"], "leaf_hash": h}
                       for f, h in zip(findings, leaf_hashes)],
            "root": root,
            "inclusion_proofs": {f["fixture_id"]: p
                                 for f, p in zip(findings, proofs)},
        },
        "signature_state": "unsigned",
        "witness_state": "unwitnessed",
    }
    if problems:
        bundle["problems"] = problems

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bundle-protected.json"
    if "--sign" in sys.argv:
        # Ed25519 detached signature at build time (docs/SIGNING.md).
        # signature_state=signed; witness_state stays honestly unwitnessed.
        bundle_signing.sign_new_bundle(bundle, out_path)
    else:
        out_path.write_text(json.dumps(bundle, indent=2) + "\n")

    print(f"bundle {bundle_id}: status={status} pass={passes} fail={fails}")
    print(f"negative controls healthy: {all(c['healthy'] for c in nc_results)} "
          f"({len(nc_results)} controls)")
    print(f"merkle root: {root}")
    for p in problems:
        print(f"PROBLEM: {p}")
    try:
        print(f"wrote {out_path.relative_to(REPO)}")
    except ValueError:
        # --out-dir given as a relative path that pathlib cannot relativize
        print(f"wrote {out_path.absolute()}")
    return 0 if status == "valid" else 2


if __name__ == "__main__":
    sys.exit(main())
