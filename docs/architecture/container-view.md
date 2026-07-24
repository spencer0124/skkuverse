---
title: Container View
type: explanation
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-07-24
audience: public
---

# Container View

> 시스템 안쪽 — 6개 레포와 MongoDB·Firebase가 어떻게 맞물리나 (C4 Level 2). 위 단계는 [시스템 컨텍스트](system-context.md), 이 그림이 실제로 흐르는 모습은 [공지 파이프라인](../flows/notice-pipeline.md).

## 핵심 아이디어: DB-as-bus, 두 개의 평면

메시지 큐가 없다. **MongoDB Atlas 하나를 버스(bus)로** 쓰고, 그 위에 동기 HTTP 시임(seam) 2개만 얹었다.

- **쓰기/수집 평면 (Python)**: 크롤러가 원문을 수집·정제해 Mongo에 쓰고, AI 서버(stateless)에 요약을 위임받아 같은 문서에 덧쓴다.
- **읽기/서빙 평면 (NestJS)**: 서버는 Mongo를 읽어 API로 서빙하고, 푸시 디스패치만 오케스트레이션한다 (전송 자체는 Firebase Cloud Function에 위임).

두 평면은 서로를 직접 호출하지 않는다 — **Mongo를 통해 비동기로 만나고**, 동기 HTTP는 딱 두 곳(크롤러→AI 요약, 크롤러→서버 디스패치 핑)뿐이다.

## 다이어그램

```mermaid
graph TB
    subgraph write["쓰기 / 수집 평면 (Python)"]
        crawler["crawler<br/>httpx · BeautifulSoup · motor · APScheduler"]
        ai["ai<br/>FastAPI · litellm (stateless)"]
    end

    subgraph read["읽기 / 서빙 평면 (NestJS)"]
        server["server<br/>NestJS · TS strict"]
    end

    subgraph clients["클라이언트"]
        app["app<br/>Expo · RN"]
        web["web<br/>Next.js"]
    end

    mongo[("MongoDB Atlas<br/>(the bus)")]
    cf["Firebase<br/>Cloud Function → FCM"]

    crawler -->|upsert 원문| mongo
    crawler -->|① POST /summarize (동기 HTTP)| ai
    ai -.->|요약 반환| crawler
    crawler -->|$set summary*| mongo
    crawler -->|② POST /dispatch-pending (동기 HTTP)| server
    server -->|read-only| mongo
    server -->|push 위임| cf
    cf -->|FCM| app
    app -->|read API| server
    web -->|read API| server
```

## 컨테이너별 책임과 소유

| 컨테이너 | 책임 | Mongo 관계 | 문서 |
| --- | --- | --- | --- |
| crawler | 크롤·정제·요약 오케스트레이션. `notices`/`schedule`(+예정 `restaurant`) **문서와 유니크 인덱스 소유** | 주 writer | [crawler docs](https://github.com/spencer0124/skkuverse-crawler/tree/main/docs) |
| ai | 공지 원문 → 구조화 요약. **상태 없음, DB 접근 없음** | 없음 | [ai docs](https://github.com/spencer0124/skkuverse-ai/tree/main/docs) |
| server | 읽기 API + 푸시 디스패치. **`summary*` 안 씀, 읽기 인덱스 1개만 소유** | read-only (+ 1 read index) | [server docs](https://github.com/spencer0124/skkuverse-server/tree/main/docs) |
| app | 서버 주도 탭 + 마크다운 렌더 + 푸시 수신 | 없음 (API 경유) | [app docs](https://github.com/spencer0124/skkuverse-app/tree/main/docs) |
| web | 마케팅 웹 | 없음 | (예정) |

두 HTTP 시임:

- **① 크롤러 → AI** (`POST /api/notices/summarize`): Docker 네트워크 내부, 인증 없음(네트워크 격리). 요약이 비동기로 "붙는" 유일한 경로.
- **② 크롤러 → 서버** (`POST /internal/notices/dispatch-pending`): 사이클 끝에 fire-and-forget 핑. `X-Internal-Token`. 안전망으로 서버측 30분 cron sweep 병행.

## 관련 문서

- [공지 파이프라인](../flows/notice-pipeline.md) — 이 그림의 동적 시퀀스
- [데이터 토폴로지](data-topology.md) — 버스(Mongo) 위 컬렉션 소유권
- [ADR 0001 — 공지 데이터 소유권](../decisions/0001-notice-data-ownership.md)
