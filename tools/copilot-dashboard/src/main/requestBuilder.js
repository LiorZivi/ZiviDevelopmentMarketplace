'use strict';
// Reconstructs the full outgoing LLM request for one round-trip from a session's
// events.jsonl, joined by service_request_id (fallback: turnId). Returns a
// structured object the renderer turns into navigable HTML.

const fs = require('fs');
const path = require('path');
const os = require('os');

const DEFAULT_ROOT = path.join(os.homedir(), '.copilot', 'session-state');

function readAllRecords(evPath) {
  let text;
  try { text = fs.readFileSync(evPath, 'utf8'); } catch { return []; }
  const out = [];
  for (const line of text.split('\n')) {
    if (!line || line.length < 2) continue;
    try { out.push(JSON.parse(line)); } catch { /* ignore */ }
  }
  return out;
}

function toolResultBody(result) {
  if (!result) return '';
  if (result.detailedContent) return String(result.detailedContent);
  if (result.content) return String(result.content);
  try { return JSON.stringify(result, null, 2); } catch { return String(result); }
}

function mapToolCalls(toolRequests) {
  return (toolRequests || []).map(t => ({
    name: t.name,
    id: t.toolCallId,
    args: t.arguments,
  }));
}

function buildRequest(root, convId, serviceRequestId, turnId) {
  const evPath = path.join(root || DEFAULT_ROOT, convId, 'events.jsonl');
  const records = readAllRecords(evPath);
  const result = {
    convId, serviceRequestId, evPath, found: false,
    system: null, messages: [], response: null, metadata: {},
  };
  if (!records.length) return result;

  // Full system prompt (first system.message).
  const sys = records.find(r => r.type === 'system.message');
  result.system = sys ? (sys.data && sys.data.content != null ? String(sys.data.content) : '') : null;

  // toolCallId -> toolName (to label tool results).
  const toolNames = {};
  for (const r of records) {
    if (r.type === 'tool.execution_start' && r.data && r.data.toolCallId) {
      toolNames[r.data.toolCallId] = r.data.toolName;
    }
  }

  // Locate the target assistant.message.
  let targetIdx = -1;
  if (serviceRequestId) {
    for (let i = 0; i < records.length; i++) {
      const r = records[i];
      if (r.type === 'assistant.message' && r.data && r.data.serviceRequestId === serviceRequestId) { targetIdx = i; break; }
    }
  }
  if (targetIdx < 0 && turnId != null) {
    for (let i = 0; i < records.length; i++) {
      const r = records[i];
      if (r.type === 'assistant.message' && String(r.data && r.data.turnId) === String(turnId)) { targetIdx = i; break; }
    }
  }
  if (targetIdx < 0) return result;

  const target = records[targetIdx];
  const d = target.data || {};
  const iid = d.interactionId;
  result.found = true;

  result.metadata = {
    model: d.model, outputTokens: d.outputTokens, turnId: d.turnId,
    interactionId: iid, serviceRequestId: d.serviceRequestId,
    requestId: d.requestId, apiCallId: d.apiCallId, time: target.timestamp,
    stop: (d.toolRequests && d.toolRequests.length) ? 'tool_use' : 'end_turn',
    session: sessionMeta(records),
  };

  // Request messages: this interaction's records, in order, before the target.
  // Faithful to the wire: user/assistant alternation, and ALL tool results of
  // one assistant turn collapsed into a single user message of tool_result
  // blocks (which is how the Messages API requires them to be sent).
  const messages = [];
  let curTool = null;
  for (let j = 0; j < targetIdx; j++) {
    const r = records[j];
    if (!r.data || r.data.interactionId !== iid) continue;
    if (r.type === 'tool.execution_complete') {
      if (!curTool) { curTool = { role: 'user', kind: 'tool_result', results: [] }; messages.push(curTool); }
      curTool.results.push({
        name: toolNames[r.data.toolCallId] || 'tool',
        id: r.data.toolCallId,
        success: r.data.success,
        content: toolResultBody(r.data.result),
      });
      continue;
    }
    curTool = null;
    if (r.type === 'user.message') {
      messages.push({
        role: 'user', kind: 'text',
        content: r.data.content != null ? String(r.data.content) : '',
        attachments: (r.data.attachments || []).length,
      });
    } else if (r.type === 'assistant.message') {
      messages.push({
        role: 'assistant', turnId: r.data.turnId,
        content: r.data.content != null ? String(r.data.content) : '',
        reasoning: r.data.reasoningText != null ? String(r.data.reasoningText) : '',
        toolCalls: mapToolCalls(r.data.toolRequests),
      });
    }
  }
  result.messages = messages;

  result.response = {
    turnId: d.turnId,
    reasoning: d.reasoningText != null ? String(d.reasoningText) : '',
    content: d.content != null ? String(d.content) : '',
    toolCalls: mapToolCalls(d.toolRequests),
  };

  return result;
}

function sessionMeta(records) {
  const ss = records.find(r => r.type === 'session.start');
  if (!ss) return {};
  const d = ss.data || {};
  const ctx = d.context || {};
  return {
    repository: ctx.repository || null, branch: ctx.branch || null,
    cwd: ctx.cwd || null, copilotVersion: d.copilotVersion || null,
    contextTier: d.contextTier || null,
  };
}

module.exports = { buildRequest, DEFAULT_ROOT };
