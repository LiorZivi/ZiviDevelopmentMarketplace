'use strict';
// Discovers Copilot CLI sessions under ~/.copilot/session-state and tails each
// tracked session's events.jsonl, emitting one "roundtrip" per assistant.message
// (an LLM round-trip). Read-only: never writes/truncates the CLI's files.

const fs = require('fs');
const path = require('path');
const os = require('os');
const { EventEmitter } = require('events');

const DEFAULT_ROOT = path.join(os.homedir(), '.copilot', 'session-state');

function parseLine(line) {
  if (!line || line.length < 2) return null;
  try { return JSON.parse(line); } catch { return null; }
}

function readAllRecords(evPath) {
  let text;
  try { text = fs.readFileSync(evPath, 'utf8'); } catch { return []; }
  const out = [];
  for (const line of text.split('\n')) {
    const rec = parseLine(line);
    if (rec) out.push(rec);
  }
  return out;
}

class SessionStore extends EventEmitter {
  constructor(root = DEFAULT_ROOT, opts = {}) {
    super();
    this.root = root;
    this.activeWindowMs = (opts.activeWindowMinutes || 120) * 60 * 1000;
    this.sessions = new Map(); // convId -> state
    this.pollTimer = null;
    this.tailTimer = null;
  }

  start() {
    this.scan();
    this.pollTimer = setInterval(() => this.scan(), 2000);
    this.tailTimer = setInterval(() => this.tailAll(), 400);
  }

  stop() {
    if (this.pollTimer) clearInterval(this.pollTimer);
    if (this.tailTimer) clearInterval(this.tailTimer);
  }

  publicSession(s) {
    return {
      convId: s.convId,
      meta: s.meta || {},
      mtime: s.mtime,
      active: (Date.now() - s.mtime) <= this.activeWindowMs,
      tracked: !!s.tracked,
      roundTripCount: s.roundTripCount || 0,
      lastTurn: s.lastTurn,
    };
  }

  listSessions() {
    return [...this.sessions.values()]
      .sort((a, b) => b.mtime - a.mtime)
      .map(s => this.publicSession(s));
  }

  scan() {
    let dirents;
    try { dirents = fs.readdirSync(this.root, { withFileTypes: true }); } catch { return; }
    let changed = false;
    for (const d of dirents) {
      if (!d.isDirectory()) continue;
      const convId = d.name;
      const evPath = path.join(this.root, convId, 'events.jsonl');
      let st;
      try { st = fs.statSync(evPath); } catch { continue; }
      let s = this.sessions.get(convId);
      if (!s) {
        s = {
          convId, path: evPath, meta: null, mtime: st.mtimeMs,
          position: 0, buffer: '', roundTripCount: 0, tracked: false, lastTurn: null,
        };
        this.sessions.set(convId, s);
        this.readMetadata(s);
        changed = true;
      } else if (st.mtimeMs !== s.mtime) {
        s.mtime = st.mtimeMs;
        changed = true;
      }
    }
    if (changed) this.emit('sessions', this.listSessions());
  }

  readMetadata(s) {
    // session.start is the first line; read a small prefix.
    try {
      const fd = fs.openSync(s.path, 'r');
      const buf = Buffer.alloc(8192);
      const n = fs.readSync(fd, buf, 0, 8192, 0);
      fs.closeSync(fd);
      const text = buf.toString('utf8', 0, n);
      for (const line of text.split('\n')) {
        const rec = parseLine(line);
        if (rec && rec.type === 'session.start') { this.applyMeta(s, rec); break; }
      }
    } catch { /* ignore */ }
  }

  applyMeta(s, rec) {
    const d = rec.data || {};
    const ctx = d.context || {};
    s.meta = {
      repository: ctx.repository || null,
      branch: ctx.branch || null,
      cwd: ctx.cwd || null,
      gitRoot: ctx.gitRoot || null,
      copilotVersion: d.copilotVersion || null,
      contextTier: d.contextTier || null,
      startTime: d.startTime || null,
    };
  }

  setTracked(convId, tracked) {
    const s = this.sessions.get(convId);
    if (!s) return;
    s.tracked = !!tracked;
    // Echo state immediately so the UI toggle feels instant; run the history
    // replay off the hot path so reading a large transcript never stalls it.
    this.emit('sessions', this.listSessions());
    if (s.tracked) {
      try { s.position = fs.statSync(s.path).size; } catch { s.position = 0; }
      s.buffer = '';
      setImmediate(() => this.replay(s));
    }
  }

  // Replay the session's existing round-trips so the stream shows history at once.
  replay(s) {
    const records = readAllRecords(s.path);
    s.roundTripCount = 0;
    for (const rec of records) {
      if (rec.type === 'session.start') this.applyMeta(s, rec);
      if (rec.type === 'assistant.message') this.emitRoundTrip(s, rec, true);
    }
    this.emit('sessions', this.listSessions());
  }

  tailAll() {
    for (const s of this.sessions.values()) {
      if (s.tracked) this.tail(s);
    }
  }

  tail(s) {
    let st;
    try { st = fs.statSync(s.path); } catch { return; }
    if (st.size < s.position) { s.position = 0; s.buffer = ''; }
    if (st.size === s.position) return;
    let fd;
    try { fd = fs.openSync(s.path, 'r'); } catch { return; }
    const len = st.size - s.position;
    const buf = Buffer.alloc(len);
    try { fs.readSync(fd, buf, 0, len, s.position); } finally { fs.closeSync(fd); }
    s.position = st.size;
    s.buffer += buf.toString('utf8');
    let idx;
    while ((idx = s.buffer.indexOf('\n')) >= 0) {
      const line = s.buffer.slice(0, idx);
      s.buffer = s.buffer.slice(idx + 1);
      const rec = parseLine(line);
      if (rec) this.handleRecord(s, rec);
    }
  }

