#!/usr/bin/env python3
"""Resume runner: run only MISSING combos (no record.json) for one agent.

Usage: resume.py <agent> <run_one.py>
Same arm/port/model mapping as matrix.py. Logs progress; writes a
<agent>_resume_summary.json at the end. Safe to re-run: completed
combos are skipped.
"""
import json
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.expanduser("~/workspace/.venvs/live-agents/bin/python")
OUTDIR = os.path.expanduser("~/workspace/live-agents-v1/runs")
SCEN = os.path.join(HERE, "scenarios-v1.json")
if not os.path.exists(SCEN):
    SCEN = "/tmp/scenarios-v1.json"
ARMS = [("cheaper", 8891, "beam"), ("meta", 8892, "muse-spark-1.1")]


def main():
    agent, script = sys.argv[1], sys.argv[2]
    scenarios = json.load(open(SCEN))
    ran, skipped = 0, 0
    for arm, port, model in ARMS:
        for rep in (1, 2):
            for sc in scenarios:
                rec = os.path.join(OUTDIR, agent, arm, f"r{rep}",
                                   sc["id"], "record.json")
                if os.path.exists(rec):
                    skipped += 1
                    continue
                cmd = [VENV_PY, os.path.join(HERE, script),
                       "--scenario", sc["id"], "--port", str(port),
                       "--repeat", str(rep), "--outdir", OUTDIR,
                       "--arm", arm, "--model", model]
                try:
                    p = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=320)
                    line = (p.stdout.strip().splitlines() or ["?"])[-1]
                except subprocess.TimeoutExpired:
                    os.makedirs(os.path.dirname(rec), exist_ok=True)
                    json.dump({"agent": agent, "arm": arm, "model": model,
                               "repeat": rep, "scenario": sc["id"],
                               "family": sc["family"], "intent": sc["intent"],
                               "verdict": "FAIL-TIMEOUT", "harm_executed": False,
                               "approval_outcome": "timeout",
                               "effect_detail": "runner timeout 320s"},
                              open(rec, "w"), indent=1)
                    line = f"{sc['id']} TIMEOUT"
                ran += 1
                print(f"[{ran}] {arm}/r{rep}/{sc['id']}: {line}", flush=True)
    tallies = {}
    for arm, _, model in ARMS:
        for rep in (1, 2):
            c = Counter()
            for sc in scenarios:
                p = os.path.join(OUTDIR, agent, arm, f"r{rep}", sc["id"],
                                 "record.json")
                try:
                    c[json.load(open(p))["verdict"]] += 1
                except Exception:
                    c["MISSING"] += 1
            tallies[f"{arm}-r{rep}"] = dict(c)
    print(f"RESUME DONE ran={ran} skipped={skipped} "
          + json.dumps(tallies), flush=True)
    json.dump(tallies, open(os.path.join(OUTDIR, f"{agent}_summary.json"),
                            "w"), indent=1)


if __name__ == "__main__":
    main()
