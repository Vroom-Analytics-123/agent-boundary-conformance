'use strict';
/* Settings: defaults, load/save round-trip, bad file falls back. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  defaultSettings, loadSettings, saveSettings,
} = require('../core/settings');

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'fp-settings-'));
}

test('defaults are the antivirus defaults: confinement off', () => {
  const s = defaultSettings();
  assert.equal(s.confine, false);
  assert.equal(s.agent, 'codex');
  assert.equal(s.cliPath, null);
  assert.equal(s.definitionsSource, null);
});

test('save then load round-trips, unknown keys are dropped', () => {
  const dir = tmpdir();
  const file = path.join(dir, 'settings.json');
  const saved = saveSettings(file, {
    cliPath: '/usr/local/bin/fineprint',
    workdir: '/tmp/work',
    agent: 'claude-code',
    confine: true,
    folders: ['/tmp/work'],
    bogus: 'ignored',
  });
  assert.equal(saved.cliPath, '/usr/local/bin/fineprint');
  assert.equal(saved.agent, 'claude-code');
  assert.equal(saved.confine, true);
  assert.equal(saved.bogus, undefined);
  assert.deepEqual(loadSettings(file), saved);
});

test('missing or broken settings file falls back to defaults', () => {
  const dir = tmpdir();
  assert.deepEqual(loadSettings(path.join(dir, 'nope.json')), defaultSettings());
  const bad = path.join(dir, 'bad.json');
  fs.writeFileSync(bad, '{not json');
  assert.deepEqual(loadSettings(bad), defaultSettings());
});
