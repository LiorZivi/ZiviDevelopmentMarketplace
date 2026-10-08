#!/usr/bin/env python3
"""
new_sweep.py - scaffold one co-located sweep folder under the evaluated skill.

Stdlib only. Creates
    <target-skill>/evals/results/<YYYYMMDD-HHMMSS>/runs/
and writes a skeleton result.json (schema_version + fully-populated metadata,
including empty judge_guidance and scenarios_reviewed=false for the pre-eval
review steps, + null mode sections + empty runs registry) for the orchestrator
and the executor to fill. Prints the absolute path of the created results folder
on stdout so the orchestrator knows where to write everything else.

Usage:
    python new_sweep.py <target-skill-dir> [options]

Options:
    --executor-model M      (default: runtime-default)
    --analyzer-model M      (default: runtime-default)
    --judge-model M         (default: runtime-default)
    --value-repeats N       (default: 2)
    --trigger-prompts N     (default: 10)
    --trigger-repeats N     (default: 3)
    --comparison-tasks N    (default: 2)
    --eval-runtime S        (default: copilot-cli)
    --evals-source S        generated|reused (default: generated)
    --baseline-mode S       isolated|in-context (default: isolated) — Mode-3 env strategy
    --feedback S            on|off (default: on)
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

import eval_schema  # sibling module; keeps skill-eval self-contained


def _utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_target_description(target_dir):
    skill_md = os.path.join(target_dir, "SKILL.md")
    try:
        with open(skill_md, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    # reuse the frontmatter parser from the contract module
    m = eval_schema.re.match(r"^\ufeff?---\s*\n(.*?)\n---\s*(\n|$)", text, eval_schema.re.DOTALL)
    if not m:
        return ""
    return eval_schema._scalar_field(m.group(1), "description")


def _ensure_local_results_excluded(target_dir):
    """Keep generated run evidence local without changing tracked ignore files."""
    found = subprocess.run(
        ["git", "-C", target_dir, "rev-parse", "--show-toplevel"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if found.returncode != 0:
        return None
    repo = os.path.abspath(found.stdout.strip())
    results_root = os.path.join(target_dir, "evals", "results")
    located = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--git-path", "info/exclude"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if located.returncode != 0 or not located.stdout.strip():
        raise OSError("could not locate the repository's local Git exclude file")
    exclude_path = located.stdout.strip()
    if not os.path.isabs(exclude_path):
        exclude_path = os.path.join(repo, exclude_path)

    rel = os.path.relpath(results_root, repo).replace("\\", "/").strip("/")
    pattern = "/" + rel + "/"
    try:
        with open(exclude_path, "r", encoding="utf-8", errors="replace") as fh:
            existing = {line.strip() for line in fh}
    except FileNotFoundError:
        existing = set()
    if pattern in existing:
        return None
    ignored = subprocess.run(
        ["git", "-C", repo, "check-ignore", "-q", "--no-index", "--", results_root],
        capture_output=True,
    )
    if ignored.returncode == 0:
        return None
    os.makedirs(os.path.dirname(exclude_path), exist_ok=True)
    needs_newline = os.path.isfile(exclude_path) and os.path.getsize(exclude_path) > 0
    with open(exclude_path, "a", encoding="utf-8") as fh:
        if needs_newline:
            fh.write("\n")
        fh.write("# evals-ai local evaluation results\n")
        fh.write(pattern + "\n")
    return pattern


def _skeleton(target_dir, sweep_id, args):
    target_dir = os.path.normpath(target_dir)
    target_name = os.path.basename(target_dir.rstrip(os.sep))
    return {
        "schema_version": eval_schema.SCHEMA_VERSION,
        "metadata": {
            "target_skill": target_name,
            "target_skill_path": target_dir.replace("\\", "/"),
            "target_skill_description": _read_target_description(target_dir),
            "sweep_id": sweep_id,
            "created_at": _utc_now_iso(),
            "evaluator_models": {
                "executor": args.executor_model,
                "analyzer": args.analyzer_model,
                "judge": args.judge_model,
            },
            "eval_runtime": args.eval_runtime,
            "evals_source": args.evals_source,
            "feedback_enabled": (args.feedback == "on"),
            # pre-eval author inputs (Steps 2-3); empty/false until captured.
            # Fixed shape keeps the signature stable.
            "judge_guidance": {"general": "", "static": "", "value": ""},
            "scenarios_reviewed": False,
            "config": {
                "trigger_prompts_total": args.trigger_prompts,
                "trigger_repeats": args.trigger_repeats,
                "comparison_tasks": args.comparison_tasks,
                "value_repeats": args.value_repeats,
                "baseline_mode": args.baseline_mode,
            },
        },
        # null placeholders — the orchestrator fills these as each mode completes,
        # then validates the assembled result before generating the report.
        "static_quality": None,
        "triggering": None,
        "value_comparison": None,
        "consolidated_findings": None,
        "runs": [],
    }


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Scaffold a co-located skill-eval sweep folder.")
    p.add_argument("target_dir", help="path to the evaluated skill's directory")
    p.add_argument("--executor-model", default="runtime-default")
    p.add_argument("--analyzer-model", default="runtime-default")
    p.add_argument("--judge-model", default="runtime-default")
    p.add_argument("--value-repeats", type=int, default=2, dest="value_repeats")
    p.add_argument("--trigger-prompts", type=int, default=10, dest="trigger_prompts")
    p.add_argument("--trigger-repeats", type=int, default=3, dest="trigger_repeats")
    p.add_argument("--comparison-tasks", type=int, default=2, dest="comparison_tasks")
    p.add_argument("--eval-runtime", default="copilot-cli", dest="eval_runtime")
    p.add_argument("--evals-source", default="generated", choices=["generated", "reused"], dest="evals_source")
    p.add_argument("--baseline-mode", default="isolated", choices=["isolated", "in-context"], dest="baseline_mode")
    p.add_argument("--feedback", default="on", choices=["on", "off"])
    return p.parse_args(argv)


def main(argv):
    args = _parse_args(argv)
    target_dir = os.path.abspath(args.target_dir)
    if not os.path.isdir(target_dir):
        sys.stderr.write("target skill dir not found: {}\n".format(target_dir))
        return 1

    sweep_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir = os.path.join(target_dir, "evals", "results", sweep_id)
    runs_dir = os.path.join(results_dir, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    _ensure_local_results_excluded(target_dir)

    skeleton = _skeleton(target_dir, sweep_id, args)
    result_path = os.path.join(results_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(skeleton, fh, indent=2)
        fh.write("\n")

    # the path the orchestrator needs
    print(results_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
