'use strict';
/* AppState end-to-end (stub CLI): initialize -> check pass -> guarded
 * denylist deny (DENY-RECORDS) -> feed item with the rule + one OS
 * notification -> confinement toggle -> allowed_commands override ->
 * definitions status. This is the whole app flow minus the Electron
 * window. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { AppState } = require('../core/app-state');

const STUB = path.resolve(__dirname, 'stub-cli', 'fineprint');
fs.chmodSync(STUB, 0o755);

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'fp-appstate-'));
}

async function freshState(t) {
  const dir = tmpdir();
  const work = path.join(dir, 'work');
  fs.mkdirSync(work);
  fs.writeFileSync(path.join(work, 'note.txt'), 'hello\n');
  fs.writeFileSync(path.join(work, 'records.txt'), 'FAKE RECORDS\n');
  const notifications = [];
  const state = new AppState({
    userDataDir: path.join(dir, 'userdata'),
    showNotification: (title, body) => notifications.push({ title, body }),
  });
  state.saveSettings({ cliPath: STUB, workdir: work });
  const status = await state.initialize();
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return { state, status, work, dir, notifications };
}

test('initialize finds the stub CLI, reads the definitions in force, probes the denylist', async (t) => {
  const { status } = await freshState(t);
  assert.equal(status.cliMissing, false);
  assert.equal(status.cli.mode, 'direct');
  assert.equal(status.definitions.version, '2026-11-07');
  assert.equal(status.definitions.source, 'built-in');
  assert.equal(status.definitions.ruleCount, 11);
  assert.equal(status.definitions.valid, true);
  assert.equal(status.denylist.supported, true);
  assert.equal(
    status.protectionLine,
    'Protected by FinePrint definitions v2026-11-07 — credential theft, destructive deletes, exfiltration, unapproved deploys blocked.',
  );
  assert.equal(status.policy.mode, 'definitions');
  assert.equal(status.policy.confine, false);
  assert.equal(status.runtime.kind, 'native');
});

test('runCheck pass writes a feed item; runGuarded denylist deny writes a blocked item + notifies once', async (t) => {
  const { state, work, notifications } = await freshState(t);
  const check = await state.runCheck(work);
  assert.equal(check.code, 0);
  assert.equal(check.verdict.status, 'pass');
  assert.equal(check.feedItem.kind, 'check-pass');

  const guarded = await state.runGuarded({
    agent: 'codex', folder: work, command: ['cat', 'records.txt'],
  });
  assert.equal(guarded.code, 2);
  assert.equal(guarded.verdict.status, 'denied');
  assert.equal(guarded.logValid, true);
  assert.ok(guarded.output.includes('GATE: DENY'));
  assert.ok(guarded.output.includes('DENY-RECORDS'));
  const blocked = guarded.feedItems.filter((i) => i.kind === 'blocked');
  assert.ok(blocked.length >= 1, 'at least one blocked feed item');
  assert.equal(blocked[0].rule, 'Credential theft');
  assert.equal(blocked[0].ruleId, 'DENY-RECORDS');
  assert.equal(blocked[0].deterministic, true);
  assert.match(blocked[0].determinismLine, /always be blocked/);
  assert.equal(guarded.notified, 1);
  assert.equal(notifications.length, 1);
  assert.equal(notifications[0].title, 'FinePrint blocked the agent');
  assert.match(notifications[0].body, /Credential theft/);

  const feed = state.getFeed();
  assert.ok(feed.some((i) => i.kind === 'blocked'));
  assert.ok(feed.some((i) => i.kind === 'check-pass'));
  assert.equal(feed[0].kind, 'blocked', 'newest first: the block is on top');
});

test('runGuarded allows an ordinary command and does not notify', async (t) => {
  const { state, work, notifications } = await freshState(t);
  const guarded = await state.runGuarded({
    agent: 'codex', folder: work, command: ['cat', 'note.txt'],
  });
  assert.equal(guarded.code, 0);
  assert.equal(guarded.verdict.status, 'allowed');
  assert.equal(guarded.feedItems.filter((i) => i.kind === 'blocked').length, 0);
  assert.equal(notifications.length, 0);
});

test('confinement toggle switches the policy mode and the plain-language line', async (t) => {
  const { state, work } = await freshState(t);
  const on = state.setConfinement(true, [work]);
  assert.equal(on.policy.mode, 'confined');
  assert.equal(on.policy.confine, true);
  assert.match(on.policy.foldersLine, /Confined to these folders/);
  assert.ok(on.policy.folders.includes(work));
  const off = state.setConfinement(false);
  assert.equal(off.policy.mode, 'definitions');
  assert.equal(off.policy.confine, false);
  assert.match(off.policy.foldersLine, /Not confined to folders/);
});

test('setAllowedCommands writes the override into the policy', async (t) => {
  const { state, work } = await freshState(t);
  const after = state.setAllowedCommands(['deploy.sh', 'rm']);
  assert.deepEqual(after.policy.allowedCommands, ['deploy.sh', 'rm']);
  assert.match(after.policy.allowedCommandsLine, /deploy\.sh, rm/);
  const saved = JSON.parse(fs.readFileSync(`${work}/fineprint-gate.json`, 'utf8'));
  assert.deepEqual(saved.allowed_commands, ['deploy.sh', 'rm']);
  const cleared = state.setAllowedCommands([]);
  assert.deepEqual(cleared.policy.allowedCommands, []);
});

test('checkDefinitions reports up-to-date when the CLI and the app agree', async (t) => {
  const { state } = await freshState(t);
  const r = await state.checkDefinitions();
  assert.equal(r.status, 'up-to-date');
  assert.equal(r.currentVersion, '2026-11-07');
});

test('missing CLI raises the plain-language error on check and guard', async (t) => {
  const dir = tmpdir();
  const state = new AppState({ userDataDir: path.join(dir, 'userdata') });
  state.saveSettings({ cliPath: '/definitely/not/fineprint', workdir: dir });
  await state.initialize();
  assert.equal(state.getStatus().cliMissing, true);
  await assert.rejects(() => state.runCheck(dir), /not found/);
  await assert.rejects(() => state.runGuarded({ folder: dir, command: ['true'] }), /not found/);
  fs.rmSync(dir, { recursive: true, force: true });
});
