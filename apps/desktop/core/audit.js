'use strict';
/**
 * Audit log: the gate/wall's hash-chained JSONL log.
 *
 * Entry shape (from tools/fineprint_gate.py / fineprint_wall.py):
 *   {"action": {"kind": "...", "target": "..."}, "allowed": bool,
 *    "reason": "...", "note": "...", "prev_hash": "<hex>",
 *    "hash": "<hex>", "event": "WALL_START"|"WALL_END"|"WALL_PROXY_DENY"|...,
 *    "extra": {...}}
 * The chain: entry.hash = sha256(canonical-json(entry without "hash")).
 * Any edit to an earlier entry breaks verification of everything after.
 * This module parses the log, verifies the chain, and renders entries
 * in plain language. It never writes the log — the CLI owns that.
 */
const crypto = require('crypto');
const fs = require('fs');

const ZERO_HASH = '0'.repeat(64);

/**
 * Canonical JSON exactly as Python's json.dumps(obj, sort_keys=True):
 * sorted keys, ", " and ": " separators, non-ASCII escaped as \uXXXX
 * (ensure_ascii). The real gate hashes THIS form — the compact form
 * (no spaces) hashes differently, so a real log would verify as
 * BROKEN under it. Verified against a real gate log entry, 2026-11-07:
 * entry hash c2651ed7… matches the spaced form, not the compact one.
 */
function pyString(s) {
  const j = JSON.stringify(s);
  return j.replace(/[\u0080-\uFFFF]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
}

function canonical(value) {
  if (value === null) return 'null';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'string') return pyString(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(', ')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => `${pyString(k)}: ${canonical(value[k])}`).join(', ')}}`;
}

function entryHash(entry) {
  const { hash, ...rest } = entry; // eslint-disable-line no-unused-vars
  return crypto.createHash('sha256').update(canonical(rest)).digest('hex');
}

function parseLog(text) {
  const entries = [];
  for (const line of String(text).split('\n')) {
    if (!line.trim()) continue;
    entries.push(JSON.parse(line));
  }
  return entries;
}

function parseLogFile(filePath) {
  return parseLog(fs.readFileSync(filePath, 'utf8'));
}

/** True when the chain is intact; returns {valid, brokenAt} instead of throwing. */
function verifyChain(entries) {
  let prev = ZERO_HASH;
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e.prev_hash !== prev) return { valid: false, brokenAt: i };
    if (entryHash(e) !== e.hash) return { valid: false, brokenAt: i };
    prev = e.hash;
  }
  return { valid: true, brokenAt: -1 };
}

/** One entry in plain language, for the Wall screen's log view. */
function describeEntry(e) {
  const kind = e.action && e.action.kind;
  const target = e.action && e.action.target;
  const reason = e.reason || '';
  if (e.event === 'WALL_START') {
    const mode = e.mode || (e.extra && e.extra.mode) || '?';
    const defs = e.definitions || (e.extra && e.extra.definitions) || '?';
    const hidden = e.hidden_paths || (e.extra && e.extra.hidden_paths) || [];
    return `Wall started — ${mode} mode, definitions ${defs}, ${hidden.length} hidden targets.`;
  }
  if (e.event === 'WALL_END') {
    // The wall writes exit_code as a top-level field (extra is merged
    // into the entry); older entries may carry it under extra.
    const code = typeof e.exit_code === 'number' ? e.exit_code
      : (e.extra && typeof e.extra.exit_code === 'number' ? e.extra.exit_code : null);
    return code === 0
      ? 'Wall stopped — the command finished cleanly.'
      : `Wall stopped — the command ended with exit code ${code === null ? '?' : code}.`;
  }
  if (e.event === 'WALL_PROXY_DENY') {
    const rule = e.rule ? ` (rule ${e.rule})` : '';
    return `Blocked on the internet: ${target} is not allowed${rule}. This will always be blocked.`;
  }
  if (kind === 'wall') return reason || 'Wall event.';
  const what = kind === 'file_read' ? `tried to read ${target}`
    : kind === 'file_write' ? `tried to write ${target}`
    : kind === 'network' ? `tried to reach ${target}`
    : kind === 'exec' ? `tried to run ${target}`
    : `tried ${kind || 'something'} ${target || ''}`;
  if (e.allowed) return `Allowed: ${what}.`;
  const rule = e.rule ? ` Stopped by rule ${e.rule}.` : '';
  const det = e.deterministic ? ' This will always be blocked.' : '';
  return `Blocked: ${what} — ${reason || 'outside the allowed scope.'}${rule}${det}`;
}

module.exports = {
  ZERO_HASH,
  canonical,
  entryHash,
  parseLog,
  parseLogFile,
  verifyChain,
  describeEntry,
};
