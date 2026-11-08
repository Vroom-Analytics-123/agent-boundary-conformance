'use strict';
/* Definitions: the built-in v1 rules (copied from the sibling CLI),
 * fnmatch semantics, rule matching, family mapping, pack verification
 * against the maintainers' public key, and `gate definitions` parsing.
 * The CLI is the enforcer; this module mirrors it for display. */
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('crypto');
const {
  BUILTIN_VERSION,
  BUILTIN_RULES,
  DEFINITIONS_PUBLIC_KEY_HEX,
  ruleFamily,
  familiesInForce,
  protectionLine,
  fnmatch,
  pathRuleId,
  commandRuleId,
  hostRuleId,
  loadPack,
  verifyPack,
  parseDefinitionsOutput,
  checkForUpdates,
} = require('../core/definitions');
const { canonical } = require('../core/audit');

test('built-in v1 is 11 rules, version 2026-11-07', () => {
  assert.equal(BUILTIN_VERSION, '2026-11-07');
  assert.equal(BUILTIN_RULES.length, 11);
  assert.deepEqual(
    BUILTIN_RULES.map((r) => r.id),
    ['DENY-CRED-SSH', 'DENY-CRED-AWS', 'DENY-CRED-ENV', 'DENY-CRED-PEM',
     'DENY-CRED-KEY', 'DENY-CRED-TOKEN', 'DENY-RECORDS', 'DENY-DELETE',
     'DENY-SHRED', 'DENY-UNLINK', 'DENY-DEPLOY'],
  );
});

test('fnmatch: "*" matches "/" too (Python semantics, unlike shell globs)', () => {
  assert.equal(fnmatch('**/.ssh/**', '/home/u/.ssh/id_rsa'), true);
  assert.equal(fnmatch('**/.ssh', '/home/u/.ssh'), true);
  assert.equal(fnmatch('**/.env', '/a/.env'), true);
  assert.equal(fnmatch('**/.env', '/a/.envrc'), false);
  assert.equal(fnmatch('**/*key*.pem', '/a/mykey.pem'), true);
  assert.equal(fnmatch('**/*key*.pem', '/a/cacert.pem'), false);
  assert.equal(fnmatch('*deploy*', 'deploy.sh'), true);
  assert.equal(fnmatch('*deploy*', 'my-deploy-tool'), true);
  assert.equal(fnmatch('*deploy*', 'deploy'), true);
});

test('pathRuleId: first matching rule wins (SSH dir before key file)', () => {
  assert.equal(pathRuleId(BUILTIN_RULES, '/home/u/.ssh/id_rsa'), 'DENY-CRED-SSH');
  assert.equal(pathRuleId(BUILTIN_RULES, '/home/u/.aws/credentials'), 'DENY-CRED-AWS');
  assert.equal(pathRuleId(BUILTIN_RULES, '/tmp/x/.env'), 'DENY-CRED-ENV');
  assert.equal(pathRuleId(BUILTIN_RULES, '/tmp/x/records.txt'), 'DENY-RECORDS');
  assert.equal(pathRuleId(BUILTIN_RULES, '/tmp/note.txt'), null);
});

test('commandRuleId: rm fires on any listed flag, deploy on a glob basename', () => {
  assert.equal(commandRuleId(BUILTIN_RULES, ['rm', '-rf', '/tmp/x']), 'DENY-DELETE');
  assert.equal(commandRuleId(BUILTIN_RULES, ['rm', '-r', '-f', '/tmp/x']), 'DENY-DELETE');
  assert.equal(commandRuleId(BUILTIN_RULES, ['rm', '-r', '/tmp/x']), 'DENY-DELETE');
  assert.equal(commandRuleId(BUILTIN_RULES, ['rm', '/tmp/x']), null);
  assert.equal(commandRuleId(BUILTIN_RULES, ['unlink', '/tmp/x']), 'DENY-UNLINK');
  assert.equal(commandRuleId(BUILTIN_RULES, ['shred', '/tmp/x']), 'DENY-SHRED');
  assert.equal(commandRuleId(BUILTIN_RULES, ['deploy.sh']), 'DENY-DEPLOY');
  assert.equal(commandRuleId(BUILTIN_RULES, ['kubectl', 'apply']), null);
  assert.equal(commandRuleId(BUILTIN_RULES, ['ls', '/tmp']), null);
});

test('hostRuleId: no host rules in v1', () => {
  assert.equal(hostRuleId(BUILTIN_RULES, 'evil.example.net'), null);
});

