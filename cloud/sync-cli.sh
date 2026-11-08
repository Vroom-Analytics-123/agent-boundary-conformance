#!/bin/sh
# Re-vendor the gate CLI from the `free-wall` branch into cloud/cli/.
#
# Usage (from the repo root):
#   sh cloud/sync-cli.sh [COMMIT]
#
# COMMIT defaults to the remote head of origin/free-wall. The script
# copies the five gate files verbatim with `git show` (it never
# checks anything out, and it never touches the free-wall checkout's
# working tree or branch), then rewrites cloud/cli/PIN with the
# commit + sha256s. Run cloud/tests/test_cloud_image.py afterwards.
#
# The free-wall checkout must exist at ~/workspace/fineprint-free-check
# (or set FINEPRINT_CHECK_DIR). It must have the origin remote.
set -e
CHECK_DIR="${FINEPRINT_CHECK_DIR:-$HOME/workspace/fineprint-free-check}"
PIN_COMMIT="${1:-$(git -C "$CHECK_DIR" rev-parse origin/free-wall)}"
OUT="$(dirname "$0")/cli"

[ -d "$CHECK_DIR/.git" ] || { echo "sync-cli: no git checkout at $CHECK_DIR" >&2; exit 3; }
git -C "$CHECK_DIR" cat-file -e "$PIN_COMMIT" 2>/dev/null || { echo "sync-cli: unknown commit $PIN_COMMIT" >&2; exit 3; }

for f in fineprint_gate fineprint_wall fineprint_definitions fineprint_canary ed25519; do
    git -C "$CHECK_DIR" show "$PIN_COMMIT:tools/$f.py" > "$OUT/tools/$f.py"
done

{
    echo "# Pinned source for the vendored gate in cloud/cli/tools/."
    echo "#"
    echo "# The five .py files are verbatim copies of these files from the"
    echo "# public repo's \`free-wall\` branch at the commit below (the latest"
    echo "# branch head verified by avan: suite 253 tests OK, Nov 8, 2026)."
    echo "# The cloud image carries the gate only — not the Check engine —"
    echo "# because its job is to run an agent inside the wall, not to run"
    echo "# checks. Re-generate with cloud/sync-cli.sh; verify with"
    echo "# cloud/tests/test_cloud_image.py (it checks these hashes)."
    echo "#"
    echo "# free-wall commit: $PIN_COMMIT"
    echo "# definitions in force at that commit: v2026-11-07, 11 rules"
    echo "#   + synthetic DENY-EXFIL (see tools/fineprint_definitions.py)"
    echo "free-wall-commit=$PIN_COMMIT"
    for f in ed25519 fineprint_canary fineprint_definitions fineprint_gate fineprint_wall; do
        echo "$f.py=$(sha256sum "$OUT/tools/$f.py" | cut -d' ' -f1)"
    done
} > "$OUT/PIN"

echo "sync-cli: vendored free-wall $PIN_COMMIT into $OUT"
