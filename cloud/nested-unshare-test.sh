#!/bin/sh
# The nested-unshare test — the FIRST check on a real Docker host.
#
# It decides the whole container story (investigation doc §7.2, §12):
# if `unshare --user --mount` works inside a default Docker container,
# shapes B, C, and D-container all work with the wall baked into the
# image. If it fails, the wall inside a container needs a seccomp
# profile or `seccomp=unconfined` — which you can set on your own
# Docker host and in your own K8s manifests but CANNOT set on Fargate,
# Cloud Run, ACI, Autopilot, or Codespaces.
#
# Usage (on a machine with Docker — a real Mac with Docker Desktop,
# a Linux host, or a cloud VM):
#   sh cloud/nested-unshare-test.sh
#
# The script:
#   0. The gate's own probe (`fineprint gate probe`) inside the cloud
#      image — default seccomp first, then the least-privilege profile,
#      then seccomp=unconfined. The probe names the failing step
#      (unshare NEWUSER / unshare NEWNS / mount / cap-drop), so a
#      failure says which guard refused, not just that it failed.
#   1. The one-command test in a bare image (debian:bookworm-slim,
#      no gate involved) with default seccomp — separates "the
#      kernel/runtime blocks it" from "the gate does something wrong".
#   2. The wall's T1–T7 smoke test inside the cloud image, in the
#      FIRST mode the probe passed (default, profile, or unconfined).
#      A probe pass is necessary, not sufficient: if the smoke test
#      fails in that mode, the verdict is FAIL — the failure is a
#      wall/gate problem, not a seccomp problem, and escalating the
#      mode would only mask it.
#   3. `gate verify-log` on the audit log the smoke test wrote.
#
# Verdict, printed at the end:
#   PASS                  unshare works with default seccomp; the wall
#                         works in containers everywhere.
#   PASS-WITH-PROFILE     the wall needs the seccomp profile
#                         (cloud/docker/fineprint-seccomp.json — the
#                         default profile + unconditional
#                         unshare/clone/mount) plus
#                         apparmor=unconfined; it works where you
#                         control the runtime (your Docker host, your
#                         K8s via seccompProfile: Localhost +
#                         appArmorProfile: Unconfined), NOT on Fargate
#                         / Cloud Run / ACI / Autopilot / Codespaces.
#   PASS-WITH-UNCONFINED  only seccomp=unconfined rescues it: the
#                         profile was not enough, so something else the
#                         wall needs is blocked by the default profile.
#                         Record exactly which step failed with the
#                         profile before treating this as a pass.
#   FAIL                  the wall does not start in this container at
#                         all — no cloud container shape works here.
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
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROFILE="$SCRIPT_DIR/docker/fineprint-seccomp.json"
PROBE_MODE=""
SMOKE_MODE=""

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

# seccomp_opts MODE — the --security-opt flags for a mode, or nothing.
# DEFAULT: no flags. PROFILE: the least-privilege profile +
# apparmor=unconfined. UNCONFINED: seccomp=unconfined +
# apparmor=unconfined (last resort).
seccomp_opts() {
    case "$1" in
        PROFILE)
            echo "--security-opt seccomp=$PROFILE --security-opt apparmor=unconfined"
            ;;
        UNCONFINED)
            echo "--security-opt seccomp=unconfined --security-opt apparmor=unconfined"
            ;;
        *) ;;
    esac
}

# probe_one MODE — `fineprint gate probe` inside the cloud image.
# Prints the probe's output; returns its exit code (0 = all three
# syscalls work in this mode, 3 = at least one fails).
probe_one() {
    mode="$1"
    # shellcheck disable=SC2086
    docker run --rm --entrypoint python3 \
        $(seccomp_opts "$mode") \
        "$IMAGE_CLOUD" /opt/fineprint/tools/fineprint_gate.py probe
}

# run_one MODE CMD... — one walled run inside the cloud image.
# MODE is DEFAULT, PROFILE, or UNCONFINED. Prints the container's
# output; returns the container's exit code.
run_one() {
    mode="$1"; shift
    # shellcheck disable=SC2086
    docker run --rm $(seccomp_opts "$mode") \
        -v "$FIX:/work" -w /work/proj \
        -e HOME=/work/home -e FINEPRINT_LOG=/work/proj/gate.log \
        "$IMAGE_CLOUD" "$@"
}

echo "=== 0. gate probe inside the cloud image ==="
for mode in DEFAULT PROFILE UNCONFINED; do
    if [ "$mode" = "PROFILE" ] && [ ! -f "$PROFILE" ]; then
        echo "--- probe, PROFILE: SKIPPED — $PROFILE is missing ---"
        continue
    fi
    echo "--- probe, $mode ---"
    if probe_one "$mode"; then
        echo "probe: PASS in $mode"
        PROBE_MODE="$mode"
        break
    else
        echo "probe: FAILED in $mode"
    fi
done
if [ -z "$PROBE_MODE" ]; then
    echo "probe: FAILED in every mode — the wall cannot start here"
    echo "=== verdict ==="
    echo "FAIL — the wall does not start in this container at all; no cloud container shape works here."
    exit 0
fi

echo "=== 1. one-command test in a bare image, default seccomp ==="
if docker run --rm debian:bookworm-slim unshare --map-root-user --mount \
        sh -c 'mount -t tmpfs tmpfs /tmp && echo OK'; then
    echo "one-command test: OK with default seccomp"
else
    echo "one-command test: FAILED with default seccomp"
    echo "(the probe above is the authority — it runs the exact three"
    echo " syscalls the wall needs inside the actual image; a bare-image"
    echo " failure with a probe pass in the same mode would be a"
    echo " discrepancy worth reporting, not a verdict on its own)"
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

echo "=== 2. wall smoke test T1–T7, $PROBE_MODE (first mode the probe passed) ==="
if smoke_run "$PROBE_MODE"; then
    echo "smoke test: PASS in $PROBE_MODE"
    SMOKE_MODE="$PROBE_MODE"
else
    echo "smoke test: FAILED in $PROBE_MODE — the probe passed but the"
    echo "wall does not hold here, so this is a wall/gate problem, not"
    echo "a seccomp problem. Do not escalate the mode to mask it."
fi

echo "=== 3. audit log ==="
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
if [ -z "$SMOKE_MODE" ]; then
    echo "FAIL — the wall does not start in this container at all; no cloud container shape works here."
elif [ "$SMOKE_MODE" = "DEFAULT" ]; then
    echo "PASS — unshare works with default seccomp; the wall works in containers everywhere."
elif [ "$SMOKE_MODE" = "PROFILE" ]; then
    echo "PASS-WITH-PROFILE — the wall needs the seccomp profile (cloud/docker/fineprint-seccomp.json) + apparmor=unconfined; it works where you control the runtime (your Docker host, your K8s via seccompProfile: Localhost + appArmorProfile: Unconfined), NOT on Fargate / Cloud Run / ACI / Autopilot / Codespaces."
else
    echo "PASS-WITH-UNCONFINED — only seccomp=unconfined rescues it; the profile was not enough, so something else the wall needs is blocked by the default profile. Record exactly which step failed with the profile before treating this as a pass."
fi
