"""Tests for the contract sync tool.

Four repos clone this tool from main and run it as a blocking CI gate, so a
bug here reddens the whole fleet at once. The bias throughout is toward
testing that things fail *closed* — a check that silently stops checking is
the failure mode this whole system exists to prevent.

    python3 -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
UMBRELLA_ROOT = TOOLS_DIR.parent

sys.path.insert(0, str(TOOLS_DIR))
_spec = importlib.util.spec_from_file_location(
    "skkuverse_sync", TOOLS_DIR / "skkuverse_sync.py",
)
assert _spec is not None and _spec.loader is not None
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

from generators.tabs_contract import GeneratorError, tabs_contract_ts  # noqa: E402


def run(fn, *args, **kwargs) -> tuple[int, str]:
    """Call a cmd_* function, capturing stdout."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = fn(*args, **kwargs)
    return code, buffer.getvalue()


# ---------------------------------------------------------------------------
# The real manifest
# ---------------------------------------------------------------------------
class TestRealManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = sync.load_manifest()

    def test_validates(self):
        code, _ = run(sync.cmd_validate_manifest, self.manifest)
        self.assertEqual(code, 0)

    def test_every_contract_is_explainable(self):
        for contract in self.manifest["contracts"]:
            code, out = run(sync.cmd_explain, self.manifest, contract["id"])
            self.assertEqual(code, 0)
            self.assertIn(contract["id"], out)

    def test_unknown_contract_raises(self):
        with self.assertRaises(sync.ContractError):
            sync.cmd_explain(self.manifest, "no.such.contract")

    def test_manifest_carries_no_hashes_or_values(self):
        """The umbrella is a map, not a copy (docs/README.md).

        Hashes and values belong in the consumer locks, where they change.
        A number here would start lying the moment a sibling repo moved.
        """
        blob = json.dumps(self.manifest)
        for banned in ('"sha256"', '"value"', '"pin"', '"version":'):
            self.assertNotIn(banned, blob, f"{banned} does not belong in the manifest")


# ---------------------------------------------------------------------------
# Constant extraction — must fail closed
# ---------------------------------------------------------------------------
class TestExtractInt(unittest.TestCase):
    PATTERN = r"(?m)^const TOPIC_CAP = (\d+);$"

    def test_extracts(self):
        self.assertEqual(
            sync.extract_int("const TOPIC_CAP = 30;\n", self.PATTERN, "x"), 30,
        )

    def test_no_match_raises(self):
        """A renamed constant must be a build failure, not a silent pass."""
        with self.assertRaises(sync.ContractError) as ctx:
            sync.extract_int("const TOPIC_LIMIT = 30;\n", self.PATTERN, "x")
        self.assertIn("found 0", str(ctx.exception))
        self.assertIn("manifest.json", str(ctx.exception))

    def test_two_matches_raises(self):
        text = "const TOPIC_CAP = 30;\nconst TOPIC_CAP = 40;\n"
        with self.assertRaises(sync.ContractError) as ctx:
            sync.extract_int(text, self.PATTERN, "x")
        self.assertIn("found 2", str(ctx.exception))

    def test_anchor_excludes_reexport(self):
        """notices.topics.ts re-exports TOPIC_CAP; only the declaration counts."""
        text = "const TOPIC_CAP = 30;\nexport { TOPIC_CAP };\n"
        self.assertEqual(sync.extract_int(text, self.PATTERN, "x"), 30)

    def test_real_patterns_match_once(self):
        manifest = sync.load_manifest()
        contract = next(
            c for c in manifest["contracts"] if c["id"] == "notices.topic-cap"
        )
        cases = [
            (contract["producer"]["extract"], "export const MAX_TOPICS = 30;"),
            (contract["consumers"][0]["extract"], "const TOPIC_CAP = 30;"),
        ]
        for pattern, line in cases:
            with self.subTest(pattern=pattern):
                self.assertEqual(sync.extract_int(line + "\n", pattern, "x"), 30)


class TestRelations(unittest.TestCase):
    def test_lte_is_green_only_on_safe_states(self):
        """ADR 0005: the CF 400s payloads above MAX_TOPICS, so the server cap
        must stay under the app cap. `lte` must be green while the app is
        ahead (the mandated deploy order) and red when the server is ahead.
        """
        cases = [
            # (app MAX_TOPICS, server TOPIC_CAP, safe?)
            (10, 10, True),    # start
            (30, 10, True),    # app raised first — the correct order
            (30, 30, True),    # server caught up
            (10, 30, False),   # server raised first — CF rejects, retries burn
        ]
        for producer, consumer, safe in cases:
            with self.subTest(producer=producer, consumer=consumer):
                self.assertEqual(sync.check_relation("lte", consumer, producer), safe)

    def test_eq_would_red_the_safe_transition(self):
        """Why the manifest says lte and not eq."""
        self.assertFalse(sync.check_relation("eq", 10, 30))
        self.assertTrue(sync.check_relation("lte", 10, 30))

    def test_unknown_relation_raises(self):
        with self.assertRaises(sync.ContractError):
            sync.check_relation("approximately", 1, 1)


