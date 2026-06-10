// Build TeamsRemoteSkill.pptx from the markdown deep-dive.
// Theme: Midnight Executive — navy 1E2761, ice blue CADCFC, white FFFFFF, accent gold E8B923
const pptxgen = require("pptxgenjs");

const NAVY    = "1E2761";
const NAVY_D  = "121A4A"; // deeper for backgrounds
const ICE     = "CADCFC";
const WHITE   = "FFFFFF";
const GOLD    = "E8B923";
const MUTED   = "8893B8";
const BODY    = "2A2F4F";

const HEADER_FONT = "Georgia";
const BODY_FONT   = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";  // 10 x 5.625
pres.author = "Copilot CLI / Lior Zivi";
pres.title  = "teams-remote Skill — Deep Dive";

const W = 10, H = 5.625;

// ---------- helpers ----------

function darkBg(slide) {
  slide.background = { color: NAVY_D };
}
function lightBg(slide) {
  slide.background = { color: WHITE };
}

// Top header band on light slides — navy bar with section title + page motif
function header(slide, sectionLabel, slideTitle) {
  // accent gold dot (the visual motif we repeat)
  slide.addShape(pres.shapes.OVAL, { x: 0.5, y: 0.35, w: 0.22, h: 0.22, fill: { color: GOLD }, line: { color: GOLD } });
  slide.addText(sectionLabel.toUpperCase(), {
    x: 0.85, y: 0.28, w: 9, h: 0.35,
    fontFace: BODY_FONT, fontSize: 11, bold: true, color: NAVY, charSpacing: 6, margin: 0
  });
  slide.addText(slideTitle, {
    x: 0.5, y: 0.65, w: 9, h: 0.7,
    fontFace: HEADER_FONT, fontSize: 28, bold: true, color: NAVY, margin: 0
  });
  // thin divider — vertical accent on the left edge
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: H, fill: { color: NAVY }, line: { color: NAVY } });
}

function footer(slide, pageNum, total) {
  slide.addText(`teams-remote · deep dive`, {
    x: 0.5, y: H - 0.35, w: 6, h: 0.25,
    fontFace: BODY_FONT, fontSize: 9, color: MUTED, margin: 0
  });
  slide.addText(`${pageNum} / ${total}`, {
    x: W - 1.0, y: H - 0.35, w: 0.5, h: 0.25,
    fontFace: BODY_FONT, fontSize: 9, color: MUTED, align: "right", margin: 0
  });
}

// Bullets slide — bullets on right; large numbered card on left with section count
function bulletsSlide(section, title, bullets, leftBadge) {
  const s = pres.addSlide();
  lightBg(s);
  header(s, section, title);

  // left card
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.55, w: 3.0, h: 3.5,
    fill: { color: NAVY }, line: { color: NAVY }
  });
  s.addText(leftBadge.num, {
    x: 0.5, y: 1.7, w: 3.0, h: 1.4,
    fontFace: HEADER_FONT, fontSize: 80, bold: true, color: GOLD, align: "center", valign: "middle", margin: 0
  });
  s.addText(leftBadge.label, {
    x: 0.7, y: 3.1, w: 2.6, h: 0.5,
    fontFace: BODY_FONT, fontSize: 12, bold: true, color: ICE, align: "center", charSpacing: 4, margin: 0
  });
  s.addText(leftBadge.sub, {
    x: 0.7, y: 3.6, w: 2.6, h: 1.3,
    fontFace: BODY_FONT, fontSize: 11, color: ICE, align: "center", margin: 0
  });

  // right bullets
  const arr = bullets.map((t, i) => ({
    text: t,
    options: { bullet: { code: "25A0" }, color: BODY, fontSize: 13, breakLine: i !== bullets.length - 1, paraSpaceAfter: 6 }
  }));
  s.addText(arr, {
    x: 3.85, y: 1.55, w: 5.8, h: 3.5,
    fontFace: BODY_FONT, valign: "top", margin: 0
  });
  return s;
}

// Table slide — 2-column table on white card
function tableSlide(section, title, headers, rows) {
  const s = pres.addSlide();
  lightBg(s);
  header(s, section, title);

  const tableRows = [
    headers.map(h => ({
      text: h,
      options: { bold: true, color: WHITE, fill: { color: NAVY }, fontFace: BODY_FONT, fontSize: 12, align: "left", valign: "middle" }
    })),
    ...rows.map(r => r.map((c, i) => ({
      text: c,
      options: {
        color: BODY, fill: { color: i === 0 ? "F1F4FA" : WHITE },
        fontFace: BODY_FONT, fontSize: 11, align: "left", valign: "middle", bold: i === 0
      }
    })))
  ];
  s.addTable(tableRows, {
    x: 0.5, y: 1.55, w: 9.0,
    colW: headers.length === 2 ? [2.6, 6.4] : Array(headers.length).fill(9.0 / headers.length),
    rowH: 0.42,
    border: { type: "solid", pt: 1, color: ICE }
  });
  return s;
}

