'use strict';
// Regression guard: the Electron entry files must parse. A syntax
// error in main.js kills the whole app at load ("App threw an error
// during load") with no window at all — the unit suite never loads
// these files, so check them explicitly.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const FILES = [
  'main.js',
  'preload.js',
  path.join('renderer', 'app.js'),
  path.join('renderer', 'demo.js'),
];

for (const f of FILES) {
  test(`${f} parses (node --check)`, () => {
    const out = execFileSync(process.execPath, ['--check', path.join(__dirname, '..', f)], { encoding: 'utf8' });
    assert.equal(typeof out, 'string');
  });
}

test('main.js still defines createWindow (the app entry)', () => {
  const fs = require('node:fs');
  const src = fs.readFileSync(path.join(__dirname, '..', 'main.js'), 'utf8');
  assert.match(src, /function createWindow\(demoDir\) \{/);
  assert.match(src, /createWindow\(demoDir\)/);
});