# ---------------------------------------------------------------------------
# tabs_contract_ts generator
# ---------------------------------------------------------------------------
class TestTabsContractGenerator(unittest.TestCase):
    CATEGORIES = [
        {"id": "dept", "tabMode": "picker"},
        {"id": "academic", "tabMode": "fixed"},
        {"id": "library", "tabMode": "picker"},
    ]

    def generate(self, categories) -> str:
        return tabs_contract_ts(json.dumps(categories).encode()).decode()

    def test_partitions_by_tab_mode_preserving_order(self):
        out = self.generate(self.CATEGORIES)
        self.assertIn("export const FIXED_TAB_KEYS = [\n  'academic',\n] as const;", out)
        self.assertIn(
            "export const KNOWN_PICKER_KEYS = [\n  'dept',\n  'library',\n] as const;", out,
        )

    def test_is_deterministic(self):
        first = self.generate(self.CATEGORIES)
        self.assertEqual(first, self.generate(self.CATEGORIES))

    def test_marks_itself_generated(self):
        self.assertIn("GENERATED — do not edit.", self.generate(self.CATEGORIES))

    def test_rejects_key_that_would_corrupt_a_topic_string(self):
        """A picker key IS the topic prefix: 'dept' -> 'dept:<id>'."""
        for bad in ("my:key", "My-Key", "9lives", "with/slash", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(GeneratorError):
                    self.generate([
                        {"id": bad, "tabMode": "picker"},
                        {"id": "academic", "tabMode": "fixed"},
                    ])

    def test_rejects_empty_picker_set(self):
        """Would silently disable every picker notification."""
        with self.assertRaises(GeneratorError):
            self.generate([{"id": "academic", "tabMode": "fixed"}])

    def test_rejects_empty_fixed_set(self):
        with self.assertRaises(GeneratorError):
            self.generate([{"id": "dept", "tabMode": "picker"}])

    def test_rejects_id_in_both_modes(self):
        with self.assertRaises(GeneratorError):
            self.generate([
                {"id": "dept", "tabMode": "picker"},
                {"id": "dept", "tabMode": "fixed"},
            ])


# ---------------------------------------------------------------------------
# check --repo (the blocking integrity edge)
# ---------------------------------------------------------------------------
FILE_MANIFEST = {
    "manifestVersion": 1,
    "repos": {
        "crawler": {"github": "o/crawler", "branch": "main", "dir": "crawler"},
        "server": {"github": "o/server", "branch": "main", "dir": "server"},
    },
    "contracts": [{
        "id": "t.file",
        "kind": "file",
        "status": "active",
        "producer": {"repo": "crawler", "path": "gen/a.json"},
        "consumers": [{"repo": "server", "path": "src/a.json", "mode": "copy"}],
    }],
}

CONST_MANIFEST = {
    "manifestVersion": 1,
    "repos": {
        "app": {"github": "o/app", "branch": "main", "dir": "app"},
        "server": {"github": "o/server", "branch": "main", "dir": "server"},
    },
    "contracts": [{
        "id": "t.cap",
        "kind": "constant",
        "status": "active",
        "producer": {
            "repo": "app", "path": "c.ts", "symbol": "MAX_TOPICS",
            "extract": r"(?m)^export const MAX_TOPICS = (\d+);$",
        },
        "consumers": [{
            "repo": "server", "path": "t.ts", "symbol": "TOPIC_CAP",
            "extract": r"(?m)^const TOPIC_CAP = (\d+);$", "relation": "lte",
        }],
    }],
}


class CheckRepoCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_lock(self, entries: dict) -> None:
        (self.root / sync.LOCK_NAME).write_text(
            json.dumps({"lockVersion": 1, "repo": "server", "contracts": entries}),
            encoding="utf-8",
        )


class TestCheckRepoFiles(CheckRepoCase):
    BODY = '{"a": 1}\n'

    def test_matching_hash_passes(self):
        self.write("src/a.json", self.BODY)
        self.write_lock({"t.file": {
            "path": "src/a.json", "sha256": sync.sha256(self.BODY.encode()),
        }})
        code, out = run(sync.cmd_check_repo, FILE_MANIFEST, "server", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("OK", out)

    def test_hand_edit_fails_with_a_cause_taxonomy(self):
        self.write("src/a.json", self.BODY)
        self.write_lock({"t.file": {"path": "src/a.json", "sha256": "0" * 64}})
        code, out = run(sync.cmd_check_repo, FILE_MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        # A failure a solo maintainer can't diagnose gets muted, so the
        # message must name the cause and print the fix verbatim.
        self.assertIn("Cause:", out)
        self.assertIn("pull --repo server", out)

    def test_missing_file_fails_closed(self):
        """Never 'skip missing' — that is how a renamed path silently stops
        being covered."""
        self.write_lock({"t.file": {"path": "src/a.json", "sha256": "0" * 64}})
        code, out = run(sync.cmd_check_repo, FILE_MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("does not exist", out)

    def test_missing_lock_entry_fails(self):
        self.write("src/a.json", self.BODY)
        self.write_lock({})
        code, out = run(sync.cmd_check_repo, FILE_MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("No entry", out)

    def test_lock_entry_for_an_unknown_contract_fails(self):
        """Rot: renamed or retired, so the manifest no longer declares it."""
        self.write("src/a.json", self.BODY)
        self.write_lock({
            "t.file": {"path": "src/a.json", "sha256": sync.sha256(self.BODY.encode())},
            "t.retired": {"path": "gone.json", "sha256": "0" * 64},
        })
        code, out = run(sync.cmd_check_repo, FILE_MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("t.retired", out)
        self.assertIn("not in the manifest at all", out)

    def test_lock_entry_ahead_of_activation_passes(self):
        """A consumer must be able to land its lock BEFORE the manifest flips
        the contract to active — otherwise no merge order works: activating
        first breaks the consumer's main (no lock entry yet), and locking
        first would be rejected as stale.
        """
        manifest = json.loads(json.dumps(FILE_MANIFEST))
        manifest["contracts"][0]["status"] = "planned"
        self.write("src/a.json", self.BODY)
        self.write_lock({"t.file": {
            "path": "src/a.json", "sha256": sync.sha256(self.BODY.encode()),
        }})
        code, out = run(sync.cmd_check_repo, manifest, "server", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("ahead", out)

    def test_check_is_offline(self):
        """Every blocking check must work with no network at all — otherwise
        a GitHub outage blocks a production deploy for an unrelated reason."""
        self.write("src/a.json", self.BODY)
        self.write_lock({"t.file": {
            "path": "src/a.json", "sha256": sync.sha256(self.BODY.encode()),
        }})

        def explode(*_args, **_kwargs):
            raise AssertionError("check --repo attempted network access")

        original_urlopen = sync.urllib.request.urlopen
        original_resolve = sync.resolve_ref
        sync.urllib.request.urlopen = explode
        sync.resolve_ref = explode
        try:
            code, out = run(sync.cmd_check_repo, FILE_MANIFEST, "server", self.root)
        finally:
            sync.urllib.request.urlopen = original_urlopen
            sync.resolve_ref = original_resolve
        self.assertEqual(code, 0, out)

    def test_unknown_repo_raises(self):
        with self.assertRaises(sync.ContractError):
            sync.cmd_check_repo(FILE_MANIFEST, "nope", self.root)


class TestCheckRepoConstants(CheckRepoCase):
    def lock_with(self, producer_value: int) -> None:
        self.write_lock({"t.cap": {
            "path": "t.ts", "symbol": "TOPIC_CAP", "relation": "lte",
            "producer": {"repo": "app", "symbol": "MAX_TOPICS",
                         "commit": "abc1234", "value": producer_value},
        }})

    def test_equal_passes(self):
        self.write("t.ts", "const TOPIC_CAP = 30;\n")
        self.lock_with(30)
        code, out = run(sync.cmd_check_repo, CONST_MANIFEST, "server", self.root)
        self.assertEqual(code, 0, out)

    def test_below_ceiling_passes(self):
        """The safe transitional state: app raised first, server not yet."""
        self.write("t.ts", "const TOPIC_CAP = 10;\n")
        self.lock_with(30)
        code, out = run(sync.cmd_check_repo, CONST_MANIFEST, "server", self.root)
        self.assertEqual(code, 0, out)

    def test_above_ceiling_fails(self):
        """The dangerous state: server would emit payloads the CF 400s."""
        self.write("t.ts", "const TOPIC_CAP = 40;\n")
        self.lock_with(30)
        code, out = run(sync.cmd_check_repo, CONST_MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("Invariant violated", out)

    def test_renamed_constant_raises_rather_than_passing(self):
        self.write("t.ts", "const TOPIC_LIMIT = 40;\n")
        self.lock_with(30)
        with redirect_stdout(io.StringIO()), self.assertRaises(sync.ContractError):
            sync.cmd_check_repo(CONST_MANIFEST, "server", self.root)


class TestBuildAssetRequirement(CheckRepoCase):
    """A JSON under src/notices/ that copy-build-assets.js does not list
    exists in source and vanishes from dist/ — the container dies at boot."""

    MANIFEST = json.loads(json.dumps(FILE_MANIFEST))
    MANIFEST["contracts"][0]["consumers"][0]["requires"] = ["server-build-asset"]

    def setUp(self):
        super().setUp()
        self.body = '{"a": 1}\n'
        self.write("src/a.json", self.body)
        self.write_lock({"t.file": {
            "path": "src/a.json", "sha256": sync.sha256(self.body.encode()),
        }})

    def test_listed_passes(self):
        self.write(sync.BUILD_ASSET_SCRIPT, "const files = ['src/a.json'];\n")
        code, out = run(sync.cmd_check_repo, self.MANIFEST, "server", self.root)
        self.assertEqual(code, 0, out)

    def test_unlisted_fails(self):
        self.write(sync.BUILD_ASSET_SCRIPT, "const files = ['src/b.json'];\n")
        code, out = run(sync.cmd_check_repo, self.MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("vanish from dist/", out)

    def test_missing_script_fails(self):
        code, out = run(sync.cmd_check_repo, self.MANIFEST, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("not found", out)

    def test_unknown_requirement_raises(self):
        with self.assertRaises(sync.ContractError):
            sync.check_requirement("teleportation", self.root, "src/a.json")


# ---------------------------------------------------------------------------
# Locks
# ---------------------------------------------------------------------------
class TestLocks(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_round_trip_sorted(self):
        sync.write_lock(self.root, "server", {"b": {"x": 1}, "a": {"y": 2}})
        lock = sync.load_lock(self.root)
        self.assertEqual(list(lock["contracts"]), ["a", "b"])

    def test_absent_lock_reads_as_empty(self):
        self.assertEqual(sync.load_lock(self.root)["contracts"], {})

    def test_wrong_lock_version_raises(self):
        (self.root / sync.LOCK_NAME).write_text('{"lockVersion": 99}', encoding="utf-8")
        with self.assertRaises(sync.ContractError):
            sync.load_lock(self.root)

    def test_syncedAt_is_not_part_of_identity(self):
        """`pull` must rewrite a lock only on a real change, or a clean fleet
        dirties four repos on every run and stops being trusted."""
        a = {"sha256": "x", "syncedAt": "2026-01-01T00:00:00Z"}
        b = {"sha256": "x", "syncedAt": "2026-08-04T00:00:00Z"}
        self.assertEqual(sync._entry_content(a), sync._entry_content(b))

    def test_producer_commit_is_not_part_of_identity(self):
        """The hash is the contract; the commit only records where it was
        seen. Otherwise a --local pull and a later remote pull of identical
        content would diff over a sha nothing compares."""
        a = {"sha256": "x", "producer": {"sha256": "y", "commit": "aaa"}}
        b = {"sha256": "x", "producer": {"sha256": "y", "commit": "bbb"}}
        self.assertEqual(sync._entry_content(a), sync._entry_content(b))

    def test_producer_sha_is_part_of_identity(self):
        a = {"sha256": "x", "producer": {"sha256": "y", "commit": "aaa"}}
        b = {"sha256": "x", "producer": {"sha256": "z", "commit": "aaa"}}
        self.assertNotEqual(sync._entry_content(a), sync._entry_content(b))


class TestLocalProducerGuard(unittest.TestCase):
    """`pull --local` must not bake a hash that exists only on disk.

    CI reads git. A lock referencing an uncommitted producer state points at
    something no runner can ever fetch, so the consumer goes red forever.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")

    def git(self, *args: str) -> None:
        import subprocess
        subprocess.run(["git", "-C", str(self.root), *args], check=True,
                       capture_output=True)

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).write_text(text, encoding="utf-8")

    def test_committed_content_is_accepted_with_its_sha(self):
        self.write("a.json", "{}\n")
        self.git("add", "a.json")
        self.git("commit", "-qm", "add")
        content, commit = sync.read_local_producer(self.root, "a.json", "crawler")
        self.assertEqual(content, b"{}\n")
        self.assertEqual(len(commit), 40)

    def test_uncommitted_change_raises(self):
        self.write("a.json", "{}\n")
        self.git("add", "a.json")
        self.git("commit", "-qm", "add")
        self.write("a.json", '{"drift": true}\n')
        with self.assertRaises(sync.ContractError) as ctx:
            sync.read_local_producer(self.root, "a.json", "crawler")
        self.assertIn("uncommitted", str(ctx.exception))

    def test_untracked_file_raises(self):
        self.write("a.json", "{}\n")
        self.git("commit", "-qm", "empty", "--allow-empty")
        with self.assertRaises(sync.ContractError) as ctx:
            sync.read_local_producer(self.root, "a.json", "crawler")
        self.assertIn("not in git HEAD", str(ctx.exception))

    def test_absent_file_returns_none(self):
        self.git("commit", "-qm", "empty", "--allow-empty")
        content, _ = sync.read_local_producer(self.root, "nope.json", "crawler")
        self.assertIsNone(content)

    def test_lock_warns_against_hand_editing(self):
        sync.write_lock(self.root, "server", {})
        note = sync.load_lock(self.root)["note"]
        self.assertIn("Do not hand-edit", note)
        self.assertIn("merge conflict", note)


# ---------------------------------------------------------------------------
# validate-manifest catches the ways a manifest rots
# ---------------------------------------------------------------------------
class TestValidateManifest(unittest.TestCase):
    def mutate(self, fn) -> tuple[int, str]:
        manifest = json.loads(json.dumps(FILE_MANIFEST))
        fn(manifest)
        return run(sync.cmd_validate_manifest, manifest)

    def test_clean_manifest_passes(self):
        code, _ = run(sync.cmd_validate_manifest, FILE_MANIFEST)
        self.assertEqual(code, 0)

    def test_unknown_producer_repo(self):
        code, out = self.mutate(
            lambda m: m["contracts"][0]["producer"].update(repo="ghost"),
        )
        self.assertEqual(code, 1)
        self.assertIn("not in repos", out)

    def test_duplicate_id(self):
        code, out = self.mutate(lambda m: m["contracts"].append(m["contracts"][0]))
        self.assertEqual(code, 1)
        self.assertIn("duplicate id", out)

    def test_self_referential_contract(self):
        code, out = self.mutate(
            lambda m: m["contracts"][0]["consumers"][0].update(repo="crawler"),
        )
        self.assertEqual(code, 1)
        self.assertIn("same repo", out)

    def test_bad_mode(self):
        code, out = self.mutate(
            lambda m: m["contracts"][0]["consumers"][0].update(mode="symlink"),
        )
        self.assertEqual(code, 1)
        self.assertIn("mode must be", out)

    def test_generate_without_generator(self):
        code, out = self.mutate(
            lambda m: m["contracts"][0]["consumers"][0].update(mode="generate"),
        )
        self.assertEqual(code, 1)
        self.assertIn("needs a generator", out)

    def test_unknown_generator(self):
        code, out = self.mutate(
            lambda m: m["contracts"][0]["consumers"][0].update(
                mode="generate", generator="make_coffee",
            ),
        )
        self.assertEqual(code, 1)
        self.assertIn("unknown generator", out)

    def test_extract_needs_exactly_one_capture_group(self):
        code, out = run(sync.cmd_validate_manifest, {
            "manifestVersion": 1,
            "repos": CONST_MANIFEST["repos"],
            "contracts": [{
                **CONST_MANIFEST["contracts"][0],
                "producer": {
                    **CONST_MANIFEST["contracts"][0]["producer"],
                    "extract": r"^export const MAX_TOPICS = \d+;$",
                },
            }],
        })
        self.assertEqual(code, 1)
        self.assertIn("capture group", out)

    def test_unsupported_manifest_version_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text('{"manifestVersion": 99, "contracts": []}')
            with self.assertRaises(sync.ContractError):
                sync.load_manifest(path)


if __name__ == "__main__":
    unittest.main()


class TestRetiredContractLockRot(CheckRepoCase):
    """A repo can end up with no active contracts — every one retired. Its
    lock must still be examined, or it carries rot forever unexamined."""

    EMPTY = {"manifestVersion": 1, "repos": FILE_MANIFEST["repos"], "contracts": []}

    def test_rotten_entry_fails_even_with_no_active_contracts(self):
        self.write_lock({"t.gone": {"path": "x.json", "sha256": "0" * 64}})
        code, out = run(sync.cmd_check_repo, self.EMPTY, "server", self.root)
        self.assertEqual(code, 1)
        self.assertIn("not in the manifest at all", out)

    def test_empty_lock_with_no_active_contracts_passes(self):
        self.write_lock({})
        code, out = run(sync.cmd_check_repo, self.EMPTY, "server", self.root)
        self.assertEqual(code, 0, out)