// Sequence diagram slide — 5 actor columns with lifelines and labelled arrows
function sequenceDiagramSlide(section, title, actors, messages, note) {
  const s = pres.addSlide();
  lightBg(s);
  header(s, section, title);

  const top = 1.45;
  const bottom = note ? 4.85 : 5.10;
  const left = 0.30;
  const right = 9.70;
  const cols = actors.length;
  const colWidth = (right - left) / cols;
  const centers = actors.map((_, i) => left + colWidth * (i + 0.5));

  const actorColors = [GOLD, NAVY, "C0392B", "16A085", "2C5F8A"];

  const boxH = 0.55;
  const boxW = colWidth * 0.92;
  actors.forEach((a, i) => {
    const x = centers[i] - boxW / 2;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: top, w: boxW, h: boxH,
      fill: { color: actorColors[i % actorColors.length] }, line: { color: NAVY_D, width: 0.5 }
    });
    s.addText(a, {
      x, y: top, w: boxW, h: boxH,
      fontFace: BODY_FONT, fontSize: 10, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0
    });
  });

  const lifelineTop = top + boxH;
  const lifelineBottom = bottom;
  centers.forEach(cx => {
    s.addShape(pres.shapes.LINE, {
      x: cx, y: lifelineTop, w: 0, h: lifelineBottom - lifelineTop,
      line: { color: MUTED, width: 0.75, dashType: "dash" }
    });
  });

  const msgTop = lifelineTop + 0.25;
  const msgBottom = lifelineBottom - 0.10;
  const rowH = (msgBottom - msgTop) / Math.max(messages.length, 1);

  messages.forEach((m, i) => {
    const y = msgTop + rowH * (i + 0.5);
    if (m.from === m.to) {
      const cx = centers[m.from];
      const stub = 0.32;
      const color = m.color || NAVY;
      s.addShape(pres.shapes.LINE, { x: cx, y: y - 0.06, w: stub, h: 0,
        line: { color, width: 1.25 } });
      s.addShape(pres.shapes.LINE, { x: cx + stub, y: y - 0.06, w: 0, h: 0.12,
        line: { color, width: 1.25 } });
      s.addShape(pres.shapes.LINE, { x: cx, y: y + 0.06, w: stub, h: 0,
        line: { color, width: 1.25, beginArrowType: "triangle", endArrowType: "none" } });
      s.addText(m.label, {
        x: cx + stub + 0.08, y: y - 0.16, w: 4.5, h: 0.32,
        fontFace: BODY_FONT, fontSize: 9, italic: !!m.italic, color: BODY, valign: "middle", margin: 0
      });
    } else {
      const x1 = centers[m.from];
      const x2 = centers[m.to];
      const xLeft = Math.min(x1, x2);
      const w = Math.abs(x2 - x1);
      const goingRight = x2 > x1;
      const isReturn = m.kind === "return";
      const color = m.color || (isReturn ? MUTED : NAVY);
      s.addShape(pres.shapes.LINE, {
        x: xLeft, y, w, h: 0,
        line: {
          color, width: 1.4,
          dashType: isReturn ? "dash" : "solid",
          beginArrowType: goingRight ? "none" : "triangle",
          endArrowType: goingRight ? "triangle" : "none"
        }
      });
      s.addText(m.label, {
        x: xLeft, y: y - 0.26, w, h: 0.22,
        fontFace: BODY_FONT, fontSize: 9, color: isReturn ? MUTED : BODY,
        italic: !!m.italic, align: "center", margin: 0
      });
    }
  });

  if (note) {
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.4, y: bottom + 0.10, w: 9.2, h: 0.32,
      fill: { color: "F8F2DC" }, line: { color: GOLD, width: 0.75 }
    });
    s.addText(note, {
      x: 0.5, y: bottom + 0.10, w: 9.0, h: 0.32,
      fontFace: BODY_FONT, fontSize: 9.5, italic: true, color: BODY, valign: "middle", margin: 0
    });
  }
  return s;
}

// Section divider — full-bleed navy with gold accent and big roman numeral
function sectionDivider(romanNum, sectionLabel, tagline) {
  const s = pres.addSlide();
  darkBg(s);
  // gold rule
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.2, w: 0.7, h: 0.06, fill: { color: GOLD }, line: { color: GOLD } });
  s.addText(`PART ${romanNum}`, {
    x: 0.6, y: 1.35, w: 9, h: 0.4,
    fontFace: BODY_FONT, fontSize: 14, bold: true, color: GOLD, charSpacing: 8, margin: 0
  });
  s.addText(sectionLabel, {
    x: 0.6, y: 1.85, w: 8.8, h: 1.6,
    fontFace: HEADER_FONT, fontSize: 44, bold: true, color: WHITE, margin: 0
  });
  s.addText(tagline, {
    x: 0.6, y: 3.6, w: 8.8, h: 1.0,
    fontFace: BODY_FONT, italic: true, fontSize: 16, color: ICE, margin: 0
  });
  return s;
}

// Title slide
function titleSlide() {
  const s = pres.addSlide();
  darkBg(s);
  // big gold dot in the upper-right (motif anchor)
  s.addShape(pres.shapes.OVAL, { x: 8.4, y: 0.6, w: 1.2, h: 1.2, fill: { color: GOLD }, line: { color: GOLD } });
  s.addShape(pres.shapes.OVAL, { x: 8.6, y: 0.8, w: 0.8, h: 0.8, fill: { color: NAVY_D }, line: { color: NAVY_D } });
  s.addShape(pres.shapes.OVAL, { x: 8.75, y: 0.95, w: 0.5, h: 0.5, fill: { color: GOLD }, line: { color: GOLD } });

  s.addText("DEEP DIVE", {
    x: 0.6, y: 1.2, w: 9, h: 0.4,
    fontFace: BODY_FONT, fontSize: 14, bold: true, color: GOLD, charSpacing: 10, margin: 0
  });
  s.addText("teams-remote", {
    x: 0.6, y: 1.7, w: 9, h: 1.2,
    fontFace: HEADER_FONT, fontSize: 64, bold: true, color: WHITE, margin: 0
  });
  s.addText("Activation, Stop-Hook Loop, Token Refresh & HTTP Fallback", {
    x: 0.6, y: 3.0, w: 9, h: 0.6,
    fontFace: HEADER_FONT, italic: true, fontSize: 22, color: ICE, margin: 0
  });
  // gold rule
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 3.85, w: 1.2, h: 0.05, fill: { color: GOLD }, line: { color: GOLD } });
  s.addText("A bidirectional Copilot CLI ↔ Microsoft Teams bridge that survives long idle windows by hijacking the Stop hook, refreshing OAuth proactively, and bypassing the CLI's stale bearer with direct-HTTP fallback.", {
    x: 0.6, y: 4.0, w: 8.5, h: 1.1,
    fontFace: BODY_FONT, fontSize: 12, color: ICE, margin: 0
  });
  return s;
}

// =====================================================================
// SECTIONS
// =====================================================================

