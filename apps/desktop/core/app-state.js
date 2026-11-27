'use strict';
/**
 * AppState: the app's orchestrator — the part main.js wires to IPC.
 * Pure Node (no Electron imports), so it is fully testable with the
 * stub CLI. It owns: settings, the CLI handle, the policy, the feed
 * store, and the notification hook.
 *
 * Definitions: the CLI is the source of truth. The app asks it for
 * the version in force (`fineprint gate definitions`) and embeds a
 * reference copy of the built-in v1 rules (core/definitions.js) only
 * for labelling feed items — it never enforces anything itself.
 *
 * Flows:
 *   initialize()   find CLI, ask for the definitions in force, load
 *                  or compose the policy, probe denylist support,
 *                  detect the wall runtime.
 *   runCheck(dir)  `fineprint check` -> plain-language verdict + a
 *                  feed item.
 *   runGuarded()   write the run policy, run the guarded command via
 *                  the runtime (native / docker / wsl) or an explicit
 *                  labelled tripwire-only run, parse the audit log,
 *                  add feed items, fire OS notifications for blocks.
 *   setConfinement() / setAllowedCommands() / checkDefinitions()
 */
const fs = require('fs');
const path = require('path');
const cli = require('./cli');
const audit = require('./audit');
const definitions = require('./definitions');
const feed = require('./feed');
const notify = require('./notify');
const policy = require('./policy');
const settingsMod = require('./settings');
const verdict = require('./verdict');
const wall = require('./wall');

const CLI_MISSING = 'The fineprint CLI was not found. Go to Setup and point the app at it, or install it first.';

function familiesSummary() {
  const byId = {};
  for (const r of definitions.BUILTIN_RULES) {
    const f = definitions.ruleFamily(r.id);
    if (!f) continue;
    if (!byId[f.familyId]) {
      byId[f.familyId] = { id: f.familyId, name: f.name, plain: f.plain, catalogue: f.catalogue, ruleIds: [] };
    }
    byId[f.familyId].ruleIds.push(r.id);
  }
  // DENY-EXFIL is produced by the gate, not listed as a rule.
  if (!byId.exfiltration) {
    byId.exfiltration = { id: 'exfiltration', name: 'Exfiltration', plain: 'Stops the agent copying or sending a protected file out.', catalogue: ['FP-004', 'FP-005'], ruleIds: ['DENY-EXFIL'] };
  } else {
    byId.exfiltration.ruleIds.push('DENY-EXFIL');
  }
  return definitions.FAMILY_ORDER.map((id) => byId[id]).filter(Boolean);
}

class AppState {
  constructor({ userDataDir, showNotification, fetchManifest } = {}) {
    if (!userDataDir) throw new Error('AppState needs a userDataDir.');
    this.userDataDir = userDataDir;
    this.showNotification = showNotification || (() => {});
    this.fetchManifest = fetchManifest || null;
    this.settingsFile = path.join(userDataDir, settingsMod.SETTINGS_FILENAME);
    this.feedFile = path.join(userDataDir, 'feed.json');
    this.settings = settingsMod.loadSettings(this.settingsFile);
    this.feedStore = new feed.FeedStore(this.feedFile);
    this.cli = null;
    this.definitionsInForce = null;
    this.denylist = null;
    this.runtime = null;
    this.policyDoc = null;
  }

  async initialize() {
    this.cli = cli.findCli(this.settings.cliPath);
    if (this.cli) {
      try {
        this.definitionsInForce = await cli.definitions(this.cli);
      } catch {
        this.definitionsInForce = { ok: false, version: null, source: null, ruleCount: null, raw: '' };
      }
      this.denylist = await cli.probeDenylistSupport(this.cli, this.settings.workdir || process.cwd());
    } else {
      this.definitionsInForce = null;
      this.denylist = null;
    }
    const workdir = this.settings.workdir || process.cwd();
    const policyFile = path.join(workdir, policy.POLICY_FILENAME);
    if (fs.existsSync(policyFile)) {
      this.policyDoc = policy.loadPolicy(policyFile);
    } else {
      this.policyDoc = policy.defaultPolicy(workdir);
    }
    this.runtime = wall.detectRuntime();
    return this.getStatus();
  }

