#!/usr/bin/env python3
"""
eval_schema.py - the single source of truth for skill-eval's data contract.

Stdlib only. Defines the versioned shapes of reusable cases and local artifacts (result.json,
evals.json, feedback.json, human_override.json), validates them, exposes a minimal
SKILL.md frontmatter check (so skill-eval needs no external validator), and
computes a content-independent structural signature used to prove that two
different skills' results share one identical shape (cross-skill comparability).

CLI:
    python eval_schema.py result  <path/to/result.json>
    python eval_schema.py evals    <path/to/evals.json>
    python eval_schema.py feedback <path/to/feedback.json>
    python eval_schema.py override  <path/to/human_override.json>
    python eval_schema.py frontmatter <path/to/SKILL.md>
    python eval_schema.py signature <path/to/result.json>
Exit code 0 = valid, 1 = invalid (errors printed to stderr).
"""

import json
import re
import sys

SCHEMA_VERSION = "skill-eval/v5"
EVALS_VERSION = "skill-eval-evals/v1"
DIMENSION_SET_VERSION = "skill-eval-dims/v2"

# The five fixed static-rubric dimensions. A dimension may instead score NA_SCORE
# ("N/A") when it genuinely does not apply to the skill; N/A dimensions are excluded
# from the average (see references/static-rubric.md).
STATIC_DIMENSIONS = [
    "Instruction Clarity",
    "Behavioral Completeness",
    "Safety & Guardrails",
    "User Experience",
    "Robustness",
]
NA_SCORE = "N/A"

_TRIGGER_INTENTS = ("should_trigger", "should_not_trigger")
_TRIGGER_ACTUAL = ("triggered", "not_triggered")
_CONFIGS = ("with_skill", "without_skill")
_VERDICTS = ("skill helps", "no clear value", "skill hurts")
_SEVERITIES = ("high", "medium", "low")
_STANCES = ("agree", "disagree", "edit", "annotate")
_OVERRIDE_ACTIONS = ("keep", "dismiss", "reseverity")
_BASELINE_MODES = ("isolated", "in-context")


# ---------------------------------------------------------------------------
# small validation helpers (no third-party deps)
# ---------------------------------------------------------------------------
def _err(errors, path, msg):
    errors.append("{}: {}".format(path or "<root>", msg))


def _need(obj, key, path, errors, types=None):
    """Require obj[key] to exist (and optionally be one of `types`). Returns value or None."""
    if not isinstance(obj, dict):
        _err(errors, path, "expected an object")
        return None
    if key not in obj:
        _err(errors, path, "missing required key '{}'".format(key))
        return None
    val = obj[key]
    if types is not None and not isinstance(val, types):
        _err(errors, "{}.{}".format(path, key), "expected {}".format(_type_names(types)))
    return val


def _type_names(types):
    if isinstance(types, tuple):
        return " or ".join(t.__name__ for t in types)
    return types.__name__


def _enum(val, allowed, path, errors):
    if val is not None and val not in allowed:
        _err(errors, path, "value '{}' not in {}".format(val, list(allowed)))


def _in_range(val, lo, hi, path, errors):
    if isinstance(val, (int, float)):
        if val < lo or val > hi:
            _err(errors, path, "value {} out of range [{}, {}]".format(val, lo, hi))
    elif val is not None:
        _err(errors, path, "expected a number")


