#!/bin/bash
# Codex v1 live matrix driver — sequential, resumable.
# Shared absolute-path fixtures (/tmp/sbx, /home/user/...) are reset per
# cell by run_one.py, so cells MUST NOT run in parallel. A cell whose
# record.json already exists is skipped, so re-running this script after
# an interruption resumes instead of restarting.
set -u
cd ~/workspace/codex-live-v1-matrix || exit 1
IDS=$(python3 -c "import json; print(' '.join(s['id'] for s in json.load(open('/tmp/scenarios-clean.json'))))")
: > progress.log
for rep in 1 2; do
  for id in $IDS; do
    out="runs/r$rep/$id"
    if [ -f "$out/record.json" ]; then
      echo "SKIP r$rep $id (record exists)" | tee -a progress.log
      continue
    fi
    echo "START r$rep $id $(date -u +%H:%M:%S)" | tee -a progress.log
    if python3 run_one.py --scenario "$id" --repeat "$rep" \
        --sandbox workspace-write --model gpt-5.6-sol --out "$out" >> progress.log 2>&1; then
      echo "DONE r$rep $id" | tee -a progress.log
    else
      echo "CELL-FAILED r$rep $id (runner exit nonzero; continuing)" | tee -a progress.log
    fi
  done
done
echo "MATRIX COMPLETE $(date -u +%FT%TZ)" | tee -a progress.log
python3 -c "
import json, pathlib
n = sum(1 for p in pathlib.Path('runs').rglob('record.json'))
print(f'record.json files present: {n} (expected 48)')
"
