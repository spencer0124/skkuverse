---
title: Exported Scripts
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Exported scripts

> The public interface of this repository. Other repos clone it during CI and run these
> scripts by absolute path, so anything here is a contract. Everything else lives under
> [`../internal/`](../internal/) and carries no promise at all.

## Why this directory exists separately

Consumers fetch the repository with `git clone --depth 1` against `main` and invoke a
script directly:

```yaml
- run: git clone --depth 1 https://github.com/spencer0124/skkuverse "$RUNNER_TEMP/sv"
- run: python3 "$RUNNER_TEMP/sv/exported/sync_contracts.py" check --repo server --root .
```

There is no version to pin, no release, and no deprecation window. A path that changes
here breaks other repositories' default branches on the next push. Splitting the directory
makes that consequence visible before someone renames a file, rather than after.

## The interface

| Script | Used by | Purpose |
| --- | --- | --- |
| [`sync_contracts.py`](sync_contracts.py) | server, app, ai | Verify or adopt vendored configuration. Subcommands: `status`, `check`, `pull`, `explain`, `validate-manifest` |
| [`lint_conventions.py`](lint_conventions.py) | server | Check a repo's own files for language, frontmatter and folder structure. `--root`, `--only` |

The contract is the script paths, their subcommands, their flags, and their exit codes.
Both take `--root` so a consumer can point them at its own checkout.

## Anything reachable from here is also contract

[`generators/`](generators/) looks internal and is not. `sync_contracts.py` imports it to
build derived consumer files, so a change there reaches consumers exactly as a change to
the entry point does. The same applies to any module added later: if an exported script can
reach it, it is part of the interface, whatever it is named.

This borrows the rule
[canonical/data-platform-workflows](https://github.com/canonical/data-platform-workflows)
states for its reusable workflows, and it is the part people get wrong.

## Constraints

**Stdlib only.** Consumers run these with the system `python3` and install nothing. A
third-party import would mean adding an install step to every consuming repository.

**No filename may collide with a standard library module.** `sync_contracts.py` puts this
directory at the *front* of `sys.path` in order to import `generators/`, so a file called
`json.py` or `types.py` here would shadow the real module for every consumer, with a
traceback pointing nowhere near the cause. `tests/test_exported_surface.py` fails the build
if that ever happens.

**Blocking checks stay offline.** Everything these scripts compare in `check` mode lives
inside the consumer's own checkout, which is what makes a red build fixable in the branch
that caused it. See [CLAUDE.md](../CLAUDE.md#constraints-that-are-not-negotiable).

## Changing something here

Renaming a script, removing a subcommand, or changing a flag is a breaking change for
three repositories at once. The sequence that works:

1. Land the change here.
2. Update every consumer's workflow immediately afterwards.

Between those two steps, consumer builds fail at the clone-and-run step. Prepare and
approve the consumer pull requests first so the window stays in minutes rather than hours.

Adding a subcommand or an optional flag is backward compatible and needs none of this.

## Related

- [`../internal/README.md`](../internal/README.md) — the other half, and what it does not promise
- [`../contracts/README.md`](../contracts/README.md) — what `sync_contracts.py` operates on
- [`../conventions/README.md`](../conventions/README.md) — what `lint_conventions.py` enforces
