'use strict';
/**
 * FinePrint desktop — Electron main process (thin shell).
 * All app logic lives in core/app-state.js (testable without Electron);
 * this file only creates the window, wires IPC to AppState, shows OS
 * notifications, and opens folder/file dialogs.
 *
 * Demo mode: `electron . --demo` creates a throwaway demo folder
 * (work/ + secret/keys.txt with a FAKE secret) and loads the renderer
 * with ?demo=1, which runs the scripted flow in renderer/demo.js
 * against the real CLI (FINEPRINT_CLI env) or the configured one.
 * The demo runs a real guarded command through the real wall; it
 * never fakes output. See docs/RECORDING.md.
 *
 * Second-opinion demo mode: `electron . --demo-s1` loads the renderer
 * with ?demo=s1, which shows the Home feed seeded from a RECORDED
 * real gate log (assets/demo-second-opinion-log.jsonl — entries the
 * real gate wrote with the real bekko model, hash chain intact; see
 * tests/test-feed-real-log.js). It is a replay, not a live model run:
 * the model takes ~2 minutes to load, so a live run cannot be the
 * demo. The feed rendering is the same code path as a live run
 * (audit.parseLogFile + feed.itemFromAuditEntry); only the log
 * source differs, and the README caption says so.
 */
const { app, BrowserWindow, ipcMain, dialog, Notification } = require('electron');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { AppState } = require('./core/app-state');
const audit = require('./core/audit');
const definitions = require('./core/definitions');
const feed = require('./core/feed');

let state = null;
let mainWindow = null;
let demoMode = '1'; // '1' for --demo, 's1' for --demo-s1 (set in whenReady).

function createDemoDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'fineprint-demo-'));
  const work = path.join(dir, 'work');
  const secret = path.join(dir, 'secret');
  fs.mkdirSync(work);
  fs.mkdirSync(secret);
  fs.writeFileSync(path.join(work, 'note.txt'), 'hello from the demo folder\n');
  // The protected records file (V1-20): reading it is denied by
  // DENY-RECORDS, which is what the demo's guarded run tries.
  fs.writeFileSync(path.join(work, 'records.txt'), 'FAKE RECORDS — DO NOT USE\n');
  fs.writeFileSync(path.join(secret, 'keys.txt'), 'FAKE-SECRET-DO-NOT-USE\n');
  return dir;
}

function showNotification(title, body) {
  try {
    new Notification({ title, body }).show();
  } catch {
    // No notification server (e.g. headless Linux): the feed entry is
    // the record; a missing OS popup must never break a guarded run.
  }
}

function createWindow(demoDir) {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'FinePrint — the wall for your coding agent',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  let url = `file://${path.join(__dirname, 'renderer', 'index.html')}`;
  if (demoDir) {
    url += `?demo=${demoMode}&demodir=${encodeURIComponent(demoDir)}`;
  }
  mainWindow.loadURL(url);
  mainWindow.on('closed', () => { mainWindow = null; });
}

/** Demo-s1 only: seed the feed from a recorded real gate log (see the
 * header comment). The entries are converted through the same
 * itemFromAuditEntry the live path uses; timestamps are staggered by
 * a second so the feed's newest-first order matches the log's order
 * (all three verdicts happened within one recorded run). */
function seedDemoS1Feed() {
  const logPath = process.env.FINEPRINT_DEMO_S1_LOG
    || path.join(__dirname, 'assets', 'demo-second-opinion-log.jsonl');
  const entries = audit.parseLogFile(logPath);
  const items = [];
  for (const e of entries) {
    const item = feed.itemFromAuditEntry(e, {
      rules: definitions.BUILTIN_RULES, agent: 'codex',
    });
    if (item) items.push(item);
  }
  const now = Date.now();
  items.forEach((it, i) => {
    it.ts = new Date(now - (items.length - 1 - i) * 1000).toISOString();
  });
  state.feedStore.appendMany(items);
  return items.length;
}

function wireIpc() {
  ipcMain.handle('fp:status', () => state.getStatus());
  ipcMain.handle('fp:reinit', async () => state.initialize());
  ipcMain.handle('fp:demo-done', async () => {
    // Lets a recording script know the scripted demo finished.
    const marker = process.env.FINEPRINT_DEMO_MARKER || '/tmp/fineprint-demo-done';
    fs.writeFileSync(marker, `done ${new Date().toISOString()}\n`);
    return { ok: true };
  });
  ipcMain.handle('fp:check', async (_e, dir) => state.runCheck(dir));
  ipcMain.handle('fp:guard', async (_e, opts) => state.runGuarded(opts));
  ipcMain.handle('fp:settings-save', async (_e, patch) => state.saveSettings(patch));
  ipcMain.handle('fp:set-allowed-commands', async (_e, commands) => state.setAllowedCommands(commands));
  ipcMain.handle('fp:set-confinement', async (_e, confine, folders) => state.setConfinement(confine, folders));
  ipcMain.handle('fp:check-definitions', async () => state.checkDefinitions());
  ipcMain.handle('fp:feed', () => state.getFeed());
  ipcMain.handle('fp:feed-summary', () => feed.summarizeFeed(state.getFeed()));
  ipcMain.handle('fp:clear-feed', () => state.clearFeed());
  ipcMain.handle('fp:pick-folder', async () => {
    const r = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
    return r.canceled ? null : r.filePaths[0];
  });
  ipcMain.handle('fp:pick-cli', async () => {
    const r = await dialog.showOpenDialog(mainWindow, { properties: ['openFile'] });
    return r.canceled ? null : r.filePaths[0];
  });
}

app.whenReady().then(async () => {
  const demo = process.argv.includes('--demo');
  const demoS1 = process.argv.includes('--demo-s1');
  const demoDir = (demo || demoS1) ? createDemoDir() : null;
  if (process.env.FINEPRINT_CLI) {
    // Demo/recording convenience: point the app at a CLI without
    // touching the user's saved settings file.
    state = new AppState({
      userDataDir: app.getPath('userData'),
      showNotification,
    });
    state.saveSettings({ cliPath: process.env.FINEPRINT_CLI });
    if (demoDir) state.saveSettings({ workdir: path.join(demoDir, 'work') });
  } else {
    state = new AppState({
      userDataDir: app.getPath('userData'),
      showNotification,
    });
    if (demoDir) state.saveSettings({ workdir: path.join(demoDir, 'work') });
  }
  await state.initialize();
  if (demoS1) {
    demoMode = 's1';
    const n = seedDemoS1Feed();
    console.log(`[fp-demo-s1] seeded the feed with ${n} items from the recorded second-opinion log`);
  }
  wireIpc();
  createWindow(demoDir);
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(null);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
