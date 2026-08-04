#!/usr/bin/env python3
"""Cross-repo config contract sync for the skkuverse ecosystem.

One SSOT lives in one repo; other repos vendor a copy. This tool is the
mechanism that keeps those copies honest, replacing a push-based script whose
failure mode was a single line of stdout.

Three edges, split by who can fix a failure:

  integrity   consumer file  <->  its own .contracts.lock.json
              offline, deterministic, blocks merge and deploy.
              Catches hand edits, partial copies, a codegen copy that landed
              without a lock update.

  freshness   consumer lock  <->  producer@main
              needs network, never blocks a consumer PR. Runs in a daily cron
              that opens a sync PR against the consumer itself.

  producer    regenerate     <->  committed artifacts
              lives in the producer's own CI, not here.

Deliberately NOT here: version strings. Every value in a lock file is a
content hash or an extracted constant, computed by `pull`. Nothing is
hand-authored, so nothing can be hand-authored wrong.

Stdlib only, no install step: `ubuntu-latest` ships python3, so a consumer
gains a contract gate without touching its dependency manifest.

    python3 tools/skkuverse_sync.py status
    python3 tools/skkuverse_sync.py check --repo server --root .
    python3 tools/skkuverse_sync.py check --fleet
    python3 tools/skkuverse_sync.py pull --all
    python3 tools/skkuverse_sync.py explain notices.topic-cap
    python3 tools/skkuverse_sync.py validate-manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TOOLS_DIR = Path(__file__).resolve().parent
UMBRELLA_ROOT = TOOLS_DIR.parent
MANIFEST_PATH = UMBRELLA_ROOT / "contracts" / "manifest.json"
# Sibling checkouts live next to the umbrella repo. Only --local uses this;
# every other mode addresses repos by their GitHub coordinates.
WORKSPACE_ROOT = UMBRELLA_ROOT.parent
LOCK_NAME = ".contracts.lock.json"

LOCK_VERSION = 1


class ContractError(Exception):
    """A contract cannot be evaluated. Always fatal — never downgraded to a
    skip, because a check that silently stops checking is worse than none."""


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"manifest not found: {path}")
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("manifestVersion") != 1:
        raise ContractError(
            f"unsupported manifestVersion {manifest.get('manifestVersion')!r}; "
            f"this tool speaks 1"
        )
    return manifest


def contracts_for_consumer(
    manifest: dict[str, Any], repo: str, *, active_only: bool = True,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Every (contract, consumer-entry) pair where `repo` is the consumer."""
    out = []
    for contract in manifest["contracts"]:
        if active_only and contract.get("status") != "active":
            continue
        for consumer in contract["consumers"]:
            if consumer["repo"] == repo:
                out.append((contract, consumer))
    return out


def consumer_repos(manifest: dict[str, Any]) -> list[str]:
    seen = []
    for contract in manifest["contracts"]:
        for consumer in contract["consumers"]:
            if consumer["repo"] not in seen:
                seen.append(consumer["repo"])
    return seen


# ---------------------------------------------------------------------------
# Hashing and extraction
# ---------------------------------------------------------------------------
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def short(digest: str | None) -> str:
    return (digest or "?")[:8]


def extract_int(text: str, pattern: str, where: str) -> int:
    """Pull a single integer constant out of source text.

    Fails closed. Regex extraction is brittle, but brittleness only matters
    if it fails *open* — "I can no longer find this constant" must itself be
    a build failure, or a rename silently stops the check forever.
    """
    hits = re.findall(pattern, text)
    if len(hits) != 1:
        raise ContractError(
            f"{where}: expected exactly 1 match for {pattern!r}, found {len(hits)}.\n"
            f"  The constant was renamed, reformatted, or duplicated.\n"
            f"  Update `extract` in contracts/manifest.json."
        )
    return int(hits[0])


RELATIONS: dict[str, tuple[Callable[[int, int], bool], str]] = {
    "eq": (lambda consumer, producer: consumer == producer, "=="),
    "lte": (lambda consumer, producer: consumer <= producer, "<="),
    "gte": (lambda consumer, producer: consumer >= producer, ">="),
}


def check_relation(name: str, consumer_value: int, producer_value: int) -> bool:
    if name not in RELATIONS:
        raise ContractError(
            f"unknown relation {name!r}; known: {', '.join(sorted(RELATIONS))}"
        )
    return RELATIONS[name][0](consumer_value, producer_value)


def relation_symbol(name: str) -> str:
    return RELATIONS[name][1] if name in RELATIONS else name


