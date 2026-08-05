#!/usr/bin/env python3
"""Enforce the workspace conventions that a vendored file cannot.

Some conventions are files, and those are handled as contracts: the umbrella
owns `conventions/markdownlint.jsonc` and `conventions/docs-template.md`, each
repo vendors a copy, and the hash lock plus `skkuverse_sync.py check` already
make drift a build failure. Nothing new is needed for them.

The rest are *properties of a repo's own files*, and no copy can express them:

    language      no Korean outside declared product-copy paths
    frontmatter   every document under docs/ carries the required keys
    structure     docs/ subdirectories are Diataxis folders, not ad-hoc ones

This checks those. It reads only the repo it is pointed at, so it is offline
and safe to block a merge on — the governing rule in CLAUDE.md is that a red
check the author cannot fix in the current branch is worse than no check.

    python3 conventions_lint.py --root .              everything
    python3 conventions_lint.py --root . --only language

Consumers run it from the umbrella clone their CI already makes for
`skkuverse_sync.py`, so adopting it costs about two lines of YAML and no new
dependency. Stdlib only, like the rest of tools/.

Repo-specific exemptions live in `.conventions.json` at the repo root, not
here — a central file listing every sibling's exceptions would be a second
place to forget to update.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HANGUL = re.compile(r"[가-힣]")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
KEY = re.compile(r"^([A-Za-z][\w-]*):\s*(.*)$", re.M)

REQUIRED_KEYS = {"title", "type", "status", "owner", "last-updated", "audience"}
ENUMS = {
    "status": {"draft", "accepted", "superseded", "deprecated"},
    "audience": {"internal", "public"},
}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Diataxis, plus the three this workspace adds. `decisions/` is ADRs;
# `internal/` and `archive/` are explicitly outside the reader-need taxonomy
# because they are filed by lifecycle rather than by need.
DOC_FOLDERS = {
    "tutorials", "how-to", "reference", "explanation",
    "decisions", "flows", "architecture", "internal", "archive", "plans",
}

# Skipped everywhere. Not exemptions — these are not this workspace's text.
ALWAYS_SKIP = (
    ".git/", "node_modules/", "__pycache__/", ".venv/", "venv/",
    "dist/", "build/", ".next/", ".expo/", "coverage/",
    "ios/Pods/", "android/", "vendor/", ".mypy_cache/", ".ruff_cache/",
)

CONFIG_NAME = ".conventions.json"

# A single line may opt out by carrying this marker, e.g. a policy document
# quoting Korean to explain why Korean is disallowed. Line-level and visible
# at the point of use, which beats a whole-file exemption in a distant config
# file — the reader of the line sees the reason without going looking.
# In Markdown, `<!-- conventions:allow-korean: quoting an example -->` renders
# as nothing.
ALLOW_MARKER = "conventions:allow-korean"


class LintError(Exception):
    """The check cannot run. Distinct from a finding: a finding means the repo
    is wrong, this means the checker is."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def load_config(root: Path) -> dict:
    """Per-repo exemptions, declared by the repo itself.

    Kept next to the code it exempts rather than in a central list, so the
    person adding a Korean i18n bundle is the person who declares it, in the
    same commit.
    """
    path = root / CONFIG_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LintError(f"{CONFIG_NAME} is not valid JSON: {exc}") from exc


def walk(root: Path, suffixes: tuple[str, ...] | None = None):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in rel for part in ALWAYS_SKIP):
            continue
        if suffixes and path.suffix not in suffixes:
            continue
        yield rel, path


