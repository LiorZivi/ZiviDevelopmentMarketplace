import json
import os
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import assemble_triggering
import eval_schema
import generate_report
import new_sweep
import run_isolated_arm
import run_trigger_check
import stage_skill


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ReportTests(unittest.TestCase):
    def test_result_json_cannot_close_inline_script(self):
        marker = "</script><script>window.__report_probe=1</script>"
        result = {"schema_version": "skill-eval/v5",
                  "metadata": {"target_skill": "probe", "target_skill_description": marker}}
        self.assertEqual(json.loads(generate_report._script_safe_json(result)), result)

        class ScriptCounter(HTMLParser):
            def __init__(self):
                super().__init__()
                self.count = 0

            def handle_starttag(self, tag, attrs):
                if tag == "script":
                    self.count += 1

        html = generate_report.build_html(result)
        parsed = ScriptCounter()
        parsed.feed(html)
        self.assertEqual(parsed.count, 1)
        self.assertNotIn("<script>window.__report_probe", html)

    def test_trigger_report_uses_expected_and_actual_without_verdict_column(self):
        triggering = {
            "trigger_repeats": 3,
            "prompts": [
                {
                    "id": "positive",
                    "prompt_text": "use the skill",
                    "expected_result": "should_trigger",
                    "actual_result": "triggered",
                    "trigger_rate": 2 / 3,
                    "runs": [],
                },
                {
                    "id": "negative",
                    "prompt_text": "do not use the skill",
                    "expected_result": "should_not_trigger",
                    "actual_result": "triggered",
                    "trigger_rate": 1.0,
                    "runs": [],
                },
            ],
            "summary": {
                "matches": 1, "mismatches": 1, "total": 2, "accuracy": 0.5,
                "false_positive": 1, "false_negative": 0,
            },
        }
        html = generate_report.section_triggering(triggering)
        self.assertIn("<th>Expected Result</th><th>Actual Result</th>", html)
        self.assertNotIn("<th>Verdict</th>", html)
        self.assertNotIn("<th>Predicted</th>", html)
        self.assertIn("Triggered (2/3)", html)
        self.assertIn('class="ok mixed"', html)
        self.assertIn('class="bad"', html)
        self.assertIn("Override Expected Result", html)
        self.assertIn('data-id="positive"', html)

        override = {
            "trigger_overrides": [{
                "prompt_id": "negative",
                "expected_result": "should_trigger",
                "note": "This authoring request should load the workflow skill first.",
            }]
        }
        overridden = generate_report.section_triggering(triggering, override)
        self.assertIn("<s class=\"was\">Should not trigger</s>", overridden)
        self.assertIn("<b class=\"ovr\">Should trigger</b>", overridden)
        self.assertIn("matches 2/2", overridden)
        self.assertIn("false-positive 0", overridden)

    def test_trigger_override_schema_and_banner(self):
        override = {
            "schema_version": "skill-eval/v5",
            "target_skill": "probe",
            "sweep_ref": "results/test",
            "created_at": "2026-10-08T00:00:00Z",
            "author": "author",
            "value_verdict": None,
            "value_note": "",
            "static_average": None,
            "static_note": "",
            "dimension_overrides": [],
            "trigger_overrides": [{
                "prompt_id": "p1",
                "expected_result": "should_trigger",
                "note": "Expected routing corrected.",
            }],
            "finding_overrides": [],
            "overall_note": "",
        }
        ok, errors = eval_schema.validate_override(override)
        self.assertTrue(ok, errors)
        result = {
            "value_comparison": {"summary": {"verdict": "no clear value"}},
            "static_quality": {"average_score": 4.0},
        }
        banner = generate_report.override_banner(override, result)
        self.assertIn("Trigger <b>p1</b> Expected Result", banner)
        self.assertIn("Should trigger", banner)


