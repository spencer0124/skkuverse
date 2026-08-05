"""Tests for the boundary between exported/ and internal/.

These do not test what a script does. They test the properties the directory
split promises, which no individual script can check for itself.

The shadowing case is the one that matters. `sync_contracts.py` inserts its own
directory at the FRONT of sys.path so it can import generators/, so a file here
named after a standard library module would shadow the real one for every repo
that runs the script — with a traceback pointing nowhere near the cause.

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

UMBRELLA_ROOT = Path(__file__).resolve().parents[1]
EXPORTED_DIR = UMBRELLA_ROOT / "exported"
INTERNAL_DIR = UMBRELLA_ROOT / "internal"

# The scripts other repositories invoke by absolute path. Renaming one of these
# is a breaking change for server, app and ai at the same time.
ENTRY_POINTS = ("sync_contracts.py", "lint_conventions.py")


def python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


class TestNoStdlibShadowing(unittest.TestCase):
    """The failure this prevents is silent in the umbrella and loud, but
    incomprehensible, in a consumer."""

    def test_no_exported_module_shadows_the_stdlib(self):
        offenders = sorted(
            p.relative_to(UMBRELLA_ROOT).as_posix()
            for p in python_files(EXPORTED_DIR)
            if p.stem in sys.stdlib_module_names
        )
        self.assertEqual(
            offenders, [],
            "these would shadow a standard library module for every consumer, "
            "because sync_contracts.py puts exported/ first on sys.path",
        )

    def test_no_exported_package_shadows_the_stdlib(self):
        offenders = sorted(
            p.relative_to(UMBRELLA_ROOT).as_posix()
            for p in EXPORTED_DIR.iterdir()
            if p.is_dir() and p.name != "__pycache__" and p.name in sys.stdlib_module_names
        )
        self.assertEqual(offenders, [], "a package name shadows just as a module name does")


class TestTheSurfaceIsWhatItClaims(unittest.TestCase):
    def test_every_entry_point_exists(self):
        for name in ENTRY_POINTS:
            with self.subTest(name=name):
                self.assertTrue(
                    (EXPORTED_DIR / name).is_file(),
                    f"{name} is named in consumers' CI; removing it breaks them",
                )

    def test_exported_holds_nothing_unexpected(self):
        """A script that drifts into exported/ silently acquires consumers.
        Adding one is fine — updating this list is the moment to notice."""
        found = sorted(p.name for p in EXPORTED_DIR.glob("*.py"))
        self.assertEqual(found, sorted(ENTRY_POINTS))

    def test_generators_travel_with_the_exported_scripts(self):
        """sync_contracts.py imports this, so it is reachable from a public
        entry point and therefore contract, whatever its name suggests."""
        self.assertTrue((EXPORTED_DIR / "generators" / "__init__.py").is_file())


class TestNoImportsAcrossTheBoundary(unittest.TestCase):
    """internal/ may read exported/, never the reverse. An exported script that
    imported an internal one would quietly make it contract too."""

    def imported_names(self, path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        return names

    def test_exported_never_imports_an_internal_module(self):
        internal_modules = {p.stem for p in python_files(INTERNAL_DIR)}
        for path in python_files(EXPORTED_DIR):
            with self.subTest(path=path.name):
                leaked = self.imported_names(path) & internal_modules
                self.assertEqual(
                    leaked, set(),
                    f"{path.name} imports {leaked}, which would make it contract",
                )


class TestStdlibOnly(unittest.TestCase):
    """Consumers install nothing, so a third-party import in exported/ would
    mean adding an install step to three other repositories."""

    def test_exported_imports_only_the_stdlib_or_its_own_package(self):
        local = {"generators"} | {p.stem for p in python_files(EXPORTED_DIR)}
        allowed = sys.stdlib_module_names | local
        for path in python_files(EXPORTED_DIR):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                names: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names.update(a.name.split(".")[0] for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                        names.add(node.module.split(".")[0])
                self.assertEqual(names - allowed, set())


if __name__ == "__main__":
    unittest.main()