# ---------------------------------------------------------------------------
# Generators (mode: generate)
# ---------------------------------------------------------------------------
def _load_generators() -> dict[str, Callable[[bytes], bytes]]:
    # Imported lazily so `check --repo` — which never generates — keeps working
    # even if a generator module is broken.
    sys.path.insert(0, str(TOOLS_DIR))
    from generators.tabs_contract import tabs_contract_ts

    return {"tabs_contract_ts": tabs_contract_ts}


def run_generator(name: str, producer_bytes: bytes) -> bytes:
    generators = _load_generators()
    if name not in generators:
        raise ContractError(
            f"unknown generator {name!r}; known: {', '.join(sorted(generators))}"
        )
    return generators[name](producer_bytes)


# ---------------------------------------------------------------------------
# Remote access
# ---------------------------------------------------------------------------
def _auth_header() -> dict[str, str]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def resolve_ref(repo_cfg: dict[str, str]) -> str:
    """Resolve a branch to a commit sha.

    `git ls-remote`, not the REST API: unauthenticated api.github.com allows
    60 requests an hour, which a fleet check would burn through, while
    ls-remote has no such limit and needs no token for a public repo.
    """
    url = f"https://github.com/{repo_cfg['github']}.git"
    proc = subprocess.run(
        ["git", "ls-remote", url, repo_cfg["branch"]],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ContractError(
            f"git ls-remote failed for {repo_cfg['github']}: {proc.stderr.strip()}"
        )
    line = proc.stdout.strip().split("\n")[0]
    if not line:
        raise ContractError(
            f"{repo_cfg['github']} has no branch {repo_cfg['branch']!r}"
        )
    return line.split()[0]


def fetch_raw(repo_cfg: dict[str, str], commit: str, path: str) -> bytes | None:
    """Fetch one file at a pinned commit. None when the path does not exist.

    Pinned to the resolved sha rather than the branch name so a push landing
    mid-run cannot mix content from two commits into one report.
    """
    url = f"https://raw.githubusercontent.com/{repo_cfg['github']}/{commit}/{path}"
    request = urllib.request.Request(url, headers=_auth_header())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise ContractError(f"GET {url} failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ContractError(f"GET {url} failed: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Local access
# ---------------------------------------------------------------------------
def local_root(manifest: dict[str, Any], repo: str) -> Path:
    return WORKSPACE_ROOT / manifest["repos"][repo]["dir"]


def read_local(root: Path, path: str) -> bytes | None:
    target = root / path
    return target.read_bytes() if target.is_file() else None


def git_branch(root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "?"


def git_dirty_count(root: Path) -> int:
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return -1
    return len([line for line in proc.stdout.splitlines() if line.strip()])


# ---------------------------------------------------------------------------
# Lock files
# ---------------------------------------------------------------------------
def load_lock(root: Path) -> dict[str, Any]:
    path = root / LOCK_NAME
    if not path.is_file():
        return {"lockVersion": LOCK_VERSION, "contracts": {}}
    with open(path, encoding="utf-8") as f:
        lock = json.load(f)
    if lock.get("lockVersion") != LOCK_VERSION:
        raise ContractError(
            f"{path}: lockVersion {lock.get('lockVersion')!r}, expected {LOCK_VERSION}. "
            f"Re-run `pull` to rewrite it."
        )
    lock.setdefault("contracts", {})
    return lock


def write_lock(root: Path, repo: str, entries: dict[str, Any]) -> None:
    lock = {
        "lockVersion": LOCK_VERSION,
        "repo": repo,
        "note": (
            "Written by skkuverse_sync.py. Do not hand-edit, and never resolve a "
            "merge conflict here by hand - take either side, then re-run "
            "`pull --repo " + repo + "`."
        ),
        "contracts": dict(sorted(entries.items())),
    }
    path = root / LOCK_NAME
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# `requires` predicates
# ---------------------------------------------------------------------------
BUILD_ASSET_SCRIPT = "scripts/copy-build-assets.js"


def check_requirement(name: str, root: Path, path: str) -> str | None:
    """Return an error string, or None when satisfied."""
    if name == "server-build-asset":
        script = root / BUILD_ASSET_SCRIPT
        if not script.is_file():
            return f"{BUILD_ASSET_SCRIPT} not found - cannot verify the file reaches dist/"
        if path not in script.read_text(encoding="utf-8"):
            return (
                f"{path} is not listed in {BUILD_ASSET_SCRIPT}, so it will exist in "
                f"src/ and vanish from dist/ - the container dies at boot"
            )
        return None
    raise ContractError(f"unknown requirement {name!r}")


# ---------------------------------------------------------------------------
# check --repo (integrity edge, offline)
# ---------------------------------------------------------------------------
def cmd_check_repo(manifest: dict[str, Any], repo: str, root: Path) -> int:
    if repo not in manifest["repos"]:
        raise ContractError(
            f"unknown repo {repo!r}; known: {', '.join(sorted(manifest['repos']))}"
        )

    pairs = contracts_for_consumer(manifest, repo)
    planned = [
        c["id"] for c in manifest["contracts"]
        if c.get("status") == "planned"
        and any(x["repo"] == repo for x in c["consumers"])
    ]

    print(f"skkuverse contracts · integrity · {repo}")
    print()

    if not pairs:
        print(f"  no active contracts for {repo}")
        if planned:
            print(f"  {len(planned)} planned: {', '.join(planned)}")
        print()
        return 0

    lock = load_lock(root)
    failures = 0
    width = max(len(c["id"]) for c, _ in pairs)

    for contract, consumer in pairs:
        cid = contract["id"]
        entry = lock["contracts"].get(cid)
        if entry is None:
            failures += 1
            print(f"  FAIL  {cid:<{width}}  {consumer['path']}")
            print(f"          No entry in {LOCK_NAME}.")
            print(f"          Fix:   skkuverse_sync.py pull --repo {repo}")
            continue

        target = root / consumer["path"]
        if not target.is_file():
            # Fail closed. "Skip missing" is how a manifest quietly stops
            # covering a path that was renamed.
            failures += 1
            print(f"  FAIL  {cid:<{width}}  {consumer['path']}")
            print("          Declared path does not exist in this repo.")
            print("          Fix:   restore the file, or update contracts/manifest.json")
            continue

        if contract["kind"] == "constant":
            value = extract_int(
                target.read_text(encoding="utf-8"),
                consumer["extract"],
                f"{repo}:{consumer['path']}",
            )
            producer_value = entry.get("producer", {}).get("value")
            relation = consumer.get("relation", "eq")
            symbol = relation_symbol(relation)
            if producer_value is None:
                failures += 1
                print(f"  FAIL  {cid:<{width}}  {consumer['symbol']}={value}")
                print(f"          Lock has no producer value. Run pull --repo {repo}.")
            elif check_relation(relation, value, producer_value):
                producer = contract["producer"]
                commit = short(entry.get("producer", {}).get("commit"))
                print(
                    f"  OK    {cid:<{width}}  {consumer['symbol']}={value} {symbol} "
                    f"{producer['repo']} {producer['symbol']}={producer_value} "
                    f"(locked @ {commit})"
                )
            else:
                failures += 1
                producer = contract["producer"]
                print(f"  FAIL  {cid:<{width}}  {consumer['symbol']}={value}")
                print(
                    f"          Invariant violated: {consumer['symbol']} {symbol} "
                    f"{producer['repo']} {producer['symbol']} ({producer_value})"
                )
                print(f"          {contract.get('note', '')}")
        else:
            actual = sha256(target.read_bytes())
            expected = entry.get("sha256")
            if actual == expected:
                print(f"  OK    {cid:<{width}}  {consumer['path']}")
            else:
                failures += 1
                print(f"  FAIL  {cid:<{width}}  {consumer['path']}")
                print(f"          lock  {expected}")
                print(f"          file  {actual}")
                print(f"          The vendored file does not match {LOCK_NAME}.")
                print("          Cause: a hand edit, a partial copy, or a codegen")
                print("                 copy that landed without a lock update.")
                print(f"          Fix:   skkuverse_sync.py pull --repo {repo}")

        for requirement in consumer.get("requires", []):
            problem = check_requirement(requirement, root, consumer["path"])
            if problem:
                failures += 1
                print(f"  FAIL  {cid:<{width}}  requires:{requirement}")
                print(f"          {problem}")

    stale = set(lock["contracts"]) - {c["id"] for c, _ in pairs}
    for cid in sorted(stale):
        failures += 1
        print(f"  FAIL  {cid}")
        print("          In the lock but not an active contract for this repo.")
        print(f"          Fix:   skkuverse_sync.py pull --repo {repo}")

    print()
    if planned:
        print(f"  {len(planned)} planned (skipped): {', '.join(planned)}")
    if failures:
        print(f"  {failures} of {len(pairs)} contracts failed.")
        return 1
    print(f"  {len(pairs)} ok.")
    return 0


# ---------------------------------------------------------------------------
# pull (adopt upstream, rewrite locks)
# ---------------------------------------------------------------------------
def pull_repo(
    manifest: dict[str, Any], repo: str, root: Path, *, local: bool,
) -> tuple[int, list[str]]:
    """Returns (files_changed, report lines)."""
    pairs = contracts_for_consumer(manifest, repo)
    lines: list[str] = []
    if not pairs:
        planned = [
            c["id"] for c in manifest["contracts"]
            if c.get("status") == "planned"
            and any(x["repo"] == repo for x in c["consumers"])
        ]
        if planned:
            lines.append(f"{len(planned)} planned contracts skipped")
        else:
            lines.append("no contracts")
        return 0, lines

    lock = load_lock(root)
    entries = dict(lock["contracts"])
    changed_files = 0
    lock_changed = False
    width = max(len(c["id"]) for c, _ in pairs)

    for contract, consumer in pairs:
        cid = contract["id"]
        producer = contract["producer"]
        producer_cfg = manifest["repos"][producer["repo"]]

        if local:
            commit = "local"
            producer_bytes = read_local(local_root(manifest, producer["repo"]), producer["path"])
        else:
            commit = resolve_ref(producer_cfg)
            producer_bytes = fetch_raw(producer_cfg, commit, producer["path"])

        if producer_bytes is None:
            raise ContractError(
                f"{cid}: producer {producer['repo']}:{producer['path']} does not exist "
                f"at {commit}. Either the artifact was not committed, or the manifest "
                f"path is stale."
            )

        previous = entries.get(cid, {})

        if contract["kind"] == "constant":
            producer_value = extract_int(
                producer_bytes.decode("utf-8"),
                producer["extract"],
                f"{producer['repo']}:{producer['path']}",
            )
            target = root / consumer["path"]
            if not target.is_file():
                raise ContractError(
                    f"{cid}: {repo}:{consumer['path']} does not exist"
                )
            consumer_value = extract_int(
                target.read_text(encoding="utf-8"),
                consumer["extract"],
                f"{repo}:{consumer['path']}",
            )
            entry = {
                "path": consumer["path"],
                "symbol": consumer["symbol"],
                "value": consumer_value,
                "relation": consumer.get("relation", "eq"),
                "producer": {
                    "repo": producer["repo"],
                    "path": producer["path"],
                    "symbol": producer["symbol"],
                    "ref": producer_cfg["branch"],
                    "commit": commit,
                    "value": producer_value,
                },
            }
            # syncedAt is informational and never compared. Carrying the old
            # one forward on a no-op is what makes `pull --all` on a clean
            # fleet produce zero diffs — the property that keeps it trusted.
            if _entry_content(previous) == _entry_content(entry):
                entry["syncedAt"] = previous.get("syncedAt", now_iso())
                lines.append(f"{cid:<{width}}  unchanged  ({producer['symbol']}={producer_value})")
            else:
                entry["syncedAt"] = now_iso()
                lock_changed = True
                lines.append(
                    f"{cid:<{width}}  updated    "
                    f"{consumer['symbol']}={consumer_value}, "
                    f"{producer['symbol']}={producer_value} @ {short(commit)}"
                )
            entries[cid] = entry
            continue

        # kind: file
        if consumer.get("mode") == "generate":
            new_bytes = run_generator(consumer["generator"], producer_bytes)
        else:
            new_bytes = producer_bytes

        target = root / consumer["path"]
        old_bytes = target.read_bytes() if target.is_file() else None
        if old_bytes != new_bytes:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(new_bytes)
            changed_files += 1

        entry = {
            "path": consumer["path"],
            "sha256": sha256(new_bytes),
            "producer": {
                "repo": producer["repo"],
                "path": producer["path"],
                "ref": producer_cfg["branch"],
                "commit": commit,
                "sha256": sha256(producer_bytes),
            },
        }
        if _entry_content(previous) == _entry_content(entry) and old_bytes == new_bytes:
            entry["syncedAt"] = previous.get("syncedAt", now_iso())
            lines.append(f"{cid:<{width}}  unchanged")
        else:
            entry["syncedAt"] = now_iso()
            lock_changed = True
            lines.append(
                f"{cid:<{width}}  updated    "
                f"{short(previous.get('sha256'))} -> {short(entry['sha256'])}"
            )
        entries[cid] = entry

    stale = set(entries) - {c["id"] for c, _ in pairs}
    for cid in sorted(stale):
        del entries[cid]
        lock_changed = True
        lines.append(f"{cid:<{width}}  removed    (no longer an active contract here)")

    if lock_changed:
        write_lock(root, repo, entries)
        lines.append(f"wrote {LOCK_NAME}")

    return changed_files, lines


def _entry_content(entry: dict[str, Any]) -> dict[str, Any]:
    """An entry minus syncedAt — the part that decides whether it changed."""
    return {k: v for k, v in entry.items() if k != "syncedAt"}


def cmd_pull(
    manifest: dict[str, Any], repos: list[str], root: Path | None, *, local: bool,
) -> int:
    total_changed = 0
    needs_commit: list[str] = []
    for repo in repos:
        repo_root = root if root is not None else local_root(manifest, repo)
        if not repo_root.is_dir():
            print(f"  {repo:<9}skipped (no checkout at {repo_root})")
            continue
        changed, lines = pull_repo(manifest, repo, repo_root, local=local)
        total_changed += changed
        print(f"  {repo}")
        for line in lines:
            print(f"    {line}")
        if changed or any(line.startswith("wrote ") for line in lines):
            needs_commit.append(repo)
    print()
    if needs_commit:
        print(f"  {total_changed} file(s) changed. Commit in: {', '.join(needs_commit)}")
    else:
        print("  everything already in sync — nothing written")
    return 0


# ---------------------------------------------------------------------------
# status (the "check all at once" view)
# ---------------------------------------------------------------------------
def cmd_status(manifest: dict[str, Any], *, remote: bool) -> int:
    mode = "origin/main" if remote else "local working trees"
    location = "" if remote else f" · {WORKSPACE_ROOT}"
    print(f"skkuverse contracts · {mode}{location}")
    print()

    if not remote:
        trees = []
        for repo, cfg in manifest["repos"].items():
            root = WORKSPACE_ROOT / cfg["dir"]
            if not root.is_dir():
                trees.append((repo, "—", "NOT CHECKED OUT"))
                continue
            dirty = git_dirty_count(root)
            state = "clean" if dirty == 0 else f"DIRTY ({dirty} file{'s' if dirty != 1 else ''})"
            trees.append((repo, git_branch(root), state))
        repo_w = max(len(r) for r, _, _ in [*trees, ("repo", "", "")])
        branch_w = max(len(b) for _, b, _ in [*trees, ("", "branch", "")])
        print(f"  {'repo':<{repo_w}}  {'branch':<{branch_w}}  tree")
        for repo, branch, state in trees:
            print(f"  {repo:<{repo_w}}  {branch:<{branch_w}}  {state}")
        print()

    rows: list[tuple[str, str, str, str, str, str]] = []
    counts = {"ok": 0, "drift": 0, "planned": 0}
    notes: list[str] = []

    for contract in manifest["contracts"]:
        cid = contract["id"]
        producer = contract["producer"]
        producer_cfg = manifest["repos"][producer["repo"]]
        planned = contract.get("status") != "active"

        if planned:
            for consumer in contract["consumers"]:
                rows.append((
                    cid, contract["kind"],
                    f"{producer['repo']} {Path(producer['path']).name}",
                    f"{consumer['repo']} {Path(consumer['path']).name}",
                    "PLAN", "",
                ))
                counts["planned"] += 1
            continue

        if remote:
            commit = resolve_ref(producer_cfg)
            producer_bytes = fetch_raw(producer_cfg, commit, producer["path"])
        else:
            commit = "local"
            producer_bytes = read_local(local_root(manifest, producer["repo"]), producer["path"])

        for consumer in contract["consumers"]:
            consumer_cfg = manifest["repos"][consumer["repo"]]
            label_producer = f"{producer['repo']} {Path(producer['path']).name}"
            label_consumer = f"{consumer['repo']} {Path(consumer['path']).name}"

            if producer_bytes is None:
                rows.append((cid, contract["kind"], label_producer, label_consumer,
                             "DRIFT", "producer absent"))
                counts["drift"] += 1
                continue

            if remote:
                consumer_commit = resolve_ref(consumer_cfg)
                consumer_bytes = fetch_raw(consumer_cfg, consumer_commit, consumer["path"])
            else:
                consumer_bytes = read_local(
                    local_root(manifest, consumer["repo"]), consumer["path"],
                )

            if consumer_bytes is None:
                rows.append((cid, contract["kind"], label_producer, label_consumer,
                             "DRIFT", "consumer absent"))
                counts["drift"] += 1
                continue

            if contract["kind"] == "constant":
                producer_value = extract_int(
                    producer_bytes.decode("utf-8"), producer["extract"],
                    f"{producer['repo']}:{producer['path']}",
                )
                consumer_value = extract_int(
                    consumer_bytes.decode("utf-8"), consumer["extract"],
                    f"{consumer['repo']}:{consumer['path']}",
                )
                relation = consumer.get("relation", "eq")
                symbol = relation_symbol(relation)
                detail = f"{consumer_value} {symbol} {producer_value}"
                if check_relation(relation, consumer_value, producer_value):
                    rows.append((cid, contract["kind"], label_producer, label_consumer,
                                 "OK", detail))
                    counts["ok"] += 1
                else:
                    rows.append((cid, contract["kind"], label_producer, label_consumer,
                                 "DRIFT", detail))
                    counts["drift"] += 1
                continue

            if consumer.get("mode") == "generate":
                expected = run_generator(consumer["generator"], producer_bytes)
            else:
                expected = producer_bytes

            if sha256(expected) == sha256(consumer_bytes):
                rows.append((cid, contract["kind"], label_producer, label_consumer, "OK", ""))
                counts["ok"] += 1
            else:
                rows.append((cid, contract["kind"], label_producer, label_consumer,
                             "DRIFT", f"{short(sha256(expected))} vs {short(sha256(consumer_bytes))}"))
                counts["drift"] += 1

            if not remote:
                note = _uncommitted_note(manifest, consumer["repo"], consumer["path"], consumer_bytes)
                if note:
                    notes.append(f"{cid}: {note}")

    _print_rows(rows)
    print()
    print(f"  {counts['ok']} ok · {counts['drift']} drift · {counts['planned']} planned")
    for note in notes:
        print()
        print(f"  ! {note}")
    if not remote:
        print()
        print("  note: --local reports what is checked out, not what is on origin/main.")
        print("        Use `status --remote` for the authoritative answer.")
    return 1 if counts["drift"] else 0


def _uncommitted_note(
    manifest: dict[str, Any], repo: str, path: str, worktree_bytes: bytes,
) -> str | None:
    """Flag a file that matches its producer on disk but not in git.

    CI reads git, not your disk. A copy that landed and was never committed
    looks perfectly in sync locally and is invisible to every consumer.
    """
    root = local_root(manifest, repo)
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{path}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return f"{repo}:{path} is not in git HEAD at all"
    if proc.stdout != worktree_bytes:
        return (
            f"{repo}:{path} matches the producer but is UNCOMMITTED "
            f"(HEAD {short(sha256(proc.stdout))}, worktree {short(sha256(worktree_bytes))}) "
            f"— commit it or the next CI run goes red"
        )
    return None


def _print_rows(rows: list[tuple[str, str, str, str, str, str]]) -> None:
    if not rows:
        print("  (no contracts)")
        return
    headers = ("CONTRACT", "KIND", "PRODUCER", "CONSUMER", "STATE", "")
    widths = [
        max(len(row[i]) for row in (*rows, headers)) for i in range(5)
    ]
    print("  " + "  ".join(headers[i].ljust(widths[i]) for i in range(5)))
    for row in rows:
        line = "  " + "  ".join(row[i].ljust(widths[i]) for i in range(5))
        print(f"{line}  {row[5]}".rstrip())


# ---------------------------------------------------------------------------
# check --fleet (freshness edge, network)
# ---------------------------------------------------------------------------
def cmd_check_fleet(manifest: dict[str, Any], *, markdown: bool) -> int:
    lines: list[str] = []
    drift = ok = planned = 0

    lock_cache: dict[str, dict[str, Any]] = {}

    def consumer_lock(repo: str) -> dict[str, Any]:
        if repo not in lock_cache:
            cfg = manifest["repos"][repo]
            commit = resolve_ref(cfg)
            raw = fetch_raw(cfg, commit, LOCK_NAME)
            lock_cache[repo] = json.loads(raw) if raw else {"contracts": {}}
        return lock_cache[repo]

    for contract in manifest["contracts"]:
        cid = contract["id"]
        if contract.get("status") != "active":
            planned += len(contract["consumers"])
            lines.append(f"PLAN   {cid}  ({contract.get('status', 'planned')})")
            continue

        producer = contract["producer"]
        producer_cfg = manifest["repos"][producer["repo"]]
        producer_commit = resolve_ref(producer_cfg)
        producer_bytes = fetch_raw(producer_cfg, producer_commit, producer["path"])
        if producer_bytes is None:
            drift += 1
            lines.append(
                f"DRIFT  {cid}  producer {producer['repo']}:{producer['path']} absent "
                f"@ {short(producer_commit)}"
            )
            continue

        if contract["kind"] == "constant":
            current: Any = extract_int(
                producer_bytes.decode("utf-8"), producer["extract"],
                f"{producer['repo']}:{producer['path']}",
            )
            field = "value"
        else:
            current = sha256(producer_bytes)
            field = "sha256"

        for consumer in contract["consumers"]:
            entry = consumer_lock(consumer["repo"])["contracts"].get(cid)
            if entry is None:
                drift += 1
                lines.append(f"DRIFT  {cid}  {consumer['repo']} has no lock entry")
                continue
            locked = entry.get("producer", {}).get(field)
            if locked == current:
                ok += 1
                lines.append(
                    f"OK     {cid}  {producer['repo']} {short(producer_commit)} "
                    f"-> {consumer['repo']}"
                )
            else:
                drift += 1
                lines.append(
                    f"DRIFT  {cid}  {consumer['repo']} is behind\n"
                    f"         producer @ {short(producer_commit)}: {locked!r} -> {current!r}\n"
                    f"         Fix: skkuverse_sync.py pull --repo {consumer['repo']}"
                )

    if markdown:
        print("## skkuverse contract freshness")
        print()
        print("```")
        for line in lines:
            print(line)
        print("```")
        print()
        print(f"**{drift} drift · {ok} ok · {planned} planned**")
    else:
        print("skkuverse contracts · fleet freshness")
        print()
        for line in lines:
            print(f"  {line}")
        print()
        print(f"  {drift} drift · {ok} ok · {planned} planned")
    return 1 if drift else 0


# ---------------------------------------------------------------------------
# explain / validate-manifest
# ---------------------------------------------------------------------------
def cmd_explain(manifest: dict[str, Any], contract_id: str) -> int:
    for contract in manifest["contracts"]:
        if contract["id"] != contract_id:
            continue
        producer = contract["producer"]
        print(f"{contract['id']}  [{contract['kind']}, {contract.get('status')}]")
        print()
        print(f"  producer  {producer['repo']}:{producer['path']}")
        if "symbol" in producer:
            print(f"            symbol {producer['symbol']}  extract {producer['extract']!r}")
        if "derivedFrom" in producer:
            print(f"            derived from {', '.join(producer['derivedFrom'])}")
        if "generatedBy" in producer:
            print(f"            generated by {producer['generatedBy']}")
        for consumer in contract["consumers"]:
            print(f"  consumer  {consumer['repo']}:{consumer['path']}")
            detail = []
            if "mode" in consumer:
                detail.append(f"mode {consumer['mode']}")
            if "generator" in consumer:
                detail.append(f"generator {consumer['generator']}")
            if "relation" in consumer:
                detail.append(f"relation {consumer['symbol']} {relation_symbol(consumer['relation'])} producer")
            if consumer.get("requires"):
                detail.append(f"requires {', '.join(consumer['requires'])}")
            if detail:
                print(f"            {'; '.join(detail)}")
        if contract.get("note"):
            print()
            print(f"  {contract['note']}")
        return 0
    known = ", ".join(c["id"] for c in manifest["contracts"])
    raise ContractError(f"unknown contract {contract_id!r}; known: {known}")


def cmd_validate_manifest(manifest: dict[str, Any]) -> int:
    errors: list[str] = []
    seen: set[str] = set()
    repos = manifest["repos"]

    for repo, cfg in repos.items():
        for field in ("github", "branch", "dir"):
            if field not in cfg:
                errors.append(f"repos.{repo}: missing {field!r}")

    for contract in manifest["contracts"]:
        cid = contract.get("id")
        if not cid:
            errors.append("a contract has no id")
            continue
        if cid in seen:
            errors.append(f"{cid}: duplicate id")
        seen.add(cid)

        if contract.get("kind") not in ("file", "constant"):
            errors.append(f"{cid}: kind must be file or constant")
        if contract.get("status") not in ("active", "planned", "retired"):
            errors.append(f"{cid}: status must be active, planned or retired")

        producer = contract.get("producer", {})
        if producer.get("repo") not in repos:
            errors.append(f"{cid}: producer repo {producer.get('repo')!r} not in repos")
        if not producer.get("path"):
            errors.append(f"{cid}: producer has no path")

        if contract.get("kind") == "constant":
            for field in ("symbol", "extract"):
                if field not in producer:
                    errors.append(f"{cid}: constant producer needs {field!r}")
            if "extract" in producer:
                errors.extend(_check_regex(cid, "producer", producer["extract"]))

        if not contract.get("consumers"):
            errors.append(f"{cid}: no consumers")

        for consumer in contract.get("consumers", []):
            where = f"{cid}/{consumer.get('repo')}"
            if consumer.get("repo") not in repos:
                errors.append(f"{where}: repo not in repos")
            if consumer.get("repo") == producer.get("repo"):
                errors.append(f"{where}: producer and consumer are the same repo")
            if not consumer.get("path"):
                errors.append(f"{where}: no path")
            if contract.get("kind") == "constant":
                for field in ("symbol", "extract"):
                    if field not in consumer:
                        errors.append(f"{where}: constant consumer needs {field!r}")
                if "extract" in consumer:
                    errors.extend(_check_regex(where, "consumer", consumer["extract"]))
                relation = consumer.get("relation", "eq")
                if relation not in RELATIONS:
                    errors.append(f"{where}: unknown relation {relation!r}")
            else:
                mode = consumer.get("mode")
                if mode not in ("copy", "generate"):
                    errors.append(f"{where}: mode must be copy or generate")
                if mode == "generate":
                    if "generator" not in consumer:
                        errors.append(f"{where}: mode generate needs a generator")
                    else:
                        try:
                            if consumer["generator"] not in _load_generators():
                                errors.append(
                                    f"{where}: unknown generator {consumer['generator']!r}"
                                )
                        except Exception as exc:  # noqa: BLE001 - reported, not raised
                            errors.append(f"{where}: generator import failed: {exc}")

    print("skkuverse contracts · manifest validation")
    print()
    if errors:
        for error in errors:
            print(f"  ERROR  {error}")
        print()
        print(f"  {len(errors)} problem(s)")
        return 1
    total = len(manifest["contracts"])
    active = sum(1 for c in manifest["contracts"] if c.get("status") == "active")
    print(f"  OK  {total} contracts ({active} active), {len(repos)} repos")
    return 0


def _check_regex(where: str, side: str, pattern: str) -> list[str]:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return [f"{where}: {side} extract is not a valid regex: {exc}"]
    if compiled.groups != 1:
        return [
            f"{where}: {side} extract must have exactly 1 capture group, "
            f"has {compiled.groups}"
        ]
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skkuverse_sync.py",
        description="Cross-repo config contract sync for skkuverse.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="every contract at a glance")
    status.add_argument("--remote", action="store_true",
                        help="read origin/main instead of local working trees")
    status.add_argument("--local", action="store_true",
                        help="read local working trees (default)")

    check = sub.add_parser("check", help="verify contracts")
    check.add_argument("--repo", help="integrity edge for one repo (offline, CI mode)")
    check.add_argument("--root", default=".", help="that repo's checkout (default: .)")
    check.add_argument("--fleet", action="store_true",
                       help="freshness edge across every repo (network)")
    check.add_argument("--format", choices=("text", "markdown"), default="text")

    pull = sub.add_parser("pull", help="adopt upstream and rewrite locks")
    pull.add_argument("--repo", help="one repo")
    pull.add_argument("--all", action="store_true", help="every consumer repo")
    pull.add_argument("--root", help="that repo's checkout (default: the sibling dir)")
    pull.add_argument("--local", action="store_true",
                      help="read producers from sibling working trees, not origin/main")

    explain = sub.add_parser("explain", help="print the full chain for one contract")
    explain.add_argument("contract_id")

    sub.add_parser("validate-manifest", help="schema + self-consistency")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_manifest()

    if args.command == "status":
        return cmd_status(manifest, remote=args.remote)

    if args.command == "check":
        if args.fleet:
            return cmd_check_fleet(manifest, markdown=args.format == "markdown")
        if not args.repo:
            raise ContractError("check needs either --repo <name> or --fleet")
        return cmd_check_repo(manifest, args.repo, Path(args.root).resolve())

    if args.command == "pull":
        if args.all:
            repos = consumer_repos(manifest)
        elif args.repo:
            repos = [args.repo]
        else:
            raise ContractError("pull needs either --repo <name> or --all")
        for repo in repos:
            if repo not in manifest["repos"]:
                raise ContractError(f"unknown repo {repo!r}")
        root = Path(args.root).resolve() if args.root else None
        if root is not None and len(repos) > 1:
            raise ContractError("--root applies to a single --repo, not --all")
        return cmd_pull(manifest, repos, root, local=args.local)

    if args.command == "explain":
        return cmd_explain(manifest, args.contract_id)

    if args.command == "validate-manifest":
        return cmd_validate_manifest(manifest)

    raise ContractError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(2)