# ---------------------------------------------------------------------------
# result.json
# ---------------------------------------------------------------------------
def validate_result(obj):
    """Return (ok, errors) for a result.json object."""
    errors = []
    if not isinstance(obj, dict):
        return False, ["<root>: expected an object"]

    sv = _need(obj, "schema_version", "", errors)
    if sv is not None and sv != SCHEMA_VERSION:
        _err(errors, "schema_version", "expected '{}', got '{}'".format(SCHEMA_VERSION, sv))

    _validate_metadata(obj.get("metadata"), "metadata", errors)
    _validate_static(obj.get("static_quality"), "static_quality", errors)
    _validate_triggering(obj.get("triggering"), "triggering", errors)
    _validate_value(obj.get("value_comparison"), "value_comparison", errors)
    _validate_findings(obj.get("consolidated_findings"), "consolidated_findings", errors)
    _validate_runs(obj.get("runs"), "runs", errors)

    for key in ("metadata", "static_quality", "triggering", "value_comparison",
                "consolidated_findings", "runs"):
        if key not in obj:
            _err(errors, "", "missing required key '{}'".format(key))
    return (len(errors) == 0), errors


def _validate_metadata(md, path, errors):
    if md is None:
        _err(errors, path, "missing")
        return
    for k in ("target_skill", "target_skill_path", "target_skill_description",
              "sweep_id", "created_at", "eval_runtime"):
        _need(md, k, path, errors)
    models = _need(md, "evaluator_models", path, errors, dict)
    if isinstance(models, dict):
        for role in ("executor", "analyzer", "judge"):
            _need(models, role, path + ".evaluator_models", errors)
    es = _need(md, "evals_source", path, errors)
    _enum(es, ("generated", "reused"), path + ".evals_source", errors)
    cfg = _need(md, "config", path, errors, dict)
    if isinstance(cfg, dict):
        for k in ("trigger_prompts_total", "trigger_repeats",
                  "comparison_tasks", "value_repeats"):
            _need(cfg, k, path + ".config", errors)
        _enum(_need(cfg, "baseline_mode", path + ".config", errors),
              _BASELINE_MODES, path + ".config.baseline_mode", errors)
    if "feedback_enabled" not in (md or {}):
        _err(errors, path, "missing required key 'feedback_enabled'")
    elif not isinstance(md.get("feedback_enabled"), bool):
        _err(errors, path + ".feedback_enabled", "expected a boolean")
    # judge_guidance: the author's pre-eval steer for the analyzer/judge. Fixed string
    # keys (empty = none) keep the metadata shape — and the cross-skill signature — stable.
    jg = _need(md, "judge_guidance", path, errors, dict)
    if isinstance(jg, dict):
        for k in ("general", "static", "value"):
            _need(jg, k, path + ".judge_guidance", errors)
    if "scenarios_reviewed" not in (md or {}):
        _err(errors, path, "missing required key 'scenarios_reviewed'")
    elif not isinstance(md.get("scenarios_reviewed"), bool):
        _err(errors, path + ".scenarios_reviewed", "expected a boolean")


def _validate_static(sq, path, errors):
    if sq is None:
        _err(errors, path, "missing")
        return
    _need(sq, "dimension_set_version", path, errors)
    _need(sq, "scale", path, errors)
    _need(sq, "average_score", path, errors)
    dims = _need(sq, "dimensions", path, errors, list)
    if isinstance(dims, list):
        for i, d in enumerate(dims):
            dp = "{}.dimensions[{}]".format(path, i)
            _need(d, "name", dp, errors)
            score = _need(d, "score", dp, errors)
            if score != NA_SCORE:
                _in_range(score, 1, 5, dp + ".score", errors)
            _need(d, "rationale", dp, errors)
            _need(d, "evidence", dp, errors)
    ti = _need(sq, "top_improvements", path, errors, list)
    if isinstance(ti, list):
        for i, t in enumerate(ti):
            tp = "{}.top_improvements[{}]".format(path, i)
            _need(t, "text", tp, errors)
            _need(t, "priority", tp, errors)
            _need(t, "dimension", tp, errors)


