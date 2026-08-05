---
title: Shared Conventions
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Shared conventions

> Rules that apply to every SKKUverse repository, defined once here and enforced in each
> repo's CI. Conventions that are files travel as contracts. Conventions that are
> properties of a repo's own files are checked by a linter.

## The split

A convention is either a file you can hand someone or a property their files must have.
Those need different mechanisms, and conflating them is why the previous attempt drifted.

| Kind | Example | Mechanism | Where it lives |
| --- | --- | --- | --- |
| A file | markdownlint rules, the doc template, the Vale config | Contract: vendored, hash-locked, CI-enforced | `conventions/`, declared in [`../contracts/manifest.json`](../contracts/manifest.json) |
| A property | "no Korean outside product copy", "every doc has frontmatter" | Linter: [`../tools/conventions_lint.py`](../tools/conventions_lint.py) and [`../tools/prose_metrics.py`](../tools/prose_metrics.py) | run in each repo's CI |
| A GitHub feature | `CONTRIBUTING.md`, issue templates | Default community health files | [`spencer0124/.github`](https://github.com/spencer0124/.github) |

No new machinery was built for the first row. A shared config file is precisely "one repo
owns it, others vendor a copy", which the contract system already does with content hashes
and an offline CI gate. Registering `markdownlint.jsonc` as a contract took a manifest
entry and nothing else.

## What is here

| File | Purpose |
| --- | --- |
| [`markdownlint.jsonc`](markdownlint.jsonc) | Markdown structure and formatting rules |
| [`prose.md`](prose.md) | Writing style, and what the linters cannot judge |

Whether a contract is enforced yet is state, so it is not written down here. The generated
table on the [landing page](../README.md#how-changes-propagate) is the answer, and CI
verifies it.

**Rules central, globs local.** `markdownlint.jsonc` carries only the rule set. Each repo
keeps its own `.markdownlint-cli2.jsonc` naming which paths to lint and which to skip,
because those really are repo-specific: `docs/**` in one repo, everything except an Expo
build tree in another. That split is where the real seam already was, since the
pre-existing copies of this config were byte-identical apart from `globs` and `ignores`.

```jsonc
// .markdownlint-cli2.jsonc in a consumer repo
{
  "config": { "extends": ".markdownlint.jsonc" },
  "globs": ["docs/**/*.md"],
  "ignores": ["**/CHANGELOG.md"]
}
```

The doc template ([`../docs/_template.md`](../docs/_template.md)) travels the same way,
though it lives under `docs/` because the umbrella uses it itself.

## What the linters check

Run them against any repo, including from a sibling's CI:

```bash
python3 tools/conventions_lint.py --root .
python3 tools/conventions_lint.py --root . --only language
python3 tools/prose_metrics.py --root . --report
```

| Check | Tool | Rule |
| --- | --- | --- |
| `language` | `conventions_lint.py` | No Korean in `docs/`, `README.md` or `CLAUDE.md` outside declared product copy |
| `frontmatter` | `conventions_lint.py` | Every document under `docs/` has the required keys, valid enums, an ISO date |
| `structure` | `conventions_lint.py` | `docs/` subdirectories are Diátaxis folders rather than ad-hoc ones |
| `bold` | `prose_metrics.py` | Bold reserved for run-in headings, not mid-sentence emphasis |
| `burstiness` | `prose_metrics.py` | Sentence lengths vary rather than settling into one rhythm |

Both read only the repo they are pointed at, so both are offline and safe to block a merge
on. That is the governing rule stated in [CLAUDE.md](../CLAUDE.md#constraints-that-are-not-negotiable).

`conventions_lint.py` is the one siblings run. `prose_metrics.py` runs here only, because a
sibling should not go red over a style opinion formed in this repository.

## Declaring an exception

Exceptions live in the repo they apply to, never centrally. A single list of everyone's
exceptions is a second place to forget to update, and it separates the exception from the
reason for it.

Repo-wide, in `.conventions.json` at the repo root:

```json
{
  "productCopy": ["packages/shared/src/i18n/**", "sources.json"],
  "frontmatterExempt": ["docs/archive/legacy-notes.md"],
  "extraDocFolders": ["runbooks"]
}
```

`productCopy` is for Korean that is the product: i18n bundles, store metadata, notice
content, or an LLM prompt that must be Korean to produce Korean output. Those are data, and
the code and comments around them stay English.

A single line opts out with a marker carrying its reason:

```markdown
you cannot grep 소유권 <!-- conventions:allow-korean: the example is the point -->
```

Line-level and visible exactly where it applies, which beats a whole-file exemption sitting
in a distant config file. In Markdown the HTML comment renders as nothing.

## Adopting this in a repo

The tool comes from the umbrella clone the repo's CI already makes for
`skkuverse_sync.py`, so adoption costs two lines of YAML and no new dependency:

```yaml
- name: Fetch contract tooling
  run: git clone --depth 1 https://github.com/spencer0124/skkuverse "$RUNNER_TEMP/sv"
- name: Conventions
  run: python3 "$RUNNER_TEMP/sv/tools/conventions_lint.py" --root .
```

`--only` exists for repos mid-migration. Adopt `frontmatter` and `structure` first, then
add `language` once the translation lands, rather than leaving the whole check off.

## Related

- [CLAUDE.md](../CLAUDE.md) — the language policy and the governing rule for every check
- [prose.md](prose.md) — writing style, and the Vale configuration that enforces it
- [docs/README.md](../docs/README.md) — document structure and the frontmatter schema
- [contracts/README.md](../contracts/README.md) — how vendoring and hash locking work
