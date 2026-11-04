#!/usr/bin/env python3
"""Recompute verdicts for already-run cells from raw stream.jsonl files.

Why this exists: the first tally pass misclassified denials whose
tool_result wording was "needs approval" (Claude Code's built-in
working-directory approval) instead of "denied". The corrected judge logic
in run_series.py (tool_result_meta.non_execution_kind is authoritative)
is applied here WITHOUT re-running any model call.

For each cell under runs/<mode>/, this script:
  - re-parses stream.jsonl with run_series.parse_stream,
  - re-judges with run_series.judge,
  - preserves the original verdict as verdict_original,
  - writes the corrected verdict fields back into record.json.

Usage: python3 retally.py --mode matrix   (also: --mode smoke)
"""

import argparse
import glob
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from run_series import judge, load_scenarios, parse_stream  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["smoke", "matrix"])
    args = parser.parse_args()
    scenarios = {s["id"]: s for s in load_scenarios()}
    changed = []
    tally = {}
    n = 0
    for record_path in sorted(
        glob.glob(os.path.join(BASE, "runs", args.mode, "*", "r*", "record.json"))
    ):
        cell_dir = os.path.dirname(record_path)
        with open(record_path) as fh:
            record = json.load(fh)
        scenario = scenarios[record["scenario"]]
        (
            tool_uses,
            tool_results,
            tool_result_meta,
            perm_decisions,
            perm_denied_events,
            texts,
            usage,
            n_lines,
        ) = parse_stream(os.path.join(cell_dir, "stream.jsonl"))
        judged = judge(
            scenario,
            record["command"],
            cell_dir,
            tool_uses,
            tool_results,
            tool_result_meta,
            perm_decisions,
            perm_denied_events,
            record["effect_checks"],
            record["timed_out"],
            record["exit_code"],
            texts,
        )
        old_verdict = record["verdict"]
        old_kind = record["decision_kind"]
        record["verdict_original"] = old_verdict
        record["decision_kind_original"] = old_kind
        record["verdict"] = judged["verdict"]
        record["decision_kind"] = judged["decision_kind"]
        record["scenario_executed"] = judged["scenario_executed"]
        record["scenario_denied"] = judged["scenario_denied"]
        record["harm_evidence"] = judged["harm_evidence"]
        record["evasion"] = judged["evasion"]
        record["tool_result_meta"] = tool_result_meta
        record["verdict_corrected"] = old_verdict != judged["verdict"] or (
            old_kind != judged["decision_kind"]
        )
        record["correction_note"] = (
            "Verdict recomputed from raw stream with corrected classifier "
            "(tool_result_meta.non_execution_kind authoritative; "
            "'needs approval' working-directory denials counted as denials, "
            "not executions)."
            if record["verdict_corrected"]
            else ""
        )
        with open(record_path, "w") as fh:
            json.dump(record, fh, indent=2)
        tally[record["verdict"]] = tally.get(record["verdict"], 0) + 1
        n += 1
        if record["verdict_corrected"]:
            changed.append(
                f"{record['scenario']} r{record['repeat']}: "
                f"{old_verdict} ({old_kind}) -> {record['verdict']} "
                f"({record['decision_kind']})"
            )
    print(json.dumps({"cells": n, "tally": tally}))
    print("CHANGED:")
    for line in changed:
        print("  " + line)


if __name__ == "__main__":
    main()
