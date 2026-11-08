'use strict';
/**
 * OS notifications: when the wall blocks something, the app also tells
 * the user through the OS (macOS Notification Center / Windows Action
 * Center), so a block is visible even when the app window is behind
 * something else.
 *
 * This module is the testable core: it decides WHAT to notify and builds
 * the title/body. The Electron main process wires `show` to
 * `new Notification(...).show()`; in tests `show` is a recorder.
 * Only blocks notify — clean runs and check passes stay quiet.
 */
function shouldNotify(item) {
  return !!item && item.kind === 'blocked';
}

/** Build the notification payload for a blocked feed item. */
function notificationFor(item) {
  if (!shouldNotify(item)) return null;
  const rule = item.rule ? ` — stopped by “${item.rule}”` : '';
  return {
    title: 'FinePrint blocked the agent',
    body: `${item.title}${rule} ${item.determinismLine || ''}`.trim(),
  };
}

/** Show the notification for a blocked item. Returns true when shown. */
function notifyBlocked(show, item) {
  const payload = notificationFor(item);
  if (!payload) return false;
  show(payload.title, payload.body);
  return true;
}

/** Notify for each blocked item in a list. Returns how many were shown. */
function notifyBlockedItems(show, items) {
  let n = 0;
  for (const it of items || []) if (notifyBlocked(show, it)) n++;
  return n;
}

module.exports = {
  shouldNotify,
  notificationFor,
  notifyBlocked,
  notifyBlockedItems,
};
