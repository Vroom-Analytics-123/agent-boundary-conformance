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
 * feed items on their own — the run's verdict summarises them. The
 * one exception is a second-opinion allow: the model letting an
 * action through is itself a reviewable verdict (the false-negative
 * candidates), so it is a feed item of its own kind.
 *
 * Determinism: a denial is deterministic — the same action is denied
 * every time. The gate marks every denial `deterministic: true` in the
 * log, and blocked items carry that line; it is the antivirus promise
 * ("this will always be blocked"). A second-opinion verdict is the
 * opposite: probabilistic, `deterministic: false`, labelled
 * "second opinion — probabilistic" with the model name + version +
 * the model's reason — never with the determinism line, and never
 * with a "Stopped by" rule name (S1-BLOCK-bekko / S1-MODEL-ERROR
 * are synthetic ids for a model judgment / a fail-closed refusal,
 * not rules that matched).
 */
const fs = require('fs');
const path = require('path');
const definitions = require('./definitions');

const DETERMINISM_LINE = 'This will always be blocked — the same action is denied every time.';

/**
 * The second opinion (Nov 8, two-stage gate — see tools/fineprint_gate.py
 * in the free-check-gate / free-wall branches and the design doc §10/§12):
 * a small model (bekko-system-one-v0-400m) judges actions Stage 1
 * allowed. Its verdicts are PROBABILISTIC, never deterministic
 * denials, and the audit log says so: `second_opinion: true`,
 * `deterministic: false`, the synthetic rule id S1-BLOCK-bekko (model
 * block) or S1-MODEL-ERROR (model error — blocked fail-closed), the
 * model name + version, the invariant family, the reason the model
 * saw (`reason_seen`), the model's verdict + reason verbatim
 * (`model_verdict`, `model_reason`), and the latency (`latency_s`).
 * A model allow carries the same fields with `allowed: true` and no
 * rule id — it is a feed item of its own kind (the false-negative
 * candidates for review), not invisible.
 */
const SECOND_OPINION_LABEL = 'second opinion — probabilistic';
const S1_BLOCK_RULE = 'S1-BLOCK-bekko';
const S1_MODEL_ERROR_RULE = 'S1-MODEL-ERROR';

/** True when this log entry is a second-opinion verdict. Keyed off the
 * gate's own `second_opinion` flag first; the synthetic rule id is
 * the fallback for a log that carries the id without the flag. */
function isSecondOpinionEntry(e) {
  if (!e) return false;
  if (e.second_opinion === true) return true;
  return e.rule === S1_BLOCK_RULE || e.rule === S1_MODEL_ERROR_RULE;
}

/** The line the renderer shows for a second-opinion item: the label,
 * the model name + version, the invariant at stake, and what the
 * verdict means (fail-closed for a model error, false-negative
 * candidate for a model allow). */
function secondOpinionLine(e, verdict) {
  const model = e.model || 'unknown model';
  const version = e.model_version ? ` ${e.model_version}` : '';
  const invariant = e.invariant ? ` · invariant: ${e.invariant}` : '';
  if (verdict === 'error') {
    return `${SECOND_OPINION_LABEL} · ${model}${version}${invariant} · blocked fail-closed: the model could not be consulted`;
  }
  if (verdict === 'allow') {
    return `${SECOND_OPINION_LABEL} · ${model}${version}${invariant} · the model let this through — a false-negative candidate for review`;
  }
  return `${SECOND_OPINION_LABEL} · ${model}${version}${invariant}`;
}

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
  // The gate logs second-opinion actions (and pre-flight command
  // checks) with kind 'exec' — same wording as 'command'.
  if (kind === 'exec') return `tried to run ${target}`;
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
  if (!e) return null;
  if (e.event === 'WALL_START' || e.event === 'WALL_END') return null;

  // A second-opinion verdict renders distinctly — model name +
  // version + reason + the probabilistic label — and NEVER as a
  // deterministic rule denial (no rule name, no determinism line).
  // This branch runs BEFORE the allowed-entries filter below: a
  // model allow is a feed item of its own kind (the false-negative
  // candidates), while a plain Stage 1 allow stays invisible.
  if (isSecondOpinionEntry(e)) {
    const isError = e.model_error === true || e.rule === S1_MODEL_ERROR_RULE;
    const verdict = isError ? 'error' : (e.allowed === true ? 'allow' : 'block');
    const kind = verdict === 'error' ? 'second-opinion-error'
      : verdict === 'allow' ? 'second-opinion-allow' : 'second-opinion-block';
    // The model's reason verbatim; a model error has no model_reason,
    // so the error text is the reason, then the gate's wrapped reason.
    const modelReason = e.model_reason || e.error || e.reason || '';
    const title = verdict === 'error'
      ? `Blocked fail-closed (second opinion failed): the agent ${whatHappened(e)}.`
      : verdict === 'allow'
        ? `Second opinion allowed: the agent ${whatHappened(e)}.`
        : `Second opinion blocked: the agent ${whatHappened(e)}.`;
    return {
      id: newId(),
      ts: new Date().toISOString(),
      kind,
      title,
      detail: modelReason,
      // NOT a rule denial: the rule name stays null, so the renderer
      // never shows a "Stopped by" line for it. ruleId keeps the
      // synthetic id the gate logged (S1-BLOCK-bekko /
      // S1-MODEL-ERROR, null on an allow) for traceability only.
      rule: null,
      ruleId: e.rule || null,
      rulePlain: '',
      catalogue: [],
      deterministic: false,
      determinismLine: '',
      secondOpinion: true,
      secondOpinionLabel: SECOND_OPINION_LABEL,
      secondOpinionLine: secondOpinionLine(e, verdict),
      model: e.model || 'unknown model',
      modelVersion: e.model_version || '',
      modelVerdict: verdict,
      modelReason,
      invariant: e.invariant || null,
      latencyS: typeof e.latency_s === 'number' ? e.latency_s : null,
      source: 'wall',
      agent: agent || null,
    };
  }

  if (e.allowed) return null;

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

