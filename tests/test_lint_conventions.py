"""Tests for the shared-conventions checker.

This runs as a blocking gate in other people's repositories, so the failure
that matters most is a false positive: a check that fails a merge for
something legitimate teaches people to bypass it, and then it guards nothing.
Most of these tests are therefore about what must NOT be reported.

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

UMBRELLA_ROOT = Path(__file__).resolve().parents[1]
EXPORTED_DIR = UMBRELLA_ROOT / "exported"

_spec = importlib.util.spec_from_file_location(
    "lint_conventions", EXPORTED_DIR / "lint_conventions.py",
)
assert _spec is not None and _spec.loader is not None
cl = importlib.util.module_from_spec(_spec)
sys.modules["lint_conventions"] = cl
_spec.loader.exec_module(cl)


GOOD_FRONTMATTER = """\
---
title: Something
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Something

> A summary.
"""


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def config(self, **kwargs) -> None:
        (self.root / cl.CONFIG_NAME).write_text(json.dumps(kwargs), encoding="utf-8")

    def run_check(self, name: str) -> list[str]:
        return cl.CHECKS[name](self.root, cl.load_config(self.root))


class TestLanguage(Case):
    def test_korean_in_docs_is_reported(self):
        self.write("docs/a.md", "# Title\n\n소유권 설명\n")
        self.assertEqual(len(self.run_check("language")), 1)

    def test_english_is_clean(self):
        self.write("docs/a.md", "# Title\n\nOwnership explained.\n")
        self.assertEqual(self.run_check("language"), [])

    def test_line_marker_exempts_only_that_line(self):
        """A policy document quoting Korean to explain the policy is the
        canonical case, and it should not require exempting the whole file."""
        self.write(
            "docs/a.md",
            "# T\n\nyou cannot grep 소유권 <!-- conventions:allow-korean: the example is the point -->\n"
            "그런데 이 줄은 표시가 없다\n",
        )
        findings = self.run_check("language")
        self.assertEqual(len(findings), 1)
        self.assertIn("line(s) 4", findings[0])

    def test_declared_product_copy_is_skipped(self):
        self.write("docs/i18n/ko.md", "안녕하세요")
        self.config(productCopy=["docs/i18n/**"])
        self.assertEqual(self.run_check("language"), [])

    def test_glob_spans_separators(self):
        """`**` must cross directory boundaries — fnmatch does not do this
        reliably, so the matcher is hand-rolled and needs pinning."""
        self.write("docs/a/b/c/ko.md", "한국어")
        self.config(productCopy=["docs/**"])
        self.assertEqual(self.run_check("language"), [])

    def test_glob_does_not_over_match(self):
        """A single `*` must not cross a separator, or one exemption would
        silently cover a whole subtree."""
        self.write("docs/a/deep/ko.md", "한국어")
        self.config(productCopy=["docs/*"])
        self.assertEqual(len(self.run_check("language")), 1)

    def test_paths_outside_the_scanned_set_are_ignored(self):
        """Source comments are not gated yet — the rule is forward-only, and
        claiming to check them would be a lie."""
        self.write("src/thing.ts", "// 한국어 주석\n")
        self.assertEqual(self.run_check("language"), [])

    def test_build_output_is_never_scanned(self):
        self.write("node_modules/pkg/readme.md", "한국어")
        self.write("docs/../dist/x.md", "한국어")
        self.assertEqual(self.run_check("language"), [])


class TestFrontmatter(Case):
    def test_valid_passes(self):
        self.write("docs/a.md", GOOD_FRONTMATTER)
        self.assertEqual(self.run_check("frontmatter"), [])

    def test_missing_frontmatter_is_reported(self):
        self.write("docs/a.md", "# No frontmatter\n")
        self.assertIn("no frontmatter", self.run_check("frontmatter")[0])

    def test_missing_key_is_reported(self):
        self.write("docs/a.md", GOOD_FRONTMATTER.replace("audience: public\n", ""))
        self.assertIn("audience", self.run_check("frontmatter")[0])

    def test_bad_enum_is_reported(self):
        self.write("docs/a.md", GOOD_FRONTMATTER.replace("status: accepted", "status: active"))
        self.assertIn("status", self.run_check("frontmatter")[0])

    def test_bad_date_is_reported(self):
        self.write("docs/a.md", GOOD_FRONTMATTER.replace("2026-08-05", "Aug 2026"))
        self.assertIn("last-updated", self.run_check("frontmatter")[0])

    def test_underscore_files_are_templates_and_exempt(self):
        self.write("docs/_template.md", "# Template\n")
        self.assertEqual(self.run_check("frontmatter"), [])

    def test_repo_without_docs_is_not_penalised(self):
        self.assertEqual(self.run_check("frontmatter"), [])


class TestStructure(Case):
    def test_diataxis_folders_pass(self):
        for folder in ("how-to", "reference", "explanation", "decisions"):
            self.write(f"docs/{folder}/a.md", GOOD_FRONTMATTER)
        self.assertEqual(self.run_check("structure"), [])

    def test_ad_hoc_folder_is_reported(self):
        self.write("docs/misc/a.md", GOOD_FRONTMATTER)
        self.assertIn("misc", self.run_check("structure")[0])

    def test_repo_can_declare_an_extra_folder(self):
        self.write("docs/runbooks/a.md", GOOD_FRONTMATTER)
        self.config(extraDocFolders=["runbooks"])
        self.assertEqual(self.run_check("structure"), [])


class TestConfigHandling(Case):
    def test_absent_config_is_fine(self):
        self.assertEqual(cl.load_config(self.root), {})

    def test_broken_config_raises_rather_than_silently_passing(self):
        (self.root / cl.CONFIG_NAME).write_text("{not json", encoding="utf-8")
        with self.assertRaises(cl.LintError):
            cl.load_config(self.root)


class TestTheUmbrellaObeysItsOwnRules(unittest.TestCase):
    """The repo that defines the conventions has to satisfy them, or nobody
    else has a reason to."""

    def test_all_checks_pass_on_this_repo(self):
        config = cl.load_config(UMBRELLA_ROOT)
        for name, check in cl.CHECKS.items():
            with self.subTest(check=name):
                self.assertEqual(check(UMBRELLA_ROOT, config), [], f"{name} failed")


if __name__ == "__main__":
    unittest.main()
