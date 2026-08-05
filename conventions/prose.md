---
title: Prose Conventions
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Prose conventions

> The writing rules are executable. [`../.vale.ini`](../.vale.ini) and
> [`../styles/skkuverse/`](../styles/skkuverse/) are the rules themselves, and CI runs
> them. This page covers only what a linter cannot decide.

## Running it

```bash
vale sync                                    # fetch the pinned style packages, once
vale --glob='!skkuverse*/**' .               # what ci.yml runs
vale docs/architecture/container-view.md     # one file
```

Vale is a single static Go binary with no runtime. It never enters `tools/`, which is what
lets `tools/` stay stdlib-only Python while the fleet still gets a prose gate. The glob
excludes the submodule directories, since those record other repositories and each one
lints its own writing.

## What is enforced

[`tbhb/vale-ai-tells`](https://github.com/tbhb/vale-ai-tells) supplies most of it, pinned
by release URL in `.vale.ini`. It covers contrastive formulas, mic-drop closers,
metacommentary, verb tricolons, rhetorical self-answers, and an overused-vocabulary list.

These rules are ours, because nothing published covers them:

| Rule | Why it exists |
| --- | --- |
| [`EmDashDensity`](../styles/skkuverse/EmDashDensity.yml) | The upstream rule flags every em dash, and the Google and Microsoft packages check only whether the dash is spaced. Density is the actual signal. |
| [`BoldEmphasis`](../styles/skkuverse/BoldEmphasis.yml) | Google states the rule in prose and provides no check. Bold belongs on run-in headings, and emphasis belongs in the words. |

## What no linter can decide

These matter as much as the enforced list, because a rule written as though it were
enforced when it is not is how a convention rots.

**A closing aphorism.** A regex list catches templates it has already seen, and a good
aphorism is by definition not a template. Ending a section on a memorable line reads as
punctuation rather than argument. Watch for it in review.

**Sentence-length uniformity.** Human writing varies its sentence length far more than
generated writing does. The statistic is the spread, not the mean, and readability metrics
compute means. Nothing in the ecosystem measures it, so this stays a human judgement.

**Counts written into prose.** `three things live here` is both a formulaic opener and a
value that goes stale silently. `ai-tells.CataphoricForecasting` catches the common shapes,
but the rule is broader than the check: never write a number that another file already
knows. Generate it, or point at the source.

## Not everything flagged is wrong

The evidence behind these rules is honest about its limits. Perfect grammar, formal
register, and transition words do not indicate generated text, and
[Wikipedia's catalogue](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) says
so explicitly. Individual signals are weak. The goal is removing formulaic habits, not
flattening the writing into something with no voice.

A falsifiable technical claim is worth keeping even when it sits inside a sentence the
linter dislikes. Cut the framing around the claim rather than the claim.

## Declaring an exception

Vale reads HTML comments, so exceptions live on the line they apply to:

```markdown
<!-- vale skkuverse.BoldEmphasis = NO -->
The rendered output shows **Save** in bold, matching the button.
```

Whole regions can opt out with `<!-- vale off -->` and `<!-- vale on -->`, though a region
that needs it is usually quoted material that belongs in a code fence.

Repo-wide exceptions belong in that repo's own `.vale.ini`, never here, for the reason
given in [README.md](README.md#declaring-an-exception): a central list of everyone's
exceptions separates each one from its reason.

## Adopting this in a repo

The rules travel by the umbrella clone the repo's CI already makes for
`skkuverse_sync.py`, so there is nothing to vendor and nothing to install:

```yaml
- name: Fetch tooling
  run: git clone --depth 1 https://github.com/spencer0124/skkuverse "$RUNNER_TEMP/sv"
- name: Install Vale
  run: |
    curl -sfL "https://github.com/vale-cli/vale/releases/download/v3.17.0/vale_3.17.0_Linux_64-bit.tar.gz" \
      | sudo tar -xz -C /usr/local/bin vale
- name: Prose
  run: |
    vale sync --config="$RUNNER_TEMP/sv/.vale.ini"
    vale --config="$RUNNER_TEMP/sv/.vale.ini" --glob='!node_modules/**' docs/
```

**Deliberately not a contract.** The markdownlint rules are vendored and hash-locked
because a repo's own `markdownlint-cli2` reads them from disk, so the copy has to be there
and has to be verifiably identical. Vale takes `--config` as a path, so a consumer reads
this repository's copy directly. A file fetched fresh at CI time cannot drift, which makes
a hash lock redundant rather than safer.

The same split still applies. Rules are central, in the config above. Which paths to lint
is local, and each repo passes that as `--glob` and a path argument.

## Related

- [README.md](README.md) — how shared conventions are split between contracts and linters
- [docs/README.md](../docs/README.md) — document structure, frontmatter, and the docs index
- [CLAUDE.md](../CLAUDE.md) — the language policy and the working constraints
