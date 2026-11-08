# Docker wall path — how the wall runs on macOS/Windows

On Linux the wall runs natively (`unshare` namespaces). macOS has no
Linux namespaces, so on a Mac (and on Windows without WSL2) the app
runs the wall inside a Linux container. This directory holds the image
that makes that work.

## The image

`Dockerfile` builds `fineprint-wall:latest`:

- Python 3.12 + `util-linux` (`unshare` — the wall itself)
- Node.js 22 LTS + two agent CLIs, pinned:
  `@openai/codex@0.167.0`, `@anthropic-ai/claude-code@2.1.319`
- git + curl

Build it once, from the repo root:

```sh
docker build -t fineprint-wall:latest -f apps/desktop/docker/Dockerfile .
```

The image is **not published anywhere yet** — there is no
`docker pull fineprint-wall`. The app uses it by name; if it is not
built, `docker run` fails with "unable to find image" and the Wall
screen says so. Publishing (GHCR/Docker Hub) is a later step.

**Cloud use:** the same image is the base for the cloud base image
(`fineprint-wall:cloud`), which adds the gate CLI + the gate
entrypoint so the container starts inside the wall. See
`cloud/README.md` — and run `cloud/nested-unshare-test.sh` on a real
Docker host before deploying anywhere: it decides whether the wall
works inside a default container at all.

The `fineprint` CLI itself is **not** in the image: the app
bind-mounts it from the host checkout at run time, so the CLI version
always tracks the app.

## Which agents work in the container

| Agent | In the image | Notes |
|---|---|---|
| Codex (`codex`) | yes | npm-installed, pinned 0.167.0 |
| Claude Code (`claude`) | yes | npm-installed, pinned 2.1.319 |
| Muse Code (`muse`) | **no** | Not npm-installable. It is a launcher script that downloads the real binary from Meta's API on first run and signs in with a device code (OAuth), so there is nothing to bake into an image. On a Mac, Muse Code runs through the wall only via a custom command, or natively on Linux / via WSL2. |

## Auth — it has to cross the container boundary

The agent inside the container needs its own login, and the login does
not carry over by itself. The app passes API-key env vars through when
they are set on the host:

- `ANTHROPIC_API_KEY` → Claude Code
- `OPENAI_API_KEY` → Codex

OAuth-based logins (Claude Code's `~/.claude.json`, Codex's
`~/.codex/auth.json`) are **not** passed through by the app today.
The mechanism exists in `core/wall.js` (`authMounts` — a read-only
bind-mount of the agent's config dir); there is no Settings UI for it
yet. Mounting your agent's config dir gives the container your agent
credentials — that is the point (the agent needs them to work), but say
it plainly: the wall protects the guarded folder, not the agent's own
credentials.

## The nested-unshare caveat (unverified)

The wall creates user + mount namespaces with `unshare` **inside**
the container. Whether that works in a default Docker container is
contested between sources — and the profile itself explains why:
Docker's default seccomp profile gates `unshare` (and `clone` /
`mount`) on `CAP_SYS_ADMIN`, which a default container does not hold,
so the call fails with EPERM; whether a given runtime's default
permits it anyway depends on whether the calling process holds that
capability when seccomp evaluates the call (rootless Docker / Podman
run the container inside a user namespace where its root holds it;
rootful Docker drops it). See the investigation doc §12 for the exact
rule. So `buildDockerRun` passes `--security-opt seccomp=unconfined`,
and — the second half, from KiroCrew's docker guide — `--security-opt
apparmor=unconfined`: Docker also attaches its `docker-default`
AppArmor profile, whose `deny mount` refuses the wall's first mount
with EACCES after both unshares succeed. The least-privilege
replacement for the seccomp flag is the profile in
`cloud/docker/fineprint-seccomp.json` (the default profile +
unconditional `unshare`/`clone`/`mount`); wiring it into the app is a
follow-up — the flag stays unconfined until then.

The test that settles whether either flag is strictly needed (run on
a real Mac) is the gate's own probe, inside the container:

```sh
docker run --rm --entrypoint python3 fineprint-wall:latest \
  /opt/fineprint/tools/fineprint_gate.py probe
```

(`fineprint gate probe` — three steps: `unshare(CLONE_NEWUSER)`,
`unshare(CLONE_NEWNS)`, then the mount — plus a cap-drop line. It
exits 0 when all three pass, 3 when any fails.) Run it with default
seccomp, then with the profile, then with `seccomp=unconfined`, and
record which step fails where — or run
`cloud/nested-unshare-test.sh`, which does the probe, the one-command
test, and the wall's own smoke test (T1–T7) in that order. Until that
test runs, the Docker path is **unit-tested only** — it has never been
verified end-to-end on a real Mac or Windows machine, and this README
says so rather than claiming otherwise.

## Which runtime on a Mac

Docker Desktop is the default, but any runtime that exposes the
standard `docker` CLI works unchanged with the app's detection —
OrbStack (free for personal use, ~200–300MB idle vs Docker Desktop's
3–4GB) and Colima (free, open source) are the lighter options. Podman
(`podman machine`) is the candidate to test next: rootless Podman
containers already run inside a user namespace, so a nested `unshare`
works there without the seccomp flag (the same reason rootless Docker
may permit it) — but the app does not detect Podman yet, and the
nested-unshare test under `podman` has not been run. See the
investigation doc §12.

## What the app runs

`core/wall.js` `buildDockerRun` builds (workdir and CLI dir
bind-mounted, policy + log files passed through):

```sh
docker run --rm --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  -v <workdir>:<workdir> -v <cliDir>:<cliDir> \
  [-e ANTHROPIC_API_KEY=...] [-e OPENAI_API_KEY=...] \
  -w <workdir> fineprint-wall:latest \
  python3 <cliDir>/fineprint gate run \
    --policy <policyFile> --log <logFile> -- <agent command>
```
