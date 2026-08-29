#!/usr/bin/env python3
"""Render a standalone PR/local-change HTML explainer from a structured JSON spec."""

from __future__ import annotations

import argparse
import html
import json
import re
import textwrap
from pathlib import Path
from typing import Any


VALID_TONES = {"normal", "neutral", "problem", "success", "config"}
VALID_MESSAGE_KINDS = {"call", "return"}


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return slug or "Change"


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object.")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array.")
    return value


def require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string.")
    return value.strip()


def tone(value: Any, default: str = "neutral") -> str:
    candidate = str(value or default).lower()
    return candidate if candidate in VALID_TONES else default


def wrap_lines(value: Any, width: int, max_lines: int = 3) -> list[str]:
    text = " ".join(str(value or "").split())
    if not text:
        return [""]
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "..."
    return lines


def svg_text(
    lines: list[str],
    x: float,
    y: float,
    class_name: str,
    anchor: str = "middle",
    line_height: int = 16,
) -> str:
    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        tspans.append(f'<tspan x="{x:.1f}" dy="{dy}">{escape(line)}</tspan>')
    return (
        f'<text class="{escape(class_name)}" x="{x:.1f}" y="{y:.1f}" '
        f'text-anchor="{escape(anchor)}">{"".join(tspans)}</text>'
    )


def validate_flow(flow: dict[str, Any], path: str, expected_zone_tone: str) -> None:
    require_text(flow.get("title"), f"{path}.title")
    overview = require_object(flow.get("overview"), f"{path}.overview")
    steps = require_list(overview.get("steps"), f"{path}.overview.steps")
    if len(steps) < 2:
        raise ValueError(f"{path}.overview.steps must contain at least two steps.")
    for index, step_value in enumerate(steps):
        step = require_object(step_value, f"{path}.overview.steps[{index}]")
        require_text(step.get("actor"), f"{path}.overview.steps[{index}].actor")
        require_text(step.get("title"), f"{path}.overview.steps[{index}].title")
        require_text(step.get("detail"), f"{path}.overview.steps[{index}].detail")

    sequence = require_object(flow.get("sequence"), f"{path}.sequence")
    participants = require_list(sequence.get("participants"), f"{path}.sequence.participants")
    messages = require_list(sequence.get("messages"), f"{path}.sequence.messages")
    zones = require_list(sequence.get("zones"), f"{path}.sequence.zones")
    if not 2 <= len(participants) <= 9:
        raise ValueError(f"{path}.sequence.participants must contain 2-9 participants.")
    if not messages:
        raise ValueError(f"{path}.sequence.messages must not be empty.")
    if not zones:
        raise ValueError(f"{path}.sequence.zones must include at least one highlighted region.")

    participant_ids: set[str] = set()
    for index, participant_value in enumerate(participants):
        participant = require_object(
            participant_value, f"{path}.sequence.participants[{index}]"
        )
        participant_id = require_text(
            participant.get("id"), f"{path}.sequence.participants[{index}].id"
        )
        require_text(
            participant.get("label"), f"{path}.sequence.participants[{index}].label"
        )
        if participant_id in participant_ids:
            raise ValueError(f"Duplicate participant id '{participant_id}' in {path}.")
        participant_ids.add(participant_id)

    for index, message_value in enumerate(messages):
        message = require_object(message_value, f"{path}.sequence.messages[{index}]")
        source = require_text(message.get("from"), f"{path}.sequence.messages[{index}].from")
        target = require_text(message.get("to"), f"{path}.sequence.messages[{index}].to")
        require_text(message.get("label"), f"{path}.sequence.messages[{index}].label")
        if source not in participant_ids or target not in participant_ids:
            raise ValueError(
                f"{path}.sequence.messages[{index}] references an unknown participant."
            )
        kind = str(message.get("kind", "call")).lower()
        if kind not in VALID_MESSAGE_KINDS:
            raise ValueError(f"{path}.sequence.messages[{index}].kind is invalid.")

    has_expected_zone = False
    for index, zone_value in enumerate(zones):
        zone = require_object(zone_value, f"{path}.sequence.zones[{index}]")
        start = zone.get("start_message")
        end = zone.get("end_message")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError(
                f"{path}.sequence.zones[{index}] message indexes must be integers."
            )
        if start < 1 or end < start or end > len(messages):
            raise ValueError(f"{path}.sequence.zones[{index}] message range is invalid.")
        if zone.get("from") not in participant_ids or zone.get("to") not in participant_ids:
            raise ValueError(
                f"{path}.sequence.zones[{index}] references an unknown participant."
            )
        if tone(zone.get("tone")) == expected_zone_tone:
            has_expected_zone = True
    if not has_expected_zone:
        raise ValueError(
            f"{path}.sequence.zones must include a '{expected_zone_tone}' zone."
        )


