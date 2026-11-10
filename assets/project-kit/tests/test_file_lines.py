"""Boundary and deliberate-violation tests for the file line limit guard."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_file_lines.py"


class FileLineLimitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(
            ["git", "init", "-q"], cwd=self.root, check=True, capture_output=True
        )

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_guard(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def test_exactly_1000_lines_allowed(self):
        self.write("source.py", "# comment\n\n" * 500)
        self.assertEqual(self.run_guard().returncode, 0)

    def test_untracked_1001_lines_rejected(self):
        self.write("source.py", "# comment\n" * 1001)
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("source.py: 1001 lines > 1000", result.stderr)

    def test_html_css_script_and_configuration_all_count(self):
        for name in ("page.html", "style.css", "tool.sh", "config.json"):
            with self.subTest(name=name):
                path = self.write(name, "\n" * 1001)
                self.assertEqual(self.run_guard().returncode, 1)
                path.unlink()

    def test_no_final_newline_still_counts_last_line(self):
        self.write("source.js", "// comment\n" * 1000 + "// last line")
        self.assertEqual(self.run_guard().returncode, 1)

    def test_untracked_ignored_dependency_not_scanned(self):
        self.write(".gitignore", "node_modules/\n")
        self.write("node_modules/dependency.js", "// generated\n" * 1001)
        self.assertEqual(self.run_guard().returncode, 0)

    def test_tracked_file_cannot_hide_behind_gitignore(self):
        self.write("source.py", "# comment\n" * 1001)
        subprocess.run(["git", "add", "source.py"], cwd=self.root, check=True)
        self.write(".gitignore", "source.py\n")
        self.assertEqual(self.run_guard().returncode, 1)

    def test_markdown_and_binary_are_not_program_lines(self):
        self.write("requirements.md", "documentation\n" * 1001)
        (self.root / "image.bin").write_bytes(b"\x00" + b"\n" * 1001)
        self.assertEqual(self.run_guard().returncode, 0)

    def test_invalid_utf8_does_not_silently_skip(self):
        (self.root / "source.py").write_bytes(b"\xff" + b"\n" * 1001)
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("use UTF-8", result.stderr)

    def test_staged_violation_not_hidden_by_fixed_working_file(self):
        self.write("source.py", "# comment\n" * 1001)
        subprocess.run(["git", "add", "source.py"], cwd=self.root, check=True)
        self.write("source.py", "# fixed\n")
        self.assertEqual(self.run_guard().returncode, 0)
        self.assertEqual(self.run_guard("--staged").returncode, 1)

    def test_good_stage_not_confused_with_unstaged_violation(self):
        self.write("source.py", "# valid\n")
        subprocess.run(["git", "add", "source.py"], cwd=self.root, check=True)
        self.write("source.py", "# unstaged\n" * 1001)
        self.assertEqual(self.run_guard("--staged").returncode, 0)
        self.assertEqual(self.run_guard().returncode, 1)

    def test_revision_checks_tree_not_working_copy(self):
        self.write("source.py", "# violation\n" * 1001)
        subprocess.run(["git", "add", "source.py"], cwd=self.root, check=True)
        tree = subprocess.check_output(
            ["git", "write-tree"], cwd=self.root, text=True).strip()
        self.write("source.py", "# fixed\n")
        self.assertEqual(self.run_guard("--revision", tree).returncode, 1)

    def test_missing_tracked_file_not_an_error(self):
        path = self.write("source.py", "# comment\n")
        subprocess.run(["git", "add", "source.py"], cwd=self.root, check=True)
        path.unlink()
        self.assertEqual(self.run_guard().returncode, 0)


if __name__ == "__main__":
    unittest.main()
