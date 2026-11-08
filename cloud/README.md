# FinePrint cloud base image — the wall, baked into an image
#
# This directory is the cloud story, in one place. The principle is
# the same as local: the wall works wherever the user owns the launch.
# In the cloud that means: on a VM it is exactly a laptop; in a
# container the wall has to be the image's entrypoint, because a
# sidecar cannot enforce (different mount namespace, no CAP_SYS_ADMIN
# over the agent's mounts). One image covers the four cloud shapes.

## What is here

| File | What it is |
|---|---|
| `Dockerfile` | The image. `FROM fineprint-wall:latest` (the desktop image) + the gate CLI + the gate entrypoint. Tag: `fineprint-wall:cloud`. |
| `entrypoint.sh` | Prints the definitions version in force, then execs `fineprint gate run -- <agent command>`. |
| `cli/` | The vendored gate CLI from the public repo's `free-wall` branch (PIN: e60e61e) + the `fineprint` shim + `PIN`. Re-vendor with `sync-cli.sh`. |
| `sync-cli.sh` | Re-vendors the gate from `free-wall` at the pinned commit. |
| `devcontainer.json` | Codespaces / VS Code devcontainer template (builds from the Dockerfile; no registry needed). |
| `ecs-fargate.json` | ECS Fargate task definition (snippet). |
| `cloud-run.sh` | Cloud Run jobs deploy command. |
| `aci.yaml` | Azure Container Instances container group. |
| `workstations.md` | Google Cloud Workstations custom-image doc. |
| `agent37.md` | agent37.com custom template + the one exec call + the ToS question. |
| `nested-unshare-test.sh` | THE test. Run it on a real Docker host FIRST. |
| `tests/test_cloud_image.py` | The checks that can run here (no Docker). |

## Build

```sh
docker build -t fineprint-wall:latest \
  -f apps/desktop/docker/Dockerfile .
docker build -t fineprint-wall:cloud -f cloud/Dockerfile .
```

The image is **NOT published anywhere yet** — no GHCR / Docker Hub
push. The app uses it by name (`fineprint-wall:latest` for the base);
the cloud shapes each need the image in their own registry (ECR,
Artifact Registry, ACR) until a publish step exists.

## Use

The container's command IS the agent command:

```sh
docker run --rm -v "$PWD:/work" -w /work \
  -e ANTHROPIC_API_KEY \
  fineprint-wall:cloud claude
```

The entrypoint runs it inside the wall. Environment: `FINEPRINT_POLICY`
(a policy file inside the container; default is the built-in
protective denylist), `FINEPRINT_LOG` (path for the hash-chained audit
log — set it and mount a volume if you want the log out),
`FINEPRINT_CONFINE=1` (confine mode). Exit codes are the gate's: 0
the agent ran, 2 a rule denied the command (it never ran), 3 the gate
could not run here (e.g. no `unshare` — it refuses rather than
running unprotected). The agent's own exit code passes through.

## The nested-unshare question — run the test FIRST (UNVERIFIED)

The wall creates user + mount namespaces with `unshare` INSIDE the
container. Whether that works in a default Docker container is
contested between sources (investigation doc §7.2): Docker's docs
describe an exception for `unshare --user`; independent tests report
EPERM / bwrap failing. **Do not resolve this from the docs.** Run:

```sh
sh cloud/nested-unshare-test.sh
```

on a real Docker host (a Mac with Docker Desktop, a Linux host, a
cloud VM). It runs the one-command test, then the wall's T1–T7 smoke
test inside the cloud image, default seccomp first and with
`--security-opt seccomp=unconfined` second, and prints a verdict:

- **PASS** — the wall works in containers everywhere.
- **PASS-WITH-FLAG** — the wall needs `seccomp=unconfined`; it works
  where you control the runtime (your Docker host, your K8s), NOT on
  Fargate / Cloud Run / ACI / Autopilot / Codespaces.
- **FAIL** — the wall does not start in this container at all.

Until that test runs, **everything in this directory is unverified
end-to-end**: the image has never been `docker build`ed or run (no
Docker in the build container, no real Mac/Windows), and no cloud
shape has been deployed. The checks in `tests/` verify the vendored
CLI, the Dockerfile wiring, and the snippets — not the container
story. Say so wherever this image is described.

## Per shape, briefly

| Shape | How the wall goes in | What decides it |
|---|---|---|
| Cloud VM (EC2, GCE, Azure VM) | Exactly a laptop: `fineprint gate run -- <agent>` on the VM | Nothing new — plain Linux. Watch the distro: an Ubuntu 24.04 AMI carries the AppArmor problem (§8 of the investigation doc); Debian / Fedora do not. |
| Orchestrated container (ECS, EKS, GKE, AKS) | Baked into the image; the entrypoint is the gate | The nested-unshare test. On a node you control you can relax seccomp; on managed nodes you cannot. K8s has a native path (KEP-127, `hostUsers: false`) on new enough versions. |
| Serverless / managed container (Fargate, Cloud Run, ACI) | Baked into the image only — see the snippets | The nested-unshare test, per platform. There is no knob to turn on any of them; if it fails, that platform cannot run the wall. Cloud Run: use gen2 (jobs always do); gen1 is gVisor, do not use it. |
| Cloud dev environment (Codespaces, Gitpod, Workstations) | The devcontainer / custom image — see `devcontainer.json` and `workstations.md` | The nested-unshare test again. Cloud9 is shape A (an EC2 instance with sudo), not this shape. |
| agent37.com | The custom template — see `agent37.md` | One exec call in the default (gVisor) tier; the full-VM tier is the fallback. Ask them the ToS question before shipping the template. |

## What the image does not do

- It does not contain Muse Code (`muse`): not npm-installable, a
  launcher that downloads the real binary from Meta's API and signs
  in with a device code. Use a custom command, or run it natively.
- It does not contain the Check engine: the image runs an agent
  inside the wall; Check runs on the laptop / in CI.
- It does not contain credentials. Auth crosses the boundary at run
  time (API-key env vars, or a read-only config-dir mount). Never
  bake a key into an image.
- It does not enforce anything outside its own container. A sidecar
  cannot enforce the wall; an agent started outside the container
  is unwalled, full stop.
