'use strict';
/* The app renders a REAL gate log — not just hand-written fixtures.
 * assets/demo-second-opinion-log.jsonl is the hash-chained audit log
 * the real gate wrote with the real bekko model (see /tmp/make_s1_real_log.py
 * for how it was produced: `gate run --no-wall` through run_guarded(),
 * model bekko-system-one-v0-400m from the local HF cache, one process
 * so the model loads once; the fail-closed entry comes from a second
 * Gate with a bogus helper python). Regenerate it the same way if the
 * gate's entry shape ever changes — do not hand-edit it, or the chain
 * breaks and this test fails on purpose.
 *
 * What this pins: the chain verifies, the three second-opinion
 * verdicts (block / allow / model-error) plus the deterministic
 * DENY-RECORDS denial render through the same itemFromAuditEntry the
 * live path uses, with the real model name + version + reason, and
 * the plain pre-flight allows and the "executed" entry stay invisible.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const audit = require('../core/audit');
const feed = require('../core/feed');
const { BUILTIN_RULES } = require('../core/definitions');

const LOG = path.join(__dirname, '..', 'assets', 'demo-second-opinion-log.jsonl');
const S1_VERSION_HASH = '1960df5602bd93cc8d336fdebd9fb68a30926e13';

test('a real gate log verifies and renders: deterministic block + three second-opinion verdicts', () => {
  const entries = audit.parseLogFile(LOG);
  assert.equal(entries.length, 9);
  assert.deepEqual(audit.verifyChain(entries), { valid: true, brokenAt: -1 });

  const items = entries
    .map((e) => feed.itemFromAuditEntry(e, { rules: BUILTIN_RULES, agent: 'codex' }))
    .filter(Boolean);
  // 9 entries -> 4 feed items: the plain pre-flight allows and the
  // "executed" entry are not feed items.
  assert.equal(items.length, 4);
  assert.deepEqual(items.map((i) => i.kind), [
    'blocked',
    'second-opinion-block',
    'second-opinion-allow',
    'second-opinion-error',
  ]);

  const [det, block, allow, error] = items;

  assert.equal(det.rule, 'Credential theft');
  assert.equal(det.ruleId, 'DENY-RECORDS');
  assert.equal(det.deterministic, true);
  assert.equal(det.determinismLine, feed.DETERMINISM_LINE);

  assert.equal(block.model, 'bekko-system-one-v0-400m');
  assert.match(block.modelVersion, new RegExp(S1_VERSION_HASH));
  assert.equal(block.modelReason, 'bekko probability_yes=0.651 (threshold 0.5)');
  assert.equal(block.invariant, 'deletion');
  assert.equal(typeof block.latencyS, 'number');
  assert.equal(block.secondOpinionLabel, 'second opinion — probabilistic');
  assert.equal(block.rule, null);
  assert.equal(block.deterministic, false);
  assert.equal(block.determinismLine, '');

  assert.equal(allow.modelReason, 'bekko probability_yes=0.386 (threshold 0.5)');
  assert.equal(allow.invariant, 'exfiltration');
  assert.match(allow.secondOpinionLine, /false-negative/);

  assert.match(error.title, /fail-closed/);
  assert.match(error.detail, /No module named 'sentence_transformers'/);
  assert.equal(error.rule, null);
  assert.equal(error.deterministic, false);

  const s = feed.summarizeFeed(items);
  assert.equal(s.total, 4);
  assert.equal(s.blocked, 1);
  assert.deepEqual(s.secondOpinion, { total: 3, blocked: 1, errors: 1, allowed: 1 });
  assert.deepEqual(s.byRule, [
    { ruleId: 'DENY-RECORDS', rule: 'Credential theft', count: 1 },
  ]);
});
