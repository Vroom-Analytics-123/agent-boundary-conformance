#!/usr/bin/env python3
"""Tally opencode-live-v1 records into per-cell verdict counts."""
import json
import os
import sys
from collections import Counter

BASE = "/home/hatch/workspace/opencode-live-v1/runs"


def main():
    for profile in ("default", "hardened"):
        for repeat in (1, 2):
            cells = {}
            for sid in [f"V1-{i:02d}" for i in range(1, 25)]:
                p = os.path.join(BASE, profile, f"r{repeat}", sid,
                                 "record.json")
                if os.path.exists(p):
                    cells[sid] = json.load(open(p))["verdict"]
            if cells:
                print(profile, f"r{repeat}", dict(Counter(cells.values())),
                      f"({len(cells)}/24 cells)")
    # Detail dump for one profile/repeat
    if len(sys.argv) > 2:
        profile, repeat = sys.argv[1], sys.argv[2]
        for sid in [f"V1-{i:02d}" for i in range(1, 25)]:
            p = os.path.join(BASE, profile, f"r{repeat}", sid, "record.json")
            if os.path.exists(p):
                r = json.load(open(p))
                print(sid, r["verdict"], "| effect:", r["effect_happened"],
                      "| deny:", r["deny_evidence"],
                      "| approval:", r["approval_outcome"],
                      "| completed:", r["completed"],
                      "| timeout:", r["timed_out"])


if __name__ == "__main__":
    main()
