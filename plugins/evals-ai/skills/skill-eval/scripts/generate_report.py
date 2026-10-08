#!/usr/bin/env python3
"""
generate_report.py - render a self-contained report.html from a result.json.

Stdlib only. No server, no external assets, no network. The layout is FIXED and
keyed to schema_version, so every skill's report is structurally identical and
comparable. Empty/None sections render as an explicit "Not available" card rather
than disappearing. When metadata.feedback_enabled is false the optional feedback
controls are still emitted (so the layout is unchanged) but hidden + disabled. If a
sibling human_override.json is present, the author's verdict is rendered as the
authoritative final word (the AI judge's original stays visible for traceability).

Usage:
    python generate_report.py <path/to/result.json> [--out <path/to/report.html>]
Default output: report.html next to the result.json.
"""

import argparse
import datetime
import html
import json
import math
import os
import sys

LAYOUT_FOR_SCHEMA = "skill-eval/v5"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def esc(x):
    return html.escape("" if x is None else str(x))


def not_available(title, why="Not available"):
    return ('<section class="card na"><h2>{}</h2>'
            '<p class="muted">{}</p></section>').format(esc(title), esc(why))


def fmt_num(x, nd=2):
    if isinstance(x, bool) or x is None:
        return "—"
    if isinstance(x, (int, float)):
        return ("{:." + str(nd) + "f}").format(x).rstrip("0").rstrip(".") if isinstance(x, float) else str(x)
    return esc(x)


def pct(x):
    if isinstance(x, (int, float)):
        return "{:.0f}%".format(x * 100)
    return "—"


def _note(n):
    n = (n or "").strip()
    return ' <span class="muted">— {}</span>'.format(esc(n)) if n else ""


def _has_override(override):
    if not override:
        return False
    return bool(override.get("value_verdict")
                or override.get("static_average") is not None
                or (override.get("dimension_overrides") or [])
                or (override.get("trigger_overrides") or [])
                or (override.get("finding_overrides") or [])
                or (override.get("overall_note") or "").strip())


# ---------------------------------------------------------------------------
# inline-SVG radar for the static rubric
# ---------------------------------------------------------------------------
def radar_svg(dimensions):
    n = len(dimensions)
    if n < 3:
        return '<p class="muted">Radar needs at least 3 dimensions.</p>'
    size = 420
    cx = cy = size / 2
    R = size * 0.34
    rings = []
    for frac in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = []
        for i in range(n):
            ang = -math.pi / 2 + i * 2 * math.pi / n
            pts.append("{:.1f},{:.1f}".format(cx + R * frac * math.cos(ang),
                                              cy + R * frac * math.sin(ang)))
        rings.append('<polygon class="ring" points="{}"/>'.format(" ".join(pts)))
    axes, labels, shape = [], [], []
    for i, d in enumerate(dimensions):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        ex, ey = cx + R * math.cos(ang), cy + R * math.sin(ang)
        axes.append('<line class="axis" x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}"/>'.format(cx, cy, ex, ey))
        score = d.get("score")
        frac = (score / 5.0) if isinstance(score, (int, float)) else 0
        shape.append("{:.1f},{:.1f}".format(cx + R * frac * math.cos(ang),
                                            cy + R * frac * math.sin(ang)))
        lx, ly = cx + (R + 26) * math.cos(ang), cy + (R + 26) * math.sin(ang)
        anchor = "middle"
        if math.cos(ang) > 0.3:
            anchor = "start"
        elif math.cos(ang) < -0.3:
            anchor = "end"
        labels.append('<text class="rlabel" x="{:.1f}" y="{:.1f}" text-anchor="{}">{} ({})</text>'.format(
            lx, ly, anchor, esc(d.get("name")), esc(d.get("score"))))
    return (
        '<svg viewBox="0 0 {0} {0}" class="radar" role="img" aria-label="static quality radar">'
        '{1}{2}<polygon class="shape" points="{3}"/>{4}</svg>'
    ).format(size, "".join(rings), "".join(axes), " ".join(shape), "".join(labels))


# ---------------------------------------------------------------------------
# feedback control (server-less): a stance <select> + note <textarea>
# ---------------------------------------------------------------------------
def fb(section, fid="", label=""):
    lab = '<span class="fb-label">{}</span>'.format(esc(label)) if label else ""
    return (
        '<span class="fb" data-section="{sec}" data-id="{fid}">{lab}'
        '<select class="fb-stance"><option value=""></option>'
        '<option value="agree">agree</option><option value="disagree">disagree</option>'
        '<option value="edit">edit</option><option value="annotate">annotate</option></select>'
        '<input class="fb-note" type="text" placeholder="note (optional)"/></span>'
    ).format(sec=esc(section), fid=esc(fid), lab=lab)


