'use strict';
/**
 * Definitions: the antivirus-style signed rule packs that power the
 * wall's protective denylist default.
 *
 * THIS MODULE MIRRORS THE REAL CLI (tools/fineprint_definitions.py in
 * the free-check-gate / free-wall branches) — the CLI is the enforcer
 * and the source of truth; the app only displays, labels, and verifies
 * packs the same way. Do not invent rules here: the built-in v1 rules
 * below are copied verbatim from the sibling's module.
 *
 * Pack format (fineprint-definitions.json):
 *   { "version": "2026-11-07", "rules": [ ... ], "signature": "<b64>" }
 * The signature is Ed25519 over the canonical JSON (sorted keys, no
 * spaces — Python json.dumps with ", " / ": " separators, same as the
 * audit log) of {"version": ..., "rules": ...}, made with the
 * maintainers' key whose public half is published in docs/SIGNING.md
 * (the same key that signs the sealed evidence bundles).
 * The wall verifies the signature before applying a pack and NEVER
 * applies an unverified one. No pack file found -> the built-in v1
 * rules, version "2026-11-07", source "built-in".
 *
 * Update channel: a new pack ships with a FinePrint release (git pull
 * or a new release). There is no live network update check.
 *
 * Rules (v1, 11 rules): path rules use Python fnmatch globs on the
 * full resolved path ("*" matches "/" too); command rules match the
 * basename of argv[0] (exact or glob) and fire only when one of
 * "any_flag" appears as a whole argv token; host rules are exact.
 */
const crypto = require('crypto');
const fs = require('fs');
const { canonical } = require('./audit');

const BUILTIN_VERSION = '2026-11-07';
const DEFINITIONS_PUBLIC_KEY_HEX = '40004a96827ae90e5ad4ae36da1414aa80d83625818668604803ba60f3393326';

// Copied verbatim from tools/fineprint_definitions.py (BUILTIN_RULES).
const BUILTIN_RULES = [
  { id: 'DENY-CRED-SSH', kind: 'path', patterns: ['**/.ssh', '**/.ssh/**'], description: 'SSH private keys and config' },
  { id: 'DENY-CRED-AWS', kind: 'path', patterns: ['**/.aws', '**/.aws/**'], description: 'AWS credentials' },
  { id: 'DENY-CRED-ENV', kind: 'path', patterns: ['**/.env'], description: '.env files (secrets)' },
  { id: 'DENY-CRED-PEM', kind: 'path', patterns: ['**/*key*.pem', '**/*private*.pem'], description: 'PEM private keys (key-named files; public CA bundles such as cacert.pem are not matched)' },
  { id: 'DENY-CRED-KEY', kind: 'path', patterns: ['**/id_rsa*', '**/id_ed25519*'], description: 'SSH private key files' },
  { id: 'DENY-CRED-TOKEN', kind: 'path', patterns: ['**/.git-credentials'], description: 'stored git credentials' },
  { id: 'DENY-RECORDS', kind: 'path', patterns: ['**/records.txt', '**/records/health'], description: 'the protected records file (FP-016)' },
  { id: 'DENY-DELETE', kind: 'command', match: 'rm', match_kind: 'exact', any_flag: ['-r', '-f', '-rf', '-fr', '-R', '--recursive', '--force'], description: 'destructive delete (rm -r/-f)' },
  { id: 'DENY-SHRED', kind: 'command', match: 'shred', match_kind: 'exact', description: 'secure delete (shred)' },
  { id: 'DENY-UNLINK', kind: 'command', match: 'unlink', match_kind: 'exact', description: 'unlink — the bypass around the rm filter' },
  { id: 'DENY-DEPLOY', kind: 'command', match: '*deploy*', match_kind: 'glob', description: 'unapproved deploy (a command named *deploy*)' },
];

