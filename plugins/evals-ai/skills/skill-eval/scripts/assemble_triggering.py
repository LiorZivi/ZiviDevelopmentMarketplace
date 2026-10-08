#!/usr/bin/env python3
"""Assemble three-run trigger observations into the skill-eval/v5 triggering block."""

import argparse
import json
import os
import sys


def assemble(evals, runs_root, repeats):
    prompts = []
    false_positive = 0
    false_negative = 0
    matches = 0
    for prompt in evals.get("trigger_prompts") or []:
        prompt_id = prompt["id"]
        runs = []
        triggered_count = 0
        for index in range(1, repeats + 1):
            run_dir = os.path.join(runs_root, "{}-{}".format(prompt_id, index))
            observation_path = os.path.join(run_dir, "observation.json")
            with open(observation_path, "r", encoding="utf-8") as fh:
                observation = json.load(fh)
            if not observation.get("success"):
                raise ValueError("trigger run failed: {}".format(observation_path))
            triggered = bool(observation.get("triggered"))
            triggered_count += int(triggered)
            prefix = "trigger-runs/{}-{}".format(prompt_id, index)
            runs.append({
                "run_index": index,
                "triggered": triggered,
                "events_ref": prefix + "/events.jsonl",
                "response_ref": prefix + "/response.md",
                "duration_s": observation.get("duration_s"),
                "errors": observation.get("errors", 0),
            })
        actual = "triggered" if triggered_count >= (repeats // 2 + 1) else "not_triggered"
        expected = prompt["intent"]
        matched = ((expected == "should_trigger" and actual == "triggered") or
                   (expected == "should_not_trigger" and actual == "not_triggered"))
        matches += int(matched)
        false_positive += int(expected == "should_not_trigger" and actual == "triggered")
        false_negative += int(expected == "should_trigger" and actual == "not_triggered")
        prompts.append({
            "id": prompt_id,
            "prompt_text": prompt["prompt_text"],
            "expected_result": expected,
            "actual_result": actual,
            "trigger_rate": triggered_count / repeats,
            "runs": runs,
        })
    total = len(prompts)
    return {
        "trigger_repeats": repeats,
        "prompts": prompts,
        "summary": {
            "matches": matches,
            "mismatches": total - matches,
            "total": total,
            "accuracy": matches / total if total else 0,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
    }


def main(argv):
    parser = argparse.ArgumentParser(description="Assemble observed skill trigger runs.")
    parser.add_argument("evals")
    parser.add_argument("runs_root")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    with open(args.evals, "r", encoding="utf-8") as fh:
        evals = json.load(fh)
    block = assemble(evals, os.path.abspath(args.runs_root), args.repeats)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(block, fh, indent=2)
        fh.write("\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
