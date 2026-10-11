#!/usr/bin/env python3
"""Stage one candidate output at a neutral path for configuration-blind judging."""

import argparse
import os
import shutil
import sys
import tempfile


_PREFIX = "skill-eval-blind-"
_CANDIDATE = "candidate-output.md"
_MARKER = ".skill-eval-blind-input"


def stage(source, temp_root=None):
    source = os.path.abspath(source)
    if not os.path.isfile(source):
        raise ValueError("candidate output not found: {}".format(source))
    root = temp_root or os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    os.makedirs(root, exist_ok=True)
    neutral_dir = tempfile.mkdtemp(prefix=_PREFIX, dir=root)
    candidate = os.path.join(neutral_dir, _CANDIDATE)
    try:
        shutil.copyfile(source, candidate)
        with open(os.path.join(neutral_dir, _MARKER), "w", encoding="utf-8") as fh:
            fh.write("skill-eval blind judge input\n")
        return candidate
    except Exception:
        shutil.rmtree(neutral_dir, ignore_errors=True)
        raise


def cleanup(candidate):
    candidate = os.path.abspath(candidate)
    neutral_dir = os.path.dirname(candidate)
    if (os.path.basename(candidate) != _CANDIDATE
            or not os.path.basename(neutral_dir).startswith(_PREFIX)
            or not os.path.isfile(os.path.join(neutral_dir, _MARKER))):
        raise ValueError("refusing to remove an unrecognized blind-judge input")
    shutil.rmtree(neutral_dir)


def main(argv):
    parser = argparse.ArgumentParser(
        description="Stage or remove a neutral candidate file for blind judging.")
    sub = parser.add_subparsers(dest="command", required=True)
    stage_parser = sub.add_parser("stage")
    stage_parser.add_argument("source")
    stage_parser.add_argument("--temp-root", default=None)
    cleanup_parser = sub.add_parser("cleanup")
    cleanup_parser.add_argument("candidate")
    args = parser.parse_args(argv)

    try:
        if args.command == "stage":
            print(stage(args.source, args.temp_root))
        else:
            cleanup(args.candidate)
    except (OSError, ValueError) as exc:
        sys.stderr.write("{}\n".format(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
