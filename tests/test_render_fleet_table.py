"""Tests for the fleet snapshot generator.

The block this writes sits on the landing page and is verified in CI, so the
failure modes that matter are the quiet ones: a table broken by a commit
subject from another repo, output that differs between machines, or a block
that drifts from the pins without anything noticing.

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import io
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

UMBRELLA_ROOT = Path(__file__).resolve().parents[1]
RENDER_DIR = UMBRELLA_ROOT / "internal" / "render"

_spec = importlib.util.spec_from_file_location(
    "fleet_table", RENDER_DIR / "fleet_table.py",
)
assert _spec is not None and _spec.loader is not None
fs = importlib.util.module_from_spec(_spec)
sys.modules["fleet_table"] = fs
_spec.loader.exec_module(fs)


SAMPLE_BLOCK = "| Repo | Pinned `main` |\n| --- | --- |\n| x | y |"


class TestSplice(unittest.TestCase):
    def test_replaces_between_markers_only(self):
        text = f"before\n{fs.START}\nOLD\n{fs.END}\nafter\n"
        out = fs.splice(text, "NEW")
        self.assertIn("before\n", out)
        self.assertIn("after\n", out)
        self.assertIn(f"{fs.START}\nNEW\n{fs.END}", out)
        self.assertNotIn("OLD", out)

    def test_is_idempotent(self):
        text = f"a\n{fs.START}\nOLD\n{fs.END}\nb\n"
        once = fs.splice(text, SAMPLE_BLOCK)
        self.assertEqual(once, fs.splice(once, SAMPLE_BLOCK))

    def test_missing_markers_raise(self):
        for text in ("no markers at all", f"only {fs.START}", f"only {fs.END}"):
            with self.subTest(text=text):
                with self.assertRaises(fs.SnapshotError):
                    fs.splice(text, SAMPLE_BLOCK)

    def test_duplicate_markers_raise(self):
        """Two blocks means the writer would silently pick one and the reader
        would trust the other."""
        text = f"{fs.START}\nA\n{fs.END}\n{fs.START}\nB\n{fs.END}"
        with self.assertRaises(fs.SnapshotError):
            fs.splice(text, SAMPLE_BLOCK)


class TestCell(unittest.TestCase):
    """A commit subject is arbitrary text authored in another repository."""

    def test_pipe_is_escaped(self):
        # An unescaped '|' silently splits the row into extra columns.
        self.assertEqual(fs.cell("feat: a | b"), "feat: a \\| b")

    def test_angle_bracket_is_escaped(self):
        # GitHub renders raw HTML inside table cells.
        self.assertIn("&lt;", fs.cell("fix: handle <script> tags"))
        self.assertNotIn("<script>", fs.cell("fix: handle <script> tags"))

    def test_newlines_and_runs_collapse(self):
        self.assertEqual(fs.cell("a\n\tb   c"), "a b c")

    def test_long_subject_truncates_with_ellipsis(self):
        out = fs.cell("x" * 200)
        self.assertLessEqual(len(out), fs.SUBJECT_MAX)
        self.assertTrue(out.endswith("…"))

    def test_short_subject_untouched(self):
        self.assertEqual(fs.cell("chore: bump"), "chore: bump")


class TestNoSelfDirtyingOutput(unittest.TestCase):
    """The block must be a pure function of the pinned SHAs.

    Any time-relative value ("3 days ago", a generated-at stamp) would rewrite
    the block every single day even when no repo moved. That makes --check
    non-deterministic and destroys the workflow's ability to distinguish a
    quiet day from a busy one. This is easy to reintroduce and expensive to
    unwind after a year of history, so it is pinned by a test.

    `commit_meta` is stubbed rather than read from the submodules, and that is
    deliberate: ci.yml checks out with `submodules: false` so umbrella PRs do
    not pay ~45 MB, and a test that only runs where someone happens to have
    initialised them is a test that does not guard anything in CI. Stubbing
    keeps this invariant enforced on every PR.
    """

    STUB = ("2026-08-04", "chore: a fixed subject")

    def setUp(self):
        self._real = fs.commit_meta
        fs.commit_meta = lambda path, sha: self.STUB
        self.addCleanup(lambda: setattr(fs, "commit_meta", self._real))

    def test_render_is_stable_across_calls(self):
        self.assertEqual(fs.render(), fs.render())

    def test_no_relative_time_words_in_output(self):
        text = fs.render().lower()
        for banned in ("ago", "today", "yesterday", "generated at", "as of"):
            self.assertNotIn(banned, text, f"{banned!r} would make the block self-dirtying")

    def test_render_passes_the_date_through_unmodified(self):
        for row in fs.render().splitlines()[2:]:
            self.assertEqual(row.split("|")[3].strip(), self.STUB[0])

    def test_date_format_is_absolute_in_code(self):
        """render() only forwards whatever commit_meta returns, so the
        absolute-date guarantee lives in the git format string."""
        source = (RENDER_DIR / "fleet_table.py").read_text(encoding="utf-8")
        self.assertIn("--date=format-local:%Y-%m-%d", source)
        self.assertNotIn("--date=relative", source)

    def test_timezone_is_pinned_in_code(self):
        """Not read from the ambient environment, or a laptop in KST and a UTC
        runner would produce different bytes for identical pins."""
        source = (RENDER_DIR / "fleet_table.py").read_text(encoding="utf-8")
        self.assertIn('COMMIT_TZ = "Asia/Seoul"', source)
        self.assertIn('env={"TZ": COMMIT_TZ', source)


class TestAgainstTheRealRepo(unittest.TestCase):
    """These run against the actual .gitmodules and index."""

    def test_declared_matches_gitmodules_order(self):
        """Row order must follow .gitmodules, not `git submodule status`,
        which sorts by path and would disconnect this table from the Service
        topology table directly above it in README."""
        declared = [p for p, _ in fs.declared()]
        raw = (UMBRELLA_ROOT / ".gitmodules").read_text(encoding="utf-8")
        in_file = re.findall(r"^\tpath = (.+)$", raw, re.M)
        self.assertEqual(declared, in_file)
        self.assertNotEqual(declared, sorted(declared), "order is path-sorted, not file order")

    def test_every_declared_submodule_is_pinned(self):
        pinned = fs.pins()
        for path, _ in fs.declared():
            self.assertIn(path, pinned)
            self.assertRegex(pinned[path], r"^[0-9a-f]{40}$")

    def test_urls_carry_no_git_suffix(self):
        """The commit link is built from the declared url, so the org name is
        never typed into the generator."""
        for _, url in fs.declared():
            self.assertFalse(url.endswith(".git"))
            self.assertTrue(url.startswith("https://github.com/"))

    def test_readme_block_matches_the_index(self):
        code, _out = run(fs.check)
        self.assertEqual(
            code, 0, "README block is stale — run internal/render/fleet_table.py"
        )

    def test_check_rejects_a_tampered_sha(self):
        readme = UMBRELLA_ROOT / "README.md"
        original = readme.read_text(encoding="utf-8")
        tampered = original.replace("/commit/" + fs.pins()[fs.declared()[0][0]],
                                    "/commit/" + "0" * 40)
        self.assertNotEqual(tampered, original, "test could not tamper with the block")
        try:
            readme.write_text(tampered, encoding="utf-8")
            code, out = run(fs.check)
        finally:
            readme.write_text(original, encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn("does not match", out)


def run(fn, *args) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        code = fn(*args)
    return code, buf.getvalue()


if __name__ == "__main__":
    unittest.main()