def ov_score(name):
    """Authoritative override control: a per-dimension score <select> (blank = no override)."""
    opts = "".join('<option value="{v}">{v}</option>'.format(v=v) for v in ("1", "2", "3", "4", "5", "N/A"))
    return ('<select class="fb-stance ov-dim" data-name="{n}" title="override this score">'
            '<option value="">score\u2026</option>{o}</select>').format(n=esc(name), o=opts)


def ov_find(fid):
    """Authoritative override control: a per-finding disposition <select> (+ severity for reseverity)."""
    acts = "".join('<option value="{v}">{v}</option>'.format(v=v) for v in ("keep", "dismiss", "reseverity"))
    sevs = "".join('<option value="{v}">{v}</option>'.format(v=v) for v in ("high", "medium", "low"))
    return ('<span class="ovctl"><select class="fb-stance ov-find" data-id="{i}" title="override disposition">'
            '<option value="">disposition\u2026</option>{a}</select>'
            '<select class="fb-stance ov-find-sev" data-id="{i}" title="new severity (for reseverity)">'
            '<option value="">severity\u2026</option>{s}</select></span>').format(i=esc(fid), a=acts, s=sevs)


def ov_trigger(prompt_id):
    """Authoritative override control for one trigger prompt's Expected Result."""
    return (
        '<span class="ovctl ov-trigger-wrap">'
        '<select class="fb-stance ov-trigger" data-id="{i}" title="override Expected Result">'
        '<option value="">override\u2026</option>'
        '<option value="should_trigger">Should trigger</option>'
        '<option value="should_not_trigger">Should not trigger</option>'
        '</select>'
        '<input class="fb-note ov-trigger-note" data-id="{i}" type="text" '
        'placeholder="override note"/></span>'
    ).format(i=esc(prompt_id))


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------
def section_static(sq, override=None):
    if not sq:
        return not_available("1 · Static quality")
    override = override or {}
    dov = {d.get("name"): d for d in (override.get("dimension_overrides") or [])}
    dims = sq.get("dimensions") or []

    def score_cell(d):
        o = dov.get(d.get("name"))
        if o is not None:
            return '<s class="was">{}</s> <b class="ovr">{}</b>'.format(esc(d.get("score")), esc(o.get("score")))
        return esc(d.get("score"))

    rows = "".join(
        '<tr><td>{}</td><td class="num">{}</td><td>{}</td><td class="muted">{}</td><td>{}{}</td></tr>'.format(
            esc(d.get("name")), score_cell(d), esc(d.get("rationale")),
            esc(d.get("evidence")), fb("static", d.get("name", ""), ""), ov_score(d.get("name", "")))
        for d in dims)
    imps = "".join('<li><span class="pill {p}">{p}</span> <b>{dim}</b> — {t}</li>'.format(
        p=esc((t or {}).get("priority")), dim=esc((t or {}).get("dimension")), t=esc((t or {}).get("text")))
        for t in (sq.get("top_improvements") or []))
    avgb = '<span class="badge">avg {avg} / 5</span>'.format(avg=esc(sq.get("average_score")))
    if override.get("static_average") is not None:
        avgb += ' <span class="badge ovr">author avg {} / 5</span>'.format(esc(override.get("static_average")))
    return (
        '<section class="card"><h2>1 · Static quality {avgb}</h2>'
        '<div class="cols"><div class="radarwrap">{radar}</div>'
        '<div><table><thead><tr><th>Dimension</th><th>Score</th><th>Rationale</th>'
        '<th>Evidence</th><th class="fbcol">Feedback</th></tr></thead><tbody>{rows}</tbody></table>'
        '<h3>Top improvements</h3><ul class="imps">{imps}</ul>'
        '<div class="fb-overall">Overall feedback on static quality: {ov}'
        '<span class="ovctl">Override avg: <input id="ov-static-avg" class="fb-note" type="number" '
        'min="1" max="5" step="0.1" style="width:64px" placeholder="1-5"></span></div></div></div></section>'
    ).format(avgb=avgb,
             radar=radar_svg([d for d in dims if isinstance(d.get("score"), (int, float))]), rows=rows,
             imps=imps or '<li class="muted">None</li>', ov=fb("static", "overall", ""))


