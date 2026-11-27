'use strict';
/* Policy: load/save/validate/describe round-trips.
 * Shape mirrors the real CLI (tools/fineprint_gate.py Policy):
 * mode "deny" (default, protective denylist) or "confine" (opt-in
 * allowlist); denied_paths / denied_hosts add your own blocks;
 * allowed_commands overrides the denylist for one command. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  defaultPolicy, loadPolicy, savePolicy, validatePolicy, describePolicy,
} = require('../core/policy');

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'fp-policy-'));
}

test('default policy is mode deny, NOT folder confinement', () => {
  const p = defaultPolicy('/tmp/work');
  assert.equal(p.mode, 'deny');
  assert.deepEqual(p.allowed_paths, ['/tmp/work']);
  assert.deepEqual(p.allowed_hosts, []);
  assert.deepEqual(p.denied_paths, []);
  assert.deepEqual(p.denied_hosts, []);
  assert.deepEqual(p.allowed_commands, []);
});

test('save then load round-trips, and "." resolves to the file dir', () => {
  const dir = tmpdir();
  const file = path.join(dir, 'fineprint-gate.json');
  const saved = savePolicy(file, {
    mode: 'confine',
    denied_paths: ['**/.ssh/**'],
    denied_hosts: ['evil.example.net'],
    allowed_commands: ['deploy.sh'],
    allowed_paths: ['.', '/tmp'],
    allowed_hosts: ['api.example.com'],
  });
  assert.equal(saved._dir, dir);
  assert.equal(saved.mode, 'confine');
  assert.deepEqual(saved.denied_paths, ['**/.ssh/**']);
  assert.deepEqual(saved.allowed_commands, ['deploy.sh']);
  const d = describePolicy(saved);
  assert.ok(d.folders.includes(dir), 'dot resolves to the policy dir');
  assert.ok(d.folders.includes('/tmp'));
  assert.equal(d.hostsLine, 'Can reach on the internet: api.example.com.');
  assert.match(d.deniedLine, /1 paths, 1 hosts/);
  assert.match(d.allowedCommandsLine, /deploy\.sh/);
});

test('an unknown mode falls back to deny on load', () => {
  const dir = tmpdir();
  const file = path.join(dir, 'fineprint-gate.json');
  fs.writeFileSync(file, JSON.stringify({ mode: 'definitions', allowed_paths: ['.'] }));
  assert.equal(loadPolicy(file).mode, 'deny');
});

test('confined mode with no hosts says nothing can be reached', () => {
  const d = describePolicy({ mode: 'confine', allowed_paths: ['/tmp'], allowed_hosts: [] });
  assert.equal(d.hostsLine, 'Can reach nothing on the internet.');
});

test('deny mode with no hosts says the internet is open except the denylist', () => {
  const d = describePolicy({ mode: 'deny', allowed_paths: ['/tmp'], allowed_hosts: [] });
  assert.equal(d.hostsLine, 'Internet is open except what the definitions block.');
  assert.match(d.foldersLine, /Not confined to folders/);
});

test('validate flags a missing folder and a bad host, in plain words', () => {
  const problems = validatePolicy(
    { mode: 'confine', allowed_paths: ['/definitely/not/here', '/tmp'], allowed_hosts: ['not a host!!'] },
    '/tmp');
  assert.equal(problems.length, 2);
  assert.match(problems[0], /does not exist/);
  assert.match(problems[1], /valid host/);
});

test('validate flags a confined policy with no folders', () => {
  const problems = validatePolicy({ mode: 'confine', allowed_paths: [], allowed_hosts: [] }, '/tmp');
  assert.equal(problems.length, 1);
  assert.match(problems[0], /No folders are allowed/);
});

test('validate accepts the deny default (no confinement needed)', () => {
  assert.deepEqual(validatePolicy(defaultPolicy('/tmp/work'), '/tmp'), []);
});

test('describePolicy states the mode and the own deny list', () => {
  const d = describePolicy(defaultPolicy('/tmp/work'));
  assert.equal(d.mode, 'definitions');
  assert.equal(d.confine, false);
  assert.equal(d.deniedLine, 'Your own deny list is empty.');
  assert.equal(d.allowedCommandsLine, '');
});

test('describePolicy states the honest limits: bounded walk + scope not intent', () => {
  const deny = describePolicy(defaultPolicy('/tmp/work'));
  // Deny mode: the denylist walk covers the folder, /tmp, /var/tmp
  // and the credential spots in $HOME — a protected file in another
  // project folder is NOT hidden unless added or confined.
  assert.match(deny.boundsLine, /Denylist covers: this folder, \/tmp, \/var\/tmp/);
  assert.match(deny.boundsLine, /not hidden unless you add it to your deny list or turn on confinement/);
  assert.match(deny.scopeLine, /enforces scope.*not intent/);
  // Confine mode: the allowlist is the bound, so no bounds line.
  const conf = describePolicy({ mode: 'confine', allowed_paths: ['/tmp'], allowed_hosts: [] });
  assert.equal(conf.boundsLine, '');
  assert.match(conf.scopeLine, /enforces scope.*not intent/);
});

test('load rejects non-object JSON', () => {
  const dir = tmpdir();
  const file = path.join(dir, 'fineprint-gate.json');
  fs.writeFileSync(file, '[]');
  assert.throws(() => loadPolicy(file), /must be a JSON object/);
});

test('a policy carries a reason through save/load/describe', () => {
  const dir = tmpdir();
  const file = path.join(dir, 'fineprint-gate.json');
  const p = defaultPolicy('/tmp/work');
  assert.ok(p.reason && p.reason.length > 10, 'default policy has no reason');
  p.reason = 'we keep prod keys out of the agent\'s reach';
  const loaded = savePolicy(file, p);
  assert.equal(loaded.reason, 'we keep prod keys out of the agent\'s reach');
  const d = describePolicy(loaded);
  assert.match(d.reasonLine, /we keep prod keys out of the agent's reach/);
  // A policy file without a reason (an old one) still loads and
  // describes with an empty reason line.
  fs.writeFileSync(file, JSON.stringify({ mode: 'deny', allowed_paths: ['/tmp/work'] }));
  const old = loadPolicy(file);
  assert.equal(old.reason, '');
  assert.equal(describePolicy(old).reasonLine, '');
  fs.rmSync(dir, { recursive: true, force: true });
});
