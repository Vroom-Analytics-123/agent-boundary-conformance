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
  codex: { id: 'codex', name: 'Codex', bin: 'codex' },
  'muse-code': { id: 'muse-code', name: 'Muse Code', bin: 'muse' },
  'claude-code': { id: 'claude-code', name: 'Claude Code', bin: 'claude' },
};

const DOCKER_IMAGE = 'python:3.12-slim';

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
        detail: 'The wall runs inside a small Linux container. Docker Desktop must be running.',
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
    // Checked lazily by the caller via docker; report what to do.
    return {
      found: null, bin: agent.bin,
      guidance: `${agent.name} must exist inside the Linux container. If the Run fails with "command not found", install ${agent.bin} in the container image or pick a custom command that is installed there.`,
    };
  }
  return { found: false, bin: null, guidance: 'The wall is unavailable, so no agent can run inside it yet.' };
}

/** Build the `docker run` argv that runs the gate inside Linux. */
function buildDockerRun({ image, workdir, cliDir, policyFile, logFile, command }) {
  const img = image || DOCKER_IMAGE;
  return ['docker', 'run', '--rm',
    '-v', `${workdir}:${workdir}`,
    '-v', `${cliDir}:${cliDir}`,
    '-w', workdir,
    img, 'python3', path.join(cliDir, 'fineprint'),
    'gate', 'run', '--policy', policyFile, '--log', logFile,
    '--', ...command];
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
  commandExists,
  detectRuntime,
  resolveAgent,
  buildDockerRun,
  buildWslRun,
  describeRuntime,
};