def section_triggering(tr, override=None):
    if not tr:
        return not_available("2 · Actual triggering")
    override = override or {}
    s = tr.get("summary") or {}
    trigger_overrides = {
        item.get("prompt_id"): item for item in (override.get("trigger_overrides") or [])
    }

    def effective_summary():
        matches = false_positive = false_negative = 0
        prompts = tr.get("prompts") or []
        for prompt in prompts:
            item = trigger_overrides.get(prompt.get("id")) or {}
            expected = item.get("expected_result") or prompt.get("expected_result")
            actual = prompt.get("actual_result")
            matched = ((expected == "should_trigger" and actual == "triggered") or
                       (expected == "should_not_trigger" and actual == "not_triggered"))
            matches += int(matched)
            false_positive += int(expected == "should_not_trigger" and actual == "triggered")
            false_negative += int(expected == "should_trigger" and actual == "not_triggered")
        total = len(prompts)
        return {
            "matches": matches,
            "total": total,
            "accuracy": matches / total if total else 0,
            "false_positive": false_positive,
            "false_negative": false_negative,
        }

    effective = effective_summary()
    has_trigger_override = bool(trigger_overrides)

    def row(prompt):
        original_expected = prompt.get("expected_result")
        item = trigger_overrides.get(prompt.get("id")) or {}
        expected = item.get("expected_result") or original_expected
        actual = prompt.get("actual_result")
        matched = ((expected == "should_trigger" and actual == "triggered") or
                   (expected == "should_not_trigger" and actual == "not_triggered"))
        rate = prompt.get("trigger_rate")
        repeats = tr.get("trigger_repeats")
        count = round(rate * repeats) if isinstance(rate, (int, float)) and isinstance(repeats, int) else None
        actual_label = ("Triggered" if actual == "triggered" else "Did not trigger")
        if count is not None:
            actual_label += " ({}/{})".format(count, repeats)
        expected_label = "Should trigger" if expected == "should_trigger" else "Should not trigger"
        original_label = ("Should trigger" if original_expected == "should_trigger"
                          else "Should not trigger")
        if item:
            expected_html = (
                '<s class="was">{old}</s> <b class="ovr">{new}</b>{note}'
            ).format(old=esc(original_label), new=esc(expected_label), note=_note(item.get("note")))
        else:
            expected_html = esc(expected_label)
        mixed = isinstance(rate, (int, float)) and rate not in (0, 1)
        cls = ("ok" if matched else "bad") + (" mixed" if mixed else "")
        return ('<tr class="{cls}"><td>{txt}</td><td>{expected}</td>'
                '<td class="actual">{actual}</td><td>{control}</td></tr>').format(
            cls=cls, txt=esc(prompt.get("prompt_text")),
            expected=expected_html, actual=esc(actual_label),
            control=ov_trigger(prompt.get("id")))

    rows = "".join(row(p) for p in (tr.get("prompts") or []))
    accuracy_badge = '<span class="badge">accuracy {}</span>'.format(
        pct(effective.get("accuracy")))
    if has_trigger_override:
        accuracy_badge += ' <span class="was">original {}</span>'.format(pct(s.get("accuracy")))
    return (
        '<section class="card"><h2>2 · Actual triggering '
        '{acc}</h2>'
        '<p class="muted">Expected Result comes from the skill author&apos;s evals.json and can be '
        'overridden by the user during scenario review. Actual Result is observed from Copilot skill '
        'invocation events.</p>'
        '<p class="muted">matches {c}/{tot} · false-positive {fp} · false-negative {fn} · '
        '{rep} actual Copilot runs per prompt</p>'
        '<table class="trigger-table"><thead><tr><th>Prompt</th><th>Expected Result</th>'
        '<th>Actual Result</th><th class="fbcol">Override Expected Result</th>'
        '</tr></thead><tbody>{rows}</tbody></table>'
        '<div class="fb-overall">Overall feedback on triggering: {ov}</div></section>'
    ).format(acc=accuracy_badge, c=esc(effective.get("matches")),
             tot=esc(effective.get("total")),
             fp=esc(effective.get("false_positive")),
             fn=esc(effective.get("false_negative")), rows=rows,
             rep=esc(tr.get("trigger_repeats")), ov=fb("triggering", "overall", ""))


def _bar(label, summary):
    mean = (summary or {}).get("mean")
    w = (mean * 100) if isinstance(mean, (int, float)) else 0
    return ('<div class="barrow"><span class="barlab">{lab}</span>'
            '<span class="bar"><span class="fill {cls}" style="width:{w:.0f}%"></span></span>'
            '<span class="barval">{v} <small>±{sd}</small></span></div>').format(
        lab=esc(label), cls=("with" if "with" in label.lower() else "without"),
        w=w, v=pct(mean), sd=fmt_num((summary or {}).get("stddev")))


