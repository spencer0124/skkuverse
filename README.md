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
| **this repo** | Markdown · stdlib Python 3 | Cross-repo documentation **and** the config-contract registry that gates the four backend repos' CI | meta | — |

The last row is easy to overlook: `tools/skkuverse_sync.py` is not documentation. It runs as a **blocking check in server, app, ai and crawler CI**, so a bad commit here reddens four pipelines at once. See [`contracts/README.md`](contracts/README.md).

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
