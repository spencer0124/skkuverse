---
title: Notice Data Ownership — Crawler Writes, AI Contributes, Server Reads
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-04
audience: public
---

# ADR 0001 — Notice data ownership

> Three repos touch the `skku_notices.notices` collection. This is the cross-repo contract for what each of them owns. Repo-local perspectives link out to their own ADRs.

## Status

accepted (backfilled — written down while organising the system documentation hub)

## Context

`notices` is the only collection in SKKUverse with **multiple writers**. The crawler writes the body, an AI summary attaches asynchronously afterwards, and the server reads it to serve. When ownership is vague:

- two repos write the same field and race,
- the server starts writing a field "just this once" and a later re-crawl overwrites it,
- the schema gets documented in several repos and the copies drift apart.

## Decision

**Split field ownership by writer, and forbid reading repos from writing at all.**

| Repo | Owns | Rule |
| --- | --- | --- |
| crawler | Body fields (`title`, `contentText`, `cleanMarkdown`, `contentHash`, …) + the **`(articleNo, sourceId)` unique index** | The only thing that creates documents and cleans them |
| ai | — (no direct DB access) | Stateless. Returns the summary; the crawler performs the `$set` |
| ai summary fields | The `summary*` family | Written by the crawler from the AI response. A re-crawl never touches them |
| server | **Exactly one read index** (idempotent in `onModuleInit`) | Writes are forbidden. It owns only its own read optimisation |

**The canonical schema document is owned by the crawler** — [`docs/notice-schema.md`](https://github.com/spencer0124/skkuverse-crawler/blob/main/docs/notice-schema.md). Server and app document only their own perspective (read index, render contract) and link here for field definitions.

## Consequences

- ✅ No races — every field has exactly one writer.
- ✅ One schema SSOT, so the drift surface is as small as it can be.
- ✅ The AI service stays stateless, which makes it easy to retry, scale or replace.
- ⚠️ Because summaries attach asynchronously, the app **must** handle `summaryAt: null` ("summary pending") as a real state.
- ⚠️ The server will occasionally be tempted into a convenience write. The read-only invariant is held by code review and by the index ownership boundary, not by the database.

## Related

- server: [read-only ownership ADR](https://github.com/spencer0124/skkuverse-server/blob/main/docs/decisions/0002-notices-read-only-ownership.md)
- crawler: [`notices` schema SSOT](https://github.com/spencer0124/skkuverse-crawler/blob/main/docs/notice-schema.md)
- The whole flow: [Notice Pipeline](../flows/notice-pipeline.md)
- The same ownership idea applied to configuration: [ADR 0002](0002-pull-based-config-contracts.md)
