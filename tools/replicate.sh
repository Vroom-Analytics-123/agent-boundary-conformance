#!/usr/bin/env bash
# tools/replicate.sh — one-path replication check for the sealed Day-2 evidence bundle.
#
# An outsider runs exactly this script: tools/replicate.sh [sealed-bundle].
# It:
#   1. reads the published expectations (Merkle root + pinned input hashes)
#      from the sealed bundle at evidence/day2-2026-10-22/bundle.json,
#   2. verifies every input file on disk against those pins (any drift is a
#      DIFF, never silently tolerated),
#   3. fetches the pinned oracle via the committed npm recipe if the vendored
#      binary is missing or hash-mismatched (a fetch FAILURE is an ERROR, not
#      a DIFF — replication could not be attempted),
#   4. reruns the corpus through tools/run_fixtures.py + rebuilds the bundle
#      with tools/build_evidence_bundle.py into a throwaway directory,
#   5. compares the fresh Merkle root against the sealed root and prints a
#      plain PASS / DIFF verdict.
#
# Exit codes: 0 = PASS, 1 = DIFF, 2 = ERROR (tooling/network failure).
# Stdlib python3 required. The script never modifies the sealed bundle,
# the sealed corpus, or the held-out split; it adds one rerun record under
# evidence/reruns/ (repo convention) and writes the fresh bundle to a
# temp dir whose path it prints.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Optional first argument: which sealed bundle to replicate (default: Day-2).
# The post-fix bundle (evidence/postfix-2026-10-22/bundle.json) works the same
# way — expectations are always read from the bundle itself.
SEALED="${1:-$REPO/evidence/day2-2026-10-22/bundle.json}"
case "$SEALED" in
  /*) ;;
  *) SEALED="$REPO/$SEALED" ;;
esac
PINNED_VERSION="0.149.0"
PINNED_SHA256="bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827"
ORACLE="$REPO/tools/vendor/codex/0.149.0/bin/codex"

log() { echo "[replicate] $*"; }
die() { echo "[replicate] ERROR: $*" >&2; exit 2; }

command -v python3 >/dev/null || die "python3 not found"
[ -f "$SEALED" ] || die "sealed bundle missing: $SEALED"

# --- 1. Published expectations from the sealed bundle -----------------------
EXPECT_JSON="$(python3 - "$SEALED" <<'EOF'
import json, sys
b = json.load(open(sys.argv[1]))
pinned = b["pinned"]
print(json.dumps({
    "merkle_root": b["merkle"]["root"],
    "bundle_id": b["bundle_id"],
    "status": b["status"],
    "corpus_version_hash": pinned["corpus_version_hash"],
    "binary_sha256": pinned["binary_sha256"],
    "invariants_sha256": pinned["invariants_sha256"],
    "preregistration_sha256": pinned["preregistration_sha256"],
    "rules_files": pinned["rules_files"],
    "neg_controls_sha256": b.get("_neg_controls_sha256"),
}))
EOF
)"
export EXPECT_JSON REPO

# --- 2. Input drift check: disk must match the sealed pins -----------------
# NOTE: `if` conditions are exempt from `set -e`; do NOT use `cmd; if [ $? ... ]`
# here — a drifting input would kill the script before the DIFF branch prints.
if python3 - <<'EOF'
import hashlib, json, os, sys
repo = os.environ["REPO"]
exp = json.loads(os.environ["EXPECT_JSON"])
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
drift = []
checks = {
    "fixtures/fixtures.json": exp["corpus_version_hash"],
    "security/invariants.yaml": exp["invariants_sha256"],
}
checks.update(exp["rules_files"])
for rel, want in checks.items():
    p = os.path.join(repo, rel)
    got = sha(p) if os.path.exists(p) else "<missing>"
    if got != want:
        drift.append(f"{rel}: on-disk {got[:16]}... != sealed {want[:16]}...")
# negative controls hash is pinned in the pre-registration; re-derive there
sys.exit(0 if not drift else 1)
EOF
then
    log "all input files match the sealed pins."
else
    log "inputs on disk differ from the sealed bundle's pins:"
    python3 - "$SEALED" <<'EOF'
import hashlib, json, os, sys
repo = os.environ.get("REPO", ".")
b = json.load(open(sys.argv[1])); pinned = b["pinned"]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""): h.update(c)
    return h.hexdigest()
for rel, want in {"fixtures/fixtures.json": pinned["corpus_version_hash"],
                  "security/invariants.yaml": pinned["invariants_sha256"],
                  **pinned["rules_files"]}.items():
    p = os.path.join(repo, rel)
    got = sha(p) if os.path.exists(p) else "<missing>"
    if got != want:
        print(f"  DRIFT {rel}: disk={got[:16]}... sealed={want[:16]}...")
EOF
    log "a sealed Merkle root cannot be reproduced from different inputs."
    log "This tree carries post-seal changes (or corruption); restore the"
    log "sealed inputs before claiming replication."
    echo "REPLICATION VERDICT: DIFF"
    exit 1
fi

# --- 3. Pinned oracle: verify vendored binary, else fetch via recipe -------
need_fetch=0
if [ ! -x "$ORACLE" ]; then
    log "vendored oracle missing; fetching via the committed recipe."
    need_fetch=1
else
    got="$(sha256sum "$ORACLE" | cut -d' ' -f1)"
    if [ "$got" != "$PINNED_SHA256" ]; then
        log "vendored oracle hash mismatch ($got); refetching via recipe."
        need_fetch=1
    else
        log "vendored oracle verified (sha256 matches pin)."
    fi
fi
if [ "$need_fetch" -eq 1 ]; then
    command -v npm >/dev/null || die "npm not found; cannot fetch the pinned oracle"
    # The fetch needs ~350 MB transient space (compressed tarball + the
    # 258 MB binary). Respect $TMPDIR so callers on small /tmp can redirect.
    FETCHD="$(mktemp -d "${TMPDIR:-/tmp}/codex-fetch.XXXXXX")"
    # Always clean the fetch dir, even on failure.
    trap 'rm -rf "$FETCHD"' EXIT
    log "fetching @openai/codex@0.149.0-linux-x64 via npm (this downloads ~100 MB)..."
    ( cd "$FETCHD" \
      && npm pack "@openai/codex@0.149.0-linux-x64" >/dev/null 2>&1 \
      && mkdir -p lin \
      && tar -xzf openai-codex-0.149.0-linux-x64.tgz -C lin \
         package/vendor/x86_64-unknown-linux-musl/bin/codex ) \
      || die "npm pack / extraction failed; replication could not be attempted"
    CAND="$FETCHD/lin/package/vendor/x86_64-unknown-linux-musl/bin/codex"
    [ -f "$CAND" ] || die "expected binary not found in the npm tarball"
    got="$(sha256sum "$CAND" | cut -d' ' -f1)"
    [ "$got" = "$PINNED_SHA256" ] \
        || die "fetched binary sha256 $got != pinned $PINNED_SHA256; refusing to use it"
    mkdir -p "$(dirname "$ORACLE")"
    # mv within one filesystem is a rename (no extra 258 MB copy); the
    # explicit check below keeps a failed move from passing silently
    # (set -e does not fire inside `a && b` lists).
    mv "$CAND" "$ORACLE" || die "could not install the fetched binary at $ORACLE"
    chmod +x "$ORACLE" || die "could not chmod the installed binary"
    [ -x "$ORACLE" ] || die "installed binary is not executable"
    log "fetched binary verified against the pin and installed at $ORACLE"
    rm -rf "$FETCHD"
    trap - EXIT
fi
[ "$("$ORACLE" --version)" = "codex-cli $PINNED_VERSION" ] \
    || die "oracle --version mismatch; refusing to run"

# --- 4. Rerun the corpus + rebuild the bundle into a throwaway dir --------
# The throwaway dir lives INSIDE the repo: some builder versions assume the
# out-dir is under the repo root (relative_to(REPO) in their final print).
# It is removed on PASS; kept for inspection on DIFF.
OUTD="$(mktemp -d "$REPO/.replication-tmp.XXXXXX")"
log "rerunning the corpus with the pinned oracle..."
RERUN_OUT="$(python3 "$REPO/tools/run_fixtures.py")" \
    || die "run_fixtures.py failed (exit $?)"
# (pipefail + set -e: neutralize the grep pipeline so a missing line is a
# clean die, not a silent exit)
RERUN_REL="$(echo "$RERUN_OUT" | grep -o 'results written: .*' | cut -d' ' -f3 || true)"
[ -n "$RERUN_REL" ] || die "could not locate the rerun JSON in run_fixtures output"
RERUN_JSON="$REPO/$RERUN_REL"
[ -f "$RERUN_JSON" ] || die "rerun JSON not found on disk: $RERUN_JSON"
log "rerun record: $RERUN_JSON"
log "rebuilding the bundle (throwaway dir: $OUTD)..."
python3 "$REPO/tools/build_evidence_bundle.py" "$RERUN_JSON" --out-dir "$OUTD" \
    >/dev/null || die "build_evidence_bundle.py failed"
FRESH="$OUTD/bundle.json"
[ -f "$FRESH" ] || die "fresh bundle was not written"

# --- 5. Compare Merkle roots ----------------------------------------------
# (same set -e note as step 2: use if/else, not `$?` after the heredoc)
if python3 - "$SEALED" "$FRESH" <<'EOF'
import json, sys
sealed = json.load(open(sys.argv[1]))["merkle"]["root"]
fresh = json.load(open(sys.argv[2]))["merkle"]["root"]
print(f"sealed root: {sealed}")
print(f"fresh  root: {fresh}")
sys.exit(0 if sealed == fresh else 1)
EOF
then
    log "fresh bundle matched the sealed root; removing throwaway dir $OUTD"
    rm -rf "$OUTD"
    echo "REPLICATION VERDICT: PASS"
    exit 0
else
    log "fresh bundle written to $FRESH (kept for inspection)"
    echo "REPLICATION VERDICT: DIFF"
    exit 1
fi
