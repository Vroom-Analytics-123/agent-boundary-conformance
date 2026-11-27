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
  SECOND_OPINION_LABEL,
  S1_BLOCK_RULE,
  S1_MODEL_ERROR_RULE,
  itemFromAuditEntry,
  itemFromCheckResult,
  itemFromGuardedRun,
  summarizeFeed,
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

/* Boundaries under test (Nov 8): the feed aggregates, it does not just list. */

function blockedItem(overrides = {}) {
  return {
    id: `i-${Math.random().toString(36).slice(2, 8)}`,
    ts: '2026-11-08T10:00:00.000Z',
    kind: 'blocked',
    title: 'Blocked: the agent tried to read /tmp/x/records.txt.',
    detail: '',
    rule: 'Credential theft',
    ruleId: 'DENY-RECORDS',
    rulePlain: '',
    catalogue: [],
    deterministic: true,
    determinismLine: DETERMINISM_LINE,
    source: 'wall',
    agent: null,
    ...overrides,
  };
}

test('summarizeFeed counts blocked items by rule, most-blocked first', () => {
  const { summarizeFeed } = require('../core/feed');
  const items = [
    blockedItem({ ruleId: 'DENY-CRED-ENV', rule: 'Credential theft' }),
    blockedItem({ ruleId: 'DENY-CRED-ENV', rule: 'Credential theft' }),
    blockedItem({ ruleId: 'DENY-CRED-ENV', rule: 'Credential theft' }),
    blockedItem({ ruleId: 'DENY-DELETE', rule: 'Destructive deletes' }),
    { ...blockedItem({ ruleId: null, rule: null }), kind: 'check-pass', title: 'Check passed' },
  ];
  const s = summarizeFeed(items);
  assert.equal(s.total, 5);
  assert.equal(s.blocked, 4);
  assert.deepEqual(s.byRule, [
    { ruleId: 'DENY-CRED-ENV', rule: 'Credential theft', count: 3 },
    { ruleId: 'DENY-DELETE', rule: 'Destructive deletes', count: 1 },
  ]);
  assert.deepEqual(s.byAgent, []);
});

test('summarizeFeed counts by agent when items carry one; empty when none do', () => {
  const { summarizeFeed } = require('../core/feed');
  const items = [
    blockedItem({ agent: 'codex' }),
    blockedItem({ agent: 'codex' }),
    blockedItem({ agent: 'claude' }),
    blockedItem({}),
  ];
  const s = summarizeFeed(items);
  assert.deepEqual(s.byAgent, [
    { agent: 'codex', count: 2 },
    { agent: 'claude', count: 1 },
  ]);
  assert.deepEqual(summarizeFeed([blockedItem({})]).byAgent, []);
  assert.deepEqual(summarizeFeed([]), {
    total: 0, blocked: 0,
    secondOpinion: { total: 0, blocked: 0, errors: 0, allowed: 0 },
    byRule: [], byAgent: [],
  });
});

test('feed items carry the agent when the run knows it', () => {
  const item = itemFromAuditEntry(
    { action: { kind: 'file_read', target: '/tmp/x/records.txt' }, allowed: false, deterministic: true, rule: 'DENY-RECORDS', reason: 'file_read of a protected path' },
    { rules: BUILTIN_RULES, commandText: 'cat /tmp/x/records.txt', agent: 'codex' },
  );
  assert.ok(item);
  assert.equal(item.agent, 'codex');
  const summary = itemFromGuardedRun({ code: 2, command: ['cat', '/tmp/x/records.txt'], blockedCount: 1, agent: 'codex' });
  assert.equal(summary.agent, 'codex');
  // Without an agent the field stays null — the feed never invents one.
  const noAgent = itemFromAuditEntry(
    { action: { kind: 'file_read', target: '/tmp/x/records.txt' }, allowed: false, deterministic: true, rule: 'DENY-RECORDS', reason: 'x' },
    { rules: BUILTIN_RULES, commandText: 'cat /tmp/x/records.txt' },
  );
  assert.equal(noAgent.agent, null);
});

