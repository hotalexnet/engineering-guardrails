#!/usr/bin/env python3
"""Static Python function-complexity, declared-layer and import-cycle checks."""

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

from check_file_lines import file_contents, git, snapshot_tree


class Decisions(ast.NodeVisitor):
    """A documented branch-count metric, not a claim of tool equivalence."""

    def __init__(self):
        self.score = 1

    def generic_visit(self, node):
        if isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
                             ast.ExceptHandler, ast.Assert, ast.comprehension)):
            self.score += 1
        if isinstance(node, ast.comprehension):
            self.score += len(node.ifs)
        if isinstance(node, ast.BoolOp):
            self.score += len(node.values) - 1
        if isinstance(node, ast.Match):
            self.score += sum(not isinstance(case.pattern, ast.MatchAs)
                              or case.pattern.pattern is not None
                              for case in node.cases)
            self.score += sum(case.guard is not None for case in node.cases)
        super().generic_visit(node)

    def visit_FunctionDef(self, node):
        pass  # Nested functions are measured independently.

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef


def function_scores(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            visitor = Decisions()
            body = [node.body] if isinstance(node, ast.Lambda) else node.body
            for statement in body:
                visitor.visit(statement)
            yield node.lineno, getattr(node, "name", "<lambda>"), visitor.score


def load_settings(contents):
    raw = contents.get(Path("quality-gates.json"))
    if raw is None:
        raise ValueError("quality-gates.json is required; define Python module ownership")
    settings = json.loads(raw)["python"]
    limit, roots, layers = (settings["max_function_complexity"],
                           settings["source_roots"], settings["layers"])
    if type(limit) is not int or limit < 1:
        raise ValueError("complexity limit must be a positive integer")
    if not roots or any(Path(r).is_absolute() or ".." in Path(r).parts for r in roots):
        raise ValueError("source_roots must be nonempty relative paths")
    if not layers:
        raise ValueError("at least one Python layer is required")
    for name, layer in layers.items():
        if not layer["modules"] or set(layer["allow"]) - layers.keys():
            raise ValueError(f"invalid module/allow list for layer {name}")
    return limit, sorted(map(Path, roots), key=lambda p: len(p.parts), reverse=True), layers


def module_name(path, roots):
    for root in roots:
        if path.is_relative_to(root):
            relative = path.relative_to(root).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            return ".".join(parts)
    raise ValueError(f"{path}: not covered by a declared Python source_root")


def owner(module, layers):
    matches = {name for name, layer in layers.items()
               for prefix in layer["modules"]
               if module == prefix or module.startswith(prefix + ".")}
    if len(matches) != 1:
        raise ValueError(f"{module}: must belong to exactly one layer")
    return matches.pop()


def imports(tree, module, is_package):
    package = module if is_package else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".") if package else []
                if node.level > len(parts):
                    raise ValueError(f"{module}: relative import escapes source_root")
                prefix = parts[:len(parts) - node.level + 1]
                base = ".".join(prefix + ([base] if base else []))
            yield base
            yield from (base + "." + alias.name for alias in node.names)


def cycle_errors(graph):
    visited, stack, errors = set(), [], []

    def visit(module):
        if module in stack:
            errors.append("import cycle: " + " -> ".join(stack + [module]))
            return
        if module in visited:
            return
        stack.append(module)
        for target in sorted(graph[module]):
            visit(target)
        stack.pop()
        visited.add(module)

    for module in sorted(graph):
        visit(module)
    return errors


def analyze(contents):
    limit, roots, layers = load_settings(contents)
    trees, ownership, errors = {}, {}, []
    for path, content in contents.items():
        if path.suffix != ".py":
            continue
        module = module_name(path, roots)
        if not module or module in trees:
            raise ValueError(f"{path}: duplicate or empty Python module name")
        tree = ast.parse(content, filename=str(path))
        trees[module] = (path, tree)
        ownership[module] = owner(module, layers)
        for line, name, score in function_scores(tree):
            if score > limit:
                errors.append(f"{path}:{line}: {name} complexity {score} > {limit}")
    return len(trees), errors + dependency_errors(trees, ownership, layers)


def dependency_errors(trees, ownership, layers):
    graph = {module: set() for module in trees}
    errors = []
    for module, (path, tree) in trees.items():
        for imported in imports(tree, module, path.name == "__init__.py"):
            candidates = [name for name in trees
                          if imported == name or imported.startswith(name + ".")]
            if not candidates:
                continue  # Standard-library/third-party imports are outside layer checks.
            target = max(candidates, key=len)
            if target == module:
                continue  # Importing a member of the current package is not a self-cycle.
            graph[module].add(target)
            source_layer, target_layer = ownership[module], ownership[target]
            if source_layer != target_layer and target_layer not in layers[source_layer]["allow"]:
                errors.append(f"{path}: forbidden dependency {source_layer} -> {target_layer}")
    return errors + cycle_errors(graph)


def check(root, tree=None):
    try:
        contents = dict(file_contents(root, tree))
        count, errors = analyze(contents)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, SyntaxError) as error:
        print(f"Python design check FAILED: {error}", file=sys.stderr)
        return 1
    if errors:
        print("Python design check FAILED:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    print(f"PASS: {count} Python modules; complexity, declared layers and static cycles checked.")
    print("Scope: Python AST only; other languages and data-access boundaries require separate checks.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--staged", action="store_true")
    modes.add_argument("--revision")
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
        tree = snapshot_tree(root, args.staged, args.revision) if (
            args.staged or args.revision is not None) else None
        return check(root, tree)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Cannot inspect Python design: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
