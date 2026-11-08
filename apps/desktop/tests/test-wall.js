'use strict';
/* WallRuntime: detection (native/docker/wsl/none), agent resolution,
 * and the Docker command builder. Detection is injected for tests so
 * no real Docker or WSL is needed. */
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  detectRuntime, resolveAgent, buildDockerRun, buildWslRun, describeRuntime,
} = require('../core/wall');

test('native unshare wins over everything', () => {
  const r = detectRuntime({
    platform: 'linux',
    pathBins: { unshare: true, docker: true, wsl: false },
  });
  assert.equal(r.kind, 'native');
  assert.match(describeRuntime(r), /Wall ready/);
});

test('docker is used when unshare is missing and docker works', () => {
  const r = detectRuntime({
    platform: 'darwin',
    pathBins: { unshare: false, docker: true, wsl: false },
    dockerOk: true,
  });
  assert.equal(r.kind, 'docker');
});

test('docker installed but not running is "none" with a clear reason', () => {
  const r = detectRuntime({
    platform: 'darwin',
    pathBins: { unshare: false, docker: true, wsl: false },
    dockerOk: false,
  });
  assert.equal(r.kind, 'none');
  assert.match(r.label, /not running/);
});

test('nothing available is "none" with install guidance', () => {
  const r = detectRuntime({
    platform: 'darwin',
    pathBins: { unshare: false, docker: false, wsl: false },
  });
  assert.equal(r.kind, 'none');
  assert.match(r.detail, /Docker/);
});

test('agent resolution reports a missing binary in plain words', () => {
  const r = detectRuntime({ platform: 'linux', pathBins: { unshare: true } });
  const found = resolveAgent('codex', r, () => false);
  assert.equal(found.found, false);
  assert.match(found.guidance, /not found on PATH/);
  const unknown = resolveAgent('nope', r, () => true);
  assert.equal(unknown.found, false);
  assert.match(unknown.guidance, /Unknown agent/);
});

test('docker run mounts the folder and the CLI dir, and runs the gate inside', () => {
  const argv = buildDockerRun({
    image: 'python:3.12-slim',
    workdir: '/Users/ana/work',
    cliDir: '/Users/ana/fineprint',
    policyFile: '/Users/ana/work/fineprint-gate.json',
    logFile: '/Users/ana/work/fineprint-audit.jsonl',
    command: ['codex', '--help'],
  });
  assert.equal(argv[0], 'docker');
  assert.ok(argv.includes('/Users/ana/work:/Users/ana/work'), 'workdir bind-mounted');
  assert.ok(argv.includes('/Users/ana/fineprint:/Users/ana/fineprint'), 'CLI dir bind-mounted');
  assert.ok(argv.includes('gate'), 'gate subcommand present');
  assert.ok(argv.includes('--'), 'separator present');
  assert.equal(argv[argv.length - 1], '--help');
  assert.ok(argv.includes('python:3.12-slim'));
});

test('docker run defaults to the fineprint-wall image and lifts the seccomp block on unshare', () => {
  const argv = buildDockerRun({
    workdir: '/Users/ana/work',
    cliDir: '/Users/ana/fineprint',
    policyFile: '/Users/ana/work/fineprint-gate.json',
    logFile: '/Users/ana/work/fineprint-audit.jsonl',
    command: ['claude', '--help'],
  });
  assert.ok(argv.includes('fineprint-wall:latest'), 'custom image is the default');
  const seccomp = argv.indexOf('--security-opt');
  assert.ok(seccomp >= 0 && argv[seccomp + 1] === 'seccomp=unconfined',
    'seccomp=unconfined so the wall can unshare inside the container');
});

test('docker run also lifts the AppArmor mount block (KiroCrew: the seccomp flag is only half the change)', () => {
  const argv = buildDockerRun({
    workdir: '/Users/ana/work',
    cliDir: '/Users/ana/fineprint',
    policyFile: '/Users/ana/work/fineprint-gate.json',
    logFile: '/Users/ana/work/fineprint-audit.jsonl',
    command: ['claude', '--help'],
  });
  // Docker's docker-default AppArmor profile denies the wall's first
  // mount with EACCES after both unshares succeed; without this flag
  // the wall fails on Ubuntu/Debian Docker hosts even with
  // seccomp=unconfined. On a host without AppArmor it is a no-op.
  const opts = argv.filter((a, i) => argv[i - 1] === '--security-opt');
  assert.ok(opts.includes('apparmor=unconfined'),
    'apparmor=unconfined so the mount is not refused');
});

test('docker run passes set API keys through and skips unset ones', () => {
  const argv = buildDockerRun({
    workdir: '/w', cliDir: '/c',
    policyFile: '/w/p.json', logFile: '/w/a.jsonl',
    command: ['codex'],
    env: { ANTHROPIC_API_KEY: 'sk-ant-x', OPENAI_API_KEY: '', MISSING_KEY: undefined },
  });
  assert.ok(argv.includes('ANTHROPIC_API_KEY=sk-ant-x'), 'set key passed through');
  assert.ok(!argv.some((a) => a.startsWith('OPENAI_API_KEY=')), 'empty key skipped');
  assert.ok(!argv.some((a) => a.startsWith('MISSING_KEY=')), 'unset key skipped');
});

test('docker run mounts agent config dirs read-only when asked', () => {
  const argv = buildDockerRun({
    workdir: '/w', cliDir: '/c',
    policyFile: '/w/p.json', logFile: '/w/a.jsonl',
    command: ['claude'],
    authMounts: [{ host: '/Users/ana/.claude', container: '/root/.claude' }],
  });
  assert.ok(argv.includes('/Users/ana/.claude:/root/.claude:ro'), 'config dir mounted read-only');
});

test('docker agent resolution: baked-in agents point at the image, muse-code says why it cannot be', () => {
  const r = detectRuntime({
    platform: 'darwin',
    pathBins: { unshare: false, docker: true, wsl: false },
    dockerOk: true,
  });
  assert.equal(r.kind, 'docker');
  const codex = resolveAgent('codex', r);
  assert.equal(codex.found, null, 'in the image if the image was built');
  assert.match(codex.guidance, /fineprint-wall/);
  assert.match(codex.guidance, /docker build/);
  const muse = resolveAgent('muse-code', r);
  assert.equal(muse.found, false, 'muse cannot be baked into the image');
  assert.match(muse.guidance, /cannot be baked into the container image/);
});

test('wsl run passes the gate invocation through', () => {
  const argv = buildWslRun({
    cliFile: '/home/ana/fineprint',
    policyFile: '/home/ana/work/fineprint-gate.json',
    logFile: '/home/ana/work/fineprint-audit.jsonl',
    command: ['claude', '--help'],
    cwd: '/home/ana/work',
  });
  assert.equal(argv[0], 'wsl');
  assert.ok(argv.includes('gate'));
  assert.ok(argv.includes('run'));
});