class StagingTests(unittest.TestCase):
    def test_stages_skills_required_by_name_but_not_negated_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp) / "resources"
            skill = resources / "skills" / "reviewer"
            write(
                skill / "SKILL.md",
                "ALWAYS use the `map-helper` skill first.\n"
                "Do not use the `unrelated-helper` skill; use the shared **`audit-helper`** skill.\n"
                "The review invokes the `feedback-helper` skill once.\n",
            )
            write(resources / "skills" / "map-helper" / "SKILL.md", "map\n")
            write(resources / "skills" / "map-helper" / "evals" / "evals.json", "hidden\n")
            write(resources / "skills" / "unrelated-helper" / "SKILL.md", "unrelated\n")
            write(resources / "skills" / "audit-helper" / "SKILL.md", "audit\n")
            write(resources / "skills" / "feedback-helper" / "SKILL.md", "feedback\n")
            dest = Path(tmp) / "env"

            stager = stage_skill.Stager(str(resources), str(dest), 6)
            stager.stage_skill_dir(str(skill), 0)

            self.assertEqual(set(stager.manifest["skills"]),
                             {"reviewer", "map-helper", "audit-helper", "feedback-helper"})
            self.assertFalse((dest / ".github" / "skills" / "unrelated-helper").exists())
            self.assertFalse((dest / ".github" / "skills" / "map-helper" / "evals").exists())
            self.assertEqual(stager.manifest["unresolved"], [])

    def test_bundled_agent_wins_over_pool_and_evals_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp) / "resources"
            skill = resources / "skills" / "reviewer"
            dest = Path(tmp) / "env"
            write(skill / "SKILL.md", 'task(agent_type="worker")\n')
            write(skill / "plugin.json", json.dumps({"agents": "agents/"}))
            write(skill / "agents" / "worker.agent.md", "bundled knowledge_base/rules.md\n")
            write(skill / "evals" / "evals.json", "private test cases\n")
            write(resources / "agents" / "worker.agent.md", "wrong pool agent\n")
            write(resources / "knowledge_base" / "rules.md", "agent dependency\n")

            stager = stage_skill.Stager(str(resources), str(dest), 6)
            stager.stage_skill_dir(str(skill), 0)

            self.assertEqual(
                (dest / ".github" / "agents" / "worker.agent.md").read_text(encoding="utf-8"),
                "bundled knowledge_base/rules.md\n",
            )
            self.assertTrue((dest / ".github" / "knowledge_base" / "rules.md").exists())
            self.assertFalse((dest / ".github" / "skills" / "reviewer" / "evals").exists())
            self.assertEqual(stager.manifest["unresolved"], [])
            self.assertEqual(stager.manifest["agents"], ["worker.agent.md"])

    def test_global_agent_still_resolves_without_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp) / "resources"
            skill = resources / "skills" / "reviewer"
            dest = Path(tmp) / "env"
            write(skill / "SKILL.md", 'task(agent_type="pool-worker")\n')
            write(resources / "agents" / "pool-worker.agent.md", "pooled\n")

            stager = stage_skill.Stager(str(resources), str(dest), 6)
            stager.stage_skill_dir(str(skill), 0)

            self.assertEqual(
                (dest / ".github" / "agents" / "pool-worker.agent.md").read_text(encoding="utf-8"),
                "pooled\n",
            )
            self.assertEqual(stager.manifest["unresolved"], [])

    def test_plugin_agent_path_is_honored_and_cannot_escape_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp) / "resources"
            skill = resources / "skills" / "reviewer"
            write(skill / "SKILL.md", "custom reviewers\n")
            write(skill / "plugin.json", json.dumps({"agents": "reviewers/"}))
            write(skill / "reviewers" / "custom.agent.md", "custom agent\n")

            dest = Path(tmp) / "env"
            stager = stage_skill.Stager(str(resources), str(dest), 6)
            stager.stage_skill_dir(str(skill), 0)
            self.assertTrue((dest / ".github" / "agents" / "custom.agent.md").exists())

            write(skill / "plugin.json", json.dumps({"agents": "../../outside/"}))
            write(resources / "outside" / "foreign.agent.md", "not bundled\n")
            with self.assertRaisesRegex(ValueError, "escapes skill directory"):
                stage_skill.Stager(str(resources), str(Path(tmp) / "other"), 6).stage_skill_dir(
                    str(skill), 0
                )

    def test_missing_declared_agent_dir_is_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp) / "resources"
            skill = resources / "skills" / "reviewer"
            write(skill / "SKILL.md", "review\n")
            write(skill / "plugin.json", json.dumps({"agents": "missing/"}))
            with self.assertRaisesRegex(FileNotFoundError, "plugin agents directory not found"):
                stage_skill.Stager(str(resources), str(Path(tmp) / "env"), 6).stage_skill_dir(
                    str(skill), 0
                )

    def test_failed_agent_copy_is_not_reported_as_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp) / "resources"
            skill = resources / "skills" / "reviewer"
            write(skill / "SKILL.md", 'task(agent_type="leaf")\n')
            write(skill / "agents" / "leaf.agent.md", "bundled\n")
            with mock.patch.object(stage_skill, "_copy_file", return_value=False):
                with self.assertRaisesRegex(OSError, "could not stage agent leaf"):
                    stage_skill.Stager(str(resources), str(Path(tmp) / "env"), 6).stage_skill_dir(
                        str(skill), 0
                    )


