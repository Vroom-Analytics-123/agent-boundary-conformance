#!/usr/bin/env python3
"""Merge pass for the Gemini full matrix: re-tally from record.json files
on disk (never trust a stale tallies file). Existing 14 = r1/r2 records
only (V1-01/r1-halted-first-attempt explicitly excluded). New 34 = the
17 full-run variants x r1/r2. Writes tallies-new.json + tallies-full.json
under runs/series/. Does not touch tallies.json or SUMMARY.md.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXISTING = ["V1-01", "V1-02", "V1-03", "V1-04", "V1-05", "V1-06", "V1-23"]
NEW = ["V1-07", "V1-08", "V1-09", "V1-10", "V1-11", "V1-12", "V1-13",
       "V1-14", "V1-15", "V1-16", "V1-17", "V1-18", "V1-19", "V1-20",
       "V1-21", "V1-22", "V1-24"]


def load(variant, rep):
    return json.loads((HERE / variant / rep / "record.json").read_text())


def tally(variants):
    per, tot, missing = {}, Counter(), []
    for v in variants:
        c = Counter()
        for rep in ("r1", "r2"):
            p = HERE / v / rep / "record.json"
            if not p.exists():
                missing.append(f"{v}/{rep}")
                continue
            c[load(v, rep)["verdict"]] += 1
        per[v] = dict(c)
        tot.update(c)
    return {"cells": sum(tot.values()), "totals": dict(tot),
            "per_variant": per, "missing": missing}


def main():
    new = tally(NEW)
    full = tally(EXISTING + NEW)
    new_out = {"cells_completed": new["cells"], "cells_planned": 34,
               "totals": new["totals"], "per_variant": new["per_variant"],
               "missing": new["missing"],
               "model": "gemini-2.5-flash", "policy": "runs/series/policy-series.toml"}
    full_out = {"cells_completed": full["cells"], "cells_planned": 48,
                "totals": full["totals"], "per_variant": full["per_variant"],
                "missing": full["missing"],
                "model": "gemini-2.5-flash", "policy": "runs/series/policy-series.toml",
                "existing_14_note": "r1/r2 records only; V1-01/r1-halted-first-attempt excluded"}
    (HERE / "tallies-new.json").write_text(json.dumps(new_out, indent=2) + "\n")
    (HERE / "tallies-full.json").write_text(json.dumps(full_out, indent=2) + "\n")
    print(json.dumps(full_out, indent=2))
    if new["missing"] or full["missing"]:
        print("MISSING:", new["missing"] or full["missing"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
