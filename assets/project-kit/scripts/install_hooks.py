#!/usr/bin/env python3
"""Opt in to repository-local hooks without replacing existing hook setups."""

import sys

if sys.version_info < (3, 12):
    sys.exit("engineering-guardrails requires Python 3.12+")

import os
import subprocess
from pathlib import Path


HOOKS = ("pre-commit", "pre-push")


def prepare_hooks(root):
    directory = root / ".githooks"
    if directory.is_symlink() or directory.is_junction():
        raise RuntimeError(f"hook directory must not be a link: {directory}")
    for name in HOOKS:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"missing or symlinked hook: {path}")
    for name in HOOKS:
        path = directory / name
        path.chmod(path.stat().st_mode | 0o111)
        if not os.access(path, os.X_OK):
            raise RuntimeError(f"hook is not executable: {path}")


def main():
    if os.name == "nt":
        raise RuntimeError("POSIX hooks require WSL2/Linux/macOS; native Windows is unsupported")
    root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True).strip())
    setting = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"], cwd=root,
        capture_output=True, text=True, check=False)
    if setting.returncode not in (0, 1):
        raise RuntimeError("cannot inspect existing hook configuration")
    if setting.returncode == 0 and setting.stdout.strip() != ".githooks":
        raise RuntimeError("existing core.hooksPath differs; integrate manually")
    legacy = Path(subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], cwd=root, text=True).strip())
    if not legacy.is_absolute():
        legacy = root / legacy
    for path in (legacy / "hooks").glob("*"):
        if path.is_file() and not path.name.endswith(".sample"):
            raise RuntimeError(f"existing hook needs review: {path}")
    prepare_hooks(root)
    subprocess.run(["git", "config", "--local", "core.hooksPath", ".githooks"],
                   cwd=root, check=True)
    print("Installed local pre-commit/pre-push hooks. Remote CI is not configured.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
        print(f"Hooks not installed: {error}", file=sys.stderr)
        sys.exit(1)
