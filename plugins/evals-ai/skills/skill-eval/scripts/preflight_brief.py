#!/usr/bin/env python3
"""
preflight_brief.py - print a read-only pre-flight brief of an evals.json so the
author can approve or edit the test cases BEFORE Mode 2 / Mode 3 run (skill-eval
Step 3; see references/preflight-review.md). Stdlib only. Modifies nothing.

Usage:
    python preflight_brief.py <path/to/evals.json>
"""

import json
import sys


def _wrap(text, width=92, indent="        "):
    """Collapse whitespace and soft-wrap to `width`, continuation lines indented."""
    words = " ".join(str(text).split()).split(" ")
    out, line = [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = word if not line else line + " " + word
    if line:
        out.append(line)
    return ("\n" + indent).join(out)


def brief(evals):
    lines = []
    target = evals.get("target_skill", "<unknown>")
    tasks = evals.get("value_tasks", []) or []
    prompts = evals.get("trigger_prompts", []) or []

    lines.append("PRE-FLIGHT BRIEF - {}".format(target))
    lines.append("(exactly what will run; approve, or ask to edit any item, before evaluation starts)")
    lines.append("")

    lines.append("VALUE-COMPARISON TASKS (Mode 3 - run WITH and WITHOUT the skill) - {} task(s)".format(len(tasks)))
    if not tasks:
        lines.append("  (none - nothing to compare)")
    for i, t in enumerate(tasks, 1):
        lines.append("  [{}] id: {}".format(i, t.get("id", "?")))
        lines.append("      prompt: {}".format(_wrap(t.get("prompt", ""))))
        lines.append("      expectations (the blind judge grades pass/fail against these):")
        for e in (t.get("expectations", []) or []):
            lines.append("        - {}".format(_wrap(e, indent="          ")))
        lines.append("")

    lines.append("ACTUAL TRIGGERING PROMPTS (Mode 2 - each runs 3 isolated times) - {} prompt(s)".format(len(prompts)))
    for intent in ("should_trigger", "should_not_trigger"):
        group = [p for p in prompts if p.get("intent") == intent]
        lines.append("  Expected Result = {} ({}):".format(intent, len(group)))
        for p in group:
            lines.append("    - {}: {}".format(p.get("id", "?"), _wrap(p.get("prompt_text", ""), indent="        ")))
    stray = [p for p in prompts if p.get("intent") not in ("should_trigger", "should_not_trigger")]
    if stray:
        lines.append("  (uncategorized Expected Result - fix before running):")
        for p in stray:
            lines.append("    - {}: expected_result={!r}".format(
                p.get("id", "?"), p.get("intent")))
    lines.append("")

    lines.append("Approve to run, or tell me what to change (reword a prompt, fix an expectation,")
    lines.append("flip an Expected Result, add/remove a case). Any edit is re-validated before anything runs.")
    return "\n".join(lines)


def main(argv):
    if len(argv) < 1:
        sys.stderr.write("usage: python preflight_brief.py <evals.json>\n")
        return 2
    try:
        with open(argv[0], "r", encoding="utf-8") as fh:
            evals = json.load(fh)
    except OSError as exc:
        sys.stderr.write("cannot read {}: {}\n".format(argv[0], exc))
        return 1
    except ValueError as exc:
        sys.stderr.write("invalid JSON in {}: {}\n".format(argv[0], exc))
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    print(brief(evals))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
