'use strict';
/* Integration against the REAL `fineprint` CLI (sibling checkout,
 * read-only — this test never modifies it).
 * Run: FINEPRINT_REAL_CLI=1 npm run test:real-cli
 * Path: FINEPRINT_REAL_CLI_PATH, or ~/workspace/fineprint-free-check/fineprint.
 * Scenarios: find; check (outcome recorded, not assumed); `gate
 * definitions` (version in force); gate run tripwire deny (T1) and
 * allow (T2) in confine mode; the wall stopping a script that reads
 * outside the scope without naming it (T3); denylist probe (the
 * sibling CLI DOES enforce denied_paths); gate check in deny mode
 * (credential read denied, normal file allowed); the real deny log
 * verifies through the app's own audit module (Python-spaced hash).
 * NOTE: wall runs are slow in-container (~30-60s each: unshare +
 * mount setup). That is the real wall's cost here, not a test bug.
 * BRANCH REQUIREMENT (Nov 8): these tests run against the WALL, so
 * the sibling checkout must be on branch `free-wall` — `free-check-gate`
 * has no `tools/fineprint_wall.py`, and without it 5 of 8 tests fail
 * with the misleading "command not found: 'cat'" (the wall cannot run,
 * so the gated command never executes). The pre-flight below fails
 * fast with that branch requirement named, instead of letting a
 * future audit chase the false failure. Pin a different sibling per
 * run with FINEPRINT_REAL_CLI_PATH. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ENABLED = process.env.FINEPRINT_REAL_CLI === '1';
const REAL_CLI = process.env.FINEPRINT_REAL_CLI_PATH
  || path.join(os.homedir(), 'workspace', 'fineprint-free-check', 'fineprint');

// Pre-flight (Nov 8): only when the tests are enabled — with them
// skipped, `npm test` never touches the sibling checkout.
const REAL_CLI_WALL = path.join(path.dirname(REAL_CLI), 'tools', 'fineprint_wall.py');
if (ENABLED && !fs.existsSync(REAL_CLI_WALL)) {
  throw new Error(
    `real-CLI tests need the sibling CLI on branch free-wall: ${REAL_CLI_WALL} is missing — `
    + `the sibling checkout (${path.dirname(REAL_CLI)}) is on a branch without the wall `
    + `(free-check-gate). Switch that checkout to free-wall, or point FINEPRINT_REAL_CLI_PATH `
    + `at a free-wall checkout.`);
}

const {
  findCli, check, gateRun, gateCheck, verifyLog, probeDenylistSupport,
  definitions,
} = require('../core/cli');
const { parseLog, verifyChain } = require('../core/audit');
const { verdictForGate } = require('../core/verdict');

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'fp-realcli-'));
}

function confinePolicyFile(dir, allowed) {
  const file = path.join(dir, 'fineprint-gate.json');
  fs.writeFileSync(file, JSON.stringify({
    mode: 'confine',
    denied_paths: [], denied_hosts: [], allowed_commands: [],
    allowed_paths: allowed, allowed_hosts: [],
  }));
  return file;
}

function denyPolicyFile(dir) {
  const file = path.join(dir, 'fineprint-gate.json');
  fs.writeFileSync(file, JSON.stringify({
    mode: 'deny',
    denied_paths: [], denied_hosts: [], allowed_commands: [],
    allowed_paths: ['.'], allowed_hosts: [],
  }));
  return file;
}

test('real CLI: pre-flight fails fast when the sibling checkout is not free-wall', async (t) => {
  // The guard is module-level and only active when FINEPRINT_REAL_CLI=1,
  // so verify it by loading the file in a child with a bad path and
  // reading its failure. Plain `node <file>` (not `node --test` — the
  // test runner refuses to run recursively from inside a test file):
  // the guard throws at load, before any test runs, so this cannot
  // recurse — the child's own pre-flight test never executes.
  const { spawnSync } = require('node:child_process');
  const badDir = tmpdir();
  t.after(() => fs.rmSync(badDir, { recursive: true, force: true }));
  const badCli = path.join(badDir, 'fineprint');
  fs.writeFileSync(badCli, '#!/bin/sh\necho hi\n');
  const res = spawnSync(process.execPath, [__filename], {
    env: {
      ...process.env,
      FINEPRINT_REAL_CLI: '1',
      FINEPRINT_REAL_CLI_PATH: badCli,
    },
    encoding: 'utf8',
    timeout: 60000,
  });
  assert.notEqual(res.status, 0, 'the child run must fail');
  const out = (res.stdout || '') + (res.stderr || '');
  assert.match(out, /free-wall/);
  assert.match(out, /fineprint_wall\.py/);
  assert.match(out, /FINEPRINT_REAL_CLI_PATH/);
});

test('real CLI: found, check runs and the bundle parses when written', { skip: !ENABLED }, async (t) => {
  assert.ok(fs.existsSync(REAL_CLI), `real CLI not found at ${REAL_CLI}`);
  const cli = findCli(REAL_CLI);
  assert.ok(cli);
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const res = await check(cli, dir, {});
  assert.ok([0, 2, 3].includes(res.code), `unexpected check exit ${res.code}: ${res.stdout} ${res.stderr}`);
  if (res.bundlePath) {
    assert.ok(res.bundle, 'bundle parses');
    assert.ok(Array.isArray(res.bundle.invariant_results));
  }
});

test('real CLI: definitions in force are the built-in v1 pack', { skip: !ENABLED }, async () => {
  const cli = findCli(REAL_CLI);
  const d = await definitions(cli);
  assert.equal(d.ok, true);
  assert.equal(d.version, '2026-11-07');
  assert.equal(d.source, 'built-in');
  assert.equal(d.ruleCount, 11);
});

test('real CLI: tripwire denies outside the scope (T1) and allows inside (T2), confine mode', { skip: !ENABLED }, async (t) => {
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const allowed = path.join(dir, 'allowed');
  const secret = path.join(dir, 'secret');
  fs.mkdirSync(allowed);
  fs.mkdirSync(secret);
  fs.writeFileSync(path.join(allowed, 'note.txt'), 'hello\n');
  fs.writeFileSync(path.join(secret, 'keys.txt'), 'TOPSECRET\n');
  const cli = findCli(REAL_CLI);
  const policy = confinePolicyFile(dir, [allowed]);
  const log = path.join(dir, 'audit.jsonl');
  const denied = await gateRun(cli, { policy, log, command: ['cat', path.join(secret, 'keys.txt')], cwd: allowed, confine: true });
  assert.equal(denied.code, 2, `expected tripwire deny, got ${denied.code}: ${denied.stdout}`);
  assert.match(denied.stdout, /DENY/);
  assert.match(denied.stdout, /CONFINE-PATH/);
  const allowedRun = await gateRun(cli, { policy, log, command: ['cat', 'note.txt'], cwd: allowed, confine: true });
  assert.equal(allowedRun.code, 0, `expected allow, got ${allowedRun.code}: ${allowedRun.stdout} ${allowedRun.stderr}`);
  assert.match(allowedRun.stdout, /hello/);
  const entries = parseLog(fs.readFileSync(log, 'utf8'));
  assert.deepEqual(verifyChain(entries), { valid: true, brokenAt: -1 });
  const v = await verifyLog(cli, log);
  assert.equal(v.valid, true);
});

test('real CLI: wall stops a script that reads outside the scope (T3)', { skip: !ENABLED }, async (t) => {
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const allowed = path.join(dir, 'allowed');
  const secret = path.join(dir, 'secret');
  fs.mkdirSync(allowed);
  fs.mkdirSync(secret);
  fs.writeFileSync(path.join(secret, 'keys.txt'), 'TOPSECRET\n');
  fs.writeFileSync(path.join(allowed, 'readsecret.sh'), `cat ${path.join(secret, 'keys.txt')}\n`);
  const cli = findCli(REAL_CLI);
  const policy = confinePolicyFile(dir, [allowed]);
  const log = path.join(dir, 'audit.jsonl');
  const res = await gateRun(cli, { policy, log, command: ['bash', 'readsecret.sh'], cwd: allowed, confine: true });
  assert.notEqual(res.code, 0, 'the run must not succeed');
  assert.ok(!res.stdout.includes('TOPSECRET'), 'the secret was never printed');
});

test('real CLI: denylist probe reports SUPPORTED (sibling CLI enforces denied_paths)', { skip: !ENABLED }, async (t) => {
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const cli = findCli(REAL_CLI);
  const probe = await probeDenylistSupport(cli, dir);
  assert.equal(probe.supported, true);
  assert.match(probe.detail, /enforces the denylist/);
});

test('real CLI: gate check in deny mode denies a credential read, allows a normal file', { skip: !ENABLED }, async (t) => {
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const cli = findCli(REAL_CLI);
  const policy = denyPolicyFile(dir);
  const no = await gateCheck(cli, { policy, file: '/home/u/.ssh/id_rsa' });
  assert.equal(no.code, 2);
  assert.match(no.stdout, /DENY-CRED-SSH/);
  const records = await gateCheck(cli, { policy, file: '/tmp/x/records.txt' });
  assert.equal(records.code, 2);
  assert.match(records.stdout, /DENY-RECORDS/);
  const ok = await gateCheck(cli, { policy, file: path.join(dir, 'note.txt') });
  assert.equal(ok.code, 0);
});

test('real CLI: a real deny log verifies through the app audit module', { skip: !ENABLED }, async (t) => {
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const cli = findCli(REAL_CLI);
  const policy = denyPolicyFile(dir);
  const log = path.join(dir, 'audit.jsonl');
  const res = await gateRun(cli, { policy, log, command: ['cat', '/tmp/x/records.txt'], cwd: dir });
  assert.equal(res.code, 2);
  const entries = parseLog(fs.readFileSync(log, 'utf8'));
  assert.equal(entries.length, 1);
  assert.equal(entries[0].rule, 'DENY-RECORDS');
  assert.equal(entries[0].deterministic, true);
  assert.deepEqual(verifyChain(entries), { valid: true, brokenAt: -1 });
});

test('real CLI: without unshare the gate refuses (exit 3) and never runs the command', { skip: !ENABLED }, async (t) => {
  // The task's rule: if `unshare` is missing the gate refuses (exit 3)
  // — it never silently falls back to the tripwire. Hide unshare with
  // a PATH that holds only python3 (the CLI's shebang needs it) and
  // run an ALLOWABLE command: the tripwire passes it, the wall must
  // refuse it. The command's output must never appear.
  const dir = tmpdir();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const note = path.join(dir, 'note.txt');
  fs.writeFileSync(note, 'hello-from-note\n');
  const shim = path.join(dir, 'bin');
  fs.mkdirSync(shim);
  fs.symlinkSync('/usr/bin/python3', path.join(shim, 'python3'));
  const cli = findCli(REAL_CLI);
  const policy = denyPolicyFile(dir);
  const log = path.join(dir, 'audit.jsonl');
  const res = await gateRun(cli, {
    policy, log, command: ['cat', note], cwd: dir,
    env: { PATH: shim },
  });
  assert.equal(res.code, 3, `expected exit 3 refusal, got ${res.code}: ${res.stdout} ${res.stderr}`);
  assert.match(res.stdout, /wall needs.*unshare/i);
  assert.ok(!res.stdout.includes('hello-from-note'), 'the command must not have run');
  // The app surfaces exactly this refusal as wall-unavailable.
  assert.equal(verdictForGate(res.code, res.stdout).status, 'wall-unavailable');
  // No wall ever started: the log has no WALL_START entry.
  if (fs.existsSync(log)) {
    const entries = parseLog(fs.readFileSync(log, 'utf8'));
    assert.ok(!entries.some((e) => e.event === 'WALL_START'));
  }
});