def section_value(vc, override=None):
    if not vc:
        return not_available("3 · Value comparison")
    override = override or {}
    summ = vc.get("summary") or {}
    ai_verdict = summ.get("verdict")
    if override.get("value_verdict"):
        vhead = ('<span class="verdict {cls}">{hv}</span>'
                 '<span class="was">AI: {ai}</span>').format(
            cls=_verdict_class(override.get("value_verdict")),
            hv=esc(override.get("value_verdict")), ai=esc(ai_verdict))
    else:
        vhead = '<span class="verdict {cls}">{v}</span>'.format(
            cls=_verdict_class(ai_verdict), v=esc(ai_verdict))
    tasks_html = []
    for t in (vc.get("tasks") or []):
        runrows = "".join(
            '<tr><td>{cfg}</td><td class="num">#{ri}</td><td class="num">{pr}</td>'
            '<td class="muted">{p}/{tot}</td></tr>'.format(
                cfg=esc(r.get("configuration")), ri=esc(r.get("run_index")),
                pr=pct((r.get("score") or {}).get("pass_rate")),
                p=esc((r.get("score") or {}).get("passed")), tot=esc((r.get("score") or {}).get("total")))
            for r in (t.get("runs") or []))
        tasks_html.append(
            '<div class="task"><h3>{tid} <span class="verdict {vc2}">{verdict}</span></h3>'
            '<p class="muted">{prompt}</p>{wbar}{wobar}'
            '<p class="delta">delta {delta}</p>'
            '<details><summary>per-run scores</summary><table><thead><tr><th>Config</th>'
            '<th>Run</th><th>Pass-rate</th><th>Passed</th></tr></thead><tbody>{rr}</tbody></table></details>'
            '</div>'.format(
                tid=esc(t.get("id")), verdict=esc(t.get("verdict")),
                vc2=_verdict_class(t.get("verdict")), prompt=esc(t.get("prompt")),
                wbar=_bar("with skill", t.get("with_skill_summary")),
                wobar=_bar("without skill", t.get("without_skill_summary")),
                delta=fmt_num(t.get("delta")), rr=runrows))
    return (
        '<section class="card"><h2>3 · Value comparison {vhead}</h2>'
        '<p class="muted">repeats {rep} per configuration · overall delta {delta} · confidence {conf}</p>'
        '{tasks}<div class="fb-overall">Feedback on the value verdict: {ov}'
        '<span class="ovctl">Override verdict: <select id="ov-value-verdict" class="fb-stance">'
        '<option value="">(no override)</option><option value="skill helps">skill helps</option>'
        '<option value="no clear value">no clear value</option><option value="skill hurts">skill hurts</option>'
        '</select></span></div></section>'
    ).format(vhead=vhead,
             rep=esc(vc.get("value_repeats")), delta=fmt_num(summ.get("delta")),
             conf=esc(summ.get("confidence")), tasks="".join(tasks_html),
             ov=fb("value", "overall", ""))


def _verdict_class(v):
    v = str(v or "").lower()
    if "help" in v:
        return "good"
    if "hurt" in v:
        return "bad"
    return "neutral"


