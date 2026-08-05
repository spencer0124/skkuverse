---
title: Expand a Past Snapshot
type: how-to
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-05
audience: public
---

# Expand a past snapshot

> Recover the state of every SKKUverse repository on a chosen date, and check out the
> code as it was. Why the snapshot exists at all is
> [ADR 0003](../decisions/0003-daily-fleet-pin-as-submodules.md).

## Before you start

Run this in a checkout of the umbrella repository. The submodule directories are empty
until you ask for them, and they stay a read-only record even once filled. Do the work in
your own checkouts elsewhere.

## Find that day's commit

```bash
git rev-list -1 --before=2026-08-06 main
```

`--before` takes any date git understands. The snapshot runs at 23:40 KST, and every UTC
time before 15:00 shares its calendar date with KST, so a date alone resolves without
ambiguity.

`--first-parent` is unnecessary here. This repository's `main` has no merge commits from
the snapshot cron, so the newest commit at or before a date is that date's state.

## Read the pins

```bash
git ls-tree <commit> | grep ^160000
```

Mode `160000` marks a gitlink. Each line gives one repository and the exact commit its
`main` pointed at, with no parsing beyond the column split.

To read a single repository instead:

```bash
git ls-tree <commit> skkuverse-server
```

## Check out the code

```bash
git checkout <commit>
git submodule update --init
```

This fetches each repository at its pinned commit. Expect several hundred megabytes across
the fleet, so limit it to what you need:

```bash
git submodule update --init -- skkuverse-server skkuverse-crawler
```

Return to the present with `git checkout main` followed by `git submodule deinit --all`.

## Find the days something moved

```bash
git log --oneline -- 'skkuverse*' 'repos/*'
```

The cron commits every day, including days when no repository moved, because the empty
commits are what prove the job ran. Filtering by path drops those and leaves only the days
a pin actually changed.

Both globs are needed. The submodules moved to the repository root in
`da61748 refactor(fleet): promote the submodules to the repository root`, and history
before that commit still records them under `repos/`. Dropping the second glob silently
hides every pre-move change.

## When a repository is missing

A repository that joined the fleet later has no gitlink in an earlier commit, and one that
left has none in a later commit. Both are correct. `.gitmodules` at that commit is the
membership record for that date:

```bash
git show <commit>:.gitmodules
```

## Related

- [ADR 0003 — Daily fleet pin as git submodules](../decisions/0003-daily-fleet-pin-as-submodules.md)
- [Container View](../architecture/container-view.md) — where this sits among the seams
- [`internal/render/fleet_table.py`](../../internal/render/fleet_table.py) — renders the pins onto the landing page