def _validate_triggering(tr, path, errors):
    if tr is None:
        _err(errors, path, "missing")
        return
    repeats = _need(tr, "trigger_repeats", path, errors, int)
    if isinstance(repeats, int) and repeats < 1:
        _err(errors, path + ".trigger_repeats", "must be at least 1")
    prompts = _need(tr, "prompts", path, errors, list)
    if isinstance(prompts, list):
        for i, p in enumerate(prompts):
            pp = "{}.prompts[{}]".format(path, i)
            _need(p, "id", pp, errors)
            _need(p, "prompt_text", pp, errors)
            _enum(_need(p, "expected_result", pp, errors),
                  _TRIGGER_INTENTS, pp + ".expected_result", errors)
            _enum(_need(p, "actual_result", pp, errors),
                  _TRIGGER_ACTUAL, pp + ".actual_result", errors)
            _in_range(_need(p, "trigger_rate", pp, errors), 0, 1,
                      pp + ".trigger_rate", errors)
            runs = _need(p, "runs", pp, errors, list)
            if isinstance(runs, list):
                if isinstance(repeats, int) and len(runs) != repeats:
                    _err(errors, pp + ".runs",
                         "expected {} runs, got {}".format(repeats, len(runs)))
                for j, run in enumerate(runs):
                    rp = "{}.runs[{}]".format(pp, j)
                    _need(run, "run_index", rp, errors, int)
                    if "triggered" not in (run or {}):
                        _err(errors, rp, "missing required key 'triggered'")
                    elif not isinstance(run.get("triggered"), bool):
                        _err(errors, rp + ".triggered", "expected a boolean")
                    _need(run, "events_ref", rp, errors)
                    _need(run, "response_ref", rp, errors)
                    _need(run, "duration_s", rp, errors, (int, float))
                    _need(run, "errors", rp, errors, int)
    summ = _need(tr, "summary", path, errors, dict)
    if isinstance(summ, dict):
        for k in ("matches", "mismatches", "total", "accuracy",
                  "false_positive", "false_negative"):
            _need(summ, k, path + ".summary", errors)


def _validate_value(vc, path, errors):
    if vc is None:
        _err(errors, path, "missing")
        return
    _need(vc, "value_repeats", path, errors)
    tasks = _need(vc, "tasks", path, errors, list)
    if isinstance(tasks, list):
        for i, t in enumerate(tasks):
            tp = "{}.tasks[{}]".format(path, i)
            _need(t, "id", tp, errors)
            _need(t, "prompt", tp, errors)
            _need(t, "expectations", tp, errors, list)
            runs = _need(t, "runs", tp, errors, list)
            if isinstance(runs, list):
                for j, r in enumerate(runs):
                    rp = "{}.runs[{}]".format(tp, j)
                    _need(r, "run_index", rp, errors)
                    _enum(_need(r, "configuration", rp, errors), _CONFIGS, rp + ".configuration", errors)
                    sc = _need(r, "score", rp, errors, dict)
                    if isinstance(sc, dict):
                        _in_range(_need(sc, "pass_rate", rp + ".score", errors), 0, 1, rp + ".score.pass_rate", errors)
                        _need(sc, "passed", rp + ".score", errors)
                        _need(sc, "total", rp + ".score", errors)
                    _need(r, "output_ref", rp, errors)
                    _need(r, "transcript_ref", rp, errors)
            _validate_summary(t.get("with_skill_summary"), tp + ".with_skill_summary", errors)
            _validate_summary(t.get("without_skill_summary"), tp + ".without_skill_summary", errors)
            _need(t, "delta", tp, errors)
            _enum(_need(t, "verdict", tp, errors), _VERDICTS, tp + ".verdict", errors)
    summ = _need(vc, "summary", path, errors, dict)
    if isinstance(summ, dict):
        _need(summ, "delta", path + ".summary", errors)
        _enum(_need(summ, "verdict", path + ".summary", errors), _VERDICTS, path + ".summary.verdict", errors)
        _need(summ, "confidence", path + ".summary", errors)


def _validate_summary(s, path, errors):
    if s is None:
        _err(errors, path, "missing")
        return
    for k in ("mean", "stddev", "n"):
        _need(s, k, path, errors)


