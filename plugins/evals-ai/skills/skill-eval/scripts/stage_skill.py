#!/usr/bin/env python3
"""
stage_skill.py - stage a target skill AND its full transitive dependency closure
into a fresh scratch directory, so skill-eval's Mode-3 *with-skill* run gets the
skill exactly as it works in production - not just its SKILL.md.

A skill is more than its SKILL.md: it bundles references/ and scripts/, it spawns
agents (which may read knowledge_base / instructions files), and it can link sibling
skills (for example `../release-helper/...`). Injecting only SKILL.md under-represents
the skill and unfairly collapses its measured value. This script resolves that whole
closure and copies it into a scratch `.github/` mirror so every in-skill,
cross-skill, agent, and knowledge_base reference resolves from the scratch dir.

It is used ONLY for the with-skill configuration. The baseline still runs in a
separate, empty scratch dir with no skill - so baseline isolation is unaffected.

Every `evals/` subtree is excluded: it holds the eval cases/expectations, and the
executor must never see what it will be graded against.

Stdlib only.

Usage:
    python stage_skill.py <target-skill-dir> <dest-scratch-dir> [--resources-root DIR] [--max-depth N]

Layout produced (mirrors standard workspace customization directories):
    <dest>/.github/skills/<name>/...        (target skill + any dependent skills)
    <dest>/.github/agents/<agent>.md        (referenced agents)
    <dest>/.github/knowledge_base/<...>      (files those agents read)
    <dest>/.github/instructions/<...>

Prints a manifest of what was staged (and any explicit reference it could not map).
"""

import argparse
import json
import os
import re
import shutil
import sys

_TEXT_EXTS = {".md", ".ps1", ".psm1", ".py", ".txt", ".json", ".yaml", ".yml",
              ".sh", ".cmd", ".g", ".ts", ".js"}
_PRUNE_DIRS = {"evals", "__pycache__", ".git", "node_modules"}
_MAX_ITEMS = 300

# explicit, high-confidence dependency signals
_AGENT_TYPE = re.compile(r'agent_type\s*[=:]\s*["\']([A-Za-z0-9._-]+)["\']')
_AGENT_FILE = re.compile(r'([A-Za-z0-9._-]+?)\.agent\.md')
_SKILL_REL = re.compile(r'\.\./([A-Za-z0-9._-]+)/')
_SKILL_GH = re.compile(r'\.github/skills/([A-Za-z0-9._-]+)')
_NAMED_SKILL = re.compile(
    r'\b(?:uses?|invokes?|loads?|calls?|runs?)\s+(?:the\s+)?(?:shared\s+)?(?:\*\*)?'
    r'`?([a-z0-9][a-z0-9._-]*)`?(?:\*\*)?\s+skill\b', re.IGNORECASE)
_NEGATED_USE = re.compile(r"\b(?:do\s+not|does\s+not|don't|never|not)\s+$", re.IGNORECASE)
_KB_PATH = re.compile(r'(?:\.github/|(?<![A-Za-z0-9._-]))knowledge_base/([A-Za-z0-9._/\-]+)')
_INSTR_PATH = re.compile(r'(?:\.github/|(?<![A-Za-z0-9._-]))instructions/([A-Za-z0-9._/\-]+)')


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def _iter_text(root):
    if os.path.isfile(root):
        if os.path.splitext(root)[1].lower() in _TEXT_EXTS:
            yield root
        return
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _PRUNE_DIRS]
        for f in files:
            if os.path.splitext(f)[1].lower() in _TEXT_EXTS:
                yield os.path.join(r, f)


