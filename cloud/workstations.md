# FinePrint on Google Cloud Workstations — the wall as a custom image
#
# Each Workstation is a Compute Engine VM running a container image the
# user controls: custom images can preinstall tools and run startup
# scripts. The image is the distribution point — set it in the
# workstation configuration once, and every workstation gets the wall.
# (REPORTED, Google Cloud docs; investigation doc §7.4.)
#
# Set the custom image on a configuration (console: Workstations →
# your configuration → container image; or gcloud — check the exact
# flags with `gcloud workstations configs create --help` before
# running, the flag names below are the documented ones):
#
#   gcloud workstations configs create fineprint-agent \
#       --cluster CLUSTER --region REGION \
#       --container-custom-image=REGION-docker.pkg.dev/PROJECT/fineprint/fineprint-wall:cloud
#
# UNVERIFIED — the nested-unshare question (investigation doc §7.2):
# you do not get the host, only the container, so the question applies
# inside the container. Run cloud/nested-unshare-test.sh on a real
# Docker host first; if it fails there, the wall needs the seccomp
# profile (cloud/docker/fineprint-seccomp.json) or
# --security-opt seccomp=unconfined, which you CANNOT set on
# Workstations. Until that test runs, this is a best-effort shape, not
# a verified one. If the wall cannot start, the gate refuses (exit 3)
# rather than running the agent unprotected — you will see that, not
# a silent pass.
#
# Notes:
# - Root access inside the container is on by default and can be
#   disabled. The wall runs as root inside its user namespace either
#   way; disabling root does not change the wall, it changes what the
#   agent can do outside it.
# - Auth: pass the API key as an env var on the workstation (or a
#   Secret Manager secret), never baked into the image. Mounting the
#   agent's config dir gives the workstation your agent credentials —
#   the wall protects the guarded folder, not the agent's own login.
# - The image is NOT published anywhere yet — push it to Artifact
#   Registry first (no GHCR / Docker Hub push).
# - The audit log: set FINEPRINT_LOG and keep the workstation's
#   persistent disk if you want the log out.