def override_banner(override, result):
    """Top 'final word' card summarizing the author's authoritative overrides."""
    if not _has_override(override):
        return ""
    rows = []
    ai_v = ((result.get("value_comparison") or {}).get("summary") or {}).get("verdict")
    if override.get("value_verdict"):
        rows.append('<li>Value verdict → <span class="verdict {cls}">{hv}</span>'
                    '<span class="was">was: {ai}</span>{n}</li>'.format(
            cls=_verdict_class(override.get("value_verdict")), hv=esc(override.get("value_verdict")),
            ai=esc(ai_v), n=_note(override.get("value_note"))))
    if override.get("static_average") is not None:
        ai_avg = (result.get("static_quality") or {}).get("average_score")
        rows.append('<li>Static average → <b>{hv} / 5</b><span class="was">was: {ai}</span>{n}</li>'.format(
            hv=esc(override.get("static_average")), ai=esc(ai_avg), n=_note(override.get("static_note"))))
    for d in (override.get("dimension_overrides") or []):
        rows.append('<li>Dimension <b>{name}</b> → <b>{s}</b>{n}</li>'.format(
            name=esc(d.get("name")), s=esc(d.get("score")), n=_note(d.get("note"))))
    for t in (override.get("trigger_overrides") or []):
        label = ("Should trigger" if t.get("expected_result") == "should_trigger"
                 else "Should not trigger")
        rows.append('<li>Trigger <b>{pid}</b> Expected Result → <b>{label}</b>{n}</li>'.format(
            pid=esc(t.get("prompt_id")), label=esc(label), n=_note(t.get("note"))))
    for f in (override.get("finding_overrides") or []):
        act = f.get("action")
        label = ("re-severity → " + str(f.get("severity"))) if act == "reseverity" else act
        rows.append('<li>Finding <b>{fid}</b> → {label}{n}</li>'.format(
            fid=esc(f.get("finding_id")), label=esc(label), n=_note(f.get("note"))))
    overall = (override.get("overall_note") or "").strip()
    who = esc(override.get("author") or "the author")
    return (
        '<section class="card override"><h2>⚑ Author override — final word '
        '<span class="badge">authoritative where set</span></h2>'
        '<p class="muted">Recorded by {who}. These values are authoritative; the original '
        'labels and AI scores stay visible below and in result.json for a traceable audit trail.</p>'
        '{on}<ul class="imps">{rows}</ul></section>'
    ).format(who=who, on=('<p class="assess">{}</p>'.format(esc(overall)) if overall else ""),
             rows="".join(rows))


