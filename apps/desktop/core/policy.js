'use strict';
/**
 * Policy: the free gate/wall policy file (fineprint-gate.json).
 *
 * THIS MODULE MIRRORS THE REAL CLI (tools/fineprint_gate.py Policy) —
 * the CLI is the enforcer and the source of truth. The app writes
 * policies the CLI reads, so the shape must match exactly:
 *   { "$comment": "...", "mode": "deny" | "confine",
 *     "denied_paths": [fnmatch...], "denied_hosts": [host...],
 *     "allowed_commands": [basename-or-glob...],
 *     "allowed_paths": [folder...], "allowed_hosts": [host...] }
 * Two modes (Nov 7: antivirus-for-agents):
 *   "deny" (the default) — protective denylist. Anything the signed
 *     definitions name is denied, everything else is allowed. The
 *     policy's denied_paths / denied_hosts add your own blocks;
 *     allowed_commands overrides the denylist for one command
 *     (e.g. your deploy script).
 *   "confine" (opt-in) — folder allowlist. Anything outside the
 *     allowed paths/hosts is denied, on top of the denylist.
 * "." means the folder the policy file lives in. This module never
 * talks to the CLI — it only reads/writes/validates the JSON and
 * renders it in plain language.
 */
const fs = require('fs');
const path = require('path');

const POLICY_FILENAME = 'fineprint-gate.json';

const POLICY_COMMENT = 'Free gate policy. mode \'deny\' is the protective '
  + 'denylist (antivirus for agents): credential reads, destructive '
  + 'deletes, exfiltration of protected files, unapproved deploys, and '
  + 'the measured bypasses are blocked; normal work anywhere is allowed. '
  + 'mode \'confine\' is the folder allowlist (opt-in): only allowed_paths '
  + '/ allowed_hosts are allowed. denied_paths / denied_hosts add your own '
  + 'blocks; allowed_commands overrides the denylist for one command '
  + '(e.g. your deploy script).';

/** The default policy: definitions denylist, NOT folder confinement. */
function defaultPolicy(dir) {
  return {
    $comment: POLICY_COMMENT,
    mode: 'deny',
    denied_paths: [],
    denied_hosts: [],
    allowed_commands: [],
    allowed_paths: [dir],
    allowed_hosts: [],
  };
}

/** Resolve a policy path entry against the policy file's directory. */
function resolveEntry(entry, baseDir) {
  if (!entry) return entry;
  if (entry === '.') return path.resolve(baseDir);
  return path.isAbsolute(entry) ? path.normalize(entry)
    : path.resolve(baseDir, entry);
}

function loadPolicy(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');
  const doc = JSON.parse(raw);
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) {
    throw new Error(`${filePath}: policy must be a JSON object`);
  }
  const baseDir = path.dirname(path.resolve(filePath));
  const mode = doc.mode === 'confine' ? 'confine' : 'deny';
  return {
    $comment: typeof doc.$comment === 'string' ? doc.$comment : '',
    mode,
    denied_paths: (doc.denied_paths || []).map((p) => String(p)),
    denied_hosts: (doc.denied_hosts || []).map((h) => String(h)),
    allowed_commands: (doc.allowed_commands || []).map((c) => String(c)),
    allowed_paths: (doc.allowed_paths || []).map((p) => String(p)),
    allowed_hosts: (doc.allowed_hosts || []).map((h) => String(h)),
    _file: path.resolve(filePath),
    _dir: baseDir,
  };
}

function savePolicy(filePath, policy) {
  const doc = {
    $comment: policy.$comment || POLICY_COMMENT,
    mode: policy.mode === 'confine' ? 'confine' : 'deny',
    denied_paths: policy.denied_paths || [],
    denied_hosts: policy.denied_hosts || [],
    allowed_commands: policy.allowed_commands || [],
    allowed_paths: policy.allowed_paths || [],
    allowed_hosts: policy.allowed_hosts || [],
  };
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(doc, null, 2) + '\n', 'utf8');
  return loadPolicy(filePath);
}

/** Problems with a policy, in plain words. Empty list = usable. */
function validatePolicy(policy, baseDir) {
  const problems = [];
  const confine = policy.mode === 'confine';
  if (confine) {
    const paths = policy.allowed_paths || [];
    if (paths.length === 0) {
      problems.push('No folders are allowed — the wall would block everything. '
        + 'Add at least one folder.');
    }
    for (const p of paths) {
      const full = resolveEntry(p, baseDir || process.cwd());
      if (!fs.existsSync(full)) {
        problems.push(`Folder does not exist: ${p}`);
      } else if (!fs.statSync(full).isDirectory()) {
        problems.push(`Not a folder: ${p}`);
      }
    }
  }
  for (const h of policy.allowed_hosts || []) {
    if (!/^[A-Za-z0-9.-]+(:[0-9]+)?$/.test(h) || h.includes('..')) {
      problems.push(`Not a valid host name: ${h}`);
    }
  }
  for (const h of policy.denied_hosts || []) {
    if (!/^[A-Za-z0-9.-]+(:[0-9]+)?$/.test(h) || h.includes('..')) {
      problems.push(`Not a valid denied host name: ${h}`);
    }
  }
  for (const p of policy.denied_paths || []) {
    if (!p || typeof p !== 'string') problems.push('A denied path is empty.');
  }
  return problems;
}

/** The policy in plain language, for the Wall screen and Settings. */
function describePolicy(policy, baseDir) {
  const dir = baseDir || policy._dir || process.cwd();
  const confine = policy.mode === 'confine';
  const folders = (policy.allowed_paths || [])
    .map((p) => resolveEntry(p, dir));
  const hosts = policy.allowed_hosts || [];
  const deniedPaths = policy.denied_paths || [];
  const deniedHosts = policy.denied_hosts || [];
  const allowedCommands = policy.allowed_commands || [];
  return {
    mode: confine ? 'confined' : 'definitions',
    confine,
    folders,
    hosts,
    deniedPaths,
    deniedHosts,
    allowedCommands,
    foldersLine: confine
      ? (folders.length
        ? `Confined to these folders: ${folders.join(', ')}.`
        : 'Confined to no folders.')
      : 'Not confined to folders — the agent can work anywhere except what the definitions block.',
    hostsLine: hosts.length
      ? `Can reach on the internet: ${hosts.join(', ')}.`
      : (confine ? 'Can reach nothing on the internet.' : 'Internet is open except what the definitions block.'),
    deniedLine: deniedPaths.length + deniedHosts.length
      ? `Your own deny list: ${deniedPaths.length} paths, ${deniedHosts.length} hosts.`
      : 'Your own deny list is empty.',
    allowedCommandsLine: allowedCommands.length
      ? `Always allowed (overrides the denylist): ${allowedCommands.join(', ')}.`
      : '',
  };
}

module.exports = {
  POLICY_FILENAME,
  POLICY_COMMENT,
  defaultPolicy,
  loadPolicy,
  savePolicy,
  validatePolicy,
  describePolicy,
  resolveEntry,
};
