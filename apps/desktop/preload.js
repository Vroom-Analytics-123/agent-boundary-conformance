'use strict';
/**
 * Preload: the only bridge between the renderer and the main process.
 * The renderer never touches Node or Electron directly — it calls
 * window.fineprint.* and gets plain JSON back.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('fineprint', {
  status: () => ipcRenderer.invoke('fp:status'),
  reinit: () => ipcRenderer.invoke('fp:reinit'),
  demoDone: () => ipcRenderer.invoke('fp:demo-done'),
  check: (dir) => ipcRenderer.invoke('fp:check', dir),
  guard: (opts) => ipcRenderer.invoke('fp:guard', opts),
  saveSettings: (patch) => ipcRenderer.invoke('fp:settings-save', patch),
  setAllowedCommands: (commands) => ipcRenderer.invoke('fp:set-allowed-commands', commands),
  setConfinement: (confine, folders) => ipcRenderer.invoke('fp:set-confinement', confine, folders),
  checkDefinitions: () => ipcRenderer.invoke('fp:check-definitions'),
  feed: () => ipcRenderer.invoke('fp:feed'),
  clearFeed: () => ipcRenderer.invoke('fp:clear-feed'),
  pickFolder: () => ipcRenderer.invoke('fp:pick-folder'),
  pickCli: () => ipcRenderer.invoke('fp:pick-cli'),
});
