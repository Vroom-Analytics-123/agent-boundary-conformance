#!/usr/bin/env python3
"""Agent Boundary Regression Check (demo): run one fixture set under TWO
codex builds and report per-fixture decision changes.

This is the wedge demo for grant reviewers: the same corpus + the same
policy, two harness versions, and a plain list of decisions that changed
between versions — each decision labelled REPRO (measured, never asserted).

Usage:
  python3 tools/diff_codex_versions.py <binary-a> <binary-b>
      [--fixtures FILE] [--out FILE]

Output JSON: per-fixture {argv, decision_a, decision_b, matched_a,
matched_b, changed, parse notes}; summary counts. Decisions follow the
project's native serialization (schemas_v1.serialize_native_decision):
a native no-match is "unknown", never "allow". If a binary's native output
does not parse, the decision is recorded as "unparseable-native-output"
(honest, not silent).

Stdlib only. Neither binary needs to be the pinned one; labels come from
`<binary> --version`.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402


def binary_label(binary: str) -> str:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True,
                             text=True, timeout=60)
        return out.stdout.strip() or binary
    except Exception as e:  # noqa: BLE001
        return f"{binary} (version query failed: {e})"


def run_fixture(binary: str, fx: dict) -> dict:
    rules_path = REPO / fx["rules"]
    cmd = [binary, "execpolicy", "check", "--rules", str(rules_path)]
    if fx.get("resolve_host_executables"):
        cmd.append("--resolve-host-executables")
    cmd += ["--", *fx["argv"]]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        raw = proc.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return {"decision": "error", "matched_rules": 0, "parsed": False,
                "note": f"execution failed: {e}", "raw_truncated": ""}
    if not raw:
        return {"decision": "unknown", "matched_rules": 0, "parsed": True,
                "note": "empty stdout -> no-match -> unknown",
                "raw_truncated": ""}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"decision": "unparseable-native-output", "matched_rules": 0,
                "parsed": False,
                "note": "stdout is not JSON; cannot derive a decision",
                "raw_truncated": raw[:200]}
    try:
        ser = S.serialize_native_decision(raw)
        matched = len(parsed.get("matchedRules") or []) if isinstance(parsed, dict) else 0
        return {"decision": ser["decision"], "matched_rules": matched,
                "parsed": True, "note": "", "raw_truncated": raw[:200]}
    except Exception as e:  # noqa: BLE001
        return {"decision": "unparseable-native-output", "matched_rules": 0,
                "parsed": False, "note": f"serialization failed: {e}",
                "raw_truncated": raw[:200]}


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: diff_codex_versions.py <binary-a> <binary-b> "
                 "[--fixtures FILE] [--out FILE]")
    bin_a, bin_b = sys.argv[1], sys.argv[2]
    fixtures_file = REPO / "fixtures" / "fixtures.json"
    out_file = None
    if "--fixtures" in sys.argv:
        fixtures_file = Path(sys.argv[sys.argv.index("--fixtures") + 1])
        if not fixtures_file.is_absolute():
            fixtures_file = REPO / fixtures_file
    if "--out" in sys.argv:
        out_file = Path(sys.argv[sys.argv.index("--out") + 1])

    fixtures = json.loads(fixtures_file.read_text())["fixtures"]
    label_a, label_b = binary_label(bin_a), binary_label(bin_b)
    print(f"A: {label_a}\nB: {label_b}\nfixtures: {len(fixtures)}")

    rows = []
    for fx in fixtures:
        ra = run_fixture(bin_a, fx)
        rb = run_fixture(bin_b, fx)
        changed = ra["decision"] != rb["decision"]
        rows.append({
            "id": fx["id"],
            "argv": fx["argv"],
            "rules": fx["rules"],
            "decision_a": ra["decision"],
            "decision_b": rb["decision"],
            "matched_rules_a": ra["matched_rules"],
            "matched_rules_b": rb["matched_rules"],
            "changed": changed,
            "evidence_class": "REPRO",
            "notes": [n for n in (ra["note"], rb["note"]) if n],
        })
        flag = "  <-- CHANGED" if changed else ""
        print(f"{fx['id']:<8} A={ra['decision']:<10} B={rb['decision']:<10}{flag}")

    changed_rows = [r for r in rows if r["changed"]]
    unparseable = [r for r in rows
                   if "unparseable" in (r["decision_a"], r["decision_b"])]
    doc = {
        "tool": "tools/diff_codex_versions.py (Agent Boundary Regression Check demo)",
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "binary_a": {"path": bin_a, "label": label_a},
        "binary_b": {"path": bin_b, "label": label_b},
        "fixtures_file": str(fixtures_file),
        "summary": {
            "fixtures": len(rows),
            "changed": len(changed_rows),
            "unchanged": len(rows) - len(changed_rows),
            "unparseable_native_output": len(unparseable),
        },
        "changed": changed_rows,
        "rows": rows,
    }
    if out_file:
        out_file.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"\nwrote {out_file}")
    print(f"\nsummary: {len(changed_rows)}/{len(rows)} decisions changed; "
          f"{len(unparseable)} unparseable native outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