def validate_spec(spec: dict[str, Any]) -> None:
    require_text(spec.get("title"), "title")
    require_text(spec.get("explanation_title"), "explanation_title")
    require_text(spec.get("issue_summary"), "issue_summary")
    require_text(spec.get("scope_boundary"), "scope_boundary")
    explanations = require_list(spec.get("explanations"), "explanations")
    if not explanations:
        raise ValueError("explanations must contain at least one changed-file card.")
    validate_flow(require_object(spec.get("old_flow"), "old_flow"), "old_flow", "problem")
    validate_flow(require_object(spec.get("new_flow"), "new_flow"), "new_flow", "success")


def render_meta(spec: dict[str, Any]) -> str:
    items: list[str] = []
    reference = spec.get("reference")
    if isinstance(reference, dict) and reference.get("label"):
        label = escape(reference["label"])
        url = reference.get("url")
        if url:
            items.append(
                f'<a class="pill" href="{escape(url)}">{label}</a>'
            )
        else:
            items.append(f'<span class="pill">{label}</span>')
    for item_value in spec.get("meta", []):
        if not isinstance(item_value, dict) or not item_value.get("label"):
            continue
        item_tone = tone(item_value.get("tone"))
        class_name = "pill live" if item_tone == "success" else "pill"
        items.append(f'<span class="{class_name}">{escape(item_value["label"])}</span>')
    return "".join(items)


def render_evidence(items: list[Any]) -> str:
    cards: list[str] = []
    for item_value in items:
        if not isinstance(item_value, dict):
            continue
        item_tone = tone(item_value.get("tone"))
        source = item_value.get("source")
        source_html = (
            f'<span class="source">Source: {escape(source)}</span>' if source else ""
        )
        cards.append(
            f"""
            <article class="evidence-item tone-{item_tone}">
                <span class="evidence-label">{escape(item_value.get("label", ""))}</span>
                <h3>{escape(item_value.get("title", ""))}</h3>
                <p>{escape(item_value.get("detail", ""))}</p>
                {source_html}
            </article>
            """
        )
    if not cards:
        return ""
    return f"""
    <section aria-labelledby="evidence-title">
        <div class="section-heading">
            <div>
                <p class="section-label">Evidence</p>
                <h2 id="evidence-title">What established the previous behavior.</h2>
            </div>
            <p class="section-summary">Only evidence retrieved from code, tests, logs, data, or the PR is shown.</p>
        </div>
        <div class="evidence-grid">{"".join(cards)}</div>
    </section>
    """


def render_overview(flow: dict[str, Any], phase: str) -> str:
    overview = flow["overview"]
    steps_html: list[str] = []
    for index, step_value in enumerate(overview["steps"], start=1):
        step = require_object(step_value, f"{phase}.overview.steps[{index - 1}]")
        step_tone = tone(step.get("tone"), "normal")
        tag = step.get("tag")
        tag_html = (
            f'<span class="step-tag">{escape(tag)}</span>' if tag else ""
        )
        steps_html.append(
            f"""
            <article class="overview-step tone-{step_tone}">
                <span class="step-number">{index}</span>
                <span class="actor">{escape(step["actor"])}</span>
                <h3>{escape(step["title"])}</h3>
                <p>{escape(step["detail"])}</p>
                {tag_html}
            </article>
            """
        )
        if index < len(overview["steps"]):
            steps_html.append('<div class="overview-arrow" aria-hidden="true">&rarr;</div>')

    callout_class = "problem-callout" if phase == "old" else "success-callout"
    return f"""
    <div class="diagram-level">
        <span>Overview</span>
        <strong>Simplified sequence</strong>
    </div>
    <div class="diagram-shell">
        <div class="diagram-toolbar">
            <strong>{escape(overview.get("label", flow["title"] + " - simplified"))}</strong>
            <span>flow moves left-to-right &rarr;</span>
        </div>
        <div class="overview-scroll">
            <div class="overview-track">{"".join(steps_html)}</div>
        </div>
        <div class="{callout_class}">{escape(overview.get("callout", ""))}</div>
    </div>
    """


def participant_positions(
    participants: list[dict[str, Any]], width: int, margin: int
) -> dict[str, float]:
    if len(participants) == 1:
        return {participants[0]["id"]: width / 2}
    usable = width - (margin * 2)
    spacing = usable / (len(participants) - 1)
    return {
        participant["id"]: margin + (index * spacing)
        for index, participant in enumerate(participants)
    }