/* Canary entries in the feed (Nov 8): a FAILED canary is the objective-level
 * failure and must read as one; a HELD canary is not feed-worthy. */

test('a failed canary becomes a blocked feed item; a held canary does not', () => {
  const failed = itemFromAuditEntry(
    { action: { kind: 'canary', target: 'FINEPRINT-CANARY-abc' }, allowed: false, reason: 'marker reached the agent via stdout — the boundary failed', event: 'CANARY', reached: true, routes: ['stdout'] },
    { rules: BUILTIN_RULES, agent: 'codex' },
  );
  assert.ok(failed);
  assert.equal(failed.kind, 'blocked');
  assert.match(failed.title, /Boundary failed/);
  assert.match(failed.title, /stdout/);
  assert.match(failed.detail, /canary marker reached the agent/);
  assert.equal(failed.agent, 'codex');
  const held = itemFromAuditEntry(
    { action: { kind: 'canary', target: 'FINEPRINT-CANARY-abc' }, allowed: true, reason: 'the marker did not reach the agent — the boundary held', event: 'CANARY', reached: false, routes: [] },
    { rules: BUILTIN_RULES },
  );
  assert.equal(held, null);
});

/* Second-opinion verdicts (Nov 8, two-stage gate): the gate logs them
 * with the real entry shape from tools/fineprint_gate.py — second_opinion,
 * model + model_version, invariant, reason_seen, model_verdict +
 * model_reason verbatim, latency_s, deterministic: false, and the
 * synthetic rule id S1-BLOCK-bekko / S1-MODEL-ERROR. The feed must
 * render them distinctly — never as a deterministic rule denial —
 * and must render model allows too (the false-negative candidates).
 * Fixture entries below are field-for-field that shape. */

const S1_MODEL = 'bekko-system-one-v0-400m';
const S1_VERSION = 'hotchpotch/bekko-system-one-v0-400m @ 1960df5602bd93cc8d336fdebd9fb68a30926e13';
const S1_REASON = 'bekko probability_yes=0.547 (threshold 0.5)';

function s1BlockEntry(overrides = {}) {
  return {
    action: { kind: 'exec', target: 'rm /tmp/fp-s1-demo/victim.txt' },
    allowed: false,
    reason: `second opinion: ${S1_REASON} (model ${S1_MODEL})`,
    note: 'pre-flight: rm /tmp/fp-s1-demo/victim.txt',
    deterministic: false,
    rule: 'S1-BLOCK-bekko',
    second_opinion: true,
    model: S1_MODEL,
    model_version: S1_VERSION,
    invariant: 'deletion',
    reason_seen: 'a recursive delete destroys work with no undo',
    model_verdict: 'block',
    model_reason: S1_REASON,
    latency_s: 6.2,
    ...overrides,
  };
}

function s1AllowEntry(overrides = {}) {
  return {
    action: { kind: 'exec', target: 'cp /tmp/fp-s1-demo/note.txt /tmp/fp-s1-demo/note-copy.txt' },
    allowed: true,
    reason: `second opinion allowed: ${S1_REASON}`,
    note: 'pre-flight: cp /tmp/fp-s1-demo/note.txt /tmp/fp-s1-demo/note-copy.txt',
    second_opinion: true,
    model: S1_MODEL,
    model_version: S1_VERSION,
    invariant: 'exfiltration',
    reason_seen: 'copying a protected file out is how secrets leave the machine',
    model_verdict: 'allow',
    model_reason: S1_REASON,
    latency_s: 5.1,
    ...overrides,
  };
}

function s1ErrorEntry(overrides = {}) {
  return {
    action: { kind: 'exec', target: 'rm /tmp/fp-s1-demo/victim.txt' },
    allowed: false,
    reason: 'second opinion unavailable (the model did not answer) — blocked fail-closed',
    note: 'pre-flight: rm /tmp/fp-s1-demo/victim.txt',
    deterministic: false,
    rule: 'S1-MODEL-ERROR',
    second_opinion: true,
    model_error: true,
    model: S1_MODEL,
    model_version: S1_VERSION,
    invariant: 'deletion',
    reason_seen: 'a recursive delete destroys work with no undo',
    error: 'the model did not answer',
    ...overrides,
  };
}

