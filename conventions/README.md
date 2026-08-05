---
title: Shared Conventions
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Shared Conventions

> Rules that apply to every SKKUverse repository, defined once here and enforced in each repo's CI. Conventions that are files are distributed as contracts; conventions that are properties of a repo's own files are checked by a linter.

## The split

A convention is either **a file you can hand someone** or **a property their files must have**. Those need different mechanisms, and conflating them is why the previous attempt drifted.

| Kind | Example | Mechanism | Where it lives |
| --- | --- | --- | --- |
| A file | markdownlint rules, the doc template | **Contract** — vendored, hash-locked, CI-enforced | `conventions/`, declared in [`../contracts/manifest.json`](../contracts/manifest.json) |
| A property | "no Korean outside product copy", "every doc has frontmatter" | **Linter** — [`../tools/conventions_lint.py`](../tools/conventions_lint.py) | run in each repo's CI |
| A GitHub feature | `CONTRIBUTING.md`, issue templates | **Default community health files** | [`spencer0124/.github`](https://github.com/spencer0124/.github) |

No new machinery was built for the first row. A shared config file is *precisely* "one repo owns it, others vendor a copy" — which the contract system already does, with content hashes and an offline CI gate. Registering `markdownlint.jsonc` as a contract took nine lines of manifest.

## What is here

| File | Consumed by | How |
| --- | --- | --- |
| [`markdownlint.jsonc`](markdownlint.jsonc) | server, app | vendored as `.markdownlint.jsonc`, referenced via `extends` |

**Rules central, globs local.** This file carries only the rule set. Each repo keeps its own `.markdownlint-cli2.jsonc` naming which paths to lint and which to skip, because those are genuinely repo-specific — `docs/**` in one, `**/*.md` minus an Expo build tree in another. That split is not a compromise: the two pre-existing copies of this config were byte-identical *except* for `globs` and `ignores`, so it is where the real seam already was.

```jsonc
// .markdownlint-cli2.jsonc in a consumer repo
{
  "config": { "extends": ".markdownlint.jsonc" },
  "globs": ["docs/**/*.md"],
  "ignores": ["**/CHANGELOG.md"]
}
```

The doc template ([`../docs/_template.md`](../docs/_template.md)) is distributed the same way, but it lives under `docs/` rather than here because the umbrella uses it itself.

## What the linter checks

Run it against any repo, including from a sibling's CI:

```bash
python3 tools/conventions_lint.py --root .
python3 tools/conventions_lint.py --root . --only language
```

| Check | Rule |
| --- | --- |
| `language` | No Korean in `docs/`, `README.md` or `CLAUDE.md` outside declared product copy |
| `frontmatter` | Every document under `docs/` has all six required keys, valid enums, an ISO date |
| `structure` | `docs/` subdirectories are Diátaxis folders, not ad-hoc ones |

It reads only the repo it is pointed at, so it is **offline** and safe to block a merge on — per [CLAUDE.md](../CLAUDE.md), a red check the author cannot fix in the current branch is worse than no check.

## Declaring an exception

Exceptions live in the repo they apply to, never centrally. A single list of everyone's exceptions is a second place to forget to update, and it separates the exception from the reason for it.

**Repo-wide** — `.conventions.json` at the repo root:

```json
{
  "productCopy": ["packages/shared/src/i18n/**", "sources.json"],
  "frontmatterExempt": ["docs/archive/legacy-notes.md"],
  "extraDocFolders": ["runbooks"]
}
```

`productCopy` is for Korean that **is** the product — i18n bundles, store metadata, notice content, an LLM prompt that must be Korean to produce Korean output. Those are data, not documentation; the code and comments around them stay English.

**One line** — a marker on the line itself:

```markdown
you cannot grep 소유권 <!-- conventions:allow-korean: the example is the point -->
```

Line-level and visible exactly where it applies, which beats a whole-file exemption sitting in a config file. In Markdown the HTML comment renders as nothing.

## Adopting this in a repo

The tool comes from the umbrella clone the repo's CI already makes for `skkuverse_sync.py`, so adoption is about two lines of YAML and no new dependency:

```yaml
- name: Fetch contract tooling
  run: git clone --depth 1 https://github.com/spencer0124/skkuverse "$RUNNER_TEMP/sv"
- name: Conventions
  run: python3 "$RUNNER_TEMP/sv/tools/conventions_lint.py" --root .
```

`--only` exists for repos mid-migration: adopt `frontmatter` and `structure` first, add `language` when the translation lands, rather than leaving the whole check off.

## Related

- [CLAUDE.md](../CLAUDE.md) — the language policy in full
- [docs/README.md](../docs/README.md) — the writing rules and frontmatter schema
- [contracts/README.md](../contracts/README.md) — how the vendoring and hash locking work
