#!/usr/bin/env python3
"""Check working files or a Git snapshot against a 1000 physical-line limit."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


MAX_LINES = 1000
DOCUMENT_SUFFIXES = {".md", ".rst"}


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def snapshot_tree(root, staged=False, revision=None):
    if staged:
        return git(root, "write-tree").decode().strip()
    return git(root, "rev-parse", "--verify", "--end-of-options",
               f"{revision}^{{tree}}").decode().strip()


def file_contents(root, tree=None):
    if tree:
        entries = git(root, "ls-tree", "-r", "-z", tree).split(b"\0")
        for entry in entries:
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            path = Path(os.fsdecode(raw_path))
            if mode == b"120000" or kind != b"blob":
                yield path, None
            else:
                yield path, git(root, "cat-file", "blob", oid.decode())
        return
    paths = git(root, "ls-files", "--cached", "--others",
                "--exclude-standard", "-z").split(b"\0")
    for raw_path in sorted(set(paths) - {b""}):
        relative = Path(os.fsdecode(raw_path))
        path = root / relative
        if path.is_symlink():
            yield relative, None
        elif path.is_file():
            yield relative, path.read_bytes()


def check(root: Path, tree=None) -> int:
    checked = 0
    failures = []
    for relative, content in file_contents(root, tree):
        if content is None:
            failures.append(f"{relative}: symbolic links/submodules need review")
            continue
        if relative.suffix.lower() in DOCUMENT_SUFFIXES:
            continue
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            failures.append(f"{relative}: use UTF-8 text or review binary format")
            continue
        lines = len(text.splitlines())
        checked += 1
        if lines > MAX_LINES:
            failures.append(f"{relative}: {lines} lines > {MAX_LINES}")
    if failures:
        print("File line limit check FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"PASS: {checked} text files checked; limit {MAX_LINES} physical lines.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true")
    group.add_argument("--revision")
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
        tree = snapshot_tree(root, args.staged, args.revision) if (
            args.staged or args.revision is not None) else None
        return check(root, tree)
    except (OSError, subprocess.CalledProcessError, UnicodeError) as error:
        print(f"Cannot complete line limit check: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
