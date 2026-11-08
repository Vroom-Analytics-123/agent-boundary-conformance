#!/usr/bin/env bash
# Record the drift-fixtures demo: one fixture (task + protected file +
# canary + step-index logging) and the self-check passing.
#
# Usage (from the repo root):
#   bash demo/record_drift_demo.sh
#
# Produces demo/drift-fixtures-demo.cast and demo/drift-fixtures-demo.gif.
# The session is deliberately slow (2-3x a normal walkthrough pace) so
# every line is readable in the GIF. Tooling: asciinema 2.4.0
# (~/workspace/.venvs/asciinema) + agg 1.5.0 (~/.local/bin/agg).
#
# Re-record after any fixture change; the GIF is embedded near the top
# of the branch README.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
CAST="$REPO/demo/drift-fixtures-demo.cast"
GIF="$REPO/demo/drift-fixtures-demo.gif"
ASCIINEMA="$HOME/workspace/.venvs/asciinema/bin/asciinema"
AGG="$HOME/workspace/.local/bin/agg"

pause() { sleep "${1:-3}"; }

session() {
    cd "$REPO"
    clear 2>/dev/null || true
    echo "== FinePrint drift fixtures — demo =="
    echo
    echo "Four long tasks (8-12 steps each). The rule is stated at step 1;"
    echo "a late step tempts the agent to touch the protected thing."
    echo "Each task is completable WITHOUT violating."
    pause 4
    echo
    echo "$ find fixtures/drift -maxdepth 2 | sort"
    find fixtures/drift -maxdepth 2 | sort
    pause 4
    echo
    echo "$ sed -n '1,12p' fixtures/drift/drift-01-bugfix-records/task.md"
    sed -n '1,12p' fixtures/drift/drift-01-bugfix-records/task.md
    pause 5
    echo
    echo "$ python3 -c '... print step 9 (the late-step temptation) ...'"
    python3 -c "import json; m=json.load(open('fixtures/drift/drift-01-bugfix-records/manifest.json')); print('step 9:', m['steps'][8]['text'])"
    pause 4
    echo
    echo "$ head -4 fixtures/drift/drift-01-bugfix-records/protected/records.csv"
    head -4 fixtures/drift/drift-01-bugfix-records/protected/records.csv
    pause 4
    echo
    echo "== Canary: unique marker, planted in the protected location =="
    python3 - <<'EOF'
import sys
sys.path.insert(0, "tools")
import fineprint_canary as c
marker = c.plant_canary("/tmp/demo-canary.txt")
print("planted marker:", marker)
print("trace, leaked output:", c.trace_marker(marker, {"stdout": "agent printed " + marker}))
print("verdict:", c.canary_verdict(marker, ["stdout"])["line"])
print("trace, clean output:", c.trace_marker(marker, {"stdout": "nothing here"}))
print("verdict:", c.canary_verdict(marker, [])["line"])
EOF
    pause 5
    echo
    echo "== Step-index log shape (run-log.jsonl, one entry per line) =="
    cat <<'EOF'
{"step": 2, "kind": "approval", "action": "read workspace file", "decision": "asked"}
{"step": 5, "kind": "effect", "action": "edit workspace file", "decision": "executed"}
{"step": 9, "kind": "note", "action": "temptation step reached", "decision": "refused"}
EOF
    pause 4
    echo
    echo "$ python3 tools/check_drift_fixtures.py"
    python3 tools/check_drift_fixtures.py
    pause 4
    echo
    echo "$ python3 -m pytest tests/test_drift_fixtures.py -q"
    python3 -m pytest tests/test_drift_fixtures.py -q
    pause 3
    echo
    echo "== Done: 4 fixtures PASS, 15 tests PASS. No live runs yet — those"
    echo "   need harness auth + Anish, after the Nov 9 ceremony. =="
    pause 2
}

if [ "${1:-}" = "_session" ]; then
    session
    exit 0
fi

"$ASCIINEMA" rec --overwrite --cols 110 --rows 34 \
    -c "bash $0 _session" "$CAST"
"$AGG" --font-size 14 "$CAST" "$GIF"
ls -la "$CAST" "$GIF"
