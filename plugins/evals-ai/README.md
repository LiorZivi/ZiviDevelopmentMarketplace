# evals-ai

`evals-ai` evaluates whether an AI skill is clearly authored, triggers for the right requests, and
improves task outcomes compared with a skill-free baseline. It is diagnose-only: it reports findings
and never rewrites the evaluated skill.

The plugin is domain-neutral. It carries no product, organization, repository, or service knowledge;
all evaluation evidence comes from the target skill, author-approved test cases, and isolated runs.

## Capability

### skill-eval

Runs one repeatable quality sweep with three complementary modes:

1. **Static quality** — an independent analyzer scores the skill's authored instructions.
2. **Actual triggering** — each approved prompt runs three times and records real skill invocation
   events rather than predicting whether the skill would trigger.
3. **Value comparison** — isolated with-skill and without-skill runs are graded blindly against
   checkable expectations.

The sweep produces a validated `result.json` and a self-contained `report.html` with prioritized
fixes, feedback controls, and optional authoritative human overrides.

## Usage

Evaluate a workspace skill:

```text
/zivi-development-marketplace:skill-eval .github/skills/api-reviewer
```

Evaluate a skill inside another plugin:

```text
/zivi-development-marketplace:skill-eval plugins/example-plugin/skills/release-notes
```

You can also ask naturally, for example: "Evaluate whether the release-notes skill actually helps."
If a bare skill name matches multiple directories, the evaluator asks which one to use.

## Prerequisites

- Python 3.9 or later
- Git
- GitHub Copilot CLI available as `copilot` and already authenticated

The analyzer and judge inherit the runtime-selected model. Isolated trigger and value runs also use
the Copilot CLI default model unless the author explicitly supplies an executor override.

## Local artifacts

Reusable cases live beside the evaluated skill; generated run evidence remains local:

```text
<target-skill>/evals/evals.json
<target-skill>/evals/results/<timestamp>/result.json
<target-skill>/evals/results/<timestamp>/report.html
```

When the target is inside a Git repository, the evaluator adds the results directory to that
repository's local `.git/info/exclude`. It does not modify the tracked `.gitignore`.

## Structure

```text
evals-ai/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   ├── skill-eval-analyzer.md
│   └── skill-eval-judge.md
├── skills/
│   └── skill-eval/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
├── plugin.json
└── README.md
```