def _validate_findings(cf, path, errors):
    if cf is None:
        _err(errors, path, "missing")
        return
    findings = _need(cf, "findings", path, errors, list)
    if isinstance(findings, list):
        for i, f in enumerate(findings):
            fp = "{}.findings[{}]".format(path, i)
            _need(f, "id", fp, errors)
            _need(f, "title", fp, errors)
            _enum(_need(f, "severity", fp, errors), _SEVERITIES, fp + ".severity", errors)
            _need(f, "source_modes", fp, errors, list)
            _need(f, "recommendation", fp, errors)
            _need(f, "rationale", fp, errors)
            if "phase2_actionable" not in (f or {}):
                _err(errors, fp, "missing required key 'phase2_actionable'")
    _need(cf, "priority_order", path, errors, list)
    _need(cf, "overall_assessment", path, errors)


def _validate_runs(runs, path, errors):
    if runs is None:
        _err(errors, path, "missing")
        return
    if not isinstance(runs, list):
        _err(errors, path, "expected a list")
        return
    for i, r in enumerate(runs):
        rp = "{}[{}]".format(path, i)
        _need(r, "run_id", rp, errors)
        _enum(_need(r, "configuration", rp, errors), _CONFIGS, rp + ".configuration", errors)
        _need(r, "task_id", rp, errors)
        _need(r, "run_index", rp, errors)
        _need(r, "transcript_ref", rp, errors)
        _need(r, "output_ref", rp, errors)
        _need(r, "metrics", rp, errors, dict)


# ---------------------------------------------------------------------------
# evals.json
# ---------------------------------------------------------------------------
def validate_evals(obj):
    errors = []
    if not isinstance(obj, dict):
        return False, ["<root>: expected an object"]
    ev = _need(obj, "evals_version", "", errors)
    if ev is not None and ev != EVALS_VERSION:
        _err(errors, "evals_version", "expected '{}', got '{}'".format(EVALS_VERSION, ev))
    _need(obj, "target_skill", "", errors)
    _need(obj, "generated_at", "", errors)
    vts = _need(obj, "value_tasks", "", errors, list)
    if isinstance(vts, list):
        if len(vts) == 0:
            _err(errors, "value_tasks", "must contain at least one task")
        for i, t in enumerate(vts):
            tp = "value_tasks[{}]".format(i)
            _need(t, "id", tp, errors)
            _need(t, "prompt", tp, errors)
            exp = _need(t, "expectations", tp, errors, list)
            if isinstance(exp, list) and len(exp) == 0:
                _err(errors, tp + ".expectations", "must contain at least one expectation")
    tps = _need(obj, "trigger_prompts", "", errors, list)
    if isinstance(tps, list):
        if len(tps) == 0:
            _err(errors, "trigger_prompts", "must contain at least one prompt")
        for i, p in enumerate(tps):
            pp = "trigger_prompts[{}]".format(i)
            _need(p, "id", pp, errors)
            _need(p, "prompt_text", pp, errors)
            _enum(_need(p, "intent", pp, errors), _TRIGGER_INTENTS, pp + ".intent", errors)
    return (len(errors) == 0), errors


# ---------------------------------------------------------------------------
# feedback.json
# ---------------------------------------------------------------------------
def validate_feedback(obj):
    errors = []
    if not isinstance(obj, dict):
        return False, ["<root>: expected an object"]
    sv = _need(obj, "schema_version", "", errors)
    if sv is not None and sv != SCHEMA_VERSION:
        _err(errors, "schema_version", "expected '{}', got '{}'".format(SCHEMA_VERSION, sv))
    _need(obj, "target_skill", "", errors)
    _need(obj, "sweep_ref", "", errors)
    _need(obj, "created_at", "", errors)
    # the per-mode feedback blocks are optional in content but the keys must exist
    for k in ("static_quality_feedback", "triggering_feedback",
              "value_comparison_feedback", "overall_notes"):
        if k not in obj:
            _err(errors, "", "missing required key '{}'".format(k))
    ff = _need(obj, "findings_feedback", "", errors, list)
    if isinstance(ff, list):
        for i, f in enumerate(ff):
            fp = "findings_feedback[{}]".format(i)
            _need(f, "finding_id", fp, errors)
            _enum(_need(f, "stance", fp, errors), _STANCES, fp + ".stance", errors)
            _need(f, "note", fp, errors)
    return (len(errors) == 0), errors


