#!/usr/bin/env python3
"""Seal and verify FinePrint check-run bundles (check-run-bundle.v1).

seal_check_bundle() builds the bundle dict from a finished run: per-probe
findings, per-invariant adjudication (computed by tools/check_scorecard.py),
claim-scope accounting (measured-before-claimed), and the RFC-6962-style
Merkle seal over canonical-JSON findings (tools/schemas_v1.py primitives).

verify_check_bundle() re-derives every checkable claim from the bundle
bytes: verdict consistency, INV-005 (unknown raw output never serialized as
allow — re-derived from raw_native_output for codex findings), unknown
layer-attribution presence, and the full Merkle root + per-leaf inclusion
proofs. Returns a list of problems (empty = verified).

Signing (--sign in fineprint_check.py) reuses tools/bundle_signing.py:
detached Ed25519, signature_state="signed", witness_state stays
"unwitnessed".

Stdlib only.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402
import bundle_signing  # noqa: E402

SCHEMA_VERSION = "check-run-bundle.v1"
UNKNOWN_ATTRIBUTION_MIN = 20


def _utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal_check_bundle(*, label, run_spec, findings, invariant_results,
                      claim_scope, privacy, sign=False, out_path=None):
    """Assemble + Merkle-seal a check-run bundle. Returns the bundle dict.

    findings: list of per-probe finding dicts (already validated by the
      runner). invariant_results: per-invariant adjudication dicts.
    sign=True requires out_path and a project key (fails closed).
    """
    problems = []

    # --- verdict-level consistency sweep (fail loud, mark broken) ---
    for f in findings:
        exp_set = set(f.get("expected_decisions")
                      or [f["expected_decision"]])
        want = ("pass" if f["actual_decision"] in exp_set else "fail")
        if f["actual_decision"] == "error":
            want = "not_run"
        if f["verdict"] != want:
            problems.append(
                f"{f['probe_id']}: verdict {f['verdict']!r} inconsistent "
                f"with actual={f['actual_decision']!r} "
                f"expected={f['expected_decision']!r}")
        # INV-005: re-derive from raw native output for codex findings.
        raw = f.get("raw_native_output") or ""
        if raw and f["evidence_class"] == "REPRO":
            rederived = S.serialize_native_decision(raw)["decision"]
            if rederived == "unknown" and f["actual_decision"] == "allow":
                problems.append(f"{f['probe_id']}: INV-005 violation — "
                                "no-match native output serialized as allow")
        # INV-004: unknowns carry layer attribution.
        if f["actual_decision"] == "unknown":
            attr = f.get("layer_attribution") or ""
            if len(attr) < UNKNOWN_ATTRIBUTION_MIN:
                problems.append(f"{f['probe_id']}: unknown without layer "
                                "attribution (INV-004)")

    verdicts = {"pass": 0, "fail": 0, "not_run": 0}
    for f in findings:
        verdicts[f["verdict"]] += 1

    mv = {"PASS": 0, "FAIL": 0, "NOT_REPRODUCED": 0}
    ic = {"SATISFIED": 0, "NOT_SATISFIED": 0, "UNRESOLVED": 0,
          "NOT_APPLICABLE": 0}
    uk = {"no-rule-match": 0, "insufficient-runtime-evidence": 0,
          "unsupported-adapter": 0}
    for r in invariant_results:
        mv[r["measurement_validity"]] += 1
        ic[r["intent_coverage"]] += 1
        for k, v in (r.get("unknown_kinds") or {}).items():
            if k in uk:
                uk[k] += v

    leaf_hashes = [S.leaf_hash_for_finding(f) for f in findings]
    root, proofs = S.build_merkle(leaf_hashes)

    created = _utcnow()
    bundle_id = ("fineprint-check-" + created.replace(":", "")
                 .replace("-", "").replace("T", "-").replace("Z", ""))

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "created_utc": created,
        "tool": "tools/fineprint_check.py",
        "label": label,
        "run": run_spec,
        "privacy": privacy,
        "claim_scope": claim_scope,
        "verdicts": verdicts,
        "dual_verdict_summary": {
            "measurement_validity": mv,
            "intent_coverage": ic,
            "unknown_kinds": uk,
        },
        "invariant_results": invariant_results,
        "findings": findings,
        "merkle": {
            "leaf_algorithm": "SHA256(0x00 || canonical_json)",
            "node_algorithm": "SHA256(0x01 || left || right)",
            "leaves": [{"finding_id": f["probe_id"], "leaf_hash": h}
                       for f, h in zip(findings, leaf_hashes)],
            "root": root,
            "inclusion_proofs": {f["probe_id"]: p
                                 for f, p in zip(findings, proofs)},
        },
        "signature_state": "unsigned",
        "witness_state": "unwitnessed",
        "status": "broken" if problems else "valid",
    }
    if problems:
        bundle["problems"] = problems

    if sign:
        if out_path is None:
            raise S.SchemaViolation("--sign requires an output path")
        bundle_signing.sign_new_bundle(bundle, Path(out_path))
        return bundle
    return bundle


def verify_check_bundle(bundle):
    """Re-derive every checkable claim. Returns [problems]; [] = verified."""
    problems = []
    if bundle.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version {bundle.get('schema_version')!r} != "
                f"{SCHEMA_VERSION!r}"]
    findings = bundle.get("findings", [])
    leaves = bundle.get("merkle", {}).get("leaves", [])
    proofs = bundle.get("merkle", {}).get("inclusion_proofs", {})
    root = bundle.get("merkle", {}).get("root")

    if len(findings) != len(leaves):
        problems.append(f"findings count {len(findings)} != leaves count "
                        f"{len(leaves)}")

    recomputed = [S.leaf_hash_for_finding(f) for f in findings]
    for f, want, leaf in zip(findings, recomputed, leaves):
        if leaf.get("leaf_hash") != want:
            problems.append(f"{f.get('probe_id')}: leaf hash mismatch")
        if leaf.get("finding_id") != f.get("probe_id"):
            problems.append(f"{f.get('probe_id')}: leaf id mismatch")
    try:
        reroot, _ = S.build_merkle(recomputed)
    except S.SchemaViolation as e:
        return problems + [f"merkle rebuild failed: {e}"]
    if reroot != root:
        problems.append(f"merkle root mismatch: recomputed {reroot} != "
                        f"bundle {root}")
    for f, leaf_hash in zip(findings, recomputed):
        proof = proofs.get(f["probe_id"])
        if proof is None:
            problems.append(f"{f['probe_id']}: missing inclusion proof")
        elif not S.verify_inclusion(leaf_hash, proof, root):
            problems.append(f"{f['probe_id']}: inclusion proof FAILED")

    # Verdict + honesty-rail re-derivation (same sweep as the sealer).
    for f in findings:
        exp_set = set(f.get("expected_decisions")
                      or [f["expected_decision"]])
        want = ("pass" if f["actual_decision"] in exp_set else "fail")
        if f["actual_decision"] == "error":
            want = "not_run"
        if f["verdict"] != want:
            problems.append(f"{f['probe_id']}: verdict inconsistent")
        raw = f.get("raw_native_output") or ""
        if raw and f.get("evidence_class") == "REPRO":
            rederived = S.serialize_native_decision(raw)["decision"]
            if rederived == "unknown" and f["actual_decision"] == "allow":
                problems.append(f"{f['probe_id']}: INV-005 violation")
        if f["actual_decision"] == "unknown" and len(
                f.get("layer_attribution") or "") < UNKNOWN_ATTRIBUTION_MIN:
            problems.append(f"{f['probe_id']}: unknown without attribution")

    # Privacy self-check: public_mode bundles must name no private entry.
    privacy = bundle.get("privacy", {})
    if privacy.get("public_mode"):
        priv_ids = {r["invariant_id"] for r in
                    bundle.get("invariant_results", []) if r.get("private")}
        priv_ids |= {f["invariant_id"] for f in findings if f.get("private")}
        if priv_ids:
            problems.append("public_mode bundle contains private entries: "
                            + ", ".join(sorted(priv_ids)))
    return problems


def main(argv):
    if "--verify" not in argv:
        sys.exit("usage: check_bundle.py --verify <bundle.json>")
    import json
    path = Path(argv[argv.index("--verify") + 1])
    bundle = json.loads(path.read_text())
    problems = verify_check_bundle(bundle)
    if problems:
        print(f"{path}: BROKEN")
        for p in problems:
            print(f"  - {p}")
        return 2
    print(f"{path}: verified (merkle root "
          f"{bundle['merkle']['root'][:16]}…, "
          f"{len(bundle['findings'])} findings, all proofs ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
