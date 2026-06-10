#!/usr/bin/env python3
"""Render a self-contained summary.html from results.json produced by
run_trigger_eval.py."""
import argparse
import html
import json
from pathlib import Path


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Trigger Eval — {skill}</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: ui-sans-serif, -apple-system, system-ui, sans-serif; max-width: 1100px;
       margin: 24px auto; padding: 0 16px; line-height: 1.45; }}
h1 {{ margin: 0 0 8px; }}
.sub {{ color: #777; margin-bottom: 16px; font-size: 13px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 12px; margin: 16px 0 24px; }}
.metric {{ padding: 12px 14px; border: 1px solid #8884; border-radius: 8px; }}
.metric .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #888; }}
.metric .value {{ font-size: 22px; font-weight: 600; margin-top: 4px; }}
.metric.good {{ background: #2ecc7115; }}
.metric.bad  {{ background: #e74c3c15; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #8883; vertical-align: top; }}
th {{ font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #777; }}
.q {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px;
      white-space: pre-wrap; max-width: 560px; }}
.tag {{ font-size: 11px; color: #888; margin-top: 4px; }}
.pass {{ color: #2ecc71; font-weight: 600; }}
.fail {{ color: #e74c3c; font-weight: 600; }}
.miss {{ background: #e74c3c10; }}
.bool-y {{ color: #2ecc71; font-weight: 600; }}
.bool-n {{ color: #888; }}
details summary {{ cursor: pointer; }}
.confusion {{ display: inline-grid; grid-template-columns: auto auto auto; gap: 0; margin: 12px 0;
              border: 1px solid #8884; }}
.confusion div {{ padding: 8px 12px; border: 1px solid #8884; min-width: 80px; text-align: center; }}
.confusion .hd {{ background: #8881; font-weight: 600; font-size: 12px; }}
</style>
<h1>Trigger Eval — <code>{skill}</code></h1>
<div class="sub">{total} queries · model: <code>{model}</code></div>

<div class="summary-grid">
  <div class="metric {acc_cls}"><div class="label">Accuracy</div>
    <div class="value">{acc_pct}% <span style="font-size:13px;font-weight:400;color:#888">({correct}/{total})</span></div></div>
  <div class="metric"><div class="label">Trigger recall</div>
    <div class="value">{recall}</div></div>
  <div class="metric"><div class="label">Non-trigger specificity</div>
    <div class="value">{spec}</div></div>
  <div class="metric {fp_cls}"><div class="label">False positives</div>
    <div class="value">{fp}</div></div>
  <div class="metric {fn_cls}"><div class="label">False negatives</div>
    <div class="value">{fn}</div></div>
</div>

<h3>Confusion matrix</h3>
<div class="confusion">
  <div class="hd"></div><div class="hd">predicted&nbsp;trigger</div><div class="hd">predicted&nbsp;skip</div>
  <div class="hd">should trigger</div><div>{tp}</div><div>{fn}</div>
  <div class="hd">should skip</div><div>{fp}</div><div>{tn}</div>
</div>

<h3>Results</h3>
<table>
<thead><tr>
  <th>#</th><th>Query</th><th>Expected</th><th>Triggered</th>
  <th>Skill invoked</th><th>Time (s)</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>

<h3>Per-log details</h3>
<p style="color:#888;font-size:12px">Raw JSONL streams from <code>copilot -p</code> are saved alongside this file under <code>logs/qNN.jsonl</code>.</p>
"""

ROW = """<tr class="{rowcls}">
  <td>{n}</td>
  <td><div class="q">{query}</div><div class="tag">{tag}</div></td>
  <td><span class="bool-{exp_b}">{exp}</span></td>
  <td><span class="bool-{trig_b}">{trig}</span></td>
  <td><code>{invoked}</code></td>
  <td>{elapsed}</td>
</tr>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    data = json.loads(args.results.read_text(encoding="utf-8"))
    s = data["summary"]
    results = data["results"]

    rows = []
    for i, r in enumerate(results, 1):
        miss = not r["correct"]
        rows.append(ROW.format(
            n=i,
            rowcls="miss" if miss else "",
            query=html.escape(r["query"]),
            tag=html.escape(r.get("tag", "")),
            exp="trigger" if r["should_trigger"] else "skip",
            exp_b="y" if r["should_trigger"] else "n",
            trig="yes" if r["triggered"] else "no",
            trig_b="y" if r["triggered"] else "n",
            invoked=html.escape(r.get("skill_invoked") or "—"),
            elapsed=r["elapsed_seconds"],
        ))

    acc = s["accuracy"] * 100
    page = PAGE.format(
        skill=html.escape(s["skill_name"]),
        total=s["total"],
        correct=s["correct"],
        acc_pct=f"{acc:.0f}",
        acc_cls="good" if acc >= 80 else ("bad" if acc < 50 else ""),
        model=html.escape(s.get("model") or "(default)"),
        recall=("—" if s["trigger_recall"] is None
                else f"{s['trigger_recall']*100:.0f}%"),
        spec=("—" if s["non_trigger_specificity"] is None
              else f"{s['non_trigger_specificity']*100:.0f}%"),
        fp=s["false_positives"], fn=s["false_negatives"],
        tp=s["true_positives"], tn=s["true_negatives"],
        fp_cls="bad" if s["false_positives"] else "good",
        fn_cls="bad" if s["false_negatives"] else "good",
        rows="\n".join(rows),
    )
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
