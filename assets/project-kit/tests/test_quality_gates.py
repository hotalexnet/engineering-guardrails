"""Exercise real local hooks using isolated temporary Git repositories."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "-q")
        self.git("config", "core.hooksPath", ".githooks")
        self.git("config", "user.name", "Gate Test")
        self.git("config", "user.email", "gate@example.invalid")
        for relative in ("scripts/check_file_lines.py", "scripts/check_quality.py",
                         "scripts/check_python_design.py", "quality-gates.json",
                         "scripts/install_hooks.py", ".githooks/pre-commit",
                         ".githooks/pre-push"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / relative, path)
            if relative.startswith(".githooks/"):
                path.chmod(0o755)
        (self.root / "tests").mkdir()
        self.test = self.root / "tests/test_file_lines.py"
        self.test.write_text(
            "import unittest\nclass Smoke(unittest.TestCase):\n"
            "    def test_valid(self): self.assertTrue(True)\n")
        self.git("add", ".")

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.root, text=True,
                              capture_output=True, check=check)

    def quality(self, *args, input=None):
        return subprocess.run(
            [sys.executable, "scripts/check_quality.py", *args],
            cwd=self.root, text=True, capture_output=True, input=input)

    def test_diff_is_explicitly_rejected_with_full_graph_reason(self):
        for args in (("--diff", "HEAD~1..HEAD"), ("--diff",)):
            with self.subTest(args=args):
                result = self.quality(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("--diff is not supported", result.stderr)
                self.assertIn("full dependency graph", result.stderr)
                self.assertNotIn("unrecognized arguments", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("PASS:", result.stdout)

    def test_valid_commit_hook_passes(self):
        self.assertEqual(self.git("commit", "-m", "valid", check=False).returncode, 0)

    def test_commit_hook_rejects_bad_index_even_with_fixed_worktree(self):
        code = self.root / "source.py"
        code.write_text("# violation\n" * 1001)
        self.git("add", "source.py")
        code.write_text("# fixed but not staged\n")
        result = self.git("commit", "-m", "invalid", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1001 lines > 1000", result.stderr)

    def test_snapshot_runs_staged_tests_not_fixed_working_tests(self):
        self.test.write_text(
            "import unittest\nclass Smoke(unittest.TestCase):\n"
            "    def test_fail(self): self.fail('staged failure')\n")
        self.git("add", "tests/test_file_lines.py")
        self.test.write_text("# working copy hides failure\n")
        result = self.quality("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("staged failure", result.stderr)

    def test_pre_push_hook_rejects_bad_committed_tip(self):
        code = self.root / "source.py"
        code.write_text("# violation\n" * 1001)
        self.git("add", "source.py")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-m", "bad fixture")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        code.write_text("# fixed but not committed\n")
        result = subprocess.run(
            [str(self.root / ".githooks/pre-push")], cwd=self.root,
            input=f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n",
            text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1001 lines > 1000", result.stderr)

    def test_commit_hook_rejects_complexity_violation(self):
        config_path = self.root / "quality-gates.json"
        config = json.loads(config_path.read_text())
        config["python"]["layers"]["entry"]["modules"].append("feature")
        config_path.write_text(json.dumps(config))
        code = self.root / "scripts/feature.py"
        code.write_text("def run(x):\n" + "    if x: x -= 1\n" * 15)
        self.git("add", "quality-gates.json", "scripts/feature.py")
        code.write_text("# unstaged fix\n")
        result = self.git("commit", "-m", "complex", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complexity 16 > 15", result.stderr)

    def test_commit_hook_rejects_forbidden_layer_dependency(self):
        path = self.root / "scripts/check_file_lines.py"
        original = path.read_text()
        path.write_text(original + "\nimport check_quality\n")
        self.git("add", "scripts/check_file_lines.py")
        path.write_text(original)
        result = self.git("commit", "-m", "wrong dependency", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden dependency checks -> entry", result.stderr)

    def test_delete_only_push_passes(self):
        result = self.quality("--pre-push", input=(
            f"(delete) {'0' * 40} refs/heads/old {'1' * 40}\n"))
        self.assertEqual(result.returncode, 0)

    def test_missing_gate_files_fail_closed(self):
        self.git("rm", "--cached", "tests/test_file_lines.py")
        self.assertNotEqual(self.quality("--staged").returncode, 0)

    def test_zero_tests_fail_closed(self):
        self.test.write_text("# no actual tests\n")
        self.git("add", "tests/test_file_lines.py")
        result = self.quality("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no tests discovered", result.stderr)

    def test_snapshot_supports_bare_script_imports_without_using_worktree(self):
        path = self.root / "scripts/check_file_lines.py"
        original = path.read_text()
        path.write_text(original + '\nSNAPSHOT_MARKER = "staged"\n')
        self.test.write_text(
            "import unittest\nfrom check_file_lines import SNAPSHOT_MARKER\n"
            "class Smoke(unittest.TestCase):\n"
            "    def test_snapshot(self): self.assertEqual(SNAPSHOT_MARKER, 'staged')\n")
        self.git("add", "scripts/check_file_lines.py", "tests/test_file_lines.py")
        path.write_text(original + '\nSNAPSHOT_MARKER = "working"\n')
        result = self.quality("--staged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pre_push_deduplicates_same_sha_for_two_branches(self):
        self.git("commit", "-m", "valid fixture")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        refs = ''.join(f"refs/heads/{name} {sha} refs/heads/{name} {'0' * 40}\n"
                       for name in ("one", "two"))
        result = self.quality("--pre-push", input=refs)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Checking push tip:"), 1)

    def test_extra_command_uses_snapshot_configuration(self):
        path = self.root / "quality-gates.json"
        config = json.loads(path.read_text())
        config["commands"] = [[sys.executable, "-c", "print('staged-command')"]]
        path.write_text(json.dumps(config))
        self.git("add", "quality-gates.json")
        config["commands"] = [[sys.executable, "-c", "raise SystemExit(99)"]]
        path.write_text(json.dumps(config))
        result = self.quality("--staged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("staged-command", result.stdout)

    def test_extra_command_failure_blocks_gate(self):
        path = self.root / "quality-gates.json"
        config = json.loads(path.read_text())
        config["commands"] = [[sys.executable, "-c", "raise SystemExit(7)"]]
        path.write_text(json.dumps(config))
        self.git("add", "quality-gates.json")
        self.assertEqual(self.quality("--staged").returncode, 7)

    def test_shell_command_string_is_rejected_without_traceback(self):
        path = self.root / "quality-gates.json"
        config = json.loads(path.read_text())
        config["commands"] = ["npm run lint && echo bypass"]
        path.write_text(json.dumps(config))
        result = self.quality()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commands[0]", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_bad_configuration_reports_filename_without_traceback(self):
        path = self.root / "quality-gates.json"
        for content in ('{broken', '{"python": {"source_roots": "scripts"}}'):
            with self.subTest(content=content):
                path.write_text(content)
                result = self.quality()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("quality-gates.json", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_native_windows_hook_installation_is_explicitly_rejected(self):
        runner = "import runpy, os; os.name = 'nt'; runpy.run_path('scripts/install_hooks.py', run_name='__main__')"
        result = subprocess.run([sys.executable, "-c", runner], cwd=self.root,
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("native Windows is unsupported", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_valid_pre_push_tip_passes(self):
        self.git("commit", "-m", "valid fixture")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.quality("--pre-push", input=(
            f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installer_refuses_other_hook_configuration(self):
        self.git("config", "core.hooksPath", "existing-hooks")
        result = subprocess.run(
            [sys.executable, "scripts/install_hooks.py"], cwd=self.root,
            text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("config", "core.hooksPath").stdout.strip(),
                         "existing-hooks")

    def test_installer_refuses_existing_legacy_hook(self):
        self.git("config", "--unset", "core.hooksPath")
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        result = subprocess.run(
            [sys.executable, "scripts/install_hooks.py"], cwd=self.root,
            text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(hook.exists())


if __name__ == "__main__":
    unittest.main()
