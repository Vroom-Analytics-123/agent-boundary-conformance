#!/bin/bash
# FinePrint check demo — real commands, real output.
#
# Record it (from the repo root):
#   asciinema rec -c demo/record-check-demo.sh assets/fineprint-check-demo.cast
#   agg assets/fineprint-check-demo.cast assets/fineprint-check-demo.gif
#
# What it shows (run inside an already-cloned repo; the CLI is
# stdlib-only, so there is nothing to install):
#   1. `fineprint init` scaffolds starter policy files;
#   2. `fineprint check` on a policy that allows everything ->
#      BLOCKED, with the sealed evidence bundle;
#   3. `fineprint gate run` allowing a good command and blocking a
#      protected file.
#
# The demo work directory is removed at the end.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/demo-work"
rm -rf "$WORK" && mkdir -p "$WORK"
cd "$WORK"

echo "already cloned — the CLI is stdlib-only, nothing to install"
sleep 1
../fineprint init --harness claude-code
echo
echo "--- a policy that allows everything breaks the rule ---"
echo "    (the starter policy is rewritten to allow Bash(*))"
sleep 1
python3 - <<'PY'
import json
p = json.load(open("fineprint.settings.json"))
p["permissions"] = {"allow": ["Bash(*)"]}
json.dump(p, open("bad.settings.json", "w"), indent=2)
PY
../fineprint check --harness claude-code --policy bad.settings.json \
    --only FP-001 --no-smoke
echo "exit code: $?"
sleep 2
echo
echo "--- the gate: a good command passes, an out-of-scope read is blocked ---"
sleep 1
printf 'hello gate\n' > notes.txt
../fineprint gate run -- cat notes.txt
echo "exit code: $?"
sleep 1
../fineprint gate run -- cat /etc/passwd
echo "exit code: $?"
sleep 2

cd "$ROOT"
rm -rf "$WORK"
