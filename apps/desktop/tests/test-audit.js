'use strict';
/* Audit log: chain verify (valid + tampered) and plain-language entries.
 * The test log is built with this module's own hasher, the same way the
 * Python side builds it (sha256 of canonical JSON without "hash"). */
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  ZERO_HASH, entryHash, parseLog, verifyChain, describeEntry,
} = require('../core/audit');

function chain(actions) {
  let prev = ZERO_HASH;
  const lines = [];
  for (const a of actions) {
    const e = { action: a.action, allowed: a.allowed, reason: a.reason, prev_hash: prev };
    if (a.event) e.event = a.event;
    if (a.extra) e.extra = a.extra;
    e.hash = entryHash(e);
    prev = e.hash;
    lines.push(JSON.stringify(e));
  }
  return lines.join('\n');
}

const SAMPLE = chain([
  { action: { kind: 'file_read', target: 'note.txt' }, allowed: true, reason: 'under allowed path' },
  { action: { kind: 'file_read', target: '/etc/passwd' }, allowed: false, reason: 'outside allowed paths' },
  { action: { kind: 'wall', target: 'start' }, allowed: true, reason: 'wall up', event: 'WALL_START', extra: { egress: 'none (network namespace, no route)' } },
  { action: { kind: 'wall', target: 'end' }, allowed: true, reason: 'wall down: exit 0', event: 'WALL_END', extra: { exit_code: 0 } },
  { action: { kind: 'network', target: 'evil.example.net' }, allowed: false, reason: 'not allowlisted', event: 'WALL_PROXY_DENY' },
]);

test('a well-formed log verifies', () => {
  const entries = parseLog(SAMPLE);
  assert.equal(entries.length, 5);
  assert.deepEqual(verifyChain(entries), { valid: true, brokenAt: -1 });
});

test('flipping an allow to a deny breaks the chain at that entry', () => {
  const entries = parseLog(SAMPLE);
  entries[1].allowed = true; // attacker flips a deny to an allow
  assert.deepEqual(verifyChain(entries), { valid: false, brokenAt: 1 });
});

test('entries render in plain language', () => {
  const entries = parseLog(SAMPLE);
  assert.match(describeEntry(entries[0]), /Allowed: tried to read note\.txt/);
  assert.match(describeEntry(entries[1]), /Blocked: tried to read \/etc\/passwd/);
  assert.match(describeEntry(entries[2]), /Wall started/);
  assert.match(describeEntry(entries[3]), /finished cleanly/);
  assert.match(describeEntry(entries[4]), /Blocked on the internet: evil\.example\.net/);
});

test('a denied entry names the rule and the determinism line', () => {
  const e = {
    action: { kind: 'file_read', target: '/tmp/x/records.txt' },
    allowed: false,
    reason: "file_read of a protected path: '/tmp/x/records.txt' resolves to '/tmp/x/records.txt'",
    rule: 'DENY-RECORDS',
    deterministic: true,
  };
  assert.match(describeEntry(e), /Stopped by rule DENY-RECORDS/);
  assert.match(describeEntry(e), /always be blocked/);
});

test('canary entries render as the objective-level verdict', () => {
  const failed = {
    action: { kind: 'canary', target: 'FINEPRINT-CANARY-abc' },
    allowed: false,
    reason: 'marker reached the agent via stdout — the boundary failed',
    event: 'CANARY',
    reached: true,
    routes: ['stdout'],
    verdict: 'FAILED',
  };
  assert.match(describeEntry(failed), /Boundary failed: the canary marker reached the agent via stdout/);
  const held = {
    action: { kind: 'canary', target: 'FINEPRINT-CANARY-abc' },
    allowed: true,
    reason: 'the marker did not reach the agent — the boundary held',
    event: 'CANARY',
    reached: false,
    routes: [],
    verdict: 'HELD',
  };
  assert.match(describeEntry(held), /Canary held: the marker did not reach the agent/);
});

/* A REAL log entry written by the sibling CLI (branch free-wall,
 * `fineprint gate run -- cat /tmp/x/records.txt`, 2026-11-07). The
 * hash must verify under this module — the real gate hashes Python's
 * json.dumps(entry, sort_keys=True) (spaced separators), and the
 * compact form hashes differently. If this test fails, the app would
 * call every real log BROKEN. */
const REAL_ENTRY = '{"action": {"kind": "file_read", "target": "/tmp/x/records.txt"}, "allowed": false, "deterministic": true, "hash": "c2651ed78ca06899b249a9a2d81db7a9439f764c23c030f07ca6dafb38868c9a", "note": "pre-flight: cat /tmp/x/records.txt", "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000", "reason": "file_read of a protected path: \'/tmp/x/records.txt\' resolves to \'/tmp/x/records.txt\'", "rule": "DENY-RECORDS"}';

test('a real gate log entry verifies (Python-spaced canonical form)', () => {
  const entries = parseLog(REAL_ENTRY);
  assert.equal(entries.length, 1);
  assert.deepEqual(verifyChain(entries), { valid: true, brokenAt: -1 });
  assert.equal(entryHash(entries[0]), 'c2651ed78ca06899b249a9a2d81db7a9439f764c23c030f07ca6dafb38868c9a');
  assert.match(describeEntry(entries[0]), /DENY-RECORDS/);
});

test('an empty log verifies (nothing to check)', () => {
  assert.deepEqual(verifyChain(parseLog('')), { valid: true, brokenAt: -1 });
});