class ArmTests(unittest.TestCase):
    def test_in_context_accepts_linked_worktree_git_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            write(repo / "README.md", "base\n")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            linked = Path(tmp) / "linked"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(linked), "HEAD"],
                           check=True, capture_output=True)
            skill = Path(tmp) / "resources" / "skills" / "reviewer"
            write(skill / "SKILL.md", "review\n")
            env = Path(tmp) / "arm"
            try:
                self.assertTrue((linked / ".git").is_file())
                run_isolated_arm.build_env_incontext(
                    "without", str(env), str(skill), str(linked), include_wip=False
                )
                self.assertTrue((env / "README.md").exists())
                run_isolated_arm.cleanup_env("in-context", str(env), str(linked))
            finally:
                if env.exists():
                    run_isolated_arm.cleanup_env("in-context", str(env), str(linked))
                subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(linked)],
                               check=True, capture_output=True)

    def test_hidden_bundled_agent_fails_preflight_without_running_copilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "resources" / "skills" / "reviewer"
            write(skill / "SKILL.md", 'task(agent_type="leaf")\n')
            write(skill / "plugin.json", json.dumps({"agents": "agents/"}))
            write(
                skill / "agents" / "leaf.agent.md",
                "---\nname: leaf\nuser-invocable: false\n"
                "disable-model-invocation: true\n---\nHidden leaf\n",
            )
            env_root = Path(tmp) / "scratch"
            env_root.mkdir()
            with mock.patch.object(run_isolated_arm, "run_arm") as executor:
                with self.assertRaisesRegex(SystemExit, "Cannot measure skill value.*leaf"):
                    run_isolated_arm.main([
                        "--arm", "with", "--mode", "isolated", "--skill-dir", str(skill),
                        "--task", "review", "--out", str(Path(tmp) / "output.md"),
                        "--env-root", str(env_root),
                    ])
                executor.assert_not_called()
            self.assertEqual(list(env_root.iterdir()), [])

    def test_invocable_agent_passes_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp)
            write(env / ".github" / "skills" / "reviewer" / "SKILL.md", 'task(agent_type="leaf")\n')
            write(
                env / ".github" / "agents" / "leaf.agent.md",
                "---\nname: leaf\nuser-invocable: true\n"
                "disable-model-invocation: false\n---\nReady\n",
            )
            self.assertEqual(run_isolated_arm.undispatchable_agents(str(env), "reviewer"), [])

    def test_in_context_ablates_stale_target_after_copying_wip(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            write(repo / "README.md", "base\n")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            write(repo / ".github" / "skills" / "reviewer" / "SKILL.md", "stale installed version\n")
            write(repo / ".github" / "skills" / "other" / "SKILL.md", "other skill\n")

            skill = Path(tmp) / "resources" / "skills" / "reviewer"
            write(skill / "SKILL.md", "current source version\n")
            write(skill / "plugin.json", json.dumps({"agents": "agents/"}))
            write(skill / "agents" / "leaf.agent.md", "current leaf\n")
            baseline = Path(tmp) / "without"
            with_skill = Path(tmp) / "with"
            try:
                run_isolated_arm.build_env_incontext(
                    "without", str(baseline), str(skill), str(repo), include_wip=True
                )
                run_isolated_arm.build_env_incontext(
                    "with", str(with_skill), str(skill), str(repo), include_wip=True
                )
                self.assertFalse((baseline / ".github" / "skills" / "reviewer").exists())
                self.assertEqual(
                    (with_skill / ".github" / "skills" / "reviewer" / "SKILL.md").read_text(
                        encoding="utf-8"
                    ),
                    "current source version\n",
                )
                self.assertTrue((with_skill / ".github" / "agents" / "leaf.agent.md").exists())
                for env in (baseline, with_skill):
                    self.assertTrue((env / ".github" / "skills" / "other" / "SKILL.md").exists())
            finally:
                for env in (baseline, with_skill):
                    if env.exists():
                        run_isolated_arm.cleanup_env("in-context", str(env), str(repo))

    def test_plugin_dir_is_passed_only_when_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "auth"
            write(source / "config.json", "{}")
            with mock.patch.dict(os.environ, {
                "COPILOT_HOME": str(source), "COPILOT_SKILLS_DIRS": "ambient",
                "COPILOT_CUSTOM_INSTRUCTIONS_DIRS": "ambient",
            }):
                for plugin in (None, str(Path(tmp) / ".github" / "skills" / "reviewer")):
                    fake = mock.Mock()
                    fake.returncode = 0
                    fake.communicate.return_value = ("review complete", "")
                    with mock.patch.object(run_isolated_arm, "_copilot_argv", side_effect=lambda argv: argv):
                        with mock.patch.object(run_isolated_arm, "_verify_skill_discovery"):
                            with mock.patch.object(run_isolated_arm.subprocess, "Popen", return_value=fake) as popen:
                                output, ok, error = run_isolated_arm.run_arm(
                                    tmp, "review this diff\nsecond line", "selected-executor", 3, plugin
                                )
                    self.assertEqual((output, ok, error), ("review complete", True, ""))
                    args = popen.call_args.args[0]
                    self.assertEqual("--plugin-dir" in args, plugin is not None)
                    self.assertEqual(args[args.index("--model") + 1], "selected-executor")
                    if plugin:
                        self.assertEqual(args[args.index("--plugin-dir") + 1], plugin)
                    child_env = popen.call_args.kwargs["env"]
                    self.assertEqual(child_env["COPILOT_PLUGIN_DIR_ONLY"], "true")
                    self.assertEqual(child_env["HOME"], child_env["USERPROFILE"])
                    self.assertNotEqual(child_env["COPILOT_HOME"], str(source))
                    self.assertFalse(Path(child_env["COPILOT_HOME"]).exists())
                    self.assertNotIn("COPILOT_SKILLS_DIRS", child_env)
                    self.assertNotIn("COPILOT_CUSTOM_INSTRUCTIONS_DIRS", child_env)
                    self.assertEqual((Path(tmp) / "TASK.md").read_text(encoding="utf-8"),
                                     "review this diff\nsecond line")

    def test_runtime_default_executor_model_is_not_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "auth"
            write(source / "config.json", "{}")
            fake = mock.Mock()
            fake.returncode = 0
            fake.communicate.return_value = ("done", "")
            with mock.patch.dict(os.environ, {"COPILOT_HOME": str(source)}):
                with mock.patch.object(run_isolated_arm, "_copilot_argv", side_effect=lambda argv: argv):
                    with mock.patch.object(run_isolated_arm, "_verify_skill_discovery"):
                        with mock.patch.object(run_isolated_arm.subprocess, "Popen", return_value=fake) as popen:
                            output, ok, error = run_isolated_arm.run_arm(
                                tmp, "review", "runtime-default", 3
                            )
            self.assertEqual((output, ok, error), ("done", True, ""))
            self.assertNotIn("--model", popen.call_args.args[0])

    def test_isolated_home_copies_only_auth_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write(source / "config.json", '{"auth": "test-only"}')
            write(source / "skills" / "ambient" / "SKILL.md", "must stay outside\n")
            private = Path(tmp) / "private"
            with mock.patch.dict(os.environ, {"COPILOT_HOME": str(source)}):
                child_env = run_isolated_arm._isolated_cli_environment(str(private))
            isolated = Path(child_env["COPILOT_HOME"])
            self.assertEqual((isolated / "config.json").read_text(encoding="utf-8"),
                             '{"auth": "test-only"}')
            self.assertFalse((isolated / "skills").exists())
            self.assertEqual(child_env["HOME"], str(private))

    def test_missing_auth_config_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {name: "" for name in
                   ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "COPILOT_PROVIDER_API_KEY")}
            env["COPILOT_HOME"] = str(Path(tmp) / "missing")
            with mock.patch.dict(os.environ, env):
                with self.assertRaisesRegex(RuntimeError, "no authentication config or token"):
                    run_isolated_arm._isolated_cli_environment(str(Path(tmp) / "private"))

    def test_rejects_ambient_skills_and_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "env"
            env.mkdir()
            target = env / ".github" / "skills" / "reviewer" / "SKILL.md"
            write(target, "review\n")
            builtin = {"name": "built-in", "path": "builtin:read", "source": "builtin"}
            staged = {"name": "reviewer", "path": str(target), "source": "project"}
            foreign = {"name": "ambient", "path": str(Path(tmp) / "personal" / "SKILL.md"),
                       "source": "personal-copilot"}
            extra_plugin = {"name": "plugin", "path": str(env / "installed" / "SKILL.md"),
                            "source": "plugin"}
            with mock.patch.object(run_isolated_arm, "_copilot_argv", side_effect=lambda argv: argv):
                with mock.patch.object(run_isolated_arm.subprocess, "run") as cli:
                    cli.return_value = subprocess.CompletedProcess([], 0, json.dumps([builtin]), "")
                    run_isolated_arm._verify_skill_discovery(str(env), {}, None, None)
                    with self.assertRaisesRegex(RuntimeError, "target skill is not discoverable"):
                        run_isolated_arm._verify_skill_discovery(str(env), {}, None, "reviewer")
                    cli.return_value = subprocess.CompletedProcess([], 0, json.dumps([builtin, staged]), "")
                    run_isolated_arm._verify_skill_discovery(str(env), {}, str(env), "reviewer")
                    cli.return_value = subprocess.CompletedProcess([], 0, json.dumps([builtin, foreign]), "")
                    with self.assertRaisesRegex(RuntimeError, "ambient personal-copilot skill"):
                        run_isolated_arm._verify_skill_discovery(str(env), {}, None, None)
                    cli.return_value = subprocess.CompletedProcess([], 0, json.dumps([builtin, extra_plugin]), "")
                    with self.assertRaisesRegex(RuntimeError, "unexpected plugin skill"):
                        run_isolated_arm._verify_skill_discovery(str(env), {}, None, None)


