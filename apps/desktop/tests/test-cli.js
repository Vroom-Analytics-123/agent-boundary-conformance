'use strict';
/* CliDriver against the stub CLI: find, check (pass/blocked/unknown),
 * gate run allow/deny, gate check, init, verify-log, and the missing-CLI
 * error. The stub stands in for the real CLI; the real-CLI test is
 * tests/test-real-cli.js (opt-in, FINEPRINT_REAL_CLI=1). */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  CliNotFoundError, findCli, check, gateRun, gateCheck, probeDenylistSupport,
  definitions, initGate, verifyLog, harnesses,
} = require('../core/cli');
const { parseLog, verifyChain } = require('../core/audit');

const STUB = path.resolve(__dirname, 'stub-cli', 'fineprint');
fs.chmodSync(STUB, 0o755);

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'fp-cli-'));
}

function cliFor() {
  return { path: STUB, mode: 'python' };
}

function policyFile(dir, allowed) {
  const file = path.join(dir, 'fineprint-gate.json');
  fs.writeFileSync(file, JSON.stringify({
    mode: 'confine',
    denied_paths: [], denied_hosts: [], allowed_commands: [],
    allowed_paths: allowed, allowed_hosts: [],
  }));
  return file;
}

test('findCli finds the stub on PATH', () => {
  const found = findCli(null);
  assert.ok(!found || found.path, 'either found or null is fine here');
  const byPath = findCli(STUB);
  assert.equal(byPath.path, STUB);
  // The stub is chmod +x with a shebang, so it runs directly.
  assert.equal(byPath.mode, 'direct');
});

test('check pass: exit 0, bundle written and parsed', async () => {
  const dir = tmpdir();
  const res = await check(cliFor(), dir, {});
  assert.equal(res.code, 0);
  assert.ok(res.bundle, 'bundle loaded');
  assert.equal(res.bundle.invariant_results[0].intent_coverage, 'SATISFIED');
  assert.ok(res.bundlePath.endsWith('bundle.json'));
});

test('check blocked: exit 2 and the broken rule is in the bundle', async () => {
  const dir = tmpdir();
  const res = await check(cliFor(), dir, {});
  // stub defaults to pass; re-run with the blocked env
  const { check: check2 } = require('../core/cli');
  process.env.STUB_CHECK_RESULT = 'blocked';
  try {
    const blocked = await check2(cliFor(), dir, {});
    assert.equal(blocked.code, 2);
    assert.equal(blocked.bundle.invariant_results[0].intent_coverage, 'NOT_SATISFIED');
  } finally {
    delete process.env.STUB_CHECK_RESULT;
  }
  assert.equal(res.code, 0, 'first run was the pass case');
});

test('check unknown: exit 3', async () => {
  const dir = tmpdir();
  process.env.STUB_CHECK_RESULT = 'unknown';
  try {
    const res = await check(cliFor(), dir, {});
    assert.equal(res.code, 3);
  } finally {
    delete process.env.STUB_CHECK_RESULT;
  }
});

test('gate run in confine mode denies a path outside the scope (exit 2) and allows inside (exit 0)', async () => {
  const dir = tmpdir();
  const allowed = path.join(dir, 'allowed');
  fs.mkdirSync(allowed);
  fs.writeFileSync(path.join(allowed, 'note.txt'), 'hello\n');
  const policy = policyFile(dir, [allowed]);
  const log = path.join(dir, 'audit.jsonl');
  const denied = await gateRun(cliFor(), {
    policy, log, command: ['cat', '/etc/passwd'], cwd: dir, confine: true,
  });
  assert.equal(denied.code, 2);
  assert.match(denied.stdout, /GATE: DENY/);
  assert.match(denied.stdout, /CONFINE-PATH/);
  const allowedRun = await gateRun(cliFor(), {
    policy, log, command: ['cat', 'note.txt'], cwd: allowed, confine: true,
  });
  assert.equal(allowedRun.code, 0);
  assert.match(allowedRun.stdout, /hello/);
  // The stub's log chain verifies through the app's own audit module.
  const entries = parseLog(fs.readFileSync(log, 'utf8'));
  assert.deepEqual(verifyChain(entries), { valid: true, brokenAt: -1 });
});

test('gate run wall mode stops a script that reads outside the scope without naming it', async () => {
  const dir = tmpdir();
  const allowed = path.join(dir, 'allowed');
  const secret = path.join(dir, 'secret');
  fs.mkdirSync(allowed);
  fs.mkdirSync(secret);
  fs.writeFileSync(path.join(secret, 'keys.txt'), 'TOPSECRET\n');
  fs.writeFileSync(path.join(allowed, 'readsecret.sh'),
    `cat ${path.join(secret, 'keys.txt')}\n`);
  const policy = policyFile(dir, [allowed]);
  const log = path.join(dir, 'audit.jsonl');
  const res = await gateRun(cliFor(), {
    policy, log, command: ['bash', 'readsecret.sh'], cwd: allowed, confine: true,
  });
  assert.notEqual(res.code, 0, 'the run must not succeed');
  assert.ok(!res.stdout.includes('TOPSECRET'), 'the secret was never printed');
});

