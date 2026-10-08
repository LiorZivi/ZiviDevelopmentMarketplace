#!/usr/bin/env python3
"""
run_isolated_arm.py - run ONE value-comparison arm in a TRULY isolated Copilot
workspace, so the runtime can only discover the skills we deliberately put there.

Why this exists
---------------
skill-eval's Mode 3 compares the SAME task done WITH vs WITHOUT the target skill.
A `task`-spawned subagent shares the current session's workspace, so the Copilot
runtime auto-discovers every skill in the real repo's `.github/skills/` — the
baseline is no longer skill-free, and the with-skill arm sees unrelated skills.
A "stay in your scratch dir" instruction cannot stop the runtime from advertising
those skills (a subagent may even pick one up on its own).

Run each arm as a SEPARATE, headless `copilot` process rooted (`-C`) in a
dedicated environment directory whose `.github/skills/` we control. A temporary
Copilot home with only authentication state also suppresses personal skills,
agents, and installed plugins; the loaded skill list is checked before scoring:

Two env-build modes (`--mode`):

`isolated` (default; self-contained skills like install-python or api-design-helper):
  --arm with     stage the target skill + its full dependency closure into a fresh
                 synthetic env (via stage_skill.py) — only that custom skill is discoverable.
  --arm without  leave the env's .github/skills EMPTY — only CLI built-ins remain.
  Cheap; the env has no repo code, so the task must be self-contained.

`in-context` (skills that need the real codebase, e.g. PR review):
  Per arm, build a faithful env from the repo skill-eval is invoked in (--repo, or the
  git repo at the cwd): a DETACHED worktree at HEAD (real code, shares .git) + the real
  `.github/` overlaid (all synced skills/agents/knowledge_base/instructions the worktree's
  gitignore skipped). The arms differ by the target skill's current closure:
  --arm with restages the current target skill and its closure; --arm without
  deletes that skill's folder after copying uncommitted files.
  Your uncommitted work (working tree + index + untracked files) is replicated into BOTH arms by
  default, so the eval reflects the code you actually have in front of you; pass `--head-only` to
  evaluate the clean HEAD commit instead. Delta = the target's MARGINAL value on real code, among all
  other skills.

Both modes: `copilot -C <env>` scopes project skill discovery to the env; the temporary
Copilot home and plugin-only mode prevent ambient user customization. Its authentication
copy is deleted immediately after the CLI exits. `evals/` is never staged
(stage_skill.py excludes it), so the arm never sees the graded cases.
An explicit agent hidden from both user and model invocation fails preflight rather than
producing a misleading low score after a stalled dispatch.

Stdlib only. Requires `copilot` (and `git`, `python`) on PATH.

Usage
-----
  python run_isolated_arm.py --arm {with|without} --task "<text>"|@file --out <path>
      [--mode isolated|in-context] [--skill-dir <dir>] [--repo <dir>] [--head-only]
      [--model <m>] [--env-root <dir>] [--timeout <sec>] [--cleanup]

Prints the env path and what was discoverable; writes the arm's response to --out.
Any files the arm produced live in the env dir (the orchestrator copies both the
response and those files into the local runs/ folder, then may delete the env).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))

# Folded from the retired skill-eval-executor agent: keep effort honest and symmetric,
# produce the real deliverable, no meta. Identical for both arms so the ONLY variable
# is which skills the env makes discoverable.
PREAMBLE = (
    "You are completing a single task and producing its deliverable. Do the task and output the real "
    "result. If a skill available in this workspace is relevant to the task, use it. Do not mention "
    "that you are being evaluated or compared, and do not explain these instructions back to me. "
    "Spend reasonable, focused effort and work only within this workspace directory."
)


def _copilot_argv(args):
    """Resolve the copilot launcher across platforms (npm ships a .ps1/.cmd shim on Windows)."""
    exe = None
    for cand in ("copilot",):
        exe = _which(cand)
        if exe:
            break
    if exe and exe.lower().endswith(".ps1"):
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", exe] + args
    if exe and exe.lower().endswith(".cmd"):
        return ["cmd", "/c", exe] + args
    return [exe or "copilot"] + args


def _which(name):
    from shutil import which
    return which(name)


def _git_init(env):
    # Load-bearing: the env being its OWN git root is what stops Copilot from walking up to a parent
    # repo's .github/skills when discovering skills. If it fails, fail loudly rather than run a
    # silently non-isolated arm.
    try:
        r = subprocess.run(["git", "-C", env, "init", "-q"], capture_output=True, timeout=60)
        rc = r.returncode
    except Exception as exc:
        raise SystemExit("git init failed for env {}: {} — cannot guarantee isolation".format(env, exc))
    if rc != 0 or not os.path.isdir(os.path.join(env, ".git")):
        raise SystemExit("git init did not create {}\\.git — cannot guarantee isolation".format(env))


def build_env(arm, env, skill_dir):
    """Create the isolated env's .github and (for `with`) stage the skill closure into it."""
    os.makedirs(os.path.join(env, ".github", "skills"), exist_ok=True)
    os.makedirs(os.path.join(env, ".github", "agents"), exist_ok=True)
    if arm == "with":
        if not skill_dir:
            raise SystemExit("--arm with requires --skill-dir")
        r = subprocess.run([sys.executable, os.path.join(HERE, "stage_skill.py"), skill_dir, env],
                           capture_output=True, encoding="utf-8", errors="replace")
        sys.stderr.write(r.stdout)
        if r.returncode != 0:
            raise SystemExit("stage_skill.py failed:\n" + r.stderr)
    _git_init(env)