class PreflightAndDefaultsTests(unittest.TestCase):
    def test_preflight_prints_unicode_cases_under_legacy_windows_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evals.json"
            path.write_text(json.dumps({
                "target_skill": "reviewer",
                "value_tasks": [{"id": "case", "prompt": "Review 🟡 finding", "expectations": ["Find issue"]}],
                "trigger_prompts": [{"id": "t1", "intent": "should_trigger", "prompt_text": "Review 🟡 PR"}],
            }), encoding="utf-8")
            env = dict(os.environ, PYTHONIOENCODING="cp1252:strict")
            run = subprocess.run(
                [sys.executable, str(SCRIPTS / "preflight_brief.py"), str(path)],
                env=env, capture_output=True, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", errors="replace"))
            self.assertIn(r"\U0001f7e1", run.stdout.decode("cp1252"))
            self.assertIn("Find issue", run.stdout.decode("cp1252"))

    def test_sweep_evaluators_inherit_model_unless_overridden(self):
        args = new_sweep._parse_args(["unused-skill-dir"])
        self.assertEqual(
            (args.executor_model, args.analyzer_model, args.judge_model),
            ("runtime-default", "runtime-default", "runtime-default"),
        )
        self.assertEqual(args.trigger_repeats, 3)
        with tempfile.TemporaryDirectory() as tmp:
            metadata = new_sweep._skeleton(tmp, "test-sweep", args)["metadata"]
            self.assertEqual(
                (
                    metadata["evaluator_models"]["executor"],
                    metadata["evaluator_models"]["analyzer"],
                    metadata["evaluator_models"]["judge"],
                ),
                ("runtime-default", "runtime-default", "runtime-default"),
            )
            self.assertEqual(metadata["config"]["trigger_repeats"], 3)
            self.assertEqual(set(metadata["judge_guidance"]), {"general", "static", "value"})
        for agent_name in ("skill-eval-analyzer", "skill-eval-judge"):
            agent = SCRIPTS.parents[2] / "agents" / (agent_name + ".md")
            frontmatter = agent.read_text(encoding="utf-8").split("---", 2)[1]
            self.assertNotIn("\nmodel:", frontmatter)
        explicit = new_sweep._parse_args([
            "unused-skill-dir", "--analyzer-model", "selected-analyzer",
            "--judge-model", "selected-judge",
        ])
        self.assertEqual(
            (explicit.analyzer_model, explicit.judge_model),
            ("selected-analyzer", "selected-judge"),
        )

    def test_sweep_results_are_added_to_local_git_exclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            skill = repo / "skills" / "reviewer"
            skill.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)

            first = new_sweep._ensure_local_results_excluded(str(skill))
            second = new_sweep._ensure_local_results_excluded(str(skill))

            self.assertEqual(first, "/skills/reviewer/evals/results/")
            self.assertIsNone(second)
            exclude = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
                capture_output=True, encoding="utf-8", check=True,
            ).stdout.strip()
            if not os.path.isabs(exclude):
                exclude = str(repo / exclude)
            text = Path(exclude).read_text(encoding="utf-8")
            self.assertEqual(text.count("/skills/reviewer/evals/results/"), 1)

    def test_arm_timeout_defaults_to_1800_and_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as tmp:
            for extra, expected in (([], 1800), (["--timeout", "2400"], 2400)):
                with mock.patch.object(run_isolated_arm, "run_arm", return_value=("done", True, "")) as executor:
                    self.assertEqual(run_isolated_arm.main([
                        "--arm", "without", "--task", "review", "--out", str(Path(tmp) / "out.md"),
                        "--env-root", tmp, "--cleanup", *extra,
                    ]), 0)
                    self.assertEqual(executor.call_args.args[3], expected)