/** Rule id -> the plain-language family it belongs to (for the feed + Home). */
const RULE_FAMILIES = {
  'DENY-CRED-SSH': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-CRED-AWS': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-CRED-ENV': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-CRED-PEM': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-CRED-KEY': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-CRED-TOKEN': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-RECORDS': { familyId: 'credential-theft', name: 'Credential theft', plain: 'Stops the agent reading your keys, secrets, and protected records.', catalogue: ['FP-004', 'FP-003'] },
  'DENY-DELETE': { familyId: 'destructive-deletes', name: 'Destructive deletes', plain: 'Stops the agent deleting files the destructive way.', catalogue: ['FP-001'] },
  'DENY-SHRED': { familyId: 'destructive-deletes', name: 'Destructive deletes', plain: 'Stops the agent deleting files the destructive way.', catalogue: ['FP-001'] },
  'DENY-UNLINK': { familyId: 'destructive-deletes', name: 'Destructive deletes', plain: 'Stops the agent deleting files the destructive way.', catalogue: ['FP-001'] },
  'DENY-EXFIL': { familyId: 'exfiltration', name: 'Exfiltration', plain: 'Stops the agent copying or sending a protected file out.', catalogue: ['FP-004', 'FP-005'] },
  'DENY-DEPLOY': { familyId: 'unapproved-deploys', name: 'Unapproved deploys', plain: 'Stops the agent shipping to production without approval.', catalogue: ['FP-002'] },
  'DENY-PATH': { familyId: 'own-deny-list', name: 'Your own deny list', plain: 'Stopped by a path you added to the deny list.', catalogue: [] },
  'DENY-HOST': { familyId: 'own-deny-list', name: 'Your own deny list', plain: 'Stopped by a host you added to the deny list.', catalogue: [] },
  'CONFINE-PATH': { familyId: 'confinement', name: 'Folder confinement', plain: 'Stopped because the agent is confined to its folders.', catalogue: [] },
  'CONFINE-HOST': { familyId: 'confinement', name: 'Folder confinement', plain: 'Stopped because the agent is confined to its folders.', catalogue: [] },
};

const FAMILY_ORDER = ['credential-theft', 'destructive-deletes', 'exfiltration', 'unapproved-deploys'];

function ruleFamily(ruleId) {
  return RULE_FAMILIES[ruleId] || null;
}

function familiesInForce(rules) {
  const ids = new Set();
  for (const r of rules || []) {
    const f = ruleFamily(r.id);
    if (f) ids.add(f.familyId);
  }
  // DENY-EXFIL is produced by the gate (copy/send of a protected file),
  // not listed as a rule — it belongs to the exfiltration family.
  ids.add('exfiltration');
  return FAMILY_ORDER.filter((id) => ids.has(id));
}

function familyName(familyId) {
  for (const f of Object.values(RULE_FAMILIES)) if (f.familyId === familyId) return f.name;
  return familyId;
}

/** The protection line shown on the home screen and the Wall screen. */
function protectionLine(version, familyIds) {
  const ids = familyIds || familiesInForce(BUILTIN_RULES);
  const names = ids.map((id) => familyName(id).toLowerCase());
  if (!names.length) return 'Definitions protection is off — no rule families are in force.';
  return `Protected by FinePrint definitions v${version} — ${names.join(', ')} blocked.`;
}

/** Python fnmatch -> RegExp. "*" matches "/" too (unlike shell globs). */
function fnmatchToRegExp(pattern) {
  let re = '';
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i];
    if (c === '*') re += '.*';
    else if (c === '?') re += '.';
    else if (c === '[') {
      let j = i + 1;
      if (j < pattern.length && pattern[j] === '!') j++;
      if (j < pattern.length && pattern[j] === ']') j++;
      while (j < pattern.length && pattern[j] !== ']') j++;
      if (j >= pattern.length) { re += '\\['; }
      else {
        let stuff = pattern.slice(i + 1, j);
        if (stuff.startsWith('!')) stuff = `^${stuff.slice(1)}`;
        re += `[${stuff.replace(/\\/g, '\\\\')}]`;
        i = j;
      }
    } else re += c.replace(/[.+^${}()|\\]/g, '\\$&');
  }
  return new RegExp(`^${re}$`);
}

function fnmatch(pattern, s) {
  return fnmatchToRegExp(pattern).test(s);
}

/** First path-rule id matching this resolved path, else null. */
function pathRuleId(rules, target) {
  for (const rule of rules || []) {
    if (rule.kind !== 'path') continue;
    for (const pattern of rule.patterns || []) {
      if (fnmatch(pattern, target)) return rule.id;
    }
  }
  return null;
}

