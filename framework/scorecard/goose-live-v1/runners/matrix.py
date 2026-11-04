#!/usr/bin/env python3
"""Run the full Goose live v1 matrix: 24 scenarios x 3 profiles, r1.

Sequential only (permission.yaml + GOOSE_PATH_ROOT are per-run, but the
proxy and the model are shared; sequential runs keep logs attributable).
Supports --only-missing to resume after an interruption.
"""
import argparse
import json
import os
import subprocess
import sys

BASE = "/home/hatch/workspace/goose-live-v1"
PROFILES = ["default", "hardened", "deny"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--outdir", default=os.path.join(BASE, "runs"))
    ap.add_argument("--only-missing", action="store_true")
    ap.add_argument("--scenarios", default="")
    ap.add_argument("--profiles", default="")
    args = ap.parse_args()

    scenarios = [s["id"] for s in
                 json.load(open("/home/hatch/workspace/live-agents-v1/scenarios-v1.json"))]
    if args.scenarios:
        keep = set(args.scenarios.split(","))
        scenarios = [s for s in scenarios if s in keep]
    profiles = args.profiles.split(",") if args.profiles else PROFILES
    total = len(profiles) * len(scenarios)
    done = 0
    for prof in profiles:
        for sc in scenarios:
            done += 1
            rec = os.path.join(args.outdir, prof, f"r{args.repeat}", sc,
                               "record.json")
            if args.only_missing and os.path.exists(rec):
                print(f"[{done}/{total}] SKIP {prof} {sc} (record exists)")
                continue
            print(f"[{done}/{total}] RUN {prof} {sc}", flush=True)
            p = subprocess.run(
                [sys.executable, os.path.join(BASE, "goose_run_one.py"),
                 "--profile", prof, "--scenario", sc,
                 "--repeat", str(args.repeat), "--outdir", args.outdir],
                capture_output=True, text=True, timeout=1200)
            try:
                d = json.loads(p.stdout.strip().splitlines()[-1]
                               if False else p.stdout)
                print(f"    -> {d['verdict']} effect={d['effect_happened']} "
                      f"gate={d['gate_evidence']} approval={d['approval_outcome']}",
                      flush=True)
            except Exception:
                print("    -> RUNNER OUTPUT UNPARSEABLE rc=", p.returncode,
                      flush=True)
                print(p.stdout[-500:], flush=True)
                print(p.stderr[-500:], flush=True)
    print("MATRIX DONE")


if __name__ == "__main__":
    main()