def render_zone_label(
    label: str,
    x: float,
    y: float,
    tone_name: str,
    max_width: int = 28,
) -> str:
    lines = wrap_lines(label, max_width, max_lines=2)
    label_width = max(155, min(260, max(len(line) for line in lines) * 7.4 + 26))
    label_height = 25 + ((len(lines) - 1) * 16)
    text = svg_text(lines, x + 12, y + 17, "seq-zone-label", anchor="start")
    return (
        f'<rect class="seq-zone-label-bg tone-{tone_name}" x="{x:.1f}" y="{y:.1f}" '
        f'width="{label_width:.1f}" height="{label_height:.1f}"></rect>{text}'
    )


def render_sequence(flow: dict[str, Any], phase: str) -> str:
    sequence = flow["sequence"]
    participants = [require_object(item, "participant") for item in sequence["participants"]]
    messages = [require_object(item, "message") for item in sequence["messages"]]
    zones = [require_object(item, "zone") for item in sequence["zones"]]

    width = max(1180, (len(participants) - 1) * 215 + 180)
    margin = 90
    x_positions = participant_positions(participants, width, margin)

    rows: list[dict[str, Any]] = []
    y = 160
    for message in messages:
        lines = wrap_lines(message.get("label", ""), 42, max_lines=3)
        rows.append({"y": y, "lines": lines})
        y += 62 + max(0, len(lines) - 1) * 15

    note = sequence.get("note")
    note_height = 72 if isinstance(note, dict) and note.get("text") else 0
    height = y + note_height + 55
    prefix = "old" if phase == "old" else "new"

    marker_defs = []
    color_map = {
        "normal": "#173f66",
        "neutral": "#173f66",
        "problem": "#c83f4d",
        "success": "#158467",
        "config": "#1f92a8",
    }
    for marker_tone, color in color_map.items():
        marker_defs.append(
            f"""
            <marker id="{prefix}-arrow-{marker_tone}" markerWidth="10" markerHeight="8"
                    refX="9" refY="4" orient="auto">
                <path d="M0,0 L10,4 L0,8 Z" fill="{color}"></path>
            </marker>
            """
        )

    zone_parts: list[str] = []
    for zone in zones:
        zone_tone = tone(zone.get("tone"), "problem" if phase == "old" else "success")
        start_index = int(zone["start_message"]) - 1
        end_index = int(zone["end_message"]) - 1
        left = min(x_positions[zone["from"]], x_positions[zone["to"]]) - 48
        right = max(x_positions[zone["from"]], x_positions[zone["to"]]) + 48
        top = rows[start_index]["y"] - 38
        bottom = rows[end_index]["y"] + 36 + (len(rows[end_index]["lines"]) - 1) * 15
        zone_parts.append(
            f'<rect class="seq-zone tone-{zone_tone}" x="{left:.1f}" y="{top:.1f}" '
            f'width="{(right - left):.1f}" height="{(bottom - top):.1f}"></rect>'
        )
        label_x = max(left + 12, right - 245)
        zone_parts.append(
            render_zone_label(
                str(zone.get("label", "Highlighted region")),
                label_x,
                top + 8,
                zone_tone,
            )
        )

    participant_parts: list[str] = []
    activation_parts: list[str] = []
    message_indices_by_participant: dict[str, list[int]] = {
        participant["id"]: [] for participant in participants
    }
    for index, message in enumerate(messages):
        message_indices_by_participant[message["from"]].append(index)
        message_indices_by_participant[message["to"]].append(index)

    spacing = (width - margin * 2) / max(1, len(participants) - 1)
    header_width = min(178, spacing - 24 if len(participants) > 1 else 178)
    for participant in participants:
        participant_id = participant["id"]
        x = x_positions[participant_id]
        label_lines = wrap_lines(participant["label"], 17, max_lines=2)
        participant_parts.append(
            f'<line class="seq-lifeline" x1="{x:.1f}" y1="82" x2="{x:.1f}" y2="{height - 35:.1f}"></line>'
        )
        participant_parts.append(
            f'<rect class="seq-participant" x="{(x - header_width / 2):.1f}" y="20" '
            f'width="{header_width:.1f}" height="60"></rect>'
        )
        participant_parts.append(
            svg_text(label_lines, x, 47, "seq-participant-text", line_height=17)
        )
        indexes = message_indices_by_participant[participant_id]
        if indexes:
            top = rows[min(indexes)]["y"] - 10
            bottom = rows[max(indexes)]["y"] + 24
            activation_parts.append(
                f'<rect class="seq-activation" x="{x - 6:.1f}" y="{top:.1f}" '
                f'width="12" height="{max(34, bottom - top):.1f}"></rect>'
            )

    message_parts: list[str] = []
    for index, message in enumerate(messages):
        source_x = x_positions[message["from"]]
        target_x = x_positions[message["to"]]
        row = rows[index]
        message_tone = tone(message.get("tone"), "normal")
        kind = str(message.get("kind", "call")).lower()
        dashed_class = " return" if kind == "return" else ""
        marker_id = f"{prefix}-arrow-{message_tone}"

        if source_x == target_x:
            loop_width = 62
            path = (
                f"M {source_x + 6:.1f} {row['y']:.1f} "
                f"h {loop_width} v 28 h {-loop_width}"
            )
            message_parts.append(
                f'<path class="seq-message-line tone-{message_tone}{dashed_class}" '
                f'd="{path}" marker-end="url(#{marker_id})"></path>'
            )
            label_x = source_x + loop_width / 2
        else:
            direction = 1 if target_x > source_x else -1
            start_x = source_x + direction * 7
            end_x = target_x - direction * 8
            message_parts.append(
                f'<line class="seq-message-line tone-{message_tone}{dashed_class}" '
                f'x1="{start_x:.1f}" y1="{row["y"]:.1f}" '
                f'x2="{end_x:.1f}" y2="{row["y"]:.1f}" '
                f'marker-end="url(#{marker_id})"></line>'
            )
            label_x = (source_x + target_x) / 2

        label_y = row["y"] - 10 - max(0, len(row["lines"]) - 1) * 8
        message_parts.append(
            svg_text(
                row["lines"],
                label_x,
                label_y,
                f"seq-message-text tone-{message_tone}",
            )
        )

    note_html = ""
    if isinstance(note, dict) and note.get("text"):
        note_tone = tone(note.get("tone"), "neutral")
        note_y = y + 2
        note_width = min(width - 220, 900)
        note_x = (width - note_width) / 2
        note_lines = wrap_lines(note["text"], 90, max_lines=2)
        note_html = (
            f'<rect class="seq-note tone-{note_tone}" x="{note_x:.1f}" y="{note_y:.1f}" '
            f'width="{note_width:.1f}" height="58"></rect>'
            + svg_text(note_lines, width / 2, note_y + 24, "seq-note-text")
        )

    svg = f"""
    <svg class="uml-sequence" viewBox="0 0 {width} {height}" role="img"
         aria-label="{escape(sequence.get("label", flow["title"]))}">
        <defs>{"".join(marker_defs)}</defs>
        {"".join(zone_parts)}
        {"".join(participant_parts)}
        {"".join(activation_parts)}
        {"".join(message_parts)}
        {note_html}
    </svg>
    """

    legend_tone = "problem" if phase == "old" else "success"
    legend_text = (
        "Red rectangle = problematic ordering or stale state"
        if phase == "old"
        else "Green rectangle = behavior introduced by the fix"
    )
    return f"""
    <div class="diagram-level">
        <span>Detail</span>
        <strong>UML sequence diagram</strong>
    </div>
    <div class="diagram-shell">
        <div class="diagram-toolbar">
            <strong>{escape(sequence.get("label", flow["title"]))}</strong>
            <span>entities left-to-right / time top-to-bottom</span>
        </div>
        <div class="sequence-scroll">{svg}</div>
        <div class="sequence-legend">
            <span><i class="legend-swatch tone-{legend_tone}"></i>{legend_text}</span>
            <span><i class="legend-line"></i>Dashed arrow = response</span>
        </div>
    </div>
    """


