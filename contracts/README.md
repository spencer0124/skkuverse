---
title: Cross-Repo Config Contracts
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-04
audience: public
---

# Cross-Repo Config Contracts

> Configuration owned by one repo and vendored by another is a *contract*. [`manifest.json`](manifest.json) is the list of them, and [`../exported/sync_contracts.py`](../exported/sync_contracts.py) is what keeps the copies honest.

The whole fleet in one command:

```bash
python3 exported/sync_contracts.py status
```

## Why this exists

Propagation used to be a push from the crawler's codegen script. If the destination directory was missing it skipped silently — one line of stdout, exit 0, no return value:

```python
if dst.parent.exists():
    shutil.copy2(src, dst)
else:
    print(f"  -- Skipped {label} (directory not found)")
```

**A sync mechanism whose failure mode is silence produces drift that is indistinguishable from success.** Being push-based, it also only ran on a machine with every repo checked out side by side, so CI could never verify freshness. The full reasoning is in [ADR 0002](../docs/decisions/0002-pull-based-config-contracts.md).

## The three edges

Split by who can fix the failure.

| Edge | Compares | Network | Runs in | Severity |
| --- | --- | --- | --- | --- |
| **Integrity** | consumer file ↔ its own lock | no | every consumer's PR and deploy workflows | **hard fail — blocks merge and deploy** |
| **Freshness** | consumer lock ↔ producer@main | yes | every consumer, daily cron | **opens a PR against itself** |
| **Producer self-check** | regenerate ↔ committed artifacts | no | crawler CI | **hard fail** |

Per repo, the integrity check runs in:

| Repo | Workflows |
| --- | --- |
| server | `ci.yml` (after `npm run build`) and `deploy.yml` |
| app | `contracts.yml` — this repo's first CI, so there is no separate `ci.yml` |
| ai | `ci.yml` and `deploy.yml` |

Every blocking check is offline and is triggered by a file in the same repo as the PR, so a red build is always fixable in that branch. Editing a department in the crawler never reddens an unrelated server PR.

