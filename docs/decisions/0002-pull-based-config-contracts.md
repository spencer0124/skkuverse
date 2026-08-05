---
title: Pull-Based Config Contracts with Content Hashes
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-04
audience: public
---

# ADR 0002 — Pull-based config contracts with content hashes

> Configuration owned by one repo and vendored by others used to be pushed across repo boundaries by a script whose failure mode was silence. It is now pulled, pinned by content hash, and enforced in CI.

## Status

accepted (2026-08-04)

## Context

Several config files have one owner and several consumers. `skkuverse-crawler` owns the notice source list, tab categories and exclusion reasons; `skkuverse-server` vendors derived copies; `skkuverse-app`'s Cloud Function mirrors the tab keys.

Propagation was a single function in the crawler's codegen script:

```python
def copy_to_sibling(src: Path, dst: Path, label: str) -> None:
    if dst.parent.exists():
        shutil.copy2(src, dst)
    else:
        print(f"  -- Skipped {label} (directory not found)")   # exit 0
```

Four problems, all of which had already caused real incidents or near-misses:

1. **Failure was indistinguishable from success.** A missing destination produced one line of stdout and exit 0. Downstream repos would serve stale config with nothing anywhere reporting a problem. A sibling repo pre-created and committed an empty directory purely to defeat this behaviour, and wrote that workaround into its README as a fact of life.
2. **It only worked on one machine.** Push resolved siblings positionally (`REPO_ROOT.parent / "skkuverse-server"`), so it required every repo checked out side by side. CI could never verify anything.
3. **The generated artifacts were gitignored**, so even with a working copy there was nothing committed to compare a consumer against.
4. **Some contracts are not files at all.** `TOPIC_CAP` in the server and `MAX_TOPICS` in the app's Cloud Function are a hand-mirrored constant pair. The only guard was a test asserting the literal `30` on one side — green in exactly the state that is dangerous.

## Decision

**Replace push with pull, pin everything by content hash, and split checks by who can fix the failure.**

A registry in this repo, [`contracts/manifest.json`](../../contracts/manifest.json), declares every cross-repo contract as pointers only: repos, paths, generators, extraction patterns. No hashes and no values live in the manifest. Those belong in each consumer's `.contracts.lock.json`, written exclusively by [`exported/sync_contracts.py`](../../exported/sync_contracts.py). The manifest therefore changes only when the set of contracts changes.

Three check edges, split by severity and owner:

| Edge | Compares | Network | Runs in | Severity |
| --- | --- | --- | --- | --- |
| Integrity | consumer file ↔ its own lock | no | each consumer's CI and deploy | **blocks merge and deploy** |
| Freshness | consumer lock ↔ producer@main | yes | each consumer, daily cron | **opens a PR against itself** |
| Producer | regenerate ↔ committed artifacts | no | crawler CI | **blocks merge** |

Three properties make this work:

- **No hand-authored versions.** Every lock value is a sha256 or an extracted constant computed by `pull`. A human never types a version string, so a human cannot mistype one. `pull` rewrites a lock only when a value actually changed, so a clean fleet produces zero diffs.
- **Blocking checks are offline.** Every check that can fail a merge or a deploy compares files inside one repo.
- **Extraction fails closed.** A constant whose regex no longer matches exactly once raises, naming the manifest field to fix. "I can no longer find this" is itself a build failure.

Directional contracts use a relation rather than equality. `notices.topic-cap` is `lte`, not `eq`, because the Cloud Function rejects payloads above its cap: the danger is one-directional, and equality would fail the mandated app-first deploy order in the middle.

## Consequences

- ✅ Silent drift is gone. Every failure mode above now produces a red build naming the cause and the exact command that fixes it.
- ✅ A class of previously undetectable bugs is caught. Adding a fixed notice tab without updating the app's mirror was documented as "self-detection impossible" — the symptom was zero notifications for that tab, with no error. It is now a hash mismatch.
- ✅ No credentials anywhere. Every repo is public, so pull needs no token, and the freshness cron opens a PR against its *own* repo using the built-in `GITHUB_TOKEN`. There is no cross-repo PAT in the system.
- ✅ The producer's artifacts are committed and reviewable, so a config change shows its downstream consequence in the producer's PR.
- ⚠️ **This repo is now a build dependency of four others.** They clone `exported/` at `main` during CI, unpinned. A bad commit here reddens four pipelines at once. Accepted deliberately: pinning would mean bumping a version in four repos on every tool change, which is the manual version management this decision exists to remove. The blast radius is bounded by this repo's own CI (unit tests plus `validate-manifest` on every PR), and recovery is a single revert.
- ⚠️ **Adopting a new contract needs an ordering.** The consumer's lock lands first, the manifest activation second. `check` therefore tolerates a lock entry that is ahead of its activation and fails only on entries the manifest no longer declares at all. Reversing the order breaks each consumer's default branch for the window in between.
- ⚠️ **Freshness is deliberately not blocking.** A consumer being behind is a working system rather than a broken one, and it is not fixable in the branch that would go red. That is the governing rule stated in [CLAUDE.md](../../CLAUDE.md#constraints-that-are-not-negotiable) applied to this edge.

## Alternatives considered

**Keep push, make it fail loudly.** Rejected. The producer's own CI runs on a runner with no sibling checkouts, so a loud copy would abort the most valuable check in the design. More fundamentally, push cannot write the consumer's lock, so it would leave consumers red on a copy the tooling itself had just made — and the failure that actually bit us was a forgotten *commit*, not a failed copy.

**A schema registry or a Pact broker.** Rejected as disproportionate. Those solve versioned message compatibility between independently deploying teams. This is one maintainer with mostly static config files; a manifest plus a CI check covers it for a fraction of the effort.

**A monorepo.** Would dissolve the problem entirely, but three languages and four deploy targets make it a large migration to fix something a manifest and a check already fix.

## Related

- [Config Contracts](../../contracts/README.md) — how to operate this day to day
- [Container View §The third seam](../architecture/container-view.md#the-third-seam-config-at-build-time) — where this sits in the architecture
- [ADR 0001](0001-notice-data-ownership.md) — the same producer-owns-it rule, applied to runtime data
