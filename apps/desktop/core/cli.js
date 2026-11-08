'use strict';
/**
 * CliDriver: the app's only way to talk to the `fineprint` CLI.
 *
 * The CLI contract (verified against the real sibling CLI, branch
 * free-wall, 2026-11-07 — see docs/CLI-CONTRACT.md):
 *   fineprint check [options]        exit 0 pass / 2 blocked / 3 unknown
 *   fineprint init [--gate]          writes fineprint-gate.json
 *   fineprint verify BUNDLE          exit 0 = seal valid
 *   fineprint report BUNDLE          readable verdict table
 *   fineprint gate run --policy P --log L [--no-wall] [--confine] -- CMD...
 *                                    exit 2 tripwire deny, 3 error/wall
 *                                    unavailable, 125 wall setup failed,
 *                                    otherwise the command's own exit code
 *   fineprint gate check --file P | --host H
 *   fineprint gate verify-log --log FILE
 *   fineprint gate definitions       prints the definitions version in force
 *   fineprint gate log --log FILE    renders the audit log in plain words
 *   fineprint harnesses
 * Policy (fineprint-gate.json): mode "deny" (default, protective
 * denylist) or "confine" (opt-in allowlist); denied_paths (fnmatch),
 * denied_hosts, allowed_commands (override the denylist for one
 * command), allowed_paths, allowed_hosts.
 * The CLI is a Python script: run it directly when executable, else via
 * `python3 <file>`. The app finds it on PATH or from Settings.
 */
const { spawn, spawnSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class CliNotFoundError extends Error {
  constructor(message) {
    super(message);
    this.name = 'CliNotFoundError';
  }
}

function which(bin, extraDirs) {
  try {
    const env = { ...process.env };
    if (extraDirs && extraDirs.length) {
      env.PATH = `${extraDirs.join(':')}:${env.PATH || ''}`;
    }
    const out = execSync(`command -v ${bin}`, { env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    return out.trim() || null;
  } catch {
    return null;
  }
}

/** Find the CLI. settingsPath wins; else PATH; else null. */
function findCli(settingsPath) {
  if (settingsPath && fs.existsSync(settingsPath)) {
    return describeCliFile(settingsPath);
  }
  const onPath = which('fineprint');
  if (onPath) return describeCliFile(onPath);
  return null;
}

function describeCliFile(file) {
  const stat = fs.statSync(file);
  let mode = 'python';
  try {
    fs.accessSync(file, fs.constants.X_OK);
    const head = fs.readFileSync(file, { encoding: 'utf8' }).slice(0, 200);
    if (head.startsWith('#!')) mode = 'direct';
  } catch {
    mode = 'python';
  }
  return { path: path.resolve(file), mode, isDirectory: stat.isDirectory() };
}

function invokeArgv(cli, args) {
  if (cli.mode === 'direct') return [cli.path, ...args];
  return ['python3', cli.path, ...args];
}

/** Run the CLI once. Returns {code, stdout, stderr}. Never throws on exit codes. */
function runCli(cli, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const argv = invokeArgv(cli, args);
    const child = spawn(argv[0], argv.slice(1), {
      cwd: opts.cwd || process.cwd(),
      env: { ...process.env, ...(opts.env || {}) },
      timeout: opts.timeoutMs || 120000,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d; if (opts.onData) opts.onData(d.toString(), 'stdout'); });
    child.stderr.on('data', (d) => { stderr += d; if (opts.onData) opts.onData(d.toString(), 'stderr'); });
    child.on('error', (err) => reject(new Error(`could not run ${argv[0]}: ${err.message}`)));
    child.on('close', (code) => resolve({ code: code === null ? 3 : code, stdout, stderr }));
  });
}

function newestBundleDir(dir) {
  const base = path.join(dir, 'fineprint-evidence');
  if (!fs.existsSync(base)) return null;
  const dirs = fs.readdirSync(base)
    .filter((d) => d.startsWith('check-'))
    .map((d) => path.join(base, d))
    .filter((d) => fs.existsSync(path.join(d, 'bundle.json')))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  return dirs[0] || null;
}

/** Run `fineprint check` in `dir`; load the bundle it wrote, if any. */
async function check(cli, dir, opts = {}) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found. Go to Setup and point the app at it, or install it first.');
  const args = ['check'];
  if (opts.harness) args.push('--harness', opts.harness);
  if (opts.rules) args.push('--rules', opts.rules);
  const res = await runCli(cli, args, { cwd: dir, onData: opts.onData, timeoutMs: opts.timeoutMs });
  let bundle = null;
  let bundlePath = null;
  const bdir = newestBundleDir(dir);
  if (bdir) {
    bundlePath = path.join(bdir, 'bundle.json');
    try { bundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8')); } catch { bundle = null; }
  }
  return { ...res, bundle, bundlePath };
}

/** Run `fineprint gate run` for one command. Streams output via onData. */
async function gateRun(cli, { policy, log, command, cwd, noWall = false, confine = false, onData, timeoutMs, env }) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found. Go to Setup and point the app at it, or install it first.');
  if (!Array.isArray(command) || command.length === 0) {
    throw new Error('gate run needs a command to run.');
  }
  const args = ['gate', 'run', '--policy', policy, '--log', log];
  if (noWall) args.push('--no-wall');
  if (confine) args.push('--confine');
  args.push('--', ...command);
  return runCli(cli, args, { cwd, onData, timeoutMs, env });
}

