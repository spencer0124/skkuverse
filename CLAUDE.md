# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Language policy: English everywhere

Everything written in or about this ecosystem is in English. No exceptions, no
mixed-language files.

This applies to every artifact, not only the ones that reach GitHub:

| Surface | Rule |
| --- | --- |
| Code comments and docstrings | English |
| Commit messages | English |
| PR titles, bodies, and review comments | English |
| Issue titles and bodies | English |
| README and all `docs/` content | English |
| ADRs | English |
| CLI output, log messages, error strings | English |
| JSON `note` and `description` fields in config | English |
| Branch names | English |

Korean product copy is the one carve-out, and only where it is the product: user-facing
strings the app displays, such as `label.ko`, i18n bundles, and notice content. Those are
data. The code and comments around them stay English.

Why: these repos are public and serve as a portfolio. A reader landing on
`container-view.md` or a PR diff should not need Korean to follow the reasoning.
Mixed-language files also make search unreliable, because you cannot grep "ownership" in
a file that says "소유권". <!-- conventions:allow-korean: the example is the point -->

This is enforced rather than merely stated. `exported/lint_conventions.py` fails on Korean
outside declared product copy. A single line may opt out with a `conventions:allow-korean`
marker plus a reason, which keeps the exception visible where it applies. Repo-wide
product-copy paths belong in that repo's `.conventions.json`.

When editing a file that still contains Korean, translate the parts you touch rather than
matching the surrounding language.

## What this repository is

The umbrella repo for the SKKUverse ecosystem. Separate concerns live here:

- **`exported/` and `internal/` are the two halves of the tooling, and the split is the
  most important thing to know about this repo.** Other repositories clone `exported/`
  during their own CI and run it by absolute path, so a rename there breaks their default
  branches. Nothing outside this repo may depend on `internal/`. Each directory has a
  README stating exactly what it does and does not promise.
- `docs/` holds cross-repo knowledge only: system boundaries, data flows that cross repo
  lines, ownership maps, and ADRs whose consequences span repos. Repo-local knowledge
  belongs in that repo's own `docs/`.
- `contracts/` and `exported/sync_contracts.py` form an executable contract registry. It runs
  as a blocking CI gate inside other repositories, so this repo is not docs-only and a
  change here can turn several pipelines red at once.
- `conventions/` defines rules that apply to every repository. Conventions that are files
  travel as contracts. Conventions that are properties of a repo's own files are checked by
  `exported/lint_conventions.py` and `internal/check/prose.py`.
- `.gitmodules` and the `skkuverse-*/` directories are a daily pin of every repo's `main`,
  written by `.github/workflows/fleet-snapshot.yml`. Never develop in them, and do not run
  `git submodule update --init` unless you are deliberately opening a past day. See
  [ADR 0003](docs/decisions/0003-daily-fleet-pin-as-submodules.md).

## Commands

```bash
python3 exported/sync_contracts.py status              # every contract at a glance (offline)
python3 exported/sync_contracts.py status --remote     # same, against origin/main
python3 exported/sync_contracts.py check --fleet       # freshness across every repo
python3 exported/sync_contracts.py pull --all          # adopt upstream, rewrite locks
python3 exported/sync_contracts.py explain <id>        # full chain for one contract
python3 exported/sync_contracts.py validate-manifest   # schema and self-consistency

python3 internal/render/fleet_table.py                     # rewrite the README fleet table
python3 internal/render/fleet_table.py --check             # verify it, offline (what CI runs)
python3 internal/render/contracts_table.py                    # rewrite the README contract table
python3 internal/render/contracts_table.py --check            # verify it, offline (what CI runs)

python3 exported/lint_conventions.py --root .          # language, frontmatter, docs structure
python3 exported/lint_conventions.py --root ../skkuverse-ai   # ...or any sibling
python3 internal/check/prose.py --root .             # bold overuse, sentence-length spread
python3 internal/check/prose.py --root . --report    # the numbers, without failing

vale sync && vale --glob='!skkuverse*/**' .         # the prose rules

python3 -m unittest discover -s tests -v      # the tools' own tests
```

## Constraints that are not negotiable

**A red check the author cannot fix in the current branch is worse than no check.** This
is the governing rule for every gate in the ecosystem, and the rest of the documentation
cites it rather than restating it. A check that fails for a reason outside the author's
branch teaches people to merge anyway, and then every check becomes decorative. Any
blocking check must therefore compare files inside a single repository, with no network.
Network-dependent checks are advisory and run on a schedule. If a blocking check is ever
observed failing for an outside reason, that is a design bug, and the fix is to move it to
a cron.

`exported/` is stdlib-only Python 3, with no dependencies ever. Sibling repos clone this
directory into CI and run it with the system `python3`. Adding a dependency would mean
adding an install step to each of them, and `skkuverse-server` pins every dependency
exactly and runs `knip` and `depcheck` on top. If you reach for a library, restructure
instead. `internal/` holds to the same rule so a contributor never has to install
anything, though only `exported/` is bound by it. Vale is the deliberate exception, and it
stays outside both directories for this reason.

Never hardcode a value that lives somewhere else. No version numbers, no counts, no schema
fields, no per-repo adoption state. Link to the owning source, or generate the text from
it. A number copied into prose starts lying the moment its source changes, and nothing
reports it. Both README tables are generated for this reason. See `docs/README.md` §3.

The manifest holds pointers, not content. No hashes and no values belong in
`contracts/manifest.json`, because those live in each consumer's `.contracts.lock.json`
and are written by tooling. The manifest changes only when the set of contracts changes.

The generated blocks in `README.md` are never hand-edited. `ci.yml` fails on any edit
between `<!-- fleet:start -->` and `<!-- fleet:end -->`, or between
`<!-- contracts:start -->` and `<!-- contracts:end -->`. Never add a time-relative column
to either: no age, no "N days ago", no generated-at stamp. Each block must be a pure
function of its inputs, or the daily cron rewrites it even when nothing moved, `--check`
becomes non-deterministic, and a quiet day stops being distinguishable from a busy one.

Test the tools before changing them. `.github/workflows/ci.yml` runs the unit tests,
`validate-manifest`, and both table checks on every PR. That job is the only thing limiting
the damage an unpinned tool can do to the repos consuming it.

## Documentation conventions

Follow [`docs/README.md`](docs/README.md) for structure, frontmatter, diagrams, and the
point-don't-copy rule. New documents start from [`docs/_template.md`](docs/_template.md).
Prose style is covered by [`conventions/prose.md`](conventions/prose.md) and enforced by
[`.vale.ini`](.vale.ini).

Frontmatter is mandatory on every Markdown document, including files outside `docs/` such
as `contracts/README.md`. The two repo-root entry points, `README.md` and this file, are
exempt.

## Related

- [`contracts/README.md`](contracts/README.md) — how the contract system works day to day
- [`conventions/README.md`](conventions/README.md) — how shared rules reach the siblings
- [`docs/decisions/`](docs/decisions/) — cross-repo ADRs
