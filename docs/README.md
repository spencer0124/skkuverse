---
title: Docs Index & Conventions
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-04
audience: internal
---

# Docs Index & Conventions

> The index and the writing rules for the SKKUverse documentation hub. This repository holds **cross-cutting knowledge only** — anything local to one repo belongs in that repo's `docs/`.

## What belongs here

| Belongs here (cross-repo) | Does not (repo-local) |
| --- | --- |
| System boundaries and architecture diagrams | One repo's build or deploy runbook |
| Data flows that cross repo lines (the notice pipeline) | The detailed schema of one collection (→ owning repo) |
| Ownership maps — who writes what | Framework-specific implementation detail |
| ADRs whose consequences cross repos | ADRs that begin and end in one repo |

**Rule: never copy a schema or a number into this repo.** This is an *index and a map* — link to the owning repo's document for detail. ([Data Topology](architecture/data-topology.md) is that map for runtime data; [`contracts/manifest.json`](../contracts/manifest.json) is the machine-readable one for config.)

## Folder structure (Diátaxis)

Adopted from skkuverse-app's convention as the workspace standard. **Documents are filed by the reader's need, not by topic.**

| Folder | Diátaxis need | Contents |
| --- | --- | --- |
| `architecture/` | Explanation — *understand* | System boundary, container view, data topology (C4) |
| `flows/` | Explanation — *understand* | End-to-end flows that cross repos |
| `decisions/` | (ADR) | Cross-repo ADRs, `NNNN-kebab-title.md` |
| `../contracts/` | Reference — *look up* | The config-contract registry. Lives outside `docs/` because `manifest.json` is read by tooling, not by people; the prose beside it follows every rule on this page. |

## Document index

### architecture

| Document | Summary |
| --- | --- |
| [system-context.md](architecture/system-context.md) | C4 L1 — the system boundary and its external touchpoints |
| [container-view.md](architecture/container-view.md) | C4 L2 — how the repos, MongoDB and FCM interlock, plus the build-time config seam |
| [data-topology.md](architecture/data-topology.md) | Which repo owns which database and collection, with links to each schema |

### flows

| Document | Summary |
| --- | --- |
| [notice-pipeline.md](flows/notice-pipeline.md) | The AI notice feature end to end (crawl → AI → serve → push → render) |

### decisions

| Document | Status |
| --- | --- |
| [0001-notice-data-ownership.md](decisions/0001-notice-data-ownership.md) | accepted |
| [0002-pull-based-config-contracts.md](decisions/0002-pull-based-config-contracts.md) | accepted |

### contracts (machine-readable)

The only material outside `docs/`. It is a registry read by tooling rather than prose — but the *point at the source, don't copy the value* rule above still holds: the manifest carries pointers only (repos, paths, generators), while hashes and values live in each consumer's `.contracts.lock.json`. That is why the manifest changes only when the **set** of contracts changes.

| File | Summary |
| --- | --- |
| [contracts/README.md](../contracts/README.md) | How the contract system works — three edges, hash locks, day-to-day commands |
| [contracts/manifest.json](../contracts/manifest.json) | Contract topology (producer, consumers, generators). Two of its entries are `planned` rather than `active` |
| [tools/skkuverse_sync.py](../tools/skkuverse_sync.py) | The tool that enforces it. Runs as a blocking gate in four other repos' CI |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Unit tests + `validate-manifest` — what bounds this repo's blast radius |
| [.github/workflows/fleet.yml](../.github/workflows/fleet.yml) | On-demand fleet-wide freshness report |

## Writing rules

### 1. Frontmatter (required)

```yaml
---
title: <Title Case>
type: reference | explanation | adr
status: draft | accepted | superseded | deprecated
owner: zoyoong124@gmail.com
last-updated: YYYY-MM-DD
audience: internal | public
---
```

Required on **every document listed in the index above**, including the ones outside `docs/` such as [`contracts/README.md`](../contracts/README.md). `audience: public` for anything published as portfolio; `audience: internal` for private working notes.

Exempt: the two repo-root entry points, [`README.md`](../README.md) and [`CLAUDE.md`](../CLAUDE.md). GitHub renders frontmatter as a table, which does not belong on a landing page, and neither file is a catalogued document — one is the front door, the other is tooling configuration.

Update `last-updated` in the same commit that changes the body. A stale date is the cheapest possible lie.

### 2. Skeleton

frontmatter → exactly one `# H1` → `> one-line summary` → `##` sections, no skipped levels. Copy [`_template.md`](_template.md) to start.

### 3. Point at the source, don't copy the value

Never hardcode a version, count, or schema field from another repo. When that repo changes, this one starts lying silently.

- ❌ `there are 149 crawl sources`
- ✅ `the source list's SSOT is skkuverse-crawler's sources.json` (a count only as "~149 at time of writing", if at all)

### 4. Diagrams

- **Mermaid by default** — GitHub renders it natively, no build step. Use a `mermaid` code fence.
- Only when Mermaid genuinely cannot express it, put PlantUML/C4 sources in `diagrams/`.

### 5. Language

**English, everywhere.** Prose, headings, diagram labels, table cells, code comments in samples. The one carve-out is Korean product copy quoted *as data* — user-facing strings shipped to the app. See [CLAUDE.md](../CLAUDE.md) for the full policy and its rationale.

### 6. Filenames and formatting

- Lowercase kebab-case `.md`. ADRs are `NNNN-kebab-title.md`.
- Code fences always carry a language tag. Structured facts go in tables.

## Related

- [Workspace landing page](../README.md)
- [CLAUDE.md](../CLAUDE.md) — working conventions, including the language policy
- [skkuverse-app docs conventions](https://github.com/spencer0124/skkuverse-app/tree/main/docs) — the original standard this adopts
