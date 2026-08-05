# SKKUverse — System Documentation

> SKKUverse is a campus app for Sungkyunkwan University. This repository is the **hub that stitches a system spread across six repos into one picture** — it covers the boundaries between repos, the data that flows across them, and the reasoning behind both, rather than any single repo's code.

In one line: **two backend planes sharing a single MongoDB Atlas as their bus — a Python ingest plane (crawler + AI) and a NestJS serving plane — with only two synchronous HTTP seams between them. All of it on one free Oracle Cloud ARM VM, $0/month.**

## Start here

| Document | What it covers |
| --- | --- |
| [System Context](docs/architecture/system-context.md) | The system boundary — where SKKUverse meets the outside world (SKKU sites, FCM). C4 Level 1 |
| [Container View](docs/architecture/container-view.md) | How six repos, MongoDB and FCM fit together. C4 Level 2 |
| [**Notice Pipeline**](docs/flows/notice-pipeline.md) | The AI notice feature end to end (crawl → summarize → serve → push → render) |
| [Data Topology](docs/architecture/data-topology.md) | Which repo owns which collection, and where each schema is documented |
| [Config Contracts](contracts/README.md) | Config one repo owns and others vendor — hash-locked and enforced in CI |
| [Decisions (ADR)](docs/decisions/) | Choices whose consequences cross repo boundaries |

## Service topology

| Service | Stack | Role | Plane | Repo |
| --- | --- | --- | --- | --- |
| server | NestJS 11 · TS (strict) · MongoDB | Read API, bus information, push dispatch orchestration | serving | [skkuverse-server](https://github.com/spencer0124/skkuverse-server) |
| crawler | Python 3.12 · httpx · BeautifulSoup · motor · APScheduler | Crawls and cleans department notices and the academic calendar | ingest | [skkuverse-crawler](https://github.com/spencer0124/skkuverse-crawler) |
| ai | Python 3.12 · FastAPI · litellm | Structured extraction from notice bodies (summary, type, dates, locations) — stateless | ingest | [skkuverse-ai](https://github.com/spencer0124/skkuverse-ai) |
| app | Expo 54 · RN 0.81 · React 19 (Yarn monorepo) | Mobile client — live shuttle, notice feed, building search (iOS/Android) | client | [skkuverse-app](https://github.com/spencer0124/skkuverse-app) |
| web | Next.js | Marketing and landing site (`skkuverse.com`) | client | [skkuverse.com](https://github.com/spencer0124/skkuverse.com) |
| codepush | self-hosted `expo-open-ota` (Docker, `ota.skkuverse.com`) | Code-signed OTA update server for the app's JS bundle | infrastructure | [skkuverse-codepush](https://github.com/spencer0124/skkuverse-codepush) |
| **this repo** | Markdown · stdlib Python 3 | Cross-repo documentation, the config-contract registry, and the daily fleet pin | meta | — |

The last row is easy to overlook: `tools/skkuverse_sync.py` is not documentation. It runs as a **blocking check in server, app and ai CI** (the crawler is the producer and has nothing to verify), so a bad commit here reddens three pipelines at once. See [`contracts/README.md`](contracts/README.md).

## Fleet snapshot

Every repo's `main` as of the last daily snapshot. Written by
[`.github/workflows/fleet-snapshot.yml`](.github/workflows/fleet-snapshot.yml), which pins each repo
as a git submodule at the repository root once a day and commits — so this repository's history is a
day-by-day record of what the whole system was.

<!-- fleet:start -->
| Repo | Pinned `main` | Committed (KST) | Subject |
| --- | --- | --- | --- |
| skkuverse-server | [`e8ef4c8`](https://github.com/spencer0124/skkuverse-server/commit/e8ef4c857bd131dfca39866a4b7a877be6ec7589) | 2026-08-04 | Merge pull request #87 from spencer0124/dev |
| skkuverse-crawler | [`262cf89`](https://github.com/spencer0124/skkuverse-crawler/commit/262cf89eff83b51f3f5b79e3369a6a4a95225f93) | 2026-08-04 | Merge pull request #56 from spencer0124/dev |
| skkuverse-ai | [`fbcc37f`](https://github.com/spencer0124/skkuverse-ai/commit/fbcc37f54ddbd015f91e95f82835da10f2a5c01c) | 2026-08-04 | Merge pull request #5 from spencer0124/ci/contracts-integrity |
| skkuverse-app | [`f13fbcf`](https://github.com/spencer0124/skkuverse-app/commit/f13fbcf54ecce001b9e9905563b95fe62fc4d465) | 2026-08-04 | Merge pull request #22 from spencer0124/dev |
| skkuverse.com | [`85103e8`](https://github.com/spencer0124/skkuverse.com/commit/85103e8ab09f3008636e9a30010e2236531ff6e1) | 2026-06-07 | Merge branch 'dev' into main — fix miniapp deep-link scheme (triple-sla… |
| skkuverse-codepush | [`83f27d8`](https://github.com/spencer0124/skkuverse-codepush/commit/83f27d844fd54b046a511f010413527040572e86) | 2026-04-09 | chore: set TZ=Asia/Seoul in docker-compose |
<!-- fleet:end -->

This is a **pin, not a live view**, and that distinction is the point.
`python3 tools/skkuverse_sync.py check --fleet` reads every repo's *current* `main` over the network;
the two disagree by design whenever someone has pushed since the last snapshot. One answers what
`main` **was**, the other what `main` **is**.

Why record it at all — git cannot reconstruct it afterwards. `git rev-list --before=<date> main`
filters *all reachable commits* by date, so it happily returns a commit that sat on `dev` for days
before being merged; it tells you what existed, not what `main` pointed at. Nothing in git stores a
branch's historical tip except a reflog, which is local and expires.

To see the whole system as it was on a given day:

```bash
git rev-list -1 --before=2026-08-06 main   # that day's snapshot commit
git ls-tree <commit> | grep ^160000        # every repo's main, as SHAs
git submodule update --init                # expand it into the actual code
git log -- 'skkuverse*' 'repos/*'          # only the days something moved
```

Those six directories are a **record, not a workspace** — cloning this repository does not fetch them,
and you should not initialise them unless you are deliberately expanding a past day. Your own checkouts
live outside this repo.

## Per-repo documentation

System-wide knowledge lives here; **repo-local knowledge lives in that repo's own `docs/`** — ownership follows whoever writes or migrates the thing.

- [server docs](https://github.com/spencer0124/skkuverse-server/tree/main/docs) — read API contract, read indexes, FCM dispatch
- [crawler docs](https://github.com/spencer0124/skkuverse-crawler/tree/main/docs) — crawl strategies, sources, **`skku_notices` schema (SSOT)**
- [ai docs](https://github.com/spencer0124/skkuverse-ai/tree/main/docs) — LLM routing and provider fallback
- [app docs](https://github.com/spencer0124/skkuverse-app/tree/main/docs) — client rendering, FCM delivery, build and release
- [web](https://github.com/spencer0124/skkuverse.com) — marketing and landing (docs pending)
- [codepush](https://github.com/spencer0124/skkuverse-codepush) — self-hosted OTA infrastructure

## Conventions

Writing rules and the document index live in [docs/README.md](docs/README.md): Diátaxis structure, required frontmatter, and *point at the source, don't copy the value*. Working conventions for this repo, including the English-only rule, are in [CLAUDE.md](CLAUDE.md).