const SECTIONS = [
  {
    label: "Overview",
    tagline: "What teams-remote is, the three modes it operates in, and why the naïve MCP-only approach falls over.",
    slides: [
      {
        kind: "bullets",
        title: "What it is",
        badge: { num: "01", label: "OVERVIEW", sub: "A long-running Copilot CLI ↔ Teams bridge." },
        bullets: [
          "Slash command /teams-remote shipped by the general-ops plugin in this marketplace.",
          "Bridges the active Copilot CLI session with a chosen Teams channel thread so the user can step away.",
          "Replies posted in Teams are injected as new user prompts; agent progress is posted back as threaded replies.",
          "Hardens the naïve MCP-only approach with proactive OAuth refresh and a direct-HTTP fallback.",
          "Lives at plugins/general-ops/skills/teams-remote/ + scripts/teams-remote/ + scripts/hooks/teams_remote_stop.py."
        ]
      },
      {
        kind: "bullets",
        title: "Three modes of operation",
        badge: { num: "3", label: "MODES", sub: "Activate. Loop while away. End." },
        bullets: [
          "Activation — /teams-remote (no args, name hints, or a channel URL). Posts a root message, persists state, flips away_mode=true.",
          "Away — every turn end the Stop hook nudges the agent into a poll cycle. Replies become injected user prompts.",
          "End — /teams-remote end (or natural-language equivalent, or 'end' typed in Teams). Posts summary, flips away_mode=false, deletes state."
        ]
      },
      {
        kind: "bullets",
        title: "Why it exists",
        badge: { num: "!", label: "MOTIVATION", sub: "Long tasks outlast the user at the keyboard." },
        bullets: [
          "Builds, evals, and refactors often outlast the user's presence at the terminal.",
          "Without a bridge the user must keep the terminal in foreground; with it they steer from a phone.",
          "The naïve approach (just call MCP each tick) breaks after ~1 hour: the CLI caches the OAuth bearer at startup and never reloads it.",
          "Once the cached bearer expires, every MCP call returns -32001 Request timed out. Restarting the CLI is not an option for an unattended session."
        ]
      }
    ]
  },
  {
    label: "Workflow Overview",
    tagline: "End-to-end sequence diagrams: activation, the listen-respond loop, and ending the session.",
    slides: [
      {
        kind: "bullets",
        title: "The five actors",
        badge: { num: "5", label: "ACTORS", sub: "Read every diagram with these columns in mind." },
        bullets: [
          "TEAMS — the user's Teams app on phone or desktop. Source of replies, target of posts.",
          "CLI AGENT — the Copilot CLI's LLM. Runs scripts, executes MCP/HTTP calls from envelopes, makes decisions.",
          "STOP HOOK — teams_remote_stop.py. Fires after every Stop event; reads state; blocks turn end if away_mode=true.",
          "PYTHON SCRIPTS — activate.py / poll.py / ask.py / end.py + teams_transport.py. Emit envelopes; persist state.",
          "TEAMS MCP SERVER — same endpoint either way. Reached via the CLI's MCP client OR via direct HTTP POSTs (after the -32001 flip)."
        ]
      },
      {
        kind: "sequence",
        title: "1. Activation — from /teams-remote to the listening loop",
        actors: ["Teams\n(channel)", "CLI Agent\n(LLM)", "Stop Hook", "activate.py", "Teams MCP Server\n(MCP client / HTTP)"],
        messages: [
          { from: 1, to: 1, label: "user types /teams-remote in CLI", color: GOLD, italic: true },
          { from: 1, to: 3, label: "spawn: activate.py --step run" },
          { from: 3, to: 1, label: "stdout JSON envelope: action=post_root, mcp_call=teams-PostChannelMessage", kind: "return" },
          { from: 1, to: 4, label: "MCP: teams-PostChannelMessage (root msg in chosen channel)" },
          { from: 4, to: 1, label: "{ id, createdDateTime }", kind: "return" },
          { from: 1, to: 3, label: "spawn: activate.py --step finalize --root-message-id <id>" },
          { from: 3, to: 3, label: "write <session>.json: away_mode=true, transport=mcp, own_message_ids=[<id>]" },
          { from: 3, to: 1, label: "stdout: ready", kind: "return" },
          { from: 1, to: 3, label: "spawn: poll.py --step tick --mode idle --long-poll (first tick)" },
          { from: 1, to: 1, label: "turn ends → Stop hook from now on will block & nudge", color: GOLD, italic: true }
        ],
        note: "From this point onward, the Stop hook is armed: every turn end re-injects a poll prompt until /teams-remote end."
      },
      {
        kind: "sequence",
        title: "2. Listen-respond loop — Teams reply → work → post answer → listen again",
        actors: ["Teams\n(channel)", "CLI Agent\n(LLM)", "Stop Hook", "poll.py / ask.py", "Teams MCP Server\n(MCP / HTTP)"],
        messages: [
          { from: 1, to: 1, label: "previous turn ends", color: MUTED, italic: true },
          { from: 2, to: 2, label: "Stop hook fires; reads state; away_mode=true", color: "C0392B" },
          { from: 2, to: 1, label: "{decision: block, reason: 'run poll.py --step tick'}", kind: "return", color: "C0392B" },
          { from: 1, to: 3, label: "spawn: poll.py --step tick --mode idle --long-poll" },
          { from: 3, to: 4, label: "long_poll_replies: GET ListChannelMessageReplies (loops up to 10 min)" },
          { from: 0, to: 4, label: "user posts reply in Teams", color: GOLD, italic: true },
          { from: 4, to: 3, label: "200 OK with new reply payload", kind: "return" },
          { from: 3, to: 1, label: "envelope: inject reply text as next user prompt", kind: "return" },
          { from: 1, to: 1, label: "agent works: runs tools, drafts answer, calls ask.py to post", color: GOLD, italic: true },
          { from: 1, to: 4, label: "MCP / HTTP-fallback: teams-ReplyToChannelMessage (answer)" }
        ],
        note: "This entire round-trip is one Stop-block cycle. Long-poll collapses ~60 forced LLM turns per idle window into ~1."
      },
      {
        kind: "sequence",
        title: "3. End — user types 'end' in Teams (or /teams-remote end in CLI)",
        actors: ["Teams\n(channel)", "CLI Agent\n(LLM)", "Stop Hook", "poll.py / end.py", "Teams MCP Server\n(MCP / HTTP)"],
        messages: [
          { from: 0, to: 0, label: "user types 'end' in Teams thread", color: GOLD, italic: true },
          { from: 4, to: 3, label: "long_poll returns reply: 'end'", kind: "return" },
          { from: 3, to: 3, label: "termination regex match (end / /teams-remote end / /teams-remote-end)", color: "C0392B" },
          { from: 3, to: 1, label: "envelope: emit_end_summary (compose handoff)", kind: "return" },
          { from: 1, to: 3, label: "spawn: end.py --step run --summary '<final summary>'" },
          { from: 3, to: 1, label: "envelope: post_summary, mcp_call=teams-ReplyToChannelMessage", kind: "return" },
          { from: 1, to: 4, label: "MCP / HTTP: teams-ReplyToChannelMessage (summary post)" },
          { from: 4, to: 1, label: "{ messageId }", kind: "return" },
          { from: 1, to: 3, label: "spawn: end.py --step finalize --summary-message-id <id>" },
          { from: 3, to: 3, label: "delete_state(): unlink <session>.json + pending; away_mode now effectively false", color: "16A085" }
        ],
        note: "Next Stop event finds no state file → hook returns no block → CLI sits idle and waits for new user input."
      }
    ]
  },
  {
    label: "Architecture & Components",
    tagline: "The files, the wiring, and where state lives on disk.",
    slides: [
      {
        kind: "bullets",
        title: "Who makes the Teams call?",
        badge: { num: "→", label: "ENVELOPES", sub: "Scripts prepare; the agent executes." },
        bullets: [
          "The Python scripts do NOT open sockets to Teams — they emit JSON envelopes to stdout.",
          "Each envelope names the MCP tool to call (mcp_call) and, for poll.py, an http_fallback sibling.",
          "The agent (Copilot CLI's LLM) reads the envelope and executes the actual MCP tool call — or, after the transport flip, the direct HTTP POST.",
          "Scripts own state, dedup, mention markup, termination regex, and stripping mcp_call once transport==\"http\".",
          "Only exception: poll.py calls teams_transport.long_poll_replies directly for the 10-min blocking GET loop. Outbound posts are always envelope-only.",
          "Today activate/ask/end emit MCP-only envelopes; only poll.py ships the dual-transport contract. Adding http_fallback to the others is a follow-up."
        ]
      },
      {
        kind: "bullets",
        title: "Files on disk",
        badge: { num: "8", label: "FILES", sub: "Skill prompt + 4 scripts + transport + hook + state lib." },
        bullets: [
          "skills/teams-remote/SKILL.md — the prompt the agent reads when invoked.",
          "scripts/teams-remote/activate.py — two-step activation handshake (emits envelopes).",
          "scripts/teams-remote/poll.py — heart of the loop; emits envelopes + calls long_poll_replies directly.",
          "scripts/teams-remote/ask.py — emits a post_question envelope for outbound questions.",
          "scripts/teams-remote/end.py — emits a post_summary envelope + teardown.",
          "scripts/teams-remote/teams_transport.py — pure-stdlib transport (refresh, SSE, HTTP fallback, long-poll).",
          "scripts/hooks/teams_remote_stop.py + scripts/lib/state.py — Stop-hook gate + schema-versioned state."
        ]
      },
      {
        kind: "bullets",
        title: "Plugin wiring",
        badge: { num: "↔", label: "WIRING", sub: "Stop hook + dual MCP transport discovery." },
        bullets: [
          "hooks/hooks.json registers the Stop hook with matcher: \"\" — fires on every Stop event.",
          "Hook command: python \"${CLAUDE_PLUGIN_ROOT}/scripts/hooks/teams_remote_stop.py\".",
          "Two MCP transports auto-discovered: user OAuth (~/.copilot/mcp-oauth-config/*.json) and agency loopback proxy (%TEMP%\\copilot-mcp-*.json).",
          "Required MCP tools: teams-ListTeams, teams-ListChannels, teams-PostChannelMessage, teams-ReplyToChannelMessage, teams-ListChannelMessageReplies."
        ]
      },
      {
        kind: "bullets",
        title: "State directory (v1.8.0+)",
        badge: { num: "v3", label: "SCHEMA", sub: "Per-session JSON, only present while away_mode=true." },
        bullets: [
          "Path: ~/.copilot/session-state/<session-id>/plugins/general-ops/teams-remote/ — co-located with the CLI's own session-state, per-session by construction.",
          "Files: state.json (live state), pending.json (out-queue), activate-pending.json (mid-handshake only).",
          "Hook-crash log stays MACHINE-LEVEL at <tempdir>/general-ops/hook-error.log (hooks can crash before they know the session_id).",
          "COPILOT_SESSION_ROOT env var (or state.set_session_root(path)) redirects the root for tests / CI.",
          "Schema version is 3 — load_state returns None for any other version (stale state treated as 'no session').",
          "Pre-1.8 layout (deprecated): flat <tempdir>/general-ops/teams-remote/<session-id>.json — required globbing, leaked across sessions."
        ]
      },
      {
        kind: "table",
        title: "State lifecycle — when state.json appears and disappears",
        headers: ["Event", "What happens to state.json"],
        rows: [
          ["/teams-remote (activate finalize)", "CREATED — schema_version=3, away_mode=true, transport=\"mcp\", own_message_ids=[<root-id>]."],
          ["Each poll tick / process / record-*", "REWRITTEN atomically — write *.tmp then os.replace (no torn reads)."],
          ["ask.py / end.py finalize step", "REWRITTEN — appends posted message id to own_message_ids."],
          ["First refresh / -32001 / 401 / AADSTS*", "REWRITTEN — transport flips \"mcp\" → \"http\" (sticky, never flips back)."],
          ["/teams-remote end (or NL end / 'end' typed in Teams)", "DELETED — delete_state() unlinks the file; empty per-session dir left for the CLI to clean."],
          ["Schema bump (v3 → v4 in the future)", "Old file orphaned — load_state returns None, hook treats as 'no session'."]
        ]
      }
    ]
  },
  {
    label: "Activation Flow",
    tagline: "Two-step handshake that posts a root message and arms the Stop hook.",
    slides: [
      {
        kind: "bullets",
        title: "Two-step handshake",
        badge: { num: "1+2", label: "ACTIVATE", sub: "run → execute MCP root post → finalize." },
        bullets: [
          "Step 1 — activate.py --step run: resolves team/channel ids; emits already_active, need_input, error, or post_root.",
          "Agent executes the root-post MCP call and captures the returned message id and ISO timestamp.",
          "Step 2 — activate.py --step finalize --root-message-id <id> --created-iso <ts>: persists state and emits 'ready'.",
          "Optional --user-id <guid> enables the self-mention notification hack (every reply mentions the away user → push notification fires).",
          "Initial state: transport='mcp', away_mode=true, last_processed_id='0', own_message_ids=[<root-id>]."
        ]
      },
      {
        kind: "bullets",
        title: "Post-activation invariants",
        badge: { num: "✓", label: "INVARIANTS", sub: "What is now true on disk and what must happen next." },
        bullets: [
          "away_mode=true is persisted — the Stop hook will start blocking turn endings from now on.",
          "transport defaults to 'mcp'; flips to 'http' on first refresh / -32001 / 401 / AADSTS*.",
          "own_message_ids already contains the root post so the poll loop never echoes it as user input.",
          "Post-activation rule: at the start of the NEXT turn the agent's only action is poll.py --step tick --mode idle. No 'how can I help?' prompt."
        ]
      }
    ]
  },
  {
    label: "The Idle-Poll Loop",
    tagline: "Long-poll first, short-poll fallback, dual-transport envelopes on every tick.",
    slides: [
      {
        kind: "bullets",
        title: "Long-poll vs short-poll",
        badge: { num: "60×", label: "LONG-POLL", sub: "Collapse ~60 forced LLM turns into ~1 per idle window." },
        bullets: [
          "Long-poll (preferred): poll.py --step tick --mode idle --long-poll blocks inside the subprocess for up to 10 minutes.",
          "Returns one poll_result envelope with replies already fetched — no separate MCP call needed.",
          "Short-poll (fallback): emits mcp_call + mcp_args + sleep_seconds; agent must execute and then call --step process.",
          "Long-poll collapses ~60 forced LLM turns per idle window down to ~1 — huge token-cost reduction.",
          "Fallback used only when neither OAuth disk config nor agency proxy is discoverable."
        ]
      },
      {
        kind: "table",
        title: "Action branching after --step process",
        headers: ["Action", "What the agent must do"],
        rows: [
          ["inject", "Each unread reply becomes a user prompt; post the ack_template in PARALLEL with the first real-work tool call."],
          ["terminate", "User typed 'end' / '/teams-remote end' / '/teams-remote-end' in Teams → run End Flow with reason remote-triggered."],
          ["heartbeat", "Periodic 'still working' post; record its id back via --record-own-id <id> --record-own-kind heartbeat."],
          ["continue", "Nothing actionable; loop again. If truncated:true, shorten pollIntervalSeconds."],
          ["poll_result", "Long-poll only — pipe straight into --step process; the resulting action is one of the four above."]
        ]
      },
      {
        kind: "bullets",
        title: "Envelopes carry both transports",
        badge: { num: "2×", label: "ENVELOPE", sub: "MCP call + http_fallback sibling on every tick." },
        bullets: [
          "Every tick emits mcp_call + mcp_args AND an http_fallback sibling — agent picks based on top-level transport flag.",
          "transport: 'mcp' (default) or 'http' (sticky after a flip).",
          "http_fallback shape varies: auth='bearer' for OAuth disk (fully-qualified teams-… tool name) or auth='none' for agency loopback proxy (prefix stripped)."
        ]
      }
    ]
  },
  {
    label: "Stop-Hook Integration",
    tagline: "How an end-of-turn Stop event becomes another idle-poll cycle.",
    slides: [
      {
        kind: "bullets",
        title: "Where it sits in the agentic loop",
        badge: { num: "Stop", label: "HOOK EVENT", sub: "Fires when the model returns end_turn." },
        bullets: [
          "The Copilot CLI emits a Stop event when the model returns end_turn — see CopilotCliAgenticLoopAndHooks.md.",
          "A Stop hook can return {\"decision\": \"block\", \"reason\": \"...\"} on stdout to FORCE another turn.",
          "The reason text is delivered to the model as the next user prompt.",
          "teams-remote registers exactly such a Stop hook with empty matcher so it runs after every turn."
        ]
      },
      {
        kind: "bullets",
        title: "What teams_remote_stop.py does (v1.8.0+)",
        badge: { num: "↧", label: "HOOK BODY", sub: "Read session_id from stdin, look up that session's state, decide." },
        bullets: [
          "Reads the JSON payload the CLI pipes on stdin and extracts the firing session's session_id.",
          "Calls load_state(session_id) directly — per-session storage means there's exactly one path it could exist at: ~/.copilot/session-state/<session-id>/plugins/general-ops/teams-remote/state.json.",
          "If no state file for THIS session, or away_mode != true → return 0 with no stdout. The CLI sees no decision; the turn ends normally.",
          "If THIS session is in away mode → emits {\"decision\": \"block\", \"reason\": \"<idle-poll instructions>\"}. The CLI forces another turn.",
          "Fail-open on missing/malformed stdin → no block. Top-level try/except logs to hook-error.log. A hook crash never blocks the user.",
          "No globbing, no _active_away_session() helper — session isolation is enforced by the storage layout itself."
        ]
      },
      {
        kind: "bullets",
        title: "What the block reason tells the agent",
        badge: { num: "→", label: "BLOCK REASON", sub: "An imperative the agent must obey." },
        bullets: [
          "Reminds it the session is away_mode=true and gives the EXACT command sequence.",
          "Step 1: poll.py --step tick --mode idle --long-poll --session-id <SID>.",
          "Step 2: pipe the poll_result envelope into --step process and act on inject / terminate / heartbeat / continue.",
          "Fallback guidance included: drop --long-poll, add --with-sleep, switch to http_fallback if transport==http or on -32001/401/AADSTS.",
          "Only /teams-remote end flips away_mode=false — this is the ONLY way out of the loop."
        ]
      },
      {
        kind: "bullets",
        title: "How the loop never ends — two halves working together",
        badge: { num: "1+2", label: "LOOP DRIVER", sub: "Long-poll waits efficiently; Stop hook causes the next turn." },
        bullets: [
          "HALF 1 — long-poll keeps the CURRENT subprocess productive: poll.py --long-poll blocks for up to 10 min inside teams_transport.long_poll_replies (one LLM turn = up to 10 minutes of wall-clock).",
          "HALF 2 — Stop hook causes the NEXT turn to exist: when the agent stops generating, CLI fires Stop, hook returns { decision: 'block', reason: ... }, CLI delivers reason as a synthetic user prompt — turn N+1 starts.",
          "EXIT: only end.py --step finalize calls delete_state(). Next Stop sees no file → hook returns {} → CLI idles, human regains control.",
          "Without HALF 2, loop dies after one tick — agent finishes turn naturally, CLI idles.",
          "Without HALF 1, loop still works but becomes a busy-wait — fresh LLM turn every minute.",
          "Hook is wrapped in top-level try/except → falls back to {} on any crash. A hook failure must NEVER take the terminal down."
        ]
      },
      {
        kind: "sequence",
        title: "Loop persistence — Half 1 (long-poll) + Half 2 (Stop hook)",
        actors: ["Copilot CLI\n(host)", "Agent\n(LLM)", "Stop Hook", "poll.py", "Teams MCP\nServer"],
        messages: [
          { from: 0, to: 1, label: "turn N starts — synthetic prompt: 'run poll.py --step tick'", color: GOLD, italic: true },
          { from: 1, to: 3, label: "spawn poll.py --step tick --long-poll" },
          { from: 3, to: 4, label: "long_poll_replies — internal short GETs (HALF 1: blocks up to 10 min)" },
          { from: 4, to: 3, label: "reply OR heartbeat", kind: "return" },
          { from: 3, to: 1, label: "envelope (subprocess returns)", kind: "return" },
          { from: 1, to: 1, label: "agent processes envelope, maybe posts, then stops generating", italic: true },
          { from: 0, to: 2, label: "CLI fires Stop event (built-in)", color: "C0392B" },
          { from: 2, to: 2, label: "load_state(session_id)", color: "C0392B" },
          { from: 2, to: 0, label: "{ decision: 'block', reason: 'run poll.py --step tick…' }", kind: "return", color: "C0392B" },
          { from: 0, to: 1, label: "HALF 2: turn N+1 starts with reason as synthetic user prompt → loop", color: GOLD, italic: true }
        ],
        note: "EXIT path: when state file is gone (after /teams-remote end), hook returns {} → CLI returns to idle prompt → loop ends, human regains control."
      }
    ]
  },
  {
    label: "Bypassing -32001",
    tagline: "Why MCP fails after ~1 hour, and the two-part fix.",
    slides: [
      {
        kind: "bullets",
        title: "Why MCP calls eventually fail",
        badge: { num: "-32001", label: "THE BUG", sub: "Cached bearer never reloads." },
        bullets: [
          "The Copilot CLI loads the Teams MCP OAuth bearer ONCE at process startup and caches it in memory.",
          "Bearer lifetime is typically ~1 hour. After that, the MCP server rejects the call.",
          "Surfaced as: McpError -32001: Request timed out (sometimes 401 or AADSTS*).",
          "Restarting the CLI is not an option for an unattended away session."
        ]
      },
      {
        kind: "bullets",
        title: "Proactive refresh — ensure_fresh_token",
        badge: { num: "10m", label: "REFRESH SKEW", sub: "Refresh 10 minutes before expiry, write back atomically." },
        bullets: [
          "At the top of every poll.py --step tick, find_teams_mcp_config() locates ~/.copilot/mcp-oauth-config/<name>.tokens.json.",
          "Match is by serverUrl containing 'mcp_TeamsServerV1' — robust against renamed config files.",
          "ensure_fresh_token checks expiresAt - now. If ≤ 600 s, POSTs a refresh_token grant to login.microsoftonline.com.",
          "New tokens written back atomically with camelCase keys (accessToken / refreshToken / expiresAt) so the CLI's on-disk file stays in sync.",
          "Returns {refreshed: True} — the loop reacts by flipping state to HTTP."
        ]
      },
      {
        kind: "bullets",
        title: "The HTTP fallback flip",
        badge: { num: "→HTTP", label: "STICKY FLIP", sub: "Once on HTTP, stay on HTTP." },
        bullets: [
          "On refreshed=True, poll.py sets state['transport']='http' and persists immediately.",
          "From that tick on, every envelope carries transport:'http' and the agent executes http_fallback instead of mcp_call.",
          "--step record-mcp-error --code -32001 does the same flip reactively after an MCP call already returned the dreaded error.",
          "Once on HTTP, NEVER flip back. The CLI's cached bearer never catches up; flipping back just reproduces the bug."
        ]
      },
      {
        kind: "table",
        title: "Two HTTP fallback shapes",
        headers: ["Discovery", "auth", "Tool name", "Authorization header"],
        rows: [
          ["OAuth disk (user-managed)", "bearer", "teams-<Verb> (full)", "Bearer <accessToken from tokens file>"],
          ["Agency loopback proxy", "none", "<Verb> (prefix stripped)", "(none — proxy injects upstream)"]
        ]
      },
      {
        kind: "bullets",
        title: "SSE parsing — non-negotiables",
        badge: { num: "3×", label: "TRIPLE NESTED", sub: "json.loads three times. Never regex." },
        bullets: [
          "Both calls send Content-Type: application/json and Accept: application/json, text/event-stream.",
          "The response body is SSE-formatted with TRIPLE-nested JSON inside data: lines.",
          "Parse via teams_transport.parse_sse_response — never regex (Unicode escapes \\u0022 will silently break you).",
          "An SSE parse failure is treated as an ERROR, not 'no replies'. Silently dropping replies is the worst-case bug."
        ]
      }
    ]
  },
  {
    label: "Session State Storage",
    tagline: "What is persisted, when it's read, when it's written, and when it's reaped.",
    slides: [
      {
        kind: "table",
        title: "Schema (v3) — key fields",
        headers: ["Key", "Purpose"],
        rows: [
          ["schema_version", "Always 3; mismatched versions load as None (treated as 'no session')."],
          ["session_id", "The Copilot CLI session id this state belongs to."],
          ["away_mode", "Boolean — true means the Stop hook will block. Only end.py flips it false."],
          ["transport", "'mcp' (default) or 'http' (sticky after refresh / -32001)."],
          ["team_id / channel_id", "Resolved Graph ids the loop posts into."],
          ["root_message_id / root_created_iso", "Activation post id; threaded replies hang under it."],
          ["own_message_ids", "Every id we've authored — ack, heartbeat, progress, ask, end summary."],
          ["last_processed_id", "Decimal-string max id processed; numeric floor against clock-skew replays."]
        ]
      },
      {
        kind: "bullets",
        title: "When state is written",
        badge: { num: "W", label: "WRITES", sub: "Every meaningful step persists." },
        bullets: [
          "activate.py --step finalize — initial save with away_mode=true, transport='mcp', root post recorded.",
          "Top of every poll.py --step tick — after ensure_fresh_token may have flipped transport to 'http'.",
          "--step process — after each successful reply: appends to own_message_ids and bumps last_processed_id.",
          "--step record-own — explicit add-to-own_message_ids after the agent posts an ad-hoc reply.",
          "--step record-mcp-error — flips transport='http' and increments mcp_timeout_streak.",
          "ask.py --step finalize — records the question id we just posted."
        ]
      },
      {
        kind: "bullets",
        title: "When state is read",
        badge: { num: "R", label: "READS", sub: "Stop hook + every poll step + end.py." },
        bullets: [
          "teams_remote_stop.py — every Stop event scans the directory and picks the first away_mode=true session.",
          "Every poll.py step starts with load_state(session_id).",
          "end.py reads it once to compose the summary, then deletes the file."
        ]
      },
      {
        kind: "bullets",
        title: "Lifetime & cleanup (v1.8.0+)",
        badge: { num: "↺", label: "PER-SESSION", sub: "State dies with the session." },
        bullets: [
          "Files live until end.py --step finalize calls delete_state() — that's the only deliberate teardown.",
          "Per-session state-dir means cleanup is the CLI's job (it owns ~/.copilot/session-state/<sid>/). When the CLI prunes a session dir, our state goes with it — no separate reaper needed.",
          "Schema-version mismatches are inert: a v4 bump simply makes any leftover v3 file return None from load_state — the hook treats it as 'no session'.",
          "Pre-1.8 had run_stale_cleanup() reaping >24h files from the flat machine-level dir; that helper was deleted in v1.8 because per-session lifetimes made it dead code.",
          "Restart-after-crash: /teams-remote starts a FRESH activation; there is no resume."
        ]
      }
    ]
  },
  {
    label: "Self-Filter & Dedup",
    tagline: "Two layers ensure the agent never echoes itself or replays old replies.",
    slides: [
      {
        kind: "bullets",
        title: "Two-layer defence against echo loops",
        badge: { num: "2", label: "LAYERS", sub: "Id-set membership + numeric floor." },
        bullets: [
          "Layer 1 — own_message_ids set. Every id we post (root, asks, acks, heartbeats, progress, end summary) goes in. Poller skips any matching reply.",
          "Layer 2 — last_processed_id numeric floor. Each processed reply id is parsed as int; max persisted. Future ticks skip any reply where int(reply_id) ≤ last_processed_id.",
          "Why two layers: clock-skewed Graph timestamps can re-surface 'older' replies; numeric ordering on monotonic id space is stronger than timestamp comparison.",
          "Filtering is by ID, never by sender — the agent posts on behalf of the signed-in user, so from.userId is identical for inbound and outbound."
        ]
      },
      {
        kind: "bullets",
        title: "Termination detection",
        badge: { num: "/end", label: "REGEX", sub: "Inbound text matched against a tight pattern." },
        bullets: [
          "Inbound replies matched against ^\\s*(end|/teams-remote\\s+end|/teams-remote-end)\\s*$ (case-insensitive).",
          "A match emits action:'terminate' with reason remote-triggered.",
          "The agent must run end.py --step run --reason remote-triggered next, not pretend to keep working."
        ]
      }
    ]
  },
  {
    label: "Posting Rules",
    tagline: "Three pieces every Teams post must carry. Plain text only for ad-hoc.",
    slides: [
      {
        kind: "bullets",
        title: "Every Teams post needs three pieces",
        badge: { num: "3", label: "RULE", sub: "Prefix + in-content @mention + mentions array." },
        bullets: [
          "Visible prefix — content begins with the literal string 'Copilot agent message:' so the user can distinguish agent posts from their own.",
          "In-content self-@mention — content begins with @DisplayName (literal at-sign + away user's display name).",
          "mentions argument — JSON-stringified [{displayName, id, type:'user'}] matching the in-content mention.",
          "Forgetting mentions is the #1 cause of 'you didn't ping me' — without it the away user gets no push notification."
        ]
      },
      {
        kind: "bullets",
        title: "Plain text only for ad-hoc posts",
        badge: { num: "TXT", label: "AD-HOC", sub: "Never raw HTML when the agent composes by hand." },
        bullets: [
          "Set contentType:'text' on teams-ReplyToChannelMessage / teams-PostChannelMessage / teams-SendMessageToChat.",
          "The MCP server expands @DisplayName into proper Teams mention markup automatically when mentions is present — do NOT author <at>...</at> tags.",
          "Never author raw HTML (<p>, <br>, <ul>, <b>, <at>, <div>, etc.) — Teams renders most hand-rolled HTML inconsistently.",
          "Use \\n for line breaks, '- ' for bullets, *asterisks* or ALL-CAPS sparingly for emphasis.",
          "The HTML envelopes from activate.py / end.py / _apply_mention_hack use a tiny controlled subset — they are the only sanctioned HTML on the wire."
        ]
      },
      {
        kind: "bullets",
        title: "Acknowledge in parallel with starting work",
        badge: { num: "∥", label: "PARALLEL", sub: "Hung MCP must never block forward progress." },
        bullets: [
          "When the poll loop returns 'inject', post the ack and the first real-work tool call as PARALLEL tool calls in a single response.",
          "This guarantees a hung MCP can never block forward progress.",
          "The ack should paraphrase what was understood in ≤2 sentences — proves the agent actually read the message."
        ]
      }
    ]
  },
  {
    label: "End Flow",
    tagline: "Two-step teardown. Reason codes. The termination matrix.",
    slides: [
      {
        kind: "bullets",
        title: "Two-step teardown",
        badge: { num: "1+2", label: "END", sub: "run → execute MCP/HTTP summary → finalize." },
        bullets: [
          "Step 1 — end.py --step run --reason <code>: composes a summary, emits post_summary (or no_session if state is missing).",
          "The agent executes the MCP/HTTP summary post.",
          "Step 2 — end.py --step finalize: deletes the state file; emits ok.",
          "If the summary post fails, STILL proceed to step 2 — the session is logically closed regardless.",
          "After ok, a future /teams-remote starts a FRESH activation; there is no resume."
        ]
      },
      {
        kind: "table",
        title: "Reason codes",
        headers: ["--reason", "When it's used"],
        rows: [
          ["user-invoked", "Default. User typed /teams-remote end or a natural-language end phrase in the CLI."],
          ["remote-triggered", "Idle-poll matched a termination string in a Teams reply."],
          ["session-ended", "Reserved for future use; currently unset by any caller."]
        ]
      },
      {
        kind: "table",
        title: "Termination matrix",
        headers: ["Trigger", "How it's handled"],
        rows: [
          ["User runs /teams-remote end in CLI", "End Flow with reason user-invoked."],
          ["User replies 'end' / '/teams-remote end' / '/teams-remote-end' in Teams", "Poll returns 'terminate' → End Flow with reason remote-triggered."],
          ["CLI session exits without cleanup", "No summary; stale state reaped on the next activation."]
        ]
      }
    ]
  },
  {
    label: "Edge Cases & Hardening",
    tagline: "What can go wrong in discovery, transport, and ambiguity.",
    slides: [
      {
        kind: "bullets",
        title: "Configuration discovery failures",
        badge: { num: "?", label: "DISCOVERY", sub: "Tolerant fallbacks; never crash the loop." },
        bullets: [
          "find_teams_mcp_config() returns None when no OAuth disk config exists yet → loop logs one-line stderr note and emits envelopes WITHOUT http_fallback. Stays on MCP.",
          "find_agency_teams_proxy() scans %TEMP%\\copilot-mcp-*.json newest-first; trusts only loopback URLs (127.0.0.1 / localhost).",
          "If both fail, MCP-only operation continues — refresh and HTTP fallback are simply unavailable.",
          "A long enough idle window in that state will eventually hit the -32001 cliff."
        ]
      },
      {
        kind: "bullets",
        title: "Agency proxy may be read-only",
        badge: { num: "RO", label: "PROXY CAVEAT", sub: "Verify tools/list before activating." },
        bullets: [
          "Some agency-hosted Teams MCP loopback proxies expose ONLY READ tools — no PostChannelMessage / ReplyToChannelMessage.",
          "Always verify tools/list against the proxy before activating.",
          "If write tools are missing, the skill must REFUSE to activate rather than silently degrade."
        ]
      },
      {
        kind: "bullets",
        title: "One-shot scripts vs the loop",
        badge: { num: "1×", label: "ONE-SHOT", sub: "activate.py / ask.py / end.py still MCP-only." },
        bullets: [
          "activate.py, ask.py, and end.py currently emit MCP-only envelopes (no http_fallback sibling).",
          "The agent retries them once on -32001; they are rarely on the long-running hot path.",
          "A future PR will add HTTP fallback siblings to these too for full symmetry."
        ]
      },
      {
        kind: "bullets",
        title: "What can't be guessed",
        badge: { num: "✗", label: "STRICT", sub: "Ambiguity is an error, not a guess." },
        bullets: [
          "Team/channel ambiguity (multiple matches by name) is an ERROR, not a guess. The skill surfaces it for human resolution.",
          "A reply with a non-numeric id is a hard failure of an upstream invariant.",
          "The numeric last_processed_id floor only works because Teams reply ids are monotonic decimal strings."
        ]
      }
    ]
  },
  {
    label: "Key Takeaways",
    tagline: "Why the design works, and the operational rules to remember.",
    slides: [
      {
        kind: "bullets",
        title: "Why the design works",
        badge: { num: "✓", label: "DESIGN", sub: "Hook hijack + sticky HTTP + dedup = robust loop." },
        bullets: [
          "The Stop hook turns 'end of turn' into 'end of one cycle of the idle loop' — keeps the agent alive without a separate daemon.",
          "Proactive refresh + sticky HTTP fallback dodges the CLI's most painful long-session bug (-32001 from a stale cached bearer).",
          "Schema-versioned per-session state keeps multi-session and multi-version installs from clobbering each other.",
          "Two-layer dedup (id-set + numeric floor) prevents the agent from ever talking to itself, even under clock skew."
        ]
      },
      {
        kind: "bullets",
        title: "Operational rules to remember",
        badge: { num: "5", label: "RULES", sub: "Memorize these or be debugging at 2am." },
        bullets: [
          "Only /teams-remote end flips away_mode=false — nothing else escapes the Stop-hook block.",
          "Once transport=='http', NEVER flip back; the CLI's cached bearer will not catch up.",
          "Every Teams post: prefix + @DisplayName + mentions array. All three. Always.",
          "An SSE parse None is an ERROR, never 'no messages' — silently empty replies is the worst-case bug.",
          "Long-poll first; fall back to short-poll only when transport discovery fails."
        ]
      }
    ]
  }
];