  handleRecord(s, rec) {
    switch (rec.type) {
      case 'session.start':
        this.applyMeta(s, rec);
        this.emit('sessions', this.listSessions());
        break;
      case 'assistant.message':
        this.emitRoundTrip(s, rec, false);
        break;
      case 'session.model_change':
        this.emit('event', {
          convId: s.convId, kind: 'model_change',
          model: rec.data && rec.data.newModel, effort: rec.data && rec.data.reasoningEffort,
        });
        break;
      default:
        break;
    }
  }

  emitRoundTrip(s, rec, replay) {
    const d = rec.data || {};
    const tools = (d.toolRequests || []).map(t => t.name);
    const rt = {
      convId: s.convId,
      time: rec.timestamp || new Date().toISOString(),
      model: d.model || '',
      turnId: d.turnId,
      interactionId: d.interactionId,
      serviceRequestId: d.serviceRequestId,
      requestId: d.requestId,
      outputTokens: d.outputTokens || 0,
      tools,
      toolCount: tools.length,
      stop: tools.length ? 'tool_use' : 'end_turn',
      init: String(d.turnId) === '0' ? 'user' : 'agent',
      hasContent: !!(d.content && String(d.content).trim()),
      replay: !!replay,
    };
    s.roundTripCount = (s.roundTripCount || 0) + 1;
    s.lastTurn = d.turnId;
    this.emit('roundtrip', rt);
  }

  // First user.message content = a human-readable title. Reads a prefix only
  // (session.start + system.message + first user.message fit comfortably).
  readTitle(s) {
    if (s.title !== undefined) return s.title;
    s.title = null;
    try {
      const fd = fs.openSync(s.path, 'r');
      const size = fs.fstatSync(fd).size;
      const len = Math.min(300000, size);
      const buf = Buffer.alloc(len);
      fs.readSync(fd, buf, 0, len, 0);
      fs.closeSync(fd);
      const lines = buf.toString('utf8').split('\n');
      for (let i = 0; i < lines.length - 1; i++) {
        const r = parseLine(lines[i]);
        if (r && r.type === 'user.message' && r.data && r.data.content) {
          s.title = String(r.data.content).replace(/\s+/g, ' ').trim().slice(0, 140);
          break;
        }
      }
    } catch { /* ignore */ }
    return s.title;
  }

  getTitles(convIds) {
    const out = {};
    for (const id of convIds || []) {
      const s = this.sessions.get(id);
      out[id] = s ? this.readTitleAndCount(s) : null;
    }
    return out;
  }

  // Title (first user.message) + turn count (assistant.message lines). Cached
  // per mtime. Counting uses a substring test to avoid parsing every line.
  readTitleAndCount(s) {
    if (s._tc && s._tcMtime === s.mtime) return s._tc;
    let title = s.title || null, turns = 0;
    try {
      const text = fs.readFileSync(s.path, 'utf8');
      const needle = '"type":"assistant.message"';
      let idx = text.indexOf(needle);
      while (idx !== -1) { turns++; idx = text.indexOf(needle, idx + needle.length); }
      if (!title) {
        const u = text.indexOf('"type":"user.message"');
        if (u !== -1) {
          const start = text.lastIndexOf('\n', u) + 1;
          let end = text.indexOf('\n', u); if (end === -1) end = text.length;
          const r = parseLine(text.slice(start, end));
          if (r && r.data && r.data.content) title = String(r.data.content).replace(/\s+/g, ' ').trim().slice(0, 140);
        }
      }
    } catch { /* ignore */ }
    s.title = title;
    s._tc = { title, turns };
    s._tcMtime = s.mtime;
    return s._tc;
  }

  // All round-trips for a session (static snapshot), independent of tracking.
  // Line-scans without splitting the whole file into an array, and parses only
  // user/assistant message lines (skips the huge system prompt + tool results).
  getTurns(convId) {
    const s = this.sessions.get(convId);
    if (!s) return [];
    let text;
    try { text = fs.readFileSync(s.path, 'utf8'); } catch { return []; }
    const userByInter = {};
    const turns = [];
    let pos = 0;
    const len = text.length;
    while (pos < len) {
      let nl = text.indexOf('\n', pos);
      if (nl === -1) nl = len;
      const line = text.slice(pos, nl);
      pos = nl + 1;
      if (line.length < 2) continue;
      if (line.indexOf('"type":"user.message"') >= 0) {
        const r = parseLine(line);
        if (r && r.type === 'user.message' && r.data && r.data.interactionId && !userByInter[r.data.interactionId]) {
          userByInter[r.data.interactionId] = String(r.data.content || '').replace(/\s+/g, ' ').trim().slice(0, 130);
        }
        continue;
      }
      if (line.indexOf('"type":"assistant.message"') < 0) continue;
      const rec = parseLine(line);
      if (!rec || rec.type !== 'assistant.message') continue;
      const d = rec.data || {};
      const tools = (d.toolRequests || []).map(t => t.name);
      turns.push({
        convId, time: rec.timestamp, model: d.model || '', turnId: d.turnId,
        interactionId: d.interactionId, serviceRequestId: d.serviceRequestId,
        requestId: d.requestId, outputTokens: d.outputTokens || 0, tools,
        toolCount: tools.length, stop: tools.length ? 'tool_use' : 'end_turn',
        init: String(d.turnId) === '0' ? 'user' : 'agent',
        hasContent: !!(d.content && String(d.content).trim()),
        prompt: userByInter[d.interactionId] || null,
      });
    }
    return turns;
  }

  getSession(convId) {
    const s = this.sessions.get(convId);
    return s ? this.publicSession(s) : null;
  }
}

module.exports = { SessionStore, DEFAULT_ROOT };
