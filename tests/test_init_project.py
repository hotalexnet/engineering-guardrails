"""Initialization must be additive, repeatable, and repository-local."""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import runpy


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
            cwd=self.root, text=True, capture_output=True)

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

    def test_templates_and_guide_are_copied_from_kit(self):
        result = self.initialize()
        self.assertEqual(result.returncode, 0, result.stderr)
        kit = SCRIPT.parents[1] / "assets/project-kit"
        for relative in ("examples/github-actions-quality.yml",
                         "examples/gitlab-ci-quality.yml", "docs/integration-guide.md"):
            with self.subTest(path=relative):
                self.assertTrue((kit / relative).is_file())
                self.assertEqual((self.root / relative).read_bytes(),
                                 (kit / relative).read_bytes())
        self.assertFalse((self.root / ".github/workflows/quality.yml").exists())

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

    def test_junction_parent_refused_before_copy(self):
        namespace = runpy.run_path(str(SCRIPT))
        with patch.object(Path, "is_junction", lambda path: path == self.root / "scripts"):
            with self.assertRaisesRegex(ValueError, "junction"):
                namespace["initialize"](self.root)
        self.assertFalse((self.root / ".githooks").exists())

    def test_all_cli_entrypoints_reject_python_311_early(self):
        kit = SCRIPT.parents[1] / "assets/project-kit/scripts"
        entries = [SCRIPT, *(kit / name for name in (
            "check_file_lines.py", "check_python_design.py", "check_quality.py", "install_hooks.py"))]
        runner = "import runpy, sys; sys.version_info = (3, 11, 0); runpy.run_path(sys.argv[1], run_name='__main__')"
        for entry in entries:
            with self.subTest(entry=entry.name):
                result = subprocess.run([sys.executable, "-c", runner, str(entry)],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("requires Python 3.12+", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_skill_readme_and_reference_local_links_exist(self):
        root = SCRIPT.parents[1]
        for name in ("SKILL.md", "README.md", "README.zh-CN.md"):
            for target in re.findall(r"\]\(([^)]+)\)", (root / name).read_text()):
                if not target.startswith(("http://", "https://", "#")):
                    with self.subTest(file=name, target=target):
                        self.assertTrue((root / target.split('#')[0]).exists())
        self.assertTrue((root / "references/project-gates.md").is_file())
        self.assertTrue((root / ".github/workflows/quality.yml").is_file())

    def test_quality_entry_layer_is_declared_in_both_configurations(self):
        root = SCRIPT.parents[1]
        for path in (root / "quality-gates.json", root / "assets/project-kit/quality-gates.json"):
            entry = json.loads(path.read_text())["python"]["layers"]["entry"]
            self.assertIn("check_quality", entry["modules"])
            self.assertIn("checks", entry["allow"])

    def test_subdirectory_not_mistaken_for_project_root(self):
        child = self.root / "child"
        child.mkdir()
        self.assertNotEqual(self.initialize(child).returncode, 0)
        self.assertEqual(list(child.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