def section_findings(cf, override=None):
    if not cf:
        return not_available("4 · Prioritized fixes")
    override = override or {}
    fov = {f.get("finding_id"): f for f in (override.get("finding_overrides") or [])}
    order = cf.get("priority_order") or []
    by_id = {f.get("id"): f for f in (cf.get("findings") or [])}
    ordered = [by_id[i] for i in order if i in by_id] or (cf.get("findings") or [])

    def item(f):
        o = fov.get(f.get("id"))
        sev = f.get("severity")
        extra, bn = "", ""
        if o:
            act = o.get("action")
            if act == "dismiss":
                extra, bn = " dismissed", ' <span class="ovr">dismissed by author</span>'
            elif act == "reseverity" and o.get("severity"):
                sev = o.get("severity")
                bn = ' <span class="ovr">author severity: {}</span>'.format(esc(o.get("severity")))
            elif act == "keep":
                bn = ' <span class="ovr">kept by author</span>'
            bn += _note(o.get("note"))
        return (
            '<li class="finding{extra}"><span class="pill {sev}">{sev}</span> <b>{title}</b>{bn}'
            '<div class="rec">{rec}</div><div class="muted">{rat} · modes: {modes}{p2}</div>'
            '<div class="fb-fitem">{fbctl}{ovctl}</div></li>').format(
            extra=extra, sev=esc(sev), title=esc(f.get("title")), bn=bn,
            rec=esc(f.get("recommendation")), rat=esc(f.get("rationale")),
            modes=esc(", ".join(f.get("source_modes") or [])),
            p2=(' · phase2' if f.get("phase2_actionable") else ''),
            fbctl=fb("finding", f.get("id", ""), ""), ovctl=ov_find(f.get("id", "")))
    items = "".join(item(f) for f in ordered)
    return (
        '<section class="card"><h2>4 · Prioritized fixes</h2>'
        '<p class="assess">{assess}</p><ol class="findings">{items}</ol></section>'
    ).format(assess=esc(cf.get("overall_assessment")), items=items or '<li class="muted">None</li>')


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
CSS = """
:root{--bg:#0f1420;--card:#171d2b;--ink:#e6e9ef;--muted:#8b94a7;--line:#2a3346;
--good:#3fb27f;--bad:#e2625b;--neutral:#c9a227;--with:#5b8def;--without:#7a8295;--accent:#5b8def}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;padding:24px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:0 0 12px}h3{font-size:14px;margin:14px 0 6px}
.muted{color:var(--muted)}.wrap{max-width:1040px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin:16px 0}
.card.na{opacity:.7}.meta{display:flex;flex-wrap:wrap;gap:8px 18px;color:var(--muted);font-size:13px}
.meta b{color:var(--ink)}.badge{background:#223;border:1px solid var(--line);border-radius:20px;
padding:2px 10px;font-size:12px;color:var(--muted);font-weight:400}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:6px 8px;
border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}.cols{display:flex;gap:18px;flex-wrap:wrap}
.cols>div{flex:1;min-width:320px}.radarwrap{flex:0 0 420px;max-width:100%}
.radar{width:100%;height:auto}.ring{fill:none;stroke:var(--line)}.axis{stroke:var(--line)}
.shape{fill:rgba(91,141,239,.28);stroke:var(--accent);stroke-width:2}
.rlabel{fill:var(--muted);font-size:11px}.imps{padding-left:0;list-style:none}.imps li{margin:6px 0}
.pill{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;text-transform:uppercase}
.pill.high{background:rgba(226,98,91,.2);color:var(--bad)}.pill.medium{background:rgba(201,162,39,.2);color:var(--neutral)}
.pill.low{background:rgba(63,178,127,.18);color:var(--good)}
tr.ok td.ok{color:var(--good)}tr.bad td.bad{color:var(--bad)}
.trigger-table tr.ok td{background:rgba(63,178,127,.08)}
.trigger-table tr.bad td{background:rgba(226,98,91,.09)}
.trigger-table tr.ok td.actual{color:var(--good);font-weight:600}
.trigger-table tr.bad td.actual{color:var(--bad);font-weight:600}
.trigger-table tr.mixed td:first-child{box-shadow:inset 3px 0 var(--neutral)}
.barrow{display:flex;align-items:center;gap:10px;margin:6px 0}.barlab{flex:0 0 110px;color:var(--muted)}
.bar{flex:1;height:14px;background:#0c1019;border-radius:7px;overflow:hidden}
.fill{display:block;height:100%}.fill.with{background:var(--with)}.fill.without{background:var(--without)}
.barval{flex:0 0 90px;text-align:right;font-variant-numeric:tabular-nums}
.delta{font-weight:600;margin:6px 0}.task{border-top:1px solid var(--line);padding-top:10px;margin-top:10px}
.verdict{border-radius:6px;padding:1px 8px;font-size:12px}.verdict.good{background:rgba(63,178,127,.2);color:var(--good)}
.verdict.bad{background:rgba(226,98,91,.2);color:var(--bad)}.verdict.neutral{background:rgba(201,162,39,.2);color:var(--neutral)}
.findings{padding-left:18px}.finding{margin:10px 0}.rec{margin:3px 0}.assess{margin:0 0 10px}
.fb{display:inline-flex;gap:4px;align-items:center}.fb-stance,.fb-note{background:#0c1019;color:var(--ink);
border:1px solid var(--line);border-radius:6px;padding:2px 6px;font-size:12px}.fb-note{width:160px}
.fb-overall{margin-top:12px;color:var(--muted)}.fb-label{color:var(--muted);font-size:12px}
.fbcol{width:1%}.fbbar{position:sticky;bottom:0;margin-top:18px;text-align:center}
button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 18px;font-size:14px;cursor:pointer}
body.feedback-off .fb,body.feedback-off .fb-overall,body.feedback-off .fbcol,
body.feedback-off .fb-fitem,body.feedback-off .fbbar,body.feedback-off .ov-dim,
body.feedback-off .ov-trigger-wrap{display:none}
.was{color:var(--muted);text-decoration:line-through;font-size:12px;margin-left:6px}
.ovr{color:var(--accent);font-size:12px}
.card.override{border-color:var(--accent);background:#1a2233}
.finding.dismissed{opacity:.55}.finding.dismissed b{text-decoration:line-through}
.ovctl{margin-left:12px;color:var(--muted);font-size:12px}.ov-dim{margin-left:6px}
.ovflag{color:var(--muted);margin-right:10px}.fbbar input{margin-right:6px}
.ov-notice{background:#12303a;border:1px solid var(--accent);border-radius:8px;padding:10px 12px;margin:0 0 12px;text-align:left}.ov-notice .warn{color:var(--neutral)}
"""