// ---------- BUILD ----------
const ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII"];

const slideQueue = [];
slideQueue.push({ kind: "title" });
SECTIONS.forEach((sec, i) => {
  slideQueue.push({ kind: "divider", section: sec, idx: i });
  sec.slides.forEach(sl => slideQueue.push({ kind: "content", section: sec, slide: sl }));
});
const TOTAL = slideQueue.length;

slideQueue.forEach((item, idx) => {
  const pageNum = idx + 1;
  let slide;
  if (item.kind === "title") {
    slide = titleSlide();
  } else if (item.kind === "divider") {
    slide = sectionDivider(ROMAN[item.idx], item.section.label, item.section.tagline);
  } else if (item.slide.kind === "bullets") {
    slide = bulletsSlide(item.section.label, item.slide.title, item.slide.bullets, item.slide.badge);
  } else if (item.slide.kind === "table") {
    slide = tableSlide(item.section.label, item.slide.title, item.slide.headers, item.slide.rows);
  } else if (item.slide.kind === "sequence") {
    slide = sequenceDiagramSlide(item.section.label, item.slide.title, item.slide.actors, item.slide.messages, item.slide.note);
  }
  if (item.kind !== "title") {
    footer(slide, pageNum, TOTAL);
  }
});

pres.writeFile({ fileName: "plugins/general-ops/learn/TeamsRemoteSkill.pptx" }).then(f => {
  console.log("WROTE:", f, "slides:", TOTAL);
});