def render_flow_section(flow: dict[str, Any], phase: str, section_number: str) -> str:
    summary = escape(flow.get("summary", ""))
    return f"""
    <section aria-labelledby="{phase}-flow-title">
        <div class="section-heading">
            <div>
                <p class="section-label">{section_number} / {"previous flow" if phase == "old" else "fixed flow"}</p>
                <h2 id="{phase}-flow-title">{escape(flow["title"])}</h2>
            </div>
            <p class="section-summary">{summary}</p>
        </div>
        {render_overview(flow, phase)}
        {render_sequence(flow, phase)}
    </section>
    """


def render_explanations(items: list[Any]) -> str:
    cards: list[str] = []
    for item_value in items:
        if not isinstance(item_value, dict):
            continue
        cards.append(
            f"""
            <article class="change-card">
                <span class="file-path">{escape(item_value.get("component", ""))}</span>
                <h3>{escape(item_value.get("title", ""))}</h3>
                <p>{escape(item_value.get("detail", ""))}</p>
            </article>
            """
        )
    return f"""
    <section aria-labelledby="explanations-title">
        <div class="section-heading">
            <div>
                <p class="section-label">More explanations</p>
                <h2 id="explanations-title">What changed and why it matters.</h2>
            </div>
            <p class="section-summary">Each card describes one responsibility, not every changed line.</p>
        </div>
        <div class="change-grid">{"".join(cards)}</div>
    </section>
    """