JS = """
function __dl(obj,name){var b=new Blob([JSON.stringify(obj,null,2)],{type:'application/json'});
  var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;a.click();}
function __buildFeedback(){
  var R=window.__RESULT__;
  function one(el){var s=el.querySelector('.fb-stance').value,n=el.querySelector('.fb-note').value.trim();
    if(!s&&!n)return null;return {stance:s||'annotate',note:n};}
  var fb={schema_version:R.schema_version,target_skill:(R.metadata||{}).target_skill,
    sweep_ref:'results/'+((R.metadata||{}).sweep_id||''),created_at:new Date().toISOString(),
    static_quality_feedback:{},triggering_feedback:{},value_comparison_feedback:{},
    findings_feedback:[],overall_notes:document.getElementById('overall_notes').value.trim()};
  document.querySelectorAll('.fb').forEach(function(el){
    var sec=el.dataset.section,id=el.dataset.id,v=one(el);if(!v)return;
    if(sec==='static'){if(id==='overall')fb.static_quality_feedback.overall=v;
      else{(fb.static_quality_feedback.dimensions=fb.static_quality_feedback.dimensions||[]).push({name:id,stance:v.stance,note:v.note});}}
    else if(sec==='triggering'){if(id==='overall')fb.triggering_feedback.overall=v;}
    else if(sec==='value'){fb.value_comparison_feedback={stance:v.stance,note:v.note};}
    else if(sec==='finding'){fb.findings_feedback.push({finding_id:id,stance:v.stance,note:v.note});}
  });
  return fb;
}
function __hasOv(ov){return !!(ov.value_verdict||ov.static_average!==null||ov.dimension_overrides.length||ov.trigger_overrides.length||ov.finding_overrides.length||ov.overall_note);}
function saveFeedback(){
  var fb=__buildFeedback();
  var el=document.getElementById('ov-flag');var flag=!!(el&&el.checked);
  fb.override_requested=flag;
  fb.override=flag?__buildOverride():null;
  __dl(fb,'feedback.json');
  __notice(flag,fb.override);
}
function __noteFor(sec,id){var el=document.querySelector('.fb[data-section="'+sec+'"][data-id="'+id+'"]');
  return el?el.querySelector('.fb-note').value.trim():'';}
function __val(id){var el=document.getElementById(id);return el?el.value:'';}
function __buildOverride(){
  var R=window.__RESULT__,M=R.metadata||{};
  var ov={schema_version:R.schema_version,target_skill:M.target_skill,
    sweep_ref:'results/'+(M.sweep_id||''),created_at:new Date().toISOString(),author:__val('ov-author').trim(),
    value_verdict:null,value_note:'',static_average:null,static_note:'',
    dimension_overrides:[],trigger_overrides:[],finding_overrides:[],overall_note:document.getElementById('overall_notes').value.trim()};
  if(__val('ov-value-verdict')){ov.value_verdict=__val('ov-value-verdict');ov.value_note=__noteFor('value','overall');}
  if(__val('ov-static-avg')!==''){ov.static_average=parseFloat(__val('ov-static-avg'));ov.static_note=__noteFor('static','overall');}
  document.querySelectorAll('.ov-dim').forEach(function(el){if(el.value!==''){
    ov.dimension_overrides.push({name:el.dataset.name,score:(el.value==='N/A'?'N/A':parseInt(el.value,10)),note:__noteFor('static',el.dataset.name)});}});
  document.querySelectorAll('.ov-trigger').forEach(function(el){if(el.value!==''){
    var n=document.querySelector('.ov-trigger-note[data-id="'+el.dataset.id+'"]');
    ov.trigger_overrides.push({prompt_id:el.dataset.id,expected_result:el.value,note:n?n.value.trim():''});}});
  document.querySelectorAll('.ov-find').forEach(function(el){if(el.value!==''){
    var o={finding_id:el.dataset.id,action:el.value,note:__noteFor('finding',el.dataset.id)};
    if(el.value==='reseverity'){var s=document.querySelector('.ov-find-sev[data-id="'+el.dataset.id+'"]');o.severity=s?s.value:'';}
    ov.finding_overrides.push(o);}});
  return ov;
}
function __notice(flag,ov){
  var box=document.getElementById('ov-notice');if(!box)return;var m;
  if(flag){var empty=!__hasOv(ov);
    m='<b>&#9989; Saved feedback.json to your Downloads folder</b> &mdash; with an override request.'
      +(empty?' <span class="warn">(You ticked \u201coverride\u201d but set no verdict, score, Expected Result, or finding disposition &mdash; set one and save again.)</span>':'')
      +'<br><b>Go back to Copilot and say: &ldquo;apply my override&rdquo;.</b> Copilot will write &amp; validate human_override.json and regenerate this report so your verdict is the final word (result.json stays untouched).';
  }else{
    m='<b>&#9989; Saved feedback.json to your Downloads folder.</b>'
      +'<br><b>Go back to Copilot and say: &ldquo;store my feedback&rdquo;.</b> Copilot will file it with this sweep as advisory only &mdash; it will <b>not</b> override the AI judge (result.json stays untouched).';
  }
  box.innerHTML=m;box.style.display='block';if(box.scrollIntoView)box.scrollIntoView({behavior:'smooth',block:'center'});
}
"""


def _script_safe_json(value):
    return (json.dumps(value).replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("&", "\\u0026"))


