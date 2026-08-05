#!/usr/bin/env python3
"""Render the document index in docs/README.md from the documents themselves.

Every catalogued document already carries a frontmatter `title` and a one-line
summary blockquote under its H1, because the skeleton rule in docs/README.md
requires both. The index is therefore derivable, and deriving it removes the
failure this repository kept hitting: `conventions/README.md` was written with
full frontmatter and never added to the index, so the index quietly described a
smaller repository than the one that existed.

    docs_index.py           rewrite the block
    docs_index.py --check   verify it (what ci.yml runs)

Membership is a rule rather than a list: every Markdown file carrying
frontmatter is indexed. Nothing has to be registered, so nothing can be
forgotten. The two repo-root entry points are exempt for the reason given in
docs/README.md, and the template is skipped because it is a form, not a
document.

Offline and deterministic, like the other generators here. The summary text
comes from the document, so it cannot drift from what it describes.

Stdlib only, same as the rest of tools/.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
UMBRELLA_ROOT = TOOLS_DIR.parent
DOCS_README = UMBRELLA_ROOT / "docs" / "README.md"

START = "<!-- index:start -->"
END = "<!-- index:end -->"

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
KEY = re.compile(r"^([A-Za-z][\w-]*):\s*(.*)$", re.M)
SUMMARY = re.compile(r"^> (.+?)(?:\n>? *\n|\n[^>])", re.M | re.S)
QUOTE_PREFIX = re.compile(r"^ *> ?", re.M)
# A summary is lifted out of its own document and re-rendered here, so any
# relative link in it would resolve against the wrong file. Keep the link text
# and drop the target.
MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")

# Not this repository's text, or not a catalogued document.
SKIP_DIRS = ("styles/", "node_modules/", ".git/", "__pycache__/")
EXEMPT = ("README.md", "CLAUDE.md", "docs/README.md", "docs/_template.md")

SUMMARY_MAX = 160


class IndexError_(Exception):
    """A document that cannot be indexed correctly. Fatal, because a document
    silently missing from the index is the exact failure this replaces."""


def documents() -> list[tuple[str, dict, str]]:
    """(repo-relative path, frontmatter, summary) for every catalogued document."""
    out = []
    for path in sorted(UMBRELLA_ROOT.rglob("*.md")):
        rel = path.relative_to(UMBRELLA_ROOT).as_posix()
        if rel in EXEMPT or any(rel.startswith(d) for d in SKIP_DIRS):
            continue
        # The submodule directories record other repositories.
        if rel.split("/")[0].startswith("skkuverse"):
            continue

        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            continue        # not a catalogued document
        meta = {k: v.strip() for k, v in KEY.findall(match.group(1))}
        if "title" not in meta:
            raise IndexError_(f"{rel} has frontmatter but no title")

        body = text[match.end():]
        found = SUMMARY.search(body)
        if not found:
            raise IndexError_(
                f"{rel} has no `> summary` line under its H1. "
                f"The index is built from it, so it cannot be omitted."
            )
        summary = QUOTE_PREFIX.sub("", found.group(1))
        summary = MD_LINK.sub(r"\1", summary)
        out.append((rel, meta, " ".join(summary.split())))
    return out


def cell(text: str) -> str:
    """Make a document's own summary safe inside a table cell."""
    if len(text) > SUMMARY_MAX:
        text = text[: SUMMARY_MAX - 1].rstrip() + "…"
    return text.replace("|", "\\|")


def group(rel: str) -> str:
    """The heading a document files under, taken from its directory."""
    parent = rel.rsplit("/", 1)[0] if "/" in rel else "."
    return parent.removeprefix("docs/") if parent.startswith("docs/") else parent


def link(rel: str) -> str:
    """Path relative to docs/README.md, which is where the block is spliced."""
    return rel.removeprefix("docs/") if rel.startswith("docs/") else f"../{rel}"


def render() -> str:
    grouped: dict[str, list[tuple[str, dict, str]]] = {}
    for rel, meta, summary in documents():
        grouped.setdefault(group(rel), []).append((rel, meta, summary))
    if not grouped:
        raise IndexError_("no documents found to index")

    lines: list[str] = []
    for name in sorted(grouped):
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| Document | Type | Summary |")
        lines.append("| --- | --- | --- |")
        for rel, meta, summary in grouped[name]:
            title = meta["title"]
            lines.append(
                f"| [{title}]({link(rel)}) | {meta.get('type', '?')} | {cell(summary)} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def splice(text: str, block: str) -> str:
    if text.count(START) != 1 or text.count(END) != 1:
        raise IndexError_(f"docs/README.md must contain exactly one {START} and one {END}")
    head, rest = text.split(START, 1)
    _old, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def extract(text: str) -> str:
    if text.count(START) != 1 or text.count(END) != 1:
        raise IndexError_(f"docs/README.md must contain exactly one {START} and one {END}")
    return text.split(START, 1)[1].split(END, 1)[0].strip("\n")


def write() -> int:
    text = DOCS_README.read_text(encoding="utf-8")
    updated = splice(text, render())
    if updated == text:
        print("docs index unchanged")
        return 0
    DOCS_README.write_text(updated, encoding="utf-8")
    print(f"docs index written — {len(documents())} documents")
    return 0


def check() -> int:
    text = DOCS_README.read_text(encoding="utf-8")
    try:
        found = extract(text)
    except IndexError_ as error:
        print(f"{error}", file=sys.stderr)
        return 1
    if found != render():
        print("docs/README.md index does not match the documents on disk.", file=sys.stderr)
        print("  Fix: python3 tools/docs_index.py", file=sys.stderr)
        return 1
    print(f"docs index ok — {len(documents())} documents")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docs_index.py",
        description="Render or verify the document index in docs/README.md.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verify the block against the documents instead of rewriting it (offline)",
    )
    args = parser.parse_args(argv)
    return check() if args.check else write()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IndexError_ as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(2)