async function gateCheck(cli, { policy, file, host }) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found.');
  const args = ['gate', 'check', '--policy', policy];
  if (file) args.push('--file', file);
  else if (host) args.push('--host', host);
  else throw new Error('gate check needs --file or --host.');
  return runCli(cli, args, {});
}

/**
 * Does this CLI enforce the denylist (denied_paths in the policy)?
 * Writes a temp policy that denies one temp file and asks `gate check`
 * about it. Denied (exit 2) = supported; allowed (exit 0) = the CLI
 * only enforces the allowlist and ignores denied_* fields. Error (exit
 * 3) = the probe itself failed. Temp files are removed afterwards.
 * The app shows the result honestly instead of claiming protection
 * the CLI cannot enforce. See docs/CLI-CONTRACT.md.
 */
async function probeDenylistSupport(cli, dir) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found.');
  const os = require('os');
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fineprint-probe-'));
  try {
    const probeFile = path.join(tmp, 'probe.txt');
    fs.writeFileSync(probeFile, 'probe\n', 'utf8');
    const policyPath = path.join(tmp, 'fineprint-gate.json');
    fs.writeFileSync(policyPath, JSON.stringify({
      $comment: 'FinePrint denylist probe policy (temporary).',
      mode: 'deny',
      denied_paths: [probeFile],
      denied_hosts: [],
      allowed_commands: [],
      allowed_paths: ['.'],
      allowed_hosts: [],
    }, null, 2) + '\n', 'utf8');
    const res = await gateCheck(cli, { policy: policyPath, file: probeFile });
    if (res.code === 2) {
      return { supported: true, detail: 'This CLI enforces the denylist: a file on the deny list was denied.' };
    }
    if (res.code === 0) {
      return { supported: false, detail: 'This CLI does not enforce the denylist yet: a file on the deny list was allowed. Folder confinement still works; update the CLI for definitions protection.' };
    }
    return { supported: false, detail: `The denylist probe failed (gate check exit ${res.code}): ${res.stderr.trim() || res.stdout.trim()}` };
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

/** Ask the CLI which definitions are in force (`gate definitions`). */
async function definitions(cli) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found.');
  const res = await runCli(cli, ['gate', 'definitions'], {});
  const defs = require('./definitions');
  const parsed = defs.parseDefinitionsOutput(res.stdout);
  if (res.code !== 0 || !parsed) {
    return { ok: false, version: null, source: null, ruleCount: null, raw: res.stdout + res.stderr };
  }
  return { ok: true, ...parsed, raw: res.stdout };
}

async function initGate(cli, dir) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found.');
  return runCli(cli, ['init', '--gate'], { cwd: dir });
}

async function verifyLog(cli, logPath) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found.');
  const res = await runCli(cli, ['gate', 'verify-log', '--log', logPath], {});
  return { ...res, valid: res.code === 0 && /valid/i.test(res.stdout) };
}

async function harnesses(cli) {
  if (!cli) throw new CliNotFoundError('The fineprint CLI was not found.');
  return runCli(cli, ['harnesses'], {});
}

module.exports = {
  CliNotFoundError,
  which,
  findCli,
  describeCliFile,
  invokeArgv,
  runCli,
  check,
  gateRun,
  gateCheck,
  probeDenylistSupport,
  definitions,
  initGate,
  verifyLog,
  harnesses,
  newestBundleDir,
};
