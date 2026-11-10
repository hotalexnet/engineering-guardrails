#!/usr/bin/env python3
"""Local/CI quality entry; snapshot checks do not test unrelated working files."""

import argparse
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from check_file_lines import check, git, snapshot_tree
from check_python_design import check as check_design


def run_tests(root):
    required = ("scripts/check_file_lines.py", "scripts/check_quality.py",
                "scripts/check_python_design.py", "quality-gates.json",
                "tests/test_file_lines.py")
    if any(not (root / name).is_file() for name in required):
        print("FAIL: required gate files/tests are missing", file=sys.stderr)
        return 1
    runner = """
import sys
import unittest
suite = unittest.defaultTestLoader.discover('tests', pattern='test_*.py')
if suite.countTestCases() == 0:
    sys.exit('FAIL: no tests discovered')
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""
    return subprocess.run(
        [sys.executable, "-c", runner], cwd=root, check=False
    ).returncode


def verify(root, tree=None):
    if check(root, tree) or check_design(root, tree):
        return 1
    if tree is None:
        return run_tests(root)
    archive = git(root, "archive", "--format=tar", tree)
    with tempfile.TemporaryDirectory(prefix="quality-snapshot-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            bundle.extractall(directory, filter="data")
        return run_tests(Path(directory))


def pre_push(root):
    tips = set()
    for line in sys.stdin:
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("invalid pre-push input")
        sha = fields[1]
        if set(sha) != {"0"}:
            tips.add(sha)
    for sha in sorted(tips):
        print(f"Checking push tip: {sha}", flush=True)
        if verify(root, snapshot_tree(root, revision=sha)):
            return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--staged", action="store_true")
    modes.add_argument("--revision")
    modes.add_argument("--pre-push", action="store_true")
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
        if args.pre_push:
            return pre_push(root)
        tree = snapshot_tree(root, args.staged, args.revision) if (
            args.staged or args.revision is not None) else None
        return verify(root, tree)
    except (OSError, subprocess.CalledProcessError, UnicodeError,
            ValueError, tarfile.TarError) as error:
        print(f"Cannot complete quality check: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
