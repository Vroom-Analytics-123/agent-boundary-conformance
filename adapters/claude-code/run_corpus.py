#!/usr/bin/env python3
"""
Run the full 41-fixture corpus (public 21 + held-out 20) plus the
protected-asset family through the Claude Code T2 evaluation engine.

Usage:  python3 run_corpus.py

Writes:
  adapters/claude-code/results.json              (committed: public per-case
                                                  records + held-out AGGREGATE
                                                  COUNTS ONLY, per
                                                  fixtures/HELDOUT_POLICY.md)
  adapters/claude-code/results_heldout.local.json (GITIGNORED: held-out
                                                  per-case detail, local only)

Command string formation: the corpus passes argv; the harness would see the
command text as written, so the engine evaluates " ".join(argv).
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from evaluate import evaluate  # noqa: E402

VERSION_UNDER_TEST = "2.1.307"
ROUTE = ("t2-config-evaluation (no native offline decision oracle exists "
         "at %s)" % VERSION_UNDER_TEST)
EVIDENCE_CLASS = "T2-evaluation (never interrogated)"

RULES_TO_POLICY = {
    "fixtures/policies/default.rules": "policy/settings.json",
    "fixtures/policies/protected_records.rules": "policy/protected.json",
    "evidence/day1-baseline-2026-10-21/prec_a.rules": "policy/prec_a.json",
    "evidence/day1-baseline-2026-10-21/prec_b.rules": "policy/prec_b.json",
    "evidence/day1-baseline-2026-10-21/prec_c.rules": "policy/prec_c.json",
    "evidence/day1-baseline-2026-10-21/prec_d.rules": "policy/prec_d.json",
    "evidence/day1-baseline-2026-10-21/prec_e.rules": "policy/prec_e.json",
    "evidence/day1-baseline-2026-10-21/prec_f.rules": "policy/prec_f.json",
}

# Codex T1 native actuals (latest reruns, for the divergence comparison).
CODEX_NATIVE = {}
for rerun in ("evidence/reruns/rerun-20261022T160502Z.json",
              "evidence/reruns/rerun-20261022T160536Z.json"):
    path = os.path.join(REPO, rerun)
    if os.path.exists(path):
        for res in json.load(open(path))["results"]:
            CODEX_NATIVE[res["id"]] = res["actual"]


def evaluate_fixture(fixture, policy_cache):
    policy_rel = RULES_TO_POLICY[fixture["rules"]]
    if policy_rel not in policy_cache:
        policy_cache[policy_rel] = json.load(
            open(os.path.join(HERE, policy_rel)))["permissions"]
    command = " ".join(fixture["argv"])
    result = evaluate(command, policy_cache[policy_rel])
    record = {
        "fixture_id": fixture["id"],
        "shard": fixture.get("_shard", "?"),
        "argv": fixture["argv"],
        "command_string": command,
        "policy_file": "adapters/claude-code/" + policy_rel,
        "matched_rules": result["matched_rules"],
        "decision": result["decision"],
        "layer": result["layer"],
        "notes": result["note"],
        "evidence_class": EVIDENCE_CLASS,
        "expected": fixture["expected"],
        "expected_match": result["decision"] == fixture["expected"],
        "codex_t1_native": CODEX_NATIVE.get(fixture["id"]),
        "diverges_from_codex_native":
            CODEX_NATIVE.get(fixture["id"]) is not None
            and result["decision"] != CODEX_NATIVE.get(fixture["id"]),
    }
    if fixture.get("resolve_host_executables"):
        record["notes"] += (" The fixture's resolve_host_executables=True is "
                            "a Codex-side concept; Claude Code has no "
                            "documented path-resolution step (docs: a rule "
                            "does not match the same program invoked in a "
                            "different form), so the command is evaluated "
                            "as written.")
    return record


def main():
    policy_cache = {}
    public, heldout, protected = [], [], []

    for shard, path, sink in (
        ("public", "fixtures/corpus_public.json", public),
        ("heldout", "fixtures/corpus_heldout.json", heldout),
    ):
        corpus = json.load(open(os.path.join(REPO, path)))
        for f in corpus["fixtures"]:
            f["_shard"] = shard
            sink.append(evaluate_fixture(f, policy_cache))

    prot = json.load(open(os.path.join(
        REPO, "fixtures/protected_records_public.json")))
    for f in prot["fixtures"]:
        f["_shard"] = "public-protected"
        protected.append(evaluate_fixture(f, policy_cache))

    # Supplementary probe: the vendor-documented tree idiom for protecting a
    # directory (Read(./secrets/**) pattern applied to Bash), measured
    # separately from the checked-in mechanical translation.
    tree_policy = {"allow": ["Bash(ls /records/health *)"], "ask": [],
                   "deny": ["Bash(rm -rf /records/health)",
                            "Bash(rm -rf /records/health/*)",
                            "Bash(rm /records/health)",
                            "Bash(rm /records/health/*)"]}
    supplementary = []
    for rec in protected:
        cmd = rec["command_string"]
        res = evaluate(cmd, tree_policy)
        supplementary.append({
            "fixture_id": rec["fixture_id"],
            "command_string": cmd,
            "policy": "supplementary tree idiom (not checked in)",
            "decision": res["decision"],
            "notes": res["note"],
            "evidence_class": EVIDENCE_CLASS,
        })

    engine_sha256 = hashlib.sha256(
        open(os.path.join(HERE, "evaluate.py"), "rb").read()).hexdigest()
    heldout_shard_sha256 = json.load(
        open(os.path.join(REPO, "fixtures/corpus_manifest.json"))
    )["held_out"]["sha256"]

    def counts(records):
        c = {}
        for r in records:
            c[r["decision"]] = c.get(r["decision"], 0) + 1
        return c

    results = {
        "harness": "claude-code",
        "version_under_test": VERSION_UNDER_TEST,
        "route": ROUTE,
        "evidence_class": EVIDENCE_CLASS,
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "engine_sha256": engine_sha256,
        "policy_files": {
            k: "adapters/claude-code/" + v
            for k, v in RULES_TO_POLICY.items()
        },
        "public_cases": public,
        "protected_asset_cases": protected,
        "supplementary_tree_idiom_probe": supplementary,
        "heldout_summary": {
            "count": len(heldout),
            "aggregate_decision_counts": counts(heldout),
            "shard_sha256": heldout_shard_sha256,
            "expected_match_count": sum(
                1 for r in heldout if r["expected_match"]),
            "note": ("Per fixtures/HELDOUT_POLICY.md: held-out per-case "
                     "argv/decisions are NEVER committed or quoted. "
                     "Aggregate counts only. Per-case detail lives in the "
                     "gitignored results_heldout.local.json."),
        },
    }
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2)
        fh.write("\n")

    heldout_local = {
        "harness": "claude-code",
        "version_under_test": VERSION_UNDER_TEST,
        "route": ROUTE,
        "evidence_class": EVIDENCE_CLASS,
        "generated_utc": results["generated_utc"],
        "engine_sha256": engine_sha256,
        "heldout_cases": heldout,
        "warning": ("GITIGNORED local-only file. Never commit, never quote "
                    "per-case content. See fixtures/HELDOUT_POLICY.md."),
    }
    with open(os.path.join(HERE, "results_heldout.local.json"), "w") as fh:
        json.dump(heldout_local, fh, indent=2)
        fh.write("\n")

    print("public: %d, heldout: %d, protected: %d"
          % (len(public), len(heldout), len(protected)))
    print("heldout counts:", counts(heldout))
    print("public expected_match: %d/%d"
          % (sum(1 for r in public if r["expected_match"]), len(public)))
    print("protected expected_match: %d/%d"
          % (sum(1 for r in protected if r["expected_match"]),
             len(protected)))
    divs = [(r["fixture_id"], r["codex_t1_native"], r["decision"])
            for r in public + heldout + protected
            if r["diverges_from_codex_native"]]
    print("divergences from codex native: %d" % len(divs))
    for d in divs:
        print("  ", d)


if __name__ == "__main__":
    main()
