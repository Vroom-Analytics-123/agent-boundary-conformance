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
function itemFromAuditEntry(e, { commandText = '', rules = null, agent = null } = {}) {
  if (!e || e.allowed) return null;
  if (e.event === 'WALL_START' || e.event === 'WALL_END') return null;

  // A canary verdict is the objective-level outcome: a FAILED canary
  // (the marker reached the agent through some route) is the boundary
  // failing, no matter how many attempts were denied. It reads as
  // that in the feed. A HELD canary is not feed-worthy.
  if (e.event === 'CANARY') {
    const routes = e.routes || [];
    const reached = e.reached === true || e.allowed === false;
    if (!reached) return null;
    const via = routes.length ? ` via ${routes.join(', ')}` : '';
    return {
      id: newId(),
      ts: new Date().toISOString(),
      kind: 'blocked',
      title: `Boundary failed: the canary marker reached the agent${via}.`,
      detail: `The canary marker reached the agent${via} — the boundary failed, no matter how many attempts were denied.`,
      rule: null,
      ruleId: null,
      rulePlain: '',
      catalogue: [],
      deterministic: true,
      determinismLine: DETERMINISM_LINE,
      source: 'wall',
      agent: agent || null,
    };
  }

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
    agent: agent || null,
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
    agent: null,
  };
}

/** A guarded run's overall verdict -> one summary feed item. */
function itemFromGuardedRun({ code, command, blockedCount, agent = null }) {
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
      agent: agent || null,
    };
  }
  return null; // clean runs do not clutter the feed
}

/**
 * Boundaries under test (Nov 8): the feed aggregates. Which rules
 * fire most, which agents keep testing them — a view on the items
 * already in the feed, not new measurement. Only `blocked` items
 * count; check results and run summaries are not blocked attempts
 * (a run summary has no rule, so it would only dilute the view).
 * byAgent counts items that carry an `agent` (runs the app itself
 * started); when no item carries one it is empty — the feed never
 * invents an agent.
 */
function summarizeFeed(items) {
  const list = Array.isArray(items) ? items : [];
  let blocked = 0;
  const byRule = new Map();
  const byAgent = new Map();
  for (const it of list) {
    if (!it || it.kind !== 'blocked') continue;
    blocked += 1;
    const key = it.ruleId || it.rule || 'unknown';
    const row = byRule.get(key) || {
      ruleId: it.ruleId || null, rule: it.rule || null, count: 0,
    };
    row.count += 1;
    byRule.set(key, row);
    if (it.agent) byAgent.set(it.agent, (byAgent.get(it.agent) || 0) + 1);
  }
  const byRuleList = [...byRule.values()].sort((a, b) =>
    b.count - a.count
    || String(a.ruleId || a.rule || '').localeCompare(String(b.ruleId || b.rule || '')));
  const byAgentList = [...byAgent.entries()]
    .map(([agent, count]) => ({ agent, count }))
    .sort((a, b) => b.count - a.count || a.agent.localeCompare(b.agent));
  return { total: list.length, blocked, byRule: byRuleList, byAgent: byAgentList };
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
  summarizeFeed,
  FeedStore,
};
