# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Language policy — English everywhere

**Everything written in or about this ecosystem is in English.** No exceptions, no mixed-language files.

This applies to every artifact, not just the ones that reach GitHub:

| Surface | Rule |
| --- | --- |
| Code comments and docstrings | English |
| Commit messages | English |
| PR titles, bodies, and review comments | English |
| Issue titles and bodies | English |
| README and all `docs/` content | English |
| ADRs | English |
| CLI output, log messages, error strings | English |
| JSON `note` / `description` fields in config | English |
| Branch names | English |

Korean product copy is the one carve-out, and only where it *is* the product: user-facing strings shipped to the app (`label.ko`, i18n bundles, notice content). Those are data, not documentation. Their surrounding code and comments stay English.

**Why:** these repos are public and serve as a portfolio. A reader landing on `container-view.md` or a PR diff should not need Korean to follow the reasoning. Mixed-language docs also make search and grep unreliable — you cannot find "ownership" in a file that says "소유권".

When editing an existing file that still contains Korean, translate the parts you touch rather than matching the surrounding language.

## What this repository is

The umbrella repo for the SKKUverse ecosystem. Three distinct things live here:

1. **`docs/`** — cross-repo knowledge only: system boundaries, data flows crossing repo lines, ownership maps, and ADRs whose consequences span repos. Repo-local knowledge belongs in that repo's own `docs/`.
2. **`contracts/` + `tools/skkuverse_sync.py`** — an executable contract registry. It runs as a **blocking CI gate in three other repositories** (server, app, ai — the crawler is the producer and has nothing to verify), which is why this repo is not docs-only and why changes here have blast radius.
3. **`.gitmodules` + `repos/`** — a daily pin of every repo's `main`, written by `.github/workflows/fleet-snapshot.yml`. It is **a record, not a workspace**: never develop in it, and do not `git submodule update --init` unless you are deliberately expanding a past day. It is also where fleet membership is declared — six repos, deliberately a superset of the contract manifest's four, because those answer different questions.

## Commands

```bash
python3 tools/skkuverse_sync.py status              # every contract at a glance (offline)
python3 tools/skkuverse_sync.py status --remote     # same, against origin/main
python3 tools/skkuverse_sync.py check --fleet       # freshness across every repo
python3 tools/skkuverse_sync.py pull --all          # adopt upstream, rewrite locks
python3 tools/skkuverse_sync.py explain <id>        # full chain for one contract
python3 tools/skkuverse_sync.py validate-manifest   # schema + self-consistency

python3 tools/fleet_snapshot.py                     # rewrite the README fleet table
python3 tools/fleet_snapshot.py --check             # verify it, offline (what CI runs)

python3 -m unittest discover -s tools/tests -v      # the tools' own tests
```

## Constraints that are not negotiable

**`tools/` is stdlib-only Python 3.** No dependencies, ever. Four repos clone this tool into CI and run it with the system `python3`; adding a dependency would mean adding an install step to each of them, and `skkuverse-server` pins every dependency exactly and runs `knip` + `depcheck` on top. If you reach for a library, restructure instead.

**Never hardcode a value that lives in another repo.** No version numbers, counts, or schema fields. Link to the owning repo's source instead. A number copied here starts lying the moment that repo changes, and nothing will tell you. See `docs/README.md` §3.

**The manifest holds pointers, not content.** No hashes, no values in `contracts/manifest.json` — those live in each consumer's `.contracts.lock.json`, written by tooling. The manifest changes only when the *set* of contracts changes.

**Blocking checks must be offline.** Any check that can fail a merge or a deploy compares files within a single repo. Network-dependent checks are advisory and run on a schedule. The governing rule: *a red check the author cannot fix in the current branch is worse than no check* — it teaches people to merge anyway.

**The fleet table in `README.md` is generated.** Never hand-edit between `<!-- fleet:start -->` and `<!-- fleet:end -->`; `ci.yml` fails on it. And **never add a time-relative column** — no "age", no "N days ago", no generated-at stamp. The block must be a pure function of the pinned SHAs, or the daily cron rewrites it every day even when nothing moved, `--check` becomes non-deterministic, and a quiet day stops being distinguishable from a busy one.

**Test the tools before changing them.** `.github/workflows/ci.yml` runs the unit tests, `validate-manifest`, and `fleet_snapshot.py --check` on every PR. That job is the only thing bounding the blast radius of an unpinned tool consumed by three other repos.

## Documentation conventions

Follow [`docs/README.md`](docs/README.md): Diátaxis folder structure, required frontmatter, Mermaid-first diagrams, and the point-don't-copy rule. New documents start from [`docs/_template.md`](docs/_template.md).

Frontmatter is mandatory on every Markdown document in this repo, including files outside `docs/` such as `contracts/README.md`.

## Related

- [`contracts/README.md`](contracts/README.md) — how the contract system works and how to operate it
- [`docs/decisions/`](docs/decisions/) — cross-repo ADRs
