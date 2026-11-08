'use strict';
/**
 * Settings: the app's own preferences (NOT the gate policy — that is
 * core/policy.js). Stored as JSON in the Electron userData directory.
 *   cliPath            path to the `fineprint` CLI (null = search PATH)
 *   workdir            default folder for checks and guarded runs
 *   agent              last-picked agent id (codex / muse-code / claude-code)
 *   confine            folder confinement opt-in (off by default)
 *   folders            folders the wall confines to when confine is on
 *   hosts              extra allowlisted hosts when confined
 *   logDir             where audit logs go (null = next to the workdir)
 *   definitionsSource  reserved: definitions ship with a FinePrint
 *                      release, so there is no update feed URL yet.
 * The definitions families are a signed set — they are not toggled
 * per-family in v1. The escape hatch for one command is the policy's
 * allowed_commands (Settings edits it as "always allow this command").
 */
const fs = require('fs');
const path = require('path');

const SETTINGS_FILENAME = 'fineprint-desktop-settings.json';

function defaultSettings() {
  return {
    cliPath: null,
    workdir: null,
    agent: 'codex',
    confine: false,
    folders: [],
    hosts: [],
    logDir: null,
    definitionsSource: null,
  };
}

function loadSettings(filePath) {
  const base = defaultSettings();
  if (!filePath || !fs.existsSync(filePath)) return base;
  try {
    const doc = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (!doc || typeof doc !== 'object') return base;
    return {
      ...base,
      cliPath: typeof doc.cliPath === 'string' ? doc.cliPath : null,
      workdir: typeof doc.workdir === 'string' ? doc.workdir : null,
      agent: typeof doc.agent === 'string' ? doc.agent : 'codex',
      confine: doc.confine === true,
      folders: Array.isArray(doc.folders) ? doc.folders.map(String) : [],
      hosts: Array.isArray(doc.hosts) ? doc.hosts.map(String) : [],
      logDir: typeof doc.logDir === 'string' ? doc.logDir : null,
      definitionsSource: typeof doc.definitionsSource === 'string' ? doc.definitionsSource : null,
    };
  } catch {
    return base;
  }
}

function saveSettings(filePath, settings) {
  const doc = { ...defaultSettings(), ...settings };
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(doc, null, 2) + '\n', 'utf8');
  return loadSettings(filePath);
}

module.exports = {
  SETTINGS_FILENAME,
  defaultSettings,
  loadSettings,
  saveSettings,
};
