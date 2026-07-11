'use strict';

/* ---------------- state ---------------- */
const state = { view: 'home', workspaceKey: null, convId: null };
const data = {
  sessions: [],
  workspaces: [],
  turns: new Map(),        // convId -> [rt]
  titles: new Map(),       // convId -> title
  counts: new Map(),       // convId -> turn count
  selectedTurnEl: null,
  turnFilter: '',
  wsFilter: '',
  activeOnly: false,
  recencyMs: 0,
  turnsWidth: null,
};

/* ---------------- dom + utils ---------------- */
const $ = (id) => document.getElementById(id);
const viewEl = $('view');
const breadcrumbEl = $('breadcrumb');

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function shortTag(id) { return id ? id.slice(-4) : '----'; }
const colorCache = {};
function sessionColor(id) {
  if (!id) return '#888';
  if (colorCache[id]) return colorCache[id];
  let hsh = 0;
  for (let i = 0; i < id.length; i++) hsh = (hsh * 31 + id.charCodeAt(i)) & 0x7fffffff;
  return colorCache[id] = `hsl(${hsh % 360}, 60%, 66%)`;
}
function fmtTime(iso) { if (!iso) return ''; const d = new Date(iso); return isNaN(d) ? '' : d.toTimeString().slice(0, 8); }
function fmtTok(n) { n = Number(n) || 0; return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }
function fmtAgo(ms) {
  if (!ms) return '';
  const s = Math.floor((Date.now() - ms) / 1000);
  if (s < 60) return s + 's ago';
  const m = Math.floor(s / 60); if (m < 60) return m + 'm ago';
  const hh = Math.floor(m / 60); if (hh < 24) return hh + 'h ago';
  return Math.floor(hh / 24) + 'd ago';
}
function cwdLeaf(cwd) { if (!cwd) return '(unknown)'; return cwd.split(/[\\/]/).filter(Boolean).pop() || cwd; }
function repoLeaf(repo) { return repo ? repo.split('/').pop() : null; }
function cssEsc(s) { return String(s || '').replace(/["\\]/g, '\\$&'); }

/* recency (last-activity) filter, shared across views */
const RECENCY_OPTS = [
  { label: 'Any time', ms: 0 },
  { label: 'Last hour', ms: 3600e3 },
  { label: 'Last 6 hours', ms: 6 * 3600e3 },
  { label: 'Last 24 hours', ms: 24 * 3600e3 },
  { label: 'Last 3 days', ms: 3 * 24 * 3600e3 },
  { label: 'Last 7 days', ms: 7 * 24 * 3600e3 },
  { label: 'Last 30 days', ms: 30 * 24 * 3600e3 },
];
function withinRecency(mtime) { return !data.recencyMs || (Date.now() - mtime) <= data.recencyMs; }
function filterByRecency(list) { return data.recencyMs ? list.filter(x => withinRecency(x.mtime)) : list; }
function recencySelectHtml(id) {
  return `<select id="${id}" class="recency" title="filter by last activity">` +
    RECENCY_OPTS.map(o => `<option value="${o.ms}" ${data.recencyMs === o.ms ? 'selected' : ''}>${escapeHtml(o.label)}</option>`).join('') +
    '</select>';
}
function wireRecency(id, rerender) {
  const el = $(id);
  if (el) el.addEventListener('change', (e) => { data.recencyMs = Number(e.target.value); rerender(); });
}
function activeChkHtml(id) {
  return `<label class="chk"><input type="checkbox" id="${id}" ${data.activeOnly ? 'checked' : ''}/> active only</label>`;
}
function wireActive(id, rerender) {
  const el = $(id);
  if (el) el.addEventListener('change', (e) => { data.activeOnly = e.target.checked; rerender(); });
}
function filteredSessions(list) {
  let out = list;
  if (data.activeOnly) out = out.filter(s => s.active);
  out = filterByRecency(out);
  return out;
}

/* ---------------- data plumbing ---------------- */
function sessionById(convId) { return data.sessions.find(s => s.convId === convId); }
function workspaceByKey(key) { return data.workspaces.find(w => w.key === key); }
function trackedSessions() { return data.sessions.filter(s => s.tracked); }

function rebuildWorkspaces() {
  const map = new Map();
  for (const s of data.sessions) {
    const cwd = (s.meta && (s.meta.cwd || s.meta.gitRoot)) || '(unknown)';
    if (!map.has(cwd)) map.set(cwd, { key: cwd, cwd, repo: (s.meta && s.meta.repository) || null, sessions: [], activeCount: 0, tracked: 0, lastMtime: 0 });
    const w = map.get(cwd);
    w.sessions.push(s);
    if (s.active) w.activeCount++;
    if (s.tracked) w.tracked++;
    if (s.mtime > w.lastMtime) w.lastMtime = s.mtime;
    if (!w.repo && s.meta && s.meta.repository) w.repo = s.meta.repository;
  }
  data.workspaces = [...map.values()].sort((a, b) => b.activeCount - a.activeCount || b.lastMtime - a.lastMtime);
}

/* ---------------- backend events ---------------- */
window.api.onSessions((list) => {
  data.sessions = list;
  rebuildWorkspaces();
  if (state.view === 'workspaces' && document.getElementById('wsGrid')) renderWorkspaceGrid();
  else if (['home', 'workspaces', 'workspace', 'tracked'].includes(state.view)) render();
  else if (state.view === 'session') updateSessionHeader();
});
window.api.onRoundTrip((rt) => {
  if (!data.turns.has(rt.convId)) data.turns.set(rt.convId, []);
  const arr = data.turns.get(rt.convId);
  if (!(rt.serviceRequestId && arr.some(x => x.serviceRequestId === rt.serviceRequestId))) arr.push(rt);
  if (state.view === 'session' && state.convId === rt.convId) maybeAppendTurn(rt);
});

/* ---------------- navigation ---------------- */
function navigate(next) { Object.assign(state, { workspaceKey: null, convId: null }, next); render(); }

function render() {
  renderBreadcrumb();
  viewEl.className = 'view-' + state.view;
  if (state.view === 'home') return renderHome();
  if (state.view === 'workspaces') return renderWorkspaces();
  if (state.view === 'workspace') return renderWorkspace();
  if (state.view === 'session') return renderSession();
  if (state.view === 'tracked') return renderTracked();
}

function renderBreadcrumb() {
  const crumbs = [{ label: 'Home', go: { view: 'home' } }];
  if (state.view === 'workspaces') crumbs.push({ label: 'Workspaces' });
  if (state.view === 'tracked') crumbs.push({ label: 'Tracked' });
  if (state.view === 'workspace') {
    crumbs.push({ label: 'Workspaces', go: { view: 'workspaces' } });
    const w = workspaceByKey(state.workspaceKey);
    crumbs.push({ label: cwdLeaf(w && w.cwd) });
  }
  if (state.view === 'session') {
    const s = sessionById(state.convId);
    const cwd = s && s.meta && s.meta.cwd;
    crumbs.push({ label: 'Workspaces', go: { view: 'workspaces' } });
    if (cwd) crumbs.push({ label: cwdLeaf(cwd), go: { view: 'workspace', workspaceKey: cwd } });
    crumbs.push({ label: '[' + shortTag(state.convId) + ']' });
  }
  breadcrumbEl.innerHTML = crumbs.map((c, i) =>
    (i > 0 ? '<span class="sep">›</span>' : '') +
    (c.go ? `<span class="crumb link" data-i="${i}">${escapeHtml(c.label)}</span>` : `<span class="crumb">${escapeHtml(c.label)}</span>`)
  ).join('');
  breadcrumbEl.querySelectorAll('.crumb.link').forEach(el => {
    const c = crumbs[Number(el.dataset.i)];
    el.addEventListener('click', () => navigate(c.go));
  });
}

/* ---------------- home ---------------- */
function renderHome() {
  const wsCount = data.workspaces.length;
  const activeWs = data.workspaces.filter(w => w.activeCount > 0).length;
  const trk = trackedSessions().length;
  viewEl.innerHTML = `
    <div class="home">
      <div class="home-card" id="goWorkspaces">
        <div class="hc-icon">🗂️</div>
        <div class="hc-title">Workspaces</div>
        <div class="hc-sub">${wsCount} workspaces · ${activeWs} active</div>
        <div class="hc-desc">Browse Copilot CLI sessions grouped by working directory — each git worktree is its own workspace.</div>
      </div>
      <div class="home-card" id="goTracked">
        <div class="hc-icon">📌</div>
        <div class="hc-title">Tracked sessions</div>
        <div class="hc-sub">${trk} tracked</div>
        <div class="hc-desc">Jump straight to the sessions you are watching live — stream their round-trips and open requests.</div>
      </div>
    </div>`;
  $('goWorkspaces').addEventListener('click', () => navigate({ view: 'workspaces' }));
  $('goTracked').addEventListener('click', () => navigate({ view: 'tracked' }));
}

/* ---------------- workspaces ---------------- */
function renderWorkspaces() {
  viewEl.innerHTML = `
    <div class="list-head">Workspaces <span class="muted" id="wsCount"></span>
      <span class="spacer"></span>
      ${recencySelectHtml('wsRecency')}
      ${activeChkHtml('wsActiveOnly')}
      <input id="wsFilter" class="filter wide" placeholder="filter by path or repo…" value="${escapeHtml(data.wsFilter)}" />
    </div>
    <div id="wsGrid" class="ws-grid"></div>`;
  const fi = $('wsFilter');
  fi.addEventListener('input', (e) => { data.wsFilter = e.target.value.trim().toLowerCase(); renderWorkspaceGrid(); });
  wireRecency('wsRecency', renderWorkspaceGrid);
  wireActive('wsActiveOnly', renderWorkspaceGrid);
  renderWorkspaceGrid();
}
function filteredWorkspaces() {
  let list = data.workspaces;
  if (data.recencyMs) list = list.filter(w => withinRecency(w.lastMtime));
  if (data.activeOnly) list = list.filter(w => w.activeCount > 0);
  const f = data.wsFilter;
  if (f) list = list.filter(w =>
    (w.cwd && w.cwd.toLowerCase().includes(f)) ||
    (w.repo && w.repo.toLowerCase().includes(f)) ||
    cwdLeaf(w.cwd).toLowerCase().includes(f));
  return list;
}
function renderWorkspaceGrid() {
  const grid = $('wsGrid'); if (!grid) return;
  const list = filteredWorkspaces();
  const cnt = $('wsCount');
  if (cnt) cnt.textContent = list.length === data.workspaces.length ? `(${list.length})` : `(${list.length} of ${data.workspaces.length})`;
  grid.innerHTML = list.map(w => {
    const color = sessionColor(w.key);
    return `<div class="ws-card" data-key="${escapeHtml(w.key)}">
      <div class="ws-top">
        <span class="dot" style="background:${color}"></span>
        <span class="ws-name" title="${escapeHtml(w.cwd)}">${escapeHtml(cwdLeaf(w.cwd))}</span>
        <span class="spacer"></span>
        ${w.activeCount ? `<span class="badge active">${w.activeCount} active</span>` : ''}
        ${w.tracked ? `<span class="badge track">${w.tracked} tracked</span>` : ''}
      </div>
      <div class="ws-cwd">${escapeHtml(w.cwd)}</div>
      <div class="ws-sub">${w.repo ? escapeHtml(repoLeaf(w.repo)) + ' · ' : ''}${w.sessions.length} session(s) · ${fmtAgo(w.lastMtime)}</div>
    </div>`;
  }).join('') || '<div class="empty">No workspaces match the filter.</div>';
  grid.querySelectorAll('.ws-card').forEach(el =>
    el.addEventListener('click', () => navigate({ view: 'workspace', workspaceKey: el.dataset.key })));
}

/* ---------------- workspace (session list) ---------------- */
function renderWorkspace() {
  const w = workspaceByKey(state.workspaceKey);
  if (!w) { viewEl.innerHTML = '<div class="empty">Workspace not found.</div>'; return; }
  viewEl.innerHTML = `<div class="list-head"><span>${escapeHtml(cwdLeaf(w.cwd))}</span>
     <span class="muted">${escapeHtml(w.cwd)}</span>
     <span class="spacer"></span>${recencySelectHtml('wsSessRecency')}${activeChkHtml('wsSessActive')}</div>
     <div id="sessionCards" class="session-cards"></div>`;
  wireRecency('wsSessRecency', renderWorkspace);
  wireActive('wsSessActive', renderWorkspace);
  renderSessionCards(filteredSessions(w.sessions).slice().sort((a, b) => b.mtime - a.mtime), $('sessionCards'));
}

/* ---------------- tracked ---------------- */
function renderTracked() {
  const list = filteredSessions(trackedSessions()).sort((a, b) => b.mtime - a.mtime);
  viewEl.innerHTML = `<div class="list-head">Tracked sessions <span class="muted">(${list.length})</span>
    <span class="spacer"></span>${recencySelectHtml('trkRecency')}${activeChkHtml('trkActive')}</div>
    <div id="sessionCards" class="session-cards"></div>`;
  wireRecency('trkRecency', renderTracked);
  wireActive('trkActive', renderTracked);
  if (!list.length) {
    $('sessionCards').innerHTML = '<div class="empty">No tracked sessions match the filter.</div>';
    return;
  }
  renderSessionCards(list, $('sessionCards'));
}

/* ---------------- session cards ---------------- */
function sessionCardHtml(s) {
  const color = sessionColor(s.convId);
  const title = data.titles.get(s.convId);
  const count = data.counts.get(s.convId);
  const branch = (s.meta && s.meta.branch) ? escapeHtml(s.meta.branch) + ' · ' : '';
  return `<div class="sess-card ${s.tracked ? 'tracked' : ''}" data-conv="${escapeHtml(s.convId)}">
    <div class="sess-top">
      <span class="dot" style="background:${color}"></span>
      <span class="tag" style="color:${color}">[${shortTag(s.convId)}]</span>
      <span class="badge ${s.active ? 'active' : 'idle'}">${s.active ? 'active' : 'idle'}</span>
      <span class="spacer"></span>
      <button class="track-btn">${s.tracked ? 'tracking' : 'track'}</button>
    </div>
    <div class="sess-title">${title ? escapeHtml(title) : '<span class="muted">(loading title…)</span>'}</div>
    <div class="sess-sub">${branch}<span class="sess-count">${count != null ? count + ' round-trips · ' : ''}</span>${fmtAgo(s.mtime)}</div>
  </div>`;
}
async function renderSessionCards(list, container) {
  container.innerHTML = list.map(sessionCardHtml).join('') || '<div class="empty">No sessions.</div>';
  container.querySelectorAll('.sess-card').forEach(el => {
    const conv = el.dataset.conv;
    el.querySelector('.track-btn').addEventListener('click', (e) => { e.stopPropagation(); toggleTrack(conv); });
    el.addEventListener('click', () => navigate({ view: 'session', convId: conv }));
  });
  const need = list.map(s => s.convId).filter(id => !data.titles.has(id));
  if (need.length) {
    try {
      const res = await window.api.getTitles(need);
      for (const id in res) { const v = res[id] || {}; data.titles.set(id, v.title || null); data.counts.set(id, v.turns); }
      container.querySelectorAll('.sess-card').forEach(el => {
        const conv = el.dataset.conv;
        const t = data.titles.get(conv);
        const tEl = el.querySelector('.sess-title');
        if (tEl) tEl.innerHTML = t ? escapeHtml(t) : '<span class="muted">(no prompt yet)</span>';
        const c = data.counts.get(conv);
        const cEl = el.querySelector('.sess-count');
        if (cEl && c != null) cEl.textContent = c + ' round-trips · ';
      });
    } catch { /* ignore */ }
  }
}

/* ---------------- session detail (turns + request) ---------------- */
async function renderSession() {
  const conv = state.convId;
  const s = sessionById(conv) || { convId: conv, meta: {} };
  const color = sessionColor(conv);
  const m = s.meta || {};
  viewEl.innerHTML = `
    <div class="sd">
      <div class="sd-head">
        <span class="dot" style="background:${color}"></span>
        <span class="tag" style="color:${color}">[${shortTag(conv)}]</span>
        <span id="sdTitle" class="sd-title">${escapeHtml(data.titles.get(conv) || '')}</span>
        <span class="spacer"></span>
        <span id="sdState" class="muted"></span>
        <button id="sdTrack" class="btn">Track</button>
        <button id="sdClear" class="btn" title="clear the round-trip list below">Clear</button>
      </div>
      <div class="sd-sub">${m.cwd ? escapeHtml(m.cwd) : ''}${m.branch ? ' · ' + escapeHtml(m.branch) : ''}${m.copilotVersion ? ' · v' + escapeHtml(m.copilotVersion) : ''}</div>
      <div class="sd-body">
        <div class="sd-turns" id="sdTurns">
          <div class="pane-head" title="Each row = one LLM round-trip (one API call). Rows are grouped by prompt; one prompt = one conversational turn that spans several round-trips until the final answer.">Round-trips <span id="turnsMeta" class="muted"></span><span class="spacer"></span>
            <input id="turnFilter" class="filter" placeholder="filter…" /></div>
          <div id="turnsList"></div>
        </div>
        <div class="splitter" id="sdSplit" title="drag to resize"></div>
        <div class="sd-request">
          <div class="pane-head">Request <span id="detailTitle" class="muted"></span></div>
          <nav id="detailNav"></nav>
          <div id="detailBody"><div class="empty">Click a round-trip on the left<br/>to view its full LLM request.</div></div>
        </div>
      </div>
    </div>`;
  $('sdTrack').addEventListener('click', () => toggleTrack(conv));
  $('sdClear').addEventListener('click', () => { data.turns.set(conv, []); const l = $('turnsList'); if (l) l.innerHTML = ''; updateTurnsMeta(); });
  $('turnFilter').addEventListener('input', (e) => { data.turnFilter = e.target.value.trim().toLowerCase(); reapplyTurnFilter(); });
  data.selectedTurnEl = null;
  updateSessionHeader();
  setupSplitter();

  if (!data.titles.has(conv)) {
    window.api.getTitles([conv]).then(res => {
      const v = (res && res[conv]) || {};
      data.titles.set(conv, v.title || null); data.counts.set(conv, v.turns);
      const el = $('sdTitle'); if (el && state.convId === conv) el.textContent = v.title || '';
    }).catch(() => {});
  }

  let turns = [];
  try { turns = await window.api.getTurns(conv); } catch { /* ignore */ }
  const seen = new Set(turns.map(t => t.serviceRequestId));
  const live = (data.turns.get(conv) || []).filter(t => !seen.has(t.serviceRequestId));
  const all = turns.concat(live);
  data.turns.set(conv, all);
  if (state.view === 'session' && state.convId === conv) renderTurnsList(all);
}

function updateSessionHeader() {
  const s = sessionById(state.convId);
  const st = $('sdState'), tb = $('sdTrack');
  if (st) st.textContent = s ? (s.active ? '● active' : 'idle') : '';
  if (tb) { tb.textContent = (s && s.tracked) ? 'Tracking' : 'Track'; tb.classList.toggle('active', !!(s && s.tracked)); }
}

// Draggable divider between the round-trips list and the request panel.
function setupSplitter() {
  const split = $('sdSplit'), turns = $('sdTurns');
  if (!split || !turns) return;
  const body = split.parentElement;
  const apply = (w) => {
    const bw = body.getBoundingClientRect().width || 1000;
    w = Math.max(240, Math.min(bw - 300, w));
    turns.style.width = w + 'px';
    turns.style.flex = '0 0 auto';
    data.turnsWidth = w;
  };
  if (data.turnsWidth) apply(data.turnsWidth);
  split.addEventListener('mousedown', (e) => {
    e.preventDefault();
    split.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev) => apply(ev.clientX - body.getBoundingClientRect().left);
    const onUp = () => {
      split.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

function renderTurnsList(turns) {
  const list = $('turnsList'); if (!list) return;
  list.innerHTML = '';
  data._lastInter = null;
  for (const rt of turns) {
    if (rt.interactionId !== data._lastInter) {
      data._lastInter = rt.interactionId;
      list.appendChild(interactionHeaderEl(rt));
    }
    list.appendChild(turnRowEl(rt));
  }
  updateTurnsMeta();
  reapplyTurnFilter();
  list.scrollTop = list.scrollHeight;
}
function interactionHeaderEl(rt) {
  const el = document.createElement('div');
  el.className = 'inter-head';
  el.innerHTML = `<span class="ih-icon">▸ prompt</span><span class="ih-prompt">${escapeHtml(rt.prompt || '(new prompt)')}</span>`;
  return el;
}
function turnRowEl(rt) {
  const row = document.createElement('div');
  row.className = 'row';
  row.dataset.svc = rt.serviceRequestId || '';
  const stopClass = rt.stop === 'tool_use' ? 'stop-tool' : 'stop-end';
  let toolsStr = '';
  if (rt.tools && rt.tools.length) {
    const head = rt.tools.slice(0, 4).join(',');
    toolsStr = `(${head}${rt.tools.length > 4 ? ',+' + (rt.tools.length - 4) : ''})`;
  }
  row.innerHTML = `<span class="rturn">#${escapeHtml(rt.turnId)}</span>
    <span class="rtime">${fmtTime(rt.time)}</span>
    <span class="rmodel">${escapeHtml(rt.model)}</span>
    <span class="rout">${fmtTok(rt.outputTokens)} out</span>
    <span class="rstop"><span class="${stopClass}">${escapeHtml(rt.stop + toolsStr)}</span> · <span class="rinit">${escapeHtml(rt.init)}</span></span>`;
  row._rt = rt;
  row.addEventListener('click', () => selectTurn(row, rt));
  return row;
}
function maybeAppendTurn(rt) {
  const list = $('turnsList'); if (!list) return;
  if (list.querySelector(`.row[data-svc="${cssEsc(rt.serviceRequestId)}"]`)) return;
  const stick = list.scrollHeight - list.scrollTop - list.clientHeight < 60;
  if (rt.interactionId !== data._lastInter) {
    data._lastInter = rt.interactionId;
    list.appendChild(interactionHeaderEl(rt));
  }
  const row = turnRowEl(rt);
  if (data.turnFilter && !turnMatches(rt)) row.style.display = 'none';
  list.appendChild(row);
  if (stick) list.scrollTop = list.scrollHeight;
  updateTurnsMeta();
}
function turnMatches(rt) {
  if (!data.turnFilter) return true;
  return [rt.model, rt.stop, rt.init, (rt.tools || []).join(','), String(rt.turnId)].join(' ').toLowerCase().includes(data.turnFilter);
}
function reapplyTurnFilter() {
  const list = $('turnsList'); if (!list) return;
  for (const row of list.querySelectorAll('.row')) row.style.display = turnMatches(row._rt) ? '' : 'none';
}
function updateTurnsMeta() { const m = $('turnsMeta'), l = $('turnsList'); if (m && l) m.textContent = String(l.querySelectorAll('.row').length); }
function selectTurn(row, rt) {
  if (data.selectedTurnEl) data.selectedTurnEl.classList.remove('selected');
  data.selectedTurnEl = row; row.classList.add('selected');
  showRequest(rt);
}

/* ---------------- tracking ---------------- */
function toggleTrack(convId) {
  const s = sessionById(convId); if (!s) return;
  s.tracked = !s.tracked;          // optimistic — instant feedback
  rebuildWorkspaces();
  if (state.view === 'session' && state.convId === convId) updateSessionHeader();
  else render();
  window.api.track(convId, s.tracked);
}

/* ---------------- request rendering ---------------- */
function navLink(label, targetId) { return `<span class="navlink" data-target="${targetId}">${escapeHtml(label)}</span>`; }
function groupHead(title, sub) {
  return `<div class="group-head">${escapeHtml(title)}${sub ? `<span class="gh-sub">${escapeHtml(sub)}</span>` : ''}</div>`;
}
function section(id, title, sub, innerHtml) {
  return `<div class="section" id="${id}">
    <div class="section-h">${escapeHtml(title)}${sub ? `<span class="sh-sub">${escapeHtml(sub)}</span>` : ''}</div>${innerHtml}</div>`;
}
function preContent(text) { return `<pre class="content">${escapeHtml(text)}</pre>`; }
function highlightJson(obj) {
  let json;
  try { json = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2); } catch { json = String(obj); }
  json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g, (m) => {
    let cls = 'j-num';
    if (/^"/.test(m)) cls = /:$/.test(m) ? 'j-key' : 'j-str';
    else if (/^(true|false)$/.test(m)) cls = 'j-bool';
    else if (/^null$/.test(m)) cls = 'j-null';
    return `<span class="${cls}">${m}</span>`;
  });
}
function toolCallsHtml(calls) {
  if (!calls || !calls.length) return '';
  return calls.map(c =>
    `<div class="toolcall"><span class="tcname">▸ ${escapeHtml(c.name)}</span> <span class="mmeta">${escapeHtml(c.id || '')}</span>
      <pre class="json">${highlightJson(c.args)}</pre></div>`
  ).join('');
}
function messageHtml(m, i) {
  // A user message carrying tool_result blocks (one per tool the model called).
  if (m.role === 'user' && m.kind === 'tool_result') {
    const n = m.results.length;
    const preview = m.results.map(r => r.name).join(', ');
    const inner = m.results.map(r => {
      const fail = r.success === false ? ' · <span class="err">FAILED</span>' : '';
      return `<div class="tr-block"><div class="mmeta">tool_result · <b>${escapeHtml(r.name)}</b>${fail} <span>${escapeHtml(r.id || '')}</span></div>${preContent(r.content)}</div>`;
    }).join('');
    return `<details class="msg role-tool" data-idx="${i}">
      <summary><span class="rolelbl">user · tool_result${n > 1 ? ' ×' + n : ''}</span><span class="mhead-preview">${escapeHtml(preview)}</span></summary>${inner}</details>`;
  }
  const roleCls = 'role-' + m.role;
  const preview = (m.content || '').replace(/\s+/g, ' ').slice(0, 110);
  let inner = '', lbl;
  if (m.role === 'assistant') {
    lbl = `assistant · round-trip ${escapeHtml(m.turnId)}`;
    if (m.reasoning) inner += `<div class="mmeta" style="padding:6px 12px 0">content · thinking:</div>` + preContent(m.reasoning);
    if (m.content) inner += `<div class="mmeta" style="padding:6px 12px 0">content · text:</div>` + preContent(m.content);
    if (m.toolCalls && m.toolCalls.length) inner += `<div class="mmeta" style="padding:6px 12px 0">content · tool_use:</div>` + toolCallsHtml(m.toolCalls);
  } else {
    lbl = 'user';
    inner = preContent(m.content);
    if (m.attachments) inner += `<div class="mmeta" style="padding:0 12px 8px">attachments: ${m.attachments}</div>`;
  }
  return `<details class="msg ${roleCls}" data-idx="${i}">
    <summary><span class="rolelbl">${lbl}</span><span class="mhead-preview">${escapeHtml(preview)}</span></summary>${inner}</details>`;
}

async function showRequest(rt) {
  const dt = $('detailTitle'), db = $('detailBody'), dn = $('detailNav');
  if (!db) return;
  if (dt) dt.textContent = `round-trip ${rt.turnId}`;
  if (dn) dn.innerHTML = '';
  db.innerHTML = '<div class="empty">Loading…</div>';
  let req;
  try { req = await window.api.getRequest(rt.convId, rt.serviceRequestId, rt.turnId); }
  catch (e) { db.innerHTML = `<div class="empty err">Failed to load request: ${escapeHtml(e.message)}</div>`; return; }
  renderRequest(req, rt);
}

function renderRequest(req, rt) {
  const db = $('detailBody'), dn = $('detailNav');
  if (!db) return;
  if (!req || !req.found) {
    db.innerHTML = `<div class="empty">Could not reconstruct this request.<br/><span class="muted">service_request_id=${escapeHtml(rt.serviceRequestId || '')} · round-trip=${escapeHtml(rt.turnId)}</span></div>`;
    if (dn) dn.innerHTML = '';
    return;
  }
  const md = req.metadata || {};
  const sess = md.session || {};
  const resp = req.response || {};
  if (dn) {
    dn.innerHTML = [
      navLink('system', 'sec-system'),
      navLink(`messages (${req.messages.length})`, 'sec-messages'),
      navLink('tools', 'sec-tools'),
      navLink('response', 'sec-response'),
      navLink('metadata', 'sec-meta'),
      '<span class="spacer"></span>',
      '<span class="navlink" id="expandAll">expand all</span>',
      '<span class="navlink" id="collapseAll">collapse all</span>',
    ].join('');
  }

  // ---- REQUEST BODY (POST /v1/messages) ----
  const reqGroup = groupHead('Request body', `POST · Anthropic Messages API · model ${md.model || '?'}`);
  const paramsSec = section('sec-params', 'model + params', 'top-level request fields',
    `<div class="kv"><div class="k">model</div><div class="v">${escapeHtml(md.model)}</div></div>
     <div class="note">max_tokens, temperature, top_p, stream and other params are not persisted by the CLI.</div>`);

  const sysLen = req.system ? req.system.length : 0;
  const systemSec = section('sec-system', 'system', sysLen ? `${sysLen} chars · the "system" field` : 'none',
    `<details class="msg role-assistant"><summary><span class="rolelbl">system</span>
       <span class="mhead-preview">${escapeHtml((req.system || '').replace(/\s+/g, ' ').slice(0, 110))}</span></summary>
       ${req.system != null ? preContent(req.system) : '<div class="empty">(no system field)</div>'}</details>`);

  const msgsHtml = req.messages.length ? req.messages.map(messageHtml).join('')
    : '<div class="empty">(round-trip 0 — "messages" holds only your first user message)</div>';
  const messagesSec = section('sec-messages', 'messages', `array of ${req.messages.length} · stateless API, so the whole conversation is resent each round-trip`, msgsHtml);

  const toolsSec = section('sec-tools', 'tools', 'array · not persisted by the CLI',
    `<div class="empty" style="text-align:left;padding:12px;line-height:1.7">The request also carries a top-level <b>tools</b> array — the JSON schema (name, description, input_schema) of every tool offered to the model. The CLI does not persist it, so it can't be shown here (only a raw HTTPS capture would have it).<br/>The tools the model <b>called</b> are the <code>tool_use</code> blocks under Response / assistant messages; their <b>results</b> are the <code>tool_result</code> blocks inside <b>messages</b>.</div>`);

  // ---- RESPONSE BODY ----
  const respGroup = groupHead('Response body', 'returned by the API for this round-trip');
  let respInner = `<div class="kv">
      <div class="k">stop_reason</div><div class="v">${escapeHtml(md.stop || '')}</div>
      <div class="k">usage.output_tokens</div><div class="v">${escapeHtml(md.outputTokens)}</div>
    </div><div class="note">usage.input_tokens and cache tokens are not persisted.</div>`;
  if (resp.reasoning) respInner += `<div class="mmeta" style="padding:8px 12px 0">content · thinking:</div>` + preContent(resp.reasoning);
  if (resp.content) respInner += `<div class="mmeta" style="padding:8px 12px 0">content · text:</div>` + preContent(resp.content);
  if (resp.toolCalls && resp.toolCalls.length) respInner += `<div class="mmeta" style="padding:8px 12px 0">content · tool_use:</div>` + toolCallsHtml(resp.toolCalls);
  const responseSec = section('sec-response', 'Response', `content · stop_reason=${md.stop || '?'}`, respInner);

  // ---- CLI metadata (not part of the wire) ----
  const metaGroup = groupHead('CLI metadata', 'added by the CLI — not part of the wire request/response');
  const kv = [
    ['round-trip', md.turnId], ['interaction', md.interactionId], ['service_request_id', md.serviceRequestId],
    ['request id', md.requestId], ['api call id', md.apiCallId], ['conversation', req.convId],
    ['repo', sess.repository], ['branch', sess.branch], ['cli', sess.copilotVersion], ['time', md.time],
  ].filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => `<div class="k">${escapeHtml(k)}</div><div class="v">${escapeHtml(v)}</div>`).join('');
  const metaSec = section('sec-meta', 'Metadata', null, `<div class="kv">${kv}</div>`);

  db.innerHTML = reqGroup + paramsSec + systemSec + messagesSec + toolsSec + respGroup + responseSec + metaGroup + metaSec;
  if (dn) {
    dn.querySelectorAll('.navlink[data-target]').forEach(el =>
      el.addEventListener('click', () => { const t = document.getElementById(el.dataset.target); if (t) t.scrollIntoView({ block: 'start' }); }));
    const ea = $('expandAll'), ca = $('collapseAll');
    if (ea) ea.addEventListener('click', () => db.querySelectorAll('details.msg').forEach(d => d.open = true));
    if (ca) ca.addEventListener('click', () => db.querySelectorAll('details.msg').forEach(d => d.open = false));
  }
  db.scrollTop = 0;
}

/* ---------------- init + automation hooks ---------------- */
$('brand').addEventListener('click', () => navigate({ view: 'home' }));

(async function init() {
  try { $('rootPath').textContent = await window.api.getRoot(); } catch { /* ignore */ }
  try { data.sessions = await window.api.listSessions(); rebuildWorkspaces(); } catch { /* ignore */ }
  render();
})();

// automation hooks used by the screenshot harness (harmless in normal use)
window.__dash = {
  navigate,
  state: () => state,
  filterWorkspaces(text) {
    const fi = document.getElementById('wsFilter');
    if (fi) fi.value = text;
    data.wsFilter = String(text).toLowerCase();
    renderWorkspaceGrid();
  },
  setRecency(ms) { data.recencyMs = Number(ms); render(); },
  setActiveOnly(on) { data.activeOnly = !!on; render(); },
  openBestWorkspace() {
    const w = data.workspaces.find(x => /LearnAI/i.test(x.key)) || data.workspaces.find(x => x.activeCount > 0) || data.workspaces[0];
    if (w) navigate({ view: 'workspace', workspaceKey: w.key });
  },
  openBestSession() {
    const w = workspaceByKey(state.workspaceKey); if (!w) return;
    const s = w.sessions.find(x => x.convId.startsWith('1b822c54')) || w.sessions.slice().sort((a, b) => b.mtime - a.mtime)[0];
    if (s) navigate({ view: 'session', convId: s.convId });
  },
  clickBestTurn() {
    const rows = document.querySelectorAll('#turnsList .row');
    let target = rows[Math.min(4, rows.length - 1)];
    for (const r of rows) { if (r._rt && r._rt.hasContent) { target = r; break; } }
    if (target) target.click();
  },
  setTurnsWidth(px) {
    const turns = document.getElementById('sdTurns');
    const body = turns && turns.parentElement;
    if (turns && body) {
      const bw = body.getBoundingClientRect().width || 1000;
      const w = Math.max(240, Math.min(bw - 300, px));
      turns.style.width = w + 'px'; turns.style.flex = '0 0 auto'; data.turnsWidth = w;
    }
  },
  trackCurrentAndGoTracked() {
    if (state.view === 'session' && state.convId) {
      const s = sessionById(state.convId);
      if (s && !s.tracked) toggleTrack(state.convId);
    }
    setTimeout(() => navigate({ view: 'tracked' }), 350);
  },
};