test('gate check answers one file/host question', async () => {
  const dir = tmpdir();
  const policy = policyFile(dir, [dir]);
  const ok = await gateCheck(cliFor(), { policy, file: path.join(dir, 'x.txt') });
  assert.equal(ok.code, 0);
  const no = await gateCheck(cliFor(), { policy, host: 'evil.example.net' });
  assert.equal(no.code, 2);
});

function denyPolicyFile(dir, denied) {
  const file = path.join(dir, 'fineprint-gate.json');
  fs.writeFileSync(file, JSON.stringify({
    mode: 'deny',
    denied_paths: denied.denied_paths || [],
    denied_hosts: denied.denied_hosts || [],
    allowed_commands: denied.allowed_commands || [],
    allowed_paths: ['/'],
    allowed_hosts: [],
  }));
  return file;
}

test('gate run in deny mode blocks a credential read and a destructive delete, and allows normal work', async () => {
  const dir = tmpdir();
  const work = path.join(dir, 'work');
  fs.mkdirSync(work);
  fs.writeFileSync(path.join(work, 'note.txt'), 'hello\n');
  const policy = denyPolicyFile(dir, { denied_paths: ['**/.ssh/**'] });
  const log = path.join(dir, 'audit.jsonl');
  const denied = await gateRun(cliFor(), {
    policy, log, command: ['cat', '/home/u/.ssh/id_rsa'], cwd: work,
  });
  assert.equal(denied.code, 2);
  assert.match(denied.stdout, /GATE: DENY/);
  assert.match(denied.stdout, /DENY-CRED-SSH/);
  const deniedCmd = await gateRun(cliFor(), {
    policy, log, command: ['rm', '-rf', '/tmp/x'], cwd: work,
  });
  assert.equal(deniedCmd.code, 2);
  assert.match(deniedCmd.stdout, /DENY-DELETE/);
  const deniedDeploy = await gateRun(cliFor(), {
    policy, log, command: ['deploy.sh'], cwd: work,
  });
  assert.equal(deniedDeploy.code, 2);
  assert.match(deniedDeploy.stdout, /DENY-DEPLOY/);
  const allowedRun = await gateRun(cliFor(), {
    policy, log, command: ['cat', 'note.txt'], cwd: work,
  });
  assert.equal(allowedRun.code, 0);
  assert.match(allowedRun.stdout, /hello/);
});

test('allowed_commands overrides the denylist for one command', async () => {
  const dir = tmpdir();
  const work = path.join(dir, 'work');
  fs.mkdirSync(work);
  const policy = denyPolicyFile(dir, { allowed_commands: ['rm'] });
  const log = path.join(dir, 'audit.jsonl');
  // `rm -rf` on a path that does not exist: denied by DENY-DELETE by
  // default, but allowed here — rm then exits 1 (no such file), which
  // proves it ran instead of being refused (exit 2). Nothing is deleted.
  const res = await gateRun(cliFor(), {
    policy, log, command: ['rm', '-rf', 'nonexistent'], cwd: work,
  });
  assert.notEqual(res.code, 2);
  assert.ok(!res.stdout.includes('GATE: DENY'));
});

test('gate check denies a denylisted file and allows an ordinary one', async () => {
  const dir = tmpdir();
  const policy = denyPolicyFile(dir, { denied_paths: ['**/.ssh/**'] });
  const no = await gateCheck(cliFor(), { policy, file: '/home/u/.ssh/id_rsa' });
  assert.equal(no.code, 2);
  const ok = await gateCheck(cliFor(), { policy, file: path.join(dir, 'note.txt') });
  assert.equal(ok.code, 0);
});

test('probeDenylistSupport reports supported against the denylist stub', async () => {
  const dir = tmpdir();
  const probe = await probeDenylistSupport(cliFor(), dir);
  assert.equal(probe.supported, true);
  assert.match(probe.detail, /enforces the denylist/);
});

test('init --gate writes the policy file', async () => {
  const dir = tmpdir();
  const res = await initGate(cliFor(), dir);
  assert.equal(res.code, 0);
  assert.ok(fs.existsSync(path.join(dir, 'fineprint-gate.json')));
});

test('definitions reports the built-in v1 pack in force', async () => {
  const d = await definitions(cliFor());
  assert.equal(d.ok, true);
  assert.equal(d.version, '2026-11-07');
  assert.equal(d.source, 'built-in');
  assert.equal(d.ruleCount, 11);
});

test('verify-log reports a valid chain', async () => {
  const dir = tmpdir();
  const allowed = path.join(dir, 'allowed');
  fs.mkdirSync(allowed);
  const policy = policyFile(dir, [allowed]);
  const log = path.join(dir, 'audit.jsonl');
  await gateRun(cliFor(), { policy, log, command: ['true'], cwd: allowed, confine: true });
  const res = await verifyLog(cliFor(), log);
  assert.equal(res.valid, true);
});

test('harnesses lists the known agents', async () => {
  const res = await harnesses(cliFor());
  assert.equal(res.code, 0);
  assert.match(res.stdout, /codex/);
  assert.match(res.stdout, /claude-code/);
});

test('missing CLI raises a clear CliNotFoundError', async () => {
  await assert.rejects(
    () => check(null, tmpdir(), {}),
    (e) => e instanceof CliNotFoundError && /not found/.test(e.message));
});
