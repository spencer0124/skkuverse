---
title: Daily Fleet Pin as Git Submodules
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# ADR 0003 — Daily fleet pin as git submodules

> Every repo's `main` is pinned as a submodule at the repository root once a day and committed, making this repository's history a day-by-day record of what the whole system was.

## Status

accepted (2026-08-05)

## Context

Six repos ship independently. Nothing recorded the fleet's combined state, so a question as basic as *"what was the whole system on 2026-08-05?"* had no answer — not in a lock file, not in a deploy log, not here.

The tempting assumption is that git already knows and we just have to ask. It does not. Committer dates describe when a commit was *made*, not when a branch *pointed at it*:

```
$ git rev-list -1 --before=2026-08-01 origin/main        # in skkuverse-server
  84ba4ce  Merge feat/webview-ssot-miniapps into dev     ← never was main's tip
$ git rev-list -1 --before=2026-08-01 --first-parent origin/main
  18bc812  Merge pull request #80 ...                    ← the actual answer
```

`--before` walks *all reachable commits*, so it returns work that sat on `dev` for days before merging. `--first-parent` is closer but still infers from merge-commit dates and breaks under rebase or force-push. The only structure that records a branch's historical tip is a reflog, which is local, unpushed, and expires.

So the state has to be recorded as it happens or it is lost. A secondary need pointed the same way: the landing page had no live view of the fleet, and this repository had no machine-readable statement of which repos *are* SKKUverse — `contracts/manifest.json` lists four, but only because those four exchange config.

## Decision

**A scheduled workflow pins every repo's `main` as a git submodule at the repository root once a day and commits, and a generated table renders those pins onto the landing page.**

| Element | Choice |
| --- | --- |
| Mechanism | Git submodules — a gitlink **is** the SHA, so `git ls-tree <commit>` is machine-readable with no parsing |
| Layout | Repository root — each submodule sits at `<repo-name>/`, so the fleet is the first thing the front page shows |
| Scope | All six repos — `.gitmodules` becomes the declaration of fleet membership, deliberately a superset of the contract manifest's four |
| Branch | `branch = main` set explicitly on every entry |
| Schedule | `40 14 * * *` — 23:40 KST, once daily |
| Cadence | One commit per calendar date, `--allow-empty` |

Three details carry more weight than they look:

**`branch = main` is explicit, not decorative.** `man gitmodules`: when unset it defaults to *the submodule's remote HEAD*. Every repo here also has a live `dev`, and most local checkouts sit on it. If a default branch were ever flipped, an unset key would silently start pinning `dev` and nothing would report it.

**14:40 UTC is chosen, not arbitrary.** Every UTC time before 15:00 shares its calendar date with KST (UTC+9), so a run's UTC date and its KST date are the same day. That is what lets `--before=<date>` mean one thing to every reader. Moving the schedule past 14:xx breaks it.

**Empty commits are the liveness record**, and they cost nothing structurally: an empty commit touches no paths, so `git log` is the daily heartbeat while `git log -- 'skkuverse*'` still filters to exactly the days something moved. Two timelines out of one history.

The generated README block must remain a **pure function of the pinned SHAs** — no "age", no "N days ago", no generated-at stamp. Any time-relative column would rewrite the block daily even when nothing moved, making the CI check non-deterministic and erasing the difference between a quiet day and a busy one.

## Consequences

- ✅ The question that prompted this now has an exact answer, and any commit expands back into the real code of all six repos via `git submodule update --init`.
- ✅ Immune to upstream force-pushes. `--remote` never reads the recorded SHA, so a rewritten sibling history cannot break the daily run.
- ✅ No credential is introduced. All six repos are public, so the pin needs no token, and the only credential in play is this repo's own `GITHUB_TOKEN` pushing to this repo. ADR 0002's no-cross-repo-PAT property is preserved.
- ✅ Zero blast radius on consumers. `skkuverse-server`, `-app` and `-ai` fetch `tools/` with `git clone --depth 1`, which never initialises submodules, and no workflow in the fleet uses `--recurse-submodules`.
- ⚠️ **All six repos must stay public.** The day one goes private, the workflow either breaks or you introduce exactly the cross-repo PAT ADR 0002 exists to avoid. The recommended response is to drop that repo from the snapshot, not to add the token.
- ⚠️ **A missed run is unrecoverable.** If GitHub drops a scheduled run, that day's state cannot be reconstructed later — that is the whole premise. Daily commits at least make the gap *visible* as a missing date.
- ⚠️ **A renamed sibling fails silently.** GitHub's redirects keep git working while the `url` in `.gitmodules` quietly becomes wrong. This is the only silent failure in the design.
- ⚠️ Branch protection on this repo's `main` would break the bot push. There is none today. If it is ever added, `github-actions[bot]` needs a bypass — switching to a pull-request flow would be a real downgrade, since a snapshot that needs a merge click is not a snapshot.
- ⚠️ The submodule directories are a record, not a workspace. Never develop in them; your own checkouts outside this repo are the workspace.

## Alternatives considered

**`git subtree`.** Rejected. It would import ~45 MB of history into this repo immediately and re-merge upstream forever, which defeats one-clean-commit-per-day. It also records the source SHA only as a `git-subtree-split:` trailer, so answering the question would mean grepping commit messages instead of reading a gitlink. And it would slow every consumer's `git clone --depth 1` of this repo.

**An append-only ledger** (`fleet-history.jsonl`, one line a day from `git ls-remote`). Cheapest option and no submodules anywhere, but it records SHAs and then hopes the repos still have them. Gitlinks let you check out a past day and hold the actual code.

**Pinning only the manifest's four repos.** Rejected: the manifest's scope is *which repos exchange config*, not *which repos are SKKUverse*. Omitting `skkuverse.com` and `skkuverse-codepush` would make the snapshot quietly narrower than the system it claims to record.

**Change-only commits.** They answer the question just as exactly — the last snapshot at or before a date *is* that date's state, because nothing moved in between. Rejected in favour of a daily heartbeat, which additionally proves the job ran and keeps the workflow out of GitHub's 60-day inactivity auto-disable.

**Top-level submodule directories.** Rejected: six pointer directories would push `tools/` — which gates three other repos' CI — below the fold on the repository's front page.

## Related

- [Container View §The fourth seam](../architecture/container-view.md#the-fourth-seam-a-daily-pin-of-the-whole-fleet)
- [ADR 0002 — Pull-based config contracts](0002-pull-based-config-contracts.md) — the no-cross-repo-PAT property this preserves
- `.github/workflows/fleet-snapshot.yml`, `tools/fleet_snapshot.py`