# ---------------------------------------------------------------------------
# language — no Korean outside declared product copy
# ---------------------------------------------------------------------------
def check_language(root: Path, config: dict) -> list[str]:
    """Korean is allowed only where it IS the product.

    User-facing strings shipped to people — i18n bundles, store metadata,
    notice content, LLM prompts that must produce Korean output — are data,
    not documentation. Everything else is English: comments, docs, commit
    messages, CLI output. See the umbrella's CLAUDE.md.

    Each repo declares its own product-copy paths in .conventions.json:

        {"productCopy": ["src/i18n/**", "sources.json"]}
    """
    allowed = config.get("productCopy", [])
    scanned = config.get("language", {}).get("include", ["docs", "README.md", "CLAUDE.md"])
    findings = []

    for rel, path in walk(root, (".md",)):
        if not any(rel == s or rel.startswith(s.rstrip("/") + "/") for s in scanned):
            continue
        if any(_matches(rel, pattern) for pattern in allowed):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = [
            i for i, line in enumerate(text.splitlines(), 1)
            if HANGUL.search(line) and ALLOW_MARKER not in line
        ]
        if lines:
            shown = ", ".join(str(n) for n in lines[:5])
            more = f" (+{len(lines) - 5} more)" if len(lines) > 5 else ""
            findings.append(f"{rel}: Korean on line(s) {shown}{more}")
    return findings


def _matches(rel: str, pattern: str) -> bool:
    """Glob match that treats `**` as spanning separators, which fnmatch does
    not do reliably across platforms."""
    regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(regex, rel) is not None


# ---------------------------------------------------------------------------
# frontmatter
# ---------------------------------------------------------------------------
def check_frontmatter(root: Path, config: dict) -> list[str]:
    docs = root / "docs"
    if not docs.is_dir():
        return []

    exempt = set(config.get("frontmatterExempt", []))
    findings = []

    for rel, path in walk(docs, (".md",)):
        rel = f"docs/{rel}"
        if rel in exempt or Path(rel).name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            findings.append(f"{rel}: no frontmatter")
            continue
        keys = dict(KEY.findall(match.group(1)))
        missing = REQUIRED_KEYS - set(keys)
        if missing:
            findings.append(f"{rel}: missing {sorted(missing)}")
        for key, allowed in ENUMS.items():
            if key in keys and keys[key] not in allowed:
                findings.append(f"{rel}: {key}={keys[key]!r} not in {sorted(allowed)}")
        if "last-updated" in keys and not DATE.match(keys["last-updated"]):
            findings.append(f"{rel}: last-updated {keys['last-updated']!r} is not YYYY-MM-DD")
    return findings


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------
def check_structure(root: Path, config: dict) -> list[str]:
    """docs/ subdirectories must be Diataxis folders.

    Filing by the reader's need rather than by topic is the whole point of the
    taxonomy; an ad-hoc folder quietly reintroduces topic-filing.
    """
    docs = root / "docs"
    if not docs.is_dir():
        return []
    allowed = DOC_FOLDERS | set(config.get("extraDocFolders", []))
    return [
        f"docs/{child.name}/: not a Diataxis folder (allowed: {', '.join(sorted(allowed))})"
        for child in sorted(docs.iterdir())
        if child.is_dir() and child.name not in allowed
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
CHECKS = {
    "language": check_language,
    "frontmatter": check_frontmatter,
    "structure": check_structure,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conventions_lint.py",
        description="Check a repo against the shared SKKUverse conventions.",
    )
    parser.add_argument("--root", default=".", help="the repo to check (default: .)")
    parser.add_argument(
        "--only", choices=sorted(CHECKS), action="append",
        help="run just this check; repeatable. Useful while a repo is mid-migration.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise LintError(f"{root} is not a directory")
    config = load_config(root)
    selected = args.only or sorted(CHECKS)

    print(f"skkuverse conventions · {root.name}")
    print()

    total = 0
    for name in selected:
        findings = CHECKS[name](root, config)
        total += len(findings)
        if findings:
            print(f"  FAIL  {name}")
            for finding in findings[:20]:
                print(f"          {finding}")
            if len(findings) > 20:
                print(f"          … and {len(findings) - 20} more")
        else:
            print(f"  OK    {name}")

    print()
    if total:
        print(f"  {total} finding(s)")
        print(f"  Conventions: https://github.com/spencer0124/skkuverse/blob/main/CLAUDE.md")
        print(f"  Declare a legitimate exception in {CONFIG_NAME}, not by weakening the rule.")
        return 1
    print("  all conventions satisfied")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LintError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(2)
