#!/usr/bin/env python3
"""Render the pinned state of every SKKUverse repo into README.md.

`.github/workflows/fleet-snapshot.yml` pins each repo's `main` as a submodule
at the repository root once a day. Those pins are the record; this script is
the rendering that puts them on the landing page.

Two modes, deliberately asymmetric:

    fleet_table.py            rewrite the block. Needs the submodules
                                 checked out, because the date and subject
                                 come from their object stores. The cron.

    fleet_table.py --check    verify the block. Offline, index-only,
                                 milliseconds. Runs in ci.yml on every PR.

`--check` deliberately verifies less than the writer produces. It confirms the
markers are well-formed and that every SHA in the block matches the gitlink in
the index, in `.gitmodules` order. It CANNOT confirm the date or subject text,
because those live in the submodules' objects and ci.yml checks out with
`submodules: false`. That gap is stated here rather than left implied, since a
check believed to cover more than it does is the worse failure.

Compare `contracts_table.py`, which verifies its block completely: every input
it reads is a file in this repository.

Why the check exists at all: the cron regenerates only when a pin actually
moved, so it will never silently correct a hand-edited block.

THE CONSTRAINT THAT MUST NOT BE VIOLATED: the output is a pure function of the
pinned SHAs. No "age", no "N days ago", no "generated at" timestamp. Any
time-relative value would rewrite the block every day even when nothing moved,
which makes `--check` non-deterministic and destroys the workflow's ability to
tell a quiet day from a busy one. For the same reason the date column pins its
timezone here in code rather than reading the ambient TZ, so regenerating on a
laptop in KST and on a UTC runner produce identical bytes.

Stdlib only — same constraint as everything under `internal/`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# parents[2] because this sits at internal/render/, two levels down.
UMBRELLA_ROOT = Path(__file__).resolve().parents[2]
README = UMBRELLA_ROOT / "README.md"
GITMODULES = UMBRELLA_ROOT / ".gitmodules"

START = "<!-- fleet:start -->"
END = "<!-- fleet:end -->"

SUBMODULE_MODE = "160000"
COMMIT_TZ = "Asia/Seoul"
SUBJECT_MAX = 72


class SnapshotError(Exception):
    """Anything that would produce a wrong row. Always fatal — a blank or
    guessed cell on the landing page is exactly the silent lie this repo's
    conventions exist to prevent."""


def git(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or UMBRELLA_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def declared() -> list[tuple[str, str]]:
    """[(path, commit-url-base)] in .gitmodules file order.

    File order, not `git submodule status` order: the latter sorts by path,
    which would give ai/app/codepush/crawler/server/.com — readable, but
    disconnected from the Service topology table this sits directly beneath.
    """
    if not GITMODULES.is_file():
        raise SnapshotError(f"{GITMODULES} not found")

    order: list[str] = []
    paths: dict[str, str] = {}
    urls: dict[str, str] = {}
    pattern = re.compile(r"^submodule\.(.+)\.(path|url)$")

    raw = git("config", "--file", str(GITMODULES), "--list", "-z")
    for entry in raw.split("\0"):
        if not entry:
            continue
        key, _, value = entry.partition("\n")
        match = pattern.match(key)
        if not match:
            continue
        name, field = match.group(1), match.group(2)
        if name not in order:
            order.append(name)
        if field == "path":
            paths[name] = value
        else:
            urls[name] = value

    missing = [n for n in order if n not in paths or n not in urls]
    if missing:
        raise SnapshotError(f".gitmodules entries missing path or url: {missing}")
    if not order:
        raise SnapshotError(".gitmodules declares no submodules")

    # The org name is never typed here — it comes from the declared url, so a
    # rename only has to be fixed in one place.
    return [(paths[n], urls[n].removesuffix(".git")) for n in order]


def pins() -> dict[str, str]:
    """path -> pinned commit sha, read from the INDEX.

    The index is what this repo commits. A submodule working tree can be
    stale, uninitialised, or mid-update, so it is not the source of truth for
    what is being recorded.

    Scans every gitlink rather than a fixed directory, so the layout can move
    without this needing to know — the submodules lived under `repos/` before
    they were promoted to the repository root.
    """
    out: dict[str, str] = {}
    for line in git("ls-files", "--stage").splitlines():
        meta, path = line.split("\t", 1)
        mode, sha, _stage = meta.split()
        if mode == SUBMODULE_MODE:
            out[path] = sha
    return out


def commit_meta(path: str, sha: str) -> tuple[str, str]:
    """(committed date in KST, subject) for the pinned commit."""
    try:
        raw = git(
            "log", "-1", "--format=%cd%x00%s",
            f"--date=format-local:%Y-%m-%d", sha,
            cwd=UMBRELLA_ROOT / path,
            # TZ pinned so the bytes do not depend on where this runs.
            env={"TZ": COMMIT_TZ, "PATH": "/usr/bin:/bin"},
        )
    except SnapshotError as exc:
        raise SnapshotError(
            f"cannot read {sha[:7]} in {path} — the submodule is not checked out.\n"
            f"  Run: git submodule update --init -- {path}"
        ) from exc
    date, _, subject = raw.strip("\n").partition("\0")
    return date, subject


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def cell(subject: str) -> str:
    """Make an arbitrary commit subject safe inside a Markdown table cell.

    The text comes from another repo, so `|` breaking the table and raw HTML
    rendering are not hypothetical.
    """
    text = " ".join(subject.split())
    if len(text) > SUBJECT_MAX:
        text = text[: SUBJECT_MAX - 1].rstrip() + "…"
    return text.replace("|", "\\|").replace("<", "&lt;")


def render() -> str:
    pinned = pins()
    rows = [
        "| Repo | Pinned `main` | Committed (KST) | Subject |",
        "| --- | --- | --- | --- |",
    ]
    for path, url in declared():
        if path not in pinned:
            raise SnapshotError(
                f"{path} is declared in .gitmodules but has no gitlink in the index"
            )
        sha = pinned[path]
        date, subject = commit_meta(path, sha)
        name = path.rsplit("/", 1)[-1]
        rows.append(
            f"| {name} | [`{sha[:7]}`]({url}/commit/{sha}) | {date} | {cell(subject)} |"
        )
    return "\n".join(rows)


def splice(text: str, block: str) -> str:
    if text.count(START) != 1 or text.count(END) != 1:
        raise SnapshotError(
            f"README.md must contain exactly one {START} and one {END}"
        )
    head, rest = text.split(START, 1)
    _old, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
def write() -> int:
    text = README.read_text(encoding="utf-8")
    updated = splice(text, render())
    if updated == text:
        print("fleet snapshot unchanged")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"fleet snapshot written — {len(declared())} repos")
    return 0


def check() -> int:
    """Offline. Markers plus the SHA list, against the index."""
    text = README.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        print(f"README.md must contain exactly one {START} and one {END}", file=sys.stderr)
        return 1

    block = text.split(START, 1)[1].split(END, 1)[0]
    found = re.findall(r"/commit/([0-9a-f]{40})", block)
    pinned = pins()
    expected = [pinned[path] for path, _ in declared() if path in pinned]

    if found != expected:
        print("README fleet block does not match the pinned submodules.", file=sys.stderr)
        print(f"  in README: {[s[:7] for s in found]}", file=sys.stderr)
        print(f"  in index:  {[s[:7] for s in expected]}", file=sys.stderr)
        print("  Fix: python3 internal/render/fleet_table.py", file=sys.stderr)
        return 1

    print(f"fleet snapshot ok — {len(expected)} repos pinned")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fleet_table.py",
        description="Render or verify the fleet snapshot block in README.md.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verify the block against the index instead of rewriting it (offline)",
    )
    args = parser.parse_args(argv)
    return check() if args.check else write()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SnapshotError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(2)