def _copy_tree(src, dst):
    """Copy a directory tree, pruning evals/ and other noise."""
    for r, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in _PRUNE_DIRS]
        rel = os.path.relpath(r, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for f in files:
            try:
                shutil.copy2(os.path.join(r, f), os.path.join(out, f))
            except OSError:
                pass


def _copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.copy2(src, dst)
        return True
    except OSError:
        return False


class Stager(object):
    def __init__(self, resources_root, dest, max_depth):
        self.res = resources_root
        self.skills_root = os.path.join(resources_root, "skills")
        self.agents_root = os.path.join(resources_root, "agents")
        self.kb_root = os.path.join(resources_root, "knowledge_base")
        self.instr_root = os.path.join(resources_root, "instructions")
        self.gh = os.path.join(dest, ".github")
        self.max_depth = max_depth
        self.visited = set()
        self.manifest = {"skills": [], "agents": [], "knowledge_base": [],
                         "instructions": [], "unresolved": []}
        # name indexes for the fuzzy "and so on" pass
        self.agent_names = self._index_agents(self.agents_root)
        self.skill_names = self._index_dirs(self.skills_root)

    # ---- indexing -------------------------------------------------------
    def _index_agents(self, root):
        names = {}
        if os.path.isdir(root):
            for f in sorted(os.listdir(root)):
                p = os.path.join(root, f)
                if not os.path.isfile(p):
                    continue
                if f.endswith(".agent.md"):
                    names[f[:-len(".agent.md")]] = p
                elif f.endswith(".md"):
                    names[f[:-len(".md")]] = p
        return names

    def _bundled_agents(self, skill_dir):
        manifest = os.path.join(skill_dir, "plugin.json")
        declared = False
        relative = "agents"
        if os.path.isfile(manifest):
            with open(manifest, "r", encoding="utf-8") as fh:
                config = json.load(fh)
            declared = "agents" in config
            relative = config.get("agents", relative)
            if relative is None:
                return {}
            if not isinstance(relative, str) or not relative.strip():
                raise ValueError("invalid plugin agents path in {}".format(manifest))
        root = os.path.normcase(os.path.realpath(skill_dir))
        agent_dir = os.path.normcase(os.path.realpath(os.path.join(skill_dir, relative)))
        if agent_dir == root or os.path.commonpath([root, agent_dir]) != root:
            raise ValueError("plugin agents path escapes skill directory: {}".format(relative))
        if not os.path.isdir(agent_dir):
            if declared:
                raise FileNotFoundError("plugin agents directory not found: {}".format(agent_dir))
            return {}
        return self._index_agents(agent_dir)

    def _index_dirs(self, root):
        names = {}
        if os.path.isdir(root):
            for d in os.listdir(root):
                p = os.path.join(root, d)
                if os.path.isdir(p):
                    names[d] = p
        return names

    # ---- resolution -----------------------------------------------------
    def _resolve_agent(self, name):
        return self.agent_names.get(name)

    def _resolve_under(self, root, sub):
        sub = sub.split("#", 1)[0].strip().strip("`\"').").rstrip("/")
        if not sub:
            return None
        root_n = os.path.normpath(root)
        cand = os.path.normpath(os.path.join(root_n, sub))
        if not cand.startswith(root_n):
            return None
        # trim a too-specific tail (e.g. file.md#anchor) down to something real,
        # but never all the way to the category root (that would stage everything)
        while cand != root_n and not os.path.exists(cand):
            parent = os.path.dirname(cand)
            if parent == cand:
                break
            cand = parent
        if cand == root_n or not os.path.exists(cand):
            return None
        return cand

    def _resolve_kb(self, sub):
        return self._resolve_under(self.kb_root, sub)

    def _resolve_instr(self, sub):
        return self._resolve_under(self.instr_root, sub)

    def _cap(self):
        total = sum(len(self.manifest[k]) for k in
                    ("skills", "agents", "knowledge_base", "instructions"))
        return total >= _MAX_ITEMS

    # ---- staging --------------------------------------------------------
    def stage_skill_dir(self, skill_dir, depth):
        name = os.path.basename(os.path.normpath(skill_dir))
        key = ("skill", name)
        if key in self.visited or depth > self.max_depth or self._cap():
            return
        self.visited.add(key)
        if not os.path.isdir(skill_dir):
            self.manifest["unresolved"].append("skill:" + name)
            return
        _copy_tree(skill_dir, os.path.join(self.gh, "skills", name))
        self.manifest["skills"].append(name)
        bundled = self._bundled_agents(skill_dir)
        self.agent_names.update(bundled)
        for agent_name in bundled:
            self.stage_agent(agent_name, depth + 1)
        self._discover(skill_dir, depth + 1)

    def stage_agent(self, agent_name, depth):
        key = ("agent", agent_name)
        if key in self.visited or depth > self.max_depth or self._cap():
            return
        self.visited.add(key)
        src = self._resolve_agent(agent_name)
        if not src:
            self.manifest["unresolved"].append("agent:" + agent_name)
            return
        if not _copy_file(src, os.path.join(self.gh, "agents", os.path.basename(src))):
            raise OSError("could not stage agent {} from {}".format(agent_name, src))
        self.manifest["agents"].append(os.path.basename(src))
        self._discover(src, depth + 1)

    def stage_kb(self, sub, depth):
        src = self._resolve_kb(sub)
        if not src:
            self.manifest["unresolved"].append("knowledge_base:" + sub)
            return
        rel = os.path.relpath(src, self.kb_root)
        key = ("kb", rel)
        if key in self.visited or self._cap():
            return
        self.visited.add(key)
        dst = os.path.join(self.gh, "knowledge_base", rel)
        if os.path.isdir(src):
            _copy_tree(src, dst)
        else:
            _copy_file(src, dst)
        self.manifest["knowledge_base"].append(rel.replace("\\", "/"))
        self._discover(src, depth + 1)

    def stage_instr(self, sub, depth):
        src = self._resolve_instr(sub)
        if not src:
            self.manifest["unresolved"].append("instructions:" + sub)
            return
        rel = os.path.relpath(src, self.instr_root)
        key = ("instr", rel)
        if key in self.visited or self._cap():
            return
        self.visited.add(key)
        dst = os.path.join(self.gh, "instructions", rel)
        if os.path.isdir(src):
            _copy_tree(src, dst)
        else:
            _copy_file(src, dst)
        self.manifest["instructions"].append(rel.replace("\\", "/"))
        self._discover(src, depth + 1)

    # ---- discovery ------------------------------------------------------
    def _discover(self, root, depth):
        if depth > self.max_depth:
            return
        text = "\n".join(_read(p) for p in _iter_text(root))
        if not text:
            return
        # explicit signals
        for name in set(_AGENT_TYPE.findall(text)) | set(_AGENT_FILE.findall(text)):
            self.stage_agent(name, depth)
        for name in set(_SKILL_GH.findall(text)):
            if name in self.skill_names:
                self.stage_skill_dir(self.skill_names[name], depth)
        for name in set(_SKILL_REL.findall(text)):
            if name in self.skill_names:  # silent skip for non-skill relative links
                self.stage_skill_dir(self.skill_names[name], depth)
        for line in text.splitlines():
            for match in _NAMED_SKILL.finditer(line):
                if _NEGATED_USE.search(line[:match.start()]):
                    continue
                name = match.group(1).lower()
                if name in self.skill_names:
                    self.stage_skill_dir(self.skill_names[name], depth)
                elif "-" in name:
                    self.manifest["unresolved"].append("skill:" + name)
        for sub in set(_KB_PATH.findall(text)):
            self.stage_kb(sub, depth)
        for sub in set(_INSTR_PATH.findall(text)):
            self.stage_instr(sub, depth)


def _detect_resources_root(target):
    parent = os.path.dirname(target)          # .../skills
    root = os.path.dirname(parent)            # .../resources  (or .github)
    return root


def main(argv):
    p = argparse.ArgumentParser(description="Stage a skill and its dependency closure into a scratch dir.")
    p.add_argument("target", help="path to the target skill's directory")
    p.add_argument("dest", help="fresh scratch directory to stage into")
    p.add_argument("--resources-root", default=None,
                   help="root containing skills/ agents/ knowledge_base/ instructions/ (auto-detected)")
    p.add_argument("--max-depth", type=int, default=6)
    args = p.parse_args(argv)

    target = os.path.abspath(os.path.normpath(args.target))
    if not os.path.isdir(target):
        sys.stderr.write("target skill dir not found: {}\n".format(target))
        return 1
    res = os.path.abspath(args.resources_root) if args.resources_root else _detect_resources_root(target)
    if not os.path.isdir(os.path.join(res, "skills")):
        sys.stderr.write("resources root has no skills/ dir: {}\n".format(res))
        return 1

    st = Stager(res, os.path.abspath(args.dest), args.max_depth)
    st.stage_skill_dir(target, 0)
    m = st.manifest

    print("Staged with-skill closure into {}".format(os.path.join(os.path.abspath(args.dest), ".github")))
    print("  skills ({}): {}".format(len(m["skills"]), ", ".join(sorted(m["skills"])) or "-"))
    print("  agents ({}): {}".format(len(m["agents"]), ", ".join(sorted(m["agents"])) or "-"))
    print("  knowledge_base ({}): {}".format(len(m["knowledge_base"]), ", ".join(sorted(m["knowledge_base"])) or "-"))
    print("  instructions ({}): {}".format(len(m["instructions"]), ", ".join(sorted(m["instructions"])) or "-"))
    if m["unresolved"]:
        print("  unresolved explicit refs ({}): {}".format(
            len(m["unresolved"]), ", ".join(sorted(set(m["unresolved"])))))
    print("  (every evals/ subtree excluded - the executor must not see the graded cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
