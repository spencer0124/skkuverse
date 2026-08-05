#!/usr/bin/env python3
"""Structural prose checks that Vale cannot express.

Vale owns the vocabulary and phrasing rules. Two defects sit outside what it can
see, and both are the kind that survive a careful read:

  bold          Bold used mid-sentence for emphasis. Google's style guide states
                the rule - bold is for UI elements and run-in headings, and
                emphasis belongs in the words - but ships no check, and neither
                does any published Vale package. Detecting it needs the markup,
                and Vale strips markup before a rule sees the text. Its escape
                hatch, `scope: raw`, hands the rule the whole file including
                fenced code and frontmatter, so a code sample demonstrating bold
                reports as bold overuse. Measured, not theorised: BlockIgnores
                does not apply to raw scope.

  burstiness    Variation in sentence length. Human writing swings between short
                and long far more than generated writing does. The statistic is
                the spread, and every readability metric in Vale's Readability
                package computes a mean, which is by construction blind to it.

This runs only in this repository's CI. exported/lint_conventions.py is a blocking
gate inside three sibling repos, and a sibling should not go red over a style
opinion formed here.

    prose.py --root .
    prose.py --root . --only bold
    prose.py --root . --report        # print the numbers, exit 0

Stdlib only, same as everything under `internal/`.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path

# Bold that has running text before it on the same line. A run-in heading has
# no prose ahead of it and is allowed, which is exactly the distinction Google
# draws.
BOLD_MID_SENTENCE = re.compile(r"\w[^\n*]*?\s\*\*[^*\n]+\*\*")

# Stripped before the test, so an ordered run-in heading (`1. **Label.** text`)
# is treated like an unordered one. Without this the list number itself counts
# as the preceding word and every numbered list reads as bold overuse.
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)]|>)\s+")

FENCE_LINE = re.compile(r"^ *(```|~~~)")
HEADING_LINE = re.compile(r"^ *#{1,6} ")
TABLE_LINE = re.compile(r"^\s*\|")          # cells are labels, not sentences
INLINE_CODE = re.compile(r"`[^`\n]+`")
LINK_TARGET = re.compile(r"\]\([^)\s]+\)")
HTML_COMMENT = re.compile(r"<!--.*?-->")

SENTENCE_END = re.compile(r"[.!?](?:\s|$)")

# A floor, not a target, and it does not fire on this repository today. When it
# was set, every document here scored between roughly 7 and 12 words of spread,
# so 5.0 leaves real headroom while still catching a collapse into uniform
# sentence length. Saying that plainly matters: a threshold nothing currently
# violates is a regression guard, and pretending otherwise would overstate what
# this check found. Re-measure with `--report` before changing it.
MIN_SENTENCES = 8          # below this a spread figure means nothing
MIN_STDEV = 5.0            # words

SKIP_DIRS = ("styles/", "node_modules/", ".git/", "__pycache__/")


class ProseError(Exception):
    """A malformed input, as distinct from a finding. Findings are reported and
    counted; this aborts."""


def prose_lines(text: str) -> list[tuple[int, str]]:
    """(1-based line number, cleaned line) for lines the author wrote as prose.

    A single forward pass, carrying the block state as it goes. An earlier
    version stripped the whole document with regexes and then matched the
    result back to the original to recover line numbers, which silently
    discarded every line an inline substitution had rewritten - nearly all of
    them. Deciding line by line keeps the numbering correct by construction.
    """
    out: list[tuple[int, str]] = []
    lines = text.split("\n")
    in_frontmatter = lines and lines[0].strip() == "---"
    fence: str | None = None

    for number, raw in enumerate(lines, start=1):
        if in_frontmatter:
            # The opening delimiter is line 1, so only a later one closes it.
            if number > 1 and raw.strip() == "---":
                in_frontmatter = False
            continue

        opener = FENCE_LINE.match(raw)
        if fence is not None:
            if opener and opener.group(1).startswith(fence):
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue

        if HEADING_LINE.match(raw) or TABLE_LINE.match(raw):
            continue

        line = HTML_COMMENT.sub("", raw)
        line = LINK_TARGET.sub("]", line)     # a URL is not words
        line = INLINE_CODE.sub("CODE", line)
        if line.strip():
            out.append((number, line))
    return out


def check_bold(path: Path, text: str) -> list[str]:
    findings = []
    for number, line in prose_lines(text):
        # A marker can repeat for a nested list, so strip until none is left.
        while LIST_MARKER.match(line):
            line = LIST_MARKER.sub("", line, count=1)
        if BOLD_MID_SENTENCE.search(line):
            findings.append(
                f"{path}:{number}: bold used for emphasis mid-sentence. "
                f"Reserve bold for run-in headings."
            )
    return findings


def sentence_lengths(text: str) -> list[int]:
    body = " ".join(line for _, line in prose_lines(text))
    # Naive splitting on terminal punctuation. It miscounts abbreviations and
    # version numbers, which is acceptable because the output is a spread over
    # many sentences rather than a judgement about any one of them.
    lengths = []
    for part in SENTENCE_END.split(body):
        words = part.split()
        if words:
            lengths.append(len(words))
    return lengths


def check_burstiness(path: Path, text: str) -> list[str]:
    lengths = sentence_lengths(text)
    if len(lengths) < MIN_SENTENCES:
        return []
    spread = statistics.pstdev(lengths)
    if spread < MIN_STDEV:
        return [
            f"{path}: sentence lengths vary too little "
            f"(spread {spread:.1f} words, floor {MIN_STDEV}). "
            f"Vary the rhythm: some sentences short, some long."
        ]
    return []


CHECKS = {"bold": check_bold, "burstiness": check_burstiness}


def targets(root: Path) -> list[Path]:
    found = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(d) for d in SKIP_DIRS):
            continue
        # The submodule directories record other repositories. Each lints its
        # own writing; a finding here would not be fixable in this branch.
        if rel.split("/")[0].startswith("skkuverse"):
            continue
        found.append(path)
    return found


def run(root: Path, only: list[str], report: bool) -> int:
    if not root.is_dir():
        raise ProseError(f"{root} is not a directory")
    selected = only or list(CHECKS)
    unknown = [name for name in selected if name not in CHECKS]
    if unknown:
        raise ProseError(f"unknown check(s): {', '.join(unknown)}")

    findings: list[str] = []
    rows: list[tuple[str, int, float]] = []
    for path in targets(root):
        text = path.read_text(encoding="utf-8")
        for name in selected:
            findings.extend(CHECKS[name](path.relative_to(root), text))
        if report:
            lengths = sentence_lengths(text)
            spread = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
            rows.append((path.relative_to(root).as_posix(), len(lengths), spread))

    if report:
        print(f"{'file':<52} {'sentences':>9} {'spread':>7}")
        for name, count, spread in sorted(rows, key=lambda r: r[2]):
            print(f"{name:<52} {count:>9} {spread:>7.1f}")
        return 0

    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} prose finding(s)", file=sys.stderr)
        return 1
    print("prose metrics ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prose.py",
        description="Structural prose checks that Vale cannot express.",
    )
    parser.add_argument("--root", default=".", help="repository root to check")
    parser.add_argument(
        "--only", action="append", choices=sorted(CHECKS), default=[],
        help="run one check (repeatable)",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="print the measured numbers and exit 0, instead of failing",
    )
    args = parser.parse_args(argv)
    return run(Path(args.root).resolve(), args.only, args.report)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProseError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(2)