def build_html(result, override=None):
    override = override or {}
    md = result.get("metadata") or {}
    cfg = md.get("config") or {}
    models = md.get("evaluator_models") or {}
    sv = result.get("schema_version", "")
    fb_on = bool(md.get("feedback_enabled"))
    jg = md.get("judge_guidance") or {}
    flags = ""
    if any((jg.get(k) or "").strip() for k in ("general", "static", "value")):
        flags += '<span class="badge ovr">guided</span>'
    if md.get("scenarios_reviewed"):
        flags += '<span class="badge ovr">scenarios reviewed</span>'
    meta = (
        '<div class="meta"><span><b>{skill}</b></span>'
        '<span>schema <b>{sv}</b></span><span>sweep <b>{sid}</b></span>'
        '<span>{created}</span><span>runtime <b>{rt}</b></span>'
        '<span>evals <b>{es}</b></span>'
        '<span>models <b>{ex}</b>/<b>{an}</b>/<b>{ju}</b></span>'
        '<span>value repeats <b>{vr}</b></span><span>trigger repeats <b>{tr}</b></span>'
        '<span>mode <b>{bm}</b></span>{flags}</div>'
        '<p class="muted">{desc}</p>'
    ).format(skill=esc(md.get("target_skill")), sv=esc(sv), sid=esc(md.get("sweep_id")),
             created=esc(md.get("created_at")), rt=esc(md.get("eval_runtime")),
             es=esc(md.get("evals_source")), ex=esc(models.get("executor")),
             an=esc(models.get("analyzer")), ju=esc(models.get("judge")),
             vr=esc(cfg.get("value_repeats")), tr=esc(cfg.get("trigger_repeats")),
             bm=esc(cfg.get("baseline_mode")), flags=flags,
             desc=esc(md.get("target_skill_description")))
    body = (
        meta
        + override_banner(override, result)
        + section_static(result.get("static_quality"), override)
        + section_triggering(result.get("triggering"), override)
        + section_value(result.get("value_comparison"), override)
        + section_findings(result.get("consolidated_findings"), override)
        + '<section class="card fb-overall-card"><h2>Overall notes</h2>'
          '<textarea id="overall_notes" rows="3" style="width:100%" '
          'placeholder="overall feedback (optional)"></textarea></section>'
        + '<div class="fbbar"><div id="ov-notice" class="ov-notice" style="display:none"></div>'
          '<label class="ovflag"><input type="checkbox" id="ov-flag" checked> Make this an authoritative override (final word)</label>'
          '<input id="ov-author" class="fb-note" placeholder="your alias (for overrides)" style="width:150px">'
          '<button onclick="saveFeedback()">Save feedback</button>'
          '<p class="muted">Downloads feedback.json. The override box is ticked by default (authoritative) \u2014 untick it for advisory feedback only; then finish in Copilot as the notice explains.</p></div>'
    )
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>skill-eval · {skill}</title><style>{css}</style></head>"
        "<body class='{cls}'><div class=wrap><h1>skill-eval report</h1>{body}</div>"
        "<script>window.__RESULT__={data};{js}</script></body></html>"
    ).format(skill=esc(md.get("target_skill")), css=CSS,
             cls=("" if fb_on else "feedback-off"), body=body,
             data=_script_safe_json(result), js=JS)


def main(argv):
    p = argparse.ArgumentParser(description="Render a self-contained skill-eval report.")
    p.add_argument("result", help="path to result.json")
    p.add_argument("--out", default=None, help="output report.html path")
    p.add_argument("--override", default=None,
                   help="path to human_override.json (default: sibling of result.json, if present)")
    args = p.parse_args(argv)
    try:
        with open(args.result, "r", encoding="utf-8") as fh:
            result = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write("cannot read result.json: {}\n".format(exc))
        return 1
    sv = result.get("schema_version")
    if sv != LAYOUT_FOR_SCHEMA:
        sys.stderr.write("warning: layout is for {}, result is {}\n".format(LAYOUT_FOR_SCHEMA, sv))
    res_dir = os.path.dirname(os.path.abspath(args.result))
    out = args.out or os.path.join(res_dir, "report.html")
    ov_path = args.override or os.path.join(res_dir, "human_override.json")
    override = {}
    if os.path.exists(ov_path):
        try:
            with open(ov_path, "r", encoding="utf-8") as fh:
                override = json.load(fh)
        except (OSError, ValueError) as exc:
            sys.stderr.write("warning: cannot read {}: {}\n".format(ov_path, exc))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build_html(result, override))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
