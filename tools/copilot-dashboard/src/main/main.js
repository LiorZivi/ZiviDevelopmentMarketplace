'use strict';
const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const { SessionStore } = require('./sessionStore');
const { buildRequest } = require('./requestBuilder');

const ROOT = process.env.COPILOT_SESSION_STATE_ROOT
  || path.join(os.homedir(), '.copilot', 'session-state');

// Software rendering makes offscreen capturePage() reliable during screenshots.
if (process.env.DASH_CAPTURE_DIR) { try { app.disableHardwareAcceleration(); } catch (e) { /* ignore */ } }

let win = null;
let store = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1500,
    height: 940,
    minWidth: 900,
    minHeight: 500,
    title: 'Copilot Dashboard',
    backgroundColor: '#1e1e1e',
    autoHideMenuBar: true,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });
  win.setMenuBarVisibility(false);
  win.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
  win.on('closed', () => { win = null; });
}

app.whenReady().then(() => {
  createWindow();

  store = new SessionStore(ROOT, { activeWindowMinutes: 120 });
  store.on('sessions', list => { if (win) win.webContents.send('sessions', list); });
  store.on('roundtrip', rt => { if (win) win.webContents.send('roundtrip', rt); });
  store.on('event', ev => { if (win) win.webContents.send('event', ev); });
  store.start();

  ipcMain.handle('list-sessions', () => store.listSessions());
  ipcMain.handle('track', (_e, convId, tracked) => { store.setTracked(convId, tracked); return true; });
  ipcMain.handle('get-request', (_e, convId, serviceRequestId, turnId) =>
    buildRequest(ROOT, convId, serviceRequestId, turnId));
  ipcMain.handle('get-turns', (_e, convId) => store.getTurns(convId));
  ipcMain.handle('get-titles', (_e, ids) => store.getTitles(ids));
  ipcMain.handle('get-session', (_e, convId) => store.getSession(convId));
  ipcMain.handle('get-root', () => ROOT);
  ipcMain.handle('open-path', (_e, p) => { shell.showItemInFolder(p); return true; });

  if (process.env.DASH_CAPTURE_DIR) {
    runCaptureSequence(process.env.DASH_CAPTURE_DIR);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (store) store.stop();
  app.quit();
});

/* ---- headless screenshot harness (DASH_CAPTURE_DIR) ---- */
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

async function runCaptureSequence(dir) {
  try { fs.mkdirSync(dir, { recursive: true }); } catch { /* ignore */ }
  const wc = win.webContents;
  const log = (m) => { try { fs.appendFileSync(path.join(dir, 'capture.log'), m + '\n'); } catch { /* ignore */ } };
  const snap = async (name) => {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const img = await Promise.race([
          wc.capturePage(),
          new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 8000)),
        ]);
        fs.writeFileSync(path.join(dir, name + '.png'), img.toPNG());
        log('captured ' + name);
        return;
      } catch (e) { log('capture ' + name + ' attempt ' + attempt + ' failed: ' + e.message); }
    }
  };
  const js = (code) => wc.executeJavaScript(code, true).catch(e => log('js err: ' + e.message));

  await new Promise(res => { if (wc.isLoading()) wc.once('did-finish-load', res); else res(); });
  try { win.show(); win.focusOnWebView(); } catch (e) { /* ignore */ }
  await delay(2500);
  await snap('1-home');

  await js(`window.__dash.navigate({view:'workspaces'})`);
  await delay(700);
  await snap('2-workspaces');

  await js(`window.__dash.filterWorkspaces('learnai')`);
  await delay(500);
  await snap('2b-workspaces-filtered');
  await js(`window.__dash.filterWorkspaces('')`);
  await delay(300);
  await js(`window.__dash.setRecency(${24 * 3600e3})`);
  await delay(500);
  await snap('2c-workspaces-recency');
  await js(`window.__dash.setRecency(0)`);
  await delay(300);

  await js(`window.__dash.openBestWorkspace()`);
  await delay(900);
  await snap('3-workspace');

  await js(`window.__dash.openBestSession()`);
  await delay(1500);
  await snap('4-session-turns');

  await js(`window.__dash.clickBestTurn()`);
  await delay(1500);
  await snap('5-request');

  await js(`window.__dash.setTurnsWidth(780)`);
  await delay(400);
  await snap('5b-splitter-resized');
  await js(`window.__dash.setTurnsWidth(560)`);
  await delay(200);

  await js(`(function(){var t=document.getElementById('sec-request'); if(t) t.scrollIntoView(); document.querySelectorAll('#detailBody details.msg').forEach(function(x){x.open=true});})()`);
  await delay(700);
  await snap('6-request-expanded');

  await js(`window.__dash.trackCurrentAndGoTracked()`);
  await delay(1200);
  await snap('7-tracked');

  await delay(300);
  app.quit();
}
