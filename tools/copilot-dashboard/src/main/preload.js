'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  listSessions: () => ipcRenderer.invoke('list-sessions'),
  track: (convId, tracked) => ipcRenderer.invoke('track', convId, tracked),
  getRequest: (convId, serviceRequestId, turnId) =>
    ipcRenderer.invoke('get-request', convId, serviceRequestId, turnId),
  getTurns: (convId) => ipcRenderer.invoke('get-turns', convId),
  getTitles: (ids) => ipcRenderer.invoke('get-titles', ids),
  getSession: (convId) => ipcRenderer.invoke('get-session', convId),
  getRoot: () => ipcRenderer.invoke('get-root'),
  openPath: (p) => ipcRenderer.invoke('open-path', p),
  onSessions: (cb) => ipcRenderer.on('sessions', (_e, list) => cb(list)),
  onRoundTrip: (cb) => ipcRenderer.on('roundtrip', (_e, rt) => cb(rt)),
  onEvent: (cb) => ipcRenderer.on('event', (_e, ev) => cb(ev)),
});