/** A guarded run's overall verdict -> one summary feed item.
 * `blockedCount` is deterministic blocks; `secondOpinionBlocked`
 * counts second-opinion blocks + fail-closed errors. A run stopped
 * only by the second opinion gets a second-opinion summary — never
 * a deterministic one (the determinism line would be a lie about a
 * probabilistic verdict). */
function itemFromGuardedRun({ code, command, blockedCount, secondOpinionBlocked = 0, agent = null }) {
  const cmd = Array.isArray(command) ? command.join(' ') : String(command || '');
  if (code === 2) {
    if (!blockedCount && secondOpinionBlocked) {
      return {
        id: newId(),
        ts: new Date().toISOString(),
        kind: 'second-opinion-block',
        title: `Stopped the agent before it ran: ${cmd}`,
        detail: `${secondOpinionBlocked} second-opinion block${secondOpinionBlocked === 1 ? '' : 's'} in the audit log (probabilistic — not a rule denial).`,
        rule: null,
        ruleId: null,
        rulePlain: '',
        catalogue: [],
        deterministic: false,
        determinismLine: '',
        secondOpinion: true,
        secondOpinionLabel: SECOND_OPINION_LABEL,
        secondOpinionLine: `${SECOND_OPINION_LABEL} · the run was stopped by the second opinion, not by a rule.`,
        model: '',
        modelVersion: '',
        modelVerdict: 'block',
        modelReason: '',
        invariant: null,
        latencyS: null,
        source: 'wall',
        agent: agent || null,
      };
    }
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
 * already in the feed, not new measurement. Only deterministic
 * `blocked` items count in `blocked` / `byRule` / `byAgent`; the
 * second opinion is a separate layer and is counted separately in
 * `secondOpinion` (blocks, fail-closed errors, allows), so the two
 * layers are never conflated in the counts. Check results and run
 * summaries are not blocked attempts (a run summary has no rule, so
 * it would only dilute the view).
 */
function summarizeFeed(items) {
  const list = Array.isArray(items) ? items : [];
  let blocked = 0;
  const secondOpinion = { total: 0, blocked: 0, errors: 0, allowed: 0 };
  const byRule = new Map();
  const byAgent = new Map();
  for (const it of list) {
    if (!it) continue;
    if (it.kind === 'second-opinion-block' || it.kind === 'second-opinion-error'
      || it.kind === 'second-opinion-allow') {
      secondOpinion.total += 1;
      if (it.kind === 'second-opinion-block') secondOpinion.blocked += 1;
      else if (it.kind === 'second-opinion-error') secondOpinion.errors += 1;
      else secondOpinion.allowed += 1;
      continue;
    }
    if (it.kind !== 'blocked') continue;
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
  return { total: list.length, blocked, secondOpinion, byRule: byRuleList, byAgent: byAgentList };
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
  SECOND_OPINION_LABEL,
  S1_BLOCK_RULE,
  S1_MODEL_ERROR_RULE,
  isSecondOpinionEntry,
  whatHappened,
  itemFromAuditEntry,
  itemFromCheckResult,
  itemFromGuardedRun,
  summarizeFeed,
  FeedStore,
};
