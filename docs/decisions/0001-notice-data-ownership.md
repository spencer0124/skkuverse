---
title: 공지 데이터 소유권 — 크롤러 쓰기 / AI $set / 서버 읽기 전용
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-07-24
audience: public
---

# ADR 0001 — 공지 데이터 소유권

> `skku_notices.notices` 컬렉션을 세 레포가 손대는데, 각자가 무엇을 소유하는지의 cross-repo 계약. 레포별 관점은 각 레포의 ADR을 링크한다.

## Status

accepted (백필 — 시스템 문서 허브 정리 시점에 명문화)

## Context

`notices`는 SKKUverse에서 유일하게 **복수 writer가 공유하는 컬렉션**이다. 크롤러가 원문을 쓰고, AI 요약이 나중에 비동기로 붙고, 서버가 읽어서 서빙한다. 소유가 흐려지면:

- 같은 필드를 두 레포가 쓰며 race가 나거나,
- 서버가 편의상 필드를 덧쓰기 시작해 크롤러의 재크롤이 그것을 덮어버리거나,
- 스키마 문서가 여러 레포에 복제돼 drift가 난다.

## Decision

**필드 소유를 writer 기준으로 분할하고, 읽기 레포는 절대 쓰지 않는다.**

| 레포 | 소유 | 규칙 |
| --- | --- | --- |
| crawler | 원문 필드(`title`, `contentText`, `cleanMarkdown`, `contentHash` 등) + **`(articleNo, sourceId)` 유니크 인덱스** | 문서 생성·정제(sanitize/markdown)의 유일 주체 |
| ai | — (DB 직접 접근 없음) | stateless. 요약 결과를 반환만 하고, 실제 `$set`은 크롤러가 대행 |
| ai 요약 필드 | `summary*` 계열 필드 | 크롤러가 AI 응답으로 `$set`. 크롤러 재크롤은 이 필드를 건드리지 않음 |
| server | **읽기 인덱스 1개** (`onModuleInit` idempotent) | 절대 write 금지. 읽기 최적화 인덱스만 소유 |

**스키마 canonical 문서는 crawler가 소유** (`reference/schema/notices.md`). 서버·앱은 자기 관점(읽기 인덱스, 렌더 계약)만 문서화하고 필드 정의는 크롤러를 링크한다.

## Consequences

- ✅ race 없음 — 필드별 단일 writer.
- ✅ 스키마 SSOT 하나 — drift 표면 최소화.
- ✅ AI를 stateless로 유지 → 확장·재시도·교체가 쉬움 (DB 결합 없음).
- ⚠️ 요약이 "비동기로 붙는" 구조라 앱은 `summaryAt: null` 상태(요약 준비 중)를 반드시 처리해야 함.
- ⚠️ 서버가 편의 write를 하고 싶은 유혹이 생길 수 있음 — 읽기 전용 불변식은 코드 리뷰/인덱스 소유 경계로 지킨다.

## 레포별 관점 (링크)

- server: [읽기 전용 소유 ADR](https://github.com/spencer0124/skkuverse-server/tree/main/docs/decisions) (`0002-notices-read-only-ownership`)
- crawler: [`notices` 스키마 SSOT](https://github.com/spencer0124/skkuverse-crawler/tree/main/docs)
- 흐름 전체: [공지 파이프라인](../flows/notice-pipeline.md)
