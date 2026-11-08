'use strict';
/**
 * WallRuntime: where the wall can run, and how the app invokes it.
 *
 * The free wall is Linux-only (it uses `unshare` user+mount+net
 * namespaces). On macOS/Windows the wall runs inside a Linux container
 * (Docker) or WSL2 (Windows). There is no native macOS/Windows wall —
 * the app says so plainly instead of pretending.
 *
 * Runtimes, in preference order:
 *   native — `unshare` on PATH (Linux): `fineprint gate run -- CMD`
 *   docker — `docker` works: the CLI + guarded folder are bind-mounted
 *            into a small Linux image and the gate runs inside it.
 *   wsl    — Windows only: `wsl` runs the Linux CLI.
 *   none   — no Linux runtime: the wall cannot run. The Check screen
 *            still works; the Wall screen explains and offers an
 *            explicit, labelled tripwire-only run (never silent).
 */
const { execSync, spawnSync } = require('child_process');
const path = require('path');

const AGENTS = {
  codex: { id: 'codex', name: 'Codex', bin: 'codex', inDockerImage: true },
  'muse-code': { id: 'muse-code', name: 'Muse Code', bin: 'muse', inDockerImage: false },
  'claude-code': { id: 'claude-code', name: 'Claude Code', bin: 'claude', inDockerImage: true },
};

// The custom wall image (apps/desktop/docker/Dockerfile): the two
// npm-installable agent CLIs are pre-installed in it, pinned. Muse
// Code is NOT in it — it is a launcher that downloads its binary from
// Meta's API on first run and signs in with a device code, so there is
// nothing to npm-install and bake in. Build it once from the repo root:
//   docker build -t fineprint-wall:latest -f apps/desktop/docker/Dockerfile .
// The image is not published anywhere yet; if it is not built, docker
// run fails with "unable to find image" and the Wall screen says so.
const DOCKER_IMAGE = 'fineprint-wall:latest';
const DOCKER_BUILD_HINT = 'docker build -t fineprint-wall:latest -f apps/desktop/docker/Dockerfile .';

function commandExists(bin, execFn) {
  const run = execFn || ((cmd) => {
    try { execSync(cmd, { stdio: 'ignore' }); return true; } catch { return false; }
  });
  return run(`command -v ${bin}`);
}

/**
 * Detect the wall runtime. `overrides` is for tests:
 * { platform, pathBins: {unshare, docker, wsl}, dockerOk }.
 */
function detectRuntime(overrides = {}) {
  const platform = overrides.platform || process.platform;
  const exists = (bin) => {
    if (overrides.pathBins && bin in overrides.pathBins) return overrides.pathBins[bin];
    return commandExists(bin);
  };
  if (exists('unshare')) {
    return {
      kind: 'native',
      label: 'Wall ready — built in (Linux).',
      detail: 'The wall runs directly on this machine using Linux namespaces.',
    };
  }
  if (exists('docker')) {
    const ok = overrides.dockerOk !== undefined ? overrides.dockerOk : (() => {
      try { execSync('docker info', { stdio: 'ignore', timeout: 10000 }); return true; } catch { return false; }
    })();
    if (ok) {
      return {
        kind: 'docker',
        label: 'Wall ready — Docker.',
        detail: 'The wall runs inside the fineprint-wall Linux container. Build the image once (see apps/desktop/docker/README.md) and keep Docker Desktop running.',
      };
    }
    return {
      kind: 'none',
      label: 'Wall unavailable — Docker is installed but not running.',
      detail: 'Start Docker Desktop and try again. The check still works without it.',
    };
  }
  if (platform === 'win32' && exists('wsl')) {
    return {
      kind: 'wsl',
      label: 'Wall ready — WSL2.',
      detail: 'The wall runs inside WSL2. The guarded folder must be reachable from WSL.',
    };
  }
  return {
    kind: 'none',
    label: 'Wall unavailable on this machine.',
    detail: 'The wall needs Linux namespaces (unshare), Docker, or WSL2. '
      + 'Install Docker Desktop to use the wall; the check still works without it.',
  };
}

