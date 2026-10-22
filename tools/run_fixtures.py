#!/usr/bin/env python3
"""Agent Boundary Conformance - v0 fixture replay engine.

Replays the fixtures in fixtures/fixtures.json against the pinned native
oracle (codex execpolicy check, codex-cli 0.149.0) and compares the actual
rules-layer decision with the expected one.

Semantics (docs/WEEK1_BUILD_SPEC.md, non-negotiable):
  - A native no-match (matchedRules empty, decision omitted) is reported as
    actual = "unknown". It is NEVER normalized to "allow" (INV-005).
  - "unknown" means: no rules-layer decision; runtime outcome depends on
    approval policy + sandbox under the pinned configuration.
  - This tool reports policy-check results only. It does not certify any
    command or harness as secure, and it observes no runtime effects.

Stdlib only. Usage: python3 tools/run_fixtures.py [--fixtures FILE ...]
Writes a results JSON under evidence/reruns/ and prints a verdict table.
Exit code 0 if every fixture's actual decision equals its expected one.
With no --fixtures flag it replays the Day-2 41-case corpus unchanged.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pin import PINNED_CODEX_VERSION, codex_binary  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
# Pinned oracle, resolved through tools/pin.py: the sha256-verified vendored
# binary is preferred; the host path is only a fallback. Resolution verifies
# the pin and fails closed on mismatch (Day-5 binary-vendoring step).
CODEX = str(codex_binary())
PINNED_CODEX_VERSION = PINNED_CODEX_VERSION
FIXTURES_FILE = REPO / "fixtures" / "fixtures.json"
RERUNS_DIR = REPO / "evidence" / "reruns"


def load_fixtures(paths):
    """Load and merge fixture files. Default is the Day-2 41-case corpus.

    Day-3 additive change (backwards compatible): --fixtures accepts one or
    more fixture files (e.g. the protected-records family shards) and merges
    them; the runner logic itself is untouched (v0 semantics: unmatched is
    never normalized to allow).
    """
    merged = {"fixtures": []}
    files = []
    for p in paths:
        fp = Path(p)
        if not fp.is_absolute():
            fp = REPO / fp
        doc = json.loads(fp.read_text())
        merged["fixtures"].extend(doc["fixtures"])
        files.append(str(fp.relative_to(REPO)))
        for k in ("harness", "harness_version", "schema_version", "default_rules", "corpus_shard"):
            if k in doc and k not in merged:
                merged[k] = doc[k]
    merged["source_files"] = files
    return merged


def codex_version():
    out = subprocess.run([CODEX, "--version"], capture_output=True, text=True)
    return out.stdout.strip()


def run_fixture(fx):
    rules_path = REPO / fx["rules"]
    cmd = [CODEX, "execpolicy", "check", "--rules", str(rules_path)]
    if fx.get("resolve_host_executables"):
        cmd.append("--resolve-host-executables")
    cmd += ["--", *fx["argv"]]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    parsed = None
    actual = "unknown"
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = None
    if parsed is not None:
        matched = parsed.get("matchedRules") or []
        decision = parsed.get("decision")
        # No matched rules (or no decision) => no rules-layer decision.
        # Report "unknown"; never fall back to "allow".
        actual = decision if (matched and decision) else "unknown"

    return {
        "id": fx["id"],
        "argv": fx["argv"],
        "rules": fx["rules"],
        "resolve_host_executables": bool(fx.get("resolve_host_executables")),
        "maps_to": fx.get("maps_to"),
        "kind": fx.get("kind"),
        "pending_owner_decision": bool(fx.get("pending_owner_decision")),
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "raw_stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "matched_rules": len(parsed.get("matchedRules") or []) if parsed else 0,
        "expected": fx["expected"],
        "actual": actual,
        "verdict": "pass" if actual == fx["expected"] else "fail",
    }


def main():
    fixture_paths = [FIXTURES_FILE]
    if "--fixtures" in sys.argv:
        idx = sys.argv.index("--fixtures")
        fixture_paths = []
        for a in sys.argv[idx + 1:]:
            if a.startswith("--"):
                break
            fixture_paths.append(a)
    fixtures_doc = load_fixtures(fixture_paths)
    fixtures = fixtures_doc["fixtures"]
    detected_version = codex_version()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    results = [run_fixture(fx) for fx in fixtures]

    run_doc = {
        "run": {
            "tool": "tools/run_fixtures.py (v0 replay engine)",
            "timestamp_utc": timestamp,
            "harness": fixtures_doc.get("harness", "codex"),
            "codex_version_pinned": PINNED_CODEX_VERSION,
            "codex_version_detected": detected_version,
            "codex_binary": CODEX,
            "fixtures_files": fixtures_doc.get("source_files", ["fixtures/fixtures.json"]),
            "fixtures_schema_version": fixtures_doc.get("schema_version"),
            "default_rules_file": fixtures_doc.get("default_rules"),
            "layer": "rules-layer decision only (codex execpolicy check); "
                     "no approval-policy outcome and no observed effect",
            "unknown_semantics": "no rules-layer decision; runtime outcome "
                                 "depends on approval policy + sandbox under "
                                 "the pinned configuration",
        },
        "results": results,
    }

    RERUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RERUNS_DIR / f"rerun-{stamp}.json"
    out_path.write_text(json.dumps(run_doc, indent=2) + "\n")

    # Compact verdict table.
    print(f"codex: {detected_version} (pinned {PINNED_CODEX_VERSION})  "
          f"fixtures: {len(results)}  at {timestamp}")
    print(f"{'ID':<8} {'EXPECTED':<10} {'ACTUAL':<10} VERDICT")
    for r in results:
        mark = " *" if r["pending_owner_decision"] else ""
        print(f"{r['id']:<8} {r['expected']:<10} {r['actual']:<10} "
              f"{r['verdict']}{mark}")

    passes = sum(1 for r in results if r["verdict"] == "pass")
    fails = len(results) - passes
    counts = {}
    for r in results:
        counts[r["actual"]] = counts.get(r["actual"], 0) + 1
    counts_str = ", ".join(f"{k}={counts[k]}" for k in sorted(counts))
    print(f"\nverdicts: pass={passes} fail={fails}")
    print(f"actual decisions: {counts_str}")
    print("* = pending owner decision on the invariant-level expectation "
          "(INV-004); the rules-layer expectation encoded is \"unknown\".")
    print("unknown = no rules-layer decision; runtime outcome depends on "
          "approval policy + sandbox under the pinned configuration.")
    print(f"results written: {out_path.relative_to(REPO)}")

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
