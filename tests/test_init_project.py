"""Initialization must be additive, repeatable, and repository-local."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/init_project.py"


class InitializerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def initialize(self, root=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(root or self.root)],
            text=True, capture_output=True)

    def test_fresh_project_and_repeat(self):
        self.assertEqual(self.initialize().returncode, 0)
        result = self.initialize()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 files created", result.stdout)
        self.assertTrue((self.root / ".githooks/pre-commit").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())
        hook = subprocess.run(["git", "config", "--local", "--get", "core.hooksPath"],
                              cwd=self.root, capture_output=True)
        self.assertNotEqual(hook.returncode, 0)

    def test_fresh_project_quality_gate_passes(self):
        self.assertEqual(self.initialize().returncode, 0)
        result = subprocess.run(
            [sys.executable, "scripts/check_quality.py"], cwd=self.root,
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_conflict_stops_before_creating_any_files(self):
        target = self.root / "scripts/check_file_lines.py"
        target.parent.mkdir()
        target.write_text("existing implementation\n")
        self.assertNotEqual(self.initialize().returncode, 0)
        self.assertEqual(target.read_text(), "existing implementation\n")
        self.assertFalse((self.root / ".githooks").exists())

    def test_symlink_parent_refused(self):
        external = self.root / "external"
        external.mkdir()
        (self.root / "scripts").symlink_to(external, target_is_directory=True)
        self.assertNotEqual(self.initialize().returncode, 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_file_parent_refused_before_copy(self):
        (self.root / "scripts").write_text("not a directory\n")
        self.assertNotEqual(self.initialize().returncode, 0)
        self.assertFalse((self.root / ".githooks").exists())

    def test_subdirectory_not_mistaken_for_project_root(self):
        child = self.root / "child"
        child.mkdir()
        self.assertNotEqual(self.initialize(child).returncode, 0)
        self.assertEqual(list(child.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