# ---------------------------------------------------------------------------
# human_override.json — the author's authoritative, traceable override of the AI
# judge. A separate local file (like feedback.json) so result.json stays the
# pristine AI record; when present it is the final word (references/author-response.md).
# Every field is optional: a null scalar or empty list means "no override here", and
# result.json's original value stands.
# ---------------------------------------------------------------------------
def validate_override(obj):
    errors = []
    if not isinstance(obj, dict):
        return False, ["<root>: expected an object"]
    sv = _need(obj, "schema_version", "", errors)
    if sv is not None and sv != SCHEMA_VERSION:
        _err(errors, "schema_version", "expected '{}', got '{}'".format(SCHEMA_VERSION, sv))
    _need(obj, "target_skill", "", errors)
    _need(obj, "sweep_ref", "", errors)
    _need(obj, "created_at", "", errors)
    # keys must exist (null/empty allowed) so the report reads a predictable shape
    for k in ("value_verdict", "value_note", "static_average", "static_note",
              "dimension_overrides", "trigger_overrides", "finding_overrides", "overall_note"):
        if k not in obj:
            _err(errors, "", "missing required key '{}'".format(k))
    if obj.get("value_verdict") is not None:
        _enum(obj.get("value_verdict"), _VERDICTS, "value_verdict", errors)
    if obj.get("static_average") is not None:
        _in_range(obj.get("static_average"), 1, 5, "static_average", errors)
    do = obj.get("dimension_overrides")
    if do is not None and not isinstance(do, list):
        _err(errors, "dimension_overrides", "expected a list")
    elif isinstance(do, list):
        for i, d in enumerate(do):
            dp = "dimension_overrides[{}]".format(i)
            _need(d, "name", dp, errors)
            score = _need(d, "score", dp, errors)
            if score is not None and score != NA_SCORE:
                _in_range(score, 1, 5, dp + ".score", errors)
    to = obj.get("trigger_overrides")
    if to is not None and not isinstance(to, list):
        _err(errors, "trigger_overrides", "expected a list")
    elif isinstance(to, list):
        for i, t in enumerate(to):
            tp = "trigger_overrides[{}]".format(i)
            _need(t, "prompt_id", tp, errors)
            _enum(_need(t, "expected_result", tp, errors),
                  _TRIGGER_INTENTS, tp + ".expected_result", errors)
            _need(t, "note", tp, errors)
    fo = obj.get("finding_overrides")
    if fo is not None and not isinstance(fo, list):
        _err(errors, "finding_overrides", "expected a list")
    elif isinstance(fo, list):
        for i, f in enumerate(fo):
            fp = "finding_overrides[{}]".format(i)
            _need(f, "finding_id", fp, errors)
            action = _need(f, "action", fp, errors)
            _enum(action, _OVERRIDE_ACTIONS, fp + ".action", errors)
            if action == "reseverity":
                _enum(f.get("severity"), _SEVERITIES, fp + ".severity", errors)
    return (len(errors) == 0), errors


