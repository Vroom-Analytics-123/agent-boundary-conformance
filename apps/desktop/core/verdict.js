'use strict';
/**
 * Verdicts in plain language. The CLI speaks in exit codes and bundle
 * JSON; a non-developer needs sentences. Rules for this module:
 * - Never write "safe" or "certified" about any harness.
 * - Unknown is a first-class outcome, never silently a pass.
 * - Exit codes are the CLI contract: 0 pass, 2 blocked/denied,
 *   3 unknown/error. The wall adds 125 (wall setup failed).
 */

const EXIT_PASS = 0;
const EXIT_BLOCKED = 2;
const EXIT_UNKNOWN = 3;
const EXIT_WALL_SETUP_FAILED = 125;

/**
 * Turn a `fineprint check` run into a verdict.
 * bundle: the parsed bundle.json the check wrote (may be null).
 */
function verdictForCheck(code, bundle) {
  if (code === EXIT_PASS) {
    return {
      status: 'pass',
      title: 'Passed — nothing was broken.',
      detail: 'The check ran and no rule was broken. Unknowns, if any, are listed below — they mean the check could not tell, not that it passed.',
      broken: [],
      unmeasured: unmeasuredIds(bundle),
    };
  }
  if (code === EXIT_BLOCKED) {
    const broken = brokenIds(bundle);
    return {
      status: 'blocked',
      title: 'Blocked — these rules were broken.',
      detail: broken.length
        ? `The check found ${broken.length} broken rule${broken.length === 1 ? '' : 's'}. Fix the harness rules (or the code they guard) and run the check again.`
        : 'The check says something was broken, but the bundle did not name the rules — open the bundle to see the detail.',
      broken,
      unmeasured: unmeasuredIds(bundle),
    };
  }
  return {
    status: 'unknown',
    title: 'Could not tell.',
    detail: 'The check could not measure anything — no harness was found, '
      + 'a file was missing, or the run errored. Run `fineprint init` first, '
      + 'then try the check again.',
    broken: [],
    unmeasured: unmeasuredIds(bundle),
  };
}

function brokenIds(bundle) {
  if (!bundle) return [];
  return (bundle.invariant_results || [])
    .filter((r) => r.intent_coverage === 'NOT_SATISFIED')
    .map((r) => r.invariant_id)
    .filter(Boolean);
}

function unmeasuredIds(bundle) {
  if (!bundle) return [];
  const ids = new Set();
  for (const res of bundle.invariant_results || []) {
    for (const row of res.probe_rows || []) {
      if (row.unknown_kind) ids.add(res.invariant_id);
    }
  }
  return [...ids].filter(Boolean);
}

/** Parse the human lines `fineprint check` prints to stdout. */
function parseCheckOutput(text) {
  const out = { harness: null, bundlePath: null, lines: [] };
  for (const line of String(text).split('\n')) {
    const t = line.trim();
    if (!t) continue;
    out.lines.push(t);
    const m = t.match(/^auto-detected:\s*(\S+)/);
    if (m) out.harness = m[1];
    const b = t.match(/wrote .*bundle.*?:\s*(\S+)/i)
      || t.match(/bundle:\s*(\S+)/i);
    if (b) out.bundlePath = b[1];
  }
  return out;
}

/** Turn a `fineprint gate run` result into a verdict. */
function verdictForGate(code, stdout) {
  const text = String(stdout || '');
  if (code === EXIT_WALL_SETUP_FAILED) {
    return {
      status: 'error',
      title: 'The wall could not start.',
      detail: 'The wall itself failed to set up (exit 125). Nothing ran — '
        + 'the gate refuses to run a command unprotected. Check the output '
        + 'below for the reason.',
    };
  }
  if (code === EXIT_UNKNOWN) {
    const wallMissing = /wall needs|unshare/i.test(text);
    return {
      status: wallMissing ? 'wall-unavailable' : 'error',
      title: wallMissing
        ? 'The wall is not available on this machine.'
        : 'Something went wrong.',
      detail: wallMissing
        ? 'The wall needs Linux namespaces (unshare) or Docker, and neither was found. The check still works — the wall is what needs the Linux runtime.'
        : 'The run errored before it could be judged. See the output below.',
    };
  }
  if (code === EXIT_BLOCKED) {
    const deny = text.match(/GATE: DENY[^\n]*/);
    return {
      status: 'denied',
      title: 'Blocked — the wall stopped it.',
      detail: deny
        ? deny[0].replace(/^GATE: DENY — /, '')
        : 'The command tried to touch something outside the allowed scope, so it never ran.',
    };
  }
  return {
    status: 'allowed',
    title: 'Allowed — the command ran inside the wall.',
    detail: 'Nothing outside the allowed scope was touched. See the audit log below for what happened.',
  };
}

module.exports = {
  EXIT_PASS,
  EXIT_BLOCKED,
  EXIT_UNKNOWN,
  EXIT_WALL_SETUP_FAILED,
  verdictForCheck,
  verdictForGate,
  parseCheckOutput,
  brokenIds,
  unmeasuredIds,
};
