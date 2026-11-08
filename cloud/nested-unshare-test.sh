#!/bin/sh
# The nested-unshare test — the FIRST check on a real Docker host.
#
# It decides the whole container story (investigation doc §7.2): if
# `unshare --user --mount` works inside a default Docker container,
# shapes B, C, and D-container all work with the wall baked into the
# image. If it fails with EPERM, the wall inside a default container
# needs `--security-opt seccomp=unconfined` — which you can set on
# your own Docker host and in your own K8s manifests but CANNOT set
# on Fargate, Cloud Run, ACI, Autopilot, or Codespaces.
#
# Usage (on a machine with Docker — a real Mac with Docker Desktop,
# a Linux host, or a cloud VM):
#   sh cloud/nested-unshare-test.sh
#
# The script:
#   1. The one-command test, default seccomp (no flag).
#   2. The same, with --security-opt seccomp=unconfined (the fallback).
#   3. The wall's T1–T7 smoke test inside the cloud image — default
#      seccomp first; if any T fails, the whole smoke test re-runs
#      with the flag, so you learn whether the flag rescues it.
#   4. `gate verify-log` on the audit log the smoke test wrote.
#
# Verdict, printed at the end:
#   PASS              unshare works with default seccomp; the wall
#                     works in containers everywhere.
#   PASS-WITH-FLAG    unshare needs seccomp=unconfined; the wall works
#                     where you control the runtime (your Docker host,
#                     your K8s), NOT on Fargate / Cloud Run / ACI /
#                     Autopilot / Codespaces.
#   FAIL              the wall does not start in this container at
#                     all — no cloud container shape works here.
#
# Prerequisites: Docker running, and both images built:
#   docker build -t fineprint-wall:latest \
#     -f apps/desktop/docker/Dockerfile .
#   docker build -t fineprint-wall:cloud -f cloud/Dockerfile .
# The script refuses to run without them (it does not build them —
# building is a separate, visible step).
set -u

IMAGE_CLOUD="fineprint-wall:cloud"
IMAGE_BASE="fineprint-wall:latest"
PASS_DEFAULT=0
PASS_FLAG=0

fail() { echo "FAIL: $*" >&2; exit 3; }

command -v docker >/dev/null 2>&1 || fail "no 'docker' on PATH — run this on a machine with Docker (Docker Desktop on a Mac, or a Linux host)"
docker info >/dev/null 2>&1 || fail "docker is not running — start Docker Desktop (or the daemon) and re-run"

for img in "$IMAGE_BASE" "$IMAGE_CLOUD"; do
    docker image inspect "$img" >/dev/null 2>&1 || fail "image $img is not built — build it first (see cloud/README.md)"
done

# --- fixture: a fake key, a fake .env, a records file, a normal file ---
FIX="$(mktemp -d)"
trap 'rm -rf "$FIX"' EXIT INT TERM
mkdir -p "$FIX/home/.ssh" "$FIX/proj"
printf 'FAKE-PRIVATE-KEY-123\n' > "$FIX/home/.ssh/id_rsa"
printf 'AWS_SECRET=<redacted>\n' > "$FIX/home/.env"
printf 'just a normal file\n' > "$FIX/home/normal.txt"
printf 'RECORDS\n' > "$FIX/proj/records.txt"
printf 'hello\n' > "$FIX/proj/notes.txt"
# T6 must be a SCRIPT file: the tripwire scans argv, so a `-c` string
# naming the key is denied (exit 2) before it runs. A script file hides
# the read from the tripwire, so the command runs inside the wall, the
# wall hides the key, and the script gets FileNotFoundError (exit 1).
printf "open('/work/home/.ssh/id_rsa').read()\n" > "$FIX/proj/read_key.py"

# run_one MODE CMD... — one walled run inside the cloud image.
# MODE is DEFAULT (no seccomp flag) or FLAG. Prints the container's
# output; returns the container's exit code.
run_one() {
    mode="$1"; shift
    if [ "$mode" = "FLAG" ]; then
        docker run --rm --security-opt seccomp=unconfined \
            -v "$FIX:/work" -w /work/proj \
            -e HOME=/work/home -e FINEPRINT_LOG=/work/proj/gate.log \
            "$IMAGE_CLOUD" "$@"
    else
        docker run --rm \
            -v "$FIX:/work" -w /work/proj \
            -e HOME=/work/home -e FINEPRINT_LOG=/work/proj/gate.log \
            "$IMAGE_CLOUD" "$@"
    fi
}

