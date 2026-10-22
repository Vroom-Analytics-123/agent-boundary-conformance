#!/usr/bin/env python3
"""Build a hash-stamped evidence bundle (evidence-bundle.v1) for a Day-2 run.

Reads the raw output of tools/run_fixtures.py (the v0 runner — NOT rebuilt),
lifts each result into finding.v1, runs the negative controls through the
same oracle path, and seals everything with a Merkle root + pinned hashes,
per docs/VERIFIABLE_EVIDENCE_ARCHITECTURE.md (week-1 scope: hash-stamped
only; signature_state is honestly "unsigned", witness_state "unwitnessed").

Defense in depth: the runner's reported `actual` is re-derived from the raw
native stdout with schemas_v1.serialize_native_decision. Any disagreement,
any INV-005 serialization violation, any unknown without layer attribution,
any passing negative control, or any hash drift vs the pre-registration
marks the bundle "broken".

Usage: python3 tools/build_evidence_bundle.py <rerun-json> [--out-dir DIR]
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

CODEX = "/opt/hatch-image/bin/codex"
PINNED_CODEX_VERSION = "0.149.0"

FIXTURES = REPO / "fixtures" / "fixtures.json"
MANIFEST = REPO / "fixtures" / "corpus_manifest.json"
NEG_CONTROLS = REPO / "fixtures" / "negative_controls.json"
INVARIANTS = REPO / "security" / "invariants.yaml"
DEFAULT_RULES = REPO / "fixtures" / "policies" / "default.rules"
PREREG = REPO / "docs" / "preregistration" / "2026-10-22-preregistration.json"

ATTRIBUTION = S.LAYER_ATTRIBUTION_UNKNOWN


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_oracle(argv, rules_path, resolve):
    """Same oracle path as the v0 runner: codex execpolicy check."""
    cmd = [CODEX, "execpolicy", "check", "--rules", str(REPO / rules_path)]
    if resolve:
        cmd.append("--resolve-host-executables")
    cmd += ["--", *argv]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.stdout.strip()


def load_prereg():
    pr = json.loads(PREREG.read_text())
    # Recompute the registration's own hash to detect tampering.
    body = {k: v for k, v in pr.items() if k != "preregistration_sha256"}
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != pr["preregistration_sha256"]:
        raise S.SchemaViolation("pre-registration file failed its own hash check")
    return pr


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: build_evidence_bundle.py <rerun-json> [--out-dir DIR]")
    rerun_path = Path(sys.argv[1])
    out_dir = REPO / "evidence" / "day2-2026-10-22"
    if "--out-dir" in sys.argv:
        out_dir = Path(sys.argv[sys.argv.index("--out-dir") + 1])

    run_doc = json.loads(rerun_path.read_text())
    prereg = load_prereg()
    manifest = json.loads(MANIFEST.read_text())
    fixtures_doc = json.loads(FIXTURES.read_text())
    neg_doc = json.loads(NEG_CONTROLS.read_text())

    problems = []

    # --- Pin verification: corpus / rules / invariants / binary vs prereg ---
    corpus_hash = sha256_file(FIXTURES)
    if corpus_hash != prereg["corpus"]["corpus_version_hash"]:
        problems.append(f"corpus drift: {corpus_hash} != preregistered "
                        f"{prereg['corpus']['corpus_version_hash']}")
    if corpus_hash != manifest["corpus_version_hash"]:
        problems.append("corpus drift vs corpus_manifest.json")
    binary_hash = sha256_file(Path(CODEX))
    if binary_hash != prereg["pinned"]["codex_binary_sha256"]:
        problems.append("codex binary drift vs pre-registration")
    rules_hash = sha256_file(DEFAULT_RULES)
    if rules_hash != prereg["pinned"]["default_rules_sha256"]:
        problems.append("default.rules drift vs pre-registration")
    invariants_hash = sha256_file(INVARIANTS)
    if invariants_hash != prereg["pinned"]["invariants_sha256"]:
        problems.append("invariants.yaml drift vs pre-registration")
    neg_hash = sha256_file(NEG_CONTROLS)
    if neg_hash != prereg["negative_controls"]["sha256"]:
        problems.append("negative_controls.json drift vs pre-registration")

    detected = run_doc["run"]["codex_version_detected"]
    if PINNED_CODEX_VERSION not in detected:
        problems.append(f"codex version drift: detected {detected!r}")

    # --- Fixture lookup tables ---
    by_id = {fx["id"]: fx for fx in fixtures_doc["fixtures"]}
    shard_of = {}
    for fid in manifest["public"]["fixture_ids"]:
        shard_of[fid] = "public"
    for fid in manifest["held_out"]["fixture_ids"]:
        shard_of[fid] = "held-out"

    # Invariant expectations from the pinned invariants.yaml.
    _, inv_expectations = S.parse_invariants_yaml(INVARIANTS.read_text()) \
        if hasattr(S, "parse_invariants_yaml") else (None, [])
    inv_expected_map = dict(inv_expectations)

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
            problems.append(
                f"{fid}: runner actual={r['actual']!r} but re-derived "
                f"from raw stdout as {rederived['decision']!r}")
        maps_to = fx.get("maps_to", "")
        f = S.Finding(
            fixture_id=fid,
            invariant_id=maps_to,
            maps_to=maps_to,
            argv=list(fx["argv"]),
            raw_native_output=r["raw_stdout"],
            native_matched_rules_count=r.get("matched_rules", 0),
            actual_decision=r["actual"],
            expected_decision=fx["expected"],
            invariant_expected=list(inv_expected_map.get(maps_to, [])),
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

    # --- Negative controls: same oracle path, deliberately wrong expectations ---
    nc_results = []
    for c in neg_doc["controls"]:
        raw = run_oracle(c["argv"], c["rules"], c.get("resolve_host_executables", False))
        ser = S.serialize_native_decision(raw)
        verdict = "pass" if ser["decision"] == c["expected"] else "fail"
        healthy = verdict == "fail"
        if not healthy:
            problems.append(
                f"negative control {c['control_id']} PASSED — run is BROKEN "
                "(a run that passes its negative controls is a broken run)")
        nc_results.append({
            "control_id": c["control_id"],
            "argv": c["argv"],
            "expected_decision": c["expected"],
            "actual_decision": ser["decision"],
            "control_verdict": verdict,
            "healthy": healthy,
            "purpose": c["purpose"],
        })

    # --- Corpus-level INV-005 sweep: no no-match finding may be allow ---
    for f in findings:
        ser = S.serialize_native_decision(f["raw_native_output"])
        if ser["decision"] == "unknown" and f["actual_decision"] == "allow":
            problems.append(f"{f['fixture_id']}: INV-005 violation in bundle")

    passes = sum(1 for f in findings if f["verdict"] == "pass")
    fails = len(findings) - passes
    status = "broken" if problems else "valid"

    # --- Merkle seal over canonical findings ---
    leaf_hashes = [S.leaf_hash_for_finding(f) for f in findings]
    root, proofs = S.build_merkle(leaf_hashes)

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle_id = f"boundary-day2-{created.replace(':', '').replace('-', '')}"

    bundle = {
        "schema_version": S.SCHEMA_BUNDLE,
        "bundle_id": bundle_id,
        "created_utc": created,
        "status": status,
        "preregistration": {
            "file": "docs/preregistration/2026-10-22-preregistration.json",
            "sha256": prereg["preregistration_sha256"],
            "locked_before_run_utc": prereg["locked_before_run_utc"],
        },
        "pinned": {
            "codex_version_pinned": PINNED_CODEX_VERSION,
            "codex_version_detected": detected,
            "binary_path": CODEX,
            "binary_sha256": binary_hash,
            "invariants_sha256": invariants_hash,
            "corpus_version_hash": corpus_hash,
            "preregistration_sha256": prereg["preregistration_sha256"],
            "rules_files": {
                "fixtures/policies/default.rules": rules_hash,
                **{k: sha256_file(REPO / k)
                   for k in prereg["pinned"]["precedence_rules_sha256"]},
            },
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
    out_path = out_dir / "bundle.json"
    out_path.write_text(json.dumps(bundle, indent=2) + "\n")

    shard_counts = {}
    for f in findings:
        key = (f.get("corpus_shard"), f["verdict"])
        shard_counts[key] = shard_counts.get(key, 0) + 1
    print(f"bundle {bundle_id}: status={status} pass={passes} fail={fails}")
    print(f"negative controls healthy: {all(c['healthy'] for c in nc_results)} "
          f"({len(nc_results)} controls)")
    print(f"merkle root: {root}")
    print(f"shard breakdown: {shard_counts}")
    for p in problems:
        print(f"PROBLEM: {p}")
    print(f"wrote {out_path.relative_to(REPO)}")
    return 0 if status == "valid" else 2


if __name__ == "__main__":
    sys.exit(main())
