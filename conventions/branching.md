---
title: Branching
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-07
audience: public
---

# Branching

> Commit to `dev`, and reach `main` by pull request. A separate branch is the exception, and
> this page names the cases that earn one.

## The default

Every repository in the fleet has a live `dev`, and most local checkouts sit on it. Commit
there.

| Branch | Role |
| --- | --- |
| `dev` | where work happens, and the branch a local checkout should be on |
| `main` | merge-only, updated by a pull request from `dev` |
| `feat/<topic>` | the exception, cut from `dev` and merged back into it |

`main` is never committed to. In `skkuverse-app` a `PreToolUse` hook blocks edits while it is
checked out, because the constraint is easier to enforce than to remember.

## When a separate branch earns its cost

Cut `feat/<topic>` from `dev` when any of these holds:

- The change is large enough that a reviewable diff, arriving before the code reaches `dev`, is
  worth a round trip.
- Someone asked for one.
- The work has to stay separable. Native changes in `skkuverse-app` are the standing example:
  mixing them into `dev` bumps `runtimeVersion` past the binary already in the stores, and
  every later over-the-air update from `dev` silently reaches nobody.

Otherwise commit to `dev`.

## Why the default is not a branch

One maintainer writes and reviews everything here. Cutting a branch per change buys isolation
nobody uses, at the cost of a push, a pull request, a wait for checks, and a merge. That
ceremony is worth paying where it protects something, which is what the list above describes.

The reverse failure is quieter and more expensive. Ceremony applied uniformly gets skipped
under time pressure, and it gets skipped first on the change that most needed the review.

## Before starting

Check where you are and what moved while you were away. A change written against a stale
checkout is discovered at merge time, and by then it has a history someone has to unpick.

```bash
git fetch --prune origin
git status -sb                 # current branch, and how far it has drifted
git log --oneline @{u}..HEAD   # unpushed work sitting here
```

`--prune` is the part people skip. Without it, remote-tracking refs for branches deleted
months ago stay in the listing and every later cleanup decision is made against a fiction.

## Cleaning up

Delete a `feat/` branch once it is merged, locally and on the remote. Merging with
`gh pr merge --delete-branch` removes the remote side, and `git fetch --prune` clears the
tracking ref, but the local branch survives both and accumulates.

```bash
git branch --merged main | grep -vE '^\*|main|dev'   # candidates
git branch -d <branch>                               # -d refuses if unmerged
```

Use `-d` rather than `-D`. The lowercase form refuses to delete anything not yet merged,
which is the check rather than an obstacle to it.

Housekeeping of this kind does not need to be proposed first. Pruning refs, deleting merged
branches, and syncing a stale local `main` are reversible from the remote and cost nothing to
redo. Anything that discards unmerged work is a different question and gets asked.

## Consequences

Continuous integration runs on pull requests into `main`, so work on `dev` reaches a gate when
it is proposed for `main` rather than when it is written. Run the repository's checks locally
before pushing to `dev`. `skkuverse-app` also has a `Stop` hook that runs lint and tests on any
turn that touched a file, which covers the same ground from the other side.

Rewriting `dev` after a push means force-pushing a shared branch, so corrections that need
history rewritten belong to the window before the first push. See
[cross-repo-references.md](cross-repo-references.md) for the reword recipe and its verification
step.

## Related

- [README.md](README.md) — how shared conventions are defined and enforced
- [cross-repo-references.md](cross-repo-references.md) — linking commits and issues across repositories
- [ADR 0003](../docs/decisions/0003-daily-fleet-pin-as-submodules.md) — why the fleet pin follows `main` rather than each repo's remote HEAD