test('a second-opinion block renders distinctly, not as a deterministic rule denial', () => {
  assert.equal(SECOND_OPINION_LABEL, 'second opinion — probabilistic');
  assert.equal(S1_BLOCK_RULE, 'S1-BLOCK-bekko');
  assert.equal(S1_MODEL_ERROR_RULE, 'S1-MODEL-ERROR');
  const item = itemFromAuditEntry(s1BlockEntry(), { rules: BUILTIN_RULES, agent: 'codex' });
  assert.ok(item);
  assert.equal(item.kind, 'second-opinion-block');
  assert.equal(item.secondOpinion, true);
  assert.match(item.title, /Second opinion blocked/);
  assert.match(item.title, /tried to run rm \/tmp\/fp-s1-demo\/victim\.txt/);
  // The model's reason, verbatim — not the gate's wrapped reason.
  assert.equal(item.detail, S1_REASON);
  assert.equal(item.model, S1_MODEL);
  assert.equal(item.modelVersion, S1_VERSION);
  assert.equal(item.modelVerdict, 'block');
  assert.equal(item.invariant, 'deletion');
  assert.equal(item.latencyS, 6.2);
  assert.equal(item.secondOpinionLabel, SECOND_OPINION_LABEL);
  assert.match(item.secondOpinionLine, /second opinion — probabilistic/);
  assert.match(item.secondOpinionLine, /bekko-system-one-v0-400m/);
  assert.match(item.secondOpinionLine, /1960df5602bd93cc8d336fdebd9fb68a30926e13/);
  assert.match(item.secondOpinionLine, /deletion/);
  // NOT a rule denial: no rule name, no determinism claim.
  assert.equal(item.rule, null);
  assert.equal(item.deterministic, false);
  assert.equal(item.determinismLine, '');
  assert.doesNotMatch(item.title + item.detail + item.secondOpinionLine, /always be blocked/);
  assert.equal(item.source, 'wall');
  assert.equal(item.agent, 'codex');
});

test('a second-opinion block is recognised by its rule id even without the flag', () => {
  const { second_opinion, ...noFlag } = s1BlockEntry();
  const item = itemFromAuditEntry(noFlag, { rules: BUILTIN_RULES });
  assert.ok(item);
  assert.equal(item.kind, 'second-opinion-block');
  assert.equal(item.secondOpinion, true);
});

test('a second-opinion model error renders distinctly as fail-closed, not a rule denial', () => {
  const item = itemFromAuditEntry(s1ErrorEntry(), { rules: BUILTIN_RULES });
  assert.ok(item);
  assert.equal(item.kind, 'second-opinion-error');
  assert.equal(item.secondOpinion, true);
  assert.match(item.title, /fail-closed/);
  assert.match(item.title, /tried to run rm \/tmp\/fp-s1-demo\/victim\.txt/);
  assert.match(item.detail, /the model did not answer/);
  assert.equal(item.model, S1_MODEL);
  assert.equal(item.modelVersion, S1_VERSION);
  assert.equal(item.modelVerdict, 'error');
  assert.equal(item.secondOpinionLabel, SECOND_OPINION_LABEL);
  assert.match(item.secondOpinionLine, /fail-closed/);
  assert.equal(item.rule, null);
  assert.equal(item.deterministic, false);
  assert.equal(item.determinismLine, '');
  assert.doesNotMatch(item.title + item.detail, /always be blocked/);
});

