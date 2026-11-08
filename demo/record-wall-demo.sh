#!/bin/bash
# FinePrint wall demo — real commands, real output.
#
# Record it (from the repo root):
#   asciinema rec -c demo/record-wall-demo.sh assets/fineprint-wall-demo.cast
#   agg assets/fineprint-wall-demo.cast assets/fineprint-wall-demo.gif
#
# What it shows:
#   1. the wall denying a script that reads a credential WITHOUT
#      naming it on argv (the tripwire cannot see it — the wall
#      hides ~/.ssh, so the read fails and nothing leaks);
#   2. a direct credential read denied by name, with the rule id;
#   3. normal work allowed;
#   4. the notification log: tried X -> blocked by rule Y ->
#      will always be blocked.
#
# The fake key is not a real secret. The demo work directory and the
# fake home are removed at the end.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/demo-work"
rm -rf "$WORK" && mkdir -p "$WORK"
cd "$WORK"

DEMO_HOME="$(mktemp -d /tmp/fineprint-wall-demo-home.XXXXXX)"
mkdir -p "$DEMO_HOME/.ssh"
printf 'TOPSECRET-FAKE-KEY - not a real secret\n' > "$DEMO_HOME/.ssh/id_rsa"
cat > read_key.py <<'PY'
import os
print(open(os.path.expanduser("~/.ssh/id_rsa")).read())
PY
printf 'hello wall\n' > notes.txt
export HOME="$DEMO_HOME"

../fineprint init --gate
echo
echo "--- the wall denies a script that reads a credential ---"
echo "    (the script never names the key on argv, so the tripwire"
echo "     cannot see it — the wall hides ~/.ssh instead)"
sleep 1
../fineprint gate run --log audit.jsonl -- python3 read_key.py
echo "exit code: $?"
sleep 2
echo
echo "--- a direct read is denied by name, with the rule ---"
sleep 1
../fineprint gate run --log audit.jsonl -- cat "$DEMO_HOME/.ssh/id_rsa"
echo "exit code: $?"
sleep 2
echo
echo "--- normal work is allowed ---"
sleep 1
../fineprint gate run -- cat notes.txt
echo "exit code: $?"
sleep 2
echo
echo "--- the notification log ---"
sleep 1
../fineprint gate log --log audit.jsonl
sleep 2

cd "$ROOT"
rm -rf "$WORK" "$DEMO_HOME"
