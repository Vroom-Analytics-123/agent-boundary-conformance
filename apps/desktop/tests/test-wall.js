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