# ---------------------------------------------------------------------------
# SKILL.md frontmatter (skill-eval's own self-contained validator)
# ---------------------------------------------------------------------------
def validate_frontmatter(text):
    """
    Minimal SKILL.md frontmatter check: a leading '---' YAML block containing a
    non-empty `name` and a non-empty `description` of at most 1024 characters.
    Avoids any YAML dependency. Returns (ok, errors).
    """
    errors = []
    if not isinstance(text, str):
        return False, ["<root>: expected SKILL.md text"]
    m = re.match(r"^\ufeff?---\s*\n(.*?)\n---\s*(\n|$)", text, re.DOTALL)
    if not m:
        return False, ["frontmatter: no leading '---' YAML block found"]
    block = m.group(1)

    name = _scalar_field(block, "name")
    if not name:
        _err(errors, "frontmatter", "missing or empty 'name'")

    desc = _scalar_field(block, "description")
    if not desc:
        _err(errors, "frontmatter", "missing or empty 'description'")
    elif len(desc) > 1024:
        _err(errors, "frontmatter", "description is {} chars (max 1024)".format(len(desc)))
    return (len(errors) == 0), errors


def _scalar_field(block, key):
    """
    Extract a frontmatter scalar that may be inline ('key: value'), quoted, or a
    folded/literal block scalar ('key: >' / 'key: |' followed by indented lines).
    Returns the collapsed text, or '' if absent/empty.
    """
    lines = block.split("\n")
    pat = re.compile(r"^" + re.escape(key) + r":\s*(.*)$")
    for i, line in enumerate(lines):
        mm = pat.match(line)
        if not mm:
            continue
        inline = mm.group(1).strip()
        if inline in (">", "|", ">-", "|-", ">+", "|+"):
            collected = []
            for cont in lines[i + 1:]:
                if cont.strip() == "":
                    collected.append("")
                    continue
                if re.match(r"^\s+\S", cont):
                    collected.append(cont.strip())
                else:
                    break
            return " ".join(x for x in collected if x).strip()
        if (inline.startswith('"') and inline.endswith('"')) or \
           (inline.startswith("'") and inline.endswith("'")):
            inline = inline[1:-1]
        return inline.strip()
    return ""


# ---------------------------------------------------------------------------
# structural signature (cross-skill comparability)
# ---------------------------------------------------------------------------
def structural_signature(obj):
    """
    A content-independent key skeleton. Two conformant results for ANY two skills
    must yield the same signature, proving identical structure. Values are ignored;
    dict keys are sorted; a list is represented by the merged skeleton of its
    elements (so element count never affects the signature).
    """
    return _sig(obj)


def _sig(obj):
    if isinstance(obj, dict):
        return "{" + ",".join("{}:{}".format(k, _sig(obj[k])) for k in sorted(obj.keys())) + "}"
    if isinstance(obj, list):
        merged = {}
        order = []
        for el in obj:
            s = _sig(el)
            if s not in merged:
                merged[s] = True
                order.append(s)
        return "[" + "|".join(order) + "]"
    # all scalars collapse to a single placeholder so values never matter
    return "*"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
_VALIDATORS = {
    "result": validate_result,
    "evals": validate_evals,
    "feedback": validate_feedback,
    "override": validate_override,
}


def _main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    kind, path = argv[1], argv[2]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        sys.stderr.write("cannot read {}: {}\n".format(path, exc))
        return 1

    if kind == "frontmatter":
        ok, errors = validate_frontmatter(raw)
    elif kind == "signature":
        try:
            print(structural_signature(json.loads(raw)))
            return 0
        except ValueError as exc:
            sys.stderr.write("invalid JSON: {}\n".format(exc))
            return 1
    elif kind in _VALIDATORS:
        try:
            obj = json.loads(raw)
        except ValueError as exc:
            sys.stderr.write("invalid JSON: {}\n".format(exc))
            return 1
        ok, errors = _VALIDATORS[kind](obj)
    else:
        sys.stderr.write("unknown kind '{}'\n".format(kind))
        return 2

    if ok:
        print("OK: {} is a valid {} ({})".format(path, kind, SCHEMA_VERSION))
        return 0
    sys.stderr.write("INVALID {} ({} error(s)):\n".format(path, len(errors)))
    for e in errors:
        sys.stderr.write("  - {}\n".format(e))
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
