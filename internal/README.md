---
title: Internal Scripts
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Internal scripts

> Scripts that only this repository runs. Nothing outside it may depend on them, so they
> can be renamed or deleted freely. The opposite guarantee to
> [`../exported/`](../exported/).

## How they split

Split by whether a script modifies the repository, because that difference decides how it
is run and what can go wrong.

| Directory | What it does | Every script has |
| --- | --- | --- |
| [`render/`](render/) | Writes generated content into a marker block in a Markdown file | a `--check` mode that verifies instead of writing |
| [`check/`](check/) | Reads and reports. Never writes | an exit code, and nothing else |

Each path reads as a verb phrase: `internal/render/docs_index`, `internal/check/prose`.

## render/

Each of these owns one marker block and is the only thing allowed to write it. CI runs
every one with `--check`, so a hand-edited block or a stale regeneration fails the build.

| Script | Block | Source of truth |
| --- | --- | --- |
| [`fleet_table.py`](render/fleet_table.py) | `<!-- fleet:start -->` in `README.md` | submodule gitlinks in the git index |
| [`contracts_table.py`](render/contracts_table.py) | `<!-- contracts:start -->` in `README.md` | `contracts/manifest.json` |
| [`docs_index.py`](render/docs_index.py) | `<!-- index:start -->` in `docs/README.md` | each document's own frontmatter |

`fleet_table.py --check` verifies less than it writes, and says so in its docstring: the
date and subject columns come from submodule objects that CI does not check out. The other
two verify completely, because every input they read is a file in this repository.

## check/

[`prose.py`](check/prose.py) covers the two writing defects Vale cannot express: bold used
mid-sentence, and sentence-length spread. Both need either the raw markup or a statistic
that no published linter computes.

It stays here rather than in `../exported/` deliberately. `lint_conventions.py` checks
things the whole fleet agreed on, so it is safe to run in a sibling's CI. Prose style is an
opinion formed in this repository, and a sibling should not go red over one.

## Depth matters here

These sit two levels below the repository root, so each derives its root with
`Path(__file__).resolve().parents[2]`. Using `parent.parent` resolves to `internal/` and
every generated block is then read from the wrong file. The `--check` runs catch that
immediately, so they belong in the verification pass after any move.

## Related

- [`../exported/README.md`](../exported/README.md) — the public half, and what changing it costs
- [`../conventions/prose.md`](../conventions/prose.md) — the rules `check/prose.py` enforces
- [`../docs/README.md`](../docs/README.md) — the document index `render/docs_index.py` builds