  getStatus() {
    const version = (this.definitionsInForce && this.definitionsInForce.version)
      || definitions.BUILTIN_VERSION;
    const inForce = this.definitionsInForce && this.definitionsInForce.ok;
    const desc = this.policyDoc ? policy.describePolicy(this.policyDoc) : null;
    return {
      platform: process.platform,
      cli: this.cli ? { path: this.cli.path, mode: this.cli.mode } : null,
      cliMissing: !this.cli,
      runtime: this.runtime,
      runtimeLine: this.runtime ? wall.describeRuntime(this.runtime) : null,
      definitions: {
        version,
        source: (this.definitionsInForce && this.definitionsInForce.source) || 'built-in',
        ruleCount: (this.definitionsInForce && this.definitionsInForce.ruleCount) || definitions.BUILTIN_RULES.length,
        valid: inForce !== false,
        validReason: inForce === false
          ? 'The CLI could not report the definitions in force.'
          : '',
        families: familiesSummary(),
      },
      protectionLine: definitions.protectionLine(version),
      denylist: this.denylist,
      policy: desc,
      settings: { ...this.settings },
      feedCount: this.feedStore.list().length,
    };
  }

  saveSettings(patch) {
    this.settings = settingsMod.saveSettings(this.settingsFile, { ...this.settings, ...patch });
    return { ...this.settings };
  }

  setConfinement(confine, folders) {
    if (!this.policyDoc) throw new Error('App is not initialised yet.');
    const allowed = confine
      ? (folders && folders.length ? folders : this.policyDoc.allowed_paths)
      : this.policyDoc.allowed_paths;
    this.policyDoc = {
      ...this.policyDoc,
      mode: confine ? 'confine' : 'deny',
      allowed_paths: allowed,
    };
    this.saveSettings({ confine: !!confine, folders: confine ? allowed : this.settings.folders });
    return this.getStatus();
  }

  /** The "always allow this command" escape hatch (policy allowed_commands). */
  setAllowedCommands(commands) {
    if (!this.policyDoc) throw new Error('App is not initialised yet.');
    const list = (commands || []).map((c) => String(c).trim()).filter(Boolean);
    this.policyDoc = { ...this.policyDoc, allowed_commands: list };
    const workdir = this.settings.workdir || process.cwd();
    policy.savePolicy(path.join(workdir, policy.POLICY_FILENAME), this.policyDoc);
    return this.getStatus();
  }

  async checkDefinitions() {
    if (!this.cli) {
      return { status: 'no-source', currentVersion: definitions.BUILTIN_VERSION, latestVersion: null, note: 'No CLI found — the bundled rules are the ones this app knows about.' };
    }
    const inForce = await cli.definitions(this.cli);
    return definitions.checkForUpdates({
      currentVersion: definitions.BUILTIN_VERSION,
      inForceVersion: inForce.ok ? inForce.version : null,
    });
  }

  async runCheck(dir) {
    if (!this.cli) throw new cli.CliNotFoundError(CLI_MISSING);
    const target = dir || this.settings.workdir || process.cwd();
    const res = await cli.check(this.cli, target, {});
    const v = verdict.verdictForCheck(res.code, res.bundle);
    const item = feed.itemFromCheckResult({ code: res.code, bundle: res.bundle, bundlePath: res.bundlePath });
    this.feedStore.append(item);
    return { code: res.code, stdout: res.stdout, stderr: res.stderr, bundlePath: res.bundlePath, verdict: v, feedItem: item };
  }