/** Where the agent binary lives in a runtime, or null + guidance. */
function resolveAgent(agentId, runtime, execFn) {
  const agent = AGENTS[agentId];
  if (!agent) return { found: false, bin: null, guidance: `Unknown agent: ${agentId}. Pick Codex, Muse Code, or Claude Code — or type a custom command.` };
  if (runtime.kind === 'native' || runtime.kind === 'wsl') {
    const found = commandExists(agent.bin, execFn);
    return found
      ? { found: true, bin: agent.bin, guidance: '' }
      : { found: false, bin: null, guidance: `${agent.name} (${agent.bin}) was not found on PATH. Install it, or type a custom command that is on PATH.` };
  }
  if (runtime.kind === 'docker') {
    if (!agent.inDockerImage) {
      // Muse Code cannot be baked into the image: its launcher
      // downloads the real binary from Meta's API on first run and
      // signs in with a device code (OAuth). There is nothing to
      // npm-install, so the image has no `muse` binary.
      return {
        found: false, bin: agent.bin,
        guidance: `${agent.name} cannot be baked into the container image — its launcher downloads the real binary from Meta's API and signs in with a device code, so there is nothing to install in the image. Run it natively on Linux or via WSL2, or type a custom command that is installed in the image.`,
      };
    }
    // Codex / Claude Code are pre-installed in the image — but only if
    // the image was actually built. `found: null` means "in the image
    // if the image exists"; a missing image fails at Run time with
    // "unable to find image", which the Wall screen reports.
    return {
      found: null, bin: agent.bin,
      guidance: `${agent.name} is pre-installed in the ${DOCKER_IMAGE} image. Build it first if you have not: ${DOCKER_BUILD_HINT}. If the Run still fails with "command not found", the image is stale or was never built.`,
    };
  }
  return { found: false, bin: null, guidance: 'The wall is unavailable, so no agent can run inside it yet.' };
}

/**
 * Build the `docker run` argv that runs the gate inside Linux.
 *
 * `env` is a map of host env vars to pass into the container (falsy
 * values are skipped) — the app passes ANTHROPIC_API_KEY /
 * OPENAI_API_KEY through when they are set, because auth has to cross
 * the container boundary and the agent inside needs its own login.
 * OAuth-based logins are not passed through by the app; `authMounts`
 * (array of {host, container}) bind-mounts an agent config dir
 * read-only (e.g. ~/.claude) for callers that opt into it. Mounting
 * your agent's config dir gives the container your agent credentials
 * — the wall protects the guarded folder, not the agent's own login.
 *
 * `--security-opt seccomp=unconfined`: the wall creates user + mount
 * namespaces with `unshare` inside the container, and Docker's default
 * seccomp profile gates `unshare` (and `clone`/`mount`) on
 * CAP_SYS_ADMIN, which a default container does not hold — so the
 * call fails with EPERM. Whether the flag is strictly needed is
 * contested between sources (investigation §7.2, §12); the
 * nested-unshare test on a real machine settles it. Until then the
 * flag stays: if `unshare` is allowed anyway it is harmless, and if
 * it is blocked the flag is what lets the wall start at all. The
 * least-privilege replacement is the profile in
 * cloud/docker/fineprint-seccomp.json (the default profile +
 * unconditional unshare/clone/mount, KiroCrew's shape) — wiring it
 * into this argv (the profile file has to ship with the app) is a
 * follow-up; the flag stays unconfined until then.
 *
 * `--security-opt apparmor=unconfined`: the seccomp flag is only half
 * the change on AppArmor hosts (Ubuntu/Debian families). Docker also
 * attaches its `docker-default` AppArmor profile, whose `deny mount`
 * refuses the wall's first mount with EACCES after both unshares
 * succeed (KiroCrew's docker guide). The flag lifts only AppArmor's
 * per-container rules; the seccomp profile, the dropped capabilities,
 * and the wall itself still apply. On a host without AppArmor it is
 * a no-op.
 */
function buildDockerRun({ image, workdir, cliDir, policyFile, logFile, command, env = {}, authMounts = [] }) {
  const img = image || DOCKER_IMAGE;
  const argv = ['docker', 'run', '--rm',
    '--security-opt', 'seccomp=unconfined',
    '--security-opt', 'apparmor=unconfined',
    '-v', `${workdir}:${workdir}`,
    '-v', `${cliDir}:${cliDir}`];
  for (const [name, value] of Object.entries(env)) {
    if (value) argv.push('-e', `${name}=${value}`);
  }
  for (const m of authMounts) {
    argv.push('-v', `${m.host}:${m.container}:ro`);
  }
  argv.push('-w', workdir,
    img, 'python3', path.join(cliDir, 'fineprint'),
    'gate', 'run', '--policy', policyFile, '--log', logFile,
    '--', ...command);
  return argv;
}

/** Build the `wsl` argv (Windows). Paths are passed through as-is; the
 *  caller is responsible for translating Windows paths to WSL paths. */
function buildWslRun({ cliFile, policyFile, logFile, command, cwd }) {
  return ['wsl', 'python3', cliFile, 'gate', 'run',
    '--policy', policyFile, '--log', logFile, '--', ...command];
}

/** Plain-language description of a runtime for Settings. */
function describeRuntime(runtime) {
  return `${runtime.label} ${runtime.detail}`;
}

module.exports = {
  AGENTS,
  DOCKER_IMAGE,
  DOCKER_BUILD_HINT,
  commandExists,
  detectRuntime,
  resolveAgent,
  buildDockerRun,
  buildWslRun,
  describeRuntime,
};
