'use strict';
/* OS notifications: only blocks notify; the payload names the rule and
 * carries the determinism line. `show` is injectable (Electron
 * Notification in the app, a recorder here). */
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  shouldNotify, notificationFor, notifyBlocked, notifyBlockedItems,
} = require('../core/notify');

const BLOCKED = {
  kind: 'blocked',
  title: 'Blocked: the agent tried to read /home/u/.ssh/id_rsa.',
  rule: 'Credential theft',
  determinismLine: 'This will always be blocked — the same action is denied every time.',
};
const CHECK_PASS = { kind: 'check-pass', title: 'Check passed: your setup held the line.', rule: null, determinismLine: '' };

test('only blocked items notify', () => {
  assert.equal(shouldNotify(BLOCKED), true);
  assert.equal(shouldNotify(CHECK_PASS), false);
  assert.equal(shouldNotify(null), false);
  assert.equal(shouldNotify({ kind: 'check-blocked' }), false);
});

test('the notification names the rule and carries the determinism line', () => {
  const n = notificationFor(BLOCKED);
  assert.equal(n.title, 'FinePrint blocked the agent');
  assert.match(n.body, /Credential theft/);
  assert.match(n.body, /This will always be blocked/);
  assert.match(n.body, /\.ssh\/id_rsa/);
  assert.equal(notificationFor(CHECK_PASS), null);
});

test('notifyBlocked shows once for a block, never for a pass', () => {
  const shown = [];
  const show = (title, body) => shown.push({ title, body });
  assert.equal(notifyBlocked(show, BLOCKED), true);
  assert.equal(shown.length, 1);
  assert.equal(notifyBlocked(show, CHECK_PASS), false);
  assert.equal(shown.length, 1);
});

test('notifyBlockedItems counts only the blocks', () => {
  const shown = [];
  const show = (title, body) => shown.push(title);
  const n = notifyBlockedItems(show, [BLOCKED, CHECK_PASS, { ...BLOCKED, title: 'second block' }]);
  assert.equal(n, 2);
  assert.equal(shown.length, 2);
});