  async runGuarded({ agent, folder, command, tripwireOnly = false } = {}) {
    if (!this.cli) throw new cli.CliNotFoundError(CLI_MISSING);
    if (!this.policyDoc) throw new Error('App is not initialised yet.');
    const workdir = folder || this.settings.workdir || process.cwd();
    const cmd = Array.isArray(command) ? command : [command];
    if (!cmd.length || !cmd[0]) throw new Error('A guarded run needs a command.');
    const runtime = this.runtime || wall.detectRuntime();
    const agentInfo = wall.resolveAgent(agent || this.settings.agent, runtime);

    const policyFile = path.join(workdir, policy.POLICY_FILENAME);
    const runPolicy = { ...this.policyDoc };
    if (runPolicy.mode === 'confine') {
      runPolicy.allowed_paths = runPolicy.allowed_paths && runPolicy.allowed_paths.length
        ? runPolicy.allowed_paths : [workdir];
    }
    policy.savePolicy(policyFile, runPolicy);
    const logFile = path.join(this.settings.logDir || workdir, 'fineprint-audit.jsonl');
    if (fs.existsSync(logFile)) fs.unlinkSync(logFile);

    let res;
    const onData = () => {};
    if (runtime.kind === 'native' || tripwireOnly) {
      if (runtime.kind === 'none' && !tripwireOnly) {
        return {
          code: 3, error: 'wall-unavailable',
          verdict: { status: 'wall-unavailable', title: 'The wall is not available on this machine.', detail: runtime.detail },
          agent: agentInfo, feedItems: [], output: '', logValid: null,
        };
      }
      res = await cli.gateRun(this.cli, {
        policy: policyFile, log: logFile, command: cmd, cwd: workdir,
        noWall: tripwireOnly, confine: runPolicy.mode === 'confine', onData,
      });
    } else if (runtime.kind === 'docker') {
      const argv = wall.buildDockerRun({
        image: wall.DOCKER_IMAGE, workdir,
        cliDir: path.dirname(this.cli.path),
        policyFile, logFile, command: cmd,
        // Auth has to cross the container boundary: the agent inside
        // needs its own login. Pass API keys through when set on the
        // host; unset keys are skipped (buildDockerRun drops falsy).
        env: {
          ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
          OPENAI_API_KEY: process.env.OPENAI_API_KEY,
        },
      });
      res = await cli.runCli({ path: 'docker', mode: 'direct' }, argv.slice(1), { cwd: workdir, onData });
    } else if (runtime.kind === 'wsl') {
      const argv = wall.buildWslRun({ cliFile: this.cli.path, policyFile, logFile, command: cmd, cwd: workdir });
      res = await cli.runCli({ path: 'wsl', mode: 'direct' }, argv.slice(1), { cwd: workdir, onData });
    } else {
      return {
        code: 3, error: 'wall-unavailable',
        verdict: { status: 'wall-unavailable', title: 'The wall is not available on this machine.', detail: runtime.detail },
        agent: agentInfo, feedItems: [], output: '', logValid: null,
      };
    }

    const v = verdict.verdictForGate(res.code, res.stdout);
    const output = `${res.stdout || ''}${res.stderr || ''}`;
    // Parse the audit log -> feed items + OS notifications for blocks.
    let entries = [];
    let logValid = null;
    if (fs.existsSync(logFile)) {
      try {
        entries = audit.parseLogFile(logFile);
        logValid = audit.verifyChain(entries).valid;
      } catch { entries = []; logValid = false; }
    }
    const commandText = cmd.join(' ');
    const items = [];
    for (const e of entries) {
      const item = feed.itemFromAuditEntry(e, {
        commandText, rules: definitions.BUILTIN_RULES,
        agent: agent || this.settings.agent,
      });
      if (item) items.push(item);
    }
    // One OS notification per blocked entry — the run summary below is
    // feed-only, so a single denied run notifies exactly once.
    const notified = notify.notifyBlockedItems(this.showNotification, items);
    // The run summary counts blocks, not feed items: a second-opinion
    // allow is a feed item but was not blocked, and a run stopped
    // only by the second opinion gets a non-deterministic summary.
    const detBlocked = items.filter((i) => i.kind === 'blocked').length;
    const s1Blocked = items.filter((i) => i.kind === 'second-opinion-block'
      || i.kind === 'second-opinion-error').length;
    const summary = feed.itemFromGuardedRun({
      code: res.code, command: cmd, blockedCount: detBlocked,
      secondOpinionBlocked: s1Blocked,
      agent: agent || this.settings.agent,
    });
    if (summary) items.push(summary);
    this.feedStore.appendMany(items);
    return {
      code: res.code, verdict: v, agent: agentInfo, feedItems: items,
      output, logValid, notified,
      auditLines: entries.map((e) => audit.describeEntry(e)),
    };
  }

  getFeed() {
    return this.feedStore.list();
  }

  clearFeed() {
    this.feedStore.clear();
    return [];
  }
}

module.exports = { AppState, CLI_MISSING };
