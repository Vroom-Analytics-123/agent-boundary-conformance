#!/usr/bin/env python3
"""Full Amp live matrix: 24 v1 scenarios x 2 repeats, sequential, fail-closed.
Stops the whole matrix on any credit-error signal. Logs progress to matrix.log."""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCEN = json.load(open(Path.home() / "workspace" / "omnigent-live-v1" / "scenarios-v1.json"))
LOG = HERE / "matrix.log"


def log(msg):
    line = time.strftime("%Y-%m-%dT%H:%M:%S") + " " + msg
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main():
    for rep in (1, 2):
        for sc in SCEN:
            out = HERE / "runs" / f"medium-r{rep}" / sc["id"]
            t0 = time.time()
            r = subprocess.run([sys.executable, str(HERE / "run_one.py"),
                                "--scenario", sc["id"], "--repeat", str(rep),
                                "--out", str(out)],
                               capture_output=True, text=True)
            dt = time.time() - t0
            if r.returncode != 0:
                log(f"DRIVER-FAIL {sc['id']} r{rep} ({dt:.0f}s)\n{r.stdout[-1000:]}\n{r.stderr[-1000:]}")
                log("MATRIX STOPPED on driver failure")
                return 2
            rec = json.loads((out / "record.json").read_text())
            log(f"DONE {sc['id']} r{rep} ({dt:.0f}s) exit={rec['exit_code']} "
                f"timeout={rec['timed_out']} tools={len(rec['tool_calls'])} "
                f"credit={rec['credit_error_signals']} post={rec['post']}")
            if rec["credit_error_signals"]:
                log("MATRIX STOPPED on credit-error signal (partial results stand)")
                return 3
    log("MATRIX COMPLETE 48/48")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
