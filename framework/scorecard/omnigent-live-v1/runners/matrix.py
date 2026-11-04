#!/usr/bin/env python3
"""Matrix runner for Omnigent live v1 (fresh implementation).

Starts one fresh proxy per arm, then runs every requested cell through
run_one.py (fresh Omnigent server per cell). Skips cells whose record.json
already carries a verdict (resume-safe). Writes tallies.json + SUMMARY.md.

Usage:
  matrix.py --smoke
  matrix.py --arms cheaper,meta --repeats 1,2
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_PY = HERE.parent / ".venvs/omnigent-live-v1/bin/python"
ARMS = {"cheaper": ("8895", "beam-free"), "meta": ("8896", "muse-spark-1.1")}


def wait_health(port, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health",
                    timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(2)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="cheaper,meta")
    ap.add_argument("--repeats", default="1,2")
    ap.add_argument("--scenarios", default="all")
    ap.add_argument("--out", default=str(HERE / "runs"))
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-policies-control", action="store_true")
    args = ap.parse_args()

    scenarios = json.loads((HERE / "scenarios-v1.json").read_text())
    if args.smoke:
        wanted = ["V1-01", "V1-21", "V1-15"]
        arms = ["cheaper"]
        repeats = [1]
    else:
        wanted = ([s["id"] for s in scenarios] if args.scenarios == "all"
                  else args.scenarios.split(","))
        arms = args.arms.split(",")
        repeats = [int(x) for x in args.repeats.split(",")]
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    proxies = []
    try:
        for arm in arms:
            port, model = ARMS[arm]
            log = open(out_root / f"proxy-{arm}.log", "w")
            p = subprocess.Popen(
                [sys.executable, str(HERE / "proxy_fresh.py"),
                 "--port", port, "--arm", arm, "--model", model],
                stdout=log, stderr=subprocess.STDOUT)
            proxies.append(p)
            if not wait_health(port):
                print(f"proxy {arm} did not come up; aborting")
                return 1
            print(f"proxy {arm} up on {port} model={model}")

        cells = []
        for arm in arms:
            port, model = ARMS[arm]
            for sid in wanted:
                for rep in repeats:
                    cells.append((arm, port, model, sid, rep, False))
        if args.no_policies_control or args.smoke:
            cells.append(("cheaper", ARMS["cheaper"][0],
                          ARMS["cheaper"][1], "V1-01", 0, True))

        for arm, port, model, sid, rep, no_pol in cells:
            tag = f"{arm}-r{rep}" + ("-nopolicy" if no_pol else "")
            cell_dir = out_root / tag / sid
            rec_path = cell_dir / "record.json"
            if rec_path.exists():
                try:
                    rec = json.loads(rec_path.read_text())
                    # Skip completed cells, but retry deterministic
                    # setup/server failures after a driver fix.
                    if rec.get("verdict") and not (
                            rec.get("error") or "").startswith(
                                "setup/server"):
                        print(f"skip {tag}/{sid} (record exists)")
                        continue
                except Exception:
                    pass
            print(f"run {tag}/{sid} ...", flush=True)
            r = subprocess.run(
                [str(VENV_PY), str(HERE / "run_one.py"),
                 "--scenario", sid, "--arm", arm, "--arm-model", model,
                 "--repeat", str(rep), "--proxy-port", port,
                 "--out", str(cell_dir), "--timeout", str(args.timeout)]
                + (["--no-policies"] if no_pol else []),
                capture_output=True, text=True,
                timeout=args.timeout + 240)
            line = (r.stdout.strip().splitlines() or ["<no output>"])[-1]
            print(f"  {line}")
            if r.returncode != 0:
                print(f"  !! run_one exit {r.returncode}: "
                      f"{r.stderr.strip()[-500:]}")

        # Tallies
        tallies = {}
        for arm in arms:
            for rep in repeats:
                tag = f"{arm}-r{rep}"
                for sid in wanted:
                    rec_path = out_root / tag / sid / "record.json"
                    v = None
                    if rec_path.exists():
                        try:
                            v = json.loads(rec_path.read_text()).get("verdict")
                        except Exception:
                            pass
                    tallies.setdefault(arm, {}).setdefault(rep, {})[sid] = v
        (out_root / "tallies.json").write_text(json.dumps(tallies, indent=1))
        lines = ["# Omnigent live v1 — tallies (fresh run)",
                 "",
                 "Cells: 24 v1 scenarios x arms x repeats. "
                 "Verdict taxonomy: PASS / FAIL-EXECUTED / FAIL-NO-DECISION / "
                 "FAIL-OVERBLOCK / FAIL-INCOMPLETE / FAIL-TIMEOUT.",
                 ""]
        for arm in arms:
            for rep in repeats:
                row = tallies[arm][rep]
                counts = {}
                for v in row.values():
                    counts[v] = counts.get(v, 0) + 1
                lines.append(f"## {arm} repeat {rep}: {counts}")
                for sid in wanted:
                    lines.append(f"- {sid}: {row[sid]}")
                lines.append("")
        (out_root / "SUMMARY-tallies.md").write_text("\n".join(lines))
        print("tallies written")
        return 0
    finally:
        for p in proxies:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
