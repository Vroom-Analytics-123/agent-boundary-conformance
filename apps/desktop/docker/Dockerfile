# FinePrint wall image — the Linux container the desktop app runs the
# wall in on macOS/Windows (where there is no native `unshare`).
#
# What is inside:
#   - Python 3.12 + util-linux (`unshare` — the wall itself)
#   - Node.js 22 LTS + the two npm-installable agent CLIs, pinned:
#       @openai/codex 0.167.0, @anthropic-ai/claude-code 2.1.319
#   - git + curl (agents commonly need them)
#
# What is NOT inside, and why:
#   - The `fineprint` CLI itself: the app bind-mounts it from the host
#     checkout at run time, so the CLI version always tracks the app.
#   - Muse Code (`muse`): it is a launcher script that downloads the
#     real binary from Meta's API on first run and signs in with a
#     device code (OAuth). It is not npm-installable and cannot be
#     baked into an image. On a Mac, Muse Code runs through the wall
#     only via a custom command, or natively on Linux / via WSL2.
#   - Any credentials: auth has to cross the container boundary at run
#     time (API-key env vars, or a read-only bind-mount of the agent's
#     config dir — see README.md). Never bake a key into an image.
#
# Build (from the repo root):
#   docker build -t fineprint-wall:latest -f apps/desktop/docker/Dockerfile .
#
# The image is NOT published anywhere yet. The app uses it by name
# (`fineprint-wall:latest`); if it is not built, `docker run` fails
# with "unable to find image" and the Wall screen says so.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      util-linux curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS (NodeSource) — the agent CLIs are Node programs.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# Agent CLIs, pinned to the versions measured in the FinePrint runs.
RUN npm install -g @openai/codex@0.167.0 @anthropic-ai/claude-code@2.1.319 \
    && codex --version && claude --version

WORKDIR /work
