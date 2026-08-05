"""Tests for the document index generator.

This block exists because a document was once written with full frontmatter and
never added to the hand-maintained index, so the index quietly described a
smaller repository than the one that existed. The rule that replaced it —
carrying frontmatter *is* what makes a file indexed — is what these guard.

The parsing tests point the module at a temporary tree rather than the real
repository, so they exercise shapes this repo does not currently contain.

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

UMBRELLA_ROOT = Path(__file__).resolve().parents[1]
RENDER_DIR = UMBRELLA_ROOT / "internal" / "render"

_spec = importlib.util.spec_from_file_location(
    "docs_index", RENDER_DIR / "docs_index.py",
)
assert _spec is not None and _spec.loader is not None
di = importlib.util.module_from_spec(_spec)
sys.modules["docs_index"] = di
_spec.loader.exec_module(di)


FRONTMATTER = """\
---
title: {title}
type: {type}
status: accepted
owner: someone@example.com
last-updated: 2026-08-05
audience: public
---

# {title}

> {summary}

## Body
"""


class TempTree:
    """Point the module at a throwaway repository."""

    def __init__(self, files: dict[str, str]):
        self._files = files
        self._tmp = tempfile.TemporaryDirectory()

    def __enter__(self) -> Path:
        root = Path(self._tmp.name)
        for rel, body in self._files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        self._saved = di.UMBRELLA_ROOT
        di.UMBRELLA_ROOT = root
        return root

    def __exit__(self, *exc):
        di.UMBRELLA_ROOT = self._saved
        self._tmp.cleanup()
        return False


def doc(title: str, summary: str, kind: str = "reference") -> str:
    return FRONTMATTER.format(title=title, type=kind, summary=summary)


class TestMembershipIsARule(unittest.TestCase):
    """The whole point: nothing has to be registered, so nothing is forgotten."""

    def test_a_file_with_frontmatter_is_indexed_without_being_registered(self):
        with TempTree({"docs/reference/thing.md": doc("Thing", "What it is.")}):
            paths = [rel for rel, _meta, _s in di.documents()]
        self.assertEqual(paths, ["docs/reference/thing.md"])

    def test_a_file_without_frontmatter_is_not_a_document(self):
        with TempTree({"docs/reference/notes.md": "# Just notes\n\nNo frontmatter.\n"}):
            self.assertEqual(di.documents(), [])

    def test_documents_outside_docs_are_still_indexed(self):
        """contracts/README.md and conventions/README.md live beside the
        artifacts they describe and must not be missed for it."""
        with TempTree({"contracts/README.md": doc("Contracts", "The registry.")}):
            paths = [rel for rel, _m, _s in di.documents()]
        self.assertEqual(paths, ["contracts/README.md"])

    def test_exempt_entry_points_are_skipped(self):
        files = {name: doc("X", "Y") for name in di.EXEMPT}
        files["docs/keep.md"] = doc("Keep", "Kept.")
        with TempTree(files):
            paths = [rel for rel, _m, _s in di.documents()]
        self.assertEqual(paths, ["docs/keep.md"])

    def test_submodule_directories_are_skipped(self):
        """Those record other repositories, whose docs are not ours to index."""
        with TempTree({
            "skkuverse-server/docs/thing.md": doc("Theirs", "Not ours."),
            "docs/ours.md": doc("Ours", "Ours."),
        }):
            paths = [rel for rel, _m, _s in di.documents()]
        self.assertEqual(paths, ["docs/ours.md"])


class TestSummaryExtraction(unittest.TestCase):
    def test_a_missing_summary_is_fatal(self):
        body = doc("Thing", "x").replace("> x\n", "")
        with TempTree({"docs/thing.md": body}):
            with self.assertRaises(di.IndexError_):
                di.documents()

    def test_a_missing_title_is_fatal(self):
        body = doc("Thing", "Summary.").replace("title: Thing\n", "")
        with TempTree({"docs/thing.md": body}):
            with self.assertRaises(di.IndexError_):
                di.documents()

    def test_a_wrapped_summary_loses_its_quote_markers(self):
        body = doc("Thing", "x").replace("> x\n", "> One line\n> and a second.\n")
        with TempTree({"docs/thing.md": body}):
            _rel, _meta, summary = di.documents()[0]
        self.assertEqual(summary, "One line and a second.")

    def test_links_are_flattened_to_their_text(self):
        """A summary is re-rendered in another file, so a relative target would
        resolve against the wrong document."""
        with TempTree({"docs/thing.md": doc("Thing", "See [Data Topology](data.md) too.")}):
            _rel, _meta, summary = di.documents()[0]
        self.assertEqual(summary, "See Data Topology too.")
        self.assertNotIn("(", summary)


class TestRendering(unittest.TestCase):
    def test_documents_group_by_directory(self):
        with TempTree({
            "docs/decisions/0001-a.md": doc("A", "First."),
            "docs/how-to/b.md": doc("B", "Second.", kind="how-to"),
        }):
            out = di.render()
        self.assertIn("### decisions", out)
        self.assertIn("### how-to", out)
        self.assertLess(out.index("### decisions"), out.index("### how-to"))

    def test_links_resolve_relative_to_docs_readme(self):
        self.assertEqual(di.link("docs/architecture/x.md"), "architecture/x.md")
        self.assertEqual(di.link("contracts/README.md"), "../contracts/README.md")

    def test_a_pipe_in_a_summary_cannot_split_the_row(self):
        self.assertEqual(di.cell("a | b"), "a \\| b")

    def test_a_long_summary_truncates(self):
        out = di.cell("x" * 500)
        self.assertLessEqual(len(out), di.SUMMARY_MAX)
        self.assertTrue(out.endswith("…"))

    def test_an_empty_tree_raises_rather_than_writing_nothing(self):
        with TempTree({"docs/notes.md": "no frontmatter\n"}):
            with self.assertRaises(di.IndexError_):
                di.render()


class TestSplice(unittest.TestCase):
    def test_replaces_between_markers_only(self):
        text = f"before\n{di.START}\nOLD\n{di.END}\nafter\n"
        out = di.splice(text, "NEW")
        self.assertIn("before\n", out)
        self.assertIn("after\n", out)
        self.assertNotIn("OLD", out)

    def test_is_idempotent(self):
        text = f"a\n{di.START}\nOLD\n{di.END}\nb\n"
        once = di.splice(text, "BLOCK")
        self.assertEqual(once, di.splice(once, "BLOCK"))

    def test_missing_or_duplicate_markers_raise(self):
        for text in ("none", f"only {di.START}", f"{di.START}{di.END}{di.START}{di.END}"):
            with self.subTest(text=text[:20]):
                with self.assertRaises(di.IndexError_):
                    di.splice(text, "BLOCK")

    def test_extract_round_trips_splice(self):
        block = "| a | b |\n| --- | --- |"
        text = di.splice(f"x\n{di.START}\n\n{di.END}\ny\n", block)
        self.assertEqual(di.extract(text), block)


class TestAgainstTheRealRepo(unittest.TestCase):
    def test_is_deterministic(self):
        self.assertEqual(di.render(), di.render())

    def test_the_committed_block_is_current(self):
        """The same assertion ci.yml makes, kept here so a new document that
        forgets to regenerate fails at test speed."""
        text = di.DOCS_README.read_text(encoding="utf-8")
        self.assertEqual(di.extract(text), di.render())

    def test_both_boundary_readmes_are_indexed(self):
        """exported/ and internal/ carry frontmatter, so the rule should pick
        them up with no registration step."""
        paths = [rel for rel, _m, _s in di.documents()]
        self.assertIn("exported/README.md", paths)
        self.assertIn("internal/README.md", paths)


if __name__ == "__main__":
    unittest.main()
