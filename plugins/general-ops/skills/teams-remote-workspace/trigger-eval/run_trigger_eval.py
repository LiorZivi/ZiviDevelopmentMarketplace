#!/usr/bin/env python3
"""Run trigger evaluation for a Copilot CLI skill.

For each query in the eval set, invokes `copilot -p` with --available-tools=skill
(no side effects possible) and parses the JSONL stream to detect whether the
target skill was invoked.

Output: results.json + (optionally) summary.html via render_summary.py.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def detect_trigger(jsonl_path: Path, target_skill: str) -> tuple[bool, str | None]:
    """Return (triggered, first_skill_invoked_name)."""
    if not jsonl_path.exists():
        return (False, None)
    for raw in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "tool.execution_start":
            continue
        data = ev.get("data", {}) or {}
        if data.get("toolName") != "skill":
            continue
        invoked = (data.get("arguments") or {}).get("skill", "")
        return (invoked == target_skill, invoked or None)
    return (False, None)


def run_query(query: str, target_skill: str, log_dir: Path, idx: int,
              timeout: int, model: str | None) -> dict:
    log_path = log_dir / f"q{idx:02d}.jsonl"
    cmd = [
        "copilot",
        "-p", query,
        "--output-format", "json",
        "--available-tools=skill",
        "--allow-all-tools",
    ]
    if model:
        cmd.extend(["--model", model])

    start = time.time()
    try:
        with log_path.open("wb") as f:
            proc = subprocess.run(
                cmd, stdout=f, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        exit_code = -1
        timed_out = True
    elapsed = time.time() - start

    triggered, invoked = detect_trigger(log_path, target_skill)
    return {
        "query": query,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 1),
        "triggered": triggered,
        "skill_invoked": invoked,
        "log_file": log_path.name,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-set", required=True, type=Path)
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--model", default=None,
                    help="Model id (e.g. claude-opus-4.7). Defaults to user config.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Run only first N queries (for smoke testing).")
    args = ap.parse_args()

    eval_set = json.loads(args.eval_set.read_text(encoding="utf-8"))
    if args.limit:
        eval_set = eval_set[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = args.out_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    results = []
    for i, item in enumerate(eval_set):
        query = item["query"]
        expected = bool(item.get("should_trigger", False))
        tag = item.get("tag", "")
        print(f"[{i+1:2d}/{len(eval_set)}] expect={expected} tag={tag}", flush=True)
        r = run_query(query, args.skill_name, log_dir, i, args.timeout, args.model)
        r["should_trigger"] = expected
        r["tag"] = tag
        r["correct"] = (r["triggered"] == expected)
        results.append(r)
        print(f"           -> triggered={r['triggered']} correct={r['correct']} "
              f"({r['elapsed_seconds']}s)", flush=True)

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    pos = [r for r in results if r["should_trigger"]]
    neg = [r for r in results if not r["should_trigger"]]
    tp = sum(1 for r in pos if r["triggered"])
    fn = len(pos) - tp
    fp = sum(1 for r in neg if r["triggered"])
    tn = len(neg) - fp

    summary = {
        "skill_name": args.skill_name,
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "true_positives": tp,
        "false_negatives": fn,
        "false_positives": fp,
        "true_negatives": tn,
        "trigger_recall": round(tp / len(pos), 4) if pos else None,
        "non_trigger_specificity": round(tn / len(neg), 4) if neg else None,
        "model": args.model,
    }
    out = {"summary": summary, "results": results}
    (args.out_dir / "results.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
