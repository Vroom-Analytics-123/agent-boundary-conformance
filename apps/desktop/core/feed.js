'use strict';
/**
 * Notifications feed: the home screen's record of what the agent tried
 * to do, what was blocked or stopped, and which rule stopped it.
 *
 * Feed items come from two sources, both owned by the CLI:
 *   - audit-log entries from a guarded run (via audit.describeEntry's
 *     raw entries), labelled with the rule that stopped the action
 *     from the entry's own `rule` field (the gate writes it, e.g.
 *     DENY-RECORDS). This labelling is PRESENTATION only — the block
 *     decision itself came from the CLI; the feed never re-decides
 *     anything.
 *   - `fineprint check` results (pass / blocked / unknown).
 * Allowed pre-flight entries and WALL_START/WALL_END markers are not
 * feed items on their own — the run's verdict summarises them.
 *
 * Determinism: a denial is deterministic — the same action is denied
 * every time. The gate marks every denial `deterministic: true` in the
 * log, and blocked items carry that line; it is the antivirus promise
 * ("this will always be blocked").
 */
const fs = require('fs');
const path = require('path');
const definitions = require('./definitions');

const DETERMINISM_LINE = 'This will always be blocked — the same action is denied every time.';

function newId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function whatHappened(e) {
  const kind = e.action && e.action.kind;
  const target = e.action && e.action.target;
  if (kind === 'file_read') return `tried to read ${target}`;
  if (kind === 'file_write') return `tried to write ${target}`;
  if (kind === 'network') return `tried to reach ${target}`;
  if (kind === 'command') return `tried to run ${target}`;
  if (kind === 'wall') return e.reason || 'wall event';
  return `tried ${kind || 'something'} ${target || ''}`;
}

/**
 * One audit entry -> one feed item, or null when the entry is not
 * feed-worthy (allowed actions, wall start/end markers).
 * The rule comes from the entry's own `rule` field — the CLI writes
 * it (e.g. DENY-RECORDS) and it is authoritative. When an entry has
 * no rule (older logs), the target/command is matched against the
 * built-in definitions as a fallback. Determinism comes from the
 * entry's own `deterministic` flag, which the gate sets on every
 * denial (policy, not model judgment).
 */
function itemFromAuditEntry(e, { commandText = '', rules = null } = {}) {
  if (!e || e.allowed) return null;
  if (e.event === 'WALL_START' || e.event === 'WALL_END') return null;

  const kind = e.action && e.action.kind;
  const target = (e.action && e.action.target) || '';
  const ruleId = e.rule || null;
  let family = ruleId ? definitions.ruleFamily(ruleId) : null;
  if (!family && rules) {
    if (kind === 'file_read' || kind === 'file_write') {
      const id = definitions.pathRuleId(rules, target);
      if (id) family = definitions.ruleFamily(id);
    }
    if (!family && commandText) {
      const id = definitions.commandRuleId(rules, commandText.split(/\s+/));
      if (id) family = definitions.ruleFamily(id);
    }
    if (!family && kind === 'command') {
      for (const tok of target.split(/\s+/)) {
        const id = definitions.pathRuleId(rules, tok);
        if (id) { family = definitions.ruleFamily(id); break; }
      }
    }
  }
  const ruleName = family ? family.name : null;
  const catalogue = family ? (family.catalogue || []) : [];
  const deterministic = e.deterministic === true || !!family;
  const title = e.event === 'WALL_PROXY_DENY'
    ? `Blocked on the internet: ${target}`
    : `Blocked: the agent ${whatHappened(e)}.`;
  return {
    id: newId(),
    ts: new Date().toISOString(),
    kind: 'blocked',
    title,
    detail: e.reason || 'Outside the allowed scope.',
    rule: ruleName,
    ruleId: ruleId || null,
    rulePlain: family ? (family.plain || '') : '',
    catalogue,
    deterministic,
    determinismLine: deterministic ? DETERMINISM_LINE : '',
    source: 'wall',
  };
}

/** A `fineprint check` result -> one feed item. */
function itemFromCheckResult({ code, bundle, bundlePath }) {
  const verdict = code === 0 ? 'pass' : code === 2 ? 'blocked' : 'unknown';
  const notSatisfied = bundle && Array.isArray(bundle.invariant_results)
    ? bundle.invariant_results.filter((r) => r.intent_coverage === 'NOT_SATISFIED').length
    : 0;
  const unknown = bundle && Array.isArray(bundle.invariant_results)
    ? bundle.invariant_results.filter((r) => r.intent_coverage === 'UNKNOWN').length
    : 0;
  const title = verdict === 'pass'
    ? 'Check passed: your setup held the line.'
    : verdict === 'blocked'
      ? `Check found ${notSatisfied} rule${notSatisfied === 1 ? '' : 's'} the setup does not hold.`
      : `Check could not decide (${unknown} unknown${unknown === 1 ? '' : 's'}).`;
  return {
    id: newId(),
    ts: new Date().toISOString(),
    kind: verdict === 'pass' ? 'check-pass' : verdict === 'blocked' ? 'check-blocked' : 'check-unknown',
    title,
    detail: bundlePath ? `Evidence bundle: ${bundlePath}` : '',
    rule: null,
    rulePlain: '',
    catalogue: [],
    deterministic: false,
    determinismLine: '',
    source: 'check',
  };
}

/** A guarded run's overall verdict -> one summary feed item. */
function itemFromGuardedRun({ code, command, blockedCount }) {
  const cmd = Array.isArray(command) ? command.join(' ') : String(command || '');
  if (code === 2) {
    return {
      id: newId(),
      ts: new Date().toISOString(),
      kind: 'blocked',
      title: `Stopped the agent before it ran: ${cmd}`,
      detail: blockedCount
        ? `${blockedCount} blocked attempt${blockedCount === 1 ? '' : 's'} in the audit log.`
        : 'The wall refused the command before it ran.',
      rule: null,
      rulePlain: '',
      catalogue: [],
      deterministic: true,
      determinismLine: DETERMINISM_LINE,
      source: 'wall',
    };
  }
  return null; // clean runs do not clutter the feed
}

class FeedStore {
  constructor(filePath) {
    this.filePath = filePath;
    this.items = [];
    if (filePath && fs.existsSync(filePath)) {
      try {
        const doc = JSON.parse(fs.readFileSync(filePath, 'utf8'));
        if (Array.isArray(doc.items)) this.items = doc.items;
      } catch { this.items = []; }
    }
  }

  append(item) {
    if (!item) return null;
    this.items.push(item);
    this.save();
    return item;
  }

  appendMany(items) {
    const added = [];
    for (const it of items || []) if (it) { this.items.push(it); added.push(it); }
    if (added.length) this.save();
    return added;
  }

  list() {
    return [...this.items].sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
  }

  clear() {
    this.items = [];
    this.save();
  }

  save() {
    if (!this.filePath) return;
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    fs.writeFileSync(this.filePath, JSON.stringify({ items: this.items }, null, 2) + '\n', 'utf8');
  }
}

module.exports = {
  DETERMINISM_LINE,
  whatHappened,
  itemFromAuditEntry,
  itemFromCheckResult,
  itemFromGuardedRun,
  FeedStore,
};
