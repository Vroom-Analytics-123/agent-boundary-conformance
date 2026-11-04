#!/usr/bin/env python3
"""Run the full v1 matrix for OpenCode: 24 scenarios x profiles.

Sequential only (opencode runs share one oc-home sqlite db and one
proxy; concurrent runs would interleave logs). Resume-safe: a cell
with an existing record.json is skipped. Usage:
  python3 matrix.py [--profiles default,hardened] [--repeat 1]
Logs to runs/matrix.log.
"""
import argparse
import json
import os
import subprocess
import sys

BASE = "/home/hatch/workspace/opencode-live-v1"
SCEN = json.load(open("/home/hatch/workspace/live-agents-v1/scenarios-v1.json"))
IDS = [s["id"] for s in SCEN]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="default,hardened")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    profiles = args.profiles.split(",")
    only = set(args.only.split(",")) if args.only else None
    log = open(os.path.join(BASE, "runs", "matrix.log"), "a")
    for profile in profiles:
        for sid in IDS:
            if only and sid not in only:
                continue
            rec = os.path.join(BASE, "runs", profile, f"r{args.repeat}",
                                sid, "record.json")
            if os.path.exists(rec):
                print(f"SKIP {profile} {sid} (record exists)", flush=True)
                continue
            print(f"RUN {profile} {sid}", flush=True)
            log.write(f"RUN {profile} {sid}\n"); log.flush()
            p = subprocess.run(
                [sys.executable, os.path.join(BASE, "oc_run_one.py"),
                 "--scenario", sid, "--profile", profile,
                 "--repeat", str(args.repeat)],
                capture_output=True, text=True)
            out = (p.stdout.strip() or p.stderr.strip()[-500:])
            print(out, flush=True)
            log.write(out + "\n"); log.flush()
    log.close()
    print("MATRIX DONE", flush=True)


if __name__ == "__main__":
    main()
