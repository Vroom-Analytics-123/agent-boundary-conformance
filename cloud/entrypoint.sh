#!/bin/sh
# Entrypoint for the FinePrint cloud base image.
#
# The container's command IS the agent command. Everything after the
# image name is passed to the gate, which runs it inside the wall:
#
#   docker run fineprint-wall:cloud claude
#   docker run fineprint-wall:cloud codex "fix the login bug"
#
# (A leading `gate run --` is stripped, so `docker run
#  fineprint-wall:cloud gate run -- claude` also works.)
#
# Environment:
#   FINEPRINT_POLICY   path to a policy file inside the container
#                      (default: the built-in protective denylist)
#   FINEPRINT_LOG      path for the hash-chained audit log
#                      (default: none — the log is not written; set
#                      this and mount a volume if you want the log)
#   FINEPRINT_CONFINE  "1" to run in confine mode (everything outside
#                      the allowed scope hidden; egress allowlisted)
#   ANTHROPIC_API_KEY / OPENAI_API_KEY — passed through to the agent
#
# The entrypoint prints the definitions version in force first (the
# acceptance bar requires it recorded), then execs the gate. tini is
# PID 1 (the image's ENTRYPOINT) and forwards signals to this script;
# exec replaces this script with the gate, so the gate is tini's child
# and receives those signals. Exit codes are the gate's: 0 the agent
# ran, 2 a rule denied the command (it never ran), 3 the gate could
# not run here (e.g. no `unshare` — it refuses rather than running
# unprotected). The agent's own exit code is passed through.
set -e

# FINEPRINT_GATE overrides the gate path (testing only — the image
# always uses /opt/fineprint/tools/fineprint_gate.py).
GATE="${FINEPRINT_GATE:-/opt/fineprint/tools/fineprint_gate.py}"

if [ "$1" = "gate" ] && [ "$2" = "run" ]; then
    shift 2
    if [ "$1" = "--" ]; then
        shift
    fi
fi

if [ $# -eq 0 ]; then
    echo "fineprint cloud image — usage:" >&2
    echo "  docker run fineprint-wall:cloud <agent command>" >&2
    echo "  docker run fineprint-wall:cloud claude" >&2
    echo "  docker run fineprint-wall:cloud codex \"fix the login bug\"" >&2
    echo "See cloud/README.md. The definitions in force are:" >&2
    python3 "$GATE" definitions || true
    exit 3
fi

# The definitions version in force, on stdout before the run. If the
# definitions do not verify, refuse here rather than running the
# agent unprotected.
python3 "$GATE" definitions || exit 3

# Build the gate argv with positional parameters (no word-splitting).
# The gate parses flags AFTER the subcommand (`run --log FILE --`),
# so build the list by prepending: start with `-- <agent...>` and
# prepend each flag, then the subcommand.
set -- -- "$@"
if [ "$FINEPRINT_CONFINE" = "1" ]; then
    set -- --confine "$@"
fi
if [ -n "$FINEPRINT_LOG" ]; then
    set -- --log "$FINEPRINT_LOG" "$@"
fi
if [ -n "$FINEPRINT_POLICY" ]; then
    set -- --policy "$FINEPRINT_POLICY" "$@"
fi
set -- run "$@"

exec python3 "$GATE" "$@"
