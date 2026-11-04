#!/usr/bin/env python3
"""Full Strands matrix: 24 scenarios x 2 arms x 2 repeats = 96 runs.
Each run is a subprocess with a 320s timeout; timeouts record as
FAIL-TIMEOUT rows so the matrix never stalls on one scenario.
Safe to re-run: every run rebuilds fresh scratch and overwrites its record.
"""
import json
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.expanduser("~/workspace/.venvs/live-agents/bin/python")
OUTDIR = os.path.expanduser("~/workspace/live-agents-v1/runs")
ARMS = [("cheaper", 8891, "beam"), ("meta", 8892, "muse-spark-1.1")]

def main():
    scenarios = json.load(open("/tmp/scenarios-v1.json"))
    total = 0
    for arm, port, model in ARMS:
        for rep in (1, 2):
            for sc in scenarios:
                total += 1
                cmd = [VENV_PY, os.path.join(HERE, "strands_run_one.py"),
                       "--scenario", sc["id"], "--port", str(port),
                       "--repeat", str(rep), "--outdir", OUTDIR,
                       "--arm", arm, "--model", model]
                try:
                    p = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
                    line = (p.stdout.strip().splitlines() or ["?"])[-1]
                except subprocess.TimeoutExpired:
                    rec_path = os.path.join(OUTDIR, "strands", arm, f"r{rep}",
                                            sc["id"], "record.json")
                    os.makedirs(os.path.dirname(rec_path), exist_ok=True)
                    rec = {"agent": "strands", "arm": arm, "model": model,
                           "repeat": rep, "scenario": sc["id"],
                           "family": sc["family"], "intent": sc["intent"],
                           "verdict": "FAIL-TIMEOUT", "harm_executed": False,
                           "approval_outcome": "timeout",
                           "effect_detail": "runner timeout 320s"}
                    json.dump(rec, open(rec_path, "w"), indent=1)
                    line = f"{sc['id']} TIMEOUT"
                print(f"[{total}] {line}", flush=True)
    # summary
    tallies = {}
    for arm, _, model in ARMS:
        for rep in (1, 2):
            c = Counter()
            for sc in scenarios:
                p = os.path.join(OUTDIR, "strands", arm, f"r{rep}", sc["id"], "record.json")
                try:
                    c[json.load(open(p))["verdict"]] += 1
                except Exception:
                    c["MISSING"] += 1
            tallies[f"{arm}-r{rep}"] = dict(c)
    print("SUMMARY " + json.dumps(tallies), flush=True)
    json.dump(tallies, open(os.path.join(OUTDIR, "strands_summary.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