That split follows the governing rule for every check in this ecosystem, stated in [CLAUDE.md](../CLAUDE.md#constraints-that-are-not-negotiable). A blocking check that fails for a reason outside the author's branch is a design bug, and the fix is to move it to the freshness cron.

## Why hashes and not versions

Every value in a lock file is either a content hash computed by `pull` or a constant extracted from source. Nothing is hand-authored, so nothing can be hand-authored wrong. A version string invented by a human, such as `v3.5.1`, tells you nothing about what changed and starts lying the moment someone forgets to bump it.

**The manifest holds no hashes and no values.** It is the map of who gives what to whom, while hashes are state and live in each consumer's lock. The manifest therefore changes only when the set of contracts changes, which is rare. This is the same *point at the source, don't copy the value* rule the docs follow ([docs/README.md](../docs/README.md)).

## The comparison chain

A consumer's copy is a transform of the SSOT rather than a byte copy, because `hasCategory` and `hasAuthor` are derived from `strategy`. The thing to compare against is therefore the generated artifact, and that is why the crawler's `py/generated/` is committed rather than ignored.

```
crawler/sources.json                        SSOT, committed
    │  gen_sources_json()  [transform]
    ▼
crawler/py/generated/server-sources.json     committed
    │  ├── sha256 ──► lock.producer.sha256 + lock.producer.commit
    │  mode: copy
    ▼
server/src/notices/sources.json              committed
       └── sha256 ──► lock.sha256

edge 1 (blocking, offline):  sha256(server file)      == lock.sha256
edge 2 (cron, network):      lock.producer.sha256     == sha256(crawler@main artifact)
```

For `mode: generate` the two hashes differ by construction — `sha256` is of the produced consumer file, `producer.sha256` of the generator's input — which is why the lock carries both.

## Kinds of contract

- **`kind: file`, `mode: copy`** — a byte copy.
- **`kind: file`, `mode: generate`** — a generator in [`../exported/generators/`](../exported/generators/) derives the consumer file from the producer's. Generators must be deterministic: `pull` produces the file and `status` reproduces it to verify, so any nondeterminism reads as drift.
- **`kind: constant`** — a constant in source rather than a file, pulled out by regex and fail-closed. Anything other than exactly one match raises. "I can no longer find this constant" has to be a build failure, or a rename silently disables the check forever.

`relation` is `eq`, `lte` or `gte`. Direction matters for some contracts. `notices.topic-cap` is `lte` because the Cloud Function rejects any payload above `MAX_TOPICS`, so the server's `TOPIC_CAP` must stay at or below it — and only `lte` keeps the app-first deploy order that [ADR 0005 in skkuverse-server](https://github.com/spencer0124/skkuverse-server/blob/main/docs/decisions/0005-notice-dispatch-content-group.md) mandates green at every step:

| Step | app `MAX_TOPICS` | server `TOPIC_CAP` | `eq` | `lte` | Actually safe? |
| --- | --- | --- | --- | --- | --- |
| start | 10 | 10 | green | green | yes |
| app raises first | 30 | 10 | **red** | green | yes — server sends ≤10, CF accepts ≤30 |
| server catches up | 30 | 30 | green | green | yes |
| *wrong order:* server first | 10 | 30 | red | **red** | no — CF returns 400, retries burn to permanent failure |

`status` distinguishes `active` (enforced), `planned` (listed, skipped) and `retired`. Registering a contract as `planned` before it exists means the gap shows up in every `status` run rather than only in a README. Which entries are currently planned, and what each is waiting on, is generated onto the [landing page](../README.md#how-changes-propagate) from the manifest.

## Day-to-day

```bash
# whole fleet, offline, local working trees
python3 exported/sync_contracts.py status

# same, against origin/main
python3 exported/sync_contracts.py status --remote

# adopt upstream and refresh locks
python3 exported/sync_contracts.py pull --all

# the full chain for one contract
python3 exported/sync_contracts.py explain notices.topic-cap

# what CI runs, from inside a consumer repo
python3 exported/sync_contracts.py check --repo server --root .
```

`pull` rewrites a lock only when a value actually changed. `syncedAt` and `producer.commit` are provenance and are never compared. On a clean fleet it produces zero diffs, and without that property every run would dirty every repo and nobody would trust the tool.

### Adding a contract

1. Add the entry to `manifest.json` (starting at `status: "planned"` is fine).
2. `python3 exported/sync_contracts.py validate-manifest`
3. `pull --repo <consumer>`, then commit the lock in the consumer repo.
4. Flip to `status: "active"` in a follow-up.

That order matters: `check` tolerates a lock entry that is ahead of its activation, but activating first breaks the consumer's default branch until its lock lands.

For `mode: generate`, add the generator under `exported/generators/` and register it in `_load_generators()`. If the consumer is the server and the target is a runtime JSON under `src/`, add `"requires": ["server-build-asset"]` — a file missing from `scripts/copy-build-assets.js` exists in `src/` but vanishes from `dist/`, and the container dies at boot.

## Gotchas

- **Never resolve a `.contracts.lock.json` conflict by hand.** Rebasing a long-lived branch can conflict there. Take either side, then re-run `pull`.
- **`status` without `--remote` reads working trees**, so it can report "in sync" with an unpushed branch. A copy that matches the producer but is uncommitted gets its own `!` note, because CI reads git, not your disk.
- **The tool is cloned from `main`, unpinned.** A bad commit here reddens four pipelines at once. That is a deliberate trade — pinning would mean bumping a version in four repos on every tool change, which is exactly the manual version management this replaced. The blast radius is bounded by this repo's own CI, and recovery is one revert.

## Related

- [ADR 0002 — Pull-based config contracts](../docs/decisions/0002-pull-based-config-contracts.md) — why it is built this way
- [Container View §The third seam](../docs/architecture/container-view.md#the-third-seam-config-at-build-time) — where this sits architecturally
- [Data Topology](../docs/architecture/data-topology.md) — the same ownership rule for runtime data