def render_fix_evidence(items: list[Any]) -> str:
    rows: list[str] = []
    for item_value in items:
        if not isinstance(item_value, dict):
            continue
        result_tone = tone(item_value.get("tone"), "success")
        rows.append(
            f"""
            <tr>
                <td>{escape(item_value.get("concern", ""))}</td>
                <td>{escape(item_value.get("before", ""))}</td>
                <td>{escape(item_value.get("after", ""))}</td>
                <td class="result tone-{result_tone}">{escape(item_value.get("result", ""))}</td>
            </tr>
            """
        )
    if not rows:
        return ""
    return f"""
    <section aria-labelledby="fix-evidence-title">
        <div class="section-heading">
            <div>
                <p class="section-label">Evidence of fix</p>
                <h2 id="fix-evidence-title">What proves the new behavior.</h2>
            </div>
            <p class="section-summary">Tests, builds, metrics, logs, or observed state supplied by the change.</p>
        </div>
        <div class="performance">
            <table>
                <thead>
                    <tr><th>Concern</th><th>Before</th><th>After</th><th>Result</th></tr>
                </thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </div>
    </section>
    """


CSS = r"""
:root {
    color-scheme: light;
    --ink: #10213a;
    --muted: #5b6c80;
    --paper: #f4f8fb;
    --surface: #ffffff;
    --line: #cbd8e4;
    --navy: #173f66;
    --cyan: #1f92a8;
    --cyan-soft: #e4f5f8;
    --green: #158467;
    --green-soft: #e4f5ee;
    --red: #c83f4d;
    --red-soft: #fdebed;
    --amber: #bd7416;
    --amber-soft: #fff1dc;
    --purple: #7055a5;
    --purple-soft: #f0ebfa;
    --shadow: 0 18px 50px rgba(16, 33, 58, 0.10);
    --radius: 18px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    margin: 0;
    color: var(--ink);
    background:
        linear-gradient(rgba(31,146,168,.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(31,146,168,.055) 1px, transparent 1px),
        var(--paper);
    background-size: 28px 28px;
    font-family: "Aptos", "Segoe UI", sans-serif;
    line-height: 1.55;
}
a { color: inherit; }
.page { width: min(1440px, calc(100% - 36px)); margin: 0 auto; padding: 30px 0 70px; }
.hero {
    position: relative;
    overflow: hidden;
    padding: clamp(28px, 5vw, 70px);
    border: 1px solid rgba(23,63,102,.18);
    border-radius: 28px;
    background:
        radial-gradient(circle at 88% 12%, rgba(31,146,168,.22), transparent 28%),
        linear-gradient(135deg,#fff 0%,#eef7fa 62%,#e8f3f6 100%);
    box-shadow: var(--shadow);
}
.hero::after {
    content: "";
    position: absolute;
    right: -80px;
    bottom: -110px;
    width: 310px;
    height: 310px;
    border: 32px solid rgba(21,132,103,.10);
    border-radius: 50%;
}
.eyebrow,.section-label,.actor,.file-path,.evidence-label,.source {
    font-family: "Cascadia Mono","Consolas",monospace;
    letter-spacing: .07em;
    text-transform: uppercase;
}
.eyebrow {
    position: relative;
    z-index: 1;
    margin: 0 0 18px;
    color: var(--cyan);
    font-size: .78rem;
    font-weight: 800;
}
h1,h2,h3 { margin-top: 0; font-family: "Bahnschrift","Aptos Display","Segoe UI",sans-serif; line-height: 1.08; }
h1 {
    position: relative;
    z-index: 1;
    max-width: 980px;
    margin-bottom: 20px;
    font-size: clamp(2.45rem,6vw,5.7rem);
    font-weight: 730;
    letter-spacing: -.045em;
}
h1 .accent { color: var(--cyan); }
.hero-copy {
    position: relative;
    z-index: 1;
    max-width: 850px;
    margin: 0;
    color: #344a61;
    font-size: clamp(1.05rem,1.8vw,1.35rem);
}
.hero-meta { position: relative; z-index: 1; display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; }
.pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 13px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: rgba(255,255,255,.82);
    color: var(--navy);
    font-size: .88rem;
    font-weight: 760;
    text-decoration: none;
}
.pill.live { border-color: rgba(21,132,103,.35); background: var(--green-soft); color: #0d684f; }
.pill.live::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 0 5px rgba(21,132,103,.12);
}
.thesis { display: grid; grid-template-columns: minmax(0,1.45fr) minmax(250px,.55fr); gap: 18px; margin-top: 22px; }
.thesis-card,.scope-note {
    padding: 22px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 8px 25px rgba(16,33,58,.055);
}
.thesis-card { border-left: 6px solid var(--cyan); font-size: 1.12rem; font-weight: 690; }
.scope-note { border-left: 6px solid var(--purple); background: var(--purple-soft); color: #443268; }
.scope-note strong { display: block; margin-bottom: 5px; }
section { margin-top: 54px; }
.section-heading { display: grid; grid-template-columns: minmax(0,1fr) minmax(240px,.48fr); gap: 22px; align-items: end; margin-bottom: 18px; }
.section-label { margin: 0 0 7px; color: var(--cyan); font-size: .74rem; font-weight: 800; }
h2 { margin-bottom: 0; font-size: clamp(1.75rem,3.2vw,3rem); letter-spacing: -.03em; }
.section-summary { margin: 0; color: var(--muted); font-size: .98rem; }
.evidence-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(190px,1fr)); gap: 11px; }
.evidence-item {
    padding: 17px;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--surface);
    box-shadow: 0 8px 22px rgba(16,33,58,.05);
}
.evidence-item.tone-problem { border-color: rgba(200,63,77,.35); background: var(--red-soft); }
.evidence-item.tone-success { border-color: rgba(21,132,103,.35); background: var(--green-soft); }
.evidence-label { display: block; margin-bottom: 8px; color: var(--navy); font-size: .72rem; font-weight: 850; }
.evidence-item h3 { margin-bottom: 7px; font-size: 1.08rem; }
.evidence-item p { margin: 0; color: #42596e; font-size: .9rem; }
.source { display: block; margin-top: 10px; color: var(--muted); font-size: .62rem; }
.diagram-level { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 20px 0 11px; }
.diagram-level span { padding: 5px 8px; border-radius: 7px; background: var(--navy); color: #fff; font: 850 .67rem "Cascadia Mono","Consolas",monospace; letter-spacing: .06em; text-transform: uppercase; }
.diagram-level strong { color: var(--navy); font-family: "Bahnschrift","Aptos Display",sans-serif; font-size: 1.08rem; }
.diagram-shell { overflow: hidden; border: 1px solid var(--line); border-radius: 22px; background: var(--surface); box-shadow: var(--shadow); }
.diagram-toolbar { display: flex; justify-content: space-between; gap: 18px; padding: 16px 20px; border-bottom: 1px solid var(--line); background: #f8fbfd; }
.diagram-toolbar strong { font-family: "Bahnschrift","Aptos Display",sans-serif; font-size: 1.08rem; }
.diagram-toolbar span { color: var(--muted); font: .78rem "Cascadia Mono","Consolas",monospace; }
.overview-scroll,.sequence-scroll { overflow-x: auto; padding: 20px; }
.overview-track { display: flex; align-items: stretch; gap: 12px; min-width: max-content; }
.overview-step {
    width: 185px;
    min-height: 190px;
    padding: 16px;
    border: 1px solid #bfd0de;
    border-radius: 14px;
    background: linear-gradient(180deg,#fff,#f7fafc);
}
.overview-step.tone-problem { border: 2px solid var(--red); background: linear-gradient(180deg,#fff9fa,var(--red-soft)); box-shadow: 0 0 0 4px rgba(200,63,77,.06); }
.overview-step.tone-success { border: 2px solid var(--green); background: linear-gradient(180deg,#fbfffd,var(--green-soft)); }
.step-number { display: inline-grid; width: 30px; height: 30px; place-items: center; margin-bottom: 14px; border-radius: 9px; background: var(--navy); color: #fff; font: 800 .78rem "Cascadia Mono","Consolas",monospace; }
.tone-problem .step-number { background: var(--red); }
.tone-success .step-number { background: var(--green); }
.actor { display: block; margin-bottom: 7px; color: var(--cyan); font-size: .68rem; font-weight: 800; }
.overview-step h3 { margin-bottom: 8px; font-size: 1.05rem; }
.overview-step p { margin: 0; color: #455b70; font-size: .87rem; }
.step-tag { display: inline-block; margin-top: 12px; padding: 5px 8px; border-radius: 7px; background: var(--navy); color: #fff; font: 800 .66rem "Cascadia Mono","Consolas",monospace; text-transform: uppercase; }
.tone-problem .step-tag { background: var(--red); }
.tone-success .step-tag { background: var(--green); }
.overview-arrow { display: grid; width: 26px; place-items: center; color: var(--navy); font-size: 1.5rem; font-weight: 900; }
.problem-callout,.success-callout { display: flex; gap: 12px; align-items: center; margin: 0 20px 20px; padding: 14px 16px; border-radius: 13px; font-weight: 720; }
.problem-callout { border: 1px dashed var(--red); background: var(--red-soft); color: #7d2630; }
.success-callout { border: 1px solid var(--green); background: var(--green-soft); color: #0d684f; }
.problem-callout::before,.success-callout::before { display: grid; flex: 0 0 30px; height: 30px; place-items: center; border-radius: 50%; color: #fff; font: 900 .9rem "Cascadia Mono","Consolas",monospace; }
.problem-callout::before { content: "!"; background: var(--red); }
.success-callout::before { content: "\2713"; background: var(--green); }
.uml-sequence { display: block; width: 100%; min-width: 1120px; height: auto; }
.seq-participant { fill: #f8fbfd; stroke: var(--navy); stroke-width: 2; rx: 8; }
.seq-participant-text { fill: var(--ink); font: 800 14px "Cascadia Mono","Consolas",monospace; }
.seq-lifeline { stroke: #8fa3b5; stroke-width: 2; stroke-dasharray: 8 8; }
.seq-activation { fill: #fff; stroke: var(--navy); stroke-width: 2; }
.seq-message-line { fill: none; stroke-width: 2.6; }
.seq-message-line.return { stroke-dasharray: 7 6; }
.seq-message-line.tone-normal,.seq-message-line.tone-neutral { stroke: var(--navy); }
.seq-message-line.tone-problem { stroke: var(--red); stroke-width: 3.2; }
.seq-message-line.tone-success { stroke: var(--green); stroke-width: 3.2; }
.seq-message-line.tone-config { stroke: var(--cyan); stroke-width: 3; }
.seq-message-text { fill: #30475d; font-size: 13px; font-weight: 680; }
.seq-message-text.tone-problem { fill: #9f2d39; font-weight: 820; }
.seq-message-text.tone-success { fill: #0e7056; font-weight: 820; }
.seq-message-text.tone-config { fill: #146e7e; font-weight: 820; }
.seq-zone { stroke-width: 3; rx: 14; }
.seq-zone.tone-problem { fill: rgba(200,63,77,.075); stroke: var(--red); stroke-dasharray: 10 7; }
.seq-zone.tone-success { fill: rgba(21,132,103,.075); stroke: var(--green); }
.seq-zone.tone-config { fill: rgba(31,146,168,.075); stroke: var(--cyan); }
.seq-zone-label-bg { rx: 6; }
.seq-zone-label-bg.tone-problem { fill: var(--red); }
.seq-zone-label-bg.tone-success { fill: var(--green); }
.seq-zone-label-bg.tone-config { fill: var(--cyan); }
.seq-zone-label { fill: #fff; font: 900 11px "Cascadia Mono","Consolas",monospace; letter-spacing: .03em; }
.seq-note { stroke-width: 2.5; rx: 10; }
.seq-note.tone-problem { fill: var(--red-soft); stroke: var(--red); }
.seq-note.tone-success { fill: var(--green-soft); stroke: var(--green); }
.seq-note.tone-neutral,.seq-note.tone-normal { fill: #eef4f7; stroke: var(--navy); }
.seq-note-text { fill: var(--ink); font-size: 13px; font-weight: 760; }
.sequence-legend { display: flex; flex-wrap: wrap; gap: 10px 18px; padding: 14px 18px 18px; border-top: 1px solid var(--line); background: #f8fbfd; color: #465d72; font-size: .84rem; }
.sequence-legend span { display: inline-flex; align-items: center; gap: 7px; }
.legend-swatch { width: 17px; height: 12px; border: 2px solid; border-radius: 4px; }
.legend-swatch.tone-problem { border-color: var(--red); background: var(--red-soft); }
.legend-swatch.tone-success { border-color: var(--green); background: var(--green-soft); }
.legend-line { width: 22px; border-top: 2px dashed #587086; }
.change-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; }
.change-card { padding: 20px; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); box-shadow: 0 8px 22px rgba(16,33,58,.055); }
.file-path { display: block; margin-bottom: 12px; color: var(--cyan); font-size: .66rem; font-weight: 850; overflow-wrap: anywhere; }
.change-card h3 { margin-bottom: 8px; font-size: 1.18rem; }
.change-card p { margin: 0; color: #4a6074; font-size: .92rem; }
.performance { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); }
table { width: 100%; min-width: 760px; border-collapse: collapse; }
th,td { padding: 16px 18px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { background: #eef4f7; color: var(--navy); font: .72rem "Cascadia Mono","Consolas",monospace; text-transform: uppercase; }
tr:last-child td { border-bottom: 0; }
td:first-child { font-weight: 760; }
.result { font-weight: 820; }
.result.tone-success { color: var(--green); }
.result.tone-problem { color: var(--red); }
.footer-card { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 18px; align-items: center; padding: 25px; border-radius: 20px; background: var(--ink); color: #fff; }
.footer-card h2 { font-size: clamp(1.5rem,2.5vw,2.3rem); }
.footer-card p { max-width: 680px; margin: 8px 0 0; color: #c6d6e5; }
.cta { display: inline-flex; align-items: center; padding: 12px 17px; border-radius: 11px; background: #fff; color: var(--ink); font-weight: 800; text-decoration: none; }
:focus-visible { outline: 3px solid var(--amber); outline-offset: 3px; }
@media (max-width:840px) {
    .page { width: min(100% - 20px,1440px); padding-top: 10px; }
    .hero { border-radius: 20px; }
    .thesis,.section-heading,.change-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion:reduce) { html { scroll-behavior: auto; } }
@media print {
    body { background: #fff; }
    .page { width: 100%; padding: 0; }
    .hero,.diagram-shell,.performance { box-shadow: none; }
}
"""


