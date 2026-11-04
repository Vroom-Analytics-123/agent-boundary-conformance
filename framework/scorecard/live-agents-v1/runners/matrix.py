#!/usr/bin/env python3
"""Generic matrix runner: scenarios x arms x repeats for one agent driver.
Usage: matrix.py <agent> <run_one.py>  (e.g. matrix.py langgraph langgraph_run_one.py)
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
    agent, script = sys.argv[1], sys.argv[2]
    scenarios = json.load(open("/tmp/scenarios-v1.json"))
    total = 0
    for arm, port, model in ARMS:
        for rep in (1, 2):
            for sc in scenarios:
                total += 1
                cmd = [VENV_PY, os.path.join(HERE, script),
                       "--scenario", sc["id"], "--port", str(port),
                       "--repeat", str(rep), "--outdir", OUTDIR,
                       "--arm", arm, "--model", model]
                try:
                    p = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
                    line = (p.stdout.strip().splitlines() or ["?"])[-1]
                except subprocess.TimeoutExpired:
                    rec_path = os.path.join(OUTDIR, agent, arm, f"r{rep}",
                                            sc["id"], "record.json")
                    os.makedirs(os.path.dirname(rec_path), exist_ok=True)
                    json.dump({"agent": agent, "arm": arm, "model": model,
                               "repeat": rep, "scenario": sc["id"],
                               "family": sc["family"], "intent": sc["intent"],
                               "verdict": "FAIL-TIMEOUT", "harm_executed": False,
                               "approval_outcome": "timeout",
                               "effect_detail": "runner timeout 320s"},
                              open(rec_path, "w"), indent=1)
                    line = f"{sc['id']} TIMEOUT"
                print(f"[{total}] {line}", flush=True)
    tallies = {}
    for arm, _, model in ARMS:
        for rep in (1, 2):
            c = Counter()
            for sc in scenarios:
                p = os.path.join(OUTDIR, agent, arm, f"r{rep}", sc["id"], "record.json")
                try:
                    c[json.load(open(p))["verdict"]] += 1
                except Exception:
                    c["MISSING"] += 1
            tallies[f"{arm}-r{rep}"] = dict(c)
    print("SUMMARY " + json.dumps(tallies), flush=True)
    json.dump(tallies, open(os.path.join(OUTDIR, f"{agent}_summary.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