test('a second-opinion allow is a feed item of its own kind, not invisible', () => {
  const item = itemFromAuditEntry(s1AllowEntry(), { rules: BUILTIN_RULES, agent: 'codex' });
  assert.ok(item);
  assert.equal(item.kind, 'second-opinion-allow');
  assert.equal(item.secondOpinion, true);
  assert.match(item.title, /Second opinion allowed/);
  assert.match(item.title, /tried to run cp \/tmp\/fp-s1-demo\/note\.txt/);
  assert.equal(item.detail, S1_REASON);
  assert.equal(item.model, S1_MODEL);
  assert.equal(item.modelVersion, S1_VERSION);
  assert.equal(item.modelVerdict, 'allow');
  assert.equal(item.invariant, 'exfiltration');
  assert.equal(item.secondOpinionLabel, SECOND_OPINION_LABEL);
  // An allow is a false-negative candidate for review — the feed says so.
  assert.match(item.secondOpinionLine, /false-negative/);
  assert.equal(item.rule, null);
  assert.equal(item.deterministic, false);
  assert.equal(item.determinismLine, '');
  assert.equal(item.agent, 'codex');
  // A plain Stage 1 allow (no second opinion) is still not a feed item.
  assert.equal(itemFromAuditEntry(
    { action: { kind: 'exec', target: 'ls /tmp' }, allowed: true, reason: 'ok' },
    { rules: BUILTIN_RULES },
  ), null);
});

test('summarizeFeed counts second-opinion verdicts separately from deterministic denials', () => {
  const items = [
    blockedItem({ ruleId: 'DENY-RECORDS', rule: 'Credential theft' }),
    blockedItem({ ruleId: 'DENY-DELETE', rule: 'Destructive deletes' }),
    { ...blockedItem(), kind: 'second-opinion-block', title: 'Second opinion blocked: the agent tried to run rm /tmp/x.', rule: null, ruleId: 'S1-BLOCK-bekko', deterministic: false, determinismLine: '' },
    { ...blockedItem(), kind: 'second-opinion-error', title: 'Blocked fail-closed (second opinion failed).', rule: null, ruleId: 'S1-MODEL-ERROR', deterministic: false, determinismLine: '' },
    { ...blockedItem(), kind: 'second-opinion-allow', title: 'Second opinion allowed: the agent tried to run cp /tmp/x.', rule: null, ruleId: null, deterministic: false, determinismLine: '' },
    { ...blockedItem(), kind: 'check-pass', title: 'Check passed' },
  ];
  const s = summarizeFeed(items);
  assert.equal(s.total, 6);
  // Deterministic denials only — the two layers are never conflated.
  assert.equal(s.blocked, 2);
  assert.deepEqual(s.secondOpinion, { total: 3, blocked: 1, errors: 1, allowed: 1 });
  // byRule covers deterministic denials only — no S1 rule ids in it.
  assert.deepEqual(s.byRule, [
    { ruleId: 'DENY-DELETE', rule: 'Destructive deletes', count: 1 },
    { ruleId: 'DENY-RECORDS', rule: 'Credential theft', count: 1 },
  ]);
  assert.deepEqual(summarizeFeed([]), {
    total: 0, blocked: 0,
    secondOpinion: { total: 0, blocked: 0, errors: 0, allowed: 0 },
    byRule: [], byAgent: [],
  });
});

test('a run stopped only by the second opinion gets a non-deterministic summary', () => {
  const s1Only = itemFromGuardedRun({
    code: 2, command: ['rm', '/tmp/x/victim.txt'],
    blockedCount: 0, secondOpinionBlocked: 1,
  });
  assert.ok(s1Only);
  assert.equal(s1Only.kind, 'second-opinion-block');
  assert.match(s1Only.title, /Stopped the agent/);
  assert.match(s1Only.detail, /1 second-opinion/);
  assert.equal(s1Only.deterministic, false);
  assert.equal(s1Only.determinismLine, '');
  assert.equal(s1Only.secondOpinion, true);
  // A deterministically blocked run is unchanged.
  const det = itemFromGuardedRun({ code: 2, command: ['cat', '/tmp/x/records.txt'], blockedCount: 1 });
  assert.equal(det.kind, 'blocked');
  assert.equal(det.deterministic, true);
});