/** First command-rule id matching argv, else null. */
function commandRuleId(rules, argv) {
  if (!argv || !argv.length) return null;
  const base = argv[0].split('/').pop();
  const flags = new Set(argv.slice(1));
  for (const rule of rules || []) {
    if (rule.kind !== 'command') continue;
    const hit = rule.match_kind === 'glob' ? fnmatch(rule.match, base) : base === rule.match;
    if (!hit) continue;
    if (rule.any_flag && !rule.any_flag.some((f) => flags.has(f))) continue;
    return rule.id;
  }
  return null;
}

/** First host-rule id matching this host, else null. */
function hostRuleId(rules, host) {
  const h = String(host || '').toLowerCase();
  for (const rule of rules || []) {
    if (rule.kind !== 'host') continue;
    if (h === String(rule.match || '').toLowerCase()) return rule.id;
  }
  return null;
}

function loadPack(filePath) {
  const pack = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  if (!pack || typeof pack !== 'object' || Array.isArray(pack)) {
    throw new Error(`${filePath}: definitions pack must be a JSON object`);
  }
  if (typeof pack.version !== 'string' || !Array.isArray(pack.rules)) {
    throw new Error(`${filePath}: definitions pack needs a version string and a rules array`);
  }
  return pack;
}

/** Verify a pack's Ed25519 signature against the maintainers' public key.
 * The published key is the raw 32 bytes; SPKI DER wraps it with the
 * Ed25519 prefix 302a300506032b6570032100. */
function verifyPack(pack, publicKeyHex = DEFINITIONS_PUBLIC_KEY_HEX) {
  if (!pack.signature) {
    return { valid: false, reason: 'Pack is not signed (no signature).' };
  }
  let pub;
  try {
    const spki = Buffer.concat([
      Buffer.from('302a300506032b6570032100', 'hex'),
      Buffer.from(publicKeyHex, 'hex'),
    ]);
    pub = crypto.createPublicKey({ key: spki, format: 'der', type: 'spki' });
  } catch {
    return { valid: false, reason: 'The maintainers public key is not a valid Ed25519 key.' };
  }
  let ok = false;
  try {
    ok = crypto.verify(
      null,
      Buffer.from(canonical({ version: pack.version, rules: pack.rules })),
      pub,
      Buffer.from(pack.signature, 'base64'),
    );
  } catch {
    ok = false;
  }
  return ok
    ? { valid: true, reason: '' }
    : { valid: false, reason: 'Signature does not match the pack contents — the pack was changed after signing.' };
}

/** Parse `fineprint gate definitions` output. */
function parseDefinitionsOutput(text) {
  const m = String(text || '').match(/^definitions:\s*v(\S+)\s*\(([^)]+)\)/m);
  if (!m) return null;
  const rules = String(text).match(/^rules:\s*(\d+)/m);
  return { version: m[1], source: m[2], ruleCount: rules ? parseInt(rules[1], 10) : null };
}

/**
 * Update check. There is no live network update check by design — a
 * new pack ships with a FinePrint release. This compares the version
 * in force (from `gate definitions`) with the version this app was
 * built against and reports the difference.
 */
function checkForUpdates({ currentVersion, inForceVersion }) {
  if (!inForceVersion) {
    return {
      status: 'no-source',
      currentVersion,
      latestVersion: null,
      note: 'Could not ask the CLI which definitions are in force — the bundled rules are the ones this app knows about.',
    };
  }
  if (inForceVersion === currentVersion) {
    return { status: 'up-to-date', currentVersion, latestVersion: inForceVersion, note: `Definitions v${inForceVersion} are the latest.` };
  }
  return {
    status: 'update-available',
    currentVersion,
    latestVersion: inForceVersion,
    note: `The CLI is using definitions v${inForceVersion} (this app was built against v${currentVersion}). Update the app to match.`,
  };
}

function summarizeRules(rules) {
  return (rules || []).map((r) => ({
    id: r.id,
    kind: r.kind,
    description: r.description || '',
    family: ruleFamily(r.id),
  }));
}

module.exports = {
  BUILTIN_VERSION,
  BUILTIN_RULES,
  DEFINITIONS_PUBLIC_KEY_HEX,
  RULE_FAMILIES,
  FAMILY_ORDER,
  ruleFamily,
  familiesInForce,
  familyName,
  protectionLine,
  fnmatch,
  fnmatchToRegExp,
  pathRuleId,
  commandRuleId,
  hostRuleId,
  loadPack,
  verifyPack,
  parseDefinitionsOutput,
  checkForUpdates,
  summarizeRules,
};
