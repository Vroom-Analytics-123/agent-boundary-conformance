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
#      bad one.
#
# PACE: deliberately slow — every command is typed out character by
# character, and every output stays on screen for several seconds
# before the next step, so each line can be read clearly. The pauses
# are explicit sleeps in this script, not hand-timed.
#
# NOTE (free-check-gate branch): the default policy here is the
# cwd-only allowlist, so the blocked read is /etc/passwd (outside
# the working directory). On free-wall (protective denylist default)
# the same beat uses a .env file instead, because a plain system
# file like /etc/passwd is allowed by the denylist.
#
# The demo work directory is removed at the end.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/demo-work"
rm -rf "$WORK" && mkdir -p "$WORK"
cd "$WORK"

# type_run: type a command out character by character (like a person
# typing), pause, then run it for real. The function's exit status is
# the command's exit status, so `echo "exit code: $?"` after a
# type_run call reports the command's code.
type_run() {
  local cmd="$1"
  local i
  for ((i=0; i<${#cmd}; i++)); do
    printf '%s' "${cmd:i:1}"
    sleep 0.035
  done
  printf '\n'
  sleep 0.5
  eval "$cmd"
}

echo "already cloned — the CLI is stdlib-only, nothing to install"
sleep 1.5
type_run '../fineprint init --harness claude-code'
sleep 3
echo
echo "--- a policy that allows everything breaks the rule ---"
echo "    (the starter policy is rewritten to allow Bash(*))"
sleep 1.5
python3 - <<'PY'
import json
p = json.load(open("fineprint.settings.json"))
p["permissions"] = {"allow": ["Bash(*)"]}
json.dump(p, open("bad.settings.json", "w"), indent=2)
PY
sleep 1.5
type_run '../fineprint check --harness claude-code --policy bad.settings.json --only FP-001 --no-smoke'
echo "exit code: $?"
sleep 5
echo
echo "--- the gate: a good command passes, an out-of-scope read is blocked ---"
sleep 1.5
printf 'hello gate\n' > notes.txt
sleep 1
type_run '../fineprint gate run -- cat notes.txt'
echo "exit code: $?"
sleep 3
type_run '../fineprint gate run -- cat /etc/passwd'
echo "exit code: $?"
sleep 6

cd "$ROOT"
rm -rf "$WORK"
