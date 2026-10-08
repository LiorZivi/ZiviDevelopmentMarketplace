#!/usr/bin/env python3
"""Run one trigger prompt and record whether Copilot actually invoked the target skill."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

import run_isolated_arm as isolated


def analyze_events(events, target_skill):
    invoked = []
    for event in events:
        if event.get("type") != "tool.execution_start":
            continue
        data = event.get("data") or {}
        if data.get("toolName") != "skill":
            continue
        arguments = data.get("arguments") or {}
        name = arguments.get("skill")
        if isinstance(name, str):
            invoked.append(name)
    return {
        "triggered": target_skill in invoked,
        "invoked_skills": invoked,
    }


def result_text(events):
    for event in reversed(events):
        if event.get("type") != "result":
            continue
        data = event.get("data")
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            for key in ("content", "text", "message", "response", "result"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
    messages = []
    for event in events:
        if event.get("type") != "assistant.message":
            continue
        data = event.get("data")
        if isinstance(data, str):
            messages.append(data)
        elif isinstance(data, dict):
            value = data.get("content") or data.get("text") or data.get("message")
            if isinstance(value, str):
                messages.append(value)
    return "\n".join(messages)


def run_check(skill_dir, prompt, out_dir, model, timeout, env_root=None):
    skill_dir = os.path.abspath(os.path.normpath(skill_dir))
    target_name = os.path.basename(skill_dir)
    env_root = env_root or os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    env = os.path.join(env_root, "skill-eval-trigger-{}".format(uuid.uuid4().hex[:8]))
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    events_path = os.path.join(out_dir, "events.jsonl")
    response_path = os.path.join(out_dir, "response.md")
    observation_path = os.path.join(out_dir, "observation.json")

    start = time.monotonic()
    try:
        os.makedirs(env, exist_ok=True)
        isolated.build_env("with", env, skill_dir)
        candidate = os.path.join(env, ".github", "skills", target_name)
        plugin_dir = candidate if os.path.isfile(os.path.join(candidate, "plugin.json")) else None
        with tempfile.TemporaryDirectory(prefix="skill-eval-cli-home-") as private_home:
            child_env = isolated._isolated_cli_environment(private_home)
            isolated._verify_skill_discovery(env, child_env, plugin_dir, target_name)
            normalized_prompt = " ".join(str(prompt).split())
            argv = ["-C", env, "-p", normalized_prompt, "--allow-all-tools", "--no-ask-user",
                    "--no-color", "--no-auto-update", "--output-format", "json",
                    "--available-tools", "skill"]
            if plugin_dir:
                argv += ["--plugin-dir", plugin_dir]
            if model and model != "runtime-default":
                argv += ["--model", model]
            kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                      "encoding": "utf-8", "errors": "replace", "env": child_env}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen(isolated._copilot_argv(argv), **kwargs)
            timed_out = False
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                isolated._kill_tree(proc.pid)
                try:
                    stdout, stderr = proc.communicate(timeout=20)
                except Exception:
                    stdout, stderr = "", ""

        event_lines = []
        events = []
        for line in (stdout or "").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            events.append(event)
            event_lines.append(json.dumps(event, ensure_ascii=True))
        analysis = analyze_events(events, target_name)
        response = result_text(events)
        success = not timed_out and proc.returncode == 0
        errors = 0 if success else 1
        observation = {
            "target_skill": target_name,
            "prompt": normalized_prompt,
            "triggered": analysis["triggered"],
            "invoked_skills": analysis["invoked_skills"],
            "success": success,
            "duration_s": round(time.monotonic() - start, 3),
            "errors": errors,
            "return_code": proc.returncode,
            "timed_out": timed_out,
            "stderr": (stderr or "").strip()[:2000],
        }
        with open(events_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(event_lines) + ("\n" if event_lines else ""))
        with open(response_path, "w", encoding="utf-8") as fh:
            fh.write((response or "").strip() + "\n")
        with open(observation_path, "w", encoding="utf-8") as fh:
            json.dump(observation, fh, indent=2)
            fh.write("\n")
        return observation
    finally:
        isolated.cleanup_env("isolated", env, None)


def main(argv):
    parser = argparse.ArgumentParser(description="Observe whether Copilot invokes one target skill.")
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--prompt", required=True, help='prompt text, or "@path"')
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--env-root", default=None)
    args = parser.parse_args(argv)
    prompt = args.prompt
    if prompt.startswith("@"):
        with open(prompt[1:], "r", encoding="utf-8") as fh:
            prompt = fh.read()
    observation = run_check(
        args.skill_dir, prompt, args.out_dir, args.model, args.timeout, args.env_root)
    print("triggered={} success={} observation={}".format(
        observation["triggered"], observation["success"],
        os.path.join(os.path.abspath(args.out_dir), "observation.json")))
    return 0 if observation["success"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
