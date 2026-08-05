"""Tests for the structural prose checks.

The bold rule exists because Vale cannot express it, so the cases that matter
are the ones Vale got wrong: markup inside fenced code, frontmatter read as
prose, and run-in headings mistaken for emphasis. A false positive here is
worse than a miss, because it teaches people to ignore the check.

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
import unittest
from pathlib import Path

UMBRELLA_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "prose", UMBRELLA_ROOT / "internal" / "check" / "prose.py",
)
assert _spec is not None and _spec.loader is not None
pm = importlib.util.module_from_spec(_spec)
sys.modules["prose"] = pm
_spec.loader.exec_module(pm)


def doc(body: str) -> str:
    return textwrap.dedent(body).lstrip("\n")


def bold_findings(body: str) -> list[str]:
    return pm.check_bold(Path("f.md"), doc(body))


class TestBoldDetection(unittest.TestCase):
    def test_flags_mid_sentence_emphasis(self):
        self.assertEqual(len(bold_findings("This is **not** a copy.\n")), 1)

    def test_allows_a_run_in_heading(self):
        """`- **Term** - text` is the shape Google explicitly permits."""
        self.assertEqual(bold_findings("- **Term** - what it means\n"), [])

    def test_allows_bold_opening_a_line(self):
        self.assertEqual(bold_findings("**Rules central, globs local.** The file...\n"), [])

    def test_allows_an_ordered_run_in_heading(self):
        """`1. **Label.** text` is the same construct as the dash form. Without
        stripping the marker the digit counts as the preceding word, and every
        numbered list reads as bold overuse."""
        self.assertEqual(bold_findings("1. **Failure was silent.** A missing path exited 0.\n"), [])

    def test_allows_a_quoted_run_in_heading(self):
        self.assertEqual(bold_findings("> **Note.** Something worth knowing.\n"), [])

    def test_still_flags_emphasis_inside_a_list_item(self):
        """Stripping the marker must not excuse bold later in the item."""
        self.assertEqual(len(bold_findings("- The value is **never** hand-authored.\n")), 1)

    def test_reports_the_right_line_number(self):
        found = bold_findings("""
            one
            two
            three has **emphasis** in it
            """)
        self.assertEqual(len(found), 1)
        self.assertIn("f.md:3:", found[0])


class TestMarkupIsNotProse(unittest.TestCase):
    """Every case here is one the Vale implementation got wrong. `scope: raw`
    hands the rule the whole file, and BlockIgnores does not apply to it."""

    def test_ignores_bold_inside_a_fenced_block(self):
        self.assertEqual(bold_findings("""
            Text before.

            ```markdown
            A sample showing **bold** in use.
            ```
            """), [])

    def test_ignores_tilde_fences(self):
        self.assertEqual(bold_findings("""
            ~~~md
            A sample with **bold**.
            ~~~
            """), [])

    def test_ignores_frontmatter(self):
        """A `title:` line is metadata. Reading it as a sentence is what made
        the linter report a colon-usage error on every document."""
        found = pm.prose_lines(doc("""
            ---
            title: Some Title Here
            audience: public
            ---

            Real prose.
            """))
        self.assertEqual([line for _, line in found], ["Real prose."])

    def test_a_lone_rule_is_not_frontmatter(self):
        """`---` partway down a document is a thematic break, and everything
        after it is still prose."""
        found = pm.prose_lines(doc("""
            Opening line.

            ---

            Later prose.
            """))
        self.assertIn("Later prose.", [line for _, line in found])

    def test_ignores_headings_and_table_rows(self):
        found = pm.prose_lines(doc("""
            # A Heading

            | col | col |
            | --- | --- |
            | a | b |

            Body text.
            """))
        self.assertEqual([line for _, line in found], ["Body text."])


class TestSentenceLengths(unittest.TestCase):
    def test_counts_sentences(self):
        self.assertEqual(pm.sentence_lengths("One two three. Four five.\n"), [3, 2])

    def test_code_and_urls_do_not_inflate_word_counts(self):
        """An inline span collapses to one token and a link target to none, so
        a line of API names does not read as a long sentence."""
        lengths = pm.sentence_lengths("Run `some --long --command --here` now.\n")
        self.assertEqual(lengths, [3])

    def test_fenced_code_contributes_no_sentences(self):
        self.assertEqual(pm.sentence_lengths(doc("""
            ```bash
            echo one. echo two. echo three.
            ```
            """)), [])


class TestBurstiness(unittest.TestCase):
    def test_short_documents_are_not_judged(self):
        """A spread over three sentences says nothing, so it is not reported."""
        self.assertEqual(pm.check_burstiness(Path("f.md"), "One two. Three four. Five six.\n"), [])

    def test_uniform_sentences_are_flagged(self):
        body = " ".join(["alpha beta gamma delta epsilon."] * 12)
        self.assertEqual(len(pm.check_burstiness(Path("f.md"), body)), 1)

    def test_varied_sentences_pass(self):
        short = "One two."
        long = " ".join(["word"] * 30) + "."
        body = " ".join([short, long] * 6)
        self.assertEqual(pm.check_burstiness(Path("f.md"), body), [])


class TestTargetSelection(unittest.TestCase):
    def test_submodule_directories_are_skipped(self):
        """They record other repositories. A finding there is not fixable in
        this branch, which is the rule this repository holds itself to."""
        root = UMBRELLA_ROOT
        names = [p.relative_to(root).as_posix() for p in pm.targets(root)]
        self.assertTrue(names, "expected to find markdown in the repository")
        self.assertFalse([n for n in names if n.startswith("skkuverse")])

    def test_vale_styles_are_skipped(self):
        root = UMBRELLA_ROOT
        names = [p.relative_to(root).as_posix() for p in pm.targets(root)]
        self.assertFalse([n for n in names if n.startswith("styles/")])


class TestAgainstTheRepository(unittest.TestCase):
    def test_this_repository_passes(self):
        """The repository defining the rule has to satisfy it."""
        root = UMBRELLA_ROOT
        findings = []
        for path in pm.targets(root):
            text = path.read_text(encoding="utf-8")
            findings.extend(pm.check_bold(path.relative_to(root), text))
            findings.extend(pm.check_burstiness(path.relative_to(root), text))
        self.assertEqual(findings, [], "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
