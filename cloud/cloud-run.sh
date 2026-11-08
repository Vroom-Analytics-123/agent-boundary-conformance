#!/bin/sh
# FinePrint on Google Cloud Run (jobs) — the wall baked into the image.
#
# Usage:
#   sh cloud/cloud-run.sh PROJECT_ID REGION [AGENT]
#   AGENT defaults to "claude".
#
# UNVERIFIED (investigation doc §7.3): whether `unshare` works inside
# a Cloud Run container is unverified either way. Use gen2 — Cloud Run
# jobs always use gen2, a microVM with, in Google's own words, "full
# Linux compatibility, including support for all system calls,
# namespaces, and cgroups". Gen1 is gVisor (syscall emulation — the
# wall's `unshare` + mount calls are emulated, and gVisor's record on
# nested namespaces is poor), so do not run this on a gen1 service.
# There is no knob for seccomp on Cloud Run. Deploy once, run the
# wall's smoke test as a job (cloud/nested-unshare-test.sh, adapted),
# and accept the answer: if it fails, Cloud Run cannot run the wall.
#
# Notes:
# - A Cloud Run JOB (not a service): the agent runs to completion
#   rather than serving requests. Services have request timeouts; a
#   long agent run wants a job.
# - The secret must exist first (Secret Manager). Never pass a key on
#   the command line — --set-secrets pulls it at run time.
# - The image is NOT published anywhere yet — push it to Artifact
#   Registry first (no GHCR / Docker Hub push).
# - The audit log: set FINEPRINT_LOG and a Cloud Storage volume if
#   you want the log out; without it the run leaves no audit trail.
set -e
PROJECT="${1:?usage: cloud-run.sh PROJECT_ID REGION [AGENT]}"
REGION="${2:?usage: cloud-run.sh PROJECT_ID REGION [AGENT]}"
AGENT="${3:-claude}"

gcloud run jobs create fineprint-agent \
    --project "$PROJECT" \
    --region "$REGION" \
    --image "REGION-docker.pkg.dev/PROJECT/fineprint/fineprint-wall:cloud" \
    --tasks 1 \
    --max-retries 0 \
    --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest" \
    --command "$AGENT"

echo "created. Run it with:"
echo "  gcloud run jobs execute fineprint-agent --project $PROJECT --region $REGION"
