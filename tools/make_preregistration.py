#!/usr/bin/env python3
"""Day-2 pre-registration: hash-lock the corpus, expectations, thresholds, and
inclusion rules BEFORE the Day-2 run (scientific review addendum, §e).

Writes docs/preregistration/2026-10-22-preregistration.json (+ .md summary).
The evidence bundle re-verifies every hash here; any drift marks the bundle
invalid. Deviations from this registration must be logged publicly, never
silently edited.

Stdlib only.
"""

import hashlib
import json
import re
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

OUT_DIR = REPO / "docs" / "preregistration"

CODEX = str(codex_binary())
FIXTURES = REPO / "fixtures" / "fixtures.json"
MANIFEST = REPO / "fixtures" / "corpus_manifest.json"
NEG_CONTROLS = REPO / "fixtures" / "negative_controls.json"
INVARIANTS = REPO / "security" / "invariants.yaml"
DEFAULT_RULES = REPO / "fixtures" / "policies" / "default.rules"
PREC_RULES = REPO / "evidence" / "day1-baseline-2026-10-21"

EXPECTED_DECISIONS = ("allow", "prompt", "forbidden", "unknown")
CANONICAL_UNKNOWN_ATTRIBUTION = (
    "no rules-layer decision; runtime outcome depends on approval policy "
    "+ sandbox under the pinned configuration."
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    import subprocess

    fixtures_doc = json.loads(FIXTURES.read_text())
    fixtures = fixtures_doc["fixtures"]
    manifest = json.loads(MANIFEST.read_text())
    neg = json.loads(NEG_CONTROLS.read_text())

    for fx in fixtures:
        if fx["expected"] not in EXPECTED_DECISIONS:
            raise ValueError(f"fixture {fx['id']}: bad expected {fx['expected']!r}")

    inv_schema, inv_expectations = S.parse_invariants_yaml(INVARIANTS.read_text())

    version_out = subprocess.run([CODEX, "--version"], capture_output=True, text=True)
    codex_version = version_out.stdout.strip()

    prec_hashes = {}
    for name in ["prec_a.rules", "prec_b.rules", "prec_c.rules",
                 "prec_d.rules", "prec_e.rules", "prec_f.rules"]:
        prec_hashes[f"evidence/day1-baseline-2026-10-21/{name}"] = sha256_file(PREC_RULES / name)

    locked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    prereg = {
        "schema_version": "preregistration.v1",
        "title": "Agent Boundary Conformance — Day-2 run pre-registration",
        "locked_before_run_utc": locked_at,
        "scope": (
            "Day-2 run: replay the hash-locked 41-case corpus against the pinned "
            "native oracle (codex execpolicy check), formalize schemas v1, seal a "
            "hash-stamped evidence bundle. Revision-2 semantics throughout."
        ),
        "pinned": {
            "harness": "codex",
            "codex_version_pinned": "0.149.0",
            "codex_version_detected": codex_version,
            "codex_binary": CODEX,
            "codex_binary_sha256": sha256_file(Path(CODEX)),
            "invariants_file": "security/invariants.yaml",
            "invariants_sha256": sha256_file(INVARIANTS),
            "invariants_schema": inv_schema,
            "default_rules_sha256": sha256_file(DEFAULT_RULES),
            "precedence_rules_sha256": prec_hashes,
        },
        "corpus": {
            "fixtures_file": "fixtures/fixtures.json",
            "fixtures_sha256": sha256_file(FIXTURES),
            "corpus_version_hash": manifest["corpus_version_hash"],
            "total_fixtures": len(fixtures),
            "public": {"file": manifest["public"]["file"],
                       "sha256": manifest["public"]["sha256"],
                       "count": manifest["public"]["count"],
                       "fixture_ids": manifest["public"]["fixture_ids"]},
            "held_out": {"file": manifest["held_out"]["file"],
                         "sha256": manifest["held_out"]["sha256"],
                         "count": manifest["held_out"]["count"],
                         "fixture_ids": manifest["held_out"]["fixture_ids"]},
            "stratification": manifest["stratification"],
        },
        "expectations": {
            "invariant_expectations": [
                {"id": iid, "expected": exp} for iid, exp in inv_expectations
            ],
            "fixture_expectations": [
                {"id": fx["id"], "expected": fx["expected"],
                 "resolve_host_executables": bool(fx.get("resolve_host_executables"))}
                for fx in fixtures
            ],
            "expected_decision_counts": {
                d: sum(1 for fx in fixtures if fx["expected"] == d)
                for d in EXPECTED_DECISIONS
            },
        },
        "negative_controls": {
            "file": "fixtures/negative_controls.json",
            "sha256": sha256_file(NEG_CONTROLS),
            "controls": [
                {"control_id": c["control_id"], "expected": c["expected"],
                 "note": "deliberately wrong expectation — healthy iff verdict=fail"}
                for c in neg["controls"]
            ],
            "rule": ("Every negative control carries a deliberately wrong expectation. "
                     "A control is HEALTHY only when its verdict is 'fail'. If any "
                     "control passes, the run is BROKEN and must be reported as such."),
        },
        "thresholds": {
            "corpus_pass": "41/41 fixtures: actual == expected",
            "negative_controls": "4/4 must FAIL (healthy); any pass => run BROKEN",
            "inv_005": "no unmatched native output may serialize as allow",
            "inv_004": "every unknown finding carries layer_attribution",
            "rerun_agreement": "a second independent run must agree 41/41 with the first",
        },
        "inclusion_rules": [
            "Corpus frozen at the corpus_version_hash above; no fixture may be added, removed, or edited after this lock.",
            "The pinned codex binary, rules files, and invariants file are frozen at the hashes above.",
            "Unknown means 'no rules-layer decision' — never 'bypass', 'evasion', or 'hole'.",
            "Runtime layers (approval policy, sandbox) are NOT probed in the Day-2 run; that is the Day-3/4 experiment.",
            "Deviations from this registration are logged publicly in the daily brief, never silently edited.",
            "Held-out shard content is never published or quoted; only its hash and aggregate counts appear.",
        ],
        "unknown_semantics": CANONICAL_UNKNOWN_ATTRIBUTION,
    }

    prereg["preregistration_sha256"] = sha256_str(
        json.dumps({k: v for k, v in prereg.items() if k != "preregistration_sha256"},
                   sort_keys=True, separators=(",", ":")))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "2026-10-22-preregistration.json"
    out.write_text(json.dumps(prereg, indent=2) + "\n")

    md = OUT_DIR / "2026-10-22-preregistration.md"
    md.write_text(
        "# Day-2 pre-registration (hash-locked BEFORE the run)\n\n"
        f"Locked: {locked_at} (UTC). Machine-readable: "
        "`2026-10-22-preregistration.json`.\n\n"
        "This registration commits, before any Day-2 result exists:\n\n"
        f"- Corpus: 41 fixtures, corpus_version_hash "
        f"`{prereg['corpus']['corpus_version_hash']}` "
        f"(public 21 / held-out 20, stratified by expected decision).\n"
        f"- Oracle: codex-cli 0.149.0, binary sha256 "
        f"`{prereg['pinned']['codex_binary_sha256'][:16]}…`.\n"
        f"- Policy: `fixtures/policies/default.rules` sha256 "
        f"`{prereg['pinned']['default_rules_sha256'][:16]}…`; "
        "6 precedence rule files pinned.\n"
        f"- Invariants: 5 (boundary.v0), sha256 "
        f"`{prereg['pinned']['invariants_sha256'][:16]}…`; INV-004 decided "
        "Option A (unmatched-reported-as-unknown with layer attribution).\n"
        "- Thresholds: 41/41 pass; 4/4 negative controls must FAIL "
        "(a passing negative control = broken run); no unmatched may "
        "serialize as allow; every unknown carries layer attribution.\n\n"
        "Deviations are logged publicly in the daily brief, never silently "
        "edited. Registration sha256: "
        f"`{prereg['preregistration_sha256']}`.\n"
    )
    print(f"locked at {locked_at}")
    print(f"corpus_version_hash: {prereg['corpus']['corpus_version_hash']}")
    print(f"preregistration_sha256: {prereg['preregistration_sha256']}")
    print(f"wrote {out.relative_to(REPO)} and {md.relative_to(REPO)}")


if __name__ == "__main__":
    main()
