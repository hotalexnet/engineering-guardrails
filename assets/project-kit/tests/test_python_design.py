"""Deliberate complexity, forbidden dependency and cycle violations."""

import ast
import json
import sys
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "scripts"))
from check_python_design import analyze, function_scores


def sources(files, layers=None):
    settings = {"python": {
        "max_function_complexity": 15,
        "source_roots": ["src"],
        "layers": layers or {"app": {"modules": ["app"], "allow": []}},
    }}
    result = {Path("quality-gates.json"): json.dumps(settings).encode()}
    result.update({Path(name): content.encode() for name, content in files.items()})
    return result


class PythonDesignTests(unittest.TestCase):
    def test_complexity_15_passes_and_16_fails(self):
        for branches, should_fail in ((14, False), (15, True)):
            with self.subTest(branches=branches):
                code = "def run(x):\n" + "    if x: x -= 1\n" * branches
                _, errors = analyze(sources({"src/app.py": code}))
                self.assertEqual(bool(errors), should_fail)

    def test_nested_functions_measured_independently(self):
        tree = ast.parse("def outer():\n    def inner(x):\n        if x: return 1\n")
        self.assertEqual([(name, score) for _, name, score in function_scores(tree)],
                         [("outer", 1), ("inner", 2)])

    def test_boolean_and_comprehension_filters_count(self):
        tree = ast.parse("def f(xs):\n    return [x for x in xs if x and x > 1]\n")
        self.assertEqual(list(function_scores(tree))[0][2], 4)

    def test_async_branch_and_lambda_are_measured(self):
        tree = ast.parse("async def f(x):\n    if x: return x\ng = lambda x: 1 if x else 0")
        self.assertEqual([score for _, _, score in function_scores(tree)], [2, 2])

    def test_forbidden_layer_import_fails(self):
        layers = {"core": {"modules": ["core"], "allow": []},
                  "ui": {"modules": ["ui"], "allow": ["core"]}}
        _, errors = analyze(sources({"src/core.py": "import ui\n",
                                     "src/ui.py": "x = 1\n"}, layers))
        self.assertTrue(any("forbidden dependency core -> ui" in e for e in errors))

    def test_allowed_layer_import_passes(self):
        layers = {"core": {"modules": ["core"], "allow": []},
                  "ui": {"modules": ["ui"], "allow": ["core"]}}
        _, errors = analyze(sources({"src/core.py": "x = 1\n",
                                     "src/ui.py": "from core import x\n"}, layers))
        self.assertEqual(errors, [])

    def test_cycle_fails_even_within_one_layer(self):
        _, errors = analyze(sources({"src/app/a.py": "from . import b\n",
                                     "src/app/b.py": "from . import a\n"}))
        self.assertTrue(any("import cycle" in e for e in errors))

    def test_standard_library_import_is_not_internal_edge(self):
        _, errors = analyze(sources({"src/app.py": "import os\nimport json\n"}))
        self.assertEqual(errors, [])

    def test_unowned_module_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exactly one layer"):
            analyze(sources({"src/unknown.py": "x = 1\n"}))

    def test_unmapped_source_root_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "source_root"):
            analyze(sources({"other/app.py": "x = 1\n"}))

    def test_missing_settings_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "quality-gates.json"):
            analyze({Path("src/app.py"): b"x = 1\n"})

    def test_overlapping_ownership_fails(self):
        layers = {"one": {"modules": ["app"], "allow": []},
                  "two": {"modules": ["app"], "allow": []}}
        with self.assertRaisesRegex(ValueError, "exactly one layer"):
            analyze(sources({"src/app.py": "x = 1\n"}, layers))

    def test_match_branches_and_guard_count(self):
        code = "def f(x):\n    match x:\n        case 1 if x: return 1\n        case _: return 0\n"
        self.assertEqual(list(function_scores(ast.parse(code)))[0][2], 3)


if __name__ == "__main__":
    unittest.main()
