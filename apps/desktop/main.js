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
 */
const { app, BrowserWindow, ipcMain, dialog, Notification } = require('electron');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { AppState } = require('./core/app-state');

let state = null;
let mainWindow = null;

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
    url += `?demo=1&demodir=${encodeURIComponent(demoDir)}`;
  }
  mainWindow.loadURL(url);
  mainWindow.on('closed', () => { mainWindow = null; });
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
  const demoDir = demo ? createDemoDir() : null;
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
  wireIpc();
  createWindow(demoDir);
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(null);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