class TriggerObservationTests(unittest.TestCase):
    def test_analyze_events_counts_only_exact_target_skill_invocation(self):
        events = [
            {"type": "session.skills_loaded",
             "data": {"skills": [{"name": "target"}]}},
            {"type": "tool.execution_start",
             "data": {"toolName": "skill", "arguments": {"skill": "other"}}},
            {"type": "tool.execution_start",
             "data": {"toolName": "skill", "arguments": {"skill": "target"}}},
        ]
        analysis = run_trigger_check.analyze_events(events, "target")
        self.assertTrue(analysis["triggered"])
        self.assertEqual(analysis["invoked_skills"], ["other", "target"])
        self.assertFalse(run_trigger_check.analyze_events(events[:2], "target")["triggered"])

    def test_assembler_uses_majority_of_three_and_computes_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evals = {
                "trigger_prompts": [
                    {"id": "yes", "prompt_text": "yes", "intent": "should_trigger"},
                    {"id": "no", "prompt_text": "no", "intent": "should_not_trigger"},
                ]
            }
            observations = {
                "yes": [True, True, False],
                "no": [False, True, True],
            }
            for prompt_id, values in observations.items():
                for index, triggered in enumerate(values, 1):
                    run_dir = root / f"{prompt_id}-{index}"
                    run_dir.mkdir()
                    write(run_dir / "events.jsonl", "{}\n")
                    write(run_dir / "response.md", "done\n")
                    write(run_dir / "observation.json", json.dumps({
                        "success": True, "triggered": triggered,
                        "duration_s": 1.0, "errors": 0,
                    }))
            block = assemble_triggering.assemble(evals, str(root), 3)
            self.assertEqual(block["prompts"][0]["actual_result"], "triggered")
            self.assertEqual(block["prompts"][0]["trigger_rate"], 2 / 3)
            self.assertEqual(block["prompts"][1]["actual_result"], "triggered")
            self.assertEqual(block["summary"], {
                "matches": 1, "mismatches": 1, "total": 2, "accuracy": 0.5,
                "false_positive": 1, "false_negative": 0,
            })

    def test_v4_schema_accepts_actual_trigger_observations(self):
        args = new_sweep._parse_args(["unused-skill-dir"])
        with tempfile.TemporaryDirectory() as tmp:
            result = new_sweep._skeleton(tmp, "test-sweep", args)
        result["static_quality"] = {
            "dimension_set_version": "skill-eval-dims/v2", "scale": "1-5",
            "dimensions": [
                {"name": name, "score": 4, "rationale": "ok", "evidence": "text"}
                for name in eval_schema.STATIC_DIMENSIONS
            ],
            "average_score": 4.0, "top_improvements": [],
        }
        result["triggering"] = {
            "trigger_repeats": 3,
            "prompts": [{
                "id": "p", "prompt_text": "prompt",
                "expected_result": "should_trigger", "actual_result": "triggered",
                "trigger_rate": 1.0,
                "runs": [
                    {"run_index": i, "triggered": True,
                     "events_ref": f"trigger-runs/p-{i}/events.jsonl",
                     "response_ref": f"trigger-runs/p-{i}/response.md",
                     "duration_s": 1.0, "errors": 0}
                    for i in range(1, 4)
                ],
            }],
            "summary": {"matches": 1, "mismatches": 0, "total": 1,
                        "accuracy": 1.0, "false_positive": 0, "false_negative": 0},
        }
        result["value_comparison"] = {
            "value_repeats": 2, "tasks": [],
            "summary": {"delta": 0, "verdict": "no clear value", "confidence": "low"},
        }
        result["consolidated_findings"] = {
            "findings": [], "priority_order": [], "overall_assessment": "ok",
        }
        ok, errors = eval_schema.validate_result(result)
        self.assertTrue(ok, errors)


if __name__ == "__main__":
    unittest.main()
