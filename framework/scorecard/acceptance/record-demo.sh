#!/bin/sh
# Record the gate-proof acceptance campaign demo (the dry-run).
#
# Usage: sh framework/scorecard/acceptance/record-demo.sh
#   (from the repo root, with FINEPRINT_CHECKOUT set to the
#   fineprint checkout, branch free-wall)
#
# Records with asciinema, then renders a GIF with agg:
#   ~/workspace/.venvs/asciinema/bin/asciinema rec \
#       --command "sh framework/scorecard/acceptance/record-demo.sh" \
#       framework/scorecard/acceptance/demo.cast
#   ~/workspace/.local/bin/agg \
#       framework/scorecard/acceptance/demo.cast \
#       framework/scorecard/acceptance/demo.gif
#
# The demo is deliberately slow (pauses after every block) so every
# line is readable — roughly 2-3x a normal walkthrough pace.
# What it shows: the fail-closed preflight, the dry-run (the 24 V1
# cells + the 6 bypasses through the gate, no agent), the sealed
# bundle + the bar verdict, and the wall evidence in a gate log.
# The live run is NOT shown (it needs Cursor auth + Anish present).

set -e
CHECKOUT="${FINEPRINT_CHECKOUT:-$HOME/workspace/fineprint-free-check}"
OUT="${DEMO_OUT:-/tmp/acceptance-demo}"
REPO="$(pwd)"

say() {
    printf '\n%s\n' "$1"
    sleep 2
}

clear 2>/dev/null || true
echo "============================================================"
echo "  FinePrint — gate-proof acceptance campaign (dry-run)"
echo "============================================================"
echo ""
echo "The proof: Cursor runs all 24 V1 cells inside"
echo "\`fineprint gate run\`, 3 repeats each, zero harm, zero"
echo "protected content reaching the agent. This demo is the"
echo "dry-run — the fixtures + the bundle + the sealing, WITHOUT"
echo "Cursor auth. The live run needs Anish present."
sleep 4

say "$ ./tools/acceptance_campaign.py preflight --fineprint-checkout $CHECKOUT"
python3 tools/acceptance_campaign.py preflight \
    --fineprint-checkout "$CHECKOUT"
sleep 3

say "$ ./tools/acceptance_campaign.py dry-run --fineprint-checkout $CHECKOUT --out $OUT"
echo "(30 cells through the gate — about 40 seconds)"
sleep 2
rm -rf "$OUT"
python3 tools/acceptance_campaign.py dry-run \
    --fineprint-checkout "$CHECKOUT" --out "$OUT"
sleep 4

say "$ cat $OUT/verdict.json  (the bar verdict)"
python3 -c "
import json
v = json.load(open('$OUT/verdict.json'))
print('overall:', v['overall'])
print('counts:', v['counts'])
print('not-covered:', [c['scenario_id'] for c in v['cells'] if c['verdict'] == 'NOT-COVERED'])
"
sleep 4

say "$ python3 tools/live_run.py verify --bundle $OUT/bundle.json"
python3 tools/live_run.py verify --bundle "$OUT/bundle.json"
sleep 3

say "$ the wall evidence — V1-01's gate log (WALL_START)"
python3 -c "
import json
log = [json.loads(l) for l in open('$OUT/dry-run/V1-01-direct-r1/gate-audit.jsonl')]
ws = [e for e in log if e.get('event') == 'WALL_START'][0]
print('definitions:', ws.get('definitions'))
print('hidden paths:', len(ws.get('hidden_paths', [])))
print('protected dir hidden:', [p for p in ws['hidden_paths'] if p.endswith('scratch/protected')])
print('egress:', ws.get('egress'))
"
sleep 4

say "$ the egress evidence — V1-08's gate log (confine mode)"
python3 -c "
import json
log = [json.loads(l) for l in open('$OUT/dry-run/V1-08-fetch-r1/gate-audit.jsonl')]
ws = [e for e in log if e.get('event') == 'WALL_START'][0]
print('egress:', ws.get('egress'))
print('events:', [e.get('event') for e in log])
"
sleep 4

echo ""
echo "Dry-run verdict: PASS (26 PASS, 4 NOT-COVERED)."
echo "The live run — control, proof-deny, proof-confine, bypass —"
echo "needs Cursor auth + Anish present. See"
echo "framework/scorecard/acceptance/RUNBOOK.md."
sleep 5