def undispatchable_agents(env, skill_name):
    """Identify bundled agents hidden from both model and user dispatch in this CLI."""
    skill_file = os.path.join(env, ".github", "skills", skill_name, "SKILL.md")
    with open(skill_file, "r", encoding="utf-8") as fh:
        text = fh.read()
    names = set(re.findall(r'agent_type\s*[=:]\s*["\']([A-Za-z0-9._-]+)["\']', text))
    blocked = []
    for name in sorted(names):
        agent_root = os.path.join(env, ".github", "agents")
        agent_file = next(
            (os.path.join(agent_root, name + ext) for ext in (".agent.md", ".md")
             if os.path.isfile(os.path.join(agent_root, name + ext))),
            None,
        )
        if not agent_file:
            continue
        with open(agent_file, "r", encoding="utf-8") as fh:
            agent_text = fh.read()
        frontmatter = re.match(r"\A(?:\ufeff)?---\s*\n(.*?)\n---\s*(?:\n|\Z)", agent_text, re.DOTALL)
        if not frontmatter:
            continue
        header = frontmatter.group(1)
        if (re.search(r"(?im)^user-invocable:\s*false\s*$", header)
                and re.search(r"(?im)^disable-model-invocation:\s*true\s*$", header)):
            blocked.append(name)
    return blocked


