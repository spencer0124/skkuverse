"""Tests for the contract table generator.

This block replaces sentences that used to carry counts by hand, so the failure
that matters most is a wrong number rendered confidently. The rest guard the
same quiet failures as the fleet block: a malformed marker region, output that
depends on manifest key order, and drift that no check reports.

    python3 -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "contracts_table", TOOLS_DIR / "contracts_table.py",
)
assert _spec is not None and _spec.loader is not None
ct = importlib.util.module_from_spec(_spec)
sys.modules["contracts_table"] = ct
_spec.loader.exec_module(ct)


def manifest(*contracts: dict) -> dict:
    return {
        "repos": {
            "alpha": {"github": "org/alpha"},
            "beta": {"github": "org/beta"},
            "gamma": {"github": "org/gamma"},
        },
        "contracts": list(contracts),
    }


def contract(cid: str, status: str = "active", consumers: list | None = None) -> dict:
    return {
        "id": cid,
        "status": status,
        "producer": {"repo": "alpha", "path": "src/thing.json"},
        "consumers": consumers or [{"repo": "beta", "path": "vendored/thing.json"}],
    }


class TestSplice(unittest.TestCase):
    def test_replaces_between_markers_only(self):
        text = f"before\n{ct.START}\nOLD\n{ct.END}\nafter\n"
        out = ct.splice(text, "NEW")
        self.assertIn("before\n", out)
        self.assertIn("after\n", out)
        self.assertIn(f"{ct.START}\nNEW\n{ct.END}", out)
        self.assertNotIn("OLD", out)

    def test_is_idempotent(self):
        text = f"a\n{ct.START}\nOLD\n{ct.END}\nb\n"
        once = ct.splice(text, "BLOCK")
        self.assertEqual(once, ct.splice(once, "BLOCK"))

    def test_missing_markers_raise(self):
        for text in ("nothing", f"only {ct.START}", f"only {ct.END}"):
            with self.subTest(text=text):
                with self.assertRaises(ct.TableError):
                    ct.splice(text, "BLOCK")

    def test_duplicate_markers_raise(self):
        """Two blocks means the writer picks one and the reader trusts the other."""
        text = f"{ct.START}\nA\n{ct.END}\n{ct.START}\nB\n{ct.END}"
        with self.assertRaises(ct.TableError):
            ct.splice(text, "BLOCK")

    def test_extract_round_trips_splice(self):
        block = "| a | b |\n| --- | --- |"
        text = ct.splice(f"x\n{ct.START}\n\n{ct.END}\ny\n", block)
        self.assertEqual(ct.extract(text), block)


class TestCounts(unittest.TestCase):
    """The whole reason this is generated. A hand-written count goes stale
    silently; these assert the generated one cannot."""

    def test_counts_reflect_statuses(self):
        out = ct.render(manifest(
            contract("a", "active"),
            contract("b", "active"),
            contract("c", "planned"),
        ))
        self.assertIn("3 contracts — 2 active, 1 planned.", out)

    def test_single_status_omits_the_others(self):
        out = ct.render(manifest(contract("a", "active")))
        self.assertIn("1 contracts — 1 active.", out)
        self.assertNotIn("planned", out)

    def test_unknown_status_is_counted_not_dropped(self):
        """A status the manifest grows later must still appear. Dropping it
        would make the count disagree with the rows above it."""
        out = ct.render(manifest(
            contract("a", "active"),
            contract("b", "superseded"),
        ))
        self.assertIn("2 contracts", out)
        self.assertIn("1 superseded", out)


class TestOrdering(unittest.TestCase):
    def test_active_sorts_before_planned(self):
        out = ct.render(manifest(
            contract("zzz", "planned"),
            contract("aaa", "active"),
        ))
        self.assertLess(out.index("`aaa`"), out.index("`zzz`"))

    def test_unknown_status_sorts_last_without_raising(self):
        out = ct.render(manifest(
            contract("weird", "experimental"),
            contract("normal", "active"),
        ))
        self.assertLess(out.index("`normal`"), out.index("`weird`"))

    def test_output_is_independent_of_manifest_order(self):
        """Otherwise reordering the JSON would rewrite the block and --check
        would fail for a change that means nothing."""
        a, b = contract("a"), contract("b")
        self.assertEqual(ct.render(manifest(a, b)), ct.render(manifest(b, a)))


class TestLinkDefinitions(unittest.TestCase):
    def test_only_cited_repos_get_definitions(self):
        """gamma is declared in the manifest but party to no contract."""
        out = ct.render(manifest(contract("a")))
        self.assertIn("[alpha]: https://github.com/org/alpha", out)
        self.assertIn("[beta]: https://github.com/org/beta", out)
        self.assertNotIn("[gamma]:", out)

    def test_each_repo_is_defined_once(self):
        out = ct.render(manifest(contract("a"), contract("b"), contract("c")))
        self.assertEqual(out.count("[alpha]: "), 1)

    def test_every_referenced_label_has_a_definition(self):
        """A reference-style link with no definition renders as literal
        brackets on the landing page."""
        out = ct.render(manifest(
            contract("a", consumers=[
                {"repo": "beta", "path": "x"},
                {"repo": "gamma", "path": "y"},
            ]),
        ))
        table, _, defs = out.partition("\n\n")
        for label in ("alpha", "beta", "gamma"):
            self.assertIn(f"[{label}]", table)
            self.assertIn(f"[{label}]: ", defs + out)


class TestMalformedInput(unittest.TestCase):
    def test_undeclared_repo_raises(self):
        data = manifest(contract("a"))
        data["contracts"][0]["producer"]["repo"] = "ghost"
        with self.assertRaises(ct.TableError):
            ct.render(data)

    def test_contract_without_consumers_raises(self):
        """A contract nobody vendors is a typo, not a valid row."""
        data = manifest(contract("a"))
        data["contracts"][0]["consumers"] = []
        with self.assertRaises(ct.TableError):
            ct.render(data)

    def test_contract_without_id_raises(self):
        data = manifest(contract("a"))
        del data["contracts"][0]["id"]
        with self.assertRaises(ct.TableError):
            ct.render(data)


class TestAgainstTheRealManifest(unittest.TestCase):
    """The generator has to survive the manifest actually in the repository,
    not only the shapes invented above."""

    def test_renders(self):
        out = ct.render()
        self.assertIn("| Contract | Owned by | Vendored into | Enforced |", out)
        self.assertRegex(out, r"\d+ contracts — ")

    def test_is_deterministic(self):
        self.assertEqual(ct.render(), ct.render())

    def test_readme_block_is_current(self):
        """The same assertion ci.yml makes. Kept here too so a manifest edit
        that forgets to regenerate fails locally at `npm test` speed."""
        text = ct.README.read_text(encoding="utf-8")
        self.assertEqual(ct.extract(text), ct.render())


if __name__ == "__main__":
    unittest.main()
