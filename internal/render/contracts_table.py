#!/usr/bin/env python3
"""Render the contract topology from contracts/manifest.json into README.md.

The manifest already declares who produces each piece of shared configuration,
who vendors it, and whether the contract is enforced yet. That makes the
landing page's propagation table a rendering rather than something to keep in
sync by hand — including the counts, which is the point. A sentence saying
"two of these are planned" is wrong the moment a third is added, and nothing
reports it. A generated line cannot be wrong.

    contracts_table.py           rewrite the block
    contracts_table.py --check   verify it (what ci.yml runs)

Unlike fleet_table.py, `--check` here verifies the block completely: it
re-renders from the manifest and compares byte for byte. Every input is a file
in this repository, so there is nothing the check has to take on trust. The
fleet block cannot do this because its date and subject columns live inside
submodule objects that CI does not check out.

The same constraint as fleet_table.py applies: the output is a pure function
of the manifest. No timestamps, no "last synced", nothing that changes when the
manifest does not.

Stdlib only, same as everything under `internal/`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# parents[2] because this sits at internal/render/, two levels down.
UMBRELLA_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = UMBRELLA_ROOT / "contracts" / "manifest.json"
README = UMBRELLA_ROOT / "README.md"

START = "<!-- contracts:start -->"
END = "<!-- contracts:end -->"

# Ordered so the enforced contracts render first. Anything the manifest grows
# later that is not listed here sorts last rather than crashing, because a new
# status value should not take down the landing page.
STATUS_ORDER = ("active", "planned", "retired")


class TableError(Exception):
    """Anything that would render a wrong or partial row. Always fatal — a
    silently missing contract on the front page is the drift this repository
    exists to make visible."""


def load() -> dict:
    if not MANIFEST.is_file():
        raise TableError(f"{MANIFEST} not found")
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TableError(f"{MANIFEST} is not valid JSON: {exc}") from exc
    if not isinstance(data.get("contracts"), list):
        raise TableError("manifest has no `contracts` list")
    if not isinstance(data.get("repos"), dict):
        raise TableError("manifest has no `repos` map")
    return data


def repo_link(repos: dict, name: str) -> str:
    """Repo name as a reference-style link.

    Reference style rather than inline: the same six repos appear in every row,
    and inlining the URLs makes the source of a nine-row table unreadable. The
    definitions are emitted once at the end of the block by `link_defs`.
    """
    if name not in repos or "github" not in repos[name]:
        raise TableError(f"contract names repo `{name}`, which the manifest does not declare")
    return f"[{name}]"


def link_defs(repos: dict, used: set[str]) -> list[str]:
    """Reference-link definitions for the repos the table actually cites.

    Only the ones used, so a repo added to the manifest but not yet party to a
    contract does not leave a dangling definition behind.
    """
    return [f"[{name}]: https://github.com/{repos[name]['github']}" for name in sorted(used)]


def sort_key(contract: dict) -> tuple[int, str]:
    status = contract.get("status", "")
    rank = STATUS_ORDER.index(status) if status in STATUS_ORDER else len(STATUS_ORDER)
    return rank, contract.get("id", "")


def render(data: dict | None = None) -> str:
    # The manifest is injectable so the tests can exercise malformed and
    # future-shaped input without writing files.
    if data is None:
        data = load()
    repos = data["repos"]
    contracts = sorted(data["contracts"], key=sort_key)

    used: set[str] = set()
    rows = [
        "| Contract | Owned by | Vendored into | Enforced |",
        "| --- | --- | --- | --- |",
    ]
    for contract in contracts:
        cid = contract.get("id")
        producer = contract.get("producer", {})
        consumers = contract.get("consumers", [])
        if not cid or not producer.get("repo") or not consumers:
            raise TableError(f"contract {cid or '<unnamed>'} is missing id, producer or consumers")

        used.add(producer["repo"])
        used.update(c["repo"] for c in consumers)
        targets = ", ".join(
            f"{repo_link(repos, c['repo'])} `{c['path']}`" for c in consumers
        )
        status = contract.get("status", "")
        # Rendered as prose rather than a tick, so the table says what the
        # state means without a legend underneath it.
        enforced = {
            "active": "yes",
            "planned": "not yet",
            "retired": "retired",
        }.get(status, status or "unknown")

        rows.append(
            f"| `{cid}` | {repo_link(repos, producer['repo'])} `{producer['path']}` "
            f"| {targets} | {enforced} |"
        )

    counts: dict[str, int] = {}
    for contract in contracts:
        counts[contract.get("status", "unknown")] = counts.get(contract.get("status", "unknown"), 0) + 1
    summary = ", ".join(f"{counts[s]} {s}" for s in STATUS_ORDER if s in counts)
    extra = ", ".join(f"{n} {s}" for s, n in counts.items() if s not in STATUS_ORDER)
    if extra:
        summary = f"{summary}, {extra}" if summary else extra

    rows.append("")
    rows.append(f"{len(contracts)} contracts — {summary}.")
    rows.append("")
    rows.extend(link_defs(repos, used))
    return "\n".join(rows)


def splice(text: str, block: str) -> str:
    if text.count(START) != 1 or text.count(END) != 1:
        raise TableError(f"README.md must contain exactly one {START} and one {END}")
    head, rest = text.split(START, 1)
    _old, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def extract(text: str) -> str:
    if text.count(START) != 1 or text.count(END) != 1:
        raise TableError(f"README.md must contain exactly one {START} and one {END}")
    return text.split(START, 1)[1].split(END, 1)[0].strip("\n")


def write() -> int:
    text = README.read_text(encoding="utf-8")
    updated = splice(text, render())
    if updated == text:
        print("contracts table unchanged")
        return 0
    README.write_text(updated, encoding="utf-8")
    print("contracts table written")
    return 0


def check() -> int:
    text = README.read_text(encoding="utf-8")
    try:
        found = extract(text)
    except TableError as error:
        print(f"{error}", file=sys.stderr)
        return 1

    expected = render()
    if found != expected:
        print("README contracts block does not match contracts/manifest.json.", file=sys.stderr)
        print("  Fix: python3 internal/render/contracts_table.py", file=sys.stderr)
        return 1

    print("contracts table ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contracts_table.py",
        description="Render or verify the contract table in README.md.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verify the block against the manifest instead of rewriting it (offline)",
    )
    args = parser.parse_args(argv)
    return check() if args.check else write()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except TableError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(2)