echo "=== 1. one-command test, default seccomp ==="
if docker run --rm debian:bookworm-slim unshare --map-root-user --mount \
        sh -c 'mount -t tmpfs tmpfs /tmp && echo OK'; then
    echo "one-command test: OK with default seccomp"
    PASS_DEFAULT=1
else
    echo "one-command test: FAILED with default seccomp"
fi

echo "=== 2. one-command test, seccomp=unconfined ==="
if docker run --rm --security-opt seccomp=unconfined debian:bookworm-slim \
        unshare --map-root-user --mount \
        sh -c 'mount -t tmpfs tmpfs /tmp && echo OK'; then
    echo "one-command test: OK with seccomp=unconfined"
    PASS_FLAG=1
else
    echo "one-command test: FAILED even with seccomp=unconfined"
fi

# The smoke test, written out (sh has no arrays; each T is explicit).
# T1 rm -rf          -> 2 DENY-DELETE, notes.txt survives
# T2 sudo rm -rf     -> 2 DENY-DELETE
# T3 bash -lc rm -rf -> 2 DENY-DELETE
# T4 env rm -rf      -> 2 DENY-DELETE
# T5 cat records.txt -> 2 DENY-RECORDS
# T6 script reads key -> 1 FileNotFoundError, nothing leaked
# T7 benign cat      -> 0
smoke_run() {
    mode="$1"
    ok=0
    t() { # t NAME WANT_RC WANT_SUBSTRING -- CMD...
        name="$1"; want_rc="$2"; want="$3"; shift 3; shift  # drop the --
        out="$(run_one "$mode" "$@" 2>&1)"; rc=$?
        if [ "$rc" = "$want_rc" ] && printf '%s' "$out" | grep -qF "$want"; then
            echo "  $name: PASS (exit $rc)"
            ok=$((ok + 1))
        else
            echo "  $name: FAIL (exit $rc, want $want_rc + '$want')"
            printf '%s\n' "$out" | head -5 | sed 's/^/    /'
        fi
    }
    t T1 2 DENY-DELETE -- rm -rf notes.txt
    [ -f "$FIX/proj/notes.txt" ] || echo "  T1: FAIL — notes.txt was deleted"
    t T2 2 DENY-DELETE -- sudo rm -rf notes.txt
    t T3 2 DENY-DELETE -- bash -lc "rm -rf notes.txt"
    t T4 2 DENY-DELETE -- env rm -rf notes.txt
    t T5 2 DENY-RECORDS -- cat records.txt
    t T6 1 FileNotFoundError -- python3 read_key.py
    if printf '%s' "$(run_one "$mode" python3 read_key.py 2>&1)" | grep -q "FAKE-PRIVATE-KEY"; then
        echo "  T6: FAIL — the key leaked into the output"
        ok=$((ok - 1))
    fi
    t T7 0 hello -- cat notes.txt
    echo "smoke test ($mode): $ok/7 passed"
    return $((ok == 7 ? 0 : 1))
}

echo "=== 3. wall smoke test T1–T7, default seccomp ==="
if smoke_run DEFAULT; then
    echo "smoke test: PASS with default seccomp"
    PASS_DEFAULT=1
else
    echo "smoke test: FAILED with default seccomp — retrying with the flag"
    echo "=== 3b. wall smoke test T1–T7, seccomp=unconfined ==="
    if smoke_run FLAG; then
        echo "smoke test: PASS with seccomp=unconfined"
        PASS_FLAG=1
    else
        echo "smoke test: FAILED even with seccomp=unconfined"
    fi
fi

echo "=== 4. audit log ==="
if [ -f "$FIX/proj/gate.log" ]; then
    docker run --rm --entrypoint /usr/local/bin/fineprint \
        -v "$FIX:/work" -w /work/proj \
        "$IMAGE_CLOUD" gate verify-log --log /work/proj/gate.log \
        && echo "audit log: hash chain VALID" \
        || echo "audit log: INVALID (see above)"
else
    echo "audit log: no gate.log was written — the gate never ran"
fi

echo "=== verdict ==="
if [ "$PASS_DEFAULT" = "1" ]; then
    echo "PASS — unshare works with default seccomp; the wall works in containers everywhere."
elif [ "$PASS_FLAG" = "1" ]; then
    echo "PASS-WITH-FLAG — unshare needs seccomp=unconfined; the wall works where you control the runtime (your Docker host, your K8s), NOT on Fargate / Cloud Run / ACI / Autopilot / Codespaces."
else
    echo "FAIL — the wall does not start in this container at all; no cloud container shape works here."
fi
