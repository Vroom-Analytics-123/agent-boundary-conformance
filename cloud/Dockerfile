# FinePrint cloud base image — the wall, baked into an image.
#
# One image, four distributions (investigation doc §10): a devcontainer
# base (Codespaces, local VS Code), a Cloud Workstations custom image,
# a Fargate / Cloud Run / ACI task image, and an Agent37 custom
# template. The entrypoint IS the gate, so the container starts
# inside the wall: whatever agent command you give it runs walled.
#
# This Dockerfile EXTENDS the desktop image (apps/desktop/docker/
# Dockerfile) — it does not reinstall the agents. The agent install
# lives in exactly one place, the desktop Dockerfile; this file only
# adds the gate CLI + the entrypoint. Build the desktop image first:
#
#   docker build -t fineprint-wall:latest \
#     -f apps/desktop/docker/Dockerfile .
#   docker build -t fineprint-wall:cloud -f cloud/Dockerfile .
#
# Tags:
#   fineprint-wall:latest  the desktop base — agents + unshare, no CLI
#                          baked in (the app bind-mounts the CLI).
#   fineprint-wall:cloud   this image — the base + the gate CLI +
#                          the gate entrypoint. A strict superset of
#                          :latest for direct runs. The app does NOT use
#                          this image as-is: its explicit command does
#                          NOT override ENTRYPOINT, it becomes the
#                          ENTRYPOINT's arguments — so `docker run
#                          :cloud python3 <cli>/fineprint gate run ...`
#                          would hand entrypoint.sh "python3" as the
#                          agent command. Use :latest for the app (its
#                          ENTRYPOINT is just tini, so the command runs
#                          directly under it), or pass
#                          `--entrypoint ""` to run :cloud the app's way.
#
# What is inside, on top of the base:
#   - The gate CLI, vendored from the public repo's `free-wall` branch
#     at the commit pinned in cloud/cli/PIN (e60e61e, Nov 8, 2026;
#     suite 253 tests OK): fineprint_gate.py, fineprint_wall.py,
#     fineprint_definitions.py (11 rules, v2026-11-07 + synthetic
#     DENY-EXFIL), fineprint_canary.py, ed25519.py. Re-vendor with
#     cloud/sync-cli.sh; verify with cloud/tests/test_cloud_image.py.
#   - `sudo`: the wall's tripwire denies `sudo rm -rf ...` (F1), which
#     only means something if `sudo` exists in the image. Agents also
#     use it. Tiny, worth having.
#   - entrypoint.sh: prints the definitions version in force, then
#     execs `fineprint gate run -- <agent command>`. tini is PID 1
#     (inherited from the base image — see apps/desktop/docker/
#     Dockerfile): without an init the gate, a Python program with
#     no signal handlers, would be PID 1 and ignore SIGTERM, so
#     `docker stop` would hang until the stop timeout.
#
# What is NOT inside, and why (same as the desktop image):
#   - Muse Code (`muse`): not npm-installable — a launcher that
#     downloads the real binary from Meta's API and signs in with a
#     device code (OAuth). Use a custom command, or run it natively
#     on Linux / via WSL2.
#   - The Check engine: the image's job is to run an agent inside the
#     wall, not to run checks. Check runs on the laptop / in CI.
#   - Any credentials: auth crosses the boundary at run time (API-key
#     env vars, or a read-only bind-mount of the agent's config dir).
#     Never bake a key into an image.
#
# UNVERIFIED — read this before deploying anywhere:
#   This image has never been `docker build`ed or run (no Docker in
#   the build container, no real Mac/Windows). The nested-unshare
#   question (§7.2 of the investigation doc) decides whether the wall
#   works inside a default container at all: run
#   cloud/nested-unshare-test.sh on a real Docker host FIRST. If it
#   fails there, the wall needs `--security-opt seccomp=unconfined`,
#   which you can set on your own Docker host and in your own K8s
#   manifests but CANNOT set on Fargate, Cloud Run, ACI, Autopilot,
#   or Codespaces. The image is NOT published anywhere yet (no GHCR /
#   Docker Hub push).
FROM fineprint-wall:latest

# sudo: the tripwire denies `sudo rm -rf ...` (F1) — that only means
# something if sudo exists. (The base image already has util-linux,
# which provides `setpriv`, the wall's CAP_SYS_ADMIN drop.)
RUN apt-get update && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/*

# The gate CLI, vendored from free-wall (see cloud/cli/PIN).
COPY cloud/cli/tools/ /opt/fineprint/tools/
COPY cloud/cli/fineprint /usr/local/bin/fineprint
COPY cloud/entrypoint.sh /opt/fineprint/entrypoint.sh
RUN chmod +x /usr/local/bin/fineprint /opt/fineprint/entrypoint.sh \
    && python3 /opt/fineprint/tools/fineprint_gate.py definitions \
    && python3 -c "import sys; sys.path.insert(0, '/opt/fineprint/tools'); import fineprint_gate, fineprint_wall, fineprint_definitions, fineprint_canary, ed25519; print('gate modules import OK')"

WORKDIR /work

# The container's command IS the agent command. The entrypoint runs
# it inside the wall: `docker run fineprint-wall:cloud claude`.
# tini is PID 1 and forwards signals to entrypoint.sh, which execs
# the gate — so `docker stop` reaches the gate (and through it the
# agent) instead of hanging until the stop timeout.
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/fineprint/entrypoint.sh"]