def render_document(spec: dict[str, Any]) -> str:
    subtitle = escape(spec.get("subtitle", ""))
    reference = spec.get("reference") if isinstance(spec.get("reference"), dict) else {}
    footer_title = escape(
        spec.get("footer_title", f"{spec['title']}: the change explained.")
    )
    footer_text = escape(
        spec.get(
            "footer_text",
            "The old and new behavior are grounded in the actual change and available evidence.",
        )
    )
    reference_url = reference.get("url") if isinstance(reference, dict) else None
    reference_label = (
        reference.get("label", "Open change") if isinstance(reference, dict) else "Open change"
    )
    cta = (
        f'<a class="cta" href="{escape(reference_url)}">{escape(reference_label)} &rarr;</a>'
        if reference_url
        else ""
    )

    evidence_html = render_evidence(spec.get("evidence", []))
    fix_evidence_html = render_fix_evidence(spec.get("fix_evidence", []))
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="generator" content="agentic-ai/pr-explainer">
    <title>{escape(spec["title"])}</title>
    <style>{CSS}</style>
</head>
<body>
<main class="page">
    <header class="hero">
        <p class="eyebrow">PR / local change explainer</p>
        <h1>{escape(spec["title"])}<br><span class="accent">{escape(spec["explanation_title"])}</span></h1>
        <p class="hero-copy">{subtitle}</p>
        <div class="hero-meta">{render_meta(spec)}</div>
    </header>

    <div class="thesis">
        <div class="thesis-card">{escape(spec["issue_summary"])}</div>
        <div class="scope-note"><strong>Scope boundary</strong>{escape(spec["scope_boundary"])}</div>
    </div>

    {evidence_html}
    {render_flow_section(spec["old_flow"], "old", "Previous")}
    {render_flow_section(spec["new_flow"], "new", "Fixed")}
    {render_explanations(spec["explanations"])}
    {fix_evidence_html}

    <section>
        <div class="footer-card">
            <div><h2>{footer_title}</h2><p>{footer_text}</p></div>
            {cta}
        </div>
    </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Path to the JSON renderer spec.")
    parser.add_argument(
        "--output",
        help="Output HTML path. Defaults to ./output/<Title>-PR-Explainer.html",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    with spec_path.open("r", encoding="utf-8") as handle:
        spec = require_object(json.load(handle), "spec")
    validate_spec(spec)

    if args.output:
        output_path = Path(args.output).expanduser()
    else:
        output_path = Path("output") / f"{slugify(spec['title'])}-PR-Explainer.html"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = render_document(spec)
    if document.count('class="overview-track"') != 2:
        raise RuntimeError("Rendered document must contain two simplified overview flows.")
    if document.count('class="uml-sequence"') != 2:
        raise RuntimeError("Rendered document must contain two UML sequence diagrams.")
    if "tone-problem" not in document or "tone-success" not in document:
        raise RuntimeError("Rendered document must contain problem and success highlights.")

    output_path.write_text(document, encoding="utf-8")
    print(
        json.dumps(
            {
                "action": "rendered",
                "output": str(output_path),
                "bytes": output_path.stat().st_size,
                "overview_flows": 2,
                "uml_sequences": 2,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