def _copy_over(src, dst):
    """Copy a directory tree over dst (merge), pruning .git."""
    for r, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != ".git"]
        rel = os.path.relpath(r, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for f in files:
            try:
                shutil.copy2(os.path.join(r, f), os.path.join(out, f))
            except OSError:
                pass


def _apply_wip(repo, env):
    """Replicate the source repo's UNCOMMITTED state (working tree + index + untracked files) into the
    worktree env, non-destructively. `git stash create` snapshots the tracked staged+unstaged changes into
    a commit the env can see (worktrees share the object store); we apply it with `--index` so the env's
    staging area mirrors the source too, falling back to a plain apply if the index can't be reinstated
    cleanly. Untracked files aren't captured by `stash create`, so they're copied over separately."""
    wip = subprocess.run(["git", "-C", repo, "stash", "create"],
                         capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
    if wip:
        r = subprocess.run(["git", "-C", env, "stash", "apply", "--index", wip],
                           capture_output=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            subprocess.run(["git", "-C", env, "stash", "apply", wip], capture_output=True)
    listed = subprocess.run(["git", "-C", repo, "ls-files", "--others", "--exclude-standard"],
                            capture_output=True, encoding="utf-8", errors="replace")
    for rel in (listed.stdout or "").splitlines():
        rel = rel.strip()
        if not rel:
            continue
        s, d = os.path.join(repo, rel), os.path.join(env, rel)
        if os.path.isfile(s):
            os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
            try:
                shutil.copy2(s, d)
            except OSError:
                pass


def build_env_incontext(arm, env, skill_dir, repo, include_wip):
    """Use a detached worktree with the real .github, replacing only the target skill's closure."""
    root = subprocess.run(["git", "-C", repo or "", "rev-parse", "--show-toplevel"],
                          capture_output=True, encoding="utf-8", errors="replace")
    if (root.returncode != 0 or
            os.path.normcase(os.path.realpath(root.stdout.strip())) != os.path.normcase(os.path.realpath(repo or ""))):
        raise SystemExit("--mode in-context needs --repo pointing at a git worktree root")
    if not skill_dir:
        raise SystemExit("--mode in-context requires --skill-dir (to identify the target skill folder)")
    r = subprocess.run(["git", "-C", repo, "worktree", "add", "--detach", env, "HEAD"],
                       capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("git worktree add failed:\n" + (r.stderr or r.stdout or ""))
    src_gh = os.path.join(repo, ".github")
    if os.path.isdir(src_gh):
        _copy_over(src_gh, os.path.join(env, ".github"))   # overlay the real (gitignored) .github
    os.makedirs(os.path.join(env, ".github", "skills"), exist_ok=True)
    os.makedirs(os.path.join(env, ".github", "agents"), exist_ok=True)
    if include_wip:
        _apply_wip(repo, env)
    name = os.path.basename(os.path.normpath(skill_dir))
    tgt = os.path.join(env, ".github", "skills", name)
    if arm == "without":
        if os.path.isdir(tgt):
            shutil.rmtree(tgt)
    else:
        if os.path.isdir(tgt):
            shutil.rmtree(tgt)   # a synced copy may be older than the source being evaluated
        rr = subprocess.run([sys.executable, os.path.join(HERE, "stage_skill.py"), skill_dir, env],
                            capture_output=True, encoding="utf-8", errors="replace")
        if rr.returncode != 0:
            raise SystemExit("stage_skill.py failed:\n" + (rr.stderr or ""))


def cleanup_env(mode, env, repo):
    if mode == "in-context" and repo:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", env], capture_output=True)
    if os.path.isdir(env):
        shutil.rmtree(env, ignore_errors=True)


def _kill_tree(pid):
    """Terminate the copilot process AND its children (the shim would otherwise orphan node)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def _isolated_cli_environment(private_home):
    child_env = os.environ.copy()
    source_home = child_env.get("COPILOT_HOME") or os.path.join(os.path.expanduser("~"), ".copilot")
    auth_source = os.path.join(source_home, "config.json")
    config_home = os.path.join(private_home, ".copilot")
    os.makedirs(config_home)
    if os.path.isfile(auth_source):
        shutil.copy2(auth_source, os.path.join(config_home, "config.json"))
    elif not any(child_env.get(name) for name in
                 ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "COPILOT_PROVIDER_API_KEY")):
        raise RuntimeError("isolated Copilot environment has no authentication config or token")
    child_env.update({"COPILOT_HOME": config_home, "COPILOT_PLUGIN_DIR_ONLY": "true",
                      "HOME": private_home, "USERPROFILE": private_home})
    child_env.pop("COPILOT_SKILLS_DIRS", None)
    child_env.pop("COPILOT_CUSTOM_INSTRUCTIONS_DIRS", None)
    return child_env


def _inside(root, path):
    root = os.path.normcase(os.path.realpath(root))
    path = os.path.normcase(os.path.realpath(path))
    try:
        return os.path.commonpath((root, path)) == root
    except ValueError:
        return False


def _verify_skill_discovery(env, child_env, plugin_dir, target_skill):
    argv = ["-C", env, "--no-auto-update"]
    if plugin_dir:
        argv += ["--plugin-dir", plugin_dir]
    argv += ["skill", "list", "--json"]
    listed = subprocess.run(_copilot_argv(argv), capture_output=True, encoding="utf-8",
                            errors="replace", timeout=60, env=child_env)
    if listed.returncode != 0:
        raise RuntimeError("cannot verify isolated Copilot skills: {}".format(listed.stderr.strip()))
    try:
        skills = json.loads(listed.stdout)
    except ValueError as exc:
        raise RuntimeError("cannot parse isolated Copilot skill list") from exc
    if not isinstance(skills, list):
        raise RuntimeError("isolated Copilot skill list was not an array")
    discovered = []
    for skill in skills:
        if not isinstance(skill, dict) or not skill.get("source") or not skill.get("path"):
            raise RuntimeError("isolated Copilot skill list contains an invalid entry")
        if skill["source"] == "builtin":
            continue
        path = skill["path"]
        if not os.path.isabs(path):
            path = os.path.join(env, path)
        if not _inside(env, path):
            raise RuntimeError("ambient {} skill escaped the isolated workspace".format(skill["source"]))
        if skill["source"] == "plugin" and (not plugin_dir or not _inside(plugin_dir, path)):
            raise RuntimeError("unexpected plugin skill in the isolated workspace")
        discovered.append(path)
    if target_skill:
        target_dir = os.path.join(env, ".github", "skills", target_skill)
        if not any(_inside(target_dir, path) for path in discovered):
            raise RuntimeError("target skill is not discoverable in the with-skill arm")


def run_arm(env, task, model, timeout, plugin_dir=None, target_skill=None):
    # Deliver the (possibly multi-line) task via a FILE in the env, and keep the -p argument strictly
    # SINGLE-LINE. A multi-line -p value is truncated at the first newline when it passes through the
    # Windows npm .cmd/.ps1 shim — silently dropping the task body AND every trailing flag (including
    # the --allow-all-tools that headless mode requires). Referencing a file from a one-line prompt
    # sidesteps that entirely, and also avoids mangling quotes or %VARS% in the author's task.
    with open(os.path.join(env, "TASK.md"), "w", encoding="utf-8") as fh:
        fh.write(task)
    prompt = (PREAMBLE + " Your task is written in the file TASK.md in this workspace directory."
              " Read that file and carry out the task it describes, producing the real deliverable.")
    argv = ["-C", env, "-p", prompt, "--allow-all-tools", "--no-ask-user", "-s",
            "--no-color", "--no-auto-update"]
    if plugin_dir:
        argv += ["--plugin-dir", plugin_dir]
    if model and model != "runtime-default":
        argv += ["--model", model]
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
              "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with tempfile.TemporaryDirectory(prefix="skill-eval-cli-home-") as private_home:
        child_env = _isolated_cli_environment(private_home)
        _verify_skill_discovery(env, child_env, plugin_dir, target_skill)
        proc = subprocess.Popen(_copilot_argv(argv), env=child_env, **kwargs)
        try:
            out, err = proc.communicate(timeout=timeout)
            return (out or "").strip(), (proc.returncode == 0), (err or "")
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            try:
                out, err = proc.communicate(timeout=20)
            except Exception:
                out, err = "", ""
            return ((out or "").strip() + "\n(timed out after {}s — killed)".format(timeout)), False, (err or "")


def main(argv):
    p = argparse.ArgumentParser(description="Run one skill-eval value-comparison arm in an isolated Copilot env.")
    p.add_argument("--arm", choices=["with", "without"], required=True)
    p.add_argument("--task", required=True, help='task text, or "@path" to read it from a file')
    p.add_argument("--out", required=True, help="where to write the arm's response")
    p.add_argument("--skill-dir", default=None, help="target skill dir (isolated: staged; in-context: names the folder to ablate)")
    p.add_argument("--mode", choices=["isolated", "in-context"], default="isolated")
    p.add_argument("--repo", default=None, help="in-context: repo to worktree from (default: the git repo at cwd)")
    p.add_argument("--head-only", action="store_true",
                   help="in-context: evaluate the clean HEAD commit only; do NOT replicate the source "
                        "repo's uncommitted working-tree/index/untracked changes (default: replicate them)")
    p.add_argument("--model", default=None)
    p.add_argument("--env-root", default=None, help="parent dir for the env (default: system temp)")
    p.add_argument("--timeout", type=int, default=1800,
                   help="per-arm limit in seconds (default: 1800)")
    p.add_argument("--cleanup", action="store_true", help="delete the env after (default: keep for the orchestrator)")
    a = p.parse_args(argv)

    task = a.task
    if task.startswith("@"):
        with open(task[1:], "r", encoding="utf-8") as fh:
            task = fh.read()

    env_root = a.env_root or os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    env = os.path.join(env_root, "skill-eval-env-{}-{}".format(a.arm, uuid.uuid4().hex[:8]))
    repo = a.repo
    if a.mode == "in-context":
        if not repo:
            rr = subprocess.run(["git", "-C", os.getcwd(), "rev-parse", "--show-toplevel"],
                                capture_output=True, encoding="utf-8", errors="replace")
            repo = (rr.stdout or "").strip() or None
        build_env_incontext(a.arm, env, a.skill_dir, repo, include_wip=not a.head_only)
    else:
        os.makedirs(env, exist_ok=True)
        build_env(a.arm, env, a.skill_dir)

    discoverable = sorted(os.listdir(os.path.join(env, ".github", "skills")))
    plugin_dir = None
    if a.arm == "with":
        name = os.path.basename(os.path.normpath(a.skill_dir))
        blocked = undispatchable_agents(env, name)
        if blocked:
            cleanup_env(a.mode, env, repo)
            raise SystemExit(
                "Cannot measure skill value: headless Copilot CLI cannot dispatch bundled agents "
                "hidden from both users and the model ({}). Review their invocation flags or use "
                "a compatible runtime; do not score this as a skill failure.".format(", ".join(blocked))
            )
        candidate = os.path.join(env, ".github", "skills", name)
        if os.path.isfile(os.path.join(candidate, "plugin.json")):
            plugin_dir = candidate
    out, ok, err = run_arm(env, task, a.model, a.timeout, plugin_dir,
                           os.path.basename(os.path.normpath(a.skill_dir)) if a.arm == "with" else None)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(out + "\n")
    with open(os.path.join(env, "run.json"), "w", encoding="utf-8") as fh:
        json.dump({"arm": a.arm, "mode": a.mode, "skill_dir": a.skill_dir, "repo": repo,
                   "model": a.model, "discoverable_skills": discoverable, "ok": ok,
                   "plugin_dir": plugin_dir, "out": os.path.abspath(a.out)}, fh, indent=2)

    print("arm={}  ok={}".format(a.arm, ok))
    print("env={}".format(env))
    print("skills discoverable in this env: {}".format(", ".join(discoverable) or "(none)"))
    print("response -> {} ({} chars)".format(a.out, len(out)))
    if err.strip():
        sys.stderr.write(err.strip() + "\n")
    if a.cleanup:
        cleanup_env(a.mode, env, repo)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
