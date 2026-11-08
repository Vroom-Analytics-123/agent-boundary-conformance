'use strict';
/* Notifications feed: audit entries -> feed items with the stopping rule
 * (from the entry's own `rule` field) and the determinism line; check
 * results -> feed items; persistence. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  DETERMINISM_LINE,
  itemFromAuditEntry,
  itemFromCheckResult,
  itemFromGuardedRun,
  FeedStore,
} = require('../core/feed');
const { BUILTIN_RULES } = require('../core/definitions');

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'fp-feed-'));
}

test('a blocked records read becomes a feed item with the rule and the determinism line', () => {
  const item = itemFromAuditEntry(
    { action: { kind: 'file_read', target: '/tmp/x/records.txt' }, allowed: false, deterministic: true, rule: 'DENY-RECORDS', reason: 'file_read of a protected path' },
    { rules: BUILTIN_RULES, commandText: 'cat /tmp/x/records.txt' },
  );
  assert.ok(item);
  assert.equal(item.kind, 'blocked');
  assert.match(item.title, /tried to read \/tmp\/x\/records\.txt/);
  assert.equal(item.rule, 'Credential theft');
  assert.equal(item.ruleId, 'DENY-RECORDS');
  assert.deepEqual(item.catalogue, ['FP-004', 'FP-003']);
  assert.equal(item.deterministic, true);
  assert.equal(item.determinismLine, DETERMINISM_LINE);
  assert.equal(item.source, 'wall');
});

test('a blocked destructive command is labelled from its rule id', () => {
  const item = itemFromAuditEntry(
    { action: { kind: 'exec', target: 'rm -rf /tmp/x' }, allowed: false, deterministic: true, rule: 'DENY-DELETE', reason: 'command denied by definitions' },
    { rules: BUILTIN_RULES, commandText: 'rm -rf /tmp/x' },
  );
  assert.ok(item);
  assert.equal(item.rule, 'Destructive deletes');
  assert.equal(item.deterministic, true);
});

test('without a rule field the target is matched against the built-in rules', () => {
  const item = itemFromAuditEntry(
    { action: { kind: 'file_read', target: '/home/u/.ssh/id_rsa' }, allowed: false, reason: 'protected path' },
    { rules: BUILTIN_RULES, commandText: 'cat /home/u/.ssh/id_rsa' },
  );
  assert.ok(item);
  assert.equal(item.rule, 'Credential theft');
  assert.equal(item.deterministic, true);
});

test('a blocked action with no matching rule still records, without the determinism claim', () => {
  const item = itemFromAuditEntry(
    { action: { kind: 'file_read', target: '/etc/passwd' }, allowed: false, reason: 'outside the allowed scope.' },
    { rules: BUILTIN_RULES, commandText: 'cat /etc/passwd' },
  );
  assert.ok(item);
  assert.equal(item.kind, 'blocked');
  assert.equal(item.rule, null);
  assert.equal(item.deterministic, false);
  assert.equal(item.determinismLine, '');
});

test('allowed entries and wall start/end markers are not feed items', () => {
  assert.equal(itemFromAuditEntry({ action: { kind: 'file_read', target: '/tmp/note.txt' }, allowed: true, reason: 'ok' }, { rules: BUILTIN_RULES }), null);
  assert.equal(itemFromAuditEntry({ action: { kind: 'wall', target: 'start' }, allowed: true, event: 'WALL_START' }, { rules: BUILTIN_RULES }), null);
  assert.equal(itemFromAuditEntry({ action: { kind: 'wall', target: 'end' }, allowed: true, event: 'WALL_END' }, { rules: BUILTIN_RULES }), null);
});

test('check results become feed items: pass, blocked, unknown', () => {
  const pass = itemFromCheckResult({ code: 0, bundle: { invariant_results: [] }, bundlePath: '/tmp/b/bundle.json' });
  assert.equal(pass.kind, 'check-pass');
  assert.match(pass.title, /Check passed/);
  const blocked = itemFromCheckResult({
    code: 2,
    bundle: { invariant_results: [{ invariant_id: 'FP-001', intent_coverage: 'NOT_SATISFIED' }] },
    bundlePath: '/tmp/b/bundle.json',
  });
  assert.equal(blocked.kind, 'check-blocked');
  assert.match(blocked.title, /1 rule the setup does not hold/);
  const unknown = itemFromCheckResult({
    code: 3,
    bundle: { invariant_results: [{ invariant_id: 'FP-002', intent_coverage: 'UNKNOWN' }] },
    bundlePath: null,
  });
  assert.equal(unknown.kind, 'check-unknown');
  assert.match(unknown.title, /could not decide/);
});

test('a denied guarded run becomes a summary item; a clean run does not', () => {
  const denied = itemFromGuardedRun({ code: 2, command: ['cat', '/tmp/x/records.txt'], blockedCount: 1 });
  assert.ok(denied);
  assert.equal(denied.kind, 'blocked');
  assert.match(denied.title, /Stopped the agent/);
  assert.equal(denied.deterministic, true);
  assert.equal(itemFromGuardedRun({ code: 0, command: ['ls'], blockedCount: 0 }), null);
});

test('FeedStore appends, lists newest first, and persists across instances', () => {
  const dir = tmpdir();
  const file = path.join(dir, 'feed.json');
  const store = new FeedStore(file);
  store.append({ id: 'a', ts: '2026-11-07T10:00:00.000Z', kind: 'blocked', title: 'first' });
  store.append({ id: 'b', ts: '2026-11-07T11:00:00.000Z', kind: 'blocked', title: 'second' });
  assert.deepEqual(store.list().map((i) => i.id), ['b', 'a']);
  const reopened = new FeedStore(file);
  assert.deepEqual(reopened.list().map((i) => i.id), ['b', 'a']);
  reopened.clear();
  assert.deepEqual(reopened.list(), []);
  assert.deepEqual(new FeedStore(file).list(), []);
});
