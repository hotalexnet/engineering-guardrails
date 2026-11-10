#!/usr/bin/env python3
"""Copy the portable gate kit to a Git root; never overwrite different files."""

import argparse
import subprocess
import sys
from pathlib import Path


KIT = Path(__file__).resolve().parents[1] / "assets/project-kit"
FILES = (
    "scripts/check_file_lines.py", "scripts/check_quality.py",
    "scripts/check_python_design.py", "scripts/install_hooks.py",
    "tests/test_file_lines.py", "tests/test_python_design.py",
    "tests/test_quality_gates.py", ".githooks/pre-commit",
    ".githooks/pre-push", "docs/engineering-gates.md",
    "docs/change-review.md", "quality-gates.json",
)


def conflict_reason(root, target, source):
    parents = [parent for parent in target.parents if root in parent.parents]
    if target.is_symlink() or any(parent.is_symlink() for parent in parents):
        return "symlink"
    if any(parent.exists() and not parent.is_dir() for parent in parents):
        return "parent is not a directory"
    if target.exists():
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            return "existing content differs"
    return None


def planned_copies(root):
    sources = [KIT / relative for relative in FILES]
    if any(not source.is_file() for source in sources):
        raise ValueError("project kit is incomplete")
    conflicts = []
    pending = []
    for source in sources:
        relative = source.relative_to(KIT)
        target = root / relative
        reason = conflict_reason(root, target, source)
        if reason:
            conflicts.append(f"{relative} ({reason})")
        elif not target.exists():
            pending.append((source, target))
    if conflicts:
        raise ValueError("existing files differ; integrate manually: "
                         + ", ".join(conflicts))
    return pending


def initialize(root):
    actual = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=root, text=True).strip())
    if actual.resolve() != root:
        raise ValueError("--repo must be the Git repository root")
    pending = planned_copies(root)
    for source, target in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(source.read_bytes())
        if ".githooks" in target.parts:
            target.chmod(0o755)
        print(f"Created {target.relative_to(root)}")
    print(f"Ready: {len(pending)} files created; existing identical files preserved.")
    print("Review project AGENTS, then opt in with: python3 scripts/install_hooks.py")
    print("No staging, commits, remote CI or global hook changes performed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args()
    try:
        initialize(args.repo.resolve(strict=True))
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"Initialization stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
