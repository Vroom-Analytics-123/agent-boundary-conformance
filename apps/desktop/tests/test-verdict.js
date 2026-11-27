'use strict';
/* Verdicts: exit codes and bundles become plain-language outcomes.
 * Never "safe" or "certified" anywhere in this module's output. */
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  verdictForCheck, verdictForGate, parseCheckOutput,
} = require('../core/verdict');

function bundle(results) {
  return { invariant_results: results };
}

test('check exit 0 is a pass, with unmeasured listed not hidden', () => {
  const v = verdictForCheck(0, bundle([
    { invariant_id: 'FP-001', intent_coverage: 'SATISFIED', probe_rows: [] },
    { invariant_id: 'FP-002', intent_coverage: 'UNKNOWN', probe_rows: [{ unknown_kind: 'unsupported-adapter' }] },
  ]));
  assert.equal(v.status, 'pass');
  assert.match(v.title, /Passed/);
  assert.deepEqual(v.unmeasured, ['FP-002']);
  assert.ok(!/safe|certified/i.test(v.title + v.detail));
});

test('check exit 2 names the broken rules', () => {
  const v = verdictForCheck(2, bundle([
    { invariant_id: 'FP-001', intent_coverage: 'NOT_SATISFIED', probe_rows: [] },
    { invariant_id: 'FP-003', intent_coverage: 'SATISFIED', probe_rows: [] },
  ]));
  assert.equal(v.status, 'blocked');
  assert.deepEqual(v.broken, ['FP-001']);
  assert.match(v.detail, /1 broken rule/);
});

test('check exit 3 is "could not tell", never a pass', () => {
  const v = verdictForCheck(3, null);
  assert.equal(v.status, 'unknown');
  assert.ok(!/Passed/.test(v.title));
});

test('gate exit 2 surfaces the deny reason', () => {
  const v = verdictForGate(2, 'GATE: DENY — file_read outside allowed paths: \'/etc/passwd\'\nrefusing to run: cat /etc/passwd');
  assert.equal(v.status, 'denied');
  assert.match(v.detail, /outside allowed paths/);
});

test('gate exit 125 is a wall setup failure, nothing ran', () => {
  const v = verdictForGate(125, 'wall: mount failed');
  assert.equal(v.status, 'error');
  assert.match(v.title, /could not start/);
});

test('gate exit 3 with a missing-wall message is wall-unavailable', () => {
  const v = verdictForGate(3, 'wall: the wall needs `unshare` (util-linux) and it is not on PATH.');
  assert.equal(v.status, 'wall-unavailable');
});

test('gate exit 0 is allowed', () => {
  const v = verdictForGate(0, 'hello\n');
  assert.equal(v.status, 'allowed');
});

test('check output parsing finds the harness', () => {
  const p = parseCheckOutput('auto-detected: codex (found config)\nbinding: ok\n');
  assert.equal(p.harness, 'codex');
});