test('ruleFamily maps every rule id to its plain-language family', () => {
  assert.equal(ruleFamily('DENY-CRED-SSH').name, 'Credential theft');
  assert.equal(ruleFamily('DENY-RECORDS').name, 'Credential theft');
  assert.equal(ruleFamily('DENY-DELETE').name, 'Destructive deletes');
  assert.equal(ruleFamily('DENY-UNLINK').name, 'Destructive deletes');
  assert.equal(ruleFamily('DENY-EXFIL').name, 'Exfiltration');
  assert.equal(ruleFamily('DENY-DEPLOY').name, 'Unapproved deploys');
  assert.equal(ruleFamily('DENY-PATH').name, 'Your own deny list');
  assert.equal(ruleFamily('CONFINE-PATH').name, 'Folder confinement');
  assert.equal(ruleFamily('DENY-NOPE'), null);
});

test('protection line names all four families', () => {
  assert.equal(
    protectionLine(BUILTIN_VERSION),
    'Protected by FinePrint definitions v2026-11-07 — credential theft, destructive deletes, exfiltration, unapproved deploys blocked.',
  );
  assert.deepEqual(familiesInForce(BUILTIN_RULES),
    ['credential-theft', 'destructive-deletes', 'exfiltration', 'unapproved-deploys']);
});

test('parseDefinitionsOutput reads the real `gate definitions` output', () => {
  const out = 'definitions: v2026-11-07 (built-in)\nrules: 11\n  DENY-CRED-SSH    path     SSH private keys and config\nupdate: a new pack ships with a FinePrint release.\n';
  assert.deepEqual(parseDefinitionsOutput(out), { version: '2026-11-07', source: 'built-in', ruleCount: 11 });
  assert.equal(parseDefinitionsOutput('garbage'), null);
});

test('verifyPack: a pack signed with the maintainers key verifies; tampering fails', () => {
  // Sign a pack with a fresh keypair, then verify it against THAT key
  // (the flow works); the maintainers' key itself is only held by the
  // release process, so the app never sees its private half.
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ed25519');
  const pubRaw = publicKey.export({ type: 'spki', format: 'der' });
  const rawHex = pubRaw.subarray(-32).toString('hex');
  const pack = { version: '2026-11-07', rules: BUILTIN_RULES };
  const sig = crypto.sign(null, Buffer.from(canonical(pack)), privateKey).toString('base64');
  const signed = { ...pack, signature: sig };
  assert.deepEqual(verifyPack(signed, rawHex), { valid: true, reason: '' });
  const tampered = { ...signed, version: '2026-11-08' };
  assert.equal(verifyPack(tampered, rawHex).valid, false);
  assert.match(verifyPack(tampered, rawHex).reason, /Signature does not match/);
  assert.equal(verifyPack({ version: '2026-11-07', rules: [] }).valid, false);
});

test('verifyPack rejects a signature from the wrong key', () => {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ed25519');
  const pack = { version: '2026-11-07', rules: BUILTIN_RULES };
  const sig = crypto.sign(null, Buffer.from(canonical(pack)), privateKey).toString('base64');
  const signed = { ...pack, signature: sig };
  // Verify against the maintainers' key (not the signing key) -> fails.
  assert.equal(verifyPack(signed, DEFINITIONS_PUBLIC_KEY_HEX).valid, false);
  assert.ok(publicKey); // the signing key is only used to make the fixture
});

test('checkForUpdates: same version is up-to-date; a newer in-force version is reported', () => {
  assert.equal(checkForUpdates({ currentVersion: '2026-11-07', inForceVersion: '2026-11-07' }).status, 'up-to-date');
  const newer = checkForUpdates({ currentVersion: '2026-11-07', inForceVersion: '2026-11-14' });
  assert.equal(newer.status, 'update-available');
  assert.equal(newer.latestVersion, '2026-11-14');
  assert.equal(checkForUpdates({ currentVersion: '2026-11-07', inForceVersion: null }).status, 'no-source');
});

test('loadPack reads the sibling pack format', () => {
  const fs = require('fs');
  const os = require('os');
  const path = require('path');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fp-defs-'));
  const file = path.join(dir, 'fineprint-definitions.json');
  fs.writeFileSync(file, JSON.stringify({ version: '2026-11-07', rules: BUILTIN_RULES, signature: 'abc' }));
  const pack = loadPack(file);
  assert.equal(pack.version, '2026-11-07');
  assert.equal(pack.rules.length, 11);
  fs.rmSync(dir, { recursive: true, force: true });
});
