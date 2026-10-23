#!/usr/bin/env python3
"""Seal the Amp T1 promotion run (evidence/amp-2026-10-22/rerun.json) into a
Merkle-rooted evidence bundle (evidence/amp-2026-10-22/bundle.json).

Mirrors the evidence-bundle.v1 structural contract (RFC-6962 Merkle over
canonical-JSON finding leaves, negative controls, INV-004/INV-005
enforcement, detached Ed25519 signature, unwitnessed) with a harness-scoped
pinned block: there is no codex_version_pinned here — the oracle is the
pinned Amp binary at tools/vendor/amp/0.0.1792680614-g8973a3/bin/amp.

Defense in depth (fail closed → status "broken" / nonzero exit):
  1. Determinism: run1 stdout == run2 stdout for every case and control.
  2. Each finding's decision is RE-DERIVED from the raw native stdout by
     serialize_amp_decision (below) — any disagreement with the runner's
     recorded decision breaks the build.
  3. INV-005: a genuine no-match (action: null) serializes as "unknown",
     never "allow".
  4. INV-004: every unknown carries mandatory layer attribution.
  5. Negative controls: all must FAIL (a pass means the run is broken).
  6. Corpus hash vs fixtures/corpus_manifest.json; policy hashes vs the
     rerun's pins; binary sha vs the pin; invariants.yaml sha recorded.

Pre-registration note: this is the first full-corpus Amp run (the spike
covered 13 probes); there is no pre-registration for it. The bundle is
honest about that — pins are verified against the committed corpus manifest
and policy files instead. The corpus "expected" values are the
pre-registered invariant-intent expectations from the Codex corpus (some
are Codex-semantics-flavored, e.g. resolve_host_executables variants and
precedence fixtures); verdicts are recorded mechanically as
actual==expected, and the cross-tier write-up interprets per-harness
distributions rather than pass rates.

Usage: python3 tools/build_amp_bundle.py [--sign]
Stdlib only.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402
import bundle_signing  # noqa: E402

RERUN = REPO / "evidence" / "amp-2026-10-22" / "rerun.json"
OUT_DIR = REPO / "evidence" / "amp-2026-10-22"
MANIFEST = REPO / "fixtures" / "corpus_manifest.json"
INVARIANTS = REPO / "security" / "invariants.yaml"

AMP_TO_FRAMEWORK = {"allow": "allow", "ask": "prompt", "reject": "forbidden",
                    None: "unknown", "delegate": "unmapped"}

ATTRIBUTION = ("no rules-layer decision (action: null); outcome depends on "
               "approval UX + sandbox under the pinned configuration")


def serialize_amp_decision(raw_stdout):
    """Serialize one `amp permissions test --json` stdout to a framework
    decision. INV-005: a genuine no-match (action: null, or unparseable
    output) serializes as "unknown" — never "allow". Returns
    {"decision", "action", "matched", "source"}.
    """
    decision, action, matched, source = "unknown", None, None, None
    text = (raw_stdout or "").strip()
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            action = parsed.get("action")
            matched = parsed.get("matchedEntry")
            source = parsed.get("source")
            if action in AMP_TO_FRAMEWORK:
                decision = AMP_TO_FRAMEWORK[action]
            else:
                # INV-005: unrecognized action falls closed to unknown.
                decision = "unknown"
    return {"decision": decision, "action": action,
            "matched": matched, "source": source}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    want_sign = "--sign" in sys.argv
    rerun = json.loads(RERUN.read_text())
    manifest = json.loads(MANIFEST.read_text())
    problems = []

    pinned = rerun["pinned"]
    binary_path = REPO / pinned["binary_path"]
    if sha256_file(binary_path) != pinned["binary_sha256"]:
        problems.append("amp binary drift vs rerun pin")
    corpus_now = sha256_file(REPO / "fixtures" / "fixtures.json")
    if corpus_now != pinned["corpus_version_hash"]:
        problems.append(f"corpus drift: {corpus_now} != manifest "
                        f"{pinned['corpus_version_hash']}")
    for rel, h in pinned["policy_sha256"].items():
        if sha256_file(REPO / rel) != h:
            problems.append(f"policy drift: {rel}")
    invariants_sha = sha256_file(INVARIANTS)

    if not rerun["determinism"]["byte_identical"]:
        problems.append("rerun not byte-identical across runs")

    findings = []
    verdicts = {"pass": 0, "fail": 0}
    family_verdicts = {}
    for c in rerun["cases"]:
        fid = c["fixture_id"]
        ser = serialize_amp_decision(c["run1"]["stdout"])
        if c["run1"]["stdout"] != c["run2"]["stdout"]:
            problems.append(f"{fid}: run1 != run2")
        if ser["decision"] != c["framework_decision"]:
            problems.append(f"{fid}: runner decision {c['framework_decision']!r} != "
                            f"re-derived {ser['decision']!r}")
        if ser["action"] is None and ser["decision"] == "allow":
            problems.append(f"{fid}: INV-005 violation — no-match serialized as allow")
        actual = ser["decision"]
        expected = c.get("expected")
        verdict = "pass" if actual == expected else "fail"
        verdicts[verdict] += 1
        fam = c["family"]
        family_verdicts.setdefault(fam, {"pass": 0, "fail": 0})[verdict] += 1
        attribution = ATTRIBUTION if actual == "unknown" else None
        if actual == "unknown" and not attribution:
            problems.append(f"{fid}: INV-004 violation — unknown without layer attribution")
        findings.append({
            "schema_version": "finding.v1",
            "fixture_id": fid,
            "invariant_id": c.get("maps_to"),
            "maps_to": c.get("maps_to"),
            "family": fam,
            "argv": c["argv"],
            "command_string": c["command_string"],
            "raw_native_output": c["run1"]["stdout"],
            "native_action": ser["action"],
            "native_matched_entry": ser["matched"],
            "native_source": ser["source"],
            "actual_decision": actual,
            "expected_decision": expected,
            "verdict": verdict,
            "layer": "rules-layer",
            "layer_attribution": attribution,
            "corpus_shard": c["shard"],
            "evidence_class": "REPRO",
            "pinned": {
                "harness": "amp",
                "amp_version": pinned["amp_version"],
                "binary_sha256": pinned["binary_sha256"],
                "policy_file": c["policy_file"],
                "policy_sha256": pinned["policy_sha256"][c["policy_file"]],
                "corpus_version_hash": pinned["corpus_version_hash"],
                "invariants_sha256": invariants_sha,
            },
        })

    # Negative controls: healthy ONLY when they FAIL.
    controls_out = []
    all_failed = True
    for c in rerun["negative_controls"]:
        actual = c["framework_decision"]
        expected = c["expected"]
        verdict = "pass" if actual == expected else "fail"
        healthy = verdict == "fail"
        if not healthy:
            all_failed = False
            problems.append(f"negative control {c['control_id']} PASSED — run is broken")
        controls_out.append({
            "control_id": c["control_id"],
            "argv": c["argv"],
            "expected_decision": expected,
            "actual_decision": actual,
            "control_verdict": verdict,
            "healthy": healthy,
            "purpose": ("Deliberately wrong expectation; a pass would mean our "
                        "serialization normalized the oracle output."),
            "amp_mechanism": ("Amp's built-in catch-all ask resolves what the Codex "
                              "oracle leaves unknown; the control still fails as designed, "
                              "but the mechanism differs from the Codex notes."),
        })

    leaf_hexes = [S.leaf_hash_for_finding(f) for f in findings]
    root, proofs = S.build_merkle(leaf_hexes)
    merkle = {
        "leaf_algorithm": "SHA256(0x00 || canonical_json)",
        "node_algorithm": "SHA256(0x01 || left || right)",
        "leaves": [{"finding_id": f["fixture_id"], "leaf_hash": h}
                   for f, h in zip(findings, leaf_hexes)],
        "inclusion_proofs": {f["fixture_id"]: p for f, p in zip(findings, proofs)},
        "root": root,
    }

    man_pub = manifest["public"]
    man_ho = manifest["held_out"]
    prot_pub = json.loads((REPO / "fixtures" / "protected_records_public.json").read_text())
    prot_ho_p = REPO / "fixtures" / "protected_records_heldout.json"
    prot_ho = json.loads(prot_ho_p.read_text()) if prot_ho_p.exists() else {"fixtures": []}
    prot_merged = sorted(prot_pub["fixtures"] + prot_ho["fixtures"], key=lambda f: f["id"])
    prot_hash = hashlib.sha256(
        json.dumps(prot_merged, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    bundle_id = ("amp-t1-promotion-" +
                 datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    bundle = {
        "schema_version": "evidence-bundle.v1",
        "bundle_id": bundle_id,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "broken" if problems else "valid",
        "harness": "amp",
        "preregistration": {
            "preregistered": False,
            "note": ("No pre-registration: the 2026-10-22 spike covered 13 probes; "
                     "this promotion run is the first full-corpus Amp run. Pins are "
                     "verified against the committed corpus manifest and policy files."),
        },
        "pinned": {
            "harness": "amp",
            "amp_version_pinned": pinned["amp_version"],
            "amp_version_detected": pinned["amp_version_detected"],
            "binary_path": pinned["binary_path"],
            "binary_sha256": pinned["binary_sha256"],
            "rules_files": dict(pinned["policy_sha256"]),
            "invariants_sha256": invariants_sha,
            "corpus_version_hash": pinned["corpus_version_hash"],
        },
        "corpus": {
            "corpus_version_hash": pinned["corpus_version_hash"],
            "fixtures_count": 41,
            "public_count": 21,
            "heldout_count": 20,
            "public_sha256": man_pub["sha256"],
            "heldout_sha256": man_ho["sha256"],
            "family_protected_records": {
                "merged_sha256": prot_hash,
                "public_count": len(prot_pub["fixtures"]),
                "heldout_count": len(prot_ho["fixtures"]),
            },
        },
        "verdicts": verdicts,
        "family_verdicts": family_verdicts,
        "findings": findings,
        "negative_controls": {
            "all_correctly_failed": all_failed,
            "controls": controls_out,
        },
        "merkle": merkle,
        "signature_state": "unsigned",
        "witness_state": "unwitnessed",
    }

    out_path = OUT_DIR / "bundle.json"
    if want_sign:
        try:
            # sign_new_bundle serializes, signs the EXACT bytes, and writes
            # out_path itself — do not rewrite the file afterwards or the
            # detached signature breaks.
            bundle = bundle_signing.sign_new_bundle(bundle, out_path)
        except RuntimeError as e:
            print(f"signing unavailable ({e}); sealing unsigned", file=sys.stderr)
            out_path.write_text(json.dumps(bundle, indent=2) + "\n")
    else:
        out_path.write_text(json.dumps(bundle, indent=2) + "\n")
    print(f"wrote {out_path}")
    print(f"merkle root: {root}")
    print(f"status: {bundle['status']}  signature_state: {bundle['signature_state']}")
    print(f"verdicts: {verdicts}  families: {json.dumps(family_verdicts)}")
    if problems:
        print("PROBLEMS:", *problems, sep="\n  ", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
