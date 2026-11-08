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
contested between sources: Docker's default seccomp profile is
documented as blocking `unshare` with `CLONE_NEWUSER`, and other
write-ups report the same call failing with `Operation not permitted`
in a default container. So `buildDockerRun` passes
`--security-opt seccomp=unconfined`: if `unshare` is allowed anyway
the flag is harmless; if it is blocked, the flag is what lets the wall
start at all. The one-command test that settles whether the flag is
strictly needed (run on a real Mac):

```sh
docker run --rm debian:bookworm-slim unshare --map-root-user --mount \
  sh -c 'mount -t tmpfs tmpfs /tmp && echo OK'
```

plus the wall's own smoke test (T1–T7) inside the same container.
Until that test runs, the Docker path is **unit-tested only** — it has
never been verified end-to-end on a real Mac or Windows machine, and
this README says so rather than claiming otherwise.

## What the app runs

`core/wall.js` `buildDockerRun` builds (workdir and CLI dir
bind-mounted, policy + log files passed through):

```sh
docker run --rm --security-opt seccomp=unconfined \
  -v <workdir>:<workdir> -v <cliDir>:<cliDir> \
  [-e ANTHROPIC_API_KEY=...] [-e OPENAI_API_KEY=...] \
  -w <workdir> fineprint-wall:latest \
  python3 <cliDir>/fineprint gate run \
    --policy <policyFile> --log <logFile> -- <agent command>
```
